"""Verify anonymous access, XSRF protection, isolation and complete execution."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import uuid
from urllib.parse import urlsplit
import requests
import websocket
import nbformat
from shared_no_sudo import ROOT, STATE

p = argparse.ArgumentParser()
p.add_argument('--local', action='store_true')
args = p.parse_args()
status = json.loads((STATE / 'status.json').read_text())
base = f'http://127.0.0.1:{status["proxy_port"]}' if args.local else status['public_url']
session = requests.Session()
session.headers['ngrok-skip-browser-warning'] = 'verification'
assert session.get(base + '/api/contents', allow_redirects=False, timeout=20).status_code == 200
page = session.get(base + '/lab/tree/GSB_quality_analysis.ipynb', timeout=30)
page.raise_for_status()
assert '/login' not in urlsplit(page.url).path
assert 'Token authentication is enabled' not in page.text
response = session.get(base + '/api/contents/GSB_quality_analysis.ipynb', timeout=20)
response.raise_for_status()
nb = nbformat.from_dict(response.json()['content'])
xsrf = session.cookies.get('_xsrf')
assert xsrf, 'Expected the browser XSRF cookie'
denied = session.post(base + '/api/kernels', json={'name': 'python3'}, timeout=20)
assert denied.status_code == 403, 'Mutating requests without XSRF proof must be rejected'
session.headers['X-XSRFToken'] = xsrf
session.headers['Referer'] = base + '/lab'
print('PASS: fresh unauthenticated access without token/password; XSRF protection retained.', flush=True)
response = session.post(base + '/api/kernels', json={'name': 'python3'}, timeout=30)
response.raise_for_status()
kid = response.json()['id']
parts = urlsplit(base)
url = ('wss' if parts.scheme == 'https' else 'ws') + '://' + parts.netloc + f'/api/kernels/{kid}/channels?session_id={uuid.uuid4().hex}'
ws = None
try:
    ws = websocket.create_connection(url, origin=base,
                                    header=['ngrok-skip-browser-warning: verification'],
                                    cookie='; '.join(f'{k}={v}' for k, v in session.cookies.items()), timeout=120)
    sid = uuid.uuid4().hex

    def execute(code, history=True):
        mid = uuid.uuid4().hex
        ws.send(json.dumps({'header': {'msg_id': mid, 'username': 'validation', 'session': sid,
                                      'date': datetime.now(timezone.utc).isoformat(),
                                      'msg_type': 'execute_request', 'version': '5.3'},
                            'parent_header': {}, 'metadata': {}, 'channel': 'shell',
                            'content': {'code': code, 'silent': False, 'store_history': history,
                                        'user_expressions': {}, 'allow_stdin': False, 'stop_on_error': True}}))
        outputs, count = [], None
        while True:
            message = json.loads(ws.recv())
            if message.get('parent_header', {}).get('msg_id') != mid:
                continue
            kind, content = message['header']['msg_type'], message['content']
            if kind == 'execute_input':
                count = content['execution_count']
            if kind == 'error':
                raise RuntimeError(content['ename'] + ': ' + content['evalue'])
            if kind == 'execute_reply' and content['status'] != 'ok':
                raise RuntimeError('Kernel execute_reply failed')
            if kind == 'stream':
                outputs.append(nbformat.v4.new_output('stream', name=content['name'], text=content['text']))
            elif kind in ('display_data', 'execute_result'):
                values = {'data': content['data'], 'metadata': content.get('metadata', {})}
                if kind == 'execute_result':
                    values['execution_count'] = content['execution_count']
                outputs.append(nbformat.v4.new_output(kind, **values))
            if kind == 'status' and content['execution_state'] == 'idle':
                return outputs, count

    host_net = str(Path('/proc/self/ns/net').readlink())
    host_pid = str(Path('/proc/self/ns/pid').readlink())
    isolation = f'''
import os
from pathlib import Path
assert not Path('/mnt/pilab_nas').exists()
assert not Path('/home/jykim/.config/gh/hosts.yml').exists()
assert not Path('/home/jykim/.ssh').exists()
assert not Path('/workspace/.secrets').exists()
assert 'NGROK_AUTHTOKEN' not in os.environ
assert str(Path('/proc/self/ns/net').readlink()) != {host_net!r}
assert str(Path('/proc/self/ns/pid').readlink()) != {host_pid!r}
assert Path.cwd() == Path('/workspace')
'''
    execute(isolation, history=False)
    print('PASS: host files, credentials, network and process namespace isolated.', flush=True)
    for cell in nb.cells:
        if cell.cell_type == 'code':
            cell.outputs, cell.execution_count = execute(cell.source)
    images = sum('image/png' in output.get('data', {}) for cell in nb.cells for output in cell.get('outputs', []))
    assert images >= 3, f'Missing inline images: {images}'
    nbformat.validate(nb)
    response = session.put(base + '/api/contents/GSB_quality_analysis.ipynb',
                           json={'type': 'notebook', 'format': 'json', 'content': nb}, timeout=30)
    response.raise_for_status()
    response = session.get(base + '/api/contents/outputs', timeout=20)
    response.raise_for_status()
    assert response.json()['content'], 'No output artifacts were created'
    print(f'PASS: all {sum(c.cell_type == "code" for c in nb.cells)} cells executed; {images} images saved in shared notebook.')
finally:
    if ws:
        ws.close()
    session.delete(base + '/api/kernels/' + kid, timeout=20).raise_for_status()
