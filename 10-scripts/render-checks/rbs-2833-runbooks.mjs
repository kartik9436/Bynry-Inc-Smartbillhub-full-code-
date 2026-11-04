/**
 * RENDERED-OUTPUT CHECK — CR-075 runbooks 28 and 33, in a browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. And the Product
 * Owner's own definition of done, 2026-09-06: *"ensure you do web walkthorugh
 * before you sign off the user story or build"*.
 *
 * ⚠ **NEITHER RUNBOOK SHIPS A LINE OF FRONTEND CODE, WHICH IS WHY THIS MATTERS
 * MORE RATHER THAN LESS.** Both are drawn by `RBS-004` and `RBS-006`, which are
 * RENDERERS over a definition and a report — so the only thing standing between
 * a correct backend and an error boundary is whether each block's PAYLOAD is
 * the shape the renderer reads. `DEF-RBS-4352` is exactly that gap: the
 * collections ladder shipped `breakdown {by, rows, rungs}` where the renderer
 * needs `{heading, columns, rows}`, every test on both sides passed, and
 * `RBS-006` drew an error boundary instead of 835 planned notices. A backend
 * assertion cannot see it, because the report crosses the wire as untyped JSON.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…smartbillhub \
 *     python3.12 10-scripts/render-checks/rbs_2833_seed.py --tenant brazosbend
 *   … which prints SMOKE_METERS_RUN_ID and SMOKE_BUDGET_RUN_ID.
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…smartbillhub \
 *     python3.12 06-backend/manage.py runserver 127.0.0.1:8077 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4277 API_PROXY_TARGET=http://127.0.0.1:8077 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4277 SMOKE_METERS_RUN_ID=… SMOKE_BUDGET_RUN_ID=… \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/rbs-2833-runbooks.mjs
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   RUNBOOK 28 — meters past change-out age or never tested
 *   1  **THE VERDICT SAYS WHAT HAPPENED IN PLAIN WORDS**, read from the DOM.
 *   2  **THE BLIND-SPOT RATIO IS ON THE SCREEN.** *8 of 8 cannot be judged*
 *      beside *0 past change-out age* — the whole reason this runbook is
 *      trustworthy, and a tile the renderer dropped would leave a clean bill of
 *      health that is a lie.
 *   3  **THE RECORDS TABLE DREW A ROW PER METER**, each carrying one of the
 *      two labels the commitment names.
 *   4  **EVERY FIX IS A REAL DESTINATION** — a resolvable href under the
 *      tenant, never `//host/…`, which reads as a perfectly good href to a
 *      substring assertion (`DEF-CWP-3925`).
 *   5  **CLICKING ONE LANDS ON A SCREEN THAT EXISTS** — the half of
 *      `BR-RBS-011` no unit test can reach.
 *
 *   RUNBOOK 33 — budget billing re-level
 *   6  **THE FIVE KPI TILES DREW WITH THE RUN'S OWN NUMBERS.**
 *   7  **THE ACTION IS DRAWN DISABLED WITH ITS REASON, NOT HIDDEN** — B14: a
 *      control a user may not use is disabled with its reason. This is the
 *      runbook's whole posture on screen.
 *   8  **NOTHING ON THE PAGE CLAIMS A LEVEL MOVED.** No *Done*, no *Applied*,
 *      no *Sent* — a run that changed nothing must not read as one that did
 *      (hard-won law 1).
 *
 *   BOTH
 *   9  **B14 RULES 31 AND 32** — no database id, no rule id, no BR/OQ/DEF code
 *      anywhere a clerk reads.
 *  10  **MONEY IS SHOWN TO TWO DECIMALS ON SCREEN**, never the stored four
 *      (hard rule 2).
 *  11  **THE PAGE DOES NOT SCROLL SIDEWAYS** at 1440.
 *  12  **NO REACT ERROR BOUNDARY AND NO CONSOLE ERROR** — the `DEF-RBS-4352`
 *      check, and the only one that can see a payload/renderer mismatch.
 *
 * ⚠ **WHAT THIS CHECK CANNOT SAY, STATED RATHER THAN LEFT AS A THIN PASS.**
 * Runbook 33's Records table is EMPTY on this deployment and the walkthrough
 * asserts its empty state instead of its rows. The reason is a fact about the
 * tenant rather than about the runbook: this utility has exactly **two**
 * non-sample budget accounts and both bill an identical amount every month, so
 * no level can drift — and the sample guard (`BR-RBS-012`) correctly keeps the
 * other ten out. The populated table, **4 rows and $51.00 a month**, is proved
 * in `06-backend/tests/test_us_rbs_044_budget_relevel.py` and in the lane
 * report's guards-lifted measurement, and this file says so rather than
 * asserting rows it knows will be absent.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4277";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const METERS_RUN = process.env.SMOKE_METERS_RUN_ID ?? "";
const BUDGET_RUN = process.env.SMOKE_BUDGET_RUN_ID ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-2833-runbooks";
const VIEWPORT = { width: 1440, height: 1000 };

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
  /\b(?:OQ|DEF|TC|US|EP|GT|RB)-(?:[A-Z]{3}-)?\d{2,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/** Money on a screen is TWO decimals; four is the stored form (hard rule 2). */
const STORED_MONEY = /\$?\d[\d,]*\.\d{4}\b/;

if ([METERS_RUN, BUDGET_RUN].some((one) => one === "")) {
  console.error(
    "⛔ both run ids must be set. This check reads STORED runs — seed them first with\n" +
      "   10-scripts/render-checks/rbs_2833_seed.py; see the header.",
  );
  process.exit(2);
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (m) => {
    if (m.type() === "error") {
      consoleErrors.push(m.text().slice(0, 200));
      console.log(`   [console.error] ${m.text().slice(0, 200)}`);
    }
  });

  // The server's own answer, captured rather than inferred. *Did the screen
  // draw it* and *did the server send it* are two different questions, and
  // `DEF-RBS-4284` is what happens when only one is asked.
  let wire = [];
  page.on("response", async (response) => {
    if (!/\/runbooks\//.test(response.url())) return;
    try {
      wire.push({ url: response.url(), body: await response.text() });
    } catch {
      /* a redirect or a bodyless response has nothing to read */
    }
  });

  console.log("── sign in ───────────────────────────────────────────────");
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });
  console.log("   ✓ signed in");

  async function open(key, runId, shot) {
    wire = [];
    consoleErrors.length = 0;
    await page.goto(`${BASE}/${TENANT}/runbooks/${key}/runs/${runId}`, {
      waitUntil: "networkidle",
    });
    // ⚠ `networkidle` IS NOT ENOUGH — the page fetches through `useQuery`, so
    // the first navigation can return with the LOADING SKELETON on screen and a
    // broken WAIT then reads as a broken SCREEN. Wait for the skeleton to GO.
    await page
      .waitForFunction(() => document.querySelector(".skeleton") === null, { timeout: 20000 })
      .catch(() => {});
    await page.screenshot({ path: join(OUT, shot), fullPage: true });
    const reportBody = wire.find((w) => /\/report\b/.test(w.url))?.body ?? "";
    return {
      text: await page.innerText("body"),
      report: reportBody,
      sideways: await page.evaluate(SIDEWAYS),
    };
  }

  // ── runbook 28 ─────────────────────────────────────────────────────────
  console.log("\n── runbook 28 · Meters past change-out age or never tested ─");
  const meters = await open("meter_change_out", METERS_RUN, "rb128-result.png");
  check(meters.report !== "", "the server sent a report for runbook 28");
  check(/Meters past change-out age/i.test(meters.text), "1 · the run names the runbook");
  check(
    /No test on file/i.test(meters.text) && /Past change-out age/i.test(meters.text),
    "1 · both of the commitment's two groups are on the screen",
  );
  check(
    /Cannot be judged/i.test(meters.text) && /\b8 of 8\b/.test(meters.text),
    "2 · the blind-spot RATIO is drawn — 8 of 8 cannot be judged",
  );
  check(
    /could not be judged on age/i.test(meters.text),
    "2 · and the verdict says it in words, beside the zero",
  );
  const meterRows = await page.$$eval(
    "table tbody tr",
    (rows) => rows.map((r) => r.innerText.replace(/\s+/g, " ").trim()),
  );
  check(meterRows.length === 8, `3 · the records table drew a row per meter (${meterRows.length})`);
  check(
    meterRows.every((r) => /Order a test|Schedule change-out/.test(r)),
    "3 · every row carries one of the commitment's two labels",
  );
  const meterLinks = await page.$$eval("table tbody tr a", (as) =>
    as.map((a) => ({ href: a.getAttribute("href") ?? "", abs: a.href })),
  );
  check(meterLinks.length > 0, "4 · the fix is a real anchor, not a span");
  check(
    meterLinks.every((l) => l.href.startsWith(`/${TENANT}/`) && !l.href.startsWith("//")),
    `4 · every fix href is tenant-prefixed and resolvable (${meterLinks[0]?.href})`,
  );
  if (meterLinks.length) {
    await page.goto(meterLinks[0].abs, { waitUntil: "networkidle" });
    const landed = await page.innerText("body");
    check(
      !/not built yet|coming soon|404|Page not found/i.test(landed),
      "5 · clicking the fix lands on a screen that exists",
    );
    await page.screenshot({ path: join(OUT, "rb128-fix-lands.png"), fullPage: true });
  }

  // ── runbook 33 ─────────────────────────────────────────────────────────
  console.log("\n── runbook 33 · Budget billing re-level ───────────────────");
  const budget = await open("budget_relevel", BUDGET_RUN, "rb133-result.png");
  check(budget.report !== "", "the server sent a report for runbook 33");
  check(/Budget billing re-level/i.test(budget.text), "6 · the run names the runbook");
  // ⚠ **CASE-INSENSITIVE, AND THE FIRST VERSION OF THIS CHECK WAS NOT.** It
  // used `text.includes("On budget billing")` and reported FIVE failures over a
  // screen that was drawing all five tiles perfectly — `RBS-006` renders a KPI
  // label in capitals, so the comparison was asking a question about the
  // stylesheet rather than about the tile. A check whose failure a reader
  // cannot act on is worse than no check (hard-won law 7, habit 3).
  // The VALUE is asserted beside the label, because a tile that drew its label
  // and lost its number is `DEF-RBS-4375`'s exact shape — four labels and no
  // figures — and a label-only assertion passes straight over it.
  for (const [label, value] of [
    ["On budget billing", "12"],
    ["Levels that should move", "0"],
    ["Change a month", "—"],
    ["Inside the band", "2"],
    ["Not yet due", "0 early · 0 short"],
  ]) {
    const tile = new RegExp(
      `${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\n\\s*${value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`,
      "i",
    );
    check(tile.test(budget.text), `6 · the KPI tile "${label}" drew, carrying ${value}`);
  }
  const action = await page.$$eval("button", (bs) =>
    bs
      .filter((b) => /Apply the new levels/i.test(b.innerText))
      .map((b) => ({ text: b.innerText.trim(), disabled: b.disabled })),
  );
  check(action.length === 1, "7 · the Apply control is PRESENT, not hidden");
  check(action[0]?.disabled === true, "7 · and it is drawn DISABLED");
  check(
    /No door moves a budget level/i.test(budget.text),
    "7 · with its reason beside it, in five words",
  );
  check(
    !/\b(Applied|Done|Sent|Completed)\b/.test(budget.text),
    "8 · nothing on the page claims a level moved",
  );
  check(
    /Nothing was changed and nobody was told/i.test(budget.text),
    "8 · and the verdict says so out loud",
  );
  // ⚠ **THE CHECK THIS WALKTHROUGH EXISTS FOR.** Runbook 33's Records table is
  // EMPTY on this tenant, and the first build passed `empty` as a plain STRING
  // where `RecordsPayload.empty` is `{title, helper}` — so the block rendered a
  // BLANK AREA between the KPI strip and the Action button. No error, no
  // console warning, no failing backend test, and `validate_report` cannot see
  // it because `PAYLOAD_FIELDS` closes the field NAMES and not their SHAPES
  // (`DEF-RBS-4406`). It was found by looking at the screenshot and by nothing
  // else, which is hard-won law 6 in one sentence.
  check(
    /Every level is where it should be/i.test(budget.text),
    "8b · the EMPTY records block draws its sentence and not a blank area",
  );
  check(
    /No level is far enough from what the last twelve months support/i.test(budget.text),
    "8b · with its helper line beneath",
  );

  // ── both ───────────────────────────────────────────────────────────────
  console.log("\n── both screens ──────────────────────────────────────────");
  for (const [name, screen] of [
    ["runbook 28", meters],
    ["runbook 33", budget],
  ]) {
    const offender = FORBIDDEN_IN_CLERK_COPY.map((re) => screen.text.match(re)).find(Boolean);
    check(!offender, `9 · ${name}: no id or rule code in clerk copy${offender ? ` — ${offender[0]}` : ""}`);
    const stored = screen.text.match(STORED_MONEY);
    check(!stored, `10 · ${name}: money is shown to two decimals${stored ? ` — ${stored[0]}` : ""}`);
    check(screen.sideways === 0, `11 · ${name}: the page does not scroll sideways at 1440`);
  }
  // ⚠ **THE WEBFONT IS EXCLUDED BY NAME AND THE EXCLUSION CARRIES ITS COUNT**
  // (hard-won law 7: a declared blind spot with no number beside it is
  // indistinguishable from an empty one). This sandbox has no route to
  // `fonts.googleapis.com`, so every page load logs one `ERR_CONNECTION_RESET`
  // for the stylesheet — a fact about the network rather than about the screen.
  // Excluding the whole category would hide a real failed API call, so only
  // that host is dropped and the number dropped is printed.
  const external = consoleErrors.filter((one) => /Failed to load resource/.test(one));
  const ours = consoleErrors.filter((one) => !/Failed to load resource/.test(one));
  check(
    ours.length === 0,
    `12 · no console error from the application (${external.length} external resource ` +
      "failure(s) excluded — the webfont this sandbox cannot reach)",
  );
  const boundary = /Something went wrong|error boundary|Unexpected Application Error/i;
  check(
    !boundary.test(meters.text) && !boundary.test(budget.text),
    "12 · no React error boundary — the payload is the shape the renderer reads",
  );

  await browser.close();
  console.log(`\n   screenshots in ${OUT}`);
  if (failures.length) {
    console.log(`\n⛔ ${failures.length} check(s) failed:`);
    failures.forEach((f) => console.log(`   · ${f}`));
    process.exit(1);
  }
  console.log("\n✅ every check passed");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
