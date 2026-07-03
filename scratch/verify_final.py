import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app

with app.test_client() as c:
    with c.session_transaction() as s:
        s['user_id'] = 1

    r = c.get('/dashboard/ecommerce.csv', follow_redirects=True)
    html = r.data.decode('utf-8')

    checks = [
        ('Plotly chart',       'ov-missing-chart' in html),
        ('Outlier (Raw)',      'Outlier (Raw)' in html),
        ('Outlier (Cleaned)',  'Outlier (Cleaned)' in html),
        ('Data Quality Overview', 'Data Quality Overview' in html),
        ('No error',           '500 Internal Server Error' not in html),
    ]
    for name, ok in checks:
        status = 'OK' if ok else 'FAIL'
        print(f'  {name}: {status}')
