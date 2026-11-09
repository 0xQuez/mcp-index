"""MCP Conformance Index — probe library.

Stdlib only. One job: take a registry server record, probe its remote
endpoint, and return a record of what actually happened, with evidence.
"""

from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

REGISTRY = "https://registry.modelcontextprotocol.io/v0/servers"
PROTOCOL_VERSION = "2025-06-18"
USER_AGENT = "mcp-index/0.1 (+https://github.com/0xQuez/mcp-index)"
MAX_BODY = 2_000_000
ERROR_MODES = ("error_object", "result_iserror", "result_text_error")
TESTABLE_MODES = ERROR_MODES + ("silent_success",)
KNOWN_TEXT_ERROR = re.compile(
    r"(?i)\b(unknown tool|tool not found|invalid tool|no such tool|"
    r"not found|error|invalid|unrecogni[sz]ed)\b"
)


class Outcome:
    OK = "ok"
    AUTH_REQUIRED = "auth_required"
    NOT_FOUND = "not_found"
    DNS_ERROR = "dns_error"
    TIMEOUT = "timeout"
    TLS_ERROR = "tls_error"
    TRANSPORT_ERROR = "transport_error"
    PROTOCOL_ERROR = "protocol_error"
    INVALID_BODY = "invalid_body"


def _request(url, payload=None, sid=None, timeout=20, method=None):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/event-stream",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
        method = method or "POST"
    if sid:
        headers["Mcp-Session-Id"] = sid
    req = urllib.request.Request(url, data=data, headers=headers, method=method or "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(MAX_BODY)
            return resp.status, dict(resp.headers), raw, None
    except urllib.error.HTTPError as exc:
        raw = b""
        try:
            raw = exc.read(4096)
        except Exception:
            pass
        return exc.code, dict(exc.headers or {}), raw, f"HTTP {exc.code}"
    except socket.timeout:
        return None, {}, b"", "timeout"
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.timeout):
            return None, {}, b"", "timeout"
        text = str(reason)
        if "Name or service not known" in text or "nodename nor servname" in text:
            return None, {}, b"", "dns_error"
        if "certificate" in text.lower() or "ssl" in text.lower():
            return None, {}, b"", "tls_error"
        return None, {}, b"", f"transport:{text[:120]}"
    except Exception as exc:  # noqa: BLE001 - classify, never crash a run
        return None, {}, b"", f"transport:{type(exc).__name__}:{str(exc)[:100]}"


def _decode(raw, headers):
    ctype = (headers.get("Content-Type") or "").lower()
    if not raw:
        return None
    text = raw.decode("utf-8", "replace").strip()
    if "text/event-stream" in ctype or text.startswith("data:"):
        # Server-Sent Events: take the last complete data frame.
        frames = [ln[5:].strip() for ln in text.splitlines() if ln.startswith("data:")]
        for frame in reversed(frames):
            if not frame or frame == "[DONE]":
                continue
            try:
                return json.loads(frame)
            except json.JSONDecodeError:
                continue
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Some servers batch multiple JSON objects; take the first that parses.
        for chunk in text.split("\n"):
            chunk = chunk.strip()
            if chunk.startswith("{"):
                try:
                    return json.loads(chunk)
                except json.JSONDecodeError:
                    continue
        return "UNPARSEABLE"


def rpc(url, payload, sid=None, timeout=20):
    status, headers, raw, err = _request(url, payload, sid=sid, timeout=timeout)
    if err:
        return None, sid, {"transport": err, "http_status": status}
    body = _decode(raw, headers)
    new_sid = headers.get("Mcp-Session-Id") or sid
    return body, new_sid, {"http_status": status}


def refine_mode(rec):
    """Re-derive the unknown-tool mode from stored evidence.

    Lets a rule change apply to existing snapshots without re-probing.
    """
    checks = rec.setdefault("checks", {})
    mode = checks.get("unknown_tool_mode")
    if mode == "silent_success":
        body = str(((rec.get("evidence") or {}).get("unknown_tool") or {}).get("body") or "")
        if KNOWN_TEXT_ERROR.search(body):
            mode = "result_text_error"
    if mode:
        checks["unknown_tool_mode"] = mode
        checks["unknown_tool_errors"] = mode in ERROR_MODES
        checks["unknown_tool_silent"] = mode == "silent_success"
        if mode in TESTABLE_MODES:
            checks["call_testable"] = True
    return rec


def _schema(tool):
    return tool.get("inputSchema") or tool.get("input_schema") or {}


def _tool_stats(tools):
    """Structural facts about the tool set. No judgement, only counts.

    Includes context cost: the tools/list payload is re-sent to the model on
    every turn, so its size is a real, recurring token cost.
    """
    total = len(tools)
    described_params = 0
    total_params = 0
    has_annotations = 0
    declares_risk = 0
    object_schema = 0
    required_ok = 0
    empty_schema = 0
    output_schema = 0
    enum_params = 0
    nested_params = 0
    desc_chars = 0
    tool_desc_chars = 0
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        schema = _schema(tool)
        props = schema.get("properties") or {}
        required = schema.get("required") or []
        if schema.get("type") == "object":
            object_schema += 1
        if not props and not required:
            empty_schema += 1
        if not (set(required) - set(props)):
            required_ok += 1
        if tool.get("outputSchema"):
            output_schema += 1
        tdesc = (tool.get("description") or "").strip()
        tool_desc_chars += len(tdesc)
        for name, spec in props.items():
            total_params += 1
            if not isinstance(spec, dict):
                continue
            pdesc = (spec.get("description") or "").strip()
            desc_chars += len(pdesc)
            if pdesc:
                described_params += 1
            if spec.get("enum"):
                enum_params += 1
            if spec.get("type") == "object" or spec.get("items", {}).get("type") == "object":
                nested_params += 1
        ann = tool.get("annotations") or {}
        if ann:
            has_annotations += 1
        if ann.get("readOnlyHint") is not None or ann.get("destructiveHint") is not None:
            declares_risk += 1

    payload_bytes = len(json.dumps(tools, ensure_ascii=False).encode())
    return {
        "tools": total,
        "object_schemas": object_schema,
        "empty_schemas": empty_schema,
        "required_ok": required_ok,
        "params": total_params,
        "params_documented": described_params,
        "params_with_enum": enum_params,
        "params_nested_object": nested_params,
        "tools_with_output_schema": output_schema,
        "tools_with_annotations": has_annotations,
        "tools_declaring_risk": declares_risk,
        "payload_bytes": payload_bytes,
        "est_tokens": round(payload_bytes / 4),
        "desc_chars": desc_chars + tool_desc_chars,
    }


def preflight(url, timeout=5):
    """Cheap TCP reachability test before a full probe.

    A dead host burns the full HTTP timeout. A TCP connect burns a few
    seconds at most, so the nightly run stops spending hours on dead
    registry entries.
    """
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname
    if not host:
        return "dns_error"
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return None
    except socket.gaierror:
        return "dns_error"
    except socket.timeout:
        return "timeout"
    except OSError:
        return "transport_error"


def probe(url, timeout=20, use_preflight=True):
    """Probe one remote MCP endpoint. Returns a record. Never raises."""
    rec = {
        "url": url,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "outcome": None,
        "protocol_version": None,
        "server_name": None,
        "server_version": None,
        "session": False,
        "latency_init_ms": None,
        "latency_tools_ms": None,
        "checks": {},
        "stats": {},
        "evidence": {},
    }

    if use_preflight:
        blocked = preflight(url)
        if blocked:
            rec["outcome"] = blocked
            rec["evidence"]["preflight"] = {"result": blocked, "note": "TCP connect failed"}
            return rec

    started = time.time()
    body, sid, meta = rpc(url, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "mcp-index", "version": "0.1"},
        },
    }, timeout=timeout)
    rec["latency_init_ms"] = int((time.time() - started) * 1000)

    if body is None:
        transport = (meta or {}).get("transport", "")
        status = (meta or {}).get("http_status")
        if status in (401, 403):
            rec["outcome"] = Outcome.AUTH_REQUIRED
        elif status == 404:
            rec["outcome"] = Outcome.NOT_FOUND
        elif transport == "timeout":
            rec["outcome"] = Outcome.TIMEOUT
        elif transport == "dns_error":
            rec["outcome"] = Outcome.DNS_ERROR
        elif transport == "tls_error":
            rec["outcome"] = Outcome.TLS_ERROR
        else:
            rec["outcome"] = Outcome.TRANSPORT_ERROR
        rec["evidence"]["init"] = {"transport": transport, "http_status": status}
        return rec

    if body == "UNPARSEABLE":
        rec["outcome"] = Outcome.INVALID_BODY
        rec["evidence"]["init"] = {"raw": "unparseable"}
        return rec

    result = (body or {}).get("result") if isinstance(body, dict) else None
    if not result:
        rec["outcome"] = Outcome.PROTOCOL_ERROR
        rec["evidence"]["init"] = {"body": str(body)[:400]}
        return rec

    rec["protocol_version"] = result.get("protocolVersion")
    info = result.get("serverInfo") or {}
    rec["server_name"] = info.get("name")
    rec["server_version"] = info.get("version")
    rec["session"] = bool(sid)
    rec["checks"]["initialize"] = True

    try:
        rpc(url, {"jsonrpc": "2.0", "method": "notifications/initialized"},
            sid=sid, timeout=min(timeout, 10))
    except Exception:  # noqa: BLE001 - notification failure is not fatal
        pass

    started = time.time()
    tl_body, sid, tl_meta = rpc(
        url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        sid=sid, timeout=timeout)
    rec["latency_tools_ms"] = int((time.time() - started) * 1000)
    tools = ((tl_body or {}).get("result") or {}).get("tools") if isinstance(tl_body, dict) else None
    if not isinstance(tools, list):
        rec["outcome"] = Outcome.PROTOCOL_ERROR
        rec["evidence"]["tools_list"] = {"body": str(tl_body)[:400], "meta": tl_meta}
        return rec

    rec["checks"]["tools_list"] = True
    rec["stats"] = _tool_stats(tools)

    # Conformance check 1: an unknown tool must be *detectable* by the agent.
    # Three possible outcomes, and they are not equal:
    #   error_object  - JSON-RPC error. Best. Spec-compliant.
    #   result_iserror - HTTP 200, but result.isError = true. Detectable.
    #   silent_success - HTTP 200, no error flag. The agent sees a success.
    # Auth responses on call are a security boundary, not a protocol defect.
    bad, _, bad_meta = rpc(url, {
        "jsonrpc": "2.0", "id": 9, "method": "tools/call",
        "params": {"name": "__mcp_index_nonexistent__", "arguments": {}},
    }, sid=sid, timeout=timeout)

    mode = "no_response"
    code = None
    if isinstance(bad, dict):
        err = bad.get("error")
        result = bad.get("result")
        if isinstance(err, dict):
            mode = "error_object"
            code = err.get("code")
        elif isinstance(result, dict):
            if result.get("isError") is True:
                mode = "result_iserror"
            else:
                # Some servers signal the error as plain text inside
                # result.content and leave isError unset. A client that
                # checks the flag sees success. Classify separately.
                text = " ".join(
                    str(part.get("text") or "")
                    for part in (result.get("content") or [])
                    if isinstance(part, dict)
                )[:600]
                mode = "result_text_error" if KNOWN_TEXT_ERROR.search(text) else "silent_success"
        else:
            mode = "unparseable"
    status = (bad_meta or {}).get("http_status")
    if mode == "no_response" and status in (401, 403):
        mode = "auth_on_call"
    elif mode == "no_response" and status:
        mode = f"http_{status}"

    rec["checks"]["unknown_tool_mode"] = mode
    rec["checks"]["unknown_tool_errors"] = mode in ERROR_MODES
    rec["checks"]["unknown_tool_code"] = code
    rec["checks"]["unknown_tool_silent"] = mode == "silent_success"
    rec["checks"]["call_testable"] = mode in TESTABLE_MODES
    rec["evidence"]["unknown_tool"] = {"body": str(bad)[:300], "meta": bad_meta}

    # Conformance check 2: an unknown method must produce -32601.
    m_body, _, m_meta = rpc(url, {
        "jsonrpc": "2.0", "id": 10, "method": "mcp-index/does-not-exist", "params": {},
    }, sid=sid, timeout=timeout)
    m_err = m_body.get("error") if isinstance(m_body, dict) else None
    m_code = m_err.get("code") if isinstance(m_err, dict) else None
    rec["checks"]["unknown_method_errors"] = isinstance(m_err, dict)
    rec["checks"]["unknown_method_code"] = m_code
    rec["evidence"]["unknown_method"] = {"body": str(m_body)[:300], "meta": m_meta}

    # Tool name hygiene and duplicate detection.
    names = [t.get("name") for t in tools if isinstance(t, dict)]
    rec["stats"]["duplicate_names"] = len(names) - len(set(names))
    rec["stats"]["tools"] = len(names)
    rec["evidence"]["tool_names"] = names[:80]

    rec["outcome"] = Outcome.OK
    return rec


def registry_servers(limit=100, max_pages=None, sleep=0.0):
    """Yield every server record from the registry, following cursors."""
    cursor = None
    pages = 0
    while True:
        url = f"{REGISTRY}?limit={limit}&version=latest"
        if cursor:
            url += f"&cursor={urllib.parse.quote(cursor, safe='')}"
        status, headers, raw, err = _request(url, timeout=45)
        if err:
            raise RuntimeError(f"registry fetch failed: {err}")
        payload = _decode(raw, headers)
        if not isinstance(payload, dict):
            raise RuntimeError("registry returned an unparseable body")
        for entry in payload.get("servers") or []:
            yield entry
        pages += 1
        cursor = (payload.get("metadata") or {}).get("nextCursor")
        if not cursor or (max_pages and pages >= max_pages):
            return
        if sleep:
            time.sleep(sleep)


def remote_url(server):
    for remote in server.get("remotes") or []:
        url = remote.get("url")
        if url and url.startswith("http"):
            return url
    return None
