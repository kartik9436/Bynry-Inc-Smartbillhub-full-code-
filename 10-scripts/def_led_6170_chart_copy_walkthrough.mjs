// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6170 — Settings → Accounting → Chart of accounts (SET-11)
//          carries a 9-to-21-word paragraph under every one of 129 rows.
//          PO, verbatim: "Too much text on this screen - GL code mapping".
//          Their paste also shows the unsigned note GLUED to the account name
//          with no separator — "Petty cashProposed — finance has not approved
//          this account number yet."
// Also:    DEF-LED-6171 (5700 renders the raw code `depreciation_expense` in
//          Role in the books — MEASURED here, fixed in the same wave).
// Rules:   B14 rule 33 (on-screen text is capped by what it is FOR; RATIONALE
//          is ZERO WORDS ON SCREEN) · B14 rule 32 (a screen has a description
//          budget; a stated absence is CLOSED by default; no internal code in
//          clerk-facing copy) · BR-SHL-025 (a control that cannot act renders
//          DISABLED WITH ITS REASON — the reason lives ON the control) ·
//          CLAUDE.md hard-won law 6 (no gate reads rendered output) ·
//          22-product-maintenance-process.md §0/§4 (reproduce first; prove it
//          against the reproduction, in a browser).
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THIS FILE COUNTS WORDS, BECAUSE THE DEFECT IS A WORD COUNT.**
 *
 * Every string on this screen was in the DOM legitimately and every assertion
 * about it passed. What nobody measured is how many TIMES it renders: the
 * unsigned note is 9 words and the demo tenant has **94 unsigned accounts**,
 * and the delete refusal is 14-21 words over **129 rows**. A `toContain` on
 * one of them is green either way, which is why this walk reports a TOTAL.
 *
 * The number it prints is the body copy a clerk scrolls past at rest: the text
 * of every `.fin-absent-reason` note inside the chart panel. It deliberately
 * does NOT count column headings, cell values, filters or button labels —
 * those are the screen doing its job.
 *
 * RUN:
 *   BASE=http://127.0.0.1:8948 node 10-scripts/def_led_6163_chart_copy_walkthrough.mjs
 *
 * ⚠ **AGAINST A DATABASE NOBODY ELSE IS SEEDING** — `10-scripts/proof-db.sh
 * clone <yours>` — and **on your own ports**. `pkill -f "server.mjs"` kills
 * every lane's server; kill by the PID you recorded.
 *
 * ⚠ **BOOT THROUGH `07-frontend/server.mjs`, NOT `vite`.** That server IS the
 * deployed join, so the walk exercises what a clerk actually gets.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8948";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/coa-proof";
const LABEL = process.env.LABEL ?? "run";

const problems = [];
const ok = (m) => console.log("  ✓ " + m);
const fail = (m) => {
  problems.push(m);
  console.log("  ✗ " + m);
};

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/opt/pw-browsers/chromium",
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => fail("page error: " + e.message));

console.log("\n── sign in ─────────────────────────────────────────────");
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
ok("signed in");

console.log("\n── SET-11 · Settings → Accounting → Chart of accounts ───");
await page.goto(`${BASE}/${TENANT}/settings/accounting`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("table tbody tr", { timeout: 30000 });
const rows = await page.locator("table tbody tr").count();
console.log(`  chart rows on screen: ${rows}`);

/**
 * The measurement.
 *
 * ⚠ **SCOPED TO THE CHART PANEL, NOT TO THE PAGE.** Settings → Accounting
 * carries six sibling GL-mapping panels with notes of their own, and counting
 * those would report a number that moves when a neighbour changes — the
 * "reports over a scope it silently includes" mirror of hard-won law 7. The
 * panel is found by the heading the PO names, and everything measured is
 * inside it.
 */
const measure = await page.evaluate(() => {
  const heads = [...document.querySelectorAll("h3")];
  const head = heads.find((h) => h.textContent.trim() === "Chart of accounts");
  if (head === undefined) return null;
  // ⚠ `[data-panel]` AND NOT `closest("section, div")`, AND THIS WALK CAUGHT
  // ITSELF ON IT. The heading's nearest `div` is `.fin-panel-head` — 35px tall,
  // holding the heading and the Add button and NOT ONE ROW of the table — so
  // the first run of this file reported **0 notes, 0 words** over a screen
  // carrying 223 of them, and printed a green tick for rule 33. That is
  // hard-won law 7's "reports zero over a scope it silently excludes", authored
  // by accident inside the check written to measure it. `Panel` marks its root
  // `data-panel=""`; the row count below is what makes a wrong answer LOUD
  // instead of quiet.
  const panel = head.closest("[data-panel]");
  if (panel === null) return null;
  const notes = [...panel.querySelectorAll(".fin-absent-reason")];
  const words = (s) => s.trim().split(/\s+/).filter(Boolean).length;
  const texts = notes.map((n) => n.textContent.trim()).filter(Boolean);
  const tally = {};
  for (const t of texts) tally[t] = (tally[t] ?? 0) + 1;
  // The Role-in-the-books column, for DEF-LED-6171: a raw enum code is
  // lower_snake_case where every catalogue phrase has a space in it.
  const raw = [...panel.querySelectorAll("tbody tr")]
    .map((tr) => (tr.children[4] ?? {}).textContent ?? "")
    .map((s) => s.trim())
    .filter((s) => /^[a-z][a-z0-9]*(_[a-z0-9]+)+$/.test(s));
  return {
    // The scope check. A measurement of "the chart panel" that cannot see the
    // chart is not a smaller number, it is a different question answered.
    rowsInPanel: panel.querySelectorAll("tbody tr").length,
    noteCount: texts.length,
    totalWords: texts.reduce((n, t) => n + words(t), 0),
    distinct: Object.entries(tally)
      .sort((a, b) => b[1] - a[1])
      .map(([text, n]) => ({ n, words: words(text), text })),
    rawCodes: [...new Set(raw)],
    panelHeight: Math.round(panel.getBoundingClientRect().height),
  };
});

if (measure === null) {
  fail("the Chart of accounts panel was not found on the page");
} else {
  console.log(`\n  BODY COPY AT REST, inside the chart panel:`);
  console.log(`    rows in panel  : ${measure.rowsInPanel}`);
  if (measure.rowsInPanel !== rows) {
    fail(
      `the measured panel holds ${measure.rowsInPanel} rows but the screen has ${rows} — ` +
        `the scope is wrong and every number below it is meaningless`,
    );
  }
  console.log(`    notes rendered : ${measure.noteCount}`);
  console.log(`    TOTAL WORDS    : ${measure.totalWords}`);
  console.log(`    panel height   : ${measure.panelHeight}px`);
  console.log(`\n  distinct strings, most-repeated first:`);
  for (const d of measure.distinct) {
    console.log(`    ${String(d.n).padStart(4)} × ${String(d.words).padStart(2)}w  ${d.text.slice(0, 84)}`);
  }

  // ── B14 rule 33 — every note at rest is capped by what it is FOR ────────
  const over = measure.distinct.filter((d) =>
    d.text
      .replace(/…/g, ".")
      .split(/(?<=[.!?])\s+/)
      .some((s) => s.trim().split(/\s+/).filter(Boolean).length > 6),
  );
  if (over.length === 0) {
    ok("no note at rest carries a sentence over six words (B14 rule 33)");
  } else {
    for (const d of over) fail(`${d.words}-word note, ${d.n}× on screen: ${d.text.slice(0, 70)}`);
  }

  // ── DEF-LED-6171 — no raw enum code in Role in the books ────────────────
  if (measure.rawCodes.length === 0) {
    ok("Role in the books shows no raw enum code (B14 rule 32)");
  } else {
    fail(`raw code(s) in Role in the books: ${measure.rawCodes.join(", ")}`);
  }
}

// ── THE NAME IS THE NAME — the unsigned note must not be glued to it ──────
// The PO's paste reads "Petty cashProposed — finance has not approved this
// account number yet." That is ONE text node's worth of run-on in the Name
// cell, and it is what `1020` looked like at 2.325.1.
const nameCell = await page.evaluate(() => {
  const tr = [...document.querySelectorAll("tbody tr")].find(
    (r) => (r.children[0] ?? {}).textContent?.trim() === "1020",
  );
  return tr === undefined ? null : (tr.children[1] ?? {}).textContent.trim();
});
if (nameCell === null) {
  fail("account 1020 was not on the page");
} else {
  console.log(`\n  1020 Name cell reads: ${JSON.stringify(nameCell)}`);
  if (nameCell === "Petty cash") {
    ok("the Name cell holds the name and nothing else");
  } else {
    fail(`the Name cell carries more than the name: ${JSON.stringify(nameCell)}`);
  }
}

// ── THE TWO STATUS PILLS DO NOT TOUCH ─────────────────────────────────────
// `.pill` is `display: inline-flex`, so two written adjacently in JSX render
// with no text node between them and their backgrounds meet — which is *"Petty
// cashProposed"* again, one element up. **Only a browser can answer this**:
// jsdom has no layout, so every element it renders is at 0x0 and a DOM test
// would report a zero gap for a correct screen and a broken one alike.
const pillGap = await page.evaluate(() => {
  const tr = [...document.querySelectorAll("tbody tr")].find(
    (r) => (r.children[0] ?? {}).textContent?.trim() === "1020",
  );
  if (tr === undefined) return null;
  const pills = [...(tr.children[5] ?? tr).querySelectorAll(".pill")];
  if (pills.length < 2) return { count: pills.length, gap: null };
  const a = pills[0].getBoundingClientRect();
  const b = pills[1].getBoundingClientRect();
  // ⚠ **STACKED IS NOT TOUCHING, AND THE FIRST DRAFT OF THIS CHECK COULD NOT
  // TELL THEM APART.** The Status column is narrow, so the second pill WRAPS to
  // its own line — which is correct and is what the browser shows. Measuring
  // `b.left - a.right` alone then reports **-57px** and calls a perfectly good
  // screen broken: a horizontal reading of a vertical fact. Two pills are only
  // colliding when they share a LINE, so the line test comes first.
  const stacked = b.top >= a.bottom - 1;
  return {
    count: pills.length,
    stacked,
    gap: stacked ? Math.round(b.top - a.bottom) : Math.round(b.left - a.right),
    words: pills.map((p) => p.textContent.trim()),
  };
});
if (pillGap === null) {
  fail("account 1020 was not on the page for the pill check");
} else if (pillGap.count < 2) {
  fail(`1020 is unsigned but its Status cell holds ${pillGap.count} pill(s)`);
} else if (pillGap.gap >= 0) {
  ok(
    `the two status pills are ${pillGap.stacked ? "stacked" : "side by side"}, ` +
      `${pillGap.gap}px apart: ${JSON.stringify(pillGap.words)}`,
  );
} else {
  fail(
    `the two status pills overlap on one line (${pillGap.gap}px): ${JSON.stringify(pillGap.words)}`,
  );
}

// ── THE REFUSAL IS STILL THERE, ON THE CONTROL (BR-SHL-025) ───────────────
// What must NOT change: an account that cannot be deleted still cannot, and a
// clerk can still read why. This asserts the BEHAVIOUR is unmoved while the
// resting paragraph is gone.
const deleteState = await page.evaluate(() => {
  const btns = [...document.querySelectorAll('tbody button[aria-label="Delete"]')];
  const blocked = btns.filter((b) => b.disabled);
  return {
    total: btns.length,
    blocked: blocked.length,
    firstReason: blocked.length > 0 ? blocked[0].getAttribute("title") : null,
  };
});
console.log(`\n  Delete controls: ${deleteState.total}, of which disabled: ${deleteState.blocked}`);
console.log(`  a blocked control's tooltip: ${JSON.stringify(deleteState.firstReason)}`);
if (deleteState.blocked > 0 && (deleteState.firstReason ?? "").length > 0) {
  ok("a blocked Delete is still disabled and still says why, on the control");
} else {
  fail("a blocked Delete no longer carries its reason — BR-SHL-025");
}

await page.screenshot({ path: `${SHOTS}/${LABEL}-01-chart-top.png` });
await page.evaluate(() => {
  const all = [...document.querySelectorAll("*")];
  const sc =
    all.find(
      (e) => e.scrollHeight > e.clientHeight + 500 && getComputedStyle(e).overflowY !== "visible",
    ) ?? document.scrollingElement;
  sc.scrollTop = 2000;
});
await page.waitForTimeout(400);
await page.screenshot({ path: `${SHOTS}/${LABEL}-02-chart-scrolled.png` });

// ── 1280, the laptop minimum the staff app must work at ───────────────────
await page.setViewportSize({ width: 1280, height: 900 });
await page.waitForTimeout(300);
const sideways = await page.evaluate(
  () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
);
if (sideways) fail("the page scrolls sideways at 1280");
else ok("no sideways scroll at 1280");
await page.screenshot({ path: `${SHOTS}/${LABEL}-03-chart-1280.png` });

console.log("\n────────────────────────────────────────────────────────");
console.log(problems.length === 0 ? "ALL CHECKS PASSED" : `${problems.length} PROBLEM(S)`);
for (const p of problems) console.log("  · " + p);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
