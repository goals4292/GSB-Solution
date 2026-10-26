# GitHub 등록

코드 저장소: https://github.com/goals4292/GSB-Solution

코드·문서·출력 제거 노트북을 main 브랜치에 업로드했습니다. 원본 엑셀, 실행 결과와 접속 정보는 제외합니다.

## 코드만 내보내기

```bash
python scripts/make_public_bundle.py
```

`private/GSB-Solution-code-only.zip`을 새 폴더에 풉니다. 이 ZIP에는 허용한 코드·안내·출력 제거 노트북만 포함되며 회사 원본·분석 결과·비밀번호·실제 접속 주소를 제외합니다. 원본 데이터 없이 전체 분석을 실행할 수는 없습니다.

## 저장소 업로드

GitHub에서 빈 저장소를 만든 뒤 코드 전용 폴더에서 실행합니다. `YOUR_ACCOUNT`는 실제 GitHub 계정으로 바꿉니다. 처음에는 Private 저장소로 만들고 공개 여부는 자료 제공 범위에 맞춰 결정합니다.

```bash
git init
git branch -M main
git add .
git diff --cached --stat
git commit -m "Add GSB analysis notebook and guides"
git remote add origin https://github.com/YOUR_ACCOUNT/GSB-Solution-Data-Analysis.git
git push -u origin main
```

노트북 실행 후 저장하면 출력에 회사 데이터가 들어갈 수 있습니다. 업데이트도 `make_public_bundle.py`로 내보낸 코드 전용 사본에서 진행합니다. `.gitignore`는 이미 추적 중인 파일이나 노트북 내부 출력까지 삭제하지 않습니다.

GitHub README에는 실제 비밀번호나 토큰이 포함된 URL을 넣지 않습니다. 노트북 접속 주소와 비밀번호는 담당자에게 별도로 전달합니다.
