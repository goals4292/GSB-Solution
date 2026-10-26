from pathlib import Path
import sys,tempfile,unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.gsb_analysis import load_data,summarize,measured_flags,REQUIRED,pearson
import pandas as pd

class AnalysisTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame([dict(part_no='11404 10806P',lot='260101-A-01-01',sheet_year=2026,
            forming_date='2026-01-01',thread_date='2026-01-02',forming_diameter_mm=9.06,
            thread_diameter_mm=9.97,forming_produced=100,forming_defects=0,thread_produced=100,thread_defects=0)])
    def load(self,df):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'input.csv';df.to_csv(p,index=False);return load_data(p)
    def test_missing_not_zero(self):
        df=self.frame();df['thread_defects']=None
        table=summarize(self.load(df))['defect_counts']
        self.assertTrue(table.query("공정 == '전조'")['기록된 불량수량 합계'].isna().all())
    def test_boundary_is_in_spec(self):
        flags=measured_flags(self.load(self.frame()))
        self.assertEqual(flags.thread_diameter_mm_status.iloc[0],'기록값 규격 내')
    def test_missing_flag(self):
        df=self.frame();df['thread_diameter_mm']=None
        flags=measured_flags(self.load(df))
        self.assertEqual(flags.thread_diameter_mm_status.iloc[0],'결측')
    def test_duplicates_blocked(self):
        with self.assertRaisesRegex(ValueError,'중복'):self.load(pd.concat([self.frame(),self.frame()]))
    def test_bad_numeric_blocked(self):
        df=self.frame();df['thread_diameter_mm']='mistyped'
        with self.assertRaisesRegex(ValueError,'숫자'):self.load(df)
    def test_no_variance_correlation(self):
        df=pd.concat([self.frame()]*3)
        self.assertTrue(np.isnan(pearson(df)))

if __name__=='__main__':unittest.main()
