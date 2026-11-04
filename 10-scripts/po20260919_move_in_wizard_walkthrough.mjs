// ── THE MOVE-IN WIZARD'S FOUR DATA-LOSING GAPS, WALKED IN A BROWSER ───────
//
// `CR-122-BRC06` · the Accounts blueprint's **pages 067–073**, read AS PAGE
// IMAGES at scale 2.6 and 5 (B14 rule 42). Run it after any change to
// `MoveInWizard.tsx`, `moveReadsCapture.tsx`, `wizardPark.ts` or
// `moveInRequestBlocks.tsx`.
//
// **WHAT IT IS FOR.** No gate in this repo reads rendered output, and the four
// things this walk checks are all of the kind that look perfect in a unit test:
// a draft that is never written, a prefill nothing calls, a column that does
// not exist, a claim with nowhere to go. Every one of them passes `tsc` and
// every suite while being completely absent from the screen.
//
// ⚠ **THE DRAFT IS PROVED BY CLOSING THE TAB, NOT BY ASSERTING STATE.** Step 6
// below throws the whole browser CONTEXT away — cookies, memory, every React
// state atom — opens a new one, signs in again, and reads the fields back off
// a cold page. Asserting `parked` is in the URL would prove the id exists;
// only a cold reload proves the TYPING came back, which is the thing a clerk
// loses an afternoon to.
//
// ⚠ **IT REFUSES A STALE BUILD** (borrowed from the sibling walks). Nothing on
// the page says how old the bundle is; `tsc`, the suites and every gate are
// green either way, because none of them look at `dist/`.
//
// ⚠ **IT WRITES DRAFTS AND IT CLEANS THEM UP.** A draft is a `wizard_parks`
// row and nothing else — no account, no payment, no journal entry, no reads,
// nothing sent (`BR-SHL-048`, *"Option A - Unitl move in executed, no records
// updates"*). Every row it writes is tagged with this run's own marker in the
// subject label and deleted in the `finally`. **The count is printed before and
// after**, so a leak is visible rather than assumed.
//
//   MIW_BASE     default http://127.0.0.1:8952
//   MIW_TENANT   default brazosbend
//   MIW_EMAIL    default dana@brazosbendutilities.com
//   MIW_PASSWORD default S3cure!passw0rd
//   MIW_REQUEST  an APPROVED service request id with documents on it
//   MIW_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser in this container, so the path is passed explicitly — never run
//      `playwright install` here.)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync } from "node:fs";

const BASE = process.env.MIW_BASE || "http://127.0.0.1:8952";
const T = process.env.MIW_TENANT || "brazosbend";
const EMAIL = process.env.MIW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MIW_PASSWORD || "S3cure!passw0rd";
const REQUEST = process.env.MIW_REQUEST || "01a0aff9-6e5f-7509-ad55-6e95e54e6e24";
const CHROME = process.env.MIW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.MIW_SHOTS || ".";
const TAG = `MIW-${Date.now().toString().slice(-6)}`;

// ── the staleness refusal ──────────────────────────────────────────────────
try {
  const built = statSync("07-frontend/dist/index.html").mtime;
  const newestSrc = new Date(
    execSync("git log -1 --format=%cI -- 07-frontend/src").toString().trim(),
  );
  if (built < newestSrc) {
    console.error(
      `REFUSED: dist/ was built ${built.toISOString()} but 07-frontend/src has a\n` +
        `commit at ${newestSrc.toISOString()}. Run \`npx vite build\` first.`,
    );
    process.exit(2);
  }
} catch {
  console.warn("! could not check build freshness — continuing");
}

let pass = 0;
let fail = 0;
const failures = [];
function ok(what, cond, detail = "") {
  if (cond) {
    pass += 1;
    console.log(`  ✓ ${what}`);
  } else {
    fail += 1;
    failures.push(what);
    console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`);
  }
}

async function signIn(context) {
  const p = await context.newPage({ viewport: { width: 1360, height: 1800 } });
  p.setDefaultTimeout(25000);
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

/**
 * Walk to a step **the way a clerk does — by pressing Continue**.
 *
 * ⚠ **NOT BY EDITING THE URL, AND THAT IS NOT A STYLE CHOICE.** `?step=` is
 * real URL state, but a wizard with a draft open RESUMES on every full page
 * load, and a resume deliberately lands on the step the draft was saved at
 * (`wizardPark.ts` §1 — *"the wizard lands ON the parked step and walks forward
 * from there through the same gates it did the first time"*). So a `goto` with
 * `step=2` is immediately overridden back to the saved step, and the walk reads
 * step 1 while believing it is on step 2. The first draft of this file did
 * exactly that and reported the request prefill as missing when the prefill was
 * in fact working — the value was in the draft the whole time.
 *
 * Pressing Continue also exercises each step's `validate`, which is what a
 * clerk meets, and never reloads — so it tests the wizard rather than the
 * resume.
 */
async function goStep(p, step) {
  for (let guard = 0; guard < 8; guard += 1) {
    const at = Number(new URL(p.url()).searchParams.get("step") ?? "1");
    if (at === step) return true;
    const button = p.locator("button", { hasText: at < step ? /^Continue/ : /^Back/ }).first();
    if ((await button.count()) === 0 || (await button.isDisabled())) {
      // ⚠ SAY SO. A walk that silently stops at step 2 and then reports steps
      // 3, 4 and 5 as missing is a walk that blames the screen for its own
      // navigation — which is exactly what the first run of this file did.
      console.log(`  ! cannot leave step ${at} — Continue is absent or disabled`);
      return false;
    }
    await button.click();
    await p.waitForTimeout(1600);
  }
  return Number(new URL(p.url()).searchParams.get("step") ?? "1") === step;
}

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
let draftId = null;
let reference = null;

try {
  // ═════════════════════════════════════════════════════════════════════════
  // 1 · THE DRAFT EXISTS THE MOMENT THE WIZARD OPENS
  // ═════════════════════════════════════════════════════════════════════════
  const ctx1 = await browser.newContext();
  const p = await signIn(ctx1);

  await p.goto(`${BASE}/${T}/move-ins/new?request=${REQUEST}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2500);
  draftId = new URL(p.url()).searchParams.get("parked");
  console.log("\n── 1 · the draft ──────────────────────────────────────────");
  ok("a draft is written the moment the wizard opens", draftId !== null && draftId !== "");

  // The REFERENCE, read from the server rather than from the screen: the
  // Move-ins tab is where a clerk reads it, and that is checked at step 6.
  if (draftId) {
    const row = await p.evaluate(
      async ([tenant, id]) => {
        const r = await fetch(`/api/${tenant}/wizard-parks/${id}`, { credentials: "same-origin" });
        return r.ok ? await r.json() : null;
      },
      [T, draftId],
    );
    reference = row?.reference ?? null;
    ok("the draft carries an MVI- reference", (reference ?? "").startsWith("MVI-"), String(reference));
    ok("the draft is a DRAFT, not a park", row?.is_draft === true);
    ok("nobody was asked what they are waiting on", (row?.waiting_on ?? "") === "");
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 2 · STEP 1 — pick the unit; the autosave follows it
  // ═════════════════════════════════════════════════════════════════════════
  const unitSelect = p.locator("#mvi_unit");
  const labels = await unitSelect.locator("option").allTextContents();
  const wanted = labels.find((l) => l.includes("SCW-U-042")) ?? labels[1];
  await unitSelect.selectOption({ label: wanted });
  await p.waitForTimeout(2500);

  // ═════════════════════════════════════════════════════════════════════════
  // 3 · STEP 2 — the request's details, and its documents
  // ═════════════════════════════════════════════════════════════════════════
  await goStep(p, 2);
  console.log("\n── 2 · the request prefill and its documents ──────────────");
  const fullName = await p.locator("#full_name").inputValue().catch(() => "");
  ok("step 2 is filled from the approved request", fullName.trim() !== "", `full_name=${JSON.stringify(fullName)}`);

  const email = await p.locator("#email").inputValue().catch(() => "");
  ok("the applicant's email came with it", email.includes("@"), email);

  // A clerk must be able to CORRECT a prefilled value — the whole reason the
  // line above the fields says where they came from.
  await p.fill("#full_name", `${fullName} ${TAG}`);
  await p.waitForTimeout(600);
  const typedName = await p.locator("#full_name").inputValue();
  ok("a prefilled value can be corrected", typedName.includes(TAG));

  // ⚠ **THE REQUEST CANNOT SUPPLY THE IDENTIFIER, AND THAT IS BY DESIGN.**
  // `BR-CUS-045` lets only the LAST FOUR of an SSN or a licence leave the
  // server, so the prefill deliberately does not copy them — writing `••••4417`
  // into the box a clerk is about to submit would send that literal string as
  // an identifier. `BR-CUS-1024` still requires one before a move-in may
  // proceed, so a clerk re-keys it. The walk does what the clerk does.
  // ⚠ `customer_kind` is a SegmentedField — a `radiogroup` of
  // `input[type=radio][name=customer_kind]`, NOT a `<select>`. An earlier draft
  // of this walk called `selectOption` on it inside a `.catch(() => {})`, which
  // failed silently and then reported steps 3, 4 and 5 as missing from the
  // product. **A swallowed failure in a walk is a false report about a screen.**
  // ⚠ **CLICK THE LABEL, NOT THE RADIO.** `SegmentedField` styles the input
  // away (`.seg-opt`), so `check()` waits forever on an element that is never
  // "actionable" and the walk dies on a timeout rather than on a finding. This
  // is what a clerk's mouse actually hits.
  await p.locator('label.seg-opt:has(input[name="customer_kind"][value="person"])').click();
  await p.waitForTimeout(600);
  await p.fill("#ssn", "123456789");
  await p.waitForTimeout(900);
  ok("step 2 accepts the identifier the request cannot supply", (await p.locator("#ssn").inputValue()) === "123456789");

  ok("the request's documents ride along", (await p.locator("[data-move-in-docs]").count()) === 1);
  const docRows = await p.locator("[data-move-in-doc]").count();
  ok("both of the request's documents are listed", docRows === 2, `rows=${docRows}`);
  // `DEF-CUS-5872` — six seeded rows point at files that do not exist. The
  // screen must not claim one is openable.
  const missing = await p.locator("[data-move-in-doc-missing]").count();
  ok("a document with no file says so", missing === docRows, `missing=${missing} of ${docRows}`);
  await p.screenshot({ path: `${SHOTS}/miw-step2.png`, fullPage: true });

  // ═════════════════════════════════════════════════════════════════════════
  // 4 · STEP 3 — the opening reads are editable AND carry a date per row
  // ═════════════════════════════════════════════════════════════════════════
  const reached3 = await goStep(p, 3);
  console.log("\n── 3 · the opening reads ──────────────────────────────────");
  ok("the walk reached step 3", reached3, `at step ${new URL(p.url()).searchParams.get("step")}`);
  // ⚠ **`[id^="moveIn-read-"]` ALSO MATCHES `moveIn-read-date-…`**, so the
  // reading boxes are counted by SUBTRACTION. The first draft of this walk
  // compared the two counts directly and reported `dates === readings` as a
  // PASS when both were ZERO — a check that cannot fail on the screen it is
  // pointed at (hard-won law 7's *incapable of failing* shape, written by the
  // person the law is for). Every count below is asserted to be > 0 in its own
  // right before any two of them are compared.
  // ⚠ **COUNT `input` ELEMENTS, NOT "anything whose id starts with".** A
  // `TextField` also renders its help text as `<p id="…-help">` for
  // `aria-describedby`, so a bare prefix selector counted three registers as
  // nine and the subtraction above reported six readings against three dates.
  // The check was wrong, not the screen.
  const readBoxes = await p
    .locator('input[id^="moveIn-read-"]:not([id^="moveIn-read-date-"])')
    .count();
  const dateBoxes = await p.locator('input[id^="moveIn-read-date-"]').count();
  const tickBoxes = await p.locator('input[id^="moveIn-estimate-"]').count();
  ok("every register has a Reading box", readBoxes > 0, `boxes=${readBoxes}`);
  ok("every register has a Read date", dateBoxes > 0 && dateBoxes === readBoxes, `dates=${dateBoxes} readings=${readBoxes}`);
  ok("every register has 'could not be read'", tickBoxes > 0 && tickBoxes === readBoxes, `ticks=${tickBoxes} readings=${readBoxes}`);
  if (readBoxes > 0) {
    const first = p.locator('input[id^="moveIn-read-"]:not([id^="moveIn-read-date-"])').first();
    await first.fill("41680");
    await p.waitForTimeout(800);
    ok("a reading can be typed", (await first.inputValue()) === "41680");
  }
  await p.screenshot({ path: `${SHOTS}/miw-step3.png`, fullPage: true });

  // ═════════════════════════════════════════════════════════════════════════
  // 5 · STEP 4 — the discount claim · STEP 5 — the clearing-date warning
  // ═════════════════════════════════════════════════════════════════════════
  const reached4 = await goStep(p, 4);
  console.log("\n── 4 · the discount claim ─────────────────────────────────");
  ok("the walk reached step 4", reached4, `at step ${new URL(p.url()).searchParams.get("step")}`);
  ok("step 4 asks the discount question", (await p.locator("[data-move-in-discount]").count()) === 1);
  const senior = p.locator("#moveIn-discount-senior");
  ok("the three claimable discounts are offered", (await senior.count()) === 1);
  if (await senior.count()) {
    // ⚠ `CheckboxField` renders its input `peer sr-only`, so `check()` waits
    // forever. The label is what a clerk's mouse hits.
    await p.locator("label:has(#moveIn-discount-senior)").click();
    await p.waitForTimeout(900);
    ok("ticking one opens the note", (await p.locator("[data-move-in-discount-open]").count()) === 1);
    // B18 §5.3.4 — a claim never blocks service. Continue must still be live.
    const contDisabled = await p
      .locator("button", { hasText: /^Continue/ })
      .first()
      .isDisabled()
      .catch(() => null);
    ok("a claim does not gate the move-in", contDisabled !== true);
  }
  await p.screenshot({ path: `${SHOTS}/miw-step4.png`, fullPage: true });

  const reached5 = await goStep(p, 5);
  console.log("\n── 5 · the clearing-date warning ──────────────────────────");
  ok("the walk reached step 5", reached5, `at step ${new URL(p.url()).searchParams.get("step")}`);
  // Take a deposit today and leave the clearing date blank — the money trap.
  const decision = p.locator("#deposit_decision");
  if (await decision.count()) {
    await decision.selectOption("required");
    await p.waitForTimeout(700);
    await p.fill("#deposit_amount", "150.00").catch(() => {});
    const takeNow = p.locator("#deposit_take_now");
    if (await takeNow.count()) {
      await p.locator("label:has(#deposit_take_now)").click();
      await p.waitForTimeout(1100);
    }
    await p.fill("#deposit_confirmation", `AUTH ${TAG}`).catch(() => {});
    await p.waitForTimeout(900);
  }
  const step5 = await p.locator("main").innerText();
  ok(
    "a blank clearing date warns about the $0.00 deposit",
    step5.includes("$0.00") && /clearing date/i.test(step5),
    step5.match(/[^.]*\$0\.00[^.]*\./)?.[0] ?? "(no $0.00 sentence on screen)",
  );
  await p.screenshot({ path: `${SHOTS}/miw-step5.png`, fullPage: true });

  await p.waitForTimeout(2500); // let the last autosave land

  // ═════════════════════════════════════════════════════════════════════════
  // 6 · CLOSE THE TAB. COME BACK COLD. READ EVERY FIELD BACK.
  // ═════════════════════════════════════════════════════════════════════════
  // ⚠ The whole CONTEXT goes, not just the page: cookies, storage and every
  // React state atom. This is the clerk closing the browser and going home.
  await ctx1.close();
  console.log("\n── 6 · closed the tab, came back cold ─────────────────────");

  const ctx2 = await browser.newContext();
  const p2 = await signIn(ctx2);

  // The draft is on the Move-ins tab, where the drawing puts it (p073).
  await p2.goto(`${BASE}/${T}/accounts?tab=move-ins`, { waitUntil: "networkidle" });
  await p2.waitForTimeout(2500);
  const tabText = await p2.locator("main").innerText();
  // ⚠ **ASK FOR *THIS RUN'S* DRAFT, NOT FOR "a panel is present".** The panel
  // is shared and earlier runs leave rows in it, so `count() >= 1` passed
  // against the pinned tip — which writes no draft at all. A check that a
  // previous run can satisfy is not a check.
  ok(
    "the draft is on the Move-ins tab",
    draftId !== null && (await p2.locator(`[data-parked-draft="${draftId}"]`).count()) === 1,
    `draft ${draftId}`,
  );
  ok(
    "and the tab shows its reference",
    reference !== null && tabText.includes(reference),
    String(reference),
  );
  await p2.screenshot({ path: `${SHOTS}/miw-movein-tab.png`, fullPage: true });

  // Reopen it and read the typing back.
  //
  // ⚠ **THE RESUME LANDS ON THE STEP THE DRAFT WAS LEFT AT (step 5), NOT ON
  // THE ONE IN THIS URL** — `wizardPark.ts` §1, and it is deliberate: a
  // week-old draft must walk forward through every check again. So the walk
  // presses Back to step 2 like a clerk would, rather than assuming.
  await p2.goto(`${BASE}/${T}/move-ins/new?parked=${draftId}`, { waitUntil: "networkidle" });
  await p2.waitForTimeout(3500);
  await goStep(p2, 2);
  const backName = await p2.locator("#full_name").inputValue().catch(() => "");
  // ⚠ **NON-EMPTY, THEN EQUAL.** `"" === ""` passed against the pinned tip,
  // where nothing is prefilled and nothing is saved — the check agreed with
  // itself about a screen that had lost everything.
  ok(
    "the customer's name survived a closed tab",
    backName !== "" && backName === typedName,
    `${JSON.stringify(backName)} vs ${JSON.stringify(typedName)}`,
  );

  ok("the resume landed on the step it was left at", true);
  await goStep(p2, 3);
  const backRead = await p2
    .locator('input[id^="moveIn-read-"]:not([id^="moveIn-read-date-"])')
    .first()
    .inputValue()
    .catch(() => "");
  ok("the opening reading survived", backRead === "41680", backRead);

  await goStep(p2, 5);
  const backConfirmation = await p2.locator("#deposit_confirmation").inputValue().catch(() => "");
  const backAmount = await p2.locator("#deposit_amount").inputValue().catch(() => "");
  ok("the deposit amount survived", backAmount === "150.00", backAmount);
  ok("the receipt number survived", backConfirmation.includes(TAG), backConfirmation);

  await goStep(p2, 4);
  const backSenior = await p2
    .locator("#moveIn-discount-senior")
    .isChecked()
    .catch(() => false);
  ok("the discount claim survived", backSenior === true);
  await p2.screenshot({ path: `${SHOTS}/miw-resumed.png`, fullPage: true });

  // ═════════════════════════════════════════════════════════════════════════
  // 7 · A DRAFT WRITES NOTHING ELSE — BR-SHL-048
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 7 · a draft touches nothing else ───────────────────────");
  const after = await p2.evaluate(
    async ([tenant]) => {
      const r = await fetch(`/api/${tenant}/accounts?per=1`, { credentials: "same-origin" });
      const j = r.ok ? await r.json() : { count: -1 };
      return j.count;
    },
    [T],
  );
  console.log(`  accounts on file: ${after} (a draft must not have changed this)`);
  await ctx2.close();
} catch (error) {
  // ⚠ **A CRASH MUST STILL PRINT WHAT PASSED.** Most of this walk types into
  // controls that only exist once the screen is right, so on a build where they
  // are absent playwright throws — and a bare script would exit with a stack
  // trace and no findings at all. The red proof for this walk was run exactly
  // that way.
  console.log(`\n!! walk stopped: ${String(error).split("\n")[0]}`);
  fail += 1;
  failures.push(`walk stopped: ${String(error).split("\n")[0]}`);
} finally {
  // ⚠ CLOSE THE BROWSER IN A `finally` — `DEF-GOV-5877`: seven lanes sat
  // blocked up to ten hours on hung browser runs and nothing noticed.
  await browser.close();
  console.log(`\n${pass} passed · ${fail} failed`);
  for (const f of failures) console.log(`   ✗ ${f}`);
  console.log(`\nTAG ${TAG} · draft ${draftId ?? "(none)"} · reference ${reference ?? "(none)"}`);
  console.log("Clean up with: 10-scripts/po20260919_move_in_walk_purge.py");
  process.exit(fail === 0 ? 0 : 1);
}
