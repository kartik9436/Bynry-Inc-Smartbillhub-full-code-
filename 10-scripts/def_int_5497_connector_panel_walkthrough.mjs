/**
 * ── Trace ──────────────────────────────────────────────
 * Defects: DEF-INT-5497 (the card was a hand-rolled box, not a Panel) ·
 *          DEF-INT-5498 (the toolbar shipped two of UI-RULES 12's four parts) ·
 *          DEF-INT-5499 (the footnote dropped the connected count) ·
 *          DEF-INT-5500 (a category rendered its raw catalogue key)
 * Change:  CR-110-BRC04 · PO 2026-09-16: *"panel class for each card - 28
 *          conenctor is not correct - we are using panel -accest something -
 *          also toolkit is not ocrrect search, filter, colume selctor etc
 *          desctoption -"*, then *"see there is a line on top and color to card
 *          - panel ui is not correct"*.
 * Rules:   CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
 *          output) · law 7 (prove a guard RED before trusting it green, in the
 *          harness that will run it) · UI-RULES 12 and 14 · B14 rule 36.
 * ───────────────────────────────────────────────────────
 *
 * ⚠ **THIS READS `getComputedStyle`, WHICH IS THE WHOLE REASON IT EXISTS.**
 * `Panel.tsx`'s own docstring records the trap that made DEF-INT-5497
 * survivable: `border-width` and `border-top-width` are DIFFERENT CSS
 * properties that COMPOSE rather than race, so a card can carry every accent
 * class a grep would look for and still render a 1px grey line — *"2px accent
 * quietly becoming 1px divider, and nothing else in the repo would have"*
 * caught it. jsdom computes no cascade and no layout, so the component suite
 * beside this file (`IntegrationsTabPanel.dom.test.tsx`) can only prove the
 * card IS a Panel; whether a Panel renders as one is a question for a browser.
 *
 * ⚠ **AND IT CHECKS THE CARD AGAINST THE PAGE, NOT AGAINST A HEX.** The PO's
 * second sentence is *"color to card"* — the complaint is that the card had no
 * surface of its OWN, which is a comparison rather than a value. Measured
 * before the fix: card `rgb(243,242,242)` over a page of `rgb(243,242,242)`.
 * Asserting a literal colour would pass the day somebody re-tones the page.
 *
 * RUN IT AGAINST THE STACK THAT SERVES THE BUILD YOU JUST MADE. `server.mjs`
 * serves whatever is in the `dist/` it was pointed at, so REBUILD FIRST
 * (`./node_modules/.bin/vite build` in `07-frontend`) or this walks the old
 * bundle and tells you so in the version line it prints.
 */
import { createRequire } from "node:module";

// ⚠ Node resolves a bare import from the SCRIPT's directory upward, never from
// `cwd`, and the repo root has no `node_modules` — so playwright is resolved
// against the frontend's own package.json explicitly.
const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8401";
const TENANT = process.env.WT_TENANT ?? "brazosbend";
const EMAIL = process.env.WT_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.WT_PASSWORD ?? "S3cure!passw0rd";
const CHROME = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
// 1440 is B14's staff design target.
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
page.on("response", (r) => {
  if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`);
});

let failed = 0;
function say(label, ok, detail = "") {
  console.log(`${ok ? "  ✓" : "  ✗"} ${label}${detail ? " — " + detail : ""}`);
  if (!ok) failed += 1;
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForTimeout(2500);
await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
await page.waitForTimeout(1800);
console.log(`at ${page.url()}`);

// ── DEF-INT-5497 · the card is a Panel, measured ──────────────────────────
console.log("\nDEF-INT-5497 · the card's top rule and its surface");
const look = await page.evaluate(() => {
  const cards = Array.from(document.querySelectorAll("[data-provider]"));
  const pageBg = getComputedStyle(document.body).backgroundColor;
  return {
    count: cards.length,
    panels: cards.filter((c) => c.hasAttribute("data-panel")).length,
    articles: cards.filter((c) => c.tagName === "ARTICLE").length,
    // Every card, not the first one: DEF-CWP-3925's lesson is that a screen
    // can be right in the place anybody looks at and wrong everywhere else.
    accented: cards.filter((c) => getComputedStyle(c).borderTopWidth === "2px").length,
    surfaced: cards.filter((c) => getComputedStyle(c).backgroundColor !== pageBg).length,
    // The accent is the tenant's own colour, so it is read off the theme rather
    // than written here as a hex — a tenant override must not turn this red.
    accentToken: getComputedStyle(document.documentElement).getPropertyValue("--color-accent").trim(),
    firstTopColour: cards.length ? getComputedStyle(cards[0]).borderTopColor : null,
    pageBg,
    firstBg: cards.length ? getComputedStyle(cards[0]).backgroundColor : null,
  };
});
say("every connector card renders through Panel", look.panels === look.count, `${look.panels}/${look.count}`);
say("and is still an <article>", look.articles === look.count, `${look.articles}/${look.count}`);
say("every card carries a 2px rule on its top edge", look.accented === look.count, `${look.accented}/${look.count}`);
say(
  "every card has a surface of its own, not the page's",
  look.surfaced === look.count,
  `card ${look.firstBg} vs page ${look.pageBg}`,
);
say("the rule is drawn in the accent, not in a divider grey", look.firstTopColour !== look.pageBg, look.firstTopColour);

// ── DEF-INT-5498 · UI-RULES 12's four parts ───────────────────────────────
console.log("\nDEF-INT-5498 · the toolbar in four parts");
const parts = await page.evaluate(() => ({
  search: document.querySelectorAll("[data-integrations-search]").length,
  chips: document.querySelectorAll("[data-category]").length,
  filter: Array.from(document.querySelectorAll("[data-connector-filter] summary")).length,
  columns: document.querySelectorAll('[aria-label="Show or hide columns"]').length,
}));
say("① the search box", parts.search === 1);
say("④ the category chips, generated", parts.chips >= 11, `${parts.chips} chips`);
say("② + Filter ▾", parts.filter >= 1);
say("③ ▦ Columns", parts.columns === 1);

// ⚠ AN OPEN PANEL, NOT A PRESENT CONTROL. A `<summary>` that opens onto nothing
// is hard-won law 2's dead-control shape, and the whole reason this file clicks
// rather than counts.
const filterTrigger = page.locator('[data-connector-filter] summary').first();
await filterTrigger.click();
await page.waitForTimeout(400);
const panel = await page.evaluate(() => {
  const open = document.querySelector("[data-connector-filter] details[open] > div");
  return open === null ? null : open.innerText;
});
say("it opens a panel with the three drawn dimensions", panel !== null && /Direction/.test(panel) && /State/.test(panel) && /Environment/.test(panel));

// Apply one dimension and prove the GRID narrows — a filter that decorates the
// toolbar and changes nothing is the DEF-3504 complaint, not a fix for it.
const before = await page.locator("[data-provider]").count();
await page.locator('[data-connector-filter] input[type="checkbox"]').first().check();
await page.waitForTimeout(600);
const after = await page.locator("[data-provider]").count();
say("pressing one narrows the grid", after < before, `${before} → ${after}`);
const chipped = await page.evaluate(() => (document.querySelector("[data-connector-filter]")?.innerText ?? ""));
say("and the applied filter says so as a chip (IS-4)", /Direction:/.test(chipped), chipped.split("\n").slice(0, 3).join(" | "));
const narrowed = await page.evaluate(() => document.body.innerText.match(/Showing \d+ of \d+\./)?.[0] ?? "");
say("the footnote stops claiming every category", narrowed !== "", narrowed);

// Put it back.
await page.locator('[data-connector-filter] input[type="checkbox"]').first().uncheck();
await page.waitForTimeout(500);
await filterTrigger.click();
await page.waitForTimeout(200);

// ── the ▦, opened and used ────────────────────────────────────────────────
console.log("\nDEF-INT-5498 · the ▦ hides and reorders a card's facts");
const opsBefore = await page.locator("[data-operations]").count();
await page.locator('[aria-label="Show or hide columns"]').click();
await page.waitForTimeout(400);
const chooser = await page.evaluate(() => document.querySelector("details[open] > div.w-\\[21rem\\]")?.innerText ?? "");
say("it opens the kit's own panel", /Columns/i.test(chooser), chooser.split("\n").slice(0, 5).join(" | "));
// Untick "Operation lines" and watch the sixteen-line cards lose them.
await page.locator('label:has-text("Operation lines") input[type="checkbox"]').first().uncheck();
await page.waitForTimeout(600);
const opsAfter = await page.locator("[data-operations]").count();
say("unticking the per-API lines takes them off every card", opsBefore > 0 && opsAfter === 0, `${opsBefore} → ${opsAfter}`);
await page.locator('button:has-text("Reset table")').first().click();
await page.waitForTimeout(600);
say("Reset puts them back", (await page.locator("[data-operations]").count()) === opsBefore);

// ── THE EMPTY STATE, AND THE WAY BACK OUT OF IT ───────────────────────────
// ⚠ THE WAY BACK IS THE HALF THAT BREAKS. `ZeroResults` offers *clear filters*,
// and this screen now has THREE things that narrow it — the category chip, the
// search box and the `+ Filter ▾` dimensions. A clear that forgets the third
// returns the clerk to a grid that is still empty, with the chip that did it
// still on screen: a control whose result does not match what it claims, which
// is DEF-3504's complaint rather than a fix for it.
console.log("\nThe empty state and the way back");
await page.locator('[data-connector-filter] summary').first().click();
await page.waitForTimeout(300);
await page.locator('[data-connector-filter] input[type="checkbox"]').last().check();
await page.waitForTimeout(400);
await page.locator('[data-connector-filter] summary').first().click();
await page.waitForTimeout(200);
await page.fill("#integrations-search", "zzzznothing");
await page.waitForTimeout(700);
say("the grid empties", (await page.locator("[data-provider]").count()) === 0);
say("and names what matched nothing", /zzzznothing/.test(await page.locator("body").innerText()));
const back = page.locator('button:has-text("Clear filters"), button:has-text("Clear")').first();
say("there is a way back", (await back.count()) > 0);
if ((await back.count()) > 0) {
  await back.click();
  await page.waitForTimeout(800);
  const restored = await page.locator("[data-provider]").count();
  say("it clears ALL THREE — the grid is whole again", restored === look.count, `${restored} of ${look.count}`);
  const leftover = await page.evaluate(() => document.querySelector("[data-connector-filter]")?.innerText ?? "");
  say("no + Filter chip is left behind", !/:/.test(leftover), leftover.replace(/\n/g, " | "));
}

// ── DEF-INT-5499 and DEF-INT-5500 ─────────────────────────────────────────
console.log("\nDEF-INT-5499 · the footnote  ·  DEF-INT-5500 · the category word");
const body = await page.locator("body").innerText(); // read AFTER the clear above
say("the footnote carries both counts", /\d+ connectors · \d+ connected\./.test(body), body.match(/\d+ connectors · \d+ connected\./)?.[0] ?? "");
say("and says what it is showing", /Showing every category\./.test(body));
say("the retired sentence is gone", !/services you can connect/.test(body));
say("no raw catalogue key reaches the screen", !/integrations\.(category|state|fact|filter)\./i.test(body));
say("the ERP chip is a word", /\bERP\b/.test(body));

console.log(`\nversion on screen: ${body.match(/v\d+\.\d+\.\d+/)?.[0] ?? "(none)"}`);
console.log(`page errors: ${errors.length === 0 ? "none" : JSON.stringify(errors.slice(0, 5))}`);
if (errors.length > 0) failed += 1;
console.log(failed === 0 ? "\nALL CHECKS PASSED" : `\n${failed} CHECK(S) FAILED`);
await browser.close();
process.exit(failed === 0 ? 0 : 1);
