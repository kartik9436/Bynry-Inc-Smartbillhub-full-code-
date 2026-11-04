// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-NOT-5637 — the blocked-addresses screen and its Release door.
// Screens: S8 · SET-12B and its four sibling sub-tabs, under
//          /:tenant/settings/notifications.
// Rules:   PO instruction 2026-09-17, verbatim: *"can you also do the Walks as
//          user from screens and ensure it is working as expected - if it break
//          fix it"* · CLAUDE.md hard-won law 6 (no gate in this repo reads
//          rendered output) · law 2's mirror (a live screen behind a dead
//          control) · law 7 habit 3 (the OUTPUT must distinguish pass from fail
//          to a READER).
// ───────────────────────────────────────────────────────
/**
 * WALK IT AS A CLERK, FROM THE FRONT DOOR — never by typing an address.
 *
 *     BASE=http://127.0.0.1:5200 node 10-scripts/def_not_5637_clerk_journey_walk.mjs
 *
 * The other walkthrough in this pair (`def_not_5637_blocked_addresses_walkthrough.mjs`)
 * proves the SCREEN. This one proves the JOURNEY: sign in, find Settings in the
 * sidebar, find Notifications among the tabs, find Blocked addresses among the
 * sub-tabs, do the work, and then walk the four NEIGHBOURS this lane's change
 * shares a file with. Every step is a CLICK on a control a clerk can see; not
 * one `page.goto` after sign-in.
 *
 * ⚠ **WHY THE DISTINCTION IS THE WHOLE POINT.** A screen that renders when you
 * visit its address and cannot be reached from the product is the failure this
 * repository keeps shipping — on 2026-09-05 the customer portal had two working
 * doors out of eight, and every wave had tested its own screen at its own
 * address. `page.goto` is how that passes.
 *
 * ⚠ **WHAT WOULD MAKE THIS WALK PASS WRONGLY:**
 *  * **A click that silently does nothing still leaves the old screen on
 *    display**, and an assertion about content would pass. So every navigation
 *    step asserts the URL CHANGED as well as what appeared.
 *  * **A neighbour that renders an empty frame looks like a neighbour that
 *    renders.** Each sibling tab is checked for a fact only IT draws, not merely
 *    for the frame around it.
 *  * **A stale bundle proves a different product.** The served bundle hash is
 *    printed first.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");

const BASE = process.env.BASE ?? "http://127.0.0.1:5200";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "/tmp/def_not_5637_journey";
const EXE = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
await fs.mkdir(OUT, { recursive: true });

let step = 0;
let failures = 0;
function check(name, passed, detail = "") {
  step += 1;
  console.log(
    `${passed ? "PASS" : "FAIL"}  step ${String(step).padStart(2)}  ${name}${detail === "" ? "" : ` — ${detail}`}`,
  );
  if (!passed) failures += 1;
}

const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 } });
const page = await ctx.newPage();

// Anything the app logs as an error during the whole walk is collected and
// reported at the end: a screen that renders while throwing is still broken.
//
// ⚠ **AND THE CONTAINER'S OWN EGRESS FAILURES ARE SEPARATED OUT, WITH A COUNT.**
// This sandbox's proxy refuses every external CONNECT, so the Archivo webfont
// from `fonts.googleapis.com` fails with `ERR_CERT_AUTHORITY_INVALID` on EVERY
// screen of this product, including the sign-in page before any of this lane's
// code has run. Counting it as a product error would make this walk cry wolf and
// teach the next reader to ignore the line. Counting it as nothing would hide a
// real font failure. So it is counted SEPARATELY and PRINTED — a declared blind
// spot with no number attached is indistinguishable from an empty one (law 7).
const consoleErrors = [];
const egressErrors = [];
const EGRESS = /fonts\.googleapis\.com|fonts\.gstatic\.com/;
function classify(text) {
  (EGRESS.test(text) || /ERR_CERT_AUTHORITY_INVALID/.test(text) ? egressErrors : consoleErrors).push(
    text.slice(0, 160),
  );
}
page.on("console", (m) => {
  if (m.type() === "error") classify(m.text());
});
page.on("pageerror", (e) => classify(`pageerror: ${String(e)}`));
page.on("requestfailed", (r) => {
  const why = r.failure()?.errorText ?? "";
  // A navigation cancels in-flight requests; that is not a failure.
  if (why.includes("ERR_ABORTED")) return;
  classify(`request failed: ${r.url()} — ${why}`);
});

const shell = await (await fetch(`${BASE}/${TENANT}/dashboard`)).text();
const bundle = (/assets\/(index-[^"]+\.js)/.exec(shell) ?? [])[1] ?? "UNKNOWN";
console.log(`STACK: ${BASE} · bundle ${bundle}\n`);

// ══ 1 · SIGN IN — an already-active user, because DEF-IDN-5653 locks out an
//        invited one at /change-password, which is not registered.
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL(/\/dashboard/, { timeout: 20000 });
check("sign in lands on the dashboard", page.url().includes("/dashboard"), page.url());
await page.screenshot({ path: `${OUT}/01-signed-in.png` });

// ══ 2 · THE SIDEBAR — click Settings, do not type its address.
const settingsLink = page.locator('nav a, aside a').filter({ hasText: /^Settings$/ }).first();
await settingsLink.click();
await page.waitForURL(/\/settings/, { timeout: 15000 });
check("the sidebar's Settings link opens Settings", /\/settings/.test(page.url()), page.url());

// ══ 3 · THE TAB STRIP — click Notifications.
await page.waitForSelector('[role="tablist"]', { timeout: 15000 });
const before = page.url();
await page.locator('[role="tab"]', { hasText: "Notifications" }).first().click();
await page.waitForURL(/\/settings\/notifications/, { timeout: 15000 });
check(
  "the Notifications tab is reachable by clicking it",
  page.url() !== before && page.url().includes("/settings/notifications"),
  page.url(),
);
await page.waitForSelector('[data-testid="notifications-subtabs"]', { timeout: 20000 });
await page.screenshot({ path: `${OUT}/02-notifications.png` });

// ══ 4 · THE SUB-STRIP — is the new door VISIBLE beside its four siblings?
const subTabs = await page.evaluate(() =>
  [...document.querySelectorAll('[data-testid="notifications-subtabs"] [role="tab"]')].map((b) => ({
    id: b.getAttribute("data-testid"),
    label: b.textContent.trim(),
  })),
);
console.log(`      the sub-strip offers: ${subTabs.map((t) => t.label).join(" · ")}`);
check("the sub-strip carries five tabs", subTabs.length === 5, `${subTabs.length} tabs`);
check(
  "one of them is Blocked addresses",
  subTabs.some((t) => t.id === "notifications-tab-blocked" && t.label === "Blocked addresses"),
);

// ══ 5 · WALK INTO IT — by clicking, and the address must change.
const beforeBlocked = page.url();
await page.click('[data-testid="notifications-tab-blocked"]');
await page.waitForURL(/\/settings\/notifications\/blocked$/, { timeout: 15000 });
check(
  "clicking it changes the address AND opens SET-12B",
  page.url() !== beforeBlocked && (await page.locator('[data-screen="SET-12B"]').count()) === 1,
  page.url(),
);
await page.waitForSelector("table tbody tr", { timeout: 20000 });
const rows = await page.evaluate(() =>
  [...document.querySelectorAll("table tbody tr")].map((tr) => ({
    address: tr.querySelector("td")?.textContent.trim() ?? "",
    cells: [...tr.querySelectorAll("td")].map((td) => td.textContent.trim()),
  })),
);
console.log(`      the list shows ${rows.length} blocked address(es)`);
for (const r of rows) console.log(`        · ${r.cells.slice(0, 5).join("  |  ")}`);
check("the list has rows a clerk can act on", rows.length > 0, `${rows.length} rows`);
await page.screenshot({ path: `${OUT}/03-blocked-addresses.png`, fullPage: true });

// ══ 6 · RELEASE — the work the clerk came to do.
const target = rows[0].address;
await page.click(`[data-testid="release-${target}"]`);
await page.waitForSelector("text=Release address", { timeout: 10000 });
check(
  "Release opens a dialog naming the address and stating the consequence",
  (await page.locator("text=Sending to this address resumes.").count()) > 0 &&
    (await page.content()).includes(target),
  target,
);
await page.screenshot({ path: `${OUT}/04-release-dialog.png` });
await page.fill("#released_note", "walked as a clerk: typo fixed on the account");
await page.click('button:has-text("Release")');
await page.waitForTimeout(2500);
await page.screenshot({ path: `${OUT}/05-after-release.png`, fullPage: true });

const after = await page.evaluate(async (tenant) => {
  const r = await fetch(`/api/${tenant}/suppressions?f.state=released`, { credentials: "include" });
  return r.ok ? await r.json() : { error: `HTTP ${r.status}` };
}, TENANT);
const kept = (after.results ?? []).find((x) => x.address === target);
check("the released row is KEPT, stamped, with the clerk's own words", kept !== undefined &&
  kept.state === "released" && kept.released_note === "walked as a clerk: typo fixed on the account",
  `released_at=${kept?.released_at}`);

// ══ 7 · THE HISTORY — visible from the screen, by clicking a chip.
await page.click('summary[title^="Filter by:"]');
await page.click('details:has(summary[title^="Filter by:"]) label:has-text("Released")');
await page.waitForTimeout(1500);
const historyHtml = await page.content();
check("the released address is shown under the Released chip, with its note",
  historyHtml.includes(target) && historyHtml.includes("walked as a clerk: typo fixed on the account"));
await page.screenshot({ path: `${OUT}/06-history.png`, fullPage: true });

// ══ 8 · THE NEIGHBOURS — the four sub-tabs this lane's change shares a file
//        with. Each is checked for a fact only IT draws.
const NEIGHBOURS = [
  ["notifications-tab-settings", /\/settings\/notifications$/, "Channel status"],
  ["notifications-tab-messages", /\/notifications\/messages$/, "Messages needing attention"],
  ["notifications-tab-sender", /\/notifications\/sender$/, "Email sender"],
  ["notifications-tab-rights", /\/notifications\/rights$/, "rights-platform-notice"],
];
for (const [testid, url, marker] of NEIGHBOURS) {
  const was = page.url();
  await page.click(`[data-testid="${testid}"]`);
  await page.waitForTimeout(2000);
  const moved = page.url() !== was;
  const atUrl = url.test(page.url());
  const html = await page.content();
  const drew = html.includes(marker);
  check(`neighbour ${testid.replace("notifications-tab-", "")} still opens and draws its own content`,
    moved && atUrl && drew, `${page.url()} · marker "${marker}" ${drew ? "present" : "MISSING"}`);
  await page.screenshot({ path: `${OUT}/07-neighbour-${testid.replace("notifications-tab-", "")}.png` });
}

// ══ 9 · AND BACK — the door still works after walking away from it.
await page.click('[data-testid="notifications-tab-blocked"]');
await page.waitForURL(/\/blocked$/, { timeout: 15000 });
await page.waitForSelector('[data-screen="SET-12B"]', { timeout: 15000 });
check("the door still opens after walking the neighbours", page.url().endsWith("/blocked"));

console.log(
  `\nerrors during the whole walk: ${consoleErrors.length} from the PRODUCT, ` +
    `${egressErrors.length} from this CONTAINER's blocked egress (the Archivo webfont)`,
);
for (const e of consoleErrors.slice(0, 8)) console.log(`   ! ${e}`);
for (const e of egressErrors.slice(0, 2)) console.log(`   (container) ${e}`);
check("the app logged no errors of its own while being walked", consoleErrors.length === 0,
  `${consoleErrors.length} product error(s), ${egressErrors.length} egress`);

console.log(`\nscreenshots → ${OUT}`);
console.log(failures === 0 ? "\nALL STEPS PASSED" : `\n${failures} STEP(S) FAILED`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
