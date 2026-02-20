"""文档管理 API — 上传、解析、查询"""
import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import logging

from app.core.database import get_db
from app.core.config import settings
from app.models.models import Document, Project
from app.schemas.schemas import DocumentResponse
from app.utils.hash import compute_md5
from app.services.parsing.pdf_parser import PDFParser
from app.services.parsing.docx_parser import DocxParser

router = APIRouter()
logger = logging.getLogger(__name__)


def _doc_to_response(d: Document) -> DocumentResponse:
    """Convert Document model to DocumentResponse, handling fonts_used default."""
    data = {c.name: getattr(d, c.name) for c in d.__table__.columns if c.name != "full_text"}
    if data.get("fonts_used") is None:
        data["fonts_used"] = []
    return DocumentResponse(**data)


@router.post("/upload/{project_id}", response_model=List[DocumentResponse])
async def upload_documents(
    project_id: str,
    files: List[UploadFile] = File(...),
    company_names: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    上传标书文档（支持批量）

    - project_id: 项目ID
    - files: 文件列表（PDF/DOCX）
    - company_names: 逗号分隔的投标单位名称（与文件顺序对应）
    """
    # Verify project exists
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # Parse company names
    companies = []
    if company_names:
        companies = [c.strip() for c in company_names.split(",")]

    uploaded_docs = []
    project_dir = os.path.join(settings.UPLOAD_DIR, project_id)
    os.makedirs(project_dir, exist_ok=True)

    for idx, file in enumerate(files):
        # Validate file type
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".pdf", ".docx", ".doc"]:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {file.filename}，仅支持 PDF/DOCX"
            )

        # Save file
        file_path = os.path.join(project_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Compute hash
        file_hash = compute_md5(file_path)
        file_size = os.path.getsize(file_path)

        company = companies[idx] if idx < len(companies) else ""

        # Create document record
        doc = Document(
            project_id=project_id,
            company_name=company,
            file_name=file.filename,
            file_path=file_path,
            file_type=ext.replace(".", ""),
            file_size=file_size,
            file_hash=file_hash,
        )
        db.add(doc)
        await db.flush()

        # Parse document
        try:
            parsed_data = _parse_document(file_path, ext)
            _apply_parsed_data(doc, parsed_data)
            doc.parsed = 1
            logger.info(f"✅ 文档解析成功: {file.filename}, 文本长度: {doc.text_length}")
        except Exception as e:
            doc.parsed = 2
            logger.error(f"❌ 文档解析失败 {file.filename}: {e}")

        uploaded_docs.append(doc)

    await db.commit()
    for doc in uploaded_docs:
        await db.refresh(doc)

    return [_doc_to_response(d) for d in uploaded_docs]


@router.get("/{project_id}", response_model=List[DocumentResponse])
async def list_documents(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取项目下所有文档"""
    result = await db.execute(
        select(Document).where(Document.project_id == project_id).order_by(Document.created_at)
    )
    docs = result.scalars().all()
    return [_doc_to_response(d) for d in docs]


@router.get("/detail/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    """获取文档详情"""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return _doc_to_response(doc)


@router.post("/reparse/{doc_id}")
async def reparse_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    """重新解析文档"""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    try:
        ext = f".{doc.file_type}" if doc.file_type else os.path.splitext(doc.file_name)[1]
        parsed_data = _parse_document(doc.file_path, ext)
        _apply_parsed_data(doc, parsed_data)
        doc.parsed = 1
        await db.commit()
        return {"message": "解析成功", "doc_id": doc_id, "text_length": doc.text_length}
    except Exception as e:
        doc.parsed = 2
        await db.commit()
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    """删除文档"""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # Remove file
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    await db.delete(doc)
    await db.commit()
    return {"message": "文档已删除", "id": doc_id}


# ========== Helper Functions ==========

def _parse_document(file_path: str, ext: str) -> dict:
    """根据文件类型选择解析器"""
    ext = ext.lower()
    if ext in [".pdf"]:
        return PDFParser.parse(file_path)
    elif ext in [".docx"]:
        return DocxParser.parse(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _apply_parsed_data(doc: Document, data: dict):
    """将解析结果应用到文档模型"""
    meta = data.get("metadata", {})

    # 🔧 关键修复：兼容 "full_text" 和 "text" 两种 key
    doc.full_text = data.get("full_text") or data.get("text") or ""
    doc.text_length = len(doc.full_text)
    doc.page_count = data.get("page_count", 0)
    doc.fonts_used = data.get("fonts", [])
    doc.format_info = data.get("format_info", {})

    # 元数据映射（兼容不同解析器的 key 命名）
    doc.meta_author = meta.get("author", "")
    doc.meta_company = meta.get("company", "")
    doc.meta_last_modified_by = meta.get("last_modified_by", "")
    doc.meta_producer = meta.get("producer", "")
    doc.meta_creator = meta.get("creator") or meta.get("application", "")
    doc.meta_software_version = meta.get("software_version") or meta.get("app_version", "")

    # Parse timestamps（兼容多种 key 命名）
    for field, keys in [
        ("meta_created_time", ["created_time", "created_date"]),
        ("meta_modified_time", ["modified_time", "modified_date"]),
    ]:
        ts = None
        for key in keys:
            ts = meta.get(key)
            if ts:
                break
        if ts:
            try:
                if isinstance(ts, str) and ts.strip():
                    # 处理 PDF 格式的日期 D:20240101120000+08'00'
                    if ts.startswith("D:"):
                        ts_clean = ts[2:16].ljust(14, '0')
                        setattr(doc, field, datetime.strptime(ts_clean, "%Y%m%d%H%M%S"))
                    else:
                        setattr(doc, field, datetime.fromisoformat(ts.replace("Z", "+00:00")))
                elif hasattr(ts, 'year'):  # already a datetime
                    setattr(doc, field, ts)
            except Exception as e:
                logger.warning(f"时间解析失败 ({field}={ts}): {e}")

    doc.meta_extra = {k: v for k, v in meta.items()
                      if k not in ["author", "company", "last_modified_by", "producer",
                                   "creator", "software_version", "created_time", "modified_time",
                                   "created_date", "modified_date", "application", "app_version"]}
