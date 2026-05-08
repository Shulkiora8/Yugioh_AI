import os
import requests
import time
from concurrent.futures import ThreadPoolExecutor

IMAGES_DIR = "imagenes"
API_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"

if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

def download_image(card):
    name = card["name"]
    # Clean name for filesystem
    clean_name = name.replace("/", "-").replace(":", "-").replace("?", "").replace("*", "").replace("\"", "").replace("<", "").replace(">", "").replace("|", "")
    
    # We'll use the small image to save space and time, but can be changed to image_url
    url = card["card_images"][0]["image_url"] 
    ext = os.path.splitext(url)[1]
    filename = f"{clean_name}{ext}"
    filepath = os.path.join(IMAGES_DIR, filename)

    if os.path.exists(filepath):
        return False # Skip if exists

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"Error downloading {name}: {e}")
    return False

def main():
    print("Fetching card data...")
    response = requests.get(API_URL)
    cards = response.json()["data"]
    total = len(cards)
    print(f"Total cards found: {total}")

    print(f"Starting download to '{IMAGES_DIR}' folder...")
    downloaded = 0
    skipped = 0
    
    # Use ThreadPoolExecutor for faster concurrent downloads
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(download_image, cards))
        
    downloaded = sum(1 for r in results if r is True)
    skipped = sum(1 for r in results if r is False)

    print(f"\nFinished!")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped (already exists): {skipped}")

if __name__ == "__main__":
    main()
