// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 2 wave E — THE STARTING-SERVICE WIZARDS.
//          `DEF-CUS-5082` (a gated field with no mark) · `DEF-CUS-5083` (the
//          one wizard of five whose step was not URL state) · B14 rule 39's
//          field anatomy on all five, and rule 40's 32px title.
// Purpose: STEP 2 PROVES. Every case below was shown RED against the tip this
//          wave started from (`f1f2f7fd0` / `2.239.0`) before it was trusted
//          green, and the RED output is quoted in the conformance document.
// Rules:   hard-won law 6 (no gate in this repo reads rendered output) · law 7
//          (prove a guard RED first, and in the harness that will run it) ·
//          law 7 habit 3 (the output must distinguish pass from fail TO A
//          READER, so every line says what it expected) · PO 2026-09-10
//          (clerk screens are verified at 1280 and 1440, nothing narrower) ·
//          PO 2026-09-12 (*"dont create duplcate code"* — the field probe is
//          IMPORTED from `render-checks/lib/fieldAnatomy.mjs`, not copied).
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY IT ASSERTS AND DOES NOT NARRATE.** `cr094_lane3_starting_service_
// walkthrough.mjs` is step 1's INVENTORY and correctly exits 0 whatever it
// finds. That shape is a check that cannot fail (law 7, second shape), which is
// right for identifying and wrong for proving. This one exits non-zero on any
// failed case and prints the expectation beside the reading on every line.
//
// ⚠ **THE STEP COUNT IS READ OFF THE RAIL THE BROWSER PAINTED**, never off the
// URL — four of these five wizards clamp `?step=` silently, so asking for a
// step and believing the answer invents one. The rail is the numbered cells in
// `[data-wizard-rail]`, falling back to the buttons that carry a step number.
//
// HOW TO RUN IT
//
//   06-backend  $ DJANGO_SETTINGS_MODULE=config.settings.local \
//                 DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub \
//                 python3 manage.py runserver 127.0.0.1:8660 --noreload
//   07-frontend $ npx vite build && PORT=8661 API_PROXY_TARGET=http://127.0.0.1:8660 node server.mjs
//   repo root   $ BASE=http://127.0.0.1:8661 node 10-scripts/cr094_wave_e_walkthrough.mjs
//
// ⚠ **IT WRITES ONE RECORD, ON PURPOSE.** The capture wizard is walked end to
// end and a real service request is created, because a wizard proved one step
// at a time is not proved (`CR-094` PROVE IT). The request number it creates is
// printed so it can be read back from PostgreSQL with `app.tenant_id` set.
import { existsSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { PROBE, RULE } from "./render-checks/lib/fieldAnatomy.mjs";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8661";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const ACCOUNT = process.env.ACCOUNT ?? "01a08ad4-2e4d-7764-8f2f-29b8e825d4ac";
const OUT = process.env.OUT ?? "/tmp/cr094-wave-e";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      for (const c of [
        join(root, dir, "chrome-linux", "chrome"),
        join(root, dir, "chrome-linux64", "chrome"),
        join(root, dir, "chrome-linux", "headless_shell"),
      ]) {
        if (existsSync(c)) return c;
      }
    }
  }
  throw new Error("no chromium found");
}

const lines = [];
let failures = 0;
let checks = 0;
const say = (s) => {
  console.log(s);
  lines.push(s);
};
function check(pass, label, saw, expected) {
  checks += 1;
  if (!pass) failures += 1;
  say(`  ${pass ? "ok  " : "FAIL"} ${label}`);
  say(`       saw ${JSON.stringify(saw)} · expected ${expected}`);
}

/** The rail and caption the browser painted, plus the required marks. */
const SCREEN = () => {
  const text = (el) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
  const h1 = document.querySelector("h1");
  const railCells = Array.from(document.querySelectorAll("[data-wizard-rail] [data-step]"));
  const rail =
    railCells.length > 0
      ? railCells.map(text)
      : Array.from(document.querySelectorAll("button"))
          .map(text)
          .filter((s) => /^\d+[A-Z]/.test(s));
  return {
    url: location.pathname + location.search,
    h1: text(h1),
    h1FontSize: h1 ? getComputedStyle(h1).fontSize : null,
    caption: (document.body.innerText.match(/Step\s+\d+\s+of\s+\d+/) || [null])[0],
    rail,
    railCount: rail.length,
    // B14 rule 10 — the mark is on the LABEL and `aria-required` on the control.
    marked: Array.from(document.querySelectorAll(".field")).map((f) => ({
      label: text(f.querySelector(":scope > label")),
      asterisk: f.querySelector(".field-required") !== null,
      ariaRequired:
        f.querySelector("[aria-required='true']") !== null ||
        f.querySelector("input[required], select[required], textarea[required]") !== null,
    })),
    blocked: text(document.querySelector("[data-wizard='blocked']")) || null,
    ariaInvalid: document.querySelectorAll("[aria-invalid='true']").length,
  };
};

const browser = await chromium.launch({ executablePath: resolveChromium() });
let createdRequestNo = null;

for (const width of [1280, 1440]) {
  const page = await browser.newPage({ viewport: { width, height: 1400 } });
  page.on("pageerror", (e) => {
    failures += 1;
    say(`  FAIL page error: ${e.message}`);
  });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  say(`\n############################ WIDTH ${width} ############################`);

  // ── DEF-CUS-5083 · the capture's step IS URL state ──────────────────────
  // RED BEFORE THE FIX: every one of these painted `Step 1 of 6`, because the
  // page held the step in component state and read `useSearchParams` for
  // `?request=` only. The blueprint draws six addresses (pages 75–79) and a
  // link to any of them landed the clerk on step 1, with every `toContain` on
  // the href passing.
  say(`\n== DEF-CUS-5083 · /requests/new?step=N is honoured ==`);
  for (const step of [1, 2, 3, 4, 5, 6]) {
    await page.goto(`${BASE}/${TENANT}/requests/new?step=${step}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    const s = await page.evaluate(SCREEN);
    check(s.caption === `Step ${step} of 6`, `?step=${step} paints its own step`, s.caption, `"Step ${step} of 6"`);
    check(s.url === `/${TENANT}/requests/new?step=${step}`, `?step=${step} stays in the address bar`, s.url, `"/${TENANT}/requests/new?step=${step}"`);
  }
  // out of range CLAMPS, it never errors (BR-SHL-011's spirit)
  for (const [asked, want] of [["7", "Step 6 of 6"], ["0", "Step 1 of 6"], ["banana", "Step 1 of 6"]]) {
    await page.goto(`${BASE}/${TENANT}/requests/new?step=${asked}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(400);
    const s = await page.evaluate(SCREEN);
    check(s.caption === want, `?step=${asked} clamps rather than errors`, s.caption, `"${want}"`);
  }

  // ── DEF-CUS-5082 · the gated category group carries its mark ────────────
  // RED BEFORE THE FIX: the group rendered no asterisk, no `required` and no
  // `aria-required`, and pressing Continue with a name typed showed *"Fill in
  // what's marked above"* with `[aria-invalid=true]` count 0 — the exact case
  // `WizardFrame` warns about in its own comment.
  say(`\n== DEF-CUS-5082 · the category group is MARKED, so the refusal is true ==`);
  await page.goto(`${BASE}/${TENANT}/requests/new?step=1`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  let s = await page.evaluate(SCREEN);
  const category = s.marked.find((f) => /categor/i.test(f.label));
  check(category !== undefined, "the category group is a .field with a label", category?.label ?? null, "a labelled field");
  check(category?.asterisk === true, "its label carries the asterisk (rule 10)", category?.asterisk, "true");
  check(category?.ariaRequired === true, "its radiogroup carries aria-required", category?.ariaRequired, "true");
  // and the one field the drawing marks that we deliberately do NOT mark
  const channel = s.marked.find((f) => /reach us/i.test(f.label));
  check(channel?.asterisk === false, "channel is NOT marked — it cannot be empty", channel?.asterisk, "false");

  // the refusal now points at a mark that exists
  await page.fill("#applicant_name", "Wave E Probe");
  await page.evaluate(() => {
    const b = Array.from(document.querySelectorAll("button")).find(
      (x) => /^continue/i.test((x.textContent || "").trim()) && !x.disabled,
    );
    b?.click();
  });
  await page.waitForTimeout(600);
  s = await page.evaluate(SCREEN);
  check(s.caption === "Step 1 of 6", "Continue is still refused with no category", s.caption, '"Step 1 of 6"');
  const stillMarked = s.marked.find((f) => /categor/i.test(f.label));
  check(
    s.blocked !== null && stillMarked?.asterisk === true,
    "the refusal is shown AND a marked field is on screen",
    { blocked: s.blocked, markedCategory: stillMarked?.asterisk },
    "a blocked sentence with at least one marked field present",
  );

  // ── B14 rule 40 · the page-head title is 32px on all five ───────────────
  say(`\n== B14 rule 40 · the page-head title is 32px ==`);
  const screens = [
    ["03 new account", `/${TENANT}/accounts/new`, 6],
    ["04 move-in", `/${TENANT}/accounts/${ACCOUNT}/move-in`, 5],
    ["05 move-in standalone", `/${TENANT}/move-ins/new`, 5],
    ["06 request capture", `/${TENANT}/requests/new`, 6],
    ["07 new connect", `/${TENANT}/connections/new`, 9],
  ];
  for (const [name, path, wantRail] of screens) {
    await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(700);
    const m = await page.evaluate(SCREEN);
    check(m.h1FontSize === "32px", `${name}: h1 is 32px`, m.h1FontSize, '"32px"');
    check(m.railCount === wantRail, `${name}: the rail the browser painted`, m.railCount, `${wantRail} cells`);
  }

  // ── The standalone move-in's later steps are a REFUSAL, not a blank ─────
  say(`\n== screen 05 · the standalone's later steps state what they are waiting for ==`);
  for (const step of [2, 3, 5]) {
    await page.goto(`${BASE}/${TENANT}/move-ins/new?step=${step}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(600);
    const seen = await page.evaluate(() => ({
      note: /Choose the unit above first/.test(document.body.innerText),
      fields: document.querySelectorAll("main .field").length,
      railCells: Array.from(document.querySelectorAll("button"))
        .map((b) => (b.textContent ?? "").trim())
        .filter((x) => /^\d+[A-Z]/.test(x)).length,
    }));
    check(seen.note, `?step=${step} SAYS what it is waiting for rather than drawing a blank`, seen, "the pick-first sentence on screen");
    check(seen.railCells === 5, `?step=${step} keeps all five rail cells (BR-SHL-046)`, seen.railCells, "5");
  }

  // ── B14 rule 39 · the field anatomy ─────────────────────────────────────
  // ⚠ **MOVE-IN IS MEASURED ON STEP 2, NOT STEP 1, AND THAT IS NOT A DODGE.**
  // Its step 1 renders NO field at all — the unit comes from the account in the
  // URL and the step is one stated absence (`Kept from the last tenancy`), which
  // step 1's inventory recorded. Measuring an empty screen and calling the
  // result clean is law 7's fifth shape; the Customer step is where its fields
  // are, so that is the address measured, and this note is why.
  say(`\n== B14 rule 39 · label→${RULE.labelToInput} input→${RULE.inputToHelp} helper, field→field ${RULE.fieldToField} ==`);
  const spacingScreens = [
    ["03 new account", `/${TENANT}/accounts/new?step=1`],
    ["04 move-in step 2", `/${TENANT}/accounts/${ACCOUNT}/move-in?step=2`],
    // ⚠ **THE STANDALONE MOVE-IN IS MEASURED ON STEP 1, AND ITS LATER STEPS
    // ARE ASSERTED AS A REGISTERED REFUSAL INSTEAD — see below.** Entered with
    // no account, `outgoing` is null and `MoveInWizard` deliberately renders
    // every step after the first as one sentence: *"Choose the unit above
    // first — the rest of the move-in is about it."* The rail keeps all five on
    // purpose (BR-SHL-046: the step number is an INDEX, so a vanishing step
    // would misaddress every step after it). **A first draft of this script
    // asserted `fields > 0` there and FAILED** — which is `CR-094` §5(b)
    // exactly: *a held control and a broken control look identical on screen*.
    // Asserting fields on a screen designed to have none is the mistake, not
    // the screen.
    ["05 move-in standalone step 1", `/${TENANT}/move-ins/new?step=1`],
    ["06 request capture", `/${TENANT}/requests/new?step=1`],
    ["07 new connect", `/${TENANT}/connections/new?step=1`],
    ["07 new connect step 3", `/${TENANT}/connections/new?step=3`],
  ];
  for (const [name, path] of spacingScreens) {
    await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(700);
    const probe = await page.evaluate(PROBE, "main");
    if (probe.error !== undefined) {
      check(false, `${name}: the probe found its scope`, probe.error, "an element matching main");
      continue;
    }
    // An empty list and a clean list look identical — refuse it (law 7).
    check(probe.fields.length > 0, `${name}: fields were found at all`, probe.fields.length, "> 0");
    if (probe.fields.length === 0) continue;
    const withHelp = probe.fields.filter((f) => f.hasHelp);
    const adjacent = probe.fields.filter((f) => f.fieldToField !== null);
    const order = new Set(withHelp.map((f) => f.paintedOrder));
    say(`  -- ${name}: ${probe.fields.length} fields (${probe.hidden.length} hidden, excluded) · ${withHelp.length} with a helper · ${adjacent.length} adjacent pairs`);
    say(`     painted order of helper fields: ${JSON.stringify([...order])}`);
    say(`     label→input : ${JSON.stringify([...new Set(probe.fields.map((f) => f.labelToInput))].sort((a, b) => a - b))}`);
    say(`     input→helper: ${JSON.stringify([...new Set(withHelp.map((f) => f.inputToHelp))].sort((a, b) => a - b))}`);
    say(`     field→field : ${JSON.stringify([...new Set(adjacent.map((f) => f.fieldToField))].sort((a, b) => a - b))}`);
    // ⚠ **HALF A PIXEL OF TOLERANCE, AND SAYING WHY MATTERS MORE THAN THE
    // NUMBER.** `getBoundingClientRect` returns FRACTIONAL coordinates, so a
    // box-to-box distance of exactly 20px can read 19.99 when the field above
    // it happens to end on a fractional pixel — the same field read −0.01px
    // before the fix, which is the same −0.01 offset with no margin under it.
    // Exact equality would fail on the browser's sub-pixel layout rather than
    // on a spacing decision, which is a check failing for the wrong reason.
    // **What would make this pass wrongly?** Nothing this defect is about: the
    // readings it was written for were 0px and 12px, and 0.5px cannot hide
    // either. A tolerance wide enough to hide a scale step would be the bug.
    const offScale = adjacent.filter(
      (x) => Math.abs(x.fieldToField - RULE.fieldToField) > 0.5,
    );
    for (const f of offScale) {
      say(`     OFF-SCALE   ${JSON.stringify(f.label)} → next field ${f.fieldToField}px (parent gap ${f.parentGap}, display ${f.parentDisplay})`);
    }
    // ⚠ **THE SKIPPED COUNT IS PRINTED BESIDE THE CHECKED COUNT** (law 7's
    // fifth shape — a declared blind spot with no number attached is
    // indistinguishable from an empty one). A field with no `.field` sibling
    // below it, or one sitting side by side in a grid row, has no
    // field-to-field distance at all and is not a pass.
    check(
      offScale.length === 0,
      `${name}: every adjacent pair is ${RULE.fieldToField}px ±0.5 (${adjacent.length} measured, ${probe.fields.length - adjacent.length} have no pair below them)`,
      offScale.map((f) => `${f.label}=${f.fieldToField}px`),
      "[]",
    );
    check(
      withHelp.every((f) => f.labelToInput === RULE.labelToInput && f.inputToHelp === RULE.inputToHelp),
      `${name}: label→input ${RULE.labelToInput} and input→helper ${RULE.inputToHelp} on all ${withHelp.length} helper fields`,
      withHelp.map((f) => `${f.label}=${f.labelToInput}/${f.inputToHelp}`),
      `all ${RULE.labelToInput}/${RULE.inputToHelp}`,
    );
    check(
      [...order].every((o) => o === "LABEL > INPUT > HELP"),
      `${name}: the painted order is label → input → helper`,
      [...order],
      '["LABEL > INPUT > HELP"]',
    );
  }
  await page.close();
}

// ── The whole path, once: a real service request, created end to end ───────
// A wizard proved one step at a time is not proved. This walks all six steps of
// the capture at 1280 and presses Submit, so the fix is exercised on the path a
// clerk actually takes rather than on six separate page loads.
say(`\n== THE WHOLE PATH · the capture walked end to end, and a record written ==`);
{
  const page = await browser.newPage({ viewport: { width: 1280, height: 1400 } });
  page.on("pageerror", (e) => {
    failures += 1;
    say(`  FAIL page error: ${e.message}`);
  });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  await page.goto(`${BASE}/${TENANT}/requests/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);

  const fill = async (sel, value) => {
    if (await page.locator(sel).count()) {
      await page.fill(sel, value);
      return true;
    }
    return false;
  };
  const pickRadio = async (name, label) => {
    return page.evaluate(
      ([n, l]) => {
        const wanted = Array.from(document.querySelectorAll(`input[name="${n}"]`)).find(
          (i) => (i.closest("label")?.textContent ?? "").trim() === l,
        );
        if (!wanted) return false;
        wanted.click();
        return true;
      },
      [name, label],
    );
  };
  const advance = async () =>
    page.evaluate(() => {
      const b = Array.from(document.querySelectorAll("button")).find(
        (x) => /^continue/i.test((x.textContent || "").trim()) && !x.disabled,
      );
      if (!b) return false;
      b.click();
      return true;
    });

  for (let step = 1; step <= 6; step += 1) {
    const m = await page.evaluate(SCREEN);
    say(`  -- painted ${m.caption} · ${m.url}`);
    check(m.caption === `Step ${step} of 6`, `the walk is on step ${step}`, m.caption, `"Step ${step} of 6"`);
    if (step === 1) {
      check(await pickRadio("account_type_code", "Residential"), "the category can be chosen", true, "true");
      await fill("#applicant_name", "Wave E Probe");
      await fill("#applicant_email", "wave-e@example.com");
      await fill("#applicant_phone", "(512) 555-0142");
    }
    if (step === 3) {
      // ⚠ **THE FIELD IS `#address_as_given`, AND THE STEP-1 INSTRUMENT NAMED
      // FOUR IDS THAT DO NOT EXIST.** `cr094_lane3_walk_and_measure.mjs` fills
      // `#service_address_line1`, `#service_city`, `#service_postal_code` and
      // `#unit_count`; step 3 renders `address_as_given`,
      // `address_unit_as_given`, `plot_or_parcel`, `what_is_being_built`,
      // `billing_address_same` and `billing_address_as_given` and NONE of those
      // four. Its `fill()` helper returns false silently when a selector
      // matches nothing, so the walk looked like it was typing and was not —
      // and because the same script also never got past step 1, nothing ever
      // exposed it. `validate()` here is `address_as_given.trim() !== ""`.
      const typed = await fill("#address_as_given", "212 Balcones Drive");
      check(typed, "step 3's service-address field exists under the id used", typed, "true");
      await fill("#address_unit_as_given", "Apt 4");
    }
    if (step === 6) break;
    // ⚠ **ASSERT THE STEP MOVED, NOT THAT A BUTTON WAS CLICKED.** The first
    // version of this check reported `Continue was offered on step 4 · saw
    // true` on a click that changed nothing, because `advance()` answers *"was
    // there an enabled Continue and did I click it"* — a different question
    // from *"did the wizard advance"*. That is law 7's second shape written by
    // this lane's own hand, so the fix is kept visible: the caption is read
    // AFTER the click and compared, and the wizard's own refusal sentence is
    // printed when it has not moved.
    const clicked = await advance();
    check(clicked, `an enabled Continue exists on step ${step}`, clicked, "true");
    if (!clicked) break;
    await page.waitForTimeout(1400);
    const after = await page.evaluate(SCREEN);
    if (after.caption === `Step ${step} of 6`) {
      check(false, `Continue MOVED the wizard off step ${step}`, {
        caption: after.caption,
        refusal: after.blocked,
      }, `"Step ${step + 1} of 6"`);
      break;
    }
  }
  const m6 = await page.evaluate(SCREEN);
  createdRequestNo = await page.evaluate(
    () => (document.body.innerText.match(/SR-\d{2}-\d{4}/) || [null])[0],
  );
  say(`  request number on screen: ${JSON.stringify(createdRequestNo)}`);
  check(createdRequestNo !== null, "the draft was numbered by the server", createdRequestNo, "an SR-nn-nnnn number");
  void m6;
  await page.close();
}

await browser.close();
say(`\n${checks - failures}/${checks} checks passed · ${failures} FAILED`);
if (createdRequestNo !== null) {
  say(`read it back:  set app.tenant_id then  select request_no, status, applicant_name, account_type_id from service_requests where request_no = '${createdRequestNo}';`);
}
writeFileSync(join(OUT, "wave-e.txt"), lines.join("\n"));
say(`wrote ${join(OUT, "wave-e.txt")}`);
process.exit(failures === 0 ? 0 : 1);
