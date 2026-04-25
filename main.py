import os
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
from dotenv import load_dotenv
from langchain_core.tools import Tool
from langchain_ollama import ChatOllama
from langchain_classic.agents import initialize_agent, AgentType
from rag_setup import setup_rag
from tools import card_search, save_deck, search_local_decks

load_dotenv()

def main():
    print("Welcome to the Yu-Gi-Oh AI Assistant!")
    
    # 1. Setup RAG
    pdf_path = "SD_RuleBook_EN_10.pdf"
    try:
        retriever = setup_rag(pdf_path)
    except Exception as e:
        print(f"Failed to setup RAG: {e}")
        return

    # 2. Define Rule Lookup Tool
    def rule_lookup_func(query: str) -> str:
        docs = retriever.invoke(query)
        return "\n\n".join([doc.page_content for doc in docs])

    rule_tool = Tool(
        name="rule_lookup",
        func=rule_lookup_func,
        description="Useful for looking up official Yu-Gi-Oh rules from the rulebook PDF. Use this for any gameplay mechanics, card types, or rule questions."
    )

    # 3. Initialize Agent
    llm = ChatOllama(model="qwen3.6:35b", temperature=0)
    tools = [rule_tool, card_search, save_deck, search_local_decks]
    
    agent = initialize_agent(
        tools,
        llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True
    )

    print("\nAssistant ready! You can ask about rules, search for cards, or ask me to build and save a deck.")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        
        try:
            # Using invoke instead of run to follow modern LangChain practices
            response = agent.invoke({"input": user_input})
            print(f"\nAI: {response['output']}\n")
        except Exception as e:
            print(f"\nError: {e}\n")

if __name__ == "__main__":
    main()


#preguntarle a Alejandro que opina de usar hilos para multiples consultas de varios usuarios