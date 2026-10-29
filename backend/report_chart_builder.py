"""
Pilih & generate beberapa chart paling representatif untuk PDF report.
Dipanggil dari app.py sebelum generate_pdf_report(), hasilnya dimasukkan
ke dict `chart_images` yang sudah dikenal oleh report_generator.py.

Chart key format mengikuti konvensi yang sudah ada:
  - 'histogram_<col>'  untuk histogram numerik
  - 'heatmap_all'      untuk correlation heatmap
  - 'bar_<col>'        untuk bar chart kategorikal
"""
from backend.viz_engine import generate_master_chart
from backend.chart_to_image import plotly_fig_to_png_bytes


def build_report_charts(df, num_cols, cat_cols, num_stats,
                        max_numeric=3, max_categorical=2):
    """
    Return dict  { chart_key: png_bytes, ... } siap masuk chart_images.
    """
    charts = {}

    # ── 1. Histogram: kolom numerik dengan |skewness| tertinggi ────────────
    sorted_num = []
    if num_stats:
        try:
            sorted_num = sorted(
                [s for s in num_stats if s.get('Skewness') not in (None, 'N/A')],
                key=lambda s: abs(float(s['Skewness'])),
                reverse=True,
            )
        except Exception:
            sorted_num = num_stats

    priority_cols = (
        [s['Column'] for s in sorted_num[:max_numeric]]
        if sorted_num
        else num_cols[:max_numeric]
    )

    for col in priority_cols:
        if col not in df.columns:
            continue
        try:
            result = generate_master_chart(
                df, num_cols, cat_cols, 'numerical', 'histogram', col_x=col
            )
            if result and result.get('ok') and result.get('chart'):
                png = plotly_fig_to_png_bytes(result['chart'])
                if png:
                    charts[f'histogram_{col}'] = png
        except Exception as e:
            print(f"[report_chart_builder] Skip histogram {col}: {e}")

    # ── 2. Correlation Heatmap (jika >= 2 kolom numerik) ───────────────────
    if len(num_cols) >= 2:
        try:
            result = generate_master_chart(
                df, num_cols, cat_cols, 'bivariate', 'heatmap'
            )
            if result and result.get('ok') and result.get('chart'):
                png = plotly_fig_to_png_bytes(
                    result['chart'], width=600, height=600
                )
                if png:
                    charts['heatmap_all'] = png
        except Exception as e:
            print(f"[report_chart_builder] Skip heatmap: {e}")

    # ── 3. Bar chart kategorikal (skip kolom unik terlalu banyak) ───────────
    cat_candidates = [
        c for c in cat_cols
        if c in df.columns and df[c].nunique() <= 20
    ][:max_categorical]

    for col in cat_candidates:
        try:
            result = generate_master_chart(
                df, num_cols, cat_cols, 'categorical', 'bar', col_x=col
            )
            if result and result.get('ok') and result.get('chart'):
                png = plotly_fig_to_png_bytes(result['chart'])
                if png:
                    charts[f'bar_{col}'] = png
        except Exception as e:
            print(f"[report_chart_builder] Skip bar {col}: {e}")

    return charts
