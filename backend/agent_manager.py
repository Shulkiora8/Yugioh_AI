"""
agent_manager.py — LangChain agent lifecycle management.

Exports:
    get_agent(session_id) -> AgentExecutor
    create_agent(session_id) -> AgentExecutor
    session_agents           (dict used for per-session caching)
"""
import os
from typing import Dict

from langchain_classic.agents import initialize_agent, AgentType, AgentExecutor
from langchain_classic.memory import ConversationBufferMemory
from langchain_ollama import ChatOllama

from tools import get_all_tools
from config import MODEL_NAME

# Per-session agent cache
session_agents: Dict[str, AgentExecutor] = {}

AGENT_PREFIX = """You are a Yu-Gi-Oh! expert AI assistant. Answer in the same language as the user.

    Use tools to find information. After getting a tool's result, ALWAYS write a detailed explanation for the user based on what you found.

    Available tools and when to use them:
    - card_search: ALWAYS use this FIRST when the user asks for a specific card, its stats, its effects, or if they ask to identify a card based on what its effect does (e.g., "what card lets me draw 2 cards?"). IMPORTANT: The database is in English. Always translate the search query to English keywords (e.g., "draw 2 cards", "white dragon") before calling this tool. NEVER guess card effects without searching.
    - rule_lookup: When the user asks about game rules or mechanics.
    - search_local_decks: ALWAYS use this FIRST when the user asks for a deck by name, archetype, or strategy (e.g., "Branded deck", "Dark Magician deck", "Yummy deck", "Hero").
    - generate_custom_deck: ONLY use this as a fallback if search_local_decks fails, or if the user asks for a generic theme (e.g., "Water deck", "Dragon deck").

    IMPORTANT: If a tool returns an 'Image' URL, you MUST include that image in your final answer using Markdown syntax: ![Card Name](URL).

    IMPORTANT: After using a tool and receiving an Observation, you MUST provide a Final Answer with the full information. Never leave the answer empty.
    """


def create_agent(session_id: str) -> AgentExecutor:
    """Create a new LangChain agent for the given session ID."""
    llm    = ChatOllama(model=MODEL_NAME, temperature=0.4, num_ctx=8192)
    tools  = get_all_tools()
    memory = ConversationBufferMemory(
        memory_key="chat_history", return_messages=True, output_key="output"
    )
    return initialize_agent(
        tools,
        llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        agent_kwargs={"prefix": AGENT_PREFIX},
        memory=memory,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5,
        return_intermediate_steps=True,
    )


def get_agent(session_id: str = "default") -> AgentExecutor:
    """Return a cached agent for the session, creating one if needed."""
    if session_id not in session_agents:
        session_agents[session_id] = create_agent(session_id)
    return session_agents[session_id]
