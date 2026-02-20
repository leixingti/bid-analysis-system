"""文本相似度检测引擎 — SimHash + TF-IDF Cosine Similarity"""
import re
import math
from typing import Dict, Any, List, Tuple
from collections import Counter
import hashlib


class ContentSimilarityDetector:
    """
    文本相似度检测器
    Phase 1: SimHash + TF-IDF 余弦相似度 (轻量级，不依赖BERT)
    """

    @staticmethod
    def compute_similarity(text_a: str, text_b: str) -> Dict[str, Any]:
        """计算两段文本的综合相似度"""
        if not text_a or not text_b:
            return {"score": 0.0, "details": {"error": "Empty text"}, "similar_segments": []}

        # Clean text
        text_a_clean = ContentSimilarityDetector._clean_text(text_a)
        text_b_clean = ContentSimilarityDetector._clean_text(text_b)

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
        text = re.sub(r'[^\u4e00-\u9fff\w\s.,;:!?。，；：！？]', '', text)
        return text.strip()

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """中文分词（简单版：基于字符n-gram + 空格分词）"""
        # Simple char-based tokenization for Chinese
        tokens = []
        # Split by spaces for non-Chinese
        words = text.split()
        for word in words:
            if re.search(r'[\u4e00-\u9fff]', word):
                # Chinese: use 2-gram
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

        # Cosine similarity
        dot_product = sum(tf_a.get(t, 0) * tf_b.get(t, 0) for t in all_tokens)
        mag_a = math.sqrt(sum(v ** 2 for v in tf_a.values()))
        mag_b = math.sqrt(sum(v ** 2 for v in tf_b.values()))

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
    def _find_similar_segments(text_a: str, text_b: str, min_length: int = 20) -> List[Dict[str, Any]]:
        """找出相似段落（基于最长公共子串）"""
        segments = []

        # Split into sentences
        sents_a = re.split(r'[。！？\n]', text_a)
        sents_b = re.split(r'[。！？\n]', text_b)

        sents_a = [s.strip() for s in sents_a if len(s.strip()) >= min_length]
        sents_b = [s.strip() for s in sents_b if len(s.strip()) >= min_length]

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
