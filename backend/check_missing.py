import os
from pathlib import Path
from database import get_connection

BASE_DIR = Path(__file__).resolve().parent

conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT name FROM card_cache")
db_names = {r[0] for r in cursor.fetchall()}

files = os.listdir(BASE_DIR / "imagenes")
missing = []
for f in files:
    if f.endswith('.jpg'):
        name = f[:-4]
        if name not in db_names:
            missing.append(name)

print(f"Total files in imagenes: {len(files)}")
print(f"Files not exact matching SQLite name: {len(missing)}")
print("First 10 missing:")
for m in missing[:10]:
    print(f"- {m}")
