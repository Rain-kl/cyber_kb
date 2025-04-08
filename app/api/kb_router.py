from fastapi import APIRouter, HTTPException
from fastapi import UploadFile, File, Query
from fastapi.responses import JSONResponse

from app.config import OLLAMA_API_URL, OLLAMA_MODEL_NAME, TIKA_SERVER_URL
from app.core.document_processor import DocumentProcessor
from app.core.embedding_async import AsyncOllamaEmbeddingModel
from app.core.vector_store import VectorStore

router = APIRouter()

# 初始化组件
document_processor = DocumentProcessor(TIKA_SERVER_URL)
embedding_model = AsyncOllamaEmbeddingModel(OLLAMA_API_URL, OLLAMA_MODEL_NAME)
vector_store = VectorStore()


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文档到知识库"""
    # try:
    # 保存文件
    file_path, filename, md5hash = document_processor.save_file(file)

    # 提取内容
    try:
        response = document_processor.process_document(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"tika processing error: {str(e)}")

    content = response["content"]
    metadata = response["metadata"]
    # 文本分块
    chunks: list = document_processor.chunk_text(content)

    if not chunks:
        return JSONResponse(
            status_code=400,
            content={"message": "无法从文档中提取内容"}
        )

    # 获取嵌入向量
    embeddings = await embedding_model.get_embeddings(chunks)

    # 准备元数据
    doc_id = md5hash
    metadata_list = [
        {
            "doc_id": doc_id,
            "filename": filename,
            "chunk_index": i,
            "mime_type": metadata.get("Content-Type", "unknown"),
            "total_chunks": len(chunks)
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
        "summary": response["content"][:100] + "..."
    }

    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")


@router.get("/query/embedding")
async def search(
        query: str = Query(..., description="搜索查询"),
        top_k: int = Query(5, description="返回结果数量")
):
    """搜索知识库"""
    try:
        # 获取查询的嵌入向量
        query_embedding = await embedding_model.get_embedding(query)

        # 搜索向量数据库
        results = vector_store.search_by_embedding(query_embedding, top_k)

        # 处理结果
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        response_items = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            response_items.append({
                "content": doc,
                "metadata": meta,
                "relevance_score": 1 - dist  # 转换距离为相关性分数
            })

        return {"results": response_items}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/query/keyword")
async def search_by_keyword(
        keyword: str = Query(..., description="关键字搜索"),
        top_k: int = Query(5, description="返回结果数量")
):
    """基于关键字搜索知识库"""
    try:
        results = vector_store.search_by_keyword(keyword, top_k)

        # 处理结果
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        response_items = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            response_items.append({
                "content": doc,
                "metadata": meta,
                "relevance_score": 1 - dist
            })

        return {"results": response_items}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"关键字搜索失败: {str(e)}")
