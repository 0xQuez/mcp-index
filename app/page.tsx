import fs from "node:fs";
import path from "node:path";
import Leaderboard from "./leaderboard";

type Summary = {
  date: string;
  totals: Record<string, number> & {
    registry_entries: number;
    verified: number;
    excluded: number;
    excluded_breakdown: Record<string, number>;
  };
  outcomes: Record<string, number>;
  context_tax: {
    median: number;
    p90: number;
    p99: number;
    max: number;
    prices: { model: string; input_per_m: number; as_of: string }[];
    histogram: { bucket: string; count: number }[];
  };
  grades: Record<string, number>;
  score_median: number;
  conformance_modes: Record<string, number>;
};

function loadSummary(): Summary | null {
  const file = path.join(process.cwd(), "data", "dashboard.json");
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, "utf8")) as Summary;
}

const fmt = (n: number | undefined) => (n === undefined || n === null ? "-" : n.toLocaleString("en-US"));

function money(tokens: number, perM: number) {
  const usd = (tokens / 1_000_000) * perM;
  return usd < 0.01 ? usd.toFixed(4) : usd.toFixed(2);
}

export default function Page() {
  const s = loadSummary();
  if (!s) {
    return (
      <main className="wrap">
        <div className="masthead">
          <span className="wordmark">MCP Conformance Index</span>
        </div>
        <div className="lede">
          <h1>No snapshot yet</h1>
          <p>
            Run <code>python3 collector/run.py</code>, then <code>python3 collector/aggregate.py --date
            YYYY-MM-DD</code>.
          </p>
        </div>
      </main>
    );
  }

  const total = s.totals.registry_entries;
  const verified = s.totals.verified;
  const excluded = s.totals.excluded;
  const excl = s.totals.excluded_breakdown || {};
  const auth = (excl.auth_required ?? 0) + (excl.auth_on_call ?? 0);
  const dead = excl.dead_or_unreachable ?? 0;
  const other = (excl.protocol_error ?? 0) + (excl.call_not_testable ?? 0);
  const pct = (n: number) => `${((n / total) * 100).toFixed(1)}%`;

  const maxHist = Math.max(...s.context_tax.histogram.map((h) => h.count));
  const silent = s.conformance_modes["silent_success"] ?? 0;
  const textErr = s.conformance_modes["result_text_error"] ?? 0;
  const errObj = s.conformance_modes["error_object"] ?? 0;
  const isErr = s.conformance_modes["result_iserror"] ?? 0;

  return (
    <main className="wrap">
      <div className="masthead">
        <span className="wordmark">MCP Conformance Index</span>
        <nav>
          <a href="#context-tax">Context tax</a>
          <a href="#servers">Servers</a>
          <a href="/data/servers.json">JSON</a>
          <a href="https://github.com/0xQuez/mcp-index">Source</a>
        </nav>
      </div>

      <div className="lede">
        <h1>What every MCP server costs your agent</h1>
        <p>
          A daily probe of the public MCP registry. It measures tool documentation and the token
          cost of each server&#39;s tool catalog. Only servers verified end to end are listed.
        </p>
        <div className="stamp">
          <span>Snapshot {s.date}</span>
          <span>{fmt(verified)} verified servers</span>
          <span>{fmt(excluded)} entries excluded</span>
          <span>Rule v1.2.0</span>
        </div>
      </div>

      <div className="coverage">
        <div className="coverage-head">
          <h2>What is in this index</h2>
          <span>{pct(verified)} of {fmt(total)} registry entries verified</span>
        </div>
        <div className="bar" role="img" aria-label="Verified share of the registry">
          <i style={{ width: pct(verified), background: "var(--ink)" }} />
          <i style={{ width: pct(auth), background: "var(--rule-strong)" }} />
          <i style={{ width: pct(dead), background: "var(--warn)" }} />
          <i style={{ width: pct(other), background: "var(--bad)" }} />
        </div>
        <div className="legend">
          <span className="denom">Share of all {fmt(total)} registry entries</span>
          <span>
            <i style={{ background: "var(--ink)" }} />
            Verified {fmt(verified)}
          </span>
          <span>
            <i style={{ background: "var(--rule-strong)" }} />
            Auth gated, excluded {fmt(auth)}
          </span>
          <span>
            <i style={{ background: "var(--warn)" }} />
            Dead or unreachable {fmt(dead)}
          </span>
          <span>
            <i style={{ background: "var(--bad)" }} />
            Other {fmt(other)}
          </span>
        </div>
        <p className="coverage-note">
          Version 1 lists only servers we could verify: reachable, tool list readable, and the
          invalid-call test executed. Auth-gated servers need a key, so we cannot verify them. They
          are counted here and left out of every number below. Other covers
          protocol errors and servers whose call test could not run.
        </p>
      </div>

      <dl className="stats">
        <div className="stat">
          <dt>Median context tax</dt>
          <dd>{fmt(s.context_tax.median)}</dd>
          <small>tokens per turn for the tool catalog</small>
        </div>
        <div className="stat">
          <dt>90th percentile</dt>
          <dd>{fmt(s.context_tax.p90)}</dd>
          <small>tokens per turn</small>
        </div>
        <div className="stat">
          <dt>Parameters documented</dt>
          <dd>{(s.totals.doc_rate * 100).toFixed(0)}%</dd>
          <small>
            {fmt(s.totals.params_documented)} of {fmt(s.totals.params)} across {fmt(s.totals.tools)} tools
          </small>
        </div>
        <div className="stat">
          <dt>Median score</dt>
          <dd>{s.score_median?.toFixed(1)}</dd>
          <small className="grades">
            {(["A", "B", "C", "D", "F"] as const).map((g) => (
              <span key={g}>
                <b>{g}</b> {fmt(s.grades[g])}
              </span>
            ))}
          </small>
        </div>
      </dl>

      <section id="context-tax">
        <h2>Context tax distribution</h2>
        <p className="note">
          An agent resends <code>tools/list</code> to the model on every turn. The payload size is a
          recurring cost. Most servers sit under 3,000 tokens. A tail of large catalogs costs orders
          of magnitude more.
        </p>
        <div className="hist">
          {s.context_tax.histogram.map((h) => (
            <div className="hist-col" key={h.bucket}>
              <b>{fmt(h.count)}</b>
              <div
                className="hist-bar"
                style={{ height: `${Math.max(4, (h.count / maxHist) * 180)}px` }}
                title={`${h.bucket} tokens: ${h.count} servers`}
              />
              <span>{h.bucket}</span>
            </div>
          ))}
        </div>
        <p className="note" style={{ marginTop: 20 }}>
          Worst observed: {fmt(s.context_tax.max)} tokens. At the median, a turn costs{" "}
          {s.context_tax.prices
            .map((p) => `$${money(s.context_tax.median, p.input_per_m)} (${p.model})`)
            .join(", ")}
          . Reference prices as of {s.context_tax.prices[0]?.as_of}.
        </p>
      </section>

      <section>
        <h2>Error handling</h2>
        <p className="note">
          We send one tool call with a name that does not exist, then classify the answer. A server
          that reports nothing teaches the agent that the call succeeded.
        </p>
        <dl className="stats" style={{ marginBottom: 0 }}>
          <div className="stat">
            <dt>JSON-RPC error</dt>
            <dd>{fmt(errObj)}</dd>
            <small>best case, spec compliant</small>
          </div>
          <div className="stat">
            <dt>result.isError</dt>
            <dd>{fmt(isErr)}</dd>
            <small>detectable by the agent</small>
          </div>
          <div className="stat">
            <dt>Text-only error</dt>
            <dd>{fmt(textErr)}</dd>
            <small>error string in content, no isError flag</small>
          </div>
          <div className="stat">
            <dt>False success</dt>
            <dd>{fmt(silent)}</dd>
            <small>no error signal at all</small>
          </div>
        </dl>
      </section>

      <section id="servers">
        <h2>Servers</h2>
        <p className="note">
          Every interrogated server, with its score, tool count, and context tax. Sort by context tax
          to find the expensive catalogs.
        </p>
        <Leaderboard />
      </section>

      <footer>
        <span>
          Code MIT, data CC BY 4.0. Scores recomputed under rule v1.2.0. Method in{" "}
          <a href="https://github.com/0xQuez/mcp-index/blob/main/docs/SCORING.md">docs/SCORING.md</a>.
        </span>
        <span>
          <a href="/data/servers.json">servers.json</a>{" "}
          <a href="/data/summary.json">summary.json</a>
        </span>
      </footer>
    </main>
  );
}
