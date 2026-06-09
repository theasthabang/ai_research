"""app/routers/mindmap.py — POST /mindmap endpoint."""
import os, re, json, logging
from fastapi import APIRouter, HTTPException
from langchain_chroma import Chroma
from langchain_groq   import ChatGroq
from app.schemas.mindmap import MindMapRequest, MindMapResponse, MindMapBranch
from app.retriever import _get_embeddings, CHROMA_DB_PATH, COLLECTION_NAME

router = APIRouter()
logger = logging.getLogger("ai-research-helper.mindmap")


def _get_file_chunks(vectorstore, filename: str):
    raw   = vectorstore.get(include=["documents", "metadatas"])
    docs  = raw.get("documents", [])
    metas = raw.get("metadatas", [])
    return [
        d for d, m in zip(docs, metas)
        if m.get("filename","").lower() == filename.lower()
        or m.get("source","").lower()   == filename.lower()
    ]


@router.post("/mindmap", response_model=MindMapResponse)
def generate_mindmap(request: MindMapRequest):
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise HTTPException(500, "GROQ_API_KEY not set in .env")

    try:
        vectorstore = Chroma(collection_name=COLLECTION_NAME,
                             persist_directory=CHROMA_DB_PATH,
                             embedding_function=_get_embeddings())
    except Exception as exc:
        raise HTTPException(500, f"ChromaDB error: {exc}")

    chunks = _get_file_chunks(vectorstore, request.filename)
    if not chunks:
        raise HTTPException(404, f"No chunks for '{request.filename}'. Is it ingested?")

    # Prioritise topic-relevant chunks if topic given
    if request.topic.strip():
        try:
            results = vectorstore.similarity_search(request.topic, k=12)
            topic_chunks = [
                d.page_content for d in results
                if d.metadata.get("filename","").lower() == request.filename.lower()
                or d.metadata.get("source","").lower()   == request.filename.lower()
            ]
            chunks = topic_chunks + [c for c in chunks if c not in topic_chunks]
        except Exception:
            pass

    text   = "\n\n".join(chunks)[:3000]
    center = request.topic.strip() or os.path.splitext(request.filename)[0]
    llm    = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1, groq_api_key=groq_key)

    prompt = (
        f'Analyze content from "{request.filename}" and return ONLY valid JSON:\n'
        f'{{"center":"Main topic","branches":[{{"topic":"Branch","subtopics":["p1","p2"]}}]}}\n'
        f'4-6 branches, 2-4 subtopics each, all under 8 words.\nCONTENT:\n{text}'
    )

    try:
        raw = llm.invoke(prompt).content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$",           "", raw)
        data = json.loads(raw)
        return MindMapResponse(
            center  =data["center"],
            branches=[MindMapBranch(**b) for b in data["branches"]],
        )
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON from LLM: %s", raw[:300])
        raise HTTPException(500, f"LLM returned invalid JSON: {exc}")
    except Exception as exc:
        logger.exception("Mind map generation failed")
        raise HTTPException(500, str(exc))