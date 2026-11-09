# MCP Conformance Index

A public, daily-updated record of whether MCP servers actually work.

Every day, this project probes every remote server listed in the public MCP registry. It performs a protocol handshake, lists the tools, sends one deliberately invalid request, and records the result. It then publishes a dashboard, a raw dataset, and a free JSON API.

**Status:** in development. This document describes the intended v1.

---

## What this project achieves

### 1. It answers "does this server work" before anyone builds on it

Today an engineer connects a server to an agent, and the agent fails in a strange way. The engineer loses an hour.

Across 18,244 verified servers, the tool catalog costs **2,758 tokens per turn at the median** and **417,388 tokens in the worst case**. That number is paid again on every request, and nobody publishes it. Version 1 lists only servers we could verify. Auth-gated entries are counted and excluded.

### 2. It prices the context tax of every server

An agent sends the full `tools/list` payload to the model on every turn. That payload is a recurring cost, and it varies by four orders of magnitude. Measured on the verified set: median 2,758 tokens, p90 36,138, worst case 417,388 for one server with 128 tools.

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
- It does **not** test authenticated servers at all. In v1, servers that need a key to list tools or to call one are excluded from the dataset and counted separately. That is why the population is 18,244, not 40,524.
- It does **not** replace evals. It measures the tool layer, not your prompt or your model.
- It is **not** a security audit. It reads public schemas only.

The honest claim: **is this server reachable, what does it cost per turn, and is it well described?**

That is a narrow claim. It is also a claim nobody else can make with data today.

---

## Scope (v1)

Version 1 publishes **only servers that were verified end to end**: the endpoint answered, the tool list was read, and the invalid-call test executed. Everything else is excluded from the dataset and from every number on the site.

| Bucket | Entries |
|---|---|
| Registry entries with a remote URL | 40,524 |
| **Verified and published** | **18,244** |
| Excluded: needs a key to list tools | 11,821 |
| Excluded: needs a key to call a tool | 2,608 |
| Excluded: dead or unreachable | 5,420 |
| Excluded: protocol error | 1,897 |
| Excluded: call test not possible | 534 |

A server behind auth is not a bad server. It is an unknown server. Scoring it would be dishonest, so v1 does not score it and does not list it. The excluded counts stay on the page so the reader knows the denominator.

## Snapshot results

Verified set only, snapshot 2026-11-09.

| Metric | Result |
|---|---|
| Verified servers | 18,244 |
| Tools enumerated | 318,029 |
| Parameters | 1,556,984 |
| Parameters with a description | 1,428,406 (91.7%) |
| Tools declaring a risk annotation | 63.1% |
| Tools with `outputSchema` | 17.2% |
| **Context tax, median** | **2,758 tokens per turn** |
| **Context tax, p90** | **36,138 tokens** |
| **Context tax, p99** | **45,714 tokens** |
| **Context tax, worst observed** | **417,388 tokens** |
| Score grades | A 6,353, B 3,826, C 1,800, D 2,045, F 4,220 |

### How verified servers answer an invalid tool call

| Answer | Count | Share | Meaning |
|---|---|---|---|
| JSON-RPC error | 9,806 | 53.7% | Correct. The client sees a failure. |
| `result.isError = true` | 5,989 | 32.8% | Detectable, not spec-exact. |
| Error text inside `result.content` | 2,406 | 13.2% | Only detectable if the client parses prose. |
| No error signal at all | 43 | 0.2% | The client sees a success. |

### Two corrections this project made to its own work

**The 37% headline was false.** An early probe reported that 37% of servers answer an invalid call with a success code. The classifier had counted `401` responses and `result.isError` as failures. After the fix, undetectable successes measured **43 of 18,244 (0.2%)**.

**The score was flat.** The first weights handed every server 50 free points from components that never varied. Median score was 94.4 and told nobody anything. Rule v1.2.0 weights only the components that separate servers.

## Architecture

1. **Collector** — a scheduled job. Reads the registry, probes each remote server, writes one JSONL record per server with raw evidence.
2. **Dataset** — daily JSONL plus Parquet snapshots, committed to the repo under `data/`.
3. **Scoring** — five sub-scores (reachability, protocol conformance, schema quality, documentation, safety annotations). Weights and raw inputs are public.
4. **Dashboard** — a web UI with a leaderboard, per-server detail, failure-mode breakdown, and trends over time.
5. **JSON API** — free endpoints for servers, scores, and history, so others can build on the data.

## License

Code: MIT. Data: CC BY 4.0.
