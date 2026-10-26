"""Shared-link Jupyter; use inside the isolated deployment container."""
import os
from pathlib import Path

c = get_config()
root = Path(os.environ.get('GSB_WORKSPACE', '/workspace')).resolve()
token_file = Path(os.environ.get('GSB_TOKEN_FILE', '/run/secrets/jupyter_token'))
token = token_file.read_text(encoding='utf-8').strip()
if len(token) < 32:
    raise RuntimeError('Run scripts/prepare_shared_runtime.py to create the link token.')
c.ServerApp.ip = os.environ.get('GSB_BIND_IP', '0.0.0.0')
c.ServerApp.port = int(os.environ.get('GSB_PORT', '8888'))
c.ServerApp.port_retries = 0
c.ServerApp.root_dir = str(root)
c.ServerApp.open_browser = False
c.ServerApp.default_url = '/lab/tree/GSB_quality_analysis.ipynb'
c.ServerApp.allow_remote_access = True
c.ServerApp.terminals_enabled = False
c.IdentityProvider.token = token
c.PasswordIdentityProvider.hashed_password = ''
c.PasswordIdentityProvider.password_required = False
# Keep the default XSRF checks and same-origin policy.
