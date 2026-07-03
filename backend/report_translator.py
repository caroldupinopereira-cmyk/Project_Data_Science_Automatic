# -*- coding: utf-8 -*-
"""
Helper module for report translation (Indonesian <-> English)
"""

TRANSLATIONS = {
    'en': {
        # Section titles
        'Kata Pengantar': 'Preface',
        'Daftar Isi': 'Table of Contents',
        'Pendahuluan & Latar Belakang': 'Introduction & Background',
        'Latar Belakang': 'Background',
        'Tujuan Analisis': 'Analysis Objectives',
        'Deskripsi & Ringkasan Dataset': 'Dataset Description & Summary',
        'Deskripsi Dataset': 'Dataset Description',
        'Ringkasan Eksekutif': 'Executive Summary',
        'Variabel Numerik': 'Numerical Variables',
        'Variabel Kategorikal': 'Categorical Variables',
        'Kualitas Data': 'Data Quality',
        'Statistik Deskriptif - Numerik': 'Descriptive Statistics - Numerical',
        'Statistik Deskriptif - Kategorikal': 'Descriptive Statistics - Categorical',
        'Statistik Deskriptif - Variabel Numerik': 'Descriptive Statistics - Numerical Variables',
        'Statistik Deskriptif - Variabel Kategorikal': 'Descriptive Statistics - Categorical Variables',
        'Visualisasi Data': 'Data Visualization',
        'Visualisasi Distribusi': 'Distribution Visualization',
        'Visualisasi Data & Interpretasi': 'Data Visualization & Interpretation',
        'Analisis Time Series': 'Time Series Analysis',
        'Analisis Deret Waktu': 'Time Series Analysis',
        'Analisis Deret Waktu (Time Series)': 'Time Series Analysis',
        'Proses Data Cleaning': 'Data Cleansing Process',
        'Proses Pembersihan Data': 'Data Cleansing Process',
        'Temuan Kunci & Insight': 'Key Findings & Insights',
        'Temuan Kunci & Insight Otomatis': 'Key Findings & Automated Insights',
        'Wawasan Otomatis': 'Automated Insights',
        'Rekomendasi Strategis': 'Strategic Recommendations',
        'Rekomendasi': 'Recommendations',
        'Penutup': 'Conclusion',
        'Penutup & Tim': 'Conclusion & Team',
        
        # Cover page labels
        'Laporan Analisis Data Deskriptif': 'Descriptive Data Analysis Report',
        'Laporan Analisis Data Kustom': 'Custom Data Analysis Report',
        'Analis': 'Analyst',
        'Tanggal': 'Date',
        'Total Data': 'Total Data',
        'RAW DATA — Perlu Pembersihan': 'RAW DATA — Needs Cleansing',
        'CLEAN DATA — Siap Dianalisis': 'CLEAN DATA — Ready for Analysis',
        'Program Studi Sains Data': 'Data Science Study Program',
        'Program Studi Sains Data ITSB': 'ITSB Data Science Study Program',
        'Sains Data ITSB': 'ITSB Data Science',
        'Kelompok 2': 'Group 2',
        
        # KPI / Metrics table
        'Total Baris': 'Total Rows',
        'Total Kolom': 'Total Columns',
        'Missing Values': 'Missing Values',
        'Duplikat': 'Duplicates',
        'IQR Outliers': 'IQR Outliers',
        
        # Table headers
        'Nomor': 'No.',
        'Nama Variabel': 'Variable Name',
        'Tipe Data': 'Data Type',
        'Nilai Kosong': 'Missing Values',
        'Persentase': 'Percentage',
        'Nilai Unik': 'Unique Values',
        'Keterangan': 'Notes',
        'Variabel': 'Variable',
        'Rata-rata': 'Mean',
        'Median': 'Median',
        'Min': 'Min',
        'Max': 'Max',
        'Standar Deviasi': 'Std Dev',
        'Jumlah Outlier': 'Outliers',
        'Modus (Dominan)': 'Mode (Dominant)',
        'Frekuensi Modus': 'Mode Frequency',
        'Persentase Modus': 'Mode Percentage',
        'Sel Kosong': 'Empty Cells',
        
        # Comparison table
        'Metrik Evaluasi': 'Evaluation Metrics',
        'Sebelum': 'Before',
        'Sesudah': 'After',
        'Dampak Reduksi': 'Reduction Impact',
        'Jumlah Baris (Observasi)': 'Row Count (Observations)',
        'Jumlah Kolom (Variabel)': 'Column Count (Variables)',
        'Sel Kosong (Missing)': 'Empty Cells (Missing)',
        'baris': 'rows',
        'kolom': 'columns',
        'sel': 'cells',
        
        # Cleansing log / history
        'Pembersihan Missing Values': 'Missing Values Cleansing',
        'Mengisi nilai kosong': 'Imputing missing values',
        'Menghapus Duplikat': 'Removing Duplicates',
        'Menghapus baris duplikat': 'Removing duplicate rows',
        'Penanganan Outlier': 'Handling Outliers',
        'Mengatasi outlier': 'Addressing outliers',
        'Pembersihan Inkonsistensi': 'Inconsistency Cleansing',
        'Memperbaiki teks tidak konsisten': 'Fixing inconsistent texts',
        'Drop Kolom Tidak Relevan': 'Drop Irrelevant Columns',
        'Membuang kolom konstan/ID': 'Dropping constant/ID columns',
        
        # Canvas / Header / Footer
        'Institut Teknologi Sains Bandung': 'Bandung Institute of Technology and Science (ITSB)',
        'Digenerate': 'Generated',
        'RAHASIA — Hanya untuk keperluan akademik': 'CONFIDENTIAL — For academic purposes only',
        'Halaman': 'Page',
        'dari': 'of',
    }
}

def tr_report(text, lang='id'):
    """Translate static text inside reports."""
    if not text:
        return ''
    cleaned_text = str(text).strip()
    if lang == 'en':
        return TRANSLATIONS['en'].get(cleaned_text, cleaned_text)
    return cleaned_text

def get_dynamic_preface(lang, filename, total_rows, total_cols, missing_c, dup_rows, outliers_c, needs_cl):
    """Generate preface paragraphs in EN or ID."""
    if lang == 'en':
        p1 = (
            "We express our gratitude to God Almighty for all His blessings and grace so that "
            "this data analysis report can be completed successfully. This report is the result of "
            "Exploratory Data Analysis (EDA) performed automatically using the <b>DS Generator</b> platform "
            "— a web-based descriptive data analysis system developed by <b>Group 2</b>, "
            "Data Science Study Program, Bandung Institute of Technology and Science (ITSB)."
        )
        
        needs_cl_str = (
            f"requires further data cleansing because it has <b>{missing_c:,} empty cells</b> and "
            f"<b>{dup_rows} duplicate rows</b>" if needs_cl else 
            "is in good condition and ready for further analysis"
        )
        outlier_str = f" A total of <b>{outliers_c} potential outliers</b> were also detected via the IQR method." if outliers_c > 0 else ""
        p2 = (
            f"This report presents a comprehensive analysis of the <b>{filename}</b> dataset "
            f"consisting of <b>{total_rows:,} observation rows</b> and <b>{total_cols} variables</b>. "
            f"Based on the automated data quality scan, this dataset {needs_cl_str}.{outlier_str}"
        )
        
        p3 = (
            "This report is structured to provide a comprehensive and structured overview of the "
            "data characteristics, variable distribution, data quality, and key findings that can be "
            "used as a basis for data-driven decision making. The analysis presented includes "
            "descriptive statistics, distribution visualization, anomaly detection, "
            "and strategic recommendations formulated automatically based on identified data patterns."
        )
        
        p4 = (
            "We realize that this report still has limitations, especially in terms of the depth of "
            "analysis which depends on the completeness and quality of the provided data. Therefore, "
            "constructive suggestions and inputs are highly expected for future improvements. "
            "We hope this report can provide significant added value for readers and parties "
            "who need information from this dataset."
        )
    else:
        p1 = (
            "Puji syukur kami panjatkan ke hadirat Tuhan Yang Maha Esa atas segala berkat dan "
            "rahmat-Nya sehingga laporan analisis data ini dapat diselesaikan dengan baik. "
            "Laporan ini merupakan hasil analisis eksplorasi data (<i>Exploratory Data Analysis</i>) "
            "yang dilakukan secara otomatis menggunakan platform <b>DS Generator</b> — sistem "
            "analisis data deskriptif berbasis web yang dikembangkan oleh <b>Kelompok 2</b>, "
            "Program Studi Sains Data, Institut Teknologi Sains Bandung (ITSB)."
        )
        
        needs_cl_str = (
            f"memerlukan proses pembersihan data lebih lanjut karena ditemukan <b>{missing_c:,} sel kosong</b> dan "
            f"<b>{dup_rows} baris duplikat</b>" if needs_cl else 
            "dalam kondisi baik dan siap untuk dianalisis lebih lanjut"
        )
        outlier_str = f" Sebanyak <b>{outliers_c} potensi outlier</b> juga terdeteksi melalui metode IQR." if outliers_c > 0 else ""
        p2 = (
            f"Laporan ini menyajikan analisis menyeluruh terhadap dataset <b>{filename}</b> "
            f"yang terdiri dari <b>{total_rows:,} baris observasi</b> dan <b>{total_cols} variabel</b>. "
            f"Berdasarkan hasil pemindaian kualitas data yang dilakukan secara otomatis, dataset ini {needs_cl_str}.{outlier_str}"
        )
        
        p3 = (
            "Laporan ini disusun dengan tujuan untuk memberikan gambaran komprehensif dan terstruktur "
            "mengenai karakteristik data, distribusi variabel, kualitas data, serta temuan-temuan penting "
            "yang dapat dijadikan dasar pengambilan keputusan berbasis data (<i>data-driven decision making</i>). "
            "Analisis yang disajikan meliputi statistik deskriptif, visualisasi distribusi, deteksi anomali, "
            "serta rekomendasi strategis yang dirumuskan secara otomatis berdasarkan pola data yang teridentifikasi."
        )
        
        p4 = (
            "Kami menyadari bahwa laporan ini masih memiliki keterbatasan, terutama dalam hal kedalaman "
            "analisis yang bergantung pada kelengkapan dan kualitas data yang diberikan. Oleh karena itu, "
            "saran dan masukan yang konstruktif sangat kami harapkan demi penyempurnaan di masa mendatang. "
            "Semoga laporan ini dapat memberikan nilai tambah yang signifikan bagi pembaca dan pihak-pihak "
            "yang memerlukan informasi dari dataset ini."
        )
    return [p1, p2, p3, p4]

def get_dynamic_introduction(lang, filename, num_cols_len, cat_cols_len):
    """Generate introduction text."""
    if lang == 'en':
        p1 = (
            f"This data analysis report is designed to explore, understand, and document the structure "
            f"of the <b>{filename}</b> dataset. Through an automated exploratory data analysis (EDA) process, "
            f"this report highlights major statistical properties across the dataset's variables, "
            f"which consist of <b>{num_cols_len} numerical variables</b> and <b>{cat_cols_len} categorical variables</b>."
        )
        p2 = (
            "The background of this analysis lies in the importance of understanding data quality "
            "and characteristics before building predictive models or formulating business policies. "
            "Clean and well-understood data is a critical asset in ensuring the validity and "
            "reliability of any insights or decisions generated."
        )
    else:
        p1 = (
            f"Laporan analisis data ini bertujuan untuk mengeksplorasi, memahami, dan mendokumentasikan "
            f"struktur dari dataset <b>{filename}</b>. Melalui proses Exploratory Data Analysis (EDA) otomatis, "
            f"laporan ini menyoroti sifat statistik utama dari seluruh variabel yang ada di dalam dataset, "
            f"yang terdiri dari <b>{num_cols_len} variabel numerik</b> dan <b>{cat_cols_len} variabel kategorikal</b>."
        )
        p2 = (
            "Latar belakang dilakukannya analisis ini adalah pentingnya memahami kualitas dan karakteristik "
            "data sebelum membangun model prediktif atau merumuskan kebijakan bisnis. Data yang bersih "
            "dan dipahami dengan baik merupakan aset penting dalam memastikan validitas dan reliabilitas "
            "setiap keputusan yang dihasilkan."
        )
    return [p1, p2]

def get_dynamic_dataset_summary(lang, filename, total_rows, total_cols, missing_c, dup_rows, outliers_c):
    """Generate dataset summary description text."""
    if lang == 'en':
        miss_pct = round(missing_c / (total_rows * total_cols) * 100, 2) if total_rows and total_cols else 0
        missing_text = (
            f"There are <b>{missing_c:,} empty cells</b> ({miss_pct}% of total cells) "
            "scattered across various columns. " if missing_c > 0 else "No empty cells were found in this dataset. "
        )
        duplicate_text = (
            f"A total of <b>{dup_rows} duplicate rows</b> were identified and should be removed to maintain analysis integrity. "
            if dup_rows > 0 else "No duplicate rows were detected. "
        )
        outlier_text = (
            f"Anomaly detection using the IQR method found <b>{outliers_c} potential outliers (extreme values)</b> "
            "which should be verified further." if outliers_c > 0 else "No outliers were detected."
        )
        return (
            f"The dataset <b>{filename}</b> consists of <b>{total_rows:,} observations</b> with "
            f"<b>{total_cols} variables</b>. {missing_text}{duplicate_text}{outlier_text}"
        )
    else:
        miss_pct = round(missing_c / (total_rows * total_cols) * 100, 2) if total_rows and total_cols else 0
        missing_text = (
            f"Terdapat <b>{missing_c:,} sel kosong</b> ({miss_pct}% dari total data) "
            "yang tersebar di berbagai kolom. " if missing_c > 0 else "Tidak ditemukan sel kosong pada dataset ini. "
        )
        duplicate_text = (
            f"Sebanyak <b>{dup_rows} baris duplikat</b> teridentifikasi dan perlu dihapus untuk menjaga integritas analisis. "
            if dup_rows > 0 else "Tidak ditemukan baris duplikat. "
        )
        outlier_text = (
            f"Deteksi outlier menggunakan metode IQR menemukan <b>{outliers_c} potensi nilai ekstrem</b> "
            "yang perlu diverifikasi lebih lanjut." if outliers_c > 0 else "Tidak ada outlier yang terdeteksi."
        )
        return (
            f"Dataset <b>{filename}</b> terdiri dari <b>{total_rows:,} observasi</b> dengan "
            f"<b>{total_cols} variabel</b>. {missing_text}{duplicate_text}{outlier_text}"
        )

def tr_caption(text, lang='id'):
    """Translate table and figure captions."""
    if not text:
        return ''
    if lang == 'en':
        text = text.replace('Tabel ', 'Table ')
        text = text.replace('Gambar ', 'Figure ')
        captions = {
            'Table 2. Ringkasan kualitas data per kolom': 'Table 2. Summary of data quality per column',
            'Table 3. Ringkasan statistik deskriptif untuk variabel numerik': 'Table 3. Summary of descriptive statistics for numerical variables',
            'Table 3. Statistik deskriptif variabel numerik': 'Table 3. Descriptive statistics of numerical variables',
            'Table 4. Analisis sebaran frekuensi dan dominasi kategori modus variabel non-numerik.': 'Table 4. Frequency distribution and dominance analysis of non-numerical variable modes.',
            'Table 4. Statistik deskriptif variabel kategorikal': 'Table 4. Descriptive statistics of categorical variables',
            'Table 5. Perbandingan metrik kebersihan data sebelum dan sesudah proses pembersihan.': 'Table 5. Comparison of data cleanliness metrics before and after the cleansing process.',
            'Table 5A. Ringkasan metadata time series': 'Table 5A. Summary of time series metadata',
            'Figure 1. Distribusi persentase sel terisi (filled) vs kosong (missing values) pada dataset.': 'Figure 1. Percentage distribution of filled vs empty (missing values) cells in the dataset.',
            'Figure 2. Jumlah nilai kosong (missing values) tertinggi berdasarkan masing-masing kolom variabel.': 'Figure 2. Highest number of missing values based on each variable column.',
            'Figure 3. Matriks koefisien korelasi Pearson antar variabel numerik terpilih.': 'Figure 3. Pearson correlation coefficient matrix between selected numerical variables.',
            'Figure 4. Dampak eliminasi baris sebelum vs sesudah dilakukan proses pembersihan data.': 'Figure 4. Impact of row elimination before vs after data cleansing process.',
        }
        return captions.get(text, text)
    return text

def translate_ts_insights(insights, lang='id', num_col=''):
    """Translate time series insights to English."""
    if lang != 'en' or not insights:
        return insights
    translated = []
    for ins in insights:
        title = ins.get('title', '')
        desc = ins.get('desc', '')
        
        # Translate title
        if 'Time Series Too Short' in title:
            title = 'Time Series Too Short'
        elif 'Meningkat' in title:
            title = 'Trend: Upward ↑'
        elif 'Menurun' in title:
            title = 'Trend: Downward ↓'
        elif 'Tinggi' in title:
            title = 'Volatility: High (CV>30%)'
        elif 'Sedang' in title:
            title = 'Volatility: Moderate (CV 10-30%)'
        elif 'Rendah' in title:
            title = 'Volatility: Low (CV<10%)'
        elif 'Peak & Trough' in title:
            title = f'Peak & Trough — {num_col}'
        elif 'Pola Musiman' in title:
            title = 'Seasonality Pattern Detected'
        elif 'Tidak Ada Pola Musiman' in title:
            title = 'No Clear Seasonality Pattern'
            
        # Translate desc by replacing key phrases
        desc = desc.replace('Variabel', 'Variable')
        desc = desc.replace('menunjukkan tren', 'shows an')
        desc = desc.replace('meningkat', 'upward')
        desc = desc.replace('menurun', 'downward')
        desc = desc.replace('dengan slope', 'trend with slope')
        desc = desc.replace('per periode', 'per period')
        desc = desc.replace('tren signifikan', 'significant trend')
        desc = desc.replace('belum signifikan', 'not significant')
        desc = desc.replace('signifikan secara statistik', 'statistically significant')
        desc = desc.replace('Koefisien variasi (CV)', 'Coefficient of variation (CV)')
        desc = desc.replace('Nilai ini menunjukkan tingkat fluktuasi yang', 'This value indicates a')
        desc = desc.replace('tinggi', 'high')
        desc = desc.replace('sedang', 'moderate')
        desc = desc.replace('rendah', 'low')
        desc = desc.replace('fluktuasi', 'fluctuation')
        desc = desc.replace('sepanjang periode waktu', 'over the time period')
        desc = desc.replace('Nilai tertinggi', 'Highest value')
        desc = desc.replace('Nilai terendah', 'Lowest value')
        desc = desc.replace('pada', 'on')
        desc = desc.replace('Autocorrelation tinggi ditemukan pada', 'High autocorrelation found at')
        desc = desc.replace('Ini mengindikasikan adanya pola berulang pada', 'This indicates a repeating pattern on')
        desc = desc.replace('Tidak ditemukan autocorrelation signifikan pada lag standar', 'No significant autocorrelation found at standard lags')
        desc = desc.replace('tampak tidak memiliki pola musiman yang kuat', 'does not seem to have a strong seasonal pattern')
        
        translated.append({
            'type': ins.get('type', ''),
            'icon': ins.get('icon', ''),
            'title': title,
            'desc': desc
        })
    return translated

