"""전장길이 추가 분석 및 재현 가능한 집계/회귀 평가."""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from .gsb_analysis import SPECS, LENGTH_COLUMNS, pearson

LABELS = {
    'forming_diameter_mm': '성형 전조하경', 'thread_diameter_mm': '전조 나사외경',
    'forming_length_mm': '성형 전장길이', 'thread_length_mm': '전조 전장길이',
}
MODEL_FEATURES = {
    '전조하경 1변수': ['forming_diameter_mm'],
    '전조하경+성형전장길이': ['forming_diameter_mm', 'forming_length_mm'],
}


def length_input_issues(data):
    """Keep invalid source text auditable; never guess a corrected measurement."""
    records = []
    for column in LENGTH_COLUMNS:
        for _, row in data.loc[data[column + '_invalid']].iterrows():
            source_row = row.get('source_row', pd.NA)
            cell = (('Q' if column == 'forming_length_mm' else 'T') + str(int(source_row))
                    if pd.notna(source_row) else '')
            records.append({'품번': row.part_no, 'LOT': row.lot, '항목': LABELS[column],
                            '원문': row[column + '_raw'], '원본 시트': row.get('source_sheet', ''),
                            '원본 셀': cell, '처리': '해당 길이만 결측 처리; 다른 유효 분석에는 포함'})
    return pd.DataFrame(records, columns=['품번', 'LOT', '항목', '원문', '원본 시트', '원본 셀', '처리'])


def summarize_extended(data):
    groups = [(str(y), g) for y, g in data.groupby('sheet_year')] + [('전체', data)]
    coverage, correlations, statistics = [], [], []
    for year, group in groups:
        diam_pairs = group[['forming_diameter_mm', 'thread_diameter_mm']].notna().all(axis=1)
        length_pairs = group[LENGTH_COLUMNS].notna().all(axis=1)
        row = {'구분': year, '전체 LOT': len(group)}
        row.update({LABELS[c] + ' 기록': int(group[c].count()) for c in LABELS})
        row.update({'외경 연결': int(diam_pairs.sum()), '외경 확보율(%)': 100 * diam_pairs.mean(),
                    '전장길이 연결': int(length_pairs.sum()), '전장 확보율(%)': 100 * length_pairs.mean(),
                    '네 치수 모두 유효': int((diam_pairs & length_pairs).sum())})
        coverage.append(row)
        correlations.append({'구분': year, '연결 LOT': int(length_pairs.sum()),
                             '피어슨 r': pearson(group, LENGTH_COLUMNS)})
        for column, label in LABELS.items():
            values = group[column].dropna()
            statistics.append({'구분': year, '항목': label, '컬럼': column, '유효 LOT': len(values),
                               '평균(mm)': values.mean(), '표준편차(mm)': values.std(ddof=1),
                               '최솟값(mm)': values.min(), '최댓값(mm)': values.max()})

    equipment = (data.assign(forming_equipment=data.forming_equipment.fillna('미기록'))
                 .groupby(['sheet_year', 'forming_equipment']).size().rename('LOT 수').reset_index())
    equipment['구성비(%)'] = equipment['LOT 수'] / equipment.groupby('sheet_year')['LOT 수'].transform('sum') * 100
    equipment = equipment.rename(columns={'sheet_year': '연도', 'forming_equipment': '성형 설비'})

    monthly_rows = []
    for month, group in data.dropna(subset=['lot_production_month']).groupby('lot_production_month'):
        monthly_rows.append({'LOT 생산월': month, '전체 LOT': len(group),
                             '불량 기록 LOT': int(group.thread_defects.count()),
                             '전조 불량수량': group.thread_defects.sum(min_count=1)})
    monthly = pd.DataFrame(monthly_rows, columns=['LOT 생산월', '전체 LOT', '불량 기록 LOT', '전조 불량수량'])
    top = data.loc[data.thread_defects.notna(),
                   ['lot', 'sheet_year', 'batch', 'forming_equipment', 'thread_equipment',
                    'lot_production_month', 'thread_defects']].copy()
    top = top.sort_values(['thread_defects', 'lot'], ascending=[False, True]).reset_index(drop=True)
    total = data.thread_defects.sum(min_count=1)
    top.insert(0, '순위', np.arange(1, len(top) + 1))
    top['누적 불량수량'] = top.thread_defects.cumsum()
    top['누적 비중(%)'] = top['누적 불량수량'] / total * 100 if pd.notna(total) and total > 0 else np.nan
    concentration = []
    for k in (1, 5, 10):
        amount = top.head(k).thread_defects.sum(min_count=1)
        concentration.append({'구분': f'상위 {k}개 LOT', '집계 LOT': min(k, len(top)),
                              '전조 불량수량': amount, '전체 기록 불량수량': total,
                              '비중(%)': amount / total * 100 if pd.notna(total) and total > 0 else np.nan})
    stats = pd.DataFrame(statistics)
    changes = []
    years = sorted(data.sheet_year.unique())
    if len(years) >= 2:
        for col in ['forming_diameter_mm', 'thread_diameter_mm']:
            first = data.loc[data.sheet_year.eq(years[0]), col].dropna()
            last = data.loc[data.sheet_year.eq(years[-1]), col].dropna()
            changes.append({'항목': LABELS[col], '기준 연도': years[0], '비교 연도': years[-1],
                            '기준 평균(mm)': first.mean(), '비교 평균(mm)': last.mean(),
                            '평균 차이(mm)': last.mean() - first.mean()})
    return {'coverage_extended': pd.DataFrame(coverage), 'length_correlation': pd.DataFrame(correlations),
            'dimension_statistics': stats, 'equipment_composition': equipment,
            'diameter_mean_changes': pd.DataFrame(changes), 'monthly_thread_defects': monthly,
            'top_defect_lots': top, 'defect_concentration': pd.DataFrame(concentration),
            'length_input_issues': length_input_issues(data)}


def temporal_regression(data):
    """Expanding training window by sheet year; only forming measurements are features.

    The primary evaluation uses model-specific complete cases. A second evaluation fits
    both models on identical complete-case train/test cohorts for fair comparison.
    Baseline is always the *training* target mean; no random split or imputation.
    """
    target = 'thread_diameter_mm'
    metrics, predictions, coefficients = [], [], []
    years = sorted(data.sheet_year.unique())
    for cohort in ('모델별 유효 LOT', '동일 LOT 비교'):
        for evaluation_year in years[1:]:
            past = data.loc[data.sheet_year.lt(evaluation_year)]
            future = data.loc[data.sheet_year.eq(evaluation_year)]
            for name, features in MODEL_FEATURES.items():
                required = features + [target] if cohort.startswith('모델별') else list(MODEL_FEATURES.values())[1] + [target]
                train = past.dropna(subset=required)
                test = future.dropna(subset=required)
                row = {'평가 기준': cohort, '평가 연도': int(evaluation_year), '모델': name,
                       '학습 연도': ', '.join(map(str, sorted(train.sheet_year.unique()))),
                       '학습 LOT': len(train), '평가 LOT': len(test), 'Baseline MAE(mm)': np.nan,
                       '모델 MAE(mm)': np.nan, 'MAE 개선량(mm)': np.nan, '상태': '자료 부족'}
                if len(train) < len(features) + 1 or test.empty:
                    metrics.append(row)
                    continue
                x = train[features].to_numpy(dtype=float)
                y = train[target].to_numpy(dtype=float)
                mean_x, mean_y = x.mean(axis=0), float(y.mean())
                beta, _, rank, _ = np.linalg.lstsq(x - mean_x, y - mean_y, rcond=None)
                estimate = mean_y + (test[features].to_numpy(dtype=float) - mean_x) @ beta
                observed = test[target].to_numpy(dtype=float)
                baseline_mae = float(np.abs(observed - mean_y).mean())
                model_mae = float(np.abs(observed - estimate).mean())
                row.update({'Baseline MAE(mm)': baseline_mae, '모델 MAE(mm)': model_mae,
                            'MAE 개선량(mm)': baseline_mae - model_mae,
                            '상태': '완료' if rank == len(features) else '완료(설명변수 선형종속)'})
                metrics.append(row)
                for feature, value in [('intercept', mean_y - mean_x @ beta), *zip(features, beta)]:
                    coefficients.append({'평가 기준': cohort, '평가 연도': int(evaluation_year),
                                         '모델': name, '항': feature, '계수': float(value)})
                for (_, sample), pred in zip(test.iterrows(), estimate):
                    predictions.append({'평가 기준': cohort, '평가 연도': int(evaluation_year), '모델': name,
                                        '품번': sample.part_no, 'LOT': sample.lot,
                                        '실측 나사외경(mm)': sample[target], '예측 나사외경(mm)': float(pred),
                                        '학습 평균 Baseline(mm)': mean_y,
                                        '절대오차(mm)': abs(float(sample[target]) - pred)})
    detail = pd.DataFrame(metrics, columns=['평가 기준', '평가 연도', '모델', '학습 연도', '학습 LOT', '평가 LOT',
                                          'Baseline MAE(mm)', '모델 MAE(mm)', 'MAE 개선량(mm)', '상태'])
    summary = []
    for year in years[1:]:
        selected = detail.loc[detail['평가 기준'].str.startswith('모델별') & detail['평가 연도'].eq(year)]
        a = selected.loc[selected['모델'].eq('전조하경 1변수')].iloc[0]
        b = selected.loc[selected['모델'].eq('전조하경+성형전장길이')].iloc[0]
        summary.append({'평가 연도': int(year), 'Baseline MAE(mm)': a['Baseline MAE(mm)'],
                        '전조하경 1변수 MAE(mm)': a['모델 MAE(mm)'],
                        '전조하경+성형전장길이 MAE(mm)': b['모델 MAE(mm)']})
    return {'regression_summary': pd.DataFrame(summary), 'regression_metrics': detail,
            'regression_predictions': pd.DataFrame(predictions),
            'regression_coefficients': pd.DataFrame(coefficients)}


def extended_plots(data, tables):
    figures = {}
    years = sorted(data.sheet_year.unique())
    colors = ['#2563a6', '#e78b2c', '#138b80', '#9b59b6']
    for key, x, y, xlabel, ylabel in [
        ('diameter_by_year', 'forming_diameter_mm', 'thread_diameter_mm', 'Forming diameter (mm)', 'Thread outside diameter (mm)'),
        ('length_scatter', 'forming_length_mm', 'thread_length_mm', 'Forming overall length (mm)', 'Thread overall length (mm)'),
    ]:
        fig, ax = plt.subplots(figsize=(9, 4.8))
        for i, year in enumerate(years):
            pair = data.loc[data.sheet_year.eq(year), [x, y]].dropna()
            grouped = pair.groupby([x, y]).size().reset_index(name='count')
            ax.scatter(grouped[x], grouped[y], s=grouped['count'] * 22, alpha=.65,
                       color=colors[i % len(colors)], label=f'{year} (n={len(pair)})')
        n = len(data[[x, y]].dropna())
        ax.set(xlabel=xlabel, ylabel=ylabel, title=f'Paired LOT records: n={n}, Pearson r={pearson(data, [x, y]):+.3f}')
        ax.legend(); ax.grid(alpha=.2); fig.tight_layout(); figures[key] = fig

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, col, title in zip(axes, LENGTH_COLUMNS, ['Forming overall length', 'Thread overall length']):
        low, high = SPECS[col]; values = data[col].dropna()
        lo = min(low, values.min()) if len(values) else low
        hi = max(high, values.max()) if len(values) else high
        ax.hist(values, bins=np.linspace(lo - .025, hi + .025, 30), color='#138b80', edgecolor='white')
        ax.axvline(low, color='red', ls='--'); ax.axvline(high, color='red', ls='--')
        ax.set(title=title, xlabel='Recorded length (mm)', ylabel='LOT count')
    fig.tight_layout(); figures['length_histograms'] = fig

    equipment = tables['equipment_composition'].pivot(index='연도', columns='성형 설비', values='LOT 수').fillna(0)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    equipment.rename(columns={'미기록': 'Unknown'}).plot.bar(ax=ax, color=colors)
    for bars in ax.containers:
        ax.bar_label(bars, fmt='%.0f', padding=3)
    ax.set(xlabel='Sheet year', ylabel='LOT count', title='Forming equipment composition')
    ax.tick_params(axis='x', rotation=0); ax.legend(title='Equipment'); fig.tight_layout()
    figures['equipment_composition'] = fig

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, col, title in zip(axes, ['forming_diameter_mm', 'thread_diameter_mm'], ['Forming diameter', 'Thread outside diameter']):
        means = data.groupby('sheet_year')[col].mean()
        ax.plot(means.index, means.values, 'o-', color='#2563a6')
        ax.set(xticks=years, xlabel='Sheet year', ylabel='Mean recorded value (mm)', title=title)
        ax.ticklabel_format(axis='y', useOffset=False); ax.grid(alpha=.2)
    fig.tight_layout(); figures['diameter_year_means'] = fig

    corr = tables['length_correlation']
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = corr['구분'].replace({'전체': 'All'})
    bars = ax.bar(labels, corr['피어슨 r'], color=colors)
    ax.bar_label(bars, labels=[f'{v:+.3f}' if pd.notna(v) else 'N/A' for v in corr['피어슨 r']], padding=4)
    ax.set(ylim=(-1, 1), ylabel='Pearson r', title='Overall-length correlation by year')
    ax.axhline(0, color='gray', lw=.8); ax.grid(axis='y', alpha=.2)
    fig.tight_layout(); figures['length_correlation'] = fig

    monthly = tables['monthly_thread_defects'].copy()
    if not monthly.empty:
        totals = monthly.groupby(monthly['LOT 생산월'].str[:4])['전조 불량수량'].sum(min_count=1)
        active = totals[totals.gt(0)].index
        shown = monthly.loc[monthly['LOT 생산월'].str[:4].isin(active)] if len(active) else monthly
        fig, ax = plt.subplots(figsize=(10, 4.5))
        bars = ax.bar(shown['LOT 생산월'], shown['전조 불량수량'], color='#138b80')
        ax.bar_label(bars, fmt='{:,.0f}', padding=3)
        ax.set(xlabel='Production month from LOT code (not inspection month)', ylabel='Recorded defective units',
               title='Thread defects by LOT production month')
        ax.tick_params(axis='x', rotation=35); ax.grid(axis='y', alpha=.2)
        fig.tight_layout(); figures['monthly_thread_defects'] = fig

    top = tables['top_defect_lots'].head(20)
    if not top.empty:
        fig, ax = plt.subplots(figsize=(11, 5.5))
        ax.bar(top['lot'], top['thread_defects'], color='#2563a6')
        ax.set(xlabel='LOT (descending defect count)', ylabel='Recorded defective units', title='Top 20 LOTs and cumulative share of ALL recorded defects')
        ax.tick_params(axis='x', rotation=80)
        right = ax.twinx(); right.plot(top['lot'], top['누적 비중(%)'], 'o-', color='#d35400')
        right.set(ylabel='Cumulative share (%)', ylim=(0, 105))
        fig.tight_layout(); figures['defect_pareto'] = fig
    return figures
