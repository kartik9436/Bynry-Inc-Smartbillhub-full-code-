// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-6912 — the plan wizard's step-4 monthly base read the
//          INFERRED `is_base` code while the bound schedule NAMED another, so
//          a priced schedule showed "No amount set · from BASE-W".
// Rules:   BR-RAT-1025 / CR-120-BRC06 (the schedule may name its base) ·
//          BR-RAT-087 (the client never formats money) · DEF-277 (absent is
//          not zero) · CLAUDE.md hard-won law 6 (diff the running app — no
//          gate reads rendered output) · B14 rule 44 (a staff screen is built
//          at 1440 and must work at 1280).
// ───────────────────────────────────────────────────────
//
// THE PRODUCT OWNER'S OWN TEST, REPLAYED IN A BROWSER, IN ONE RUN:
//   1. the schedule NAMES `BASE-W-FIRE`  → step 4 must read that code, $12.00
//   2. the schedule names NOTHING        → step 4 falls back to `BASE-W`
//   3. the named code is RETIRED         → step 4 states the absence
//
// The three states are seeded BETWEEN the shots by
// `def_rat_6912_seed_bound_base.py`, so this is one browser session over three
// database states rather than three fixtures. Nothing is injected, hidden or
// substituted; where a state cannot be reached the script SAYS SO in
// 00-README.txt rather than skipping it silently (law 7's fifth shape).
//
//   node 10-scripts/def_rat_6912_plan_base_walkthrough.mjs
//
// Env: SMOKE_BASE · SMOKE_TENANT · SMOKE_EMAIL · SMOKE_PASSWORD · PLAN_ID ·
//      SHOT_OUT · SEED_CMD (how to re-seed between states)

import { execSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8702";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const PLAN_ID = process.env.PLAN_ID ?? "";
const OUT = process.env.SHOT_OUT ?? "/tmp/def-rat-6912-shots";
const EXE = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SEED = process.env.SEED_CMD ?? "";

const notes = [];
function note(line) {
  console.log(line);
  notes.push(line);
}

function seed(args) {
  if (SEED === "") {
    note(`  NOT RE-SEEDED — SEED_CMD is unset, so this state was not reached.`);
    return false;
  }
  const cmd = `${SEED} ${args}`.trim();
  const out = execSync(cmd, { encoding: "utf8" });
  const named = (out.match(/^names\s+(.*)$/m) ?? [])[1] ?? "?";
  note(`  seeded (${args || "bound"}) — tariff_versions.base_charge_code = ${named}`);
  return true;
}

async function shot(page, name, width) {
  await page.setViewportSize({ width, height: 1100 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/${name}-${width}.png`, fullPage: true });
  note(`  shot ${name}-${width}.png`);
}

/** WHAT THE MONTHLY-BASE PANEL ACTUALLY SAYS — read out of the rendered
 *  `<dd>`, never out of the component's own arithmetic. */
async function baseLine(page) {
  const dd = page.locator('section:has-text("Monthly base") dl dd').first();
  await dd.waitFor({ timeout: 15000 }).catch(() => null);
  return (await dd.textContent().catch(() => null))?.trim() ?? "NOT FOUND";
}

async function openStep4(page) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${PLAN_ID}/edit`, {
    waitUntil: "networkidle",
  });
  // ⚠ **PRESS CONTINUE UNTIL THE PANEL IS THERE, NEVER A FIXED NUMBER OF
  // TIMES.** The first draft clicked three times and read the `<dd>` — and on
  // a slow load it read a step-3 screen and reported `NOT FOUND`, which looks
  // exactly like a broken panel. A wait with no clock in it never ends and a
  // click count with no check after it never fails; this loop has both.
  // The draft is loaded before the first press — on the first state of the
  // run the wizard was still fetching, the click landed on an unhydrated
  // button and every later press then had nothing to advance. That reported
  // `NOT FOUND` over a healthy screen, which is law 7's *looking at the wrong
  // thing* dressed as a defect.
  await page.waitForSelector('button:has-text("Continue")', { timeout: 20000 });
  await page.waitForTimeout(1500);
  for (let i = 0; i < 12; i += 1) {
    if ((await page.locator('section:has-text("Monthly base") dl dd').count()) > 0) break;
    const before = (await page.locator("text=/STEP \\d OF 8/i").first().textContent()) ?? "";
    const next = page.locator('button:has-text("Continue")').last();
    if ((await next.count()) === 0) break;
    await next.click().catch(() => null);
    // Wait for the step to CHANGE rather than for a fixed pause: a press that
    // did nothing and a press that is still working look identical to a clock.
    await page
      .waitForFunction(
        (was) => !(document.body.innerText || "").includes(was),
        before,
        { timeout: 8000 },
      )
      .catch(() => null);
  }
  await page.waitForTimeout(500);
  const step = (await page.locator("text=/STEP \\d OF 8/i").first().textContent().catch(() => null)) ?? "?";
  note(`  stopped on ${step.trim()}`);
}

async function main() {
  if (PLAN_ID === "") {
    console.error("PLAN_ID is required — the plan the walk opens.");
    return 2;
  }
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE });
  const page = await (await browser.newContext()).newPage();

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);
  note(`signed in as ${EMAIL}; landed on ${page.url()}`);

  const version = await page
    .locator("text=/v?2\\.\\d+\\.\\d+/")
    .first()
    .textContent()
    .catch(() => null);
  note(`version on screen: ${version ?? "NOT FOUND — reported rather than assumed"}`);

  // ── 1 · the schedule NAMES a code ────────────────────────────────────────
  note("STATE 1 — the water schedule NAMES BASE-W-FIRE ($12.00)");
  seed("");
  await openStep4(page);
  note(`  monthly base reads: "${await baseLine(page)}"`);
  await shot(page, "01-named", 1440);
  await shot(page, "01-named", 1280);

  // ── 2 · the schedule names NOTHING ───────────────────────────────────────
  note("STATE 2 — the same schedule names NOTHING; the inferred code answers");
  if (seed("--unbind")) {
    await openStep4(page);
    note(`  monthly base reads: "${await baseLine(page)}"`);
    await shot(page, "02-inferred", 1440);
  }

  // ── 3 · the named code is RETIRED ────────────────────────────────────────
  note("STATE 3 — the named code is RETIRED, so the builder's active-only");
  note("          catalogue cannot resolve it. The screen must say so and must");
  note("          NOT quietly draw BASE-W, which is not what the bill would use.");
  if (seed("--retire-bound")) {
    await openStep4(page);
    note(`  monthly base reads: "${await baseLine(page)}"`);
    await shot(page, "03-named-gone", 1440);
  }

  // Leave the database in state 1 — the state the defect is about.
  note("restoring state 1");
  seed("");

  await browser.close();
  writeFileSync(`${OUT}/00-README.txt`, `${notes.join("\n")}\n`);
  note(`\nwrote ${OUT}/00-README.txt`);
  return 0;
}

main().then((code) => process.exit(code ?? 0));
