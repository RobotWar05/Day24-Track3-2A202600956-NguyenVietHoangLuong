# Phase A Failure Cluster Analysis

Source: `reports/ragas_50q.json`

## Summary

| Distribution | Count | Avg Score | Faithfulness | Answer Relevancy | Context Precision | Context Recall |
|---|---:|---:|---:|---:|---:|---:|
| factual | 20 | 0.9045 | 0.8917 | 0.9264 | 0.9000 | 0.9000 |
| multi_hop | 20 | 0.5178 | 0.5687 | 0.3526 | 0.4667 | 0.6833 |
| adversarial | 10 | 0.6574 | 0.6417 | 0.5045 | 0.8333 | 0.6500 |

Overall avg_score: 0.7004.

## Dominant Failure

Dominant failure metric: `answer_relevancy`.

Dominant failure distribution from the generated cluster matrix: `factual`.

Interpretation: the pipeline usually retrieves useful factual context, but several answers are too short or not aligned enough with the exact question wording. Multi-hop remains the weakest distribution by average score, which is expected because it requires combining documents and doing calculations.

## Bottom Failure Pattern

The bottom-10 list is led by multi-hop questions such as senior leave/salary and advance-payment penalty cases. These require both retrieval and arithmetic or policy version selection. When the answer is brief, RAGAS may mark relevancy or faithfulness low even if part of the retrieved context is correct.

## Recommended Fixes

- Improve the generation prompt to force direct answer format: final number, approval role, policy version, and short reason.
- For multi-hop questions, retrieve more candidate chunks before reranking and include parent context.
- Add a post-generation verifier for arithmetic questions.
- Keep version markers such as v2024/current policy in metadata and boost current-policy chunks.
