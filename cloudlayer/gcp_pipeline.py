"""Vertex AI Pipelines (Kubeflow) translation of pipeline/pipeline.yaml.

Kept out of pipelines.py on purpose: that file uses `from __future__ import annotations`,
which turns the dsl.OutputPath(...) annotations below into strings KFP may not resolve.
"""
import json
import os
import subprocess

from kfp import compiler, dsl

from src import config

REQUIRED_ENV = (
    "PROJECT_ID", "REGION", "BLOB_URI", "CONTAINER_REGISTRY", "MODEL_REGISTRY_NAME",
    "PIPELINE_IMAGE", "TRAIN_SERVICE_ACCOUNT", "SERVE_SERVICE_ACCOUNT", "STAGING_INSTANCE",
)
OPTIONAL_ENV = ("STAGING_ENDPOINT", "SERVING_IMAGE")


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def _task_env(spec):
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        raise RuntimeError("missing env for the pipeline: " + ", ".join(missing))
    if "${" in json.dumps(spec):
        raise RuntimeError("unresolved ${VAR} left in the pipeline spec")
    if _git("status", "--porcelain") and not os.environ.get("ALLOW_DIRTY"):
        raise RuntimeError(
            "working tree is dirty, so GIT_COMMIT would not describe the image: commit first "
            "(ALLOW_DIRTY=1 only for a test compile)"
        )
    env = {k: os.environ[k] for k in REQUIRED_ENV}
    env.update({k: os.environ[k] for k in OPTIONAL_ENV if os.environ.get(k)})
    env.update(CLOUD_PROVIDER="gcp", COURSE_LAB=str(spec["tags"]["lab"]),
               GIT_COMMIT=_git("rev-parse", "HEAD"))
    return env


def build_pipeline(spec):
    steps = {s["name"]: s for s in spec["steps"]}
    env = _task_env(spec)

    def run(name, *extra):
        s = steps[name]
        return dsl.ContainerSpec(image=s["image"], command=list(s["command"]), args=list(extra))

    @dsl.container_component
    def ingest_op():
        return run("ingest")

    @dsl.container_component
    def validate_op():
        return run("validate")

    @dsl.container_component
    def train_op(run_name: dsl.OutputPath(str)):
        return run("train", "--out", run_name)

    @dsl.container_component
    def gate_op(run_name: str, decision: dsl.OutputPath(str)):
        return run("evaluate", "--run-name", run_name, "--out", decision)

    @dsl.container_component
    def register_op(run_name: str, model_ref: dsl.OutputPath(str)):
        return run("register", "--run-name", run_name, "--out", model_ref)

    @dsl.container_component
    def deploy_op(model_ref: str):
        return run("deploy_staging", "--model-ref", model_ref)

    @dsl.pipeline(name=spec["name"])
    def pipeline():
        a = ingest_op()
        v = validate_op().after(a)
        t = train_op().after(v)
        g = gate_op(run_name=t.outputs["run_name"])
        with dsl.If(g.outputs["decision"] == "pass"):
            r = register_op(run_name=t.outputs["run_name"])
            d = deploy_op(model_ref=r.outputs["model_ref"])
        for task in (a, v, t, g, r, d):
            for key, value in env.items():
                task.set_env_variable(key, value)

    return pipeline


def compile_pipeline(spec):
    out = config.REPO_ROOT / "pipeline" / "compiled" / f"{spec['name']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    compiler.Compiler().compile(pipeline_func=build_pipeline(spec), package_path=str(out))
    return out


def submit(path):
    """Costs money. Never called by compile; run it deliberately."""
    from google.cloud import aiplatform

    missing = [k for k in ("PIPELINE_SERVICE_ACCOUNT",) if not os.environ.get(k)]
    if missing:
        raise RuntimeError("missing env: " + ", ".join(missing))
    cfg = config.load(strict=False)
    aiplatform.init(project=cfg.project_id, location=cfg.region, staging_bucket=cfg.blob_uri)
    job = aiplatform.PipelineJob(
        display_name="itcs355-training-pipeline",
        template_path=str(path),
        pipeline_root=f"{cfg.blob_uri.rstrip('/')}/pipeline-root",
        labels=cfg.tags(5),
    )
    job.submit(service_account=os.environ["PIPELINE_SERVICE_ACCOUNT"])
    print(job.resource_name)
    return job.resource_name
