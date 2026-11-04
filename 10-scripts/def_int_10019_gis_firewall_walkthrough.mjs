// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-INT-10019 — a city's Cloudflare 403 ("error code: 1010") read
//          as "The city rejected our key"
// Screens: S16 Add a property (the amber box) · City GIS connection → Parcel
//          check → Preview · the run's detail (provider error)
// ───────────────────────────────────────────────────────
// THREE THINGS PHOTOGRAPHED AT 1440, against a LOCAL stack only:
//   1 · the address search — amber box "The city's firewall blocked us."
//   2 · Parcel check → Preview — the same sentence, ahead of "stopped"
//   3 · the run's detail — the provider error "403, error code: 1010"
//
// The stack: the API (runserver) and the SPA built `--mode lane` (same-origin)
// served by `07-frontend/server.mjs` with API_PROXY_TARGET at the API. The City
// connection's address is `https://firewall.gis.brazosbend.example/…`, the
// recorded host in `gis_fixtures.py` answering 403 with `error code: 1010`.
// Every /api call is asserted to go to the local origin before signing in.
//
//   BASE=http://127.0.0.1:5519 OUT=<dir> node 10-scripts/def_int_10019_gis_firewall_walkthrough.mjs
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5519";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/gis-cf403";
const PROVIDER = process.env.PROVIDER ?? "gis_esri";
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

const origin = new URL(BASE).origin;
const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const statuses = [];
page.on("request", (r) => {
  if (r.url().includes("/api/") && new URL(r.url()).origin !== origin) {
    throw new Error(`an API call left the local stack: ${r.url()}`);
  }
});
page.on("response", (r) => {
  if (r.url().includes("/api/")) statuses.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
});
page.on("pageerror", (e) => console.log("  page error:", e.message));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
console.log(`signed in; every /api call so far went to ${origin}`);

// 1 · the address search
await page.goto(`${BASE}/${TENANT}/premises/new`, { waitUntil: "networkidle" });
const street = page.getByLabel("Street address");
if (!(await street.isVisible().catch(() => false))) {
  await page.getByRole("button", { name: /next|continue/i }).first().click();
}
await street.fill("2670 Sequ");
const box = page.getByTestId("city-offline");
await box.waitFor({ timeout: 15000 });
await box.scrollIntoViewIfNeeded();
const amber = (await box.innerText()).replace(/\s+/g, " ");
console.log(`1 AMBER: ${amber}`);
await page.screenshot({ path: join(OUT, "1-address-search-firewall-1440.png"), fullPage: false });
if (!amber.includes("The city's firewall blocked us.")) throw new Error("the firewall sentence is not in the amber box");
if (amber.includes("rejected our key")) throw new Error("still says the key");

// 2 · Parcel check → Preview
await page.goto(`${BASE}/${TENANT}/settings/integrations/${PROVIDER}`, { waitUntil: "networkidle" });
const preview = page.getByRole("button", { name: /preview/i }).first();
await preview.scrollIntoViewIfNeeded();
await preview.click();
const stopped = page.locator("[data-warning='reconcile-stopped']");
await stopped.waitFor({ timeout: 30000 });
await stopped.scrollIntoViewIfNeeded();
const said = (await stopped.innerText()).replace(/\s+/g, " ");
console.log(`2 PREVIEW: ${said}`);
await page.screenshot({ path: join(OUT, "2-parcel-check-preview-firewall-1440.png"), fullPage: false });
if (!said.includes("The city's firewall blocked us.")) throw new Error("the parcel check does not name the firewall");

// 3 · the run's detail
await page.reload({ waitUntil: "networkidle" });
// The newest run is the Preview just pressed; its row action opens the detail.
const open = page.getByRole("button", { name: "Open the run" }).first();
await open.scrollIntoViewIfNeeded();
await open.click();
const err = page.locator("[data-provider-said]").first();
await err.waitFor({ timeout: 15000 });
await err.scrollIntoViewIfNeeded();
const providerSaid = (await err.innerText()).trim();
console.log(`3 RUN DETAIL: ${providerSaid}`);
await page.screenshot({ path: join(OUT, "3-run-detail-provider-error-1440.png"), fullPage: false });
if (providerSaid !== "403, error code: 1010") throw new Error("the run does not keep the city's answer");

console.log(`answers: ${statuses.filter((s) => /address-search|reconcile|runs/.test(s)).join(" | ")}`);
if (statuses.some((s) => s.startsWith("5"))) throw new Error("a 5xx reached the screen");
await browser.close();
