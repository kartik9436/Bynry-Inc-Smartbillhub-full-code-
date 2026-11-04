// ── THE TRANSFERS TAB, WALKED IN A BROWSER ─────────────────────────────────
//
// Accounts blueprint **p131 of the 281-page edition**, read AS IMAGES per B14
// rule 42. Run it after any change to `TransfersTab.tsx` or
// `apps/customers/transfer_reads.py`.
//
// **WHY IT EXISTS.** `DEF-CUS-5934`'s own prevention column, 2026-09-20:
// *"This flow has no walkthrough script in 10-scripts/ while move-in, move-out
// and the clerk request walk all have one — write one, and press every control
// rather than asserting the markup around it."* The PO found a screen-breaking
// defect on the transfer wizard in ONE pass of the live product while its 39
// unit tests were green, and the tab beside it had been describing a deleted
// job for nineteen days with every check passing.
//
// **WHAT ONLY THIS CAN SEE.** Three things the unit suite structurally cannot:
//   · the tab holds its table state in a `useState` no caller can seed
//     (DEF-664), so SEARCHING and CLEARING can only be exercised by pressing;
//   · `ZeroResults` vs `EmptyList` — two different empties with opposite
//     toolbar behaviour, and only one is reachable from a static render;
//   · whether anything scrolls sideways at 1280, which no assertion reads.
//
// ⚠ **IT REFUSES A STALE BUILD.** Nothing on the page says how old the bundle
// is, and `tsc`, the suites and every gate are green either way because none of
// them look at `dist/`.
//
// ⚠ **IT WRITES NOTHING** — every step is a GET or a keystroke in a search box.
// The rows come from `po20260920_transfers_tab_seed.py` and go away with
// `po20260920_transfers_tab_purge.py`.
//
//   TTW_BASE     default http://127.0.0.1:8977
//   TTW_TENANT   default brazosbend
//   TTW_EMAIL    default dana@brazosbendutilities.com
//   TTW_PASSWORD default S3cure!passw0rd
//   TTW_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser here, so the path is passed explicitly — never run
//      `playwright install` in this container.)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync } from "node:fs";

const BASE = process.env.TTW_BASE || "http://127.0.0.1:8977";
const T = process.env.TTW_TENANT || "brazosbend";
const EMAIL = process.env.TTW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.TTW_PASSWORD || "S3cure!passw0rd";
const CHROME =
  process.env.TTW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

try {
  const built = statSync("07-frontend/dist/index.html").mtime;
  const newestSrc = new Date(
    execSync("git log -1 --format=%cI -- 07-frontend/src").toString().trim(),
  );
  if (built < newestSrc) {
    console.error(
      `REFUSED: dist/ was built ${built.toISOString()} but 07-frontend/src has a\n` +
        `commit at ${newestSrc.toISOString()}. Run \`npx vite build\` first.`,
    );
    process.exit(2);
  }
  console.log(`build is current (dist ${built.toISOString()})`);
} catch {
  console.warn("! could not check build freshness — continuing");
}

let pass = 0;
let fail = 0;
const failures = [];
function ok(what, cond, detail = "") {
  if (cond) {
    pass += 1;
    console.log(`  ✓ ${what}`);
  } else {
    fail += 1;
    failures.push(what);
    console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`);
  }
}

async function signIn(context, width) {
  const p = await context.newPage({ viewport: { width, height: 1600 } });
  p.setDefaultTimeout(25000);
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

// ⚠ A HARD TIMEOUT ON THE WHOLE RUN (`DEF-GOV-5877`) — a walk that hangs is a
// walk nobody reads, and it holds the container open behind it.
const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });
  const context = await browser.newContext();
  const page = await signIn(context, 1440);

  await page.goto(`${BASE}/${T}/accounts?tab=transfers`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="S89"]', { timeout: 25000 });
  const text = () => page.textContent('[data-screen="S89"]');

  // ── 1 · THE THREE TILES, p131 ─────────────────────────────────────────
  console.log("\n1 · the KPI strip — three tiles, not five");
  const tileLabels = await page.$$eval('[data-screen="S89"] .kpi .k', (ns) =>
    ns.map((n) => n.textContent.trim()),
  );
  console.log("    tiles on screen:", JSON.stringify(tileLabels));
  ok("exactly three tiles", tileLabels.length === 3, `saw ${tileLabels.length}`);
  ok("Open", tileLabels[0] === "Open");
  ok("Selling this week", tileLabels[1] === "Selling this week");
  ok("Owed on accounts being sold", tileLabels[2] === "Owed on accounts being sold");
  for (const gone of [
    "Moving this week",
    "Deposits carrying",
    "Arrears following",
    "Completed this month",
  ]) {
    ok(`the deleted job's tile \`${gone}\` is gone`, !tileLabels.includes(gone));
  }
  const body = await text();
  ok("`Open`'s sub-line is the sale, not `same customer, new address`",
    body.includes("a sale part-way through") && !body.includes("same customer, new address"));
  ok("the money tile STATES its absence and shows no zero",
    (await page.$('[data-kpi-absent="owed"]')) !== null && !body.includes("$0.00"));

  // ── 2 · THE COLUMNS, p131 ─────────────────────────────────────────────
  console.log("\n2 · the columns");
  const heads = await page.$$eval('[data-screen="S89"] table.data-table thead th', (ns) =>
    ns.map((n) => n.textContent.replace(/[↑↓↕]/g, "").trim()).filter(Boolean),
  );
  console.log("    headings on screen:", JSON.stringify(heads));
  ok(
    "the drawn eight, in the drawn order",
    JSON.stringify(heads) ===
      JSON.stringify([
        "Reference", "Address", "Account", "Sold to", "Sale date", "Step", "Taken on", "State",
      ]),
    JSON.stringify(heads),
  );
  for (const gone of ["From account", "In date", "From → to", "Money", "Customer", "Out date"]) {
    ok(`\`${gone}\` is gone`, !heads.includes(gone));
  }
  ok("`Sold by` is NOT faked — held by ruling, DEF-CUS-5941", !heads.includes("Sold by"));

  // ── 3 · THE ROWS ──────────────────────────────────────────────────────
  console.log("\n3 · the rows");
  const rows = await page.$$eval('[data-screen="S89"] table.data-table tbody tr', (ns) =>
    ns.map((n) => Array.from(n.querySelectorAll("td")).map((td) => td.textContent.trim())),
  );
  console.log("    rows:", JSON.stringify(rows, null, 1));
  ok("four seeded rows are listed", rows.length === 4, `saw ${rows.length}`);
  ok(
    "the ACCOUNT cell is ONE account with no arrow",
    rows.every((r) => !r[2].includes("→")),
    JSON.stringify(rows.map((r) => r[2])),
  );
  ok(
    "no row shows a second address",
    (await page.$("[data-to-absent]")) === null,
  );
  const soldTo = await page.$$eval('[data-screen="S89"] tbody tr td:nth-child(4)', (ns) =>
    ns.map((n) => n.textContent.trim()),
  );
  ok(
    "an OPEN sale states the buyer's absence rather than naming the seller",
    soldTo.filter((v) => v.startsWith("Recorded when the sale completes")).length === 3,
    JSON.stringify(soldTo),
  );
  ok(
    "a COMMITTED sale names the buyer",
    soldTo.some((v) => v.includes("buyer committed")),
    JSON.stringify(soldTo),
  );
  const takenOn = await page.$$eval('[data-screen="S89"] tbody tr td:nth-child(7)', (ns) =>
    ns.map((n) => n.textContent.trim()),
  );
  console.log("    Taken on:", JSON.stringify(takenOn));
  ok(
    "`Taken on` is ONE figure or a dash — never two stacked sentences",
    takenOn.every((v) => !v.includes("deposit carried") && !v.includes("arrear follows")),
    JSON.stringify(takenOn),
  );
  // ⚠ **A COLUMN OF DASHES CANNOT TELL A WORKING MONEY CELL FROM A BROKEN
  // ONE**, which is why the seed makes one indebted account: without it the
  // whole walk passes over a `Taken on` that never renders a figure at all.
  ok(
    "a row carrying a balance shows the FIGURE, at 2 decimals",
    takenOn.some((v) => /^\$\d[\d,]*\.\d{2}$/.test(v)),
    JSON.stringify(takenOn),
  );
  ok(
    "and no fabricated zero anywhere in the column (DEF-127)",
    !takenOn.includes("$0.00"),
    JSON.stringify(takenOn),
  );
  ok("no `↗ Open` row action — held by ruling, DEF-CUS-5942",
    (await page.$('[data-screen="S89"] a[href*="/transfers/"]')) === null);

  // ── 4 · THE COPY BELOW THE TABLE ──────────────────────────────────────
  console.log("\n4 · the copy");
  ok("p131's red note reads `One account, not two.`", body.includes("One account, not two."));
  ok(
    "the counting contract is OFF the screen",
    !body.includes("the same job listed three times") && !body.includes("two halves"),
  );
  ok("`Taken on: the buyer owes this.`", body.includes("Taken on: the buyer owes this."));
  ok(
    "the moving-house line is the short pair",
    body.includes("A transfer is a sale.") && body.includes("Moving house needs a service request."),
  );
  ok(
    "the long version is gone",
    !body.includes("If the customer is moving to a new address, raise a new service request instead."),
  );

  // ── 5 · B14 RULE 12'S TOOLBAR, AND THE EMPTY THAT KEEPS IT ────────────
  console.log("\n5 · the toolbar, and the two empties");
  const search = await page.$('[data-screen="S89"] .table-toolbar input[type="search"], [data-screen="S89"] .table-toolbar input');
  ok("the search box is in the toolbar", search !== null);
  ok(
    "its prompt is the server's own SEARCH_HINT",
    (await search?.getAttribute("placeholder")) === "Customer, account #, or either address…",
    await search?.getAttribute("placeholder"),
  );
  // ⚠ **`All` IS RULE 12'S OWN DEFAULT CHIP AND MUST BE PRESENT** — the rule
  // reads `[Search…] [All | filter chips ×] [+ Filter ▾] … [▦ Columns]`. The
  // first draft of this assertion counted `All` as a SEGMENT and went red over
  // a toolbar that was correct. What p131 draws, and what rule 12 replaced, is
  // the FIXED strip `Open · Selling this week · Completed · All`.
  const toolbarButtons = await page.$$eval(
    '[data-screen="S89"] .table-toolbar button',
    (ns) => ns.map((n) => n.textContent.trim()),
  );
  console.log("    toolbar buttons:", JSON.stringify(toolbarButtons));
  ok("rule 12's `All` chip is present", toolbarButtons.includes("All"));
  ok(
    "no FIXED segment strip — chips, not p131's segments",
    !toolbarButtons.includes("Completed") &&
      !toolbarButtons.includes("Open") &&
      !toolbarButtons.includes("Selling this week"),
    JSON.stringify(toolbarButtons),
  );
  ok(
    "the `+ Filter ▾` panel is in the same toolbar row",
    (await page.$('[data-screen="S89"] .table-toolbar details summary')) !== null,
  );

  // ⚠ THE BRANCH A STATIC RENDER CANNOT REACH: filtered down to nothing.
  await search.fill("zzzz-no-such-transfer");
  await page.waitForTimeout(1500);
  const filtered = await text();
  ok(
    "searched to nothing — the TOOLBAR STAYS, so the clerk can get back",
    (await page.$('[data-screen="S89"] .table-toolbar input')) !== null,
  );
  ok(
    "…and it is ZeroResults, not the virgin empty state",
    !filtered.includes("No transfers yet"),
  );
  await search.fill("");
  await page.waitForTimeout(1500);

  // ── 6 · BOTH STAFF WIDTHS ─────────────────────────────────────────────
  console.log("\n6 · 1440 and 1280");
  for (const width of [1440, 1280]) {
    await page.setViewportSize({ width, height: 1600 });
    await page.waitForTimeout(600);
    const sideways = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    );
    ok(`no sideways page scroll at ${width}`, !sideways);
    const stillEight = await page.$$eval('[data-screen="S89"] thead th', (ns) => ns.length);
    ok(`all eight columns still drawn at ${width}`, stillEight === 8, `saw ${stillEight}`);
  }

  console.log(`\n${pass} passed, ${fail} failed`);
  if (fail > 0) {
    console.log("FAILED:");
    for (const f of failures) console.log(`  · ${f}`);
  }
  clearTimeout(KILL);
  await browser.close();
  process.exit(fail === 0 ? 0 : 1);
} catch (err) {
  console.error("WALK CRASHED:", err && err.message ? err.message : err);
  clearTimeout(KILL);
  if (browser) await browser.close();
  process.exit(4);
}
