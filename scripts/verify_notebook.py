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
parser.add_argument('--write-back', action='store_true', help='검증 성공 후 원본 노트북에도 실행 출력을 저장')
parser.add_argument('--input', type=Path, help='검증할 입력 파일 경로 (기본: 신규 엑셀 우선)')
args=parser.parse_args()
sys.path.insert(0,str(root))
from src.gsb_analysis import load_data, summarize, select_input
from src.gsb_extended_analysis import summarize_extended, temporal_regression
path = args.input.resolve() if args.input else select_input(root)
before=hashlib.sha256(path.read_bytes()).hexdigest()
data=load_data(path, length_errors='coerce')
tables=summarize(data)
reference='3f04cc3fe890350393d05390199989bd071c25998bc7d114adec133ba4a8c261'
if before==reference:
    total=tables['coverage'].iloc[-1]
    assert list(total.iloc[1:5]) == [279,236,254,217]
    assert abs(tables['correlation'].iloc[-1]['피어슨 r']-(-0.090688)) < 0.000001
    assert tables['specifications']['규격 이탈 수'].sum()==0
    print('제공 원본의 표본수·연결률·상관계수·규격 이탈 수 검증 통과')
elif before == '87bd292c57c755a355662d93f4321e3fa963dbab98b87499806c8cf1949a46e2':
    import numpy as np
    extended = summarize_extended(data)
    coverage = extended['coverage_extended'].iloc[-1]
    assert coverage['전체 LOT'] == 279
    assert [coverage[c] for c in ['성형 전조하경 기록', '전조 나사외경 기록', '성형 전장길이 기록', '전조 전장길이 기록', '외경 연결', '전장길이 연결', '네 치수 모두 유효']] == [236, 254, 235, 254, 217, 216, 216]
    assert abs(extended['length_correlation'].iloc[-1]['피어슨 r'] - 0.7036343849740285) < 1e-10
    assert tables['specifications']['규격 이탈 수'].sum() == 0
    assert extended['length_input_issues']['원문'].tolist() == ['79..8']
    assert extended['length_input_issues']['원본 셀'].tolist() == ['Q162']
    assert extended['equipment_composition']['LOT 수'].tolist() == [116, 44, 24, 95]
    assert extended['defect_concentration']['전조 불량수량'].tolist() == [2198, 7434, 11287]
    assert data.thread_defects.sum() == 15332
    monthly = extended['monthly_thread_defects'].set_index('LOT 생산월')['전조 불량수량']
    assert monthly.loc[['2025-11', '2026-02', '2026-05', '2026-06']].tolist() == [1769, 3648, 4952, 4963]
    regression = temporal_regression(data)['regression_summary']
    np.testing.assert_allclose(regression.iloc[:, 1:].round(5).to_numpy(),
                               [[0.00887, 0.00935, 0.00930], [0.01542, 0.01564, 0.01270]], atol=1e-10, rtol=0)
    print('추가 엑셀의 네 치수·길이 상관·설비·불량 집중도·회귀 MAE 기준값 검증 통과')
else:
    print('다른 입력 파일입니다. 기존 원본 기준 숫자 대조를 건너뜁니다.')
nb=nbformat.read(root/'GSB_quality_analysis.ipynb',as_version=4)
if args.input:
    changed = False
    for cell in nb.cells:
        if cell.cell_type == 'code' and 'INPUT_FILE = core.select_input(ROOT)' in cell.source:
            cell.source = cell.source.replace('INPUT_FILE = core.select_input(ROOT)', f'INPUT_FILE = Path({str(path)!r})')
            changed = True
    if not changed:
        raise ValueError('노트북 INPUT_FILE 할당을 확인하세요. 입력 파일을 안전하게 바꿀 수 없습니다.')
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
if args.write_back:
    temporary = root / 'private/GSB_quality_analysis.verified.ipynb'
    nbformat.write(nb, temporary)
    os.replace(temporary, root / 'GSB_quality_analysis.ipynb')
    print('GSB_quality_analysis.ipynb에 전체 실행 출력을 저장했습니다.')
print('전체 셀 실행 및 원본 해시 보존 확인 완료')
