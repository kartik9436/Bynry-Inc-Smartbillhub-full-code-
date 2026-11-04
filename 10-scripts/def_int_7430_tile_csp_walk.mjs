/**
 * def_int_7430_tile_csp_walk — DEF-INT-7430 option (a): with the baked page
 * policy now naming the default Esri tile origin, does the BROWSER still refuse
 * the tiles (a CSP violation), or do the requests leave and fail only at the
 * network (this container has no route to Esri)?
 *
 *     BASE=http://127.0.0.1:5491 node 10-scripts/def_int_7430_tile_csp_walk.mjs
 *
 * Walks the Work map (WRK-09) and the Assets map (AST-03) at 1440, as Dana.
 * For each it prints the document's CSP img-src (meta AND header), every
 * console line naming a Content Security Policy, and the outcome of every
 * tile request. PASS = zero CSP refusals and at least one tile request that
 * actually left the browser (answered or failed with a NETWORK error).
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5491";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "08-qa/csp-tiles-2026-10-04";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const c = join(root, dir, sub);
        if (existsSync(c)) return c;
      }
    }
  }
  throw new Error("no chromium found");
}

const problems = [];
const browser = await chromium.launch({ executablePath: resolveChromium() });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
let log = { csp: [], tiles: [] };
page.on("console", (m) => {
  if (/Content Security Policy/i.test(m.text())) log.csp.push(m.text());
});
const isTile = (url) => /\/tile\/\d+\/\d+\/\d+/.test(url);
page.on("request", (r) => {
  if (isTile(r.url())) log.tiles.push({ url: r.url(), outcome: "pending" });
});
page.on("requestfinished", async (r) => {
  const row = log.tiles.find((t) => t.url === r.url() && t.outcome === "pending");
  if (row) row.outcome = `answered ${(await r.response())?.status() ?? "?"}`;
});
page.on("requestfailed", (r) => {
  const row = log.tiles.find((t) => t.url === r.url() && t.outcome === "pending");
  if (row) row.outcome = `failed: ${r.failure()?.errorText ?? "?"}`;
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("#signin-email", { timeout: 60000 });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });

const results = {};
for (const [name, path, shot] of [
  ["Work map (WRK-09)", `/${TENANT}/work/map`, "01-work-map.png"],
  ["Assets map (AST-03)", `/${TENANT}/assets?sort=asset_no&dir=asc&tab=map`, "02-assets-map.png"],
]) {
  log = { csp: [], tiles: [] };
  // A full document load, so the document's own policy (meta + header) applies.
  const response = await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });
  const header = response?.headers()["content-security-policy"] ?? "";
  const meta = await page.evaluate(
    () => document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.getAttribute("content") ?? "",
  );
  await page.waitForSelector("[data-map-canvas]", { timeout: 60000 });
  await page.waitForTimeout(8000);
  const tileHost = await page.evaluate(
    () => document.querySelector("[data-map-canvas]")?.getAttribute("data-tile-host") ?? "",
  );
  await page.screenshot({ path: `${OUT}/${shot}` });
  const imgSrc = (p) => (p.match(/img-src[^;]*/) ?? ["(none)"])[0];
  const outcomes = {};
  for (const t of log.tiles) outcomes[t.outcome] = (outcomes[t.outcome] ?? 0) + 1;
  const tileCsp = log.csp.filter((l) => /arcgisonline|tile/i.test(l));
  console.log(`\n── ${name} ──`);
  console.log(`photo          : ${OUT}/${shot}`);
  console.log(`tile_host      : ${tileHost || "(none)"}`);
  console.log(`meta  img-src  : ${imgSrc(meta)}`);
  console.log(`header img-src : ${header ? imgSrc(header) : "(no header)"}`);
  console.log(`CSP console    : ${log.csp.length} line(s), ${tileCsp.length} about tiles${tileCsp[0] ? ` — ${tileCsp[0].slice(0, 220)}` : ""}`);
  console.log(`tile requests  : ${log.tiles.length}`);
  for (const [k, v] of Object.entries(outcomes)) console.log(`   ${v} × ${k}`);
  if (log.tiles[0]) console.log(`   e.g. ${log.tiles[0].url}`);
  if (tileCsp.length > 0) problems.push(`${name}: ${tileCsp.length} CSP refusal(s) of tiles`);
  if (log.tiles.length === 0) problems.push(`${name}: no tile request left the browser`);
  if (log.tiles.some((t) => /\bcsp\b|ERR_BLOCKED_BY_CSP/i.test(t.outcome)))
    problems.push(`${name}: a tile request failed as blocked-by-CSP`);
  results[name] = { tileHost, meta, header, csp: log.csp, outcomes, tiles: log.tiles.slice(0, 20) };
}
writeFileSync(`${OUT}/tile-csp-network-log.json`, JSON.stringify({ results, problems }, null, 2));
await browser.close();
console.log(problems.length ? `\nFAIL — ${problems.join("; ")}` : "\nPASS — no CSP refusal of a tile on either map; every tile request left the browser");
process.exit(problems.length ? 1 : 0);
