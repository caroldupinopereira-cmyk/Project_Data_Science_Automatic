import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pandas as pd

import app as web
from backend import cleaning_engine as engine


class RuntimeRegressionTests(unittest.TestCase):
    def test_public_pages(self):
        with web.app.test_client() as client:
            for url in ('/', '/auth/login', '/auth/register'):
                with self.subTest(url=url):
                    self.assertEqual(client.get(url).status_code, 200)

    def test_caches_are_scoped_to_user(self):
        filename = f'{uuid4().hex}.csv'
        with web.app.test_request_context('/'):
            web.session.update(user_id='regression-one', username='One')
            web._set_cached_ctx(filename, {'owner': 'one'})
            web._set_cached_charts(filename, {'chart': 'one'})
            web.session.update(user_id='regression-two', username='Two')
            self.assertIsNone(web._get_cached_ctx(filename))
            self.assertIsNone(web._get_cached_charts(filename))
            web.session.update(user_id='regression-one', username='One')
            self.assertEqual(web._get_cached_ctx(filename)['owner'], 'one')
            web._invalidate_ctx_cache(filename)
            self.assertIsNone(web._get_cached_charts(filename))

    def test_cleaned_filename_and_dashboard_session_restore(self):
        # Use a normal directory: Windows sandbox ACLs may reject mkdtemp dirs.
        directory = Path(__file__).resolve().parent / f'runtime_{uuid4().hex}'
        directory.mkdir()
        key = f'regression::{uuid4().hex}.xlsx'
        output = directory / (Path(key.rsplit('::', 1)[-1]).stem + '_cleaned.csv')
        try:
            frame = pd.DataFrame({'value': [10.0, 20.0, 30.0]})
            cleaning = engine.reset_session(key, frame)
            self.assertTrue(cleaning.apply_step(
                'normalize', {'method': 'minmax', 'columns': ['value']}
            )['ok'])
            self.assertTrue(engine.save_cleaned_to_disk(key, str(directory)))
            self.assertEqual(pd.read_csv(output)['value'].max(), 1.0)
            with patch.object(engine, 'SESSIONS_DIR', str(directory)):
                engine.persist_session(key)
                engine.delete_session(key)
                with web.app.test_request_context('/'):
                    web.session.update(user_id='regression', username='Test')
                    with patch('app._user_upload_dir', return_value=str(directory)):
                        restored, error = web._get_or_init_session(key.split('::')[1])
                self.assertIsNone(error)
                self.assertTrue(restored.is_cleaned)
                self.assertEqual(restored.df_current['value'].max(), 1.0)
        finally:
            engine.delete_session(key)
            for file in directory.iterdir():
                file.unlink()
            directory.rmdir()


if __name__ == '__main__':
    unittest.main()
