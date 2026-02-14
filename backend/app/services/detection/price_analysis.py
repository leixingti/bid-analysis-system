"""报价分析引擎 — 数学序列检测 + 分项构成异常分析"""
import re
import math
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter


class PriceAnalysisDetector:
    """
    报价数据特征检测器
    1. 数学序列检测：等差/等比数列、固定系数关系
    2. 异常梯度识别：价格围堵（同时偏高/偏低）
    3. 分项构成分析：人工/材料/税费比例异常一致
    """

    # === 报价提取正则 ===
    PRICE_PATTERNS = [
        # "投标总价: 1,234,567.89 元"
        re.compile(r'(?:投标总?价|报价|总[价报]|合计金额)[：:为\s]*(?:人民币)?[\s]*([0-9,，]+(?:\.\d{1,2})?)\s*(?:元|万元)'),
        # "￥1,234,567.89"
        re.compile(r'[￥¥]\s*([0-9,，]+(?:\.\d{1,2})?)'),
        # "总价(元): 1234567.89"
        re.compile(r'总价\s*(?:\(元\))?\s*[：:]\s*([0-9,，]+(?:\.\d{1,2})?)'),
    ]

    # 分项关键词
    COST_CATEGORIES = {
        "labor": ["人工费", "人工成本", "劳务费", "工资"],
        "material": ["材料费", "材料成本", "主材费", "辅材费"],
        "equipment": ["机械费", "设备费", "机具费"],
        "management": ["管理费", "企业管理费"],
        "profit": ["利润"],
        "tax": ["税金", "税费", "增值税", "税率"],
        "other": ["措施费", "安全文明施工费", "规费", "其他费用"],
    }

    @staticmethod
    def extract_prices(text: str) -> List[Dict[str, Any]]:
        """从文本中提取报价金额"""
        prices = []
        for pattern in PriceAnalysisDetector.PRICE_PATTERNS:
            for match in pattern.finditer(text):
                price_str = match.group(1).replace(",", "").replace("，", "")
                try:
                    price = float(price_str)
                    if price > 0:
                        # 检查是否为"万元"
                        full_match = match.group()
                        if "万元" in full_match:
                            price *= 10000
                        prices.append({
                            "value": price,
                            "raw_text": match.group(),
                            "position": match.start(),
                        })
                except ValueError:
                    pass
        return prices

    @staticmethod
    def extract_cost_breakdown(text: str) -> Dict[str, Optional[float]]:
        """提取分项费用构成"""
        breakdown = {}
        for category, keywords in PriceAnalysisDetector.COST_CATEGORIES.items():
            for kw in keywords:
                # 模式: "人工费：123,456.78 元"
                pattern = re.compile(
                    rf'{re.escape(kw)}[：:为\s]*([0-9,，]+(?:\.\d{{1,2}})?)\s*(?:元|万元)?'
                )
                for match in pattern.finditer(text):
                    val_str = match.group(1).replace(",", "").replace("，", "")
                    try:
                        val = float(val_str)
                        if "万元" in match.group():
                            val *= 10000
                        if val > 0:
                            breakdown[category] = val
                            break
                    except ValueError:
                        pass
        return breakdown

    @staticmethod
    def detect_arithmetic_sequence(prices: List[float], tolerance: float = 0.02) -> Dict[str, Any]:
        """
        检测报价是否构成等差数列
        tolerance: 允许的相对误差
        """
        if len(prices) < 3:
            return {"is_arithmetic": False}

        sorted_prices = sorted(prices)
        diffs = [sorted_prices[i+1] - sorted_prices[i] for i in range(len(sorted_prices)-1)]

        if not diffs:
            return {"is_arithmetic": False}

        avg_diff = sum(diffs) / len(diffs)
        if avg_diff == 0:
            return {"is_arithmetic": True, "common_difference": 0, "description": "所有报价完全相同"}

        max_deviation = max(abs(d - avg_diff) / abs(avg_diff) for d in diffs) if avg_diff != 0 else 0
        is_arithmetic = max_deviation <= tolerance

        return {
            "is_arithmetic": is_arithmetic,
            "common_difference": round(avg_diff, 2),
            "max_deviation": round(max_deviation, 4),
            "sorted_prices": sorted_prices,
            "differences": [round(d, 2) for d in diffs],
            "description": f"报价呈等差数列，公差约 {avg_diff:,.2f} 元" if is_arithmetic else "",
        }

    @staticmethod
    def detect_geometric_sequence(prices: List[float], tolerance: float = 0.02) -> Dict[str, Any]:
        """检测报价是否构成等比数列"""
        if len(prices) < 3:
            return {"is_geometric": False}

        sorted_prices = sorted(prices)
        if any(p <= 0 for p in sorted_prices):
            return {"is_geometric": False}

        ratios = [sorted_prices[i+1] / sorted_prices[i] for i in range(len(sorted_prices)-1)]
        avg_ratio = sum(ratios) / len(ratios)

        if avg_ratio == 0:
            return {"is_geometric": False}

        max_deviation = max(abs(r - avg_ratio) / abs(avg_ratio) for r in ratios)
        is_geometric = max_deviation <= tolerance

        return {
            "is_geometric": is_geometric,
            "common_ratio": round(avg_ratio, 4),
            "max_deviation": round(max_deviation, 4),
            "ratios": [round(r, 4) for r in ratios],
            "description": f"报价呈等比数列，公比约 {avg_ratio:.4f}" if is_geometric else "",
        }

    @staticmethod
    def detect_fixed_coefficient(prices: List[float], tolerance: float = 0.005) -> Dict[str, Any]:
        """检测报价之间是否存在固定系数关系 (如 0.95 倍)"""
        if len(prices) < 2:
            return {"has_fixed_coeff": False}

        results = []
        for i in range(len(prices)):
            for j in range(i + 1, len(prices)):
                if prices[j] == 0 or prices[i] == 0:
                    continue
                ratio = prices[i] / prices[j]
                # 检测常见系数: 0.90, 0.95, 0.98, 1.02, 1.05, 1.10
                common_coeffs = [0.90, 0.92, 0.95, 0.96, 0.97, 0.98, 0.99,
                                 1.01, 1.02, 1.03, 1.05, 1.08, 1.10]
                for coeff in common_coeffs:
                    if abs(ratio - coeff) <= tolerance:
                        results.append({
                            "price_a": prices[i],
                            "price_b": prices[j],
                            "ratio": round(ratio, 4),
                            "matched_coefficient": coeff,
                            "deviation": round(abs(ratio - coeff), 6),
                        })

        return {
            "has_fixed_coeff": len(results) > 0,
            "found_pairs": results,
            "description": f"发现 {len(results)} 对报价存在固定系数关系" if results else "",
        }

    @staticmethod
    def detect_price_cluster(prices: List[float], threshold_pct: float = 0.03) -> Dict[str, Any]:
        """
        异常梯度识别 — 检测报价是否异常集中（价格围堵）
        threshold_pct: 价格偏差阈值百分比
        """
        if len(prices) < 3:
            return {"is_clustered": False}

        avg_price = sum(prices) / len(prices)
        if avg_price == 0:
            return {"is_clustered": False}

        deviations = [abs(p - avg_price) / avg_price for p in prices]
        max_dev = max(deviations)
        avg_dev = sum(deviations) / len(deviations)

        # 所有报价偏差都在阈值内 → 价格围堵嫌疑
        all_within = all(d <= threshold_pct for d in deviations)
        # 大多数报价偏差很小
        most_within = sum(1 for d in deviations if d <= threshold_pct) / len(deviations)

        is_clustered = all_within or (most_within >= 0.8 and max_dev < threshold_pct * 2)

        return {
            "is_clustered": is_clustered,
            "average_price": round(avg_price, 2),
            "max_deviation_pct": round(max_dev * 100, 2),
            "avg_deviation_pct": round(avg_dev * 100, 2),
            "prices_within_threshold": sum(1 for d in deviations if d <= threshold_pct),
            "total_prices": len(prices),
            "description": (
                f"报价高度集中，均价 {avg_price:,.2f}，最大偏差仅 {max_dev*100:.1f}%"
                if is_clustered else ""
            ),
        }

    @staticmethod
    def compare_cost_breakdowns(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分项构成分析 — 比较多份标书的费用构成比例是否异常一致

        documents: [{"id": ..., "company": ..., "text": ..., "breakdown": {...}}]
        """
        breakdowns = {}
        for doc in documents:
            bd = doc.get("breakdown")
            if not bd:
                bd = PriceAnalysisDetector.extract_cost_breakdown(doc.get("text", ""))
            if bd:
                breakdowns[doc["id"]] = {
                    "company": doc.get("company", ""),
                    "breakdown": bd,
                }

        if len(breakdowns) < 2:
            return {"alerts": [], "total_alerts": 0}

        # 计算各文档的比例
        ratios_by_doc = {}
        for doc_id, info in breakdowns.items():
            bd = info["breakdown"]
            total = sum(bd.values())
            if total > 0:
                ratios_by_doc[doc_id] = {
                    "company": info["company"],
                    "ratios": {k: round(v / total, 4) for k, v in bd.items()},
                    "total": total,
                }

        # 两两比较比例一致性
        alerts = []
        doc_ids = list(ratios_by_doc.keys())
        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                id_a, id_b = doc_ids[i], doc_ids[j]
                ratios_a = ratios_by_doc[id_a]["ratios"]
                ratios_b = ratios_by_doc[id_b]["ratios"]

                # 计算比例的相似度
                common_keys = set(ratios_a.keys()) & set(ratios_b.keys())
                if len(common_keys) < 2:
                    continue

                diffs = []
                for key in common_keys:
                    diff = abs(ratios_a[key] - ratios_b[key])
                    diffs.append(diff)

                avg_diff = sum(diffs) / len(diffs)
                max_diff = max(diffs)

                # 如果平均差异 < 1% 且最大差异 < 2%，认为异常一致
                if avg_diff < 0.01 and max_diff < 0.02:
                    severity = 1.0 - avg_diff * 50  # 越接近越严重
                    alerts.append({
                        "type": "cost_ratio_match",
                        "doc_a_id": id_a,
                        "doc_b_id": id_b,
                        "company_a": ratios_by_doc[id_a]["company"],
                        "company_b": ratios_by_doc[id_b]["company"],
                        "severity_score": round(min(severity, 1.0), 4),
                        "avg_ratio_diff": round(avg_diff, 4),
                        "max_ratio_diff": round(max_diff, 4),
                        "compared_categories": list(common_keys),
                        "ratios_a": ratios_a,
                        "ratios_b": ratios_b,
                        "description": (
                            f"费用构成比例异常一致，{len(common_keys)} 个分项的平均差异仅 "
                            f"{avg_diff*100:.2f}%（最大 {max_diff*100:.2f}%）"
                        ),
                    })

        return {
            "total_alerts": len(alerts),
            "max_severity": max((a["severity_score"] for a in alerts), default=0.0),
            "alerts": sorted(alerts, key=lambda x: x["severity_score"], reverse=True),
            "breakdowns": {
                doc_id: {
                    "company": info["company"],
                    "ratios": info["ratios"],
                    "total": info["total"],
                }
                for doc_id, info in ratios_by_doc.items()
            },
        }

    @staticmethod
    def full_price_analysis(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        完整报价分析入口

        documents: [{"id": ..., "company": ..., "text": ..., "price": optional float}]
        """
        # 提取价格
        prices_map = {}
        for doc in documents:
            price = doc.get("price")
            if price is None:
                extracted = PriceAnalysisDetector.extract_prices(doc.get("text", ""))
                if extracted:
                    price = extracted[0]["value"]
            if price and price > 0:
                prices_map[doc["id"]] = {
                    "company": doc.get("company", ""),
                    "price": price,
                }

        price_values = [v["price"] for v in prices_map.values()]
        company_prices = [(v["company"], v["price"]) for v in prices_map.values()]

        results = {
            "price_count": len(price_values),
            "prices": company_prices,
            "arithmetic_sequence": {},
            "geometric_sequence": {},
            "fixed_coefficient": {},
            "price_cluster": {},
            "cost_breakdown": {},
            "alerts": [],
        }

        if len(price_values) >= 2:
            # 等差数列
            results["arithmetic_sequence"] = PriceAnalysisDetector.detect_arithmetic_sequence(price_values)
            if results["arithmetic_sequence"].get("is_arithmetic"):
                results["alerts"].append({
                    "type": "arithmetic_sequence",
                    "severity_score": 0.9,
                    "description": results["arithmetic_sequence"]["description"],
                })

            # 等比数列
            results["geometric_sequence"] = PriceAnalysisDetector.detect_geometric_sequence(price_values)
            if results["geometric_sequence"].get("is_geometric"):
                results["alerts"].append({
                    "type": "geometric_sequence",
                    "severity_score": 0.9,
                    "description": results["geometric_sequence"]["description"],
                })

            # 固定系数
            results["fixed_coefficient"] = PriceAnalysisDetector.detect_fixed_coefficient(price_values)
            if results["fixed_coefficient"].get("has_fixed_coeff"):
                results["alerts"].append({
                    "type": "fixed_coefficient",
                    "severity_score": 0.7,
                    "description": results["fixed_coefficient"]["description"],
                })

        if len(price_values) >= 3:
            # 价格围堵
            results["price_cluster"] = PriceAnalysisDetector.detect_price_cluster(price_values)
            if results["price_cluster"].get("is_clustered"):
                results["alerts"].append({
                    "type": "price_cluster",
                    "severity_score": 0.8,
                    "description": results["price_cluster"]["description"],
                })

        # 分项构成
        results["cost_breakdown"] = PriceAnalysisDetector.compare_cost_breakdowns(documents)
        results["alerts"].extend([
            {"type": "cost_ratio_match", "severity_score": a["severity_score"],
             "description": a["description"]}
            for a in results["cost_breakdown"].get("alerts", [])
        ])

        results["max_severity"] = max(
            (a["severity_score"] for a in results["alerts"]), default=0.0
        )

        return results
