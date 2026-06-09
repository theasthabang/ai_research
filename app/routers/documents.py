"""app/routers/documents.py — /documents and /history endpoints."""
from fastapi import APIRouter
from app.ingest import list_ingested_documents
from app.memory import clear_memory, get_history

router = APIRouter()

@router.get("/documents")
def get_documents():
    return list_ingested_documents()

@router.get("/history/{session_id}")
def get_session_history(session_id: str):
    return {"history": get_history(session_id)}

@router.delete("/history/{session_id}")
def delete_session_history(session_id: str):
    clear_memory(session_id)
    return {"message": "cleared"}