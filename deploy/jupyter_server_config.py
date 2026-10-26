import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
secret = ROOT / '.secrets' / 'password.json'
if not secret.exists():
    raise RuntimeError('먼저 python scripts/setup_password.py를 실행하세요.')
c = get_config()
c.ServerApp.ip = '127.0.0.1'
c.ServerApp.port = 8888
c.ServerApp.port_retries = 0
c.ServerApp.root_dir = str(ROOT)
c.ServerApp.open_browser = False
c.ServerApp.default_url = '/lab/tree/GSB_quality_analysis.ipynb'
c.ServerApp.allow_remote_access = True
c.PasswordIdentityProvider.hashed_password = json.loads(secret.read_text(encoding='utf-8'))['hashed_password']
c.PasswordIdentityProvider.password_required = True
