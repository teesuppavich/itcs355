"""Lab 5 — the registration gate.

Compares a candidate against the currently registered production model. Exits non-zero
when the candidate should NOT be registered, which is what makes the pipeline condition
real rather than decorative.

    python scripts/evaluation_gate.py --metrics reports/metrics.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.factory import get_adapter
from src import config

MIN_ABSOLUTE = 0.80
MIN_IMPROVEMENT = 0.02


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", type=Path, required=True)
    ap.add_argument("--metric", default="test_roc_auc")
    ap.add_argument("--incumbent", type=float, default=None,
                    help="current production score; omit to read from the registry")
    args = ap.parse_args()

    payload = json.loads(args.metrics.read_text())
    candidate = float(payload[args.metric])
    print(f"candidate {args.metric} = {candidate:.4f}")

    if candidate < MIN_ABSOLUTE:
        print(f"GATE FAIL  below absolute floor {MIN_ABSOLUTE}")
        return 1

    incumbent = args.incumbent
    if incumbent is None:
        try:
            key = {"test_roc_auc": "metric_test", "val_roc_auc": "metric_val"}[args.metric]
            cfg = config.load(strict=False)
            incumbent = get_adapter(cfg).latest_registered_metric(cfg.model_registry_name, key)
        except Exception as exc:
            print(f"GATE ERROR  cannot read the incumbent from the registry: {exc}")
            return 2
        if incumbent is None:
            print("no registered model yet; treating as first registration")
            print("GATE PASS")
            return 0
        print(f"incumbent from registry = {incumbent:.4f}")

    delta = candidate - incumbent
    print(f"incumbent {incumbent:.4f}  delta {delta:+.4f}  required {MIN_IMPROVEMENT:+.4f}")
    if delta < MIN_IMPROVEMENT:
        reason = "candidate worse than incumbent" if delta < 0 else "improvement within noise"
        print(f"GATE FAIL  {reason}; not registering")
        return 1

    print("GATE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
