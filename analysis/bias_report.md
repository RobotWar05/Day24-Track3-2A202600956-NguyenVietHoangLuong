# Phase B Bias Report

Source: `reports/judge_results.json`

## Summary

| Metric | Result |
|---|---:|
| Evaluated items | 10 |
| Judge model | deepseek-chat |
| Cohen kappa | 0.5833 |
| Position bias rate | 0.2000 |
| Position bias count | 2 |
| Verbosity bias | 0.5710 |

## Interpretation

Cohen kappa is moderate and close to the rubric bonus threshold of 0.6. The judge agrees with human labels better than chance, but the result is not strong enough to treat as production-grade without more calibration.

Position bias is present but not dominant: 2 out of 10 swap-and-average checks were inconsistent. Keeping the swap pass is justified.

Verbosity bias is noticeable. Longer answers often win when the judge is decisive, so the judge prompt should keep emphasizing accuracy and completeness over length.

## Recommended Fixes

- Use a stricter judge rubric with separate scores for correctness, completeness, citation support, and conciseness.
- Add few-shot judge examples from the human-labeled set.
- Keep swap-and-average enabled for all pairwise comparisons.
- Increase the human-labeled calibration set beyond 10 examples before using kappa as a CI gate.
