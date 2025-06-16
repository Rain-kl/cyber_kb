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
        """
        添加文档到向量数据库
        :param document_chunks:
        :param embeddings:
        :param metadata_list:
        :param doc_id:
        :return:
        """
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

    def delete_document(self, doc_id: str):
        """
        删除指定doc_id的所有相关文档条目

        Args:
            doc_id (str): 要删除的文档ID

        Returns:
            int: 删除的文档条目数量
        """
        try:
            # 获取所有文档
            all_documents = self.collection.get()

            # 找到所有以doc_id开头的ID
            ids_to_delete = []
            if all_documents["ids"]:
                for doc_id_in_db in all_documents["ids"]:
                    # 检查ID是否以指定的doc_id开头，格式为 {doc_id}_{chunk_index}
                    if doc_id_in_db.startswith(f"{doc_id}_"):
                        ids_to_delete.append(doc_id_in_db)

            # 如果找到要删除的ID，执行删除操作
            if ids_to_delete:
                self.collection.delete(ids=ids_to_delete)
                print(f"成功删除 {len(ids_to_delete)} 个与文档ID '{doc_id}' 相关的条目")
                return len(ids_to_delete)
            else:
                print(f"未找到与文档ID '{doc_id}' 相关的条目")
                return 0

        except Exception as e:
            print(f"删除文档时发生错误: {str(e)}")
            raise e

    def get_document_count(self):
        """
        获取向量数据库中文档条目的总数

        Returns:
            int: 文档条目总数
        """
        try:
            results = self.collection.count()
            return results
        except Exception as e:
            print(f"获取文档数量时发生错误: {str(e)}")
            return 0

    def check_document_exists(self, doc_id: str):
        """
        检查指定doc_id的文档是否存在

        Args:
            doc_id (str): 要检查的文档ID

        Returns:
            bool: 如果存在返回True，否则返回False
        """
        try:
            # 获取所有文档ID
            all_documents = self.collection.get()

            if all_documents["ids"]:
                for doc_id_in_db in all_documents["ids"]:
                    if doc_id_in_db.startswith(f"{doc_id}_"):
                        return True
            return False

        except Exception as e:
            print(f"检查文档存在性时发生错误: {str(e)}")
            return False

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
