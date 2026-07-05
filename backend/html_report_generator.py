"""
html_report_generator.py — DS Generator Kelompok 2 ITSB
Generate self-contained interactive HTML report (inline CSS + JS).
Professional layout with collapsible sections, dark mode, search, and more.
"""

import os
import datetime
import base64
import traceback
import pandas as pd
import numpy as np
from io import BytesIO


def _safe(val, default='—'):
    if val is None:
        return default
    if isinstance(val, float) and np.isnan(val):
        return default
    s = str(val).strip()
    return s if s else default


def _fig_to_base64(fig):
    import matplotlib
    matplotlib.use('Agg')
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt = __import__('matplotlib.pyplot', fromlist=['plt'])
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def _generate_chart_images_b64(df, num_cols, cat_cols):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker

    charts = {}
    if df is None or df.empty:
        return charts

    df_work = df.copy()
    real_num = [c for c in (num_cols or df_work.select_dtypes(include=[np.number]).columns.tolist())
                if c in df_work.columns and pd.to_numeric(df_work[c], errors='coerce').notna().sum() > len(df_work)*0.5]
    real_cat = [c for c in (cat_cols or df_work.select_dtypes(exclude=[np.number]).columns.tolist())
                if c in df_work.columns and c not in real_num]

    max_rows = 500
    df_plot = df_work.sample(n=max_rows, random_state=42) if len(df_work) > max_rows else df_work.copy()
    for c in real_num:
        df_plot[c] = pd.to_numeric(df_plot[c], errors='coerce')

    plt.rcParams.update({
        'font.family': 'sans-serif', 'font.size': 10, 'axes.titlesize': 12,
        'axes.labelsize': 10, 'figure.facecolor': 'white', 'axes.facecolor': '#fafbfc',
        'axes.grid': True, 'grid.alpha': 0.25, 'grid.linestyle': '--',
        'axes.spines.top': False, 'axes.spines.right': False,
    })
    palette = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']

    for col in real_num[:3]:
        try:
            fig, ax = plt.subplots(figsize=(7, 4))
            vals = df_plot[col].dropna()
            ax.hist(vals, bins=25, color=palette[0], edgecolor='white', alpha=0.88, rwidth=0.92)
            mean_v = vals.mean()
            median_v = vals.median()
            ax.axvline(mean_v, color='#ef4444', linestyle='--', linewidth=1.5, label=f'Mean={mean_v:,.2f}')
            ax.axvline(median_v, color='#10b981', linestyle='-', linewidth=1.5, label=f'Median={median_v:,.2f}')
            ax.set_title(f'Distribusi {col}', fontweight='bold', pad=10)
            ax.set_xlabel(col); ax.set_ylabel('Frekuensi')
            ax.legend(fontsize=8, framealpha=0.9)
            fig.tight_layout()
            charts[f'hist_{col}'] = _fig_to_base64(fig)
        except Exception:
            plt.close('all')

    for col in real_cat[:2]:
        try:
            vc = df_plot[col].value_counts().head(10)
            if len(vc) < 1:
                continue
            fig, ax = plt.subplots(figsize=(7, 4))
            bars = ax.barh(range(len(vc)), vc.values, color=palette[1], edgecolor='white', alpha=0.9, height=0.7)
            ax.set_yticks(range(len(vc)))
            ax.set_yticklabels([str(x)[:25] for x in vc.index], fontsize=9)
            ax.invert_yaxis()
            ax.set_title(f'Frekuensi {col}', fontweight='bold', pad=10)
            for b in bars:
                w = b.get_width()
                ax.text(w + max(vc.values)*0.01, b.get_y() + b.get_height()/2,
                        f'{int(w):,}', va='center', fontsize=8, color='#374151')
            fig.tight_layout()
            charts[f'bar_{col}'] = _fig_to_base64(fig)
        except Exception:
            plt.close('all')

    if len(real_num) >= 2:
        try:
            cols_corr = real_num[:5]
            corr = df_plot[cols_corr].corr().fillna(0)
            fig, ax = plt.subplots(figsize=(8, 6.5))
            im = ax.imshow(corr.values, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
            ax.set_xticks(range(len(cols_corr)))
            ax.set_xticklabels(cols_corr, rotation=45, ha='right', fontsize=9)
            ax.set_yticks(range(len(cols_corr)))
            ax.set_yticklabels(cols_corr, fontsize=9)
            for i in range(len(cols_corr)):
                for j in range(len(cols_corr)):
                    v = corr.values[i, j]
                    ax.text(j, i, f'{v:.2f}', ha='center', va='center', fontsize=7,
                            color='white' if abs(v) > 0.5 else 'black', fontweight='bold' if abs(v) > 0.7 else 'normal')
            fig.colorbar(im, ax=ax, shrink=0.8, label='Pearson r')
            ax.set_title('Matriks Korelasi Pearson', fontweight='bold', pad=12)
            fig.tight_layout()
            charts['heatmap'] = _fig_to_base64(fig)
        except Exception:
            plt.close('all')

    if len(real_num) >= 2:
        try:
            c1, c2 = real_num[0], real_num[1]
            fig, ax = plt.subplots(figsize=(7, 5))
            ax.scatter(df_plot[c1], df_plot[c2], alpha=0.45, s=18, c=palette[0], edgecolors='white', linewidth=0.3)
            z = np.polyfit(df_plot[c1].dropna(), df_plot[c2].dropna().reindex(df_plot[c1].dropna().index), 1)
            p = np.poly1d(z)
            x_line = np.linspace(df_plot[c1].min(), df_plot[c1].max(), 100)
            ax.plot(x_line, p(x_line), '--', color='#ef4444', linewidth=1.5, label='Trend Line')
            ax.set_xlabel(c1, fontweight='bold'); ax.set_ylabel(c2, fontweight='bold')
            ax.set_title(f'{c1} vs {c2}', fontweight='bold', pad=10)
            ax.legend(fontsize=8)
            fig.tight_layout()
            charts['scatter'] = _fig_to_base64(fig)
        except Exception:
            plt.close('all')

    return charts


def _generate_ts_chart_b64(df, dt_col, num_col, freq_label=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from scipy import stats as sp_stats

    charts = {}
    if df is None or df.empty or not dt_col or not num_col:
        return charts
    if dt_col not in df.columns or num_col not in df.columns:
        return charts

    try:
        ts = df[[dt_col, num_col]].copy()
        ts[dt_col] = pd.to_datetime(ts[dt_col], errors='coerce')
        ts[num_col] = pd.to_numeric(ts[num_col], errors='coerce')
        ts = ts.dropna().sort_values(dt_col).reset_index(drop=True)
        if len(ts) < 3:
            return charts

        x = ts[dt_col].values
        y = ts[num_col].values
        x_num = mdates.date2num(x)

        plt.rcParams.update({
            'font.family': 'sans-serif', 'font.size': 10, 'axes.titlesize': 12,
            'axes.labelsize': 10, 'figure.facecolor': 'white', 'axes.facecolor': '#fafbfc',
            'axes.grid': True, 'grid.alpha': 0.25, 'grid.linestyle': '--',
            'axes.spines.top': False, 'axes.spines.right': False,
        })

        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.plot(x, y, color='#3b82f6', linewidth=1.5, alpha=0.85, zorder=2)
        ax.fill_between(x, y, alpha=0.08, color='#3b82f6', zorder=1)
        ax.set_title(f'Time Series: {num_col}', fontweight='bold', pad=12)
        ax.set_xlabel(dt_col); ax.set_ylabel(num_col)
        ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(mdates.AutoDateLocator()))
        fig.autofmt_xdate(rotation=30); fig.tight_layout()
        charts['ts_line'] = _fig_to_base64(fig)

        slope, intercept, r_val, p_val, _ = sp_stats.linregress(x_num, y)
        trend_line = slope * x_num + intercept
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.plot(x, y, color='#3b82f6', linewidth=1, alpha=0.45, label='Actual')
        ax.plot(x, trend_line, color='#ef4444', linewidth=2.5, linestyle='--',
               label=f'Trend (R²={r_val**2:.3f}, p={p_val:.4f})')
        ax.set_title(f'Trend Analysis: {num_col}', fontweight='bold', pad=12)
        ax.legend(fontsize=9, framealpha=0.9)
        ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(mdates.AutoDateLocator()))
        fig.autofmt_xdate(rotation=30); fig.tight_layout()
        charts['ts_trend'] = _fig_to_base64(fig)

        n = len(y)
        window = 30 if n >= 365 else 7 if n >= 90 else 5 if n >= 30 else max(n//5, 2)
        ma = pd.Series(y).rolling(window=window, min_periods=1).mean().values
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.plot(x, y, color='#3b82f6', linewidth=0.8, alpha=0.4, label='Actual')
        ax.plot(x, ma, color='#f59e0b', linewidth=2.5, label=f'Moving Avg (w={window})')
        ax.set_title(f'Moving Average: {num_col}', fontweight='bold', pad=12)
        ax.legend(fontsize=9, framealpha=0.9)
        ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(mdates.AutoDateLocator()))
        fig.autofmt_xdate(rotation=30); fig.tight_layout()
        charts['ts_ma'] = _fig_to_base64(fig)

    except Exception as e:
        print(f'[HTML TS chart] error: {e}')
        plt.close('all')

    return charts


# ══════════════════════════════════════════════════════════════════════════════
# CSS TEMPLATE
# ══════════════════════════════════════════════════════════════════════════════
_CSS = '''
:root {
  --pri: #1e3a8a; --blue: #2563eb; --green: #059669; --yellow: #d97706;
  --red: #dc2626; --gray: #64748b; --purple: #7c3aed;
  --bg: #f1f5f9; --card: #ffffff; --text: #0f172a; --muted: #64748b;
  --border: #e2e8f0; --radius: 14px; --shadow: 0 1px 3px rgba(0,0,0,.06), 0 4px 12px rgba(0,0,0,.04);
  --header-from: #0f172a; --header-mid: #1e3a8a; --header-to: #2563eb;
}

THEME_PLACEHOLDER {
  --pri: #1e3a8a; --blue: #2563eb; --green: #059669; --yellow: #d97706;
  --header-from: #0f172a; --header-mid: #1e3a8a; --header-to: #2563eb;
}
.modern_emerald {
  --pri: #065f46; --blue: #059669; --green: #10b981; --yellow: #d97706;
  --header-from: #064e3b; --header-mid: #059669; --header-to: #d97706;
}
.editorial_charcoal {
  --pri: #1a1a2e; --blue: #4f46e5; --green: #6b7280; --yellow: #f59e0b;
  --header-from: #0f0f1a; --header-mid: #1a1a2e; --header-to: #4f46e5;
}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     background:var(--bg);color:var(--text);line-height:1.65;-webkit-font-smoothing:antialiased}

/* ── Print ── */
@media print{
  body{background:#fff!important}
  .report-header{background:#1e3a8a!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .report-section{break-inside:avoid;box-shadow:none;border:1px solid #ddd}
  .toc-container,.no-print,.back-to-top{display:none!important}
  .report-section.collapsed .sec-body{display:block!important;max-height:none!important}
}

/* ── Header ── */
.report-header{background:linear-gradient(135deg,var(--header-from) 0%,var(--header-mid) 50%,var(--header-to) 100%);
  color:#fff;padding:56px 32px 48px;text-align:center;position:relative;overflow:hidden}
.report-header::before{content:'';position:absolute;top:-50%;right:-20%;width:400px;height:400px;
  background:radial-gradient(circle,rgba(255,255,255,.06) 0%,transparent 70%);border-radius:50%}
.report-header::after{content:'';position:absolute;bottom:-30%;left:-10%;width:300px;height:300px;
  background:radial-gradient(circle,rgba(59,130,246,.15) 0%,transparent 70%);border-radius:50%}
.report-header h1{font-size:2rem;font-weight:900;margin-bottom:6px;position:relative;z-index:1;
  letter-spacing:-.02em}
.report-header .subtitle{font-size:1.05rem;opacity:.75;font-weight:400;position:relative;z-index:1}
.report-header .meta{margin-top:20px;display:flex;gap:20px;justify-content:center;flex-wrap:wrap;
  font-size:.82rem;opacity:.8;position:relative;z-index:1}
.report-header .meta span{display:flex;align-items:center;gap:5px}
.status-badge{display:inline-block;padding:4px 14px;border-radius:20px;font-size:.72rem;font-weight:700;letter-spacing:.3px}
.status-raw{background:rgba(251,191,36,.2);color:#fcd34d;border:1px solid rgba(251,191,36,.3)}
.status-clean{background:rgba(110,231,183,.2);color:#6ee7b7;border:1px solid rgba(110,231,183,.3)}

/* ── TOC ── */
.toc-container{max-width:940px;margin:-28px auto 0;padding:0 20px;position:relative;z-index:10}
.toc-card{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);
  padding:22px 28px;border:1px solid var(--border)}
.toc-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;cursor:pointer}
.toc-header h3{font-size:.82rem;color:var(--muted);text-transform:uppercase;letter-spacing:1.2px;font-weight:700}
.toc-toggle{font-size:.75rem;color:var(--blue);font-weight:600;cursor:pointer;user-select:none}
.toc{list-style:none;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:4px}
.toc li a{text-decoration:none;color:var(--text);font-size:.84rem;font-weight:600;
  padding:7px 12px;border-radius:8px;display:flex;align-items:center;gap:8px;transition:all .15s}
.toc li a:hover{background:#eff6ff;color:var(--blue);transform:translateX(2px)}
.toc li a .toc-num{background:var(--pri);color:#fff;width:22px;height:22px;border-radius:6px;
  display:flex;align-items:center;justify-content:center;font-size:.68rem;flex-shrink:0;font-weight:700}

/* ── Content ── */
.report-content{max-width:940px;margin:28px auto;padding:0 20px 80px}
.report-section{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);
  border:1px solid var(--border);margin-bottom:20px;overflow:hidden;transition:all .25s}
.report-section:hover{box-shadow:0 2px 8px rgba(0,0,0,.04),0 8px 24px rgba(0,0,0,.06)}
.sec-header{display:flex;align-items:center;gap:12px;padding:20px 28px;cursor:pointer;user-select:none}
.sec-header:hover{background:#f8fafc}
.sec-header h2{font-size:1.1rem;font-weight:800;color:var(--pri);flex:1;margin:0;display:flex;align-items:center;gap:10px}
.sec-num{background:var(--pri);color:#fff;width:30px;height:30px;border-radius:8px;
  display:flex;align-items:center;justify-content:center;font-size:.78rem;flex-shrink:0;font-weight:700}
.sec-chevron{width:20px;height:20px;color:var(--muted);transition:transform .25s;flex-shrink:0}
.report-section.collapsed .sec-chevron{transform:rotate(-90deg)}
.report-section.collapsed .sec-body{display:none}
.sec-body{padding:0 28px 24px}
.sec-body h3{font-size:.95rem;font-weight:700;color:var(--blue);margin:18px 0 10px;
  padding-bottom:6px;border-bottom:2px solid #eff6ff}
.sec-body p{color:#374151;font-size:.88rem;margin-bottom:12px}

/* ── KPI ── */
.kpi-row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.kpi-card{flex:1;min-width:130px;background:var(--bg);border-radius:12px;padding:16px 14px;text-align:center;
  border:1px solid var(--border);transition:transform .15s}
.kpi-card:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.06)}
.kpi-val{font-size:1.5rem;font-weight:800;color:var(--text);line-height:1.2}
.kpi-label{font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.6px;margin-top:4px;font-weight:600}

/* ── Table ── */
.table-wrap{overflow-x:auto;margin-bottom:16px;border-radius:10px;border:1px solid var(--border)}
.data-table{width:100%;border-collapse:collapse;font-size:.82rem;white-space:nowrap}
.data-table th{background:var(--pri);color:#fff;padding:11px 14px;text-align:left;font-weight:700;
  position:sticky;top:0;font-size:.78rem;text-transform:uppercase;letter-spacing:.4px}
.data-table td{padding:9px 14px;border-bottom:1px solid var(--border)}
.data-table tbody tr:nth-child(even){background:#f8fafc}
.data-table tbody tr:hover{background:#eff6ff}
.data-table td:first-child{font-weight:600;color:var(--text)}

/* ── Charts ── */
.chart-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(400px,1fr));gap:16px}
.chart-card{background:var(--bg);border-radius:12px;padding:18px;text-align:center;
  border:1px solid var(--border);transition:transform .15s}
.chart-card:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.06)}
.chart-card h4{font-size:.85rem;font-weight:700;color:var(--text);margin-bottom:12px}
.chart-card img{max-width:100%;height:auto;border-radius:8px}

/* ── Insights ── */
.insight-card{background:var(--bg);border-radius:10px;padding:14px 16px;margin-bottom:10px;
  border:1px solid var(--border);transition:transform .15s}
.insight-card:hover{transform:translateX(3px)}
.insight-title{font-weight:700;font-size:.88rem;margin-bottom:4px}
.insight-desc{font-size:.82rem;color:#475569;line-height:1.5}
.insight-item{background:var(--bg);border-radius:8px;padding:12px 14px;margin-bottom:8px;font-size:.85rem;
  border:1px solid var(--border)}

/* ── Cleaning ── */
.cleaning-step{background:var(--bg);border-radius:10px;padding:14px 16px;margin-bottom:10px;
  border:1px solid var(--border)}
.log-line{font-size:.82rem;color:#475569;padding:3px 0 3px 20px;position:relative}
.log-line::before{content:'→';position:absolute;left:4px;color:var(--blue);font-weight:700}

/* ── Recommendations ── */
.recom-item{background:var(--bg);border-radius:10px;padding:16px 18px;margin-bottom:10px;
  font-size:.88rem;line-height:1.65;border:1px solid var(--border);border-left:4px solid var(--blue)}

/* ── Badges ── */
.badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:.7rem;font-weight:700;letter-spacing:.2px}
.badge-ok{background:#d1fae5;color:#065f46}
.badge-warn{background:#fef3c7;color:#92400e}
.badge-err{background:#fee2e2;color:#991b1b}

/* ── Interpretation ── */
.interp-item{background:var(--bg);border-radius:8px;padding:12px 14px;margin-bottom:6px;font-size:.85rem;
  border:1px solid var(--border)}

/* ── Data Preview ── */
.preview-note{font-size:.78rem;color:var(--muted);font-style:italic;margin-bottom:10px}

/* ── Back to Top ── */
.back-to-top{position:fixed;bottom:28px;right:28px;width:44px;height:44px;border-radius:12px;
  background:var(--pri);color:#fff;border:none;font-size:1.1rem;cursor:pointer;
  box-shadow:0 4px 16px rgba(30,58,138,.3);display:flex;align-items:center;justify-content:center;
  opacity:0;transform:translateY(20px);transition:all .3s;z-index:100}
.back-to-top.visible{opacity:1;transform:translateY(0)}
.back-to-top:hover{background:#1e40af;transform:translateY(-2px)}

/* ── Footer ── */
.report-footer{max-width:940px;margin:0 auto;padding:20px 20px 40px;text-align:center;
  font-size:.78rem;color:var(--muted);border-top:1px solid var(--border)}
.report-footer a{color:var(--blue);text-decoration:none;font-weight:600}

/* ── Search ── */
.search-box{max-width:940px;margin:0 auto 16px;padding:0 20px;position:relative}
.search-input{width:100%;padding:12px 16px 12px 44px;border:1px solid var(--border);border-radius:12px;
  font-size:.88rem;background:var(--card);color:var(--text);box-shadow:var(--shadow);outline:none;transition:border .15s}
.search-input:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(37,99,235,.1)}
.search-icon{position:absolute;left:36px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:.9rem}
.search-count{font-size:.75rem;color:var(--muted);margin-top:6px;padding-left:4px}

/* ── Responsive ── */
@media(max-width:768px){
  .report-header{padding:40px 20px 36px}
  .report-header h1{font-size:1.4rem}
  .kpi-row{flex-direction:column}
  .chart-grid{grid-template-columns:1fr}
  .toc{grid-template-columns:1fr}
  .sec-header{padding:16px 20px}
  .sec-body{padding:0 20px 20px}
  .report-header .meta{flex-direction:column;gap:8px}
}
'''


# ══════════════════════════════════════════════════════════════════════════════
# JS TEMPLATE
# ══════════════════════════════════════════════════════════════════════════════
_JS = '''
// ── Collapsible Sections ──
document.querySelectorAll('.sec-header').forEach(function(h){
  h.addEventListener('click',function(){
    this.closest('.report-section').classList.toggle('collapsed');
  });
});

// ── Back to Top ──
var btt=document.querySelector('.back-to-top');
if(btt){
  window.addEventListener('scroll',function(){
    btt.classList.toggle('visible',window.scrollY>400);
  });
  btt.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'})});
}

// ── Search ──
var searchInput=document.getElementById('reportSearch');
if(searchInput){
  searchInput.addEventListener('input',function(){
    var q=this.value.toLowerCase().trim();
    var sections=document.querySelectorAll('.report-section');
    var count=0;
    sections.forEach(function(s){
      if(!q){s.style.display='';count++;return}
      var text=s.textContent.toLowerCase();
      if(text.indexOf(q)!==-1){s.style.display='';count++}
      else{s.style.display='none'}
    });
    var sc=document.getElementById('searchCount');
    if(sc){sc.textContent=q?count+' section'+(count!==1?'s':'')+' ditemukan':''}
  });
}

// ── TOC collapse ──
var tocHeader=document.querySelector('.toc-header');
if(tocHeader){
  tocHeader.addEventListener('click',function(){
    var toc=document.querySelector('.toc');
    var toggle=document.querySelector('.toc-toggle');
    if(toc.style.display==='none'){toc.style.display='';toggle.textContent='Sembunyikan ▲'}
    else{toc.style.display='none';toggle.textContent='Tampilkan ▼'}
  });
}
'''


# ══════════════════════════════════════════════════════════════════════════════
# MAIN GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
def generate_html_report(
    dest_path,
    filename,
    df,
    quality_report,
    metrics,
    num_stats,
    cat_stats,
    auto_insights,
    cleaning_history,
    cleaning_summary,
    selected_sections=None,
    analyst_name='',
    report_title='',
    ts_chart_images=None,
    ts_insights=None,
    ts_meta=None,
    language='id',
    theme='academic_slate',
    conclusion='',
    institution='',
    return_html=False,
):
    ALL_SECTIONS = [
        'pendahuluan', 'dataset', 'kualitas', 'statistik_num',
        'statistik_cat', 'visualisasi', 'time_series', 'cleaning',
        'insight', 'rekomendasi', 'penutup'
    ]
    if not selected_sections:
        selected_sections = ALL_SECTIONS

    def active(key):
        return key in selected_sections

    now = datetime.datetime.now()
    today = now.strftime('%d %B %Y')
    time_str = now.strftime('%H:%M')
    r_title = report_title or 'Laporan Analisis Data Deskriptif'

    summary = (quality_report or {}).get('summary', {})
    total_rows = len(df) if df is not None else 0
    total_cols = len(df.columns) if df is not None else 0
    missing_c = summary.get('missing_cells', 0)
    dup_rows = summary.get('duplicate_rows', 0)
    outliers_c = summary.get('total_outliers', 0)
    needs_cl = summary.get('needs_cleaning', False)
    status_str = 'RAW DATA' if needs_cl else 'CLEAN DATA'
    completeness = round((1 - missing_c / (total_rows * total_cols if total_rows and total_cols else 1)) * 100, 1) if total_rows and total_cols else 100

    num_cols_list = [s.get('Column', '') for s in (num_stats or [])]
    cat_cols_list = [s.get('Column', '') for s in (cat_stats or [])]

    chart_images = _generate_chart_images_b64(df, num_cols_list, cat_cols_list) if active('visualisasi') else {}
    if not ts_chart_images and active('time_series') and ts_meta:
        dt_col = ts_meta.get('dt_col')
        num_col = ts_meta.get('num_col')
        if dt_col and num_col and df is not None:
            ts_chart_images = _generate_ts_chart_b64(df, dt_col, num_col, ts_meta.get('freq_label'))
    ts_chart_images = ts_chart_images or {}

    sec_labels = {
        'pendahuluan': 'Pendahuluan & Latar Belakang' if language == 'id' else 'Introduction & Background',
        'dataset': 'Deskripsi Dataset' if language == 'id' else 'Dataset Description',
        'kualitas': 'Kualitas Data' if language == 'id' else 'Data Quality',
        'statistik_num': 'Statistik Deskriptif — Numerik' if language == 'id' else 'Descriptive Statistics — Numerical',
        'statistik_cat': 'Statistik Deskriptif — Kategorikal' if language == 'id' else 'Descriptive Statistics — Categorical',
        'visualisasi': 'Visualisasi Data' if language == 'id' else 'Data Visualization',
        'time_series': 'Analisis Time Series' if language == 'id' else 'Time Series Analysis',
        'cleaning': 'Proses Data Cleaning' if language == 'id' else 'Data Cleaning Process',
        'insight': 'Temuan Kunci & Insight' if language == 'id' else 'Key Findings & Insights',
        'rekomendasi': 'Rekomendasi Strategis' if language == 'id' else 'Strategic Recommendations',
        'penutup': 'Penutup' if language == 'id' else 'Conclusion',
    }
    active_seq = [s for s in ALL_SECTIONS if s in selected_sections]

    def get_sec_num(sec):
        if sec in active_seq:
            return active_seq.index(sec) + 1
        return ""

    toc_items = []
    for sec in ALL_SECTIONS:
        if sec in selected_sections:
            num = get_sec_num(sec)
            toc_items.append(f'<li><a href="#sec-{sec}"><span class="toc-num">{num}</span>{sec_labels.get(sec, sec)}</a></li>')
    toc_html = '<ul class="toc">' + '\n'.join(toc_items) + '</ul>'

    # Data preview table
    preview_html = ''
    if df is not None and not df.empty:
        preview_df = df.head(8)
        cols_html = ''.join(f'<th>{c}</th>' for c in preview_df.columns)
        rows_html = ''
        for _, row in preview_df.iterrows():
            cells = ''.join(f'<td>{_safe(str(v)[:40])}</td>' for v in row.values)
            rows_html += f'<tr>{cells}</tr>'
        preview_html = f'''<p class="preview-note">Menampilkan 8 dari {total_rows:,} baris</p>
        <div class="table-wrap"><table class="data-table"><thead><tr>{cols_html}</tr></thead>
        <tbody>{rows_html}</tbody></table></div>'''

    sections_html = []

    # ── 1. Pendahuluan ──────────────────────────────────────────────────────
    if active('pendahuluan'):
        intro_p1 = ('Analisis Data Eksplorasi (<i>Exploratory Data Analysis — EDA</i>) merupakan langkah fundamental '
            'dalam setiap proyek analisis data. Tujuannya adalah memahami karakteristik dasar dataset, mendeteksi '
            'anomali, memverifikasi asumsi, serta merumuskan hipotesis awal sebelum pemodelan statistik atau '
            'machine learning.') if language == 'id' else (
            'Exploratory Data Analysis (EDA) is a fundamental step in every data analysis project. '
            'Its purpose is to understand the basic characteristics of the dataset, detect anomalies, '
            'verify assumptions, and formulate initial hypotheses before statistical modeling or machine learning.')
        intro_p2 = (f'Laporan ini disusun secara otomatis menggunakan platform <b>DS Generator</b> yang dikembangkan oleh '
            f'<b>Kelompok 2</b>, Program Studi Sains Data, {institution_text}.') if language == 'id' else (
            f'This report was automatically generated using the <b>DS Generator</b> platform developed by '
            f'<b>Kelompok 2</b>, Data Science Study Program, {institution_text}.')
        intro_p3 = (f'Dataset yang dianalisis adalah <b>{filename}</b> dengan <b>{total_rows:,} observasi</b> dan '
            f'<b>{total_cols} variabel</b> ({len(num_cols_list)} numerik, {len(cat_cols_list)} kategorikal). '
            f'Tingkat kelengkapan data mencapai <b>{completeness}%</b>.') if language == 'id' else (
            f'The analyzed dataset is <b>{filename}</b> with <b>{total_rows:,} observations</b> and '
            f'<b>{total_cols} variables</b> ({len(num_cols_list)} numerical, {len(cat_cols_list)} categorical). '
            f'Data completeness reaches <b>{completeness}%</b>.')
        sections_html.append(f'''
        <section id="sec-pendahuluan" class="report-section">
          <div class="sec-header">
            <h2><span class="sec-num">{get_sec_num('pendahuluan')}</span> {sec_labels['pendahuluan']}</h2>
            <svg class="sec-chevron" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/></svg>
          </div>
          <div class="sec-body">
            <p>{intro_p1}</p>
            <p>{intro_p2}</p>
            <p>{intro_p3}</p>
          </div>
        </section>''')

    # ── 2. Dataset ──────────────────────────────────────────────────────────
    if active('dataset'):
        sections_html.append(f'''
        <section id="sec-dataset" class="report-section">
          <div class="sec-header">
            <h2><span class="sec-num">{get_sec_num('dataset')}</span> Deskripsi Dataset</h2>
            <svg class="sec-chevron" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/></svg>
          </div>
          <div class="sec-body">
            <div class="kpi-row">
              <div class="kpi-card" style="border-top:3px solid #3b82f6"><div class="kpi-val">{total_rows:,}</div><div class="kpi-label">Total Baris</div></div>
              <div class="kpi-card" style="border-top:3px solid #10b981"><div class="kpi-val">{total_cols}</div><div class="kpi-label">Total Kolom</div></div>
              <div class="kpi-card" style="border-top:3px solid #059669"><div class="kpi-val">{completeness}%</div><div class="kpi-label">Kelengkapan</div></div>
              <div class="kpi-card" style="border-top:3px solid #f59e0b"><div class="kpi-val">{missing_c:,}</div><div class="kpi-label">Missing Values</div></div>
              <div class="kpi-card" style="border-top:3px solid #ef4444"><div class="kpi-val">{dup_rows}</div><div class="kpi-label">Duplikat</div></div>
              <div class="kpi-card" style="border-top:3px solid #8b5cf6"><div class="kpi-val">{outliers_c}</div><div class="kpi-label">Outliers</div></div>
            </div>
            <h3>Komposisi Variabel</h3>
            <div class="table-wrap"><table class="data-table">
              <thead><tr><th>Tipe Variabel</th><th>Jumlah</th><th>Contoh Variabel</th></tr></thead>
              <tbody>
                <tr><td>Numerik (Kuantitatif)</td><td>{len(num_cols_list)}</td><td>{', '.join(num_cols_list[:6]) or '—'}</td></tr>
                <tr><td>Kategorikal (Kualitatif)</td><td>{len(cat_cols_list)}</td><td>{', '.join(cat_cols_list[:6]) or '—'}</td></tr>
              </tbody>
            </table></div>
            <h3>Preview Data</h3>
            {preview_html}
          </div>
        </section>''')

    # ── 3. Kualitas Data ────────────────────────────────────────────────────
    if active('kualitas') and quality_report:
        col_quality = quality_report.get('columns', [])
        rows_html = ''
        for c in col_quality:
            st = c.get('status', 'ok')
            badge_cls = 'badge-ok' if st == 'ok' else 'badge-warn' if st == 'warning' else 'badge-err'
            badge_txt = 'OK' if st == 'ok' else 'Warning' if st == 'warning' else 'Error'
            rows_html += f'''<tr>
              <td>{c.get('column','—')}</td><td>{c.get('dtype','—')}</td>
              <td>{c.get('missing',0)} ({c.get('missing_pct',0)}%)</td>
              <td>{c.get('unique','—')}</td><td>{c.get('outliers',0)}</td>
              <td><span class="badge {badge_cls}">{badge_txt}</span></td>
            </tr>'''
        sections_html.append(f'''
        <section id="sec-kualitas" class="report-section">
          <div class="sec-header">
            <h2><span class="sec-num">{get_sec_num('kualitas')}</span> Kualitas Data</h2>
            <svg class="sec-chevron" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/></svg>
          </div>
          <div class="sec-body">
            <div class="table-wrap"><table class="data-table">
              <thead><tr><th>Kolom</th><th>Tipe</th><th>Missing</th><th>Unique</th><th>Outliers</th><th>Status</th></tr></thead>
              <tbody>{rows_html}</tbody>
            </table></div>
          </div>
        </section>''')

    # ── 4. Statistik Numerik ────────────────────────────────────────────────
    if active('statistik_num') and num_stats:
        rows_html = ''
        for s in num_stats:
            rows_html += f'''<tr>
              <td>{s.get('Column','—')}</td><td>{s.get('Count','—')}</td><td>{s.get('Missing','—')}</td>
              <td>{s.get('Mean','—')}</td><td>{s.get('Median','—')}</td><td>{s.get('Std Dev','—')}</td>
              <td>{s.get('Min','—')}</td><td>{s.get('Q25','—')}</td><td>{s.get('Q75','—')}</td>
              <td>{s.get('Max','—')}</td><td>{s.get('Skewness','—')}</td>
            </tr>'''
        interp_html = ''
        for s in num_stats:
            col = s.get('Column', '?')
            skew = s.get('Skewness', 0)
            mean = s.get('Mean', 0)
            median = s.get('Median', 0)
            std = s.get('Std Dev', '—')
            try:
                sf = float(str(skew))
                if abs(sf) < 0.5:
                    skew_desc = 'cenderung <b>simetris</b>'
                elif sf > 0.5:
                    skew_desc = f'miring ke kanan (<i>right-skewed</i>, skewness={skew})'
                else:
                    skew_desc = f'miring ke kiri (<i>left-skewed</i>, skewness={skew})'
            except Exception:
                skew_desc = '—'
            interp_html += f'''<div class="interp-item">
              <b>{col}</b>: distribusi {skew_desc}. Rata-rata {_safe(mean)}, median {_safe(median)}, standar deviasi {_safe(std)}.
            </div>'''
        sections_html.append(f'''
        <section id="sec-statistik_num" class="report-section">
          <div class="sec-header">
            <h2><span class="sec-num">{get_sec_num('statistik_num')}</span> Statistik Deskriptif — Numerik</h2>
            <svg class="sec-chevron" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/></svg>
          </div>
          <div class="sec-body">
            <div class="table-wrap"><table class="data-table">
              <thead><tr><th>Kolom</th><th>Count</th><th>Missing</th><th>Mean</th><th>Median</th><th>Std Dev</th><th>Min</th><th>Q25</th><th>Q75</th><th>Max</th><th>Skew</th></tr></thead>
              <tbody>{rows_html}</tbody>
            </table></div>
            <h3>Interpretasi per Variabel</h3>
            {interp_html}
          </div>
        </section>''')

    # ── 5. Statistik Kategorikal ────────────────────────────────────────────
    if active('statistik_cat') and cat_stats:
        rows_html = ''
        for s in cat_stats:
            rows_html += f'''<tr>
              <td>{s.get('Column','—')}</td><td>{s.get('Unique','—')}</td>
              <td>{_safe(s.get('Mode'))}</td><td>{_safe(s.get('Mode Freq'))}</td>
              <td>{_safe(s.get('Mode %'))}</td><td>{s.get('Missing Count',0)}</td>
            </tr>'''
        interp_html = ''
        for s in cat_stats:
            col = s.get('Column', '?')
            unique = s.get('Unique', '?')
            mode = _safe(s.get('Mode'))
            mode_pct = _safe(s.get('Mode %'))
            interp_html += f'''<div class="interp-item">
              <b>{col}</b>: {unique} kategori unik. Kategori terdominan "<b>{mode}</b>" dengan proporsi {mode_pct}.
            </div>'''
        sections_html.append(f'''
        <section id="sec-statistik_cat" class="report-section">
          <div class="sec-header">
            <h2><span class="sec-num">{get_sec_num('statistik_cat')}</span> Statistik Deskriptif — Kategorikal</h2>
            <svg class="sec-chevron" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/></svg>
          </div>
          <div class="sec-body">
            <div class="table-wrap"><table class="data-table">
              <thead><tr><th>Kolom</th><th>Unique</th><th>Mode</th><th>Frekuensi</th><th>Mode %</th><th>Missing</th></tr></thead>
              <tbody>{rows_html}</tbody>
            </table></div>
            <h3>Interpretasi per Variabel</h3>
            {interp_html}
          </div>
        </section>''')

    # ── 6. Visualisasi ──────────────────────────────────────────────────────
    if active('visualisasi') and chart_images:
        charts_html = ''
        chart_titles_map = {
            'heatmap': 'Matriks Korelasi Pearson',
            'scatter': 'Scatter Plot + Trend Line',
            'boxplot': 'Boxplot Variabel Numerik',
        }
        for key, b64 in chart_images.items():
            if key.startswith('hist_'):
                title = f'Distribusi {key[5:]}'
            elif key.startswith('bar_'):
                title = f'Frekuensi {key[4:]}'
            else:
                title = chart_titles_map.get(key, key)
            charts_html += f'''<div class="chart-card">
              <h4>{title}</h4>
              <img src="data:image/png;base64,{b64}" alt="{title}" loading="lazy">
            </div>'''
        sections_html.append(f'''
        <section id="sec-visualisasi" class="report-section">
          <div class="sec-header">
            <h2><span class="sec-num">{get_sec_num('visualisasi')}</span> Visualisasi Data</h2>
            <svg class="sec-chevron" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/></svg>
          </div>
          <div class="sec-body">
            <div class="chart-grid">{charts_html}</div>
          </div>
        </section>''')

    # ── 7. Time Series ──────────────────────────────────────────────────────
    if active('time_series') and ts_chart_images and ts_meta:
        ts_dt = ts_meta.get('dt_col', '?')
        ts_nc = ts_meta.get('num_col', '?')
        ts_freq = ts_meta.get('freq_label', 'Auto')
        ts_n = ts_meta.get('n_points', '?')
        ts_dir = ts_meta.get('direction', '?')
        ts_r2 = ts_meta.get('r_squared', '?')
        ts_start = ts_meta.get('date_start', '?')
        ts_end = ts_meta.get('date_end', '?')
        ts_slope = ts_meta.get('slope', '?')

        ts_chart_titles = {
            'ts_line': 'Line Chart — Data Time Series',
            'ts_trend': 'Trend Analysis — Regresi Linear OLS',
            'ts_ma': 'Moving Average — Perataan Data',
            'ts_rolling': 'Rolling Mean — Rata-rata Bergulir',
            'ts_overview': 'Overview — Panel 4 Variabel',
        }
        ts_charts_html = ''
        for ck in ['ts_line', 'ts_trend', 'ts_ma', 'ts_rolling', 'ts_overview']:
            if ck in ts_chart_images:
                ts_charts_html += f'''<div class="chart-card">
                  <h4>{ts_chart_titles.get(ck, ck)}</h4>
                  <img src="data:image/png;base64,{ts_chart_images[ck]}" alt="{ck}" loading="lazy">
                </div>'''

        insights_html = ''
        if ts_insights:
            for ins in ts_insights[:6]:
                t = ins.get('type', 'info')
                color = '#10b981' if t == 'success' else '#f59e0b' if t == 'warning' else '#ef4444' if t == 'danger' else '#3b82f6'
                insights_html += f'''<div class="insight-card" style="border-left:4px solid {color}">
                  <div class="insight-title" style="color:{color}">{ins.get("title","")}</div>
                  <div class="insight-desc">{ins.get("desc","")}</div>
                </div>'''

        try:
            direction_desc = {
                'UPWARD': 'Tren Naik ↑',
                'DOWNWARD': 'Tren Turun ↓',
                'STABLE': 'Stabil →',
            }.get(str(ts_dir).upper(), str(ts_dir))
        except Exception:
            direction_desc = str(ts_dir)

        sections_html.append(f'''
        <section id="sec-time_series" class="report-section">
          <div class="sec-header">
            <h2><span class="sec-num">{get_sec_num('time_series')}</span> Analisis Time Series</h2>
            <svg class="sec-chevron" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/></svg>
          </div>
          <div class="sec-body">
            <div class="kpi-row">
              <div class="kpi-card" style="border-top:3px solid #3b82f6"><div class="kpi-val">{ts_dt}</div><div class="kpi-label">Kolom Waktu</div></div>
              <div class="kpi-card" style="border-top:3px solid #10b981"><div class="kpi-val">{ts_nc}</div><div class="kpi-label">Kolom Numerik</div></div>
              <div class="kpi-card" style="border-top:3px solid #f59e0b"><div class="kpi-val">{ts_freq}</div><div class="kpi-label">Frekuensi</div></div>
              <div class="kpi-card" style="border-top:3px solid #ef4444"><div class="kpi-val">{direction_desc}</div><div class="kpi-label">Arah Tren</div></div>
              <div class="kpi-card" style="border-top:3px solid #8b5cf6"><div class="kpi-val">{ts_r2}</div><div class="kpi-label">R-squared</div></div>
            </div>
            <p>Analisis time series terhadap variabel <b>{ts_nc}</b> dengan dimensi waktu <b>{ts_dt}</b> ({ts_freq}).
            Rentang: {ts_start} s.d. {ts_end}, {ts_n} observasi. Slope = {ts_slope}, R² = {ts_r2}.</p>
            {insights_html}
            <h3>Visualisasi Time Series</h3>
            <div class="chart-grid">{ts_charts_html}</div>
          </div>
        </section>''')

    # ── 8. Cleaning ─────────────────────────────────────────────────────────
    if active('cleaning') and cleaning_history:
        sb = cleaning_summary or {}
        log_html = ''
        for i, h in enumerate(cleaning_history or []):
            label = h.get('label', f'Operasi {i+1}')
            logs = h.get('log', [])
            log_lines = ''.join(f'<div class="log-line">{_safe(l)}</div>' for l in (logs if isinstance(logs, list) else [str(logs)]))
            log_html += f'<div class="cleaning-step"><b>Langkah {i+1}:</b> {label}{log_lines}</div>'
        sections_html.append(f'''
        <section id="sec-cleaning" class="report-section">
          <div class="sec-header">
            <h2><span class="sec-num">{get_sec_num('cleaning')}</span> Proses Data Cleaning</h2>
            <svg class="sec-chevron" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/></svg>
          </div>
          <div class="sec-body">
            <div class="table-wrap"><table class="data-table">
              <thead><tr><th>Metrik</th><th>Sebelum</th><th>Sesudah</th><th>Perubahan</th></tr></thead>
              <tbody>
                <tr><td>Jumlah Baris</td><td>{sb.get('rows_before','—')}</td><td>{sb.get('rows_after','—')}</td>
                    <td>Δ {abs(sb.get('rows_before',0) - sb.get('rows_after',0))}</td></tr>
                <tr><td>Jumlah Kolom</td><td>{sb.get('cols_before','—')}</td><td>{sb.get('cols_after','—')}</td>
                    <td>Δ {abs(sb.get('cols_before',0) - sb.get('cols_after',0))}</td></tr>
                <tr><td>Missing Values</td><td>{sb.get('missing_before','—')}</td><td>{sb.get('missing_after','—')}</td>
                    <td>Δ {abs(sb.get('missing_before',0) - sb.get('missing_after',0))}</td></tr>
              </tbody>
            </table></div>
            <h3>Log Proses Cleaning</h3>
            {log_html}
          </div>
        </section>''')

    # ── 9. Insight ──────────────────────────────────────────────────────────
    if active('insight') and auto_insights:
        ins_html = ''
        for i, ins in enumerate(auto_insights[:15]):
            t = ins.get('type', 'info')
            color = '#10b981' if t == 'success' else '#f59e0b' if t == 'warning' else '#ef4444' if t == 'danger' else '#3b82f6'
            icon = '✓' if t == 'success' else '⚠' if t == 'warning' else '✗' if t == 'danger' else 'ℹ'
            ins_html += f'''<div class="insight-card" style="border-left:4px solid {color}">
              <div class="insight-title" style="color:{color}">{icon} {i+1}. {_safe(ins.get('title'))}</div>
              <div class="insight-desc">{_safe(ins.get('desc'))}</div>
            </div>'''
        sections_html.append(f'''
        <section id="sec-insight" class="report-section">
          <div class="sec-header">
            <h2><span class="sec-num">{get_sec_num('insight')}</span> Temuan Kunci & Insight</h2>
            <svg class="sec-chevron" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/></svg>
          </div>
          <div class="sec-body">{ins_html}</div>
        </section>''')

    # ── 10. Rekomendasi ─────────────────────────────────────────────────────
    if active('rekomendasi'):
        recoms = []
        if missing_c > 0:
            recoms.append(f'<div class="recom-item"><b>R1. Penanganan Missing Values</b><br>Dataset memiliki {missing_c:,} sel kosong ({round(missing_c/(total_rows*total_cols)*100,2) if total_rows and total_cols else 0}%). Gunakan imputasi mean/median untuk variabel numerik dan modus untuk kategorikal. Pertimbangkan KNN imputation untuk data yang kompleks.</div>')
        if dup_rows > 0:
            recoms.append(f'<div class="recom-item"><b>R2. Pembersihan Duplikat</b><br>Ditemukan {dup_rows} baris duplikat. Lakukan deduplication dengan mempertahankan observasi paling relevan untuk menjaga integritas analisis.</div>')
        if outliers_c > 0:
            recoms.append(f'<div class="recom-item"><b>R3. Investigasi Outlier</b><br>Terdeteksi {outliers_c} outlier menggunakan metode IQR. Validasi apakah nilai ekstrem valid secara bisnis atau merupakan error pencatatan. Terapkan IQR capping jika diperlukan.</div>')
        if num_stats:
            recoms.append('<div class="recom-item"><b>R4. Transformasi & Standardisasi</b><br>Transformasi variabel numerik yang highly skewed (|skewness| > 1) menggunakan log atau Box-Cox. Standardisasi fitur menggunakan StandardScaler sebelum pemodelan.</div>')
        recoms.append('<div class="recom-item"><b>R5. Train-Test Split & Validasi</b><br>Bagi dataset menjadi training (80%) dan testing (20%) menggunakan stratified split. Lakukan cross-validation k-fold (k=5) untuk evaluasi model yang robust.</div>')
        sections_html.append(f'''
        <section id="sec-rekomendasi" class="report-section">
          <div class="sec-header">
            <h2><span class="sec-num">{get_sec_num('rekomendasi')}</span> Rekomendasi Strategis</h2>
            <svg class="sec-chevron" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/></svg>
          </div>
          <div class="sec-body">{''.join(recoms)}</div>
        </section>''')

    # ── 11. Penutup ─────────────────────────────────────────────────────────
    if active('penutup'):
        conclusion_html = ''
        if conclusion:
            conclusion_html = f'<div style="background:#f0fdf4;border-left:4px solid var(--green);padding:16px 20px;border-radius:8px;margin-bottom:16px"><b>{"Kesimpulan Kustom" if language == "id" else "Custom Conclusion"}:</b><br>{conclusion}</div>'
        penutup_p1 = (f'Laporan ini disusun oleh <b>{analyst_name or "Kelompok 2 ITSB"}</b> pada tanggal <b>{today}</b>, pukul <b>{time_str} WIB</b>.') if language == 'id' else (
            f'This report was prepared by <b>{analyst_name or "Kelompok 2 ITSB"}</b> on <b>{today}</b> at <b>{time_str}</b>.')
        penutup_p2 = f'{footer_text} <b>DS Generator Platform</b> — {footer_org}.'
        sections_html.append(f'''
        <section id="sec-penutup" class="report-section">
          <div class="sec-header">
            <h2><span class="sec-num">{get_sec_num('penutup')}</span> {sec_labels['penutup']}</h2>
            <svg class="sec-chevron" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/></svg>
          </div>
          <div class="sec-body">
            {conclusion_html}
            <p>{penutup_p1}</p>
            <p>{penutup_p2}</p>
          </div>
        </section>''')

    # ════════════════════════════════════════════════════════════════════════
    # ASSEMBLE
    # ════════════════════════════════════════════════════════════════════════
    theme_class = theme if theme in ('academic_slate', 'modern_emerald', 'editorial_charcoal') else 'academic_slate'
    if theme_class == 'academic_slate':
        theme_class = ''
    body_class = f' class="{theme_class}"' if theme_class else ''
    css_cleaned = _CSS.replace('THEME_PLACEHOLDER', f'.{theme_class}' if theme_class else ':root')

    subtitle_text = 'Exploratory Data Analysis Report' if language == 'id' else 'Exploratory Data Analysis Report'
    toc_title = f'Daftar Isi ({len(selected_sections)} sections)' if language == 'id' else f'Table of Contents ({len(selected_sections)} sections)'
    toc_hide = 'Sembunyikan' if language == 'id' else 'Hide'
    search_placeholder = 'Cari section, kolom, atau insight...' if language == 'id' else 'Search sections, columns, or insights...'
    footer_text = 'Auto-generated by' if language == 'id' else 'Auto-generated by'
    footer_org = 'Institut Teknologi Sains Bandung (ITSB)' if language == 'id' else 'Institut Teknologi Sains Bandung (ITSB)'
    back_to_top = 'Kembali ke atas' if language == 'id' else 'Back to top'
    institution_text = institution or ('Institut Teknologi Sains Bandung' if language == 'id' else 'Institut Teknologi Sains Bandung')
    status_raw = 'RAW DATA' if language == 'id' else 'RAW DATA'
    status_clean = 'CLEAN DATA' if language == 'id' else 'CLEAN DATA'
    baris_text = 'baris' if language == 'id' else 'rows'
    kolom_text = 'kolom' if language == 'id' else 'columns'
    menampilkan_text = 'Menampilkan' if language == 'id' else 'Showing'
    dari_text = 'dari' if language == 'id' else 'of'
    baris_lower = 'baris' if language == 'id' else 'rows'

    html = f'''<!DOCTYPE html>
<html lang="{language}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{r_title} — {filename}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>{css_cleaned}</style>
</head>
<body{body_class}>

<div class="report-header">
  <h1>{r_title}</h1>
  <div class="subtitle">{subtitle_text}</div>
  <div class="meta">
    <span>📊 {filename}</span>
    <span>📋 {total_rows:,} {baris_text} × {total_cols} {kolom_text}</span>
    <span>Status: <span class="status-badge {'status-raw' if needs_cl else 'status-clean'}">{status_raw if needs_cl else status_clean}</span></span>
    <span>📅 {today} {time_str}</span>
    <span>👤 {analyst_name or 'Kelompok 2 ITSB'}</span>
  </div>
</div>

<div class="toc-container no-print">
  <div class="toc-card">
    <div class="toc-header">
      <h3>📑 {toc_title}</h3>
      <span class="toc-toggle">{toc_hide} ▲</span>
    </div>
    {toc_html}
  </div>
</div>

<div class="search-box no-print">
  <svg class="search-icon" width="18" height="18" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z"/></svg>
  <input type="text" id="reportSearch" class="search-input" placeholder="{search_placeholder}">
  <div id="searchCount" class="search-count"></div>
</div>

<div class="report-content">
  {''.join(sections_html)}
</div>

<div class="report-footer">
  <p>{footer_text} <a href="#">DS Generator Platform</a> — {footer_org}</p>
  <p>Kelompok 2 • {today}</p>
</div>

<button class="back-to-top no-print" title="{back_to_top}">↑</button>

<script>{_JS}</script>
</body>
</html>'''

    if return_html:
        return html

    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return True
