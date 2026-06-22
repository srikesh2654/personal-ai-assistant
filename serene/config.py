from dotenv import load_dotenv
import os
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ACTIVE_BRAIN = os.getenv("ACTIVE_BRAIN","local")
DB_URL = os.getenv("DB_URL","postgresql://openpg@127.0.0.1:5432/serene")
ALLOWED_ROOT = os.getenv("ALLOWED_ROOT", r"C:\Users\srike")
# sha256 hash of the unlock password. Empty => no lock screen.
SERENE_PASSWORD_HASH = os.getenv("SERENE_PASSWORD_HASH", "")