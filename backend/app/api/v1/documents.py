"""文档管理 API — 上传、解析、预览、查询"""
import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import logging

from app.core.database import get_db
from app.core.config import settings
from app.core.security import require_auth, get_client_ip
from app.models.models import Document, Project
from app.schemas.schemas import DocumentResponse, DocumentPreview
from app.utils.hash import compute_md5
from app.services.parsing.pdf_parser import PDFParser
from app.services.parsing.docx_parser import DocxParser
from app.services.audit import log_action

router = APIRouter()
logger = logging.getLogger(__name__)


def _doc_to_response(d: Document) -> DocumentResponse:
    data = {c.name: getattr(d, c.name) for c in d.__table__.columns if c.name != "full_text"}
    if data.get("fonts_used") is None:
        data["fonts_used"] = []
    return DocumentResponse(**data)


@router.post("/upload/{project_id}", response_model=List[DocumentResponse])
async def upload_documents(
    project_id: str,
    files: List[UploadFile] = File(...),
    company_names: Optional[str] = Form(None),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_auth),
):
    """上传标书文档（支持批量）"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    companies = [c.strip() for c in company_names.split(",")] if company_names else []

    uploaded_docs = []
    project_dir = os.path.join(settings.UPLOAD_DIR, project_id)
    os.makedirs(project_dir, exist_ok=True)

    for idx, file in enumerate(files):
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".pdf", ".docx", ".doc"]:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式: {file.filename}，仅支持 PDF/DOCX")

        file_path = os.path.join(project_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        file_hash = compute_md5(file_path)
        file_size = os.path.getsize(file_path)
        company = companies[idx] if idx < len(companies) else ""

        doc = Document(
            project_id=project_id, company_name=company, file_name=file.filename,
            file_path=file_path, file_type=ext.replace(".", ""),
            file_size=file_size, file_hash=file_hash,
        )
        db.add(doc)
        await db.flush()

        # 解析文档（带重试）
        parse_success = False
        for attempt in range(2):
            try:
                parsed_data = _parse_document(file_path, ext)
                _apply_parsed_data(doc, parsed_data)
                doc.parsed = 1
                doc.parse_error = None
                parse_success = True
                logger.info(f"✅ 文档解析成功: {file.filename}, 文本长度: {doc.text_length}")
                break
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"⚠️ 首次解析失败, 重试: {file.filename}: {e}")
                else:
                    doc.parsed = 2
                    doc.parse_error = str(e)[:500]
                    logger.error(f"❌ 文档解析失败 {file.filename}: {e}")

        uploaded_docs.append(doc)

    await log_action(db, action="upload", resource_type="document", resource_id=project_id,
                   user_id=current_user.get("sub"), username=current_user.get("username"),
                   details={"file_count": len(files), "files": [f.filename for f in files]},
                   ip_address=get_client_ip(request) if request else None)

    await db.commit()
    for doc in uploaded_docs:
        await db.refresh(doc)

    return [_doc_to_response(d) for d in uploaded_docs]


@router.get("/{project_id}", response_model=List[DocumentResponse])
async def list_documents(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Document).where(Document.project_id == project_id).order_by(Document.created_at)
    )
    return [_doc_to_response(d) for d in result.scalars().all()]


@router.get("/detail/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return _doc_to_response(doc)


@router.get("/preview/{doc_id}", response_model=DocumentPreview)
async def preview_document(doc_id: str, max_chars: int = 3000, db: AsyncSession = Depends(get_db)):
    """文档预览 — 返回前N字符文本 + 元数据"""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    text = doc.full_text or ""
    preview_text = text[:max_chars] + ("..." if len(text) > max_chars else "")

    metadata = {
        "author": doc.meta_author,
        "company": doc.meta_company,
        "creator": doc.meta_creator,
        "producer": doc.meta_producer,
        "software_version": doc.meta_software_version,
        "last_modified_by": doc.meta_last_modified_by,
        "created_time": doc.meta_created_time.isoformat() if doc.meta_created_time else None,
        "modified_time": doc.meta_modified_time.isoformat() if doc.meta_modified_time else None,
        "page_count": doc.page_count,
        "fonts_used": doc.fonts_used or [],
    }

    return DocumentPreview(
        id=doc.id, file_name=doc.file_name, company_name=doc.company_name,
        text_preview=preview_text, text_length=doc.text_length, metadata=metadata,
    )


@router.post("/reparse/{doc_id}")
async def reparse_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    try:
        ext = f".{doc.file_type}" if doc.file_type else os.path.splitext(doc.file_name)[1]
        parsed_data = _parse_document(doc.file_path, ext)
        _apply_parsed_data(doc, parsed_data)
        doc.parsed = 1
        doc.parse_error = None
        await db.commit()
        return {"message": "解析成功", "doc_id": doc_id, "text_length": doc.text_length}
    except Exception as e:
        doc.parsed = 2
        doc.parse_error = str(e)[:500]
        await db.commit()
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    await db.delete(doc)
    await db.commit()
    return {"message": "文档已删除", "id": doc_id}


# ========== Helper Functions ==========

def _parse_document(file_path: str, ext: str) -> dict:
    ext = ext.lower()
    if ext in [".pdf"]:
        return PDFParser.parse(file_path)
    elif ext in [".docx"]:
        return DocxParser.parse(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _apply_parsed_data(doc: Document, data: dict):
    meta = data.get("metadata", {})
    doc.full_text = data.get("full_text") or data.get("text") or ""
    doc.text_length = len(doc.full_text)
    doc.page_count = data.get("page_count", 0)
    doc.fonts_used = data.get("fonts", [])
    doc.format_info = data.get("format_info", {})

    doc.meta_author = meta.get("author", "")
    doc.meta_company = meta.get("company", "")
    doc.meta_last_modified_by = meta.get("last_modified_by", "")
    doc.meta_producer = meta.get("producer", "")
    doc.meta_creator = meta.get("creator") or meta.get("application", "")
    doc.meta_software_version = meta.get("software_version") or meta.get("app_version", "")

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
                dt = None
                if isinstance(ts, str) and ts.strip():
                    if ts.startswith("D:"):
                        ts_clean = ts[2:16].ljust(14, '0')
                        dt = datetime.strptime(ts_clean, "%Y%m%d%H%M%S")
                    else:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                elif hasattr(ts, 'year'):
                    dt = ts
                if dt is not None:
                    if dt.tzinfo is not None:
                        dt = dt.replace(tzinfo=None)
                    setattr(doc, field, dt)
            except Exception as e:
                logger.warning(f"时间解析失败 ({field}={ts}): {e}")

    doc.meta_extra = {k: v for k, v in meta.items()
                      if k not in ["author", "company", "last_modified_by", "producer",
                                   "creator", "software_version", "created_time", "modified_time",
                                   "created_date", "modified_date", "application", "app_version"]}
