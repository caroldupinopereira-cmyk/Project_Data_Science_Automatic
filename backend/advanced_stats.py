"""
backend/advanced_stats.py
Week 15 — Analisis Statistik Tingkat Lanjut
Meliputi: Quartile, IQR, CV, Percentiles, Chi-Square, Cramér's V, Point-Biserial

DATA SANITIZATION:
  - All numeric columns validated before quantile/corr/CV operations.
  - Forced pd.to_numeric(errors='coerce') via data_sanitizer.
  - Safe correlation matrix: only valid numeric cols passed to df.corr().
  - Per-column and per-operation try-except for maximum robustness.
  - Never crashes dashboard even if individual columns are invalid.
"""

import pandas as pd
import numpy as np
from scipy import stats

from backend.data_sanitizer import (
    sanitize_series,
    filter_numeric_cols,
    sanitize_df_numeric_cols,
    safe_corr_matrix,
    safe_iqr_outliers,
)


def _fmt(val, decimals=3):
    """Safe float formatter → 'N/A' on invalid."""
    if val is None:
        return "N/A"
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return "N/A"
        return round(f, decimals)
    except (TypeError, ValueError):
        return "N/A"


def get_advanced_stats(df, num_cols, cat_cols):
    """
    Menghasilkan statistik lanjutan untuk dashboard Week 15.
    Semua operasi dijaga dengan sanitasi dan error handling.
    """
    result = {}

    # ─── 1. ADVANCED NUMERICAL STATS ─────────────────────────────────────────
    adv_num = []
    for col in num_cols:
        try:
            # Sanitize: force numeric conversion, drop NaN
            s = sanitize_series(df[col] if col in df.columns else pd.Series(dtype=float), col)

            if s.empty:
                adv_num.append({
                    "Column": col,
                    "Q1": "N/A", "Q2 (Median)": "N/A", "Q3": "N/A",
                    "IQR": "N/A", "CV (%)": "N/A",
                    "P5": "N/A", "P95": "N/A",
                    "Shapiro-Wilk": "N/A (no data)"
                })
                continue

            # Quantiles — all in one safe call
            try:
                quants = s.quantile([0.05, 0.25, 0.50, 0.75, 0.95])
                p5,  q1, q2, q3, p95 = (
                    float(quants[0.05]), float(quants[0.25]),
                    float(quants[0.50]), float(quants[0.75]),
                    float(quants[0.95]),
                )
                iqr = q3 - q1
            except Exception:
                p5 = q1 = q2 = q3 = p95 = iqr = None

            # Coefficient of variation — guard against zero mean
            try:
                mean_val = float(s.mean())
                std_val  = float(s.std())
                if not np.isfinite(mean_val) or mean_val == 0:
                    cv = "N/A"
                else:
                    cv = round(std_val / abs(mean_val) * 100, 2)
            except Exception:
                cv = "N/A"

            # Shapiro-Wilk normality test
            normality = "N/A"
            try:
                n = len(s)
                if n >= 3:
                    sample = s if n <= 5000 else s.sample(5000, random_state=42)
                    if sample.nunique() > 1:
                        _, p_val = stats.shapiro(sample)
                        normality = (
                            f"Normal (p={round(p_val, 3)})" if p_val > 0.05
                            else "Not Normal"
                        )
                    else:
                        normality = "Constant"
                else:
                    normality = "N/A (n<3)"
            except Exception:
                normality = "N/A"

            adv_num.append({
                "Column":       col,
                "Q1":           _fmt(q1),
                "Q2 (Median)":  _fmt(q2),
                "Q3":           _fmt(q3),
                "IQR":          _fmt(iqr),
                "CV (%)":       cv,
                "P5":           _fmt(p5),
                "P95":          _fmt(p95),
                "Shapiro-Wilk": normality,
            })

        except Exception as exc:
            print(f"[advanced_stats] adv_num col '{col}' error: {exc}")
            adv_num.append({
                "Column": col,
                "Q1": "N/A", "Q2 (Median)": "N/A", "Q3": "N/A",
                "IQR": "N/A", "CV (%)": "N/A",
                "P5": "N/A", "P95": "N/A",
                "Shapiro-Wilk": "N/A (error)"
            })

    result['adv_num'] = adv_num

    # ─── 2. SAFE CORRELATION MATRIX ──────────────────────────────────────────
    # filter_numeric_cols ensures only truly numeric cols enter df.corr()
    try:
        valid_num_cols, corr_df = safe_corr_matrix(df, num_cols)

        if corr_df is not None and len(valid_num_cols) >= 2:
            corr_df = corr_df.round(3)
            result['corr_cols']   = list(corr_df.columns)
            result['corr_matrix'] = corr_df.values.tolist()

            # Top 5 strongest pairs
            pairs = []
            cols_list = list(corr_df.columns)
            for i in range(len(cols_list)):
                for j in range(i + 1, len(cols_list)):
                    val = corr_df.iloc[i, j]
                    if pd.notna(val):
                        pairs.append((cols_list[i], cols_list[j], round(float(val), 3)))
            pairs.sort(key=lambda x: abs(x[2]), reverse=True)
            result['top_corr_pairs'] = pairs[:5]
        else:
            result['corr_cols']      = []
            result['corr_matrix']    = []
            result['top_corr_pairs'] = []
    except Exception as exc:
        print(f"[advanced_stats] correlation matrix error: {exc}")
        result['corr_cols']      = []
        result['corr_matrix']    = []
        result['top_corr_pairs'] = []

    # ─── 3. CATEGORICAL ANALYSIS ──────────────────────────────────────────────
    cat_freq = []
    for col in cat_cols[:3]:
        try:
            if col not in df.columns:
                continue
            vc  = df[col].value_counts(normalize=False).head(10)
            pct = df[col].value_counts(normalize=True).head(10) * 100
            if vc.empty:
                continue
            cat_freq.append({
                "col":    col,
                "labels": list(vc.index.astype(str)),
                "counts": list(vc.values.astype(int)),
                "pct":    [round(p, 1) for p in pct.values],
            })
        except Exception as exc:
            print(f"[advanced_stats] cat_freq col '{col}' error: {exc}")

    result['cat_freq'] = cat_freq

    # ─── 4. CHI-SQUARE & CRAMÉR'S V ──────────────────────────────────────────
    assoc = []
    if len(cat_cols) >= 2:
        for i in range(min(len(cat_cols), 4)):
            for j in range(i + 1, min(len(cat_cols), 4)):
                col_a, col_b = cat_cols[i], cat_cols[j]
                try:
                    if col_a not in df.columns or col_b not in df.columns:
                        continue
                    ct = pd.crosstab(df[col_a], df[col_b])
                    if ct.empty or min(ct.shape) < 2:
                        continue
                    chi2, p, dof, _ = stats.chi2_contingency(ct)
                    n = ct.values.sum()
                    v = np.sqrt(chi2 / (n * (min(ct.shape) - 1))) if min(ct.shape) > 1 and n > 0 else 0
                    if not np.isfinite(v):
                        v = 0.0
                    assoc.append({
                        "col_a": col_a, "col_b": col_b,
                        "chi2": round(float(chi2), 2),
                        "p": round(float(p), 4),
                        "cramers_v": round(float(v), 3),
                        "strength": "Kuat" if v > 0.5 else ("Sedang" if v > 0.3 else "Lemah"),
                    })
                except Exception as exc:
                    print(f"[advanced_stats] chi2 ({col_a}×{col_b}) error: {exc}")

    result['cat_assoc'] = assoc

    # ─── 5. NUMERICAL vs CATEGORICAL (ANOVA) ──────────────────────────────────
    num_cat_analysis = []
    if num_cols and cat_cols:
        for nc in num_cols[:3]:
            for cc in cat_cols[:2]:
                try:
                    if nc not in df.columns or cc not in df.columns:
                        continue

                    # Sanitize the numeric column before groupby
                    df_work = df[[nc, cc]].copy()
                    df_work[nc] = pd.to_numeric(df_work[nc], errors='coerce')
                    df_work = df_work.dropna()

                    if df_work.empty:
                        continue

                    groups = df_work.groupby(cc)[nc].agg(['mean', 'std', 'count'])
                    groups = groups[groups['count'] >= 2].dropna()

                    if groups.empty or len(groups) < 2:
                        continue

                    group_means = {str(k): round(float(v), 3) for k, v in groups['mean'].items()}
                    group_data  = [
                        df_work[df_work[cc] == g][nc].dropna().values
                        for g in groups.index
                    ]
                    group_data = [g for g in group_data if len(g) >= 2]

                    if len(group_data) < 2:
                        continue

                    f_stat, p_anova = stats.f_oneway(*group_data)
                    if not np.isfinite(f_stat) or not np.isfinite(p_anova):
                        continue

                    num_cat_analysis.append({
                        "num": nc, "cat": cc,
                        "group_means": group_means,
                        "f_stat":     round(float(f_stat), 3),
                        "p_anova":    round(float(p_anova), 4),
                        "significant": bool(p_anova < 0.05),
                    })
                except Exception as exc:
                    print(f"[advanced_stats] ANOVA ({nc}×{cc}) error: {exc}")

    result['num_cat'] = num_cat_analysis[:4]

    return result
