"""风险预警 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.core.database import get_db
from app.models.models import Project, AnalysisResult
from app.schemas.schemas import RiskAlert

router = APIRouter()


@router.get("/alerts/{project_id}", response_model=List[RiskAlert])
async def get_risk_alerts(
    project_id: str,
    min_score: float = 0.2,
    db: AsyncSession = Depends(get_db)
):
    """获取项目风险预警列表"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    ar_result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.project_id == project_id, AnalysisResult.score >= min_score)
        .order_by(AnalysisResult.score.desc())
    )
    results = ar_result.scalars().all()

    alerts = []
    type_names = {
        "content_similarity": "文本内容雷同",
        "metadata_match": "元数据异常关联",
        "format_match": "格式指纹一致",
        "timestamp_cluster": "时间戳异常聚集",
        "entity_cross": "实体信息交叉泄露",
        "error_pattern": "错误模式一致",
        "price_analysis": "报价异常规律",
    }

    for ar in results:
        companies = []
        if ar.company_a:
            companies.append(ar.company_a)
        if ar.company_b:
            companies.append(ar.company_b)

        alerts.append(RiskAlert(
            alert_type=ar.analysis_type,
            risk_level=ar.risk_level,
            title=type_names.get(ar.analysis_type, ar.analysis_type),
            description=ar.summary or "",
            involved_companies=companies,
            score=ar.score,
            details=ar.details or {},
        ))

    return alerts


@router.get("/dashboard")
async def risk_dashboard(db: AsyncSession = Depends(get_db)):
    """风险总览看板数据"""
    projects_result = await db.execute(
        select(Project).order_by(Project.risk_score.desc()).limit(50)
    )
    projects = projects_result.scalars().all()

    dashboard = {
        "total_projects": len(projects),
        "risk_distribution": {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        },
        "top_risk_projects": [],
    }

    for p in projects:
        level = p.risk_level or "low"
        if level in dashboard["risk_distribution"]:
            dashboard["risk_distribution"][level] += 1

        if p.risk_score > 0:
            dashboard["top_risk_projects"].append({
                "id": p.id,
                "name": p.name,
                "risk_score": p.risk_score,
                "risk_level": p.risk_level,
                "status": p.status,
            })

    dashboard["top_risk_projects"] = dashboard["top_risk_projects"][:10]

    return dashboard
