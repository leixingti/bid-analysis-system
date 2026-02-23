"""检测分析 API — 异步任务 + 进度追踪 + 历史对比 + 可配置阈值"""
import asyncio
import traceback
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.core.database import get_db, async_session_factory
from app.core.config import settings
from app.core.security import require_auth, get_client_ip
from app.models.models import Project, Document, AnalysisResult, AnalysisHistory, ProjectStatus, RiskLevel
from app.schemas.schemas import (
    AnalysisResultResponse, AnalysisOverview, AnalysisConfig,
    AnalysisProgress, AnalysisHistoryResponse
)
from app.services.audit import log_action

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
logger = logging.getLogger(__name__)

# 全局进度缓存（进程内，无需Redis）
_progress_cache: dict = {}


def _score_to_risk(score: float) -> str:
    if score >= 0.7: return "critical"
    elif score >= 0.5: return "high"
    elif score >= 0.3: return "medium"
    return "low"


async def _run_analysis_task(project_id: str, history_id: str, config: dict, user_info: dict):
    """后台异步分析任务"""
    async with async_session_factory() as db:
        try:
            history = (await db.execute(
                select(AnalysisHistory).where(AnalysisHistory.id == history_id)
            )).scalar_one_or_none()
            if not history:
                return

            project = (await db.execute(
                select(Project).where(Project.id == project_id)
            )).scalar_one_or_none()
            if not project:
                history.status = "failed"
                history.error_message = "项目不存在"
                await db.commit()
                return

            # 获取已解析文档
            docs_result = await db.execute(
                select(Document).where(Document.project_id == project_id, Document.parsed == 1)
            )
            documents = docs_result.scalars().all()

            if len(documents) < 2:
                history.status = "failed"
                history.error_message = "至少需要2份已解析文档"
                await db.commit()
                return

            history.document_count = len(documents)

            # 清除旧分析结果
            old_results = await db.execute(
                select(AnalysisResult).where(AnalysisResult.project_id == project_id)
            )
            for old in old_results.scalars().all():
                await db.delete(old)
            await db.flush()

            # 准备文档数据
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
            sim_threshold = config.get("similarity_threshold", settings.SIMILARITY_THRESHOLD)
            ts_minutes = config.get("timestamp_diff_minutes", settings.TIMESTAMP_DIFF_MINUTES)
            total_steps = sum([
                config.get("enable_content_similarity", True),
                config.get("enable_metadata_match", True),
                config.get("enable_format_match", True),
                config.get("enable_timestamp_cluster", True),
                config.get("enable_entity_cross", True),
                config.get("enable_error_pattern", True),
                config.get("enable_price_analysis", True),
            ])
            step = 0

            def update_progress(step_name):
                nonlocal step
                step += 1
                pct = int(step / max(total_steps, 1) * 100)
                history.progress = pct
                history.current_step = step_name
                _progress_cache[history_id] = {"progress": pct, "current_step": step_name, "status": "running"}

            # ========== Phase 1 ==========

            # 4a. 文本相似度
            if config.get("enable_content_similarity", True):
                update_progress("文本相似度检测")
                try:
                    similarity_results = ContentSimilarityDetector.batch_compare(doc_data)
                    max_sim_score = 0.0
                    for sim in similarity_results:
                        score = sim["score"]
                        max_sim_score = max(max_sim_score, score)
                        if score > sim_threshold:
                            ar = AnalysisResult(
                                project_id=project_id, history_id=history_id,
                                analysis_type="content_similarity",
                                doc_id_a=sim["doc_a_id"], doc_id_b=sim["doc_b_id"],
                                company_a=sim["company_a"], company_b=sim["company_b"],
                                score=score, risk_level=_score_to_risk(score),
                                summary=f"文本相似度 {score:.1%}，超过阈值 {sim_threshold:.0%}",
                                details={**sim["details"], "similar_segments": sim.get("similar_segments", [])[:10]},
                            )
                            db.add(ar)
                            all_analysis_results.append(ar)
                    dimension_max_scores["content_similarity"] = max_sim_score
                except Exception as e:
                    logger.error(f"文本相似度检测失败: {e}")
                    dimension_max_scores["content_similarity"] = 0.0
                await db.flush()

            # 4b. 元数据比对
            if config.get("enable_metadata_match", True):
                update_progress("元数据关联检测")
                try:
                    metadata_results = MetadataDetector.batch_compare(doc_data)
                    max_meta_score = 0.0
                    for meta in metadata_results:
                        score = meta["normalized_score"]
                        max_meta_score = max(max_meta_score, score)
                        if meta["alert_count"] > 0:
                            ar = AnalysisResult(
                                project_id=project_id, history_id=history_id,
                                analysis_type="metadata_match",
                                doc_id_a=meta["doc_a_id"], doc_id_b=meta["doc_b_id"],
                                company_a=meta["company_a"], company_b=meta["company_b"],
                                score=score, risk_level=_score_to_risk(score),
                                summary=f"元数据匹配度 {score:.1%}，发现 {meta['alert_count']} 项异常",
                                details={"alerts": meta["alerts"]},
                            )
                            db.add(ar)
                            all_analysis_results.append(ar)
                    dimension_max_scores["metadata_match"] = max_meta_score
                except Exception as e:
                    logger.error(f"元数据检测失败: {e}")
                    dimension_max_scores["metadata_match"] = 0.0
                await db.flush()

            # 4c. 格式指纹
            if config.get("enable_format_match", True):
                update_progress("格式指纹检测")
                try:
                    format_results = FormatDetector.batch_compare(doc_data)
                    max_fmt_score = 0.0
                    for fmt in format_results:
                        score = fmt["score"]
                        max_fmt_score = max(max_fmt_score, score)
                        if fmt["alert_count"] > 0:
                            ar = AnalysisResult(
                                project_id=project_id, history_id=history_id,
                                analysis_type="format_match",
                                doc_id_a=fmt["doc_a_id"], doc_id_b=fmt["doc_b_id"],
                                company_a=fmt["company_a"], company_b=fmt["company_b"],
                                score=score, risk_level=_score_to_risk(score),
                                summary=f"格式指纹匹配度 {score:.1%}，发现 {fmt['alert_count']} 项一致",
                                details={"alerts": fmt["alerts"]},
                            )
                            db.add(ar)
                            all_analysis_results.append(ar)
                    dimension_max_scores["format_match"] = max_fmt_score
                except Exception as e:
                    logger.error(f"格式指纹检测失败: {e}")
                    dimension_max_scores["format_match"] = 0.0
                await db.flush()

            # 4d. 时间戳聚集
            if config.get("enable_timestamp_cluster", True):
                update_progress("时间戳聚集检测")
                try:
                    timestamp_result = MetadataDetector.detect_timestamp_cluster(doc_data, threshold_minutes=ts_minutes)
                    ts_score = 1.0 if timestamp_result["is_clustered"] else 0.0
                    dimension_max_scores["timestamp_cluster"] = ts_score
                    if timestamp_result["is_clustered"]:
                        ar = AnalysisResult(
                            project_id=project_id, history_id=history_id,
                            analysis_type="timestamp_cluster",
                            score=ts_score, risk_level="high",
                            summary=f"检测到 {timestamp_result['cluster_count']} 组时间戳聚集",
                            details=timestamp_result,
                        )
                        db.add(ar)
                        all_analysis_results.append(ar)
                except Exception as e:
                    logger.error(f"时间戳聚集检测失败: {e}")
                    dimension_max_scores["timestamp_cluster"] = 0.0
                await db.flush()

            # ========== Phase 2 ==========

            # 5. 实体交叉
            if config.get("enable_entity_cross", True):
                update_progress("实体交叉检测")
                try:
                    entity_result = EntityCrossDetector.batch_analyze(doc_data)
                    dimension_max_scores["entity_cross"] = entity_result["max_severity"]
                    for alert in entity_result.get("alerts", []):
                        if alert["severity_score"] > 0.1:
                            ar = AnalysisResult(
                                project_id=project_id, history_id=history_id,
                                analysis_type="entity_cross",
                                doc_id_a=alert["doc_id"], doc_id_b=alert["leaked_from_doc_id"],
                                company_a=alert["doc_company"], company_b=alert["leaked_from_company"],
                                score=alert["severity_score"],
                                risk_level=_score_to_risk(alert["severity_score"]),
                                summary=alert["summary"],
                                details={"hits": alert["hits"][:10]},
                            )
                            db.add(ar)
                            all_analysis_results.append(ar)
                except Exception as e:
                    logger.error(f"实体交叉检测失败: {e}")
                    dimension_max_scores["entity_cross"] = 0.0
                await db.flush()

            # 6. 错误模式
            if config.get("enable_error_pattern", True):
                update_progress("错误模式检测")
                try:
                    error_result = ErrorPatternDetector.compare_error_patterns(doc_data)
                    dimension_max_scores["error_pattern"] = error_result["max_severity"]
                    for alert in error_result.get("alerts", []):
                        if alert["severity_score"] > 0.1:
                            ar = AnalysisResult(
                                project_id=project_id, history_id=history_id,
                                analysis_type="error_pattern",
                                doc_id_a=alert.get("doc_a_id"), doc_id_b=alert.get("doc_b_id"),
                                company_a=alert.get("company_a", ""), company_b=alert.get("company_b", ""),
                                score=alert["severity_score"],
                                risk_level=_score_to_risk(alert["severity_score"]),
                                summary=alert["description"],
                                details={"type": alert["type"], "common_errors": alert.get("common_errors", []),
                                         "common_standards": alert.get("common_standards", []),
                                         "common_patterns": alert.get("common_patterns", [])},
                            )
                            db.add(ar)
                            all_analysis_results.append(ar)
                except Exception as e:
                    logger.error(f"错误模式检测失败: {e}")
                    dimension_max_scores["error_pattern"] = 0.0
                await db.flush()

            # 7. 报价分析
            if config.get("enable_price_analysis", True):
                update_progress("报价分析")
                try:
                    price_result = PriceAnalysisDetector.full_price_analysis(doc_data)
                    dimension_max_scores["price_analysis"] = price_result.get("max_severity", 0.0)
                    for alert in price_result.get("alerts", []):
                        if alert["severity_score"] > 0.1:
                            ar = AnalysisResult(
                                project_id=project_id, history_id=history_id,
                                analysis_type="price_analysis",
                                score=alert["severity_score"],
                                risk_level=_score_to_risk(alert["severity_score"]),
                                summary=alert["description"],
                                details={"alert_type": alert["type"],
                                         "arithmetic": price_result.get("arithmetic_sequence", {}),
                                         "geometric": price_result.get("geometric_sequence", {}),
                                         "fixed_coeff": price_result.get("fixed_coefficient", {}),
                                         "cluster": price_result.get("price_cluster", {})},
                            )
                            db.add(ar)
                            all_analysis_results.append(ar)
                except Exception as e:
                    logger.error(f"报价分析失败: {e}")
                    dimension_max_scores["price_analysis"] = 0.0
                await db.flush()

            # ========== 综合评分 ==========
            risk_result = RiskEngine.compute_project_risk([
                {"type": dim, "score": score,
                 "pairs": [{"score": r.score, "company_a": r.company_a or "", "company_b": r.company_b or ""}
                           for r in all_analysis_results if r.analysis_type == dim]}
                for dim, score in dimension_max_scores.items()
            ])

            project.risk_score = risk_result["risk_score"]
            project.risk_level = risk_result["risk_level"]
            project.status = ProjectStatus.COMPLETED

            history.status = "completed"
            history.progress = 100
            history.current_step = "完成"
            history.risk_score = risk_result["risk_score"]
            history.risk_level = risk_result["risk_level"]
            history.total_alerts = len(all_analysis_results)
            history.dimension_scores = dimension_max_scores
            history.completed_at = datetime.utcnow()

            _progress_cache[history_id] = {"progress": 100, "current_step": "完成", "status": "completed"}

            await log_action(db, action="analysis_complete", resource_type="project", resource_id=project_id,
                           user_id=user_info.get("sub"), username=user_info.get("username"),
                           details={"alerts": len(all_analysis_results), "risk_score": risk_result["risk_score"]})

            await db.commit()
            logger.info(f"✅ 分析完成: project={project_id}, alerts={len(all_analysis_results)}, score={risk_result['risk_score']:.1f}")

        except Exception as e:
            logger.error(f"❌ 分析任务异常: {e}\n{traceback.format_exc()}")
            try:
                history.status = "failed"
                history.error_message = str(e)[:500]
                history.completed_at = datetime.utcnow()
                project.status = ProjectStatus.COMPLETED  # 不卡在analyzing
                _progress_cache[history_id] = {"progress": 0, "current_step": f"失败: {str(e)[:100]}", "status": "failed"}
                await db.commit()
            except:
                pass


# ==================== API Routes ====================

@router.post("/run/{project_id}")
async def run_analysis(
    project_id: str,
    config: Optional[AnalysisConfig] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_auth),
):
    """启动异步分析任务（后台执行）"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 检查是否有正在运行的分析
    running = await db.execute(
        select(AnalysisHistory).where(
            AnalysisHistory.project_id == project_id,
            AnalysisHistory.status == "running"
        )
    )
    if running.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该项目有正在进行的分析任务")

    doc_count = (await db.execute(
        select(func.count()).select_from(Document).where(Document.project_id == project_id, Document.parsed == 1)
    )).scalar() or 0
    if doc_count < 2:
        raise HTTPException(status_code=400, detail="至少需要2份已解析文档才能进行分析")

    # 版本号
    latest_version = (await db.execute(
        select(func.max(AnalysisHistory.version)).where(AnalysisHistory.project_id == project_id)
    )).scalar() or 0

    # 使用项目级配置 或 请求参数 或 系统默认
    analysis_cfg = {}
    if config:
        analysis_cfg = config.model_dump()
    elif project.analysis_config:
        analysis_cfg = project.analysis_config
    else:
        analysis_cfg = AnalysisConfig().model_dump()

    # 创建历史记录
    history = AnalysisHistory(
        project_id=project_id,
        version=latest_version + 1,
        status="running",
        config_snapshot=analysis_cfg,
        document_count=doc_count,
        triggered_by=current_user.get("sub"),
    )
    db.add(history)

    project.status = ProjectStatus.ANALYZING
    _progress_cache[history.id] = {"progress": 0, "current_step": "初始化...", "status": "running"}

    await log_action(db, action="analysis_start", resource_type="project", resource_id=project_id,
                   user_id=current_user.get("sub"), username=current_user.get("username"),
                   details={"version": latest_version + 1},
                   ip_address=get_client_ip(request) if request else None)

    await db.commit()
    await db.refresh(history)

    # 启动后台任务
    background_tasks.add_task(_run_analysis_task, project_id, history.id, analysis_cfg, current_user)

    return {
        "message": "分析任务已启动",
        "history_id": history.id,
        "version": history.version,
        "status": "running",
    }


@router.get("/progress/{history_id}", response_model=AnalysisProgress)
async def get_analysis_progress(history_id: str, db: AsyncSession = Depends(get_db)):
    """查询分析进度"""
    # 先查缓存
    cached = _progress_cache.get(history_id)

    result = await db.execute(select(AnalysisHistory).where(AnalysisHistory.id == history_id))
    history = result.scalar_one_or_none()
    if not history:
        raise HTTPException(status_code=404, detail="分析记录不存在")

    return AnalysisProgress(
        history_id=history.id,
        status=cached["status"] if cached else history.status,
        progress=cached["progress"] if cached else history.progress,
        current_step=cached["current_step"] if cached else history.current_step,
        started_at=history.started_at,
        completed_at=history.completed_at,
        error_message=history.error_message,
    )


@router.get("/history/{project_id}", response_model=list[AnalysisHistoryResponse])
async def get_analysis_history(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取项目分析历史"""
    result = await db.execute(
        select(AnalysisHistory).where(AnalysisHistory.project_id == project_id)
        .order_by(AnalysisHistory.version.desc()).limit(20)
    )
    histories = result.scalars().all()
    return [AnalysisHistoryResponse(**{c.name: getattr(h, c.name) for c in h.__table__.columns}) for h in histories]


@router.get("/results/{project_id}", response_model=AnalysisOverview)
async def get_analysis_results(
    project_id: str,
    analysis_type: Optional[str] = None,
    history_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取项目分析结果（支持按历史版本查询）"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    query = select(AnalysisResult).where(AnalysisResult.project_id == project_id)
    if analysis_type:
        query = query.where(AnalysisResult.analysis_type == analysis_type)
    if history_id:
        query = query.where(AnalysisResult.history_id == history_id)
    query = query.order_by(AnalysisResult.score.desc())

    ar_result = await db.execute(query)
    analysis_results = ar_result.scalars().all()

    doc_count = (await db.execute(
        select(func.count()).select_from(Document).where(Document.project_id == project_id, Document.parsed == 1)
    )).scalar() or 0

    result_responses = [
        AnalysisResultResponse(**{c.name: getattr(ar, c.name) for c in ar.__table__.columns})
        for ar in analysis_results
    ]

    return AnalysisOverview(
        project_id=project_id, project_name=project.name,
        total_documents=doc_count, total_alerts=len(analysis_results),
        risk_score=project.risk_score or 0.0, risk_level=project.risk_level or "low",
        results=result_responses,
    )


@router.post("/config/{project_id}")
async def update_analysis_config(
    project_id: str, config: AnalysisConfig,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_auth),
):
    """更新项目分析参数"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project.analysis_config = config.model_dump()
    await db.commit()
    return {"message": "分析参数已更新", "config": config.model_dump()}


@router.get("/config/{project_id}", response_model=AnalysisConfig)
async def get_analysis_config(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取项目分析参数"""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if project.analysis_config:
        return AnalysisConfig(**project.analysis_config)
    return AnalysisConfig()
