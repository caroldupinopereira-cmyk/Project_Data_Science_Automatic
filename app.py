import os
import secrets
import datetime
import functools

from dotenv import load_dotenv
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np

from backend.data_loader import load_data, DataLoadError
from backend.preprocessing import detect_data_types
from backend.descriptive_stats import get_summary_metrics, get_descriptive_stats
from backend.advanced_stats import get_advanced_stats
from backend.dashboard_overview import generate_overview_dashboard
from backend.viz_engine import (
    generate_master_chart, category_available, CATEGORY_CHARTS, CHART_LABELS,
)
from backend.insights_generator import generate_auto_insights
from backend.time_series import detect_datetime_cols, generate_ts_plots, generate_complete_timeseries
from backend.cleaning_engine import (
    get_session, reset_session, delete_session,
    get_quality_report, detect_data_status,
)
from backend.data_sanitizer import sanitize_df_numeric_cols
from backend.ai_settings import get_ai_settings
from backend.interpretation_generator import generate_interpretation, build_dataset_context_text

def _load_secret_key():
    configured = os.environ.get('SECRET_KEY')
    if configured:
        return configured
    path = os.path.join(BASE_DIR, '.secret_key')
    try:
        with open(path, encoding='utf-8') as file:
            key = file.read().strip()
        if key:
            return key
    except FileNotFoundError:
        pass
    key = secrets.token_hex(32)
    try:
        with open(path, 'x', encoding='utf-8') as file:
            file.write(key)
    except FileExistsError:
        with open(path, encoding='utf-8') as file:
            return file.read().strip() or key
    return key


app = Flask(__name__, template_folder='frontend/templates', static_folder='frontend/static')
app.secret_key = _load_secret_key()

# ─── Register Auth Blueprint ──────────────────────────────────────────────
from backend.auth import auth_bp, oauth
app.register_blueprint(auth_bp)
oauth.init_app(app)
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

ALLOWED_EXTENSIONS = {'csv', 'txt', 'xlsx'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ─── Performance Caches ─────────────────────────────────────────────────────
import time as _time

# Cache for _get_dashboard_context(): key = filename, value = (timestamp, context_dict)
_ctx_cache = {}
_CTX_CACHE_TTL = 300  # 5 minutes

# Cache for build_report_charts(): key = filename, value = (timestamp, chart_images_dict)
_chart_cache = {}
_CHART_CACHE_TTL = 600  # 10 minutes

# Cache for inlined HTML assets: key = 'assets', value = dict of file contents
_inlined_assets_cache = None

# Cache for custom HTML report output: key = (filename, params_hash), value = (timestamp, html_string)
_custom_html_cache = {}
_CUSTOM_HTML_CACHE_TTL = 120  # 2 minutes (shorter since params change often)


def _invalidate_ctx_cache(filename):
    """Invalidate cached context for a file (called after cleaning operations)."""
    filename = _session_key(filename)
    _ctx_cache.pop(filename, None)
    _chart_cache.pop(filename, None)
    _custom_html_cache.pop(filename, None)


def _get_cached_ctx(filename):
    """Return cached context if still valid, else None."""
    entry = _ctx_cache.get(_session_key(filename))
    if entry and (_time.time() - entry[0]) < _CTX_CACHE_TTL:
        return entry[1]
    return None


def _set_cached_ctx(filename, ctx):
    """Store context in cache."""
    _ctx_cache[_session_key(filename)] = (_time.time(), ctx)


def _get_cached_charts(filename):
    """Return cached chart images if still valid, else None."""
    entry = _chart_cache.get(_session_key(filename))
    if entry and (_time.time() - entry[0]) < _CHART_CACHE_TTL:
        return entry[1]
    return None


def _set_cached_charts(filename, charts):
    """Store chart images in cache."""
    _chart_cache[_session_key(filename)] = (_time.time(), charts)


def current_user():
    # All entry points use the account authentication session.
    user_id = session.get('user_id')
    if user_id:
        return {
            'id': user_id,
            'name': session.get('username', 'User'),
            'email': session.get('email', ''),
            'role': 'Data Analyst',
        }

    return None


def login_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash('Silakan login terlebih dahulu.', 'info')
            return redirect(url_for('auth.login', next=request.path))
        return fn(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_current_user():
    return {'current_user': current_user()}


@app.before_request
def require_login_for_private_routes():
    if request.endpoint in ('index', 'login', 'logout', 'static', 'landing'):
        return None

    # Allow all auth blueprint routes
    if request.endpoint and request.endpoint.startswith('auth.'):
        return None

    private_prefixes = ('/upload', '/dashboard', '/timeseries', '/api/')
    if not request.path.startswith(private_prefixes):
        return None

    if current_user():
        return None

    if request.path.startswith('/api/'):
        return jsonify({'ok': False, 'error': 'Silakan login terlebih dahulu.'}), 401

    flash('Silakan login terlebih dahulu.', 'info')
    return redirect(url_for('auth.login', next=request.path))


def _user_upload_dir():
    user = current_user()
    if not user:
        return None

    from backend.user_data import get_upload_dir
    upload_dir = get_upload_dir(user['id'], user.get('name', 'user'))
    if upload_dir:
        os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _session_key(filename):
    user = current_user()
    if not user:
        return filename
    return f"{user['id']}::{filename}"


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_or_init_session(filename):
    """
    Ambil CleaningSession untuk filename.
    Jika belum ada di memory, coba load dari disk.
    Jika tidak ada di disk juga, buat baru dari file upload.
    Secures against path traversal attacks by validating with secure_filename.
    Return: (session, error_msg)
    """
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        return None, 'Nama file tidak valid.'

    key = _session_key(safe_name)

    # Coba dari memory dulu
    sess = get_session(key)
    if sess is not None:
        return sess, None

    # Coba load dari disk
    from backend.cleaning_engine import load_session_from_disk
    sess = load_session_from_disk(key)
    if sess is not None:
        return sess, None

    # Buat baru dari file upload
    base_dir = _user_upload_dir()
    if not base_dir:
        return None, 'Silakan login terlebih dahulu.'

    filepath = os.path.abspath(os.path.join(base_dir, safe_name))
    if not filepath.startswith(base_dir):
        return None, 'Akses tidak sah.'

    if not os.path.exists(filepath):
        return None, 'File tidak ditemukan.'

    df_raw = load_data(filepath)
    if df_raw is None:
        return None, 'Gagal membaca dataset.'

    sess = reset_session(key, df_raw)
    return sess, None


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('landing.html')


@app.route('/landing')
def landing():
    return render_template('landing.html')


@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', code=404, message='Halaman tidak ditemukan.'), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template('error.html', code=500, message='Terjadi kesalahan server internal.'), 500


@app.route('/login', methods=['GET', 'POST'])
def login():
    # Keep old links working while using one authentication implementation.
    from backend.auth import login as account_login
    return account_login()


@app.route('/logout')
def logout():
    from backend.auth import logout as account_logout
    return account_logout()


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    def upload_error(message, status=400):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'ok': False, 'error': message, 'message': message}), status
        flash(message, 'error')
        return redirect(request.url)

    uploaded_files = []
    try:
        folder_path = _user_upload_dir()
        if folder_path and os.path.exists(folder_path):
            files = [
                f for f in os.listdir(folder_path)
                if os.path.isfile(os.path.join(folder_path, f))
            ]
            files.sort(
                key=lambda x: os.path.getmtime(os.path.join(folder_path, x)),
                reverse=True,
            )
            uploaded_files = files
    except Exception as e:
        print(f"Error membaca history: {e}")

    if request.method == 'POST':
        if 'file' not in request.files:
            return upload_error('Pilih file dataset terlebih dahulu.')

        file = request.files['file']
        if file.filename == '':
            return upload_error('Pilih file dataset terlebih dahulu.')

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            if not filename or not allowed_file(filename):
                return upload_error('Nama file tidak valid.')
            folder_path = _user_upload_dir()
            filepath = os.path.join(folder_path, filename)

            # ── Deteksi duplikat ──────────────────────────────────────────────
            if os.path.exists(filepath):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'duplicate': True,
                        'filename' : filename,
                        'redirect' : url_for('dashboard', filename=filename),
                    })
                flash(
                    f'Dataset "{filename}" sudah pernah dianalisis sebelumnya. '
                    'Menampilkan data lama...', 'info',
                )
                return redirect(url_for('dashboard', filename=filename))

            file.save(filepath)

            try:
                df_raw = load_data(filepath, strict=True)
            except DataLoadError as error:
                os.remove(filepath)
                return upload_error(str(error))

            # ── Init cleaning session untuk file baru ─────────────────────────
            if df_raw is not None:
                reset_session(_session_key(filename), df_raw)
                # Record upload to history
                user = current_user()
                if user:
                    from backend.user_data import add_to_history
                    add_to_history(user['id'], 'upload', {
                        'filename': filename,
                        'rows': len(df_raw),
                        'cols': len(df_raw.columns),
                    }, user.get('name'))

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'duplicate': False,
                    'filename' : filename,
                    'redirect' : url_for('dashboard', filename=filename),
                })

            flash(f'Dataset "{filename}" berhasil diunggah!', 'success')
            return redirect(url_for('dashboard', filename=filename))
        else:
            return upload_error('Format file tidak valid. Gunakan .csv, .txt, atau .xlsx')

    return render_template('upload.html', history=uploaded_files)


def _get_dashboard_context(filename):
    """
    Computes dashboard context variables.
    Secures against path traversal attacks.
    Results are cached for 5 minutes to avoid recomputation.
    """
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        return None

    # ── Check cache first ──────────────────────────────────────────────────
    cached = _get_cached_ctx(safe_name)
    if cached is not None:
        return cached

    base_dir = _user_upload_dir()
    if not base_dir:
        return None

    filepath = os.path.abspath(os.path.join(base_dir, safe_name))
    if not filepath.startswith(base_dir):
        return None

    if not os.path.exists(filepath):
        return None

    df_raw = load_data(filepath)
    if df_raw is None:
        return None

    # ── Ambil atau inisialisasi CleaningSession ───────────────────────────────
    sess, session_error = _get_or_init_session(safe_name)
    if sess is None:
        return None

    # ── Tentukan df yang dipakai (cleaned atau raw) ───────────────────────────
    is_cleaned   = sess.is_cleaned
    df           = sess.df_current     # cleaned kalau sudah cleaning, raw kalau belum
    data_status  = detect_data_status(df)

    # ── Quality report (dari current df) untuk overview warning ─────────────────────
    quality_full = get_quality_report(df)
    if is_cleaned and len(sess._history) > 1:
        last_snap      = sess._history[-1]
        cleaning_log   = last_snap.summary.get('log', [])
        cleaning_summary = {
            'rows_before'       : last_snap.summary['rows_before'],
            'rows_after'        : last_snap.summary['rows_after'],
            'cols_before'       : last_snap.summary['cols_before'],
            'cols_after'        : last_snap.summary['cols_after'],
            'missing_before'    : last_snap.summary['missing_before'],
            'missing_after'     : last_snap.summary['missing_after'],
            'missing_pct_before': round(
                last_snap.summary['missing_before'] /
                max(last_snap.summary['rows_before'] * last_snap.summary['cols_before'], 1) * 100, 2
            ),
            'missing_pct_after' : round(
                last_snap.summary['missing_after'] /
                max(last_snap.summary['rows_after'] * last_snap.summary['cols_after'], 1) * 100, 2
            ),
            'duplicates_removed': last_snap.summary.get('rows_removed', 0),
            'log'               : cleaning_log,
        }
    else:
        # Backward-compat: build cleaning_summary from raw data
        cleaning_summary = {
            'rows_before'       : len(df_raw),
            'rows_after'        : len(df),
            'cols_before'       : len(df_raw.columns),
            'cols_after'        : len(df.columns),
            'missing_before'    : int(df_raw.isna().sum().sum()),
            'missing_after'     : int(df.isna().sum().sum()),
            'missing_pct_before': round(int(df_raw.isna().sum().sum()) / max(df_raw.size, 1) * 100, 2),
            'missing_pct_after' : round(int(df.isna().sum().sum()) / max(df.size, 1) * 100, 2),
            'duplicates_removed': len(df_raw) - len(df),
            'log'               : [],
        }

    # ── Column detection ──────────────────────────────────────────────────────
    num_cols, cat_cols, ts_cols = detect_data_types(df)

    # ── GLOBAL DATA SANITIZATION ──────────────────────────────────────────────
    df_stats = sanitize_df_numeric_cols(df, num_cols)

    # ── Summary metrics ───────────────────────────────────────────────────────
    metrics = get_summary_metrics(df_stats, num_cols, cat_cols)

    # ── Descriptive stats ─────────────────────────────────────────────────────
    num_stats, cat_stats = get_descriptive_stats(df_stats, num_cols, cat_cols)

    # ── Advanced stats ────────────────────────────────────────────────────────
    advanced = get_advanced_stats(df_stats, num_cols, cat_cols)

    # ── Time Series detection (merge preprocessing ts_cols + legacy detector) ─
    dt_cols_legacy = detect_datetime_cols(df)
    dt_cols = list(set(ts_cols + dt_cols_legacy))

    # ── Dashboard overview ────────────────────────────────────────────────────
    overview = generate_overview_dashboard(
        df, num_cols, cat_cols, dt_cols=dt_cols, metrics=metrics
    )

    # ── Time Series plots ─────────────────────────────────────────────────────
    plots            = {}
    ts_insights_list = []
    ts_meta          = {}

    if dt_cols:
        try:
            ts_plots, ts_insights_list, ts_meta = generate_ts_plots(
                df, dt_cols, num_cols
            )
            plots = ts_plots
        except Exception as e:
            print(f"[TS] generate_ts_plots error: {e}")

    # ── Intelligent insights (bilingual) ───────────────────────────────────
    auto_insights_bilingual = generate_auto_insights(
        df, num_cols, cat_cols, ts_insights=ts_insights_list
    )
    auto_insights_en = auto_insights_bilingual.get('en', [])
    auto_insights_id = auto_insights_bilingual.get('id', [])

    # ── Preview HTML ──────────────────────────────────────────────────────────
    preview_raw_html = df_raw.to_html(
        classes='data-table display nowrap',
        index=False,
        table_id='preview-raw-table',
    )
    preview_clean_html = df.to_html(
        classes='data-table display nowrap',
        index=False,
        table_id='preview-clean-table',
    )

    # ── Dataset info untuk sidebar card ───────────────────────────────────────
    file_size_kb = 0.0
    if os.path.exists(filepath):
        file_size_kb = os.path.getsize(filepath) / 1024.0
    file_size_str = f"{file_size_kb:,.2f} KB"

    dt_file = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
    months  = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]
    upload_time_str = (
        f"{dt_file.day:02d} {months[dt_file.month - 1]} {dt_file.year} "
        f"{dt_file.hour:02d}:{dt_file.minute:02d}"
    )
    dataset_info = {
        'name': safe_name,
        'rows': metrics['total_rows'],
        'cols': metrics['total_columns'],
        'size': file_size_str,
        'time': upload_time_str,
    }

    # ── col_data untuk interactive chart (sampled) ────────────────────────────
    col_data = {}
    for col in num_cols:
        series = df_stats[col].dropna()
        if len(series) > 2000:
            series = series.sample(2000, random_state=42)
        
        vals = []
        for v in series.tolist():
            try:
                f = float(v)
                if not np.isnan(f) and not np.isinf(f):
                    vals.append(round(f, 4))
            except (ValueError, TypeError):
                continue
        col_data[col] = {
            'type'  : 'numeric',
            'values': vals,
        }
    for col in cat_cols:
        vc = df[col].value_counts().head(20)
        col_data[col] = {
            'type'  : 'categorical',
            'labels': vc.index.astype(str).tolist(),
            'counts': [int(v) for v in vc.values.tolist()],
        }

    # ── Cleaning history untuk UI ─────────────────────────────────────────────
    cleaning_history = sess.history_labels

    # ── clean_opts dummy untuk backward-compat template lama ─────────────────
    clean_opts = {
        'strip_whitespace'       : True,
        'empty_to_nan'           : True,
        'drop_duplicates'        : True,
        'drop_empty_cols'        : True,
        'drop_high_missing'      : 0.0,
        'fill_missing_numeric'   : 'none',
        'fill_missing_categorical': 'none',
        'cap_outliers'           : False,
    }

    # ── Auto-generated recommendations for the Report tab ───────────────────
    recommendations = []
    # Based on data quality
    if quality_full and hasattr(quality_full, 'get'):
        warnings = quality_full.get('warnings', []) if isinstance(quality_full, dict) else []
        if warnings:
            recommendations.append({
                'icon': 'fa-broom',
                'title': 'Lakukan Data Cleaning',
                'desc': f'Dataset memiliki {len(warnings)} warning kualitas data. '
                        'Disarankan melakukan cleaning terlebih dahulu untuk hasil analisis yang lebih akurat.',
                'priority': 'high',
            })
    # Based on missing data
    total_missing = int(df.isna().sum().sum())
    if total_missing > 0:
        recommendations.append({
            'icon': 'fa-exclamation-triangle',
            'title': 'Tangani Missing Values',
            'desc': f'Terdapat {total_missing:,} missing values pada dataset. '
                    'Pertimbangkan untuk melakukan imputasi atau penghapusan baris yang tidak lengkap.',
            'priority': 'high',
        })
    # Based on column types
    if len(num_cols) >= 2:
        recommendations.append({
            'icon': 'fa-chart-line',
            'title': 'Eksplorasi Analisis Bivariate',
            'desc': f'Dataset memiliki {len(num_cols)} kolom numerik. '
                    'Gunakan visualisasi Bivariate (Scatter, Heatmap) untuk menemukan pola korelasi antar variabel.',
            'priority': 'medium',
        })
    if len(cat_cols) > 0 and len(num_cols) > 0:
        recommendations.append({
            'icon': 'fa-shuffle',
            'title': 'Analisis Perbandingan Kelompok',
            'desc': 'Kombinasi kolom kategorik dan numerik memungkinkan analisis Cat vs Num '
                    '(Boxplot by Category, Violin, Grouped Bar) untuk membandingkan distribusi antar kelompok.',
            'priority': 'medium',
        })
    if dt_cols:
        recommendations.append({
            'icon': 'fa-clock',
            'title': 'Analisis Tren Waktu',
            'desc': f'Kolom time series terdeteksi ({", ".join(dt_cols[:3])}). '
                    'Manfaatkan menu Time Series untuk melihat tren, pola musiman, dan moving average.',
            'priority': 'medium',
        })
    if not recommendations:
        recommendations.append({
            'icon': 'fa-check-circle',
            'title': 'Data Siap Dianalisis',
            'desc': 'Dataset dalam kondisi baik. Jelajahi berbagai menu visualisasi dan statistik untuk mendapatkan insight.',
            'priority': 'low',
        })

    # ── Team members for the Report tab ──────────────────────────────────────
    team_members = [
        {'name': 'Carol Dupino Pereira',   'nim': '52250051', 'role': 'Data Science',
         'photo': 'https://raw.githubusercontent.com/caroldupinopereira-cmyk/carol/main/carol_1-removebg-preview.png',
         'github': 'https://github.com/caroldupinopereira-cmyk'},
        {'name': 'Refantanur Husnul Haqib', 'nim': '52250052', 'role': 'Data Science',
         'photo': 'https://raw.githubusercontent.com/adindaadeliafutri6-gif/refan/main/Foto_refan-removebg-preview.png',
         'github': 'https://github.com/refantanjung23-wq'},
        {'name': 'Cahaya Medina Semidang',  'nim': '52250053', 'role': 'Data Science',
         'photo': 'https://raw.githubusercontent.com/cahayasemidang-max/foto/cfc8d91ef344fb1beba4eadb93e4be67168bc2b8/FotoCahaya.png',
         'github': 'https://github.com/cahayasemidang-max'},
        {'name': 'Raihania Syah Putri',     'nim': '52250054', 'role': 'Data Science',
         'photo': 'https://raw.githubusercontent.com/raihaniasyahputri/Foto_lulu/696dc3e134536210f870e9d5230b8fbeaad40e0d/IMG-20251129-WA0001.png',
         'github': 'https://github.com/raihaniasyahputri'},
        {'name': 'Cloise Shafira',          'nim': '52250044', 'role': 'Data Science',
         'photo': 'https://raw.githubusercontent.com/cahayasemidang-max/foto/b7534990c32ff093c6cb2faefc6282f5f6079296/FotoCloise.png',
         'github': 'https://github.com/xcoliyyyzz1/cloi'},
        {'name': 'Adinda Adelia Futri',     'nim': '52250055', 'role': 'Student Admin',
         'photo': 'https://raw.githubusercontent.com/caroldupinopereira-cmyk/adinda/main/adinda_baru-removebg-preview.png',
         'github': 'https://github.com/adindaadeliafutri6-gif'},
    ]

    ctx = {
        'filename'          : safe_name,
        'data_status'       : data_status,
        'preview'           : preview_clean_html if is_cleaned else preview_raw_html,
        'preview_raw'       : preview_raw_html,
        'preview_clean'     : preview_clean_html,
        'is_cleaned'        : is_cleaned,
        'metrics'           : metrics,
        'num_stats'         : num_stats,
        'cat_stats'         : cat_stats,
        'plots'             : plots,
        'insights'          : auto_insights_en,
        'insights_en'       : auto_insights_en,
        'insights_id'       : auto_insights_id,
        'advanced'          : advanced,
        'num_cols'          : num_cols,
        'cat_cols'          : cat_cols,
        'col_data'          : col_data,
        'dataset_info'      : dataset_info,
        'cleaning_summary'  : cleaning_summary,
        'quality_report'    : quality_full,
        'quality_full'      : quality_full,
        'clean_opts'        : clean_opts,
        'cleaning_history'  : cleaning_history,
        'overview'          : overview,
        'has_ts'            : bool(dt_cols),
        'dt_cols'           : dt_cols,
        'ts_meta'           : ts_meta,
        'recommendations'   : recommendations,
        'team_members'      : team_members,
    }

    _set_cached_ctx(safe_name, ctx)
    return ctx


@app.route('/dashboard/<filename>')
def dashboard(filename):
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        flash('Nama file tidak valid.', 'error')
        return redirect(url_for('upload_file'))

    ctx = _get_dashboard_context(safe_name)
    if ctx is None:
        flash('File atau data tidak dapat dimuat.', 'error')
        return redirect(url_for('upload_file'))

    return render_template('dashboard.html', **ctx)


@app.route('/dashboard/<filename>/report/pdf')
def download_report_pdf(filename):
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        flash('Nama file tidak valid.', 'error')
        return redirect(url_for('upload_file'))

    ctx = _get_dashboard_context(safe_name)
    if ctx is None:
        flash('File atau data tidak dapat dimuat.', 'error')
        return redirect(url_for('upload_file'))

    # Path to temp PDF file
    temp_dir = os.path.join(_user_upload_dir(), 'temp_reports')
    os.makedirs(temp_dir, exist_ok=True)
    temp_pdf_path = os.path.join(temp_dir, f"{safe_name}_report.pdf")

    # Load sess to pass df
    sess = get_session(_session_key(safe_name))
    df = sess.df_current

    from backend.report_generator import generate_pdf_report
    try:
        # Generate chart images for PDF (with caching)
        chart_images = _get_cached_charts(safe_name)
        if chart_images is None:
            try:
                from backend.report_chart_builder import build_report_charts
                chart_images = build_report_charts(
                    df,
                    ctx.get('num_cols', []),
                    ctx.get('cat_cols', []),
                    ctx['num_stats'],
                )
                _set_cached_charts(safe_name, chart_images)
            except Exception as e:
                print(f"[PDF] Chart generation failed, continuing without images: {e}")
                chart_images = {}

        generate_pdf_report(
            temp_pdf_path,
            safe_name,
            df,
            ctx.get('quality_full') or ctx.get('quality_report'),  # prefer rich dict
            ctx['metrics'],
            ctx['num_stats'],
            ctx['cat_stats'],
            ctx['insights'],
            ctx['cleaning_history'],
            ctx['cleaning_summary'],
            chart_images=chart_images,
            num_cols=ctx.get('num_cols', []),
            cat_cols=ctx.get('cat_cols', []),
        )
        from flask import send_file
        return send_file(
            temp_pdf_path,
            as_attachment=True,
            download_name=f"{os.path.splitext(safe_name)[0]}_report.pdf"
        )
    except Exception as e:
        flash(f"Gagal membuat laporan PDF: {e}", 'error')
        return redirect(url_for('dashboard', filename=safe_name))


@app.route('/dashboard/<filename>/preview/pdf')
def preview_report_pdf(filename):
    """Serve PDF inline for iframe preview (no download prompt)."""
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        return 'Invalid filename', 400

    ctx = _get_dashboard_context(safe_name)
    if ctx is None:
        return 'Data not found', 404

    temp_dir = os.path.join(_user_upload_dir(), 'temp_reports')
    os.makedirs(temp_dir, exist_ok=True)
    temp_pdf_path = os.path.join(temp_dir, f"{safe_name}_preview.pdf")

    sess = get_session(_session_key(safe_name))
    df = sess.df_current

    from backend.report_generator import generate_pdf_report
    try:
        chart_images = _get_cached_charts(safe_name)
        if chart_images is None:
            try:
                from backend.report_chart_builder import build_report_charts
                chart_images = build_report_charts(
                    df,
                    ctx.get('num_cols', []),
                    ctx.get('cat_cols', []),
                    ctx['num_stats'],
                )
                _set_cached_charts(safe_name, chart_images)
            except Exception:
                chart_images = {}

        generate_pdf_report(
            temp_pdf_path, safe_name, df,
            ctx.get('quality_full') or ctx.get('quality_report'),
            ctx['metrics'], ctx['num_stats'], ctx['cat_stats'],
            ctx['insights'], ctx['cleaning_history'], ctx['cleaning_summary'],
            chart_images=chart_images,
            num_cols=ctx.get('num_cols', []),
            cat_cols=ctx.get('cat_cols', []),
        )
        from flask import send_file
        return send_file(temp_pdf_path, mimetype='application/pdf')
    except Exception as e:
        return f'Error generating preview: {e}', 500


@app.route('/dashboard/<filename>/preview/html')
def preview_report_html(filename):
    """Serve HTML inline for iframe preview (no download prompt)."""
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        return 'Invalid filename', 400

    ctx = _get_dashboard_context(safe_name)
    if ctx is None:
        return 'Data not found', 404

    rendered = render_template('dashboard.html', **ctx)
    inlined = inline_html_assets(rendered)

    from flask import Response
    return Response(inlined, mimetype='text/html')


@app.route('/dashboard/<filename>/preview/html/custom', methods=['POST'])
def preview_report_html_custom(filename):
    """Serve custom HTML report based on sidebar params (theme, language, sections, metadata, conclusion)."""
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        return 'Invalid filename', 400

    data = request.get_json() or {}

    ctx = _get_dashboard_context(safe_name)
    if ctx is None:
        return 'Data not found', 404

    # Map sidebar section keys to report section keys
    SECTION_MAP = {
        'cover': 'pendahuluan',
        'completeness': 'dataset',
        'descriptive': 'statistik_num',
        'distribution': 'visualisasi',
        'categorical': 'statistik_cat',
        'correlation': 'visualisasi',
        'bivariate': 'visualisasi',
        'ai_summary': 'insight',
        'signature': 'penutup',
    }
    sidebar_sections = data.get('sections', [])
    selected_sections = []
    for sec in sidebar_sections:
        mapped = SECTION_MAP.get(sec)
        if mapped and mapped not in selected_sections:
            selected_sections.append(mapped)
    if not selected_sections:
        selected_sections = None  # use all

    theme = data.get('theme', 'academic_slate')
    language = data.get('language', 'id')
    analyst_name = data.get('analyst', '')
    report_title = data.get('title', '')
    institution = data.get('institution', '')
    conclusion = data.get('conclusion', '')

    # Check custom HTML cache
    cache_key = (safe_name, theme, language, tuple(selected_sections or []), analyst_name, report_title, institution, conclusion)
    import hashlib
    cache_hash = hashlib.md5(str(cache_key).encode()).hexdigest()
    user_cache_key = _session_key(safe_name)
    file_cache = _custom_html_cache.get(user_cache_key, {})
    cached_entry = file_cache.get(cache_hash)
    if cached_entry and (_time.time() - cached_entry[0]) < _CUSTOM_HTML_CACHE_TTL:
        from flask import Response
        return Response(cached_entry[1], mimetype='text/html')

    # Get session/df
    sess = get_session(_session_key(safe_name))
    if sess is None:
        return 'Session not found', 404
    df = sess.df_current

    from backend.html_report_generator import generate_html_report
    try:
        html = generate_html_report(
            dest_path=None,
            filename=safe_name,
            df=df,
            quality_report=ctx.get('quality_full') or ctx.get('quality_report'),
            metrics=ctx['metrics'],
            num_stats=ctx['num_stats'],
            cat_stats=ctx['cat_stats'],
            auto_insights=ctx.get('insights', []),
            cleaning_history=ctx.get('cleaning_history', []),
            cleaning_summary=ctx.get('cleaning_summary', {}),
            selected_sections=selected_sections,
            analyst_name=analyst_name,
            report_title=report_title,
            language=language,
            theme=theme,
            conclusion=conclusion,
            institution=institution,
            ts_meta=ctx.get('ts_meta'),
            return_html=True,
        )
        if user_cache_key not in _custom_html_cache:
            _custom_html_cache[user_cache_key] = {}
        _custom_html_cache[user_cache_key][cache_hash] = (_time.time(), html)
        from flask import Response
        return Response(html, mimetype='text/html')
    except Exception as e:
        return f'Error generating custom report: {e}', 500


def inline_html_assets(rendered_html):
    """
    Inlines style.css, jquery.min.js, plotly.min.js, script.js, dashboardOverview.js,
    and visualizationsMaster.js into the rendered HTML to ensure fully functional offline support.
    File contents are cached after first read.
    """
    global _inlined_assets_cache
    static_dir = os.path.join(app.root_path, 'frontend', 'static')
    import re

    # Load and cache file contents on first call
    if _inlined_assets_cache is None:
        _inlined_assets_cache = {}
        # CSS
        css_path = os.path.join(static_dir, 'css', 'style.css')
        if os.path.exists(css_path):
            try:
                with open(css_path, 'r', encoding='utf-8') as f:
                    _inlined_assets_cache['css'] = f.read()
            except Exception:
                pass
        # JS files
        js_files = {
            'jquery': os.path.join(static_dir, 'js', 'jquery.min.js'),
            'plotly': os.path.join(static_dir, 'js', 'plotly.min.js'),
            'script': os.path.join(static_dir, 'js', 'script.js'),
            'overview': os.path.join(static_dir, 'js', 'dashboardOverview.js'),
            'vizmaster': os.path.join(static_dir, 'js', 'visualizationsMaster.js'),
        }
        for key, path in js_files.items():
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        _inlined_assets_cache[key] = f.read()
                except Exception:
                    pass

    # 1. Inline CSS
    css_content = _inlined_assets_cache.get('css')
    if css_content:
        css_tag = f'<style>\n/* INLINED style.css */\n{css_content}\n</style>'
        rendered_html = re.sub(
            r'<link[^>]*href=[^>]*style\.css[^>]*>',
            css_tag,
            rendered_html
        )

    # 2. Inline JS files
    js_patterns = [
        (r'jquery\.min\.js', 'jquery'),
        (r'plotly\.min\.js', 'plotly'),
        (r'script\.js', 'script'),
        (r'dashboardOverview\.js', 'overview'),
        (r'visualizationsMaster\.js', 'vizmaster'),
    ]

    for pattern, cache_key in js_patterns:
        js_content = _inlined_assets_cache.get(cache_key)
        if js_content:
            js_tag = f'<script type="text/javascript">\n/* INLINED {cache_key} */\n{js_content}\n</script>'
            tag_pattern = re.compile(r'<script[^>]*src=[^>]*' + pattern + r'[^>]*>\s*</script>')
            rendered_html = tag_pattern.sub(lambda m: js_tag, rendered_html)

    return rendered_html


@app.route('/dashboard/<filename>/report/html')
def download_report_html(filename):
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        flash('Nama file tidak valid.', 'error')
        return redirect(url_for('upload_file'))

    ctx = _get_dashboard_context(safe_name)
    if ctx is None:
        flash('File atau data tidak dapat dimuat.', 'error')
        return redirect(url_for('upload_file'))

    rendered = render_template('dashboard.html', **ctx)
    inlined = inline_html_assets(rendered)

    from flask import Response
    return Response(
        inlined,
        mimetype='text/html',
        headers={"Content-disposition": f"attachment; filename={os.path.splitext(safe_name)[0]}_dashboard.html"}
    )


@app.route('/dashboard/<filename>/export/excel')
def export_excel(filename):
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        flash('Nama file tidak valid.', 'error')
        return redirect(url_for('upload_file'))

    sess, err = _get_or_init_session(safe_name)
    if err:
        flash(err, 'error')
        return redirect(url_for('upload_file'))

    df = sess.df_current

    from io import BytesIO
    from openpyxl.utils import get_column_letter

    excel_buffer = BytesIO()
    try:
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Cleaned Data', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Cleaned Data']

            # Enable AutoFilter on header row
            max_col = worksheet.max_column
            max_row = worksheet.max_row
            if max_col > 0 and max_row > 0:
                last_col_letter = get_column_letter(max_col)
                worksheet.auto_filter.ref = f"A1:{last_col_letter}{max_row}"

            # Auto-adjust column widths
            for col in worksheet.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    if cell.value is not None:
                        max_len = max(max_len, len(str(cell.value)))
                worksheet.column_dimensions[col_letter].width = max(max_len + 3, 10)

        excel_buffer.seek(0)
        from flask import send_file
        return send_file(
            excel_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"{os.path.splitext(safe_name)[0]}_cleaned.xlsx"
        )
    except Exception as e:
        flash(f"Gagal mengekspor data ke Excel: {e}", 'error')
        return redirect(url_for('dashboard', filename=safe_name))


@app.route('/dashboard/<filename>/export/csv')
def export_csv(filename):
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        flash('Nama file tidak valid.', 'error')
        return redirect(url_for('upload_file'))

    sess, err = _get_or_init_session(safe_name)
    if err:
        flash(err, 'error')
        return redirect(url_for('upload_file'))

    df = sess.df_current

    from io import BytesIO, StringIO
    try:
        str_io = StringIO()
        df.to_csv(str_io, index=False)
        mem = BytesIO(str_io.getvalue().encode('utf-8'))
        from flask import send_file
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"{os.path.splitext(safe_name)[0]}_cleaned.csv"
        )
    except Exception as e:
        flash(f"Gagal mengekspor data ke CSV: {e}", 'error')
        return redirect(url_for('dashboard', filename=safe_name))


# ─────────────────────────────────────────────────────────────────────────────
# CLEANING API ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/cleaning/status/<filename>')
def api_cleaning_status(filename):
    """
    GET status session cleaning:
    - is_cleaned, quality_report dari df_current
    - history labels
    - rows & cols current
    """
    sess, err = _get_or_init_session(filename)
    if err:
        return jsonify({'ok': False, 'error': err}), 404

    df = sess.df_current
    return jsonify({
        'ok'          : True,
        'is_cleaned'  : sess.is_cleaned,
        'rows'        : len(df),
        'cols'        : len(df.columns),
        'history'     : sess.history_labels,
        'quality'     : get_quality_report(df),
        'missing_total': int(df.isna().sum().sum()),
    })


@app.route('/api/cleaning/preview/<filename>', methods=['POST'])
def api_cleaning_preview(filename):
    """
    POST preview dampak 1 operasi cleaning TANPA apply.
    Body JSON: { op_type, op_params }
    """
    sess, err = _get_or_init_session(filename)
    if err:
        return jsonify({'ok': False, 'error': err}), 404

    data     = request.get_json() or {}
    op_type  = data.get('op_type', '')
    op_params = data.get('op_params', {})

    if not op_type:
        return jsonify({'ok': False, 'error': 'op_type diperlukan'}), 400

    result = sess.preview_step(op_type, op_params)
    return jsonify(result)


@app.route('/api/cleaning/apply/<filename>', methods=['POST'])
def api_cleaning_apply(filename):
    """
    POST apply 1 operasi cleaning dan simpan ke history.
    Body JSON: { op_type, op_params }
    """
    sess, err = _get_or_init_session(filename)
    if err:
        return jsonify({'ok': False, 'error': err}), 404

    data      = request.get_json() or {}
    op_type   = data.get('op_type', '')
    op_params = data.get('op_params', {})

    if not op_type:
        return jsonify({'ok': False, 'error': 'op_type diperlukan'}), 400

    result = sess.apply_step(op_type, op_params)
    if result.get('ok'):
        _invalidate_ctx_cache(filename)
        try:
            from backend.cleaning_engine import save_cleaned_to_disk, persist_session
            user = current_user()
            if user:
                from backend.user_data import get_cleaned_dir
                cleaned_dir = get_cleaned_dir(user['id'], user.get('name'))
                if cleaned_dir:
                    save_cleaned_to_disk(_session_key(filename), cleaned_dir)
                from backend.user_data import add_to_history
                add_to_history(user['id'], 'cleaning', {
                    'filename': filename, 'operation': op_type,
                    'rows_affected': result.get('summary', {}).get('rows_changed', 0),
                }, user.get('name'))
            persist_session(_session_key(filename))
        except Exception:
            pass
    return jsonify(result)


@app.route('/api/cleaning/undo/<filename>', methods=['POST'])
def api_cleaning_undo(filename):
    """
    POST undo 1 langkah terakhir.
    Body JSON opsional: { index } untuk undo ke titik tertentu
    """
    sess, err = _get_or_init_session(filename)
    if err:
        return jsonify({'ok': False, 'error': err}), 404

    data  = request.get_json() or {}
    index = data.get('index')

    if index is not None:
        result = sess.undo_to(int(index))
    else:
        result = sess.undo()

    if result.get('ok'):
        _invalidate_ctx_cache(filename)
        try:
            from backend.cleaning_engine import save_cleaned_to_disk, persist_session
            user = current_user()
            if user:
                from backend.user_data import get_cleaned_dir
                cleaned_dir = get_cleaned_dir(user['id'], user.get('name'))
                if cleaned_dir:
                    save_cleaned_to_disk(_session_key(filename), cleaned_dir)
            persist_session(_session_key(filename))
        except Exception:
            pass

    return jsonify(result)


@app.route('/api/cleaning/reset/<filename>', methods=['POST'])
def api_cleaning_reset(filename):
    """POST reset ke raw data."""
    sess, err = _get_or_init_session(filename)
    if err:
        return jsonify({'ok': False, 'error': err}), 404

    result = sess.reset()
    if result.get('ok'):
        _invalidate_ctx_cache(filename)
        try:
            from backend.cleaning_engine import save_cleaned_to_disk, persist_session
            user = current_user()
            if user:
                from backend.user_data import get_cleaned_dir
                cleaned_dir = get_cleaned_dir(user['id'], user.get('name'))
                if cleaned_dir:
                    save_cleaned_to_disk(_session_key(filename), cleaned_dir)
            persist_session(_session_key(filename))
        except Exception:
            pass
    return jsonify(result)


@app.route('/api/cleaning/auto-clean/<filename>', methods=['POST'])
def api_cleaning_auto_clean(filename):
    """
    POST auto-clean: jalankan beberapa langkah cleaning sekaligus.
    Body JSON opsional: { options: { ... } }
    """
    sess, err = _get_or_init_session(filename)
    if err:
        return jsonify({'ok': False, 'error': err}), 404

    data = request.get_json() or {}
    options = data.get('options', {})

    result = sess.auto_clean(options)
    if result.get('ok'):
        _invalidate_ctx_cache(filename)
        try:
            from backend.cleaning_engine import save_cleaned_to_disk, persist_session
            user = current_user()
            if user:
                from backend.user_data import get_cleaned_dir
                cleaned_dir = get_cleaned_dir(user['id'], user.get('name'))
                if cleaned_dir:
                    save_cleaned_to_disk(_session_key(filename), cleaned_dir)
                from backend.user_data import add_to_history
                add_to_history(user['id'], 'auto_clean', {
                    'filename': filename,
                    'steps': len(result.get('steps_applied', [])),
                }, user.get('name'))
            persist_session(_session_key(filename))
        except Exception:
            pass
    return jsonify(result)


@app.route('/api/cleaning/preview-table/<filename>')
def api_cleaning_preview_table(filename):
    """
    GET preview tabel df_current (10 baris pertama) sebagai HTML.
    Dipakai untuk refresh preview di Data Preview tab setelah cleaning.
    """
    sess, err = _get_or_init_session(filename)
    if err:
        return jsonify({'ok': False, 'error': err}), 404

    df   = sess.df_current
    html = df.to_html(
        classes='data-table display nowrap',
        index=False,
        border=0,
        table_id='preview-clean-table',
    )
    return jsonify({
        'ok'          : True,
        'html'        : html,
        'is_cleaned'  : sess.is_cleaned,
        'rows'        : len(df),
        'cols'        : len(df.columns),
        'missing'     : int(df.isna().sum().sum()),
    })


@app.route('/api/cleaning/columns/<filename>')
def api_cleaning_columns(filename):
    """
    GET daftar kolom df_current beserta info (dtype, missing, is_numeric).
    Dipakai untuk populate dropdown kolom di form cleaning.
    """
    sess, err = _get_or_init_session(filename)
    if err:
        return jsonify({'ok': False, 'error': err}), 404

    df   = sess.df_current
    cols = []
    for col in df.columns:
        s = df[col]
        cols.append({
            'name'       : col,
            'dtype'      : str(s.dtype),
            'missing'    : int(s.isna().sum()),
            'missing_pct': round(s.isna().mean() * 100, 1),
            'is_numeric' : bool(pd.api.types.is_numeric_dtype(s)),
            'is_text'    : bool(pd.api.types.is_object_dtype(s)),
            'unique'     : int(s.nunique()),
        })
    return jsonify({'ok': True, 'columns': cols, 'is_cleaned': sess.is_cleaned})


@app.route('/api/cleaning/column-profile/<filename>/<col_name>')
def api_column_profile(filename, col_name):
    """
    GET detail profile untuk satu kolom: distribusi, top values, statistics.
    """
    sess, err = _get_or_init_session(filename)
    if err:
        return jsonify({'ok': False, 'error': err}), 404

    df = sess.df_current
    if col_name not in df.columns:
        return jsonify({'ok': False, 'error': f'Kolom "{col_name}" tidak ditemukan.'}), 404

    s = df[col_name]
    total = len(s)
    missing = int(s.isna().sum())
    missing_pct = round(missing / total * 100, 2) if total else 0
    unique = int(s.nunique(dropna=True))
    is_numeric = bool(pd.api.types.is_numeric_dtype(s))

    profile = {
        'column': col_name,
        'dtype': str(s.dtype),
        'total': total,
        'missing': missing,
        'missing_pct': missing_pct,
        'unique': unique,
        'is_numeric': is_numeric,
    }

    if is_numeric:
        valid = s.dropna()
        if not valid.empty:
            profile.update({
                'mean': round(float(valid.mean()), 4),
                'median': round(float(valid.median()), 4),
                'std': round(float(valid.std()), 4),
                'min': round(float(valid.min()), 4),
                'max': round(float(valid.max()), 4),
                'q1': round(float(valid.quantile(0.25)), 4),
                'q3': round(float(valid.quantile(0.75)), 4),
                'skewness': round(float(valid.skew()), 4),
                'kurtosis': round(float(valid.kurt()), 4),
            })
            # Histogram bins
            try:
                counts, bin_edges = np.histogram(valid, bins=10)
                profile['histogram'] = {
                    'counts': [int(c) for c in counts],
                    'edges': [round(float(e), 4) for e in bin_edges],
                }
            except Exception:
                profile['histogram'] = None
        else:
            profile['histogram'] = None
    else:
        # Categorical: top values
        vc = s.value_counts().head(10)
        profile['top_values'] = [
            {'value': str(v), 'count': int(c), 'pct': round(c / total * 100, 1)}
            for v, c in vc.items()
        ]

    # Sample data
    sample = s.dropna().head(5).tolist()
    profile['sample'] = [str(x) for x in sample]

    return jsonify({'ok': True, 'profile': profile})


@app.route('/api/cleaning/before-after/<filename>')
def api_before_after(filename):
    """
    GET perbandingan data sebelum vs sesudah cleaning (10 baris pertama).
    """
    sess, err = _get_or_init_session(filename)
    if err:
        return jsonify({'ok': False, 'error': err}), 404

    df_raw = sess.df_raw
    df_current = sess.df_current

    before_html = df_raw.head(10).to_html(
        classes='data-table', index=False, border=0,
        table_id='before-table',
    )
    after_html = df_current.head(10).to_html(
        classes='data-table', index=False, border=0,
        table_id='after-table',
    )

    # Summary diff
    summary = {
        'rows_before': len(df_raw),
        'rows_after': len(df_current),
        'cols_before': len(df_raw.columns),
        'cols_after': len(df_current.columns),
        'missing_before': int(df_raw.isna().sum().sum()),
        'missing_after': int(df_current.isna().sum().sum()),
        'duplicates_before': int(df_raw.duplicated().sum()),
        'duplicates_after': int(df_current.duplicated().sum()),
    }

    return jsonify({
        'ok': True,
        'before_html': before_html,
        'after_html': after_html,
        'summary': summary,
        'is_cleaned': sess.is_cleaned,
    })


@app.route('/api/cleaning/steps-summary/<filename>')
def api_steps_summary(filename):
    """
    GET ringkasan visual semua langkah cleaning yang sudah dilakukan.
    """
    sess, err = _get_or_init_session(filename)
    if err:
        return jsonify({'ok': False, 'error': err}), 404

    history = sess.history_labels
    steps = []
    for item in history:
        if item['is_initial']:
            continue
        steps.append({
            'index': item['index'],
            'label': item['label'],
            'rows': item['rows'],
            'cols': item['cols'],
            'missing': item['missing'],
            'is_current': item['is_current'],
        })

    # Calculate overall impact
    if len(sess._history) > 1:
        first = sess._history[0]
        last = sess._history[-1]
        impact = {
            'rows_changed': len(last.df) - len(first.df),
            'cols_changed': len(last.df.columns) - len(first.df.columns),
            'missing_changed': int(last.df.isna().sum().sum()) - int(first.df.isna().sum().sum()),
            'total_steps': len(history) - 1,
        }
    else:
        impact = {'rows_changed': 0, 'cols_changed': 0, 'missing_changed': 0, 'total_steps': 0}

    return jsonify({
        'ok': True,
        'steps': steps,
        'impact': impact,
    })


# ─────────────────────────────────────────────────────────────────────────────
# VISUALIZATION MASTER API
# ─────────────────────────────────────────────────────────────────────────────

def _load_analysis_df(filename):
    """
    Muat df untuk visualisasi.
    Prioritaskan df_current dari CleaningSession jika sudah cleaned,
    fallback ke reset_session untuk backward-compat.
    """
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        return None, None, None, None

    folder_path = _user_upload_dir()
    if not folder_path:
        return None, None, None, None

    filepath = os.path.abspath(os.path.join(folder_path, safe_name))
    if not filepath.startswith(folder_path):
        return None, None, None, None

    if not os.path.exists(filepath):
        return None, None, None, None

    sess, error = _get_or_init_session(safe_name)
    if sess is None:
        return None, None, None, None
    df = sess.df_current

    num_cols, cat_cols, ts_cols = detect_data_types(df)
    dt_cols_legacy = detect_datetime_cols(df)
    dt_cols = list(set(ts_cols + dt_cols_legacy))
    return df, num_cols, cat_cols, dt_cols


@app.route('/api/viz-chart/<filename>')
def api_viz_chart(filename):
    """Generate satu grafik master berdasarkan kategori, tipe, dan kolom."""
    try:
        df, num_cols, cat_cols, _ = _load_analysis_df(filename)
        if df is None:
            return jsonify({'ok': False, 'placeholder': 'Dataset tidak ditemukan.'}), 404

        category   = request.args.get('category', 'numerical')
        chart_type = request.args.get('chart_type', '')
        col_x      = request.args.get('col_x') or None
        col_y      = request.args.get('col_y') or None
        col_z      = request.args.get('col_z') or None

        if not chart_type:
            types      = CATEGORY_CHARTS.get(category, [])
            chart_type = types[0] if types else ''

        result = generate_master_chart(
            df, num_cols, cat_cols, category, chart_type,
            col_x=col_x, col_y=col_y, col_z=col_z,
        )
        result['category']  = category
        result['available'] = category_available(category, num_cols, cat_cols)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'ok'         : False,
            'placeholder': f'Gagal memuat grafik: {str(e)}',
            'kpis'       : [],
        })


# ─────────────────────────────────────────────────────────────────────────────
# TIME SERIES PAGE & API
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/timeseries/<filename>')
@login_required
def time_series_page(filename):
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        flash('Nama file tidak valid.', 'error')
        return redirect(url_for('upload_file'))

    base_dir = _user_upload_dir()
    if not base_dir:
        flash('Silakan login terlebih dahulu.', 'error')
        return redirect(url_for('upload_file'))

    filepath = os.path.abspath(os.path.join(base_dir, safe_name))
    if not filepath.startswith(base_dir) or not os.path.exists(filepath):
        flash('File tidak ditemukan.', 'error')
        return redirect(url_for('upload_file'))

    df_raw = load_data(filepath)
    if df_raw is None:
        flash('Gagal membaca dataset.', 'error')
        return redirect(url_for('upload_file'))

    sess, error = _get_or_init_session(safe_name)
    if sess is None:
        flash(error, 'error')
        return redirect(url_for('upload_file'))
    df = sess.df_current

    num_cols, cat_cols, ts_cols = detect_data_types(df)
    dt_cols_legacy = detect_datetime_cols(df)
    dt_cols = list(set(ts_cols + dt_cols_legacy))
    categorical_or_date_cols = list(set(cat_cols + dt_cols))

    return render_template(
        'timeseries.html',
        filename=safe_name,
        num_cols=num_cols,
        categorical_or_date_cols=categorical_or_date_cols,
        dt_cols=dt_cols,
        has_ts=bool(dt_cols),
    )


@app.route('/api/get_complete_timeseries')
def api_get_complete_timeseries():
    filename = request.args.get('filename', '')
    categorical = request.args.get('categorical', '')
    numerical = request.args.get('numerical', '')
    granularity = request.args.get('granularity', 'Auto')

    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        return jsonify({'status': 'error', 'error': 'Nama file tidak valid.'}), 400

    base_dir = _user_upload_dir()
    if not base_dir:
        return jsonify({'status': 'error', 'error': 'Silakan login terlebih dahulu.'}), 401

    filepath = os.path.abspath(os.path.join(base_dir, safe_name))
    if not filepath.startswith(base_dir) or not os.path.exists(filepath):
        return jsonify({'status': 'error', 'error': 'File tidak ditemukan.'}), 404

    df_raw = load_data(filepath)
    if df_raw is None:
        return jsonify({'status': 'error', 'error': 'Gagal membaca dataset.'}), 500

    sess, error = _get_or_init_session(safe_name)
    if sess is None:
        return jsonify({'status': 'error', 'error': error}), 404
    df = sess.df_current

    num_cols, cat_cols, ts_cols = detect_data_types(df)
    dt_cols_legacy = detect_datetime_cols(df)
    dt_cols = list(set(ts_cols + dt_cols_legacy))

    result = generate_complete_timeseries(
        df, dt_cols, num_cols,
        categorical=categorical or None,
        numerical=numerical or None,
        granularity=granularity,
    )

    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# AI INTERPRETATION ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/interpretation/<filename>', methods=['POST'])
def api_interpretation(filename):
    """Generate AI-powered dataset interpretation."""
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        return jsonify({'ok': False, 'error': 'Nama file tidak valid.'}), 400

    ctx = _get_dashboard_context(safe_name)
    if ctx is None:
        return jsonify({'ok': False, 'error': 'Dataset tidak ditemukan.'}), 404

    lang = request.args.get('lang', 'en')
    ai_settings = get_ai_settings(session.get('user_id', 'default'))

    if not ai_settings or not ai_settings.get('api_key'):
        return jsonify({'ok': False, 'error': 'no_api_key', 'message': 'AI API key belum dikonfigurasi.'}), 200

    try:
        result = generate_interpretation(ctx, lang, ai_settings)
        return jsonify({'ok': True, 'data': result})
    except Exception as e:
        error_msg = str(e)
        if 'quota' in error_msg.lower() or '429' in error_msg:
            return jsonify({
                'ok': False,
                'error': 'quota_exceeded',
                'message': error_msg,
                'reset_in_seconds': getattr(e, 'reset_in_seconds', None),
                'keys_exhausted': getattr(e, 'keys_exhausted', None),
                'total_keys': getattr(e, 'total_keys', None),
            }), 200
        return jsonify({'ok': False, 'error': error_msg}), 500


# ─────────────────────────────────────────────────────────────────────────────
# AI CHAT ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/ai-chat', methods=['POST'])
def ai_chat():
    """Multi-provider AI chat endpoint via ai_client."""
    try:
        data = request.get_json()
        user_msg = data.get('message', '')
        context = data.get('context', '')
        filename = data.get('filename', '')

        ai_settings = get_ai_settings(session.get('user_id', 'default'))
        if not ai_settings or not ai_settings.get('api_key'):
            return jsonify({'reply': 'AI API key belum dikonfigurasi.'}), 500

        system_prompt = (
            "Kamu adalah asisten analisis data cerdas bernama DataBot untuk aplikasi "
            "DS Generator Kelompok 2. "
            "Jawab dengan bahasa yang jelas, ringkas, dan informatif. "
            "JANGAN gunakan markdown formatting seperti **bold**, *italic*, atau `code`. "
            "Gunakan teks polos saja. Untuk poin-poin, gunakan tanda strip (-) biasa. "
            "Untuk penekanan, gunakan huruf KAPITAL. "
            f"Konteks dataset saat ini: {context}"
        )

        from backend.ai_client import call_ai, AIClientError, QuotaExceededError
        import re
        try:
            reply = call_ai(
                ai_settings['provider'],
                ai_settings['api_key'],
                ai_settings.get('model', ''),
                system_prompt,
                user_msg,
                api_keys=ai_settings.get('api_keys', []),
            )
            if reply:
                reply = re.sub(r'\*\*(.+?)\*\*', r'\1', reply)
                reply = re.sub(r'\*(.+?)\*', r'\1', reply)
                reply = re.sub(r'`(.+?)`', r'\1', reply)
            return jsonify({'reply': reply})
        except QuotaExceededError as e:
            return jsonify({
                'reply': str(e),
                'error': 'quota_exceeded',
                'reset_in_seconds': e.reset_in_seconds,
            }), 200
        except AIClientError as e:
            return jsonify({'reply': f'Error: {str(e)}'}), 500

    except Exception as e:
        return jsonify({'reply': f'Error: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT JSON
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/dashboard/<filename>/export/json')
def export_json(filename):
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        flash('Nama file tidak valid.', 'error')
        return redirect(url_for('upload_file'))

    sess, err = _get_or_init_session(safe_name)
    if err:
        flash(err, 'error')
        return redirect(url_for('upload_file'))

    df = sess.df_current

    from io import BytesIO, StringIO
    try:
        json_str = df.to_json(orient='records', indent=2, force_ascii=False)
        mem = BytesIO(json_str.encode('utf-8'))
        from flask import send_file
        return send_file(
            mem,
            mimetype='application/json',
            as_attachment=True,
            download_name=f"{os.path.splitext(safe_name)[0]}_export.json"
        )
    except Exception as e:
        flash(f"Gagal mengekspor data ke JSON: {e}", 'error')
        return redirect(url_for('dashboard', filename=safe_name))


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM PDF — Download & Preview
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/dashboard/<filename>/report/pdf/custom', methods=['POST'])
def download_custom_pdf(filename):
    """Generate & download custom PDF with selected sections & charts."""
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        return jsonify({'error': 'Nama file tidak valid.'}), 400

    ctx = _get_dashboard_context(safe_name)
    if ctx is None:
        return jsonify({'error': 'Dataset tidak ditemukan.'}), 404

    data = request.get_json() or {}
    selected_sections = data.get('selected_sections', [])
    selected_charts = data.get('selected_charts', [])
    report_title = data.get('report_title', '')
    analyst_name = data.get('analyst_name', '')

    temp_dir = os.path.join(_user_upload_dir(), 'temp_reports')
    os.makedirs(temp_dir, exist_ok=True)
    temp_pdf_path = os.path.join(temp_dir, f"{safe_name}_custom_report.pdf")

    from backend.report_generator import generate_pdf_report
    try:
        sess = get_session(_session_key(safe_name))
        df = sess.df_current

        chart_images = _get_cached_charts(safe_name)
        if chart_images is None:
            try:
                from backend.report_chart_builder import build_report_charts
                chart_images = build_report_charts(
                    df,
                    ctx.get('num_cols', []),
                    ctx.get('cat_cols', []),
                    ctx['num_stats'],
                )
                _set_cached_charts(safe_name, chart_images)
            except Exception as e:
                print(f"[Custom PDF] Chart generation failed: {e}")
                chart_images = {}

        generate_pdf_report(
            temp_pdf_path,
            safe_name,
            df,
            ctx.get('quality_full') or ctx.get('quality_report'),
            ctx['metrics'],
            ctx['num_stats'],
            ctx['cat_stats'],
            ctx['insights'],
            ctx['cleaning_history'],
            ctx['cleaning_summary'],
            selected_sections=selected_sections,
            selected_charts=selected_charts,
            chart_images=chart_images,
            analyst_name=analyst_name,
            report_title=report_title,
            num_cols=ctx.get('num_cols', []),
            cat_cols=ctx.get('cat_cols', []),
        )

        from flask import send_file
        return send_file(
            temp_pdf_path,
            as_attachment=True,
            download_name=f"Laporan_{safe_name}_{datetime.datetime.now().strftime('%Y-%m-%d')}.pdf"
        )
    except Exception as e:
        return jsonify({'error': f'Gagal generate PDF: {e}'}), 500


@app.route('/dashboard/<filename>/report/pdf/custom/preview', methods=['POST'])
def preview_custom_pdf(filename):
    """Preview custom PDF in new tab (POST form submission)."""
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        return 'Invalid filename', 400

    ctx = _get_dashboard_context(safe_name)
    if ctx is None:
        return 'Data not found', 404

    import json as _json
    selected_sections = _json.loads(request.form.get('selected_sections', '[]'))
    selected_charts = _json.loads(request.form.get('selected_charts', '[]'))
    report_title = request.form.get('report_title', '')
    analyst_name = request.form.get('analyst_name', '')

    temp_dir = os.path.join(_user_upload_dir(), 'temp_reports')
    os.makedirs(temp_dir, exist_ok=True)
    temp_pdf_path = os.path.join(temp_dir, f"{safe_name}_custom_preview.pdf")

    from backend.report_generator import generate_pdf_report
    try:
        sess = get_session(_session_key(safe_name))
        df = sess.df_current

        chart_images = _get_cached_charts(safe_name)
        if chart_images is None:
            try:
                from backend.report_chart_builder import build_report_charts
                chart_images = build_report_charts(
                    df,
                    ctx.get('num_cols', []),
                    ctx.get('cat_cols', []),
                    ctx['num_stats'],
                )
                _set_cached_charts(safe_name, chart_images)
            except Exception:
                chart_images = {}

        generate_pdf_report(
            temp_pdf_path,
            safe_name,
            df,
            ctx.get('quality_full') or ctx.get('quality_report'),
            ctx['metrics'],
            ctx['num_stats'],
            ctx['cat_stats'],
            ctx['insights'],
            ctx['cleaning_history'],
            ctx['cleaning_summary'],
            selected_sections=selected_sections,
            selected_charts=selected_charts,
            chart_images=chart_images,
            analyst_name=analyst_name,
            report_title=report_title,
            num_cols=ctx.get('num_cols', []),
            cat_cols=ctx.get('cat_cols', []),
        )

        from flask import send_file
        return send_file(temp_pdf_path, mimetype='application/pdf')
    except Exception as e:
        return f'Error generating preview: {e}', 500


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM EXPORT — Excel / CSV / JSON with selected columns
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/dashboard/<filename>/export/<export_type>/custom', methods=['POST'])
def custom_export(filename, export_type):
    """Export with user-selected columns. Supports excel, csv, json."""
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        return jsonify({'error': 'Nama file tidak valid.'}), 400

    if export_type not in ('excel', 'csv', 'json'):
        return jsonify({'error': 'Tipe export tidak valid.'}), 400

    sess, err = _get_or_init_session(safe_name)
    if err:
        return jsonify({'error': err}), 404

    data = request.get_json() or {}
    selected_cols = data.get('selected_columns', [])

    df = sess.df_current
    if selected_cols:
        valid_cols = [c for c in selected_cols if c in df.columns]
        if valid_cols:
            df = df[valid_cols]

    from io import BytesIO, StringIO

    try:
        if export_type == 'excel':
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Data', index=False)
            buf.seek(0)
            from flask import send_file
            return send_file(
                buf,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f"{os.path.splitext(safe_name)[0]}_custom.xlsx"
            )

        elif export_type == 'csv':
            str_io = StringIO()
            df.to_csv(str_io, index=False)
            mem = BytesIO(str_io.getvalue().encode('utf-8'))
            from flask import send_file
            return send_file(
                mem,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f"{os.path.splitext(safe_name)[0]}_custom.csv"
            )

        elif export_type == 'json':
            json_str = df.to_json(orient='records', indent=2, force_ascii=False)
            mem = BytesIO(json_str.encode('utf-8'))
            from flask import send_file
            return send_file(
                mem,
                mimetype='application/json',
                as_attachment=True,
                download_name=f"{os.path.splitext(safe_name)[0]}_custom.json"
            )

    except Exception as e:
        return jsonify({'error': f'Gagal export: {e}'}), 500


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True)
