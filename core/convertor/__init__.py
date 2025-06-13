"""
Document Convertor module for handling different document conversion engines.
"""

from .DocumentConvertor import DocumentConvertor

# 具体实现类可以通过工厂方法创建，不需要直接导入
__all__ = ["DocumentConvertor"]
