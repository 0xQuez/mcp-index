// Split the aggregate into the files the site loads.
// Runs before `next build`, so the deployed site is fully static.
// The aggregate is the single source of truth: no filtering happens here.

import fs from "node:fs";

const summaryPath = "data/dashboard.json";
if (!fs.existsSync(summaryPath)) {
  console.log("build-data: no data/dashboard.json, nothing to publish");
  process.exit(0);
}

const summary = JSON.parse(fs.readFileSync(summaryPath, "utf8"));
const servers = summary.servers || [];

// Compact keys for the browser. The table reads these exact names.
const compact = (r) => ({
  n: r.server,
  t: r.title || null,
  u: r.url,
  d: (r.description || "").slice(0, 180),
  o: "ok",
  sc: r.score,
  g: r.grade,
  tk: r.est_tokens,
  tl: r.tools || 0,
  pa: r.params || 0,
  pd: r.params_documented || 0,
  cf: r.conformance || null,
  la: r.latency_ms,
});

const rows = servers.map(compact);
const slim = rows.map(({ d, o, ...rest }) => ({ ...rest, o }));
const full = rows;

fs.mkdirSync("public/data", { recursive: true });
fs.writeFileSync(
  "public/data/servers.json",
  JSON.stringify({ date: summary.date, count: slim.length, servers: slim }),
);
fs.writeFileSync(
  "public/data/servers-full.json",
  JSON.stringify({ date: summary.date, count: full.length, servers: full }),
);
const { servers: _omit, ...summaryOnly } = summary;
fs.writeFileSync("public/data/summary.json", JSON.stringify(summaryOnly));

console.log(
  `build-data: ${slim.length} verified servers for ${summary.date}, ` +
    `${summary.totals?.excluded ?? 0} excluded`,
);
