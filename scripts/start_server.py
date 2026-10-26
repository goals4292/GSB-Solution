from pathlib import Path
import subprocess, sys
root=Path(__file__).resolve().parents[1]
if not (root/'.secrets/password.json').exists():
    raise SystemExit('먼저 python scripts/setup_password.py를 실행하세요.')
raise SystemExit(subprocess.call([sys.executable,'-m','jupyterlab','--config',str(root/'deploy/jupyter_server_config.py')],cwd=root))
