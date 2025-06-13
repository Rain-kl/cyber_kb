from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal


class DocumentConvertor(ABC):
    """
    Abstract base class for document converters.
    """

    def __init__(
        self,
        file_path: str = None,
        conversion_engine: Literal["docling", "tika"] = "docling",
    ):
        super().__init__()
        self.file_path = file_path
        self.conversion_engine = conversion_engine

    @staticmethod
    def create_convertor(
        file_path: str = None, conversion_engine: Literal["docling", "tika"] = "docling"
    ) -> "DocumentConvertor":
        """
        Factory method to create appropriate document converter based on engine type.

        :param file_path: Path to the file to be converted
        :param conversion_engine: Type of conversion engine to use
        :return: Instance of appropriate DocumentConvertor implementation
        :raises ValueError: If conversion_engine is not supported
        """
        # 延迟导入以避免循环导入
        import sys
        import os

        current_dir = os.path.dirname(__file__)
        sys.path.insert(0, current_dir)

        try:
            if conversion_engine == "docling":
                from DoclingDocumentConvertorImpl import DoclingDocumentConvertorImpl

                return DoclingDocumentConvertorImpl(file_path, conversion_engine)
            elif conversion_engine == "tika":
                from TikaDocumentConvertorImpl import TikaDocumentConvertorImpl

                return TikaDocumentConvertorImpl(file_path, conversion_engine)
            else:
                raise ValueError(f"Unsupported conversion engine: {conversion_engine}")
        finally:
            sys.path.remove(current_dir)

    @abstractmethod
    def convert(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert a document into a list of dictionaries.

        :param document: The document to convert.
        :return: A list of dictionaries representing the converted document.
        """
        pass

    @abstractmethod
    def get_type(self) -> str:
        """
        Get the type of the document converter.

        :return: The type of the document converter.
        """
        pass
