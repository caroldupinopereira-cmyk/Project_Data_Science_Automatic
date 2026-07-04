"""
backend/cleaning_engine.py
─────────────────────────────────────────────────────────────────────────────
Cleaning Engine — modular, stateful, dengan history/undo stack.

Arsitektur:
  - CleaningSession  : menyimpan df_raw, history stack (list of snapshots)
  - apply_step()     : terapkan 1 langkah cleaning, push ke stack
  - undo()           : pop stack → kembali ke state sebelumnya
  - preview_step()   : hitung dampak tanpa apply (untuk preview modal)
  - get_quality_report() : analisis kualitas lengkap (dipakai Overview + Cleaning tab)

Operations yang didukung:
  handle_missing   : mean | median | mode | drop_rows | fill_value
  remove_outliers  : iqr | zscore
  normalize        : minmax | standard
  drop_duplicates  : (no params)
  strip_whitespace : (no params)
  drop_high_missing: threshold (float 0-1)
  drop_col         : column name
─────────────────────────────────────────────────────────────────────────────
"""

import os
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
import copy
import json


# ─── Snapshot model ──────────────────────────────────────────────────────────

class _Snapshot:
    """Satu titik dalam history stack."""
    def __init__(self, df, label, op_type, op_params, summary):
        self.df        = df.copy()           # state DataFrame saat itu
        self.label     = label               # deskripsi singkat, e.g. "Fill missing age with mean"
        self.op_type   = op_type             # jenis operasi
        self.op_params = op_params           # parameter yang dipakai
        self.summary   = summary             # dict ringkasan perubahan


# ─── Cleaning Session ─────────────────────────────────────────────────────────

class CleaningSession:
    """
    Satu sesi cleaning per file.
    Disimpan di server memory (dict global) per filename.
    """

    MAX_HISTORY = 20   # batas undo stack

    def __init__(self, df_raw: pd.DataFrame, filename: str):
        self.filename   = filename
        self.df_raw     = df_raw.copy()
        self._history   : list[_Snapshot] = []   # history[0] = state paling awal setelah upload
        self.is_cleaned = False
        self.ignored_cols = []

        # Push initial state (raw) ke history sebagai titik awal
        self._history.append(_Snapshot(
            df      = df_raw,
            label   = 'Upload awal (raw data)',
            op_type = 'initial',
            op_params = {},
            summary = self._build_summary(df_raw, df_raw, []),
        ))

    # ── Public: current df ────────────────────────────────────────────────────

    @property
    def df_current(self) -> pd.DataFrame:
        return self._history[-1].df

    @property
    def history_labels(self) -> list[dict]:
        """List ringkasan history untuk ditampilkan di UI."""
        result = []
        for i, snap in enumerate(self._history):
            result.append({
                'index'    : i,
                'label'    : snap.label,
                'op_type'  : snap.op_type,
                'rows'     : len(snap.df),
                'cols'     : len(snap.df.columns),
                'missing'  : int(snap.df.isna().sum().sum()),
                'is_current': i == len(self._history) - 1,
                'is_initial': i == 0,
            })
        return result

    # ── Apply step ────────────────────────────────────────────────────────────

    def apply_step(self, op_type: str, op_params: dict) -> dict:
        """
        Terapkan 1 langkah cleaning ke df_current.
        Return: dict hasil (ok, label, summary, preview_rows)
        """
        df_before = self.df_current.copy()

        try:
            df_after, label, log = _dispatch_op(df_before, op_type, op_params)
        except Exception as e:
            return {'ok': False, 'error': str(e)}

        summary = self._build_summary(df_before, df_after, log)

        # Trim history jika melebihi batas
        if len(self._history) >= self.MAX_HISTORY:
            # Pertahankan initial (index 0) + trim dari index 1
            self._history = [self._history[0]] + self._history[-(self.MAX_HISTORY - 2):]

        snap = _Snapshot(
            df        = df_after,
            label     = label,
            op_type   = op_type,
            op_params = op_params,
            summary   = summary,
        )
        self._history.append(snap)
        self.is_cleaned = True

        return {
            'ok'       : True,
            'label'    : label,
            'summary'  : summary,
            'history'  : self.history_labels,
            'quality'  : get_quality_report(df_after),
            'rows_now' : len(df_after),
            'cols_now' : len(df_after.columns),
        }

    # ── Undo ──────────────────────────────────────────────────────────────────

    def undo(self) -> dict:
        """Kembali ke state sebelumnya."""
        if len(self._history) <= 1:
            return {'ok': False, 'error': 'Tidak ada langkah yang bisa di-undo. Ini sudah data awal.'}

        popped = self._history.pop()
        current = self._history[-1]

        # Jika sudah kembali ke state awal, is_cleaned = False
        if len(self._history) == 1:
            self.is_cleaned = False

        return {
            'ok'         : True,
            'undone_label': popped.label,
            'current_label': current.label,
            'history'    : self.history_labels,
            'quality'    : get_quality_report(current.df),
            'rows_now'   : len(current.df),
            'cols_now'   : len(current.df.columns),
        }

    def undo_to(self, index: int) -> dict:
        """Kembali ke snapshot tertentu berdasarkan index."""
        if index < 0 or index >= len(self._history):
            return {'ok': False, 'error': f'Index {index} tidak valid.'}

        self._history = self._history[:index + 1]
        current = self._history[-1]
        self.is_cleaned = len(self._history) > 1

        return {
            'ok'           : True,
            'current_label': current.label,
            'history'      : self.history_labels,
            'quality'      : get_quality_report(current.df),
            'rows_now'     : len(current.df),
            'cols_now'     : len(current.df.columns),
        }

    def reset(self) -> dict:
        """Reset ke raw data (state awal)."""
        self._history = [self._history[0]]
        self.is_cleaned = False
        return {
            'ok'      : True,
            'history' : self.history_labels,
            'quality' : get_quality_report(self.df_raw),
            'rows_now': len(self.df_raw),
            'cols_now': len(self.df_raw.columns),
        }

    # ── Auto Clean (batch) ──────────────────────────────────────────────────

    def auto_clean(self, options: dict = None) -> dict:
        """
        Jalankan beberapa langkah cleaning sekaligus secara otomatis.

        Parameters
        ----------
        options : dict (opsional)
            strip_whitespace      : bool (default True)
            empty_to_nan          : bool (default True)
            drop_duplicates       : bool (default True)
            drop_high_missing     : float (default 0.5) — threshold 0-1, 0 = off
            fill_missing_numeric  : str ('median'|'mean'|'none', default 'median')
            fill_missing_categorical : str ('mode'|'none', default 'mode')
            remove_outliers       : bool (default False)
            outlier_method        : str ('iqr'|'zscore', default 'iqr')
            outlier_action        : str ('cap'|'remove', default 'cap')
            fix_inconsistencies   : bool (default True)
            inconsistency_method  : str ('strip'|'lower'|'title', default 'strip')

        Returns
        -------
        dict dengan keys: ok, steps_applied, summary, history, quality, rows_now, cols_now
        """
        opts = {
            'strip_whitespace'          : True,
            'empty_to_nan'              : True,
            'drop_duplicates'           : True,
            'drop_high_missing'         : 0.5,
            'fill_missing_numeric'      : 'median',
            'fill_missing_categorical'  : 'mode',
            'remove_outliers'           : False,
            'outlier_method'            : 'iqr',
            'outlier_action'            : 'cap',
            'fix_inconsistencies'       : True,
            'inconsistency_method'      : 'all',
        }
        if options:
            opts.update(options)

        df_before_all = self.df_current.copy()
        steps_applied = []
        all_logs = []

        # Step 1: Strip whitespace
        if opts['strip_whitespace']:
            result = self.apply_step('strip_whitespace', {})
            if result.get('ok'):
                steps_applied.append({'label': result['label'], 'summary': result['summary']})
                all_logs.extend(result['summary'].get('log', []))

        # Step 2: Empty string → NaN
        if opts['empty_to_nan']:
            result = self.apply_step('empty_to_nan', {})
            if result.get('ok'):
                steps_applied.append({'label': result['label'], 'summary': result['summary']})
                all_logs.extend(result['summary'].get('log', []))

        # Step 3: Drop high-missing columns
        threshold = float(opts.get('drop_high_missing') or 0)
        if threshold > 0:
            result = self.apply_step('drop_high_missing', {'threshold': threshold})
            if result.get('ok'):
                steps_applied.append({'label': result['label'], 'summary': result['summary']})
                all_logs.extend(result['summary'].get('log', []))

        # Step 4: Fix inconsistencies
        if opts['fix_inconsistencies']:
            result = self.apply_step('fix_inconsistencies', {'method': opts['inconsistency_method']})
            if result.get('ok'):
                steps_applied.append({'label': result['label'], 'summary': result['summary']})
                all_logs.extend(result['summary'].get('log', []))

        # Step 5: Drop duplicates
        if opts['drop_duplicates']:
            result = self.apply_step('drop_duplicates', {})
            if result.get('ok'):
                steps_applied.append({'label': result['label'], 'summary': result['summary']})
                all_logs.extend(result['summary'].get('log', []))

        # Step 6: Fill missing numeric
        fill_num = opts.get('fill_missing_numeric', 'none')
        if fill_num in ('mean', 'median'):
            result = self.apply_step('handle_missing', {'method': fill_num, 'scope': 'numeric'})
            if result.get('ok'):
                steps_applied.append({'label': result['label'], 'summary': result['summary']})
                all_logs.extend(result['summary'].get('log', []))

        # Step 7: Fill missing categorical
        fill_cat = opts.get('fill_missing_categorical', 'none')
        if fill_cat == 'mode':
            result = self.apply_step('handle_missing', {'method': 'mode', 'scope': 'categorical'})
            if result.get('ok'):
                steps_applied.append({'label': result['label'], 'summary': result['summary']})
                all_logs.extend(result['summary'].get('log', []))

        # Step 8: Remove outliers (opsional)
        if opts.get('remove_outliers'):
            result = self.apply_step('remove_outliers', {
                'method': opts['outlier_method'],
                'action': opts['outlier_action'],
            })
            if result.get('ok'):
                steps_applied.append({'label': result['label'], 'summary': result['summary']})
                all_logs.extend(result['summary'].get('log', []))

        # Build combined summary
        df_after_all = self.df_current
        summary = self._build_summary(df_before_all, df_after_all, all_logs)

        return {
            'ok'           : True,
            'steps_applied': steps_applied,
            'total_steps'  : len(steps_applied),
            'summary'      : summary,
            'history'      : self.history_labels,
            'quality'      : get_quality_report(df_after_all),
            'rows_now'     : len(df_after_all),
            'cols_now'     : len(df_after_all.columns),
        }

    # ── Preview (tanpa apply) ─────────────────────────────────────────────────

    def preview_step(self, op_type: str, op_params: dict) -> dict:
        """
        Hitung dampak operasi TANPA menyimpan ke history.
        Return: dict berisi perubahan yang akan terjadi.
        """
        df_before = self.df_current.copy()
        try:
            df_after, label, log = _dispatch_op(df_before, op_type, op_params)
        except Exception as e:
            return {'ok': False, 'error': str(e)}

        rows_removed  = len(df_before) - len(df_after)
        cols_removed  = len(df_before.columns) - len(df_after.columns)
        miss_before   = int(df_before.isna().sum().sum())
        miss_after    = int(df_after.isna().sum().sum())
        miss_filled   = miss_before - miss_after

        return {
            'ok'          : True,
            'label'       : label,
            'log'         : log,
            'rows_before' : len(df_before),
            'rows_after'  : len(df_after),
            'rows_removed': rows_removed,
            'cols_before' : len(df_before.columns),
            'cols_after'  : len(df_after.columns),
            'cols_removed': cols_removed,
            'miss_before' : miss_before,
            'miss_after'  : miss_after,
            'miss_filled' : miss_filled,
            'preview_html': df_after.head(5).to_html(
                classes='data-table', index=False, border=0,
                max_cols=10,
            ),
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _build_summary(df_before, df_after, log):
        miss_b = int(df_before.isna().sum().sum())
        miss_a = int(df_after.isna().sum().sum())
        return {
            'rows_before'  : len(df_before),
            'rows_after'   : len(df_after),
            'cols_before'  : len(df_before.columns),
            'cols_after'   : len(df_after.columns),
            'missing_before': miss_b,
            'missing_after' : miss_a,
            'rows_removed' : len(df_before) - len(df_after),
            'cols_removed' : len(df_before.columns) - len(df_after.columns),
            'miss_filled'  : max(0, miss_b - miss_a),
            'log'          : log,
        }


# ─── Session registry (in-memory, per process) ───────────────────────────────
# Key: filename, Value: CleaningSession

_sessions: dict[str, CleaningSession] = {}


def get_session(filename: str, df_raw: pd.DataFrame = None) -> CleaningSession:
    """
    Ambil session yang sudah ada, atau buat baru jika df_raw diberikan.
    Jika session tidak ada dan df_raw None → return None.
    """
    if filename in _sessions:
        return _sessions[filename]
    if df_raw is not None:
        sess = CleaningSession(df_raw, filename)
        _sessions[filename] = sess
        return sess
    return None


def reset_session(filename: str, df_raw: pd.DataFrame) -> CleaningSession:
    """Buat ulang session (misalnya setelah upload ulang file)."""
    sess = CleaningSession(df_raw, filename)
    _sessions[filename] = sess
    return sess


def delete_session(filename: str):
    _sessions.pop(filename, None)


# ─── Disk persistence ─────────────────────────────────────────────────────────

import pickle as _pickle

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'sessions')


def save_cleaned_to_disk(session_key: str, cleaned_dir: str):
    """Simpan cleaned df dari session ke cleaned_dir."""
    sess = _sessions.get(session_key)
    if not sess or not sess.is_cleaned:
        return False
    os.makedirs(cleaned_dir, exist_ok=True)
    out_path = os.path.join(cleaned_dir, sess.filename)
    sess.df_current.to_csv(out_path, index=False)
    return True


def persist_session(session_key: str):
    """Simpan session state ke disk (pickle)."""
    try:
        sess = _sessions.get(session_key)
        if not sess:
            return
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        safe_key = session_key.replace('::', '_').replace('/', '_').replace('\\', '_')
        data = {
            'filename'  : sess.filename,
            'df_raw'    : _pickle.dumps(sess.df_raw),
            'df_current': _pickle.dumps(sess.df_current),
            'history'   : [(_pickle.dumps(s.df), s.label, s.op_type, s.op_params) for s in sess._history],
            'is_cleaned': sess.is_cleaned,
        }
        with open(os.path.join(SESSIONS_DIR, f"{safe_key}.pkl"), 'wb') as f:
            _pickle.dump(data, f)
    except Exception:
        pass


def load_session_from_disk(session_key: str):
    """Load session dari disk jika ada. Return CleaningSession atau None."""
    try:
        safe_key = session_key.replace('::', '_').replace('/', '_').replace('\\', '_')
        sf = os.path.join(SESSIONS_DIR, f"{safe_key}.pkl")
        if not os.path.exists(sf):
            return None
        with open(sf, 'rb') as f:
            data = _pickle.load(f)
        df_raw = _pickle.loads(data['df_raw'])
        sess = CleaningSession(df_raw, data['filename'])
        # Replace history with saved state
        loaded_history = []
        for df_bytes, label, op_type, op_params in data['history']:
            df = _pickle.loads(df_bytes)
            loaded_history.append(_Snapshot(
                df=df, label=label, op_type=op_type, op_params=op_params,
                summary=CleaningSession._build_summary(df, df, []),
            ))
        if loaded_history:
            sess._history = loaded_history
        sess.is_cleaned = data.get('is_cleaned', False)
        _sessions[session_key] = sess
        return sess
    except Exception:
        return None


# ─── Operation dispatcher ─────────────────────────────────────────────────────

def _dispatch_op(df: pd.DataFrame, op_type: str, params: dict):
    """
    Dispatch operasi cleaning ke handler yang sesuai.
    Return: (df_result, label_str, log_list)
    """
    handlers = {
        'handle_missing'     : _op_handle_missing,
        'remove_outliers'    : _op_remove_outliers,
        'normalize'          : _op_normalize,
        'drop_duplicates'    : _op_drop_duplicates,
        'strip_whitespace'   : _op_strip_whitespace,
        'drop_high_missing'  : _op_drop_high_missing,
        'drop_col'           : _op_drop_col,
        'empty_to_nan'       : _op_empty_to_nan,
        'fix_inconsistencies': _op_fix_inconsistencies,
        'drop_irrelevant_cols': _op_drop_irrelevant_cols,
        'regex_replace'      : _op_regex_replace,
    }
    fn = handlers.get(op_type)
    if fn is None:
        raise ValueError(f"Operasi tidak dikenal: '{op_type}'")
    return fn(df, params)


# ─── Individual operation handlers ───────────────────────────────────────────

def _op_handle_missing(df: pd.DataFrame, params: dict):
    """
    Handle missing values.
    params:
      method    : 'mean' | 'median' | 'mode' | 'fill_value' | 'drop_rows'
      columns   : list of column names (opsional; default = semua kolom relevan)
      fill_value: value untuk method 'fill_value'
      scope     : 'numeric' | 'categorical' | 'all'
    """
    method     = params.get('method', 'mean')
    columns    = params.get('columns') or []
    fill_value = params.get('fill_value', 0)
    scope      = params.get('scope', 'all')
    df         = df.copy()
    log        = []
    total_filled = 0
    total_dropped = 0

    # Tentukan kolom target
    if columns:
        target_cols = [c for c in columns if c in df.columns]
    elif scope == 'numeric':
        target_cols = df.select_dtypes(include='number').columns.tolist()
    elif scope == 'categorical':
        target_cols = df.select_dtypes(include=['object', 'category', 'string']).columns.tolist()
    else:
        target_cols = df.columns.tolist()

    if method == 'drop_rows':
        rows_before = len(df)
        df = df.dropna(subset=target_cols if target_cols else None)
        dropped = rows_before - len(df)
        if dropped:
            log.append(f'Dropped {dropped} rows with missing values')
            total_dropped = dropped
    else:
        for col in target_cols:
            n = int(df[col].isna().sum())
            if n == 0:
                continue
            if method == 'mean':
                if pd.api.types.is_numeric_dtype(df[col]):
                    val = df[col].mean()
                    df[col] = df[col].fillna(round(float(val), 4))
                    log.append(f'{col}: filled {n} missing → mean ({val:.4f})')
                    total_filled += n
            elif method == 'median':
                if pd.api.types.is_numeric_dtype(df[col]):
                    val = df[col].median()
                    df[col] = df[col].fillna(round(float(val), 4))
                    log.append(f'{col}: filled {n} missing → median ({val:.4f})')
                    total_filled += n
            elif method == 'mode':
                mode_val = df[col].mode()
                if not mode_val.empty:
                    df[col] = df[col].fillna(mode_val.iloc[0])
                    log.append(f'{col}: filled {n} missing → mode ({mode_val.iloc[0]})')
                    total_filled += n
            elif method == 'fill_value':
                df[col] = df[col].fillna(fill_value)
                log.append(f'{col}: filled {n} missing → "{fill_value}"')
                total_filled += n

    method_labels = {
        'mean': 'Mean', 'median': 'Median', 'mode': 'Mode',
        'fill_value': f'Nilai "{fill_value}"', 'drop_rows': 'Drop Rows',
    }
    label = f'Handle Missing: {method_labels.get(method, method)}'
    if total_filled:
        label += f' ({total_filled} sel diisi)'
    elif total_dropped:
        label += f' ({total_dropped} baris dihapus)'

    if not log:
        log.append('Tidak ada missing value ditemukan pada kolom yang dipilih.')

    return df, label, log


def _op_remove_outliers(df: pd.DataFrame, params: dict):
    """
    Remove/cap outliers.
    params:
      method  : 'iqr' | 'zscore'
      action  : 'remove' | 'cap'
      columns : list (opsional; default = semua numerik)
      zscore_threshold: float (default 3.0)
    """
    method    = params.get('method', 'iqr')
    action    = params.get('action', 'remove')
    columns   = params.get('columns') or []
    z_thresh  = float(params.get('zscore_threshold', 3.0))
    df        = df.copy()
    log       = []
    rows_before = len(df)

    num_cols = df.select_dtypes(include='number').columns.tolist()
    target   = [c for c in columns if c in num_cols] if columns else num_cols

    if method == 'iqr':
        mask = pd.Series([True] * len(df), index=df.index)
        for col in target:
            s   = df[col].dropna()
            if len(s) < 4:
                continue
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr    = q3 - q1
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outlier_mask = (df[col] < lo) | (df[col] > hi)
            n_out = int(outlier_mask.sum())
            if n_out == 0:
                continue
            if action == 'cap':
                df[col] = df[col].clip(lower=lo, upper=hi)
                log.append(f'{col}: capped {n_out} outliers IQR [{lo:.2f}, {hi:.2f}]')
            else:
                mask = mask & ~outlier_mask
                log.append(f'{col}: {n_out} outliers IQR ditandai untuk dihapus')
        if action == 'remove':
            df = df[mask]

    elif method == 'zscore':
        mask = pd.Series([True] * len(df), index=df.index)
        for col in target:
            s = df[col].dropna()
            if len(s) < 4:
                continue
            z_scores     = np.abs(scipy_stats.zscore(s))
            outlier_idx  = s.index[z_scores > z_thresh]
            n_out        = len(outlier_idx)
            if n_out == 0:
                continue
            if action == 'cap':
                mean_val = float(s.mean())
                std_val  = float(s.std())
                lo, hi   = mean_val - z_thresh * std_val, mean_val + z_thresh * std_val
                df[col]  = df[col].clip(lower=lo, upper=hi)
                log.append(f'{col}: capped {n_out} outliers Z-score >{z_thresh}σ')
            else:
                mask = mask & ~df.index.isin(outlier_idx)
                log.append(f'{col}: {n_out} outliers Z-score ditandai untuk dihapus')
        if action == 'remove':
            df = df[mask]

    rows_removed = rows_before - len(df)
    method_label = 'IQR' if method == 'iqr' else f'Z-Score (>{z_thresh}σ)'
    action_label = 'Dihapus' if action == 'remove' else 'Di-cap'
    label = f'Remove Outliers: {method_label} — {action_label}'
    if rows_removed:
        label += f' ({rows_removed} baris dihapus)'

    if not log:
        log.append('Tidak ada outlier yang ditemukan pada kolom yang dipilih.')

    return df, label, log


def _op_normalize(df: pd.DataFrame, params: dict):
    """
    Normalisasi data numerik.
    params:
      method  : 'minmax' | 'standard'
      columns : list (opsional; default = semua numerik)
    """
    method   = params.get('method', 'minmax')
    columns  = params.get('columns') or []
    df       = df.copy()
    log      = []

    num_cols = df.select_dtypes(include='number').columns.tolist()
    target   = [c for c in columns if c in num_cols] if columns else num_cols

    for col in target:
        s = df[col].dropna()
        if s.empty:
            continue
        if method == 'minmax':
            mn, mx = float(s.min()), float(s.max())
            if mx - mn == 0:
                log.append(f'{col}: dilewati (range = 0)')
                continue
            df[col] = (df[col] - mn) / (mx - mn)
            log.append(f'{col}: min-max scaled [{mn:.3f}, {mx:.3f}] → [0, 1]')
        elif method == 'standard':
            mean_v, std_v = float(s.mean()), float(s.std())
            if std_v == 0:
                log.append(f'{col}: dilewati (std = 0)')
                continue
            df[col] = (df[col] - mean_v) / std_v
            log.append(f'{col}: standardized μ={mean_v:.3f} σ={std_v:.3f}')

    method_label = 'Min-Max Scaling' if method == 'minmax' else 'Standard Scaling (Z-score)'
    label = f'Normalize: {method_label} ({len(target)} kolom)'

    if not log:
        log.append('Tidak ada kolom yang dinormalisasi.')

    return df, label, log


def _op_drop_duplicates(df: pd.DataFrame, params: dict):
    df         = df.copy()
    n_before   = len(df)
    df         = df.drop_duplicates()
    n_removed  = n_before - len(df)
    log        = [f'Removed {n_removed} duplicate row(s)'] if n_removed else ['Tidak ada baris duplikat.']
    label      = f'Drop Duplicates ({n_removed} baris dihapus)' if n_removed else 'Drop Duplicates (tidak ada duplikat)'
    return df, label, log


def _op_strip_whitespace(df: pd.DataFrame, params: dict):
    df   = df.copy()
    log  = []
    cols = df.select_dtypes(include=['object', 'string']).columns.tolist()
    for col in cols:
        df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
    if cols:
        log.append(f'Stripped whitespace dari {len(cols)} kolom teks.')
    label = f'Strip Whitespace ({len(cols)} kolom)'
    return df, label, log


def _op_drop_high_missing(df: pd.DataFrame, params: dict):
    threshold = float(params.get('threshold', 0.5))
    df        = df.copy()
    to_drop   = [c for c in df.columns if df[c].isna().mean() > threshold]
    log       = []
    if to_drop:
        df = df.drop(columns=to_drop)
        log.append(f'Dropped {len(to_drop)} kolom dengan missing >{threshold*100:.0f}%: {", ".join(to_drop)}')
    else:
        log.append(f'Tidak ada kolom dengan missing >{threshold*100:.0f}%.')
    label = f'Drop High-Missing Columns (>{threshold*100:.0f}%) — {len(to_drop)} kolom'
    return df, label, log


def _op_drop_col(df: pd.DataFrame, params: dict):
    col = params.get('column', '')
    df  = df.copy()
    if col and col in df.columns:
        df  = df.drop(columns=[col])
        log = [f'Dropped column: {col}']
    else:
        log = [f'Kolom "{col}" tidak ditemukan.']
    label = f'Drop Column: {col}'
    return df, label, log


def _op_empty_to_nan(df: pd.DataFrame, params: dict):
    df   = df.copy()
    cols = df.select_dtypes(include=['object', 'string']).columns.tolist()
    for col in cols:
        df[col] = df[col].replace(r'^\s*$', np.nan, regex=True)
    log   = [f'Empty strings → NaN pada {len(cols)} kolom teks.']
    label = 'Empty Strings → NaN'
    return df, label, log


def _op_fix_inconsistencies(df: pd.DataFrame, params: dict):
    """
    Fix text inconsistencies: smart normalization dengan berbagai metode.
    params:
      method: 'strip' | 'lower' | 'upper' | 'title' | 'smart' | 'all'
              'strip'  = Strip whitespace saja
              'lower'  = Strip + Lowercase
              'upper'  = Strip + Uppercase
              'title'  = Strip + Title Case
              'smart'  = Smart fix (pakai mapping gender/status/abbrev)
              'all'    = Semua fix sekaligus (whitespace + casing + special chars)
    """
    from .inconsistency_detector import (
        fix_casing, fix_whitespace, fix_special_chars,
        detect_near_duplicates, fix_near_duplicates,
        analyze_column_inconsistencies,
    )

    method = params.get('method', 'strip')
    df     = df.copy()
    log    = []
    cols   = df.select_dtypes(include=['object', 'string']).columns.tolist()
    total_fixed = 0

    method_labels = {
        'strip' : 'Strip Whitespace',
        'lower' : 'Strip + Lowercase',
        'upper' : 'Strip + Uppercase',
        'title' : 'Strip + Title Case',
        'smart' : 'Smart Normalization',
        'all'   : 'Full Cleanup (All)',
    }

    for col in cols:
        s_orig = df[col].copy()
        fixed_count = 0

        if method == 'strip':
            df[col] = fix_whitespace(df[col])
            fixed_count = int((df[col].astype(str) != s_orig.astype(str)).sum())

        elif method == 'lower':
            df[col] = fix_casing(df[col], 'lower')
            fixed_count = int((df[col].astype(str) != s_orig.astype(str)).sum())

        elif method == 'upper':
            df[col] = fix_casing(df[col], 'upper')
            fixed_count = int((df[col].astype(str) != s_orig.astype(str)).sum())

        elif method == 'title':
            df[col] = fix_casing(df[col], 'title')
            fixed_count = int((df[col].astype(str) != s_orig.astype(str)).sum())

        elif method == 'smart':
            # Smart: detect what type of inconsistency and fix accordingly
            analysis = analyze_column_inconsistencies(df[col], col)
            issue_types = analysis.get('issue_types', [])

            # Apply whitespace fix first
            df[col] = fix_whitespace(df[col])

            # Apply casing fix (smart mode)
            if 'casing' in issue_types or 'near_duplicates' in issue_types:
                df[col] = fix_casing(df[col], 'smart')

            # Apply special char fix
            if 'special_chars' in issue_types:
                df[col] = fix_special_chars(df[col])

            # Fix near duplicates if detected
            if 'near_duplicates' in issue_types:
                nd = analysis['issues']['near_duplicates']
                if nd.get('groups'):
                    df[col] = fix_near_duplicates(df[col], nd['groups'])

            fixed_count = int((df[col].astype(str) != s_orig.astype(str)).sum())

        elif method == 'all':
            # Full cleanup: whitespace → special chars → casing (title)
            df[col] = fix_whitespace(df[col])
            df[col] = fix_special_chars(df[col])
            df[col] = fix_casing(df[col], 'title')
            fixed_count = int((df[col].astype(str) != s_orig.astype(str)).sum())

        if fixed_count:
            log.append(f'{col}: {fixed_count} nilai diperbaiki ({method_labels.get(method, method)})')
            total_fixed += fixed_count

    if not log:
        log.append('Tidak ada inkonsistensi teks yang ditemukan pada kolom yang dipilih.')
    label = f'Fix Inconsistencies ({method_labels.get(method, method)}) — {total_fixed} nilai diperbaiki'
    return df, label, log


def detect_irrelevant_cols(df: pd.DataFrame, threshold: float = 0.95) -> list:
    """
    Return a list of column names that are deemed irrelevant based on uniqueness threshold or zero variance.
    Also detects columns with zero variance (single unique value).
    """
    irrelevant = []
    total_rows = len(df)
    for col in df.columns:
        n_unique = df[col].nunique()
        # 1. Zero variance column (constant values)
        if n_unique <= 1:
            irrelevant.append(col)
            continue
        # 2. High uniqueness ratio (likely ID/UUID/free text)
        unique_ratio = n_unique / max(total_rows, 1)
        if unique_ratio > threshold and n_unique > 50:
            irrelevant.append(col)
    return irrelevant


def _op_drop_irrelevant_cols(df: pd.DataFrame, params: dict):
    """
    Drop kolom yang kemungkinan tidak relevan (ID / free text).
    params:
      columns   : list[str] kolom spesifik yang ingin di-drop (opsional)
      threshold : float 0-1, unique ratio threshold (default 0.95)
    """
    threshold     = float(params.get('threshold', 0.95))
    selected_cols = params.get('columns') or []
    df  = df.copy()
    log = []

    if selected_cols:
        to_drop = [c for c in selected_cols if c in df.columns]
    else:
        to_drop = detect_irrelevant_cols(df, threshold)

    if to_drop:
        # Log specific reasons for each column dropped
        for col in to_drop:
            if col in df.columns:
                n_unique = df[col].nunique()
                if n_unique <= 1:
                    log.append(f"Kolom {col} dihapus karena variansi nol")
                else:
                    log.append(f"Kolom {col} dihapus karena tingkat keunikan tinggi")
        df = df.drop(columns=[c for c in to_drop if c in df.columns])
    else:
        log.append('Tidak ada kolom irrelevant yang terdeteksi untuk dihapus.')
    
    label = f'Drop Irrelevant Columns — {len(to_drop)} kolom dihapus'
    return df, label, log


def _op_regex_replace(df: pd.DataFrame, params: dict):
    """
    Regex find & replace pada kolom teks.
    params:
      pattern     : str — regex pattern untuk dicari
      replacement : str — pengganti (bisa pakai backreference \1, \2)
      columns     : list — kolom target (default: semua kolom teks)
      scope       : str — 'all' | 'select' | 'numeric' | 'categorical'
      case_insensitive : bool (default True)
    """
    import re as re_module
    pattern     = params.get('pattern', '')
    replacement = params.get('replacement', '')
    columns     = params.get('columns') or []
    scope       = params.get('scope', 'all')
    case_ignore = params.get('case_insensitive', True)

    df = df.copy()
    log = []
    total_replaced = 0

    if not pattern:
        return df, 'Regex Replace: Tidak ada pattern', ['Pattern tidak boleh kosong.']

    # Tentukan kolom target
    if columns:
        target_cols = [c for c in columns if c in df.columns]
    elif scope == 'numeric':
        target_cols = df.select_dtypes(include='number').columns.tolist()
    elif scope == 'categorical':
        target_cols = df.select_dtypes(include=['object', 'category', 'string']).columns.tolist()
    else:
        target_cols = df.select_dtypes(include=['object', 'string']).columns.tolist()

    flags = re_module.IGNORECASE if case_ignore else 0

    for col in target_cols:
        s_orig = df[col].copy()
        try:
            df[col] = df[col].apply(
                lambda x: re_module.sub(pattern, replacement, str(x), flags=flags)
                if pd.notna(x) and isinstance(x, str) else x
            )
            changed = int((df[col].astype(str) != s_orig.astype(str)).sum())
            if changed:
                log.append(f'{col}: {changed} nilai direplace dengan regex')
                total_replaced += changed
        except re_module.error as e:
            log.append(f'{col}: Error regex — {str(e)}')

    if not log:
        log.append(f'Tidak ada nilai yang cocok dengan pattern "{pattern}".')
    label = f'Regex Replace — {total_replaced} nilai direplace'
    return df, label, log


# ─── Quality Report ───────────────────────────────────────────────────────────

def get_quality_report(df: pd.DataFrame) -> dict:
    """
    Analisis kualitas dataset lengkap untuk Overview + Cleaning tab.
    Return dict dengan kunci:
      summary    : dict ringkasan global
      columns    : list[dict] per kolom
      warnings   : list[str] peringatan utama
      inconsistency_details : dict detail inkonsistensi per kolom
    """
    from .inconsistency_detector import analyze_column_inconsistencies

    total_rows  = len(df)
    total_cols  = len(df.columns)
    total_cells = df.size
    missing_cells   = int(df.isna().sum().sum())
    duplicate_rows  = int(df.duplicated().sum())
    missing_pct     = round(missing_cells / total_cells * 100, 2) if total_cells else 0

    # ── Advanced Inconsistency Detection ──────────────────────────────────────
    text_cols = df.select_dtypes(include=['object', 'string']).columns.tolist()
    inconsistency_count = 0
    inconsistency_details = {}
    total_inconsistency_values = 0

    for col in text_cols:
        analysis = analyze_column_inconsistencies(df[col], col)
        if analysis['total_issues'] > 0:
            inconsistency_count += 1
            inconsistency_details[col] = analysis
            total_inconsistency_values += analysis['total_issues']

    # ── Outliers (IQR) global count ────────────────────────────────────────────
    total_outliers = 0
    for col in df.select_dtypes(include='number').columns:
        s = df[col].dropna()
        if len(s) < 4:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        total_outliers += int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())

    # Irrelevant columns: unique ratio > 0.95 (kemungkinan ID/free text) OR unique values <= 1 (constant)
    irrelevant_count = 0
    for col in df.columns:
        n_unique     = df[col].nunique()
        unique_ratio = n_unique / max(total_rows, 1)
        if (unique_ratio > 0.95 and n_unique > 50) or (n_unique <= 1):
            irrelevant_count += 1

    # Data types breakdown
    dtypes_summary = {}
    for col in df.columns:
        dtype_str = str(df[col].dtype)
        if 'int' in dtype_str or 'float' in dtype_str:
            key = 'numeric'
        elif 'object' in dtype_str or 'string' in dtype_str:
            key = 'text'
        elif 'datetime' in dtype_str:
            key = 'datetime'
        elif 'bool' in dtype_str:
            key = 'boolean'
        else:
            key = 'other'
        dtypes_summary[key] = dtypes_summary.get(key, 0) + 1

    # Warnings
    warnings = []
    if missing_pct > 5:
        warnings.append(f'{missing_cells} sel missing ({missing_pct}% dari total data)')
    if duplicate_rows > 0:
        warnings.append(f'{duplicate_rows} baris duplikat ditemukan')
    if total_outliers > 0:
        warnings.append(f'{total_outliers} outlier terdeteksi (metode IQR)')
    if inconsistency_count > 0:
        warnings.append(f'{inconsistency_count} kolom memiliki inkonsistensi format teks ({total_inconsistency_values} nilai terdampak)')
    if irrelevant_count > 0:
        warnings.append(f'{irrelevant_count} kolom kemungkinan tidak relevan (ID/free text)')

    needs_cleaning = bool(warnings)

    # Per-column detail
    columns_detail = []
    for col in df.columns:
        series   = df[col]
        missing  = int(series.isna().sum())
        miss_pct = round(missing / total_rows * 100, 2) if total_rows else 0
        unique   = int(series.nunique(dropna=True))

        issues = []
        if miss_pct > 50:
            issues.append('High missing (>50%)')
        elif miss_pct > 0:
            issues.append('Has missing values')
        if unique <= 1 and total_rows > 0:
            issues.append('Constant column')
        if pd.api.types.is_object_dtype(series.dtype):
            stripped = series.dropna().astype(str).str.strip()
            if (stripped == '').any():
                issues.append('Empty strings')
            if (series.dropna().astype(str) != series.dropna().astype(str).str.strip()).any():
                issues.append('Whitespace issues')

        # Check inconsistency details for this column
        if col in inconsistency_details:
            detail = inconsistency_details[col]
            for itype in detail.get('issue_types', []):
                if itype == 'casing':
                    issues.append('Mixed casing')
                elif itype == 'numeric_as_string':
                    issues.append('Numbers stored as text')
                elif itype == 'date_like':
                    issues.append('Date-like strings')
                elif itype == 'boolean_like':
                    issues.append('Boolean-like values')
                elif itype == 'mixed_types':
                    issues.append('Mixed data types')
                elif itype == 'near_duplicates':
                    issues.append('Near-duplicate values')
                elif itype == 'number_format':
                    issues.append('Inconsistent number format')

        # Outliers per numeric col
        col_outliers = 0
        if pd.api.types.is_numeric_dtype(series):
            s = series.dropna()
            if len(s) >= 4:
                q1, q3 = s.quantile(0.25), s.quantile(0.75)
                iqr    = q3 - q1
                col_outliers = int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())
                if col_outliers > 0:
                    issues.append(f'{col_outliers} outliers')

        n_unique    = series.nunique()
        uniq_ratio  = n_unique / max(total_rows, 1)
        if uniq_ratio > 0.95 and n_unique > 50:
            issues.append('Possible ID/free text')

        columns_detail.append({
            'column'     : col,
            'dtype'      : str(series.dtype),
            'missing'    : missing,
            'missing_pct': miss_pct,
            'unique'     : unique,
            'outliers'   : col_outliers,
            'issues'     : ', '.join(issues) if issues else 'OK',
            'status'     : 'warning' if issues else 'ok',
        })

    return {
        'summary': {
            'total_rows'          : total_rows,
            'total_cols'          : total_cols,
            'missing_cells'       : missing_cells,
            'missing_pct'         : missing_pct,
            'duplicate_rows'      : duplicate_rows,
            'total_outliers'      : total_outliers,
            'inconsistency_count' : inconsistency_count,
            'irrelevant_count'    : irrelevant_count,
            'needs_cleaning'      : needs_cleaning,
            'dtypes'              : dtypes_summary,
        },
        'columns'  : columns_detail,
        'warnings' : warnings,
        'inconsistency_details' : inconsistency_details,
    }


def detect_data_status(df) -> str:
    """
    Auto-detect dataset cleanliness status. Returns one of three values:

      'raw'                 — Critical quality issues exist: missing values, duplicate rows,
                              irrelevant columns (ID/constant), or text inconsistencies.
                              Dashboard visualizations are blocked.

      'clean_with_outliers' — No critical issues, but statistical outliers detected (IQR method).
                              Dashboard is shown with an informational orange warning badge.

      'clean'               — Fully clean: no missing, no duplicates, no irrelevant cols,
                              no inconsistencies, no outliers.
    """
    from .inconsistency_detector import analyze_column_inconsistencies

    total_rows = len(df)
    if total_rows == 0:
        return 'clean'

    # ── Critical checks (block dashboard) ────────────────────────────────────
    missing_cells  = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())

    # ── Advanced Text Inconsistency Detection ──────────────────────────────────
    text_cols = df.select_dtypes(include=['object', 'string']).columns.tolist()
    inconsistency_count = 0

    for col in text_cols:
        analysis = analyze_column_inconsistencies(df[col], col)
        if analysis['total_issues'] > 0:
            inconsistency_count += 1

    # Irrelevant columns: zero variance (constant) or near-unique ID columns
    irrelevant_count = 0
    for col in df.columns:
        n_unique     = df[col].nunique()
        unique_ratio = n_unique / max(total_rows, 1)
        if (n_unique <= 1) or (unique_ratio > 0.95 and n_unique > 50):
            irrelevant_count += 1

    has_critical = (
        missing_cells > 0
        or duplicate_rows > 0
        or inconsistency_count > 0
        or irrelevant_count > 0
    )

    if has_critical:
        return 'raw'

    # ── Soft check: outliers only (IQR method) ────────────────────────────────
    total_outliers = 0
    for col in df.select_dtypes(include='number').columns:
        s = df[col].dropna()
        if len(s) < 4:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        total_outliers += int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())

    if total_outliers > 0:
        return 'clean_with_outliers'

    return 'clean'