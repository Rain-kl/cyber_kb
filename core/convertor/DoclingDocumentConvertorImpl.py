from typing import Any, Dict, List, Literal
from DocumentConvertor import DocumentConvertor


class DoclingDocumentConvertorImpl(DocumentConvertor):
    """
    Implementation of the DocumentConvertor interface for Docling.
    This class is responsible for converting documents to a format suitable for Docling.
    """

    def __init__(
        self,
        file_path: str = None,
        conversion_engine: Literal["docling", "tika"] = "docling",
    ):
        super().__init__(file_path, conversion_engine)

    def convert(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert the given document to a format suitable for Docling.

        :param document: The document to convert.
        :return: The converted document as a list of dictionaries.
        """
        # Implement the conversion logic here
        pass

    def get_type(self) -> str:
        """
        Get the type of the document converter.

        :return: The type of the document converter.
        """
        return "DoclingDocumentConvertor"
