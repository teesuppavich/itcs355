"""Lab 5 pipeline steps. One image, one entry point: python -m scripts.pipeline_steps <step>.

Step logic lives here, inside the image. pipeline.yaml and cloudlayer/pipelines.py only wire
the steps together. Containers do not share a disk, so every step fetches what it needs.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from cloudlayer.factory import get_adapter
from src import config

# The same object src/train.py downloads, and the hyperparameters of Lab 2's selected trial.
DATA_KEY = "dvc/files/md5/63/ec074c360e4e75d5ac2acb431feaca"
TRIAL = {"n_estimators": 100, "max_depth": 4, "min_samples_leaf": 5, "seed": 20260101}


def _need(*names: str) -> None:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise SystemExit("missing env: " + ", ".join(missing))


def _ctx():
    cfg = config.load(strict=False)
    if not cfg.blob_uri:
        raise SystemExit("BLOB_URI is not set")
    return cfg, get_adapter(cfg)


def _write_out(path: str | None, value: str) -> None:
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(value)


def _run_uri(cfg, run_name: str, tail: str = "") -> str:
    return f"{cfg.blob_uri.rstrip('/')}/vertex-jobs/{run_name}/{tail}"


def _fetch_data(cfg, adapter) -> None:
    expected = config.REPO_ROOT / "data" / "raw" / "sensors.csv"
    if Path(cfg.raw_path).resolve() != expected.resolve():
        raise SystemExit(f"raw_path {cfg.raw_path} is not where tests/test_data.py reads ({expected})")
    adapter.download(f"{cfg.blob_uri.rstrip('/')}/{DATA_KEY}", str(cfg.raw_path))


def ingest(args) -> None:
    from src import data

    cfg, adapter = _ctx()
    _fetch_data(cfg, adapter)
    print("data_fingerprint =", data.data_fingerprint(cfg.raw_path))


class _Tally:
    passed = failed = skipped = 0

    def pytest_runtest_logreport(self, report):
        if report.failed:
            self.failed += 1
        elif report.skipped:
            self.skipped += 1
        elif report.passed and report.when == "call":
            self.passed += 1


def validate(args) -> None:
    import pytest

    cfg, adapter = _ctx()
    _fetch_data(cfg, adapter)
    t = _Tally()
    rc = pytest.main(["-q", "-p", "no:cacheprovider", "tests/test_data.py"], plugins=[t])
    print(f"passed={t.passed} failed={t.failed} skipped={t.skipped} rc={int(rc)}")
    # pytest exits 0 when every test is skipped, which would pass a check that checked nothing.
    if rc != 0 or t.failed or t.skipped or not t.passed:
        raise SystemExit("data validation did not run cleanly")


def train(args) -> None:
    _need("COURSE_LAB", "TRAIN_SERVICE_ACCOUNT", "PIPELINE_IMAGE", "GIT_COMMIT")
    cfg, adapter = _ctx()
    image, commit = os.environ["PIPELINE_IMAGE"], os.environ["GIT_COMMIT"]
    if "@sha256:" not in image:
        raise SystemExit("PIPELINE_IMAGE must be pinned by digest, not by tag")
    run_name = f"pipe-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    job_args = {**TRIAL, "run_name": run_name, "blob_uri": cfg.blob_uri,
                "metrics_out": "/tmp/metrics.json", "git_commit": commit}
    job_id = adapter.submit_training(image, job_args)
    print(f"JOB_ID={job_id}")
    print(adapter.wait_training(job_id))

    local = Path("/tmp/candidate_metrics.json")
    adapter.download(_run_uri(cfg, run_name, "metrics.json"), str(local))  # missing means the job failed
    metrics = json.loads(local.read_text())
    # train.py does not write these three, and register_model reads them for the lineage.
    metrics.update(git_commit=commit, training_job_id=job_id, image_digest=image.split("@", 1)[1])
    local.write_text(json.dumps(metrics, indent=2))
    adapter.upload(str(local), f"vertex-jobs/{run_name}/metrics.json")
    _write_out(args.out, run_name)
    print(f"RUN_NAME={run_name}")


def gate(args) -> None:
    _need("MODEL_REGISTRY_NAME")
    cfg, adapter = _ctx()
    local = "/tmp/candidate_metrics.json"
    adapter.download(_run_uri(cfg, args.run_name, "metrics.json"), local)
    rc = subprocess.run(
        [sys.executable, "-m", "scripts.evaluation_gate", "--metrics", local]
    ).returncode
    if rc not in (0, 1):
        raise SystemExit(f"gate could not decide (exit {rc}); failing the step on purpose")
    decision = "pass" if rc == 0 else "fail"
    _write_out(args.out, decision)
    print(f"GATE_DECISION={decision}")


def register(args) -> None:
    _need("MODEL_REGISTRY_NAME", "COURSE_LAB")
    cfg, adapter = _ctx()
    version = adapter.register_model(_run_uri(cfg, args.run_name), cfg.model_registry_name)
    ref = adapter.model_ref(cfg.model_registry_name, version)
    print(f"MODEL_REF={ref}")
    _write_out(args.out, ref)


def deploy(args) -> None:
    _need("COURSE_LAB", "SERVE_SERVICE_ACCOUNT", "STAGING_INSTANCE")
    cfg, adapter = _ctx()
    endpoint = os.environ.get("STAGING_ENDPOINT", "itcs355-staging")
    print(adapter.deploy(args.model_ref, endpoint, os.environ["STAGING_INSTANCE"]))


STEPS = {"ingest": ingest, "validate": validate, "train": train,
         "gate": gate, "register": register, "deploy": deploy}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("step", choices=sorted(STEPS))
    p.add_argument("--run-name")
    p.add_argument("--model-ref")
    p.add_argument("--out")
    args = p.parse_args()
    STEPS[args.step](args)


if __name__ == "__main__":
    main()
