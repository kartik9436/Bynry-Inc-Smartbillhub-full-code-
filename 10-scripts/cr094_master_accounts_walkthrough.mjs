// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 2 wave F — remedy `R7` / commitment `ACC-S17`:
//          the **Accounts** tab on a master account's detail screen (S21).
//          Drawn at `05-prototype/02 Accounts Menu Blueprint.pdf` p189–192,
//          transcribed in `04-docs/05-modules/03-customers/08-screen-layouts.md`.
// Rules:   BR-CUS-1048 (this tab) · BR-CUS-068 (a master is an ordinary
//          `accounts` row) · BR-CUS-1010 (it hangs off the ADDRESS) ·
//          hard-won law 6 (diff the running app — no gate reads rendered
//          output) · hard-won law 7 (a check must be able to fail, and its
//          OUTPUT must distinguish pass from fail to a reader).
// ───────────────────────────────────────────────────────
//
// WHY THIS EXISTS RATHER THAN A `renderToStaticMarkup` CASE. `MasterAccountsTab
// .test.tsx` proves the tab's structure with a seeded query cache: it never
// crosses the wire, so it cannot see whether `GET /accounts?f.premises_id=`
// actually answers, whether `covered_units` reaches the cell, or whether the
// tab appears at all on a REAL master account. Every number below is read off
// the rendered page.
//
// ⚠ **IT IS WRITTEN TO GO RED, AND EACH CHECK NAMES WHAT IT SAW.** A
// walkthrough that only prints what it found cannot be distinguished from one
// that found nothing (law 7, habit 3), so every clause below ends in PASS or
// FAIL with the value beside it, and the script exits non-zero on any FAIL.
//
// USAGE
//     BASE=http://127.0.0.1:8712 \
//     CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//     node 10-scripts/cr094_master_accounts_walkthrough.mjs
//
// ⚠ `CHROMIUM_PATH` IS NOT OPTIONAL ON THIS IMAGE — `playwright-core` asks for
// a headless-shell build number that is not installed, and the failure reads
// like a code fault rather than a missing browser.
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8712";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
// `AC-2026-00052` — the demo utility's own master account, six accounts at its
// address. Its id, not its number, because the route takes an id.
const MASTER = process.env.MASTER ?? "01a09540-80d7-787f-9f1e-c493579e2184";
// `A-10432` — an ORDINARY account, for the negative half: no Accounts tab.
const REGULAR = process.env.REGULAR ?? "01a09540-727d-7b81-a750-49ddd2e237be";
const OUT =
  process.env.OUT ??
  "/tmp/claude-0/-home-user-SMARTBillHub/9cbb9b39-00da-5925-a69c-c6f1b1985b49/scratchpad/cr094-waveF";
mkdirSync(OUT, { recursive: true });

let failures = 0;
function check(id, what, got, ok) {
  const verdict = ok ? "PASS" : "FAIL";
  if (!ok) failures += 1;
  console.log(`[${id}] ${verdict} — ${what}\n        ${got}`);
}

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH ?? undefined,
  args: ["--no-sandbox", "--ignore-certificate-errors"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
async function shot(name) {
  const path = `${OUT}/${name}.png`;
  await page.screenshot({ path, fullPage: true });
  return path;
}

// ⚠ THE SIGN-IN IS TENANT-SCOPED AND ITS FIELD IDS ARE PREFIXED. The first
// draft used `${BASE}/signin` with `#email` and timed out on the locator, which
// reads like a broken page rather than the wrong address: PO 2026-08-10 made
// every authenticated URL `/{tenant}/…`, and the form's ids are `#signin-email`
// / `#signin-password` (the precedent every other walkthrough here uses).
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.includes("signin"), { timeout: 30000 });
console.log(`[00] signed in, landed on ${page.url()}`);

// ── 1 · THE TAB EXISTS, AND IT IS SECOND ──────────────────────────────────
await page.goto(`${BASE}/${TENANT}/accounts/${MASTER}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
const strip = await page.evaluate(() =>
  [...document.querySelectorAll('[role="tab"]')].map((el) => (el.textContent ?? "").trim()),
);
check(
  "1a",
  "the master's tab strip, in render order",
  JSON.stringify(strip),
  strip[0] === "Overview" && strip[1] === "Accounts" && strip.length === 13,
);
await shot("1a-master-overview");

// ── 2 · THE TABLE, AS DRAWN ───────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/accounts/${MASTER}?tab=accounts`, {
  waitUntil: "networkidle",
});
await page.waitForTimeout(1800);
const table = await page.evaluate(() => {
  const t = document.querySelector("table.data-table");
  if (!t) return { found: false };
  const headings = [...t.querySelectorAll("thead th")].map((el) =>
    (el.textContent ?? "").replace(/[▲▼]/g, "").trim(),
  );
  const rows = [...t.querySelectorAll("tbody tr.data-table-row")].map((tr) =>
    [...tr.querySelectorAll("td")].map((td) => (td.textContent ?? "").replace(/\s+/g, " ").trim()),
  );
  return {
    found: true,
    headings,
    rows,
    hasFoot: t.querySelector("tfoot") !== null,
    pager: (document.querySelector(".table-pager")?.textContent ?? "").replace(/\s+/g, " ").trim(),
  };
});
check("2a", "the table is on the page", JSON.stringify(table.found), table.found === true);
check(
  "2b",
  "the eight drawn column headings, left to right",
  JSON.stringify(table.headings),
  JSON.stringify(table.headings) ===
    JSON.stringify(["Account", "Unit", "Occupant", "Kind", "Status", "Since", "Balance", "Actions"]),
);
check(
  "2c",
  "how many accounts at this address, and the rows",
  `${table.rows?.length} row(s) · ${JSON.stringify(table.rows)}`,
  (table.rows?.length ?? 0) >= 2,
);
check(
  "2d",
  "there is NO total under the balance column (no <tfoot>)",
  `tfoot present: ${table.hasFoot}`,
  table.hasFoot === false,
);
check("2e", "the pagination footer the kit draws", table.pager, (table.pager ?? "").length > 0);
await shot("2-master-accounts-tab-1440");

// ── 3 · THE MASTER'S OWN ROW — MARKED, COUNTED, AND NOT A LINK ────────────
const masterRow = await page.evaluate(() => {
  const rows = [...document.querySelectorAll("table.data-table tbody tr.data-table-row")];
  const hit = rows.find((tr) => /This account/.test(tr.textContent ?? ""));
  if (!hit) return { found: false };
  const cells = [...hit.querySelectorAll("td")].map((td) =>
    (td.textContent ?? "").replace(/\s+/g, " ").trim(),
  );
  return {
    found: true,
    cells,
    linksInRow: [...hit.querySelectorAll("a")].map((a) => a.getAttribute("href")),
    openActions: [...hit.querySelectorAll('[aria-label="Open account"]')].length,
  };
});
check(
  "3a",
  "the master is IN the list and marked as the one you are on",
  JSON.stringify(masterRow.cells),
  masterRow.found === true,
);
check(
  "3b",
  "its UNIT cell counts the units its own agreements reach, and is not a unit label",
  `unit cell = ${JSON.stringify(masterRow.cells?.[1])}`,
  /Common areas ×\d+/.test(masterRow.cells?.[1] ?? ""),
);
check(
  "3c",
  "its row carries NO link back to this page and NO Open action",
  `links: ${JSON.stringify(masterRow.linksInRow)} · Open actions: ${masterRow.openActions}`,
  (masterRow.linksInRow ?? []).length === 0 && masterRow.openActions === 0,
);

// ── 4 · A TENANT ROW OPENS ITS OWN ACCOUNT ────────────────────────────────
const tenantHref = await page.evaluate(() => {
  const rows = [...document.querySelectorAll("table.data-table tbody tr.data-table-row")];
  const hit = rows.find((tr) => !/This account/.test(tr.textContent ?? ""));
  return hit?.querySelector('[aria-label="Open account"]')?.getAttribute("href") ?? null;
});
check(
  "4a",
  "a tenant row's Open action addresses that account's own detail",
  String(tenantHref),
  typeof tenantHref === "string" && new RegExp(`^/${TENANT}/accounts/[0-9a-f-]{36}$`).test(tenantHref),
);
if (typeof tenantHref === "string") {
  await page.goto(`${BASE}${tenantHref}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const landed = await page.evaluate(() => ({
    h1: (document.querySelector("h1")?.textContent ?? "").trim(),
    tabs: [...document.querySelectorAll('[role="tab"]')].map((el) => (el.textContent ?? "").trim()),
  }));
  check(
    "4b",
    "…and the door actually opens that account (not a 'not built yet')",
    `h1 = ${JSON.stringify(landed.h1)} · ${landed.tabs.length} tabs`,
    landed.h1.length > 0 && landed.tabs.length >= 12,
  );
}

// ── 5 · THE NEGATIVE HALF — AN ORDINARY ACCOUNT HAS NO SUCH TAB ───────────
await page.goto(`${BASE}/${TENANT}/accounts/${REGULAR}?tab=accounts`, {
  waitUntil: "networkidle",
});
await page.waitForTimeout(1200);
const regular = await page.evaluate(() => ({
  tabs: [...document.querySelectorAll('[role="tab"]')].map((el) => (el.textContent ?? "").trim()),
  selected: (
    document.querySelector('[role="tab"][aria-selected="true"]')?.textContent ?? ""
  ).trim(),
}));
check(
  "5a",
  "an ordinary account's strip does NOT carry Accounts",
  `${regular.tabs.length} tabs · ${JSON.stringify(regular.tabs)}`,
  !regular.tabs.includes("Accounts") && regular.tabs.length === 12,
);
check(
  "5b",
  "…and `?tab=accounts` there falls back to Overview rather than a blank body",
  `selected = ${JSON.stringify(regular.selected)}`,
  regular.selected === "Overview",
);
await shot("5-regular-account-no-tab");

// ── 6 · THE STAFF WIDTHS THE SKILL REQUIRES: 1440 AND 1280 ────────────────
await page.goto(`${BASE}/${TENANT}/accounts/${MASTER}?tab=accounts`, {
  waitUntil: "networkidle",
});
for (const width of [1440, 1280]) {
  await page.setViewportSize({ width, height: 1000 });
  await page.waitForTimeout(600);
  const overflow = await page.evaluate(() => ({
    body: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    tableBox: (() => {
      const t = document.querySelector("table.data-table");
      return t ? Math.round(t.getBoundingClientRect().width) : null;
    })(),
  }));
  check(
    `6-${width}`,
    `at ${width}px the page body does not scroll sideways`,
    `horizontal overflow = ${overflow.body}px · table width = ${overflow.tableBox}px`,
    overflow.body <= 0,
  );
  await shot(`6-master-accounts-${width}`);
}

// ── 7 · THE FILTER IS THE SERVER'S, AND THE REQUEST PROVES IT ─────────────
//
// ⚠ **THE FIRST DRAFT OF `7b` WAS A CHECK THAT COULD NOT FAIL — ITS VERDICT
// WAS THE LITERAL `true`.** It attached the request listener AFTER the
// navigation, observed `0 /accounts request(s)`, and reported PASS anyway. That
// is hard-won law 7's own shape inside a walkthrough written to demonstrate law
// 7, which is why it is written out here rather than quietly corrected: a
// verdict that does not read its evidence is decoration. The listener now goes
// on BEFORE the navigation and the verdict is the request URL.
await page.setViewportSize({ width: 1440, height: 1000 });
const accountRequests = [];
page.on("request", (r) => {
  if (/\/api\/.*\/accounts\?/.test(r.url())) accountRequests.push(r.url());
});
await page.goto(`${BASE}/${TENANT}/accounts/${MASTER}?tab=accounts`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const scoped = accountRequests.filter((u) => u.includes("f.premises_id="));
check(
  "7a",
  "the rows come from the SERVER, scoped to this address — not from a client-side match",
  `${accountRequests.length} /accounts request(s), ${scoped.length} carrying f.premises_id: ${JSON.stringify(scoped.map((u) => u.slice(u.indexOf("/accounts?"))))}`,
  scoped.length >= 1,
);
const filterOpened = await page.evaluate(() => {
  const btn = [...document.querySelectorAll("button,summary")].find((el) =>
    /filter/i.test(el.textContent ?? ""),
  );
  if (!btn) return false;
  btn.click();
  return true;
});
await page.waitForTimeout(800);
const statusOffered = await page.evaluate(() => {
  const panel = document.querySelector("details[open], [role='dialog']") ?? document.body;
  const text = (panel.textContent ?? "").replace(/\s+/g, " ");
  return { offered: /Status/.test(text), options: (text.match(/Marked disconnect|Vacation hold|Pending activation/g) ?? []).length };
});
check(
  "7b",
  "the drawn segment strip renders as ONE Status filter chip (B14 rule 12), with the seeded statuses behind it",
  `filter control opened: ${filterOpened} · Status offered: ${statusOffered.offered} · seeded options seen: ${statusOffered.options}`,
  filterOpened === true && statusOffered.offered === true && statusOffered.options >= 2,
);
await shot("7-status-filter");

writeFileSync(`${OUT}/walkthrough.json`, JSON.stringify({ failures }, null, 2));
await browser.close();
console.log(`\n${failures === 0 ? "ALL CHECKS PASS" : `${failures} CHECK(S) FAILED`}`);
process.exit(failures === 0 ? 0 : 1);
