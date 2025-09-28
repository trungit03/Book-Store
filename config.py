import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).parent.absolute()
DATA_DIR = BASE_DIR / "data"
SQLITE_DB_PATH = DATA_DIR / "books.db"
CHROMA_DB_PATH = BASE_DIR / "chroma_db"
CHROMA_COLLECTION_NAME = "books_collection"

OLLAMA_MODEL = "llama3.1:8b"
LLM_TEMPERATURE = 0.7

# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# OPENAI_MODEL = "gpt-4o-mini"


CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
SEARCH_TOP_K = 5
  
MAX_CONVERSATION_HISTORY = 10
SESSION_TIMEOUT = 3600  
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def create_directories():
  DATA_DIR.mkdir(parents=True, exist_ok=True)

create_directories()
