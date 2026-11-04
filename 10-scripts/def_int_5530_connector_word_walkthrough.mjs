// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-INT-5530` — the PO, twice, from the deployed product. "on tab
//          it still says integration, on detail view page it says connector -
//          please fix tab", then "here it again says integration - so please
//          check".
// Rules:   CLAUDE.md hard-won law 6 (no gate reads rendered output) · law 7
//          ("what would make this pass wrongly?" and a check's output must
//          distinguish pass from fail TO A READER) ·
//          `22-product-maintenance-process.md` step 4 (prove it against the
//          REPRODUCTION) and step 5 (regression-walk the neighbours).
// ───────────────────────────────────────────────────────
/**
 * Walk all SIX clerk-facing strings the rename moved, and say what each one
 * renders.
 *
 *     BASE=http://127.0.0.1:8433 OUT=/tmp/after node walk6.mjs
 *
 * ⚠ **IT ASSERTS WHAT THE STACK SERVES BEFORE IT BELIEVES ANY SCREENSHOT.**
 * `EXPECT_BUNDLE` is the hash the build just wrote; the walk REFUSES if the
 * origin is serving anything else. On 2026-09-16 a walk was served by a sibling
 * lane's older stack and its screens were reported to the PO as a product
 * fault — a walk against the wrong bundle is not a weaker proof, it is a proof
 * of a different product.
 *
 * ⚠ **`integrations.runs.backTo` IS ONE KEY ON TWO SCREENS** — the run history
 * AND the connection detail page. The connection page is the one the PO is
 * looking at, so both are walked; walking only the screen the key is named
 * after would leave the reported surface unchecked.
 *
 * ⚠ **THE DISCONNECT TOAST'S SERVER ANSWER IS STUBBED, AND THAT IS SAID OUT
 * LOUD.** Disconnecting for real writes to a database four other lanes share.
 * The component, the catalogue lookup and the render path are all the product's
 * own; only the vendor call's 200 is fulfilled by the harness. What this proves
 * is the STRING, not the mutation — and a reader is owed that distinction
 * rather than a tick.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");

const BASE = process.env.BASE ?? "http://127.0.0.1:8433";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "/tmp/after";
const EXPECT_BUNDLE = process.env.EXPECT_BUNDLE ?? "";
const MAPPING_KEY = process.env.MAPPING_KEY ?? "email_smtp";
await fs.mkdir(OUT, { recursive: true });

const bundle = ((await (await fetch(`${BASE}/`)).text()).match(/assets\/index-[A-Za-z0-9_-]+\.js/) || ["?"])[0];
console.log(`SERVED BUNDLE: ${bundle}   (${BASE})`);
if (EXPECT_BUNDLE && !bundle.includes(EXPECT_BUNDLE)) {
  console.error(`REFUSED: expected ${EXPECT_BUNDLE}, origin serves ${bundle}. Someone else's stack.`);
  process.exit(2);
}

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();

const rows = [];
const say = (n, surface, key, got, verdict) => {
  rows.push({ n, surface, key, got, verdict });
  console.log(`  ${verdict.padEnd(12)} ${n}. ${surface}\n       ${key}\n       -> ${JSON.stringify(got)}`);
};

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForLoadState("networkidle");
await page.waitForTimeout(3000);

const back = () => page.$$eval("a", els => els.map(e => e.textContent.trim()).filter(t => t.startsWith("←")));
/**
 * ⚠ THREE OUTCOMES, NOT TWO, AND THE THIRD IS THE WHOLE POINT. The first draft
 * of this walk returned `[]` for three of the six surfaces and scored every one
 * of them CONNECTORS, because an empty array contains no "integration" either.
 * That is law 7's *what would make this check pass wrongly* answered by the
 * check itself: **a string nobody rendered is a string nobody has checked**, and
 * reporting it as a pass is worse than reporting nothing.
 */
const verdict = (s) => {
  const flat = (Array.isArray(s) ? s : [s]).filter((x) => typeof x === "string" && x.trim());
  if (flat.length === 0) return "NOT REACHED";
  return /integration|integrazion|integraci|intégration/i.test(flat.join(" ")) ? "STILL WRONG" : "CONNECTORS";
};

// 1 + 2 · the tab strip and the heading under it — the PO's own screenshot ---
await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
await page.waitForSelector("h1", { timeout: 20000 });
await page.waitForTimeout(2000);
await page.screenshot({ path: `${OUT}/01-tab-and-heading.png`, clip: { x: 230, y: 90, width: 1180, height: 330 } });
await page.screenshot({ path: `${OUT}/01-full.png` });
const tab = await page.$$eval("a,[role=tab],button", els => els.map(e => (e.textContent || "").trim()).filter(t => /^(integrations|connectors|konnektoren|conectores)$/i.test(t)));
say(1, "Settings tab strip", "settings.tab.integrations", tab, verdict(tab));
const h2 = await page.$$eval("h2", els => els.map(e => e.textContent.trim()).slice(0, 2));
say(2, "the grid heading, ~90px under the tab", "integrations.title", h2, verdict(h2[0] ?? ""));

// 3 · mappings back link ----------------------------------------------------
await page.goto(`${BASE}/${TENANT}/settings/integrations/${MAPPING_KEY}/mappings`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
await page.screenshot({ path: `${OUT}/03-mappings.png`, clip: { x: 230, y: 90, width: 1180, height: 230 } });
const m = await back();
say(3, `Value mappings (${MAPPING_KEY}) — back link`, "integrations.mappings.backTo", m, verdict(m));

// ⚠ THERE IS NO `/settings/integrations/runs` SCREEN, and the first draft of
// this walk invented one and scored its empty result as a pass.
// `integrations.runs.backTo` is rendered in exactly ONE place —
// `ConnectionDetailPage.tsx:1046`, the CONNECTION screen (S142) — so the key is
// named after a screen it does not serve. That is the surface the PO reported,
// and it is walked at 4b below.

// 4b · THE SAME KEY on the CONNECTION screen — the one the PO reported ------
await page.goto(`${BASE}/${TENANT}/settings/integrations/email_smtp`, { waitUntil: "networkidle" });
await page.waitForTimeout(3000);
await page.screenshot({ path: `${OUT}/05-connection-detail.png`, clip: { x: 230, y: 90, width: 1180, height: 300 } });
await page.screenshot({ path: `${OUT}/05-connection-full.png` });
const c = await back();
say("4b", "Connection detail (email_smtp) — THE ONE THE PO REPORTED", "integrations.runs.backTo (same key, second screen)", c, verdict(c));

// 6 · the disconnect toast — server answer stubbed, render path real --------
// ⚠ TWO THINGS DEFEATED THE FIRST DRAFT, and both are the "not reached" shape.
// (a) `disconnectIntegration` is `DELETE /integrations/{key}` — there is no
//     `/disconnect` path, so the stub never matched and the mutation never ran.
// (b) The confirm dialog makes you TYPE the connector's name; Disconnect stays
//     DISABLED until you do, so a walk that only clicked would report "not
//     reached" for ever and a reader would never learn why.
let toastText = [];
try {
  await page.route("**/api/**", (route, req) =>
    req.method() === "DELETE"
      ? route.fulfill({ status: 200, contentType: "application/json",
          body: JSON.stringify({ key: "email_smtp", name: "Custom SMTP", category: "email",
                                 state: "not_connected", operations: [], connections: [] }) })
      : route.continue());
  await page.goto(`${BASE}/${TENANT}/settings/integrations/email_smtp`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  await page.locator('button:has-text("Disconnect")').first().click();
  await page.waitForTimeout(1200);
  await page.locator("input[type=text]").last().fill("Custom SMTP");
  await page.waitForTimeout(400);
  await page.locator("button").filter({ hasText: /^Disconnect$/ }).last().click();
  await page.waitForTimeout(1500);
  toastText = await page.$$eval("[role=status]", els => els.map(e => (e.textContent || "").trim()).filter(Boolean));
  await page.screenshot({ path: `${OUT}/06-disconnect-toast.png` });
  await page.unroute("**/api/**");
} catch (e) { toastText = [`could not reach: ${String(e).slice(0, 140)}`]; }
say(6, "Disconnect toast (server 200 STUBBED; component+catalogue real)", "integrations.disconnect.toast", toastText, verdict(toastText));

// 5 · the failure state -----------------------------------------------------
await ctx.route("**/api/*/integrations**", (route) => route.abort());
await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(4000);
await page.screenshot({ path: `${OUT}/07-failed.png` });
const f = await page.evaluate(() => (document.body.innerText || "").split("\n").map(s => s.trim())
  .filter(s => /could not load|konnten nicht|no se pudieron|impossible de charger/i.test(s)));
say(5, "Grid failure state (API aborted at the browser)", "integrations.failedTitle", f, verdict(f));
await ctx.unroute("**/api/*/integrations**");

await fs.writeFile(`${OUT}/results.json`, JSON.stringify({ bundle, base: BASE, rows }, null, 2));
const bad = rows.filter(x => x.verdict !== "CONNECTORS");
console.log(`\n${rows.length} surfaces walked · ${bad.length} still reading "integration"`);
for (const b of bad) console.log(`   XX ${b.n} ${b.surface}`);

// ═══════════════════════════════════════════════════════════════════════════
// ACT TWO — THE REGRESSION WALK (`22-product-maintenance-process.md` step 5)
//
// A fix that breaks an adjacent screen is worse than the defect it fixed,
// because the defect was known and the regression is not. Staff app, so BOTH
// agreed staff widths — 1280 (laptop minimum, everything must work) and 1440
// (the design target). Nothing narrower: that is the ruling, not an omission.
//
// ⚠ TWO OF ITS CHECKS FIRED WRONGLY THE FIRST TIME, AND BOTH ARE KEPT HERE AS
// COMMENTS RATHER THAN QUIETLY FIXED, because each is law 7's shape:
//   * `/not built yet/` over the page text flagged the machine-keys screen as
//     BROKEN. Those words were ACCESS-LOG ROWS — "Ledger, not built yet" is a
//     partner asking for something we do not serve yet, which is data the
//     screen is supposed to show. The check was reading content as chrome.
//   * `input[placeholder*="Search"]` typed into the APP SHELL's global search
//     box, which sorts first in the DOM, so the grid never filtered and the
//     count stayed 28. Addressed by its own id, the grid narrows 28 -> 1.
// ═══════════════════════════════════════════════════════════════════════════
const SCREENS = [
  ["grid",              "/brazosbend/settings/integrations",                        "Connectors"],
  ["setup-page",        "/brazosbend/settings/connectors/gis_esri/configure",       null],
  ["connection-detail", "/brazosbend/settings/integrations/email_smtp",             null],
  ["mappings",          "/brazosbend/settings/integrations/email_smtp/mappings",    null],
  ["machine-keys",      "/brazosbend/settings/integrations/erp_aclarian",           null],
  ["settings-company",  "/brazosbend/settings/company",                             null],
  ["settings-security", "/brazosbend/settings/security",                            null],
];

const regRows = [];
for (const width of [1280, 1440]) {
  const ctx = await browser.newContext({ viewport: { width, height: 1000 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", e => errors.push(String(e).slice(0, 160)));
  await page.goto(`${BASE}/brazosbend/signin`, { waitUntil: "networkidle" });
  await page.waitForSelector("#signin-email", { timeout: 60000 });
  await page.fill("#signin-email", "dana@brazosbendutilities.com");
  await page.fill("#signin-password", "S3cure!passw0rd");
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle"); await page.waitForTimeout(3000);

  for (const [name, path] of SCREENS) {
    errors.length = 0;
    await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2200);
    // ⚠ OPEN EVERY <details> BEFORE READING THE PAGE. `innerText` omits
    // collapsed content, so a string inside a closed disclosure reads as
    // ABSENT — and B14 rule 32 puts a stated absence in a `<details>` CLOSED by
    // default, which means the repo's own convention hides exactly the copy a
    // sweep is looking for. This walk reported Settings > Company CLEAN on one
    // pass and dirty on another for this reason alone; opened, it is 3 of 3.
    await page.evaluate(() => document.querySelectorAll("details").forEach((d) => { d.open = true; }));
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${OUT}/${width}-${name}.png` });
    const body = await page.evaluate(() => document.body.innerText || "");
    const sideways = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    const stillOld = /\bintegrations?\b/i.test(body);
    const blank = body.trim().length < 60;
    // ⚠ NOT `/not built yet/` OVER THE WHOLE PAGE. The machine-keys screen's
    // ACCESS LOG legitimately prints "Ledger, not built yet" — a partner asked
    // for something we do not serve — so that pattern reported a healthy screen
    // as BROKEN, intermittently, depending on what was in the log that hour.
    // A check that reads a screen's DATA as its chrome is law 7's *looking at
    // the wrong thing*. Anchored to the not-built PLACEHOLDER instead.
    const broke = /^\s*(not built yet|something went wrong)\s*$/im.test(body)
      || /Unexpected Application Error/i.test(body);
    regRows.push({ width, name, stillOld, blank, broke, sideways, errors: [...errors] });
    const bad = stillOld || blank || broke || sideways || errors.length;
    console.log(`  ${bad ? "XX" : "ok"}  ${width}  ${name.padEnd(18)} ` +
      `${stillOld ? "SAYS-INTEGRATION " : ""}${blank ? "BLANK " : ""}${broke ? "BROKEN " : ""}` +
      `${sideways ? "H-SCROLL " : ""}${errors.length ? "JS:" + errors[0] : ""}`);
  }
  await ctx.close();
}
// The filters and the column chooser, on the grid — the controls the fix sits beside.
const ctlCtx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const ctl = await ctlCtx.newPage();
await ctl.goto(`${BASE}/brazosbend/signin`, { waitUntil: "networkidle" });
await ctl.waitForSelector("#signin-email", { timeout: 60000 });
await ctl.fill("#signin-email", "dana@brazosbendutilities.com");
await ctl.fill("#signin-password", "S3cure!passw0rd");
await ctl.click('button[type="submit"]'); await ctl.waitForLoadState("networkidle"); await ctl.waitForTimeout(3000);
await ctl.goto(`${BASE}/brazosbend/settings/integrations`, { waitUntil: "networkidle" });
await ctl.waitForTimeout(2500);
const cardCount = () => ctl.evaluate(() => document.querySelectorAll("[data-provider]").length);
const cardsBefore = await cardCount();
await ctl.locator("summary").filter({ hasText: /Filter/i }).first().click();
await ctl.waitForTimeout(700);
await ctl.screenshot({ path: `${OUT}/ctrl-filter.png` });
const filterOpen = (await ctl.evaluate(() => document.body.innerText)).length;
await ctl.keyboard.press("Escape"); await ctl.waitForTimeout(400);
// ⚠ BOTH THESE CONTROLS ARE <summary> INSIDE A <details>, NOT <button>. A
// `button:has-text("Filter")` locator waits thirty seconds and then throws,
// and `.catch(() => {})` around it turns that into a silent pass — the shape
// this walk already got wrong once.
await ctl.locator('summary[aria-label*="olumn"]').first().click();
await ctl.waitForTimeout(700);
await ctl.screenshot({ path: `${OUT}/ctrl-columns.png` });
await ctl.fill("#integrations-search", "esri");
await ctl.waitForTimeout(1200);
const cardsAfter = await cardCount();
const narrowedTo = await ctl.$$eval("[data-provider] h3, [data-provider] h4", e => e.map(x => x.textContent.trim()));
await ctl.screenshot({ path: `${OUT}/ctrl-search.png` });
console.log(`\n  grid controls: cards ${cardsBefore} -> search "esri" -> ${cardsAfter} ${JSON.stringify(narrowedTo)}` +
  `${cardsAfter === cardsBefore ? "  XX SEARCH DID NOT NARROW" : ""}; filter panel ${filterOpen} chars`);
await fs.writeFile(`${OUT}/regression.json`, JSON.stringify(regRows, null, 2));
const regBad = regRows.filter(r => r.stillOld || r.blank || r.broke || r.sideways || r.errors.length);
console.log(`\n${regRows.length} screen-widths walked · ${regBad.length} with a finding`);

await browser.close();
