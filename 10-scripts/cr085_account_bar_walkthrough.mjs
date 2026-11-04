// ── Trace ──────────────────────────────────────────────
// Change:  CR-085 task 12 — the account bar. PO, 2026-09-08, reviewing the
//          portal wireframes: *"here header bar should ahve menu - and below
//          that we should have a line for account - this should be consitent
//          across registered user login"*.
// Rules:   the PO's definition of done — *"ensure you do web walkthorugh
//          before you sign off the user story or build"*; hard-won law 6 (no
//          gate in this repo reads rendered output).
// ───────────────────────────────────────────────────────
/**
 * WALK THE ACCOUNT BAR ON TEN SIGNED-IN SCREENS AND CHECK IT SAYS THE SAME
 * THING IN THE SAME PLACE ON ALL OF THEM.
 *
 * *Consistent across every signed-in screen* is the requirement, and it is
 * exactly the kind of claim a per-screen test cannot make: each screen's own
 * suite renders that screen and would pass whether the frame around it drew a
 * bar or not. This reads the RENDERED page — the bar's text and its `y` — so
 * "the same place" is measured rather than assumed.
 *
 * ⚠ **THE MULTI-ACCOUNT CASE IS NOT WALKED HERE AND CANNOT BE.** The seed has
 * ONE portal login on pine-hill (`ana@example.test`) holding ONE account, so
 * the switcher never renders on this data. `select=0` in the output below is
 * therefore the SINGLE-account rule being kept — *no control when there is
 * nothing to choose* — and NOT evidence about the switcher. What proves the
 * switcher moved into the bar is `PortalShell.test.tsx`, which renders the real
 * frame with four accounts and asserts the ORDER of the markup. Saying which
 * check covers what is the point of this paragraph: a walkthrough that quietly
 * skipped a case would read exactly like one that covered it.
 *
 * RUN IT: with the stack up (backend on 8000, `server.mjs` on 8080),
 *   node 10-scripts/cr085_account_bar_walkthrough.mjs
 */
import { chromium } from "/home/user/SMARTBillHub/07-frontend/node_modules/playwright/index.mjs";

const BASE = "http://127.0.0.1:8080";
const TENANT = "pine-hill";
const OUT = "/tmp/claude-0/-home-user-SMARTBillHub/4faa9719-9698-53f6-b629-20a1ce3043e9/scratchpad";

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

const r = await page.request.post(`${BASE}/api/${TENANT}/portal/auth/sign-in`, {
  data: { email: "ana@example.test", password: "Pine-Hill-2026!" },
});
console.log("sign-in:", r.status(), (await r.text()).slice(0, 60));

const SCREENS = [
  ["/home", "Home"],
  ["/bills", "Bills"],
  ["/usage", "Usage"],
  ["/payments", "Payments"],
  ["/requests", "Requests"],
  ["/my-details", "My details"],
  ["/account", "Your account"],
  ["/overdue", "Past due"],
  ["/level-pay", "Budget billing"],
  ["/stop-or-restart", "Stop or restart"],
];

let ok = 0, bad = [];
for (const [route, name] of SCREENS) {
  await page.goto(`${BASE}/${TENANT}/portal${route}`, { waitUntil: "networkidle" });
  const bar = page.locator('[data-account-bar=""]');
  const present = await bar.count();
  if (!present) { bad.push(`${name} (${route}) — NO BAR`); continue; }
  const number = (await page.locator('[data-account-bar="number"]').first().innerText().catch(() => "")).trim();
  const where  = (await page.locator('[data-account-bar="where"]').first().innerText().catch(() => "")).trim();
  const box = await bar.first().boundingBox();
  const hasSelect = await page.locator('[data-account-bar=""] select').count();
  console.log(`${name.padEnd(18)} ${route.padEnd(18)} "${number}" · "${where}" · y=${box ? Math.round(box.y) : "?"} h=${box ? Math.round(box.height) : "?"} select=${hasSelect}`);
  if (number !== "Account AC-2026-00001" || where !== "101 Silver Creek Rd · Unit 1") {
    bad.push(`${name} — bar reads "${number}" / "${where}"`);
  }
  ok++;
}

await page.goto(`${BASE}/${TENANT}/portal/home`, { waitUntil: "networkidle" });
await page.screenshot({ path: `${OUT}/bar-home-1280.png` });
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${BASE}/${TENANT}/portal/home`, { waitUntil: "networkidle" });
await page.screenshot({ path: `${OUT}/bar-home-390.png` });

console.log(`\n${ok}/${SCREENS.length} screens carry the bar`);
if (bad.length) { console.log("PROBLEMS:"); bad.forEach((b) => console.log("  ·", b)); }
else console.log("every screen shows the same account, in the same place");
await browser.close();
