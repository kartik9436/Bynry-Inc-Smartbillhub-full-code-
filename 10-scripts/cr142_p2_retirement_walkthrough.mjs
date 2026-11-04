// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 2 · P2.8 + P2.16 — the three report pages that
//          were NOT retired. Screens: S59 · S60 · RPT-03.
// Rules:   12-governance/22-product-maintenance-process.md step 1, REPRODUCE —
//          *"never fix what you have not seen"* · hard-won law 6 (no gate in
//          this repo looks at rendered output) · P2.8's own requirement, which
//          is the one that matters: **KEEP THE ADDRESSES.**
// ───────────────────────────────────────────────────────
//
// **OPEN ALL THREE OLD ADDRESSES AS A CLERK AND SAY WHAT IS THERE.**
//
// It is written to pass on BOTH sides of a retirement, deliberately: it asserts
// that the address opens a real screen with a heading and a screen id, not that
// it opens a particular component. The DOM hold
// (`07-frontend/src/features/reports/retirementHolds.dom.test.tsx`) is what
// pins the component; this is what a person can watch.
//
//   BASE=http://127.0.0.1:8180 TENANT=brazosbend LABEL=today OUT=<dir> \
//     [W=1280] node 10-scripts/cr142_p2_retirement_walkthrough.mjs
//
// ⚠ **THE URL GRAMMAR IS `f.account_id`, NOT `account`**, and getting it wrong
// is not a 422 — the page renders its empty state and reads exactly like an
// account with no ledger lines. The first run of this script did that.
//
// ⚠ **THE ACCOUNT PARAMETER TAKES THE DATABASE UUID AND REFUSES THE ACCOUNT
// NUMBER ITS OWN HELPER TEXT NAMES** (`DEF-REP-6851`, found by this script).
// `AC-2026-00032` — what the accounts list shows — answers *"Something went
// wrong on our side."* The UUID here is therefore a REPRODUCTION of a defect
// and not an endorsement of B14 rule 31 being broken.
// REPRODUCE / VERIFY the three old report addresses — before & after.
// LABEL=before|after decides the filename prefix only; the steps are identical,
// which is the point: the same script must pass on both sides.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");
const requireFrontend = createRequire(new URL("/home/user/SMARTBillHub/07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8180";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const LABEL = process.env.LABEL ?? "before";
const OUT = process.env.OUT;
const ACCOUNT = process.env.ACCOUNT ?? "01a0d3f1-f4ce-7750-ac16-845414e59f58";
const CUSTOMER = process.env.CUSTOMER ?? "01a0d3f1-faab-7316-80e8-890b95b45847";
const FROM = "2026-07-01", TO = "2026-08-31";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome","chrome-linux/chrome","chrome-linux/headless_shell"]) {
        const c = join(root, dir, sub); if (existsSync(c)) return c;
      }
    }
  }
  throw new Error("no chromium found");
}
const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: Number(process.env.W ?? 1440), height: 1000 } });
let failures = 0;
const check = (l, ok, d = "") => { console.log(`${ok ? "PASS" : "FAIL"}  ${l}${d ? ` — ${d}` : ""}`); if (!ok) failures++; };

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
console.log(`signed in as ${EMAIL}`);

const ADDRESSES = [
  ["account-ledger", `/${TENANT}/reports/account-ledger?f.account_id=${ACCOUNT}&f.from=${FROM}&f.to=${TO}`],
  ["by-premises",    `/${TENANT}/reports/by-premises`],
  ["customer-statement", `/${TENANT}/reports/customer-statement?customer=${CUSTOMER}&from=${FROM}&to=${TO}`],
];

for (const [name, path] of ADDRESSES) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  const url = page.url();
  const h1 = await page.$eval("h1", n => n.textContent.trim()).catch(() => "(no h1)");
  const screenId = await page.$eval("[data-screen-id]", n => n.getAttribute("data-screen-id")).catch(() => "(none)");
  const rows = await page.$$eval("table tbody tr", ns => ns.length).catch(() => 0);
  const notBuilt = await page.$$eval("*", ns => ns.some(n => /not built yet|does not exist/i.test(n.textContent ?? ""))).catch(() => false);
  const body = (await page.$eval("main", n => n.innerText.replace(/\s+/g," ").slice(0,280)).catch(() => ""));
  check(`${name} · the address opens a real screen`, !notBuilt && h1 !== "(no h1)", `h1="${h1}" screen-id=${screenId} rows=${rows} url=${url}`);
  console.log(`   body: ${body}`);
  await page.screenshot({ path: `${OUT}/${LABEL}-${name}.png`, fullPage: true });
}
console.log(`\n${failures === 0 ? "ALL PASS" : `${failures} FAILURES`}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
