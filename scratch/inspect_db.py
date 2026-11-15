import sqlite3

conn = sqlite3.connect('database.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cur.fetchall()]
print('Tables in DB:', tables)
for t in tables:
    cur.execute(f"PRAGMA table_info({t});")
    cols = [(c[1], c[2]) for c in cur.fetchall()]
    print(f"  {t}: {cols}")
conn.close()
