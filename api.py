import os
import requests as http_requests
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional, Dict
from main import setup_rag, card_search, save_deck, search_local_decks
from database import (
    get_cached_card, cache_card, get_saved_decks, save_user_deck, 
    delete_user_deck, rename_user_deck, create_user, get_user_by_username
)
import tools as tools_module
from langchain_ollama import ChatOllama
from langchain_classic.agents import initialize_agent, AgentType, AgentExecutor
from langchain_core.tools import Tool
from fastapi.middleware.cors import CORSMiddleware
from langchain_classic.memory import ConversationBufferMemory
import warnings
from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt
from dotenv import load_dotenv
from tools import session_id_context 

load_dotenv()
warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- Security Config ---
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-it-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 1 week

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def verify_password(plain_password, hashed_password):
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password):
    # Bcrypt has a 72-byte limit. We truncate to ensure no error, 
    # though usually user passwords are shorter.
    pwd_bytes = password.encode('utf-8')[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_username(username)
    if user is None:
        raise credentials_exception
    return user

MODEL_NAME = os.getenv("MODEL_NAME", "qwen3.6:35b")
RULEBOOK_PATH = os.getenv("RULEBOOK_PATH", "SD_RuleBook_EN_10.pdf")

app = FastAPI(title="Yu-Gi-Oh Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Schemas ---
class UserCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class ChatRequest(BaseModel):
    message: str

class DeckSaveRequest(BaseModel):
    name: str
    main: List[dict]
    extra: List[dict]
    side: List[dict]

# --- Auth Endpoints ---

@app.post("/register", response_model=Token)
def register(user: UserCreate):
    db_user = get_user_by_username(user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user_id = create_user(user.username, hashed_password)
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

# --- Agent Management ---
# Store agents per session ID
session_agents: Dict[str, AgentExecutor] = {}

def create_agent(session_id: str):
    # Note: For multi-user, we might want to pass user info to agent tools
    retriever = setup_rag(RULEBOOK_PATH)
    
    def rule_lookup_func(query: str) -> str:
        docs = retriever.invoke(query)
        return "\n\n".join([doc.page_content for doc in docs])

    rule_tool = Tool(
        name="rule_lookup",
        func=rule_lookup_func,
        description="Useful for looking up official Yu-Gi-Oh rules from the rulebook PDF."
    )
    
    llm = ChatOllama(model=MODEL_NAME, temperature=0.7)
    tools = [rule_tool, card_search, save_deck, search_local_decks]
    
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    
    prefix = """You are a Yu-Gi-Oh expert AI assistant. 
    You must ALWAYS respond to the user in ENGLISH.
    
    When the user asks you to build or make a deck:
    - If the user asks for a 'good' deck, pick one of these names: 'Branded Dracotail', 'Radiant Typhoon Dracotail', 'Fiendsmith Yummy', 'Azamina Yummy', 'K9 Vanquish Soul'.
    - If the user asks for the 'worst' deck, pick one of these names: 'Hero', 'Unchained Yubel', 'K9 Solfachord', 'Fiendsmith Mitsurugi Megalith', 'Traptrix'.
    - For specific archetypes, use the name requested.
    
    STEP 1 - Call 'search_local_decks' with the name.
    STEP 2 - Call 'save_deck' with the deck name and ALL cards returned.
    STEP 3 - Provide a FINAL ANSWER in ENGLISH confirming the deck is ready in the editor.
    
    Always finish your chain with a 'Final Answer' to the user.
    """

    agent = initialize_agent(
        tools,
        llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        agent_kwargs={'prefix': prefix},
        memory=memory,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10
    )
    return agent

def get_agent(session_id: str = "default"):
    if session_id not in session_agents:
        session_agents[session_id] = create_agent(session_id)
    return session_agents[session_id]

# --- Endpoints ---

@app.post("/chat")
async def chat(request: ChatRequest, req: Request, current_user: dict = Depends(get_current_user)):
    try:
        # Get session ID from headers or use default
        session_id = req.headers.get("x-session-id", "default")
        
        # Set the session ID and user ID in the context for this thread
        s_token = session_id_context.set(session_id)
        u_token = tools_module.user_id_context.set(current_user["id"])
        
        try:
            agent = get_agent(session_id)
            
            # Clear previous deck for this session before running
            tools_module._last_decks[session_id] = {"name": "", "cards": []}
            
            response = agent.run(request.message)
            
            # Check if a deck was stored for this session
            deck_data = None
            last = tools_module._last_decks.get(session_id, {})
            if last.get("cards"):

                def fetch_card_objects(names: list) -> list:
                    result = []
                    for card_name in names:
                        try:
                            c = get_cached_card(name=card_name)
                            if not c:
                                url = f"https://db.ygoprodeck.com/api/v7/cardinfo.php?name={card_name}"
                                r = http_requests.get(url, timeout=5)
                                cdata = r.json().get("data", [])
                                if cdata:
                                    c = cdata[0]
                                    cache_card(c["id"], c["name"], c)
                            if c:
                                result.append({
                                    "id": c["id"],
                                    "name": c["name"],
                                    "type": c["type"],
                                    "desc": c.get("desc", ""),
                                    "atk": c.get("atk"),
                                    "def": c.get("def"),
                                    "level": c.get("level"),
                                    "attribute": c.get("attribute", ""),
                                    "image": c["card_images"][0]["image_url_small"],
                                    "card_images": c["card_images"]
                                })
                        except Exception:
                            pass
                    return result

                # Use pre-separated sections if available (set by search_local_decks)
                if "main" in last and "extra" in last:
                    deck_data = {
                        "name": last["name"],
                        "main":  fetch_card_objects(last["main"]),
                        "extra": fetch_card_objects(last["extra"]),
                        "side":  fetch_card_objects(last.get("side", [])),
                    }
                else:
                    # Fallback: split by card type (save_deck path)
                    extra_types = {"fusion", "synchro", "xyz", "link"}
                    main_cards, extra_cards = [], []
                    for card_obj in fetch_card_objects(last["cards"]):
                        if any(t in card_obj["type"].lower() for t in extra_types):
                            extra_cards.append(card_obj)
                        else:
                            main_cards.append(card_obj)
                    deck_data = {
                        "name": last["name"],
                        "main": main_cards,
                        "extra": extra_cards,
                        "side": [],
                    }


            return {"response": response, "deck_data": deck_data}
        finally:
            # Reset context variables after request
            session_id_context.reset(s_token)
            tools_module.user_id_context.reset(u_token)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cards")
def search_cards(q: str = ""):
    base_url = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
    url = f"{base_url}?fname={q}" if q else base_url
    try:
        response = http_requests.get(url, timeout=10)
        data = response.json()
        if "data" in data:
            for card in data["data"][:50]:
                cache_card(card["id"], card["name"], card)
        return data
    except Exception as e:
        return {"data": []}

@app.get("/")
def root():
    return {"status": "alive", "service": "Yu-Gi-Oh Assistant API"}

@app.get("/decks")
def list_decks(current_user: dict = Depends(get_current_user)):
    print(f"Fetching saved decks for user {current_user['username']}...")
    decks = get_saved_decks(current_user["id"])
    for d in decks:
        first_card_name = None
        if d["main"]: first_card_name = d["main"][0]["name"] if isinstance(d["main"][0], dict) else d["main"][0]
        elif d["extra"]: first_card_name = d["extra"][0]["name"] if isinstance(d["extra"][0], dict) else d["extra"][0]
        elif d["side"]: first_card_name = d["side"][0]["name"] if isinstance(d["side"][0], dict) else d["side"][0]
        
        d["image"] = None
        if first_card_name:
            c = get_cached_card(name=first_card_name)
            if not c:
                try:
                    url = f"https://db.ygoprodeck.com/api/v7/cardinfo.php?name={first_card_name}"
                    r = http_requests.get(url, timeout=5)
                    cdata = r.json().get("data", [])
                    if cdata:
                        c = cdata[0]
                        cache_card(c["id"], c["name"], c)
                except Exception as e:
                    print(f"Error caching card {first_card_name}: {e}")
            
            if c:
                d["image"] = c["card_images"][0].get("image_url") or c["card_images"][0].get("image_url_small")
    print(f"Returning {len(decks)} decks.")
    return decks

@app.delete("/decks/{name}")
def delete_deck(name: str, current_user: dict = Depends(get_current_user)):
    print(f"Deleting deck: {name} for user {current_user['username']}")
    delete_user_deck(current_user["id"], name)
    return {"status": "success"}

@app.patch("/decks/{name}")
async def rename_deck(name: str, request: Request, current_user: dict = Depends(get_current_user)):
    body = await request.json()
    new_name = body.get("name")
    print(f"Renaming deck '{name}' to '{new_name}' for user {current_user['username']}")
    if not new_name:
        raise HTTPException(status_code=400, detail="New name required")
    rename_user_deck(current_user["id"], name, new_name)
    return {"status": "success"}

class StructuredDeckSaveRequest(BaseModel):
    name: str
    main: List[str]
    extra: List[str]
    side: List[str]

@app.post("/save-deck")
async def save_structured_deck(request: StructuredDeckSaveRequest, current_user: dict = Depends(get_current_user)):
    print(f"Saving structured deck: {request.name} for user {current_user['username']}")
    save_user_deck(current_user["id"], request.name, request.main, request.extra, request.side)
    return {"status": "success"}

@app.get("/decks/{name}")
def get_deck_details(name: str, current_user: dict = Depends(get_current_user)):
    decks = get_saved_decks(current_user["id"])
    deck = next((d for d in decks if d["name"] == name), None)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    def fetch_card_objects(names: list) -> list:
        result = []
        for card_name in names:
            try:
                c = get_cached_card(name=card_name)
                if not c:
                    url = f"https://db.ygoprodeck.com/api/v7/cardinfo.php?name={card_name}"
                    r = http_requests.get(url, timeout=5)
                    cdata = r.json().get("data", [])
                    if cdata:
                        c = cdata[0]
                        cache_card(c["id"], c["name"], c)
                if c:
                    result.append({
                        "id": c["id"],
                        "name": c["name"],
                        "type": c["type"],
                        "desc": c.get("desc", ""),
                        "atk": c.get("atk"),
                        "def": c.get("def"),
                        "level": c.get("level"),
                        "attribute": c.get("attribute", ""),
                        "image": c["card_images"][0]["image_url_small"],
                        "card_images": c["card_images"]
                    })
            except Exception:
                pass
        return result

    return {
        "name": deck["name"],
        "main": fetch_card_objects(deck["main"]),
        "extra": fetch_card_objects(deck["extra"]),
        "side": fetch_card_objects(deck["side"])
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
