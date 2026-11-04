// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CWP-6072 — CWP-057's *What it would cost* adds a reconnection
//           fee the balance it is adding to already holds. Screen: CWP-057
//           (`P43`), rail panel, `[data-total='if-it-goes-that-far']`
// Also:     DEF-CWP-6083 — the portal answers *what you owe* from OPEN BILLS
//           while the rest of the product answers it from the LEDGER. This walk
//           MEASURES both figures and asserts nothing about them: it is filed,
//           not fixed, and a walk that asserted agreement would go red on a
//           defect somebody else is going to fix.
// Rules:    CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
//           output — diff the running app) · hard rule 2 (money displayed at
//           2 dp) · B14 rule 33 (a FACT is six words or fewer)
// ───────────────────────────────────────────────────────
/**
 * def_cwp_6072_arrears_cost_walkthrough — **is the fee on this screen counted
 * once or twice?**, asked of a browser.
 *
 *     PORTAL_LOGIN=… PORTAL_PASSWORD=… ACCOUNT_NO=A-11340 \
 *     BASE=http://127.0.0.1:8937 TENANT=brazosbend \
 *     SHOTS=/tmp/shots node 10-scripts/def_cwp_6072_arrears_cost_walkthrough.mjs
 *
 * ⚠ **IT PRINTS THE FIGURES AND THEN ASSERTS THE ARITHMETIC.** The panel shows
 * *Owed now*, *Reconnection fee* and a subtotal. After a cut the fee is an
 * ISSUED bill, so it is already inside *Owed now* — the subtotal must EQUAL
 * *Owed now*, and the fee row must say so in words. Before a cut the fee is a
 * quote and the subtotal must be the SUM. The walk reads the case's own state
 * from the API and checks the arithmetic that state requires, so it cannot be
 * satisfied by whichever answer happens to be on screen.
 *
 * ⚠ **REBUILD THE BUNDLE FIRST.** `server.mjs` serves whatever was in `dist/`
 * when it started, forever, and prints the directory only at boot. A stale
 * bundle is indistinguishable from a fix that did not work.
 *
 * ⚠ **THE SCREEN IS ABSENT UNLESS SOMETHING IS PAST DUE** (`BR-CWP-093`), and
 * on a freshly cut account nothing is: the reconnection fee bill is due on the
 * day of the cut. That is why `DEF-CWP-6072` is LATENT rather than live, and it
 * is why this walk needs an account that is cut AND carries an older overdue
 * bill. If it reports *nothing is overdue*, that is the state to fix in the
 * fixture — it is not a clean run.
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

// ⚠ Node resolves a bare import from THIS file's directory upward, never from
// the working directory, and the repo root has no `node_modules`.
const require = createRequire("/tmp/claude-0/wt-cwp1/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8937";
const TENANT = process.env.TENANT ?? "brazosbend";
const LOGIN = process.env.PORTAL_LOGIN ?? "alvarez0@example.invalid";
const PASSWORD = process.env.PORTAL_PASSWORD ?? "Sample-Portal-2026!";
const ACCOUNT_NO = process.env.ACCOUNT_NO ?? "A-11340";
const SHOTS = process.env.SHOTS ?? null;
const LABEL = process.env.LABEL ?? "run";
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

const rel = (p) => `${BASE}/${TENANT}/portal${p}`;
let failures = 0;
const check = (ok, what, detail) => {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${what}${detail ? ` — ${detail}` : ""}`);
  if (!ok) failures += 1;
};
const money = (text) => {
  const m = (text ?? "").match(/-?\$[\d,]+\.\d{2}/);
  return m ? Number(m[0].replace(/[$,]/g, "")) : null;
};

// ⚠ **THE BROWSER IS NAMED EXPLICITLY.** `playwright` 1.62 looks for build
// 1234 and this image ships 1194, so a bare `launch()` dies telling you to run
// `npx playwright install` — which is not the problem and would download half a
// gigabyte to fix it. `po20260920_reconnect_and_visit_walk.mjs` does the same.
const CHROME = process.env.CWALK_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const jsErrors = [];
page.on("pageerror", (e) => jsErrors.push(String(e)));

const signIn = await page.request.post(`${BASE}/api/${TENANT}/portal/auth/sign-in`, {
  data: { email: LOGIN, password: PASSWORD },
});
if (!signIn.ok()) {
  console.log("SIGN-IN FAILED", signIn.status(), (await signIn.text()).slice(0, 300));
  process.exit(1);
}
console.log(`signed in as ${LOGIN}`);

// ── which account, and WHAT THE SERVER SAYS ABOUT IT ────────────────────────
const session = await (await page.request.get(`${BASE}/api/${TENANT}/portal/session`)).json();
const accounts = session.accounts ?? [];
const wanted = accounts.find((a) => (a.label ?? "").includes(ACCOUNT_NO) || a.account_no === ACCOUNT_NO)
  ?? accounts[0];
if (!wanted) {
  console.log("NO ACCOUNT ON THIS LOGIN — the walk below would prove nothing");
  process.exit(1);
}
const arrears = await (
  await page.request.get(`${BASE}/api/${TENANT}/portal/accounts/${wanted.id}/arrears`)
).json();
// ⚠ **WHICH SIDE OF THE CUT — READ FROM THE TIMELINE, NOT FROM THE FIELD THE
// FIX ADDS.** `cost.basis` is new in the fix, so a walk that keyed on it would
// simply SKIP its own arithmetic check against the build it is meant to catch:
// law 7's *incapable of failing*. The first version of this file did exactly
// that and printed ALL CHECKS PASSED over a `$287.45` subtotal built from a
// `$212.45` balance and a `$75.00` fee. The `cut` step is on the timeline in
// both builds, and `state: "done"` is `case.cut_on` being set.
const cutStep = (arrears.timeline ?? []).find((s) => s.step === "cut");
const cutSide = arrears.case_open ? cutStep?.state === "done" : null;
console.log(`\n── ${ACCOUNT_NO} · what the server answers ──`);
console.log(`  overdue          ${arrears.overdue}`);
console.log(`  owed             ${arrears.owed}`);
console.log(`  cost.subtotal    ${arrears.cost?.subtotal}`);
console.log(`  cost.basis       ${JSON.stringify(arrears.cost?.basis ?? null)}`);

// ⚠ **DEF-CWP-6083, MEASURED AND NOT ASSERTED.** The staff record reads the
// LEDGER position and this screen reads the OPEN BILLS. On a migrated account
// they differ by the whole cutover opening balance. Printed so a reader of this
// run can see the gap; nothing here goes red on it.
console.log(`  ⓘ this figure is the OPEN-BILL sum (DEF-CWP-6083 — the staff record reads the ledger)`);

if (!arrears.overdue) {
  console.log("\n⚠ NOTHING IS OVERDUE ON THIS ACCOUNT, so CWP-057 renders its empty state.");
  console.log("  That is BR-CWP-093 working, and it is also why this defect is latent.");
  console.log("  The walk cannot prove the panel from here — give the account an overdue bill.");
  await browser.close();
  process.exit(1);
}

// ── the screen itself ───────────────────────────────────────────────────────
await page.goto(rel("/overdue"), { waitUntil: "domcontentloaded" });
await page.waitForTimeout(700);
const switcher = await page.$("[data-account-switcher='select']");
if (switcher) {
  await switcher.selectOption(wanted.id);
  await page.waitForTimeout(700);
}
if (SHOTS) await page.screenshot({ path: `${SHOTS}/cwp-057-${LABEL}.png`, fullPage: true });

const text = async (sel) => {
  const el = await page.$(sel);
  return el ? (await el.textContent())?.replace(/\s+/g, " ").trim() ?? "" : null;
};
const screen = await page.$("[data-screen='CWP-057']");
const owedRow = await text("[data-part='owed']");
const feeRow = await text("[data-part='reconnection_fee']");
const included = await text("[data-part-included='reconnection_fee']");
const subtotal = await text("[data-total='if-it-goes-that-far']");
const headline = await text("[data-headline]");

console.log(`\n── ${ACCOUNT_NO} · CWP-057 as a customer sees it ──`);
console.log(`  headline         ${headline}`);
console.log(`  Owed now         ${owedRow}`);
console.log(`  Reconnection fee ${feeRow}`);
console.log(`  (fee note)       ${included ?? "— none —"}`);
console.log(`  subtotal row     ${subtotal}`);

console.log(`\n── the arithmetic this case requires ──`);
check(screen !== null, "CWP-057 rendered", screen ? null : "no [data-screen='CWP-057'] on the page");
const owedNum = money(owedRow);
const feeNum = money(feeRow);
const totalNum = money(subtotal);
if (cutSide === true) {
  check(
    totalNum !== null && owedNum !== null && Math.abs(totalNum - owedNum) < 0.005,
    "AFTER THE CUT the subtotal is what is owed and nothing is added",
    `owed ${owedNum} · fee ${feeNum} · subtotal ${totalNum}`,
  );
  check(
    feeNum !== null,
    "the fee is still SHOWN (a customer must see what they are charged)",
    `fee row ${feeRow}`,
  );
  check(
    included !== null && included.length > 0,
    "the fee row says, in words, that it is already inside the figure",
    included ?? "nothing beside the amount",
  );
  check(
    included === null || included.split(/\s+/).length <= 6,
    "that sentence is six words or fewer (B14 rule 33)",
    included ? `${included.split(/\s+/).length} words` : "n/a",
  );
} else if (cutSide === false) {
  check(
    totalNum !== null && owedNum !== null && feeNum !== null
      && Math.abs(totalNum - (owedNum + feeNum)) < 0.005,
    "BEFORE THE CUT the fee is a quote and the subtotal ADDS it",
    `owed ${owedNum} + fee ${feeNum} = ${totalNum}`,
  );
  check(included === null, "and nothing claims the fee is already owed", included ?? "absent");
} else {
  console.log("  (no disconnection case on this account — no basis to check)");
}

// ── the eight accessibility questions, for the parts a browser can answer ───
console.log(`\n── accessibility (12-governance/22-product-maintenance-process.md §6) ──`);
const headings = await page.$$eval("h1, h2, h3", (ns) =>
  ns.map((n) => `${n.tagName}:${(n.textContent ?? "").trim().slice(0, 40)}`));
console.log(`  headings         ${headings.join(" | ") || "NONE"}`);
const h1s = headings.filter((h) => h.startsWith("H1")).length;
check(h1s === 1, "Q4 · exactly one H1, and the headings run in order", `${h1s} H1`);
const inputs = await page.$$eval("input, select, textarea", (ns) =>
  ns.map((n) => ({
    tag: n.tagName,
    labelled: !!(n.getAttribute("aria-label") || n.id && document.querySelector(`label[for='${n.id}']`)),
  })));
check(
  inputs.every((i) => i.labelled),
  "Q3 · every box you type into has a label attached",
  `${inputs.length} control(s), ${inputs.filter((i) => !i.labelled).length} unlabelled`,
);
// Q1/Q2 — tab through and report where focus lands and whether it is visible.
const stops = [];
for (let i = 0; i < 14; i += 1) {
  await page.keyboard.press("Tab");
  stops.push(
    await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return "body";
      const style = getComputedStyle(el);
      const ring = style.outlineStyle !== "none" || style.boxShadow !== "none";
      return `${el.tagName}${ring ? "" : "(no focus ring)"}:${(el.textContent ?? "").trim().slice(0, 24)}`;
    }),
  );
}
console.log(`  tab stops        ${stops.join(" → ")}`);
check(stops.some((s) => s.startsWith("A") || s.startsWith("BUTTON") || s.startsWith("SELECT")),
  "Q1 · the screen's controls are reachable by keyboard", `${stops.length} stops`);
check(!stops.some((s) => s.includes("(no focus ring)")),
  "Q2 · every stop shows where you are", stops.filter((s) => s.includes("(no focus ring)")).join(", ") || "all visible");
// Q6 — reflow at 320 (WCAG 2.1 AA) and at the agreed 390 target.
for (const width of [320, 390]) {
  await page.setViewportSize({ width, height: 900 });
  await page.waitForTimeout(250);
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check(over <= 1, `Q6 · no sideways scroll at ${width}px`, `${over}px over`);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/cwp-057-${LABEL}-${width}.png`, fullPage: true });
}
await page.setViewportSize({ width: 1280, height: 900 });
const live = await page.$$eval("[aria-live], [role='status'], [role='alert']", (ns) => ns.length);
console.log(`  Q7 · live regions on this screen: ${live}`);

console.log(`\njs errors: ${jsErrors.length}`);
for (const e of jsErrors) console.log(`  · ${e.slice(0, 160)}`);
console.log(`\n${failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`}`);
await browser.close();
process.exit(failures === 0 ? 0 : 2);
