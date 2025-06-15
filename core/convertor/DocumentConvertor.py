from abc import ABC, abstractmethod


class DocumentConvertor(ABC):
    """
    Abstract base class for document converters.
    """

    def __init__(
        self,
        file_path: str = None,
    ):
        self.file_path = file_path

    @abstractmethod
    def convert(self) -> str:
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
