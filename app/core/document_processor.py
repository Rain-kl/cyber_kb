# app/core/document_processor.py
import hashlib
from loguru import logger as logging
import os
from typing import Dict, Any, TypedDict

import requests


class DocumentParsedModel(TypedDict):
    filename: str
    content: str
    metadata: Dict[str, Any]


class DocumentProcessor:
    def __init__(self, tika_server_url: str = "http://your-server-ip:9998", upload_dir="./data/uploads"):
        """
        初始化文档处理器

        Args:
            tika_server_url: Tika 服务器的 URL，默认为 http://your-server-ip:9998
        """
        self.upload_dir = upload_dir
        self.tika_server_url = tika_server_url
        logging.info(f"DocumentProcessor initialized with Tika server at {tika_server_url}")

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 3000, overlap: int = 500) -> list[str]:
        """
        Splits a text into overlapping chunks, ensuring each chunk ends with a sentence-ending punctuation mark.

        Args:
            text (str): The input text to be chunked.
            chunk_size (int): The maximum desired size (in characters) for each chunk. Defaults to 5000.
            overlap (int): The desired number of overlapping characters between consecutive chunks. Defaults to 1000.

        Returns:
            list[str]: A list of text chunks.

        Raises:
            ValueError: If chunk_size is less than or equal to overlap, as this prevents meaningful progress.
        """
        actual_end_index = 0
        sentence_enders = {'.', '?', '!', '。', '？', '！', '\n'}
        if not text:
            return []

        if chunk_size <= overlap:
            raise ValueError(f"chunk_size ({chunk_size}) must be greater than overlap ({overlap})")

        chunks = []
        start_index = 0
        text_length = len(text)

        while start_index < text_length:
            ideal_end_index = min(start_index + chunk_size, text_length)
            if ideal_end_index == text_length:
                actual_end_index = text_length
            else:
                found_ender = False
                for i in range(ideal_end_index - 1, start_index - 1, -1):

                    if text[i] in sentence_enders:

                        if i >= start_index:  # Ensure the ender is within the current theoretical chunk slice
                            actual_end_index = i + 1  # Include the punctuation mark
                            found_ender = True
                            break
                        else:
                            continue
                if not found_ender:
                    actual_end_index = ideal_end_index

            chunk = text[start_index:actual_end_index]
            if chunk:  # Avoid adding empty chunks
                chunks.append(chunk)

            if actual_end_index >= text_length:
                break

            next_start_index = actual_end_index - overlap

            if next_start_index <= start_index:
                print(
                    f"Warning: Potential stall detected. Chunk end: {actual_end_index}, Overlap: {overlap}, Current start: {start_index}. Calculated next start: {next_start_index}. Forcing minimal advancement.")
                start_index += 1
            else:
                start_index = next_start_index

            # Safety clamp (though the loop condition `start_index < text_length` should suffice)
            start_index = min(start_index, text_length)

        return chunks

    def extract_text(self, file_path: str) -> str:
        """
        从文件中提取文本

        Args:
            file_path: 文件路径

        Returns:
            提取的文本内容
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # 获取文件名和扩展名
        # filename = os.path.basename(file_path)

        # 准备发送到 Tika 服务器的请求
        headers = {
            'Accept': 'text/plain'  # 请求纯文本输出
        }

        with open(file_path, 'rb') as file:
            # 发送文件到 Tika 服务器进行解析
            response = requests.put(
                f"{self.tika_server_url}/tika",
                headers=headers,
                data=file
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response.text

    def process_document(self, file_path: str) -> DocumentParsedModel:
        """
        处理文档并返回元数据和内容

        Args:
            file_path: 文件路径

        Returns:
            包含文档元数据和内容的字典
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)

        # 提取文本内容
        content = self.extract_text(file_path)

        # 获取元数据
        metadata = self.extract_metadata(file_path)

        return {
            "filename": filename,
            "content": content,
            "metadata": metadata
        }

    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        从文件中提取元数据

        Args:
            file_path: 文件路径

        Returns:
            文件的元数据
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # 准备发送到 Tika 服务器的请求
        headers = {
            'Accept': 'application/json'  # 请求 JSON 格式的元数据
        }

        with open(file_path, 'rb') as file:
            # 发送文件到 Tika 服务器进行元数据提取
            response = requests.put(
                f"{self.tika_server_url}/meta",
                headers=headers,
                data=file
            )
            response.raise_for_status()
            return response.json()

    def extract_text_streaming(self, file_path: str) -> str:
        """
        使用流式处理从大文件中提取文本

        Args:
            file_path: 文件路径

        Returns:
            提取的文本内容
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        headers = {
            'Accept': 'text/plain'
        }

        try:
            with open(file_path, 'rb') as file:
                # 使用流式请求
                with requests.put(
                        f"{self.tika_server_url}/tika",
                        headers=headers,
                        data=file,
                        stream=True
                ) as response:
                    response.raise_for_status()
                    return response.text

        except Exception as e:
            logging.error(f"Error extracting text from {file_path}: {str(e)}")
            return f"Error processing document: {str(e)}"

    def save_file(self, file):

        content = file.file.read()
        file.file.seek(0)

        # 计算 MD5 哈希值
        md5_hash = hashlib.md5(content).hexdigest()

        filename = f"{md5_hash}_{file.filename}"

        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)

        file_path = os.path.join(self.upload_dir, filename)

        # 写入文件
        with open(file_path, "wb") as f:
            f.write(content)

        return file_path, filename, md5_hash
