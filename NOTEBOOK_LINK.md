# 노트북 접속 링크

현재 상태: **외부 서버 미배포, 실제 ngrok 주소 미발급**

[공유 링크 배포 안내](docs/shared-link-deploy.md)에 따라 서버를 시작한 후 실행합니다.

```bash
.venv/bin/python scripts/make_notebook_link.py
```

private/notebook_link.txt의 첫 줄 전체를 담당자에게 전달합니다.
링크를 가진 사람은 비밀번호 입력 없이 노트북을 실행할 수 있습니다.
실제 링크는 코드 저장소에 포함하지 않습니다.
