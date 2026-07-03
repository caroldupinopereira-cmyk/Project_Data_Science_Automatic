import os
import json

USERS_ROOT = os.path.join(os.path.dirname(__file__), '..', 'data', 'users')


def _make_folder_name(username, user_id):
    short_id = user_id[:8]
    return f"{username}_{short_id}"


def get_user_dir(user_id, username=None):
    if username is None:
        from backend.models import user_model
        user = user_model.get_by_id(user_id)
        if not user:
            return None
        username = user['username']
    folder_name = _make_folder_name(username, user_id)
    return os.path.abspath(os.path.join(USERS_ROOT, folder_name))


def get_upload_dir(user_id, username=None):
    user_dir = get_user_dir(user_id, username)
    if not user_dir:
        return None
    return os.path.join(user_dir, 'uploaded')


def get_cleaned_dir(user_id, username=None):
    user_dir = get_user_dir(user_id, username)
    if not user_dir:
        return None
    return os.path.join(user_dir, 'cleaned')


def get_reports_dir(user_id, username=None):
    user_dir = get_user_dir(user_id, username)
    if not user_dir:
        return None
    return os.path.join(user_dir, 'reports')


def get_history_path(user_id, username=None):
    user_dir = get_user_dir(user_id, username)
    if not user_dir:
        return None
    return os.path.join(user_dir, 'history.json')


def create_user_folder(user_id, username):
    user_dir = get_user_dir(user_id, username)
    if not user_dir:
        return None

    os.makedirs(user_dir, exist_ok=True)
    os.makedirs(os.path.join(user_dir, 'uploaded'), exist_ok=True)
    os.makedirs(os.path.join(user_dir, 'cleaned'), exist_ok=True)
    os.makedirs(os.path.join(user_dir, 'reports'), exist_ok=True)
    os.makedirs(os.path.join(user_dir, 'reports', 'pdf'), exist_ok=True)
    os.makedirs(os.path.join(user_dir, 'reports', 'html'), exist_ok=True)
    os.makedirs(os.path.join(user_dir, 'reports', 'csv'), exist_ok=True)
    os.makedirs(os.path.join(user_dir, 'reports', 'json'), exist_ok=True)

    history_path = os.path.join(user_dir, 'history.json')
    if not os.path.exists(history_path):
        history = {
            'user_id': user_id,
            'username': username,
            'files_uploaded': [],
            'analyses': [],
        }
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=2)

    return user_dir


def add_to_history(user_id, event_type, data, username=None):
    history_path = get_history_path(user_id, username)
    if not os.path.exists(history_path):
        return False

    with open(history_path, 'r') as f:
        history = json.load(f)

    from datetime import datetime
    entry = {
        'type': event_type,
        'timestamp': datetime.utcnow().isoformat(),
        **data,
    }

    if event_type == 'upload':
        history.setdefault('files_uploaded', []).append(entry)
    elif event_type == 'analysis':
        history.setdefault('analyses', []).append(entry)

    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)
    return True


def get_user_history(user_id, username=None):
    history_path = get_history_path(user_id, username)
    if not os.path.exists(history_path):
        return {'files_uploaded': [], 'analyses': []}
    with open(history_path, 'r') as f:
        return json.load(f)


def find_user_folder_by_id(user_id):
    if not os.path.exists(USERS_ROOT):
        return None
    for name in os.listdir(USERS_ROOT):
        if name.endswith(f"_{user_id[:8]}") and os.path.isdir(os.path.join(USERS_ROOT, name)):
            return os.path.join(USERS_ROOT, name)
    return None


def ensure_all_user_folders():
    from backend.models import user_model
    users = user_model._read()
    for user in users:
        user_dir = find_user_folder_by_id(user['id'])
        if user_dir is None:
            create_user_folder(user['id'], user['username'])
