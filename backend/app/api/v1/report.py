"""报告导出 API — 支持 Excel / PDF 格式导出"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.models.models import Project, Document, AnalysisResult
from app.services.report.excel_report import ExcelReportGenerator
from app.services.report.pdf_report import PDFReportGenerator

router = APIRouter()


async def _get_report_data(project_id: str, db: AsyncSession):
    """获取项目报告所需数据"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    doc_result = await db.execute(
        select(Document).where(Document.project_id == project_id).order_by(Document.created_at)
    )
    documents = doc_result.scalars().all()

    ar_result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.project_id == project_id)
        .order_by(AnalysisResult.score.desc())
    )
    analysis_results = ar_result.scalars().all()

    # Build dicts
    project_dict = {c.name: getattr(project, c.name) for c in project.__table__.columns}
    project_dict["document_count"] = len(documents)
    # Ensure numeric fields are never None
    project_dict["risk_score"] = project_dict.get("risk_score") or 0.0
    project_dict["risk_level"] = project_dict.get("risk_level") or "low"

    doc_dicts = []
    for d in documents:
        dd = {c.name: getattr(d, c.name) for c in d.__table__.columns if c.name != "full_text"}
        # Convert datetime to string for serialization
        for key in ["meta_created_time", "meta_modified_time", "created_at"]:
            if dd.get(key) and hasattr(dd[key], "strftime"):
                dd[key] = dd[key].strftime("%Y-%m-%d %H:%M")
        doc_dicts.append(dd)

    result_dicts = []
    for ar in analysis_results:
        rd = {c.name: getattr(ar, c.name) for c in ar.__table__.columns}
        if rd.get("created_at") and hasattr(rd["created_at"], "strftime"):
            rd["created_at"] = rd["created_at"].strftime("%Y-%m-%d %H:%M")
        # Ensure numeric/string fields are never None
        rd["score"] = rd.get("score") or 0.0
        rd["risk_level"] = rd.get("risk_level") or "low"
        rd["summary"] = rd.get("summary") or ""
        rd["company_a"] = rd.get("company_a") or ""
        rd["company_b"] = rd.get("company_b") or ""
        rd["analysis_type"] = rd.get("analysis_type") or ""
        result_dicts.append(rd)

    # Build risk summary
    dimension_scores = {}
    for ar in analysis_results:
        t = ar.analysis_type
        if t not in dimension_scores or ar.score > dimension_scores[t]:
            dimension_scores[t] = ar.score

    risk_summary = {
        "risk_score": project.risk_score,
        "risk_level": project.risk_level,
        "dimension_scores": dimension_scores,
    }

    return project_dict, doc_dicts, result_dicts, risk_summary


@router.get("/excel/{project_id}")
async def export_excel(project_id: str, db: AsyncSession = Depends(get_db)):
    """导出 Excel 分析报告"""
    project_dict, doc_dicts, result_dicts, risk_summary = await _get_report_data(project_id, db)

    buf = ExcelReportGenerator.generate(project_dict, doc_dicts, result_dicts, risk_summary)

    filename = f"串标分析报告_{project_dict.get('name', 'report')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/pdf/{project_id}")
async def export_pdf(project_id: str, db: AsyncSession = Depends(get_db)):
    """导出 PDF 分析报告"""
    project_dict, doc_dicts, result_dicts, risk_summary = await _get_report_data(project_id, db)

    buf = PDFReportGenerator.generate(project_dict, doc_dicts, result_dicts, risk_summary)

    filename = f"串标分析报告_{project_dict.get('name', 'report')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
