// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-NOT-5637 — `GET /suppressions` and `POST /suppressions/{id}/
//          release` were served with NO screen behind them, so the Release the
//          Product Owner asked for by name could only be performed by an
//          engineer.
// Screens: S8 · SET-12B, at `/:tenant/settings/notifications/blocked`.
// Rules:   CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
//          output — a screen is proved by clicking it) · law 7 habit 3 (the
//          OUTPUT must distinguish pass from fail to a READER) · B14 rule 31
//          (no database id is the visible value of a field) · hard rule 7
//          (every money action writes `audit_log`).
// ───────────────────────────────────────────────────────
/**
 * Walk the blocked-addresses screen in a real browser, against real rows in a
 * real PostgreSQL, and RELEASE one — then read the row back and prove it is
 * still there, stamped.
 *
 *     BASE=http://127.0.0.1:5200 node 10-scripts/def_not_5637_blocked_addresses_walkthrough.mjs
 *
 * ⚠ **WHAT WOULD MAKE THIS WALK PASS WRONGLY, AND WHAT IS DONE ABOUT IT:**
 *
 *  * **A walk against a stale bundle proves a different product.** The served
 *    JS bundle hash is printed first, and the walk refuses if the screen does
 *    not carry `data-screen="SET-12B"` — which only this lane's code emits.
 *  * **`release` could DELETE the row and every visible thing would still look
 *    right**: the list would shorten, a toast would fire, and the screen would
 *    read exactly as it does now. So the row is read back FROM THE API by its
 *    address, and the walk fails if it is gone. That is the one assertion a
 *    screenshot cannot make.
 *  * **An id could leak through a `title`, an `aria-label` or a data attribute
 *    rather than through a cell.** The whole document's HTML is searched for
 *    every id the API served, not just the table's text.
 *  * **A zero is not a pass.** Every count this walk prints is printed beside
 *    what it was counted over, and a run that finds no rows at all says so and
 *    exits non-zero — a screen with nothing on it proves nothing about a list.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");

const BASE = process.env.BASE ?? "http://127.0.0.1:5200";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "/tmp/def_not_5637";
const EXE = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const BLOCKED = `${BASE}/${TENANT}/settings/notifications/blocked`;
await fs.mkdir(OUT, { recursive: true });

let failures = 0;
function check(name, passed, detail = "") {
  console.log(`${passed ? "PASS" : "FAIL"}  ${name}${detail === "" ? "" : ` — ${detail}`}`);
  if (!passed) failures += 1;
}

const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 } });
const page = await ctx.newPage();

const shell = await (await fetch(`${BASE}/${TENANT}/dashboard`)).text();
const bundle = (/assets\/(index-[^"]+\.js)/.exec(shell) ?? [])[1] ?? "UNKNOWN";
console.log(`STACK: ${BASE} · bundle ${bundle}`);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL(/\/dashboard/, { timeout: 20000 });

// ── what the SERVER holds, before anything is clicked ──────────────────────
const served = await page.evaluate(async (tenant) => {
  const r = await fetch(`/api/${tenant}/suppressions?f.state=all`, { credentials: "include" });
  if (!r.ok) return { error: `HTTP ${r.status}` };
  return await r.json();
}, TENANT);
if (served.error) {
  console.log(`API: ${served.error}`);
  process.exit(1);
}
console.log(
  `STACK: the API holds ${served.count} suppression(s) across all states · ` +
    `reasons offered: ${served.vocabulary.reasons.join(", ")}`,
);
check("there is something to walk over", served.count > 0, `${served.count} rows`);

// ══ 1 · THE DOOR ═══════════════════════════════════════════════════════════
await page.goto(`${BASE}/${TENANT}/settings/notifications`, { waitUntil: "networkidle" });
await page.waitForSelector('[data-testid="notifications-subtabs"]', { timeout: 20000 });
const doorLabel = await page
  .locator('[data-testid="notifications-tab-blocked"]')
  .textContent()
  .catch(() => null);
check("the sub-tab strip offers the door", doorLabel !== null, `label: ${doorLabel}`);
await page.screenshot({ path: `${OUT}/01-the-door.png`, fullPage: false });

await page.click('[data-testid="notifications-tab-blocked"]');
await page.waitForURL(/\/settings\/notifications\/blocked$/, { timeout: 10000 });
check("clicking it changes the ADDRESS", page.url().endsWith("/settings/notifications/blocked"), page.url());

// ══ 2 · THE LIST, AT ITS OWN ADDRESS (a pasted link, not a click) ══════════
await page.goto(BLOCKED, { waitUntil: "networkidle" });
await page.waitForSelector('[data-screen="SET-12B"]', { timeout: 20000 });
await page.waitForSelector("table tbody tr", { timeout: 20000 });

const onScreen = await page.evaluate(() =>
  [...document.querySelectorAll("table tbody tr")].map((tr) =>
    [...tr.querySelectorAll("td")].map((td) => td.textContent.trim()),
  ),
);
console.log(`SCREEN: ${onScreen.length} row(s) rendered on the landing view (active only)`);
for (const row of onScreen) console.log(`   · ${row.join("  |  ")}`);
check("the list renders rows", onScreen.length > 0, `${onScreen.length} rows`);
check(
  "every row states a REASON in words, not a code",
  onScreen.every((r) => r.some((c) => /Bad address|Marked as spam|Unsubscribed|Blocked by hand/.test(c))),
);
check(
  "no row shows a raw reason code",
  !onScreen.some((r) => r.some((c) => /hard_bounce|unsubscribed|complaint/.test(c))),
);
await page.screenshot({ path: `${OUT}/02-the-list.png`, fullPage: true });

// ── B14 rule 31, over the WHOLE document rather than over the cells ────────
const html = await page.content();
const leaked = served.results.filter((row) => html.includes(row.id));
check("no suppression id appears anywhere in the document (B14 rule 31)", leaked.length === 0,
  leaked.length === 0 ? `checked ${served.results.length} ids` : leaked.map((r) => r.id).join(", "));

// ══ 3 · RELEASE — the control the Product Owner asked for by name ══════════
const target = served.results.find((row) => row.state === "active");
if (target === undefined) {
  console.log("FAIL  there is no ACTIVE row to release");
  process.exit(1);
}
console.log(`WALK: releasing ${target.address} (${target.reason})`);

await page.click(`[data-testid="release-${target.address}"]`);
await page.waitForSelector("text=Release address", { timeout: 10000 });
const consequence = await page.locator("text=Sending to this address resumes.").count();
check("the consequence is stated BEFORE the act (B14 rule 33)", consequence > 0);
const dialogHtml = await page.content();
check("the dialog names the ADDRESS and not the id",
  dialogHtml.includes(target.address) && !dialogHtml.includes(target.id));
await page.screenshot({ path: `${OUT}/03-release-dialog.png`, fullPage: false });

await page.fill("#released_note", "typo, corrected on the account");
await page.click('button:has-text("Release")');
await page.waitForSelector(`[data-testid="release-${target.address}"]`, {
  state: "detached",
  timeout: 15000,
}).catch(() => undefined);
await page.waitForTimeout(1500);
await page.screenshot({ path: `${OUT}/04-after-release.png`, fullPage: true });

// ══ 4 · THE ROW SURVIVED — the assertion no screenshot can make ════════════
const after = await page.evaluate(async (tenant) => {
  const r = await fetch(`/api/${tenant}/suppressions?f.state=released`, { credentials: "include" });
  return r.ok ? await r.json() : { error: `HTTP ${r.status}` };
}, TENANT);
const kept = (after.results ?? []).find((row) => row.id === target.id);
check("the released row is KEPT, not deleted", kept !== undefined);
check("…and it is stamped released", kept?.state === "released" && kept?.released_at !== null,
  `released_at=${kept?.released_at}`);
check("…and it carries the clerk's own words", kept?.released_note === "typo, corrected on the account",
  `note=${JSON.stringify(kept?.released_note)}`);

// ══ 5 · THE HISTORY IS SHOWN, NOT HIDDEN ═══════════════════════════════════
await page.goto(BLOCKED, { waitUntil: "networkidle" });
await page.waitForSelector('[data-screen="SET-12B"]', { timeout: 20000 });
await page.click('summary[title^="Filter by:"]');
await page.click('details:has(summary[title^="Filter by:"]) label:has-text("Released")');
await page.waitForTimeout(1200);
const historyHtml = await page.content();
check("the released address is visible under the Released chip", historyHtml.includes(target.address));
check("…with the clerk's note beside it", historyHtml.includes("typo, corrected on the account"));
await page.screenshot({ path: `${OUT}/05-the-history.png`, fullPage: true });

console.log(`\nscreenshots → ${OUT}`);
console.log(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
