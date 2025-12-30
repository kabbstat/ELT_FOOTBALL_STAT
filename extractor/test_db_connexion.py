from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
from urllib.parse import quote_plus

load_dotenv()

db_pass = quote_plus(os.environ['DB_PASS'])
db_url = f"postgresql+psycopg2://{os.environ['DB_USER']}:{db_pass}@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"

try:
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        print(f"✅ Connexion réussie!")
        print(f"📊 PostgreSQL version: {version}")
except Exception as e:
    print(f"❌ Erreur de connexion: {e}")