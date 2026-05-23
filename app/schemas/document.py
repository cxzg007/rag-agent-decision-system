from typing import Literal

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    doc_id: str
    chunk_id: str
    text: str
    chunk_level: Literal["parent", "child"] = "child"
    parent_id: str | None = None
    child_index: int | None = None
    title: str | None = None
    section: str | None = None
    page: int | None = None
    metadata: dict = Field(default_factory=dict)


class DocumentIngestResponse(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    indexed_count: int
