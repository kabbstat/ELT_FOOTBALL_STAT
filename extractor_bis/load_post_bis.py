import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
import numpy as np
import json

load_dotenv()

# connexion au BD 
engine = create_engine(f"postgresql+psycopg2://{os.environ['DB_USER']}:{os.environ['DB_PASS']}@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}")
landing_dir = os.getenv("DATA_DIR")+"/landing"

def clean_data(df: pd.DataFrame)-> pd.DataFrame:
    for col in df.columns:
        if df[col].dtype =='object':
            def save_json(x):
                if not isinstance(x, (np.ndarray, list, dict)) and pd.isna(x): 
                    return None
                if isinstance(x, np.ndarray):
                    if x.size ==0 or (x.size > 0 and pd.isna(x).all()):
                        return None
                    return json.dumps(x.tolist(), default=str)
                if isinstance(x, (list,dict)):
                    return json.dumps(x, default=str)
                return str(x)
            df[col] = df[col].apply(save_json)
    return df 
def load_parquet_to_postgres():
    for file in os.listdir(landing_dir):
        if file.endswith(".parquet"):
            table_name = file.replace(".parquet", "")
            file_path = os.path.join(landing_dir, file)
            print(f"loading {file_path} to table {table_name}")
            df = pd.read_parquet(file_path)
            df = clean_data(df)
            df.to_sql(table_name, engine, if_exists="replace", index=False)
    print("Data loaded to Postgres successfully.")
if __name__ == "__main__":
    load_parquet_to_postgres()
            
                    