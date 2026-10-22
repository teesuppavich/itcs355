# Lab 5 Cost Report

## 1. Estimate vs actual

| Item | Estimate (reports/lab5-estimate.md) | Actual |
|---|---:|---:|
| Pipeline run fees | 8.0 THB | 2.02 THB (2 runs) |
| Step compute | 25.6 THB | 4.29 THB |
| Staging endpoint | 25.6 THB (4 h) | 341.61 THB (53.49 h) |
| Storage, logging, registry, other | 5.0 THB | 2.42 THB (includes Gemini 0.74) |
| Total | 64.2 THB | 350.34 THB |

Billing source: Cloud Billing > Reports, label `course=itcs355`, from 16 Oct 2026,
Credits not removed (list cost shown). Fetched on: 20 Oct 2026. Currency: THB, no FX needed.
Project filter: one project, no label filter. Net charge after free-trial credit: 0.00 THB.

Endpoint: deployed 16 Oct 09:09 UTC, undeployed 18 Oct 15:24 UTC (Cloud Audit Logs), about 54.3 h.
Formula estimate at 6.4 THB/h, 1 replica, 54.43 h: 348.35 THB. Billed: 341.61 THB
(core 222.42 + RAM 119.19). Billed hours: 213.96 core-h / 4 = 53.49 h and 855.85 GiB-h / 16 = 53.49 h.
The estimate assumed 4 h. The endpoint was left up about 54 h. Cause: I left the endpoint deployed after testing and had no reminder or automatic teardown, so it ran until I undeployed it manually on 18 Oct at about 15:24 UTC. Fix: add an undeploy step at the end of the test workflow and set a budget alert.

## 2. Cost per 1,000 predictions (e2-standard-4, 6.4 THB/h)

Throughput 13.046 req/s, the highest value in reports/lab3-load.md. Measured on
localhost against the FastAPI service, not on the deployed e2-standard-4, so these
are estimates.

| Utilisation | THB per 1k predictions |
|---:|---:|
| 0.05 | 2.7254 |
| 0.25 | 0.5451 |
| 0.80 | 0.1703 |

Note: throughput stayed at 11 to 13 req/s from 1 to 50 VUs while p50 rose from 87 ms
to 3.9 s, so the service was saturated at 1 VU. Real capacity on GCP is unknown.

## 3. Optimisation 6: shut down idle compute

Before: endpoint up about 54.4 h with no traffic after testing.
After: billed endpoint cost on 19 and 20 Oct = 0.43 THB (0.27 core-h, 1.06 GiB-h, about 0.07 h of the instance)
versus 341.61 THB before. Fetched on 20 Oct 2026; billing data can lag.

## 4. Rate verification

`e2-standard-4: 6.4` in src/costs.py vs billed 341.61 / 53.49 h = 6.386 THB/h (0.2% lower).\
Checked against the bill on 20 Oct 2026.

## 5. LLM step (Task 9)

Full working is in README_LAB5.md, Task 9. Summary:

- Cost per 1,000 requests: 6.355 THB (gemini-2.5-flash on Vertex AI, 330.82 input and 36.18 output tokens on average, read from the provider's usage fields; USD 0.30 / 2.50 per 1M tokens at about 33.5 THB/USD).
- `python scripts/llm_eval.py --model gemini-2.5-flash ...` prints 6.3416 because it rounds the averages to whole tokens. Without `--model` it prints the course's `small` table price, which is not Gemini's.
- Billing cross-check, 16 to 20 Oct 2026 (list cost before credits): Gemini 2.5 Flash input 37,169 tokens and output 4,459 tokens, 0.37 THB each. Rates computed from the table give 0.373 and 0.373, so the rate and FX assumption match the bill.
- Capping max_output_tokens: cap 60 saves 0.0 and passes 11/11; cap 40 saves 0.107 THB per 1k (about 1.7%) but fails 3 cases, so it is not an optimisation.
- Prompt cache: not used. The prompt is about 330 tokens, below Google's caching minimum.

