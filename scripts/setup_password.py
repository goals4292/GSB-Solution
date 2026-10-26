from pathlib import Path
from getpass import getpass
import json
from jupyter_server.auth import passwd
root=Path(__file__).resolve().parents[1]
a=getpass('Jupyter 접속 비밀번호: ')
b=getpass('비밀번호 확인: ')
if len(a)<12 or a!=b:
    raise SystemExit('12자 이상이고 두 입력이 같아야 합니다.')
folder=root/'.secrets';folder.mkdir(exist_ok=True,mode=0o700)
path=folder/'password.json'
path.write_text(json.dumps({'hashed_password':passwd(a)}),encoding='utf-8')
path.chmod(0o600)
print('비밀번호 해시 저장 완료. 서버를 재시작하세요.')
