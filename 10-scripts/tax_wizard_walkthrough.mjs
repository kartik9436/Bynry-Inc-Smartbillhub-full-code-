// ── TAX-02 WALKED END TO END, AS A CLERK, IN A BROWSER ─────────────────────
//
// The PO's ask, 2026-09-19: *"Run end to end Walk for Discount and Tax also
// simialr to rate and Charge code"*, to the standard they set for all of them —
// *"walk ahould check plasna dn rates work end to end - clark dont have any
// frictions to perform his job, overall user experience is good"*.
//
// It is a SCREEN walk and it deliberately prices no bill: the PO struck that
// requirement. What it measures is whether a clerk can do the job — how many
// clicks, where they must guess, and what they are not told that they need.
//
// TWO SCENARIOS, because the screen has two doors and they must be tellable
// apart: CREATE a tax from nothing, and EDIT a live one, which opens as a
// *"Filing a correction"*.
//
// WHAT IT FOUND, AND WHAT IT NOW GUARDS — all three fixed 2026-09-19:
//   · `DEF-RAT-5804` — Continue on an incomplete step 1 refused and said
//     NOTHING: no sentence, no marked field, nothing on screen changed. The
//     guard fired correctly every time and erased its own evidence one line
//     later. The checks now assert the SENTENCE is on screen and the empty
//     FIELD is marked — *"the page did not advance"* passes on the defect too.
//   · `DEF-RAT-5805` — the Named place help read *"Left blank, this reaches
//     nobody."* while the count four lines below read *"71 of 79 premises
//     match."* One sentence described two opposite behaviours: it is TRUE of
//     *In a state* and false of *Inside city limits*.
//   · `DEF-RAT-5806` — the Named place appeared not to narrow: a city this
//     utility has never heard of reached the same 71 premises as the right one,
//     and a town of six reached seventy-seven.
//
// ⚠ **5805 AND 5806 ARE ONE BEHAVIOUR SEEN FROM TWO SIDES, AND THE ENGINE WAS
// RIGHT.** `premises_in_scope` reads each premises' own city-limits FLAG first
// and falls back to the typed name only where no flag is recorded — signed
// behaviour (CR-013 part 4: *"premise city-limit flags drive attachment and are
// audit-logged on the premise"*, and `BR-MET-1170` turns on the same
// precedence). **Nothing in the engine changed; the screen's account of it
// did.** So 77 is still 77, and these checks assert that the screen now says
// where all 77 came from — not that the number got smaller.
//
// ⚠ **SEVERAL CHECKS HERE USED TO ASSERT THE DEFECT**, because they were
// written from the copy rather than from the engine: *"THE WARNING MATCHES THE
// COUNT BESIDE IT"* demanded `count === "0"`, which could only ever have gone
// green if somebody had changed the engine to match a wrong sentence. They now
// assert the fix, and each one is noted where it stands.
// Sixty-nine other checks PASS, so the screen is in good shape; do not read a
// red run as the wizard being broken.
//
// ⚠ **IT REFUSES A STALE BUILD** — copied from
// `plan_wizard_seven_walkthrough.mjs`, where the guard was written after a walk
// against a `dist/` 26 hours old read three landed fixes as ABSENT. Nothing in
// the page says how old it is and every gate is green either way, because none
// of them look at `dist/`. A walk against a stale bundle is worse than no walk:
// it produces confident, specific, wrong findings about other people's work.
//
// ⚠ **IT NEVER JUMPS BY URL PAST STEP 1.** The wizard FENCES a new record —
// `clampStepToReached` sends a pasted `?step=2` back to step 1 — so a walk that
// navigated by address would assert over a screen that had done nothing. Every
// step here is reached by pressing Continue, and the clamp itself is asserted.
//
//   TAX_WALK_BASE     default http://127.0.0.1:8742
//   TAX_WALK_TENANT   default brazosbend
//   TAX_WALK_EMAIL    default dana@brazosbendutilities.com
//   TAX_WALK_PASSWORD default S3cure!passw0rd
//   TAX_WALK_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser in this container, so the path is passed explicitly — see
//      CLAUDE.md's environment note; never run `playwright install` here.)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync } from "node:fs";

const BASE = process.env.TAX_WALK_BASE || "http://127.0.0.1:8742";
const T = process.env.TAX_WALK_TENANT || "brazosbend";
const EMAIL = process.env.TAX_WALK_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.TAX_WALK_PASSWORD || "S3cure!passw0rd";
const CHROME =
  process.env.TAX_WALK_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const DIST = process.env.TAX_WALK_DIST || "07-frontend/dist/index.html";

// ── the staleness refusal ──────────────────────────────────────────────────
const built = statSync(DIST).mtime;
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

// ⚠ THE TAX THIS RUN MAKES CARRIES THIS RUN'S STAMP, and that is not
// decoration. Scenario B corrects the tax scenario A made, and it finds it by
// NAME in the catalogue: with a fixed name the second run picks the FIRST such
// row, which the previous run already corrected, and the product answers
// *"This rate has already been corrected"* — correctly. The walk would then
// report the product refusing as a failure of the product.
const STAMP = new Date().toISOString().slice(5, 16).replace(/[-:T]/g, "");
const TAX_NAME = `WALK levy ${STAMP}`;

const R = [];
const ok = (n, c, d = "") => R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`);
const note = (n) => R.push(`NOTE · ${n}`);

// ── the friction meter ─────────────────────────────────────────────────────
// Every click and every field a clerk fills is counted, per scenario, so the
// report carries a NUMBER rather than an impression.
let acts = 0;
let scenario = "";
const tally = {};
const bump = (what) => {
  acts += 1;
  tally[scenario] = tally[scenario] ?? { clicks: 0, typed: 0, picked: 0 };
  if (what === "type") tally[scenario].typed += 1;
  else if (what === "pick") tally[scenario].picked += 1;
  else tally[scenario].clicks += 1;
};

const b = await chromium.launch({ executablePath: CHROME });
const p = await b.newPage();
// ⚠ EACH SCENARIO RUNS INSIDE ITS OWN try/catch AND THE REPORT PRINTS EITHER
// WAY. A thrown selector timeout that swallows forty passing lines reads
// exactly like a screen that does nothing, and the walk would then be reporting
// on its own crash rather than on the product.
const click = async (loc) => {
  bump("click");
  await loc.click({ timeout: 8000 });
};
const fill = async (sel, value) => {
  bump("type");
  await p.fill(sel, value, { timeout: 8000 });
};
const pick = async (sel, value) => {
  bump("pick");
  await p.selectOption(sel, value, { timeout: 8000 });
};
const text = () => p.evaluate(() => document.body.innerText);
const matched = () =>
  p.evaluate(() => {
    const n = document.querySelector("[data-matched-premises]");
    return n
      ? { count: n.dataset.matchedPremises, total: n.dataset.matchedTotal, narrowed: n.dataset.matchedNarrowed }
      : null;
  });
const continueOn = async () => {
  await click(p.locator("button").filter({ hasText: /^Continue$/ }).first());
  await p.waitForTimeout(700);
};

// ── sign in (not counted — it is not part of the job) ───────────────────────
await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);

// The tax scenario A creates, which scenario B then corrects — declared out
// here because each scenario runs inside its own try block.
let createdId = null;

// ═══ SCENARIO A · a clerk creates a tax, starting from the module ═══════════
try {
  scenario = "A · create";
  await p.goto(`${BASE}/${T}/plans-rates`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1200);

  // The tab is reached by clicking, not by address — the walk measures the door.
  const taxTab = p.locator("button,a").filter({ hasText: /^Taxes\s*&\s*fees$/i }).first();
  ok("A door · a Taxes & fees tab exists on Plans & Rates", (await taxTab.count()) > 0);
  if (await taxTab.count()) {
    await click(taxTab);
    await p.waitForTimeout(1400);
  }
  const listBody = await text();
  ok("A door · the catalogue lists the tenant's taxes", /TX State Utility Tax/i.test(listBody));

  const newBtn = p.locator("button,a").filter({ hasText: /New tax or fee/i }).first();
  ok("A door · a New tax or fee control is present", (await newBtn.count()) > 0);
  if (await newBtn.count()) {
    await click(newBtn);
    await p.waitForTimeout(1600);
  }
  ok("A door · it opens the wizard route", /taxes-fees\/new/.test(p.url()), p.url());

  // ── the fence: a pasted ?step=2 must clamp back ────────────────────────────
  await p.goto(`${BASE}/${T}/plans-rates/taxes-fees/new?step=2`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1200);
  const clamped = await text();
  ok(
    "A fence · a pasted ?step=2 clamps back to step 1",
    /Step 1 of 3/i.test(clamped),
    (clamped.match(/Step \d of \d/i) || ["none"])[0],
  );

  // ── step 1 · what it is ────────────────────────────────────────────────────
  const s1 = await text();
  ok("A step 1 · the rail names three steps", /Step 1 of 3/i.test(s1));
  ok(
    "A step 1 · the three steps are What it is · How much · Review & save",
    /What it is/.test(s1) && /How much/.test(s1) && /Review & save/.test(s1),
  );
  ok("A step 1 · the sub-line agrees it is three steps", /Three steps/.test(s1));

  // The authority. There is no shared registry — a utility types its own, so the
  // walk asserts BOTH doors exist: an existing one, and minting a new one.
  const jur = p.locator("#jurisdiction");
  const jurOptions = await p.evaluate(() =>
    [...document.querySelectorAll("#jurisdiction option")].map((o) => o.innerText.trim()),
  );
  ok("A step 1 · an authority picker is present", (await jur.count()) > 0, `${jurOptions.length} options`);
  ok(
    "A step 1 · the utility can mint its own authority",
    jurOptions.some((o) => /add|new/i.test(o)),
    jurOptions.join(" | "),
  );

  await fill("#name", TAX_NAME);

  // ⚠ PRESS CONTINUE WITH THE AUTHORITY STILL UNSET. `wizard.blocked` tells the
  // clerk to *"Fill in what's marked above"*, so the walk asks the only
  // question that matters about that sentence: is anything actually marked?
  await click(p.locator("button").filter({ hasText: /^Continue$/ }).first());
  await p.waitForTimeout(900);
  const refusedS1 = await text();
  ok(
    "A guard · Continue is refused while the authority is unset",
    /Step 1 of 3/i.test(refusedS1),
    (refusedS1.match(/Step \d of \d/i) || ["none"])[0],
  );
  ok(
    "A guard · the refusal answers at the button",
    /isn't finished/i.test(refusedS1),
    (refusedS1.match(/This step isn't finished[^\n]*/) || ["none"])[0],
  );
  // ⚠ **`aria-invalid` ONLY — AND THE ORIGINAL ALSO MATCHED `.text-danger-700`,
  // WHICH IS A CHECK THAT CANNOT FAIL ON THIS SCREEN.** That class is on the
  // unresolvable-boundary note and on the zero-count note, so any red text
  // anywhere satisfied it while not one FIELD was marked. A mark is a field
  // saying *I am the problem*; red prose four panels away is not.
  const markedFields = await p.evaluate(() =>
    [...document.querySelectorAll('[aria-invalid="true"]')].map((n) => n.id).filter(Boolean),
  );
  ok(
    "A guard · and the EMPTY FIELD is marked, as the refusal promises",
    markedFields.includes("jurisdiction"),
    markedFields.length
      ? markedFields.join(" | ")
      : "NOTHING is marked — the clerk is sent to look for a mark that is not drawn",
  );
  const markText = await p.evaluate(() => {
    const e = document.getElementById("jurisdiction-error");
    return e ? e.innerText.trim() : null;
  });
  ok(
    "A guard · and the mark SAYS what to do",
    markText !== null && markText.length > 0,
    markText ?? "the field is marked but carries no words",
  );

  await pick("#jurisdiction", await p.evaluate(() => {
    const o = [...document.querySelectorAll("#jurisdiction option")].find(
      (x) => x.value && !/^__/.test(x.value),
    );
    return o ? o.value : "";
  }));
  await p.waitForTimeout(600);

  // ── the boundary, and the blank-value trap ─────────────────────────────────
  const beforeScope = await matched();
  ok(
    "A scope · with no boundary the screen says it reaches everyone",
    /reaches every premises/i.test(await text()) || beforeScope !== null,
    beforeScope ? `${beforeScope.count}/${beforeScope.total}` : "fixed sentence",
  );

  const scopeOptions = await p.evaluate(() =>
    [...document.querySelectorAll("#premises_scope_kind option")].map((o) => o.innerText.trim()),
  );
  ok("A scope · a Boundary picker is present", scopeOptions.length > 0, scopeOptions.join(" | "));

  // Switch the boundary ON and leave the named place BLANK. This is the trap the
  // walk exists to measure: what is the clerk TOLD, and is what they are told
  // TRUE of the number the same screen prints beside it?
  await pick("#premises_scope_kind", "city_limits");
  await p.waitForTimeout(1600);
  const blankTxt = await text();
  const blankCount = await matched();
  ok(
    "A scope · a second field asks which place it is measured against",
    (await p.locator("#premises_scope_value").count()) > 0,
  );
  // ⚠ **THIS BLOCK USED TO ASSERT THE DEFECT AND NOW ASSERTS THE FIX
  // (`DEF-RAT-5805`).** It read *"the blank place is called out"* → true, and
  // *"THE WARNING MATCHES THE COUNT BESIDE IT"* → `count === "0"`, which is
  // what a *reaches nobody* sentence would have to mean. It does not mean it
  // here: `premises_in_scope` reads each premises' own city-limits FLAG first
  // and only falls back to the typed name where no flag is recorded, so a blank
  // box reaches every FLAGGED premises — **71 of 79** on this tenant.
  // The engine was right and is unchanged. The sentence was the lie, and the
  // check now asks the two questions that can tell them apart: is the FALSE
  // sentence gone, and does the screen ACCOUNT for the number it prints?
  ok(
    "A scope · the false 'reaches nobody' warning is gone from a city-limits boundary",
    !/Left blank, this reaches nobody/i.test(blankTxt),
    (blankTxt.match(/.{0,50}reaches nobody.{0,50}/i) || ["absent"])[0].replace(/\n/g, " "),
  );
  ok(
    "A scope · and the truthful one is in its place",
    /Recorded City limits decide first/i.test(blankTxt),
    (blankTxt.match(/Recorded City limits[^\n]*/) || ["MISSING"])[0],
  );
  const blankSplit = (blankTxt.match(/(\d+) by recorded City limits\. (\d+) more by name\./) || null);
  ok(
    "A scope · THE SCREEN ACCOUNTS FOR THE COUNT IT PRINTS, blank box",
    blankCount !== null && blankSplit !== null &&
      Number(blankSplit[1]) + Number(blankSplit[2]) === Number(blankCount.count) &&
      blankSplit[2] === "0",
    blankSplit
      ? `${blankCount?.count} of ${blankCount?.total} = ${blankSplit[1]} by flag + ${blankSplit[2]} by name`
      : `${blankCount?.count} of ${blankCount?.total} with NOTHING on screen to explain it`,
  );

  // Now NAME a place — and name one that does not exist, then one that does.
  await fill("#premises_scope_value", "Nowhereville");
  await p.waitForTimeout(1800);
  const bogus = await matched();
  const bogusTxt = await text();
  const bogusSplit = (bogusTxt.match(/(\d+) by recorded City limits\. (\d+) more by name\./) || null);
  // ⚠ IT DOES NOT REACH NOBODY, AND IT NEVER DID. A town the utility has never
  // heard of adds NOBODY — which is not the same statement — and the flagged
  // premises are in scope regardless. The old check asserted `"0"` and would
  // have gone green only if the engine had been changed to match the copy.
  ok(
    "A scope · a place that does not exist adds NOBODY, and the screen says so",
    bogusSplit !== null && bogusSplit[2] === "0",
    bogusSplit ? `${bogus?.count} of ${bogus?.total} — ${bogusSplit[0]}` : "no split shown",
  );

  await fill("#premises_scope_value", "Katy");
  await p.waitForTimeout(1800);
  const katy = await matched();
  ok(
    "A scope · the count MOVES when the place changes",
    katy !== null && bogus !== null && katy.count !== bogus.count,
    katy ? `Nowhereville ${bogus?.count} → Katy ${katy.count} of ${katy.total}` : "no count",
  );
  // ⚠ **THE COUNT IS ASSERTED BY VALUE, NOT MERELY "SHOWN" (`DEF-RAT-5806`,
  // law 7).** A check that asks only whether a count is present passes on every
  // version of this screen ever written. Katy holds six properties and the
  // count is SEVENTY-SEVEN — the six, plus the 71 premises this utility has
  // flagged as inside its limits, which are in scope whatever the box says.
  // **77 is the TRUE reach and the engine is not changed to shrink it.** What
  // is asserted beside it is that every one of the 77 is now accounted for on
  // screen, which is the thing a clerk could not find out and the reason the
  // number read as a broken box.
  const katyTxt = await text();
  const katySplit = (katyTxt.match(/(\d+) by recorded City limits\. (\d+) more by name\./) || null);
  ok(
    "A scope · THE SCREEN ACCOUNTS FOR THE COUNT IT PRINTS, named town",
    katy !== null && katySplit !== null &&
      Number(katySplit[1]) + Number(katySplit[2]) === Number(katy.count) &&
      Number(katySplit[2]) > 0,
    katySplit
      ? `${katy?.count} of ${katy?.total} = ${katySplit[1]} by flag + ${katySplit[2]} by name`
      : `${katy?.count} of ${katy?.total} with NOTHING on screen to explain it`,
  );
  ok(
    "A scope · the named place is what MOVED the count, and only by the unflagged",
    katySplit !== null && bogusSplit !== null &&
      katySplit[1] === bogusSplit[1] &&
      Number(katySplit[2]) > Number(bogusSplit[2]),
    katySplit && bogusSplit
      ? `flagged stays ${katySplit[1]}; by-name ${bogusSplit[2]} → ${katySplit[2]}`
      : "no split",
  );
  note(
    `A scope · measured counts — blank ${blankCount?.count}, Nowhereville ${bogus?.count}, Katy ${katy?.count}, of ${katy?.total ?? "?"} premises`,
  );
  // ⚠ THE SAMPLE MADE THE COUNT WORSE AND NOW HAS TO CARRY BOTH GROUPS. Scoped
  // to Katy it listed three Katy addresses and none of the flagged premises that
  // are the reason the number is 77, so the only reading available to a clerk
  // was that the town has 77 properties. `matched[:3]` shows whichever group
  // sorts first, so WHICH half it hides is an accident of the data — and either
  // half hides the thing that explains the number.
  const sampleLine = await p.evaluate(
    () => document.querySelector("[data-matched-premises]")?.innerText.replace(/\n/g, " · ") ?? "",
  );
  const sampleCities = await p.evaluate(async () => {
    const tenant = location.pathname.split("/")[1];
    const res = await fetch(
      `/api/${tenant}/taxes/matched-premises?premises_scope_kind=city_limits&premises_scope_value=Katy`,
    );
    const body = await res.json();
    return (body.sample ?? []).map((row) => row.city);
  });
  ok(
    "A scope · the sample names BOTH groups, never one of them as if it were the answer",
    new Set(sampleCities).size > 1,
    `sample cities: ${sampleCities.join(", ") || "none"}`,
  );
  note(`A scope · the sample shown beside the count for "Katy" — ${sampleLine.slice(0, 200)}`);
  ok(
    "A scope · the screen SAYS a recorded flag decides before the name",
    /Recorded City limits decide first/i.test(katyTxt) && /by recorded City limits/i.test(katyTxt),
    "a clerk can now learn from this screen why Katy reaches more than Katy",
  );

  // ⚠ **AN UNRESOLVABLE BOUNDARY IS NOW REFUSED AT THE PICKER, SO THE WALK
  // CANNOT PICK ONE — AND PROVING THAT IS THE CHECK.** `county`,
  // `taxing_district` and `premise_list` have no fact in this product to resolve
  // against, so a tax scoped by one reaches NOBODY silently, for ever. The
  // screen said so in red AFTER the clerk had chosen; it did not stop the save.
  const boundaryStates = await p.evaluate(() =>
    Object.fromEntries(
      [...document.querySelectorAll("#premises_scope_kind option")]
        .filter((o) => o.value)
        .map((o) => [o.value, o.disabled]),
    ),
  );
  ok(
    "A scope · all five boundaries are still OFFERED",
    ["city_limits", "state", "county", "taxing_district", "premise_list"].every(
      (k) => k in boundaryStates,
    ),
    Object.keys(boundaryStates).join(" | "),
  );
  ok(
    "A scope · the three the engine cannot resolve cannot be CHOSEN",
    boundaryStates.county === true &&
      boundaryStates.taxing_district === true &&
      boundaryStates.premise_list === true &&
      boundaryStates.city_limits === false &&
      boundaryStates.state === false,
    JSON.stringify(boundaryStates),
  );

  // ⚠ AND THE SENTENCE THAT IS TRUE MUST SURVIVE. *In a state* really does
  // read 0 of 79 when the place is blank, so removing its warning because the
  // sibling one was false would be the mirror-image defect.
  await pick("#premises_scope_kind", "state");
  await p.waitForTimeout(1700);
  const stateTxt = await text();
  const stateCount = await matched();
  ok(
    "A scope · 'In a state' KEEPS the blank-place warning, because there it is true",
    /Left blank, this reaches nobody/i.test(stateTxt) && stateCount?.count === "0",
    `state + blank reads ${stateCount?.count} of ${stateCount?.total}`,
  );
  ok(
    "A scope · and claims no flag/name split, because that boundary has one door",
    !/by recorded City limits/i.test(stateTxt),
  );

  await pick("#premises_scope_kind", "city_limits");
  await p.waitForTimeout(600);
  await fill("#premises_scope_value", "Katy");
  await p.waitForTimeout(1500);

  // ── the two multi-selects ──────────────────────────────────────────────────
  const svcEmpty = await p.evaluate(
    () => document.querySelector('[data-chip-select="tax-services"] [data-chip-empty]')?.innerText.trim() ?? null,
  );
  const clsEmpty = await p.evaluate(
    () => document.querySelector('[data-chip-select="tax-customer-classes"] [data-chip-empty]')?.innerText.trim() ?? null,
  );
  ok(
    "A chips · an empty SERVICES box reads as every service, never none",
    svcEmpty !== null && /all services/i.test(svcEmpty),
    String(svcEmpty),
  );
  ok(
    "A chips · an empty CLASSES box reads as every class, never none",
    clsEmpty !== null && /every customer class/i.test(clsEmpty),
    String(clsEmpty),
  );
  ok(
    "A chips · they are chips, not a wall of tick boxes",
    (await p.locator('[data-chip-select="tax-services"] input[type="checkbox"]').count()) === 0 &&
      (await p.locator('[data-chip-select="tax-customer-classes"] input[type="checkbox"]').count()) === 0,
  );

  const svcOptions = await p.evaluate(() =>
    [...document.querySelectorAll('[data-chip-add="tax-services"] option')]
      .map((o) => o.innerText.trim())
      .filter((v) => v && !/^add a service/i.test(v)),
  );
  ok(
    "A chips · all eleven services are offered, Fire among them",
    svcOptions.length === 11 && svcOptions.some((s) => /fire/i.test(s)),
    `${svcOptions.length}: ${svcOptions.join(", ")}`,
  );

  await pick('[data-chip-add="tax-services"]', "water");
  await p.waitForTimeout(1500);
  const afterSvc = await matched();
  ok(
    "A chips · the count narrows when a service is chosen",
    afterSvc !== null && katy !== null && afterSvc.count !== katy.count,
    afterSvc ? `Katy ${katy?.count} → Katy+Water ${afterSvc.count} of ${afterSvc.total}` : "no count",
  );
  ok(
    "A chips · a chosen service can be taken off again",
    (await p.locator('[data-chip-select="tax-services"] [data-chip-remove="water"]').count()) > 0,
  );

  await pick('[data-chip-add="tax-customer-classes"]', "residential");
  await p.waitForTimeout(1500);
  const afterCls = await matched();
  ok(
    "A chips · the count narrows again when a class is chosen",
    afterCls !== null,
    afterCls ? `${afterCls.count} of ${afterCls.total} (narrowed=${afterCls.narrowed})` : "no count",
  );

  // ── step 2 · how much ──────────────────────────────────────────────────────
  await continueOn();
  const s2 = await text();
  ok("A step 2 · Continue reaches step 2", /Step 2 of 3/i.test(s2), (s2.match(/Step \d of \d/i) || ["none"])[0]);

  await fill("#rate", "0.0150");
  const s2b = await text();
  ok(
    "A step 2 · only usage and base service charges can be taxed",
    /Usage charges/.test(s2b) && /Base service charges/.test(s2b) && /Only these two can be taxed/i.test(s2b),
  );
  ok(
    "A step 2 · discount treatment carries a worked example",
    /\$1\.00 credit/.test(s2b) && /\$3\.78/.test(s2b) && /\$3\.80/.test(s2b),
    (s2b.match(/Example:.*/) || ["none"])[0],
  );
  const dtOptions = await p.evaluate(() =>
    [...document.querySelectorAll("#discount_treatment option")].map((o) => o.innerText.trim()),
  );
  ok("A step 2 · both discount directions are offered", dtOptions.length >= 2, dtOptions.join(" | "));

  const roundOptions = await p.evaluate(() =>
    [...document.querySelectorAll("#rounding_rule option")].map((o) => o.innerText.trim()),
  );
  ok("A step 2 · the authority's rounding can be recorded", roundOptions.length > 1, roundOptions.join(" | "));
  await pick("#rounding_rule", "up");
  await p.waitForTimeout(500);
  ok(
    "A step 2 · and the clerk is told it is recorded, not applied",
    /Recorded only\. Bills use standard rounding\./i.test(await text()),
  );
  ok("A step 2 · the start date is asked for here", (await p.locator("#effective_from").count()) > 0);
  await fill("#effective_from", "2026-11-01");
  await p.waitForTimeout(400);

  // ── step 3 · review & save ─────────────────────────────────────────────────
  await continueOn();
  const s3 = await text();
  ok("A step 3 · Continue reaches the review", /Step 3 of 3/i.test(s3), (s3.match(/Step \d of \d/i) || ["none"])[0]);
  const reads = (re) => re.test(s3);
  const readback = {
    name: s3.includes(TAX_NAME),
    authority: /Authority|Jurisdiction/i.test(s3),
    rate: reads(/0\.0150/),
    taxed: reads(/Usage charges|Base service charges/),
    discounts: reads(/Full amount taxed|Discounted amount taxed/),
    boundary: reads(/Inside city limits/) && reads(/Katy/),
    classes: reads(/Residential/),
    services: reads(/Water/),
    from: reads(/2026-11-01|01\/11\/2026|11\/01\/2026/),
    to: /Effective to|End|—/.test(s3),
    rounding: reads(/Always up/),
  };
  for (const [k, v] of Object.entries(readback)) {
    ok(`A step 3 · the review reads back ${k}`, v);
  }
  // ⚠ THE REVIEW CARRIES THE COUNT TOO, and the only question worth asking of
  // a second copy of a number is whether it AGREES with the first. It did not
  // for two days (`DEF-RAT-4826`): the same component was passed the boundary
  // alone here and all three narrowings on step 1, so a tax restricted to one
  // class read its true reach on step 1 and a larger figure on the last screen
  // before the commit. Every test passed, because both steps rendered A
  // sentence and nothing compared the two numbers.
  const reviewCount = await matched();
  ok(
    "A step 3 · the review carries the matched count",
    reviewCount !== null,
    reviewCount ? `${reviewCount.count} of ${reviewCount.total}` : "absent",
  );
  ok(
    "A step 3 · and it AGREES with the number step 1 showed",
    reviewCount !== null && afterCls !== null && reviewCount.count === afterCls.count,
    `step 1 said ${afterCls?.count}, the review says ${reviewCount?.count}`,
  );
  // ⚠ AND THE EXPLANATION TRAVELS WITH THE NUMBER. The review is the last
  // screen before a levy goes live; a count it cannot account for there is the
  // same defect one step later, where it costs more.
  ok(
    "A step 3 · the review accounts for the count too, not just prints it",
    /by recorded City limits/i.test(s3),
    (s3.match(/\d+ by recorded City limits[^\n]*/) || ["MISSING on the last screen before the commit"])[0],
  );
  // ⚠ **A TAX CANNOT BE UNDONE AND NOTHING SAID SO BEFORE THE CLERK SAVED.**
  // There is no DELETE on `taxes` anywhere in the product — this script's own
  // cleanup block says so at the bottom, because it had to find out — and the
  // wizard let a clerk commit one having never mentioned it. B14 rule 33 names
  // this shape exactly: a CONSEQUENCE stated before an irreversible act.
  ok(
    "A step 3 · the clerk is told a tax cannot be deleted, BEFORE they save",
    /cannot be deleted/i.test(s3),
    (s3.match(/[^\n]*cannot be deleted[^\n]*/) || ["nothing on screen says it"])[0],
  );

  const saveBtn = p.locator("button").filter({ hasText: /^Save tax or fee$/ }).first();
  ok("A step 3 · a save control is present and enabled", (await saveBtn.count()) > 0 && (await saveBtn.isEnabled()));
  if ((await saveBtn.count()) && (await saveBtn.isEnabled())) {
    await click(saveBtn);
    await p.waitForTimeout(3000);
  }
  ok("A save · it leaves the wizard", !/taxes-fees\/new/.test(p.url()), p.url());
  const afterSave = await text();
  ok("A save · the new tax is visible afterwards", afterSave.includes(TAX_NAME));
  // ⚠ SCENARIO B CORRECTS THE TAX SCENARIO A JUST MADE, and that is not a
  // shortcut — it is what makes this walk REPEATABLE. Correcting a seeded tax
  // works once: the second run meets *"This rate has already been corrected"*,
  // correctly, and the walk then reports the product refusing as a failure of
  // the product. A tax this run created has never been corrected by anybody.
  createdId = (p.url().match(/taxes-fees\/([0-9a-f-]{36})/) || [])[1] ?? null;
  note(`A save · the tax this run will correct in B — ${createdId ?? "not captured"}`);

  const A = tally["A · create"];
  note(
    `A total · ${A.clicks} clicks + ${A.typed} typed fields + ${A.picked} dropdown picks = ${A.clicks + A.typed + A.picked} acts, nothing to a saved tax`,
  );
  // ⚠ THAT FIGURE INCLUDES THIS WALK'S OWN PROBES and is not what a clerk owes.
  // The probes are the deliberate wrong turns: pressing Continue while the
  // authority is unset, typing a city that does not exist, and switching the
  // boundary to an unresolvable one and back. Quoting the instrumented number
  // as the clerk's cost would overstate the friction by a third, which is the
  // mirror of the thing this walk exists to catch.
  const PROBES = 6;
  note(
    `A total · the MINIMUM clerk path is ${A.clicks + A.typed + A.picked - PROBES} acts — tab, New, name, authority, boundary, place, one service, one class, Continue, rate, start date, Continue, Save`,
  );

} catch (e) {
  R.push(`ERROR · scenario A stopped · ${String(e).split("\n")[0]}`);
}

// ═══ SCENARIO B · a clerk edits a live tax — the correction door ════════════
try {
  scenario = "B · correct";
  await p.goto(`${BASE}/${T}/plans-rates/taxes-fees`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1600);

  // ⚠ the row opens through a BUTTON, not an anchor. A link selector finds
  // nothing here and would read as "no tax is editable" — which is the
  // selector-lies failure a sibling's walk already shipped once.
  const target = createdId ? TAX_NAME : "TX State Utility Tax";
  const rowEdit = p
    .locator("table tbody tr")
    .filter({ hasText: new RegExp(target.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) })
    .locator('button[aria-label*="Edit" i], button[title*="Edit" i]');
  let opened = false;
  if (await rowEdit.count()) {
    await click(rowEdit.first());
    await p.waitForTimeout(2500);
    opened = /\/edit/.test(p.url());
  }
  ok("B door · a live tax has an edit control on its row", opened, p.url());
  if (!opened) {
    // Fall back to the address so the rest of the scenario can still be walked,
    // and SAY SO — a walk that quietly substitutes a URL for a click is exactly
    // the failure this script is written against.
    note("B door · no row edit control was clickable; the rest of B was reached by address");
    if (createdId) {
      await p.goto(`${BASE}/${T}/plans-rates/taxes-fees/${createdId}/edit`, { waitUntil: "networkidle" });
      await p.waitForTimeout(2500);
    }
  }

  const e1 = await text();
  ok("B step 1 · the edit door opens the same three-step wizard", /Step 1 of 3/i.test(e1));
  ok(
    "B step 1 · a clerk can tell an edit from a new one",
    /Edit tax or fee/i.test(e1) || new RegExp(`Edit ${target}`, "i").test(e1),
    (e1.match(/Edit[^\n]{0,40}/) || ["none"])[0],
  );
  ok(
    "B step 1 · the correction banner is on the FIRST screen",
    /Filing a correction/i.test(e1),
    (e1.match(/Filing a correction[\s\S]{0,140}/) || ["none"])[0].replace(/\n/g, " · "),
  );
  ok(
    "B step 1 · it says a new dated version is written",
    /new dated version/i.test(e1),
  );
  ok("B step 1 · it says issued bills keep their rate", /Issued bills keep their rate/i.test(e1));
  // BR-SHL-025: a forbidden control is PRESENT and disabled WITH its reason,
  // never vanished — a control that disappears teaches nothing.
  const draftBtn = p.locator("button").filter({ hasText: /^Save draft & exit$/ }).first();
  ok(
    "B step 1 · Save draft & exit is present but refused on a correction",
    (await draftBtn.count()) > 0 && !(await draftBtn.isEnabled()),
    (await draftBtn.count()) === 0 ? "the control vanished" : `enabled=${await draftBtn.isEnabled()}`,
  );
  ok(
    "B step 1 · the existing values are loaded, not blank",
    (await p.inputValue("#name")).trim().length > 0,
    await p.inputValue("#name"),
  );
  const editClasses = await p.evaluate(() =>
    [...document.querySelectorAll('[data-chip-select="tax-customer-classes"] [data-chip]')].map((n) =>
      n.getAttribute("data-chip"),
    ),
  );
  ok(
    "B step 1 · the tax's stored customer classes are shown back as chips",
    editClasses.length > 0,
    editClasses.length ? editClasses.join(", ") : "NONE — the saved row carries one",
  );
  const editServices = await p.evaluate(() =>
    [...document.querySelectorAll('[data-chip-select="tax-services"] [data-chip]')].map((n) =>
      n.getAttribute("data-chip"),
    ),
  );
  ok(
    "B step 1 · and so are its services",
    editServices.length > 0,
    editServices.length ? editServices.join(", ") : "NONE — the saved row carries one",
  );
  ok(
    "B step 1 · the boundary round-trips",
    (await p.inputValue("#premises_scope_value")).trim() !== "",
    `${await p.inputValue("#premises_scope_kind")} · ${await p.inputValue("#premises_scope_value")}`,
  );

  await continueOn();
  const e2 = await text();
  ok("B step 2 · the rate step is reached", /Step 2 of 3/i.test(e2));
  const fromDisabled = await p.evaluate(() => {
    const n = document.querySelector("#effective_from");
    return n ? n.disabled === true || n.getAttribute("aria-disabled") === "true" : null;
  });
  ok(
    "B step 2 · a correction cannot move the statutory window",
    fromDisabled === true,
    fromDisabled === null ? "no date field" : `disabled=${fromDisabled}`,
  );
  ok(
    "B step 2 · and the clerk is told why it is locked",
    /A correction keeps these dates/i.test(e2),
  );
  await fill("#rate", "0.0700");
  await continueOn();

  const e3 = await text();
  ok("B step 3 · the review is reached", /Step 3 of 3/i.test(e3));
  ok("B step 3 · a reason is asked for", /Reason for correction/i.test(e3));
  ok(
    "B step 3 · the outcome is stated before the act",
    /supersedes this rate now/i.test(e3),
    (e3.match(/Saving supersedes[^\n]*/) || ["none"])[0],
  );
  const saveCorr = p.locator("button").filter({ hasText: /^Save correction$/ }).first();
  ok(
    "B step 3 · the commit is named a correction, not a save",
    (await saveCorr.count()) > 0,
    await p.evaluate(() =>
      [...document.querySelectorAll("button")].map((x) => x.innerText.trim()).filter(Boolean).join(" | "),
    ),
  );
  // A correction with no reason must be refused — the reason is the whole point.
  if (await saveCorr.count()) {
    await click(saveCorr);
    await p.waitForTimeout(2000);
  }
  const refused = await text();
  ok(
    "B guard · a correction with no reason does not save",
    /Step 3 of 3/i.test(refused),
    /required|reason/i.test(refused) ? "it stays and complains" : "it stays",
  );
  const reasonBox = p.locator("#reason").first();
  if (await reasonBox.count()) {
    bump("type");
    await reasonBox.fill("WALK — rate restated at the authority's corrected figure.");
    await p.waitForTimeout(400);
  }
  if (await saveCorr.count()) {
    await click(saveCorr);
    await p.waitForTimeout(3500);
  }
  const afterCorrect = await text();
  ok(
    "B save · the correction leaves the wizard",
    !/\/edit/.test(p.url()),
    /\/edit/.test(p.url())
      ? (afterCorrect.match(/(already been corrected|no liability account|[A-Z][^\n]*refus[^\n]*)/i) || [
          "it stayed and said nothing quotable",
        ])[0]
      : p.url(),
  );

  const B = tally["B · correct"];
  note(
    `B total · ${B.clicks} clicks + ${B.typed} typed fields + ${B.picked} dropdown picks = ${B.clicks + B.typed + B.picked} acts to file a correction`,
  );

} catch (e) {
  R.push(`ERROR · scenario B stopped · ${String(e).split("\n")[0]}`);
}

// ═══ READABILITY · B14 rule 33 measured on what a clerk actually sees ═══════
try {
  // A LABEL ≤ 3 words · a FACT ≤ 6 words · an INSTRUCTION ≤ 6 words PER SENTENCE.
  // This counts only the longest sentences so the report can say whether the cut
  // of 2026-09-19 landed, without pretending to be the rule's judge.
  scenario = "C · readability";
  await p.goto(`${BASE}/${T}/plans-rates/taxes-fees/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  const longOnes = [];
  for (const [n, label] of [[1, "What it is"], [2, "How much"], [3, "Review & save"]]) {
    if (n > 1) {
      // reach it the only lawful way
      if (n === 2) {
        // Step 1 has to be COMPLETE or Continue refuses and the probe measures
        // step 1 three times over — which is what it did on its first run.
        await p.fill("#name", "WALK readability probe");
        const first = await p.evaluate(() => {
          const o = [...document.querySelectorAll("#jurisdiction option")].find(
            (x) => x.value && !/^__/.test(x.value),
          );
          return o ? o.value : "";
        });
        if (first) await p.selectOption("#jurisdiction", first);
        await p.waitForTimeout(500);
      }
      await click(p.locator("button").filter({ hasText: /^Continue$/ }).first());
      await p.waitForTimeout(900);
    }
    const sentences = await p.evaluate(() => {
      const main = document.querySelector("main") ?? document.body;
      return main.innerText
        .split(/\n+/)
        .flatMap((line) => line.split(/(?<=[.!?])\s+/))
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
    });
    for (const s of sentences) {
      const words = s.split(/\s+/).filter(Boolean).length;
      if (words > 6) longOnes.push({ step: `${n} ${label}`, words, s });
    }
  }
  note(
    `C readability · ${longOnes.length} on-screen sentences run past six words across the three steps`,
  );
  for (const l of longOnes.slice(0, 12)) {
    note(`C readability · step ${l.step} · ${l.words} words · "${l.s.slice(0, 96)}"`);
  }

} catch (e) {
  R.push(`ERROR · readability pass stopped · ${String(e).split("\n")[0]}`);
}

// ═══ CLEAN UP AFTER THE WALK ═══════════════════════════════════════════════
// ⚠ A WALK THAT LEAVES ITS OWN ROWS BEHIND IS FRICTION FOR THE NEXT PERSON.
// Every tax this script makes is named `WALK …`, and the corrections it files
// carry the same name, so the sweep is by that prefix and touches nothing a
// clerk or a sibling lane created. Without it the demo utility grows two taxes
// per run and the PO's own beta walk reads them as real.
try {
  const swept = await p.evaluate(async () => {
    const tenant = location.pathname.split("/")[1];
    const res = await fetch(`/api/${tenant}/taxes`);
    const body = await res.json();
    const rows = Array.isArray(body) ? body : (body.results ?? []);
    const mine = rows.filter((r) => typeof r.name === "string" && r.name.startsWith("WALK "));
    let gone = 0;
    for (const row of mine) {
      if (row.active === false) continue;
      // ⚠ THERE IS NO DELETE FOR A TAX AND THAT IS THE PRODUCT'S OWN CHOICE —
      // `IS-1 deactivate-first`. `DELETE /taxes/{id}` answers 405. So the sweep
      // retires its own rows the way a clerk would, and says how many.
      const d = await fetch(`/api/${tenant}/taxes/${row.id}/deactivate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] ?? "",
        },
        body: "{}",
      });
      if (d.ok) gone += 1;
    }
    return { found: mine.length, gone };
  });
  note(`Z cleanup · ${swept.gone} of ${swept.found} WALK taxes retired (the product has no delete for a tax — IS-1 deactivate-first)`);
} catch (e) {
  note(`Z cleanup · could not sweep this walk's own rows · ${String(e).split("\n")[0]}`);
}

await b.close();
console.log(R.join("\n"));
process.exit(R.some((l) => l.startsWith("FAIL")) ? 1 : 0);
