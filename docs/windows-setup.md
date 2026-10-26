# Windows PC에서 직접 실행

공유 서버 링크를 이용한다면 이 설치는 필요하지 않습니다.

1. Python 3.11을 설치하고 `py -3.11 --version`으로 확인합니다.
2. 전달용 ZIP을 풀고 그 폴더에서 PowerShell을 엽니다.
3. 아래 명령을 순서대로 실행합니다. PowerShell 실행정책을 바꾸지 않도록 가상환경의 Python 경로를 직접 사용합니다.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\setup_password.py
.\.venv\Scripts\python.exe scripts\start_server.py
```

4. 브라우저에서 `http://127.0.0.1:8888/lab/tree/GSB_quality_analysis.ipynb`를 엽니다.
5. 설정한 비밀번호를 입력한 뒤 **Run → Run All Cells**를 클릭합니다.

종료는 PowerShell에서 `Ctrl+C`를 누릅니다. 다음 실행부터는 마지막 서버 실행 명령만 입력하면 됩니다. Windows 실행 스크립트 `start_windows.bat`도 제공하며, 첫 설치와 비밀번호 설정 후 더블클릭할 수 있습니다.

원본은 `data/raw/gsb_input.xlsx`에 둡니다. 회사망에서 패키지 다운로드를 차단하면 서버 링크 방식으로 사용하거나 사내 Python 패키지 설치 경로를 관리자에게 확인합니다.
