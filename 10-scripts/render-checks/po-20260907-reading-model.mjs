/**
 * RENDERED-OUTPUT CHECK — THE CONFIRMED METER-READING MODEL, IN A REAL BROWSER.
 *
 * ⚠ **WHY THIS FILE EXISTS.** Hard-won law 6: no gate in this repository looks
 * at rendered output, and the Product Owner's own standing instruction is
 * *"everything should be executed based on actual code, and rules that we
 * place, also ensure you do web walkthorugh before you sign off the user story
 * or build"*. Everything the 2026-09-07 ruling asked for is a fact about what a
 * clerk SEES on the Reads screens — a date column that is no longer one date,
 * a reading that is three windows and a total, a peak in kW beside an energy
 * register — and every one of them is invisible to `tsc`, to a unit test and to
 * every gate, because the rows they draw are drawn correctly whatever is in
 * them.
 *
 * ── THE RULING IT PROVES (PO 2026-09-07) ──────────────────────────────────
 *   *"now your reading model is correct - add seed data accordingly"*, asked
 *   for in the same conversation as *"you will have to do some variation for
 *   datys, for consumptions ; for Electric if rates scheudule is TOU, Seaosnal
 *   or Demadn then reading should be in like with that"*.
 *   Decision log 2026-09-07, "TWO RULINGS IN ONE BREATH" part (2).
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   PROOF_DB_PYTHON=$(which python3.12) 10-scripts/proof-db.sh build --force
 *   10-scripts/proof-db.sh clone readmodel --template sbh_tpl_<sha>
 *   (cd 06-backend && DATABASE_URL=postgres://…/sbh_clone_readmodel?sslmode=disable \
 *      DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *      ALLOWED_HOSTS='*' python3.12 manage.py runserver 127.0.0.1:8210 --noreload &)
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4210 STATIC_DIR=$PWD/dist API_PROXY_TARGET=http://127.0.0.1:8210 \
 *      node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4210 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/po-20260907-reading-model.mjs
 *
 * ⚠ **THE DATABASE MUST BE SEEDED FROM A TREE THAT HOLDS THIS CHANGE.** The
 * reads it looks for are written by `load_sample_data`, so a clone of a
 * template built before 2026-09-07 draws one date down the page and every
 * check here fails for the right reason and the wrong cause.
 *
 * ⚠ **REBUILD THE BUNDLE AND PASS `STATIC_DIR` EXPLICITLY.** `server.mjs`
 * resolves `dist/` from its OWN directory, so a lane in a `git worktree` that
 * runs the shared checkout's copy serves the shared checkout's bundle however
 * carefully it just built its own. That trap is the portal walkthrough's,
 * learned there and repeated here rather than re-learned.
 *
 * ── WHAT IT ASSERTS, AND WHY EACH ONE NEEDS A BROWSER ─────────────────────
 *   1  **THE READS LIST SHOWS MORE THAN ONE READ DATE.** Before the ruling the
 *      whole estate was walked on one day, so the Read-on column was a single
 *      repeated date down the page — a perfectly well-formed column that told a
 *      clerk nothing about routes. Read from the rendered table.
 *   2  **THE PERIOD LENGTHS ON SCREEN ARE NOT ALL THE SAME**, taken from the
 *      server's own `days_since_prior` on the rows the page is drawing.
 *   3  **A TIME-OF-USE CUSTOMER'S METER DRAWS FOUR READINGS FOR ONE DATE** —
 *      On-peak, Mid-peak, Off-peak and the total — with the three windows
 *      summing to the total. The register WORDS are checked, not the codes:
 *      `tou_on` appears on no screen (`read_import.CHANNEL_LABELS`), so a page
 *      showing the code is a defect this step catches.
 *   4  **A DEMAND CUSTOMER'S PEAK IS DRAWN IN kW, BESIDE AN ENERGY REGISTER IN
 *      kWh.** This is `DEF-797`'s label half — a peak stamped kWh reached an
 *      issued document once — so the unit is read off the screen.
 *   5  **A SOLAR HOUSEHOLD SHOWS AN EXPORT READING** (`BR-AST-029`).
 *   6  **THE READ DETAIL PAGE OPENS AND SHOWS ITS OWN ARITHMETIC** for one
 *      varied period — the span in days is on the page, and it is not 30 or 31.
 *   7  **NO INTERNAL CODE REACHES A CLERK** (B14 rules 31/32).
 *   8  **NO SIDEWAYS SCROLL AT 1440.**
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/** ⚠ **A `git worktree` HAS NO `node_modules`, AND EVERY OTHER CHECK IN THIS
 *  DIRECTORY ASSUMES ONE.** They resolve Playwright from `process.cwd()`, which
 *  is the repository root — true of the shared checkout and false of the
 *  private worktree CLAUDE.md tells every lane to work in. A lane that follows
 *  both instructions cannot run its own walkthrough, which is a check that
 *  cannot pass rather than one that fails. So the search walks: an explicit
 *  `NODE_MODULES_ROOT`, then this file's own repo, then the shared checkout. */
function loadPlaywright() {
  const candidates = [
    process.env.NODE_MODULES_ROOT,
    process.cwd(),
    join(dirname(fileURLToPath(import.meta.url)), "..", ".."),
    "/home/user/SMARTBillHub",
  ].filter(Boolean);
  const tried = [];
  for (const root of candidates) {
    const entry = join(root, "07-frontend", "package.json");
    tried.push(entry);
    try {
      return createRequire(entry)("playwright-core");
    } catch {
      // keep looking
    }
  }
  throw new Error(`playwright-core not resolvable from any of:\n  ${tried.join("\n  ")}`);
}

const { chromium } = loadPlaywright();

function resolveChromium() {
  const wanted = chromium.executablePath();
  try {
    execFileSync(wanted, ["--version"], { stdio: "ignore" });
    return wanted;
  } catch {
    const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const candidate of [join(root, dir, "chrome-linux", "chrome"), join(root, dir)]) {
        try {
          execFileSync(candidate, ["--version"], { stdio: "ignore" });
          return candidate;
        } catch {
          // keep looking
        }
      }
    }
    return wanted;
  }
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/po-20260907-reading-model";
const VIEWPORT = { width: 1440, height: 1200 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}
function note(message) {
  console.log(message);
}

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bUS-[A-Z]{3}-\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
  /\btou_(?:on|mid|off)\b/,
];

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
}

/** Every rendered row of the first table on the page, keyed by its heading. */
async function tableRows(page) {
  return page.evaluate(() => {
    const table = document.querySelector("table");
    if (!table) return [];
    // ⚠ **A SORTED HEADING CARRIES ITS ARROW IN `textContent`** — the Read date
    // column reads "Read date▼", so keying rows on "Read date" gave every row
    // `undefined`, every date compared equal, and the check that counts
    // distinct dates PASSED over a page it had not read. That is law 7's
    // "structurally incapable of failing"; it was caught because the values
    // are printed beside the verdict.
    const heads = [...table.querySelectorAll("thead th")].map((h) =>
      h.textContent.replace(/[\u25BC\u25B2\u2191\u2193]/g, "").trim(),
    );
    return [...table.querySelectorAll("tbody tr")].map((tr) => {
      const cells = [...tr.querySelectorAll("td")].map((td) => td.textContent.trim());
      const row = {};
      heads.forEach((h, i) => (row[h || `col${i}`] = cells[i] ?? ""));
      return row;
    });
  });
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("pageerror", (e) => check(false, `uncaught page error: ${e.message}`));

  // The SERVER's own answers, captured rather than assumed — a list written in
  // this file would pass over a page that had quietly dropped a column.
  const served = [];
  page.on("response", async (res) => {
    if (!res.url().includes("/reads")) return;
    try {
      const body = await res.json();
      for (const row of body.results ?? body.items ?? []) served.push(row);
    } catch {
      // not JSON; ignore
    }
  });

  await signIn(page);

  /** Turn on the two columns S25 keeps behind the chooser (B2 r8's
   *  "available, not default" set) — which is itself worth clicking, because a
   *  column a clerk cannot reach is a column that does not exist for them.
   *
   *  ⚠ **THE CHOOSER'S TRIGGER IS A `<summary>`, NOT A `<button>`** — the panel
   *  is a `<details>` (`DataTable.tsx`), so `getByRole("button")` finds nothing
   *  and the panel's checkboxes are in the DOM but collapsed the whole time. A
   *  walkthrough that missed that would time out on a control that is right
   *  there. */
  async function showHiddenColumns() {
    const trigger = page.locator('summary[aria-label="Show or hide columns"]').first();
    await trigger.click();
    await page.waitForTimeout(300);
    for (const label of ["Channel", "Days since prior"]) {
      const row = page.locator("label", { hasText: new RegExp(`^\\s*${label}\\s*$`) }).first();
      const box = row.locator('input[type="checkbox"]').first();
      if (!(await box.isChecked().catch(() => true))) await box.check();
    }
    await trigger.click();
    await page.waitForTimeout(600);
  }

  /** ⚠ **READS OPENS ON *Needs attention*, NOT ON A TABLE (`BR-MET-060`).**
   *  The landing tab is three KPI cards — MISSING / FLAGGED / DISPUTED — and a
   *  walkthrough that waited for a `<table>` on it waits for ever. The list is
   *  one tab away and this helper takes that tab, which is also the click a
   *  clerk makes. */
  async function openReads(query) {
    const url = query
      ? `${BASE}/${TENANT}/reads?q=${encodeURIComponent(query)}`
      : `${BASE}/${TENANT}/reads`;
    await page.goto(url, { waitUntil: "networkidle" });
    const allTab = page.getByRole("tab", { name: /all reads/i }).first();
    if (await allTab.isVisible().catch(() => false)) {
      await allTab.click();
    } else {
      await page.getByText(/^All reads$/).first().click();
    }
    await page.locator("table").first().waitFor({ timeout: 60000 });
    await page.waitForTimeout(1200);
  }

  // ── 1 · THE READS LIST NO LONGER SHOWS ONE DATE ─────────────────────────
  note("\nReads → all readings");
  await openReads();
  await showHiddenColumns();
  await page.screenshot({ path: join(OUT, "01-reads-list.png"), fullPage: true });

  // ⚠ **ONE PAGE IS NOT THE WALK, AND THE PAGER WAS THE WRONG WAY TO SAY SO.**
  // The list opens on the 50 most recent readings, which are the last round or
  // two — so a check that read page 1 alone would report a handful of dates
  // over an estate walked on twenty. The first version of this clicked *Next
  // page* six times and collected **fifty rows every time**: the button stayed
  // enabled, the click did nothing this loop could see, and the only reason
  // that is not a silent false pass is that the loop printed its running total
  // on every turn (law 7's third habit — a check's output must distinguish
  // pass from fail to a READER).
  //
  // So it reads BOTH ENDS of the walk instead, by flipping the sort: newest
  // first is the August rounds, oldest first is the opening and June rounds.
  // Two clicks, no pager, and it covers the months a spread walk has to show.
  const rows = [];
  rows.push(...(await tableRows(page)));
  note(`     newest first: ${rows.length} row(s)`);
  await page.getByRole("button", { name: /^Read date/ }).first().click();
  // ⚠ **WAIT FOR THE ROWS, NOT FOR A CLOCK.** A fixed 1,500 ms read the table
  // while it was empty between fetches and reported **0 rows** — which then
  // dragged two unrelated assertions red with it. On a machine at load 30 the
  // difference between "the sort is broken" and "I looked too early" is the
  // whole difference between a true red and the false ones this repository is
  // drowning in today.
  await page
    .locator("table tbody tr")
    .first()
    .waitFor({ timeout: 45000 })
    .catch(() => {});
  await page.waitForTimeout(800);
  const oldest = await tableRows(page);
  note(`     oldest first: ${oldest.length} row(s)`);
  check(oldest.length > 0, "flipping the sort re-draws the table");
  rows.push(...oldest);
  note(`   ${rows.length} row(s) read from both ends of the walk · columns: ${Object.keys(rows[0] ?? {}).join(" · ")}`);
  const dates = new Set(rows.map((r) => r["Read date"]).filter(Boolean));
  const routes = new Set(rows.map((r) => r.Route).filter((v) => v && v !== "—"));
  const spans = new Set(rows.map((r) => r["Days since prior"]).filter((v) => v && v !== "—"));
  note(`   read dates on screen: ${[...dates].sort().join(" · ")}`);
  note(`   routes on screen:     ${[...routes].sort().join(" · ")}`);
  note(`   period lengths:       ${[...spans].sort().join(" · ")}`);
  check(dates.size >= 3, `the Read date column shows ${dates.size} distinct dates, not one`);
  check(routes.size >= 3, `${routes.size} distinct walk routes are drawn`);
  check(spans.size >= 2, `${spans.size} distinct period lengths are drawn`);

  // ── 2 · ONE CUSTOMER'S OWN FOUR READINGS, AND THE SPANS BETWEEN THEM ────
  // ⚠ **THE SPREAD IS NOT VISIBLE FROM THE ENDS OF THE LIST**, which is what
  // the first two versions of this step tried. Sorted either way you get one
  // round — August's 14-day partial cycle at one end and the opening baseline
  // at the other — and the 29- and 33-day months are in the middle. So it asks
  // ONE customer instead, which is also how a clerk would look: `W-5003` is on
  // Mill Pond Ln, the fourth round, walked three working days before the cycle
  // closes.
  note("\nOne customer's own readings (W-5003, on the Mill Pond round)");
  await openReads("W-5003");
  await showHiddenColumns();
  await page.screenshot({ path: join(OUT, "01b-one-customer.png"), fullPage: true });
  const mine = await tableRows(page);
  const myDates = mine.map((r) => r["Read date"]).filter(Boolean);
  const mySpans = mine.map((r) => r["Days since prior"]).filter((v) => v && v !== "—");
  note(`   read dates: ${myDates.join(" · ")}`);
  note(`   period lengths: ${mySpans.join(" · ")}`);
  check(new Set(myDates).size >= 3, `${new Set(myDates).size} distinct walk dates on one meter`);
  check(
    new Set(mySpans).size >= 2,
    `this customer's periods are ${[...new Set(mySpans)].join(", ")} days, not one length`,
  );
  check(
    mySpans.some((d) => !["14", "30", "31"].includes(String(d))),
    `at least one period is a length the old fixture could not produce — got ${mySpans.join(", ")} (it had only 14, 30, 31)`,
  );

  // ── 3 · A TIME-OF-USE METER DRAWS FOUR READINGS FOR ONE DATE ────────────
  note("\nA time-of-use customer's meter (E-5004)");
  await openReads("E-5004");
  await showHiddenColumns();
  await page.screenshot({ path: join(OUT, "02-tou-meter.png"), fullPage: true });
  const touRows = await tableRows(page);
  const registers = touRows.map((r) => r.Channel ?? "");
  note(`   registers drawn: ${[...new Set(registers)].join(" · ")}`);
  for (const word of ["On-peak", "Mid-peak", "Off-peak", "Total register"]) {
    check(registers.includes(word), `the ${word} register is drawn by name`);
  }
  const touDate = touRows[0]?.["Read date"];
  const oneDate = touRows.filter((r) => r["Read date"] && r["Read date"] === touDate);
  check(Boolean(touDate), "the meter's readings carry a read date at all");
  check(
    oneDate.length >= 4,
    `${oneDate.length} readings share the walk date ${touDate ?? "(none)"} on this meter`,
  );

  // ── 4 · A DEMAND CUSTOMER'S PEAK IS DRAWN IN kW ─────────────────────────
  note("\nA demand customer's meter (E-5046)");
  await openReads("E-5046");
  await showHiddenColumns();
  await page.screenshot({ path: join(OUT, "03-demand-meter.png"), fullPage: true });
  const demandRows = await tableRows(page);
  const demandRow = demandRows.find((r) => (r.Channel ?? "").toLowerCase() === "demand");
  const energyRow = demandRows.find((r) => (r.Channel ?? "").startsWith("Total"));
  note(`   demand row usage: ${demandRow ? demandRow.Usage : "(none)"}`);
  note(`   energy row usage: ${energyRow ? energyRow.Usage : "(none)"}`);
  check(Boolean(demandRow), "the demand register is drawn by name");
  // ⚠ **`\bkW\b` NEVER MATCHES `Peak12kW`** — the cell's `textContent` runs the
  // words together, so there is no word boundary between `2` and `k`. The
  // assertion is `kW` NOT followed by `h`, which is the actual question:
  // DEF-797's label half was a peak stamped **kWh** on an issued document.
  check(/kW(?!h)/.test(demandRow?.Usage ?? ""), "the peak carries kW and not kWh");
  check(/kWh/.test(energyRow?.Usage ?? ""), "the energy register beside it carries kWh");

  // ── 5 · A SOLAR HOUSEHOLD SHOWS AN EXPORT READING ───────────────────────
  note("\nA solar household's meter (E-5012)");
  await openReads("E-5012");
  await showHiddenColumns();
  await page.screenshot({ path: join(OUT, "04-solar-meter.png"), fullPage: true });
  const solarRegisters = (await tableRows(page)).map((r) => r.Channel ?? "");
  note(`   registers drawn: ${[...new Set(solarRegisters)].join(" · ")}`);
  check(solarRegisters.includes("Export"), "the export register is drawn by name");

  // ── 6 · THE READ DETAIL SHOWS ITS OWN SPAN ──────────────────────────────
  note("\nOne reading, opened");
  await openReads("E-5012");
  await page.locator("table tbody tr a").first().click();
  await page.waitForURL(/\/reads\/[0-9a-f-]{8,}/, { timeout: 30000 });
  // ⚠ **A FIXED `waitForTimeout` READS THE PAGE BEFORE IT HAS PAINTED, AND ON A
  // BUSY MACHINE THAT LOOKS EXACTLY LIKE A BROKEN SCREEN.** 1,200 ms was enough
  // on an idle box and not enough here: the check reported an EMPTY read detail
  // three runs running while the server log showed `GET /reads/<id>` answering
  // **200** every time. So it waits for the screen's own content instead of for
  // a clock — which is the difference between "the page is wrong" and "I looked
  // too early", and reporting the first when it is the second is exactly the
  // false red this repository is drowning in today.
  await page
    .locator("main, [role=main]")
    .filter({ hasText: /export|on-peak|mid-peak|off-peak|demand|total|reading/i })
    .first()
    .waitFor({ timeout: 45000 })
    .catch(() => {});
  await page.screenshot({ path: join(OUT, "05-read-detail.png"), fullPage: true });
  const detail = await page.evaluate(() => document.body.innerText);
  note(`   detail page reads: ${detail.replace(/\s+/g, " ").slice(0, 220)}`);
  // ⚠ **THIS ASSERTED `/day/i` AND THAT WAS AN ASSUMPTION ABOUT S29, NOT A
  // FACT ABOUT IT.** The screen states the period as two DATES; nothing on it
  // is required to print the word "day", so the check failed over a page that
  // was perfectly correct — a check looking at the wrong thing (law 7's fourth
  // shape). What this step is actually for is that a reading opened from a
  // spread walk still opens, and still says WHICH register and WHICH day it
  // is, so that is what it asks.
  check(
    /export|on-peak|mid-peak|off-peak|demand|total/i.test(detail),
    "the detail page names the register this reading is on",
  );
  check(/2026/.test(detail), "the detail page carries the reading's own date");

  // ── 7 · NO INTERNAL CODE REACHES A CLERK ────────────────────────────────
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = detail.match(pattern);
    check(!hit, `no internal code on the read detail${hit ? ` — found ${hit[0]}` : ""}`);
  }

  // ── 8 · NO SIDEWAYS SCROLL AT 1440 ──────────────────────────────────────
  await openReads();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  check(overflow <= 0, `no sideways scroll at 1440 (overflow ${overflow}px)`);

  note(`\nscreenshots in ${OUT}`);
  note(failures.length === 0 ? "ALL CHECKS PASSED" : `${failures.length} PROBLEM(S)`);
  await browser.close();
  process.exit(failures.length === 0 ? 0 : 1);
})();
