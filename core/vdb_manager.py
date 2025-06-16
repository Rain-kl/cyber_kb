import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any

from config import OLLAMA_API_URL, OLLAMA_MODEL_NAME
from utils.embedding import EmbeddingModel, AsyncOllamaEmbeddingModel
from utils.user_file_manager import default_file_manager
from utils.vector_store import VectorStore
from .ext import default_kb_db, default_user_db


class UserVectorStore(VectorStore):
    """用户专属向量存储类"""

    def __init__(self, collection_id: str, user_token: str):
        """
        初始化用户向量存储

        Args:
            collection_id: 集合ID
            user_token: 用户ID
        """
        # 构建用户专属的向量数据库路径: data/user/{user_id}/chroma_kb
        user_vdb_dir = (
                default_file_manager.get_user_directories(user_token).root / "chroma_kb"
        )
        super().__init__(collection=collection_id, persist_directory=str(user_vdb_dir))


class VDBManager(ABC):
    """向量数据库管理器抽象基类"""

    @abstractmethod
    def add_chunks(
            self,
            collection_id: str,
            document_chunks: list[str],
            doc_id: str,
            metadata_list: list[dict] = None,
    ):
        """添加文档分块到向量数据库"""
        pass

    @abstractmethod
    def search_by_embedding(
            self, collection_id: str, embedding: list[float], top_k: int = 5
    ):
        """基于嵌入向量搜索相关文档"""
        pass

    @abstractmethod
    def search_by_keyword(self, collection_id: str, keyword: str, top_k: int = 5):
        """基于关键字搜索文档"""
        pass

    @abstractmethod
    def list_all_documents(self, collection_id: str, limit: int = None):
        """
        列出集合中的所有文档

        参数:
            collection_id: 集合ID
            limit (int, 可选): 要返回的最大文档数量。如果为None，则返回所有文档。

        返回:
            dict: 包含ids、documents、embeddings和metadatas的字典
        """
        pass

    @abstractmethod
    def delete_document(self, collection_id: str, doc_id: str):
        """删除指定文档"""
        pass

    @abstractmethod
    def get_document_count(self, collection_id: str):
        """获取集合中文档数量"""
        pass

    @abstractmethod
    def check_document_exists(self, collection_id: str, doc_id: str):
        """检查文档是否存在"""
        pass


class UserKBVDBManager(VDBManager):
    """用户知识库向量数据库管理器实现"""

    def __init__(
            self,
            user_token: str,
            embedding_model: EmbeddingModel = AsyncOllamaEmbeddingModel(
                ollama_api_url=OLLAMA_API_URL, model_name=OLLAMA_MODEL_NAME
            ),
            user_db=default_user_db,
            file_manager=default_file_manager,
    ):
        """
        初始化用户知识库向量数据库管理器

        Args:
            user_token: 用户ID
            embedding_model: 嵌入模型，如果为None则使用默认模型
        """
        self.user_token = user_token
        self.base_data_dir = file_manager.get_user_directories(user_token).root
        self.embedding_model = embedding_model
        # 初始化用户数据库和文件管理器
        self.user_db = user_db
        self.file_manager = file_manager
        # 用于缓存向量存储实例
        self._vector_stores: Dict[str, UserVectorStore] = {}

    def _get_vector_store(self, collection_id: str) -> UserVectorStore:
        """获取或创建指定集合的向量存储实例"""
        if collection_id not in self._vector_stores:
            self._vector_stores[collection_id] = UserVectorStore(
                collection_id=collection_id,
                user_token=self.user_token,
            )
        return self._vector_stores[collection_id]

    async def add_chunks(
            self,
            collection_id: str,
            document_chunks: List[str],
            doc_id: str,
            metadata_list: List[dict] = None,
    ) -> List[str]:
        """
        添加文档分块到向量数据库

        Args:
            collection_id: 集合ID
            document_chunks: 文档分块列表
            doc_id: 文档ID
            metadata_list: 元数据列表，如果为None则自动生成

        Returns:
            添加的文档块ID列表
        """
        if not document_chunks:
            return []

        # 获取向量存储实例
        vector_store = self._get_vector_store(collection_id)

        # 生成嵌入向量
        embeddings = await self.embedding_model.get_embeddings_batch(document_chunks)

        # 生成元数据
        if metadata_list is None:
            metadata_list = [
                {
                    "doc_id": doc_id,
                    "chunk_index": i,
                    "user_token": self.user_token,
                    "collection_id": collection_id,
                    "text_length": len(chunk),
                }
                for i, chunk in enumerate(document_chunks)
            ]

        # 添加到向量数据库
        chunk_ids = vector_store.add_documents(
            document_chunks=document_chunks,
            embeddings=embeddings,
            metadata_list=metadata_list,
            doc_id=doc_id,
        )

        return chunk_ids

    def add_chunks_sync(
            self,
            collection_id: str,
            document_chunks: List[str],
            doc_id: str,
            metadata_list: List[dict] = None,
    ) -> List[str]:
        """同步版本的添加文档分块方法"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            self.add_chunks(collection_id, document_chunks, doc_id, metadata_list)
        )

    async def search_by_embedding(
            self, collection_id: str, embedding: List[float], top_k: int = 5
    ) -> Dict[str, Any]:
        """基于嵌入向量搜索相关文档"""
        vector_store = self._get_vector_store(collection_id)
        return vector_store.search_by_embedding(embedding, top_k)

    async def search_by_keyword(
            self, collection_id: str, keyword: str, top_k: int = 5
    ) -> Dict[str, Any]:
        """基于关键字搜索文档"""
        vector_store = self._get_vector_store(collection_id)
        return vector_store.search_by_keyword(keyword, top_k)

    async def search_by_text(
            self, collection_id: str, query_text: str, top_k: int = 5
    ) -> Dict[str, Any]:
        """
        基于文本查询搜索相关文档

        Args:
            collection_id: 集合ID
            query_text: 查询文本
            top_k: 返回结果数量

        Returns:
            搜索结果
        """
        # 生成查询文本的嵌入向量
        query_embedding = await self.embedding_model.get_embedding(query_text)
        return await self.search_by_embedding(collection_id, query_embedding, top_k)

    def search_by_text_sync(
            self, collection_id: str, query_text: str, top_k: int = 5
    ) -> Dict[str, Any]:
        """同步版本的基于文本搜索方法"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            self.search_by_text(collection_id, query_text, top_k)
        )

    def list_all_documents(
            self, collection_id: str, limit: int = None
    ) -> Dict[str, Any]:
        """列出集合中的所有文档"""
        vector_store = self._get_vector_store(collection_id)
        return vector_store.list_all_documents(limit)

    def delete_document(self, collection_id: str, doc_id: str) -> int:
        """删除指定文档"""
        vector_store = self._get_vector_store(collection_id)
        return vector_store.delete_document(doc_id)

    def get_document_count(self, collection_id: str) -> int:
        """获取集合中文档数量"""
        vector_store = self._get_vector_store(collection_id)
        return vector_store.get_document_count()

    def check_document_exists(self, collection_id: str, doc_id: str) -> bool:
        """检查文档是否存在"""
        vector_store = self._get_vector_store(collection_id)
        return vector_store.check_document_exists(doc_id)

    def list_collections(self) -> List[str]:
        """列出用户的所有集合"""
        collections_info = default_kb_db.list_collections(self.user_token)
        return [collection["collection_id"] for collection in collections_info]

    def get_user_vdb_path(self) -> str:
        """获取用户向量数据库路径"""
        return str(Path(self.base_data_dir) / "chroma_kb")
