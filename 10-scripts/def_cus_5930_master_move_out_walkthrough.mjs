// ── Trace ────────────────────────────────────────────────────
// Defect:  `DEF-CUS-5930` — a master account with OPEN SUB-ACCOUNTS moved out:
//          the account closed, its agreements ended and `MVO-26-0001` was
//          allocated, for a move the drawing forbids.
// Rule:    `BR-CUS-1082` — WARNED at the commit and on step 1 (PO ruling
//          2026-09-20, closing `OQ-CUS-12515` on option (b)). It was a LANE
//          JUDGMENT refusing the move-out for one day; the ratification was
//          asked for and the answer was no.
// Rules:   `BR-CUS-171` (who counts as an open child — the LINK only) ·
//          B14 rule 32 (no rule id in clerk-facing copy) · rule 33 (a fact ≤ 6
//          words, an instruction ≤ 6 per sentence, RATIONALE zero words) ·
//          hard-won law 6 (diff the running app — no gate reads rendered output)
// Screens: S20 move-out wizard, step 1 (blueprint p110)
// ─────────────────────────────────────────────────────
//
// ⚠⚠ **THE SAFETY THIS FILE USED TO CLAIM WAS DESTROYED BY THE VERY RULING IT
// NOW CHECKS, AND THAT IS THE MOST IMPORTANT LINE IN IT.** It used to read:
// *"IT NEVER COMMITS ANYTHING, AND THE BETA IS SAFE BY CONSTRUCTION. The only
// account it posts a move-out for is the MASTER, whose move-out is the thing
// being refused — so the request that would write is the request that
// cannot."* **That was true for exactly one day.** From `2.317.0` the master's
// move-out COMMITS, so running the old version of this script against the beta
// would have closed `AC-2026-00051` — *Ridge Property LLC* — permanently,
// ended its service agreements and allocated a numbered move record that hard
// rule 4 forbids deleting. **A safety property that rests on something being
// refused expires the moment the refusal does**, and nothing anywhere would
// have announced it: the script's checks would simply have started passing for
// the opposite reason.
//
// **SO THE COMMITTING POST IS GONE.** The write half of this rule — that the
// account really closes and the warning really rides the response — is proved
// on `config.settings.pgtest` against a throwaway tenant
// (`tests/test_br_cus_1082_parent_with_open_children.py`, `tc1`), which is
// where a write belongs. What is left here is what only a browser can answer:
// the words on the strip, its TIER, and whether `Continue` moves. The one
// request this file still makes is a **GET** of the close-impact read, to show
// the screen's number came from the server rather than from the markup.
//
// ⚠ **IT READS THE RENDERED STEP, NOT THE URL — AND THE FIRST VERSION OF THIS
// FILE READ THE URL AND WAS A CHECK THAT COULD NOT FAIL.** The wizard opens as
// a modal over the account page and `?step=` does not move in the address bar,
// so *"the URL did not change"* is TRUE of a blocked master and equally true of
// a tenant walking happily to step 2. It passed on the master for the wrong
// reason. What separates them is the heading — `Step 1 of 6 · Find account`
// versus `Step 2 of 6 · Date & final read` — so that is what is read.
//
//   WALK_BASE      the SPA join (default http://127.0.0.1:8992)
//   WALK_MASTER    a master account id WITH open sub-accounts
//   WALK_ORDINARY  an ordinary occupying account id, to prove it is not everyone
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.WALK_BASE || "http://127.0.0.1:8992";
const T = process.env.WALK_TENANT || "brazosbend";
const MASTER = process.env.WALK_MASTER;
const ORDINARY = process.env.WALK_ORDINARY;
const CHROME = process.env.WALK_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOT = process.env.WALK_SHOT || "/tmp/def-cus-5930";

if (!MASTER) { console.error("REFUSED: WALK_MASTER is required"); process.exit(2); }

let pass = 0, fail = 0;
const ok = (what, cond, detail = "") => {
  if (cond) { pass++; console.log(`  ✓ ${what}`); }
  else { fail++; console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`); }
};
const KILL = setTimeout(() => { console.error("REFUSED: walk exceeded 5 minutes"); process.exit(3); }, 300000);

const browser = await chromium.launch({ executablePath: CHROME });
try {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1600 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", "dana@brazosbendutilities.com");
  await page.fill("#signin-password", "S3cure!passw0rd");
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ]);

  const stepOf = async () => {
    const m = (await page.locator("body").innerText()).match(/Step (\d) of 6 · ([^\n]+)/);
    return m ? { n: Number(m[1]), name: m[2].trim() } : { n: 0, name: "??" };
  };
  const openMoveOut = async (id) => {
    await page.goto(`${BASE}/${T}/accounts/${id}/move-out`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
  };

  // ══ THE MASTER · step 1 WARNS and the wizard walks on ════════════════
  await openMoveOut(MASTER);
  await page.screenshot({ path: `${SHOT}-master-step1.png`, fullPage: true });
  const masterHtml = await page.content();
  const masterText = await page.locator("body").innerText();
  const said = masterText.match(/(\d+) sub-accounts? (?:are|is) still open\./);
  ok("step 1 draws the FACT, with the count the settlement measured", Boolean(said),
     masterText.slice(0, 300).replace(/\n/g, " | "));
  if (said) console.log(`      it reads: "${said[0]}"`);
  // ⚠ **THE INSTRUCTION IS ASSERTED AS AN ABSENCE.** *"Close or reassign them
  // first"* told a clerk to do something the product no longer requires, and a
  // catalogue somebody forgot to trim would still render it here while every
  // other check on this page passed.
  ok("and the INSTRUCTION is gone — a fact, not an order",
     !/Close or reassign/i.test(masterText));
  // ⚠ **THE TIER, IN THE DOM RATHER THAN IN THE COLOUR.** It was a
  // `RefusalStrip`: `data-refusal`, `role="alert"`. A warning left inside that
  // wrapper reads as a refusal to a clerk and announces itself as one to a
  // screen reader, whatever the sentence says.
  ok("it is drawn in the WARNING tier, not the refusal tier",
     masterHtml.includes('data-warning="customers-open-sub-accounts"'));
  ok("B14 rule 32 — no rule id reaches the clerk",
     !/BR-CUS-1082|BR-CUS-171|OQ-CUS-12515|B19/.test(masterText));
  // ⚠ **RATIONALE IS ZERO WORDS (B14 rule 33)** — and after this ruling the
  // tempting rationale is the TRANSFER, which must not appear on this screen.
  ok("B14 rule 33 — no RATIONALE on screen, and no mention of a transfer",
     !/measuring against a meter|no account behind it|because/i.test(said ? said[0] : "") &&
     !/transfer|sold the property/i.test(said ? said[0] : ""));

  const mBefore = await stepOf();
  await page.locator('button:has-text("Continue")').last().click();
  await page.waitForTimeout(1800);
  const mAfter = await stepOf();
  // ⚠ **THIS IS THE RULING, AND IT IS THE ASSERTION THAT INVERTED.** It read
  // *"Continue does not advance the master past step 1"* and passed. The clerk
  // may now walk on: the warning is read and the wizard moves.
  ok("Continue ADVANCES the master to step 2 — the clerk may walk past the warning",
     mBefore.n === 1 && mAfter.n === 2, `${mBefore.n} -> ${mAfter.n}`);
  console.log(`      master: step ${mBefore.n} (${mBefore.name}) --Continue--> step ${mAfter.n} (${mAfter.name})`);
  // ⚠ **AND NOTHING ASKED THE CLERK TO ACKNOWLEDGE ANYTHING** — the ruling left
  // that to us and the answer was no: a tick-to-continue is a refusal with an
  // extra click. Asserted, because a later lane adding one would otherwise be
  // adding back the thing the PO removed.
  ok("and no acknowledgement was demanded on the way",
     !/I understand|Confirm that|acknowledge/i.test(masterText));

  // ══ THE SERVER · the COUNT, read-only ════════════════════════════════
  // ⚠ **A GET, AND NEVER THE MOVE-OUT POST.** See the header: the commit now
  // succeeds, so posting it here would close a real account on the beta with
  // no undo. This proves the number on the strip came from the server; that
  // the commit warns is `tc1`'s job, on a throwaway tenant.
  const served = await page.evaluate(async ([tenant, id]) => {
    const res = await fetch(`/api/${tenant}/accounts/${id}/close-impact`, {
      method: "GET", credentials: "include",
    });
    return { status: res.status, body: await res.text() };
  }, [T, MASTER]);
  ok("the close-impact read serves the count the strip drew",
     served.status === 200 && /"open_sub_accounts"\s*:\s*[1-9]/.test(served.body),
     `HTTP ${served.status} ${served.body.slice(0, 200)}`);
  console.log(`      server: HTTP ${served.status} ${served.body.slice(0, 220)}`);

  // ══ AN ORDINARY TENANT · unchanged, which is the false pass killed ════
  if (ORDINARY) {
    await openMoveOut(ORDINARY);
    const tenantText = await page.locator("body").innerText();
    // ⚠ **THE FALSE PASS THIS HALF KILLS, AND THE REVERSAL MADE IT QUIETER.**
    // A warning drawn on every account would make every check above green
    // exactly as a correct one does — and where a wrong REFUSAL stops a clerk
    // and gets reported, a wrong warning is just noise nobody reports.
    ok("an ordinary tenant's step 1 shows no sub-account warning",
       !/sub-accounts? (?:are|is) still open/.test(tenantText) &&
       !(await page.content()).includes('data-warning="customers-open-sub-accounts"'));
    const tBefore = await stepOf();
    await page.locator('button:has-text("Continue")').last().click();
    await page.waitForTimeout(1800);
    const tAfter = await stepOf();
    ok("and it walks on to step 2 exactly as before",
       tBefore.n === 1 && tAfter.n === 2, `${tBefore.n} -> ${tAfter.n}`);
    console.log(`      tenant: step ${tBefore.n} (${tBefore.name}) --Continue--> step ${tAfter.n} (${tAfter.name})`);
    await page.screenshot({ path: `${SHOT}-tenant-step2.png`, fullPage: false });
  }
  console.log(`\n${pass} passed, ${fail} failed`);
} finally {
  clearTimeout(KILL);
  await browser.close();
}
process.exit(fail === 0 ? 0 : 1);
