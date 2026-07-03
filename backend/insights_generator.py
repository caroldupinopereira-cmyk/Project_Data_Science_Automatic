"""
backend/insights_generator.py
Week 15 — Intelligent Insight Generator (Bilingual: EN + ID)

Insights yang dihasilkan:
  1.  Kualitas data (missing values)
  2.  Ukuran & struktur dataset
  3.  Variabel dengan rata-rata tertinggi
  4.  Variabel dengan missing value terbanyak
  5.  Variabel dengan outlier terbanyak
  6.  Variabel dengan standar deviasi terbesar
  7.  Korelasi terkuat antar variabel
  8.  Identifikasi distribusi normal vs tidak normal
  9.  Distribusi kategorik (class balance)
  10. Time series patterns (jika ada — dioper dari time_series.py)
  11. Rekomendasi analisis lanjut

Returns dict: { 'en': [...], 'id': [...] }
"""

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from backend.data_sanitizer import sanitize_series, safe_corr_matrix


# ─── Helper ──────────────────────────────────────────────────────────────────

def _pct(a, b):
    return round(a / b * 100, 1) if b > 0 else 0.0


def _normality(series, max_sample=5000):
    """Mengembalikan 'Normal' atau 'Not Normal' via Shapiro-Wilk."""
    clean = sanitize_series(series)  # forced numeric, drop NaN
    if len(clean) < 3 or clean.nunique() <= 1:
        return 'N/A'
    sample = clean if len(clean) <= max_sample else clean.sample(max_sample, random_state=42)
    try:
        _, p = scipy_stats.shapiro(sample)
        return 'Normal' if p > 0.05 else 'Not Normal'
    except Exception:
        return 'N/A'


def _outlier_count(series):
    """Hitung outlier dengan metode IQR (safe terhadap non-numeric)."""
    clean = sanitize_series(series)  # forced numeric, drop NaN
    if len(clean) < 4:
        return 0
    try:
        q1, q3 = float(clean.quantile(0.25)), float(clean.quantile(0.75))
        iqr = q3 - q1
        if iqr == 0:
            return 0
        return int(((clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)).sum())
    except Exception:
        return 0


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def generate_auto_insights(df, num_cols, cat_cols, ts_insights=None):
    """
    Menghasilkan list insight otomatis dalam 2 bahasa.

    Parameters
    ----------
    df          : DataFrame lengkap
    num_cols    : list kolom numerik
    cat_cols    : list kolom kategorik
    ts_insights : list insight dari time_series.py (opsional) — format EN

    Returns
    -------
    dict: { 'en': list[dict], 'id': list[dict] }
    Each dict: {type, icon, title, desc}
    """
    insights_en = []
    insights_id = []
    total_rows  = len(df)
    total_cells = df.size

    def _add(type_, icon, title_en, desc_en, title_id, desc_id):
        insights_en.append({'type': type_, 'icon': icon, 'title': title_en, 'desc': desc_en})
        insights_id.append({'type': type_, 'icon': icon, 'title': title_id, 'desc': desc_id})

    # ── 1. DATA QUALITY (missing values) ─────────────────────────────────────
    total_missing = int(df.isna().sum().sum())
    miss_pct = _pct(total_missing, total_cells)

    if total_missing == 0:
        _add(
            'success', 'fa-check-circle',
            ' Excellent Data Quality — Zero Missing Values',
            ('No missing values found at all. '
             'The dataset is clean and ready for statistical analysis '
             'or machine learning without additional preprocessing.'),
            ' Kualitas Data Sangat Baik — Tidak Ada Missing Values',
            ('Tidak ditemukan missing values sama sekali. '
             'Dataset bersih dan siap digunakan untuk analisis statistik '
             'maupun pemodelan machine learning tanpa preprocessing tambahan.')
        )
    elif miss_pct < 5:
        _add(
            'warning', 'fa-exclamation-triangle',
            f' Minor Missing Values ({miss_pct}%)',
            (f'There are {total_missing:,} empty cells ({miss_pct}% of total data). '
             'This level is still considered safe, but imputation '
             '(mean/median/mode) is recommended before modeling.'),
            f' Missing Values Kecil ({miss_pct}%)',
            (f'Terdapat {total_missing:,} sel kosong ({miss_pct}% dari total data). '
             'Tingkat ini masih tergolong aman, namun disarankan melakukan imputasi '
             '(mean/median/modus) sebelum pemodelan.')
        )
    else:
        _add(
            'danger', 'fa-times-circle',
            f' High Missing Rate ({miss_pct}%)',
            (f'Dataset has {total_missing:,} missing values ({miss_pct}% of total data). '
             'This rate is quite high and may affect the validity of the analysis. '
             'Consider a more aggressive missing data handling strategy '
             '(imputation, deletion, or model-based filling).'),
            f' Tingkat Missing Tinggi ({miss_pct}%)',
            (f'Dataset memiliki {total_missing:,} missing values ({miss_pct}% dari total data). '
             'Tingkat ini cukup tinggi dan dapat mempengaruhi validitas analisis. '
             'Pertimbangkan strategi penanganan missing data yang lebih agresif '
             '(imputation, deletion, atau model-based filling).')
        )

    # ── 2. DATASET SIZE & STRUCTURE ──────────────────────────────────────────
    if total_rows >= 100_000:
        size_note_en = 'Very large dataset. Consider strategic sampling or distributed computing.'
        size_note_id = 'Dataset berukuran sangat besar. Pertimbangkan sampling strategis atau distributed computing.'
    elif total_rows >= 10_000:
        size_note_en = 'Large dataset — well-suited for robust statistical analysis and machine learning.'
        size_note_id = 'Dataset berukuran besar — cocok untuk analisis statistik yang robust dan machine learning.'
    elif total_rows >= 1_000:
        size_note_en = 'Dataset size is sufficiently representative for reliable statistical analysis.'
        size_note_id = 'Ukuran dataset cukup representatif untuk analisis statistik yang handal.'
    elif total_rows >= 100:
        size_note_en = 'Medium-sized dataset. Analysis results are fairly stable but should be validated.'
        size_note_id = 'Dataset berukuran sedang. Hasil analisis cukup stabil namun perlu divalidasi.'
    else:
        size_note_en = 'Small dataset (< 100 rows). Statistical results may be unstable — be careful with generalizations.'
        size_note_id = 'Dataset berukuran kecil (< 100 baris). Hasil statistik mungkin kurang stabil — hati-hati dalam generalisasi.'

    _add(
        'info', 'fa-database',
        f' Dataset: {total_rows:,} Rows × {len(df.columns)} Columns',
        (f'{size_note_en} '
         f'Consists of {len(num_cols)} numeric and {len(cat_cols)} categorical columns.'),
        f' Dataset: {total_rows:,} Baris × {len(df.columns)} Kolom',
        (f'{size_note_id} '
         f'Terdiri dari {len(num_cols)} kolom numerik dan {len(cat_cols)} kolom kategorik.')
    )

    # ── 3. HIGHEST AVERAGE VARIABLE ──────────────────────────────────────────
    if num_cols:
        means = {}
        for col in num_cols:
            try:
                s = sanitize_series(df[col] if col in df.columns else pd.Series(dtype=float), col)
                if not s.empty:
                    means[col] = float(s.mean())
            except Exception:
                pass
        if means:
            top_mean_col = max(means, key=means.get)
            top_mean_val = round(means[top_mean_col], 2)
            s_top = sanitize_series(df[top_mean_col], top_mean_col)
            median_v = round(float(s_top.median()), 2) if not s_top.empty else 'N/A'
            std_v    = round(float(s_top.std()), 2) if len(s_top) >= 2 else 'N/A'
            _add(
                'primary', 'fa-arrow-up',
                f' Highest Average Value: {top_mean_col}',
                (f'Column <strong>{top_mean_col}</strong> has the highest average value '
                 f'of <strong>{top_mean_val:,}</strong>. '
                 f'Median: {median_v}, Std: {std_v}.'),
                f' Nilai Rata-rata Tertinggi: {top_mean_col}',
                (f'Kolom <strong>{top_mean_col}</strong> memiliki nilai rata-rata tertinggi '
                 f'sebesar <strong>{top_mean_val:,}</strong>. '
                 f'Median: {median_v}, Std: {std_v}.')
            )

    # ── 4. MOST MISSING VALUES VARIABLE ──────────────────────────────────────
    miss_per_col = df.isna().sum()
    if miss_per_col.max() > 0:
        worst_col   = miss_per_col.idxmax()
        worst_count = int(miss_per_col.max())
        worst_pct   = _pct(worst_count, total_rows)
        rec_en = 'It is recommended to drop this column if >50% is missing.' if worst_pct > 50 else 'Consider imputation for this column.'
        rec_id = 'Disarankan untuk membuang kolom ini jika >50% hilang.' if worst_pct > 50 else 'Pertimbangkan imputasi untuk kolom ini.'
        _add(
            'danger', 'fa-exclamation',
            f' Most Missing Values: {worst_col}',
            (f'Column <strong>{worst_col}</strong> has the most missing values: '
             f'<strong>{worst_count:,} rows ({worst_pct}%)</strong>. {rec_en}'),
            f' Missing Values Terbanyak: {worst_col}',
            (f'Kolom <strong>{worst_col}</strong> memiliki missing values terbanyak: '
             f'<strong>{worst_count:,} baris ({worst_pct}%)</strong>. {rec_id}')
        )

    # ── 5. MOST OUTLIERS VARIABLE ─────────────────────────────────────────────
    if num_cols:
        outlier_counts = {col: _outlier_count(df[col]) for col in num_cols}
        max_out_col = max(outlier_counts, key=outlier_counts.get)
        max_out_val = outlier_counts[max_out_col]
        max_out_pct = _pct(max_out_val, total_rows)

        if max_out_val > 0:
            _add(
                'warning', 'fa-dot-circle',
                f' Most Outliers: {max_out_col}',
                (f'Column <strong>{max_out_col}</strong> has the most outliers: '
                 f'<strong>{max_out_val:,} data points ({max_out_pct}%)</strong> '
                 f'based on IQR method (±1.5×IQR). '
                 f'Check whether these outliers are data errors or valid extreme values.'),
                f' Outlier Terbanyak: {max_out_col}',
                (f'Kolom <strong>{max_out_col}</strong> memiliki outlier terbanyak: '
                 f'<strong>{max_out_val:,} titik data ({max_out_pct}%)</strong> '
                 f'berdasarkan metode IQR (±1.5×IQR). '
                 f'Tinjau apakah outlier ini merupakan error data atau nilai ekstrem yang valid.')
            )
        else:
            _add(
                'success', 'fa-bullseye',
                ' No Outliers Detected',
                ('No outliers found in any numeric column '
                 'using the IQR method. Data is distributed within reasonable ranges.'),
                ' Tidak Ada Outlier Terdeteksi',
                ('Tidak ditemukan outlier pada seluruh kolom numerik '
                 'menggunakan metode IQR. Data terdistribusi dalam rentang yang wajar.')
            )

    # ── 6. HIGHEST STD DEVIATION VARIABLE ────────────────────────────────────
    if num_cols:
        stds = {}
        for col in num_cols:
            try:
                s = sanitize_series(df[col] if col in df.columns else pd.Series(dtype=float), col)
                if not s.empty and len(s) >= 2:
                    stds[col] = float(s.std())
            except Exception:
                pass
        if stds:
            top_std_col = max(stds, key=stds.get)
            top_std_val = round(stds[top_std_col], 4)
            s_top = sanitize_series(df[top_std_col], top_std_col)
            mean_top = float(s_top.mean()) if not s_top.empty else 0
            cv = round(top_std_val / mean_top * 100, 1) if mean_top != 0 else 0

            var_en = 'very high' if cv > 30 else ('high' if cv > 15 else 'moderate')
            spread_en = 'wide' if cv > 15 else 'moderate'
            var_id = 'sangat tinggi' if cv > 30 else ('tinggi' if cv > 15 else 'wajar')
            spread_id = 'lebar' if cv > 15 else 'moderat'

            _add(
                'orange', 'fa-ruler-horizontal',
                f' Highest Std Deviation: {top_std_col}',
                (f'Column <strong>{top_std_col}</strong> has the largest standard deviation '
                 f'of <strong>{top_std_val:,}</strong> (CV={cv}%). '
                 f'{var_en.capitalize()} variability on this column indicates a {spread_en} data spread.'),
                f' Standar Deviasi Terbesar: {top_std_col}',
                (f'Kolom <strong>{top_std_col}</strong> memiliki standar deviasi terbesar '
                 f'sebesar <strong>{top_std_val:,}</strong> (CV={cv}%). '
                 f'Variabilitas {var_id} pada kolom ini menunjukkan sebaran data yang {spread_id}.')
            )

    # ── 7. STRONGEST CORRELATION — via safe_corr_matrix ──────────────────────
    if len(num_cols) > 1:
        try:
            valid_cols, corr_df = safe_corr_matrix(df, num_cols)
            if corr_df is not None and len(valid_cols) >= 2:
                np.fill_diagonal(corr_df.values, np.nan)
                abs_corr = corr_df.abs()
                flat     = abs_corr.values.flatten()
                flat_nan = flat[~np.isnan(flat)]
                if len(flat_nan) > 0:
                    max_idx  = np.unravel_index(np.nanargmax(abs_corr.values), abs_corr.shape)
                    col_a, col_b = valid_cols[max_idx[0]], valid_cols[max_idx[1]]
                    r_val = round(float(corr_df.iloc[max_idx[0], max_idx[1]]), 3)
                    direction_en = 'positive' if r_val > 0 else 'negative'
                    direction_id = 'positif' if r_val > 0 else 'negatif'
                    if abs(r_val) > 0.8:
                        strength_en, strength_id = 'Very Strong', 'Sangat Kuat'
                    elif abs(r_val) > 0.6:
                        strength_en, strength_id = 'Strong', 'Kuat'
                    elif abs(r_val) > 0.4:
                        strength_en, strength_id = 'Moderate', 'Sedang'
                    else:
                        strength_en, strength_id = 'Weak', 'Lemah'

                    sig_en = 'This relationship is highly significant and worth investigating further.' if abs(r_val) > 0.6 else 'This relationship is moderate and may be influenced by other variables.'
                    sig_id = 'Hubungan ini sangat signifikan dan layak diinvestigasi lebih lanjut.' if abs(r_val) > 0.6 else 'Hubungan ini moderat dan mungkin dipengaruhi variabel lain.'

                    _add(
                        'primary', 'fa-link',
                        f' Strongest Correlation: {col_a} ↔ {col_b} (r={r_val})',
                        (f'{strength_en} ({direction_en}) correlation found between '
                         f'<strong>{col_a}</strong> and <strong>{col_b}</strong> with r = {r_val}. '
                         f'{sig_en} (R² = {round(r_val**2, 3)})'),
                        f' Korelasi Terkuat: {col_a} ↔ {col_b} (r={r_val})',
                        (f'Korelasi {strength_id} ({direction_id}) ditemukan antara '
                         f'<strong>{col_a}</strong> dan <strong>{col_b}</strong> dengan r = {r_val}. '
                         f'{sig_id} (R² = {round(r_val**2, 3)})')
                    )
        except Exception:
            pass

    # ── 8. NORMALITY DISTRIBUTION ─────────────────────────────────────────────
    if num_cols:
        normal_cols     = []
        not_normal_cols = []
        for col in num_cols:
            result = _normality(df[col])
            if result == 'Normal':
                normal_cols.append(col)
            elif result == 'Not Normal':
                not_normal_cols.append(col)

        if normal_cols or not_normal_cols:
            total_tested = len(normal_cols) + len(not_normal_cols)
            normal_pct   = _pct(len(normal_cols), total_tested)
            nn_list = ', '.join(not_normal_cols[:3]) + (f' (+{len(not_normal_cols)-3} more)' if len(not_normal_cols) > 3 else '')
            nn_list_id = ', '.join(not_normal_cols[:3]) + (f' (+{len(not_normal_cols)-3} lainnya)' if len(not_normal_cols) > 3 else '')
            n_list  = ', '.join(normal_cols[:3])     + (f' (+{len(normal_cols)-3} more)'     if len(normal_cols) > 3 else '')
            n_list_id = ', '.join(normal_cols[:3])   + (f' (+{len(normal_cols)-3} lainnya)'  if len(normal_cols) > 3 else '')

            desc_en = (
                (f'Normally distributed columns: {n_list}. ' if normal_cols else '') +
                (f'NOT normal columns: {nn_list}. ' if not_normal_cols else '') +
                (f'Non-normal columns ({100 - normal_pct}%) require non-parametric tests '
                 f'(Mann-Whitney, Kruskal-Wallis) or data transformation '
                 f'(log, sqrt, Box-Cox) before parametric analysis.'
                 if not_normal_cols else
                 'All columns are normally distributed — parametric analysis can be performed.')
            )
            desc_id = (
                (f'Kolom berdistribusi normal: {n_list_id}. ' if normal_cols else '') +
                (f'Kolom TIDAK normal: {nn_list_id}. ' if not_normal_cols else '') +
                (f'Kolom tidak normal ({100 - normal_pct}%) memerlukan uji non-parametrik '
                 f'(Mann-Whitney, Kruskal-Wallis) atau transformasi data '
                 f'(log, sqrt, Box-Cox) sebelum analisis parametrik.'
                 if not_normal_cols else
                 'Semua kolom berdistribusi normal — analisis parametrik dapat dilakukan.')
            )
            _add(
                'info', 'fa-bell',
                f' Normality Test — {len(normal_cols)}/{total_tested} Columns Normal',
                desc_en,
                f' Uji Normalitas — {len(normal_cols)}/{total_tested} Kolom Normal',
                desc_id
            )

        # Skewness — sanitized
        skewed = []
        for col in num_cols:
            try:
                s = sanitize_series(df[col] if col in df.columns else pd.Series(dtype=float), col)
                if not s.empty and s.nunique() >= 2:
                    skw = float(s.skew())
                    if abs(skw) > 1:
                        skewed.append(f'{col} (skew={round(skw, 2)})')
            except Exception:
                pass
        if skewed:
            _add(
                'warning', 'fa-chart-line',
                f' Skewed Distributions: {len(skewed)} Column(s)',
                (f'The following columns have skewness > 1: {", ".join(skewed[:4])}. '
                 'These skewed distributions can affect parametric analysis results. '
                 'Consider log or Box-Cox transformation.'),
                f' Distribusi Miring: {len(skewed)} Kolom',
                (f'Kolom berikut memiliki skewness > 1: {", ".join(skewed[:4])}. '
                 'Distribusi miring ini dapat memengaruhi hasil analisis parametrik. '
                 'Pertimbangkan transformasi log atau Box-Cox.')
            )

    # ── 9. CATEGORICAL DISTRIBUTION ──────────────────────────────────────────
    if cat_cols:
        col = cat_cols[0]
        vc  = df[col].value_counts()
        dom_pct = _pct(vc.iloc[0], total_rows) if not vc.empty else 0

        if dom_pct > 70:
            bt = 'danger'
            bl_en, bl_id = 'Very Imbalanced', 'Sangat Tidak Seimbang'
            bn_en = f'Category "{vc.index[0]}" dominates {dom_pct}% of data — beware of class imbalance in modeling.'
            bn_id = f'Kategori "{vc.index[0]}" mendominasi {dom_pct}% data — waspadai class imbalance dalam pemodelan.'
        elif dom_pct > 50:
            bt = 'warning'
            bl_en, bl_id = 'Slightly Imbalanced', 'Kurang Seimbang'
            bn_en = f'Category "{vc.index[0]}" is quite dominant ({dom_pct}%). Consider oversampling if used for classification.'
            bn_id = f'Kategori "{vc.index[0]}" cukup dominan ({dom_pct}%). Pertimbangkan oversampling jika digunakan untuk klasifikasi.'
        else:
            bt = 'success'
            bl_en, bl_id = 'Balanced', 'Seimbang'
            bn_en = f'Category distribution is fairly even. Most frequent category: "{vc.index[0]}" ({dom_pct}%).'
            bn_id = f'Distribusi kategori cukup merata. Kategori terbanyak: "{vc.index[0]}" ({dom_pct}%).'

        _add(
            bt, 'fa-tags',
            f' Categorical Balance ({col}): {bl_en}',
            f'{bn_en} Total {df[col].nunique()} unique categories in column {col}.',
            f' Keseimbangan Kategorik ({col}): {bl_id}',
            f'{bn_id} Total {df[col].nunique()} kategori unik pada kolom {col}.'
        )

    # ── 10. TIME SERIES INSIGHTS (dari time_series.py) ───────────────────────
    if ts_insights:
        for ts_ins in ts_insights:
            # ts_insights hanya tersedia dalam EN; untuk ID kita salin saja
            insights_en.append(ts_ins)
            # Buat versi ID dari TS insight jika belum ada field id
            ts_ins_id = dict(ts_ins)
            insights_id.append(ts_ins_id)

    # ── 11. FURTHER ANALYSIS RECOMMENDATIONS ─────────────────────────────────
    recs_en = []
    recs_id = []
    if num_cols and cat_cols:
        recs_en.append('One-Way ANOVA / T-Test to compare means across categorical groups')
        recs_id.append('One-Way ANOVA / T-Test untuk membandingkan rata-rata antar grup kategorik')
    if len(num_cols) > 1:
        recs_en.append('Linear / Logistic Regression for prediction and modeling')
        recs_id.append('Regresi Linear / Logistik untuk prediksi dan pemodelan')
    if len(cat_cols) >= 2:
        recs_en.append("Chi-Square + Cramér's V for categorical variable association")
        recs_id.append("Chi-Square + Cramér's V untuk asosiasi antar variabel kategorik")
    if any(_normality(df[c]) == 'Not Normal' for c in num_cols):
        recs_en.append('Non-Parametric Tests (Mann-Whitney, Spearman) for non-normal columns')
        recs_id.append('Uji Non-Parametrik (Mann-Whitney, Spearman) untuk kolom tidak normal')
    if len(num_cols) >= 3:
        recs_en.append('Principal Component Analysis (PCA) for dimensionality reduction')
        recs_id.append('Principal Component Analysis (PCA) untuk reduksi dimensi')

    if recs_en:
        _add(
            'success', 'fa-rocket',
            ' Further Analysis Recommendations',
            'Based on the structure of this dataset, suggested techniques: ' + '; '.join(recs_en) + '.',
            ' Rekomendasi Analisis Lanjut',
            'Berdasarkan struktur dataset ini, teknik yang disarankan: ' + '; '.join(recs_id) + '.'
        )

    return {'en': insights_en, 'id': insights_id}