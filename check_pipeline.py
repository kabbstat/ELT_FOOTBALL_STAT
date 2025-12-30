import psycopg2

conn = psycopg2.connect(
    host='localhost', 
    port=5432, 
    dbname='football_stats_db', 
    user='football_user', 
    password='123456'
)

cur = conn.cursor()

# Vérifier les schémas
cur.execute("""
    SELECT schema_name 
    FROM information_schema.schemata 
    WHERE schema_name IN ('bronze', 'silver', 'gold')
    ORDER BY schema_name
""")
schemas = [row[0] for row in cur.fetchall()]
print('📂 Schémas disponibles:', ', '.join(schemas))

# Tables bronze
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'bronze'
""")
print('\n🟤 Tables BRONZE:')
for row in cur.fetchall():
    cur.execute(f'SELECT COUNT(*) FROM bronze.{row[0]}')
    count = cur.fetchone()[0]
    print(f'  • {row[0]}: {count} lignes')

# Tables silver
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'silver'
""")
print('\n⚪ Tables SILVER:')
for row in cur.fetchall():
    cur.execute(f'SELECT COUNT(*) FROM silver.{row[0]}')
    count = cur.fetchone()[0]
    print(f'  • {row[0]}: {count} lignes')

# Tables gold
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'gold'
""")
print('\n🟡 Tables GOLD:')
for row in cur.fetchall():
    cur.execute(f'SELECT COUNT(*) FROM gold.{row[0]}')
    count = cur.fetchone()[0]
    print(f'  • {row[0]}: {count} lignes')

# Exemple de données gold
print('\n📊 Exemple: Top 5 équipes (gold.mart_team_stats):')
cur.execute("""
    SELECT team_name, league_code, total_matches, total_wins, total_draws, total_losses, total_points
    FROM gold.mart_team_stats
    ORDER BY total_points DESC
    LIMIT 5
""")
for row in cur.fetchall():
    print(f'  {row[0]} ({row[1]}): {row[2]} matchs, {row[6]} pts ({row[3]}V-{row[4]}N-{row[5]}D)')

conn.close()
