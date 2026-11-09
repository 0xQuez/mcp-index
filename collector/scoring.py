"""Scoring. Every number here is derived from raw probe output.

Rules are deliberately simple and public. If a component has no inputs
(for example a server with zero tools), it is marked n/a and its weight
is redistributed across the components that do have inputs.
"""

from __future__ import annotations

# Weights are set by how much each component actually separates servers,
# measured across 4,282 probed servers on 2026-11-09:
#   reachability  sd = 0.00  (only reached servers get scored, so keep as a gate)
#   schema        sd = 0.00  (near-universal pass; small weight, kept as a gate)
#   conformance   sd = 0.20
#   documentation sd = 0.30
#   safety        sd = 0.42
# A weight on a component that never varies is a free gift to every server.
WEIGHTS = {
    "conformance": 35,
    "documentation": 35,
    "safety": 25,
    "schema": 5,
}
RULE_VERSION = "1.2.0"


def probe_ok():
    return "ok"


def _ratio(num, den):
    if not den:
        return None
    return max(0.0, min(1.0, num / den))


def subscores(rec):
    checks = rec.get("checks") or {}
    stats = rec.get("stats") or {}

    conf = None
    if checks.get("call_testable"):
        conf = 0.0
        mode = checks.get("unknown_tool_mode")
        if mode == "error_object":
            conf += 0.6
        elif mode == "result_iserror":
            conf += 0.3
        elif mode == "result_text_error":
            conf += 0.15
        if checks.get("unknown_method_errors"):
            conf += 0.4

    tools = stats.get("tools") or 0
    schema = _ratio(stats.get("object_schemas", 0) + stats.get("required_ok", 0), 2 * tools) if tools else None
    doc = _ratio(stats.get("params_documented", 0), stats.get("params", 0))
    safety = _ratio(stats.get("tools_declaring_risk", 0), tools) if tools else None

    return {
        "reachability": {"value": 1.0 if checks.get("tools_list") else 0.0,
                         "weight": 0,
                         "raw": {"initialize": bool(checks.get("initialize")),
                                 "tools_list": bool(checks.get("tools_list")),
                                 "note": "gate only, not weighted"}},
        "conformance": {"value": None if conf is None else round(conf, 4),
                        "weight": WEIGHTS["conformance"],
                        "raw": {"unknown_tool_mode": checks.get("unknown_tool_mode"),
                                "unknown_method_errors": bool(checks.get("unknown_method_errors")),
                                "unknown_tool_code": checks.get("unknown_tool_code")}},
        "schema": {"value": None if schema is None else round(schema, 4),
                   "weight": WEIGHTS["schema"],
                   "raw": {"object_schemas": stats.get("object_schemas", 0),
                           "required_ok": stats.get("required_ok", 0), "tools": tools}},
        "documentation": {"value": None if doc is None else round(doc, 4),
                          "weight": WEIGHTS["documentation"],
                          "raw": {"params_documented": stats.get("params_documented", 0),
                                  "params": stats.get("params", 0)}},
        "safety": {"value": None if safety is None else round(safety, 4),
                   "weight": WEIGHTS["safety"],
                   "raw": {"tools_declaring_risk": stats.get("tools_declaring_risk", 0),
                           "tools": tools}},
    }


def grade_for(score):
    if score is None:
        return None
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 55:
        return "D"
    return "F"


def score(rec):
    # Only a server we could actually interrogate gets a score.
    # An auth-gated or dead server is unknown, not bad.
    if rec.get("outcome") != probe_ok():
        return {
            "score": None,
            "grade": None,
            "reason": rec.get("outcome"),
            "components": None,
            "weights_applied": {},
            "weights_skipped": list(WEIGHTS),
            "rule_version": RULE_VERSION,
        }

    parts = subscores(rec)
    available = {k: v for k, v in parts.items()
                 if v["value"] is not None and v["weight"] > 0}
    weight_sum = sum(v["weight"] for v in available.values())
    if not weight_sum:
        total = None
    else:
        total = round(100 * sum(v["value"] * v["weight"] for v in available.values()) / weight_sum, 1)
    return {
        "score": total,
        "grade": grade_for(total),
        "components": parts,
        "weights_applied": {k: v["weight"] for k, v in available.items()},
        "weights_skipped": [k for k, v in parts.items() if v["value"] is None],
        "rule_version": RULE_VERSION,
    }
