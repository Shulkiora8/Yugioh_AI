import os
import json
import base64
import warnings
from datetime import datetime
import uvicorn
import ollama
from PIL import Image
import io
import requests as http_requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, Depends, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from database import (
    get_cached_card, cache_card, get_saved_decks, save_user_deck,
    delete_user_deck, rename_user_deck, create_user, get_user_by_username,
    get_card_by_exact_name,
)
import tools as tools_module
from tools import session_id_context, visual_card_search, card_search
from auth import (
    verify_password, get_password_hash, create_access_token,
    get_current_user, oauth2_scheme,
)
from schemas import (
    UserCreate, Token, ChatRequest,
    DeckSaveRequest, StructuredDeckSaveRequest,
)
from agent_manager import get_agent, session_agents
from rag_manager import init_all_rag
from config import (
    MODEL_NAME, VISION_MODEL_NAME, API_URL, BASE_DIR, 
    RULEBOOK_PATH, IMAGENES_DIR, EXTRA_TYPES
)
load_dotenv()
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Yu-Gi-Oh Assistant API")

os.makedirs(IMAGENES_DIR, exist_ok=True)
app.mount("/local-images", StaticFiles(directory=IMAGENES_DIR), name="local-images")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@app.post("/register", response_model=Token)
def register(user: UserCreate):
    if get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed = get_password_hash(user.password)
    create_user(user.username, hashed)
    token = create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(data={"sub": user["username"]})
    return {"access_token": token, "token_type": "bearer"}

# --- Startup: initialise all RAG indices ---
_rag = init_all_rag(RULEBOOK_PATH)
card_retriever = _rag["card"]

# --- Endpoints ---

@app.post("/chat")
def chat(request: ChatRequest, req: Request, current_user: dict = Depends(get_current_user)):
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
            
            # Use invoke instead of run to get intermediate steps
            result = agent.invoke({"input": request.message})
            response = result.get("output", "").strip()
            intermediate_steps = result.get("intermediate_steps", [])
            
            # --- BULLETPROOF FALLBACK ---
            # Si el agente falla al dar la respuesta final pero encontró datos en la herramienta
            if not response and intermediate_steps:
                print("\n[FALLBACK] El agente no generó respuesta final. Resumiendo la observación manualmente...")
                last_action, last_observation = intermediate_steps[-1]
                
                llm = ChatOllama(model=MODEL_NAME, temperature=0.4, num_ctx=8192)
                
                fallback_prompt = (
                    f"El usuario preguntó: '{request.message}'.\n\n"
                    f"Has encontrado esta información en la base de datos:\n---\n{last_observation}\n---\n\n"
                    "Por favor, responde al usuario de forma amable y detallada resumiendo esta información. "
                    "IMPORTANTE: Si la información incluye una URL de imagen ('Image: ...'), DEBES incluirla en tu respuesta "
                    "usando el formato Markdown: ![Nombre de la carta](URL). NO uses JSON."
                )
                
                fallback_result = llm.invoke([HumanMessage(content=fallback_prompt)])
                response = fallback_result.content
            # ---------------------------
            
            # Process thoughts for the frontend (to show what happens in terminal)
            thoughts = []
            for action, observation in intermediate_steps:
                obs_str = str(observation)
                thought_entry = f"Thought: {action.log}\nObservation: {obs_str}"
                
                # Detect errors or warnings in the observation
                lower_obs = obs_str.lower()
                if any(word in lower_obs for word in ["error", "failed", "exception", "not available", "limit reached"]):
                    error_msg = f"--- [WARNING] AGENT WARNING/ERROR --- \nAction: {action.tool}\nObservation: {obs_str}\n---------------------------"
                    print(error_msg) # Print to terminal as requested
                    thought_entry = "[WARNING] [SYSTEM ALERT: ERROR OR WARNING DETECTED]\n" + thought_entry
                
                thoughts.append(thought_entry)
            full_thoughts = "\n\n".join(thoughts)
            
            # Check if a deck was stored for this session
            deck_data = None
            last = tools_module._last_decks.get(session_id, {})
            if last.get("cards"):

                def fetch_card_objects(names: list) -> list:
                    if not names:
                        return []
                    
                    result_map = {}
                    try:
                        from database import get_connection
                        conn = get_connection()
                        cursor = conn.cursor()
                        
                        # Prepare placeholders for IN clause
                        placeholders = ",".join(["?"] * len(names))
                        cursor.execute(f"SELECT name, data FROM card_cache WHERE name IN ({placeholders})", names)
                        
                        for row_name, row_data in cursor.fetchall():
                            c = json.loads(row_data)
                            result_map[row_name] = {
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
                            }
                        conn.close()
                    except Exception as e:
                        print(f"[API] Error in batch fetch: {e}")

                    # Maintain order and handle missing cards via API fallback only if absolutely necessary
                    final_result = []
                    for name in names:
                        if name in result_map:
                            final_result.append(result_map[name])
                        else:
                            # Fallback for single missing card (rare if generated from local DB)
                            try:
                                url = f"https://db.ygoprodeck.com/api/v7/cardinfo.php?name={name}"
                                r = http_requests.get(url, timeout=2)
                                if r.status_code == 200:
                                    c = r.json()["data"][0]
                                    final_result.append({
                                        "id": c["id"], "name": c["name"], "type": c["type"],
                                        "desc": c.get("desc", ""), "image": c["card_images"][0]["image_url_small"],
                                        "card_images": c["card_images"]
                                    })
                            except Exception: pass
                    return final_result

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


            return {"response": response, "deck_data": deck_data, "thoughts": full_thoughts}
        finally:
            # Reset context variables after request
            session_id_context.reset(s_token)
            tools_module.user_id_context.reset(u_token)
            
    except Exception as e:
        import traceback
        print("--- ERROR EN EL CHAT ---")
        traceback.print_exc()
        print("------------------------")
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
    final_name = rename_user_deck(current_user["id"], name, new_name)
    return {"status": "success", "new_name": final_name}


@app.post("/save-deck")
async def save_structured_deck(request: StructuredDeckSaveRequest, current_user: dict = Depends(get_current_user)):
    print(f"Saving structured deck: {request.name} (overwrite={request.overwrite}) for user {current_user['username']}")
    final_name = save_user_deck(current_user["id"], request.name, request.main, request.extra, request.side, overwrite=request.overwrite)
    return {"status": "success", "name": final_name}

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

def optimize_image(image_bytes, max_size=(1024, 1024)):
    """Convert to JPEG and resize to save memory and ensure compatibility."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as e:
        print(f"[IMAGE AGENT] [WARNING] Error optimizando imagen: {e}")
        return image_bytes

@app.post("/analyze-image")
def analyze_image(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    print(f"\n[IMAGE AGENT] [INFO] Recibida imagen: {file.filename}")
    try:
        raw_contents = file.file.read()
        
        from rag_manager import image_rag_collection
        
        clean_name = "Unknown"
        rag_details = ""
        local_image_url = None
        vision_description = "Búsqueda directa por imagen (OpenCLIP)"
        
        if image_rag_collection:
            print("[IMAGE AGENT] [INFO] Usando OpenCLIP Image RAG para búsqueda directa...")
            temp_path = os.path.join(BASE_DIR, "temp_upload.jpg")
            with open(temp_path, "wb") as f:
                f.write(raw_contents)
            
            try:
                results = image_rag_collection.query(
                    query_uris=[temp_path],
                    n_results=1
                )
                
                if results and results["metadatas"] and results["metadatas"][0]:
                    best_match = results["metadatas"][0][0]
                    clean_name = best_match.get("name", "Unknown")
                    print(f"[IMAGE AGENT] [OK] OpenCLIP Match: {clean_name}")
                    
                    local_img = best_match.get("image_path")
                    if local_img:
                        local_image_url = f"{API_URL}/local-images/{os.path.basename(local_img)}"
                        
                    exact_card = get_card_by_exact_name(clean_name)
                    if exact_card:
                        rag_details = f"Name: {clean_name}\nDescription: {exact_card['data'].get('desc', '')}"
                    else:
                        rag_details = f"Name: {clean_name}\nIdentificado vía Image RAG."
            except Exception as e:
                print(f"[IMAGE AGENT] [ERROR] Error en Image RAG: {e}")
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        # Fallback a moondream si OpenCLIP falló o no está inicializado
        if clean_name == "Unknown":
            print(f"[IMAGE AGENT] [INFO] Fallback a modelo de visión ({VISION_MODEL_NAME})...")
            contents = optimize_image(raw_contents)
            import ollama
            
            try:
                response = ollama.generate(
                    model=VISION_MODEL_NAME,
                    prompt="Focus on the card name at the top and the artwork. Describe the card in detail, including the color of the frame, the character's appearance, and any text you can read. What is the name of this Yu-Gi-Oh card?",
                    images=[contents],
                    stream=False
                )
            except Exception as ollama_err:
                err_msg = str(ollama_err)
                if "resource limitations" in err_msg.lower() or "500" in err_msg:
                    print(f"[IMAGE AGENT] [ERROR] ERROR DE RECURSOS: El modelo de visión ha fallado por falta de memoria.")
                raise ollama_err

            vision_description = response.get('response', '').strip()
            
            print(f"[IMAGE AGENT] [INFO] Buscando carta en Visual RAG de texto (ChromaDB)...")
            from tools import visual_card_search
            rag_result = visual_card_search.invoke(vision_description)
            
            expert_name = "Unknown"
            if "Identified Match:" in rag_result:
                expert_name = rag_result.split("Identified Match:")[1].split("\n")[0].strip()
            
            print(f"[IMAGE AGENT] [OK] Resultado Visual RAG: '{expert_name}'")
            exact_card = get_card_by_exact_name(expert_name)
            
            rag_details = rag_result
            clean_name = expert_name
            
            if exact_card:
                print(f"[IMAGE AGENT] [INFO] Exact Match found in DB for '{expert_name}'. Skipping RAG.")
                clean_name = exact_card["data"]["name"]
                rag_details = f"Name: {clean_name}\nDescription: {exact_card['data'].get('desc', '')}"
                
                local_img = exact_card.get("local_image")
                if local_img:
                    local_image_url = f"{API_URL}/local-images/{os.path.basename(local_img)}"
                    print(f"[IMAGE AGENT] [INFO] Imagen local (Exact): {local_image_url}")
                    
            elif card_retriever:
                query = f"Name: {expert_name}. Appearance: {vision_description}"
                docs = card_retriever.invoke(query)
                
                if docs:
                    top_card = docs[0]
                    clean_name = top_card.metadata.get("name")
                    local_img = top_card.metadata.get("local_image")
                    if local_img:
                        local_image_url = f"{API_URL}/local-images/{os.path.basename(local_img)}"
                    rag_details = "\n---\n".join([d.page_content for d in docs[:2]])

        print(f"[IMAGE AGENT] [INFO] Buscando detalles finales para '{clean_name}'...")
        search_url = f"https://db.ygoprodeck.com/api/v7/cardinfo.php?fname={clean_name}"
        card_data = None
        
        try:
            r = http_requests.get(search_url, timeout=5)
            if r.status_code == 200:
                r_json = r.json()
                if "data" in r_json:
                    card_data = r_json["data"][0]
                    print(f"[IMAGE AGENT] [INFO] Carta confirmada: {card_data['name']}")
        except Exception as e:
            print(f"[IMAGE AGENT] [WARNING] Error en búsqueda API: {e}")

        from tools import card_search
        return {
            "card_name": clean_name,
            "details": card_data.get("desc") if card_data else (exact_card["data"].get("desc") if exact_card else rag_details),
            "card_image": local_image_url or (card_data["card_images"][0]["image_url"] if card_data else None)
        }
    except Exception as e:
        print(f"[IMAGE AGENT] [ERROR] ERROR CRÍTICO: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8000)
