"""
backend/dashboard_overview.py
Dashboard Overview — KPI cards + grid visualisasi.

SLOT RULES (tidak ada chart duplikat, semua slot punya toggle):
  ov_hbar        → Pareto Chart            (cat_cols >= 1, toggle cat_cols)   ← ganti Count Plot
  ov_center      → Pie/Donut Chart         (cat_cols >= 1, toggle cat_cols)
  ov_top_right   → TS line / Scatter       (dt+num → TS tanpa toggle;
                                            num>=2 → Scatter dengan toggle X & Y)
  ov_vbar_left   → Histogram per num_col   (num_cols >= 1, toggle num_cols)
  ov_area_bottom → Boxplot per num_col     (num_cols >= 1, toggle num_cols)
  ov_vbar_right  → Bar Chart per cat_col   (cat_cols >= 1, toggle cat_cols)
"""

import numpy as np
import pandas as pd

from backend.data_sanitizer import sanitize_series, safe_iqr_outliers
from backend.viz_engine import (
    _chart_bar,
    _chart_pareto,
    _chart_histogram,
    _chart_boxplot,
    _chart_pie,
    _chart_scatter,
    _json,
    _axes,
    _layout,
    _to_list,
    PALETTE,
    PLOT_BG,
)
import plotly.graph_objects as go


# ─── helpers ─────────────────────────────────────────────────────────────────

def _fmt_num(val, decimals=2):
    try:
        f = float(val)
        if abs(f) >= 1_000_000:
            return f"{f/1_000_000:,.2f}M"
        if abs(f) >= 1_000:
            return f"{f:,.{decimals}f}"
        return round(f, decimals)
    except (TypeError, ValueError):
        return "N/A"


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"[overview] chart error in {fn.__name__}: {e}")
        return None


# ─── KPI builder ─────────────────────────────────────────────────────────────

def build_overview_kpis(df, num_cols, cat_cols, metrics):
    kpis = [
        {'id': 'rows',    'label': 'Total Rows',    'value': metrics.get('total_rows', len(df)),
         'icon': 'fa-list-ol',  'color': 'blue'},
        {'id': 'cols',    'label': 'Total Columns', 'value': metrics.get('total_columns', len(df.columns)),
         'icon': 'fa-columns',  'color': 'green'},
        {'id': 'missing', 'label': 'Missing Ratio', 'value': metrics.get('missing_pct', '0%'),
         'icon': 'fa-exclamation-circle', 'color': 'red'},
    ]

    if num_cols:
        col = num_cols[0]
        s0  = sanitize_series(df[col] if col in df.columns else pd.Series(dtype=float), col)
        kpis.append({
            'id': 'mean', 'label': f'Avg — {col}',
            'value': _fmt_num(s0.mean()) if not s0.empty else 'N/A',
            'icon': 'fa-chart-line', 'color': 'orange',
        })
        if len(num_cols) > 1:
            col2 = num_cols[1]
            s1   = sanitize_series(df[col2] if col2 in df.columns else pd.Series(dtype=float), col2)
            kpis.append({
                'id': 'std', 'label': f'Std — {col2}',
                'value': _fmt_num(s1.std()) if (not s1.empty and len(s1) >= 2) else 'N/A',
                'icon': 'fa-ruler-horizontal', 'color': 'purple',
            })
        elif cat_cols:
            kpis.append({
                'id': 'cat_count', 'label': 'Categorical Cols',
                'value': len(cat_cols),
                'icon': 'fa-font', 'color': 'purple',
            })
    elif cat_cols:
        col = cat_cols[0]
        kpis.append({
            'id': 'unique', 'label': f'Unique — {col}',
            'value': df[col].nunique(),
            'icon': 'fa-tags', 'color': 'orange',
        })
        kpis.append({
            'id': 'cat_count', 'label': 'Categorical Cols',
            'value': len(cat_cols),
            'icon': 'fa-font', 'color': 'purple',
        })

    return kpis[:5]


# ─── Stats preview builder ────────────────────────────────────────────────────

def build_stats_preview(df, num_cols, cat_cols):
    num_rows = []
    for col in num_cols[:8]:
        try:
            # Sanitize: force numeric conversion, drop NaN
            s = sanitize_series(df[col] if col in df.columns else pd.Series(dtype=float), col)
            if s.empty:
                continue

            # IQR outlier detection — safe subtraction
            outliers = 0
            iqr_result = safe_iqr_outliers(s)
            if iqr_result is not None:
                _, _, _, outliers = iqr_result

            num_rows.append({
                'col':      col,
                'mean':     round(float(s.mean()), 3),
                'median':   round(float(s.median()), 3),
                'std':      round(float(s.std()), 3) if len(s) >= 2 else 0.0,
                'min':      round(float(s.min()), 3),
                'max':      round(float(s.max()), 3),
                'outliers': outliers,
                'missing':  int(df[col].isna().sum()) if col in df.columns else 0,
            })
        except Exception as exc:
            print(f"[overview] stats_preview num col '{col}' error: {exc}")

    cat_rows = []
    for col in cat_cols[:6]:
        s = df[col].dropna()
        if s.empty:
            continue
        vc = s.value_counts()
        mode_val = str(vc.index[0]) if not vc.empty else 'N/A'
        mode_pct = round(vc.iloc[0] / len(s) * 100, 1) if not vc.empty else 0
        cat_rows.append({
            'col':      col,
            'unique':   int(s.nunique()),
            'mode':     mode_val[:30],
            'mode_pct': mode_pct,
            'missing':  int(df[col].isna().sum()),
        })

    return {'num': num_rows, 'cat': cat_rows}


# ─── Chart builders ──────────────────────────────────────────────────────────

def _build_pareto_charts(df, cat_cols):
    """
    Pareto Chart per kolom kategorik (toggle semua cat_cols).
    Identik dengan Visualizations > Categorical > Pareto Chart.
    Unik: menampilkan bar frekuensi + garis kumulatif 80/20.
    BERBEDA dari ov_center (Pie) dan ov_vbar_right (Bar Chart).
    Return: dict {col_name: chart_json}
    """
    if not cat_cols:
        return {}
    result = {}
    for col in cat_cols[:6]:
        chart = _safe(_chart_pareto, df, col)
        if chart:
            result[col] = chart
    return result


def _build_pie_charts(df, cat_cols):
    """
    Pie/Donut Chart per kolom kategorik (toggle semua cat_cols).
    Identik dengan Visualizations > Categorical > Donut / Pie Chart.
    Return: dict {col_name: chart_json}
    """
    if not cat_cols:
        return {}
    result = {}
    for col in cat_cols[:6]:
        chart = _safe(_chart_pie, df, col)
        if chart:
            result[col] = chart
    return result


def _build_scatter_charts(df, num_cols):
    """
    Scatter Plot dengan pasangan kolom X dan Y (toggle independent).
    Identik dengan Visualizations > Bivariate > Scatter Plot.
    Return: dict of dict { col_x: { col_y: chart_json } }
    Digunakan saat tidak ada dt_cols (fallback dari TS).
    """
    if len(num_cols) < 2:
        return {}
    result = {}
    cols = num_cols[:6]
    for i, cx in enumerate(cols):
        result[cx] = {}
        for j, cy in enumerate(cols):
            if cx == cy:
                continue
            chart = _safe(_chart_scatter, df, cx, cy)
            if chart:
                result[cx][cy] = chart
    return result


def _build_top_right_ts(df, num_cols, dt_cols):
    """
    Time-series line chart — hanya dipanggil jika dt_cols tersedia.
    Tidak ada toggle (TS bersifat fixed ke dt_col × num_col utama).
    Return: chart_json atau None
    """
    if not (dt_cols and num_cols):
        return None
    try:
        from backend.time_series import prepare_ts
        dt_col, num_col = dt_cols[0], num_cols[0]
        ts, freq_label = prepare_ts(df, dt_col, num_col)
        if ts is None or len(ts) < 4:
            return None
        x_vals = ts['ds'].astype(str).tolist()
        y_vals = ts['y'].tolist()
        fig = go.Figure(go.Scatter(
            x=x_vals, y=y_vals,
            mode='lines',
            line=dict(color=PALETTE[0], width=2),
            fill='tozeroy',
            fillcolor='rgba(78,205,196,0.12)',
            hovertemplate='%{x}<br>' + num_col + ': %{y:,.2f}<extra></extra>',
        ))
        fig.update_layout(_layout(
            title=f'Trend — {num_col} ({freq_label})',
            xaxis=dict(type='date'),
        ))
        _axes(fig)
        return _json(fig)
    except Exception as e:
        print(f"[overview] ts top_right error: {e}")
        return None


def _build_vbar_left_charts(df, num_cols):
    """
    Histogram per kolom numerik (toggle semua num_cols).
    Return: dict {col_name: chart_json}
    """
    if not num_cols:
        return {}
    result = {}
    for col in num_cols[:6]:
        chart = _safe(_chart_histogram, df, col)
        if chart:
            result[col] = chart
    return result


def _build_boxplot_charts(df, num_cols):
    """
    Box Plot per kolom numerik (toggle semua num_cols).
    Default kolom: num_cols[1] jika ada (beda dari histogram default).
    Return: dict {col_name: chart_json}
    """
    if not num_cols:
        return {}
    result = {}
    for col in num_cols[:6]:
        chart = _safe(_chart_boxplot, df, col)
        if chart:
            result[col] = chart
    return result


def _build_vbar_right_charts(df, cat_cols):
    """
    Bar Chart vertikal per kolom kategorik (toggle semua cat_cols).
    Return: dict {col_name: chart_json}
    """
    if not cat_cols:
        return {}
    result = {}
    for col in cat_cols[:6]:
        chart = _safe(_chart_bar, df, col)
        if chart:
            result[col] = chart
    return result


# ─── Toggle data builder helper ──────────────────────────────────────────────

def _make_toggle(charts_dict, default_col):
    if not charts_dict:
        return None
    keys    = list(charts_dict.keys())
    default = default_col if default_col in charts_dict else keys[0]
    return {
        'options': keys,
        'default': default,
        'charts' : charts_dict,
    }


# ─── MAIN ENTRY POINT ────────────────────────────────────────────────────────

def generate_overview_dashboard(df, num_cols, cat_cols, dt_cols=None, metrics=None):
    """
    Bangun payload lengkap untuk tab Dashboard Overview.
    """
    dt_cols = dt_cols or []
    metrics = metrics or {}

    result = {
        'kpis'         : build_overview_kpis(df, num_cols, cat_cols, metrics),
        'slots'        : {},
        'toggle_data'  : {},
        'viz_links'    : {},
        'stats_preview': build_stats_preview(df, num_cols, cat_cols),
    }

    def _slot(key, chart_json, title, viz_tab, viz_sub=None):
        result['slots'][key] = {
            'visible': chart_json is not None,
            'title'  : title,
            'chart'  : chart_json,
        }
        result['viz_links'][key] = {
            'tab': viz_tab,
            'sub': viz_sub or 'numerical',
        }

    def _reg(key, charts_dict, default_col):
        td = _make_toggle(charts_dict, default_col)
        if td:
            result['toggle_data'][key] = td

    # ══════════════════════════════════════════════════════════════════
    # BARIS TENGAH
    # ══════════════════════════════════════════════════════════════════

    # ov_hbar: Pareto Chart — toggle semua cat_cols
    pareto_charts = _build_pareto_charts(df, cat_cols)
    default_cat0  = cat_cols[0] if cat_cols else ''
    _reg('ov_hbar', pareto_charts, default_cat0)
    _slot('ov_hbar',
          pareto_charts.get(default_cat0) if pareto_charts else None,
          title   = f'Pareto — {default_cat0}' if default_cat0 else '',
          viz_tab = 'visualizations',
          viz_sub = 'categorical')

    # ov_center: Pie/Donut — toggle semua cat_cols
    pie_charts = _build_pie_charts(df, cat_cols)
    _reg('ov_center', pie_charts, default_cat0)
    _slot('ov_center',
          pie_charts.get(default_cat0) if pie_charts else None,
          title   = f'Composition — {default_cat0}' if default_cat0 else '',
          viz_tab = 'visualizations',
          viz_sub = 'categorical')

    # ov_top_right: TS (fixed) → Scatter (toggle X & Y) → SKIP
    has_ts = bool(dt_cols and num_cols)
    if has_ts:
        # TS: chart tunggal, tidak ada toggle kolom
        ts_chart = _build_top_right_ts(df, num_cols, dt_cols)
        _slot('ov_top_right', ts_chart,
              title   = f'Trend — {num_cols[0]}' if ts_chart and num_cols else '',
              viz_tab = 'timeseries',
              viz_sub = None)
        # Tidak perlu toggle_data untuk slot ini (TS fixed)
    elif len(num_cols) >= 2:
        # Scatter dengan toggle X dan Y terpisah
        scatter_charts = _build_scatter_charts(df, num_cols)
        default_x      = num_cols[0]
        default_y      = num_cols[1]
        # Struktur toggle khusus scatter: nested { col_x: { col_y: chart } }
        default_chart  = (scatter_charts.get(default_x) or {}).get(default_y)
        result['toggle_data']['ov_top_right'] = {
            'type'    : 'scatter',          # penanda untuk JS
            'options_x': list(scatter_charts.keys()),
            'options_y': num_cols[:6],
            'default_x': default_x,
            'default_y': default_y,
            'charts'   : scatter_charts,    # nested dict
        }
        _slot('ov_top_right', default_chart,
              title   = f'Scatter — {default_x} × {default_y}' if default_chart else '',
              viz_tab = 'visualizations',
              viz_sub = 'bivariate')
    else:
        _slot('ov_top_right', None, '', 'visualizations', 'bivariate')

    # ══════════════════════════════════════════════════════════════════
    # BARIS BAWAH
    # ══════════════════════════════════════════════════════════════════

    # ov_vbar_left: Histogram + toggle semua num_cols
    vbar_left = _build_vbar_left_charts(df, num_cols)
    default_num0 = num_cols[0] if num_cols else ''
    _reg('ov_vbar_left', vbar_left, default_num0)
    _slot('ov_vbar_left',
          vbar_left.get(default_num0) if vbar_left else None,
          title   = f'Distribution — {default_num0}' if default_num0 else '',
          viz_tab = 'visualizations',
          viz_sub = 'numerical')

    # ov_area_bottom: Boxplot + toggle semua num_cols
    # Default: num_cols[1] jika ada (beda dari histogram default di vbar_left)
    boxplot_charts = _build_boxplot_charts(df, num_cols)
    default_num1   = num_cols[1] if len(num_cols) >= 2 else default_num0
    _reg('ov_area_bottom', boxplot_charts, default_num1)
    _slot('ov_area_bottom',
          boxplot_charts.get(default_num1) if boxplot_charts else None,
          title   = f'Spread — {default_num1}' if default_num1 else '',
          viz_tab = 'visualizations',
          viz_sub = 'numerical')

    # ov_vbar_right: Bar Chart + toggle semua cat_cols
    vbar_right = _build_vbar_right_charts(df, cat_cols)
    _reg('ov_vbar_right', vbar_right, default_cat0)
    _slot('ov_vbar_right',
          vbar_right.get(default_cat0) if vbar_right else None,
          title   = f'Frequency — {default_cat0}' if default_cat0 else '',
          viz_tab = 'visualizations',
          viz_sub = 'categorical')

    return result