# Lab 5 Cost Report

## 1. Estimate vs actual

| Item | Estimate (reports/lab5-estimate.md) | Actual |
|---|---:|---:|
| Pipeline run fees | 8.0 THB | TODO (from bill) |
| Step compute | 25.6 THB | TODO |
| Staging endpoint | 25.6 THB (4 h) | TODO (see below) |
| Storage, logging, registry | 5.0 THB | TODO |
| Total | 64.2 THB | TODO |

Billing source: Cloud Billing > Reports, label `course=itcs355`, from 16 Oct 2026,
Credits not removed. Fetched on: TODO (date). Currency: TODO. FX rate used: TODO.

Endpoint: deployed 16 Oct 09:09 UTC, undeployed 18 Oct 15:35 UTC, about 54.4 h.
Formula estimate at 6.4 THB/h, 1 replica: 348.35 THB. Billed: TODO.
The estimate assumed 4 h. The endpoint was left up about 54 h. Cause: TODO (your own words).

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
After: billed endpoint cost on 19 and 20 Oct = TODO (expected 0). Fetched on: TODO.

## 4. Rate verification

`e2-standard-4: 6.4` in src/costs.py compared with billed rate (usage hours and cost): TODO.
