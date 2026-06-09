"""app/routers/chat.py — POST /chat endpoint."""
from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.agent import run_agent

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
def chat_with_agent(request: ChatRequest):
    try:
        result = run_agent(
            query=request.query,
            session_id=request.session_id,
            mode=request.mode,
        )
        return ChatResponse(
            answer    =result.get("answer", "No answer generated."),
            sources   =result.get("sources", []),
            confidence=result.get("confidence"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))