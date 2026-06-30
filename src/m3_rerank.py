from __future__ import annotations

"""Module 3: Reranking — Cross-encoder top-20 → top-3 + latency benchmark."""

import os, sys, time
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RERANK_TOP_K


_MODEL_CACHE = {}


@dataclass
class RerankResult:
    text: str
    original_score: float
    rerank_score: float
    metadata: dict
    rank: int


class CrossEncoderReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            if self.model_name not in _MODEL_CACHE:
                from sentence_transformers import CrossEncoder

                _MODEL_CACHE[self.model_name] = CrossEncoder(
                    self.model_name,
                    local_files_only=True,
                )
            self._model = _MODEL_CACHE[self.model_name]
        return self._model

    def rerank(self, query: str, documents: list[dict], top_k: int = RERANK_TOP_K) -> list[RerankResult]:
        """Rerank documents: top-20 → top-k."""
        if not documents or top_k <= 0:
            return []

        model = self._load_model()
        pairs = [(query, str(document.get("text", ""))) for document in documents]
        raw_scores = model.predict(pairs, show_progress_bar=False)

        import numpy as np

        scores = np.asarray(raw_scores, dtype=float).reshape(-1)
        if len(scores) != len(documents):
            raise RuntimeError(
                "CrossEncoder returned an unexpected number of scores: "
                f"{len(scores)} for {len(documents)} documents"
            )

        scored_documents = sorted(
            zip(scores, documents),
            key=lambda item: float(item[0]),
            reverse=True,
        )

        return [
            RerankResult(
                text=str(document.get("text", "")),
                original_score=float(document.get("score", 0.0)),
                rerank_score=float(score),
                metadata=dict(document.get("metadata", {})),
                rank=rank,
            )
            for rank, (score, document) in enumerate(scored_documents[:top_k], start=1)
        ]


class FlashrankReranker:
    """Lightweight alternative (<5ms). Optional."""
    def __init__(self):
        self._model = None

    def rerank(self, query: str, documents: list[dict], top_k: int = RERANK_TOP_K) -> list[RerankResult]:
        if not documents or top_k <= 0:
            return []

        from flashrank import Ranker, RerankRequest

        if self._model is None:
            self._model = Ranker()

        passages = [
            {
                "id": index,
                "text": str(document.get("text", "")),
                "original_score": float(document.get("score", 0.0)),
                "metadata": dict(document.get("metadata", {})),
            }
            for index, document in enumerate(documents)
        ]
        ranked = self._model.rerank(RerankRequest(query=query, passages=passages))

        return [
            RerankResult(
                text=str(item.get("text", "")),
                original_score=float(item.get("original_score", 0.0)),
                rerank_score=float(item.get("score", 0.0)),
                metadata=dict(item.get("metadata", {})),
                rank=rank,
            )
            for rank, item in enumerate(ranked[:top_k], start=1)
        ]


def benchmark_reranker(reranker, query: str, documents: list[dict], n_runs: int = 5) -> dict:
    """Benchmark latency over n_runs. (Đã implement sẵn)"""
    if n_runs <= 0:
        raise ValueError("n_runs must be greater than 0")
    times = []
    for _ in range(n_runs):
        start = time.perf_counter()
        reranker.rerank(query, documents)
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    return {"avg_ms": sum(times) / len(times), "min_ms": min(times), "max_ms": max(times)}


if __name__ == "__main__":
    query = "Nhân viên được nghỉ phép bao nhiêu ngày?"
    docs = [
        {"text": "Nhân viên được nghỉ 12 ngày/năm.", "score": 0.8, "metadata": {}},
        {"text": "Mật khẩu thay đổi mỗi 90 ngày.", "score": 0.7, "metadata": {}},
        {"text": "Thời gian thử việc là 60 ngày.", "score": 0.75, "metadata": {}},
    ]
    reranker = CrossEncoderReranker()
    for r in reranker.rerank(query, docs):
        print(f"[{r.rank}] {r.rerank_score:.4f} | {r.text}")
