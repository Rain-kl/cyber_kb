# api/endpoints.py
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.ext import require_authorization
from app.core.vector_store import MemoVectorStore
from app.api.ext import require_authorization, parse_query_response, document_processor, embedding_model

router = APIRouter(tags=["memo"])


class SearchMemoriesRequest(BaseModel):
    text: str
    limit: str = "5000"
    similarity: str = "0.3"
    searchMode: str = "mixedRecall"


class MemoryListRequest(BaseModel):
    fromDate: str
    toDate: str
    limit: int = 1000


class ChatSummary(BaseModel):
    timestamp: str
    summary: str


@router.get("/list")
@require_authorization
async def list_memories(request: Request, from_date: str, to_date: str, limit: int = 1000):
    # Process the memory list request
    try:
        # 这里可以使用 authorization 变量
        # Here you would typically call your database or external API
        # This is a placeholder for the actual implementation
        authorization = request.headers.get("authorization", "").replace("Bearer ", "")
        vector_store = MemoVectorStore(authorization)
        vector_store.list_all_documents()

        result = {
            "success": True,
            "data": []  # Memory list would be populated here
        }
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memories: {str(e)}")


# @router.post("/uploadSummary")
# @require_authorization
# async def upload_memo_summary(request: Request, summary: ChatSummary):
#     # Process the memory upload request
#     try:
#         # 这里可以使用 authorization 变量
#         # Here you would typically store the memory in your database
#         # This is a placeholder for the actual implementation
#         authorization = request.headers.get("authorization", "").replace("Bearer ", "")
#         vector_store = MemoVectorStore(authorization)
#         # 获取嵌入向量
#         embeddings = await embedding_model.get_embeddings(summary)
#
#         metadata_list = {
#             "doc_id": str(int(time.time())),
#             "filename": f"summary_{int(time.time())}",
#             "chunk_index": 0,
#             "mime_type": "unknown",
#             "total_chunks": len(summary)
#         }
#
#         # 存储到向量数据库
#         vector_store.add_documents(summary, embeddings, metadata_list, doc_id)
#
#         return {
#             "message": "文档上传成功",
#             "doc_id": doc_id,
#             "filename": filename,
#             "chunk_count": len(chunks),
#             "summary": response["content"][:100] + "..."
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to upload memory: {str(e)}")


@router.post("/query/embedding")
@require_authorization
async def search_memories(request: Request, search_request: SearchMemoriesRequest, authorization: str = None):
    # Process the search memories request
    try:
        authorization = request.headers.get("authorization", "").replace("Bearer ", "")
        vector_store = MemoVectorStore(authorization)
        # 这里可以使用 authorization 变量
        # Here you would typically query your vector database or similar
        # This is a placeholder for the actual implementation
        result = {
            "success": True,
            "data": []  # Search results would be populated here
        }
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search memories: {str(e)}")
