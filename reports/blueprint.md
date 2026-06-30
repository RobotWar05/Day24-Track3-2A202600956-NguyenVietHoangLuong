# CI/CD Blueprint: RAG Eval + Guardrail Stack

Student: Nguyen Viet Hoang Luong
Date: 2026-07-01

## Guard Stack Pipeline

| Layer | Tool | Measured P95 | Budget | Failure Action |
|---|---:|---:|---:|---|
| PII Detection | Presidio-compatible local recognizers | 0.07 ms | <10 ms | Reject/anonymize and log entity type |
| Topic/Jailbreak | NeMo-compatible input rail fallback | 0.02 ms | <300 ms | Block with refusal reason |
| RAG Pipeline | Day 18 hybrid search + rerank + DeepSeek generation | not in guard timer | <2000 ms target | Return fallback answer from retrieved context |
| Output Check | PII/output safety check | not separately benchmarked | <300 ms | Anonymize PII or replace unsafe answer |
| Total Guard | PII + input rail | 0.09 ms | <500 ms | Fail closed if guard stack errors |

## CI Gates

- RAGAS faithfulness >= 0.75 on the 50-question test set.
- RAGAS average score should not regress by more than 5 percent from the latest accepted report.
- Adversarial guard suite pass rate >= 90 percent. Current result: 18/20.
- Total guard P95 latency < 500 ms. Current result: 0.09 ms.
- `pytest tests/ -q` must pass before merge.
- `python check_lab.py` must pass before submission.

## Monitoring

| Metric | Current Lab Result | Alert Threshold | Action |
|---|---:|---:|---|
| RAGAS avg_score | 0.7004 | <0.65 | Inspect bottom-10 failures and retrieval traces |
| RAGAS faithfulness | 0.7166 | <0.75 | Tighten context-only prompt and review hallucinated answers |
| Worst RAGAS metric | answer_relevancy 0.6125 | <0.60 | Improve answer prompt and query decomposition |
| Dominant failure distribution | factual | factual dominates repeatedly | Audit short factual answers and expected answer format |
| LLM judge Cohen kappa | 0.5833 | <0.50 | Review judge prompt and human-label mapping |
| Guard adversarial pass rate | 18/20 | <18/20 | Add new jailbreak/off-topic patterns |
| Guard total P95 latency | 0.09 ms | >500 ms | Profile slow layer and fail closed |

## Actual Lab Results

| Item | Result |
|---|---:|
| RAGAS total questions | 50 |
| Factual avg_score | 0.9045 |
| Multi-hop avg_score | 0.5178 |
| Adversarial avg_score | 0.6574 |
| Overall avg_score | 0.7004 |
| Worst metric | answer_relevancy |
| Dominant failure distribution | factual |
| Cohen kappa | 0.5833 |
| Adversarial pass rate | 18/20 |
| Guard P95 latency | 0.09 ms |

## Notes And Improvements

The guard stack passes the lab threshold and meets the latency budget because the default path uses local PII and rule-based rail checks. For production, the NeMo LLM rail should be enabled and benchmarked separately because its latency will be much higher than the local fallback. The RAG evaluation shows factual questions score well overall, but the dominant failure metric is answer relevancy, which means some answers are too short or not shaped exactly to the question. The next technical improvement should be answer-format prompting plus multi-hop query decomposition before changing the retrieval stack.
