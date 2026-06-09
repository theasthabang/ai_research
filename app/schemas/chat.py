from typing import List, Literal, Optional
from pydantic import BaseModel, Field

SearchMode = Literal["web_academic", "my_documents", "all_sources"]

class ChatRequest(BaseModel):
    query:      str        = Field(..., description="User research question")
    session_id: str        = Field(..., description="Unique session ID")
    mode:       SearchMode = Field("all_sources")

class ConfidenceSchema(BaseModel):
    score:  int = Field(..., description="Score 1-10")
    reason: str = Field(..., description="Explanation")

class ChatResponse(BaseModel):
    answer:     str                        = Field(...)
    sources:    List[str]                  = Field(...)
    confidence: Optional[ConfidenceSchema] = Field(None)