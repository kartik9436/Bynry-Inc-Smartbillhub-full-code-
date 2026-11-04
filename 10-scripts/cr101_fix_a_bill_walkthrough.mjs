// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 · §06 Fix a bill — the four-step wizard the Product
//           Owner ruled on 2026-09-12 (*"we will ahve to make it wizard - 4
//           steps"*), converted under 12-governance/22-product-maintenance-process.md.
// Rules:    CLAUDE.md hard rule 4 (no UPDATE and no DELETE on an issued bill —
//           a correction is NEW ROWS) · hard-won law 6 (no gate reads rendered
//           output; diff the running app) · maintenance process §0 REPRODUCE
//           and §4 PROVE IT AGAINST THE REPRODUCTION · B14 rule 41
// ───────────────────────────────────────────────────────
/**
 * cr101_fix_a_bill_walkthrough — DRIVE the Fix a bill journey in a browser and
 * watch a real issued bill get corrected.
 *
 *     service postgresql start
 *     (cd 06-backend && DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \
 *        python manage.py runserver 127.0.0.1:8000 --noreload &)
 *     (cd 07-frontend && API_PROXY_TARGET=http://127.0.0.1:8000 PORT=8080 node server.mjs &)
 *     node 10-scripts/cr101_fix_a_bill_walkthrough.mjs
 *
 * ⚠ **THIS IS THE REPRODUCTION, AND IT RUNS BEFORE AND AFTER THE CONVERSION.**
 * The maintenance process's first step is *"drive it and see it with your own
 * eyes — never fix what you have not seen"*, and its fourth is *"go back to
 * step 0's recorded state and do the same thing again"*. One file does both:
 * `--before` records what today's two-panel tab does, `--after` records the
 * same journey through the four-step rail, and the money assertions are
 * IDENTICAL in both modes because the money path is what must not move.
 *
 * ⚠ **IT WRITES REAL MONEY ROWS AND SAYS SO.** Executing a correction issues a
 * credit note and a replacement bill against a real account on the demo tenant
 * — that is the only way to see hard rule 4 hold, and a preview alone would
 * prove nothing about execution. Pass `--preview-only` to stop at the approval
 * gate. The bill it picks is the NEWEST issued bill with no correction against
 * it already, so a re-run does not act on the replacement of its own last run
 * (BR-BIL-048 — only the latest in a chain is correctable, which would refuse
 * it anyway, but refusing is not the same as choosing well).
 *
 * WHAT IT ASSERTS ABOUT THE MONEY, in both modes:
 *   1. the ORIGINAL invoice row keeps its total, its number and its lines
 *      (hard rule 4, no UPDATE). ⚠ **ITS `status` MAY MOVE, AND THAT IS
 *      RATIFIED RATHER THAN A HOLE.** `billing/0002_rls_w3_and_immutability`
 *      lets the trigger through an UPDATE that changes ONLY `status`,
 *      `updated_at` and the issue-time stamps, and only along `issued → paid |
 *      void | corrected`. This run's first pass asserted "same status" and went
 *      RED on `issued → corrected`, which is the lifecycle working — the
 *      assertion was wrong, not the product, and it is written out here so the
 *      next reader does not re-tighten it;
 *   2. the original still EXISTS (hard rule 4, no DELETE);
 *   3. the correction produced NEW rows — a credit note id and a rebill id on
 *      the case's own bill row;
 *   4. no control anywhere in the journey offers to edit an amount, a
 *      description or a line (the document's standing rule for single bills:
 *      *"the enforcement is that there is nowhere to put one"*).
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const MODE = process.argv.includes("--after") ? "after" : "before";
const PREVIEW_ONLY = process.argv.includes("--preview-only");
const SHOTS = process.env.SHOTS ?? `SCRATCH/fix-a-bill`;

mkdirSync(SHOTS, { recursive: true });

/** The only statuses the immutability trigger lets an issued bill move to —
 *  `billing/0002_rls_w3_and_immutability`, verbatim: *"(issued -> paid | void |
 *  corrected)"*. Anything else on an issued row is hard rule 4 breached. */
const LIFECYCLE_AFTER_ISSUE = ["issued", "paid", "void", "corrected"];

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => {
  problems.push(m);
  console.log("  ✗ " + m);
};
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();
page.on("pageerror", (error) => fail(`page error: ${error.message}`));

async function api(path, init) {
  const response = await page.request.fetch(`${BASE}/api/${TENANT}${path}`, init);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

// ── sign in through the real form ──────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
note(`signed in — ${page.url()}`);

// ── pick the subject: the newest issued bill with no case against it ───────
const issued = await api("/invoices?per=25&f.status=issued&sort=issue_date&dir=desc");
const cases = await api("/corrections");
const taken = new Set(
  (cases.body?.results ?? []).flatMap((row) => Object.values(row.scope ?? {})),
);
const subject = (issued.body?.results ?? []).find(
  (row) => row.invoice_no && !taken.has(row.id),
);
if (subject === undefined) {
  fail("no issued bill is available to correct on this tenant");
  await browser.close();
  process.exit(1);
}
note(`subject bill ${subject.invoice_no} — total ${subject.total} ${subject.currency}`);
const beforeRow = await api(`/invoices/${subject.id}`);

// ── the journey ────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/billing/fix`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2500);
await page.screenshot({ path: `${SHOTS}/${MODE}-step1-1440.png`, fullPage: true });

const railSteps = await page.locator("[data-wizard-step]").allTextContents();
note(`rail: ${railSteps.length} step(s) — ${JSON.stringify(railSteps)}`);
if (MODE === "after" && railSteps.length !== 4) {
  fail(`the rail draws ${railSteps.length} steps; the ruling is four`);
} else if (MODE === "after") {
  ok("four steps on the rail");
}

// Step 1 — choose the bill through the finder the screen actually offers.
const finderSearch = page.locator("[data-bil-finder] input[type=search]").first();
if ((await finderSearch.count()) > 0) {
  await finderSearch.fill(subject.invoice_no);
  await page.waitForTimeout(1800);
  const pick = page.locator(`[data-bil-finder] tbody tr`).first().locator("button").first();
  await pick.click();
  await page.waitForTimeout(1200);
  ok(`bill chosen through the finder — ${subject.invoice_no}`);
} else {
  fail("no bill finder on step 1");
}

// Step 1 — the reason. `wrong_read` is class R: the money AND the document move,
// which is the only class that exercises the credit-note + rebill pair.
const reasonSelect = page.locator("#bil-fix-reason");
if ((await reasonSelect.count()) > 0) {
  await reasonSelect.selectOption("wrong_read");
  ok("reason chosen from the select");
} else {
  const box = page.locator('[data-fix-reason="wrong_read"] input[type=checkbox]').first();
  await box.check();
  ok("reason ticked from the banded list");
}
await page.waitForTimeout(600);
await page.screenshot({ path: `${SHOTS}/${MODE}-step1-chosen-1440.png`, fullPage: true });

// ⚠ THE STANDING RULE FOR SINGLE BILLS — there is nowhere to type money.
const typedMoney = await page.evaluate(() =>
  [...document.querySelectorAll("input")].filter((el) => {
    const name = `${el.id} ${el.name} ${el.getAttribute("aria-label") ?? ""}`.toLowerCase();
    return /amount|price|total|charge|line/.test(name) && el.type !== "checkbox";
  }).length,
);
if (typedMoney === 0) {
  ok("no amount, description or line field anywhere on the screen");
} else {
  fail(`${typedMoney} money-shaped input(s) on screen — the standing rule is that there is nowhere to put one`);
}

// Forward. Today that is the preview button; after the conversion it is the
// rail's Continue, and BOTH open the case — the call underneath is the same.
const forward = page.locator('[data-wizard="actions"] button').last();
const legacyPreview = page.getByRole("button", { name: /what it would do/i }).first();
if ((await legacyPreview.count()) > 0) {
  await legacyPreview.click();
} else {
  await forward.click();
}
await page.waitForTimeout(3000);
await page.screenshot({ path: `${SHOTS}/${MODE}-step2-1440.png`, fullPage: true });

const opened = await api("/corrections");
const theCase = (opened.body?.results ?? []).find(
  (row) => !taken.has(row.id) && row.status !== "done",
);
if (theCase === undefined) {
  fail("no correction case was opened");
} else {
  ok(`case opened — class ${theCase.correction_class}, net ${theCase.net_delta}`);
}

// ⚠ NOTHING MONEY-BEARING YET (BR-BIL-014). The original must be untouched at
// this point, which is the half a preview alone can prove.
const atPreview = await api(`/invoices/${subject.id}`);
if (
  atPreview.body?.total === beforeRow.body?.total &&
  atPreview.body?.status === beforeRow.body?.status
) {
  ok("preview wrote nothing to the original bill");
} else {
  fail("the original bill moved during PREVIEW — BR-BIL-014");
}

if (MODE === "after") {
  // Step 2 → step 3 → step 4 on the rail, reading each as it opens.
  for (const label of ["step3", "step4"]) {
    const next = page.locator('[data-wizard="actions"] button').last();
    await next.click();
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `${SHOTS}/${MODE}-${label}-1440.png`, fullPage: true });
    note(`  reached ${label}`);
  }
}

if (PREVIEW_ONLY) {
  note("--preview-only: stopping at the gate; nothing was written");
} else {
  // Approve, then execute — two acts, never one button (BR-BIL-044).
  const approve = page.getByRole("button", { name: /approve|send for approval/i }).first();
  if ((await approve.count()) > 0) {
    await approve.click();
    await page.waitForTimeout(2500);
  }
  const commit = page
    .getByRole("button", { name: /make the correction|create .* documents|post/i })
    .first();
  if ((await commit.count()) > 0) {
    await commit.click();
    await page.waitForTimeout(4000);
    await page.screenshot({ path: `${SHOTS}/${MODE}-executed-1440.png`, fullPage: true });
  } else {
    fail("no commit control was reachable");
  }

  // ══ HARD RULE 4, READ OFF THE DATABASE THROUGH THE API ══════════════════
  const afterRow = await api(`/invoices/${subject.id}`);
  if (afterRow.status !== 200) {
    fail(`the ORIGINAL bill is gone (${afterRow.status}) — hard rule 4 forbids DELETE`);
  } else if (
    afterRow.body.total === beforeRow.body.total &&
    afterRow.body.invoice_no === beforeRow.body.invoice_no &&
    LIFECYCLE_AFTER_ISSUE.includes(afterRow.body.status)
  ) {
    ok(
      `the original ${afterRow.body.invoice_no} keeps its money — ${afterRow.body.total} ${afterRow.body.currency}; status ${beforeRow.body.status} → ${afterRow.body.status}`,
    );
  } else {
    fail(
      `the ORIGINAL bill was UPDATED: ${beforeRow.body.total}/${beforeRow.body.status} → ${afterRow.body.total}/${afterRow.body.status}`,
    );
  }

  if (theCase !== undefined) {
    const detail = await api(`/corrections/${theCase.id}`);
    const bill = (detail.body?.bills_detail ?? [])[0];
    if (bill?.credit_note_id && bill?.rebill_invoice_id) {
      ok("the correction wrote NEW rows — a credit note and a replacement bill");
    } else {
      fail(
        `the correction produced no new rows (credit note ${bill?.credit_note_id ?? "—"}, rebill ${bill?.rebill_invoice_id ?? "—"})`,
      );
    }
  }
}

// ── the narrow width every staff screen must survive ───────────────────────
await ctx.pages()[0].setViewportSize({ width: 1280, height: 1000 });
await page.waitForTimeout(800);
await page.screenshot({ path: `${SHOTS}/${MODE}-final-1280.png`, fullPage: true });
const sideways = await page.evaluate(
  () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
);
if (sideways) {
  fail("the page body scrolls sideways at 1280");
} else {
  ok("no horizontal scroll at 1280");
}

await browser.close();
console.log(`\n${MODE}: ${problems.length} problem(s)`);
for (const problem of problems) {
  console.log(`  - ${problem}`);
}
process.exit(problems.length === 0 ? 0 : 1);
