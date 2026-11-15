import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..', 'database.db')

def migrate_database():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    migrations = [
        # (table, column, col_type, default)
        ('patients', 'blood_group', 'VARCHAR(10)', "'O+'"),
        ('patients', 'allergies', 'TEXT', "'None'"),
        ('health_records', 'temperature', 'REAL', '98.6'),
        ('health_records', 'risk_level', 'VARCHAR(20)', "'LOW RISK'"),
        ('health_records', 'risk_reason', 'TEXT', "'Routine wellness vitals within normal limits.'"),
        ('health_records', 'followup_date', 'DATE', 'NULL'),
        ('health_records', 'followup_status', 'VARCHAR(30)', "'None'"),
        ('health_records', 'followup_notes', 'TEXT', 'NULL'),
        ('appointments', 'temperature', 'REAL', '98.6'),
        ('appointments', 'slot_number', 'INTEGER', '1'),
    ]

    for table, col, col_type, default in migrations:
        cur.execute(f"PRAGMA table_info({table});")
        existing_cols = [c[1] for c in cur.fetchall()]
        if col not in existing_cols:
            alter_query = f"ALTER TABLE {table} ADD COLUMN {col} {col_type} DEFAULT {default};"
            cur.execute(alter_query)
            print(f"Added column {col} ({col_type}) to {table}.")
        else:
            print(f"Column {col} already exists in {table}.")

    conn.commit()
    conn.close()
    print("Database migration completed successfully.")

if __name__ == '__main__':
    migrate_database()
