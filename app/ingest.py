"""
app/ingest.py — PDF ingestion pipeline.

What happens at ingest time (ONE time per PDF):
  1. Open & validate PDF (PyMuPDF)
  2. Extract & clean text per page
  3. Chunk with RecursiveCharacterTextSplitter (400 chars, 80 overlap)
  4. Embed via HuggingFace all-MiniLM-L6-v2 → store in ChromaDB
  5. Build page_groups: evenly-distributed chunk groups for mindmap/revision
  6. Save everything to metadata.json so downstream features just read it

This means mindmap and revision NEVER re-chunk or re-fetch all chunks —
they just read the pre-built groups from metadata.json.
"""

import os
import re
import json
import math
import logging
from typing import List, Dict, Any

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_chroma import Chroma

logger = logging.getLogger("ai-research-helper.ingest")

UPLOAD_DIR      = "./data/uploads"
CHROMA_DB_PATH  = "./data/chroma_db"
COLLECTION_NAME = "research_docs"
METADATA_FILE   = os.path.join(UPLOAD_DIR, "metadata.json")
GROUPS_DIR      = "./data/page_groups"   # pre-built groups stored here

os.makedirs(UPLOAD_DIR,     exist_ok=True)
os.makedirs(CHROMA_DB_PATH, exist_ok=True)
os.makedirs(GROUPS_DIR,     exist_ok=True)


# ── Metadata helpers ──────────────────────────────────────────────────────────

def load_metadata() -> Dict[str, Any]:
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_metadata(metadata: Dict[str, Any]) -> None:
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=4)


def list_ingested_documents() -> List[Dict[str, Any]]:
    return list(load_metadata().values())


# ── Page-group helpers ────────────────────────────────────────────────────────

def _groups_path(filename: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._\-]", "_", filename)
    return os.path.join(GROUPS_DIR, f"{safe}.groups.json")


def save_page_groups(filename: str, groups: List[List[str]]) -> None:
    """Persist pre-built page groups to disk."""
    with open(_groups_path(filename), "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False)


def load_page_groups(filename: str) -> List[List[str]]:
    """
    Load pre-built page groups. Returns list of lists of chunk text.
    Returns [] if not found (old ingestion before this feature).
    """
    path = _groups_path(filename)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def build_page_groups(chunks: List[str], max_pages: int = 20) -> List[List[str]]:
    """
    Distribute ALL chunks evenly across pages.
    Formula (chunk-based):
      chunks_per_page = 15  (sweet spot: enough context, not too long for LLM)
      n_pages = min(max_pages, max(3, total // chunks_per_page))
    Last group absorbs remainder so NOTHING is skipped.
    Examples:
      100 chunks → 100//15 = 6 pages
      196 chunks → 196//15 = 13 pages
      400 chunks → 400//15 = 20 pages (capped)
    """
    total            = len(chunks)
    chunks_per_page  = 15
    n_pages          = min(max_pages, max(3, total // chunks_per_page))
    size             = max(1, total // n_pages)

    groups = []
    for i in range(n_pages):
        start = i * size
        end   = start + size if i < n_pages - 1 else total
        groups.append(chunks[start:end])
    return groups


# ── Main pipeline ─────────────────────────────────────────────────────────────

def ingest_pdf(file_path: str) -> int:
    """
    Ingest a PDF. Steps:
      1. Open & validate
      2. Extract & clean text per page
      3. Chunk (400 chars, 80 overlap)
      4. Embed & store in ChromaDB
      5. Build page_groups → save to disk
      6. Update metadata.json

    Returns number of chunks added (0 if no extractable text).
    """
    filename = os.path.basename(file_path)
    logger.info("Starting ingestion: %s", filename)

    # 1. Open & validate
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF not found: {file_path}")
    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        raise RuntimeError(f"PyMuPDF could not open '{filename}': {exc}") from exc

    if getattr(doc, "is_encrypted", False) and not doc.authenticate(""):
        doc.close()
        raise RuntimeError(f"'{filename}' is password-protected.")

    total_pages = len(doc)
    logger.info("Opened '%s' — %d pages", filename, total_pages)

    # 2. Extract & clean text per page
    raw_pages: List[tuple] = []
    for page_num in range(total_pages):
        try:
            text = doc.load_page(page_num).get_text() or ""
        except Exception as exc:
            logger.warning("Could not read page %d: %s", page_num + 1, exc)
            text = ""
        raw_pages.append((page_num + 1, text))
    doc.close()

    documents: List[Document] = []
    for page_num, raw_text in raw_pages:
        cleaned = re.sub(r" {2,}", " ", raw_text)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if cleaned:
            documents.append(Document(
                page_content=cleaned,
                metadata={"filename": filename, "page": page_num},
            ))

    logger.info("Extracted text from %d / %d pages", len(documents), total_pages)
    if not documents:
        logger.warning("No extractable text in '%s'", filename)
        return 0

    # 3. Chunk
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=80,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    logger.info("Split into %d chunks", len(chunks))
    if not chunks:
        return 0

    for idx, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = idx
        chunk.metadata["source"]      = filename

    # 4. Embed & store in ChromaDB
    try:
        from app.retriever import _get_embeddings
        vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            persist_directory=CHROMA_DB_PATH,
            embedding_function=_get_embeddings(),
        )
        vectorstore.add_documents(chunks)
    except Exception as exc:
        raise RuntimeError(f"ChromaDB upsert failed: {exc}") from exc

    # 5. Build page groups from chunk texts and save to disk
    chunk_texts = [c.page_content for c in chunks]
    page_groups = build_page_groups(chunk_texts, max_pages=15)
    save_page_groups(filename, page_groups)
    logger.info(
        "Built %d page groups for '%s' (total %d chunks, all covered)",
        len(page_groups), filename, len(chunk_texts),
    )

    # 6. Update metadata
    index = load_metadata()
    index[filename] = {
        "filename":     filename,
        "path":         file_path,
        "chunks_count": len(chunks),
        "pages_count":  total_pages,
        "n_page_groups": len(page_groups),
        "status":       "indexed",
    }
    save_metadata(index)

    logger.info("Ingestion complete: %d chunks, %d page groups for '%s'",
                len(chunks), len(page_groups), filename)
    return len(chunks)