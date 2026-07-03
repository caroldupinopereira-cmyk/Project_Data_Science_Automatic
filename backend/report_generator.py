"""
report_generator.py — DS Generator Kelompok 2 ITSB
Fungsi generate PDF report lengkap dan customizable.
"""

import os
import datetime
import tempfile
import traceback
import pandas as pd
import numpy as np
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether, ListFlowable, ListItem, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.pdfgen import canvas as rl_canvas
from io import BytesIO


# ─── Warna Brand ──────────────────────────────────────────────────────────────
C_NAVY   = colors.HexColor('#1e3a8a')
C_BLUE   = colors.HexColor('#2563eb')
C_CYAN   = colors.HexColor('#06b6d4')
C_GREEN  = colors.HexColor('#059669')
C_YELLOW = colors.HexColor('#d97706')
C_RED    = colors.HexColor('#dc2626')
C_GRAY   = colors.HexColor('#64748b')
C_LIGHT  = colors.HexColor('#f1f5f9')
C_WHITE  = colors.white
C_BLACK  = colors.HexColor('#0f172a')
C_ROW2   = colors.HexColor('#f8fafc')


# ─── NumberedCanvas ───────────────────────────────────────────────────────────
class NumberedCanvas(rl_canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_page_decorations(self, total):
        self.saveState()
        W, H = A4

        if self._pageNumber == 1:
            self.restoreState()
            return

        self.setFillColor(C_NAVY)
        self.rect(0, H - 36, W, 36, fill=1, stroke=0)
        self.setFillColor(C_WHITE)
        self.setFont('Helvetica-Bold', 8)
        self.drawString(cm*1.5, H - 22, 'DS Generator — Laporan Analisis Data Deskriptif')
        self.setFont('Helvetica', 8)
        self.drawRightString(W - cm*1.5, H - 22, 'Kelompok 2 | Institut Teknologi Sains Bandung')

        self.setFillColor(C_NAVY)
        self.rect(0, 0, W, 28, fill=1, stroke=0)
        self.setFillColor(C_WHITE)
        self.setFont('Helvetica', 7.5)
        gen_time = datetime.datetime.now().strftime('%d %B %Y')
        self.drawString(cm*1.5, 9, f'Digenerate: {gen_time}')
        self.drawCentredString(W/2, 9, 'RAHASIA — Hanya untuk keperluan akademik')
        self.setFont('Helvetica-Bold', 8)
        self.drawRightString(W - cm*1.5, 9, f'Halaman {self._pageNumber} dari {total}')

        self.restoreState()


def _safe(val, default='—'):
    if val is None:
        return default
    if isinstance(val, float) and np.isnan(val):
        return default
    s = str(val).strip()
    return s if s else default


def _make_styles():
    base = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, parent=base['Normal'], **kw)

    return {
        'cover_title'  : S('CoverTitle',   fontName='Helvetica-Bold',  fontSize=28, leading=34, textColor=C_WHITE,  spaceAfter=10),
        'cover_sub'    : S('CoverSub',     fontName='Helvetica',        fontSize=13, leading=18, textColor=colors.HexColor('#93c5fd'), spaceAfter=6),
        'cover_meta'   : S('CoverMeta',    fontName='Helvetica',        fontSize=10, leading=14, textColor=colors.HexColor('#cbd5e1')),
        'bab'          : S('Bab',          fontName='Helvetica-Bold',   fontSize=15, leading=20, textColor=C_NAVY,   spaceBefore=20, spaceAfter=8),
        'subbab'       : S('SubBab',       fontName='Helvetica-Bold',   fontSize=11, leading=15, textColor=C_BLUE,   spaceBefore=14, spaceAfter=6, keepWithNext=1),
        'body'         : S('Body',         fontName='Helvetica',        fontSize=9,  leading=14, textColor=colors.HexColor('#374151'), spaceAfter=8, alignment=4),
        'body_bold'    : S('BodyBold',     fontName='Helvetica-Bold',   fontSize=9,  leading=14, textColor=C_BLACK,  spaceAfter=6),
        'caption'      : S('Caption',      fontName='Helvetica',        fontSize=8,  leading=11, textColor=C_GRAY,   spaceAfter=10, alignment=1),
        'th'           : S('TH',           fontName='Helvetica-Bold',   fontSize=8,  leading=10, textColor=C_WHITE),
        'td'           : S('TD',           fontName='Helvetica',        fontSize=8,  leading=10, textColor=C_BLACK),
        'td_mono'      : S('TDMono',       fontName='Courier',          fontSize=7.5,leading=10, textColor=C_BLACK),
        'insight_title': S('InsightT',     fontName='Helvetica-Bold',   fontSize=9,  leading=12, textColor=C_NAVY,   spaceAfter=3),
        'insight_body' : S('InsightB',     fontName='Helvetica',        fontSize=8.5,leading=13, textColor=colors.HexColor('#374151'), spaceAfter=4),
        'quote'        : S('Quote',        fontName='Helvetica-Oblique',fontSize=9,  leading=13, textColor=C_GRAY,   leftIndent=16, spaceBefore=6, spaceAfter=6),
        'bullet'       : S('Bullet',       fontName='Helvetica',        fontSize=9,  leading=13, textColor=colors.HexColor('#374151'), leftIndent=16, firstLineIndent=-8, spaceAfter=4),
    }


def _hr(story, color=None):
    story.append(HRFlowable(width='100%', thickness=0.5, color=color or C_LIGHT, spaceAfter=10, spaceBefore=4))


def _section_label(story, styles, num, title):
    data = [[Paragraph(f'Bab {num} — {title}', styles['bab'])]]
    t = Table(data, colWidths=[16.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), C_LIGHT),
        ('LEFTPADDING',   (0,0), (-1,-1), 12),
        ('RIGHTPADDING',  (0,0), (-1,-1), 12),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LINEAFTER',     (0,0), (0,-1),  3, C_BLUE),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))


def _kpi_table(story, styles, items):
    n   = len(items)
    W   = 16.5 * cm / n
    row = [Paragraph(f'<b><font size=14>{v}</font></b><br/><font size=7 color="#64748b">{lbl}</font>', styles['body'])
            for lbl, v, _ in items]
    bg  = [c for _, _, c in items]

    t = Table([row], colWidths=[W]*n)
    ts = [
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('INNERGRID',     (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BOX',           (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
    ]
    for i, c in enumerate(bg):
        ts.append(('BACKGROUND', (i,0), (i,0), colors.HexColor(c)))
    t.setStyle(TableStyle(ts))
    story.append(t)
    story.append(Spacer(1, 12))


def _data_table(story, styles, headers, rows, col_widths, caption=None):
    data = [[Paragraph(str(h), styles['th']) for h in headers]]
    for r in rows:
        data.append([Paragraph(_safe(c), styles['td']) for c in r])

    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  C_NAVY),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [C_WHITE, C_ROW2]),
        ('GRID',          (0,0), (-1,-1), 0.4, colors.HexColor('#e2e8f0')),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE',      (0,0), (-1,-1), 8),
    ]))
    story.append(t)
    if caption:
        story.append(Paragraph(caption, styles['caption']))
    story.append(Spacer(1, 10))


def _auto_interp_numeric(col, stats):
    mean   = stats.get('Mean',     'N/A')
    median = stats.get('Median',   'N/A')
    std    = stats.get('Std Dev',  'N/A')
    skew   = stats.get('Skewness', 'N/A')
    mn     = stats.get('Min',      'N/A')
    mx     = stats.get('Max',      'N/A')

    interp = f'Variabel <b>{col}</b> memiliki nilai rata-rata sebesar <b>{mean}</b> '
    interp += f'dengan nilai tengah (median) <b>{median}</b>. '

    try:
        s = float(str(skew).replace(',',''))
        if abs(s) < 0.5:
            interp += 'Distribusi data cenderung simetris (|skewness| < 0,5), '
            interp += 'mengindikasikan data mendekati distribusi normal. '
        elif s > 0.5:
            interp += f'Distribusi data miring ke kanan (<i>right-skewed</i>, skewness = {skew}), '
            interp += 'artinya terdapat beberapa nilai ekstrem tinggi yang menarik rata-rata ke atas. '
        else:
            interp += f'Distribusi data miring ke kiri (<i>left-skewed</i>, skewness = {skew}), '
            interp += 'artinya terdapat beberapa nilai ekstrem rendah. '
    except Exception:
        pass

    interp += f'Rentang nilai berkisar antara <b>{mn}</b> hingga <b>{mx}</b> '
    interp += f'dengan standar deviasi <b>{std}</b>. '

    try:
        if float(str(std).replace(',','')) / (float(str(mean).replace(',','')) + 1e-9) > 0.5:
            interp += 'Nilai standar deviasi yang relatif besar mengindikasikan variabilitas data yang tinggi, '
            interp += 'sehingga perlu dilakukan investigasi lebih lanjut terhadap penyebab keragaman nilai tersebut.'
        else:
            interp += 'Nilai standar deviasi yang relatif kecil menunjukkan data cukup homogen dan konsisten.'
    except Exception:
        pass

    return interp


def _auto_interp_categorical(col, stats):
    unique = stats.get('Unique',    'N/A')
    mode   = stats.get('Mode',      'N/A')
    mode_p = stats.get('Mode %',    'N/A')
    miss   = stats.get('Missing Count', 0)

    interp = f'Variabel kategorikal <b>{col}</b> memiliki <b>{unique} kategori unik</b>. '
    interp += f'Kategori yang paling dominan adalah "<b>{mode}</b>" '
    interp += f'dengan frekuensi kemunculan sebesar <b>{mode_p}%</b> dari total data. '

    try:
        u = int(str(unique))
        if u <= 5:
            interp += 'Jumlah kategori yang sedikit menunjukkan variabel ini bersifat ordinal atau nominal terbatas, '
            interp += 'cocok untuk analisis frekuensi dan cross-tabulation. '
        elif u <= 20:
            interp += 'Variabel ini memiliki jumlah kategori yang moderat, '
            interp += 'berpotensi untuk dijadikan fitur dalam pemodelan machine learning setelah encoding. '
        else:
            interp += 'Variabel ini memiliki kardinalitas tinggi (banyak kategori unik), '
            interp += 'disarankan untuk dikelompokkan atau di-encode dengan teknik target encoding. '
    except Exception:
        pass

    if miss and int(str(miss)) > 0:
        interp += f'Terdapat <b>{miss} nilai kosong</b> yang perlu diperhatikan dalam proses preprocessing.'

    return interp


# ─── GENERATE CHART IMAGES FOR PDF ─────────────────────────────────────────────
def generate_chart_images(df, num_cols_list=None, cat_cols_list=None, selected_charts=None):
    """
    Generate static chart images (PNG bytes) from DataFrame for PDF visualisasi.
    Per-column chart keys: histogram_Age, boxplot_Age, bar_Gender, pie_Gender,
                           heatmap_all, scatter_Age_vs_Income, box_Income_by_Gender
    Returns dict: { 'histogram_Age': bytes, ... }
    """
    import io
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    charts = {}
    if df is None or df.empty:
        return charts

    df_work = df.copy()

    real_num = []
    for c in (num_cols_list or df_work.select_dtypes(include=[np.number]).columns.tolist()):
        if c in df_work.columns:
            converted = pd.to_numeric(df_work[c], errors='coerce')
            if converted.notna().sum() > len(df_work) * 0.5:
                real_num.append(c)

    real_cat = []
    for c in (cat_cols_list or df_work.select_dtypes(exclude=[np.number]).columns.tolist()):
        if c in df_work.columns and c not in real_num:
            real_cat.append(c)

    if not real_num and not real_cat:
        return charts

    max_rows = 500
    if len(df_work) > max_rows:
        df_plot = df_work.sample(n=max_rows, random_state=42)
    else:
        df_plot = df_work.copy()

    for c in real_num:
        df_plot[c] = pd.to_numeric(df_plot[c], errors='coerce')

    plt.rcParams.update({
        'font.size': 9, 'axes.titlesize': 11, 'axes.labelsize': 9,
        'figure.facecolor': 'white', 'axes.facecolor': '#f8fafc',
        'axes.grid': True, 'grid.alpha': 0.3,
    })

    palette = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316', '#6366f1']

    if selected_charts is None:
        want = None
    else:
        want = set(selected_charts)

    # ── Per-column histogram ────────────────────────────────────────────────
    for col in real_num:
        key = f'histogram_{col}'
        if want is not None and key not in want:
            continue
        try:
            fig, ax = plt.subplots(figsize=(6, 4))
            vals = df_plot[col].dropna()
            if len(vals) < 2:
                continue
            ax.hist(vals, bins=20, color='#3b82f6', edgecolor='white', alpha=0.85)
            ax.set_title(f'Distribusi {col}', fontweight='bold')
            ax.set_xlabel(col)
            ax.set_ylabel('Frekuensi')
            fig.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
            plt.close(fig)
            charts[key] = buf.getvalue()
        except Exception as e:
            print(f'[PDF chart] {key} error: {e}')
            plt.close('all')

    # ── Per-column boxplot ──────────────────────────────────────────────────
    for col in real_num:
        key = f'boxplot_{col}'
        if want is not None and key not in want:
            continue
        try:
            vals = df_plot[col].dropna()
            if len(vals) < 2:
                continue
            fig, ax = plt.subplots(figsize=(4, 5))
            bp = ax.boxplot(vals, patch_artist=True,
                           boxprops=dict(facecolor='#93c5fd', edgecolor='#2563eb'),
                           medianprops=dict(color='#dc2626', linewidth=2),
                           whiskerprops=dict(color='#64748b'),
                           capprops=dict(color='#64748b'))
            ax.set_title(f'Boxplot {col}', fontweight='bold')
            ax.set_ylabel(col)
            fig.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
            plt.close(fig)
            charts[key] = buf.getvalue()
        except Exception as e:
            print(f'[PDF chart] {key} error: {e}')
            plt.close('all')

    # ── Per-column bar chart (categorical) ─────────────────────────────────
    for col in real_cat:
        key = f'bar_{col}'
        if want is not None and key not in want:
            continue
        try:
            vc = df_plot[col].value_counts().head(10)
            if len(vc) < 1:
                continue
            fig, ax = plt.subplots(figsize=(7, 4))
            bars = ax.bar(range(len(vc)), vc.values,
                         color=palette[0], edgecolor='white', alpha=0.9)
            ax.set_xticks(range(len(vc)))
            ax.set_xticklabels([str(x)[:20] for x in vc.index], rotation=30, ha='right', fontsize=8)
            ax.set_title(f'Frekuensi {col}', fontweight='bold')
            ax.set_ylabel('Jumlah')
            for b in bars:
                ax.text(b.get_x() + b.get_width()/2, b.get_height() + max(vc.values)*0.02,
                        f'{int(b.get_height())}', ha='center', va='bottom', fontsize=7)
            fig.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
            plt.close(fig)
            charts[key] = buf.getvalue()
        except Exception as e:
            print(f'[PDF chart] {key} error: {e}')
            plt.close('all')

    # ── Per-column pie chart (categorical) ─────────────────────────────────
    for col in real_cat:
        key = f'pie_{col}'
        if want is not None and key not in want:
            continue
        try:
            vc = df_plot[col].value_counts().head(8)
            if len(vc) < 2:
                continue
            fig, ax = plt.subplots(figsize=(5, 5))
            wedges, texts, autotexts = ax.pie(
                vc.values, labels=[str(x)[:20] for x in vc.index],
                colors=palette[:len(vc)], autopct='%1.1f%%',
                startangle=90, pctdistance=0.8
            )
            for t in autotexts:
                t.set_fontsize(8)
            ax.set_title(f'Proporsi {col}', fontweight='bold')
            fig.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
            plt.close(fig)
            charts[key] = buf.getvalue()
        except Exception as e:
            print(f'[PDF chart] {key} error: {e}')
            plt.close('all')

    # ── Heatmap (correlation) ──────────────────────────────────────────────
    key = 'heatmap_all'
    if (want is None or key in want) and len(real_num) >= 2:
        try:
            cols_corr = real_num[:8]
            corr = df_plot[cols_corr].corr().fillna(0)
            fig, ax = plt.subplots(figsize=(7, 6))
            im = ax.imshow(corr.values, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
            ax.set_xticks(range(len(cols_corr)))
            ax.set_xticklabels(cols_corr, rotation=45, ha='right', fontsize=8)
            ax.set_yticks(range(len(cols_corr)))
            ax.set_yticklabels(cols_corr, fontsize=8)
            for i in range(len(cols_corr)):
                for j in range(len(cols_corr)):
                    ax.text(j, i, f'{corr.values[i, j]:.2f}', ha='center', va='center', fontsize=7,
                            color='white' if abs(corr.values[i, j]) > 0.5 else 'black')
            fig.colorbar(im, ax=ax, shrink=0.8)
            ax.set_title('Matriks Korelasi Pearson', fontweight='bold')
            fig.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
            plt.close(fig)
            charts[key] = buf.getvalue()
        except Exception as e:
            print(f'[PDF chart] {key} error: {e}')
            plt.close('all')

    # ── Scatter plots (pairwise numeric) ───────────────────────────────────
    max_scatter = 10
    scatter_count = 0
    for i in range(len(real_num)):
        if scatter_count >= max_scatter:
            break
        for j in range(i+1, len(real_num)):
            if scatter_count >= max_scatter:
                break
            c1, c2 = real_num[i], real_num[j]
            key = f'scatter_{c1}_vs_{c2}'
            if want is not None and key not in want:
                continue
            try:
                fig, ax = plt.subplots(figsize=(7, 5))
                ax.scatter(df_plot[c1], df_plot[c2], alpha=0.5, s=20,
                          c='#3b82f6', edgecolors='white', linewidth=0.3)
                ax.set_xlabel(c1)
                ax.set_ylabel(c2)
                ax.set_title(f'Scatter: {c1} vs {c2}', fontweight='bold')
                fig.tight_layout()
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
                plt.close(fig)
                charts[key] = buf.getvalue()
                scatter_count += 1
            except Exception as e:
                print(f'[PDF chart] {key} error: {e}')
                plt.close('all')

    # ── Box by category (num by cat) ───────────────────────────────────────
    max_boxby = 8
    boxby_count = 0
    for cat_col in real_cat[:4]:
        if boxby_count >= max_boxby:
            break
        for num_col in real_num[:4]:
            if boxby_count >= max_boxby:
                break
            key = f'box_{num_col}_by_{cat_col}'
            if want is not None and key not in want:
                continue
            try:
                groups = df_plot.groupby(cat_col)[num_col].apply(list)
                if len(groups) < 2:
                    continue
                fig, ax = plt.subplots(figsize=(8, 5))
                group_labels = [str(k)[:20] for k in groups.index]
                group_data = [v.dropna().values for v in groups.values]
                group_data = [g for g in group_data if len(g) > 0]
                if len(group_data) < 2:
                    plt.close(fig)
                    continue
                bp = ax.boxplot(group_data, patch_artist=True, labels=group_labels[:len(group_data)])
                for idx, patch in enumerate(bp['boxes']):
                    patch.set_facecolor(palette[idx % len(palette)])
                    patch.set_alpha(0.8)
                for median in bp['medians']:
                    median.set_color('#dc2626')
                    median.set_linewidth(2)
                ax.set_title(f'{num_col} by {cat_col}', fontweight='bold')
                ax.set_ylabel(num_col)
                plt.xticks(rotation=30, ha='right', fontsize=8)
                fig.tight_layout()
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
                plt.close(fig)
                charts[key] = buf.getvalue()
                boxby_count += 1
            except Exception as e:
                print(f'[PDF chart] {key} error: {e}')
                plt.close('all')

    return charts


# ─── GENERATE TIME SERIES CHART IMAGES FOR PDF ────────────────────────────────
def generate_ts_chart_images(df, dt_col, num_col, freq_label=None, selected_charts=None):
    """
    Generate static time series chart images (PNG bytes) for PDF.
    Returns dict: { 'ts_line': bytes, 'ts_trend': bytes, 'ts_ma': bytes,
                     'ts_rolling': bytes, 'ts_overview': bytes }
    """
    import io
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

    want = set(selected_charts) if selected_charts else {'ts_line', 'ts_trend', 'ts_ma', 'ts_rolling', 'ts_overview'}

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
            'font.size': 9, 'axes.titlesize': 11, 'axes.labelsize': 9,
            'figure.facecolor': 'white', 'axes.facecolor': '#f8fafc',
            'axes.grid': True, 'grid.alpha': 0.3,
        })

        # ── ts_line: basic line chart ──────────────────────────────────────
        if 'ts_line' in want:
            try:
                fig, ax = plt.subplots(figsize=(9, 4.5))
                ax.plot(x, y, color='#3b82f6', linewidth=1.2, alpha=0.85)
                ax.fill_between(x, y, alpha=0.1, color='#3b82f6')
                ax.set_title(f'Time Series: {num_col}', fontweight='bold')
                ax.set_xlabel(dt_col)
                ax.set_ylabel(num_col)
                ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(mdates.AutoDateLocator()))
                fig.autofmt_xdate(rotation=30)
                fig.tight_layout()
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
                plt.close(fig)
                charts['ts_line'] = buf.getvalue()
            except Exception as e:
                print(f'[PDF TS chart] ts_line error: {e}')
                plt.close('all')

        # ── ts_trend: line + OLS trend ─────────────────────────────────────
        if 'ts_trend' in want:
            try:
                slope, intercept, r_val, p_val, std_err = sp_stats.linregress(x_num, y)
                trend_line = slope * x_num + intercept

                fig, ax = plt.subplots(figsize=(9, 4.5))
                ax.plot(x, y, color='#3b82f6', linewidth=1.2, alpha=0.6, label='Actual')
                ax.plot(x, trend_line, color='#dc2626', linewidth=2, linestyle='--',
                       label=f'Trend (R²={r_val**2:.3f}, p={p_val:.4f})')
                ax.set_title(f'Trend Analysis: {num_col}', fontweight='bold')
                ax.set_xlabel(dt_col)
                ax.set_ylabel(num_col)
                ax.legend(fontsize=8)
                ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(mdates.AutoDateLocator()))
                fig.autofmt_xdate(rotation=30)
                fig.tight_layout()
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
                plt.close(fig)
                charts['ts_trend'] = buf.getvalue()
            except Exception as e:
                print(f'[PDF TS chart] ts_trend error: {e}')
                plt.close('all')

        # ── ts_ma: moving average ──────────────────────────────────────────
        if 'ts_ma' in want:
            try:
                n = len(y)
                if n >= 365:
                    window = 30
                elif n >= 90:
                    window = 7
                elif n >= 30:
                    window = 5
                else:
                    window = max(n // 5, 2)
                ma = pd.Series(y).rolling(window=window, min_periods=1).mean().values

                fig, ax = plt.subplots(figsize=(9, 4.5))
                ax.plot(x, y, color='#3b82f6', linewidth=1, alpha=0.5, label='Actual')
                ax.plot(x, ma, color='#f59e0b', linewidth=2.2,
                       label=f'Moving Avg (window={window})')
                ax.set_title(f'Moving Average: {num_col}', fontweight='bold')
                ax.set_xlabel(dt_col)
                ax.set_ylabel(num_col)
                ax.legend(fontsize=8)
                ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(mdates.AutoDateLocator()))
                fig.autofmt_xdate(rotation=30)
                fig.tight_layout()
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
                plt.close(fig)
                charts['ts_ma'] = buf.getvalue()
            except Exception as e:
                print(f'[PDF TS chart] ts_ma error: {e}')
                plt.close('all')

        # ── ts_rolling: rolling mean + rolling std ─────────────────────────
        if 'ts_rolling' in want:
            try:
                n = len(y)
                w_short = max(n // 10, 2)
                w_long = max(n // 3, 5)
                ys = pd.Series(y)
                rm_short = ys.rolling(window=w_short, min_periods=1).mean().values
                rm_long = ys.rolling(window=w_long, min_periods=1).mean().values

                fig, ax = plt.subplots(figsize=(9, 4.5))
                ax.plot(x, y, color='#3b82f6', linewidth=1, alpha=0.4, label='Actual')
                ax.plot(x, rm_short, color='#10b981', linewidth=1.8,
                       label=f'Rolling Mean (w={w_short})')
                ax.plot(x, rm_long, color='#dc2626', linewidth=2, linestyle='--',
                       label=f'Rolling Mean (w={w_long})')
                ax.set_title(f'Rolling Mean: {num_col}', fontweight='bold')
                ax.set_xlabel(dt_col)
                ax.set_ylabel(num_col)
                ax.legend(fontsize=8)
                ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(mdates.AutoDateLocator()))
                fig.autofmt_xdate(rotation=30)
                fig.tight_layout()
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
                plt.close(fig)
                charts['ts_rolling'] = buf.getvalue()
            except Exception as e:
                print(f'[PDF TS chart] ts_rolling error: {e}')
                plt.close('all')

        # ── ts_overview: 2x2 panel ─────────────────────────────────────────
        if 'ts_overview' in want:
            try:
                n = len(y)
                window_ma = max(n // 5, 2)
                window_vol = max(n // 10, 2)
                ys = pd.Series(y)
                ma_vals = ys.rolling(window=window_ma, min_periods=1).mean().values
                vol_vals = ys.rolling(window=window_vol, min_periods=1).std().values
                slope_val, intercept_val, _, _, _ = sp_stats.linregress(x_num, y)
                trend_vals = slope_val * x_num + intercept_val

                fig, axes = plt.subplots(2, 2, figsize=(10, 7))

                axes[0][0].plot(x, y, color='#3b82f6', linewidth=0.8)
                axes[0][0].set_title('Raw Data', fontweight='bold', fontsize=9)
                axes[0][0].set_ylabel(num_col, fontsize=8)

                axes[0][1].plot(x, y, color='#3b82f6', linewidth=0.8, alpha=0.5)
                axes[0][1].plot(x, trend_vals, color='#dc2626', linewidth=2, linestyle='--')
                axes[0][1].set_title('Trend (OLS)', fontweight='bold', fontsize=9)

                axes[1][0].plot(x, y, color='#3b82f6', linewidth=0.8, alpha=0.5)
                axes[1][0].plot(x, ma_vals, color='#f59e0b', linewidth=2)
                axes[1][0].set_title(f'Moving Avg (w={window_ma})', fontweight='bold', fontsize=9)
                axes[1][0].set_xlabel(dt_col, fontsize=8)
                axes[1][0].set_ylabel(num_col, fontsize=8)

                axes[1][1].plot(x, vol_vals, color='#8b5cf6', linewidth=1.2)
                axes[1][1].set_title('Rolling Std Dev', fontweight='bold', fontsize=9)
                axes[1][1].set_xlabel(dt_col, fontsize=8)
                axes[1][1].set_ylabel('Std Dev', fontsize=8)

                for row in axes:
                    for ax in row:
                        ax.tick_params(labelsize=7)
                        ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(mdates.AutoDateLocator()))
                        ax.grid(True, alpha=0.3)

                fig.suptitle(f'Overview: {num_col} — {freq_label or "Auto"}', fontweight='bold', fontsize=11)
                fig.tight_layout()
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
                plt.close(fig)
                charts['ts_overview'] = buf.getvalue()
            except Exception as e:
                print(f'[PDF TS chart] ts_overview error: {e}')
                plt.close('all')

    except Exception as e:
        print(f'[PDF TS chart] overall error: {e}')
        plt.close('all')

    return charts


# ─── FUNGSI UTAMA ─────────────────────────────────────────────────────────────
def generate_pdf_report(
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
    selected_charts=None,
    chart_images=None,
    ts_chart_images=None,
    ts_insights=None,
    ts_meta=None,
    analyst_name='',
    report_title='',
):
    """
    Generate laporan PDF lengkap dan customizable.
    """
    ALL_SECTIONS = [
        'pendahuluan', 'dataset', 'kualitas', 'statistik_num',
        'statistik_cat', 'visualisasi', 'time_series', 'cleaning', 'insight',
        'rekomendasi', 'penutup'
    ]
    if not selected_sections:
        selected_sections = ALL_SECTIONS

    def active(key):
        return key in selected_sections

    styles = _make_styles()
    story  = []
    now    = datetime.datetime.now()
    today  = now.strftime('%d %B %Y')
    time_  = now.strftime('%H:%M:%S')

    summary    = (quality_report or {}).get('summary', {})
    total_rows = len(df) if df is not None else 0
    total_cols = len(df.columns) if df is not None else 0
    missing_c  = summary.get('missing_cells', 0)
    dup_rows   = summary.get('duplicate_rows', 0)
    outliers_c = summary.get('total_outliers', 0)
    needs_cl   = summary.get('needs_cleaning', False)
    status_str = 'RAW DATA — Perlu Pembersihan' if needs_cl else 'CLEAN DATA — Siap Dianalisis'
    r_title    = report_title or 'Laporan Analisis Data Deskriptif'

    # ════════════════════════════════════════════
    # HALAMAN 1 — COVER
    # ════════════════════════════════════════════
    _logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'itsb_logo.png')
    if os.path.exists(_logo_path):
        try:
            _logo = Image(_logo_path, width=3.5*cm, height=3.5*cm)
            _logo.hAlign = 'CENTER'
            story.append(Spacer(1, 1.5*cm))
            story.append(_logo)
            story.append(Spacer(1, 0.3*cm))
        except Exception:
            story.append(Spacer(1, 3*cm))
    else:
        story.append(Spacer(1, 3*cm))

    # Brand + Title + Subtitle — unified navy block
    cover_content = []
    cover_content.append(Paragraph(
        '<b><font color="#60a5fa" size=10>DS GENERATOR</font></b>',
        ParagraphStyle('brand', fontName='Helvetica-Bold', fontSize=10, leading=14, alignment=1, textColor=C_WHITE)
    ))
    cover_content.append(Spacer(1, 0.6*cm))
    cover_content.append(Paragraph(
        r_title,
        ParagraphStyle('ctitle', fontName='Helvetica-Bold', fontSize=26, leading=32, alignment=1, textColor=C_WHITE)
    ))
    cover_content.append(Spacer(1, 0.3*cm))
    cover_content.append(Paragraph(
        'Exploratory Data Analysis Report',
        ParagraphStyle('csub', fontName='Helvetica', fontSize=12, leading=16, alignment=1, textColor=colors.HexColor('#93c5fd'))
    ))
    cover_content.append(Spacer(1, 0.15*cm))
    cover_content.append(Paragraph(
        f'Institut Teknologi Sains Bandung — Kelompok 2',
        ParagraphStyle('cuni', fontName='Helvetica', fontSize=9, leading=13, alignment=1, textColor=colors.HexColor('#94a3b8'))
    ))

    cover_tbl_data = [[cover_content]]
    cover_tbl = Table(cover_tbl_data, colWidths=[16.5*cm])
    cover_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), C_NAVY),
        ('TOPPADDING',    (0,0), (-1,-1), 20),
        ('BOTTOMPADDING', (0,0), (-1,-1), 20),
        ('LEFTPADDING',   (0,0), (-1,-1), 16),
        ('RIGHTPADDING',  (0,0), (-1,-1), 16),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    story.append(cover_tbl)
    story.append(Spacer(1, 2*cm))

    # Metadata row
    status_col = '#059669' if not needs_cl else '#dc2626'
    meta_items = [
        ('Dataset', filename),
        ('Total Data', f'{total_rows:,} baris x {total_cols} kolom'),
        ('Status', f'<font color="{status_col}"><b>{status_str}</b></font>'),
        ('Tanggal', f'{today}'),
        ('Analis', analyst_name or 'Kelompok 2 ITSB'),
    ]
    meta_rows = [[
        Paragraph(f'<font color="#94a3b8" size=7>{lbl.upper()}</font><br/>'
                  f'<font color="white" size=9><b>{val}</b></font>', styles['body'])
        for lbl, val in meta_items
    ]]
    meta_t = Table(meta_rows, colWidths=[16.5*cm/len(meta_items)]*len(meta_items))
    meta_t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), colors.HexColor('#1e3a5f')),
        ('TOPPADDING',    (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('LEFTPADDING',   (0,0), (-1,-1), 10),
        ('INNERGRID',     (0,0), (-1,-1), 0.5, colors.HexColor('#334155')),
        ('BOX',           (0,0), (-1,-1), 0.5, colors.HexColor('#334155')),
    ]))
    story.append(meta_t)

    # Footer
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph(
        '<font color="#94a3b8" size=8>Auto-generated by DS Generator Platform</font>',
        ParagraphStyle('cfoot', fontName='Helvetica', fontSize=8, leading=12, alignment=1, textColor=colors.HexColor('#94a3b8'))
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════
    # HALAMAN 2 — KATA PENGANTAR
    # ════════════════════════════════════════════
    _section_label(story, styles, 'I', 'Kata Pengantar')

    kp_paragraphs = [
        (
            'Puji syukur kami panjatkan ke hadirat Tuhan Yang Maha Esa atas segala berkat dan '
            'rahmat-Nya sehingga laporan analisis data ini dapat diselesaikan dengan baik. '
            'Laporan ini merupakan hasil analisis eksplorasi data (<i>Exploratory Data Analysis</i>) '
            'yang dilakukan secara otomatis menggunakan platform <b>DS Generator</b> — sistem '
            'analisis data deskriptif berbasis web yang dikembangkan oleh <b>Kelompok 2</b>, '
            'Program Studi Data Science, Institut Teknologi Sains Bandung (ITSB).'
        ),
        (
            f'Laporan ini menyajikan analisis menyeluruh terhadap dataset <b>{filename}</b> '
            f'yang terdiri dari <b>{total_rows:,} baris observasi</b> dan <b>{total_cols} variabel</b>. '
            f'Berdasarkan hasil pemindaian kualitas data yang dilakukan secara otomatis, dataset ini '
            f'{"memerlukan proses pembersihan data lebih lanjut karena ditemukan " + str(missing_c) + " sel kosong dan " + str(dup_rows) + " baris duplikat" if needs_cl else "dalam kondisi baik dan siap untuk dianalisis lebih lanjut"}. '
            f'{"Sebanyak " + str(outliers_c) + " potensi outlier juga terdeteksi melalui metode IQR." if outliers_c > 0 else ""}'
        ),
        (
            'Laporan ini disusun dengan tujuan untuk memberikan gambaran komprehensif dan terstruktur '
            'mengenai karakteristik data, distribusi variabel, kualitas data, serta temuan-temuan penting '
            'yang dapat dijadikan dasar pengambilan keputusan berbasis data (<i>data-driven decision making</i>). '
            'Analisis yang disajikan meliputi statistik deskriptif, visualisasi distribusi, deteksi anomali, '
            'serta rekomendasi strategis yang dirumuskan secara otomatis berdasarkan pola data yang teridentifikasi.'
        ),
        (
            'Kami menyadari bahwa laporan ini masih memiliki keterbatasan, terutama dalam hal kedalaman '
            'analisis yang bergantung pada kelengkapan dan kualitas data yang diberikan. Oleh karena itu, '
            'saran dan masukan yang konstruktif sangat kami harapkan demi penyempurnaan di masa mendatang. '
            'Semoga laporan ini dapat memberikan nilai tambah yang signifikan bagi pembaca dan pihak-pihak '
            'yang memerlukan informasi dari dataset ini.'
        ),
    ]

    for p in kp_paragraphs:
        story.append(Paragraph(p, styles['body']))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 1*cm))

    ttd_data = [
        [Paragraph(f'Cikarang, {today}', styles['body']), ''],
        [Paragraph('Tim Penyusun,', styles['body']), ''],
        [Spacer(1, 1*cm), ''],
        [Paragraph('<b>Kelompok 2 — Data Science Programming</b>', styles['body_bold']), ''],
        [Paragraph('Institut Teknologi Sains Bandung (ITSB)', styles['body']), ''],
    ]
    ttd_t = Table(ttd_data, colWidths=[8*cm, 8.5*cm])
    ttd_t.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.append(ttd_t)
    story.append(PageBreak())

    # ════════════════════════════════════════════
    # BAB I — PENDAHULUAN & LATAR BELAKANG
    # ════════════════════════════════════════════
    if active('pendahuluan'):
        _section_label(story, styles, 'II', 'Pendahuluan & Latar Belakang')

        story.append(Paragraph('1.1 Latar Belakang', styles['subbab']))
        story.append(Paragraph(
            'Perkembangan teknologi informasi yang pesat telah mendorong munculnya ledakan data '
            '(<i>data explosion</i>) di berbagai sektor industri dan akademik. Kemampuan untuk memahami, '
            'mengolah, dan menginterpretasikan data secara efisien menjadi kompetensi krusial di era '
            'transformasi digital ini. Analisis data eksplorasi (<i>Exploratory Data Analysis</i> — EDA) '
            'merupakan langkah fundamental yang harus dilakukan sebelum pemodelan statistik atau '
            'machine learning, guna memahami karakteristik dasar dataset, mendeteksi anomali, dan '
            'merumuskan hipotesis awal yang akan diuji lebih lanjut.',
            styles['body']
        ))
        story.append(Paragraph(
            f'Dataset <b>{filename}</b> yang dianalisis dalam laporan ini merupakan data '
            f'dengan {total_rows:,} observasi dan {total_cols} variabel. Keberagaman variabel yang '
            f'mencakup {len(num_stats) if num_stats else 0} variabel numerik '
            f'dan {len(cat_stats) if cat_stats else 0} variabel kategorikal '
            f'memberikan peluang analisis yang komprehensif untuk mengungkap pola tersembunyi dalam data.',
            styles['body']
        ))

        story.append(Paragraph('1.2 Tujuan Analisis', styles['subbab']))
        tujuan = [
            'Mengidentifikasi karakteristik statistik dasar setiap variabel dalam dataset.',
            'Mendeteksi dan mengkuantifikasi masalah kualitas data (missing values, duplikat, outlier).',
            'Menganalisis distribusi dan pola sebaran data pada variabel numerik dan kategorikal.',
            'Menghasilkan visualisasi data yang informatif dan mudah dipahami.',
            'Merumuskan rekomendasi strategis berdasarkan temuan analisis.',
        ]
        for t in tujuan:
            story.append(Paragraph(f'\u2022 {t}', styles['bullet']))

        story.append(Paragraph('1.3 Ruang Lingkup', styles['subbab']))
        story.append(Paragraph(
            'Analisis dalam laporan ini mencakup: (1) pemeriksaan kualitas dan kesehatan data, '
            '(2) statistik deskriptif untuk seluruh variabel numerik dan kategorikal, '
            '(3) deteksi outlier menggunakan metode Interquartile Range (IQR), '
            '(4) analisis korelasi antar variabel numerik, serta '
            '(5) pembersihan data jika diperlukan. Analisis prediktif atau inferensial berada di '
            'luar ruang lingkup laporan ini.',
            styles['body']
        ))

        story.append(Paragraph('1.4 Metodologi', styles['subbab']))
        story.append(Paragraph(
            'Analisis dilakukan menggunakan platform <b>DS Generator</b> yang dibangun di atas '
            'ekosistem Python dengan library utama: <b>Pandas</b> untuk manipulasi data, '
            '<b>NumPy</b> untuk komputasi numerik, <b>Plotly</b> untuk visualisasi interaktif, '
            '<b>SciPy</b> untuk uji statistik, dan <b>ReportLab</b> untuk generasi laporan PDF. '
            'Proses analisis berjalan secara otomatis (<i>automated pipeline</i>) setelah dataset '
            'diunggah ke dalam sistem.',
            styles['body']
        ))
        story.append(PageBreak())

    # ════════════════════════════════════════════
    # BAB II — DESKRIPSI DATASET
    # ════════════════════════════════════════════
    if active('dataset'):
        _section_label(story, styles, 'III', 'Deskripsi & Ringkasan Dataset')

        story.append(Paragraph('2.1 Ringkasan Eksekutif', styles['subbab']))
        _kpi_table(story, styles, [
            ('Total Baris',     f'{total_rows:,}',    '#dbeafe'),
            ('Total Kolom',     str(total_cols),       '#d1fae5'),
            ('Missing Values',  f'{missing_c:,}',      '#fef3c7'),
            ('Duplikat',        str(dup_rows),          '#fee2e2' if dup_rows > 0 else '#d1fae5'),
            ('IQR Outliers',    str(outliers_c),        '#fef3c7' if outliers_c > 0 else '#d1fae5'),
        ])

        story.append(Paragraph(
            f'Dataset <b>{filename}</b> terdiri dari <b>{total_rows:,} observasi</b> dengan '
            f'<b>{total_cols} variabel</b>. '
            + (f'Terdapat <b>{missing_c:,} sel kosong</b> ({round(missing_c/(total_rows*total_cols)*100,2) if total_rows and total_cols else 0}% dari total data) '
               f'yang tersebar di berbagai kolom. ' if missing_c > 0 else 'Tidak ditemukan sel kosong pada dataset ini. ')
            + (f'Sebanyak <b>{dup_rows} baris duplikat</b> teridentifikasi dan perlu dihapus untuk menjaga integritas analisis. '
               if dup_rows > 0 else '')
            + (f'Deteksi outlier menggunakan metode IQR menemukan <b>{outliers_c} potensi nilai ekstrem</b> '
               f'yang perlu diverifikasi lebih lanjut.' if outliers_c > 0 else ''),
            styles['body']
        ))

        story.append(Paragraph('2.2 Komposisi Variabel', styles['subbab']))
        num_cols_list = [s.get('Column','') for s in (num_stats or [])]
        cat_cols_list = [s.get('Column','') for s in (cat_stats or [])]

        comp_data = [
            ['Tipe Variabel', 'Jumlah', 'Contoh Variabel'],
            ['Numerik (Kuantitatif)', str(len(num_cols_list)),
             ', '.join(num_cols_list[:4]) + (' ...' if len(num_cols_list) > 4 else '') or '\u2014'],
            ['Kategorikal (Kualitatif)', str(len(cat_cols_list)),
             ', '.join(cat_cols_list[:4]) + (' ...' if len(cat_cols_list) > 4 else '') or '\u2014'],
        ]
        _data_table(story, styles,
                    comp_data[0], comp_data[1:],
                    [5*cm, 2.5*cm, 9*cm],
                    'Tabel 1. Komposisi variabel berdasarkan tipe data')

        story.append(PageBreak())

    # ════════════════════════════════════════════
    # BAB III — KUALITAS DATA
    # ════════════════════════════════════════════
    if active('kualitas') and quality_report:
        _section_label(story, styles, 'IV', 'Kualitas Data & Data Health')

        story.append(Paragraph('3.1 Gambaran Umum Kualitas Data', styles['subbab']))
        story.append(Paragraph(
            'Pemeriksaan kualitas data (<i>data quality assessment</i>) merupakan langkah krusial '
            'sebelum analisis statistik dilakukan. Pada tahap ini, setiap kolom diperiksa '
            'untuk mengidentifikasi sel kosong, nilai duplikat, inkonsistensi format, dan '
            'nilai ekstrem yang dapat mempengaruhi keakuratan analisis.',
            styles['body']
        ))

        col_quality = quality_report.get('columns', [])
        if col_quality:
            story.append(Paragraph('3.2 Detail Kualitas per Kolom', styles['subbab']))
            rows = []
            for c in col_quality:
                status = c.get('status', 'ok')
                st_txt = '\u2713 OK' if status == 'ok' else '\u26a0 Warning' if status == 'warning' else '\u2717 Error'
                rows.append([
                    c.get('column', '\u2014'),
                    c.get('dtype', '\u2014'),
                    f"{c.get('missing', 0)} ({c.get('missing_pct', 0)}%)",
                    str(c.get('unique', '\u2014')),
                    str(c.get('outliers', 0)),
                    st_txt,
                ])
            _data_table(story, styles,
                        ['Kolom', 'Tipe', 'Missing', 'Unique', 'Outliers', 'Status'],
                        rows,
                        [4.5*cm, 2.5*cm, 2.5*cm, 1.8*cm, 2*cm, 3.2*cm],
                        'Tabel 2. Ringkasan kualitas data per kolom')

        if quality_report.get('warnings'):
            story.append(Paragraph('3.3 Peringatan Kualitas Data', styles['subbab']))
            story.append(Paragraph(
                'Sistem mendeteksi sejumlah isu kualitas data yang perlu ditangani sebelum '
                'analisis lebih lanjut dilakukan:',
                styles['body']
            ))
            for w in quality_report['warnings']:
                story.append(Paragraph(f'\u2022 {_safe(w)}', styles['bullet']))

        story.append(PageBreak())

    # ════════════════════════════════════════════
    # BAB IV — STATISTIK NUMERIK
    # ════════════════════════════════════════════
    if active('statistik_num') and num_stats:
        _section_label(story, styles, 'V', 'Statistik Deskriptif — Variabel Numerik')

        story.append(Paragraph('4.1 Pengertian Statistik Deskriptif', styles['subbab']))
        story.append(Paragraph(
            'Statistik deskriptif adalah cabang statistik yang bertujuan merangkum, '
            'mendeskripsikan, dan menyajikan data secara informatif tanpa menarik kesimpulan '
            'inferensial. Ukuran yang digunakan meliputi: <b>Mean</b> (rata-rata aritmatik), '
            '<b>Median</b> (nilai tengah), <b>Standar Deviasi</b> (ukuran dispersi/keragaman), '
            '<b>Nilai Minimum dan Maksimum</b> (rentang data), serta <b>Kuartil</b> (Q25 dan Q75) '
            'yang membagi data menjadi empat bagian sama besar.',
            styles['body']
        ))

        story.append(Paragraph('4.2 Tabel Statistik Deskriptif', styles['subbab']))
        rows = [[
            s.get('Column','\u2014'), s.get('Count','\u2014'), s.get('Missing','\u2014'),
            s.get('Mean','\u2014'), s.get('Median','\u2014'), s.get('Std Dev','\u2014'),
            s.get('Min','\u2014'), s.get('Q25','\u2014'), s.get('Q75','\u2014'),
            s.get('Max','\u2014'), s.get('Skewness','\u2014')
        ] for s in num_stats]
        _data_table(story, styles,
                    ['Kolom','Count','Missing','Mean','Median','Std Dev','Min','Q25','Q75','Max','Skewness'],
                    rows,
                    [3.2*cm,1.5*cm,1.5*cm,1.8*cm,1.8*cm,1.8*cm,1.8*cm,1.5*cm,1.5*cm,1.8*cm,1.8*cm],
                    'Tabel 3. Statistik deskriptif variabel numerik')

        story.append(Paragraph('4.3 Interpretasi per Variabel', styles['subbab']))
        for i, s in enumerate(num_stats):
            col = s.get('Column', '?')
            story.append(KeepTogether([
                Paragraph(f'<b>4.3.{i+1} Variabel: {col}</b>', styles['body_bold']),
                Paragraph(_auto_interp_numeric(col, s), styles['body']),
                Spacer(1, 4),
            ]))

        story.append(PageBreak())

    # ════════════════════════════════════════════
    # BAB V — STATISTIK KATEGORIKAL
    # ════════════════════════════════════════════
    if active('statistik_cat') and cat_stats:
        _section_label(story, styles, 'VI', 'Statistik Deskriptif — Variabel Kategorikal')

        story.append(Paragraph('5.1 Pengertian Variabel Kategorikal', styles['subbab']))
        story.append(Paragraph(
            'Variabel kategorikal adalah variabel yang nilainya berupa kategori atau label, '
            'bukan angka kontinu. Terdapat dua jenis utama: variabel <b>nominal</b> (kategori tanpa urutan, '
            'misal: jenis kelamin, kota) dan variabel <b>ordinal</b> (kategori berurutan, misal: tingkat '
            'kepuasan, kelas nilai). Analisis variabel kategorikal berfokus pada frekuensi kemunculan '
            'setiap kategori dan distribusi proporsionalnya.',
            styles['body']
        ))

        story.append(Paragraph('5.2 Tabel Statistik Kategorikal', styles['subbab']))
        rows = [[
            s.get('Column','\u2014'), str(s.get('Unique','\u2014')), _safe(s.get('Mode')),
            _safe(s.get('Mode Freq')), _safe(s.get('Mode %')),
            str(s.get('Missing Count', 0))
        ] for s in cat_stats]
        _data_table(story, styles,
                    ['Kolom', 'Unique', 'Mode (Dominan)', 'Frekuensi Mode', 'Mode %', 'Missing'],
                    rows,
                    [4.5*cm, 2*cm, 4*cm, 2.5*cm, 2*cm, 1.5*cm],
                    'Tabel 4. Statistik deskriptif variabel kategorikal')

        story.append(Paragraph('5.3 Interpretasi per Variabel', styles['subbab']))
        for i, s in enumerate(cat_stats):
            col = s.get('Column', '?')
            story.append(KeepTogether([
                Paragraph(f'<b>5.3.{i+1} Variabel: {col}</b>', styles['body_bold']),
                Paragraph(_auto_interp_categorical(col, s), styles['body']),
                Spacer(1, 4),
            ]))

        story.append(PageBreak())

    # ════════════════════════════════════════════
    # BAB VI — VISUALISASI
    # ════════════════════════════════════════════
    if active('visualisasi') and chart_images:
        _section_label(story, styles, 'VII', 'Visualisasi Data & Interpretasi')

        story.append(Paragraph('6.1 Pentingnya Visualisasi dalam EDA', styles['subbab']))
        story.append(Paragraph(
            'Visualisasi data merupakan komponen esensial dalam EDA karena memungkinkan analis '
            'untuk memahami pola, tren, distribusi, dan anomali dalam data secara intuitif '
            'dan efisien. Berikut adalah visualisasi yang dihasilkan berdasarkan karakteristik dataset ini.',
            styles['body']
        ))

        charts_to_include = selected_charts or list(chart_images.keys())

        chart_titles = {
            'histogram':  'Distribusi Frekuensi Variabel Numerik',
            'boxplot':    'Sebaran Data & Deteksi Outlier',
            'bar_chart':  'Frekuensi Kategori',
            'scatter':    'Hubungan Antar Variabel Numerik',
            'heatmap':    'Matriks Korelasi Variabel Numerik',
            'line_chart': 'Tren Waktu',
            'pie_chart':  'Proporsi Kategori',
        }

        def _get_chart_title(chart_key):
            if chart_key.startswith('histogram_'):
                col = chart_key[len('histogram_'):]
                return f'Distribusi Frekuensi — {col}'
            elif chart_key.startswith('boxplot_'):
                col = chart_key[len('boxplot_'):]
                return f'Boxplot — {col}'
            elif chart_key.startswith('bar_'):
                col = chart_key[len('bar_'):]
                return f'Frekuensi Kategori — {col}'
            elif chart_key.startswith('pie_'):
                col = chart_key[len('pie_'):]
                return f'Proporsi Kategori — {col}'
            elif chart_key == 'heatmap_all':
                return 'Matriks Korelasi Pearson'
            elif chart_key.startswith('scatter_') and '_vs_' in chart_key:
                parts = chart_key[len('scatter_'):].split('_vs_', 1)
                return f'Scatter Plot: {parts[0]} vs {parts[1]}'
            elif chart_key.startswith('box_') and '_by_' in chart_key:
                parts = chart_key[len('box_'):].split('_by_', 1)
                return f'Boxplot: {parts[0]} by {parts[1]}'
            return chart_titles.get(chart_key, chart_key)

        def _interpret_chart(chart_key, num_stats, cat_stats):
            interp_parts = []
            # Per-column histogram
            if chart_key.startswith('histogram_'):
                col = chart_key[len('histogram_'):]
                for s in (num_stats or []):
                    if s.get('Column') == col:
                        skew = s.get('Skewness', 0)
                        mean = s.get('Mean', 0)
                        try:
                            sf = float(str(skew))
                            if abs(sf) < 0.5:
                                skew_desc = 'cenderung simetris'
                            elif sf > 0.5:
                                skew_desc = 'miring ke kanan (right-skewed)'
                            else:
                                skew_desc = 'miring ke kiri (left-skewed)'
                        except Exception:
                            skew_desc = 'tidak dapat ditentukan'
                        interp_parts.append(
                            f'Variabel <b>{col}</b> menunjukkan distribusi {skew_desc} '
                            f'(skewness = {skew}) dengan rata-rata {_safe(mean)}. '
                        )
                        break
                if not interp_parts:
                    interp_parts.append(f'Histogram menunjukkan distribusi frekuensi dari variabel <b>{col}</b>. ')
            # Per-column boxplot
            elif chart_key.startswith('boxplot_'):
                col = chart_key[len('boxplot_'):]
                for s in (num_stats or []):
                    if s.get('Column') == col:
                        q25 = s.get('Q25', '?')
                        q75 = s.get('Q75', '?')
                        interp_parts.append(
                            f'Boxplot <b>{col}</b> menunjukkan sebaran interkuartil (Q25 = {_safe(q25)}, Q75 = {_safe(q75)}) '
                            f'dengan potensi outlier yang ditandai titik di luar whisker. '
                        )
                        break
                if not interp_parts:
                    interp_parts.append(f'Boxplot menunjukkan sebaran data dari variabel <b>{col}</b>. ')
            # Per-column bar chart
            elif chart_key.startswith('bar_'):
                col = chart_key[len('bar_'):]
                for s in (cat_stats or []):
                    if s.get('Column') == col:
                        unique = s.get('Unique', '?')
                        mode = _safe(s.get('Mode'))
                        mode_pct = _safe(s.get('Mode %'))
                        interp_parts.append(
                            f'Variabel <b>{col}</b> memiliki {unique} kategori unik. '
                            f'Kategori terdominan adalah "{mode}" dengan proporsi {mode_pct}. '
                        )
                        break
                if not interp_parts:
                    interp_parts.append(f'Bar chart menunjukkan distribusi frekuensi dari variabel kategorikal <b>{col}</b>. ')
            # Per-column pie chart
            elif chart_key.startswith('pie_'):
                col = chart_key[len('pie_'):]
                for s in (cat_stats or []):
                    if s.get('Column') == col:
                        unique = s.get('Unique', '?')
                        mode = _safe(s.get('Mode'))
                        mode_pct = _safe(s.get('Mode %'))
                        interp_parts.append(
                            f'Pie chart <b>{col}</b> menunjukkan proporsi relatif dari {unique} kategori. '
                            f'Kategori "{mode}" mendominasi dengan {mode_pct} dari keseluruhan data. '
                        )
                        break
                if not interp_parts:
                    interp_parts.append(f'Pie chart menunjukkan proporsi kategori dari variabel <b>{col}</b>. ')
            # Heatmap
            elif chart_key == 'heatmap_all':
                cols = [s.get('Column', '?') for s in (num_stats or [])[:5]]
                interp_parts.append(
                    f'Heatmap menampilkan matriks korelasi antara variabel numerik: '
                    f'<b>{", ".join(cols)}</b>. '
                    f'Nilai korelasi mendekati 1 atau -1 menunjukkan hubungan kuat, '
                    f'mendekati 0 menunjukkan hubungan lemah. '
                )
            # Scatter
            elif chart_key.startswith('scatter_') and '_vs_' in chart_key:
                parts = chart_key[len('scatter_'):].split('_vs_', 1)
                interp_parts.append(
                    f'Scatter plot antara <b>{parts[0]}</b> dan <b>{parts[1]}</b> '
                    f'menggambarkan hubungan/ko-relasi antara kedua variabel numerik tersebut. '
                )
            # Box by category
            elif chart_key.startswith('box_') and '_by_' in chart_key:
                parts = chart_key[len('box_'):].split('_by_', 1)
                interp_parts.append(
                    f'Boxplot <b>{parts[0]}</b> dikelompokkan berdasarkan <b>{parts[1]}</b> '
                    f'menunjukkan perbandingan sebaran data antar kategori. '
                )
            else:
                interp_parts.append(
                    'Visualisasi ini menampilkan karakteristik dan pola pada data yang dianalisis. '
                )
            return ' '.join(interp_parts)

        for i, chart_name in enumerate(charts_to_include):
            if chart_name not in chart_images:
                continue
            img_data = chart_images[chart_name]
            title = _get_chart_title(chart_name)

            interp = _interpret_chart(chart_name, num_stats, cat_stats)

            try:
                if isinstance(img_data, bytes):
                    img = Image(BytesIO(img_data), width=9.5*cm, height=6.5*cm)
                else:
                    img = Image(img_data, width=9.5*cm, height=6.5*cm)

                interp_style = ParagraphStyle(
                    'interp', fontName='Helvetica', fontSize=8.5, leading=12,
                    textColor=colors.HexColor('#1e293b'), spaceBefore=2, spaceAfter=2
                )
                interp_para = Paragraph(interp, interp_style)
                caption_style = ParagraphStyle(
                    'cap2', fontName='Helvetica', fontSize=7.5, leading=10,
                    textColor=colors.HexColor('#64748b'), spaceBefore=4
                )
                caption_para = Paragraph(f'Gambar {i+1}. {title}', caption_style)

                interp_cell = [
                    Paragraph(f'<b>Interpretasi</b>', ParagraphStyle(
                        'interp_hdr', fontName='Helvetica-Bold', fontSize=8, leading=11,
                        textColor=C_NAVY, spaceBefore=0, spaceAfter=4
                    )),
                    interp_para,
                ]

                chart_cell = [img, Spacer(1, 2), caption_para]

                side_data = [[chart_cell, interp_cell]]
                side_tbl = Table(side_data, colWidths=[10*cm, 6.5*cm])
                side_tbl.setStyle(TableStyle([
                    ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                    ('LEFTPADDING',   (0,0), (-1,-1), 0),
                    ('RIGHTPADDING',  (0,0), (-1,-1), 6),
                    ('TOPPADDING',    (0,0), (-1,-1), 0),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                    ('BACKGROUND',    (1,0), (1,0), colors.white),
                    ('BOX',           (1,0), (1,0), 0.5, colors.white),
                    ('LEFTPADDING',   (1,0), (1,0), 8),
                    ('RIGHTPADDING',  (1,0), (1,0), 8),
                    ('TOPPADDING',    (1,0), (1,0), 8),
                    ('BOTTOMPADDING', (1,0), (1,0), 8),
                ]))

                story.append(Paragraph(f'6.{i+2} {title}', styles['subbab']))
                story.append(side_tbl)
            except Exception as e:
                story.append(Paragraph(f'6.{i+2} {title}', styles['subbab']))
                story.append(Paragraph(f'<i>[Gambar tidak dapat ditampilkan: {e}]</i>', styles['caption']))

            story.append(Spacer(1, 10))

        story.append(PageBreak())

    # ════════════════════════════════════════════
    # BAB VII — TIME SERIES
    # ════════════════════════════════════════════
    if active('time_series') and ts_chart_images and ts_meta:
        _section_label(story, styles, 'VII-A', 'Analisis Time Series')

        story.append(Paragraph('7A.1 Pengertian Time Series', styles['subbab']))
        story.append(Paragraph(
            'Analisis <i>time series</i> adalah teknik statistik yang digunakan untuk menganalisis '
            'urutan data yang diamati dari waktu ke waktu. Tujuan utamanya adalah mengidentifikasi '
            'pola (<i>pattern</i>) seperti tren (<i>trend</i>), musiman (<i>seasonality</i>), '
            'dan volatilitas (<i>volatility</i>) untuk memahami dinamika perubahan suatu variabel '
            'sepanjang periode waktu tertentu.',
            styles['body']
        ))

        ts_dt = ts_meta.get('dt_col', '?')
        ts_nc = ts_meta.get('num_col', '?')
        ts_freq = ts_meta.get('freq_label', 'Auto')
        ts_n = ts_meta.get('n_points', '?')
        ts_dir = ts_meta.get('direction', '?')
        ts_slope = ts_meta.get('slope', '?')
        ts_r2 = ts_meta.get('r_squared', '?')
        ts_start = ts_meta.get('date_start', '?')
        ts_end = ts_meta.get('date_end', '?')

        story.append(Paragraph('7A.2 Ringkasan Time Series', styles['subbab']))
        _kpi_table(story, styles, [
            ('Variabel Waktu', str(ts_dt), '#dbeafe'),
            ('Variabel Numerik', str(ts_nc), '#d1fae5'),
            ('Frekuensi', str(ts_freq), '#fef3c7'),
            ('Titik Data', str(ts_n), '#ede9fe'),
        ])

        ts_meta_rows = [
            ['Metrik', 'Nilai'],
            ['Kolom Waktu', str(ts_dt)],
            ['Kolom Numerik', str(ts_nc)],
            ['Frekuensi', str(ts_freq)],
            ['Rentang Waktu', f'{ts_start} s.d. {ts_end}'],
            ['Jumlah Observasi', str(ts_n)],
            ['Arah Tren', str(ts_dir)],
            ['Slope (OLS)', str(ts_slope)],
            ['R-squared', str(ts_r2)],
        ]
        _data_table(story, styles,
                    ts_meta_rows[0], ts_meta_rows[1:],
                    [8*cm, 8.5*cm],
                    'Tabel 5A. Ringkasan metadata time series')

        story.append(Paragraph('7A.3 Interpretasi Tren', styles['subbab']))
        try:
            direction_desc = {
                'UPWARD': 'menunjukkan tren naik (<i>upward trend</i>)',
                'DOWNWARD': 'menunjukkan tren turun (<i>downward trend</i>)',
                'STABLE': 'cenderung stabil tanpa tren signifikan',
            }.get(str(ts_dir).upper(), f'arah tren: {ts_dir}')
        except Exception:
            direction_desc = f'arah tren: {ts_dir}'

        try:
            r2_val = float(str(ts_r2))
            if r2_val > 0.7:
                strength = 'kuat'
            elif r2_val > 0.3:
                strength = 'moderat'
            else:
                strength = 'lemah'
        except Exception:
            strength = 'tidak dapat ditentukan'

        interp_text = (
            f'Analisis time series terhadap variabel <b>{ts_nc}</b> dengan dimensi waktu '
            f'<b>{ts_dt}</b> ({ts_freq}) {direction_desc} berdasarkan regresi linear OLS. '
            f'Nilai R-squared sebesar <b>{ts_r2}</b> mengindikasikan kekuatan tren yang <b>{strength}</b>. '
        )
        try:
            slope_f = float(str(ts_slope))
            if slope_f > 0:
                interp_text += f'Slope positif ({ts_slope}) menunjukkan rata-rata peningkatan per periode waktu. '
            elif slope_f < 0:
                interp_text += f'Slope negatif ({ts_slope}) menunjukkan rata-rata penurunan per periode waktu. '
            else:
                interp_text += 'Slope mendekati nol menunjukkan stabilitas nilai dari waktu ke waktu. '
        except Exception:
            pass

        if ts_insights:
            interp_text += '\n\n<b>Temuan otomatis:</b>\n'
            for ins in ts_insights[:6]:
                title = ins.get('title', '')
                desc = ins.get('desc', '')
                interp_text += f'\u2022 <b>{title}</b> — {desc}\n'

        story.append(Paragraph(interp_text, styles['body']))

        story.append(Paragraph('7A.4 Visualisasi Time Series', styles['subbab']))

        ts_chart_titles = {
            'ts_line':    'Line Chart — Data Time Series',
            'ts_trend':   'Trend Analysis — Regresi Linear OLS',
            'ts_ma':      'Moving Average — Perataan Data',
            'ts_rolling': 'Rolling Mean — Rata-rata Bergulir',
            'ts_overview':'Overview — Panel 4 Variabel',
        }

        ts_charts_order = ['ts_line', 'ts_trend', 'ts_ma', 'ts_rolling', 'ts_overview']
        chart_idx = 0
        for ck in ts_charts_order:
            if ck not in ts_chart_images:
                continue
            img_data = ts_chart_images[ck]
            title = ts_chart_titles.get(ck, ck)
            story.append(Paragraph(f'7A.4.{chart_idx+1} {title}', styles['subbab']))
            try:
                if isinstance(img_data, bytes):
                    img = Image(BytesIO(img_data), width=15*cm, height=8*cm)
                else:
                    img = Image(img_data, width=15*cm, height=8*cm)
                story.append(img)
                story.append(Paragraph(f'Gambar TS-{chart_idx+1}. {title}', styles['caption']))
            except Exception as e:
                story.append(Paragraph(f'<i>[Gambar tidak dapat ditampilkan: {e}]</i>', styles['caption']))
            story.append(Spacer(1, 6))
            chart_idx += 1

        story.append(PageBreak())

    # ════════════════════════════════════════════
    # BAB VII — CLEANING
    # ════════════════════════════════════════════
    if active('cleaning') and cleaning_history:
        _section_label(story, styles, 'VIII', 'Proses Data Cleaning')

        story.append(Paragraph('7.1 Gambaran Proses Pembersihan Data', styles['subbab']))
        story.append(Paragraph(
            'Pembersihan data (<i>data cleaning</i>) adalah proses identifikasi dan perbaikan '
            '(atau penghapusan) data yang tidak akurat, tidak lengkap, atau tidak konsisten '
            'dari dataset. Proses ini krusial karena kualitas output analisis sangat bergantung '
            'pada kualitas input data \u2014 prinsip "<i>Garbage In, Garbage Out</i>" (GIGO).',
            styles['body']
        ))

        sb = cleaning_summary or {}
        if sb:
            story.append(Paragraph('7.2 Perbandingan Sebelum & Sesudah Cleaning', styles['subbab']))
            rows = [
                ['Jumlah Baris',     str(sb.get('rows_before', '\u2014')),   str(sb.get('rows_after', '\u2014')),
                 f"\u0394 {abs(sb.get('rows_before',0) - sb.get('rows_after',0))} baris"],
                ['Jumlah Kolom',     str(sb.get('cols_before', '\u2014')),   str(sb.get('cols_after', '\u2014')),
                 f"\u0394 {abs(sb.get('cols_before',0) - sb.get('cols_after',0))} kolom"],
                ['Sel Kosong',       str(sb.get('missing_before', '\u2014')), str(sb.get('missing_after', '\u2014')),
                 f"Berkurang {abs(sb.get('missing_before',0) - sb.get('missing_after',0))} sel"],
            ]
            _data_table(story, styles,
                        ['Metrik', 'Sebelum', 'Sesudah', 'Perubahan'],
                        rows,
                        [5*cm, 3.5*cm, 3.5*cm, 4.5*cm],
                        'Tabel 5. Perbandingan dataset sebelum dan sesudah cleaning')

        story.append(Paragraph('7.3 Log Proses Cleaning', styles['subbab']))
        for i, h in enumerate(cleaning_history or []):
            label = h.get('label', f'Operasi {i+1}')
            logs  = h.get('log', [])
            story.append(Paragraph(f'<b>Langkah {i+1}:</b> {label}', styles['body_bold']))
            for log_line in (logs if isinstance(logs, list) else [str(logs)]):
                story.append(Paragraph(f'  \u2192 {_safe(log_line)}', styles['quote']))

        story.append(PageBreak())

    # ════════════════════════════════════════════
    # BAB VIII — INSIGHT
    # ════════════════════════════════════════════
    if active('insight') and auto_insights:
        _section_label(story, styles, 'IX', 'Temuan Kunci & Insight Otomatis')

        story.append(Paragraph('8.1 Metodologi Perumusan Insight', styles['subbab']))
        story.append(Paragraph(
            'Insight dalam laporan ini dirumuskan secara otomatis oleh sistem DS Generator '
            'berdasarkan analisis statistik multi-dimensi. Sistem mengidentifikasi pola anomali, '
            'korelasi signifikan, distribusi tidak normal, dan karakteristik khusus dataset '
            'yang berpotensi memiliki implikasi analitis atau bisnis yang penting.',
            styles['body']
        ))

        story.append(Paragraph('8.2 Daftar Temuan', styles['subbab']))
        for i, ins in enumerate(auto_insights[:15]):
            t    = ins.get('type', 'info')
            icon = {'success': '\u2713', 'warning': '\u26a0', 'danger': '\u2717'}.get(t, '\u2139')
            col  = {'success': C_GREEN, 'warning': C_YELLOW, 'danger': C_RED}.get(t, C_BLUE)

            ins_data = [[
                Paragraph(f'<b>{icon} {i+1}. {_safe(ins.get("title"))}</b>',
                          ParagraphStyle('IT', parent=styles['body_bold'], textColor=col)),
                Paragraph(_safe(ins.get('desc')), styles['body'])
            ]]
            ins_t = Table(ins_data, colWidths=[4.5*cm, 12*cm])
            ins_t.setStyle(TableStyle([
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING',    (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
                ('BACKGROUND',    (0,0), (-1,-1), C_LIGHT),
                ('LINEAFTER',     (0,0), (0,-1),  2, col),
                ('BOX',           (0,0), (-1,-1),  0.5, colors.HexColor('#e2e8f0')),
            ]))
            story.append(ins_t)
            story.append(Spacer(1, 6))

        story.append(PageBreak())

    # ════════════════════════════════════════════
    # BAB IX — REKOMENDASI
    # ════════════════════════════════════════════
    if active('rekomendasi'):
        _section_label(story, styles, 'X', 'Rekomendasi Strategis')

        story.append(Paragraph('9.1 Dasar Perumusan Rekomendasi', styles['subbab']))
        story.append(Paragraph(
            'Rekomendasi berikut dirumuskan berdasarkan temuan dari analisis kualitas data, '
            'statistik deskriptif, dan insight otomatis yang dihasilkan. Setiap rekomendasi '
            'bersifat spesifik dan dapat ditindaklanjuti (<i>actionable</i>) oleh tim data '
            'atau pemangku kepentingan terkait.',
            styles['body']
        ))

        story.append(Paragraph('9.2 Daftar Rekomendasi', styles['subbab']))

        recoms = []
        if missing_c > 0:
            recoms.append((
                'R1. Penanganan Missing Values',
                f'Dataset memiliki {missing_c:,} sel kosong. Disarankan untuk mengisi nilai kosong '
                f'menggunakan imputasi mean/median untuk variabel numerik dan modus untuk variabel '
                f'kategorikal. Jika proporsi missing values melebihi 50% pada suatu kolom, '
                f'pertimbangkan untuk menghapus kolom tersebut dari analisis.',
                C_YELLOW
            ))
        if dup_rows > 0:
            recoms.append((
                'R2. Pembersihan Duplikat',
                f'Ditemukan {dup_rows} baris duplikat yang berpotensi menghasilkan bias dalam analisis. '
                f'Lakukan deduplication dengan mempertahankan satu observasi per grup duplikat, '
                f'atau terapkan primary key constraint pada database sumber untuk mencegah duplikasi di masa depan.',
                C_RED
            ))
        if outliers_c > 0:
            recoms.append((
                'R3. Investigasi & Penanganan Outlier',
                f'Terdeteksi {outliers_c} nilai outlier menggunakan metode IQR. Lakukan validasi '
                f'domain untuk memverifikasi apakah nilai ekstrem tersebut valid secara konteks bisnis '
                f'atau merupakan kesalahan pencatatan. Jika terbukti error, terapkan IQR capping '
                f'(winsorization) untuk menetralkan dampaknya.',
                C_YELLOW
            ))
        if num_stats:
            high_skew = []
            for s in num_stats:
                try:
                    sk = _safe(s.get('Skewness','0'))
                    if sk != '\u2014' and abs(float(sk.replace(',','') or '0')) > 1.0:
                        high_skew.append(s.get('Column',''))
                except Exception:
                    pass
            if high_skew:
                recoms.append((
                    'R4. Transformasi Data Skewed',
                    f'Variabel {", ".join(high_skew[:4])} memiliki distribusi yang sangat miring '
                    f'(|skewness| > 1). Pertimbangkan transformasi logaritmik, akar kuadrat, atau '
                    f'Box-Cox sebelum digunakan dalam pemodelan statistik untuk memenuhi asumsi normalitas.',
                    C_BLUE
                ))
        recoms.append((
            f'R{len(recoms)+1}. Pembersihan Data Berkala',
            'Jadwalkan audit kualitas data secara berkala menggunakan DS Generator sebelum setiap '
            'siklus analisis. Dokumentasikan setiap keputusan cleaning untuk memastikan '
            'reproducibility dan transparansi proses analisis.',
            C_GREEN
        ))
        recoms.append((
            f'R{len(recoms)+1}. Eksplorasi Analisis Lanjutan',
            'Setelah pembersihan data selesai, lanjutkan ke analisis korelasi mendalam, '
            'pengujian hipotesis statistik, dan pemodelan prediktif jika relevan dengan tujuan bisnis. '
            'Dataset yang bersih adalah fondasi untuk model machine learning yang akurat dan andal.',
            C_CYAN
        ))

        for title, desc, col in recoms:
            rec_data = [[
                Paragraph(f'<b>{title}</b>', ParagraphStyle('RT', parent=styles['body_bold'], textColor=col)),
                Paragraph(desc, styles['body'])
            ]]
            rec_t = Table(rec_data, colWidths=[4.5*cm, 12*cm])
            rec_t.setStyle(TableStyle([
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING',    (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
                ('BACKGROUND',    (0,0), (-1,-1), C_LIGHT),
                ('LINEBEFORE',    (0,0), (0,-1),  3, col),
                ('BOX',           (0,0), (-1,-1),  0.5, colors.HexColor('#e2e8f0')),
            ]))
            story.append(rec_t)
            story.append(Spacer(1, 8))

        story.append(PageBreak())

    # ════════════════════════════════════════════
    # PENUTUP
    # ════════════════════════════════════════════
    if active('penutup'):
        _section_label(story, styles, 'XI', 'Penutup')

        story.append(Paragraph('10.1 Kesimpulan', styles['subbab']))
        story.append(Paragraph(
            f'Laporan analisis data eksplorasi ini telah berhasil menyajikan gambaran komprehensif '
            f'terhadap dataset <b>{filename}</b>. Dari total <b>{total_rows:,} observasi</b> dengan '
            f'<b>{total_cols} variabel</b> yang dianalisis, diperoleh beberapa temuan utama: '
            f'{"(1) terdapat " + str(missing_c) + " sel kosong yang perlu ditangani, " if missing_c > 0 else "(1) dataset tidak memiliki missing values, "}'
            f'{"(2) ditemukan " + str(dup_rows) + " baris duplikat, " if dup_rows > 0 else "(2) tidak ditemukan duplikasi data, "}'
            f'{"(3) terdeteksi " + str(outliers_c) + " nilai outlier yang memerlukan verifikasi, " if outliers_c > 0 else "(3) data berada dalam rentang nilai yang normal, "}'
            f'dan (4) seluruh variabel telah berhasil diklasifikasikan berdasarkan tipe datanya untuk analisis lebih lanjut.',
            styles['body']
        ))

        story.append(Paragraph('10.2 Keterbatasan', styles['subbab']))
        story.append(Paragraph(
            'Laporan ini memiliki beberapa keterbatasan yang perlu diperhatikan: '
            '(1) Analisis ini bersifat deskriptif dan tidak mencakup inferensi statistik atau pemodelan prediktif; '
            '(2) Kualitas insight yang dihasilkan bergantung pada kelengkapan dan representativitas data yang diunggah; '
            '(3) Interpretasi otomatis mungkin tidak selalu mencerminkan konteks domain bisnis yang spesifik dan '
            'perlu dikonfirmasi oleh pakar domain terkait.',
            styles['body']
        ))

        story.append(Paragraph('10.3 Penutup', styles['subbab']))
        story.append(Paragraph(
            'Demikian laporan analisis data ini disusun. Kami berharap temuan dan rekomendasi '
            'yang tersaji dapat memberikan kontribusi nyata dalam mendukung proses pengambilan '
            'keputusan yang berbasis data. Platform DS Generator terus dikembangkan untuk '
            'menghadirkan fitur analisis yang semakin canggih dan mudah digunakan.',
            styles['body']
        ))

        story.append(Spacer(1, 0.8*cm))
        story.append(Paragraph(
            f'<i>Laporan ini digenerate secara otomatis oleh DS Generator pada {today}, {time_}.</i>',
            styles['caption']
        ))

    # ════════════════════════════════════════════
    # BUILD PDF
    # ════════════════════════════════════════════
    try:
        doc = SimpleDocTemplate(
            dest_path,
            pagesize       = A4,
            leftMargin     = 1.5*cm,
            rightMargin    = 1.5*cm,
            topMargin      = 1.8*cm,
            bottomMargin   = 1.8*cm,
        )
        doc.build(story, canvasmaker=NumberedCanvas)
        return True
    except Exception as e:
        print(f'[PDF] Build error: {e}\n{traceback.format_exc()}')
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# FUNGSI LAMA — backward compatibility
# ═══════════════════════════════════════════════════════════════════════════════

def _build_sections_from_ctx(ctx):
    sections = [
        'kata_pengantar',
        'ringkasan',
        'quality',
        'num_stats',
        'cat_stats',
        'insights',
    ]
    if ctx.get('cleaning_summary') and ctx.get('cleaning_summary').get('rows_before', 0) > 0:
        sections.append('cleaning')
    return sections


def _build_payload(filename, ctx, custom_title='', custom_preface=''):
    df = None
    from backend.cleaning_engine import get_session
    sess = get_session(filename)
    if sess is not None:
        df = sess.df_current

    quality_report = ctx.get('quality_full') or {}
    num_stats = ctx.get('num_stats') or []
    cat_stats = ctx.get('cat_stats') or []
    insights = ctx.get('insights_id') or ctx.get('insights') or []
    cleaning_summary = ctx.get('cleaning_summary') or {}
    sections = _build_sections_from_ctx(ctx)

    return {
        'filename': filename,
        'df': df,
        'quality_report': quality_report,
        'num_stats': num_stats,
        'cat_stats': cat_stats,
        'insights': insights,
        'cleaning_summary': cleaning_summary,
        'sections': sections,
        'custom_title': custom_title,
        'custom_preface': custom_preface,
    }


def render_pdf_html(filename, ctx, custom_title='', custom_preface=''):
    from backend.html_report_generator import generate_html_report
    payload = _build_payload(filename, ctx, custom_title, custom_preface)
    return generate_html_report(**payload)


def _generate_report_plots(df, sess, cleaning_summary, temp_dir, lang='id'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import seaborn as sns

    generated_plots = {}

    if df is None:
        return generated_plots

    try:
        plt.rcParams['font.sans-serif'] = 'Arial'
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['text.color'] = '#334155'
        plt.rcParams['axes.labelcolor'] = '#475569'
        plt.rcParams['xtick.color'] = '#64748b'
        plt.rcParams['ytick.color'] = '#64748b'
        plt.rcParams['figure.facecolor'] = 'none'

        total_cells = df.size
        missing_cells = df.isna().sum().sum()
        filled_cells = total_cells - missing_cells

        # 1. completeness donut chart
        fig, ax = plt.subplots(figsize=(4, 3))
        from backend.report_translator import tr_report
        labels = ['Terisi', 'Kosong'] if lang == 'id' else ['Filled', 'Missing']
        sizes = [filled_cells, missing_cells]
        colors_list = ['#10b981', '#ef4444']
        if missing_cells == 0:
            labels = ['Terisi'] if lang == 'id' else ['Filled']
            sizes = [filled_cells]
            colors_list = ['#10b981']
            
        ax.pie(sizes, labels=labels, colors=colors_list, autopct='%1.1f%%', startangle=90, 
               textprops={'fontsize': 8, 'weight': 'bold'}, pctdistance=0.75,
               wedgeprops=dict(width=0.4, edgecolor='w'))
        ax.set_title(tr_report('Dataset Completeness', lang), fontsize=10, weight='bold', pad=10)
        fig.tight_layout()
        completeness_path = os.path.join(temp_dir, 'completeness.png')
        fig.savefig(completeness_path, dpi=120, bbox_inches='tight')
        plt.close(fig)
        generated_plots['completeness'] = completeness_path

        # 2. missing_bars
        missing_series = df.isna().sum()
        missing_cols = missing_series[missing_series > 0].sort_values(ascending=True)
        if not missing_cols.empty:
            fig, ax = plt.subplots(figsize=(5, 3))
            missing_cols.tail(10).plot(kind='barh', color='#f59e0b', ax=ax, width=0.6)
            ax.set_title(tr_report('Top Missing Values per Column', lang), fontsize=10, weight='bold', pad=10)
            ax.set_xlabel(tr_report('Count', lang), fontsize=8)
            ax.tick_params(axis='both', labelsize=8)
            ax.grid(True, axis='x', linestyle='--', alpha=0.5)
            fig.tight_layout()
            missing_bars_path = os.path.join(temp_dir, 'missing_bars.png')
            fig.savefig(missing_bars_path, dpi=120, bbox_inches='tight')
            plt.close(fig)
            generated_plots['missing_bars'] = missing_bars_path

        # 3. correlation heatmap
        num_df = df.select_dtypes(include=[np.number])
        if len(num_df.columns) > 1:
            num_df = num_df.fillna(num_df.mean())
            corr_cols = num_df.columns[:10]
            corr_matrix = num_df[corr_cols].corr()
            
            fig, ax = plt.subplots(figsize=(4.5, 3.5))
            sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap='coolwarm', vmin=-1, vmax=1,
                        annot_kws={"size": 6, "weight": "bold"}, cbar=False, ax=ax)
            ax.set_title(tr_report('Pearson Correlation Heatmap', lang), fontsize=10, weight='bold', pad=10)
            ax.tick_params(axis='both', labelsize=7)
            fig.tight_layout()
            correlation_path = os.path.join(temp_dir, 'correlation.png')
            fig.savefig(correlation_path, dpi=120, bbox_inches='tight')
            plt.close(fig)
            generated_plots['correlation'] = correlation_path

        # 4. cleaning_impact
        if cleaning_summary:
            rows_before = cleaning_summary.get('rows_before', len(df))
            rows_after = cleaning_summary.get('rows_after', len(df))
            if rows_before != rows_after:
                fig, ax = plt.subplots(figsize=(4, 3))
                bars = ax.bar([tr_report('Before', lang), tr_report('After', lang)], [rows_before, rows_after], color=['#ef4444', '#10b981'], width=0.5)
                ax.set_title(tr_report('Rows Before vs After Cleaning', lang), fontsize=10, weight='bold', pad=10)
                ax.tick_params(axis='both', labelsize=8)
                for bar in bars:
                    height = bar.get_height()
                    ax.annotate(f'{height:,}',
                                xy=(bar.get_x() + bar.get_width() / 2, height),
                                xytext=(0, 3),
                                textcoords="offset points",
                                ha='center', va='bottom', fontsize=8, weight='bold')
                fig.tight_layout()
                cleaning_impact_path = os.path.join(temp_dir, 'cleaning_impact.png')
                fig.savefig(cleaning_impact_path, dpi=120, bbox_inches='tight')
                plt.close(fig)
                generated_plots['cleaning_impact'] = cleaning_impact_path
    except Exception as e:
        print(f"[PDF Generator] Error drawing Matplotlib charts: {e}")
        traceback.print_exc()

    return generated_plots


def generate_custom_pdf_report(dest_path, filename, ctx, title, author, notes, selected_tables, selected_charts, narratives, lang='id'):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, KeepTogether, Image
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfgen import canvas as rl_canvas
        import tempfile
        import datetime
    except ImportError:
        raise ImportError("ReportLab tidak terinstall. Jalankan: pip install reportlab")

    from backend.cleaning_engine import get_session
    sess = get_session(filename)
    df = sess.df_current if sess else None

    quality_report  = ctx.get('quality_full') or {}
    metrics         = ctx.get('metrics') or {}
    num_stats       = ctx.get('num_stats') or []
    cat_stats       = ctx.get('cat_stats') or []
    cleaning_summary = ctx.get('cleaning_summary') or {}
    is_cleaned      = bool(ctx.get('is_cleaned', False))

    summary = quality_report.get('summary', {})

    def _to_int(v, default=0):
        if v is None:
            return default
        try:
            s = str(v).replace(',', '').replace('%', '').strip()
            return int(float(s))
        except Exception:
            return default

    def _to_float(v, default=0.0):
        if v is None:
            return default
        try:
            return float(str(v).replace(',', '').replace('%', '').strip())
        except Exception:
            return default

    total_rows  = _to_int(summary.get('total_rows',  metrics.get('total_rows',  len(df) if df is not None else 0)))
    total_cols  = _to_int(summary.get('total_cols',  metrics.get('total_columns', len(df.columns) if df is not None else 0)))
    missing     = _to_int(summary.get('missing_cells',  0))
    miss_pct    = _to_float(summary.get('missing_pct', 0))
    dupe        = _to_int(summary.get('duplicate_rows', 0))
    outliers    = _to_int(summary.get('total_outliers', 0))

    status_label = "RAW DATASET REPORT" if not is_cleaned else "CLEANED DATASET REPORT"
    status_color = "#e31c23" if not is_cleaned else "#16a34a"
    status_html = f"<font color='{status_color}'><b>{status_label}</b></font>"

    primary_color = colors.HexColor('#1a1b5c')
    secondary_color = colors.HexColor('#e31c23')
    text_dark = colors.HexColor('#1e293b')
    text_muted = colors.HexColor('#64748b')
    bg_light = colors.HexColor('#f8fafc')

    class NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._draw_page_decorations(num_pages)
                super().showPage()
            super().save()

        def _draw_page_decorations(self, page_count):
            self.saveState()
            self.setFont("Helvetica-BoldOblique", 8)
            self.setFillColor(primary_color)

            if self._pageNumber > 1:
                self.drawString(54, 750, f"Laporan Analisis Data Kustom \u2014 {filename}")
                self.drawRightString(558, 750, f"{status_label}")
                self.setStrokeColor(colors.HexColor("#cbd5e1"))
                self.setLineWidth(0.5)
                self.line(54, 742, 558, 742)

                self.setFont("Helvetica", 8)
                self.setFillColor(text_muted)
                page_text = f"Halaman {self._pageNumber} dari {page_count}"
                self.drawRightString(558, 40, page_text)
                self.drawString(54, 40,
                    f"Program Studi Sains Data ITSB | Kelompok 2 | {datetime.datetime.now().strftime('%d %b %Y')}")
                self.setStrokeColor(colors.HexColor("#cbd5e1"))
                self.setLineWidth(0.5)
                self.line(54, 52, 558, 52)
            self.restoreState()

    doc = SimpleDocTemplate(
        dest_path,
        pagesize=letter,
        leftMargin=54, rightMargin=54,
        topMargin=54, bottomMargin=54
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('CustomTitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=14, leading=18,
        textColor=primary_color, alignment=1, spaceAfter=14)
    
    author_style = ParagraphStyle('CustomAuthor', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9, leading=12,
        textColor=text_dark, alignment=1, spaceAfter=2)
        
    inst_style = ParagraphStyle('CustomInst', parent=styles['Normal'],
        fontName='Helvetica-Oblique', fontSize=8, leading=11,
        textColor=text_muted, alignment=1, spaceAfter=14)
        
    preface_heading = ParagraphStyle('CustomPrefaceHeading', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, leading=13,
        textColor=primary_color, spaceAfter=6, alignment=1)
        
    preface_body = ParagraphStyle('CustomPrefaceBody', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, leading=13.5,
        textColor=text_dark, spaceAfter=8, alignment=4)
        
    h1_style = ParagraphStyle('CustomH1', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=12, leading=16,
        textColor=primary_color, spaceBefore=16, spaceAfter=8, keepWithNext=True)
        
    h2_style = ParagraphStyle('CustomH2', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, leading=13,
        textColor=primary_color, spaceBefore=10, spaceAfter=6, keepWithNext=True)
        
    body_style = ParagraphStyle('CustomBodyText', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, leading=13.5,
        textColor=text_dark, spaceAfter=8, alignment=4)
        
    th_style = ParagraphStyle('CustomTableHeader', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8, leading=10,
        textColor=colors.white)
        
    td_style = ParagraphStyle('CustomTableCell', parent=styles['Normal'],
        fontName='Helvetica', fontSize=7.5, leading=9.5,
        textColor=text_dark)
        
    caption_style = ParagraphStyle('CustomCaption', parent=styles['Normal'],
        fontName='Helvetica-Oblique', fontSize=7.5, leading=10,
        textColor=text_muted, alignment=1, spaceBefore=4, spaceAfter=10)

    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, bg_light]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEABOVE', (0, 0), (-1, 0), 1.5, primary_color),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, primary_color),
        ('LINEBELOW', (0, 1), (-1, -2), 0.5, colors.HexColor('#e2e8f0')),
        ('LINEBELOW', (0, -1), (-1, -1), 1.5, primary_color),
    ])

    def make_bab_heading(bab_num, bab_title):
        mapping = {
            'BAB I': '1',
            'BAB II': '2',
            'BAB III': '3',
            'BAB IV': '4',
            'BAB V': '5',
            'BAB VI': '6'
        }
        num = mapping.get(bab_num.strip().upper(), bab_num)
        elements = [
            Spacer(1, 14),
            Paragraph(f"<b>{num}. {bab_title.upper()}</b>", h1_style),
            Spacer(1, 6)
        ]
        return elements

    def make_pasal_heading(pasal_num, pasal_title):
        elements = [
            Spacer(1, 10),
            Paragraph(f"<b>{pasal_num} {pasal_title}</b>", h2_style),
            Spacer(1, 4)
        ]
        return elements

    story = []
    temp_dir_obj = tempfile.TemporaryDirectory()
    temp_dir = temp_dir_obj.name
    
    try:
        from backend.report_generator import _generate_report_plots
        plots = _generate_report_plots(df, sess, cleaning_summary, temp_dir, lang=lang)

        # Centered ITSB Logo on Page 1 top
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        possible_logo_paths = [
            os.path.join(root_dir, 'assets', 'itsb_logo.png'),
            os.path.join(root_dir, 'assets', 'logo.png'),
            os.path.join(root_dir, 'frontend', 'static', 'img', 'itsb_logo.png'),
        ]
        logo_file = None
        for path_candidate in possible_logo_paths:
            if os.path.exists(path_candidate):
                logo_file = path_candidate
                break

        if logo_file:
            logo_img = Image(logo_file, width=80, height=80)
            logo_img.hAlign = 'CENTER'
            story.append(Spacer(1, 40))
            story.append(logo_img)
            story.append(Spacer(1, 10))

        story.append(Paragraph(title or tr_report("Laporan Analisis Data Kustom", lang), title_style))
        story.append(Paragraph(f"{tr_report('Disusun Oleh', lang)}: {author or 'Tim Analis'}", author_style))
        story.append(Paragraph(f"{tr_report('Program Studi Sains Data', lang)}, {tr_report('Fakultas Teknik dan Desain', lang)}<br/>{tr_report('Institut Teknologi Sains Bandung', lang)}", inst_style))
        
        story.append(Spacer(1, 30))
        
        # Meta grid on cover page
        abstract_meta_data = [
            [Paragraph(f"<b>{tr_report('Parameter Dataset', lang)}</b>", ParagraphStyle('SubH', parent=td_style, fontName='Helvetica-Bold', fontSize=8, textColor=primary_color)), Paragraph("", td_style)],
            [Paragraph(tr_report("Nama Dataset File", lang), td_style), Paragraph(filename, td_style)],
            [Paragraph(tr_report("Jumlah Baris (Observasi)", lang), td_style), Paragraph(f"{total_rows:,}", td_style)],
            [Paragraph(tr_report("Jumlah Kolom (Variabel)", lang), td_style), Paragraph(f"{total_cols:,}", td_style)],
            [Paragraph(tr_report("Nilai Kosong", lang), td_style), Paragraph(f"{missing:,} sel ({miss_pct:.1f}%)", td_style)],
            [Paragraph(tr_report("Status Pemrosesan", lang), td_style), Paragraph(tr_report(status_label, lang), td_style)],
        ]
        abstract_meta_table = Table(abstract_meta_data, colWidths=[150, 354])
        abstract_meta_table.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#cbd5e1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(abstract_meta_table)
        story.append(PageBreak())

        if notes.strip():
            story.append(Paragraph("<b>KATA PENGANTAR / PRAKATA</b>", preface_heading))
            story.append(Spacer(1, 4))
            notes_p = Paragraph(notes.strip().replace('\n', '<br/>'), preface_body)
            story.append(notes_p)
            story.append(PageBreak())

        def append_narrative(comp_id, default_text):
            text = narratives.get(comp_id) or default_text
            for p_text in text.strip().split('\n'):
                if p_text.strip():
                    story.append(Paragraph(p_text.strip(), body_style))

        story.extend(make_bab_heading("BAB I", "PENDAHULUAN"))
        story.extend(make_pasal_heading("1.1", "Latar Belakang & Tujuan Analisis"))

        default_background = (
            f"Analisis Eksplorasi Data (Exploratory Data Analysis - EDA) merupakan fondasi utama dan tahapan "
            f"paling krusial dalam setiap siklus sains data profesional, baik dalam kerangka kerja CRISP-DM "
            f"maupun OSEMN. Melalui pengenalan dini terhadap properti statistik dan kualitas data pada dataset "
            f"<b>{filename}</b>, seorang analis dapat memetakan kekuatan serta keterbatasan informasi yang terekam "
            f"secara terperinci. Aktivitas ini mencakup penelaahan mendalam terhadap karakteristik sebaran variabel, "
            f"pola ketersebaran missing values, densitas pencilan (outliers), dan konsistensi tipe data di setiap kolom.\n\n"
            f"Metodologi eksplorasi data otomatis (Auto-EDA) diterapkan untuk meningkatkan efisiensi waktu deteksi tanpa "
            f"mengorbankan kedalaman analisis statistik. Pemetaan kualitas data ini bertujuan untuk mengidentifikasi "
            f"cacat struktural (anomali) sedini mungkin, mengingat bias hasil analisis deskriptif atau penurunan akurasi "
            f"model prediktif (machine learning) hampir selalu bermula dari rendahnya kualitas data mentah yang masuk ke "
            f"dalam sistem (garbage in, garbage out).\n\n"
            f"Dengan demikian, penyusunan laporan kustom ini memiliki tujuan strategis untuk menyajikan wawasan kuantitatif "
            f"mengenai tingkat kelayakan dataset bagi kebutuhan pemodelan statistik tingkat lanjut. Wawasan yang diperoleh "
            f"akan menjadi acuan objektif dalam merancang pipa pembersihan data (data cleaning pipeline) serta strategi "
            f"rekayasa fitur (feature engineering) yang valid, akurat, dan dapat dipertanggungjawabkan secara ilmiah."
        )
        append_narrative('doc_background', default_background)
        story.append(Spacer(1, 10))

        has_pembahasan = (len(selected_tables) + len(selected_charts)) > 0
        if has_pembahasan:
            story.append(PageBreak())
            story.extend(make_bab_heading("BAB II", "PEMBAHASAN & ANALISIS DATA"))

            current_pasal = 1

            if 'table_summary' in selected_tables:
                story.extend(make_pasal_heading(f"2.{current_pasal}", "Ringkasan Metrik Kualitas Data"))
                current_pasal += 1

                summary_data = [
                    [Paragraph("<b>Karakteristik Metrik</b>", th_style), Paragraph("<b>Nilai / Keterangan Observasi</b>", th_style)],
                    [Paragraph("Total Baris (Observasi)", td_style), Paragraph(f"{total_rows:,}", td_style)],
                    [Paragraph("Total Kolom (Variabel)", td_style), Paragraph(f"{total_cols:,}", td_style)],
                    [Paragraph("Sel Kosong (Missing Cells)", td_style), Paragraph(f"{missing:,} sel ({miss_pct:.1f}%)", td_style)],
                    [Paragraph("Baris Duplikat Terdeteksi", td_style), Paragraph(f"{dupe:,}", td_style)],
                    [Paragraph("Pencilan Terdeteksi (Outliers)", td_style), Paragraph(f"{outliers:,}", td_style)],
                    [Paragraph("Status Pembersihan Data", td_style), Paragraph(status_html, td_style)],
                ]
                summary_table = Table(summary_data, colWidths=[240, 264])
                summary_table.setStyle(table_style)
                story.append(summary_table)
                story.append(Paragraph("<i>Tabel 1. Ringkasan metrik kualitas dan kelengkapan data dataset.</i>", caption_style))

                default_summary_narrative = (
                    f"Tabel 1 memaparkan parameter metrik ringkasan kualitas data untuk dataset {filename}. "
                    f"Berdasarkan hasil pemindaian awal, dataset ini tercatat memiliki ukuran dimensi sebanyak {total_rows:,} baris "
                    f"observasi dan {total_cols:,} kolom variabel. Dari keseluruhan dimensi tersebut, diidentifikasi adanya "
                    f"cacat data berupa {missing:,} sel kosong (missing cells) yang mewakili {miss_pct:.1f}% dari kapasitas "
                    f"penyimpanan data keseluruhan. Tingkat duplikasi baris berada pada angka {dupe:,} baris observasi berulang, "
                    f"sementara keberadaan pencilan (outliers) tercatat sebanyak {outliers:,} pencilan.\n\n"
                    f"Informasi kualitas data yang tersaji pada Tabel 1 menegaskan status pemrosesan data saat ini yang berada pada status "
                    f"<b>{status_label}</b>. Jika tingkat kehilangan data atau pencilan melebihi ambang batas toleransi (biasanya 5%), "
                    f"maka tindakan pembersihan data wajib dilakukan. Keberadaan baris duplikat sebanyak {dupe:,} baris juga menunjukkan "
                    f"adanya redundansi pencatatan yang dapat mengganggu asumsi independensi observasi pada pengujian statistik parametrik."
                )
                append_narrative('table_summary', default_summary_narrative)
                story.append(Spacer(1, 10))

            if 'table_columns' in selected_tables:
                columns = quality_report.get('columns', [])
                if columns:
                    story.append(PageBreak())
                    story.extend(make_pasal_heading(f"2.{current_pasal}", "Evaluasi Integritas Kolom Variabel"))
                    current_pasal += 1

                    col_rows = [[
                        Paragraph("<b>Nama Kolom</b>", th_style),
                        Paragraph("<b>Tipe Data</b>", th_style),
                        Paragraph("<b>Missing</b>", th_style),
                        Paragraph("<b>Missing %</b>", th_style),
                        Paragraph("<b>Unik</b>", th_style),
                        Paragraph("<b>Outlier</b>", th_style),
                        Paragraph("<b>Status Kualitas</b>", th_style),
                    ]]
                    for c in columns:
                        status_text = c.get('issues', 'OK')
                        status_color_col = "#16a34a" if status_text == 'OK' else "#e31c23"
                        col_rows.append([
                            Paragraph(str(c.get('column', '\u2014')), td_style),
                            Paragraph(str(c.get('dtype', '\u2014')), td_style),
                            Paragraph(str(c.get('missing', 0)), td_style),
                            Paragraph(f"{c.get('missing_pct', 0):.1f}%", td_style),
                            Paragraph(str(c.get('unique', '\u2014')), td_style),
                            Paragraph(str(c.get('outliers', 0)), td_style),
                            Paragraph(f"<font color='{status_color_col}'><b>{status_text}</b></font>", td_style),
                        ])
                    col_table = Table(col_rows, colWidths=[120, 60, 60, 60, 50, 50, 104])
                    col_table.setStyle(table_style)
                    story.append(col_table)
                    story.append(Paragraph(f"<i>{tr_report('Tabel 2. Rincian kualitas data per kolom variabel.', lang)}</i>", caption_style))
                    story.append(Spacer(1, 10))

        # --- Numerical descriptive stats ---
        if 'num_stats' in selected_tables:
            if num_stats:
                story.append(PageBreak())
                story.extend(make_pasal_heading(f"2.{current_pasal}", tr_report("Statistik Deskriptif - Variabel Numerik", lang)))
                current_pasal += 1
                
                num_headers = [
                    Paragraph(tr_report("Nama Variabel", lang), th_style),
                    Paragraph(tr_report("Rata-rata", lang), th_style),
                    Paragraph(tr_report("Median", lang), th_style),
                    Paragraph("Min", th_style),
                    Paragraph("Max", th_style),
                    Paragraph(tr_report("Standar Deviasi", lang), th_style),
                    Paragraph("Skewness", th_style),
                ]
                num_rows = [num_headers]
                for ns in num_stats:
                    num_rows.append([
                        Paragraph(str(ns.get('Column', '\u2014')), td_style),
                        Paragraph(str(ns.get('Mean', '\u2014')), td_style),
                        Paragraph(str(ns.get('Median', '\u2014')), td_style),
                        Paragraph(str(ns.get('Min', '\u2014')), td_style),
                        Paragraph(str(ns.get('Max', '\u2014')), td_style),
                        Paragraph(str(ns.get('Std Dev', '\u2014')), td_style),
                        Paragraph(str(ns.get('Skewness', '\u2014')), td_style),
                    ])
                num_table = Table(num_rows, colWidths=[120, 64, 64, 64, 64, 64, 64])
                num_table.setStyle(table_style)
                story.append(num_table)
                story.append(Paragraph(f"<i>{tr_report('Tabel 3. Ringkasan analisis statistik deskriptif variabel numerik.', lang)}</i>", caption_style))
                story.append(Spacer(1, 10))

        # --- Categorical descriptive stats ---
        if 'cat_stats' in selected_tables:
            if cat_stats:
                story.append(PageBreak())
                story.extend(make_pasal_heading(f"2.{current_pasal}", tr_report("Statistik Deskriptif - Variabel Kategorikal", lang)))
                current_pasal += 1
                
                cat_headers = [
                    Paragraph(tr_report("Nama Variabel", lang), th_style),
                    Paragraph(tr_report("Nilai Unik", lang), th_style),
                    Paragraph(tr_report("Modus (Dominan)", lang), th_style),
                    Paragraph(tr_report("Frekuensi Modus", lang), th_style),
                    Paragraph(tr_report("Persentase Modus", lang), th_style),
                ]
                cat_rows = [cat_headers]
                for cs in cat_stats:
                    cat_rows.append([
                        Paragraph(str(cs.get('Column', '\u2014')), td_style),
                        Paragraph(str(cs.get('Unique', '\u2014')), td_style),
                        Paragraph(str(cs.get('Mode', '\u2014')), td_style),
                        Paragraph(str(cs.get('Mode Freq', '\u2014')), td_style),
                        Paragraph(str(cs.get('Mode %', '\u2014')), td_style),
                    ])
                cat_table = Table(cat_rows, colWidths=[120, 64, 160, 80, 80])
                cat_table.setStyle(table_style)
                story.append(cat_table)
                story.append(Paragraph(f"<i>{tr_report('Tabel 4. Ringkasan sebaran frekuensi dan dominasi modus variabel kategorikal.', lang)}</i>", caption_style))
                story.append(Spacer(1, 10))

        # --- Cleaning Comparison ---
        if 'cleaning' in selected_tables:
            if cleaning_summary and cleaning_summary.get('rows_before', 0) > 0:
                story.append(PageBreak())
                story.extend(make_pasal_heading(f"2.{current_pasal}", tr_report("Proses Pembersihan Data", lang)))
                current_pasal += 1
                
                rows_b = _to_int(cleaning_summary.get('rows_before', len(df)))
                rows_a = _to_int(cleaning_summary.get('rows_after', len(df)))
                cols_b = _to_int(cleaning_summary.get('cols_before', len(df.columns)))
                cols_a = _to_int(cleaning_summary.get('cols_after', len(df.columns)))
                miss_b = _to_int(cleaning_summary.get('missing_before', 0))
                miss_a = _to_int(cleaning_summary.get('missing_after', 0))
                
                diff_data = [
                    [Paragraph(f"<b>{tr_report('Metrik Evaluasi', lang)}</b>", th_style),
                     Paragraph(f"<b>{tr_report('Sebelum', lang)}</b>", th_style),
                     Paragraph(f"<b>{tr_report('Sesudah', lang)}</b>", th_style),
                     Paragraph(f"<b>{tr_report('Dampak Reduksi', lang)}</b>", th_style)],
                    [Paragraph(tr_report("Jumlah Baris (Observasi)", lang), td_style),
                     Paragraph(f"{rows_b:,}", td_style),
                     Paragraph(f"{rows_a:,}", td_style),
                     Paragraph(f"-{rows_b - rows_a:,} {tr_report('baris', lang)}", td_style)],
                    [Paragraph(tr_report("Jumlah Kolom (Variabel)", lang), td_style),
                     Paragraph(str(cols_b), td_style),
                     Paragraph(str(cols_a), td_style),
                     Paragraph(f"-{cols_b - cols_a} {tr_report('kolom', lang)}", td_style)],
                    [Paragraph(tr_report("Sel Kosong (Missing)", lang), td_style),
                     Paragraph(f"{miss_b:,}", td_style),
                     Paragraph(f"{miss_a:,}", td_style),
                     Paragraph(f"-{miss_b - miss_a:,} {tr_report('sel', lang)}", td_style)],
                ]
                diff_table_small = Table(diff_data, colWidths=[160, 100, 100, 144])
                diff_table_small.setStyle(table_style)
                story.append(diff_table_small)
                story.append(Paragraph(f"<i>{tr_report('Tabel 5. Evaluasi perbandingan metrik kebersihan data sebelum vs sesudah pembersihan.', lang)}</i>", caption_style))
                story.append(Spacer(1, 10))

        # --- Cleaning Log ---
        if 'cleaning_log' in selected_tables:
            logs = cleaning_summary.get('log', [])
            if logs:
                story.append(PageBreak())
                story.extend(make_pasal_heading(f"2.{current_pasal}", tr_report("Log Tindakan Pembersihan Detil Per Kolom", lang)))
                current_pasal += 1
                
                log_rows = [[Paragraph(f"<b>{tr_report('Keterangan Modifikasi', lang)}</b>", th_style)]]
                for item in logs:
                    log_rows.append([Paragraph(f"• {tr_report(item, lang)}", td_style)])
                log_table = Table(log_rows, colWidths=[504])
                log_table.setStyle(table_style)
                story.append(log_table)
                story.append(Paragraph(f"<i>{tr_report('Tabel 6. Log urutan tindakan data cleaning per kolom.', lang)}</i>", caption_style))
                story.append(Spacer(1, 10))

        # ── Visualizations ──
        if selected_charts:
            story.append(PageBreak())
            story.extend(make_bab_heading("BAB III", tr_report("Visualisasi Data", lang)))
            current_pasal = 1
            
            # Figure 1: Completeness
            if 'chart_completeness' in selected_charts and 'completeness' in plots:
                story.extend(make_pasal_heading(f"3.{current_pasal}", tr_report("Visualisasi Kelengkapan Variabel", lang)))
                current_pasal += 1
                img = Image(plots['completeness'], width=240, height=180)
                img.hAlign = 'CENTER'
                story.append(img)
                story.append(Paragraph(f"<i>{tr_report('Gambar 1. Distribusi persentase sel terisi (filled) vs kosong (missing values) pada dataset.', lang)}</i>", caption_style))
                default_comp_desc = (
                    "Visualisasi di atas memperlihatkan proporsi kelengkapan sel data. Sel terisi (filled) "
                    "yang dominan mengindikasikan kelayakan analisis deskriptif dasar."
                )
                append_narrative('chart_completeness', tr_report(default_comp_desc, lang))
                story.append(Spacer(1, 10))

            # Figure 2: Missing
            if 'chart_missing' in selected_charts and 'missing_bars' in plots:
                story.extend(make_pasal_heading(f"3.{current_pasal}", tr_report("Visualisasi Distribusi Nilai Kosong", lang)))
                current_pasal += 1
                img = Image(plots['missing_bars'], width=300, height=180)
                img.hAlign = 'CENTER'
                story.append(img)
                story.append(Paragraph(f"<i>{tr_report('Gambar 2. Jumlah nilai kosong (missing values) tertinggi berdasarkan masing-masing kolom variabel.', lang)}</i>", caption_style))
                default_miss_desc = (
                    "Grafik batang di atas mengidentifikasi kolom-kolom dengan tingkat kekosongan tertinggi, "
                    "yang mendasari penentuan strategi imputasi data."
                )
                append_narrative('chart_missing', tr_report(default_miss_desc, lang))
                story.append(Spacer(1, 10))

            # Figure 3: Correlation
            if 'chart_correlation' in selected_charts and 'correlation' in plots:
                story.extend(make_pasal_heading(f"3.{current_pasal}", tr_report("Visualisasi Korelasi Variabel Numerik", lang)))
                current_pasal += 1
                img = Image(plots['correlation'], width=260, height=200)
                img.hAlign = 'CENTER'
                story.append(img)
                story.append(Paragraph(f"<i>{tr_report('Gambar 3. Matriks koefisien korelasi Pearson antar variabel numerik terpilih.', lang)}</i>", caption_style))
                default_corr_desc = (
                    "Peta panas korelasi mengukur kekuatan hubungan linier antar variabel numerik. "
                    "Koefisien absolut tinggi menunjukkan potensi multikolinearitas."
                )
                append_narrative('chart_correlation', tr_report(default_corr_desc, lang))
                story.append(Spacer(1, 10))

            # Figure 4: Cleaning
            if 'chart_cleaning' in selected_charts and 'cleaning_impact' in plots:
                story.extend(make_pasal_heading(f"3.{current_pasal}", tr_report("Visualisasi Dampak Data Cleaning", lang)))
                current_pasal += 1
                img = Image(plots['cleaning_impact'], width=240, height=180)
                img.hAlign = 'CENTER'
                story.append(img)
                story.append(Paragraph(f"<i>{tr_report('Gambar 4. Dampak eliminasi baris sebelum vs sesudah dilakukan proses pembersihan data.', lang)}</i>", caption_style))
                default_clean_desc = (
                    "Perbandingan volume baris sebelum dan sesudah data cleaning untuk memastikan bahwa "
                    "reduksi baris akibat pembersihan tidak memicu hilangnya representasi data secara berlebihan."
                )
                append_narrative('chart_cleaning', tr_report(default_clean_desc, lang))
                story.append(Spacer(1, 10))

        # ── AI Insights ──
        if auto_insights:
            story.append(PageBreak())
            story.extend(make_bab_heading("BAB IV", tr_report("Temuan Kunci & Insight Otomatis", lang)))
            for idx, ins in enumerate(auto_insights[:12], 1):
                ins_title = tr_report(ins.get('title', 'Temuan'), lang)
                ins_desc = tr_report(ins.get('desc', ''), lang)
                story.append(Paragraph(f"<b>{idx}. {ins_title}</b>", ParagraphStyle('CustomInsH', parent=body_style, fontName='Helvetica-Bold')))
                story.append(Paragraph(ins_desc, body_style))
                story.append(Spacer(1, 6))

        # ── Conclusion & Recommendations ──
        story.append(PageBreak())
        story.extend(make_bab_heading("BAB PENUTUP", tr_report("Kesimpulan & Rekomendasi", lang)))
        
        # Kesimpulan
        story.extend(make_pasal_heading("1", tr_report("Kesimpulan Kondisi Data", lang)))
        if is_cleaned:
            conclusion_text = (
                "Berdasarkan sebaran metrik kualitas pasca-pembersihan, dataset saat ini telah dinyatakan "
                "bersih (Cleaned Data) dengan tingkat kelengkapan sel data mencapai 100%. Anomali nilai duplikat "
                "telah dieliminasi, dan outliers telah dikontrol dengan baik. Peneliti menyatakan bahwa dataset "
                "layak dan siap digunakan untuk konstruksi model statistika inferensial maupun machine learning."
            )
        else:
            conclusion_text = (
                "Berdasarkan analisis kualitas awal, dataset mentah (Raw Data) ini terindikasi memiliki cacat "
                "integritas berupa sel kosong dan anomali pencilan (outliers). Penggunaan data mentah ini "
                "secara langsung sangat rawan memicu bias eksposisi model. Sangat disarankan bagi analis "
                "untuk menjalankan modul Data Cleaning terlebih dahulu sebelum melakukan analisis model inferensial lanjutan."
            )
        story.append(Paragraph(tr_report(conclusion_text, lang), body_style))
        
        # Saran
        story.extend(make_pasal_heading("2", tr_report("Saran & Tindak Lanjut", lang)))
        if is_cleaned:
            recom_text = (
                "1. Segera lakukan pembagian dataset (train-test split) untuk kebutuhan pemodelan.<br/>"
                "2. Terapkan normalisasi/standarisasi variabel numerik sebelum menjalankan algoritma klasterisasi atau regresi.<br/>"
                "3. Evaluasi kembali variabel kategorik pasca-imputasi modus untuk mendeteksi skewness kategori."
            )
        else:
            recom_text = (
                "1. Jalankan fitur pembersihan data (imputasi nilai hilang dan eliminasi baris duplikat).<br/>"
                "2. Lakukan standarisasi penulisan kategori agar format homogen.<br/>"
                "3. Capping nilai outliers menggunakan metode IQR untuk menstabilkan skewness sebaran variabel numerik."
            )
        story.append(Paragraph(tr_report(recom_text, lang), body_style))
        story.append(Spacer(1, 20))

        # Signature Block
        sig_date = datetime.datetime.now().strftime("%d %B %Y")
        sig_time = datetime.datetime.now().strftime("%H.%M")
        sig_text = (
            f"{tr_report('Ditetapkan di Kota Deltamas', lang)}<br/>"
            f"{tr_report('Pada tanggal', lang)} {sig_date}<br/>"
            f"{tr_report('Pukul', lang)} {sig_time} WIB<br/><br/>"
            f"<b>{tr_report('Disahkan Oleh', lang)}:</b><br/>"
            f"{tr_report('Analis Laporan Kustom', lang)}<br/><br/><br/><br/>"
            f"<u>{author}</u><br/>"
            f"{tr_report('Program Studi Sains Data ITSB', lang)}"
        )
        sig_paragraph = Paragraph(sig_text, ParagraphStyle('CustomSigText', fontName='Helvetica', fontSize=9, leading=13))
        sig_table = Table([[sig_paragraph]], colWidths=[200])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        
        outer_layout = Table([["", sig_table]], colWidths=[304, 200])
        outer_layout.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(outer_layout)

        # Build Document
        doc.build(story, canvasmaker=NumberedCanvas)
                  
    finally:
        try:
            temp_dir_obj.cleanup()
        except Exception:
            pass

    return True