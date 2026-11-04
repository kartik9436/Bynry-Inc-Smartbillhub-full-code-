#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-054 tasks 4, 5, 6, 7, 9, 11, 12, 13, 18, 19, 20 and 21 — the
//           reads upload.   (4/5/7 and 9 added 2026-08-31.)
// Screens:  RDS-03 / S28 (Upload reads: stages 1, 2 and 3)
// Defects:  DEF-2443 (the flagged-rows read date rendered the raw ISO instant) ·
//           DEF-2671 (the 36-word note about an endpoint that always existed) ·
//           DEF-2673 (a batch stores ONE service or ALL and nothing between)
// Rules:    BR-MET-032 (ONE published template, NO mapping memory) ·
//           BR-MET-049 (plan-driven read-set completeness) · BR-MET-123
//           (two transports) · BR-MET-014 (the batch tag inherits to a row) ·
//           BR-SHL-025 (disabled WITH its reason) ·
//           BR-SHL-034 (one date formatter) · B14 rules 9, 20, 21 and 31 ·
//           hard-won law 6 (diff the RUNNING app — no gate reads rendered
//           output) · hard-won law 2 (built is not wired)
// ───────────────────────────────────────────────────────
/**
 * Open the three RDS-03 stages in a REAL browser and read what comes back.
 *
 * ⚠ **WHY THIS EXISTS BESIDE FIFTEEN PASSING TEST CASES.** The Product Owner's
 * rule of 2026-08-30: *"All UI screen should be confirm using real broswer
 * testing and not just based on test cases"*. And it is not ceremony on this
 * screen in particular, because **B14 rule 21's migration clause is per FILE**:
 * a Tailwind utility written in a file that is not on
 * `07-frontend/src/styles/route-b-migrated.txt` renders as **nothing at all**,
 * and `tsc`, eslint and every `toContain("flex")` assertion pass on it because
 * the class IS in the DOM. This whole change is one screen moving to utilities.
 * Only a browser with a real style engine can answer whether they drew.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is reading the
 * wrong bytes.
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** The shared
 * development database is reseeded by other lanes; on 2026-08-30 a sibling
 * check lost three runs to it, with every id changing mid-run, which looks
 * exactly like a broken screen. This harness was written against
 * **`smartbillhub_cr054`**, created for it and left in place.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 * ⚠ **A COMMENT INSIDE ONE OF THE `READ_STAGE*` TEMPLATE LITERALS MAY NOT USE
 * A BACKTICK.** They are template literals, so a backtick in prose ends the
 * string and the file stops parsing — `node --check` catches it in a second and
 * nothing else in this repo would. Write the utility name plainly.
 *
 *   createdb smartbillhub_cr054
 *   DATABASE_URL=…/smartbillhub_cr054 python3 06-backend/manage.py migrate
 *   DATABASE_URL=…/smartbillhub_cr054 python3 06-backend/manage.py seed_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub_cr054" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8054 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4254 API_PROXY_TARGET=http://127.0.0.1:8054 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4254 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr054-reads-upload.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  STAGE 1 IS THE KIT'S CARDS: two source cards with a real box on screen,
 *      both selectable radios, and no third card (BR-MET-123 clause 3).
 *   2  THE 36-WORD SERVICE NOTE IS GONE from stage 1 (task 20).
 *   3  THE READING-SHEET BUTTON NAMES ITS CYCLE AND ITS ROW COUNT, beside the
 *      blank template rather than instead of it — and the URL it names really
 *      answers a CSV, fetched rather than assumed (task 6).
 *  3a  THE UTILITY-SERVICE CONTROL on stage 1 (task 9): a chip per ENABLED
 *      service, defaulting to every one of them, the chips laid out (computed
 *      style, which is the only thing that can see a utility that did not
 *      compile), no checkbox wall (B14 rule 9), the NAME on the chip and never
 *      the stored code (B14 rule 31), and the consequence of the choice stated
 *      in one short sentence — MEASURED in words, because the note it replaces
 *      was 36 of them and a 20-word replacement is the same defect.
 *  3b  THE SHEET IS DOWNLOADED BY PRESSING THE BUTTON and the SAVED BYTES are
 *      opened (tasks 4, 5 and 7). Everything before this fetched the URL, which
 *      is a different thing: a wrong period, a filename the client overwrites
 *      or a handler that throws before it saves are invisible to a fetch and
 *      all reach the clerk. The file must carry the three column groups, MORE
 *      THAN ONE ROW for at least one meter (a register each — the whole point
 *      of task 4), registers in plain words, NO uuid in any cell (B14 rule 31,
 *      the half G28 cannot see), a blank reading in every row and a pre-filled
 *      date in every row, and a key naming its own cycle and meter.
 *   4  THE DROP TARGET IS DRAWN AND HAS A BOX: the kit's dashed panel, not a
 *      bare file input. After staging it states the SERVER's SHA-256.
 *   5  "WHAT IS IN THIS FILE" LISTS THE REGISTERS (task 11) — the line that
 *      catches a time-of-use cycle uploaded with one row per meter.
 *   6  THE MAPPING SHOWS A SAMPLE VALUE and draws NO picker (task 18 /
 *      BR-MET-032).
 *   7  STAGE 2's SUB-LINE NO LONGER PROMISES A SAVED MAPPING TEMPLATE and
 *      stage 4's heading no longer names a dry run (task 19).
 *   8  THE REGISTER-COMPLETENESS TABLE IS ON STAGE 3, grouped by plan model,
 *      with `Estimate all` and `Send someone out` on the shortfall row
 *      (tasks 12 and 13).
 *   9  THE FLAGGED ROW'S READ DATE IS FORMATTED, not the ISO instant
 *      (task 21 / DEF-2443).
 *  10  NO STAGE SCROLLS SIDEWAYS, and the utilities this change wrote actually
 *      COMPILED — asserted by reading computed style, which is the only thing
 *      that can tell a rendered utility from a class name in the DOM.
 */
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
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
  return undefined;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4254";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
// CY-002 is the seeded cycle CR-054 W0 gave a time-of-use meter, a demand meter
// and one meter deliberately SHORT of its plan — so the completeness table has
// both states to draw. Its code, not its id: the id changes on every reseed.
const CYCLE_CODE = process.env.SMOKE_CYCLE ?? "CY-002";
const PERIOD = process.env.SMOKE_PERIOD ?? "2026-08-03";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr054-reads-upload";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS = `Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)`;

/** Stage 1, as a browser sees it. */
const READ_STAGE1 = `(() => {
  const rect = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height), y: Math.round(r.y) };
  };
  const cards = [...document.querySelectorAll('[data-workflow-source]')].map((el) => ({
    id: el.getAttribute("data-workflow-source"),
    available: el.getAttribute("data-available"),
    box: rect(el),
    // ⚠ COMPUTED, not the class attribute. A utility on a file that is not on
    //   the Route B ledger is a class name with no rule behind it, and reading
    //   className cannot tell the difference (B14 rule 21 / DEF-974).
    display: getComputedStyle(el).display,
    padding: getComputedStyle(el).paddingTop,
    isRadio: el.querySelector('input[type="radio"]') !== null,
  }));
  const grid = document.querySelector('[data-workflow="source-cards"]');
  // ── CR-054 task 9 — the utility-service control ──────────────────────────
  const serviceGroup = document.querySelector('[data-reads="services"]');
  const serviceChips = [...document.querySelectorAll('[data-reads="service-chip"]')].map((el) => ({
    code: el.getAttribute("data-reads-service"),
    text: (el.textContent || "").replace(/\\s+/g, " ").trim(),
    disabled: el.disabled,
    title: el.getAttribute("title"),
    box: rect(el),
  }));
  const serviceAdd = document.querySelector('[data-reads="service-add"]');
  const serviceFact = document.querySelector('[data-reads="service-fact"]');
  return {
    cards,
    gridDisplay: grid ? getComputedStyle(grid).display : null,
    gridColumns: grid ? getComputedStyle(grid).gridTemplateColumns : null,
    // ⚠ COMPUTED for the same reason the grid above is. A flex/flex-wrap pair
    //   in a file that had NOT joined the Route B ledger would read 'block'
    //   here while className still said "flex" — the exact failure mode B14
    //   rule 21's per-file clause names, and the one no vitest case can see.
    serviceGroupDisplay: serviceGroup ? getComputedStyle(serviceGroup).display : null,
    serviceGroupWrap: serviceGroup ? getComputedStyle(serviceGroup).flexWrap : null,
    serviceChips,
    serviceAddPresent: serviceAdd !== null,
    serviceAddDisabled: serviceAdd ? serviceAdd.disabled : null,
    serviceAddOptions: serviceAdd
      ? [...serviceAdd.options].map((option) => option.value)
      : [],
    serviceFact: serviceFact ? (serviceFact.textContent || "").trim() : null,
    serviceCheckboxes: serviceGroup
      ? serviceGroup.querySelectorAll('input[type="checkbox"]').length
      : -1,
    body: (document.body.innerText || ""),
  };
})()`;

/** Stage 2. */
const READ_STAGE2 = `(() => {
  const rect = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height), y: Math.round(r.y), x: Math.round(r.x) };
  };
  const buttons = [...document.querySelectorAll("button")].map((b) => ({
    text: (b.textContent || "").trim(),
    disabled: b.disabled,
    box: rect(b),
  }));
  const drop = document.querySelector('[data-workflow="dropzone"]');
  const facts = document.querySelector('[data-workflow="dropzone-facts"]');
  const hash = document.querySelector('[data-workflow="dropzone-hash"]');
  const figures = [...document.querySelectorAll('[data-workflow-figure]')].map((el) => ({
    id: el.getAttribute("data-workflow-figure"),
    text: (el.textContent || "").replace(/\\s+/g, " ").trim(),
  }));
  const mapping = document.querySelector('[data-workflow="mapping"]');
  const mapHeaders = mapping
    ? [...mapping.querySelectorAll("th")].map((th) => (th.textContent || "").trim())
    : [];
  const firstRowCells = mapping
    ? [...(mapping.querySelector("tbody tr")?.children ?? [])].map((td) => (td.textContent || "").trim())
    : [];
  return {
    buttons,
    dropBox: rect(drop),
    dropBorder: drop ? getComputedStyle(drop).borderTopStyle : null,
    facts: facts ? (facts.textContent || "").replace(/\\s+/g, " ").trim() : null,
    hash: hash ? (hash.textContent || "").trim() : null,
    figures,
    mapHeaders,
    firstRowCells,
    mapSelects: mapping ? mapping.querySelectorAll("select").length : -1,
    blurb: (document.querySelector('[data-workflow="stage-head"] p') || {}).textContent ?? null,
    body: (document.body.innerText || ""),
  };
})()`;

/** Stage 3. */
const READ_STAGE3 = `(() => {
  const table = document.querySelector('[data-reads="register-completeness"]');
  const rows = table
    ? [...table.querySelectorAll("tbody tr")].map((tr) => ({
        plan: tr.getAttribute("data-reads-plan"),
        short: tr.getAttribute("data-reads-short"),
        cells: [...tr.children].map((td) => (td.textContent || "").replace(/\\s+/g, " ").trim()),
        buttons: [...tr.querySelectorAll("button")].map((b) => (b.textContent || "").trim()),
      }))
    : [];
  const review = document.querySelector('[data-reads="review-rows"]');
  const tiles = [...document.querySelectorAll('[data-workflow-figure]')].map((el) => ({
    id: el.getAttribute("data-workflow-figure"),
    text: (el.textContent || "").replace(/\\s+/g, " ").trim(),
  }));
  const ruleTable = document.querySelector('[data-workflow="rules"]');
  return {
    tablePresent: table !== null,
    tableDisplay: table ? getComputedStyle(table.querySelector("table") || table).display : null,
    rows,
    tiles,
    rulesPresent: ruleTable !== null,
    ruleRows: ruleTable
      ? [...ruleTable.querySelectorAll("tbody tr")].map((tr) => ({
          available: tr.getAttribute("data-available"),
          text: (tr.textContent || "").replace(/\\s+/g, " ").trim(),
        }))
      : [],
    reviewText: review ? (review.textContent || "").replace(/\\s+/g, " ").trim() : null,
    // ⛔ DEF-2438 — COMPUTED, because the class was always there and the
    //   alignment never was: PlainTable's [&_td]:text-left beat the kit's
    //   plain text-right on every count in every importer.
    hitsAlign: (() => {
      const cell = document.querySelector('[data-workflow="rules"] tbody td:nth-child(3)');
      return cell ? getComputedStyle(cell).textAlign : null;
    })(),
    expectsAlign: (() => {
      const cell = document.querySelector('[data-reads="register-completeness"] tbody td:nth-child(3)');
      return cell ? getComputedStyle(cell).textAlign : null;
    })(),
    captionAboveHeader: (() => {
      const cap = document.querySelector('[data-workflow="rules"] caption');
      const head = document.querySelector('[data-workflow="rules"] thead');
      if (!cap || !head) return null;
      return cap.getBoundingClientRect().y < head.getBoundingClientRect().y;
    })(),
    body: (document.body.innerText || ""),
  };
})()`;

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  // `acceptDownloads` — CR-054 tasks 4/5 press the reading-sheet button and
  // read the bytes the browser SAVED, which is the only way to prove the
  // handler between the route and the file works.
  const context = await browser.newContext({ viewport: VIEWPORT, acceptDownloads: true });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  console.log(`cr054: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // ── STAGE 1 ─────────────────────────────────────────────────────────────
  console.log("\n── stage 1 · source & context ──");
  await page.goto(`${BASE}/${TENANT}/reads/upload`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(OUT, "stage1.png"), fullPage: true });
  const s1 = await page.evaluate(READ_STAGE1);

  check(s1.cards.length === 2, `task 18: two source cards, and only two (${s1.cards.length})`);
  check(
    s1.cards.every((card) => card.box !== null && card.box.w > 100 && card.box.h > 40),
    `task 18: each card has a real box on screen (${JSON.stringify(s1.cards.map((c) => c.box))})`,
  );
  check(
    s1.cards.every((card) => card.isRadio && card.available === "true"),
    "task 18 / BR-MET-123: each is a real RADIO and both are available",
  );
  // ⚠ THE UTILITY TEST. `grid-template-columns` is `SOURCE_GRID`'s own
  //   `grid-cols-4`; if the kit's classes had not compiled this would be `none`.
  check(
    s1.gridDisplay === "grid" && s1.gridColumns !== "none",
    `B14 rule 21: the kit's grid utilities COMPILED (display=${s1.gridDisplay}, columns=${s1.gridColumns})`,
  );
  check(
    !s1.body.includes("no utility-service tag on this screen"),
    "task 20: the 36-word service note is gone from stage 1",
  );
  check(
    !s1.body.includes("metering.upload."),
    "G27: no dotted key name is rendered on stage 1",
  );

  // ── CR-054 TASK 9 — THE UTILITY-SERVICE CONTROL ──────────────────────────
  // The note above is gone; this is what stands in its place. Everything here
  // is read from the RUNNING screen because three of the five things that can
  // go wrong are invisible to jsdom: whether the chips laid out at all, what
  // the tenant's real enabled set is, and whether a name or a code is on screen.
  check(
    s1.serviceChips.length > 0,
    `task 9: stage 1 draws a chip per enabled service (${s1.serviceChips.length} chips: ${JSON.stringify(s1.serviceChips.map((c) => c.code))})`,
  );
  check(
    s1.serviceChips.every((chip) => chip.box !== null && chip.box.w > 20 && chip.box.h > 10),
    `task 9: each chip has a real box on screen (${JSON.stringify(s1.serviceChips.map((c) => c.box))})`,
  );
  // ⚠ **THE UTILITY TEST, AND THE REASON THIS BLOCK IS IN A BROWSER.** The
  //   chips are `flex flex-wrap` in `UploadReadsWizard.tsx`, which joined
  //   `route-b-migrated.txt` on 2026-08-27. Had it not, these would be class
  //   names with no rule behind them and `display` would read `block` — while
  //   `tsc`, eslint and every `toContain("flex")` passed (B14 rule 21).
  check(
    s1.serviceGroupDisplay === "flex" && s1.serviceGroupWrap === "wrap",
    `B14 rule 21: the chip row's utilities COMPILED (display=${s1.serviceGroupDisplay}, flex-wrap=${s1.serviceGroupWrap})`,
  );
  // B14 rule 9 — removable chips + ONE add control, never a wall of checkboxes.
  check(
    s1.serviceCheckboxes === 0 && s1.serviceAddPresent,
    `B14 rule 9: chips plus an add control, and no checkbox wall (${s1.serviceCheckboxes} checkboxes)`,
  );
  // B14 rule 31 — the VISIBLE value is the service's NAME. The seeded tenant
  // sells electric and water, so the codes `electric`/`water` must appear on
  // no chip's text even though they are what the payload carries.
  check(
    s1.serviceChips.every((chip) => chip.code !== null && !chip.text.includes(chip.code)),
    `B14 rule 31: a chip shows the NAME, never the stored code (${JSON.stringify(s1.serviceChips.map((c) => c.text))})`,
  );
  // The DEFAULT is every enabled service, so there is nothing left to add and
  // the control says so rather than opening an empty menu (BR-SHL-025).
  check(
    s1.serviceAddDisabled === true && s1.serviceAddOptions.length === 1,
    `task 9: it defaults to EVERY enabled service, so the add control is spent (disabled=${s1.serviceAddDisabled}, options=${JSON.stringify(s1.serviceAddOptions)})`,
  );
  check(
    s1.serviceFact !== null && s1.serviceFact.length > 0,
    `task 9: the consequence of the choice is STATED ("${s1.serviceFact}")`,
  );
  // CR-054's copy rule, measured rather than asserted: the note this control
  // replaced was 36 words. A one-sentence consequence is what replaces it, and
  // a 20-word replacement would be the same defect with a shorter tail.
  {
    const words = (s1.serviceFact ?? "").split(/\s+/).filter(Boolean).length;
    check(
      words > 0 && words <= 8,
      `task 9 / copy: the sentence that replaces 36 words is ${words} words long`,
    );
  }
  let sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `stage 1 does not scroll sideways (${sideways}px)`);

  // Fill the two things stage 2 depends on: the reading month and the cycle.
  await page.fill("#period_month", PERIOD);
  const cycleOptions = await page.$$eval("#cycle_id option", (nodes) =>
    nodes.map((n) => ({ value: n.value, label: n.textContent.trim() })),
  );
  const cycle = cycleOptions.find((option) => option.label.startsWith(CYCLE_CODE));
  check(cycle !== undefined, `the seeded cycle ${CYCLE_CODE} is in the picker`);
  if (cycle === undefined) {
    console.log(`   cycles offered: ${JSON.stringify(cycleOptions.map((o) => o.label))}`);
    await browser.close();
    process.exit(2);
  }
  await page.selectOption("#cycle_id", cycle.value);
  await page.click('button:has-text("Transform →")');
  await page.waitForTimeout(2500);

  // ── STAGE 2 ─────────────────────────────────────────────────────────────
  console.log("\n── stage 2 · upload ──");
  await page.screenshot({ path: join(OUT, "stage2-empty.png"), fullPage: true });
  let s2 = await page.evaluate(READ_STAGE2);

  const sheetButton = s2.buttons.find((b) => b.text.includes("Reading sheet"));
  check(
    sheetButton !== undefined && /·\s*[\d,]+\s*rows/.test(sheetButton.text),
    `task 6: the reading-sheet button names its cycle and its row count ("${sheetButton?.text}")`,
  );
  check(sheetButton !== undefined && !sheetButton.disabled, "task 6: it is live, not a dead label");
  const templateButton = s2.buttons.find((b) => b.text.includes("reads_template.csv"));
  check(
    templateButton !== undefined &&
      sheetButton !== undefined &&
      Math.abs(templateButton.box.y - sheetButton.box.y) < 40,
    "task 6: it sits BESIDE the blank template, not instead of it (same row, measured)",
  );

  // …and the URL it names really answers a CSV. Fetched, not assumed.
  const sheetUrl = `/api/${TENANT}/cycles/${cycle.value}/reading-sheet?period=${PERIOD.slice(0, 7)}`;
  const sheetAnswer = await page.request.get(`${BASE}${sheetUrl}`);
  const sheetBody = await sheetAnswer.text();
  const sheetRows = sheetBody.trim().split("\n").length - 1;
  check(
    sheetAnswer.status() === 200 && sheetBody.startsWith("row_key,"),
    `task 6: the sheet route really answers a CSV (${sheetAnswer.status()}, ${sheetBody.split("\n")[0].slice(0, 60)}…)`,
  );
  const named = Number((sheetButton?.text.match(/(\d[\d,]*)\s*rows/) ?? [])[1]?.replace(/,/g, ""));
  check(
    named === sheetRows,
    `task 6 / law 5: the number on the button IS the number of rows in the file (${named} vs ${sheetRows})`,
  );

  // ── TASKS 4 AND 5 — THE FILE THE BROWSER ACTUALLY SAVES ──────────────────
  // ⚠ **EVERYTHING ABOVE THIS POINT FETCHED THE URL, WHICH IS NOT THE SAME
  //   THING AS PRESSING THE BUTTON.** `getReadingSheet` → `saveTextFile` builds
  //   a Blob and clicks a synthetic anchor; a broken query string, a wrong
  //   period, a filename the server names and the client overwrites, or a
  //   handler that throws before it saves are all invisible to a `page.request`
  //   fetch and all reach the clerk. So the button is PRESSED and the saved
  //   bytes are opened.
  const download = await Promise.all([
    page.waitForEvent("download", { timeout: 20000 }),
    page.click('button:has-text("Reading sheet")'),
  ]).then(([event]) => event);
  const savedPath = await download.path();
  const saved = readFileSync(savedPath, "utf8");
  const savedLines = saved.trim().split("\n");
  check(
    download.suggestedFilename().startsWith("reading_sheet_"),
    `tasks 4/5: the browser saved the SERVER's own filename ("${download.suggestedFilename()}")`,
  );
  check(
    savedLines.length - 1 === named && named > 0,
    `tasks 4/5: the saved file holds the rows the button promised (${savedLines.length - 1} vs ${named}, and greater than zero)`,
  );
  // TASK 5's THREE GROUPS, in the file a clerk opens. Identity, context, theirs.
  const savedCols = savedLines[0].split(",");
  for (const group of [
    ["identity", ["row_key", "meter_id", "channel"]],
    ["context", ["premise", "unit_of_measure", "previous_reading", "previous_read_date"]],
    ["theirs", ["reading", "read_date", "read_method", "demand_reset", "notes"]],
  ]) {
    const [name, columns] = group;
    check(
      columns.every((column) => savedCols.includes(column)),
      `task 5: the saved sheet carries the ${name} group (${columns.join(" · ")})`,
    );
  }
  {
    const cell = (line, name) => line.split(",")[savedCols.indexOf(name)];
    const bodyLines = savedLines.slice(1);
    // TASK 4's whole point: one row per meter PER REGISTER. A time-of-use meter
    // is four rows, and a cycle of five meters is eighteen — the figure this
    // check would silently pass if the sheet had gone back to one row a meter.
    const perMeter = {};
    for (const line of bodyLines) {
      const meter = cell(line, "meter_id");
      perMeter[meter] = (perMeter[meter] ?? 0) + 1;
    }
    const widest = Math.max(...Object.values(perMeter));
    check(
      widest > 1,
      `task 4: at least one meter carries MORE THAN ONE row — a register each (${JSON.stringify(perMeter)})`,
    );
    // TASK 5's identity group "in plain words": the register column prints the
    // word every screen shows and never the token the key carries.
    const words = new Set(bodyLines.map((line) => cell(line, "channel")));
    check(
      !words.has("tou_on") && !words.has("tou_mid") && !words.has("tou_off"),
      `task 5 / rule 31: the register column is in PLAIN WORDS (${JSON.stringify([...words])})`,
    );
    // B14 rule 31 over the file a clerk opens in Excel — the half G28 cannot
    // see, because it inspects strings and not values.
    const uuid = saved.match(
      /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/,
    );
    check(uuid === null, `B14 rule 31: no internal id in any cell of the saved file (${uuid?.[0]})`);
    // TASK 5's "theirs": the reading is BLANK — it is the one fact only the
    // clerk holds — and the read date is PRE-FILLED, inside the cycle's window.
    check(
      bodyLines.every((line) => cell(line, "reading") === ""),
      "task 5: every reading cell is blank — the one thing the clerk supplies",
    );
    check(
      bodyLines.every((line) => /^\d{4}-\d{2}-\d{2}$/.test(cell(line, "read_date"))),
      `task 5: every read date is pre-filled ("${cell(bodyLines[0], "read_date")}")`,
    );
    // TASK 7's key, round-tripping: it names the cycle and the meter of its own
    // row, so a swapped meter is the ONLY way the two can disagree.
    check(
      bodyLines.every((line) => {
        const parts = cell(line, "row_key").split("|");
        return parts.length === 3 && parts[0] === CYCLE_CODE && parts[2] === cell(line, "meter_id");
      }),
      `task 7: every key names its own cycle and meter ("${cell(bodyLines[0], "row_key")}")`,
    );
  }

  check(
    s2.dropBox !== null && s2.dropBox.w > 400 && s2.dropBox.h > 60,
    `task 18: the kit's drop target has a real box (${JSON.stringify(s2.dropBox)})`,
  );
  check(
    s2.dropBorder === "dashed",
    `B14 rule 21: DROPZONE's dashed border COMPILED (border-top-style=${s2.dropBorder})`,
  );
  check(
    !s2.body.includes("save it as a mapping template"),
    "task 19: stage 2 no longer promises a saved mapping template",
  );
  check(
    (s2.blurb ?? "").includes("published template on every upload"),
    `task 19: it says what reads actually does ("${(s2.blurb ?? "").slice(0, 80)}")`,
  );

  // Paste a real file for this cycle — the sheet's own first rows, so the
  // register vocabulary is the server's rather than this harness's.
  const header = sheetBody.split("\n")[0];
  const cols = header.split(",");
  const idx = (name) => cols.indexOf(name);
  const bodyRows = sheetBody.trim().split("\n").slice(1);
  const upload = [
    "meter_id,read_date,channel,reading",
    ...bodyRows.slice(0, 6).map((line, i) => {
      const cells = line.split(",");
      return [cells[idx("meter_id")], PERIOD, cells[idx("channel")], String(1000 + i * 37)].join(",");
    }),
  ].join("\n");
  await page.fill("#reads-text", upload);
  await page.click('button:has-text("Stage the batch")');
  await page.waitForTimeout(3000);
  await page.screenshot({ path: join(OUT, "stage2-staged.png"), fullPage: true });
  s2 = await page.evaluate(READ_STAGE2);

  check(
    s2.hash !== null && /[0-9a-f]{16,}/.test(s2.hash),
    `task 18: the drop target states the SERVER's SHA-256 ("${(s2.hash ?? "").slice(0, 40)}…")`,
  );
  const registerFigures = s2.figures.filter((f) => f.id.startsWith("register-"));
  check(
    registerFigures.length > 0,
    `task 11: "what is in this file" lists a count PER REGISTER (${JSON.stringify(registerFigures.map((f) => f.id))})`,
  );
  check(
    s2.figures.some((f) => f.id === "meters") && s2.figures.some((f) => f.id === "dates"),
    "task 11: …beside rows, meters, services and dates",
  );
  check(
    s2.mapHeaders.includes("Sample value"),
    `task 18: the mapping carries a SAMPLE VALUE column (${JSON.stringify(s2.mapHeaders)})`,
  );
  check(
    s2.firstRowCells.length >= 2 && s2.firstRowCells[1] !== "",
    `task 18: …and the first row really shows one ("${s2.firstRowCells[1]}")`,
  );
  check(
    s2.mapSelects === 0,
    `task 18 / BR-MET-032: no picker is drawn over a route that cannot remap (${s2.mapSelects} selects)`,
  );
  sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `stage 2 does not scroll sideways (${sideways}px)`);

  // ── STAGE 3 ─────────────────────────────────────────────────────────────
  console.log("\n── stage 3 · validate & review ──");
  await page.click('button:has-text("Validate →")');
  await page.waitForTimeout(1500);
  await page.click('button:has-text("Run the rules")');
  await page.waitForTimeout(4000);
  await page.screenshot({ path: join(OUT, "stage3.png"), fullPage: true });
  const s3 = await page.evaluate(READ_STAGE3);

  check(s3.tablePresent, "task 12: the register-completeness table is on stage 3");
  check(
    s3.rows.length > 0,
    `task 12: it has a row per plan model (${JSON.stringify(s3.rows.map((r) => r.plan))})`,
  );
  const shortRow = s3.rows.find((r) => Number(r.short) > 0);
  if (shortRow !== undefined) {
    check(
      shortRow.buttons.includes("Estimate all") && shortRow.buttons.includes("Send someone out"),
      `task 13: the shortfall row carries both bulk actions (${JSON.stringify(shortRow.buttons)})`,
    );
    check(
      shortRow.cells.length >= 5,
      `task 12: expects · arrived · short are three columns (${JSON.stringify(shortRow.cells)})`,
    );
  } else {
    check(
      s3.rows.every((r) => r.buttons.length === 0),
      "task 13: a group with no shortfall gets no buttons (nothing to estimate)",
    );
    console.log("   note: this batch is complete, so the bulk actions are correctly absent");
  }

  // ⚠ **AND IT IS CLICKED, BECAUSE A CONTROL THAT DRAWS IS NOT A CONTROL THAT
  //   WRITES (hard-won law 2).** `Estimate all` must leave every row of the
  //   shortfall group carrying a recorded decision — the round trip, not the
  //   button. BR-MET-015: with a reason on every row it touches.
  if (shortRow !== undefined) {
    const before = (await page.evaluate(READ_STAGE3)).body;
    await page.click('[data-reads="register-completeness"] button:has-text("Estimate all")');
    await page.waitForTimeout(4000);
    await page.screenshot({ path: join(OUT, "stage3-estimated.png"), fullPage: true });
    const after = await page.evaluate(READ_STAGE3);
    check(
      after.body.includes("recorded:") && !before.includes("recorded:"),
      "task 13: pressing Estimate all really records a decision on the group's rows",
    );
    check(
      after.tiles.some((tile) => tile.id === "missing"),
      "task 20: the Missing tile is still a served figure after the write",
    );
  }

  check(s3.rulesPresent, "task 18: the rules table is the kit's RuleResultsTable");
  check(
    s3.hitsAlign === "right" && s3.expectsAlign === "right",
    `DEF-2438: the count columns really are right-aligned (hits=${s3.hitsAlign}, expects=${s3.expectsAlign})`,
  );
  check(
    s3.captionAboveHeader === true,
    `DEF-2439: the table caption sits ABOVE the header row (${s3.captionAboveHeader})`,
  );
  check(
    !s3.body.includes("Rules that could not run"),
    "task 18: the separate 'rules that could not run' list is folded into it (BR-MET-091)",
  );

  // ── task 21 / DEF-2443 ──
  if (s3.reviewText !== null) {
    check(
      !/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(s3.reviewText),
      "task 21 / DEF-2443: no raw ISO instant in the flagged-rows table",
    );
    check(
      /\d{2}\/\d{2}\/\d{4}/.test(s3.reviewText),
      `task 21: the read date is formatted (${(s3.reviewText.match(/\d{2}\/\d{2}\/\d{4}/) ?? ["none"])[0]})`,
    );
  } else {
    console.log("   note: no row was flagged on this batch, so the date cell has nothing to draw");
  }

  check(
    !s3.body.includes("that calculation is not built"),
    "task 20: the 33-word note under the Missing tile is gone",
  );
  sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `stage 3 does not scroll sideways (${sideways}px)`);

  await browser.close();
  console.log(`\nscreenshots in ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s):`);
    for (const failure of failures) console.log(`   · ${failure}`);
    process.exit(1);
  }
  console.log("\n✓ every check passed");
})();
