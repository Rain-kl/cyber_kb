# api/endpoints.py
import time
from typing import List, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.ext import embedding_model
from app.api.model import OK
from app.core.mdb import MemoryDB
from app.core.vector_store import MemoVectorStore

router = APIRouter(tags=["memo"])
authorization = "test"


class MemoryListRequest(BaseModel):
    fromDate: str
    toDate: str
    limit: int = 1000


class UploadLayer1Request(BaseModel):
    content: str  # summary 字段从请求体中获取


# 定义 Pydantic 模型，用于从请求体中获取 summary
class UploadSummaryRequest(BaseModel):
    summary: str  # summary 字段从请求体中获取


class UploadLayer3Request(BaseModel):
    # def add_layer3_record(self, apikey: str, behavior: str, instruction: str) -> int:
    behavior: str
    instruction: str


class QueryResponseModel(BaseModel):
    layer1: List[Dict]
    layer2: Dict
    layer3: List[Dict]


########################################################################################################################
@router.get("/layer1/list")
# @require_authorization
async def l1_list_memories(request: Request):
    # Process the memory list request
    try:
        # authorization = request.headers.get("authorization", "").replace("Bearer ", "")
        with MemoryDB() as db:
            results = db.get_layer1_records_by_apikey(authorization)

        return OK(data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memories: {str(e)}")


@router.post("/layer1/upload")
# @require_authorization  # 假设这是个自定义装饰器，保留它
async def l1_upload_memo_summary(request: Request, upload_data: UploadLayer1Request):
    # Process the memory upload request
    try:
        # authorization = request.headers.get("authorization", "").replace("Bearer ", "")

        with MemoryDB() as db:
            results = db.add_layer1_record(authorization, upload_data.content)

        return OK(data=results)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload memory: {str(e)}")


########################################################################################################################

@router.get("/layer2/list")
# @require_authorization
async def l2_list_memories(request: Request):
    # Process the memory list request
    try:
        # authorization = request.headers.get("authorization", "").replace("Bearer ", "")
        vector_store = MemoVectorStore(authorization)
        results = vector_store.list_all_documents()

        return OK(data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memories: {str(e)}")


@router.post("/layer2/upload")
# @require_authorization  # 假设这是个自定义装饰器，保留它
async def l2_upload_memo_summary(request: Request, upload_data: UploadSummaryRequest):
    # Process the memory upload request
    try:
        # 获取授权信息
        # authorization = request.headers.get("authorization", "").replace("Bearer ", "")

        vector_store = MemoVectorStore(authorization)

        # 获取嵌入向量
        embeddings = await embedding_model.get_embedding(upload_data.summary)  # 使用 upload_data.summary
        metadata_list = {
            "doc_id": str(int(time.time())),
            "filename": f"summary_{int(time.time())}",
            "chunk_index": 0,
            "mime_type": "unknown",
            "total_chunks": len(upload_data.summary)  # 注意：len(summary) 是字符串长度，可能不是实际的 chunks 数
        }
        # 存储到向量数据库
        vector_store.add_documents([upload_data.summary], embeddings, [metadata_list], str(int(time.time())))
        return OK(data={
            "message": "摘要上传成功",
            "summary": upload_data.summary[:100] + "..."  # 使用 upload_data.summary
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload memory: {str(e)}")


########################################################################################################################

@router.get("/layer3/list")
# @require_authorization
async def l3_list_memories(request: Request):
    # Process the memory list request
    try:
        # 这里可以使用 authorization 变量
        # Here you would typically call your database or external API
        # This is a placeholder for the actual implementation
        # authorization = request.headers.get("authorization", "").replace("Bearer ", "")

        with MemoryDB() as db:
            results = db.get_layer3_records_by_apikey(authorization)

        return OK(data=results)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memories: {str(e)}")


@router.post("/layer3/upload")
# @require_authorization  # 假设这是个自定义装饰器，保留它
async def l3_upload_memo_summary(request: Request, upload_data: UploadLayer3Request):
    # Process the memory upload request
    try:
        # 获取授权信息
        # authorization = request.headers.get("authorization", "").replace("Bearer ", "")

        with MemoryDB() as db:
            results = db.add_layer3_record(authorization, upload_data.behavior, upload_data.instruction)

        return OK(data=results)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload memory: {str(e)}")


########################################################################################################################
@router.get("/query")
# @require_authorization
async def search_memories(request: Request, text: str) -> OK[QueryResponseModel]:
    # Process the search memories request
    try:
        # authorization = request.headers.get("authorization", "").replace("Bearer ", "")
        vector_store = MemoVectorStore(authorization)
        embeddings = await embedding_model.get_embedding(text)
        layer2 = vector_store.search_by_embedding(embeddings)

        with MemoryDB() as db:
            layer1 = db.get_layer1_records_by_apikey(authorization)
            layer3 = db.get_layer3_records_by_apikey(authorization)

        results = QueryResponseModel(
            layer1=layer1,
            layer2=layer2,
            layer3=layer3
        )
        return OK(data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search memories: {str(e)}")
