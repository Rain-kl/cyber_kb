import hashlib
from pathlib import Path
from typing import Any, Dict

import requests
from loguru import logger as logging

from .DocumentConvertor import DocumentConvertor


class TikaDocumentConvertorImpl(DocumentConvertor):
    """
    Implementation of the DocumentConvertor interface for Tika.
    This class is responsible for converting documents using Apache Tika server.
    """

    def __init__(
        self,
        file_path: str = None,
        tika_server_url: str = "http://localhost:9998",
    ):
        super().__init__(file_path)
        self.tika_server_url = tika_server_url
        logging.info(
            f"TikaDocumentConvertorImpl initialized with Tika server at {tika_server_url}"
        )

    def convert(self) -> str:
        """
        Convert the given document to text using Tika.

        :return: The converted document content as string.
        """
        if not self.file_path:
            raise ValueError("File path is required for document conversion")

        file_path = Path(self.file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        try:
            # 对于纯文本文件直接读取
            if file_path.suffix.lower() in [".txt", ".md", ".markdown"]:
                return self._read_text_file(file_path)

            # 使用 Tika 提取文本
            content = self._extract_text_with_tika(file_path)
            logging.info(f"Document {file_path.name} converted successfully with Tika")
            return content

        except Exception as e:
            error_msg = f"Error converting document {file_path.name}: {str(e)}"
            logging.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _read_text_file(self, file_path: Path) -> str:
        """
        Read plain text files directly.

        :param file_path: Path to the text file.
        :return: File content as string.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # 如果UTF-8失败，尝试其他编码
            try:
                with open(file_path, "r", encoding="gbk") as f:
                    return f.read()
            except UnicodeDecodeError:
                with open(file_path, "r", encoding="latin-1") as f:
                    return f.read()

    def _extract_text_with_tika(self, file_path: Path) -> str:
        """
        Extract text from file using Tika server.

        :param file_path: Path to the file.
        :return: Extracted text content.
        """
        headers = {"Accept": "text/plain"}

        try:
            with open(file_path, "rb") as file:
                response = requests.put(
                    f"{self.tika_server_url}/tika",
                    headers=headers,
                    data=file,
                    timeout=300,  # 5分钟超时
                )
                response.raise_for_status()
                response.encoding = response.apparent_encoding or "utf-8"
                return response.text
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 502:
                logging.warning(
                    f"Tika server unavailable for {file_path.name}, falling back to direct reading"
                )
                return self._read_text_file_fallback(file_path)
            else:
                raise
        except Exception as e:
            logging.warning(
                f"Tika extraction failed for {file_path.name}, falling back to direct reading: {e}"
            )
            return self._read_text_file_fallback(file_path)

    def _read_text_file_fallback(self, file_path: Path) -> str:
        """
        Fallback method to read text files when Tika fails.

        :param file_path: Path to the file.
        :return: File content as string.
        """
        # 对于常见的文本格式，尝试直接读取
        text_extensions = {
            ".txt",
            ".md",
            ".markdown",
            ".html",
            ".htm",
            ".xml",
            ".json",
            ".yaml",
            ".yml",
            ".csv",
            ".pdf",
        }

        if file_path.suffix.lower() in text_extensions:
            return self._read_text_file(file_path)
        else:
            # 对于其他格式，返回错误信息
            return f"Error processing document: Tika server unavailable and no fallback available for {file_path.suffix} format"

    def extract_metadata(self) -> Dict[str, Any]:
        """
        Extract metadata from the document using Tika.

        :return: Document metadata as dictionary.
        """
        if not self.file_path:
            raise ValueError("File path is required for metadata extraction")

        file_path = Path(self.file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        headers = {"Accept": "application/json"}

        try:
            with open(file_path, "rb") as file:
                response = requests.put(
                    f"{self.tika_server_url}/meta",
                    headers=headers,
                    data=file,
                    timeout=300,
                )
                response.raise_for_status()
                return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 502:
                logging.warning(
                    f"Tika metadata endpoint unavailable (502) for {file_path.name}, returning basic metadata"
                )
                # 返回基本的文件元数据
                return self._get_basic_metadata(file_path)
            else:
                logging.error(
                    f"HTTP error extracting metadata from {file_path.name}: {str(e)}"
                )
                return self._get_basic_metadata(file_path)
        except Exception as e:
            logging.error(f"Error extracting metadata from {file_path.name}: {str(e)}")
            return self._get_basic_metadata(file_path)

    def _get_basic_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Get basic file metadata when Tika metadata extraction fails.

        :param file_path: Path to the file.
        :return: Basic metadata dictionary.
        """
        try:
            stat = file_path.stat()
            return {
                "filename": file_path.name,
                "file_size": stat.st_size,
                "file_extension": file_path.suffix,
                "last_modified": stat.st_mtime,
                "created": stat.st_ctime,
                "md5_hash": self.get_file_md5(str(file_path)),
            }
        except Exception as e:
            logging.error(
                f"Error getting basic metadata for {file_path.name}: {str(e)}"
            )
            return {"filename": file_path.name, "error": str(e)}

    def extract_text_streaming(self) -> str:
        """
        Extract text using streaming for large files.

        :return: Extracted text content.
        """
        if not self.file_path:
            raise ValueError("File path is required for document conversion")

        file_path = Path(self.file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        headers = {"Accept": "text/plain"}

        try:
            with open(file_path, "rb") as file:
                with requests.put(
                    f"{self.tika_server_url}/tika",
                    headers=headers,
                    data=file,
                    stream=True,
                    timeout=300,
                ) as response:
                    response.raise_for_status()
                    return response.text
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 502:
                logging.warning(
                    f"Tika server unavailable for streaming {file_path.name}, falling back to direct reading"
                )
                return self._read_text_file_fallback(file_path)
            else:
                logging.error(
                    f"HTTP error extracting text from {file_path.name}: {str(e)}"
                )
                return self._read_text_file_fallback(file_path)
        except Exception as e:
            logging.error(f"Error extracting text from {file_path.name}: {str(e)}")
            return self._read_text_file_fallback(file_path)

    def get_type(self) -> str:
        """
        Get the type of the document converter.

        :return: The type of the document converter.
        """
        return "TikaDocumentConvertor"

    def is_supported_format(self, file_path: str) -> bool:
        """
        Check if the file format is supported by Tika.
        Tika supports a wide range of formats.

        :param file_path: Path to the file to check.
        :return: True if the format is supported, False otherwise.
        """
        file_path_obj = Path(file_path)
        suffix = file_path_obj.suffix.lower()

        # Tika 支持的常见文件格式
        supported_extensions = {
            # 文档格式
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".odt",
            ".ods",
            ".odp",
            ".rtf",
            # 文本格式
            ".txt",
            ".csv",
            ".xml",
            ".html",
            ".htm",
            ".md",
            ".markdown",
            # 图片格式（OCR）
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".tiff",
            ".tif",
            # 压缩格式
            ".zip",
            ".tar",
            ".gz",
            ".7z",
            # 其他格式
            ".json",
            ".yaml",
            ".yml",
        }

        return suffix in supported_extensions

    @staticmethod
    def get_file_md5(file_path: str) -> str:
        """
        Calculate MD5 hash of a file.

        :param file_path: Path to the file.
        :return: MD5 hash of the file.
        """
        try:
            with open(file_path, "rb") as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()
        except Exception as e:
            logging.error(f"Failed to calculate MD5 for file {file_path}: {str(e)}")
            raise e
