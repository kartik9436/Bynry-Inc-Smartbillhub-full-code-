// ── Trace ──────────────────────────────────────────────
// Screens:  ACC-06 steps 1 and 2, against their APPROVED drawings —
//           `05-prototype/move-out-acc06-2026-09-24/01-find-account.png` and
//           `02-date-and-reads.png` (PO ratified 2026-09-24: *"this scren
//           drawing are correct - use images to build the screen"*).
// Defects:  DEF-CUS-6476 (step 1's panel was missing four drawn rows) ·
//           DEF-CUS-6487 (the field-visit table, and the door that discarded
//           its rows) · DEF-CUS-6475 (one searchable box, not two controls)
// Rules:    B14 rule 42 (a screen is built from the drawing AS AN IMAGE) ·
//           rule 31 (no database id is a field's visible value) · rule 33
//           (a LABEL ≤ 3 words; RATIONALE is ZERO words on screen) ·
//           CLAUDE.md hard-won law 6 — diffing the running app against the
//           drawing is the ONLY check in this repository that reads rendered
//           output, and it is a person
// ───────────────────────────────────────────────────────
//
//   BASE=http://127.0.0.1:8972 node 10-scripts/po20260924_move_out_steps_1_2_walkthrough.mjs
//
// ⚠ **READ-ONLY, AND IT SAYS SO RATHER THAN CLAIMING IT.** A move-out COMMITS
// and there is no undo (hard rule 4). This walk OPENS the two screens, reads
// them and photographs them; nothing is submitted and nothing is parked. The
// write paths are proved by the backend suites.
//
// ⚠ **WHAT THIS CAN AND CANNOT TELL YOU.** It reads the DOM, so it answers
// *is the row there, in the drawn order, spelled as drawn* — which is the half
// no unit test in this repo answers, because none of them renders to a browser.
// It does NOT measure spacing or weight; the screenshots are for a person to put
// beside the PNG, which is the other half of law 6 and has no tool.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// Resolved through `07-frontend` — `playwright` is not a dependency of the repo
// root, so a bare import fails wherever this is run from.
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8972";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/mvo-1-2";
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
  const page = await browser.newPage({ viewport: { width, height: 1400 } });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  // ── An ACTIVE account, found the way a clerk finds one ────────────────────
  await page.goto(`${BASE}/${TENANT}/accounts`, { waitUntil: "networkidle" });
  const href = await page.evaluate(() => {
    const a = [...document.querySelectorAll('a[href*="/accounts/"]')].find((x) =>
      /\/accounts\/[0-9a-f-]{20,}$/.test(x.getAttribute("href") ?? ""),
    );
    return a ? a.getAttribute("href") : null;
  });
  // ⚠ **THE ACCOUNT IS OVERRIDABLE, AND THE DEFAULT IS WHATEVER THE LIST GIVES
  // FIRST — WHICH IS THE POINT.** The first row on the seeded tenant is a
  // MASTER with no unit, and running against it is what found `DEF-CUS-6492`.
  // Pin `ACCOUNT=` to a regular account to exercise the reading table itself;
  // both cases matter and neither is the "real" one.
  if (!href && !process.env.ACCOUNT) {
    check(`${width}: found an account to open`, false);
    continue;
  }
  const accountId = process.env.ACCOUNT ?? href.split("/").pop();

  // ══════════════════════════════════════════════════════════════════════════
  // STEP 1 — `01-find-account.png`
  // ══════════════════════════════════════════════════════════════════════════
  await page.goto(`${BASE}/${TENANT}/accounts/${accountId}/move-out?step=1`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/step1-${width}.png`, fullPage: true });

  const panel = await page.$("[data-move-out-account-panel]");
  check(`${width}: step 1 draws the account panel`, panel !== null);

  // ── THE DRAWN ROWS, IN THE DRAWN ORDER (DEF-CUS-6476) ────────────────────
  // The whole point of the defect: four of these were absent while the server
  // had been sending them all along. Read from the DOM in document order, so a
  // row in the wrong column is caught as well as a row that is missing.
  const labels = await page.evaluate(() =>
    [...document.querySelectorAll("[data-move-out-account-panel] dt")].map((n) =>
      (n.textContent ?? "").trim(),
    ),
  );
  const drawn = [
    "Account",
    "Name",
    "Service address",
    "Mailing address",
    "Services",
    "Plan",
    "Type",
    "Sub-type",
    "Kind",
    "Status",
    "Since",
    "Balance",
  ];
  check(
    `${width}: step 1's panel draws all 12 rows in the drawn order`,
    JSON.stringify(labels) === JSON.stringify(drawn),
    `saw ${JSON.stringify(labels)}`,
  );

  // ── ONE SEARCHABLE BOX, NOT TWO CONTROLS (DEF-CUS-6475) ──────────────────
  // The account-scoped road draws no finder at all (the account is in the
  // address bar); the standalone road draws exactly one.
  await page.goto(`${BASE}/${TENANT}/move-outs/new?step=1`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/step1-find-${width}.png`, fullPage: true });
  const finderControls = await page.evaluate(
    () => document.querySelectorAll("[data-account-finder] input, [data-account-finder] select").length,
  );
  check(
    `${width}: the finder is ONE control, not a box plus a second select`,
    finderControls === 1,
    `saw ${finderControls}`,
  );
  // ⛔ B14 rule 31 — the id never becomes the visible value of the field.
  const finderValue = await page.evaluate(() => {
    const el = document.querySelector("[data-account-finder] input");
    return el === null ? "" : el.value;
  });
  check(
    `${width}: the finder shows no database id`,
    !/[0-9a-f]{8}-[0-9a-f]{4}-/.test(finderValue),
    finderValue,
  );

  // ══════════════════════════════════════════════════════════════════════════
  // STEP 2 — `02-date-and-reads.png`
  // ══════════════════════════════════════════════════════════════════════════
  await page.goto(`${BASE}/${TENANT}/accounts/${accountId}/move-out?step=2`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${OUT}/step2-${width}.png`, fullPage: true });

  // ── EVERY DATE IS A PICKER (the spec sheet's own footnote) ───────────────
  const dateInputs = await page.evaluate(
    () => document.querySelectorAll('input[type="date"]').length,
  );
  check(`${width}: step 2's dates are date pickers`, dateInputs >= 1, `${dateInputs} picker(s)`);
  const movedOut = await page.$("#moved_out_on");
  check(`${width}: the move-out date is a picker`, movedOut !== null);
  if (movedOut !== null) {
    const type = await movedOut.evaluate((el) => el.getAttribute("type"));
    check(`${width}: …of type=date, not a typed box`, type === "date", String(type));
  }
  check(`${width}: step 2 draws the reason select`, (await page.$("#close_reason")) !== null);

  // ── THE NINE-COLUMN READING TABLE (PO-approved 2026-09-23/24) ────────────
  // ⚠ **EITHER THE TABLE OR A STATED ABSENCE — NEVER NOTHING (DEF-CUS-6492).**
  // This walk found the meters area rendering no heading, no table and no
  // sentence on a MASTER account, whose `unit_id` is NULL by BR-CUS-1010.
  // `MoveInReadingsTable` returns null on an empty unitId, which is right for
  // the move-in and wrong the moment a second host inherits it. So the check is
  // not *is the table there* — it is **is ANYTHING there**.
  const meters = await page.evaluate(() => {
    const absent = document.querySelector("[data-move-out-meters='no-unit']");
    if (absent !== null) return { kind: "stated", text: (absent.textContent ?? "").trim() };
    // ⚠ **ASK FOR THE COMPONENT, NOT FOR A `<table>` — this check did not check
    // on its first run.** `MoveInReadingsTable` renders four states and only
    // ONE of them is a table: `loading` is a skeleton, `failed` is a Note, and
    // a unit with no registers is an empty-text box reading *No meters at this
    // unit*. Looking for `<table>` reported "nothing" over a panel that was
    // plainly on the screen, which is the exact shape this walk exists to
    // catch, turned on itself.
    // ⊕ 2026-10-11 (`DEF-CUS-10051`): a unit's services are now
    // `MoveOutServicesTable`, grouped by billing basis — *Meters on this unit*
    // (`move-out-metered`), *% of service* (`move-out-share`) and *Capacity
    // based* (`move-out-capacity`) — each group drawn only when it has rows.
    const services = document.querySelector("[data-move-out-services]");
    if (services !== null) {
      const state = services.getAttribute("data-move-out-services");
      // `TableArray` puts its collection on the frame as `data-array`; the
      // frame opens with its title.
      const groups = [...services.querySelectorAll("[data-array]")].map((g) => ({
        key: g.getAttribute("data-array"),
        title: (g.textContent ?? "").trim().slice(0, 40),
        rows: g.querySelectorAll("tbody tr").length,
      }));
      return { kind: state === "ready" ? "services" : "stateful", state, groups, text: (services.textContent ?? "").trim() };
    }
    const host = document.querySelector("[data-move-in-readings]");
    if (host === null) return { kind: "nothing" };
    const state = host.getAttribute("data-move-in-readings");
    const table = host.querySelector("table");
    if (table === null) return { kind: "stateful", state, text: (host.textContent ?? "").trim() };
    return {
      kind: "table",
      state,
      heads: [...table.querySelectorAll("thead th")].map((n) => (n.textContent ?? "").trim()),
    };
  });
  check(
    `${width}: the meters area is never blank — it draws a table or states why not`,
    meters.kind !== "nothing",
    meters.kind,
  );
  if (meters.kind === "services") {
    const TITLES = {
      "move-out-metered": "Meters on this unit",
      "move-out-share": "% of service",
      "move-out-capacity": "Capacity based",
    };
    console.log(`      (services: ${JSON.stringify(meters.groups)})`);
    for (const group of meters.groups.filter((g) => TITLES[g.key] !== undefined)) {
      check(
        `${width}: the ${group.key} group is titled "${TITLES[group.key]}"`,
        group.title.startsWith(TITLES[group.key]),
        group.title,
      );
    }
    // Every READABLE metered row carries the Fetch reading icon (DEF-CUS-10051
    // task 7), which is Move-in's own `FetchMeterReading`.
    const fetchSlots = await page.evaluate(() =>
      [...document.querySelectorAll("[data-fetch-slot]")].map((n) => ({
        meter: n.getAttribute("data-fetch-slot"),
        button: n.querySelector("[data-fetch-reading] button") !== null,
      })),
    );
    const readBoxes = await page.locator('input[id^="moveOut-read-"]:not([id^="moveOut-read-date-"])').count();
    check(
      `${width}: each metered row with a reading box has a Fetch reading button`,
      fetchSlots.length === readBoxes && fetchSlots.every((f) => f.button),
      `${readBoxes} box(es), ${JSON.stringify(fetchSlots)}`,
    );
  }
  const readCols = meters.kind === "table" ? meters.heads : null;
  if (meters.kind === "stated" || meters.kind === "stateful") {
    console.log(`      (meters area is in state "${meters.state ?? "no-unit"}" — "${(meters.text ?? "").slice(0, 70)}")`);
  }
  if (readCols !== null) {
    check(
      `${width}: the reading table has the nine approved columns`,
      readCols.length === 9,
      JSON.stringify(readCols),
    );
    // ⚠ **THE COLUMN A CLERK TYPES INTO MUST NOT SAY *Move-in* ON A MOVE-OUT.**
    // Sharing the table hands you the other flow's word for free, and nothing
    // but an assertion catches it.
    check(
      `${width}: the reading column is not headed "Move-in reading"`,
      !readCols.some((c) => /move-in/i.test(c)),
      JSON.stringify(readCols),
    );
  }

  // ── THE SEVEN-COLUMN FIELD-VISIT TABLE, AND *No visit needed* ────────────
  const visit = await page.evaluate(() => {
    const host = document.querySelector('[data-field-visit], [data-flow-kind="move_out"]');
    const root = host ?? document.body;
    const heads = [...root.querySelectorAll("table thead th")].map((n) =>
      (n.textContent ?? "").trim(),
    );
    return {
      hasNoVisit: /No visit needed/i.test(root.textContent ?? ""),
      hasAddOrder: /Add work order/i.test(root.textContent ?? ""),
      heads,
    };
  });
  check(`${width}: step 2 offers "No visit needed"`, visit.hasNoVisit);
  check(`${width}: step 2 offers "+ Add work order"`, visit.hasAddOrder);

  // ── RULE 33: the rationale the PO struck is GONE from the rendered page ───
  // Every one of these was on this screen at v2.351.19 and was reported by the
  // PO. They are deletions, not shortenings, so the test is absence.
  const body = await page.evaluate(() => document.body.innerText);
  for (const gone of [
    "because none of them can happen yet",
    "The date is the whole of what this step stores",
    "Listed so you can see which registers are left unread",
    "the same search the accounts list uses",
    "AC-2026-00025",
  ]) {
    check(`${width}: struck copy is gone — "${gone.slice(0, 44)}…"`, !body.includes(gone));
  }

  // ══════════════════════════════════════════════════════════════════════════
  // STEP 3 — the bill either prices, or SAYS WHY NOT (`DEF-CUS-6464`)
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **THE PO's OWN QUESTION, and the one thing a unit test cannot settle:**
  // whether a REAL account on a REAL tenant gets an answer. Measured on the
  // seeded tenant, 30 of 75 open accounts refuse to price — and on every one of
  // them this panel drew two rows and no sentence at all.
  // ⚠ **DRIVEN FROM STEP 2, NOT JUMPED TO.** The preview query is DISABLED
  // until a move-out date exists — correctly, since there is no window to price
  // without one — so a `goto(?step=3)` lands on a step with no preview at all
  // and proves nothing. The wizard's state does not survive a navigation, so
  // the date is typed and *Continue* is pressed, which is in-page only and
  // writes nothing. **This walk stays read-only: nothing is submitted and
  // nothing is parked** (a move-out commits and there is no undo, hard rule 4).
  await page.goto(`${BASE}/${TENANT}/accounts/${accountId}/move-out?step=2`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1200);
  // The date must not precede the account's opening (the step refuses it),
  // so it defaults to TODAY rather than a fixed day an account newer than the
  // walk would refuse. `MOVE_OUT_DATE=` pins one.
  await page.fill("#moved_out_on", process.env.MOVE_OUT_DATE ?? new Date().toISOString().slice(0, 10));
  await page.selectOption("#close_reason", { index: 1 });
  // ⊕ 2026-10-11: a blank closing read BLOCKS Continue. Each box opens with
  // its register's last reading (`OQ-394`'s ruled prefill), so the walk
  // CLEARS them, presses Continue (in-page only, nothing written) and expects
  // step 2 to hold and say so — then puts the prefilled figures back.
  await page.waitForTimeout(1500);
  const readBoxes = page.locator('input[id^="moveOut-read-"]:not([id^="moveOut-read-date-"])');
  const readCount = await readBoxes.count();
  if (readCount > 0) {
    const prefilled = await readBoxes.evaluateAll((ns) => ns.map((n) => n.value));
    for (let i = 0; i < readCount; i += 1) await readBoxes.nth(i).fill("");
    await page.click("button:has-text('Continue')");
    await page.waitForTimeout(1500);
    const told = await page.getByText("Enter a reading or check Estimate.").count();
    check(
      `${width}: a blank reading blocks Continue`,
      /step=2/.test(page.url()) && told > 0,
      `told ${told} time(s), at ${new URL(page.url()).search}`,
    );
    for (let i = 0; i < readCount; i += 1) {
      await readBoxes.nth(i).fill(process.env.READ ?? (prefilled[i] || "0"));
    }
  }
  await page.click("button:has-text('Continue')");
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${OUT}/step3-${width}.png`, fullPage: true });
  const bill = await page.evaluate(() => {
    const refusal = document.querySelector("[data-final-bill-unavailable]");
    // ⊕ The section is *The draft bill* (`draft-bill`) since 2026-10-11.
    const section = document.querySelector('[data-step-section="draft-bill"]');
    const rows = section === null ? 0 : section.querySelectorAll("tbody tr").length;
    return {
      reason: refusal === null ? null : refusal.getAttribute("data-final-bill-unavailable"),
      sentence: refusal === null ? null : (refusal.textContent ?? "").trim(),
      rows,
      hasSection: section !== null,
    };
  });
  check(`${width}: step 3 draws the draft-bill section`, bill.hasSection);
  // Either it priced (rows beyond the two money rows) or it SAYS WHY. What it
  // may never do is neither — which is what it did until today.
  const priced = bill.rows > 2;
  check(
    `${width}: the bill either prices or states the engine's reason`,
    priced || bill.sentence !== null,
    priced ? `priced, ${bill.rows} rows` : `refusal: ${(bill.sentence ?? "").slice(0, 90)}`,
  );
  // ⊕ `DEF-BIL-10052` — an unpriced draft says *The draft bill is not
  // generated.* with every missing value, and offers *Back to readings*.
  if (bill.reason === "values_missing") {
    const missing = await page.locator("[data-final-bill-missing] li").allTextContents();
    check(
      `${width}: not generated — names the missing values and offers Back to readings`,
      (bill.sentence ?? "").startsWith("The draft bill is not generated.") &&
        missing.length > 0 &&
        (await page.locator("[data-back-to-readings]").count()) === 1,
      JSON.stringify(missing),
    );
  }
  if (bill.reason !== null) {
    // ⛔ The CODE rides `data-` and is never text a clerk reads (B14 rule 32).
    const text = await page.evaluate(() => document.body.innerText);
    check(`${width}: the refusal CODE is not on screen`, !text.includes(bill.reason), bill.reason);
  }

  // ⛔ No rule id, no OQ, no DEF reaches a clerk (B14 rule 32).
  check(
    `${width}: no internal id is on screen`,
    !/\b(BR-[A-Z]{3}-\d+|OQ-\d+|DEF-[A-Z]*-?\d+)\b/.test(body),
    (body.match(/\b(BR-[A-Z]{3}-\d+|OQ-\d+|DEF-[A-Z]*-?\d+)\b/) ?? [""])[0],
  );

  await page.close();
}

await browser.close();
console.log(`\nscreenshots: ${OUT}`);
console.log(failures === 0 ? "WALKTHROUGH PASSED" : `WALKTHROUGH FAILED — ${failures} finding(s)`);
process.exit(failures === 0 ? 0 : 1);
