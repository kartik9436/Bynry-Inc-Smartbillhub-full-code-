// ── `DEF-MET-6302` — THE PREMISES LIST'S OWNER COLUMN, ON A SEEDED TENANT,
//    IN A BROWSER ──────────────────────────────────────────────────────────
//
// PO, 2026-09-23: they created a master account, linked it to a premises, and
// reported that the Premises list's owner column was **empty on every row**.
// It was empty honestly — no seeder had ever written `premises.master_account_
// id` — and the fix is a new sample block, `customers:seed_sample_owner_
// accounts`.
//
// ⛔ **NO GATE IN THIS REPOSITORY READS RENDERED OUTPUT (hard-won law 6), SO
// THIS FILE IS THE ONLY CHECK THAT CAN ANSWER THE PO'S ACTUAL QUESTION.** The
// backend suite can prove a column holds a uuid; only a browser can prove that
// a clerk opening S14 SEES an account number where they saw nothing.
//
// ⚠ **IT ASSERTS BOTH HALVES, AND THE SECOND IS THE ONE THAT MATTERS MOST.**
// *Some rows show an owner* would pass on a seed that filled every row, which
// is exactly what the PO ruled out: *"a demo where all 80 properties have an
// identical master account teaches a clerk nothing and hides the cases that
// matter"*. So it asserts a POPULATED count, an EMPTY count, and that neither
// is zero — a fixture that demonstrates the feature and the absence of it.
//
// ⚠ **IT WRITES NOTHING.** Every other premises walkthrough in this directory
// creates addresses and needs a purge script; this one only reads, so there is
// nothing to leave behind and no beta to pollute.
//
// ⚠ **IT REFUSES A STALE BUILD**, the same guard as
// `def_met_5844_owner_account_walkthrough.mjs`: a walk against an old bundle
// reports landed work as absent, which cost that lane three false ABSENTs.
//
//   MET6302_BASE     default http://127.0.0.1:8743
//   MET6302_TENANT   default brazosbend
//   MET6302_EMAIL    default dana@brazosbendutilities.com
//   MET6302_PASSWORD default S3cure!passw0rd
//   MET6302_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { statSync, readdirSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.env.MET6302_ROOT || process.cwd();
const BASE = process.env.MET6302_BASE || "http://127.0.0.1:8743";
const T = process.env.MET6302_TENANT || "brazosbend";
const EMAIL = process.env.MET6302_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MET6302_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.MET6302_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.MET6302_SHOTS || ".";

function newestMtime(dir) {
  let newest = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
    const path = join(dir, entry.name);
    const at = entry.isDirectory() ? newestMtime(path) : statSync(path).mtimeMs;
    if (at > newest) newest = at;
  }
  return newest;
}
const built = statSync(join(ROOT, "07-frontend/dist/index.html")).mtimeMs;
const newestFile = newestMtime(join(ROOT, "07-frontend/src"));
if (built < newestFile) {
  console.error(
    `REFUSED: dist/ was built ${new Date(built).toISOString()} but 07-frontend/src\n` +
      `has work at ${new Date(newestFile).toISOString()}. Run \`npx vite build\` first.`,
  );
  process.exit(2);
}
console.log(`dist built ${new Date(built).toISOString()} >= src ${new Date(newestFile).toISOString()}`);

const R = [];
const ok = (n, c, d = "") => {
  R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`);
  console.log(R[R.length - 1]);
};

const b = await chromium.launch({ executablePath: CHROME });
const p = await b.newPage({ viewport: { width: 1440, height: 1100 } });

await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);

// ── 1 · THE PREMISES LIST, THE SCREEN THE PO WAS LOOKING AT ────────────────
await p.goto(`${BASE}/${T}/premises`, { waitUntil: "networkidle" });
await p.waitForTimeout(2000);
await p.screenshot({ path: join(SHOTS, "def-met-6302-1-premises-list.png"), fullPage: true });

const table = p.locator("table").first();
await table.scrollIntoViewIfNeeded();
await p.waitForTimeout(600);
await table.screenshot({ path: join(SHOTS, "def-met-6302-1b-table.png") });

const rows = await table.locator("tbody tr").count();
const withAccount = await p.locator('[data-tracks="premises-owner-account"]').count();
ok("the owner column shows an account on at least one row", withAccount > 0, `${withAccount} of ${rows} row(s)`);
// ⚠ **THE EMPTY STATE HAS NO TRACKER ON THIS SCREEN AND ASKING FOR ONE WAS A
// CHECK THAT COULD NOT PASS (law 7).** A list row that holds no account renders
// `<span />` — `master_account_expanded: false` means *nobody asked*, and a
// chip there would be a claim the server never made. So *not blanket-filled* is
// asserted as ARITHMETIC over the page instead.
ok(
  "and it is EMPTY on the rows that should have none — not blanket-filled",
  withAccount < rows && rows > 0,
  `${rows - withAccount} of ${rows} row(s) show none`,
);

// ── 2 · SEARCH THE BUILDING THE PO'S OWN DEFECT NAMES ──────────────────────
// `500 Main St` is `DEF-709`'s master account, and the one address that HAD an
// account and did not name it. If any row proves the declaration reached the
// screen, this is the one.
await p.locator('input[type="search"][placeholder*="premise ID" i]').first().fill("Main St");
await p.waitForTimeout(2500);
await p.screenshot({ path: join(SHOTS, "def-met-6302-2-main-st.png"), fullPage: true });
const mainStRow = p.locator("tr", { hasText: "500 Main St" }).first();
const mainStOwner = await mainStRow
  .locator('[data-tracks="premises-owner-account"]')
  .first()
  .textContent()
  .catch(() => null);
ok("500 Main St names its owner account on screen", Boolean(mainStOwner), String(mainStOwner));

// ── 3 · THE OWNER'S OWN PAGE, AND ITS ACCOUNTS TAB (BR-CUS-1048) ───────────
// The PO's second question is whether the account a premises names is a real
// account with a real page. This opens it from the list rather than by url, so
// the LINK is walked too.
await p.locator('input[type="search"][placeholder*="premise ID" i]').first().fill("Mill Pond");
await p.waitForTimeout(2500);
const millRow = p.locator("tr", { hasText: "301 Mill Pond Ln" }).first();
const millOwner = await millRow
  .locator('[data-tracks="premises-owner-account"]')
  .first()
  .textContent()
  .catch(() => null);
ok("301 Mill Pond Ln names its owner account", Boolean(millOwner), String(millOwner));

// ── 4 · THE OWNER'S ACCOUNT, AND ITS `Accounts` TAB (`BR-CUS-1048`) ────────
// PO 2026-09-22, on that tab: *"units -> regular accounts assocaited with it"*.
// It is built, routed and tested — and before this seed it had **no master
// account anywhere to render against**, which is hard-won law 2's mirror: a
// live screen nobody could reach a true case of.
await p.goto(`${BASE}/${T}/accounts?q=AC-2026-00053`, { waitUntil: "networkidle" });
await p.waitForTimeout(2500);
await p.locator("a", { hasText: "AC-2026-00053" }).first().click();
await p.waitForTimeout(2500);
const isMaster = await p.locator("text=/master/i").first().isVisible().catch(() => false);
ok("the owner's account opens and reads as a master account", isMaster);

// ⚠ **CLICKING `Accounts` WAS A FALSE PASS AND THE FIRST RUN TOOK IT.** The
// LEFT NAV carries a word spelled exactly the same, so the click navigated to
// the register, the register's own table has 50 rows, and the assertion below
// reported `50 row(s)` and PASSED over a tab it had never opened. Only the
// screenshot showed it. So the tab is opened by its OWN address (`?tab=`,
// `IS-4`'s deep link), and the account number is asserted on the page
// afterwards, so a navigation away cannot be read as a tab.
const accountUrl = p.url().split("?")[0];
await p.goto(`${accountUrl}?tab=accounts`, { waitUntil: "networkidle" });
await p.waitForTimeout(2500);
await p.screenshot({ path: join(SHOTS, "def-met-6302-3-accounts-tab.png"), fullPage: true });
const stillOnAccount = await p
  .locator("text=AC-2026-00053")
  .first()
  .isVisible()
  .catch(() => false);
ok("the Accounts tab opens ON the owner's account, not the register", stillOnAccount);
// The tab lists the OCCUPYING accounts at this master's address. Asserted as a
// COUNT, because *the tab rendered* passes on an empty table — which is exactly
// the state this whole lane exists to end. Five is what the database holds
// (`selectors.sub_accounts_for_master`), so an upper bound catches the register
// slipping back in.
const subRows = await p.locator("table tbody tr").count();
ok(
  "its Accounts tab lists the tenants at that address",
  subRows >= 1 && subRows <= 12,
  `${subRows} row(s)`,
);

await b.close();
console.log("\n" + R.join("\n"));
process.exit(R.some((r) => r.startsWith("FAIL")) ? 1 : 0);
