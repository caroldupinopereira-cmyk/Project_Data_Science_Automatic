# DS Generator

Aplikasi Flask untuk upload dataset CSV/TXT/XLSX, data cleaning, statistik,
visualisasi, analisis time series, dan ekspor laporan.

## Menjalankan di Windows

Buka terminal di folder proyek, lalu jalankan:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Buka http://127.0.0.1:5000 di browser. Biarkan terminal tetap terbuka selama
aplikasi digunakan. Tekan Ctrl+C untuk menghentikan server.

Untuk menjalankan kembali, cukup gunakan perintah terakhir. Jika perintah
`python` tidak ditemukan, gunakan `py` untuk membuat virtual environment.

API key dalam `.env` diperlukan untuk fitur AI. Analisis statistik dan cleaning
dapat digunakan tanpa API key. Login Google/Microsoft memerlukan konfigurasi
OAuth masing-masing; pendaftaran akun lokal tersedia di `/auth/register`.

Semua pintu masuk (`/login` dan `/auth/login`) menggunakan akun dan password
yang sama. Login lama dengan nama saja sudah dinonaktifkan. Pengguna mungkin
perlu login kembali setelah pembaruan pengaturan sesi ini.

`SECRET_KEY` dapat diatur di `.env`. Jika tidak diatur, aplikasi menggunakan
file lokal `.secret_key` yang dibuat otomatis dan tidak dimasukkan ke Git.

File kosong, Excel rusak, dan CSV dengan struktur kolom yang tidak konsisten
ditolak saat upload. Baris yang rusak tidak lagi dilewati diam-diam.

## Pemeriksaan regresi

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node tests/test_navigation.cjs
```

Tes navigasi memerlukan Node.js. Tes PDF memeriksa isi dan penyisipan gambar;
hasil render Kaleido dan tata letak visual tetap perlu diperiksa langsung.
