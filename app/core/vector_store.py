import os

import chromadb


class VectorStore:
    def __init__(self, collection, persist_directory="./data/chroma_db"):
        os.makedirs(persist_directory, exist_ok=True)
        assert isinstance(collection, str), "collection must be a string"
        self.chroma_client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.chroma_client.get_or_create_collection(collection)

    def add_documents(self, document_chunks, embeddings, metadata_list, doc_id):
        """添加文档到向量数据库"""
        ids = [f"{doc_id}_{i}" for i in range(len(document_chunks))]

        self.collection.add(
            documents=document_chunks,
            embeddings=embeddings,
            metadatas=metadata_list,
            ids=ids
        )

        return ids

    def search_by_embedding(self, embedding, top_k=5):
        """基于文本搜索相关文档"""
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k
        )

        return results

    def search_by_keyword(self, keyword, top_k=5):
        """基于关键字搜索文档"""
        results = self.collection.query(
            query_texts=[keyword],
            n_results=top_k
        )

        return results
