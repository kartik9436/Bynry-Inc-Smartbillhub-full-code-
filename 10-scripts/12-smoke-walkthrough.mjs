#!/usr/bin/env node
// ── 12-smoke-walkthrough.mjs ─────────────────────────────────────────────────
//
// THE BROWSER WALKTHROUGH, AS A SCRIPT IN THE REPO — because on 2026-08-21 one
// afternoon of clicking through a real deployment found five defects a full
// green suite could not: DEF-528 (seed dies), DEF-529 (500 only outside a
// transaction), DEF-530 (validate's results unseeable), DEF-531 (wrong payload
// key), DEF-532 (a back link that broke the whole app). Every one was invisible
// to unit tests, gates and tsc, and visible to a browser in minutes.
//
// WHEN TO RUN IT (the rule, not a suggestion):
//   * before any push that touches a screen;
//   * after fixing any defect whose escape_reason names DEF-523 (no DOM test
//     environment) — the walkthrough is the check that class of escape needs;
//   * any time seed_demo, the import runner, sign-in or routing change.
// `10-scripts/11-smoke-stack.sh` boots a full stack and runs this for you.
//
// WHAT IT WALKS (signed in as the seeded owner):
//   dashboard → premises list → premises/import stages 1→4 with a 3-row CSV
//   → THE HEADER BACK LINK (DEF-532's case: the URL must KEEP the tenant)
//   → units list → plans list → settings
//   → accounts list → accounts/import stages 1→5 with a 3-row CSV that carries
//     ALL FOUR BR-CUS-048 opening-balance buckets, and its RECEIPT.
//
// WHY THE ACCOUNTS LEG GOES ALL THE WAY TO STAGE 5 AND THE PREMISES ONE STOPS
// AT 4 (CR-030 W1 task 1.25): the accounts target is the only one whose commit
// hands money to another module — `customers.create_from_import` writes the
// four aged buckets and `ledger.opening_balances` posts ONE balanced batch for
// the run (US-CUS-021/022, GT-16 ❄️). None of that is reachable from stage 4,
// and BR-CUS-049 puts a REFUSAL in front of it: an accounts file with any
// `ob_*` column loaded WITHOUT a cutover date is refused before the first
// write, deliberately, because "today" would date a utility's migrated books
// on the day somebody happened to run the import. So the leg must supply a
// cutover date, and stage 5's receipt is the only place the browser can see
// that the money half actually happened.
//
// WHAT FAILS IT, on every page it visits:
//   * a missing/empty main heading (<h1>) — a screen that renders nothing;
//   * any raw catalogue key like `errors.not-found` visible in body text
//     (DEF-532's second finding: the failure state printed its i18n key);
//   * any 5xx response observed anywhere in the run (DEF-529's class);
//   * and each step's own assertion (wrong stage, wrong URL, missing rows).
//
// CONFIG (env):
//   SMOKE_BASE      default http://127.0.0.1:8080  (server.mjs's port — the
//                   production join: SPA + /api proxy on ONE origin)
//   SMOKE_TENANT    default brazosbend             (seed_demo's tenant)
//   SMOKE_EMAIL     default dana@brazosbendutilities.com
//   SMOKE_PASSWORD  default S3cure!passw0rd        (the PUBLISHED demo fixture
//                   credential — override to whatever SEED_DEMO_OWNER_PASSWORD
//                   the seed ran with; never a real credential)
//   SMOKE_OUT       screenshot dir, default $TMPDIR/smartbillhub-smoke-<stamp>
//   SMOKE_HEADED    "1" opens a visible browser (default headless)
//
// DEPENDENCIES: none of its own. It borrows `playwright-core` from
// 07-frontend/node_modules (already pinned there for the e2e suite) and finds
// a chromium in PLAYWRIGHT_BROWSERS_PATH (or /opt/pw-browsers) even when the
// exact revision playwright wants is not the one installed.
// ─────────────────────────────────────────────────────────────────────────────

import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";

const requireFrontend = createRequire(
  new URL("../07-frontend/package.json", import.meta.url),
);
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.SMOKE_BASE ?? "http://127.0.0.1:8080").replace(/\/$/, "");
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT =
  process.env.SMOKE_OUT ??
  join(tmpdir(), `smartbillhub-smoke-${new Date().toISOString().replace(/[:.]/g, "-")}`);
const HEADED = process.env.SMOKE_HEADED === "1";

/** The 3-row premises CSV. Headers chosen to hit `_auto_map`'s aliases
 *  ("address" → address_line, "city" → city, "type" → premises_type). */
const CSV_TEXT =
  "Address,City,Type\n" +
  "101 Smoke Test Ln,Katy,Residential\n" +
  "202 Smoke Test Ln,Katy,Residential\n" +
  "303 Smoke Test Ave,Katy,Commercial\n";

/** The 3-row ACCOUNTS CSV (CR-030 W1 — the sixth runner target).
 *
 *  Headers are `import_runs.ACCOUNTS_COLUMNS`' own target names. `_auto_map`
 *  matches ONLY through `ACCOUNTS_ALIASES`, and every one of these names is
 *  listed as its own alias there, so stage 2 maps the file to itself.
 *
 *  ⚠ THE UNIT REFERENCES ARE seed_demo's OWN. BR-CUS-047: an account import
 *  RESOLVES a unit against the tenant's units and never creates one, so an
 *  invented `unit_ref` is an error row rather than a new unit. seed_demo
 *  creates NO accounts, so these three units are free — and BR-CUS-017 (one
 *  live account per unit, ever) means a SECOND walkthrough over the SAME
 *  database rejects all three. That is why 11-smoke-stack.sh seeds, and why
 *  SMOKE_SKIP_SEED=1 makes this leg's counts a re-run, not a repeat.
 *
 *  ⚠ ALL FOUR BR-CUS-048 BUCKETS CARRY MONEY on every row — which is exactly
 *  what makes BR-CUS-049's cutover date REQUIRED for this file. Values are
 *  written to 4 decimals (CLAUDE.md hard rule 2) and DISPLAY to 2.
 *
 *  ⚠ THE FILE MUST CARRY EVERY COLUMN THE SERVER MAKES REQUIRED, AND IT
 *  STOPPED DOING SO WITHOUT ANYTHING GOING RED. `account_no` became
 *  `required=True` on the accounts target (PO ruling 2026-08-27, CR-046 C4 —
 *  "if row dont have account number reject it"; `import_runs.py`'s
 *  `_account_column("account_no", …)`), and BR-MET-1032 / CR-058 W7 then made
 *  a row with a name and no identifier load NOTHING
 *  (`account_customer_identity_required`). This CSV was updated for neither, so the
 *  server refused stage 2 (`422 metering.import.required_column_unmapped`,
 *  targets ["account_no"]) and the runner stayed on stage 2 for ever — which
 *  this walk reported as "stage 3 never arrives". Nothing about it was a
 *  background job: a 3-row file is far below every async bar.
 *  So each row carries its OWN account number (the utility's, never ours),
 *  a `customer_kind`, and the one identifier that kind accepts — a phone for
 *  a person, a Tax ID for a company (ACCOUNT_IDENTIFIER_COLUMNS_BY_KIND). */
const ACCOUNTS_CSV_TEXT =
  "unit_ref,account_no,customer_name,customer_kind,phone,customer_tax_id,account_type," +
  "ob_current,ob_31_60,ob_61_90,ob_90_plus\n" +
  "U-00101-A,SMK-0001,Smoke Alpha,person,512-555-0101,,residential,84.2000,62.1000,0.0000,121.0000\n" +
  "U-00101-B,SMK-0002,Smoke Bravo,person,512-555-0102,,residential,10.5000,0.0000,0.0000,0.0000\n" +
  "U-00102,SMK-0003,Smoke Charlie Ltd,company,,74-1234567,commercial,240.0000,0.0000,15.7500,0.0000\n";

/** BR-CUS-049's cutover date — ONE per run, and the date the opening journal
 *  entries are stamped with. A fixed date, never `new Date()`: a walkthrough
 *  that dated the books on the day it happened to run would be the money error
 *  the rule exists to prevent, rehearsed nightly. */
const ACCOUNTS_CUTOVER = "2026-08-01";

/** Raw i18n keys leaking into copy (DEF-532's second screenshot: the app
 *  printed `errors.not-found` to the user). `errors.` followed by a key
 *  segment — "3 errors." (dot then space/end) deliberately does not match. */
const RAW_KEY_RE = /\berrors\.[a-zA-Z][\w-]*/;

const failures = [];
const fiveHundreds = [];
let stepNo = 0;

function fail(step, message) {
  failures.push(`[${step}] ${message}`);
  console.error(`  ✗ ${message}`);
}

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  // The pinned revision is absent — find ANY installed chromium. This is a
  // smoke walkthrough, not a pixel test; an off-revision chromium beats not
  // running at all, and the mismatch is printed so nobody is surprised.
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) {
          console.log(`chromium: pinned revision missing; using ${candidate}`);
          return candidate;
        }
      }
    }
  }
  throw new Error(
    `no chromium found: playwright wants ${wanted} and neither it nor any ` +
      `chromium under ${roots.join(", ")} exists. Run: npx playwright install chromium ` +
      `(from 07-frontend).`,
  );
}

async function pageChecks(page, step) {
  // 1 — a main heading exists and says something.
  const heading = await page
    .locator("h1")
    .first()
    .textContent({ timeout: 5000 })
    .catch(() => null);
  if (heading === null || heading.trim() === "") {
    fail(step, `no main heading (<h1>) rendered at ${page.url()}`);
  }
  // 2 — no raw catalogue key in the visible text.
  const bodyText = (await page.locator("body").textContent().catch(() => "")) ?? "";
  const leaked = bodyText.match(RAW_KEY_RE);
  if (leaked !== null) {
    fail(step, `raw message key "${leaked[0]}" is visible in body text at ${page.url()}`);
  }
}

async function step(page, name, run) {
  stepNo += 1;
  const slug = `${String(stepNo).padStart(2, "0")}-${name.replace(/[^a-z0-9]+/gi, "-")}`;
  console.log(`step ${stepNo} · ${name}`);
  try {
    await run();
    await pageChecks(page, name);
  } catch (error) {
    fail(name, error instanceof Error ? error.message.split("\n")[0] : String(error));
  }
  await page
    .screenshot({ path: join(OUT, `${slug}.png`), fullPage: true })
    .catch((error) => console.error(`  (screenshot failed: ${error.message})`));
}

/**
 * Wait for the runner to reach stage `want` — and when it does not, say WHY.
 *
 * ⚠ A bare selector timeout reads as "the run stalled", which sends the next
 * reader looking for a background job that never ran. The day the accounts
 * CSV fell behind the server's required columns, the runner did not stall at
 * all: the server refused the stage with a 422 and the screen printed the
 * refusal in a `role="alert"` ("Map these columns first: account_no."), while
 * this walk reported only "Timeout 15000ms exceeded". So the alert text and
 * the stage the runner is actually on are part of the failure.
 */
async function expectStage(page, want) {
  try {
    await page.waitForSelector(`[data-workflow="runner"][data-stage="${want}"]`, {
      timeout: 15000,
    });
  } catch (error) {
    const at = await page
      .locator('[data-workflow="runner"]')
      .first()
      .getAttribute("data-stage", { timeout: 1000 })
      .catch(() => null);
    const alerts = (await page.locator('[role="alert"]').allInnerTexts().catch(() => []))
      .map((text) => text.trim())
      .filter(Boolean);
    throw new Error(
      `the runner never reached stage ${want} (it is on stage ${at ?? "?"})` +
        (alerts.length > 0
          ? ` — the screen says: ${alerts.join(" | ")}`
          : ` — no refusal on screen; ${error instanceof Error ? error.message.split("\n")[0] : error}`),
    );
  }
}

/**
 * BR-CUS-049's cutover date, typed into whatever control the accounts wizard
 * offers for it — and a NAMED failure when it offers none.
 *
 * The date is a property of the RUN and not of any column (`import_runs`'
 * stage-2 note: putting it in `columns` would make it look mappable from a CSV
 * header, which it is not), so it belongs beside the mapping table on stage 2.
 * Every plausible spelling is tried before the step is failed, so that a lane
 * that ships the control under a different id gets a green walkthrough rather
 * than a false alarm.
 */
async function fillCutoverDate(page, value) {
  const candidates = [
    "#import-cutover",
    "#import-cutover-on",
    "#import-cutover-date",
    '[data-workflow-option="cutover_on"] input',
    'input[name="cutover_on"]',
    'input[name="cutover_date"]',
    'input[type="date"]',
  ];
  for (const selector of candidates) {
    const field = page.locator(selector).first();
    if ((await field.count()) === 0) continue;
    await field.fill(value);
    return selector;
  }
  const labelled = page.getByLabel(/cutover/i).first();
  if ((await labelled.count()) > 0) {
    await labelled.fill(value);
    return "getByLabel(/cutover/i)";
  }
  return null;
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  console.log(`walkthrough: ${BASE} tenant=${TENANT} → screenshots in ${OUT}`);

  const browser = await chromium.launch({
    executablePath: resolveChromium(),
    headless: !HEADED,
  });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // DEF-529's class: any 5xx anywhere in the run is a failure, whatever the
  // screen made of it.
  page.on("response", (response) => {
    if (response.status() >= 500) {
      fiveHundreds.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });

  const csvPath = join(OUT, "smoke-premises.csv");
  writeFileSync(csvPath, CSV_TEXT);
  const accountsCsvPath = join(OUT, "smoke-accounts.csv");
  writeFileSync(accountsCsvPath, ACCOUNTS_CSV_TEXT);

  await step(page, "sign-in", async () => {
    await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
    await page.fill("#signin-email", EMAIL);
    await page.fill("#signin-password", PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 20000 });
  });

  await step(page, "dashboard", async () => {
    await page.waitForSelector("h1", { timeout: 15000 });
  });

  await step(page, "premises-list", async () => {
    await page.goto(`${BASE}/${TENANT}/premises`, { waitUntil: "networkidle" });
  });

  await step(page, "import-stage-1-extract", async () => {
    await page.goto(`${BASE}/${TENANT}/premises/import`, { waitUntil: "networkidle" });
    await expectStage(page, 1);
    await page.setInputFiles('input[type="file"]', csvPath);
  });

  await step(page, "import-stage-2-transform", async () => {
    await page.click('button:has-text("Transform →")');
    await expectStage(page, 2);
    const rows = await page.locator("[data-workflow-map-status]").count();
    if (rows === 0) throw new Error("stage 2 shows no mapping rows for a 3-column file");
  });

  await step(page, "import-stage-3-validate", async () => {
    await page.click('button:has-text("Validate →")');
    await expectStage(page, 3);
    // DEF-530's case: the operator ARRIVES at stage 3 with the numbers ON the
    // screen — a checked count of 0 over a 3-row file is that bug again.
    await page.waitForFunction(
      () => {
        const tile = document.querySelector('[data-workflow-figure="checked"]');
        return tile !== null && /[1-9]/.test(tile.textContent ?? "");
      },
      { timeout: 15000 },
    );
  });

  await step(page, "import-stage-4-load", async () => {
    await page.click('button:has-text("Load →")');
    await expectStage(page, 4);
  });

  await step(page, "import-header-back-link-keeps-tenant", async () => {
    // ⚠ DEF-532's case, verbatim: clicking this link once dropped the tenant,
    // the router read "premises" AS the tenant slug, and every screen in the
    // product failed from then on. Forward-only clicking cannot see it — the
    // walkthrough must go BACK too.
    await page.click(".page-header-back");
    await page.waitForLoadState("networkidle");
    const path = new URL(page.url()).pathname;
    if (!path.startsWith(`/${TENANT}/`) && path !== `/${TENANT}`) {
      throw new Error(`back link dropped the tenant: landed on ${path} (DEF-532)`);
    }
  });

  await step(page, "units-list", async () => {
    await page.goto(`${BASE}/${TENANT}/premises/units`, { waitUntil: "networkidle" });
  });

  await step(page, "plans-list", async () => {
    await page.goto(`${BASE}/${TENANT}/plans-rates`, { waitUntil: "networkidle" });
  });

  await step(page, "settings", async () => {
    await page.goto(`${BASE}/${TENANT}/settings`, { waitUntil: "networkidle" });
  });

  // ── CR-030 W1 · the ACCOUNT import, all five stages ────────────────────────
  //
  // Appended AFTER the premises leg rather than woven into it so the existing
  // steps keep their numbers, and therefore their screenshot filenames: a
  // walkthrough whose 07-import-stage-4-load.png silently becomes a different
  // screen is a diffing tool that cannot be diffed.
  await step(page, "accounts-list", async () => {
    await page.goto(`${BASE}/${TENANT}/accounts`, { waitUntil: "networkidle" });
  });

  await step(page, "account-import-stage-1-extract", async () => {
    // The route constant is `ACCOUNT_IMPORT_ROUTE` (`customersShared.tsx`),
    // mounted by `AccountImportWorkflowPage`, which mounts the SHARED
    // `ImportWorkflowPage` with `target="accounts"` (BR-MET-096 — one runner,
    // the target the only difference).
    await page.goto(`${BASE}/${TENANT}/accounts/import`, { waitUntil: "networkidle" });
    await expectStage(page, 1);
    // ⚠ The runner it mounts must be the ACCOUNTS one. If `accounts` ever
    // falls out of `WORKFLOW_KINDS` the page renders BR-SHL-025's stated
    // absence instead — an <h1> and a paragraph, which every check above
    // passes. Ask the runner which kind it is.
    const kind = await page
      .locator('[data-workflow="runner"]')
      .first()
      .getAttribute("data-kind");
    if (kind !== "accounts") {
      throw new Error(
        `the accounts import route mounted the "${kind}" runner, not "accounts" ` +
          `(BR-MET-096 — or the kind is unregistered and this is the stated-absence page)`,
      );
    }
    await page.setInputFiles('input[type="file"]', accountsCsvPath);
  });

  await step(page, "account-import-stage-2-transform", async () => {
    await page.click('button:has-text("Transform →")');
    await expectStage(page, 2);
    const rows = await page.locator("[data-workflow-map-status]").count();
    if (rows === 0) throw new Error("stage 2 shows no mapping rows for an 11-column file");
    // ⚠ WAIT FOR THE PICKER TO BE POPULATED BEFORE JUDGING — OR SCREENSHOTTING —
    // THIS SCREEN. `MAPS TO` is filled from `GET /imports/{id}/columns`
    // (BR-MET-088), a SECOND request that lands after stage 2 renders; until it
    // does, every row's select holds only `— ignore —` and the TRANSFORM column
    // falls back to the raw target id. The first run of this leg photographed
    // exactly that and it reads like a defect — seven columns marked `Matched`
    // beside seven pickers saying `— ignore —`. It is not one: 2.5s later the
    // select carries 32 options with the right one chosen. A screenshot the next
    // reader has to be told to disbelieve is worse than no screenshot.
    await page.waitForFunction(
      () => {
        const select = document.querySelector('[data-workflow="mapping"] tbody select');
        return select !== null && select.options.length > 1;
      },
      { timeout: 15000 },
    );
    // ⚠ BR-CUS-049 — the ONE batch option this target needs. It is required
    // BEFORE stage 4 writes anything, so it is typed here, on the stage that
    // stores `mapping_spec`, and its absence is a finding rather than a
    // silently-skipped field.
    const usedSelector = await fillCutoverDate(page, ACCOUNTS_CUTOVER);
    if (usedSelector === null) {
      throw new Error(
        "no cutover-date control on the accounts import: BR-CUS-049 requires one " +
          "whenever an opening-balance column is present, and this file carries all " +
          "four — so stage 4 must refuse before it writes",
      );
    }
    console.log(`  · cutover date ${ACCOUNTS_CUTOVER} typed into ${usedSelector}`);
  });

  await step(page, "account-import-stage-3-validate", async () => {
    await page.click('button:has-text("Validate →")');
    await expectStage(page, 3);
    // DEF-530's case again: the operator ARRIVES with the numbers on screen.
    await page.waitForFunction(
      () => {
        const tile = document.querySelector('[data-workflow-figure="checked"]');
        return tile !== null && /[1-9]/.test(tile.textContent ?? "");
      },
      { timeout: 15000 },
    );
  });

  await step(page, "account-import-stage-4-load", async () => {
    await page.click('button:has-text("Load →")');
    await expectStage(page, 4);
    // The rehearsal is the SERVER's (B15 §16 TC-16 — "a dry run that lies is
    // worse than none"). Three rows naming three free units must be three
    // creations; a zero here means the rows were rejected upstream and the
    // commit below would write nothing while still reaching stage 5.
    await page.waitForFunction(
      () => {
        const tile = document.querySelector('[data-workflow-figure="create"]');
        return tile !== null && /[1-9]/.test(tile.textContent ?? "");
      },
      { timeout: 15000 },
    );
  });

  await step(page, "account-import-stage-5-receipt", async () => {
    // The ONE writing control in the product's import path — B14's danger tier
    // ("Commit load ✓", `data-writes="true"`).
    await page.click('button:has-text("Commit load ✓")');
    await expectStage(page, 5);
    // BR-MET-090 past the commit: the receipt prints what the run RECORDED.
    // A stage-5 frame over a receipt of zero loaded rows is DEF-530's shape
    // one stage along — arriving at the result before there is a result.
    const loaded = await page
      .locator('[data-workflow-figure="loaded"]')
      .first()
      .textContent({ timeout: 15000 });
    if (!/[1-9]/.test(loaded ?? "")) {
      throw new Error(`the receipt reports "${(loaded ?? "").trim()}" loaded for a 3-row file`);
    }
  });

  await browser.close();

  for (const line of fiveHundreds) {
    failures.push(`[5xx] ${line}`);
  }

  console.log("");
  if (failures.length > 0) {
    console.error(`WALKTHROUGH FAILED — ${failures.length} finding(s):`);
    for (const line of failures) console.error(`  · ${line}`);
    console.error(`screenshots: ${OUT}`);
    process.exit(1);
  }
  console.log(`walkthrough clean · ${stepNo} steps · screenshots in ${OUT}`);
}

main().catch((error) => {
  console.error(`walkthrough could not run: ${error.message}`);
  process.exit(2);
});
