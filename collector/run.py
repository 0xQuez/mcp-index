"""Run one snapshot of the MCP Conformance Index.

    python3 collector/run.py --pages 1 --workers 12
    python3 collector/run.py --out data/snapshots

Writes one JSONL file per run plus a run summary. Never raises on a
single server failure: every failure becomes a record.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import probe  # noqa: E402
import scoring  # noqa: E402


def build_targets(max_pages=None):
    targets = []
    seen = set()
    for entry in probe.registry_servers(max_pages=max_pages):
        server = entry.get("server") or {}
        name = server.get("name")
        url = probe.remote_url(server)
        if not name or not url or name in seen:
            continue
        seen.add(name)
        targets.append({
            "name": name,
            "title": server.get("title"),
            "description": (server.get("description") or "").strip(),
            "url": url,
            "version": server.get("version"),
            "repository": (server.get("repository") or {}).get("url"),
            "published_at": ((entry.get("_meta") or {})
                             .get("io.modelcontextprotocol.registry/official") or {}).get("publishedAt"),
        })
    return targets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/snapshots")
    ap.add_argument("--pages", type=int, default=None, help="limit registry pages (100 servers each)")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--limit", type=int, default=None, help="cap number of servers probed")
    args = ap.parse_args()

    started = time.time()
    targets = build_targets(args.pages)
    if args.limit:
        targets = targets[:args.limit]
    print(f"targets={len(targets)}", flush=True)

    os.makedirs(args.out, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d", time.gmtime())
    path = os.path.join(args.out, f"{stamp}.jsonl")
    tmp = path + ".part"

    counts = Counter()
    scores = []
    done = 0

    with open(tmp, "w", encoding="utf-8") as fh, ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe.probe, t["url"], args.timeout): t for t in targets}
        for future in as_completed(futures):
            target = futures[future]
            try:
                rec = future.result()
            except Exception as exc:  # noqa: BLE001 - a crash must still yield a record
                rec = {"url": target["url"], "outcome": "probe_crash",
                       "evidence": {"error": f"{type(exc).__name__}: {exc}"[:300]},
                       "checks": {}, "stats": {}}
            rec.update({
                "server": target["name"],
                "title": target["title"],
                "description": target["description"][:600],
                "version": target["version"],
                "repository": target["repository"],
            })
            rec["score"] = scoring.score(rec)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            counts[rec["outcome"]] += 1
            if rec["score"]["score"] is not None:
                scores.append(rec["score"]["score"])
            done += 1
            if done % 250 == 0:
                print(f"  {done}/{len(targets)} in {int(time.time()-started)}s", flush=True)

    os.replace(tmp, path)
    elapsed = int(time.time() - started)
    scores.sort()
    summary = {
        "date": stamp,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_s": elapsed,
        "targets": len(targets),
        "outcomes": dict(counts),
        "scored": len(scores),
        "score_median": scores[len(scores) // 2] if scores else None,
        "score_mean": round(sum(scores) / len(scores), 1) if scores else None,
        "score_p90": scores[int(len(scores) * 0.9)] if scores else None,
        "file": os.path.basename(path),
        "rule_version": scoring.RULE_VERSION,
    }
    with open(os.path.join(args.out, f"{stamp}.summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
