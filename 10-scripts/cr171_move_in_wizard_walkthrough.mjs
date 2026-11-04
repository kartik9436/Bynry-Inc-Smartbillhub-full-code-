#!/usr/bin/env node
// CR-171-BRC10 lane MVI-WIZ — walk the four-step move-in at 1440 and photograph
// the frame (image 30), each step, the Edit title on a resumed draft (image 47)
// and Move-in completed (image 48), for the side-by-side with
// `05-prototype/movein-redesign-2026-10-05/images/`.
//
// Usage:
//   MWW_BASE=http://127.0.0.1:5723 MWW_OUT=08-qa/movein-2026-10-05/after/wizard \
//   node 10-scripts/cr171_move_in_wizard_walkthrough.mjs
//
// It COMMITS one move-in on the tenant it is pointed at (the last step), so run
// it on a lane database, never a shared one. Each shot asserts the page is not
// blank: the h1 must be on it, and the rail (or the completed list) too.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.MWW_BASE || "http://127.0.0.1:5723";
const T = process.env.MWW_TENANT || "brazosbend";
const OUT = process.env.MWW_OUT || "08-qa/movein-2026-10-05/after/wizard";
const EMAIL = process.env.MWW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MWW_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.MWW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const DATE = process.env.MWW_DATE || "2026-10-10";

const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
page.setDefaultTimeout(25000);
await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);

let failed = 0;
async function shot(name, mustSee) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(400);
  const title = (await page.locator("h1").first().innerText()).trim();
  if (title === "" || (await page.locator(mustSee).count()) === 0) {
    failed += 1;
    console.log(`  ✗ ${name} — blank or missing ${mustSee} (h1: "${title}")`);
  }
  await page.screenshot({ path: join(OUT, name), fullPage: true });
  console.log(`  ✓ ${name} — ${title}`);
}
async function onStep(n) {
  await page.waitForSelector(`[data-wizard-step="${n}"][data-state="active"]`, { timeout: 20000 });
}
// ⊕ 2026-10-11 (`DEF-CUS-10050`): step 1's metered rows carry a Fetch reading
// icon and a blank opening read blocks Continue — so the walk takes the FIRST
// vacant unit that has a metered row (or `MWW_UNIT`, a label substring), not
// merely the first unit, which on the demo seed has no meter and walks past
// the whole readings table. A unit with none is said, not passed.
const WANT_UNIT = process.env.MWW_UNIT || "";
async function pickUnit() {
  await page.waitForSelector("#mvi_unit option:nth-child(2)", { state: "attached" });
  const options = await page.$$eval("#mvi_unit option", (ns) =>
    ns.filter((o) => o.value !== "").map((o) => ({ value: o.value, label: o.textContent.trim() })),
  );
  const candidates = WANT_UNIT === "" ? options : options.filter((o) => o.label.includes(WANT_UNIT));
  for (const option of candidates) {
    await page.selectOption("#mvi_unit", option.value);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);
    if ((await page.locator("[data-opening-read]").count()) > 0 || WANT_UNIT !== "") {
      console.log(`  · unit ${option.label}`);
      return true;
    }
  }
  console.log("  ✗ no vacant unit with a metered row — the readings table was not walked");
  failed += 1;
  await page.selectOption("#mvi_unit", options[0].value);
  await page.waitForLoadState("networkidle");
  return false;
}
async function walkReadings() {
  const rows = await page.locator("[data-opening-read]").evaluateAll((ns) => ns.map((n) => n.getAttribute("data-opening-read")));
  for (const meterNo of rows) {
    const fetchBox = page.locator(`[data-fetch-reading="${meterNo}"]`);
    if ((await fetchBox.count()) === 0) {
      failed += 1;
      console.log(`  ✗ metered row ${meterNo} has no Fetch reading`);
      continue;
    }
    await fetchBox.getByRole("button").click();
    const said = fetchBox.locator("[data-fetch-reading-state]");
    await said.waitFor({ timeout: 15000 }).catch(() => undefined);
    const text = ((await said.textContent().catch(() => "")) ?? "").trim();
    console.log(`  · Fetch reading ${meterNo}: ${text || "(nothing said)"}`);
    // With no connector the answer is "Provider is not connected."; a tenant
    // with a meter head-end that gives nothing says one of the other lines
    // (brazosbend's demo seed holds an untested Neptune 360 row, so it reads
    // "Provider could not give a reading."). Anything else is a fault.
    const KNOWN = ["Provider is not connected.", "Provider could not give a reading.", "No reading for this meter."];
    if (!KNOWN.includes(text) && !/^Read on /.test(text)) {
      failed += 1;
      console.log(`  ✗ Fetch reading for ${meterNo} said "${text}"`);
    }
  }
  if (rows.length === 0) return;
  // A blank opening read blocks Continue — the step must not move.
  await cont();
  await page.waitForTimeout(800);
  const stayed = (await page.locator('[data-wizard-step="1"][data-state="active"]').count()) === 1;
  const told = await page.getByText("Enter the opening read.").count();
  if (!stayed || told === 0) {
    failed += 1;
    console.log(`  ✗ a blank opening read did not block Continue (stayed=${stayed}, told=${told})`);
  } else {
    console.log("  ✓ a blank opening read blocks Continue");
  }
  for (const meterNo of rows) {
    await page.fill(`#moveIn-open-read-${meterNo}`, process.env.MWW_READ || "99999");
  }
}
async function cont() {
  // Settle first, as the review walk does: each step reads its own facts on
  // mount, and a press before they land is held (DEF-CUS-9761 — the Billing
  // step's first early press is refused while nothing is marked).
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(800);
  await page.getByRole("button", { name: "Continue" }).click();
}

try {
  // 1 · the empty frame, then a unit chosen (image 30)
  await page.goto(`${BASE}/${T}/move-ins/new`, { waitUntil: "domcontentloaded" });
  await shot("W30-1-unit-empty.png", '[data-wizard="rail"]');
  await pickUnit();
  await page.fill("#opened_at", DATE);
  await page.keyboard.press("Tab");
  await page.waitForLoadState("networkidle");
  await walkReadings();
  await shot("W30-2-unit-chosen.png", '[data-wizard="rail"]');

  // 2 · customer (image 33)
  await cont();
  await onStep(2);
  await page.getByLabel(/Full name/).fill("Nilesh G");
  await page.locator("label", { hasText: /^Person$/ }).first().click();
  await page.getByLabel(/^Phone/).fill("732-630-0285");
  await shot("W33-customer.png", '[data-wizard="rail"]');

  // 3 · billing (image 41)
  await cont();
  await onStep(3);
  // A unit whose plan carries a fee opens Payment on *Pay now* with no
  // method; the walk puts it on the first bill rather than taking a tender.
  const addToBill = page.locator('[data-segmented="move-in-payment"] [data-segment="add_to_bill"]');
  if ((await addToBill.count()) > 0) await addToBill.click();
  await shot("W41-billing.png", '[data-wizard="rail"]');

  // 4 · review (image 45)
  await cont();
  await onStep(4);
  await shot("W45-review.png", '[data-wizard="rail"]');

  // Image 47 — the same draft, resumed: *Edit move-in · MVI-…*
  const resumeUrl = page.url();
  const draft = await context.newPage();
  await draft.goto(resumeUrl.replace(/([?&])step=\d+&?/, "$1"), { waitUntil: "domcontentloaded" });
  await draft.waitForFunction(() => /Edit move-in/.test(document.querySelector("h1")?.textContent ?? ""), null, {
    timeout: 20000,
  });
  await draft.waitForLoadState("networkidle");
  await draft.screenshot({ path: join(OUT, "W47-edit-title.png"), fullPage: true });
  console.log(`  ✓ W47-edit-title.png — ${(await draft.locator("h1").first().innerText()).trim()}`);
  await draft.close();

  // Image 48 — Complete, and the answer
  await page.getByRole("button", { name: /Complete move-in/ }).click();
  await page.waitForSelector('[data-screen="move-in-completed"]', { timeout: 30000 });
  await shot("W48-completed.png", "[data-check-list]");

  // + Start another move-in — a FRESH form
  await page.getByRole("button", { name: /Start another move-in/ }).click();
  await page.waitForSelector('[data-wizard="rail"]');
  await shot("W48b-start-another.png", '[data-wizard="rail"]');
} catch (error) {
  failed += 1;
  console.log(`  ✗ ${String(error).split("\n")[0]}`);
  await page.screenshot({ path: join(OUT, "FAILED.png"), fullPage: true }).catch(() => undefined);
}
await browser.close();
clearTimeout(KILL);
process.exit(failed === 0 ? 0 : 1);
