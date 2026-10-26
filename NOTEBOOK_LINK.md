# 노트북 접속 링크

현재 상태: **관리자 권한 없는 격리 서버와 ngrok HTTPS 접속 운영 중**

회사 담당자는 운영자가 전달한 전체 링크를 열고 Run → Run All Cells를 선택합니다.
ngrok 안내가 나오면 Visit Site를 누릅니다. 별도 설치나 비밀번호 입력은 없습니다.

현재 운영 서버는 접속용 토큰·비밀번호 인증을 사용하지 않습니다.
주소를 아는 사람은 누구나 회사 작업공간에서 코드를 실행할 수 있습니다.
실제 주소는 담당자에게 별도로 전달하며 공개 GitHub에는 게시하지 않습니다.
운영자는 실제 배포 폴더의 private/notebook_link.txt에서 전체 링크를 확인합니다.

운영 안내: [관리자 권한 없는 공유 배포](docs/no-sudo-deploy.md)

사용자 서비스는 서버 로그인 상태에 따라 중지될 수 있습니다. 현재 상태 확인:

```bash
systemctl --user status gsb-shared-no-sudo.service
```
