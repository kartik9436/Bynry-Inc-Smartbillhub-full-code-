// ── Trace ──────────────────────────────────────────────
// Screens:  ACC-06, ALL FOUR steps, against their APPROVED drawings —
//           `05-prototype/move-out-acc06-2026-09-24/{01,01M,02,02M,03,04}*.png`
//           (PO ratified 2026-09-24: *"this scren drawing are correct - use
//           images to build the screen and all changes that we discussed"*,
//           then *"okay we are good with all changes agreed for move out"*).
// Rules:    B14 rule 42 (a screen is built from the drawing AS AN IMAGE) ·
//           rule 44 (the drawing says WHAT is on the screen; our token scale,
//           spacing and component kit say HOW it is built, and win) · rule 43
//           (a piece of UI is a COMPONENT) · rule 37 (a drawn figure is an
//           ILLUSTRATION) · rule 33 (RATIONALE is ZERO words on screen) ·
//           CLAUDE.md hard-won law 6 — diffing the running app against the
//           drawing is the ONLY check in this repository that reads rendered
//           output, and it is a person.
// ───────────────────────────────────────────────────────
//
//   BASE=http://127.0.0.1:8972 node 10-scripts/po20260924_move_out_four_steps_walkthrough.mjs
//
// ⚠ **READ-ONLY, AND IT SAYS SO RATHER THAN CLAIMING IT.** A move-out COMMITS
// and there is no undo (CLAUDE.md hard rule 4). This walk OPENS the four
// screens, types a date and a reading so the engine has something to price,
// reads the DOM and photographs it. **Nothing is submitted and nothing is
// parked**; the write paths are proved by the backend suites.
//
// ⚠ **WHAT THIS CAN AND CANNOT TELL YOU.** It reads the DOM, so it answers
// *is the row there, in the drawn order, spelled as drawn* — the half no unit
// test in this repo answers, because none renders to a browser. It does NOT
// measure spacing or weight; the screenshots are for a PERSON to put beside
// the PNG, which is the other half of law 6 and has no tool.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8972";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/moveout-built";
// A REGULAR occupying account and a MASTER, both real rows on the seeded
// tenant. Overridable, because the seed moves.
// ⚠ **AN ACCOUNT WITH METERS, DELIBERATELY.** The first row of the seeded
// list holds none, and a move-out on a meterless account cannot be priced —
// so step 3 states why instead of drawing the bill, and the shot proves
// nothing about the table. `Creekside Laundromat` has three registers.
// ⚠ 2026-10-11: the two ids that were pinned here (`Creekside Laundromat` and
// a master) did not survive a reseed — a hardcoded uuid is a fixture that
// rots silently, and the walk failed 36 checks over pages that never loaded.
// So the defaults are RESOLVED from the tenant after sign-in: ACCOUNT is the
// first open REGULAR account whose unit has a metered service (preferring one
// whose unit also has a % or capacity service), MASTER the first open master.
let ACCOUNT = process.env.ACCOUNT ?? "";
let MASTER = process.env.MASTER ?? "";
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

/** Press the frame's own `Continue`. It validates the step and advances; it is
 *  NOT the commit, which is the last step's `Close the account`. */
async function advance(page) {
  const pressed = await page.evaluate(() => {
    const button = [...document.querySelectorAll('[data-wizard="actions"] button')].find(
      (b) => /continue/i.test(b.textContent ?? "") && !b.disabled,
    );
    if (button === undefined) return false;
    button.click();
    return true;
  });
  return pressed;
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
let failures = 0;
const check = (label, ok, detail = "") => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
};

// ⚠ **BOTH STAFF WIDTHS.** The skill's §6 table: a clerk screen is verified at
// 1440 (the design target) and 1280 (the laptop minimum) and at nothing
// narrower — the staff app is not a mobile product (PO 2026-09-10).
for (const width of [1440, 1280]) {
  const shot = (name) =>
    width === 1440 ? `${OUT}/${name}.png` : `${OUT}/${name}-1280.png`;
  const page = await browser.newPage({ viewport: { width, height: 1400 } });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  if (ACCOUNT === "" || MASTER === "") {
    const picked = await page.evaluate(async (tenant) => {
      const get = async (url) => (await fetch(`/api/${tenant}${url}`, { headers: { Accept: "application/json" } })).json();
      const list = await get("/accounts?per=200");
      const rows = (list.results ?? list.data?.results ?? []).filter((r) => r.closed_at === null);
      const master = rows.find((r) => r.kind === "master")?.id ?? "";
      let best = null;
      for (const r of rows.filter((x) => x.kind === "regular" && x.unit_id)) {
        const sv = await get(`/units/${r.unit_id}/move-out-services`);
        if ((sv.metered ?? []).length === 0) continue;
        const score = (sv.share ?? []).length + (sv.capacity ?? []).length;
        if (best === null || score > best.score) best = { id: r.id, score, no: r.account_no };
        if (score > 0) break;
      }
      return { master, account: best?.id ?? "", accountNo: best?.no ?? "" };
    }, TENANT);
    if (ACCOUNT === "") ACCOUNT = picked.account;
    if (MASTER === "") MASTER = picked.master;
    console.log(`      (account ${picked.accountNo || ACCOUNT}, master ${MASTER})`);
  }
  const open = async (account, step) => {
    await page.goto(`${BASE}/${TENANT}/accounts/${account}/move-out?step=${step}`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(1800);
  };
  const railWords = () =>
    page.evaluate(() =>
      [...document.querySelectorAll("[data-wizard-step]")].map((n) => (n.textContent ?? "").trim()),
    );
  const stepLine = () =>
    page.evaluate(() => (document.body.innerText.match(/Step \d+ of \d+[^\n]*/) ?? [""])[0]);

  // ══════════════════════════════════════════════════════════════════════════
  // THE STEPPER — four across, on EVERY screen. This is the first thing the PO
  // looks at, and the thing they reported as still reading six.
  // ══════════════════════════════════════════════════════════════════════════
  await open(ACCOUNT, 1);
  await page.screenshot({ path: shot("step-1-find-account"), fullPage: true });
  const rail = await railWords();
  check(
    `${width}: the rail is FOUR segments`,
    rail.length === 4,
    `${rail.length}: ${JSON.stringify(rail)}`,
  );
  check(
    `${width}: …and they are the drawn four`,
    JSON.stringify(rail) ===
      JSON.stringify(["1Find account", "2Date & reads", "3Bill & deposit", "4Review & close"]),
    JSON.stringify(rail),
  );
  check(`${width}: the step line counts to four`, (await stepLine()).includes(" of 4"), await stepLine());

  // ══════════════════════════════════════════════════════════════════════════
  // STEP 2 — `02-date-and-reads.png`. The date and a reading are TYPED so the
  // engine has a closing window to price; nothing is submitted.
  // ══════════════════════════════════════════════════════════════════════════
  await open(ACCOUNT, 2);
  const dateField = await page.$("#moved_out_on");
  if (dateField !== null) {
    // Not before the account opened (the step refuses that): today, or
    // `MOVE_OUT_DATE=`.
    await dateField.fill(process.env.MOVE_OUT_DATE ?? new Date().toISOString().slice(0, 10));
    await page.waitForTimeout(400);
  }
  const reason = await page.$("#close_reason");
  if (reason !== null) {
    await reason.selectOption({ index: 1 }).catch(() => undefined);
  }
  // ⊕ 2026-10-11 (`DEF-CUS-10051`): step 2's services are grouped by billing
  // basis; every metered row's box opens with its last reading (`OQ-394`) and
  // a BLANK one blocks Continue. The walk keeps the prefilled figures (they
  // close at zero usage, which the engine can price) and fills any box that
  // opened empty with `READ=` or 0.
  await page.waitForTimeout(1500);
  const groups = await page.evaluate(() =>
    [...document.querySelectorAll("[data-move-out-services] [data-array]")].map((g) => g.getAttribute("data-array")),
  );
  check(`${width}: step 2 groups the unit's services, metered first`, groups[0] === "move-out-metered", JSON.stringify(groups));
  const readBoxes = page.locator('input[id^="moveOut-read-"]:not([id^="moveOut-read-date-"])');
  for (let i = 0; i < (await readBoxes.count()); i += 1) {
    if ((await readBoxes.nth(i).inputValue()) === "") await readBoxes.nth(i).fill(process.env.READ ?? "0");
  }
  await page.waitForTimeout(2500);
  await page.screenshot({ path: shot("step-2-date-and-reads"), fullPage: true });
  check(`${width}: step 2's move-out date is a PICKER`, dateField !== null &&
    (await dateField.evaluate((el) => el.getAttribute("type"))) === "date");

  // ══════════════════════════════════════════════════════════════════════════
  // STEP 3 — `03-bill-and-deposit.png`. THE HEADLINE SCREEN.
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **PRESS `Continue`, DO NOT CLICK THE RAIL AND DO NOT RE-NAVIGATE.** The
  // rail disables a step the clerk has not reached, so a click on segment 3 is
  // a no-op — the first run of this walk did exactly that and photographed
  // step 2 under the name `step-3`, which is a check looking at the wrong
  // thing. And `?step=3` remounts the wizard, which throws away the date and
  // the reading typed above, so the preview would have nothing to price.
  // Continue is the clerk's own path and it COMMITS NOTHING on this step.
  await advance(page);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: shot("step-3-bill-and-deposit"), fullPage: true });

  const three = await page.evaluate(() => ({
    text: document.body.innerText,
    money: document.querySelector('[data-move-matrix="money"]') !== null,
    draftBill: document.querySelector('[data-move-matrix="draft-bill"]') !== null,
    draftSection: document.querySelector('[data-step-section="draft-bill"]') !== null,
    deposit: document.querySelector('[data-step-section="deposit"]') !== null,
    paths: document.querySelector('[data-move-matrix="shortfall-paths"]') !== null,
    landings: document.querySelector('[data-move-matrix="landings"]') !== null,
    otherThree: document.querySelector('[data-move-matrix="other-three"]') !== null,
  }));
  // ⛔ **THE THREE DELETIONS THE PO ASKED FOR AND COULD STILL SEE.**
  check(`${width}: step 3 no longer draws *The five landings*`,
    !three.landings && !three.text.includes("The five landings"));
  check(`${width}: step 3 no longer draws *What the other three would ask for*`,
    !three.otherThree && !three.text.includes("What the other three would ask for"));
  check(`${width}: step 3 no longer says *The subtraction has not run yet.*`,
    !three.text.includes("The subtraction has not run yet"));
  // …and the drawn panels ARE there.
  check(`${width}: step 3 draws *The money*`, three.money);
  check(`${width}: step 3 draws *The deposit*`, three.deposit);
  check(`${width}: step 3 draws *The draft bill*`, three.draftSection,
    three.draftBill ? "with a table" : "stating why it is not priced");
  // ⊕ `DEF-BIL-10052`: priced, or *The draft bill is not generated.* with the
  // missing values, or the engine's own reason — always with Back to readings
  // when it is not priced.
  if (!three.draftBill) {
    const backs = await page.locator("[data-back-to-readings]").count();
    check(`${width}: an unpriced draft bill offers *Back to readings*`, backs === 1, `${backs}`);
  }
  // ⊕ `DEF-CUS-10053` (PO 2026-10-11, *"show me all option dont drop it"*):
  // every deposit option stays on screen; the account's own landing is the
  // one highlighted, carrying its amount.
  const options = await page.evaluate(() =>
    [...document.querySelectorAll("[data-deposit-option]")].map((n) => ({
      option: n.getAttribute("data-deposit-option"),
      selected: n.getAttribute("data-selected") === "yes",
      text: (n.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 60),
    })),
  );
  const chosen = options.filter((o) => o.selected);
  check(
    `${width}: step 3 keeps every deposit option and highlights at most one`,
    options.length >= 3 && chosen.length <= 1,
    JSON.stringify(options),
  );
  if (chosen.length === 1 && chosen[0].option !== "apply") {
    check(`${width}: the highlighted option carries its amount`, /\$\d/.test(chosen[0].text), chosen[0].text);
  }

  // ══════════════════════════════════════════════════════════════════════════
  // STEP 4 — `04-review-and-close.png`, six panels.
  // ══════════════════════════════════════════════════════════════════════════
  await advance(page);
  await page.waitForTimeout(2000);
  await page.screenshot({ path: shot("step-4-review-and-close"), fullPage: true });
  const four = await page.evaluate(() => ({
    sections: [...document.querySelectorAll("[data-step-section]")].map((n) =>
      n.getAttribute("data-step-section"),
    ),
    text: document.body.innerText,
  }));
  for (const drawn of ["account", "unit", "closing-meters", "money", "messages"]) {
    check(`${width}: step 4 draws *${drawn}*`, four.sections.includes(drawn),
      JSON.stringify(four.sections));
  }
  check(`${width}: step 4 no longer draws *What this close does NOT do*`,
    !four.text.includes("What this close does NOT do"));
  check(`${width}: step 4 no longer draws *Not stated here*`,
    !four.text.includes("Not stated here"));
  check(`${width}: step 4 keeps *What we will send*`, four.text.includes("What we will send"));

  // ══════════════════════════════════════════════════════════════════════════
  // THE MASTER VARIANTS — `01M` and `02M`.
  // ══════════════════════════════════════════════════════════════════════════
  await open(MASTER, 1);
  await page.screenshot({ path: shot("step-1M-find-account-master"), fullPage: true });
  const masterOne = await page.evaluate(() => ({
    kindMaster: (document.body.innerText.match(/Kind\s*\n?\s*Master/) ?? []).length > 0 ||
      document.body.innerText.includes("Master"),
    table: document.querySelector('[data-move-matrix="master-accounts"]') !== null,
    refusal: document.querySelector("[data-master-refusal]") !== null,
    continueDisabled: [...document.querySelectorAll("button")]
      .filter((b) => /continue/i.test(b.textContent ?? ""))
      .every((b) => b.disabled),
    text: document.body.innerText,
  }));
  check(`${width}: step 1 master names the KIND`, masterOne.kindMaster);
  check(`${width}: step 1 master lists the accounts on this master`, masterOne.table);
  check(`${width}: step 1 master REFUSES`, masterOne.refusal);
  // ⚠ CORRECTED 2026-10-11: this read *"Continue cannot be pressed"* and
  // passed only while the pinned MASTER id no longer opened a page (no button
  // at all → `every` is true). The shared wizard frame offers no disabled
  // Continue; a refused master's step returns its SENTENCE on the press
  // (`MoveOutWizard.tsx`, *"A REFUSED MASTER RETURNS THE SENTENCE, NOT
  // false"*). So the press is made and must hold step 1 and say why.
  await advance(page);
  await page.waitForTimeout(1000);
  const held = await page.evaluate(() => ({
    onOne: /Step 1 of 4/.test(document.body.innerText),
    said: document.body.innerText.split("This account cannot be closed.").length - 1,
  }));
  check(
    `${width}: …and pressing Continue holds step 1 and says why`,
    held.onOne && held.said >= 2,
    JSON.stringify(held),
  );

  await open(MASTER, 2);
  await page.screenshot({ path: shot("step-2M-date-and-reads-master"), fullPage: true });
  const masterTwo = await page.evaluate(() => ({
    units: document.querySelector('[data-move-matrix="master-units"]') !== null,
    common: document.body.innerText.includes("common areas"),
  }));
  check(`${width}: step 2 master draws *Units on this master*`, masterTwo.units);
  check(`${width}: step 2 master's meters panel is the COMMON AREAS`, masterTwo.common);

  await page.close();
}

await browser.close();
console.log(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
