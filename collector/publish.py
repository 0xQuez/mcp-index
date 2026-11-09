"""Post-process a snapshot: compress, prune, and update the file index.

    python3 collector/publish.py --dir data/snapshots --keep-days 90
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe  # noqa: E402
import scoring  # noqa: E402

NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl(\.gz)?$")


def rescore(path):
    """Recompute scores with the current rule version so data and site agree."""
    gz = path.endswith(".gz")
    opener = gzip.open if gz else open
    records = []
    changed = 0
    skipped = 0
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            probe.refine_mode(rec)
            new = scoring.score(rec)
            if (rec.get("score") or {}).get("rule_version") != new.get("rule_version"):
                changed += 1
            rec["score"] = new
            records.append(rec)
    writer = gzip.open if gz else open
    with writer(path, "wt", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return changed, len(records)



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/snapshots")
    ap.add_argument("--keep-days", type=int, default=90)
    args = ap.parse_args()

    for name in sorted(os.listdir(args.dir)):
        if not NAME.match(name):
            continue
        changed, total = rescore(os.path.join(args.dir, name))
        print(f"rescored {name}: {changed} rule changes, {total} records")

    compressed = []
    for name in sorted(os.listdir(args.dir)):
        match = NAME.match(name)
        if not match or name.endswith(".gz"):
            continue
        raw_path = os.path.join(args.dir, name)
        gz_path = raw_path + ".gz"
        with open(raw_path, "rb") as src, gzip.open(gz_path, "wb", compresslevel=9) as dst:
            dst.write(src.read())
        os.remove(raw_path)
        compressed.append(gz_path)
        print(f"compressed {name}")

    cutoff = time.time() - args.keep_days * 86400
    pruned = 0
    for name in list(os.listdir(args.dir)):
        if not name.endswith(".jsonl.gz"):
            continue
        path = os.path.join(args.dir, name)
        if os.path.getmtime(path) < cutoff:
            os.remove(path)
            pruned += 1

    files = sorted(n for n in os.listdir(args.dir) if n.endswith(".jsonl.gz"))
    index = {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "snapshots": files, "count": len(files),
             "pruned": pruned, "new_this_run": len(compressed)}
    with open(os.path.join(args.dir, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2)
    print(json.dumps(index, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
