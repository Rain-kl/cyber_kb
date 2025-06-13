from typing import TypeVar, Generic

from pydantic import BaseModel

T = TypeVar("T")


class OK(BaseModel, Generic[T]):
    ok: bool = True
    message: str = "ok"
    data: T


class MetadataModel(BaseModel):
    chunk_index: int
    doc_id: str
    total_chunks: int
    mime_type: str
    filename: str


class QueryResponseModel(BaseModel):
    content: str
    metadata: MetadataModel
    relevance_score: float
