"""Unprivileged, filesystem/network-isolated Jupyter with an external ngrok relay.

The relay transports HTTP/WebSocket bytes through a Unix socket. The notebook
kernel cannot access the host network, home directory or ngrok credentials.
"""
from pathlib import Path
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import resource
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path.home() / '.local/share/gsb-tools'
STATE = Path.home() / '.local/state/gsb-solution' / hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]
WORK = ROOT / 'private/shared-runtime'
SANDBOX_PID_NAMESPACE = None


def write_json(name, data):
    path = STATE / name
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temp.chmod(0o600)
    temp.replace(path)


def process_start(pid):
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]


def running():
    try:
        info = json.loads((STATE / 'pid.json').read_text())
        if process_start(info['pid']) == info['start']:
            return info['pid']
    except (OSError, ValueError, KeyError, IndexError):
        pass
    return None


def sandbox_command(info_fd):
    bwrap = shutil.which('bwrap') or str(TOOLS / 'bubblewrap/usr/bin/bwrap')
    if not Path(bwrap).is_file():
        raise RuntimeError('Install bubblewrap for this user first.')
    venv, base = Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()
    socks = STATE / 'sockets'
    socks.mkdir(exist_ok=True, mode=0o700)
    (socks / 'jupyter.sock').unlink(missing_ok=True)
    (STATE / 'hosts').write_text('127.0.0.1 localhost gsb-solution\n::1 localhost\n')
    (STATE / 'passwd').write_text(f'gsb:x:{os.getuid()}:{os.getgid()}::/tmp/gsb-home:/bin/sh\n')
    (STATE / 'group').write_text(f'gsb:x:{os.getgid()}:\n')
    cmd = [bwrap, '--unshare-all', '--unshare-user', '--new-session', '--die-with-parent',
           '--info-fd', str(info_fd),
           '--cap-drop', 'ALL', '--hostname', 'gsb-solution', '--clearenv',
           '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--dir', '/tmp/gsb-home', '--dir', '/run']
    for name in ['/usr/bin', '/usr/lib', '/usr/lib64', '/usr/share/fonts', '/usr/share/fontconfig', '/usr/share/zoneinfo']:
        if Path(name).exists():
            cmd += ['--ro-bind', name, name]
    for name in ['bin', 'lib', 'lib64']:
        cmd += ['--symlink', 'usr/' + name, '/' + name]
    for path in {venv, base}:
        cmd += ['--ro-bind', str(path), str(path)]
    executable = venv / 'bin/python'
    if executable.is_symlink():
        target = Path(os.readlink(executable))
        if target.is_absolute() and target.parent.parent != base:
            # uv uses an unversioned interpreter alias in the venv symlink.
            cmd += ['--ro-bind', str(base), str(target.parent.parent)]
    for name in ['hosts', 'passwd', 'group']:
        cmd += ['--ro-bind', str(STATE / name), '/etc/' + name]
    cmd += ['--bind', str(WORK), '/workspace', '--bind', str(socks), '/run/gsb',
            '--ro-bind', str(ROOT / 'deploy/jupyter_shared_config.py'), '/run/jupyter_config.py',
            '--chdir', '/workspace']
    env = {'HOME': '/tmp/gsb-home', 'USER': 'gsb', 'LOGNAME': 'gsb',
           'PATH': str(venv / 'bin') + ':/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TZ': 'Asia/Seoul',
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1',
           'JUPYTER_RUNTIME_DIR': '/tmp/jupyter-runtime', 'GSB_WORKSPACE': '/workspace',
           'GSB_PUBLIC_ACCESS': '1', 'GSB_SOCKET': '/run/gsb/jupyter.sock',
           'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
    for name, value in env.items():
        cmd += ['--setenv', name, value]
    return cmd + [str(venv / 'bin/python'), '-m', 'jupyterlab', '--config=/run/jupyter_config.py']


def limits():
    for key, value in [(resource.RLIMIT_CORE, 0), (resource.RLIMIT_AS, 3 * 1024**3),
                       (resource.RLIMIT_NOFILE, 1024), (resource.RLIMIT_FSIZE, 512 * 1024**2)]:
        resource.setrlimit(key, (value, value))


async def relay(reader, writer):
    upstream = None
    async def copy(source, target):
        while data := await source.read(65536):
            target.write(data)
            await target.drain()
    try:
        incoming, upstream = await asyncio.open_unix_connection(str(STATE / 'sockets/jupyter.sock'))
        # The workspace can rename its socket. Never relay to a host socket even
        # if that path is replaced by a symlink between lookup and connect.
        raw = upstream.get_extra_info('socket').getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        peer_pid, peer_uid, _ = struct.unpack('3i', raw)
        peer_namespace = str(Path(f'/proc/{peer_pid}/ns/pid').readlink())
        if peer_uid != os.getuid() or peer_namespace != SANDBOX_PID_NAMESPACE:
            return
        tasks = [asyncio.create_task(copy(reader, upstream)), asyncio.create_task(copy(incoming, writer))]
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    except (OSError, ConnectionError):
        pass
    finally:
        for stream in [upstream, writer]:
            if stream:
                stream.close()
                try:
                    await stream.wait_closed()
                except (OSError, ConnectionError):
                    pass


def tunnel_url(port):
    with urlopen(f'http://127.0.0.1:{port}/api/tunnels', timeout=3) as r:
        urls = [t['public_url'] for t in json.load(r)['tunnels'] if t['public_url'].startswith('https://')]
    if len(urls) != 1:
        raise RuntimeError('Waiting for an HTTPS tunnel')
    return urls[0]


async def serve(local_only):
    global SANDBOX_PID_NAMESPACE
    stop = asyncio.Event()
    for sig in [signal.SIGTERM, signal.SIGINT]:
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    children, logs, server = [], [], None
    def launch(cmd, logname, **kwargs):
        log = (STATE / logname).open('a'); logs.append(log)
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                start_new_session=True, **kwargs)
        children.append(proc)
        return proc
    try:
        read_fd, write_fd = os.pipe()
        try:
            jupyter = launch(sandbox_command(write_fd), 'jupyter.log', preexec_fn=limits,
                             pass_fds=(write_fd,))
        finally:
            os.close(write_fd)
        with os.fdopen(read_fd) as info:
            child = await asyncio.to_thread(json.load, info)
        SANDBOX_PID_NAMESPACE = str(Path(f'/proc/{child["child-pid"]}/ns/pid').readlink())
        for _ in range(120):
            if jupyter.poll() is not None:
                raise RuntimeError('Sandbox startup failed; inspect jupyter.log')
            if (STATE / 'sockets/jupyter.sock').exists():
                break
            if stop.is_set():
                return
            await asyncio.sleep(.5)
        else:
            raise RuntimeError('Sandbox startup timed out')
        server = await asyncio.start_server(relay, '127.0.0.1', 0)
        port = server.sockets[0].getsockname()[1]
        status = {'state': 'local-ready', 'proxy_port': port, 'workspace': str(WORK), 'network_isolated': True}
        write_json('status.json', status)
        if not local_only:
            ngrok = shutil.which('ngrok') or str(TOOLS / 'bin/ngrok')
            lines = (ROOT / '.secrets/ngrok.env').read_text().splitlines()
            token = next(x.split('=', 1)[1] for x in lines if x.startswith('NGROK_AUTHTOKEN='))
            if not token:
                raise RuntimeError('Missing ngrok account token')
            with socket.socket() as s:
                s.bind(('127.0.0.1', 0)); api_port = s.getsockname()[1]
            config = STATE / 'ngrok.yml'
            config.write_text(f'version: "3"\nagent:\n  web_addr: 127.0.0.1:{api_port}\n')
            proc = launch([ngrok, 'http', f'http://127.0.0.1:{port}', '--inspect=false',
                           '--config=' + str(config), '--log=stdout', '--log-format=json'],
                          'ngrok.log', env={'HOME': str(Path.home()), 'PATH': os.defpath, 'NGROK_AUTHTOKEN': token})
            for _ in range(90):
                if proc.poll() is not None:
                    raise RuntimeError('ngrok failed; inspect ngrok.log')
                try:
                    public = await asyncio.to_thread(tunnel_url, api_port)
                    break
                except (OSError, ValueError, RuntimeError, KeyError):
                    pass
                if stop.is_set():
                    return
                await asyncio.sleep(1)
            else:
                raise RuntimeError('ngrok endpoint startup timed out')
            link = public + '/lab/tree/GSB_quality_analysis.ipynb'
            target = ROOT / 'private/notebook_link.txt'
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(link + '\n')
            target.chmod(0o600)
            status.update(state='ready', public_url=public, ngrok_api_port=api_port)
            write_json('status.json', status)
        while not stop.is_set():
            if any(p.poll() is not None for p in children):
                raise RuntimeError('A shared-server component stopped unexpectedly')
            try:
                await asyncio.wait_for(stop.wait(), 1)
            except asyncio.TimeoutError:
                pass
    except Exception as exc:
        write_json('status.json', {'state': 'error', 'message': str(exc)})
        raise
    finally:
        if server:
            server.close(); await server.wait_closed()
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    await asyncio.to_thread(child.wait, 10)
                except subprocess.TimeoutExpired:
                    child.kill(); await asyncio.to_thread(child.wait)
        for log in logs:
            log.close()
        if stop.is_set():
            write_json('status.json', {'state': 'stopped'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop', 'status', '_serve'])
    parser.add_argument('--local-only', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE.chmod(0o700)
    if args.action == 'status':
        info = json.loads((STATE / 'status.json').read_text()) if (STATE / 'status.json').exists() else {'state': 'not-started'}
        info['running'] = bool(running())
        print(json.dumps(info, ensure_ascii=False, indent=2)); return
    if args.action == 'stop':
        if pid := running():
            os.kill(pid, signal.SIGTERM)
            for _ in range(60):
                if not running():
                    break
                time.sleep(.5)
            else:
                raise SystemExit('Shutdown still in progress; inspect logs.')
        print('Shared server stopped.'); return
    if args.action == 'start':
        if running():
            print('Already running; use status or stop first.'); return
        required = [WORK / 'GSB_quality_analysis.ipynb']
        if not args.local_only:
            required.append(ROOT / '.secrets/ngrok.env')
        if any(not p.is_file() for p in required):
            raise SystemExit('Run prepare_shared_runtime.py and setup_ngrok.py first.')
        (STATE / 'status.json').unlink(missing_ok=True)
        cmd = [sys.executable, str(Path(__file__).resolve()), '_serve']
        if args.local_only:
            cmd.append('--local-only')
        with (STATE / 'supervisor.log').open('a') as log:
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                    start_new_session=True, cwd=ROOT)
        print('Starting isolated server. PID:', proc.pid)
        print('Status/log directory:', STATE); return
    with (STATE / 'lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another supervisor is already running.')
        write_json('pid.json', {'pid': os.getpid(), 'start': process_start(os.getpid())})
        try:
            asyncio.run(serve(args.local_only))
        finally:
            (STATE / 'pid.json').unlink(missing_ok=True)


if __name__ == '__main__':
    main()
