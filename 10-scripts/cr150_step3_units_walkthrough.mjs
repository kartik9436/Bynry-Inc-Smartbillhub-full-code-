#!/usr/bin/env node
// ── cr150_step3_units_walkthrough.mjs ───────────────────────────────────────
//
// CLICK NEW CONNECT STEP 3 AND PHOTOGRAPH IT BESIDE ITS THREE DRAWINGS.
//
// CLAUDE.md hard-won law 6: *"Diff the running app against `05-prototype/`.
// No gate looks at rendered output. Nine defects were found this way and by
// nothing else."* Twenty-three DOM cases and a green `tsc` say the markup is
// what this lane meant; only a photograph beside
// `05-prototype/new-connect-redesign-2026-09-28/step3-units.png`,
// `step3a-add-row.png` and `step3b-add-work-order.png` says whether it is the
// screen the Product Owner drew.
//
// ⚠ **THE BUNDLE MUST BE BUILT `--mode compose`.** A bare `npx vite build`
// resolves as `production`, bakes `https://api-smart360.bynry.com` into the
// bundle, and sign-in then fails with *"That email or password is
// incorrect."* on correct credentials (`DEF-INF-7802`, after biting four
// lanes).
//
// ⚠ **NEVER `npx playwright install`.** The container's chromium is at
// `/opt/pw-browsers/chromium-*/chrome-linux/chrome`; `resolveChromium` finds
// it and PRINTS which one it took when the pinned revision is absent — a
// mismatch stated rather than silently accepted.
//
// WHAT IT CHECKS, beyond taking three pictures:
//   * the eight ruled column headings, in the drawn order, on the real page;
//   * **no `Qty` column** — `OQ-CUS-12770` is OPEN and it multiplies a price
//     on a real invoice, so its ABSENCE is asserted rather than assumed;
//   * `+ Add row` adds a row IN PLACE and opens no dialog, which is what both
//     add-screens say in their own words;
//   * `+ Add work order` reaches a template search in place, likewise;
//   * the four tiles, the common selection and *Apply to all*;
//   * no raw catalogue key and no uuid visible (B14 rule 31);
//   * no horizontal page scroll at 1280 (the staff minimum);
//   * any 5xx anywhere in the run.
//
//   SMOKE_BASE (http://127.0.0.1:8992) · SMOKE_TENANT · SMOKE_EMAIL ·
//   SMOKE_PASSWORD · SMOKE_OUT
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.SMOKE_BASE ?? "http://127.0.0.1:8992").replace(/\/$/, "");
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT =
  process.env.SMOKE_OUT ??
  join(tmpdir(), `cr150-step3-${new Date().toISOString().replace(/[:.]/g, "-")}`);

const failures = [];
const notes = [];
const fiveHundreds = [];

const fail = (m) => {
  failures.push(m);
  console.error(`  ✗ ${m}`);
};
const note = (m) => {
  notes.push(m);
  console.log(`  · ${m}`);
};

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (existsSync(wanted)) return wanted;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  if (!existsSync(root)) return wanted;
  const found = readdirSync(root)
    .filter((name) => name.startsWith("chromium-"))
    .map((name) => join(root, name, "chrome-linux", "chrome"))
    .filter(existsSync);
  if (found.length === 0) return wanted;
  // The mismatch is STATED. A script that silently takes a different browser
  // than the one it pinned is the next version of `DEF-GOV-4299`.
  console.log(`  · pinned chromium absent (${wanted}); taking ${found[0]}`);
  return found[0];
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: resolveChromium(),
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();
  page.on("response", (response) => {
    if (response.status() >= 500) fiveHundreds.push(`${response.status()} ${response.url()}`);
  });

  console.log(`── sign in as ${EMAIL}`);
  // The route is `/signin` and the boxes carry ids — `12-smoke-walkthrough.mjs`
  // is the worked example and a guessed `input[type="email"]` times out.
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  // ⚠ **WAIT FOR THE DESTINATION, NOT FOR THE NETWORK.** `networkidle` fires
  // while the button still reads *Working…*, and the page then "has not left
  // /signin" — a true sentence about a request still in flight, which reads
  // exactly like a real refusal (law 7's *looking at the wrong thing*).
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 }).catch(() => undefined);
  if (/signin/.test(page.url())) {
    // The refusal sentence, verbatim — `DEF-INF-7802` reads *"That email or
    // password is incorrect."* on CORRECT credentials when the bundle was
    // built without `--mode compose`.
    const said = await page.locator("body").innerText();
    fail(`sign-in did not leave /signin. The page says: ${said.slice(0, 200)}`);
    await page.screenshot({ path: join(OUT, "signin-failed.png"), fullPage: true });
    await browser.close();
    return;
  }

  console.log("── walk to New Connect step 3");
  await page.goto(`${BASE}/${TENANT}/connections/new?step=3`, { waitUntil: "networkidle" });

  const body = () => page.locator("body").innerText();

  // ── TYPE A UNIT RANGE FIRST, BECAUSE A BUILD WITH NO UNITS HAS NO TABLE ──
  // The table's empty state is the correct answer to a fresh draft; the
  // columns cannot be checked against nothing. Three units, which is the
  // drawing's own shape — the LABELS on it (1, 2, 15) are illustrations.
  await page.fill("#nc_from", "1");
  await page.fill("#nc_to", "3");
  await page.waitForTimeout(300);

  // ── the eight ruled columns, in the drawn order ──────────────────────────
  const headers = await page
    .locator('[data-array="units-and-service-points"] thead th')
    .allInnerTexts();
  const drawn = ["Unit", "Kind", "Service", "Asset", "Size", "Work order", "Completes", "Occupancy"];
  // ⚠ **CASE-INSENSITIVE, AND THAT IS NOT LAXITY.** The kit sets a table
  // header in small caps (B14), so the page reads `UNIT`; an exact-case
  // comparison fails on eight headings that are present, in order and
  // correct — a check that cannot pass. The ORDER is what this asserts.
  const seen = headers.map((h) => h.trim()).filter((h) => h !== "");
  if (JSON.stringify(seen.map((h) => h.toUpperCase())) !== JSON.stringify(drawn.map((h) => h.toUpperCase()))) {
    fail(`columns are ${JSON.stringify(seen)}; the PO ruled ${JSON.stringify(drawn)}`);
  } else {
    note(`the eight ruled columns, in the drawn order: ${seen.join(" · ")}`);
  }
  // ⛔ `OQ-CUS-12770` is OPEN. Asserted in the same breath as the eight above,
  // so this cannot pass by the table having failed to render at all.
  if (seen.includes("Qty")) {
    fail("a Qty column is on the page and OQ-CUS-12770 is OPEN — it multiplies a price");
  } else if (seen.length === 8) {
    note("no Qty column, which is OQ-CUS-12770 being left unanswered");
  }

  // ── the four tiles and the common selection ──────────────────────────────
  // ⚠ **CASE-INSENSITIVE, AND THAT IS NOT LAXITY.** `KPIStrip` sets its label
  // in small caps, so `innerText` returns `SERVICES HERE`; an exact-case
  // check fails on a tile that is present and correct — a check that cannot
  // pass (law 7's third shape), which is what the first run of this script
  // did on three of the four tiles.
  const shouting = (await body()).toUpperCase();
  for (const tile of ["Services here", "Service points", "Meters to fit", "Work orders"]) {
    if (!shouting.includes(tile.toUpperCase())) fail(`the tile "${tile}" is not on the page`);
  }
  for (const id of ["nc_from", "nc_to", "nc_common_occupancy", "nc_target"]) {
    if ((await page.locator(`#${id}`).count()) === 0) fail(`the common selection has no #${id}`);
  }
  if ((await page.locator("[data-apply-to-all]").count()) === 0) fail("no Apply to all");
  else note("Apply to all is on the page, with its instruction");

  await page.screenshot({ path: join(OUT, "step3-units-1440.png"), fullPage: true });
  note(`photographed step 3 at 1440 → ${join(OUT, "step3-units-1440.png")}`);

  // ── + Add row: IN PLACE, and nothing opens on top of the screen ──────────
  // ⚠ **THE FIRST PRESS CONSUMES THE AUTOMATIC PLACEHOLDER, AND THAT IS THE
  // PRODUCT AND NOT A BUG.** A unit with no service chosen already shows ONE
  // empty row — otherwise the whole unit would vanish with the table's empty
  // state, taking the duplicate-label refusal with it. Pressing `+ Add row`
  // on such a unit turns that placeholder into the typed row rather than
  // leaving two empty rows side by side. So the count rises on the SECOND
  // press, and asserting +1 on the first is asserting the wrong thing.
  const serviceCells = () =>
    page.locator('[data-array="units-and-service-points"] [data-cell="service"]').count();
  const rowsBefore = await serviceCells();
  await page.locator('[data-array-action="add-row"]').click();
  await page.waitForTimeout(250);
  await page.locator('[data-array-action="add-row"]').click();
  await page.waitForTimeout(250);
  const rowsAfter = await serviceCells();
  if (rowsAfter !== rowsBefore + 1) {
    fail(`+ Add row twice took the row count ${rowsBefore} → ${rowsAfter}; one more was expected`);
  } else {
    note(`+ Add row adds a row in place (${rowsBefore} → ${rowsAfter} over two presses)`);
  }
  if ((await page.locator('[role="dialog"]').count()) > 0) {
    fail('+ Add row opened a dialog; both drawings say "Nothing opens on top of the screen"');
  } else {
    note("+ Add row opened no dialog, which is what the drawing says");
  }
  await page.screenshot({ path: join(OUT, "step3a-add-row-1440.png"), fullPage: true });
  note(`photographed the new row at 1440 → ${join(OUT, "step3a-add-row-1440.png")}`);

  // ── + Add work order: the template search, also in place ─────────────────
  await page.locator('[data-array-action="add-work-order"]').click();
  await page.waitForTimeout(250);
  if ((await page.locator("#nc_add_order").count()) === 0) {
    fail("+ Add work order reached no template search");
  } else {
    note("+ Add work order reaches a template search, in place");
  }
  if ((await page.locator('[role="dialog"]').count()) > 0) {
    fail("+ Add work order opened a dialog; the drawing says it is added in place");
  }
  await page.screenshot({ path: join(OUT, "step3b-add-work-order-1440.png"), fullPage: true });
  note(`photographed the work-order row at 1440 → ${join(OUT, "step3b-add-work-order-1440.png")}`);

  // ── B14 rule 31, and a raw catalogue key ─────────────────────────────────
  const text = await body();
  const uuid = text.match(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/);
  if (uuid) fail(`a database id is visible on the page: ${uuid[0]}`);
  const key = text.match(/\bcustomers\.newConnect\.[A-Za-z0-9.]+/);
  if (key) fail(`an unresolved catalogue key is on the page: ${key[0]}`);
  if (!uuid && !key) note("no database id and no raw catalogue key on the page");

  // ── 1280 is the staff minimum and must not scroll sideways ───────────────
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.waitForTimeout(200);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  if (overflow > 0) fail(`the page scrolls sideways by ${overflow}px at 1280`);
  else note("no horizontal page scroll at 1280");
  await page.screenshot({ path: join(OUT, "step3-units-1280.png"), fullPage: true });

  await browser.close();

  console.log("\n── result");
  for (const five of fiveHundreds) fail(`server error during the run: ${five}`);
  console.log(`  ${notes.length} observed · ${failures.length} failed`);
  console.log(`  pictures in ${OUT}`);
  if (failures.length > 0) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
