"""Phase 1 核心功能测试"""
import pytest
from app.services.detection.content_similarity import ContentSimilarityDetector
from app.services.detection.metadata_detector import MetadataDetector
from app.services.detection.format_detector import FormatDetector
from app.services.risk.risk_engine import RiskEngine


class TestContentSimilarity:
    """文本相似度检测测试"""

    def test_identical_text(self):
        text = "本项目位于某市某区，投标总价为人民币壹佰万元整。施工工期为120个日历天。"
        result = ContentSimilarityDetector.compute_similarity(text, text)
        assert result["score"] > 0.9

    def test_different_text(self):
        text_a = "本项目采用钢结构框架体系，建筑面积约五千平方米。"
        text_b = "今天天气晴朗，万里无云，适合户外运动。"
        result = ContentSimilarityDetector.compute_similarity(text_a, text_b)
        assert result["score"] < 0.3

    def test_similar_text(self):
        text_a = "本投标文件由甲公司编制，项目经理为张三，联系电话13800138001。施工方案采用钢筋混凝土框架结构。"
        text_b = "本投标文件由乙公司编制，项目经理为张三，联系电话13800138001。施工方案采用钢筋混凝土框架结构。"
        result = ContentSimilarityDetector.compute_similarity(text_a, text_b)
        assert result["score"] > 0.5

    def test_empty_text(self):
        result = ContentSimilarityDetector.compute_similarity("", "some text")
        assert result["score"] == 0.0

    def test_batch_compare(self):
        docs = [
            {"id": "1", "company": "A公司", "text": "本项目投标总价为100万元"},
            {"id": "2", "company": "B公司", "text": "本项目投标总价为100万元"},
            {"id": "3", "company": "C公司", "text": "完全不同的内容关于其他事情"},
        ]
        results = ContentSimilarityDetector.batch_compare(docs)
        assert len(results) == 3  # C(3,2) = 3 pairs


class TestMetadataDetector:
    """元数据检测测试"""

    def test_author_match(self):
        meta_a = {"author": "张三", "created_time": "2024-01-15T10:00:00"}
        meta_b = {"author": "张三", "created_time": "2024-01-15T10:03:00"}
        result = MetadataDetector.compare_pair(meta_a, meta_b, "A公司", "B公司")
        assert result["normalized_score"] > 0
        assert any(a["field"] == "文档作者(Author)" for a in result["alerts"])

    def test_timestamp_cluster(self):
        meta_a = {"created_time": "2024-01-15T10:00:00"}
        meta_b = {"created_time": "2024-01-15T10:02:00"}
        result = MetadataDetector.compare_pair(meta_a, meta_b)
        assert any(a.get("is_clustered") for a in result["alerts"])

    def test_no_match(self):
        meta_a = {"author": "张三", "created_time": "2024-01-10T08:00:00"}
        meta_b = {"author": "李四", "created_time": "2024-03-20T15:00:00"}
        result = MetadataDetector.compare_pair(meta_a, meta_b)
        assert result["alert_count"] == 0

    def test_timestamp_cluster_detection(self):
        docs = [
            {"id": "1", "company": "A公司", "metadata": {"created_time": "2024-01-15T10:00:00"}},
            {"id": "2", "company": "B公司", "metadata": {"created_time": "2024-01-15T10:02:00"}},
            {"id": "3", "company": "C公司", "metadata": {"created_time": "2024-01-15T10:04:00"}},
        ]
        result = MetadataDetector.detect_timestamp_cluster(docs, threshold_minutes=5)
        assert result["is_clustered"] is True


class TestFormatDetector:
    """格式指纹检测测试"""

    def test_same_format(self):
        fmt_a = {
            "fonts_used": ["宋体", "黑体", "Arial"],
            "page_width": 8.27,
            "page_height": 11.69,
            "left_margin": 1.25,
            "right_margin": 1.25,
            "top_margin": 1.0,
            "bottom_margin": 1.0,
            "font_sizes": [10.5, 12.0, 14.0, 22.0],
        }
        fmt_b = dict(fmt_a)  # identical
        result = FormatDetector.compare_pair(fmt_a, fmt_b)
        assert result["score"] > 0.5
        assert result["alert_count"] > 0

    def test_different_format(self):
        fmt_a = {"fonts_used": ["宋体"], "page_width": 8.27, "left_margin": 1.25}
        fmt_b = {"fonts_used": ["Times New Roman"], "page_width": 8.5, "left_margin": 1.0}
        result = FormatDetector.compare_pair(fmt_a, fmt_b)
        assert result["score"] < 0.5


class TestRiskEngine:
    """风险评分引擎测试"""

    def test_high_risk(self):
        results = [
            {"type": "content_similarity", "score": 0.8, "pairs": [
                {"score": 0.8, "company_a": "A", "company_b": "B"}
            ]},
            {"type": "metadata_match", "score": 0.6, "pairs": [
                {"score": 0.6, "company_a": "A", "company_b": "B"}
            ]},
        ]
        risk = RiskEngine.compute_project_risk(results)
        assert risk["risk_score"] > 50
        assert risk["risk_level"] in ["high", "critical"]

    def test_low_risk(self):
        results = [
            {"type": "content_similarity", "score": 0.05, "pairs": []},
            {"type": "metadata_match", "score": 0.0, "pairs": []},
        ]
        risk = RiskEngine.compute_project_risk(results)
        assert risk["risk_score"] < 30
        assert risk["risk_level"] == "low"

    def test_pair_risk(self):
        result = RiskEngine.compute_pair_risk(
            similarity_score=0.9,
            metadata_score=0.7,
            format_score=0.5
        )
        assert result["risk_score"] > 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
