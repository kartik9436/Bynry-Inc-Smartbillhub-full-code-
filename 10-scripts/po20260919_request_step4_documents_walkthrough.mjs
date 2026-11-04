// ── THE NEW-REQUEST WIZARD'S STEP 4 · DOCUMENTS, WALKED IN A BROWSER ───────
//
// `CR-094-BRC01` · the Accounts blueprint's **entry 06, page 78 (TOP)**, read
// AS A PAGE IMAGE at scale 2.6 and again at scale 6 (B14 rule 42 — the small
// labels on that page are vector art and a text search returns NOTHING).
// Run it after any change to step 4 of `ServiceRequestCapturePage.tsx`.
//
// **WHAT IT IS FOR.** No gate in this repo reads rendered output, and this step
// in particular cannot be proved by a unit test: its headline is that the
// `Attach a file` control is no longer refused, and *a control that is present
// and dead* looks identical to *a control that works* in every DOM assertion
// that only checks the element exists. So this walk presses it, with a real
// file, against a real store.
//
// ⚠ **IT PROVES THE BYTES SEPARATELY AND ON PURPOSE.** A row in a table is not
// a file. `DEF-CUS-5872` is six seeded rows that carry a name, a type and a
// `storage_ref` and point at **nothing** — four of them reading `Verified` —
// so every check that reads the ROW passes over them. This walk asserts the
// two halves that actually differ: a real attachment's size comes back from
// the store, and a placeholder's download is REFUSED BY NAME. The sha256
// comparison of the stored bytes is done server-side by
// `po20260919_request_step4_readback.py`, because the dev storage backend
// mints `file://` URLs a browser cannot follow — which is the honest reason
// step 4 draws the file as TEXT and offers no Open control, exactly as p078
// draws it.
//
// ⚠ **IT REFUSES A STALE BUILD, AND STRICTLY.** The sibling walk compares
// `dist/` against the last COMMIT touching `07-frontend/src`, which cannot see
// an uncommitted edit — so a lane that builds, edits and re-runs is told its
// bundle is fresh. This one takes the newest mtime of the working tree as well,
// so an edited-but-unbuilt tree is refused. Proved by touching a source file
// and watching it refuse before it was trusted.
//
// ⚠ **IT WRITES ONE DRAFT AND TAGS IT.** `po20260919_request_steps_purge.py`
// removes it; this walk's tag begins `W1AND3-` so that one purge covers both
// walks and no second deleter has to exist. ⚠ **THE STORED FILE ITSELF CANNOT
// BE PURGED AND THAT IS THE PRODUCT WORKING** — `stored_documents` is
// write-once under a seven-year object lock (`BR-SHL-031`, `NFR-35`), so the
// attachment ROW goes and one small orphan object stays, named by nothing. It
// is 41 bytes. Stated rather than hidden.
//
//   REQ_WALK_BASE     default http://127.0.0.1:8942
//   REQ_WALK_TENANT   default brazosbend
//   REQ_WALK_EMAIL    default dana@brazosbendutilities.com
//   REQ_WALK_PASSWORD default S3cure!passw0rd
//   REQ_WALK_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//   REQ_WALK_DIST     default 07-frontend/dist — the bundle under test
//   REQ_WALK_SHOTS    default ./
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync, writeFileSync, mkdtempSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

const BASE = process.env.REQ_WALK_BASE || "http://127.0.0.1:8942";
const T = process.env.REQ_WALK_TENANT || "brazosbend";
const EMAIL = process.env.REQ_WALK_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.REQ_WALK_PASSWORD || "S3cure!passw0rd";
const CHROME =
  process.env.REQ_WALK_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const DIST = process.env.REQ_WALK_DIST || "07-frontend/dist";
const SHOTS = process.env.REQ_WALK_SHOTS || ".";
const TAG = `W1AND3-S4-${Date.now().toString().slice(-6)}`;

// ── the staleness refusal ──────────────────────────────────────────────────
// Two clocks, because either one alone lies. The COMMIT clock misses an
// uncommitted edit; the MTIME clock misses nothing but is noisy on a fresh
// checkout, where every file carries the checkout time — so the commit time is
// the floor and the working tree is the ceiling.
const built = statSync(`${DIST}/index.html`).mtime;
const lastCommit = new Date(
  execSync("git log -1 --format=%cI -- 07-frontend/src").toString().trim(),
);
const newestEdit = new Date(
  Number(
    execSync(
      "find 07-frontend/src -type f -newermt '2026-01-01' -printf '%T@\\n' | sort -n | tail -1",
    )
      .toString()
      .trim() * 1000,
  ),
);
const newestSrc = newestEdit > lastCommit ? newestEdit : lastCommit;
if (built < newestSrc) {
  console.error(
    `REFUSED: ${DIST}/ was built ${built.toISOString()} but 07-frontend/src has\n` +
      `a change at ${newestSrc.toISOString()}. Run \`npx vite build\` first.\n` +
      `A walk against a stale bundle reports absent features that are present.`,
  );
  process.exit(2);
}

// ⚠ **AND THE BUNDLE THE SERVER IS ACTUALLY SERVING MUST BE THE ONE JUST
// CHECKED — THE STALENESS TEST ABOVE LOOKS AT A DIRECTORY, AND A SERVER IS
// FREE TO BE SERVING A DIFFERENT ONE.** This bit, and it cost twenty minutes:
// the SPA process on the default port had `STATIC_DIR` pointed at a pinned-tip
// worktree, so `07-frontend/dist` was rebuilt and freshly verified while the
// browser went on loading a build from six commits earlier. Every assertion
// then reported the OLD screen, truthfully, and read exactly like a feature
// that had not been built. That is hard-won law 7's *looking at the wrong
// thing*: the check was not lying, it was answering about a directory nobody
// was serving.
//
// So the bundle is identified from BOTH ends and compared. `index.html` names
// its hashed entry chunk, which changes whenever the source does, so this is a
// content comparison wearing a filename.
const entryOf = (html) => (html.match(/assets\/index-[A-Za-z0-9_-]+\.js/) || [null])[0];
const localEntry = entryOf(readFileSync(`${DIST}/index.html`, "utf8"));
const servedEntry = entryOf(await (await fetch(`${BASE}/${T}/requests/new`)).text());
if (localEntry === null || servedEntry === null || localEntry !== servedEntry) {
  console.error(
    `REFUSED: ${BASE} is serving ${servedEntry} but ${DIST}/index.html names\n` +
      `${localEntry}. The server is not serving the bundle this walk just checked,\n` +
      `so every result below would be about a different build.\n` +
      `Point the SPA's STATIC_DIR at ${DIST}, or set REQ_WALK_BASE to the port that serves it.`,
  );
  process.exit(2);
}

const R = [];
const ok = (n, c, d = "") => R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`);

// The file the clerk hands across the counter. Small, real, and its exact bytes
// are what the readback script compares against.
const FILE_BODY = `SMARTBillHub step-4 attach proof ${TAG}\n`;
const scratch = mkdtempSync(join(tmpdir(), "sr-doc-"));
const FILE_PATH = join(scratch, "driving-licence.pdf");
writeFileSync(FILE_PATH, FILE_BODY);

const b = await chromium.launch({ executablePath: CHROME });
const p = await b.newPage({ viewport: { width: 1280, height: 1600 } });

// ⚠ **A CRASH MUST STILL PRINT WHAT PASSED** — most of this walk types into
// controls that only exist once the step is right, so on the unfixed build
// playwright throws and a bare script would exit with a stack trace and no
// findings at all. The red proof for this walk was run exactly that way.
try {
await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);

// ═══════════════════════════════════════════════════════════════════════════
// REACHING STEP 4 — BY PRESSING CONTINUE, NEVER BY ITS URL
// ═══════════════════════════════════════════════════════════════════════════
// The wizard holds the form in component state, so `goto(?step=4)` remounts it
// with an empty form, `canCreateDraft` never becomes true and NO DRAFT ROW IS
// CREATED — and every attach assertion below would then be measuring a screen
// with no request behind it. The sibling walk records the same trap.
await p.goto(`${BASE}/${T}/requests/new?step=1`, { waitUntil: "networkidle" });
await p.waitForTimeout(1500);
await p.fill("#applicant_name", `${TAG} Walker`);
await p.locator("button").filter({ hasText: /^Continue$/ }).first().click();
await p.waitForTimeout(1200);
await p.selectOption("#account_type_code", { index: 1 });
await p.waitForTimeout(500);
await p.locator("button").filter({ hasText: /^Continue$/ }).first().click();
await p.waitForTimeout(1500);
await p.fill("#address_as_given", "Mill Pond");
await p.waitForTimeout(2500);
const option = p.locator('[data-premises-option="P-00045"]');
if ((await option.count()) > 0) {
  await option.click();
  await p.waitForTimeout(1200);
}
await p.locator("button").filter({ hasText: /^Continue$/ }).first().click();
await p.waitForTimeout(2500);
ok("step4 · reached by pressing Continue", /step=4/.test(p.url()), p.url());

const s4 = await p.evaluate(() => document.body.innerText);

// ═══════════════════════════════════════════════════════════════════════════
// THE HEAD AND THE FRAME — p078 top
// ═══════════════════════════════════════════════════════════════════════════
const head = await p.evaluate(() => {
  const h1 = document.querySelector("h1");
  // ⚠ `?? null` NOT `?.textContent` ALONE. The sibling walk recorded that
  // `x !== null` is TRUE for `undefined`, so a probe that bails early reports a
  // title on a page that has none. Every field here is explicitly null-or-value.
  const backs = [...document.querySelectorAll("a,button")]
    .map((el) => (el.textContent || "").trim())
    .filter((s) => s.startsWith("←"));
  return {
    title: h1 ? h1.textContent.trim() : null,
    titlePx: h1 ? Math.round(parseFloat(getComputedStyle(h1).fontSize)) : null,
    backs,
  };
});
ok("step4 · the page-head title reads Documents", head.title === "Documents", String(head.title));
// B14 rule 40, ratified 2026-09-12 — 32px on every screen.
ok("step4 · and it is 32px (B14 rule 40)", head.titlePx === 32, `${head.titlePx}px`);
ok(
  "step4 · the sub-line reads Step 4 of 6 · Documents",
  /Step 4 of 6\s*·\s*Documents/.test(s4),
);
// B14 rule 1 — the head's arrow names where it EXITS to; the footer's means
// previous step only. Both are on this screen, so they must differ.
ok(
  "step4 · the head arrow names the list it exits to",
  head.backs.some((s) => /Requests/.test(s)),
  head.backs.join(" | "),
);
const footer = await p.evaluate(() => {
  const names = [...document.querySelectorAll(".wizard-actions button, [data-wizard-actions] button")]
    .map((el) => el.textContent.trim());
  return names.length > 0
    ? names
    : [...document.querySelectorAll("button")].map((el) => el.textContent.trim());
});
ok("step4 · the footer carries Back", footer.some((s) => /^←?\s*Back$/.test(s)), footer.join("|"));
ok("step4 · the footer carries Continue", footer.some((s) => /^Continue/.test(s)));

// ═══════════════════════════════════════════════════════════════════════════
// THE DRAWN TABLE — DOCUMENT | REQUIRED | FILE | UPLOADED BY | STATE
// ═══════════════════════════════════════════════════════════════════════════
// ⚠ **THE TABLE IS ASSERTED AFTER THE FIRST ATTACH, NOT HERE, AND THAT IS
// THE DRAWING BEING READ RATHER THAN A CHECK BEING MOVED OUT OF THE WAY.**
// p078 draws a table of what the request HOLDS. A request created thirty
// seconds ago holds nothing, so there is no table to draw and the step says so
// instead. Asserting `a table exists` on a brand-new draft would have demanded
// a header over five empty columns -- and worse, it is a check whose only
// passing shape is one the drawing does not draw.
//
// What IS asserted here is the honest empty state, because *"nothing is
// rendered at all"* and *"the step says nothing was brought in"* look identical
// to a check that only asks whether a table is absent.
const emptyState = await p.evaluate(() => ({
  table: document.querySelector('[data-table="capture-documents"]') !== null,
  said: document.querySelector("[data-doc-empty]")?.textContent?.trim() ?? null,
}));
ok(
  "step4 · a request holding nothing draws no table",
  emptyState.table === false,
  String(emptyState.table),
);
ok(
  "step4 · and says so rather than drawing an empty header",
  emptyState.said !== null && emptyState.said.length > 0,
  String(emptyState.said),
);

// ⚠ **THE CHECKBOX LIST IT REPLACED MUST BE GONE.** *"a table exists"* passes
// on a screen that ALSO still draws nine tick-boxes, which is what this step
// was before — and a clerk with two ways to say the same thing is the drift the
// drawing exists to stop.
const oldList = await p.evaluate(
  () => document.querySelectorAll('[data-doc-list] input[type="checkbox"]').length,
);
ok("step4 · the nine-checkbox list is gone", oldList === 0, `${oldList} checkbox(es)`);

// ═══════════════════════════════════════════════════════════════════════════
// THE FOUR FILTER CHIPS — All | Required | Missing | Rejected
// ═══════════════════════════════════════════════════════════════════════════
const chips = await p.evaluate(() =>
  [...document.querySelectorAll("[data-doc-filter]")].map((el) => el.textContent.trim()),
);
ok(
  "step4 · the four drawn chips, in the drawn order",
  JSON.stringify(chips) === JSON.stringify(["All", "Required", "Missing", "Rejected"]),
  JSON.stringify(chips),
);

// ═══════════════════════════════════════════════════════════════════════════
// `Attaching one` — AND THE CONTROL THAT WAS REFUSED
// ═══════════════════════════════════════════════════════════════════════════
const form = await p.evaluate(() => {
  const get = (id) => document.getElementById(id);
  const fileEl = get("capture-doc-file");
  const typeEl = get("capture-doc-type");
  const provesEl = get("capture-doc-proves");
  const reqEl = get("capture-doc-required");
  const lbl = (id) => document.querySelector(`label[for="${id}"]`)?.textContent?.trim() ?? null;
  const btn = (attr) => {
    const el = document.querySelector(`[${attr}]`);
    return el ? { text: el.textContent.trim(), disabled: el.disabled === true } : null;
  };
  return {
    fileTag: fileEl ? fileEl.tagName : null,
    fileType: fileEl ? fileEl.type : null,
    fileDisabled: fileEl ? fileEl.disabled : null,
    fileLabel: lbl("capture-doc-file"),
    typeTag: typeEl ? typeEl.tagName : null,
    typeLabel: lbl("capture-doc-type"),
    typeOptions: typeEl ? [...typeEl.querySelectorAll("option")].length : null,
    provesTag: provesEl ? provesEl.tagName : null,
    provesLabel: lbl("capture-doc-proves"),
    reqTag: reqEl ? reqEl.tagName : null,
    reqLabel: lbl("capture-doc-required"),
    attach: btn("data-doc-attach"),
    add: btn("data-doc-add"),
  };
});
ok("step4 · the Attaching one heading is drawn", /Attaching one/.test(s4));
ok("step4 · Document type is a <select>", form.typeTag === "SELECT", String(form.typeTag));
ok("step4 · labelled Document type", form.typeLabel === "Document type*", String(form.typeLabel));
ok("step4 · it offers the nine designed types", form.typeOptions === 9, String(form.typeOptions));

// ⊕ **THE HEADLINE OF THIS LANE.** The control was a `BlockedControl` carrying
// *"We cannot take a file yet — there is nowhere to store it"* over a store
// that landed this morning. Hard-won law 2's MIRROR: a live path behind a dead
// control. Both halves are asserted — the input exists AND it is not disabled.
ok("step4 · File is a real file input", form.fileTag === "INPUT" && form.fileType === "file",
   `${form.fileTag}/${form.fileType}`);
ok("step4 · and it is NOT disabled", form.fileDisabled === false, String(form.fileDisabled));
ok("step4 · labelled File", form.fileLabel === "File*", String(form.fileLabel));
ok(
  "step4 · the old 'nowhere to store it' refusal is gone",
  !/nowhere to store it|cannot take a file/i.test(s4),
);
ok("step4 · What it proves is a text box", form.provesTag === "INPUT", String(form.provesTag));
ok("step4 · labelled What it proves", form.provesLabel === "What it proves", String(form.provesLabel));
ok("step4 · Required on this request is a checkbox", form.reqTag === "INPUT", String(form.reqTag));
ok(
  "step4 · labelled Required on this request",
  form.reqLabel === "Required on this request",
  String(form.reqLabel),
);
ok("step4 · Attach a file is present and live", form.attach?.text === "Attach a file" && form.attach?.disabled === false,
   JSON.stringify(form.attach));
ok("step4 · Add another document is present and live", form.add?.text === "Add another document" && form.add?.disabled === false,
   JSON.stringify(form.add));

// ═══════════════════════════════════════════════════════════════════════════
// THE COPY — B14 RULE 33, AND THE TWO THINGS IN THE DRAWING THAT ARE NOT COPY
// ═══════════════════════════════════════════════════════════════════════════
// The right rail's plain black prose is the BLUEPRINT talking to its reader.
// Rule 33 puts RATIONALE at zero words on screen and the PO complained about
// these exact sentences on the detail page this week.
ok(
  "step4 · the blueprint's 'never blocks the request' paragraph is not on screen",
  !/never blocks the request being created|A missing document never/i.test(s4),
);
ok(
  "step4 · the blueprint's 'two different facts' paragraph is not on screen",
  !/[Tt]wo different facts decide/.test(s4),
);
// The SOLID RED box is SUPERSEDED — PO 2026-09-16, *"lets not make it
// mandetory"*. `blocks_approval` is a literal False. A screen still printing
// this would be hard-won law 1 wearing a translation.
ok(
  "step4 · the superseded approval gate is not on screen",
  !/[Aa]pproval is blocked until/.test(s4),
);
// ⚠ **THE TWO PARAGRAPHS THAT WERE REALLY THERE, NAMED BY THEIR OWN WORDS.**
// The three assertions above passed on the UNFIXED build — which carried 43
// words of rationale — because the blueprint's wording ("never blocks") and the
// product's ("does not stop") differ by two words. A phrase match is a check
// whose false pass is a synonym, so the budget below is what actually decides
// it and these two only pin the specific sentences that were removed.
ok(
  "step4 · the 24-word not-blocking paragraph is gone",
  !/does not stop the request being created/.test(s4),
);
ok(
  "step4 · the 19-word checklist paragraph is gone",
  !/insists on is set in Settings/.test(s4),
);
// Rule 33: at most ONE short sentence of the step's own prose, and it is
// MEASURED rather than matched — every paragraph on the step that is not a
// field's own help line is counted, so a lane that re-adds rationale under a
// new wording goes red.
// ⚠ **MEASURED PER SENTENCE, NOT SUMMED ACROSS THE STEP -- AND THE
// DIFFERENCE IS THE RULE, NOT A WEAKENING.** An earlier draft of this check
// added every paragraph's words together and demanded six in total. Neither
// rule says that. **Rule 33 caps a FACT at six words each**; **rule 32 allows
// one sentence per SECTION plus a stated absence**. A summed budget therefore
// goes red on a step carrying two perfectly lawful four-word sentences, and --
// far worse -- it goes GREEN on a step carrying one six-word sentence of pure
// RATIONALE, which is the thing rule 33 actually bans and which it cannot see
// at all. So: every paragraph is capped individually, stated absences are
// counted separately because rule 32 names them, and the step may carry AT MOST
// ONE sentence of its own prose.
const prose = await p.evaluate(() => {
  const root = document.querySelector('[data-step-content="documents"]') || document.body;
  const count = (t) => t.replace(/[.·,]/g, " ").trim().split(/\s+/).filter(Boolean).length;
  const paras = [...root.querySelectorAll("p")].filter(
    (el) => !el.classList.contains("field-help") && !el.id.endsWith("-help"),
  );
  // Rule 32 names a STATED ABSENCE as its own thing: the table's "nothing was
  // brought in" and a chip narrowing to nothing are answers, not description.
  const isAbsence = (el) =>
    el.hasAttribute("data-doc-empty") || el.hasAttribute("data-doc-filter-empty");
  const absences = paras.filter(isAbsence).map((el) => el.textContent.trim()).filter(Boolean);
  const texts = paras.filter((el) => !isAbsence(el)).map((el) => el.textContent.trim()).filter(Boolean);
  return {
    texts,
    absences,
    longest: texts.reduce((n, t) => Math.max(n, count(t)), 0),
    longestAbsence: absences.reduce((n, t) => Math.max(n, count(t)), 0),
    words: texts.join(" ").replace(/[.·,]/g, " ").trim().split(/\s+/).filter(Boolean).length,
    note: root.querySelector("[data-doc-note]")?.textContent?.trim() ?? null,
  };
});
ok("step4 · the step carries one short note", prose.note !== null, String(prose.note));
ok(
  "step4 · and it is within rule 33's six words",
  prose.note !== null && prose.note.replace(/[.·]/g, " ").trim().split(/\s+/).filter(Boolean).length <= 6,
  String(prose.note),
);
ok(
  "step4 · the step carries AT MOST ONE sentence of its own prose",
  prose.texts.length <= 1,
  `${prose.texts.length}: ${JSON.stringify(prose.texts)}`,
);
ok(
  "step4 · and no sentence on it exceeds rule 33's six words",
  prose.longest <= 6,
  `longest ${prose.longest} word(s): ${JSON.stringify(prose.texts)}`,
);
ok(
  "step4 · every stated absence is within six words too",
  prose.longestAbsence <= 6,
  `longest ${prose.longestAbsence} word(s): ${JSON.stringify(prose.absences)}`,
);

await p.screenshot({ path: `${SHOTS}/req-step4-before-attach.png`, fullPage: true });

// ═══════════════════════════════════════════════════════════════════════════
// ATTACHING A REAL FILE, END TO END
// ═══════════════════════════════════════════════════════════════════════════
await p.selectOption("#capture-doc-type", "proof_of_identity");
await p.setInputFiles("#capture-doc-file", FILE_PATH);
await p.fill("#capture-doc-proves", "Identity and current address");
// ⚠ **THE LABEL, NEVER THE INPUT.** `CheckboxField` renders its real
// `<input>` as `peer sr-only` and draws the box with a sibling `<span>`, so the
// input has no size and playwright's actionability check waits thirty seconds
// and gives up. `check()` here failed for a reason that has nothing to do with
// the product: a clerk clicks the words, and so does this.
await p.click('label[for="capture-doc-required"]');
ok(
  "attach · ticking Required on this request registers",
  await p.isChecked("#capture-doc-required"),
);
await p.click("[data-doc-attach]");
await p.waitForTimeout(3000);

const readRows = () =>
  p.evaluate(() =>
    [...document.querySelectorAll("[data-doc-row]")].map((tr) => ({
      type: tr.getAttribute("data-doc-row"),
      document: tr.querySelector("[data-doc-name]")?.textContent?.trim() ?? null,
      required: tr.querySelector("[data-doc-required]")?.textContent?.trim() ?? null,
      file: tr.querySelector("[data-doc-file]")?.textContent?.trim() ?? null,
      by: tr.querySelector("[data-doc-by]")?.textContent?.trim() ?? null,
      state: tr.querySelector("[data-doc-state]")?.textContent?.trim() ?? null,
      opens: tr.querySelectorAll("a[href],button[data-doc-open]").length,
    })),
  );

// ══ THE DRAWN TABLE — DOCUMENT | REQUIRED | FILE | UPLOADED BY | STATE ══
// Now that the request HOLDS something, p078's table is what the step must
// draw. Asserted here rather than on the empty step: see the note above.
const table = await p.evaluate(() => {
  const el = document.querySelector('[data-table="capture-documents"]');
  if (!el) return null;
  return { heads: [...el.querySelectorAll("thead th")].map((h) => h.textContent.trim()) };
});
ok("attach · the drawn table is now on the step", table !== null);
ok(
  "attach · its five columns are the drawn five, in the drawn order",
  JSON.stringify(table?.heads) ===
    JSON.stringify(["Document", "Required", "File", "Uploaded by", "State"]),
  JSON.stringify(table?.heads),
);
// And the empty state must GO when the table arrives — a step saying "nothing
// brought in yet" over a table of two documents is the same class of lie as a
// row claiming a file it does not have.
ok(
  "attach · and the nothing-brought-in line is gone",
  (await p.evaluate(() => document.querySelector("[data-doc-empty]") === null)),
);

let rows = await readRows();
const mine = rows.find((r) => r.type === "proof_of_identity");
ok("attach · a row appeared for the attached document", mine !== undefined, JSON.stringify(rows));
ok("attach · DOCUMENT names the type", mine?.document === "Proof of identity", String(mine?.document));
// ⚠ **THE SIZE IS THE HALF THAT CANNOT BE FAKED BY A TICK.** A row created by
// `Add another document` looks identical in every column but this one.
ok(
  "attach · FILE carries the name AND the size, as drawn",
  /driving-licence\.pdf\s*·\s*\d+(\.\d+)?\s*(B|KB|MB)/.test(mine?.file ?? ""),
  String(mine?.file),
);
ok("attach · UPLOADED BY names the clerk and the date", /\w+\s*·\s*\d/.test(mine?.by ?? ""), String(mine?.by));
// Attaching is not verifying — `attach_file` lands `not_checked`, always.
ok("attach · STATE reads Not checked", mine?.state === "Not checked", String(mine?.state));
ok("attach · REQUIRED reads Yes, because the box was ticked", mine?.required === "Yes", String(mine?.required));

// ── `Add another document` — the row with no file, which p078 also draws ───
await p.selectOption("#capture-doc-type", "tenancy_agreement_or_deed");
await p.click("[data-doc-add]");
await p.waitForTimeout(2500);
rows = await readRows();
const ticked = rows.find((r) => r.type === "tenancy_agreement_or_deed");
ok("add · a row appeared with no file", ticked !== undefined, JSON.stringify(rows.map((r) => r.type)));
ok("add · FILE is an em dash, as drawn", ticked?.file === "—", String(ticked?.file));
ok("add · UPLOADED BY is an em dash, as drawn", ticked?.by === "—", String(ticked?.by));
ok("add · STATE reads Nothing attached", ticked?.state === "Nothing attached", String(ticked?.state));

// ⚠ **NOTHING ON THIS STEP MAY OFFER TO OPEN A FILE.** p078 draws the file as
// TEXT, the dev store mints `file://` URLs a browser cannot follow, and
// `DEF-CUS-5872` is six rows that would each have drawn a live-looking link.
const anyOpen = rows.reduce((n, r) => n + r.opens, 0);
ok("attach · no row offers to open a file", anyOpen === 0, `${anyOpen} link(s)`);

await p.screenshot({ path: `${SHOTS}/req-step4-after-attach.png`, fullPage: true });

// ═══════════════════════════════════════════════════════════════════════════
// IT SURVIVES THE STEP — 4 → 5 → 4
// ═══════════════════════════════════════════════════════════════════════════
// The six steps share ONE state object in one 3,705-line file, so a step that
// wrote somewhere the draft read does not reach is exactly the loss nothing in
// this repo goes red for.
await p.locator("button").filter({ hasText: /^Continue$/ }).first().click();
await p.waitForTimeout(2000);
await p.locator("button").filter({ hasText: /^←?\s*Back$/ }).first().click();
await p.waitForTimeout(2000);
rows = await readRows();
ok(
  "round trip · both rows survive stepping forward and back",
  rows.filter((r) => ["proof_of_identity", "tenancy_agreement_or_deed"].includes(r.type)).length === 2,
  JSON.stringify(rows.map((r) => r.type)),
);

// ═══════════════════════════════════════════════════════════════════════════
// IT SURVIVES THE DRAFT — SAVE, CLOSE THE WIZARD, REOPEN IT
// ═══════════════════════════════════════════════════════════════════════════
const requestId = await p.evaluate(() => new URLSearchParams(location.search).get("request"));
ok("round trip · the draft has a request id in the bar", requestId !== null, String(requestId));
// Leave the wizard entirely, then come back at its address. This is the path
// `BR-CUS-093` describes — *"the applicant rings back Thursday quoting it"*.
await p.goto(`${BASE}/${T}/requests`, { waitUntil: "networkidle" });
await p.waitForTimeout(1200);
await p.goto(`${BASE}/${T}/requests/new?request=${requestId}&step=4`, { waitUntil: "networkidle" });
await p.waitForTimeout(3000);
rows = await readRows();
const backAgain = rows.find((r) => r.type === "proof_of_identity");
ok(
  "round trip · the attachment is still there after reopening the draft",
  backAgain !== undefined,
  JSON.stringify(rows.map((r) => r.type)),
);
ok(
  "round trip · with its file name and size",
  /driving-licence\.pdf\s*·\s*\d+(\.\d+)?\s*(B|KB|MB)/.test(backAgain?.file ?? ""),
  String(backAgain?.file),
);
ok("round trip · with its Required tick", backAgain?.required === "Yes", String(backAgain?.required));
ok("round trip · with its state", backAgain?.state === "Not checked", String(backAgain?.state));
const provesBack = await p.evaluate(
  () =>
    document.querySelector('[data-doc-row="proof_of_identity"] [data-doc-proves]')?.textContent?.trim() ??
    null,
);
ok(
  "round trip · and with what it proves",
  provesBack === "Identity and current address",
  String(provesBack),
);
ok(
  "round trip · the no-file row survived too",
  rows.some((r) => r.type === "tenancy_agreement_or_deed" && r.state === "Nothing attached"),
);

// ═══════════════════════════════════════════════════════════════════════════
// THE SERVER — BECAUSE THE SCREEN IS WHERE A WRONG ANSWER LOOKS RIGHT
// ═══════════════════════════════════════════════════════════════════════════
const server = await p.evaluate(
  async ([tenant, id]) => {
    const tab = await (
      await fetch(`/api/${tenant}/service-requests/${id}/documents`, {
        headers: { Accept: "application/json" },
      })
    ).json();
    const docs = (tab.data ?? tab).documents ?? [];
    const real = docs.find((d) => d.doc_type === "proof_of_identity");
    const tick = docs.find((d) => d.doc_type === "tenancy_agreement_or_deed");
    const link = real
      ? await fetch(`/api/${tenant}/service-requests/${id}/documents/${real.id}/download`, {
          headers: { Accept: "application/json" },
        })
      : null;
    const linkBody = link ? await link.json() : null;
    const tickLink = tick
      ? await fetch(`/api/${tenant}/service-requests/${id}/documents/${tick.id}/download`, {
          headers: { Accept: "application/json" },
        })
      : null;
    return {
      real,
      tick,
      linkStatus: link?.status ?? null,
      linkHasUrl: typeof (linkBody?.data ?? linkBody)?.url === "string",
      tickLinkStatus: tickLink?.status ?? null,
      blocksApproval: (tab.data ?? tab).blocks_approval,
    };
  },
  [T, requestId],
);
ok("server · the attachment is recorded with a byte count", typeof server.real?.size_bytes === "number",
   String(server.real?.size_bytes));
ok("server · and the server agrees a real file is held", server.real?.file_present === true,
   String(server.real?.file_present));
ok("server · what it proves reached the column", server.real?.what_it_proves === "Identity and current address",
   String(server.real?.what_it_proves));
ok("server · the required flag reached the column", server.real?.required === true, String(server.real?.required));
ok("server · it landed not_checked, never verified", server.real?.verification_state === "not_checked",
   String(server.real?.verification_state));
ok("server · a download link is issued for the real file", server.linkStatus === 200 && server.linkHasUrl,
   `${server.linkStatus}`);
ok("server · the ticked row holds no file", server.tick?.file_present === false, String(server.tick?.file_present));
// ⚠ This is the assertion `DEF-CUS-5872` is about: a row with no artefact is
// REFUSED a link rather than handed one that 500s on `UUID('sample-data://…')`.
ok("server · and its download is refused, not handed a broken link", server.tickLinkStatus === 422,
   String(server.tickLinkStatus));
// PO 2026-09-16 — *"lets not make it mandetory"*.
ok("server · documents do not block approval", server.blocksApproval === false, String(server.blocksApproval));

// ═══════════════════════════════════════════════════════════════════════════
// THE SIX SEEDED ROWS THAT POINT AT NOTHING — `DEF-CUS-5872`
// ═══════════════════════════════════════════════════════════════════════════
// Four of them read `verified` over a `sample-data://` reference that resolves
// to no stored document at all. The step must draw them without crashing and
// without claiming any of their files can be opened.
const seeded = await p.evaluate(async ([tenant]) => {
  const list = await (
    await fetch(`/api/${tenant}/service-requests?segment=all&per=200`, {
      headers: { Accept: "application/json" },
    })
  ).json();
  const rows = list.data?.results ?? list.results ?? [];
  const osei = rows.find((r) => (r.applicant ?? "").startsWith("Osei"));
  return osei ? osei.id : null;
}, [T]);
if (seeded !== null) {
  await p.goto(`${BASE}/${T}/requests/new?request=${seeded}&step=4`, { waitUntil: "networkidle" });
  await p.waitForTimeout(3000);
  const seededRows = await readRows();
  const crashed = await p.evaluate(
    () => document.body.innerText.includes("Something went wrong") || document.querySelectorAll("[data-table]").length === 0,
  );
  ok("seeded · the placeholder rows render without the step crashing", crashed === false);
  ok("seeded · both of this request's rows are drawn", seededRows.length === 2, String(seededRows.length));
  ok(
    "seeded · not one of them claims a file",
    seededRows.every((r) => r.file === "—"),
    JSON.stringify(seededRows.map((r) => r.file)),
  );
  ok(
    "seeded · and not one of them offers to open one",
    seededRows.every((r) => r.opens === 0),
  );
  ok(
    "seeded · a row with no artefact reads Nothing attached, whatever was ticked",
    seededRows.every((r) => r.state === "Nothing attached"),
    JSON.stringify(seededRows.map((r) => r.state)),
  );
}

console.log(`\nrequest under test: ${requestId}`);
console.log(`proof file bytes: ${Buffer.byteLength(FILE_BODY)} at ${FILE_PATH}`);

} catch (err) {
  ok("the walk ran to the end", false, String(err).split("\n")[0]);
} finally {
  console.log("\n" + R.join("\n"));
  console.log(
    `\n${R.filter((r) => r.startsWith("PASS")).length} PASS · ` +
      `${R.filter((r) => r.startsWith("FAIL")).length} FAIL`,
  );
  console.log(`\nTAG=${TAG}  ← purge with po20260919_request_steps_purge.py (REQ_PURGE=W1AND3-)`);
  await b.close();
  process.exit(R.some((r) => r.startsWith("FAIL")) ? 1 : 0);
}
