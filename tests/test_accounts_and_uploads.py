import io
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import app as web
from backend import auth, cleaning_engine, models, user_data
from backend.data_loader import load_data


class AccountsAndUploadsTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(__file__).resolve().parent / f'runtime_{uuid4().hex}'
        self.directory.mkdir()
        self.users_file = self.directory / 'accounts.json'
        self.users_file.write_text('[]', encoding='utf-8')
        self.patches = [
            patch.object(models, 'DATA_DIR', str(self.directory)),
            patch.object(models, 'USERS_FILE', str(self.users_file)),
            patch.object(user_data, 'USERS_ROOT', str(self.directory / 'users')),
            patch.object(cleaning_engine, 'SESSIONS_DIR', str(self.directory / 'sessions')),
        ]
        for item in self.patches:
            item.start()
        self.client = web.app.test_client()
        auth._login_attempts.clear()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        # Only remove this test's verified directory, never account data.
        root = Path(__file__).resolve().parent
        self.assertEqual(self.directory.parent, root)
        self.assertTrue(self.directory.name.startswith('runtime_'))
        shutil.rmtree(self.directory)
        web._ctx_cache.clear()
        web._chart_cache.clear()
        web._custom_html_cache.clear()
        cleaning_engine._sessions.clear()

    def csrf(self, client=None):
        client = client or self.client
        client.get('/auth/login')
        with client.session_transaction() as session:
            return {'X-CSRF-Token': session['_csrf_token']}

    def register(self, client=None, username='Analyst'):
        client = client or self.client
        response = client.post('/auth/register', headers=self.csrf(client), json={
            'username': username, 'email': username + '@example.com',
            'password': 'test-password', 'confirm_password': 'test-password',
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response

    def upload(self, content, name='dataset.csv', client=None):
        return (client or self.client).post('/upload', data={
            'file': (io.BytesIO(content), name),
        }, headers={'X-Requested-With': 'XMLHttpRequest'})

    def test_old_login_requires_password_and_csrf(self):
        response = self.client.post('/login', data={'name': 'Anyone'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get('/upload').status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)
            session['user'] = {'id': 'old-session', 'name': 'Anyone'}
        self.assertEqual(self.client.get('/timeseries/dataset.csv').status_code, 302)
        self.assertEqual(self.client.get('/api/cleaning/status/dataset.csv').status_code, 401)

    def test_register_login_remember_and_both_logout_urls(self):
        self.register()
        self.client.get('/logout')
        response = self.client.post('/login', headers=self.csrf(), json={
            'login': 'Analyst', 'password': 'test-password', 'remember': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(self.client.get_cookie('remember_token'))
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.get('/upload').status_code, 200)
        response = self.client.get('/auth/logout')
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.client.get_cookie('remember_token'))
        self.assertEqual(self.client.get('/upload').status_code, 302)
        self.assertIsNone(models.user_model._read()[0]['remember_token'])

    def test_social_account_password_login_returns_error(self):
        models.user_model.create_user_oauth('Social', 'social@example.com', 'google', 'id')
        response = self.client.post('/auth/login', headers=self.csrf(), json={
            'login': 'Social', 'password': 'test-password',
        })
        self.assertEqual(response.status_code, 401)

    def test_empty_corrupt_and_inconsistent_uploads_are_rejected(self):
        self.register()
        cases = [(b'', 'empty.csv'), (b'value\n', 'header.csv'),
                 (b'not an excel archive', 'broken.xlsx'),
                 (b'a,b\n1,2\n3,4,5\n', 'broken.csv')]
        for content, name in cases:
            with self.subTest(name=name):
                response = self.upload(content, name)
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.get_json())
                with self.client.session_transaction() as session:
                    upload_dir = user_data.get_upload_dir(session['user_id'], session['username'])
                self.assertFalse((Path(upload_dir) / name).exists())

    def test_upload_dashboard_cleaning_undo_and_exports(self):
        self.register()
        response = self.upload(b'category,value,amount\nA,10,2\nB,20,4\nA,30,6\nB,40,8\nA,50,10\nB,60,12\n')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(response.get_json()['redirect']).status_code, 200)
        for kind in ('csv', 'excel', 'json'):
            self.assertEqual(self.client.get('/dashboard/dataset.csv/export/' + kind).status_code, 200)
        response = self.client.post('/api/cleaning/apply/dataset.csv', json={
            'op_type': 'normalize', 'op_params': {'method': 'minmax', 'columns': ['value']},
        })
        self.assertTrue(response.get_json()['ok'])
        with self.client.session_transaction() as session:
            user_id, username = session['user_id'], session['username']
        output = Path(user_data.get_cleaned_dir(user_id, username)) / 'dataset_cleaned.csv'
        self.assertTrue(output.is_file())
        cleaning_engine._sessions.clear()
        web._ctx_cache.clear()
        self.assertEqual(self.client.get(
            '/api/viz-chart/dataset.csv?category=numerical&chart_type=histogram&col_x=value'
        ).status_code, 200)
        restored = cleaning_engine.get_session(user_id + '::dataset.csv')
        self.assertEqual(restored.df_current['value'].max(), 1.0)
        cleaning_engine._sessions.clear()
        self.assertEqual(self.client.get('/dashboard/dataset.csv').status_code, 200)
        restored = cleaning_engine.get_session(user_id + '::dataset.csv')
        self.assertEqual(restored.df_current['value'].max(), 1.0)
        self.assertTrue(restored._history[-1].summary['log'])
        response = self.client.post('/api/cleaning/undo/dataset.csv', json={})
        self.assertTrue(response.get_json()['ok'])
        self.assertFalse(output.exists())
        history = user_data.get_user_history(user_id, username)
        self.assertEqual(history['events'][0]['type'], 'cleaning')

    def test_reset_clears_saved_cleaned_data_and_survives_restart(self):
        self.register()
        self.upload(b'value\n10\n20\n30\n')
        self.client.post('/api/cleaning/apply/dataset.csv', json={
            'op_type': 'normalize', 'op_params': {'method': 'minmax', 'columns': ['value']},
        })
        self.assertTrue(self.client.post('/api/cleaning/reset/dataset.csv').get_json()['ok'])
        cleaning_engine._sessions.clear()
        exported = self.client.get('/dashboard/dataset.csv/export/csv')
        self.assertIn(b'30', exported.data)

    def test_same_filename_isolated_for_two_accounts(self):
        self.register()
        self.upload(b'value\n10\n20\n')
        self.client.get('/dashboard/dataset.csv')
        other = web.app.test_client()
        self.register(other, 'Other')
        self.assertEqual(other.get('/dashboard/dataset.csv/export/csv').status_code, 302)
        self.upload(b'value\n100\n200\n', client=other)
        self.assertEqual(other.get('/dashboard/dataset.csv').status_code, 200)
        exported = other.get('/dashboard/dataset.csv/export/csv').data.decode('utf-8-sig')
        self.assertIn('100', exported)
        self.assertNotIn('\n10\n', exported)

    def test_username_cannot_escape_user_storage(self):
        path = Path(user_data.get_user_dir('valid-user-id', '../../outside'))
        self.assertEqual(path.parent, Path(user_data.USERS_ROOT).resolve())
        with self.assertRaises(ValueError):
            user_data.get_user_dir('../../outside', 'Analyst')

    def test_single_column_delimiters_and_legacy_encoding(self):
        for name, content, columns in [
            ('one.csv', b'name\nAnna\nBen\n', ['name']),
            ('semi.csv', b'name;value\nAnna;1\nBen;2\n', ['name', 'value']),
            ('latin.csv', 'name,value\nAndr\u00e9,1\n'.encode('latin1'), ['name', 'value']),
        ]:
            file = self.directory / name
            file.write_bytes(content)
            result = load_data(file, strict=True)
            self.assertEqual(result.columns.tolist(), columns)


if __name__ == '__main__':
    unittest.main()
