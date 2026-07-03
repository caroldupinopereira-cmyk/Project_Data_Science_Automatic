/**
 * i18n.js — Lightweight i18n module for landing & login pages.
 *
 * Usage:
 *   1. Add `data-i18n="key"` attributes to translatable elements.
 *   2. Include this script at the bottom of the page.
 *   3. Call `I18n.init()` on DOMContentLoaded.
 *
 * The dashboard page has its own TRANSLATIONS object in script.js;
 * this module covers the standalone pages (index, login).
 */

const I18n = (function () {
    'use strict';

    /* ── Translation dictionaries ─────────────────────────────── */
    const DICT = {
        en: {
            /* ── Landing page (index.html) ── */
            'brand.subtitle'    : 'Auto-EDA Dashboard',
            'nav.features'      : 'Features',
            'nav.members'       : 'Project Members',
            'nav.get_started'   : 'Get Started',
            'eyebrow'           : 'Data Science Programming Final Project',
            'hero.title'        : 'Automated data analysis with',
            'hero.title_accent' : 'futuristic Auto-EDA.',
            'hero.desc'         : 'DS Generator helps you upload datasets, assess data quality, compute descriptive statistics, build interactive visualizations, and generate insights & reports — all in one dashboard.',
            'hero.cta_start'    : 'Start Analysis',
            'hero.cta_features' : 'View Features',
            'stat.charts'       : 'Chart types for data exploration',
            'stat.export'       : 'Export formats: PDF, HTML, Excel, CSV',
            'stat.auto'         : 'Auto-detect numeric, categorical & time series',
            'stat.themes'       : 'Light & dark theme with accessible contrast',
            'features.heading'  : 'Built for fast exploratory analysis.',
            'features.sub'      : 'A streamlined workflow from raw dataset to final insight, with a professional UI that\'s easy to use in class, presentations, or project demos.',
            'feat.upload.title' : 'Secure Upload',
            'feat.upload.desc'  : 'Upload CSV, XLSX, and TXT — the dashboard reads your dataset structure automatically.',
            'feat.clean.title'  : 'Data Cleaning',
            'feat.clean.desc'   : 'Preview cleaning impact, run operations, and track every change in history.',
            'feat.eda.title'    : 'Interactive EDA',
            'feat.eda.desc'     : 'Numeric & categorical stats, advanced tests, and Plotly visualizations in one place.',
            'feat.report.title' : 'Report Ready',
            'feat.report.desc'  : 'Export analysis to PDF, HTML dashboard, Excel, or CSV for documentation.',
            'members.heading'   : 'Project Members',
            'members.sub'       : 'Kelompok 2 ITSB — building DS Generator as a modern Auto-EDA dashboard for automated data analysis.',
            'footer.left'       : 'DS Generator — Auto-EDA Dashboard Kelompok 2 ITSB.',
            'footer.right'      : 'Modern analytics for descriptive statistics, visualization, insight, and reporting.',

            /* ── Login page (login.html) ── */
            'login.title'       : 'Login DS Generator',
            'login.subtitle'    : 'Sign in so each user\'s datasets and recent files stay private.',
            'login.name_label'  : 'Your Name',
            'login.name_ph'     : 'e.g. Carol',
            'login.role_label'  : 'Role',
            'login.btn_back'    : 'Back',
            'login.btn_submit'  : 'Login',
            'login.note'        : 'Each user gets their own upload folder, so recent datasets and cleaning sessions never mix.',

            /* ── Shared ── */
            'lang.label'        : 'Language',
        },

        id: {
            /* ── Landing page ── */
            'brand.subtitle'    : 'Dashboard Auto-EDA',
            'nav.features'      : 'Fitur',
            'nav.members'       : 'Anggota Proyek',
            'nav.get_started'   : 'Mulai Sekarang',
            'eyebrow'           : 'Tugas Akhir Pemrograman Data Science',
            'hero.title'        : 'Analisis data otomatis dengan',
            'hero.title_accent' : 'Auto-EDA futuristik.',
            'hero.desc'         : 'DS Generator membantu Anda mengunggah dataset, menilai kualitas data, menghitung statistik deskriptif, membuat visualisasi interaktif, serta menghasilkan insight & laporan — semua dalam satu dashboard.',
            'hero.cta_start'    : 'Mulai Analisis',
            'hero.cta_features' : 'Lihat Fitur',
            'stat.charts'       : 'Jenis chart untuk eksplorasi data',
            'stat.export'       : 'Format ekspor: PDF, HTML, Excel, CSV',
            'stat.auto'         : 'Deteksi otomatis numerik, kategorik & time series',
            'stat.themes'       : 'Tema terang & gelap dengan kontras terjaga',
            'features.heading'  : 'Dirancang untuk analisis eksploratif yang cepat.',
            'features.sub'      : 'Alur kerja ringkas dari dataset mentah hingga insight akhir, dengan UI profesional yang mudah dipakai di kelas, presentasi, atau demo proyek.',
            'feat.upload.title' : 'Upload Aman',
            'feat.upload.desc'  : 'Unggah CSV, XLSX, dan TXT — dashboard otomatis membaca struktur dataset Anda.',
            'feat.clean.title'  : 'Pembersihan Data',
            'feat.clean.desc'   : 'Pratinjau dampak cleaning, jalankan operasi, dan lacak setiap perubahan di riwayat.',
            'feat.eda.title'    : 'EDA Interaktif',
            'feat.eda.desc'     : 'Statistik numerik & kategorik, uji lanjutan, dan visualisasi Plotly dalam satu tempat.',
            'feat.report.title' : 'Siap Laporan',
            'feat.report.desc'  : 'Ekspor analisis ke PDF, HTML dashboard, Excel, atau CSV untuk dokumentasi.',
            'members.heading'   : 'Anggota Proyek',
            'members.sub'       : 'Kelompok 2 ITSB — membangun DS Generator sebagai dashboard Auto-EDA modern untuk analisis data otomatis.',
            'footer.left'       : 'DS Generator — Dashboard Auto-EDA Kelompok 2 ITSB.',
            'footer.right'      : 'Analitik modern untuk statistik deskriptif, visualisasi, insight, dan pelaporan.',

            /* ── Login page ── */
            'login.title'       : 'Login DS Generator',
            'login.subtitle'    : 'Masuk dulu agar dataset dan recent file tetap milik masing-masing user.',
            'login.name_label'  : 'Nama User',
            'login.name_ph'     : 'Contoh: Carol',
            'login.role_label'  : 'Role',
            'login.btn_back'    : 'Kembali',
            'login.btn_submit'  : 'Masuk',
            'login.note'        : 'Setiap user mendapat folder upload sendiri, jadi recent dataset dan session cleaning tidak akan tercampur.',

            /* ── Shared ── */
            'lang.label'        : 'Bahasa',
        },
    };

    /* ── State ─────────────────────────────────────────────────── */
    let _currentLang = 'en';
    const STORAGE_KEY = 'ds-lang';

    /* ── Public API ────────────────────────────────────────────── */

    function t(key) {
        return (DICT[_currentLang] && DICT[_currentLang][key]) || DICT.en[key] || key;
    }

    function applyTranslations() {
        var dict = DICT[_currentLang] || DICT.en;
        document.querySelectorAll('[data-i18n]').forEach(function (el) {
            var key = el.getAttribute('data-i18n');
            if (dict[key] !== undefined) {
                el.textContent = dict[key];
            }
        });
        // data-i18n-placeholder for input placeholders
        document.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
            var key = el.getAttribute('data-i18n-placeholder');
            if (dict[key] !== undefined) {
                el.setAttribute('placeholder', dict[key]);
            }
        });
    }

    function getLang() {
        return _currentLang;
    }

    function setLang(lang) {
        if (!DICT[lang]) lang = 'en';
        _currentLang = lang;
        localStorage.setItem(STORAGE_KEY, lang);
        applyTranslations();
        // Update selector if present
        var sel = document.getElementById('lang-selector-standalone');
        if (sel) sel.value = lang;
    }

    function init() {
        _currentLang = localStorage.getItem(STORAGE_KEY) || 'en';
        applyTranslations();

        // Wire up selector
        var sel = document.getElementById('lang-selector-standalone');
        if (sel) {
            sel.value = _currentLang;
            sel.addEventListener('change', function () {
                setLang(this.value);
            });
        }
    }

    return {
        init: init,
        t: t,
        setLang: setLang,
        getLang: getLang,
    };
})();

document.addEventListener('DOMContentLoaded', I18n.init);
