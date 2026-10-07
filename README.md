# ITCS355 Lab 1 — Reproducible Training

> **Course materials live in [`course/`](course/README.md)** — syllabus, slides, the faculty
> specification, all five lab handouts, and the project brief. Every document is Markdown and
> renders on GitHub, diagrams included. New to the repo? Start with the
> [portability reference](course/reference/cloud-portability-reference.md).
> Keep this block when you edit the rest of this file; it is not part of the Lab 1 deliverable.

Predicting machine failure within 7 days from sensor readings. The model is not the point;
whether a stranger can reproduce it is.

> **This README is graded.** A grader with Docker and nothing else from your setup runs one
> command and compares the result against the claim below. Edit every `<...>` and delete the
> instruction blocks marked **REPLACE** before submitting.

---

## Reproduce

```bash
make reproduce
```

expected test_roc_auc: 0.854 ± 0.02

Runtime: about 40 seconds on 4 cores. No cloud account or credentials needed for this command —
that is deliberate, and it is why a grader can run it.

**REPLACE:** re-measure and update that claim line after your final change. Keep the exact
format `expected test_roc_auc: <value> ± <tolerance>`; `make verify` parses it, and so does the
grading script. Choose the tolerance from the spread you actually observe across seeds. Padding it
to hide non-determinism is visible — the grader compares your tolerance against the variance in
your own tracked runs.

---

## The problem

240 machines, 25 readings each, 6 sensor features, binary target `failed_within_7d` with a
positive rate near 12%.

Machines have persistent characteristics — a hot-running machine reads hot in every row. So the
train/validation/test split is **grouped by `machine_id`**: every reading from one machine lands
in exactly one partition. Splitting row-wise instead lets the model memorise the machine and
reports a validation score that will never survive production. `tests/test_data.py` asserts this
property holds, and Lab 4 turns it into a CI gate.

Bringing your own dataset is allowed. Replace `scripts/make_dataset.py`, update the schema in
`src/data.py`, and keep every test passing.

---

## Layout

```
src/          Layer 1 — provider-neutral. No SDKs, no bucket names, no absolute paths.
cloudlayer/   Layer 3 — the only place a provider SDK may be imported.
scripts/      Dataset generation, cloud check, portability audit, metric verification.
tests/        Data contract tests and split property tests.
```

`src/config.py` is the single point of environment knowledge. Everything else reads from it.
`make portability-audit` enforces the rule; it fails the build if a provider string appears in
`src/` or `tests/`.

---

## Setup

```bash
cp cloud.env.example cloud.env      # fill in, never commit
make setup
make cloud-check                    # eight slots, all PASS
make data                           # generate the dataset
make test                           # 10 tests, all passing
```

Post your `make cloud-check` output in the course channel before Session 1.

---

## What you must finish

Four `TODO` markers are left in the repo deliberately. Each is a graded decision, not busywork.

| Where | What |
|---|---|
| `requirements.txt` | Regenerate with `pip-compile --generate-hashes` |
| `Dockerfile` | Pin the base image by digest; add `--require-hashes` |
| `cloudlayer/<your provider>.py` | Implement `upload`, `download`, `push_image` |
| This README | The reproducibility trade-off question below |

Then:

```bash
make image-push        # image reaches your registry, digest-pinned
dvc init && dvc remote add -d storage ${BLOB_URI}/dvc
dvc add data/raw && dvc push
```

Run five or more tracked runs varying something meaningful — not five identical runs with
different seeds.

---

## Reproducibility trade-off

If I ran out of time, I would drop hashed dependencies first, rather than digest pinning or seeds. Generating requirements.txt with --generate-hashes took the longest and was the most fragile part of this lab; my network dropped twice and interrupted it. Without hashes, pip install still installs the same versions from the == pins, so the build stays reproducible in most cases. What we lose is protection against a compromised PyPI package being swapped in unnoticed. Digest pinning and seed control are much cheaper to keep and guard against problems far more likely day to day.

Three things pin your build: hashed dependencies, a digest-pinned base image, and controlled
seeds. Under real time pressure you would keep some and drop others.

Which would you drop first, and what specifically breaks when you do? There is a defensible
answer, and we compare answers in Session 2. An answer that refuses to choose scores zero.

---

## Notes for the grader

**REPLACE:** anything that would otherwise cause you to answer a question by email. Non-obvious
choices, known limitations, anything that behaves differently on your machine. A README that
requires a conversation has failed the lab regardless of what the code does.

---

## Checklist before you submit

- [ ] `make reproduce` works from a fresh clone, on a machine that is not yours
- [ ] `make verify` passes against your claim line
- [ ] `make test` — all tests pass
- [ ] `make portability-audit` — clean
- [ ] Image builds for `linux/amd64` and is pushed, digest-pinned
- [ ] `dvc push` completed; a grader can `dvc pull`
- [ ] Five or more tracked runs with params, metrics, data fingerprint, and commit SHA
- [ ] Every **REPLACE** block above is gone (the course-materials block at the top stays)
- [ ] `git log -p | grep -i -E "secret|password|AKIA|BEGIN PRIVATE"` returns nothing

That last check is not optional. A credential in Git history is an automatic deduction in this
course, and rotating it is your responsibility, not the grader's.
---

# ITCS355 Lab 4 — CI/CD, Observability, Drift Detection, and Incident Response

## Task 1 — Automated Tests

Lab 4 extends the existing test suite with CI gates for data and model correctness.

The pipeline includes:

- Unit tests for core functionality.
- Data contract tests for the expected schema and valid sensor data.
- Model behavior tests for valid model predictions.
- An integration test covering the service behavior.

A deliberately bad commit was tested in CI. The data contract test failed, so the change was blocked and was not merged into `main`.

---

## Task 2 — CI/CD Pipeline

The CI/CD pipeline runs checks before deployment:

    lint
      ↓
    unit tests
      ↓
    data contract tests
      ↓
    model behavior tests
      ↓
    build container
      ↓
    integration test
      ↓
    push image (main only)
      ↓
    staging deployment (main only)

The container image is tagged using the Git commit SHA so that a deployed version can be traced back to the exact source revision.

Cloud credentials are not stored directly in the repository. The CI workflow uses GitHub Actions secrets/OIDC configuration for cloud authentication.

---

## Task 3 — Bad Commit Protection

A deliberately invalid change was introduced to test whether the CI pipeline could prevent a bad data change from reaching deployment.

The data contract test failed because the modified data no longer satisfied the expected contract. The pull request was closed without merging.

This demonstrates that the data contract is an actual deployment gate rather than only a local test.

---

## Task 4 — Observability Dashboard and SLOs

The service exposes Prometheus metrics through `/metrics`.

The monitoring dashboard tracks:

- Request rate.
- 4xx/5xx error rate.
- p50, p95, and p99 request latency.
- Rolling `temp_c` feature mean.
- Current model version.

### SLOs

| SLO | Target | Window | Action |
|---|---:|---|---|
| Availability | >= 99.5% | 30 days | Freeze deployment, investigate, and rollback if required |
| Latency | p95 < 200 ms | 7 days | Stop model/dependency changes and investigate |
| Model freshness | <= 30 days | Current | Retrain only after confirming input data is valid |

---

## Task 5 — Scheduled Drift Detection

Production inputs are compared against the training/reference distribution.

Architecture:

    Reference data ───────┐
                          │
    Current data ─────────┤
                          ▼
                   Google Cloud Storage
                          │
                          ▼
                   Cloud Scheduler
                     every 5 minutes
                          │
                          ▼
                    Cloud Run Job
                   itcs355-lab4-drift
                          │
                          ▼
                  monitoring.drift
                     PSI + KS
                          │
                          ▼
                  Cloud Monitoring
                    custom metric
                          │
                          ▼
                     Alert Policy
                          │
                          ▼
                   Email notification

Reference data:

    gs://itcs355-6688097/itcs355/drift/reference.csv

Current data:

    gs://itcs355-6688097/itcs355/drift/current.csv

The drift detector calculates both PSI and the two-sample KS statistic.

The custom Cloud Monitoring metric is:

    custom.googleapis.com/itcs355/drift_psi_temp_c

### Drift threshold

The alert threshold is:

    PSI > 0.25

The threshold was justified using the experiment rather than relying only on a library default. The unchanged reference/current comparison produced PSI = 0 for all features. After deliberately injecting a +6°C shift into `temp_c`, the PSI increased to 0.38333 and triggered the alert.

This provides a clear separation between the normal baseline and the deliberately shifted production input.

### Injected drift result

    temp_c mean: 79.5800 -> 85.5800
    PSI:         0.38333
    KS:          0.24567
    verdict:     significant

All other monitored features remained stable.

The detector reported:

    ALERT  1 feature(s) above threshold 0.25: temp_c

### Scheduled execution

Cloud Scheduler was configured as:

    Job:      itcs355-lab4-drift-schedule
    Schedule: */5 * * * *
    Timezone: Asia/Bangkok

It successfully triggered the Cloud Run Job:

    itcs355-lab4-drift

The scheduled execution downloaded the reference/current files, ran the detector, emitted the metric, and detected the injected drift.

The scheduler was paused after the required evidence was collected to prevent repeated alerts from the intentionally shifted test data.

### Real alert evidence

The Cloud Monitoring alert policy is:

    ITCS355 Lab 4 - Drift Alert

It monitors:

    custom.googleapis.com/itcs355/drift_psi_temp_c

with threshold:

    0.25

A real Google Cloud Monitoring email notification was received:

    [ALERT - No severity] temp_c PSI >= 0.25 on itcs355-6688097

The notification reported the PSI value of 0.38333 and confirmed that the alert was firing.

---

## Task 6 — Drift Incident and Postmortem

### Incident

A deliberate +6°C distribution shift was injected into the `temp_c` feature to simulate production drift.

Observed result:

    PSI = 0.38333
    KS  = 0.24567

The Cloud Monitoring alert fired because PSI exceeded 0.25.

### Five-line postmortem

1. **Signal:** `temp_c` PSI exceeded 0.25 and reached 0.38333.
2. **Cause:** A deliberate +6°C shift was injected as the Lab 4 drift experiment.
3. **Action:** No retraining was performed. The upstream data should be checked first because retraining on corrupted data could damage a working model.
4. **Cost:** Google Cloud Billing was checked before teardown. For 1–6 October 2026, the reported net cost was **THB 0.00**. Vertex AI showed THB 12.83 of usage, fully offset by THB 12.83 in savings.
5. **Prevention/detection:** Keep scheduled PSI monitoring and alerting, and validate upstream data before allowing retraining.

### Cost Evidence

Google Cloud Billing was checked for project `itcs355-6688097` before teardown.

For **1–6 October 2026**:

- **Total billed cost:** THB 0.00
- Artifact Registry: THB 0.00
- Vertex AI usage: THB 12.83
- Vertex AI savings: -THB 12.83
- Cloud Storage: THB 0.00
- Free trial credits remaining: THB 9,776.59

The Vertex AI usage was fully offset by the reported savings, resulting in a net billed cost of **THB 0.00** for the displayed period. This value was taken from the Google Cloud Billing report rather than estimated.

The repository `make cost-report` target was not used as Lab 4 cost evidence because its implementation is a later Lab cost-report scaffold requiring manual estimate, actual cost, RPS, and instance inputs.

### Detection latency

The scheduled Cloud Run execution was:

    Created:   2026-10-07T15:49:35Z
    Started:   2026-10-07T15:49:40Z
    Completed: 2026-10-07T15:50:04Z
    Duration:  approximately 24 seconds

The approximately 24 seconds is the Cloud Run Job execution duration, not the complete end-to-end alert latency. The exact scheduled detection latency was not measured with synchronized injection and alert timestamps, so no unsupported latency value is claimed.

---

## Final Verification

Before teardown, the following evidence was collected:

- CI data contract gate blocked an intentionally bad commit.
- Observability dashboard tracked requests, errors, latency, model version, and feature distribution.
- SLO targets and operational actions were documented.
- Drift detection calculated PSI and KS statistics.
- PSI threshold 0.25 was experimentally justified.
- Drift metrics were written to Cloud Monitoring.
- Cloud Scheduler successfully triggered the Cloud Run Job.
- Cloud Monitoring detected the drift.
- A real email notification was received.
- Injected `temp_c` drift reached PSI 0.38333.
- No retraining was performed on the deliberately shifted data.

---

## Teardown

After all evidence is collected:

    make teardown
    make cost-report

The scheduler should also be explicitly verified:

    gcloud scheduler jobs describe itcs355-lab4-drift-schedule \
      --location=asia-southeast1

The final teardown should confirm that temporary Lab 4 cloud resources are removed or disabled.
