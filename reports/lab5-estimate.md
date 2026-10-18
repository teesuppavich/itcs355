# Lab 5 cost estimate (made before running Task 1)

Assumptions
- Pipeline runs: 8, most expected to fail early while debugging
- Compute per run: 30 minutes of container steps at 6.4 THB/hour (e2-standard-4 rate from src/costs.py)
- Staging endpoint up: 4 hours at 6.4 THB/hour
- Pipeline run fee: USD 0.03 per run, about 1.0 THB at 33.5 THB/USD
- Spot discount on the train step ignored, so the estimate is conservative

Estimate
- Pipeline run fees: 8.0 THB
- Step compute: 25.6 THB
- Staging endpoint: 25.6 THB
- Storage, logging, registry: 5.0 THB
- Total: 64.2 THB

Not included: second-provider charges from Task 4.
