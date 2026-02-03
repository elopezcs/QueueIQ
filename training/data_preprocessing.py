import pandas as pd

class DataPreprocessor:
    @staticmethod
    def clean_percentage_data(df):
        for col in df.columns[1:]:
            df[col] = df[col].astype(str).str.replace('%', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
