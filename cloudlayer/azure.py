"""Azure adapter. Implement upload/download/push_image for Lab 1.

SDK:  pip install azure-storage-blob azure-identity azure-containerregistry
Docs: BlobServiceClient for storage; ACR push goes through `docker push` after
      `az acr login --name <registry>`.

Hints for Lab 1:
  * BLOB_URI is either abfss://container@account.dfs.core.windows.net/prefix or
    https://account.blob.core.windows.net/container/prefix. Pick one form and parse
    it here, never in src/.
  * Use DefaultAzureCredential rather than a connection string. It picks up your CLI
    login locally and your managed identity in CI, which is what Lab 4 needs.
  * push_image must return the digest reference: registry.azurecr.io/repo@sha256:...
  * Azure tags live on the resource, not the blob. Tag the storage account, the
    registry, and later the workspace with cfg.tags(1).
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from cloudlayer.base import CloudAdapter


class AzureAdapter(CloudAdapter):
    @staticmethod
    def _split(uri: str) -> tuple[str, str, str]:
        """Return (account_url, container, path) for an https:// or abfss:// blob URI."""
        parsed = urlparse(uri)
        if parsed.scheme == "abfss":
            container, _, host = parsed.netloc.partition("@")
            return "https://" + host.replace(".dfs.", ".blob."), container, parsed.path.lstrip("/")
        if parsed.scheme == "https":
            container, _, path = parsed.path.lstrip("/").partition("/")
            return f"https://{parsed.netloc}", container, path
        raise ValueError(f"Azure adapter cannot read blob URI {uri!r}: expected https:// or abfss://")

    def upload(self, local_path: str, key: str) -> str:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        account_url, container, prefix = self._split(self.cfg.blob_uri)
        full_key = f"{prefix}/{key}" if prefix else key
        service = BlobServiceClient(account_url, credential=DefaultAzureCredential())
        with open(local_path, "rb") as fh:
            service.get_blob_client(container, full_key).upload_blob(fh, overwrite=True)
        return f"{account_url}/{container}/{full_key}"

    def download(self, uri: str, local_path: str) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        account_url, container, blob_key = self._split(uri)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        service = BlobServiceClient(account_url, credential=DefaultAzureCredential())
        data = service.get_blob_client(container, blob_key).download_blob().readall()
        Path(local_path).write_bytes(data)

    def push_image(self, local_tag: str) -> str:
        raise NotImplementedError("TODO Lab 1: az acr login, push, return registry/repo@sha256:...")

    def invoke(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Stand-in for an Azure ML online endpoint: POST positional instances to a scoring URL.

        Same contract as the GCP adapter: a dict of named features in, a dict with
        predictions / model_version / endpoint out.
        """
        import json
        import os
        import urllib.request

        from src.data import FEATURES

        url = endpoint if endpoint.startswith(("http://", "https://")) else os.environ.get("AZURE_SCORING_URL")
        if not url:
            raise RuntimeError("Azure invoke needs a scoring URL: pass one or set AZURE_SCORING_URL")
        missing = [name for name in FEATURES if name not in payload]
        if missing:
            raise ValueError(f"Missing features: {missing}")
        body = json.dumps({"instances": [[payload[name] for name in FEATURES]]}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            out = json.load(resp)
        # /predict/instances returns no model version, unlike Vertex's deployed-model metadata.
        return {"predictions": out["predictions"], "model_version": "unknown", "endpoint": url}

    # submit_training / register_model  -> Lab 2 (Azure ML command job + model registry)
    # deploy / invoke                   -> Lab 3 (managed online endpoint + deployment)
    # emit_metric                       -> Lab 4 (Azure Monitor custom metric)
    # generate                          -> Lab 5 (managed LLM endpoint; read the usage block for tokens)
    # teardown                          -> Lab 5 (resource graph query by tag)
