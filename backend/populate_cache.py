import json
import requests
from database import init_db, cache_card, get_connection
import sqlite3

def get_safe_connection():
    # Use a longer timeout to handle "database is locked"
    import os
    from database import DB_PATH
    return sqlite3.connect(DB_PATH, timeout=30)


def fetch_all_cards():
    print("Fetching all cards from YGOPRODeck API...")
    url = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()["data"]

def populate_cache():
    # 1. Initialize database (creates tables if they don't exist)
    print("Initializing database...")
    init_db()
    
    # 2. Fetch all cards
    try:
        cards = fetch_all_cards()
        print(f"Fetched {len(cards)} cards.")
    except Exception as e:
        print(f"Error fetching cards: {e}")
        return

    # 3. Save each card to card_cache
    print("Populating card_cache table...")
    conn = get_safe_connection()
    cursor = conn.cursor()
    
    count = 0
    for card in cards:
        card_id = card["id"]
        name = card["name"]
        # Save the full card data as JSON
        cursor.execute('INSERT OR REPLACE INTO card_cache (id, name, data) VALUES (?, ?, ?)', 
                       (card_id, name, json.dumps(card)))
        count += 1
        if count % 1000 == 0:
            print(f"Cached {count} cards...")
            conn.commit()
            
    conn.commit()
    conn.close()
    print(f"Successfully cached {count} cards in card_cache.")

if __name__ == "__main__":
    populate_cache()
