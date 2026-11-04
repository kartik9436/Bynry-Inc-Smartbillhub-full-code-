// ── `DEF-MET-6304` — THE OWNER CELL NAMES ITS OWNER, IN A BROWSER ──────────
//
// The Premises list's Master a/c column read **"No name recorded ·
// AC-2026-00051"** on every row that HAD an owner account — beside a real
// number, for a real, named company. The name was recorded the whole time; the
// LIST never asked for it, and then explained the gap with a sentence that says
// the opposite of the truth.
//
// ⛔ **NO GATE IN THIS REPOSITORY READS RENDERED OUTPUT (hard-won law 6), SO
// THIS FILE IS THE ONLY CHECK THAT CAN ANSWER THE COMPLAINT.** The backend
// suite can prove a payload carries a key; only a browser can prove that a
// clerk opening S14 READS a company's name where they read an apology.
//
// ⚠ **IT ASSERTS THE ABSENCE OF THE OLD SENTENCE AS WELL AS THE PRESENCE OF
// THE NAME, AND THE FIRST IS THE ONE THAT CATCHES A HALF-FIX.** A row can
// perfectly well render `Ridge Property LLC` in one cell while another row
// still renders the apology; *some row shows a name* would pass on that. So
// section 2 counts **every** owner-account cell on the page and requires that
// NONE of them carries the phrase.
//
// ⚠ **AND IT ASSERTS THE HONEST ABSENCE SURVIVES.** Rows with no owner account
// must still render blank — `master_account_expanded: false` means *nobody
// asked*, and a name there would be a claim the server never made. Section 3
// is that arithmetic, borrowed from `def_met_6302_owner_accounts_walkthrough`.
//
// ⚠ **IT WRITES NOTHING.** It only reads, so there is nothing to purge and no
// beta to pollute.
//
// ⚠ **IT REFUSES A STALE BUILD.** A walk against an old bundle reports landed
// work as absent — that cost one lane three false ABSENTs.
//
//   MET6304_BASE     default http://127.0.0.1:8743
//   MET6304_TENANT   default brazosbend
//   MET6304_EMAIL    default dana@brazosbendutilities.com
//   MET6304_PASSWORD default S3cure!passw0rd
//   MET6304_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { statSync, readdirSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.env.MET6304_ROOT || process.cwd();
const BASE = process.env.MET6304_BASE || "http://127.0.0.1:8743";
const T = process.env.MET6304_TENANT || "brazosbend";
const EMAIL = process.env.MET6304_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MET6304_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.MET6304_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.MET6304_SHOTS || ".";

/** The sentence this defect is about, in `en`. */
const APOLOGY = "No name recorded";

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
await p.screenshot({ path: join(SHOTS, "def-met-6304-1-premises-list.png"), fullPage: true });

const table = p.locator("table").first();
await table.scrollIntoViewIfNeeded();
await p.waitForTimeout(600);
await table.screenshot({ path: join(SHOTS, "def-met-6304-1b-table.png") });

const rows = await table.locator("tbody tr").count();
const cells = p.locator('[data-tracks="premises-owner-account"]');
const withAccount = await cells.count();
ok("the Master a/c column shows an account on at least one row", withAccount > 0,
   `${withAccount} of ${rows} row(s)`);

// ── 2 · NOT ONE OF THEM APOLOGISES ────────────────────────────────────────
// ⛔ **COUNTED OVER EVERY CELL, NOT SAMPLED.** *Some row shows a name* passes
// on a half-fix where one row is named and the rest still apologise; the only
// assertion that cannot is *no cell carries the phrase*.
const texts = [];
for (let i = 0; i < withAccount; i += 1) {
  texts.push(((await cells.nth(i).textContent()) || "").trim());
}
const apologising = texts.filter((t) => t.includes(APOLOGY));
ok(
  `not one owner cell reads "${APOLOGY}"`,
  apologising.length === 0,
  apologising.length ? apologising.join(" | ") : `${texts.length} cell(s) checked`,
);
// And every one of them carries a real name AND a number — the shape
// `<name> · <account_no>`. A cell that is only a number would be the fix half
// applied, and `toContain("·")` alone cannot see that.
//
// ⚠ **THE FIRST DRAFT OF THIS CHECK WAS INCAPABLE OF FAILING AND I ONLY FOUND
// OUT BY RUNNING IT AGAINST THE BROKEN BUILD (hard-won law 7, habit 2).** It
// read `/\S+.*·\s*AC-/`, and *"No name recorded · AC-2026-00054"* matches that
// perfectly — `No name recorded` IS `\S+.*`. So it printed **PASS · 3 of 3**
// over the exact defect this file exists to catch, on the run that was
// supposed to prove it red. The primary check above caught the build anyway,
// which is the only reason the flaw cost nothing; a check whose NAME claims
// more than its regex can tell is a check that will be trusted later for
// something it never did. **The name segment is now extracted and judged.**
const shaped = texts.map((t) => {
  const [name, ...rest] = t.split("·");
  return { name: name.trim(), number: rest.join("·").trim() };
});
const named = shaped.filter(
  (c) => c.name !== "" && c.name !== APOLOGY && /^AC-/.test(c.number),
);
ok("every owner cell reads <a real name> · <account number>", named.length === texts.length,
   `${named.length} of ${texts.length} — ${JSON.stringify(shaped.map((c) => c.name))}`);

// ── 3 · THE HONEST ABSENCE SURVIVES ───────────────────────────────────────
// A row with no owner account renders `<span />` — *nobody asked* — and a name
// there would be a claim the server never made. Asserted as arithmetic over
// the page, because the empty state carries no tracker to select.
ok(
  "rows with no owner account are still blank — not blanket-filled",
  withAccount < rows && rows > 0,
  `${rows - withAccount} of ${rows} row(s) show none`,
);

// ── 4 · THE BUILDING THE ORIGINAL REPORT NAMES ────────────────────────────
// `500 Main St` / `AC-2026-00051` is the exact row quoted in `DEF-MET-6304`.
await p.locator('input[type="search"][placeholder*="premise ID" i]').first().fill("Main St");
await p.waitForTimeout(2500);
await p.screenshot({ path: join(SHOTS, "def-met-6304-2-main-st.png"), fullPage: true });
const mainStRow = p.locator("tr", { hasText: "500 Main St" }).first();
const mainStOwner = (
  await mainStRow.locator('[data-tracks="premises-owner-account"]').first().textContent()
    .catch(() => null)
) || "";
ok("500 Main St names its owner and not an apology", mainStOwner.includes("AC-2026-00051") &&
   !mainStOwner.includes(APOLOGY), JSON.stringify(mainStOwner.trim()));

// ── 5 · THE LIST AND THE DETAIL NOW AGREE ─────────────────────────────────
// ⚠ **THE DETAIL WAS ALWAYS RIGHT, WHICH IS WHAT MADE THE LIST'S SENTENCE A
// LIE RATHER THAN A GAP.** Reading both in one run is what proves they stopped
// disagreeing — two screens showing one fact two ways is `BR-CUS-171`'s shape.
await mainStRow.locator("a").first().click();
await p.waitForTimeout(2500);
await p.screenshot({ path: join(SHOTS, "def-met-6304-3-premises-detail.png"), fullPage: true });
const detailNames = await p
  .locator(`text=${mainStOwner.split("·")[0].trim()}`)
  .first()
  .isVisible()
  .catch(() => false);
ok("the premises detail shows the same owner name the list now shows", detailNames,
   mainStOwner.split("·")[0].trim());

await b.close();
console.log("\n" + R.join("\n"));
process.exit(R.some((r) => r.startsWith("FAIL")) ? 1 : 0);
