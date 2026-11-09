# Data format

One snapshot per day: `data/snapshots/YYYY-MM-DD.jsonl`, one JSON object per
server. A companion `YYYY-MM-DD.summary.json` holds run totals.

## Fields

| Field | Type | Meaning |
|---|---|---|
| `server` | string | Registry name, e.g. `academy.ase/periodic-system` |
| `title` | string\|null | Human title from the registry |
| `description` | string | Registry description, truncated to 600 chars |
| `url` | string | The probed remote endpoint |
| `version` | string | Registry version probed |
| `repository` | string\|null | Source repository, when declared |
| `checked_at` | ISO8601 | UTC timestamp of the probe |
| `outcome` | enum | `ok`, `auth_required`, `not_found`, `dns_error`, `timeout`, `tls_error`, `transport_error`, `protocol_error`, `invalid_body` |
| `protocol_version` | string\|null | Version the server returned during `initialize` |
| `server_name`, `server_version` | string\|null | `serverInfo` from the handshake |
| `latency_init_ms`, `latency_tools_ms` | int\|null | Round-trip time per request |
| `checks` | object | Boolean results for each conformance test |
| `stats` | object | Counts: tools, schemas, params, annotations, duplicates |
| `evidence` | object | Raw response bodies and HTTP status for each check |
| `score` | object | See `docs/SCORING.md` |

## Example

```json
{
  "server": "academy.ase/periodic-system",
  "url": "https://ase.academy/mcp",
  "outcome": "ok",
  "protocol_version": "2025-06-18",
  "checks": {"initialize": true, "tools_list": true,
             "unknown_tool_errors": true, "unknown_tool_code": -32602,
             "unknown_method_errors": true, "unknown_method_code": -32601},
  "stats": {"tools": 4, "params": 8, "params_documented": 0,
            "tools_declaring_risk": 0, "duplicate_names": 0},
  "score": {"score": 75.0, "grade": "C", "rule_version": "1.0.0"}
}
```

## Stability

The record shape is versioned by `score.rule_version`. Fields may be added.
Fields will not be renamed or removed within a major version.
