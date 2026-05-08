import os
import requests
import json
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from dotenv import load_dotenv
from database import update_card_local_image, init_db, get_connection

load_dotenv()

INDEX_PATH = "faiss_cards_index"
EMBEDDING_MODEL = "all-minilm:33m"

IMAGES_DIR = "imagenes"

def fetch_all_cards():
    print("Fetching all cards from YGOPRODeck API...")
    url = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()["data"]

def get_local_images():
    """Returns a dict mapping card names (cleaned) to their local file paths."""
    mapping = {}
    if not os.path.exists(IMAGES_DIR):
        return mapping
    
    for filename in os.listdir(IMAGES_DIR):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            # Clean filename: remove extension and replace hyphens/underscores with spaces
            name_part = os.path.splitext(filename)[0]
            clean_name = name_part.replace('-', ' ').replace('_', ' ').lower().strip()
            mapping[clean_name] = os.path.join(IMAGES_DIR, filename)
    return mapping

def get_visual_descriptions():
    """Returns a dict mapping card IDs to their visual descriptions from DB."""
    mapping = {}
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, visual_description FROM card_cache WHERE visual_description IS NOT NULL")
        for row in cursor.fetchall():
            mapping[row[0]] = row[1]
        conn.close()
    except Exception as e:
        print(f"Warning: Could not fetch visual descriptions: {e}")
    return mapping

def process_cards(cards, local_images_map=None, visual_desc_map=None):
    if local_images_map is None:
        local_images_map = {}
    if visual_desc_map is None:
        visual_desc_map = {}
    print(f"Processing {len(cards)} cards...")
    documents = []
    for card in cards:
        # Create a rich text representation for the card
        stats = []
        if "atk" in card: stats.append(f"ATK: {card['atk']}")
        if "def" in card: stats.append(f"DEF: {card['def']}")
        if "level" in card: stats.append(f"Level/Rank: {card['level']}")
        if "attribute" in card: stats.append(f"Attribute: {card['attribute']}")
        
        # Include visual description in content if available
        desc = card['desc']
        if len(desc) > 300:
            desc = desc[:300] + "..."
            
        vis = visual_desc_map.get(card["id"], "")
        if len(vis) > 300:
            vis = vis[:300] + "..."
            
        visual_info = f"\nVisual Appearance: {vis}" if vis else ""
        
        content = (
            f"Name: {card['name']}\n"
            f"Type: {card['type']}\n"
            f"Race: {card['race']}\n"
            f"{' | '.join(stats)}\n"
            f"Description: {desc}"
            f"{visual_info}"
        )
        
        # Check for local image match
        clean_card_name = card['name'].lower().strip()
        local_path = local_images_map.get(clean_card_name)
        
        if local_path:
            # Update database with local path
            try:
                update_card_local_image(card['id'], local_path)
            except Exception as e:
                print(f"Error updating DB for {card['name']}: {e}")
        
        metadata = {
            "id": card["id"],
            "name": card["name"],
            "type": card["type"],
            "image": card["card_images"][0]["image_url_small"],
            "local_image": local_path # Could be None
        }
        
        documents.append(Document(page_content=content, metadata=metadata))
    return documents

def create_index():
    try:
        cards_data = fetch_all_cards()
        local_images = get_local_images()
        visual_descs = get_visual_descriptions()
        print(f"Found {len(local_images)} local images and {len(visual_descs)} visual descriptions.")
        docs = process_cards(cards_data, local_images, visual_descs)
        
        print(f"Creating FAISS index with model '{EMBEDDING_MODEL}' (this may take a while)...")
        embeddings = OllamaEmbeddings(model="all-minilm:33m")
        
        # Split into smaller batches if needed, but FAISS handles lists well.
        # Reduce batch size to 100 to prevent Ollama from hanging on huge payloads
        batch_size = 100
        vectorstore = None
        
        total_batches = (len(docs) + batch_size - 1) // batch_size
        print(f"Total entries: {len(docs)} | Batch size: {batch_size} | Total batches: {total_batches}")

        for i in range(0, len(docs), batch_size):
            batch = docs[i:i + batch_size]
            current_batch_num = i//batch_size + 1
            print(f"[{current_batch_num}/{total_batches}] Processing cards {i} to {min(i + batch_size, len(docs))}...")
            if vectorstore is None:
                vectorstore = FAISS.from_documents(batch, embeddings)
            else:
                vectorstore.add_documents(batch)
            print(f"[{current_batch_num}/{total_batches}] Batch completed.")
        
        print(f"Saving index to {INDEX_PATH}...")
        vectorstore.save_local(INDEX_PATH)
        print("Success!")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_index()
