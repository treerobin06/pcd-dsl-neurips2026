#!/usr/bin/env python3
"""Summarize router/scope-gate metrics from mixed E2E artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path
from typing import Any, Dict, List, Tuple

from _artifact_schema import save_artifact

SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = SCRIPT_DIR / "results"


def wilson(k: int, n: int) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    z = 1.96
    p = k / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    margin = z * sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def pct(k: int, n: int) -> Dict[str, Any]:
    lo, hi = wilson(k, n)
    return {"n": n, "correct": k, "rate": k / n if n else 0.0, "wilson_95ci": [lo, hi]}


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    supported_labels = {r["family_label"] for r in rows if r["family_label"] != "unsupported"}
    supported = [r for r in rows if r["family_label"] != "unsupported"]
    unsupported = [r for r in rows if r["family_label"] == "unsupported"]

    route_correct = sum(1 for r in rows if r.get("route_correct"))
    supported_accepted = sum(1 for r in supported if (r.get("route") or {}).get("decision") == "supported")
    unsupported_rejected = sum(1 for r in unsupported if (r.get("route") or {}).get("decision") == "reject")
    false_reject = len(supported) - supported_accepted
    false_accept = len(unsupported) - unsupported_rejected

    by_family: Dict[str, Any] = {}
    confusion = Counter()
    for label in sorted(supported_labels | {"unsupported"}):
        fam_rows = [r for r in rows if r["family_label"] == label]
        correct = sum(1 for r in fam_rows if r.get("route_correct"))
        by_family[label] = pct(correct, len(fam_rows))
        for r in fam_rows:
            route = r.get("route") or {}
            pred = route.get("family") if route.get("decision") == "supported" else "reject"
            confusion[(label, pred)] += 1

    precision_den = supported_accepted + false_accept
    reject_precision_den = unsupported_rejected + false_reject
    return {
        "route_accuracy": pct(route_correct, len(rows)),
        "supported_recall": pct(supported_accepted, len(supported)),
        "unsupported_reject_recall": pct(unsupported_rejected, len(unsupported)),
        "supported_precision": pct(supported_accepted, precision_den),
        "reject_precision": pct(unsupported_rejected, reject_precision_den),
        "false_reject": {"count": false_reject, "denominator": len(supported)},
        "false_accept": {"count": false_accept, "denominator": len(unsupported)},
        "by_family": by_family,
        "confusion": [
            {"gold": gold, "route": pred, "count": count}
            for (gold, pred), count in sorted(confusion.items())
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize router metrics from mixed E2E artifact")
    parser.add_argument("artifact", help="Path to all-family mixed E2E JSON artifact")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    path = Path(args.artifact)
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("results", [])
    if not rows:
        raise RuntimeError(f"No results rows found in {path}")
    summary = summarize(rows)
    print(json.dumps(summary, indent=2))

    out_path = Path(args.out) if args.out else RESULTS_DIR / f"router_metrics_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    save_artifact(
        str(out_path),
        {
            "experiment": "router_scope_gate_metrics",
            "source_artifact": str(path),
            "summary": summary,
        },
        prompt_tokens=0,
        completion_tokens=0,
        total_cost_usd=0.0,
        model_id=str(data.get("model", "derived")),
        extra_meta={"script": "baselines/summarize_router_metrics.py"},
    )
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
