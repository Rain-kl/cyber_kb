import os
from typing import List

import chromadb


class VectorStore:
    def __init__(self, collection, persist_directory="./data/chroma_db"):
        os.makedirs(persist_directory, exist_ok=True)
        assert isinstance(collection, str), "collection must be a string"
        self.chroma_client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.chroma_client.get_or_create_collection(collection)

    def add_documents(
            self,
            document_chunks: List,
            embeddings: List[List],
            metadata_list: List,
            doc_id: str,
    ):
        """添加文档到向量数据库"""
        ids = [f"{doc_id}_{i}" for i in range(len(document_chunks))]

        self.collection.add(
            documents=document_chunks,
            embeddings=embeddings,
            metadatas=metadata_list,
            ids=ids,
        )

        return ids

    def search_by_embedding(self, embedding, top_k=5):
        """基于文本搜索相关文档"""
        results = self.collection.query(query_embeddings=[embedding], n_results=top_k)

        return results

    def search_by_keyword(self, keyword, top_k=5):
        """基于关键字搜索文档"""
        results = self.collection.query(query_texts=[keyword], n_results=top_k)

        return results

    def list_all_documents(self, limit=None):
        """
        列出集合中的所有文档

        参数:
            limit (int, 可选): 要返回的最大文档数量。如果为None，则返回所有文档。

        返回:
            dict: 包含ids、documents、embeddings和metadatas的字典
        """
        # 获取集合中的所有文档
        # ChromaDB的get方法如果不指定ids，会返回所有文档
        results = self.collection.get(limit=limit)

        return results

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
        sentence_enders = {".", "?", "!", "。", "？", "！", "\n"}
        if not text:
            return []

        if chunk_size <= overlap:
            raise ValueError(
                f"chunk_size ({chunk_size}) must be greater than overlap ({overlap})"
            )

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

                        if (
                                i >= start_index
                        ):  # Ensure the ender is within the current theoretical chunk slice
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
                    f"Warning: Potential stall detected. Chunk end: {actual_end_index}, Overlap: {overlap}, Current start: {start_index}. Calculated next start: {next_start_index}. Forcing minimal advancement."
                )
                start_index += 1
            else:
                start_index = next_start_index

            # Safety clamp (though the loop condition `start_index < text_length` should suffice)
            start_index = min(start_index, text_length)

        return chunks


class KBVectorStore(VectorStore):
    def __init__(self, collection, persist_directory="./data/chroma_kb"):
        super().__init__(collection, persist_directory=persist_directory)


class MemoVectorStore(VectorStore):
    def __init__(self, collection, persist_directory="./data/chroma_memo"):
        super().__init__(collection, persist_directory=persist_directory)
