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
    return json.loads(fig.to_json())


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
        try:
            parsed = pd.to_datetime(sample, infer_datetime_format=True, errors='coerce')
            # Jika > 70% berhasil di-parse → anggap datetime
            if parsed.notna().mean() >= 0.70:
                dt_cols.append(col)
        except Exception:
            pass

    return dt_cols


def prepare_ts(df, dt_col, num_col):
    """
    Menyiapkan DataFrame time-series yang sudah diurutkan dan di-resample jika perlu.
    Mengembalikan (ts_df, freq_label).
    """
    temp = df[[dt_col, num_col]].copy()
    temp[dt_col] = pd.to_datetime(temp[dt_col], errors='coerce')
    temp = temp.dropna(subset=[dt_col, num_col]).sort_values(dt_col)

    # Hitung rata-rata rentang waktu
    if len(temp) < 2:
        return temp.rename(columns={dt_col: 'ds', num_col: 'y'}), 'original'

    diffs   = temp[dt_col].diff().dropna()
    med_sec = diffs.median().total_seconds()

    # Pilih frekuensi resample adaptif
    if med_sec <= 3600:          # < 1 jam → hourly
        freq, label = 'H', 'Hourly'
    elif med_sec <= 86400:       # < 1 hari → daily
        freq, label = 'D', 'Daily'
    elif med_sec <= 86400 * 7:   # < 1 minggu → weekly
        freq, label = 'W', 'Weekly'
    elif med_sec <= 86400 * 31:  # < 1 bulan → monthly
        freq, label = 'ME', 'Monthly'
    else:
        freq, label = 'YE', 'Yearly'

    try:
        ts = temp.set_index(dt_col)[num_col].resample(freq).mean().dropna().reset_index()
        ts.columns = ['ds', 'y']
    except Exception:
        ts = temp.rename(columns={dt_col: 'ds', num_col: 'y'})

    return ts, label


def _moving_window(n):
    """Pilih ukuran window moving average yang wajar berdasarkan panjang data."""
    if n >= 365: return 30
    if n >= 90:  return 7
    if n >= 30:  return 5
    return max(2, n // 5)


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
    direction = 'Meningkat (Upward) ↑' if slope > 0 else 'Menurun (Downward) ↓'
    sig = 'signifikan secara statistik (p<0.05)' if p < 0.05 else 'belum signifikan (p≥0.05)'
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

    _try('ts_line',    ts_line_chart,    ts, dt_col, num_col, freq_label)
    _try('ts_trend',   ts_trend_line,    ts, num_col, freq_label)
    _try('ts_ma',      ts_moving_average,ts, num_col, freq_label)
    _try('ts_rolling', ts_rolling_mean,  ts, num_col)
    _try('ts_overview',ts_overview_panel,ts, num_col, freq_label)

    ts_insights_list = ts_insights(ts, num_col, dt_col, freq_label)

    return ts_plots, ts_insights_list, ts_meta