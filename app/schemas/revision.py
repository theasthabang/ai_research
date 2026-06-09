from typing import List
from pydantic import BaseModel, Field


class RevisionRequest(BaseModel):
    filename: str = Field(..., description="Ingested PDF filename")


class CrispNote(BaseModel):
    heading: str
    point:   str


class Keyword(BaseModel):
    term:  str
    color: str


class TopicSection(BaseModel):
    topic:       str
    mindmap:     dict
    crisp_notes: List[CrispNote]
    keywords:    List[Keyword]


class RevisionResponse(BaseModel):
    filename: str
    sections: List[TopicSection]