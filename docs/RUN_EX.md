# Run Guide - Lab 24 Production Eval + Guardrail Stack

This guide explains how to run, verify, and regenerate the Lab 24 outputs.

## 1. What This Repo Contains

Main deliverables:

- `src/phase_a_ragas.py`: Phase A RAGAS evaluation logic.
- `src/phase_b_judge.py`: Phase B LLM-as-Judge logic.
- `src/phase_c_guard.py`: Phase C guardrail logic.
- `answers_50q.json`: generated answers for the 50-question test set.
- `reports/ragas_50q.json`: Phase A generated report.
- `reports/judge_results.json`: Phase B generated report.
- `reports/guard_results.json`: Phase C generated report.
- `reports/blueprint.md`: CI/CD blueprint filled with real lab results.
- `analysis/failure_clusters.md`: Phase A failure analysis.
- `analysis/bias_report.md`: Phase B bias analysis.

Local-only files are ignored by git:

- `.env`: API keys and secrets.
- `venv/`: local Python virtual environment.
- `.codex/`: local run logs.
- `TomTat.md`, `todo.md`, `history.md`, `.agents/`: local AI coordination notes.

## 2. Environment Setup

Recommended runtime:

- Windows PowerShell.
- Python 3.11.
- Docker Desktop.
- Microsoft Visual C++ Build Tools if `annoy` fails to build during install.

Why these components are needed:

- Python 3.11: runs the lab scripts and tests.
- Docker Desktop: runs Qdrant, the vector database used by the copied Day 18 RAG search pipeline.
- `requirements.txt`: installs RAGAS, LangChain, Qdrant client, sentence-transformers, NeMo Guardrails, Presidio, and other lab dependencies.
- `en_core_web_lg`: spaCy model needed by Presidio-related NLP components.
- Microsoft Visual C++ Build Tools: only needed on Windows if native packages such as `annoy` cannot build during `pip install`.
- `pytest`: needed because the starter `requirements.txt` does not include it, but `check_lab.py` runs the test suite.

Create and activate a virtual environment:

```powershell
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_lg
pip install pytest
```

If dependency install fails on `annoy`, install Microsoft Visual Studio Build Tools with the C++ build workload, then run `pip install -r requirements.txt` again.

## 3. API Key Setup

Do not commit `.env`.

Create your own `.env` from the example:

```powershell
Copy-Item .env.example .env
```

For DeepSeek OpenAI-compatible API, fill `.env` like this:

```env
DEEPSEEK_API_KEY=your_key_here
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
JUDGE_MODEL=deepseek-chat
```

You may also use `OPENAI_API_KEY` instead of `DEEPSEEK_API_KEY` if your provider uses the default OpenAI endpoint.

## 4. Start Qdrant

The copied Day 18 pipeline uses Qdrant.

```powershell
docker compose up -d
docker ps --filter "publish=6333"
```

Expected: a Qdrant container is running on ports `6333` and `6334`.

After finishing the lab, stop Qdrant:

```powershell
docker compose down
```

Use `docker compose down -v` only if you intentionally want to delete the Qdrant volume/data.

## 5. Generate Answers

This step builds the Day 18 RAG pipeline, enriches chunks, indexes documents, reranks results, and generates 50 answers.

```powershell
$env:PYTHONIOENCODING = "utf-8"
python setup_answers.py
```

Expected output:

- Day 18 source files found: `6/6`.
- Loaded `50` questions.
- Saved `answers_50q.json`.

On the verified run for this repo:

- 97 chunks were enriched.
- 50 answers were generated.
- Total query time was about 895 seconds.

## 6. Run Phase Reports

Run Phase A:

```powershell
$env:PYTHONIOENCODING = "utf-8"
python src/phase_a_ragas.py
```

Expected output:

- `reports/ragas_50q.json`
- `total_questions = 50`

Run Phase B:

```powershell
$env:PYTHONIOENCODING = "utf-8"
python src/phase_b_judge.py
```

Expected output:

- `reports/judge_results.json`
- Cohen kappa printed in terminal.

Run Phase C:

```powershell
$env:PYTHONIOENCODING = "utf-8"
python src/phase_c_guard.py
```

Expected output:

- `reports/guard_results.json`
- adversarial pass count.
- guard latency P95.

## 7. Verify Before Submission

Run unit tests:

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -m pytest tests/ -q --tb=short
```

Expected for the verified run:

```text
40 passed
```

Run the lab checker:

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:PATH = (Join-Path (Get-Location) "venv\Scripts") + ";" + $env:PATH
python check_lab.py
```

Expected for the verified run:

```text
Score: 22/22 checks passed
Sẵn sàng nộp bài!
```

Check there are no remaining TODO markers:

```powershell
rg "# TODO" src -g "phase_*.py"
```

Expected: no output.

## 8. Current Verified Results

From the generated reports:

- RAGAS total questions: 50.
- Overall RAGAS avg_score: 0.7004.
- Factual avg_score: 0.9045.
- Multi-hop avg_score: 0.5178.
- Adversarial avg_score: 0.6574.
- Worst RAGAS metric: `answer_relevancy`.
- Dominant failure distribution: `factual`.
- Judge Cohen kappa: 0.5833.
- Guard adversarial pass rate: 18/20.
- Guard P95 latency: 0.09 ms.

## 9. Notes

If you only need to inspect the submitted state, the generated `answers_50q.json` and report files are already included. If you need to regenerate them, you must provide your own `.env` API key and run the commands above.

Phase C uses a local rule fallback by default, so the measured latency is very low. If you enable full NeMo LLM rails, rerun the latency measurement before reporting production numbers.

Before pushing code, make sure these local-only files are not committed:

- `.env`
- `venv/`
- `.codex/`
- `.pytest_cache/`
- `__pycache__/`
