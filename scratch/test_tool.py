import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from tools import generate_custom_deck, session_id_context, user_id_context
import database

# Set up environment
os.environ["DATABASE_PATH"] = "backend/yugioh_helper.db"

def test_tool():
    # Set context
    s_token = session_id_context.set("test_session")
    u_token = user_id_context.set(1) # Assume user 1 exists
    
    print("Testing generate_custom_deck with 'Cyberse'...")
    try:
        result = generate_custom_deck.invoke({"theme": "Cyberse"})
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session_id_context.reset(s_token)
        user_id_context.reset(u_token)

if __name__ == "__main__":
    test_tool()
