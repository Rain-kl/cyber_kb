from typing import Any

from pydantic import BaseModel


class OK(BaseModel):
    ok: bool = True
    message: str = "ok"
    data: Any
    # Optional: You can also add a timestamp or other fields if needed


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
