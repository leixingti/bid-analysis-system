"""格式指纹检测引擎 — 检测排版样式一致性"""
from typing import Dict, Any, List


class FormatDetector:
    """
    格式数字指纹检测器
    - 字体一致性
    - 页面布局一致性
    - 页边距一致性
    """

    @staticmethod
    def compare_pair(format_a: Dict[str, Any], format_b: Dict[str, Any]) -> Dict[str, Any]:
        """比对两份文档的格式信息"""
        alerts = []
        score = 0.0
        checks = 0

        # 1. 字体完全一致
        fonts_a = set(format_a.get("fonts_used", []))
        fonts_b = set(format_b.get("fonts_used", []))
        if fonts_a and fonts_b:
            checks += 1
            if fonts_a == fonts_b:
                score += 1.0
                alerts.append({
                    "type": "font_match",
                    "description": "使用完全相同的字体集合",
                    "value_a": sorted(list(fonts_a)),
                    "value_b": sorted(list(fonts_b)),
                    "severity": "medium",
                })
            else:
                overlap = fonts_a & fonts_b
                ratio = len(overlap) / max(len(fonts_a | fonts_b), 1)
                if ratio > 0.8:
                    score += 0.6
                    alerts.append({
                        "type": "font_high_overlap",
                        "description": f"字体重合率 {ratio:.0%}",
                        "overlap": sorted(list(overlap)),
                        "severity": "low",
                    })

        # 2. 页面尺寸一致
        for dim in ["page_width", "page_height"]:
            val_a = format_a.get(dim)
            val_b = format_b.get(dim)
            if val_a and val_b:
                checks += 1
                if abs(val_a - val_b) < 0.01:
                    score += 0.5  # 页面尺寸一致较常见

        # 3. 页边距一致
        margins = ["left_margin", "right_margin", "top_margin", "bottom_margin"]
        margin_match_count = 0
        margin_total = 0
        for m in margins:
            val_a = format_a.get(m)
            val_b = format_b.get(m)
            if val_a is not None and val_b is not None:
                margin_total += 1
                if abs(val_a - val_b) < 0.01:
                    margin_match_count += 1

        if margin_total > 0:
            checks += 1
            margin_ratio = margin_match_count / margin_total
            if margin_ratio == 1.0 and margin_total >= 3:
                score += 1.0
                alerts.append({
                    "type": "margin_exact_match",
                    "description": "所有页边距完全一致",
                    "severity": "medium",
                })
            elif margin_ratio > 0.5:
                score += margin_ratio * 0.5

        # 4. 字号分布一致
        sizes_a = format_a.get("font_size_distribution") or format_a.get("font_sizes", [])
        sizes_b = format_b.get("font_size_distribution") or format_b.get("font_sizes", [])
        if sizes_a and sizes_b:
            checks += 1
            if isinstance(sizes_a, list) and isinstance(sizes_b, list):
                if sorted(sizes_a) == sorted(sizes_b):
                    score += 0.8
                    alerts.append({
                        "type": "font_size_match",
                        "description": "字号分布完全一致",
                        "severity": "medium",
                    })

        # Normalize
        normalized = score / max(checks, 1)

        return {
            "score": round(normalized, 4),
            "raw_score": round(score, 4),
            "checks_performed": checks,
            "alert_count": len(alerts),
            "alerts": alerts,
        }

    @staticmethod
    def batch_compare(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量比对"""
        results = []
        n = len(documents)
        for i in range(n):
            for j in range(i + 1, n):
                result = FormatDetector.compare_pair(
                    documents[i].get("format_info", {}),
                    documents[j].get("format_info", {}),
                )
                result["doc_a_id"] = documents[i]["id"]
                result["doc_b_id"] = documents[j]["id"]
                result["company_a"] = documents[i].get("company", "")
                result["company_b"] = documents[j].get("company", "")
                results.append(result)
        return results
