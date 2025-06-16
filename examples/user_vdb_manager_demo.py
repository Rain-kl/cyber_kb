#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户向量数据库管理器使用示例
演示如何使用 UserKBVDBManager 进行用户知识库管理
"""

import asyncio

from core.vdb_manager import UserKBVDBManager
from utils.embedding import AsyncOllamaEmbeddingModel


async def demo_user_vdb_manager():
    """演示用户向量数据库管理器的完整使用流程"""

    print("=" * 60)
    print("用户向量数据库管理器使用演示")
    print("=" * 60)

    # 1. 初始化管理器
    user_id = "demo_user_001"
    print(f"\n1. 初始化用户 {user_id} 的向量数据库管理器...")

    try:
        # 如果有Ollama服务，可以使用真实的嵌入模型
        embedding_model = AsyncOllamaEmbeddingModel(
            ollama_api_url="http://localhost:11434", model_name="bge-m3"
        )
        vdb_manager = UserKBVDBManager(user_id=user_id, embedding_model=embedding_model)
        print("✓ 使用 Ollama BGE-M3 嵌入模型")
    except Exception as e:
        print(f"⚠ Ollama 服务不可用: {e}")
        print("⚠ 使用默认嵌入模型（需要配置）")
        vdb_manager = UserKBVDBManager(user_id=user_id)

    print(f"✓ 用户向量数据库路径: {vdb_manager.get_user_vdb_path()}")

    # 2. 定义集合和文档
    collection_id = "ai_knowledge"
    doc_id = "ai_introduction_001"

    print(f"\n2. 准备添加文档到集合 '{collection_id}'...")

    # 示例文档内容
    document_content = """
    人工智能（Artificial Intelligence, AI）是计算机科学的一个分支，
    它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。
    
    机器学习是人工智能的一个子集，它使计算机具有学习能力，
    而不需要明确地编程。机器学习算法通过训练数据来构建数学模型，
    以便对新数据做出预测或决策。
    
    深度学习是机器学习的一个子领域，它基于人工神经网络，
    特别是深层神经网络来进行学习和表示。深度学习在图像识别、
    自然语言处理、语音识别等领域取得了显著的成果。
    
    自然语言处理（Natural Language Processing, NLP）是人工智能和语言学的分支，
    它研究能实现人与计算机之间用自然语言进行有效通信的各种理论和方法。
    
    计算机视觉是一门研究如何使机器"看"的科学，更进一步的说，
    就是是指用摄像机和电脑代替人眼对目标进行识别、跟踪和测量等机器视觉，
    并进一步做图形处理。
    """

    # 3. 文档分块
    print("\n3. 对文档进行分块处理...")
    from utils.vector_store import VectorStore

    chunks = VectorStore.chunk_text(document_content, chunk_size=200, overlap=50)
    print(f"✓ 文档被分为 {len(chunks)} 个分块")
    for i, chunk in enumerate(chunks):
        print(f"   分块 {i+1}: {chunk[:50]}...")

    # 4. 添加文档分块到向量数据库
    print(f"\n4. 添加文档分块到向量数据库...")
    try:
        chunk_ids = await vdb_manager.add_chunks(
            collection_id=collection_id, document_chunks=chunks, doc_id=doc_id
        )
        print(f"✓ 成功添加 {len(chunk_ids)} 个分块")
        print(
            f"✓ 分块IDs: {chunk_ids[:3]}..."
            if len(chunk_ids) > 3
            else f"✓ 分块IDs: {chunk_ids}"
        )
    except Exception as e:
        print(f"✗ 添加分块失败: {e}")
        return

    # 5. 查询文档数量
    print(f"\n5. 查询集合中的文档数量...")
    doc_count = vdb_manager.get_document_count(collection_id)
    print(f"✓ 集合 '{collection_id}' 中有 {doc_count} 个文档分块")

    # 6. 检查文档是否存在
    print(f"\n6. 检查文档是否存在...")
    exists = vdb_manager.check_document_exists(collection_id, doc_id)
    print(f"✓ 文档 '{doc_id}' 存在: {exists}")

    # 7. 基于文本搜索
    print(f"\n7. 执行语义搜索...")
    search_queries = ["什么是机器学习？", "深度学习的应用", "计算机视觉技术"]

    for query in search_queries:
        print(f"\n   查询: '{query}'")
        try:
            results = await vdb_manager.search_by_text(
                collection_id=collection_id, query_text=query, top_k=2
            )

            if results and "documents" in results and results["documents"]:
                print(f"   ✓ 找到 {len(results['documents'][0])} 个相关结果:")
                for i, doc in enumerate(results["documents"][0]):
                    print(f"     结果 {i+1}: {doc[:100]}...")
            else:
                print("   ⚠ 未找到相关结果")

        except Exception as e:
            print(f"   ✗ 搜索失败: {e}")

    # 8. 列出所有文档
    print(f"\n8. 列出集合中的所有文档...")
    try:
        all_docs = vdb_manager.list_all_documents(collection_id, limit=5)
        if all_docs and "ids" in all_docs:
            print(f"✓ 集合中的文档ID (前5个): {all_docs['ids'][:5]}")
        else:
            print("⚠ 集合为空或获取失败")
    except Exception as e:
        print(f"✗ 列出文档失败: {e}")

    # 9. 列出用户的所有集合
    print(f"\n9. 列出用户的所有集合...")
    collections = vdb_manager.list_collections()
    print(f"✓ 用户 '{user_id}' 的集合: {collections}")

    # 10. 删除文档测试（可选）
    print(f"\n10. 文档管理操作...")
    print("   注意: 以下是删除操作的演示，实际使用时请谨慎操作")

    # 不实际执行删除，只演示方法调用
    print(
        f"   - 删除文档的方法: vdb_manager.delete_document('{collection_id}', '{doc_id}')"
    )
    print(f"   - 这将删除文档 '{doc_id}' 的所有分块")

    print(f"\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)


def demo_sync_operations():
    """演示同步操作方法"""
    print("\n" + "=" * 60)
    print("同步操作演示")
    print("=" * 60)

    user_id = "demo_user_sync"
    collection_id = "sync_collection"

    # 初始化管理器
    vdb_manager = UserKBVDBManager(user_id=user_id)

    print(f"✓ 初始化用户 '{user_id}' 的向量数据库管理器")
    print(f"✓ 向量数据库路径: {vdb_manager.get_user_vdb_path()}")

    # 同步方法演示
    print("\n同步方法调用示例:")
    print("- vdb_manager.get_document_count(collection_id)")
    print("- vdb_manager.check_document_exists(collection_id, doc_id)")
    print("- vdb_manager.list_all_documents(collection_id)")
    print("- vdb_manager.delete_document(collection_id, doc_id)")
    print("- vdb_manager.add_chunks_sync(...)")
    print("- vdb_manager.search_by_text_sync(...)")

    # 测试基本操作
    count = vdb_manager.get_document_count(collection_id)
    print(f"\n✓ 当前文档数量: {count}")


async def demo_multiple_collections():
    """演示多集合管理"""
    print("\n" + "=" * 60)
    print("多集合管理演示")
    print("=" * 60)

    user_id = "demo_user_multi"
    vdb_manager = UserKBVDBManager(user_id=user_id)

    collections = ["ai_basics", "ml_algorithms", "deep_learning", "nlp_techniques"]

    print(f"✓ 为用户 '{user_id}' 创建多个知识库集合...")

    for collection in collections:
        # 创建集合（通过获取向量存储实例）
        vector_store = vdb_manager._get_vector_store(collection)
        print(f"   ✓ 创建集合: {collection}")

    # 列出所有集合
    user_collections = vdb_manager.list_collections()
    print(f"\n✓ 用户拥有的集合: {user_collections}")

    # 为每个集合获取文档数量
    print(f"\n各集合的文档数量:")
    for collection in user_collections:
        count = vdb_manager.get_document_count(collection)
        print(f"   {collection}: {count} 个文档")


if __name__ == "__main__":
    print("请选择演示模式:")
    print("1. 完整异步演示 (需要嵌入模型)")
    print("2. 同步操作演示")
    print("3. 多集合管理演示")
    print("4. 全部演示")

    choice = input("\n请输入选项 (1-4): ").strip()

    if choice == "1":
        asyncio.run(demo_user_vdb_manager())
    elif choice == "2":
        demo_sync_operations()
    elif choice == "3":
        asyncio.run(demo_multiple_collections())
    elif choice == "4":
        # 运行所有演示
        asyncio.run(demo_user_vdb_manager())
        demo_sync_operations()
        asyncio.run(demo_multiple_collections())
    else:
        print("无效选项，运行默认演示...")
        demo_sync_operations()
        asyncio.run(demo_multiple_collections())
