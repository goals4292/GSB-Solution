"""Write a password-free access link to a private file without printing its token."""
from pathlib import Path
from urllib.parse import urlsplit, urlencode
from urllib.request import urlopen
import argparse
import json
import os

p = argparse.ArgumentParser()
p.add_argument('--base-url', help='ngrok HTTPS origin; otherwise query the local agent')
p.add_argument('--legacy-password', action='store_true')
args = p.parse_args()
root = Path(__file__).resolve().parents[1]
base = args.base_url
if not base:
    try:
        with urlopen('http://127.0.0.1:4041/api/tunnels', timeout=10) as response:
            tunnels = json.load(response)['tunnels']
        urls = [t['public_url'] for t in tunnels if t['public_url'].startswith('https://')]
        if len(urls) != 1:
            raise ValueError('Expected one HTTPS tunnel')
        base = urls[0]
    except Exception as exc:
        raise SystemExit('Start the ngrok deployment or pass --base-url.') from exc
u = urlsplit(base)
if u.scheme != 'https' or not u.netloc or u.username or u.password or u.query or u.fragment or u.path not in ('', '/'):
    raise SystemExit('Use an HTTPS origin without credentials, path, query or fragment.')
url = base.rstrip('/') + '/lab/tree/GSB_quality_analysis.ipynb'
if not args.legacy_password:
    token = (root / '.secrets/jupyter-token').read_text(encoding='utf-8').strip()
    if len(token) < 32:
        raise SystemExit('Run prepare_shared_runtime.py to prepare the link token.')
    url += '?' + urlencode({'token': token})
path = root / 'private/notebook_link.txt'
path.parent.mkdir(exist_ok=True)
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as f:
    f.write(url + '\n')
path.chmod(0o600)
print('Company access link saved to:', path)
