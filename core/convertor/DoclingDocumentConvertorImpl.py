import logging
from pathlib import Path

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
    WordFormatOption,
)
from docling.pipeline.simple_pipeline import SimplePipeline
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

from .DocumentConvertor import DocumentConvertor

_log = logging.getLogger(__name__)


class DoclingDocumentConvertorImpl(DocumentConvertor):
    """
    Implementation of the DocumentConvertor interface for Docling.
    This class is responsible for converting documents to a format suitable for Docling.
    """

    def __init__(self, file_path: str = None):
        super().__init__(file_path)
        self.file_path = file_path
        # 初始化 docling 文档转换器
        self.doc_converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF,
                InputFormat.IMAGE,
                InputFormat.DOCX,
                InputFormat.HTML,
                InputFormat.PPTX,
                InputFormat.ASCIIDOC,
                InputFormat.CSV,
                InputFormat.MD,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline, backend=PyPdfiumDocumentBackend
                ),
                InputFormat.DOCX: WordFormatOption(pipeline_cls=SimplePipeline),
            },
        )

    def convert(self) -> str:
        """
        Convert the given document to markdown format using Docling.

        :return: The converted document content as markdown string.
        """
        if not self.file_path:
            raise ValueError("File path is required for document conversion")

        file_path = Path(self.file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        # 特殊处理纯文本文件
        if file_path.suffix.lower() in [".txt"]:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return f"```\n{content}\n```"
            except UnicodeDecodeError:
                # 如果UTF-8失败，尝试其他编码
                with open(file_path, "r", encoding="gbk") as f:
                    content = f.read()
                return f"```\n{content}\n```"

        try:
            _log.info(f"Converting document: {file_path.name}")

            # 转换文档
            conv_result = self.doc_converter.convert(file_path)

            # 检查是否有文档内容
            if hasattr(conv_result, "document") and conv_result.document:
                try:
                    # 首先尝试标准 markdown 导出
                    markdown_content = conv_result.document.export_to_markdown()
                    
                    # 如果 markdown 内容为空，尝试手动提取内容
                    if not markdown_content.strip():
                        _log.info(f"Standard markdown export is empty, trying manual extraction for {file_path.name}")
                        markdown_content = self._extract_content_manually(conv_result.document)
                    
                    _log.info(
                        f"Document {file_path.name} converted successfully to markdown (length: {len(markdown_content)})"
                    )
                    return markdown_content
                except Exception as export_error:
                    _log.error(
                        f"Failed to export document {file_path.name} to markdown: {str(export_error)}"
                    )
                    raise RuntimeError(
                        f"Export failed: {str(export_error)}"
                    ) from export_error
            else:
                error_msg = f"No document content available for {file_path.name}"
                _log.error(error_msg)
                raise RuntimeError(error_msg)

        except Exception as e:
            error_msg = f"Error converting document {file_path.name}: {str(e)}"
            _log.error(error_msg)
            raise RuntimeError(error_msg) from e

    def get_type(self) -> str:
        """
        Get the type of the document converter.

        :return: The type of the document converter.
        """
        return "DoclingDocumentConvertor"

    def is_supported_format(self, file_path: str) -> bool:
        """
        Check if the file format is supported by the converter.

        :param file_path: Path to the file to check.
        :return: True if the format is supported, False otherwise.
        """
        file_path_obj = Path(file_path)
        suffix = file_path_obj.suffix.lower()

        # 支持的文件扩展名映射
        supported_extensions = {
            ".pdf": InputFormat.PDF,
            ".docx": InputFormat.DOCX,
            ".doc": InputFormat.DOCX,
            ".html": InputFormat.HTML,
            ".htm": InputFormat.HTML,
            ".pptx": InputFormat.PPTX,
            ".ppt": InputFormat.PPTX,
            ".md": InputFormat.MD,
            ".markdown": InputFormat.MD,
            ".txt": "TEXT",  # 特殊处理
            ".csv": InputFormat.CSV,
            ".asciidoc": InputFormat.ASCIIDOC,
            ".adoc": InputFormat.ASCIIDOC,
            ".png": InputFormat.IMAGE,
            ".jpg": InputFormat.IMAGE,
            ".jpeg": InputFormat.IMAGE,
            ".gif": InputFormat.IMAGE,
            ".bmp": InputFormat.IMAGE,
            ".tiff": InputFormat.IMAGE,
        }

        return suffix in supported_extensions

    def _extract_content_manually(self, document) -> str:
        """
        手动从文档中提取内容，包括表格和文本
        当标准 markdown 导出失败或为空时使用此方法
        
        :param document: Docling 文档对象
        :return: 提取的文本内容
        """
        content_parts = []
        
        try:
            # 导出为字典以便分析
            dict_content = document.export_to_dict()
            
            # 提取 texts 中的内容
            if 'texts' in dict_content:
                for text_item in dict_content['texts']:
                    if 'text' in text_item and text_item['text'].strip():
                        content_parts.append(text_item['text'].strip())
            
            # 提取 tables 中的内容
            if 'tables' in dict_content:
                for table in dict_content['tables']:
                    if 'data' in table and 'table_cells' in table['data']:
                        table_content = []
                        for cell in table['data']['table_cells']:
                            if 'text' in cell and cell['text'].strip():
                                cell_text = cell['text'].strip()
                                table_content.append(cell_text)
                        
                        if table_content:
                            # 将表格内容组合为 markdown 格式
                            combined_table_text = '\n\n'.join(table_content)
                            content_parts.append(combined_table_text)
            
            # 如果仍然没有内容，尝试 HTML 导出并提取
            if not content_parts:
                try:
                    html_content = document.export_to_html()
                    if html_content.strip():
                        # 简单的 HTML 标签移除（可以考虑使用更专业的 HTML 解析器）
                        import re
                        text_content = re.sub(r'<[^>]+>', '', html_content)
                        text_content = re.sub(r'\s+', ' ', text_content).strip()
                        if text_content:
                            content_parts.append(text_content)
                except Exception as html_error:
                    _log.warning(f"HTML extraction also failed: {str(html_error)}")
            
            return '\n\n'.join(content_parts) if content_parts else ""
            
        except Exception as e:
            _log.error(f"Manual content extraction failed: {str(e)}")
            return ""
