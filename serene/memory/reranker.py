"""Cross-encoder reranker — the last-mile precision step.

The embedder is a *bi-encoder*: it turns the query and each memory into
vectors SEPARATELY, then compares. Fast, but it never looks at the query and
a memory *together*, so it misses nuance.

A *cross-encoder* reads (query, memory) as one pair and scores how well they
actually match. Much more accurate, but too slow to run over the whole DB —
so we only run it on the handful of candidates hybrid search already found.
"""
from sentence_transformers import CrossEncoder

_reranker = CrossEncoder("BAAI/bge-reranker-base")


def rerank(query, texts):
    """Score each text against the query. Returns floats in 0..1
    (higher = more relevant), aligned with the input list.

    CrossEncoder.predict already applies the model's Sigmoid activation,
    so its output is already a 0..1 relevance score — we use it directly.
    """
    if not texts:
        return []
    return _reranker.predict([(query, t) for t in texts])
