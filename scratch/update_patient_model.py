import sqlite3

# 1. Update models.py
with open('models.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = """    qr_code_path = db.Column(db.String(255), nullable=True)  # relative path, e.g., 'qrcodes/PAT-2026-0001.png'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)"""

replacement = """    qr_code_path = db.Column(db.String(255), nullable=True)  # relative path, e.g., 'qrcodes/PAT-2026-0001.png'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    symptoms = db.Column(db.Text, nullable=True)  # Chief complaints ('Kya Hua Hai?')
    urgency_level = db.Column(db.String(20), default='NORMAL', nullable=False)  # 'NORMAL', 'URGENT', 'EMERGENCY'"""

if target not in text:
    target = target.replace('\n', '\r\n')
    replacement = replacement.replace('\n', '\r\n')

if target in text:
    text = text.replace(target, replacement, 1)
    
    # Also update to_dict
    dict_target = "'qr_code_path': self.qr_code_path,"
    dict_replacement = "'qr_code_path': self.qr_code_path,\n            'symptoms': self.symptoms,\n            'urgency_level': self.urgency_level,"
    if dict_target in text:
        text = text.replace(dict_target, dict_replacement, 1)

    with open('models.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("models.py updated with Patient symptoms and urgency_level!")
else:
    print("Target not found in models.py")

# 2. Update SQLite database schema
conn = sqlite3.connect('database.db')
c = conn.cursor()
c.execute("PRAGMA table_info(patients);")
existing_cols = [col[1] for col in c.fetchall()]

if 'symptoms' not in existing_cols:
    print("Adding symptoms column to patients...")
    c.execute("ALTER TABLE patients ADD COLUMN symptoms TEXT;")

if 'urgency_level' not in existing_cols:
    print("Adding urgency_level column to patients...")
    c.execute("ALTER TABLE patients ADD COLUMN urgency_level VARCHAR(20) DEFAULT 'NORMAL';")

conn.commit()
conn.close()
print("Database schema migration for patients completed successfully!")
