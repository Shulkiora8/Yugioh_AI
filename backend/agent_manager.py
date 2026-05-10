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
    - card_search: Use this to find cards by NAME or EFFECT text (e.g., "Blue-Eyes White Dragon", "draw 2 cards"). ALWAYS translate keywords to English.
    - visual_card_search: Use this ONLY when the user describes what a card LOOKS like (e.g., "a dragon with blue eyes", "a warrior in red armor") but doesn't know the name or effect.
    - rule_lookup: Use this for game rules, phases, or mechanics.
    - search_local_decks: Use this for decks by archetype or name (e.g., "Branded", "Dark Magician").
    - generate_custom_deck: Use this to build a new deck based on a broad theme (e.g., "Dragon", "Water").
"""

AGENT_SUFFIX = """
    To use a tool, you MUST use the following format:

    Thought: Do I need to use a tool? Yes
    Action: 
    ```json
    {{
      "action": "tool_name",
      "action_input": {{
        "parameter_name": "value"
      }}
    }}
    ```
    Observation: the result of the tool

    When you have a final answer for the user, or if you do not need to use a tool, you MUST use the following format:

    Thought: Do I need to use a tool? No
    Action:
    ```json
    {{
      "action": "Final Answer",
      "action_input": "Your final response to the user here, in the same language they used."
    }}
    ```

    IMPORTANT: Always provide a detailed Final Answer. If you generate a deck, explain to the user that it's ready and where they can find it.
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
        agent_kwargs={
            "prefix": AGENT_PREFIX,
            "suffix": AGENT_SUFFIX
        },
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
