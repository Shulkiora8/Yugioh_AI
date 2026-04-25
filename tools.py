import requests
import os
import json
import contextvars
from langchain.tools import tool
from typing import List, Optional, Dict

from database import search_decks_by_archetype, save_user_deck
import random

# Context variables to track state in the current thread
session_id_context: contextvars.ContextVar[str] = contextvars.ContextVar("session_id", default="default")
user_id_context: contextvars.ContextVar[int] = contextvars.ContextVar("user_id", default=0)

# Shared state - stored per session ID
_last_decks: Dict[str, dict] = {}

@tool
def card_search(query: str) -> str:
    """Search for a Yu-Gi-Oh card by name or fuzzy name using the YGOPRODeck API.
    Returns card details such as name, type, description, and stats.
    """
    url = f"https://db.ygoprodeck.com/api/v7/cardinfo.php?fname={query}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if "data" in data:
            cards = data["data"][:5] # Limit to top 5 results
            results = []
            for card in cards:
                card_info = (
                    f"Name: {card['name']}\n"
                    f"Type: {card['type']}\n"
                    f"Description: {card['desc']}\n"
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



# We will define the rule_lookup tool dynamically in main.py to pass the retriever
