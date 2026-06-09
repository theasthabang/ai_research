import os
import re
import logging
from typing import Dict, Any
from dotenv import load_dotenv, find_dotenv
from langchain_groq import ChatGroq
from app.retriever import retrieval_tools
from app.memory import load_messages, save_message

load_dotenv(find_dotenv(), override=True)
logger = logging.getLogger("ai-research-helper.agent")


def select_tools(query: str, mode: str = "all_sources"):
    """Select tools based on frontend mode or keyword fallback."""

    # ── Explicit mode from frontend ────────────────────────────────────────
    if mode == "my_documents":
        return ["pdf_search"]
    if mode == "web_academic":
        return ["web_search", "arxiv_search"]
    if mode == "all_sources":
        return ["web_search", "arxiv_search", "pdf_search"]

    # ── Auto / keyword fallback ────────────────────────────────────────────
    q = query.lower()
    if any(w in q for w in ["uploaded", "my document", "my pdf", "my notes",
                             "inside the document", "this paper"]):
        return ["pdf_search"]
    if any(w in q for w in ["latest", "today", "recent", "current",
                             "breaking", "news"]):
        return ["web_search"]
    if any(w in q for w in ["research paper", "academic", "journal",
                             "study", "arxiv"]):
        return ["arxiv_search"]

    return ["web_search", "arxiv_search", "pdf_search"]


def calculate_confidence(
    sources: list, context: str, query: str, answer: str, llm
) -> Dict[str, Any]:
    """
    Ask the LLM to score how well the answer is grounded in retrieved context.
    Falls back to source-count scoring if LLM eval fails.
    """
    if not sources and not context.strip():
        return {"score": 2, "reason": "No sources found — treat answer with caution"}

    eval_prompt = f"""You are a research quality evaluator. Score how well the answer is supported by the retrieved sources.

Question: {query}

Retrieved context (first 2000 chars):
{context[:2000]}

Answer given:
{answer[:1000]}

Reply with ONLY these two lines, nothing else:
SCORE: <integer 1-10>
REASON: <one sentence explanation>

Scoring guide:
1-3 = answer not supported by retrieved sources
4-5 = partially supported, noticeable gaps
6-7 = mostly supported, minor gaps
8-9 = well supported by multiple strong sources
10 = fully grounded, every claim traceable to a source"""

    try:
        result = llm.invoke(eval_prompt).content.strip()
        lines  = result.splitlines()

        score_line  = next((l for l in lines if l.upper().startswith("SCORE:")),  None)
        reason_line = next((l for l in lines if l.upper().startswith("REASON:")), None)

        if not score_line or not reason_line:
            raise ValueError("LLM did not return expected SCORE/REASON format")

        score  = max(1, min(10, int(score_line.split(":", 1)[1].strip())))
        reason = reason_line.split(":", 1)[1].strip()
        return {"score": score, "reason": reason}

    except Exception as exc:
        logger.warning("LLM confidence eval failed (%s), falling back to count-based scoring", exc)
        count = len(sources)
        if count >= 5: return {"score": 7, "reason": f"Fallback: {count} sources retrieved"}
        if count >= 2: return {"score": 5, "reason": f"Fallback: {count} sources retrieved"}
        if count >= 1: return {"score": 3, "reason": "Fallback: only 1 source retrieved"}
        return          {"score": 2, "reason": "Fallback: no sources retrieved"}


def run_agent(
    query: str,
    session_id: str,
    mode: str = "all_sources",   # ← NEW parameter, matches SearchMode in schema
) -> Dict[str, Any]:

    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return {
            "answer":     "GROQ_API_KEY not set in .env file.",
            "sources":    [],
            "confidence": {"score": 1, "reason": "API key missing."},
        }

    try:
        chat_history = load_messages(session_id)

        llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.2,
            groq_api_key=groq_key,
        )

        sources: list = []
        context: str  = ""

        selected_tool_names = select_tools(query, mode)   # ← pass mode here
        logger.info("Session %s | mode=%s | tools=%s", session_id, mode, selected_tool_names)

        for tool in retrieval_tools:
            if tool.name in selected_tool_names:
                try:
                    result   = tool.run(query)
                    context += f"\n[{tool.name}]:\n{result}\n"
                    urls     = re.findall(r'https?://[^\s\n\)]+', str(result))
                    sources.extend(urls)
                except Exception as exc:
                    logger.warning("Tool %s failed: %s", tool.name, exc)

        prompt = f"""You are AI Research Helper — a precise assistant for academics and students.
Always cite your sources inline. Never fabricate information.

Chat History:
{chat_history}

Retrieved Information:
{context}

Question: {query}

Provide a clear, well-structured answer with all sources cited."""

        response = llm.invoke(prompt).content

        save_message(session_id, "human",     query)
        save_message(session_id, "assistant", response)

        # Also capture any URLs the LLM added in its answer
        for url in re.findall(r'https?://[^\s\n\)]+', response):
            if url not in sources:
                sources.append(url)

        return {
            "answer":     response,
            "sources":    list(dict.fromkeys(sources)),   # deduplicate, preserve order
            "confidence": calculate_confidence(sources, context, query, response, llm),
        }

    except Exception as e:
        logger.exception("run_agent failed for session %s", session_id)
        return {
            "answer":     f"Error: {str(e)}",
            "sources":    [],
            "confidence": {"score": 1, "reason": str(e)},
        }