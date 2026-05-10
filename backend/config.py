import os
from dotenv import load_dotenv

load_dotenv()

# --- General Config ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_URL = os.getenv("API_URL", "http://localhost:8000")

# --- Security Config ---
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-it-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 1 week

# --- AI Models Config ---
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:7b")
VISION_MODEL_NAME = os.getenv("VISION_MODEL_NAME", "moondream")

# --- Path Config ---
RULEBOOK_PATH = os.getenv("RULEBOOK_PATH", os.path.join(BASE_DIR, "SD_RuleBook_EN_10.pdf"))
IMAGENES_DIR = os.path.join(BASE_DIR, "imagenes")
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")

# --- Game Logic Config ---
EXTRA_TYPES = {"fusion", "synchro", "xyz", "link"}
COLLECTION_NAME = "yugioh_visual_cards"
