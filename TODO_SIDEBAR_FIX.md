# TODO: Perbaiki struktur sidebar (Visualizations & Descriptive Statistics dropdown)

## Step 1 — Analisis struktur & handler
- [x] Cek `frontend/templates/base.html`: identifikasi markup sidebar untuk item **Descriptive Statistics** dan **Visualizations**.
- [x] Cek `frontend/static/js/script.js`: cari fungsi `toggleAccordion()` dan logika `switchTab()`.

## Step 2 — Perbaiki HTML accordion untuk Visualizations
- [x] Bungkus submenu Visualizations di dalam container accordion.

- [x] Samakan pola dengan accordion Descriptive Statistics.


## Step 3 — Tambahkan JS `toggleAccordion(id)`
- [x] Implementasi `toggleAccordion(id)` untuk mengatur class `.open` pada `.nav-accordion-item`.

- [ ] Pastikan klik Visualizations memanggil `toggleAccordion('acc-visualizations')`.
- [ ] Pastikan klik Descriptive Statistics tetap bekerja.

## Step 4 — Test manual
- [ ] Jalankan aplikasi.
- [ ] Klik **Descriptive Statistics**: submenu muncul.
- [ ] Klik **Visualizations**: submenu muncul.

