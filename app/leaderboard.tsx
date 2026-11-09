"use client";

import { useEffect, useMemo, useState } from "react";

type Row = {
  n: string;
  t: string | null;
  u: string;
  d?: string;
  o: string;
  sc: number | null;
  g: string | null;
  tk: number | null;
  tl: number;
  pa: number;
  pd: number;
  cf: string | null;
  la: number | null;
};

type Payload = { date: string; count: number; servers: Row[] };

type SortKey = "sc" | "tk" | "tl" | "pa" | "la";

const COLS: { key: SortKey | null; label: string; num?: boolean; hideSm?: boolean }[] = [
  { key: null, label: "Server" },
  { key: "sc", label: "Score", num: true },
  { key: "tk", label: "Context tax", num: true },
  { key: "tl", label: "Tools", num: true },
  { key: "pa", label: "Params", num: true, hideSm: true },
  { key: "la", label: "Latency", num: true, hideSm: true },
];

export default function Leaderboard() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("tk");
  const [dir, setDir] = useState<1 | -1>(-1);
  const [limit, setLimit] = useState(100);

  useEffect(() => {
    let alive = true;
    fetch("/data/servers.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: Payload) => alive && setData(d))
      .catch((e) => alive && setError(String(e)));
    return () => {
      alive = false;
    };
  }, []);

  const rows = useMemo(() => {
    if (!data) return [];
    const needle = q.trim().toLowerCase();
    let out = data.servers.filter((r) => {
      if (r.sc === null) return false;
      if (!needle) return true;
      return (
        r.n.toLowerCase().includes(needle) ||
        (r.t || "").toLowerCase().includes(needle) ||
        (r.d || "").toLowerCase().includes(needle)
      );
    });
    out = out.slice().sort((a, b) => {
      const av = (a[sort] ?? (dir === 1 ? Infinity : -Infinity)) as number;
      const bv = (b[sort] ?? (dir === 1 ? Infinity : -Infinity)) as number;
      return (av - bv) * dir;
    });
    return out;
  }, [data, q, sort, dir]);

  const shown = rows.slice(0, limit);

  if (error) {
    return (
      <div className="controls">
        <span className="tag flag">Could not load /data/servers.json ({error}).</span>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="controls">
        <span className="tag">Loading servers.json</span>
      </div>
    );
  }

  const click = (key: SortKey | null) => {
    if (!key) return;
    if (key === sort) setDir(dir === 1 ? -1 : 1);
    else {
      setSort(key);
      setDir(-1);
    }
  };

  return (
    <>
      <div className="controls">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter by name or description"
          aria-label="Filter servers"
        />
        <span className="count">
          {shown.length.toLocaleString("en-US")} of {rows.length.toLocaleString("en-US")}
        </span>
      </div>

      <table>
        <thead>
          <tr>
            {COLS.map((c) => (
              <th
                key={c.label}
                className={c.num ? "n" : undefined}
                onClick={() => click(c.key)}
                aria-sort={c.key === sort ? (dir === 1 ? "ascending" : "descending") : "none"}
              >
                {c.label}
                {c.key === sort ? (dir === 1 ? " ↑" : " ↓") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={r.n}>
              <td>
                <div className="server-name">{r.t || r.n}</div>
                <div className="tag">{r.n}</div>
                {r.d ? <div className="server-desc">{r.d}</div> : null}
              </td>
              <td className="n">
                {r.sc === null ? (
                  <span className="tag">{r.o.replace("_", " ")}</span>
                ) : (
                  <>
                    <span className={`grade ${(r.g || "").toLowerCase()}`}>{r.g}</span>{" "}
                    <span>{r.sc.toFixed(0)}</span>
                  </>
                )}
              </td>
              <td className="n">{r.tk === null ? "-" : r.tk.toLocaleString("en-US")}</td>
              <td className="n">{r.tl.toLocaleString("en-US")}</td>
              <td className="n hide-sm">
                {r.pa.toLocaleString("en-US")}
                {r.pa > 0 ? (
                  <span className="tag">{` ${Math.round((r.pd / r.pa) * 100)}%`}</span>
                ) : null}
              </td>
              <td className="n hide-sm">{r.la === null ? "-" : `${r.la} ms`}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {rows.length > limit ? (
        <div className="controls" style={{ borderTop: "none" }}>
          <button
            onClick={() => setLimit(limit + 200)}
            style={{
              font: "inherit",
              fontSize: 13,
              padding: "8px 14px",
              border: "1px solid var(--rule-strong)",
              background: "var(--surface)",
              color: "var(--ink)",
              cursor: "pointer",
            }}
          >
            Show 200 more
          </button>
        </div>
      ) : null}
    </>
  );
}
