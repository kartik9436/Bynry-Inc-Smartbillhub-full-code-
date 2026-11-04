#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-051 tasks 13–19 and 24 — the run wizard's steps 2, 3 and 4
//           (12-governance/11-change-requests.md § CR-051).
// Screens:  S31.2 (six sub-screens · the reads table · charges to add · the
//           bill-generation KPIs) · S31.3 (three families · the row decision) ·
//           S31 step 4 (the outlook band)
// Defects:  DEF-2705 (a recorded decision never reached the screen) ·
//           DEF-2706 (spec and glossary mean opposite things by Over charges) ·
//           DEF-2596 (nothing produces a late fee or an extra charge) ·
//           DEF-2438 (no count in the kit has ever been right-aligned) ·
//           DEF-2439 (a <caption> renders BELOW the header row)
// Rules:    BR-BIL-015 · BR-BIL-029 · BR-BIL-053 · BR-BIL-060 · BR-BIL-061 ·
//           BR-SHL-025 · B14 rule 31 (no database id on screen) ·
//           hard-won law 6 (diff the RUNNING app — no gate reads rendered output)
// ───────────────────────────────────────────────────────
/**
 * Open steps 2, 3 and 4 in a REAL browser and read what comes back.
 *
 * ⚠ **WHY THIS EXISTS BESIDE 32 PASSING TEST CASES.** PO ruling 2026-08-30:
 * *"All UI screen should be confirm using real broswer testing and not just
 * based on test cases"*. jsdom renders no layout at all, so a table can hold
 * every assertion in `CR051Step23.test.tsx` and still draw as a column of
 * unstyled text — which is precisely what a Tailwind utility in an unmigrated
 * file does, invisibly to tsc, eslint and every `toContain`.
 *
 * It earns its place for three specific things no static render can claim:
 *   * **the figures MOVE** — recording a decision and watching the KPI change
 *     WITHOUT a reload is the only proof `DEF-2705`'s fix works, and it is a
 *     claim about a second network round trip;
 *   * **the numbers are right-aligned** — `DEF-2438` says a plain `text-right`
 *     inside `PlainTable` loses to `[&_td]:text-left`, and only a measured
 *     `text-align` can tell the two apart;
 *   * **nothing scrolls sideways and the caption is not under the header**
 *     (`DEF-2439`) — both are geometry, and geometry is what jsdom has none of.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is reading the
 * wrong bytes. `cr049-bill-document.mjs` records the day that cost a full
 * investigation and `cr053-bill-surface.mjs` repeats it, because it is the
 * cheapest mistake here to make twice.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   # A DATABASE OF YOUR OWN — see the warning below.
 *   psql "postgres://smartbillhub:smartbillhub@localhost:5432/postgres" \
 *     -c "CREATE DATABASE smartbillhub_cr051w34"
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub_cr051w34" \
 *     python3 06-backend/manage.py migrate --noinput
 *   … then `seed_demo` and `load_sample_data --tenant brazosbend`.
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=true \
 *   DATABASE_URL="postgres://…/smartbillhub_cr051w34" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8071 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4271 API_PROXY_TARGET=http://127.0.0.1:8071 node server.mjs &)
 *
 *   SMOKE_BASE=http://127.0.0.1:4271 \
 *   SMOKE_RUN=<a run with exception rows — a missing read and a flagged one> \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr051-step23.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** The development
 * database is shared by every lane and is re-seeded without warning — on
 * 2026-08-30 the shared `smartbillhub` answered zero accounts, zero invoices and
 * zero runs for several minutes, which from in here looks exactly like four
 * broken screens. **This lane's own database is `smartbillhub_cr051w34`** and it
 * is left in place for the same reason `smartbillhub_cr051run` was.
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  SIX SUB-SCREENS, and each draws something DIFFERENT — a tab strip with
 *      six buttons, and six distinct bodies (task 13).
 *   2  THE READS TABLE IS ONE TABLE WITH A FILTER FOR EVERY SCENARIO, its chips
 *      carry counts, and clicking one narrows the table (task 14).
 *   3  EVERY QUANTITY CARRIES ITS UNIT and a service with no read shows its
 *      REASON, never a zero (CLAUDE.md rule 3).
 *   4  THE DECISION IS TAKEN ON THE ROW, nothing is pre-selected, and the
 *      selected option is the empty placeholder (BR-BIL-015/061).
 *   5  CHARGES TO ADD IS CHARGES TO ADD — the tab draws late fees and service
 *      charges, and NAMES the absence because nothing produces either today
 *      (tasks 15 + 18, DEF-2706, DEF-2596).
 *   6  SIX KPIs ABOVE STEP 2, each with a value, and four carrying a WORD as
 *      well as a colour (task 16).
 *   7  THE KPIs MOVE — record a decision, do NOT reload, and watch *Waiting on
 *      you* fall and *Decided* rise (task 16, DEF-2705). **The assertion no
 *      static render can make.**
 *   8  STEP 3 IS THREE FAMILIES, not fifteen tabs, with a case filter inside
 *      the open one, and the URL carries both (task 17, BR-SHL-011).
 *   9  THE OUTLOOK BAND on step 4 names what goes out and what is held, in
 *      words and colours, above the totals (task 19).
 *  10  GEOMETRY: every figure column is measurably RIGHT-ALIGNED (DEF-2438), no
 *      table has a caption under its header (DEF-2439), and no screen scrolls
 *      sideways at 1440.
 *  11  NO DATABASE ID AND NO INTERNAL REFERENCE reaches the clerk (B14 rule 31,
 *      CR-016) — reported separately for a rule id, because DEF-2432 composes
 *      those in three BACKEND services a frontend lane may not edit.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4271";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const RUN = process.env.SMOKE_RUN ?? "";
const DB = process.env.SMOKE_DB ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr051-step23";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/**
 * One statement against THIS LANE's database. Never the shared one.
 *
 * ⚠ **`case` IS A SQL RESERVED WORD.** `where case = '…'` is a syntax error,
 * and the column really is called `case` (`bill_run_decisions.case`), so it has
 * to be quoted. Worth stating because the error names the `=` rather than the
 * word, which sends a reader looking at the wrong half of the line.
 *
 * ⚠ **AND `SET app.tenant_id` OR THE ROW IS INVISIBLE — CLAUDE.md hard rule 1.**
 * RLS FORCE is on, so a bare SELECT returns NOTHING, which reads as "the
 * decision was never written" rather than as a missing context. The GUC is set
 * in the SAME psql invocation because the setting is per-session.
 */
function sql(statement, tenantId = null) {
  const prefix = tenantId === null ? "" : `set app.tenant_id = '${tenantId}'; `;
  const out = execFileSync("psql", [DB, "-tAc", prefix + statement], { encoding: "utf8" });
  const lines = out.split("\n").map((line) => line.trim()).filter(Boolean);
  return lines.find((line) => !/^(SET|INSERT|UPDATE|DELETE|BEGIN|COMMIT)\b/.test(line)) ?? "";
}

const SIDEWAYS = `Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)`;

/** Step 2's tab strip, its KPI strip and whichever sub-screen is open. */
const READ_STEP2 = `(() => {
  const text = (el) => (el ? el.innerText.trim() : null);
  const tabs = [...document.querySelectorAll('[role="tablist"][aria-label]')].map((strip) => ({
    label: strip.getAttribute("aria-label"),
    buttons: [...strip.querySelectorAll("button")].map((b) => b.innerText.trim()),
    active: (() => {
      const on = strip.querySelector('button[aria-selected="true"]');
      return on ? on.innerText.trim() : null;
    })(),
  }));
  const kpis = [...document.querySelectorAll(".kpi")].map((tile) => ({
    label: text(tile.querySelector(".k")),
    value: text(tile.querySelector(".v")),
    detail: text(tile.querySelector(".d")),
    word: (() => {
      const pill = tile.querySelector(".d .pill, .pill");
      return pill ? pill.innerText.trim() : null;
    })(),
  }));
  const body = document.body.innerText || "";
  return {
    tabs,
    kpis,
    kpiCount: kpis.length,
    readRows: document.querySelectorAll('[data-brun-s2="read-row"]').length,
    chargeRows: document.querySelectorAll('[data-brun-s2="charge-row"]').length,
    planRows: document.querySelectorAll('[data-brun-s2="plan-row"]').length,
    consumerRows: document.querySelectorAll('[data-brun-s2="consumer-row"]').length,
    readCount: text(document.querySelector('[data-brun-s2="read-count"]')),
    // DEF-2899 — the twelve reading scenarios are a <select> since the PO's
    // 2026-08-31 "the bill-run tabs are filters now", not a strip of buttons.
    // No backticks in this block: it is a template literal.
    readFilterOptions: (() => {
      const sel = document.querySelector('[data-brun-s2="read-filters"] select');
      return sel ? [...sel.options].map((o) => o.text.trim()) : null;
    })(),
    sections: [...document.querySelectorAll('[data-brun="section"]')].map((s) =>
      (s.innerText || "").split("\\n")[0].trim(),
    ),
    // DEF-2439 — a <caption> with display:block draws BELOW the header row.
    captions: [...document.querySelectorAll("table caption")].length,
    // DEF-2438 — a plain text-right on a <td> loses to [&_td]:text-left, so the
    //   only honest question is the COMPUTED alignment of a figure cell.
    figureAligns: [...document.querySelectorAll("td .tabular-nums, td span")]
      .filter((el) => el.className && String(el.className).includes("text-right"))
      .map((el) => getComputedStyle(el).textAlign),
    // B14 rule 31 (PO 2026-08-30) + CR-016. Read the VISIBLE text only: the
    //   ruling allows an id on title as evidence, so scanning the markup would
    //   be a check that cannot distinguish pass from fail (DEF-182).
    uuidOnScreen: (body.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi) || []).slice(0, 3),
    namesADefect: (body.match(/DEF-[0-9]+|apps\\/[a-z]+|_[a-z]+\\(\\)/g) || []).slice(0, 3),
    namesARule: (body.match(/BR-[A-Z]{3}-[0-9]{3,5}(?![0-9])/g) || []).slice(0, 3),
    sideways: ${SIDEWAYS},
    hasUnit: /\\b(kWh|kgal|therm|CCF|gal|kW)\\b/.test(body),
    // DEF-2899 — RunGap is a CLOSED <details> since B14 rule 32, so its
    // sentence is not in innerText. The summary is; the sentence is read from
    // the markup, which is where a closed <details> keeps it.
    // (No backticks in here: this whole block is a template literal, and one
    //  backtick in a comment ends it and refuses the file.)
    saysNoSource: [...document.querySelectorAll('[data-brun="gap"]')].some((el) =>
      (el.innerHTML || "").includes("no late fees or extra charges"),
    ),
    saysNoSourceTitle: body.includes("No charges are gathered yet"),
    chargeFilterOptions: (() => {
      const sel = document.querySelector('[data-brun-s2="charge-filters"] select');
      return sel ? [...sel.options].map((o) => o.text.trim()) : null;
    })(),
  };
})()`;

/** Step 3's families, its case filter and the per-row decision control. */
const READ_STEP3 = `(() => {
  const strips = [...document.querySelectorAll('[role="tablist"][aria-label]')].map((strip) => ({
    label: strip.getAttribute("aria-label"),
    buttons: [...strip.querySelectorAll("button")].map((b) => b.innerText.trim()),
    active: (() => {
      const on = strip.querySelector('button[aria-selected="true"]');
      return on ? on.innerText.trim() : null;
    })(),
  }));
  const selects = [...document.querySelectorAll('[data-brun-s3="decide"]')].map((sel) => ({
    name: sel.getAttribute("aria-label"),
    disabled: sel.disabled === true,
    title: sel.getAttribute("title"),
    value: sel.value,
    options: [...sel.options].map((o) => o.text),
    // DEF-2900 — the VALUES, because "nothing is pre-selected" is a question
    // about the placeholder's value and never about its words. (Template
    // literal: no backticks.)
    values: [...sel.options].map((o) => o.value),
  }));
  // DEF-2899 — step 3's families and its case filter are FilterSelects since
  // the PO's 2026-08-31 "the bill-run tabs are filters now" (35ae9e5b). They
  // were [role=tablist] strips when this file was written. No backticks here:
  // this block is a template literal and one would end it.
  const picker = (handle) => {
    const sel = document.querySelector('[data-brun-s2="' + handle + '"] select');
    if (!sel) return null;
    return {
      options: [...sel.options].map((o) => o.text.trim()),
      active: (sel.selectedOptions[0] || {}).text ? sel.selectedOptions[0].text.trim() : null,
      // DEF-2899 — the option VALUE is the family id, which is what the URL
      // names and what a reword cannot move. Assert this; print the words.
      activeValue: sel.value,
    };
  };
  return {
    strips,
    familyPicker: picker("families"),
    casePicker: picker("case-filters"),
    rows: document.querySelectorAll('[data-brun-s3="family-row"]').length,
    selects,
    kinds: [...document.querySelectorAll('[data-brun-s3="kind"]')].map((c) => c.innerText.trim()),
    bulk: (() => {
      const el = document.querySelector('[data-brun="selcount"]');
      return el ? el.innerText.trim() : null;
    })(),
    sideways: ${SIDEWAYS},
  };
})()`;

/** Step 4's outlook band, measured against the panels below it. */
const READ_STEP4 = `(() => {
  const rect = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { y: Math.round(r.y), h: Math.round(r.height) };
  };
  const text = (v) => {
    const el = document.querySelector('[data-brun-s4="' + v + '"]');
    return el ? el.innerText.trim() : null;
  };
  const band = document.querySelector('[data-brun-s4="outlook"]');
  const sections = [...document.querySelectorAll('[data-brun="section"]')];
  const named = (needle) =>
    sections.find((s) => (s.innerText || "").toLowerCase().includes(needle));
  return {
    band: rect(band),
    produced: text("outlook-produced"),
    held: text("outlook-held"),
    split: text("outlook-split"),
    absent: text("outlook-absent"),
    words: band ? [...band.querySelectorAll(".pill")].map((p) => p.innerText.trim()) : [],
    breaksY: rect(named("bills that broke")),
    totalsY: rect(named("the bills so far")),
    sideways: ${SIDEWAYS},
  };
})()`;

/**
 * Open a wizard URL and WAIT FOR THE DATA, not for the network to go quiet.
 *
 * ⚠ **`waitUntil: "networkidle"` TIMES OUT ON STEP 2 AND IT IS NOT A BUG IN THE
 * SCREEN.** `GET /billing/runs/{id}/findings` re-runs the whole prepare pass on
 * every call — the PO ruled it recomputed and never cached on 2026-08-30, *"it
 * is dyanmic, so at the time of compute if data is changed, process will
 * dynamically use it"* — and it MEASURED 20.6 SECONDS for 47 accounts on this
 * lane's own database. Playwright's networkidle budget is 30s and the wizard
 * fires four other reads behind it, so the check failed on the endpoint's
 * honesty rather than on anything drawn. Making the run faster is CR-051 task
 * 21's job and explicitly not a cache; waiting for the ELEMENT is this check's.
 */
async function open(page, url, selector) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 90000 });
  try {
    await page.waitForSelector(selector, { timeout: 120000 });
  } catch {
    console.log(`   [warn] ${selector} never appeared at ${url}`);
  }
  await page.waitForTimeout(700);
}

/**
 * ⚠ **WAIT FOR THE CONTENT, NOT FOR A CONTAINER THAT IS ALWAYS THERE.** The
 * first draft waited for `.kpi`, which renders IMMEDIATELY with a dash in every
 * tile while the findings pass is still running — so it returned in 700ms and
 * read six sub-screens with 0 rows each. Every check then failed, over a screen
 * that draws 47 rows perfectly at 22 seconds. That is DEF-182's shape exactly:
 * a check whose output could not distinguish "the screen is broken" from "the
 * screen has not been handed its data yet".
 *
 * So each sub-screen names the element that only exists once its OWN data has
 * arrived, and the two the server does not serve name the stated-absence panel
 * they legitimately draw instead of a row.
 */
const SETTLED = {
  consumers: '[data-brun-s2="consumer-row"]',
  plans: '[data-brun-s2="plan-row"]',
  reads: '[data-brun-s2="read-row"]',
  balances: '[data-brun="gap"]',
  credits: '[data-brun="gap"]',
  overcharges: '[data-brun="gap"]',
};

/**
 * Poll a KPI tile until it reaches `want`, or give up and return what it says.
 *
 * ⚠ **A SINGLE `waitForTimeout` CANNOT ASK "DID IT MOVE".** Recording a decision
 * invalidates the case read, and `GET .../exceptions` calls `prepared_for`,
 * which re-runs the whole prepare pass — the same pass that MEASURED 20.6s for
 * 47 accounts here. A 2.5-second sample therefore reported "waiting 2→2" over a
 * write that had succeeded, which is a false failure and exactly the kind of
 * check DEF-182 says is worse than none. Poll, and say how long it took.
 */
async function tileReaches(page, label, want, seconds = 90) {
  const started = Date.now();
  let seen = null;
  while ((Date.now() - started) / 1000 < seconds) {
    const state = await page.evaluate(READ_STEP2);
    seen = Number(
      state.kpis.find((k) => (k.label ?? "").toLowerCase().includes(label))?.value ?? "-1",
    );
    if (seen === want) {
      return { value: seen, took: Math.round((Date.now() - started) / 1000) };
    }
    await page.waitForTimeout(2000);
  }
  return { value: seen, took: Math.round((Date.now() - started) / 1000) };
}

async function signIn(page) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
}

(async () => {
  if (RUN === "") {
    console.log("⛔ give SMOKE_RUN a run id whose findings carry exception rows");
    process.exit(2);
  }

  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  // ⚠ ONE console error is EXPECTED IN THIS CONTAINER AND IS NOT A DEFECT:
  //   index.html asks fonts.googleapis.com for Archivo and this container has no
  //   route to it, so every page load logs ERR_CONNECTION_RESET.
  page.on("console", (m) => {
    const text = m.text();
    if (m.type() === "error" && !text.includes("Failed to load resource")) {
      console.log(`   [console.error] ${text.slice(0, 200)}`);
    }
  });

  console.log(`cr051-step23: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);
  await signIn(page);
  console.log("   signed in");

  const step2 = (tab, extra = "") =>
    `${BASE}/${TENANT}/billing/run?run=${RUN}&step=2&found=${tab}${extra}`;

  // ── 1 · TASK 13 — six sub-screens, and six different bodies ──────────────
  console.log("\n── step 2 · six sub-screens (task 13) ──");
  const bodies = {};
  for (const tab of ["consumers", "plans", "reads", "balances", "credits", "overcharges"]) {
    await open(page, step2(tab), SETTLED[tab]);
    const seen = await page.evaluate(READ_STEP2);
    bodies[tab] = seen;
    await page.screenshot({ path: join(OUT, `step2-${tab}.png`), fullPage: true });
  }
  const strip = bodies.consumers.tabs.find((one) => one.label === "What we found");
  console.log(`   tab strip: ${JSON.stringify(strip?.buttons)}`);
  check(strip !== undefined && strip.buttons.length === 6, "the six sub-screens are a tab strip of six");
  check(
    strip !== undefined && strip.buttons.some((b) => b.startsWith("Charges to add")),
    "the sixth tab reads *Charges to add*, not *Over charges* (DEF-2706)",
  );
  check(bodies.consumers.consumerRows > 0, `Consumers draws its own table (${bodies.consumers.consumerRows} rows)`);
  check(bodies.plans.planRows > 0, `Plans & Rates draws its own table (${bodies.plans.planRows} rows)`);
  check(bodies.reads.readRows > 0, `Meter reads draws its own table (${bodies.reads.readRows} rows)`);
  const kickers = new Set(
    ["consumers", "plans", "reads", "balances", "credits", "overcharges"].map((tab) =>
      (bodies[tab].sections[0] ?? "").toLowerCase(),
    ),
  );
  check(kickers.size >= 5, `the six bodies are DIFFERENT, not one table relabelled (${kickers.size} distinct openings)`);
  check(
    ["consumers", "plans", "reads", "balances", "credits", "overcharges"].every(
      (tab) => bodies[tab].sideways === 0,
    ),
    "no sub-screen scrolls the page sideways at 1440",
  );

  // ── 2 · TASK 14 — one table, every scenario, and the filter narrows it ───
  console.log("\n── step 2 · the meter-reads table (task 14) ──");
  await open(page, step2("reads"), '[data-brun-s2="read-row"]');
  const readsAll = await page.evaluate(READ_STEP2);
  // ⚠ **THE TWELVE SCENARIOS ARE A SELECT, NOT A CHIP STRIP — DEF-2899.** They
  //   were a `[role="tablist"]` of twelve buttons when this was written, and the
  //   PO ruled on 2026-08-31 that *the bill-run tabs are filters now* (commit
  //   35ae9e5b), which turned them into a `FilterSelect`. This check was not
  //   moved with them, so for a day it printed `chips: undefined` and reported
  //   TWO FAILURES over a screen that is correct by that same ruling — a check
  //   pointing at markup that no longer exists, which is DEF-524's shape one
  //   gate along and reads exactly like a broken screen.
  //   The requirement is unchanged and is what is asserted: twelve scenarios,
  //   each carrying its own count. Only where they are drawn moved.
  const scenarios = readsAll.readFilterOptions;
  console.log(`   scenarios: ${JSON.stringify(scenarios)}`);
  console.log(`   ${readsAll.readCount} · ${readsAll.readRows} row(s) drawn`);
  check(scenarios !== null && scenarios.length === 12, `every read scenario is offered (${scenarios?.length})`);
  check(
    scenarios !== null && scenarios.every((one) => /\(\d+\)$/.test(one)),
    "every scenario carries its own count",
  );
  check(readsAll.hasUnit, "every quantity carries its unit (CLAUDE.md rule 3)");
  check(
    readsAll.sections.some((s) => s.toLowerCase().includes("meter reads")),
    "the table is titled by its section kicker, not by a <caption>",
  );
  check(readsAll.captions === 0, "no table draws a <caption> (DEF-2439 avoided, not inherited)");

  // click a chip and watch the table narrow — a filter that filters
  const narrowUrl = step2("reads", "&read=missing");
  // ⚠ WAIT FOR A ROW, NOT FOR THE CHIP STRIP. The chips render immediately and
  //   the table does not, so waiting on `read-filters` read a page whose data
  //   had not arrived and reported "0 of 47" — the same too-early mistake the
  //   SETTLED map above was written to stop, made once more one line along.
  await open(page, narrowUrl, '[data-brun-s2="read-row"]');
  const readsMissing = await page.evaluate(READ_STEP2);
  console.log(`   ?read=missing → ${readsMissing.readRows} of ${readsAll.readRows}`);
  check(
    readsMissing.readRows > 0 && readsMissing.readRows < readsAll.readRows,
    `the Missing filter NARROWS the table (${readsMissing.readRows} of ${readsAll.readRows})`,
  );
  await page.screenshot({ path: join(OUT, "step2-reads-missing.png"), fullPage: true });

  // ── 3 · TASK 14 — the decision is taken on the row ───────────────────────
  await open(page, step2("reads"), '[data-brun-s3="decide"]');
  const rowDecide = await page.evaluate(READ_STEP3);
  console.log(`   row controls: ${JSON.stringify(rowDecide.selects.map((s) => s.options))}`);
  check(rowDecide.selects.length > 0, "the flagged reading carries a decision control ON ITS ROW");
  // ⚠ **ASKED OF THE UNDECIDED ROWS ONLY, AND THE CHECK POISONED ITS OWN
  //   PRECONDITION — DEF-2900.** Section 6 below RECORDS a decision to prove
  //   the KPIs move, and the decision is durable, so every later run of this
  //   script opens a run that already carries choices. Measured on 2026-09-01:
  //   `bill_run_decisions` held 4 rows for this run — `missing_read/estimate` ×2
  //   and `missing_read/hold` ×2 — all of them written by earlier runs of this
  //   file. A row showing its RECORDED choice is the screen working, so
  //   `every(s => s.value === "")` reported a BR-BIL-015 violation over correct
  //   behaviour, and it would do so on every machine that had ever run the
  //   check twice. The rule is about a DEFAULT, so the honest question is
  //   whether an undecided row shows a placeholder.
  const undecidedRows = rowDecide.selects.filter((s) => !s.disabled && s.value === "");
  const decidedRows = rowDecide.selects.length - undecidedRows.length;
  console.log(`   ${undecidedRows.length} undecided row(s), ${decidedRows} already answered`);
  //   The rule forbids a DEFAULT, so the two things that actually answer it are:
  //   every control offers the empty placeholder FIRST, and a row nobody has
  //   answered is showing it. `value` is `row.chosen ?? ""`, so a non-empty
  //   value is a recorded answer and never a default.
  check(
    rowDecide.selects.every((s) => s.values[0] === ""),
    "every decision control offers the empty placeholder FIRST (BR-BIL-015/061)",
  );
  check(
    undecidedRows.length > 0,
    `at least one row is undecided and shows that placeholder, or this proves nothing (${undecidedRows.length})`,
  );
  check(
    rowDecide.selects.every((s) => s.name && !/[0-9a-f]{8}-[0-9a-f]{4}/.test(s.name)),
    "the accessible name is words, never an id (B14 rule 31)",
  );

  // ── 4 · TASKS 15 + 18 — charges to add, and its stated absence ───────────
  console.log("\n── step 2 · charges to add (tasks 15, 18 · DEF-2706, DEF-2596) ──");
  const charges = bodies.overcharges;
  // DEF-2899 again — the three kinds are a select since 35ae9e5b, not chips.
  const chargeKinds = charges.chargeFilterOptions;
  console.log(`   kinds: ${JSON.stringify(chargeKinds)}`);
  check(
    chargeKinds !== null && chargeKinds.length === 3,
    "the three kinds r10 draws — All · Late payment fees · Service charges",
  );
  // ⚠ **AND THE ABSENCE IS READ FROM THE MARKUP, NOT FROM `innerText` —
  //   DEF-2899.** B14 rule 32 (ratified 2026-08-31, the day AFTER this check
  //   last passed) makes a stated absence a `<details>` CLOSED by default, so
  //   `RunGap` now hides its own sentence until a clerk clicks. `body.innerText`
  //   reports what is RENDERED, so it stopped seeing the sentence and this
  //   assertion failed over a screen obeying a rule that did not exist when the
  //   assertion was written. The absence is still NAMED, which is the
  //   requirement; the summary is what a clerk reads first, so that is what is
  //   asserted, and the sentence underneath is checked in the markup.
  check(
    charges.saysNoSourceTitle && charges.saysNoSource,
    "the absence is NAMED because nothing produces either case (DEF-2596), not drawn as an empty table",
  );
  check(!/\$/.test(JSON.stringify(charges.kpis)), "no money is invented on this tab");

  // ── 5 · TASK 16 — six KPIs, and four carry a WORD as well as a colour ────
  console.log("\n── step 2 · the bill-generation KPIs (task 16) ──");
  const kpis = bodies.consumers.kpis;
  console.log(`   ${kpis.map((k) => `${k.label}=${k.value}${k.word ? ` [${k.word}]` : ""}`).join(" · ")}`);
  check(kpis.length === 6, `six KPI tiles above step 2 (${kpis.length})`);
  check(
    kpis.every((k) => k.value !== null && k.value !== ""),
    "every tile carries a value the server sent",
  );
  const worded = kpis.filter((k) => k.word !== null);
  check(worded.length === 4, `four tiles carry a WORD as well as a colour (${worded.length})`);

  // ── 6 · TASK 16 — AND THE FIGURES MOVE (DEF-2705) ────────────────────────
  console.log("\n── step 2 · the KPIs MOVE when a decision is recorded (DEF-2705) ──");
  await open(page, step2("reads"), '[data-brun-s3="decide"]');
  const before = await page.evaluate(READ_STEP2);
  // ⚠ `.kpi .k` IS UPPERCASED BY CSS AND `innerText` REFLECTS text-transform, so
  //   an equality against "Waiting on you" finds nothing on a strip that draws
  //   WAITING ON YOU — and `Number(undefined ?? "-1")` is -1, which reads as a
  //   broken screen. cr051-run-screens.mjs records the same trap on its kickers.
  //
  // ⚠ **AND IT IS A `includes`, NOT AN `===`, SINCE DEF-2892.** Those labels now
  //   open with the unit they count — *Decisions waiting on you*, *Decisions you
  //   have taken* — because the row put 95 undecided CASE ROWS beside 48
  //   accounts under six unitless headings and the PO read the fourth tile as
  //   customers. An exact match against the old wording is the same -1 trap the
  //   paragraph above describes, one wording change later.
  const tile = (kpis, label) =>
    Number(kpis.find((k) => (k.label ?? "").toLowerCase().includes(label))?.value ?? "-1");
  const waitingBefore = tile(before.kpis, "waiting on you");
  const decidedBefore = tile(before.kpis, "you have taken");
  console.log(`   before: waiting=${waitingBefore} decided=${decidedBefore}`);

  // Record ONE decision through the row control and DO NOT RELOAD.
  // The row must still be UNDECIDED for the movement to be observable. A rerun
  //   of this check would otherwise measure a tile that was already at its
  //   final value and report a pass that proves nothing.
  //
  // ⚠ **PICK A CHOICE A BARE CLICK CAN COMPLETE.** `estimate` opens a MODAL
  //   (PO 2026-08-30, *"for estimate reads - keep it modal"*) and is proved
  //   separately below; selecting it here would measure a tile that has not
  //   moved because nothing was submitted yet — a false failure over correct
  //   behaviour, which is the shape this file keeps having to guard against.
  // ⚠ **AND THE ROW HAS TO BE UNDECIDED, WHICH THIS CODE DID NOT CHECK
  //   ALTHOUGH THE PARAGRAPH ABOVE SAYS SO — DEF-2900.** It took the first
  //   enabled control and the first plain option, so on any machine where this
  //   file had run before it re-chose a row that already carried that very
  //   answer: nothing moved, nothing could move, and it reported *waiting
  //   1→1, decided 1→1* as a failure of DEF-2705's fix. Measured on
  //   2026-09-01 this run held four decisions the script had written on earlier
  //   runs. A comment describing a precondition is not the precondition
  //   (hard-won law 1); `value === ""` is.
  const controls = await page.$$('[data-brun-s3="decide"]:not([disabled])');
  let target = null;
  let choice = null;
  for (const control of controls) {
    if ((await control.inputValue()) !== "") {
      continue; // already answered — re-answering it moves no tile
    }
    const options = await control.$$eval("option", (els) => els.map((e) => e.value));
    const plain = options.find((value) => value !== "" && value !== "estimate");
    if (plain !== undefined) {
      target = control;
      choice = plain;
      break;
    }
  }
  if (target === null) {
    check(
      false,
      `an UNDECIDED row exists to record against (${controls.length} enabled control(s), every one already ` +
        "answered — clear this run's bill_run_decisions, or point SMOKE_RUN at a run nobody has worked)",
    );
  } else {
    await target.selectOption(choice);
    const moved = await tileReaches(page, "you have taken", decidedBefore + 1);
    const after = await page.evaluate(READ_STEP2);
    const waitingAfter = tile(after.kpis, "waiting on you");
    const decidedAfter = tile(after.kpis, "you have taken");
    console.log(
      `   chose "${choice}" → waiting=${waitingAfter} decided=${decidedAfter} after ${moved.took}s, NO reload`,
    );
    await page.screenshot({ path: join(OUT, "step2-kpis-moved.png"), fullPage: true });
    check(
      waitingAfter === waitingBefore - 1 && decidedAfter === decidedBefore + 1,
      `the KPIs MOVED without a reload: waiting ${waitingBefore}→${waitingAfter}, decided ${decidedBefore}→${decidedAfter}`,
    );
  }

  // ── 6b · DEF-2597 — the estimate is a MODAL and it actually records ──────
  console.log("\n── step 2 · estimate opens a modal and records (PO 2026-08-30 · DEF-2597) ──");
  await open(page, step2("reads", "&read=missing"), '[data-brun-s3="decide"]');
  const beforeEstimate = await page.evaluate(READ_STEP2);
  const decidedBeforeEstimate = tile(beforeEstimate.kpis, "you have taken");
  const missing = await page.$('[data-brun-s3="decide"]:not([disabled])');
  if (missing === null) {
    check(false, "the missing reading carries a live decision control");
  } else {
    await missing.selectOption("estimate");
    await page.waitForTimeout(600);
    const modal = await page.evaluate(`(() => {
      const shell = document.querySelector('[role="dialog"], .modal-card, .modal');
      if (!shell) return null;
      return {
        title: (shell.querySelector("h2, h3, .modal-title") || {}).innerText || null,
        qty: shell.querySelector('#brun-estimate-qty') !== null,
        unitOptions: [...(shell.querySelector('#brun-estimate-unit') || { options: [] }).options].map((o) => o.value),
        confirmDisabled: (() => {
          const buttons = [...shell.querySelectorAll("button")];
          const commit = buttons[buttons.length - 1];
          return commit ? commit.disabled === true : null;
        })(),
      };
    })()`);
    console.log(`   modal: ${JSON.stringify(modal)}`);
    check(modal !== null, "choosing *Estimate the reading* opens a modal, not a silent 422");
    check(
      modal !== null && modal.qty && modal.unitOptions.length > 0,
      `the modal asks for a quantity AND a unit, offering the units the server used (${JSON.stringify(modal?.unitOptions)})`,
    );
    check(
      modal !== null && modal.confirmDisabled === true,
      "the commit is REFUSED until both are given (CLAUDE.md rule 3, before the round trip)",
    );
    await page.fill("#brun-estimate-qty", "9.5");
    const units = modal?.unitOptions.filter((one) => one !== "") ?? [];
    if (units.length > 0) await page.selectOption("#brun-estimate-unit", units[0]);
    await page.screenshot({ path: join(OUT, "step2-estimate-modal.png"), fullPage: true });
    // ⚠ CLICK BY ITS WORDS, NOT BY POSITION. `button:last-of-type` inside the
    //   shell can be the ✕ or the Cancel depending on where the shell's own
    //   chrome sits in the DOM, and a click on the wrong one CLOSES the dialog
    //   and reports "it did not record" over a screen that was never asked to.
    const commit = await page.$(`text=${"Record this estimate"}`);
    check(commit !== null, "the modal's commit is named in words, not an OK");
    if (commit !== null) await commit.click();
    // ⚠ **DO NOT ASSERT THE *Decided* TILE RISES HERE, AND THE REASON IS A
    //   RULE.** The previous step already recorded a choice on THIS SAME ROW,
    //   and `record_decision` is append-only: a change of mind SUPERSEDES
    //   rather than adding a second decision (*"evidence that can be edited is
    //   not evidence"*). So the count correctly stays where it is, and a check
    //   expecting +1 fails over the product behaving exactly as signed. The
    //   movement claim is proved one step above, on a row that was undecided.
    //   What this step must prove is that the ESTIMATE landed — so it reads
    //   the row's own recorded choice, and then the database.
    // ⚠ POLL, DO NOT SAMPLE — same reason as the tile. The row redraws from the
    //   REFETCHED case read, and that read re-runs the prepare pass (measured
    //   at 20.6s for 47 accounts here). A four-second sample reported the
    //   PREVIOUS choice over a decision the database had already taken —
    //   `stored: estimate 9.500000 kgal` on the very same run.
    const READ_ROW = `(() => {
      const cell = document.querySelector('[data-brun-s2="read-row"] [data-brun-s3="decide"]');
      const shell = document.querySelector('[role="dialog"], .modal-card');
      return { value: cell ? cell.value : null, modalStillOpen: shell !== null };
    })()`;
    let rowChoice = await page.evaluate(READ_ROW);
    const rowStarted = Date.now();
    while (rowChoice.value !== "estimate" && (Date.now() - rowStarted) / 1000 < 90) {
      await page.waitForTimeout(2000);
      rowChoice = await page.evaluate(READ_ROW);
    }
    console.log(`   row settled after ${Math.round((Date.now() - rowStarted) / 1000)}s`);
    console.log(`   row now reads "${rowChoice.value}"; modal open: ${rowChoice.modalStillOpen}`);
    await page.screenshot({ path: join(OUT, "step2-estimate-recorded.png"), fullPage: true });
    check(!rowChoice.modalStillOpen, "the modal CLOSES on a successful record, not on a click");
    check(
      rowChoice.value === "estimate",
      `the row now carries the recorded estimate ("${rowChoice.value}") — DEF-2597 closed`,
    );
    const tenantId = DB === "" ? "" : sql("select id from tenants limit 1");
    const stored = DB === "" ? "" : sql(
      "select choice || ' ' || coalesce(amount::text,'-') || ' ' || coalesce(unit,'-') " +
        `from bill_run_decisions where "case" = 'missing_read' order by created_at desc limit 1`,
      tenantId,
    );
    if (stored !== "") {
      console.log(`   stored: ${stored}`);
      check(
        /estimate/.test(stored) && /9\.5/.test(stored),
        `the quantity and its unit reached the DATABASE (${stored})`,
      );
    }
  }

  // ── 7 · TASK 17 — three families, and the case filter inside one ─────────
  console.log("\n── step 3 · three families (task 17) ──");
  await open(page, `${BASE}/${TENANT}/billing/run?run=${RUN}&step=3`, '[data-brun-s3="family-row"]');
  await page.screenshot({ path: join(OUT, "step3-families.png"), fullPage: true });
  const step3 = await page.evaluate(READ_STEP3);
  // DEF-2899 — read the two pickers, not the tab strips they used to be. The
  //   requirement is unchanged and is what is asserted: three families, and the
  //   cases inside the open one offered as a filter rather than a rail. Only
  //   the control the PO asked for changed underneath.
  const families = step3.familyPicker;
  const kinds = step3.casePicker;
  console.log(`   families: ${JSON.stringify(families?.options)}`);
  console.log(`   kinds:    ${JSON.stringify(kinds?.options)}`);
  check(families !== null && families.options.length === 3, `THREE families, not fifteen tabs (${families?.options.length})`);
  check(kinds !== null && kinds.options.length > 1, "the cases inside the open family are a filter, not a rail");
  check(step3.rows > 0, `the family table draws rows (${step3.rows})`);
  check(step3.bulk !== null, "the bulk bar survives — per-row deciding is added BESIDE it (BR-BIL-060)");
  check(step3.sideways === 0, "step 3 does not scroll sideways at 1440");

  const owesUrl = `${BASE}/${TENANT}/billing/run?run=${RUN}&step=3&family=owes`;
  await open(page, owesUrl, '[data-brun-s2="families"] select');
  const owes = await page.evaluate(READ_STEP3);
  const owesFamilies = owes.familyPicker;
  // ⚠ **AND IT IS THE FAMILY ID, NOT ITS WORDS — DEF-2899.** This read
  //   `startsWith("What the customer owes")`, which was right when it was
  //   written and wrong the moment the bill run stopped saying *customers* and
  //   started saying *accounts* (06682551, v2.109.1): the option reads *What
  //   the account owes (0)* and the assertion failed over a screen honouring
  //   the URL perfectly. The count moving was already anticipated here; the
  //   NOUN moving was not, and copy is the thing this repo rewords most. The
  //   option's value is the family id the URL itself names, so it is the only
  //   part of this control a reword cannot touch.
  check(
    owesFamilies !== null && owesFamilies.activeValue === "owes",
    `the URL names the open family and the screen honours it (${owesFamilies?.active})`,
  );

  // ── 8 · TASK 19 — the outlook band on step 4 ─────────────────────────────
  console.log("\n── step 4 · the outlook band (task 19) ──");
  await open(page, `${BASE}/${TENANT}/billing/run?run=${RUN}&step=4`, '[data-brun-s4="outlook"]');
  await page.screenshot({ path: join(OUT, "step4-outlook.png"), fullPage: true });
  const step4 = await page.evaluate(READ_STEP4);
  console.log(`   ${step4.produced} | ${step4.held}`);
  console.log(`   ${step4.split}`);
  check(step4.band !== null, "the outlook band is drawn on step 4");
  check(
    step4.produced !== null && /\d+ bills/.test(step4.produced.replace(/\s+/g, " ")),
    `what will be produced is a real figure (${(step4.produced ?? "").replace(/\s+/g, " ")})`,
  );
  check(
    step4.split !== null && /\d/.test(step4.split),
    `what is held back is split into what broke and what a person held (${step4.split})`,
  );
  check(step4.words.length === 2, `both halves carry a word as well as a colour (${JSON.stringify(step4.words)})`);
  check(
    step4.band !== null && step4.breaksY !== null && step4.band.y < step4.breaksY.y,
    "the outlook comes ABOVE the break list and the totals",
  );
  check(step4.sideways === 0, "step 4 does not scroll sideways at 1440");

  // ── 9 · GEOMETRY — DEF-2438, and nothing internal on the clerk's screen ──
  console.log("\n── geometry and the clerk's own words ──");
  await open(page, step2("plans"), '[data-brun-s2="plan-row"]');
  const plans = await page.evaluate(READ_STEP2);
  console.log(`   figure alignments: ${JSON.stringify(plans.figureAligns)}`);
  check(
    plans.figureAligns.length > 0 && plans.figureAligns.every((v) => v === "right"),
    `every figure column is MEASURABLY right-aligned (DEF-2438 worked around, ${plans.figureAligns.length} cells)`,
  );

  const seenIds = [];
  const seenRules = [];
  for (const tab of ["consumers", "plans", "reads", "overcharges"]) {
    seenIds.push(...bodies[tab].uuidOnScreen, ...bodies[tab].namesADefect);
    seenRules.push(...bodies[tab].namesARule);
  }
  check(seenIds.length === 0, `no database id and no internal name reaches the clerk (B14 rule 31) ${JSON.stringify(seenIds.slice(0, 2))}`);
  // REPORTED, not failed — DEF-2432 composes these in three BACKEND services a
  // frontend lane may not edit, and step 2's rows inherit whatever they say.
  if (seenRules.length > 0) {
    console.log(`   ⚠ REPORTED (DEF-2432, backend-composed): a rule id is on screen — ${JSON.stringify([...new Set(seenRules)])}`);
  }

  await browser.close();
  console.log(`\n${failures.length === 0 ? "PASS" : `FAIL — ${failures.length}`}; screenshots in ${OUT}`);
  for (const one of failures) console.log(`   ⛔ ${one}`);
  process.exit(failures.length === 0 ? 0 : 1);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
