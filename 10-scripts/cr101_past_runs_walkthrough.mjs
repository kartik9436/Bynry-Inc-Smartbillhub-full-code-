#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-101-BRC03 §07 — blueprint screen 27 `Past billing runs`
//          (`/:tenant/billing/history` · the `history` tab of S30), built from
//          p145–p146 of `05-prototype/04 Billing, As Built.pdf`, read AS IMAGES
//          at scale 2 and the table band again at scale 4 (B14 rule 42).
// Defects: DEF-BIL-5351 (the grey panel over a working read) · DEF-BIL-5352
//          (the run status never advances) · DEF-BIL-5371 (the read is not
//          paginated and serves no total)
// Rules:   B14 rule 15 (row actions are icons) · rule 16 (the pagination
//          footer) · rule 31 (no database id is a visible value) · rule 32 (a
//          stated absence is a disclosure CLOSED by default)
// ───────────────────────────────────────────────────────
/**
 * Drive Past billing runs in a real browser and ASSERT what step 2 built.
 *
 * ⚠ **THIS EXISTS BECAUSE NOTHING ELSE IN THIS REPO READS RENDERED OUTPUT.**
 * `jsdom` lays nothing out, so the things that cost the most here — a grey
 * refusal still on screen, a disclosure that opens by default, a uuid in a
 * cell — are invisible to every suite and every gate. Hard-won law 6.
 *
 * ⚠ **IT EXITS NON-ZERO ON THE FIRST FAILED ASSERTION AND NEVER PRINTS `ok`
 * FROM A `&&`.** A check whose output cannot distinguish pass from fail is
 * worse than no check, because it is trusted (hard-won law 7, habit 3).
 *
 * ⚠ **AND IT PRINTS WHAT IT SKIPPED BESIDE WHAT IT CHECKED.** The demo tenant
 * holds THREE runs against the 34 the drawing illustrates, and two of the
 * drawn statuses — `Abandoned` and `Corrected` — have no row anywhere in this
 * database. A check reporting zero over a scope it silently excludes is
 * indistinguishable from an empty one, so the scope is printed.
 *
 * Stack: SPA on 8142, API on 8042 with `API_PROXY_TARGET` set, PostgreSQL up,
 * tenant `brazosbend`. ⚠ Without that proxy target every data call answers 502
 * while pages answer 200, and a walk begun in that state reports every screen
 * broken and every finding is false.
 *
 *   node 10-scripts/cr101_past_runs_walkthrough.mjs [width]     # 1440 | 1280
 */
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
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
  throw new Error("no chromium found");
}

const WIDTH = Number(process.argv[2] ?? 1440);
const BASE = process.env.SPA_BASE ?? "http://127.0.0.1:8142";
const TENANT = process.env.TENANT ?? "brazosbend";
const SHOTS = process.env.SHOT_DIR ?? null;

const failures = [];
function check(name, condition, detail) {
  if (condition) {
    console.log(`  PASS  ${name}`);
    return;
  }
  failures.push(`${name} — ${detail}`);
  console.log(`  FAIL  ${name} — ${detail}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const context = await browser.newContext({ viewport: { width: WIDTH, height: 1100 } });
const page = await context.newPage();
const pageErrors = [];
page.on("pageerror", (error) => pageErrors.push(String(error).slice(0, 240)));
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

console.log(`CR-101 §07 · Past billing runs · ${WIDTH}px · ${BASE}/${TENANT}`);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("#signin-email", { timeout: 60000 });
await page.fill("#signin-email", process.env.WALK_EMAIL ?? "dana@brazosbendutilities.com");
await page.fill("#signin-password", process.env.WALK_PASSWORD ?? "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── THE DOOR, FROM WHERE A PERSON WOULD ACTUALLY CLICK ─────────────────────
// Start on the Billing page and reach this screen by pressing its tab, not by
// typing its address: a screen that opens only when you type the URL is the
// shape two screens in this repo shipped in (skill §11, *check the door from
// the outside*).
await page.goto(`${BASE}/${TENANT}/billing`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("h1", { timeout: 30000 });
const tab = page.locator('a,button', { hasText: /^Past billing runs$/ }).first();
check("the tab is a real door on the Billing page", (await tab.count()) > 0, "no tab found");
await tab.click();
await page.waitForURL(/\/billing\/history/, { timeout: 30000 });
await page.waitForSelector("table tbody tr", { timeout: 30000 });
// ⚠ **WAIT FOR THE SECOND QUERY, NOT ONLY THE TABLE — THIS WALK REPORTED A
// FALSE FAILURE WITHOUT IT.** The rows arrive from `GET /billing/runs` and the
// CYCLE cell fills a moment later from the tenant's cycle list, so a snapshot
// taken when the table appears catches every cycle cell mid-flight and reads
// as "the column shows a dash for every row". The screen was right and the
// check was wrong — law 7's second habit, asking what makes a check FAIL
// wrongly as well as pass wrongly.
await page.waitForLoadState("networkidle");

const body = await page.locator("body").innerText();

// ── DEF-BIL-5351 · the refusal is gone ─────────────────────────────────────
check(
  "the grey panel is gone",
  !body.includes("arrives with the billing run work"),
  "the tab still refuses over a working read",
);
check("a table is rendered", (await page.locator("table").count()) > 0, "no table");

// ── the drawn columns, in the drawn order ──────────────────────────────────
// ⚠ **COMPARED CASE-INSENSITIVELY, AND THE REASON IS THE DRAWING.** p146 inks
// the header row in CAPS — `RUN CYCLE PERIOD BILLS VALUE RUN BY STATUS` — and
// the table type uppercases its headers to match, so the catalogue's `Run by`
// reaches the screen as `RUN BY`. A case-sensitive compare failed all six
// columns on a screen that was right; it is the check that was wrong.
const headers = await page.locator("table thead th").allInnerTexts();
const trimmed = headers.map((h) => h.trim().toUpperCase()).filter((h) => h !== "");
const drawn = ["RUN", "CYCLE", "PERIOD", "BILLS", "RUN BY", "STATUS"];
let cursor = -1;
for (const label of drawn) {
  const at = trimmed.indexOf(label);
  check(
    `column "${label}" is present and after the one before it`,
    at > cursor,
    `found at ${at}, previous at ${cursor} — headers: ${trimmed.join(" | ")}`,
  );
  if (at > cursor) cursor = at;
}

// ── B14 rule 31 · no database id is the visible value of a field ───────────
const uuid = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i;
check("no uuid is on screen", !uuid.test(body), `found ${body.match(uuid)?.[0] ?? ""}`);
check(
  "the cycle reads as a code",
  /\bCY-\d{3}\b/.test(body),
  "no cycle code on screen — the column may be showing a dash for every row",
);

// ── B14 rule 32 · the stated absence is CLOSED by default ──────────────────
const gap = page.locator("details[data-brun='gap']").first();
check("the gap disclosure exists", (await gap.count()) > 0, "no disclosure");
check(
  "the gap disclosure is CLOSED by default",
  (await gap.count()) > 0 && (await gap.evaluate((el) => !el.open)),
  "it opens by default, which is the content budget rule 32 exists to hold",
);

// ── the drill-in · every row opens the run it names ────────────────────────
const rows = page.locator("table tbody tr");
const rowCount = await rows.count();
check("rows are rendered", rowCount > 0, `${rowCount} rows`);
const targets = await rows.evaluateAll((els) =>
  els.map((el) => el.getAttribute("data-row-href")),
);
check(
  "every row carries its own run's address",
  targets.length > 0 && targets.every((t) => typeof t === "string" && t.includes("/billing/run?run=")),
  `targets: ${JSON.stringify(targets)}`,
);
check(
  "each row's address is DISTINCT — one run per row",
  new Set(targets).size === targets.length,
  `${new Set(targets).size} distinct of ${targets.length}`,
);

// ── B14 rule 16 · the pagination footer ────────────────────────────────────
check("the pager footer is drawn", body.includes("Rows per page"), "no pager");

// ── B14 rule 15 · the row action is an ICON with an accessible name ────────
const openAction = page.locator('[aria-label="Open run"]').first();
check("the row action is an icon with its name", (await openAction.count()) > 0, "no Open run control");
const actionText = (await openAction.count()) > 0 ? (await openAction.innerText()).trim() : "";
check(
  "the row action renders no text label (rule 15)",
  actionText === "",
  `it renders the text "${actionText}"`,
);

// ── the drill-in actually opens the run ────────────────────────────────────
const firstTarget = targets[0];
await page.goto(`${BASE}${firstTarget}`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("h1", { timeout: 30000 });
check(
  "the address a row points at opens the bill run, not a dead end",
  !(await page.locator("body").innerText()).includes("not built yet"),
  "the run address opens a placeholder",
);
await page.goBack({ waitUntil: "domcontentloaded" });
await page.waitForSelector("table tbody tr", { timeout: 30000 });
// ⚠ AND AGAIN AFTER THE BACK NAVIGATION, FOR THE SAME REASON AS ABOVE — the
// screenshots below are what the Product Owner reads beside the drawing, and
// the first run of this walk captured every CYCLE cell mid-flight, so the shot
// showed a dash on four rows over a screen that renders `CY-001` on three.
await page.waitForLoadState("networkidle");

// ── no horizontal scroll at this width ─────────────────────────────────────
const overflow = await page.evaluate(
  () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
);
check("the page body does not scroll sideways", overflow <= 0, `${overflow}px of overflow`);

if (SHOTS) {
  await page.screenshot({ path: `${SHOTS}/past-runs-${WIDTH}.png`, fullPage: true });
  await gap.evaluate((el) => (el.open = true));
  await page.screenshot({ path: `${SHOTS}/past-runs-${WIDTH}-absence-open.png`, fullPage: true });
  await gap.evaluate((el) => (el.open = false));
}

// ── THE CYCLE FILTER IS LIVE, AND THE EMPTY STATE IS REAL ──────────────────
// ⚠ **A DECLARED FILTER NOTHING DRIVES IS DEAD UI** (hard-won law 2): every
// suite can assert the config declares `cycle_id` and none of them can tell you
// the server narrowed anything. So it is PRESSED here, on a cycle this tenant
// has never billed — which is also the only way to see the EMPTY state in a
// database that holds runs.
const beforeFilter = await page.locator("table tbody tr").count();
await page.locator("details summary", { hasText: "Filter" }).first().click();
const emptyCycle = page.locator('label', { hasText: /^CY-00[4-7]$/ }).last();
check("the Cycle filter offers this tenant's cycles by code", (await emptyCycle.count()) > 0, "no cycle options");
const chosenCycle = (await emptyCycle.innerText()).trim();
await emptyCycle.click();
// ⚠ **`networkidle` IS NOT ENOUGH HERE AND THIS CHECK REPORTED A FALSE FAILURE
// WITHOUT THE LINE BELOW.** Changing the filter changes the query KEY, so there
// is no cached answer and the table renders its LOADING SKELETON — zero rows,
// no copy. `networkidle` can return before the refetch has even started, so the
// snapshot caught the skeleton and read as *"no filtered-empty copy on screen"*
// over a screen that renders it correctly a moment later. Wait for the SETTLED
// state — rows or the zero-results block — never for the network alone.
await page.waitForSelector(".state-zero, table tbody tr", { timeout: 30000 });
await page.waitForLoadState("networkidle");
const filterBody = await page.locator("body").innerText();
check(
  `choosing ${chosenCycle} narrows the list`,
  (await page.locator("table tbody tr").count()) < beforeFilter ||
    filterBody.includes("No billing run yet"),
  `still ${await page.locator("table tbody tr").count()} of ${beforeFilter} rows`,
);
// ⚠ **THE FILTERED-EMPTY STATE IS NOT THE CONSUMER'S EMPTY BLOCK, AND THIS
// CHECK ASSERTED THE WRONG COPY UNTIL THE WALK RAN.** `DataTable` renders the
// screen's own *"No billing run yet / Start a run to fill this."* only when
// `totalRows` is 0 AND no filter is applied — a list nobody has filled — and
// keeps the toolbar with *"No results match these filters"* when a filter is
// what emptied it, so a clerk can clear it. Both are right; the check was
// pointed at the first while driving the second.
check(
  "a filtered-empty list keeps its toolbar and offers a way back",
  filterBody.includes("No results match these filters") && filterBody.includes("Clear filters"),
  "no filtered-empty copy on screen",
);
check(
  "the applied filter is a chip a clerk can remove",
  filterBody.includes(chosenCycle),
  "the chosen cycle is not named on the toolbar",
);
if (SHOTS) {
  await page.screenshot({ path: `${SHOTS}/past-runs-${WIDTH}-empty-filtered.png`, fullPage: true });
}

// ── A KEYBOARD ALONE CAN OPERATE IT ────────────────────────────────────────
// ⚠ **A CLICKABLE `<div>` IS A DEFECT** — invisible to a keyboard and to a
// screen reader, and invisible to every text assertion too, which is why it is
// read off the DOM here rather than reasoned about from the source.
await page.locator('button[aria-label^="Remove"], button[title^="Remove"]').first().click().catch(() => {});
await page.waitForSelector("table tbody tr", { timeout: 30000 });
await page.waitForLoadState("networkidle");
const focusable = await page.evaluate(() => {
  const action = document.querySelector('[aria-label="Open run"]');
  if (action === null) return { reachable: false, tag: "missing" };
  action.focus();
  return { reachable: document.activeElement === action, tag: action.tagName };
});
check(
  "the row action takes keyboard focus",
  focusable.reachable,
  `activeElement did not become the action (it is a <${focusable.tag}>)`,
);
check(
  "the row action is a real link, not a clickable div",
  focusable.tag === "A" || focusable.tag === "BUTTON",
  `it is a <${focusable.tag}>`,
);
const handRolled = await page.evaluate(() =>
  [...document.querySelectorAll("table div[onclick], table span[onclick]")].length,
);
check("no clickable div or span in the table", handRolled === 0, `${handRolled} found`);

check("no uncaught page error", pageErrors.length === 0, pageErrors.join(" · "));

// ── WHAT THIS WALK DID NOT SEE, WITH ITS NUMBER (hard-won law 7) ───────────
await page.locator('button[aria-label^="Remove"], button[title^="Remove"]').first().click().catch(() => {});
await page.waitForLoadState("networkidle");
const statuses = await page.locator("table tbody tr .pill").allInnerTexts();
console.log(`\n  SCOPE — ${rowCount} run(s) in this tenant, against the 34 p146 illustrates.`);
console.log(`  statuses actually rendered: ${[...new Set(statuses.map((s) => s.trim()))].join(", ")}`);
console.log(
  "  NOT exercised, because no such row exists in this database: Abandoned, Corrected.",
);
console.log(
  "  NOT exercised here, because this tenant HAS runs: the unfilled empty state\n" +
    "  (covered by pastBillingRuns.dom.test.tsx TC-I11) and the failed read\n" +
    "  (covered by DataTable's own suite). A filtered-empty list IS exercised above.",
);

await browser.close();
if (failures.length > 0) {
  console.log(`\nFAILED ${failures.length}:`);
  for (const f of failures) console.log(`  · ${f}`);
  process.exit(1);
}
console.log(`\nALL CHECKS PASSED at ${WIDTH}px`);
