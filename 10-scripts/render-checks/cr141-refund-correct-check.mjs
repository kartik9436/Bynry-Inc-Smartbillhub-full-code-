// ── Trace ──────────────────────────────────────────────
// Change:   CR-141-BRC07 — a refund's check number may be corrected, the same
//           way a payment's can (OQ-PAY-12614, CLOSED 2026-09-23, option b).
// Also:     DEF-PAY-6398 — the Refunds list never refreshed after an act.
// Screens:  S58 — /:tenant/payments/refunds, the ✎ row action and its form
// ───────────────────────────────────────────────────────
/**
 * THE PO's CASE, CLICKED — against a REAL backend and a REAL PostgreSQL, so the
 * trigger (`payments/0043`) is in the path and not a route interception.
 *
 * *"Dana sends a refund of $91.60 by check #10241 but types #10214."* This
 * signs in as Dana, finds the $91.60 refund reading #10214 on the Refunds list,
 * presses ✎ *Correct check number*, types 10241 and a reason, saves — and then
 * reads the LIST again, because the correction is only real to a clerk when the
 * row she corrected says so (`DEF-PAY-6398` was that row not changing).
 *
 * Checks, each printed PASS/FAIL, exit non-zero on any FAIL:
 *   1. the row action is an ICON with the accessible name *Correct check number*;
 *   2. the form opens on the stored number and offers no memo, tender or amount;
 *   3. the form says NOTHING about how long the old number is kept (B14 rule 33);
 *   4. saving answers with the toast *Check 10214 is now 10241.*;
 *   5. the LIST shows 10241 on that row without a reload.
 *
 * ── RUN (from the REPO ROOT) ──────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone <label> --export)"   # then migrate payments
 *   (seed the refund: $91.60, method check, issued as #10214 — see CR-141's
 *    review-ledger row for the shell snippet the lane used)
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8140 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4140 API_PROXY_TARGET=http://127.0.0.1:8140 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4140 SBH_FE=07-frontend \
 *     node 10-scripts/render-checks/cr141-refund-correct-check.mjs
 */
import { existsSync, readdirSync } from "node:fs";
import path, { join } from "node:path";
import { createRequire } from "node:module";

const FE = path.resolve(process.env.SBH_FE ?? "07-frontend");
const requireFrontend = createRequire(path.join(FE, "package.json"));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  if (process.env.SBH_CHROMIUM) return process.env.SBH_CHROMIUM;
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  return undefined;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4140";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const TYPED = "10214";
const WRITTEN = "10241";
const SHOTS = process.env.SBH_SHOTS ?? "/tmp";

const checks = [];
function check(name, pass, detail = "") {
  checks.push({ name, pass });
  console.log(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on("console", (m) => {
  if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 160)}`);
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
console.log("   signed in");

await page.goto(`${BASE}/${TENANT}/payments/refunds`, { waitUntil: "networkidle" });
const row = page.locator("tr", { hasText: TYPED }).first();
await row.waitFor({ timeout: 30000 });
await page.screenshot({ path: `${SHOTS}/cr141-1-list-before.png` });

const action = row.getByRole("button", { name: "Correct check number" });
check("1 · the row action is an icon named *Correct check number*", (await action.count()) === 1);
check(
  "1 · …and it is enabled on the issued refund",
  (await action.count()) === 1 && !(await action.isDisabled()),
);
await action.click();

const dialog = page.getByRole("dialog");
await dialog.waitFor({ timeout: 10000 });
await page.screenshot({ path: `${SHOTS}/cr141-2-form.png` });
const number = dialog.locator("#reference");
check("2 · the form opens on the stored number", (await number.inputValue()) === TYPED);
check(
  "2 · no memo, tender, amount or method is offered",
  (await dialog.locator("#memo, #tender_id, #amount, #method").count()) === 0,
);
const text = ((await dialog.textContent()) ?? "").toLowerCase();
const leaked = ["audit", "retention", "pruned", "permanent", "forever"].filter((w) => text.includes(w));
check("3 · nothing about how long the old number is kept", leaked.length === 0, leaked.join(", "));

await number.fill(WRITTEN);
await dialog.locator("#note").fill("the check stub reads 10241; I keyed 10214");
await dialog.getByRole("button", { name: "Save correction" }).click();

const toast = page.getByText(`Check ${TYPED} is now ${WRITTEN}.`);
let toasted = true;
try {
  await toast.waitFor({ timeout: 15000 });
} catch {
  toasted = false;
}
check(`4 · the toast says *Check ${TYPED} is now ${WRITTEN}.*`, toasted);

// ⚠ SCOPED BY THE AMOUNT AS WELL AS THE NUMBER. The demo utility already holds
// PE-9's refund under #10241 ($171.16), so a row matched on the number alone
// is found whether or not the correction ever reached the list — a check that
// cannot fail (hard-won law 7). The $91.60 row reading #10241 can only exist
// if the list refreshed after the correction.
const corrected = page.locator("tr", { hasText: WRITTEN }).filter({ hasText: "91.60" });
let refreshed = true;
try {
  await corrected.first().waitFor({ timeout: 15000 });
} catch {
  refreshed = false;
}
await page.screenshot({ path: `${SHOTS}/cr141-3-list-after.png` });
check(`5 · the LIST shows ${WRITTEN} without a reload (DEF-PAY-6398)`, refreshed);
check(
  `5 · …and no row still reads ${TYPED}`,
  (await page.locator("tr", { hasText: TYPED }).count()) === 0,
);

await browser.close();
const failed = checks.filter((c) => !c.pass).length;
console.log(`\n${checks.length - failed}/${checks.length} checks passed`);
process.exit(failed === 0 ? 0 : 1);
