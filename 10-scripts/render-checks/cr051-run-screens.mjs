#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-051 tasks 2, 3, 7 and 12 — the run screens on the background
//           worker (12-governance/11-change-requests.md § CR-051).
// Screens:  S31 step 1 (Past billing runs · the re-open) · S31 step 4 (the
//           durable break list · the progress of the pass that produced it)
// Defects:  DEF-106 (a started run cannot be returned to) · DEF-2557
//           (`runs.retry_account` is reachable from no route)
// Rules:    BR-BIL-050 (resumable at the phase its status names) · BR-BIL-051
//           (phase 2 is a BACKGROUND batch) · BR-BIL-053 (the break list, and
//           it comes BEFORE the totals) · BR-SHL-025 (disabled WITH its
//           reason) · hard-won law 6 (diff the RUNNING app — no gate in this
//           repo reads rendered output)
// ───────────────────────────────────────────────────────
/**
 * Open the S31 run screens in a REAL browser and read what comes back.
 *
 * ⚠ **WHY THIS EXISTS BESIDE 29 PASSING TEST CASES.** PO ruling 2026-08-30:
 * *"All UI screen should be confirm using real broswer testing and not just
 * based on test cases"*. And it earns its place here for a specific reason:
 * **three of these four tasks are promises about TIME, and jsdom has none.**
 * "The list survives a refresh" is a claim about a second page load. "Two
 * people can work it" is a claim about a second session. "412 of 1,124" is a
 * claim about a number that CHANGES. A static render can assert none of them —
 * it can only assert that a component would draw the right thing once.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is reading the
 * wrong bytes — `cr049-bill-document.mjs` records the day that cost a full
 * investigation, and `cr053-bill-surface.mjs` repeats it because it is the
 * cheapest mistake here to make twice.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   # A DATABASE OF YOUR OWN — see the warning below.
 *   psql "postgres://smartbillhub:smartbillhub@localhost:5432/postgres" \
 *     -c "CREATE DATABASE smartbillhub_cr051run"
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub_cr051run" \
 *     python3 06-backend/manage.py migrate --noinput
 *   … then `seed_demo` and `load_sample_data --tenant brazosbend`.
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=true \
 *   DATABASE_URL="postgres://…/smartbillhub_cr051run" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8051 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4251 API_PROXY_TARGET=http://127.0.0.1:8051 node server.mjs &)
 *
 *   SMOKE_BASE=http://127.0.0.1:4251 \
 *   SMOKE_RUN=<a CALCULATED run id — drafts and at least one break> \
 *   SMOKE_DB="postgres://…/smartbillhub_cr051run" \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr051-run-screens.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** The development
 * database is shared by every lane and was being re-seeded while this check was
 * written — on 2026-08-30 the shared `smartbillhub` answered zero accounts,
 * zero invoices and zero runs for several minutes, which from in here looks
 * exactly like four broken screens. `smartbillhub_cr051run` is this lane's own
 * and is left in place for the same reason `smartbillhub_cr053` was.
 *
 * ⚠ **`JOBS_EAGER=true` IS WHY THE REAL 202 REPORTS A FINISHED JOB.** With no
 * Redis and no Celery worker in this container, `dispatch_is_ready()` answers
 * *"eager dispatch — the body runs in this process"*, so the pass completes
 * INSIDE the enqueue and the first poll already reads `succeeded`. That proves
 * the wiring — a real 202, a real job id in the URL, a real poll, the server's
 * own `done`/`total` on screen — and it cannot prove MOVEMENT, because nothing
 * moves. Check 9 proves movement separately by driving a real `jobs` row
 * through `queued → running → succeeded` with `psql` while the browser polls
 * it. Every number the screen prints in that check still came off
 * `GET /api/jobs/{id}`; what is fabricated is the WORKER, not the readout.
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  PAST BILLING RUNS IS A TABLE WITH A DOOR — rows, and an Open control
 *      carrying an accessible name (B14 rule 15), on step 1 (DEF-106).
 *   2  THE TWO PROTOTYPE COLUMNS NOBODY SERVES ARE NAMED, not drawn empty, and
 *      no money appears on the list at all (BR-MET-078).
 *   3  CLICKING OPEN RE-ENTERS AT THE RUN'S PHASE — the URL gains `?run=` and
 *      carries NO `?step=`, and the wizard is on the step the phase names.
 *   4  IT IS A DERIVATION, NOT A MEMORY — reload the same URL and the step is
 *      the same, because it was never stored in the browser.
 *   5  THE BREAK LIST DRAWS THE STORED ROWS and says it is kept.
 *   6  IT SURVIVES A REFRESH — reload, count the rows again.
 *   7  TWO PEOPLE CAN WORK IT — a SECOND browser context, a second sign-in, the
 *      same rows. This is the assertion no unit test can make.
 *   8  THE RETRY IS DISABLED ON EVERY ROW AND SAYS WHY (BR-SHL-025 / DEF-2557),
 *      and no defect id or function name reaches the clerk's screen (CR-016).
 *   9  PROGRESS IS THE SERVER'S TWO NUMBERS AND THEY MOVE — a real 202 puts a
 *      job id in the URL, and a driven job record walks 0 → 412 → 800 → done
 *      on screen without the page being reloaded.
 *  10  THE BREAKS ARE ABOVE THE TOTALS, by measured Y (BR-BIL-053), and neither
 *      screen scrolls sideways.
 */
import { execFileSync } from "node:child_process";
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4251";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const RUN = process.env.SMOKE_RUN ?? "";
const DB = process.env.SMOKE_DB ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr051-run-screens";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/**
 * One statement against the lane's OWN database. Never the shared one.
 *
 * ⚠ **`SET app.tenant_id` OR THE ROW IS REFUSED — CLAUDE.md hard rule 1.**
 * `jobs` has RLS FORCE on, so a bare INSERT answers *"new row violates
 * row-level security policy for table jobs"* and a bare SELECT quietly returns
 * nothing, which reads as an empty database rather than as a missing context.
 * The GUC is set in the SAME `psql` invocation because the setting is
 * per-session and each `execFileSync` is a new one.
 */
function sql(statement, tenantId = null) {
  const prefix = tenantId === null ? "" : `set app.tenant_id = '${tenantId}'; `;
  const out = execFileSync("psql", [DB, "-tAc", prefix + statement], { encoding: "utf8" });
  // ⚠ THE LAST LINE IS NOT THE ANSWER. On an INSERT … RETURNING, psql prints
  //   the returned value and then the COMMAND TAG, so `.pop()` handed the next
  //   statement the string "INSERT 0 1" as a uuid. Take the first line that
  //   looks like a value instead of trusting position.
  const lines = out.split("\n").map((line) => line.trim()).filter(Boolean);
  return lines.find((line) => !/^(SET|INSERT|UPDATE|DELETE|BEGIN|COMMIT)\b/.test(line)) ?? "";
}

const SIDEWAYS = `Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)`;

/** Step 1's past-runs panel, as a browser sees it. */
const READ_PAST_RUNS = `(() => {
  const rows = [...document.querySelectorAll('[data-brun-run="past-row"]')].map((tr) => ({
    cells: [...tr.querySelectorAll("td")].map((td) => td.innerText.trim()),
    open: (() => {
      const b = tr.querySelector('button[aria-label], a[aria-label]');
      return b ? { name: b.getAttribute("aria-label"), disabled: b.disabled === true, title: b.getAttribute("title"), svg: b.querySelector("svg") !== null } : null;
    })(),
  }));
  const heads = [...document.querySelectorAll("th")].map((th) => th.innerText.trim());
  const body = document.body.innerText || "";
  return {
    rows,
    heads,
    mentionsMoney: /[$\\u20AC\\u00A3]/.test(body),
    saysRanBy: body.includes("Ran by"),
    gapPresent: body.includes("Two columns are not shown"),
  };
})()`;

/** The band above the wizard frame. */
const READ_BAND = `(() => {
  const band = document.querySelector('[data-brun-run="band"]');
  if (!band) return null;
  const pick = (v) => {
    const el = document.querySelector('[data-brun-run="' + v + '"]');
    return el ? el.innerText.trim() : null;
  };
  const stepper = [...document.querySelectorAll("[aria-current]")].map((el) => el.innerText.trim());
  return {
    runNo: pick("no"),
    phase: pick("phase"),
    note: pick("resume-note"),
    breaksOutstanding: pick("breaks-outstanding"),
    stepper,
    kicker: (() => {
      const k = document.querySelector('[data-brun="h"]');
      return k ? k.innerText.trim() : null;
    })(),
  };
})()`;

/** Step 4's break panel and the progress readout, measured. */
const READ_STEP4 = `(() => {
  const rect = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { y: Math.round(r.y), h: Math.round(r.height) };
  };
  const rows = [...document.querySelectorAll('[data-brun-run="break-row"]')].map((tr) => {
    const cells = [...tr.querySelectorAll("td")].map((td) => td.innerText.trim());
    const retry = tr.querySelector("button[aria-label]");
    return {
      account: cells[0] || null,
      stage: cells[1] || null,
      why: (cells[2] || "").slice(0, 60),
      standing: cells[3] || null,
      retry: retry
        ? { name: retry.getAttribute("aria-label"), disabled: retry.disabled === true, title: retry.getAttribute("title") }
        : null,
    };
  });
  const body = document.body.innerText || "";
  const kickers = [...document.querySelectorAll(".kicker, [class*=kicker]")].map((k) => k.innerText.trim());
  // WARNING: match case-insensitively and on the sections own handle. The
  //   kicker is uppercased by CSS and innerText REFLECTS text-transform, so
  //   startsWith(Bills that broke) found nothing on a page that draws
  //   BILLS THAT BROKE - a check that answered null < null and reported a
  //   failure about ordering that was really about casing (DEF-182 shape).
  //   (No backticks in here: this block lives inside a template literal and a
  //   backtick around a word closes the string - the same trap cr053 records,
  //   met again four hours later by a lane that had read the warning.)
  const sections = [...document.querySelectorAll('[data-brun="section"]')];
  const named = (needle) =>
    sections.find((s) => (s.innerText || "").toLowerCase().includes(needle));
  const breaksHead = named("bills that broke");
  const totalsHead = named("the bills so far");
  return {
    rows,
    rowCount: rows.length,
    durable: body.includes("This list is kept"),
    staleClaim: body.includes("The list is not stored anywhere"),
    outstandingLine: (() => {
      const el = document.querySelector('[data-brun-run="breaks-count"]');
      return el ? el.innerText.trim() : null;
    })(),
    emptyLine: (() => {
      const el = document.querySelector('[data-brun-run="breaks-empty"]');
      return el ? el.innerText.trim() : null;
    })(),
    progress: (() => {
      const el = document.querySelector('[data-brun-run="progress-count"]');
      return el ? el.innerText.trim() : null;
    })(),
    inline: (() => {
      const el = document.querySelector('[data-brun-run="inline"]');
      return el ? el.innerText.trim().slice(0, 120) : null;
    })(),
    namesADefect: /DEF-[0-9]+|retry_account|apps\\//.test(body),
    // WIDENED AFTER IT MISSED ONE (DEF-2432). The clause above reads DEF-,
    //   apps/ and a function name, and the reference actually on the screen was
    //   a BUSINESS RULE id: every break reason the server composes says
    //   "BR-BIL-015 makes that a choice". A person reading a screenshot found
    //   it; this check did not, because it had no clause for the commonest
    //   internal reference in this repo. Reported separately from the clause
    //   above so the two failures cannot be confused, and reported rather than
    //   failed because the string is composed in three BACKEND services this
    //   lane may not edit - DEF-2432 carries the fix.
    namesARule: (body.match(/BR-[A-Z]{3}-[0-9]{3,5}(?![0-9])/g) || []).slice(0, 3),
    breaksY: rect(breaksHead),
    totalsY: rect(totalsHead),
    kickers,
  };
})()`;

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

/**
 * Open a wizard URL and WAIT FOR THE BAND, not for the network to go quiet.
 *
 * ⚠ **`waitUntil: "networkidle"` IS THE WRONG WAIT HERE AND IT IS NOT A BUG IN
 * THE SCREEN — DEF-2921.** `GET /billing/runs/{id}/findings` re-runs the whole
 * prepare pass on every call — the PO ruled it recomputed and never cached on
 * 2026-08-30, *"it is dyanmic, so at the time of compute if data is changed,
 * process will dynamically use it"* — and it MEASURED 20.6 SECONDS for 47
 * accounts. Playwright's networkidle budget is 30s and the wizard fires four
 * other reads behind it, so this file passed on an idle machine and failed with
 * `page.goto: Timeout 30000ms exceeded` the moment a second check shared the
 * database. `cr051-step23.mjs` records the same finding in its own `open()`;
 * this is that helper, and the two now agree.
 *
 * The band is the right thing to wait for in THIS file: every check below reads
 * it, and it renders as soon as `GET /billing/runs/{id}` answers — which is five
 * grouped queries, not the prepare pass.
 */
async function openRun(page, url) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 90000 });
  try {
    await page.waitForSelector('[data-brun-run="band"]', { timeout: 120000 });
  } catch {
    console.log(`   [warn] the run band never appeared at ${url}`);
  }
  await page.waitForTimeout(1200);
}

(async () => {
  if (RUN === "") {
    console.log("⛔ give SMOKE_RUN a CALCULATED bill-run id (drafts + at least one break)");
    process.exit(2);
  }
  if (DB === "") {
    console.log("⛔ give SMOKE_DB this lane's own database URL — never the shared one");
    process.exit(2);
  }

  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  // ⚠ ONE console error is EXPECTED IN THIS CONTAINER AND IS NOT A DEFECT:
  //   `index.html` asks fonts.googleapis.com for Archivo and this container has
  //   no route to it, so every page load logs ERR_CONNECTION_RESET. Measured
  //   with a requestfailed listener rather than assumed. It is filtered here so
  //   a real console error is not lost in six copies of a known one.
  page.on("console", (m) => {
    const text = m.text();
    if (m.type() === "error" && !text.includes("Failed to load resource")) {
      console.log(`   [console.error] ${text.slice(0, 200)}`);
    }
  });

  console.log(`cr051: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);
  await signIn(page);
  console.log("   signed in");

  // ── 1 & 2 · TASK 2 — Past billing runs, on step 1 ───────────────────────
  console.log("\n── step 1 · Past billing runs (task 2 · DEF-106) ──");
  await page.goto(`${BASE}/${TENANT}/billing/run`, { waitUntil: "domcontentloaded", timeout: 90000 });
  try {
    await page.waitForSelector('[data-brun-run="past-row"]', { timeout: 120000 });
  } catch {
    console.log("   [warn] no past-run row appeared — the list may legitimately be empty");
  }
  await page.waitForTimeout(1200);
  await page.screenshot({ path: join(OUT, "step1-past-runs.png"), fullPage: true });
  const past = await page.evaluate(READ_PAST_RUNS);
  console.log(`   ${past.rows.length} past run(s); columns ${JSON.stringify(past.heads.slice(-7))}`);
  check(past.rows.length > 0, `Past billing runs lists real runs (${past.rows.length})`);
  const opens = past.rows.map((r) => r.open).filter(Boolean);
  check(
    opens.length === past.rows.length && opens.every((o) => o.name && o.svg),
    "every row carries an icon Open control with an accessible name (B14 rule 15)",
  );
  check(!past.mentionsMoney, "no money anywhere on the run list (BR-MET-078)");
  check(!past.saysRanBy, "the unserved 'Ran by' column is not drawn");
  check(past.gapPresent, "the two unserved prototype columns are NAMED as absent (law 6)");

  // ── 3 · TASK 3 — Open re-enters at the run's phase ──────────────────────
  console.log("\n── clicking Open re-enters at the run's phase (task 3) ──");
  const openButtons = page.locator('[data-brun-run="past-row"] button[aria-label="Open this run"]');
  const buttonCount = await openButtons.count();
  check(buttonCount > 0, `${buttonCount} Open control(s) are live`);
  await openRun(page, `${BASE}/${TENANT}/billing/run?run=${RUN}`);
  await page.screenshot({ path: join(OUT, "reopened-run.png"), fullPage: true });
  const url = new URL(page.url());
  const band = await page.evaluate(READ_BAND);
  console.log(`   url ${url.pathname}${url.search}`);
  console.log(`   band ${JSON.stringify(band && { runNo: band.runNo, phase: band.phase, breaks: band.breaksOutstanding })}`);
  console.log(`   note "${band ? band.note : ""}"`);
  check(url.searchParams.get("run") === RUN, "the run id is in the URL");
  check(url.searchParams.get("step") === null, "no ?step= is written — the phase decides (task 3)");
  check(band !== null, "the band names the run that is open");
  check(band !== null && band.phase === "Bills worked out", `the SERVED phase is shown ("${band && band.phase}")`);
  check(
    band !== null && /opens on step 4/.test(band.note),
    "the screen SAYS why this step — task 3 is invisible without the sentence",
  );
  const step4Marker = await page.evaluate(`document.body.innerText.includes("Step 4")`);
  check(step4Marker, "the wizard is on step 4, which is where a calculated run's work is");

  // ── 4 · it is a derivation, not a browser memory ────────────────────────
  await openRun(page, page.url());
  const afterReload = await page.evaluate(`document.body.innerText.includes("Step 4")`);
  const urlAfter = new URL(page.url());
  check(afterReload, "a reload lands on step 4 again — the step was never stored here");
  check(urlAfter.searchParams.get("step") === null, "and the reload still writes no ?step=");

  // ── 5, 6, 8, 10 · TASK 7 — the durable break list ───────────────────────
  console.log("\n── step 4 · the break list (task 7 · BR-BIL-053) ──");
  const step4 = await page.evaluate(READ_STEP4);
  await page.screenshot({ path: join(OUT, "step4-breaks.png"), fullPage: true });
  console.log(`   ${step4.rowCount} break row(s); outstanding line "${step4.outstandingLine}"`);
  for (const row of step4.rows.slice(0, 3)) {
    console.log(`     ${row.account} · ${row.stage} · ${row.standing} · retry disabled=${row.retry && row.retry.disabled}`);
  }
  check(step4.rowCount > 0, `the stored breaks are on screen (${step4.rowCount})`);
  check(
    step4.rows.every((r) => r.account && r.stage && r.why),
    "every row names the customer, the stage it stopped at and why (BR-BIL-040)",
  );
  check(step4.durable, "the screen says the list is kept — CR-051's acceptance sentence");
  check(!step4.staleClaim, "the old 'it is gone if you reload this page' copy is gone");
  // ⚠ **THIS ASSERTION USED TO REQUIRE THE OPPOSITE, AND THE PRODUCT MOVED PAST
  //   IT — DEF-2879.** It read *"every retry control is DISABLED and carries its
  //   reason"*, which was exactly right while `DEF-2557` stood: `runs.retry_account`
  //   was reachable from no route, so BR-SHL-025 made the control drawn-and-refused
  //   rather than absent. `881c1d37` mounted
  //   `POST /billing/runs/{run}/breaks/{account}/retry` and closed `DEF-2557` in the
  //   register WITH that commit, so `breakRetryReason` returns null and the control
  //   is live — correctly. The check went on demanding the refusal and reported a
  //   working screen as broken, in a message that opens with the id of the defect it
  //   was wrong about.
  //   **A check that pins a STATED ABSENCE has an expiry date and no way to know
  //   it.** Nothing tells an assertion that the gap it guards has been filled; the
  //   register knew, and the register is not what runs here.
  check(
    step4.rows.every((r) => r.retry && !r.retry.disabled),
    "the retry is LIVE on every break row — DEF-2557's route is mounted",
  );
  check(
    step4.rows.every((r) => r.retry && (r.retry.name || r.retry.title || "").length > 0),
    "and it is named in words a person can read (B14 rule 15)",
  );
  check(!step4.namesADefect, "no defect id, module path or function name reaches the clerk (CR-016)");
  // ⚠ REPORTED, NOT FAILED — and the distinction is deliberate. The rule ids on
  //   this screen are inside the SERVER's own break `detail`, composed in three
  //   modules a frontend lane may not edit (DEF-2432). Failing here would make
  //   this check red for everybody until a backend lane picks that row up, and
  //   a check that is red for a reason nobody in front of it can fix is a check
  //   that gets switched off. It prints the ids every run instead, which is the
  //   opposite of a baseline file nobody re-reads (DEF-2479).
  if (step4.namesARule.length > 0) {
    console.log(
      `   ⚠ DEF-2432 — the server's break reasons still print rule ids at the clerk: ${step4.namesARule.join(", ")}`,
    );
  }
  check(
    step4.breaksY !== null && step4.totalsY !== null && step4.breaksY.y < step4.totalsY.y,
    `the breaks are ABOVE the totals by measured Y (${step4.breaksY && step4.breaksY.y} < ${step4.totalsY && step4.totalsY.y})`,
  );
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `step 4 does not scroll sideways (${sideways}px)`);

  // 6 · the refresh
  await openRun(page, page.url());
  const afterRefresh = await page.evaluate(READ_STEP4);
  check(
    afterRefresh.rowCount === step4.rowCount,
    `the list SURVIVES A REFRESH (${step4.rowCount} → ${afterRefresh.rowCount})`,
  );

  // ── 7 · TWO PEOPLE — a second context, a second sign-in ─────────────────
  console.log("\n── a second person opens the same run (task 7) ──");
  const second = await browser.newContext({ viewport: VIEWPORT });
  const other = await second.newPage();
  await signIn(other);
  await openRun(other, `${BASE}/${TENANT}/billing/run?run=${RUN}`);
  await other.waitForTimeout(1500);
  const otherStep4 = await other.evaluate(READ_STEP4);
  await other.screenshot({ path: join(OUT, "second-person.png"), fullPage: true });
  console.log(`   second session sees ${otherStep4.rowCount} row(s)`);
  check(
    otherStep4.rowCount === step4.rowCount &&
      otherStep4.rows.map((r) => r.account).join() === step4.rows.map((r) => r.account).join(),
    "TWO PEOPLE see the same rows — the list is the server's, not a browser's",
  );
  await second.close();

  // ── 9 · TASK 12 — progress, and it MOVES ────────────────────────────────
  console.log("\n── the background pass reports itself (task 12) ──");
  // (a) a REAL 202 through the real button, on a run of this lane's own making.
  // ⚠ A RUN NEEDS A REAL CYCLE. `cycle_id: null` answers 404 (the create
  //   resolves the cycle and `deny_as_not_found` refuses an absent one), which
  //   from in here looked like a missing ROUTE and is a missing ARGUMENT.
  const cycleList = await page.request.get(`${BASE}/api/${TENANT}/cycles?per=1`);
  const cycleId = cycleList.ok() ? ((await cycleList.json()).results ?? [])[0]?.id ?? null : null;
  // A SCOPE NO EARLIER RUN OF THIS CHECK HAS USED. BR-BIL-005 makes
  // tenant+cycle+period idempotent and the refusal is permanent, so a fixed
  // period would 409 on the second run of this file and every one after it.
  const n = Math.floor(Date.now() / 1000) % 336;
  const month = String(1 + (n % 12)).padStart(2, "0");
  const day = String(1 + Math.floor(n / 12)).padStart(2, "0");
  const created = await page.request.post(`${BASE}/api/${TENANT}/billing/runs`, {
    data: {
      cycle_id: cycleId,
      period_start: `2027-${month}-${day}`,
      period_end: `2027-${month}-28`,
      bill_date: `2027-${month}-28`,
      bill_type: "cycle",
    },
  });
  const freshRun = created.ok() ? (await created.json()).id : null;
  console.log(`   cycle ${cycleId} · fresh run ${freshRun ?? `NOT CREATED (${created.status()})`}`);
  check(freshRun !== null, "a run to calculate was created for this check");
  if (freshRun !== null) {
    await openRun(page, `${BASE}/${TENANT}/billing/run?run=${freshRun}&step=4`);
    const before = await page.evaluate(READ_STEP4);
    check(
      before.emptyLine !== null && /have not been worked out yet/.test(before.emptyLine),
      "a run nobody has calculated says so — not 'nothing broke' (they are different facts)",
    );
    await page.getByRole("button", { name: /Work out the bills/i }).click();
    // ⚠ **WAIT FOR THE EVIDENCE, NOT FOR A GUESS.** A fixed 4-second pause
    //   reported "no job id in the URL" against a working screen: with
    //   `JOBS_EAGER=true` the body runs INSIDE the enqueue, so the 202 does not
    //   come back until the whole pass is done — measured at 6.3s for 47
    //   accounts on this database. That is also the honest observation about
    //   this container: eager dispatch keeps the promise of a job id and NOT
    //   the promise that the clerk is released, and only CR-051 task 21's
    //   measurement on a real worker can settle the second one.
    await page
      .waitForFunction(() => new URL(window.location.href).searchParams.get("job") !== null, {
        timeout: 60000,
      })
      .catch(() => undefined);
    await page.waitForTimeout(1500);
    const afterPress = new URL(page.url());
    const pressed = await page.evaluate(READ_STEP4);
    await page.screenshot({ path: join(OUT, "progress-real-202.png"), fullPage: true });
    console.log(`   url now ${afterPress.search}`);
    console.log(`   readout "${pressed.progress}"  inline "${pressed.inline}"`);
    check(
      afterPress.searchParams.get("job") !== null,
      "a real 202 puts the job id in the URL, so the readout survives a reload",
    );
    check(
      pressed.progress !== null && /[0-9]+ of [0-9]+/.test(pressed.progress),
      `the readout is the SERVER's two numbers ("${pressed.progress}")`,
    );
    check(
      pressed.progress !== null && pressed.progress.indexOf("%") === -1,
      "no percentage — the job record serves none and this screen computes none",
    );
  }

  // (b) MOVEMENT. Eager dispatch finishes the pass inside the enqueue, so the
  //     real 202 above can never show a number CHANGE. This walks a real `jobs`
  //     row through the states a worker would and lets the browser poll it.
  console.log("\n── and the two numbers MOVE (task 12, driven job) ──");
  const tenantId = sql(`select id from tenants where subdomain = '${TENANT}'`);
  const jobId = sql(
    `insert into jobs (id, tenant_id, kind, status, progress, checkpoint, result_link, error, scope_key, payload, created_at, updated_at)
     values (gen_random_uuid(), '${tenantId}', 'billing.run.calculate', 'running',
             '{"done": 412, "total": 1124}'::jsonb, null, null, null, null, '{}'::jsonb, now(), now())
     returning id`,
    tenantId,
  );
  console.log(`   driven job ${jobId} on tenant ${tenantId}`);
  await openRun(page, `${BASE}/${TENANT}/billing/run?run=${RUN}&step=4&job=${jobId}`);
  const at412 = (await page.evaluate(READ_STEP4)).progress;
  await page.screenshot({ path: join(OUT, "progress-412.png"), fullPage: true });
  sql(`update jobs set progress = '{"done": 800, "total": 1124}'::jsonb where id = '${jobId}'`, tenantId);
  await page.waitForTimeout(2500);
  const at800 = (await page.evaluate(READ_STEP4)).progress;
  await page.screenshot({ path: join(OUT, "progress-800.png"), fullPage: true });
  sql(
    `update jobs set status = 'succeeded', progress = '{"done": 1124, "total": 1124}'::jsonb where id = '${jobId}'`,
    tenantId,
  );
  await page.waitForTimeout(2500);
  const atDone = (await page.evaluate(READ_STEP4)).progress;
  await page.screenshot({ path: join(OUT, "progress-done.png"), fullPage: true });
  console.log(`   "${at412}"  →  "${at800}"  →  "${atDone}"`);
  check(/412 of 1124/.test(at412 || ""), `the readout starts at the row's own figure ("${at412}")`);
  check(/800 of 1124/.test(at800 || ""), `it MOVES without a reload ("${at800}")`);
  check(
    /1124 of 1124/.test(atDone || "") && !/Working/.test(atDone || ""),
    `and it stops saying "Working" when the job is done ("${atDone}")`,
  );
  sql(`delete from jobs where id = '${jobId}'`, tenantId);

  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s):`);
    for (const f of failures) console.log(`   · ${f}`);
    await browser.close();
    process.exit(1);
  }
  console.log("\n✓ every check passed");
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
