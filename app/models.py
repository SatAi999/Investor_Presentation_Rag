from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    status: str
    chunk_count: int
    document: str
    message: str


class Citation(BaseModel):
    page: int
    chunk_id: str
    excerpt: str


class RetrievalInfo(BaseModel):
    top_k: int
    chunks_consulted: int


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Analyst question about the presentation")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")


class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]
    retrieval: RetrievalInfo
    limitations: List[str]
