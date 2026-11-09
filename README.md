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

## Snapshot results

Full registry sweep, 2026-11-09. Every entry was probed. Nothing was sampled.

| Metric | Result |
|---|---|
| Registry entries with a remote URL | 40,524 |
| Interrogated (handshake and tool list) | 21,370 (52.7%) |
| Auth-gated, not inspectable without a key | 11,821 (29.2%) |
| Dead or unreachable (DNS, 404, TLS, timeout) | 5,420 (13.4%) |
| Protocol error | 1,897 (4.7%) |
| Tools enumerated | 390,285 |
| Parameters | 1,836,914 |
| Parameters with a description | 1,660,035 (90.4%) |
| Tools declaring a risk annotation | 68.3% |
| Tools with `outputSchema` | 17.4% |
| **Context tax, median** | **2,995 tokens per turn** |
| **Context tax, p90** | **36,340 tokens** |
| **Context tax, worst observed** | **417,388 tokens** |
| Score grades | A 8,415, B 4,052, C 1,912, D 2,434, F 4,557 |

### How servers answer an invalid tool call

We send one `tools/call` for a tool that does not exist, then classify the answer.

| Answer | Count | Share | Meaning |
|---|---|---|---|
| JSON-RPC error | 9,806 | 45.9% | Correct. The client sees a failure. |
| `result.isError = true` | 5,989 | 28.0% | Detectable, not spec-exact. |
| Error text inside `result.content` | 2,406 | 11.3% | Only detectable if the client parses prose. |
| No error signal at all | 43 | 0.2% | The client sees a success. |
| Auth required on the call | 2,608 | 12.2% | A security boundary, not a defect. |

### Two corrections this project made to its own work

**The 37% headline was false.** An early probe reported that 37% of servers answer an invalid call with a success code. The classifier had counted `401` responses and `result.isError` as failures. After the classifier was fixed, undetectable successes measured **43 of 21,370 (0.2%)**. The README kept the retraction on purpose.

**The score was flat.** The first weights handed every server 50 free points from components that never varied. Median score was 94.4 and told nobody anything. Rule v1.2.0 weights only the components that separate servers, and splits text-only errors from silent ones.

## Architecture

1. **Collector** — a scheduled job. Reads the registry, probes each remote server, writes one JSONL record per server with raw evidence.
2. **Dataset** — daily JSONL plus Parquet snapshots, committed to the repo under `data/`.
3. **Scoring** — five sub-scores (reachability, protocol conformance, schema quality, documentation, safety annotations). Weights and raw inputs are public.
4. **Dashboard** — a web UI with a leaderboard, per-server detail, failure-mode breakdown, and trends over time.
5. **JSON API** — free endpoints for servers, scores, and history, so others can build on the data.

## License

Code: MIT. Data: CC BY 4.0.
