import os
from database import get_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGENES_DIR = os.path.join(BASE_DIR, "imagenes")

def sync_all_images():
    conn = get_connection()
    cursor = conn.cursor()
    
    files = os.listdir(IMAGENES_DIR)
    print(f"Found {len(files)} files in imagenes/")
    
    updates = 0
    not_found = 0
    already_synced = 0
    
    for i, file in enumerate(files):
        if file.endswith(".jpg"):
            name = file[:-4]  # Remove .jpg
            local_path = f"imagenes/{file}"
            
            cursor.execute("SELECT id, local_image FROM card_cache WHERE name = ?", (name,))
            row = cursor.fetchone()
            
            if row:
                if row[1] is None:
                    cursor.execute("UPDATE card_cache SET local_image = ? WHERE id = ?", (local_path, row[0]))
                    updates += 1
                else:
                    already_synced += 1
            else:
                not_found += 1
                
        if i % 1000 == 0:
            print(f"Processed {i}/{len(files)}")
                
    conn.commit()
    conn.close()
    print(f"✅ Synced {updates} new images to database. {already_synced} already synced. {not_found} not found in DB.")

if __name__ == '__main__':
    sync_all_images()
