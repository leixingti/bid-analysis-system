"""错误模式识别引擎 — 检测多份标书中的共性错误"""
import re
from typing import Dict, Any, List, Tuple
from collections import Counter


class ErrorPatternDetector:
    """
    错误模式检测器
    核心：若多份标书包含相同的非通用性错误，说明极可能同源
    检测项：
    1. 相同的错别字/别字
    2. 相同的标点符号错误
    3. 引用过期/错误标准编号
    4. 相同的计算/数据错误
    5. 相同的异常格式（如全角半角混用模式）
    """

    # === 常见错别字词典 (错误 -> 正确) ===
    COMMON_TYPOS = {
        "安全帽": None,  # 正确词，不报错
        # 建筑工程常见错别字
        "钢筋混凝土": None,
        "钢筋混泥土": "钢筋混凝土",
        "混泥土": "混凝土",
        "沥清": "沥青",
        "勾缝": None,
        "勾逢": "勾缝",
        "抹灰": None,
        "抹会": "抹灰",
        "脚手架": None,
        "脚手加": "脚手架",
        "竣工": None,
        "峻工": "竣工",
        "梁柱": None,
        "粱柱": "梁柱",
        "施工": None,
        "施公": "施工",
        "质量": None,
        "质梁": "质量",
        "验收": None,
        "验受": "验收",
        "竞标": None,
        "竞彪": "竞标",
        "招标": None,
        "招彪": "招标",
        "预算": None,
        "予算": "预算",
        "概算": None,
        "慨算": "概算",
        "决算": None,
        "绝算": "决算",
        "工期": None,
        "工其": "工期",
        "监理": None,
        "监里": "监理",
        "防水": None,
        "仿水": "防水",
        "保温": None,
        "保问": "保温",
        "管道": None,
        "管到": "管道",
        "消防": None,
        "消仿": "消防",
        "排水": None,
        "排说": "排水",
        "承包": None,
        "承抱": "承包",
        "分包": None,
        "分抱": "分包",
    }

    # === 已废止/过期的国标编号 ===
    OBSOLETE_STANDARDS = {
        "GB50300-2001": {"replaced_by": "GB50300-2013", "name": "建筑工程施工质量验收统一标准"},
        "GB50010-2002": {"replaced_by": "GB50010-2010(2015版)", "name": "混凝土结构设计规范"},
        "GB50011-2001": {"replaced_by": "GB50011-2010(2016版)", "name": "建筑抗震设计规范"},
        "GB50009-2001": {"replaced_by": "GB50009-2012", "name": "建筑结构荷载规范"},
        "GB50007-2002": {"replaced_by": "GB50007-2011", "name": "建筑地基基础设计规范"},
        "GB50017-2003": {"replaced_by": "GB50017-2017", "name": "钢结构设计标准"},
        "GB/T50328-2001": {"replaced_by": "GB/T50328-2014", "name": "建设工程文件归档规范"},
        "GB50204-2002": {"replaced_by": "GB50204-2015", "name": "混凝土结构工程施工质量验收规范"},
        "GB50205-2001": {"replaced_by": "GB50205-2020", "name": "钢结构工程施工质量验收标准"},
        "JGJ46-2005": {"replaced_by": "JGJ46-2024", "name": "施工现场临时用电安全技术规范"},
        "JGJ59-2011": {"replaced_by": "JGJ59-2023", "name": "建筑施工安全检查标准"},
    }

    # 标准编号正则
    STANDARD_PATTERN = re.compile(
        r'(?:GB|GB/T|JGJ|JGJ/T|CJJ|DL/T|SL|JTG|JTGD|SH/T|HG/T)\s*/?'
        r'\s*\d{4,5}(?:\.\d+)?(?:\s*[-—]\s*\d{4})'
    )

    @staticmethod
    def detect_typos(text: str) -> List[Dict[str, Any]]:
        """检测文本中的错别字"""
        found_typos = []
        for wrong, correct in ErrorPatternDetector.COMMON_TYPOS.items():
            if correct is None:
                continue  # 这是正确词
            positions = [m.start() for m in re.finditer(re.escape(wrong), text)]
            if positions:
                for pos in positions[:5]:  # 每个错别字最多记5处
                    ctx_start = max(0, pos - 15)
                    ctx_end = min(len(text), pos + len(wrong) + 15)
                    found_typos.append({
                        "typo": wrong,
                        "correction": correct,
                        "position": pos,
                        "context": text[ctx_start:ctx_end],
                    })
        return found_typos

    @staticmethod
    def detect_punctuation_errors(text: str) -> List[Dict[str, Any]]:
        """检测标点符号错误/异常模式"""
        errors = []

        # 1. 中英文标点混用模式
        mixed_patterns = [
            (r'[\u4e00-\u9fff],[\u4e00-\u9fff]', "中文间使用英文逗号"),
            (r'[\u4e00-\u9fff]\.[\u4e00-\u9fff]', "中文间使用英文句号"),
            (r'[\u4e00-\u9fff];[\u4e00-\u9fff]', "中文间使用英文分号"),
            (r'[\u4e00-\u9fff]\(', "中文前使用英文左括号"),
            (r'\)[\u4e00-\u9fff]', "中文后使用英文右括号"),
        ]
        for pattern, desc in mixed_patterns:
            matches = list(re.finditer(pattern, text))
            if matches:
                errors.append({
                    "type": "mixed_punctuation",
                    "description": desc,
                    "count": len(matches),
                    "examples": [text[max(0, m.start()-5):m.end()+5] for m in matches[:3]],
                })

        # 2. 连续重复标点
        repeated = list(re.finditer(r'([，。！？；：、])\1+', text))
        if repeated:
            errors.append({
                "type": "repeated_punctuation",
                "description": "连续重复标点",
                "count": len(repeated),
                "examples": [m.group() for m in repeated[:3]],
            })

        # 3. 全角半角数字混用
        has_fullwidth = bool(re.search(r'[０-９]', text))
        has_halfwidth = bool(re.search(r'[0-9]', text))
        if has_fullwidth and has_halfwidth:
            errors.append({
                "type": "mixed_width_numbers",
                "description": "全角半角数字混用",
                "count": 1,
            })

        # 4. 多余空格模式
        double_spaces = list(re.finditer(r'[\u4e00-\u9fff]\s{2,}[\u4e00-\u9fff]', text))
        if double_spaces:
            errors.append({
                "type": "extra_spaces",
                "description": "中文间多余空格",
                "count": len(double_spaces),
                "examples": [m.group().strip() for m in double_spaces[:3]],
            })

        return errors

    @staticmethod
    def detect_obsolete_standards(text: str) -> List[Dict[str, Any]]:
        """检测引用的过期/废止标准"""
        found = []
        # 先找所有标准编号
        for match in ErrorPatternDetector.STANDARD_PATTERN.finditer(text):
            std_raw = match.group().replace(" ", "").replace("—", "-")
            # 标准化格式
            std_normalized = re.sub(r'\s+', '', std_raw)

            for obsolete, info in ErrorPatternDetector.OBSOLETE_STANDARDS.items():
                if obsolete.replace(" ", "") in std_normalized:
                    ctx_start = max(0, match.start() - 20)
                    ctx_end = min(len(text), match.end() + 20)
                    found.append({
                        "standard": std_raw,
                        "status": "已废止",
                        "replaced_by": info["replaced_by"],
                        "standard_name": info["name"],
                        "context": text[ctx_start:ctx_end],
                        "position": match.start(),
                    })
        return found

    @staticmethod
    def compare_error_patterns(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        比较多份文档的错误模式，找出共性错误

        documents: [{"id": ..., "company": ..., "text": ...}]
        """
        all_doc_errors = {}
        for doc in documents:
            text = doc.get("text", "")
            doc_id = doc["id"]
            all_doc_errors[doc_id] = {
                "company": doc.get("company", ""),
                "typos": ErrorPatternDetector.detect_typos(text),
                "punctuation": ErrorPatternDetector.detect_punctuation_errors(text),
                "obsolete_standards": ErrorPatternDetector.detect_obsolete_standards(text),
            }

        # 找共性错误
        alerts = []

        # 1. 共性错别字
        typo_by_doc = {}
        for doc_id, errs in all_doc_errors.items():
            typo_set = set(t["typo"] for t in errs["typos"])
            typo_by_doc[doc_id] = typo_set

        doc_ids = list(typo_by_doc.keys())
        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                common_typos = typo_by_doc[doc_ids[i]] & typo_by_doc[doc_ids[j]]
                if common_typos:
                    alerts.append({
                        "type": "common_typo",
                        "doc_a_id": doc_ids[i],
                        "doc_b_id": doc_ids[j],
                        "company_a": all_doc_errors[doc_ids[i]]["company"],
                        "company_b": all_doc_errors[doc_ids[j]]["company"],
                        "severity_score": min(len(common_typos) * 0.3, 1.0),
                        "common_errors": list(common_typos),
                        "description": f"发现 {len(common_typos)} 个相同错别字: {', '.join(list(common_typos)[:5])}",
                    })

        # 2. 共性标点错误模式
        punct_by_doc = {}
        for doc_id, errs in all_doc_errors.items():
            punct_types = set(p["type"] + ":" + p.get("description", "") for p in errs["punctuation"])
            punct_by_doc[doc_id] = punct_types

        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                common_punct = punct_by_doc.get(doc_ids[i], set()) & punct_by_doc.get(doc_ids[j], set())
                if len(common_punct) >= 2:  # 至少2种相同标点错误才报警
                    alerts.append({
                        "type": "common_punctuation_pattern",
                        "doc_a_id": doc_ids[i],
                        "doc_b_id": doc_ids[j],
                        "company_a": all_doc_errors[doc_ids[i]]["company"],
                        "company_b": all_doc_errors[doc_ids[j]]["company"],
                        "severity_score": min(len(common_punct) * 0.2, 0.8),
                        "common_patterns": list(common_punct),
                        "description": f"发现 {len(common_punct)} 种相同标点错误模式",
                    })

        # 3. 共性过期标准引用
        std_by_doc = {}
        for doc_id, errs in all_doc_errors.items():
            std_set = set(s["standard"] for s in errs["obsolete_standards"])
            std_by_doc[doc_id] = std_set

        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                common_stds = std_by_doc.get(doc_ids[i], set()) & std_by_doc.get(doc_ids[j], set())
                if common_stds:
                    alerts.append({
                        "type": "common_obsolete_standard",
                        "doc_a_id": doc_ids[i],
                        "doc_b_id": doc_ids[j],
                        "company_a": all_doc_errors[doc_ids[i]]["company"],
                        "company_b": all_doc_errors[doc_ids[j]]["company"],
                        "severity_score": min(len(common_stds) * 0.35, 1.0),
                        "common_standards": list(common_stds),
                        "description": f"引用了 {len(common_stds)} 个相同的过期标准: {', '.join(list(common_stds)[:3])}",
                    })

        max_score = max((a["severity_score"] for a in alerts), default=0.0)
        return {
            "total_alerts": len(alerts),
            "max_severity": round(max_score, 4),
            "alerts": sorted(alerts, key=lambda x: x["severity_score"], reverse=True),
            "per_document_errors": {
                doc_id: {
                    "company": errs["company"],
                    "typo_count": len(errs["typos"]),
                    "punctuation_error_count": len(errs["punctuation"]),
                    "obsolete_standard_count": len(errs["obsolete_standards"]),
                    "typos": [t["typo"] for t in errs["typos"]],
                    "obsolete_standards": [s["standard"] for s in errs["obsolete_standards"]],
                }
                for doc_id, errs in all_doc_errors.items()
            },
        }
