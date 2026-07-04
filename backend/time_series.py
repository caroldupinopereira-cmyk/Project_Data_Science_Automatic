"""
backend/time_series.py
Week 15 — Time Series Analytics (Auto Detection)

Fitur:
  - Auto-detect kolom datetime
  - Time Series Line Chart
  - Trend Line (OLS)
  - Moving Average (7, 30 hari atau adaptif)
  - Rolling Mean
  - Insight ringkasan (trend, seasonality, fluktuasi)
"""

import json
import warnings
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats as scipy_stats

warnings.filterwarnings('ignore')

# ─── Palette ────────────────────────────────────────────────────────────────
COLORS = ['#4318ff', '#05cd99', '#ffce20', '#ee5d50', '#868cff', '#17a2b8']
LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor ='rgba(0,0,0,0)',
    font         =dict(family='Inter, sans-serif', size=12),
    margin       =dict(l=40, r=20, t=52, b=40),
    hoverlabel   =dict(bgcolor='rgba(10,18,48,0.93)',
                       bordercolor='rgba(100,160,235,0.45)',
                       font=dict(color='#e8f4fc', size=13)),
    hovermode    ='x unified',
)
AXIS = dict(showgrid=True, gridcolor='rgba(180,190,220,0.15)',
            zeroline=False, linecolor='rgba(180,190,220,0.3)')

def _layout(**kw):
    d = dict(**LAYOUT); d.update(kw); return d

def _safe_json(fig):
    """Convert a Plotly figure to a JSON-serializable dict with plain Python lists."""
    import json as _json
    import base64
    import numpy as _np

    def _convert(obj):
        if obj is None:
            return None
        if isinstance(obj, dict):
            if 'dtype' in obj and 'bdata' in obj:
                dtype = _np.dtype(obj['dtype'])
                raw_bytes = base64.b64decode(obj['bdata'])
                arr = _np.frombuffer(raw_bytes, dtype=dtype)
                if _np.issubdtype(dtype, _np.floating):
                    return [None if _np.isnan(v) else round(float(v), 6) for v in arr]
                elif _np.issubdtype(dtype, _np.datetime64):
                    return [pd.Timestamp(v).isoformat() for v in arr]
                else:
                    return [v.item() for v in arr]
            return {k: _convert(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [_convert(v) for v in obj]
        elif isinstance(obj, _np.ndarray):
            if _np.issubdtype(obj.dtype, _np.floating):
                return [None if _np.isnan(v) else round(float(v), 6) for v in obj]
            elif _np.issubdtype(obj.dtype, _np.datetime64):
                return [pd.Timestamp(v).isoformat() for v in obj]
            else:
                return [v.item() for v in obj]
        elif isinstance(obj, (_np.integer,)):
            return int(obj)
        elif isinstance(obj, (_np.floating,)):
            return None if _np.isnan(obj) else round(float(obj), 6)
        elif isinstance(obj, (_np.datetime64,)):
            return pd.Timestamp(obj).isoformat()
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        elif hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return obj

    raw = fig.to_dict()
    return _json.loads(_json.dumps(_convert(raw), default=str))


# ════════════════════════════════════════════════════════════════════════════
# AUTO-DETECTION
# ════════════════════════════════════════════════════════════════════════════

def detect_datetime_cols(df):
    """
    Mendeteksi kolom datetime secara otomatis.
    Memeriksa tipe data asli dan mencoba parse kolom object/string.
    Mengembalikan list nama kolom datetime.
    """
    dt_cols = []

    # Kolom yang sudah bertipe datetime
    for col in df.select_dtypes(include=['datetime64', 'datetimetz']).columns:
        dt_cols.append(col)

    # Kolom object/string yang bisa di-parse sebagai datetime
    for col in df.select_dtypes(include=['object']).columns:
        if col in dt_cols:
            continue
        sample = df[col].dropna().head(100)
        if len(sample) == 0:
            continue
        try:
            parsed = pd.to_datetime(sample, errors='coerce', format='mixed')
            # Jika > 70% berhasil di-parse → anggap datetime
            if parsed.notna().mean() >= 0.70:
                dt_cols.append(col)
        except Exception:
            try:
                parsed = pd.to_datetime(sample, errors='coerce')
                if parsed.notna().mean() >= 0.70:
                    dt_cols.append(col)
            except Exception:
                pass

    return dt_cols


def prepare_ts(df, dt_col, num_col):
    """
    Menyiapkan DataFrame time-series yang sudah diurutkan kronologis.
    Mengembalikan (ts_df, freq_label).
    Tidak resample - pakai semua data point mentah seperti reference.
    """
    temp = df[[dt_col, num_col]].copy()
    try:
        temp[dt_col] = pd.to_datetime(temp[dt_col], errors='coerce', format='mixed')
    except Exception:
        try:
            temp[dt_col] = pd.to_datetime(temp[dt_col], errors='coerce')
        except Exception:
            pass
    temp[num_col] = pd.to_numeric(temp[num_col], errors='coerce')
    temp = temp.dropna(subset=[dt_col, num_col]).sort_values(dt_col).reset_index(drop=True)

    # Determine frequency label for display (no resampling)
    if len(temp) < 2:
        return temp.rename(columns={dt_col: 'ds', num_col: 'y'}), 'original'

    unique_dates = temp[dt_col].dt.normalize().nunique()
    total_days = (temp[dt_col].max() - temp[dt_col].min()).days + 1

    if total_days <= 0:
        label = 'Event'
    elif unique_dates >= total_days * 0.5:
        label = 'Daily'
    elif unique_dates >= total_days * 0.1:
        label = 'Weekly'
    else:
        label = 'Monthly'

    # If multiple events per timestamp, label as Transactional
    if unique_dates < len(temp) * 0.5:
        label = 'Transactional'

    ts = temp.rename(columns={dt_col: 'ds', num_col: 'y'})
    return ts, label


def _moving_window(n):
    """Pilih ukuran window moving average yang wajar berdasarkan panjang data."""
    if n >= 500: return 30
    if n >= 200: return 20
    if n >= 100: return 14
    if n >= 50:  return 10
    if n >= 30:  return 7
    return max(3, n // 10)


# ════════════════════════════════════════════════════════════════════════════
# CHART GENERATORS
# ════════════════════════════════════════════════════════════════════════════

def ts_line_chart(ts, dt_col_name, num_col_name, freq_label):
    """Time Series Line Chart utama."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts['ds'], y=ts['y'],
        mode='lines', name=num_col_name,
        line=dict(color=COLORS[0], width=2),
        hovertemplate='%{x|%Y-%m-%d}<br>' + num_col_name + ': %{y:,.2f}<extra></extra>',
    ))
    fig.update_layout(_layout(
        title=f'📈 Time Series — {num_col_name} ({freq_label})',
        xaxis=dict(**AXIS, title=dt_col_name, rangeslider=dict(visible=True), type='date'),
        yaxis=dict(**AXIS, title=num_col_name),
    ))
    return _safe_json(fig)


def ts_trend_line(ts, num_col_name, freq_label):
    """Time Series + OLS Trend Line."""
    x_num = np.arange(len(ts))
    slope, intercept, r, p, _ = scipy_stats.linregress(x_num, ts['y'])
    trend = slope * x_num + intercept
    direction = '↑ Upward' if slope > 0 else '↓ Downward'

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts['ds'], y=ts['y'],
        mode='lines', name='Actual',
        line=dict(color=COLORS[0], width=2), opacity=0.8,
        hovertemplate='%{x|%Y-%m-%d}<br>Actual: %{y:,.2f}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=ts['ds'], y=trend,
        mode='lines', name=f'Trend (R²={r**2:.3f})',
        line=dict(color=COLORS[3], width=2.5, dash='dash'),
        hovertemplate='%{x|%Y-%m-%d}<br>Trend: %{y:,.2f}<extra></extra>',
    ))
    fig.update_layout(_layout(
        title=f'📉 Trend Line — {num_col_name} | {direction} | R²={r**2:.3f}',
        xaxis=dict(**AXIS, title='Date', type='date'),
        yaxis=dict(**AXIS, title=num_col_name),
    ))
    return _safe_json(fig)


def ts_moving_average(ts, num_col_name, freq_label):
    """Time Series + Moving Average overlay."""
    window = _moving_window(len(ts))
    ma = ts['y'].rolling(window, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts['ds'], y=ts['y'],
        mode='lines', name='Actual',
        line=dict(color=COLORS[0], width=1.5), opacity=0.6,
        hovertemplate='%{x|%Y-%m-%d}<br>Actual: %{y:,.2f}<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=ts['ds'], y=ma,
        mode='lines', name=f'MA({window})',
        line=dict(color=COLORS[1], width=2.5),
        hovertemplate='%{x|%Y-%m-%d}<br>MA(' + str(window) + '): %{y:,.2f}<extra></extra>',
    ))
    fig.update_layout(_layout(
        title=f'📊 Moving Average (window={window}) — {num_col_name}',
        xaxis=dict(**AXIS, title='Date', type='date'),
        yaxis=dict(**AXIS, title=num_col_name),
    ))
    return _safe_json(fig)


def ts_rolling_mean(ts, num_col_name):
    """Rolling Mean dengan beberapa window berbeda."""
    windows = [_moving_window(len(ts)), _moving_window(len(ts)) * 3]
    windows = [w for w in windows if w < len(ts)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts['ds'], y=ts['y'],
        mode='lines', name='Actual',
        line=dict(color=COLORS[0], width=1.5), opacity=0.5,
        hovertemplate='%{x|%Y-%m-%d}<br>Actual: %{y:,.2f}<extra></extra>',
    ))
    for i, w in enumerate(windows):
        rm = ts['y'].rolling(w, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=ts['ds'], y=rm,
            mode='lines', name=f'Rolling Mean ({w})',
            line=dict(color=COLORS[i + 1], width=2.5),
            hovertemplate='%{x|%Y-%m-%d}<br>RM(' + str(w) + '): %{y:,.2f}<extra></extra>',
        ))
    fig.update_layout(_layout(
        title=f'🔄 Rolling Mean — {num_col_name}',
        xaxis=dict(**AXIS, title='Date', type='date'),
        yaxis=dict(**AXIS, title=num_col_name),
    ))
    return _safe_json(fig)


def ts_combined_chart(ts, num_col_name, freq_label):
    """
    Combined chart: actual data (light) + rolling mean (bold) + OLS trend (dashed).
    Matches the reference "Dynamic Time Series & Rolling Averaging projections" style.
    """
    window = _moving_window(len(ts))
    y = ts['y'].values
    n = len(y)

    # Rolling mean
    ma = ts['y'].rolling(window, min_periods=1).mean()

    # OLS trend
    x_num = np.arange(n)
    slope, intercept, r, p, _ = scipy_stats.linregress(x_num, y)
    trend = slope * x_num + intercept

    fig = go.Figure()

    # 1. Actual data (light, thin)
    fig.add_trace(go.Scatter(
        x=ts['ds'], y=ts['y'],
        mode='lines', name=f'{num_col_name} (Actual counts)',
        line=dict(color='rgba(180,190,220,0.45)', width=1.2),
        hovertemplate='%{x|%Y-%m-%d}<br>Actual: %{y:,.2f}<extra></extra>',
    ))

    # 2. Rolling Mean (bold blue)
    fig.add_trace(go.Scatter(
        x=ts['ds'], y=ma,
        mode='lines', name=f'Smoothed Rolling Window Mean',
        line=dict(color='#3b82f6', width=3),
        hovertemplate='%{x|%Y-%m-%d}<br>Rolling Mean: %{y:,.2f}<extra></extra>',
    ))

    # 3. OLS Trend Line (red dashed)
    fig.add_trace(go.Scatter(
        x=ts['ds'], y=trend,
        mode='lines', name=f'OLS Trend Line',
        line=dict(color='#ef4444', width=2, dash='dash'),
        hovertemplate='%{x|%Y-%m-%d}<br>Trend: %{y:,.2f}<extra></extra>',
    ))

    fig.update_layout(_layout(
        title=f'Dynamic Time Series & Rolling Averaging projections',
        xaxis=dict(**AXIS, title='Date', type='date'),
        yaxis=dict(**AXIS, title=num_col_name),
        legend=dict(
            orientation='h', yanchor='bottom', y=-0.25, xanchor='center', x=0.5,
            font=dict(size=11),
        ),
        hovermode='x unified',
    ))
    return _safe_json(fig)


def ts_overview_panel(ts, num_col_name, freq_label):
    """Panel 4-in-1: line, trend, MA, rolling std (volatility)."""
    window = _moving_window(len(ts))
    ma     = ts['y'].rolling(window, min_periods=1).mean()
    rs     = ts['y'].rolling(window, min_periods=1).std().fillna(0)
    x_num  = np.arange(len(ts))
    slope, intercept, _, _, _ = scipy_stats.linregress(x_num, ts['y'])
    trend  = slope * x_num + intercept

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            f'Line Chart — {num_col_name}',
            f'Trend Line (OLS)',
            f'Moving Average (window={window})',
            'Rolling Volatility (Std)',
        ],
        shared_xaxes=False,
    )

    kw = dict(x=ts['ds'], mode='lines')

    # Row 1 col 1 — Line
    fig.add_trace(go.Scatter(**kw, y=ts['y'],    name='Actual', line=dict(color=COLORS[0], width=1.8)), row=1, col=1)
    # Row 1 col 2 — Trend
    fig.add_trace(go.Scatter(**kw, y=ts['y'],    name='Actual', line=dict(color=COLORS[0], width=1.5), opacity=0.6, showlegend=False), row=1, col=2)
    fig.add_trace(go.Scatter(**kw, y=trend,      name='Trend',  line=dict(color=COLORS[3], width=2, dash='dash')), row=1, col=2)
    # Row 2 col 1 — MA
    fig.add_trace(go.Scatter(**kw, y=ts['y'],    name='Actual', line=dict(color=COLORS[0], width=1.2), opacity=0.4, showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(**kw, y=ma,         name=f'MA({window})', line=dict(color=COLORS[1], width=2.2)), row=2, col=1)
    # Row 2 col 2 — Rolling Std
    fig.add_trace(go.Scatter(**kw, y=rs, fill='tozeroy', name='Rolling Std',
                             fillcolor='rgba(134,140,255,0.15)', line=dict(color=COLORS[4], width=1.8)), row=2, col=2)

    fig.update_layout(_layout(
        title=f'⏱️ Time Series Overview — {num_col_name} ({freq_label})',
        height=520, showlegend=True,
    ))
    fig.update_xaxes(**AXIS)
    fig.update_yaxes(**AXIS)
    return _safe_json(fig)


# ════════════════════════════════════════════════════════════════════════════
# INSIGHT GENERATOR
# ════════════════════════════════════════════════════════════════════════════

def ts_insights(ts, num_col_name, dt_col_name, freq_label):
    """
    Menghasilkan ringkasan insight time series:
    - Trend (naik/turun/flat)
    - Seasonality (deteksi kasar via korelasi lag)
    - Fluktuasi (CV)
    - Nilai max & min beserta tanggalnya
    """
    insights = []
    y = ts['y'].values
    n = len(y)

    if n < 4:
        return [{'type': 'warning', 'icon': 'fa-clock',
                 'title': 'Time Series Too Short',
                 'desc': f'Kolom waktu {dt_col_name} terdeteksi namun data terlalu sedikit untuk analisis mendalam.'}]

    # ── Trend ────────────────────────────────────────────────────────────────
    x_num = np.arange(n)
    slope, _, r, p, _ = scipy_stats.linregress(x_num, y)
    direction = 'Meningkat (Upward)' if slope > 0 else 'Menurun (Downward)'
    sig = 'signifikan secara statistik (p<0.05)' if p < 0.05 else 'belum signifikan (p>=0.05)'
    insights.append({
        'type': 'primary', 'icon': 'fa-chart-line',
        'title': f'Trend: {direction}',
        'desc': (f'Variabel {num_col_name} menunjukkan tren {direction.lower()} '
                 f'dengan slope={slope:.4f} per periode ({freq_label}). '
                 f'R²={r**2:.3f} — tren {sig}.')
    })

    # ── Fluktuasi / Volatilitas ───────────────────────────────────────────────
    cv = (np.std(y) / np.mean(y) * 100) if np.mean(y) != 0 else 0
    vol_level = 'Tinggi (CV>30%)' if cv > 30 else ('Sedang (CV 10–30%)' if cv > 10 else 'Rendah (CV<10%)')
    insights.append({
        'type': 'warning' if cv > 30 else 'success', 'icon': 'fa-wave-square',
        'title': f'Volatilitas: {vol_level}',
        'desc': (f'Koefisien variasi (CV) = {cv:.1f}%. '
                 f'Nilai ini menunjukkan tingkat fluktuasi yang {vol_level.lower()} '
                 f'pada {num_col_name} sepanjang periode waktu.')
    })

    # ── Max & Min ─────────────────────────────────────────────────────────────
    idx_max = ts['y'].idxmax()
    idx_min = ts['y'].idxmin()
    date_max = str(ts.loc[idx_max, 'ds'])[:10]
    date_min = str(ts.loc[idx_min, 'ds'])[:10]
    val_max  = ts.loc[idx_max, 'y']
    val_min  = ts.loc[idx_min, 'y']
    insights.append({
        'type': 'info', 'icon': 'fa-calendar-check',
        'title': f'Peak & Trough — {num_col_name}',
        'desc': (f'Nilai tertinggi: {val_max:,.2f} pada {date_max}. '
                 f'Nilai terendah: {val_min:,.2f} pada {date_min}. '
                 f'Range: {val_max - val_min:,.2f}.')
    })

    # ── Seasonality (autocorrelation lag) ─────────────────────────────────────
    if n >= 14:
        lags  = [7, 12, 30]
        found = []
        for lag in lags:
            if lag >= n:
                continue
            corr = np.corrcoef(y[:-lag], y[lag:])[0, 1]
            if abs(corr) > 0.40:
                found.append(f'lag={lag} (r={corr:.2f})')
        if found:
            insights.append({
                'type': 'success', 'icon': 'fa-redo',
                'title': 'Pola Musiman (Seasonality) Terdeteksi',
                'desc': f'Autocorrelation tinggi ditemukan pada: {", ".join(found)}. '
                        f'Ini mengindikasikan adanya pola berulang pada {num_col_name}.'
            })
        else:
            insights.append({
                'type': 'muted', 'icon': 'fa-minus-circle',
                'title': 'Tidak Ada Pola Musiman Jelas',
                'desc': (f'Tidak ditemukan autocorrelation signifikan pada lag standar (7, 12, 30). '
                         f'Data {num_col_name} tampak tidak memiliki pola musiman yang kuat.')
            })

    return insights


# ════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

def generate_ts_plots(df, dt_cols, num_cols):
    """
    Menghasilkan semua plot & insight time series.

    Parameters
    ----------
    df       : DataFrame lengkap
    dt_cols  : list kolom datetime (dari detect_datetime_cols)
    num_cols : list kolom numerik

    Returns
    -------
    ts_plots    : dict { key: plotly_json }
    ts_insights_list : list insight dicts
    ts_meta     : dict { dt_col, num_col, freq_label, n_points }
    """
    ts_plots         = {}
    ts_insights_list = []
    ts_meta          = {}

    if not dt_cols or not num_cols:
        return ts_plots, ts_insights_list, ts_meta

    dt_col  = dt_cols[0]
    num_col = num_cols[0]

    # Prepare single-variable ts
    ts, freq_label = prepare_ts(df, dt_col, num_col)

    if len(ts) < 4:
        return ts_plots, ts_insights_list, ts_meta

    ts_meta = {
        'dt_col'     : dt_col,
        'num_col'    : num_col,
        'freq_label' : freq_label,
        'n_points'   : len(ts),
        'date_start' : str(ts['ds'].min())[:10],
        'date_end'   : str(ts['ds'].max())[:10],
    }

    def _try(key, fn, *args):
        try:
            result = fn(*args)
            if result:
                ts_plots[key] = result
        except Exception as e:
            print(f"[time_series] Skipping '{key}': {e}")

    # ── Single-variable charts ──
    _try('ts_combined', ts_combined_chart, ts, num_col, freq_label)
    _try('ts_line',    ts_line_chart,    ts, dt_col, num_col, freq_label)
    _try('ts_trend',   ts_trend_line,    ts, num_col, freq_label)
    _try('ts_ma',      ts_moving_average,ts, num_col, freq_label)
    _try('ts_rolling', ts_rolling_mean,  ts, num_col)
    _try('ts_overview',ts_overview_panel,ts, num_col, freq_label)

    n = len(ts)
    _try('ts_forecast', ts_forecast_simple, ts, num_col, min(30, max(5, n // 5)))
    _try('ts_acf_pacf', ts_acf_pacf, ts, num_col)

    # ── Summary stats ──
    ts_for_summary = ts[['ds', 'y']].copy()
    ts_for_summary[num_col] = ts_for_summary['y']
    _try('ts_summary', ts_summary_stats, ts_for_summary, [num_col], dt_col, freq_label)

    # ── Multivariate charts (need prepare_ts_multivariate) ──
    if len(num_cols) > 1:
        try:
            ts_multi, _ = prepare_ts_multivariate(df, dt_col, num_cols)
            _try('ts_multi_line',  ts_multi_line_chart,  ts_multi, num_cols, freq_label)
            _try('ts_correlation', ts_correlation_heatmap, ts_multi, num_cols)
            _try('ts_subplots',   ts_subplots,           ts_multi, num_cols, freq_label)
        except Exception as e:
            print(f"[time_series] Skipping multivariate charts: {e}")

    ts_insights_list = ts_insights(ts, num_col, dt_col, freq_label)

    return ts_plots, ts_insights_list, ts_meta


# ════════════════════════════════════════════════════════════════════════════
# MULTIVARIATE TIME SERIES
# ════════════════════════════════════════════════════════════════════════════

def prepare_ts_multivariate(df, dt_col, num_cols, freq=None):
    """
    Menyiapkan DataFrame multivariate time-series tanpa resample.
    Mengembalikan (ts_df, freq_label) dengan kolom 'ds' + semua num_cols.
    """
    temp = df[[dt_col] + num_cols].copy()
    try:
        temp[dt_col] = pd.to_datetime(temp[dt_col], errors='coerce', format='mixed')
    except Exception:
        try:
            temp[dt_col] = pd.to_datetime(temp[dt_col], errors='coerce')
        except Exception:
            pass
    for c in num_cols:
        temp[c] = pd.to_numeric(temp[c], errors='coerce')
    temp = temp.dropna(subset=[dt_col]).sort_values(dt_col).reset_index(drop=True)

    if len(temp) < 2:
        ts = temp.rename(columns={dt_col: 'ds'})
        return ts, 'original'

    unique_dates = temp[dt_col].dt.normalize().nunique()
    total_days = (temp[dt_col].max() - temp[dt_col].min()).days + 1

    if total_days <= 0:
        label = 'Event'
    elif unique_dates >= total_days * 0.5:
        label = 'Daily'
    elif unique_dates >= total_days * 0.1:
        label = 'Weekly'
    else:
        label = 'Monthly'

    if unique_dates < len(temp) * 0.5:
        label = 'Transactional'

    ts = temp.rename(columns={dt_col: 'ds'})
    return ts, label


def ts_multi_line_chart(ts, num_cols, freq_label):
    """Multi-line chart: semua variabel numerik dalam satu plot."""
    fig = go.Figure()
    for i, col in enumerate(num_cols):
        color = COLORS[i % len(COLORS)]
        fig.add_trace(go.Scatter(
            x=ts['ds'], y=ts[col],
            mode='lines', name=col,
            line=dict(color=color, width=2),
            hovertemplate=f'%{{x|%Y-%m-%d}}<br>{col}: %{{y:,.2f}}<extra></extra>',
        ))
    fig.update_layout(_layout(
        title=f'📈 Multi-Line Chart ({freq_label})',
        xaxis=dict(**AXIS, title='Date', type='date'),
        yaxis=dict(**AXIS, title='Value'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    ))
    return _safe_json(fig)


def ts_correlation_heatmap(ts, num_cols):
    """Heatmap korelasi antar variabel time series."""
    valid_cols = [c for c in num_cols if c in ts.columns]
    if len(valid_cols) < 2:
        return None

    corr = ts[valid_cols].corr()
    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns.tolist(),
        y=corr.index.tolist(),
        colorscale='RdBu_r',
        zmin=-1, zmax=1,
        text=corr.values.round(2).tolist(),
        texttemplate='%{text}',
        textfont=dict(size=12),
        hovertemplate='%{x} vs %{y}<br>Correlation: %{z:.3f}<extra></extra>',
    ))
    fig.update_layout(_layout(
        title='🔗 Correlation Heatmap — Time Series Variables',
        height=450,
        xaxis=dict(**AXIS, tickangle=-45),
        yaxis=dict(**AXIS, autorange='reversed'),
    ))
    return _safe_json(fig)


def ts_subplots(ts, num_cols, freq_label):
    """Subplot terpisah untuk setiap variabel numerik."""
    n = len(num_cols)
    if n == 0:
        return None

    rows = (n + 1) // 2
    cols = 2 if n > 1 else 1

    subplot_titles = [f'{col}' for col in num_cols]
    fig = make_subplots(
        rows=rows, cols=cols,
        subplot_titles=subplot_titles,
        shared_xaxes=True,
        vertical_spacing=0.06,
        horizontal_spacing=0.08,
    )

    for i, col in enumerate(num_cols):
        r = i // 2 + 1
        c = i % 2 + 1
        color = COLORS[i % len(COLORS)]
        fig.add_trace(go.Scatter(
            x=ts['ds'], y=ts[col],
            mode='lines', name=col,
            line=dict(color=color, width=1.8),
            showlegend=False,
            hovertemplate=f'%{{x|%Y-%m-%d}}<br>{col}: %{{y:,.2f}}<extra></extra>',
        ), row=r, col=c)

    fig.update_layout(_layout(
        title=f'📊 Subplots — All Variables ({freq_label})',
        height=280 * rows,
        showlegend=False,
    ))
    fig.update_xaxes(**AXIS)
    fig.update_yaxes(**AXIS)
    return _safe_json(fig)


def ts_multivariate_insights(ts, num_cols, dt_col, freq_label):
    """Insight untuk analisis multivariate."""
    insights = []
    valid_cols = [c for c in num_cols if c in ts.columns]

    if len(valid_cols) < 2:
        return insights

    # Korelasi tertinggi
    corr = ts[valid_cols].corr()
    n = len(valid_cols)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            c1, c2 = valid_cols[i], valid_cols[j]
            pairs.append((c1, c2, corr.loc[c1, c2]))
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)

    if pairs:
        top = pairs[0]
        direction = 'positif' if top[2] > 0 else 'negatif'
        strength = 'kuat' if abs(top[2]) > 0.7 else ('sedang' if abs(top[2]) > 0.4 else 'lemah')
        insights.append({
            'type': 'primary', 'icon': 'fa-link',
            'title': f'Korelasi Tertinggi: {top[0]} vs {top[1]}',
            'desc': (f'Korelasi {direction} {strength} (r={top[2]:.3f}) antara {top[0]} dan {top[1]}. '
                     f'Ini menunjukkan hubungan {strength} antar kedua variabel.')
        })

    # Variabel paling stabil (CV terendah)
    cvs = {}
    for col in valid_cols:
        mean = ts[col].mean()
        std = ts[col].std()
        cvs[col] = (std / mean * 100) if mean != 0 else 0
    most_stable = min(cvs, key=cvs.get)
    least_stable = max(cvs, key=cvs.get)
    insights.append({
        'type': 'success', 'icon': 'fa-compress-alt',
        'title': 'Stabilitas Variabel',
        'desc': (f'{most_stable} paling stabil (CV={cvs[most_stable]:.1f}%), '
                 f'{least_stable} paling volatil (CV={cvs[least_stable]:.1f}%).')
    })

    # Tren untuk setiap variabel
    trends = []
    for col in valid_cols:
        y = ts[col].dropna().values
        if len(y) < 4:
            continue
        slope, _, r, p, _ = scipy_stats.linregress(np.arange(len(y)), y)
        direction = '↑' if slope > 0 else '↓'
        sig = '*' if p < 0.05 else ''
        trends.append(f'{col} {direction} (R²={r**2:.2f}{sig})')
    if trends:
        insights.append({
            'type': 'info', 'icon': 'fa-chart-line',
            'title': 'Tren per Variabel',
            'desc': ' | '.join(trends)
        })

    return insights


def ts_forecast_simple(ts, num_col, periods=30):
    """Forecast sederhana menggunakan linear extrapolation."""
    y = ts['y'].values
    n = len(y)
    if n < 4 or periods < 1:
        return None

    x = np.arange(n)
    slope, intercept, r, p, _ = scipy_stats.linregress(x, y)

    x_future = np.arange(n, n + periods)
    y_forecast = slope * x_future + intercept

    last_date = ts['ds'].max()
    freq = ts['ds'].diff().median()
    if pd.isna(freq) or freq.total_seconds() <= 0:
        freq = pd.Timedelta(days=1)
    future_dates = pd.date_range(start=last_date + freq, periods=periods, freq=freq)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts['ds'], y=ts['y'],
        mode='lines', name='Actual',
        line=dict(color=COLORS[0], width=2),
    ))
    fig.add_trace(go.Scatter(
        x=future_dates, y=y_forecast,
        mode='lines', name='Forecast',
        line=dict(color=COLORS[3], width=2, dash='dash'),
    ))
    fig.update_layout(_layout(
        title=f'Forecast - {num_col} ({periods} periods) | R2={r**2:.3f}',
        xaxis=dict(**AXIS, title='Date', type='date'),
        yaxis=dict(**AXIS, title=num_col),
    ))
    return _safe_json(fig)


def ts_acf_pacf(ts, num_col, lags=40):
    """ACF & PACF plot sederhana."""
    y = ts['y'].dropna().values
    n = len(y)
    if n < lags + 1:
        lags = max(n // 2 - 1, 5)

    # Manual ACF calculation
    mean = np.mean(y)
    var = np.var(y)
    acf_vals = []
    for lag in range(1, lags + 1):
        if lag >= n:
            break
        cov = np.mean((y[:-lag] - mean) * (y[lag:] - mean))
        acf_vals.append(cov / var if var != 0 else 0)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=list(range(1, len(acf_vals) + 1)),
        y=acf_vals,
        name='ACF',
        marker_color=COLORS[0],
    ))
    ci = 1.96 / np.sqrt(n)
    fig.add_hline(y=ci, line_dash='dash', line_color='rgba(255,0,0,0.4)')
    fig.add_hline(y=-ci, line_dash='dash', line_color='rgba(255,0,0,0.4)')
    fig.update_layout(_layout(
        title=f'📊 Autocorrelation (ACF) — {num_col}',
        xaxis=dict(**AXIS, title='Lag'),
        yaxis=dict(**AXIS, title='ACF'),
        height=350,
    ))
    return _safe_json(fig)


def ts_summary_stats(ts, num_cols, dt_col, freq_label):
    """Statistik ringkasan untuk semua variabel."""
    stats = {}
    valid_cols = [c for c in num_cols if c in ts.columns]
    for col in valid_cols:
        y = ts[col].dropna()
        if len(y) == 0:
            continue
        stats[col] = {
            'Count': len(y),
            'Mean': f'{y.mean():,.2f}',
            'Median': f'{y.median():,.2f}',
            'Std Dev': f'{y.std():,.2f}',
            'Min': f'{y.min():,.2f}',
            'Max': f'{y.max():,.2f}',
            'Range': f'{y.max() - y.min():,.2f}',
            'CV (%)': f'{(y.std() / y.mean() * 100) if y.mean() != 0 else 0:.1f}%',
        }
    return stats


# ════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY — COMPLETE TIMESERIES (for API)
# ════════════════════════════════════════════════════════════════════════════

def generate_complete_timeseries(df, dt_cols, num_cols, categorical=None, numerical=None, granularity='Auto'):
    """
    Generate semua plot time series untuk API endpoint.
    Mengembalikan dict dengan plots, kpis, meta.
    """
    result = {
        'status': 'error',
        'plots': {},
        'kpis': {},
        'meta': {},
        'insights': [],
    }

    if not dt_cols or not num_cols:
        result['error'] = 'Tidak ada kolom datetime atau numerik yang terdeteksi.'
        return result

    dt_col = categorical if categorical and categorical in dt_cols else dt_cols[0]
    num_col = numerical if numerical and numerical in num_cols else num_cols[0]

    ts, freq_label = prepare_ts_multivariate(df, dt_col, num_cols, freq=granularity)

    if len(ts) < 4:
        result['error'] = 'Data terlalu sedikit untuk analisis time series.'
        return result

    result['meta'] = {
        'dt_col': dt_col,
        'num_col': num_col,
        'freq_label': freq_label,
        'n_points': len(ts),
        'all_num_cols': num_cols,
        'date_start': str(ts['ds'].min())[:10],
        'date_end': str(ts['ds'].max())[:10],
    }

    # ── KPIs ──
    y = ts[num_col].dropna().values
    n = len(y)
    x_num = np.arange(n)
    slope, intercept, r, p, _ = scipy_stats.linregress(x_num, y)

    trend_dir = 'Upward' if slope > 0 else 'Downward'
    pct_change = ((y[-1] - y[0]) / abs(y[0]) * 100) if y[0] != 0 else 0

    result['kpis'] = {
        'chron_trend': trend_dir,
        'slope': f'{slope:.6f}',
        'horizon': f'{n} timestamps',
        'current_value': f'{y[-1]:,.2f}',
        'average': f'{np.mean(y):,.2f}',
        'trend_dir': trend_dir,
        'pct_change': f'{pct_change:+.2f}%',
    }

    # ── Single variable plots (primary) ──
    ts_single = ts[['ds', num_col]].rename(columns={num_col: 'y'})

    def _try(key, fn, *args):
        try:
            result_plot = fn(*args)
            if result_plot:
                result['plots'][key] = result_plot
        except Exception as e:
            print(f"[time_series] Skipping '{key}': {e}")

    _try('ts_combined', ts_combined_chart, ts_single, num_col, freq_label)
    _try('ts_line', ts_line_chart, ts_single, dt_col, num_col, freq_label)
    _try('ts_trend', ts_trend_line, ts_single, num_col, freq_label)
    _try('ts_ma', ts_moving_average, ts_single, num_col, freq_label)
    _try('ts_rolling', ts_rolling_mean, ts_single, num_col)
    _try('ts_overview', ts_overview_panel, ts_single, num_col, freq_label)
    _try('ts_forecast', ts_forecast_simple, ts_single, num_col, min(30, max(5, n // 5)))
    _try('ts_acf_pacf', ts_acf_pacf, ts_single, num_col)

    # ── Summary stats ──
    try:
        result['plots']['ts_summary'] = ts_summary_stats(ts, num_cols, dt_col, freq_label)
    except Exception:
        pass

    # ── Multivariate plots (if multiple numeric columns) ──
    if len(num_cols) > 1:
        _try('ts_multi_line', ts_multi_line_chart, ts, num_cols, freq_label)
        _try('ts_correlation', ts_correlation_heatmap, ts, num_cols)
        _try('ts_subplots', ts_subplots, ts, num_cols, freq_label)

    # ── Insights ──
    result['insights'] = ts_insights(ts_single, num_col, dt_col, freq_label)
    if len(num_cols) > 1:
        result['insights'] += ts_multivariate_insights(ts, num_cols, dt_col, freq_label)

    result['status'] = 'success'
    return result