// ── Trace ──────────────────────────────────────────────
// Defects: DEF-INT-9846 / DEF-INT-5620 (PO GIS review gap 4) · DEF-MET-9847 (gap 6)
// Screens: S16 Add a property (frame 66.2, the amber box) · Edit premise (Parcel)
// ───────────────────────────────────────────────────────
//
// TWO THINGS A CLERK SEES, PHOTOGRAPHED AT 1440 (the staff design width):
//
//   1 · the City REFUSES us (the connection points at a recorded refusing host)
//       → the amber box, with the reason in words, and never our 500;
//   2 · a parcel number another property already holds is typed into Edit
//       premise → one sentence naming that property's address.
//
// The stack it expects: the API on API (default 127.0.0.1:8346) and the SPA
// built `--mode lane` (same-origin) served by `07-frontend/server.mjs` with
// API_PROXY_TARGET at the API. The City connection's address is switched
// between the recorded hosts in `gis_fixtures.py` (key., moved., down.,
// token.gis.brazosbend.example) before each run of part 1; HOST names it.
//
//   HOST=key PART=refusal OUT=08-qa/gis-gap4-6-2026-10-07 node 10-scripts/def_int_9846_def_met_9847_walkthrough.mjs
//   PART=parcel MOVER=<premises uuid> OUT=… node 10-scripts/def_int_9846_def_met_9847_walkthrough.mjs
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5346";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/gis46";
const PART = process.env.PART ?? "refusal";
const HOST = process.env.HOST ?? "key";
const PARCEL = process.env.PARCEL ?? "R-114-0082-004";
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
  if (r.url().includes("/api/")) statuses.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
});
page.on("pageerror", (e) => console.log("  page error:", e.message));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

if (PART === "refusal") {
  await page.goto(`${BASE}/${TENANT}/premises/new`, { waitUntil: "networkidle" });
  const street = page.getByLabel("Street address");
  if (!(await street.isVisible().catch(() => false))) {
    await page.getByRole("button", { name: /next|continue/i }).first().click();
  }
  await street.fill("1408 Pec");
  const box = page.getByTestId("city-offline");
  await box.waitFor({ timeout: 15000 });
  await box.scrollIntoViewIfNeeded();
  console.log(`AMBER (${HOST}): ${(await box.innerText()).replace(/\s+/g, " ")}`);
  await page.screenshot({ path: join(OUT, `gap4-amber-${HOST}-1440.png`), fullPage: false });
  const search = statuses.filter((s) => s.includes("address-search"));
  console.log(`search answers: ${search.slice(-2).join(" | ")}`);
  if (search.some((s) => s.startsWith("5"))) throw new Error("a 5xx reached the screen");
} else {
  const mover = process.env.MOVER;
  await page.goto(`${BASE}/${TENANT}/premises/${mover}`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /^edit/i }).first().click();
  const parcel = page.locator("#external_ref");
  await parcel.waitFor({ timeout: 15000 });
  await parcel.fill(PARCEL);
  await page.getByRole("button", { name: /save/i }).last().click();
  await page.waitForTimeout(1500);
  const text = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  const said = text.match(/This parcel already belongs to [^.]*\./);
  console.log(`PARCEL refusal: ${said ? said[0] : "(sentence not found)"}`);
  console.log(`edit answers: ${statuses.filter((s) => s.includes("premises")).slice(-2).join(" | ")}`);
  await page.screenshot({ path: join(OUT, "gap6-parcel-taken-1440.png"), fullPage: false });
  if (!said) throw new Error("the refusal sentence did not reach the screen");
}
await browser.close();
