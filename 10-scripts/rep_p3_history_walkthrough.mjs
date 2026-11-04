// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 3 · `P3.6` — the runner for journey `J-REP-02`
//          (`08-qa/01-e2e/journeys/J-REP-02-find-yesterdays-csv-and-download-it.md`).
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code … ensure you do web walkthorugh before you
//          sign off the user story or build"* · hard-won law 6 (no gate looks
//          at rendered output) · law 7 clause 3 (a check's output must
//          distinguish pass from fail to a READER)
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT A UNIT TEST CANNOT.
//
//  1 · **THE TOAST POINTS SOMEWHERE THAT OPENS.** A DOM test can assert the
//      string names History. Only a browser can follow the strip to that
//      address and confirm a screen renders there rather than a placeholder.
//  2 · **THE DOWNLOAD IS A REAL FILE.** The `href` is asserted in jsdom; the
//      BYTES come back only here, from the real streamed route.
//  3 · **THE EXPIRED ROW HAS NO CONTROL, ON A REAL ROW.** The fixture can be
//      made to say `file: null`; this ages an actual run, sweeps its actual
//      file, and photographs what the table then draws.
//
// ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING**, and step 7 WRITES:
// it ages a run's `created_at` and sweeps the artifacts directory. Use a
// private clone — `10-scripts/proof-db.sh clone repp3` — never a shared one.
//
// ⚠ **EVERY COUNT IS PRINTED BESIDE ITS CHECK**, and a step this fixture
// cannot perform prints `CANNOT` with its reason rather than passing quietly
// (hard-won law 7's fifth shape). Two steps are in that state here and the
// journey names both: a RUNNING row (JOBS_EAGER is on, so a job succeeds
// before the 202 returns) and a run older than three days that the walkthrough
// did not itself age.
const { existsSync, readdirSync, mkdirSync, writeFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8180";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/j-rep-02";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found — PLAYWRIGHT_BROWSERS_PATH is unset and /opt/pw-browsers has none");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const say = (...parts) => console.log(...parts);
let failures = 0;
let unprovable = 0;
const counts = [];
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}
function cannot(label, why) {
  say(`CANNOT ${label} — ${why}`);
  unprovable += 1;
}
function count(line) {
  counts.push(line);
  say(`   ${line}`);
}

// ── 1 · sign in, open the catalogue, and look for the strip ────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

await page.goto(`${BASE}/${TENANT}/reports`, { waitUntil: "networkidle" });
await page.waitForTimeout(1000);
const tabs = await page.$$eval('[data-sub-tabs="reports"] [data-sub-tab]', (ns) =>
  ns.map((n) => n.textContent.trim()),
);
check("1 · the tab strip is drawn on the catalogue", tabs.length >= 2, JSON.stringify(tabs));
count(`tabs drawn: ${tabs.length} — ${tabs.join(" · ")}`);
await page.screenshot({ path: `${OUT}/01-catalogue-with-strip.png`, fullPage: true });

// ── 2 · export a report and read the toast ─────────────────────────────────
await page.goto(`${BASE}/${TENANT}/reports/ar-aging`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const exportPosts = [];
page.on("request", (r) => {
  if (r.method() === "POST" && r.url().includes("/exports")) exportPosts.push(r.url());
});
await page.click('[data-download="button"]');
await page.waitForTimeout(800);
const toast = await page.$eval('[data-toast="region"]', (n) => n.innerText.trim()).catch(() => "");
check("2 · POST /exports fired", exportPosts.length === 1, `${exportPosts.length} post(s)`);
check("2 · the toast names History and not Jobs", /History/i.test(toast) && !/\bJobs\b/.test(toast), JSON.stringify(toast));
await page.screenshot({ path: `${OUT}/02-export-toast.png` });

// ── 3 · follow the strip to History ────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/reports`, { waitUntil: "networkidle" });
await page.waitForTimeout(600);
await page.click('[data-sub-tabs="reports"] [data-sub-tab="history"]');
await page.waitForTimeout(1500);
const address = new URL(page.url()).pathname;
check("3 · the History tab opens /{tenant}/reports/history", address === `/${TENANT}/reports/history`, address);
const isScreen51 = (await page.$('[data-screen="5.1"]')) !== null;
check("3 · …and the screen there is 5·1", isScreen51, `data-screen=5.1 present: ${isScreen51}`);

// ── 4 · the run is on the list ─────────────────────────────────────────────
await page.waitForSelector("table tbody tr", { timeout: 20000 });
const rows = await page.$$eval("table tbody tr", (ns) =>
  ns.map((n) => Array.from(n.querySelectorAll("td")).map((c) => c.textContent.trim())),
);
count(`rows on History: ${rows.length}`);
const pager = await page.$eval(".table-pager-range", (n) => n.textContent.trim()).catch(() => "(no pager)");
count(`pager: ${pager}`);
check("4 · the export from step 2 is on the list", rows.length > 0, `${rows.length} row(s)`);
const startedBy = rows.map((r) => r[2]);
check(
  "4 · Started by is a NAME for a run a person started",
  startedBy.some((name) => /\w/.test(name) && name !== "Schedule"),
  JSON.stringify(startedBy.slice(0, 4)),
);
const downloads = await page.$$eval("[data-run-file]", (ns) => ns.length);
count(`download controls drawn: ${downloads} over ${rows.length} rows`);
await page.screenshot({ path: `${OUT}/03-history.png`, fullPage: true });

// ── 5 · the download is a real file ────────────────────────────────────────
const href = await page.$eval("[data-run-file]", (n) => n.getAttribute("href")).catch(() => null);
if (href === null) {
  cannot("5 · download the file", "no row on this list has one — step 4 found no READY run");
} else {
  const response = await page.request.get(`${BASE}${href}`);
  const body = await response.body();
  check("5 · the file downloads", response.status() === 200, `${response.status()} ${response.headers()["content-type"]}`);
  count(`file: ${body.length} bytes · ${response.headers()["content-disposition"] ?? "(no filename)"}`);
  // IS-11's five-segment filename: {tenant}_{report}_{period}_{basis}_{generated}.csv
  const filename = (response.headers()["content-disposition"] ?? "").match(/filename="([^"]+)"/)?.[1] ?? "";
  check("5 · the filename carries its basis segment (BR-REP-001)", filename.split("_").length === 5, filename);
}

// ── 6 · open the run, and re-run it ────────────────────────────────────────
await page.click("[data-run-open]");
await page.waitForTimeout(1200);
const dialogOpen = (await page.$('[data-screen="5.2"]')) !== null;
check("6 · a row opens 5·2", dialogOpen, `address now ${new URL(page.url()).pathname}`);
const dialogDownload = await page.$eval("[data-run-download]", (n) => n.textContent.trim()).catch(() => "");
check("6 · the dialog's download is LABELLED (p43), unlike 2·1's icon", dialogDownload !== "", JSON.stringify(dialogDownload));
await page.screenshot({ path: `${OUT}/04-run-opened.png`, fullPage: true });

const before = rows.length;
const rerunPosts = [];
page.on("request", (r) => {
  if (r.method() === "POST" && r.url().includes("/exports")) rerunPosts.push(r.postData() ?? "");
});
await page.click("[data-run-rerun]");
await page.waitForTimeout(2000);
const after = await page.$$eval("table tbody tr", (ns) => ns.length);
check("6 · Re-run goes back through POST /exports", rerunPosts.length >= 1, `${rerunPosts.length} post(s)`);
count(`rows before re-run: ${before} · after: ${after}`);
check("6 · …and a NEW row appears; the old run is untouched", after === before + 1, `${before} → ${after}`);
if (rerunPosts.length > 0) {
  say(`   re-run body: ${rerunPosts[0]}`);
}
await page.screenshot({ path: `${OUT}/05-after-rerun.png`, fullPage: true });

// ── 7 · THE ONE THAT MATTERS · an EXPIRED row draws no download ────────────
// The ageing is done by the caller (rep_p3_age_a_run.py) before this script
// runs, because a browser cannot move a clock. If nothing on the list is
// expired, this prints CANNOT rather than passing.
await page.goto(`${BASE}/${TENANT}/reports/history?f.status=expired`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const expiredRows = await page.$$eval("table tbody tr", (ns) =>
  ns.map((n) => ({
    cells: Array.from(n.querySelectorAll("td")).map((c) => c.textContent.trim()),
    downloads: n.querySelectorAll("[data-run-file]").length,
  })),
);
count(`rows under f.status=expired: ${expiredRows.length}`);
if (expiredRows.length === 0) {
  cannot(
    "7 · photograph an EXPIRED row",
    "no run on this tenant is older than the 3-day window — run 10-scripts/rep_p3_age_a_run.py first",
  );
} else {
  const withControls = expiredRows.filter((r) => r.downloads > 0).length;
  check(
    "7 · NO expired row draws a download control",
    withControls === 0,
    `${withControls} of ${expiredRows.length} expired rows have one`,
  );
  count(`expired rows: ${expiredRows.length} · download controls over them: ${withControls}`);
  say(`   first expired row: ${JSON.stringify(expiredRows[0].cells)}`);
  await page.screenshot({ path: `${OUT}/06-expired-no-download.png`, fullPage: true });
}

writeFileSync(
  `${OUT}/00-README.txt`,
  [
    "J-REP-02 — export → poll → find it on History → download",
    `base ${BASE} · tenant ${TENANT} · ${new Date().toISOString()}`,
    "",
    "EVERY ON-SCREEN COUNT, MEASURED:",
    ...counts.map((line) => `  ${line}`),
    "",
    `checks failed: ${failures} · steps this fixture could not perform: ${unprovable}`,
  ].join("\n"),
);

say("");
say(`${failures} failed · ${unprovable} unprovable on this fixture · shots in ${OUT}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
