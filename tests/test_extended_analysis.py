from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.gsb_analysis import load_data, measured_flags, REQUIRED
from src.gsb_extended_analysis import summarize_extended, temporal_regression


class ExtendedAnalysisTests(unittest.TestCase):
    def excel(self, folder, new=True, length=80.1, invalid_header=False):
        path = Path(folder) / 'input.xlsx'
        wb = Workbook(); s = wb.active; s.title = '추가_25년'
        s['B5'] = '11404 10806P'
        headers = (['측정일자', '전조하경', '전장길이', '측정일자', '나사외경', '전장길이'] if new
                   else ['측정일자', '전조하경', '측정일자', '나사외경'])
        for i, h in enumerate(headers, 15):
            s.cell(16, i, h)
        if invalid_header:
            s['R16'] = '알 수 없는 열'
        s['B17'] = '250101-FR04-01-01'; s['E17'] = 'FR-04'; s['I17'] = 'RL-13'
        values = ['2025-01-01', 9.08, length, '2025-01-03', 9.84, 80.0] if new else ['2025-01-01', 9.08, '2025-01-03', 9.84]
        for i, value in enumerate(values, 15):
            s.cell(17, i, value)
        s['D18'] = '생산수량'; s['D19'] = '불량수량'
        s['E18'] = s['I18'] = 100
        s['E19'] = s['I19'] = 0
        wb.save(path); wb.close()
        return path

    def test_new_excel_shifted_columns_and_old_layout(self):
        with tempfile.TemporaryDirectory() as td:
            new = load_data(self.excel(td))
            old = load_data(self.excel(td, new=False))
        pd.testing.assert_frame_equal(new[REQUIRED], old[REQUIRED])
        self.assertEqual(new.thread_date.iloc[0], pd.Timestamp('2025-01-03'))
        self.assertEqual(new.forming_length_mm.iloc[0], 80.1)
        self.assertEqual(new.thread_length_mm.iloc[0], 80.0)
        self.assertTrue(old.forming_length_mm.isna().all())

    def test_unrecognized_layout_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, '열 배치'):
                load_data(self.excel(td, invalid_header=True))

    def test_invalid_length_requires_explicit_coercion_and_keeps_source(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.excel(td, length='79..8')
            with self.assertRaisesRegex(ValueError, '79..8'):
                load_data(path)
            d = load_data(path, length_errors='coerce')
        self.assertTrue(pd.isna(d.forming_length_mm.iloc[0]))
        self.assertEqual(d.forming_length_mm_raw.iloc[0], '79..8')
        self.assertTrue(d.forming_length_mm_invalid.iloc[0])
        self.assertEqual(d.thread_diameter_mm.iloc[0], 9.84)
        t = summarize_extended(d)
        self.assertEqual(t['length_input_issues']['원문'].iloc[0], '79..8')
        self.assertEqual(t['length_input_issues']['원본 셀'].iloc[0], 'Q17')
        total = t['coverage_extended'].iloc[-1]
        self.assertEqual((total['외경 연결'], total['전장길이 연결']), (1, 0))

    def test_length_spec_boundaries_and_missing(self):
        with tempfile.TemporaryDirectory() as td:
            d = load_data(self.excel(td, length=79.30))
        d.loc[0, 'thread_length_mm'] = 80.70
        flags = measured_flags(d)
        self.assertEqual(flags.forming_length_mm_status.iloc[0], '기록값 규격 내')
        self.assertEqual(flags.thread_length_mm_status.iloc[0], '기록값 규격 내')
        d.loc[0, 'thread_length_mm'] = 80.71
        self.assertEqual(measured_flags(d).thread_length_mm_status.iloc[0], '기록값 규격 이탈')

    def model_data(self):
        records = []
        for year in [2024, 2025, 2026]:
            for i in range(5):
                diameter = 9.07 + .01 * (i % 3)
                length = 79.9 + .04 * i + .02 * (year - 2024)
                records.append(dict(part_no='11404 10806P', lot=f'{str(year)[2:]}0101-FR04-01-{i+1:02}',
                                    sheet_year=year, forming_date=f'{year}-01-01', thread_date=f'{year}-01-03',
                                    forming_diameter_mm=diameter, forming_length_mm=length,
                                    thread_diameter_mm=9.8 + .2 * (diameter - 9.07) + .03 * (length - 79.9),
                                    thread_length_mm=length - .05, forming_produced=100, thread_produced=100,
                                    forming_defects=0, thread_defects=i))
        frame = pd.DataFrame(records)
        frame.loc[6, 'forming_length_mm'] = np.nan
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'input.csv'; frame.to_csv(path, index=False)
            return load_data(path)

    def test_future_targets_do_not_change_fitted_parameters_or_baseline(self):
        data = self.model_data()
        first = temporal_regression(data)
        altered = data.copy()
        altered.loc[altered.sheet_year.eq(2025), 'thread_diameter_mm'] += 10
        second = temporal_regression(altered)
        a = first['regression_predictions'].query('`평가 연도` == 2025')
        b = second['regression_predictions'].query('`평가 연도` == 2025')
        np.testing.assert_allclose(a['예측 나사외경(mm)'], b['예측 나사외경(mm)'])
        np.testing.assert_allclose(a['학습 평균 Baseline(mm)'], b['학습 평균 Baseline(mm)'])
        coef_a = first['regression_coefficients'].query('`평가 연도` == 2025')
        coef_b = second['regression_coefficients'].query('`평가 연도` == 2025')
        np.testing.assert_allclose(coef_a['계수'], coef_b['계수'])

    def test_common_cohort_uses_identical_lots_and_recovers_linear_relation(self):
        result = temporal_regression(self.model_data())
        predictions = result['regression_predictions']
        common = predictions.loc[predictions['평가 기준'].eq('동일 LOT 비교')]
        for year, group in common.groupby('평가 연도'):
            lots = [set(g.LOT) for _, g in group.groupby('모델')]
            self.assertEqual(lots[0], lots[1])
        metrics = result['regression_metrics']
        perfect = metrics.loc[metrics['모델'].eq('전조하경+성형전장길이')]
        self.assertLess(perfect['모델 MAE(mm)'].max(), 1e-10)
        self.assertEqual(metrics.loc[metrics['평가 기준'].eq('동일 LOT 비교')].groupby('평가 연도')['학습 LOT'].nunique().max(), 1)

    def test_month_is_lot_date_not_inspection_date_and_missing_is_not_zero(self):
        d = self.model_data()
        d['thread_date'] = pd.Timestamp('2030-12-01')
        d.loc[d.sheet_year.eq(2024), 'thread_defects'] = np.nan
        tables = summarize_extended(d)
        monthly = tables['monthly_thread_defects'].set_index('LOT 생산월')
        self.assertTrue(pd.isna(monthly.loc['2024-01', '전조 불량수량']))
        self.assertNotIn('2030-12', monthly.index)
        self.assertEqual(tables['defect_concentration'].iloc[0]['전조 불량수량'], 4)
        self.assertEqual(tables['defect_concentration'].iloc[0]['비중(%)'], 20)


if __name__ == '__main__':
    unittest.main()
