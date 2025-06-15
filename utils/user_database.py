#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户数据库接口和实现
基于 SQLite 的用户管理系统
"""

import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from pydantic import BaseModel


class KBUploadRecord(BaseModel):
    """用户上传记录模型"""

    doc_id: str  # 主键，用户手动设定
    user_token: str  # 外键，指向UserInfo表
    collection_id: Optional[str] = None
    filename: str
    status: str  # pending, processing, completed, failed
    upload_time: datetime
    process_start_time: Optional[datetime] = None
    process_end_time: Optional[datetime] = None
    err_msg: Optional[str] = None
    mime_type: Optional[str] = None


class UserInfo(BaseModel):
    """用户信息模型"""

    user_token: str  # 主键
    create_time: datetime


class UserDatabase(ABC):
    """用户数据库接口"""

    @abstractmethod
    def _init_user_table(self):
        """初始化数据库表结构"""
        pass

    @abstractmethod
    def create_user_if_not_exists(self, user_token: str) -> UserInfo:
        """创建用户（如果不存在）"""
        pass

    @abstractmethod
    def get_user_info(self, user_token: str) -> Optional[UserInfo]:
        """获取用户信息"""
        pass

    @abstractmethod
    def delete_user(self, user_token: str) -> bool:
        """删除用户及其所有上传记录"""
        pass


class KnowledgeBase(UserDatabase):
    @abstractmethod
    def _init_kb_table(self):
        """初始化知识库相关表结构"""
        pass

    @abstractmethod
    def add_upload_record(self, record: KBUploadRecord) -> str:
        """添加上传记录，返回doc_id"""
        pass

    @abstractmethod
    def update_upload_record(self, doc_id: str, **kwargs) -> bool:
        """更新上传记录"""
        pass

    @abstractmethod
    def get_upload_record(self, doc_id: str) -> Optional[KBUploadRecord]:
        """根据任务ID获取上传记录"""
        pass

    @abstractmethod
    def delete_upload_record(self, doc_id: str) -> bool:
        """删除上传记录"""
        pass

    @abstractmethod
    def get_all_uploads(
        self, limit: int = 50, status: Optional[str] = None
    ) -> List[KBUploadRecord]:
        """获取所有上传记录（管理员用）"""
        pass

    @abstractmethod
    def get_user_uploads(
        self, user_token: str, limit: int = 50, status: Optional[str] = None
    ) -> List[KBUploadRecord]:
        """获取用户的上传记录"""
        pass

    @abstractmethod
    def create_collection(
        self,
        collection_id: str,
        collection_name: str,
        created_by: str,
        description: str = None,
    ) -> bool:
        """创建新的知识库集合"""
        pass

    @abstractmethod
    def get_collection_info(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """获取集合信息"""
        pass

    @abstractmethod
    def list_collections(self, user_token: str) -> List[Dict[str, Any]]:
        """列出用户所有知识库"""
        pass

    @abstractmethod
    def get_collection(
        self, user_token: str, collection_id: str
    ) -> List[KBUploadRecord]:
        """获取指定集合的内容"""
        pass

    @abstractmethod
    def query_documents(
        self, doc_id: str, collection_id: str, top_k: int = 5
    ) -> List[KBUploadRecord]:
        """查询指定集合中的文档"""
        pass


class SQLiteUserDatabase(UserDatabase):
    """基于 SQLite 的用户数据库实现"""

    def __init__(self, db_path: str = "data/user/user.db"):
        """初始化数据库连接

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_user_table()

    def _init_user_table(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 创建用户信息表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_info
                (
                    user_token  TEXT PRIMARY KEY,
                    create_time TEXT NOT NULL
                )
                """
            )

            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
        return conn

    def _row_to_user_info(self, row: tuple) -> UserInfo:
        """将数据库行转换为UserInfo对象"""
        return UserInfo(user_token=row[0], create_time=datetime.fromisoformat(row[1]))

    def create_user_if_not_exists(self, user_token: str) -> UserInfo:
        """创建用户（如果不存在）"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 首先检查用户是否存在
                cursor.execute(
                    "SELECT user_token, create_time FROM user_info WHERE user_token = ?",
                    (user_token,),
                )
                row = cursor.fetchone()

                if row:
                    return self._row_to_user_info(row)

                # 用户不存在，创建新用户
                create_time = datetime.now()
                cursor.execute(
                    "INSERT INTO user_info (user_token, create_time) VALUES (?, ?)",
                    (user_token, create_time.isoformat()),
                )
                conn.commit()

                return UserInfo(user_token=user_token, create_time=create_time)

    def get_user_info(self, user_token: str) -> Optional[UserInfo]:
        """获取用户信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_token, create_time FROM user_info WHERE user_token = ?",
                (user_token,),
            )
            row = cursor.fetchone()
            return self._row_to_user_info(row) if row else None

    def delete_user(self, user_token: str) -> bool:
        """删除用户"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM user_info WHERE user_token = ?", (user_token,)
                )
                conn.commit()
                return cursor.rowcount > 0


class SQLiteKnowledgeBaseDB(SQLiteUserDatabase, KnowledgeBase):
    """基于 SQLite 的知识库数据库实现，继承用户数据库功能"""

    # 默认集合配置
    DEFAULT_COLLECTION_NAME = "默认集合"
    DEFAULT_COLLECTION_DESCRIPTION = "用户默认知识库集合，用于存储未指定集合的文档"

    @staticmethod
    def get_user_default_collection_id(user_token: str) -> str:
        """获取用户的默认集合ID"""
        return f"default_{user_token}"

    def __init__(self, db_path: str = "data/user/user.db"):
        """初始化知识库数据库连接

        Args:
            db_path: 数据库文件路径
        """
        super().__init__(db_path)
        self._init_kb_table()

    def _init_kb_table(self):
        """初始化知识库相关表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 创建知识库集合表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS kb_collections
                (
                    collection_id   TEXT PRIMARY KEY,
                    collection_name TEXT NOT NULL,
                    description     TEXT,
                    create_time     TEXT NOT NULL,
                    created_by      TEXT NOT NULL,
                    FOREIGN KEY (created_by) REFERENCES user_info (user_token)
                )
                """
            )

            # 创建用户上传记录表（直接包含collection_id外键）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_upload_record
                (
                    doc_id             TEXT PRIMARY KEY,
                    user_token         TEXT NOT NULL,
                    collection_id      TEXT,
                    filename           TEXT NOT NULL,
                    status             TEXT NOT NULL,
                    upload_time        TEXT NOT NULL,
                    process_start_time TEXT,
                    process_end_time   TEXT,
                    err_msg            TEXT,
                    mime_type          TEXT,
                    FOREIGN KEY (user_token) REFERENCES user_info (user_token),
                    FOREIGN KEY (collection_id) REFERENCES kb_collections (collection_id)
                )
                """
            )

            # 创建索引提高查询性能
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_upload_user_token
                    ON user_upload_record (user_token)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_upload_status
                    ON user_upload_record (status)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_upload_collection
                    ON user_upload_record (collection_id)
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_kb_collections_created_by
                    ON kb_collections (created_by)
                """
            )

            conn.commit()

    def _row_to_upload_record(self, row: tuple) -> KBUploadRecord:
        """将数据库行转换为KBUploadRecord对象"""
        return KBUploadRecord(
            doc_id=row[0],
            user_token=row[1],
            collection_id=row[2],
            filename=row[3],
            status=row[4],
            upload_time=datetime.fromisoformat(row[5]),
            process_start_time=datetime.fromisoformat(row[6]) if row[6] else None,
            process_end_time=datetime.fromisoformat(row[7]) if row[7] else None,
            err_msg=row[8],
            mime_type=row[9],
        )

    def add_upload_record(self, record: KBUploadRecord) -> str:
        """添加上传记录，返回doc_id"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 检查doc_id是否已存在
                cursor.execute(
                    "SELECT doc_id FROM user_upload_record WHERE doc_id = ?",
                    (record.doc_id,),
                )
                if cursor.fetchone():
                    raise ValueError(f"Document ID '{record.doc_id}' already exists")

                # 检查user_token是否存在
                cursor.execute(
                    "SELECT user_token FROM user_info WHERE user_token = ?",
                    (record.user_token,),
                )
                if not cursor.fetchone():
                    raise ValueError(f"User token '{record.user_token}' does not exist")

                # 如果没有指定collection_id，创建并使用用户的默认集合
                if not record.collection_id:
                    self._create_user_default_collection(record.user_token)
                    record.collection_id = self.get_user_default_collection_id(
                        record.user_token
                    )

                # 检查collection_id是否存在
                cursor.execute(
                    "SELECT collection_id FROM kb_collections WHERE collection_id = ?",
                    (record.collection_id,),
                )
                if not cursor.fetchone():
                    raise ValueError(
                        f"Collection '{record.collection_id}' does not exist"
                    )

                # 插入上传记录
                cursor.execute(
                    """
                    INSERT INTO user_upload_record
                    (doc_id, user_token, collection_id, filename, status, upload_time,
                     process_start_time, process_end_time, err_msg, mime_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.doc_id,
                        record.user_token,
                        record.collection_id,
                        record.filename,
                        record.status,
                        record.upload_time.isoformat(),
                        (
                            record.process_start_time.isoformat()
                            if record.process_start_time
                            else None
                        ),
                        (
                            record.process_end_time.isoformat()
                            if record.process_end_time
                            else None
                        ),
                        record.err_msg,
                        record.mime_type,
                    ),
                )
                conn.commit()

                return record.doc_id

    def update_upload_record(self, doc_id: str, **kwargs) -> bool:
        """更新上传记录"""
        if not kwargs:
            return False

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 如果要更新collection_id，先验证其存在性
                if "collection_id" in kwargs and kwargs["collection_id"]:
                    cursor.execute(
                        "SELECT collection_id FROM kb_collections WHERE collection_id = ?",
                        (kwargs["collection_id"],),
                    )
                    if not cursor.fetchone():
                        raise ValueError(
                            f"Collection '{kwargs['collection_id']}' does not exist"
                        )

                # 构建SET子句
                set_clauses = []
                values = []

                allowed_fields = {
                    "collection_id",
                    "filename",
                    "status",
                    "upload_time",
                    "process_start_time",
                    "process_end_time",
                    "err_msg",
                    "mime_type",
                }

                for key, value in kwargs.items():
                    if key in allowed_fields:
                        set_clauses.append(f"{key} = ?")
                        if key.endswith("_time") and isinstance(value, datetime):
                            values.append(value.isoformat())
                        else:
                            values.append(value)

                if not set_clauses:
                    return False

                values.append(doc_id)

                sql = f"UPDATE user_upload_record SET {', '.join(set_clauses)} WHERE doc_id = ?"
                cursor.execute(sql, values)
                conn.commit()
                return cursor.rowcount > 0

    def get_upload_record(self, doc_id: str) -> Optional[KBUploadRecord]:
        """根据doc_id获取上传记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT doc_id,
                       user_token,
                       collection_id,
                       filename,
                       status,
                       upload_time,
                       process_start_time,
                       process_end_time,
                       err_msg,
                       mime_type
                FROM user_upload_record
                WHERE doc_id = ?
                """,
                (doc_id,),
            )
            row = cursor.fetchone()
            return self._row_to_upload_record(row) if row else None

    def get_user_uploads(
        self, user_token: str, limit: int = 50, status: Optional[str] = None
    ) -> List[KBUploadRecord]:
        """获取用户的上传记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if status:
                cursor.execute(
                    """
                    SELECT doc_id,
                           user_token,
                           collection_id,
                           filename,
                           status,
                           upload_time,
                           process_start_time,
                           process_end_time,
                           err_msg,
                           mime_type
                    FROM user_upload_record
                    WHERE user_token = ?
                      AND status = ?
                    ORDER BY upload_time DESC
                    LIMIT ?
                    """,
                    (user_token, status, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT doc_id,
                           user_token,
                           collection_id,
                           filename,
                           status,
                           upload_time,
                           process_start_time,
                           process_end_time,
                           err_msg,
                           mime_type
                    FROM user_upload_record
                    WHERE user_token = ?
                    ORDER BY upload_time DESC
                    LIMIT ?
                    """,
                    (user_token, limit),
                )

            rows = cursor.fetchall()
            return [self._row_to_upload_record(row) for row in rows]

    def get_all_uploads(
        self, limit: int = 50, status: Optional[str] = None
    ) -> List[KBUploadRecord]:
        """获取所有上传记录（管理员用）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if status:
                cursor.execute(
                    """
                    SELECT doc_id,
                           user_token,
                           collection_id,
                           filename,
                           status,
                           upload_time,
                           process_start_time,
                           process_end_time,
                           err_msg,
                           mime_type
                    FROM user_upload_record
                    WHERE status = ?
                    ORDER BY upload_time DESC
                    LIMIT ?
                    """,
                    (status, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT doc_id,
                           user_token,
                           collection_id,
                           filename,
                           status,
                           upload_time,
                           process_start_time,
                           process_end_time,
                           err_msg,
                           mime_type
                    FROM user_upload_record
                    ORDER BY upload_time DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            rows = cursor.fetchall()
            return [self._row_to_upload_record(row) for row in rows]

    def query_documents(
        self, doc_id: str, collection_id: str, top_k: int = 5
    ) -> List[KBUploadRecord]:
        """查询指定集合中的文档

        注意：这是一个基础实现，实际的语义搜索需要结合向量数据库
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT doc_id,
                       user_token,
                       collection_id,
                       filename,
                       status,
                       upload_time,
                       process_start_time,
                       process_end_time,
                       err_msg,
                       mime_type
                FROM user_upload_record
                WHERE collection_id = ?
                  AND doc_id != ?
                ORDER BY upload_time DESC
                LIMIT ?
                """,
                (collection_id, doc_id, top_k),
            )
            rows = cursor.fetchall()
            return [self._row_to_upload_record(row) for row in rows]

    def create_collection(
        self,
        collection_id: str,
        collection_name: str,
        created_by: str,
        description: str = None,
    ) -> bool:
        """创建新的知识库集合"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 检查集合ID是否已存在
                cursor.execute(
                    "SELECT collection_id FROM kb_collections WHERE collection_id = ?",
                    (collection_id,),
                )
                if cursor.fetchone():
                    raise ValueError(f"Collection ID '{collection_id}' already exists")

                # 检查创建者是否存在
                cursor.execute(
                    "SELECT user_token FROM user_info WHERE user_token = ?",
                    (created_by,),
                )
                if not cursor.fetchone():
                    raise ValueError(f"User token '{created_by}' does not exist")

                # 创建集合
                create_time = datetime.now()
                cursor.execute(
                    """
                    INSERT INTO kb_collections
                        (collection_id, collection_name, description, create_time, created_by)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        collection_id,
                        collection_name,
                        description,
                        create_time.isoformat(),
                        created_by,
                    ),
                )
                conn.commit()
                return True

    def get_collection_info(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """获取集合信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT collection_id, collection_name, description, create_time, created_by
                FROM kb_collections
                WHERE collection_id = ?
                """,
                (collection_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return {
                "collection_id": row[0],
                "collection_name": row[1],
                "description": row[2],
                "create_time": datetime.fromisoformat(row[3]),
                "created_by": row[4],
            }

    def list_collections(self, user_token: str) -> List[Dict[str, Any]]:
        """获取用户创建的所有集合"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT collection_id, collection_name, description, create_time, created_by
                FROM kb_collections
                WHERE created_by = ?
                ORDER BY create_time DESC
                """,
                (user_token,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "collection_id": row[0],
                    "collection_name": row[1],
                    "description": row[2],
                    "create_time": datetime.fromisoformat(row[3]),
                    "created_by": row[4],
                }
                for row in rows
            ]

    def delete_upload_record(self, doc_id: str) -> bool:
        """删除上传记录"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM user_upload_record WHERE doc_id = ?", (doc_id,)
                )
                conn.commit()
                return cursor.rowcount > 0

    def delete_user(self, user_token: str) -> bool:
        """删除用户及其所有相关数据"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 先删除用户的上传记录（因为它们引用集合）
                cursor.execute(
                    "DELETE FROM user_upload_record WHERE user_token = ?", (user_token,)
                )

                # 然后删除用户创建的集合
                cursor.execute(
                    "DELETE FROM kb_collections WHERE created_by = ?", (user_token,)
                )

                # 最后删除用户信息
                cursor.execute(
                    "DELETE FROM user_info WHERE user_token = ?", (user_token,)
                )

                conn.commit()
                return cursor.rowcount > 0

    def get_collection(
        self, user_token: str, collection_id: str
    ) -> List[KBUploadRecord]:
        """获取指定集合的内容"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 检查用户是否有权限访问该集合（必须是集合的创建者）
            cursor.execute(
                "SELECT created_by FROM kb_collections WHERE collection_id = ?",
                (collection_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Collection '{collection_id}' does not exist")

            # 只有集合的创建者才能访问
            if row[0] != user_token:
                raise PermissionError(
                    f"User '{user_token}' does not have permission to access collection '{collection_id}'"
                )

            # 获取集合中的所有文档
            cursor.execute(
                """
                SELECT doc_id,
                       user_token,
                       collection_id,
                       filename,
                       status,
                       upload_time,
                       process_start_time,
                       process_end_time,
                       err_msg,
                       mime_type
                FROM user_upload_record
                WHERE collection_id = ?
                ORDER BY upload_time DESC
                """,
                (collection_id,),
            )
            rows = cursor.fetchall()
            return [self._row_to_upload_record(row) for row in rows]

    def add_document_to_collection(self, doc_id: str, collection_id: str) -> bool:
        """将文档添加到集合中"""
        return self.update_upload_record(doc_id, collection_id=collection_id)

    def remove_document_from_collection(self, doc_id: str, collection_id: str) -> bool:
        """从集合中移除文档"""
        # 检查文档当前是否在指定集合中
        record = self.get_upload_record(doc_id)
        if not record or record.collection_id != collection_id:
            return False

        # 将collection_id设置为None来移除关联
        return self.update_upload_record(doc_id, collection_id=None)

    def _create_user_default_collection(self, user_token: str):
        """为用户创建默认集合"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            collection_id = self.get_user_default_collection_id(user_token)

            # 检查用户的默认集合是否存在，不存在则创建
            cursor.execute(
                "SELECT collection_id FROM kb_collections WHERE collection_id = ?",
                (collection_id,),
            )
            if not cursor.fetchone():
                create_time = datetime.now()
                cursor.execute(
                    """
                    INSERT INTO kb_collections
                        (collection_id, collection_name, description, create_time, created_by)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        collection_id,
                        self.DEFAULT_COLLECTION_NAME,
                        self.DEFAULT_COLLECTION_DESCRIPTION,
                        create_time.isoformat(),
                        user_token,
                    ),
                )
                conn.commit()
                return True
            return False

    def get_user_default_collection_info(
        self, user_token: str
    ) -> Optional[Dict[str, Any]]:
        """获取用户的默认集合信息"""
        collection_id = self.get_user_default_collection_id(user_token)
        return self.get_collection_info(collection_id)


# 默认数据库实例
default_user_db = SQLiteUserDatabase()
default_kb_db = SQLiteKnowledgeBaseDB()
