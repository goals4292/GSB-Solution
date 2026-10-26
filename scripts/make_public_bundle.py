from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json
import os
import tempfile
root=Path(__file__).resolve().parents[1]
top=['README.md','NOTEBOOK_LINK.md','requirements.txt','requirements-tested.txt','.gitignore','.dockerignore','start_windows.bat']
paths=[root/f for f in top]
for folder in ['src','docs','scripts','deploy','tests','data/templates']:
    paths += [p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
missing = [str(p.relative_to(root)) for p in paths if not p.is_file()]
if missing:
    raise SystemExit(f'Missing required files: {missing}')
nb=json.loads((root/'GSB_quality_analysis.ipynb').read_text(encoding='utf-8'))
nb['metadata']['kernelspec'] = {'display_name': 'Python 3 (ipykernel)', 'language': 'python', 'name': 'python3'}
for cell in nb['cells']:
    if cell['cell_type']=='code':
        cell['outputs']=[];cell['execution_count']=None
        cell.get('metadata', {}).pop('execution', None)
out=root/'private/GSB-Solution-code-only.zip';out.parent.mkdir(exist_ok=True)
fd, name = tempfile.mkstemp(dir=out.parent, suffix='.zip')
os.close(fd)
temp = Path(name)
try:
    with ZipFile(temp,'w',ZIP_DEFLATED) as z:
        for p in paths:z.write(p,p.relative_to(root))
        z.writestr('GSB_quality_analysis.ipynb',json.dumps(nb,ensure_ascii=False,indent=1))
        for folder in ['data/raw','outputs','private']:z.writestr(folder+'/.gitkeep','')
    os.replace(temp, out)
finally:
    temp.unlink(missing_ok=True)
print(out)
