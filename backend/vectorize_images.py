import os
import time
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenCLIPEmbeddingFunction
from chromadb.utils.data_loaders import ImageLoader
from database import get_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PATH = os.path.join(BASE_DIR, "chromadb_images")
COLLECTION_NAME = "image_visual_index"

def vectorize_all_images():
    print("Connecting to database...")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, local_image FROM card_cache WHERE local_image IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No local images found in SQLite.")
        return

    print("Initializing ChromaDB and OpenCLIP (this might download a model on first run)...")
    client = PersistentClient(path=CHROMA_PATH)
    
    # We use OpenCLIP for image-to-image embeddings
    embedding_function = OpenCLIPEmbeddingFunction()
    data_loader = ImageLoader()

    # Get or create the collection
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        data_loader=data_loader,
        metadata={"hnsw:space": "cosine"}
    )

    try:
        existing_data = collection.get(include=[])
        existing_ids = set(existing_data['ids'])
    except Exception:
        existing_ids = set()

    # Filter out rows that are already processed
    rows_to_process = [r for r in rows if str(r[0]) not in existing_ids]

    if not rows_to_process:
        print("All images are already vectorized!")
        return

    print(f"Found {len(rows_to_process)} NEW images to vectorize (out of {len(rows)} total).")
    
    # We will process in batches to avoid OOM
    BATCH_SIZE = 100
    
    for i in range(0, len(rows_to_process), BATCH_SIZE):
        batch = rows_to_process[i:i + BATCH_SIZE]
        
        ids = []
        uris = []
        metadatas = []
        
        for card_id, name, local_image in batch:
            img_path = os.path.join(BASE_DIR, local_image)
            if os.path.exists(img_path):
                ids.append(str(card_id))
                uris.append(img_path)
                metadatas.append({"name": name, "card_id": card_id, "image_path": local_image})
        
        if uris:
            print(f"Adding batch {i} to {i + len(batch)} / {len(rows_to_process)}...")
            start_t = time.time()
            try:
                # Add images using their URIs. Chroma automatically handles reading and embedding.
                collection.add(
                    ids=ids,
                    uris=uris,
                    metadatas=metadatas
                )
                print(f"Batch completed in {time.time() - start_t:.2f} seconds.")
            except Exception as e:
                print(f"Error adding batch: {e}")
                
    print(f"✅ Vectorization complete! {len(rows_to_process)} new images processed.")

if __name__ == '__main__':
    vectorize_all_images()
