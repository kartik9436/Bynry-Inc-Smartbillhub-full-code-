// ── THE CLERK WALK · A REQUEST END TO END, IN A REAL BROWSER ───────────────
//
// `08-qa/01-e2e/journeys/J-REQ-CLERK-WALK-the-request-end-to-end.md`, the
// journey the Product Owner specified on 2026-09-19 and then asked to have
// actually run:
//
//   *"baiscally you create requestwith all details -> save as a draft, and
//    submit it - tow cases - see whther it behave correctly; then submitted
//    request - open it see all the details - then 4 actions refuse, park, ask
//    for more and apporve - whether it behave correctly"*
//
// **THE DELIVERABLE IS NOT PASS/FAIL. IT IS THE FRICTION LIST** — what a clerk
// has to do that they should not have to. Every check records WHAT HAPPENED as
// well as whether it matched, and the findings print in their own `FRICTION`
// section at the end, in plain English.
//
// ⚠ **THE SCREEN IS WHERE A WRONG ANSWER LOOKS RIGHT.** This script drives the
// browser. Every verdict that matters — the four actions, the fee, the ledger,
// the side effects of a draft — is re-read out of PostgreSQL by
// `po20260919_clerk_walk_readback.py`, for which this writes a manifest of ids.
// A screen that says `Approved` over a row that did not move is exactly the
// class of defect this split exists to catch.
//
// ⚠ **IT REFUSES A STALE BUILD, TWICE OVER.** Once against the directory (the
// commit clock AND the working-tree mtime, because either alone lies) and once
// against the SERVER, comparing the hashed entry chunk `index.html` names with
// the one the running server hands out. A sibling lane lost twenty minutes to a
// dev server six commits stale, and only the second check can see that: the
// first is truthfully answering about a directory nobody is serving.
//
// ⚠ **EVERYTHING IT CREATES IS TAGGED** and removed by
// `po20260919_clerk_walk_purge.py`, which deletes by that tag and nothing else.
// The tag goes in `applicant_name` — the one free-text field that is required
// and echoed on every screen.
//
//   CW_BASE / CW_TENANT / CW_EMAIL / CW_PASSWORD / CW_CHROME / CW_DIST
//   CW_ADDRESS / CW_UNIT  the address searched on Property (default 500 Main St) and a unit label to pin
//   CW_MANIFEST  where the ids are written for the readback
//   CW_TAG       override the tag (the purge script takes the same value)
//   CW_SKIP_STALE=1  only for the deliberate old-build proof (see the report)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync, writeFileSync, mkdtempSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

const BASE = process.env.CW_BASE || "http://127.0.0.1:8972";
const T = process.env.CW_TENANT || "brazosbend";
const EMAIL = process.env.CW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.CW_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.CW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const DIST = process.env.CW_DIST || "07-frontend/dist";
const MANIFEST = process.env.CW_MANIFEST || "/tmp/clerk-walk-manifest.json";
const TAG = process.env.CW_TAG || `CLERKWALK-${Date.now().toString().slice(-6)}`;
const ADDRESS = process.env.CW_ADDRESS || "500 Main St";

if (process.env.CW_SKIP_STALE !== "1") {
  const built = statSync(`${DIST}/index.html`).mtime;
  const lastCommit = new Date(execSync("git log -1 --format=%cI -- 07-frontend/src").toString().trim());
  const newestEdit = new Date(Number(execSync(
    "find 07-frontend/src -type f -newermt '2026-01-01' -printf '%T@\\n' | sort -n | tail -1",
  ).toString().trim() * 1000));
  const newestSrc = newestEdit > lastCommit ? newestEdit : lastCommit;
  if (built < newestSrc) {
    console.error(`REFUSED: ${DIST}/ built ${built.toISOString()} but 07-frontend/src changed ${newestSrc.toISOString()}. Run vite build.`);
    process.exit(2);
  }
}
const entryOf = (html) => (html.match(/assets\/index-[A-Za-z0-9_-]+\.js/) || [null])[0];
const localEntry = entryOf(readFileSync(`${DIST}/index.html`, "utf8"));
const servedEntry = entryOf(await (await fetch(`${BASE}/${T}/requests/new`)).text());
if (localEntry === null || servedEntry === null || localEntry !== servedEntry) {
  console.error(`REFUSED: ${BASE} serves ${servedEntry}; ${DIST}/index.html names ${localEntry}.`);
  process.exit(2);
}

const R = [];
const FRICTION = [];
const ok = (n, c, d = "") => { R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`); return c; };
const friction = (title, detail) => FRICTION.push({ title, detail });
const manifest = { tag: TAG, base: BASE, tenant: T, bundle: servedEntry, cases: {}, actions: {} };

const FILE_BODY = `SMARTBillHub clerk-walk attachment ${TAG}\n`;
const scratch = mkdtempSync(join(tmpdir(), "clerk-walk-"));
const FILE_PATH = join(scratch, "driving-licence.pdf");
writeFileSync(FILE_PATH, FILE_BODY);

const b = await chromium.launch({ executablePath: CHROME });
const httpErrors = [];

/** A fresh, signed-in page. Used wherever the journey says COLD — a new page
 *  object is the only way to prove a value came from the server rather than
 *  from component state that never unmounted. */
async function freshPage() {
  const pg = await b.newPage({ viewport: { width: 1360, height: 2000 } });
  // A missing control must cost seconds, not half a minute: this walk presses
  // a lot of things that may legitimately not be there, and the default 30s
  // turns "absent" into "the run never finishes".
  pg.setDefaultTimeout(12000);
  pg.on("response", (r) => {
    if (!r.url().includes("/api/") || r.status() < 400) return;
    // ⚠ **ONE DOCUMENTED 404 IS NOT AN ERROR AND MUST NOT BE REPORTED AS ONE.**
    // `GET .../interruption` answers 404 by design for a request that is
    // neither a fault report nor attached to an interruption — its own
    // docstring says so, because "a section that rendered for every request
    // would be an empty frame on every move-in in the product". Every ordinary
    // request therefore produces one, and a walk that files it as a fault is
    // crying wolf at the product working correctly.
    if (r.status() === 404 && /\/interruption$/.test(new URL(r.url()).pathname)) return;
    httpErrors.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`);
  });
  await pg.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await pg.fill("#signin-email", EMAIL);
  await pg.fill("#signin-password", PASSWORD);
  await Promise.all([
    pg.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    pg.click('button[type="submit"]'),
  ]);
  return pg;
}
const txt = (pg) => pg.evaluate(() => document.body.innerText);
const cont = async (pg) => {
  await pg.locator("button").filter({ hasText: /^Continue$/ }).first().click();
  await pg.waitForTimeout(2200);
};
const idOf = (pg) => new URL(pg.url()).searchParams.get("request");

/** Tick or untick a checkbox that may be visually replaced by a styled span.
 *  `locator.check()` times out on those — the real <input> is not the thing the
 *  clerk clicks — so this falls back to the LABEL, which is what a clerk
 *  actually presses, and only then to the input itself. Reported state is read
 *  back from the input either way, so a silent no-op cannot pass for a tick. */
async function setCheck(pg, id, want) {
  const el = pg.locator(`#${id}`);
  if (!(await el.count())) return null;
  if ((await el.isChecked()) === want) return want;
  const label = pg.locator(`label[for="${id}"]`);
  if (await label.count()) await label.first().click({ timeout: 8000 }).catch(() => {});
  if ((await el.isChecked()) !== want) await el.click({ force: true, timeout: 8000 }).catch(() => {});
  if ((await el.isChecked()) !== want)
    await el.evaluate((n, w) => { if (n.checked !== w) n.click(); }, want).catch(() => {});
  await pg.waitForTimeout(700);
  return await el.isChecked();
}

// The values the clerk types — ONE source, so the detail-page coverage matrix
// is built from the same object the wizard was filled from. A coverage check
// written from a second hand-made list drifts from the thing it measures.
const V = (tag) => ({
  applicant_name: `${tag} Rivera`,
  applicant_email: `rivera.${tag.toLowerCase()}@example.com`,
  applicant_phone: "555-0142",
  date_of_birth: "1984-03-11",
  drivers_licence: "TX4417882",
  ssn: "402-55-7781",
  co_applicant_name: `${tag} Okonkwo`,
  co_applicant_email: `okonkwo.${tag.toLowerCase()}@example.com`,
  co_applicant_phone: "555-0199",
  requested_start: "2026-11-02",
  // The mailing address is five parts since the free-text box was retired.
  billing_line1: "PO Box 7741",
  billing_city: "Silver Creek",
  billing_state: "TX",
  billing_postal_code: "78611",
  doc_proves: "Identity and current address",
  account_type_label: "Residential",
  address_unit_as_given: null,
  premises: null,
  services: [],
});

/** Fill all FOUR steps (PO approval 2026-09-29 — six became four; updated
 *  2026-10-11). Records WHEN a number first appears — check 1.1, which cannot
 *  be asked after the fact.
 *    1 · Applicant — the person, the category, the co-applicant, documents
 *    2 · Property  — the address, the unit, the mailing address
 *    3 · Service   — services, connection date, fees, *Payment details*
 *    4 · Review    — *Check and submit*, with *What the customer is told* */
async function fillFourSteps(pg, tag, { attach = true, fee = true } = {}) {
  const v = V(tag);
  const seen = {};
  await pg.goto(`${BASE}/${T}/requests/new?step=1`, { waitUntil: "networkidle" });
  await pg.waitForTimeout(2200);

  // ── STEP 1 · Applicant (customer category and documents live here now) ──
  seen.step1Fields = await pg.evaluate(() =>
    [...document.querySelectorAll("input,select,textarea")].filter((e) => e.id).map((e) => e.id));
  await pg.selectOption("#applicant_kind", { label: "A person" }).catch(() => {});
  await pg.fill("#applicant_name", v.applicant_name);
  await pg.fill("#applicant_email", v.applicant_email);
  await pg.fill("#applicant_phone", v.applicant_phone);
  await pg.fill("#date_of_birth", v.date_of_birth).catch(() => {});
  await pg.fill("#drivers_licence", v.drivers_licence).catch(() => {});
  await pg.fill("#ssn", v.ssn).catch(() => {});
  await pg.selectOption("#account_type_code", { label: "Residential" })
    .catch(async () => { await pg.selectOption("#account_type_code", { index: 1 }); });
  const coOn = await setCheck(pg, "add_co_applicant", true);
  seen.coApplicantOpened = coOn;
  if (coOn === true) {
    await pg.waitForTimeout(800);
    for (const [id, val] of [["#co_applicant_name", v.co_applicant_name],
                             ["#co_applicant_email", v.co_applicant_email],
                             ["#co_applicant_phone", v.co_applicant_phone]])
      if (await pg.locator(id).count()) await pg.fill(id, val);
  }
  seen.idAfterStep1 = idOf(pg);
  await cont(pg);

  // ── STEP 2 · Property ──
  seen.idAtStep2 = idOf(pg);
  const s2 = await txt(pg);
  seen.step2Footer = s2.split("\n").find((l) => /Not saved yet|already allocated|Saved as draft/.test(l)) ?? null;
  // Documents are attached on step 1's panel, and a document needs a saved
  // draft — which exists from here on — so the walk goes back for it.
  if (attach && seen.idAtStep2) {
    await pg.locator("button").filter({ hasText: /^Back$/ }).first().click();
    await pg.waitForTimeout(1800);
    if (await pg.locator("#capture-doc-file").count()) {
      await pg.selectOption("#capture-doc-type", { index: 1 }).catch(() => {});
      await pg.setInputFiles("#capture-doc-file", FILE_PATH);
      await pg.fill("#capture-doc-proves", v.doc_proves).catch(() => {});
      await setCheck(pg, "capture-doc-required", true);
      await pg.locator("[data-doc-attach]").click().catch(() => {});
      await pg.waitForTimeout(3200);
    }
    await cont(pg);
  }
  // ⚠ 2026-10-11: `Mill Pond`'s first match holds ONE unit and it is
  // occupied, so a move-in onto it can never be approved and 4.approve-b
  // measured the fixture. `500 Main St` (P-00059) holds a run of VACANT units
  // at the end of its list; the walk takes a random one of the last fifteen so
  // successive runs do not queue move-ins onto the same unit. `CW_ADDRESS` /
  // `CW_UNIT` pin them.
  await pg.fill("#address_as_given", ADDRESS);
  await pg.waitForTimeout(3400);
  const opt = pg.locator("[data-premises-option]");
  if (await opt.count()) {
    v.premises = await opt.first().getAttribute("data-premises-option");
    await opt.first().click(); await pg.waitForTimeout(2000);
  }
  const unitSel = pg.locator("#address_unit_as_given");
  if ((await unitSel.count()) && (await unitSel.evaluate((e) => e.tagName)) === "SELECT") {
    const uo = (await unitSel.locator("option").allTextContents()).map((s) => s.trim())
      .filter((s) => s && !/^(—|Choose|Select|No unit|Whole)/i.test(s));
    const pickUnit = process.env.CW_UNIT
      ? uo.find((label) => label.includes(process.env.CW_UNIT))
      : uo.slice(-15)[Math.floor(Math.random() * Math.min(15, uo.length))];
    if (pickUnit) { await unitSel.selectOption({ label: pickUnit }).catch(() => {}); v.address_unit_as_given = pickUnit; }
  }
  // The mailing address is five parts now (the free-text box is retired).
  await setCheck(pg, "billing_address_same", false);
  if (await pg.locator("#billing_line1").count()) {
    await pg.fill("#billing_line1", v.billing_line1);
    await pg.fill("#billing_city", v.billing_city);
    await pg.fill("#billing_state", v.billing_state);
    await pg.fill("#billing_postal_code", v.billing_postal_code);
  }
  await cont(pg);
  seen.idAfterStep3 = idOf(pg); // "a row exists by the end of the property step"

  // ── STEP 3 · Service — services, connection date, fees, Payment details ──
  for (let i = 0; i < 2; i++) {
    const add = pg.locator("[data-add-service]");
    if (!(await add.count()) || (await add.isDisabled())) break;
    await add.click(); await pg.waitForTimeout(500);
    const sel = pg.locator(`#service_row_${i}`);
    if (!(await sel.count())) break;
    const opts = (await sel.locator("option").evaluateAll((ns) => ns.map((o) => [o.value, o.textContent.trim()])))
      .filter(([val]) => val);
    if (!opts.length) break;
    await sel.selectOption(opts[0][0]).catch(() => {});
    v.services.push(opts[0][1]);
    await pg.waitForTimeout(1200);
  }
  if (await pg.locator("#requested_start").count()) await pg.fill("#requested_start", v.requested_start);
  const addFee = pg.locator("[data-add-fee]");
  // The four action requests carry NO fee: an unpaid, unwaived fee blocks
  // Approve (`fee_settled`, PO 2026-09-23 — *"either fee is paid or waived"*),
  // and this walk takes no tender (see Payment details below).
  if (fee && (await addFee.count()) && !(await addFee.isDisabled())) {
    await addFee.click(); await pg.waitForTimeout(800);
    const fees = (await pg.locator("#fee_row_0 option").evaluateAll((ns) => ns.map((o) => o.value))).filter(Boolean);
    if (fees.length) { await pg.selectOption("#fee_row_0", fees[0]); await pg.waitForTimeout(2500); }
  }
  seen.step5Text = await txt(pg);
  seen.step5Fields = await pg.evaluate(() =>
    [...document.querySelectorAll("input,select,textarea")].filter((e) => e.id).map((e) => e.id));
  // *Payment details* (2026-10-11): Pay now → a method, its own inputs
  // (Cash: received and change due) and a receipt number. The walk fills Cash
  // to read the change due, then SUBMITS ON *Pay later*: a tender taken at
  // the counter needs an OPEN counter (`BR-PAY-1186` — "Start your counter
  // first."), which this walk does not open, and Pay later sends no tender.
  const payNow = pg.locator('[data-pay-option="collect_now"]');
  seen.payDetails = (await payNow.count()) > 0;
  if (seen.payDetails) {
    await payNow.click(); await pg.waitForTimeout(600);
    await pg.selectOption("#fee_method", "cash").catch(() => {});
    await pg.waitForTimeout(600);
    await pg.fill("#cash_received", "100").catch(() => {});
    await pg.fill("#fee_receipt_no", `${tag}-R`).catch(() => {});
    seen.cashChange = await pg.inputValue("#cash_change").catch(() => null);
    await pg.locator('[data-pay-option="collect_later"]').click().catch(() => {});
    await pg.waitForTimeout(600);
  }
  await cont(pg);

  // ── STEP 4 · Check and submit ──
  seen.step6Text = await txt(pg);
  seen.id = idOf(pg);
  const m = seen.step6Text.match(/SR-\d\d-\d+/);
  seen.request_no = m ? m[0] : null;
  return { v, seen };
}

let page = null;
try {
// ═══════════════════════════════════════════════════════════════════════════
// CASE 1 · EVERY FIELD, THEN SAVE AS DRAFT
// ═══════════════════════════════════════════════════════════════════════════
page = await freshPage();
ok("signed in as the clerk", !page.url().endsWith("/signin"), page.url());

const c1tag = `${TAG}-D`;
const c1 = await fillFourSteps(page, c1tag);
manifest.cases.draft = { tag: c1tag, id: c1.seen.id, request_no: c1.seen.request_no, values: c1.v };

ok("1.1 · a number exists once the applicant is named (leaving step 1)",
   c1.seen.idAtStep2 !== null,
   c1.seen.idAtStep2 === null ? `NO ROW at step 2 — the screen said: "${c1.seen.step2Footer}"` : c1.seen.idAtStep2);
if (c1.seen.idAtStep2 === null)
  friction("A request has no number until step 3, so the clerk cannot quote one at the counter",
    `The blueprint is explicit: a draft "carries its number from the moment it is started. The clerk can quote it to somebody still standing at the counter." It does not. ` +
    `Steps 1 and 2 live in the browser only; the row is created when an ADDRESS is typed on step 3. The product says so itself on step 2: "${c1.seen.step2Footer}". ` +
    `Two screens of typing — name, email, phone, date of birth, licence, SSN, co-applicant, category, services, start date — are held nowhere until then.`);
ok("1.1b · a row exists by the end of the property step", c1.seen.idAfterStep3 !== null, String(c1.seen.idAfterStep3));
ok("1.1c · the review step shows the allocated number", c1.seen.request_no !== null, String(c1.seen.request_no));

const saveDraft = page.locator("button").filter({ hasText: /^Save as draft$/ });
ok("1.2a · a Save as draft control is on the screen", (await saveDraft.count()) > 0);
if (await saveDraft.count()) { await saveDraft.first().click(); await page.waitForTimeout(3200); }
const afterSave = await txt(page);
ok("1.2 · the screen confirms the draft was saved", /Saved as draft/.test(afterSave),
   (afterSave.split("\n").find((l) => /Saved as draft/.test(l)) || "").trim());

// the register
await page.goto(`${BASE}/${T}/requests`, { waitUntil: "networkidle" });
await page.waitForTimeout(3000);
const reg = await txt(page);
ok("1.4 · the draft is in the register",
   reg.includes(c1tag) || (c1.seen.request_no && reg.includes(c1.seen.request_no)),
   c1.seen.request_no ?? c1tag);
ok("1.2b · and the register shows it as a Draft", /Draft/.test(reg));
manifest.cases.draft.registerHasIt = reg.includes(c1tag) || (c1.seen.request_no ? reg.includes(c1.seen.request_no) : false);

// ── 1.3 · CLOSE IT AND COME BACK COLD ──
await page.close();
page = await freshPage();
const readBack = {};
for (const step of [1, 2, 3, 4]) {
  await page.goto(`${BASE}/${T}/requests/new?request=${c1.seen.id}&step=${step}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2800);
  readBack[`step${step}`] = await page.evaluate(() => {
    const vals = {};
    for (const el of document.querySelectorAll("input,select,textarea")) {
      if (!el.id) continue;
      vals[el.id] = el.type === "checkbox" ? el.checked : el.value;
      if (el.placeholder) vals[`${el.id}@placeholder`] = el.placeholder;
    }
    return { vals, body: document.body.innerText };
  });
}
manifest.cases.draft.readBack = Object.fromEntries(Object.entries(readBack).map(([k, v]) => [k, v.vals]));
const rb = (id) => { for (const s of Object.values(readBack)) if (id in s.vals && String(s.vals[id]).trim() !== "") return s.vals[id];
                     for (const s of Object.values(readBack)) if (id in s.vals) return s.vals[id];
                     return undefined; };
const want = [
  ["applicant_name", c1.v.applicant_name], ["applicant_email", c1.v.applicant_email],
  ["applicant_phone", c1.v.applicant_phone], ["date_of_birth", c1.v.date_of_birth],
  ["drivers_licence", c1.v.drivers_licence], ["ssn", c1.v.ssn],
  ["co_applicant_name", c1.v.co_applicant_name], ["co_applicant_email", c1.v.co_applicant_email],
  ["co_applicant_phone", c1.v.co_applicant_phone], ["requested_start", c1.v.requested_start],
  ["billing_line1", c1.v.billing_line1], ["billing_city", c1.v.billing_city],
  ["billing_postal_code", c1.v.billing_postal_code],
];
const lostCold = [];
for (const [id, w] of want) {
  const got = rb(id);
  let survived = got !== undefined && String(got).trim() !== "" &&
    (String(got).trim() === String(w).trim() || String(got).includes(String(w)));
  // ⚠ SSN and Driver's license are MASKED: a saved one never comes back as
  // its value — the box opens empty with the last four as its placeholder
  // (`ssnOnFileMask` / `licenceOnFileMask`), and typing replaces it. So the
  // survival test for those two is the placeholder carrying the last four.
  if (!survived && (id === "ssn" || id === "drivers_licence")) {
    const ph = rb(`${id}@placeholder`);
    survived = typeof ph === "string" && ph.endsWith(String(w).slice(-4));
  }
  if (!survived) lostCold.push(`${id}: typed "${w}", came back ${got === undefined ? "NO SUCH FIELD ON ANY STEP" : `"${got}"`}`);
}
ok("1.3 · every field of all four steps survives a cold reopen", lostCold.length === 0,
   lostCold.length ? `${lostCold.length} lost → ${lostCold.join(" | ")}` : "all present");
if (lostCold.length)
  friction("Fields the clerk typed are empty when the draft is reopened",
    `The wizard was closed, the browser signed in again on a new page, and the draft reopened by its id. ` +
    `${lostCold.length} field(s) came back blank or had no home at all: ${lostCold.join(" ; ")}. ` +
    `Nothing tells the clerk — the step just looks unfilled, so it gets typed a second time, or worse, it is assumed saved and is not.`);
manifest.cases.draft.lostCold = lostCold;

// ── 1.5 · the document and its BYTES ──
const docState = await page.evaluate(async ([tenant, id]) => {
  const tab = await (await fetch(`/api/${tenant}/service-requests/${id}/documents`, { headers: { Accept: "application/json" } })).json();
  const docs = (tab.data ?? tab).documents ?? [];
  const mine = docs.find((d) => d.file_present === true) ?? docs[0] ?? null;
  let status = null, url = null, body = null;
  if (mine) {
    const lr = await fetch(`/api/${tenant}/service-requests/${id}/documents/${mine.id}/download`, { headers: { Accept: "application/json" } });
    status = lr.status;
    // the envelope is `{data:{url}}` on some doors and `{url}` on others; a
    // check that knows only one shape reports a working download as broken.
    if (lr.ok) { const j = await lr.json(); url = (j.data ?? j)?.url ?? j?.url ?? null; body = JSON.stringify(j).slice(0, 200); }
  }
  return { count: docs.length, mine, status, url, body };
}, [T, c1.seen.id]);
ok("1.5a · the document attached on the draft is still there", docState.count > 0, `${docState.count} row(s)`);
ok("1.5b · the server agrees a real file is held", docState.mine?.file_present === true, String(docState.mine?.file_present));
ok("1.5c · a download is issued for it", docState.status === 200 && !!docState.url,
   `HTTP ${docState.status} · body ${docState.body}`);
ok("1.5d · the stored size equals the bytes handed in", docState.mine?.size_bytes === FILE_BODY.length,
   `${docState.mine?.size_bytes} vs ${FILE_BODY.length}`);
manifest.cases.draft.document = { id: docState.mine?.id ?? null, size: docState.mine?.size_bytes ?? null, bytes: FILE_BODY.length };

// ═══════════════════════════════════════════════════════════════════════════
// CASE 2 · EVERY FIELD, THEN SUBMIT
// ═══════════════════════════════════════════════════════════════════════════
await page.close();
page = await freshPage();
const c2tag = `${TAG}-S`;
const c2 = await fillFourSteps(page, c2tag);
manifest.cases.submitted = { tag: c2tag, id: c2.seen.id, request_no: c2.seen.request_no, values: c2.v };
const submitBtn = page.locator("button").filter({ hasText: /Submit the request/ });
ok("2.0 · a Submit control is on the review step", (await submitBtn.count()) > 0);
if (await submitBtn.count()) { await submitBtn.first().click(); await page.waitForTimeout(4000); }
const afterSubmit = await txt(page);
manifest.cases.submitted.afterSubmitUrl = page.url();
manifest.cases.submitted.afterSubmitTail = afterSubmit.split("\n").filter(Boolean).slice(-14).join(" | ");
// Two ways for the product to tell the clerk it worked: take them to the
// request, or say so on the step. Either is fine; NEITHER is the friction.
const wentToRequest = new RegExp(`/requests/${c2.seen.id}`).test(page.url());
// ⚠ "Draft → Submitted" is the review's own forecast and is on the page
// BEFORE the press, so it is not an answer; a refusal banner says it failed.
const refusedSubmit = /could not submit/i.test(afterSubmit);
// The submitted screen is a confirmation panel: *What happens next*, with
// *Capture another* and *Open the request*.
const saidSo = !refusedSubmit && (/has been submitted|Request submitted|What happens next|Open the request/.test(afterSubmit.replace(/Draft → Submitted/g, "")));
ok("2.1 · the clerk is told the request was submitted",
   !refusedSubmit && (wentToRequest || saidSo),
   `url=${page.url()} · last lines: ${manifest.cases.submitted.afterSubmitTail}`);
if (!(wentToRequest || saidSo))
  friction("Pressing Submit leaves the clerk on the same screen with no confirmation",
    `After "Submit the request ✓" the browser stayed on the review step (${page.url()}) and the page never said the request was submitted. ` +
    `The request IS submitted in the database — so the clerk has done the job and cannot tell, and the natural response is to press Submit again.`);

// register + waiting-on
await page.goto(`${BASE}/${T}/requests`, { waitUntil: "networkidle" });
await page.waitForTimeout(3000);
const reg2 = await txt(page);
ok("2.0b · Pay now offers Cash with a change due", c2.seen.payDetails === true && /\d/.test(c2.seen.cashChange ?? ""),
   `change due = ${c2.seen.cashChange}`);
ok("2.2 · the submitted request is in the register",
   reg2.includes(c2tag) || (c2.seen.request_no && reg2.includes(c2.seen.request_no)), c2.seen.request_no ?? c2tag);

// ═══════════════════════════════════════════════════════════════════════════
// OPEN IT — EVERY CAPTURED FIELD MUST HAVE A HOME ON THE DETAIL PAGE
// ═══════════════════════════════════════════════════════════════════════════
await page.goto(`${BASE}/${T}/requests/${c2.seen.id}`, { waitUntil: "networkidle" });
await page.waitForTimeout(3500);
let detail = await txt(page);
// the detail page is tabbed — collect every tab's text, because a field with a
// home on another tab is FOUND, not missing, and reporting it missing would be
// this walk making the very mistake it exists to catch.
const tabNames = await page.evaluate(() =>
  [...document.querySelectorAll('[role="tab"], [data-tab], nav button')].map((e) => e.textContent.trim()).filter(Boolean));
const tabTexts = { "(landing)": detail };
for (const name of [...new Set(tabNames)]) {
  const tb = page.locator(`[role="tab"]:text-is("${name}"), button:text-is("${name}")`).first();
  if (!(await tb.count())) continue;
  await tb.click().catch(() => {});
  await page.waitForTimeout(1800);
  tabTexts[name] = await txt(page);
}
const allDetail = Object.values(tabTexts).join("\n");
manifest.cases.submitted.tabs = Object.keys(tabTexts);

const expect = [
  ["Full name", c2.v.applicant_name], ["Email", c2.v.applicant_email],
  ["Phone", c2.v.applicant_phone], ["Date of birth", c2.v.date_of_birth],
  ["Driver's licence (last 4)", c2.v.drivers_licence.slice(-4)],
  ["Social Security Number (last 4)", c2.v.ssn.slice(-4)],
  ["Co-applicant name", c2.v.co_applicant_name],
  ["Co-applicant email", c2.v.co_applicant_email],
  ["Co-applicant phone", c2.v.co_applicant_phone],
  ["Requested start / connection date", c2.v.requested_start],
  ["Billing address", "PO Box 7741"],
  ["What the document proves", c2.v.doc_proves],
  ["Premises", c2.v.premises],
  // A REQUIRED field on step 2 (`Customer category*`). The server stores it and
  // `customer_category()` serves it on the Applicant tab's payload, so if it is
  // not on screen the loss is at the last hop.
  ["Customer category", c2.v.account_type_label],
];
const missing = [];
for (const [label, value] of expect) {
  if (value === null || value === undefined || value === "") continue;
  const shown = allDetail.includes(String(value)) ||
    // a date may be rendered in a human format
    (/^\d{4}-\d{2}-\d{2}$/.test(String(value)) && (() => {
      const d = new Date(String(value) + "T00:00:00Z");
      const alts = [
        d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }),
        d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }),
        `${String(d.getUTCMonth() + 1).padStart(2, "0")}/${String(d.getUTCDate()).padStart(2, "0")}/${d.getUTCFullYear()}`,
      ];
      return alts.some((a) => allDetail.includes(a));
    })());
  if (!shown) {
    // Record what the page DOES say near that idea, so a missing field can be
    // told apart from one merely rendered in a format this check did not guess.
    const key = label.split(/[ /]/)[0].toLowerCase();
    const near = allDetail.split("\n").filter((l) => l.toLowerCase().includes(key)).slice(0, 3).join(" ¶ ");
    missing.push(`${label} = "${value}"${near ? ` (page says near "${key}": ${near})` : " (no line mentions it at all)"}`);
  }
}
ok("3.1 · every field captured across the four steps appears on the detail page",
   missing.length === 0, missing.length ? `${missing.length} with no home → ${missing.join(" | ")}` : "all present");
if (missing.length)
  friction("Facts the clerk typed never appear again on the request",
    `Opened the submitted request and read every tab (${Object.keys(tabTexts).join(", ")}). ` +
    `${missing.length} captured value(s) are shown nowhere: ${missing.join(" ; ")}. ` +
    `The clerk typed them, the product took them, and there is no screen that gives them back — so nobody can check them, correct them, or answer a question about them.`);
manifest.cases.submitted.missingOnDetail = missing;

// the untranslated-key check — a raw i18n key on a clerk screen is a code on
// screen, which B14 rule 32 forbids outright.
const keyRe = /\b[a-z]+(?:\.[a-zA-Z]+){2,}\b/g;
const prefix = /^(customers|shell|common|billing|payments)\./;
const keysOn = (t) => [...new Set((t || "").match(keyRe) || [])].filter((k) => prefix.test(k));
const detailKeys = keysOn(allDetail);
const wizardKeys = keysOn(c2.seen.step6Text);
const rawKeys = [...new Set([...detailKeys, ...wizardKeys])];
manifest.cases.submitted.rawKeys = { detail: detailKeys, wizardStep6: wizardKeys };
ok("3.2 · no untranslated message key is printed on a clerk screen", rawKeys.length === 0,
   `detail page: ${detailKeys.join(", ") || "none"} · wizard review step: ${wizardKeys.join(", ") || "none"}`);
if (rawKeys.length)
  friction("The screen prints internal message codes at the clerk",
    `These appeared as visible text instead of English — on the detail page: ${detailKeys.join(", ") || "none"}; ` +
    `on the wizard's review step: ${wizardKeys.join(", ") || "none"}. A clerk cannot act on them and cannot read them out to an applicant.`);

// ═══════════════════════════════════════════════════════════════════════════
// THE FOUR ACTIONS — one request each, because two of them are terminal
// ═══════════════════════════════════════════════════════════════════════════
async function makeSubmitted(label) {
  await page.close();
  page = await freshPage();
  const tag = `${TAG}-${label}`;
  const r = await fillFourSteps(page, tag, { attach: false, fee: false });
  const sb = page.locator("button").filter({ hasText: /Submit the request/ });
  if (await sb.count()) { await sb.first().click(); await page.waitForTimeout(4000); }
  manifest.actions[label] = { tag, id: r.seen.id, request_no: r.seen.request_no };
  return r;
}

/** Open a request's detail page and press one of the four head buttons. */
async function pressAction(id, buttonText) {
  await page.goto(`${BASE}/${T}/requests/${id}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3200);
  const btn = page.locator("button").filter({ hasText: new RegExp(`^${buttonText}$`) }).first();
  const present = (await btn.count()) > 0;
  const enabled = present ? await btn.isEnabled() : false;
  if (present && enabled) { await btn.click(); await page.waitForTimeout(2200); }
  return { present, enabled };
}

// ⚠ **EVERY DIALOG IS DRIVEN BY ITS REAL CONTROL IDS AND ITS REAL SUBMIT
// LABEL, AND THE FIRST RUN OF THIS WALK IS WHY.** It pressed a generic
// `select`/`textarea`/`^(Park|Save|Confirm)$` and reported that Park and Ask
// for more did nothing — over a product where both work. The submit buttons
// read `Park ✓` and `Ask and queue the message`, `waiting_on` is a TEXT field
// and not a select, and the outcome is a RADIO. A walk that mis-drives a
// dialog and files the result as a product defect is worse than no walk, so
// each control below is named from the component, and `filledOk` records
// whether the walk actually managed to fill the thing it meant to.
const DIALOG = {
  PARK:    { submit: "Park ✓" },
  ASK:     { submit: "Ask and queue the message" },
  REFUSE:  { submit: "Refuse the request" },
  APPROVE: { submit: "Approve and raise the build" },
};
// ⊕ 2026-10-11: Approve's commit is named per kind — "Approve and raise the
// build" for a new connection, "Approve" for a move-in.
const submitBtnFor = (key) =>
  key === "APPROVE"
    ? page.locator('[role="dialog"] button').filter({ hasText: /^(Approve and raise the build|Approve)$/ }).last()
    : page.locator("button").filter({ hasText: new RegExp(`^${DIALOG[key].submit.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`) }).last();

// ── PARK · Submitted becomes Under review ──
const rPark = await makeSubmitted("PARK");
const parkBtn = await pressAction(rPark.seen.id, "Park");
ok("4.park · a Park control is on the request", parkBtn.present && parkBtn.enabled, JSON.stringify(parkBtn));
if (parkBtn.present && parkBtn.enabled) {
  manifest.actions.PARK.dialogFields = await page.evaluate(() =>
    [...document.querySelectorAll("input,select,textarea")].filter((e) => e.id).map((e) => e.id));
  await page.fill("#waiting_on", "A supervisor").catch(() => {});
  await page.fill("#note", `${TAG} parked by the clerk walk`).catch(() => {});
  manifest.actions.PARK.filledOk = await page.inputValue("#waiting_on").catch(() => null);
  const sb = submitBtnFor("PARK");
  manifest.actions.PARK.submitFound = (await sb.count()) > 0;
  if (await sb.count()) { await sb.click().catch(() => {}); await page.waitForTimeout(3500); }
}

// ── ASK FOR MORE · waiting-on moves to the applicant, a message is sent ──
const rAsk = await makeSubmitted("ASK");
const askBtn = await pressAction(rAsk.seen.id, "Ask for more");
ok("4.ask · an Ask for more control is on the request", askBtn.present && askBtn.enabled, JSON.stringify(askBtn));
if (askBtn.present && askBtn.enabled) {
  // the tick-list of what is needed lives inside the dialog
  const boxIds = await page.evaluate(() =>
    [...document.querySelectorAll('input[type="checkbox"]')].map((e) => e.id).filter(Boolean));
  manifest.actions.ASK.dialogFields = boxIds;
  let ticked = 0;
  for (const bid of boxIds.slice(0, 2)) { if ((await setCheck(page, bid, true)) === true) ticked++; }
  manifest.actions.ASK.ticked = ticked;
  await page.fill("#ask_message_to_applicant", `${TAG} please send a utility bill and a photo ID.`).catch(() => {});
  const sb = submitBtnFor("ASK");
  manifest.actions.ASK.submitFound = (await sb.count()) > 0;
  if (await sb.count()) { await sb.click().catch(() => {}); await page.waitForTimeout(3500); }
}

// ── REFUSE · a reason is REQUIRED, the applicant is told, the fee stays ──
const rRef = await makeSubmitted("REFUSE");
const refBtn = await pressAction(rRef.seen.id, "Refuse");
ok("4.refuse · a Refuse control is on the request", refBtn.present && refBtn.enabled, JSON.stringify(refBtn));
if (refBtn.present && refBtn.enabled) {
  // FIRST, with NO reason chosen, to prove a reason is genuinely required.
  const sbFirst = submitBtnFor("REFUSE");
  let blocked = null;
  if (await sbFirst.count()) {
    if (!(await sbFirst.isEnabled())) blocked = true;
    else {
      await sbFirst.click().catch(() => {});
      await page.waitForTimeout(2500);
      const after = await txt(page);
      // still on the dialog, or an explicit complaint = refused
      blocked = /required|choose|select a reason|Refuse .*\d/i.test(after);
    }
  }
  ok("4.refuse-b · a reason is required before a refusal can be sent", blocked === true, String(blocked));
  if (blocked !== true)
    friction("A request can be refused without saying why",
      `The Refuse dialog's "${DIALOG.REFUSE.submit}" was live with no reason chosen and the refusal went through. A refusal with no recorded reason cannot be explained to the applicant afterwards.`);
  await page.selectOption("#reason_code", { index: 1 }).catch(() => {});
  await page.fill("#message_to_applicant", `${TAG} the premises already has an open account.`).catch(() => {});
  manifest.actions.REFUSE.filledOk = await page.inputValue("#reason_code").catch(() => null);
  const sb = submitBtnFor("REFUSE");
  manifest.actions.REFUSE.submitFound = (await sb.count()) > 0;
  if (await sb.count()) { await sb.click().catch(() => {}); await page.waitForTimeout(3500); }
}

// ── APPROVE · approved, the build is raised, money travels; nothing energised ──
const rApp = await makeSubmitted("APPROVE");
const appBtn = await pressAction(rApp.seen.id, "Approve");
ok("4.approve · an Approve control is on the request", appBtn.present && appBtn.enabled, JSON.stringify(appBtn));
if (appBtn.present && appBtn.enabled) {
  // ⚠ **PICK AN OUTCOME THE SERVER CALLS `possible`, NOT THE FIRST RADIO.**
  // The decision payload grades all five, and on a served-and-occupied premises
  // `new_connection` is `not_possible` — so a walk that clicks radio one is
  // asking to approve something the product has already said no to, and then
  // reports the greyed button as a defect.
  const graded = await page.evaluate(async ([t, id]) => {
    const j = await (await fetch(`/api/${t}/service-requests/${id}`, { headers: { Accept: "application/json" } })).json();
    return ((j.data ?? j).decision?.options ?? []).map((o) => [o.outcome, o.verdict]);
  }, [T, manifest.actions.APPROVE.id]);
  manifest.actions.APPROVE.graded = graded;
  const possible = (graded.find(([, v]) => v === "possible") || [])[0] ?? null;
  manifest.actions.APPROVE.chose = possible;
  // ⚠ 2026-10-11: the kind is the Approve window's `SegmentedControl`
  // (`data-segmented="approve-kind"`), not radios, since the 2026-09-23
  // rebuild — and it offers two kinds, so `possible` may name one it lacks.
  const segment = (kind) => page.locator(`[data-segmented="approve-kind"] [data-segment="${kind}"]`).first();
  const pick = async () => {
    const seg = possible && (await segment(possible).count()) ? segment(possible)
      : page.locator('[data-segmented="approve-kind"] [data-segment]:not([disabled])').first();
    if (await seg.count()) await seg.click().catch(() => {});
    await page.waitForTimeout(1200);
  };
  await pick();

  // ⚠⚠ **THE ARREARS SEARCH IS THE ONLY THING IN THE PRODUCT THAT SETS
  // `search_done`, AND WITHOUT IT NO REQUEST CAN EVER BE APPROVED.** Since
  // 2026-10-11 (PO, option B) the Arrears row only POINTS at *Search
  // customer* (`[data-approve-arrears-search]`, "Search customer below."); the
  // clerk runs that search (`[data-customer-search]`) and answers it with
  // *Link* or *No match* (`data-action="record-search"`). So the real
  // sequence is pick → search → No match → approve.
  manifest.actions.APPROVE.arrearsPointer =
    ((await page.locator("[data-approve-arrears-search]").first().textContent().catch(() => null)) ?? "").trim() || null;
  manifest.actions.APPROVE.recordSearchOffered = false;
  if (manifest.actions.APPROVE.arrearsPointer !== null) {
    await page.locator("[data-customer-search]").first().click().catch(() => {});
    const noMatch = page.locator('[data-action="record-search"]').first();
    await noMatch.waitFor({ timeout: 15000 }).catch(() => {});
    manifest.actions.APPROVE.recordSearchOffered = (await noMatch.count()) > 0;
    if (manifest.actions.APPROVE.recordSearchOffered) { await noMatch.click().catch(() => {}); await page.waitForTimeout(3000); }
    // re-picking is harmless and the dialog may have re-rendered on the post
    await pick();
  }
  ok("4.approve-a · the Arrears row points at Search customer, with no button of its own",
     manifest.actions.APPROVE.arrearsPointer === null ||
       (manifest.actions.APPROVE.arrearsPointer === "Search customer below." &&
        (await page.locator("[data-approve-arrears-search] button").count()) === 0),
     String(manifest.actions.APPROVE.arrearsPointer));
  // The decision payload grades a kind `possible` while the window's own
  // checks may still block it (a matched premises reads "In Premises · use a
  // move-in" under New connection), so if the first pick leaves the commit
  // refused the walk tries the other kind the window offers, as a clerk would.
  if (!(await submitBtnFor("APPROVE").isEnabled().catch(() => false))) {
    for (const kind of await page.locator('[data-segmented="approve-kind"] [data-segment]:not([disabled])')
      .evaluateAll((ns) => ns.map((n) => n.getAttribute("data-segment")))) {
      await segment(kind).click().catch(() => {});
      await page.waitForTimeout(1000);
      if (await submitBtnFor("APPROVE").isEnabled().catch(() => false)) break;
    }
  }
  manifest.actions.APPROVE.picked = await page.evaluate(() =>
    document.querySelector('[data-segmented="approve-kind"] [data-segment][aria-checked="true"]')?.getAttribute("data-segment") ?? null);
  const sb = submitBtnFor("APPROVE");
  manifest.actions.APPROVE.submitFound = (await sb.count()) > 0;
  manifest.actions.APPROVE.submitEnabled = (await sb.count()) ? await sb.isEnabled() : null;
  ok("4.approve-b · after picking an outcome and answering the search, Approve is live",
     manifest.actions.APPROVE.submitEnabled === true,
     `outcome=${manifest.actions.APPROVE.picked} noMatchOffered=${manifest.actions.APPROVE.recordSearchOffered}`);
  // The friction this walk filed here ("the clerk attests to a search the
  // product cannot run") was answered: the search runs (`DEF-CUS-9043`) and
  // No match is its answer (PO 2026-10-11, option B). Not re-filed.
  if (await sb.count()) { await sb.click().catch(() => {}); await page.waitForTimeout(4500); }
  manifest.actions.APPROVE.afterText = (await txt(page)).slice(0, 1600);
}

// what the screen claims, for comparison against the database in the readback
for (const k of ["PARK", "ASK", "REFUSE", "APPROVE"]) {
  if (!manifest.actions[k]) continue;
  await page.goto(`${BASE}/${T}/requests/${manifest.actions[k].id}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2800);
  const t = await txt(page);
  manifest.actions[k].screenState =
    (t.match(/\b(Draft|Submitted|Under review|More info|Approved|Refused|In fulfilment|Withdrawn)\b/) || [null])[0];
}

manifest.httpErrors = [...new Set(httpErrors)];
ok("no API call failed during the walk", httpErrors.length === 0, [...new Set(httpErrors)].join(" | ") || "none");
if (httpErrors.length)
  friction("The product returned errors while the clerk worked",
    `${[...new Set(httpErrors)].length} distinct failing API call(s) during an ordinary walk: ${[...new Set(httpErrors)].join(" ; ")}.`);

} catch (err) {
  ok("the walk ran to the end", false, String(err).split("\n")[0]);
} finally {
  writeFileSync(MANIFEST, JSON.stringify(manifest, null, 1));
  console.log("\n════════ CHECKS ════════");
  console.log(R.join("\n"));
  console.log(`\n${R.filter((r) => r.startsWith("PASS")).length} PASS · ${R.filter((r) => r.startsWith("FAIL")).length} FAIL`);
  console.log("\n════════ FRICTION ════════");
  FRICTION.forEach((f, i) => console.log(`\n${i + 1}. ${f.title}\n   ${f.detail}`));
  if (!FRICTION.length) console.log("(none recorded by this script)");
  console.log(`\nmanifest → ${MANIFEST}`);
  console.log(`TAG=${TAG}  ← purge with po20260919_clerk_walk_purge.py`);
  await b.close();
  process.exit(R.some((r) => r.startsWith("FAIL")) ? 1 : 0);
}
