"""元数据比对检测引擎 — 检测文档元信息异常关联"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.core.config import settings


class MetadataDetector:
    """
    元数据检测器
    - 作者/公司一致性
    - 创建/修改时间聚集
    - 软件版本一致性
    - Producer/Creator 一致性
    """

    @staticmethod
    def compare_pair(meta_a: Dict[str, Any], meta_b: Dict[str, Any],
                     company_a: str = "", company_b: str = "") -> Dict[str, Any]:
        """比对两份文档的元数据"""
        alerts = []
        score = 0.0
        max_score = 0.0

        # 1. Author 比对 (权重: 0.25)
        max_score += 0.25
        author_result = MetadataDetector._check_field_match(
            meta_a.get("author", ""), meta_b.get("author", ""),
            "文档作者(Author)"
        )
        if author_result["match"]:
            score += 0.25
            alerts.append(author_result)

        # 2. Last Modified By 比对 (权重: 0.2)
        max_score += 0.2
        modifier_result = MetadataDetector._check_field_match(
            meta_a.get("last_modified_by", ""), meta_b.get("last_modified_by", ""),
            "最后修改人(Last Modified By)"
        )
        if modifier_result["match"]:
            score += 0.2
            alerts.append(modifier_result)

        # 3. Company 比对 (权重: 0.15)
        max_score += 0.15
        company_meta_a = meta_a.get("company", "")
        company_meta_b = meta_b.get("company", "")
        if company_meta_a and company_meta_b and company_meta_a == company_meta_b:
            # 如果 company 一致但投标单位不同，风险更高
            if company_a and company_b and company_a != company_b:
                score += 0.15
                alerts.append({
                    "field": "文档公司属性(Company)",
                    "value_a": company_meta_a,
                    "value_b": company_meta_b,
                    "match": True,
                    "severity": "high",
                    "note": f"不同投标人({company_a} vs {company_b})文档的Company属性一致"
                })

        # 4. Creator/Producer 比对 (权重: 0.1)
        max_score += 0.1
        creator_a = f"{meta_a.get('creator', '')} {meta_a.get('producer', '')}".strip()
        creator_b = f"{meta_b.get('creator', '')} {meta_b.get('producer', '')}".strip()
        if creator_a and creator_b and creator_a == creator_b:
            score += 0.05  # 相同软件较常见，较低权重
            alerts.append({
                "field": "创建软件(Creator/Producer)",
                "value_a": creator_a,
                "value_b": creator_b,
                "match": True,
                "severity": "low",
            })

        # 5. Software Version 精确匹配 (权重: 0.1)
        max_score += 0.1
        sw_a = meta_a.get("software_version", "")
        sw_b = meta_b.get("software_version", "")
        if sw_a and sw_b and sw_a == sw_b:
            score += 0.05
            alerts.append({
                "field": "软件版本(Software Version)",
                "value_a": sw_a,
                "value_b": sw_b,
                "match": True,
                "severity": "info",
            })

        # 6. 时间戳聚集检测 (权重: 0.2)
        max_score += 0.2
        time_result = MetadataDetector._check_timestamp_cluster(meta_a, meta_b)
        if time_result["is_clustered"]:
            score += 0.2
            alerts.append(time_result)

        return {
            "score": round(score, 4),
            "max_possible": round(max_score, 4),
            "normalized_score": round(score / max_score, 4) if max_score > 0 else 0.0,
            "alert_count": len(alerts),
            "alerts": alerts,
        }

    @staticmethod
    def batch_compare(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量比对多份文档的元数据
        documents: [{"id": ..., "company": ..., "metadata": {...}}]
        """
        results = []
        n = len(documents)
        for i in range(n):
            for j in range(i + 1, n):
                result = MetadataDetector.compare_pair(
                    documents[i]["metadata"],
                    documents[j]["metadata"],
                    documents[i].get("company", ""),
                    documents[j].get("company", ""),
                )
                result["doc_a_id"] = documents[i]["id"]
                result["doc_b_id"] = documents[j]["id"]
                result["company_a"] = documents[i].get("company", "")
                result["company_b"] = documents[j].get("company", "")
                results.append(result)
        return results

    @staticmethod
    def detect_timestamp_cluster(documents: List[Dict[str, Any]],
                                  threshold_minutes: int = None) -> Dict[str, Any]:
        """检测多份文档的时间戳是否异常聚集"""
        threshold = threshold_minutes or settings.TIMESTAMP_DIFF_MINUTES
        times = []

        for doc in documents:
            meta = doc.get("metadata", {})
            for field in ["created_time", "modified_time"]:
                ts = meta.get(field)
                if ts:
                    try:
                        if isinstance(ts, str):
                            dt = datetime.fromisoformat(ts)
                        else:
                            dt = ts
                        times.append({
                            "doc_id": doc["id"],
                            "company": doc.get("company", ""),
                            "field": field,
                            "time": dt,
                        })
                    except Exception:
                        pass

        if len(times) < 2:
            return {"is_clustered": False, "clusters": []}

        # Sort by time
        times.sort(key=lambda x: x["time"])

        # Find clusters (时间差 < threshold)
        clusters = []
        current_cluster = [times[0]]

        for k in range(1, len(times)):
            diff = (times[k]["time"] - times[k-1]["time"]).total_seconds() / 60
            if diff <= threshold:
                current_cluster.append(times[k])
            else:
                if len(current_cluster) >= 2:
                    clusters.append(current_cluster)
                current_cluster = [times[k]]

        if len(current_cluster) >= 2:
            clusters.append(current_cluster)

        # Format clusters
        formatted_clusters = []
        for cluster in clusters:
            companies = list(set(t["company"] for t in cluster if t["company"]))
            if len(companies) >= 2:  # Only flag if different companies
                formatted_clusters.append({
                    "companies": companies,
                    "time_range": {
                        "start": cluster[0]["time"].isoformat(),
                        "end": cluster[-1]["time"].isoformat(),
                        "span_minutes": round((cluster[-1]["time"] - cluster[0]["time"]).total_seconds() / 60, 1),
                    },
                    "entries": [
                        {
                            "company": t["company"],
                            "field": t["field"],
                            "time": t["time"].isoformat(),
                        }
                        for t in cluster
                    ],
                })

        return {
            "is_clustered": len(formatted_clusters) > 0,
            "cluster_count": len(formatted_clusters),
            "clusters": formatted_clusters,
            "severity": "high" if formatted_clusters else "none",
        }

    # ========== Internal Methods ==========

    @staticmethod
    def _check_field_match(value_a: str, value_b: str, field_name: str) -> Dict[str, Any]:
        """检查字段是否匹配"""
        match = False
        if value_a and value_b:
            # Exact match or very close
            match = value_a.strip() == value_b.strip()

        return {
            "field": field_name,
            "value_a": value_a,
            "value_b": value_b,
            "match": match,
            "severity": "high" if match and value_a else "none",
        }

    @staticmethod
    def _check_timestamp_cluster(meta_a: Dict, meta_b: Dict) -> Dict[str, Any]:
        """检查两份文档时间戳是否聚集"""
        threshold_minutes = settings.TIMESTAMP_DIFF_MINUTES

        for field in ["created_time", "modified_time"]:
            ts_a = meta_a.get(field)
            ts_b = meta_b.get(field)
            if ts_a and ts_b:
                try:
                    dt_a = datetime.fromisoformat(ts_a) if isinstance(ts_a, str) else ts_a
                    dt_b = datetime.fromisoformat(ts_b) if isinstance(ts_b, str) else ts_b
                    diff_minutes = abs((dt_a - dt_b).total_seconds()) / 60

                    if diff_minutes <= threshold_minutes:
                        return {
                            "field": f"时间戳聚集({field})",
                            "time_a": dt_a.isoformat(),
                            "time_b": dt_b.isoformat(),
                            "diff_minutes": round(diff_minutes, 1),
                            "threshold": threshold_minutes,
                            "is_clustered": True,
                            "severity": "high",
                        }
                except Exception:
                    pass

        return {"is_clustered": False, "severity": "none"}
