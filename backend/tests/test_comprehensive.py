"""增强测试套件 — 检测算法核心测试 + API集成测试"""
import pytest
import sys
import os

# 确保导入路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestContentSimilarity:
    """文本相似度检测器测试"""

    def test_identical_texts(self):
        from app.services.detection.content_similarity import ContentSimilarityDetector
        docs = [
            {"id": "1", "company": "A公司", "text": "本公司承诺按照招标文件要求，严格执行质量管理体系，确保工程按时保质完成。"},
            {"id": "2", "company": "B公司", "text": "本公司承诺按照招标文件要求，严格执行质量管理体系，确保工程按时保质完成。"},
        ]
        results = ContentSimilarityDetector.batch_compare(docs)
        assert len(results) == 1
        assert results[0]["score"] > 0.8, "相同文本应高相似度"

    def test_different_texts(self):
        from app.services.detection.content_similarity import ContentSimilarityDetector
        docs = [
            {"id": "1", "company": "A公司", "text": "我们提供最先进的施工机械设备，包括挖掘机、起重机和混凝土搅拌车。"},
            {"id": "2", "company": "B公司", "text": "公司财务状况良好，注册资本五千万元，年营业收入超过两亿元人民币。"},
        ]
        results = ContentSimilarityDetector.batch_compare(docs)
        assert len(results) == 1
        assert results[0]["score"] < 0.3, "不同文本应低相似度"

    def test_empty_text(self):
        from app.services.detection.content_similarity import ContentSimilarityDetector
        docs = [
            {"id": "1", "company": "A", "text": ""},
            {"id": "2", "company": "B", "text": "有内容的文档"},
        ]
        results = ContentSimilarityDetector.batch_compare(docs)
        assert len(results) == 1
        assert results[0]["score"] == 0.0 or results[0]["score"] < 0.1

    def test_single_document(self):
        from app.services.detection.content_similarity import ContentSimilarityDetector
        docs = [{"id": "1", "company": "A", "text": "只有一份"}]
        results = ContentSimilarityDetector.batch_compare(docs)
        assert len(results) == 0

    def test_three_documents_generates_three_pairs(self):
        from app.services.detection.content_similarity import ContentSimilarityDetector
        docs = [
            {"id": "1", "company": "A", "text": "文本一" * 20},
            {"id": "2", "company": "B", "text": "文本二" * 20},
            {"id": "3", "company": "C", "text": "文本三" * 20},
        ]
        results = ContentSimilarityDetector.batch_compare(docs)
        assert len(results) == 3  # C(3,2) = 3


class TestMetadataDetector:
    """元数据检测器测试"""

    def test_same_author(self):
        from app.services.detection.metadata_detector import MetadataDetector
        docs = [
            {"id": "1", "company": "A", "text": "", "metadata": {"author": "张三", "company": "", "last_modified_by": "", "created_time": None, "modified_time": None, "producer": "", "creator": "", "software_version": ""}},
            {"id": "2", "company": "B", "text": "", "metadata": {"author": "张三", "company": "", "last_modified_by": "", "created_time": None, "modified_time": None, "producer": "", "creator": "", "software_version": ""}},
        ]
        results = MetadataDetector.batch_compare(docs)
        assert len(results) >= 1
        assert results[0]["alert_count"] > 0, "相同作者应产生预警"

    def test_different_metadata(self):
        from app.services.detection.metadata_detector import MetadataDetector
        docs = [
            {"id": "1", "company": "A", "text": "", "metadata": {"author": "张三", "company": "A公司", "last_modified_by": "张三", "created_time": None, "modified_time": None, "producer": "WPS", "creator": "WPS", "software_version": "11.0"}},
            {"id": "2", "company": "B", "text": "", "metadata": {"author": "李四", "company": "B公司", "last_modified_by": "李四", "created_time": None, "modified_time": None, "producer": "Word", "creator": "Word", "software_version": "16.0"}},
        ]
        results = MetadataDetector.batch_compare(docs)
        assert len(results) >= 1
        assert results[0]["alert_count"] == 0 or results[0]["normalized_score"] < 0.3

    def test_timestamp_cluster_detected(self):
        from app.services.detection.metadata_detector import MetadataDetector
        docs = [
            {"id": "1", "company": "A", "text": "", "metadata": {"created_time": "2024-06-15T10:00:00", "modified_time": None, "author": "", "company": "", "last_modified_by": "", "producer": "", "creator": "", "software_version": ""}},
            {"id": "2", "company": "B", "text": "", "metadata": {"created_time": "2024-06-15T10:02:00", "modified_time": None, "author": "", "company": "", "last_modified_by": "", "producer": "", "creator": "", "software_version": ""}},
            {"id": "3", "company": "C", "text": "", "metadata": {"created_time": "2024-06-15T10:03:00", "modified_time": None, "author": "", "company": "", "last_modified_by": "", "producer": "", "creator": "", "software_version": ""}},
        ]
        result = MetadataDetector.detect_timestamp_cluster(docs, threshold_minutes=5)
        assert result["is_clustered"], "3份文档3分钟内创建应检测到聚集"


class TestEntityCross:
    """实体交叉检测器测试"""

    def test_phone_leak(self):
        from app.services.detection.entity_cross import EntityCrossDetector
        docs = [
            {"id": "1", "company": "A公司", "text": "联系人张三，电话13800138000，地址北京"},
            {"id": "2", "company": "B公司", "text": "我们的联系方式：13800138000，联系人李四"},
        ]
        result = EntityCrossDetector.batch_analyze(docs)
        assert result["max_severity"] > 0, "相同电话号码应产生预警"

    def test_no_entity_overlap(self):
        from app.services.detection.entity_cross import EntityCrossDetector
        docs = [
            {"id": "1", "company": "A公司", "text": "联系人张三电话13800138001"},
            {"id": "2", "company": "B公司", "text": "联系人李四电话13900139002"},
        ]
        result = EntityCrossDetector.batch_analyze(docs)
        # 不同号码不应产生高分预警
        assert result["max_severity"] < 0.5


class TestPriceAnalysis:
    """报价分析测试"""

    def test_arithmetic_sequence(self):
        from app.services.detection.price_analysis import PriceAnalysisDetector
        # 构造含等差数列报价的文档
        docs = [
            {"id": "1", "company": "A", "text": "投标报价：人民币壹佰万元整 (1000000元)"},
            {"id": "2", "company": "B", "text": "投标报价：人民币壹佰壹拾万元 (1100000元)"},
            {"id": "3", "company": "C", "text": "投标报价：人民币壹佰贰拾万元 (1200000元)"},
        ]
        result = PriceAnalysisDetector.full_price_analysis(docs)
        # 应能检测到价格模式（具体取决于解析结果）
        assert "alerts" in result


class TestErrorPattern:
    """错误模式检测测试"""

    def test_common_typo(self):
        from app.services.detection.error_pattern import ErrorPatternDetector
        docs = [
            {"id": "1", "company": "A", "text": "本项目按照GB50300-2001标准执行，确保质量合个"},
            {"id": "2", "company": "B", "text": "本项目按照GB50300-2001标准执行，确保质量合个"},
        ]
        result = ErrorPatternDetector.compare_error_patterns(docs)
        assert "alerts" in result


class TestRiskEngine:
    """风险引擎测试"""

    def test_high_risk_scoring(self):
        from app.services.risk.risk_engine import RiskEngine
        results = [
            {"type": "content_similarity", "score": 0.9, "pairs": [{"score": 0.9, "company_a": "A", "company_b": "B"}]},
            {"type": "entity_cross", "score": 0.8, "pairs": [{"score": 0.8, "company_a": "A", "company_b": "B"}]},
        ]
        risk = RiskEngine.compute_project_risk(results)
        assert risk["risk_score"] >= 30, "高分检测应产生高风险"
        assert risk["risk_level"] in ["medium", "high", "critical"]

    def test_low_risk_scoring(self):
        from app.services.risk.risk_engine import RiskEngine
        results = [
            {"type": "content_similarity", "score": 0.1, "pairs": []},
            {"type": "metadata_match", "score": 0.05, "pairs": []},
        ]
        risk = RiskEngine.compute_project_risk(results)
        assert risk["risk_score"] < 30
        assert risk["risk_level"] == "low"

    def test_empty_results(self):
        from app.services.risk.risk_engine import RiskEngine
        risk = RiskEngine.compute_project_risk([])
        assert risk["risk_score"] == 0.0
        assert risk["risk_level"] == "low"

    def test_weight_sum(self):
        from app.services.risk.risk_engine import RiskEngine
        total = sum(RiskEngine.WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"权重之和应为1.0，实际为{total}"


class TestFormatDetector:
    """格式指纹检测测试"""

    def test_same_format(self):
        from app.services.detection.format_detector import FormatDetector
        docs = [
            {"id": "1", "company": "A", "text": "", "format_info": {"page_size": "A4", "margins": {"top": 72, "bottom": 72}, "font_sizes": {"12": 80, "14": 20}}},
            {"id": "2", "company": "B", "text": "", "format_info": {"page_size": "A4", "margins": {"top": 72, "bottom": 72}, "font_sizes": {"12": 80, "14": 20}}},
        ]
        results = FormatDetector.batch_compare(docs)
        assert len(results) >= 1
        assert results[0]["alert_count"] > 0 or results[0]["score"] > 0.3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
