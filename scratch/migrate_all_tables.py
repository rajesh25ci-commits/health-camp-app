import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Get existing columns for appointments
cursor.execute("PRAGMA table_info(appointments);")
cols = [info[1] for info in cursor.fetchall()]
print("Current columns in appointments:", cols)

new_cols = [
    ("systolic_bp", "INTEGER"),
    ("diastolic_bp", "INTEGER"),
    ("blood_sugar", "REAL"),
    ("spo2", "REAL"),
    ("pulse_rate", "INTEGER"),
    ("is_critical", "BOOLEAN DEFAULT 0"),
    ("triage_priority", "VARCHAR(20) DEFAULT 'NORMAL_GREEN'")
]

for col_name, col_type in new_cols:
    if col_name not in cols:
        print(f"Adding {col_name} to appointments...")
        cursor.execute(f"ALTER TABLE appointments ADD COLUMN {col_name} {col_type};")

# Also check health_records
cursor.execute("PRAGMA table_info(health_records);")
hr_cols = [info[1] for info in cursor.fetchall()]
print("Current columns in health_records:", hr_cols)

for col_name, col_type in new_cols:
    if col_name not in hr_cols:
        print(f"Adding {col_name} to health_records...")
        cursor.execute(f"ALTER TABLE health_records ADD COLUMN {col_name} {col_type};")

conn.commit()
conn.close()
print("Migration completed successfully!")
