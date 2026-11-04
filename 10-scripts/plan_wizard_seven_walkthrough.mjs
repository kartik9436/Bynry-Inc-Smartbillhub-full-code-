// ── THE PO's SEVEN PLAN-WIZARD ITEMS, WALKED IN A BROWSER ──────────────────
// DEF-RAT-5767 · 5768 · 5769 · 5772 · 5773 · 5779 · 5780, all from the PO's
// beta walk of 2026-09-19. Run it after any change to PlanWizard.tsx.
//
// ⚠ **IT REFUSES A STALE BUILD, AND THAT GUARD IS THE POINT.**
// On 2026-09-19 this walk was first run against a `dist/` built 26 hours
// earlier. Three fixes that ARE on the branch read as ABSENT — no
// multi-select, no step-1 picker, the old APPLIED column still drawn — and
// the walk was one step from reporting that the lanes had not done their
// work. Nothing in the page says how old it is; `tsc`, the suites and every
// gate are green either way, because none of them look at `dist/`.
// So the first thing this script does is compare the bundle's mtime against
// the newest commit touching `07-frontend/src`, and REFUSE rather than
// report. A walk against a stale bundle is worse than no walk: it produces
// confident, specific, wrong findings about other people's work.
//
//   PLAN_WALK_BASE     default http://127.0.0.1:8702
//   PLAN_WALK_TENANT   default brazosbend
//   PLAN_WALK_EMAIL    default dana@brazosbendutilities.com
//   PLAN_WALK_PASSWORD default S3cure!passw0rd
//   PLAN_WALK_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//     (the pinned @playwright/test version does not match the preinstalled
//      browser in this container, so the path is passed explicitly — see
//      CLAUDE.md's environment note; never run `playwright install` here.)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync } from "node:fs";

const BASE = process.env.PLAN_WALK_BASE || "http://127.0.0.1:8702";
const T = process.env.PLAN_WALK_TENANT || "brazosbend";
const EMAIL = process.env.PLAN_WALK_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.PLAN_WALK_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.PLAN_WALK_CHROME
  || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

// ── the staleness refusal ──────────────────────────────────────────────────
const built = statSync("07-frontend/dist/index.html").mtime;
const newestSrc = new Date(
  execSync("git log -1 --format=%cI -- 07-frontend/src").toString().trim(),
);
if (built < newestSrc) {
  console.error(
    `REFUSED: dist/ was built ${built.toISOString()} but 07-frontend/src has a\n` +
    `commit at ${newestSrc.toISOString()}. Run \`npx vite build\` first.\n` +
    `A walk against a stale bundle reports absent features that are present.`,
  );
  process.exit(2);
}

const R = [];
const ok = (n, c, d = "") => R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`);

const b = await chromium.launch({ executablePath: CHROME });
const p = await b.newPage();
await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);

await p.goto(`${BASE}/${T}/plans-rates/plans`, { waitUntil: "networkidle" });
// The row opens through a BUTTON, not an anchor — a link selector finds
// nothing here and reads as "no plan is openable".
await p.locator("table tbody tr button.rating-link").first().click();
await p.waitForTimeout(2500);
const planUrl = p.url();
ok("a plan detail opens", /plans\/[0-9a-f-]{36}/.test(planUrl));

// DEF-RAT-5765 — the correction door lives on the Audit tab, not the header.
await p.locator("button,a").filter({ hasText: /^Audit$/ }).first().click();
await p.waitForTimeout(1500);
const audit = await p.evaluate(() => document.body.innerText);
ok("5765 · the Audit tab offers a correction", /correct|fix an error/i.test(audit));

await p.goto(`${planUrl}/edit`, { waitUntil: "networkidle" });
await p.waitForTimeout(2500);
const s1 = await p.evaluate(() => document.body.innerText);
ok("5769 · change-or-correction is on STEP 1",
   /change the plan/i.test(s1) && /fix an error/i.test(s1));
ok("5768 · customer class takes more than one",
   /add a class/i.test(s1), "an add control, not a single select");

for (let i = 0; i < 3; i++) {
  const c = p.locator("button").filter({ hasText: /^Continue$/ }).first();
  if (await c.count()) { await c.click(); await p.waitForTimeout(800); }
}
const head = await p.evaluate(() =>
  [...document.querySelectorAll("table thead th")].map((h) => h.innerText.trim()));
ok("5779 · the editable APPLIED dropdown is gone", !head.includes("APPLIED"));
ok("5779 · TYPE and WHEN IT APPLIES are drawn",
   head.includes("TYPE") && head.includes("WHEN IT APPLIES"), head.join(" | "));

const rows = await p.evaluate(() =>
  [...document.querySelectorAll("table tbody tr")].map((r) =>
    [...r.cells].map((c) => c.innerText.trim()).join(" · ")));
// A penalty ATTACHED and reading "When triggered" is the whole of DEF-RAT-5767
// and DEF-RAT-5784 in one row: it is reachable, and it no longer rides the
// ordinary bill. Asserting the picker alone cannot show the second half.
ok("5767 · a penalty is attached to the plan",
   rows.some((r) => /Penalty/i.test(r)), rows.find((r) => /Penalty/i.test(r)) || "none");
ok("5784 · an attached penalty says When triggered",
   rows.some((r) => /Penalty/i.test(r) && /When triggered/i.test(r)));

const cb = p.locator('[role="combobox"], input[type="text"]').first();
await cb.click(); await p.waitForTimeout(600);
const offered = await p.evaluate(() =>
  [...document.querySelectorAll('[role="option"],li')].map((n) => n.innerText.trim()).filter(Boolean));
ok("5772 · the add control is a type-ahead", offered.length > 0, `${offered.length} offered`);

const body = await p.evaluate(() => document.body.innerText);
ok("5773 · no empty state says 'Add one below'", !/add one below/i.test(body));

await b.close();
console.log(R.join("\n"));
process.exit(R.some((l) => l.startsWith("FAIL")) ? 1 : 0);
