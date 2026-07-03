import pandas as pd
import numpy as np
import sys
import os

# Tambahkan path project ke sys.path agar bisa import backend
sys.path.append(os.path.abspath('.'))

from backend.cleaning_engine import _op_fix_inconsistencies

def test_casing():
    print("Mulai pengujian...")
    
    # 1. Buat mock DataFrame dengan tipe data string, object, dan category
    data = {
        'col_str': pd.Series(['  apple  ', 'BANANA', 'cherry description', np.nan], dtype='string'),
        'col_obj': ['  dog  ', 'CAT', 'elephant in the room', np.nan],
        'col_cat': pd.Series(['  red  ', 'BLUE', 'green grass', np.nan], dtype='category'),
        'col_num': [1, 2, 3, 4]
    }
    df = pd.DataFrame(data)
    
    print("\nDataFrame Awal:")
    print(df)
    print("Dtypes Awal:")
    print(df.dtypes)
    
    # 2. Uji method "capitalize"
    params = {'method': 'capitalize'}
    df_clean, label, log = _op_fix_inconsistencies(df, params)
    
    print("\nDataFrame Hasil Cleaning ('capitalize'):")
    print(df_clean)
    print("Dtypes Hasil:")
    print(df_clean.dtypes)
    print("\nLabel:")
    print(label)
    print("\nLog:")
    print(log)
    
    # Verifikasi hasil col_str
    assert df_clean['col_str'].iloc[0] == 'Apple', f"Expected 'Apple', got {df_clean['col_str'].iloc[0]}"
    assert df_clean['col_str'].iloc[1] == 'Banana', f"Expected 'Banana', got {df_clean['col_str'].iloc[1]}"
    assert df_clean['col_str'].iloc[2] == 'Cherry description', f"Expected 'Cherry description', got {df_clean['col_str'].iloc[2]}"
    assert pd.isna(df_clean['col_str'].iloc[3]), "Expected NaN"

    # Verifikasi hasil col_obj
    assert df_clean['col_obj'].iloc[0] == 'Dog', f"Expected 'Dog', got {df_clean['col_obj'].iloc[0]}"
    assert df_clean['col_obj'].iloc[1] == 'Cat', f"Expected 'Cat', got {df_clean['col_obj'].iloc[1]}"
    assert df_clean['col_obj'].iloc[2] == 'Elephant in the room', f"Expected 'Elephant in the room', got {df_clean['col_obj'].iloc[2]}"
    assert pd.isna(df_clean['col_obj'].iloc[3]), "Expected NaN"

    # Verifikasi hasil col_cat (sebelumnya category, harus diubah ke object/string dan di-clean)
    assert df_clean['col_cat'].iloc[0] == 'Red', f"Expected 'Red', got {df_clean['col_cat'].iloc[0]}"
    assert df_clean['col_cat'].iloc[1] == 'Blue', f"Expected 'Blue', got {df_clean['col_cat'].iloc[1]}"
    assert df_clean['col_cat'].iloc[2] == 'Green grass', f"Expected 'Green grass', got {df_clean['col_cat'].iloc[2]}"
    assert pd.isna(df_clean['col_cat'].iloc[3]), "Expected NaN"

    # Verifikasi kolom numerik tidak berubah tipe atau isinya
    assert df_clean['col_num'].iloc[0] == 1
    assert df_clean['col_num'].dtype == 'int64' or df_clean['col_num'].dtype == 'int32'

    print("\nSemua verifikasi sukses!")

if __name__ == '__main__':
    test_casing()
