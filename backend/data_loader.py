import csv
import logging
import os
import warnings

import pandas as pd

logger = logging.getLogger(__name__)


class DataLoadError(ValueError):
    """Dataset cannot be read without losing rows."""


def get_delimiter(file_path, encoding='utf-8-sig'):
    with open(file_path, encoding=encoding) as file:
        sample = file.read(65536)
    try:
        return csv.Sniffer().sniff(sample, delimiters=',;\t|').delimiter
    except csv.Error:
        first_line = sample.splitlines()[0] if sample.splitlines() else ''
        return max((',', ';', '\t', '|'), key=first_line.count)


def load_data(file_path, strict=False):
    """Read datasets; strict uploads get an actionable error."""
    try:
        extension = os.path.splitext(file_path)[1].lower()
        if extension in ('.csv', '.txt'):
            for encoding in ('utf-8-sig', 'latin1'):
                try:
                    delimiter = get_delimiter(file_path, encoding)
                    with warnings.catch_warnings():
                        warnings.simplefilter('error', pd.errors.ParserWarning)
                        frame = pd.read_csv(
                            file_path, sep=delimiter, engine='python',
                            encoding=encoding, on_bad_lines='error', index_col=False,
                        )
                    break
                except UnicodeDecodeError:
                    if encoding == 'latin1':
                        raise
        elif extension == '.xlsx':
            frame = pd.read_excel(file_path)
        else:
            raise DataLoadError('Format file tidak didukung. Gunakan CSV, TXT, atau XLSX.')
        if frame.empty:
            raise DataLoadError('Dataset kosong. File harus berisi header dan minimal satu baris data.')
        return frame
    except Exception as error:
        if isinstance(error, DataLoadError):
            message = str(error)
        elif isinstance(error, pd.errors.EmptyDataError):
            message = 'File kosong atau tidak memiliki kolom yang dapat dibaca.'
        elif isinstance(error, (pd.errors.ParserError, pd.errors.ParserWarning)):
            message = 'Struktur CSV/TXT tidak konsisten. Periksa pemisah dan jumlah kolom setiap baris.'
        else:
            message = 'Dataset tidak dapat dibaca. Periksa format dan pastikan file tidak rusak.'
        if strict:
            raise DataLoadError(message) from error
        logger.warning('Dataset could not be loaded: %s', message)
        return None
