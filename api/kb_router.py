from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request, Form
from fastapi import UploadFile, File
from fastapi.responses import HTMLResponse
from loguru import logger

from api.ext import (
    require_authorization,
)
from api.model import OK
from core.convertor.DoclingDocumentConvertorImpl import DoclingDocumentConvertorImpl
from core.document_queue import (
    DocumentProcessingManager,
    TaskStatus,
)
from core.ext import default_kb_db, file_manager
from utils.user_database import KBUploadRecord

router = APIRouter()


# 模拟的文档转换函数，使用10秒延迟
def convert_function(filepath: str) -> str:
    convertor = DoclingDocumentConvertorImpl(filepath)
    return convertor.convert()


# 初始化文件管理器和文档处理管理器
document_manager = DocumentProcessingManager(
    kb_database=default_kb_db,
    file_manager=file_manager,
    convert_func=convert_function,
    max_workers=2,
)


@router.get("/", summary="API 服务信息")
async def root():
    """
    API 根路径，返回服务信息
    """
    with open(
        "html/kb_demo.html",
        "r",
        encoding="utf-8",
    ) as f:
        html_content = f.read()
    return HTMLResponse(html_content)


@router.post("/file/upload", response_model=OK[Dict[str, str]])
@require_authorization
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    collection_id: Optional[str] = Form(None),
):
    """
    上传文档到处理队列

    Args:
        :param request:
        :param file: 上传的文件
        :param collection_id: 可选的集合ID，用于将文档分组到指定的知识库集合中
    """
    try:
        # 从request.state获取用户token（由require_authorization装饰器设置）
        user_token = getattr(request.state, "authorization", None)
        if not user_token:
            raise HTTPException(status_code=401, detail="未找到授权信息")

        # 如果提供了collection_id，验证集合是否存在
        if collection_id:
            collection_info = default_kb_db.get_collection_info(collection_id)
            if not collection_info:
                raise HTTPException(status_code=404, detail="指定的集合不存在")
        else:
            collection_id = f"default_{user_token}"

        # 提交任务到处理队列
        doc_id = document_manager.submit_task(
            user_token, file, collection_id=collection_id
        )

        # 注意：collection_id 已经在 submit_task 中处理了，不需要额外的 update_upload_record 调用

        logger.info(
            f"文档已提交到处理队列: {doc_id}, 文件名: {file.filename}, 集合ID: {collection_id}"
        )

        return OK(
            data={
                "doc_id": doc_id,
                "filename": file.filename,
                "collection_id": collection_id,
                "status": "submitted",
                "message": "文档已提交到处理队列",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/file/status/{doc_id}", response_model=OK[Dict[str, Any]])
@require_authorization
async def get_task_status(request: Request, doc_id: str):
    """
    获取任务状态
    """
    try:
        user_token = getattr(request.state, "authorization", None)
        task = document_manager.get_task_status(doc_id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task.status == TaskStatus.COMPLETED:
            # 获取处理后的文件内容
            original_dir, processed_file_path = file_manager.get_doc_dirs(user_token)

            if not processed_file_path.exists():
                raise HTTPException(status_code=404, detail="处理后的文件不存在")
            content = file_manager.get_processed_file_content(user_token, doc_id)
        else:
            content = None

        # 转换为字典格式
        task_dict = {
            "doc_id": task.doc_id,
            "user_token": task.user_token,
            "filename": task.filename,
            "status": task.status,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": (
                task.completed_at.isoformat() if task.completed_at else None
            ),
            "result": {},
            "err_msg": task.err_msg,
        }

        if content:
            task_dict["result"]["content"] = content

        return OK(data=task_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")


@router.get("/queue/status", response_model=OK[Dict[str, Any]])
async def get_queue_status():
    """
    获取队列状态
    """
    try:
        queue_status = document_manager.get_queue_status()

        status_dict = {
            "queue_size": queue_status.queue_size,
            "processing_tasks": queue_status.processing_tasks,
            "completed_count": queue_status.completed_count,
            "failed_count": queue_status.failed_count,
        }

        return OK(data=status_dict)

    except Exception as e:
        logger.error(f"获取队列状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取队列状态失败: {str(e)}")


@router.get("/tasks", response_model=OK[List[Dict[str, Any]]])
@require_authorization
async def get_tasks(request: Request):
    """
    获取用户所有任务
    """
    try:
        user_token = getattr(request.state, "authorization", None)
        tasks: list[KBUploadRecord] = default_kb_db.get_user_uploads(user_token)

        tasks_list = []
        for task in tasks:
            task_dict = {
                "doc_id": task.doc_id,
                "user_token": task.user_token,
                "filename": task.filename,
                "status": task.status,
                "created_at": (
                    task.upload_time.isoformat() if task.upload_time else None
                ),
                "started_at": (
                    task.process_start_time.isoformat()
                    if task.process_start_time
                    else None
                ),
                "completed_at": (
                    task.process_end_time.isoformat() if task.process_end_time else None
                ),
                "err_msg": task.err_msg,
            }
            tasks_list.append(task_dict)

        return OK(data=tasks_list)

    except Exception as e:
        logger.error(f"获取所有任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取所有任务失败: {str(e)}")


@router.delete("/file/{doc_id}", response_model=OK[Dict[str, str]])
@require_authorization
async def delete_document(request: Request, doc_id: str):
    """
    删除指定的上传文件

    Args:
        :param request:
        :param doc_id: 要删除的文档ID
    """
    try:
        user_token = getattr(request.state, "authorization", None)
        if not user_token:
            raise HTTPException(status_code=401, detail="未找到授权信息")

        # 获取上传记录，验证文档是否存在且属于当前用户
        upload_record = default_kb_db.get_upload_record(doc_id)
        if not upload_record:
            raise HTTPException(status_code=404, detail="文档不存在")

        if upload_record.user_token != user_token:
            raise HTTPException(status_code=403, detail="无权删除此文档")

        # 删除数据库记录
        db_deleted = default_kb_db.delete_upload_record(doc_id)
        if not db_deleted:
            raise HTTPException(status_code=500, detail="删除数据库记录失败")

        # 删除文件系统中的文件
        file_deleted = file_manager.delete_user_doc(user_token, doc_id)
        if not file_deleted:
            logger.warning(f"删除文件失败，但数据库记录已删除: {doc_id}")

        logger.info(f"成功删除文档: {doc_id}, 用户: {user_token}")

        return OK(
            data={
                "doc_id": doc_id,
                "filename": upload_record.filename,
                "status": "deleted",
                "message": "文档删除成功",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")


@router.get(
    "/collection/{collection_id}/documents", response_model=OK[List[Dict[str, Any]]]
)
@require_authorization
async def get_collection_documents(
    request: Request, collection_id: str, limit: int = 50, status: Optional[str] = None
):
    """
    查询指定集合下的文档

    Args:
        request: fastapi Request 对象
        collection_id: 集合ID
        limit: 返回文档数量限制，默认50
        status: 可选的状态过滤器，如 'completed', 'processing', 'failed', 'pending'
    """
    try:
        user_token = getattr(request.state, "authorization", None)
        if not user_token:
            raise HTTPException(status_code=401, detail="未找到授权信息")

        # 验证集合是否存在
        collection_info = default_kb_db.get_collection_info(collection_id)
        if not collection_info:
            raise HTTPException(status_code=404, detail="集合不存在")

        # 获取集合中的文档
        documents = default_kb_db.get_collection(user_token, collection_id)

        # 根据状态过滤（如果提供了status参数）
        if status:
            documents = [doc for doc in documents if doc.status == status]

        # 限制返回数量
        documents = documents[:limit]

        # 转换为字典格式
        documents_list = []
        for doc in documents:
            doc_dict = {
                "doc_id": doc.doc_id,
                "user_token": doc.user_token,
                "collection_id": doc.collection_id,
                "filename": doc.filename,
                "status": doc.status,
                "upload_time": doc.upload_time.isoformat() if doc.upload_time else None,
                "process_start_time": (
                    doc.process_start_time.isoformat()
                    if doc.process_start_time
                    else None
                ),
                "process_end_time": (
                    doc.process_end_time.isoformat() if doc.process_end_time else None
                ),
                "err_msg": doc.err_msg,
                "mime_type": doc.mime_type,
            }
            documents_list.append(doc_dict)

        logger.info(f"获取集合文档: {collection_id}, 文档数量: {len(documents_list)}")

        return OK(data=documents_list)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取集合文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取集合文档失败: {str(e)}")


@router.get("/collections", response_model=OK[List[Dict[str, Any]]])
@require_authorization
async def get_user_collections(request: Request):
    """
    获取用户的所有集合列表
    """
    try:
        user_token = getattr(request.state, "authorization", None)
        if not user_token:
            raise HTTPException(status_code=401, detail="未找到授权信息")

        # 获取用户的所有集合
        collections = default_kb_db.list_collections(user_token)

        logger.info(f"获取用户集合列表: {user_token}, 集合数量: {len(collections)}")

        return OK(data=collections)

    except Exception as e:
        logger.error(f"获取集合列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取集合列表失败: {str(e)}")


@router.post("/collections", response_model=OK[Dict[str, str]])
@require_authorization
async def create_collection(
    request: Request,
    collection_name: str = Form(...),
    description: Optional[str] = Form(None),
):
    """
    创建新的知识库集合

    Args:
        request: fastapi Request 对象
        collection_name: 集合名称
        description: 集合描述（可选）
    """
    try:
        user_token = getattr(request.state, "authorization", None)
        if not user_token:
            raise HTTPException(status_code=401, detail="未找到授权信息")

        # 生成集合ID
        import uuid

        collection_id = str(uuid.uuid4())

        # 创建集合
        success = default_kb_db.create_collection(
            collection_id=collection_id,
            collection_name=collection_name,
            created_by=user_token,
            description=description or "",
        )

        if not success:
            raise HTTPException(status_code=500, detail="创建集合失败")

        logger.info(
            f"成功创建集合: {collection_id}, 名称: {collection_name}, 用户: {user_token}"
        )

        return OK(
            data={
                "collection_id": collection_id,
                "collection_name": collection_name,
                "description": description,
                "created_by": user_token,
                "message": "集合创建成功",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建集合失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建集合失败: {str(e)}")


# =============================================================================
# 向量库相关 API
# =============================================================================


@router.post("/vector/search", response_model=OK[Dict[str, Any]])
@require_authorization
async def search_vector_documents(
    request: Request,
    query_text: str = Form(...),
    collection_id: str = Form(...),
    top_k: int = Form(5),
):
    """
    在向量库中搜索文档

    Args:
        request: fastapi Request 对象
        query_text: 查询文本
        collection_id: 集合ID
        top_k: 返回结果数量，默认5
    """
    try:
        user_token = getattr(request.state, "authorization", None)
        if not user_token:
            raise HTTPException(status_code=401, detail="未找到授权信息")

        # 验证集合是否存在
        collection_info = default_kb_db.get_collection_info(collection_id)
        if not collection_info:
            raise HTTPException(status_code=404, detail="指定的集合不存在")

        # 执行搜索
        search_results = await document_manager.search_documents(
            user_token=user_token,
            collection_id=collection_id,
            query_text=query_text,
            top_k=top_k,
        )

        logger.info(
            f"向量搜索完成: 用户={user_token}, 集合={collection_id}, 查询='{query_text}', 结果数={len(search_results.get('documents', []))}"
        )

        return OK(
            data={
                "query_text": query_text,
                "collection_id": collection_id,
                "top_k": top_k,
                "results": search_results,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"向量搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"向量搜索失败: {str(e)}")


@router.get("/vector/documents/{collection_id}", response_model=OK[Dict[str, Any]])
@require_authorization
async def list_vector_documents(
    request: Request,
    collection_id: str,
    limit: Optional[int] = None,
):
    """
    列出集合中向量库的所有文档

    Args:
        request: fastapi Request 对象
        collection_id: 集合ID
        limit: 限制返回数量（可选）
    """
    try:
        user_token = getattr(request.state, "authorization", None)
        if not user_token:
            raise HTTPException(status_code=401, detail="未找到授权信息")

        # 验证集合是否存在
        collection_info = default_kb_db.get_collection_info(collection_id)
        if not collection_info:
            raise HTTPException(status_code=404, detail="指定的集合不存在")

        # 获取文档列表
        documents = document_manager.list_vector_store_documents(
            user_token=user_token, collection_id=collection_id, limit=limit
        )

        # 获取文档数量
        doc_count = document_manager.get_vector_store_document_count(
            user_token=user_token, collection_id=collection_id
        )

        logger.info(
            f"列出向量文档: 用户={user_token}, 集合={collection_id}, 文档数={doc_count}"
        )

        return OK(
            data={
                "collection_id": collection_id,
                "document_count": doc_count,
                "documents": documents,
                "limit": limit,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"列出向量文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"列出向量文档失败: {str(e)}")


@router.delete(
    "/vector/document/{collection_id}/{doc_id}", response_model=OK[Dict[str, Any]]
)
@require_authorization
async def delete_vector_document(
    request: Request,
    collection_id: str,
    doc_id: str,
):
    """
    从向量库中删除指定文档

    Args:
        request: fastapi Request 对象
        collection_id: 集合ID
        doc_id: 文档ID
    """
    try:
        user_token = getattr(request.state, "authorization", None)
        if not user_token:
            raise HTTPException(status_code=401, detail="未找到授权信息")

        # 验证集合是否存在
        collection_info = default_kb_db.get_collection_info(collection_id)
        if not collection_info:
            raise HTTPException(status_code=404, detail="指定的集合不存在")

        # 从向量库中删除文档
        deleted_count = document_manager.delete_document_from_vector_store(
            user_token=user_token, collection_id=collection_id, doc_id=doc_id
        )

        logger.info(
            f"从向量库删除文档: 用户={user_token}, 集合={collection_id}, 文档={doc_id}, 删除块数={deleted_count}"
        )

        return OK(
            data={
                "collection_id": collection_id,
                "doc_id": doc_id,
                "deleted_chunks": deleted_count,
                "message": f"成功从向量库删除文档，删除了 {deleted_count} 个块",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除向量文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除向量文档失败: {str(e)}")


@router.get("/vector/stats/{collection_id}", response_model=OK[Dict[str, Any]])
@require_authorization
async def get_vector_collection_stats(
    request: Request,
    collection_id: str,
):
    """
    获取集合的向量库统计信息

    Args:
        request: fastapi Request 对象
        collection_id: 集合ID
    """
    try:
        user_token = getattr(request.state, "authorization", None)
        if not user_token:
            raise HTTPException(status_code=401, detail="未找到授权信息")

        # 验证集合是否存在
        collection_info = default_kb_db.get_collection_info(collection_id)
        if not collection_info:
            raise HTTPException(status_code=404, detail="指定的集合不存在")

        # 获取统计信息
        doc_count = document_manager.get_vector_store_document_count(
            user_token=user_token, collection_id=collection_id
        )

        # 获取上传记录统计
        upload_records = default_kb_db.get_collection(user_token, collection_id)

        stats = {
            "collection_id": collection_id,
            "collection_name": collection_info.get("collection_name", ""),
            "vector_document_count": doc_count,
            "total_uploads": len(upload_records),
            "completed_uploads": len(
                [r for r in upload_records if r.status == "completed"]
            ),
            "failed_uploads": len([r for r in upload_records if r.status == "failed"]),
            "pending_uploads": len(
                [r for r in upload_records if r.status in ["pending", "processing"]]
            ),
        }

        logger.info(f"获取向量集合统计: 用户={user_token}, 集合={collection_id}")

        return OK(data=stats)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取向量集合统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取向量集合统计失败: {str(e)}")


@router.get("/vector/collections", response_model=OK[List[Dict[str, Any]]])
@require_authorization
async def list_vector_collections(request: Request):
    """
    列出用户的所有向量集合及其统计信息
    """
    try:
        user_token = getattr(request.state, "authorization", None)
        if not user_token:
            raise HTTPException(status_code=401, detail="未找到授权信息")

        # 获取用户的集合列表
        collections = default_kb_db.list_collections(user_token)

        # 为每个集合添加向量库统计信息
        collection_stats = []
        for collection in collections:
            collection_id = collection["collection_id"]

            # 获取向量库文档数量
            try:
                doc_count = document_manager.get_vector_store_document_count(
                    user_token=user_token, collection_id=collection_id
                )
            except:
                doc_count = 0

            collection_stat = {**collection, "vector_document_count": doc_count}
            collection_stats.append(collection_stat)

        logger.info(f"列出向量集合: 用户={user_token}, 集合数={len(collection_stats)}")

        return OK(data=collection_stats)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"列出向量集合失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"列出向量集合失败: {str(e)}")
