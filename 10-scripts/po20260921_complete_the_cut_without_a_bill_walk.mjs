// ── Trace ────────────────────────────────────────────────────────────────────
// Rule:     **PO ruling 2026-09-21**, verbatim: *"in single bill we have final
//           bill workflow - so if clark want to complete the bill he can do it
//           from there - we will need to allow clark to complete the cut request
//           later without bill."*
// Walks:    `/{t}/disconnects/{case}` — the case record (blueprint p143) and its
//           `Finish disconnection` dialog.
// Rules:    BR-CUS-107 (`Disconnected`) · BR-CUS-103 (base stops at the cut) ·
//           `DSC-02.4` (a cut is not a close-out) · B14 rules 31, 33, 43 ·
//           CLAUDE.md hard-won law 6 (no gate in this repo reads rendered output)
// Pairs:    `10-scripts/po20260921_disconnect_web_walk.mjs` walks ALL the
//           disconnect screens; this one walks the ONE dialog the ruling moved,
//           end to end, including the destructive commit. Read that file first —
//           if what you need is a screen census rather than this act, it is the
//           tool, not this one.
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠ **THIS IS A PERSON WITH A BROWSER, WHICH IS THE ONLY CHECK IN THIS REPO
// THAT READS RENDERED OUTPUT.** The backend suite proves the DECISION; it cannot
// prove that a clerk can reach it. On 2026-09-21 the decision was reachable only
// through one control that refused, and every backend case was green.
//
// ⚠ **IT WRITES, AND EVERY WRITE IS GATED AND NAMED.**
//   * `CWALK_CUT=1` presses `Mark as cut`. **Destructive and not undoable** —
//     `commit_cut` refuses a second cut by name.
//   * `CWALK_FINISH=1` opens `Finish disconnection` and commits it.
//   * `CWALK_WITHOUT_BILL=1` picks `Complete without it` FIRST, so the commit
//     writes BR-CUS-107's status with no bill. Without it the dialog asks
//     billing, which is the unchanged path.
//   With none set the walk is READ-ONLY and still prints every control.
//
// ⚠ **RUN IT AGAINST A DATABASE YOU OWN.** `DSC-26-0001` and `DSC-26-0002` are
// the first two disconnections this product ever performed and are REAL
// records; `DSC-26-0001` is already damaged (`DEF-CUS-6094`). Clone the
// development database by template and point `DATABASE_URL` at the clone.
//
//   node 10-scripts/po20260921_complete_the_cut_without_a_bill_walk.mjs
//   CWALK_CASE=DSC-26-0005 CWALK_CUT=1 node …
//   CWALK_CASE=DSC-26-0005 CWALK_FINISH=1 CWALK_WITHOUT_BILL=1 node …
//
// ⚠ **`ROOT` IS DERIVED FROM THIS FILE'S OWN PATH** — `DEF-CUS-6028`: a walk
// that hard-codes `/home/user/SMARTBillHub` drives somebody else's bundle.
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = process.env.CWALK_ROOT || path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.CWALK_BASE || "http://127.0.0.1:8967";
const T = process.env.CWALK_TENANT || "brazosbend";
const EMAIL = process.env.CWALK_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.CWALK_PASSWORD || "S3cure!passw0rd";
const CASE = process.env.CWALK_CASE || "DSC-26-0005";
const CHROME = process.env.CWALK_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.CWALK_SHOTS || "/tmp/claude-0/cut8/shots";
const DO_CUT = process.env.CWALK_CUT === "1";
const DO_FINISH = process.env.CWALK_FINISH === "1";
const DO_WITHOUT = process.env.CWALK_WITHOUT_BILL === "1";

console.log(`tree:   ${ROOT}`);
console.log(`app:    ${BASE}/${T}`);
console.log(`case:   ${CASE}`);
console.log(`writes: cut=${DO_CUT} finish=${DO_FINISH} withoutBill=${DO_WITHOUT}\n`);

let pass = 0;
const failures = [];
const httpErrors = [];
const pageErrors = [];
const ok = (what) => { pass += 1; console.log(`  ✓ ${what}`); };
const bad = (what, saw) => { failures.push(`${what} — saw: ${saw}`); console.log(`  ✗ ${what}\n      saw: ${saw}`); };
const is = (cond, what, saw) => (cond ? ok(what) : bad(what, String(saw)));
const bodyText = (p) => p.evaluate(() => document.body.innerText.replace(/\s+/g, " "));

async function signIn(ctx) {
  const p = await ctx.newPage({ viewport: { width: 1440, height: 1800 } });
  p.setDefaultTimeout(25000);
  p.on("pageerror", (e) => pageErrors.push(`PAGEERROR ${e.message}`));
  p.on("response", async (r) => {
    if (r.url().includes("/api/") && r.status() >= 400) {
      httpErrors.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")} ${(await r.text().catch(() => "")).slice(0, 300)}`);
    }
  });
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

const browser = await chromium.launch({ executablePath: CHROME });
try {
  const page = await signIn(await browser.newContext());
  const record = async (shot) => {
    await page.goto(`${BASE}/${T}/disconnects/${CASE.toLowerCase()}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `${SHOTS}/${shot}.png`, fullPage: true });
    return bodyText(page);
  };

  console.log("═══ 1 · THE RECORD, BEFORE ANYTHING ═══");
  let text = await record("00-record");
  is(text.includes(CASE), "the kicker carries the case number", text.slice(0, 160));

  if (DO_CUT) {
    console.log("\n═══ 2 · THE CUT — the destructive commit ═══");
    const button = await page.$('[data-testid="disconnect-record-mark-cut"]');
    if (button === null || (await button.isDisabled())) {
      bad("the cut committed", "`Mark as cut` is absent or greyed");
    } else {
      await button.click();
      await page.waitForTimeout(1500);
      await page.click('button[type="submit"]:has-text("Mark as cut")');
      await page.waitForTimeout(8000);
      text = await record("01-after-cut");
      is(/\bCut\b/.test(text), "the record now reads the case as cut", text.slice(0, 200));
    }
  }

  if (DO_FINISH) {
    console.log("\n═══ 3 · COMPLETING THE CUT REQUEST ═══");
    const door = await page.$('[data-testid="disconnect-record-finish-cut"]');
    is(door !== null, "`Finish disconnection` is offered on a cut whose status was held", "absent");
    if (door !== null) {
      await door.click();
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `${SHOTS}/02-finish-dialog.png`, fullPage: true });
      const dialog = await bodyText(page);
      // ⚠ **THE ONE QUESTION THE RULING ADDED.** Both answers must be on the
      // screen BEFORE the clerk commits: a way out that is only reachable after
      // a failure is a way out most clerks never find.
      is(/Raise it now/i.test(dialog), "the dialog offers `Raise it now`", dialog.slice(-320));
      is(/Complete without it/i.test(dialog), "…and `Complete without it` (PO ruling 2026-09-21)", dialog.slice(-320));
      // ⚠ **AND THE DAYS NOBODY BILLED ARE ON IT.** A clerk about to strand a
      // window reads it first — the ruling's own *"must remain visible"* half.
      is(/Days not billed/i.test(dialog), "…and the days nobody has billed are stated", dialog.slice(-320));

      if (DO_WITHOUT) {
        const picked = await page.evaluate(() => {
          const r = document.querySelector('input[name="disconnect-finish-bill"][value="without"]');
          if (r === null) return null;
          r.click();
          return r.checked;
        });
        is(picked === true, "`Complete without it` can be chosen", String(picked));
        await page.waitForTimeout(600);
        const chosen = await bodyText(page);
        is(/No bill is raised/i.test(chosen), "…and the consequence sentence changes with it", chosen.slice(-260));
        is(/Complete without bill/i.test(chosen), "…and so does the commit's own words", chosen.slice(-260));
      }

      const before = httpErrors.length;
      await page.click('button[type="submit"]');
      await page.waitForTimeout(8000);
      await page.screenshot({ path: `${SHOTS}/03-after-finish.png`, fullPage: true });
      const refused = httpErrors.slice(before).filter((h) => h.includes("disconnect-case/finish"));
      is(refused.length === 0, "the server accepted the completion", refused.join(" || ") || "none");

      // ⚠ **THREE WITNESSES, BECAUSE ANY ONE OF THEM CAN LIE.** The record is
      // re-read from the server rather than believed off the dialog.
      text = await record("04-record-final");
      if (DO_WITHOUT) {
        is(!/This cut is not finished/i.test(text), "the record stops calling the cut unfinished", text.slice(-400));
        is((await page.$('[data-testid="disconnect-record-finish-cut"]')) === null,
           "…and the door is ABSENT, because the act has happened", "still offered");
        // THE HALF THAT MUST NOT BE LOST — the days survive the completion.
        is(/Days not billed/i.test(text),
           "…and the days nobody billed are STILL stated on the record", text.slice(-400));
      }
    }
  }

  console.log(`\n${pass} passed, ${failures.length} failed`);
  for (const f of failures) console.log(`  ✗ ${f}`);
  for (const e of httpErrors) console.log(`  HTTP ${e}`);
  for (const e of pageErrors) console.log(`  ${e}`);
  process.exitCode = failures.length === 0 && pageErrors.length === 0 ? 0 : 1;
} finally {
  await browser.close();
}
