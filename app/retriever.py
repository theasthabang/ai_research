"""
retriever.py — LangChain tools for web, ArXiv, and PDF search.

Key improvement in pdf_search:
  - 3-strategy search: numbered question lookup + keyword match + semantic search
  - Handles "explain question 10", "what is question 5", "show me problem 3" etc.
  - Fetches ALL chunks from the PDF and scans for numbered patterns directly
  - Returns more context (8 chunks) for detailed answers
  - Deduplicates results across all strategies
"""

import os
import re
import json
import logging
from functools import lru_cache
from typing import List

from dotenv import load_dotenv
from langchain.tools import tool
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.tools.tavily_search import TavilySearchResults

load_dotenv()
logger = logging.getLogger("ai-research-helper.retriever")

CHROMA_DB_PATH  = "./data/chroma_db"
COLLECTION_NAME = "research_docs"
EMBED_MODEL     = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_embeddings() -> HuggingFaceEmbeddings:
    logger.info("Loading embedding model '%s'…", EMBED_MODEL)
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


# ---------------------------------------------------------------------------
# Tool 1 — web_search
# ---------------------------------------------------------------------------

@tool
def web_search(query: str) -> str:
    """
    Searches the web for real-time information, recent news, or general knowledge.
    Use when you need up-to-date information not present in uploaded research papers.
    """
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        return "Error: TAVILY_API_KEY not set. Add it to your .env file."

    try:
        search_engine = TavilySearchResults(max_results=5)
        raw_results   = search_engine.run(query)

        if isinstance(raw_results, str):
            try:
                results_list = json.loads(raw_results)
            except Exception:
                return raw_results
        else:
            results_list = raw_results

        formatted: List[str] = []
        for res in results_list:
            formatted.append(
                f"Title: {res.get('title', 'Web Result')}\n"
                f"URL: {res.get('url', 'N/A')}\n"
                f"Snippet: {res.get('content', 'No content.')}\n---"
            )
        return "\n".join(formatted) if formatted else "No results found."

    except Exception as exc:
        logger.exception("web_search failed")
        return f"Error: {exc}"


# ---------------------------------------------------------------------------
# Tool 2 — arxiv_search
# ---------------------------------------------------------------------------

@tool
def arxiv_search(query: str) -> str:
    """
    Searches arXiv.org for academic preprints and research papers.
    Use when the user needs scholarly papers or scientific abstracts.
    """
    import arxiv
    try:
        client  = arxiv.Client()
        search  = arxiv.Search(query=query, max_results=5, sort_by=arxiv.SortCriterion.Relevance)
        results = list(client.results(search))

        if not results:
            return "No academic papers found on arXiv."

        formatted: List[str] = []
        for paper in results:
            authors  = ", ".join(a.name for a in paper.authors)
            pub_date = paper.published.strftime("%Y-%m-%d") if paper.published else "Unknown"
            abstract = paper.summary.strip()[:500] + ("…" if len(paper.summary) > 500 else "")
            formatted.append(
                f"Title: {paper.title}\nAuthors: {authors}\n"
                f"Published: {pub_date}\nSummary: {abstract}\n"
                f"URL: {paper.entry_id}\n---"
            )
        return "\n".join(formatted)

    except Exception as exc:
        logger.exception("arxiv_search failed")
        return f"Error: {exc}"


# ---------------------------------------------------------------------------
# Tool 3 — pdf_search  (smart multi-strategy)
# ---------------------------------------------------------------------------

def _extract_question_number(query: str):
    """
    Return integer if query contains a question/problem number, else None.
    Handles: 'question 10', 'problem 5', 'q10', 'explain 3', '#7', 'no. 12'
    """
    patterns = [
        r'\b(?:question|problem|q|no\.?|#|ques)\s*(\d+)\b',
        r'\bexplain\s+(\d+)\b',
        r'\b(\d+)\s*(?:st|nd|rd|th)?\s+question\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, query.lower())
        if match:
            return int(match.group(1))
    return None


def _get_all_chunks(vectorstore: Chroma) -> List:
    """Fetch every chunk stored in ChromaDB for brute-force scanning."""
    try:
        raw = vectorstore.get(include=["documents", "metadatas"])
        docs_text = raw.get("documents", [])
        metadatas = raw.get("metadatas", [])
        from langchain_core.documents import Document
        return [
            Document(page_content=t, metadata=m)
            for t, m in zip(docs_text, metadatas)
        ]
    except Exception:
        return []


def _find_numbered_chunks(all_chunks: List, number: int) -> List:
    """
    Scan every chunk for patterns like '10.', '10)', 'Question 10', 'Problem 10'.
    Returns the matching chunk + the one after it (for context).
    """
    patterns = [
        rf'^\s*{number}[\.\)]\s',           # "10. " or "10) " at line start
        rf'\bquestion\s+{number}\b',         # "question 10"
        rf'\bproblem\s+{number}\b',          # "problem 10"
        rf'\b{number}\.\s+[A-Z]',            # "10. GCD" — numbered heading
    ]
    matched = []
    for i, doc in enumerate(all_chunks):
        text = doc.page_content
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE | re.MULTILINE):
                matched.append(doc)
                # include next chunk too for full context
                if i + 1 < len(all_chunks):
                    matched.append(all_chunks[i + 1])
                break
    return matched


@tool
def pdf_search(query: str) -> str:
    """
    Searches the user's uploaded PDF documents using 3 strategies:
    1. Numbered question lookup  — finds 'question 10', 'problem 5' etc. exactly
    2. Keyword match             — finds chunks containing key terms from query
    3. Semantic similarity       — finds conceptually related chunks

    Use for ANY question about content in the user's uploaded documents.
    """
    try:
        vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            persist_directory=CHROMA_DB_PATH,
            embedding_function=_get_embeddings(),
        )

        all_chunks   = _get_all_chunks(vectorstore)
        all_results  = []
        seen         = set()

        def add_unique(docs):
            for doc in docs:
                key = doc.page_content[:80]
                if key not in seen:
                    seen.add(key)
                    all_results.append(doc)

        # ── Strategy 1: Numbered question lookup ──────────────────────────
        num = _extract_question_number(query)
        if num is not None:
            logger.info("pdf_search: numbered lookup for question %d", num)
            numbered = _find_numbered_chunks(all_chunks, num)
            add_unique(numbered)
            if numbered:
                logger.info("pdf_search: found %d chunks via numbered lookup", len(numbered))

        # ── Strategy 2: Keyword match ──────────────────────────────────────
        # Extract meaningful words (4+ chars) from the query and scan chunks
        stop_words = {"explain", "what", "show", "tell", "give", "from",
                      "document", "about", "question", "problem", "the", "and"}
        keywords = [
            w for w in re.findall(r'\b[a-zA-Z]{4,}\b', query.lower())
            if w not in stop_words
        ]
        if keywords:
            for doc in all_chunks:
                text_lower = doc.page_content.lower()
                # chunk must contain at least 2 keywords (or 1 if query is short)
                threshold = 1 if len(keywords) <= 2 else 2
                hits = sum(1 for kw in keywords if kw in text_lower)
                if hits >= threshold:
                    key = doc.page_content[:80]
                    if key not in seen:
                        seen.add(key)
                        all_results.append(doc)

        # ── Strategy 3: Semantic similarity ───────────────────────────────
        semantic = vectorstore.similarity_search(query, k=6)
        add_unique(semantic)

        # Also try semantic search on just the topic (strip "explain", "what is" etc.)
        clean_query = re.sub(
            r'\b(explain|what is|tell me about|show me|describe|define)\b',
            '', query, flags=re.IGNORECASE
        ).strip()
        if clean_query and clean_query != query:
            add_unique(vectorstore.similarity_search(clean_query, k=4))

        if not all_results:
            return (
                "No relevant content found in your uploaded documents. "
                "Make sure you clicked 'Upload & Ingest' after uploading the PDF."
            )

        # Sort by page number so answer reads in document order
        all_results.sort(key=lambda d: (d.metadata.get("page", 0), d.metadata.get("chunk_index", 0)))

        # Return top 8 chunks for a detailed answer
        formatted: List[str] = []
        for doc in all_results[:8]:
            filename = doc.metadata.get("filename", "Unknown")
            page     = doc.metadata.get("page", "?")
            formatted.append(
                f"Source: {filename} (Page {page})\n"
                f"{doc.page_content}\n---"
            )

        return "\n".join(formatted)

    except Exception as exc:
        logger.exception("pdf_search failed")
        return f"Error executing PDF search: {exc}"


# ---------------------------------------------------------------------------
# Exported tool list
# ---------------------------------------------------------------------------

retrieval_tools = [web_search, arxiv_search, pdf_search]