"""실행 환경의 Python으로 임시 커널을 만들어 전체 노트북을 실행한다."""
from pathlib import Path
import sys, json, tempfile, hashlib, os, argparse
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--in-process',action='store_true',help='커널 소켓이 제한된 환경에서 셀 코드를 같은 Python 프로세스로 검증')
args=parser.parse_args()
sys.path.insert(0,str(root))
from src.gsb_analysis import load_data, summarize
path=root/'data/raw/gsb_input.xlsx'
if not path.exists() and (root/'data/raw/gsb_input.csv').exists():
    path=root/'data/raw/gsb_input.csv'
before=hashlib.sha256(path.read_bytes()).hexdigest()
data=load_data(path)
tables=summarize(data)
reference='3f04cc3fe890350393d05390199989bd071c25998bc7d114adec133ba4a8c261'
if before==reference:
    total=tables['coverage'].iloc[-1]
    assert list(total.iloc[1:5]) == [279,236,254,217]
    assert abs(tables['correlation'].iloc[-1]['피어슨 r']-(-0.090688)) < 0.000001
    assert tables['specifications']['규격 이탈 수'].sum()==0
    print('제공 원본의 표본수·연결률·상관계수·규격 이탈 수 검증 통과')
else:
    print('다른 입력 파일입니다. 기존 원본 기준 숫자 대조를 건너뜁니다.')
nb=nbformat.read(root/'GSB_quality_analysis.ipynb',as_version=4)
nbformat.validate(nb)
if args.in_process:
    from IPython.core.interactiveshell import InteractiveShell
    from IPython.utils.capture import capture_output
    shell=InteractiveShell.instance()
    os.chdir(root)
    for count,cell in enumerate((c for c in nb.cells if c.cell_type=='code'),start=1):
        with capture_output() as captured:
            result=shell.run_cell(cell.source)
        if result.error_before_exec:raise result.error_before_exec
        if result.error_in_exec:raise result.error_in_exec
        cell.execution_count=count
        cell.outputs=[]
        if captured.stdout:cell.outputs.append(nbformat.v4.new_output('stream',name='stdout',text=captured.stdout))
        if captured.stderr:cell.outputs.append(nbformat.v4.new_output('stream',name='stderr',text=captured.stderr))
        for item in captured.outputs:cell.outputs.append(nbformat.v4.new_output('display_data',data=item.data,metadata=item.metadata))
    print('동일 프로세스에서 셀 코드를 검증했습니다. 별도 Jupyter 커널 통신 검증은 포함하지 않습니다.')
else:
    with tempfile.TemporaryDirectory() as td:
        folder=Path(td)/'gsb-check';folder.mkdir()
        (folder/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],'display_name':'GSB check','language':'python'}))
        km=KernelManager(kernel_name='gsb-check',kernel_spec_manager=KernelSpecManager(kernel_dirs=[td]))
        NotebookClient(nb,km=km,timeout=180,resources={'metadata':{'path':str(root)}}).execute()
assert before==hashlib.sha256(path.read_bytes()).hexdigest(),'원본이 변경되었습니다.'
(root/'private').mkdir(exist_ok=True)
nbformat.write(nb,root/'private/GSB_executed.ipynb')
print('전체 셀 실행 및 원본 해시 보존 확인 완료')
