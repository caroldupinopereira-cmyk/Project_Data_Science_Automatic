import plotly.graph_objects as go
import plotly.io as pio
from io import BytesIO


def plotly_fig_to_png_bytes(fig_dict, width=720, height=420, scale=2):
    """
    Konversi dict hasil Plotly (data + layout, format yang sama dengan yang
    dikirim ke frontend lewat _json()/_safe_json() di viz_engine.py / time_series.py)
    menjadi PNG bytes, untuk dipakai sebagai Image() di ReportLab.

    Parameters:
    fig_dict : dict dengan key 'data' dan 'layout' (hasil fig.to_dict() / json.loads dari _json())
    width, height : ukuran render dalam pixel (sebelum scale)
    scale : multiplier resolusi (2x untuk PDF tetap tajam saat di-print)

    Returns: BytesIO siap dipakai reportlab.platypus.Image(BytesIO(...))
    """
    try:
        fig = go.Figure(data=fig_dict.get('data', []), layout=fig_dict.get('layout', {}))

        # Override beberapa hal supaya cocok untuk PDF (background putih,
        # font lebih besar sedikit karena akan diperkecil saat print)
        fig.update_layout(
            paper_bgcolor='white',
            plot_bgcolor='white',
            font=dict(color='#1a1a1a', size=12),
            margin=dict(l=50, r=30, t=50, b=50),
        )
        # Pastikan grid/axis terlihat di atas background putih (chart asli didesain utk dark theme)
        fig.update_xaxes(gridcolor='#e2e8f0', linecolor='#cbd5e0', zerolinecolor='#cbd5e0')
        fig.update_yaxes(gridcolor='#e2e8f0', linecolor='#cbd5e0', zerolinecolor='#cbd5e0')

        png_bytes = pio.to_image(fig, format='png', width=width, height=height, scale=scale)
        return BytesIO(png_bytes)
    except Exception as e:
        print(f"[chart_to_image] Failed to render chart: {e}")
        return None
