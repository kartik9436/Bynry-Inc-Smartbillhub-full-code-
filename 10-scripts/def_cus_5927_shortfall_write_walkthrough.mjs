// ── Trace ────────────────────────────────────────────────────
// Defects: `DEF-CUS-5927` (critical — step 4's decision could never be recorded)
//          `DEF-CUS-5928` (the heading's bare figure)
// Screens: S20 move-out wizard, steps 3 and 4 (Billing blueprint p112–p114)
// Rules:   CLAUDE.md hard rule 2 (money DISPLAYS to 2 decimals) · hard rule 4
//          (a new row, never an edit) · hard rule 7 (every money action writes
//          `audit_log`) · hard-won law 6 (diff the running app — no gate in this
//          repo reads rendered output)
// ─────────────────────────────────────────────────────
//
// ⚠⚠ **A UNIT TEST CANNOT SEE THIS DEFECT, WHICH IS WHY THIS FILE IS KEPT.**
// Both halves behaved correctly alone: the backend records a decision when the
// figure is stated (`tc16`) and the read states it on every call. The fault was
// that the WRITE and the READ disagreed, and only a clerk pressing the button
// shows that. The suite renders this screen STATICALLY and cannot click it.
//
// ⚠ **IT HAS A BEFORE MODE, ON PURPOSE.** `WALK_EXPECT_OK=0` asserts the OLD
// behaviour — body `{"path":"collect"}`, **409**, and the refusal sentence
// *"Nothing is left unrecovered here…"* printed under `Short by $1,591.85`. Run
// it against a build of the pre-fix code and the before-and-after is
// reproducible rather than remembered. That is what was done on 2026-09-19.
//
// ⚠ **IT WRITES ONE `audit_log` ROW AND NOTHING ELSE.** The shortfall decision
// is RECORDED; no invoice, payment, journal line or move record is created and
// `persisted` is `false` on the wire. The beta's counts are unchanged by a run
// — 78 accounts, 2 move records, 74 payments, 751 journal lines, 92 invoices,
// 1 parked draft — and it deliberately stops at step 4 rather than committing
// the close.
//
// ⚠ **IT NEEDS A BUILT BUNDLE AND THE SERVED ONE IS THE ONE THAT COUNTS.**
// Build, then check the sha256 of the served `/assets/index-*.js` against the
// file you built; nothing on the page says how old the bundle is.
//
//   WALK_BASE       the SPA join (default http://127.0.0.1:8973)
//   WALK_LABEL      a word for the report
//   WALK_EXPECT_OK  1 expects the write to succeed, 0 expects the 409
//   WALK_SHOT       screenshot prefix
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.WALK_BASE || "http://127.0.0.1:8973";
const LABEL = process.env.WALK_LABEL || "after";
const EXPECT_OK = (process.env.WALK_EXPECT_OK || "1") === "1";
const T = "brazosbend";
const ACC = "01a0aff9-6140-7e09-be9e-a3d983503041";
const CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const KILL = setTimeout(() => { console.error("REFUSED: walk exceeded 5 minutes"); process.exit(3); }, 300000);
let pass = 0, fail = 0;
const ok = (what, cond, detail = "") => {
  if (cond) { pass++; console.log(`  ✓ ${what}`); }
  else { fail++; console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`); }
};

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const context = await browser.newContext();
  const page = await context.newPage({ viewport: { width: 1440, height: 1600 } });
  page.setDefaultTimeout(25000);

  // Capture the settle-shortfall POST: its BODY and its STATUS.
  const settles = [];
  page.on("request", (r) => {
    if (r.url().includes("/settle-shortfall") && r.method() === "POST") {
      settles.push({ body: r.postData(), status: null });
    }
  });
  page.on("response", async (r) => {
    if (r.url().includes("/settle-shortfall") && r.request().method() === "POST") {
      const row = settles[settles.length - 1];
      if (row) { row.status = r.status(); try { row.answer = await r.text(); } catch { row.answer = ""; } }
    }
  });

  console.log(`\n═══ ${LABEL}: ${BASE} ═══`);
  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", "dana@brazosbendutilities.com");
  await page.fill("#signin-password", "S3cure!passw0rd");
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ]);

  await page.goto(`${BASE}/${T}/accounts/${ACC}/move-out`, { waitUntil: "networkidle" });

  // ── step 1 → 2 ──────────────────────────────────────────────────────────
  await page.click('button:has-text("Continue")');
  await page.waitForSelector("#moved_out_on");
  await page.fill("#moved_out_on", "2026-09-30");
  await page.click('button:has-text("Continue")');

  // ── step 3 — the money. Wait for the preview and the settlement. ────────
  await page.waitForSelector('[data-move-matrix="subtraction"]', { timeout: 40000 });
  await page.waitForFunction(
    () => document.body.innerText.includes("Short by") &&
          !document.body.innerText.includes("The subtraction has not run yet."),
    { timeout: 40000 },
  );
  const step3 = await page.innerText("body");
  ok("step 3 prices the closing bill and lands on a shortfall",
     /Short by/.test(step3) && /\$1,591\.85/.test(step3));

  await page.click('button:has-text("Continue")');

  // ── step 4 — the shortfall ──────────────────────────────────────────────
  await page.waitForSelector("[data-shortfall-paths]", { timeout: 30000 });
  const head4 = await page.innerText("body");

  // DEF-CUS-5928 — the heading.
  const heading = await page.$eval(
    '[data-step-section="shortfall-headline"] h3', (h) => h.innerText.trim(),
  );
  console.log(`    heading: ${JSON.stringify(heading)}`);
  ok("DEF-CUS-5928 — the heading carries the currency and the separator",
     heading === "What happens to $1,591.85", `read ${JSON.stringify(heading)}`);

  // The SHORT BY cell it sits above, for the comparison the defect is about.
  const cell = await page.$eval('[data-figure="short-by"]', (n) => n.innerText.trim());
  console.log(`    short-by cell: ${JSON.stringify(cell)}`);
  ok("DEF-CUS-5928 — heading and cell spell the same money the same way",
     heading.endsWith(cell), `${JSON.stringify(heading)} vs ${JSON.stringify(cell)}`);

  ok("before the click there is no refusal on screen",
     !head4.includes("Nothing is left unrecovered here"));

  // ── the clerk chooses a path and confirms ───────────────────────────────
  await page.click('[data-shortfall-path="collect"] input[type="radio"]');
  await page.click("[data-shortfall-confirm]");
  await page.waitForFunction(
    () => document.body.innerText.includes("Recorded, with your name on it") ||
          document.body.innerText.includes("Nothing is left unrecovered here"),
    { timeout: 30000 },
  );
  const after = await page.innerText("body");
  const posted = settles[settles.length - 1] || {};
  console.log(`    POST body   : ${posted.body}`);
  console.log(`    POST status : ${posted.status}`);
  if (posted.status !== 200) console.log(`    POST answer : ${(posted.answer || "").slice(0, 260)}`);

  if (EXPECT_OK) {
    ok("DEF-CUS-5927 — the POST carries final_bill and as_of",
       /"final_bill"/.test(posted.body || "") && /"as_of"/.test(posted.body || ""),
       String(posted.body));
    ok("DEF-CUS-5927 — the write is ACCEPTED (200)", posted.status === 200, String(posted.status));
    ok("the screen says the decision is recorded",
       after.includes("Recorded, with your name on it"));
    ok("the contradictory sentence is GONE from the screen",
       !after.includes("Nothing is left unrecovered here"));
  } else {
    ok("BEFORE — the POST carries only the path",
       (posted.body || "") === '{"path":"collect"}', String(posted.body));
    ok("BEFORE — the write is REFUSED 409", posted.status === 409, String(posted.status));
    ok("BEFORE — the contradictory sentence is printed under the figure",
       after.includes("Nothing is left unrecovered here"));
    const i = after.indexOf("Nothing is left unrecovered here");
    if (i > -1) console.log(`    on screen   : …${after.slice(Math.max(0, i - 120), i + 70).replace(/\n+/g, " · ")}`);
  }

  await page.screenshot({ path: `${process.env.WALK_SHOT || "/tmp/walk"}-${LABEL}.png`, fullPage: false });
  await context.close();
} catch (err) {
  fail++;
  console.log(`  ✗ the walk threw — ${err && err.message}`);
} finally {
  if (browser) await browser.close();
  clearTimeout(KILL);
}
console.log(`\n${LABEL}: ${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
