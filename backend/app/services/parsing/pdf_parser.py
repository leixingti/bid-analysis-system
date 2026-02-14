"""PDF 文档解析器"""
import fitz  # PyMuPDF
from typing import Dict, Any, Optional
from datetime import datetime
from app.utils.hash import md5_bytes
import logging

logger = logging.getLogger(__name__)


class PDFParser:
    """PDF 全量解析引擎"""

    @staticmethod
    def parse(file_path: str) -> Dict[str, Any]:
        try:
            doc = fitz.open(file_path)
            result = {
                "full_text": "",
                "metadata": PDFParser._extract_metadata(doc),
                "format_info": PDFParser._extract_format(doc),
                "images": PDFParser._extract_images(doc),
                "page_count": len(doc),
            }
            # 提取全文
            texts = []
            for page in doc:
                texts.append(page.get_text())
            result["full_text"] = "\n".join(texts)
            doc.close()
            return result
        except Exception as e:
            logger.error(f"PDF 解析失败: {file_path}, 错误: {e}")
            return {"full_text": "", "metadata": {}, "format_info": {}, "images": [], "page_count": 0, "error": str(e)}

    @staticmethod
    def _extract_metadata(doc: fitz.Document) -> Dict[str, Any]:
        meta = doc.metadata or {}
        return {
            "author": meta.get("author", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "title": meta.get("title", ""),
            "subject": meta.get("subject", ""),
            "keywords": meta.get("keywords", ""),
            "created_date": meta.get("creationDate", ""),
            "modified_date": meta.get("modDate", ""),
            "format": meta.get("format", ""),
            "encryption": meta.get("encryption", ""),
        }

    @staticmethod
    def _extract_format(doc: fitz.Document) -> Dict[str, Any]:
        fonts = set()
        font_sizes = set()

        for page_num in range(min(len(doc), 10)):  # 抽样前10页
            page = doc[page_num]
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            for block in blocks.get("blocks", []):
                if block.get("type") == 0:  # text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            fonts.add(span.get("font", ""))
                            font_sizes.add(round(span.get("size", 0), 1))

        first_page = doc[0] if len(doc) > 0 else None
        page_width = first_page.rect.width if first_page else 0
        page_height = first_page.rect.height if first_page else 0

        return {
            "fonts": sorted(list(fonts)),
            "font_sizes": sorted(list(font_sizes)),
            "page_width": round(page_width, 2),
            "page_height": round(page_height, 2),
            "page_count": len(doc),
        }

    @staticmethod
    def _extract_images(doc: fitz.Document) -> list:
        images = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            img_list = page.get_images(full=True)
            for img_index, img in enumerate(img_list):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image:
                        images.append({
                            "page": page_num + 1,
                            "index": img_index,
                            "width": base_image.get("width", 0),
                            "height": base_image.get("height", 0),
                            "md5": md5_bytes(base_image.get("image", b"")),
                            "ext": base_image.get("ext", ""),
                        })
                except Exception:
                    pass
        return images
