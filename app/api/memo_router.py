# api/endpoints.py

from functools import wraps
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


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


def require_authorization(func: Callable):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        authorization = request.headers.get("authorization", "").replace("Bearer ", "")
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization token is required")
        # 将授权令牌传递给原始函数，以便它可以使用
        kwargs['authorization'] = authorization
        return await func(request, *args, **kwargs)

    return wrapper


@router.get("/list")
@require_authorization
async def list_memories(request: Request, from_date: str, to_date: str, limit: int = 1000, authorization: str = None):
    # Process the memory list request
    try:
        # 这里可以使用 authorization 变量
        # Here you would typically call your database or external API
        # This is a placeholder for the actual implementation
        result = {
            "success": True,
            "data": []  # Memory list would be populated here
        }
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memories: {str(e)}")


@router.post("/upload")
@require_authorization
async def upload_memory(request: Request, summary: ChatSummary, authorization: str = None):
    # Process the memory upload request
    try:
        # 这里可以使用 authorization 变量
        # Here you would typically store the memory in your database
        # This is a placeholder for the actual implementation
        result = {
            "success": True,
            "data": {
                "id": "mem_" + summary.timestamp.replace(":", "").replace("-", "").replace(".", ""),
                "timestamp": summary.timestamp
            }
        }
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload memory: {str(e)}")


@router.post("/searchMemories")
@require_authorization
async def search_memories(request: Request, search_request: SearchMemoriesRequest, authorization: str = None):
    # Process the search memories request
    try:
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
