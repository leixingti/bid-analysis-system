"""检测分析 API — 集成全部 Phase 1+2 检测引擎"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.core.config import settings
from app.models.models import Project, Document, AnalysisResult, ProjectStatus, RiskLevel
from app.schemas.schemas import AnalysisResultResponse, AnalysisOverview

# Phase 1 engines
from app.services.detection.content_similarity import ContentSimilarityDetector
from app.services.detection.metadata_detector import MetadataDetector
from app.services.detection.format_detector import FormatDetector

# Phase 2 engines
from app.services.detection.entity_cross import EntityCrossDetector
from app.services.detection.error_pattern import ErrorPatternDetector
from app.services.detection.price_analysis import PriceAnalysisDetector

from app.services.risk.risk_engine import RiskEngine

router = APIRouter()


@router.post("/run/{project_id}", response_model=AnalysisOverview)
async def run_analysis(project_id: str, db: AsyncSession = Depends(get_db)):
    """
    对项目下所有文档执行全维度串标/围标分析

    Phase 1 检测:
      1. 文本相似度 (SimHash + TF-IDF + Jaccard)
      2. 元数据比对 (Author, Company, 时间戳聚集)
      3. 格式指纹比对 (字体、页边距、字号)

    Phase 2 检测:
      4. NER 实体交叉 (A公司标书出现B公司人员/电话)
      5. 错误模式识别 (共性错别字、标点、过期标准)
      6. 报价数学序列 (等差/等比/固定系数/价格围堵)
      7. 分项构成分析 (费用比例异常一致)
    """
    # 1. 验证项目
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 2. 获取已解析文档
    doc_result = await db.execute(
        select(Document).where(Document.project_id == project_id, Document.parsed == 1)
    )
    documents = doc_result.scalars().all()

    if len(documents) < 2:
        raise HTTPException(status_code=400, detail="至少需要2份已解析文档才能进行分析")

    # 更新项目状态
    project.status = ProjectStatus.ANALYZING
    await db.flush()

    # 清除旧分析结果
    old_results = await db.execute(
        select(AnalysisResult).where(AnalysisResult.project_id == project_id)
    )
    for old in old_results.scalars().all():
        await db.delete(old)
    await db.flush()

    # 3. 准备文档数据
    doc_data = []
    for doc in documents:
        doc_data.append({
            "id": doc.id,
            "company": doc.company_name or doc.file_name,
            "text": doc.full_text or "",
            "metadata": {
                "author": doc.meta_author or "",
                "company": doc.meta_company or "",
                "last_modified_by": doc.meta_last_modified_by or "",
                "created_time": doc.meta_created_time.isoformat() if doc.meta_created_time else None,
                "modified_time": doc.meta_modified_time.isoformat() if doc.meta_modified_time else None,
                "producer": doc.meta_producer or "",
                "creator": doc.meta_creator or "",
                "software_version": doc.meta_software_version or "",
            },
            "format_info": doc.format_info or {},
        })

    all_analysis_results = []
    dimension_max_scores = {}

    # =====================================================
    # Phase 1: 基础检测
    # =====================================================

    # 4a. 文本相似度检测
    similarity_results = ContentSimilarityDetector.batch_compare(doc_data)
    max_sim_score = 0.0
    for sim in similarity_results:
        score = sim["score"]
        max_sim_score = max(max_sim_score, score)
        if score > settings.SIMILARITY_THRESHOLD:
            ar = AnalysisResult(
                project_id=project_id, analysis_type="content_similarity",
                doc_id_a=sim["doc_a_id"], doc_id_b=sim["doc_b_id"],
                company_a=sim["company_a"], company_b=sim["company_b"],
                score=score, risk_level=_score_to_risk(score),
                summary=f"文本相似度 {score:.1%}，超过阈值 {settings.SIMILARITY_THRESHOLD:.0%}",
                details={**sim["details"], "similar_segments": sim.get("similar_segments", [])[:10]},
            )
            db.add(ar)
            all_analysis_results.append(ar)
    dimension_max_scores["content_similarity"] = max_sim_score

    # 4b. 元数据比对
    metadata_results = MetadataDetector.batch_compare(doc_data)
    max_meta_score = 0.0
    for meta in metadata_results:
        score = meta["normalized_score"]
        max_meta_score = max(max_meta_score, score)
        if meta["alert_count"] > 0:
            ar = AnalysisResult(
                project_id=project_id, analysis_type="metadata_match",
                doc_id_a=meta["doc_a_id"], doc_id_b=meta["doc_b_id"],
                company_a=meta["company_a"], company_b=meta["company_b"],
                score=score, risk_level=_score_to_risk(score),
                summary=f"元数据匹配度 {score:.1%}，发现 {meta['alert_count']} 项异常",
                details={"alerts": meta["alerts"]},
            )
            db.add(ar)
            all_analysis_results.append(ar)
    dimension_max_scores["metadata_match"] = max_meta_score

    # 4c. 格式指纹比对
    format_results = FormatDetector.batch_compare(doc_data)
    max_fmt_score = 0.0
    for fmt in format_results:
        score = fmt["score"]
        max_fmt_score = max(max_fmt_score, score)
        if fmt["alert_count"] > 0:
            ar = AnalysisResult(
                project_id=project_id, analysis_type="format_match",
                doc_id_a=fmt["doc_a_id"], doc_id_b=fmt["doc_b_id"],
                company_a=fmt["company_a"], company_b=fmt["company_b"],
                score=score, risk_level=_score_to_risk(score),
                summary=f"格式指纹匹配度 {score:.1%}，发现 {fmt['alert_count']} 项一致",
                details={"alerts": fmt["alerts"]},
            )
            db.add(ar)
            all_analysis_results.append(ar)
    dimension_max_scores["format_match"] = max_fmt_score

    # 4d. 时间戳聚集检测
    timestamp_result = MetadataDetector.detect_timestamp_cluster(doc_data)
    ts_score = 1.0 if timestamp_result["is_clustered"] else 0.0
    dimension_max_scores["timestamp_cluster"] = ts_score
    if timestamp_result["is_clustered"]:
        ar = AnalysisResult(
            project_id=project_id, analysis_type="timestamp_cluster",
            score=ts_score, risk_level="high",
            summary=f"检测到 {timestamp_result['cluster_count']} 组时间戳聚集",
            details=timestamp_result,
        )
        db.add(ar)
        all_analysis_results.append(ar)

    # =====================================================
    # Phase 2: 深度检测
    # =====================================================

    # 5. NER 实体交叉检测
    entity_result = EntityCrossDetector.batch_analyze(doc_data)
    dimension_max_scores["entity_cross"] = entity_result["max_severity"]
    for alert in entity_result.get("alerts", []):
        if alert["severity_score"] > 0.1:
            ar = AnalysisResult(
                project_id=project_id, analysis_type="entity_cross",
                doc_id_a=alert["doc_id"],
                doc_id_b=alert["leaked_from_doc_id"],
                company_a=alert["doc_company"],
                company_b=alert["leaked_from_company"],
                score=alert["severity_score"],
                risk_level=_score_to_risk(alert["severity_score"]),
                summary=alert["summary"],
                details={"hits": alert["hits"][:10]},
            )
            db.add(ar)
            all_analysis_results.append(ar)

    # 6. 错误模式识别
    error_result = ErrorPatternDetector.compare_error_patterns(doc_data)
    dimension_max_scores["error_pattern"] = error_result["max_severity"]
    for alert in error_result.get("alerts", []):
        if alert["severity_score"] > 0.1:
            ar = AnalysisResult(
                project_id=project_id, analysis_type="error_pattern",
                doc_id_a=alert.get("doc_a_id"),
                doc_id_b=alert.get("doc_b_id"),
                company_a=alert.get("company_a", ""),
                company_b=alert.get("company_b", ""),
                score=alert["severity_score"],
                risk_level=_score_to_risk(alert["severity_score"]),
                summary=alert["description"],
                details={
                    "type": alert["type"],
                    "common_errors": alert.get("common_errors", []),
                    "common_standards": alert.get("common_standards", []),
                    "common_patterns": alert.get("common_patterns", []),
                },
            )
            db.add(ar)
            all_analysis_results.append(ar)

    # 7. 报价分析（数学序列 + 分项构成）
    price_result = PriceAnalysisDetector.full_price_analysis(doc_data)
    dimension_max_scores["price_analysis"] = price_result.get("max_severity", 0.0)
    for alert in price_result.get("alerts", []):
        if alert["severity_score"] > 0.1:
            ar = AnalysisResult(
                project_id=project_id, analysis_type="price_analysis",
                score=alert["severity_score"],
                risk_level=_score_to_risk(alert["severity_score"]),
                summary=alert["description"],
                details={
                    "alert_type": alert["type"],
                    "arithmetic": price_result.get("arithmetic_sequence", {}),
                    "geometric": price_result.get("geometric_sequence", {}),
                    "fixed_coeff": price_result.get("fixed_coefficient", {}),
                    "cluster": price_result.get("price_cluster", {}),
                },
            )
            db.add(ar)
            all_analysis_results.append(ar)

    # =====================================================
    # 8. 综合风险评分
    # =====================================================
    risk_result = RiskEngine.compute_project_risk([
        {
            "type": dim, "score": score,
            "pairs": [
                {"score": r.score, "company_a": r.company_a or "", "company_b": r.company_b or ""}
                for r in all_analysis_results if r.analysis_type == dim
            ],
        }
        for dim, score in dimension_max_scores.items()
    ])

    project.risk_score = risk_result["risk_score"]
    project.risk_level = risk_result["risk_level"]
    project.status = ProjectStatus.COMPLETED
    await db.commit()

    # Build response
    result_responses = []
    for ar in all_analysis_results:
        await db.refresh(ar)
        result_responses.append(AnalysisResultResponse(
            **{c.name: getattr(ar, c.name) for c in ar.__table__.columns}
        ))

    return AnalysisOverview(
        project_id=project_id,
        project_name=project.name,
        total_documents=len(documents),
        total_alerts=len(all_analysis_results),
        risk_score=risk_result["risk_score"],
        risk_level=risk_result["risk_level"],
        analysis_summary={
            "dimension_scores": dimension_max_scores,
            "risk_details": risk_result,
            "phase2_summary": {
                "entity_cross_alerts": entity_result["total_alerts"],
                "error_pattern_alerts": error_result["total_alerts"],
                "price_alerts": len(price_result.get("alerts", [])),
            },
        },
        results=result_responses,
    )


@router.get("/results/{project_id}", response_model=AnalysisOverview)
async def get_analysis_results(
    project_id: str,
    analysis_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取项目分析结果"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    query = select(AnalysisResult).where(AnalysisResult.project_id == project_id)
    if analysis_type:
        query = query.where(AnalysisResult.analysis_type == analysis_type)
    query = query.order_by(AnalysisResult.score.desc())

    ar_result = await db.execute(query)
    analysis_results = ar_result.scalars().all()

    doc_count_result = await db.execute(
        select(Document).where(Document.project_id == project_id, Document.parsed == 1)
    )
    doc_count = len(doc_count_result.scalars().all())

    result_responses = [
        AnalysisResultResponse(**{c.name: getattr(ar, c.name) for c in ar.__table__.columns})
        for ar in analysis_results
    ]

    return AnalysisOverview(
        project_id=project_id, project_name=project.name,
        total_documents=doc_count, total_alerts=len(analysis_results),
        risk_score=project.risk_score, risk_level=project.risk_level,
        results=result_responses,
    )


def _score_to_risk(score: float) -> str:
    if score >= 0.7: return "critical"
    elif score >= 0.5: return "high"
    elif score >= 0.3: return "medium"
    return "low"
