// ── THE DISCOUNT WIZARD (DIS-02), WALKED END TO END AS A CLERK ─────────────
// PO ask, 2026-09-19: *"Run end to end Walk for Discount and Tax also simialr
// to rate and Charge code"*, against the standard they set for all of them:
// *"walk ahould check plasna dn rates work end to end - clark dont have any
// frictions to perform his job, overall user experience is good"*.
//
// IT IS A SCREEN-LEVEL WALK AND IT DOES NOT PRICE A BILL. The PO struck that
// requirement explicitly. Nothing here asserts a money figure off an engine;
// where a figure is checked it is checked as PRESENTATION (two decimals, not
// six — `DEF-RAT-5791`).
//
// WHAT IT COVERS, in the order a clerk meets it:
//   A · the three types that carry a value — percentage, fixed amount, usage
//       allowance — each created from nothing to a saved draft;
//   B · step 2's arithmetic: the three caps, the bill floor, stacking
//       precedence, the exclusivity group, and BLANK versus ZERO;
//   C · step 3's enrolment pair and the contradiction it is meant to refuse;
//   D · step 4's dates, budget cap and exhaustion behaviour — the one setting
//       that lets a BILL RUN move the status on its own;
//   E · step 5's read-back, measured as a FRACTION of what was actually typed;
//   F · the edit door on a LIVE discount, which drafts a new dated version;
//   G · the two fixes of 2.308.5 — word counts per step (`DEF-RAT-5790`) and
//       two-decimal display on the edit door (`DEF-RAT-5791`).
//
// ⚠ **IT REFUSES A STALE BUILD, AND THAT GUARD IS THE POINT.** Copied from
// `plan_wizard_seven_walkthrough.mjs`, which earned it: that walk was first
// run against a `dist/` built 26 hours earlier and three fixes that ARE on
// the branch read as ABSENT. Nothing in the page says how old it is, and
// `tsc`, the suites and every gate are green either way because none of them
// look at `dist/`. A walk against a stale bundle is worse than no walk.
//
//   DISC_WALK_BASE     default http://127.0.0.1:8722
//   DISC_WALK_TENANT   default brazosbend
//   DISC_WALK_EMAIL    default dana@brazosbendutilities.com
//   DISC_WALK_PASSWORD default S3cure!passw0rd
//   DISC_WALK_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser in this container, so the path is passed explicitly — see
//      CLAUDE.md's environment note; never run `playwright install` here.)
//   DISC_WALK_DIST     default 07-frontend/dist — the bundle actually served.
//     Point it at the worktree whose `server.mjs` is answering DISC_WALK_BASE;
//     checking a dist nobody is serving is law 7's "looking at the wrong thing".
//
// ⚠ **RUN IT AGAINST A DATABASE YOU CAN THROW AWAY, AND THAT IS NOT A STYLE
// NOTE (added 2026-09-19).** This walk CREATES discounts — one per type, one
// per scope, several more — and the product has no delete for one, so every
// run leaves them behind. On 2026-09-19 a run against the beta left **26
// discounts and a blocking draft** and the Product Owner cleared them BY HAND.
// One command gives you a private copy and one throws it away:
//
//     eval "$(10-scripts/proof-db.sh clone discwalk --export)"   # DATABASE_URL
//     10-scripts/proof-db.sh drop discwalk
//
// `proof-db.sh` will only ever create and drop a database it named itself, so
// it cannot touch `sbh`, `sbh_dev` or a sibling lane's walkthrough database.
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync } from "node:fs";

const BASE = process.env.DISC_WALK_BASE || "http://127.0.0.1:8722";
const T = process.env.DISC_WALK_TENANT || "brazosbend";
const EMAIL = process.env.DISC_WALK_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.DISC_WALK_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.DISC_WALK_CHROME
  || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const DIST = process.env.DISC_WALK_DIST || "07-frontend/dist";

// ── the staleness refusal ──────────────────────────────────────────────────
const built = statSync(`${DIST}/index.html`).mtime;
const newestSrc = new Date(
  execSync("git log -1 --format=%cI -- 07-frontend/src").toString().trim(),
);
if (built < newestSrc) {
  console.error(
    `REFUSED: ${DIST} was built ${built.toISOString()} but 07-frontend/src has a\n` +
    `commit at ${newestSrc.toISOString()}. Run \`npx vite build\` first.\n` +
    `A walk against a stale bundle reports absent features that are present.`,
  );
  process.exit(2);
}

const R = [];
const ok = (n, c, d = "") => R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`);
const note = (n) => R.push(`NOTE · ${n}`);

// A unique suffix, so the walk is repeatable against one database: a discount
// CODE is unique per tenant and a second run would otherwise die on the commit.
const SFX = Date.now().toString(36).slice(-4).toUpperCase();

const b = await chromium.launch({ executablePath: CHROME });
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } });

// ── clicks and keystrokes are COUNTED, because the deliverable is friction ──
let clicks = 0;
const origClick = p.click.bind(p);
p.click = async (...a) => { clicks += 1; return origClick(...a); };
const tap = async (loc) => { clicks += 1; await loc.click(); };

await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);

// Everything is scoped to <main>. The shell carries an unlabelled `input
// [type=search]` and a sibling's walk once matched it instead of a picker,
// with both assertions passing over a screen that had done nothing.
const M = (sel) => p.locator(`main ${sel}`);
const btn = (re) => p.locator("main button").filter({ hasText: re }).first();
const cont = async () => { await tap(btn(/^Continue$/)); await p.waitForTimeout(700); };
const stepText = () => p.evaluate(() => document.querySelector("main").innerText);
const words = (s) => s.split(/\s+/).filter(Boolean).length;
/** Left the wizard = saved. The commit returns to the LIST; still on `/new`
 *  or still on `/edit` means the server refused and the page stayed put. */
const saved = (url) => !/\/(new|edit)$/.test(new URL(url).pathname);
/** What a refused commit actually SAYS to the clerk, at the button. */
const failureText = () => p.evaluate(() => {
  const n = [...document.querySelectorAll('main [role="alert"]')]
    .map((x) => x.innerText.trim()).filter(Boolean);
  return n.join(" | ").replace(/\s+/g, " ").slice(0, 220) || null;
});
/** ⚠ READ HELP THROUGH `aria-describedby`, NEVER BY WALKING UP THE DOM. A
 *  first draft of this walk took `closest("div").parentElement.innerText` and
 *  got the WHOLE PANEL back for every field — so "does each cap box mention
 *  zero" returned 4/4 while not one of them does. That is law 7's
 *  structurally-incapable-of-failing shape, found by asking what would make
 *  the check pass wrongly. The help element is the one the input POINTS at. */
const helpOf = (ids) => p.evaluate((list) => Object.fromEntries(list.map((id) => {
  const el = document.getElementById(id);
  const d = el?.getAttribute("aria-describedby");
  return [id, d ? d.split(/\s+/).map((x) => document.getElementById(x)?.innerText.trim() || "").join(" ").trim() : ""];
})), ids);
const fieldsOf = () => p.evaluate(() =>
  [...document.querySelectorAll("main input,main select,main textarea")]
    .filter((n) => n.id).map((n) => n.id));

// ══ A · the DISCOUNTS LIST — the door a clerk comes through ═══════════════
await p.goto(`${BASE}/${T}/plans-rates/discounts`, { waitUntil: "networkidle" });
await p.waitForTimeout(1200);
const listText = await stepText();
ok("the discounts list opens with rows", /AUTOPAY/.test(listText) && /SENIOR/.test(listText));
// DEF-RAT-5791 on the LIST: a percentage reads 1.50%, never 1.500000%.
ok("5791 · list values read at two decimals",
   /1\.50%/.test(listText) && !/\.\d{5,}/.test(listText),
   (listText.match(/\d+\.\d+%?/g) || []).slice(0, 6).join(" "));
// A fixed-amount row prints a bare number with no currency mark beside a
// percentage row that prints its unit. Recorded, not asserted.
note(`list · fixed-amount rows print a bare figure: ${
  (listText.match(/Fixed amount\s+([\d.,]+)/) || [])[1] || "n/a"} (percentage rows carry %)`);

// ══ B · CREATE ONE OF EACH TYPE THAT CARRIES A VALUE ══════════════════════
/** Drive the five steps for one type. Returns what the review read back. */
async function create(kind, typeValue, value, extras = {}) {
  const before = clicks;
  await p.goto(`${BASE}/${T}/plans-rates/discounts/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1000);

  // ── step 1 ──
  const w1 = words(await stepText());
  await p.fill("#discount-code", `W${kind}${SFX}`);
  await p.fill("#discount-name", `Walk ${kind} ${SFX}`);
  await M("#discount-type").selectOption(typeValue);
  await p.waitForTimeout(300);
  await cont();

  // ── step 2 ──
  const s2ids = await fieldsOf();
  const w2 = words(await stepText());
  if (s2ids.includes("discount-value")) await p.fill("#discount-value", value);
  if (extras.scope) {
    await M("#discount-scope").selectOption(extras.scope);
    await p.waitForTimeout(600);
    // `one_service` grows a second picker. A walk that skips it is refused at
    // the COMMIT, two steps later, by a message that names no field.
    if (await M("#discount-service").count()) {
      const opts = await p.evaluate(() =>
        [...document.getElementById("discount-service").options].map((o) => o.value).filter(Boolean));
      if (opts.length) await M("#discount-service").selectOption(opts[0]);
    }
  }
  if (extras.capPerBill !== undefined) await p.fill("#discount-cap-per-bill", extras.capPerBill);
  if (extras.floor !== undefined) await p.fill("#discount-floor", extras.floor);
  if (extras.precedence !== undefined) await p.fill("#discount-precedence", extras.precedence);
  if (extras.exclusivity !== undefined) await p.fill("#discount-exclusivity", extras.exclusivity);
  const readBack = await p.evaluate(() =>
    document.querySelector("main [data-value-readback]")?.innerText.trim() ?? null);
  await cont();

  // ── step 3 ──
  const w3 = words(await stepText());
  await p.fill("#discount-eligibility-summary", `Qualifies for ${kind}`);
  if (extras.enrolment) {
    await M("#discount-enrolment").selectOption(extras.enrolment);
    await p.waitForTimeout(600);
    // The proof tick-boxes are `sr-only` behind peer labels, so `.check()`
    // times out on them; the LABEL is the control a person clicks.
    if (extras.proofKind) await tap(p.locator(`main label[for="discount-proof-${extras.proofKind}"]`));
  }
  if (extras.recertMonths !== undefined) await p.fill("#discount-recert-months", extras.recertMonths);
  await cont();

  // ── step 4 ──
  const w4 = words(await stepText());
  await p.fill("#discount-effective-from", "2026-10-01");
  if (extras.budgetCap !== undefined) await p.fill("#discount-budget-cap", extras.budgetCap);
  if (extras.exhaustion) { await M("#discount-exhaustion").selectOption(extras.exhaustion); await p.waitForTimeout(300); }
  await cont();

  // ── step 5 ──
  const s5 = await stepText();
  const w5 = words(s5);
  const reviewRows = await p.evaluate(() =>
    [...document.querySelectorAll("main dl > div")].map((d) =>
      [d.querySelector("dt")?.innerText.trim(), d.querySelector("dd")?.innerText.trim()]));
  await tap(btn(/^Create discount$/));
  await p.waitForTimeout(3000);
  const landed = p.url();
  const failure = saved(landed) ? null : await failureText();
  return { before, spent: clicks - before, w: [w1, w2, w3, w4, w5], readBack, reviewRows, landed, s2ids, s5, failure };
}

// ── B1 · PERCENTAGE, with every arithmetic control on step 2 filled ───────
const pct = await create("PCT", "percentage", "15", {
  capPerBill: "20", floor: "0", precedence: "10", exclusivity: "INCOME",
  budgetCap: "12000", exhaustion: "suspend", recertMonths: "12",
  enrolment: "apply_and_approve_with_proof", proofKind: "government_id",
});
// ⚠ A SAVE LANDS ON THE LIST, NOT ON THE THING JUST MADE. `saved()` is
// written from what the product DOES, not from what a walk expected: the
// commit leaves `/new`, and anything still on `/new` was refused.
ok("A · a PERCENTAGE discount saves and leaves the wizard", saved(pct.landed),
   pct.landed.split("/").slice(-2).join("/") + (pct.failure ? ` — refused: ${pct.failure}` : ""));
note(`A · percentage: ${pct.spent} clicks, five steps of ${pct.w.join("/")} words (${
  pct.w.reduce((a, c) => a + c, 0)} total)`);
ok("B · step 2's read-back echoes what was typed", pct.readBack !== null, pct.readBack || "absent");

// ⚠ THE REVIEW IS MEASURED AS A FRACTION. Step 5 draws a FIXED list of rows,
// so the question is not "is there a review" but "of the things this clerk
// chose, how many does it read back".
const shown = pct.reviewRows.map((r) => (r[0] || "").toUpperCase());
const typedFacts = {
  "CAP PER BILL": "20", "BILL FLOOR": "0", "EXCLUSIVITY GROUP": "INCOME",
  "BUDGET CAP": "12000", "BUDGET RUNS OUT": "Suspend", "EFFECTIVE FROM": "2026-10-01",
  "WHO QUALIFIES": "Qualifies for PCT", "RECERTIFY EVERY (MONTHS)": "12",
};
const missing = Object.keys(typedFacts).filter((k) => !shown.includes(k));
ok("E · step 5 reads back the bill floor", shown.includes("BILL FLOOR"));
ok("E · step 5 reads back the budget cap", shown.includes("BUDGET CAP"));
ok("E · step 5 reads back the effective date", shown.includes("EFFECTIVE FROM"));
note(`E · review draws ${pct.reviewRows.length} rows: ${shown.join(", ")}`);
note(`E · ${missing.length} of ${Object.keys(typedFacts).length} things typed on steps 2-4 are NOT read back: ${missing.join(", ")}`);
const blankRow = pct.reviewRows.filter((r) => !r[1]);
ok("E · no review row is drawn with an empty value", blankRow.length === 0,
   blankRow.map((r) => r[0]).join(", ") || "none");

// ── B2 · FIXED AMOUNT ────────────────────────────────────────────────────
const fix = await create("FIX", "fixed_amount", "25", { capPerBill: "", floor: "" });
ok("A · a FIXED AMOUNT discount saves", saved(fix.landed),
   fix.landed.split("/").pop() + (fix.failure ? ` — refused: ${fix.failure}` : ""));
note(`A · fixed amount: ${fix.spent} clicks, steps ${fix.w.join("/")} words`);
ok("A · a fixed amount asks which currency", fix.s2ids.includes("discount-currency"),
   fix.s2ids.join(","));

// ── B3 · USAGE ALLOWANCE ─────────────────────────────────────────────────
// BR-RAT-960: an allowance is a QUANTITY and takes its unit from the SERVICE,
// so the scope has to name one. Whole-bill leaves `2` meaning nothing.
const usg = await create("USG", "usage_allowance", "2", { scope: "one_service" });
ok("A · a USAGE ALLOWANCE discount saves", saved(usg.landed),
   usg.landed.split("/").pop() + (usg.failure ? ` — refused: ${usg.failure}` : ""));
note(`A · usage allowance: ${usg.spent} clicks, steps ${usg.w.join("/")} words`);

// ══ C · THE TWO TYPES THAT CARRY NO VALUE ════════════════════════════════
await p.goto(`${BASE}/${T}/plans-rates/discounts/new`, { waitUntil: "networkidle" });
await p.waitForTimeout(900);
await p.fill("#discount-code", `WOVR${SFX}`);
await p.fill("#discount-name", `Walk override ${SFX}`);
await M("#discount-type").selectOption("rate_override");
await cont();
const ovr = await stepText();
ok("C · rate override says it cannot go live, instead of a value box",
   /cannot go live/i.test(ovr) && !(await fieldsOf()).includes("discount-value"), ovr.split("\n").find((l) => /cannot go live/i.test(l)) || "");
await M("#discount-type") // back to step 1 to switch type
  .count().catch(() => 0);
await tap(btn(/^Back$/)); await p.waitForTimeout(600);
await M("#discount-type").selectOption("charge_waiver");
await cont();
const wvr = await stepText();
ok("C · charge waiver says why it needs no value",
   /removes the whole charge/i.test(wvr), wvr.split("\n").find((l) => /removes the whole/i.test(l)) || "");

// ══ D · BLANK versus ZERO, which decides whether a bill can reach nothing ══
await p.goto(`${BASE}/${T}/plans-rates/discounts/new`, { waitUntil: "networkidle" });
await p.waitForTimeout(900);
await p.fill("#discount-code", `WZRO${SFX}`);
await p.fill("#discount-name", `Walk zero ${SFX}`);
await cont();
const capsPanel = await p.evaluate(() => {
  const heads = [...document.querySelectorAll("main section")];
  const sec = heads.find((s) => /CAPS/i.test(s.innerText));
  return sec ? sec.innerText : "";
});
ok("D · the caps panel states blank versus zero",
   /blank means uncapped/i.test(capsPanel) && /zero grants nothing/i.test(capsPanel));
ok("D · the bill floor states blank versus zero",
   /blank means no floor/i.test(capsPanel) && /zero allows a zero bill/i.test(capsPanel));
// ⚠ AND THE QUESTION THE PO ACTUALLY ASKED: does the help UNDER EACH CAP BOX
// say it? The panel note is one line above three boxes that each carry a
// DIFFERENT sentence, so a clerk reading the help under "Cap per year" is told
// about storage precision and nothing about zero.
const perCapHelp = await helpOf(
  ["discount-cap-per-bill", "discount-cap-per-year", "discount-cap-lifetime", "discount-floor"]);
const zeroSaid = Object.entries(perCapHelp).filter(([, v]) => /zero/i.test(v)).map(([k]) => k);
ok("D · each cap box's own help mentions zero", zeroSaid.length === 4,
   `${zeroSaid.length}/4 do — ${JSON.stringify(perCapHelp["discount-cap-per-year"]).slice(0, 90)}`);
// Typing ZERO must not be silently rewritten to blank, and must not vanish.
await p.fill("#discount-cap-per-bill", "0");
await p.fill("#discount-floor", "0");
await p.waitForTimeout(400);
const zeroKept = await p.evaluate(() => [
  document.getElementById("discount-cap-per-bill").value,
  document.getElementById("discount-floor").value,
]);
ok("D · a typed zero stays a zero in the box", zeroKept.every((v) => v === "0"), zeroKept.join(" / "));

// ══ E · THE CONTRADICTION step 3 is meant to refuse ═══════════════════════
await cont();
const enrolOpts = await p.evaluate(() =>
  [...document.getElementById("discount-enrolment").options].map((o) => o.value));
// CR-087 C1 collapsed two controls (mode + a proof tick-box) into one list of
// three, so the fourth combination — automatic enrolment demanding proof — is
// no longer EXPRESSIBLE. The refusal still exists in the code and can only be
// reached by a stored row that predates the gate. That is the right answer to
// "can the clerk understand and escape it": they cannot enter it.
ok("E · the impossible pair cannot be picked at all",
   enrolOpts.length === 3 && !enrolOpts.includes("automatic_with_proof"), enrolOpts.join(" / "));
// ⚠ BUT THE NEIGHBOURING PAIR IS STILL FREELY CONTRADICTORY. Enrolment
// `Automatic — no application` with Verification `One-time proof at enrolment`
// is two controls saying opposite things, and nothing on the screen objects.
await M("#discount-enrolment").selectOption("automatic");
await p.waitForTimeout(300);
await M("#discount-verification").selectOption("one_time_proof");
await p.waitForTimeout(500);
const contradictoryBlocked = await btn(/^Continue$/).isDisabled();
const step3Text = await stepText();
ok("E · automatic enrolment + one-time-proof verification is flagged",
   contradictoryBlocked || /cannot demand proof|contradict/i.test(step3Text),
   contradictoryBlocked ? "Continue blocked" : "nothing said, Continue enabled");
// The recertification trio: what a clerk is told about notice and grace.
const recertHelp = await helpOf(
  ["discount-recert-months", "discount-recert-notice", "discount-recert-grace"]);
ok("E · notice and grace say what they count from",
   !!recertHelp["discount-recert-notice"] && !!recertHelp["discount-recert-grace"],
   `notice=${JSON.stringify(recertHelp["discount-recert-notice"])} grace=${JSON.stringify(recertHelp["discount-recert-grace"])}`);

// ══ F · STEP 4 — the setting a BILL RUN can act on ════════════════════════
await cont();
const s4 = await stepText();
ok("F · step 4 says saving enrols nobody", /saving enrols nobody/i.test(s4));
ok("F · step 4 says a status can change on its own",
   /changes the status automatically/i.test(s4),
   s4.split("\n").find((l) => /automatically/i.test(l)) || "absent");
// ⚠ It says a status changes automatically and never says WHAT changes it.
note(`F · exhaustion help names no actor: ${JSON.stringify(
  (s4.split("\n").find((l) => /automatically/i.test(l)) || "").trim())} — a BILL RUN is what sets it (BR-RAT-072)`);
ok("F · an end date is optional and says so", /blank end date/i.test(s4));

// ══ F2 · THE TWO DEAD ENDS — a job a clerk starts and cannot finish ═══════
// Both are the same shape: a choice made on an EARLY step is refused at the
// COMMIT on step 5, by a sentence that names neither the field nor the step.
// Nothing on the step that raised it objects at the time.

/** Walk to the commit with one deliberate omission and report what is said.
 *
 * ⚠ **IT ONLY PRESSES `Create discount` IF THE WIZARD LET IT GET THERE, AND
 * THAT CHANGED ON 2026-09-19.** These two cases exist to ask *where* an
 * omission is caught. While both were caught only at the COMMIT, the walk
 * always reached step 5 and the button was always present. Now that
 * `DEF-RAT-5816`'s objection is on step 3, a blocked walk is still standing on
 * step 3 — **there is no commit button on that screen at all** — and pressing
 * for one timed out after thirty seconds and killed the whole run.
 * **A harness that cannot express the fixed behaviour reports the fix as a
 * crash**, which is law 7's *looking at the wrong thing* wearing a red tick.
 * So `fill()` may answer `{ stopped: true }` and the commit is skipped. */
async function deadEnd(code, fill) {
  await p.goto(`${BASE}/${T}/plans-rates/discounts/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(900);
  await p.fill("#discount-code", `${code}${SFX}`);
  await p.fill("#discount-name", `Walk ${code} ${SFX}`);
  const r = await fill();
  if (r.stopped) {
    return { ...r, landed: p.url(), failure: await failureText(), reachedCommit: false };
  }
  await tap(btn(/^Create discount$/));
  await p.waitForTimeout(3000);
  return { ...r, landed: p.url(), failure: await failureText(), reachedCommit: true };
}

// F2a · "Apply and approve, with proof" and no document ticked.
const noProof = await deadEnd("WNOP", async () => {
  await cont(); await p.fill("#discount-value", "10"); await cont();
  await M("#discount-enrolment").selectOption("apply_and_approve_with_proof");
  await p.waitForTimeout(600);
  const blockedHere = await (async () => {
    const b4 = await stepText(); await tap(btn(/^Continue$/)); await p.waitForTimeout(700);
    return /STEP 3 OF 5/.test(await stepText()) ? b4 : null;
  })();
  if (blockedHere === null) { await p.fill("#discount-effective-from", "2026-10-01"); await cont(); }
  // Blocked on step 3 is the WANTED outcome, and there is no commit button
  // there — so the walk stops, and what the clerk was told is read off the
  // step itself rather than off a refusal panel that never appears.
  return { blockedAtStep3: blockedHere !== null, stopped: blockedHere !== null,
           saidAtStep3: blockedHere === null ? null
             : (await stepText()).split("\n").find((l) => /document/i.test(l))?.trim() ?? null };
});
ok("F2 · with-proof and no document is caught on STEP 3, where it is chosen",
   noProof.blockedAtStep3, noProof.blockedAtStep3 ? "blocked" : "walked on to the commit");
// ⚠ THE FIRST DRAFT OF THIS CHECK PASSED ON THE DEFECT IT WAS WRITTEN FOR.
// It tested the LAST `|`-separated fragment, which is the long generic panel,
// so the raw key sitting in the FIRST fragment never reached the regex. Look
// for a bare dotted identifier ANYWHERE in what the clerk is shown.
const RAW_KEY = /(?:^|\s)[a-z][a-z0-9]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*){2,}(?:\s|$)/;
ok("F2 · the with-proof refusal is a sentence, not a message key",
   noProof.failure === null || !RAW_KEY.test(noProof.failure),
   JSON.stringify((noProof.failure || "").match(RAW_KEY)?.[0]?.trim() || "no raw key"));
// ⚠ AND THE SAME QUESTION OF WHAT STEP 3 ITSELF SAYS, because once the block
// lands there the commit panel is never reached and the check above passes
// over a screen it never saw (`DEF-RAT-5816`).
ok("F2 · and what step 3 says is a sentence, not a message key",
   noProof.saidAtStep3 === null || !RAW_KEY.test(noProof.saidAtStep3),
   JSON.stringify(noProof.saidAtStep3 || "step 3 said nothing"));
note(`F2 · with-proof, no document → ${
  noProof.reachedCommit === false ? "STOPPED ON STEP 3: " + JSON.stringify(noProof.saidAtStep3)
    : (saved(noProof.landed) ? "SAVED" : "refused") + ": " + JSON.stringify(noProof.failure)}`);

// F2b · scope "One service" and no service picked.
const noSvc = await deadEnd("WNOS", async () => {
  await cont(); await p.fill("#discount-value", "10");
  await M("#discount-scope").selectOption("one_service"); await p.waitForTimeout(600);
  const b4 = await stepText(); await tap(btn(/^Continue$/)); await p.waitForTimeout(700);
  const blockedHere = /STEP 2 OF 5/.test(await stepText());
  if (!blockedHere) { await cont(); await p.fill("#discount-effective-from", "2026-10-01"); await cont(); }
  return { blockedAtStep2: blockedHere, stopped: blockedHere, b4 };
});
ok("F2 · one-service and no service is caught on STEP 2, where it is chosen",
   noSvc.blockedAtStep2, noSvc.blockedAtStep2 ? "blocked" : "walked on to the commit");
ok("F2 · the refusal names the field it is about",
   noSvc.failure === null || /service/i.test(noSvc.failure),
   JSON.stringify(noSvc.failure));
note(`F2 · one service, none picked → ${saved(noSvc.landed) ? "SAVED" : "refused"}: ${JSON.stringify(noSvc.failure)}`);

// ══ F3 · EVERY SCOPE THE DROPDOWN OFFERS, SAVED ══════════════════════════
// ⚠ THE DROPDOWN IS THE PROMISE. A scope a clerk can pick and cannot save is
// a dead end with no warning on it, and three of these are exactly that at
// the time of writing: `one_service` posts a service CODE into a UUID foreign
// key, and `all_services` / `specific_services` — the pair `CR-091-BRC01`
// added on the PO's 2026-09-10 request — are refused by the DATABASE, whose
// `ck_discount_versions_scope` still lists only the original five. All three
// reach the clerk as *"Something went wrong on our side."*
const SCOPES = ["whole_bill", "one_service", "usage_only", "base_only",
                "named_codes", "all_services", "specific_services"];
const scopeResult = {};
for (const scope of SCOPES) {
  await p.goto(`${BASE}/${T}/plans-rates/discounts/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(900);
  await p.fill("#discount-code", `SC${scope.slice(0, 4).toUpperCase()}${SFX}`);
  await p.fill("#discount-name", `Scope ${scope} ${SFX}`);
  await cont();
  await p.fill("#discount-value", "10");
  await M("#discount-scope").selectOption(scope);
  await p.waitForTimeout(700);
  // Each scope's own second control, filled the way a clerk would.
  if (await M("#discount-service").count()) {
    const o = await p.evaluate(() => [...document.getElementById("discount-service").options]
      .map((x) => x.value).filter(Boolean));
    if (o.length) await M("#discount-service").selectOption(o[0]);
  }
  const chipAdd = M('[data-chip-add="discount-services"]');
  if (await chipAdd.count()) {
    const o = await p.evaluate(() => [...document.querySelector('[data-chip-add="discount-services"]').options]
      .map((x) => x.value).filter(Boolean));
    if (o.length) await chipAdd.selectOption(o[0]);
    await p.waitForTimeout(400);
  }
  const codeBox = M('input[id^="discount-code-"]').first();
  if (await codeBox.count()) {
    const id = await codeBox.getAttribute("id");
    await tap(p.locator(`main label[for="${id}"]`));
    await p.waitForTimeout(300);
  }
  await cont(); await cont();
  await p.fill("#discount-effective-from", "2026-10-01");
  await cont();
  await tap(btn(/^Create discount$/));
  await p.waitForTimeout(2800);
  scopeResult[scope] = saved(p.url()) ? "saved" : (await failureText() || "refused").slice(0, 60);
}
const deadScopes = Object.entries(scopeResult).filter(([, v]) => v !== "saved");
ok("F3 · every scope the dropdown offers can be saved", deadScopes.length === 0,
   deadScopes.map(([k, v]) => `${k} → ${v}`).join(" ;; ") || "all seven save");
const crashed = deadScopes.filter(([, v]) => /went wrong on our side/i.test(v));
ok("F3 · no scope reaches the clerk as a server crash", crashed.length === 0,
   crashed.map(([k]) => k).join(", ") || "none");
note(`F3 · scope sweep: ${Object.entries(scopeResult).map(([k, v]) => `${k}=${v === "saved" ? "saved" : "REFUSED"}`).join(" · ")}`);

// ⚠ **AND THE SAVE IS NOT THE ASSERTION — THE STORED VALUE IS (`DEF-RAT-5814`,
// hard-won law 7).** *What would make this check pass wrongly?* A scope that
// silently fell back to `whole_bill` on the way to the database: the row would
// save, the URL would leave `/new`, every line above would report PASS, and
// the clerk's choice would be gone. **Two of this walk's own checks first
// PASSED on the defects they were written for**, which is why this one reads
// the column back out through the API the screen itself uses.
const storedScopes = await p.evaluate(async ([tenant, sfx]) => {
  const res = await fetch(`/api/${tenant}/discounts?page_size=200`, { credentials: "include" });
  if (!res.ok) return { error: res.status };
  const body = await res.json();
  const rows = body.results ?? body.data ?? body;
  return Object.fromEntries(
    rows.filter((r) => String(r.code).endsWith(sfx) && String(r.code).startsWith("SC"))
        .map((r) => [r.code, r.applies_to]));
}, [T, SFX]);
const wrongScope = SCOPES.filter((scope) => {
  const code = `SC${scope.slice(0, 4).toUpperCase()}${SFX}`;
  return storedScopes[code] !== undefined && storedScopes[code] !== scope;
});
const absent = SCOPES.filter((scope) => storedScopes[`SC${scope.slice(0, 4).toUpperCase()}${SFX}`] === undefined);
ok("F3 · the scope READ BACK from the database is the one that was chosen",
   !storedScopes.error && wrongScope.length === 0 && absent.length === 0,
   storedScopes.error ? `list read failed: ${storedScopes.error}`
     : [wrongScope.map((s) => `${s} stored as ${storedScopes[`SC${s.slice(0, 4).toUpperCase()}${SFX}`]}`),
        absent.length ? `never reached the database: ${absent.join(", ")}` : ""]
       .flat().filter(Boolean).join(" ;; ") || "all seven stored as chosen");

// ══ G · THE EDIT DOOR — a new DATED VERSION, not an edit ══════════════════
await p.goto(`${BASE}/${T}/plans-rates/discounts`, { waitUntil: "networkidle" });
await p.waitForTimeout(1200);
// ⚠ SELECTORS LIE QUIETLY, AND THIS ROW IS THE PROOF. The PLANS tab opens a
// row through a `<button class="rating-link">`; the DISCOUNTS tab opens it
// through an `<a data-inlinelink>` to a real href. The same screen, two tabs,
// two mechanisms — a selector copied from the plan walk finds nothing here
// and reads as "no discount is openable". Assert by ROLE and by the code.
const seniorRow = p.locator("main table tbody tr").filter({ hasText: /SENIOR/ }).first();
const rowActions = await seniorRow.locator("td:last-child button").evaluateAll(
  (ns) => ns.map((n) => n.getAttribute("aria-label") || n.innerText.trim()));
note(`G · a discount row offers ${rowActions.length} action(s): ${rowActions.join(", ") || "none"}`);
await tap(seniorRow.locator("a[data-inlinelink]").first());
await p.waitForTimeout(2000);
const detailUrl = p.url();
ok("G · a live discount opens from the list",
   /\/plans-rates\/discounts\/[0-9a-f-]{36}/.test(detailUrl), detailUrl.split("/").pop());
const detailText = await stepText();
ok("G · the detail offers a way to change it", /edit|change|new version|correct/i.test(detailText));

const editClicksFrom = clicks;
await p.goto(`${detailUrl}/edit`, { waitUntil: "networkidle" });
await p.waitForTimeout(2200);
const e1 = await stepText();
ok("G · the edit door says it is an edit", /edit/i.test(e1), e1.split("\n").slice(0, 6).join(" | "));
// DEF-RAT-5791 — the whole defect, on the door it was found on.
await cont();
const editValue = await p.evaluate(() => document.getElementById("discount-value")?.value ?? "");
const editFloor = await p.evaluate(() => document.getElementById("discount-floor")?.value ?? "");
ok("5791 · the edit door's value reads at two decimals",
   !/\.\d{3,}/.test(editValue), `value=${JSON.stringify(editValue)}`);
ok("5791 · the edit door's bill floor reads at two decimals",
   !/\.\d{3,}/.test(editFloor), `floor=${JSON.stringify(editFloor)}`);
const editCaps = await p.evaluate(() =>
  ["discount-cap-per-bill", "discount-cap-per-year", "discount-cap-lifetime"]
    .map((i) => document.getElementById(i)?.value ?? ""));
ok("5791 · no money box on the edit door shows six places",
   !editCaps.some((v) => /\.\d{3,}/.test(v)), editCaps.join(" / "));
await cont(); await cont();
const e4 = await stepText();
// BR-RAT-037 — every version after the first states what changed.
ok("G · an edit demands a reason before it will continue",
   /reason|what changed/i.test(e4), e4.split("\n").find((l) => /reason/i.test(l)) || "absent");
// ⚠ CONTINUE IS NEVER DISABLED IN THIS FRAME — `WizardFrame` validates ON
// PRESS and renders a line at the button (DEF-178). Asserting `isDisabled()`
// tests a mechanism the product does not use and fails on a healthy screen.
const beforePress = await stepText();
await tap(btn(/^Continue$/));
await p.waitForTimeout(700);
const afterPress = await stepText();
const stayed = /STEP 4 OF 5/.test(afterPress);
const saidWhy = afterPress.replace(beforePress, "").trim();
ok("G · a blank reason does not advance the step", stayed);
ok("G · and the clerk is told why, at the button", stayed && saidWhy.length > 0,
   JSON.stringify(saidWhy.slice(0, 90)));
await p.fill("#discount-change-reason", "Walk: rate review 2026");
await p.waitForTimeout(400);
await cont();
const e5 = await stepText();
const editBudget = e5;
ok("G · the review of an edit says a NEW VERSION is what saves",
   /version/i.test(e5), e5.split("\n").filter((l) => /version/i.test(l)).join(" | ") || "no mention");
ok("5791 · the review reads the value at two decimals",
   !/\d\.\d{3,}/.test(e5), (e5.match(/\d+\.\d+/g) || []).join(" "));
ok("G · the phrase 'as typed' is gone from the review", !/as typed/i.test(e5));
note(`G · edit door to a reviewable new version: ${clicks - editClicksFrom} clicks`);
const commitLabel = await p.evaluate(() =>
  [...document.querySelectorAll("main button")].map((n) => n.innerText.trim())
    .find((s) => /save|create|version|commit/i.test(s)) || "");
note(`G · the commit button reads: ${JSON.stringify(commitLabel)}`);

// ══ G2 · COMMIT THE EDIT — and the rule that only shows up on the SECOND ══
// ⚠ A DISCOUNT CAN BE EDITED ONCE. `uq_discount_versions_one_draft` is a
// PARTIAL UNIQUE INDEX allowing one draft per discount — a deliberate rule,
// and the right one. The discount path has no handler for it, so the second
// new version arrives as HTTP 500 and the clerk reads "Something went wrong
// on our side." while the product is working exactly as designed. The TARIFF
// twin `uq_tariff_versions_one_draft` was given a human refusal (DEF-RAT-6447)
// and this one was not.
//
// ⚠ THE CHECK IS WRITTEN SO IT IS TRUE ON EITHER RUN. The first run of this
// walk against a fresh database SAVES; every run after it is refused, because
// the draft this one leaves behind is still there and nothing in the product
// can show it or discard it. So the assertion is not "it saves" — it is
// "whatever happens, the clerk is not shown a server crash".
await tap(btn(/^Save new version$/));
await p.waitForTimeout(3200);
const editLanded = p.url();
const editFailure = saved(editLanded) ? null : await failureText();
note(`G2 · saving the new version → ${saved(editLanded) ? "SAVED" : "refused"}${
  editFailure ? ": " + JSON.stringify(editFailure.split("|")[0].trim()) : ""}`);
ok("G2 · a refused new version is a sentence, not a server crash",
   editFailure === null || !/went wrong on our side/i.test(editFailure),
   editFailure ? "uq_discount_versions_one_draft reaching the clerk as SYS-INTERNAL" : "saved");
// ⚠ AND WHETHER IT SAVED OR NOT, THERE IS NOWHERE TO SEE THE VERSION. The
// Audit tab says so in its own words, which is honest and is still a clerk
// who has just drafted something they cannot find.
await p.goto(detailUrl, { waitUntil: "networkidle" });
await p.waitForTimeout(1800);
await tap(p.locator("main button,main a").filter({ hasText: /^Audit$/ }).first());
// ⚠ **WAIT FOR THE TABLE, NOT FOR A CLOCK.** The Audit tab fetches its own
// versions, so a fixed `waitForTimeout` reads the panel mid-flight: on
// 2026-09-19 that is exactly what happened — the row check below saw only the
// header's `V1` while the DRAFT row arrived a moment later, and the very next
// assertion (is there a Discard control?) found it. **A check that reads the
// screen at the wrong MOMENT reports the right screen wrongly**, which is law
// 7's *looking at the wrong thing* with no bug behind it.
await p.locator("main [data-discount-versions] tbody tr").first()
  .waitFor({ timeout: 15000 }).catch(() => {});
await p.waitForTimeout(600);
const auditText = await stepText();
ok("G2 · the version history a new version lands in is served",
   !/no endpoint serves those versions/i.test(auditText),
   auditText.split("\n").find((l) => /no endpoint serves/i.test(l))?.slice(0, 80) || "served");

// ══ G3 · THE SECOND EDIT — refused in words, and a way back out ═══════════
// ⚠ **`DEF-RAT-5817`. THE FIRST EDIT WAS NEVER THE PROBLEM.** A discount
// holds ONE draft (`uq_discount_versions_one_draft`, and the rule is right),
// so the SECOND *Save new version* used to arrive as a raw HTTP 500 and the
// edit door on that discount stayed shut for ever: nothing listed the draft
// and nothing could discard it.
//
// ⚠ **THE DRAFT IS MADE HERE RATHER THAN ASSUMED.** The PO cleared the one
// this walk left behind on the beta, so a run that assumed a blocking draft
// would test nothing. The block above has just created one; this is the
// SECOND attempt on the same discount.
ok("G3 · the blocking draft is LISTED, by version number and not by id",
   /\bV\d+\b/.test(auditText) && !/[0-9a-f]{8}-[0-9a-f]{4}/i.test(auditText),
   (auditText.match(/\bV\d+\b/g) || []).join(" ") || "no version row drawn");
const discardBtn = p.locator("main button").filter({ hasText: /^Discard draft$/ }).first();
ok("G3 · and there is a way to withdraw it", await discardBtn.count() > 0);

// Now the second edit, which is the reported symptom exactly.
await p.goto(detailUrl, { waitUntil: "networkidle" });
await p.waitForTimeout(1500);
const editAgain = p.locator("main button,main a").filter({ hasText: /^(Edit|Change|New version)/i }).first();
if (await editAgain.count()) {
  await tap(editAgain);
  await p.waitForTimeout(1800);
  await cont(); await cont(); await cont();
  const reasonBox = M("#discount-change-reason");
  if (await reasonBox.count()) await p.fill("#discount-change-reason", "Walk: second edit in a row");
  await cont();
  await tap(btn(/^Save new version$/));
  await p.waitForTimeout(3000);
  const second = saved(p.url()) ? null : await failureText();
  ok("G3 · the SECOND edit is refused with a sentence, never a 500",
     second !== null && !/went wrong on our side/i.test(second),
     second === null ? "it SAVED — two drafts, which the index forbids" : JSON.stringify(second.slice(0, 110)));
  ok("G3 · and the sentence names the way out",
     second !== null && /discard/i.test(second), JSON.stringify((second || "").slice(0, 110)));
} else {
  note("G3 · no edit door found on the detail — the second-edit case was not reached");
}

// And the draft can actually be thrown away, which is what makes the sentence
// actionable rather than a politer dead end (hard-won law 2's mirror).
await p.goto(`${detailUrl}?tab=audit`, { waitUntil: "networkidle" });
await p.waitForTimeout(1600);
const discard2 = p.locator("main button").filter({ hasText: /^Discard draft$/ }).first();
if (await discard2.count()) {
  await tap(discard2);
  await p.waitForTimeout(600);
  await tap(p.locator('[role="dialog"] button, body button').filter({ hasText: /^Discard draft$/ }).last());
  await p.waitForTimeout(2500);
  const afterDiscard = await stepText();
  ok("G3 · discarding the draft removes it from the history",
     !/Finish it or discard it/i.test(afterDiscard),
     afterDiscard.split("\n").find((l) => /discard/i.test(l))?.slice(0, 80) || "gone");
} else {
  note("G3 · no discard control on the Audit tab — the withdraw case was not reached");
}

// ⚠ **`DEF-RAT-5816` IS NOT RE-WALKED HERE — `F2a` ABOVE ALREADY OWNS IT**,
// and owns it better: it checks that the with-proof refusal is caught on
// STEP 3 where the choice is made, and that what the clerk reads is a
// sentence rather than a dotted message key, through a regex whose own first
// draft passed on the defect it was written for. A second walk of the same
// screen would add three minutes and no information.

// ══ H · THE TWO DEAD CONTROLS AT THE FOOT OF EVERY REVIEW ═════════════════
await p.goto(`${BASE}/${T}/plans-rates/discounts/new`, { waitUntil: "networkidle" });
await p.waitForTimeout(900);
await p.fill("#discount-code", `WGRD${SFX}`);
await p.fill("#discount-name", `Walk guard ${SFX}`);
await cont(); await cont(); await cont(); await cont();
const guarded = await p.evaluate(() =>
  [...document.querySelectorAll("main button")].filter((n) => n.disabled)
    .map((n) => [n.innerText.trim(), n.getAttribute("title") || n.getAttribute("aria-describedby") || ""])
    .filter(([s]) => /submit|activate/i.test(s)));
ok("H · a disabled lifecycle button carries its reason (BR-SHL-025)",
   guarded.length > 0 && guarded.every(([, why]) => why),
   JSON.stringify(guarded));

await b.close();
console.log(R.join("\n"));
console.log(`\nTOTAL CLICKS ACROSS THE WALK: ${clicks}`);
process.exit(R.some((l) => l.startsWith("FAIL")) ? 1 : 0);
