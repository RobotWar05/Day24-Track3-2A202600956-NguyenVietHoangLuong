from __future__ import annotations

"""Module 4: RAGAS Evaluation — 4 metrics + failure analysis."""

import os, sys, json, math
from dataclasses import asdict, dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (TEST_SET_PATH, OPENAI_API_KEY, OPENAI_BASE_URL,
                    OPENAI_MODEL, EMBEDDING_MODEL)


METRIC_NAMES = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)


def _empty_results() -> dict:
    return {**{name: 0.0 for name in METRIC_NAMES}, "per_question": []}


def _safe_float(value) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else 0.0
    except (TypeError, ValueError):
        return 0.0


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


def load_test_set(path: str = TEST_SET_PATH) -> list[dict]:
    """Load test set from JSON. (Đã implement sẵn)"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_ragas(questions: list[str], answers: list[str],
                   contexts: list[list[str]], ground_truths: list[str]) -> dict:
    """Run RAGAS evaluation."""
    lengths = {len(questions), len(answers), len(contexts), len(ground_truths)}
    if len(lengths) != 1:
        raise ValueError("questions, answers, contexts and ground_truths must have equal lengths")
    if not questions:
        return _empty_results()
    if not OPENAI_API_KEY:
        print("  ⚠️  RAGAS skipped: OPENAI_API_KEY is not configured.")
        return _empty_results()

    try:
        from datasets import Dataset
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_openai import ChatOpenAI
        from ragas import evaluate
        from ragas.metrics import (
            AnswerRelevancy,
            context_precision,
            context_recall,
            faithfulness,
        )

        dataset = Dataset.from_dict({
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        })

        llm_kwargs = {
            "model": OPENAI_MODEL,
            "temperature": 0,
            "openai_api_key": OPENAI_API_KEY,
        }
        if OPENAI_BASE_URL:
            llm_kwargs["openai_api_base"] = OPENAI_BASE_URL

        # DeepSeek's OpenAI-compatible endpoint currently accepts n=1 only.
        # RAGAS AnswerRelevancy defaults to strictness=3, which sends n=3.
        deepseek_answer_relevancy = AnswerRelevancy(strictness=1)

        evaluation = evaluate(
            dataset,
            metrics=[
                faithfulness,
                deepseek_answer_relevancy,
                context_precision,
                context_recall,
            ],
            llm=ChatOpenAI(**llm_kwargs),
            embeddings=HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"local_files_only": True},
            ),
        )
        frame = evaluation.to_pandas()

        invalid_metrics = []
        for metric_name in METRIC_NAMES:
            if metric_name not in frame.columns:
                frame[metric_name] = 0.0
                invalid_metrics.append(f"{metric_name}: missing column")
                continue
            for row_index, value in enumerate(frame[metric_name]):
                if _safe_float(value) == 0.0 and str(value).lower() in {"nan", "none"}:
                    invalid_metrics.append(f"{metric_name}: invalid row {row_index}")

        if invalid_metrics:
            details = ", ".join(invalid_metrics[:8])
            print(f"  Warning: RAGAS returned incomplete metrics; invalid values set to 0.0 ({details})")

        per_question = []
        for _, row in frame.iterrows():
            per_question.append(EvalResult(
                question=str(row.get("question", "")),
                answer=str(row.get("answer", "")),
                contexts=list(row.get("contexts", [])),
                ground_truth=str(row.get("ground_truth", "")),
                faithfulness=_safe_float(row.get("faithfulness")),
                answer_relevancy=_safe_float(row.get("answer_relevancy")),
                context_precision=_safe_float(row.get("context_precision")),
                context_recall=_safe_float(row.get("context_recall")),
            ))

        aggregates = {}
        for metric_name in METRIC_NAMES:
            values = [getattr(item, metric_name) for item in per_question]
            aggregates[metric_name] = sum(values) / len(values) if values else 0.0

        return {**aggregates, "per_question": per_question}
    except Exception as exc:
        print(f"  ⚠️  RAGAS evaluation failed: {type(exc).__name__}: {exc}")
        return _empty_results()


def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N worst questions using Diagnostic Tree."""
    if bottom_n <= 0 or not eval_results:
        return []

    diagnostic_tree = {
        "faithfulness": (
            "Câu trả lời có chi tiết không được context hỗ trợ.",
            "Siết prompt chỉ trả lời từ context, giảm temperature và kiểm tra context đầu vào.",
        ),
        "answer_relevancy": (
            "Câu trả lời không đi thẳng vào yêu cầu của câu hỏi.",
            "Cải thiện answer prompt và bảo đảm query không mất điều kiện quan trọng.",
        ),
        "context_precision": (
            "Retrieval trả về nhiều chunk không liên quan.",
            "Điều chỉnh BM25/Dense fusion, thêm reranking hoặc metadata filter.",
        ),
        "context_recall": (
            "Context thiếu thông tin cần để tạo câu trả lời đầy đủ.",
            "Kiểm tra chunking, tăng candidate retrieval hoặc bổ sung parent context.",
        ),
    }

    analyzed = []
    for item in eval_results:
        scores = {name: _safe_float(getattr(item, name, 0.0)) for name in METRIC_NAMES}
        worst_metric = min(scores, key=scores.get)
        average_score = sum(scores.values()) / len(scores)
        diagnosis, suggested_fix = diagnostic_tree[worst_metric]
        analyzed.append({
            "question": item.question,
            "expected": item.ground_truth,
            "got": item.answer,
            "contexts": item.contexts,
            "metrics": scores,
            "average_score": average_score,
            "worst_metric": worst_metric,
            "score": scores[worst_metric],
            "diagnosis": diagnosis,
            "suggested_fix": suggested_fix,
        })

    analyzed.sort(key=lambda item: item["average_score"])
    return analyzed[:bottom_n]


def save_report(results: dict, failures: list[dict], path: str = "ragas_report.json"):
    """Save evaluation report to JSON. (Đã implement sẵn)"""
    report = {
        "aggregate": {k: v for k, v in results.items() if k != "per_question"},
        "num_questions": len(results.get("per_question", [])),
        "per_question": [
            asdict(item) if isinstance(item, EvalResult) else item
            for item in results.get("per_question", [])
        ],
        "failures": failures,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Loaded {len(test_set)} test questions")
    print("Run pipeline.py first to generate answers, then call evaluate_ragas().")
