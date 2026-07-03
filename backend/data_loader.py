import pandas as pd
import os
import csv

def get_delimiter(file_path):
    """
    Fungsi cerdas untuk mendeteksi separator (pemisah) 
    pada file text atau csv (koma, tab, titik koma, dsb).
    """
    try:
        # Buka file dan baca sebagian kecil datanya untuk dianalisis
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            sample = file.read(2048) # Baca 2048 karakter pertama
            
            # Gunakan csv.Sniffer dari bawaan Python untuk menebak delimiter
            dialect = csv.Sniffer().sniff(sample)
            return dialect.delimiter
    except Exception:
        # Jika Sniffer gagal, kita gunakan fallback manual dengan melihat baris pertama
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                first_line = file.readline()
                if '\t' in first_line: return '\t'  # Jika ada Tab
                if ';' in first_line: return ';'    # Jika ada titik koma
                if '|' in first_line: return '|'    # Jika ada pipa
                return ','                          # Default ke koma
        except:
            return ','

def load_data(file_path):
    """Loads dataset based on file extension smoothly."""
    try:
        ext = os.path.splitext(file_path)[1].lower()
        
        # Penanganan untuk CSV dan TXT yang lebih canggih
        if ext in ['.csv', '.txt']:
            # 1. Deteksi pemisahnya apa
            detected_sep = get_delimiter(file_path)
            
            # 2. Baca file menggunakan pandas dengan separator yang terdeteksi
            # engine='python' dan on_bad_lines='skip' agar file tidak crash jika ada baris error
            df = pd.read_csv(file_path, sep=detected_sep, engine='python', on_bad_lines='skip', encoding='utf-8')
            return df
            
        # Penanganan untuk file Excel
        elif ext == '.xlsx':
            return pd.read_excel(file_path)
            
        else:
            raise ValueError(f"Unsupported file format: {ext}")
            
    except Exception as e:
        print(f"Error loading data: {e}")
        # Jika gagal dengan utf-8, coba dengan encoding latin1 (biasanya ampuh untuk file TXT lama)
        try:
            if ext in ['.csv', '.txt']:
                detected_sep = get_delimiter(file_path)
                return pd.read_csv(file_path, sep=detected_sep, engine='python', encoding='latin1', on_bad_lines='skip')
        except Exception as e2:
            print(f"Second attempt failed: {e2}")
            return None
