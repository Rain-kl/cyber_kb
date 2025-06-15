#!/usr/from abc import ABC, abstractmethod
# -*- coding: utf-8 -*-
"""
用户文件管理器
基于用户 token 的文件存储管理
"""
import shutil
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, List, Dict, IO

from fastapi import UploadFile
from pydantic import BaseModel


class FilePath(BaseModel):
    root: Path
    original: Path
    processed: Path


class UserFileStructure(BaseModel):
    """文件结构定义"""

    user_token: str
    doc_id: str
    file_path: FilePath
    user_size: int = 0

    def __str__(self):
        return f"{self.user_token}/{self.doc_id}/"

    def __repr__(self):
        return self.__str__()


class UserFileManager(ABC):
    """用户文件管理器抽象基类"""

    @abstractmethod
    def get_user_directories(self, user_token: str) -> FilePath:
        """获取用户的原始文件和处理后文件目录"""
        pass

    @staticmethod
    def get_doc_dirs(self, user_token: str) -> Tuple[Path, Path]:
        """获取文档的原始和处理目录"""

        pass

    @abstractmethod
    def save_uploaded_file(
        self, file: UploadFile, user_token: str, doc_id: str
    ) -> FilePath:
        """保存用户上传的文件"""
        pass

    @abstractmethod
    def save_processed_content(
        self,
        user_token: str,
        doc_id: str,
        content: str,
        mime_type: str = "text/plain",
    ) -> bool:
        """保存处理后的文档内容, 当前仅支持文本内容"""
        pass

    @abstractmethod
    def get_origin_file_content(self, user_token: str, doc_id: str) -> Optional[str]:
        """读取文件内容"""
        pass

    @abstractmethod
    def get_processed_file_content(self, user_token: str, doc_id: str) -> Optional[str]:
        """读取文件内容"""
        pass

    @abstractmethod
    def get_user_storage_info(self, user_token: str) -> UserFileStructure:
        """获取用户存储信息"""
        pass

    @abstractmethod
    def list_user_docs(self, user_token: str) -> List[Dict]:
        pass

    @abstractmethod
    def delete_user_doc(self, user_token: str, doc_id: str) -> bool:
        """删除用户文件"""
        pass

    @abstractmethod
    def delete_user(self, user_token: str) -> bool:
        """删除用户及其所有文件"""
        pass


class LocalUserFileManager(UserFileManager):
    """基于本地文件系统的用户文件管理器实现"""

    def __init__(self, base_data_dir: str = "data"):
        """初始化文件管理器

        Args:
            base_data_dir: 基础数据目录，默认为 "data"
        """
        self.base_data_dir = Path(base_data_dir)
        self.base_data_dir.mkdir(parents=True, exist_ok=True)

        # 用户目录根路径：data/user/
        self.user_root_dir = self.base_data_dir / "user"
        self.user_root_dir.mkdir(parents=True, exist_ok=True)

    def _get_user_base_dir(self, user_token: str) -> Path:
        """获取用户基础目录：data/user/{user_token}"""
        user_dir = self.user_root_dir / user_token
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def get_doc_dirs(self, user_token: str) -> Tuple[Path, Path]:
        """获取文档的原始和处理目录

        Returns:
            Tuple[original_dir, processed_dir]
        """
        user_base = self._get_user_base_dir(user_token)

        # 原始文件目录：data/user/{user_token}/uploads/{doc_id}/origin/
        original_dir = user_base / "uploads" / "origin"
        original_dir.mkdir(parents=True, exist_ok=True)

        # 处理后文件目录：data/user/{user_token}/uploads/{doc_id}/processed/
        processed_dir = user_base / "uploads" / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)

        return original_dir, processed_dir

    def _get_original_filename(self, user_token: str, doc_id: str) -> Path:
        """获取原始文件的完整路径"""
        original_dir, _ = self.get_doc_dirs(user_token)

        # 查找以doc_id开头的文件（包含原始文件扩展名）
        for file_path in original_dir.iterdir():
            if file_path.is_file() and file_path.stem == doc_id:
                return file_path

        # 如果没有找到匹配的文件，返回不带扩展名的路径（向后兼容）
        raise FileNotFoundError("<UNK>")

    def get_user_directories(self, user_token: str) -> FilePath:
        """获取用户的原始文件和处理后文件目录"""
        user_base = self._get_user_base_dir(user_token)

        # 用户上传根目录
        uploads_dir = user_base / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        return FilePath(root=user_base, original=uploads_dir, processed=uploads_dir)

    def save_uploaded_file(
        self, file: UploadFile, user_token: str, doc_id: str
    ) -> FilePath:
        """保存用户上传的文件"""

        # 获取目录
        original_dir, processed_dir = self.get_doc_dirs(user_token)

        # 保存原始文件
        file_extension = Path(file.filename).suffix
        original_file_path = original_dir / f"{doc_id}{file_extension}"

        try:
            with open(original_file_path, "wb") as buffer:
                content = file.file.read()
                buffer.write(content)

            return FilePath(
                root=self._get_user_base_dir(user_token),
                original=original_file_path,
                processed=processed_dir,
            )

        except Exception as e:
            # 如果保存失败，清理已创建的文件
            if original_file_path.exists():
                original_file_path.unlink()
            raise e

    def save_processed_content(
        self,
        user_token: str,
        doc_id: str,
        content: str,
        mime_type: str = "text/plain",
    ) -> bool:
        """保存处理后的文档内容"""
        # 获取处理目录
        _, processed_dir = self.get_doc_dirs(user_token)

        # 保存处理后的内容
        processed_file_path = processed_dir / f"{doc_id}.txt"

        with open(processed_file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return True

    def get_processed_file_content(self, user_token, doc_id: str) -> Optional[str]:
        """读取文件内容"""
        # 从数据库获取记录信息
        try:
            # 尝试读取处理后的文件
            _, processed_dir = self.get_doc_dirs(user_token)
            processed_file_path = processed_dir / f"{doc_id}.txt"

            if processed_file_path.exists():
                with open(processed_file_path, "r", encoding="utf-8") as f:
                    return f.read()
            return None
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def get_origin_file_content(self, user_token: str, doc_id: str) -> IO[bytes] | None:
        # 如果处理后的文件不存在，尝试读取原始文件
        original_file_path = self._get_original_filename(user_token, doc_id)

        if original_file_path.exists():
            # 根据文件类型尝试读取
            with open(original_file_path, "rb") as f:
                return f
        return None

    def get_user_storage_info(self, user_token: str) -> UserFileStructure:
        """获取用户存储信息"""
        user_base = self._get_user_base_dir(user_token)

        # 计算用户目录总大小
        total_size = 0
        if user_base.exists():
            for file_path in user_base.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        doc_count = len(list(user_base.glob("uploads/origin/*")))
        return UserFileStructure(
            user_token=user_token,
            doc_id=f"total_docs_{doc_count}",
            file_path=self.get_user_directories(user_token),
            user_size=total_size,
        )

    def delete_user_doc(self, user_token: str, doc_id: str) -> bool:
        """删除用户文档"""
        try:
            # 删除文件目录
            user_base = self._get_user_base_dir(user_token)

            original_file_path = self._get_original_filename(user_token, doc_id)
            _, processed_dir = self.get_doc_dirs(user_token)
            processed_file_path = processed_dir / f"{doc_id}_processed.txt"
            if original_file_path.exists():
                original_file_path.unlink()
            if processed_file_path.exists():
                processed_file_path.unlink()
            return True

        except Exception:
            return False

    def delete_user(self, user_token: str) -> bool:
        """删除用户及其所有文件"""
        try:
            # 删除用户目录
            user_dir = self._get_user_base_dir(user_token)
            if user_dir.exists():
                shutil.rmtree(user_dir)
            return True

        except Exception:
            return False

    def list_user_docs(self, user_token: str) -> List[Dict]:
        """列出用户的所有文档"""
        docs = []
        user_base = self._get_user_base_dir(user_token)
        original_dir, processed_dir = self.get_doc_dirs(user_token)
        # 获取原始文件目录下的所有文件
        for file_path in original_dir.iterdir():
            if file_path.is_file():
                doc_info = {
                    "doc_id": file_path.stem,
                    "file_name": file_path.name,
                    "file_size": file_path.stat().st_size,
                    "created_at": datetime.fromtimestamp(file_path.stat().st_ctime),
                    "processed": (processed_dir / f"{file_path.stem}.txt").exists(),
                }
                docs.append(doc_info)
        return docs


# 默认文件管理器实例
default_file_manager = LocalUserFileManager()
