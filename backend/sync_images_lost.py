import os
import re
from database import get_connection

def normalize(text):
    if not text: return ""
    text = re.sub(r'[^a-zA-Z0-9]', ' ', text)
    return ' '.join(text.lower().split())

def sync_remaining_files():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Get all used image paths
    cursor.execute("SELECT local_image FROM card_cache WHERE local_image IS NOT NULL")
    used_files = {row[0] for row in cursor.fetchall()}
    
    # 2. List all files
    base_dir = os.path.dirname(os.path.abspath(__file__))
    imagenes_dir = os.path.join(base_dir, "imagenes")
    all_files = [f for f in os.listdir(imagenes_dir) if f.endswith(".jpg")]
    
    # 3. Find files NOT used
    unused_files = []
    for f in all_files:
        path = f"imagenes/{f}"
        if path not in used_files:
            unused_files.append(f)
            
    print(f"Files not linked to any card: {len(unused_files)}")
    if not unused_files:
        print("All files are already linked.")
        return

    # 4. Try fuzzy matching for these unused files
    # Get cards that STILL have no image (though we checked this, maybe some IDs were missed)
    cursor.execute("SELECT id, name FROM card_cache WHERE local_image IS NULL")
    missing_cards = cursor.fetchall()
    
    if not missing_cards:
        print("No cards in DB are missing images. The extra files might be duplicates or unknown cards.")
        print("Example unused files:")
        for f in unused_files[:10]:
            print(f" - {f}")
        return

    # Normalized missing cards map
    card_map = {normalize(name): card_id for card_id, name in missing_cards}
    
    updates = 0
    for f in unused_files:
        norm_f = normalize(f[:-4])
        if norm_f in card_map:
            card_id = card_map[norm_f]
            local_path = f"imagenes/{f}"
            cursor.execute("UPDATE card_cache SET local_image = ? WHERE id = ?", (local_path, card_id))
            updates += 1
            
    conn.commit()
    conn.close()
    print(f"Successfully matched {updates} more images via fuzzy matching.")

if __name__ == "__main__":
    sync_remaining_files()
