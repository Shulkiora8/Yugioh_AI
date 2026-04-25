import sqlite3
import json
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DATABASE_PATH", "yugioh_helper.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Table for users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table for stored/saved decks (the ones the agent or user saves)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            main_deck TEXT NOT NULL, 
            extra_deck TEXT NOT NULL,
            side_deck TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, name)
        )
    ''')
    
    # Table for local archetypes database (migrated from decks_data.json)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS local_decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_name TEXT NOT NULL,
            archetype TEXT,
            url TEXT,
            main_deck TEXT, -- JSON string
            extra_deck TEXT, -- JSON string
            side_deck TEXT  -- JSON string
        )
    ''')
    
    # Table for card cache
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS card_cache (
            id INTEGER PRIMARY KEY, -- Use YGOPRODeck card ID
            name TEXT NOT NULL,
            data TEXT NOT NULL, -- Full JSON data
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def create_user(username, password_hash):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password_hash))
        conn.commit()
        user_id = cursor.lastrowid
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, password FROM users WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "password": row[2]}
    return None

def save_user_deck(user_id, name, main, extra, side):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO saved_decks (user_id, name, main_deck, extra_deck, side_deck) 
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, name, json.dumps(main), json.dumps(extra), json.dumps(side)))
    conn.commit()
    conn.close()

def get_saved_decks(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, main_deck, extra_deck, side_deck FROM saved_decks WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{
        "name": r[0], 
        "main": json.loads(r[1]),
        "extra": json.loads(r[2]),
        "side": json.loads(r[3])
    } for r in rows]

def delete_user_deck(user_id, name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM saved_decks WHERE user_id = ? AND name = ?', (user_id, name))
    conn.commit()
    conn.close()

def rename_user_deck(user_id, old_name, new_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE saved_decks SET name = ? WHERE user_id = ? AND name = ?', (new_name, user_id, old_name))
    conn.commit()
    conn.close()

def add_local_deck(deck_name, archetype, url, main, extra, side):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO local_decks (deck_name, archetype, url, main_deck, extra_deck, side_deck)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (deck_name, archetype, url, json.dumps(main), json.dumps(extra), json.dumps(side)))
    conn.commit()
    conn.close()

def search_decks_by_archetype(query):
    conn = get_connection()
    cursor = conn.cursor()
    q = f"%{query}%"
    cursor.execute('''
        SELECT deck_name, archetype, main_deck, extra_deck, side_deck 
        FROM local_decks 
        WHERE deck_name LIKE ? OR archetype LIKE ?
    ''', (q, q))
    rows = cursor.fetchall()
    conn.close()
    return [{
        "name": r[0],
        "archetype": r[1],
        "cards": {
            "Main Deck": json.loads(r[2]),
            "Extra Deck": json.loads(r[3]),
            "Side Deck": json.loads(r[4])
        }
    } for r in rows]

def cache_card(card_id, name, data):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO card_cache (id, name, data) VALUES (?, ?, ?)', 
                   (card_id, name, json.dumps(data)))
    conn.commit()
    conn.close()

def get_cached_card(name=None, card_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    if card_id:
        cursor.execute('SELECT data FROM card_cache WHERE id = ?', (card_id,))
    else:
        cursor.execute('SELECT data FROM card_cache WHERE name = ?', (name,))
    row = cursor.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
