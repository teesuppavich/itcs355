# ITCS355 — Lab 4: Observability, CI/CD, and Drift Detection

## Objective

The objective of Lab 4 is to build a more reliable and observable machine learning system. The lab focuses on automated testing, CI/CD, service monitoring, data drift detection, alerting, scheduled monitoring, and cost awareness.

The main goals are:

- Validate the data and model before deployment.
- Automate testing and container builds with CI.
- Automate staging deployment with CD.
- Monitor the prediction service using metrics.
- Define service-level objectives (SLOs).
- Detect changes in the input data distribution.
- Generate a real monitoring alert when drift is detected.
- Run drift detection automatically using a scheduled cloud job.
- Document the results and response process.

## Task 1 — Data and Model Validation

The project includes automated tests for the data contract, model behaviour, and prediction service.

The test suite was executed with:

    pytest -q tests/test_data.py tests/test_model_behaviour.py tests/test_service.py

Result:

    22 passed, 1 warning

The warning was a Starlette TestClient deprecation warning and did not cause a test failure.

The dataset was generated using:

    make data

The generated dataset contained:

- 6,000 rows
- 240 machines
- Positive rate: 0.117

The data contract tests validate:

- Required columns and schema
- Data types
- Missing values
- Plausible feature ranges
- Binary and non-degenerate target values
- Unique reading IDs

The model behaviour tests validate:

- Valid probability outputs
- Low risk for healthy machines
- Risk does not decrease as machine wear increases
- Prediction latency remains within the required budget
- Predictions are not nearly constant

The service tests validate:

- `/health`
- `/ready`
- `/predict`
- Invalid input values
- Unknown fields
- Missing fields
- Single and batch prediction equivalence
- Maximum batch size

These tests provide a basic quality gate before deployment.

## Task 2 — CI/CD

GitHub Actions was configured for continuous integration and continuous deployment.

### Continuous Integration

The CI workflow runs on pull requests and pushes to `main`.

The CI pipeline performs the following checks:

1. Secret scanning
2. Python 3.12 environment setup
3. Dependency installation using hash-checked requirements
4. Ruff linting
5. Portability audit
6. Dataset generation
7. Data contract tests
8. Model behaviour tests
9. Service tests
10. Training image build
11. Serving image build
12. End-to-end integration test

The integration test generates the dataset, trains the model, exports the model, starts the serving container, checks readiness, sends a prediction request, verifies the response, and stops the container.

### Continuous Deployment

The CD workflow runs after a successful CI workflow on `main`.

The deployment process:

1. Uses the exact commit that passed CI.
2. Authenticates to Google Cloud using Workload Identity Federation.
3. Builds the serving image.
4. Pushes the image to Artifact Registry.
5. Deploys the staging service through the cloud adapter.
6. Runs the smoke test.

The deployment configuration uses GitHub environment variables and secrets instead of storing credentials directly in the repository.

## Task 3 — Quality Gate and Failure Handling

A deliberately broken data contract was introduced to verify that the CI pipeline could detect invalid changes.

The data contract tests failed when the invalid change was introduced, which prevented the pipeline from progressing to the later deployment stages.

This demonstrates that the data contract is being used as an actual quality gate rather than only as a local test.

The same experiment also supported the drift detection and alerting work in Tasks 5 and 6.

## Task 4 — Service Observability and SLOs

The prediction service exposes a `/metrics` endpoint for Prometheus monitoring.

The main metrics include:

- `http_requests_total{method,path,status_class}`
- `request_latency_ms`
- `model_version_info{version}`
- `feature_rolling_mean{feature}`

A rolling mean of the `temp_c` feature is also tracked using a 500-value window.

The monitoring stack consists of:

- Docker Compose
- Prometheus
- Grafana
- Application metrics
- A Grafana dashboard

The dashboard was tested successfully and displays request and service behaviour.

The following SLOs were defined:

### Availability

Target:

    99.5% over 30 days

If the availability SLO is violated, the response is to freeze deployments, roll back to a known-good version, and perform a postmortem.

### Latency

Target:

    p95 latency < 200 ms over 7 days

If the latency target is violated, model or dependency changes should be stopped while the regression and service capacity are investigated.

### Model Freshness

Target:

    Model age <= 30 days

If the model becomes too old, retraining should be considered unless the problem is caused by an upstream schema or data-quality issue.

## Task 5 — Data Drift Detection

A drift detector was implemented in:

    monitoring/drift.py

The detector uses Population Stability Index (PSI) and the two-sample Kolmogorov-Smirnov statistic.

The PSI thresholds are:

    PSI < 0.10       stable
    PSI < 0.25       moderate
    PSI >= 0.25      significant

The drift detector supports:

- Reference and current datasets
- Configurable thresholds
- JSON output
- Cloud metric emission

The baseline comparison used the same reference and current dataset.

The result was:

    temp_c          PSI 0.00000    stable
    vibration_mm    PSI 0.00000    stable
    ...

All features had PSI = 0, confirming that the unchanged data did not produce a false drift alert.

### Drift Injection

A deliberate temperature shift was injected using:

    python scripts/inject_drift.py --feature temp_c --mode shift --magnitude 6

The resulting drift detection was:

    feature    psi       ks       verdict
    temp_c     0.38333   0.24567  significant

The detector produced:

    ALERT 1 feature(s) above threshold 0.25: temp_c

The threshold of 0.25 was selected because the unchanged reference/current comparison produced PSI = 0 for all features, while the deliberately injected +6°C shift increased the `temp_c` PSI to 0.38333 and triggered an alert.

This provides a clear separation between the normal baseline and the distribution shift used in the experiment.

## Task 6 — Real Alerting and Scheduled Drift Monitoring

The drift detector emits the custom Google Cloud Monitoring metric:

    custom.googleapis.com/itcs355/drift_psi_temp_c

A Google Cloud Monitoring alert policy was configured with:

    Threshold: PSI > 0.25
    Alignment period: 300 seconds
    Duration: 0 seconds
    Auto-close: 86400 seconds

The alert policy was:

    ITCS355 Lab 4 - Drift Alert

An email notification channel was configured for the alert.

A real alert was successfully received:

    [ALERT - No severity] temp_c PSI >= 0.25 on itcs355-6688097

The alert reported:

    value: 0.38333
    threshold: 0.25

This confirms that the drift detector was connected to Google Cloud Monitoring and that the alert was triggered by an actual metric.

### Cloud Storage

The drift datasets were stored in:

    gs://itcs355-6688097/itcs355/drift/reference.csv
    gs://itcs355-6688097/itcs355/drift/current.csv

### Cloud Run Job

The drift detection job was deployed as:

    itcs355-lab4-drift

The job downloads the reference and current datasets from Cloud Storage, runs the drift detector, emits the metric, and exits with code 2 when drift is detected.

Exit code 2 is intentional and represents detected drift rather than a program failure.

The container image was built using the pinned Python 3.12 base image.

Image:

    asia-southeast1-docker.pkg.dev/itcs355-6688097/itcs355/itcs355-drift@sha256:7f25153fdf5f6085f32b6a4d21f3fb7fed1064e320c6fef7a1f933c6e862a3e6

The Cloud Run Job used:

    Region: asia-southeast1
    Memory: 512Mi
    CPU: 1
    Timeout: 10 minutes
    Maximum retries: 0

### Cloud Scheduler

A scheduler was configured as:

    itcs355-lab4-drift-schedule

Schedule:

    */5 * * * *

Timezone:

    Asia/Bangkok

The scheduler successfully triggered the Cloud Run Job.

The scheduled execution completed successfully from the infrastructure perspective, with exit code 2 because drift was detected.

The recorded Cloud Run Job execution was approximately 24 seconds. This is the job execution duration only and is not treated as the complete end-to-end alert latency.

## Task 7 — Drift Response and Postmortem

The drift experiment used a deliberate +6°C shift in `temp_c`.

### Signal

The `temp_c` PSI increased to:

    0.38333

This was above the configured threshold:

    0.25

### Cause

The drift was intentionally injected by shifting the temperature distribution by +6°C.

### Response

Retraining was not immediately performed.

The first response should be to validate the upstream data source and confirm whether the distribution change represents a real operating change or a data-quality problem.

### Cost

For the displayed billing period from 1–6 October 2026, the project showed:

    Total billed: THB 0.00
    Vertex AI usage: THB 12.83
    Vertex AI savings: -THB 12.83
    Cloud Storage: THB 0.00
    Artifact Registry: THB 0.00

The net billed amount was THB 0.00 because the Vertex AI usage was fully offset by the displayed savings.

The project also showed remaining free-trial credits of THB 9,776.59.

### Prevention

The main prevention measures are:

- Run scheduled PSI monitoring.
- Alert when PSI exceeds the defined threshold.
- Validate upstream data before retraining.
- Keep the drift response process documented.
- Monitor service and model behaviour continuously.

## Teardown

The generic teardown target did not remove the Lab 4 monitoring resources because these resources were not matched by the generic teardown tags.

The Lab 4 Cloud Run Job was therefore deleted manually:

    gcloud run jobs delete itcs355-lab4-drift --region=asia-southeast1 --quiet

The Cloud Scheduler job was deleted:

    gcloud scheduler jobs delete itcs355-lab4-drift-schedule --location=asia-southeast1 --quiet

The Cloud Monitoring alert policy was deleted:

    gcloud monitoring policies delete projects/itcs355-6688097/alertPolicies/7446149716105548409 --quiet

Verification showed no remaining Lab 4 Cloud Run Jobs and no active monitoring alert policies.

The shared Artifact Registry repository was intentionally not deleted because it is also used by earlier labs.

## Conclusion

Lab 4 implemented an end-to-end observability and reliability workflow for the machine learning system. Automated tests validate the data, model, and service before deployment, while CI/CD provides automated testing, container builds, and staging deployment.

The service was instrumented with Prometheus metrics and monitored using Grafana. SLOs were defined for availability, latency, and model freshness.

The drift detection experiment showed that unchanged data produced PSI = 0, while the deliberate +6°C temperature shift increased the `temp_c` PSI to 0.38333 and triggered the configured 0.25 threshold. The drift metric successfully reached Google Cloud Monitoring and generated a real email alert.

Scheduled monitoring was also tested through Cloud Scheduler and Cloud Run Jobs. The complete workflow demonstrates how model quality, service health, data drift, alerting, and operational response can be connected into one reproducible MLOps process.
