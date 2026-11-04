// ── Trace ──────────────────────────────────────────────
// Defects: DEF-INT-9848 (PO GIS review gap 2 — Runbook 20 asks the City) ·
//          DEF-INT-9849 (gap 3 — a by-hand Preview reads a few pages and says so)
// Screens: S142 the Esri ArcGIS connection (Nightly parcel check → Preview) ·
//          RBS-004 GIS reconciliation (Run ▶) · RBS-006 the run's result
// ───────────────────────────────────────────────────────
//
// THE PARCEL CHECK, RUN BY HAND THE TWO WAYS THE PO RULED (2026-10-07), AT 1440:
//
//   1 · Settings → Integrations → Esri ArcGIS → Preview — the recorded City
//       (`gis_esri_fixtures`, 7 rows, 3 a page) is three pages, so the default
//       of three reads it WHOLE and draws no "Stopped after" line;
//   2 · the same Preview with `?pages=1` — what a person calling the API by
//       hand gets. ⚠ THE SCREEN HAS NO PAGES BOX: this step rewrites the
//       request's URL in the browser (Playwright `route`) so the SERVER'S real
//       partial answer is drawn by the real screen. It is labelled as such.
//   3 · Runbooks → GIS reconciliation → Review → (if offered) → Run ▶, dry,
//       City pages to read = 1 → the run's result screen;
//   4 · the same Run ▶ with the box left empty → the whole City.
//
// The stack it expects: the API at API (default 127.0.0.1:8391) with
// JOBS_EAGER=true so a Run ▶ job runs inside the request, and the SPA built
// `--mode lane` (same-origin) served by `07-frontend/server.mjs` at BASE.
//
//   OUT=08-qa/gis-lane-b-2026-10-07 node 10-scripts/def_int_9848_9849_parcel_check_walkthrough.mjs
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5391";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/gis-lane-b";
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
const statuses = [];
page.on("response", (r) => {
  if (r.url().includes("/api/")) statuses.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}${new URL(r.url()).search}`);
});
page.on("pageerror", (e) => console.log("  page error:", e.message));
const fail = (why) => {
  throw new Error(`${why}\n  last answers: ${statuses.slice(-6).join(" | ")}`);
};

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── 1 · Preview, the route's default (3 pages = the whole recorded City) ────
await page.goto(`${BASE}/${TENANT}/settings/integrations/gis_esri`, { waitUntil: "networkidle" });
const preview = page.locator("[data-run-preview]").first();
await preview.waitFor({ timeout: 20000 });
await preview.click();
const result = page.locator("[data-reconcile-result]");
await result.waitFor({ timeout: 30000 });
await result.scrollIntoViewIfNeeded();
console.log(`PREVIEW (default): ${(await result.innerText()).replace(/\s+/g, " ")}`);
if (await page.locator("[data-reconcile-partial]").count()) fail("a whole register was labelled partial");
await page.screenshot({ path: join(OUT, "gap3-preview-default-whole-1440.png"), fullPage: false });

// ── 2 · the same Preview as a by-hand API call with ?pages=1 ────────────────
await page.route("**/integrations/gis_esri/reconcile", (route) =>
  route.continue({ url: `${route.request().url()}?pages=1` }),
);
await page.reload({ waitUntil: "networkidle" });
await page.locator("[data-run-preview]").first().click();
const partial = page.locator("[data-reconcile-partial]");
await partial.waitFor({ timeout: 30000 });
await partial.scrollIntoViewIfNeeded();
const said = (await partial.innerText()).trim();
console.log(`PREVIEW (?pages=1): ${said}`);
if (said !== "Stopped after 1 of 3 pages.") fail(`expected "Stopped after 1 of 3 pages.", read "${said}"`);
await page.screenshot({ path: join(OUT, "gap3-preview-pages-1-stopped-1440.png"), fullPage: false });
await page.unroute("**/integrations/gis_esri/reconcile");

// ── 3 · Runbook 20 by hand: Run ▶, dry, City pages to read = 1 ──────────────
async function runByHand(pages, photo) {
  await page.goto(`${BASE}/${TENANT}/runbooks/gis_reconciliation`, { waitUntil: "networkidle" });
  const review = page.locator("[data-template-update] button, [data-template-update] a").first();
  if (await review.isVisible().catch(() => false)) {
    console.log("  template update offered — pressing Review →");
    await review.click();
    await page.waitForLoadState("networkidle");
  }
  await page.getByRole("button", { name: /^Run/ }).first().click();
  const box = page.locator("#run_pages");
  await box.waitFor({ timeout: 15000 });
  if (pages) await box.fill(String(pages));
  await page.screenshot({ path: join(OUT, `gap2-run-dialog-${photo}-1440.png`), fullPage: false });
  const before = statuses.length;
  await page.getByRole("dialog").getByRole("button", { name: /^Run/ }).last().click();
  await page.waitForTimeout(2500);
  const posted = statuses.slice(before).filter((s) => s.includes("/runs"));
  console.log(`  run answers: ${posted.join(" | ")}`);
  if (!posted.some((s) => s.startsWith("202 POST"))) fail("Run ▶ was not accepted");
  await page.goto(`${BASE}/${TENANT}/runbooks/runs`, { waitUntil: "networkidle" });
  // The newest run's own row action (RunHistory.tsx: `runbooks/{key}/runs/{id}`).
  await page.locator("table tbody tr").first().locator('a[href*="/runs/"]').first().click();
  await page.waitForURL(/\/runbooks\/[^/]+\/runs\/[^/]+$/, { timeout: 15000 });
  await page.waitForLoadState("networkidle");
  // The result screen draws a skeleton first; wait for the verdict's words.
  await page
    .getByText(/The city sent|Nothing to compare|Nothing has landed|could not be read|rejected|Stopped/)
    .first()
    .waitFor({ timeout: 30000 })
    .catch(() => {});
  const body = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  const verdict = body.match(/The city sent [^.]*\.( Stopped after [^.]*\.)?/);
  console.log(`RUNBOOK 20 (${photo}): ${verdict ? verdict[0] : "(verdict sentence not found)"}`);
  await page.screenshot({ path: join(OUT, `gap2-run-result-${photo}-1440.png`), fullPage: true });
  if (!verdict) fail("the run's result does not say what the City sent");
  return verdict[0];
}

const one = await runByHand(1, "pages-1");
if (!one.includes("Stopped after 1 of 3 pages.")) fail("the limited run did not say it stopped");
const whole = await runByHand(null, "whole");
if (whole.includes("Stopped after")) fail("the whole-register run says it stopped");
if (statuses.some((s) => s.startsWith("5"))) fail("a 5xx reached the browser");
await browser.close();
