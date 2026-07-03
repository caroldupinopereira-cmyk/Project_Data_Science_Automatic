'use strict';

/**
 * dashboardOverview.js — v2 (with state management)
 *
 * Perubahan utama:
 *  - Klik chart slot → simpan state (category, chartType, col) ke sessionStorage
 *    sebelum pindah ke tab Visualizations.
 *  - VizMaster membaca state dari sessionStorage saat tab dibuka.
 *  - Binary decode lengkap (parcoords, splom, marker.size, line.color).
 *  - Toggle title header ikut update saat dropdown berubah.
 */

var OverviewDashboard = (function () {
    var data     = null;
    var rendered = new Set();

    var PLOTLY_CFG = {
        responsive     : true,
        displayModeBar : false,
        displaylogo    : false,
        scrollZoom     : false,
    };

    // ── Peta slot → {category, chartType} untuk state management ─────────────
    var SLOT_VIZ_STATE = {
        'ov_hbar'        : { category: 'categorical', chartType: 'pareto'    },
        'ov_center'      : { category: 'categorical', chartType: 'pie'       },
        'ov_vbar_left'   : { category: 'numerical',   chartType: 'histogram' },
        'ov_area_bottom' : { category: 'numerical',   chartType: 'boxplot'   },
        'ov_vbar_right'  : { category: 'categorical', chartType: 'bar'       },
    };

    var SLOT_TITLE_PREFIX = {
        'ov_hbar'        : 'Pareto — ',
        'ov_center'      : 'Composition — ',
        'ov_vbar_left'   : 'Distribution — ',
        'ov_area_bottom' : 'Spread — ',
        'ov_vbar_right'  : 'Frequency — ',
    };

    // ── State management key ─────────────────────────────────────────────────
    var VIZ_STATE_KEY = 'ds_viz_state';

    function _saveVizState(category, chartType, colX, colY) {
        try {
            sessionStorage.setItem(VIZ_STATE_KEY, JSON.stringify({
                category  : category  || null,
                chartType : chartType || null,
                colX      : colX      || null,
                colY      : colY      || null,
                ts        : Date.now(),
            }));
        } catch (e) {}
    }

    function readVizState() {
        try {
            var raw = sessionStorage.getItem(VIZ_STATE_KEY);
            if (!raw) return null;
            var state = JSON.parse(raw);
            // Expire setelah 5 menit (state yang terlalu lama diabaikan)
            if (Date.now() - (state.ts || 0) > 5 * 60 * 1000) {
                sessionStorage.removeItem(VIZ_STATE_KEY);
                return null;
            }
            return state;
        } catch (e) {
            return null;
        }
    }

    function clearVizState() {
        try { sessionStorage.removeItem(VIZ_STATE_KEY); } catch (e) {}
    }

    // ── Layout patch ──────────────────────────────────────────────────────────
    function getLayoutPatch() {
        var dark = document.body.getAttribute('data-theme') === 'dark';
        return {
            paper_bgcolor : 'rgba(0,0,0,0)',
            plot_bgcolor  : 'rgba(0,0,0,0)',
            font          : {
                color  : dark ? '#c8d8f0' : '#2b3674',
                family : 'Inter, sans-serif',
                size   : 11,
            },
            margin    : { l: 44, r: 16, t: 38, b: 38 },
            hoverlabel: {
                bgcolor    : 'rgba(10,18,48,0.93)',
                bordercolor: 'rgba(100,160,235,0.45)',
                font       : { color: '#e8f4fc', size: 12 },
            },
        };
    }

    // ── Binary decode ──────────────────────────────────────────────────────────
    function _decodeBinaryField(field) {
        if (!field || typeof field !== 'object' || !field.bdata) return field;
        var dtype  = field.dtype || 'f8';
        var binary = atob(field.bdata);
        var len    = binary.length;
        var buf    = new ArrayBuffer(len);
        var view   = new Uint8Array(buf);
        for (var i = 0; i < len; i++) view[i] = binary.charCodeAt(i);
        var arr;
        if      (dtype === 'f8') arr = new Float64Array(buf);
        else if (dtype === 'f4') arr = new Float32Array(buf);
        else if (dtype === 'i4') arr = new Int32Array(buf);
        else if (dtype === 'i2') arr = new Int16Array(buf);
        else if (dtype === 'u4') arr = new Uint32Array(buf);
        else if (dtype === 'u1') arr = new Uint8Array(buf);
        else                     arr = new Float64Array(buf);
        return Array.from(arr);
    }

    function _decodeTrace(trace) {
        if (!trace || typeof trace !== 'object') return trace;
        var decoded = Object.assign({}, trace);

        // Decode scalar array fields
        ['x', 'y', 'z', 'values', 'labels', 'ids',
         'open', 'high', 'low', 'close', 'lat', 'lon'].forEach(function (f) {
            if (decoded[f] && typeof decoded[f] === 'object' && decoded[f].bdata) {
                decoded[f] = _decodeBinaryField(decoded[f]);
            }
        });

        // marker.size / marker.color
        if (decoded.marker && typeof decoded.marker === 'object') {
            decoded.marker = Object.assign({}, decoded.marker);
            ['size', 'color'].forEach(function(k) {
                if (decoded.marker[k] && typeof decoded.marker[k] === 'object' && decoded.marker[k].bdata) {
                    decoded.marker[k] = _decodeBinaryField(decoded.marker[k]);
                }
            });
        }

        // parcoords / splom dimensions
        if ((decoded.type === 'parcoords' || decoded.type === 'splom') &&
             Array.isArray(decoded.dimensions)) {
            decoded.dimensions = decoded.dimensions.map(function (dim) {
                if (!dim || typeof dim !== 'object') return dim;
                var d = Object.assign({}, dim); d
                if (d.values && typeof d.values === 'object' && d.values.bdata) {
                    d.values = _decodeBinaryField(d.values);
                }
                return d;
            });
        }

        // line.color
        if (decoded.line && typeof decoded.line === 'object') {
            decoded.line = Object.assign({}, decoded.line);
            if (decoded.line.color && typeof decoded.line.color === 'object' && decoded.line.color.bdata) {
                decoded.line.color = _decodeBinaryField(decoded.line.color);
            }
        }

        return decoded;
    }

    function _decodeChartData(chartObj) {
        if (!chartObj || !Array.isArray(chartObj.data)) return chartObj;
        return Object.assign({}, chartObj, {
            data: chartObj.data.map(_decodeTrace),
        });
    }

    // ── Draw single slot ──────────────────────────────────────────────────────
    function drawSlot(slotId, chartJson, force) {
        if (!chartJson || typeof Plotly === 'undefined') return;
        var el = document.getElementById(slotId);
        if (!el) return;

        if (!force && rendered.has(slotId)) {
            Plotly.Plots.resize(el);
            return;
        }

        var decoded = _decodeChartData(chartJson);
        var layout  = Object.assign({}, decoded.layout || {}, getLayoutPatch());

        try { Plotly.purge(el); } catch (e) {}
        el.innerHTML = '';

        Plotly.react(el, decoded.data || [], layout, PLOTLY_CFG)
            .then(function () { rendered.add(slotId); })
            .catch(function (err) {
                console.warn('[Overview] Chart render failed:', slotId, err);
            });
    }

    function renderAll() {
        if (!data || !data.slots) return;
        Object.keys(data.slots).forEach(function (key) {
            var slot = data.slots[key];
            if (slot && slot.visible && slot.chart) {
                drawSlot(key, slot.chart, false);
            }
        });
    }

    // ── Stats Preview Tables ──────────────────────────────────────────────────
    function renderStatsPreview() {
        if (!data || !data.stats_preview) return;
        var sp = data.stats_preview;

        var numWrap = document.getElementById('ov-stats-num-wrap');
        if (numWrap && sp.num && sp.num.length > 0) {
            var numHtml =
                '<table class="ov-stats-table"><thead><tr>' +
                '<th>Column</th><th>Mean</th><th>Median</th>' +
                '<th>Std</th><th>Min</th><th>Max</th>' +
                '<th>Outliers</th><th>Missing</th>' +
                '</tr></thead><tbody>';
            sp.num.forEach(function (r) {
                var outCls = r.outliers > 0 ? 'ov-td-warn' : '';
                var misCls = r.missing  > 0 ? 'ov-td-warn' : '';
                numHtml +=
                    '<tr><td class="ov-td-col">' + r.col    + '</td>' +
                    '<td>' + r.mean   + '</td><td>' + r.median + '</td>' +
                    '<td>' + r.std    + '</td><td>' + r.min    + '</td>' +
                    '<td>' + r.max    + '</td>' +
                    '<td class="' + outCls + '">' + r.outliers + '</td>' +
                    '<td class="' + misCls + '">' + r.missing  + '</td></tr>';
            });
            numHtml += '</tbody></table>';
            numWrap.innerHTML     = numHtml;
            numWrap.style.display = 'block';
            var nc = document.getElementById('ov-stats-num-card');
            if (nc) nc.style.display = 'block';
        }

        var catWrap = document.getElementById('ov-stats-cat-wrap');
        if (catWrap && sp.cat && sp.cat.length > 0) {
            var catHtml =
                '<table class="ov-stats-table"><thead><tr>' +
                '<th>Column</th><th>Unique</th><th>Mode</th>' +
                '<th>Mode %</th><th>Missing</th>' +
                '</tr></thead><tbody>';
            sp.cat.forEach(function (r) {
                var misCls = r.missing  > 0  ? 'ov-td-warn'   : '';
                var pctCls = r.mode_pct > 70 ? 'ov-td-danger' :
                             r.mode_pct > 50 ? 'ov-td-warn'   : '';
                catHtml +=
                    '<tr><td class="ov-td-col">'   + r.col     + '</td>' +
                    '<td>'                         + r.unique  + '</td>' +
                    '<td class="ov-td-mode">'      + r.mode    + '</td>' +
                    '<td class="' + pctCls + '">'  + r.mode_pct + '%</td>' +
                    '<td class="' + misCls + '">'  + r.missing  + '</td></tr>';
            });
            catHtml += '</tbody></table>';
            catWrap.innerHTML     = catHtml;
            catWrap.style.display = 'block';
            var cc = document.getElementById('ov-stats-cat-card');
            if (cc) cc.style.display = 'block';
        }
    }

    // ── Toggle dropdowns ─────────────────────────────────────────────────────

    function _updateSlotTitle(slotId, colName) {
        var prefix  = SLOT_TITLE_PREFIX[slotId] || '';
        var titleEl = document.getElementById(slotId + '-title');
        if (titleEl) titleEl.textContent = prefix + colName;
    }

    function _getActiveCol(slotId) {
        // Ambil kolom yang sedang dipilih di toggle dropdown
        var sel = document.getElementById('toggle-' + slotId);
        return sel ? sel.value : null;
    }

    function _bindRegularToggle(slotId, toggle) {
        var select = document.getElementById('toggle-' + slotId);
        if (!select || !toggle.charts) return;
        select.addEventListener('change', function () {
            var col   = select.value;
            var chart = toggle.charts[col];
            if (chart) {
                rendered.delete(slotId);
                drawSlot(slotId, chart, true);
                _updateSlotTitle(slotId, col);
            }
        });
    }

    function _bindScatterToggle(toggle) {
        var selX = document.getElementById('scatter-col-x');
        var selY = document.getElementById('scatter-col-y');
        if (!selX || !selY) return;

        function _redraw() {
            var cx    = selX.value;
            var cy    = selY.value;
            var chart = (toggle.charts[cx] || {})[cy];
            if (chart) {
                rendered.delete('ov_top_right');
                drawSlot('ov_top_right', chart, true);
                var titleEl = document.getElementById('ov_top_right-title');
                if (titleEl) titleEl.textContent = 'Scatter — ' + cx + ' × ' + cy;
            }
        }

        selX.addEventListener('change', function () {
            var cx = selX.value;
            if (cx === selY.value) {
                var opts = Array.from(selY.options).map(function(o) { return o.value; });
                var alt  = opts.find(function(v) { return v !== cx; });
                if (alt) selY.value = alt;
            }
            _redraw();
        });

        selY.addEventListener('change', function () {
            var cy = selY.value;
            if (cy === selX.value) {
                var opts = Array.from(selX.options).map(function(o) { return o.value; });
                var alt  = opts.find(function(v) { return v !== cy; });
                if (alt) selX.value = alt;
            }
            _redraw();
        });
    }

    function bindToggles() {
        if (!data || !data.toggle_data) return;
        Object.keys(data.toggle_data).forEach(function (slotId) {
            var toggle = data.toggle_data[slotId];
            if (!toggle) return;
            if (slotId === 'ov_top_right' && toggle.type === 'scatter') {
                _bindScatterToggle(toggle);
            } else {
                _bindRegularToggle(slotId, toggle);
            }
        });
    }

    // ── Click-through ke Visualizations dengan state management ──────────────

    function bindVizNavigation() {
        document.querySelectorAll('.ov-chart-slot[data-viz-tab]').forEach(function (el) {
            el.addEventListener('click', function (e) {
                if (e.target.closest('.ov-toggle-wrap')) return;

                // Cari slot ID dari chart area di dalam card
                var chartEl = el.querySelector('.ov-chart-area');
                var sid     = chartEl ? chartEl.id : null;

                _navigateToSlot(sid, el);
            });
        });
    }

    function _navigateToSlot(slotId, cardEl) {
        // ov_top_right: cek TS atau scatter
        if (slotId === 'ov_top_right') {
            var vizTab = cardEl ? cardEl.getAttribute('data-viz-tab') : 'visualizations';
            if (vizTab === 'timeseries') {
                if (typeof switchTab === 'function') switchTab('timeseries');
                setTimeout(function () {
                    if (typeof switchTsTab === 'function') switchTsTab('line');
                }, 90);
            } else {
                // Scatter — simpan state X dan Y
                var selX = document.getElementById('scatter-col-x');
                var selY = document.getElementById('scatter-col-y');
                var cx   = selX ? selX.value : null;
                var cy   = selY ? selY.value : null;
                _saveVizState('bivariate', 'scatter', cx, cy);
                openVizCategory('bivariate', 'scatter');
            }
            return;
        }

        var target = SLOT_VIZ_STATE[slotId];
        if (!target) {
            if (cardEl) {
                var sub = cardEl.getAttribute('data-viz-sub') || 'numerical';
                openVizCategory(sub, null);
            }
            return;
        }

        // Ambil kolom yang sedang aktif di toggle
        var activeCol = _getActiveCol(slotId);

        // Simpan state ke sessionStorage
        _saveVizState(target.category, target.chartType, activeCol, null);

        // Navigasi
        openVizCategory(target.category, target.chartType);
    }

    // ── Public API ────────────────────────────────────────────────────────────

    function init(overviewPayload) {
        data = overviewPayload || null;
        if (!data) return;
        bindToggles();
        bindVizNavigation();
        var overviewTab = document.getElementById('tab-overview');
        if (overviewTab && overviewTab.classList.contains('active-tab')) {
            setTimeout(function () {
                renderAll();
                renderStatsPreview();
            }, 200);
        }
    }

    function onTabShow() {
        setTimeout(function () {
            renderAll();
            renderStatsPreview();
        }, 120);
    }

    function onResize() {
        rendered.forEach(function (slotId) {
            var el = document.getElementById(slotId);
            if (el && el._fullLayout && typeof Plotly !== 'undefined') {
                Plotly.Plots.resize(el);
            }
        });
    }

    return {
        init              : init,
        onTabShow         : onTabShow,
        onResize          : onResize,
        renderAll         : renderAll,
        renderStatsPreview: renderStatsPreview,
        readVizState      : readVizState,
        clearVizState     : clearVizState,
        saveVizState      : _saveVizState,
    };
})();