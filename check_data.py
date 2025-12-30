import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost', 
    port=5432, 
    dbname='football_stats_db', 
    user='football_user', 
    password='123456'
)

cur = conn.cursor()

# Compter les matchs
cur.execute('SELECT COUNT(*) FROM bronze.all_matches')
count = cur.fetchone()[0]
print(f'📊 Total matchs: {count}')

# Vérifier la plage de dates
cur.execute('SELECT MIN("utcDate"), MAX("utcDate") FROM bronze.all_matches')
min_date, max_date = cur.fetchone()
print(f'📅 Période des matchs: {min_date} → {max_date}')

# Compter par saison
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM "utcDate"::timestamp) as year,
        COUNT(*) as nb_matches
    FROM bronze.all_matches
    GROUP BY year
    ORDER BY year
""")
print('\n📈 Matchs par année:')
for row in cur.fetchall():
    print(f'  {int(row[0])}: {row[1]} matchs')

# Vérifier les premiers matchs de chaque saison
cur.execute('SELECT "utcDate", "homeTeam_name", "awayTeam_name" FROM bronze.all_matches ORDER BY "utcDate" LIMIT 3')
rows = cur.fetchall()
print('\n🔍 Premiers matchs dans la base:')
for r in rows:
    print(f'  {r[0]}: {r[1]} vs {r[2]}')

# Derniers matchs
cur.execute('SELECT "utcDate", "homeTeam_name", "awayTeam_name" FROM bronze.all_matches ORDER BY "utcDate" DESC LIMIT 3')
rows = cur.fetchall()
print('\n🔍 Derniers matchs dans la base:')
for r in rows:
    print(f'  {r[0]}: {r[1]} vs {r[2]}')

conn.close()
