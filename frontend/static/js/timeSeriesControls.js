/* ============================================================
   DS Generator — timeSeriesControls.js
   Time Series column/granularity dynamic controls
   ============================================================ */
(function () {
  'use strict';

  function reloadTimeSeries() {
    var dtCol  = document.getElementById('ts-categorical-dim')?.value;
    var numCol = document.getElementById('ts-numerical-val')?.value;
    var freq   = document.getElementById('ts-freq-select')?.value;
    var theme  = document.body.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';

    var filename = window.vizMeta?.filename;
    if (!filename) return;

    var url = '/api/ts-chart/' + encodeURIComponent(filename)
      + '?dt_col=' + encodeURIComponent(dtCol || '')
      + '&num_col=' + encodeURIComponent(numCol || '')
      + '&freq=' + encodeURIComponent(freq || '')
      + '&theme=' + theme
      + '&chart_type=ts_combined&dim_type=datetime&dim_col=' + encodeURIComponent(dtCol || '');

    showTsLoading(true);

    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        showTsLoading(false);
        if (!data.ok) {
          showToast(data.error || 'Failed to load Time Series', 'error');
          return;
        }
        if (data.chart) {
          var el = document.getElementById('plot-ts-line');
          if (el && typeof Plotly !== 'undefined') {
            var layout = Object.assign({}, data.chart.layout || {}, {
              paper_bgcolor: 'rgba(0,0,0,0)',
              plot_bgcolor: 'rgba(0,0,0,0)',
              autosize: true,
              margin: { l: 48, r: 20, t: 52, b: 48 },
              font: {
                color: document.body.getAttribute('data-theme') === 'dark' ? 'var(--text-secondary)' : 'var(--text)',
                family: 'Inter, sans-serif',
                size: 11,
              },
              hoverlabel: {
                bgcolor: 'var(--bg)',
                bordercolor: 'var(--blue-light)',
                font: { color: 'var(--text)', size: 12 },
              },
              xaxis: {
                gridcolor: document.body.getAttribute('data-theme') === 'dark' ? 'rgba(255,255,255,0.06)' : 'var(--border)'
              },
              yaxis: {
                gridcolor: document.body.getAttribute('data-theme') === 'dark' ? 'rgba(255,255,255,0.06)' : 'var(--border)'
              }
            });
            Plotly.react(el, data.chart.data, layout, { responsive: true });
          }
        }
        if (data.meta) {
          updateTsCombinedKpis(data.meta);
        }
      })
      .catch(function (err) {
        showTsLoading(false);
        showToast('Error loading Time Series chart', 'error');
        console.error(err);
      });
  }

  function showTsLoading(show) {
    var areas = document.querySelectorAll('#ts-line .chart-area');
    areas.forEach(function (el) {
      if (show) {
        el.style.opacity = '0.5';
        el.style.pointerEvents = 'none';
      } else {
        el.style.opacity = '1';
        el.style.pointerEvents = '';
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    ['ts-categorical-dim', 'ts-numerical-val', 'ts-freq-select'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('change', reloadTimeSeries);
    });
  });
})();
