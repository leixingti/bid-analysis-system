"""Phase 2 检测引擎测试"""
import pytest
from app.services.detection.entity_cross import EntityCrossDetector
from app.services.detection.error_pattern import ErrorPatternDetector
from app.services.detection.price_analysis import PriceAnalysisDetector


class TestEntityCrossDetector:
    """NER 实体交叉检测测试"""

    def test_extract_phone(self):
        text = "联系人：张三，电话：13812345678，座机：010-88886666"
        entities = EntityCrossDetector.extract_entities(text)
        assert "13812345678" in entities["phones"]
        assert any("88886666" in p for p in entities["phones"])

    def test_extract_email(self):
        text = "邮箱 zhangsan@example.com 请联系"
        entities = EntityCrossDetector.extract_entities(text)
        assert "zhangsan@example.com" in entities["emails"]

    def test_extract_persons(self):
        text = "项目经理：李明，技术负责人：王刚，安全员：赵强"
        entities = EntityCrossDetector.extract_entities(text)
        names = [p["name"] for p in entities["persons"]]
        assert "李明" in names
        assert "王刚" in names

    def test_cross_detection_person(self):
        """A公司标书出现B公司项目经理"""
        docs = [
            {"id": "1", "company": "A建设公司",
             "text": "本公司项目经理为张三，技术负责人为陈明。联系电话13900001111。我方承诺由张三全权负责本项目。"},
            {"id": "2", "company": "B工程公司",
             "text": "项目经理：张三，联系电话13900001111。本项目由张三担任项目经理，负责全面管理。"},
        ]
        result = EntityCrossDetector.batch_analyze(docs)
        # B的张三出现在A中，A的张三也出现在B中
        assert result["total_alerts"] > 0

    def test_cross_detection_company_name(self):
        """A公司标书中直接出现B公司名称"""
        docs = [
            {"id": "1", "company": "恒达建设",
             "text": "本项目由恒达建设有限公司承建...鑫源工程的报价为参考..."},
            {"id": "2", "company": "鑫源工程",
             "text": "鑫源工程有限公司投标..."},
        ]
        result = EntityCrossDetector.batch_analyze(docs)
        has_company_leak = any(
            any(h["type"] == "company_name" for h in a.get("hits", []))
            for a in result["alerts"]
        )
        assert has_company_leak

    def test_no_cross_detection(self):
        """正常情况不应报警"""
        docs = [
            {"id": "1", "company": "A公司", "text": "项目经理：张三，电话13800001111"},
            {"id": "2", "company": "B公司", "text": "项目经理：李四，电话13900002222"},
        ]
        result = EntityCrossDetector.batch_analyze(docs)
        # 不同人名、不同电话，不应有交叉
        assert result["total_alerts"] == 0


class TestErrorPatternDetector:
    """错误模式识别测试"""

    def test_detect_typos(self):
        text = "本工程采用钢筋混泥土结构，沥清路面施工"
        typos = ErrorPatternDetector.detect_typos(text)
        typo_words = [t["typo"] for t in typos]
        assert "混泥土" in typo_words or "沥清" in typo_words

    def test_detect_obsolete_standards(self):
        text = "施工应符合 GB50300-2001《建筑工程施工质量验收统一标准》的要求"
        stds = ErrorPatternDetector.detect_obsolete_standards(text)
        assert len(stds) > 0
        assert stds[0]["status"] == "已废止"

    def test_detect_punctuation_errors(self):
        text = "本工程位于某市某区,施工工期为120天,质量要求合格。"
        errors = ErrorPatternDetector.detect_punctuation_errors(text)
        has_mixed = any(e["type"] == "mixed_punctuation" for e in errors)
        assert has_mixed

    def test_common_typo_detection(self):
        """多份文档包含相同错别字"""
        docs = [
            {"id": "1", "company": "A公司", "text": "钢筋混泥土结构，沥清路面"},
            {"id": "2", "company": "B公司", "text": "采用钢筋混泥土框架，沥清面层"},
            {"id": "3", "company": "C公司", "text": "钢筋混凝土结构，沥青路面"},  # 正确写法
        ]
        result = ErrorPatternDetector.compare_error_patterns(docs)
        # A和B共享"混泥土"和"沥清"错别字
        assert result["total_alerts"] > 0
        common = result["alerts"][0]
        assert common["company_a"] in ["A公司", "B公司"]

    def test_common_obsolete_standard(self):
        """多份文档引用相同过期标准"""
        docs = [
            {"id": "1", "company": "A公司", "text": "依据GB50300-2001标准执行"},
            {"id": "2", "company": "B公司", "text": "参照GB50300-2001进行质量验收"},
        ]
        result = ErrorPatternDetector.compare_error_patterns(docs)
        has_std_alert = any(a["type"] == "common_obsolete_standard" for a in result["alerts"])
        assert has_std_alert


class TestPriceAnalysisDetector:
    """报价分析测试"""

    def test_extract_price(self):
        text = "投标总价：1,234,567.89 元"
        prices = PriceAnalysisDetector.extract_prices(text)
        assert len(prices) > 0
        assert abs(prices[0]["value"] - 1234567.89) < 0.01

    def test_extract_price_wan(self):
        text = "报价为 123.45 万元"
        prices = PriceAnalysisDetector.extract_prices(text)
        assert len(prices) > 0
        assert abs(prices[0]["value"] - 1234500) < 1

    def test_arithmetic_sequence(self):
        """等差数列检测"""
        prices = [1000000, 1050000, 1100000, 1150000]  # 公差 50000
        result = PriceAnalysisDetector.detect_arithmetic_sequence(prices)
        assert result["is_arithmetic"] is True
        assert abs(result["common_difference"] - 50000) < 100

    def test_geometric_sequence(self):
        """等比数列检测"""
        prices = [1000000, 1050000, 1102500, 1157625]  # 公比 1.05
        result = PriceAnalysisDetector.detect_geometric_sequence(prices)
        assert result["is_geometric"] is True
        assert abs(result["common_ratio"] - 1.05) < 0.01

    def test_fixed_coefficient(self):
        """固定系数检测"""
        prices = [1000000, 950000]  # 0.95倍关系
        result = PriceAnalysisDetector.detect_fixed_coefficient(prices)
        assert result["has_fixed_coeff"] is True

    def test_price_cluster(self):
        """价格围堵检测"""
        prices = [1000000, 1002000, 998000, 1001000, 999500]  # 极度集中
        result = PriceAnalysisDetector.detect_price_cluster(prices)
        assert result["is_clustered"] is True

    def test_no_price_cluster(self):
        """正常价格分散"""
        prices = [800000, 1000000, 1200000, 950000, 1150000]  # 分散
        result = PriceAnalysisDetector.detect_price_cluster(prices)
        assert result["is_clustered"] is False

    def test_cost_breakdown_comparison(self):
        """分项构成异常一致"""
        docs = [
            {"id": "1", "company": "A", "text": "人工费：300000元 材料费：500000元 机械费：100000元 税金：100000元"},
            {"id": "2", "company": "B", "text": "人工费：301000元 材料费：501000元 机械费：100500元 税金：100500元"},
        ]
        result = PriceAnalysisDetector.compare_cost_breakdowns(docs)
        # 比例几乎一致
        assert result["total_alerts"] > 0

    def test_full_price_analysis(self):
        """完整报价分析"""
        docs = [
            {"id": "1", "company": "A公司", "text": "投标总价：1,000,000 元", "price": 1000000},
            {"id": "2", "company": "B公司", "text": "投标总价：950,000 元", "price": 950000},
            {"id": "3", "company": "C公司", "text": "投标总价：1,050,000 元", "price": 1050000},
        ]
        result = PriceAnalysisDetector.full_price_analysis(docs)
        assert result["price_count"] == 3
        assert "arithmetic_sequence" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
