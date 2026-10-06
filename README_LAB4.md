# ITCS355 — Lab 4: CI/CD, Observability and Drift Detection

## 1. Objective

Lab 4 extends the previous MLOps pipeline with automated testing, CI/CD, service observability, and data drift detection.

The main goal is to make the ML system safer to change and easier to monitor in production. The pipeline should prevent bad data or model changes from reaching deployment, while monitoring the deployed service for operational and data-related problems.

---

## 2. Task 1 — Automated Tests

### Unit Tests

The project uses `pytest` for automated testing. Tests are separated by responsibility so that data problems, model behaviour problems, and service problems can be identified separately.

The test suite was executed locally with:

```bash
pytest -q tests/test_data.py tests/test_model_behaviour.py tests/test_service.py
```

Result:

```text
22 passed, 1 warning
```

The warning was a deprecation warning from the Starlette test client and did not cause any test failure.

### Data Contract Tests

The data contract tests are implemented in `tests/test_data.py`.

The tests check that incoming sensor data still follows the assumptions required by the ML pipeline.

#### 1. Schema and data types

`test_schema_columns_present_and_typed`

This checks that all expected columns are present, no unexpected columns are introduced, and each column has the expected data type.

**Production incident caught:** an upstream data producer changes a column name or data type, causing the training or prediction pipeline to read the data incorrectly.

#### 2. Required values are not null

`test_no_nulls_in_required_columns`

This checks that required sensor fields do not contain missing values.

**Production incident caught:** an upstream sensor or data pipeline stops providing one of the required measurements, which could result in invalid preprocessing or predictions.

#### 3. Plausible feature ranges

`test_features_within_plausible_ranges`

This checks that sensor values remain within predefined plausible ranges.

**Production incident caught:** a sensor malfunction or unit conversion error produces unrealistic values that could silently enter model training or prediction.

#### 4. Target values are valid

`test_target_is_binary_and_not_degenerate`

This checks that the target contains only `0` and `1` and that the positive class is not completely missing or dominant.

**Production incident caught:** a broken labeling or upstream transformation process produces invalid labels or causes the training data to contain only one effective class.

#### 5. Reading identifiers are unique

`test_identifier_is_unique`

This checks that every `reading_id` is unique.

**Production incident caught:** duplicated records enter the training dataset and cause some observations to be counted multiple times, potentially biasing the trained model.

These tests provide more than the required two data contract checks and cover different failure modes that could occur in production.

### Model Behaviour Test

Model behaviour tests are implemented in `tests/test_model_behaviour.py`.

The tests do not depend only on an aggregate accuracy or other performance metric. They check behaviours that should remain valid when the model changes.

The tests include:

* predictions must be valid probabilities between 0 and 1;
* a known healthy machine should have a relatively low predicted risk;
* risk should not decrease when machine wear increases;
* prediction latency should remain within the defined budget;
* the model should not produce nearly constant predictions.

For example:

`test_known_healthy_machine_scores_low`

checks that a cool, lightly loaded and recently serviced machine is not incorrectly classified as high risk.

`test_risk_increases_with_wear`

checks a domain expectation that increased hours since service should not reduce the predicted risk.

### Integration Test

Service integration tests are implemented in `tests/test_service.py`.

The tests use the FastAPI application and verify the service behaviour through HTTP requests.

The integration coverage includes:

* `/health` returns a live status;
* `/ready` confirms that the model is ready for prediction;
* `/predict` returns a probability and model version;
* invalid feature values are rejected;
* unknown input fields are rejected;
* missing required fields are rejected;
* batch predictions match equivalent single predictions;
* batch requests larger than the configured limit are rejected.

The tests were executed successfully with the result:

```text
22 passed, 1 warning
```

### Dataset Used for Testing

The local test dataset was generated with:

```bash
make data
```

The command generated:

```text
rows=6000
machines=240
positive_rate=0.117
```

The generated file was:

```text
data/raw/sensors.csv
```

---

## 3. Task 2 — CI/CD

### CI Pipeline

*To be completed after the GitHub Actions pipeline is verified.*

### CD Pipeline

*To be completed after the staging deployment is verified.*

### GCP Authentication

*To be completed after the GitHub OIDC deployment is tested.*

### Container Image

*To be completed after the SHA-tagged image is successfully pushed.*

---

## 4. Task 3 — Deliberately Broken Data Contract

*To be completed.*

---

## 5. Task 4 — Observability Dashboard

### Request Rate

*To be completed.*

### Error Rate

*To be completed.*

### Latency

*To be completed.*

### Feature Distribution

*To be completed.*

### Model Version

*To be completed.*

### SLO and Error Budget

*To be completed.*

---

## 6. Task 5 — Drift Detection and Alerting

### Drift Metric

*To be completed.*

### Threshold

*To be completed.*

### Alert Channel

*To be completed.*

### Schedule

*To be completed.*

---

## 7. Task 6 — Drift Injection and Incident

### Detection

*To be completed.*

### Dashboard Evidence

*To be completed.*

### Alert Timestamp

*To be completed.*

### Postmortem

*To be completed.*

---

## 8. Results

*To be completed after all Lab 4 tasks are finished.*

---

## 9. Conclusion

*To be completed after all Lab 4 tasks are finished.*

---

## 10. Teardown and Cost

### Teardown

*To be completed.*

### Cost Report

*To be completed.*
