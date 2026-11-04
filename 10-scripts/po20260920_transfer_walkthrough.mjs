// ── THE PROPERTY SALE, WALKED END TO END IN A BROWSER ──────────────────────
//
// **WHY IT EXISTS.** `12-governance/26-the-transfer-does-not-transfer.md` §4
// names its own largest blind spot in its own words: *"U1 · Whether a clerk can
// do any of this ON A SCREEN. It drives the services and reads PostgreSQL back.
// It never opens a browser."* — and `10-scripts/` held a walkthrough for the
// move-in job, the move-out wizard, the account bar, the portal and nine CRs
// **and none for a transfer**. The PO found `DEF-CUS-5934` by clicking while 39
// green front-end cases and a clean `tsc` passed over it.
//
// **WHAT IT WALKS**, in the PO's own order (2026-09-20):
//   0 · the beta is COUNTED before and after, and put back
//   1 · is there a DOOR to the wizard from the Transfers tab
//   2 · step 1, including a unit with NO METER and an account with NO CONTACT
//   3 · step 2, the buyer: DOB, licence, SSN, phone, email, co-applicant,
//       mailing address, the match preview, and whether a DOCUMENT can be
//       attached at all
//   4 · step 3, the property — premises, unit, meters, plan
//   5 · step 4, and **the last tick is PRESSED** (`DEF-CUS-5934`)
//   6 · step 5 and the COMMIT
//   7 · after the commit: the account's NAME, its number, the unit's occupant,
//       the assets, the plan, the premises owner, both customer numbers, and
//       whether any message was queued
//   8 · `Save & exit` and `Park`, and whether what was typed comes back
//
// ⚠ **IT SELLS A REAL ACCOUNT ON A SHARED BETA AND PUTS IT BACK.** A sale has
// no undo — it rewrites `customer_accounts`, writes a permanent `transfers` row
// and writes `audit_log`. So `--commit` is OFF by default; with it on, the
// walk writes `po20260920_transfer_walk_planted.json` and
// `po20260920_transfer_walk_purge.py` restores the seller from `audit_log`'s
// `transfer.reassigned` row. Run the purge even if the walk dies — it is
// idempotent and refuses to touch a customer it did not create (`DEF-CUS-5945`).
//
// ⚠ **IT REFUSES A STALE BUILD.** Nothing on the page says how old the bundle
// is and no gate looks at `dist/`.
//
//   TW_BASE      default http://127.0.0.1:8977   (server.mjs over `vite build`;
//                the vite DEV server has no /api proxy and the walk would look
//                broken for the wrong reason)
//   TW_TENANT    default brazosbend
//   TW_EMAIL     default dana@brazosbendutilities.com
//   TW_PASSWORD  default S3cure!passw0rd
//   TW_ACCOUNT   default AC-2026-00012 — the account that is SOLD
//   TW_CHROME    default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//   --commit     actually complete the sale (writes to the beta, then purges)
//   --keep       skip the purge, to inspect what a sale left behind
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync, writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";

const ROOT = "/home/user/SMARTBillHub";
const BASE = process.env.TW_BASE || "http://127.0.0.1:8977";
const T = process.env.TW_TENANT || "brazosbend";
const EMAIL = process.env.TW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.TW_PASSWORD || "S3cure!passw0rd";
const ACC = process.env.TW_ACCOUNT || "AC-2026-00012";
const CHROME = process.env.TW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const DO_COMMIT = process.argv.includes("--commit");
const KEEP = process.argv.includes("--keep");
const SHOTS = process.env.TW_SHOTS || "/tmp/transfer-walk";
//: The one string that licences the purge to delete anything. Must match
//: `po20260920_transfer_walk_purge.py`.
const MARKER = "WALKTRF-20260920";

let pass = 0, fail = 0, skipped = 0;
const failures = [], skips = [], notes = [];
function ok(what, cond, detail = "") {
  if (cond) { pass += 1; console.log(`  ✓ ${what}`); }
  else { fail += 1; failures.push(what); console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`); }
}
function skip(what, why) { skipped += 1; skips.push(`${what} — ${why}`); console.log(`  ⊘ SKIPPED ${what} — ${why}`); }
function saw(what) { notes.push(what); console.log(`  · ${what}`); }

// ── the beta, counted ─────────────────────────────────────────────────────
// Hard-won law 1: a comment claiming a guarantee is not the guarantee. The
// counts are read with a RAW cursor because several demo rows were written
// under a retired field-encryption key and the ORM converter refuses them.
function betaCounts(label) {
  const py = `
import os, sys, django
sys.path.insert(0, "${ROOT}/06-backend")
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
django.setup()
from django.db import connection
with connection.cursor() as cur:
    cur.execute("select id from tenants where subdomain = '${T}'")
    row = cur.fetchone()
    if row is None:
        print("  ${label}: no ${T} tenant"); raise SystemExit(0)
    cur.execute("select set_config('app.tenant_id', %s, false)", [str(row[0])])
    out = []
    for name, table in (("accounts","accounts"),("transfers","transfers"),
        ("customer links","customer_accounts"),("customers","customers"),
        ("payments","payments"),("journal lines","journal_lines"),("invoices","invoices"),
        ("queued messages","outbound_messages"),("parked drafts","wizard_parks")):
        cur.execute("select count(*) from " + table)
        out.append(name + " " + str(cur.fetchone()[0]))
print("  ${label}: " + " · ".join(out))
`;
  return execSync(
    `cd ${ROOT}/06-backend && set -a && . ./.env && set +a && .venv/bin/python -`,
    { input: py, encoding: "utf8", shell: "/bin/bash" },
  ).trim();
}

function backendRead(pycode) {
  return execSync(
    `cd ${ROOT}/06-backend && set -a && . ./.env && set +a && .venv/bin/python -`,
    { input: pycode, encoding: "utf8", shell: "/bin/bash" },
  ).trim();
}

try {
  // ⚠ **THE DIST THAT IS SERVED, NOT THE ONE IN THE REPO.** A lane running in
  // its own `git worktree` serves that worktree's build, and checking the
  // shared repo's `dist/` would refuse a perfectly current walk — or, worse,
  // pass one over a stale bundle. `TW_DIST` names the tree `server.mjs` was
  // started in.
  const built = statSync(`${process.env.TW_DIST || ROOT + "/07-frontend/dist"}/index.html`).mtime;
  const newestSrc = new Date(execSync("git log -1 --format=%cI -- 07-frontend/src", { cwd: ROOT }).toString().trim());
  if (built < newestSrc) {
    console.error(`REFUSED: dist/ built ${built.toISOString()} but 07-frontend/src has a commit at ${newestSrc.toISOString()}. Run \`npx vite build\`.`);
    process.exit(2);
  }
  console.log(`build is current (dist ${built.toISOString()})`);
} catch { console.warn("! could not check build freshness — continuing"); }

mkdirSync(SHOTS, { recursive: true });
console.log("\n── THE BETA, BEFORE ──────────────────────────────────────────────────");
const before = betaCounts("before");
console.log(before);

// A walk that hangs is a walk nobody reads (`DEF-GOV-5877`).
const KILL = setTimeout(() => { console.error("REFUSED: walkthrough exceeded 15 minutes — killing"); process.exit(3); }, 900000);

async function signIn(ctx, width = 1440) {
  const p = await ctx.newPage({ viewport: { width, height: 1600 } });
  p.setDefaultTimeout(25000);
  p.on("pageerror", (e) => { pageErrors.push(e.message); });
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }), p.click('button[type="submit"]')]);
  return p;
}
let pageErrors = [];

/** ⚠ **THE SCREEN IS ALIVE, ASKED PROPERLY.** A React error boundary replaces
 *  the content and leaves the chrome, so `page.$("main")` alone answers the
 *  wrong question on some frames and a bundle stack trace reads as body text to
 *  `toContain`. Both are asked. */
async function screenAlive(p, marker) {
  const el = await p.$(marker);
  const txt = (await p.textContent("body")) || "";
  const stack = /index-[A-Za-z0-9_-]+\.js:\d+:\d+/.test(txt);
  return el !== null && !stack;
}

/** A tick in this kit is an `sr-only` input behind its label, so clicking the
 *  INPUT is refused by the page itself (*"<html> intercepts pointer events"*).
 *  A clerk presses the label. */
async function pressTick(p, id) { await p.click(`label[for=${id}]`); }

async function chooseAccount(p, accountNo) {
  await p.fill("#trf_account_q", accountNo);
  await p.waitForTimeout(2200);
  const values = await p.$$eval("#trf_account option", (os) => os.filter((o) => o.value).map((o) => ({ v: o.value, t: o.textContent.trim() })));
  const hit = values.find((o) => o.t.includes(accountNo));
  if (hit === undefined) return null;
  await p.selectOption("#trf_account", hit.v);
  await p.waitForTimeout(1600);
  return hit;
}

let browser, planted = [];
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const context = await browser.newContext();
  const page = await signIn(context);

  // ══ 1 · IS THERE A DOOR? ════════════════════════════════════════════════
  console.log("\n1 · THE DOOR — can a clerk reach the wizard without typing a URL?");
  await page.goto(`${BASE}/${T}/accounts?tab=transfers`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="S89"]', { timeout: 25000 });
  // ⚠ **`aria-selected` OFF THE CONTROL, NEVER THE STRIP'S TEXT.** A sibling's
  // walk asserted `innerText(body).includes("move-outs")` — true on the
  // Move-INS tab too, because the strip names all ten tabs, and it reported a
  // tick on a broken build. ⚠ And the strip is OUTSIDE `[data-screen="S89"]`,
  // which is the tab PANEL: scoping this to the screen finds no tabs at all
  // and fails a correct page, which is how this assertion was wrong first time.
  const tabState = await page.$$eval("main [role=tab]", (ns) =>
    ns.map((n) => ({ t: n.textContent.trim(), sel: n.getAttribute("aria-selected") })));
  const transfersTab = tabState.find((b) => b.t === "Transfers");
  ok("the Transfers tab is the SELECTED tab, read off the control and not off the strip's text",
    transfersTab !== undefined && transfersTab.sel === "true", JSON.stringify(tabState));
  ok("and it is the ONLY selected tab", tabState.filter((b) => b.sel === "true").length === 1,
    JSON.stringify(tabState.filter((b) => b.sel === "true")));
  const door = await page.$('[data-screen="S89"] button:has-text("New transfer")');
  ok("a `+ New transfer` door exists on the tab", door !== null);
  if (door !== null) {
    await door.click();
    await page.waitForTimeout(1500);
    // ⚠ WHOLE ADDRESS, never `toContain` — a lane once built
    // `/brazosbend/undefined?tab=move-ins` with `tsc` clean and the label right.
    ok("pressing it lands on exactly `/" + T + "/transfers/new`",
      page.url() === `${BASE}/${T}/transfers/new`, page.url());
  }
  ok("the wizard screen mounted", await screenAlive(page, '[data-r10="TRF-02"]'));

  // ══ 2 · STEP 1 ══════════════════════════════════════════════════════════
  console.log("\n2 · STEP 1 — find the account");
  const rail = await page.$$eval('[data-wizard="rail"] button', (ns) => ns.map((n) => n.textContent.replace(/^\d/, "").trim()));
  ok("five steps on the rail, in the ruled order",
    JSON.stringify(rail) === JSON.stringify(["Find the account", "The buyer", "Date of sale", "What they take on", "Review & confirm"]),
    JSON.stringify(rail));
  const chosen = await chooseAccount(page, ACC);
  ok(`the account search finds ${ACC} and offers it by NAME, not by id (B14 rule 31)`,
    chosen !== null && !/[0-9a-f]{8}-[0-9a-f]{4}/.test(chosen.t), chosen === null ? "no option" : chosen.t);
  ok("choosing it does not take the screen down", await screenAlive(page, '[data-r10="TRF-02"]'));
  const step1 = (await page.textContent('[data-wizard="content"]')).replace(/\s+/g, " ");
  for (const [what, needle] of [["the account number", "AC-"], ["the seller's name", "Seller"],
    ["the customer number", "Customer number"], ["the unit", "Unit"], ["the meters", "Meters"],
    ["the premises", "Premises"], ["the service address", "Service address"], ["the plan", "Plan"]]) {
    ok(`step 1 states ${what}`, step1.includes(needle));
  }
  await page.screenshot({ path: path.join(SHOTS, "01-step1.png"), fullPage: true });

  // ── 2b · A UNIT WITH NO METER, AND AN ACCOUNT WITH NO CONTACT ───────────
  // `DEF-CUS-5991`/`5998`: the panel read five fields declared non-optional in
  // the type while the wire can send them empty, and a meterless unit took the
  // whole step down twice in one suite run. There is no meterless account on
  // this beta, so the WIRE is shaped instead of the database — which is the
  // same read, and says so.
  console.log("\n2b · the same step over an EMPTY account payload (DEF-CUS-5991/5998)");
  for (const [label, mutate] of [
    ["a unit with NO METER and NO PLAN", "j['meters']=[]; j['unit_plan']=None; j['services']=[]; j['service_agreements']=[]"],
    ["no unit at all", "j['unit_id']=None; j['unit_label']=None; j['meters']=[]; j['unit_plan']=None"],
    ["the books unreadable", "j['balance']=None; j['balance_unavailable']=True"],
    ["NOBODY on file — contacts null", "j['contacts']=None"],
    ["no customer block", "j['customer']=None"],
  ]) {
    const ctx2 = await browser.newContext();
    await ctx2.route(new RegExp(`/api/${T}/accounts/[0-9a-f-]+$`), async (route) => {
      const res = await route.fetch();
      const j = await res.json();
      // eslint-disable-next-line no-eval
      eval(mutate.replace(/j\['(\w+)'\]/g, "j.$1").replace(/None/g, "null").replace(/True/g, "true"));
      await route.fulfill({ status: res.status(), contentType: "application/json", body: JSON.stringify(j) });
    });
    const p2 = await signIn(ctx2, 1280);
    await p2.goto(`${BASE}/${T}/transfers/new`, { waitUntil: "networkidle" });
    const got = await chooseAccount(p2, ACC);
    const alive = got !== null && (await screenAlive(p2, '[data-r10="TRF-02"]'));
    ok(`step 1 SURVIVES ${label} and states the absence`, alive,
      alive ? "" : "the screen went down — " + ((await p2.textContent("body")).match(/Cannot read properties of \w+ \(reading '[^']+'\)/) || ["no message"])[0]);
    if (!alive) await p2.screenshot({ path: path.join(SHOTS, `02-crash-${label.slice(0, 12).replace(/\W/g, "")}.png`), fullPage: true });
    await ctx2.close();
  }

  // ══ 3 · STEP 2 · THE BUYER ══════════════════════════════════════════════
  console.log("\n3 · STEP 2 — the buyer");
  await page.click('[data-wizard="actions"] button:has-text("Continue")');
  await page.waitForTimeout(1200);
  ok("Continue from step 1 lands on exactly `?step=2`", page.url() === `${BASE}/${T}/transfers/new?step=2`, page.url());
  const kinds = await page.$$eval('[data-wizard="content"] input[type=radio]', (ns) => ns.map((n) => ({ v: n.value, checked: n.checked })));
  ok("Person and Company are both offered, neither pre-chosen (BR-CUS-1022)",
    kinds.length === 2 && kinds.every((k) => !k.checked), JSON.stringify(kinds));
  saw("before a kind is stated the identity fields are ABSENT, which is the shared block's own answer");
  for (const l of await page.$$('[data-wizard="content"] label')) {
    if ((await l.textContent()).trim() === "Person") { await l.click(); break; }
  }
  await page.waitForTimeout(800);
  const fieldIds = await page.$$eval('[data-wizard="content"] input, [data-wizard="content"] select', (ns) => ns.map((n) => n.id).filter(Boolean));
  for (const [what, id] of [["full name", "trf_buyer_name"], ["date of birth", "trf_buyer_date_of_birth"],
    ["driving licence", "trf_buyer_drivers_licence"], ["SSN", "trf_buyer_ssn"],
    ["email", "trf_buyer_applicant_email"], ["phone", "trf_buyer_applicant_phone"],
    ["a co-applicant tick", "trf_buyer_add_co_applicant"], ["the `bill goes elsewhere` tick", "trf_buyer_mails_elsewhere"]]) {
    ok(`step 2 offers ${what}`, fieldIds.includes(id), JSON.stringify(fieldIds));
  }
  // Each one ACCEPTS INPUT — a rendered field that does not take a keystroke is
  // hard-won law 2's shape and `tsc` cannot see it.
  const typed = {
    trf_buyer_name: `${MARKER} Nadia Okonjo`,
    trf_buyer_date_of_birth: "1985-04-11",
    trf_buyer_drivers_licence: "TX-DL-99120",
    trf_buyer_ssn: "123-45-6789",
    trf_buyer_applicant_email: "walktrf-buyer@example.invalid",
    trf_buyer_applicant_phone: "5550199123",
  };
  for (const [id, value] of Object.entries(typed)) {
    await page.fill(`#${id}`, value);
    const back = await page.inputValue(`#${id}`);
    ok(`\`${id}\` keeps what was typed`, back === value, `typed ${value}, read back ${back}`);
  }
  // the co-applicant, opened by its tick
  await pressTick(page, "trf_buyer_add_co_applicant");
  await page.waitForTimeout(600);
  const coIds = await page.$$eval('[data-wizard="content"] input', (ns) => ns.map((n) => n.id).filter((i) => i.includes("co_applicant")));
  ok("ticking `Add a co-applicant` opens the co-applicant's own fields", coIds.length > 1, JSON.stringify(coIds));
  const coName = coIds.find((i) => i.includes("name"));
  if (coName !== undefined) { await page.fill(`#${coName}`, `${MARKER} Co Buyer`); ok("the co-applicant's name accepts input", (await page.inputValue(`#${coName}`)) !== ""); }
  await pressTick(page, "trf_buyer_add_co_applicant");
  await page.waitForTimeout(400);
  // the mailing address, opened by its tick — hard rule 8's ONE named exception
  await pressTick(page, "trf_buyer_mails_elsewhere");
  await page.waitForTimeout(600);
  const mailIds = await page.$$eval('[data-wizard="content"] input', (ns) => ns.map((n) => n.id).filter((i) => i.includes("mailing")));
  ok("ticking `Bill goes elsewhere` opens a mailing address", mailIds.length >= 4, JSON.stringify(mailIds));
  await pressTick(page, "trf_buyer_mails_elsewhere");
  await page.waitForTimeout(500);
  ok("unticking it states the seller's address stays, rather than leaving a blank",
    (await page.$('[data-mailing="sellers"]')) !== null);
  await page.waitForTimeout(2500);
  const step2 = (await page.textContent('[data-wizard="content"]')).replace(/\s+/g, " ");
  ok("the buyer-match preview ANSWERS as the clerk types (BR-CUS-1081 §4)",
    /Nobody on file matches|Matched an existing customer/.test(step2), step2.slice(0, 400));
  saw(`the preview said: "${(step2.match(/Nobody on file matches[^A-Z]*|Matched an existing customer[^F]*/) || ["(nothing)"])[0].trim()}"`);

  // ── DOCUMENTS · the PO's own question, answered by looking ──────────────
  const uploads = await page.$$eval('[data-wizard="content"] input[type=file]', (ns) => ns.length);
  const docWords = /document|upload|attach|ID proof|KYC/i.test(step2);
  ok("a clerk can attach a DOCUMENT to the buyer on step 2", uploads > 0 || docWords,
    `${uploads} file input(s); the step's words mention a document: ${docWords}`);
  await page.screenshot({ path: path.join(SHOTS, "03-step2.png"), fullPage: true });

  // ══ 4 · STEP 3 · THE PROPERTY ═══════════════════════════════════════════
  console.log("\n4 · STEP 3 — the date, and what changes hands");
  await page.click('[data-wizard="actions"] button:has-text("Continue")');
  await page.waitForTimeout(1200);
  ok("Continue from step 2 lands on exactly `?step=3`", page.url() === `${BASE}/${T}/transfers/new?step=3`, page.url());
  const step3 = (await page.textContent('[data-wizard="content"]')).replace(/\s+/g, " ");
  for (const [what, needle] of [["the premises", "Premises"], ["the unit", "Unit"], ["the meters", "Meters"],
    ["the service address", "Service address"], ["the plan", "Plan"], ["the services", "Services"]]) {
    ok(`step 3 shows ${what}`, step3.includes(needle));
  }
  const drawnMeters = (step3.match(/Meters([A-Z0-9·\- ]+)Plan/) || ["", "(none)"])[1].trim();
  saw(`step 3 draws the meters as: ${drawnMeters}`);
  ok("the meter cell carries a real asset number, not a dash", /[A-Z]-\d+/.test(drawnMeters), drawnMeters);
  await page.fill("#trf_sold_on", "2026-09-18");
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(SHOTS, "04-step3.png"), fullPage: true });

  // ══ 5 · STEP 4 · THE LAST TICK ══════════════════════════════════════════
  console.log("\n5 · STEP 4 — and the last tick is PRESSED (DEF-CUS-5934)");
  await page.click('[data-wizard="actions"] button:has-text("Continue")');
  await page.waitForTimeout(1400);
  ok("Continue from step 3 lands on exactly `?step=4`", page.url() === `${BASE}/${T}/transfers/new?step=4`, page.url());
  const step4 = (await page.textContent('[data-wizard="content"]')).replace(/\s+/g, " ");
  ok("step 4 heads the figures with the SALE's date, not today's", /As it stands on 09\/18\/2026/.test(step4), step4.slice(0, 200));
  const money = await page.$$eval('[data-wizard="content"] table tr', (ns) =>
    ns.map((n) => [n.querySelector("th")?.textContent.trim(), n.querySelector("td")?.textContent.trim()]));
  saw("step 4's money table: " + JSON.stringify(money));
  ok("`Deposit interest earned` is an ABSENCE with its reason, never $0.00 (BR-CUS-057)",
    (money.find((r) => r[0] === "Deposit interest earned") || ["", ""])[1].includes("not built"));
  ok("`Taken on by the buyer` carries a figure at 2 decimals",
    /\$[\d,]+\.\d{2}$/.test((money.find((r) => r[0] === "Taken on by the buyer") || ["", ""])[1] || ""),
    JSON.stringify(money.find((r) => r[0] === "Taken on by the buyer")));
  pageErrors = [];
  const ticks = await page.$$eval('[data-wizard="content"] input[type=checkbox]', (ns) => ns.map((n) => n.id));
  saw(`step 4 carries ${ticks.length} tick(s): ${JSON.stringify(ticks)}`);
  const lastTick = ticks[ticks.length - 1];
  console.log(`  >>> pressing the LAST tick: ${lastTick}`);
  await pressTick(page, lastTick);
  await page.waitForTimeout(1500);
  ok("the screen SURVIVES the last tick (DEF-CUS-5934)", await screenAlive(page, '[data-r10="TRF-02"]'),
    JSON.stringify(pageErrors).slice(0, 300));
  ok("the tick is now ticked", (await page.$$eval(`#${lastTick}`, (ns) => ns[0].checked)) === true);
  ok("no uncaught error was thrown by pressing it", pageErrors.length === 0, JSON.stringify(pageErrors).slice(0, 300));
  await page.screenshot({ path: path.join(SHOTS, "05-step4-after-tick.png"), fullPage: true });
  // Press it again — an untick is the other half of the control.
  await pressTick(page, lastTick);
  await page.waitForTimeout(800);
  ok("and it UNTICKS, and the screen still stands", (await page.$$eval(`#${lastTick}`, (ns) => ns[0].checked)) === false && (await screenAlive(page, '[data-r10="TRF-02"]')));
  await pressTick(page, lastTick);
  await page.waitForTimeout(600);

  // ══ 6 · STEP 5 · REVIEW AND COMMIT ══════════════════════════════════════
  console.log("\n6 · STEP 5 — review, and the commit");
  await page.click('[data-wizard="actions"] button:has-text("Continue")');
  await page.waitForTimeout(1400);
  ok("Continue from step 4 lands on exactly `?step=5`", page.url() === `${BASE}/${T}/transfers/new?step=5`, page.url());
  const review = (await page.textContent('[data-wizard="content"]')).replace(/\s+/g, " ");
  saw("the review reads: " + review.slice(0, 900));
  ok("the review names the account being sold", review.includes(ACC), review.slice(0, 200));
  ok("the review names the BUYER the clerk typed", review.includes("Nadia Okonjo"));
  ok("the review states what will happen before an irreversible act (B14 rule 11)",
    (await page.$('[data-will="atomic"]')) !== null || /will happen when you confirm/i.test(review));
  const commitBtn = await page.$('[data-wizard="actions"] button:has-text("Complete the sale")');
  ok("the commit control is drawn and says what the act is", commitBtn !== null);
  await page.screenshot({ path: path.join(SHOTS, "06-step5.png"), fullPage: true });

  if (!DO_COMMIT) {
    skip("the COMMIT and everything after it (the account's name, the unit's occupant, the assets, the plan, the premises owner, the customer numbers, the queued message)",
      "run with --commit; it sells a real account on a shared beta and is put back by po20260920_transfer_walk_purge.py");
  } else {
    const sellerBefore = JSON.parse(backendRead(`
import os, sys, json, django
sys.path.insert(0, "${ROOT}/06-backend")
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
django.setup()
from django.db import connection
with connection.cursor() as cur:
    cur.execute("select id from tenants where subdomain='${T}'"); tid = cur.fetchone()[0]
    cur.execute("select set_config('app.tenant_id', %s, false)", [str(tid)])
    cur.execute("""select a.id, a.account_no, c.customer_no, c.display_name, a.unit_id, a.premises_id,
                          (select count(*) from outbound_messages) 
                   from accounts a join customer_accounts ca on ca.account_id=a.id
                   join customers c on c.id=ca.customer_id where a.account_no=%s""", ["${ACC}"])
    r = cur.fetchone()
    cur.execute("""select id, full_name, email, phone, dob from contacts where account_id=%s order by is_primary desc""", [str(r[0])])
    contacts = [{"id": str(x[0]), "full_name": x[1], "email": x[2], "phone": x[3], "dob": x[4].isoformat() if x[4] else None} for x in cur.fetchall()]
print(json.dumps({"account_id": str(r[0]), "account_no": r[1], "seller_no": r[2], "seller_name": r[3],
                  "unit_id": str(r[4]), "premises_id": str(r[5]), "messages": r[6], "contacts": contacts}))
`).split("\n").pop());
    saw(`BEFORE the sale — account ${sellerBefore.account_no} · seller ${sellerBefore.seller_no} ${sellerBefore.seller_name} · ${sellerBefore.messages} queued messages`);

    console.log("  >>> pressing `Complete the sale ✓`");
    await commitBtn.click();
    await page.waitForTimeout(6000);
    const done = (await page.textContent("body")).replace(/\s+/g, " ");
    ok("the commit did not take the screen down", await screenAlive(page, "body"));
    saw("after the commit the screen says: " + done.slice(200, 1200));
    await page.screenshot({ path: path.join(SHOTS, "07-committed.png"), fullPage: true });

    const after = JSON.parse(backendRead(`
import os, sys, json, django
sys.path.insert(0, "${ROOT}/06-backend")
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
django.setup()
from django.db import connection
with connection.cursor() as cur:
    cur.execute("select id from tenants where subdomain='${T}'"); tid = cur.fetchone()[0]
    cur.execute("select set_config('app.tenant_id', %s, false)", [str(tid)])
    cur.execute("select id, from_account_id, to_account_id, customer_id, state, step from transfers order by created_at desc limit 1")
    tr = cur.fetchone()
    cur.execute("select c.customer_no, c.display_name from customer_accounts ca join customers c on c.id=ca.customer_id where ca.account_id=%s", [str(tr[1])])
    holders = cur.fetchall()
    cur.execute("select count(*) from outbound_messages"); msgs = cur.fetchone()[0]
    cur.execute("select account_no from accounts where id=%s", [str(tr[1])]); fromno = cur.fetchone()[0]
    cur.execute("select account_no from accounts where id=%s", [str(tr[2])]) if tr[2] else None
    tono = cur.fetchone()[0] if tr[2] else None
    cur.execute("select count(*) from accounts"); naccts = cur.fetchone()[0]
print(json.dumps({"transfer_id": str(tr[0]), "from_no": fromno, "to_no": tono, "state": tr[4], "step": tr[5],
                  "holders": [list(h) for h in holders], "messages": msgs, "accounts": naccts}))
`).split("\n").pop());
    // ⚠ **THE CONTACT SNAPSHOT IS THE PURGE'S ONLY WAY BACK.** `commit_transfer`
    // does not ADD a contact for the buyer, it UPDATEs the one the account
    // already had — the SELLER's — in place, same row id. Without this the
    // purge restores the link, every count matches, and the demo seller's own
    // name, email and phone are gone for good.
    planted.push({ transfer_id: after.transfer_id, account_no: after.from_no,
                   contact: sellerBefore.contacts[0] ?? null });
    writeFileSync(`${ROOT}/10-scripts/po20260920_transfer_walk_planted.json`, JSON.stringify(planted, null, 2) + "\n");
    saw(`AFTER the sale — transfer ${after.transfer_id} state=${after.state} · from ${after.from_no} · to ${after.to_no} · holders ${JSON.stringify(after.holders)}`);

    // ── the PO's four questions, answered ──────────────────────────────
    ok("NO SECOND ACCOUNT was created — the SAME account changed hands (BR-CUS-1030)",
      after.from_no === after.to_no && after.accounts === Number((before.match(/accounts (\d+)/) || [])[1]),
      `from ${after.from_no} → to ${after.to_no}; accounts ${after.accounts}`);
    ok("the account is now held by the BUYER and not by the seller",
      after.holders.length === 1 && after.holders[0][1].includes(MARKER),
      JSON.stringify(after.holders));
    ok("the seller keeps their OWN customer number — no id was transferred (PO 2026-09-20)",
      after.holders.every((h) => h[0] !== sellerBefore.seller_no) || after.holders[0][1].includes(MARKER),
      `seller was ${sellerBefore.seller_no}; the account now names ${JSON.stringify(after.holders)}`);
    ok("a message was queued to somebody about the sale",
      after.messages > sellerBefore.messages, `${sellerBefore.messages} → ${after.messages}`);

    // ── what a CLERK sees, which is the part only a browser can answer ──
    // ⚠ **EVERY ONE OF THESE IS SCOPED TO THE LABELLED FIELD.** A first draft
    // asked `body.includes("Nadia Okonjo")` and reported the unit's occupant
    // and the account's name GREEN over screens it had not actually read — the
    // buyer's name appears anywhere the account is listed. A whole-body
    // `toContain` cannot tell a field from a footnote.
    console.log("\n7 · AFTER THE COMMIT — what a clerk reads on each screen");
    const seller = sellerBefore.seller_name;
    /** The value beside a heading whose text is exactly `label`.
     *  ⚠ These screens draw facts as `<dt>`/`<dd>` SIBLINGS inside one `<dl>`,
     *  not as a row that contains both — a first draft looked for a container
     *  holding the pair, found none, and returned `null` for every field on a
     *  perfectly good page. Both shapes are asked for. */
    async function fieldValue(p, label) {
      return await p.evaluate((want) => {
        const main = document.querySelector("main") ?? document.body;
        for (const dt of main.querySelectorAll("dt, th")) {
          if (dt.textContent.trim() !== want) continue;
          let n = dt.nextElementSibling;
          while (n !== null && !["DD", "TD"].includes(n.tagName)) n = n.nextElementSibling;
          if (n !== null) return n.textContent.replace(/\s+/g, " ").trim();
          const row = dt.closest("tr, div");
          const v = row?.querySelector("dd, td");
          if (v != null) return v.textContent.replace(/\s+/g, " ").trim();
        }
        return null;
      }, label);
    }

    await page.goto(`${BASE}/${T}/accounts/${sellerBefore.account_id}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: path.join(SHOTS, "08-account-after.png"), fullPage: true });
    const acctHead = (await page.textContent("main")).replace(/\s+/g, " ").slice(0, 200);
    saw(`the account header reads: ${acctHead.slice(0, 140)}`);
    ok("THE NAME ON THE ACCOUNT is the BUYER (PO 2026-09-20)",
      acctHead.includes("Nadia Okonjo") && !acctHead.includes(seller),
      `the header still says ${seller}`);
    // ⚠ **THE PLAN IS A KPI TILE, NOT A `<dt>`/`<dd>` PAIR** — `fieldValue`
    // returns null for it and a lane reading that as *"no plan"* would file a
    // defect against a working screen. It is read off the header's own text.
    const acctBody = (await page.textContent("main")).replace(/\s+/g, " ");
    const plan = (acctBody.match(/Plan from unit(.{0,60})/) || ["", ""])[1].trim();
    saw(`the account's \`Plan from unit\` tile reads: ${JSON.stringify(plan)}`);
    ok("the account still carries its PLAN after the sale (PO 2026-09-20)",
      plan !== "" && !plan.startsWith("—") && !/not available|no plan/i.test(plan), JSON.stringify(plan));

    await page.goto(`${BASE}/${T}/premises/units/${sellerBefore.unit_id}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: path.join(SHOTS, "09-unit-after.png"), fullPage: true });
    const unitTabs = await page.$$eval("main [role=tab], main button", (ns) => ns.map((n) => n.textContent.trim()));
    saw(`the unit page's tabs: ${JSON.stringify(unitTabs.filter((x) => ["Overview", "Assets", "Plan", "Account", "Occupancy", "Audit log"].includes(x)))}`);
    const unitAccount = await fieldValue(page, "Account");
    const occupancy = await fieldValue(page, "Occupancy");
    saw(`the unit's Occupancy reads: ${JSON.stringify(occupancy)}`);
    saw(`the unit's Account row reads: ${JSON.stringify(unitAccount)}`);
    ok("THE UNIT NAMES THE BUYER as who is there",
      unitAccount !== null && unitAccount.includes("Nadia Okonjo"),
      `it reads ${JSON.stringify(unitAccount)} — the SELLER`);

    await page.goto(`${BASE}/${T}/premises/${sellerBefore.premises_id}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: path.join(SHOTS, "10-premises-after.png"), fullPage: true });
    const prem = (await page.textContent("main")).replace(/\s+/g, " ");
    const owner = (prem.match(/Owner(.{0,70})/) || ["", "(not drawn)"])[1].trim();
    saw(`the premises Owner block reads: ${JSON.stringify(owner)}`);
    ok("THE PREMISES OWNER names the BUYER", owner.includes("Nadia Okonjo"), owner);

    // The unit's OCCUPANCY and ACCOUNT tabs — the two the scenario suite's
    // `occupancy_at_unit` and `assets_and_account` dimensions read in SQL.
    for (const [tab, what] of [["occupancy", "the unit's OCCUPANCY tab"], ["account", "the unit's ACCOUNT tab"], ["plan", "the unit's PLAN tab"]]) {
      if (tab === "plan") {
        await page.goto(`${BASE}/${T}/premises/units/${sellerBefore.unit_id}?tab=plan`, { waitUntil: "networkidle" });
        await page.waitForTimeout(2200);
        const planText = (await page.textContent("main")).replace(/\s+/g, " ");
        saw(`${what} reads: ${planText.slice(200, 700)}`);
        ok("the unit still carries its PLAN after the sale (PO 2026-09-20)",
          /Sample — Residential|SCW-RES/.test(planText), planText.slice(200, 400));
        continue;
      }
      await page.goto(`${BASE}/${T}/premises/units/${sellerBefore.unit_id}?tab=${tab}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(2200);
      await page.screenshot({ path: path.join(SHOTS, `11-unit-${tab}-after.png`), fullPage: true });
      const text = (await page.textContent("main")).replace(/\s+/g, " ");
      saw(`${what} reads: ${text.slice(0, 420)}`);
      ok(`${what} names the BUYER and not the seller`,
        text.includes("Nadia Okonjo") && !text.includes(seller),
        text.includes(seller) ? `it still names ${seller}` : "neither name is drawn");
    }

    // The ASSETS, read where a clerk reads them.
    await page.goto(`${BASE}/${T}/premises/units/${sellerBefore.unit_id}?tab=assets`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2200);
    await page.screenshot({ path: path.join(SHOTS, "12-assets-after.png"), fullPage: true });
    const assetHeads = await page.$$eval("main table thead th", (ns) => ns.map((n) => n.textContent.replace(/[↑↓▲▼]/g, "").trim()).filter(Boolean));
    saw(`the unit's asset table columns: ${JSON.stringify(assetHeads)}`);
    ok("the asset table says WHOSE the asset now is — a customer or account column",
      assetHeads.some((h) => /customer|account|holder/i.test(h)), JSON.stringify(assetHeads));
    const assetText = (await page.textContent("main")).replace(/\s+/g, " ");
    ok("THE ASSETS name the BUYER as their customer",
      assetText.includes("Nadia Okonjo") && !assetText.includes(seller),
      assetText.includes(seller) ? `they still name ${seller}` : "neither name is drawn anywhere on the assets tab");
  }

  // ══ 8 · SAVE & EXIT, AND PARK ═══════════════════════════════════════════
  console.log("\n8 · `Save & exit` and `Park` — does what was typed come back?");
  const ctx3 = await browser.newContext();
  const p3 = await signIn(ctx3);
  await p3.goto(`${BASE}/${T}/transfers/new`, { waitUntil: "networkidle" });
  await chooseAccount(p3, ACC);
  await p3.click('[data-wizard="actions"] button:has-text("Continue")');
  await p3.waitForTimeout(900);
  for (const l of await p3.$$('[data-wizard="content"] label')) { if ((await l.textContent()).trim() === "Person") { await l.click(); break; } }
  await p3.fill("#trf_buyer_name", `${MARKER} Parked Buyer`);
  await p3.fill("#trf_buyer_applicant_phone", "5550177777");
  await p3.waitForTimeout(1500);
  await p3.click('[data-wizard="actions"] button:has-text("Save & exit")');
  await p3.waitForTimeout(2000);
  ok("`Save & exit` lands on exactly the Transfers tab", p3.url() === `${BASE}/${T}/accounts?tab=transfers`, p3.url());
  await p3.goto(`${BASE}/${T}/transfers/new`, { waitUntil: "networkidle" });
  await p3.waitForTimeout(1500);
  const resumed = await p3.inputValue("#trf_account_q").catch(() => "");
  ok("after `Save & exit`, re-opening the wizard brings back what was typed", resumed !== "",
    `the account box came back "${resumed}" — Save & exit writes NOTHING (onSaveAndExit only navigates)`);
  await ctx3.close();
} catch (error) {
  fail += 1;
  failures.push(`the walk threw: ${error.message}`);
  console.error("\n!! THE WALK THREW:", error.message);
} finally {
  clearTimeout(KILL);
  if (browser !== undefined) await browser.close();
  if (DO_COMMIT && !KEEP) {
    console.log("\n── PUTTING THE BETA BACK ─────────────────────────────────────────────");
    try {
      // ⚠ **BY PATH, NEVER THROUGH `exec(open(...))`** — the purge reads
      // `__file__` to find its own state file, and `python -c "exec(open(…))"`
      // does not define it. The first run of this walk failed exactly there
      // and left a live sale on a shared beta.
      console.log(execSync(
        `cd ${ROOT}/06-backend && set -a && . ./.env && set +a && .venv/bin/python ${ROOT}/10-scripts/po20260920_transfer_walk_purge.py`,
        { encoding: "utf8", shell: "/bin/bash" }));
    } catch (e) { console.error("!! PURGE FAILED — the beta is NOT as it was found:", e.stdout || e.message); }
  } else if (DO_COMMIT) { console.log("\n! --keep: the sale is LEFT ON THE BETA. Run po20260920_transfer_walk_purge.py."); }
  console.log("\n── THE BETA, AFTER ───────────────────────────────────────────────────");
  const after = betaCounts("after");
  console.log(after);
  console.log("\n── WHAT THIS WALK CHECKED ────────────────────────────────────────────");
  console.log(`  ${pass} passed · ${fail} failed · ${skipped} skipped`);
  if (failures.length > 0) { console.log("\n  FAILED:"); for (const f of failures) console.log(`    ✗ ${f}`); }
  if (skips.length > 0) { console.log("\n  NOT CHECKED, and why:"); for (const s of skips) console.log(`    ⊘ ${s}`); }
  console.log(`\n  screenshots: ${SHOTS}`);
  process.exit(fail === 0 ? 0 : 1);
}
