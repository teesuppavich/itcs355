# Lab 5 — Operating LLM Systems and Defending the Bill

## Part A — Defending the bill
### Task 1 — Managed pipeline
(not started)
### Task 2 — Least privilege
(identity table + which permission removed + what broke)
### Task 3 — Scheduled retraining
(three-strategy table for this system + chosen strategy + worst case)
### Task 4 — Portability test
(audit result, second adapter demo, half-page write-up with honest verdict)
### Task 5 — Cost accounting
(see reports/lab5-cost.md)
### Task 6 — Teardown
(screenshot of empty resource list + re-check after 24h)

## Part B — Operating an LLM step
### Task 7 — Evaluation gate
- Golden set: `evals/golden/mine.jsonl` (11 cases: grounding, guardrail, injection, insufficient-input)
- Baseline: prompt v1, 11/11, fixture `evals/fixtures/mine-baseline.jsonl`
- Changed prompt: v2 (injection rule removed), gate FAILED on mine-006
- Reproduce offline:
  `python scripts/llm_eval.py --golden evals/golden/mine.jsonl --responses evals/fixtures/mine-v2-regressed.jsonl --out reports/llm_eval-mine-v2.json --baseline reports/llm_eval-mine-baseline.json`
### Task 8 — Guardrail demonstrated
(failure, control, evidence, one command)
### Task 9 — Token bill
(three numbers with working + one-paragraph budget defence)
