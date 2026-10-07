"""Cloud Run Job entrypoint for scheduled drift detection."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from google.cloud import storage


PROJECT_ID = os.environ["PROJECT_ID"]
BUCKET = os.environ["DRIFT_BUCKET"]
REFERENCE_OBJECT = os.environ.get(
    "DRIFT_REFERENCE_OBJECT",
    "itcs355/drift/reference.csv",
)
CURRENT_OBJECT = os.environ.get(
    "DRIFT_CURRENT_OBJECT",
    "itcs355/drift/current.csv",
)


def download(bucket_name: str, object_name: str, destination: Path) -> None:
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    blob.download_to_filename(str(destination))
    print(f"downloaded gs://{bucket_name}/{object_name} -> {destination}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        reference = tmpdir / "reference.csv"
        current = tmpdir / "current.csv"

        download(BUCKET, REFERENCE_OBJECT, reference)
        download(BUCKET, CURRENT_OBJECT, current)

        cmd = [
            sys.executable,
            "-m",
            "monitoring.drift",
            "--reference",
            str(reference),
            "--current",
            str(current),
            "--emit",
        ]

        print("running:", " ".join(cmd))
        result = subprocess.run(cmd, check=False)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
