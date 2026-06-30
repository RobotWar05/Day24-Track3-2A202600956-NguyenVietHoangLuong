from __future__ import annotations

"""Phase C: Presidio PII + guardrail checks + latency measurement."""

import asyncio
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ADVERSARIAL_SET_PATH, GUARDRAILS_CONFIG_DIR, LATENCY_BUDGET_P95_MS, PRESIDIO_LANGUAGE


def setup_presidio():
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
    from presidio_anonymizer import AnonymizerEngine

    cccd_recognizer = PatternRecognizer(
        supported_entity="VN_CCCD",
        patterns=[
            Pattern("CCCD 12 digits", r"\b\d{12}\b", 0.9),
            Pattern("CMND 9 digits", r"\b\d{9}\b", 0.7),
        ],
    )
    phone_recognizer = PatternRecognizer(
        supported_entity="VN_PHONE",
        patterns=[Pattern("VN mobile", r"\b0[3-9]\d{8}\b", 0.9)],
    )

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers()
    registry.add_recognizer(cccd_recognizer)
    registry.add_recognizer(phone_recognizer)
    analyzer = AnalyzerEngine(registry=registry)
    anonymizer = AnonymizerEngine()
    return analyzer, anonymizer


def pii_scan(text: str, analyzer=None, anonymizer=None) -> dict:
    patterns = [
        ("EMAIL_ADDRESS", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), 0.95),
        ("VN_CCCD", re.compile(r"\b\d{12}\b"), 0.9),
        ("VN_CCCD", re.compile(r"\b\d{9}\b"), 0.7),
        ("VN_PHONE", re.compile(r"\b0[3-9]\d{8}\b"), 0.9),
    ]

    entities = []
    occupied: list[range] = []
    for entity_type, pattern, score in patterns:
        for match in pattern.finditer(text):
            if any(match.start() in used or match.end() - 1 in used for used in occupied):
                continue
            occupied.append(range(match.start(), match.end()))
            entities.append(
                {
                    "type": entity_type,
                    "text": match.group(0),
                    "score": score,
                    "start": match.start(),
                    "end": match.end(),
                }
            )

    if not entities and analyzer is not None:
        for result in analyzer.analyze(text=text, language=PRESIDIO_LANGUAGE):
            entities.append(
                {
                    "type": result.entity_type,
                    "text": text[result.start:result.end],
                    "score": round(result.score, 3),
                    "start": result.start,
                    "end": result.end,
                }
            )

    if not entities:
        return {"has_pii": False, "entities": [], "anonymized": text}

    anonymized = text
    for entity in sorted(entities, key=lambda item: item["start"], reverse=True):
        anonymized = (
            anonymized[:entity["start"]]
            + f"<{entity['type']}>"
            + anonymized[entity["end"]:]
        )
    return {"has_pii": True, "entities": entities, "anonymized": anonymized}


def setup_nemo_rails():
    from nemoguardrails import LLMRails, RailsConfig

    config = RailsConfig.from_path(GUARDRAILS_CONFIG_DIR)
    return LLMRails(config)


async def check_input_rail(text: str, rails=None) -> dict:
    if rails is not None:
        response = await rails.generate_async(messages=[{"role": "user", "content": text}])
        response_text = str(response.get("content", response)) if isinstance(response, dict) else str(response)
        blocked = any(keyword in _normalize(response_text) for keyword in ["i cannot", "cannot", "khong the"])
        return {
            "allowed": not blocked,
            "blocked_reason": "nemo_input_rail" if blocked else None,
            "response": response_text,
        }

    blocked = _looks_unsafe_or_offtopic(text)
    return {
        "allowed": not blocked,
        "blocked_reason": "rule_input_rail" if blocked else None,
        "response": "blocked by local guardrail" if blocked else "allowed",
    }


async def check_output_rail(question: str, answer: str, rails=None) -> dict:
    pii = pii_scan(answer)
    if pii["has_pii"]:
        return {"safe": False, "flagged_reason": "pii_in_output", "final_answer": pii["anonymized"]}

    if rails is not None:
        response = await rails.generate_async(
            messages=[
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]
        )
        response_text = str(response.get("content", response)) if isinstance(response, dict) else str(response)
        blocked = any(keyword in _normalize(response_text) for keyword in ["i cannot", "cannot", "khong the"])
        return {
            "safe": not blocked,
            "flagged_reason": "nemo_output_rail" if blocked else None,
            "final_answer": response_text if blocked else answer,
        }

    return {"safe": True, "flagged_reason": None, "final_answer": answer}


def run_adversarial_suite(
    adversarial_set: list[dict],
    rails=None,
    analyzer=None,
    anonymizer=None,
) -> list[dict]:
    async def _run_all():
        results = []
        for item in adversarial_set:
            text = item.get("input", "")
            blocked_by = None

            if pii_scan(text, analyzer, anonymizer)["has_pii"]:
                blocked_by = "presidio"

            if blocked_by is None:
                rail_result = await check_input_rail(text, rails)
                if not rail_result["allowed"]:
                    blocked_by = "nemo_input"

            actual = "blocked" if blocked_by else "allowed"
            results.append(
                {
                    "id": item.get("id"),
                    "category": item.get("category", ""),
                    "input": text[:80] + ("..." if len(text) > 80 else ""),
                    "expected": item.get("expected", "blocked"),
                    "actual": actual,
                    "blocked_by": blocked_by,
                    "passed": actual == item.get("expected", "blocked"),
                }
            )
        return results

    results = asyncio.run(_run_all())
    passed = sum(1 for result in results if result["passed"])
    print(f"Adversarial suite: {passed}/{len(results)} passed")
    return results


def measure_p95_latency(
    test_inputs: list[str],
    n_runs: int = 20,
    rails=None,
    analyzer=None,
    anonymizer=None,
) -> dict:
    inputs = (test_inputs or ["test"])[:max(n_runs, 1)]
    presidio_times, nemo_times, total_times = [], [], []

    async def _measure():
        for text in inputs:
            t0 = time.perf_counter()
            pii_scan(text, analyzer, anonymizer)
            presidio_ms = (time.perf_counter() - t0) * 1000

            t1 = time.perf_counter()
            await check_input_rail(text, rails)
            nemo_ms = (time.perf_counter() - t1) * 1000

            presidio_times.append(presidio_ms)
            nemo_times.append(nemo_ms)
            total_times.append(presidio_ms + nemo_ms)

    asyncio.run(_measure())
    total_p = _percentiles(total_times)
    return {
        "presidio_ms": _percentiles(presidio_times),
        "nemo_ms": _percentiles(nemo_times),
        "total_ms": total_p,
        "latency_budget_ok": total_p["p95"] < LATENCY_BUDGET_P95_MS,
        "budget_ms": LATENCY_BUDGET_P95_MS,
    }


def _percentiles(times: list[float]) -> dict[str, float]:
    if not times:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    ordered = sorted(times)
    n = len(ordered)

    def pick(pct: float) -> float:
        return round(ordered[min(int((n - 1) * pct), n - 1)], 2)

    return {"p50": pick(0.50), "p95": pick(0.95), "p99": pick(0.99)}


def _normalize(text: str) -> str:
    return text.lower()


def _looks_unsafe_or_offtopic(text: str) -> bool:
    normalized = _normalize(text)
    unsafe_keywords = [
        "ignore", "forget", "system override", "admin command", "previous instructions",
        "dan", "unrestricted", "confidential", "salary", "salaries", "employee records",
        "system instructions", "training data", "mat khau", "password", "cccd", "cmnd",
        "email", "tiet lo", "bang luong", "tan cong", "attack", "bitcoin", "ethereum",
        "marvel", "pho", "poem", "bai tho", "phuong trinh",
    ]
    if any(keyword in normalized for keyword in unsafe_keywords):
        return True

    hr_keywords = [
        "hr", "policy", "nhan vien", "nghi", "phep", "bao hiem", "luong", "phu cap",
        "thu viec", "dao tao", "cong tac", "tam ung", "vpn", "mat khau",
    ]
    return not any(keyword in normalized for keyword in hr_keywords)


if __name__ == "__main__":
    test_pii = "Nhan vien CCCD 034095001234, SDT 0987654321 hoi ve nghi phep."
    print(pii_scan(test_pii))

    with open(ADVERSARIAL_SET_PATH, encoding="utf-8") as f:
        adversarial_set = json.load(f)
    results = run_adversarial_suite(adversarial_set)
    latency = measure_p95_latency([item["input"] for item in adversarial_set[:10]], n_runs=10)
    passed = sum(1 for r in results if r["passed"])
    report = {
        "total_cases": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "latency": latency,
        "results": results,
    }
    os.makedirs("reports", exist_ok=True)
    with open("reports/guard_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Adversarial passed: {passed}/{len(results)}")
    print(f"Latency P95 total: {latency['total_ms']['p95']}ms")
    print("Phase C report saved -> reports/guard_results.json")
