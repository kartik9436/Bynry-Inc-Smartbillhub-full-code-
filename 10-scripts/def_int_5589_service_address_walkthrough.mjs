// ── Trace ──────────────────────────────────────────────
// Defects: DEF-INT-5589 (a Service address declared kind=host could not hold
//          the City of Ann Arbor's real ArcGIS URL) · DEF-INT-5593 (the set-up
//          screen said "Check the highlighted fields" and highlighted none).
// PO:      2026-09-17 — "a) build it now with the Edit fix"
// Screens: S8 / CON-01 · /:tenant/settings/connectors/gis_esri/configure
// Rules:   CLAUDE.md hard-won law 6 — no gate in this repo reads rendered
//          output, so the only proof that a CLERK can type this is typing it.
// ───────────────────────────────────────────────────────
/**
 * Paste the City of Ann Arbor's REAL service address into the Esri connector,
 * save it, reload, and see it come back.
 *
 *     BASE=http://127.0.0.1:5300 node 10-scripts/def_int_5589_service_address_walkthrough.mjs
 *
 * ⚠ **IT ASSERTS WHICH STACK IT IS TALKING TO FIRST**, and prints the bundle
 * hash — a walk against another lane's stack on a shared box is not a weaker
 * proof, it is a proof of a different product (con01's clause, paid for on
 * 2026-09-16).
 *
 * ⚠ **WHAT WOULD MAKE THIS WALK PASS WRONGLY:**
 *
 *  * **A screenshot proves a screen exists, never that it is right.** Every
 *    line scored below is read out of the live DOM; the images are for a
 *    person to look at afterwards.
 *  * **`toContain` on the saved value would pass on a truncated URL** — the
 *    whole point is the PATH, and a check that accepts a prefix accepts
 *    exactly the bug. So the comparison is `=== ANN_ARBOR`, byte-for-byte,
 *    and it is made twice: in the box, and again after a reload.
 *  * **Saving and seeing no error is not proof it was STORED.** The page could
 *    keep the value in React state and never send it. So the walk navigates
 *    AWAY, comes back, and reads the row and the box again.
 *  * **The row actions are icon-only** and keyed by `aria-label`; matching on
 *    button TEXT finds nothing and would report "no door" on a healthy screen.
 *  * **A refusal is only a refusal if a clerk can read it.** The last block
 *    types rubbish and reads the sentence UNDER the field, not the banner at
 *    the foot of the form — the banner was there all along and said nothing
 *    useful (`DEF-INT-5593`).
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");

const BASE = process.env.BASE ?? "http://127.0.0.1:5300";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "/tmp/def-int-5589";
const EXE = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const ANN_ARBOR =
  "https://a2mapseg.a2gov.org/a2arcgis/rest/services/SEU/SEUQualifiedAddress/FeatureServer/0/query";
await fs.mkdir(OUT, { recursive: true });

// ── 0 · WHICH STACK IS THIS, ACTUALLY (con01's clause, and it is paid for) ──
const html = await (await fetch(`${BASE}/${TENANT}/settings/integrations`)).text();
const bundle = (/assets\/(index-[^"]+\.js)/.exec(html) ?? [])[1] ?? "UNKNOWN";
console.log(`STACK: ${BASE} · bundle ${bundle}`);

const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 } });
const page = await ctx.newPage();
page.on("console", (m) => { if (m.type() === "error") console.log("  console.error:", m.text()); });

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL(/\/dashboard/, { timeout: 20000 });
console.log("signed in");

// What the API says the field kind is — read before touching a pixel.
const kinds = await page.evaluate(async (t) => {
  const r = await fetch(`/api/${t}/integrations`, { credentials: "include" });
  const b = await r.json();
  const g = (b.providers ?? []).find((p) => p.key === "gis_esri");
  return { count: (b.providers ?? []).length, fields: (g?.fields ?? []).map((f) => `${f.name}:${f.kind}`) };
}, TENANT);
console.log(`API: ${kinds.count} connectors · gis_esri fields = ${kinds.fields.join(", ")}`);

await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
await page.waitForSelector("table", { timeout: 15000 });

// Find the Esri row and press its Connect (or Edit, if already connected).
const row = page.locator("tr", { hasText: "Esri ArcGIS" }).first();
await row.waitFor({ timeout: 10000 });
const actions = await row.locator("[aria-label]").evaluateAll((bs) =>
  bs.map((b) => `${b.getAttribute("aria-label")}${b.hasAttribute("disabled") ? "(greyed)" : ""}`));
console.log(`the Esri row offers: ${actions.join(" \u00b7 ")}`);
const state = (await row.locator("[data-cell='state']").textContent()).trim();
console.log(`the Esri row's state reads: ${state}`);

// The four row actions are ICON-ONLY and keyed by aria-label; Connect is an
// <a> and the rest are <button>. Take the first enabled door, in the order a
// clerk would: Edit an existing connection, else Connect a new one.
async function openForm() {
  for (const word of ["Edit", "Connect"]) {
    const el = row.locator(`[aria-label="${word}"]`).first();
    if (!(await el.count())) continue;
    if (await el.evaluate((n) => n.hasAttribute("disabled"))) continue;
    await el.click();
    console.log(`pressed ${word}`);
    await page.waitForLoadState("networkidle");
    return word;
  }
  throw new Error("no enabled door on the Esri row");
}
const pressed = await openForm();
console.log(`landed on: ${new URL(page.url()).pathname}`);
await page.waitForSelector("#field-base_url", { timeout: 15000 });

const seeded = await page.inputValue("#field-base_url");
console.log(`the field is pre-filled with: ${seeded || "(empty)"}`);

await page.screenshot({ path: `${OUT}/1-form-open.png` });

// ── THE ONE CASE THAT MATTERS ──────────────────────────────────────────────
await page.fill("#field-base_url", ANN_ARBOR);
const typed = await page.inputValue("#field-base_url");
console.log(`typed, and the box holds: ${typed}`);
console.log(`  the box kept it byte-for-byte: ${typed === ANN_ARBOR}`);
await page.screenshot({ path: `${OUT}/2-typed.png` });

const save = page.locator("button", { hasText: /^Save and test$/ }).first();
await save.click();
console.log("pressed save");
await page.waitForTimeout(3500);
await page.screenshot({ path: `${OUT}/3-after-save.png` });

const refusal = await page.evaluate(() =>
  Array.from(document.querySelectorAll('[aria-invalid="true"], .text-danger-600, [role="alert"]'))
    .map((n) => n.textContent.trim()).filter(Boolean).slice(0, 5));
console.log(`refusals on screen after save: ${refusal.length ? JSON.stringify(refusal) : "none"}`);

// ── RELOAD, AND SEE IT COME BACK ───────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
await page.waitForSelector("table", { timeout: 15000 });
const row2 = page.locator("tr", { hasText: "Esri ArcGIS" }).first();
const shown = (await row2.textContent()).replace(/\s+/g, " ").trim();
console.log(`after reload the Esri ROW reads: ${shown.slice(0, 220)}`);
console.log(`  the row shows the pasted address: ${shown.includes("a2mapseg.a2gov.org")}`);

for (const word of ["Edit", "Connect"]) {
  const el = row2.locator(`[aria-label="${word}"]`).first();
  if ((await el.count()) && !(await el.evaluate((n) => n.hasAttribute("disabled")))) {
    await el.click(); await page.waitForLoadState("networkidle"); break;
  }
}
await page.waitForSelector("#field-base_url", { timeout: 15000 });
const reread = await page.inputValue("#field-base_url");
console.log(`after reload the FIELD holds: ${reread}`);
console.log(`  IT CAME BACK BYTE-FOR-BYTE: ${reread === ANN_ARBOR}`);
await page.screenshot({ path: `${OUT}/4-after-reload.png` });

// ── AND THE REFUSAL A CLERK CAN READ ───────────────────────────────────────
await page.fill("#field-base_url", "rubbish");
const save2 = page.locator("button", { hasText: /^Save and test$/ }).first();
await save2.click();
await page.waitForTimeout(2500);
const said = await page.evaluate(() => ({
  underTheField: Array.from(document.querySelectorAll("[data-field-error]"))
    .map((n) => `${n.getAttribute("data-field-error")}: ${n.textContent.trim()}`),
  highlighted: Array.from(document.querySelectorAll('[aria-invalid="true"]'))
    .map((n) => n.id || n.getAttribute("name")),
  banner: Array.from(document.querySelectorAll("p, div"))
    .map((n) => n.textContent.trim())
    .filter((t) => /highlighted/i.test(t) && t.length < 60)[0] ?? "(none)",
}));
console.log(`typing rubbish — under the field: ${JSON.stringify(said.underTheField)}`);
console.log(`typing rubbish — highlighted    : ${JSON.stringify(said.highlighted)}`);
console.log(`typing rubbish — banner         : ${said.banner}`);
await page.screenshot({ path: `${OUT}/5-rubbish-refused.png` });

await browser.close();
console.log("screenshots in", OUT);
