# MCP Conformance Index

A public, daily-updated record of whether MCP servers actually work.

Every day, this project probes every remote server listed in the public MCP registry. It performs a protocol handshake, lists the tools, sends one deliberately invalid request, and records the result. It then publishes a dashboard, a raw dataset, and a free JSON API.

**Status:** in development. This document describes the intended v1.

---

## What this project achieves

### 1. It answers "does this server work" before anyone builds on it

Today an engineer connects a server to an agent, and the agent fails in a strange way. The engineer loses an hour.

A first probe of 262 registry entries found that **half of them cannot be inspected at all without credentials**, and that a single server's tool catalog can cost **125,000 tokens of context on every turn**. Those two facts decide whether a server is usable in an agent. Neither is published anywhere today.

### 2. It prices the context tax of every server

An agent sends the full `tools/list` payload to the model on every turn. That payload is a recurring cost, and it varies by four orders of magnitude across servers. Measured so far: median 2,031 tokens, 90th percentile 9,507, worst case 125,392 for one server with 128 tools.

Nobody publishes this number. It is the reason some agents are slow and expensive for no visible reason.

### 3. It creates a dataset that does not exist

No public record exists of MCP server health over time.

- The official MCP registry lists servers. It does not rate them.
- The official conformance tool is a library you run against your own server. It is not an index.
- The commercial monitoring options are closed and paid.

This project publishes the raw JSONL and Parquet snapshots, so other people can fork the data and build their own tools.

### 4. Every metric has one job

| Metric | The question it answers | Why it matters |
|---|---|---|
| Reachability (gate) | Can I reach it today? | An unreached server gets no score |
| Inspectability | Can I evaluate it without a key? | Half the registry hides behind auth |
| Error conformance | Does it fail correctly? | An undetectable failure burns agent turns |
| Parameter documentation | Can a model fill in the arguments? | Undocumented fields cause wrong tool calls |
| Safety annotations | Does it declare risk? | Agents need to know which tools destroy data |
| **Context tax** | **What does this server cost per turn?** | **Token cost recurs on every request** |
| Latency | Is it usable in an agent loop? | Slow tools break the user experience |

Every score has a raw input behind it. Anyone can check the arithmetic. That is the difference between a rating and a guess.

Context tax is reported, not scored. A large tool catalog can be legitimate. Charging it as a defect would be dishonest. The dashboard plots quality and cost as two axes, so both facts stay visible.

---

## Who gets value

**Applied AI engineers.** Pick a server, check the score, skip a debugging session.

**MCP server authors.** Get a public scoreboard and a specific list of defects to fix.

**Agent framework and client maintainers.** Get a compatibility signal across many servers without testing each one by hand.

**Platform and enterprise teams.** Shortlist servers and show due diligence. "We only adopt servers with conformance above X" is a policy they can defend.

**Researchers and builders.** Get a free dataset, a free API, and a citation.

---

## What this project does not do

This scope is deliberately narrow. Overselling would weaken the project.

- It does **not** judge the quality of a tool's output. A server can pass conformance and still return bad data.
- It does **not** test authenticated servers deeply. In the first probe, 33 of 94 servers required a key. This project measures the door, not the room.
- It does **not** replace evals. It measures the tool layer, not your prompt or your model.
- It is **not** a security audit. It reads public schemas only.

The honest claim: **is this server reachable, what does it cost per turn, and is it well described?**

That is a narrow claim. It is also a claim nobody else can make with data today.

---

## First probe results

Direct measurements against the live MCP registry. 262 entries, 169 remote endpoints reachable, 103 servers fully interrogated. Run on 2026-11-09.

| Metric | Result |
|---|---|
| Registry entries fetched | 6,100+ |
| Entries with a remote URL | 5,731 |
| Sampled for this probe | 262 |
| Auth-gated (`401`/`403`) | 129 (49%) |
| Dead or broken (DNS, 404, 400, timeout) | 30 (11%) |
| Fully interrogated | 103 |
| Total tools enumerated | 1,204 |
| Median tools per server | 6 (p90 24, max 160) |
| Parameters across all tools | 4,312 |
| Parameters with a description | 2,740 (64%) |
| Tools declaring risk annotations | 94% |
| Tools with `outputSchema` (MCP 2025-06-18) | 317 (26%) |
| **Context tax, median** | **2,031 tokens** |
| **Context tax, p90** | **9,507 tokens** |
| **Context tax, worst observed** | **125,392 tokens** |
| Handshake latency | p50 489 ms, p95 888 ms |
| Invalid tool call returned a JSON-RPC error | 53 of 103 |
| Invalid tool call returned `result.isError` | 32 of 103 |
| Invalid tool call returned a false success | **0 of 85 testable** |
| Unknown method returned `-32601` | 68 of 82 |

### What this corrected

An early probe reported that 37% of servers answer an invalid tool call with a success code. That was wrong. The probe had counted `401` responses and `result.isError: true` as failures. After fixing the classifier, **zero** servers returned an undetectable success.

The real defects are different, and more useful: half the registry cannot be evaluated without credentials, documentation coverage is 64%, and the context tax ranges across four orders of magnitude.

## Architecture

1. **Collector** — a scheduled job. Reads the registry, probes each remote server, writes one JSONL record per server with raw evidence.
2. **Dataset** — daily JSONL plus Parquet snapshots, committed to the repo under `data/`.
3. **Scoring** — five sub-scores (reachability, protocol conformance, schema quality, documentation, safety annotations). Weights and raw inputs are public.
4. **Dashboard** — a web UI with a leaderboard, per-server detail, failure-mode breakdown, and trends over time.
5. **JSON API** — free endpoints for servers, scores, and history, so others can build on the data.

## License

Code: MIT. Data: CC BY 4.0.
