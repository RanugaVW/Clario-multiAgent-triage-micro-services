import os
from pathlib import Path
import chromadb
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_COLLECTION_NAME = "kb_codebase"

def _chroma_path() -> str:
    configured = Path(os.getenv("CHROMA_PATH", "./vector_store/chroma_data"))
    return str(configured if configured.is_absolute() else _ROOT / configured)

def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """Basic character chunker."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks

def ingest_directories(directories: list[str], extensions: set[str]):
    print("Loading embedding model...")
    embedder = SentenceTransformer(_MODEL_NAME, local_files_only=True)
    
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
            if "node_modules" in root or ".next" in root or "dist" in root or "target" in root or ".venv" in root:
                continue
            for file in files:
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
                        
                    chunks = chunk_text(content)
                    
                    ids = [f"{file_path}_{i}" for i in range(len(chunks))]
                    metadatas = [{"source_file": str(file_path)} for _ in range(len(chunks))]
                    
                    print(f"Embedding {len(chunks)} chunks for {file}...")
                    embeddings = embedder.encode(chunks, normalize_embeddings=True).tolist()
                    
                    collection.add(
                        ids=ids,
                        embeddings=embeddings,
                        documents=chunks,
                        metadatas=metadatas
                    )

    print("Ingestion complete!")

if __name__ == "__main__":
    dirs_to_ingest = [
        r"C:\Users\ranug\Downloads\rysera-stem-web",
        r"C:\Users\ranug\Downloads\rysera-stem-backend"
    ]
    exts = {".ts", ".tsx", ".js", ".jsx", ".py", ".java"}
    ingest_directories(dirs_to_ingest, exts)
