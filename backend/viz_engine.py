"""
backend/viz_engine.py
Master Visualization Engine — 1 chart per view, dark pastel theme, dynamic columns.

FIX (bdata prevention):
  Semua array numerik/kategorik yang di-pass ke Plotly trace dikonversi ke
  plain Python list via .tolist() SEBELUM masuk go.* constructor.
  Ini mencegah Plotly men-serialize array sebagai bdata (base64 binary),
  yang tidak bisa di-decode oleh dashboardOverview.js karena chart di-embed
  langsung di HTML (bukan via AJAX).

  Chart yang di-render via AJAX (VizMaster) sudah punya decode di JS,
  tapi chart Overview di-embed via {{ overview | tojson }} — tidak ada
  decode step, sehingga bdata tampil sebagai angka salah/kosong.

  Solusi universal: hilangkan bdata dari sumbernya.
"""

import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats as scipy_stats
from backend.data_sanitizer import sanitize_series, filter_numeric_cols

# ─── High Visual Dark Palette ────────────────────────────────────────────────
PALETTE = ['#4ECDC4', '#7EA9FF', '#A8E6CF', '#C9B8FF', '#88D4E8', '#F4A9C8']
BG_CONTAINER = '#111A40'
PLOT_BG      = '#172254'
GRID         = 'rgba(255,255,255,0.06)'
AXIS_LINE    = 'rgba(255,255,255,0.12)'
FONT_COLOR   = '#C8D8F0'

# ─── All category→chart-type lists (SINGLE SOURCE OF TRUTH) ──────────────────
CATEGORY_CHARTS = {
    'numerical'  : ['histogram', 'boxplot', 'density', 'qq', 'violin'],
    'categorical': ['bar', 'pie', 'count', 'pareto'],
    'bivariate'  : ['scatter', 'heatmap', 'scatter_matrix', 'regression_plot', 'bubble_chart'],
    'catnum'     : ['box_cat_num', 'violin_cat_num', 'grouped_bar', 'strip_plot'],
    'compare'    : ['violin_compare', 'grouped_bar_compare', 'parallel_coords'],
}

CHART_LABELS = {
    'histogram'           : 'Histogram + KDE',
    'boxplot'             : 'Box Plot',
    'density'             : 'Density Plot (KDE)',
    'qq'                  : 'QQ Plot — Normality',
    'violin'              : 'Violin Plot',
    'bar'                 : 'Bar Chart',
    'pie'                 : 'Donut / Pie Chart',
    'count'               : 'Count Plot',
    'pareto'              : 'Pareto Chart',
    'scatter'             : 'Scatter Plot',
    'heatmap'             : 'Correlation Heatmap',
    'scatter_matrix'      : 'Pair Plot / Scatter Matrix',
    'regression_plot'     : 'Regression + 95% CI',
    'bubble_chart'        : 'Bubble Chart',
    'box_cat_num'         : 'Boxplot by Category',
    'violin_cat_num'      : 'Violin by Category',
    'grouped_bar'         : 'Grouped Bar Chart',
    'strip_plot'          : 'Strip Plot',
    'violin_compare'      : 'Violin Comparison',
    'grouped_bar_compare' : 'Mean ± Std Comparison',
    'parallel_coords'     : 'Parallel Coordinates',
}

PLACEHOLDERS = {
    'numerical'  : 'Gunakan dataset dengan minimal 1 kolom numerik untuk mengaktifkan halaman ini.',
    'categorical': 'Gunakan dataset dengan kolom kategorik untuk mengaktifkan halaman ini.',
    'bivariate'  : 'Gunakan dataset dengan minimal 2 kolom numerik untuk mengaktifkan halaman ini.',
    'catnum'     : 'Gunakan dataset dengan kolom numerik dan kategorik untuk mengaktifkan halaman ini.',
    'compare'    : 'Gunakan dataset dengan minimal 2 kolom numerik untuk perbandingan.',
}


def category_available(category, num_cols, cat_cols):
    n, c = len(num_cols), len(cat_cols)
    checks = {
        'numerical'  : n >= 1,
        'categorical': c >= 1,
        'bivariate'  : n >= 2,
        'catnum'     : n >= 1 and c >= 1,
        'compare'    : n >= 2,
    }
    return checks.get(category, False)


# ─── Layout helpers ───────────────────────────────────────────────────────────

def _layout(**extra):
    base = dict(
        paper_bgcolor = BG_CONTAINER,
        plot_bgcolor  = PLOT_BG,
        font          = dict(color=FONT_COLOR, family='Inter, sans-serif', size=12),
        margin        = dict(l=52, r=28, t=56, b=56),
        hoverlabel    = dict(
            bgcolor     = 'rgba(17,26,64,0.95)',
            bordercolor = 'rgba(126,169,255,0.4)',
            font        = dict(color='#E8F0FF', size=12),
        ),
        legend = dict(
            bgcolor     = 'rgba(17,26,64,0.6)',
            bordercolor = 'rgba(255,255,255,0.08)',
            font        = dict(color=FONT_COLOR, size=11),
        ),
    )
    base.update(extra)
    return base


def _axes(fig):
    style = dict(
        gridcolor     = GRID,
        zerolinecolor = GRID,
        linecolor     = AXIS_LINE,
        tickfont      = dict(color=FONT_COLOR, size=10),
        title_font    = dict(color=FONT_COLOR, size=11),
    )
    fig.update_xaxes(**style)
    fig.update_yaxes(**style)
    return fig


def _json(fig):
    return json.loads(fig.to_json())


def _to_list(arr):
    """
    Konversi numpy array / pandas Series ke plain Python list.
    Ini WAJIB sebelum passing ke Plotly trace agar tidak di-encode
    sebagai bdata (base64 binary) dalam JSON output.
    """
    if arr is None:
        return []
    if isinstance(arr, (np.ndarray,)):
        return arr.tolist()
    if isinstance(arr, pd.Series):
        return arr.tolist()
    if hasattr(arr, 'tolist'):
        return arr.tolist()
    return list(arr)


# ─── KPI builders ────────────────────────────────────────────────────────────

def _kpis_numeric(series, col_name):
    s = series.dropna()
    if s.empty:
        return []
    return [
        {'label': 'Mean',    'value': f'{s.mean():,.2f}',  'icon': 'fa-calculator'},
        {'label': 'Median',  'value': f'{s.median():,.2f}','icon': 'fa-chart-line'},
        {'label': 'Std Dev', 'value': f'{s.std():,.2f}',   'icon': 'fa-ruler'},
        {'label': 'Min',     'value': f'{s.min():,.2f}',   'icon': 'fa-arrow-down'},
        {'label': 'Max',     'value': f'{s.max():,.2f}',   'icon': 'fa-arrow-up'},
    ]


def _kpis_categorical(series, col_name):
    s  = series.dropna()
    if s.empty:
        return []
    vc   = s.value_counts()
    mode = str(vc.index[0]) if not vc.empty else 'N/A'
    return [
        {'label': 'Unique',   'value': str(s.nunique()),                               'icon': 'fa-tags'},
        {'label': 'Mode',     'value': mode[:18],                                      'icon': 'fa-star'},
        {'label': 'Top Freq', 'value': str(int(vc.iloc[0])) if not vc.empty else '0', 'icon': 'fa-hashtag'},
        {'label': 'Missing',  'value': str(int(series.isna().sum())),                  'icon': 'fa-exclamation'},
        {'label': 'Rows',     'value': f'{len(series):,}',                             'icon': 'fa-list'},
    ]


def _kpis_bivariate(df, col_x, col_y):
    clean = df[[col_x, col_y]].dropna()
    if len(clean) < 2:
        return _kpis_numeric(df[col_x], col_x)[:5]
    r = clean[col_x].corr(clean[col_y])
    return [
        {'label': 'Correlation',        'value': f'{r:.3f}',                    'icon': 'fa-link'},
        {'label': 'Pairs',              'value': f'{len(clean):,}',             'icon': 'fa-circle-dot'},
        {'label': f'Mean {col_x[:12]}', 'value': f'{clean[col_x].mean():,.2f}', 'icon': 'fa-calculator'},
        {'label': f'Mean {col_y[:12]}', 'value': f'{clean[col_y].mean():,.2f}', 'icon': 'fa-chart-bar'},
        {'label': 'R²',                 'value': f'{r**2:.3f}',                 'icon': 'fa-square-root-alt'},
    ]


def build_kpis(category, df, col_x=None, col_y=None, num_cols=None):
    if category == 'numerical' and col_x:
        return _kpis_numeric(df[col_x], col_x)
    if category == 'categorical' and col_x:
        return _kpis_categorical(df[col_x], col_x)
    if category == 'bivariate' and col_x and col_y:
        return _kpis_bivariate(df, col_x, col_y)
    if category == 'catnum' and col_x and col_y:
        return [
            {'label': 'Groups',             'value': str(df[col_x].nunique()),   'icon': 'fa-layer-group'},
            {'label': f'Mean {col_y[:12]}', 'value': f'{df[col_y].mean():,.2f}', 'icon': 'fa-calculator'},
            {'label': 'Std',                'value': f'{df[col_y].std():,.2f}',  'icon': 'fa-ruler'},
            {'label': 'Rows',               'value': f'{len(df):,}',             'icon': 'fa-list'},
            {'label': 'Missing',            'value': str(int(df[[col_x, col_y]].isna().any(axis=1).sum())), 'icon': 'fa-exclamation'},
        ]
    if category == 'compare' and num_cols:
        return [
            {'label': 'Variables', 'value': str(len(num_cols)),                    'icon': 'fa-hashtag'},
            {'label': 'Rows',      'value': f'{len(df):,}',                        'icon': 'fa-list'},
            {'label': 'Cols',      'value': str(len(df.columns)),                  'icon': 'fa-columns'},
            {'label': 'Numeric',   'value': str(len(num_cols)),                    'icon': 'fa-chart-bar'},
            {'label': 'Complete',  'value': f'{df[num_cols].dropna().shape[0]:,}', 'icon': 'fa-check'},
        ]
    return []


# ─── a) NUMERICAL ────────────────────────────────────────────────────────────

def _chart_histogram(df, col):
    raw   = df[col] if col in df.columns else pd.Series(dtype=float)
    clean = sanitize_series(raw, col)   # forced numeric conversion
    if clean.empty:
        return None
    fig   = go.Figure()
    # FIX: .tolist() prevents bdata encoding
    fig.add_trace(go.Histogram(
        x=_to_list(clean), nbinsx=30,
        marker_color=PALETTE[0], opacity=0.85, name=col,
        hovertemplate='%{x}<br>Count: %{y}<extra></extra>',
    ))
    if len(clean) >= 3:
        try:
            kde_x = np.linspace(float(clean.min()), float(clean.max()), 200)
            kde   = scipy_stats.gaussian_kde(clean)
            scale = len(clean) * (float(clean.max()) - float(clean.min())) / 30
            # FIX: .tolist() on both kde_x and kde values
            fig.add_trace(go.Scatter(
                x=kde_x.tolist(), y=(kde(kde_x) * scale).tolist(),
                mode='lines', name='KDE',
                line=dict(color=PALETTE[1], width=2.5),
                hovertemplate='%{x:.2f}<br>Density: %{y:.4f}<extra></extra>',
            ))
        except Exception:
            pass  # KDE failed (e.g. constant data), skip overlay
    fig.update_layout(_layout(title=f' {CHART_LABELS["histogram"]}: {col}'))
    return _json(_axes(fig))


def _chart_boxplot(df, col):
    clean = sanitize_series(df[col] if col in df.columns else pd.Series(dtype=float), col)
    if clean.empty:
        return None
    fig = go.Figure(go.Box(
        y=_to_list(clean), name=col,
        marker_color=PALETTE[0],
        boxmean='sd', line_color=PALETTE[1],
        hovertemplate=f'{col}: %{{y:.2f}}<extra></extra>',
    ))
    fig.update_layout(_layout(title=f' {CHART_LABELS["boxplot"]}: {col}'))
    return _json(_axes(fig))


def _chart_density(df, col):
    clean = sanitize_series(df[col] if col in df.columns else pd.Series(dtype=float), col)
    if len(clean) < 3:
        return None
    try:
        kde_x = np.linspace(float(clean.min()), float(clean.max()), 300)
        kde   = scipy_stats.gaussian_kde(clean)
        fig   = go.Figure(go.Scatter(
            x=kde_x.tolist(), y=(kde(kde_x)).tolist(),
            fill='tozeroy', mode='lines',
            line=dict(color=PALETTE[0], width=2.5),
            fillcolor='rgba(78,205,196,0.18)', name=col,
            hovertemplate='%{x:.2f}<br>Density: %{y:.4f}<extra></extra>',
        ))
        fig.update_layout(_layout(title=f' {CHART_LABELS["density"]}: {col}'))
        return _json(_axes(fig))
    except Exception:
        return None


def _chart_qq(df, col):
    clean = sanitize_series(df[col] if col in df.columns else pd.Series(dtype=float), col)
    if len(clean) < 4:
        return None
    try:
        clean_arr = clean.values
        (osm, osr), (slope, intercept, _) = scipy_stats.probplot(clean_arr, dist='norm')
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=osm.tolist(), y=osr.tolist(), mode='markers',
            marker=dict(color=PALETTE[1], size=5, opacity=0.7),
            name='Data Points',
            hovertemplate='Theoretical: %{x:.3f}<br>Sample: %{y:.3f}<extra></extra>',
        ))
        x_line = np.array([osm.min(), osm.max()])
        fig.add_trace(go.Scatter(
            x=x_line.tolist(), y=(slope * x_line + intercept).tolist(),
            mode='lines', name='Normal Reference',
            line=dict(color=PALETTE[2], dash='dash', width=2),
        ))
        fig.update_layout(_layout(
            title=f' {CHART_LABELS["qq"]}: {col}',
            xaxis_title='Theoretical Quantiles',
            yaxis_title='Sample Quantiles',
        ))
        return _json(_axes(fig))
    except Exception:
        return None


def _chart_violin(df, col):
    clean = sanitize_series(df[col] if col in df.columns else pd.Series(dtype=float), col)
    if clean.empty:
        return None
    fig = go.Figure(go.Violin(
        y=_to_list(clean), name=col,
        fillcolor=PALETTE[0], line_color=PALETTE[1],
        box_visible=True, meanline_visible=True, opacity=0.8,
        hovertemplate=f'{col}: %{{y:.2f}}<extra></extra>',
    ))
    fig.update_layout(_layout(title=f' {CHART_LABELS["violin"]}: {col}'))
    return _json(_axes(fig))


# ─── b) CATEGORICAL ──────────────────────────────────────────────────────────

def _chart_bar(df, col):
    vc  = df[col].value_counts().head(12)
    fig = go.Figure(go.Bar(
        x=vc.index.astype(str).tolist(),
        y=vc.values.tolist(),          # FIX: .tolist()
        marker_color=PALETTE[0], opacity=0.9,
        hovertemplate='%{x}<br>Count: %{y:,}<extra></extra>',
    ))
    fig.update_layout(_layout(title=f' {CHART_LABELS["bar"]}: {col}'))
    return _json(_axes(fig))


def _chart_pie(df, col):
    # Guard: jika nunique > 5, fallback ke Bar Chart (Pie berantakan)
    if df[col].nunique() > 5:
        return _chart_bar(df, col)
    
    vc  = df[col].value_counts().head(10)
    fig = go.Figure(go.Pie(
        labels=vc.index.astype(str).tolist(),
        values=vc.values.tolist(),     # FIX: .tolist()
        hole=0.45,
        marker_colors=PALETTE,
        textfont=dict(color=FONT_COLOR),
        hovertemplate='%{label}<br>Count: %{value:,}<br>%{percent}<extra></extra>',
    ))
    fig.update_layout(_layout(title=f' {CHART_LABELS["pie"]}: {col}'))
    return _json(fig)


def _chart_count(df, col):
    vc  = df[col].value_counts().head(15).sort_values()
    fig = go.Figure(go.Bar(
        x=vc.values.tolist(),          # FIX: .tolist()
        y=vc.index.astype(str).tolist(),
        orientation='h',
        marker_color=PALETTE[2], opacity=0.9,
        hovertemplate='%{y}<br>Count: %{x:,}<extra></extra>',
    ))
    fig.update_layout(_layout(title=f' {CHART_LABELS["count"]}: {col}'))
    return _json(_axes(fig))


def _chart_pareto(df, col):
    vc  = df[col].value_counts().head(12)
    cum = (vc.cumsum() / vc.sum() * 100)
    x_labels = vc.index.astype(str).tolist()
    fig = make_subplots(specs=[[{'secondary_y': True}]])
    fig.add_trace(go.Bar(
        x=x_labels,
        y=vc.values.tolist(),          # FIX: .tolist()
        marker_color=PALETTE[0], opacity=0.85,
        name='Count',
        hovertemplate='%{x}<br>Count: %{y:,}<extra></extra>',
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=cum.tolist(),                # FIX: .tolist()
        mode='lines+markers',
        line=dict(color=PALETTE[3], width=2.5),
        name='Cumulative %',
        hovertemplate='%{x}<br>Cumulative: %{y:.1f}%<extra></extra>',
    ), secondary_y=True)
    fig.add_hline(y=80, line_dash='dash', line_color=PALETTE[2],
                  annotation_text='80%', secondary_y=True)
    fig.update_yaxes(title_text='Count',        secondary_y=False)
    fig.update_yaxes(title_text='Cumulative %', secondary_y=True, range=[0, 105])
    fig.update_layout(_layout(title=f' {CHART_LABELS["pareto"]}: {col} (80/20 Rule)'))
    return _json(_axes(fig))


# ─── c) BIVARIATE ────────────────────────────────────────────────────────────

def _chart_scatter(df, col_x, col_y):
    clean = df[[col_x, col_y]].dropna()
    fig = go.Figure(go.Scatter(
        x=_to_list(clean[col_x]),
        y=_to_list(clean[col_y]),
        mode='markers',
        marker=dict(color=PALETTE[0], size=6, opacity=0.65),
        hovertemplate=f'{col_x}: %{{x:.2f}}<br>{col_y}: %{{y:.2f}}<extra></extra>',
    ))
    fig.update_layout(_layout(
        title=f' {CHART_LABELS["scatter"]}: {col_x} vs {col_y}',
        xaxis_title=col_x,
        yaxis_title=col_y,
    ))
    return _json(_axes(fig))


def _chart_heatmap(df, num_cols):
    """
    Correlation heatmap — only valid numeric cols enter df.corr().
    FIX: filter_numeric_cols guards against TypeError in df.corr().
    """
    # Safe: keep only truly numeric, non-empty, non-constant columns
    valid_cols = filter_numeric_cols(df, num_cols[:12])
    if len(valid_cols) < 2:
        return None
    try:
        # Work on coerced copy to handle any remaining string-encoded numbers
        from backend.data_sanitizer import sanitize_df_numeric_cols
        df2  = sanitize_df_numeric_cols(df, valid_cols)
        corr = df2[valid_cols].corr()
        z_values = corr.values.tolist()
        z_text   = [[f'{v:.2f}' if not (isinstance(v, float) and (v != v)) else 'N/A'
                     for v in row] for row in corr.values.tolist()]
        col_list = corr.columns.tolist()

        fig = go.Figure(go.Heatmap(
            z=z_values,
            x=col_list,
            y=col_list,
            colorscale=[[0, PLOT_BG], [0.5, PALETTE[1]], [1, PALETTE[0]]],
            zmid=0,
            text=z_text,
            texttemplate='%{text}',
            hovertemplate='%{x} × %{y}<br>r = %{z:.3f}<extra></extra>',
        ))
        fig.update_layout(_layout(title=f' {CHART_LABELS["heatmap"]}'))
        return _json(fig)
    except Exception as exc:
        print(f"[viz_engine] heatmap error: {exc}")
        return None


def _chart_scatter_matrix(df, num_cols):
    cols = num_cols[:5]
    df_s = df[cols].dropna()
    if df_s.empty:
        return None
    fig = px.scatter_matrix(
        df_s, dimensions=cols,
        color_discrete_sequence=PALETTE,
        title=f' {CHART_LABELS["scatter_matrix"]}',
    )
    fig.update_traces(
        diagonal_visible=False,
        marker=dict(size=3, opacity=0.55),
        hovertemplate='%{xaxis.title.text}: %{x:.2f}<br>%{yaxis.title.text}: %{y:.2f}<extra></extra>',
    )
    fig.update_layout(_layout())
    return _json(fig)


def _chart_regression_plot(df, col_x, col_y):
    if col_x == col_y:
        return _chart_scatter(df, col_x, col_y)

    df_r = df[[col_x, col_y]].dropna()
    if len(df_r) < 4:
        return None
    if df_r[col_x].nunique() < 2:
        return _chart_scatter(df, col_x, col_y)

    slope, intercept, r, p, se = scipy_stats.linregress(df_r[col_x], df_r[col_y])

    x_line = np.linspace(float(df_r[col_x].min()), float(df_r[col_x].max()), 200)
    y_line = slope * x_line + intercept

    n   = len(df_r)
    t_c = scipy_stats.t.ppf(0.975, df=n - 2)
    x_m = df_r[col_x].mean()
    s_e = np.sqrt(np.sum((df_r[col_y] - (slope * df_r[col_x] + intercept)) ** 2) / (n - 2))
    ci  = t_c * s_e * np.sqrt(1/n + (x_line - x_m)**2 / np.sum((df_r[col_x] - x_m)**2))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=_to_list(df_r[col_x]), y=_to_list(df_r[col_y]),
        mode='markers', name='Data',
        marker=dict(color=PALETTE[0], size=6, opacity=0.6),
        hovertemplate=f'{col_x}: %{{x:.2f}}<br>{col_y}: %{{y:.2f}}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=x_line.tolist(), y=y_line.tolist(),
        mode='lines', name=f'OLS (R²={r**2:.3f})',
        line=dict(color=PALETTE[3], width=2.5),
    ))
    ci_x = np.concatenate([x_line, x_line[::-1]])
    ci_y = np.concatenate([y_line + ci, (y_line - ci)[::-1]])
    fig.add_trace(go.Scatter(
        x=ci_x.tolist(), y=ci_y.tolist(),
        fill='toself', fillcolor='rgba(238,93,80,0.10)',
        line=dict(color='rgba(0,0,0,0)'),
        name='95% CI',
    ))
    fig.update_layout(_layout(
        title=f' {CHART_LABELS["regression_plot"]}: {col_x} → {col_y} | R²={r**2:.3f}',
        xaxis_title=col_x,
        yaxis_title=col_y,
    ))
    return _json(_axes(fig))


def _chart_bubble_chart(df, col_x, col_y, col_z):
    df_b = df[[col_x, col_y, col_z]].dropna()
    if df_b.empty:
        return None
    size_range = float(df_b[col_z].max()) - float(df_b[col_z].min())
    if size_range == 0:
        size_scaled = [20] * len(df_b)
    else:
        size_scaled = ((df_b[col_z] - df_b[col_z].min()) / size_range * 35 + 5).tolist()
    fig = go.Figure(go.Scatter(
        x=_to_list(df_b[col_x]), y=_to_list(df_b[col_y]),
        mode='markers',
        marker=dict(
            size=size_scaled,
            color=PALETTE[0], opacity=0.65,
            line=dict(width=0.5, color='white'),
            sizemode='diameter',
        ),
        hovertemplate=f'{col_x}: %{{x:.2f}}<br>{col_y}: %{{y:.2f}}<br>{col_z}: %{{marker.size:.1f}}<extra></extra>',
    ))
    fig.update_layout(_layout(
        title=f' {CHART_LABELS["bubble_chart"]}: {col_x} × {col_y} (size={col_z})',
        xaxis_title=col_x,
        yaxis_title=col_y,
    ))
    return _json(_axes(fig))


# ─── d) CATEGORICAL vs NUMERICAL ─────────────────────────────────────────────

def _chart_box_cat_num(df, cat_col, num_col):
    top = df[cat_col].value_counts().head(8).index
    sub = df[df[cat_col].isin(top)]
    fig = px.box(
        sub, x=cat_col, y=num_col, color=cat_col,
        color_discrete_sequence=PALETTE,
        title=f' {CHART_LABELS["box_cat_num"]}: {num_col} by {cat_col}',
        points='outliers',
    )
    fig.update_layout(_layout(showlegend=False))
    return _json(_axes(fig))


def _chart_violin_cat_num(df, cat_col, num_col):
    top = df[cat_col].value_counts().head(8).index
    sub = df[df[cat_col].isin(top)]
    fig = px.violin(
        sub, x=cat_col, y=num_col, color=cat_col,
        color_discrete_sequence=PALETTE, box=True, points='outliers',
        title=f' {CHART_LABELS["violin_cat_num"]}: {num_col} by {cat_col}',
    )
    fig.update_layout(_layout(showlegend=False))
    return _json(_axes(fig))


def _chart_grouped_bar(df, cat_col, num_col):
    grp = df.groupby(cat_col)[num_col].mean().head(12).sort_values(ascending=False)
    fig = go.Figure(go.Bar(
        x=grp.index.astype(str).tolist(),
        y=grp.values.tolist(),         # FIX: .tolist()
        marker_color=PALETTE[1], opacity=0.9,
        hovertemplate='%{x}<br>Mean: %{y:,.2f}<extra></extra>',
    ))
    fig.update_layout(_layout(title=f' {CHART_LABELS["grouped_bar"]}: Mean {num_col} by {cat_col}'))
    return _json(_axes(fig))


def _chart_strip_plot(df, cat_col, num_col):
    top = df[cat_col].value_counts().head(10).index
    sub = df[df[cat_col].isin(top)]
    fig = px.strip(
        sub, x=cat_col, y=num_col,
        color_discrete_sequence=[PALETTE[0]],
        title=f' {CHART_LABELS["strip_plot"]}: {num_col} by {cat_col}',
    )
    fig.update_layout(_layout(showlegend=False))
    return _json(_axes(fig))


# ─── e) COMPARISON ───────────────────────────────────────────────────────────

def _chart_violin_compare(df, num_cols):
    cols = [c for c in num_cols if c in df.columns]
    if not cols:
        return None
    fig = go.Figure()
    for i, col in enumerate(cols[:8]):
        fig.add_trace(go.Violin(
            y=_to_list(df[col].dropna()), name=col,
            line_color=PALETTE[i % len(PALETTE)],
            fillcolor=PALETTE[i % len(PALETTE)],
            opacity=0.75, box_visible=True, meanline_visible=True,
            hovertemplate=f'{col}: %{{y:.2f}}<extra></extra>',
        ))
    suffix = ', '.join(cols[:4]) + ('…' if len(cols) > 4 else '')
    fig.update_layout(_layout(title=f' {CHART_LABELS["violin_compare"]} — {suffix}'))
    return _json(_axes(fig))


def _chart_grouped_bar_compare(df, num_cols):
    cols = [c for c in num_cols if c in df.columns][:10]
    if not cols:
        return None
    means = []
    stds  = []
    valid_cols = []
    for c in cols:
        try:
            s = sanitize_series(df[c], c)
            if not s.empty:
                means.append(float(s.mean()))
                stds.append(float(s.std()) if len(s) >= 2 else 0.0)
                valid_cols.append(c)
        except Exception:
            pass
    if not valid_cols:
        return None
    suffix = ', '.join(valid_cols[:4]) + ('…' if len(valid_cols) > 4 else '')
    fig = go.Figure(go.Bar(
        x=valid_cols, y=means,
        error_y=dict(
            type='data', array=stds, visible=True,
            color='rgba(200,216,240,0.6)', thickness=1.5, width=6,
        ),
        marker_color=PALETTE[0], opacity=0.9,
        hovertemplate='%{x}<br>Mean: %{y:,.3f}<extra></extra>',
    ))
    fig.update_layout(_layout(title=f' {CHART_LABELS["grouped_bar_compare"]} — {suffix}'))
    return _json(_axes(fig))


def _chart_parallel_coords(df, num_cols):
    cols = [c for c in num_cols if c in df.columns][:6]
    if not cols:
        return None
    sub  = df[cols].dropna()
    if sub.empty:
        return None
    sub  = sub.sample(min(500, len(sub)), random_state=42)
    dims = [dict(label=c, values=sub[c].tolist()) for c in cols]
    color_vals = list(range(len(sub)))
    fig = go.Figure(go.Parcoords(
        line=dict(
            color=color_vals,
            colorscale=[[0, PALETTE[0]], [0.5, PALETTE[4]], [1, PALETTE[3]]],
            showscale=True,
            colorbar=dict(title='Index', thickness=12, tickfont=dict(color=FONT_COLOR, size=9)),
        ),
        dimensions=dims,
        unselected=dict(line=dict(opacity=0.15)),
    ))
    fig.update_layout(_layout(title=f' {CHART_LABELS["parallel_coords"]} — Multivariable Pattern'))
    return _json(fig)


def _chart_all_numerical(df, num_cols, chart_type):
    import math
    cols_to_plot = [c for c in num_cols if c in df.columns]
    n_cols = len(cols_to_plot)
    if n_cols == 0:
        return None
    
    n_plot_cols = 2 if n_cols > 1 else 1
    n_plot_rows = math.ceil(n_cols / n_plot_cols)
    
    fig = make_subplots(
        rows=n_plot_rows, cols=n_plot_cols,
        subplot_titles=cols_to_plot,
        vertical_spacing=0.15 / max(1, n_plot_rows - 1) if n_plot_rows > 1 else 0.1,
    )
    
    for i, col in enumerate(cols_to_plot):
        r = (i // n_plot_cols) + 1
        c = (i % n_plot_cols) + 1
        clean = df[col].dropna()
        if clean.empty:
            continue
        
        color = PALETTE[i % len(PALETTE)]
        
        if chart_type == 'boxplot':
            fig.add_trace(go.Box(
                y=_to_list(clean), name=col,
                marker_color=color, boxmean='sd',
                hovertemplate=f'{col}: %{{y:.2f}}<extra></extra>',
            ), row=r, col=c)
        elif chart_type == 'violin':
            fig.add_trace(go.Violin(
                y=_to_list(clean), name=col,
                fillcolor=color, line_color=color,
                box_visible=True, meanline_visible=True, opacity=0.8,
                hovertemplate=f'{col}: %{{y:.2f}}<extra></extra>',
            ), row=r, col=c)
        elif chart_type == 'density':
            if len(clean) >= 3:
                kde_x = np.linspace(float(clean.min()), float(clean.max()), 100)
                kde = scipy_stats.gaussian_kde(clean)
                fig.add_trace(go.Scatter(
                    x=kde_x.tolist(), y=(kde(kde_x)).tolist(),
                    fill='tozeroy', mode='lines',
                    line=dict(color=color, width=2),
                    name=col,
                    hovertemplate='%{x:.2f}<br>Density: %{y:.4f}<extra></extra>',
                ), row=r, col=c)
        elif chart_type == 'qq':
            if len(clean) >= 4:
                (osm, osr), (slope, intercept, _) = scipy_stats.probplot(clean, dist='norm')
                fig.add_trace(go.Scatter(
                    x=osm.tolist(), y=osr.tolist(), mode='markers',
                    marker=dict(color=color, size=4, opacity=0.6),
                    name=f'{col} Points',
                    showlegend=False,
                ), row=r, col=c)
                x_line = np.array([osm.min(), osm.max()])
                fig.add_trace(go.Scatter(
                    x=x_line.tolist(), y=(slope * x_line + intercept).tolist(),
                    mode='lines', line=dict(color='#FF7A00', dash='dash', width=1.5),
                    name=f'{col} Ref',
                    showlegend=False,
                ), row=r, col=c)
        else: # default histogram
            fig.add_trace(go.Histogram(
                x=_to_list(clean), nbinsx=20,
                marker_color=color, opacity=0.8, name=col,
                hovertemplate='%{x}<br>Count: %{y}<extra></extra>',
            ), row=r, col=c)
            
    height = max(450, n_plot_rows * 300)
    fig.update_layout(_layout(
        title=f' Visualisasi Semua Variabel Numerik ({CHART_LABELS.get(chart_type, chart_type)})',
        height=height,
        showlegend=False,
    ))
    return _json(_axes(fig))


def _chart_all_categorical(df, cat_cols, chart_type):
    import math
    cols_to_plot = [c for c in cat_cols if c in df.columns]
    n_cols = len(cols_to_plot)
    if n_cols == 0:
        return None
        
    n_plot_cols = 2 if n_cols > 1 else 1
    n_plot_rows = math.ceil(n_cols / n_plot_cols)
    
    fig = make_subplots(
        rows=n_plot_rows, cols=n_plot_cols,
        subplot_titles=cols_to_plot,
        vertical_spacing=0.15 / max(1, n_plot_rows - 1) if n_plot_rows > 1 else 0.1,
    )
    
    for i, col in enumerate(cols_to_plot):
        r = (i // n_plot_cols) + 1
        c = (i % n_plot_cols) + 1
        
        vc = df[col].value_counts().head(10)
        if vc.empty:
            continue
            
        color = PALETTE[i % len(PALETTE)]
        
        if chart_type == 'pie':
            # Guard: jika nunique > 5, fallback ke Bar Chart (Pie berantakan)
            if df[col].nunique() > 5:
                fig.add_trace(go.Bar(
                    x=vc.index.astype(str).tolist(),
                    y=vc.values.tolist(),
                    marker_color=color, opacity=0.85, name=col,
                    hovertemplate='%{x}<br>Count: %{y:,}<extra></extra>',
                ), row=r, col=c)
            else:
                fig.add_trace(go.Pie(
                    labels=vc.index.astype(str).tolist(),
                    values=vc.values.tolist(),
                    hole=0.4,
                    name=col,
                    showlegend=False,
                ), row=r, col=c)
        elif chart_type == 'count':
            vc_sorted = vc.sort_values()
            fig.add_trace(go.Bar(
                x=vc_sorted.values.tolist(),
                y=vc_sorted.index.astype(str).tolist(),
                orientation='h',
                marker_color=color, opacity=0.85, name=col,
                hovertemplate='%{y}<br>Count: %{x:,}<extra></extra>',
            ), row=r, col=c)
        elif chart_type == 'pareto':
            cum = (vc.cumsum() / vc.sum() * 100)
            x_labels = vc.index.astype(str).tolist()
            fig.add_trace(go.Bar(
                x=x_labels,
                y=vc.values.tolist(),
                marker_color=color, opacity=0.85,
                name=col,
            ), row=r, col=c)
            fig.add_trace(go.Scatter(
                x=x_labels,
                y=vc.values.tolist(),
                mode='lines+markers',
                line=dict(color='#FF7A00', width=1.5),
                showlegend=False,
            ), row=r, col=c)
        else: # default bar
            fig.add_trace(go.Bar(
                x=vc.index.astype(str).tolist(),
                y=vc.values.tolist(),
                marker_color=color, opacity=0.85, name=col,
                hovertemplate='%{x}<br>Count: %{y:,}<extra></extra>',
            ), row=r, col=c)
            
    height = max(450, n_plot_rows * 300)
    fig.update_layout(_layout(
        title=f' Visualisasi Semua Variabel Kategorik ({CHART_LABELS.get(chart_type, chart_type)})',
        height=height,
        showlegend=False,
    ))
    return _json(_axes(fig))


# ─── MASTER ENTRY POINT ──────────────────────────────────────────────────────

def generate_master_chart(df, num_cols, cat_cols, category, chart_type,
                          col_x=None, col_y=None, col_z=None):
    if not category_available(category, num_cols, cat_cols):
        return {
            'ok'         : False,
            'placeholder': PLACEHOLDERS.get(category, 'Dataset tidak kompatibel.'),
            'kpis'       : [],
        }

    types = CATEGORY_CHARTS.get(category, [])
    if not chart_type or chart_type not in types:
        chart_type = types[0] if types else None
    if not chart_type:
        return {'ok': False, 'placeholder': 'Tidak ada tipe grafik.', 'kpis': []}

    if category in ('numerical', 'categorical') and not col_x:
        col_x = num_cols[0] if category == 'numerical' else cat_cols[0]

    if category == 'bivariate':
        col_x = col_x or (num_cols[0] if num_cols else None)
        col_y = col_y or (num_cols[1] if len(num_cols) > 1 else num_cols[0])
        col_z = col_z or (num_cols[2] if len(num_cols) > 2 else num_cols[0])

    if category == 'catnum':
        # Default jika belum ada
        if not col_x or col_x not in df.columns:
            col_x = cat_cols[0] if cat_cols else None
        if not col_y or col_y not in df.columns:
            col_y = num_cols[0] if num_cols else None
        # Smart swap: builder butuh (cat_col, num_col)
        # Jika user pilih X=numeric dan Y=categorical → swap dulu
        x_is_num = (col_x in num_cols) if col_x else False
        y_is_cat = (col_y in cat_cols) if col_y else False
        if x_is_num and y_is_cat:
            col_x, col_y = col_y, col_x
        # Fallback: jika keduanya numeric → X = cat[0]
        if col_x in num_cols and col_y in num_cols:
            col_x = cat_cols[0] if cat_cols else col_x
        # Fallback: jika keduanya categorical → Y = num[0]
        if col_x in cat_cols and col_y in cat_cols:
            col_y = num_cols[0] if num_cols else col_y

    if category == 'compare':
        # col_x bisa berisi comma-separated kolom yang dipilih user
        # Contoh: "age,salary,score" → pakai sebagai subset num_cols
        if col_x:
            selected = [c.strip() for c in col_x.split(',')
                        if c.strip() in df.columns and c.strip() in num_cols]
            if selected:
                num_cols = selected

    if col_x == '__all__':
        try:
            if category == 'numerical':
                chart = _chart_all_numerical(df, num_cols, chart_type)
                kpis = [
                    {'label': 'Numerical Cols', 'value': str(len(num_cols)), 'icon': 'fa-columns'},
                    {'label': 'Total Rows', 'value': f'{len(df):,}', 'icon': 'fa-list'},
                    {'label': 'Missing Cells', 'value': f'{int(df[num_cols].isna().sum().sum()):,}', 'icon': 'fa-exclamation'},
                ]
            elif category == 'categorical':
                chart = _chart_all_categorical(df, cat_cols, chart_type)
                kpis = [
                    {'label': 'Categorical Cols', 'value': str(len(cat_cols)), 'icon': 'fa-columns'},
                    {'label': 'Total Rows', 'value': f'{len(df):,}', 'icon': 'fa-list'},
                    {'label': 'Missing Cells', 'value': f'{int(df[cat_cols].isna().sum().sum()):,}', 'icon': 'fa-exclamation'},
                ]
            else:
                chart = None
                kpis = []
            
            if chart is None:
                return {
                    'ok'         : False,
                    'placeholder': f'Gagal membuat grafik untuk semua variabel.',
                    'kpis'       : kpis,
                }
            
            idx = types.index(chart_type)
            return {
                'ok'          : True,
                'chart'       : chart,
                'kpis'        : kpis,
                'chart_type'  : chart_type,
                'chart_label' : CHART_LABELS.get(chart_type, chart_type),
                'chart_index' : idx,
                'chart_total' : len(types),
                'col_x'       : col_x,
                'col_y'       : col_y,
                'col_z'       : col_z,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'ok'         : False,
                'placeholder': f'Gagal membuat grafik semua variabel: {str(e)}',
                'kpis'       : [],
            }

    def _valid(c):
        return c and c in df.columns

    try:
        builders = {
            'histogram'           : lambda: _chart_histogram(df, col_x) if _valid(col_x) else None,
            'boxplot'             : lambda: _chart_boxplot(df, col_x) if _valid(col_x) else None,
            'density'             : lambda: _chart_density(df, col_x) if _valid(col_x) else None,
            'qq'                  : lambda: _chart_qq(df, col_x) if _valid(col_x) else None,
            'violin'              : lambda: _chart_violin(df, col_x) if _valid(col_x) else None,
            'bar'                 : lambda: _chart_bar(df, col_x) if _valid(col_x) else None,
            'pie'                 : lambda: _chart_pie(df, col_x) if _valid(col_x) else None,  # _chart_pie has nunique guard
            'count'               : lambda: _chart_count(df, col_x) if _valid(col_x) else None,
            'pareto'              : lambda: _chart_pareto(df, col_x) if _valid(col_x) else None,
            'scatter'             : lambda: _chart_scatter(df, col_x, col_y) if _valid(col_x) and _valid(col_y) else None,
            'heatmap'             : lambda: _chart_heatmap(df, num_cols),
            'scatter_matrix'      : lambda: _chart_scatter_matrix(df, num_cols),
            'regression_plot'     : lambda: _chart_regression_plot(df, col_x, col_y) if _valid(col_x) and _valid(col_y) else None,
            'bubble_chart'        : lambda: _chart_bubble_chart(df, col_x, col_y, col_z) if _valid(col_x) and _valid(col_y) and _valid(col_z) else None,
            'box_cat_num'         : lambda: _chart_box_cat_num(df, col_x, col_y) if _valid(col_x) and _valid(col_y) else None,
            'violin_cat_num'      : lambda: _chart_violin_cat_num(df, col_x, col_y) if _valid(col_x) and _valid(col_y) else None,
            'grouped_bar'         : lambda: _chart_grouped_bar(df, col_x, col_y) if _valid(col_x) and _valid(col_y) else None,
            'strip_plot'          : lambda: _chart_strip_plot(df, col_x, col_y) if _valid(col_x) and _valid(col_y) else None,
            'violin_compare'      : lambda: _chart_violin_compare(df, num_cols),
            'grouped_bar_compare' : lambda: _chart_grouped_bar_compare(df, num_cols),
            'parallel_coords'     : lambda: _chart_parallel_coords(df, num_cols),
        }

        chart = builders[chart_type]()
        if chart is None:
            return {
                'ok'         : False,
                'placeholder': f'Data tidak cukup untuk membuat grafik "{CHART_LABELS.get(chart_type, chart_type)}".',
                'kpis'       : build_kpis(category, df, col_x, col_y, num_cols),
            }

        idx = types.index(chart_type)
        return {
            'ok'          : True,
            'chart'       : chart,
            'kpis'        : build_kpis(category, df, col_x, col_y, num_cols),
            'chart_type'  : chart_type,
            'chart_label' : CHART_LABELS.get(chart_type, chart_type),
            'chart_index' : idx,
            'chart_total' : len(types),
            'col_x'       : col_x,
            'col_y'       : col_y,
            'col_z'       : col_z,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'ok'         : False,
            'placeholder': f'Gagal membuat grafik: {str(e)}',
            'kpis'       : build_kpis(category, df, col_x, col_y, num_cols),
        }