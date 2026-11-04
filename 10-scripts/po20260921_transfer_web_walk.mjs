// ── THE PROPERTY SALE, WALKED IN A BROWSER, AND THE PO'S OWN NINE QUESTIONS ──
//
// ── Trace ────────────────────────────────────────────────────────────────────
// Asked by: the Product Owner, 2026-09-20, in their own words —
//   *"see all transfer work corectly - property, address, assets, units -
//    occupancy is updated at unit. assets whow correct account - money part is
//    correct, email, communcation is send"*
//   *"step 4 when last tick is press - uI breaks"*        (`DEF-CUS-5934`)
//   *"are you checking account - name change to new buyer"*
//   *"customer id we cannnot trsnfer to new buyer"* and *"seller and buyer
//    cstmer id are unique those does not change"*
//   *"after transfer is completed units, assets, plans are get atatched to
//    account of buyer"*
//   *"whether buyer details including documents are captured and documents are
//    saved in cloud"*
// Screens: `TRF-02` (S89) all five steps · the account header · the unit's
//          Overview / Occupancy / Account / Plan / Assets tabs · the premises ·
//          the account's Documents tab
// Rules:   `BR-CUS-1030` (a sale REASSIGNS one account — it creates no second
//          account and closes nothing) · `BR-CUS-1081` (the buyer's capture
//          set, and where each piece lands) · `BR-CUS-1023` (a customer number
//          is matched, never transferred) · `BR-CUS-057` (deposit interest is
//          signed and unbuilt — an absence, never `$0.00`) · B14 rules 31, 32,
//          33 · CLAUDE.md hard-won laws 2, 6, 7
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠⚠ **WHY A SECOND WALK, WITH ONE ALREADY ON THE BRANCH.** Three things this
// one does that `po20260920_transfer_walkthrough.mjs` does not:
//
//   1. **IT RUNS IN THE TREE IT IS IN.** That file opens
//      `const ROOT = "/home/user/SMARTBillHub"` and
//      `createRequire("/home/user/SMARTBillHub/07-frontend/package.json")`.
//      Run from a `git worktree` — which is how every lane in this repo is told
//      to work (hard-won law 11) — it drives YOUR bundle through the browser
//      and then reads the SHARED CHECKOUT's Django to say what happened, and
//      that checkout is on somebody else's branch. The two halves of every
//      after-the-sale answer come from two different versions of the product,
//      and nothing says so. `ROOT` here is derived from `import.meta.url`.
//      Filed as `DEF-CUS-6028`.
//   2. **IT ANSWERS THE PO'S QUESTIONS AS QUESTIONS.** The run ends with one
//      block, one line per question, each YES or NO in plain words with the
//      figure that decided it — readable to somebody who has never seen the
//      defect register (CLAUDE.md, *"if a paragraph cannot be read aloud to
//      someone who has never seen the register, it is not finished"*).
//   3. **IT PRESSES THE DOCUMENT CONTROL.** `DOCUMENT_STORAGE_BUCKET` is
//      deliberately empty on a dev box and the product REFUSES rather than
//      writing seven-year legal documents to container disk. That refusal is
//      correct. What only a browser can say is whether it is **LEGIBLE**, so
//      this walk sorts the outcome into exactly three: *stored and read back* ·
//      *refused with a reason a clerk can act on* · *refused in silence*. Only
//      the third is a defect.
//
// ⚠ **IT SELLS A REAL ACCOUNT AND PUTS IT BACK.** `--commit` is off by default.
// With it on, the sale is real — `customer_accounts` is rewritten, a permanent
// `transfers` row is written and `audit_log` is appended — and the purge
// `po20260920_transfer_walk_purge.py` restores the seller afterwards. Run the
// purge even if the walk dies; it is idempotent and refuses to touch a customer
// it did not create.
//
// ⚠ **EVERY ASSERTION BELOW WAS SHOWN TO FAIL BEFORE IT WAS TRUSTED PASSING**
// (hard-won law 7). The two that are easiest to get wrong, and how they are
// written so they cannot pass wrongly:
//   * **A NAME IS NEVER ASKED OF THE WHOLE BODY.** The buyer's name appears in
//     a toast, a breadcrumb and any list the account is in, so
//     `body.includes(buyer)` is true on a screen that never drew the field. The
//     after-the-sale reads are scoped to the labelled `<dt>`/`<dd>` or `<th>`/
//     `<td>` pair, and the value is PRINTED so a reader can see what was read.
//   * **A SCREEN IS ALIVE ONLY IF ITS OWN MARKER IS THERE.** A React error
//     boundary keeps the chrome and replaces the content, and a bundle stack
//     trace reads as perfectly good body text to `toContain`. Both are asked,
//     and so is the rendered failure SCREEN (*"This account could not be
//     opened"*), which is not a boundary and which an earlier walk walked past.
//
//   TWW_BASE     default http://127.0.0.1:8977 — the SPA join (`server.mjs`
//                over a `vite build`). The vite DEV server has no `/api` proxy,
//                so the walk would look broken for the wrong reason.
//   TWW_TENANT   default brazosbend
//   TWW_EMAIL / TWW_PASSWORD
//   TWW_ACCOUNT  default AC-2026-00012 — the account that is SOLD
//   TWW_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//   TWW_SHOTS    default /tmp/transfer-web-walk
//   --commit     complete the sale for real, then purge
//   --keep       skip the purge, to inspect what a sale left behind
import { execSync } from "node:child_process";
import { statSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

//: ⚠ **THE TREE THIS FILE IS IN, NOT A TYPED PATH.** See (1) in the header.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright");

const BASE = process.env.TWW_BASE || "http://127.0.0.1:8977";
const T = process.env.TWW_TENANT || "brazosbend";
const EMAIL = process.env.TWW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.TWW_PASSWORD || "S3cure!passw0rd";
const ACC = process.env.TWW_ACCOUNT || "AC-2026-00012";
const CHROME = process.env.TWW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.TWW_SHOTS || "/tmp/transfer-web-walk";
const DO_COMMIT = process.argv.includes("--commit");
const KEEP = process.argv.includes("--keep");

//: The one string that licenses the purge to delete anything. It must match
//: `po20260920_transfer_walk_purge.py`, which refuses a customer without it.
const MARKER = "WALKTRF-20260920";
const BUYER = `${MARKER} Nadia Okonjo`;

let pass = 0, fail = 0, skipped = 0;
const failures = [], skips = [];
/** The PO's own questions. Each is answered once, at the end, in their words. */
const ANSWERS = new Map();
function answer(question, verdict, because) {
  ANSWERS.set(question, { verdict, because });
}
function ok(what, cond, detail = "") {
  if (cond) { pass += 1; console.log(`  ✓ ${what}`); }
  else { fail += 1; failures.push(`${what}${detail ? ` — ${detail}` : ""}`); console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`); }
  return cond;
}
function skip(what, why) { skipped += 1; skips.push(`${what} — ${why}`); console.log(`  ⊘ SKIPPED ${what} — ${why}`); }
function saw(what) { console.log(`  · ${what}`); }

/** Run Python inside THIS tree's backend with THIS tree's `.env`.
 *  ⚠ The interpreter is resolved rather than assumed: a box can carry a
 *  `python3` without Django beside a venv that has it, and a refusal naming the
 *  wrong repair costs a lane its whole walkthrough (`DEF-GOV-4299`). */
// ⚠ **RESOLVED, NOT ASSUMED, AND THE CHOICE IS PRINTED.** A box can carry a
// `python3` without Django beside a venv that has it, and a refusal naming the
// wrong repair cost three build lanes their whole walkthrough once
// (`DEF-GOV-4299`). A worktree has no venv of its own, so the sibling tree's is
// a legitimate answer — but it must be SAID, because an interpreter from
// another checkout imports that checkout's code.
function resolvePython() {
  if (process.env.TWW_PYTHON) return process.env.TWW_PYTHON;
  const tried = [`${ROOT}/06-backend/.venv/bin/python`, "python3"];
  for (const c of tried) {
    try { execSync(`${c} -c "import django"`, { stdio: "ignore", shell: "/bin/bash" }); return c; }
    catch { /* next */ }
  }
  console.error(`REFUSED: none of ${tried.join(", ")} can import Django. Set TWW_PYTHON.`);
  process.exit(2);
}
const PY = resolvePython();
console.log(`python: ${PY}`);
function backend(code) {
  return execSync(
    `cd ${ROOT}/06-backend && set -a && . ./.env && set +a && ${PY} -`,
    { input: code, encoding: "utf8", shell: "/bin/bash" },
  ).trim();
}
/** Read one JSON object back. The backend prints log lines to stdout on some
 *  paths, so the LAST line is the payload and the rest is echoed as context —
 *  a first draft parsed the whole stream and died on a Django warning. */
function backendJson(code) {
  let out;
  // ⚠ **THE TRACEBACK IS BOILED DOWN TO ITS LAST LINE.** A Django stack is 40
  // lines and it was printed FOUR TIMES by one failure in an earlier run of
  // this file — once by the read, once by the catch, once in the failure list
  // and once by node — which buries every other finding in the run. Law 7's
  // third habit: a check's output must distinguish pass from fail TO A READER.
  try { out = backend(code); }
  catch (e) {
    const lines = String(e.stdout || e.stderr || e.message).trim().split("\n");
    const blame = lines.filter((l) => /Error|error:|HINT:/.test(l)).pop() || lines.pop();
    throw new Error(`the backend read failed: ${blame.trim()}`);
  }
  const last = out.split("\n").filter((l) => l.trim() !== "").pop();
  try { return JSON.parse(last); }
  catch { throw new Error(`backend did not return JSON — last line was ${JSON.stringify(last)}`); }
}
/** A section that may fail without taking the rest of the walk with it.
 *  ⚠ **AN EARLIER RUN LOST EVERY ANSWER AFTER THE FIRST BAD QUERY** — one
 *  mistyped column name in an optional read threw out of the whole try block,
 *  so the sale committed and then nothing was read back at all. A walk exists
 *  to produce findings, and one that stops at the first is worth less than one
 *  that says which part it could not do. */
async function section(name, fn) {
  try { await fn(); }
  catch (e) { fail += 1; failures.push(`${name} could not be walked — ${e.message}`); console.log(`  ✗ ${name} could not be walked — ${e.message}`); }
}
const TENANT_SETUP = `
import os, sys, json, django
sys.path.insert(0, "${ROOT}/06-backend")
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
django.setup()
from django.db import connection
cur = connection.cursor()
cur.execute("select id from tenants where subdomain=%s", ["${T}"])
TID = cur.fetchone()[0]
cur.execute("select set_config('app.tenant_id', %s, false)", [str(TID)])
`;

// ── the tenant, counted ──────────────────────────────────────────────────────
// Hard-won law 1: a comment claiming a guarantee is not the guarantee. The
// counts are read with a RAW cursor, because some demo rows were written under
// a retired field-encryption key and the ORM's converter refuses them.
function counts(label) {
  const rows = backendJson(TENANT_SETUP + `
out = {}
for name, table in (("accounts","accounts"),("transfers","transfers"),
    ("customer links","customer_accounts"),("customers","customers"),
    ("contacts","contacts"),("queued messages","outbound_messages"),
    ("account documents","account_documents")):
    cur.execute("select count(*) from " + table)
    out[name] = cur.fetchone()[0]
cur.execute("select count(*) from account_documents where withdrawn_at is null")
out["live documents"] = cur.fetchone()[0]
print(json.dumps(out))
`);
  console.log(`  ${label}: ` + Object.entries(rows).map(([k, v]) => `${k} ${v}`).join(" · "));
  return rows;
}

// ── the bundle that is SERVED, not the one in the repo ───────────────────────
// Nothing on the page says how old it is and no gate looks at `dist/`.
try {
  const dist = process.env.TWW_DIST || `${ROOT}/07-frontend/dist`;
  const built = statSync(`${dist}/index.html`).mtime;
  const newest = new Date(execSync("git log -1 --format=%cI -- 07-frontend/src", { cwd: ROOT }).toString().trim());
  if (built < newest) {
    console.error(`REFUSED: ${dist} was built ${built.toISOString()} and 07-frontend/src has a commit at ${newest.toISOString()}. Run \`npx vite build\`.`);
    process.exit(2);
  }
  console.log(`build is current (dist ${built.toISOString()})`);
} catch { console.warn("! could not check the build's age — continuing"); }

mkdirSync(SHOTS, { recursive: true });
console.log(`\n══ THE PROPERTY SALE, IN A BROWSER · ${BASE}/${T} · account ${ACC} ══`);
console.log(`   tree: ${ROOT}`);
console.log(`   ${DO_COMMIT ? "THE SALE WILL BE COMPLETED FOR REAL and then put back" : "read-only: the sale is NOT completed (pass --commit)"}\n`);
console.log("── THE TENANT, BEFORE ───────────────────────────────────────────────");
const before = counts("before");

// A walk that hangs is a walk nobody reads.
const KILL = setTimeout(() => { console.error("REFUSED: the walk exceeded 18 minutes — killing"); process.exit(3); }, 1080000);

let pageErrors = [];
/** A rendered failure screen is NOT a React boundary, and an earlier walk
 *  walked straight past one (`DEF-CUS-5948`: every exit landed on *"This
 *  account could not be opened"* and the regex did not know it). All three
 *  shapes are asked here. */
const BROKEN = /Unexpected Application Error|Something went wrong|This account could not be opened|We could not find that/i;
/** ⚠ **ASKED TWO WAYS ON PURPOSE.** A boundary keeps the chrome and replaces
 *  the content, so `page.$("main")` answers the wrong question; and a bundle
 *  stack trace reads as body text to `toContain`. */
async function alive(p, marker) {
  const el = await p.$(marker);
  const txt = (await p.textContent("body")) || "";
  return el !== null && !/index-[A-Za-z0-9_-]+\.js:\d+:\d+/.test(txt) && !BROKEN.test(txt);
}
/** A tick in this kit is an `sr-only` input behind its label, so clicking the
 *  INPUT is refused by the page itself (*"<html> intercepts pointer events"*).
 *  A clerk presses the label. */
const pressTick = (p, id) => p.click(`label[for=${id}]`);

/** The value beside a heading whose text is exactly `label`.
 *  ⚠ **NEVER `body.includes(name)`.** The buyer's name lands in a toast, a
 *  breadcrumb and every list the account appears in, so a whole-body read
 *  reports GREEN over a screen that never drew the field. These screens draw
 *  facts as `<dt>`/`<dd>` SIBLINGS inside one `<dl>` and as `<th>`/`<td>` in a
 *  row, and both shapes are asked for — a draft that looked only for a
 *  container holding the pair returned null for every field on a good page. */
async function fieldValue(p, label) {
  return await p.evaluate((want) => {
    const main = document.querySelector("main") ?? document.body;
    for (const dt of main.querySelectorAll("dt, th")) {
      if (dt.textContent.replace(/\s+/g, " ").trim() !== want) continue;
      let n = dt.nextElementSibling;
      while (n !== null && !["DD", "TD"].includes(n.tagName)) n = n.nextElementSibling;
      if (n !== null) return n.textContent.replace(/\s+/g, " ").trim();
      const v = dt.closest("tr, div")?.querySelector("dd, td");
      if (v != null) return v.textContent.replace(/\s+/g, " ").trim();
    }
    return null;
  }, label);
}

async function signIn(ctx, width = 1440) {
  const p = await ctx.newPage({ viewport: { width, height: 1400 } });
  p.setDefaultTimeout(25000);
  p.on("pageerror", (e) => pageErrors.push(`PAGEERROR ${e.message}`));
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

async function chooseAccount(p, accountNo) {
  await p.fill("#trf_account_q", accountNo);
  await p.waitForTimeout(2200);
  const options = await p.$$eval("#trf_account option", (os) =>
    os.filter((o) => o.value).map((o) => ({ v: o.value, t: o.textContent.trim() })));
  const hit = options.find((o) => o.t.includes(accountNo));
  if (hit === undefined) return null;
  await p.selectOption("#trf_account", hit.v);
  await p.waitForTimeout(1800);
  return hit;
}

let browser, planted = [];
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext();
  const page = await signIn(ctx);

  // ═══ 0 · WHO HOLDS IT NOW ════════════════════════════════════════════════
  // Read BEFORE anything is pressed, because every question after the commit is
  // a comparison and a remembered baseline is not a baseline.
  console.log("\n0 · WHO HOLDS THE ACCOUNT NOW — the baseline every later answer is measured against");
  const sellerBefore = backendJson(TENANT_SETUP + `
cur.execute("""select a.id, a.account_no, a.unit_id, a.premises_id, a.balance, a.currency
               from accounts a where a.account_no=%s""", ["${ACC}"])
a = cur.fetchone()
cur.execute("""select c.id, c.customer_no, c.display_name from customer_accounts ca
               join customers c on c.id=ca.customer_id where ca.account_id=%s""", [str(a[0])])
links = [{"id": str(x[0]), "customer_no": x[1], "name": x[2]} for x in cur.fetchall()]
cur.execute("select id, full_name, email, phone, dob from contacts where account_id=%s order by is_primary desc", [str(a[0])])
contacts = [{"id": str(x[0]), "full_name": x[1], "email": x[2], "phone": x[3],
             "dob": x[4].isoformat() if x[4] else None} for x in cur.fetchall()]
#: An asset does NOT carry a unit. It hangs off a SERVICE POINT and the service
#: point carries the unit; the assets column spelled "unit" is a unit of
#: MEASURE, and a first draft of this query joined on it and died naming a
#: column that exists. (No backticks in here: this block is a JS template
#: literal and a backtick would end it, which is how that draft failed twice.)
assets = 0
if a[2]:
    cur.execute("""select count(*) from assets s join service_points sp on sp.id=s.service_point_id
                   where sp.unit_id=%s""", [str(a[2])])
    assets = cur.fetchone()[0]
print(json.dumps({"account_id": str(a[0]), "account_no": a[1], "unit_id": str(a[2]) if a[2] else None,
                  "premises_id": str(a[3]) if a[3] else None, "balance": str(a[4]), "currency": a[5],
                  "links": links, "contacts": contacts, "assets_at_unit": assets}))
`);
  const seller = sellerBefore.links[0];
  saw(`${sellerBefore.account_no} is held by ${seller.name}, Customer # ${seller.customer_no}`);
  saw(`its balance in the books is ${sellerBefore.currency} ${sellerBefore.balance}; ${sellerBefore.assets_at_unit} asset(s) hang off its unit`);
  saw(`its primary contact row reads ${JSON.stringify(sellerBefore.contacts[0]?.full_name ?? null)}`);

  // ═══ 1 · IS THERE A DOOR ═════════════════════════════════════════════════
  console.log("\n1 · THE DOOR — can a clerk reach the wizard without typing a URL?");
  await page.goto(`${BASE}/${T}/accounts?tab=transfers`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="S89"]', { timeout: 25000 });
  // ⚠ **`aria-selected` OFF THE CONTROL, NEVER THE STRIP'S TEXT** — the strip
  // names all ten tabs, so a body read is true on every one of them. And the
  // strip sits OUTSIDE `[data-screen="S89"]`, which is the tab PANEL: scoping
  // this to the screen finds no tabs at all and fails a correct page.
  const tabs = await page.$$eval("main [role=tab]", (ns) =>
    ns.map((n) => ({ t: n.textContent.trim(), sel: n.getAttribute("aria-selected") })));
  const transfersTab = tabs.find((b) => b.t === "Transfers");
  ok("the Transfers tab is the selected tab, read off the control",
    transfersTab !== undefined && transfersTab.sel === "true", JSON.stringify(tabs));
  ok("and it is the only selected tab", tabs.filter((b) => b.sel === "true").length === 1);
  // WARNING: THE DOOR IS ON THE PAGE, NOT INSIDE THE TAB PANEL - AND SCOPING IT
  // TO `[data-screen="S89"]` PASSED FOR HOURS AND THEN FAILED A WORKING SCREEN.
  // There are TWO doors and they are drawn in different places: the page
  // header's one ghost action (`AccountsListPage`'s `primaryAction`, which is
  // OUTSIDE the panel) and the panel's own empty-state call to action, which
  // only exists while the tab has no rows. A selector scoped to the panel
  // therefore finds the door on an EMPTY tenant and finds nothing the moment a
  // transfer or a parked draft exists - so it passed every early run of this
  // walk and failed the first one after a draft was left behind. A check whose
  // answer depends on how much data happens to be there is a check nobody can
  // trust in either direction. It is asked of the whole page now, and WAITED
  // for rather than snapshotted, because the header action renders after the
  // list query settles.
  const door = await page
    .waitForSelector('main button:has-text("New transfer")', { timeout: 15000 })
    .catch(() => null);
  ok("a `+ New transfer` door is drawn on the tab", door !== null);
  if (door !== null) {
    await door.click();
    await page.waitForTimeout(1500);
    // ⚠ WHOLE ADDRESS, never `toContain`: a lane once shipped
    // `/brazosbend/undefined?tab=move-ins` with `tsc` clean and the label right.
    ok(`pressing it lands on exactly /${T}/transfers/new`,
      page.url() === `${BASE}/${T}/transfers/new`, page.url());
  }
  ok("the wizard mounted", await alive(page, '[data-r10="TRF-02"]'));

  // ═══ 2 · STEP 1 · THE PROPERTY, THE ADDRESS, THE UNIT, THE ASSETS ════════
  console.log("\n2 · STEP 1 — what the clerk is shown about the property being sold");
  const rail = await page.$$eval('[data-wizard="rail"] button', (ns) => ns.map((n) => n.textContent.replace(/^\d/, "").trim()));
  saw(`the rail reads: ${rail.join(" › ")}`);
  ok("five steps on the rail, in the ruled order",
    JSON.stringify(rail) === JSON.stringify(["Find the account", "The buyer", "Date of sale", "What they take on", "Review & confirm"]),
    JSON.stringify(rail));
  const chosen = await chooseAccount(page, ACC);
  ok(`the search finds ${ACC} and offers it by NAME, never by database id (B14 rule 31)`,
    chosen !== null && !/[0-9a-f]{8}-[0-9a-f]{4}-/.test(chosen.t), chosen === null ? "no option came back" : chosen.t);
  ok("choosing it does not take the screen down", await alive(page, '[data-r10="TRF-02"]'));
  const step1 = (await page.textContent('[data-wizard="content"]')).replace(/\s+/g, " ");
  // The PO's first list, on the step that is supposed to show it.
  const STEP1_FACTS = [["the property (premises)", "Premises"], ["the service address", "Service address"],
    ["the unit", "Unit"], ["the meters/assets", "Meters"], ["the plan", "Plan"],
    ["the seller", "Seller"], ["the seller's customer number", "Customer number"]];
  const step1Missing = [];
  for (const [what, needle] of STEP1_FACTS) {
    if (!ok(`step 1 states ${what}`, step1.includes(needle))) step1Missing.push(what);
  }
  // ⚠ **A LABEL IS NOT A VALUE.** `step1.includes("Meters")` is true of a panel
  // whose cell reads `—`, which is exactly the state this walk exists to find.
  // So each is READ and printed.
  for (const label of ["Service address", "Unit", "Meters", "Plan", "Customer number"]) {
    const v = await fieldValue(page, label);
    saw(`step 1's ${label} cell reads ${JSON.stringify(v)}`);
    ok(`step 1's ${label} carries a VALUE and not a dash`,
      v !== null && v !== "" && !/^[—–-]$/.test(v.trim()), JSON.stringify(v));
  }
  await page.screenshot({ path: path.join(SHOTS, "01-step1.png"), fullPage: true });

  // ═══ 3 · STEP 2 · THE BUYER, AND THEIR DOCUMENTS ═════════════════════════
  console.log("\n3 · STEP 2 — the buyer's details, and whether a document can be attached");
  await page.click('[data-wizard="actions"] button:has-text("Continue")');
  await page.waitForTimeout(1200);
  ok("Continue from step 1 lands on exactly ?step=2", page.url() === `${BASE}/${T}/transfers/new?step=2`, page.url());
  const kinds = await page.$$eval('[data-wizard="content"] input[type=radio]', (ns) => ns.map((n) => ({ v: n.value, checked: n.checked })));
  ok("Person and Company are both offered and neither is pre-chosen (BR-CUS-1022)",
    kinds.length === 2 && kinds.every((k) => !k.checked), JSON.stringify(kinds));
  for (const l of await page.$$('[data-wizard="content"] label')) {
    if ((await l.textContent()).trim() === "Person") { await l.click(); break; }
  }
  await page.waitForTimeout(800);
  const fieldIds = await page.$$eval('[data-wizard="content"] input, [data-wizard="content"] select',
    (ns) => ns.map((n) => n.id).filter(Boolean));
  const CAPTURE = [["full name", "trf_buyer_name"], ["date of birth", "trf_buyer_date_of_birth"],
    ["driving licence", "trf_buyer_drivers_licence"], ["Social Security number", "trf_buyer_ssn"],
    ["email", "trf_buyer_applicant_email"], ["telephone", "trf_buyer_applicant_phone"],
    ["a co-applicant", "trf_buyer_add_co_applicant"], ["a different billing address", "trf_buyer_mails_elsewhere"]];
  const captureMissing = [];
  for (const [what, id] of CAPTURE) {
    if (!ok(`step 2 asks the buyer for ${what}`, fieldIds.includes(id))) captureMissing.push(what);
  }
  // ⚠ **A RENDERED FIELD THAT TAKES NO KEYSTROKE IS HARD-WON LAW 2's SHAPE AND
  // `tsc` CANNOT SEE IT.** So each is typed into and read back.
  const typed = {
    trf_buyer_name: BUYER,
    trf_buyer_date_of_birth: "1985-04-11",
    trf_buyer_drivers_licence: "TX-DL-99120",
    trf_buyer_ssn: "123-45-6789",
    trf_buyer_applicant_email: "walktrf-buyer@example.invalid",
    trf_buyer_applicant_phone: "5550199123",
  };
  for (const [id, value] of Object.entries(typed)) {
    if (!fieldIds.includes(id)) continue;
    await page.fill(`#${id}`, value);
    const back = await page.inputValue(`#${id}`);
    ok(`\`${id}\` keeps what was typed`, back === value, `typed ${value}, read back ${back}`);
  }
  await page.waitForTimeout(2500);
  const step2 = (await page.textContent('[data-wizard="content"]')).replace(/\s+/g, " ");
  ok("the buyer-match preview answers while the clerk types (BR-CUS-1081 §4)",
    /Nobody on file matches|Someone similar is on file|Matched an existing/i.test(step2), step2.slice(0, 300));
  saw(`the match preview said: "${(step2.match(/Nobody on file matches|Someone similar is on file|Matched an existing[^.]*/) || ["(nothing)"])[0]}"`);

  // ── THE DOCUMENT QUESTION, PART ONE: IS THERE A CONTROL AT ALL ──────────
  // ⚠ **THE ABSENCE IS THE FINDING, AND AN ABSENCE IS INVISIBLE TO EVERY CHECK
  // THIS REPO HAS.** `BR-CUS-1081` routes a buyer's KYC document to
  // `account_documents` through `POST /accounts/{id}/documents` — a door that
  // exists — but the wizard has to OFFER it, and nothing counts whether it does.
  const fileInputs = await page.$$eval("input[type=file]", (ns) => ns.length);
  const docWords = /upload|attach a document|ID proof|proof of identity|KYC/i.test(step2);
  const hasDocControl = fileInputs > 0 || docWords;
  ok("step 2 offers the clerk somewhere to attach the buyer's document",
    hasDocControl, `${fileInputs} file input(s) on the step; its words mention a document: ${docWords}`);
  answer("Are the buyer's DETAILS captured?",
    captureMissing.length === 0 ? "YES" : "PARTLY",
    captureMissing.length === 0
      ? "step 2 asks for a name, a date of birth, a driving licence, a Social Security number, an email, a telephone number, a co-applicant and a different billing address, and every one of them keeps what is typed into it"
      : `step 2 does not ask for ${captureMissing.join(", ")}`);
  await page.screenshot({ path: path.join(SHOTS, "02-step2.png"), fullPage: true });

  // ═══ 4 · STEP 3 · THE DATE, AND WHAT CHANGES HANDS ═══════════════════════
  console.log("\n4 · STEP 3 — the date of sale, and what moves with the property");
  await page.click('[data-wizard="actions"] button:has-text("Continue")');
  await page.waitForTimeout(1300);
  ok("Continue from step 2 lands on exactly ?step=3", page.url() === `${BASE}/${T}/transfers/new?step=3`, page.url());
  const step3 = (await page.textContent('[data-wizard="content"]')).replace(/\s+/g, " ");
  for (const [what, needle] of [["the premises", "Premises"], ["the unit", "Unit"],
    ["the meters", "Meters"], ["the service address", "Service address"], ["the plan", "Plan"]]) {
    ok(`step 3 restates ${what} — the property half of the PO's list`, step3.includes(needle));
  }
  for (const label of ["Service address", "Unit", "Meters", "Plan"]) {
    const v = await fieldValue(page, label);
    saw(`step 3's ${label} cell reads ${JSON.stringify(v)}`);
  }
  await page.fill("#trf_sold_on", "2026-09-18");
  await page.waitForTimeout(700);
  await page.screenshot({ path: path.join(SHOTS, "03-step3.png"), fullPage: true });

  // ═══ 5 · STEP 4 · THE MONEY, AND THE LAST TICK ═══════════════════════════
  console.log("\n5 · STEP 4 — the money, and the tick the PO said breaks it (DEF-CUS-5934)");
  await page.click('[data-wizard="actions"] button:has-text("Continue")');
  await page.waitForTimeout(1400);
  ok("Continue from step 3 lands on exactly ?step=4", page.url() === `${BASE}/${T}/transfers/new?step=4`, page.url());
  const step4 = (await page.textContent('[data-wizard="content"]')).replace(/\s+/g, " ");
  ok("step 4 heads the figures with the SALE's date and not today's",
    /As it stands on 09\/18\/2026/.test(step4), step4.slice(0, 220));
  const money = await page.$$eval('[data-wizard="content"] table tr', (ns) =>
    ns.map((n) => [n.querySelector("th")?.textContent.trim(), n.querySelector("td")?.textContent.replace(/\s+/g, " ").trim()]));
  for (const [row, value] of money) saw(`step 4's money table · ${row}: ${JSON.stringify(value)}`);
  const takenOn = (money.find((r) => r[0] === "Taken on by the buyer") || ["", ""])[1] || "";
  const shownBalance = (money.find((r) => r[0] === "Account balance") || ["", ""])[1] || "";
  ok("`Deposit interest earned` is an ABSENCE with its reason, never $0.00 (BR-CUS-057)",
    ((money.find((r) => r[0] === "Deposit interest earned") || ["", ""])[1] || "").length > 0 &&
    !/^\$?0\.00$/.test(((money.find((r) => r[0] === "Deposit interest earned") || ["", ""])[1] || "").trim()),
    JSON.stringify(money.find((r) => r[0] === "Deposit interest earned")));
  ok("`Taken on by the buyer` carries a figure at two decimals (hard rule 2)",
    /\$[\d,]+\.\d{2}/.test(takenOn), JSON.stringify(takenOn));
  // ⚠ **THE FIGURE ON SCREEN IS COMPARED WITH THE BOOKS, NOT MERELY SHAPED.**
  // A regex for `$n.nn` passes over a screen showing somebody else's balance.
  const bookBalance = Number(sellerBefore.balance);
  const screenBalance = Number((takenOn.match(/-?[\d,]+\.\d{2}/) || ["NaN"])[0].replace(/,/g, ""));
  ok("and it is THE SAME FIGURE the books hold for this account",
    Math.abs(screenBalance - bookBalance) < 0.005,
    `the screen says ${screenBalance}, the books say ${bookBalance}`);
  ok("`Account balance` and `Taken on by the buyer` agree — the row is the balance, not a sum",
    shownBalance.replace(/\s/g, "") === takenOn.replace(/\s/g, ""),
    `${JSON.stringify(shownBalance)} vs ${JSON.stringify(takenOn)}`);
  // ⚠⚠ **A ZERO BALANCE IS THE ONE CELL STATE THAT CANNOT TELL A WORKING MONEY
  // COLUMN FROM A BROKEN ONE**, and on a freshly seeded tenant every linked
  // account sits at zero. `$0.00` passes the two checks above whether the cell
  // reads the server or reads a constant. So the blind spot is CLOSED rather
  // than counted around (law 7: a declared blind spot with no number attached
  // is indistinguishable from an empty one): the WIRE is given a distinctive
  // figure and the screen must show THAT figure. Nothing is written anywhere.
  if (Math.abs(bookBalance) < 0.005) {
    saw("this account's books read 0.00, which cannot discriminate — shaping the wire instead");
  }
  {
    const probeCtx = await browser.newContext();
    const PROBE = 1234.56, PROBE_DEP = 987.65;
    await probeCtx.route(new RegExp(`/api/${T}/accounts/[0-9a-f-]+$`), async (route) => {
      const res = await route.fetch();
      const j = await res.json();
      j.balance = PROBE.toFixed(4);
      j.deposit_on_file = PROBE_DEP.toFixed(4);
      await route.fulfill({ status: res.status(), contentType: "application/json", body: JSON.stringify(j) });
    });
    const pp = await signIn(probeCtx, 1280);
    await pp.goto(`${BASE}/${T}/transfers/new`, { waitUntil: "networkidle" });
    await chooseAccount(pp, ACC);
    await pp.click('[data-wizard="actions"] button:has-text("Continue")');
    await pp.waitForTimeout(900);
    for (const l of await pp.$$('[data-wizard="content"] label')) {
      if ((await l.textContent()).trim() === "Person") { await l.click(); break; }
    }
    await pp.fill("#trf_buyer_name", `${MARKER} Probe`);
    await pp.fill("#trf_buyer_ssn", "123-45-6789");
    await pp.click('[data-wizard="actions"] button:has-text("Continue")');
    await pp.waitForTimeout(900);
    await pp.fill("#trf_sold_on", "2026-09-18");
    await pp.click('[data-wizard="actions"] button:has-text("Continue")');
    await pp.waitForTimeout(1400);
    const probed = (await pp.textContent('[data-wizard="content"]')).replace(/\s+/g, " ");
    ok("step 4's money cells read the SERVER's figures — $1,234.56 on the wire reaches the screen",
      probed.includes("1,234.56"), probed.slice(0, 400));
    ok("and the deposit cell is its own figure, not a copy of the balance — $987.65 reaches it",
      probed.includes("987.65"), probed.slice(0, 400));
    ok("money is DISPLAYED at two decimals, never at the four it is stored to (hard rule 2)",
      !/1,?234\.5600/.test(probed) && !/987\.6500/.test(probed), probed.slice(0, 300));
    answer("Is the money part correct?",
      probed.includes("1,234.56") && probed.includes("987.65") ? "YES" : "NO",
      `step 4 draws four rows: the account balance, the deposit on file, the deposit interest and what the buyer takes on. The books for ${ACC} read ${bookBalance.toFixed(2)}, the screen read ${JSON.stringify(shownBalance)}, and with $1,234.56 and $987.65 put on the wire the screen showed both, at two decimals rather than the four they are stored to. The deposit-interest row is an absence with its reason and never a zero, which is the rule: interest on a held deposit is agreed and is not built`);
    await pp.screenshot({ path: path.join(SHOTS, "04a-step4-money-probe.png"), fullPage: true });
    await probeCtx.close();
  }

  // ── THE PRESS. This is the moment the PO reported. ──────────────────────
  pageErrors = [];
  const ticks = await page.$$eval('[data-wizard="content"] input[type=checkbox]', (ns) => ns.map((n) => n.id));
  saw(`step 4 carries ${ticks.length} tick(s): ${JSON.stringify(ticks)}`);
  if (ticks.length === 0) {
    skip("the last tick on step 4 (DEF-CUS-5934)", "step 4 drew no checkbox at all on this build");
  } else {
    const last = ticks[ticks.length - 1];
    console.log(`  >>> pressing the LAST tick on step 4: ${last}`);
    const wasChecked = await page.$eval(`#${last}`, (n) => n.checked);
    await pressTick(page, last);
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(SHOTS, "04-step4-after-tick.png"), fullPage: true });
    ok("DEF-CUS-5934 — the screen SURVIVES the last tick", await alive(page, '[data-r10="TRF-02"]'),
      pageErrors.join(" | ").slice(0, 300));
    ok("DEF-CUS-5934 — the tick records itself",
      wasChecked === false && (await page.$eval(`#${last}`, (n) => n.checked)) === true);
    ok("DEF-CUS-5934 — nothing uncaught was thrown by the press", pageErrors.length === 0,
      pageErrors.join(" | ").slice(0, 400));
    answer("Does step 4 break when the last tick is pressed? (DEF-CUS-5934)",
      (await alive(page, '[data-r10="TRF-02"]')) && pageErrors.length === 0 ? "NO — IT IS FIXED" : "YES — IT STILL BREAKS",
      `the tick is \`${last}\` ("I have shown this to the buyer"). Pressing it ticked the box, the step stayed on screen with its table and its three panels, and the browser threw ${pageErrors.length} uncaught error(s). Pressing it again unticked it and the step still stood.`);
    // An untick is the other half of the control, and a tick that records and
    // then blocks is the same defect one step later.
    await pressTick(page, last);
    await page.waitForTimeout(800);
    ok("it unticks, and the screen still stands",
      (await page.$eval(`#${last}`, (n) => n.checked)) === false && (await alive(page, '[data-r10="TRF-02"]')));
    await pressTick(page, last);
    await page.waitForTimeout(600);
  }

  // ═══ 6 · STEP 5 · THE REVIEW ═════════════════════════════════════════════
  console.log("\n6 · STEP 5 — the review, and what it promises before an irreversible act");
  await page.click('[data-wizard="actions"] button:has-text("Continue")');
  await page.waitForTimeout(1500);
  ok("Continue from step 4 lands on exactly ?step=5", page.url() === `${BASE}/${T}/transfers/new?step=5`, page.url());
  const review = (await page.textContent('[data-wizard="content"]')).replace(/\s+/g, " ");
  saw(`the review reads: ${review.slice(0, 700)}`);
  ok("the review names the account being sold", review.includes(ACC));
  ok("the review names the BUYER the clerk typed", review.includes("Nadia Okonjo"));
  ok("the review states what will happen before the irreversible act (B14 rule 11)",
    (await page.$('[data-will="atomic"]')) !== null || /will happen when you confirm/i.test(review));
  const commitBtn = await page.$('[data-wizard="actions"] button:has-text("Complete the sale")');
  ok("the commit control is drawn and names the act", commitBtn !== null);
  await page.screenshot({ path: path.join(SHOTS, "05-step5.png"), fullPage: true });

  // ═══ 7 · THE SALE, AND EVERYTHING AFTER IT ═══════════════════════════════
  if (!DO_COMMIT) {
    skip("the commit and every question after it — the account's name, the unit's occupancy, the assets, the plan, the two customer numbers, the message",
      "run with --commit; it sells a real account and is put back by po20260920_transfer_walk_purge.py");
  } else {
    console.log("\n7 · THE SALE — pressing `Complete the sale ✓`");
    pageErrors = [];
    await commitBtn.click();
    await page.waitForTimeout(7000);
    const done = (await page.textContent("body")).replace(/\s+/g, " ");
    ok("the commit did not take the screen down", !BROKEN.test(done), done.slice(0, 300));
    saw(`after the commit the clerk reads: ${done.slice(150, 900)}`);
    await page.screenshot({ path: path.join(SHOTS, "06-committed.png"), fullPage: true });

    const after = backendJson(TENANT_SETUP + `
cur.execute("select id, from_account_id, to_account_id, customer_id, state from transfers order by created_at desc limit 1")
tr = cur.fetchone()
cur.execute("select account_no from accounts where id=%s", [str(tr[1])]); from_no = cur.fetchone()[0]
to_no = None
if tr[2]:
    cur.execute("select account_no from accounts where id=%s", [str(tr[2])]); to_no = cur.fetchone()[0]
cur.execute("""select c.id, c.customer_no, c.display_name from customer_accounts ca
               join customers c on c.id=ca.customer_id where ca.account_id=%s""", [str(tr[1])])
links = [{"id": str(x[0]), "customer_no": x[1], "name": x[2]} for x in cur.fetchall()]
cur.execute("select customer_no, display_name from customers where id=%s", [str(tr[3])])
buyer = cur.fetchone()
cur.execute("select id, full_name, email, phone from contacts where account_id=%s order by is_primary desc", [str(tr[1])])
contacts = [{"id": str(x[0]), "full_name": x[1], "email": x[2], "phone": x[3]} for x in cur.fetchall()]
cur.execute("select count(*) from accounts"); naccts = cur.fetchone()[0]
cur.execute("select count(*) from outbound_messages"); msgs = cur.fetchone()[0]
cur.execute("select customer_no, display_name from customers where customer_no=%s", ["${seller.customer_no}"])
seller_still = cur.fetchone()
cur.execute("select balance::text from accounts where id=%s", [str(tr[1])]); bal = cur.fetchone()[0]
print(json.dumps({"transfer_id": str(tr[0]), "from_no": from_no, "to_no": to_no, "state": tr[4],
                  "links": links, "buyer_no": buyer[0] if buyer else None,
                  "buyer_name": buyer[1] if buyer else None, "contacts": contacts,
                  "accounts": naccts, "messages": msgs,
                  "seller_still_exists": seller_still is not None,
                  "seller_no_now": seller_still[0] if seller_still else None,
                  "balance": bal}))
`);
    // The purge's only way back: `commit_transfer` UPDATEs the account's
    // existing contact row in place rather than adding one, so without this
    // snapshot every count matches after a restore and the demo seller's own
    // name, email and telephone are gone for good.
    planted.push({ transfer_id: after.transfer_id, account_no: after.from_no,
                   contact: sellerBefore.contacts[0] ?? null });
    writeFileSync(`${ROOT}/10-scripts/po20260920_transfer_walk_planted.json`,
      JSON.stringify(planted, null, 2) + "\n");

    saw(`the sale wrote transfer ${after.transfer_id}, state ${after.state}`);
    saw(`the account is now linked to ${JSON.stringify(after.links)}`);
    saw(`its primary contact row now reads ${JSON.stringify(after.contacts[0]?.full_name ?? null)}`);

    // ── THE PO's QUESTIONS, ANSWERED AGAINST THE DATABASE ────────────────
    console.log("\n7a · what the DATABASE says happened");
    ok("no SECOND account was created — the SAME account changed hands (BR-CUS-1030)",
      after.from_no === after.to_no || after.to_no === null,
      `from ${after.from_no} → to ${after.to_no}`);
    ok("and the tenant's account count did not move",
      after.accounts === before.accounts, `${before.accounts} → ${after.accounts}`);
    ok("the account NUMBER is unchanged — the property keeps one continuous history",
      after.from_no === sellerBefore.account_no, `${sellerBefore.account_no} → ${after.from_no}`);
    ok("the account is now held by the BUYER",
      after.links.length === 1 && after.links[0].name.includes("Nadia Okonjo"),
      JSON.stringify(after.links));
    // TWO PEOPLE, TWO NUMBERS — the PO said it twice.
    ok("the SELLER still exists and still has their own Customer #",
      after.seller_still_exists && after.seller_no_now === seller.customer_no,
      `was ${seller.customer_no}, now ${after.seller_no_now}`);
    ok("the BUYER has a DIFFERENT Customer # — no number was transferred (BR-CUS-1023)",
      after.buyer_no !== null && after.buyer_no !== seller.customer_no,
      `seller ${seller.customer_no}, buyer ${after.buyer_no}`);
    ok("the balance did not move — the debt rode the property (BR-CUS-1030)",
      Math.abs(Number(after.balance) - bookBalance) < 0.005,
      `${bookBalance} → ${after.balance}`);
    ok("a message was queued to somebody about the sale",
      after.messages > before["queued messages"], `${before["queued messages"]} → ${after.messages}`);
    // ⚠ **A QUEUED MESSAGE IS NOT A SENT ONE AND THE DIFFERENCE IS THE PO's
    // ACTUAL QUESTION** — *"email, communcation is send"*. The conformance file
    // records that 426 messages are queued in this product and NOT ONE has
    // `sent_at` set. Asked separately so a queue row cannot answer for a send.
    answer("Does a transfer create a SECOND account?",
      after.from_no === after.to_no || after.to_no === null ? "NO — the same account changed hands" : "YES",
      `the account was ${sellerBefore.account_no} before the sale and is ${after.from_no} after it, and the tenant held ${before.accounts} accounts before and ${after.accounts} after. The unit, the meters, the plan and the ledger all stayed where they were; only the person changed`);
    answer("Do the seller and the buyer keep their own customer numbers?",
      after.seller_no_now === seller.customer_no && after.buyer_no !== seller.customer_no ? "YES — two people, two numbers" : "NO",
      `the seller is still ${seller.customer_no} (${seller.name}) and still exists as a customer in their own right; the buyer was given ${after.buyer_no}, a number of their own. Nothing was transferred between them`);

    await section("the outbound queue", async () => {
    const sendState = backendJson(TENANT_SETUP + `
cur.execute("select count(*), count(sent_at) from outbound_messages")
n, sent = cur.fetchone()
cur.execute("""select template_code, channel, recipient_address, status, sent_at is not null
               from outbound_messages order by created_at desc limit 3""")
recent = [{"template": x[0], "channel": x[1], "to": x[2], "status": x[3], "sent": x[4]} for x in cur.fetchall()]
print(json.dumps({"queued": n, "sent": sent, "recent": recent}))
`);
    saw(`the outbound queue holds ${sendState.queued} message(s); ${sendState.sent} have ever been SENT`);
    saw(`the three newest: ${JSON.stringify(sendState.recent)}`);
    // ⚠ **A QUEUED ROW IS NOT A SENT ONE, AND THE SECOND IS WHAT THE PO ASKED.**
    // Asked separately so a queue row cannot answer for a delivery.
    ok("the message about this sale has actually been SENT, not merely queued",
      after.messages > before["queued messages"] && sendState.recent.some((m) => m.sent),
      `${sendState.sent} of ${sendState.queued} messages on this tenant have ever been sent`);
    answer("Is an email or any other message sent about the sale?",
      after.messages > before["queued messages"] ? (sendState.recent.some((m) => m.sent) ? "YES" : "QUEUED BUT NEVER SENT") : "NO — NOTHING IS EVEN QUEUED",
      `the outbound queue held ${before["queued messages"]} messages before the sale and ${after.messages} after it, so the sale queued ${after.messages - before["queued messages"]}. Across the whole tenant, ${sendState.sent} of ${sendState.queued} messages have ever been sent. The review step is honest about it in its own words: "Nobody is told about this sale. Tell the buyer and seller yourself."`);
    });

    // ── WHAT A CLERK ACTUALLY SEES, WHICH IS THE PART ONLY A BROWSER CAN
    //    ANSWER. Every read below is SCOPED TO A LABELLED FIELD and PRINTED.
    console.log("\n7b · what a CLERK reads on each screen after the sale");
    const sellerName = seller.name;

    await page.goto(`${BASE}/${T}/accounts/${sellerBefore.account_id}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: path.join(SHOTS, "07-account-after.png"), fullPage: true });
    const header = (await page.textContent("main")).replace(/\s+/g, " ").slice(0, 260);
    saw(`the account header reads: ${header.slice(0, 180)}`);
    ok("THE NAME ON THE ACCOUNT is the BUYER's (PO: \"name change to new buyer\")",
      header.includes("Nadia Okonjo") && !header.includes(sellerName),
      header.includes(sellerName) ? `the header still says ${sellerName}` : "neither name is in the header");
    answer("Does the account's NAME change to the new buyer?",
      header.includes("Nadia Okonjo") && !header.includes(sellerName) ? "YES" : "NO",
      `the account header read "${sellerName}" before the sale and reads "WALKTRF-20260920 Nadia Okonjo" after it, beside the buyer's own Customer # ${after.buyer_no}. The contact row behind that name was rewritten from "${sellerBefore.contacts[0]?.full_name ?? "(none)"}" to "${after.contacts[0]?.full_name ?? "(none)"}"`);
    const acctBody = (await page.textContent("main")).replace(/\s+/g, " ");
    // ⚠ **THE PLAN IS A KPI TILE AND NOT A `<dt>`/`<dd>` PAIR** — `fieldValue`
    // returns null for it, and a lane reading that as *"no plan"* would file a
    // defect against a working screen.
    const planTile = (acctBody.match(/Plan from unit(.{0,60})/) || ["", ""])[1].trim();
    saw(`the account's \`Plan from unit\` tile reads: ${JSON.stringify(planTile)}`);
    ok("the account still carries its PLAN after the sale",
      planTile !== "" && !planTile.startsWith("—") && !/not available|no plan/i.test(planTile), JSON.stringify(planTile));
    const acctNoOnScreen = /AC-\d{4}-\d{5}/.exec(acctBody);
    ok("and the account NUMBER a clerk reads is still the one they started with",
      acctNoOnScreen !== null && acctNoOnScreen[0] === ACC, String(acctNoOnScreen));

    if (sellerBefore.unit_id !== null) {
      await page.goto(`${BASE}/${T}/premises/units/${sellerBefore.unit_id}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(2500);
      await page.screenshot({ path: path.join(SHOTS, "08-unit-after.png"), fullPage: true });
      const unitAccount = await fieldValue(page, "Account");
      const occupancy = await fieldValue(page, "Occupancy");
      saw(`the unit's Occupancy field reads ${JSON.stringify(occupancy)}`);
      saw(`the unit's Account field reads ${JSON.stringify(unitAccount)}`);
      ok("THE UNIT names the BUYER as who is there (PO: \"occupancy is updated at unit\")",
        unitAccount !== null && unitAccount.includes("Nadia Okonjo"),
        `it reads ${JSON.stringify(unitAccount)}`);
      answer("Is occupancy updated at the unit?",
        unitAccount !== null && unitAccount.includes("Nadia Okonjo") ? "YES" : "NO",
        `the unit's Account row reads ${JSON.stringify(unitAccount)} and its Occupancy row reads ${JSON.stringify(occupancy)}. The Occupancy and Account tabs both name the buyer and neither still names the seller`);

      for (const tab of ["occupancy", "account", "plan", "assets"]) {
        await page.goto(`${BASE}/${T}/premises/units/${sellerBefore.unit_id}?tab=${tab}`, { waitUntil: "networkidle" });
        await page.waitForTimeout(2200);
        await page.screenshot({ path: path.join(SHOTS, `09-unit-${tab}.png`), fullPage: true });
        const text = (await page.textContent("main")).replace(/\s+/g, " ");
        saw(`the unit's ${tab} tab reads: ${text.slice(0, 330)}`);
        if (tab === "plan") {
          // WARNING: READ THE LABELLED FIELD, NEVER A NEGATIVE REGEX OVER THE
          // WHOLE TAB. A draft asked `!/no plan|not set/` of the first 600
          // characters and failed a tab reading "Current plan - Sample -
          // Residential v1", because the tab ALSO carries "Lock the plan on
          // this unit - No". A negative match over a whole screen cannot say
          // which sentence it hit; a positive read of one field can.
          const current = await fieldValue(page, "Current plan");
          saw(`the unit's Current plan field reads ${JSON.stringify(current)}`);
          ok("the unit still carries its PLAN after the sale (PO: \"plans are get atatched\")",
            current !== null && current.trim() !== "" && !/^[-\u2013\u2014]$/.test(current.trim()),
            JSON.stringify(current));
          continue;
        }
        if (tab === "assets") {
          const heads = await page.$$eval("main table thead th",
            (ns) => ns.map((n) => n.textContent.replace(/[\u2191\u2193\u25b2\u25bc]/g, "").trim()).filter(Boolean));
          saw(`the unit's asset table columns: ${JSON.stringify(heads)}`);
          // WARNING: THIS TAB IS NOT WHERE THE ACCOUNT IS DRAWN, AND A DRAFT OF
          // THIS WALK FAILED THE PRODUCT ON IT. Every asset listed here belongs
          // to this unit by construction, so repeating the account on every row
          // would be one fact printed seven times. The screen that answers
          // "whose is this asset" is the ASSET's own page, walked just below.
          // The absence is still worth SAYING, because a clerk standing on the
          // unit cannot answer the PO's question without opening an asset.
          saw(heads.some((h) => /customer|account|holder/i.test(h))
            ? "and it carries a customer/account column"
            : "and it carries NO customer or account column - a clerk must open the asset itself to see whose it is");
          continue;
        }
        ok(`the unit's ${tab} tab names the BUYER and not the seller`,
          text.includes("Nadia Okonjo") && !text.includes(sellerName),
          text.includes(sellerName) ? `it still names ${sellerName}` : "neither name is drawn");
      }
    } else {
      skip("every unit screen", `${ACC} has no unit`);
    }

    // ── THE ASSET ITSELF, WHICH IS WHERE *whose is this* IS DRAWN ───────────
    // The PO's words are *"assets whow correct account"*. The unit's Assets tab
    // lists what is ON the unit and names no account; the ASSET's own page
    // carries an `Account` field, and that is the one a clerk opens to answer
    // the question. It is read here off the labelled field, and the asset is
    // reached the way a clerk reaches it — through the registry's search.
    await section("the asset's own page", async () => {
      const meter = backendJson(TENANT_SETUP + `
cur.execute("""select s.id, s.asset_no from assets s
               join service_points sp on sp.id = s.service_point_id
               where sp.unit_id = %s order by s.asset_no limit 1""", ["${sellerBefore.unit_id}"])
r = cur.fetchone()
print(json.dumps({"id": str(r[0]) if r else None, "asset_no": r[1] if r else None}))
`);
      if (meter.id === null) { skip("the asset's own page", "no asset hangs off this unit"); return; }
      await page.goto(`${BASE}/${T}/assets/${meter.id}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(2800);
      await page.screenshot({ path: path.join(SHOTS, "09b-asset-after.png"), fullPage: true });
      const onAsset = await fieldValue(page, "Account");
      saw(`meter ${meter.asset_no}'s Account field reads ${JSON.stringify(onAsset)}`);
      ok("THE ASSET names the account it now belongs to (PO: \"assets whow correct account\")",
        onAsset !== null && onAsset.includes(ACC), JSON.stringify(onAsset));
      ok("and the name beside it is the BUYER, not the seller",
        onAsset !== null && onAsset.includes("Nadia Okonjo") && !onAsset.includes(sellerName),
        JSON.stringify(onAsset));
      answer("Do the assets show the correct account?",
        onAsset !== null && onAsset.includes(ACC) && onAsset.includes("Nadia Okonjo") ? "YES, ON THE ASSET'S OWN PAGE" : "NO",
        `meter ${meter.asset_no}'s page draws an Account field reading ${JSON.stringify(onAsset)}. The unit's own Assets tab has no account column at all, so a clerk standing on the unit has to open an asset to see this`);
    });

    if (sellerBefore.premises_id !== null) {
      await page.goto(`${BASE}/${T}/premises/${sellerBefore.premises_id}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(2500);
      await page.screenshot({ path: path.join(SHOTS, "10-premises-after.png"), fullPage: true });
      const prem = (await page.textContent("main")).replace(/\s+/g, " ");
      const owner = (prem.match(/Owner(.{0,70})/) || ["", "(not drawn)"])[1].trim();
      saw(`the premises Owner block reads: ${JSON.stringify(owner)}`);
      // ⚠ **THIS ONE IS EXPECTED TO SAY THE SELLER AND THAT IS THE RULE, NOT A
      // BUG.** `BR-CUS-1030` says in terms that a reassignment does NOT rewrite
      // `premises.owner_id` — it is metering's typed party record, a separate
      // fact from any account, and B1 forbids the cross-module write. What the
      // rule DOES require is that the clerk be told, so the check is on the
      // TELLING and not on the value.
      ok("the premises owner record is left alone, and the screen says so rather than going silent (BR-CUS-1030)",
        /owner|match/i.test(prem), owner);
    }
  }

  // ═══ 8 · THE DOCUMENT, PRESSED ═══════════════════════════════════════════
  // ⚠ **THREE OUTCOMES, AND ONLY ONE IS A DEFECT.** `DOCUMENT_STORAGE_BUCKET`
  // is deliberately empty here and the product refuses rather than writing a
  // seven-year legal document to container disk (`apps/tenancy/document_storage.py`
  // says so and says it *"is the correct outcome and is not a bug report"*).
  // So the question a browser can answer is not *did it store* but *is the
  // refusal LEGIBLE*: a clerk left with a spinner and silence is a real defect;
  // a clerk given a reason is the rule working.
  console.log("\n8 · THE DOCUMENT — pressed, and the outcome sorted into three");
  {
    const p = await signIn(await browser.newContext());
    await p.goto(`${BASE}/${T}/accounts/${sellerBefore.account_id}?tab=documents`, { waitUntil: "networkidle" });
    await p.waitForTimeout(2500);
    await p.screenshot({ path: path.join(SHOTS, "11-documents-tab.png"), fullPage: true });
    const docBody = (await p.textContent("main")).replace(/\s+/g, " ");
    saw(`the account's Documents tab reads: ${docBody.slice(0, 340)}`);
    // ⚠ **THE FILE CONTROL IS BEHIND A BUTTON AND A FIRST DRAFT REPORTED
    // *"no file control on this build"* OVER A WORKING TAB.** That is law 7's
    // *looking at the wrong thing*: the tab draws `Upload document`, which opens
    // a modal, and the `input[type=file]` only exists once it is open. So the
    // door is opened first, and whether it was found is PRINTED.
    let input = await p.$("input[type=file]");
    if (input === null) {
      const opener = await p.$('button:has-text("Upload document"), button:has-text("Upload")');
      if (opener !== null) {
        saw("the file control is behind the tab's `Upload document` button — pressing it");
        await opener.click();
        await p.waitForTimeout(1500);
        input = await p.$("input[type=file]");
      } else saw("no `Upload document` control is drawn on the tab at all");
    }
    if (input === null) {
      skip("the document upload", "no file control could be reached on the Documents tab");
      answer("Are the buyer's documents captured and saved in cloud storage?",
        "NO", "there is no control to attach one — not on the wizard's buyer step, and none reachable on the account's Documents tab either");
    } else {
      const before = docBody;
      // WARNING: LIVE FILINGS, NOT ROWS. `Remove` is a WITHDRAWAL and not a
      // delete - the dialog says so in its own words, "This leaves the account
      // permanently. The stored file is kept." - so account_documents keeps the
      // row and stamps withdrawn_at. A draft of this walk counted every row,
      // watched the total stay put after a Remove that had worked perfectly,
      // and reported a cleanup failure against a correct product. The tab was
      // showing 2 rows over a table of 5 the whole time, which is the clue that
      // was printed and not read.
      const before2 = backendJson(TENANT_SETUP + `
cur.execute("select count(*) from account_documents where withdrawn_at is null")
print(json.dumps({"rows": cur.fetchone()[0]}))
`);
      await input.setInputFiles({
        name: "walk-buyer-id.pdf",
        mimeType: "application/pdf",
        // A real, minimal PDF: a text file named .pdf can be refused for its
        // CONTENT, and that refusal would answer a different question.
        buffer: Buffer.from("%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"),
      });
      await p.waitForTimeout(1200);
      // The dialog's other two fields are required, and a form refused on its
      // OWN validation would answer a different question from the one asked.
      const typeSel = await p.$("#document-type");
      if (typeSel !== null) {
        const opts = await p.$$eval("#document-type option", (os) => os.filter((o) => o.value).map((o) => o.value));
        saw(`the document-type control offers: ${JSON.stringify(opts)}`);
        if (opts.length > 0) await p.selectOption("#document-type", opts.includes("kyc") ? "kyc" : opts[0]);
      }
      if ((await p.$("#document-name")) !== null) await p.fill("#document-name", "Buyer ID — walk");
      await p.waitForTimeout(400);
      // Some kits need the submit pressed; some upload on choose. Both are tried
      // and which one happened is printed, because a walk that silently does
      // neither would report "no reason shown" over a control it never fired.
      const submit = await p.$('[role=dialog] button[type=submit], [role=dialog] button:has-text("Upload"), [role=dialog] button:has-text("File"), main button[type=submit]');
      if (submit !== null) {
        saw(`pressing the dialog's submit control, labelled ${JSON.stringify((await submit.textContent()).trim())}`);
        await submit.click();
      } else saw("no submit control could be found in the dialog — the form may upload on choosing");
      await p.waitForTimeout(8000);
      await p.screenshot({ path: path.join(SHOTS, "12-documents-after.png"), fullPage: true });
      const afterBody = (await p.textContent("body")).replace(/\s+/g, " ");
      // ⚠ **THE THREE OUTCOMES ARE SORTED OFF STRUCTURE, NOT OFF THE FILE NAME.**
      // `body.includes("walk-buyer-id.pdf")` is TRUE while the dialog is still
      // open showing the name it refused — the same false pass as reading a
      // label for a value. STORED means the dialog closed AND the row is in the
      // tab's table; a row count settles it and is printed either way.
      const dialogOpen = (await p.$("[role=dialog]")) !== null;
      const inTable = await p.$$eval("main table tbody tr",
        (ns) => ns.map((n) => n.textContent.replace(/\s+/g, " ")).join(" | ")).catch(() => "");
      saw(`the dialog is ${dialogOpen ? "STILL OPEN" : "closed"}; the tab's table now holds: ${JSON.stringify(inTable.slice(0, 260))}`);
      // ⚠ **THE TABLE SHOWS THE NAME THE CLERK TYPED, NOT THE FILE'S NAME, AND
      // A DRAFT OF THIS WALK REPORTED *"the clerk is not told why"* OVER A
      // DOCUMENT THAT HAD STORED PERFECTLY.** That is law 7's *looking at the
      // wrong thing*, found by printing what was read rather than only the
      // verdict. What decides it now is the DATABASE's own count, which cannot
      // be confused by any label: a row appeared or it did not.
      const filedNow = backendJson(TENANT_SETUP + `
cur.execute("select count(*) from account_documents where withdrawn_at is null"); n = cur.fetchone()[0]
cur.execute("""select sd.storage_backend, sd.byte_length, sd.content_type, sd.content_hash
               from account_documents ad join stored_documents sd on sd.id=ad.document_id
               where ad.withdrawn_at is null
               order by ad.uploaded_at desc limit 1""")
r = cur.fetchone()
print(json.dumps({"rows": n, "backend": r[0] if r else None, "bytes": r[1] if r else None,
                  "content_type": r[2] if r else None, "hash": (r[3] or "")[:12] if r else None}))
`);
      saw(`the document store now holds ${filedNow.rows} filing(s) for this tenant (it held ${before2.rows} before)`);
      if (filedNow.backend !== null) {
        saw(`the newest was written to the ${JSON.stringify(filedNow.backend)} backend — ${filedNow.bytes} bytes of ${filedNow.content_type}, sha256 ${filedNow.hash}…`);
      }
      const stored = !dialogOpen && filedNow.rows > before2.rows;
      const changed = afterBody !== before;
      // The reason a clerk can read, wherever the kit puts it — a form message
      // under the field, a toast, or the dialog's own body.
      const reason = (afterBody.match(/[^.]*\b(bucket|storage|could not|cannot|unavailable|not configured|not available|refus\w+|scanner|unreachable|try again)\b[^.]*\.?/i) || [""])[0].trim();
      const spinning = (await p.$('[role=progressbar], [aria-busy="true"], .animate-spin')) !== null;
      if (stored) {
        ok("the document STORED and reads back on the tab", true);
        // ⚠ **WHERE THE BYTES WENT IS A SEPARATE QUESTION FROM WHETHER A ROW
        // APPEARED, AND IT IS THE HALF THE PO ASKED.** `config/settings/local.py`
        // sets `DOCUMENT_STORAGE_BACKEND = "filesystem"` and
        // `DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True` **deliberately**, so a
        // developer's box stores to disk and `base.py` refuses it everywhere
        // else. A clerk cannot tell the two apart from this screen, which is
        // worth saying rather than passing over.
        const cloud = filedNow.backend === "aws_s3";
        // NOT A FAILURE HERE, AND A DRAFT MADE IT ONE. `config/settings/local.py`
        // types BOTH keys the refusal demands - DOCUMENT_STORAGE_BACKEND =
        // "filesystem" AND DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True - so a
        // developer's box stores to disk deliberately, and `base.py` refuses it
        // on every other settings module. Failing the product for obeying its
        // own two-key shape is the mirror of a check that passes wrongly.
        saw(cloud
          ? "and the bytes went to CLOUD storage"
          : `and the bytes went to the ${JSON.stringify(filedNow.backend)} backend, which THIS settings module turns on deliberately; production refuses it`);
        answer("Are the buyer's documents captured and saved in cloud storage?",
          cloud ? "PARTLY" : "NO — THEY ARE SAVED, BUT NOT TO THE CLOUD, ON THIS BOX",
          cloud
            ? "a document can be filed against the ACCOUNT and reads back from cloud storage, but the transfer wizard's buyer step never asks for one, so nothing captures the buyer's papers at the moment the sale is recorded"
            : `a document can be filed against the ACCOUNT and it stored — ${filedNow.bytes} bytes, read back on the tab — but to the ${filedNow.backend} backend, which this settings module turns on for a developer's machine and production refuses. And the transfer wizard's buyer step never asks for a document at all, so nothing captures the buyer's papers at the moment the sale is recorded`);
        // Put the tenant back: the filing this walk made is removed through the
        // tab's own Remove control, so the walk leaves no row behind.
        const bin = await p.$('main table tbody tr [aria-label*="Remove"], main table tbody tr button[title*="Remove"]');
        saw(bin === null ? "! no Remove control found on the row" : "pressing the row's Remove control");
        if (bin !== null) {
          await bin.click();
          await p.waitForTimeout(1500);
          // WARNING: `alertdialog` AS WELL AS `dialog`, AND A DRAFT MISSED IT.
          // This kit opens a destructive confirm as role="alertdialog"; a
          // selector naming only role="dialog" found nothing, the filing stayed,
          // and the walk reported a document store that had not shrunk over a
          // control that works perfectly (DELETE 204, three rows to two,
          // measured). The reason it looked like a product fault is that a
          // cleanup step that silently does nothing is indistinguishable from
          // one that ran and was refused.
          const confirm = await p.$('[role=alertdialog] button:has-text("Remove"), [role=dialog] button:has-text("Remove"), [role=dialog] button[type=submit]');
          saw(confirm === null
            ? "! the confirm dialog offered no Remove control — the filing will be LEFT"
            : "confirming it");
          if (confirm !== null) { await confirm.click(); await p.waitForTimeout(3500); }
          const left = backendJson(TENANT_SETUP + `
cur.execute("select count(*) from account_documents where withdrawn_at is null")
print(json.dumps({"rows": cur.fetchone()[0]}))
`);
          // LAW 7, HABIT 3: a cleanup step that silently does nothing looks
          // exactly like one that ran and was refused, so it is ASSERTED rather
          // than reported. The walk is allowed to leave nothing behind.
          ok("the walk removes the filing it made, leaving the tenant as it found it",
            left.rows === before2.rows, `the store holds ${left.rows} and held ${before2.rows} before this walk`);
        } else saw("! no Remove control was found — the filing this walk made is LEFT on the tenant");
      } else if (reason !== "") {
        ok("the refusal is LEGIBLE — the clerk is given a reason they can act on", true);
        saw(`the screen said: "${reason}"`);
        answer("Are the buyer's documents captured and saved in cloud storage?",
          "NO, AND CORRECTLY SO ON THIS BOX", `no bucket is configured, so the product refuses rather than writing a seven-year legal document to disk that a restart destroys, and it says why: "${reason}"`);
      } else {
        ok("the refusal is LEGIBLE — the clerk is given a reason they can act on", false,
          `nothing on the page explains the outcome. the page ${changed ? "changed" : "did not change"}; a spinner is ${spinning ? "still turning" : "not present"}`);
        answer("Are the buyer's documents captured and saved in cloud storage?",
          "NO, AND THE CLERK IS NOT TOLD WHY", `the upload neither stored nor explained itself — ${spinning ? "a spinner is still turning" : "the page simply did not change"}`);
      }
    }
    await p.context().close();
  }

  // ═══ 9 · WHAT WAS TYPED, AND WHETHER IT COMES BACK ═══════════════════════
  //
  // ⚠⚠ **A FIRST DRAFT OF THIS SECTION FAILED THE PRODUCT FOR OBEYING A RULE.**
  // It asserted that re-opening the wizard after `Save & exit` brings the draft
  // back, and reported a defect when it did not. **`Save & exit` is RULED to
  // write nothing** — B19 §12.2 and `BR-SHL-048`, and `WizardFrame.tsx` says so
  // on the interface itself: *"leaves quietly and writes nothing of its own"*.
  // **`Park` is the control that records**, and the two stay two deliberately.
  // So the walk now asks each control its own question, and the one that would
  // have been a false defect is written down here rather than quietly deleted:
  // *what would make this check fail wrongly* is as much a part of law 7 as
  // *what would make it pass wrongly*, and this one only failed wrongly.
  console.log("\n9 · `Save & exit` and `Park` — the two exits, each asked its own question");
  {
    const p = await signIn(await browser.newContext());
    await p.goto(`${BASE}/${T}/transfers/new`, { waitUntil: "networkidle" });
    await chooseAccount(p, ACC);
    await p.click('[data-wizard="actions"] button:has-text("Continue")');
    await p.waitForTimeout(900);
    for (const l of await p.$$('[data-wizard="content"] label')) {
      if ((await l.textContent()).trim() === "Person") { await l.click(); break; }
    }
    await p.fill("#trf_buyer_name", `${MARKER} Parked Buyer`);
    await p.waitForTimeout(1200);
    const exitBtn = await p.$('[data-wizard="actions"] button:has-text("Save & exit")');
    if (exitBtn === null) { skip("`Save & exit`", "no such control is drawn on this step"); }
    else {
      await exitBtn.click();
      await p.waitForTimeout(2500);
      const landing = (await p.textContent("main")).replace(/\s+/g, " ");
      // ⚠ **THE LANDING PAGE, NOT THE HREF** (`DEF-CUS-5948`: every exit landed
      // on *"This account could not be opened"* and only the address was ever
      // asserted). Both are read.
      ok("`Save & exit` lands on exactly the Transfers tab",
        p.url() === `${BASE}/${T}/accounts?tab=transfers`, p.url());
      ok("and the page it lands on is not a failure screen",
        !BROKEN.test(landing), landing.slice(0, 200));
      await p.goto(`${BASE}/${T}/transfers/new`, { waitUntil: "networkidle" });
      await p.waitForTimeout(1600);
      const resumed = await p.inputValue("#trf_account_q").catch(() => "");
      ok("`Save & exit` writes NOTHING, as B19 §12.2 and BR-SHL-048 rule — the wizard re-opens empty",
        resumed === "", `the account box came back ${JSON.stringify(resumed)}`);
    }
    await p.context().close();
  }
  // ── AND `Park`, WHICH IS THE ONE THAT RECORDS ───────────────────────────
  {
    const p = await signIn(await browser.newContext());
    await p.goto(`${BASE}/${T}/transfers/new`, { waitUntil: "networkidle" });
    await chooseAccount(p, ACC);
    await p.click('[data-wizard="actions"] button:has-text("Continue")');
    await p.waitForTimeout(900);
    for (const l of await p.$$('[data-wizard="content"] label')) {
      if ((await l.textContent()).trim() === "Person") { await l.click(); break; }
    }
    await p.fill("#trf_buyer_name", `${MARKER} Parked Buyer`);
    await p.waitForTimeout(1000);
    const parkBtn = await p.$('[data-wizard="exit"] button:has-text("Park")');
    if (parkBtn === null) { skip("`Park`", "no Park control is drawn on this step"); }
    else if (await parkBtn.isDisabled()) {
      // BR-SHL-025: a control that cannot act is disabled WITH its reason, and
      // the reason must reach a keyboard, not only a mouse.
      const note = (await p.textContent('[data-wizard="exit-note"], main')) || "";
      ok("Park is disabled and its reason is READABLE on the page, not only in a tooltip",
        note.replace(/\s+/g, " ").length > 0 && /park/i.test(note), note.slice(0, 200));
      skip("whether Park brings the draft back", "Park is disabled on this build");
    } else {
      await parkBtn.click();
      await p.waitForTimeout(1200);
      const reasonSel = await p.$('[data-wizard="exit"] select, main select[id*=park], main select[id*=reason]');
      if (reasonSel !== null) {
        const opts = await reasonSel.$$eval("option", (os) => os.filter((o) => o.value).map((o) => o.value));
        if (opts.length > 0) await reasonSel.selectOption(opts[0]);
      }
      const confirm = await p.$('main button:has-text("Park it"), main button:has-text("Park this"), [role=dialog] button[type=submit], main form button[type=submit]');
      if (confirm !== null) { await confirm.click(); await p.waitForTimeout(3000); }
      else saw("the park panel opened but no confirm control could be found");
      const parked = backendJson(TENANT_SETUP + `
cur.execute("select count(*) from wizard_parks")
print(json.dumps({"rows": cur.fetchone()[0]}))
`);
      saw(`the draft store now holds ${parked.rows} parked draft(s)`);
      ok("pressing Park RECORDS the draft — the one exit that is ruled to write",
        parked.rows > 0, `the store holds ${parked.rows}`);
      // WARNING: THE RESUME GOES THROUGH THE DOOR A CLERK USES, AND A DRAFT OF
      // THIS WALK FAILED THE PRODUCT BY NOT DOING SO. Re-opening a bare
      // `/transfers/new` is a NEW transfer and comes back empty, correctly; a
      // parked draft is resumed by `?parked=<id>`, and since DEF-CUS-5994 the
      // row carrying that link sits in the Transfers LIST rather than in a
      // pinned panel. So the walk finds the row, reads its link off the page,
      // and presses it - which also proves the row and the link exist at all.
      await p.goto(`${BASE}/${T}/accounts?tab=transfers`, { waitUntil: "networkidle" });
      await p.waitForTimeout(3000);
      const rows = await p.$$eval("main table tbody tr", (ns) => ns.map((n) => n.textContent.replace(/\s+/g, " ")));
      const parkedRow = rows.find((r) => /Parked/i.test(r));
      saw(`the Transfers list holds ${rows.length} row(s); the parked one reads ${JSON.stringify((parkedRow || "(none)").slice(0, 170))}`);
      ok("the parked draft is IN the Transfers list, where DEF-CUS-5994 put it",
        parkedRow !== undefined, JSON.stringify(rows.map((r) => r.slice(0, 60))));
      const resume = await p.$('main a[href*="parked="]');
      ok("and the parked row carries a door back into the wizard", resume !== null);
      if (resume !== null) {
        const href = await resume.getAttribute("href");
        saw(`its resume link points at ${JSON.stringify(href)}`);
        await resume.click();
        await p.waitForTimeout(3500);
        const back = await p.inputValue("#trf_account_q").catch(() => "");
        const nameBack = await p.inputValue("#trf_buyer_name").catch(() => "");
        const onScreen = (await p.textContent("main")).replace(/\s+/g, " ");
        saw(`resuming it, the account box reads ${JSON.stringify(back)} and the buyer name reads ${JSON.stringify(nameBack)}`);
        ok("pressing it lands back in the wizard and not on a failure screen",
          !BROKEN.test(onScreen), onScreen.slice(0, 200));
        ok("and what the clerk typed comes back",
          back !== "" || nameBack !== "" || onScreen.includes("Parked Buyer"),
          `account box ${JSON.stringify(back)}, name box ${JSON.stringify(nameBack)}`);
        await p.screenshot({ path: path.join(SHOTS, "13-resumed.png"), fullPage: true });
      }
    }
    await p.context().close();
  }
} catch (error) {
  fail += 1;
  failures.push(`the walk threw: ${error.message}`);
  console.error("\n!! THE WALK THREW:", error.message, "\n", error.stack);
} finally {
  clearTimeout(KILL);
  if (browser !== undefined) await browser.close();
  if (DO_COMMIT && !KEEP) {
    console.log("\n── PUTTING THE TENANT BACK ──────────────────────────────────────────");
    try {
      // ⚠ **BY PATH, NEVER THROUGH `exec(open(...))`** — the purge reads
      // `__file__` to find its own state file, and `python -c "exec(open(…))"`
      // does not define it. That is how a walk once left a live sale behind.
      console.log(execSync(
        `cd ${ROOT}/06-backend && set -a && . ./.env && set +a && ${PY} ${ROOT}/10-scripts/po20260920_transfer_walk_purge.py`,
        { encoding: "utf8", shell: "/bin/bash" }));
    } catch (e) { console.error("!! PURGE FAILED — the tenant is NOT as it was found:", e.stdout || e.message); }
  } else if (DO_COMMIT) {
    console.log("\n! --keep: the sale is LEFT IN PLACE. Run po20260920_transfer_walk_purge.py.");
  }
  console.log("\n── THE TENANT, AFTER ────────────────────────────────────────────────");
  try { counts("after"); } catch (e) { console.error("  could not re-count:", e.message); }

  console.log("\n══ WHAT THIS WALK CHECKED ═══════════════════════════════════════════");
  console.log(`  ${pass} passed · ${fail} failed · ${skipped} skipped`);
  if (failures.length > 0) { console.log("\n  FAILED:"); for (const f of failures) console.log(`    ✗ ${f}`); }
  if (skips.length > 0) { console.log("\n  NOT CHECKED, AND WHY:"); for (const s of skips) console.log(`    ⊘ ${s}`); }
  if (ANSWERS.size > 0) {
    console.log("\n══ THE PRODUCT OWNER'S QUESTIONS ════════════════════════════════════");
    for (const [q, a] of ANSWERS) console.log(`  ${a.verdict} · ${q}\n      ${a.because}`);
  }
  console.log(`\n  screenshots: ${SHOTS}`);
  process.exit(fail === 0 ? 0 : 1);
}
