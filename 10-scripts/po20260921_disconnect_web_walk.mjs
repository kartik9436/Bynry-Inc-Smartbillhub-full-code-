// ── Trace ────────────────────────────────────────────────────────────────────
// Ask:      PO, 2026-09-21, verbatim: *"can you do end to end web walk for
//           diconnect - all screens - create disocnenct request, view it, list
//           view filter, search etc, and then complete the request and see it
//           does what it says - disocnnect mean account status mter, assets
//           status etc. anything else what we have to do"*.
// Walks:    `/{t}/disconnects/new` (the five-step wizard, DSC-02) ·
//           `/{t}/disconnects/{case}` (the case record, blueprint p143) ·
//           `/{t}/accounts?tab=disconnects` (the register, ACC-01)
// Rules:    BR-CUS-039 (no cut before tier 3 + proof) · BR-CUS-100 · BR-CUS-103
//           (base stops at the cut) · BR-CUS-104 (the fee is owed AT the cut) ·
//           BR-CUS-107 (`Disconnected`) · BR-SHL-025 (a refused control renders
//           disabled WITH ITS REASON) · B14 rules 6, 31, 33, 40 ·
//           CLAUDE.md hard-won laws 2, 6, 7
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠ **THIS IS A PERSON WITH A BROWSER, WHICH IS THE ONLY CHECK IN THIS REPO
// THAT READS RENDERED OUTPUT** (hard-won law 6). Every assertion below is one a
// unit test cannot make: it drives the SHIPPED bundle through a real router, a
// real query client, a real API and a real PostgreSQL with RLS on.
//
// ⚠ **`ROOT` IS DERIVED FROM THIS FILE'S OWN PATH AND IS PRINTED** —
// `DEF-CUS-6028`: a walk that hard-codes `/home/user/SMARTBillHub` drives YOUR
// bundle and reads the SHARED checkout's Django, which is on somebody else's
// branch, and nothing says so.
//
// ⚠ **IT WRITES, AND THE WRITES ARE GATED AND NAMED.**
//   * `DWALK_SCHEDULE=1` presses the wizard's Complete. That RE-SCHEDULES an
//     existing tier-3 case (services, reason, deposit, date) and records a
//     proof of service. Safe to repeat **ON A CASE THAT HAS NOT BEEN CUT**.
//     ⛔ **IT WAS NOT SAFE ON A CUT CASE AND THIS LINE SAID IT WAS —
//     `DEF-CUS-6062`.** Re-scheduling used to move a `cut` case back to
//     `scheduled`, which re-opened `Mark as cut` on a household already
//     disconnected; a run of this walk with both flags set then charged
//     `A-11340` the reconnection fee a SECOND time on 2026-09-20, in an issued
//     invoice hard rule 4 makes permanent. `schedule_cut` now refuses a case
//     that carries a `cut_on` (422, `already_cut`), so this walk reports the
//     refusal instead of performing it — and the DEFAULT case below,
//     `DSC-26-0001`, is one of the two that are already CUT.
//   * `DWALK_CUT=1` presses `Mark as cut`. **That is the destructive commit and
//     it cannot be undone** — `commit_cut` refuses a second cut by name. Run it
//     once, against a case you meant.
//   With neither set the walk is READ-ONLY and still exercises every screen.
//
// ⚠ **THE ROW COUNTS ARE NOT IN HERE.** They are
// `10-scripts/po20260921_disconnect_walk_readback.py`, which reads the database
// with `app.tenant_id` set inside a transaction. A screen cannot prove what a
// cut wrote, and a walk that asserted it from the page would be asserting the
// page back to itself.
//
//   node 10-scripts/po20260921_disconnect_web_walk.mjs
//   DWALK_SCHEDULE=1 DWALK_CASE=<a case that is NOT cut> DWALK_ACCT=<its account> node …
//   DWALK_CUT=1 node …
//   ⚠ The second line named `DSC-26-0001` / `A-11340` until 2026-09-20. That
//   case is CUT, and the example is how a reader reaches for the flag.
//
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.DWALK_BASE || "http://127.0.0.1:8967";
const T = process.env.DWALK_TENANT || "brazosbend";
const EMAIL = process.env.DWALK_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.DWALK_PASSWORD || "S3cure!passw0rd";
const ACCT = process.env.DWALK_ACCT || "A-11340";
const CASE = process.env.DWALK_CASE || "DSC-26-0001";
const CUT_ON = process.env.DWALK_CUT_ON || "2026-09-20";
const CHROME = process.env.DWALK_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.DWALK_SHOTS || "/tmp/claude-0/dwalk-shots";
const DO_SCHEDULE = process.env.DWALK_SCHEDULE === "1";
const DO_CUT = process.env.DWALK_CUT === "1";

console.log(`tree:   ${ROOT}`);
console.log(`app:    ${BASE}/${T}`);
console.log(`case:   ${CASE} on ${ACCT}`);
console.log(`writes: schedule=${DO_SCHEDULE} cut=${DO_CUT}\n`);

let pass = 0;
const failures = [];
const pageErrors = [];
const httpErrors = [];
function ok(what) { pass += 1; console.log(`  ✓ ${what}`); }
function bad(what, saw) { failures.push(`${what} — saw: ${saw}`); console.log(`  ✗ ${what}\n      saw: ${saw}`); }
function is(cond, what, saw) { cond ? ok(what) : bad(what, String(saw)); }

async function signIn(ctx, width) {
  const p = await ctx.newPage({ viewport: { width, height: 1800 } });
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
const flat = (s) => s.replace(/\s+/g, " ");
const bodyText = (p) => p.evaluate(() => document.body.innerText.replace(/\s+/g, " "));

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext();
  const page = await signIn(ctx, 1440);

  // ══════════════════════════════════════════════════════════════════════════
  // 1 · THE WIZARD — five steps, and every control PRESSED
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **PRESSED, NOT RENDERED.** The PO found a step-4 break by pressing a tick
  // that 39 green tests had rendered without pressing.
  console.log("═══ 1 · THE WIZARD · /disconnects/new ═══");
  await page.goto(`${BASE}/${T}/disconnects/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${SHOTS}/w1-step1-empty.png`, fullPage: true });

  let text = await bodyText(page);
  is(/Step 1 of 5/.test(text), "it opens on step 1 of five", text.slice(0, 120));
  is(/nothing is cut until the scheduled date/i.test(text),
     "the footer promise is on the step", text.slice(0, 200));

  console.log("\n1a · THE TWO ACTIONS, AND NO THIRD (PO: `this si correct`)");
  const wizardActions = await page.evaluate(() => {
    const foot = document.querySelector("footer, [data-wizard-actions]") ?? document.body;
    return [...foot.querySelectorAll("button")]
      .map((b) => b.textContent.replace(/\s+/g, " ").trim())
      .filter((t) => t.length > 0 && t.length < 40);
  });
  is(wizardActions.includes("Park"), "`Park` is offered", wizardActions.join(" | "));
  is(!wizardActions.some((b) => /Save\s*&\s*exit/i.test(b)),
     "`Save & exit` is gone — it and Park were two names for one act",
     wizardActions.join(" | "));

  console.log("\n1b · STEP 1 — the account is a SEARCH, never an id (DEF-732)");
  await page.fill("#dsc_account_q", ACCT);
  await page.waitForTimeout(2500);
  const matches = await page.$$eval("#dsc_account option", (os) => os.map((o) => o.textContent.trim()));
  is(matches.some((m) => m.includes(ACCT)), `typing \`${ACCT}\` finds the account`, matches.join(" | "));
  await page.selectOption("#dsc_account", { index: 1 });
  await page.waitForTimeout(2500);
  text = await bodyText(page);
  is(/Balance \$/.test(text), "picking it draws the customer and the money", text.slice(0, 200));
  is(!/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/i.test(text),
     "no database id is the visible value of any field (B14 rule 31)",
     (text.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}[^ ]*/i) ?? ["none"])[0]);

  console.log("\n1c · THE FIVE REASONS — and which of them the SERVER accepts");
  // ⛔ `DEF-CUS-6023` — the screen sent `tampering`/`abandoned` and the server
  // and a DB constraint require `tampering_or_theft`/`premises_abandoned`, so
  // two of the five reasons could never commit. The walk asserts the VALUES the
  // option carries, because that is the thing that was wrong; a label check
  // passed on the defect.
  const reasonValues = await page.$$eval("#dsc_reason option", (os) => os.map((o) => o.value).filter((v) => v !== ""));
  is(reasonValues.length === 5, "five reasons are offered", reasonValues.join(","));
  for (const wanted of ["non_payment", "unsafe_installation", "tampering_or_theft", "premises_abandoned", "customer_asked"]) {
    is(reasonValues.includes(wanted), `the reason \`${wanted}\` is the value the server accepts`, reasonValues.join(","));
  }
  await page.selectOption("#dsc_reason", "non_payment").catch(() => undefined);
  await page.waitForTimeout(400);

  console.log("\n1d · ONE DECISION PER SERVICE — and the restrictor is refused, not hidden");
  const treatments = await page.evaluate(() => ({
    full: document.querySelectorAll('[data-segment="full_disconnection"]').length,
    restrictor: [...document.querySelectorAll('[data-segment="restrictor"]')].map((b) => b.disabled),
    note: document.querySelector('[data-restrictor="unbuildable"]')?.textContent.trim().slice(0, 60) ?? null,
  }));
  is(treatments.full >= 1, "every readable service gets its own treatment control", JSON.stringify(treatments));
  is(treatments.restrictor.length > 0 && treatments.restrictor.every((d) => d === true),
     "`Restrictor / limiter` is DISABLED rather than absent (BR-SHL-025)", JSON.stringify(treatments));
  is(treatments.note !== null, "…and the reason is VISIBLE TEXT under the table", String(treatments.note));
  for (const b of await page.$$('[data-segment="full_disconnection"]')) { await b.click(); await page.waitForTimeout(200); }

  console.log("\n1e · STEP 2 — PROTECTIONS, which this product cannot clear");
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SHOTS}/w2-step2.png`, fullPage: true });
  text = await bodyText(page);
  is(/Step 2 of 5/.test(text), "step 2 is reached", text.slice(0, 120));
  is(/no summary, because a summary would be a clearance nobody computed/i.test(text),
     "it refuses to summarise ten checks it performs three of", text.slice(0, 300));
  const protectionRows = await page.$$eval("table tbody tr", (rs) => rs.length);
  is(protectionRows >= 10, "all ten questions are listed", String(protectionRows));
  // ⚠ **THE TWO TICKS ARE PRESSED, NOT LOOKED AT.** They are live writes
  // (`record_protection`, `stop_by_hand`) and this walk must NOT fire them, so
  // it presses them with their REQUIRED FIELDS EMPTY and asserts the screen
  // refuses rather than posting. A tick nobody presses is how DEF-CUS-6006 hid.
  const beforePress = await bodyText(page);
  await page.click('button:has-text("Record it")').catch(() => undefined);
  await page.waitForTimeout(1200);
  const afterRecord = await bodyText(page);
  is(afterRecord !== beforePress || /Fill in|required|Pick/i.test(afterRecord),
     "`Record it ✓` pressed with no dates refuses instead of writing", afterRecord.slice(0, 200));
  await page.click('button:has-text("Stop it")').catch(() => undefined);
  await page.waitForTimeout(1200);
  is(/Step 2 of 5/.test(await bodyText(page)), "`Stop it ✓` pressed with no reason keeps the clerk on step 2", "left the step");

  console.log("\n1f · STEP 3 — the ladder, the proof and the date");
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2000);
  text = await bodyText(page);
  is(/Step 3 of 5/.test(text), "step 3 is reached", text.slice(0, 120));
  is(/Serve it outside, then record the proof\./i.test(text),
     "it says plainly that the product cannot send certified mail", text.slice(0, 300));
  const channelBoxes = await page.$$eval('input[id^="dsc_channel_"]', (bs) => bs.map((b) => b.disabled));
  is(channelBoxes.length > 0 && channelBoxes.every((d) => d === true),
     "every send channel is disabled — nothing here delivers a notice", JSON.stringify(channelBoxes));
  is(/No proof, no cut/i.test(text), "`No proof, no cut` is on the step", "absent");

  // ⚠ **THE EARLIEST LAWFUL DATE IS SHOWN AND AN EARLIER ONE IS WARNED, NOT
  // REFUSED** — `DSC-02.3`. Both halves are asserted, because a screen that
  // silently accepted an early date would look identical.
  // ⚠ **THE PROOF FORM IS ONLY DRAWN WHEN A NOTICE IS STILL UNPROVED**, so the
  // walk asks whether it is there rather than assuming it, and asserts the
  // OTHER half when it is not. A selector that silently matches nothing is how
  // a cleanup step no-opped on 2026-09-20 and reported success.
  const proofForm = await page.$("#dsc_proof_channel");
  if (proofForm !== null) {
    await page.selectOption("#dsc_proof_channel", "certified_mail");
    await page.fill("#dsc_proof_reference", process.env.DWALK_PROOF_REF || "RW-DWALK-0001");
    await page.fill("#dsc_proof_served_on", "2026-09-18");
    await page.fill("#dsc_proof_signed_on", "2026-09-19");
    ok("an unproved notice draws its proof-of-service form");
  } else {
    is(/every notice|all .*proved|nothing left to prove|No notice is waiting/i.test(await bodyText(page)),
       "with every notice proved, the step says so instead of drawing an empty form",
       (await bodyText(page)).slice(0, 400));
  }
  await page.fill("#dsc_cut_on", CUT_ON);
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${SHOTS}/w3-step3.png`, fullPage: true });
  text = await bodyText(page);
  is(/Earliest lawful cut/i.test(text), "the earliest lawful cut is computed and shown", "absent");
  const earliest = (text.match(/Earliest lawful cut:\s*([0-9/]+)/) ?? [])[1] ?? null;
  is(earliest !== null, "…with a date on it", String(earliest));
  is(/This date is before the earliest lawful cut/i.test(text) === (CUT_ON < "2026-09-22"),
     "an early date is WARNED about and still allowed", text.slice(text.indexOf("Earliest"), text.indexOf("Earliest") + 200));

  console.log("\n1g · STEP 4 — the fees, from the tenant's own charge codes");
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2200);
  await page.screenshot({ path: `${SHOTS}/w4-step4.png`, fullPage: true });
  text = await bodyText(page);
  is(/Step 4 of 5/.test(text), "step 4 is reached", text.slice(0, 120));
  is(/Stop the base and standing charges at the cut/i.test(text),
     "BR-CUS-103 is the sentence on the screen, not the prototype's opposite", text.slice(0, 300));
  // ⛔ THE FEE. The PO ruled it is $75.00 (2026-09-21). Until the charge code
  // agrees with the seed the row states its absence; this walk REPORTS which of
  // the two it saw rather than asserting one, because both are true findings on
  // different days and a walk that asserted the broken one would go red on the
  // fix.
  const feeShown = (text.match(/Reconnection fee\s*\$?([0-9,]+\.[0-9]{2})/) ?? [])[1] ?? null;
  console.log(`      → the reconnection fee this screen shows: ${feeShown === null ? "NO FIGURE (the charge code does not resolve)" : "$" + feeShown}`);
  is(feeShown === null || feeShown === "75.00",
     "the fee is either $75.00 or an honest absence — never another number", String(feeShown));
  const deposit = await page.evaluate(() => [...document.querySelectorAll("button")]
    .map((b) => b.textContent.trim()).filter((t) => /Hold it|Apply it against/i.test(t)));
  is(deposit.length === 2, "the deposit offers exactly the two dispositions the rule has", deposit.join(" | "));
  await page.click('button:has-text("Hold it")').catch(() => undefined);
  await page.waitForTimeout(500);

  console.log("\n1h · STEP 5 — the review, and the one commit");
  await page.click('button:has-text("Continue")');
  await page.waitForTimeout(2200);
  await page.screenshot({ path: `${SHOTS}/w5-step5.png`, fullPage: true });
  text = await bodyText(page);
  is(/Step 5 of 5/.test(text), "step 5 is reached", text.slice(0, 120));
  is(/Services cut Electric · Water|Services cut/.test(text), "the review names the services chosen", text.slice(0, 200));
  // ⚠ **A CODE ON A REVIEW SCREEN IS A CODE A CLERK READS.** B14 rule 31 bans a
  // database id; this asks the neighbouring question — is the REASON and the
  // DEPOSIT shown in the clerk's words or in the server's?
  const rawCodes = ["non_payment", "unsafe_installation", "tampering_or_theft", "premises_abandoned",
                    "customer_asked", "held", "applied_against_arrear", "full_disconnection"]
    .filter((c) => new RegExp(`\\b${c}\\b`).test(text));
  is(rawCodes.length === 0, "the review reads in the clerk's words, never in the server's codes", rawCodes.join(", "));
  const commit = await page.evaluate(() => {
    const b = [...document.querySelectorAll("button")].find((n) => /Schedule the disconnection/i.test(n.textContent));
    return b === undefined ? null : { text: b.textContent.trim(), disabled: b.disabled };
  });
  is(commit !== null, "the one commit is `Schedule the disconnection ✓`", JSON.stringify(commit));

  if (DO_SCHEDULE) {
    console.log("\n1i · COMPLETE — and it SCHEDULES, it never cuts");
    await page.click('button:has-text("Schedule the disconnection")');
    await page.waitForTimeout(4000);
    await page.screenshot({ path: `${SHOTS}/w6-done.png`, fullPage: true });
    text = await bodyText(page);
    is(/The disconnection is scheduled/i.test(text), "the done panel says it is scheduled", text.slice(-400));
    is(/Nothing has been cut/i.test(text), "…and states plainly that nothing has been cut", text.slice(-400));
    is(new RegExp(CUT_ON.replace(/-/g, "").length ? CUT_ON.split("-").slice(1).join("/") + "/" + CUT_ON.slice(0, 4) : "x").test(text) || text.includes(CUT_ON),
       "…and echoes the date it wrote", text.slice(-300));
  } else {
    console.log("\n1i · Complete NOT pressed (set DWALK_SCHEDULE=1)");
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 2 · THE LIST — search, filters, columns, sorting, paging
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n═══ 2 · THE REGISTER · /accounts?tab=disconnects ═══");
  await page.goto(`${BASE}/${T}/accounts?tab=disconnects`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${SHOTS}/l1-list.png`, fullPage: true });
  const SEARCH = 'input[placeholder^="Case #"]';
  const firstCells = () => page.evaluate(() =>
    [...document.querySelectorAll("table tbody tr")].map((tr) => tr.children[0].textContent.trim().slice(0, 14)));

  const baseline = await firstCells();
  is(baseline.length > 0, "the register draws rows", JSON.stringify(baseline));
  const headers = await page.$$eval("table thead th", (hs) => hs.map((h) => h.textContent.trim()));
  for (const col of ["CASE #", "ACCOUNT", "CUSTOMER", "ADDRESS", "OWED", "TIER", "CUT DATE", "LAST NOTICE", "STATE", "ACTIONS"]) {
    is(headers.some((h) => h.toUpperCase().includes(col)), `the \`${col}\` column is drawn`, headers.join(" | "));
  }

  console.log("\n2a · THE SEARCH BOX — and the leg it promised and did not have");
  // ⚠ The placeholder has promised `Case #` since the tab shipped and the query
  // did not search it. Each term below is asserted to NARROW the list to the
  // one case, which a box that ignores its input cannot do.
  const searchCases = [
    [CASE, "the full case number"],
    [CASE.toLowerCase(), "the case number in lower case"],
    [CASE.slice(-4), "the tail of the case number"],
    [ACCT, "the account number"],
  ];
  for (const [term, what] of searchCases) {
    await page.fill(SEARCH, term);
    await page.waitForTimeout(1800);
    const got = await firstCells();
    is(got.length === 1 && got[0] === CASE, `the box finds ${what} (\`${term}\`)`, JSON.stringify(got));
  }
  await page.fill(SEARCH, "zzzznothingmatchesthis");
  await page.waitForTimeout(1800);
  const empty = await firstCells();
  is(empty.length === 0, "a term that matches nothing returns nothing — the box is not decorative", JSON.stringify(empty));
  await page.fill(SEARCH, "");
  await page.waitForTimeout(1600);
  is((await firstCells()).length === baseline.length, "clearing it restores the list", "it did not");

  console.log("\n2b · THE SEGMENTS — and a SEGMENT is not a FILTER");
  for (const seg of ["Due to cut", "At notice", "Reconnections", "All"]) {
    const btn = await page.$(`button:has-text("${seg}")`);
    is(btn !== null, `the \`${seg}\` segment is offered`, seg);
  }
  await page.click('button:has-text("Due to cut")');
  await page.waitForTimeout(2000);
  const dueRows = await page.evaluate(() =>
    [...document.querySelectorAll("table tbody tr")].map((tr) => tr.textContent.replace(/\s+/g, " ")));
  is(dueRows.length > 0 && dueRows.every((r) => /Due to cut|On hold/i.test(r)),
     "`Due to cut` narrows to cases with a date", dueRows.map((r) => r.slice(0, 60)).join(" || "));
  await page.click('button:has-text("All")');
  await page.waitForTimeout(2000);
  is((await firstCells()).length === baseline.length, "`All` restores every row", "it did not");

  console.log("\n2c · THE FILTER PANEL — the STATE predicate, applied by the server");
  // The panel is a `<details>` whose summary reads `+ Filter ▾`.
  const filterSummary = await page.evaluateHandle(() =>
    [...document.querySelectorAll("summary")].find((s) => /Filter/i.test(s.textContent)) ?? null);
  is((await filterSummary.evaluate((n) => n !== null)), "the register offers a filter panel", "no `+ Filter` summary");
  await filterSummary.asElement().click();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${SHOTS}/l2-filter.png`, fullPage: true });
  const filterOptions = await page.evaluate(() => {
    const panel = [...document.querySelectorAll("details")].find((d) => /Filter/i.test(d.querySelector("summary")?.textContent ?? ""));
    if (panel === undefined) return [];
    return [...panel.querySelectorAll("label")].map((l) => ({
      label: l.textContent.replace(/\s+/g, " ").trim(),
      checked: (l.querySelector("input") ?? document.getElementById(l.htmlFor))?.checked ?? null,
    }));
  });
  is(filterOptions.length > 0, "…and it offers the STATES a case can be in", JSON.stringify(filterOptions));
  // ⚠ **EVERY OPTION IS TICKED IN TURN AND ITS EFFECT MEASURED.** A filter that
  // renders and does not filter is this repo's commonest shape of dead UI, and
  // it is invisible to a check that only counts the options.
  // ⚠ **THE HANDLE IS RE-RESOLVED EVERY TIME.** The panel re-renders on each
  // tick, so a handle held across one is detached — and a click on a detached
  // node throws rather than doing nothing, which is the good outcome; a
  // SELECTOR held across one would silently match nothing.
  async function toggleFilter(label) {
    const panel = await page.evaluateHandle(() =>
      [...document.querySelectorAll("details")].find((d) => /Filter/i.test(d.querySelector("summary")?.textContent ?? "")) ?? null);
    const isOpen = await panel.evaluate((d) => d !== null && d.open);
    if (!isOpen) { await (await page.evaluateHandle(() =>
      [...document.querySelectorAll("summary")].find((s) => /Filter/i.test(s.textContent)) ?? null)).asElement().click();
      await page.waitForTimeout(500); }
    const box = await page.evaluateHandle((wanted) => {
      const d = [...document.querySelectorAll("details")].find((n) => /Filter/i.test(n.querySelector("summary")?.textContent ?? ""));
      if (d === undefined) return null;
      const l = [...d.querySelectorAll("label")].find((n) => n.textContent.replace(/\s+/g, " ").trim() === wanted);
      return l === undefined ? null : (l.querySelector("input") ?? document.getElementById(l.htmlFor));
    }, label);
    const el = box.asElement();
    if (el === null || !(await box.evaluate((n) => n !== null))) return false;
    await el.click();
    await page.waitForTimeout(2200);
    return true;
  }
  for (const opt of filterOptions) {
    if (!(await toggleFilter(opt.label))) { bad(`the \`${opt.label}\` filter can be ticked`, "no checkbox"); continue; }
    const got = await page.evaluate(() =>
      [...document.querySelectorAll("table tbody tr")].map((tr) => tr.textContent.replace(/\s+/g, " ").slice(0, 90)));
    console.log(`      → \`${opt.label}\` → ${got.length} row(s)`);
    is(got.length <= baseline.length, `the \`${opt.label}\` filter narrows or holds the list`,
       `${got.length} of ${baseline.length}`);
    await toggleFilter(opt.label);
  }
  is((await firstCells()).length === baseline.length, "clearing every filter restores the list",
     `${(await firstCells()).length} of ${baseline.length}`);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(600);

  console.log("\n2d · THE COLUMN SELECTOR — a column is hidden and comes back");
  // The selector is a second `<details>`, labelled for a screen reader rather
  // than in text. It must be OPENED before anything in it can be pressed — a
  // click on a control inside a closed one times out rather than no-opping,
  // which is the failure worth having.
  const colsSummary = await page.evaluateHandle(() =>
    [...document.querySelectorAll("summary")].find((n) => /Show or hide columns/i.test(n.getAttribute("aria-label") ?? "")) ?? null);
  is(await colsSummary.evaluate((n) => n !== null), "the register offers a column selector", "no summary");
  await colsSummary.asElement().click();
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${SHOTS}/l3-columns.png`, fullPage: true });
  const headersBefore = await page.$$eval("table thead th", (hs) => hs.map((h) => h.textContent.trim()));
  const colRows = await page.evaluate(() => {
    const d = [...document.querySelectorAll("details")].find((n) => /Show or hide columns/i.test(n.querySelector("summary")?.getAttribute("aria-label") ?? ""));
    return d === undefined ? [] : [...d.querySelectorAll("label")].map((l) => ({
      label: l.textContent.replace(/\s+/g, " ").trim(),
      checked: (l.querySelector("input") ?? document.getElementById(l.htmlFor))?.checked ?? null,
    }));
  });
  is(colRows.length === headersBefore.length,
     "every drawn column has a show/hide tick", `${colRows.length} ticks · ${headersBefore.length} columns`);

  // HIDE one, and assert it LEAVES the table — a selector that renders and
  // does nothing is this repo's commonest dead control.
  const hideBox = await page.evaluateHandle(() => {
    const d = [...document.querySelectorAll("details")].find((n) => /Show or hide columns/i.test(n.querySelector("summary")?.getAttribute("aria-label") ?? ""));
    const l = [...d.querySelectorAll("label")].find((n) => /Customer/i.test(n.textContent));
    return l === undefined ? null : (l.querySelector("input") ?? document.getElementById(l.htmlFor));
  });
  if (await hideBox.evaluate((n) => n !== null)) {
    await hideBox.asElement().click();
    await page.waitForTimeout(1200);
    const hidden = await page.$$eval("table thead th", (hs) => hs.map((h) => h.textContent.trim()));
    is(!hidden.some((h) => /CUSTOMER/i.test(h)) && hidden.length === headersBefore.length - 1,
       "unticking `Customer` removes exactly that column", hidden.join(" | "));
  } else {
    bad("a column can be hidden", "no Customer tick");
  }

  const moveDown = await page.$('button[aria-label="Move Case # down"]');
  is(moveDown !== null, "every column offers a reorder control", "none found");
  if (moveDown !== null) {
    await moveDown.click();
    await page.waitForTimeout(1200);
    const reordered = await page.$$eval("table thead th", (hs) => hs.map((h) => h.textContent.trim()));
    is(!/CASE/i.test(reordered[0]), "moving `Case #` down reorders the table", reordered.join(" | "));
  }
  const reset = await page.evaluateHandle(() =>
    [...document.querySelectorAll("button")].find((b) => /Reset table/i.test(b.textContent)) ?? null);
  is(await reset.evaluate((n) => n !== null), "`Reset table` is offered", "absent");
  if (await reset.evaluate((n) => n !== null)) {
    await reset.asElement().click();
    await page.waitForTimeout(1800);
    const back = await page.$$eval("table thead th", (hs) => hs.map((h) => h.textContent.trim()));
    is(back.length === headersBefore.length && /CASE/i.test(back[0]),
       "…and it puts every column back in its drawn order", back.join(" | "));
  }
  await page.keyboard.press("Escape");
  await page.waitForTimeout(500);

  console.log("\n2e · SORTING — the two the server allows, and the order it answers in");
  // ⚠ **`has-text` IS A SUBSTRING MATCH AND `Accounts` CONTAINS `Account`.**
  // The first draft of this line pressed the *Accounts tab* instead of the
  // sort, silently left the disconnects tab, and the next section then
  // measured the accounts pager and reported the register broken. The tab is
  // excluded by EXACT text and by refusing anything inside the tab strip.
  const sortBtn = await page.evaluateHandle(() => {
    const tabs = document.querySelector('[role="tablist"]');
    return [...document.querySelectorAll("button")].find((b) =>
      b.textContent.trim() === "Account" && (tabs === null || !tabs.contains(b))) ?? null;
  }).then((h) => h.asElement());
  const hasSort = sortBtn !== null && await sortBtn.evaluate((n) => n !== null).catch(() => false);
  is(hasSort, "`Account` is a clickable sort, and it is not the Accounts tab", "absent");
  if (hasSort) {
    const beforeSort = await page.evaluate(() =>
      [...document.querySelectorAll("table tbody tr")].map((tr) => tr.children[1]?.textContent.trim() ?? ""));
    await sortBtn.click();
    await page.waitForTimeout(2200);
    const afterSort = await page.evaluate(() =>
      [...document.querySelectorAll("table tbody tr")].map((tr) => tr.children[1]?.textContent.trim() ?? ""));
    is(JSON.stringify(beforeSort) !== JSON.stringify(afterSort),
       "clicking `Account` re-orders the rows", `${beforeSort.join(",")} → ${afterSort.join(",")}`);
    const sorted = afterSort.filter((s) => /^A-/.test(s));
    is(sorted.length === 0 || sorted.every((v, i) => i === 0 || sorted[i - 1] <= v) || sorted.every((v, i) => i === 0 || sorted[i - 1] >= v),
       "…into account-number order", afterSort.join(","));
    const stillHere = await page.$$eval("table thead th", (hs) => hs.map((h) => h.textContent.trim()));
    is(stillHere.some((h) => /CASE/i.test(h)), "…and the clerk is still on the Disconnects tab", stillHere.join(" | "));
  }

  console.log("\n2f · PAGING — the page size is the server's, never the browser's");
  // ⚠ **THE HANDLE IS RESOLVED HERE AND NOT EARLIER.** Everything above this
  // line re-renders the table, and a handle taken before one of those is
  // detached — which is exactly what made the first draft of this assertion
  // report `no request` over a pager that works perfectly.
  const perOpts = await page.$$eval("select option", (os) => os.map((o) => o.value));
  is(perOpts.length >= 3, "a rows-per-page control is offered, with several sizes", perOpts.join(","));
  const perNow = await page.$eval("select", (n) => n.value);
  const perNext = perOpts.find((o) => o !== perNow) ?? perOpts[0];
  const reqs = [];
  const allReqs = [];
  page.on("request", (r) => { if (r.url().includes("/api/")) allReqs.push(r.url().replace(BASE, "")); if (r.url().includes("/disconnects?")) reqs.push(r.url()); });
  await page.selectOption("select", perNext);
  await page.waitForTimeout(2500);
  if (reqs.length === 0) console.log("      (api calls in the window: " + (allReqs.join(" | ") || "none") + "; select now reads " + (await page.$eval("select", (n) => n.value)) + ")");
  is(reqs.some((u) => u.includes(`per=${perNext}`)),
     "changing it re-asks the SERVER — paging is never client-side (NFR-3)",
     reqs.join(" | ") || `no request (was per=${perNow}, chose ${perNext})`);
  await page.selectOption("select", perNow);
  await page.waitForTimeout(2000);
  is(reqs.some((u) => u.includes("page=1")), "…and every page is asked for by number", reqs.join(" | "));
  const pager = await bodyText(page);
  is(/\d+–\d+ of \d+/.test(pager), "the pager states the range and the total", (pager.match(/\d+–\d+ of \d+/) ?? ["absent"])[0]);

  // ══════════════════════════════════════════════════════════════════════════
  // 3 · THE DOOR — from the list row to the record
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n═══ 3 · THE DOOR · a row opens its case ═══");
  // Re-entered from the top, so the door is tested the way a clerk reaches it
  // and not from whatever state the column experiments above left behind.
  await page.goto(`${BASE}/${T}/accounts?tab=disconnects`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2200);
  await page.fill(SEARCH, CASE);
  await page.waitForTimeout(2000);
  const door = await page.evaluate(() => {
    const a = document.querySelector('table tbody tr a[aria-label="Open the case"], table tbody tr a[title="Open the case"]');
    return a === null ? null : a.getAttribute("href");
  });
  is(door !== null, "the row carries an `Open the case` door", String(door));
  is(door !== null && door.startsWith(`/${T}/disconnects/`),
     "…addressed under this tenant and by the CASE NUMBER (B14 rule 31)", String(door));
  is(door !== null && !door.startsWith("//"),
     "…and it is a path on this host, not a protocol-relative URL to another", String(door));
  if (door !== null) {
    await page.click('table tbody tr a[aria-label="Open the case"]');
    await page.waitForTimeout(2500);
    is(page.url().includes(`/${T}/disconnects/`) && !/Case not found/i.test(await bodyText(page)),
       "…and pressing it lands on the record", page.url());
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 4 · THE RECORD — and the greyed commit that carries its reason
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n═══ 4 · THE RECORD · /disconnects/{case} ═══");
  await page.goto(`${BASE}/${T}/disconnects/${CASE.toLowerCase()}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SHOTS}/r1-record.png`, fullPage: true });
  text = await bodyText(page);
  is(text.includes(CASE), "the kicker carries the case number", text.slice(0, 200));
  const head = await page.evaluate(() => {
    const h = document.querySelector("h1");
    return h === null ? null : { text: h.textContent.trim(), size: getComputedStyle(h).fontSize };
  });
  is(head !== null && head.size === "32px", "the page-head title is 32px (B14 rule 40)", JSON.stringify(head));
  for (const [sel, what] of [
    ['[data-testid="disconnect-record-case"]', "THE CASE"],
    ['[data-testid="disconnect-record-protections"]', "PROTECTIONS CHECKED"],
    ['[data-testid="disconnect-record-cut"]', "WHAT A CUT WOULD DO"],
    ['[data-testid="disconnect-record-not-a-closeout"]', "the `not a close-out` banner"],
  ]) {
    is((await page.$(sel)) !== null, `${what} is on the record`, sel);
  }
  // ⚠ **EACH ONE IS NAMED IN ITS OWN LINE.** Three identical `✓` lines cannot
  // tell a reader WHICH control is missing when one of them goes — law 7's
  // third habit, that a check's output must distinguish pass from fail.
  const wantActions = {
    "disconnect-record-hold": "Hold the case",
    "disconnect-record-open-account": "Open the account",
    "disconnect-record-mark-cut": "Mark as cut",
  };
  const acts = await page.evaluate((ids) => ids.map((id) => {
    const n = document.querySelector(`[data-testid="${id}"]`);
    return n === null ? null : { id, text: n.textContent.trim(), disabled: n.disabled ?? false };
  }), Object.keys(wantActions));
  for (const [id, label] of Object.entries(wantActions)) {
    const got = acts.find((a) => a !== null && a.id === id);
    is(got !== undefined, `\`${label}\` is on the record`, JSON.stringify(acts));
  }
  const extra = await page.evaluate(() => {
    const h = document.querySelector("header, .page-head") ?? document.body;
    return [...h.querySelectorAll("button, a")].map((b) => b.textContent.replace(/\s+/g, " ").trim())
      .filter((t) => /Stop the ladder|Advance|Lift a protection|Mark reconnecting|Restore service/i.test(t));
  });
  is(extra.length === 0, "…and no fourth action — the PO said `keep critical ones`", extra.join(" | "));
  const cut = await page.evaluate(() => {
    const b = document.querySelector('[data-testid="disconnect-record-mark-cut"]');
    const r = document.querySelector('[data-testid="disconnect-record-cut-refused"]');
    return {
      disabled: b === null ? null : b.disabled,
      describedBy: b === null ? null : b.getAttribute("aria-describedby"),
      reason: r === null ? null : r.textContent.trim(),
      // The COMPUTED visibility: a refusal behind `display:none` reads as
      // present to a selector and as nothing at all to a clerk.
      visible: r === null ? false : r.offsetParent !== null || getComputedStyle(r).display !== "none",
    };
  });
  console.log(`      → \`Mark as cut\` is ${cut.disabled ? "GREYED" : "LIVE"}${cut.reason ? `, reason: "${cut.reason}"` : ""}`);
  if (cut.disabled === true) {
    is(cut.reason !== null && cut.reason.length > 0 && cut.visible,
       "when it is refused, the reason is VISIBLE TEXT (BR-SHL-025)", JSON.stringify(cut));
    is(cut.describedBy !== null, "…and the button points at it for a screen reader", JSON.stringify(cut));
  } else {
    ok("`Mark as cut` is live — its preconditions are met");
  }

  console.log("\n4a · WHAT THE RECORD DOES NOT HOLD, IT SAYS");
  is(/Oldest debt/.test(text) && /Not counted/.test(text), "`Oldest debt` states its absence", "absent");
  is(/Raised by/.test(text) && /Name not kept/.test(text), "`Raised by` states its absence", "absent");
  is(/Queued is not sent/i.test(text), "the notices table refuses to call a queue a delivery", "absent");

  // ══════════════════════════════════════════════════════════════════════════
  // 5 · THE CUT
  // ══════════════════════════════════════════════════════════════════════════
  if (DO_CUT) {
    console.log("\n═══ 5 · THE CUT · p145, the destructive commit ═══");
    // ⚠ **A DISABLED BUTTON IS A REFUSAL AND IS REPORTED AS ONE.** The first
    // draft of this section pressed the button, saw no HTTP error because the
    // click never reached the server, and would have said the cut committed.
    // That is a false pass, and the question *what would make this check pass
    // wrongly* is what found it.
    if (cut.disabled === true) {
      bad("the cut committed", `\`Mark as cut\` is greyed out: ${cut.reason}`);
      console.log(`      → THE CUT DID NOT HAPPEN — the server refuses it: "${cut.reason}"`);
    } else {
      await page.click('[data-testid="disconnect-record-mark-cut"]');
      await page.waitForTimeout(1600);
      await page.screenshot({ path: `${SHOTS}/r2-cut-dialog.png`, fullPage: true });
      const dlg = await bodyText(page);
      // ⚠ **THE COPY, NOT THE COMPONENT'S CONSTANT NAME.** The first draft of
      // this line matched `WHAT MARKING IT CUT WILL DO`, which is a comment in
      // the source and is on no screen; it failed over a dialog that is
      // perfectly correct. Read the catalogue, never the code's own headings.
      is(/What this will do/i.test(dlg),
         "the dialog states the consequences before the irreversible act (B14 rule 33)", dlg.slice(0, 300));
      for (const said of ["The account reads Disconnected", "The notice ladder stops",
                          "A reconnection fee is raised", "The account does not close"]) {
        is(dlg.includes(said), `…including \`${said}\``, dlg.slice(0, 200));
      }
      const submit = await page.evaluate(() => {
        const b = [...document.querySelectorAll("button")].find((n) => n.type === "submit" && /Mark as cut/i.test(n.textContent));
        return b === undefined ? null : { disabled: b.disabled, variant: b.getAttribute("data-variant") };
      });
      is(submit !== null && submit.variant === "danger",
         "its commit is the DANGER tier, because it takes a supply away (B14 rule 6)", JSON.stringify(submit));

      const errorsBefore = httpErrors.length;
      await page.click('button[type="submit"]:has-text("Mark as cut")');
      await page.waitForTimeout(7000);
      await page.screenshot({ path: `${SHOTS}/r3-after-cut.png`, fullPage: true });

      // ⚠ **THREE INDEPENDENT WITNESSES, BECAUSE ANY ONE OF THEM CAN LIE.**
      // The absence of an HTTP error only says the request did not 4xx. The
      // record is re-read from the server and asked whether the case MOVED.
      const refused = httpErrors.slice(errorsBefore).filter((h) => h.includes("disconnect-case/cut"));
      await page.goto(`${BASE}/${T}/disconnects/${CASE.toLowerCase()}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(2500);
      await page.screenshot({ path: `${SHOTS}/r4-record-after.png`, fullPage: true });
      const after = await bodyText(page);
      const stillOfferable = await page.evaluate(() => {
        const b = document.querySelector('[data-testid="disconnect-record-mark-cut"]');
        return b === null ? null : b.disabled;
      });
      is(refused.length === 0, "the server accepted the cut", refused.join(" || ") || "none");
      is(stillOfferable !== false,
         "…and `Mark as cut` is no longer offerable, because a cut is recorded once",
         `mark-as-cut disabled=${stillOfferable}`);
      is(/\bCut\b/.test(after), "…and the record now reads the case as cut", after.slice(0, 400));
      console.log(`      → the record head now reads: ${after.slice(after.indexOf("CASE"), after.indexOf("CASE") + 160)}`);
      console.log("      → now run the readback to count what it wrote:");
      console.log("        10-scripts/po20260921_disconnect_walk_readback.py " + ACCT + " after out.json");
    }
  } else {
    console.log("\n═══ 5 · THE CUT — NOT pressed (set DWALK_CUT=1) ═══");
    console.log(`      → \`Mark as cut\` is currently ${cut.disabled ? "REFUSED: " + cut.reason : "LIVE"}`);
  }

  // ══════════════════════════════════════════════════════════════════════════
  // 6 · 1280 — the staff app's laptop minimum
  // ══════════════════════════════════════════════════════════════════════════
  console.log("\n═══ 6 · 1280, the laptop minimum ═══");
  const narrow = await signIn(await browser.newContext(), 1280);
  for (const [where, what] of [
    [`/${T}/accounts?tab=disconnects`, "the register"],
    [`/${T}/disconnects/${CASE.toLowerCase()}`, "the record"],
    [`/${T}/disconnects/new`, "the wizard"],
  ]) {
    await narrow.goto(`${BASE}${where}`, { waitUntil: "networkidle" });
    await narrow.waitForTimeout(1500);
    const over = await narrow.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    is(over <= 0, `${what} does not scroll sideways at 1280`, `${over}px of overflow`);
  }

  console.log(`\n${pass} passed · ${failures.length} failed`);
  if (pageErrors.length > 0) console.log("PAGE ERRORS:\n  " + pageErrors.join("\n  "));
  if (httpErrors.length > 0) console.log("HTTP ERRORS:\n  " + httpErrors.join("\n  "));
  for (const f of failures) console.log("FAIL " + f);
  console.log(`screenshots: ${SHOTS}`);
  process.exitCode = failures.length === 0 ? 0 : 1;
} finally {
  if (browser !== undefined) await browser.close();
}
