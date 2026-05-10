import sqlite3
import json
import os

DB_PATH = 'backend/yugioh_helper.db'

def check_cyberse():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    theme = "Cyberse"
    q = f"%{theme}%"
    cursor.execute('''
        SELECT count(*) FROM card_cache 
        WHERE name LIKE ? 
           OR data LIKE ?
    ''', (q, q))
    
    count = cursor.fetchone()[0]
    print(f"Cards found for theme '{theme}': {count}")
    
    if count > 0:
        cursor.execute('''
            SELECT name, data FROM card_cache 
            WHERE name LIKE ? 
               OR data LIKE ?
            LIMIT 5
        ''', (q, q))
        for row in cursor.fetchall():
            print(f" - {row[0]}")
            
    conn.close()

if __name__ == "__main__":
    check_cyberse()
