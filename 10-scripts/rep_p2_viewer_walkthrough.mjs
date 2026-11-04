// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 2 · P2.11 — the runner for journey `J-REP-01`
//          (`08-qa/01-e2e/journeys/J-REP-01-open-a-report-and-find-one-bill.md`).
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate looks at rendered output) · hard-won law 7
//          clause 3 (a check's output must distinguish pass from fail to a
//          READER, not merely to an exit code).
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT A UNIT TEST CANNOT.
//
//  1 · **THE SORT CHANGES THE ORDER.** A DOM test can assert that pressing a
//      caret writes `sort=amount` into a URL. Only this can assert that the
//      ROWS came back in a different order, because the ordering is an ORDER BY
//      in PostgreSQL and the test suite runs on SQLite.
//  2 · **THE SEARCH REACHES THE SERVER.** `q` narrowing 45 rows to 1 is a
//      statement about a query plan, not about a component.
//  3 · **THE EXPORT CARRIES THE WHOLE SELECTION AND NOT THE PAGE.** Read off
//      the real `POST /exports` body, which is the only place the two halves
//      of §8.2 meet.
//  4 · **A PAGE PAST THE END CLAMPS.** It drew *"51–45 of 45"* on 2026-09-26.
//
// ⚠ **EVERY COUNT IS PRINTED BESIDE ITS CHECK.** The seeded tenant holds 45
// bills, which is ONE page, so the second-page step cannot be performed here
// and says so rather than passing quietly (law 7's fifth shape). The paging
// proof is `P2.9`, on PostgreSQL, with 40,000 rows.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8180";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/j-rep-01";
mkdirSync(OUT, { recursive: true });

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
  throw new Error("no chromium found — PLAYWRIGHT_BROWSERS_PATH is not set and /opt/pw-browsers has none");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const say = (...parts) => console.log(...parts);
let failures = 0;
let unprovable = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}
/** A step this fixture CANNOT perform. Printed with its number, never skipped. */
function cannot(label, why) {
  say(`CANNOT ${label} — ${why}`);
  unprovable += 1;
}

const reportRequests = [];
const exportPosts = [];
page.on("request", (r) => {
  const url = r.url();
  if (url.includes("/api/") && url.includes("/reports/")) reportRequests.push(url);
  if (r.method() === "POST" && url.includes("/exports")) exportPosts.push(r.postData() ?? "");
});

// ── 1 · sign in and open the catalogue ─────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say(`signed in as ${EMAIL}`);

await page.goto(`${BASE}/${TENANT}/reports`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
const catalogueCards = await page.$$eval("a, article", (ns) => ns.length);
check("1 · the catalogue opens", catalogueCards > 0, `${catalogueCards} elements`);
await page.screenshot({ path: `${OUT}/01-catalogue.png`, fullPage: true });

// ── 2 · the register, its basis and its grain ──────────────────────────────
async function openRegister(search = "") {
  await page.goto(`${BASE}/${TENANT}/reports/billing-register${search}`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("table tbody tr", { timeout: 20000 });
  await page.waitForTimeout(400);
}
await openRegister();
const head = await page.$eval(".fin-rollup", (n) => n.innerText.replace(/\s+/g, " ").trim());
check("2 · the head names the window AND the basis", /Posting date/.test(head), head);
const grain = await page.$eval("[data-grain]", (n) => n.textContent.trim()).catch(() => "");
check("2 · the grain line says what one row is", grain === "One row per bill", JSON.stringify(grain));
check("2 · …in four words (B14 rule 33 caps a FACT at six)", grain.split(/\s+/).length <= 6, grain);
const firstPage = await page.$$eval("table tbody tr td:first-child", (ns) =>
  ns.map((n) => n.textContent.trim()),
);
const pagerText = await page.$eval(".table-pager-range", (n) => n.textContent.trim());
say(`   rows on screen: ${firstPage.length} · pager: ${pagerText}`);
await page.screenshot({ path: `${OUT}/02-register.png`, fullPage: true });

// ── 3 · page to 3 ──────────────────────────────────────────────────────────
const total = Number((pagerText.match(/of\s+([\d,. ]+)/) ?? [])[1]?.replace(/[^\d]/g, "") ?? 0);
if (total > 100) {
  await openRegister("?page=3");
  const third = await page.$eval(".table-pager-range", (n) => n.textContent.trim());
  check("3 · page 3 is a different page", third !== pagerText, `${pagerText} → ${third}`);
} else {
  cannot(
    "3 · page to 3",
    `this tenant holds ${total} bills, which is one page of 50 — the paging proof is P2.9, on PostgreSQL, with 40,000 rows`,
  );
  // What CAN be proved here: a page past the end clamps rather than counting
  // backwards. It drew "51–45 of 45" on 2026-09-26.
  await openRegister("?page=2");
  const clamped = await page.$eval(".table-pager-range", (n) => n.textContent.trim());
  check(
    "3b · a page past the end CLAMPS instead of counting backwards",
    !/^\s*5\d+–4\d+/.test(clamped) && clamped === pagerText,
    clamped,
  );
}

// ── 4 · sort ───────────────────────────────────────────────────────────────
await openRegister();
const sortableHeaders = await page.$$eval("table thead th", (ns) =>
  ns.map((n) => ({ text: n.textContent.trim(), sortable: n.querySelector("button") !== null })),
);
say(`   headers: ${JSON.stringify(sortableHeaders)}`);
check(
  "4 · a caret is drawn only where the dataset declares a sort",
  sortableHeaders.some((h) => h.sortable) && sortableHeaders.some((h) => !h.sortable),
  JSON.stringify(sortableHeaders.map((h) => `${h.text}:${h.sortable}`)),
);
await openRegister("?sort=amount&dir=desc");
const byAmount = await page.$$eval("table tbody tr td:first-child", (ns) =>
  ns.map((n) => n.textContent.trim()),
);
check(
  "4 · sorting by amount changes the ORDER of the rows",
  JSON.stringify(byAmount) !== JSON.stringify(firstPage),
  `first row ${firstPage[0]} → ${byAmount[0]}`,
);
await page.screenshot({ path: `${OUT}/04-sorted.png`, fullPage: true });

// ── 5 · search one bill ────────────────────────────────────────────────────
const wanted = firstPage[0];
await openRegister();
reportRequests.length = 0;
// ⚠ **NOT `input[type="search"]` — THAT MATCHES THE APP SHELL's GLOBAL SEARCH
// BOX, which is the first one in the document.** Typing into it fires no report
// request at all, and the check then reads as a broken search rather than as a
// broken selector. Found the first time this ran.
const box = await page.$('.table-toolbar input, [class*="toolbar"] input[placeholder]');
await (box ?? (await page.$('input[placeholder="Search this report"]'))).fill(wanted);
await page.waitForTimeout(1600);
const found = await page.$$eval("table tbody tr td:first-child", (ns) =>
  ns.map((n) => n.textContent.trim()),
);
check(
  "5 · the search reaches the SERVER",
  reportRequests.some((u) => u.includes("q=")),
  JSON.stringify(reportRequests.slice(-1)),
);
check("5 · and it finds exactly the one bill", found.length === 1 && found[0] === wanted, JSON.stringify(found));
await page.screenshot({ path: `${OUT}/05-searched.png`, fullPage: true });

// ── 6 · export it ──────────────────────────────────────────────────────────
exportPosts.length = 0;
const download = await page.$('button[aria-label*="ownload"], .download-button, button[title*="ownload"]');
if (download === null) {
  check("6 · the export control is on the toolbar", false, "no download control found");
} else {
  await download.click();
  await page.waitForTimeout(1200);
  check("6 · the export is asked for", exportPosts.length === 1, JSON.stringify(exportPosts));
  const body = exportPosts[0] ?? "";
  say(`   export body: ${body}`);
  check(
    "6 · §8.2 — the file carries the clerk's SEARCH",
    body.includes(wanted),
    "the export must be the whole FILTERED set",
  );
  check(
    "6 · §8.2 — and carries NO page and NO per",
    !/"page"/.test(body) && !/"per"/.test(body),
    "a file made of page three is not a smaller file, it is a wrong one",
  );
}

say("");
say(`${failures === 0 ? "GREEN" : "RED"} — ${failures} failed, ${unprovable} unprovable on this tenant`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
