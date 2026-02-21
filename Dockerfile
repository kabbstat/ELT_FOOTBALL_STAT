FROM apache/airflow:2.7.3-python3.11

USER airflow

# Installer les dependances Python necessaires
# Mise a jour : Fevrier 2026 - Ajout elasticsearch
RUN pip install --no-cache-dir \
    pandas==2.1.3 \
    pyarrow==14.0.1 \
    psycopg2-binary==2.9.9 \
    requests==2.31.0 \
    dbt-core==1.7.4 \
    dbt-postgres==1.7.4 \
    python-dotenv==1.0.0 \
    elasticsearch==8.11.0 \
    beautifulsoup4==4.12.2