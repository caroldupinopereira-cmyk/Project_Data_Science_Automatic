import json
import os
import unittest
from unittest.mock import Mock, patch

import requests

import app as web
from backend import ai_client as client, ai_settings as settings
from backend.interpretation_generator import build_dataset_context_text, generate_interpretation


CONTEXT = {
    'is_cleaned': True,
    'metrics': {'total_rows': '10', 'total_columns': '3', 'num_count': 2, 'cat_count': 1, 'missing_cells': '4'},
    'quality_full': {'summary': {'missing_cells': 4, 'missing_pct': 13.33, 'duplicate_rows': 2}},
    'num_stats': [{'Column': 'amount', 'Mean': 25}],
}
SETTINGS = {'provider': 'gemini', 'api_key': 'test-key', 'model': 'test-model'}


class AIClientTests(unittest.TestCase):
    def response(self, status=200, payload=None, headers=None):
        return Mock(status_code=status, headers=headers or {}, json=Mock(return_value=payload))

    def test_http_errors_and_retry_information_for_all_http_providers(self):
        for provider in ('openai', 'gemini', 'openrouter'):
            with self.subTest(provider=provider), patch.object(client.requests, 'post', return_value=self.response(429, headers={'Retry-After': '45'})):
                with self.assertRaises(client.QuotaExceededError) as raised:
                    client.call_ai(provider, 'test-key', '', 'system', 'message')
                self.assertEqual(raised.exception.reset_in_seconds, 45)
                self.assertIn(provider, str(raised.exception))
                self.assertNotIn('tengah malam', str(raised.exception))

    def test_fallback_keys_are_deduplicated(self):
        with patch.object(client, '_call_provider', side_effect=[client.QuotaExceededError('limit'), 'ok']) as call:
            self.assertEqual(client.call_ai('gemini', 'a', '', '', '', api_keys=['a', 'a', 'b']), 'ok')
            self.assertEqual(call.call_count, 2)
            self.assertEqual(call.call_args.args[1], 'b')

    def test_network_errors_do_not_disclose_api_key(self):
        for error in (requests.Timeout('secret-key'), requests.ConnectionError('url?key=secret-key')):
            with self.subTest(error=type(error).__name__), patch.object(client.requests, 'post', side_effect=error):
                with self.assertRaises(client.AIClientError) as raised:
                    client.call_ai('gemini', 'secret-key', '', '', '')
                self.assertNotIn('secret-key', str(raised.exception))

    def test_authentication_and_empty_responses(self):
        with patch.object(client.requests, 'post', return_value=self.response(401)):
            with self.assertRaisesRegex(client.AIClientError, 'API key'):
                client.call_ai('openai', 'test-key', '', '', '')
        with patch.object(client.requests, 'post', return_value=self.response(payload={'candidates': []})):
            with self.assertRaises(client.AIClientError):
                client.call_ai('gemini', 'test-key', '', '', '')
        with patch.object(client, '_call_provider', return_value='   '):
            with self.assertRaisesRegex(client.AIClientError, 'kosong'):
                client.call_ai('openrouter', 'test-key', '', '', '')

    def test_model_not_reused_when_provider_changes(self):
        with patch.object(settings, '_load_env'), patch.dict(os.environ, {
            'AI_PROVIDER': 'gemini', 'AI_MODEL': 'gemini-custom', 'OPENAI_API_KEY': 'test-key',
        }, clear=True):
            result = settings.get_default_settings()
            self.assertEqual(result['provider'], 'openai')
            self.assertEqual(result['model'], client.DEFAULT_MODELS['openai'])

    def test_numbered_key_without_primary_and_masking(self):
        with patch.object(settings, '_load_env'), patch.dict(os.environ, {
            'AI_PROVIDER': 'gemini', 'GEMINI_API_KEY_2': 'test-key',
        }, clear=True):
            self.assertEqual(settings.get_default_settings()['api_key'], 'test-key')
        self.assertNotEqual(settings.get_masked_api_key('short'), 'short')


class AIContextTests(unittest.TestCase):
    def test_current_statistics_and_quality_fields(self):
        text = build_dataset_context_text(CONTEXT)
        for expected in ('Data state: cleaned', 'Numeric cols: 2', 'Categorical cols: 1',
                         'Missing values: 4, Duplicates: 2', 'missing_pct=13.33%', 'mean=25'):
            self.assertIn(expected, text)

    def test_response_schema_is_validated(self):
        for value in ([], None, {'summary': 'incomplete'}, {'summary': [], 'conclusion': '', 'key_findings': [], 'recommendations': []}):
            with self.subTest(value=value), patch('backend.interpretation_generator.call_ai', return_value=json.dumps(value)):
                with self.assertRaises(client.AIClientError):
                    generate_interpretation(CONTEXT, 'id', SETTINGS)

    def test_valid_fenced_response(self):
        value = {'summary': '**Summary**', 'conclusion': 'Conclusion', 'key_findings': ['Finding'], 'recommendations': ['Action']}
        with patch('backend.interpretation_generator.call_ai', return_value='```json\n' + json.dumps(value) + '\n```'):
            self.assertEqual(generate_interpretation(CONTEXT, 'en', SETTINGS)['summary'], 'Summary')


class AIEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = web.app.test_client()
        with self.client.session_transaction() as session:
            session.update(user_id='ai-test', username='Tester')

    def test_chat_uses_server_context(self):
        with patch('app._get_dashboard_context', return_value=CONTEXT), patch('app.get_ai_settings', return_value=SETTINGS), patch('backend.ai_client.call_ai', return_value='Answer') as call:
            response = self.client.post('/api/ai-chat', json={'message': 'Analyze', 'filename': 'sample.csv', 'context': 'FORGED CONTEXT'})
            self.assertEqual(response.status_code, 200)
            self.assertIn('mean=25', call.call_args.args[3])
            self.assertNotIn('FORGED CONTEXT', call.call_args.args[3])

    def test_chat_request_validation(self):
        for payload in (None, [], {}, {'message': ' ', 'filename': 'sample.csv'}, {'message': 'Hi', 'filename': '../sample.csv'}):
            with self.subTest(payload=payload):
                response = self.client.post('/api/ai-chat', json=payload)
                self.assertEqual(response.status_code, 400)

    def test_dataset_access_checked_before_ai_call(self):
        with patch('app._get_dashboard_context', return_value=None), patch('backend.ai_client.call_ai') as call:
            self.assertEqual(self.client.post('/api/ai-chat', json={'message': 'Hi', 'filename': 'other.csv'}).status_code, 404)
            call.assert_not_called()

    def test_interpretation_quota_uses_exception_type(self):
        with patch('app._get_dashboard_context', return_value=CONTEXT), patch('app.get_ai_settings', return_value=SETTINGS), patch('app.generate_interpretation', side_effect=client.QuotaExceededError('Batas permintaan tercapai.', 30)):
            response = self.client.post('/api/interpretation/sample.csv?lang=id')
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.get_json()['error'], 'quota_exceeded')
            self.assertEqual(response.get_json()['reset_in_seconds'], 30)


if __name__ == '__main__':
    unittest.main()
