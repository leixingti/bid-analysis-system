"""NER 实体交叉检测引擎 — 检测标书中的跨公司实体泄露（混名检测）"""
import re
from typing import Dict, Any, List


class EntityCrossDetector:
    """
    实体交叉检测器
    核心：检测 A 公司标书中是否出现 B 公司的人员姓名、电话号码、
    邮箱、地址、银行账号等实体信息
    实现方式：正则 + 规则引擎（轻量高效，不依赖 BERT）
    """

    PHONE_PATTERN = re.compile(
        r'(?<!\d)(?:1[3-9]\d{9}|0\d{2,3}-?\d{7,8})(?!\d)'
    )
    EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    BANK_ACCOUNT_PATTERN = re.compile(r'(?<!\d)\d{16,19}(?!\d)')
    FAX_PATTERN = re.compile(r'(?:传真|Fax)[：:\s]*(?:0\d{2,3}-?\d{7,8})')
    ID_CARD_PATTERN = re.compile(
        r'(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)'
    )
    COMPANY_PATTERN = re.compile(
        r'[\u4e00-\u9fff]{2,}(?:集团|公司|企业|工程|建设|建筑|市政|路桥|'
        r'设计院|研究院|咨询|监理|劳务|装饰|机电|安装|水利|环保|科技|'
        r'实业|投资|开发|物业|供应链)(?:有限)?(?:责任)?(?:公司|集团)?'
    )
    ROLE_KEYWORDS = [
        "项目经理", "技术负责人", "项目负责人", "法定代表人", "法人代表",
        "授权代表", "联系人", "负责人", "总工程师", "安全员", "质量员",
        "施工员", "资料员", "造价工程师", "监理工程师", "注册建造师",
    ]

    @staticmethod
    def extract_entities(text: str, company_name: str = "") -> Dict[str, Any]:
        """从文本中提取所有关键实体"""
        entities = {
            "persons": [], "phones": [], "emails": [],
            "companies": [], "bank_accounts": [], "id_cards": [], "fax_numbers": [],
        }
        if not text:
            return entities

        # 电话
        for m in EntityCrossDetector.PHONE_PATTERN.finditer(text):
            phone = m.group().replace("-", "").strip()
            if len(phone) >= 7 and phone not in entities["phones"]:
                entities["phones"].append(phone)
        # 邮箱
        for m in EntityCrossDetector.EMAIL_PATTERN.finditer(text):
            email = m.group().lower()
            if email not in entities["emails"]:
                entities["emails"].append(email)
        # 银行账号
        for m in EntityCrossDetector.BANK_ACCOUNT_PATTERN.finditer(text):
            acct = m.group()
            if EntityCrossDetector._is_likely_bank_account(acct) and acct not in entities["bank_accounts"]:
                entities["bank_accounts"].append(acct)
        # 身份证
        for m in EntityCrossDetector.ID_CARD_PATTERN.finditer(text):
            if m.group() not in entities["id_cards"]:
                entities["id_cards"].append(m.group())
        # 传真
        for m in EntityCrossDetector.FAX_PATTERN.finditer(text):
            if m.group() not in entities["fax_numbers"]:
                entities["fax_numbers"].append(m.group())
        # 公司名称
        for m in EntityCrossDetector.COMPANY_PATTERN.finditer(text):
            comp = m.group()
            if comp != company_name and comp not in entities["companies"]:
                entities["companies"].append(comp)
        # 人员
        entities["persons"] = EntityCrossDetector._extract_persons(text)
        return entities

    @staticmethod
    def cross_check(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """交叉检测：检查每份标书中是否出现其他投标人的实体"""
        alerts = []
        for doc in documents:
            if "entities" not in doc:
                doc["entities"] = EntityCrossDetector.extract_entities(
                    doc.get("text", ""), doc.get("company", ""))

        n = len(documents)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                cross_hits = EntityCrossDetector._find_cross_entities(documents[i], documents[j])
                if cross_hits:
                    total_sev = sum(h["severity_score"] for h in cross_hits)
                    alerts.append({
                        "doc_id": documents[i]["id"],
                        "doc_company": documents[i].get("company", ""),
                        "leaked_from_doc_id": documents[j]["id"],
                        "leaked_from_company": documents[j].get("company", ""),
                        "hit_count": len(cross_hits),
                        "severity_score": min(total_sev / 3.0, 1.0),
                        "hits": cross_hits,
                        "summary": (
                            f"{documents[i].get('company', 'A')} 的标书中发现 "
                            f"{documents[j].get('company', 'B')} 的 {len(cross_hits)} 项实体信息"
                        ),
                    })
        return alerts

    @staticmethod
    def batch_analyze(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量分析入口"""
        for doc in documents:
            doc["entities"] = EntityCrossDetector.extract_entities(
                doc.get("text", ""), doc.get("company", ""))
        alerts = EntityCrossDetector.cross_check(documents)
        max_score = max((a["severity_score"] for a in alerts), default=0.0)
        return {
            "total_alerts": len(alerts),
            "max_severity": round(max_score, 4),
            "alerts": sorted(alerts, key=lambda x: x["severity_score"], reverse=True),
            "entity_summary": {
                doc["id"]: {
                    "company": doc.get("company", ""),
                    "person_count": len(doc["entities"]["persons"]),
                    "phone_count": len(doc["entities"]["phones"]),
                    "email_count": len(doc["entities"]["emails"]),
                    "company_mentions": len(doc["entities"]["companies"]),
                } for doc in documents
            },
        }

    # ===== Internal =====

    @staticmethod
    def _extract_persons(text: str) -> List[Dict[str, str]]:
        persons, seen = [], set()
        for role in EntityCrossDetector.ROLE_KEYWORDS:
            for pattern in [rf'{role}[：:\s]+([^\s,，。；;：:\n]{{2,4}})',
                            rf'{role}\s*(?:为|是)\s*([^\s,，。；;：:\n]{{2,4}})']:
                for m in re.finditer(pattern, text):
                    name = m.group(1).strip()
                    if re.match(r'^[\u4e00-\u9fff]{2,4}$', name) and name not in seen:
                        start = max(0, m.start() - 20)
                        end = min(len(text), m.end() + 20)
                        persons.append({"name": name, "role": role, "context": text[start:end].strip()})
                        seen.add(name)
        return persons

    @staticmethod
    def _find_cross_entities(doc_a: Dict, doc_b: Dict) -> List[Dict[str, Any]]:
        hits = []
        text_a = doc_a.get("text", "")
        ent_b = doc_b.get("entities", {})
        if not text_a:
            return hits

        # B的人员出现在A中
        for person in ent_b.get("persons", []):
            name = person["name"]
            if name in text_a:
                pos = text_a.index(name)
                ctx = text_a[max(0, pos - 30):min(len(text_a), pos + len(name) + 30)]
                hits.append({
                    "type": "person_name", "entity": name,
                    "role_in_source": person.get("role", ""),
                    "context_in_target": ctx, "severity_score": 1.0,
                    "description": f"发现{doc_b.get('company', 'B')}的{person.get('role', '人员')}「{name}」出现在{doc_a.get('company', 'A')}的标书中",
                })
        # B的电话出现在A中
        for phone in ent_b.get("phones", []):
            if phone in text_a:
                hits.append({"type": "phone_number", "entity": phone, "severity_score": 0.9,
                             "description": f"发现{doc_b.get('company', 'B')}的电话 {phone} 出现在{doc_a.get('company', 'A')}的标书中"})
        # B的邮箱
        for email in ent_b.get("emails", []):
            if email in text_a.lower():
                hits.append({"type": "email", "entity": email, "severity_score": 0.8,
                             "description": f"发现{doc_b.get('company', 'B')}的邮箱 {email} 出现在{doc_a.get('company', 'A')}的标书中"})
        # B的公司名出现在A中
        comp_a, comp_b = doc_a.get("company", ""), doc_b.get("company", "")
        if comp_b and comp_b in text_a and comp_b != comp_a:
            hits.append({"type": "company_name", "entity": comp_b, "severity_score": 1.0,
                         "description": f"{comp_a}的标书中直接出现了其他投标人「{comp_b}」的公司名称"})
        # B的银行账号
        for acct in ent_b.get("bank_accounts", []):
            if acct in text_a:
                hits.append({"type": "bank_account", "entity": acct[:4] + "****" + acct[-4:],
                             "severity_score": 0.9,
                             "description": f"发现{doc_b.get('company', 'B')}的银行账号出现在{doc_a.get('company', 'A')}的标书中"})
        return hits

    @staticmethod
    def _is_likely_bank_account(s: str) -> bool:
        if len(s) < 16 or len(s) > 19:
            return False
        prefixes = ["621", "622", "623", "625", "626", "627", "628",
                     "403", "404", "512", "516", "518", "520", "524", "558"]
        return any(s.startswith(p) for p in prefixes)
