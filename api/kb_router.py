import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi import UploadFile, File
from fastapi.responses import HTMLResponse
from loguru import logger

from api.ext import (
    require_authorization,
)
from api.model import OK
from utils.document_queue import (
    DocumentProcessingManager,
    TaskStatus,
)
from utils.user_database import default_kb_db, KBUploadRecord
from utils.user_file_manager import LocalUserFileManager

router = APIRouter()


# 模拟的文档转换函数，使用10秒延迟
def mock_convert_function(filepath: str) -> str:
    """模拟文档转换函数，延迟10秒"""
    logger.info(f"开始转换文件: {filepath}")
    time.sleep(10)  # 模拟10秒的处理时间

    # 读取原始文件内容
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        # 如果不是UTF-8编码，尝试其他编码
        try:
            with open(filepath, "r", encoding="gbk") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(filepath, "rb") as f:
                content = f.read().decode("utf-8", errors="ignore")

    converted_content = f"[已转换] 文件: {Path(filepath).name}\n转换时间: {datetime.now()}\n原始内容:\n{content}"
    logger.info(f"文件转换完成: {filepath}")
    return converted_content


# 初始化文件管理器和文档处理管理器
file_manager = LocalUserFileManager("data/user")
document_manager = DocumentProcessingManager(
    kb_database=default_kb_db,
    file_manager=file_manager,
    convert_func=mock_convert_function,
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
):
    """
    上传文档到处理队列
    """
    try:
        # 从request.state获取用户token（由require_authorization装饰器设置）
        user_token = getattr(request.state, "authorization", None)
        if not user_token:
            raise HTTPException(status_code=401, detail="未找到授权信息")

        # 提交任务到处理队列
        doc_id = document_manager.submit_task(user_token, file)

        logger.info(f"文档已提交到处理队列: {doc_id}, 文件名: {file.filename}")

        return OK(
            data={
                "doc_id": doc_id,
                "filename": file.filename,
                "status": "submitted",
                "message": "文档已提交到处理队列",
            }
        )

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
