# app/core/embedding.py
import asyncio
from asyncio import Semaphore, TaskGroup
from typing import List

import httpx
import requests
from loguru import logger
from tqdm import tqdm  # 导入 tqdm 用于进度条


class AsyncOllamaEmbeddingModel:
    """通过 Ollama API 调用 BGE-M3 嵌入模型"""

    def __init__(
            self,
            ollama_api_url: str = "http://your-ollama-server:11434",
            model_name: str = "bge-m3",
    ):
        """
        初始化 Ollama 嵌入模型

        Args:
            ollama_api_url: Ollama API 服务器的 URL
            model_name: 要使用的模型名称
        """
        self.ollama_api_base = ollama_api_url
        self.api_url = f"{ollama_api_url.rstrip('/')}/api/embeddings"
        self.model_name = model_name
        self.embedding_dim = 1024
        # logger.info(f"OllamaEmbeddingModel initialized with API URL: {self.api_url}, model: {model_name}")
        self.check_connection()

    def check_connection(self) -> bool:
        """异步检查与 Ollama API 的连接"""
        try:
            # 尝试获取一个简单文本的嵌入，验证连接
            requests.get(self.ollama_api_base).raise_for_status()
            logger.info(f"Successfully connected to Ollama API at {self.api_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Ollama API: {str(e)}")
            logger.warning(
                "OllamaEmbeddingModel initialized but connection test failed"
            )
            raise e

    @staticmethod
    async def _retry_request(func, *args, **kwargs):
        """带重试机制的异步请求函数"""
        max_retries = 3
        retry_delay = 1  # 初始延迟 1 秒

        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"API request failed: {str(e)}. Retrying in {retry_delay} seconds..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    logger.error(
                        f"API request failed after {max_retries} attempts: {str(e)}"
                    )
                    raise
        raise

    async def get_embedding(self, text: str) -> List[float]:
        """
        异步获取单个文本的嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        if not text or not isinstance(text, str):
            logger.warning("Empty or invalid text provided for embedding")
            # 返回零向量作为默认值，维度为 1024（BGE-M3 的嵌入维度）
            return [0.0] * self.embedding_dim

        payload = {"model": self.model_name, "prompt": text}

        async def make_request():
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=30.0,  # 30秒超时
                )
                response.raise_for_status()
                return response.json()

        try:
            result = await self._retry_request(make_request)
            return result.get("embedding", [])
        except Exception as e:
            logger.error(f"Error getting embedding for text: {str(e)}")
            # 返回零向量作为错误时的默认值
            return [0.0] * self.embedding_dim

    async def get_embeddings_batch(
            self, texts: List[str], batch_size: int = 10, concurrency_limit: int = 5
    ) -> List[List[float]]:
        """
        异步批量获取嵌入向量，控制并发请求数量，并添加进度条

        Args:
            texts: 输入文本列表
            batch_size: 每批处理的文本数量
            concurrency_limit: 最大并发请求数

        Returns:
            嵌入向量列表
        """
        if not texts:
            return []

        all_embeddings = []

        # 创建一个限制并发的信号量
        semaphore = Semaphore(concurrency_limit)

        async def get_with_semaphore(text):
            async with semaphore:
                return await self.get_embedding(
                    text
                )  # 假设 self.get_embedding 是异步方法

        total_batches = (
                                len(texts) + batch_size - 1
                        ) // batch_size  # 计算总批次数（向上取整）

        with tqdm(total=total_batches, desc="Processing batches") as pbar:  # 创建进度条
            for i in range(0, len(texts), batch_size):
                batch = texts[i: i + batch_size]

                async with TaskGroup() as tg:
                    tasks = [tg.create_task(get_with_semaphore(text)) for text in batch]

                # 任务组会等待所有任务完成，现在提取结果
                batch_embeddings = [
                    task.result() for task in tasks
                ]  # tasks 列表来自 TaskGroup
                all_embeddings.extend(batch_embeddings)

                pbar.update(1)  # 更新进度条

                # 添加小延迟，避免请求过于频繁
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.5)

        return all_embeddings

    async def similarity(self, text1: str, text2: str) -> float:
        """
        异步计算两个文本之间的余弦相似度

        Args:
            text1: 第一个文本
            text2: 第二个文本

        Returns:
            余弦相似度，范围为 [-1, 1]
        """
        # 并行获取两个嵌入
        embedding1, embedding2 = await asyncio.gather(
            self.get_embedding(text1), self.get_embedding(text2)
        )

        # 计算余弦相似度
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = sum(a * a for a in embedding1) ** 0.5
        norm2 = sum(b * b for b in embedding2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    # 为了向后兼容，添加同步包装方法
    def get_embedding_sync(self, text: str) -> List[float]:
        """同步获取嵌入的包装方法"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.get_embedding(text))

    def get_embeddings_batch_sync(
            self, texts: List[str], batch_size: int = 10
    ) -> List[List[float]]:
        """同步批量获取嵌入的包装方法"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.get_embeddings_batch(texts, batch_size))

    def similarity_sync(self, text1: str, text2: str) -> float:
        """同步计算相似度的包装方法"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.similarity(text1, text2))
