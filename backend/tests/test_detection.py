"""检测引擎单元测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.detection.content_sim import (
    detect_content_similarity, compute_tfidf_similarity,
    find_common_sentences, find_common_errors
)
from app.services.detection.format_trace import (
    compare_metadata, compare_format, compare_timestamps, compare_images
)
from app.services.detection.entity_cross import cross_check_entities, extract_entities
from app.services.risk.risk_engine import compute_pair_risk, classify_risk
from app.utils.hash import simhash_text, simhash_similarity


# ── 内容相似度测试 ──

def test_identical_text_similarity():
    text = "本项目采用钢筋混凝土框架结构，基础采用桩基础。施工工期为180个日历天。"
    result = detect_content_similarity(text, text)
    assert result["overall_similarity"] > 0.9


def test_different_text_similarity():
    text_a = "本项目位于北京市朝阳区，建筑面积约5000平方米。"
    text_b = "今天天气晴朗，适合户外活动，公园里人很多。"
    result = detect_content_similarity(text_a, text_b)
    assert result["overall_similarity"] < 0.5


def test_common_sentences():
    text_a = "质量保证期为两年。施工安全措施按照国家标准执行。所有材料必须有合格证明。"
    text_b = "所有材料必须有合格证明。工期为120天。施工安全措施按照国家标准执行。"
    common = find_common_sentences(text_a, text_b, min_len=5)
    assert len(common) >= 1


def test_common_errors():
    text_a = "本项目采用。。钢结构"
    text_b = "该工程使用。。钢材"
    errors = find_common_errors(text_a, text_b)
    assert len(errors) > 0


# ── SimHash 测试 ──

def test_simhash_identical():
    text = "投标文件应按照招标文件要求编制"
    h1 = simhash_text(text)
    h2 = simhash_text(text)
    assert simhash_similarity(h1, h2) == 1.0


# ── 元数据比对测试 ──

def test_metadata_same_author():
    meta_a = {"author": "张三", "application": "Microsoft Word"}
    meta_b = {"author": "张三", "application": "Microsoft Word"}
    result = compare_metadata(meta_a, meta_b)
    assert result["score"] > 0


def test_metadata_cross_company():
    meta_a = {"author": "公司B的人"}
    meta_b = {"author": "其他人"}
    result = compare_metadata(meta_a, meta_b, "公司A", "公司B")
    # 检测公司名交叉
    assert isinstance(result["risk_factors"], list)


# ── 时间戳检测 ──

def test_timestamp_close():
    meta_a = {"created_date": "2024-01-15T10:00:00"}
    meta_b = {"created_date": "2024-01-15T10:03:00"}
    result = compare_timestamps(meta_a, meta_b, threshold_minutes=5)
    assert len(result["timestamp_alerts"]) > 0


def test_timestamp_far():
    meta_a = {"created_date": "2024-01-15T10:00:00"}
    meta_b = {"created_date": "2024-01-20T14:00:00"}
    result = compare_timestamps(meta_a, meta_b, threshold_minutes=5)
    assert len(result["timestamp_alerts"]) == 0


# ── 实体交叉检测 ──

def test_entity_cross_company_name():
    text_a = "我公司即公司B具有丰富的施工经验"  # A 的标书提到 B
    text_b = "我公司具有丰富的施工经验"
    result = cross_check_entities(text_a, text_b, "公司A", "公司B")
    alerts = result["cross_entity_alerts"]
    assert any(a["type"] == "company_name_cross" for a in alerts)


def test_entity_cross_phone():
    text_a = "联系电话：13812345678，项目经理张三"
    text_b = "联系人李四，电话13812345678"
    result = cross_check_entities(text_a, text_b, "公司A", "公司B")
    alerts = result["cross_entity_alerts"]
    assert any("电话" in a["message"] for a in alerts)


# ── 图片比对 ──

def test_image_match():
    imgs_a = [{"md5": "abc123"}, {"md5": "def456"}]
    imgs_b = [{"md5": "abc123"}, {"md5": "ghi789"}]
    result = compare_images(imgs_a, imgs_b)
    assert result["common_image_count"] == 1


# ── 风险评分 ──

def test_risk_classify():
    assert classify_risk(0.8) == "critical"
    assert classify_risk(0.5) == "high"
    assert classify_risk(0.3) == "medium"
    assert classify_risk(0.1) == "low"


def test_compute_pair_risk():
    result = compute_pair_risk(
        content_result={"overall_similarity": 0.8, "common_sentences_count": 5, "common_errors": []},
        metadata_result={"score": 0.5, "risk_factors": ["作者相同"], "metadata_matches": []},
        format_result={"score": 0.3, "format_matches": []},
        timestamp_result={"score": 0.5, "timestamp_alerts": [{"alert": "时间接近"}]},
        entity_result={"score": 0.5, "cross_entity_alerts": [{"message": "公司名交叉"}]},
        image_result={"score": 0.2, "common_image_count": 1},
    )
    assert result["risk_score_100"] > 0
    assert result["risk_level"] in ("low", "medium", "high", "critical")
