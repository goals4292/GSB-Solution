# 관리자 권한 없이 ngrok로 공유하기

Linux의 비특권 사용자 네임스페이스와 bubblewrap을 이용합니다. 이 기능이 서버에서
허용돼 있어야 합니다. 허용되지 않으면 격리를 생략하지 않고 중단합니다.
Docker나 sudo는 사용하지 않습니다.

## 회사 담당자

운영자가 보낸 **전체 링크**를 Windows의 Edge/Chrome에서 엽니다. ngrok 안내가 나오면
Visit Site를 누릅니다. 노트북에서 Run → Run All Cells를 선택하면 됩니다.
설치·회원가입·비밀번호 입력은 없습니다. 링크를 가진 사람은 같은 작업공간에서
코드를 실행하고 자료를 수정할 수 있으므로 한 번에 한 담당자가 사용합니다.

## 운영자 준비

1. Python 3.12 가상환경과 requirements-tested.txt의 패키지를 준비합니다.
2. bubblewrap과 ngrok 실행 파일을 현재 사용자 권한으로 설치합니다.
3. 회사 자료를 data/raw/gsb_input.xlsx 또는 표준 CSV인 data/raw/gsb_input.csv에 둡니다.

Ubuntu에서 bubblewrap 패키지를 사용자 디렉터리에 풀 수 있습니다.

```bash
mkdir -p "$HOME/.local/share/gsb-tools"
cd "$HOME/.local/share/gsb-tools"
apt-get download bubblewrap
dpkg-deb -x bubblewrap_*.deb bubblewrap
```

ngrok 공식 Linux 배포 파일의 실행 파일은 PATH 또는
~/.local/share/gsb-tools/bin/ngrok에 둡니다. 시스템 bubblewrap이 있으면 이를 사용하고,
없으면 ~/.local/share/gsb-tools/bubblewrap/usr/bin/bwrap을 사용합니다.

프로젝트 루트에서:

```bash
.venv/bin/python scripts/prepare_shared_runtime.py
.venv/bin/python scripts/setup_ngrok.py
.venv/bin/python scripts/shared_no_sudo.py start
.venv/bin/python scripts/shared_no_sudo.py status
```

status의 state가 ready가 되면 private/notebook_link.txt에 생성된 첫 줄 전체를 전달합니다.
토큰은 숨김 입력으로 저장하며 Git에 포함하지 않습니다. start는 백그라운드 실행입니다.
정지는 `.venv/bin/python scripts/shared_no_sudo.py stop`입니다.
먼저 외부 연결 없이 시험하려면 start에 --local-only를 붙입니다. 공개 시작 전 stop합니다.

## 실제 격리 범위

- 회사 작업공간 private/shared-runtime만 읽고 쓸 수 있습니다.
- Python 실행환경과 필요한 시스템 라이브러리는 읽기 전용입니다.
- 호스트의 연구실 NAS·SSH·GitHub 인증 파일과 ngrok 계정 토큰은 연결하지 않습니다.
- 프로세스와 네트워크 네임스페이스를 분리합니다. 커널의 외부 네트워크 접근은 없습니다.
- 호스트 중계 프로세스가 Unix 소켓으로 HTTP/WebSocket을 전달합니다.
- ngrok는 격리 환경 밖에서 HTTPS 연결을 유지합니다.

원본 프로젝트와 공유 사본은 별개입니다. 추가 엑셀은 공유 화면의 data/raw 폴더에
gsb_input.xlsx 이름으로 업로드합니다. 엑셀이 없으면 gsb_input.csv를 사용합니다.
prepare_shared_runtime.py는 이미 있는 공유 파일을 덮어쓰지 않습니다.

## 사용자 서비스

deploy/gsb-shared-no-sudo.service.example의 절대 경로를 바꿔
~/.config/systemd/user/gsb-shared-no-sudo.service에 저장합니다.
직접 실행한 프로세스가 있다면 stop한 후 다음을 실행합니다.

```bash
systemctl --user daemon-reload
systemctl --user enable --now gsb-shared-no-sudo.service
systemctl --user status gsb-shared-no-sudo.service
```

서비스는 오류 종료 시 재시작하며 메모리·프로세스·CPU 한도를 적용합니다.
사용자 서비스가 실행되는 환경에서만 유지됩니다. loginctl show-user로 확인한 Linger가
no이면 마지막 로그인 세션 종료나 서버 재부팅 시 접속이 끊길 수 있습니다.
로그인 후 서비스가 다시 시작됩니다. 로그아웃 후에도 상시 유지하려면 별도 운영 지원이 필요합니다.

로그는 ~/.local/state/gsb-solution 아래의 프로젝트별 디렉터리에 저장됩니다.
공유 링크·로그·원본 데이터는 공개 저장소에 올리지 않습니다.

## 검증

```bash
.venv/bin/python scripts/verify_shared_server.py
```

외부 HTTPS 로그인, 호스트 파일/네트워크/프로세스 격리, 실제 WebSocket 커널 실행,
전체 셀 결과 및 그래프 저장을 검증합니다. --local 옵션은 로컬 중계 서버를 시험합니다.
회사 Windows 브라우저에서의 수동 화면 확인은 별도입니다.

공식 참고: [bubblewrap](https://github.com/containers/bubblewrap),
[ngrok Linux 설치](https://ngrok.com/download/linux).
