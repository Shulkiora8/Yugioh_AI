import os
import time
import uuid
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenCLIPEmbeddingFunction
from chromadb.utils.data_loaders import ImageLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PATH = os.path.join(BASE_DIR, "chromadb_images")
IMAGENES_DIR = os.path.join(BASE_DIR, "imagenes")
COLLECTION_NAME = "image_visual_index"

def vectorize_missing_images():
    print("Initializing ChromaDB and OpenCLIP...")
    client = PersistentClient(path=CHROMA_PATH)
    
    embedding_function = OpenCLIPEmbeddingFunction()
    data_loader = ImageLoader()

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        data_loader=data_loader,
        metadata={"hnsw:space": "cosine"}
    )

    print("Fetching existing collection data...")
    try:
        existing_data = collection.get(include=["metadatas"])
        existing_names = set()
        for m in existing_data['metadatas']:
            if m and "name" in m:
                existing_names.add(m["name"])
    except Exception as e:
        print(f"Error fetching existing data: {e}")
        existing_names = set()

    print(f"Found {len(existing_names)} images already in ChromaDB.")

    files = [f for f in os.listdir(IMAGENES_DIR) if f.endswith(".jpg")]
    print(f"Total images in folder: {len(files)}")

    missing_files = []
    for f in files:
        name = f[:-4]
        if name not in existing_names:
            missing_files.append((name, os.path.join(IMAGENES_DIR, f)))

    if not missing_files:
        print("✅ No missing images to vectorize. All are in ChromaDB.")
        return

    print(f"Found {len(missing_files)} missing images. Starting vectorization...")

    BATCH_SIZE = 100
    for i in range(0, len(missing_files), BATCH_SIZE):
        batch = missing_files[i:i + BATCH_SIZE]
        
        ids = []
        uris = []
        metadatas = []
        
        for name, full_path in batch:
            # Generate a unique ID that won't collide with existing numeric card_ids
            unique_id = f"missing_{uuid.uuid4().hex[:8]}"
            local_rel_path = f"imagenes/{name}.jpg"
            
            ids.append(unique_id)
            uris.append(full_path)
            # Use card_id = 0 for missing ones
            metadatas.append({"name": name, "card_id": 0, "image_path": local_rel_path})
        
        if uris:
            print(f"Adding batch {i} to {i + len(batch)} / {len(missing_files)}...")
            start_t = time.time()
            try:
                collection.add(
                    ids=ids,
                    uris=uris,
                    metadatas=metadatas
                )
                print(f"Batch completed in {time.time() - start_t:.2f} seconds.")
            except Exception as e:
                print(f"Error adding batch: {e}")
                
    print(f"✅ Vectorization complete! {len(missing_files)} missing images processed.")

if __name__ == '__main__':
    vectorize_missing_images()
