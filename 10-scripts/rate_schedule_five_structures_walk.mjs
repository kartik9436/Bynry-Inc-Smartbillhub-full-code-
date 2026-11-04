// ── THE FIVE RATE-SCHEDULE STRUCTURES, WALKED AS A CLERK ────────────────────
// PO's ask, 2026-09-19, verbatim: *"also run End to end Walk for Rate schedule
// - alos do all combinations/senarios - Flat, tiered, TOU, Demand, Seasional -
// youa re able to set for 1 Utility - you have multiple end ot end walk - also
// correction or new rate schedule - when you cahnge does is update the plans
// audit"*, and *"walk ahould check plasna dn rates work end to end - clark dont
// have any frictions to perform his job, overall user experience is good"*.
//
// **THIS IS NOT A PASS/FAIL GATE.** It answers one question — can a clerk get
// from an empty screen to a saved, activated rate schedule of each shape
// without getting stuck or having to guess — and it MEASURES the answer:
// every field filled, every control clicked and every step entered is counted,
// per scenario, and printed at the end beside what the screen said.
//
// ⚠ **IT DOES NOT PRICE A BILL, DELIBERATELY.** The PO ruled the priced-bill
// ending out of scope on 2026-09-19 (*"this is not required"*), so nothing
// here calls a bill run or asserts a money figure. Where a SCREEN shows a
// figure this reads it back and says whether it is the figure that was typed.
//
// ⚠ **IT REFUSES A STALE BUILD, AND THAT GUARD IS THE POINT** (copied from
// `plan_wizard_seven_walkthrough.mjs`, whose own header records why). On
// 2026-09-19 a walk was run against a `dist/` built 26 hours earlier and three
// landed fixes read as ABSENT; the walk was one step from reporting that other
// lanes had not done their work. Nothing in the page says how old it is, and
// `tsc`, the suites and every gate are green either way, because none of them
// look at `dist/`.
//
// ⚠ **IT NOW CARRIES VERDICTS AS WELL AS MEASUREMENTS (2026-09-19, the fix
// run).** The eight findings below were all recorded as `note`/`DEAD END`
// lines, which a reader has to know to look for. Each one that has been FIXED
// now also has a named verdict that says PASS or FAIL in one line at the end,
// so a regression is a word in a summary rather than an absent sentence in a
// 300-line log. `verdict()` is the only thing that prints there; the friction
// measurement is unchanged and is still the point of the walk.
//
// ⚠ **A RATES VERDICT COMPARES THE WHOLE COMPOSED BLOCK, NEVER *a price
// appears*.** `DEF-RAT-5826`'s weak fix passes *a price appears* by showing one
// season's ladder twice, or the right figure against the wrong label. So the
// time-of-use scenario files FOUR windows at FOUR different prices across TWO
// seasons and the verdict is the exact string the review draws.
//
// WHAT THIS WALK FOUND on 2026-09-19, so a later run knows what is expected
// to be red and what would be new:
//   DEF-RAT-5826  Review & activate shows NO prices for time-of-use, demand,
//                 seasonal or capacity — it draws an empty `Rates` row
//   DEF-RAT-5827  a correction leaves no trace on the schedule's own Audit tab
//                 and the corrected-away row is labelled `Scheduled`
//   DEF-RAT-5828  the review says a schedule minimum is never billed; it is
//   DEF-RAT-5829  after a failed activation there is no Continue and no Back
//   DEF-RAT-5830  a missing season price refuses with an unplaced
//                 "This is required."
//   DEF-RAT-5831  a future-dated schedule says Draft and names a version as
//                 IN FORCE in the same header
//   DEF-RAT-5832  the demand editor explains a ratchet it offers no control for
//   DEF-RAT-5833  editing an in-force schedule pre-fills the OUTGOING
//                 version's end date into the new one
//
// ⚠ **SELECTORS: a plan row opens through `button.rating-link`, not an
// anchor.** A link selector finds nothing here and reads as "no plan is
// openable" — which is a confident, specific, wrong finding about somebody
// else's work.
//
//   RSW_BASE     default http://127.0.0.1:8702
//   RSW_TENANT   default brazosbend
//   RSW_EMAIL    default dana@brazosbendutilities.com
//   RSW_PASSWORD default S3cure!passw0rd
//   RSW_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser in this container, so the path is passed explicitly — see
//      CLAUDE.md's environment note; never run `playwright install` here.)
//   RSW_KEEP=1   leave the schedules this walk creates behind (default: they
//                are left behind anyway — nothing here deletes, because a
//                walk that cleans up cannot be inspected afterwards)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync } from "node:fs";

const BASE = process.env.RSW_BASE || "http://127.0.0.1:8702";
const T = process.env.RSW_TENANT || "brazosbend";
const EMAIL = process.env.RSW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.RSW_PASSWORD || "S3cure!passw0rd";
const CHROME =
  process.env.RSW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

// ── the staleness refusal ──────────────────────────────────────────────────
const built = statSync("07-frontend/dist/index.html").mtime;
const newestSrc = new Date(
  execSync("git log -1 --format=%cI -- 07-frontend/src").toString().trim(),
);
if (built < newestSrc) {
  console.error(
    `REFUSED: dist/ was built ${built.toISOString()} but 07-frontend/src has a\n` +
      `commit at ${newestSrc.toISOString()}. Run \`npx vite build\` first.\n` +
      `A walk against a stale bundle reports absent features that are present.`,
  );
  process.exit(2);
}

// ── the measurement ────────────────────────────────────────────────────────
// Friction is the deliverable, so every act a clerk performs is counted at the
// point it happens rather than estimated afterwards. `guess` records a place
// the walk had to decide something the screen did not say.
const SCENARIOS = [];
let cur = null;
// RSW_ONLY=9 runs just the scenarios whose name starts with that text, so a
// single finding can be re-checked without a twelve-minute walk.
const ONLY = process.env.RSW_ONLY || "";
const skipped = (name) => ONLY !== "" && !name.startsWith(ONLY);
const scenario = (name) => {
  cur = { name, acts: 0, steps: 0, guesses: [], deadEnds: [], notes: [], result: "" };
  SCENARIOS.push(cur);
  return cur;
};
const act = () => { if (cur) cur.acts += 1; };
// ── THE VERDICTS ───────────────────────────────────────────────────────────
// A measurement says what the screen did; a verdict says whether that is what
// it is supposed to do. They are kept apart on purpose: the friction figures
// are the PO's ask and must not turn into a pass/fail gate, while a defect
// that has been fixed needs one line somebody can read without knowing which
// sentence used to be missing.
const VERDICTS = [];
const verdict = (id, what, ok, saw) => {
  VERDICTS.push({ id, what, ok, saw });
  console.log(`   ${ok ? "PASS" : "FAIL"} · ${id} — ${what}${ok ? "" : `\n        saw: ${saw}`}`);
};
// What the review's Rates block reads, with whitespace flattened, so a verdict
// compares text rather than layout.
const flat = (s) => s.replace(/\s+/g, " ").trim();
const guess = (s) => { if (cur) cur.guesses.push(s); console.log(`   GUESS · ${s}`); };
const dead = (s) => { if (cur) cur.deadEnds.push(s); console.log(`   DEAD END · ${s}`); };
const note = (s) => { if (cur) cur.notes.push(s); console.log(`   note · ${s}`); };

class SkipScenario extends Error {}
const stamp = Date.now().toString().slice(-6);
// ⚠ **THE EFFECTIVE DATE IS TODAY, AND THAT IS NOT A DETAIL.** A schedule whose
// only version starts in the FUTURE has nothing in force, so the product calls
// it a draft and the correction verb has no door — `mayCorrect` is
// `activated && !showingParkedDraft`. The first run of this walk dated every
// schedule 2027 and then reported that the correction verb was missing, which
// was the walk's own choice and not the product's behaviour. Scenario 8 walks
// the future-dated case deliberately, where it belongs.
const TODAY = process.env.RSW_TODAY || new Date().toISOString().slice(0, 10);
// The flat schedule this run creates, reused by scenario 6 for the two verbs.
let FLAT_URL = null;
// Set when the seasonal scenario has already committed through the failure
// card, so the shared `finish` is not walked over a wizard that has gone.
let SEASONAL_DONE = false;
// The reason typed on the correction, so the walk can look for it afterwards.
let CORRECTION_REASON = null;

const b = await chromium.launch({ executablePath: CHROME });
const p = await b.newPage();
const pageErrors = [];
p.on("pageerror", (e) => pageErrors.push(e.message));

// Counted wrappers. Everything the walk does to the page goes through one of
// these, so the click count in the report is measured and not remembered.
const fill = async (sel, value) => { await p.fill(sel, value); act(); };
const pick = async (sel, value) => { await p.selectOption(sel, value); act(); };
const click = async (sel) => { await p.click(sel); act(); };
const clickText = async (text, opts = {}) => {
  const loc = p.locator(opts.scope || "main").locator("button").filter({ hasText: text });
  await loc.first().click();
  act();
};
const mainText = async () => await p.evaluate(() => document.querySelector("main")?.innerText || document.body.innerText);
const has = async (re) => re.test(await mainText());

// ⚠ **A DISABLED OR ABSENT `Continue` IS A FINDING, NOT A CRASH.** The rail
// steps are disabled until they are reached, and a `page.click` on a disabled
// button waits thirty seconds and then throws — which ends the scenario and
// prints a Playwright stack where a sentence about the product belongs.
const nextStep = async () => {
  const c = p.locator("main button").filter({ hasText: /^Continue$/ });
  if ((await c.count()) === 0) {
    // ⚠ **NAME THE BUTTONS THAT ARE THERE, NOT THE FIRST 160 CHARACTERS OF
    // PROSE.** The old message printed the page-head copy, which is the same on
    // every step and says nothing about why the footer is missing — a reader
    // could not tell a still-loading wizard from a failure card from a genuine
    // dead end. The footer's own labels tell all three apart at a glance.
    const buttons = await p.evaluate(() =>
      Array.from(document.querySelectorAll("main button"))
        .map((e) => `${(e.innerText || "").replace(/\s+/g, " ").trim()}${e.disabled ? " [disabled]" : ""}`)
        .filter(Boolean),
    );
    dead(`there is no Continue on this step; the buttons on it are ${JSON.stringify(buttons)}`);
    return false;
  }
  if (await c.first().isDisabled()) {
    dead("Continue is disabled and the screen does not say why");
    return false;
  }
  await c.first().click();
  act();
  if (cur) cur.steps += 1;
  await p.waitForTimeout(800);
  return true;
};

// ── sign in ────────────────────────────────────────────────────────────────
await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);
console.log(`signed in as ${EMAIL} on ${T}`);

// ── the shared opening: steps 1 and 2 ──────────────────────────────────────
// Every structure starts the same way, so this is written once and the count
// it adds is identical for all five — which is what makes the totals
// comparable.
async function openWizardTo3(name, service, uom) {
  await p.goto(`${BASE}/${T}/plans-rates/rates/new`, { waitUntil: "networkidle" });
  // ⚠ WAIT FOR THE FIELD, NOT FOR A TIMEOUT. A fixed pause passed four times
  // and timed out on the fifth run of the same page, which reads as "the
  // wizard is broken" when it is the walk that was impatient.
  try {
    await p.waitForSelector("#rate-name", { timeout: 30000 });
  } catch {
    dead(`the new-schedule wizard did not draw its first field; the page said: ${(await mainText()).slice(0, 200)}`);
    throw new Error("wizard did not open");
  }
  await p.waitForTimeout(600);
  if (cur) cur.steps += 1; // step 1 entered
  await fill("#rate-name", name);
  await pick("#rate-service", service);
  await p.waitForTimeout(400);
  await pick("#rate-uom", uom);
  await nextStep(); // -> step 2 Base rates
  await nextStep(); // -> step 3 Pricing formula
}

// Steps 4 and 5, shared. `effectiveFrom` empty means "leave it a draft".
//
// ⚠ **THE COMMIT BUTTON IS MATCHED BY ITS EXACT WORDS, NOT BY `/Save/`.** The
// wizard's HEADER carries `Save draft & exit`, which is INSIDE `main` and
// matches a loose selector first — so a loose match parks a draft and the walk
// then reports that nothing was created. That is a selector lying quietly, and
// it cost this walk one whole run.
const COMMIT = /^(Create rate schedule|Create new version|Correct this version)/;
// ⚠ **`atEffective` EXISTS BECAUSE SCENARIO 9 ENTERS FROM STEP 4 AND THIS
// FUNCTION ASSUMES STEP 3.** Without it the first `nextStep` moves 4→5 and the
// second finds no `Continue` on the review step — which printed a DEAD END
// reading *"there is no Continue on this step"* on a walk that then committed
// perfectly. A dead end that is not one is worse than none: it is a true red
// losing its meaning, which is the failure CLAUDE.md's law 7 habit 1 is about.
async function finish({ effectiveFrom, reason, expectRates, atEffective }) {
  if (!atEffective) await nextStep(); // -> step 4
  if (effectiveFrom) await fill("#rate-effective-from", effectiveFrom);
  if (reason) await fill("#rate-change-reason", reason);
  await nextStep(); // -> step 5 review
  const review = await mainText();
  // ⚠ **DOES `Review & activate` SHOW THE PRICES THAT WERE TYPED?** Its own
  // hint is *"Check what will be stored"*, so this is the one question the
  // step exists to answer, and it is asked of every structure rather than
  // assumed from the one that passes.
  const ratesBlock = (review.match(/Rates\n[\s\S]*?(?=\nNothing in force|\nThe change against)/) || [""])[0];
  note(`the review's Rates block reads: ${flat(ratesBlock).slice(0, 220)}`);
  // ⚠ **THE WHOLE COMPOSED BLOCK, NOT *a price appears*** — see the header.
  if (expectRates) {
    const saw = flat(ratesBlock);
    verdict(
      "DEF-RAT-5826",
      `the review prices this structure: ${expectRates}`,
      saw.includes(expectRates),
      saw.slice(0, 300),
    );
  }
  const commit = p.locator("main button").filter({ hasText: COMMIT });
  if (!(await commit.count())) {
    dead("step 5 offers no commit button");
    return { review, commitLabel: null, url: p.url(), after: await mainText() };
  }
  const label = (await commit.first().innerText()).trim();
  await commit.first().click();
  act();
  await p.waitForTimeout(3000);
  return { review, commitLabel: label, url: p.url(), after: await mainText() };
}

// What the screen said when a commit did not land, in the clerk's own view.
//
// ⚠ **IT USED TO GREP THE WHOLE PAGE FOR A WORD LIKE `error`, AND THE EDIT
// WIZARD'S OWN INTENT PICKER IS LABELLED `Fix an error`.** So a refused filing
// reported *"the schedule change itself did not land: Fix an error"* — a
// sentence that names a control rather than a refusal, on the one line a reader
// goes to for the reason. `RefusalStrip` and `FailedWithRetry` both carry
// `data-refusal`, so the real message can be asked for by name; the word search
// is kept only as the fallback for a screen that renders neither.
const refusalOnScreen = async () => {
  const strip = await p.evaluate(() =>
    Array.from(document.querySelectorAll("main [data-refusal]"))
      .map((e) => (e.innerText || "").replace(/\s+/g, " ").trim())
      .filter(Boolean)
      .join(" · "),
  );
  return strip;
};
const refusalText = (body) =>
  (body.match(/[^\n]*(could not|cannot|must|refus|check|problem|error|required)[^\n]*/i) || [""])[0]
    .slice(0, 220);

// DID THE SCHEDULE GET MADE, AND WHERE WAS THE CLERK PUT?
//
// ⚠ **THESE ARE TWO QUESTIONS AND THE FIRST RUN OF THIS WALK CONFLATED THEM.**
// Committing a new schedule returns the clerk to the rate-schedules LIST, not
// to the schedule they just built. A check that only asked "is the URL a
// schedule" reported five creations as failures. So: the schedule is looked
// for BY NAME on the list, and where the clerk was put is reported separately
// as friction rather than as a break.
async function landed(out, s, name) {
  const onDetail = /rates\/[0-9a-f-]{36}/.test(out.url);
  let madeUrl = onDetail ? out.url : null;
  let made = onDetail;
  if (!onDetail) {
    // ⚠ **SEARCH FOR IT — READING PAGE ONE IS A CHECK THAT REPORTS *NOT
    // CREATED* ABOUT A ROW THAT EXISTS.** The list is server-paginated
    // (`NFR-3`), so on any tenant with more schedules than one page a
    // just-created row is simply not on the page this walk was reading, and
    // the verdict came back `NOT created — commit "Create rate schedule ✓"
    // left the clerk at …/rates`. That is a confident, specific, wrong
    // finding, and it gets MORE likely as the tenant grows, which is the worst
    // possible direction for a check to drift. `q` is the list's own search
    // parameter (`serializeTableParams`), so this is the clerk's own route.
    const q = new URLSearchParams({ q: name }).toString();
    await p.goto(`${BASE}/${T}/plans-rates/rates?${q}`, { waitUntil: "networkidle" });
    await p.waitForTimeout(1800);
    const row = p.locator("table tbody tr").filter({ hasText: name });
    made = (await row.count()) > 0;
    if (made) {
      const status = (await row.first().innerText()).replace(/\s+/g, " ").trim();
      note(`the list row reads: ${status.slice(0, 190)}`);
      await row.first().locator("button").first().click();
      await p.waitForTimeout(2000);
      if (/rates\/[0-9a-f-]{36}/.test(p.url())) madeUrl = p.url();
    }
  }
  if (!made) {
    s.result = `NOT created — commit "${out.commitLabel}" left the clerk at ${out.url}`;
    dead(s.result);
    note(`what the screen said: ${refusalText(out.after)}`);
  } else if (onDetail) {
    s.result = `created — commit read "${out.commitLabel}" and opened the schedule`;
  } else {
    s.result = `created — commit read "${out.commitLabel}", clerk returned to the LIST`;
    note("after committing, the clerk is on the list and must find the schedule again to see it");
  }
  return madeUrl;
}

// ═══════════════════════════════════════════════════════════════════════════
// 1 · FLAT
// ═══════════════════════════════════════════════════════════════════════════
try {
  scenario("1 · Flat");
  if (skipped("1 · Flat")) throw new SkipScenario();
  console.log("\n=== 1 · FLAT ===");
  await openWizardTo3(`WALK ${stamp} Flat electric`, "electric", "kWh");
  await pick("#rate-model", "flat");
  await p.waitForTimeout(400);
  await fill("#flat-unit-price", "0.1150");
  const out = await finish({
    effectiveFrom: TODAY,
    reason: "Walk: flat 0.1150/kWh",
    // THE CONTROL. If this moves, the verdicts below are measuring the wrong
    // block and nothing under them means anything.
    expectRates: "0 kWh and above — 0.1150",
  });
  FLAT_URL = await landed(out, cur, `WALK ${stamp} Flat electric`);
  note(/0\.1150|0\.115/.test(out.after)
    ? "the schedule screen shows the 0.1150 that was typed"
    : "the schedule screen does NOT echo 0.1150");
  console.log(`   ${cur.result} · ${cur.acts} acts, ${cur.steps} steps`);
} catch (e) {
  if (e instanceof SkipScenario) { SCENARIOS.pop(); cur = null; }
  else
  // ⚠ ONE SCENARIO MUST NOT KILL THE WALK. A timeout in the fourth
  // structure used to end the run before the fifth, the two verbs and the
  // plan audit were ever reached — so the report was silently PARTIAL.
  dead(`the walk could not finish this scenario: ${e.message.split("\n")[0]}`);
}

// ═══════════════════════════════════════════════════════════════════════════
// 2 · TIERED — and the straddle the PO reported in the beta
// ═══════════════════════════════════════════════════════════════════════════
try {
  scenario("2 · Tiered");
  if (skipped("2 · Tiered")) throw new SkipScenario();
  console.log("\n=== 2 · TIERED ===");
  await openWizardTo3(`WALK ${stamp} Tiered water`, "water", "kgal");
  await pick("#rate-model", "tiered");
  await p.waitForTimeout(400);
  // Three blocks: 0–10, 10–30, 30+. BR-RAT-032's boundaries are HALF-OPEN, so
  // tier 2 starts at the number tier 1 stops at. DEF-RAT-5717 is the defect
  // where the message did not say which number; this checks it now does.
  await fill("#tier-from-0", "0");
  await fill("#tier-to-0", "10");
  await fill("#tier-price-0", "3.2000");
  await clickText(/Add tier/);
  await p.waitForTimeout(400);
  // the wrong number first, on purpose — this is the PO's own beta report
  await fill("#tier-from-1", "11");
  await fill("#tier-to-1", "30");
  await fill("#tier-price-1", "4.8000");
  await p.waitForTimeout(600);
  const gapMsg = await mainText();
  // DEF-RAT-5717's cure is that the sentence NAMES the number: the catalogue
  // reads "Start tier {tier} at {expected}. Tier {previous} ends there." A
  // message with the placeholder unfilled is the defect, so the check is for
  // the digits and not for the sentence.
  const gapLine = (gapMsg.match(/[^\n]*Start tier[^\n]*/i) || [""])[0];
  note(gapLine
    ? `the gap message reads: "${gapLine.trim()}"`
    : "typing a gapped tier produced NO message on this step");
  if (gapLine && !/\b10\b/.test(gapLine)) {
    dead("the gap message does not name the number to type");
  }
  await fill("#tier-from-1", "10");
  await p.waitForTimeout(400);
  await clickText(/Add tier/);
  await p.waitForTimeout(400);
  await fill("#tier-from-2", "30");
  await fill("#tier-to-2", "");
  await fill("#tier-price-2", "7.2000");
  const out = await finish({
    effectiveFrom: TODAY,
    reason: "Walk: three blocks 3.20/4.80/7.20",
    expectRates: "0–10 kgal — 3.2000 10–30 kgal — 4.8000 30 kgal and above — 7.2000",
  });
  await landed(out, cur, `WALK ${stamp} Tiered water`);
  note(/3 blocks|3\.2000|3\.20/.test(out.after) ? "the detail screen shows the three blocks" : "the detail screen does not show the blocks");
  console.log(`   ${cur.result} · ${cur.acts} acts, ${cur.steps} steps`);
} catch (e) {
  if (e instanceof SkipScenario) { SCENARIOS.pop(); cur = null; }
  else
  // ⚠ ONE SCENARIO MUST NOT KILL THE WALK. A timeout in the fourth
  // structure used to end the run before the fifth, the two verbs and the
  // plan audit were ever reached — so the report was silently PARTIAL.
  dead(`the walk could not finish this scenario: ${e.message.split("\n")[0]}`);
}

// ═══════════════════════════════════════════════════════════════════════════
// 3 · TIME-OF-USE — two seasons, a window in each
// ═══════════════════════════════════════════════════════════════════════════
try {
  scenario("3 · Time-of-use");
  if (skipped("3 · Time-of-use")) throw new SkipScenario();
  console.log("\n=== 3 · TIME-OF-USE ===");
  await openWizardTo3(`WALK ${stamp} TOU electric`, "electric", "kWh");
  await pick("#rate-model", "time_of_use");
  await p.waitForTimeout(500);
  // BR-RAT-1017: a season OWNS its windows, and a window is added from inside
  // the season that owns it. Two seasons must cover the year between them.
  const seasons = [
    { i: 0, label: "Summer", sm: "6", sd: "1", em: "9", ed: "30" },
    { i: 1, label: "Winter", sm: "10", sd: "1", em: "5", ed: "31" },
  ];
  for (const s of seasons) {
    await clickText(/Add season/);
    await p.waitForTimeout(500);
    await fill(`#season-label-${s.i}`, s.label);
    await pick(`#season-start-${s.i}-month`, s.sm);
    await pick(`#season-start-${s.i}-day`, s.sd);
    await pick(`#season-end-${s.i}-month`, s.em);
    await pick(`#season-end-${s.i}-day`, s.ed);
    await p.waitForTimeout(300);
  }
  // Two weekday windows per season, covering 00:00–24:00. The window controls
  // are numbered across ALL seasons, so the indices run 0..3.
  const addWindow = async (seasonIdx) => {
    const btns = p.locator("main button").filter({ hasText: /Add window/ });
    await btns.nth(seasonIdx).click();
    act();
    await p.waitForTimeout(500);
  };
  const windows = [
    { s: 0, label: "Off-peak", start: "00:00", end: "16:00", reg: "tou_off", price: "0.0900" },
    { s: 0, label: "On-peak", start: "16:00", end: "00:00", reg: "tou_on", price: "0.2400" },
    { s: 1, label: "Off-peak", start: "00:00", end: "16:00", reg: "tou_off", price: "0.0800" },
    { s: 1, label: "On-peak", start: "16:00", end: "00:00", reg: "tou_on", price: "0.1900" },
  ];
  let wi = 0;
  for (const w of windows) {
    await addWindow(w.s);
    // find the newest window row by its index in the DOM
    const idx = (await p.locator("main input[id^='window-label-']").count()) - 1;
    await fill(`#window-label-${idx}`, w.label);
    await fill(`#window-start-${idx}`, w.start);
    await fill(`#window-end-${idx}`, w.end);
    await pick(`#window-register-${idx}`, w.reg);
    await fill(`#window-price-${idx}`, w.price);
    wi += 1;
  }
  // ⚠ FOUR DIFFERENT PRICES ACROSS TWO SEASONS, so a review that showed one
  // season's ladder twice — or a price against the wrong window — cannot pass.
  const out = await finish({
    effectiveFrom: TODAY,
    reason: "Walk: two seasons, peak and off-peak",
    expectRates:
      "Summer · Off-peak, 00:00 to 16:00 — 0.0900 " +
      "Summer · On-peak, 16:00 to 00:00 — 0.2400 " +
      "Winter · Off-peak, 00:00 to 16:00 — 0.0800 " +
      "Winter · On-peak, 16:00 to 00:00 — 0.1900",
  });
  await landed(out, cur, `WALK ${stamp} TOU electric`);
  console.log(`   ${cur.result} · ${cur.acts} acts, ${cur.steps} steps`);
} catch (e) {
  if (e instanceof SkipScenario) { SCENARIOS.pop(); cur = null; }
  else
  // ⚠ ONE SCENARIO MUST NOT KILL THE WALK. A timeout in the fourth
  // structure used to end the run before the fifth, the two verbs and the
  // plan audit were ever reached — so the report was silently PARTIAL.
  dead(`the walk could not finish this scenario: ${e.message.split("\n")[0]}`);
}

// ═══════════════════════════════════════════════════════════════════════════
// 4 · DEMAND
// ═══════════════════════════════════════════════════════════════════════════
try {
  scenario("4 · Demand");
  if (skipped("4 · Demand")) throw new SkipScenario();
  console.log("\n=== 4 · DEMAND ===");
  await openWizardTo3(`WALK ${stamp} Demand electric`, "electric", "kW");
  await pick("#rate-model", "demand");
  await p.waitForTimeout(400);
  await fill("#demand-energy", "0.0850");
  await fill("#demand-demand", "14.5000");
  await fill("#demand-peak-window", "15-min monthly");
  // The screen's own note talks about a RATCHET that "a bill run refuses when
  // ticked" — there is no ratchet control on this editor to tick. Recorded,
  // not worked around.
  const editor = await mainText();
  // `DEF-RAT-5832` — the panel either offers the ratchet or stops explaining
  // it. Both halves are checked, because removing the paragraph and leaving the
  // field unreachable would satisfy a looser test while a version stored with
  // the ratchet ON still could not be untangled.
  const ratchetCtl = await p.locator("main input[id*='ratchet'], main select[id*='ratchet']").count();
  verdict(
    "DEF-RAT-5832",
    "the demand editor offers a ratchet control",
    ratchetCtl > 0,
    `controls matching 'ratchet': ${ratchetCtl}; panel mentions it: ${/ratchet/i.test(editor)}`,
  );
  if (ratchetCtl > 0) {
    // ⚠ **`CheckboxField` RENDERS `input.peer.sr-only`, SO A CLICK ON THE ID
    // WAITS THIRTY SECONDS AND THEN THROWS** — the same trap as the
    // `SegmentedField` radio this walk's header already records, one component
    // over. The LABEL is what a clerk clicks, so that is what this clicks.
    const tick = p.locator('main label[for="demand-ratchet"]');
    await tick.first().click();
    act();
    await p.waitForTimeout(500);
    const pct = await p.locator("#demand-ratchet-pct").count();
    verdict(
      "DEF-RAT-5832",
      "ticking the ratchet reveals its percentage box",
      pct > 0,
      `#demand-ratchet-pct count: ${pct}`,
    );
    // Untick it again: a ticked ratchet makes a bill run REFUSE the schedule
    // (`rating.demand.blockedBody`), and this scenario is about the review
    // page, not about leaving an unbillable rate behind on the tenant.
    await tick.first().click();
    act();
    await p.waitForTimeout(500);
  }
  const out = await finish({
    effectiveFrom: TODAY,
    reason: "Walk: energy 0.0850 + demand 14.50",
    expectRates: "Energy price per kWh — 0.0850 Demand price per kW — 14.5000",
  });
  await landed(out, cur, `WALK ${stamp} Demand electric`);
  console.log(`   ${cur.result} · ${cur.acts} acts, ${cur.steps} steps`);
} catch (e) {
  if (e instanceof SkipScenario) { SCENARIOS.pop(); cur = null; }
  else
  // ⚠ ONE SCENARIO MUST NOT KILL THE WALK. A timeout in the fourth
  // structure used to end the run before the fifth, the two verbs and the
  // plan audit were ever reached — so the report was silently PARTIAL.
  dead(`the walk could not finish this scenario: ${e.message.split("\n")[0]}`);
}

// ═══════════════════════════════════════════════════════════════════════════
// 5 · SEASONAL
// ═══════════════════════════════════════════════════════════════════════════
try {
  scenario("5 · Seasonal");
  if (skipped("5 · Seasonal")) throw new SkipScenario();
  console.log("\n=== 5 · SEASONAL ===");
  await openWizardTo3(`WALK ${stamp} Seasonal water`, "water", "kgal");
  await pick("#rate-model", "seasonal");
  await p.waitForTimeout(500);
  const warned = await has(/cannot be billed yet|will refuse/i);
  note(warned
    ? "the screen says up front that a seasonal schedule cannot be billed yet"
    : "no warning that seasonal cannot be billed");
  const seasons = [
    { i: 0, label: "Summer", sm: "6", sd: "1", em: "9", ed: "30" },
    { i: 1, label: "Winter", sm: "10", sd: "1", em: "5", ed: "31" },
  ];
  for (const s of seasons) {
    await clickText(/Add season/);
    await p.waitForTimeout(500);
    await fill(`#season-label-${s.i}`, s.label);
    await pick(`#season-start-${s.i}-month`, s.sm);
    await pick(`#season-start-${s.i}-day`, s.sd);
    await pick(`#season-end-${s.i}-month`, s.em);
    await pick(`#season-end-${s.i}-day`, s.ed);
    await p.waitForTimeout(300);
  }
  // WHERE DOES A SEASONAL PRICE GET TYPED? That is the question this scenario
  // exists to answer, and the answer is recorded rather than assumed.
  const priceInputs = await p.evaluate(() =>
    Array.from(document.querySelectorAll("main input")).map((e) => e.id).filter((i) => /price|rate/i.test(i)),
  );
  note(`price-shaped inputs on the seasonal editor: ${JSON.stringify(priceInputs)}`);
  const seasonPrices = priceInputs.filter((i) => /^season-price-/.test(i));
  if (seasonPrices.length === 0) {
    dead("a seasonal schedule offers nowhere to type a seasonal price");
  } else {
    // ⚠ THE PRICE BOX IS NOT MARKED REQUIRED ON THE PANEL, so the walk first
    // tries to commit WITHOUT it — which is what a clerk does who reads the
    // labels. What comes back is recorded before the prices are filled in.
    await nextStep(); // step 4
    await fill("#rate-effective-from", TODAY);
    await nextStep(); // step 5
    const tryCommit = p.locator("main button").filter({ hasText: COMMIT });
    if (await tryCommit.count()) {
      await tryCommit.first().click();
      act();
      await p.waitForTimeout(2500);
      const after = await mainText();
      const refusal = refusalText(after);
      const namesField = /season|price|rate|summer|winter/i.test(refusal);
      note(`committing with no season price says: "${refusal.trim()}"`);
      if (refusal && !namesField) {
        // ⚠ **THIS IS THE PAGE-LEVEL SENTENCE, NOT THE FIELD-LEVEL ONE, AND
        // AFTER `DEF-RAT-5830` THE TWO ANSWER DIFFERENTLY.** The failure card
        // renders the server's message on its own, with no field beside it;
        // whether the message REACHED the box it is about is asked below,
        // through that box's `aria-describedby`, which is what a clerk's eye
        // and a screen reader both follow. A dead end here would now read as
        // *the clerk is not told which field* when they are.
        note(`the page-level sentence alone does not name the field: "${refusal.trim()}" — the box is checked below`);
      }
      const stepNow = await p.evaluate(() => {
        const on = document.querySelector("main [aria-current=step], main .is-current");
        return on ? on.innerText.replace(/\s+/g, " ").trim() : "(cannot tell)";
      });
      note(`after that refusal the wizard is showing: ${stepNow}`);
      // Back to step 3 to fill the prices the clerk now knows are needed.
      // The rail is the obvious route, so the walk COUNTS how many acts it
      // takes to get back to the box that was missing.
      const rail = p.locator("main button").filter({ hasText: /Pricing formula/ });
      if (await rail.count()) { await rail.first().click(); act(); await p.waitForTimeout(1500); }
      let backs = 0;
      while ((await p.locator("#season-price-0").count()) === 0 && backs < 4) {
        const back = p.locator("main button").filter({ hasText: /^Back$/ });
        if (!(await back.count())) break;
        await back.first().click(); act(); backs += 1;
        await p.waitForTimeout(1000);
      }
      note(`getting back to the box that was missing took ${1 + backs} act(s)`);
      if ((await p.locator("#season-price-0").count()) === 0) {
        dead("after the refusal there was no way back to the season price box");
      }
      // ── `DEF-RAT-5830` · IS THE REFUSAL ATTACHED TO THE BOX IT IS ABOUT? ──
      // Not *is the sentence somewhere on the page* — the defect was that it
      // WAS on the page and belonged to nothing. The box's own
      // `aria-describedby` is what a clerk's eye and a screen reader both
      // follow, so that is what is read.
      if (await p.locator("#season-price-0").count()) {
        const bound = await p.evaluate(() => {
          const box = document.querySelector("#season-price-0");
          if (!box) return { required: null, message: "(no box)" };
          const ids = (box.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
          return {
            required: box.getAttribute("aria-required"),
            message: ids
              .map((id) => document.getElementById(id)?.textContent || "")
              .join(" ")
              .replace(/\s+/g, " ")
              .trim(),
          };
        });
        verdict(
          "DEF-RAT-5830",
          "the missing-price refusal is attached to the season price box",
          /required/i.test(bound.message),
          `aria-describedby text: "${bound.message}"`,
        );
        verdict(
          "DEF-RAT-5830",
          "the season price box carries the required mark",
          bound.required === "true",
          `aria-required: ${bound.required}`,
        );
      }
      // ⚠ **AFTER A FAILED ACTIVATION THERE IS NO `Continue` AND NO `Back` ON
      // ANY STEP.** The footer is replaced by a failure card — `Retry ·
      // Download error report · Cancel` — and the rail greys out every step
      // ahead of the one being shown. So the ONLY way forward after fixing the
      // field is a button labelled `Retry`, which reads as *do the same thing
      // again* rather than *submit what I have just corrected*. Recorded here
      // because it is the whole recovery path for any server refusal on this
      // wizard, not a seasonal quirk.
      const footer = await p.evaluate(() =>
        Array.from(document.querySelectorAll("main button"))
          .map((e) => `${e.innerText.replace(/\s+/g, " ").trim()}${e.disabled ? " [disabled]" : ""}`)
          .filter((x) => x && !/^\d /.test(x)),
      );
      note(`the controls a clerk has after the refusal: ${JSON.stringify(footer)}`);
      const hasContinue = footer.some((x) => /^Continue/.test(x));
      const hasRetry = footer.some((x) => /^Retry/.test(x));
      if (!hasContinue && hasRetry) {
        dead("after a failed activation the only way forward is a button labelled Retry — there is no Continue on any step");
      }
      const railAhead = await p.evaluate(() =>
        Array.from(document.querySelectorAll("main button"))
          .filter((e) => /^\d /.test(e.innerText.replace(/\s+/g, " ").trim()))
          .map((e) => `${e.innerText.replace(/\s+/g, " ").trim()}${e.disabled ? " [disabled]" : ""}`),
      );
      note(`the rail after the refusal: ${JSON.stringify(railAhead)}`);
    }
    for (let i = 0; i < seasonPrices.length; i++) {
      if (await p.locator(`#${seasonPrices[i]}`).count()) {
        await fill(`#${seasonPrices[i]}`, i === 0 ? "6.5000" : "4.2000");
      }
    }
    // Does the banner clear when the missing value is supplied?
    const stillSaysRequired = /This is required\./.test(await mainText());
    note(stillSaysRequired
      ? "after typing the missing prices the banner still reads 'This is required.'"
      : "the banner clears once the missing prices are typed");
    // ⚠ **A REFUSAL DESCRIBES THE PAYLOAD IT REFUSED, AND THAT PAYLOAD IS GONE
    // THE MOMENT THE CLERK TYPES.** `DEF-RAT-5829`'s third clause: the banner
    // and the per-field errors were cleared only by the NEXT submit, so the
    // screen went on demanding a value that was now on it. Once `DEF-RAT-5830`
    // puts the message at its own box, a stale one is a red box over a
    // corrected field, which is worse than an unplaced sentence.
    // ⚠ **TWO BANNERS, TWO OWNERS, AND CONFLATING THEM WAS WHY THE FIRST
    // VERSION OF THIS VERDICT SAID NOTHING USEFUL.**
    //   · the WIZARD's own refusal strip and its per-field errors belong to
    //     `RateScheduleWizard`, and they now clear on the first edit.
    //   · the red FAILURE CARD belongs to `WizardFrame`, is shared with five
    //     other wizards, and holds the message until `Retry` or `Cancel`.
    // So the box is asked about separately from the page, and the card's own
    // staleness is reported against the defect that owns it rather than being
    // folded into a single pass/fail nobody can act on.
    const boxStale = await p.evaluate(() => {
      const box = document.querySelector("#season-price-0");
      if (!box) return "(no box)";
      return (box.getAttribute("aria-describedby") || "")
        .split(/\s+/)
        .filter(Boolean)
        .map((id) => document.getElementById(id)?.textContent || "")
        .join(" ");
    });
    verdict(
      "DEF-RAT-5830",
      "the per-field refusal clears when the clerk types the missing price",
      !/required/i.test(boxStale),
      `the season price box still reads: "${boxStale}"`,
    );
    note(
      stillSaysRequired
        ? "the FAILURE CARD still repeats the refused message — WizardFrame's, shared with five wizards (DEF-RAT-5829, open)"
        : "nothing on the page still demands the value that has been typed",
    );
    // Take the only door there is.
    const retry = p.locator("main button").filter({ hasText: /^Retry$/ });
    if (await retry.count()) {
      await retry.first().click();
      act();
      await p.waitForTimeout(3500);
      const made = /rates\/[0-9a-f-]{36}/.test(p.url()) || p.url().endsWith("/rates");
      cur.result = made
        ? "created — but only after pressing Retry inside a failure card; the wizard never offered Continue again"
        : `Retry did not land it (${p.url()})`;
      note(`Retry left the clerk at ${p.url()}`);
      SEASONAL_DONE = true;
    }
  }
  if (!SEASONAL_DONE) {
    const out = await finish({ effectiveFrom: TODAY, reason: "Walk: summer and winter" });
    await landed(out, cur, `WALK ${stamp} Seasonal water`);
  } else {
    // Confirm from the LIST that the schedule really exists, because "Retry
    // returned me to the list" is not the same claim as "it was created".
    const q = new URLSearchParams({ q: `WALK ${stamp} Seasonal water` }).toString();
    await p.goto(`${BASE}/${T}/plans-rates/rates?${q}`, { waitUntil: "networkidle" });
    await p.waitForTimeout(1800);
    const row = p.locator("table tbody tr").filter({ hasText: `WALK ${stamp} Seasonal water` });
    note((await row.count()) > 0
      ? `the seasonal schedule is on the list: ${(await row.first().innerText()).replace(/\s+/g, " ").trim().slice(0, 170)}`
      : "the seasonal schedule is NOT on the list after Retry");
  }
  console.log(`   ${cur.result} · ${cur.acts} acts, ${cur.steps} steps`);
} catch (e) {
  if (e instanceof SkipScenario) { SCENARIOS.pop(); cur = null; }
  else
  // ⚠ ONE SCENARIO MUST NOT KILL THE WALK. A timeout in the fourth
  // structure used to end the run before the fifth, the two verbs and the
  // plan audit were ever reached — so the report was silently PARTIAL.
  dead(`the walk could not finish this scenario: ${e.message.split("\n")[0]}`);
}

// ═══════════════════════════════════════════════════════════════════════════
// 6 · THE THREE VERBS — CORRECT over the SAME window vs CHANGE over a NEW one
//     (`BR-RAT-1016`, PO 2026-09-17). Walked on the flat schedule this run
//     created, so what each verb LEAVES BEHIND is read off one object's own
//     history rather than inferred from two different objects.
// ═══════════════════════════════════════════════════════════════════════════
async function openScheduleAudit(url) {
  await p.goto(url, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  const tab = p.locator("main button, main a").filter({ hasText: /^Audit$/ });
  if (await tab.count()) {
    await tab.first().click();
    act();
    await p.waitForTimeout(1500);
  }
  return await mainText();
}

try {
  scenario("6a · Correct — same window");
  if (skipped("6a · Correct — same window")) throw new SkipScenario();
  console.log("\n=== 6a · CORRECT (same window) ===");
  if (!FLAT_URL) {
    dead("scenario 1 did not leave a schedule to correct");
  } else {
    await p.goto(FLAT_URL, { waitUntil: "networkidle" });
    await p.waitForTimeout(1800);
    const doors = await p.evaluate(() =>
      Array.from(document.querySelectorAll("main button, main a"))
        .map((e) => (e.innerText || "").replace(/\s+/g, " ").trim())
        .filter((x) => x && x.length < 40),
    );
    note(`doors on the schedule: ${JSON.stringify(doors.slice(0, 16))}`);
    const edit = p.locator("main button, main a").filter({ hasText: /^Edit$/ });
    if (!(await edit.count())) {
      dead("no Edit door on the schedule detail");
    } else {
      await edit.first().click();
      act();
      await p.waitForTimeout(2800);
      // ⚠ **`#rate-edit-intent` MATCHES NOTHING AND THAT NEARLY COST A FALSE
      // FINDING.** `SegmentedField` puts the id on the LABEL (`<id>-label`)
      // and uses it as the radio group's `name`; no element carries the bare
      // id. A run of this walk using `#rate-edit-intent` reported "the
      // correction verb has no door on a schedule with a version in force" —
      // over a picker that is on screen, checked, and works. THE SELECTOR
      // LIED, not the product. Match the radio by NAME.
      const picker = p.locator('input[name="rate-edit-intent"]');
      const asked = (await picker.count()) > 0;
      note(asked
        ? "the editor asks 'What are you doing?' before anything else"
        : "the editor does NOT ask change-vs-correction on a live schedule");
      if (!asked) {
        dead("the correction verb has no door on a schedule with a version in force");
        cur.result = "could not reach the correction verb";
      } else {
        // The picker is a SegmentedField, so the option is a button.
        const correct = p.locator('input[name="rate-edit-intent"][value="correct"]');
        if (!(await correct.count())) {
          dead("'Fix an error' is not offered inside the intent picker");
        } else {
          // ⚠ The radio is visually hidden inside `.seg-opt`, so `.check()`
          // waits thirty seconds for an element that is never actionable.
          // The LABEL is what a clerk clicks, so that is what this clicks.
          await p.locator("main label").filter({ hasText: /Fix an error/ }).first().click();
          act();
          await p.waitForTimeout(900);
          const fact = await mainText();
          note(/Same dates/i.test(fact)
            ? "choosing Fix an error says 'Same dates. The price was wrong.'"
            : "choosing Fix an error says nothing about the dates");
          const issued = (fact.match(/[^\n]*(bill|issued)[^\n]*/i) || [""])[0].trim().slice(0, 140);
          if (issued) note(`it also says: ${issued}`);
          // Walk to step 3 and change the price, then to step 4 and see
          // whether the dates are the ORIGINAL window or the payload's.
          for (let i = 0; i < 2; i++) { await nextStep(); }
          await fill("#flat-unit-price", "0.1250");
          await nextStep(); // step 4
          const eff = await p.inputValue("#rate-effective-from").catch(() => "(no field)");
          const effTo = await p.inputValue("#rate-effective-to").catch(() => "(no field)");
          note(`on a CORRECTION, effective from = ${eff || "(blank)"}, to = ${effTo || "(blank)"}`);
          // a correction needs its own reason — find the field that asks for it
          const why = await p.evaluate(() =>
            Array.from(document.querySelectorAll("main input,main textarea"))
              .map((e) => `${e.id}::${e.labels && e.labels[0] ? e.labels[0].innerText.replace(/\s+/g, " ") : ""}`)
              .filter((x) => /why|reason|changed|error|correct/i.test(x)),
          );
          note(`fields asking WHY on the correction path: ${JSON.stringify(why)}`);
          for (const id of ["rate-correction-reason", "rate-change-reason"]) {
            if (await p.locator(`#${id}`).count()) {
              await fill(`#${id}`, "Walk: the 0.1150 was keyed from the wrong sheet");
              break;
            }
          }
          await nextStep(); // step 5
          const review = await mainText();
          note(/Same dates|corrects|correction/i.test(review)
            ? "the review says this is a correction"
            : "the review does not say this is a correction");
          const out = { review, commitLabel: null, url: null, after: null };
          const commit = p.locator("main button").filter({ hasText: COMMIT });
          if (!(await commit.count())) {
            dead("the correction has no commit button on step 5");
          } else {
            out.commitLabel = (await commit.first().innerText()).trim();
            await commit.first().click();
            act();
            await p.waitForTimeout(3000);
            out.url = p.url();
            out.after = await mainText();
            note(`commit read "${out.commitLabel}"`);
            CORRECTION_REASON = "Walk: the 0.1150 was keyed from the wrong sheet";
          }
        }
      }
    }
    // ── WHAT DID THE CORRECTION LEAVE BEHIND, ON THE SCREEN? ──────────────
    // This is the half of `BR-RAT-1016` a clerk actually sees. The chain is
    // stored either way; the question is whether the schedule's own history
    // says a correction happened, and what it calls the row that was
    // corrected AWAY.
    const audit = await openScheduleAudit(FLAT_URL);
    console.log("--- SCHEDULE AUDIT AFTER THE CORRECTION ---");
    console.log(audit.slice(0, 1800));
    const rows = (audit.match(/\nv\d[\s\S]*?(Active|Scheduled|Superseded|Corrected|Draft)\n/g) || []).length;
    const saysCorrection = /correct/i.test(audit);
    const carriesReason = CORRECTION_REASON !== null && audit.includes(CORRECTION_REASON);
    const callsItScheduled = /Scheduled/.test(audit);
    // ── `DEF-RAT-5827`, in four verdicts because it was four separate silences
    // and a single "does it say correction" would pass on any one of them.
    verdict(
      "DEF-RAT-5827",
      "the schedule's own history uses the word correction",
      saysCorrection,
      flat(audit).slice(0, 260),
    );
    verdict(
      "DEF-RAT-5827",
      "the correction's OWN reason is on the schedule's history",
      carriesReason,
      `looked for: "${CORRECTION_REASON}"`,
    );
    verdict(
      "DEF-RAT-5827",
      "the corrected-away row is not labelled Scheduled",
      !callsItScheduled,
      "a row still reads 'Scheduled', the word this screen uses for a change still to come",
    );
    verdict(
      "DEF-RAT-5827",
      "the corrected-away row says so on its own line",
      /This filing was corrected/i.test(audit),
      flat(audit).slice(0, 260),
    );
    note(`the history now lists ${rows} version row(s)`);
    note(saysCorrection
      ? "the schedule's own history uses the word correction"
      : "the schedule's own history NEVER uses the word correction");
    note(carriesReason
      ? "the correction's own reason is on the schedule's history"
      : "the correction's own reason is NOT on the schedule's history — both rows show the ORIGINAL filing's reason");
    if (callsItScheduled) {
      note("the corrected-away row is labelled 'Scheduled', the word this screen uses for a change still to come");
    }
    if (!saysCorrection) {
      dead("a correction of a live price leaves no trace on the schedule's own Audit tab");
    }
    cur.result = saysCorrection
      ? "the correction is recorded and the schedule says so"
      : "the correction was accepted and the schedule's history does not say a correction happened";
  }
  console.log(`   ${cur.result} · ${cur.acts} acts`);
} catch (e) {
  if (e instanceof SkipScenario) { SCENARIOS.pop(); cur = null; }
  else
  // ⚠ ONE SCENARIO MUST NOT KILL THE WALK. A timeout in the fourth
  // structure used to end the run before the fifth, the two verbs and the
  // plan audit were ever reached — so the report was silently PARTIAL.
  dead(`the walk could not finish this scenario: ${e.message.split("\n")[0]}`);
}

try {
  scenario("6b · Change — new window");
  if (skipped("6b · Change — new window")) throw new SkipScenario();
  console.log("\n=== 6b · CHANGE (new window) ===");
  if (!FLAT_URL) {
    dead("scenario 1 did not leave a schedule to change");
  } else {
    await p.goto(FLAT_URL, { waitUntil: "networkidle" });
    await p.waitForTimeout(1800);
    const edit = p.locator("main button, main a").filter({ hasText: /^Edit$/ });
    if (!(await edit.count())) {
      dead("no Edit door on the schedule detail");
    } else {
      await edit.first().click();
      act();
      await p.waitForTimeout(2800);
      // `change` is the default, so nothing is clicked to choose it — which is
      // itself worth recording: the safer verb is the one you have to pick.
      const picker = p.locator("#rate-edit-intent");
      if (await picker.count()) {
        const chosen = await p.evaluate(() => {
          const el = document.querySelector("#rate-edit-intent");
          const on = el && el.querySelector("[aria-checked=true],[aria-pressed=true],.is-selected");
          return on ? on.textContent.trim() : "(cannot tell)";
        });
        note(`the picker opens on: ${chosen}`);
      }
      for (let i = 0; i < 2; i++) { await nextStep(); }
      await fill("#flat-unit-price", "0.1400");
      await nextStep(); // step 4
      const effBefore = await p.inputValue("#rate-effective-from").catch(() => "");
      const toBefore = await p.inputValue("#rate-effective-to").catch(() => "");
      note(`on a CHANGE, effective from opens as ${effBefore || "(blank)"} — the clerk supplies the new window`);
      note(`on a CHANGE, effective TO opens as ${toBefore || "(blank)"}`);
      if (toBefore) {
        // The new-version form is seeded from the row being SUPERSEDED, so it
        // arrives carrying that row's closing date. Two costs, and the second
        // is the quiet one: a new window starting after that date is refused
        // over a field nobody typed, and a new window starting BEFORE it
        // silently inherits it as its own end.
        dead(`the new version's end date is pre-filled with the outgoing version's (${toBefore}) — a date the clerk did not type`);
      }
      // ── `DEF-RAT-5833` · BOTH DATES OPEN BLANK ON A NEW VERSION ──────────
      // The window is the one fact a new version may not inherit:
      // `activate_new_version` closes the outgoing version itself, so an end
      // date here is never how the old one is ended.
      verdict(
        "DEF-RAT-5833",
        "a new version's END date opens blank",
        toBefore === "",
        `#rate-effective-to opened as "${toBefore}"`,
      );
      verdict(
        "DEF-RAT-5833",
        "a new version's START date opens blank",
        effBefore === "",
        `#rate-effective-from opened as "${effBefore}"`,
      );
      await fill("#rate-effective-from", "2027-09-01"); // a NEW window, well clear of the one in force
      await fill("#rate-change-reason", "Walk: 2027 filing, energy to 0.1400");
      await nextStep(); // step 5
      const commit = p.locator("main button").filter({ hasText: COMMIT });
      if (!(await commit.count())) {
        dead("the change has no commit button on step 5");
      } else {
        const label = (await commit.first().innerText()).trim();
        await commit.first().click();
        act();
        await p.waitForTimeout(3000);
        note(`commit read "${label}"`);
        // The commit returns the clerk to the LIST, so the verdict is read off
        // the schedule's own history and not off the URL.
        const hist = await openScheduleAudit(FLAT_URL);
        const madeV2 = /0\.1400|2027/.test(hist) && /Walk: 2027 filing/.test(hist);
        cur.result = madeV2
          ? `a NEW version was created over a new window — commit read "${label}"`
          : `the change did not reach the schedule's history — ${refusalText(await mainText())}`;
      }
    }
    const audit = await openScheduleAudit(FLAT_URL);
    console.log("--- SCHEDULE AUDIT AFTER THE CHANGE ---");
    console.log(audit.slice(0, 2400));
  }
  console.log(`   ${cur.result} · ${cur.acts} acts`);
} catch (e) {
  if (e instanceof SkipScenario) { SCENARIOS.pop(); cur = null; }
  else
  // ⚠ ONE SCENARIO MUST NOT KILL THE WALK. A timeout in the fourth
  // structure used to end the run before the fifth, the two verbs and the
  // plan audit were ever reached — so the report was silently PARTIAL.
  dead(`the walk could not finish this scenario: ${e.message.split("\n")[0]}`);
}

// ═══════════════════════════════════════════════════════════════════════════
// 7 · THE PLAN'S AUDIT — does a plan show anything when its rates move
//     underneath it? Read off the SCREEN.
// ═══════════════════════════════════════════════════════════════════════════
try {
  scenario("7 · Plan audit");
  if (skipped("7 · Plan audit")) throw new SkipScenario();
  console.log("\n=== 7 · PLAN AUDIT ===");
  await p.goto(`${BASE}/${T}/plans-rates/plans`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  const openable = p.locator("table tbody tr button.rating-link");
  if (!(await openable.count())) {
    dead("no plan row opens — `button.rating-link` found nothing");
  } else {
    await openable.first().click();
    act();
    await p.waitForTimeout(2500);
    const planUrl = p.url();
    note(`opened ${planUrl}`);
    const tab = p.locator("main button, main a").filter({ hasText: /^Audit$/ });
    if (!(await tab.count())) {
      dead("the plan has no Audit tab");
    } else {
      await tab.first().click();
      act();
      await p.waitForTimeout(2000);
      const audit = await mainText();
      const tellsBound = /underneath|what moved|rate change|schedule/i.test(audit);
      cur.result = tellsBound
        ? "the Audit tab carries a panel for changes underneath the plan"
        : "the Audit tab says nothing about changes underneath the plan";
      note(cur.result);
      const blind = audit.match(/[^\n]*(not shown|cannot|does not include|tax|discount)[^\n]*/i);
      if (blind) note(`blind-spot sentence on screen: ${blind[0].slice(0, 160)}`);
      console.log("--- AUDIT TAB TEXT ---");
      console.log(audit.slice(0, 2200));
    }
  }
  console.log(`   ${cur.result} · ${cur.acts} acts`);
} catch (e) {
  if (e instanceof SkipScenario) { SCENARIOS.pop(); cur = null; }
  else
  // ⚠ ONE SCENARIO MUST NOT KILL THE WALK. A timeout in the fourth
  // structure used to end the run before the fifth, the two verbs and the
  // plan audit were ever reached — so the report was silently PARTIAL.
  dead(`the walk could not finish this scenario: ${e.message.split("\n")[0]}`);
}

// ═══════════════════════════════════════════════════════════════════════════
// 8 · A RATE FILED AHEAD OF TIME — the ordinary case of a utility filing next
//     year's price before this year's exists. Nothing is in force, so every
//     word the screen uses for "which version is live" has to come from
//     somewhere other than the clock.
// ═══════════════════════════════════════════════════════════════════════════
try {
  scenario("8 · A rate filed ahead of time");
  if (skipped("8 · A rate filed ahead of time")) throw new SkipScenario();
  console.log("\n=== 8 · A RATE FILED AHEAD OF TIME ===");
  const name = `WALK ${stamp} Future filing`;
  await openWizardTo3(name, "water", "kgal");
  await pick("#rate-model", "flat");
  await p.waitForTimeout(400);
  await fill("#flat-unit-price", "9.9900");
  const out = await finish({ effectiveFrom: "2027-03-01", reason: "Walk: the 2027 filing" });
  const url = await landed(out, cur, name);
  if (url) {
    await p.goto(url, { waitUntil: "networkidle" });
    await p.waitForTimeout(2000);
    const head = await mainText();
    // Four places one screen states which version is live. They are read
    // separately and compared, because a screen that disagrees with itself
    // passes every check this repo has.
    const pill = (head.match(/\n(Draft|Active|Archived)\n/) || [])[1] || "(none)";
    const inForceTile = (head.match(/IN FORCE\n([^\n]*)\n([^\n]*)/) || []).slice(1).join(" · ");
    const nextTile = (head.match(/NEXT CHANGE\n([^\n]*)/) || [])[1] || "(none)";
    const eyebrow = (head.match(/RATE SCHEDULE[^\n]*/) || [])[0] || "(none)";
    note(`status pill:     ${pill}`);
    note(`IN FORCE tile:   ${inForceTile}`);
    note(`NEXT CHANGE tile:${nextTile}`);
    note(`eyebrow:         ${eyebrow}`);
    await openScheduleAudit(url);
    const audit = await mainText();
    const rowState = (audit.match(/\n(Active|Scheduled|Superseded|Draft)\n/g) || []).map((x) => x.trim());
    note(`the Audit table's STATUS words: ${JSON.stringify(rowState)}`);
    const disagrees = /Draft/.test(pill) && /v\d/.test(inForceTile);
    // ── `DEF-RAT-5831` · ONE SCREEN, ONE ANSWER ─────────────────────────────
    // `schedule_card` serves `current = in_force_version(today) or
    // latest_version(tariff)`, so `current_version` is a FALLBACK when nothing
    // is in force — and every surface keyed off it repeated the fallback as a
    // fact while the pill beside them said Draft.
    verdict(
      "DEF-RAT-5831",
      "the IN FORCE tile does not name a version while the pill says Draft",
      !disagrees,
      `pill "${pill}" · IN FORCE tile "${inForceTile}"`,
    );
    verdict(
      "DEF-RAT-5831",
      "no version in the history claims to be Active",
      !rowState.includes("Active"),
      `status words: ${JSON.stringify(rowState)}`,
    );
    cur.result = disagrees
      ? "the screen says Draft in the pill and names a version as IN FORCE in the same header"
      : "the header agrees with itself";
    if (disagrees) {
      dead("nothing is in force, and the IN FORCE tile names a version anyway");
    }
    console.log("--- THE FUTURE-FILED SCHEDULE, AS DRAWN ---");
    console.log(audit.slice(0, 1600));
  }
  console.log(`   ${cur.result} · ${cur.acts} acts, ${cur.steps} steps`);
} catch (e) {
  // ⚠ **A SKIPPED SCENARIO IS NOT A DEAD END.** These two catches had no
  // `SkipScenario` branch, so every `RSW_ONLY` run printed
  // `DEAD END · the walk could not finish this scenario:` with an empty reason
  // — a red in the log that means nothing happened. Same class as the false
  // dead end on `finish`: a reader who learns to ignore one learns to ignore
  // the next one, which will be real.
  if (e instanceof SkipScenario) { SCENARIOS.pop(); cur = null; }
  else dead(`the walk could not finish this scenario: ${e.message.split("\n")[0]}`);
}

// ═══════════════════════════════════════════════════════════════════════════
// 9 · THE PO's OWN QUESTION, END TO END — *"also correction or new rate
//     schedule - when you cahnge does is update the plans audit"*. Scenario 7
//     only showed that the panel EXISTS. This changes a schedule a plan
//     actually binds and then goes and looks at that plan.
// ═══════════════════════════════════════════════════════════════════════════
try {
  scenario("9 · A bound schedule changes — does the plan hear about it");
  if (skipped("9 · A bound schedule changes — does the plan hear about it")) throw new SkipScenario();
  console.log("\n=== 9 · DOES THE PLAN HEAR ABOUT IT ===");
  // A schedule a plan binds: the list's PLANS column is the fact, so the row
  // is chosen from the list rather than assumed.
  await p.goto(`${BASE}/${T}/plans-rates/rates`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  const bound = await p.evaluate(() =>
    Array.from(document.querySelectorAll("table tbody tr"))
      .map((tr) => Array.from(tr.querySelectorAll("td,th")).map((td) => td.innerText.replace(/\s+/g, " ").trim()))
      .filter((cells) => cells.length > 6 && /^[1-9]/.test(cells[5] || ""))
      .map((cells) => cells[0]),
  );
  note(`schedules a plan binds: ${JSON.stringify(bound.slice(0, 6))}`);
  if (bound.length === 0) {
    dead("no rate schedule on this tenant is bound to a plan, so the loop cannot be walked");
  } else {
    const target = bound[0];
    // 1 · what the plan says BEFORE
    const planOf = async () => {
      await p.goto(`${BASE}/${T}/plans-rates/plans`, { waitUntil: "networkidle" });
      await p.waitForTimeout(1500);
      const rows = p.locator("table tbody tr button.rating-link");
      const n = await rows.count();
      for (let i = 0; i < n; i++) {
        await rows.nth(i).click();
        await p.waitForTimeout(2200);
        const t = await mainText();
        if (t.includes(target)) return p.url();
        await p.goto(`${BASE}/${T}/plans-rates/plans`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
      }
      return null;
    };
    const planUrl = await planOf();
    if (!planUrl) {
      dead(`could not find the plan that binds "${target}" from the plan list`);
    } else {
      note(`the plan that binds "${target}" is ${planUrl}`);
      const auditRows = async () => {
        await p.goto(planUrl, { waitUntil: "networkidle" });
        await p.waitForTimeout(1500);
        await p.locator("main button, main a").filter({ hasText: /^Audit$/ }).first().click();
        await p.waitForTimeout(2000);
        const t = await mainText();
        const m = t.match(/Changes underneath[\s\S]*?(\d+)–(\d+) of (\d+)/);
        return { total: m ? Number(m[3]) : null, text: t };
      };
      const before = await auditRows();
      note(`before the change, the plan's "Changes underneath" shows ${before.total} row(s)`);

      // 2 · change the schedule the plan binds
      await p.goto(`${BASE}/${T}/plans-rates/rates`, { waitUntil: "networkidle" });
      await p.waitForTimeout(1500);
      const row = p.locator("table tbody tr").filter({ hasText: target });
      await row.first().locator("button").first().click();
      act();
      await p.waitForTimeout(2200);
      await p.locator("main button, main a").filter({ hasText: /^Edit$/ }).first().click();
      act();
      await p.waitForTimeout(2800);
      const REASON = `Walk ${stamp}: does this reach the plan`;
      // The minimum is a version field every structure carries, so this works
      // whatever shape the bound schedule happens to be.
      for (let i = 0; i < 3 && (await p.locator("#rate-minimum-bill").count()) === 0; i++) {
        if (!(await nextStep())) break;
      }
      if (await p.locator("#rate-minimum-bill").count()) {
        await fill("#rate-minimum-bill", "1.2300");
      } else {
        note("the version's minimum box was not reachable; the change is dates-only");
      }
      // ⚠ **A FIXED FUTURE DATE MAKES THIS SCENARIO LIE ON ITS SECOND RUN.**
      // The second run files the same window as the first, the non-overlap
      // guard refuses it, no `rate_change_log` row is written — and the walk
      // then reports "the plan is not told", which is a confident, specific,
      // wrong finding about somebody else's work. The window is derived from
      // this run's stamp so every run files a window of its own.
      // ⚠ **AND IT MUST BE LATER THAN EVERY WINDOW A PREVIOUS RUN FILED, WHICH
      // A STAMP-DERIVED DATE IS NOT.** The old derivation took a month and a
      // day out of `stamp`, which moves but does not ASCEND: a later run could
      // land on an EARLIER date than the version it had just filed, and
      // `_guard_window` then refused it with `rating.schedules.window_overlap`
      // — after which this scenario reports *"the plan is not told"*, which is
      // a confident, specific, wrong finding about somebody else's work. That
      // is the exact hazard the comment above already warned about, in a form
      // the fix for it did not cover. Hours elapsed since this walk was
      // written ascends by 24 a day and never repeats.
      // ⚠ **MINUTES, NOT HOURS.** Hours was the first fix and two runs inside
      // one hour still collided — which is how this scenario reported
      // INCONCLUSIVE twice in an afternoon over a server refusal that was
      // entirely its own doing. Minutes since this walk was written ascends by
      // 1,440 a day, so only two runs in the SAME MINUTE can repeat a window,
      // and the refusal is now read off the screen rather than guessed at, so
      // even that case reports what actually happened.
      const MINUTES = Math.floor((Date.now() - Date.UTC(2026, 8, 19)) / 60000);
      const filedAt = new Date(Date.UTC(2030, 0, 1) + MINUTES * 86400000);
      const window = filedAt.toISOString().slice(0, 10);
      // Walk to step 4 first, so the carried-over end date can be recorded AND
      // cleared. Left in place it refuses the filing (`DEF-RAT-5833`), and
      // this scenario is here to answer the PO's question about the plan, not
      // to be blocked by a different defect on the way.
      for (let i = 0; i < 4 && (await p.locator("#rate-effective-to").count()) === 0; i++) {
        if (!(await nextStep())) break;
      }
      const carried = await p.inputValue("#rate-effective-to").catch(() => "");
      if (carried) {
        dead(`the new version's end date arrived pre-filled with the outgoing version's (${carried}); clearing it to get past DEF-RAT-5833`);
      }
      // Order matters: set the new START first, then clear the inherited END.
      // Clearing first leaves the form momentarily inverted and the date
      // control does not settle.
      await fill("#rate-effective-from", window);
      if (carried) {
        await p.locator("#rate-effective-to").fill("");
        act();
        await p.waitForTimeout(600);
        note(`end date after clearing: "${await p.inputValue("#rate-effective-to").catch(() => "?")}"`);
      }
      if (await p.locator("#rate-change-reason").count()) {
        await fill("#rate-change-reason", REASON);
      }
      // Already standing on step 4 — the loop above walked here to read the
      // carried end date, so `finish` must not walk again (see `atEffective`).
      const out = await finish({
        effectiveFrom: null,
        reason: null,
        atEffective: true,
        expectRates: "Energy price per kWh",
      });
      note(`commit read "${out.commitLabel}" for a window starting ${window}`);
      // And the refusal is READ, so a failed commit cannot be mistaken for a
      // plan that was never told.
      // ⚠ `/rates/<uuid>/edit` MATCHES `/rates/<uuid>/`, so a naive test reads
      // "still on the form after a 422" as "landed on the schedule". That is
      // how a refused filing was reported as a plan that was never told.
      const landedOk = !/\/edit$/.test(out.url)
        && (/rates\/[0-9a-f-]{36}$/.test(out.url) || out.url.endsWith("/rates"));
      const said = (await refusalOnScreen()) || refusalText(out.after);
      if (!landedOk || /could not|cannot|refus|overlap/i.test(said)) {
        note(`the schedule change itself did not land — the screen says: ${said || "(nothing)"}`);
      }

      // 3 · DID THE SCHEDULE ITSELF MOVE? Ask this BEFORE asking the plan.
      // A change that never landed and a plan that was never told look
      // identical from the plan's side, and only one of them is a product
      // fault. Runs of this walk on 2026-09-19 reported the second when the
      // truth was the first.
      await p.goto(`${BASE}/${T}/plans-rates/rates`, { waitUntil: "networkidle" });
      await p.waitForTimeout(1500);
      const r2 = p.locator("table tbody tr").filter({ hasText: target });
      await r2.first().locator("button").first().click();
      await p.waitForTimeout(2200);
      await p.locator("main button, main a").filter({ hasText: /^Audit$/ }).first().click();
      await p.waitForTimeout(1800);
      const schedHist = await mainText();
      const scheduleMoved = schedHist.includes(REASON);
      note(scheduleMoved
        ? "the schedule's own history carries the new version"
        : "the schedule's own history does NOT carry it — the change never landed, so the plan cannot be at fault");
      if (!scheduleMoved) {
        cur.result = "INCONCLUSIVE — the schedule change did not land, so this says nothing about the plan";
        dead(cur.result);
        throw new SkipScenario();
      }

      // 4 · what the plan says AFTER
      const after = await auditRows();
      note(`after the change, the plan's "Changes underneath" shows ${after.total} row(s)`);
      const named = after.text.includes(REASON);
      cur.result = named
        ? `YES — the plan's Audit tab names the change, with the reason typed on the schedule`
        : `the plan's Audit tab does not name it (${before.total} → ${after.total} rows) — CHECK THE SCHEDULE CHANGE LANDED before calling this a product fault`;
      if (!named) dead(cur.result);
      const line = (after.text.match(new RegExp(`[^\n]*${stamp}[^\n]*`)) || [""])[0];
      if (line) note(`the row the plan shows: ${line.trim().slice(0, 180)}`);
    }
  }
  console.log(`   ${cur.result} · ${cur.acts} acts`);
} catch (e) {
  // ⚠ **A SKIPPED SCENARIO IS NOT A DEAD END.** These two catches had no
  // `SkipScenario` branch, so every `RSW_ONLY` run printed
  // `DEAD END · the walk could not finish this scenario:` with an empty reason
  // — a red in the log that means nothing happened. Same class as the false
  // dead end on `finish`: a reader who learns to ignore one learns to ignore
  // the next one, which will be real.
  if (e instanceof SkipScenario) { SCENARIOS.pop(); cur = null; }
  else dead(`the walk could not finish this scenario: ${e.message.split("\n")[0]}`);
}

// ── the report ─────────────────────────────────────────────────────────────
console.log("\n\n════════ FRICTION, MEASURED ════════");
for (const s of SCENARIOS) {
  console.log(`\n${s.name}`);
  console.log(`  acts (fields filled + controls clicked): ${s.acts}`);
  console.log(`  wizard steps entered:                    ${s.steps}`);
  console.log(`  outcome: ${s.result || "(none recorded)"}`);
  for (const g of s.guesses) console.log(`  GUESS    · ${g}`);
  for (const d of s.deadEnds) console.log(`  DEAD END · ${d}`);
  for (const n of s.notes) console.log(`  note     · ${n}`);
}
// ⚠ **THE VERDICTS ARE PRINTED LAST AND TOGETHER**, because a true FAIL in the
// middle of a 300-line log is exactly where a red goes to hide (CLAUDE.md's
// hard-won law 7, habit 1). A scenario that never ran records no verdict, so
// the COUNT is printed beside the results: nine verdicts and eight results is a
// partial walk, which reads nothing like a pass.
console.log("\n\n════════ VERDICTS ════════");
if (VERDICTS.length === 0) {
  console.log("  (none recorded — no scenario that carries one was reached)");
} else {
  for (const v of VERDICTS) {
    console.log(`  ${v.ok ? "PASS" : "FAIL"} · ${v.id} · ${v.what}`);
    if (!v.ok) console.log(`         saw: ${v.saw}`);
  }
  const failed = VERDICTS.filter((v) => !v.ok).length;
  console.log(
    `\n  ${VERDICTS.length - failed} of ${VERDICTS.length} verdicts pass` +
      (failed ? ` — ${failed} FAIL` : ""),
  );
}
if (pageErrors.length) {
  console.log("\n════════ PAGE ERRORS ════════");
  for (const e of [...new Set(pageErrors)]) console.log(`  ${e}`);
}
await b.close();
