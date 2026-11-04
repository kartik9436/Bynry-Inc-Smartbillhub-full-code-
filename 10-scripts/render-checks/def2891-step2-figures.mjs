#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-2891 (two numbers labelled Accounts on one screen disagree) ·
//          DEF-2892 (three units in one KPI row with no unit stated) ·
//          DEF-2893 (Cannot be billed shows a count and never says who or why)
// Change:  CR-051 tasks 3 and 16 (12-governance/11-change-requests.md § CR-051)
// Screens: S31 (the run band, on every step) · S31.2 (the bill-generation KPIs)
// Rules:   the PO's KPI consistency rule — *"a KPI must agree with its owning
//          module for the same as-of moment"* (12-governance/02-decision-log.md
//          2026-08-19) · B14 rule 31 (no database id on screen) · B14 rule 32
//          (a stated absence is CLOSED by default; no rule id or internal code
//          in clerk-facing copy) · hard-won law 6 (diff the RUNNING app)
// ───────────────────────────────────────────────────────
/**
 * Open step 2 in a REAL browser and read the figures back.
 *
 * ⚠ **WHY A BROWSER AND NOT THE FIVE PASSING CASES BESIDE IT.** PO ruling
 * 2026-08-30: *"All UI screen should be confirm using real broswer testing and
 * not just based on test cases"*. All three defects here were reported off a
 * DEPLOYMENT, by a person looking at a screen, and two of them are properties
 * of the whole page rather than of any component: *Accounts 0* and *Accounts
 * 48* were each drawn correctly by code with its own green suite, and only the
 * two of them being on one screen at one moment made either wrong. A jsdom case
 * can be written to compare them — `CR051Step23.test.tsx` now does — but it can
 * only compare what it was told to render. The browser is what says the clerk
 * sees no second *Accounts* anywhere on the page.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is reading the
 * wrong bytes. Every render check in this folder records that lesson; it is the
 * cheapest mistake here to make twice.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=true \
 *   DATABASE_URL="postgres://…/smartbillhub_cr051w34" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8073 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4273 API_PROXY_TARGET=http://127.0.0.1:8073 node server.mjs &)
 *
 *   SMOKE_BASE=http://127.0.0.1:4273 \
 *   SMOKE_RUN=<a run that has been prepared> \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/def2891-step2-figures.mjs
 *
 * ⚠ **A DATABASE NOBODY ELSE IS SEEDING.** The shared `smartbillhub` is
 * re-seeded without warning, and from in here that looks exactly like four
 * broken screens. This lane used `smartbillhub_cr051w34`, the CR-051 W3/W4
 * lane's own, left in place for this reason.
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  ONE NUMBER PER FACT — no label is drawn both on the run band and in the
 *      KPI strip, and the band draws no account count at all (DEF-2891).
 *   2  EVERY TILE SAYS WHAT IT COUNTS — each of the six labels opens with its
 *      unit, and the three units are grouped rather than interleaved
 *      (DEF-2892).
 *   3  THE BLOCKED FIGURE OPENS — a disclosure, closed on arrival, listing
 *      every blocked account with its reason in words and where to fix it; no
 *      reason code and no uuid is visible; and it draws nothing when the run
 *      blocks nobody (DEF-2893, B14 rules 31 and 32).
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4273";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const RUN = process.env.SMOKE_RUN ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/def2891-step2";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/**
 * The band's labels, the strip's tiles, and the blocked disclosure.
 *
 * ⚠ **`.kpi .k` IS UPPERCASED BY CSS AND `innerText` REFLECTS text-transform**,
 * which is a trap `cr051-step23.mjs` recorded the hard way — an equality
 * against a catalogue string finds nothing on a strip drawing ACCOUNTS IN THIS
 * RUN. Everything below is compared lower-cased.
 */
const READ = `(() => {
  const band = document.querySelector('[data-brun-run="band"]');
  const bandLabels = band
    ? [...band.querySelectorAll("span")]
        .filter((el) => (el.className || "").includes("uppercase"))
        .map((el) => el.innerText.trim().toLowerCase())
    : null;
  const bandFigures = band
    ? [...band.querySelectorAll(".tabular-nums")].map((el) => el.innerText.trim())
    : null;
  const tiles = [...document.querySelectorAll(".kpi")].map((tile) => ({
    label: (tile.querySelector(".k")?.innerText ?? "").trim().toLowerCase(),
    value: (tile.querySelector(".v")?.innerText ?? "").trim(),
    word: (tile.querySelector(".d .pill")?.innerText ?? "").trim() || null,
  }));
  const disclosure = document.querySelector('[data-brun-s2="blocked-why"]');
  const rows = [...document.querySelectorAll('[data-brun-s2="blocked-row"]')].map((row) => ({
    reason: row.getAttribute("data-reason"),
    cells: [...row.querySelectorAll("td")].map((td) => td.innerText.trim()),
  }));
  const body = document.body.innerText || "";
  return {
    bandLabels,
    bandFigures,
    tiles,
    hasDisclosure: disclosure !== null,
    disclosureOpen: disclosure === null ? null : disclosure.hasAttribute("open"),
    summary: disclosure === null ? null : (disclosure.querySelector("summary")?.innerText ?? "").trim(),
    rows,
    // B14 rule 31 / rule 32 clause 4 — read the VISIBLE text only. The ruling
    // allows an id or a code to ride on an attribute as evidence, so scanning
    // the markup would be a check that cannot distinguish pass from fail.
    uuidOnScreen: (body.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi) || []).slice(0, 3),
    snakeOnScreen: (body.match(/\\b[a-z]+(?:_[a-z]+){2,}\\b/g) || []).slice(0, 5),
    // DEF-2895 — REPORTED, not failed. See the section that reads these.
    ruleIdsOnScreen: (body.match(/\\b(?:BR-[A-Z]{3}|OQ|US-[A-Z]{3}|DEF)-[0-9]{3,5}(?![0-9])/g) || []).slice(0, 5),
    isoStampsOnScreen: (body.match(/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}/g) || []).slice(0, 5),
    sideways: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
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
 * ⚠ **WAIT FOR THE DATA, NOT FOR THE NETWORK TO GO QUIET.**
 * `GET /billing/runs/{id}/findings` re-runs the whole prepare pass on every
 * call — the PO ruled on 2026-08-30 that it is recomputed and never cached —
 * and it measured 20.6 seconds for 47 accounts on this database. `networkidle`
 * has a 30s budget and would fail on the endpoint's honesty rather than on
 * anything drawn. And `.kpi` is the WRONG thing to wait for: it renders
 * immediately with a dash in every tile, so a check that waited for it would
 * read six empty tiles and report the screen broken.
 */
async function openStep2(page, url) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 90000 });
  try {
    await page.waitForSelector('[data-brun-s2="consumer-row"]', { timeout: 180000 });
  } catch {
    console.log("   [warn] the consumers table never arrived — the findings pass may still be running");
  }
  await page.waitForTimeout(700);
}

(async () => {
  if (RUN === "") {
    console.log("⛔ give SMOKE_RUN a run id that has been prepared");
    process.exit(2);
  }

  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  // ⚠ ONE console error is EXPECTED IN THIS CONTAINER AND IS NOT A DEFECT:
  //   index.html asks fonts.googleapis.com for Archivo and this container has
  //   no route to it, so every page load logs ERR_CONNECTION_RESET.
  page.on("console", (m) => {
    const text = m.text();
    if (m.type() === "error" && !text.includes("Failed to load resource")) {
      console.log(`   [console.error] ${text.slice(0, 200)}`);
    }
  });

  console.log(`def2891-step2-figures: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);
  await signIn(page);
  console.log("   signed in");

  await openStep2(page, `${BASE}/${TENANT}/billing/run?run=${RUN}&step=2&found=consumers`);
  const seen = await page.evaluate(READ);
  await page.screenshot({ path: join(OUT, "step2-figures.png"), fullPage: true });

  // ── 1 · DEF-2891 — ONE NUMBER PER FACT ──────────────────────────────────
  console.log("\n── the band and the strip cannot both claim Accounts (DEF-2891) ──");
  console.log(`   band labels : ${JSON.stringify(seen.bandLabels)}`);
  console.log(`   band figures: ${JSON.stringify(seen.bandFigures)}`);
  check(Array.isArray(seen.bandLabels) && seen.bandLabels.length > 0, "the run band is drawn");
  check(
    Array.isArray(seen.bandLabels) && !seen.bandLabels.some((one) => one.startsWith("accounts")),
    `the band draws NO account count (${JSON.stringify(seen.bandLabels)})`,
  );
  const tileLabels = seen.tiles.map((tile) => tile.label);
  const collisions = tileLabels.filter((label) => (seen.bandLabels ?? []).includes(label));
  check(collisions.length === 0, `no label is drawn on BOTH the band and the strip (${JSON.stringify(collisions)})`);
  // …and the assertion above cannot pass by both being empty.
  check(seen.tiles.length === 6, `six KPI tiles above step 2 (${seen.tiles.length})`);

  // ── 2 · DEF-2892 — EVERY TILE SAYS WHAT IT COUNTS ───────────────────────
  console.log("\n── every figure names its unit (DEF-2892) ──");
  console.log(`   ${seen.tiles.map((k) => `${k.label}=${k.value}${k.word ? ` [${k.word}]` : ""}`).join(" · ")}`);
  const UNITS = ["accounts", "decisions", "days"];
  const unitOf = (label) => UNITS.find((unit) => label.includes(unit)) ?? null;
  const units = tileLabels.map(unitOf);
  check(
    units.every((unit) => unit !== null),
    `every tile label names its unit (${JSON.stringify(tileLabels.filter((l) => unitOf(l) === null))} name none)`,
  );
  // Grouped, not interleaved: the row splits into three families by eye.
  //
  // ⚠ **ONLY ASKED WHEN EVERY UNIT IS KNOWN, AND THAT GUARD IS THE POINT.** Run
  // against the shipped screen this read `["accounts", null, null, null, null,
  // "days"]` and PASSED — every null shares one `indexOf`, so the sequence is
  // monotonic and the assertion reported success over the exact row it exists
  // to reject. That is DEF-182's shape: a check whose output cannot distinguish
  // pass from fail. It now says NOT EXERCISED instead, and the assertion above
  // is the one that fails.
  if (units.every((unit) => unit !== null)) {
    const firstSeen = units.map((unit) => units.indexOf(unit));
    const grouped = firstSeen.every((position, index) => index === 0 || position >= firstSeen[index - 1]);
    check(grouped, `the units are grouped, not interleaved (${JSON.stringify(units)})`);
  } else {
    console.log("   — grouping NOT EXERCISED: a tile names no unit, so there is nothing to group");
  }
  check(
    seen.tiles.every((tile) => tile.value !== ""),
    "every tile carries a figure — a dash is a figure, an empty tile is not",
  );
  const worded = seen.tiles.filter((tile) => tile.word !== null);
  check(worded.length === 4, `four tiles carry a WORD as well as a colour (${worded.length})`);

  // ── 3 · DEF-2893 — THE BLOCKED FIGURE OPENS ─────────────────────────────
  console.log("\n── cannot be billed says who and why (DEF-2893) ──");
  const blockedTile = seen.tiles.find((tile) => tile.label.includes("cannot be billed"));
  const blockedCount = Number(blockedTile?.value ?? "-1");
  console.log(`   cannot be billed = ${blockedTile?.value ?? "(no tile)"}`);
  // ⚠ **THE ROWS MUST BE READ WITH THE DISCLOSURE OPEN, AND THE FIRST DRAFT OF
  //   THIS CHECK WAS NOT — WHICH IS ITSELF THE FINDING.** A closed `<details>`
  //   hides its content, and `innerText` reports what is RENDERED, so all three
  //   cells came back as empty strings over a table that is completely correct.
  //   `textContent` would have "passed" and told us nothing, because it reads
  //   hidden nodes too. So the check CLICKS, which is also the only way to
  //   learn that the disclosure opens at all — the half no static render has.
  let opened = seen;
  if (blockedCount > 0 && !seen.hasDisclosure) {
    // ⚠ **REPORT, NEVER THROW.** The first draft clicked unconditionally, so
    // against the shipped screen it raised a Playwright timeout and the four
    // checks after it never ran at all — a check that dies takes the rest of
    // the run with it and reports nothing about the things it was still going
    // to ask. The two remaining sections are exactly the ones that answer
    // B14 rules 31 and 32.
    check(false, "the figure can be opened to the accounts it counts");
  } else if (blockedCount > 0) {
    check(true, "the figure can be opened to the accounts it counts");
    check(seen.disclosureOpen === false, "it arrives CLOSED (B14 rule 32 — a stated absence is closed by default)");
    await page.click('[data-brun-s2="blocked-why"] summary');
    await page.waitForTimeout(300);
    opened = await page.evaluate(READ);
    await page.screenshot({ path: join(OUT, "step2-blocked-open.png"), fullPage: true });
    check(opened.disclosureOpen === true, "clicking the summary opens it");
    check(opened.rows.length === blockedCount, `it lists every blocked account (${opened.rows.length} rows against ${blockedCount})`);
    console.log(`   summary: ${opened.summary}`);
    console.log(`   rows   : ${JSON.stringify(opened.rows.slice(0, 3))}`);
    check(
      opened.rows.every((row) => row.cells.length === 3 && row.cells.every((cell) => cell !== "")),
      "every row says the account, what we found, and where to fix it",
    );
    check(
      opened.rows.every((row) => row.reason !== null && !row.cells.join(" ").includes(row.reason)),
      "the reason CODE rides on the row as evidence and is never the words (B14 rule 32)",
    );
  } else if (blockedCount === 0) {
    check(!seen.hasDisclosure, "nothing is blocked, so no empty disclosure is offered");
  } else {
    check(false, "the *cannot be billed* tile was not found at all");
  }

  // ── 4 · WHAT NEITHER OF THE ABOVE MAY COST ──────────────────────────────
  //   Read from the OPENED page: a rule about what a clerk can see is not
  //   answered by a panel that was shut when we looked.
  console.log("\n── no id, no internal code, no sideways scroll ──");
  check(opened.uuidOnScreen.length === 0, `no uuid is visible (${JSON.stringify(opened.uuidOnScreen)}) — B14 rule 31`);
  check(opened.snakeOnScreen.length === 0, `no internal code is visible (${JSON.stringify(opened.snakeOnScreen)}) — B14 rule 32`);
  check(opened.sideways === false, "nothing scrolls sideways at 1440");

  // ⚠ **REPORTED AND NOT FAILED, AND THE DISTINCTION IS DELIBERATE — DEF-2895.**
  //   The blocked row's sentence is composed in `apps/billing/runs.py`, a
  //   BACKEND service, so nothing a frontend lane can do makes this section
  //   pass. `cr051-step23.mjs` took exactly this posture for DEF-2432 and for
  //   the same reason. Failing here would give the next lane a red check it
  //   cannot clear and would teach it to stop reading the output.
  console.log("\n── REPORTED, not failed — clerk copy composed in the backend (DEF-2895) ──");
  if (opened.ruleIdsOnScreen.length > 0) {
    console.log(`   ⚠ a rule or question id is on screen: ${JSON.stringify(opened.ruleIdsOnScreen)} (B14 rule 32 clause 4)`);
  }
  if (opened.isoStampsOnScreen.length > 0) {
    console.log(`   ⚠ a raw ISO timestamp is on screen: ${JSON.stringify(opened.isoStampsOnScreen)} (BR-SHL-034 — every displayed date goes through DateCell)`);
  }
  if (opened.ruleIdsOnScreen.length === 0 && opened.isoStampsOnScreen.length === 0) {
    console.log("   none — DEF-2895 may be closeable");
  }

  await browser.close();
  console.log(`\n${failures.length === 0 ? "PASS" : `FAIL (${failures.length})`} — screenshots in ${OUT}`);
  for (const line of failures) console.log(`   ⛔ ${line}`);
  process.exit(failures.length === 0 ? 0 : 1);
})();
