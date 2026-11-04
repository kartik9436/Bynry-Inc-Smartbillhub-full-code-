// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6723 — *"on this screen user is unable to see detail screen
//          of Journal entry - we cannot click on eye."* (PO, v2.351.84)
// Drawing: 05-prototype/07 Finance Blueprint.pdf p020 item 7 (the eye) and
//          p079 gap G3 (why it never opened), read as IMAGES (B14 rule 42).
// Rules:   CLAUDE.md hard-won law 6 — *"diff the running app against the
//          drawing; no gate looks at rendered output"* · hard-won law 2's
//          MIRROR · hard rule 4 (no edit on a posted entry) · B14 rule 31.
// ───────────────────────────────────────────────────────
/**
 * **A PERSON CLICKS THE EYE, IN A REAL BROWSER, AGAINST REAL POSTGRESQL.**
 *
 * ⚠ **THE EYE IS DRIVEN THROUGH THE UI AND THE URL IS NEVER TYPED.** A lane
 * this month produced four byte-identical screenshots of one grouping under
 * four names by driving a control through a parameter the screen does not
 * read. Typing `/finance/journal-entries/<id>` would prove the ROUTE resolves
 * and say nothing about the thing the Product Owner reported, which is that
 * the CONTROL does not work. So this clicks the row action.
 *
 * ⚠ **THE IMAGE IS CAPTURED, NOT `innerText`.** Reading a screen through
 * `innerText` lies about layout: it reports text that is clipped, overlapped or
 * off-screen as present and correct.
 *
 * ⚠ **TWO ENTRIES ARE OPENED, AND THE SECOND IS THE POINT.** Most rows in the
 * Journal show `—` under ENTRY NO. because an OPENING BALANCE is not a document
 * and has no document number. That is the case most likely to break, and hard
 * rule 4 means a number invented on this screen could never be withdrawn.
 *
 * RUN, on your own ports and a database nobody else is seeding:
 *   BASE=http://127.0.0.1:8972 SHOTS=<dir> node 10-scripts/def_led_6723_journal_detail_walkthrough.mjs
 */
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";

const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8972";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? "/tmp/je-shots";

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

console.log("\n── sign in ────────────────────────");
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
ok("signed in");

/** Open the journal, click the eye on the row at `index`, and report. */
async function openEntry(index, label) {
  console.log(`\n── ${label} ────────────────────────`);
  await page.goto(`${BASE}/${TENANT}/finance?view=journal`, {
    waitUntil: "domcontentloaded",
  });
  // ⚠ **WAIT FOR THE TABLE BODY, NOT FOR THE PANEL.** A walk that proceeds on
  // the heading reads the skeleton and reports failures over a correct screen —
  // hard-won law 7's *measuring how far the render had got*.
  await page.waitForSelector("table tbody tr", { timeout: 30000 });
  const row = page.locator("table tbody tr").nth(index);
  const entryNo = (await row.locator("td").first().innerText()).trim();
  const memo = (await row.locator("td").nth(3).innerText()).trim();
  console.log(`    row ${index}: ENTRY NO. "${entryNo}" · memo "${memo}"`);
  writeFileSync(`${SHOTS}/${label}-01-journal.png`, await page.screenshot());

  const eye = row.getByRole("button", { name: "View entry" });
  if ((await eye.count()) === 0) {
    fail("no View entry control on the row");
    return null;
  }
  if (await eye.isDisabled()) {
    fail("the View entry control is DISABLED — this is the defect");
    return null;
  }
  ok("the eye is enabled");
  await eye.click();
  await page.waitForURL((u) => /\/finance\/journal-entries\/[0-9a-f-]+$/.test(u.pathname), {
    timeout: 30000,
  });
  ok(`address: ${new URL(page.url()).pathname}`);
  await page.waitForSelector('[data-testid="journal-entry-lines"] tbody tr', {
    timeout: 30000,
  });
  // The screen id, so this proves the ROUTE resolved AND the right screen opened.
  const screenId = await page
    .locator("[data-screen-id]")
    .first()
    .getAttribute("data-screen-id");
  if (screenId === "S56-detail") ok("opened S56-detail");
  else fail(`opened the wrong screen: ${screenId}`);

  const lines = await page.locator('[data-testid="journal-entry-lines"] tbody tr').count();
  const foot = (await page.locator('[data-testid="journal-entry-foot"]').innerText())
    .replace(/\s+/g, " ")
    .trim();
  console.log(`    lines: ${lines}`);
  console.log(`    footer: ${foot}`);
  writeFileSync(`${SHOTS}/${label}-02-detail.png`, await page.screenshot());

  // Hard rule 4 — nothing on this screen could be saved.
  const boxes = await page.locator('[data-testid="journal-entry-lines"] input').count();
  if (boxes === 0) ok("no editable field anywhere in the lines table");
  else fail(`${boxes} editable field(s) on an immutable entry`);
  return { entryNo, lines, foot };
}

// ROW 0 — the newest posted entry, whatever it is.
await openEntry(0, "entry");

// ⚠ THE `—` CASE. The demo books are opening balances at the top, so row 0 is
// usually one already; this opens a second row so the walk covers two entries
// rather than one, and the printed ENTRY NO. says which case each was.
await openEntry(3, "opening");

console.log(`\nshots in ${SHOTS}`);
if (problems.length > 0) {
  console.log(`\n${problems.length} PROBLEM(S):`);
  for (const p of problems) console.log("  · " + p);
}
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
