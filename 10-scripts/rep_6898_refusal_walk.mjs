// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-REP-6898 — 27 of the 46 reports drew "The finance figures could
//          not be loaded / Something went wrong on our side. Nothing was
//          saved." over a refusal the product had already written down.
// Rules:   hard-won law 6 (no gate looks at rendered output — a browser walk is
//          what found this) · hard-won law 7 clause 3 (a check's output must
//          distinguish pass from fail TO A READER) and clause 5 (a number
//          beside every bucket, so a blind spot cannot look like an empty one)
//          · B14 rule 33 (a FACT ≤ 6 words on screen).
// ───────────────────────────────────────────────────────
//
// OPEN ALL FORTY-SIX REPORTS, ONE AT A TIME, AND SAY WHAT A CLERK SEES.
//
// ⚠ **THE PREVIOUS LANE'S WALK SCRIPT IS NOT IN THE REPOSITORY.**
// `scratchpad/po-shots/reports-wired/` holds its OUTPUTS — `walk-results.json`,
// `walk-notes.txt` and eleven screenshots — and no script. This is written to
// be the one that is kept, which is why it lives in `10-scripts/` rather than
// in a scratch folder.
//
// FOUR VERDICTS AND THEY SUM TO THE CATALOGUE. Three are good answers:
//   SERVED   — a payload and rows on screen.
//   REFUSED  — the product says, in six words, that it cannot produce this.
//   ASKS     — the screen wants a parameter first ("Choose an account.").
//   BROKEN   — anything else, and a 5xx is always this.
// A run that printed only the SERVED count would read identically whether the
// rest refused properly or fell through every branch and were counted by
// nobody. Every bucket gets a number and the four are added up out loud.
//
// USAGE:  BASE=http://127.0.0.1:8211 OUT=/tmp/shots node rep_6898_refusal_walk.mjs
const { existsSync, readdirSync, mkdirSync, writeFileSync, readFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8211";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/rep-6898";
// ⚠ **THE FORTY-SIX ARE READ FROM THE MIGRATION THAT SEEDS THEM, NOT TYPED
// HERE.** A literal list in this file is the count that rots: the day a
// forty-seventh definition is seeded, a hard-coded walk would report `46 of 46`
// and be silently blind to it — law 7's *reporting zero over a scope it
// excludes*. `tests/test_rep_wire_catalogue_reachable.py` reads the same file
// for the same reason. The total is asserted below rather than assumed.
const SEED = new URL("../06-backend/apps/reports/migrations/0003_seed_catalogue.py", import.meta.url);
const CATALOGUE = [
  ...readFileSync(SEED, "utf8").matchAll(
    /^\s*\("R\d+",\s*"([a-z0-9_]+)",\s*"([^"]*)",\s*"[^"]*",\s*"[^"]*",\s*"([a-z_]+)"/gm,
  ),
].map(([, key, name, dataset]) => ({ key, name, dataset }));
if (CATALOGUE.length !== 46) {
  // A guard on the guard: every count this script prints is relative to this
  // list, so a short read must stop the run rather than shrink the report.
  throw new Error(`read ${CATALOGUE.length} definitions from the seed, expected 46`);
}
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
  throw new Error("no chromium found — PLAYWRIGHT_BROWSERS_PATH is not set and /opt/pw-browsers has none");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const say = (...p) => console.log(...p);

let lastStatus = null;
page.on("response", (r) => {
  const url = r.url();
  if (url.includes("/api/") && url.includes("/reports/") && !url.endsWith("/reports")) {
    lastStatus = r.status();
  }
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say(`signed in as ${EMAIL} against ${BASE}`);

const results = [];
for (const row of CATALOGUE) {
  const segment = row.key.replace(/_/g, "-");
  lastStatus = null;
  await page.goto(`${BASE}/${TENANT}/reports/${segment}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  const seen = await page.evaluate(() => {
    const text = (document.body.textContent ?? "").replace(/\s+/g, " ");
    return {
      rows: document.querySelectorAll("table tbody tr").length,
      faultPanel: text.includes("Something went wrong on our side"),
      cannotProduce: text.includes("This report cannot be produced yet."),
      heading: text.includes("Report not available"),
      // A raw i18n key on screen is its own defect (DEF-REP-6900) and is
      // reported here rather than being allowed to read as a sentence.
      h1: (document.querySelector("h1")?.textContent ?? "").trim(),
      controls: document.querySelectorAll("main input, main select, form input, form select").length,
      snippet: text.slice(0, 160),
    };
  });
  // ⚠ **THE FOURTH CASE IS REAL AND THE FIRST DRAFT CALLED IT BROKEN.**
  // `account_ledger` is S59, a ROUTE card with its own screen, and that screen
  // asks for an account before it fetches anything — so NO report request is
  // made at all and `lastStatus` stays null. Reporting that as BROKEN would
  // have put a working screen in the defect column and made the four buckets
  // add up to a wrong story. It is only ASKS when the page actually RENDERED
  // (a heading) and offers something to fill in; a blank page with no request
  // is still BROKEN, which is what keeps this bucket from swallowing faults.
  let verdict;
  if (seen.faultPanel) verdict = "BROKEN";
  else if (seen.cannotProduce) verdict = "REFUSED";
  else if (lastStatus === 200) verdict = "SERVED";
  else if (lastStatus === 422) verdict = "ASKS";
  else if (lastStatus === null && seen.h1 !== "" && seen.controls > 0) verdict = "ASKS";
  else verdict = "BROKEN";
  results.push({ ...row, verdict, http: lastStatus, ...seen });
  say(
    `${verdict.padEnd(8)} ${row.key.padEnd(26)} HTTP ${String(lastStatus).padEnd(4)} ` +
      `${seen.rows} row(s)  ${seen.h1}`,
  );
}

const count = (v) => results.filter((r) => r.verdict === v).length;
say("");
say(
  `SERVED ${count("SERVED")}  REFUSED ${count("REFUSED")}  ASKS ${count("ASKS")}  ` +
    `BROKEN ${count("BROKEN")}  = ${results.length} of ${CATALOGUE.length}`,
);
writeFileSync(`${OUT}/walk-results.json`, JSON.stringify(results, null, 2));

// ── the three shots the defect asks for ────────────────────────────────────
// The SAME two reports the PO photographed on 2026-09-27, so the before and
// after shots can be put side by side: `read_completeness` is the one in
// `06-refused-read-completeness.png` and `ar_aging` the one in
// `02-receivables-ar-aging.png`.
const pick = (verdict, wanted) =>
  (results.find((r) => r.key === wanted && r.verdict === verdict) ??
    results.find((r) => r.verdict === verdict) ??
    {}).key ?? null;
const refusedKey = pick("REFUSED", "read_completeness");
const servedKey = pick("SERVED", "ar_aging");
if (refusedKey) {
  await page.goto(`${BASE}/${TENANT}/reports/${refusedKey.replace(/_/g, "-")}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}/01-viewer-says-the-real-reason.png`, fullPage: true });
}
if (servedKey) {
  await page.goto(`${BASE}/${TENANT}/reports/${servedKey.replace(/_/g, "-")}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${OUT}/02-a-working-report-still-works.png`, fullPage: true });
}
await page.goto(`${BASE}/${TENANT}/reports`, { waitUntil: "networkidle" });
await page.waitForTimeout(900);
await page.screenshot({ path: `${OUT}/03-catalogue-card-says-the-same-thing.png`, fullPage: true });

// A 1440-wide close-up of the SAME report, card and viewer, one above the
// other — the pair the defect is about.
if (refusedKey) {
  await page.goto(`${BASE}/${TENANT}/reports/${refusedKey.replace(/_/g, "-")}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}/04-${refusedKey}-viewer.png` });
}

await browser.close();
process.exit(count("BROKEN") === 0 ? 0 : 1);
