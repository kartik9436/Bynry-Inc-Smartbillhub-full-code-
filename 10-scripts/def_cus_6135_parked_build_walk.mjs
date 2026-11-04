// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-6135 (parking a draft build and finishing it made a SECOND
//          build, and left the draft row behind as a third) · DEF-CUS-6132 (a
//          clerk could not get back into a draft build at all)
// Rules:   BR-SHL-048 (d), CONFIRMED-AS-AMENDED 2026-09-21 — PO verbatim:
//          *"this is big problem - we cannot create two build - you can update
//          the existing build"* · BR-MET-112 (nothing is written until the
//          last button) · CLAUDE.md hard-won law 6 (no gate reads rendered
//          output, so this is the only thing that can see the screen)
// Process: 12-governance/22-product-maintenance-process.md §0 REPRODUCE and §4
//          PROVE IT AGAINST THE REPRODUCTION
// ───────────────────────────────────────────────────────
//
// **THE CLERK'S WHOLE DAY, IN ONE RUN.** `PHASE=park` in
// `cr126_s9_request_to_record_walk.mjs` reproduced the first half of this
// defect and stopped at step 1 — the resumed wizard refused on *"Add the Tax
// ID."* and `POST /connections/commit` was never called, so it could say the
// park had forgotten the build and could NOT say what the last press then did.
// This finishes the walk.
//
// ⚠ **THE VERDICT IS `commit.id`, NEVER A COUNT (`DEF-CUS-6135`'s own trap).**
// `GET /connections` counts ROWS ON THE LIST, and that list draws parked
// wizards as rows too — so parking twice moves its envelope by two with nothing
// committed at all. The first version of the check that found this defect did
// exactly that and announced *"a SECOND build was created"* over a run in which
// nothing was written. The id needs no denominator: the SAME id means the draft
// was finished, a DIFFERENT one means a second build stands beside it. Where a
// figure below is rows rather than builds, its label says so.
//
// ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING** — a mid-run reseed
// looks exactly like a broken screen. `10-scripts/proof-db.sh clone <label>`.
//
//     10-scripts/proof-db.sh clone park1
//     DATABASE_URL=... ALLOWED_HOSTS='*' DJANGO_SETTINGS_MODULE=config.settings.local \
//       python manage.py runserver 127.0.0.1:8747 --noreload
//     cd 07-frontend && npx vite build
//     PORT=8746 STATIC_DIR=$PWD/dist API_PROXY_TARGET=http://127.0.0.1:8747 node server.mjs
//     BASE=http://127.0.0.1:8746 node 10-scripts/def_cus_6135_parked_build_walk.mjs
//
// ⚠ **PASS `STATIC_DIR` EXPLICITLY** — `server.mjs` resolves `dist/` from its
// OWN directory, so a lane in a `git worktree` that runs the shared checkout's
// copy serves the shared checkout's bundle however carefully it just built its
// own.
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright-core");

const BASE = process.env.BASE || "http://127.0.0.1:8746";
const T = process.env.TENANT || "brazosbend";
const EMAIL = process.env.EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const OUT = process.env.OUT || "/tmp/claude-0/park1-shots";
mkdirSync(OUT, { recursive: true });

const say = (...a) => console.log(...a);
const bad = [];
const note = (s) => say("  · " + s);
const fail = (s) => { bad.push(s); say("  ⛔ " + s); };
let presses = 0;
const press = (w) => { presses += 1; say(`  press ${presses}: ${w}`); };

const browser = await chromium.launch({ executablePath: CHROME });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1600 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => fail(`PAGEERROR ${e.message.slice(0, 150)}`));
await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);

const api = (p, init) =>
  page.evaluate(async ([pp, ii]) => {
    const r = await fetch(pp, ii || { headers: { accept: "application/json" } });
    return { status: r.status, body: await r.text() };
  }, [p, init]);
const shot = async (n) => { await page.waitForTimeout(400); await page.screenshot({ path: `${OUT}/p1-${n}.png`, fullPage: true }); };
const byLabel = async (label) => {
  for (const b of await page.$$("button")) if ((await b.innerText()).trim() === label) return b;
  return null;
};
const wizardForward = async (label) => {
  const buttons = await page.$$('[data-wizard="actions"] button');
  const last = buttons[buttons.length - 1];
  if (!last) { fail(`${label}: no wizard action buttons at all`); return false; }
  const text = (await last.innerText()).trim();
  if (await last.isDisabled()) { fail(`${label}: cannot advance — "${text}" is DISABLED`); return false; }
  await last.click(); press(`${label} → ${text}`);
  await page.waitForTimeout(1600);
  return true;
};
const pickRadio = async (name, value) => {
  const el = await page.$(`input[name="${name}"][value="${value}"]`);
  if (el === null) return false;
  await el.evaluate((n) => n.click());
  await page.waitForTimeout(250);
  return true;
};

/** Every row the New connects list serves, and which kind each is. */
const listRows = async () => {
  const body = JSON.parse((await api(`/api/${T}/connections?per=50`)).body || "{}");
  return body.results ?? body.data ?? [];
};
/** The BUILDS among them — a `connections` row has an `id` and a park does not. */
const buildNumbers = (rows) => rows.filter((r) => r.id).map((r) => r.connection_no).sort();

// ── 0 · THE STATE THE REPORTER WAS IN ───────────────────────────────────────
say("\n════ the draft a clerk is about to pick up ════");
const before = await listRows();
// ⚠ **THE SHAPE WITH NO PROPERTY YET IS PREFERRED, AND THE REASON IS NOT THIS
// DEFECT.** A build on a property that ALREADY carries an occupied common area
// is refused at the last button by `BR-CUS-017` — `create_owner_account` is
// opt-in only in the sense that typing an owner name turns it on, and it
// attaches the master account to every existing common area. That refusal
// fires identically on the tip and on the fix, so a walk pinned to that shape
// can never see what the last press DID. It is real, it is somebody's defect,
// and it is filed rather than worked around here. See the run log's own line.
const drafts = before.filter((r) => r.id && r.state === "draft" && r.request_no);
const draft = drafts.find((r) => r.premises === null) ?? drafts[0];
if (!draft) {
  fail("no DRAFT build raised from an application on this database — approve one first");
  await browser.close();
  process.exit(1);
}
const buildsBefore = buildNumbers(before);
say(`  ${draft.connection_no}, raised by ${draft.request_no}` +
    (draft.premises === null ? " (its address had not resolved)" : ` (on ${draft.premises.address})`));
say(`  the list holds ${before.length} rows, of which ${buildsBefore.length} are builds`);

// ── 1 · DEF-CUS-6132 · THE DRAFT'S OWN ROW IS A DOOR ────────────────────────
say("\n════ DEF-CUS-6132 · can a clerk get back into it at all? ════");
await page.goto(`${BASE}/${T}/accounts?tab=new-connects`, { waitUntil: "networkidle" });
await page.waitForTimeout(2400);
const rowHrefFor = async (number) =>
  page.$$eval("tbody tr", (ns, want) => {
    for (const tr of ns) {
      const cells = [...tr.querySelectorAll("td")].map((td) => td.innerText.trim());
      if (cells[0] === want) return tr.querySelector("a")?.getAttribute("href") ?? null;
    }
    return null;
  }, number);
const draftHref = await rowHrefFor(draft.connection_no);
note(`${draft.connection_no}'s row opens ${draftHref ?? "(NOTHING — no link at all)"}`);
if (!draftHref || !draftHref.includes(`/connections/new?build=${draft.id}`)) {
  fail(`the draft's row does not open its wizard — it opens ${draftHref ?? "nothing"}`);
}
await shot("01-list-before");

// ── 2 · TYPE, AND PARK ──────────────────────────────────────────────────────
say("\n════ the clerk types for ten minutes and parks it ════");
const MARK = `PARK1-${Date.now().toString().slice(-4)}`;
// ⚠ **THE DOOR IS WALKED WHEN IT IS ONE, AND STEPPED AROUND WHEN IT IS NOT.**
// A walk that simply followed a broken href would land on the property page,
// find no `Park` control and stop — reporting *"the wizard offers no Park"*,
// which is true of the property page and says nothing about the wizard. That
// is law 7's *looking at the wrong thing*, and it is what happened on the
// first run of this script against the defect. The finding above is already
// recorded; the rest of the walk is about the PARK, so it goes to the wizard
// by its own address and says which of the two it did.
const wizardHref = draftHref && draftHref.includes("/connections/new?build=")
  ? draftHref
  : `/${T}/connections/new?build=${draft.id}`;
note(draftHref === wizardHref
  ? "walked in through the row's own door"
  : "the row's door does not lead here, so this walk went to the wizard's address directly");
await page.goto(`${BASE}${wizardHref}`, { waitUntil: "networkidle" });
await page.waitForTimeout(2600);
await page.fill("#nc_owner_name", MARK).catch(() => {});
press("type into the owner name");
const park = await byLabel("Park");
if (!park) { fail("the wizard offers no Park control"); await browser.close(); process.exit(1); }
await park.click(); press("press Park");
await page.waitForTimeout(1800);
// ⚠ THE PICKER IS FOUND BY WHAT IT OFFERS, NEVER BY POSITION — step 1's OWNER
// TYPE select is still mounted behind the inline panel, and a probe that took
// the first `<select>` set that instead and printed a cheerful confirmation of
// a park that never happened.
let waitingSet = null;
for (const sel of await page.$$("select")) {
  const opts = await sel.$$eval("option", (ns) =>
    ns.map((o) => ({ v: o.value, t: (o.textContent || "").trim() })).filter((o) => o.v));
  const wanted = opts.find((o) => /^waiting on/i.test(o.t));
  if (!wanted) continue;
  await sel.selectOption(wanted.v).catch(() => {});
  waitingSet = wanted.t; press(`Waiting on = ${wanted.t}`);
  break;
}
if (waitingSet === null) fail("the park panel offers no `Waiting on` picker");
await page.waitForTimeout(600);
const parkIt = await byLabel("Park it");
if (!parkIt || (await parkIt.isDisabled())) { fail('"Park it" is missing or disabled'); await browser.close(); process.exit(1); }
await parkIt.click(); press('press "Park it"');
await page.waitForTimeout(3200);
// `?park=1` still on the address means the panel never closed, which is what a
// REFUSED park looks like — said out loud, because every line after this one
// would otherwise describe a park that did not happen.
const afterPark = new URL(page.url());
if (afterPark.searchParams.get("park") === "1") {
  fail("the park panel is STILL OPEN — `Park it` did not take");
  await browser.close();
  process.exit(1);
}
note(`after parking, the clerk is on ${afterPark.pathname}${afterPark.search}`);

// ── 3 · THE ROW IT LEFT BEHIND NAMES ITS BUILD ──────────────────────────────
say("\n════ the row on the New connects tab ════");
await page.goto(`${BASE}/${T}/accounts?tab=new-connects`, { waitUntil: "networkidle" });
await page.waitForTimeout(2400);
const rows = await page.$$eval("tbody tr", (ns) => ns.map((tr) => ({
  cells: [...tr.querySelectorAll("td")].map((td) => td.innerText.trim()),
  href: tr.querySelector("a")?.getAttribute("href") ?? null,
  parked: tr.querySelector("[data-connect-draft]")?.getAttribute("data-connect-draft") ?? null,
})));
const parkedRow = rows.find((r) => r.parked);
if (!parkedRow) { fail("the park left no row on the New connects list"); await browser.close(); process.exit(1); }
note(`the parked row's CONNECTION cell reads ${JSON.stringify(parkedRow.cells[0])}`);
if (parkedRow.cells[0] !== draft.connection_no) {
  fail(`the parked row names ${JSON.stringify(parkedRow.cells[0])} and not ${draft.connection_no}`);
}
await shot("02-list-parked");

// ── 4 · RESUME IT AND FINISH IT ─────────────────────────────────────────────
say("\n════ the clerk comes back the next day and finishes it ════");
const resumeHref = `/${T}/connections/new?parked=${parkedRow.parked}`;
const commits = [];
page.on("response", async (r) => {
  if (!r.url().includes("/connections/commit")) return;
  try { commits.push({ status: r.status(), body: await r.text() }); } catch { /* consumed */ }
});
await page.goto(`${BASE}${resumeHref}`, { waitUntil: "networkidle" });
await page.waitForTimeout(3000);
const cameBack = await page.$eval("#nc_owner_name", (n) => n.value).catch(() => "(no field)");
note(`the owner name came back as ${JSON.stringify(cameBack)}`);
if (cameBack !== MARK) fail(`the typing did not come back — the field reads ${JSON.stringify(cameBack)}`);

// Step 1's remaining questions. A COMPANY owner needs a Tax ID, and this is
// what stopped the reproduction walk one step in.
const stamp = Date.now().toString().slice(-6);
await page.selectOption("#nc_owner_subcategory", "permanent").catch(() => {});
for (const sel of ["#nc_tax_id", "#nc_owner_tax_id", "#nc_ssn"]) {
  if (await page.$(sel)) {
    const cur = await page.$eval(sel, (n) => n.value).catch(() => "");
    if (cur === "") await page.fill(sel, sel === "#nc_ssn" ? `4${stamp.slice(-2)}-11-${stamp}`.slice(0, 11) : `TX-${stamp}`).catch(() => {});
    break;
  }
}
await pickRadio("nc_mode", "our_crew");
await wizardForward("step 1 · Owner & scope");

for (const [sel, v] of [["#nc_address", `${stamp} Park Way`], ["#nc_city", "Austin"], ["#nc_postal_code", "78704"], ["#nc_state", "TX"]]) {
  if (await page.$(sel)) { const cur = await page.$eval(sel, (n) => n.value); if (cur === "") await page.fill(sel, v).catch(() => {}); }
}
const ptypes = await page.$$eval("#nc_premise_type option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
if ((await page.$eval("#nc_premise_type", (n) => n.value).catch(() => "")) === "" && ptypes.length) {
  await page.selectOption("#nc_premise_type", ptypes[0]).catch(() => {});
}
await page.waitForSelector("#services_available-add", { timeout: 15000 }).catch(() => {});
const offered = await page.$$eval("#services_available-add option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
for (const code of offered.slice(0, 1)) { await page.selectOption("#services_available-add", code).catch(() => {}); await page.waitForTimeout(250); }
const plans = await page.$$eval("#nc_plan option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
if (plans.length && (await page.$eval("#nc_plan", (n) => n.value).catch(() => "")) === "") {
  await page.selectOption("#nc_plan", plans[0]).catch(() => {});
}
await wizardForward("step 2 · Premise");

await page.fill("#nc_from", "1").catch(() => {});
await page.fill("#nc_to", "1").catch(() => {});
await page.waitForTimeout(800);
for (const label of ["step 3 · Units", "step 4 · Services", "step 5 · Work orders", "step 6 · Charges", "step 7 · Communication", "step 8 · Create connection"]) {
  if (!(await wizardForward(label))) break;
}
await page.waitForTimeout(8000);
await shot("03-after-the-press");

// ── 5 · THE VERDICT ─────────────────────────────────────────────────────────
say("\n════ what the last press did ════");
const said = commits[commits.length - 1] ?? null;
if (said === null) {
  fail("POST /connections/commit was never called — the wizard did not reach the last button, so nothing below is an answer");
} else {
  let answered = {};
  try { answered = JSON.parse(said.body || "{}"); } catch { /* not json */ }
  note(`the commit answered HTTP ${said.status} with ${answered.connection_no ?? "(no connection_no)"}`);
  // ⚠ **THREE OUTCOMES, AND COLLAPSING TWO OF THEM WOULD BE LAW 7's *LOOKING
  // AT THE WRONG THING*.** A refusal and a second build are opposite failures
  // — one loses the work in front of the clerk, the other loses it silently —
  // and the first draft of this block reported a `409` as *"a DIFFERENT
  // build"*, which is not true of a press that wrote nothing at all.
  if (said.status >= 400) {
    fail(`the last press was REFUSED (HTTP ${said.status}) — ${said.body.slice(0, 200)}`);
  } else if (answered.id === draft.id) {
    note(`✔ it FINISHED ${draft.connection_no} — the same build, not a second one`);
  } else {
    fail(`the commit made ${answered.connection_no ?? answered.id}, a SECOND build beside ${draft.connection_no}`);
  }
}
const after = await listRows();
const buildsAfter = buildNumbers(after);
const minted = buildsAfter.filter((n) => !buildsBefore.includes(n));
say(`  builds before: ${buildsBefore.length} · after: ${buildsAfter.length} · newly minted: ${minted.join(", ") || "none"}`);
if (minted.length) fail(`a new build was minted: ${minted.join(", ")}`);

const named = after.filter((r) => r.connection_no === draft.connection_no);
say(`  rows on the tab naming ${draft.connection_no}: ${named.length}`);
if (named.length !== 1) fail(`${named.length} rows name one piece of work`);
const leftovers = after.filter((r) => !r.id);
if (leftovers.length) fail(`${leftovers.length} parked draft(s) still on the list after the commit`);

const still = JSON.parse((await api(`/api/${T}/connections/${draft.id}`)).body || "{}");
const sd = still.data ?? still;
note(`${draft.connection_no} now reads state=${sd.state} (it was draft) and still names ${sd.request_no ?? "(no request)"}`);
if (sd.state === "draft") fail(`${draft.connection_no} is still a draft — the press did not finish it`);
if (sd.request_no !== draft.request_no) fail(`${draft.connection_no} has lost its application`);

say(`\n════ ${bad.length} problem(s) · ${presses} presses ════`);
bad.forEach((b) => say("  ⛔ " + b));
await browser.close();
process.exit(bad.length ? 1 : 0);
