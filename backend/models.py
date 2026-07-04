import os
import json
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
DB_FILE = os.path.join(DATA_DIR, 'users.db')

os.makedirs(DATA_DIR, exist_ok=True)


class UserModel:
    def __init__(self):
        self._init_json()

    def _init_json(self):
        if not os.path.exists(USERS_FILE) or os.path.getsize(USERS_FILE) == 0:
            with open(USERS_FILE, 'w') as f:
                json.dump([], f)

    def _read(self):
        with open(USERS_FILE, 'r') as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)

    def _write(self, data):
        with open(USERS_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def create_user(self, username, email, password):
        users = self._read()
        for u in users:
            if u['username'] == username:
                return None, 'Username already exists'
            if u['email'] == email:
                return None, 'Email already registered'
        user = {
            'id': str(uuid.uuid4()),
            'username': username,
            'email': email,
            'password': generate_password_hash(password),
            'is_first_login': True,
            'created_at': datetime.utcnow().isoformat(),
            'remember_token': None,
            'reset_token': None,
            'reset_token_expires': None,
        }
        users.append(user)
        self._write(users)
        return user, None

    def create_user_oauth(self, username, email, provider, provider_id):
        """Create a new user from OAuth provider."""
        users = self._read()
        for u in users:
            if u['email'] == email:
                return None, 'Email already registered'
        
        # Ensure unique username
        base_username = username
        counter = 1
        while any(u['username'] == username for u in users):
            username = f"{base_username}_{counter}"
            counter += 1
        
        user = {
            'id': str(uuid.uuid4()),
            'username': username,
            'email': email,
            'password': None,  # No password for OAuth users
            'oauth_provider': provider,
            'oauth_provider_id': provider_id,
            'is_first_login': True,
            'created_at': datetime.utcnow().isoformat(),
            'remember_token': None,
            'reset_token': None,
            'reset_token_expires': None,
        }
        users.append(user)
        self._write(users)
        return user, None

    def authenticate(self, login, password):
        users = self._read()
        for u in users:
            if u['username'] == login or u['email'] == login:
                if check_password_hash(u['password'], password):
                    return u, None
                return None, 'Invalid password'
        return None, 'User not found'

    def get_by_id(self, user_id):
        users = self._read()
        for u in users:
            if u['id'] == user_id:
                return u
        return None

    def set_first_login_done(self, user_id):
        users = self._read()
        for u in users:
            if u['id'] == user_id:
                u['is_first_login'] = False
                self._write(users)
                return True
        return False

    def update_profile(self, user_id, username=None, email=None, password=None, profile_pic=None):
        users = self._read()
        for u in users:
            if u['id'] == user_id:
                if username is not None:
                    u['username'] = username
                if email is not None:
                    u['email'] = email
                if password is not None:
                    u['password'] = generate_password_hash(password)
                if profile_pic is not None:
                    u['profile_pic'] = profile_pic
                self._write(users)
                return u, None
        return None, 'User not found'

    def get_by_username(self, username, exclude_id=None):
        users = self._read()
        for u in users:
            if u['username'] == username:
                if exclude_id and u['id'] == exclude_id:
                    continue
                return u
        return None

    # ─── Remember-Me Token (secure, no plain-text password) ────────────────
    def create_remember_token(self, user_id):
        token = secrets.token_urlsafe(64)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        users = self._read()
        for u in users:
            if u['id'] == user_id:
                u['remember_token'] = token_hash
                self._write(users)
                return token
        return None

    def verify_remember_token(self, token):
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        users = self._read()
        for u in users:
            if u.get('remember_token') == token_hash:
                return u
        return None

    def revoke_remember_token(self, user_id):
        users = self._read()
        for u in users:
            if u['id'] == user_id:
                u['remember_token'] = None
                self._write(users)
                return True
        return False

    # ─── Password Reset Token ─────────────────────────────────────────────
    def create_reset_token(self, email):
        users = self._read()
        for u in users:
            if u['email'] == email:
                token = secrets.token_urlsafe(48)
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                u['reset_token'] = token_hash
                u['reset_token_expires'] = (
                    datetime.utcnow() + timedelta(hours=1)
                ).isoformat()
                self._write(users)
                return token
        return None

    def verify_reset_token(self, token):
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        users = self._read()
        for u in users:
            if u.get('reset_token') == token_hash:
                expires = u.get('reset_token_expires')
                if expires:
                    exp_dt = datetime.fromisoformat(expires)
                    if datetime.utcnow() > exp_dt:
                        return None
                return u
        return None

    def reset_password(self, token, new_password):
        user = self.verify_reset_token(token)
        if not user:
            return None, 'Token tidak valid atau sudah kedaluwarsa.'
        users = self._read()
        for u in users:
            if u['id'] == user['id']:
                u['password'] = generate_password_hash(new_password)
                u['reset_token'] = None
                u['reset_token_expires'] = None
                self._write(users)
                return u, None
        return None, 'User tidak ditemukan.'

    def get_by_email(self, email):
        users = self._read()
        for u in users:
            if u['email'] == email:
                return u
        return None


user_model = UserModel()
