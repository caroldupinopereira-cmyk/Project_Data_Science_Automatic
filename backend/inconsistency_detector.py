"""
backend/inconsistency_detector.py
────────────────────────────────────────────────────────────────────────────
Advanced Inconsistency Detection & Smart Fix untuk Dataset.

Mendeteksi berbagai jenis inkonsistensi:
  1. Casing issues     — mixed case (Jakarta, jakarta, JAKARTA)
  2. Whitespace issues — leading/trailing/multiple spaces
  3. Format numbers    — "1,000" vs "1.000" vs "Rp 50.000"
  4. Date formats      — "2024-01-15" vs "15/01/2024" vs "Jan 15, 2024"
  5. Boolean-like      — "yes"/"no", "true"/"false", "1"/"0", "Y"/"N"
  6. Near-duplicates   — "Jakarta" vs "Jkt" (fuzzy matching)
  7. Special chars     — trailing/leading punctuation, unicode issues
  8. Mixed types       — numeric stored as string
  9. Category grouping — "Laki-laki" vs "Laki" vs "Pria"
────────────────────────────────────────────────────────────────────────────
"""

import re
import unicodedata
import pandas as pd
import numpy as np
from collections import Counter


# ─── Constants ────────────────────────────────────────────────────────────────

# Common boolean mappings
BOOLEAN_MAP = {
    # English
    'yes': True, 'no': False,
    'true': True, 'false': False,
    'y': True, 'n': False,
    'on': True, 'off': False,
    '1': True, '0': False,
    # Indonesian
    'ya': True, 'tidak': False,
    'aktif': True, 'nonaktif': False,
    'tersedia': True, 'tidak tersedia': False,
    # Shorthand
    't': True, 'f': False,
    'benar': True, 'salah': False,
}

# Common gender/sex mappings
GENDER_MAP = {
    'laki-laki': 'Laki-laki', 'laki': 'Laki-laki', 'pria': 'Laki-laki',
    'laki laki': 'Laki-laki', 'lelaki': 'Laki-laki', 'cowok': 'Laki-laki',
    'm': 'Laki-laki', 'male': 'Laki-laki', 'l': 'Laki-laki',
    'perempuan': 'Perempuan', 'wanita': 'Perempuan', 'cewek': 'Perempuan',
    'f': 'Perempuan', 'female': 'Perempuan', 'p': 'Perempuan',
}

# Common status mappings
STATUS_MAP = {
    'aktif': 'Aktif', 'active': 'Aktif',
    'nonaktif': 'Nonaktif', 'inactive': 'Nonaktif', 'tidak aktif': 'Nonaktif',
    'pending': 'Pending', 'menunggu': 'Pending',
    'selesai': 'Selesai', 'done': 'Selesai', 'completed': 'Selesai',
    'dibatalkan': 'Dibatalkan', 'cancelled': 'Dibatalkan', 'canceled': 'Dibatalkan',
}

# Common abbreviation expansions (Indonesia)
ABBREV_MAP = {
    'jkt': 'Jakarta',
    'jogja': 'Yogyakarta',
    'yg': 'yang',
    'dn': 'dan',
    'utk': 'untuk',
    'dr': 'dari',
    'dlm': 'dalam',
    'tp': 'tapi',
    'klo': 'kalau',
    'gak': 'tidak',
    'ga': 'tidak',
    'gk': 'tidak',
    'bkn': 'bukan',
    'blm': 'belum',
    'sdh': 'sudah',
    'bgt': 'banget',
    'sm': 'sama',
    'sma': 'sama',
    'dgn': 'dengan',
    'dr': 'dari',
    'prd': 'produk',
    'qty': 'jumlah',
    'unit': 'satuan',
}

# Date format patterns
DATE_PATTERNS = [
    (r'^\d{4}-\d{1,2}-\d{1,2}$', 'iso'),           # 2024-01-15
    (r'^\d{1,2}/\d{1,2}/\d{4}$', 'dmy_slash'),     # 15/01/2024
    (r'^\d{1,2}-\d{1,2}-\d{4}$', 'dmy_dash'),      # 15-01-2024
    (r'^\d{1,2}\.\d{1,2}\.\d{4}$', 'dmy_dot'),     # 15.01.2024
    (r'^\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}$', 'mdy_text'),
    (r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}$', 'us_text'),
]


# ─── Detection Functions ──────────────────────────────────────────────────────

def detect_casing_issues(series: pd.Series) -> dict:
    """
    Deteksi inkonsistensi casing pada kolom teks.
    Return: dict dengan info detail
    """
    s = series.dropna().astype(str)
    if s.empty:
        return {'detected': False, 'count': 0, 'examples': []}

    lower_vals = s.str.lower()
    upper_vals = s.str.upper()
    title_vals = s.str.title()

    # Check if ALL values are same when lowercased
    n_unique_lower = lower_vals.nunique()
    n_unique_original = s.nunique()

    # Mixed casing: values differ in original vs lowercased
    mixed_mask = s != lower_vals
    mixed_count = int(mixed_mask.sum())

    # Same value, different casing (e.g., "Jakarta" and "JAKARTA" and "jakarta")
    if n_unique_lower < n_unique_original:
        # Find groups of same value with different casing
        groups = s.groupby(lower_vals).apply(lambda x: x.unique().tolist())
        conflicting = groups[groups.apply(len) > 1]
        examples = []
        for _, vals in conflicting.items():
            examples.append(vals[:3])
        return {
            'detected': True,
            'count': mixed_count,
            'type': 'mixed_case_groups',
            'examples': examples[:5],
        }

    return {'detected': mixed_count > 0, 'count': mixed_count, 'examples': []}


def detect_whitespace_issues(series: pd.Series) -> dict:
    """Deteksi whitespace issues: leading, trailing, multiple spaces."""
    s = series.dropna().astype(str)
    if s.empty:
        return {'detected': False, 'count': 0, 'examples': []}

    leading = int((s != s.str.lstrip()).sum())
    trailing = int((s != s.str.rstrip()).sum())
    multiple = int(s.str.contains(r'\s{2,}', regex=True).sum())
    total = leading + trailing + multiple

    examples = []
    if total > 0:
        bad_vals = s[s != s.str.strip()]
        examples = bad_vals.head(5).tolist()

    return {
        'detected': total > 0,
        'count': total,
        'leading': leading,
        'trailing': trailing,
        'multiple_spaces': multiple,
        'examples': examples,
    }


def detect_numeric_as_string(series: pd.Series) -> dict:
    """Deteksi nilai yang seharusnya numerik tapi tersimpan sebagai string."""
    s = series.dropna().astype(str)
    if s.empty or len(s) < 3:
        return {'detected': False, 'count': 0, 'examples': []}

    # Try to parse as numeric
    numeric_count = 0
    examples = []
    patterns = {
        'plain': r'^-?[\d,]+\.?\d*$',
        'currency_rp': r'^Rp[\s.]?[\d.,]+$',
        'currency_usd': r'^\$[\s]?[\d.,]+$',
        'percent': r'^[\d.,]+\s?%$',
        'thousands_dot': r'^\d{1,3}(\.\d{3})+([.,]\d+)?$',
        'thousands_comma': r'^\d{1,3}(,\d{3})+([.]\d+)?$',
    }

    for pattern_name, pattern in patterns.items():
        matches = s.str.match(pattern, case=False)
        n = int(matches.sum())
        if n > 0:
            numeric_count += n
            if len(examples) < 5:
                matched = s[matches].head(5 - len(examples)).tolist()
                examples.extend(matched)

    is_numeric_pct = numeric_count / len(s) * 100

    return {
        'detected': is_numeric_pct > 50 and numeric_count > 3,
        'count': numeric_count,
        'pct': round(is_numeric_pct, 1),
        'examples': examples[:5],
    }


def detect_date_like_strings(series: pd.Series) -> dict:
    """Deteksi nilai yang merupakan tanggal dalam format string."""
    s = series.dropna().astype(str).str.strip()
    if s.empty or len(s) < 3:
        return {'detected': False, 'count': 0, 'examples': []}

    date_count = 0
    detected_formats = set()
    examples = []

    for val in s:
        for pattern, fmt_name in DATE_PATTERNS:
            if re.match(pattern, val, re.IGNORECASE):
                date_count += 1
                detected_formats.add(fmt_name)
                if len(examples) < 5:
                    examples.append(val)
                break

    is_date_pct = date_count / len(s) * 100

    return {
        'detected': is_date_pct > 70 and date_count > 3,
        'count': date_count,
        'pct': round(is_date_pct, 1),
        'formats': list(detected_formats),
        'examples': examples,
    }


def detect_boolean_like(series: pd.Series) -> dict:
    """Deteksi kolom yang berisi boolean-like values."""
    s = series.dropna().astype(str).str.strip().str.lower()
    if s.empty:
        return {'detected': False, 'count': 0, 'examples': []}

    bool_count = 0
    found_values = set()
    for val in s:
        if val in BOOLEAN_MAP:
            bool_count += 1
            found_values.add(val)

    is_bool_pct = bool_count / len(s) * 100

    return {
        'detected': is_bool_pct > 80 and bool_count > 3,
        'count': bool_count,
        'pct': round(is_bool_pct, 1),
        'values_found': list(found_values),
    }


def detect_special_char_issues(series: pd.Series) -> dict:
    """Deteksi special characters yang tidak perlu di awal/akhir."""
    s = series.dropna().astype(str)
    if s.empty:
        return {'detected': False, 'count': 0, 'examples': []}

    # Check for leading/trailing punctuation
    bad_mask = s.str.match(r'^[^\w\s]|[^\w\s]$', regex=True)
    bad_count = int(bad_mask.sum())

    # Check for unicode issues (full-width chars, etc.)
    unicode_count = 0
    for val in s:
        for char in val:
            if unicodedata.category(char).startswith('P'):
                if ord(char) > 0xFF00:  # Full-width characters
                    unicode_count += 1
                    break

    total = bad_count + unicode_count
    examples = []
    if bad_count > 0:
        examples = s[bad_mask].head(5).tolist()

    return {
        'detected': total > 0,
        'count': total,
        'leading_trailing_punct': bad_count,
        'unicode_issues': unicode_count,
        'examples': examples,
    }


def detect_near_duplicates(series: pd.Series, threshold: float = 0.8) -> dict:
    """
    Deteksi nilai yang hampir sama (fuzzy matching).
    Contoh: "Jakarta" vs "Jkt", "Bandung" vs "BDG"
    """
    s = series.dropna().astype(str).str.strip().str.lower()
    if s.empty or s.nunique() < 2:
        return {'detected': False, 'count': 0, 'examples': []}

    unique_vals = s.unique().tolist()
    if len(unique_vals) < 2:
        return {'detected': False, 'count': 0, 'examples': []}

    similar_groups = []
    visited = set()

    for i, v1 in enumerate(unique_vals):
        if v1 in visited:
            continue
        group = [v1]
        for j, v2 in enumerate(unique_vals):
            if i >= j or v2 in visited:
                continue
            similarity = _simple_similarity(v1, v2)
            if similarity >= threshold:
                group.append(v2)
                visited.add(v2)
        if len(group) > 1:
            similar_groups.append(group)
            visited.add(v1)

    return {
        'detected': len(similar_groups) > 0,
        'group_count': len(similar_groups),
        'groups': similar_groups[:5],
    }


def detect_mixed_numeric_types(series: pd.Series) -> dict:
    """
    Deteksi kolom yang memiliki campuran tipe: sebagian numerik, sebagian string.
    """
    if not pd.api.types.is_object_dtype(series.dtype):
        return {'detected': False, 'count': 0, 'examples': []}

    s = series.dropna().astype(str)
    if s.empty:
        return {'detected': False, 'count': 0, 'examples': []}

    numeric_count = 0
    non_numeric_count = 0
    non_numeric_examples = []

    for val in s:
        try:
            float(val.replace(',', '').replace('.', '', 1))
            numeric_count += 1
        except ValueError:
            non_numeric_count += 1
            if len(non_numeric_examples) < 5:
                non_numeric_examples.append(val)

    total = numeric_count + non_numeric_count
    has_mix = numeric_count > 0 and non_numeric_count > 0
    ratio = min(numeric_count, non_numeric_count) / max(total, 1)

    return {
        'detected': has_mix and ratio > 0.05,
        'numeric_count': numeric_count,
        'non_numeric_count': non_numeric_count,
        'examples': non_numeric_examples,
    }


def detect_inconsistent_number_format(series: pd.Series) -> dict:
    """
    Deteksi format angka yang tidak konsisten.
    Contoh: "1,000" vs "1.000" vs "1000"
    """
    s = series.dropna().astype(str).str.strip()
    if s.empty:
        return {'detected': False, 'count': 0, 'examples': []}

    # Patterns for number formats
    has_comma_sep = s.str.match(r'^-?\d{1,3}(,\d{3})+([.]\d+)?$', regex=True).sum()
    has_dot_sep = s.str.match(r'^-?\d{1,3}(\.\d{3})+([,]\d+)?$', regex=True).sum()
    has_plain = s.str.match(r'^-?\d+([.,]\d+)?$', regex=True).sum()

    formats_found = []
    if has_comma_sep > 0: formats_found.append('comma_thousands')
    if has_dot_sep > 0: formats_found.append('dot_thousands')
    if has_plain > 0: formats_found.append('plain')

    detected = len(formats_found) > 1

    return {
        'detected': detected,
        'formats': formats_found,
        'comma_count': int(has_comma_sep),
        'dot_count': int(has_dot_sep),
        'plain_count': int(has_plain),
    }


# ─── Smart Fix Functions ──────────────────────────────────────────────────────

def fix_casing(series: pd.Series, method: str = 'title') -> pd.Series:
    """
    Fix casing issues.
    method: 'lower', 'upper', 'title', 'smart'
    'smart' uses GENDER_MAP, STATUS_MAP, ABBREV_MAP for intelligent mapping.
    """
    s = series.copy()

    if method == 'smart':
        # Apply known mappings first
        s_lower = s.astype(str).str.strip().str.lower()

        # Try gender mapping
        gender_mapped = s_lower.map(GENDER_MAP)
        if gender_mapped.notna().sum() > len(s) * 0.3:
            return gender_mapped

        # Try status mapping
        status_mapped = s_lower.map(STATUS_MAP)
        if status_mapped.notna().sum() > len(s) * 0.3:
            return status_mapped

        # Try abbreviation expansion
        abbrev_mapped = s_lower.map(ABBREV_MAP)
        mask = abbrev_mapped.notna()
        if mask.sum() > 0:
            s[mask] = abbrev_mapped[mask]
            return s

        # Fallback to title case
        return s.apply(lambda x: x.strip().title() if isinstance(x, str) else x)

    elif method == 'lower':
        return s.apply(lambda x: x.strip().lower() if isinstance(x, str) else x)
    elif method == 'upper':
        return s.apply(lambda x: x.strip().upper() if isinstance(x, str) else x)
    elif method == 'title':
        return s.apply(lambda x: x.strip().title() if isinstance(x, str) else x)
    else:
        return s.apply(lambda x: x.strip() if isinstance(x, str) else x)


def fix_whitespace(series: pd.Series) -> pd.Series:
    """Fix all whitespace issues: strip, collapse multiple spaces."""
    s = series.copy()
    # Strip leading/trailing
    s = s.apply(lambda x: x.strip() if isinstance(x, str) else x)
    # Collapse multiple spaces
    s = s.apply(lambda x: re.sub(r'\s+', ' ', x) if isinstance(x, str) else x)
    return s


def fix_special_chars(series: pd.Series) -> pd.Series:
    """Remove leading/trailing punctuation."""
    s = series.copy()
    s = s.apply(lambda x: re.sub(r'^[^\w\s]+|[^\w\s]+$', '', x).strip()
                if isinstance(x, str) else x)
    return s


def fix_numeric_strings(series: pd.Series) -> pd.Series:
    """
    Convert numeric strings to actual numeric.
    Handles: currency (Rp, $), percent, thousands separators.
    """
    from .data_sanitizer import clean_and_parse_numeric
    s = series.copy()
    converted = s.map(clean_and_parse_numeric)

    # If most values converted successfully, use converted
    n_valid = converted.notna().sum()
    n_total = len(s.dropna())
    if n_total > 0 and n_valid / n_total > 0.5:
        return converted
    return series


def fix_boolean(series: pd.Series) -> pd.Series:
    """Convert boolean-like strings to True/False."""
    s = series.copy()
    s_lower = s.astype(str).str.strip().str.lower()
    mapped = s_lower.map(BOOLEAN_MAP)
    # Only apply if most values mapped
    n_mapped = mapped.notna().sum()
    n_total = len(s.dropna())
    if n_total > 0 and n_mapped / n_total > 0.7:
        return mapped
    return series


def fix_near_duplicates(series: pd.Series, groups: list) -> pd.Series:
    """
    Merge near-duplicate values using the first value in each group as canonical.
    """
    s = series.copy()
    for group in groups:
        canonical = group[0]  # Use first as canonical
        for variant in group:
            s = s.replace(variant, canonical)
    return s


def fix_number_format(series: pd.Series, target_format: str = 'plain') -> pd.Series:
    """
    Standardize number format.
    target_format: 'plain' (1000), 'comma' (1,000), 'dot' (1.000)
    """
    from .data_sanitizer import clean_and_parse_numeric
    s = series.copy()
    numeric = s.map(clean_and_parse_numeric)

    if numeric.notna().sum() < len(s.dropna()) * 0.5:
        return series

    if target_format == 'plain':
        return numeric
    elif target_format == 'comma':
        return numeric.apply(lambda x: f"{x:,.2f}" if pd.notna(x) else x)
    elif target_format == 'dot':
        return numeric.apply(lambda x: f"{x:,.2f}".replace(',', '.') if pd.notna(x) else x)
    return numeric


# ─── Analysis Engine ──────────────────────────────────────────────────────────

def analyze_column_inconsistencies(series: pd.Series, col_name: str = "") -> dict:
    """
    Analisis lengkap inkonsistensi pada satu kolom.
    Return dict dengan semua jenis inkonsistensi yang terdeteksi.
    """
    if not pd.api.types.is_object_dtype(series.dtype):
        return {
            'column': col_name,
            'dtype': str(series.dtype),
            'is_text': False,
            'issues': {},
            'total_issues': 0,
        }

    issues = {}

    # 1. Casing
    casing = detect_casing_issues(series)
    if casing['detected']:
        issues['casing'] = casing

    # 2. Whitespace
    ws = detect_whitespace_issues(series)
    if ws['detected']:
        issues['whitespace'] = ws

    # 3. Numeric as string
    num_str = detect_numeric_as_string(series)
    if num_str['detected']:
        issues['numeric_as_string'] = num_str

    # 4. Date-like
    date_like = detect_date_like_strings(series)
    if date_like['detected']:
        issues['date_like'] = date_like

    # 5. Boolean-like
    bool_like = detect_boolean_like(series)
    if bool_like['detected']:
        issues['boolean_like'] = bool_like

    # 6. Special chars
    special = detect_special_char_issues(series)
    if special['detected']:
        issues['special_chars'] = special

    # 7. Near duplicates
    near_dup = detect_near_duplicates(series)
    if near_dup['detected']:
        issues['near_duplicates'] = near_dup

    # 8. Mixed types
    mixed = detect_mixed_numeric_types(series)
    if mixed['detected']:
        issues['mixed_types'] = mixed

    # 9. Number format
    num_fmt = detect_inconsistent_number_format(series)
    if num_fmt['detected']:
        issues['number_format'] = num_fmt

    total = sum(i.get('count', 0) for i in issues.values()
                if isinstance(i, dict) and 'count' in i)

    return {
        'column': col_name,
        'dtype': str(series.dtype),
        'is_text': True,
        'issues': issues,
        'total_issues': total,
        'issue_types': list(issues.keys()),
    }


def analyze_dataset_inconsistencies(df: pd.DataFrame) -> dict:
    """
    Analisis inkonsistensi seluruh dataset.
    Return dict dengan ringkasan global + detail per kolom.
    """
    text_cols = df.select_dtypes(include=['object', 'string']).columns.tolist()
    col_results = {}

    total_issues = 0
    issue_type_counts = Counter()

    for col in text_cols:
        result = analyze_column_inconsistencies(df[col], col)
        col_results[col] = result
        total_issues += result['total_issues']
        for itype in result.get('issue_types', []):
            issue_type_counts[itype] += 1

    return {
        'total_text_columns': len(text_cols),
        'columns_with_issues': sum(1 for r in col_results.values() if r['total_issues'] > 0),
        'total_issues': total_issues,
        'issue_type_summary': dict(issue_type_counts),
        'columns': col_results,
    }


# ─── Helper ───────────────────────────────────────────────────────────────────

def _simple_similarity(a: str, b: str) -> float:
    """
    Simple character-based similarity (Jaccard on character bigrams).
    Good enough for detecting abbreviations and minor typos.
    """
    if not a or not b:
        return 0.0

    a_lower = a.lower().strip()
    b_lower = b.lower().strip()

    if a_lower == b_lower:
        return 1.0

    # Check if one is abbreviation of the other
    if a_lower.startswith(b_lower) or b_lower.startswith(a_lower):
        shorter = min(len(a_lower), len(b_lower))
        longer = max(len(a_lower), len(b_lower))
        if shorter / longer > 0.5:
            return 0.85

    # Bigram similarity
    def bigrams(s):
        return set(s[i:i+2] for i in range(len(s)-1))

    bg_a = bigrams(a_lower)
    bg_b = bigrams(b_lower)

    if not bg_a or not bg_b:
        return 0.0

    intersection = bg_a & bg_b
    union = bg_a | bg_b
    return len(intersection) / len(union)
