import os
import ollama
import sqlite3
import json
import base64
from database import get_connection, update_card_visual_description, init_db

# Configuration
VISION_MODEL = "moondream"
IMAGES_DIR = "imagenes"

def get_cards_needing_description():
    conn = get_connection()
    cursor = conn.cursor()
    # We only process cards that have a local image but no visual description yet
    cursor.execute("SELECT id, name, local_image FROM card_cache WHERE local_image IS NOT NULL AND visual_description IS NULL")
    rows = cursor.fetchall()
    conn.close()
    return rows

def generate_description(image_path):
    if not os.path.exists(image_path):
        return None
    
    try:
        with open(image_path, "rb") as f:
            content = f.read()
            
        response = ollama.generate(
            model=VISION_MODEL,
            prompt="Describe this image in detail. Focus on the character, colors, and background.",
            images=[content],
            stream=False
        )
        return response.get('response', '').strip()
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None

def main():
    init_db()
    cards = get_cards_needing_description()
    total = len(cards)
    print(f"Found {total} cards needing visual descriptions.")

    for i, (card_id, name, local_path) in enumerate(cards):
        print(f"[{i+1}/{total}] Generating description for {name}...")
        description = generate_description(local_path)
        if description:
            update_card_visual_description(card_id, description)
            print(f"Done: {description[:50]}...")
        else:
            print(f"Failed to generate description for {name}")

if __name__ == "__main__":
    main()
