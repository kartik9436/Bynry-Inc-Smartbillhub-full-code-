// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave K — PUJ-51 / PUJ-52 / PUJ-53, finding things by address
//          Screens: S17 the accounts list · S33 the payments list · S30 the
//          bills list
// Rules:   CLAUDE.md hard rule 8 (an address lives on `premises`) ·
//          BR-CUS-1010 (the owner's account is at an ADDRESS and names no
//          unit) · BR-CUS-053 · BR-PAY-027 · BR-BIL-1032 · NFR-3
// ───────────────────────────────────────────────────────
//
// TYPE A REAL STREET INTO ALL THREE LISTS AND CHECK WHAT COMES BACK IS WHAT IS
// ACTUALLY AT THAT ADDRESS.
//
// ⚠ THE ADDRESSES ARE NOT THE ONES CR-089 §6 NAMES, AND THAT IS A FINDING
// RATHER THAN A SUBSTITUTION. `412 Cypress Row` is a real property on the demo
// utility (`P-00080`) and it has ONE unit and NO accounts, no bills and no
// payments; `A-10517` does not exist at all; and `BL-2608-000052` DOES exist —
// at **101 Silver Creek Rd**. So the done-whens are honoured at the addresses
// that actually carry the data, and `412 Cypress Row` is walked too, because
// "returns nothing, correctly" is also a claim worth checking.
//
//   1 · 500 Main St        — six accounts, one of them the MASTER with no unit
//   2 · 301 Mill Pond Ln   — six accounts · nine payments · eighteen bills
//   3 · 101 Silver Creek Rd — the bill the CR names, BL-2608-000052
//   4 · 412 Cypress Row    — the CR's own address: a real property with nothing
//                            standing on it
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8212";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr089k";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const candidate = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

// ⚠ THE LIST IS NOT AT THE MODULE'S OWN ADDRESS, AND THE FIRST DRAFT OF THIS
// SCRIPT WALKED TO THE WRONG ONE. `/payments` opens the SUMMARY tab and
// `/bills` is not a route at all — both rendered, both looked like a screen,
// and both reported *zero rows* for an address that has nine payments and
// eighteen bills. That is hard-won law 7's *looking at the wrong thing*: the
// checks were honest and the crawler was standing somewhere else. The S33 list
// is the `record` tab; the S30 list is the billing page's default tab.
const PAYMENTS_LIST = "/payments/record";
const BILLS_LIST = "/billing";

const results = [];
// ⚠ A CHECK'S OUTPUT MUST DISTINGUISH PASS FROM FAIL TO A READER (law 7): every
// check prints what it looked for and, on failure, what it found instead.
function check(name, ok, detail = "") {
  results.push({ name, ok });
  console.log(`${ok ? "  PASS" : "  FAIL"}  ${name}${ok || !detail ? "" : `\n          ${detail}`}`);
}

/** THIS LIST's own prompt, not the shell's.
 *
 * ⚠ THE FIRST DRAFT READ `input[type="search"], input[placeholder]` AND FOUND
 * THE TOPBAR — `AppShell`'s global box, whose placeholder is *"Search"*. It
 * failed honestly rather than passing wrongly, which is the only reason it was
 * caught; a looser assertion (`.includes("Search")`) would have gone green over
 * the wrong control on all three screens. `DataTable` renders the list's box
 * with `className="input"`, so that is what is asked for by name.
 */
async function listPrompt(page) {
  return await page.getAttribute('input.input[type="search"]', "placeholder");
}

/** Type `term` into THIS list's own search box and read the table back. */
async function search(page, path, term, shot) {
  await page.goto(`${BASE}/${TENANT}${path}?q=${encodeURIComponent(term)}`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: join(OUT, `${shot}.png`), fullPage: true });
  return (await page.locator("body").innerText()).replace(/\s+/g, " ");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1500, height: 1500 } });
page.on("pageerror", (e) => console.log("  page error:", e.message));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
console.log(`signed in as ${EMAIL}\n`);

// ── K1 · PUJ-51 — an address finds the ACCOUNTS at it ─────────────────────
console.log("K1 · PUJ-51 · the accounts list, searched by address");
{
  const text = await search(page, "/accounts", "500 Main St", "k1-500-main-st");
  for (const no of ["A-11720", "A-11801", "A-11802", "A-11803", "A-11804"]) {
    check(`500 Main St returns the occupant ${no}`, text.includes(no));
  }
  // THE ONE THAT WAS MISSING. BR-CUS-1010's owner account names no unit, so the
  // unit walk could never reach it: five of six came back before wave K.
  check(
    "500 Main St returns AC-2026-00051 — the MASTER account that owns the building",
    text.includes("AC-2026-00051"),
    "the owner's account is still unreachable by address",
  );
  const prompt = await listPrompt(page);
  check("the accounts prompt offers an address", (prompt ?? "").includes("address"), prompt ?? "");
}

// ── K2 · PUJ-52 — the same address finds the PAYMENTS ─────────────────────
console.log("\nK2 · PUJ-52 · the payments list, searched by address");
{
  const text = await search(page, PAYMENTS_LIST, "301 Mill Pond Ln", "k2-301-mill-pond-ln");
  const shown = (text.match(/PY-\d{6}-\d{4}/g) ?? []);
  check(
    "301 Mill Pond Ln returns the nine payments taken at that building",
    new Set(shown).size === 9,
    `found ${new Set(shown).size}: ${[...new Set(shown)].join(", ") || "(none)"}`,
  );
  const prompt = await listPrompt(page);
  check("the payments prompt offers an address", (prompt ?? "").includes("address"), prompt ?? "");
}

// ── K3 · PUJ-53 — the same address finds the BILLS ────────────────────────
console.log("\nK3 · PUJ-53 · the bills list, searched by address");
{
  const text = await search(page, BILLS_LIST, "301 Mill Pond Ln", "k3-301-mill-pond-ln");
  const shown = new Set(text.match(/BL-\d{4}-\d{6}/g) ?? []);
  check(
    "301 Mill Pond Ln returns eighteen bills",
    shown.size === 18,
    `found ${shown.size}: ${[...shown].slice(0, 20).join(", ") || "(none)"}`,
  );
  const prompt = await listPrompt(page);
  check("the bills prompt offers an address", (prompt ?? "").includes("address"), prompt ?? "");

  // The CR's own done-when, at the address the bill it names actually stands at.
  const silver = await search(page, BILLS_LIST, "101 Silver Creek Rd", "k3-101-silver-creek-rd");
  check("101 Silver Creek Rd returns BL-2608-000052 — the bill CR-089 K3 names", silver.includes("BL-2608-000052"));
  for (const no of ["BL-2607-000001", "BL-2608-000101"]) {
    check(`101 Silver Creek Rd returns ${no} — every other bill at that building`, silver.includes(no));
  }
}

// ── The CR's own address, walked because an absence is a claim too ────────
console.log("\n412 Cypress Row — the address CR-089 §6 names");
{
  const text = await search(page, "/accounts", "412 Cypress Row", "k4-412-cypress-row");
  check(
    "412 Cypress Row returns NO accounts — it is a real property with none",
    !/A-\d{5}|AC-2026-\d{5}/.test(text),
    "something came back for a property that has no accounts",
  );
}

await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
if (failed.length) {
  console.log("FAILED:", failed.map((r) => r.name).join(" · "));
  process.exit(1);
}
