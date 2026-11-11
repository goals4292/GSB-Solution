# GSB솔루션 공정 품질 데이터 분석

Windows PC의 Edge 또는 Chrome에서 JupyterLab 링크를 열어, 준비된 노트북을 클릭하여 실행합니다. 서버를 이용하는 회사 담당자는 Python이나 Git을 설치하지 않아도 됩니다.

## 바로 시작하기

1. 운영자가 전달한 **노트북 접속 링크**를 엽니다. ngrok 안내 화면이 나오면 `Visit Site`를 누릅니다.
2. 노트북이 바로 열립니다. 접속용 토큰이나 비밀번호 입력은 없습니다.
3. `GSB_quality_analysis.ipynb`에서 **Run → Run All Cells**를 누릅니다.
4. 마지막 셀의 **분석 완료**와 결과 폴더 링크를 확인합니다.

**회사 공유 서버 운영 중입니다.** 비밀번호 입력 없는 전체 링크는 담당자에게 별도로 전달합니다. [접속 링크 안내](NOTEBOOK_LINK.md)

GitHub의 노트북 화면은 코드 열람용입니다. 실행은 별도 JupyterLab 서버에서 합니다.

## 제공 기능

| 기능 | 내용 |
|---|---|
| 데이터 입력 | 제공받은 2024~2026년 추가 데이터 엑셀 또는 표준 CSV |
| 전처리·검증 | 결측 보존, 숫자·날짜 검증, 품번·LOT 중복 확인 |
| LOT 연결 | 외경·전장길이 쌍 및 네 치수 전체의 유효 기록 확보율 |
| 분석 | 네 치수 규격, 연도별 상관·평균, 설비 구성, 월별·상위 LOT 불량 집중도, PPM |
| 회귀 평가 | 이전 시트 연도 학습 → 다음 연도 나사외경 예측; 모델별 유효 LOT 및 동일 LOT 비교 |
| 시각화 | 치수 산점도·히스토그램·측정일 기준 추세 |
| 기록값 점검 | 측정값의 규격 내·외 및 결측 표시 |
| 결과 저장 | 실행별 CSV·PNG·HTML 보고서 및 입력 파일 SHA-256 |

기본 입력은 `data/raw/gsb_input_2.xlsx`이며, 성형·전조 전장길이를 포함한 추가 분석을 수행합니다. `79..8`로 기록된 성형 전장길이 한 건은 임의 보정 없이 원문과 오류 위치를 표시하고 해당 길이 분석에서 제외합니다.

현재 자료는 나사외경 규격 이탈 사례가 없어 불량 예측모델과 위험 임계치를 검증할 수 없습니다. 기록값의 규격 판정은 미래 불량 사전알람과 다릅니다. LOT 평균값인지 대표 샘플값인지도 확인이 필요합니다.

## 문서

- [전장길이 추가 분석 안내](docs/length-analysis.md)
- [회사 담당자 사용 안내](docs/user-guide.md)
- [설치·활용 가이드](docs/install-guide.md)
- [Linux 서버 및 ngrok 운영](docs/server-setup.md)
- [Windows에서 직접 실행](docs/windows-setup.md)
- [입력 자료 및 추가 데이터](docs/data-guide.md)
- [분석 노트북](GSB_quality_analysis.ipynb)

## 파일 구성

```text
GSB_quality_analysis.ipynb   셀 순서대로 실행하는 분석 노트북
src/gsb_analysis.py          구형·신형 입력 검증, 기본 분석·저장
src/gsb_extended_analysis.py 전장길이·설비·불량 집중도·시간순 회귀
data/raw/                   회사 원본 자료 (신규 기본: gsb_input_2.xlsx, Git 제외)
data/templates/             표준 CSV 빈 양식
outputs/                    실행별 결과 (Git 제외)
private/                    검증 기록·공유 주소 (Git 제외)
docs/                       사용자·설치·운영 안내
scripts/                    서버 실행·비밀번호·링크 생성 도구
deploy/                     서버 설정·서비스 예제
```

Python 3.11 이상을 대상으로 준비했으며 코드 검증 환경은 Python 3.12입니다. GPU는 필요하지 않습니다. 실제 설치 시 `requirements.txt`를 사용합니다. 검증에 사용한 주요 패키지 버전은 `requirements-tested.txt`에 기록했습니다. 운영환경의 설치 버전은 `pip freeze`로 별도 보관합니다.

원본 엑셀과 분석 결과는 Git에 포함하지 않습니다. 전달용 ZIP에는 회사 자료가 들어 있으므로 담당자 간에만 공유하고, 공개 GitHub에는 `scripts/make_public_bundle.py`로 만든 코드 배포본을 사용합니다.
