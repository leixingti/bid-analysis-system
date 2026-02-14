"""综合风险评分引擎 — 多维度加权评分 (Phase 1+2)"""
from typing import Dict, Any, List
from app.core.config import settings


class RiskEngine:
    """
    综合风险评分引擎
    将各维度检测结果加权计算为 0-100 的综合风险评分
    """

    # 各检测维度权重 (Phase 1 + Phase 2)
    WEIGHTS = {
        "content_similarity": 0.20,   # 文本相似度
        "metadata_match": 0.12,       # 元数据匹配
        "format_match": 0.08,         # 格式指纹
        "timestamp_cluster": 0.10,    # 时间戳聚集
        "entity_cross": 0.20,         # NER 实体交叉 (Phase 2)
        "error_pattern": 0.10,        # 错误模式识别 (Phase 2)
        "price_analysis": 0.20,       # 报价分析 (Phase 2)
    }

    RISK_THRESHOLDS = {
        "critical": 0.7,
        "high": 0.5,
        "medium": 0.3,
        "low": 0.0,
    }

    @staticmethod
    def compute_project_risk(analysis_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        计算项目综合风险评分

        analysis_results: [{
            "type": "content_similarity" | "metadata_match" | "entity_cross" | ...,
            "score": 0.0-1.0,
            "pairs": [...]
        }]
        """
        dimension_scores = {}
        all_alerts = []

        for result in analysis_results:
            rtype = result.get("type", "")
            rscore = result.get("score", 0.0)
            dimension_scores[rtype] = rscore

            for pair in result.get("pairs", []):
                if pair.get("score", 0) > settings.SIMILARITY_THRESHOLD:
                    all_alerts.append({
                        "type": rtype,
                        "score": pair["score"],
                        "company_a": pair.get("company_a", ""),
                        "company_b": pair.get("company_b", ""),
                    })

        # Weighted score
        total_score = 0.0
        total_weight = 0.0
        for dim, weight in RiskEngine.WEIGHTS.items():
            if dim in dimension_scores:
                total_score += dimension_scores[dim] * weight
                total_weight += weight

        normalized_score = total_score / total_weight if total_weight > 0 else 0.0
        risk_score_100 = round(normalized_score * 100, 1)

        risk_level = "low"
        for level, threshold in sorted(RiskEngine.RISK_THRESHOLDS.items(),
                                        key=lambda x: x[1], reverse=True):
            if normalized_score >= threshold:
                risk_level = level
                break

        all_alerts.sort(key=lambda x: x["score"], reverse=True)

        return {
            "risk_score": risk_score_100,
            "risk_level": risk_level,
            "normalized_score": round(normalized_score, 4),
            "dimension_scores": dimension_scores,
            "weights_used": {k: v for k, v in RiskEngine.WEIGHTS.items() if k in dimension_scores},
            "alert_count": len(all_alerts),
            "top_alerts": all_alerts[:10],
            "summary": RiskEngine._generate_summary(risk_level, dimension_scores, all_alerts),
        }

    @staticmethod
    def compute_pair_risk(similarity_score: float, metadata_score: float,
                          format_score: float) -> Dict[str, Any]:
        """计算两份文档之间的风险"""
        scores = {
            "content_similarity": similarity_score,
            "metadata_match": metadata_score,
            "format_match": format_score,
        }
        weighted = sum(scores.get(d, 0) * w for d, w in RiskEngine.WEIGHTS.items() if d in scores)
        total_w = sum(w for d, w in RiskEngine.WEIGHTS.items() if d in scores)
        normalized = weighted / total_w if total_w > 0 else 0.0

        risk_level = "low"
        for level, threshold in sorted(RiskEngine.RISK_THRESHOLDS.items(),
                                        key=lambda x: x[1], reverse=True):
            if normalized >= threshold:
                risk_level = level
                break

        return {"risk_score": round(normalized * 100, 1), "risk_level": risk_level, "dimension_scores": scores}

    @staticmethod
    def _generate_summary(risk_level: str, scores: Dict[str, float], alerts: List[Dict]) -> str:
        prefixes = {
            "critical": "⚠️ 极高风险：存在明显串标/围标嫌疑",
            "high": "🔴 高风险：检测到多项异常指标",
            "medium": "🟡 中等风险：部分指标异常需关注",
            "low": "🟢 低风险：未检测到明显异常",
        }
        prefix = prefixes.get(risk_level, prefixes["low"])

        details = []
        if scores.get("content_similarity", 0) > 0.2:
            details.append(f"文本相似度异常({scores['content_similarity']:.0%})")
        if scores.get("metadata_match", 0) > 0.3:
            details.append(f"元数据关联异常({scores['metadata_match']:.0%})")
        if scores.get("entity_cross", 0) > 0.3:
            details.append(f"发现实体信息交叉泄露({scores['entity_cross']:.0%})")
        if scores.get("error_pattern", 0) > 0.3:
            details.append(f"发现共性错误模式({scores['error_pattern']:.0%})")
        if scores.get("price_analysis", 0) > 0.3:
            details.append(f"报价数据存在数学规律({scores['price_analysis']:.0%})")
        if scores.get("format_match", 0) > 0.5:
            details.append(f"格式指纹高度一致({scores['format_match']:.0%})")
        if scores.get("timestamp_cluster", 0) > 0.5:
            details.append("文档时间戳异常聚集")

        if details:
            return f"{prefix}。{'; '.join(details)}。涉及 {len(alerts)} 条预警。"
        return prefix
