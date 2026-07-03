# TODO — DS Generator Redesign (Theme, i18n, PDF)

## Step 1 — Theme variables & aksesibilitas
- [ ] Audit komponen: sidebar, navbar/topbar, card, tooltip, alert/flash, form, button, insight, report
- [ ] Konsolidasikan CSS variables untuk light/dark
- [ ] Pastikan kontras & keterbacaan (hindari teks putih/abu pada background terang)
- [ ] Tambahkan `prefers-reduced-motion` untuk animasi ringan

## Step 2 — Unifikasi responsive table
- [ ] Pastikan seluruh tabel berada di wrapper horizontal scroll
- [ ] Sticky header aktif & konsisten untuk semua jenis tabel (pandas to_html, dataTables, quality tables)
- [ ] Zebra striping + hover effect seragam
- [ ] Optimasi padding/font-size untuk mobile
- [ ] Pastikan tidak ada teks bertabrakan/terpotong tanpa akses

## Step 3 — i18n multi-language penuh
- [ ] Buat dictionary terpusat untuk ID/EN
- [ ] Ganti semua hardcoded UI text di template
- [ ] Update placeholder, tooltip, toast/alert, error/success
- [ ] Pastikan label chart & table ikut translate

## Step 4 — Perbaikan export PDF
- [ ] Refactor `backend/report_generator.py` untuk error handling per section
- [ ] Pastikan PDF tetap dibuat walau beberapa section/data tidak ada
- [ ] Pastikan UTF-8 & font untuk karakter Indonesia
- [ ] Ubah watermark: “Kelompok 2”

## Step 5 — UX responsive
- [ ] Tambahkan skeleton loading & empty state informatif
- [ ] Perbaiki spacing/grid/typography untuk mobile
- [ ] Pastikan animasi ringan dan tidak mengganggu

## Step 6 — Kualitas kode & refactor
- [ ] Hilangkan duplikasi string/hardcoded warna/text
- [ ] Pisahkan komponen JS yang redundan
- [ ] Pastikan fitur lama tetap jalan

