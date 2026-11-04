// ── Trace ──────────────────────────────────────────────
// Screens:  the DISCONNECT WIZARD, all four steps, against the drawings made
//           for this rebuild — `Step1Choose.png` `Step2Check.png`
//           `Step3Schedule.png` `Step4Confirm.png` and the four master
//           variants `MasterStep1.png` … `MasterStep4.png`.
// Rules:    B14 rule 42 (a screen is built from the drawing AS AN IMAGE) ·
//           rule 44 (the drawing says WHAT is on the screen; our token scale,
//           spacing and component kit say HOW, and win) · rule 43 (a piece of
//           UI is a COMPONENT) · rule 37 (a drawn figure is an ILLUSTRATION) ·
//           rule 33 (RATIONALE is ZERO words on screen) · rule 31 (no database
//           id is a visible value) · **BR-CUS-1096** · **BR-CUS-1099** ·
//           **BR-CUS-1100** · CLAUDE.md hard-won law 6 — diffing the running
//           app against the drawing is the ONLY check in this repository that
//           reads rendered output, and it is a person.
// ───────────────────────────────────────────────────────
//
//   BASE=http://127.0.0.1:<your port> node 10-scripts/def_cus_6750_four_step_disconnect_walkthrough.mjs
//
// ⚠ **READ-ONLY, AND IT SAYS SO RATHER THAN CLAIMING IT.** Scheduling a cut is
// a real act against a named customer. This walk OPENS the four steps, types
// what each needs so the next one has something to show, reads the DOM and
// photographs it. **Nothing is submitted and nothing is parked.**
//
// ⚠ **WHAT THIS CAN AND CANNOT TELL YOU.** It reads the DOM, so it answers *is
// the row there, in the drawn order, spelled as drawn* — the half no unit test
// in this repo answers, because none renders to a browser. It does NOT measure
// spacing, weight or colour; the screenshots are for a PERSON to put beside the
// PNG, which is the other half of law 6 and has no tool.
//
// ⚠⚠ **IT MD5s THE SHOTS AND FAILS ON A DUPLICATE, AND THAT IS NOT PARANOIA.**
// A sibling lane captured wizard steps 4 and 5 and got byte-identical
// screenshots OF STEP 3, because `Continue` silently no-opped on an empty
// required date and the walk photographed the same screen twice under two
// names. Every assertion it then made about "step 4" was true of step 3. **A
// check that cannot tell which screen it is looking at is hard-won law 7's
// *looking at the wrong thing* shape**, and the cure is three lines of hashing.
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8972";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/disconnect-four";
// A REGULAR account and a MASTER, both real rows on the seeded tenant.
// Overridable, because the seed moves.
const ACCOUNT = process.env.ACCOUNT ?? "";
const MASTER = process.env.MASTER ?? "";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

let failures = 0;
const check = (label, ok, detail = "") => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
};

/** ⚠ **THE DUPLICATE-SHOT GUARD.** See the header: two captures of two steps
 *  that hash the same are one screen photographed twice. */
const seen = new Map();
function recordShot(path, label) {
  const digest = createHash("md5").update(readFileSync(path)).digest("hex");
  const first = seen.get(digest);
  if (first !== undefined) {
    check(`${label} is a DIFFERENT screen from ${first}`, false, `identical md5 ${digest}`);
    return;
  }
  seen.set(digest, label);
}

/** Press the frame's own `Continue`. It validates the step and advances; it is
 *  NOT the commit, which is step 4's `Schedule the disconnection ✓`. */
async function advance(page) {
  return page.evaluate(() => {
    const button = [...document.querySelectorAll('[data-wizard="actions"] button')].find(
      (b) => /continue/i.test(b.textContent ?? "") && !b.disabled,
    );
    if (button === undefined) return false;
    button.click();
    return true;
  });
}

const browser = await chromium.launch({ executablePath: resolveChromium() });

// ⚠ **BOTH STAFF WIDTHS.** A clerk screen is verified at 1440 (the design
// target) and 1280 (the laptop minimum) and at nothing narrower — the staff app
// is not a mobile product (PO 2026-09-10).
for (const width of [1440, 1280]) {
  const shot = async (page, name) => {
    const path = width === 1440 ? `${OUT}/${name}.png` : `${OUT}/${name}-1280.png`;
    await page.screenshot({ path, fullPage: true });
    recordShot(path, `${width}:${name}`);
    return path;
  };
  const page = await browser.newPage({ viewport: { width, height: 1600 } });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  const openNew = async (step) => {
    const q = ACCOUNT === "" ? "" : `&account=${ACCOUNT}`;
    await page.goto(`${BASE}/${TENANT}/disconnects/new?step=${step}${q}`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(1500);
  };
  const railWords = () =>
    page.evaluate(() =>
      [...document.querySelectorAll("[data-wizard-step]")].map((n) => (n.textContent ?? "").trim()),
    );

  // ══════════════════════════════════════════════════════════════════════════
  // THE STEPPER — ITEMS 3.1 AND 3.16
  // ══════════════════════════════════════════════════════════════════════════
  await openNew(1);
  await shot(page, "step-1-choose");
  const rail = await railWords();
  check(`${width}: the rail is FOUR segments`, rail.length === 4, JSON.stringify(rail));
  check(
    `${width}: …and they are Choose · Check · Schedule · Confirm`,
    JSON.stringify(rail) === JSON.stringify(["1Choose", "2Check", "3Schedule", "4Confirm"]),
    JSON.stringify(rail),
  );
  // ITEM 3.16 — the rail is NOT four controls that never act.
  const railButtons = await page.evaluate(
    () => document.querySelectorAll('[data-wizard="rail"] button').length,
  );
  check(`${width}: the rail draws NO button`, railButtons === 0, `${railButtons} found`);

  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ THE ACTIVE STEP MUST LOOK DIFFERENT — `DEF-SHL-6766`, AND ONLY A BROWSER
  //   CAN ANSWER IT
  // ══════════════════════════════════════════════════════════════════════════
  // Every class was in the DOM and every one compiled to a real rule; the
  // ACTIVE badge still rendered `rgb(234,233,233)` behind `rgb(243,242,242)`
  // text — near-white on near-white — because `.bg-surface` sits after
  // `.bg-accent` in the built stylesheet and the cascade decides. **`tsc`, the
  // suites, `G31`, `routeBUtilities` and an assertion reading
  // `className.toContain("text-accent")` all passed over it.** This is the
  // check that could not.
  const tones = await page.evaluate(() =>
    [...document.querySelectorAll("[data-wizard-step]")].map((cell) => {
      const badge = cell.querySelector("span");
      const cs = getComputedStyle(cell);
      const bs = badge === null ? null : getComputedStyle(badge);
      return {
        state: cell.getAttribute("data-state"),
        cell: cs.color,
        bg: bs?.backgroundColor ?? "",
        fg: bs?.color ?? "",
      };
    }),
  );
  const activeTone = tones.find((t) => t.state === "active");
  const upcoming = tones.find((t) => t.state === "upcoming");
  check(
    `${width}: the ACTIVE step is drawn differently from an upcoming one`,
    activeTone !== undefined &&
      upcoming !== undefined &&
      (activeTone.bg !== upcoming.bg || activeTone.cell !== upcoming.cell),
    JSON.stringify({ activeTone, upcoming }),
  );
  // ⚠ **CONTRAST, NOT INEQUALITY — THE FIRST DRAFT OF THIS LINE PASSED ON THE
  // BROKEN SCREEN.** It asked `bg !== fg`, and `rgb(234,233,233)` is not equal
  // to `rgb(243,242,242)`, so it reported PASS over a number nobody could read.
  // Two near-whites are *different colours* to a string comparison and the same
  // colour to a person, which is law 7's habit 2 in one line: ask what would
  // make this pass wrongly.
  const luminance = (rgb) => {
    const [r, g, b] = (rgb.match(/\d+/g) ?? ["0", "0", "0"]).map(Number);
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  };
  const contrast = (a, b) => {
    const [hi, lo] = [luminance(a) + 0.05, luminance(b) + 0.05].sort((x, y) => y - x);
    return hi / lo;
  };
  // ⚠ **WHAT THIS BAR IS AND WHAT IT IS NOT, BECAUSE A THRESHOLD CHOSEN TO GO
  // GREEN IS THE MOST DAMAGING MOVE AVAILABLE HERE.**
  //
  // It asks ONE question: *is the number drawn at all, or is it the same colour
  // as the thing behind it?* The broken composition measured **1.04:1** — near-
  // white on near-white — and the kit's signed active badge measures
  // **2.59:1**, which is `text-bg` on the brand accent. `2` separates those two
  // and nothing else was fitted to.
  //
  // ⛔ **IT IS NOT A WCAG BAR AND MUST NOT BE READ AS ONE.** AA for small text
  // is 4.5:1 and the large-text floor is 3:1; the kit's own active badge meets
  // neither, and the contrast is PRINTED on every run so nobody has to take
  // this line's word for it. Whether the brand accent should carry white
  // numerals is a DESIGN decision about a signed colour, not a defect for a
  // lane to fix on one screen's authority — reported, not quietly raised or
  // quietly lowered.
  const activeContrast =
    activeTone === undefined ? 0 : contrast(activeTone.bg, activeTone.fg);
  check(
    `${width}: …and its number is DRAWN rather than invisible (this is not a WCAG bar)`,
    activeTone !== undefined && activeContrast >= 2,
    activeTone === undefined
      ? "no active step"
      : `contrast ${activeContrast.toFixed(2)}:1 — ${JSON.stringify(activeTone)}`,
  );
  console.log(
    `INFO  ${width}: the active badge measures ${activeContrast.toFixed(2)}:1 — ` +
      "WCAG AA is 4.5:1 for small text and 3:1 for large. REPORTED, not fixed here.",
  );

  // ITEMS 3.7 / 3.8 — no subtitle, no repeated footer sentence.
  const frameText = await page.evaluate(() => document.body.innerText);
  check(`${width}: no *Five steps* subtitle`, !frameText.includes("Five steps"));
  check(
    `${width}: no *nothing is cut until the scheduled date* footer`,
    !frameText.includes("nothing is cut until the scheduled date"),
  );

  // ══════════════════════════════════════════════════════════════════════════
  // STEP 1 · CHOOSE — the account, the reason, and the services TABLE ARRAY
  // ══════════════════════════════════════════════════════════════════════════
  const one = await page.evaluate(() => ({
    account: document.querySelector('[data-panel="account"]') !== null,
    facts: document.querySelector('[data-facts="account"]') !== null,
    services: document.querySelector('[data-editable-table="services"]') !== null,
    add: document.querySelector('[data-array-add="services"]') !== null,
    fact: (document.querySelector('[data-array-fact="services"]') ?? {}).textContent ?? "",
    text: document.body.innerText,
  }));
  check(`${width}: step 1 draws *The account*`, one.account);
  check(`${width}: step 1 draws the fact strip`, one.facts);
  check(`${width}: step 1 draws *Which services* as a table array`, one.services);
  check(`${width}: …with *+ Add a service*`, one.add);
  check(`${width}: …and a running fact beside it`, one.fact.trim() !== "", one.fact);
  // ITEM 3.14 — the restrictor is GONE, option and sentence together.
  check(`${width}: no restrictor option`, !one.text.includes("Restrictor"));
  check(
    `${width}: …and no sentence about not being able to record one`,
    !one.text.includes("cannot express") && !one.text.includes("refused by name"),
  );

  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ EVERY REQUIRED FIELD, PRESSED EMPTY — NOT ASSUMED
  // ══════════════════════════════════════════════════════════════════════════
  // A validation fault ran through five dialogs in this product on 2026-09-25:
  // the field id the form asked about and the path the schema named did not
  // match, so pressing the button with a required field empty did **nothing at
  // all** — no message, no error, no movement. **The only way to know is to
  // press it**, so both of this wizard's required fields are pressed empty
  // here: the account on step 1 and the cut date on step 3 (below).
  await page.goto(`${BASE}/${TENANT}/disconnects/new?step=1`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await advance(page);
  await page.waitForTimeout(700);
  // ⚠ **SCOPED TO THE REFUSAL LINE, AND THE FIRST DRAFT WAS NOT.** It read the
  // whole frame and asked whether the text contained *account* — which is TRUE
  // on this screen because the FIELD IS LABELLED `Account`. It printed PASS
  // over a screen that had said nothing at all, which is precisely the fault
  // this check exists to catch, reproduced inside the check itself.
  const emptyAccount = await page.evaluate(() => ({
    said: document.querySelector('[data-wizard="blocked"]')?.textContent ?? "",
    active: document.querySelector('[data-wizard-step][data-state="active"]')?.textContent ?? "",
  }));
  check(
    `${width}: Continue with NO account does not advance`,
    emptyAccount.active.includes("Choose"),
    emptyAccount.active,
  );
  check(
    `${width}: …and the REFUSAL LINE says so, rather than nothing at all`,
    emptyAccount.said.trim() !== "" && /account/i.test(emptyAccount.said),
    emptyAccount.said === "" ? "the refusal line is EMPTY" : emptyAccount.said,
  );
  await shot(page, "step-1-refused-empty-account");

  // ══════════════════════════════════════════════════════════════════════════
  // STEP 2 · CHECK — `BR-CUS-1096`
  // ══════════════════════════════════════════════════════════════════════════
  await openNew(2);
  await shot(page, "step-2-check");
  const two = await page.evaluate(() => ({
    checks: document.querySelector('[data-editable-table="checks"]') !== null,
    add: document.querySelector('[data-array-add="checks"]') !== null,
    marks: document.querySelectorAll('select[id^="disconnect-mark-"]').length,
    note: document.querySelector("#disconnect-what-happened") !== null,
    text: document.body.innerText,
  }));
  check(`${width}: step 2 draws ONE checks table`, two.checks);
  check(`${width}: …with *+ Add a check*`, two.add);
  check(`${width}: …and a mark dropdown per row`, two.marks > 0, `${two.marks} rows`);
  check(`${width}: …and the *What happened* box`, two.note);
  // ITEM 3.2 — the ladder check is here and NOT on step 1.
  // ⚠ asserted as a PAIR, because *present on step 2* alone is true of the
  // screen that had it on both.
  check(
    `${width}: the ladder/notice check is on step 2`,
    two.text.includes("Notice served") || two.text.includes("Notice period"),
  );
  check(`${width}: …and not on step 1`, !one.text.includes("Where the ladder has got to"));
  // BR-CUS-1096 — warns, never blocks, and asks for nothing first.
  check(`${width}: the screen never says a protection stops the cut`, !two.text.includes("stops the cut"));
  check(`${width}: no override, tick-box or typed reason`, !two.text.includes("Override"));
  // ITEM 3.3 — three separate tables became one.
  const twoTables = await page.evaluate(
    () => document.querySelectorAll("[data-editable-table]").length,
  );
  check(`${width}: step 2 has ONE table array, not three`, twoTables === 1, `${twoTables} found`);

  // ══════════════════════════════════════════════════════════════════════════
  // STEP 3 · SCHEDULE — `BR-CUS-1099`, and ITEM 3.6
  // ══════════════════════════════════════════════════════════════════════════
  await openNew(3);
  await shot(page, "step-3-schedule");
  const three = await page.evaluate(() => ({
    notice: document.querySelector('[data-panel="notice"]') !== null,
    cutOn: document.querySelector("#disconnect-cut-on") !== null,
    visits: document.querySelector('[data-editable-table="visits"]') !== null,
    add: document.querySelector('[data-array-add="visits"]') !== null,
    warn: document.querySelector('[data-warning="no-proof"]') !== null,
    panels: document.querySelectorAll('[data-panel], [data-array]').length,
    text: document.body.innerText,
  }));
  check(`${width}: step 3 draws *Notice*`, three.notice);
  check(`${width}: …the scheduled cut date`, three.cutOn);
  check(`${width}: …and *Who goes* as a table array`, three.visits && three.add);
  check(`${width}: BR-CUS-1099 — a missing proof WARNS`, three.warn);
  check(`${width}: …and never says *No proof, no cut*`, !three.text.includes("No proof, no cut"));

  // ⚠ **ITEM 3.6 — THE BUTTON SAYS WHAT IS MISSING.** This is the defect that
  // produced the byte-identical screenshots: Continue was LIVE and did nothing
  // on an empty required date. Pressed with the date empty, the frame must now
  // print a sentence naming the field — and the step must NOT change.
  const beforeRail = await page.evaluate(
    () => document.querySelector('[data-wizard-step][data-state="active"]')?.textContent ?? "",
  );
  await advance(page);
  await page.waitForTimeout(800);
  const refusal = await page.evaluate(() => ({
    said: document.querySelector('[data-wizard="blocked"]')?.textContent ?? "",
    active: document.querySelector('[data-wizard-step][data-state="active"]')?.textContent ?? "",
  }));
  check(
    `${width}: Continue on an empty cut date does NOT advance`,
    refusal.active === beforeRail,
    `${beforeRail} → ${refusal.active}`,
  );
  check(
    `${width}: …and names the missing field rather than *fill in what's marked above*`,
    /cut date/i.test(refusal.said) && !/marked above/i.test(refusal.said),
    refusal.said === "" ? "the refusal line is EMPTY" : refusal.said,
  );
  await shot(page, "step-3-refused-empty-date");

  // Now fill it and go on, the clerk's own path.
  await page.fill("#disconnect-cut-on", "2026-10-02");
  await page.waitForTimeout(500);
  await advance(page);
  await page.waitForTimeout(2000);

  // ══════════════════════════════════════════════════════════════════════════
  // STEP 4 · CONFIRM
  // ══════════════════════════════════════════════════════════════════════════
  await shot(page, "step-4-confirm");
  const four = await page.evaluate(() => ({
    active: document.querySelector('[data-wizard-step][data-state="active"]')?.textContent ?? "",
    thisCut: document.querySelector('[data-panel="this-cut"]') !== null,
    fees: document.querySelector('[data-editable-table="fees"]') !== null,
    plan: (document.querySelector("[data-plan-and-category]") ?? {}).textContent ?? "",
    deposit: document.querySelector('[data-panel="deposit"]') !== null,
    toClear: document.querySelector('[data-recap="to-clear"]') !== null,
    repeatVisits: document.querySelector('[data-editable-table="confirm-visits"]') !== null,
    marks: document.querySelector('[data-consequence="marks"]') !== null,
    commit: [...document.querySelectorAll('[data-wizard="actions"] button')].some((b) =>
      /Schedule the disconnection/.test(b.textContent ?? ""),
    ),
    text: document.body.innerText,
  }));
  check(`${width}: Continue reached step 4`, four.active.includes("Confirm"), four.active);
  check(`${width}: step 4 draws *This cut*`, four.thisCut);
  check(`${width}: …the fees table`, four.fees);
  check(`${width}: …naming the account's plan and category`, four.plan.trim() !== "", four.plan);
  check(`${width}: …the deposit panel`, four.deposit && four.toClear);
  check(`${width}: …the field work REPEATED (item 3.5)`, four.repeatVisits);
  check(`${width}: …and BR-CUS-1100's account-and-customer mark`, four.marks);
  check(`${width}: the commit is *Schedule the disconnection ✓*`, four.commit);
  // ══════════════════════════════════════════════════════════════════════════
  // ITEM 3.9 / B14 RULE 37 — AND THE FIRST VERSION OF THIS CHECK WAS WRONG
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **IT ASSERTED THAT THE SIX DRAWN FIGURES ARE ABSENT FROM THE SCREEN, AND
  // IT FAILED ON A SCREEN THAT WAS BEHAVING CORRECTLY.** Two of the six —
  // `$75.00` and `$45.00` — are ALSO this tenant's real, seeded charge-code
  // amounts (PO 2026-09-21: *"reconnection fee is $75 - fix the code and
  // seed"*). So a string search cannot tell *the screen hardcoded the drawing's
  // figure* from *the tenant's catalogue says that number*, which is the whole
  // question `BR-BIL-007` asks. **A check you cannot describe a false pass for
  // is a check you do not understand** — this one had a false FAIL, and the
  // same blindness is a false PASS the day a tenant prices a fee at $35.00.
  //
  // **THE QUESTION THAT CAN BE ANSWERED: does every amount on the screen come
  // from the API?** Asked by reading the same endpoint the screen reads and
  // comparing, figure for figure.
  // ⚠ **THE TENANT IS A URL SEGMENT AND NOT A HEADER** — `/api/{tenant}/…`,
  // read from the route the browser is actually on (`src/api/client.ts` §API
  // URL shape). The first draft of this read guessed a header and an account
  // id taken from `pathname.split("/")[3]`, which on
  // `/brazosbend/disconnects/new` is the word `new`. It failed, and it printed
  // a SKIP saying so rather than a PASS — which is the only reason it was
  // noticed at all.
  const served = await page.evaluate(
    async ([tenant, account]) => {
      const r = await fetch(`/api/${tenant}/accounts/${account}/reconnection-terms`);
      if (!r.ok) return null;
      const body = await r.json();
      return ((body.data ?? body).fees ?? []).map((f) =>
        f.amount === null || f.amount === undefined ? null : f.amount.display,
      );
    },
    [TENANT, ACCOUNT],
  );
  if (served === null) {
    console.log(
      `SKIP  ${width}: the fee figures — the reconnection-terms read did not answer, ` +
        "so nothing below was compared. This is NOT a pass.",
    );
  } else {
    // ⚠ **SCOPED TO THE FEES TABLE, NOT THE PAGE — AND THE FIRST DRAFT OF THIS
    // WAS INCAPABLE OF FAILING.** It read every figure on the page and then
    // asked `four.text.includes(money)`, which is TRUE for every figure by
    // construction, because that is where `money` came from. It printed PASS
    // over anything. That is hard-won law 7's *structurally incapable of
    // failing* shape, written by the same hand that quoted the law at the top
    // of this file — which is why habit 2, *ask what would make this check pass
    // wrongly*, is worth more than the law it comes from.
    //
    // The page legitimately carries figures from OTHER reads — the arrears, the
    // deposit, the reconnection total — so the question is only about the FEES
    // TABLE, and it is answered by set difference against what the API served.
    const feeFigures = await page.evaluate(() => {
      const table = document.querySelector('[data-editable-table="fees"]');
      return table === null
        ? null
        : [...(table.textContent ?? "").matchAll(/\$[\d,]+\.\d{2}/g)].map((m) => m[0]);
    });
    const unserved =
      feeFigures === null
        ? []
        : feeFigures.filter(
            (money) => !served.some((v) => v !== null && money === `$${v}`),
          );
    check(
      `${width}: every figure in the FEES table came from the server`,
      feeFigures !== null && unserved.length === 0,
      `served ${JSON.stringify(served)} · in the table ${JSON.stringify(feeFigures)} · unserved ${JSON.stringify(unserved)}`,
    );
    // And the two the drawing invents for a COMMERCIAL account, which this
    // tenant does not price, must be absent whatever else is.
    for (const invented of ["$85.00", "$150.00", "$35.00"]) {
      check(
        `${width}: the drawn ${invented} is not rendered unless the server served it`,
        !four.text.includes(invented) || served.some((s) => s !== null && invented.includes(s)),
      );
    }
  }
  for (const code of ["CC-RECON", "CC-DISC", "CC-FIELD"]) {
    check(`${width}: the charge code ${code} is NOT on screen`, !four.text.includes(code));
  }
  // ITEM 3.10 — no subtraction the product cannot make.
  check(`${width}: no *Deposit applied* subtraction`, !four.text.includes("Deposit applied"));

  // ══════════════════════════════════════════════════════════════════════════
  // THE MASTER VARIANT — `BR-CUS-1098`
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **SKIPPED WITH A REASON RATHER THAN QUIETLY PASSING.** A check that
  // reports nothing over a scope it excludes is indistinguishable from an empty
  // one (CLAUDE.md law 7, fifth shape), so the absence is printed.
  if (MASTER === "") {
    console.log(
      `SKIP  ${width}: the master variant — no MASTER account id was supplied. ` +
        "Pass MASTER=<account id> to walk it; nothing below was checked.",
    );
  } else {
    for (const step of [1, 2, 3, 4]) {
      await page.goto(`${BASE}/${TENANT}/accounts/${MASTER}/disconnect?step=${step}`, {
        waitUntil: "networkidle",
      });
      await page.waitForTimeout(1500);
      await shot(page, `master-step-${step}`);
    }
    const master = await page.evaluate(() => document.body.innerText);
    check(`${width}: the master variant names the account as a master`, master.includes("Master account"));
  }

  await page.close();
}

await browser.close();
console.log(`\n${failures} FAILURE(S) · shots in ${OUT}`);
console.log(
  "⚠ THE SHOTS ARE HALF THE CHECK. Put each beside its PNG — Step1Choose.png, " +
    "Step2Check.png, Step3Schedule.png, Step4Confirm.png and the four master " +
    "variants — and walk presence, order, labels, alignment, spacing, weight " +
    "and colour in that order. No tool does that half.",
);
process.exit(failures === 0 ? 0 : 1);
