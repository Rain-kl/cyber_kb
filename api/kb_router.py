from fastapi import APIRouter, HTTPException, Request
from fastapi import UploadFile, File, Query
from fastapi.responses import JSONResponse
from loguru import logger
from api.ext import (
    require_authorization,
    parse_query_response,
    document_processor,
    embedding_model,
)
from api.model import QueryResponseModel, OK
from core.vector_store import KBVectorStore

router = APIRouter(tags=["knowledge_base"])
authorization = "test"


@router.get("/documents/list")
async def get_documents_list(
    request: Request,
    limit: int = Query(10, description="返回结果数量"),
):
    """获取知识库中的文档列表"""
    try:
        # authorization = request.headers.get("authorization", "").replace("Bearer ", "")
        authorization = "test"
        vector_store = KBVectorStore(authorization)
        # vector_store = VectorStore("documents")
        results = vector_store.list_all_documents(limit)

        return OK(data=results)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")


@router.post("/documents/upload")
# @require_authorization
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
):
    """上传文档到知识库"""
    # try:
    # 保存文件
    # authorization = request.headers.get("authorization", "").replace("Bearer ", "")
    authorization = "test"
    vector_store = KBVectorStore(authorization)

    file_path, filename, md5hash = document_processor.save_file(file)

    # 提取内容
    try:
        response = document_processor.process_document(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"tika processing error: {str(e)}")
    logger.info(f"tika processing complete! total nums: {len(f"{response}")}")
    content = response["content"]
    metadata = response["metadata"]
    # 文本分块
    chunks: list = document_processor.chunk_text(content)
    logger.info(f"chunk text complete! total nums: {len(chunks)}")

    if not chunks:
        return JSONResponse(
            status_code=400, content={"message": "无法从文档中提取内容"}
        )

    # 获取嵌入向量
    embeddings = await embedding_model.get_embeddings_batch(chunks)

    # 准备元数据
    doc_id = md5hash
    metadata_list = [
        {
            "doc_id": doc_id,
            "filename": filename,
            "chunk_index": i,
            "mime_type": metadata.get("Content-Type", "unknown"),
            "total_chunks": len(chunks),
        }
        for i in range(len(chunks))
    ]

    # 存储到向量数据库
    vector_store.add_documents(chunks, embeddings, metadata_list, doc_id)

    return {
        "message": "文档上传成功",
        "doc_id": doc_id,
        "filename": filename,
        "chunk_count": len(chunks),
        "summary": response["content"][:100] + "...",
    }

    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")


@router.get("/query/embedding")
@require_authorization
async def search(
    request: Request,
    query: str = Query(..., description="搜索查询"),
    top_k: int = Query(5, description="返回结果数量"),
) -> OK:
    """搜索知识库"""
    try:
        authorization = request.headers.get("authorization", "").replace("Bearer ", "")
        vector_store = KBVectorStore(authorization)
        # vector_store = VectorStore("documents")

        # 获取查询的嵌入向量
        query_embedding = await embedding_model.get_embedding(query)

        # 搜索向量数据库
        results = vector_store.search_by_embedding(query_embedding, top_k)

        response_items: list[QueryResponseModel] = parse_query_response(results)

        return OK(data=response_items)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


#
# @router.get("/query/keyword")
# @require_authorization
# async def search_by_keyword(
#         request: Request,
#         keyword: str = Query(..., description="关键字搜索"),
#         top_k: int = Query(5, description="返回结果数量"),
# ) -> OK:
#     """基于关键字搜索知识库"""
#     try:
#         authorization = request.headers.get("authorization", "").replace("Bearer ", "")
#         vector_store = VectorStore(authorization)
#         # vector_store = VectorStore("documents")
#         results = vector_store.search_by_keyword(keyword, top_k)
#
#         response_items: list[QueryResponseModel] = parse_query_response(results)
#
#         return OK(data=response_items)
#
#     except Exception as e:
#         logging.exception(e)
#         raise HTTPException(status_code=500, detail=f"关键字搜索失败: {str(e)}")
