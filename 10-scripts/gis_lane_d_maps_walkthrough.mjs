// ── Trace ──────────────────────────────────────────────
// PO GIS review 2026-10-07, Lane D — gaps 10, 11, 12 on BOTH maps
// Screens: AST-03 (Assets → Map tab) · WRK-09 (Work → Map)
// ───────────────────────────────────────────────────────
//
// Photographs both maps at 1440: the pins, a pin's popup, the click-through to
// the asset / the work order, and the work map with a filter. Run it once on
// the tip (PHASE=before) and once on the change (PHASE=after); the two sets are
// the regression record.
//
//   BASE=http://127.0.0.1:5471 TENANT=brazosbend PHASE=before AREA=North \
//   OUT=08-qa/gis-lane-d-2026-10-07/maps node 10-scripts/gis_lane_d_maps_walkthrough.mjs
//
// A LOCAL stack only: the SPA served by 07-frontend/server.mjs with
// API_PROXY_TARGET pointing at a local API. The script prints every API host
// it saw, so a run against a live host is visible in its own output.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5471";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const PHASE = process.env.PHASE ?? "before";
const OUT = process.env.OUT ?? "/tmp/gis-lane-d-maps";
const AREA = process.env.AREA ?? "";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const candidate = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const calls = [];
page.on("request", (r) => {
  const u = new URL(r.url());
  if (u.pathname.includes("/api/")) calls.push(`${r.method()} ${u.host}${u.pathname}${u.search}`);
});
page.on("pageerror", (e) => console.log("  page error:", e.message));
const shot = async (name) => {
  await page.screenshot({ path: join(OUT, `${PHASE}-${name}-1440.png`), fullPage: false });
  console.log(`  ${PHASE}-${name}-1440.png`);
};

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── Assets → Map ──────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/assets?tab=map`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
const caption = await page.locator('[role="status"]').first().innerText().catch(() => "");
console.log(`ASSET MAP caption: ${caption}`);
console.log(`ASSET MAP markers: ${await page.locator(".leaflet-interactive").count()}`);
const notes = await page.locator("[data-basemap-note], [data-no-tile-host], [data-tile-policy-failed]").allInnerTexts();
console.log(`ASSET MAP basemap note: ${notes.join(" | ") || "(none)"}`);
await shot("asset-map");
const marker = page.locator(".leaflet-interactive").first();
if (await marker.count()) {
  await marker.click({ force: true });
  await page.waitForTimeout(800);
  console.log(
    `ASSET POPUP: ${(await page.locator(".leaflet-popup-content").innerText().catch(() => "")).replace(/\s+/g, " ")}`,
  );
  await shot("asset-map-popup");
  const open = page.locator(".leaflet-popup-content button").first();
  if (await open.count()) {
    await open.click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    console.log(`ASSET CLICK-THROUGH → ${new URL(page.url()).pathname}`);
    await shot("asset-click-through");
  }
}

// ── Work → Map ────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/work/map`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
console.log(
  `WORK MAP pins: ${await page.locator("[data-pin]").count()} clusters: ${await page.locator("[data-cluster]").count()} unplaced: ${await page.locator("[data-unplaced]").count()}`,
);
const workNotes = await page.locator("[data-basemap-note], [data-map-window]").allInnerTexts();
console.log(`WORK MAP notes: ${workNotes.join(" | ") || "(none)"}`);
await shot("work-map");
const cluster = page.locator("[data-cluster]").first();
if (await cluster.count()) {
  await cluster.click();
  await page.waitForTimeout(600);
  console.log(`WORK CLUSTER PANEL: ${(await page.locator("aside, [aria-labelledby]").last().innerText().catch(() => "")).replace(/\s+/g, " ").slice(0, 200)}`);
  await shot("work-map-cluster-open");
  // A job in the panel opens the order — the click-through when every pin is
  // a cluster (the demo's seventeen jobs stand at five places).
  const job = page.getByRole("button", { name: /WO-\d+/ }).first();
  if (await job.count()) {
    await job.click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    console.log(`WORK CLUSTER CLICK-THROUGH → ${new URL(page.url()).pathname}`);
    await shot("work-cluster-click-through");
  }
}
if (await page.locator("[data-pin]").count()) {
  await page.goto(`${BASE}/${TENANT}/work/map`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.locator("[data-pin]").first().click();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1000);
  console.log(`WORK CLICK-THROUGH → ${new URL(page.url()).pathname}`);
  await shot("work-click-through");
}
if (AREA) {
  await page.goto(`${BASE}/${TENANT}/work/map?area=${encodeURIComponent(AREA)}`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2000);
  console.log(
    `WORK MAP area=${AREA} pins: ${await page.locator("[data-pin]").count()} clusters: ${await page.locator("[data-cluster]").count()}`,
  );
  await shot("work-map-filtered");
}
const hosts = [...new Set(calls.map((c) => c.split(" ")[1].split("/")[0]))];
console.log(`API hosts called: ${hosts.join(", ")}`);
console.log(
  `map reads: ${calls.filter((c) => /assets\/geo|work-orders\/map|page-policy/.test(c)).join(" | ")}`,
);
await browser.close();
