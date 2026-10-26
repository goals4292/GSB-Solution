# 비밀번호 입력 없는 회사용 공유 링크

회사 담당자는 Windows의 Edge/Chrome에서 공유 링크를 열고, ngrok 안내가 나오면
Visit Site를 누른 뒤 Run → Run All Cells를 실행합니다. 설치와 비밀번호 입력은 없습니다.
링크의 `?token=...`이 접속 권한입니다. 링크를 받은 사람은 같은 작업공간의 코드를
실행하고 회사 자료를 열람·수정할 수 있습니다. 한 번에 한 담당자가 사용합니다.
접속 링크는 공개 GitHub에 게시하지 않습니다.

## 운영자 준비와 실행

Docker Engine과 Compose 플러그인가 설치되고 현재 계정에서 `docker info`가 성공해야 합니다.
ngrok 계정의 authtoken과 `data/raw/gsb_input.xlsx`도 필요합니다.
공개 코드 배포본은 Python 3.12 가상환경을 만들고 requirements-tested.txt로 설치합니다.

프로젝트 루트에서:

```bash
.venv/bin/python scripts/prepare_shared_runtime.py
.venv/bin/python scripts/setup_ngrok.py
docker compose --env-file .secrets/deploy.env -f deploy/compose.shared.yml up -d --build
.venv/bin/python scripts/make_notebook_link.py
```

ngrok 토큰은 setup_ngrok.py의 숨김 입력창에 입력합니다. 채팅이나 GitHub에 올리지 않습니다.
마지막 명령은 로컬 ngrok API에서 주소를 읽고 private/notebook_link.txt에 전체 링크를
저장합니다. ngrok 시작 직후에는 잠시 기다린 뒤 다시 실행하세요.
자동 조회가 안 되면 `--base-url https://실제로-발급된-도메인`을 지정합니다.
파일의 첫 줄 전체를 회사 담당자에게 전달합니다.

## 작업공간과 운영

Jupyter 컨테이너에는 private/shared-runtime만 연결합니다. 연구실 홈 디렉터리,
GitHub 인증정보와 ngrok 계정 토큰은 연결하지 않습니다. ngrok는 별도 컨테이너에서
실행합니다. Jupyter 네트워크는 내부 통신용이므로 추가 패키지를 인터넷에서 설치할 수 없습니다.
터미널 메뉴는 숨기지만 노트북의 Python 실행은 가능합니다.

결과는 private/shared-runtime/outputs에 남습니다. prepare_shared_runtime.py는
기존 공유 파일을 덮어쓰지 않습니다. 최신 데이터는 공유 화면에서 업로드하거나 운영자가
별도 작업공간의 파일을 갱신합니다.

중지:

```bash
docker compose --env-file .secrets/deploy.env -f deploy/compose.shared.yml down
```

링크를 폐기하려면 중지 후 .secrets/jupyter-token을 삭제하고 준비·시작·링크 생성 명령을
다시 실행합니다. 서버와 Docker/ngrok가 계속 실행 중이어야 외부 접속이 유지됩니다.

## GitHub 등록

```bash
.venv/bin/python scripts/make_public_bundle.py
```

private/GSB-Solution-code-only.zip에는 코드·문서와 출력 제거 노트북만 들어갑니다.
이 사본을 비공개 GitHub 저장소에 올립니다. 실행용 원본 폴더를 그대로 git add 하지 않습니다.
GitHub는 코드 보관용이고 실행은 ngrok로 연결된 서버에서 이루어집니다.

## 검증 범위

실제 배포 후 외부 Windows 브라우저에서 링크 클릭, 노트북 열기, Run All Cells,
그래프 표시와 CSV 다운로드를 확인합니다. 로컬 로그인·커널 검증은 Docker 이미지 빌드나
ngrok 외부 연결 시험을 대신하지 않습니다.

참고: [Jupyter 링크 인증](https://jupyter-server.readthedocs.io/en/latest/operators/security.html),
[ngrok Docker](https://ngrok.com/download/docker).
