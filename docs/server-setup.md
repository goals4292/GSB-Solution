> 현재 서버는 [관리자 권한 없는 배포](no-sudo-deploy.md)를 사용합니다.

> 비밀번호 입력 없는 현재 회사 공유 구성은 [공유 링크 배포](shared-link-deploy.md)를 사용합니다. 아래 내용은 기존 비밀번호 방식입니다.

# Linux 서버 설치와 운영

학교·연구실 서버에서 전용 일반 사용자 계정으로 실행합니다. Jupyter는 로그인 사용자가 Python 코드를 실행하는 서비스이므로 연구실 공용 관리자 계정으로 운영하지 않습니다. 이 구성은 한 담당자의 순차 실행용입니다. 사용자별 격리가 필요하면 JupyterHub를 사용합니다.

## 1. 프로젝트와 환경 준비

전달용 ZIP을 `~/GSB-Solution-Data-Analysis`에 풉니다. 공개 코드 ZIP을 사용했다면 원본 엑셀은 별도로 `data/raw/gsb_input.xlsx`에 배치합니다.

```bash
cd ~/GSB-Solution-Data-Analysis
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/verify_notebook.py
python -m pip freeze > private/requirements-installed.txt
```

`python3.11` 또는 venv가 없으면 서버 관리자에게 설치를 요청합니다. 검증은 원본 해시 보존·기준 표본수·피어슨 계수·전체 셀 실행을 확인합니다. 새 데이터로 바꾼 경우 기준 숫자는 달라질 수 있으므로 아래 데이터 가이드를 확인합니다.

## 2. 비밀번호 설정 및 서버 실행

```bash
python scripts/setup_password.py
python scripts/start_server.py
```

비밀번호를 두 번 입력합니다. 입력 내용은 화면에 표시하지 않으며 해시를 `.secrets/password.json`에 저장합니다. 기본 서버는 `127.0.0.1:8888`에서 실행되고 비밀번호 인증을 유지합니다. `.secrets`는 Git에 올리지 않습니다.

## 3. ngrok 연결

운영자의 계정으로 [ngrok 공식 설치 안내](https://ngrok.com/download)를 따라 설치한 뒤, 별도 터미널에서 다음을 실행합니다. 회사 자료를 외부 터널로 제공할 수 있는지는 해당 서버의 운영 규정에 맞춰 진행합니다.

```bash
ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
ngrok http 8888
```

토큰은 운영자 계정에서 발급받아 로컬 터미널에서만 입력하고 Git이나 문서에 적지 않습니다. 출력된 `Forwarding https://...` 주소를 다음 명령에 넣습니다.

```bash
cd ~/GSB-Solution-Data-Analysis
source .venv/bin/activate
python scripts/make_notebook_link.py --legacy-password --base-url https://YOUR-ACTUAL-DOMAIN.ngrok-free.dev
```

`private/notebook_link.txt`의 링크와 비밀번호를 회사 담당자에게 별도로 전달합니다. ngrok 도메인은 계정과 설정에 따라 다르며, 위 문자열은 자리표시자입니다. HTTPS는 ngrok에서 제공하고 서버의 8888 포트는 외부 방화벽에 직접 개방하지 않습니다. WebSocket·인증·XSRF 보호는 기본 설정을 유지합니다.

## 4. 서버를 계속 켜 두기

테스트 시 터미널 2개를 유지하면 됩니다. 상시 운영은 `deploy/gsb-jupyter.service.example`을 자신의 사용자 systemd 서비스로 복사하고 절대 경로를 수정합니다.

```bash
mkdir -p ~/.config/systemd/user
cp deploy/gsb-jupyter.service.example ~/.config/systemd/user/gsb-jupyter.service
# 편집기로 WorkingDirectory와 ExecStart의 경로를 수정
systemctl --user daemon-reload
systemctl --user enable --now gsb-jupyter
systemctl --user status gsb-jupyter
```

로그아웃 후 계속 운영하려면 관리자가 해당 사용자에 대해 linger를 허용해야 할 수 있습니다. ngrok도 별도 장기 실행 서비스 또는 서버의 기존 운영 방식으로 유지해야 합니다. Jupyter만 살아 있고 ngrok가 종료되면 외부 접속은 끊깁니다. 기관의 HTTPS 리버스 프록시가 이미 있다면 운영자에게 WebSocket 지원과 인증 경로 설정을 요청하고 그 주소로 링크를 만듭니다.

## 5. 실제 인계 전 확인

외부 Windows 브라우저에서 비밀번호 로그인, 노트북 열기, 전체 실행, 결과 CSV 다운로드를 확인합니다. 서버 또는 ngrok 재시작 후 같은 링크가 유효한지도 확인합니다. 현재 배포본은 이 외부 접속 시험을 수행한 상태는 아닙니다.

참고: [Jupyter 보안](https://jupyter-server.readthedocs.io/en/latest/operators/security.html), [Jupyter 서버 운영](https://jupyter-server.readthedocs.io/en/latest/operators/public-server.html), [ngrok CLI](https://ngrok.com/docs/gateway/agent/cli).
