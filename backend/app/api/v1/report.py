"""报告导出 API — 含审计日志"""
import os
import tempfile
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_user, get_client_ip
from app.models.models import Project, Document, AnalysisResult
from app.services.report.excel_report import ExcelReportGenerator
from app.services.report.pdf_report import PDFReportGenerator
from app.services.audit import log_action

router = APIRouter()


def _orm_to_dict(obj):
    """Convert a SQLAlchemy ORM object to a plain dict"""
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _build_risk_summary(results):
    """Build risk_summary dict with dimension_scores from result ORM objects"""
    dimension_scores = {}
    for r in results:
        atype = r.analysis_type
        score = r.score or 0.0
        if atype not in dimension_scores or score > dimension_scores[atype]:
            dimension_scores[atype] = score
    return {"dimension_scores": dimension_scores}


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
    current_user=Depends(get_current_user),
):
    """导出 Excel 分析报告"""
    project, documents, results = await _get_report_data(project_id, db)

    await log_action(db, action="export_excel", resource_type="report", resource_id=project_id,
                   user_id=current_user.get("sub") if current_user else None,
                   username=current_user.get("username") if current_user else None,
                   ip_address=get_client_ip(request) if request else None)
    await db.commit()

    project_dict = _orm_to_dict(project)
    project_dict["document_count"] = len(documents)
    documents_list = [_orm_to_dict(d) for d in documents]
    results_list = [_orm_to_dict(r) for r in results]
    risk_summary = _build_risk_summary(results)

    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    try:
        buf = ExcelReportGenerator.generate(project_dict, documents_list, results_list, risk_summary)
        with open(tmp.name, "wb") as f:
            f.write(buf.read())
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
    current_user=Depends(get_current_user),
):
    """导出 PDF 分析报告"""
    project, documents, results = await _get_report_data(project_id, db)

    await log_action(db, action="export_pdf", resource_type="report", resource_id=project_id,
                   user_id=current_user.get("sub") if current_user else None,
                   username=current_user.get("username") if current_user else None,
                   ip_address=get_client_ip(request) if request else None)
    await db.commit()

    project_dict = _orm_to_dict(project)
    project_dict["document_count"] = len(documents)
    documents_list = [_orm_to_dict(d) for d in documents]
    results_list = [_orm_to_dict(r) for r in results]
    risk_summary = _build_risk_summary(results)

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    try:
        buf = PDFReportGenerator.generate(project_dict, documents_list, results_list, risk_summary)
        with open(tmp.name, "wb") as f:
            f.write(buf.read())
        return FileResponse(
            tmp.name,
            media_type="application/pdf",
            filename=f"串标分析报告_{project.name}.pdf",
        )
    except Exception as e:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise HTTPException(status_code=500, detail=f"报告生成失败: {str(e)}")
