import requests
import os
import sqlite3
import json
import contextvars
from langchain.tools import tool
from typing import List, Optional, Dict

from database import search_decks_by_archetype, save_user_deck, get_connection
import random
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

# Context variables to track state in the current thread
session_id_context: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="default")
user_id_context: contextvars.ContextVar[int] = contextvars.ContextVar("user_id", default=0)

# Shared state - stored per session ID
_last_decks: Dict[str, dict] = {}

# Shared state for retrievers (initialized from main/api)
_card_retriever = None
_rule_retriever = None
_visual_retriever = None

@tool
def card_search(query: str) -> str:
    """Search for a Yu-Gi-Oh card by exact name, fuzzy name, OR by its effect/description text.
    IMPORTANT: The database is in English. Always translate the user's description into English keywords before searching.
    Returns card details such as name, type, description, stats, and image URL.
    """
    global _card_retriever
    print(f"Searching for card: {query}")
    if _card_retriever:
        try:
            docs = _card_retriever.invoke(query)
            if docs:
                results = []
                for doc in docs[:4]: # Limit to top 3 results
                    content = doc.page_content
                    # Remove Visual Appearance to save tokens and prevent agent confusion
                    if "Visual Appearance:" in content:
                        content = content.split("Visual Appearance:")[0].strip()
                    # Try to find image in metadata
                    image_url = doc.metadata.get("image_url") or doc.metadata.get("card_image") or doc.metadata.get("image")
                    if image_url:
                        content += f"\nImage: {image_url}"
                    results.append(content)
                return "\n---\n".join(results)
        except Exception as e:
            print(f"RAG search error: {e}")

    # Fallback to API
    url = f"https://db.ygoprodeck.com/api/v7/cardinfo.php?fname={query}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if "data" in data:
            cards = data["data"][:3] # Limit to top 3 results
            results = []
            for card in cards:
                img_url = card['card_images'][0]['image_url'] if card.get('card_images') else "No image available"
                card_info = (
                    f"Name: {card['name']}\n"
                    f"Type: {card['type']}\n"
                    f"Description: {card['desc']}\n"
                    f"Image: {img_url}\n"
                )
                if "atk" in card:
                    card_info += f"ATK: {card['atk']} / DEF: {card['def']}\n"
                if "level" in card:
                    card_info += f"Level/Rank: {card['level']}\n"
                results.append(card_info)
            return "\n---\n".join(results)
        return "No cards found with that name."
    except Exception as e:
        return f"Error searching for card: {str(e)}"

@tool
def save_deck(deck_name: str, card_list: List[str]) -> str:
    """Saves a list of card names to the database.
    The deck_name is the name of the deck.
    card_list is a list of strings representing card names.
    """
    global _last_decks
    
    try:
        # Use context variables
        session_id = session_id_context.get()
        user_id = user_id_context.get()
        
        save_user_deck(user_id, deck_name, card_list, [], [])
        
        # Store the deck for the specific session
        _last_decks[session_id] = {
            "name": deck_name,
            "cards": card_list,
            "main": card_list,
            "extra": [],
            "side": []
        }
        
        return f"Deck '{deck_name}' successfully saved to database."
    except Exception as e:
        return f"Error saving deck: {str(e)}"


# Track shown decks per session to avoid repetition
_shown_decks: dict = {}

@tool
def search_local_decks(query: str) -> str:
    """Search for a deck in the local database by name or archetype.
    Examples of valid queries: 'Branded', 'Dark Magician', 'Yummy', 'Hero', Dracotail.
    Automatically picks a random deck, saves it to the database, and returns a summary.
    """
    global _shown_decks

    try:
        matches = search_decks_by_archetype(query)

        if not matches:
            return f"No decks found for '{query}' in local database."

        # Filter out already shown decks; reset if all have been shown
        shown_key = query.lower()
        shown = _shown_decks.get(shown_key, set())
        available = [m for m in matches if m["name"] not in shown]
        if not available:
            shown = set()
            _shown_decks[shown_key] = shown
            available = matches

        # Pick one at random
        deck_info = random.choice(available)
        name = deck_info["name"]
        shown.add(name)
        _shown_decks[shown_key] = shown

        main  = deck_info["cards"].get("Main Deck", [])
        extra = deck_info["cards"].get("Extra Deck", [])
        side  = deck_info["cards"].get("Side Deck", [])
        all_cards = main + extra + side

        # Auto-save to SQLite — pass separate sections
        session_id = session_id_context.get()
        user_id = user_id_context.get()
        
        save_user_deck(user_id, name, main, extra, side)
        
        # Store full section data for the API to consume
        _last_decks[session_id] = {
            "name": name,
            "cards": all_cards,
            "main": main,
            "extra": extra,
            "side": side,
        }

        return (
            f"Deck '{name}' ({deck_info['archetype']}) found and saved automatically. "
            f"Main: {len(main)} cards | Extra: {len(extra)} cards | Side: {len(side)} cards. "
            f"Tell the user the deck is ready."
        )

    except Exception as e:
        return f"Error reading local database: {str(e)}"

@tool
def generate_custom_deck(theme: str) -> str:
    """Generates a custom, random Yu-Gi-Oh! deck based on a specific theme, race, or attribute.
    It builds a legal 40-card main deck and 15-card extra deck and saves it.
    Use this when the user asks for a deck of a certain generic type (e.g. 'Dragon deck', 'Water deck').
    """
    global _last_decks
    
    try:
        from database import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        q = f"%{theme}%"
        # Optimized search: using columns and raw JSON data blob search
        cursor.execute('''
            SELECT data FROM card_cache 
            WHERE name LIKE ? 
               OR data LIKE ?
            LIMIT 1000
        ''', (q, q))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return f"No cards found matching the theme '{theme}'. Cannot build deck."
            
        all_matches = [json.loads(r[0]) for r in rows]
        
        # Categorize
        main_monsters = []
        spells = []
        traps = []
        extra_monsters = []
        
        extra_types = ["fusion monster", "synchro monster", "xyz monster", "link monster"]
        
        for c in all_matches:
            ctype = c.get("type", "").lower()
            if any(t in ctype for t in extra_types):
                extra_monsters.append(c["name"])
            elif "spell card" in ctype:
                spells.append(c["name"])
            elif "trap card" in ctype:
                traps.append(c["name"])
            elif "monster" in ctype:
                main_monsters.append(c["name"])
                
        # Build logic: max 3 copies of each card.
        multi_m = main_monsters * 3
        multi_s = spells * 3
        multi_t = traps * 3
        
        random.shuffle(multi_m)
        random.shuffle(multi_s)
        random.shuffle(multi_t)
        
        main_deck = multi_m[:20] + multi_s[:10] + multi_t[:10]
        
        leftovers = multi_m[20:] + multi_s[10:] + multi_t[10:]
        random.shuffle(leftovers)
        
        while len(main_deck) < 40 and leftovers:
            main_deck.append(leftovers.pop())
            
        if len(main_deck) < 40:
            return f"Not enough unique cards to build a 40-card deck for theme '{theme}'. Only found {len(main_deck)} slots."
            
        multi_e = extra_monsters * 3
        random.shuffle(multi_e)
        extra_deck = multi_e[:15]
        
        deck_name = f"{theme.capitalize()} Custom Deck"
        
        session_id = session_id_context.get()
        user_id = user_id_context.get()
        
        save_user_deck(user_id, deck_name, main_deck, extra_deck, [])
        
        _last_decks[session_id] = {
            "name": deck_name,
            "cards": main_deck + extra_deck,
            "main": main_deck,
            "extra": extra_deck,
            "side": [],
        }
        
        return f"Custom {theme} deck '{deck_name}' successfully generated and saved! Main Deck: {len(main_deck)} cards. Extra Deck: {len(extra_deck)} cards. Tell the user it's ready!"
        
    except Exception as e:
        return f"Error generating deck: {str(e)}"



# Visual RAG Tool
_visual_retriever = None

@tool
def visual_card_search(description: str) -> str:
    """Search for a Yu-Gi-Oh card by its visual appearance (colors, character, background).
    Input should be a detailed visual description of the card.
    Returns the most likely card matches based on visual similarity.
    """
    global _visual_retriever
    if _visual_retriever is None:
        try:
            # Lazy import to avoid circular dependency
            from rag_setup import get_visual_retriever
            _visual_retriever = get_visual_retriever()
        except Exception as e:
            return f"Visual search index not available: {e}"
    
    try:
        docs = _visual_retriever.invoke(description)
        if not docs:
            return "No visually similar cards found."
        
        results = []
        for doc in docs:
            name = doc.metadata.get("name", "Unknown")
            results.append(f"Identified Match: {name}")
        return "\n".join(results)
    except Exception as e:
        return f"Error performing visual search: {e}"

@tool
def rule_lookup(query: str) -> str:
    """Useful for looking up official Yu-Gi-Oh rules from the rulebook PDF. 
    Use this for mechanics, phases, or gameplay questions.
    """
    global _rule_retriever
    if not _rule_retriever:
        return "Rulebook is not available at the moment."
    
    try:
        docs = _rule_retriever.invoke(query)
        # Limit to top 3 results to avoid context flooding and ensure quality
        return "\n\n".join([doc.page_content for doc in docs[:3]])
    except Exception as e:
        return f"Error looking up rules: {e}"

# Export all tools in a single list for easy access
def get_all_tools():
    return [card_search, save_deck, search_local_decks, generate_custom_deck, visual_card_search, rule_lookup]
