"""Aggregate a snapshot into the JSON the dashboard consumes.

    python3 collector/aggregate.py --date 2026-11-09

Reads data/snapshots/<date>.jsonl (or .jsonl.gz) and writes
data/dashboard.json. All dashboard numbers come from this file, so the
site never computes statistics at request time.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoring  # noqa: E402

# Reference prices, USD per million input tokens. Stated on the site next to
# any dollar figure. Update deliberately, never silently.
PRICES = [
    {"model": "GPT-5.4", "input_per_m": 1.25, "as_of": "2026-11-01"},
    {"model": "Claude Fable 5.1", "input_per_m": 3.00, "as_of": "2026-11-01"},
    {"model": "Gemini 3.5 Pro", "input_per_m": 1.25, "as_of": "2026-11-01"},
]

BUCKETS = [("0-1k", 0, 1000), ("1k-3k", 1000, 3000), ("3k-10k", 3000, 10000),
           ("10k-30k", 10000, 30000), ("30k+", 30000, 10**12)]


def load(path):
    opener = gzip.open if path.endswith(".gz") else open
    skipped = 0
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # A torn line can only happen when reading a file that is
                # still being written. Count it, never crash the aggregation.
                skipped += 1
    if skipped:
        print(f"warning: skipped {skipped} unparseable line(s)")


def find_snapshot(directory, date):
    for name in (f"{date}.jsonl", f"{date}.jsonl.gz"):
        path = os.path.join(directory, name)
        if os.path.exists(path):
            return path
    raise SystemExit(f"no snapshot for {date} in {directory}")


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(len(ordered) * q))
    return ordered[idx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--dir", default="data/snapshots")
    ap.add_argument("--out", default="data/dashboard.json")
    args = ap.parse_args()

    path = find_snapshot(args.dir, args.date)
    records = list(load(path))
    scored = [r for r in records if (r.get("score") or {}).get("score") is not None]
    reachable = [r for r in records if r.get("outcome") == "ok"]
    outcomes = Counter(r.get("outcome") for r in records)

    total = len(records)
    tokens = [r["stats"]["est_tokens"] for r in reachable if "est_tokens" in r.get("stats", {})]
    params = sum(r["stats"].get("params", 0) for r in reachable)
    documented = sum(r["stats"].get("params_documented", 0) for r in reachable)
    tools = sum(r["stats"].get("tools", 0) for r in reachable)
    risk = sum(r["stats"].get("tools_declaring_risk", 0) for r in reachable)
    output_schema = sum(r["stats"].get("tools_with_output_schema", 0) for r in reachable)

    modes = Counter((r.get("checks") or {}).get("unknown_tool_mode") for r in reachable)

    def money(tok):
        return {p["model"]: round(tok / 1_000_000 * p["input_per_m"], 4) for p in PRICES}

    hist = []
    for label, lo, hi in BUCKETS:
        hist.append({"bucket": label, "count": sum(1 for t in tokens if lo <= t < hi)})

    leaderboard = sorted(
        (r for r in scored if "est_tokens" in r.get("stats", {})),
        key=lambda r: (-r["score"]["score"], r["stats"]["est_tokens"]))[:100]

    def row(r):
        s = r["stats"]
        return {
            "server": r.get("server"),
            "title": r.get("title"),
            "url": r.get("url"),
            "description": (r.get("description") or "")[:200],
            "score": r["score"]["score"],
            "grade": r["score"]["grade"],
            "tools": s.get("tools", 0),
            "params": s.get("params", 0),
            "est_tokens": s.get("est_tokens"),
            "usd_per_turn": money(s.get("est_tokens") or 0),
            "doc_rate": round(s.get("params_documented", 0) / s["params"], 3) if s.get("params") else None,
            "conformance": (r.get("checks") or {}).get("unknown_tool_mode"),
            "latency_ms": r.get("latency_init_ms"),
        }

    payload = {
        "date": args.date,
        "rule_version": scoring.RULE_VERSION,
        "generated_at": records[0].get("checked_at") if records else None,
        "totals": {
            "servers": total,
            "reachable": len(reachable),
            "scored": len(scored),
            "inspectability": round(len(reachable) / total, 4) if total else None,
            "tools": tools,
            "params": params,
            "params_documented": documented,
            "doc_rate": round(documented / params, 4) if params else None,
            "risk_declared_rate": round(risk / tools, 4) if tools else None,
            "output_schema_rate": round(output_schema / tools, 4) if tools else None,
        },
        "outcomes": dict(outcomes),
        "conformance_modes": {str(k): v for k, v in modes.items()},
        "context_tax": {
            "median": percentile(tokens, 0.5),
            "p90": percentile(tokens, 0.9),
            "p99": percentile(tokens, 0.99),
            "max": max(tokens) if tokens else None,
            "median_usd": money(percentile(tokens, 0.5) or 0),
            "prices": PRICES,
            "histogram": hist,
        },
        "grades": dict(Counter(r["score"]["grade"] for r in scored)),
        "score_median": statistics.median([r["score"]["score"] for r in scored]) if scored else None,
        "leaderboard": [row(r) for r in leaderboard],
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    print(json.dumps({k: v for k, v in payload.items() if k != "leaderboard"}, indent=2)[:2000])
    print(f"wrote {args.out} ({os.path.getsize(args.out)} bytes)")


if __name__ == "__main__":
    raise SystemExit(main())
