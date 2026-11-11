# 전장길이 추가 분석 안내

기본 입력: `data/raw/gsb_input_2.xlsx`. 실행: `GSB_quality_analysis.ipynb`에서 Run All Cells.
추가 분석은 `src/gsb_extended_analysis.py`에 있으며 NumPy·pandas·Matplotlib만 사용합니다.

| 노트북 단계 | 계산 및 저장 표 |
|---|---|
| 2~3 | 네 치수 확보율·규격, 오류 원문: coverage_extended, specifications, length_input_issues |
| 4 | 연도별 성형 설비의 LOT 수·구성비: equipment_composition |
| 5 | 전조하경↔나사외경 상관 및 연도별 산점도: correlation |
| 6 | 성형↔전조 전장길이 상관·산점도·분포: length_correlation |
| 7 | 치수별 유효 표본 평균·표준편차·범위 및 외경 평균 변화량: dimension_statistics, diameter_mean_changes |
| 8 | LOT 생산월별 전조 불량수량: monthly_thread_defects |
| 8 | 상위 LOT·상위 1/5/10개 비중과 Pareto: top_defect_lots, defect_concentration |
| 9 | 시간순 회귀 MAE 및 동일 LOT 비교: regression_summary, regression_metrics |
| 10 | 기록값 점검, 해석 한계 및 추가 확인자료 |

## 입력 오류 처리

추가_25년!Q162의 성형 전장길이는 `79..8`입니다. 이를 79.8로 고치지 않습니다.
load_data는 기본적으로 숫자 오류를 거부합니다. 노트북에서는 length_errors='coerce'를
명시하여 해당 길이만 결측 처리하고, 원문 컬럼과 invalid 표시 및 오류 표를 남깁니다.
해당 LOT의 다른 유효 항목까지 지우지는 않습니다. 그 결과 외경 연결은 217 LOT,
길이 연결 및 네 치수 모두 유효한 표본은 216 LOT입니다.

CSV의 길이 컬럼은 forming_length_mm / thread_length_mm, 설비 컬럼은
forming_equipment / thread_equipment입니다. 기존 CSV와 엑셀에는 없어도 되며 결측으로 유지합니다.

## 회귀 평가를 읽는 방법

절편이 있는 OLS로 예측값과 MAE를 계산합니다. 목표는 thread_diameter_mm이고 입력은
forming_diameter_mm 하나 또는 forming_diameter_mm + forming_length_mm 두 개입니다.
전조 후 길이·불량수량은 예측 입력에 넣지 않습니다. 결측을 채우거나 임의 분할하지 않습니다.

- 2025년 평가: 2024년 학습. 1변수 105/56 LOT, 2변수 105/55 LOT(학습/평가).
- 2026년 평가: 2024~2025년 학습. 1변수 161/56 LOT, 2변수 160/56 LOT.
- Baseline: 해당 모델 학습 LOT의 나사외경 평균. 평가연도 평균을 사용하지 않습니다.
- 요약 표의 단일 Baseline 열은 1변수 표본 기준입니다. 상세 표에는 2변수 자체의 Baseline도 있습니다.
- 별도 '동일 LOT 비교'에서는 두 모델 모두 동일한 완전 관측 학습·평가 LOT를 사용합니다.
- MAE 개선량은 Baseline MAE − 모델 MAE이며 양수가 개선입니다.

| 평가연도 | Baseline MAE | 1변수 MAE | 2변수 MAE |
|---|---:|---:|---:|
| 2025 | 0.00887 | 0.00935 | 0.00930 |
| 2026 | 0.01542 | 0.01564 | 0.01270 |

단위는 mm입니다. 상세한 계수와 LOT별 예측·오차도 각각 regression_coefficients.csv,
regression_predictions.csv로 저장합니다. 이는 시트 연도 기준 전진 검증으로, 실제
검사일이 시트 연도와 다른 LOT가 있으므로 실제 검사시간 기준의 완전한 시간 검증은 아닙니다.
연속 치수의 회귀 결과를 불량확률이나 현장 사전알람 성능으로 해석하지 않습니다.

## 해석 주의점

전장길이 전체 r≈0.704와 연도별 r≈0.186/0.796/0.330을 함께 봅니다. 전체 상관에는
연도별 평균 이동과 설비 구성 변화가 포함될 수 있습니다. 동일 제품의 전후 측정인지 확인되지 않았습니다.
월별 불량 집계의 월은 LOT 코드의 생산일자 기준이고 실제 전조 측정월과 다를 수 있습니다.
불량수량은 치수 이탈 건수와 다른 지표입니다. 길이 규격 양 끝값은 규격 내로 처리합니다.

## 검증과 결과 파일

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/verify_notebook.py --write-back
```

검증 스크립트는 입력 SHA-256이 알려진 원본과 일치할 때만 분석 기준 수치를 대조합니다.
--input으로 입력을 지정할 수 있고, --write-back은 성공한 실행 출력을 원본 노트북에 저장합니다.
원본 엑셀을 수정하지 않았는지도 해시로 확인합니다. 이전 노트북·코드·문서 사본은
private/before_length_analysis_날짜시각에 보관했습니다.

실행별 outputs 폴더에는 전체 CSV 표, PNG 그래프, report.html, manifest.json이 생성됩니다.
manifest에는 입력·분석 코드 해시, 길이 숫자 오류 수와 회귀 계산 기준이 기록됩니다.
