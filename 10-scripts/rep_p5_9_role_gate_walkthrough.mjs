// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 5 · `P5.9` — role gating on a definition,
//          walked in a browser as TWO people.
// Rules:   BR-REP-023 (access-review: System Admin + Executive only — Billing
//          Clerk excluded) · hard-won law 6 (no gate in this repo looks at
//          rendered output) · law 7 clause 3 (a check's output must
//          distinguish pass from fail to a READER)
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY PROOF IS A PAIR OF PEOPLE, NOT A PAIR OF SCREENSHOTS.** A rule of
// the form *"X may, Y may not"* cannot be walked by one signed-in user: a
// screenshot of a missing card proves nothing about whether the card exists,
// and `DEF-REP-6864` shipped for exactly that reason — a private report served
// to every colleague, over a suite in which every test had one user.
//
// ⚠ **THE PREVIOUS PHASE-5 WALK SAID IT COULD NOT DO THIS AND IT COULD.**
// `rep_p5_builder_walkthrough.mjs` announces `CANNOT` for the colleague steps
// *"no COLLEAGUE= address was given, so this deployment has one signed-in
// user"*. The seeded `brazosbend` tenant holds **seven** memberships —
// `sam.reyes@sample.test` (billing_clerk), `avery.cole@sample.test`
// (executive), four field technicians and Dana (system_admin). The addresses
// were there the whole time.
//
//   1 · Dana (System Admin) opens the catalogue · the access-review card IS drawn
//   2 · Sam (Billing Clerk) opens the same catalogue · it is NOT drawn, and the
//       rest of the grid is, with both counts printed
//   3 · Sam types the address · refused, and the History tab still opens
//   4 · Avery (Executive) opens the catalogue · it IS drawn — BR-REP-023's
//       second admitted role, which a one-role check would never distinguish
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const ADMIN = process.env.ADMIN_EMAIL ?? "dana@brazosbendutilities.com";
const CLERK = process.env.CLERK_EMAIL ?? "sam.reyes@sample.test";
const EXEC = process.env.EXEC_EMAIL ?? "avery.cole@sample.test";
const KEY = "access_review";
const OUT = process.env.OUT ?? "/tmp/p5-role-gate";
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
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH or install to /opt/pw-browsers");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const say = (...parts) => console.log(...parts);
let failures = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

async function signIn(email) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  return page;
}

/** The catalogue as a reader sees it: how many cards, and is the one there. */
async function catalogue(page, who, shot) {
  await page.goto(`${BASE}/${TENANT}/reports`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const total = await page.locator("[data-report-key]").count();
  const present = (await page.locator(`[data-report-key='${KEY}']`).count()) > 0;
  say(`   ${who}: ${total} cards drawn, ${KEY} ${present ? "PRESENT" : "ABSENT"}`);
  await page.screenshot({ path: `${OUT}/${shot}`, fullPage: true });
  return { total, present };
}

// ── 1 · the System Admin ───────────────────────────────────────────────────
const admin = await signIn(ADMIN);
const asAdmin = await catalogue(admin, "System Admin", "01-admin-catalogue.png");
check("1 · a System Admin is drawn the access-review card", asAdmin.present);

// ── 2 · the Billing Clerk ──────────────────────────────────────────────────
const clerk = await signIn(CLERK);
const asClerk = await catalogue(clerk, "Billing Clerk", "02-clerk-catalogue.png");
check("2 · a Billing Clerk is NOT drawn it (BR-REP-023)", asClerk.present === false);
// ⚠ THE POSITIVE TWIN. Without this the case above passes over a catalogue
// that returns nothing at all for a clerk, which would be a far worse defect.
check(
  "2 · …and the rest of the grid is untouched",
  asClerk.total === asAdmin.total - 1,
  `admin ${asAdmin.total} · clerk ${asClerk.total}`,
);

// ── 3 · the clerk types the address anyway ─────────────────────────────────
await clerk.goto(`${BASE}/${TENANT}/reports/${KEY}`, { waitUntil: "networkidle" });
await clerk.waitForTimeout(1500);
const body = (await clerk.locator("body").innerText()).toLowerCase();
const rows = await clerk.locator("table tbody tr").count();
check("3 · the address serves no report rows", rows === 0, `${rows} rows`);
say(`   the screen says: ${JSON.stringify((await clerk.locator("body").innerText()).slice(0, 220))}`);
await clerk.screenshot({ path: `${OUT}/03-clerk-refused-at-the-address.png`, fullPage: true });
check(
  "3 · …and the refusal is not a raw key or a stack trace",
  !body.includes("reports.viewer") && !body.includes("traceback"),
);

// ⚠ THE SHADOW CHECK. A gate that swallowed the whole `/reports/<key>` path
// would also break the tab, which is `P5.2`'s whole hazard one door over.
await clerk.goto(`${BASE}/${TENANT}/reports/history`, { waitUntil: "networkidle" });
await clerk.waitForTimeout(800);
check(
  "3 · the History TAB still opens for the same clerk",
  clerk.url().includes("/reports/history"),
  clerk.url(),
);
await clerk.screenshot({ path: `${OUT}/04-history-still-opens.png`, fullPage: true });

// ── 4 · the Executive — the second admitted role ───────────────────────────
const exec = await signIn(EXEC);
const asExec = await catalogue(exec, "Executive", "05-executive-catalogue.png");
check("4 · an Executive IS drawn it — the rule admits two roles, not one", asExec.present);

say("");
say(`${failures === 0 ? "ALL PASS" : `${failures} FAILURE(S)`} · screenshots in ${OUT}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
