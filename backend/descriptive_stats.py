"""
backend/descriptive_stats.py
Descriptive Statistics Generator — Kelompok 2 ITSB

Numerical columns output:
  Mean, Median, Min, Max, Std Dev, Variance, Mode,
  Skewness, Kurtosis, Missing Count, Missing %, Normality, Outliers

Categorical columns output:
  Unique, Mode, Mode Freq, Mode %, Missing Count, Missing %

DATA SANITIZATION:
  - All numeric operations use data_sanitizer helpers.
  - Forced pd.to_numeric(errors='coerce') for string-encoded numbers.
  - Empty-safe: returns 'N/A' if series is empty after sanitization.
  - Full try-except per column so one bad col never halts the dashboard.
"""

import pandas as pd
import numpy as np
from scipy.stats import shapiro

from backend.data_sanitizer import (
    sanitize_series,
    safe_iqr_outliers,
    _fmt,
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _pct(count, total, decimals=2):
    """Safe percentage calculation."""
    if total == 0:
        return "0.00%"
    return f"{round(count / total * 100, decimals)}%"


def _safe_mode(series):
    """Return mode value as string or 'N/A', safe against empty series."""
    try:
        m = series.mode()
        return m.iloc[0] if not m.empty else "N/A"
    except Exception:
        return "N/A"


def _safe_normality(clean_series, n_clean):
    """Run Shapiro-Wilk, return readable string. Safe against all edge cases."""
    if n_clean < 3:
        return "N/A (n<3)"
    try:
        sample = clean_series if n_clean <= 5000 else clean_series.sample(5000, random_state=42)
        if sample.nunique() <= 1:
            return "Not Normal (constant)"
        _, p_val = shapiro(sample)
        return "Normal" if p_val > 0.05 else "Not Normal"
    except Exception:
        return "N/A"


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY METRICS  (untuk KPI cards di dashboard)
# ─────────────────────────────────────────────────────────────────────────────

def get_summary_metrics(df, num_cols=None, cat_cols=None):
    """
    Mengembalikan dict metrik level dataset.
    Dipanggil di app.py dan dioper ke template sebagai `metrics`.

    num_cols dan cat_cols bersifat opsional — jika tidak diisi,
    akan di-detect otomatis dari df sehingga app.py lama tetap bisa
    memanggil get_summary_metrics(df) tanpa error.
    """
    try:
        # Auto-detect jika tidak dioper dari app.py
        if num_cols is None:
            num_cols = df.select_dtypes(include=['number']).columns.tolist()
        if cat_cols is None:
            cat_cols = df.select_dtypes(include=['object', 'category', 'string']).columns.tolist()

        total_rows    = len(df)
        total_columns = len(df.columns)
        missing_cells = int(df.isna().sum().sum())
        total_cells   = total_rows * total_columns
        missing_pct   = round(missing_cells / total_cells * 100, 2) if total_cells > 0 else 0.0

        return {
            "total_rows":     f"{total_rows:,}",
            "total_columns":  f"{total_columns:,}",
            "num_count":      len(num_cols),
            "cat_count":      len(cat_cols),
            "missing_cells":  f"{missing_cells:,}",
            "missing_pct":    f"{missing_pct}%",
        }
    except Exception as exc:
        print(f"[descriptive_stats] get_summary_metrics error: {exc}")
        return {
            "total_rows": "N/A", "total_columns": "N/A",
            "num_count": 0, "cat_count": 0,
            "missing_cells": "N/A", "missing_pct": "N/A",
        }


# ─────────────────────────────────────────────────────────────────────────────
# DESCRIPTIVE STATS
# ─────────────────────────────────────────────────────────────────────────────

def get_descriptive_stats(df, num_cols, cat_cols):
    """
    Menghitung statistik deskriptif lengkap dengan sanitisasi data ketat.

    Returns
    -------
    num_stats : list[dict]   — Satu dict per kolom numerik
    cat_stats : list[dict]   — Satu dict per kolom kategorik
    """
    total_rows = len(df)
    num_stats  = []
    cat_stats  = []

    # ══════════════════════════════════════════════════════════════════════════
    # NUMERICAL STATISTICS
    # ══════════════════════════════════════════════════════════════════════════

    for col in num_cols:
        try:
            # ── Step 1: Validate & sanitize ───────────────────────────────────
            raw_series = df[col] if col in df.columns else pd.Series(dtype=float)

            # Forced conversion: string → numeric (non-convertible → NaN)
            clean = sanitize_series(raw_series, col)

            # ── Step 2: Missing count (from raw series before sanitize) ───────
            missing_count = int(raw_series.isna().sum())
            missing_pct   = _pct(missing_count, total_rows)
            n_clean       = len(clean)

            # ── Step 3: If empty after sanitize → all N/A ─────────────────────
            if n_clean == 0:
                num_stats.append({
                    "Column":        col,
                    "Mean":          "N/A",
                    "Median":        "N/A",
                    "Min":           "N/A",
                    "Max":           "N/A",
                    "Std Dev":       "N/A",
                    "Variance":      "N/A",
                    "Mode":          "N/A",
                    "Skewness":      "N/A",
                    "Kurtosis":      "N/A",
                    "Missing Count": missing_count,
                    "Missing %":     missing_pct,
                    "Normality":     "N/A",
                    "Outliers":      0,
                })
                continue

            # ── Step 4: Central tendency ──────────────────────────────────────
            mean_val   = _fmt(clean.mean())
            median_val = _fmt(clean.median())
            min_val    = _fmt(clean.min())
            max_val    = _fmt(clean.max())

            # ── Step 5: Dispersion ────────────────────────────────────────────
            std_val = _fmt(clean.std())  if n_clean >= 2 else "N/A"
            var_val = _fmt(clean.var())  if n_clean >= 2 else "N/A"

            # ── Step 6: Mode ──────────────────────────────────────────────────
            mode_val = _fmt(_safe_mode(clean))

            # ── Step 7: Shape ─────────────────────────────────────────────────
            skew_val = _fmt(clean.skew(), decimals=4) if clean.nunique() >= 2 else "N/A"
            kurt_val = _fmt(clean.kurt(), decimals=4) if clean.nunique() >= 2 else "N/A"

            # ── Step 8: Normality ─────────────────────────────────────────────
            normality = _safe_normality(clean, n_clean)

            # ── Step 9: Outliers via IQR — safe subtraction ───────────────────
            outliers_count = 0
            iqr_result = safe_iqr_outliers(clean)
            if iqr_result is not None:
                q1, q3, iqr, outliers_count = iqr_result

            num_stats.append({
                "Column":        col,
                "Mean":          mean_val,
                "Median":        median_val,
                "Min":           min_val,
                "Max":           max_val,
                "Std Dev":       std_val,
                "Variance":      var_val,
                "Mode":          mode_val,
                "Skewness":      skew_val,
                "Kurtosis":      kurt_val,
                "Missing Count": missing_count,
                "Missing %":     missing_pct,
                "Normality":     normality,
                "Outliers":      outliers_count,
            })

        except Exception as exc:
            # Per-column safety net: log and continue, never crash dashboard
            print(f"[descriptive_stats] num col '{col}' error: {exc}")
            num_stats.append({
                "Column": col, "Mean": "N/A", "Median": "N/A",
                "Min": "N/A", "Max": "N/A", "Std Dev": "N/A",
                "Variance": "N/A", "Mode": "N/A", "Skewness": "N/A",
                "Kurtosis": "N/A", "Missing Count": 0, "Missing %": "N/A",
                "Normality": "N/A", "Outliers": 0,
            })

    # ══════════════════════════════════════════════════════════════════════════
    # CATEGORICAL STATISTICS
    # ══════════════════════════════════════════════════════════════════════════

    for col in cat_cols:
        try:
            series = df[col] if col in df.columns else pd.Series(dtype=object)

            # ── Missing values ────────────────────────────────────────────────
            missing_count = int(series.isna().sum())
            missing_pct   = _pct(missing_count, total_rows)
            clean         = series.dropna()

            # ── If no clean data ──────────────────────────────────────────────
            if clean.empty:
                cat_stats.append({
                    "Column":        col,
                    "Unique":        0,
                    "Mode":          "N/A",
                    "Mode Freq":     0,
                    "Mode %":        "0.00%",
                    "Missing Count": missing_count,
                    "Missing %":     missing_pct,
                })
                continue

            # ── Unique categories ─────────────────────────────────────────────
            unique_count = int(clean.nunique())

            # ── Mode ──────────────────────────────────────────────────────────
            try:
                vc        = clean.value_counts()
                mode_val  = str(vc.index[0]) if not vc.empty else "N/A"
                mode_freq = int(vc.iloc[0])  if not vc.empty else 0
                mode_pct  = _pct(mode_freq, len(clean))
            except Exception:
                mode_val, mode_freq, mode_pct = "N/A", 0, "N/A"

            cat_stats.append({
                "Column":        col,
                "Unique":        unique_count,
                "Mode":          mode_val,
                "Mode Freq":     mode_freq,
                "Mode %":        mode_pct,
                "Missing Count": missing_count,
                "Missing %":     missing_pct,
            })

        except Exception as exc:
            print(f"[descriptive_stats] cat col '{col}' error: {exc}")
            cat_stats.append({
                "Column": col, "Unique": 0, "Mode": "N/A",
                "Mode Freq": 0, "Mode %": "N/A",
                "Missing Count": 0, "Missing %": "N/A",
            })

    return num_stats, cat_stats