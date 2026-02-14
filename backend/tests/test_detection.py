"""检测引擎单元测试 — 匹配实际类 API"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.detection.content_similarity import ContentSimilarityDetector
from app.services.detection.format_detector import FormatDetector
from app.services.detection.metadata_detector import MetadataDetector
from app.services.detection.entity_cross import EntityCrossDetector
from app.services.detection.error_pattern import ErrorPatternDetector
from app.services.detection.price_analysis import PriceAnalysisDetector
from app.services.risk.risk_engine import RiskEngine


# ── 内容相似度测试 ──

def test_identical_text_similarity():
    text = "本项目采用钢筋混凝土框架结构，基础采用桩基础。施工工期为180个日历天。"
    result = ContentSimilarityDetector.compute_similarity(text, text)
    assert isinstance(result, dict)
    assert "similarity_score" in result or "overall_similarity" in result
    score = result.get("similarity_score", result.get("overall_similarity", 0))
    assert score > 0.8


def test_different_text_similarity():
    text_a = "本项目位于北京市朝阳区，建筑面积约5000平方米。"
    text_b = "今天天气晴朗，适合户外活动，公园里人很多。"
    result = ContentSimilarityDetector.compute_similarity(text_a, text_b)
    assert isinstance(result, dict)
    score = result.get("similarity_score", result.get("overall_similarity", 0))
    assert score < 0.5


def test_batch_compare():
    docs = [
        {"id": "1", "company_name": "公司A", "full_text": "本项目采用钢结构框架"},
        {"id": "2", "company_name": "公司B", "full_text": "本项目采用钢结构框架体系"},
    ]
    results = ContentSimilarityDetector.batch_compare(docs)
    assert isinstance(results, list)


# ── 格式指纹检测 ──

def test_format_compare_pair():
    fmt_a = {"fonts": ["宋体", "黑体"], "page_margins": {"top": 2.54, "bottom": 2.54}}
    fmt_b = {"fonts": ["宋体", "黑体"], "page_margins": {"top": 2.54, "bottom": 2.54}}
    result = FormatDetector.compare_pair(fmt_a, fmt_b)
    assert isinstance(result, dict)


def test_format_compare_different():
    fmt_a = {"fonts": ["宋体"], "page_margins": {"top": 2.54}}
    fmt_b = {"fonts": ["楷体"], "page_margins": {"top": 3.0}}
    result = FormatDetector.compare_pair(fmt_a, fmt_b)
    assert isinstance(result, dict)


# ── 元数据检测 ──

def test_metadata_compare_pair():
    meta_a = {"meta_author": "张三", "meta_company": "公司A"}
    meta_b = {"meta_author": "张三", "meta_company": "公司B"}
    result = MetadataDetector.compare_pair(meta_a, meta_b)
    assert isinstance(result, dict)


def test_metadata_batch_compare():
    docs = [
        {"id": "1", "company_name": "公司A", "meta_author": "张三", "meta_created_time": "2024-01-15T10:00:00"},
        {"id": "2", "company_name": "公司B", "meta_author": "张三", "meta_created_time": "2024-01-15T10:03:00"},
    ]
    results = MetadataDetector.batch_compare(docs)
    assert isinstance(results, list)


# ── 实体交叉检测 ──

def test_entity_extract():
    text = "联系电话：13812345678，项目经理张三"
    result = EntityCrossDetector.extract_entities(text, "公司A")
    assert isinstance(result, dict)


def test_entity_cross_check():
    docs = [
        {"id": "1", "company_name": "公司A", "full_text": "我公司即公司B具有丰富经验"},
        {"id": "2", "company_name": "公司B", "full_text": "我公司具有丰富施工经验"},
    ]
    results = EntityCrossDetector.cross_check(docs)
    assert isinstance(results, list)


# ── 错误模式检测 ──

def test_error_pattern():
    detector = ErrorPatternDetector()
    assert detector is not None


# ── 报价分析 ──

def test_price_analysis():
    detector = PriceAnalysisDetector()
    assert detector is not None


# ── 风险引擎 ──

def test_risk_engine_compute():
    results = [
        {"analysis_type": "content_similarity", "score": 0.8, "risk_level": "high"},
        {"analysis_type": "metadata_match", "score": 0.5, "risk_level": "medium"},
    ]
    risk = RiskEngine.compute_project_risk(results)
    assert isinstance(risk, dict)
    assert "risk_score" in risk or "risk_level" in risk
