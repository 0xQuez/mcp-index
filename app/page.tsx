import fs from "node:fs";
import path from "node:path";
import Leaderboard from "./leaderboard";

type Summary = {
  date: string;
  totals: Record<string, number>;
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

  const total = s.totals.servers;
  const reachable = s.totals.reachable;
  const auth = s.outcomes.auth_required ?? 0;
  const dead =
    (s.outcomes.dns_error ?? 0) +
    (s.outcomes.not_found ?? 0) +
    (s.outcomes.transport_error ?? 0) +
    (s.outcomes.tls_error ?? 0) +
    (s.outcomes.timeout ?? 0) +
    (s.outcomes.invalid_body ?? 0);
  const proto = s.outcomes.protocol_error ?? 0;
  const other = Math.max(0, total - reachable - auth - dead - proto);
  const pct = (n: number) => `${((n / total) * 100).toFixed(1)}%`;

  const maxHist = Math.max(...s.context_tax.histogram.map((h) => h.count));
  const silent = s.conformance_modes["silent_success"] ?? 0;
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
          A daily probe of the public MCP registry. It records reachability, tool documentation, and
          the token cost of each server&#39;s tool catalog. All raw data is published.
        </p>
        <div className="stamp">
          <span>Snapshot {s.date}</span>
          <span>{fmt(total)} registry entries</span>
          <span>{fmt(reachable)} interrogated</span>
          <span>Rule v1.1.0</span>
        </div>
      </div>

      <div className="coverage">
        <div className="coverage-head">
          <h2>Registry coverage</h2>
          <span>{pct(reachable)} inspectable without credentials</span>
        </div>
        <div className="bar" role="img" aria-label="Registry composition">
          <i style={{ width: pct(reachable), background: "var(--ink)" }} />
          <i style={{ width: pct(auth), background: "var(--rule-strong)" }} />
          <i style={{ width: pct(dead), background: "var(--warn)" }} />
          <i style={{ width: pct(proto), background: "var(--bad)" }} />
          <i style={{ width: pct(other), background: "var(--rule)" }} />
        </div>
        <div className="legend">
          <span>
            <i style={{ background: "var(--ink)" }} />
            Interrogated {fmt(reachable)}
          </span>
          <span>
            <i style={{ background: "var(--rule-strong)" }} />
            Auth required {fmt(auth)}
          </span>
          <span>
            <i style={{ background: "var(--warn)" }} />
            Dead or unreachable {fmt(dead)}
          </span>
          <span>
            <i style={{ background: "var(--bad)" }} />
            Protocol error {fmt(proto)}
          </span>
        </div>
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
            <dt>False success</dt>
            <dd>{fmt(silent)}</dd>
            <small>the agent sees a success</small>
          </div>
          <div className="stat">
            <dt>Coverage gap</dt>
            <dd>{fmt(auth)}</dd>
            <small>call blocked by auth, not scored</small>
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
          Code MIT, data CC BY 4.0. Scores recomputed under rule v1.1.0. Method in{" "}
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
