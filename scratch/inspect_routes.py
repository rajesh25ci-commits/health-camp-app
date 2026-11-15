import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app

print("\n--- ALL REGISTERED ROUTES IN FLASK APP ---")
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    methods = [m for m in rule.methods if m not in ('HEAD', 'OPTIONS')]
    print(f"{rule.rule:45} -> {rule.endpoint:35} {methods}")
