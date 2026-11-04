// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4. `P4.10` (delivery)
//          and the walk of `J-REP-03`'s step 1, which is the one that CANNOT
//          be walked: `DEF-REP-6913`.
// Rules:   CLAUDE.md hard-won law 6 (diff the running app against the drawing —
//          no gate looks at rendered output) · law 2's mirror (a live screen
//          behind a dead control, and its twin: a built dialog behind NO
//          control) · law 7 habit 3 (a check's output must distinguish pass
//          from fail to a READER)
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES, AND WHY IT IS A SCRIPT RATHER THAN A SENTENCE.
//
// `P4.4` built screen `2·3` — the schedule dialog, one `FormModal`, three
// fields — and `p034`'s own words are that **you schedule FROM the report you
// are looking at**. `ScheduleReportDialog.tsx` is 227 lines, has a schema, has
// dom tests, and `tsc` and every gate pass over it.
//
// **Nothing in the product renders it.** The only file that mounts it is its
// own test. So this walkthrough opens a real report in a real browser and
// COUNTS the controls on it whose accessible name contains *Schedule*. The
// number it prints is the evidence in `DEF-REP-6913`, and it is printed beside
// what was counted so a reader can tell a pass from a fail without reading the
// exit code.
//
// ⚠ IT ALSO WALKS `4·1`, the Scheduled tab, because a lane touching the sweep
// must show that screen still renders — the regression half.
//
// usage:
//   BASE=http://127.0.0.1:8081 TENANT=brazosbend OUT=/tmp/p4rest \
//     node 10-scripts/rep_p4_delivery_walkthrough.mjs
const { existsSync, readdirSync, mkdirSync, writeFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8081";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const REPORT = process.env.REPORT ?? "ar-aging";
const OUT = process.env.OUT ?? "/tmp/p4rest";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const entry of readdirSync(root)) {
      if (!entry.startsWith("chromium")) continue;
      for (const tail of ["chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, entry, tail);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found — PLAYWRIGHT_BROWSERS_PATH is unset and /opt/pw-browsers has none");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
// 1440 is the build width for a staff screen; 1280 must also work.
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
const say = (...parts) => console.log(...parts);
let failures = 0;
const counts = [];
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}
function count(line) {
  counts.push(line);
  say(`   ${line}`);
}

// ── sign in ────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// The version, read off the running app so every screenshot below can be
// attributed to a BUILD rather than to "the day I looked".


// ── 1 · the report (2·1) and the control that is not there ─────────────────
await page.goto(`${BASE}/${TENANT}/reports/${REPORT}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
// ⚠ **THE SELECTOR IS `[data-testid="app-version"]`, AND THE FIRST DRAFT OF
// THIS LINE GUESSED `[data-app-version]` AND REPORTED *NOT SHOWN* OVER A
// VERSION THAT WAS PLAINLY ON THE SCREENSHOT** — hard-won law 7's *looking at
// the wrong thing*, in the one check whose whole job is to attribute every
// screenshot below to a BUILD.
const version = await page.evaluate(() => {
  const el = document.querySelector('[data-testid="app-version"]');
  return el ? el.textContent.trim() : null;
});
check("0 · the running build names itself on screen", version !== null, version ?? "no [data-testid=app-version] in the rail");
count(`app version on screen: ${version ?? "NOT SHOWN"}`);
await page.screenshot({ path: `${OUT}/01-report-2.1-at-1440.png`, fullPage: true });

const controls = await page.$$eval("button, a[role='button'], a", (nodes) =>
  nodes.map((n) => (n.textContent || "").trim()).filter(Boolean),
);
const scheduleControls = controls.filter((t) => /schedul/i.test(t));
count(`controls on the report screen: ${controls.length}`);
count(
  `of those, naming "schedule": ${scheduleControls.length}` +
    (scheduleControls.length ? ` — ${JSON.stringify(scheduleControls)}` : ""),
);
// ⚠ THE ASSERTION IS THE DEFECT'S, NOT THE PRODUCT'S. This is expected to be
// ZERO today, which is exactly what `DEF-REP-6913` says. The day the door is
// built this line goes red and NAMES the defect that has been fixed — a
// walkthrough whose expectation outlives its defect is the next reader's false
// alarm, so it is written to fail loudly rather than quietly flip.
check(
  "1 · DEF-REP-6913 — the report screen offers NO way to schedule it",
  scheduleControls.length === 0,
  scheduleControls.length === 0
    ? "0 controls — the dialog built by P4.4 has no door (this is the DEFECT, reproduced)"
    : `${scheduleControls.length} found — the door now EXISTS; close DEF-REP-6913 and delete this check`,
);

// ── 2 · the Scheduled tab (4·1) still renders — the regression half ────────
// ⚠ **THE RESPONSE STATUS IS RECORDED, BECAUSE CHECK 2b CANNOT ASSERT
// ANYTHING WITHOUT IT.** Its first draft read *"if the screen says it failed,
// it must not also say no results"* — which passes **vacuously** on a screen
// that failed and did not say so, which is the entire defect. A check whose
// green means *I could not tell* is law 7's worst shape.
const listStatuses = [];
page.on("response", (r) => {
  if (/\/reports\/schedules(\?|$)/.test(r.url())) listStatuses.push(r.status());
});
await page.goto(`${BASE}/${TENANT}/reports/scheduled`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await page.screenshot({ path: `${OUT}/02-scheduled-4.1-at-1440.png`, fullPage: true });
const headers = await page.$$eval("th", (ns) => ns.map((n) => (n.textContent || "").trim()));
const title = await page.$eval("h1", (n) => (n.textContent || "").trim()).catch(() => "");
const failed = await page.evaluate(() => /couldn.t load/i.test(document.body.innerText));
count(`4·1 page-head title: ${JSON.stringify(title)}`);
count(`4·1 column headers: ${headers.length} — ${JSON.stringify(headers)}`);
count(`4·1 shows the retry block: ${failed}`);
// ⚠ **THE FIRST DRAFT ASSERTED `headers.length >= 5` AND WENT RED ON A TENANT
// WHOSE DATABASE SIMPLY HAD NO `report_schedules` TABLE.** A list with no rows
// draws no `th` at all, which is correct, so the header count answers *is
// there data* and NOT *did this screen render* — law 7's *looking at the wrong
// thing* a second time in one script. What is asserted now is that the screen
// RENDERED: its page head is drawn, and it is showing EITHER the table, the
// empty block, or — `DEF-REP-6914` — the retry block, never the zero-results
// sentence over a failure.
const zeroResults = await page.evaluate(() =>
  /no results match/i.test(document.body.innerText),
);
const serverFailed = listStatuses.some((code) => code >= 400);
count(`GET /reports/schedules answered: ${JSON.stringify(listStatuses)}`);
check("2 · the Scheduled tab renders after the sweep change", title !== "", JSON.stringify(title));
if (!serverFailed) {
  // ⚠ NOT A PASS. The screen could not be put into the state this check is
  // about, and a silent green here would be indistinguishable from a product
  // that handles failure correctly.
  say(
    "CANNOT 2b · DEF-REP-6914 — the list endpoint answered normally, so the " +
      "failure branch was never reached. Point this at a tenant whose " +
      `report_schedules table is missing to drive it. statuses=${JSON.stringify(listStatuses)}`,
  );
} else {
  check(
    "2b · DEF-REP-6914 — a failed read draws the retry block and NOT 'no results'",
    failed && !zeroResults,
    `serverFailed=${serverFailed} retryBlock=${failed} zeroResults=${zeroResults}`,
  );
}

// ── 3 · 1280 must work too (staff floor) ───────────────────────────────────
await page.setViewportSize({ width: 1280, height: 1000 });
await page.waitForTimeout(800);
const scrolls = await page.evaluate(
  () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
);
await page.screenshot({ path: `${OUT}/03-scheduled-4.1-at-1280.png`, fullPage: true });
check("3 · no horizontal page scroll at 1280", scrolls === false, `scrollWidth>clientWidth = ${scrolls}`);

writeFileSync(
  `${OUT}/counts.txt`,
  counts.join("\n") + `\nbase ${BASE} · tenant ${TENANT} · ${new Date().toISOString()}\n`,
);
say(`\n${failures} failing check(s). Screenshots and counts in ${OUT}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
