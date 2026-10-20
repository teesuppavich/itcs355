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

expected test_roc_auc: 0.848 ± 0.010

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

**REPLACE with your answer, 100 words maximum.**

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

## Task 2: Least-privilege identities

| Identity | Can do | Why it needs it |
|---|---|---|
| `itcs355-train` | Read and create objects in the project bucket (`objectViewer`, `objectCreator`); write logs and metrics; read Artifact Registry | Reads the dataset, writes `model.joblib` and `metrics.json` under a run-specific path, reports job logs and metrics |
| `itcs355-serve` | Read objects in the project bucket (`objectViewer`); write logs and metrics; read Artifact Registry | Loads the model artifact at startup, emits endpoint logs and metrics. It cannot write data |
| `github-deploy` (CI) | `aiplatform.user`, `artifactregistry.writer`, `storage.objectAdmin`, `monitoring.metricWriter`; `serviceAccountUser` on train and serve only | Pushes images, submits the pipeline, uploads models, deploys endpoints, and runs jobs as train/serve |

Scope is enforced at the bucket level, not the project level, for train and serve.

### Evidence: boundaries verified by impersonation (2026-10-19)

| Identity | Action | Result |
|---|---|---|
| serve | write `serve.txt` | Denied: `storage.objects.create` |
| train | write `train.txt` (first time) | Allowed |
| train | overwrite `train.txt` | Denied: no `storage.objects.delete` |
| serve | read `train.txt` | Allowed |

Side effect worth noting: `objectCreator` makes artifacts write-once per path, so a trained model cannot be silently overwritten. Re-runs must use a run-specific path.

### Known weak point

`github-deploy` holds `storage.objectAdmin` on the whole project, the broadest grant in the table. I have not tested which pipeline steps actually need delete or overwrite, so I have not narrowed it.

### Permission removal experiment

- Removed: `roles/artifactregistry.reader` from `itcs355-serve`
- Prediction before the test: deploy still succeeds, because the Vertex service agent, not `itcs355-serve`, pulls the serving image
- What actually broke: nothing. Redeploying the test model to a Vertex endpoint with `itcs355-serve` lacking `artifactregistry.reader` completed successfully (audit log: DeployModel at 02:27 UTC, a second DeployModel entry at 02:46:14 UTC, then UndeployModel at 02:46:19 UTC; my script only undeploys when a deployed model exists on the endpoint, so the deploy took effect), so the grant was not needed for deploying. My hypothesis, not verified: the Vertex service agent pulls the image, not the serve identity. The permission was restored after the test.
