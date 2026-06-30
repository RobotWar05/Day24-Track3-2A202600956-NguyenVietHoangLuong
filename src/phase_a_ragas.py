from __future__ import annotations

"""Phase A: RAGAS Production Evaluation."""

import json
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ANSWERS_PATH, TEST_SET_PATH

Distribution = str

DIAGNOSTIC_TREE = {
    "faithfulness": ("LLM hallucinating", "Tighten system prompt, lower temperature"),
    "context_recall": ("Missing relevant chunks", "Improve chunking or add BM25"),
    "context_precision": ("Too many irrelevant chunks", "Add reranking or metadata filter"),
    "answer_relevancy": ("Answer does not match question", "Improve prompt template"),
}


@dataclass
class RagasResult:
    question_id: int
    distribution: Distribution
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float

    @property
    def avg_score(self) -> float:
        return (
            self.faithfulness
            + self.answer_relevancy
            + self.context_precision
            + self.context_recall
        ) / 4

    @property
    def worst_metric(self) -> str:
        scores = {
            "faithfulness": self.faithfulness,
            "answer_relevancy": self.answer_relevancy,
            "context_precision": self.context_precision,
            "context_recall": self.context_recall,
        }
        return min(scores, key=scores.get)


def load_test_set_50q(path: str = TEST_SET_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_answers(path: str = ANSWERS_PATH) -> list[dict]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"answers_50q.json not found at {path}\n"
            "Run first: python setup_answers.py"
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_phase_a_report(
    results: list[RagasResult],
    clusters: dict,
    path: str = "reports/ragas_50q.json",
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    per_dist: dict[str, dict] = {}
    for dist in ["factual", "multi_hop", "adversarial"]:
        subset = [r for r in results if r.distribution == dist]
        if subset:
            per_dist[dist] = {
                "count": len(subset),
                "faithfulness": sum(r.faithfulness for r in subset) / len(subset),
                "answer_relevancy": sum(r.answer_relevancy for r in subset) / len(subset),
                "context_precision": sum(r.context_precision for r in subset) / len(subset),
                "context_recall": sum(r.context_recall for r in subset) / len(subset),
                "avg_score": sum(r.avg_score for r in subset) / len(subset),
            }

    report = {
        "total_questions": len(results),
        "per_distribution": per_dist,
        "failure_clusters": clusters,
        "bottom_10": bottom_10(results),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Phase A report saved -> {path}")


def group_by_distribution(test_set: list[dict]) -> dict[str, list[dict]]:
    groups = {"factual": [], "multi_hop": [], "adversarial": []}
    for item in test_set:
        dist = item.get("distribution")
        if dist in groups:
            groups[dist].append(item)
    return groups


def run_ragas_50q(answers: list[dict]) -> list[RagasResult]:
    try:
        from src.m4_eval import evaluate_ragas
    except ImportError as exc:
        print(f"Cannot import evaluate_ragas: {exc}")
        return []

    questions = [item.get("question", "") for item in answers]
    answer_texts = [item.get("answer", "") for item in answers]
    contexts = [item.get("contexts", []) for item in answers]
    ground_truths = [item.get("ground_truth", "") for item in answers]

    raw = evaluate_ragas(questions, answer_texts, contexts, ground_truths)
    per_question = raw.get("per_question", []) if isinstance(raw, dict) else []

    results: list[RagasResult] = []
    for item, metric in zip(answers, per_question):
        results.append(
            RagasResult(
                question_id=int(item.get("id", item.get("question_id", 0))),
                distribution=item.get("distribution", ""),
                question=item.get("question", ""),
                answer=item.get("answer", ""),
                contexts=item.get("contexts", []),
                ground_truth=item.get("ground_truth", ""),
                faithfulness=float(getattr(metric, "faithfulness", 0.0)),
                answer_relevancy=float(getattr(metric, "answer_relevancy", 0.0)),
                context_precision=float(getattr(metric, "context_precision", 0.0)),
                context_recall=float(getattr(metric, "context_recall", 0.0)),
            )
        )
    return results


def bottom_10(results: list[RagasResult]) -> list[dict]:
    output = []
    for rank, result in enumerate(sorted(results, key=lambda r: r.avg_score)[:10], start=1):
        diagnosis, fix = DIAGNOSTIC_TREE.get(
            result.worst_metric,
            ("Unknown failure", "Inspect retrieval and generation traces"),
        )
        output.append(
            {
                "rank": rank,
                "question_id": result.question_id,
                "distribution": result.distribution,
                "question": result.question,
                "avg_score": round(result.avg_score, 4),
                "worst_metric": result.worst_metric,
                "diagnosis": diagnosis,
                "suggested_fix": fix,
            }
        )
    return output


def cluster_analysis(results: list[RagasResult]) -> dict:
    distributions = ["factual", "multi_hop", "adversarial"]
    metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    matrix = {metric: {dist: 0 for dist in distributions} for metric in metrics}

    for result in results:
        if result.worst_metric in matrix and result.distribution in matrix[result.worst_metric]:
            matrix[result.worst_metric][result.distribution] += 1

    dominant_dist = max(
        distributions,
        key=lambda dist: sum(counts[dist] for counts in matrix.values()),
    )
    dominant_metric = max(matrix, key=lambda metric: sum(matrix[metric].values()))
    _, fix = DIAGNOSTIC_TREE.get(
        dominant_metric,
        ("Unknown failure", "Inspect retrieval and generation traces"),
    )

    return {
        "matrix": matrix,
        "dominant_failure_distribution": dominant_dist,
        "dominant_failure_metric": dominant_metric,
        "insight": (
            f"Dominant failure is {dominant_metric} in {dominant_dist}. "
            f"Recommended next fix: {fix}."
        ),
    }


if __name__ == "__main__":
    test_set = load_test_set_50q()
    print(f"Loaded {len(test_set)} questions")

    groups = group_by_distribution(test_set)
    for dist, questions in groups.items():
        print(f"  {dist}: {len(questions)} questions")

    answers = load_answers()
    results = run_ragas_50q(answers)
    if results:
        clusters = cluster_analysis(results)
        save_phase_a_report(results, clusters)
        print(f"Dominant failure: {clusters['dominant_failure_metric']} / {clusters['dominant_failure_distribution']}")
    else:
        print("No RAGAS results. Check answers_50q.json, API key, and m4_eval dependencies.")
