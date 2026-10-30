import json
import re

from backend.ai_client import call_ai, AIClientError


def _strip_md(text):
    """Strip markdown bold/italic markers from text."""
    if not isinstance(text, str):
        return text
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    return text.strip()


SYSTEM_PROMPT_TEMPLATE = """
Kamu adalah AI Data Analyst senior untuk aplikasi DS Generator (Kelompok 2 - ITSB).
Tugasmu: berikan interpretasi MENYELURUH dan ANALISIS MENDALAM terhadap dataset berikut.

Gunakan seluruh konteks statistik yang diberikan untuk menghasilkan analisis yang
AKURAT, SPESIFIK (menyebutkan angka riil dari data), dan BERGUNA untuk pengambilan keputusan.

Output dalam format JSON valid (tanpa markdown code fence), dengan struktur:
{{
  "summary": "Ringkasan EKSEKUTIF kondisi dataset (3-5 kalimat). Sebutkan jumlah baris, kolom, dan 2-3 temuan paling penting dengan angka spesifik.",
  "key_findings": [
    "Temuan 1: [variable=X, nilai=Y, makna=Z]. Contoh: Rata-rata Hours_Studied adalah 20.3 jam/minggu dengan std 5.2, menunjukkan variasi moderat.",
    "Temuan 2: Sebutkan variabel, nilai spesifik, dan interpretasi.",
    "Temuan 3: ...",
    "Temuan 4: ...",
    "Temuan 5: ..."
  ],
  "recommendations": [
    "Rekomendasi 1: Langkah konkret dan spesifik berdasarkan temuan data. Contoh: Karena korelasi antara Hours_Studied dan Exam_Score sebesar 0.65, disarankan untuk meningkatkan durasi belajar.",
    "Rekomendasi 2: ...",
    "Rekomendasi 3: ..."
  ],
  "conclusion": "Kesimpulan akhir berisi: (1) apakah dataset layak dipakai, (2) risiko/keterbatasan utama, (3) langkah selanjutnya yang harus dilakukan. Gunakan data riil sebagai pendukung."
}}

PANDUAN ANALISIS KETAT:
1. SUMMARY: Gambaran besar — ukuran data, kualitas, 2-3 insight paling penting dengan ANGKA SPESIFIK.
2. KEY FINDINGS: Setiap temuan WAJIB menyebutkan nama variabel, nilai numerik, dan interpretasi. Contoh BAIK: "Kolom Attendance memiliki rata-rata 82.5% dengan std 12.3 — menunjukkan variasi kehadiran yang cukup lebar." Contoh BURUK: "Tingkat kehadiran bervariasi." (tanpa angka).
3. RECOMMENDATIONS: Langkah konkret yang bisa DIAMBIL oleh pengguna data. Terkait langsung dengan temuan. BUKAN saran umum.
4. CONCLUSION: Ya/tidak layak pakai + risiko + langkah selanjutnya. Gunakan data sebagai pendukung argumen.

PENTING: Jangan gunakan markdown formatting (seperti **bold** atau *italic*) di dalam nilai JSON. Tulis teks polos saja.
Gunakan bahasa sesuai parameter 'lang' (id = Bahasa Indonesia, en = English).
JAWAB HANYA DENGAN JSON valid, tanpa teks tambahan apapun.
"""


def build_dataset_context_text(ctx):
    parts = []

    di = ctx.get('dataset_info', {})
    parts.append(f"Dataset: {di.get('name', 'N/A')}")
    parts.append(f"Rows: {di.get('rows', 'N/A')}, Columns: {di.get('cols', 'N/A')}, Size: {di.get('size', 'N/A')}")

    metrics = ctx.get('metrics', {})
    quality = ctx.get('quality_full') or ctx.get('quality_report') or {}
    summary = quality.get('summary', {})
    parts.append(f"Data state: {'cleaned' if ctx.get('is_cleaned') else 'raw'}")
    parts.append(f"Total rows: {metrics.get('total_rows', 'N/A')}, Total cols: {metrics.get('total_columns', 'N/A')}")
    parts.append(f"Numeric cols: {metrics.get('num_count', 'N/A')}, Categorical cols: {metrics.get('cat_count', 'N/A')}")
    parts.append(f"Missing values: {summary.get('missing_cells', metrics.get('missing_cells', 'N/A'))}, Duplicates: {summary.get('duplicate_rows', 'N/A')}")

    num_stats = ctx.get('num_stats', [])
    if num_stats:
        parts.append("=== NUMERICAL STATS (ALL COLUMNS) ===")
        for stat in num_stats:
            col = stat.get('Column', 'N/A')
            parts.append(
                f"  [{col}] mean={stat.get('Mean', 'N/A')}, "
                f"median={stat.get('Median', 'N/A')}, "
                f"min={stat.get('Min', 'N/A')}, "
                f"max={stat.get('Max', 'N/A')}, "
                f"std={stat.get('Std Dev', 'N/A')}, "
                f"skew={stat.get('Skewness', 'N/A')}, "
                f"kurtosis={stat.get('Kurtosis', 'N/A')}, "
                f"missing={stat.get('Missing Count', 0)}, "
                f"normality={stat.get('Normality', 'N/A')}, "
                f"outliers={stat.get('Outliers', 0)}"
            )

    cat_stats = ctx.get('cat_stats', [])
    if cat_stats:
        parts.append("=== CATEGORICAL STATS (ALL COLUMNS) ===")
        for stat in cat_stats:
            col = stat.get('Column', 'N/A')
            parts.append(
                f"  [{col}] unique={stat.get('Unique', 'N/A')}, "
                f"mode={stat.get('Mode', 'N/A')}, "
                f"mode_pct={stat.get('Mode %', 'N/A')}, "
                f"missing={stat.get('Missing Count', 0)}"
            )

    advanced = ctx.get('advanced', {})
    if advanced:
        top_corr = advanced.get('top_corr_pairs', [])
        if top_corr:
            parts.append("=== TOP CORRELATIONS ===")
            for pair in top_corr:
                if len(pair) >= 3:
                    parts.append(f"  {pair[0]} ↔ {pair[1]}: r={pair[2]}")

        cat_assoc = advanced.get('cat_assoc', [])
        if cat_assoc:
            parts.append("=== CATEGORICAL ASSOCIATIONS (Cramér's V) ===")
            for assoc in cat_assoc[:5]:
                parts.append(
                    f"  {assoc.get('col_a')} × {assoc.get('col_b')}: "
                    f"V={assoc.get('cramers_v', 'N/A')} "
                    f"(p={assoc.get('p', 'N/A')}, {assoc.get('strength', '')})"
                )

        num_cat = advanced.get('num_cat', [])
        if num_cat:
            parts.append("=== NUMERICAL vs CATEGORICAL (ANOVA) ===")
            for item in num_cat[:4]:
                sig = "SIGNIFICANT" if item.get('significant') else "not significant"
                parts.append(
                    f"  {item.get('num')} × {item.get('cat')}: "
                    f"F={item.get('f_stat', 'N/A')}, "
                    f"p={item.get('p_anova', 'N/A')} ({sig})"
                )

    if isinstance(summary, dict):
        parts.append(
            f"Data quality: missing_pct={summary.get('missing_pct', 'N/A')}%, "
            f"duplicate_rows={summary.get('duplicate_rows', 'N/A')}"
        )

    insights = ctx.get('insights_en', [])
    if insights:
        parts.append("=== KEY INSIGHTS FROM SYSTEM ===")
        for ins in insights[:5]:
            parts.append(f"  - {ins.get('title', '')}: {ins.get('desc', '')}")

    context_text = '\n'.join(parts)

    if len(context_text) > 8000:
        cut = context_text.rfind('\n', 0, 8000)
        if cut < 2000:
            cut = 8000
        context_text = context_text[:cut] + '\n[context truncated due to length]'

    return context_text


def generate_interpretation(ctx, lang, ai_settings):
    if not ai_settings or not ai_settings.get('api_key'):
        raise AIClientError('AI API key belum dikonfigurasi.')

    provider = ai_settings.get('provider', 'anthropic')
    api_key = ai_settings.get('api_key', '')
    api_keys = ai_settings.get('api_keys', [api_key])
    model = ai_settings.get('model', '')

    context_text = build_dataset_context_text(ctx)
    user_prompt = f"Bahasa: {lang}\n\nDataset context:\n{context_text}"

    system_prompt = SYSTEM_PROMPT_TEMPLATE.strip().replace('{{', '{').replace('}}', '}')

    raw = call_ai(provider, api_key, model, system_prompt, user_prompt, api_keys=api_keys)

    if not raw or not raw.strip():
        raise AIClientError('AI mengembalikan respons kosong. Coba lagi nanti.')

    json_str = raw.strip()
    json_str = re.sub(r'^```(?:json)?\s*', '', json_str)
    json_str = re.sub(r'\s*```$', '', json_str)

    try:
        result = json.loads(json_str)
        expected_keys = {'summary', 'key_findings', 'recommendations', 'conclusion'}
        if not isinstance(result, dict) or not expected_keys.issubset(result):
            raise AIClientError('Format interpretasi AI tidak lengkap. Coba buat ulang.')
        if not all(isinstance(result[key], str) for key in ('summary', 'conclusion')) or not all(
            isinstance(result[key], list) and all(isinstance(item, str) for item in result[key])
            for key in ('key_findings', 'recommendations')
        ):
            raise AIClientError('Format interpretasi AI tidak valid. Coba buat ulang.')
        if isinstance(result.get('key_findings'), list):
            result['key_findings'] = [_strip_md(str(f)) for f in result['key_findings']]
        else:
            result['key_findings'] = []
        if isinstance(result.get('recommendations'), list):
            result['recommendations'] = [_strip_md(str(r)) for r in result['recommendations']]
        else:
            result['recommendations'] = []
        result['summary'] = _strip_md(str(result.get('summary', '')))
        result['conclusion'] = _strip_md(str(result.get('conclusion', '')))
        return result
    except json.JSONDecodeError:
        raise AIClientError('Respons interpretasi AI bukan JSON yang valid. Coba buat ulang.') from None
