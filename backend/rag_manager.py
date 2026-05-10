import os

from dotenv import load_dotenv

import tools as tools_module
from rag_setup import setup_rag, setup_card_rag, get_visual_retriever, setup_image_rag

load_dotenv()

# These are set by init_all_rag() and can be imported by other modules.
rule_retriever   = None
card_retriever   = None
visual_retriever = None
image_rag_collection = None


def init_all_rag(rulebook_path: str) -> dict:
    """
    Initialise all RAG retrievers and inject them into the tools module.

    Returns a dict with keys 'rule', 'card', 'visual' mapping to the
    retriever objects (or None if initialisation failed).
    """
    global rule_retriever, card_retriever, visual_retriever, image_rag_collection

    # --- Rule RAG (PDF) ---
    print(f"[RAG] Loading rulebook from {rulebook_path}...")
    try:
        rule_retriever = setup_rag(rulebook_path)
        if rule_retriever:
            tools_module._rule_retriever = rule_retriever
            print("[RAG] [OK] Rulebook RAG loaded.")
    except Exception as e:
        print(f"[RAG] [ERROR] Error loading Rulebook RAG: {e}")
        rule_retriever = None

    # --- Card RAG (FAISS) ---
    print("[RAG] Loading card FAISS index...")
    try:
        card_retriever = setup_card_rag()
        if card_retriever:
            tools_module._card_retriever = card_retriever
            print("[RAG] [OK] Card RAG loaded.")
        else:
            print("[RAG] [WARNING] Card RAG index not found — card visual search disabled.")
    except Exception as e:
        print(f"[RAG] [ERROR] Error loading Card RAG: {e}")
        card_retriever = None

    # --- Visual RAG (ChromaDB) ---
    print("[RAG] Loading visual ChromaDB index...")
    try:
        visual_retriever = get_visual_retriever()
        if visual_retriever:
            print("[RAG] [OK] Visual RAG loaded.")
        else:
            print("[RAG] [WARNING] Visual RAG not available.")
    except Exception as e:
        print(f"[RAG] [ERROR] Error loading Visual RAG: {e}")
        visual_retriever = None

    # --- Image-to-Image Visual RAG (OpenCLIP ChromaDB) ---
    print("[RAG] Loading OpenCLIP Image RAG index...")
    try:
        image_rag_collection = setup_image_rag()
        if image_rag_collection:
            print("[RAG] [OK] Image RAG loaded.")
        else:
            print("[RAG] [WARNING] Image RAG not available.")
    except Exception as e:
        print(f"[RAG] [ERROR] Error loading Image RAG: {e}")
        image_rag_collection = None

    return {
        "rule":   rule_retriever,
        "card":   card_retriever,
        "visual": visual_retriever,
        "image":  image_rag_collection,
    }
