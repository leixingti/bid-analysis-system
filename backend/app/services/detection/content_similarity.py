"""文本相似度检测引擎 — SimHash + TF-IDF Cosine Similarity + jieba 分词"""
import re
import math
from typing import Dict, Any, List, Tuple
from collections import Counter
import hashlib
import logging

logger = logging.getLogger(__name__)

# 🔧 优化：尝试导入jieba，提升中文分词质量
try:
    import jieba
    jieba.setLogLevel(logging.WARNING)  # 抑制jieba调试日志
    HAS_JIEBA = True
    logger.info("✅ jieba 分词引擎已加载")
except ImportError:
    HAS_JIEBA = False
    logger.warning("⚠️ jieba 未安装，使用基础分词（建议 pip install jieba）")

# 中文停用词（高频无意义词）
STOP_WORDS = set("""
的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有
看 好 自己 这 他 她 它 们 那 里 能 下 过 么 多 大 小 些 之 及 与 或 等 其 中
对 而 所 以 为 被 把 从 但 如 什么 如何 因为 所以 然后 其中 这个 那个 还是
可以 已经 需要 应该 进行 通过 根据 按照 关于 对于 由于 不同 相同 以及
本 该 项 个 条 份 种 方 面 次 件 部 类 组 级 层 段 章 节 款 则 条款
工程 建设 施工 项目 单位 公司 企业 投标 招标 采购 方案 技术 质量 安全
管理 服务 标准 要求 规定 规范 合同 文件 材料 设备 人员 负责 组织 实施
""".split())


class ContentSimilarityDetector:
    """
    文本相似度检测器
    使用 jieba 中文分词 + SimHash + TF-IDF 余弦相似度
    """

    @staticmethod
    def compute_similarity(text_a: str, text_b: str) -> Dict[str, Any]:
        """计算两段文本的综合相似度"""
        if not text_a or not text_b:
            return {"score": 0.0, "details": {"error": "Empty text"}, "similar_segments": []}

        # Clean text
        text_a_clean = ContentSimilarityDetector._clean_text(text_a)
        text_b_clean = ContentSimilarityDetector._clean_text(text_b)

        if len(text_a_clean) < 10 or len(text_b_clean) < 10:
            return {"score": 0.0, "details": {"error": "Text too short after cleaning"}, "similar_segments": []}

        # 1. SimHash 相似度 (快速粗筛)
        simhash_sim = ContentSimilarityDetector._simhash_similarity(text_a_clean, text_b_clean)

        # 2. TF-IDF Cosine 相似度 (更精确)
        cosine_sim = ContentSimilarityDetector._tfidf_cosine_similarity(text_a_clean, text_b_clean)

        # 3. Jaccard 相似度 (词级别)
        jaccard_sim = ContentSimilarityDetector._jaccard_similarity(text_a_clean, text_b_clean)

        # 4. 找出相似段落
        similar_segments = ContentSimilarityDetector._find_similar_segments(text_a, text_b)

        # 综合评分: 加权平均
        overall_score = (simhash_sim * 0.2 + cosine_sim * 0.5 + jaccard_sim * 0.3)

        return {
            "score": round(overall_score, 4),
            "details": {
                "simhash_similarity": round(simhash_sim, 4),
                "cosine_similarity": round(cosine_sim, 4),
                "jaccard_similarity": round(jaccard_sim, 4),
                "text_a_length": len(text_a),
                "text_b_length": len(text_b),
                "similar_segment_count": len(similar_segments),
                "tokenizer": "jieba" if HAS_JIEBA else "ngram",
            },
            "similar_segments": similar_segments[:20],  # Top 20
        }

    @staticmethod
    def batch_compare(documents: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        批量比对多份文档的两两相似度
        documents: [{"id": "...", "company": "...", "text": "..."}]
        """
        results = []
        n = len(documents)
        for i in range(n):
            for j in range(i + 1, n):
                sim = ContentSimilarityDetector.compute_similarity(
                    documents[i]["text"],
                    documents[j]["text"]
                )
                results.append({
                    "doc_a_id": documents[i]["id"],
                    "doc_b_id": documents[j]["id"],
                    "company_a": documents[i].get("company", ""),
                    "company_b": documents[j].get("company", ""),
                    "score": sim["score"],
                    "details": sim.get("details", {}),
                    "similar_segments": sim.get("similar_segments", []),
                })
        return results

    # ========== Internal Methods ==========

    @staticmethod
    def _clean_text(text: str) -> str:
        """清洗文本：去除多余空白、特殊字符"""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\u4e00-\u9fff\w\s.,;:!?。，；：！？、（）()]', '', text)
        return text.strip()

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """分词：优先使用 jieba，回退到 n-gram"""
        if HAS_JIEBA:
            # 使用 jieba 精确模式分词 + 去停用词
            words = jieba.lcut(text)
            return [w.strip() for w in words
                    if len(w.strip()) > 1 and w.strip() not in STOP_WORDS
                    and not w.strip().isspace()]
        else:
            # 回退：基于字符 n-gram + 空格分词
            tokens = []
            words = text.split()
            for word in words:
                if re.search(r'[\u4e00-\u9fff]', word):
                    for k in range(len(word) - 1):
                        tokens.append(word[k:k+2])
                else:
                    if len(word) > 1:
                        tokens.append(word.lower())
            return tokens

    @staticmethod
    def _simhash_similarity(text_a: str, text_b: str) -> float:
        """SimHash 相似度 (基于汉明距离)"""
        hash_a = ContentSimilarityDetector._compute_simhash(text_a)
        hash_b = ContentSimilarityDetector._compute_simhash(text_b)

        # Hamming distance
        xor = hash_a ^ hash_b
        hamming = bin(xor).count('1')

        # Convert to similarity (64-bit hash)
        return 1.0 - (hamming / 64.0)

    @staticmethod
    def _compute_simhash(text: str, bits: int = 64) -> int:
        """计算 SimHash 值"""
        tokens = ContentSimilarityDetector._tokenize(text)
        if not tokens:
            return 0
        v = [0] * bits

        for token in tokens:
            h = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)
            for i in range(bits):
                bitmask = 1 << i
                if h & bitmask:
                    v[i] += 1
                else:
                    v[i] -= 1

        fingerprint = 0
        for i in range(bits):
            if v[i] > 0:
                fingerprint |= (1 << i)
        return fingerprint

    @staticmethod
    def _tfidf_cosine_similarity(text_a: str, text_b: str) -> float:
        """TF-IDF 余弦相似度"""
        tokens_a = ContentSimilarityDetector._tokenize(text_a)
        tokens_b = ContentSimilarityDetector._tokenize(text_b)

        if not tokens_a or not tokens_b:
            return 0.0

        # Build vocabulary
        all_tokens = set(tokens_a) | set(tokens_b)

        # TF vectors
        tf_a = Counter(tokens_a)
        tf_b = Counter(tokens_b)

        # IDF weights (simple: log(2 / df))
        idf = {}
        for t in all_tokens:
            df = (1 if t in tf_a else 0) + (1 if t in tf_b else 0)
            idf[t] = math.log(2.0 / df) + 1.0

        # TF-IDF weighted cosine similarity
        dot_product = sum(tf_a.get(t, 0) * tf_b.get(t, 0) * idf[t] ** 2 for t in all_tokens)
        mag_a = math.sqrt(sum((tf_a.get(t, 0) * idf[t]) ** 2 for t in all_tokens))
        mag_b = math.sqrt(sum((tf_b.get(t, 0) * idf[t]) ** 2 for t in all_tokens))

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot_product / (mag_a * mag_b)

    @staticmethod
    def _jaccard_similarity(text_a: str, text_b: str) -> float:
        """Jaccard 相似度"""
        tokens_a = set(ContentSimilarityDetector._tokenize(text_a))
        tokens_b = set(ContentSimilarityDetector._tokenize(text_b))

        if not tokens_a and not tokens_b:
            return 0.0

        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b

        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _find_similar_segments(text_a: str, text_b: str, min_length: int = 15) -> List[Dict[str, Any]]:
        """找出相似段落（基于句子级别比对）"""
        segments = []

        # Split into sentences
        sents_a = re.split(r'[。！？\n]', text_a)
        sents_b = re.split(r'[。！？\n]', text_b)

        sents_a = [s.strip() for s in sents_a if len(s.strip()) >= min_length]
        sents_b = [s.strip() for s in sents_b if len(s.strip()) >= min_length]

        # 限制比较数量避免性能问题
        max_sents = 100
        sents_a = sents_a[:max_sents]
        sents_b = sents_b[:max_sents]

        for i, sa in enumerate(sents_a):
            for j, sb in enumerate(sents_b):
                sim = ContentSimilarityDetector._tfidf_cosine_similarity(sa, sb)
                if sim > 0.6:  # High sentence-level similarity
                    segments.append({
                        "text_a_segment": sa[:200],
                        "text_b_segment": sb[:200],
                        "similarity": round(sim, 4),
                        "position_a": i,
                        "position_b": j,
                    })

        # Sort by similarity
        segments.sort(key=lambda x: x["similarity"], reverse=True)
        return segments
