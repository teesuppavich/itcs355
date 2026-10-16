"""Cloud Run Job entrypoint for scheduled drift detection."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from src import config
from cloudlayer.factory import get_adapter


BUCKET = os.environ["DRIFT_BUCKET"]
REFERENCE_OBJECT = os.environ.get(
    "DRIFT_REFERENCE_OBJECT",
    "itcs355/drift/reference.csv",
)
CURRENT_OBJECT = os.environ.get(
    "DRIFT_CURRENT_OBJECT",
    "itcs355/drift/current.csv",
)


def main() -> int:
    adapter = get_adapter(config.load(strict=False))
    scheme = urlparse(adapter.cfg.blob_uri).scheme

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        reference = tmpdir / "reference.csv"
        current = tmpdir / "current.csv"

        adapter.download(f"{scheme}://{BUCKET}/{REFERENCE_OBJECT}", str(reference))
        adapter.download(f"{scheme}://{BUCKET}/{CURRENT_OBJECT}", str(current))

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
