# Contributing

The index is only useful if the measurement is fair. Read this before you
change a rule.

## What gets measured

Each day every registry entry with an HTTP remote URL is probed:

1. TCP preflight (a dead host costs seconds, not a full timeout).
2. `initialize` with protocol version `2025-06-18`.
3. `notifications/initialized`.
4. `tools/list`.
5. One `tools/call` with a tool name that does not exist.
6. One JSON-RPC request with a method that does not exist.

We never call a real tool. That would be intrusive, costly, and unsafe.

## Rules for changing the probe

- **Never raise on a single server.** Every failure becomes a record.
- **Classify before you publish.** A `401`, a `429`, and a `result.isError`
  are three different facts. Lumping them together produced a false
  "37% silent failure" headline in an early build. Do not repeat it.
- **An unreached server is unknown, not bad.** No score. A `reason` field.
- **A weight on a component that never varies is a gift.** Check the
  standard deviation before you add weight. See `docs/SCORING.md`.
- **Weights are public.** Any change needs a new `rule_version` and a note
  in `docs/SCORING.md` that says what changed and why.

## Local run

```bash
python3 collector/run.py --pages 1                 # 100 servers, fast
python3 collector/aggregate.py --date YYYY-MM-DD
npm install && npm run dev
```

`data/snapshots/YYYY-MM-DD.jsonl` is the dataset. `data/dashboard.json` is
the aggregate the site reads. Both are committed by CI.

## Adding a metric

Add the raw input to `probe.py`, add a count to `stats`, then decide:

- Is it **quality**? Add a component with a weight, and prove it varies.
- Is it **cost**? Report it separately. Do not fold cost into quality.

## Data licence

Probe output is CC BY 4.0. Cite the date and the rule version.
