"""GCP adapter. Implement upload/download/push_image for Lab 1."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cloudlayer.base import CloudAdapter


class GcpAdapter(CloudAdapter):
    def _bucket_and_prefix(self) -> tuple[str, str]:
        parsed = urlparse(self.cfg.blob_uri)
        bucket = parsed.netloc
        prefix = parsed.path.lstrip("/")
        return bucket, prefix

    def upload(self, local_path: str, key: str) -> str:
        from google.cloud import storage

        bucket_name, prefix = self._bucket_and_prefix()
        full_key = f"{prefix}/{key}" if prefix else key

        client = storage.Client(project=self.cfg.project_id)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(full_key)
        blob.upload_from_filename(local_path)

        return f"gs://{bucket_name}/{full_key}"

    def download(self, uri: str, local_path: str) -> None:
        from google.cloud import storage

        parsed = urlparse(uri)
        bucket_name = parsed.netloc
        blob_key = parsed.path.lstrip("/")

        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        client = storage.Client(project=self.cfg.project_id)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_key)
        blob.download_to_filename(local_path)

    def push_image(self, local_tag: str) -> str:
        name, _, tag = local_tag.partition(":")
        remote_tag = f"{self.cfg.container_registry}/{name}:{tag}"

        subprocess.run(["docker", "tag", local_tag, remote_tag], check=True)
        subprocess.run(["docker", "push", remote_tag], check=True)

        result = subprocess.run(
            ["docker", "inspect", "--format={{index .RepoDigests 0}}", remote_tag],
            check=True,
            capture_output=True,
            text=True,
        )
        digest_ref = result.stdout.strip()
        return digest_ref

    def submit_training(self, image_uri: str, args: dict[str, Any]) -> str:
        from google.cloud import aiplatform

        aiplatform.init(
            project=self.cfg.project_id,
            location=self.cfg.region,
            staging_bucket=self.cfg.blob_uri
        )

        cli_args: list[str] = []
        for key, value in args.items():
            cli_args.append(f"--{key.replace('_', '-')}")
            cli_args.append(str(value))

        job = aiplatform.CustomJob(
            display_name=f"itcs355-lab2-{args.get('run_name', 'trial')}",
            worker_pool_specs=[{
                "machine_spec": {"machine_type": "e2-standard-4"},
                "replica_count": 1,
                "container_spec": {
                    "image_uri": image_uri,
                    "args": cli_args,
                    "env": [
                        {"name": "CLOUD_PROVIDER", "value": "gcp"},
                        {"name": "PROJECT_ID", "value": self.cfg.project_id},
                        {"name": "REGION", "value": self.cfg.region},
                        {"name": "BLOB_URI", "value": self.cfg.blob_uri},
                    ],
                },
            }],
            base_output_dir=f"{self.cfg.blob_uri}/vertex-jobs",
            labels=self.cfg.tags(2),
        )

        job.submit(
            scheduling_strategy=aiplatform.compat.types.custom_job.Scheduling.Strategy.SPOT
        )

        return job.resource_name


    def wait_training(self, job_id: str) -> dict[str, Any]:
        from google.cloud import aiplatform
        import time

        aiplatform.init(
            project=self.cfg.project_id,
            location=self.cfg.region,
        )

        terminal_states = {
            "JOB_STATE_SUCCEEDED",
            "JOB_STATE_FAILED",
            "JOB_STATE_CANCELLED",
            "JOB_STATE_EXPIRED",
        }

        while True:
            job = aiplatform.CustomJob.get(job_id)
            state = job.state.name

            print(f"Training job state: {state}")

            if state in terminal_states:
                return {
                    "job_id": job_id,
                    "state": state,
                    "success": state == "JOB_STATE_SUCCEEDED",
                }

        time.sleep(20)

    def register_model(self, model_uri: str, name: str) -> str:
        from google.cloud import aiplatform
        import json

        # model_uri is expected to point to the GCS directory
        # containing model.joblib and metrics.json.
        if not model_uri.startswith("gs://"):
            raise ValueError("GCP model_uri must be a gs:// URI")

        parsed = urlparse(model_uri)
        bucket_name = parsed.netloc
        prefix = parsed.path.lstrip("/").rstrip("/")

        # Read the metrics/lineage produced by the remote training job.
        from google.cloud import storage

        client = storage.Client(project=self.cfg.project_id)
        bucket = client.bucket(bucket_name)

        metrics_blob = bucket.blob(f"{prefix}/metrics.json")
        metrics = json.loads(metrics_blob.download_as_text())

        run_id = str(metrics.get("run_id", "unknown"))
        seed = str(metrics.get("seed", "unknown"))
        data_fingerprint = str(
            metrics.get("data_fingerprint", "unknown")
        )
        val_roc_auc = str(metrics.get("val_roc_auc", "unknown"))
        test_roc_auc = str(metrics.get("test_roc_auc", "unknown"))

        git_commit = str(metrics.get("git_commit", "unknown"))
        training_job_id = str(
            metrics.get("training_job_id", "unknown")
        )
        image_digest = str(
            metrics.get("image_digest", "unknown")
        )

        lineage = (
            f"git_commit={git_commit}\n"
            f"data_version={data_fingerprint}\n"
            f"mlflow_run_id={run_id}\n"
            f"training_job_id={training_job_id}\n"
            f"image_digest={image_digest}\n"
            f"seed={seed}\n"
            f"metric_val={val_roc_auc}\n"
            f"metric_test={test_roc_auc}"
        )

        aiplatform.init(
            project=self.cfg.project_id,
            location=self.cfg.region,
            staging_bucket=self.cfg.blob_uri,
        )

        model = aiplatform.Model.upload(
            display_name=name,
            artifact_uri=model_uri,
            serving_container_image_uri=(
                "us-docker.pkg.dev/vertex-ai/"
                "prediction/sklearn-cpu.1-8:latest"
            ),
            version_aliases=["staging"],
            description=lineage,
            labels=self.cfg.tags(2),
            project=self.cfg.project_id,
            location=self.cfg.region,
            staging_bucket=self.cfg.blob_uri,
            sync=True,
        )

        print(f"Registered Vertex model: {model.resource_name}")
        print(f"Version ID: {model.version_id}")
        print("Alias: staging")

        return str(model.version_id)
    # deploy / invoke                   -> Lab 3 (Vertex Endpoint)

    def deploy(self, model_ref: str, endpoint: str, instance: str) -> str:
        """Create a Lab 3 serving model and deploy it to a Vertex endpoint."""
        from google.cloud import aiplatform

        aiplatform.init(
            project=self.cfg.project_id,
            location=self.cfg.region,
            staging_bucket=self.cfg.blob_uri,
        )

        # Get the Lab 2 model so we can reuse its artifact URI.
        source_model = aiplatform.Model(
            model_name=str(model_ref),
            project=self.cfg.project_id,
            location=self.cfg.region,
        )

        artifact_uri = source_model.gca_resource.artifact_uri
        print(f"Source artifact: {artifact_uri}")

        # Lab 3 custom FastAPI serving image.
        serving_image = os.environ.get(
            "SERVING_IMAGE",
            f"{self.cfg.container_registry}/itcs355-lab3-serving:v2",
        )
        print(f"Serving image: {serving_image}")

        # Create a new Vertex Model for Lab 3.
        model = aiplatform.Model.upload(
            display_name=f"{endpoint}-model",
            artifact_uri=artifact_uri,
            serving_container_image_uri=serving_image,
            serving_container_ports=[8080],
            serving_container_environment_variables={"MODEL_VERSION": str(model_ref)},
            serving_container_predict_route="/predict/instances",
            serving_container_health_route="/ready",
            labels=self.cfg.tags(3),
            project=self.cfg.project_id,
            location=self.cfg.region,
            staging_bucket=self.cfg.blob_uri,
            sync=True,
        )

        print(f"Created Lab 3 model: {model.resource_name}")
        print(f"Model ID: {model.name}")

        # Reuse an existing endpoint or create one.
        endpoints = aiplatform.Endpoint.list(
            filter=f'display_name="{endpoint}"',
            project=self.cfg.project_id,
            location=self.cfg.region,
        )

        if endpoints:
            ep = endpoints[0]
            print(f"Using existing endpoint: {ep.resource_name}")
        else:
            ep = aiplatform.Endpoint.create(
                display_name=endpoint,
                labels=self.cfg.tags(3),
                project=self.cfg.project_id,
                location=self.cfg.region,
                sync=True,
            )
            print(f"Created endpoint: {ep.resource_name}")

        ep.deploy(
            model=model,
            deployed_model_display_name=f"{endpoint}-model",
            traffic_percentage=100,
            machine_type=instance,
            min_replica_count=1,
            max_replica_count=1,
            sync=True,
        )

        print(f"Deployed model: {model.resource_name}")
        print(f"Endpoint: {ep.resource_name}")

        return ep.resource_name

    def invoke(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Invoke a Vertex Endpoint using the service's feature-dict payload."""
        from google.cloud import aiplatform
        from src.data import FEATURES

        aiplatform.init(
            project=self.cfg.project_id,
            location=self.cfg.region,
        )

        # Accept either an endpoint resource name or a display name.
        if endpoint.startswith("projects/"):
            ep = aiplatform.Endpoint(
                endpoint_name=endpoint,
                project=self.cfg.project_id,
                location=self.cfg.region,
            )
        else:
            endpoints = aiplatform.Endpoint.list(
                filter=f'display_name="{endpoint}"',
                project=self.cfg.project_id,
                location=self.cfg.region,
            )
            if not endpoints:
                raise RuntimeError(f"Vertex endpoint not found: {endpoint}")
            ep = endpoints[0]

        missing = [name for name in FEATURES if name not in payload]
        if missing:
            raise ValueError(f"Missing features: {missing}")

        instance = [payload[name] for name in FEATURES]
        prediction = ep.predict(instances=[instance])

        deployed_version = "unknown"
        if ep.gca_resource.deployed_models:
            deployed_model = ep.gca_resource.deployed_models[0]
            deployed_version = getattr(deployed_model, "model", "unknown").split("/")[-1]

        return {
            "predictions": prediction.predictions,
            "model_version": deployed_version,
            "endpoint": ep.resource_name,
        }

    def teardown(self, tags: dict[str, str]) -> list[str]:
        from google.cloud import aiplatform
        aiplatform.init(project=self.cfg.project_id, location=self.cfg.region)
        deleted=[]
        for ep in aiplatform.Endpoint.list(project=self.cfg.project_id, location=self.cfg.region):
            if ep.display_name != "itcs355-lab3-endpoint":
                continue
            for dm in list(ep.gca_resource.deployed_models):
                ep.undeploy(deployed_model_id=str(dm.id), sync=True)
                deleted.append(f"deployed-model:{dm.id}")
            ep.delete(sync=True)
            deleted.append(f"endpoint:{ep.resource_name}")
        return deleted

    # emit_metric                       -> Lab 4 (Cloud Monitoring time series)
    # generate                          -> Lab 5 (managed LLM endpoint; read usageMetadata for tokens)
    # teardown                          -> Lab 5 (filter resources by label)
