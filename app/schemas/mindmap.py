from typing import List
from pydantic import BaseModel, Field

class MindMapRequest(BaseModel):
    filename: str = Field(..., description="Ingested PDF filename")
    topic:    str = Field("",  description="Optional focus topic")

class MindMapBranch(BaseModel):
    topic:     str       = Field(...)
    subtopics: List[str] = Field(...)

class MindMapResponse(BaseModel):
    center:   str               = Field(...)
    branches: List[MindMapBranch] = Field(...)