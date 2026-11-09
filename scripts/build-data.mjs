// Turn the latest snapshot into the compact JSON the site loads.
// Runs before `next build`, so the deployed site is fully static.

import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";

const dir = "data/snapshots";
const files = fs.existsSync(dir)
  ? fs.readdirSync(dir).filter((f) => /^\d{4}-\d{2}-\d{2}\.jsonl(\.gz)?$/.test(f)).sort()
  : [];
const jsonl = files.filter((f) => f.endsWith(".jsonl"));
const chosen = jsonl.length ? jsonl[jsonl.length - 1] : null;

if (!chosen) {
  console.log("build-data: no snapshot found, keeping existing public/data");
  process.exit(0);
}

const date = chosen.slice(0, 10);
const rows = [];
const rl = readline.createInterface({
  input: fs.createReadStream(path.join(dir, chosen)),
  crlfDelay: Infinity,
});

for await (const line of rl) {
  if (!line.trim()) continue;
  let r;
  try {
    r = JSON.parse(line);
  } catch {
    continue;
  }
  const s = r.score || {};
  const st = r.stats || {};
  rows.push({
    n: r.server,
    t: r.title || null,
    u: r.url,
    d: (r.description || "").slice(0, 180),
    o: r.outcome,
    sc: s.score ?? null,
    g: s.grade ?? null,
    tk: st.est_tokens ?? null,
    tl: st.tools ?? 0,
    pa: st.params ?? 0,
    pd: st.params_documented ?? 0,
    cf: (r.checks || {}).unknown_tool_mode ?? null,
    la: r.latency_init_ms ?? null,
  });
}

fs.mkdirSync("public/data", { recursive: true });
fs.writeFileSync("public/data/servers.json", JSON.stringify({ date, count: rows.length, servers: rows }));

const summaryPath = "data/dashboard.json";
if (fs.existsSync(summaryPath)) {
  const summary = JSON.parse(fs.readFileSync(summaryPath, "utf8"));
  fs.writeFileSync("public/data/summary.json", JSON.stringify({ ...summary, date: summary.date || date }));
  console.log(`build-data: ${rows.length} servers, summary for ${summary.date || date}`);
} else {
  console.log(`build-data: ${rows.length} servers, no summary yet`);
}
