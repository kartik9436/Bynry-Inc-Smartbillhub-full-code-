// ── Trace ──────────────────────────────────────────────
// Task:    Finance blueprint `P2.21` — 2·2 Aging, the view and the report's
//          paging and filters.
// Drawing: 05-prototype/07 Finance Blueprint.pdf p034 (the view's header and
//          the *build over the report* box) · p035 (the wireframe, the five
//          numbered notes and the binding FILTER CRITERIA table) · p036
//          (FIELDS · TABLE CONTROLS · WRITE SURFACES), rendered as IMAGES
//          (B14 rule 42).
// Defect:  `DEF-REP-6607` — the handback this closes.
// Rules:   CLAUDE.md hard-won law 6 — *"diff the running app against the
//          drawing; no gate looks at rendered output"* · hard-won law 2 and
//          its MIRROR (a live screen behind a dead control) · `NFR-3`.
// ───────────────────────────────────────────────────────
/**
 * **A PERSON LOOKING AT THE SHOTS THIS TAKES IS THE ONLY CHECK IN THIS REPO
 * THAT READS RENDERED OUTPUT.** Fourteen backend cases prove the ageing pages,
 * filters and foots; a screenshot of five bands of real money under a working
 * pager is the difference between that and *a finance officer can see who owes
 * what*.
 *
 * ⚠ **IT ASSERTS THE PAGER AGAINST THE SERVER'S OWN COUNT, NOT AGAINST THE
 * ROWS.** A pager that counts the rows it was handed says *1–50 of 50* over a
 * receivable of any size and looks perfectly right — which is the silent
 * truncation `P2.21` exists to remove, one layer up from where it was.
 *
 * RUN:
 *   BASE=http://127.0.0.1:8972 SHOTS=<dir> node 10-scripts/fin_p221_aging_walkthrough.mjs
 *
 * ⚠ **AGAINST A DATABASE NOBODY ELSE IS SEEDING** — `10-scripts/proof-db.sh
 * clone <yours>` — and **on your own ports**. Kill your server by the PID you
 * recorded; matching on a process name kills every lane's.
 */
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8972";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/fin-p221-shots";
/** A service code and a premises id THAT EXIST ON THE DATABASE BEING WALKED.
 *  There are no defaults worth having: a wrong id returns an empty list, which
 *  is indistinguishable from a broken filter — so the premises is REQUIRED and
 *  the walk fails without it rather than reporting a pass it did not earn. */
const SERVICE = process.env.SERVICE ?? "water";
const PREMISES = process.env.PREMISES ?? "";

mkdirSync(SHOTS, { recursive: true });

const problems = [];
const ok = (m) => console.log("  ✓ " + m);
const fail = (m) => {
  problems.push(m);
  console.log("  ✗ " + m);
};

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/opt/pw-browsers/chromium",
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => fail("page error: " + e.message));

/**
 * ⚠⚠ **EVERY `ar_aging` RESPONSE IS CHECKED, AND THIS IS THE HALF THAT WAS
 * MISSING WHEN `DEF-REP-6673` SHIPPED.** The front-end ledger suite is 17
 * files and 191 cases and every one of them was GREEN over a screen whose only
 * read answered **422 VAL-001 field=from** on every request: a test that mounts
 * a component against a mock cannot be refused by a server, so a query object
 * that loses a required parameter is invisible to all 191.
 *
 * So the walk listens to the wire. Any non-2xx from `/reports/ar_aging` fails
 * it, whatever the screen happens to render — which is the question law 7 asks
 * (*what would make this check pass wrongly?*), answered rather than assumed:
 * without this, a filter that silently returned an unfiltered list, or a page
 * that quietly 422'd and left the previous rows on screen, would read as a pass.
 */
const refusals = [];
page.on("response", (r) => {
  if (r.url().includes("/reports/ar_aging") && r.status() >= 300) {
    refusals.push(`${r.status()} ${r.url().slice(r.url().indexOf("/reports/"))}`);
  }
});
function noRefusals(what) {
  if (refusals.length === 0) {
    ok(`${what}: the server accepted every request`);
    return;
  }
  fail(`${what}: the server REFUSED ${refusals.length} request(s) — ${refusals.join(" · ")}`);
  refusals.length = 0;
}

/**
 * The tie-out sentence the screen is showing, or null when it shows none.
 *
 * ⚠ **MATCHED ON THE CATALOGUE'S OWN WORDS, NOT ON THE WORD "foot".** The
 * screen renders `finance.gap.aging_does_not_foot_to_the_ar_control_total`,
 * whose English is *"These bands do not add up to the receivable in the
 * books…"* — the server's code and its two figures stay off the screen (B14
 * rule 31). A first draft grepped for *foot* and found nothing over a screen
 * that was saying exactly the right thing, which would have read as a pass.
 * This walk runs in English; a run in another locale needs the same key's
 * words, which is why the needle is written here once.
 */
async function tieOutSentence() {
  const items = await page.locator(".fin-gap-list li").allInnerTexts();
  return items.find((line) => /add up to the receivable/i.test(line)) ?? null;
}

/**
 * Rows on screen right now AND the filtered set behind them — the numbers this
 * walk reports instead of a test count.
 *
 * ⚠ **BOTH, BECAUSE ONE OF THEM ALONE MISLEADS.** A filter that narrows to 900
 * debtors still shows 50 rows, so a row count alone says *"50"* for the
 * unfiltered list and *"50"* for the filter — identical figures over completely
 * different answers. The footer carries the server's own COUNT over the
 * filtered set, which is the number a finance officer is actually told.
 */
async function rowCount(what) {
  const n = await page.locator("table tbody tr").count();
  const m = (await page.locator("body").innerText()).match(/(\d[\d,]*)[–-](\d[\d,]*) of ([\d,]+)/);
  const total = m === null ? null : Number(m[3].replace(/,/g, ""));
  console.log(
    `    ${what}: ${n} row(s) on screen` + (total === null ? "" : ` · ${total} in the filtered set`),
  );
  return n;
}

async function shot(name) {
  await page.waitForTimeout(250);
  writeFileSync(`${SHOTS}/${name}.png`, await page.screenshot({ fullPage: true }));
  console.log(`    shot ${name}.png`);
}

console.log("\n── sign in ────────────────────────");
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
ok("signed in");

// ══════════════════════════════════════════════════════════════════════════
// THE DOOR — p035's DOORS row: *"Two — the Aging view · the Dashboard aging
// panel, which today leads nowhere in Finance"*
// ══════════════════════════════════════════════════════════════════════════
console.log("\n── the door ───────────────────────");
await page.goto(`${BASE}/${TENANT}/finance/revenue`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1500);
const agingTab = page.getByRole("button", { name: /^Aging$/ }).first();
if ((await agingTab.count()) > 0) {
  await agingTab.click();
  await page.waitForTimeout(1500);
  if (page.url().includes("view=aging")) ok("the view strip's Aging opens ?view=aging");
  else fail(`Aging did not reach the view: ${page.url()}`);
} else {
  fail("no Aging control on the view strip");
  await page.goto(`${BASE}/${TENANT}/finance/revenue?view=aging`, {
    waitUntil: "domcontentloaded",
  });
}

// ══════════════════════════════════════════════════════════════════════════
// p036's FIELDS row — *"Account · Customer · Current · 1–30 · 31–60 · 61–90 ·
// 90+ · Total"*, and `BR-REP-030`'s FIVE bands
// ══════════════════════════════════════════════════════════════════════════
console.log("\n── the table ──────────────────────");
// ⚠ **THE WAIT IS CAUGHT AND REPORTED, NOT THROWN.** The first version let
// `waitForSelector` time out, so a screen whose read was REFUSED crashed the
// walk with *"waiting for locator('table tbody tr')"* — a stack trace about a
// selector, over a server that had said exactly what was wrong. A check whose
// output cannot tell a reader pass from fail is worse than no check (law 7).
let tableArrived = true;
try {
  await page.waitForSelector("table tbody tr", { timeout: 30000 });
} catch {
  tableArrived = false;
  const shown = (await page.locator("body").innerText()).replace(/\s+/g, " ").slice(0, 200);
  fail(`no rows after 30s. The screen says: "${shown}"`);
}
noRefusals("the unfiltered view");
const unfiltered = tableArrived ? await rowCount("no filter") : 0;
// ⚠ **THE SERVER'S REFUSALS MUST REACH THE SCREEN.** `GET /reports/ar_aging`
// attaches every absence it found — the unbuilt opening buckets, an un-aged
// bill, and the tie-out. A view that renders none of them shows a receivable
// the report itself is calling short, with nothing on the page to say so.
const gapsShown = await page.locator(".fin-gap-list li").count();
if (gapsShown > 0) ok(`the server's ${gapsShown} stated absence(s) are ON the screen`);
else fail("the screen renders NONE of the report's stated absences");
const unfilteredTieOut = await tieOutSentence();
if (unfilteredTieOut !== null) {
  console.log(`    tie-out: "${unfilteredTieOut.slice(0, 130)}…"`);
}
await shot("aging-01-view");
if (!tableArrived) {
  console.log("\n── stopping: the list never loaded ──");
  await browser.close();
  console.log(`\n${problems.length} problem(s):`);
  for (const p of problems) console.log("  · " + p);
  process.exit(1);
}
// ⚠ **THE HEADER TEXT IS MATCHED AS A SUBSTRING AND THE NEEDLE IS ESCAPED.**
// The first run of this file built `new RegExp("^" + column + "$")`, which
// turns `90+` into *nine followed by one or more zeros* and anchors `Total`
// against a header that reads `TOTAL ▾` once it carries a sort arrow. It
// reported two columns MISSING over a screen where both were plainly on
// display — hard-won law 7's *looking at the wrong thing*, in a test's own
// needle.
for (const column of ["Account", "Customer", "Current", "1–30", "31–60", "61–90", "90+", "Total"]) {
  const seen = await page.locator("table thead th", { hasText: column }).count();
  if (seen > 0) ok(`column present: ${column}`);
  else fail(`column MISSING: ${column}`);
}

// ⚠ **THE HEADING AND THE AS-OF ARE ONE FACT EACH** (B14 rule 33).
for (const text of ["Who owes you"]) {
  if ((await page.getByText(text, { exact: true }).count()) > 0) ok(`copy present: ${text}`);
  else fail(`copy MISSING: ${text}`);
}
if ((await page.getByText(/^As of /).count()) > 0) ok("the as-of date is stated");
else fail("no as-of date on the view — a receivable with no date is unlabelled");

// ══════════════════════════════════════════════════════════════════════════
// `NFR-3` — THE PAGER, AGAINST THE SERVER'S COUNT AND NOT THE ROWS
// ══════════════════════════════════════════════════════════════════════════
console.log("\n── the pager ──────────────────────");
const served = await page.locator("table tbody tr").count();
const footer = (await page.locator("body").innerText()).match(/(\d[\d,]*)[–-](\d[\d,]*) of ([\d,]+)/);
// ⚠ **A TENANT SMALLER THAN ONE PAGE CANNOT PROVE PAGING, AND SAYING SO IS THE
// WHOLE POINT.** The seeded demo has 30 debtors, so `1–30 of 30` is CORRECT and
// an assertion that the total exceeds the rows would fail over a perfectly good
// screen — and a walk that cries wolf on a fixture is a walk the next lane
// learns to ignore. It is reported as NOT PROVED, never as a pass: a declared
// blind spot with no number beside it is indistinguishable from an empty one
// (law 7). Run it against a tenant with more than 50 debtors to prove paging.
let pagingProvable = false;
if (footer === null) {
  fail("no pagination footer — the list cannot say how big it is");
} else {
  const total = Number(footer[3].replace(/,/g, ""));
  console.log(`    footer reads ${footer[0]} · ${served} rows on screen`);
  if (total > served) {
    pagingProvable = true;
    ok(`the pager counts the WHOLE set (${total}) and not the page (${served})`);
  } else {
    console.log(
      `  ⓘ NOT PROVED: this tenant has ${total} debtor(s), which is one page. ` +
        "Paging is not exercised here — run against a tenant with more than 50.",
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════
// THE TILES MUST NOT MOVE WHEN A PAGE DOES (`DEF-REP-6607`'s own trap)
// ══════════════════════════════════════════════════════════════════════════
console.log("\n── page two ───────────────────────");
const nextButton = page.getByRole("button", { name: /next/i }).first();
if (!pagingProvable) {
  console.log("  ⓘ SKIPPED: one page of debtors — see the note above.");
} else if ((await nextButton.count()) > 0 && (await nextButton.isEnabled())) {
  const before = await page.locator("table tbody tr").first().innerText();
  await nextButton.click();
  await page.waitForTimeout(2000);
  const after = await page.locator("table tbody tr").first().innerText();
  if (before !== after) ok("page two serves different rows");
  else fail("page two serves the same first row — the page is not being cut");
  await rowCount("page 2");
  noRefusals("page two");
  await shot("aging-02-page-two");
  if (page.url().includes("page=2")) ok("the page rides in the URL (BR-SHL-011)");
  else fail("the page is not in the URL — this view cannot be shared");
} else {
  fail("no enabled next-page control — cannot prove the pager works");
}

// ══════════════════════════════════════════════════════════════════════════
// p035's CRITERIA — search, band, service
// ══════════════════════════════════════════════════════════════════════════
console.log("\n── the criteria ───────────────────");
await page.goto(`${BASE}/${TENANT}/finance/revenue?view=aging`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("table tbody tr", { timeout: 30000 });
const box = page.getByPlaceholder(/Search account or customer/i).first();
if ((await box.count()) > 0) {
  ok("the search box names what it matches (B14 rule 19)");
  const firstAccount = (await page.locator("table tbody tr td").first().innerText()).trim();
  await box.fill(firstAccount);
  await page.waitForTimeout(2500);
  const narrowed = await rowCount(`q=${firstAccount}`);
  noRefusals("the search box");
  if (narrowed > 0 && narrowed < served) ok(`search narrows the list: ${served} → ${narrowed}`);
  else fail(`search did not narrow the list (${served} → ${narrowed})`);
  // ⚠⚠ **THE ASSERTION THE WHOLE TASK TURNS ON, AND THE FIRST VERSION OF IT
  // COULD NOT FAIL.** It read *"if the page says 'does not foot', fail"* — and
  // passed for the wrong reason, because the view rendered the server's
  // refusals nowhere at all. A check that cannot fail is worse than none.
  //
  // What is asserted now is the PROPERTY: the tie-out sentence, wherever the
  // books happen to stand, is the SAME sentence filtered and unfiltered — it
  // is a fact about the general ledger and never about the search box. On the
  // seeded utility the books genuinely do not foot (the ageing is bill-based
  // and the control carries opening balances nobody has imported), so the
  // sentence is present in both and must quote the same figure in both.
  const searchedTieOut = await tieOutSentence();
  if (searchedTieOut === null && unfilteredTieOut === null) {
    ok("the books foot, and neither view claims otherwise");
  } else if (searchedTieOut === unfilteredTieOut) {
    ok("the tie-out sentence is IDENTICAL filtered and unfiltered");
  } else {
    fail(
      "the tie-out MOVED when the list was filtered — the screen is reporting " +
        `the books against a filtered total. unfiltered: "${unfilteredTieOut}" · ` +
        `searched: "${searchedTieOut}"`,
    );
  }
  await shot("aging-03-searched");
} else {
  fail("no search box on the Aging view");
}

// ⚠ **ALL FIVE BANDS, AND THE TEST IS THAT THEY DISAGREE.** Asking for ONE
// band and finding rows proves nothing: a filter the server ignores returns the
// whole list and reads as a pass. A band that is legitimately empty on this
// fixture (the demo has nothing over 90 days) is not a defect either. So the
// walk asks for every band, prints each count, and asserts that the five do not
// all come back the same — which a filter doing nothing cannot satisfy.
console.log("\n── the band chip ──────────────────");
const bandCounts = {};
for (const band of ["current", "1-30", "31-60", "61-90", "90+"]) {
  await page.goto(
    `${BASE}/${TENANT}/finance/revenue?view=aging&f.band=${encodeURIComponent(band)}`,
    { waitUntil: "domcontentloaded" },
  );
  await page.waitForTimeout(2200);
  bandCounts[band] = await rowCount(`f.band=${band}`);
  noRefusals(`the ${band} band`);
}
const distinct = new Set(Object.values(bandCounts));
if (distinct.size > 1) {
  ok(`the five bands serve different sets: ${JSON.stringify(bandCounts)}`);
} else {
  fail(
    `every band returned the same count (${JSON.stringify(bandCounts)}) — ` +
      "a filter the server ignores looks exactly like this",
  );
}
await shot("aging-04-bands");

// ⚠ **THE TWO CRITERIA THE FIRST VERSION OF THIS WALK NEVER EXERCISED.**
// `f.service` and `f.premises` were served, typed and unit-tested and had never
// been sent to a running server — which is exactly the state `f.from` was in
// when it shipped broken. Both are driven through the URL because that is how a
// saved link arrives, and the screen reads both on mount (`BR-SHL-011`).
console.log("\n── the service criterion ──────────");
await page.goto(`${BASE}/${TENANT}/finance/revenue?view=aging&f.service=${SERVICE}`, {
  waitUntil: "domcontentloaded",
});
await page.waitForTimeout(3000);
const byService = await rowCount(`f.service=${SERVICE}`);
noRefusals("the service filter");
if (byService > 0) ok(`the service filter serves ${byService} debtor(s)`);
else fail("the service filter serves nothing — it is either broken or the fixture has no such bills");
await shot("aging-05-service");

console.log("\n── the property criterion ─────────");
if (PREMISES === "") {
  fail("no PREMISES id given — the property criterion was NOT exercised against a server");
} else {
  await page.goto(`${BASE}/${TENANT}/finance/revenue?view=aging&f.premises=${PREMISES}`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForTimeout(3000);
  const byPremises = await rowCount(`f.premises=${PREMISES.slice(0, 8)}…`);
  noRefusals("the property filter");
  if (byPremises > 0 && byPremises < unfiltered) {
    ok(`the property filter narrows to ${byPremises} debtor(s) of ${unfiltered}`);
  } else {
    fail(`the property filter did not narrow the list (${unfiltered} → ${byPremises})`);
  }
  await shot("aging-06-property");
}

// ⚠ **AS-OF IS THE FIFTH CRITERION AND IT IS THE PAGE'S PERIOD, NOT A CONTROL
// ON THIS VIEW.** It is exercised by the request itself — every call above
// carried it — and the screen states it, which the copy check above asserts.

console.log("\n── done ───────────────────────────");
await browser.close();
if (problems.length > 0) {
  console.log(`\n${problems.length} problem(s):`);
  for (const p of problems) console.log("  · " + p);
  process.exit(1);
}
console.log("\nno problems.");

// ── Lifecycle ─────────────────────────────────────────────
// packet: Finance blueprint `P2.21` (p034–p036) · `DEF-REP-6607`
// generated: 2026-09-24 by lane FIN-AGING
// exceptions: (1) it photographs the VIEWPORT; a screen taller than 1100px
//   loses its lower half and the shots are named so a reader can tell · (2) it
//   does not assert the money FIGURES — `tests/test_fin_p221_aging_page.py`
//   owns those, and a walk that re-asserted them would be a second, weaker
//   implementation of the same arithmetic
// ──────────────────────────────────────────────────────────
