// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-4516 — a seeded gas customer is charged nothing for the gas
//          they use. PO 2026-09-07: "please fix this gap - One real gap, and it
//          is money. Gas bills $0.00 usage".
// Ruling:  the standing definition of done — "everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build".
// Rules:   billing workbook [W] §1 line 22 — "Gas add-on · Gas flat $1.15/ccf
//          · $6" · CLAUDE.md hard rule 2 (4 decimals stored, 2 displayed) ·
//          hard-won law 6 (no gate reads rendered output).
// ───────────────────────────────────────────────────────
//
// OPEN A SEEDED GAS BILL IN A BROWSER AND READ THE USAGE LINE.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  IT NAMES THE FIGURES IT EXPECTS, RATHER THAN CHECKING THE LINE EXISTS.  ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// A walkthrough asserting only "there is a gas usage row" would have been GREEN
// on the defect: the row was there all along, correctly shaped, priced at
// $0.0000 — which is exactly why 150 committed readings and every gate could
// not see it. So each check below names a string a person could read aloud:
// the quantity `40`, the unit `ccf`, the price `$1.15`, the usage `$46.00` and
// the pre-tax total `$52.00`.
//
// Run:  node 10-scripts/def_rat4511_gas_usage_walkthrough.mjs
//   WEB=http://127.0.0.1:8180  TENANT=<the seeded gas tenant's subdomain>
//   EMAIL=owner@<subdomain>.test  PASSWORD='S3cure!passw0rd'

import { existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(
  new URL("../07-frontend/package.json", import.meta.url),
);
const { chromium } = requireFrontend("playwright-core");

// The pinned revision is not what is installed in this sandbox and
// `playwright install` is forbidden here; `12-smoke-walkthrough.mjs` solved
// this first and the substitution is PRINTED rather than silent.
const resolveChromium = () => {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) {
          console.log(`chromium: pinned revision missing; using ${candidate}`);
          return candidate;
        }
      }
    }
  }
  throw new Error(`no chromium found; playwright wants ${wanted}`);
};

const WEB = process.env.WEB || "http://127.0.0.1:8180";
const TENANT = process.env.TENANT || "brazosbend";
const EMAIL = process.env.EMAIL || `owner@${TENANT}.test`;
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
const OUT = process.env.OUT || "/tmp/def-rat4516";

const findings = [];
const note = (ok, what, detail) => {
  findings.push({ ok, what, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${what}${detail ? " — " + detail : ""}`);
};

const run = async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.on("console", (m) => {
    if (m.type() === "error") console.log("   [console error]", m.text().slice(0, 160));
  });

  // ── sign in through the real door ────────────────────────────────────────
  await page.goto(`${WEB}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 });
  note(!page.url().includes("/signin"), "signed in", page.url());

  // ── the bills list, then the first bill ──────────────────────────────────
  await page.goto(`${WEB}/${TENANT}/billing/bills`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${OUT}-bills.png`, fullPage: true });

  // ⚠ MOUNT THE REAL ADDRESS AND FOLLOW THE REAL LINK. Building the bill URL
  // from an id read out of the database would prove the API and not the app.
  const firstBill = page.locator('a[href*="/billing/bills/"]').first();
  const linked = await firstBill.count();
  note(linked > 0, "the bills list offers a bill to open", `${linked} link(s)`);
  if (!linked) {
    console.log("PAGE TEXT >>>");
    console.log((await page.locator("body").innerText()).slice(0, 2000));
    await browser.close();
    return finish();
  }
  await firstBill.click();
  await page.waitForURL("**/billing/bills/**", { timeout: 30000 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${OUT}-bill.png`, fullPage: true });

  // ⚠ **THE MONEY IS ON THE *CHARGES* TAB AND THE BILL OPENS ON *DOCUMENT*.**
  // The first version of this walkthrough read the landing tab, found no gas
  // line at all, and its NEGATIVE check — "no gas usage line reads $0.00" —
  // PASSED, because a line that is not on the page cannot read $0.00. That is
  // law 7's *structurally incapable of failing* shape, produced by accident, and
  // it is why the negative below is now gated on the positive.
  const charges = page.getByRole("tab", { name: /charges/i }).or(
    page.getByRole("link", { name: /^charges$/i }),
  ).or(page.getByText(/^Charges$/));
  if (await charges.count()) {
    await charges.first().click();
    await page.waitForTimeout(1500);
  }
  await page.screenshot({ path: `${OUT}-charges.png`, fullPage: true });

  const text = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  console.log("\nBILL TEXT >>>");
  console.log(text.slice(0, 3000));
  console.log("<<<\n");

  // ── the figures, each named ──────────────────────────────────────────────
  note(/gas usage/i.test(text), "the bill carries a gas usage line", null);
  note(text.includes("ccf"), "the usage line states its unit", "ccf — CLAUDE.md hard rule 3");
  note(text.includes("$1.15"), "the unit price is the workbook's signed $1.15", "[W] §1 line 22");
  note(text.includes("$46.00"), "40 ccf x $1.15 bills $46.00", "was $0.00 before DEF-RAT-4516");
  note(text.includes("$6.00"), "the signed $6.00 gas base is still there", null);
  note(text.includes("$52.00"), "the bill totals $52.00 before tax", "the acceptance figure");
  // ⚠ GATED ON THE POSITIVE, so it cannot pass by the line being absent.
  const hasLine = /gas usage/i.test(text);
  note(
    hasLine && !/gas usage[^$]*\$0\.00/i.test(text),
    "no gas usage line reads $0.00",
    hasLine ? null : "VACUOUS — there is no gas usage line on this page at all",
  );

  await browser.close();
  return finish();
};

const finish = () => {
  const bad = findings.filter((f) => !f.ok);
  console.log(`\n${findings.length - bad.length}/${findings.length} checks passed`);
  if (bad.length) {
    console.log("FAILING:");
    for (const f of bad) console.log(`  - ${f.what}${f.detail ? " — " + f.detail : ""}`);
  }
  process.exitCode = bad.length ? 1 : 0;
};

run().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
