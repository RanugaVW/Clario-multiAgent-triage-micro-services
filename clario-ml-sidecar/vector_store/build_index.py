"""Build an idempotent local Chroma index from the support KB markdown files."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
KB_ROOT = Path(__file__).resolve().parent / "kb_documents"
COLLECTION_NAME = "kb_support_docs"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def chroma_path() -> str:
    configured = Path(os.getenv("CHROMA_PATH", "./vector_store/chroma_data"))
    return str(configured if configured.is_absolute() else ROOT / configured)


def chunk_text(text: str, size: int = 300, overlap: int = 50) -> list[str]:
    """Split text into approximate word-token chunks with a bounded overlap."""
    words = text.split()
    if not words:
        return []
    step = size - overlap
    return [" ".join(words[start : start + size]) for start in range(0, len(words), step)]


def documents() -> list[tuple[str, str, str, int]]:
    """Yield chunk text, domain, source path, and ordinal for every KB markdown file."""
    rows: list[tuple[str, str, str, int]] = []
    for source in sorted(KB_ROOT.glob("*/*.md")):
        domain = source.parent.name
        for index, chunk in enumerate(chunk_text(source.read_text(encoding="utf-8"))):
            rows.append((chunk, domain, source.relative_to(KB_ROOT).as_posix(), index))
    return rows


def build_index() -> int:
    """Embed and upsert all deterministic document chunks; safe to run repeatedly."""
    load_dotenv(ROOT / ".env")
    rows = documents()
    if not rows:
        raise RuntimeError(f"No markdown KB documents found in {KB_ROOT}")
    texts, domains, sources, ordinals = zip(*rows)
    ids = [hashlib.sha256(f"{source}:{ordinal}".encode()).hexdigest() for source, ordinal in zip(sources, ordinals)]
    embeddings = SentenceTransformer(MODEL_NAME).encode(list(texts)).tolist()
    client = chromadb.PersistentClient(path=chroma_path())
    collection = client.get_or_create_collection(
        COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )

    # upsert() only adds/updates the ids produced by this run - it never
    # deletes one. If a KB doc shrinks and now produces fewer chunks than
    # it used to (e.g. it drops back under the chunking boundary), its old,
    # larger-revision chunk would otherwise stay in the index forever under
    # the same source_file as its replacement. Scoped to source_files this
    # run actually manages, so it can never touch precedent_memory (written
    # by a different process entirely).
    current_sources = sorted(set(sources))
    existing_ids = set(collection.get(where={"source_file": {"$in": current_sources}}, include=[])["ids"])
    stale_ids = existing_ids - set(ids)
    if stale_ids:
        collection.delete(ids=list(stale_ids))

    collection.upsert(
        ids=ids,
        documents=list(texts),
        embeddings=embeddings,
        metadatas=[{"domain": domain, "source_file": source} for domain, source in zip(domains, sources)],
    )
    return len(rows)


if __name__ == "__main__":
    print(f"Indexed {build_index()} KB chunks into {chroma_path()}")
