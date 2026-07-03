import time
import secrets
import functools
from collections import defaultdict
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from backend.models import user_model
from backend.user_data import create_user_folder

auth_bp = Blueprint('auth', __name__, url_prefix='/auth', template_folder='../frontend/templates')


# ─── Rate Limiting (in-memory) ─────────────────────────────────────────────
_login_attempts = defaultdict(list)
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300  # 5 minutes


def _is_rate_limited(ip):
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _WINDOW_SECONDS]
    if len(_login_attempts[ip]) >= _MAX_ATTEMPTS:
        return True
    return False


def _record_attempt(ip):
    _login_attempts[ip].append(time.time())


def _clear_attempts(ip):
    _login_attempts.pop(ip, None)


# ─── CSRF Token ────────────────────────────────────────────────────────────

def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def validate_csrf_token():
    token = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
    return token and token == session.get('_csrf_token')


@auth_bp.app_context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token)


# ─── Register ──────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not validate_csrf_token():
            if request.is_json:
                return jsonify({'status': 'error', 'message': 'CSRF token tidak valid.'}), 403
            flash('CSRF token tidak valid. Silakan coba lagi.', 'error')
            return redirect(url_for('auth.register'))

        is_json = request.is_json
        if is_json:
            data = request.get_json()
            username = data.get('username', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            confirm = data.get('confirm_password', data.get('password', ''))
        else:
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            confirm = request.form.get('confirm_password', '')

        if not username or not email or not password:
            if is_json:
                return jsonify({'status': 'error', 'message': 'Semua kolom wajib diisi.'}), 400
            flash('Semua kolom wajib diisi.', 'error')
            return redirect(url_for('auth.register'))

        if len(password) < 8:
            msg = 'Password minimal 8 karakter.'
            if is_json:
                return jsonify({'status': 'error', 'message': msg}), 400
            flash(msg, 'error')
            return redirect(url_for('auth.register'))

        if password != confirm:
            if is_json:
                return jsonify({'status': 'error', 'message': 'Password tidak cocok.'}), 400
            flash('Password tidak cocok.', 'error')
            return redirect(url_for('auth.register'))

        user, err = user_model.create_user(username, email, password)
        if err:
            if is_json:
                return jsonify({'status': 'error', 'message': err}), 400
            flash(err, 'error')
            return redirect(url_for('auth.register'))

        create_user_folder(user['id'], user['username'])

        session['user_id'] = user['id']
        session['username'] = user['username']
        session['email'] = user['email']
        session['is_first_login'] = user['is_first_login']
        session['profile_pic'] = user.get('profile_pic', '')

        upload_url = url_for('upload_file', welcome='new', u=user['username'])
        if is_json:
            return jsonify({'status': 'success', 'redirect': upload_url, 'is_first_login': True})
        flash('Akun berhasil dibuat!', 'success')
        return redirect(upload_url)

    return render_template('auth.html', csrf_token=generate_csrf_token())


# ─── Login ─────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not validate_csrf_token():
            if request.is_json:
                return jsonify({'status': 'error', 'message': 'CSRF token tidak valid.'}), 403
            flash('CSRF token tidak valid. Silakan coba lagi.', 'error')
            return redirect(url_for('auth.login'))

        client_ip = request.remote_addr or 'unknown'

        if _is_rate_limited(client_ip):
            msg = 'Terlalu banyak percobaan login. Coba lagi dalam 5 menit.'
            if request.is_json:
                return jsonify({'status': 'error', 'message': msg}), 429
            flash(msg, 'error')
            return redirect(url_for('auth.login'))

        is_json = request.is_json
        if is_json:
            data = request.get_json()
            login_id = data.get('login', '').strip()
            password = data.get('password', '')
        else:
            login_id = request.form.get('login', '').strip()
            password = request.form.get('password', '')

        if not login_id or not password:
            if is_json:
                return jsonify({'status': 'error', 'message': 'Masukkan username/email dan password.'}), 400
            flash('Masukkan username/email dan password.', 'error')
            return redirect(url_for('auth.login'))

        user, err = user_model.authenticate(login_id, password)
        if err:
            _record_attempt(client_ip)
            if is_json:
                return jsonify({'status': 'error', 'message': err}), 401
            flash(err, 'error')
            return redirect(url_for('auth.login'))

        _clear_attempts(client_ip)
        create_user_folder(user['id'], user['username'])

        session['user_id'] = user['id']
        session['username'] = user['username']
        session['email'] = user['email']
        session['is_first_login'] = user['is_first_login']
        session['profile_pic'] = user.get('profile_pic', '')

        # Remember Me — secure token instead of plain-text password
        remember = request.form.get('remember') or (is_json and request.get_json().get('remember', False))

        first_login = user['is_first_login']
        uname = user['username']
        upload_url = url_for('upload_file', welcome='new' if first_login else 'back', u=uname)

        if is_json:
            if remember:
                token = user_model.create_remember_token(user['id'])
                if token:
                    resp = make_response(jsonify({'status': 'success', 'redirect': upload_url, 'is_first_login': first_login}))
                    resp.set_cookie(
                        'remember_token', token,
                        max_age=30 * 24 * 3600,  # 30 days
                        httponly=True, samesite='Lax', secure=False
                    )
                    return resp
            return jsonify({'status': 'success', 'redirect': upload_url, 'is_first_login': first_login})
        else:
            if remember:
                token = user_model.create_remember_token(user['id'])
                if token:
                    resp = make_response(redirect(upload_url))
                    resp.set_cookie(
                        'remember_token', token,
                        max_age=30 * 24 * 3600,
                        httponly=True, samesite='Lax', secure=False
                    )
                    return resp

            return redirect(upload_url)

    return render_template('auth.html', csrf_token=generate_csrf_token())


# ─── Logout ────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        user_model.revoke_remember_token(user_id)
    session.clear()
    resp = make_response(redirect(url_for('auth.login')))
    resp.delete_cookie('remember_token')
    flash('Anda telah logout.', 'info')
    return resp


# ─── Onboarding ────────────────────────────────────────────────────────────

@auth_bp.route('/onboarding')
def onboarding():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('onboarding.html', username=session.get('username', 'User'))


@auth_bp.route('/complete-onboarding', methods=['POST'])
def complete_onboarding():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'error': 'Belum login.'}), 401

    user_id = session['user_id']
    user_model.set_first_login_done(user_id)
    session['is_first_login'] = False
    uname = session.get('username', 'User')
    return jsonify({'ok': True, 'redirect': url_for('upload_file', welcome='new', u=uname)})


# ─── Forgot Password ───────────────────────────────────────────────────────

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('CSRF token tidak valid. Silakan coba lagi.', 'error')
            return redirect(url_for('auth.forgot_password'))

        is_json = request.is_json
        if is_json:
            data = request.get_json()
            email = data.get('email', '').strip()
        else:
            email = request.form.get('email', '').strip()

        if not email:
            msg = 'Masukkan alamat email Anda.'
            if is_json:
                return jsonify({'status': 'error', 'message': msg}), 400
            flash(msg, 'error')
            return redirect(url_for('auth.forgot_password'))

        user = user_model.get_by_email(email)
        if user:
            token = user_model.create_reset_token(email)
            if token:
                reset_url = url_for('auth.reset_password_page', token=token, _external=True)
                print(f"[PASSWORD RESET] {user['username']}: {reset_url}")

        # Selalu tampilkan pesan sukses (security: jangan bocorkan apakah email ada)
        msg = 'Jika email terdaftar, tautan reset password telah dikirim.'
        if is_json:
            return jsonify({'status': 'success', 'message': msg})
        flash(msg, 'success')
        return redirect(url_for('auth.forgot_password'))

    return render_template('forgot_password.html', csrf_token=generate_csrf_token())


# ─── Reset Password Page ──────────────────────────────────────────────────

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_page(token):
    user = user_model.verify_reset_token(token)
    if not user:
        flash('Tautan reset password tidak valid atau sudah kedaluwarsa.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        if not validate_csrf_token():
            flash('CSRF token tidak valid. Silakan coba lagi.', 'error')
            return redirect(url_for('auth.reset_password_page', token=token))

        is_json = request.is_json
        if is_json:
            data = request.get_json()
            password = data.get('password', '')
            confirm = data.get('confirm_password', '')
        else:
            password = request.form.get('password', '')
            confirm = request.form.get('confirm_password', '')

        if not password or len(password) < 8:
            msg = 'Password minimal 8 karakter.'
            if is_json:
                return jsonify({'status': 'error', 'message': msg}), 400
            flash(msg, 'error')
            return redirect(url_for('auth.reset_password_page', token=token))

        if password != confirm:
            msg = 'Password tidak cocok.'
            if is_json:
                return jsonify({'status': 'error', 'message': msg}), 400
            flash(msg, 'error')
            return redirect(url_for('auth.reset_password_page', token=token))

        updated, err = user_model.reset_password(token, password)
        if err:
            if is_json:
                return jsonify({'status': 'error', 'message': err}), 400
            flash(err, 'error')
            return redirect(url_for('auth.forgot_password'))

        msg = 'Password berhasil diubah! Silakan masuk.'
        if is_json:
            return jsonify({'status': 'success', 'message': msg, 'redirect': url_for('auth.login')})
        flash(msg, 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token, csrf_token=generate_csrf_token())
