import os
from backend.ai_client import DEFAULT_MODELS

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
SETTINGS_FILE = os.path.join(DATA_DIR, 'ai_settings.json')

ALLOWED_PROVIDERS = {'anthropic', 'openai', 'gemini', 'openrouter'}

def _load_env():
    """Load .env file into os.environ if it exists."""
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    load_dotenv(env_path, override=False)


PROVIDER_ENV_MAP = {
    'anthropic': 'ANTHROPIC_API_KEY',
    'openai': 'OPENAI_API_KEY',
    'gemini': 'GEMINI_API_KEY',
    'openrouter': 'OPENROUTER_API_KEY',
}


def get_api_key_for_provider(provider):
    """Get primary API key from .env for a specific provider."""
    _load_env()
    env_var = PROVIDER_ENV_MAP.get(provider)
    if env_var:
        return (os.environ.get(env_var) or '').strip()
    return ''


def get_all_api_keys_for_provider(provider):
    """Get ALL API keys for a provider (primary + numbered fallbacks like _2, _3).

    Returns a list of non-empty keys, primary first.
    Example for gemini: ['key1', 'key2']
    """
    _load_env()
    primary_var = PROVIDER_ENV_MAP.get(provider)
    if not primary_var:
        return []

    keys = []
    primary_val = (os.environ.get(primary_var) or '').strip()
    if primary_val:
        keys.append(primary_val)

    for i in range(2, 10):
        fallback_var = f'{primary_var}_{i}'
        val = (os.environ.get(fallback_var) or '').strip()
        if val:
            keys.append(val)

    return list(dict.fromkeys(keys))


def get_masked_api_key(api_key):
    if not api_key or len(api_key) <= 8:
        return '***' if api_key else ''
    return api_key[:4] + '***' + api_key[-4:]


def get_default_settings():
    """Membaca default AI settings dari file .env di root project."""
    _load_env()

    provider = (os.environ.get('AI_PROVIDER') or '').strip().lower()
    model = (os.environ.get('AI_MODEL') or '').strip()
    configured_provider = provider
    available = {name: get_all_api_keys_for_provider(name) for name in PROVIDER_ENV_MAP}
    if provider not in ALLOWED_PROVIDERS or not available.get(provider):
        provider = next((name for name, keys in available.items() if keys), None)
    if not provider:
        return None
    api_keys = available[provider]
    return {
        'provider': provider,
        'api_key': api_keys[0],
        'api_keys': api_keys,
        'model': model if model and provider == configured_provider else DEFAULT_MODELS[provider],
    }


def get_ai_settings(user_id):
    """Always return default settings from .env (no per-user settings)."""
    return get_default_settings()


def save_ai_settings(user_id, provider, api_key, model):
    """No-op: settings are read-only from .env."""
    pass
