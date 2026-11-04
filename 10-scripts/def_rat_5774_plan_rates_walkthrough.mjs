// ── Trace ──────────────────────────────────────────────
// Change:   DEF-RAT-5774 (the Rate schedule band prints the schedule's FIGURES,
//           not the word `seasonal`) · DEF-RAT-5775 (the base total drops
//           *"from the server"* — B14 rule 33 puts RATIONALE at zero words).
// Rules:    PO 2026-09-19, verbatim: *"here can we show actual rate prices -
//           when rates are tiered, seasonal, ToU etc- it is not shown"* ·
//           PO ruling 2026-09-10 (the review AND the plan's page show the
//           schedule's figures) · B14 rule 33 · B14 rule 37 (a drawn figure is
//           an ILLUSTRATION) · B14 rule 42 (a screen is built from the drawing
//           AS AN IMAGE) · CLAUDE.md hard-won law 6 — no gate reads rendered
//           output, so this is the only thing that can see the cell.
// ───────────────────────────────────────────────────────
/**
 * Read the `RATE` column on BOTH screens that share `PlanSummaryCard`.
 *
 *     BASE=http://127.0.0.1:8394 PASSWORD='…' \
 *       CHROME_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
 *       node 10-scripts/def_rat_5774_plan_rates_walkthrough.mjs
 *
 * ⚠ **BOTH, BECAUSE ONE COMPONENT FEEDS TWO SCREENS AND ONLY ONE WAS IN THE
 * PO'S SCREENSHOT.** `PlanSummaryCard` is rendered by the wizard's step 8 and
 * by the plan's Overview tab. A change here shows in two places, which is the
 * point — they must not disagree — so this measures the second one instead of
 * assuming it.
 *
 * ⚠ **IT ASSERTS THE FIGURE, NOT THAT *A* FIGURE APPEARS.** *A price is on the
 * page* passes on a screen showing the wrong price. So the cell is read against
 * what the API says that schedule's tiers and windows actually hold, fetched in
 * the same session — the screen and the server have to agree, digit for digit.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8394";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/-home-user-SMARTBillHub/da7d6dea-a84b-56ee-b035-57684ffe93fb/scratchpad/rat5774/shots";

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1200 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => fail(`PAGE ERROR: ${e.message}`));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
note(`signed in as ${EMAIL} → ${page.url()}`);

const api = async (p) => (await page.request.get(`${BASE}/api/${TENANT}${p}`)).json();
const list = (r) => r.results ?? r.items ?? r;

/** The band's own rows, read off the rendered table. */
async function band() {
  const root = page.locator('[data-band="schedules"]');
  await root.waitFor({ timeout: 30000 });
  // ⚠ `allInnerTexts` applies CSS `text-transform`, and the table header wears
  // `uppercase` — so the DOM says `Rate` and this reads `RATE`. Compared in one
  // case, or the check fails on a column that is perfectly correct.
  const columns = (await root.locator("thead th").allInnerTexts()).map((s) => s.trim().toUpperCase());
  // A footnote is its own single-cell row spanning the table (`DEF-RAT-5801`),
  // so a DATA row is one with as many cells as there are columns.
  const rows = [];
  const notes = [];
  for (const tr of await root.locator("tbody tr").all()) {
    const cells = (await tr.locator("td").allInnerTexts()).map((s) => s.trim());
    // Keyed on ONE CELL rather than on `cells.length === columns.length`, so
    // this reads the same on a build where the footnote is still an extra cell
    // in the data row — otherwise the RED proof misreports every data row as a
    // footnote and diagnoses the wrong thing.
    (cells.length === 1 ? notes : rows).push(cells);
  }
  return { columns, rows, notes };
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE PLAN'S OWN PAGE — `PLN-02 · Overview`, blueprint p106–p107
// ══════════════════════════════════════════════════════════════════════════
const plans = list(await api("/plans?page_size=100"));
const plan = plans.find((p) => p.code === "RES-STD") ?? plans[0];
note(`\n1 · The plan's page — ${plan.name} (${plan.code})`);
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${plan.id}`, { waitUntil: "domcontentloaded" });
const onPage = await band();
await page.screenshot({ path: `${SHOTS}/plan-page-rate-column.png`, fullPage: true });
note(`   columns: ${onPage.columns.filter(Boolean).join(" | ")}`);
onPage.columns.includes("RATE")
  ? ok("the RATE column is drawn — p107 draws it and we did not")
  : fail("no RATE column on the plan's page");
for (const cells of onPage.rows) note(`   row: ${cells.map((c) => JSON.stringify(c)).join(" · ")}`);

// The figures the SERVER holds for the schedules this plan names.
const detail = await api(`/plans/${plan.id}`);
const cards = list(await api("/rate-schedules?page_size=100"));
let checked = 0;
for (const ref of detail.rate_schedules ?? []) {
  const card = cards.find((c) => c.id === ref.tariff_id);
  if (!card) continue;
  const version = card.current_version ?? card.draft_version;
  const st = version?.structure ?? {};
  const row = onPage.rows.find((cells) => cells.some((c) => c === card.name));
  if (!row) { fail(`the plan names ${card.name} and the band has no row for it`); continue; }
  const rate = row[4] ?? "";
  // Every price the server holds, as the four places a RATE rounds to
  // (OQ-620(a)) — NOT money's two. Storage is six.
  const wanted = [
    ...(st.tiers ?? []).filter((one) => one.size_class === null).map((one) => one.unit_price),
    ...(st.windows ?? []).map((one) => one.unit_price),
    st.capacity?.rate_per_unit,
    st.demand?.energy_rate_per_kwh,
    st.demand?.demand_rate_per_kw,
  ]
    .filter((one) => one !== null && one !== undefined)
    .map((one) => Number(one).toFixed(4));
  note(`   ${card.name} [${card.structure}] server holds ${wanted.join(" ")} → cell reads ${JSON.stringify(rate)}`);
  if (wanted.length === 0) { note("      (nothing priced — nothing to assert)"); continue; }
  checked += 1;
  const missing = wanted.filter((one) => !rate.includes(one));
  missing.length === 0
    ? ok(`${card.name}: every served price is ON the screen, at four places`)
    : fail(`${card.name}: the screen is missing ${missing.join(", ")} — it reads ${JSON.stringify(rate)}`);
  // The defect itself: the structure NAME standing in for the price.
  /^\s*(seasonal|tiered|time_of_use|flat|demand|capacity|percent_of_service)\s*$/.test(rate)
    && fail(`${card.name}: the RATE cell is still just the structure name — ${JSON.stringify(rate)}`);
  // Hard rule 2's neighbour: a rate is four places, and storage is six.
  /\d\.\d{5,}/.test(rate) && fail(`${card.name}: storage precision reached the screen — ${JSON.stringify(rate)}`);
}
checked ? ok(`${checked} schedule(s) checked digit for digit against the API`) : fail("no schedule could be checked");

// The Usage cell must name the shape in words, never the stored enum.
// ⚠ The tick is CONDITIONAL. It printed unconditionally once, directly under
// two failures of its own loop — a line that says PASS while the thing it
// names is red is worse than no line (law 7, habit 3).
const rawEnums = onPage.rows
  .map((cells) => cells[3] ?? "")
  .filter((usage) => /^(seasonal|tiered|time_of_use|flat|demand|capacity|percent_of_service)$/.test(usage));
rawEnums.length
  ? rawEnums.forEach((usage) => fail(`the Usage cell still prints the raw enum: ${JSON.stringify(usage)}`))
  : ok(`no Usage cell prints a raw enum value (${String(onPage.rows.length)} row(s) read)`);

// ══════════════════════════════════════════════════════════════════════════
// 2 · STEP 8 OF THE WIZARD — `PLN-03 step 8`, blueprint p102
// ══════════════════════════════════════════════════════════════════════════
note("\n2 · The wizard's step 8 — the same card, the other screen");
async function continueOn() {
  const cont = page.getByRole("button", { name: /^Continue$/ }).first();
  if (!(await cont.count())) return false;
  await cont.click().catch(() => {});
  await page.waitForTimeout(700);
  return true;
}
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/new`, { waitUntil: "domcontentloaded" });
await page.locator("#plan-name").waitFor({ timeout: 30000 });
await page.fill("#plan-name", "DEF-RAT-5774 walkthrough");
await page.fill("#plan-code", `D5774-${Date.now().toString().slice(-6)}`);
await page.selectOption("#plan-customer-class", { index: 1 }).catch(() => {});
await continueOn();

// step 2 — tick the services the priced schedules belong to
const priced = [...new Set(cards
  .filter((c) => { const v = c.current_version ?? c.draft_version; const s = v?.structure ?? {}; return (s.tiers ?? []).length || (s.windows ?? []).length; })
  .map((c) => c.service))];
// ⚠ **STEP 2 IS AN *Add a service…* PICKER, NOT A TICK-LIST.** It was
// `#plan-service-<code>` checkboxes and a sibling lane redrew it while this was
// being written. A walkthrough that keeps asking for the old control reports
// *"the control is not wired"* over a control that is wired — the exact mistake
// `cr087_plan_wizard_walkthrough.mjs` records in its own docstring.
const picker = page.locator("select").filter({ has: page.locator('option[value=""]') }).first();
const offered = await picker.locator("option").all();
note(`   step 2 offers ${offered.length - 1} service(s); priced services are ${priced.join(", ")}`);
let ticked = 0;
for (const code of priced) {
  const option = picker.locator(`option[value="${code}"]`);
  if (!(await option.count())) { note(`   ${code} is switched OFF for this tenant`); continue; }
  await picker.selectOption(code);
  await page.waitForTimeout(500);
  ticked += 1;
  note(`   added service: ${code}`);
}
if (ticked === 0) fail("step 2 added nothing — step 8 would have no service to price");
await page.waitForTimeout(400);
await continueOn();

// step 3 — CHOOSE a schedule for each, or step 8 has nothing to price
await page.waitForTimeout(600);
for (const sel of await page.locator('select[id^="schedule-"]').all()) {
  const options = await sel.locator("option").all();
  for (let i = 1; i < options.length; i += 1) {
    const value = await options[i].getAttribute("value");
    if (!value) continue;
    const card = cards.find((c) => c.id === value);
    const st = (card?.current_version ?? card?.draft_version)?.structure ?? {};
    if ((st.tiers ?? []).length || (st.windows ?? []).length) {
      await sel.selectOption(value);
      note(`   ${await sel.getAttribute("id")} → ${card.name} [${card.structure}]`);
      break;
    }
  }
}
await page.waitForTimeout(400);

// ⚠ **PRESS UNTIL THE SCREEN SAYS 8, NEVER A FIXED COUNT.** A step that refuses
// to advance leaves a fixed loop reporting success on step 3 — and the band it
// then fails to find reads as "the card is missing", which is a diagnosis of
// the wrong screen. The step number is on the page; ask it.
async function stepNow() {
  const text = await page.locator("body").innerText();
  const m = text.match(/STEP\s+(\d+)\s+OF\s+8/i);
  return m ? Number(m[1]) : null;
}
for (let press = 0; press < 12; press += 1) {
  const before = await stepNow();
  if (before === 8) break;
  await continueOn();
  let after = await stepNow();
  if (after === before) {
    // A step that refuses names what it wants. Step 7 wants a start date
    // (`BR-RAT-890`, PO 2026-08-28: a plan cannot be published without saying
    // when it starts) — so fill the empty dates and press once more before
    // calling it stuck, or this reports a refusal that is the product working.
    let filled = 0;
    for (const el of await page.locator('input[type="date"]:visible').all()) {
      if ((await el.inputValue().catch(() => "x")) !== "") continue;
      await el.fill("2027-01-01").catch(() => {});
      filled += 1;
    }
    if (filled) {
      note(`   step ${String(before)} wanted ${filled} date(s) — filled and pressing again`);
      await continueOn();
      after = await stepNow();
    }
  }
  if (after === before) {
    const refusal = await page.locator('[role="alert"]').allInnerTexts().catch(() => []);
    fail(`stuck on step ${String(before)} — ${refusal.join(" | ") || "Continue did nothing and nothing was said"}`);
    break;
  }
  note(`   step ${String(before)} → ${String(after)}`);
}
await page.waitForTimeout(1200);

const heading = await page.locator("h2, h3").allInnerTexts().catch(() => []);
note(`   headings: ${heading.map((h) => h.trim()).filter(Boolean).slice(0, 6).join(" | ")}`);
const onStep8 = await band();
await page.screenshot({ path: `${SHOTS}/step8-rate-column.png`, fullPage: true });
note(`   columns: ${onStep8.columns.filter(Boolean).join(" | ")}`);
onStep8.columns.includes("RATE")
  ? ok("step 8 draws the RATE column too — p102 draws it")
  : fail("no RATE column on step 8");
for (const cells of onStep8.rows) note(`   row: ${cells.map((c) => JSON.stringify(c)).join(" · ")}`);

// THE TWO SCREENS MUST NOT DISAGREE — that is why the card is shared.
// ⚠ It is an AGREEMENT check and not a correctness one: it passes when both
// screens are wrong in the same way, which is exactly what it did on the tip.
JSON.stringify(onStep8.columns) === JSON.stringify(onPage.columns)
  ? ok("step 8 and the plan's page draw the SAME columns")
  : fail(`the two screens disagree: ${onStep8.columns.join("|")} vs ${onPage.columns.join("|")}`);

const priceOnStep8 = onStep8.rows.some((cells) => /\d\.\d{4}/.test(cells[4] ?? ""));
priceOnStep8 ? ok("step 8 shows a real four-place rate") : fail("step 8 shows no rate at all");

// ── DEF-RAT-5775 ───────────────────────────────────────────────────────────
// ⚠ **THIS ONE CAN ONLY EVER FAIL, NEVER PASS, SO IT DOES NOT PRINT A TICK.**
// A NEW draft has no server-computed total, so the label is not on this screen
// at all and its absence says nothing about the defect. Proved: on the
// unmodified tip this printed a tick while the phrase was live one screen away.
// Part 3 below is the check that can actually go red, and it did.
const body = await page.locator("body").innerText();
if (/from the server/i.test(body)) {
  fail("step 8 still says 'from the server' — B14 rule 33, rationale is zero words");
} else if (/Plan base charge/i.test(body)) {
  ok("the base total is labelled here, and says nothing about where it came from");
} else {
  note("   (a NEW draft draws no server total — DEF-RAT-5775 is checked in part 3)");
}

// ══════════════════════════════════════════════════════════════════════════
// 3 · THE SAVED PLAN'S STEP 8 — where the base TOTAL is actually drawn
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **A NEW DRAFT NEVER SHOWS IT, SO PART 2 COULD NOT CHECK `DEF-RAT-5775`.**
// `PlanWizard` draws the total only when `plan !== null && plan.base_charges
// !== null` — the SERVER's sum exists once the plan is saved (`DEF-RAT-5694`
// removed the draft branch on purpose). Checking the label on a screen that
// never draws it is law 7's *looking at the wrong thing*, so this walks the
// EDIT wizard of a published plan, where the figure is real.
note("\n3 · A SAVED plan's step 8 — the base total, where it is actually drawn");
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${plan.id}/edit`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1500);
for (let press = 0; press < 12; press += 1) {
  const text = await page.locator("body").innerText();
  const m = text.match(/STEP\s+(\d+)\s+OF\s+8/i);
  if (!m || Number(m[1]) === 8) break;
  await continueOn();
}
await page.waitForTimeout(1000);
const saved = await page.locator("body").innerText();
await page.screenshot({ path: `${SHOTS}/step8-saved-base-total.png`, fullPage: true });
const label = saved.match(/Plan base charge[^\n]*/);
note(`   the label reads: ${JSON.stringify(label ? label[0] : null)}`);
if (!label) {
  fail("the base total is not drawn at all on a saved plan's step 8");
} else {
  /from the server/i.test(label[0])
    ? fail(`still rationale on screen: ${JSON.stringify(label[0])} — B14 rule 33`)
    : ok("the label carries the figure and no provenance");
  /\$\d/.test(label[0])
    ? ok("and the FIGURE is still there — the fix dropped words, not the number")
    : fail(`the figure went with the phrase: ${JSON.stringify(label[0])}`);
  label[0].replace(/[:·].*$/, "").trim().split(/\s+/).length <= 3
    ? ok("a LABEL is three words or fewer (B14 rule 33)")
    : fail(`the label is longer than three words: ${JSON.stringify(label[0])}`);
}

await browser.close();
console.log(problems.length ? `\nFAILED: ${problems.length} problem(s)` : "\nALL CHECKS PASSED");
process.exit(problems.length ? 1 : 0);
