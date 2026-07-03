# Struktur Folder Data

Folder ini digunakan untuk menyimpan semua data yang diolah dalam aplikasi DS Generator.

## Struktur Folder

```
data/
├── README.md              # File ini
├── uploaded/              # Data mentah yang diupload oleh pengguna
│   ├── *.csv              # File CSV
│   ├── *.xlsx             # File Excel
│   └── *.txt              # File teks
│
├── cleaned/               # Data yang sudah melalui proses cleaning
│   └── *_cleaned.csv      # Data hasil cleaning dalam format CSV
│
└── reports/               # Laporan hasil analisis
    ├── pdf/               # Laporan dalam format PDF
    ├── html/              # Laporan dalam format HTML
    ├── csv/               # Laporan ringkasan dalam format CSV
    ├── json/              # Laporan data dalam format JSON
    └── temp_reports/      # File temporary saat generate laporan (otomatis dibersihkan)
```

## Penjelasan

### 1. Folder `uploaded/`
Menyimpan semua file data mentah yang diupload oleh pengguna sebelum melalui proses cleaning. File disimpan dengan nama asli sesuai yang diupload.

### 2. Folder `cleaned/`
Menyimpan data yang sudah melalui proses cleaning dan preprocessing. File hasil cleaning diberi akhiran `_cleaned` untuk membedakan dari data asli.

### 3. Folder `reports/`
Menyimpan semua laporan hasil analisis data:
- **pdf/**: Laporan lengkap dalam format PDF (statistik deskriptif, visualisasi, insight)
- **html/**: Laporan interaktif dalam format HTML
- **csv/**: Ringkasan data dalam format tabel CSV
- **json/**: Data laporan dalam format JSON untuk keperluan integrasi

## Cara Penggunaan

1. Upload data melalui halaman upload di aplikasi
2. Data akan tersimpan di folder `uploaded/`
3. Lakukan cleaning data melalui fitur data cleaning
4. Data hasil cleaning akan tersimpan di folder `cleaned/`
5. Generate laporan melalui fitur reporting
6. Laporan akan tersimpan di folder `reports/` sesuai formatnya

## Catatan
- File di folder ini dikelola secara otomatis oleh aplikasi
- Folder `temp_reports/` berisi file temporary yang digunakan saat generate laporan, dapat dihapus kapan saja
- Jangan menghapus atau memodifikasi file secara manual kecuali jika diperlukan
- Backup data penting secara berkala