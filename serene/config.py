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

# --- model choices (change in .env, no rebuild needed) ---
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")   # groq chat brain
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "llama3.2")                # ollama chat brain
AGENT_MODEL = os.getenv("AGENT_MODEL", "openai/gpt-oss-20b")      # tool-using agent
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "llama-3.1-8b-instant")  # chat-vs-action
REFLECTION_MODEL = os.getenv("REFLECTION_MODEL", "llama-3.3-70b-versatile")  # memory extraction