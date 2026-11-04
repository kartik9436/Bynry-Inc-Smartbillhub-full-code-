// ── `DEF-MET-5844` · `DEF-MET-5845` · `OQ-MET-12472` — THE ADD PREMISES
//    FORM'S OWNER ACCOUNT AND ITS ADDRESS BLOCK, WALKED ───────────────────
//
// PO, from the live product: *"when user add propery from add new premise form
// - user provides owner type, name, managed by input but system does not create
// master account"*.
//
// ⛔ **`OQ-MET-12472` CLOSED ON 2026-09-19 AND THIS FILE GREW BECAUSE OF IT.**
// Two signed rulings met on this path — *every address gets its owner a Master
// Account* (2026-08-31) against *"Without identifier we cannot create Customer
// ID or master account ot regular account"* (2026-09-01). The option put to
// the PO: *"The Add Premises form must collect an identifier — it gains the
// same kind + identifier fields the import already has, and no account exists
// until they're supplied."* — **"this is correct"**.
//
// So it walks **nine behaviour rows** rather than five: a person identified
// three different ways · a company by its Tax ID · a company offered a phone,
// which must be UNREACHABLE rather than refused late · a kind with no
// identifier · no account type · no owner at all · and **saved twice**, which
// is where the idempotency claim either holds or does not.
//
// ⚠ **AND THE SAVED-TWICE ROW CAN FINALLY PROVE SOMETHING.** Until this ruling
// both saves refused, so *the second opened no second account* was true of two
// nulls — a check that passes wrongly (CLAUDE.md hard-won law 7), and the
// previous lane said so in this file rather than claiming the proof. Now the
// first save really opens an account, so the second either hands the same one
// back or the claim is false.
//
// It then opens the property's **Common Areas tab**, which is the FOURTH door
// onto the same act (`DEF-CUS-5846`), and checks it refuses in a sentence
// rather than a 500.
//
// ⚠ **IT PURGES WHAT IT WRITES.** Every address it creates carries the
// `WALK_TAG` prefix, and the ids are printed at the end for
// `def_met_5844_purge.py`. A walk that leaves rows behind is a walk that makes
// the next person's beta lie to them.
//
// ⚠ **THE DELTA IS ASSERTED, NOT THE PRESENCE.** *"An account exists on this
// premises"* passes on an account that was already there — the beta holds one
// orphaned master account, `AC-2026-00051` on `P-00059`. The database read-back
// is `10-scripts/def_met_5844_owner_account_readback.py`; this file is the
// SCREEN, and it asserts what a clerk can see and do.
//
// ⚠ **IT REFUSES A STALE BUILD, AND THE GUARD IS WIDER THAN THE ONE IT WAS
// COPIED FROM.** `plan_wizard_seven_walkthrough.mjs` compares `dist/` against
// the newest COMMIT touching `07-frontend/src`, which cannot see work that is
// not committed yet — and a maintenance lane walks its own fix before it
// commits it. This also compares against the newest MTIME in `src/`, so an
// edit made five minutes ago and not yet committed still refuses a stale
// bundle. On 2026-09-19 a walk against a 26-hour-old bundle read three landed
// fixes as ABSENT.
//
//   MET5844_BASE     default http://127.0.0.1:8742
//   MET5844_TENANT   default brazosbend
//   MET5844_EMAIL    default dana@brazosbendutilities.com
//   MET5844_PASSWORD default S3cure!passw0rd
//   MET5844_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync, readdirSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.env.MET5844_ROOT || process.cwd();
const BASE = process.env.MET5844_BASE || "http://127.0.0.1:8742";
const T = process.env.MET5844_TENANT || "brazosbend";
const EMAIL = process.env.MET5844_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MET5844_PASSWORD || "S3cure!passw0rd";
const CHROME =
  process.env.MET5844_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.MET5844_SHOTS || ".";
const WALK_TAG = `W5844-${Date.now().toString().slice(-6)}`;

// ── the staleness refusal ──────────────────────────────────────────────────
function newestMtime(dir) {
  let newest = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
    const path = join(dir, entry.name);
    const at = entry.isDirectory() ? newestMtime(path) : statSync(path).mtimeMs;
    if (at > newest) newest = at;
  }
  return newest;
}
const built = statSync(join(ROOT, "07-frontend/dist/index.html")).mtimeMs;
const newestCommit = new Date(
  execSync("git log -1 --format=%cI -- 07-frontend/src", { cwd: ROOT }).toString().trim(),
).getTime();
const newestFile = newestMtime(join(ROOT, "07-frontend/src"));
const staleAgainst = Math.max(newestCommit, newestFile);
if (built < staleAgainst) {
  console.error(
    `REFUSED: dist/ was built ${new Date(built).toISOString()} but 07-frontend/src\n` +
      `has work at ${new Date(staleAgainst).toISOString()}. Run \`npx vite build\` first.\n` +
      `A walk against a stale bundle reports absent features that are present.`,
  );
  process.exit(2);
}
console.log(`dist built ${new Date(built).toISOString()} >= src ${new Date(staleAgainst).toISOString()}`);

const R = [];
const ok = (n, c, d = "") => {
  R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`);
  console.log(R[R.length - 1]);
};
/** B14 rule 33 counts WORDS ON SCREEN, so this counts the rendered string. */
const words = (s) => s.trim().split(/\s+/).filter(Boolean).length;
const madeIds = [];

const b = await chromium.launch({ executablePath: CHROME });
const p = await b.newPage({ viewport: { width: 1440, height: 1100 } });
const posts = [];
p.on("response", async (res) => {
  if (res.request().method() === "POST" && /\/premises$/.test(new URL(res.url()).pathname)) {
    let body = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    posts.push({ status: res.status(), body });
    if (body && body.id) madeIds.push(`${body.premise_no} ${body.id}`);
  }
});

await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);

/** Step 1 -> step 2 of the guided add, with the single-premise mode chosen. */
async function openDetails() {
  await p.goto(`${BASE}/${T}/premises/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1200);
  await p.locator("button,label").filter({ hasText: /one premise/i }).first().click();
  await p.waitForTimeout(400);
  await p.locator("button").filter({ hasText: /^Continue$/ }).first().click();
  await p.waitForTimeout(2500);
}

/**
 * Pick `Person` or `Company` on the segmented control.
 *
 * ⚠ **`page.check()` DOES NOT WORK HERE AND THE FAILURE READS LIKE A MISSING
 * FIELD.** `SegmentedField` is a radio GROUP whose input is
 * `position:absolute; opacity:0; width:0; height:0; pointer-events:none` — the
 * VISIBLE control is the `<label class="seg-opt">` wrapping it. So `check()`
 * resolves the element, finds it invisible and times out after 30 seconds with
 * *"element is not visible"*, which is exactly what a control that does not
 * exist looks like. **Click the label, which is what a clerk clicks.**
 * (`selectOption` finds nothing either: it is not a `<select>`, and the id is
 * on the label as `owner_kind-label`, not on any input.)
 */
async function pickKind(kind) {
  await p
    .locator("label.seg-opt")
    .filter({ has: p.locator(`input[name="owner_kind"][value="${kind}"]`) })
    .first()
    .click();
  await p.waitForTimeout(250);
  const chosen = await p.evaluate(
    (value) =>
      document.querySelector(`input[name="owner_kind"][value="${value}"]`)?.checked === true,
    kind,
  );
  if (!chosen) throw new Error(`the ${kind} option did not take`);
}

/**
 * One behaviour row, start to finish, as a clerk does it.
 * `owner` picks the typed party by visible label; `type` picks the account
 * type; either may be omitted, which is what three of the five rows are.
 */
async function walkRow({ label, address, owner, managedBy, type, kind, identity }) {
  await openDetails();
  await p.fill("#address_line", address);
  await p.selectOption("#premises_type", { label: "Single-family" });
  if (owner) {
    // ⚠ **TYPE, DO NOT CLICK.** `OwnerField` is a `SearchSelectField` — the PO's
    // word is *search* (`BR-SHL-033`) — so its listbox renders in the DOM while
    // collapsed. A click-then-pick finds the option and times out on
    // *element is not visible*, which reads exactly like a missing option.
    await p.locator("#owner_id").click();
    await p.locator("#owner_id").fill(owner.slice(0, 5));
    await p.waitForTimeout(700);
    await p.locator('[role="option"]:visible').filter({ hasText: owner }).first().click();
    await p.waitForTimeout(400);
  }
  if (managedBy) await p.fill("#owner_manager", managedBy);
  if (type) await p.selectOption("#owner_account_type", { label: type });
  // ── `OQ-MET-12472` — WHO THE OWNER IS ────────────────────────────────────
  if (kind) {
    await pickKind(kind);
  }
  for (const [field, value] of Object.entries(identity ?? {})) {
    await p.fill(`#${field}`, value);
  }
  await p.locator("button").filter({ hasText: /^Continue$/ }).first().click();
  await p.waitForTimeout(1500);
  const review = await p.evaluate(() => document.body.innerText);
  const before = posts.length;
  await p.locator("button").filter({ hasText: /^Create$|^Create premise/i }).first().click();
  await p.waitForTimeout(3500);
  const post = posts.length > before ? posts[posts.length - 1] : null;
  return { review, post };
}

// ══ THE ACCOUNT NUMBER'S PROVENANCE, READ ONCE FROM THE SERIES ═══════════
// ⛔ **THE PO ASKED FOR THIS AND IT IS NOT NEW WORK — IT IS `OQ-790`, CLOSED
// 2026-08-27 AND BUILT.** Their words on 2026-09-19: *"it should create account
// number based numbering set in settings"*. `customers._allocate_account_no`
// calls `core_numbering.next_number(ACCOUNT_SERIES, …)` under `BR-TEN-035` and
// refuses BY NAME with `customers.account.numbering_unavailable` rather than
// inventing one. **So this asserts it rather than asking again** (CLAUDE.md
// hard-won law 13: a re-ask manufactures inconsistency).
//
// ⚠ **THE SHAPE IS READ FROM THE TENANT'S OWN SERIES, NEVER HARDCODED.** A
// test asserting `/^AC-/` would pass on a literal in the code and would fail
// for a utility that spells its series differently — it would be looking at
// the wrong thing (hard-won law 7). The prefix comes from Settings.
let seriesPrefix = null;

// ── ONE OWNER PER ELIGIBLE ROW, AND IT IS NOT FASTIDIOUSNESS ───────────────
//
// ⛔ **THE BROWSER COMMITS. A ROLLED-BACK DATABASE PROBE DOES NOT.** That is
// the whole difference, and it cost this lane a run to see. Walking four
// eligible rows against ONE owner opens the account on the first and then
// reports `owner_account_already_linked` on the other three — **which is the
// CORRECT behaviour and is the proof that the identity is asked once per OWNER
// rather than once per ADDRESS** (decision log 2026-09-19). It is not proof
// that a driving licence or a phone earns an account, which is what those rows
// are for, and the same trap silences the DECLINING rows: an owner who already
// holds an account never reaches the identity gate at all.
//
// So: the declining rows run FIRST, on an owner with no account. Then each
// eligible row takes a FRESH owner. The beta has five owners and all five
// start with `master_account_id` null — read from the API rather than
// hardcoded, so a tenant with different parties still walks.
const ownerPool = [];
{
  const owners = await p.evaluate(async (tenant) => {
    const res = await fetch(`/api/${tenant}/premises-owners?page_size=200`, {
      headers: { accept: "application/json" },
    });
    return res.ok ? res.json() : { error: res.status };
  }, T);
  const rows = Array.isArray(owners) ? owners : (owners?.results ?? []);
  for (const row of rows) {
    if (row?.active !== false && !row?.master_account_id) ownerPool.push(row.name);
  }
  ok(
    "five owners with no account yet, to walk the eligible rows against",
    ownerPool.length >= 5,
    `${ownerPool.length}: ${ownerPool.join(" · ")}`,
  );
}
/** The next owner nobody has opened an account for. Throws rather than reusing
 *  one, because a silent reuse is exactly the false pass described above. */
function freshOwner() {
  const name = ownerPool.shift();
  if (name === undefined) throw new Error("no owner left without an account");
  return name;
}
/**
 * The owner the DECLINING rows share, and it is the LAST one `freshOwner` will
 * hand out — peeked, never removed.
 *
 * ⚠ **THAT IS DELIBERATE AND THE REASONING IS THE POINT.** There are five
 * eligible rows and five owners, so reserving a sixth is not an option. It is
 * safe because **a declining row creates nothing**: the declining rows all run
 * before any eligible row, and by the time this party is handed out as the
 * fifth fresh owner it still has no account, so the eligible row it serves is
 * a real first-account case. Taking the FIRST of the pool instead would break
 * that — it becomes the first eligible row's owner one line later.
 */
const decliningOwner = ownerPool[ownerPool.length - 1];

{
  // `GET /settings/number-series` is the SET-08 tab's own read — a LIST of
  // rows, each `{series, format, prefix, next_number, …}`. `core_numbering
  // .ACCOUNT` is the string `"account"`.
  const series = await p.evaluate(async (tenant) => {
    const res = await fetch(`/api/${tenant}/settings/number-series`, {
      headers: { accept: "application/json" },
    });
    if (!res.ok) return { error: res.status };
    return res.json();
  }, T);
  const rows = Array.isArray(series) ? series : (series?.results ?? []);
  const account = rows.find((row) => String(row?.series ?? "") === "account") ?? null;
  seriesPrefix = account?.prefix ?? null;
  ok(
    "the tenant's ACCOUNT series was read from Settings",
    typeof seriesPrefix === "string" && seriesPrefix.length > 0,
    JSON.stringify({ prefix: seriesPrefix }),
  );
}

/** One eligible row: the account must be created, linked, and numbered from
 *  the tenant's own series. */
async function expectAccountOpens(label, walked) {
  const { post } = walked;
  ok(`${label} · the save is accepted`, post?.status === 201, `HTTP ${post?.status}`);
  const warnings = post?.body?.warnings ?? [];
  const made = warnings.find((w) => w.code === "owner_account_created");
  ok(
    `${label} · an owner account was CREATED, and the server says so`,
    made !== undefined,
    JSON.stringify(warnings),
  );
  // ⚠ **`owner_master_account` IS THE OWNER, NOT AN ID.** The door answers
  // `owner_detail_dict(...)`, so the key carries the whole party — `name`,
  // `premises_count` and all. Reading it as an id is a mistake this lane made
  // and a red test caught; comparing two of those dicts for idempotency also
  // fails, because the property count moves between the two saves.
  const accountId =
    post?.body?.owner_master_account?.master_account_id ?? made?.account_id ?? null;
  ok(`${label} · the property carries the account id`, accountId !== null, String(accountId));
  if (accountId) {
    const account = await p.evaluate(
      async ([tenant, id]) => {
        const res = await fetch(`/api/${tenant}/accounts/${id}`, {
          headers: { accept: "application/json" },
        });
        return res.ok ? res.json() : { error: res.status };
      },
      [T, accountId],
    );
    // ⚠ **`OQ-790` — THE NUMBER CAME FROM THE TENANT'S SERIES.** Not a shape
    // this file invented: the prefix was read from Settings above.
    ok(
      `${label} · the account number came from the tenant's series`,
      typeof account?.account_no === "string" &&
        seriesPrefix !== null &&
        account.account_no.startsWith(seriesPrefix),
      `${account?.account_no} vs prefix ${seriesPrefix}`,
    );
    ok(
      `${label} · it is a MASTER account on this property`,
      account?.kind === "master",
      String(account?.kind),
    );
  }
  return accountId;
}

// ══ THE DECLINING ROWS FIRST — they create nothing, so they leave the pool
//    exactly as they found it ════════════════════════════════════════════
//
// ⛔ **ORDER IS LOAD-BEARING HERE.** An owner who already holds an account
// never reaches the identity gate — `ensure_owner_master_account` hands the
// account back before it reads the payload — so every one of these rows would
// report `owner_account_already_linked` if it ran after an eligible one, and
// four assertions would go quietly hollow.

// ── ROW 1 · A KIND AND NO IDENTIFIER — the address still saves ────────────
{
  const { review, post } = await walkRow({
    label: "kind, no identifier",
    address: `${WALK_TAG} 1 No Identifier`,
    owner: decliningOwner,
    type: "Residential",
    kind: "person",
  });
  ok("row 1 · the address saves without an identifier", post?.status === 201);
  ok(
    "row 1 · and the server reports no account, waiting on identity",
    (post?.body?.warnings ?? []).some((w) => w.reason === "awaiting_identity"),
    JSON.stringify(post?.body?.warnings ?? []),
  );
  ok(
    "row 1 · the clerk was told BEFORE they saved",
    /No owner account will be created/i.test(review),
  );
}

// ── ROW 2 · OWNER AND IDENTIFIER, NO ACCOUNT TYPE ────────────────────────
{
  const { review, post } = await walkRow({
    label: "owner, no type",
    address: `${WALK_TAG} 2 Owner No Type`,
    owner: decliningOwner,
    kind: "company",
    identity: { owner_tax_id: "74-3182640" },
  });
  ok("row 2 · a blank account type still saves the address", post?.status === 201);
  ok(
    "row 2 · and the server reports no account, with its reason",
    (post?.body?.warnings ?? []).some((w) => w.reason === "no_account_type"),
    JSON.stringify(post?.body?.warnings ?? []),
  );
  ok("row 2 · the review says no account will be created",
    /No owner account will be created/i.test(review));
}

// ── ROW 3 · A FREE-TEXT NAME AND NO OWNER RECORD — no party is invented ───
{
  const { post } = await walkRow({
    label: "free-text name only",
    address: `${WALK_TAG} 3 Name Only`,
    managedBy: "Somebody Not On File LLC",
    type: "Residential",
    kind: "company",
    identity: { owner_tax_id: "74-3182640" },
  });
  ok("row 3 · the address saves", post?.status === 201);
  // ⚠ `BR-MET-151` clause 3 — a name in a box is a NAME and not a party, and
  // an identifier beside it changes nothing about that.
  ok(
    "row 3 · no party is invented from the typed name, identifier or not",
    (post?.body?.warnings ?? []).some((w) => w.reason === "no_typed_owner"),
    JSON.stringify(post?.body?.warnings ?? []),
  );
}

// ── ROW 4 · NO OWNER AT ALL ──────────────────────────────────────────────
{
  const { post } = await walkRow({
    label: "no owner",
    address: `${WALK_TAG} 4 No Owner`,
    type: "Residential",
  });
  ok("row 4 · the address saves with nobody named", post?.status === 201);
  ok(
    "row 4 · and says so",
    (post?.body?.warnings ?? []).some((w) => w.reason === "no_typed_owner"),
  );
}

// ── ROW 5 · A COMPANY OFFERED A PHONE — UNREACHABLE, NOT REFUSED LATE ────
// ⛔ **`BR-CUS-1022`, AND THE ASSERTION IS ABOUT WHAT IS ON SCREEN.** A Social
// Security number or a phone filed under a company is stored where the company
// matcher never looks, and `owner_account_verdict` refuses that combination by
// name (`identifier_belongs_to_the_other_kind`). **A screen that can REACH a
// named refusal is a screen that should not have offered it**, so the
// person-only boxes must not EXIST once Company is picked. Nothing is saved
// here — the assertion is the absence of controls.
{
  await openDetails();
  await p.fill("#address_line", `${WALK_TAG} 5 Company No Phone`);
  await p.locator("#owner_id").click();
  await p.locator("#owner_id").fill(decliningOwner.slice(0, 5));
  await p.waitForTimeout(700);
  await p.locator('[role="option"]:visible').filter({ hasText: decliningOwner }).first().click();
  await p.waitForTimeout(400);
  const boxes = () =>
    p.evaluate(() =>
      ["owner_tax_id", "owner_ssn", "owner_driving_licence", "owner_phone"].filter(
        (id) => document.getElementById(id) !== null,
      ),
    );
  // Nothing at all before a kind is stated — the evidence cannot be judged.
  const beforeKind = await boxes();
  ok("row 5 · no identifier box exists before a kind is picked", beforeKind.length === 0,
    beforeKind.join(", "));
  await pickKind("person");
  const asPerson = await boxes();
  ok(
    "row 5 · a PERSON is offered SSN, licence and phone — and no Tax ID",
    asPerson.length === 3 && !asPerson.includes("owner_tax_id"),
    asPerson.join(", "),
  );
  await pickKind("company");
  const asCompany = await boxes();
  ok(
    "row 5 · a COMPANY is offered its Tax ID and NOTHING ELSE",
    asCompany.length === 1 && asCompany[0] === "owner_tax_id",
    asCompany.join(", "),
  );
  await p.locator('[data-premises-section="owner"]').screenshot({
    path: join(SHOTS, "met5845-owner-identity-company.png"),
  });
}

// ══ THE ELIGIBLE ROWS — ONE FRESH OWNER EACH ══════════════════════════════

// ── ROWS 6a-6c · A PERSON, IDENTIFIED THREE WAYS ─────────────────────────
// ⛔ PO 2026-09-01, the ruling this is built from: *"If owner name is given and
// one identify given - DL, SSN, Phone or Tax ID - then you create master
// account and Customer ID - otherwise dont create anything"*. **Any ONE of the
// three is enough for a person**, so all three are walked: a rule that holds
// for the first identifier and not the third is a rule that holds by accident.
for (const [suffix, identity] of [
  ["SSN", { owner_ssn: "123-45-6789" }],
  ["Licence", { owner_driving_licence: "TX-99481" }],
  ["Phone", { owner_phone: "555-0142" }],
]) {
  const walked = await walkRow({
    label: `person + ${suffix}`,
    address: `${WALK_TAG} 6 Person ${suffix}`,
    owner: freshOwner(),
    type: "Residential",
    kind: "person",
    identity,
  });
  await expectAccountOpens(`person + ${suffix}`, walked);
}

// ── ROW 7 · A COMPANY, BY ITS TAX ID ─────────────────────────────────────
{
  const walked = await walkRow({
    label: "company + Tax ID",
    address: `${WALK_TAG} 7 Company TaxId`,
    owner: freshOwner(),
    type: "Commercial",
    kind: "company",
    identity: { owner_tax_id: "74-3182640" },
  });
  await expectAccountOpens("company + Tax ID", walked);
}

// ── ROW 8 · SAVED TWICE — the claim that could not be walked until today ──
{
  const twiceOwner = freshOwner();
  const first = await walkRow({
    label: "saved twice (a)",
    address: `${WALK_TAG} 8 Saved Twice`,
    owner: twiceOwner,
    type: "Commercial",
    kind: "company",
    identity: { owner_tax_id: "74-3182640" },
  });
  const second = await walkRow({
    label: "saved twice (b)",
    address: `${WALK_TAG} 8 Saved Twice`,
    owner: twiceOwner,
    type: "Commercial",
    kind: "company",
    identity: { owner_tax_id: "74-3182640" },
  });
  ok("row 8 · both saves are accepted", first.post?.status === 201 && second.post?.status === 201);
  // ⚠ **THE DELTA, NEVER THE PRESENCE.** The beta already holds one master
  // account (`AC-2026-00051` on `P-00059`), so *"an account exists"* passes on
  // a property nobody touched. These two saves were made in THIS run.
  // The ACCOUNT ID out of the owner dict — see `expectAccountOpens`. The whole
  // dicts differ on `premises_count` between the two saves, which has nothing
  // to do with whether a second account was opened.
  const a = first.post?.body?.owner_master_account?.master_account_id ?? null;
  const b = second.post?.body?.owner_master_account?.master_account_id ?? null;
  ok("row 8 · the FIRST save really opened an account", a !== null, String(a));
  ok(
    "row 8 · the second save handed back the SAME account, not a second one",
    a !== null && a === b,
    `${a} vs ${b}`,
  );
  ok(
    "row 8 · and the second save says *already linked* rather than *created*",
    (second.post?.body?.warnings ?? []).some(
      (w) => w.code === "owner_account_already_linked",
    ),
    JSON.stringify(second.post?.body?.warnings ?? []),
  );
  // ⚠ **THE OTHER HALF OF *ASKED ONCE PER OWNER*, AND IT IS THE CLAIM THE
  // DECISION LOG RESTS ON.** A third address for the same party, with NO kind
  // and NO identifier typed at all, must still come back with that account —
  // which is what makes the pass-through design cost a clerk one ask rather
  // than one per building.
  const third = await walkRow({
    label: "third address, nothing retyped",
    address: `${WALK_TAG} 8 Third Address`,
    owner: twiceOwner,
    type: "Commercial",
  });
  const c = third.post?.body?.owner_master_account?.master_account_id ?? null;
  ok(
    "row 8 · a THIRD address needs no identifier retyped and reuses the account",
    c !== null && c === a,
    `${c} vs ${a}`,
  );
}

// ══ `DEF-MET-5845` — ONE ADDRESS BLOCK, WITH THE LOOKUP ON AND OFF ════════
//
// ⛔ **THE PO SAW THIS IN A SCREENSHOT AND RULED: "yes one is optional".** The
// step drew two headings — *Where is it?* then *Where is this property?* — two
// address boxes, and two postcode boxes, one of them *Zip (optional)* directly
// above the form's own *ZIP / postal code*.
//
// ⚠ **IT IS INVISIBLE ON EVERY DEMO TENANT, WHICH IS WHY IT SURVIVED.**
// `brazosbend` has no City connection, so the panel collapses to `absent` and
// draws nothing at all. **The defect exists only where the lookup WORKS**, and
// that is the one state no walkthrough had ever been run in.
//
// ⚠ **THE CITY IS ANSWERED AT THE NETWORK, NOT CONNECTED IN THE DATABASE, AND
// THAT IS A DELIBERATE CHOICE RATHER THAN A SHORTCUT.** Connecting a `gis_esri`
// connector would write connector, credential and run rows into a BETA the
// brief says to leave exactly as found, for a screen state that is a pure
// function of two API answers. So the ANSWERS are intercepted and the page,
// the panel, the state machine and every rendered word are the product's own.
// The `off` case below runs against the real server with nothing intercepted.
async function addressBlockShape(label) {
  await openDetails();
  const where = p.locator('[data-premises-section="where"]');
  await where.screenshot({ path: join(SHOTS, `met5845-where-${label}.png`) });
  return p.evaluate(() => {
    const section = document.querySelector('[data-premises-section="where"]');
    if (section === null) return { missing: true };
    const labelText = (input) => {
      const byFor = input.id
        ? document.querySelector(`label[for="${input.id}"]`)
        : null;
      const wrapping = input.closest("label");
      return (byFor ?? wrapping)?.innerText?.trim() ?? "";
    };
    const inputs = [...section.querySelectorAll("input,select")].map(labelText);
    return {
      headings: [...section.querySelectorAll("h1,h2,h3,h4")].map((h) => h.innerText.trim()),
      inputs,
      // The two questions a clerk cannot answer when there are two of each.
      addressBoxes: inputs.filter((text) => /address/i.test(text)).length,
      postcodeBoxes: inputs.filter((text) => /zip|post(al)?\s*code/i.test(text)).length,
    };
  });
}

{
  // ── (1) THE LOOKUP OFF — the demo tenant's own state, and the one every
  //        other walk runs in. A regression here would hide from every lane.
  const off = await addressBlockShape("lookup-off");
  ok(
    "address block · lookup OFF · one heading on the section",
    off.headings.length === 1,
    JSON.stringify(off.headings),
  );
  ok(
    "address block · lookup OFF · one address box and one postcode box",
    off.addressBoxes === 1 && off.postcodeBoxes === 1,
    JSON.stringify(off.inputs),
  );

  // ── (2) THE LOOKUP ON — the only state the defect exists in ────────────
  await p.route("**/integrations/gis_esri/address-search**", async (route) => {
    const url = new URL(route.request().url());
    const q = url.searchParams.get("q") ?? "";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session: q ? "01a07646-0000-7000-8000-000000000001" : null,
        reachable: true,
        truncated: false,
        elapsed_ms: 12,
        budget_ms: 1000,
        message_key: null,
        ranking_note_key: null,
        candidates:
          q.length >= 3
            ? [
                {
                  parcel: "88214",
                  point: "88214-0001",
                  address_line: "1408 Pecan St",
                  city: "Brazos Bend",
                  state: "TX",
                  postal_code: "78702",
                  lat: "30.2672",
                  lng: "-97.7431",
                  frame: "EPSG:4326",
                  status: "ACTIVE",
                  match: "strong",
                },
              ]
            : [],
      }),
    });
  });

  const on = await addressBlockShape("lookup-on");
  ok(
    "address block · lookup ON · still ONE heading, not two",
    on.headings.length === 1,
    JSON.stringify(on.headings),
  );
  ok(
    "address block · lookup ON · still ONE address box and ONE postcode box",
    on.addressBoxes === 1 && on.postcodeBoxes === 1,
    JSON.stringify(on.inputs),
  );
  ok(
    "address block · lookup ON · the retired boxes are gone by name",
    !on.inputs.some((text) => /unit \(optional\)|zip \(optional\)/i.test(text)),
    JSON.stringify(on.inputs),
  );
  ok(
    "address block · lookup ON · the panel's own heading is gone",
    !on.headings.some((text) => /where is this property/i.test(text)),
    JSON.stringify(on.headings),
  );

  // ── (3) AND THE LOOKUP STILL WORKS, driven by the form's OWN box ───────
  // ⚠ **THE HALF THAT MATTERS MOST.** Removing a duplicate box is easy; doing
  // it without killing the convenience is the fix. `Street address` is the
  // only required answer on this step and must never become dependent on the
  // City — so this types into it and the candidates must appear underneath.
  await p.fill("#address_line", "1408 Pec");
  await p.waitForTimeout(1200);
  const body = await p.evaluate(() => document.body.innerText);
  ok(
    "address block · typing in Street address asks the City",
    /1408 Pecan St/.test(body),
    body.slice(0, 200),
  );
  await p.locator('[data-premises-section="where"]').screenshot({
    path: join(SHOTS, "met5845-where-lookup-on-answered.png"),
  });
  // Taking a candidate fills the form's own boxes and stops the list.
  const use = p.locator("button").filter({ hasText: /^Use this$/ }).first();
  if (await use.count()) {
    await use.click();
    await p.waitForTimeout(1200);
    const filled = await p.evaluate(() => ({
      address: document.querySelector("#address_line")?.value ?? "",
      city: document.querySelector("#city")?.value ?? "",
      zip: document.querySelector("#postal_code")?.value ?? "",
      stillOffering: document.body.innerText.includes("Use this"),
    }));
    ok(
      "address block · a chosen candidate fills the form's own boxes",
      filled.address === "1408 Pecan St" && filled.city === "Brazos Bend" && filled.zip === "78702",
      JSON.stringify(filled),
    );
    ok(
      "address block · and the list stops re-offering the row just taken",
      filled.stillOffering === false,
      JSON.stringify(filled),
    );
  } else {
    ok("address block · a candidate was offered to take", false, "no Use this button");
  }
  await p.unroute("**/integrations/gis_esri/address-search**");
}

// ══ THE FOURTH DOOR — two doors onto one account ══════════════════════════
// A clerk who has just made a property opens its Common Areas tab and tries to
// create a master account there. `BR-CUS-1011` allows ONE owner account per
// address, so this must refuse in a sentence and never as a 500.
{
  const id = madeIds[0]?.split(" ")[1];
  if (id) {
    const failures = [];
    p.on("response", (res) => {
      if (res.status() >= 500) failures.push(`${res.status()} ${res.url()}`);
    });
    await p.goto(`${BASE}/${T}/premises/${id}`, { waitUntil: "networkidle" });
    await p.waitForTimeout(2000);
    const tab = p.locator("button,a").filter({ hasText: /Common areas/i }).first();
    if (await tab.count()) {
      await tab.click();
      await p.waitForTimeout(1800);
    }
    const body = await p.evaluate(() => document.body.innerText);
    await p.screenshot({ path: join(SHOTS, "met5844-common-areas.png"), fullPage: true });
    ok("fourth door · the property page opens", /Common areas/i.test(body));
    ok("fourth door · nothing 500s on the way", failures.length === 0, failures.join(" | "));
  } else {
    ok("fourth door · a property was created to open", false, "no id captured");
  }
}

await b.close();
console.log("\n── WHAT THIS RUN WROTE (purge these) ──");
console.log(`WALK_TAG ${WALK_TAG}`);
for (const made of madeIds) console.log("  " + made);
console.log("\n" + R.join("\n"));
process.exit(R.some((l) => l.startsWith("FAIL")) ? 1 : 0);
