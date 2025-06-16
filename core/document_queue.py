#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档处理任务队列管理器
基于 Python 队列实现，支持后续升级到 RabbitMQ
支持用户分离和数据库记录
"""

import asyncio
import logging
import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

from fastapi import UploadFile
from pydantic import BaseModel

from core.vdb_manager import UserKBVDBManager
from utils.user_database import KnowledgeBase, KBUploadRecord
from utils.user_file_manager import UserFileManager


class TaskStatus(str, Enum):
    """任务状态枚举"""

    PENDING = "pending"  # 等待中
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失败


class DocumentTask(BaseModel):
    """文档处理任务模型"""

    doc_id: Optional[str] = None
    user_token: str
    filename: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    err_msg: Optional[str] = None


class QueueStatus(BaseModel):
    """队列状态模型"""

    queue_size: int
    processing_tasks: List[str]
    completed_count: int
    failed_count: int


class DocumentQueue:
    """文档处理队列接口（为升级 RabbitMQ 预留）"""

    def add_task(self, task: DocumentTask) -> None:
        """添加任务到队列"""
        raise NotImplementedError

    def get_next_task(self) -> Optional[DocumentTask]:
        """获取下一个待处理任务"""
        raise NotImplementedError

    def update_task_status(self, task_id: str, status: TaskStatus, **kwargs) -> None:
        """更新任务状态"""
        raise NotImplementedError

    def get_task(self, task_id: str) -> Optional[DocumentTask]:
        """根据ID获取任务"""
        raise NotImplementedError

    def get_queue_status(self) -> QueueStatus:
        """获取队列状态"""
        raise NotImplementedError

    def get_all_tasks(self) -> List[DocumentTask]:
        """获取所有任务"""
        raise NotImplementedError


class MemoryDocumentQueue(DocumentQueue):
    """基于内存的文档队列实现"""

    def __init__(self):
        self._task_queue = queue.Queue()
        self._tasks: Dict[str, DocumentTask] = {}
        self._processing_tasks: Dict[str, DocumentTask] = {}
        self._completed_tasks: Dict[str, DocumentTask] = {}
        self._failed_tasks: Dict[str, DocumentTask] = {}
        self._lock = threading.Lock()

    def add_task(self, task: DocumentTask) -> None:
        """添加任务到队列"""
        with self._lock:
            task.doc_id = task.doc_id or str(uuid.uuid4())
            self._tasks[task.doc_id] = task
            self._task_queue.put(task.doc_id)

    def get_next_task(self) -> Optional[DocumentTask]:
        """获取下一个待处理任务"""
        try:
            task_id = self._task_queue.get_nowait()
            with self._lock:
                if task_id in self._tasks:
                    task = self._tasks[task_id]
                    task.status = TaskStatus.PROCESSING
                    task.started_at = datetime.now()
                    self._processing_tasks[task_id] = task
                    return task
        except queue.Empty:
            return None
        return None

    def update_task_status(self, task_id: str, status: TaskStatus, **kwargs) -> None:
        """更新任务状态"""
        with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.status = status

                if status == TaskStatus.COMPLETED:
                    task.completed_at = datetime.now()
                    self._processing_tasks.pop(task_id, None)
                    self._completed_tasks[task_id] = task
                elif status == TaskStatus.FAILED:
                    task.completed_at = datetime.now()
                    task.err_msg = kwargs.get("err_msg", "")
                    self._processing_tasks.pop(task_id, None)
                    self._failed_tasks[task_id] = task

    def get_task(self, task_id: str) -> Optional[DocumentTask]:
        """根据ID获取任务"""
        with self._lock:
            return self._tasks.get(task_id)

    def get_queue_status(self) -> QueueStatus:
        """获取队列状态"""
        with self._lock:
            return QueueStatus(
                queue_size=self._task_queue.qsize(),
                processing_tasks=list(self._processing_tasks.keys()),
                completed_count=len(self._completed_tasks),
                failed_count=len(self._failed_tasks),
            )

    def get_all_tasks(self) -> List[DocumentTask]:
        """获取所有任务"""
        with self._lock:
            return list(self._tasks.values())


class DocumentProcessingManager:
    """文档处理管理器 - 整合队列、数据库和文件管理"""

    def __init__(
            self,
            kb_database: KnowledgeBase,
            file_manager: UserFileManager,
            convert_func: Callable[[str], str],
            max_workers: int = 3,
            queue_impl: Optional[DocumentQueue] = None,
            enable_vector_store: bool = True,
    ):
        """
        初始化文档处理管理器

        Args:
            kb_database: 用户数据库实例
            file_manager: 文件管理器实例
            convert_func: 文档转换函数，接收文件路径返回转换后的文本
            max_workers: 最大并发处理数
            queue_impl: 队列实现，默认使用内存队列
            enable_vector_store: 是否启用向量存储，默认为True
        """
        self.kb_database = kb_database
        self.file_manager = file_manager
        self.convert_func = convert_func
        self.max_workers = max_workers
        self.queue = queue_impl or MemoryDocumentQueue()
        self.enable_vector_store = enable_vector_store

        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._worker_futures: List[Future] = []
        self._running = False
        self._lock = threading.Lock()

        # 使用 Semaphore 控制最大并发数
        self._semaphore = asyncio.Semaphore(max_workers)
        self._event_loop = None

        # 缓存用户的VDB管理器实例
        self._vdb_managers: Dict[str, UserKBVDBManager] = {}

        # 启动工作线程
        self.start_workers()

    def start_workers(self):
        """启动工作线程"""
        with self._lock:
            if not self._running:
                self._running = True
                for i in range(self.max_workers):
                    future = self._executor.submit(self._worker_loop)
                    self._worker_futures.append(future)

    def stop_workers(self):
        """停止工作线程"""
        with self._lock:
            self._running = False

        # 等待所有任务完成
        for future in self._worker_futures:
            try:
                future.result(timeout=5)
            except Exception as e:
                logging.error(f"Worker thread error: {e}")

        self._executor.shutdown(wait=True)

    def _worker_loop(self):
        """工作线程循环"""
        # 创建新的事件循环用于当前线程
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._event_loop = loop

        try:
            while self._running:
                try:
                    task = self.queue.get_next_task()
                    if task:
                        # 在事件循环中运行协程
                        loop.run_until_complete(self._process_document_task(task))
                    else:
                        time.sleep(0.1)  # 没有任务时短暂休眠
                except Exception as e:
                    logging.error(f"Worker loop error: {e}")
        finally:
            loop.close()

    async def _process_document_task(self, task: DocumentTask):
        """处理单个文档任务（协程版本）"""
        async with self._semaphore:  # 控制最大并发数
            try:
                # 更新数据库状态为处理中
                await asyncio.to_thread(
                    self.kb_database.update_upload_record,
                    task.doc_id,
                    status="processing",
                    process_start_time=datetime.now(),
                )

                # 获取文件路径
                upload_record = await asyncio.to_thread(
                    self.kb_database.get_upload_record, task.doc_id
                )

                if not upload_record:
                    raise Exception(
                        f"Upload record not found for doc_id: {task.doc_id}"
                    )

                # 获取原始文件路径 - 注意save_uploaded_file时已经保存了文件
                # 我们需要重构这里，根据文件名和用户token构建文件路径
                original_dir, processed_dir = self.file_manager.get_doc_dirs(
                    task.user_token
                )

                # 根据doc_id查找原始文件
                file_extension = Path(task.filename).suffix
                original_file_path = original_dir / f"{task.doc_id}{file_extension}"

                if not original_file_path.exists():
                    raise Exception(f"Original file not found: {original_file_path}")

                # 调用转换函数（在线程中运行，避免阻塞事件循环）
                converted_text = await asyncio.to_thread(
                    self.convert_func, str(original_file_path)
                )

                # 保存转换后的文本（在线程中运行）
                processed_file_path = processed_dir / f"{task.doc_id}.txt"
                await asyncio.to_thread(
                    self._save_converted_text, processed_file_path, converted_text
                )

                # 如果启用了向量存储，将文档添加到向量库
                if self.enable_vector_store and converted_text.strip():
                    try:
                        vdb_manager = self._get_vdb_manager(task.user_token)

                        # 获取collection_id，如果没有则使用默认的"default"
                        collection_id = upload_record.collection_id or "default"

                        # 将文本分割成块
                        chunks = self._split_text_into_chunks(converted_text)

                        if chunks:
                            # 生成元数据
                            metadata_list = [
                                {
                                    "doc_id": task.doc_id,
                                    "chunk_index": i,
                                    "user_token": task.user_token,
                                    "collection_id": collection_id,
                                    "filename": task.filename,
                                    "text_length": len(chunk),
                                    "created_at": datetime.now().isoformat(),
                                }
                                for i, chunk in enumerate(chunks)
                            ]

                            # 添加到向量库（异步操作）
                            chunk_ids = await vdb_manager.add_chunks(
                                collection_id=collection_id,
                                document_chunks=chunks,
                                doc_id=task.doc_id,
                                metadata_list=metadata_list,
                            )

                            logging.info(
                                f"Added {len(chunk_ids)} chunks to vector store for doc: {task.doc_id}"
                            )

                    except Exception as e:
                        # 向量存储失败不应影响文档处理的完成
                        logging.error(
                            f"Failed to add document to vector store: {str(e)}"
                        )

                # 更新任务状态为完成
                self.queue.update_task_status(task.doc_id, TaskStatus.COMPLETED)

                # 更新数据库状态为完成
                await asyncio.to_thread(
                    self.kb_database.update_upload_record,
                    task.doc_id,
                    status="completed",
                    process_end_time=datetime.now(),
                )

                logging.info(f"Successfully processed document: {task.doc_id}")

            except Exception as e:
                error_msg = str(e)
                logging.error(f"Failed to process document {task.doc_id}: {error_msg}")

                # 更新任务状态为失败
                self.queue.update_task_status(
                    task.doc_id, TaskStatus.FAILED, err_msg=error_msg
                )

                # 更新数据库状态为失败
                await asyncio.to_thread(
                    self._update_failed_record, task.doc_id, error_msg
                )

    def _save_converted_text(self, file_path: Path, text: str):
        """保存转换后的文本到文件"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)

    def _update_failed_record(self, doc_id: str, error_msg: str):
        """更新失败的记录"""
        self.kb_database.update_upload_record(
            doc_id,
            status="failed",
            process_end_time=datetime.now(),
            err_msg=error_msg,
        )

    def submit_task(
            self,
            user_token: str,
            file: UploadFile,
            doc_id: Optional[str] = None,
            collection_id: Optional[str] = None,
    ) -> str:
        """
        提交文档处理任务

        Args:
            user_token: 用户令牌
            file: 上传的文件
            doc_id: 文档ID，如果不提供则自动生成
            collection_id: 可选的集合ID，用于将文档分组到指定的知识库集合中

        Returns:
            文档ID
        """
        # 生成或使用提供的文档ID
        doc_id = doc_id or str(uuid.uuid4())

        # 确保用户存在
        self.kb_database.create_user_if_not_exists(user_token)

        # 保存上传的文件
        self.file_manager.save_uploaded_file(file, user_token, doc_id)

        # 创建上传记录
        upload_record = KBUploadRecord(
            doc_id=doc_id,
            user_token=user_token,
            collection_id=collection_id,
            filename=file.filename,
            status="pending",
            upload_time=datetime.now(),
            mime_type=file.content_type,
        )
        self.kb_database.add_upload_record(upload_record)

        # 创建任务并添加到队列
        task = DocumentTask(
            doc_id=doc_id,
            user_token=user_token,
            filename=file.filename,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
        )
        self.queue.add_task(task)

        logging.info(
            f"Submitted task for document: {doc_id}, collection: {collection_id}"
        )
        return doc_id

    def get_task_status(self, doc_id: str) -> Optional[DocumentTask]:
        """获取任务状态"""
        rsp: KBUploadRecord = self.kb_database.get_upload_record(doc_id)
        if not rsp:
            raise ValueError(f"Document with ID {doc_id} not found")
        return DocumentTask(
            doc_id=rsp.doc_id,
            user_token=rsp.user_token,
            filename=rsp.filename,
            status=TaskStatus(rsp.status),
            created_at=rsp.upload_time,
            started_at=rsp.process_start_time,
            completed_at=rsp.process_end_time,
            err_msg=rsp.err_msg,
        )

    def get_queue_status(self) -> QueueStatus:
        """获取队列状态"""
        return self.queue.get_queue_status()

    def get_user_tasks(self, user_token: str) -> List[DocumentTask]:
        """获取用户的所有任务"""
        all_tasks = self.queue.get_all_tasks()
        return [task for task in all_tasks if task.user_token == user_token]

    def get_all_tasks(self) -> List[DocumentTask]:
        """获取所有任务"""
        return self.queue.get_all_tasks()

    def get_vdb_manager(self, user_token: str) -> UserKBVDBManager:
        """获取用户的VDB管理器（公共接口）"""
        return self._get_vdb_manager(user_token)

    async def search_documents(
            self, user_token: str, collection_id: str, query_text: str, top_k: int = 5
    ) -> Dict[str, Any]:
        """
        在指定集合中搜索文档

        Args:
            user_token: 用户令牌
            collection_id: 集合ID
            query_text: 查询文本
            top_k: 返回结果数量

        Returns:
            搜索结果
        """
        if not self.enable_vector_store:
            raise Exception("Vector store is not enabled")

        vdb_manager = self._get_vdb_manager(user_token)
        return await vdb_manager.search_by_text(collection_id, query_text, top_k)

    def delete_document_from_vector_store(
            self, user_token: str, collection_id: str, doc_id: str
    ) -> int:
        """
        从向量库中删除文档

        Args:
            user_token: 用户令牌
            collection_id: 集合ID
            doc_id: 文档ID

        Returns:
            删除的块数量
        """
        if not self.enable_vector_store:
            raise Exception("Vector store is not enabled")

        vdb_manager = self._get_vdb_manager(user_token)
        return vdb_manager.delete_document(collection_id, doc_id)

    def list_vector_store_documents(
            self, user_token: str, collection_id: str, limit: int = None
    ) -> Dict[str, Any]:
        """
        列出向量库中的文档

        Args:
            user_token: 用户令牌
            collection_id: 集合ID
            limit: 限制返回数量

        Returns:
            文档列表
        """
        if not self.enable_vector_store:
            raise Exception("Vector store is not enabled")

        vdb_manager = self._get_vdb_manager(user_token)
        return vdb_manager.list_all_documents(collection_id, limit)

    def get_vector_store_document_count(
            self, user_token: str, collection_id: str
    ) -> int:
        """
        获取向量库中文档数量

        Args:
            user_token: 用户令牌
            collection_id: 集合ID

        Returns:
            文档数量
        """
        if not self.enable_vector_store:
            return 0

        vdb_manager = self._get_vdb_manager(user_token)
        return vdb_manager.get_document_count(collection_id)

    def _get_vdb_manager(self, user_token: str) -> UserKBVDBManager:
        """获取或创建用户的VDB管理器实例"""
        if user_token not in self._vdb_managers:
            self._vdb_managers[user_token] = UserKBVDBManager(user_token)
        return self._vdb_managers[user_token]

    def _split_text_into_chunks(
            self, text: str, chunk_size: int = 1000, overlap: int = 100
    ) -> List[str]:
        """
        将文本分割成块

        Args:
            text: 要分割的文本
            chunk_size: 每块的大小
            overlap: 块之间的重叠大小

        Returns:
            文本块列表
        """
        if not text:
            return []

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk = text[start:end]
            chunks.append(chunk)

            if end >= text_len:
                break

            start = end - overlap

        return chunks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_workers()
