"""Read the operator's ngrok token locally; never write it to shared files."""
from getpass import getpass
from pathlib import Path
import os

root = Path(__file__).resolve().parents[1]
token = getpass('ngrok authtoken (hidden): ').strip()
if not token or any(ch.isspace() for ch in token) or not all(ch.isalnum() or ch in '_-' for ch in token):
    raise SystemExit('Invalid token. Copy the authtoken from your ngrok dashboard.')
folder = root / '.secrets'
folder.mkdir(exist_ok=True, mode=0o700)
folder.chmod(0o700)
path = folder / 'ngrok.env'
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as f:
    f.write('NGROK_AUTHTOKEN=' + token + '\n')
path.chmod(0o600)
print('ngrok account token saved locally. It is not the company access link.')
