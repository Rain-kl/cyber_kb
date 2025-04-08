# app/core/embedding.py
import requests
import json
import logging
import time
import numpy as np
from typing import List, Dict, Any, Optional, Union
from requests.exceptions import RequestException
from app.config import OLLAMA_API_URL, OLLAMA_MODEL_NAME


class OllamaEmbeddingModel:
    """通过 Ollama API 调用 BGE-M3 嵌入模型"""

    def __init__(self,
                 ollama_api_url: str = "http://your-ollama-server:11434",
                 model_name: str = "bge-m3"):
        """
        初始化 Ollama 嵌入模型

        Args:
            ollama_api_url: Ollama API 服务器的 URL
            model_name: 要使用的模型名称
        """
        self.api_url = f"{ollama_api_url.rstrip('/')}/api/embeddings"
        self.model_name = model_name
        self.embedding_dim = 1024
        logging.info(f"OllamaEmbeddingModel initialized with API URL: {self.api_url}, model: {model_name}")

        # 验证连接
        self._check_connection()

    def _check_connection(self) -> bool:
        """检查与 Ollama API 的连接"""
        try:
            # 尝试获取一个简单文本的嵌入，验证连接
            self.get_embedding("connection test")
            logging.info(f"Successfully connected to Ollama API at {self.api_url}")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to Ollama API: {str(e)}")
            logging.warning("OllamaEmbeddingModel initialized but connection test failed")
            return False

    def _retry_request(self, func, *args, **kwargs):
        """带重试机制的请求函数"""
        max_retries = 3
        retry_delay = 1  # 初始延迟 1 秒

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except RequestException as e:
                if attempt < max_retries - 1:
                    logging.warning(f"API request failed: {str(e)}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    logging.error(f"API request failed after {max_retries} attempts: {str(e)}")
                    raise

    def get_embedding(self, text: str) -> List[float]:
        """
        获取单个文本的嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        if not text or not isinstance(text, str):
            logging.warning("Empty or invalid text provided for embedding")
            # 返回零向量作为默认值，维度为 1024（BGE-M3 的嵌入维度）
            return [0.0] * self.embedding_dim

        payload = {
            "model": self.model_name,
            "prompt": text
        }

        def make_request():
            response = requests.post(
                self.api_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=30  # 30秒超时
            )
            response.raise_for_status()
            return response.json()

        try:
            result = self._retry_request(make_request)
            return result.get("embedding", [])
        except Exception as e:
            logging.error(f"Error getting embedding for text: {str(e)}")
            # 返回零向量作为错误时的默认值
            return [0.0] * 1024

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        获取多个文本的嵌入向量

        Args:
            texts: 输入文本列表

        Returns:
            嵌入向量列表
        """
        if not texts:
            return []

        # 批量处理每个文本
        embeddings = []
        for text in texts:
            embedding = self.get_embedding(text)
            embeddings.append(embedding)

        return embeddings

    def get_embeddings_batch(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """
        批量获取嵌入向量，控制并发请求数量

        Args:
            texts: 输入文本列表
            batch_size: 每批处理的文本数量

        Returns:
            嵌入向量列表
        """
        if not texts:
            return []

        all_embeddings = []

        # 按批次处理
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.get_embeddings(batch)
            all_embeddings.extend(batch_embeddings)

            # 添加小延迟，避免请求过于频繁
            if i + batch_size < len(texts):
                time.sleep(0.5)

        return all_embeddings

    def similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本之间的余弦相似度

        Args:
            text1: 第一个文本
            text2: 第二个文本

        Returns:
            余弦相似度，范围为 [-1, 1]
        """
        embedding1 = self.get_embedding(text1)
        embedding2 = self.get_embedding(text2)

        # 计算余弦相似度
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = sum(a * a for a in embedding1) ** 0.5
        norm2 = sum(b * b for b in embedding2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


class EmbeddingModel:
    """嵌入模型包装类，使用 Ollama API 调用 BGE-M3"""

    def __init__(self, model_name: str = None):
        """
        初始化嵌入模型

        Args:
            model_name: 模型名称，如果提供则覆盖配置中的默认值
        """
        model = model_name or OLLAMA_MODEL_NAME
        self.model = OllamaEmbeddingModel(
            ollama_api_url=OLLAMA_API_URL,
            model_name=model
        )
        logging.info(f"EmbeddingModel initialized with Ollama model: {model}")

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        获取多个文本的嵌入向量

        Args:
            texts: 输入文本列表

        Returns:
            嵌入向量列表
        """
        return self.model.get_embeddings_batch(texts)

    def get_embedding(self, text: str) -> List[float]:
        """
        获取单个文本的嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        return self.model.get_embedding(text)
