"""GSB LOT 자료 로딩 및 탐색 분석. 원본 파일은 읽기 전용으로 사용한다."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import re
import platform
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from openpyxl import load_workbook

SPECS = {'forming_diameter_mm': (9.06, 9.10), 'thread_diameter_mm': (9.76, 9.97),
         'forming_length_mm': (79.30, 80.70), 'thread_length_mm': (79.30, 80.70)}
LENGTH_COLUMNS = ['forming_length_mm', 'thread_length_mm']
NUMERIC = ['forming_diameter_mm', 'thread_diameter_mm', 'forming_produced',
           'forming_defects', 'thread_produced', 'thread_defects']
DATES = ['forming_date', 'thread_date']
REQUIRED = ['part_no', 'lot', 'sheet_year'] + DATES + NUMERIC


def select_input(root):
    """Prefer the new workbook; retain support for the original workbook and CSV."""
    folder = Path(root) / 'data/raw'
    for name in ('gsb_input_2.xlsx', 'gsb_input.xlsx', 'gsb_input.csv'):
        if (folder / name).is_file():
            return folder / name
    raise FileNotFoundError('data/raw에 gsb_input_2.xlsx, gsb_input.xlsx 또는 gsb_input.csv가 필요합니다.')


def load_data(path, *, length_errors='raise'):
    """Read old/new Excel layouts; explicit 'coerce' flags invalid length text as missing."""
    if length_errors not in ('raise', 'coerce'):
        raise ValueError('length_errors는 raise 또는 coerce여야 합니다.')
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'입력 파일이 없습니다: {path}. data/raw에 gsb_input.xlsx를 업로드하세요.')
    if path.suffix.lower() == '.csv':
        data = pd.read_csv(path, dtype=str, encoding='utf-8-sig')
    elif path.suffix.lower() == '.xlsx':
        records = []
        wb = load_workbook(path, data_only=True, read_only=True)
        try:
            for sheet in wb:
                if not re.search(r'(24|25|26)년', sheet.title):
                    continue
                rows = list(sheet.values)
                if len(rows) < 16:
                    raise ValueError(f'{sheet.title}: 검사 헤더가 없습니다.')
                labels = [re.sub(r'\s+', '', str(v or '')) for v in rows[15]]
                old = ['측정일자', '전조하경', '측정일자', '나사외경']
                new = ['측정일자', '전조하경', '전장길이', '측정일자', '나사외경', '전장길이']
                if labels[14:20] == new:
                    thread_date_col, thread_diameter_col = 17, 18
                    length_cols = (16, 19)
                elif labels[14:18] == old:
                    thread_date_col, thread_diameter_col = 16, 17
                    length_cols = (None, None)
                else:
                    raise ValueError(f'{sheet.title}: 지원하지 않는 검사 열 배치입니다. 헤더와 표준 CSV를 확인하세요.')
                year = 2000 + int(re.search(r'(\d{2})년', sheet.title).group(1))
                for i, row in enumerate(rows):
                    lot = str(row[1] or '').strip()
                    if not re.fullmatch(r'\d{6}-[A-Za-z0-9]+-[A-Za-z0-9]+-[A-Za-z0-9]+', lot):
                        continue
                    if i + 2 >= len(rows) or rows[i+1][3] != '생산수량' or rows[i+2][3] != '불량수량':
                        raise ValueError(f'{sheet.title} {i+1}행: LOT 블록 구조가 변경되었습니다.')
                    records.append(dict(part_no=str(rows[4][1]).strip(), lot=lot, sheet_year=year,
                        forming_date=row[14], forming_diameter_mm=row[15],
                        thread_date=row[thread_date_col], thread_diameter_mm=row[thread_diameter_col],
                        forming_length_mm=row[length_cols[0]] if length_cols[0] is not None else None,
                        thread_length_mm=row[length_cols[1]] if length_cols[1] is not None else None,
                        forming_equipment=row[4], thread_equipment=row[8],
                        forming_produced=rows[i+1][4], forming_defects=rows[i+2][4],
                        thread_produced=rows[i+1][8], thread_defects=rows[i+2][8],
                        source_sheet=sheet.title, source_row=i+1))
        finally:
            wb.close()
        data = pd.DataFrame(records)
    else:
        raise ValueError('지원 형식은 .xlsx 또는 .csv입니다.')
    missing = set(REQUIRED) - set(data.columns)
    if missing:
        raise ValueError(f'필수 컬럼이 없습니다: {sorted(missing)}')
    if data.empty:
        raise ValueError('읽을 수 있는 LOT 자료가 없습니다.')
    data = data.copy()
    for col in LENGTH_COLUMNS + ['forming_equipment', 'thread_equipment']:
        if col not in data:
            data[col] = pd.NA
    for col in ['forming_equipment', 'thread_equipment']:
        data[col] = data[col].astype('string').str.strip().replace({'-': pd.NA, '': pd.NA})
    for col in ['part_no', 'lot']:
        data[col] = data[col].astype('string').str.strip()
        if data[col].isna().any() or data[col].eq('').any():
            raise ValueError(f'{col}: 빈 식별자가 있습니다.')
    for col in NUMERIC + LENGTH_COLUMNS + ['sheet_year']:
        if col in LENGTH_COLUMNS:
            data[col + '_raw'] = data[col].astype('string')
        clean = data[col].astype('string').str.strip().replace({'-': pd.NA, '': pd.NA, 'None': pd.NA})
        clean = clean.str.replace(',', '', regex=False)
        parsed = pd.to_numeric(clean, errors='coerce')
        invalid = clean.notna() & (parsed.isna() | ~np.isfinite(parsed))
        if col in LENGTH_COLUMNS:
            data[col + '_invalid'] = invalid.fillna(False).astype(bool)
        if invalid.any() and not (col in LENGTH_COLUMNS and length_errors == 'coerce'):
            raise ValueError(f'{col}: 숫자로 해석할 수 없는 값 {clean[invalid].head().tolist()}')
        parsed = parsed.mask(invalid)
        if parsed.dropna().lt(0).any():
            raise ValueError(f'{col}: 음수가 있습니다. 원자료를 확인하세요.')
        data[col] = parsed.astype(float)
    if data.sheet_year.isna().any() or (data.sheet_year % 1 != 0).any():
        raise ValueError('sheet_year는 정수 연도여야 합니다.')
    data['sheet_year'] = data.sheet_year.astype(int)
    for col in DATES:
        clean = data[col].astype('string').str.strip().replace({'-': pd.NA, '': pd.NA, 'None': pd.NA})
        parsed = pd.to_datetime(clean, errors='coerce', format='mixed')
        if (clean.notna() & parsed.isna()).any():
            raise ValueError(f'{col}: 날짜 형식을 확인하세요. 권장 YYYY-MM-DD')
        data[col] = parsed
    if data.duplicated(['part_no','lot']).any():
        raise ValueError('품번·LOT 중복이 있습니다. 기존 행을 수정하거나 중복 원인을 확인하세요.')
    for stage in ['forming','thread']:
        if (data[f'{stage}_defects'] > data[f'{stage}_produced']).any():
            raise ValueError(f'{stage}: 불량수량이 생산수량보다 큽니다. 집계 기준을 확인하세요.')
        for kind in ['produced','defects']:
            v = data[f'{stage}_{kind}'].dropna()
            if (v % 1 != 0).any():
                raise ValueError('수량은 정수여야 합니다.')
    data['batch'] = data['lot'].str.rsplit('-', n=1).str[0]
    date_prefix = data['lot'].str.extract(r'^(\d{6})-', expand=False)
    data['lot_production_date'] = pd.to_datetime('20' + date_prefix, format='%Y%m%d', errors='coerce')
    data['lot_production_month'] = data['lot_production_date'].dt.strftime('%Y-%m')
    return data


def pearson(frame, columns=('forming_diameter_mm', 'thread_diameter_mm')):
    pair = frame[list(columns)].dropna()
    if len(pair) < 3 or pair.nunique().min() < 2:
        return np.nan
    return pair.corr().iloc[0,1]


def summarize(data):
    rows, corr = [], []
    groups = [(str(y), g) for y,g in data.groupby('sheet_year')] + [('전체',data)]
    for year,g in groups:
        n = g[['forming_diameter_mm','thread_diameter_mm']].notna().all(axis=1).sum()
        rows.append([year,len(g),g.forming_diameter_mm.count(),g.thread_diameter_mm.count(),n,100*n/len(g)])
        corr.append([year,n,pearson(g)])
    coverage = pd.DataFrame(rows,columns=['구분','전체 LOT','전조하경 기록','나사외경 기록','두 치수 연결','확보율(%)'])
    correlation = pd.DataFrame(corr,columns=['구분','연결 LOT','피어슨 r'])
    specs = []
    for col,(low,high) in SPECS.items():
        v=data[col].dropna()
        specs.append([col,low,high,len(v),v.min(),v.max(),int(((v<low)|(v>high)).sum())])
    spec_table=pd.DataFrame(specs,columns=['항목','하한(mm)','상한(mm)','측정값 수','최솟값','최댓값','규격 이탈 수'])
    counts=[]
    for year,g in groups:
        for stage,label in [('forming','성형'),('thread','전조')]:
            produced=g[f'{stage}_produced']; bad=g[f'{stage}_defects']
            eligible=produced.gt(0)&bad.notna()
            denom=produced[eligible].sum()
            counts.append([year,label,bad.sum(min_count=1),int(bad.isna().sum()),int(eligible.sum()),
                           bad[eligible].sum()/denom*1e6 if denom else np.nan])
    counts=pd.DataFrame(counts,columns=['구분','공정','기록된 불량수량 합계','불량수량 결측 LOT','PPM 계산 LOT','계산 PPM'])
    return {'coverage':coverage,'correlation':correlation,'specifications':spec_table,'defect_counts':counts}


def quality_checks(data):
    checks = []
    for col in NUMERIC + LENGTH_COLUMNS + DATES:
        checks.append([f'{col} 결측',int(data[col].isna().sum())])
    for col in LENGTH_COLUMNS:
        checks.append([f'{col} 숫자 오류(결측 처리)', int(data[col + '_invalid'].sum())])
    checks.append(['LOT 생산일자 해석 불가', int(data.lot_production_date.isna().sum())])
    checks += [['품번·LOT 중복',int(data.duplicated(['part_no','lot']).sum())],
               ['전조일이 성형일보다 빠름',int((data.thread_date < data.forming_date).sum())],
               ['시트 연도와 전조 측정연도 불일치',int((data.thread_date.notna() & data.thread_date.dt.year.ne(data.sheet_year)).sum())],
               ['전조 생산수량 결측이나 나사외경 기록 있음',int((data.thread_produced.isna() & data.thread_diameter_mm.notna()).sum())],
               ['성형보다 전조 생산수량이 많음',int((data.thread_produced > data.forming_produced).sum())]]
    return pd.DataFrame(checks,columns=['점검 항목','LOT 수'])


def plots(data):
    figures={}
    pair=data.dropna(subset=['forming_diameter_mm','thread_diameter_mm'])
    fig,ax=plt.subplots(figsize=(8,4.5))
    # 같은 좌표의 빈도를 면적으로 표시하며 측정값의 위치는 바꾸지 않는다.
    grouped=pair.groupby(['forming_diameter_mm','thread_diameter_mm']).size().reset_index(name='count')
    ax.scatter(grouped.forming_diameter_mm,grouped.thread_diameter_mm,s=grouped['count']*18,alpha=.55,color='#087f8c')
    ax.set(xlabel='Forming diameter (mm)',ylabel='Thread outside diameter (mm)',title=f'LOT measurements: n={len(pair)}, Pearson r={pearson(pair):.3f}')
    ax.grid(alpha=.2);fig.tight_layout();figures['scatter']=fig
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,col in zip(axes, ['forming_diameter_mm', 'thread_diameter_mm']):
        low,high=SPECS[col];v=data[col].dropna()
        start = min(low, v.min()) if len(v) else low
        end = max(high, v.max()) if len(v) else high
        ax.hist(v,bins=np.arange(start-.005,end+.015,.01),color='#087f8c',edgecolor='white')
        ax.axvline(low,color='red',ls='--');ax.axvline(high,color='red',ls='--')
        ax.set(xlabel=col.replace('_',' '),ylabel='Recorded LOT count')
    fig.tight_layout();figures['histograms']=fig
    fig,ax=plt.subplots(figsize=(10,4))
    ordered=data.dropna(subset=['thread_date','thread_diameter_mm']).sort_values('thread_date')
    ax.scatter(ordered.thread_date,ordered.thread_diameter_mm,s=16,color='#087f8c')
    for limit in SPECS['thread_diameter_mm']:ax.axhline(limit,color='red',ls='--')
    ax.set(xlabel='Thread measurement date',ylabel='Thread outside diameter (mm)',title='Recorded measurements and specification limits')
    fig.autofmt_xdate();fig.tight_layout();figures['trend']=fig
    return figures


def measured_flags(data):
    result=data[['part_no','lot','thread_date']].copy()
    for col,(low,high) in SPECS.items():
        result[col]=data[col]
        result[col+'_status']=np.select([data[col].isna(),data[col].lt(low)|data[col].gt(high)],['결측','기록값 규격 이탈'],default='기록값 규격 내')
    return result


def save_results(data,tables,figures,source,root):
    source=Path(source);root=Path(root)
    # 실행마다 별도 폴더: 이전 결과 보존, 같은 시각의 실행도 충돌하지 않음.
    import uuid
    out=root/'outputs'/(datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    out.mkdir(parents=True)
    data.to_csv(out/'cleaned_lot_data.csv',index=False,encoding='utf-8-sig')
    for name,table in tables.items():table.to_csv(out/f'{name}.csv',index=False,encoding='utf-8-sig')
    for name,fig in figures.items():fig.savefig(out/f'{name}.png',dpi=160,bbox_inches='tight')
    manifest={'input_file':source.name,'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'executed_at':datetime.now().isoformat(),'rows':len(data),'specifications':SPECS,
              'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,
              'limitations':['LOT 평균/대표샘플 여부 미확인','수량 불량과 치수 이탈 불량은 별개','관측 규격 점검은 사전예측이 아님']}
    manifest['invalid_length_values'] = {col: int(data[col + '_invalid'].sum()) for col in LENGTH_COLUMNS}
    manifest['length_error_policy'] = '숫자 오류 원문 보존; coerce가 명시된 경우만 해당 길이를 결측 처리'
    manifest['regression'] = {'algorithm': 'OLS with intercept (numpy.linalg.lstsq)',
                              'split': '이전 시트 연도 전체 학습 → 다음 시트 연도 평가',
                              'baseline': '학습 LOT의 나사외경 평균',
                              'cohorts': ['모델별 유효 LOT', '두 모델 동일 유효 LOT']}
    manifest['analysis_code_sha256'] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in (root/'src').glob('gsb*analysis.py')}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    sections=['<html><meta charset="utf-8"><title>GSB 분석 결과</title><body><h1>GSB솔루션 분석 결과</h1>',
              '<p>기록된 LOT 값 기준의 탐색 분석입니다. 규격 내 기록값은 LOT 전체 무불량을 뜻하지 않습니다.</p>',
              '<p>전장길이의 숫자 오류는 원문을 보존하고 해당 분석에서 제외합니다. 회귀 평가는 나사외경의 연속값 예측이며 불량 확률 예측이 아닙니다. 모델별 평가는 모델별 표본이 다를 수 있으므로 동일 LOT 비교 표도 함께 확인하세요.</p>']
    for name,table in tables.items():sections += [f'<h2>{name}</h2>',table.to_html(index=False,escape=True)]
    for name in figures:sections.append(f'<p><img src="{name}.png" style="max-width:100%"></p>')
    sections.append('<p>추가 확인: LOT 값 대표성, 불량품 실측값, 불량 판정 항목, 연도별 공정 조건.</p></body></html>')
    (out/'report.html').write_text('\n'.join(sections),encoding='utf-8')
    return out
