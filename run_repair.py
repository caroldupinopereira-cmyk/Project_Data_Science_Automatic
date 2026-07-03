# -*- coding: utf-8 -*-
"""
Helper script to repair and restore backend/report_generator.py
using the reconstructed transcript data and hand-crafted implementations of missing gaps.
"""
import os
import re

RECONSTRUCTED_FILE = r"C:\Users\Hype\.gemini\antigravity\brain\18edcb26-cc20-4007-98a8-084ee251dabb\scratch\reconstructed_report_generator.py"
OUTPUT_FILE = r"C:\Users\Hype\Desktop\OneDrive\Documents\Matakulia semester 2\Pemograman Sains Data I\DS_Generator_Week15_Kelompok2 - Copy\backend\report_generator.py"

# Repaired Code blocks

# 1. Matplotlib Plotting Logic for _generate_report_plots (Gap 1801-1959)
plot_logic = """
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
"""

# 2. Document Setup and Styling for generate_custom_pdf_report (Gap 2071-2129)
doc_setup_and_styles = """
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
"""

# 3. Cover page block for generate_custom_pdf_report (Gap 2161-2199)
cover_page_block = """
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
"""

# 4. Content loops and end of generate_custom_pdf_report (Gap 2301-2638)
end_block = """
                            Paragraph(f"{c.get('missing_pct', 0):.1f}%", td_style),
                            Paragraph(str(c.get('unique', '\\u2014')), td_style),
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
                        Paragraph(str(ns.get('Column', '\\u2014')), td_style),
                        Paragraph(str(ns.get('Mean', '\\u2014')), td_style),
                        Paragraph(str(ns.get('Median', '\\u2014')), td_style),
                        Paragraph(str(ns.get('Min', '\\u2014')), td_style),
                        Paragraph(str(ns.get('Max', '\\u2014')), td_style),
                        Paragraph(str(ns.get('Std Dev', '\\u2014')), td_style),
                        Paragraph(str(ns.get('Skewness', '\\u2014')), td_style),
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
                        Paragraph(str(cs.get('Column', '\\u2014')), td_style),
                        Paragraph(str(cs.get('Unique', '\\u2014')), td_style),
                        Paragraph(str(cs.get('Mode', '\\u2014')), td_style),
                        Paragraph(str(cs.get('Mode Freq', '\\u2014')), td_style),
                        Paragraph(str(cs.get('Mode %', '\\u2014')), td_style),
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
"""

# Let's read reconstructed_report_generator.py and do the replacements
print("Reading reconstructed file...")
with open(RECONSTRUCTED_FILE, 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.splitlines()
repaired_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    if "MISSING LINE 1801" in line:
        repaired_lines.append(plot_logic.strip('\n'))
        # Skip until 1959
        while i < len(lines) and "MISSING LINE 1959" not in lines[i]:
            i += 1
    elif "MISSING LINE 2071" in line:
        repaired_lines.append(doc_setup_and_styles.strip('\n'))
        while i < len(lines) and "MISSING LINE 2129" not in lines[i]:
            i += 1
    elif "MISSING LINE 2161" in line:
        repaired_lines.append(cover_page_block.strip('\n'))
        while i < len(lines) and "MISSING LINE 2199" not in lines[i]:
            i += 1
    elif "MISSING LINE 2301" in line:
        repaired_lines.append(end_block.strip('\n'))
        while i < len(lines) and "MISSING LINE 2637" not in lines[i] and "MISSING LINE 2638" not in lines[i]:
            i += 1
    elif "MISSING LINE" in line:
        # Drop stray missing lines
        pass
    else:
        repaired_lines.append(line)
    i += 1

final_code = '\n'.join(repaired_lines)

# Also fix the signature of _generate_report_plots in the repaired file to support lang
final_code = final_code.replace(
    "def _generate_report_plots(df, sess, cleaning_summary, temp_dir):",
    "def _generate_report_plots(df, sess, cleaning_summary, temp_dir, lang='id'):"
)

# Strip line numbers if they were somehow prepended
# Reconstructed file should already have line numbers stripped but let's check
# We saw that reconstructed file does NOT have line numbers prepended in our view_file check!
# But just in case, let's verify if there are any '<line_number>:' prefixes.
# No, our view_file shows that the lines were raw (the "modified to include a line number" was only done by the tool when returning the result).

# Write to output file
print("Writing repaired file...")
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(final_code)

print("Repair completed successfully!")
print(f"File written to {OUTPUT_FILE}")
