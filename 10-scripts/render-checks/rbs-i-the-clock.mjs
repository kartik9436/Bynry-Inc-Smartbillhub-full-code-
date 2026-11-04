/**
 * RENDERED-OUTPUT CHECK — `US-RBS-007`, `CR-075` wave I: **nobody opens the
 * product**, and afterwards a clerk can read what happened.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. And the Product
 * Owner's own definition of done, 2026-09-06: *"everything should be executed
 * based on actual code, and rules that we place, also ensure you do web
 * walkthorugh before you sign off the user story or build"*.
 *
 * ⚠ **NOTHING IN THIS FILE STARTS A RUN, AND THAT IS THE POINT.** The runs it
 * reads were started by `apps/runbooks/scheduler.py`'s sweep — the same function
 * the beat entry calls once a minute — driven by
 * `10-scripts/render-checks/rbs_i_seed_schedule.py`. A walkthrough that pressed
 * **Run ▶** would be proving `RBS-005`, which is somebody else's wave.
 *
 * ⚠ **AND THE SEEDER ALREADY FOUND ONE DEFECT THAT NO TEST COULD (`DEF-RBS-4363`).**
 * The job body opened a nested tenant context; `core.tenancy.tenant_context`
 * CLEARS on exit rather than restoring, so `core.jobs.run_job`'s next statement
 * read the RLS-FORCEd `jobs` table with no tenant and raised *unknown job*. The
 * RUN was written correctly, so every unit test passed — and the default suite
 * runs on SQLite, which has no row-level security and could not have failed on
 * it at all.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \
 *     python3.12 10-scripts/render-checks/rbs_i_seed_schedule.py --tenant brazosbend
 *
 *   SMOKE_SKIP_SEED=1 SMOKE_API_PORT=8091 SMOKE_WEB_PORT=8092 \
 *     ./10-scripts/11-smoke-stack.sh
 *
 *   SMOKE_BASE=http://127.0.0.1:8092 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/rbs-i-the-clock.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  `RBS-001`'s *History →* is a LIVE LINK and not a disabled button — the
 *      hold released in the same commit as the screen (law 2's mirror);
 *   2  clicking it opens `RBS-008` by ADDRESS and by SCREEN ID;
 *   3  the seven columns the sheet draws, in the sheet's order;
 *   4  a **Failed** row is on the page — the missed firing, raised rather than
 *      absent (`BR-RBS-016`);
 *   5  its *Started* cell is a formatted DATE and not an ISO timestamp — the
 *      tenant's own zone and format (`BR-SHL-023`), which is the exact thing
 *      `DEF-RBS-4358` gets wrong one screen along;
 *   6  the **Failed** chip narrows the list ON THE SERVER — the row count and
 *      the pager's total both move, which a client-side `.filter()` cannot do;
 *   7  opening the failed row shows the sentence naming the missed time;
 *   8  `RBS-004`'s Overview *Next run* is a real date and no longer *Not set*;
 *   9  nothing a clerk can read carries a rule id, a screen id or a uuid
 *      (B14 rules 31 and 32);
 *  10  the page does not scroll sideways at 1440.
 */
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// ⚠ **`playwright-core` FROM THE FRONTEND'S OWN `node_modules`, NOT A BARE
// `import "playwright"`.** `10-scripts/` has no `package.json`, so a bare
// specifier resolves against nothing and the check dies with
// ERR_MODULE_NOT_FOUND before it has asserted anything — which reads exactly
// like a walkthrough nobody ran. Every sibling in this folder does it this way.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8092";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const KEY = process.env.SMOKE_RUNBOOK_KEY ?? "configuration_check";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-i-the-clock";
const VIEWPORT = { width: 1440, height: 1100 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\b(?:OQ|DEF|TC|US|EP|GT|RB|CR)-(?:[A-Z]{3}-)?\d{2,5}\b/,
  /\bRBS-\d{3}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/** An ISO instant printed raw into a cell — what `DEF-RBS-4358` looks like. */
const RAW_ISO = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  // The SERVER's own answers, captured rather than inferred. *Did the screen
  // draw it* and *did the server send it* are two different questions.
  const wire = [];
  page.on("response", async (response) => {
    if (!/\/runbooks\b/.test(response.url())) return;
    try {
      wire.push({ url: response.url(), body: await response.text() });
    } catch {
      /* a redirect or a bodyless response has nothing to read */
    }
  });
  const served = (match) => {
    const hit = wire.filter((w) => match.test(w.url)).pop();
    if (hit === undefined) return null;
    try {
      return JSON.parse(hit.body);
    } catch {
      return null;
    }
  };

  console.log("── sign in ───────────────────────────────────────────────");
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });

  console.log("── 1 · THE DOOR — History → is a LINK, not a held button ──");
  await page.goto(`${BASE}/${TENANT}/runbooks`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="RBS-001"]', { timeout: 30000 });
  const historyDoor = page.locator('a[href$="/runbooks/runs"], [data-open="history"]').first();
  await historyDoor.waitFor({ timeout: 30000 });
  const doorTag = await historyDoor.evaluate((el) => el.tagName);
  check(doorTag === "A", `History → is an <a> and not a disabled <button> (it is <${doorTag}>)`);
  check(
    (await historyDoor.getAttribute("href")) === `/${TENANT}/runbooks/runs`,
    "…and its href is the real address, not //host/… (DEF-CWP-3925)",
  );
  await page.screenshot({ path: join(OUT, "1-home-door.png"), fullPage: true });

  console.log("── 2 · IT OPENS RBS-008 ──────────────────────────────────");
  await historyDoor.click();
  await page.waitForURL(new RegExp(`/${TENANT}/runbooks/runs$`), { timeout: 30000 });
  await page.waitForSelector('[data-screen="RBS-008"]', { timeout: 30000 });
  check(true, "clicking History → opens RBS-008 — the door works");
  check(
    (await page.locator('[data-not-built-yet="true"]').count()) === 0,
    "…and it is NOT the not-built-yet screen",
  );
  await page.waitForSelector("tbody tr", { timeout: 30000 });
  await page.screenshot({ path: join(OUT, "2-run-history.png"), fullPage: true });

  console.log("── 2b · THE BADGE THE PO READS OFF A SCREENSHOT ──────────");
  // ⚠ **THIS ASSERTION EXISTS BECAUSE IT FAILED.** The first run of this
  // walkthrough drew **`RBS-004.runs`** in the bottom-right badge over a page
  // whose own `data-screen` said `RBS-008`: `routing/screenIds.ts` is walked in
  // ORDER and had no row for `/runbooks/runs`, so the badge fell through to
  // `/:tenant/runbooks/:key`. The router was right and the badge was wrong, and
  // the badge is the thing the Product Owner reads to say *which screen has a
  // problem* (CR-016 addendum, 2026-08-19). Nothing else looks at it.
  const badge = (await page.locator("body").innerText()).match(/\bRBS-\d{3}(?:\.\S+)?/);
  check(
    badge !== null && badge[0] === "RBS-008",
    `the screen-id badge reads ${JSON.stringify(badge?.[0] ?? "(none)")}`,
  );

  console.log("── 3 · THE SEVEN COLUMNS, IN THE SHEET'S ORDER ───────────");
  const headers = await page.$$eval("thead th", (cells) =>
    cells.map((c) => (c.textContent ?? "").trim()),
  );
  check(
    JSON.stringify(headers) ===
      JSON.stringify(["Started", "Runbook", "By", "Outcome", "Acted", "Took", "Actions"]),
    `columns are ${JSON.stringify(headers)}`,
  );

  console.log("── 4 · THE FIRST PAGE HAS ROWS AT ALL ────────────────────");
  // ⚠ **THE FAILED ROW IS ASSERTED AFTER THE CHIP, AND THE FIRST DRAFT OF THIS
  // CHECK LOOKED FOR IT HERE — WHICH IS LAW 7'S *LOOKING AT THE WRONG THING*.**
  // The utility has sixty runs and `per` defaults to fifty, so the one Failed
  // row is on page 2 and this check reported *a missed firing is an absence*
  // over a product that had raised it correctly. A red like that is worse than
  // no check: it teaches the next reader to ignore the file. The chip is where
  // the row is guaranteed to be, and it is a stronger assertion anyway — it
  // proves the SERVER can find it, not merely that it happened to be visible.
  const firstPage = await page.$$eval("tbody tr", (trs) => trs.length);
  check(firstPage > 0, `the first page draws ${firstPage} run(s)`);

  console.log("── 5 · THE CHIP FILTERS ON THE SERVER ────────────────────");
  const totalBefore = served(/\/runbooks\/runs\?/)?.count ?? null;
  await page.click('[data-chip="failed"]');
  await page.waitForTimeout(1500);
  const totalAfter = served(/\/runbooks\/runs\?/)?.count ?? null;
  const lastUrl = wire.filter((w) => /\/runbooks\/runs\?/.test(w.url)).pop()?.url ?? "";
  check(
    /f\.outcome=failed/.test(lastUrl),
    `the chip travelled to the server as f.outcome=failed (${lastUrl.split("?")[1] ?? "?"})`,
  );
  check(
    totalBefore !== null && totalAfter !== null && totalAfter < totalBefore,
    `the SERVER's own total moved ${totalBefore} → ${totalAfter}, which a client-side filter cannot do`,
  );
  const afterRows = await page.$$eval("tbody tr td:nth-child(4)", (tds) =>
    tds.map((td) => (td.textContent ?? "").trim()),
  );
  check(
    afterRows.length > 0 && afterRows.every((word) => word === "Failed"),
    `every row on the filtered page reads Failed (${afterRows.join(", ") || "none"})`,
  );
  await page.screenshot({ path: join(OUT, "3-failed-only.png"), fullPage: true });

  console.log("── 6 · BR-RBS-016 — the missed firing is FAILED, and readable ");
  const failedRows = await page.$$eval("tbody tr", (trs) =>
    trs.map((tr) =>
      Array.from(tr.querySelectorAll("td"), (td) => (td.textContent ?? "").trim()),
    ),
  );
  const failedRow = failedRows[0];
  check(
    failedRow !== undefined && failedRow[3] === "Failed",
    "a missed firing is a real Failed run — raised rather than being an absence",
  );
  if (failedRow !== undefined) {
    check(
      !RAW_ISO.test(failedRow[0]) && failedRow[0] !== "",
      `Started reads ${JSON.stringify(failedRow[0])} — a formatted date, not a raw instant`,
    );
    check(
      failedRow[2] === "Scheduled",
      `By reads ${JSON.stringify(failedRow[2])} — the schedule, not a person's name`,
    );
  }

  console.log("── 7 · THE MISSED TIME IS ON THE RUN'S OWN RESULT ────────");
  await page.click("tbody tr:first-child a[href*='/runs/']");
  await page.waitForURL(/\/runs\/[0-9a-f-]+$/, { timeout: 30000 });
  await page.waitForSelector('[data-screen="RBS-006"]', { timeout: 30000 });
  const resultText = (await page.locator('[data-screen="RBS-006"]').innerText()).replace(
    /\s+/g,
    " ",
  );
  check(
    /should have run/i.test(resultText),
    "the result names the firing that did not happen, in words",
  );
  check(
    /\bC[SD]T\b|\bUTC\b/.test(resultText),
    "…and it NAMES THE ZONE, so 06:00 on screen and 06:00 in a person's head are one time",
  );
  await page.screenshot({ path: join(OUT, "4-missed-sentence.png"), fullPage: true });

  console.log("── 8 · RBS-004 Overview — Next run is a real date ────────");
  await page.goto(`${BASE}/${TENANT}/runbooks/${KEY}`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="RBS-004"]', { timeout: 30000 });
  const detail = served(new RegExp(`/runbooks/${KEY}$`));
  check(
    detail !== null && typeof detail.schedule?.next_run === "string",
    `the SERVER serves schedule.next_run = ${JSON.stringify(detail?.schedule?.next_run ?? null)}`,
  );
  const overview = (await page.locator('[data-screen="RBS-004"]').innerText()).replace(
    /\s+/g,
    " ",
  );
  // ⚠ **THE SCREEN'S OWN WORD IS `Next`, NOT `Next run`.** The first draft of
  // this check searched for *Next run* — the phrase in the story — and reported
  // *(no Next run line)* over a screen that was drawing the date correctly.
  // A walkthrough must assert what the product says, not what the packet does.
  const nextRunLine = /\bNext\b[^A-Za-z0-9]*([^\n·]{3,40})/.exec(overview);
  check(
    nextRunLine !== null && !/not set/i.test(nextRunLine[1]),
    `the SCREEN draws it: ${JSON.stringify(nextRunLine?.[1]?.trim() ?? "(no Next line)")}`,
  );
  await page.screenshot({ path: join(OUT, "5-next-run.png"), fullPage: true });

  console.log("── 9 · NOTHING INTERNAL REACHES A CLERK (B14 31 · 32) ────");
  await page.goto(`${BASE}/${TENANT}/runbooks/runs`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="RBS-008"]', { timeout: 30000 });
  const visible = await page.locator('[data-screen="RBS-008"]').innerText();
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = pattern.exec(visible);
    check(hit === null, `no ${pattern} in the visible copy${hit ? ` — found ${hit[0]}` : ""}`);
  }

  console.log("── 10 · IT DOES NOT SCROLL SIDEWAYS AT 1440 ──────────────");
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `horizontal overflow is ${sideways}px`);

  await browser.close();
  console.log("");
  if (failures.length > 0) {
    console.log(`⛔ ${failures.length} FAILED:`);
    for (const one of failures) console.log(`   · ${one}`);
    process.exit(1);
  }
  console.log("✓ every assertion passed — screenshots in", OUT);
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
