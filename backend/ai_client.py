import requests
import json
from datetime import datetime, timezone, timedelta


class AIClientError(Exception):
    pass


class QuotaExceededError(AIClientError):
    def __init__(self, message, reset_in_seconds=None, keys_exhausted=1, total_keys=1):
        self.reset_in_seconds = reset_in_seconds
        self.keys_exhausted = keys_exhausted
        self.total_keys = total_keys
        self.reset_time_iso = None
        if reset_in_seconds:
            self.reset_time_iso = (datetime.now(timezone.utc) + timedelta(seconds=reset_in_seconds)).isoformat()
        super().__init__(message)


DEFAULT_MODELS = {
    'anthropic': 'claude-sonnet-4-20250514',
    'openai': 'gpt-4o-mini',
    'gemini': 'gemini-2.5-flash',
    'openrouter': 'openai/gpt-4o-mini',
}


def call_ai(provider, api_key, model, system_prompt, user_prompt, api_keys=None):
    """Call AI with automatic fallback across multiple API keys.

    Parameters:
        api_keys: Optional list of API keys to try in order. If provided,
                  overrides single api_key for fallback logic.
    """
    if provider not in DEFAULT_MODELS:
        raise AIClientError('Provider AI tidak didukung.')
    keys_to_try = list(dict.fromkeys(k.strip() for k in (api_keys or [api_key]) if isinstance(k, str) and k.strip()))
    if not keys_to_try:
        raise AIClientError('API key tidak boleh kosong.')
    model = model or DEFAULT_MODELS[provider]
    quota_errors = []
    for index, key in enumerate(keys_to_try):
        try:
            result = _call_provider(provider, key, model, system_prompt, user_prompt)
            if not isinstance(result, str) or not result.strip():
                raise AIClientError('AI mengembalikan respons kosong. Coba lagi nanti.')
            return result.strip()
        except QuotaExceededError as error:
            quota_errors.append(error)
        except AIClientError:
            if index == len(keys_to_try) - 1:
                raise
    resets = [error.reset_in_seconds for error in quota_errors if error.reset_in_seconds]
    raise QuotaExceededError(
        f'Batas permintaan atau kuota {provider} tercapai untuk {len(quota_errors)} API key. Coba lagi nanti atau periksa kuota provider.',
        min(resets) if resets else None, len(quota_errors), len(keys_to_try),
    )


def _raise_http_error(response, provider):
    status = response.status_code
    if status == 429:
        retry_after = response.headers.get('Retry-After', '')
        try:
            retry_after = max(0, int(retry_after)) or None
        except (TypeError, ValueError):
            retry_after = None
        raise QuotaExceededError(f'Batas permintaan atau kuota {provider} tercapai.', retry_after)
    if status in (401, 403):
        raise AIClientError(f'API key {provider} tidak valid atau tidak memiliki akses.')
    if status == 404:
        raise AIClientError(f'Model {provider} tidak ditemukan atau tidak dapat diakses.')
    if status >= 500:
        raise AIClientError(f'Layanan {provider} sedang bermasalah. Coba lagi nanti.')
    if status != 200:
        raise AIClientError(f'Permintaan ke {provider} ditolak (HTTP {status}). Periksa model dan konfigurasi.')


def _call_provider(provider, api_key, model, system_prompt, user_prompt):
    """Dispatch to the correct provider implementation."""
    try:
        if provider == 'anthropic':
            return _call_anthropic(api_key, model, system_prompt, user_prompt)
        elif provider == 'openai':
            return _call_openai(api_key, model, system_prompt, user_prompt)
        elif provider == 'gemini':
            return _call_gemini(api_key, model, system_prompt, user_prompt)
        elif provider == 'openrouter':
            return _call_openrouter(api_key, model, system_prompt, user_prompt)
        else:
            raise AIClientError(f"Provider '{provider}' tidak didukung.")
    except AIClientError:
        raise
    except requests.Timeout:
        raise AIClientError('Permintaan AI melewati batas waktu. Coba lagi nanti.') from None
    except requests.RequestException:
        raise AIClientError('Tidak dapat terhubung ke layanan AI. Periksa koneksi dan coba lagi.') from None
    except Exception as error:
        status = getattr(error, 'status_code', None)
        if status == 429:
            raise QuotaExceededError(f'Batas permintaan atau kuota {provider} tercapai.') from None
        if status in (401, 403):
            raise AIClientError(f'API key {provider} tidak valid atau tidak memiliki akses.') from None
        raise AIClientError('Layanan AI gagal memproses permintaan atau mengembalikan respons yang tidak valid.') from None


def _call_anthropic(api_key, model, system_prompt, user_prompt):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=0)
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system_prompt,
        messages=[{'role': 'user', 'content': user_prompt}],
    )
    return message.content[0].text


def _call_openai(api_key, model, system_prompt, user_prompt):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'max_tokens': 2048,
    }
    resp = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers=headers,
        json=payload,
        timeout=60,
    )
    _raise_http_error(resp, 'openai')
    data = resp.json()
    return data['choices'][0]['message']['content']


def _call_gemini(api_key, model, system_prompt, user_prompt):
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    payload = {
        'system_instruction': {
            'parts': [{'text': system_prompt}]
        },
        'contents': [{
            'parts': [{'text': user_prompt}]
        }],
        'generationConfig': {
            'maxOutputTokens': 4096,
            'temperature': 0.4,
        },
    }
    resp = requests.post(url, headers={'x-goog-api-key': api_key}, json=payload, timeout=60)
    _raise_http_error(resp, 'gemini')
    data = resp.json()
    candidates = data.get('candidates', [])
    if not candidates:
        raise AIClientError('Gemini: tidak ada kandidat respons.')
    parts = candidates[0].get('content', {}).get('parts', [])
    return ''.join(p.get('text', '') for p in parts)


def _call_openrouter(api_key, model, system_prompt, user_prompt):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'max_tokens': 2048,
    }
    resp = requests.post(
        'https://openrouter.ai/api/v1/chat/completions',
        headers=headers,
        json=payload,
        timeout=60,
    )
    _raise_http_error(resp, 'openrouter')
    data = resp.json()
    return data['choices'][0]['message']['content']
