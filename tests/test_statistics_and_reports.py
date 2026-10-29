import io
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from PIL import Image as PillowImage
from pypdf import PdfReader

from backend.advanced_stats import get_advanced_stats
from backend.cleaning_engine import get_quality_report
from backend.data_sanitizer import clean_and_parse_numeric, safe_iqr_outliers, sanitize_series
from backend.descriptive_stats import get_descriptive_stats, get_summary_metrics
from backend.insights_generator import _outlier_count
from backend.report_chart_builder import build_report_charts
from backend.report_generator import generate_pdf_report


class StatisticsTests(unittest.TestCase):
    def test_known_descriptive_values(self):
        frame = pd.DataFrame({'value': [1, 2, 3, 4, None], 'group': ['A', 'A', 'B', None, 'B']})
        numeric, categorical = get_descriptive_stats(frame, ['value'], ['group'])
        row = numeric[0]
        self.assertEqual(row['Mean'], 2.5)
        self.assertEqual(row['Median'], 2.5)
        self.assertEqual(row['Variance'], 1.67)
        self.assertEqual(row['Std Dev'], 1.29)
        self.assertEqual(row['Missing Count'], 1)
        self.assertEqual(row['Outliers'], 0)
        self.assertEqual(categorical[0]['Mode Freq'], 2)
        self.assertEqual(categorical[0]['Mode %'], '50.0%')
        self.assertEqual(get_summary_metrics(frame)['missing_cells'], '2')

    def test_scientific_notation_is_not_reinterpreted_as_digits(self):
        for source, expected in [('1e3', 1000.0), ('-2.5E-2', -0.025), ('Rp 1.234,50', 1234.5)]:
            with self.subTest(source=source):
                self.assertAlmostEqual(clean_and_parse_numeric(source), expected)

    def test_nonfinite_values_excluded_from_statistics(self):
        result = sanitize_series(pd.Series([1, 3, np.inf, -np.inf, np.nan]))
        self.assertEqual(result.tolist(), [1, 3])
        stats, _ = get_descriptive_stats(pd.DataFrame({'x': [1, 3, np.inf]}), ['x'], [])
        self.assertEqual(stats[0]['Mean'], 2.0)

    def test_zero_iqr_outlier_consistent_across_modules(self):
        series = pd.Series([1, 1, 1, 1, 100])
        self.assertEqual(safe_iqr_outliers(series)[-1], 1)
        self.assertEqual(_outlier_count(series), 1)
        stats, _ = get_descriptive_stats(series.to_frame('x'), ['x'], [])
        self.assertEqual(stats[0]['Outliers'], 1)
        self.assertEqual(get_quality_report(series.to_frame('x'))['summary']['total_outliers'], 1)
        self.assertEqual(safe_iqr_outliers(pd.Series([5, 5, 5, 5]))[-1], 0)

    def test_advanced_quantiles_and_correlation(self):
        result = get_advanced_stats(pd.DataFrame({'x': [1, 2, 3, 4], 'y': [2, 4, 6, 8]}), ['x', 'y'], [])
        self.assertEqual(result['top_corr_pairs'][0][2], 1.0)
        row = result['adv_num'][0]
        self.assertEqual(row['Q1'], 1.75)
        self.assertEqual(row['Q3'], 3.25)
        self.assertEqual(row['IQR'], 1.5)


class ReportTests(unittest.TestCase):
    def test_pdf_explains_when_chart_images_are_unavailable(self):
        frame = pd.DataFrame({'value': [1, 2, 3, 4]})
        numeric, categorical = get_descriptive_stats(frame, ['value'], [])
        document = io.BytesIO()
        generate_pdf_report(
            document, 'sample.csv', frame, get_quality_report(frame),
            get_summary_metrics(frame), numeric, categorical, [], [], {},
            selected_sections=['visualisasi'], chart_images={},
            num_cols=['value'], cat_cols=[],
        )
        text = '\n'.join(page.extract_text() or '' for page in PdfReader(document).pages)
        self.assertIn('Visualisasi tidak dapat ditampilkan', text)

    def test_heatmap_contains_correlation_trace(self):
        charts_seen = []

        def capture(figure, **kwargs):
            charts_seen.append(figure)
            return io.BytesIO(b'test-image')

        frame = pd.DataFrame({'x': [1, 2, 3, 4], 'y': [2, 4, 6, 8]})
        with patch('backend.report_chart_builder.plotly_fig_to_png_bytes', side_effect=capture):
            charts = build_report_charts(frame, ['x', 'y'], [], [], max_numeric=0)
        self.assertIn('heatmap_all', charts)
        self.assertEqual(charts_seen[0]['data'][0]['type'], 'heatmap')

    def test_pdf_embeds_image_and_statistics(self):
        frame = pd.DataFrame({'value': [1, 2, 3, 4], 'group': ['A', 'A', 'B', 'B']})
        numeric, categorical = get_descriptive_stats(frame, ['value'], ['group'])
        image = io.BytesIO()
        PillowImage.new('RGB', (400, 240), 'white').save(image, format='PNG')
        document = io.BytesIO()
        generate_pdf_report(
            document, 'sample.csv', frame, get_quality_report(frame),
            get_summary_metrics(frame), numeric, categorical, [], [], {},
            chart_images={'histogram_value': image.getvalue()},
            num_cols=['value'], cat_cols=['group'],
        )
        reader = PdfReader(document)
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        self.assertIn('sample.csv', text)
        self.assertIn('value', text)
        self.assertIn('2.5', text)
        self.assertNotIn('Gambar tidak dapat ditampilkan', text)
        self.assertTrue(any(page.images for page in reader.pages))


if __name__ == '__main__':
    unittest.main()
