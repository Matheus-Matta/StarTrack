import os
import pandas as pd

def read_file_to_dataframe(file_path: str) -> pd.DataFrame:
    _, ext = os.path.splitext(file_path)

    if ext.lower() == '.csv':
        return pd.read_csv(file_path, encoding='ISO-8859-1', sep=None, engine='python', delimiter=None)
    elif ext.lower() in ['.xls', '.xlsx']:
        return pd.read_excel(file_path)
    else:
        raise ValueError("Formato de arquivo não suportado. Use .csv ou .xlsx")