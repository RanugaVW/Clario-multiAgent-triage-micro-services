import os
import re
from pathlib import Path
import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language

_ROOT = Path(__file__).resolve().parents[3]
_SIDECAR_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_SIDECAR_ROOT / ".env")

_MODEL_NAME = "gemini-embedding-2"
_COLLECTION_NAME = "kb_codebase"

def _chroma_path() -> str:
    configured = Path(os.getenv("CHROMA_PATH", "./vector_store/chroma_data"))
    return str(configured if configured.is_absolute() else _SIDECAR_ROOT / configured)

def get_splitter_for_ext(ext: str):
    mapping = {
        ".ts": Language.TS,
        ".tsx": Language.TS,
        ".js": Language.JS,
        ".jsx": Language.JS,
        ".py": Language.PYTHON,
        ".java": Language.JAVA,
        ".md": Language.MARKDOWN,
        ".html": Language.HTML
    }
    lang = mapping.get(ext)
    if lang:
        return RecursiveCharacterTextSplitter.from_language(
            language=lang, chunk_size=1500, chunk_overlap=200
        )
    return RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)

def redact_secrets(text: str) -> str:
    """Masks hardcoded secrets, keys, and tokens in source code."""
    # Pattern to match: (secret|password|key|token) followed by = or : and a string literal
    pattern = re.compile(r'(?i)(secret|password|key|token|api_key|pwd)\s*[:=]\s*(["\'])(.*?)\2')
    return pattern.sub(r'\1 = \2[REDACTED_SECRET]\2', text)

def ingest_directories(directories: list[str], extensions: set[str]):
    print("Loading Gemini embedding client...")
    client_genai = genai.Client()
    
    print("Connecting to ChromaDB...")
    client = chromadb.PersistentClient(path=_chroma_path())
    # Delete existing to start fresh if needed, or get_or_create
    try:
        client.delete_collection(_COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(_COLLECTION_NAME)

    for dir_path in directories:
        dir_p = Path(dir_path)
        if not dir_p.exists():
            print(f"Directory {dir_path} does not exist. Skipping.")
            continue
            
        print(f"Walking {dir_path}...")
        for root, _, files in os.walk(dir_path):
            if any(skip in root for skip in ["node_modules", ".next", "dist", "target", ".venv", ".git"]):
                continue
            for file in files:
                # Skip environment and property files entirely
                if file.startswith('.env') or file.endswith('.properties') or file.endswith('.yml') or file.endswith('.pem'):
                    continue
                ext = Path(file).suffix
                if ext in extensions:
                    file_path = Path(root) / file
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                    except Exception as e:
                        print(f"Could not read {file_path}: {e}")
                        continue
                    
                    if not content.strip():
                        continue
                    
                    # Redact secrets before chunking
                    content = redact_secrets(content)
                        
                    splitter = get_splitter_for_ext(ext)
                    chunks = splitter.split_text(content)
                    
                    ids = [f"{file_path}_{i}" for i in range(len(chunks))]
                    metadatas = [{"source_file": str(file_path)} for _ in range(len(chunks))]
                    
                    print(f"Embedding {len(chunks)} chunks for {file} via Gemini...")
                    embeddings = []
                    for c in chunks:
                        res = client_genai.models.embed_content(
                            model=_MODEL_NAME,
                            contents=[c],
                            config=types.EmbedContentConfig(output_dimensionality=384)
                        )
                        embeddings.append(res.embeddings[0].values)
                    
                    collection.add(
                        ids=ids,
                        embeddings=embeddings,
                        documents=chunks,
                        metadatas=metadatas
                    )

    print("Ingestion complete!")

if __name__ == "__main__":
    # Pointing to both Clario workspace and Rysera-stem workspace for full technical knowledge.
    dirs_to_ingest = [
        str(_ROOT / "frontend"),
        str(_ROOT / "clario-app"),
        str(_ROOT / "clario-ml-sidecar"),
        r"C:\Users\ranug\Downloads\rysera-stem-web",
        r"C:\Users\ranug\Downloads\rysera-stem-backend"
    ]
    exts = {".ts", ".tsx", ".js", ".jsx", ".py", ".java"}
    ingest_directories(dirs_to_ingest, exts)
