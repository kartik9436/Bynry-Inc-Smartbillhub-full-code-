#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-054 W4 tasks 2, 15, 17, 24 and 25 — partial posting reaches the
//           screen, the rejects file is offered twice, and BR-MET-057's
//           completeness bar gets a surface.
// Screens:  RDS-03 / S28 (Upload reads: stages 3, 4 and 5) · S27 (Cycles)
// Defects:  DEF-2731 (stage 4 said "Rows that will become readings: 0" over a
//           post that filed 5; the receipt's breakdown summed to 6 over 1) ·
//           DEF-2730 (the Cycles page divided READINGS by METERS and drew a
//           full 100 % bar on a cycle that was 83.3 % complete) ·
//           DEF-2732 (the coverage sentence double-counted) ·
//           DEF-2438 (`PlainTable`'s `[&_td]:text-left` beats `text-right`) ·
//           DEF-2439 (a `<caption>` with `display:block` renders BELOW thead)
// Rules:    BR-MET-940 (partial posting — PO: "all or nothing will not work") ·
//           BR-MET-941 (the rejects export) · BR-MET-129 (a warned reading
//           POSTS) · BR-MET-057 (cycle read-window drives expectations;
//           per-cycle completeness bar + chase list) · B4.4 ❄️ FROZEN (tier
//           thresholds scale with the prorated period) · BR-SHL-025 ·
//           B14 rules 4, 6 and 21 · hard-won law 2 (built is not wired) ·
//           hard-won law 6 (diff the RUNNING app)
// ───────────────────────────────────────────────────────
/**
 * Open the three surfaces this wave changed in a REAL browser and read what
 * comes back.
 *
 * ⚠ **WHY THIS EXISTS BESIDE FIFTEEN PASSING TEST CASES.** The PO's rule of
 * 2026-08-30: *"All UI screen should be confirm using real broswer testing and
 * not just based on test cases"*. And every defect this wave repairs was found
 * exactly this way and by nothing else — `DEF-2731` in particular was a LABEL
 * that was present, spelled correctly, translated into eleven languages, and
 * describing the wrong number. No type, no lint rule and no `toContain` can see
 * that; a person reading "Rows that will become readings: 0" beside a receipt
 * saying "Readings created: 5" can, in one second.
 *
 * ⚠ **AND B14 RULE 21's MIGRATION CLAUSE IS PER FILE.** A Tailwind utility in a
 * file that is not on `07-frontend/src/styles/route-b-migrated.txt` renders as
 * NOTHING while `tsc`, eslint and every class-name assertion pass. Only a
 * browser with a real style engine can tell a rendered utility from a class
 * name in the DOM, so the geometry assertions below read COMPUTED style.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is reading the
 * wrong bytes.
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A shared database
 * being reseeded looks exactly like a broken screen from in here, and cost a
 * sibling lane three runs on 2026-08-30. This harness was written against
 * **`smartbillhub_cr054w4`**, created for it and left in place.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   createdb smartbillhub_cr054w4
 *   DATABASE_URL=…/smartbillhub_cr054w4 python3 06-backend/manage.py migrate
 *   DATABASE_URL=…/smartbillhub_cr054w4 python3 06-backend/manage.py seed_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub_cr054w4" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8154 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4354 API_PROXY_TARGET=http://127.0.0.1:8154 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4354 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr054-w4-partial-post.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  THE STAGE 3 → 4 FENCE IS GONE (task 15). A batch carrying an
 *      UNRESOLVED ERROR must still reach the Load stage. This is the check
 *      that would have caught the whole defect: the button was disabled.
 *   2  THE BANNER STATES, IT DOES NOT REFUSE. Both numbers on screen, no
 *      "cannot be posted", and `role=status` rather than `role=alert`.
 *   3  THE REJECTS DOWNLOAD IS OFFERED AT STAGE 3 (task 17, the PO's *"at
 *      loading stage itself"*) — and the URL it names really answers a CSV
 *      whose header carries `why_it_failed`, fetched rather than assumed.
 *      ⛔ **THIS CLAUSE WAS RED ON `DEF-2734` AND IS NOW GREEN — `2 vs 0`
 *      became `2 vs 2` (fixed 2026-08-31, 2.101.2).** It read 0 rows against a
 *      button saying 2 because both rejects routes streamed a lazy generator
 *      consumed after the tenant context had been cleared. The assertion was
 *      left FAILING rather than weakened, which is why the fix exists.
 *   4  THE COMMIT BUTTON NAMES ITS OWN NUMBER (task 15) and keeps the DANGER
 *      tier (B14 rules 4 and 6).
 *   5  STAGE 4's COMPOSITION IS HONEST (DEF-2731): `will-post` equals the
 *      readings the post then creates, measured across the click.
 *   6  THE COVERAGE SENTENCE ADDS UP (DEF-2732) — and it is the SERVER's own
 *      `batch_cycle_coverage` it is compared with, not only with itself, over a
 *      cycle whose expected count is greater than zero.
 *   7  THE RECEIPT OFFERS THE FILE AGAIN (task 17) and its breakdown no longer
 *      claims to compose the failures.
 *   8  THE CYCLES PAGE SHOWS COMPLETENESS AGAINST THE EXPECTED SET (task 24)
 *      and the chase list names the missing registers — each cell compared with
 *      `GET /cycles/{id}/chase-list`, which is BR-MET-057's own computation.
 *   9  A PERCENTAGE OVER 100 IS SHOWN, NOT CLAMPED (DEF-2730's second fault).
 *      The chase-list route is answered with `completeness_pct: "300.0"` and the
 *      page must print **300%**, announce it, and flag the bar — while the FILL
 *      stays at 100 %, because a 120px track cannot draw more. The server
 *      cannot produce this case (`collected_channels` is a subset of
 *      `expected_channels`), which is exactly why it is injected: the guard is
 *      about the screen refusing to present an impossible figure as a healthy
 *      one, and a full bar reading "100%" is what hid the readings-over-meters
 *      quotient for five days.
 *  10  NOTHING SCROLLS SIDEWAYS, and the utilities this change wrote actually
 *      COMPILED — read from computed style.
 *
 * ⚠ **TWO ASSERTIONS HERE ONCE COULD NOT FAIL, AND BOTH ARE FIXED IN PLACE.**
 * `shortCell === undefined || …` passed green when the deliberately-short cycle
 * was absent from the page, and `cov === null || …` passed over a screen that
 * printed no coverage sentence at all. Absence is now the failure it always was.
 * This is the same hole this file's own note two hundred lines down warns about
 * — *"0 = 0 = 0 satisfies all of them"* — arriving through a different door.
 */
import { existsSync, mkdirSync, readdirSync } from "node:fs";
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4354";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
// CY-002 is the cycle CR-054 W0 seeded with a time-of-use meter, a demand meter
// and one meter deliberately SHORT of its plan — so both the completeness table
// and the chase list have something to draw. Its CODE, not its id: the id
// changes on every reseed.
const CYCLE_CODE = process.env.SMOKE_CYCLE ?? "CY-002";
// ⚠ **THE READ DATE AND THE READINGS BOTH VARY PER RUN, DELIBERATELY.** Hard
// rule 6 is asserted both ways by the server: an identical re-upload of a
// posted batch is REFUSED (`already_posted_identical`), and a second reading at
// the same meter/date/register is a duplicate ERROR. A harness that posted the
// same bytes twice would therefore pass once and then report a broken screen
// for ever. The date walks a fortnight and the readings carry the run's own
// clock, so every run stages a file this database has not seen.
// ⚠ **REPEATABILITY IS NOT A DATE PROBLEM, AND FOUR DRAFTS SPENT TRYING TO
// MAKE IT ONE.** A reading is unique per (meter, date, register), so a second
// run on the same date is all duplicate ERRORS — the wizard then scores
// `Commit 0 rows ✓`, files nothing, and **every relational assertion below
// still passes**, because 0 = 0 = 0 satisfies *the button says what the strip
// says* and *the receipt says what the button said*. Reproduced four ways on
// this database: a date keyed off `getUTCDate()`, off the minute, off a
// 120-slot second hand that a third consecutive 40-second run wrapped onto,
// and finally off a random day in August — which failed for a DIFFERENT reason
// and is the useful finding:
//
//   · **a future date is refused outright** (`SMOKE_PERIOD=2027-03-15` filed
//     zero — the server has a horizon and enforces it per row); and
//   · **once a run has posted at a LATER date, an earlier one is out of
//     order**, so the usable window shrinks with every run rather than
//     cycling.
//
// **So the harness stops fighting the data and states its premise instead:
// stage 1's write mode is set to INSERT & UPDATE.** A duplicate then
// SUPERSEDES (BR-MET-016/053 — the commit appends a superseding read and
// closes the old head) rather than erroring, so one fixed date works on every
// run, for ever, against the same database. It also exercises the path a real
// corrections upload takes, which the `insert` default never reaches.
//
// The two unknown-meter rows are held whatever the mode, which is the
// behaviour under test.
const PERIOD = process.env.SMOKE_PERIOD ?? "2026-08-15";
const RUN_SALT = Date.now() % 90000;
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr054-w4-partial-post";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS = `Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)`;

/** Stage 3 — the statement that replaced the refusal. */
const READ_STAGE3 = `(() => {
  const split = document.querySelector('[data-reads="post-split"]');
  const footer = [...document.querySelectorAll('[data-workflow="footer"] button')].map((b) => ({
    text: (b.textContent || "").trim(),
    disabled: b.disabled,
    variant: b.getAttribute("data-variant"),
  }));
  const rejects = document.querySelector('[data-reads="rejects-review"]');
  const tiered = document.querySelector('[data-reads="tiered-date-warning"]');
  return {
    splitPresent: split !== null,
    splitRole: split ? split.getAttribute("role") : null,
    splitHold: split ? split.getAttribute("data-reads-hold") : null,
    splitText: split ? (split.textContent || "").replace(/\\s+/g, " ").trim() : null,
    // ⚠ COMPUTED, not the class attribute — a utility in a file off the Route B
    //   ledger is a class name with no rule behind it (B14 rule 21 / DEF-974).
    splitBorder: split ? getComputedStyle(split).borderTopWidth : null,
    splitPadding: split ? getComputedStyle(split).paddingTop : null,
    alerts: [...document.querySelectorAll('[role="alert"]')].map((el) =>
      (el.textContent || "").replace(/\\s+/g, " ").trim(),
    ),
    rejectsPresent: rejects !== null,
    rejectsButton: rejects
      ? (() => {
          const b = rejects.querySelector("button");
          return b ? { text: (b.textContent || "").trim(), disabled: b.disabled } : null;
        })()
      : null,
    rejectsNote: rejects ? (rejects.textContent || "").replace(/\\s+/g, " ").trim() : null,
    tieredPresent: tiered !== null,
    tieredText: tiered ? (tiered.textContent || "").replace(/\\s+/g, " ").trim() : null,
    footer,
    body: document.body.innerText || "",
  };
})()`;

/** Stage 4 — the composition, the coverage sentence and the commit button. */
const READ_STAGE4 = `(() => {
  const figures = [...document.querySelectorAll('[data-workflow-figure]')].map((el) => ({
    id: el.getAttribute("data-workflow-figure"),
    text: (el.textContent || "").replace(/\\s+/g, " ").trim(),
  }));
  const coverage = document.querySelector('[data-workflow="reads-coverage"]');
  const footer = [...document.querySelectorAll('[data-workflow="footer"] button')].map((b) => ({
    text: (b.textContent || "").trim(),
    disabled: b.disabled,
    variant: b.getAttribute("data-variant"),
  }));
  return {
    figures,
    coverage: coverage ? (coverage.textContent || "").replace(/\\s+/g, " ").trim() : null,
    footer,
    writes: (document.querySelector('[data-workflow="footer"]') || {}).dataset?.writes ?? null,
    body: document.body.innerText || "",
  };
})()`;

/** Stage 5 — the receipt. */
const READ_STAGE5 = `(() => {
  const rejects = document.querySelector('[data-reads="rejects-receipt"]');
  return {
    rejectsPresent: rejects !== null,
    rejectsText: rejects ? (rejects.textContent || "").replace(/\\s+/g, " ").trim() : null,
    unresolved: (() => {
      const el = document.querySelector('[data-reads="result-unresolved"]');
      return el ? (el.textContent || "").replace(/\\s+/g, " ").trim() : null;
    })(),
    body: document.body.innerText || "",
  };
})()`;

/** S27 — the completeness column and the chase list. */
const READ_CYCLES = `(() => {
  const heads = [...document.querySelectorAll("thead th")].map((th) => (th.textContent || "").trim());
  const cells = [...document.querySelectorAll('[data-reads="cycle-completeness"]')].map((el) => ({
    missing: el.getAttribute("data-reads-missing"),
    text: (el.textContent || "").replace(/\\s+/g, " ").trim(),
    barWidth: (() => {
      const fill = el.querySelector('[role="img"] > span');
      return fill ? fill.style.width : null;
    })(),
    // The bar is Tailwind utilities; COMPUTED height proves they drew.
    barHeight: (() => {
      const bar = el.querySelector('[role="img"]');
      return bar ? getComputedStyle(bar).height : null;
    })(),
    // ⛔ DEF-2730's clamp — what the bar SAYS, beside what it draws.
    barLabel: (() => {
      const bar = el.querySelector('[role="img"]');
      return bar ? bar.getAttribute("aria-label") : null;
    })(),
    overFlag: (() => {
      const bar = el.querySelector('[role="img"]');
      return bar ? bar.getAttribute("data-reads-over") : null;
    })(),
  }));
  const chase = document.querySelector('[data-reads="chase-list"]');
  return {
    heads,
    cells,
    chasePresent: chase !== null,
    chaseCycle: chase ? chase.getAttribute("data-reads-cycle") : null,
    chaseRows: chase
      ? [...chase.querySelectorAll("tbody tr")].map((tr) =>
          [...tr.children].map((td) => (td.textContent || "").replace(/\\s+/g, " ").trim()),
        )
      : [],
    daysAlign: (() => {
      const cell = document.querySelector('[data-reads="chase-list"] tbody td:last-child');
      return cell ? getComputedStyle(cell).textAlign : null;
    })(),
    body: document.body.innerText || "",
  };
})()`;

/**
 * ⛔ **DEF-2730 — THE SERVER'S OWN ANSWER, FETCHED FROM INSIDE THE PAGE.**
 *
 * The defect was a number that agreed with everything on the screen and with
 * nothing off it: `expected` (METERS) divided by `collected` (READINGS) is a
 * perfectly consistent quotient and it read 300 %, 500 % and 400 %. So the
 * only assertion that can see this class of fault compares the printed figure
 * with the figure the RULE computes — `GET /cycles/{id}/chase-list`, which is
 * BR-MET-057's own `expected_records` / `collected_records` /
 * `completeness_pct`. Same shape as task 15's *"the button said 5 and the post
 * created 5"*, one screen over.
 *
 * The session cookie is httpOnly and `credentials: "include"` is what the app's
 * own client sends, so the fetch runs in the page rather than in node.
 */
const READ_SERVED_COMPLETENESS = `(async () => {
  const tenant = location.pathname.split("/")[1];
  const get = async (path) => {
    const r = await fetch("/api/" + tenant + path, { credentials: "include" });
    if (!r.ok) return null;
    const body = await r.json();
    return body && body.data !== undefined ? body.data : body;
  };
  const cycles = (await get("/cycles")) || [];
  const rows = [];
  for (const cycle of Array.isArray(cycles) ? cycles : (cycles.results || [])) {
    // ⚠ **PASS THE PERIOD, exactly as the screen does.** Without it the route
    //   answers the CURRENT occurrence as of the tenant's today, which on the
    //   last day of a month is the NEXT window — every figure honestly zero,
    //   and a comparison against zeros proves nothing. The first draft of this
    //   probe omitted it and reported 0/0 for all six cycles beside a page
    //   printing "10 of 18".
    const period = cycle.window_start ? "?period=" + encodeURIComponent(cycle.window_start) : "";
    const chase = await get("/cycles/" + cycle.id + "/chase-list" + period);
    if (chase === null || chase.window === null || chase.window === undefined) continue;
    rows.push({
      code: cycle.code,
      expected: chase.expected_records || 0,
      collected: chase.collected_records || 0,
      missing: chase.missing_records || 0,
      pct: chase.completeness_pct,
    });
  }
  return rows;
})()`;

/**
 * ⛔ **DEF-2732 — `batch_cycle_coverage` FOR THE BATCH THE WIZARD IS ON.**
 * Served on `GET /read-batches/{id}`. Its own docstring names the trap the
 * screen fell into: *"a meter is missing only if NEITHER this batch nor a
 * committed head in the window covers it"* — so `received_in_batch` and
 * `committed_before_batch` OVERLAP and adding them is the defect.
 */
// ⚠ **A STRING `pageFunction` TAKES NO ARGUMENT.** Playwright evaluates a
//   string as an EXPRESSION and ignores the `arg`, so the first draft's
//   `page.evaluate(SERVED_BATCH_COVERAGE, stagedBatchId)` ran with `batchId`
//   undefined, fetched `/read-batches/undefined`, and came back `undefined` —
//   which the check then reported as *"the server answered no coverage
//   block"*. A harness fault wearing a product fault's clothes. The id is
//   interpolated into the expression instead, which is why this is a factory.
const SERVED_BATCH_COVERAGE = (batchId) => `(async () => {
  const batchId = ${JSON.stringify(batchId)};
  const tenant = location.pathname.split("/")[1];
  const r = await fetch("/api/" + tenant + "/read-batches/" + batchId, { credentials: "include" });
  // ⚠ A null here would be indistinguishable from "the batch has no cycle", so
  //   a failure says what failed. A probe that cannot explain itself sends the
  //   next lane looking at the screen instead of at the route.
  if (!r.ok) return { probe_failed: "HTTP " + r.status + " on /read-batches/" + batchId };
  const body = await r.json();
  const payload = body && body.data !== undefined ? body.data : body;
  if (!payload) return { probe_failed: "empty body" };
  if (!payload.cycle_coverage) {
    return { probe_failed: "no cycle_coverage", reason: payload.cycle_coverage_absent_reason ?? null };
  }
  return payload.cycle_coverage;
})()`;

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  page.on("pageerror", (e) => console.log(`   [pageerror] ${String(e).slice(0, 200)}`));
  // ⚠ **THE BATCH ID COMES FROM THE APP'S OWN STAGING RESPONSE.** There is no
  //   `GET /read-batches` list route — it answers 405 — and the number printed
  //   on the receipt is `batch_no`, not the id the results route takes. Reading
  //   the response the screen itself received is the only way to name the
  //   batch without inventing a route, and it is also the honest one: it is the
  //   same id the button is about to use.
  let stagedBatchId = null;
  page.on("response", (response) => {
    const url = response.url();
    if (!/\/read-batches$/.test(url) || response.request().method() !== "POST") return;
    response
      .json()
      .then((body) => {
        stagedBatchId = body?.data?.id ?? body?.id ?? stagedBatchId;
      })
      .catch(() => undefined);
  });

  console.log(`cr054-w4: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // ── S27 · THE CYCLES PAGE (task 24) ─────────────────────────────────────
  console.log("\n── S27 · cycles · completeness and the chase list ──");
  await page.goto(`${BASE}/${TENANT}/reads/cycles`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: join(OUT, "cycles.png"), fullPage: true });
  let cycles = await page.evaluate(READ_CYCLES);

  check(
    cycles.heads.includes("Completeness") && cycles.heads.includes("Meters"),
    `task 24 / DEF-2730: the columns are Meters and Completeness (${JSON.stringify(cycles.heads.slice(-4))})`,
  );
  check(
    !cycles.heads.includes("Collected") && !cycles.heads.includes("Progress"),
    "DEF-2730: the readings-over-meters quotient is gone from the page",
  );
  const scored = cycles.cells.filter((c) => /\d+ of \d+/.test(c.text));
  check(
    scored.length > 0,
    `task 24: at least one cycle states its completeness against the expected set (${JSON.stringify(scored.map((c) => c.text.slice(0, 40)))})`,
  );
  // ⛔ **DEF-2730's PROMISE-AGAINST-OUTCOME, THE SHAPE TASK 15's CHECK USES.**
  //   Every assertion in this block until now compares the page WITH ITSELF —
  //   a heading is present, a bar drew, a fraction parses. All of them passed
  //   on the readings-over-meters quotient, because a wrong number is as
  //   internally consistent as a right one. So the cell is compared against
  //   the SERVER's own answer for the same cycle: `GET /cycles/{id}/chase-list`
  //   is BR-MET-057's computation and the cell claims to be showing it.
  const servedCompleteness = await page.evaluate(READ_SERVED_COMPLETENESS);
  check(
    servedCompleteness.length > 0 && servedCompleteness.some((row) => row.expected > 0),
    `DEF-2730: the chase-list route answered for at least one cycle with a non-empty expected set (${JSON.stringify(servedCompleteness.map((r) => [r.code, r.collected, r.expected, r.pct]))})`,
  );
  for (const row of servedCompleteness) {
    if (row.expected === 0) continue;
    const onScreen = cycles.cells.find((c) => c.text.startsWith(`${row.collected} of ${row.expected}`));
    check(
      onScreen !== undefined,
      `DEF-2730: cycle ${row.code} prints the SERVER's pair — ${row.collected} of ${row.expected} (screen: ${JSON.stringify(cycles.cells.map((c) => c.text.slice(0, 24)))})`,
    );
    // ⚠ NUMERICALLY, not as a substring. The server sends `"100.0"` and the
    //   screen prints `100%` — BR-MET-144 trims trailing zeros — so a literal
    //   `includes("100.0%")` fails over a screen that is exactly right.
    const shown = Number((onScreen?.text?.match(/(\d+(?:\.\d+)?)%/) ?? [])[1]);
    check(
      Number.isFinite(shown) && shown === Number(row.pct),
      `DEF-2730: …and the SERVER's percentage, ${row.pct} — not one this screen derived (screen ${onScreen?.text?.slice(0, 60)})`,
    );
  }
  // ⚠ A BAR IS ONLY OWED WHERE A PERCENTAGE IS SERVED. `completeness_pct` is
  //   `null` when there is nothing to divide by (a cycle whose window expects
  //   no records), and a 0 % bar there would read as *"nothing collected"* over
  //   a cycle that owes nothing — the BR-SHL-020 posture the cell states in
  //   words instead. So the utility proof runs over the cells that DO score.
  const barred = cycles.cells.filter((c) => c.text.includes("%"));
  check(
    barred.length > 0 && barred.every((c) => c.barHeight !== null && parseFloat(c.barHeight) > 0),
    `B14 rule 21: the bar's utilities COMPILED (heights ${JSON.stringify(barred.map((c) => c.barHeight))})`,
  );
  check(
    cycles.cells.filter((c) => !c.text.includes("%")).every((c) => c.barHeight === null),
    "BR-SHL-020: a cycle with nothing to divide by draws NO bar rather than an empty one",
  );
  // ⛔ DEF-2730's own signature: a bar that reads 100 % on a short cycle. The
  //   fixture leaves CY-002 three records short, so a full bar there is the bug.
  // ⚠ **AND THE `undefined ||` THIS USED TO CARRY WAS A CHECK THAT COULD NOT
  //   FAIL.** *"no short cycle in this fixture"* passed green on a fixture that
  //   is built to contain one — the same class of hole as `0 = 0 = 0` two
  //   hundred lines below, and the reason this harness's own author wrote that
  //   warning. A short cycle must EXIST for this assertion to mean anything, so
  //   its absence is now the failure it always was.
  const shortCell = cycles.cells.find((c) => Number(c.missing) > 0);
  check(
    shortCell !== undefined,
    `DEF-2730: the fixture's deliberately-short cycle is on the page (missing counts ${JSON.stringify(cycles.cells.map((c) => c.missing))})`,
  );
  check(
    shortCell !== undefined && shortCell.barWidth !== "100%",
    `DEF-2730: a cycle with missing records does NOT draw a full bar (${shortCell?.barWidth ?? "no short cycle on the page"})`,
  );

  const chaseButton = await page.$('[data-reads="cycle-completeness"] button');
  if (chaseButton !== null) {
    await chaseButton.click();
    await page.waitForTimeout(1200);
    await page.screenshot({ path: join(OUT, "cycles-chase.png"), fullPage: true });
    cycles = await page.evaluate(READ_CYCLES);
    check(cycles.chasePresent, "task 24 / BR-MET-057: the chase list opens from the cell that counts it");
    check(
      cycles.chaseRows.length > 0 && cycles.chaseRows.every((cells) => cells[4] !== ""),
      `task 24: every chase row NAMES the registers it still owes (${JSON.stringify(cycles.chaseRows.map((c) => c[4]))})`,
    );
    check(
      !JSON.stringify(cycles.chaseRows).includes("tou_"),
      "CR-054's own finding: the register is its business word, never its code",
    );
    // DEF-2438 — `[&&]` is what makes a cell right-align in this kit.
    check(
      cycles.daysAlign === "right",
      `DEF-2438: the days-left column really is right-aligned (${cycles.daysAlign})`,
    );
  } else {
    check(false, "task 24: no cycle offered a chase list — the fixture should leave CY-002 short");
  }
  let sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `S27 does not scroll sideways (${sideways}px)`);

  // ── DEF-2730's SECOND FAULT · THE CLAMP ─────────────────────────────────
  // ⛔ **A CLAMP IS A CLAIM, AND THIS ONE WAS FALSE.** `ProgressBar` read
  //   `Math.min(100, progress)` and used that one number for the fill, the
  //   accessible label AND the printed figure, so 300 % drew a full bar,
  //   announced *"100 percent collected"* and printed **100%**. That is why the
  //   readings-over-meters quotient survived five days on three cycles: a full
  //   bar reads as good news. Replacing the quotient fixes today's number; only
  //   removing the clamp stops the NEXT wrong one hiding.
  //
  // ⚠ **THE SERVER CANNOT PRODUCE THE CASE, WHICH IS WHY IT IS INTERCEPTED.**
  //   `completeness.cycle_coverage` builds `collected_channels` as a SUBSET of
  //   `expected_channels`, so `completeness_pct` is ≤ 100 by construction today.
  //   The guard is not about today's server: it is about the screen refusing to
  //   present an impossible figure as a healthy one. So the route is answered
  //   with a percentage over 100 and the page is asked what it draws.
  await page.route("**/chase-list*", async (route) => {
    const response = await route.fetch();
    let body;
    try {
      body = await response.json();
    } catch {
      return route.fulfill({ response });
    }
    const payload = body && body.data !== undefined ? body.data : body;
    if (payload && payload.window && (payload.expected_records || 0) > 0) {
      payload.completeness_pct = "300.0";
    }
    return route.fulfill({ response, body: JSON.stringify(body) });
  });
  await page.goto(`${BASE}/${TENANT}/reads/cycles`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: join(OUT, "cycles-over-100.png"), fullPage: true });
  const over = await page.evaluate(READ_CYCLES);
  const overCell = over.cells.find((c) => c.text.includes("%"));
  check(
    overCell !== undefined && overCell.text.includes("300%"),
    `DEF-2730: a served 300% is PRINTED as 300%, not clamped away ("${overCell?.text?.slice(0, 60) ?? "no scored cell"}")`,
  );
  check(
    overCell !== undefined && !overCell.text.includes("100%"),
    `DEF-2730: …and the screen never states a percentage the server did not send ("${overCell?.text?.slice(0, 60) ?? "no scored cell"}")`,
  );
  check(
    overCell !== undefined && overCell.overFlag === "true",
    `DEF-2730: the over-100 bar is FLAGGED rather than drawn as a healthy full one (data-reads-over=${overCell?.overFlag ?? "absent"})`,
  );
  check(
    overCell !== undefined && overCell.barWidth === "100%",
    `DEF-2730: the fill is still bounded by its own track — geometry, not a statement (${overCell?.barWidth ?? "none"})`,
  );
  // ⚠ ACCESSIBILITY IS HALF THE FIX: the label announced the clamped figure too.
  check(
    overCell !== undefined && /300 percent/.test(overCell.barLabel ?? ""),
    `DEF-2730: the accessible label announces the SERVED figure ("${overCell?.barLabel ?? "none"}")`,
  );
  await page.unroute("**/chase-list*");

  // ── S28 · WALK THE WIZARD WITH A DELIBERATELY BAD FILE ───────────────────
  console.log("\n── RDS-03 · stages 1–2 · a file with two unknown meters in it ──");
  await page.goto(`${BASE}/${TENANT}/reads/upload`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
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
  // ⚠ INSERT & UPDATE, for the reason the block at the top of this file gives:
  //   it makes a duplicate SUPERSEDE instead of erroring, which is what lets
  //   this harness run twice against one database.
  const upsert = await page.$('input[name="reads-write-mode"][value="upsert"]');
  check(upsert !== null, "stage 1 offers the two write modes (CR-042 / BR-MET-210)");
  if (upsert !== null) await upsert.check();
  await page.click('button:has-text("Transform →")');
  await page.waitForTimeout(2500);

  // The file is built from the SERVER's own reading sheet, so the register
  // vocabulary is the server's rather than this harness's — plus two rows for
  // meters that do not exist, which is CR-054's own worked case.
  const sheetUrl = `/api/${TENANT}/cycles/${cycle.value}/reading-sheet?period=${PERIOD.slice(0, 7)}`;
  const sheetAnswer = await page.request.get(`${BASE}${sheetUrl}`);
  const sheetBody = await sheetAnswer.text();
  const cols = sheetBody.split("\n")[0].split(",");
  const idx = (name) => cols.indexOf(name);
  const bodyRows = sheetBody.trim().split("\n").slice(1);
  const upload = [
    "meter_id,read_date,channel,reading",
    ...bodyRows.slice(0, 5).map((line, i) => {
      const cells = line.split(",");
      return [
        cells[idx("meter_id")],
        PERIOD,
        cells[idx("channel")],
        String(100000 + RUN_SALT + i * 37),
      ].join(",");
    }),
    `M-9999,${PERIOD},total,4242`,
    `M-9998,${PERIOD},total,4243`,
  ].join("\n");
  await page.fill("#reads-text", upload);
  await page.click('button:has-text("Stage the batch")');
  await page.waitForTimeout(3000);
  await page.click('button:has-text("Validate →")');
  await page.waitForTimeout(1500);
  await page.click('button:has-text("Run the rules")');
  await page.waitForTimeout(5000);
  await page.screenshot({ path: join(OUT, "stage3.png"), fullPage: true });

  console.log("\n── stage 3 · the statement that replaced the refusal ──");
  const s3 = await page.evaluate(READ_STAGE3);

  check(s3.splitPresent, "task 15: the post-split statement is on stage 3");
  check(
    s3.splitRole === "status",
    `task 15: it is a STATUS, not an alert — nothing here is blocked (role=${s3.splitRole})`,
  );
  check(
    /\d+ rows will post\. \d+ will not/.test(s3.splitText ?? ""),
    `task 15: it names BOTH numbers ("${(s3.splitText ?? "").slice(0, 70)}")`,
  );
  // ⛔ THE SENTENCE BR-MET-940 RETIRED. It was live at 2.94.0, in a
  //   `RefusalStrip`, above a disabled button.
  check(
    !s3.body.includes("cannot be posted") && !s3.body.includes("still need a decision before"),
    "task 15 / BR-MET-940: the all-or-nothing refusal is gone from stage 3",
  );
  check(
    parseFloat(s3.splitBorder ?? "0") > 0 && parseFloat(s3.splitPadding ?? "0") > 0,
    `B14 rule 21: the statement's utilities COMPILED (border=${s3.splitBorder}, padding=${s3.splitPadding})`,
  );

  // ── TASK 17, THE FIRST OFFER ──
  check(s3.rejectsPresent, "task 17: the rejects download is offered AT STAGE 3 (the PO's *at loading stage itself*)");
  check(
    s3.rejectsButton !== null && !s3.rejectsButton.disabled,
    `task 17: it is live once the rules have run ("${s3.rejectsButton?.text}")`,
  );
  // ⛔ DEF-2672 — reads cannot hand back the operator's own file, and the copy
  //   must not claim it does.
  check(
    (s3.rejectsNote ?? "").includes("It is not the spreadsheet you uploaded"),
    "task 17 / DEF-2672: the note does NOT promise the clerk their own file back",
  );

  // …and the file the button names really answers a CSV with the reason in it.
  // ⚠ **FETCHED FROM INSIDE THE PAGE.** `page.request` is a separate context
  //   and carries none of the app's session, so it answers the sign-in page
  //   rather than the resource — which reads as a broken endpoint.
  const csvProbe = await page.evaluate(
    async ([tenant, batchId]) => {
      if (batchId === null) return { found: false };
      const csv = await fetch(`/api/${tenant}/read-batches/${batchId}/results.csv?kind=failures`, {
        credentials: "include",
      });
      return { found: true, status: csv.status, body: await csv.text() };
    },
    [TENANT, stagedBatchId],
  );
  if (csvProbe.found) {
    const header = csvProbe.body.split("\n")[0];
    check(
      csvProbe.status === 200 &&
        header.includes("why_it_failed") &&
        header.includes("how_to_fix_it"),
      `task 17 / BR-MET-941: the failures route answers a CSV with the two reason columns (${csvProbe.status}, "${header.slice(0, 70)}")`,
    );
    const csvRows = csvProbe.body.trim().split("\n").length - 1;
    const namedOnButton = Number((s3.rejectsButton?.text.match(/(\d+)/) ?? [])[1]);
    // ⛔ **THIS ASSERTION FOUND `DEF-2734` — DO NOT WEAKEN IT.** It read
    //   `2 vs 0` for a day: both rejects routes wrapped a LAZY generator in a
    //   `StreamingHttpResponse`, and `TenantContextMiddleware` clears
    //   `app.tenant_id` in a `finally` the moment the view returns. WSGI
    //   consumes the body afterwards, so the generator's first query ran with
    //   no tenant GUC, RLS FORCE denied on unset, and the file came back as a
    //   HEADER AND NO ROWS — which reads as *"nothing was rejected"*, the exact
    //   DEF-320 failure `read_rejects` cites as its reason for refusing rather
    //   than serving an empty file. **Fixed 2026-08-31 (2.101.2):** both routes
    //   build their body through `core.tenancy.stream_within_tenant_context`,
    //   `G58` refuses a `StreamingHttpResponse` under `06-backend/apps/**`
    //   built any other way, and
    //   `06-backend/tests/test_def2734_streamed_tenant_context.py` holds the
    //   property on live Postgres under a role RLS actually applies to.
    //
    // ⚠ **IT PASSED TWICE ON THIS SAME DATABASE AN HOUR BEFORE IT CAUGHT IT**,
    //   because the role was still SUPERUSER — a superuser bypasses RLS
    //   completely, FORCE included, while every table still reports
    //   `relrowsecurity=t`. A sibling lane revoked that bit between the runs
    //   (`DEF-2717`, same root cause one route over). **That cuts both ways, so
    //   check the role's posture before believing a GREEN run here too:**
    //     select rolsuper, rolbypassrls from pg_roles where rolname=current_user;
    if (csvRows === 0 && namedOnButton > 0) {
      console.log(
        "   ⚠ this is DEF-2734's signature — a streamed rejects file consumed " +
          "outside the tenant context. Confirm the database role does NOT bypass RLS " +
          "before reading it as a harness fault, and check the route still builds its " +
          "body through core.tenancy.stream_within_tenant_context (G58).",
      );
    }
    check(
      csvRows === namedOnButton,
      `task 17 / law 5: the number on the button IS the number of rows in the file (${namedOnButton} vs ${csvRows}) — the check that found DEF-2734`,
    );
  } else {
    check(false, "no POST /read-batches response was seen, so the batch id is unknown");
  }

  // ── TASK 15's CENTRAL ASSERTION: THE FENCE IS GONE ──
  const loadButton = s3.footer.find((b) => b.text.includes("Load"));
  check(
    loadButton !== undefined && !loadButton.disabled,
    `task 15: stage 3 → 4 ADVANCES with unresolved errors on the batch (disabled=${loadButton?.disabled}) — this is the check that would have caught the whole defect`,
  );
  sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `stage 3 does not scroll sideways (${sideways}px)`);

  // ── STAGE 4 ─────────────────────────────────────────────────────────────
  console.log("\n── stage 4 · the composition, the coverage sentence, the button ──");
  await page.click('[data-workflow="footer"] button:has-text("Load")');
  await page.waitForTimeout(2500);
  await page.screenshot({ path: join(OUT, "stage4.png"), fullPage: true });
  const s4 = await page.evaluate(READ_STAGE4);

  const willPost = s4.figures.find((f) => f.id === "will-post");
  const willHold = s4.figures.find((f) => f.id === "will-hold");
  check(
    willPost !== undefined && willHold !== undefined,
    `DEF-2731: stage 4 states what will POST and what will be HELD (${JSON.stringify(s4.figures.map((f) => f.id))})`,
  );
  // ⛔ THE LABEL THAT WAS WRONG. It read "Rows that will become readings" over
  //   `counts.accepted`, which is 0 on a batch nobody has dispositioned — and
  //   five of those rows became readings.
  check(
    !s4.body.includes("Rows that will become readings"),
    "DEF-2731: the label that counted a person's ACCEPTS and called them readings is gone",
  );
  check(
    !s4.body.includes("Posting is all-or-nothing"),
    "task 15 / BR-MET-940: stage 4 no longer says posting is all-or-nothing",
  );
  check(
    !s4.body.includes("A row without a decision is not posted"),
    "BR-MET-129: the note contradicting *a warned reading posts* is gone",
  );
  // ⛔ DEF-2732 — measured on this very screen: "expects 5 … cover 5 … 1 have
  //   not been read". Covered + missing must equal expected.
  // ⚠ **THE `cov === null ||` THIS USED TO CARRY COULD NOT FAIL EITHER.** A
  //   sentence that stopped rendering, or whose wording moved a comma, made the
  //   regex miss and the check pass — over a screen that had said nothing at
  //   all. Absence is now the failure, and the three numbers are compared with
  //   the SERVER's own coverage for this batch rather than only with each
  //   other: internal consistency is exactly what the double-count had.
  const cov = (s4.coverage ?? "").match(/(\d+) of (\d+) meters covered\. (\d+) meters still unread/);
  check(
    cov !== null,
    `DEF-2732: the coverage sentence is on the screen and states three numbers ("${(s4.coverage ?? "none").slice(0, 110)}")`,
  );
  if (cov !== null) {
    const [covered, expected, missing] = [Number(cov[1]), Number(cov[2]), Number(cov[3])];
    check(
      expected > 0,
      `DEF-2732: …over a cycle that actually expects something (${expected}) — a sentence of zeroes adds up too`,
    );
    check(
      covered + missing === expected,
      `DEF-2732: the coverage sentence adds up (${covered} + ${missing} = ${expected})`,
    );
    // THE PROMISE AGAINST THE OUTCOME: `batch_cycle_coverage` is the rule's own
    // set difference and the screen claims to be printing it.
    const served =
      stagedBatchId === null
        ? null
        : ((await page.evaluate(SERVED_BATCH_COVERAGE(stagedBatchId))) ?? null);
    check(
      served !== null && (served.expected_meters ?? 0) > 0,
      `DEF-2732: the server answered a coverage block for this batch (${JSON.stringify(served)})`,
    );
    check(
      served !== null &&
        expected === served.expected_meters &&
        missing === served.missing_after_batch &&
        covered === served.expected_meters - served.missing_after_batch,
      `DEF-2732: the sentence is the SERVER's set difference, not a sum of two overlapping counters (screen ${covered}/${expected}/${missing} vs served ${served?.expected_meters}−${served?.missing_after_batch}, received_in_batch ${served?.received_in_batch} + committed_before ${served?.committed_before_batch})`,
    );
  }

  const commit = s4.footer.find((b) => b.variant === "danger");
  check(
    commit !== undefined && /Commit \d+ rows/.test(commit.text),
    `task 15: the commit button names its own number ("${commit?.text}")`,
  );
  // ⚠ ONE derivation feeds both, so they cannot disagree — and this is the
  //   assertion that proves it rather than assuming it (hard-won law 5).
  const buttonNumber = Number((commit?.text.match(/Commit (\d+) rows/) ?? [])[1]);
  const stripNumber = Number((willPost?.text.match(/(\d+)\s*$/) ?? [])[1]);
  check(
    Number.isFinite(buttonNumber) && buttonNumber === stripNumber,
    `task 15: the button and the strip state the SAME number (${buttonNumber} vs ${stripNumber})`,
  );
  check(s4.writes === "true", "B14 rules 4 and 6: the writing stage keeps its DANGER tier");
  sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `stage 4 does not scroll sideways (${sideways}px)`);

  const promisedPost = Number((commit?.text.match(/Commit (\d+) rows/) ?? [])[1]);

  // ── STAGE 5 ─────────────────────────────────────────────────────────────
  console.log("\n── stage 5 · the receipt, and whether the forecast was true ──");
  await page.evaluate(() => {
    const box = document.querySelector("#certified");
    if (box && !box.checked) box.click();
  });
  await page.waitForTimeout(500);
  await page.click('[data-workflow="footer"] button[data-variant="danger"]');
  await page.waitForTimeout(7000);
  await page.screenshot({ path: join(OUT, "stage5.png"), fullPage: true });
  const s5 = await page.evaluate(READ_STAGE5);

  const created = Number((s5.body.match(/Readings created\s*\n?\s*(\d+)/) ?? [])[1]);
  check(
    Number.isFinite(created) && created === promisedPost,
    `task 15 / DEF-2731: the button's promise was TRUE — it said ${promisedPost} and the post created ${created}`,
  );
  // ⛔ **THE CHECK THAT STOPS THIS HARNESS PASSING OVER A DEAD SCREEN.** Every
  //   assertion above is relational — *the button says what the strip says*,
  //   *the receipt says what the button said* — and 0 = 0 = 0 satisfies all of
  //   them. It happened: a second run on the same read date made all seven rows
  //   duplicates, the wizard scored `Commit 0 rows ✓`, and the run reported
  //   every check green over a post that filed nothing.
  check(
    created > 0,
    `the run actually FILED something (${created} readings). A 0 means the batch held every row — check that stage 1 really took INSERT & UPDATE, without which a re-run is all duplicates`,
  );
  check(
    Number.isFinite(created) && created < 7,
    "…and it HELD something too, which is the behaviour under test (two unknown meters are in the file on purpose)",
  );
  check(s5.rejectsPresent, "task 17: the receipt offers the file a SECOND time");
  check(
    (s5.rejectsText ?? "").includes("were not filed"),
    `task 17: …and it is the past tense there, not a forecast ("${(s5.rejectsText ?? "").slice(0, 60)}")`,
  );
  // ⛔ DEF-2731's second surface: "Of those: … 5 left without a decision" under
  //   a receipt that had just filed those five.
  check(
    !s5.body.includes("left without a decision"),
    "DEF-2731: the receipt no longer describes filed rows as failures",
  );
  check(
    s5.unresolved === null || /\d+ of them carried an error/.test(s5.unresolved),
    `task 15: the unresolved count is the SERVER's, stated as a fact ("${s5.unresolved ?? "none"}")`,
  );
  sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `stage 5 does not scroll sideways (${sideways}px)`);

  await browser.close();
  console.log(`\nscreenshots in ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s):`);
    for (const failure of failures) console.log(`   · ${failure}`);
    process.exit(1);
  }
  console.log("\n✓ every check passed");
})();
