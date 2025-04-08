# app/core/embedding_async.py
import httpx
import asyncio
import logging
from typing import List
from app.config import OLLAMA_API_URL, OLLAMA_MODEL_NAME


class AsyncOllamaEmbeddingModel:
    """异步版本的 Ollama 嵌入模型"""

    def __init__(self,
                 ollama_api_url: str = OLLAMA_API_URL,
                 model_name: str = OLLAMA_MODEL_NAME):
        """
        初始化异步 Ollama 嵌入模型

        Args:
            ollama_api_url: Ollama API 服务器的 URL
            model_name: 要使用的模型名称
        """
        self.api_url = f"{ollama_api_url.rstrip('/')}/api/embeddings"
        self.model_name = model_name
        logging.info(f"AsyncOllamaEmbeddingModel initialized with API URL: {self.api_url}, model: {model_name}")

    async def get_embedding(self, text: str) -> List[float]:
        """
        异步获取单个文本的嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        if not text or not isinstance(text, str):
            return [0.0] * 1024

        payload = {
            "model": self.model_name,
            "prompt": text
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                return result.get("embedding", [])
        except Exception as e:
            logging.error(f"Error getting embedding for text: {str(e)}")
            return [0.0] * 1024

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        异步获取多个文本的嵌入向量

        Args:
            texts: 输入文本列表

        Returns:
            嵌入向量列表
        """
        if not texts:
            return []

        # 并发获取所有嵌入
        tasks = [self.get_embedding(text) for text in texts]
        return await asyncio.gather(*tasks)
