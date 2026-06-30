from __future__ import annotations

"""Phase B: LLM-as-Judge with swap-and-average and bias analysis."""

import json
import os
import sys
from dataclasses import asdict, dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import HUMAN_LABELS_PATH, JUDGE_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL


@dataclass
class JudgeResult:
    question: str
    answer_a: str
    answer_b: str
    winner_pass1: str
    winner_pass2: str
    final_winner: str
    reasoning_pass1: str
    reasoning_pass2: str
    position_consistent: bool
    scores_pass1: dict = field(default_factory=dict)
    scores_pass2: dict = field(default_factory=dict)


def pairwise_judge(
    question: str,
    answer_a: str,
    answer_b: str,
    use_llm: bool = False,
) -> dict:
    if use_llm and OPENAI_API_KEY:
        try:
            from openai import OpenAI

            client_kwargs = {"api_key": OPENAI_API_KEY}
            if OPENAI_BASE_URL:
                client_kwargs["base_url"] = OPENAI_BASE_URL
            client = OpenAI(**client_kwargs)
            prompt = (
                "Judge the better RAG answer. Consider accuracy, completeness, "
                "and conciseness. Return only JSON with winner, reasoning, scores.\n\n"
                f"Question: {question}\n\nAnswer A:\n{answer_a}\n\nAnswer B:\n{answer_b}"
            )
            response = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[
                    {"role": "system", "content": "You are a strict RAG judge. Return only JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                timeout=30,
            )
            payload = json.loads(response.choices[0].message.content or "{}")
            winner = payload.get("winner", "tie")
            scores = payload.get("scores", {})
            if winner in {"A", "B", "tie"}:
                return {
                    "winner": winner,
                    "reasoning": str(payload.get("reasoning", "")),
                    "scores": {
                        "A": _clamp(scores.get("A", 0.0)),
                        "B": _clamp(scores.get("B", 0.0)),
                    },
                }
        except Exception as exc:
            print(f"LLM judge fallback used: {type(exc).__name__}: {exc}")

    score_a = _heuristic_answer_score(question, answer_a)
    score_b = _heuristic_answer_score(question, answer_b)
    if abs(score_a - score_b) < 0.05:
        return {"winner": "tie", "reasoning": "", "scores": {"A": score_a, "B": score_b}}
    if score_a > score_b:
        return {
            "winner": "A",
            "reasoning": "Answer A has stronger overlap and useful specificity.",
            "scores": {"A": score_a, "B": score_b},
        }
    return {
        "winner": "B",
        "reasoning": "Answer B has stronger overlap and useful specificity.",
        "scores": {"A": score_a, "B": score_b},
    }


def _heuristic_answer_score(question: str, answer: str) -> float:
    q_terms = {token.strip(".,:;!?()[]").lower() for token in question.split() if len(token) > 2}
    a_terms = {token.strip(".,:;!?()[]").lower() for token in answer.split() if len(token) > 2}
    overlap = len(q_terms & a_terms) / max(len(q_terms), 1)
    length_score = min(len(answer.split()) / 40, 1.0)
    number_bonus = 0.1 if any(char.isdigit() for char in answer) else 0.0
    return round(min(0.65 * overlap + 0.25 * length_score + number_bonus, 1.0), 3)


def _clamp(value) -> float:
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def swap_and_average(
    question: str,
    answer_a: str,
    answer_b: str,
    use_llm: bool = False,
) -> JudgeResult:
    pass1 = pairwise_judge(question, answer_a, answer_b, use_llm=use_llm)
    pass2_raw = pairwise_judge(question, answer_b, answer_a, use_llm=use_llm)

    swap_map = {"A": "B", "B": "A", "tie": "tie"}
    winner_pass1 = pass1.get("winner", "tie")
    winner_pass2 = swap_map.get(pass2_raw.get("winner", "tie"), "tie")
    final = winner_pass1 if winner_pass1 == winner_pass2 else "tie"
    position_consistent = winner_pass1 == winner_pass2

    return JudgeResult(
        question=question,
        answer_a=answer_a,
        answer_b=answer_b,
        winner_pass1=winner_pass1,
        winner_pass2=winner_pass2,
        final_winner=final,
        reasoning_pass1=pass1.get("reasoning", ""),
        reasoning_pass2=pass2_raw.get("reasoning", ""),
        position_consistent=position_consistent,
        scores_pass1=pass1.get("scores", {}),
        scores_pass2={
            "A": pass2_raw.get("scores", {}).get("B", 0.0),
            "B": pass2_raw.get("scores", {}).get("A", 0.0),
        },
    )


def cohen_kappa(judge_labels: list[int], human_labels: list[int]) -> float:
    if len(judge_labels) != len(human_labels):
        raise ValueError("judge_labels and human_labels must have equal length")
    n = len(judge_labels)
    if n == 0:
        return 0.0

    observed = sum(j == h for j, h in zip(judge_labels, human_labels)) / n
    labels = set(judge_labels) | set(human_labels)
    expected = sum(
        (judge_labels.count(label) / n) * (human_labels.count(label) / n)
        for label in labels
    )
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1 - expected)


def bias_report(judge_results: list[JudgeResult]) -> dict:
    total = len(judge_results)
    if total == 0:
        return {
            "total_judged": 0,
            "position_bias_rate": 0.0,
            "position_bias_count": 0,
            "verbosity_bias": 0.0,
            "verbosity_details": {"a_wins_a_longer": 0, "b_wins_b_longer": 0, "total_decisive": 0},
            "interpretation": "No judge results to analyze.",
        }

    position_bias_count = sum(1 for result in judge_results if not result.position_consistent)
    decisive = [result for result in judge_results if result.final_winner in {"A", "B"}]
    a_wins_a_longer = sum(
        1 for result in decisive
        if result.final_winner == "A" and len(result.answer_a) > len(result.answer_b)
    )
    b_wins_b_longer = sum(
        1 for result in decisive
        if result.final_winner == "B" and len(result.answer_b) > len(result.answer_a)
    )
    verbosity_bias = (a_wins_a_longer + b_wins_b_longer) / len(decisive) if decisive else 0.0
    position_bias_rate = position_bias_count / total
    interpretation = (
        "Position bias is high; keep swap-and-average in production."
        if position_bias_rate > 0.3
        else "Position bias is low for this sample."
    )
    return {
        "total_judged": total,
        "position_bias_rate": round(position_bias_rate, 3),
        "position_bias_count": position_bias_count,
        "verbosity_bias": round(verbosity_bias, 3),
        "verbosity_details": {
            "a_wins_a_longer": a_wins_a_longer,
            "b_wins_b_longer": b_wins_b_longer,
            "total_decisive": len(decisive),
        },
        "interpretation": interpretation,
    }


def _winner_to_correct_label(result: JudgeResult) -> int:
    """A is the model answer and B is the human note/reference."""
    return 1 if result.final_winner in {"A", "tie"} else 0


def run_human_label_eval(use_llm: bool = False) -> dict:
    with open(HUMAN_LABELS_PATH, encoding="utf-8") as f:
        human_data = json.load(f)

    judge_results: list[JudgeResult] = []
    judge_labels: list[int] = []
    human_labels: list[int] = []

    for item in human_data:
        result = swap_and_average(
            item.get("question", ""),
            item.get("model_answer", ""),
            item.get("human_note", ""),
            use_llm=use_llm,
        )
        judge_results.append(result)
        judge_labels.append(_winner_to_correct_label(result))
        human_labels.append(int(item.get("human_label", 0)))

    llm_used = use_llm and bool(OPENAI_API_KEY)
    return {
        "total_items": len(judge_results),
        "use_llm": llm_used,
        "judge_model": JUDGE_MODEL if llm_used else "heuristic",
        "cohen_kappa": round(cohen_kappa(judge_labels, human_labels), 4),
        "bias_report": bias_report(judge_results),
        "items": [
            {
                "question_id": item.get("question_id"),
                "human_label": item.get("human_label"),
                "judge_label": judge_label,
                "result": asdict(result),
            }
            for item, judge_label, result in zip(human_data, judge_labels, judge_results)
        ],
    }


def save_judge_report(report: dict, path: str = "reports/judge_results.json") -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Phase B report saved -> {path}")


if __name__ == "__main__":
    report = run_human_label_eval(use_llm=True)
    save_judge_report(report)
    print(f"Cohen kappa: {report['cohen_kappa']:.3f}")
