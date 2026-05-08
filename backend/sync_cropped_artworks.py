import os
import json
import time
import requests
from database import get_connection
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenCLIPEmbeddingFunction
from chromadb.utils.data_loaders import ImageLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CROPPED_DIR = os.path.join(BASE_DIR, "imagenes_cropped")
CHROMA_PATH = os.path.join(BASE_DIR, "chromadb_images")

if not os.path.exists(CROPPED_DIR):
    os.makedirs(CROPPED_DIR)

def get_db_cards():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, data FROM card_cache")
    cards = []
    for row in c.fetchall():
        data = json.loads(row[2])
        images = data.get("card_images", [])
        if images and "image_url_cropped" in images[0]:
            cards.append({
                "id": row[0],
                "name": row[1],
                "url": images[0]["image_url_cropped"]
            })
    conn.close()
    return cards

def download_image(url, local_path):
    if os.path.exists(local_path):
        return True
    try:
        # Respect YGOPRODeck rate limits (~15 req/sec max). We do 5 req/sec.
        time.sleep(0.2) 
        headers = {'User-Agent': 'YugiohAIRagAgent/1.0'}
        r = requests.get(url, stream=True, timeout=10, headers=headers)
        if r.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            return True
        else:
            print(f"Error downloading {url}: HTTP {r.status_code}")
            return False
    except Exception as e:
        print(f"Exception downloading {url}: {e}")
        return False

def sync_all():
    print("Fetching card list from database...")
    cards = get_db_cards()
    print(f"Found {len(cards)} cards with cropped URLs.")
    
    print("Initializing ChromaDB...")
    client = PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(
        name="image_visual_index",
        embedding_function=OpenCLIPEmbeddingFunction(),
        data_loader=ImageLoader(),
        metadata={"hnsw:space": "cosine"}
    )
    
    try:
        existing = collection.get(include=["metadatas"])
        existing_crop_ids = {str(m["crop_id"]) for m in existing["metadatas"] if m and "crop_id" in m}
    except Exception as e:
        print(f"Error checking existing crops: {e}")
        existing_crop_ids = set()
    
    print(f"Found {len(existing_crop_ids)} cropped images already in ChromaDB.")
    
    pending_cards = [c for c in cards if str(c["id"]) not in existing_crop_ids]
    print(f"Starting process for {len(pending_cards)} missing cropped images.")
    print("This will take about 45-60 minutes to complete in the background. Leave it running.")
    
    BATCH_SIZE = 50
    for i in range(0, len(pending_cards), BATCH_SIZE):
        batch = pending_cards[i:i+BATCH_SIZE]
        
        ids_to_add = []
        uris_to_add = []
        metas_to_add = []
        
        for c in batch:
            # Safe filename
            local_name = c["name"].replace("/", "_").replace("\\", "_").replace(":", "_").replace("\"", "_").replace("?", "_").replace("<", "_").replace(">", "_").replace("|", "_").replace("*", "_")
            local_path = os.path.join(CROPPED_DIR, f"{local_name}.jpg")
            
            success = download_image(c["url"], local_path)
            if success:
                ids_to_add.append(f"crop_{c['id']}")
                uris_to_add.append(local_path)
                metas_to_add.append({
                    "name": c["name"],
                    "card_id": 0,  
                    "crop_id": str(c["id"]),
                    "image_path": f"imagenes_cropped/{local_name}.jpg"
                })
        
        if uris_to_add:
            print(f"Embedding batch {i} to {i+len(batch)} / {len(pending_cards)}...")
            try:
                collection.add(
                    ids=ids_to_add,
                    uris=uris_to_add,
                    metadatas=metas_to_add
                )
            except Exception as e:
                print(f"Error embedding batch: {e}")
                
    print("✅ All cropped artworks synchronized and vectorized!")

if __name__ == "__main__":
    sync_all()
