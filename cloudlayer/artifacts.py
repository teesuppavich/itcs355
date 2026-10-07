"""Fetch model artifacts by URI. Provider specifics live here, never in service/."""
from __future__ import annotations

import tempfile
from pathlib import Path


def fetch_model(uri: str, filename: str = "model.joblib") -> Path:
    """Download <uri>/<filename> into a temp dir and return the local path."""
    if not uri.startswith("gs://"):
        raise ValueError(f"unsupported model URI scheme: {uri}")
    from google.cloud import storage  # lazy: only the GCP path needs it

    bucket_name, _, prefix = uri[len("gs://"):].partition("/")
    prefix = prefix.strip("/")
    blob_name = f"{prefix}/{filename}" if prefix else filename
    dest = Path(tempfile.mkdtemp()) / filename
    storage.Client().bucket(bucket_name).blob(blob_name).download_to_filename(str(dest))
    return dest
