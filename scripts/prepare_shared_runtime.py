"""Prepare a separate writable company demo, without changing source notebooks."""
from pathlib import Path
import json
import os
import secrets
import shutil

root = Path(__file__).resolve().parents[1]
runtime = root / 'private/shared-runtime'
runtime.mkdir(parents=True, exist_ok=True)
for folder in ('src', 'data/raw', 'data/templates', 'docs'):
    for source in (root / folder).rglob('*'):
        if not source.is_file() or '__pycache__' in source.parts or source.suffix == '.pyc':
            continue
        target = runtime / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Preserve uploaded data and edits on repeat runs.
        if not target.exists():
            shutil.copy2(source, target)
target = runtime / 'GSB_quality_analysis.ipynb'
if not target.exists():
    nb = json.loads((root / target.name).read_text(encoding='utf-8'))
    nb['metadata']['kernelspec'] = {'display_name': 'Python 3 (ipykernel)',
                                  'language': 'python', 'name': 'python3'}
    for cell in nb['cells']:
        if cell['cell_type'] == 'code':
            cell['outputs'] = []
            cell['execution_count'] = None
            cell.get('metadata', {}).pop('execution', None)
    target.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding='utf-8')
(runtime / 'outputs').mkdir(exist_ok=True)
secret_dir = root / '.secrets'
secret_dir.mkdir(exist_ok=True, mode=0o700)
secret_dir.chmod(0o700)
token_file = secret_dir / 'jupyter-token'
if not token_file.exists():
    fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(secrets.token_urlsafe(32) + '\n')
env_file = secret_dir / 'deploy.env'
env_file.write_text(f'GSB_UID={os.getuid()}\nGSB_GID={os.getgid()}\n', encoding='utf-8')
env_file.chmod(0o600)
print('Shared workspace:', runtime)
print('Link token prepared (not printed). Existing shared files preserved.')
