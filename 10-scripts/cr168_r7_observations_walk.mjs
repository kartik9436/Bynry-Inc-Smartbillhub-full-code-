// CR-168-BRC10 round 7, lane WALK-A — what the group walks (cr168_*_walk.mjs)
// do not already photograph or prove, re-run at 1440 on PostgreSQL 16:
//
//   beta observations
//   #1  the map asks for a street ground under its pins (tiles requested; drawn
//       only where the tile host is reachable)
//   #3  one clear cross in the Orders LIST search, not two
//   #10 an accepted order is findable on Orders (Status · Complete) and its
//       page offers no Mark complete
//   #12 demo orders carry a priority, so the Priority filter returns rows
//   #28 Duplicate on a rule's page (and whether an order offers one)
//   #29 Select all on the Orders list
//   #32 job type and sub-type are two levels in the Orders filter
//
//   photographs the group walks take clipped or cannot reach any more
//   01  Orders, the whole list (the orders walk shoots a 1200-high viewport)
//   34  one technician's Performance (the crews walks stop at a Renew button
//       CREWS-2 replaced with ✎ Edit, as image 33 draws)
//   38–42  Import parts, every stage whole (the parts walk shoots 1100 high);
//       IMPORT_CSV names a file whose part numbers are NOT on file yet
//
//   BASE=http://127.0.0.1:5217 OUT=<dir> ACCEPTED=WO-0037 \
//   IMPORT_CSV=<csv> node 10-scripts/cr168_r7_observations_walk.mjs
//
// WRITES IT MAKES: the IMPORT_CSV rows that pass validation (3 parts on the
// walk's file). Everything else is a read. Prints PASS/FAIL per check; a FAIL
// is a finding, never hidden.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5217";
const TENANT = "brazosbend";
const OUT = process.env.OUT ?? "/tmp/r7-obs";
const ACCEPTED = process.env.ACCEPTED ?? "WO-0037";
const IMPORT_CSV = process.env.IMPORT_CSV ?? "";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}
const checks = [];
function check(name, ok, detail = "") {
  checks.push([name, ok]);
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const settle = (ms = 1200) => page.waitForTimeout(ms);
async function go(path) {
  try { await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle", timeout: 30000 }); }
  catch { console.log("goto timeout", path); }
  await settle(1500);
}
// The frame scrolls inside <main>, so a "full page" shot is only the viewport:
// grow the viewport to the content, shoot, restore (cr168_templates_after_walk's helper).
async function shot(name) {
  await settle(600);
  const tall = await page.evaluate(() => {
    document.querySelector("main")?.scrollTo(0, 0);
    window.scrollTo(0, 0);
    let h = document.documentElement.scrollHeight;
    for (const el of document.querySelectorAll("*")) {
      if (el.scrollHeight > el.clientHeight + 4 && getComputedStyle(el).overflowY !== "visible") h = Math.max(h, el.scrollHeight + 120);
    }
    return Math.min(h, 6000);
  });
  await page.setViewportSize({ width: 1440, height: Math.max(1000, tall) });
  await settle(500);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  console.log(`=== ${name}.png — ${page.url().replace(BASE, "")}`);
}
async function api(path) {
  return page.evaluate(async ([t, p]) => {
    const r = await fetch(`/api/${t}/${p}`, { credentials: "include" });
    let body = null; try { body = await r.json(); } catch { /* not JSON */ }
    return { status: r.status, body };
  }, [TENANT, path]);
}
const main = () => page.locator("main").innerText();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── #1 · map ground ────────────────────────────────────────────────────────
await go("/work/map");
await settle(4000);
const tiles = await page.evaluate(() => {
  const imgs = [...document.querySelectorAll("img.leaflet-tile")];
  return { requested: imgs.length, drawn: imgs.filter((i) => i.complete && i.naturalWidth > 0).length,
           host: imgs[0] ? new URL(imgs[0].src).host : null };
});
check("#1 the map asks for a street ground", tiles.requested > 0, JSON.stringify(tiles));
console.log(`INFO #1 tiles drawn here: ${tiles.drawn} of ${tiles.requested} (this sandbox's proxy refuses the tile host's certificate)`);

// ── 01 · the whole Orders list ─────────────────────────────────────────────
await go("/work/orders");
await shot("01-orders-work-orders-whole");

// ── #3 · one clear cross in the LIST search ───────────────────────────────
const listSearch = page.locator('main input[type="search"]').first();
await listSearch.fill("WO");
await settle(1000);
const crosses = await page.evaluate(() => {
  const input = document.querySelector('main input[type="search"]');
  const native = getComputedStyle(input, "::-webkit-search-cancel-button");
  const nativeShown = (native.webkitAppearance || native.appearance) !== "none" && native.display !== "none";
  const box = input.getBoundingClientRect();
  const kit = [...document.querySelectorAll("main button")].filter((b) => {
    const r = b.getBoundingClientRect();
    return r.top >= box.top - 2 && r.bottom <= box.bottom + 2 && r.left >= box.left && r.right <= box.right + 4;
  }).length;
  return { nativeShown, kit };
});
check("#3 one clear cross in the Orders list search", !(crosses.nativeShown && crosses.kit > 0), JSON.stringify(crosses));
const sb = await listSearch.boundingBox();
if (sb) await page.screenshot({ path: `${OUT}/o03-list-search-crosses.png`, clip: { x: sb.x - 8, y: sb.y - 8, width: sb.width + 16, height: sb.height + 16 } });
console.log("=== o03-list-search-crosses.png");
await listSearch.fill("");
await settle(800);

// ── #29 · Select all ──────────────────────────────────────────────────────
const headBox = await page.locator('main thead input[type="checkbox"]').count();
const selectAllWord = await page.getByRole("button", { name: /select all/i }).count();
check("#29 Orders list offers Select all", headBox + selectAllWord > 0, `head checkbox ${headBox}, button ${selectAllWord}`);

// ── #12 · priority ────────────────────────────────────────────────────────
const open = await api("work-orders?per=200");
const rows = open.body?.results ?? [];
const withPriority = rows.filter((r) => r.priority).length;
check("#12 demo orders carry a priority", withPriority > 0, `${withPriority} of ${rows.length} open orders`);

// ── #32 · job type, two levels ────────────────────────────────────────────
await page.locator("main summary", { hasText: "Filter" }).first().click();
await settle(800);
const typeBlock = await page.evaluate(() => {
  const d = document.querySelector("main details[open]");
  return d ? d.innerText : "";
});
await shot("o32-orders-type-filter");
const nested = await page.evaluate(() => {
  const d = document.querySelector("main details[open]");
  if (!d) return null;
  const label = [...d.querySelectorAll("label")].find((l) => l.textContent.trim() === "Outage report");
  const parent = [...d.querySelectorAll("label")].find((l) => l.textContent.trim() === "Electrical Line");
  if (!label || !parent) return null;
  return { child: label.getBoundingClientRect().left, parent: parent.getBoundingClientRect().left };
});
check("#32 a sub-type sits under its type, not beside it", !!nested && nested.child > nested.parent + 4,
  nested ? `Electrical Line at x=${nested.parent}, Outage report at x=${nested.child}` : "labels not found");
console.log("FILTER (first 400):", JSON.stringify(typeBlock.slice(0, 400)));
await page.keyboard.press("Escape");

// ── #10 · the accepted order is findable ──────────────────────────────────
const found = await api(`work-orders?q=${ACCEPTED}&status=complete`);
const hit = (found.body?.results ?? []).find((r) => r.order_no === ACCEPTED);
check("#10 accepted order returned under Status · Complete", !!hit, hit ? `${hit.order_no}` : `status ${found.status}`);
await go("/work/orders");
await page.locator("main summary", { hasText: "Filter" }).first().click();
await settle(600);
await page.locator("main details[open] label", { hasText: /^Complete$/ }).first().click();
await settle(1200);
await page.keyboard.press("Escape");
await page.locator('main input[type="search"]').first().fill(ACCEPTED);
await settle(1500);
// The search box holds the number too, so the check reads the TABLE's rows,
// never the page text (a "No results for 'WO-0037'" line would pass a text test).
const tableHit = await page.locator("main tbody tr", { hasText: ACCEPTED }).count();
check("#10 accepted order is a row on Orders under Status · Complete", tableHit > 0, `${tableHit} row(s)`);
await shot("o10-accepted-order-on-orders");
await go(`/work/orders/${ACCEPTED}`);
const head10 = await page.locator(".page-header-actions").first().innerText().catch(() => "");
check("#10 accepted order's page offers no Mark complete and no Accept", !/Mark complete|Accept/.test(head10), JSON.stringify(head10));
await shot("o10-accepted-order-page");

// ── #28 · Duplicate ───────────────────────────────────────────────────────
const rules = await api("work/rules?page=1&per=50");
const firstRule = (rules.body?.results ?? [])[0];
if (firstRule) {
  await go(`/work/rules/${firstRule.id}`);
  const head = await page.locator(".page-header-actions").first().innerText().catch(() => "");
  check("#28 a rule's page offers Duplicate", /Duplicate/.test(head), JSON.stringify(head));
}
const anyOpen = rows[0];
if (anyOpen) {
  await go(`/work/orders/${anyOpen.order_no}`);
  const head = await page.locator(".page-header-actions").first().innerText().catch(() => "");
  console.log(`INFO #28 an order's head: ${JSON.stringify(head)} — Duplicate on an order: ${/Duplicate/.test(head)}`);
}

// ── 34 · one technician's Performance ─────────────────────────────────────
await go("/work/crews/d-ortiz?tab=performance");
await shot("34-crews-one-technician-performance");

// ── 38–42 · Import parts, each stage whole ────────────────────────────────
if (IMPORT_CSV) {
  await go("/work/parts/import");
  await page.locator('input[type="file"]').setInputFiles(IMPORT_CSV);
  await settle(2000);
  await shot("38-parts-import-parts-extract");
  await page.getByRole("button", { name: /^Transform/ }).last().click();
  await settle(2500);
  await shot("39-parts-import-parts-transform");
  await page.getByRole("button", { name: /^Validate/ }).last().click();
  await settle(3000);
  await shot("40-parts-import-parts-validate");
  await page.getByRole("button", { name: /^Load/ }).last().click();
  await settle(3000);
  await shot("41-parts-import-parts-load");
  await page.getByText("I approve this load.").click().catch(() => {});
  await settle(800);
  await page.getByRole("button", { name: /^Commit load/ }).click();
  await settle(5000);
  await shot("42-parts-import-parts-result");
  const t5 = await main();
  check("42 · three loaded, two rejected", /LOADED\s*3/i.test(t5) && /REJECTED\s*2/i.test(t5));
}

const failed = checks.filter(([, ok]) => !ok).length;
console.log(`\n${checks.length - failed}/${checks.length} checks passed`);
await browser.close();
