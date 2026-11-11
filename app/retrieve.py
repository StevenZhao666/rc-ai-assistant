"""中文检索：字符二元组 + BM25。

为什么不用向量库：
- 现在只有 111 条，暴力算一遍不到 1 毫秒
- 繁简混用（数据繁体、学生简体会问）用 OpenCC 统一到简体再建索引
- 等 L2 网页切片进来（几千条），再换 sqlite-vec / pgvector，接口不变
"""
import math
import re
from collections import Counter

from opencc import OpenCC

from .synonyms import expand

_cc = OpenCC("t2s")
_HAN = re.compile(r"[\u4e00-\u9fff]+")
_LATIN = re.compile(r"[a-z0-9]+")


def normalize(text: str) -> str:
    return _cc.convert(text or "").lower()


def tokenize(text: str) -> list[str]:
    """中文按二元组切，英文/数字按词切。'洗衣房开放时间' → 洗衣,衣房,房开,开放,放时,时间"""
    s = normalize(text)
    toks = _LATIN.findall(s)
    for run in _HAN.findall(s):
        if len(run) == 1:
            toks.append(run)
        for i in range(len(run) - 1):
            toks.append(run[i:i + 2])
    return toks


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tokens = [tokenize(d) for d in docs]
        self.tf = [Counter(t) for t in self.tokens]
        self.N = len(self.tokens)
        self.avgdl = (sum(len(t) for t in self.tokens) / self.N) if self.N else 0.0
        df = Counter()
        for t in self.tokens:
            df.update(set(t))
        self.idf = {w: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for w, n in df.items()}

    def scores(self, query: str) -> list[float]:
        q = tokenize(query)
        out = []
        for i, tf in enumerate(self.tf):
            dl = len(self.tokens[i]) or 1
            s = 0.0
            for w in q:
                f = tf.get(w)
                if not f:
                    continue
                s += self.idf.get(w, 0.0) * (f * (self.k1 + 1)) / (
                    f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                )
            out.append(s)
        return out


class Retriever:
    def __init__(self, items: list[dict]):
        self.items = items
        # 索引同时吃「问题」和「答案」，因为学生可能用答案里的词提问
        self.bm25 = BM25([f"{it['question']} {it['answer']}" for it in items])

    def search(self, query: str, k: int = 3) -> list[dict]:
        # 查询扩展：口语/英文/近义词 → 资料用词（猫 → 寵物，gym → 健身房）
        expanded = query + " " + " ".join(expand(query))
        scores = self.bm25.scores(expanded)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [dict(self.items[i], score=round(scores[i], 2)) for i in ranked if scores[i] > 0]
