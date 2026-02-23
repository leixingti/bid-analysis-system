"""报告导出 API — 含审计日志"""
import os
import tempfile
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import settings
from app.core.security import require_auth, get_client_ip
from app.models.models import Project, Document, AnalysisResult
from app.services.report.excel_report import ExcelReportGenerator
from app.services.report.pdf_report import PDFReportGenerator
from app.services.audit import log_action

router = APIRouter()


async def _get_report_data(project_id: str, db: AsyncSession):
    """收集报告所需的全部数据"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    docs_result = await db.execute(
        select(Document).where(Document.project_id == project_id).order_by(Document.created_at)
    )
    documents = docs_result.scalars().all()

    ar_result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.project_id == project_id)
        .order_by(AnalysisResult.score.desc())
    )
    results = ar_result.scalars().all()

    return project, documents, results


@router.get("/excel/{project_id}")
async def export_excel(
    project_id: str, request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_auth),
):
    """导出 Excel 分析报告"""
    project, documents, results = await _get_report_data(project_id, db)

    await log_action(db, action="export_excel", resource_type="report", resource_id=project_id,
                   user_id=current_user.get("sub"), username=current_user.get("username"),
                   ip_address=get_client_ip(request) if request else None)
    await db.commit()

    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    try:
        ExcelReportGenerator.generate(project, documents, results, tmp.name)
        return FileResponse(
            tmp.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"串标分析报告_{project.name}.xlsx",
        )
    except Exception as e:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise HTTPException(status_code=500, detail=f"报告生成失败: {str(e)}")


@router.get("/pdf/{project_id}")
async def export_pdf(
    project_id: str, request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_auth),
):
    """导出 PDF 分析报告"""
    project, documents, results = await _get_report_data(project_id, db)

    await log_action(db, action="export_pdf", resource_type="report", resource_id=project_id,
                   user_id=current_user.get("sub"), username=current_user.get("username"),
                   ip_address=get_client_ip(request) if request else None)
    await db.commit()

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        PDFReportGenerator.generate(project, documents, results, tmp.name)
        return FileResponse(
            tmp.name,
            media_type="application/pdf",
            filename=f"串标分析报告_{project.name}.pdf",
        )
    except Exception as e:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise HTTPException(status_code=500, detail=f"报告生成失败: {str(e)}")
