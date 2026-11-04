// ── Trace ──────────────────────────────────────────────
// Change:   CR-126-BRC07 §9 — THE PRODUCT OWNER'S OWN ACCEPTANCE WALK, in their
//           words: *"create a new conenct request - take variations of all kind
//           - do ultiple request submission check whther clark is able to create
//           these request with ease … then complete the new connect request -
//           see at submit does it create premsies, units, services, plan and
//           asete and account of owner a smaster account , money handling, audit
//           handling, documents are stored etc - then whether request is
//           available in the list view - you can search, filter etc"*
// Rules:    CLAUDE.md hard-won law 6 — no gate in this repo reads rendered
//           output, so this script and a person are the only things that can
//           answer §9 · hard rule 2 (money 4dp stored, 2dp displayed) ·
//           hard rule 7 (audit_log on every money action) · NFR-3 (the list is
//           server-paginated) · PO ruling 2026-09-21 (assets generated and
//           assigned, NOT installed and NOT activated)
// ───────────────────────────────────────────────────────
//
// WHAT THIS IS AND IS NOT
// -----------------------
// It is a CLERK, driven. It types what a clerk types, presses what a clerk
// presses, and **counts both** — because §9's question is not "does it submit",
// it is whether a clerk can do this with EASE several times in a row. The press
// count and the re-typing log are the deliverable; the pass line is not.
//
// ⚠ **IT ASSERTS ABSENCES AS WELL AS VALUES.** A build that commits and leaves
// no meter behind passes every "did it submit" check ever written. So the
// readback below asks the DATABASE for each of §9's nine nouns separately and
// prints what it found, including zero.
//
// ⚠ **IT MUST RUN AGAINST ITS OWN DATABASE.** A lane using the shared one on
// 2026-09-20 reached a real case and posted two duplicate $75.00 invoices to
// the books. Clone by template, point DATABASE_URL at the clone, drop it after.
//
// RUN:  BASE=http://127.0.0.1:8718 VARIATION=v1 node 10-scripts/cr126_s9_acceptance_walk.mjs
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const require = createRequire(path.join(ROOT, "07-frontend/package.json"));
const { chromium } = require("playwright-core");

const BASE = process.env.BASE || "http://127.0.0.1:8718";
const T = process.env.TENANT || "brazosbend";
const EMAIL = process.env.EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const OUT = process.env.OUT || "/tmp/claude-0/walk2-shots";
const VAR = process.env.VARIATION || "v1";
const DUMP = process.env.DUMP === "1";
mkdirSync(OUT, { recursive: true });

// ── THE VARIATIONS §9 NAMES, one object each ────────────────────────────────
// "a single house, a seven-unit apartment block, a build with one service and a
//  build with several, a developer and a private owner, a picked existing
//  address and a new one, with documents and without."
const STAMP = Date.now().toString().slice(-7);
const VARIATIONS = {
  v1: { name: "single house · private owner · every service · new address · no documents",
        ownerKind: "property_owner", party: "person", scope: "new_premise",
        units: 0, services: "all", docs: false, addressPicked: false },
  v2: { name: "seven-unit block · developer · every service · new address · one document",
        ownerKind: "builder_developer", party: "company", scope: "new_premise",
        units: 7, services: "all", docs: true, addressPicked: false },
  v3: { name: "single house · landlord · ONE service only · new address · no documents",
        ownerKind: "landlord", party: "person", scope: "new_premise",
        units: 0, services: "one", docs: false, addressPicked: false },
  v4: { name: "new units at an EXISTING premise · occupier · picked address",
        ownerKind: "occupier", party: "person", scope: "new_units",
        units: 3, services: "all", docs: false, addressPicked: true },
  v5: { name: "a new service at an existing unit · property owner · picked address",
        ownerKind: "property_owner", party: "person", scope: "new_service",
        units: 0, services: "one", docs: false, addressPicked: true },
  // ⚠ **v6 IS v1 WITH ONE DWELLING TYPED IN, AND IT EXISTS TO ISOLATE A CAUSE.**
  // v1 is the single house a clerk actually builds — no unit numbers, because a
  // house has none — and step 3 then makes ONE COMMON-AREA unit. A common area
  // is sent NO plan by PO ruling (2026-09-16, `DEF-CUS-5496`), so the build has
  // zero plan assignments and the last press is refused. v6 types `From 1 To 1`
  // instead. If v6 commits and v1 does not, the cause is the common area and
  // not the plan picker.
  v6: { name: "single house typed as ONE DWELLING (From 1 To 1) · private owner · every service",
        ownerKind: "property_owner", party: "person", scope: "new_premise",
        units: 1, services: "all", docs: false, addressPicked: false },
  // ⚠ **v7 UNTICKS THE COMMON AREA, WHICH IS THE OTHER HALF OF THE SAME MAP.**
  // v6 shows that a build WITH a common area is refused because the common area
  // carries no plan. v7 asks the opposite question: with no common area at all,
  // does the owner's master account open? `create_owner_account` refuses by name
  // (`metering.connection_no_common_area_for_master`) when the premises has
  // none, so the two together say whether ANY path through this wizard reaches a
  // committed build — which is what §9 part 3 needs before it can ask anything.
  v7: { name: "one dwelling and NO common area · private owner · every service",
        ownerKind: "property_owner", party: "person", scope: "new_premise",
        units: 1, services: "all", docs: false, addressPicked: false, commonArea: false },
  // ⚠ **v8 IS THE LAST CORNER OF THE MAP AND IT EXISTS TO PROVE A NEGATIVE.**
  // `newConnectDraft.ts` sends `create_owner_account: draft.owner.name.trim()
  // !== ""`, so the only build that never calls `create_owner_account` is one
  // with no owner named — and step 1 marks *Owner or developer* required. If
  // step 1 refuses to advance, there is no path through this wizard that
  // commits at all, and that is a statement worth measuring rather than
  // inferring from two refusals.
  v8: { name: "no owner named at all · no common area · one dwelling",
        ownerKind: "property_owner", party: "person", scope: "new_premise",
        units: 1, services: "all", docs: false, addressPicked: false, commonArea: false,
        noOwnerName: true },
  // ── WALK-3, 2026-09-21 · THE VARIATIONS §9 ACTUALLY NAMES, NOW THAT A BUILD
  // COMMITS ────────────────────────────────────────────────────────────────
  // v1–v8 above are the PREVIOUS walk's diagnostic map, written when every
  // build was refused at the last press; each isolates a cause, and several of
  // them now pass. `BR-MET-1179` then made the common area OPTIONAL AND
  // DEFAULT OFF, so `commonArea: true` had to become something this script can
  // do — v1–v8 only ever UNTICKED it. w1–w6 are §9's own list, one variation
  // per clause of it, and they are the ones whose press counts are quoted.
  w1: { name: "single house · private owner · every service · new address · no documents · NO common area",
        ownerKind: "property_owner", party: "person", scope: "new_premise",
        units: 1, services: "all", docs: false, addressPicked: false, commonArea: false },
  w2: { name: "single house · private owner · every service · new address · WITH a common area",
        ownerKind: "property_owner", party: "person", scope: "new_premise",
        units: 1, services: "all", docs: false, addressPicked: false, commonArea: true },
  w3: { name: "seven-unit block · DEVELOPER (company) · every service · new address · ONE DOCUMENT · with a common area",
        ownerKind: "builder_developer", party: "company", scope: "new_premise",
        units: 7, services: "all", docs: true, addressPicked: false, commonArea: true },
  w4: { name: "single house · landlord · ONE service only · new address · no documents · no common area",
        ownerKind: "landlord", party: "person", scope: "new_premise",
        units: 1, services: "one", docs: false, addressPicked: false, commonArea: false },
  w5: { name: "three new units at an EXISTING PICKED address · occupier · every service · no common area",
        ownerKind: "occupier", party: "person", scope: "new_units",
        units: 3, services: "all", docs: false, addressPicked: true, commonArea: false },
  w6: { name: "a new service at an existing unit · property owner · picked address · one service",
        ownerKind: "property_owner", party: "person", scope: "new_service",
        units: 1, services: "one", docs: false, addressPicked: true, commonArea: false },
  // §9's money clause needs a build that was actually PRICED — see step 6.
  w7: { name: "single house · private owner · every service · a CONNECTION FEE put on the quote",
        ownerKind: "property_owner", party: "person", scope: "new_premise",
        units: 1, services: "all", docs: false, addressPicked: false, commonArea: false,
        charge: "CONN" },
  // ⚠ **w8's CHARGE WAS `TAP` UNTIL 2026-09-21, AND THAT WAS MEASURING A BROKEN
  // CATALOGUE ROW RATHER THAN THE WIZARD.** `TAP`, `IMPACT` and `DAMAGE` are
  // live charge codes in the demo tenant with **no amount at all**, so the
  // commit answered a bare 500 and the whole seven-unit build was lost. That is
  // `DEF-MET-6110`, it has its own row and its own variations below (`x6110`,
  // `x6110b`), and it is NOT what w8 is for — which is a build that PRICES
  // ITSELF and reaches §9 part 3's money clause. `CONN` is the flat `$45.00`
  // the walk's own worked figure is quoted from.
  w8: { name: "seven-unit block · developer · every service · a PER-UNIT charge on the quote · with a document",
        ownerKind: "builder_developer", party: "company", scope: "new_premise",
        units: 7, services: "all", docs: true, addressPicked: false, commonArea: true,
        charge: "CONN" },
  // ⛔ **THERE IS NO `w9`, AND ITS ABSENCE IS DELIBERATE.** One was written on
  // 2026-09-21 — w8 with the unpriceable `TAP` — to prove that step 6's priced
  // preview refuses a code the catalogue cannot price BEFORE the press. It was
  // deleted unpushed on finding `x6110` and `x6110b` below, another lane's, the
  // same day and the same question. **Two variations asking one question is two
  // things to keep in step**, and theirs is the better pair: `x6110` walks the
  // commit's own refusal and `x6110b` walks the case a picker filter cannot see
  // — a code edited on Settings after the step was drawn. The preview's part in
  // that is asserted where it belongs, in
  // `newConnectEaseFixes.dom.test.tsx` and
  // `test_def_cus_6115_the_quote_is_priced_for_the_screen.py`.
  // ⚠ **`w9` IS THE ONLY VARIATION THAT TOUCHES STEP 4'S GRID, AND THAT IS WHY
  // IT EXISTS (WALK-A, 2026-09-21).** Every variation above presses straight
  // through step 4, so all of them measure the DEFAULTS — which is how sixteen
  // asset-type pickers and sixteen size pickers were walked four times over
  // without anybody learning whether either one travels. `DEF-CUS-6101` is the
  // same shape on the install date, already found and already fixed; a control
  // a walk never presses is a control a walk cannot report on.
  w9: { name: "single house · the step-4 grid actually USED — a non-default asset type and size picked",
        ownerKind: "property_owner", party: "person", scope: "new_premise",
        units: 1, services: "all", docs: false, addressPicked: false, commonArea: false,
        useGrid: true },
  // ── `DEF-MET-6110` / `DEF-MET-6111` · THE TWO BUSINESS RULES THAT REACHED A
  // CLERK AS A RAW 500 (2026-09-21) ────────────────────────────────────────
  // ⚠ **THEY ARE VARIATIONS AND NOT A SECOND SCRIPT, BECAUSE THE FAULT IS IN
  // THIS WALK'S OWN FLOW.** Each is a build a clerk can make out of controls
  // the product offers them; what is measured is what the LAST PRESS answers
  // and WHICH STEP the answer lands on. `commitSeen` below records both.
  x6110: { name: "single house · a charge code the picker offers and billing cannot price (TAP)",
        ownerKind: "property_owner", party: "person", scope: "new_premise",
        units: 1, services: "all", docs: false, addressPicked: false, commonArea: false,
        charge: process.env.CHARGE || "TAP" },
  // ⚠ **THE FRAGMENT AND THE PREFIX ARE THE WHOLE REPRODUCTION.** `PICK` types
  // a fragment of an address ALREADY ON FILE and `PREFIX`/`FROM`/`TO` make
  // labels that address already holds — `2200 Riverbend Ct` holds `Apt 101`,
  // `Apt 102` and `Apt 103`, so `Apt` · 101 · 103 is three labels that cannot
  // be created. The database is right to refuse; the question is what the clerk
  // is told, and where.
  x6111: { name: "three units at a picked address that already holds those very labels",
        ownerKind: "occupier", party: "person", scope: "new_units",
        units: 3, services: "all", docs: false, addressPicked: true, commonArea: false,
        pick: "2200 Riv", prefix: "Apt", from: "101", to: "103" },
  // ⚠⚠ **THE CASE LAYER 1 CANNOT COVER, AND IT IS THE ONE THE PO NAMED.** With
  // the picker filtered, `TAP` is no longer offered — so the only way a build
  // can still carry an unpriceable code is the way a real utility produces it:
  // the code was priceable when the clerk picked it and **a tenant edited it on
  // Settings before the press**. `rating.selectors.charge_by_code` says that is
  // what a charge code IS — *"the amount is a SEED the tenant edits, never a
  // constant"*. `deprice` does exactly that, through the product's own
  // `PATCH /charges/{id}`, between step 6 and the last button.
  x6110b: { name: "a charge that WAS priceable at step 6 and is edited on Settings before the press",
        ownerKind: "property_owner", party: "person", scope: "new_premise",
        units: 1, services: "all", docs: false, addressPicked: false, commonArea: false,
        charge: "CONN", deprice: "CONN" },
};
// ⚠ **`PART=list` IS §9 PART 4, AND IT IS A DIFFERENT WALK OVER THE SAME
// SCREENS.** Parts 1–3 RAISE a build; part 4 asks *"then whether request is
// available in the list view - you can search, filter etc"*. It was never
// implemented, so the two list defects the PO's walk found — a filter offering
// raw server codes, and a filter that does not survive a reload — were found
// by hand and could be proved by nothing. It runs without a VARIATION.
const PART = process.env.PART || "raise";
const V = VARIATIONS[VAR];
if (PART === "raise" && !V) { console.error(`unknown VARIATION ${VAR}; have ${Object.keys(VARIATIONS).join(", ")}`); process.exit(2); }

// ── THE PRESS COUNTER ───────────────────────────────────────────────────────
// A "press" is one discrete clerk act: one click, one radio, one option chosen,
// one field typed into. Characters are counted separately, because a field the
// product already knows the answer to costs a clerk a whole sentence.
let presses = 0, chars = 0;
const pressLog = [];
const retyped = [];       // things the wizard already knows and asks for anyway
const stopAndThink = [];  // places a clerk has to work out what is wanted
const refusals = [];
const notes = [];
const press = (what) => { presses += 1; pressLog.push(what); };
const say = (...a) => console.log(...a);

const browser = await chromium.launch({ executablePath: CHROME });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => refusals.push(`PAGEERROR ${e.message.slice(0, 160)}`));
// ⚠ **A CONSOLE ERROR FROM SOMETHING THAT IS NOT THIS PRODUCT IS NOT A
// REFUSAL, AND THIRTEEN OF THEM BURIED THE ONE THAT WAS (WALK-B, 2026-09-21).**
// Chromium makes its own outbound calls, and in this container they fail
// against the agent proxy — so `PART=list` printed a REFUSALS block of fourteen
// lines, thirteen reading `net::ERR_CERT_AUTHORITY_INVALID` and one naming a
// real defect. That is law 7's habit 3 from the other side: the output was
// truthful and a reader could not tell the finding from the furniture. Browser
// noise is still COLLECTED, under its own heading, because a real one matters.
const browserNoise = [];
const NOT_OURS = /ERR_CERT_AUTHORITY_INVALID|ERR_PROXY|ERR_NAME_NOT_RESOLVED|ERR_INTERNET_DISCONNECTED|favicon/i;
page.on("console", (m) => {
  if (m.type() !== "error") return;
  const text = m.text().slice(0, 140);
  (NOT_OURS.test(text) ? browserNoise : refusals).push(`console: ${text}`);
});

// ── WHAT THE LAST PRESS ACTUALLY GOT BACK — `DEF-MET-6110` / `DEF-MET-6111` ──
// ⚠ **THE SCREEN ALONE CANNOT TELL A 500 FROM A REFUSAL, WHICH IS THE WHOLE
// DEFECT.** Both render a strip; only the wire says whether the product refused
// the clerk by a rule or fell over. So the commit's STATUS and its envelope are
// read off the response, and the step the clerk is left on is read off the DOM.
const commitSeen = [];
page.on("response", async (r) => {
  if (!/\/connections\/commit$/.test(new URL(r.url()).pathname)) return;
  let body = "";
  try { body = (await r.text()).slice(0, 700); } catch { body = "(unreadable)"; }
  commitSeen.push({ status: r.status(), body });
});

async function typeInto(sel, value, label) {
  const el = await page.$(sel);
  if (!el) return false;
  await el.fill(String(value));
  press(`type ${label || sel} = "${value}"`);
  chars += String(value).length;
  return true;
}
async function choose(sel, value, label) {
  const el = await page.$(sel);
  if (!el) return false;
  await page.selectOption(sel, value);
  press(`choose ${label || sel} = ${value}`);
  return true;
}
async function radio(name, value) {
  const el = await page.$(`input[name="${name}"][value="${value}"]`);
  if (!el) { refusals.push(`no control ${name}=${value}`); return false; }
  // The radio is visually hidden and zero-sized; the label is what a person
  // clicks, and dispatching on the input is the same event React binds.
  await el.evaluate((n) => n.click());
  press(`pick ${name} = ${value}`);
  const on = await page.evaluate(([n, v]) =>
    document.querySelector(`input[name="${n}"][value="${v}"]`)?.checked === true, [name, value]);
  if (!on) refusals.push(`${name}=${value} would not take`);
  return on;
}
async function shot(tag) {
  await page.waitForTimeout(350);
  await page.screenshot({ path: `${OUT}/${VAR}-${tag}.png`, fullPage: true });
  if (DUMP) {
    const d = await page.evaluate(() => ({
      h1: document.querySelector("h1")?.innerText || "",
      fields: [...document.querySelectorAll("input,select,textarea,button")]
        .map((n) => `${n.tagName}${n.disabled ? "(dis)" : ""} id=${n.id} nm=${n.getAttribute("name") || ""} ty=${n.getAttribute("type") || ""} | ${(n.closest("label")?.innerText || document.querySelector(`label[for="${n.id}"]`)?.innerText || (n.tagName === "BUTTON" ? n.innerText : "")).trim().replace(/\n/g, "·").slice(0, 60)}`),
      text: document.body.innerText,
    }));
    writeFileSync(`${OUT}/${VAR}-${tag}.txt`, `H1 ${d.h1}\n${d.fields.join("\n")}\n---- TEXT ----\n${d.text}`);
  }
}
function stepText() { return page.evaluate(() => document.body.innerText); }
async function forward(label) {
  const bs = await page.$$('[data-wizard="actions"] button');
  if (!bs.length) { refusals.push(`${label}: no wizard action bar`); return false; }
  const last = bs[bs.length - 1];
  const txt = (await last.innerText()).trim();
  if (await last.isDisabled()) {
    const why = (await stepText()).match(/[^\n]*(?:continue|required|needs|choose|pick|must)[^\n]*/gi)?.slice(0, 3) ?? [];
    refusals.push(`${label}: "${txt}" is disabled — ${why.join(" / ")}`);
    return false;
  }
  const before = page.url();
  await last.click();
  press(`press "${txt}" (${label})`);
  await page.waitForTimeout(1700);
  const moved = page.url() !== before || true;
  return moved;
}
async function onStep() {
  const t = await stepText();
  const m = t.match(/Step (\d+) of (\d+)/);
  return m ? Number(m[1]) : -1;
}

// ── SIGN IN ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
                   page.click('button[type="submit"]')]);
say(`\n══ ${VAR} · ${V.name} ══`);
say(`signed in as ${EMAIL}`);
const t0 = Date.now();

// ══════════════════════════════════════════════════════════════════════════
// §9 PART 4 · FIND IT AGAIN — the filter panel, the words in it, and whether
//             a clerk's choice survives a reload or can be sent to anybody
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **IT READS THE RENDERED OPTIONS, NOT THE PAYLOAD.** The payload is right
// and always was: `list_connections` serves ten state codes and the screen
// labels them. What a clerk READS is the question, and no gate in this repo
// reads rendered output (CLAUDE.md law 6).
//
// ⚠ **THE RELOAD IS THE WHOLE POINT OF THE SECOND HALF.** A walk that clicks a
// filter and reads the row count sees a pass — the filter WORKS. Only a reload
// can see that the choice was never written down.
if (PART === "list") {
  const LIST = `${BASE}/${T}/accounts?tab=new-connects`;
  await page.goto(LIST, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  press("open the New connects tab");
  await shot("list-open");

  const rowsOn = async () => page.$$eval("tbody tr", (ns) => ns.length);
  const before = await rowsOn();
  notes.push(`the tab opens on ${before} row(s)`);

  // \u26a0 **THE FILTER PANEL IS A `<details>`/`<summary>` DISCLOSURE, NOT A
  // BUTTON** (`FilterBar.tsx`, DEF-442 \u2014 r10's `+ Filter \u25be`). A walk that
  // looked for a `<button>` reported *"the tab offers no Filter control"*, which
  // is law 7's *looking at the wrong thing*: the control was there and the probe
  // was not.
  // \u26a0 **THERE ARE TWO DISCLOSURES ON THIS TOOLBAR** \u2014 the filter panel and
  // the column chooser \u2014 and `details > summary` takes whichever is first.
  // Opened by the WORD, and opened by setting `open` rather than clicking,
  // because a `<summary>` inside an overflowing toolbar can be off-screen.
  const filterOpened = await page.evaluate(() => {
    for (const d of document.querySelectorAll("details")) {
      const word = (d.querySelector("summary")?.textContent || "").trim();
      if (/filter/i.test(word)) { d.open = true; return word; }
    }
    return null;
  });
  if (filterOpened === null) refusals.push("the New connects tab offers no Filter control");
  else press(`press "${filterOpened}"`);
  await page.waitForTimeout(900);
  await shot("list-filter-panel");

  // ⚠ **EVERY WORD IN THE PANEL, READ AS A CLERK READS IT.** A raw server code
  // among translated words is the defect, and it is only visible here: the
  // option list is built from whatever the server sends, so a code always
  // renders and always looks deliberate.
  const offered = await page.$$eval("details[open] fieldset label span, details[open] fieldset legend", (ns) =>
    ns.map((n) => (n.textContent || "").trim()).filter(Boolean));
  // \u26a0 **AN UNDERSCORE IS NOT THE TEST, AND A FIRST DRAFT THAT USED ONE
  // MISSED HALF THE DEFECT.** `in_progress_draft` is obviously a code and
  // `parked` is not \u2014 it is a lowercase English word, and it was reported as
  // fine while a clerk was reading it beside `Draft`, `On hold` and `Activated`.
  // The test a clerk actually applies is CASE: every word in this panel is a
  // label and a label is capitalised, so anything starting lowercase is a
  // stored value that reached the screen.
  const RAW = offered.filter((word) => /^[a-z]/.test(word));
  notes.push(`the filter panel offers ${offered.length} word(s)`);
  if (RAW.length) refusals.push(`the filter offers RAW SERVER CODES to a clerk: ${[...new Set(RAW)].join(" · ")}`);
  else notes.push("every word in the filter panel is a word, not a code");

  // Tick the state the PO's own walk ticked \u2014 `Draft`, which narrowed nine
  // rows to one \u2014 by the WORD a clerk reads, never by a code.
  const boxes = await page.$$("details[open] fieldset label");
  let picked = null;
  for (const box of boxes) {
    const word = (await box.innerText()).trim();
    if (/^draft$/i.test(word)) {
      await box.evaluate((n) => n.querySelector("input")?.click());
      press(`tick Show = ${word}`);
      picked = word;
      break;
    }
  }
  if (picked === null && boxes.length > 0) {
    picked = (await boxes[0].innerText()).trim();
    await boxes[0].evaluate((n) => n.querySelector("input")?.click());
    press(`tick Show = ${picked}`);
  }
  if (picked === null) refusals.push("the filter panel offers no state to choose");
  await page.waitForTimeout(1800);
  const narrowed = await rowsOn();
  const filteredUrl = page.url();
  notes.push(`filtering narrowed ${before} row(s) to ${narrowed}; the address reads ${filteredUrl}`);
  await shot("list-filtered");

  // ── HALF ONE · DOES THE CHOICE REACH THE ADDRESS ──────────────────────────
  if (filteredUrl === LIST || !/[?&](f\.|nc\.)/.test(filteredUrl)) {
    refusals.push(`the filter is NOT in the address — it reads ${filteredUrl}, so it cannot be sent to anybody`);
  } else {
    notes.push("the filter reached the address and can be pasted");
  }

  // ── HALF TWO · DOES IT SURVIVE A RELOAD ───────────────────────────────────
  await page.goto(filteredUrl, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  const afterReload = await rowsOn();
  await shot("list-reloaded");
  if (afterReload !== narrowed) {
    refusals.push(`the filter is LOST on reload: ${narrowed} row(s) filtered, ${afterReload} after opening the same address`);
  } else {
    notes.push(`the filter survived a reload: ${afterReload} row(s) both times`);
  }


  // ══════════════════════════════════════════════════════════════════════════
  // §9 PART 4, THE OTHER THREE CLAUSES — SEARCH · COLUMNS · PAGINATION
  //                                                     (WALK-B, 2026-09-21)
  // ══════════════════════════════════════════════════════════════════════════
  // §9 part 4 names five searches, the column selector and `NFR-3` by name, and
  // the block above walks none of them. Each is read the way a clerk meets it —
  // typed into the box, ticked in the panel — and the pagination clause is
  // answered by **what the server is asked for**, never by counting rows on one
  // screen: a list that ignored `page` entirely would show fifty rows and look
  // exactly like a list that paged correctly.
  const apiGet = (p) => page.evaluate(async (pp) => {
    const r = await fetch(pp, { headers: { accept: "application/json" } });
    return { status: r.status, body: await r.text() };
  }, p);

  // Every `/connections?` the browser asks for, in order. This is the evidence
  // for the pagination clause and it is collected rather than inferred.
  const asked = [];
  page.on("request", (r) => {
    const u = new URL(r.url());
    if (u.pathname.endsWith("/connections")) asked.push(u.search || "(no query)");
  });

  const SEARCH = 'input[type="search"][aria-label^="Connection"]';
  const typeSearch = async (text) => {
    await page.goto(LIST, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    const box = await page.$(SEARCH);
    if (!box) { refusals.push("the New connects tab has no search box"); return null; }
    asked.length = 0;
    await box.fill(text);
    press(`type "${text}" into the search box`);
    await page.waitForTimeout(2200);
    const rows = await page.$$eval("tbody tr", (ns) => ns.map((tr) => tr.innerText.replace(/\s+/g, " ").trim()));
    return { rows, sentToServer: asked[asked.length - 1] ?? "(the browser asked the server nothing)" };
  };

  say("\n── the five searches §9 names, typed into the box ──");
  // ⚠ **THE TERMS ARE READ OFF A ROW, NOT TYPED IN HERE.** Naming
  // `CON-26-0130` would make this walk pass on one database and report a
  // missing row on every other — the same trap part 2's shape-picking already
  // records one file over.
  const listing = JSON.parse((await apiGet(`/api/${T}/connections?per=50`)).body || "{}");
  const allRows = listing.results ?? listing.data ?? [];
  const withRequest = allRows.find((r) => r.request_no) ?? null;
  const withPremise = allRows.find((r) => r.premises && r.premises.premise_no) ?? null;
  const withApplicant = allRows.find((r) => r.applicant) ?? null;
  // ⚠ **EACH LEG CARRIES THE ROW IT EXPECTS BACK, AND THE ROW IS IDENTIFIED BY
  // ITS CONNECTION NUMBER — NOT BY THE TERM.** The first run of this block
  // asserted that the TERM appeared in the returned row, and reported *"AND NOT
  // THE ONE SEARCHED FOR"* on two perfectly good searches: the PREMISE column
  // draws the ADDRESS rather than `P-00059`, and the APPLICANT column is
  // `defaultVisible: false`. That is this file's own header warning — reading a
  // field off a list row that the list row does not carry — made again, and it
  // reads exactly like a broken search.
  const legs = [
    ["connection number", allRows[0]?.connection_no ?? null, allRows[0]?.connection_no ?? null],
    ["premise", withPremise?.premises?.premise_no ?? null, withPremise?.connection_no ?? null],
    ["address", (withPremise?.premises?.address ?? "").split(",")[0] || null, withPremise?.connection_no ?? null],
    ["applicant", withApplicant?.applicant ?? null, withApplicant?.connection_no ?? null],
    ["request number", withRequest?.request_no ?? null, withRequest?.connection_no ?? null],
  ];
  for (const [leg, term, expect] of legs) {
    if (term === null || expect === null) { refusals.push(`search by ${leg}: this database offers no row carrying one, so the leg was not walked`); continue; }
    const got = await typeSearch(term);
    if (got === null) break;
    const hit = got.rows.some((r) => r.includes(expect));
    notes.push(`search by ${leg} — typed "${term}" → ${got.rows.length} row(s)${hit ? `, ${expect} among them` : `, WITHOUT ${expect}`}; the server was asked ${got.sentToServer}`);
    if (!hit) refusals.push(`search by ${leg}: "${term}" did not return ${expect}, the row it names`);
    if (!/[?&]q=/.test(got.sentToServer)) refusals.push(`search by ${leg} never reached the server — it asked ${got.sentToServer}, so the narrowing happened in the browser`);
    // ⚠ **A RESULT THAT DOES NOT SAY WHY IT MATCHED IS THE HALF §9 CANNOT SEE.**
    // `NewConnectsTab` states this trade-off in its own words — an APPLICANT
    // column the blueprint does not draw, *"declared and off"*, turned on by the
    // column chooser — so this is REPORTED rather than refused, and it is what a
    // clerk actually meets.
    if (hit && !got.rows.some((r) => r.includes(term)))
      notes.push(`  …and no column on screen shows "${term}", so the clerk cannot see why that row matched`);
  }
  await shot("list-searched");

  // ── THE COLUMN SELECTOR ───────────────────────────────────────────────────
  // ⚠ **THE TOOLBAR CARRIES THREE `<details>` AND THE FILTER IS THE ONLY ONE
  // WITH A WORD IN IT**, so the chooser is found by what it CONTAINS — a
  // per-column tick — rather than by position, which would silently open the
  // wrong disclosure the day a fourth is added.
  await page.goto(LIST, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const headersBefore = await page.$$eval("thead th", (ns) => ns.map((n) => n.innerText.trim()).filter(Boolean));
  notes.push(`the table draws ${headersBefore.length} columns: ${headersBefore.join(" · ")}`);
  const chooserOpened = await page.evaluate(() => {
    for (const d of document.querySelectorAll("details")) {
      if (/filter/i.test(d.querySelector("summary")?.textContent || "")) continue;
      if (d.querySelector('input[type="checkbox"]') === null) continue;
      d.open = true; return true;
    }
    return false;
  });
  if (!chooserOpened) refusals.push("the New connects tab offers no column selector");
  else {
    press("open the column selector");
    await page.waitForTimeout(700);
    await shot("list-column-chooser");
    const dropped = await page.evaluate(() => {
      const d = [...document.querySelectorAll("details[open]")].find((x) => x.querySelector('input[type="checkbox"]'));
      const boxes = [...d.querySelectorAll('input[type="checkbox"]')].filter((b) => b.checked);
      // The LAST ticked column, so the identity column is never the one taken
      // out — a table with no identity column is a different question.
      const box = boxes[boxes.length - 1];
      if (!box) return null;
      const word = (box.closest("label")?.innerText || "").trim().split("\n")[0];
      box.click();
      return word;
    });
    if (dropped === null) refusals.push("the column selector offers nothing to untick");
    else {
      press(`untick the column "${dropped}"`);
      await page.waitForTimeout(1800);
      const headersAfter = await page.$$eval("thead th", (ns) => ns.map((n) => n.innerText.trim()).filter(Boolean));
      const wentAway = headersBefore.length - headersAfter.length;
      notes.push(`unticking "${dropped}" took the table from ${headersBefore.length} columns to ${headersAfter.length}`);
      if (wentAway !== 1) refusals.push(`unticking "${dropped}" changed the column count by ${wentAway}, not by one`);
      // ⚠ **A PREFERENCE THAT DOES NOT SURVIVE A RELOAD IS NOT A PREFERENCE.**
      // `user-preferences/table.S86.columns` is asked for on every load, so a
      // choice that vanished would mean the round trip never happened.
      await page.goto(LIST, { waitUntil: "networkidle" });
      await page.waitForTimeout(2200);
      const headersReloaded = await page.$$eval("thead th", (ns) => ns.map((n) => n.innerText.trim()).filter(Boolean));
      if (headersReloaded.length === headersAfter.length) notes.push(`the column choice survived a reload: ${headersReloaded.length} columns both times`);
      else refusals.push(`the column choice was LOST on reload: ${headersAfter.length} columns, ${headersReloaded.length} after opening the list again`);
      // Put it back, so the next thing to read this database finds the table it expects.
      await page.evaluate((word) => {
        for (const d of document.querySelectorAll("details")) {
          if (d.querySelector('input[type="checkbox"]') === null) continue;
          d.open = true;
          for (const b of d.querySelectorAll('input[type="checkbox"]')) {
            if ((b.closest("label")?.innerText || "").trim().startsWith(word) && !b.checked) b.click();
          }
        }
      }, dropped);
      await page.waitForTimeout(1200);
    }
  }

  // ── `NFR-3` · IS THE PAGINATION REAL? ─────────────────────────────────────
  // ⚠ **THE QUESTION IS NOT *"DOES ONE SCREEN HOLD ALL THE ROWS"*.** With 11
  // builds on file every honest list and every unpaginated one look identical,
  // and the sibling walk that reported *"server pagination is real"* had read
  // the SELECTOR's source rather than driven the screen. Three facts settle it
  // and all three are observed: the browser ASKS for a page, a second page
  // RETURNS DIFFERENT ROWS, and the pager's own controls move with it.
  //
  // ⚠ **`per` CLAMPS UP, NOT DOWN** — `core.pagination.clamp_page_size`'s
  // vocabulary is 50/100/200/500/1000, so `?per=1` answers FIFTY rows. A probe
  // that asked for one row, got fifty and concluded *"`per` is ignored, the
  // list is unpaginated"* would file a defect against a correct list; that
  // probe was written, and this comment is what it cost.
  //
  // `SEED=<n>` raises n empty DRAFT builds through the product's own
  // `POST /connections` so a second page EXISTS. Without it, a database of
  // eleven builds cannot answer the question and this says so rather than
  // reporting a pass.
  await page.goto(LIST, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const firstAsk = asked[asked.length - 1] ?? "(nothing)";
  notes.push(`opening the tab asks the server for ${firstAsk}`);
  if (!/[?&]page=/.test(firstAsk) || !/[?&]per=/.test(firstAsk))
    refusals.push(`the tab does not ask the server for a page at all — it asked ${firstAsk} (NFR-3)`);

  const SEED = Number(process.env.SEED || 0);
  if (SEED > 0) {
    say(`\n── raising ${SEED} draft builds through POST /connections so a second page exists ──`);
    let made = 0;
    for (let i = 0; i < SEED; i += 1) {
      const r = await page.evaluate(async (t) => {
        const res = await fetch(`/api/${t}/connections`, {
          method: "POST", headers: { "content-type": "application/json", accept: "application/json" },
          body: JSON.stringify({ premises_at_commit: true }),
        });
        return res.status;
      }, T);
      if (r === 200 || r === 201) made += 1;
    }
    notes.push(`${made} of ${SEED} draft builds raised, to push the list past one page`);
  }

  await page.goto(LIST, { waitUntil: "networkidle" });
  await page.waitForTimeout(2200);
  const envelope = JSON.parse((await apiGet(`/api/${T}/connections?page=1&per=50`)).body || "{}");
  const total = envelope.count ?? 0;
  const pageOne = await page.$$eval("tbody tr td:first-child", (ns) => ns.map((n) => n.innerText.trim()));
  notes.push(`the server holds ${total} build(s); page one draws ${pageOne.length} row(s), the first being ${pageOne[0] ?? "(none)"}`);
  const next = await page.$('button[aria-label="Next page"]');
  if (!next) { refusals.push("the list draws no pager"); }
  else if (await next.isDisabled()) {
    if (total > 50) refusals.push(`Next page is DISABLED with ${total} builds on file — more than one page of 50`);
    else notes.push(`Next page is correctly disabled: ${total} build(s) is under one page of 50, so a second page CANNOT be walked on this database — run with SEED=45 to make one`);
  } else {
    asked.length = 0;
    await next.click(); press("press Next page");
    await page.waitForTimeout(2400);
    const secondAsk = asked[asked.length - 1] ?? "(nothing)";
    const pageTwo = await page.$$eval("tbody tr td:first-child", (ns) => ns.map((n) => n.innerText.trim()));
    const prev = await page.$('button[aria-label="Previous page"]');
    notes.push(`pressing Next asks the server for ${secondAsk} and returns ${pageTwo.length} row(s), the first being ${pageTwo[0] ?? "(none)"}`);
    if (!/[?&]page=2/.test(secondAsk)) refusals.push(`Next did not ask the server for page 2 — it asked ${secondAsk}, so the pager is slicing in the browser`);
    const overlap = pageTwo.filter((r) => pageOne.includes(r));
    if (overlap.length) refusals.push(`page 2 repeats ${overlap.length} row(s) from page 1 — the server is not slicing (${overlap.slice(0, 3).join(" · ")})`);
    else notes.push(`page 2 shares no row with page 1, so the server sliced rather than the browser`);
    if (prev && await prev.isDisabled()) refusals.push("Previous page is still disabled on page 2");
    await shot("list-page-two");
  }

  // ── B14, READ OFF THE RENDERED TABLE ──────────────────────────────────────
  // Rule 31 — no database id is ever the visible value of a field. Rule 33 —
  // a LABEL is at most three words. And a raw server code reaching a clerk as a
  // word, tested by CASE **and** by shape, because the case test alone passed
  // `parked` and a shape test alone passes `parked` too.
  await page.goto(LIST, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const cells = await page.$$eval("tbody td", (ns) => ns.map((n) => n.innerText.trim()).filter(Boolean));
  const uuids = cells.filter((c) => /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(c));
  if (uuids.length) refusals.push(`B14 rule 31 — a database id is a visible value: ${uuids.slice(0, 3).join(" · ")}`);
  else notes.push(`B14 rule 31 holds: no database id among the ${cells.length} cell values on screen`);
  const heads = await page.$$eval("thead th", (ns) => ns.map((n) => n.innerText.trim()).filter(Boolean));
  const longHeads = heads.filter((h) => h.split(/\s+/).length > 3);
  if (longHeads.length) refusals.push(`B14 rule 33 — a column label runs past three words: ${longHeads.join(" · ")}`);
  else notes.push(`B14 rule 33 holds on the headers: ${heads.length} labels, longest ${Math.max(...heads.map((h) => h.split(/\s+/).length))} word(s)`);
  const codey = cells.filter((c) => /^[a-z][a-z0-9]*(?:[._][a-z0-9]+)+$/.test(c));
  if (codey.length) refusals.push(`a raw server code is on screen as a value: ${[...new Set(codey)].slice(0, 5).join(" · ")}`);
  else notes.push("no cell value reads as a raw server code");
  // ⚠ **TWO OPTIONS THAT READ THE SAME ARE AS BAD AS A CODE, AND NO CHECK
  // ASKED** (`DEF-CUS-6133`): the fix that removed `in_progress_draft` gave it
  // the word `Draft`, which `draft` already had.
  const words = await page.evaluate(() => {
    for (const d of document.querySelectorAll("details")) {
      if (/filter/i.test(d.querySelector("summary")?.textContent || "")) { d.open = true;
        return [...d.querySelectorAll("fieldset label")].map((l) => l.innerText.trim()); }
    }
    return [];
  });
  const dupes = words.filter((w, i) => words.indexOf(w) !== i);
  if (dupes.length) refusals.push(`the filter offers the same word twice, so a clerk cannot tell the two apart: ${[...new Set(dupes)].join(" · ")} (DEF-CUS-6133)`);
  else notes.push(`the filter's ${words.length} words are all different`);

  say(`\n══ §9 PART 4 · THE LIST ══`);
  say(`  ${presses} presses`);
  say(`\n══ REFUSALS AND SNAGS (${refusals.length}) ══`);
  refusals.forEach((r) => say("  · " + r));
  say(`\n══ NOTES (${notes.length}) ══`);
  notes.forEach((r) => say("  · " + r));
  say(`\n══ BROWSER NOISE, NOT THIS PRODUCT (${browserNoise.length}) ══`);
  say(browserNoise.length ? `  ${[...new Set(browserNoise)].join("\n  ")}` : "  (none)");
  writeFileSync(`${OUT}/list-summary.json`, JSON.stringify({ presses, refusals, notes, browserNoise, pressLog }, null, 2));
  say(`\nshots: ${OUT}/${VAR}-list-*`);
  await browser.close();
  process.exit(0);
}

const api = (p, init) => page.evaluate(async ([pp, ii]) => {
  const r = await fetch(pp, ii || { headers: { accept: "application/json" } });
  return { status: r.status, body: await r.text() };
}, [p, init]);

await page.goto(`${BASE}/${T}/connections/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
press("open New Connect");

// ── STEP 1 · Owner & scope ──────────────────────────────────────────────────
await choose("#nc_owner_kind", V.ownerKind, "Owner type");
if (V.noOwnerName !== true) await typeInto("#nc_owner_name", V.party === "company" ? `Walk2 ${VAR} Developments LLC` : `Walk2 ${VAR} Owner`, "Owner or developer");
const subcats = await page.$$eval("#nc_owner_subcategory option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
if (subcats.length) await choose("#nc_owner_subcategory", subcats[subcats.length - 1], "Sub-category");
await typeInto("#nc_owner_email", `walk2.${VAR}@example.test`, "Email");
await typeInto("#nc_owner_phone", "512-555-0" + STAMP.slice(-3), "Phone");
await radio("nc_party_kind", V.party);
await page.waitForTimeout(400);
// A person needs ONE identifier; a company needs its tax id.
if (V.party === "person") {
  if (!(await typeInto("#nc_ssn", `4${STAMP.slice(-2)}-11-${STAMP.slice(-4)}`.slice(0, 11), "Social Security number")))
    await typeInto("#nc_driving_licence", `TX${STAMP}`, "Driving licence");
} else {
  for (const s of ["#nc_tax_id", "#nc_owner_tax_id", "#nc_ein"]) if (await page.$(s)) { await typeInto(s, `TX-${STAMP}`, s); break; }
}
await radio("nc_scope", V.scope);
await radio("nc_mode", "our_crew");
// ⚠ **THE PREFIX IS ASKED ON STEP 1 AND IT NAMES THE UNITS STEP 3 MAKES**
// (`DEF-CUS-5435` moved it here). A variation that needs a label collision
// therefore has to type it on this screen, not on step 3.
if (V.prefix) await typeInto("#nc_prefix", V.prefix, "Prefix");
if (V.docs) {
  const dtypes = await page.$$eval("#nc-owner-doc-type option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
  if (dtypes.length) {
    await choose("#nc-owner-doc-type", dtypes[0], "Document type");
    // ⚠ **THE FILE HAS TO BE ONE THE ALLOWLIST ACCEPTS, OR THE WALK MEASURES
    // ITS OWN TEST DATA (WALK-3, 2026-09-21).** `account_documents.py`'s
    // allowlist is PDF · PNG · JPG · CSV and everything else is a 415
    // (`BR-SHL-031`). The first run of this block attached a `.txt`, the upload
    // was refused after the build had already committed, and the done panel
    // read *"1 document was not filed."* — a true sentence about a file the
    // product was right to refuse. `DOCKIND=txt` still sends the `.txt`, on
    // purpose, because *what a clerk is told when their file is refused* is its
    // own question and the answer today is "after the build is committed".
    const kind = process.env.DOCKIND || "pdf";
    const f = `${OUT}/${VAR}-proof.${kind}`;
    if (kind === "pdf") {
      // The smallest PDF that is a PDF: header, one empty page, xref, trailer.
      const pdf = ["%PDF-1.4", "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj",
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj",
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj",
        "trailer<</Root 1 0 R>>", "%%EOF", ""].join("\n");
      writeFileSync(f, pdf, "latin1");
    } else writeFileSync(f, `WALK3 ${VAR} proof of ownership — stamp ${STAMP}\n`);
    await page.setInputFiles("#nc-owner-doc-file", f);
    press("attach a file");
    await typeInto("#nc-owner-doc-proves", "Proof of ownership", "What it proves");
    const add = await page.$$('button');
    for (const b of add) { if ((await b.innerText()).trim() === "Attach a file") { await b.click(); press('press "Attach a file"'); break; } }
    await page.waitForTimeout(900);
  } else refusals.push("step1: no document type offered");
}
await shot("step1");
await forward("step 1 · Owner & scope");
if (await onStep() === 1) { refusals.push("step 1 would not let the clerk past it"); }

// ── STEP 2 · Premise ────────────────────────────────────────────────────────
const ADDRESS = `${STAMP.slice(-4)} Walk Two ${VAR.toUpperCase()} Lane`;
let pickedAddress = "";
if (V.addressPicked) {
  // "a picked existing address" — the clerk types a fragment and takes a hit
  // instead of typing the whole address again.
  // ⚠ **`fill()` CANNOT FIND THIS PICKER AND A WALK THAT USED IT REPORTS A
  // FALSE ABSENCE.** `#nc_address` is the combined type-or-search box — its own
  // help line reads *"Search the register. Pick the address."* — and it calls
  // `GET /premises/picker?q=` on each KEYSTROKE. `page.fill()` sets the value in
  // one event, and the first run of this walk therefore saw no list, recorded
  // *"offered no existing address to pick"*, and was wrong: typing `240 Sab` a
  // character at a time offers `P-00058 · 240 Sable Court`. Type like a person.
  const q = (await page.$("#nc_address")) ? "#nc_address" : "";
  // ⚠ **WHICH address is picked decides what step 3 can collide with**, so a
  // variation may name its own fragment (`DEF-MET-6111`); the default is the
  // one walk-3 used.
  const fragment = V.pick || "240 Sab";
  if (q) {
    await page.click(q);
    for (const ch of fragment) { await page.keyboard.type(ch); await page.waitForTimeout(150); }
    press("type a fragment of an address already on file");
    chars += fragment.length;
    await page.waitForTimeout(2200);
    const hits = await page.$$eval("button, [role=\"option\"]", (ns) =>
      ns.map((n, i) => ({ i, t: n.innerText.trim() })).filter((x) => /^P-\d+\s+·/.test(x.t)));
    if (hits.length) {
      pickedAddress = hits[0].t;
      const all = await page.$$('button, [role="option"]');
      await all[hits[0].i].click(); press(`pick existing address "${pickedAddress}"`);
      await page.waitForTimeout(1400);
    } else {
      refusals.push("step 2: typing a fragment of an address already on file offered nothing to pick");
    }
  } else refusals.push("step 2: no address box at all");
  // ⚠ **§9's ACTUAL QUESTION IS WHETHER A CLERK CAN DO THIS WITH EASE, AND
  // *"name every place the wizard makes them type something it already knows"*
  // IS THE DELIVERABLE (WALK-3, 2026-09-21).** A press count alone cannot see
  // this: a field left blank costs no press and still stops a clerk, because
  // they have to work out whether a starred field over a premises already on
  // file is theirs to fill. So after a pick, READ THE VALUES the screen is
  // holding and say which of the four facts the register already has came back
  // empty.
  if (pickedAddress) {
    const held = await page.evaluate(() => {
      const g = (id) => { const n = document.getElementById(id); return n ? String(n.value ?? "") : "(no such field)"; };
      return { premiseType: g("nc_premise_type"), city: g("nc_city"), state: g("nc_state"),
               zip: document.getElementById("nc_postal_code") ? String(document.getElementById("nc_postal_code").value ?? "") : g("nc_zip") };
    });
    for (const [what, v2] of Object.entries(held)) {
      if (v2 === "" ) retyped.push(`step 2 asks for ${what} again, empty, over the picked premises ${pickedAddress} — the register already holds it`);
    }
    // ⚠ **A FILLED BOX A CLERK CAN STILL CHANGE IS THE OTHER HALF, AND IT IS
    // THE ONE THAT COSTS (`DEF-CUS-6116`).** The keystroke is not the point:
    // two answers in the product for one fact about one building is. So say
    // which of the register's own facts are OFFERED FOR EDITING over a picked
    // address, beside which arrive as answers.
    const editable = await page.evaluate(() =>
      ["nc_premise_type", "nc_city", "nc_state", "nc_zip", "nc_postal_code"]
        .map((id) => document.getElementById(id))
        .filter((n) => n !== null && !n.disabled && String(n.value ?? "") !== "")
        .map((n) => n.id));
    if (editable.length) notes.push(`over a picked address these arrive filled and REMAIN EDITABLE: ${editable.join(" · ")}`);
    notes.push(`after picking an address the screen holds: ${JSON.stringify(held)}`);
  }
}
if (!pickedAddress) {
  await typeInto("#nc_address", ADDRESS, "Address");
  for (const [s2, v2, lbl] of [["#nc_city", "Austin", "City"], ["#nc_postal_code", "78704", "Postal code"],
                               ["#nc_zip", "78704", "ZIP"], ["#nc_state", "TX", "State"],
                               // ⚠ **THE ID IS `nc_premise_name`, SINGULAR, AND THIS LIST SPELT IT
                               // `nc_premises_name` UNTIL 2026-09-21 (WALK-A).** `page.$` returned
                               // null, the loop skipped it silently, and every build this walk has
                               // ever raised therefore left `premises.name` NULL — which a part-3
                               // readback then reports as a product finding. A walk that skips a
                               // field and reports the column it fills as empty is a false absence
                               // it manufactured itself. Both spellings are tried so the line
                               // cannot go quiet again if the id moves.
                               ["#nc_premise_name", `Walk Two ${VAR}`, "Premises name"],
                               ["#nc_premises_name", `Walk Two ${VAR}`, "Premises name"],
                               ["#nc_name", `Walk Two ${VAR}`, "Name"]]) {
    if (await page.$(s2)) await typeInto(s2, v2, lbl);
  }
}
// ⚠ **A FIELD THE REGISTER HAS ALREADY ANSWERED IS NOT A PRESS (`DEF-CUS-6116`).**
// Over a PICKED address the premise type arrives filled and DISABLED — it is
// the register's answer and not the clerk's to give, which is the whole point:
// a clerk answering differently from the record puts two answers in the product
// for one fact. A walk that went on pressing it would either fail (it did, with
// `element is not enabled`) or, worse, report a press the product no longer
// asks for.
const typeIsOnFile = await page.$eval("#nc_premise_type", (n) => n.disabled).catch(() => false);
const ptypes = typeIsOnFile
  ? []
  : await page.$$eval("#nc_premise_type option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
if (typeIsOnFile) {
  const held = await page.$eval("#nc_premise_type", (n) => n.value).catch(() => "");
  notes.push(`step 2 answered the premise type from the register (${held}) — one press the clerk does not make`);
}
if (ptypes.length) {
  // ⚠ **A SINGLE HOUSE IS ONE DWELLING, AND SINCE `BR-MET-1179` ONE DWELLING
  // HAS TO BE TYPED IN (WALK-3).** The old rule here read the UNIT COUNT and so
  // called every `units > 0` build an apartment block — which made §9's *"a
  // single house"* land on `apartment_complex`. The variation says what kind of
  // property it is; the unit count no longer guesses it.
  const want = V.premiseType
    ? (ptypes.find((x) => x === V.premiseType) ?? ptypes[0])
    : V.units > 1 ? (ptypes.find((x) => /apart|multi|block/i.test(x)) ?? ptypes[0])
                  : (ptypes.find((x) => /single|house|famil/i.test(x)) ?? ptypes[0]);
  await choose("#nc_premise_type", want, "Premise type");
}
// The services control is a chip multi-select reading the tenant's own enabled
// services — never tick boxes. It is `#services_available-add`.
await page.waitForSelector("#services_available-add", { timeout: 12000 }).catch(() => {});
let offered = [];
if (await page.$("#services_available-add")) {
  offered = await page.$$eval("#services_available-add option", (ns) => ns.map((o) => o.value).filter(Boolean));
  const take = V.services === "one" ? offered.slice(0, 1) : offered;
  for (const code of take) { await choose("#services_available-add", code, `service ${code}`); await page.waitForTimeout(250); }
  notes.push(`step 2 offered ${offered.length} services; this build took ${take.length}`);
} else refusals.push("step 2: no services control");
// The plan is asked HERE, once (PO 2026-09-16).
const plans = await page.$$eval("#nc_plan option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
if (!plans.length) refusals.push("step 2: #nc_plan offered no plan — the commit will refuse later");
else await choose("#nc_plan", plans[0], "Plan");
await shot("step2");
await forward("step 2 · Premise");

// ── STEP 3 · Units ──────────────────────────────────────────────────────────
if (await onStep() === 3) {
  if (V.units > 0) {
    // A variation may name the RANGE rather than a count, because a label
    // collision is about the numbers themselves (`DEF-MET-6111`).
    await typeInto("#nc_from", V.from ?? "1", "Units from");
    await typeInto("#nc_to", V.to ?? String(V.units), "Units to");
    await page.waitForTimeout(700);
  }
  // ⚠ **THE BOX IS NAMED NOW, AND IT IS ASKED BOTH WAYS (WALK-3, 2026-09-21).**
  // This block used to take `document.querySelector('input[type=checkbox]')` —
  // the FIRST box on the page, whatever it is — and only ever unticked. Since
  // `BR-MET-1179` the common area is optional on every type and DEFAULT OFF, so
  // a walk that cannot TICK it cannot answer §9's *"with a common area and
  // without"* at all. `#nc_common_area` is the control's own id.
  const box = await page.$("#nc_common_area");
  if (!box) refusals.push("step 3: no #nc_common_area tick box");
  else {
    const startedOn = await box.isChecked();
    notes.push(`step 3 offers the common area ${startedOn ? "ALREADY TICKED" : "unticked"} by default`);
    if (startedOn) refusals.push("step 3 pre-ticks the common area — BR-MET-1179 says default OFF");
    if (V.commonArea === true && !startedOn) {
      await box.evaluate((n) => n.click()); press("tick Include a common-area unit"); await page.waitForTimeout(700);
      if (!(await box.isChecked())) refusals.push(`step 3 REFUSED to tick a common area on this premise type`);
    }
    if (V.commonArea === false && startedOn) {
      await box.evaluate((n) => n.click()); press("untick Include a common-area unit"); await page.waitForTimeout(700);
    }
  }
  // ── `DEF-MET-6111` LAYER 1 · DOES THE STEP SAY SO BEFORE THE PRESS? ──────
  // The commit refusing on step 3 is layer 2 and is the backstop. What the PO
  // asked for FIRST is that a clerk adding `Apt 101` to a building that already
  // has one is told *here*, before they walk five more steps. Read both the
  // strip and the row marks, because they answer different questions: the strip
  // names one label, the table marks every one it shows.
  const saidHere = await page.$$eval("[data-labels-taken]", (ns) => ns.map((n) => n.innerText.trim()))
    .catch(() => []);
  const markedRows = await page.$$eval("[data-label-taken]", (ns) => ns.map((n) => n.innerText.trim()))
    .catch(() => []);
  notes.push(`step 3 warns before the press: ${saidHere.length ? JSON.stringify(saidHere) : "(nothing)"}`);
  notes.push(`step 3 rows marked as already here: ${markedRows.length ? JSON.stringify(markedRows) : "(none)"}`);
  await shot("step3");
  await forward("step 3 · Units");
}

// ── STEP 4 · Map services ───────────────────────────────────────────────────
await page.waitForTimeout(1100);
const grid = await page.evaluate(() => ({
  assets: document.querySelectorAll('[id^="nc_asset_"]').length,
  sizes: document.querySelectorAll('[id^="nc_size_"]').length,
  installs: document.querySelectorAll('[id^="nc_install_"]').length,
}));
notes.push(`step 4 grid: ${grid.assets} asset cells · ${grid.sizes} size cells · ${grid.installs} install-date cells`);
// ⚠ **USING THE GRID IS A DIFFERENT QUESTION FROM COUNTING IT.** The cells are
// pre-resolved — the asset type shows `Meter` and the size shows the FIRST
// size its service offers — so a clerk reads a plausible answer on every row
// without touching anything. What a press of one of them is worth can only be
// answered by pressing it and then asking the database, which is what
// `useGrid` does: pick the LAST option each control offers, so the choice is
// unmistakably not the default, and say what was picked so the readback can be
// compared against it rather than against a guess.
if (V.useGrid) {
  const cells = await page.$$eval('[id^="nc_asset_"]', (ns) => ns.map((n) => n.id));
  const first = cells[0];
  if (!first) refusals.push("step 4: asked to use the grid and there is no asset cell to use");
  else {
    const key = first.replace(/^nc_asset_/, "");
    const types = await page.$$eval(`[id="${first}"] option`, (ns) => ns.map((o) => ({ v: o.value, t: o.textContent || "" })).filter((o) => o.v));
    const wantType = types[types.length - 1];
    if (wantType) { await choose(`[id="${first}"]`, wantType.v, `Asset type on ${key}`); notes.push(`step 4: asset type picked = ${wantType.v} ("${wantType.t.trim()}")`); }
    await page.waitForTimeout(500);
    const sizeSel = `nc_size_${key}`;
    const sizes = await page.$$eval(`[id="${sizeSel}"] option`, (ns) => ns.map((o) => ({ v: o.value, t: o.textContent || "" })).filter((o) => o.v)).catch(() => []);
    const wantSize = sizes[sizes.length - 1];
    if (!sizes.length) notes.push(`step 4: ${sizeSel} offers no size once ${wantType?.v} is picked`);
    else { await choose(`[id="${sizeSel}"]`, wantSize.v, `Size on ${key}`); notes.push(`step 4: size picked = ${wantSize.v} ("${wantSize.t.trim()}")`); }
    notes.push(`step 4: what the grid was told — unit·service ${key}, asset type ${wantType?.v ?? "(none)"}, size ${wantSize?.v ?? "(none)"}`);
  }
}
if (grid.installs > 0) notes.push(`step 4 asks for ${grid.installs} INSTALL DATE(s) at commit time — PO ruled install_date is written on work-order completion`);
await shot("step4");
await forward("step 4 · Map services");

// ── STEP 5 · Work orders ────────────────────────────────────────────────────
await page.waitForTimeout(800);
const stray = await page.$$("#nc_plan, #nc_plan_apartments, #nc_plan_common");
if (stray.length) refusals.push(`step 5 asks for a plan again (${stray.length} picker(s)) — step 2 already did`);
await shot("step5");
await forward("step 5 · Work orders");

// ── STEP 6 · Charges ────────────────────────────────────────────────────────
await page.waitForTimeout(900);
// ⚠ **THE PREVIOUS WALK PRESSED STRAIGHT THROUGH THIS STEP AND THEN REPORTED
// THAT A BUILD SHOWS NO MONEY (WALK-3, 2026-09-21).** That was true of what it
// did and false of the screen: step 6 carries a whole quote builder — a charge
// code, a basis, `+ Charge`, a payer, terms and a posting date — and the build
// prices itself from what is picked here. A walk that never picks one is
// measuring its own restraint, which is law 7's *looking at the wrong thing*.
// `charge: <CODE>` on a variation puts one on, so §9's money clause has
// something to be a yes or a no about.
const CHARGE = process.env.CHARGE || V.charge;
if (CHARGE) {
  const codes = await page.$$eval("#nc_quote_charge_code option", (ns) => ns.map((o) => ({ v: o.value, t: o.textContent || "" })));
  const want = codes.find((c) => c.v === CHARGE || c.t.startsWith(`${CHARGE} `));
  if (!want) refusals.push(`step 6 offers no charge code "${CHARGE}" (${codes.length} offered)`);
  else {
    await choose("#nc_quote_charge_code", want.v, `Charge ${CHARGE}`);
    await page.waitForTimeout(500);
    const bases = await page.$$eval("#nc_quote_charge_basis option", (ns) => ns.map((o) => o.value).filter(Boolean));
    if (bases.length) await choose("#nc_quote_charge_basis", bases[0], "Basis");
    for (const b of await page.$$("button")) {
      if (/^\+\s*Charge$/.test((await b.innerText()).trim())) {
        if (await b.isDisabled()) refusals.push('step 6: "+ Charge" stayed disabled after a code and a basis were chosen');
        else { await b.click(); press('press "+ Charge"'); await page.waitForTimeout(900); }
        break;
      }
    }
    const payer = await page.$('input[name="nc_quote_payer"]:not([disabled])');
    if (payer) { await payer.evaluate((n) => n.click()); press("pick who pays"); await page.waitForTimeout(600); }
    else refusals.push("step 6: every payer choice is disabled");
    // ⚠ **THE TERMS ARE WHAT DECIDE WHETHER THE CHARGE IS EVER ISSUED, AND
    // NOTHING ON STEP 6 SAYS SO (WALK-3).** A build priced with a charge code
    // and no `Payment terms` commits happily and the done panel then reads
    // *"Nobody captured how many days this charge is due in, so it cannot be
    // issued"* — `BR-BIL-024`, correctly, but only after the build exists.
    // `TERMS=""` leaves the box empty on purpose, which is how that was found.
    const terms = process.env.TERMS ?? "30";
    if (terms !== "") await typeInto("#nc_quote_due_days", terms, "Payment terms");
  }
}
const chargeText = await stepText();
const moneyOnScreen = [...chargeText.matchAll(/\$\s?-?[\d,]+\.\d+/g)].map((m) => m[0]);
notes.push(`step 6 shows ${moneyOnScreen.length} money figures: ${[...new Set(moneyOnScreen)].slice(0, 12).join(" · ")}`);
const bad2dp = moneyOnScreen.filter((m) => !/\.\d{2}$/.test(m));
if (bad2dp.length) refusals.push(`step 6 shows money NOT at 2dp: ${bad2dp.join(" · ")}`);
await shot("step6");
await forward("step 6 · Charges");

// ── STEP 7 · Communication ──────────────────────────────────────────────────
await page.waitForTimeout(800);
await shot("step7");
await forward("step 7 · Communication");

// ── STEP 8 · Review & confirm ───────────────────────────────────────────────
await page.waitForTimeout(1100);
const promised = await stepText();
await shot("step8-review");
const reviewMoney = [...promised.matchAll(/\$\s?-?[\d,]+\.\d+/g)].map((m) => m[0]);
const badReview = reviewMoney.filter((m) => !/\.\d{2}$/.test(m));
if (badReview.length) refusals.push(`step 8 shows money NOT at 2dp: ${badReview.join(" · ")}`);
const beforeList = JSON.parse((await api(`/api/${T}/connections?per=1`)).body || "{}");
const beforeTotal = beforeList.total ?? beforeList.count ?? null;
// ── THE TENANT EDITS THE CHARGE CODE BETWEEN STEP 6 AND THE PRESS ───────────
// `DEF-MET-6110`'s second layer. Not a contrivance: it is one clerk on Settings
// while another is mid-build, and it is why a picker filtered at step 6 cannot
// be the guarantee. The edit goes through the product's own door.
const DEPRICE = process.env.DEPRICE || V.deprice;
if (DEPRICE) {
  const list = JSON.parse((await api(`/api/${T}/charges?per=200`)).body || "{}");
  const row = (list.results ?? list.data ?? []).find((c) => c.code === DEPRICE);
  if (!row) refusals.push(`deprice: no charge code ${DEPRICE} to edit`);
  else {
    const patched = await api(`/api/${T}/charges/${row.id}`, {
      method: "PATCH",
      headers: { "content-type": "application/json", accept: "application/json" },
      // A flat fee becomes a percentage — a lawful Settings edit, and the one
      // that makes `charge_by_code` answer `amount: null` from then on.
      // ⚠ **`reason` IS `BR-RAT-1016` AND NOT TEST FURNITURE** — a reprice of a
      // charge code that reaches a plan is refused without one. Leaving it out
      // measured the walk's own payload rather than the product (a 422 that
      // read like the edit had happened).
      body: JSON.stringify({
        amount_rule: "percent",
        amount: null,
        percent: "0.015",
        reason: "Walk: a tenant reprices a connection fee mid-build",
      }),
    });
    notes.push(`Settings edited ${DEPRICE} to a percent rule mid-build → HTTP ${patched.status}`);
    if (patched.status >= 400) refusals.push(`deprice ${DEPRICE}: HTTP ${patched.status} ${patched.body.slice(0, 200)}`);
  }
}
const pressed = await forward("step 8 · REVIEW → COMMIT");
await page.waitForTimeout(7000);
await shot("step9-after-the-press");
const afterUrl = page.url();
const afterText = await stepText();

// ── WHAT THE LAST PRESS ANSWERED, AND WHERE THE CLERK WAS LEFT ──────────────
// `DEF-MET-6110` / `DEF-MET-6111`. Three facts, and each is a different
// question: the HTTP status says whether a rule refused or the product fell
// over; the step number says whether the answer landed where the clerk chose
// the thing; and the work-intact check says whether they still have a build.
const landedOn = await onStep();
const strip = await page.$$eval('[role="alert"]', (ns) => ns.map((n) => n.innerText.trim()).filter(Boolean))
  .catch(() => []);
const fieldsStillHeld = await page.evaluate(() => {
  const g = (id) => { const n = document.getElementById(id); return n ? String(n.value ?? "") : null; };
  return { from: g("nc_from"), to: g("nc_to"), dueDays: g("nc_quote_due_days") };
});
say(`\n══ WHAT THE LAST PRESS ANSWERED ══`);
if (!commitSeen.length) say("  POST /connections/commit was never called");
for (const seen of commitSeen) say(`  HTTP ${seen.status}  ${seen.body.replace(/\s+/g, " ").slice(0, 400)}`);
// ⚠ **THE FOOTER IS THE HALF THAT SAYS *"THE WORK STAYS INTACT"*.** A refusal
// that takes the action row leaves the clerk on the right step with no way
// forward — they have to dismiss a card before they can fix one field. So the
// walk reads the buttons, not only the sentence.
const footer = await page.$$eval('[data-wizard="actions"] button', (ns) => ns.map((n) => n.innerText.trim()))
  .catch(() => []);
const failedCard = await page.$$eval(".state-failed", (ns) => ns.length).catch(() => 0);
say(`  the clerk is left on step ${landedOn}`);
// ⚠ **AN EMPTY FOOTER MEANS TWO OPPOSITE THINGS AND THE LINE HAS TO SAY
// WHICH.** A build that COMMITTED shows the done panel, which has no wizard
// action bar at all — so the first draft of this line printed "the failure
// card took the row" over a perfectly good build. A check whose output
// cannot distinguish a pass from a fail to a reader is worse than no check
// (CLAUDE.md law 7, habit 3), so the step number decides the sentence.
const whyNoFooter = landedOn < 0
  ? "(no wizard footer — the build finished and the done panel is showing)"
  : "(NONE on a wizard step — the failure card took the row)";
say(`  footer buttons: ${footer.length ? footer.join(" · ") : whyNoFooter}`);
say(`  whole-commit failure cards on screen: ${failedCard}`);
say(`  strips on screen: ${strip.length ? strip.map((s) => JSON.stringify(s.slice(0, 120))).join(" · ") : "(none)"}`);
say(`  fields still held: ${JSON.stringify(fieldsStillHeld)}`);

// ── WHAT REACHED THE DATABASE ───────────────────────────────────────────────
const elapsed = Math.round((Date.now() - t0) / 1000);
say(`\n══ THE PRESS COUNT ══`);
say(`  ${presses} discrete clerk acts · ${chars} characters typed · ${elapsed}s wall clock`);
if (DUMP) pressLog.forEach((p2, i) => say(`   ${String(i + 1).padStart(3)} ${p2}`));

const listAfter = JSON.parse((await api(`/api/${T}/connections?per=5&sort=-created_at`)).body || "{}");
const rows = listAfter.data ?? listAfter.results ?? [];
const made = rows[0] ?? null;
say(`\n══ WHAT REACHED THE DATABASE ══`);
say(`  connections before: ${beforeTotal} · after: ${listAfter.total ?? listAfter.count ?? "?"}`);
let connectionNo = "", connectionId = "";
if (!made) { refusals.push("the commit produced no connection row"); }
else {
  connectionNo = made.connection_no ?? made.number ?? "";
  connectionId = made.id ?? "";
  say(`  newest connection: ${connectionNo}  (${connectionId})`);
  const detail = JSON.parse((await api(`/api/${T}/connections/${connectionId}`)).body || "{}");
  const d = detail.data ?? detail;
  writeFileSync(`${OUT}/${VAR}-connection-detail.json`, JSON.stringify(d, null, 2));
  for (const k of Object.keys(d)) {
    const v2 = d[k];
    if (v2 === null || typeof v2 !== "object") say(`  ${k.padEnd(26)} ${JSON.stringify(v2)}`);
    else say(`  ${k.padEnd(26)} ${Array.isArray(v2) ? `[${v2.length}]` : "{…}"}`);
  }
  const rec = await api(`/api/${T}/connections/${connectionId}/record`);
  writeFileSync(`${OUT}/${VAR}-build-record.json`, rec.body);
  say(`  GET /connections/{id}/record → ${rec.status}`);
}
writeFileSync(`${OUT}/${VAR}-summary.json`, JSON.stringify({
  variation: VAR, name: V.name, presses, chars, elapsed, connectionNo, connectionId,
  afterUrl, refusals, notes, retyped, stopAndThink, pressLog,
  commitSeen, landedOn, strip, fieldsStillHeld, footer, failedCard,
  promisedOnReview: (promised.match(/\b\d+\s+(?:units?|meters?|services?|plans?|work orders?|messages?|documents?)/gi) ?? []),
  afterTextHead: afterText.slice(0, 1200),
}, null, 2));
say(`\n══ WHAT THE REVIEW SCREEN PROMISED ══`);
say("  " + ((promised.match(/\b\d+\s+(?:units?|meters?|services?|plans?|work orders?|messages?|documents?)/gi) ?? []).join(" · ") || "(nothing counted)"));
say(`\n══ AFTER THE PRESS ══\n  url: ${afterUrl}\n  ${afterText.split("\n").filter(Boolean).slice(0, 14).join("\n  ")}`);
say(`\n══ WHAT IT ASKED FOR THAT IT ALREADY KNEW (${retyped.length}) ══`);
retyped.forEach((r) => say("  · " + r));
say(`\n══ REFUSALS AND SNAGS (${refusals.length}) ══`);
refusals.forEach((r) => say("  · " + r));
say(`\n══ NOTES (${notes.length}) ══`);
notes.forEach((r) => say("  · " + r));
say(`\nshots + json: ${OUT}/${VAR}-*`);
await browser.close();
