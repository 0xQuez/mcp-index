# Scoring rules (v1.2.0)

The index answers one question per metric. No metric guesses. Every score
is computed from raw probe output that ships in the same record.

## The five components

| Component | Weight | Inputs | What it proves |
|---|---|---|---|
| Conformance | 35 | JSON-RPC error (60%), `result.isError` (30%), unknown method returns `-32601` (40%) | The agent can detect a failed call |
| Documentation | 35 | share of parameters with a non-empty `description` | A model can choose the right arguments |
| Safety | 25 | share of tools declaring `readOnlyHint` or `destructiveHint` | An agent can see which tools change or delete data |
| Schema quality | 5 | share of tools with `type: object` and `required ⊆ properties` | A model can form a valid call |
| *Reachability* | *gate* | `tools/list` must succeed | An unreached server has no score at all |

### Why the weights changed in v1.1.0

The v1.0.0 weights were a guess. Measured over 4,282 servers:

| Component | Standard deviation |
|---|---|
| Reachability | 0.00 |
| Schema quality | 0.00 |
| Conformance | 0.20 |
| Documentation | 0.30 |
| Safety | 0.42 |

Two components never varied. They handed every server 50 free points, and the
median score was 94.4. A score that says "everything is excellent" is not a
score. v1.1.0 weights only the components that separate servers. Reachability
became a gate: a server that cannot be reached is not scored.

Total = `100 × Σ(weight × value) / Σ(weight)` over the components that have inputs.

## How the conformance check classifies responses

We send `tools/call` with a tool name that does not exist. There are five
possible answers, and they are not equal:

| Mode | Score | Meaning |
|---|---|---|
| `error_object` | 15/15 | JSON-RPC error (`-32602`, `-32601`). Spec-compliant. |
| `result_iserror` | 30% | HTTP 200 with `result.isError = true`. Structured clients see it. |
| `result_text_error` | 15% | Error words inside `result.content`, flag unset. Only a prose-reading client sees it. |
| `silent_success` | 0% | No error signal at all. The client sees success. |
| `auth_on_call` | n/a | `401`/`403`. A security boundary, not a defect. |
| `http_400` / `http_404` | n/a | Transport problem. Not scored. |

When the answer is `auth_on_call` or another transport failure, the
conformance component is marked n/a and its weight is removed.

Note: this probe has twice corrected itself.

1. The first version counted `401` and `result.isError` as failures and
   produced a false 37% "silent failure" rate. After the fix, the full
   sweep measured **43 of 21,370 (0.2%)** true silent successes.
2. The second version counted `result_text_error` as silent. A manual
   read of 400 evidence bodies showed the error string was present as
   plain text. That is a real but weaker defect, so it now earns 15%.

The lesson sits in the file on purpose: open 400 evidence records before
you publish any prevalence number.

## The n/a rule

Some components cannot be computed for some servers. Examples:

- A server with zero tools has no schema, documentation, or safety inputs.
- A server with zero parameters has no documentation input.

In these cases the component is marked `null`, its weight is removed, and the
remaining weights are renormalised. The record lists `weights_applied` and
`weights_skipped` so anyone can redo the arithmetic.

## No score without evidence

A server only receives a score when the probe reached `tools/list`. Servers
that are auth-gated (`401`/`403`), dead, or offline are recorded with
`score: null` and a `reason`. They are **unknown, not bad.** Conflating the
two would punish servers that correctly require a key.

## Grades

| Score | Grade |
|---|---|
| 90–100 | A |
| 80–89.9 | B |
| 70–79.9 | C |
| 55–69.9 | D |
| 0–54.9 | F |

## Context tax (reported, not scored)

`tools/list` is re-sent to the model on every turn. Its size is a real
recurring cost. We report `est_tokens` = payload bytes / 4 and never fold it
into the quality score. A large catalog can be legitimate, so a penalty
would be dishonest. The dashboard shows quality and cost as two axes.

## Known limits

- Static schema checks pass easily. A high score does not prove correct
  behaviour at call time; only conformance and documentation do.
- We do not call tools with valid arguments. That would be intrusive, costly,
  and unsafe.
- Latency is measured from one network location. Treat it as a relative
  signal, not an SLA.
- The registry is in preview. Records can change shape between runs.
