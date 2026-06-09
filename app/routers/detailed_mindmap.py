"""app/routers/detailed_mindmap.py — POST /detailed-mindmap endpoint.

Speed optimisations vs original:
  - Groups are BATCHED: 3 page-groups per LLM call instead of 1
    → 15 groups = 5 calls instead of 15  (3× fewer API round-trips)
  - Sleep reduced from 8 s → 3 s  (safe because we make far fewer calls)
  - Each call asks for multiple PageSection objects in one JSON array
  - Total time for a typical PDF: ~25 s instead of ~2 min
"""
import os, re, json, logging, time
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from functools import lru_cache

router = APIRouter()
logger = logging.getLogger("ai-research-helper.detailed-mindmap")

CHROMA_DB_PATH  = "./data/chroma_db"
COLLECTION_NAME = "research_docs"
EMBED_MODEL     = "all-MiniLM-L6-v2"

BRANCH_COLORS = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
    "#FFEAA7", "#DDA0DD", "#FF8C42", "#6BCB77",
]

INTER_CALL_SLEEP = 3    # reduced: fewer calls means we can sleep less
GROUPS_PER_BATCH = 3    # combine 3 page-groups per single LLM call


# ── Pydantic models ───────────────────────────────────────────────────────────

class DetailedMindMapRequest(BaseModel):
    filename:    str = Field(..., description="Ingested PDF filename")
    total_pages: int = Field(..., description="Total number of pages in the PDF")


class SubBranch(BaseModel):
    name:   str
    points: List[str]


class Branch(BaseModel):
    name:         str
    color:        str
    sub_branches: List[SubBranch]


class PageSection(BaseModel):
    page_title:   str
    center_topic: str
    branches:     List[Branch]
    key_facts:    List[str]
    exam_corner:  List[str]


class DetailedMindMapResponse(BaseModel):
    filename: str
    pages:    List[PageSection]


# ── Embeddings (cached) ───────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_page_groups(filename: str) -> List[List[str]]:
    from app.ingest import load_page_groups, build_page_groups
    groups = load_page_groups(filename)
    if groups:
        logger.info("Loaded %d pre-built page groups for '%s'", len(groups), filename)
        return groups

    logger.warning("No pre-built groups for '%s' — rebuilding from ChromaDB", filename)
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_DB_PATH,
        embedding_function=_get_embeddings(),
    )
    raw   = vectorstore.get(include=["documents", "metadatas"])
    docs  = raw.get("documents", [])
    metas = raw.get("metadatas", [])
    pairs = [
        (d, m.get("page", 0))
        for d, m in zip(docs, metas)
        if m.get("filename", "").lower() == filename.lower()
        or m.get("source",   "").lower() == filename.lower()
    ]
    pairs.sort(key=lambda x: x[1])
    all_chunks = [d for d, _ in pairs]
    return build_page_groups(all_chunks, max_pages=15)


def _clean_json(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


# ── Batched prompt ────────────────────────────────────────────────────────────

BATCH_PROMPT = """\
You are an expert academic mind-map creator. You will receive {n} sections of study content.
Return ONLY a valid JSON ARRAY with exactly {n} objects — one per section. No markdown, no explanation.

{sections_block}

Each object MUST follow this structure exactly:
{{
  "page_title": "short section name (4-6 words)",
  "center_topic": "main topic (2-4 words)",
  "branches": [
    {{
      "name": "branch name",
      "color": "#FF6B6B",
      "sub_branches": [
        {{
          "name": "sub topic",
          "points": ["point 1", "point 2"]
        }}
      ]
    }}
  ],
  "key_facts": ["fact 1", "fact 2"],
  "exam_corner": ["exam tip 1", "exam tip 2"]
}}

Rules:
- 3-4 branches per section, each with 2-3 sub_branches, each with 2-3 points (all under 10 words)
- 3-4 key_facts (concise, exam-ready, under 15 words each)
- 2-3 exam_corner tips
- Use colors from: {colors}
- Base everything strictly on the provided content
- Return ONLY the JSON array — starting with [ and ending with ]"""


def _build_sections_block(batch: List[List[str]], start_idx: int) -> str:
    parts = []
    for i, group in enumerate(batch):
        text = "\n\n".join(group)[:2000]   # limit per group so total stays under token limit
        parts.append(f"=== SECTION {start_idx + i + 1} ===\n{text}")
    return "\n\n".join(parts)


def _generate_batch(llm: ChatGroq, batch: List[List[str]], start_idx: int) -> List[dict]:
    """Call LLM once for a batch of groups. Returns list of parsed dicts."""
    n      = len(batch)
    block  = _build_sections_block(batch, start_idx)
    prompt = BATCH_PROMPT.format(
        n=n,
        sections_block=block,
        colors=" ".join(BRANCH_COLORS),
    )
    try:
        raw  = llm.invoke(prompt).content
        raw  = _clean_json(raw)
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        # LLM sometimes wraps in {"pages": [...]}
        if isinstance(data, dict):
            for key in ("pages", "sections", "results"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        logger.error("Batch %d: unexpected JSON shape", start_idx)
        return []
    except json.JSONDecodeError as exc:
        logger.error("Batch starting at %d — invalid JSON: %s", start_idx, exc)
        return []
    except Exception as exc:
        logger.error("Batch starting at %d — LLM call failed: %s", start_idx, exc)
        return []


def _parse_page_section(data: dict, fallback_idx: int) -> PageSection | None:
    try:
        return PageSection(
            page_title   = data.get("page_title",   f"Section {fallback_idx + 1}"),
            center_topic = data.get("center_topic", f"Topic {fallback_idx + 1}"),
            branches=[
                Branch(
                    name         = b.get("name", ""),
                    color        = b.get("color", BRANCH_COLORS[bi % len(BRANCH_COLORS)]),
                    sub_branches = [
                        SubBranch(
                            name   = sb.get("name", ""),
                            points = sb.get("points", []),
                        )
                        for sb in b.get("sub_branches", [])
                    ],
                )
                for bi, b in enumerate(data.get("branches", []))
            ],
            key_facts   = data.get("key_facts",   []),
            exam_corner = data.get("exam_corner", []),
        )
    except Exception as exc:
        logger.warning("Could not parse section %d: %s", fallback_idx, exc)
        return None


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/detailed-mindmap", response_model=DetailedMindMapResponse)
def generate_detailed_mindmap(request: DetailedMindMapRequest):

    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise HTTPException(500, "GROQ_API_KEY not set in .env")

    try:
        groups = _get_page_groups(request.filename)
    except Exception as exc:
        raise HTTPException(500, f"Error loading page groups: {exc}")

    if not groups:
        raise HTTPException(
            404,
            f"No content found for '{request.filename}'. "
            "Make sure the PDF is ingested first.",
        )

    logger.info(
        "File '%s' — %d groups, will use %d batched LLM calls (batch size %d)",
        request.filename, len(groups),
        -(-len(groups) // GROUPS_PER_BATCH),   # ceiling division
        GROUPS_PER_BATCH,
    )

    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.1,
        groq_api_key=groq_key,
    )

    pages: List[PageSection] = []
    group_idx = 0

    # Process in batches of GROUPS_PER_BATCH
    batches = [groups[i:i + GROUPS_PER_BATCH] for i in range(0, len(groups), GROUPS_PER_BATCH)]

    for batch_num, batch in enumerate(batches):
        logger.info("Processing batch %d/%d (%d groups)…",
                    batch_num + 1, len(batches), len(batch))

        if batch_num > 0:
            time.sleep(INTER_CALL_SLEEP)

        results = _generate_batch(llm, batch, group_idx)

        # If batch returned fewer results than expected, pad with empty dicts
        while len(results) < len(batch):
            results.append({})

        for i, data in enumerate(results[:len(batch)]):
            page = _parse_page_section(data, group_idx + i)
            if page:
                pages.append(page)

        group_idx += len(batch)

    if not pages:
        raise HTTPException(500, "Failed to generate any page sections.")

    logger.info("Done — %d pages generated for '%s'", len(pages), request.filename)
    return DetailedMindMapResponse(filename=request.filename, pages=pages)