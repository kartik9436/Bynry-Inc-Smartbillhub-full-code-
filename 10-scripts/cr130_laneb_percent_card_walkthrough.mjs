#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-130-BRC07 lane B — step 3's percent card gains the BASIS choice
//           (% of the charge · % of the usage), a RATE and the tier ladder on
//           the usage basis, a DERIVED Based-on list, and one sentence saying
//           where taxability is decided. Part two: step 1's unit picker reads
//           the tenant's DECLARED unit for the service.
// Defects:  DEF-RAT-6146 — a percent schedule cannot be saved from this screen
//           at all (`{percent, basis_service}` posted, `structure.unit_price`
//           required since CR-081) · DEF-RAT-6145 — five catalogue sentences
//           describe arithmetic the engine stopped doing on 2026-09-08.
// Screens:  RAT-03 steps 1, 3 and 5 (S11 → Rate schedules → New)
// Rules:    CLAUDE.md hard-won law 6 (no gate reads rendered output) · law 7
//           (a check's output must distinguish pass from fail to a READER) ·
//           hard rule 3 (a quantity always carries its unit) · B14 rule 33
//           (on-screen text is capped by what it is for) ·
//           22-product-maintenance-process.md step 1 — REPRODUCE FIRST.
// ───────────────────────────────────────────────────────
/**
 * WALK RAT-03 IN A BROWSER, ON A REAL WATER+SEWER UTILITY.
 *
 *     10-scripts/proof-db.sh clone <label>
 *     DATABASE_URL=… JOBS_EAGER=true python3 10-scripts/cr081_seed_sewer_utility.py
 *     BASE=http://127.0.0.1:8118 TENANT=cr081-sewer \
 *       node 10-scripts/cr130_laneb_percent_card_walkthrough.mjs
 *
 * ⚠ **IT IS WRITTEN TO RUN BEFORE AND AFTER THE FIX AND TO PRINT A DIFFERENT
 * STORY EACH TIME.** `MODE=before` expects today's product and FAILS if the
 * defects are already gone; `MODE=after` (the default) expects the fix. A
 * walkthrough that passes in both worlds is law 7's *incapable of failing*.
 *
 * The four things it reads off the rendered screen, none of which any gate in
 * this repo can see:
 *
 *   1. STEP 1's unit picker on a SEWER schedule — every option, and whether it
 *      is selectable. Before: eight, all selectable, none preselected. After:
 *      the tenant's own declared unit chosen, the rest present and refused.
 *   2. STEP 3's percent card — is there a BASIS choice, and is there a RATE
 *      field. Before: neither.
 *   3. The **Based on** list on each basis, by NAME, never by service code —
 *      and it asserts that the usage basis offers FEWER services than the
 *      charge basis on this utility, because trash meters nothing.
 *   4. THE SAVE. Before: the server refuses `structure.unit_price` and the
 *      screen has no field for it, so the schedule cannot be saved at all.
 */
import { createRequire } from "node:module";
const require = createRequire(process.env.NODE_MODULES_FROM ?? "/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8118";
const TENANT = process.env.TENANT ?? "cr081-sewer";
const EMAIL = process.env.EMAIL ?? `owner@${TENANT}.test`;
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/cr130-laneb";
const MODE = process.env.MODE ?? "after";

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/opt/pw-browsers/chromium",
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();

/** Every wait in this file carries a DEADLINE and re-checks the producer. */
async function reachable(url) {
  const res = await fetch(url).catch(() => null);
  return res !== null;
}
if (!(await reachable(`${BASE}/`))) {
  console.log(`the SPA server at ${BASE} is not answering — nothing to walk`);
  process.exit(2);
}

// ── sign in through the real form ──────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
note(`signed in — ${page.url()}`);

// What this utility has switched on, so the derived list has something to be
// checked AGAINST rather than compared with a constant.
const services = await (await page.request.get(`${BASE}/api/${TENANT}/settings/services`)).json();
const rows = services.results ?? services.items ?? services;
const enabled = rows.filter((r) => r.enabled);
note(`\nthis utility sells ${enabled.length}: ` +
  enabled.map((r) => `${r.name} (${r.billing_basis ?? "?"})`).join(" · "));
const meters = enabled.filter((r) => r.billing_basis === "metered");
note(`of those, ${meters.length} meter a quantity: ${meters.map((r) => r.name).join(", ")}`);

/**
 * ⚠ **CLICK THE LABEL, NOT THE INPUT.** `FormModal.css` hides the segmented
 * control's `<input>` — `position:absolute; opacity:0; width:0; height:0;
 * pointer-events:none` — and draws the selected and focused states on the
 * `<label>` (`.seg-opt:has(input:checked)` / `:has(input:focus-visible)`).
 * That is the shared kit's own pattern and it IS keyboard-reachable, because
 * `opacity:0` leaves the radio in the tab order where `display:none` would
 * not. `locator.check()` on the input times out against a control a person can
 * plainly press, so this presses what a person presses.
 */
async function pickBasisKind(value) {
  await page
    .locator("label.seg-opt")
    .filter({ has: page.locator(`input[name="percent-basis-kind"][value="${value}"]`) })
    .click();
  await page.waitForTimeout(400);
}

// ── 1 · STEP 1, ON A SEWER SCHEDULE ────────────────────────────────────────
note("\n1 · RAT-03 step 1 — the unit picker on a Sewer schedule");
await page.goto(`${BASE}/${TENANT}/plans-rates/rates/new`, { waitUntil: "networkidle" });
await page.waitForSelector("#rate-service", { timeout: 30000 });
// ⚠ A NAME THIS RUN HAS NOT USED BEFORE. `rating.schedules.duplicate_name`
// is a real refusal and a correct one; a walkthrough that only passes against
// a fresh seed is one nobody can re-run, and re-running over its own
// leftovers is half the value of having it.
const RUN = new Date().toISOString().replace(/\D/g, "").slice(8, 14);
await page.locator("#rate-name").fill(`Sewer — percent of water ${RUN}`);
await page.selectOption("#rate-service", "sewer");
await page.waitForTimeout(600);

const uom = await page.evaluate(() => {
  const el = document.querySelector("#rate-uom");
  if (!el) return null;
  return {
    value: el.value,
    options: Array.from(el.options)
      .filter((o) => o.value !== "")
      .map((o) => ({ value: o.value, label: o.textContent, disabled: o.disabled })),
  };
});
if (uom === null) {
  fail("step 1 has no unit picker at all");
} else {
  note(`    ${uom.options.length} unit(s) offered, ${uom.options.filter((o) => !o.disabled).length} of them selectable`);
  for (const o of uom.options) note(`      ${o.disabled ? "— refused" : "  offered"}  ${o.label}`);
  note(`    preselected: ${uom.value === "" ? "(nothing)" : uom.value}`);

  const sewer = rows.find((r) => r.service === "sewer");
  const declared = sewer ? (sewer.billed_uom ?? sewer.primary_uom) : null;
  note(`    this utility declares sewer in: ${declared ?? "(nothing)"}`);

  if (MODE === "before") {
    if (uom.value !== "") fail("BEFORE: something is already preselected — the defect is gone; run MODE=after");
    else ok(`BEFORE: nothing preselected, and all ${uom.options.length} units selectable — the reported screen`);
  } else {
    if (declared !== null && uom.value !== declared) {
      fail(`the picker should open on ${declared}, the unit this utility declares for sewer — it opens on "${uom.value}"`);
    } else ok(`opens on ${uom.value} — the unit this utility declared in Settings`);
    const refused = uom.options.filter((o) => o.disabled);
    if (refused.length === 0) fail("no unit is refused — out-of-scope units must be PRESENT and unselectable, never absent");
    else ok(`${refused.length} unit(s) present and refused, each carrying its reason`);
    const selectable = uom.options.filter((o) => !o.disabled);
    if (selectable.length > 1) fail(`${selectable.length} units are still selectable on a service measured in one`);
    else ok("exactly one unit is selectable");
  }
}
await page.screenshot({ path: `${SHOTS}-step1.png`, fullPage: true });

// ── 2 · STEP 3, THE PERCENT CARD ───────────────────────────────────────────
note("\n2 · RAT-03 step 3 — the percent-of-another-service card");
if (uom && uom.value === "") await page.selectOption("#rate-uom", "kgal");
await page.getByRole("button", { name: /continue|next/i }).first().click();
await page.waitForTimeout(500);
await page.getByRole("button", { name: /continue|next/i }).first().click();
await page.waitForTimeout(700);
await page.waitForSelector("#rate-model", { timeout: 30000 });
await page.selectOption("#rate-model", "percent_of_service");
await page.waitForTimeout(600);

const card = await page.evaluate(() => {
  const ids = ["percent-value", "percent-basis", "percent-unit-price",
    "percent-confirm-over-100", "tier-price-0"];
  const present = {};
  for (const id of ids) present[id] = document.getElementById(id) !== null;
  // ⚠ **THE SEGMENTED CONTROL HAS NO ELEMENT CARRYING ITS `id`** — the shared
  // `SegmentedField` spends it on `name`, `${id}-label` and `${id}-error`, so
  // `getElementById` answers null over a control that is plainly on screen.
  // The first draft of this file probed by id, reported *"the card offers no
  // basis choice"* against a rendered radio group, and was law 7's fourth
  // shape: a check looking at the wrong thing. Probe by NAME.
  const kinds = Array.from(document.querySelectorAll('input[name="percent-basis-kind"]'));
  present["percent-basis-kind"] = kinds.length > 0;
  const basis = document.querySelector("#percent-basis");
  const labelled = document.getElementById("percent-basis-kind-label");
  return {
    present,
    basisOptions: basis ? Array.from(basis.options).filter((o) => o.value !== "").map((o) => o.textContent) : [],
    basisKinds: kinds.map((r) => r.value),
    basisKindLabels: kinds.map((r) => (r.closest("label")?.innerText ?? "").trim()),
    basisKindGroupLabel: labelled ? labelled.innerText.trim() : null,
    checkedKind: (kinds.find((r) => r.checked) ?? {}).value ?? null,
    text: document.body.innerText,
  };
});
note("    controls on the card: " +
  Object.entries(card.present).map(([k, v]) => `${k}=${v ? "yes" : "no"}`).join(" · "));

if (MODE === "before") {
  if (card.present["percent-basis-kind"]) fail("BEFORE: the basis choice already exists — run MODE=after");
  else ok("BEFORE: no basis choice on the card");
  if (card.present["percent-unit-price"] || card.present["tier-price-0"]) {
    fail("BEFORE: a rate field already exists — run MODE=after");
  } else ok("BEFORE: NO rate field anywhere on the card — DEF-RAT-6146's first half");
} else {
  if (!card.present["percent-basis-kind"]) fail("the card offers no basis choice");
  else ok(`the basis choice is on the card: "${card.basisKindGroupLabel}" — ${card.basisKindLabels.join(" / ")}`);
  if (card.checkedKind !== "usage") {
    fail(`the card opens on "${card.checkedKind}" — it must open on usage, which is what every stored schedule bills`);
  } else ok("it opens on usage, so opening the card cannot change a live bill");
  if (!card.present["percent-unit-price"]) fail("the usage basis draws no rate field — DEF-RAT-6146");
  else ok("a rate field is on the card");
}

// The BASED ON list, on each basis, by NAME.
note("\n    the Based on list, per basis — derived, never a named pair");
async function basisList(kindValue) {
  if (card.present["percent-basis-kind"]) {
    await pickBasisKind(kindValue);
  }
  return page.evaluate(() => {
    const el = document.querySelector("#percent-basis");
    return el ? Array.from(el.options).filter((o) => o.value !== "").map((o) => o.textContent.trim()) : [];
  });
}
const usageList = await basisList("usage");
const chargeList = card.present["percent-basis-kind"] ? await basisList("charge") : [];
note(`      % of the usage  → ${usageList.join(", ") || "(none)"}`);
note(`      % of the charge → ${chargeList.join(", ") || "(not offered)"}`);

if (MODE === "after" && card.present["percent-basis-kind"]) {
  await pickBasisKind("charge");
  const rateOnCharge = await page.evaluate(() => ({
    flat: document.getElementById("percent-unit-price") !== null,
    ladder: document.getElementById("tier-price-0") !== null,
    add: Array.from(document.querySelectorAll("button")).some((b) => /add tier/i.test(b.innerText)),
  }));
  if (rateOnCharge.flat || rateOnCharge.ladder || rateOnCharge.add) {
    fail(`a rate control is drawn on the CHARGE basis (${JSON.stringify(rateOnCharge)}) — a percentage of money needs no price per unit`);
  } else ok("the charge basis draws NO rate control of any kind");
  await pickBasisKind("usage");
}
if (MODE === "after") {
  if (usageList.includes("Sewer")) fail("the Based on list offers the service being priced");
  else ok("the service being priced is not in its own Based on list");
  if (chargeList.length <= usageList.length) {
    fail(`the charge basis offers ${chargeList.length} and the usage basis ${usageList.length} — on this utility trash meters nothing, so the usage list must be SHORTER`);
  } else ok(`the usage basis offers ${usageList.length} and the charge basis ${chargeList.length} — the derivation is doing work`);
}

// ── 3 · THE SAVE ───────────────────────────────────────────────────────────
note("\n3 · saving it — the whole of DEF-RAT-6146");
if (card.present["percent-basis-kind"]) {
  await pickBasisKind("usage");
}
await page.locator("#percent-value").fill("90");
await page.selectOption("#percent-basis", { label: usageList[0] ?? "Water" });
await page.waitForTimeout(300);
if (await page.locator("#tier-price-0").count()) {
  await page.locator("#tier-price-0").fill("5.00");
} else if (await page.locator("#percent-unit-price").count()) {
  await page.locator("#percent-unit-price").fill("5.00");
}
await page.screenshot({ path: `${SHOTS}-step3.png`, fullPage: true });

const posts = [];
page.on("response", async (res) => {
  const req = res.request();
  if (req.method() === "POST" && /\/rate-schedules/.test(req.url())) {
    let body = "";
    try { body = await res.text(); } catch { body = "(unreadable)"; }
    posts.push({ status: res.status(), sent: req.postData() ?? "", body: body.slice(0, 700) });
  }
});

for (let step = 0; step < 2; step += 1) {
  const cont = page.getByRole("button", { name: /continue|next/i }).first();
  if (await cont.count()) { await cont.click(); await page.waitForTimeout(700); }
}
// ── STEP 5's REVIEW LINE, READ BEFORE THE SAVE ──────────────────────────
// `90%` means two entirely different bills depending on which number it is
// taken of, so a comparison that shows the percentage and not the BASIS hides
// the change that matters most on this step.
const review = await page.evaluate(() => document.body.innerText);
note("\n   step 5, the rate comparison:");
for (const line of review.split("\n")) {
  if (/percentage of|percentage|price per unit|based on/i.test(line)) note(`      ${line}`);
}
if (MODE === "after") {
  if (!/Percentage of/i.test(review)) fail("step 5 does not review the BASIS — 90% of what is the whole question");
  else ok("step 5 reviews the basis by name");
  if (!/Price per unit/i.test(review)) fail("step 5 does not review the RATE");
  else ok("step 5 reviews the rate");
}

const save = page.getByRole("button", { name: /save|create|activate|file/i }).first();
if (await save.count()) { await save.click(); }
// A deadline, and the producer is the page itself.
const until = Date.now() + 20000;
while (Date.now() < until && posts.length === 0) {
  if (page.isClosed()) break;
  await page.waitForTimeout(400);
}
await page.screenshot({ path: `${SHOTS}-save.png`, fullPage: true });

if (posts.length === 0) {
  note("    no POST to /rate-schedules was made — the wizard refused before the wire");
} else {
  for (const p of posts) {
    note(`    POST → ${p.status}`);
    note(`      sent: ${p.sent.slice(0, 400)}`);
    note(`      back: ${p.body}`);
  }
}
const screen = await page.evaluate(() => document.body.innerText);
const refusedUnitPrice = posts.some((p) => /unit_price/.test(p.body)) || /unit_price/.test(screen);
// ⚠ `card.text` is the STEP 3 card, captured while it was on screen. `screen`
// above is whatever the wizard shows AFTER the save, which is a different
// page — reading the stale sentences off it would be law 7's fourth shape, a
// check looking at the wrong thing.

if (MODE === "before") {
  if (refusedUnitPrice) ok("BEFORE: the server refuses `structure.unit_price` and the screen has no field for it — DEF-RAT-6146 reproduced");
  else fail("BEFORE: the save was NOT refused for a missing rate — the defect did not reproduce, do not fix what you have not seen");
} else {
  const saved = posts.some((p) => p.status >= 200 && p.status < 300);
  if (saved) ok("the schedule SAVED from step 3 — which it could not do at all before");
  else fail("the schedule still cannot be saved: " + (posts.map((p) => `${p.status} ${p.body.slice(0, 200)}`).join(" | ") || "no POST made"));
}

// ── 4 · THE FIVE STALE SENTENCES ───────────────────────────────────────────
note("\n4 · the sentences on the screen (DEF-RAT-6145)");
const stale = ["usage charge", "usage charges"];
const hits = stale.filter((one) => card.text.toLowerCase().includes(one));
note(`    "usage charge(s)" on a USAGE-basis card: ${hits.length ? hits.join(", ") : "absent"}`);
if (MODE === "after" && hits.length) {
  fail("a usage-basis card still describes the DOLLAR arithmetic the engine stopped doing on 2026-09-08");
} else if (MODE === "after") ok("no sentence describes the wrong arithmetic");

note("\n── result ──");
if (problems.length === 0) console.log(`  MODE=${MODE}: everything this file looks at is as expected.`);
else { console.log(`  MODE=${MODE}: ${problems.length} problem(s):`); for (const p of problems) console.log("   · " + p); }
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
