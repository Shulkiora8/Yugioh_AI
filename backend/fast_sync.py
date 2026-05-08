import os
from database import get_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGENES_DIR = os.path.join(BASE_DIR, "imagenes")

conn = get_connection()
cursor = conn.cursor()

cursor.execute("SELECT id, name, local_image FROM card_cache")
rows = cursor.fetchall()
db_dict = {row[1]: (row[0], row[2]) for row in rows}

files = os.listdir(IMAGENES_DIR)
updates = []
for f in files:
    if f.endswith('.jpg'):
        name = f[:-4]
        if name in db_dict:
            card_id, local_img = db_dict[name]
            if local_img is None:
                updates.append((f"imagenes/{f}", card_id))

if updates:
    cursor.executemany("UPDATE card_cache SET local_image = ? WHERE id = ?", updates)
    conn.commit()
conn.close()
print(f"Fast synced {len(updates)} images!")
