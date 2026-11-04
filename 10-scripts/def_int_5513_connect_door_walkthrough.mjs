// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-INT-5513` — the connector set-up screen (S147 · INT-07) was
//          built, routed and tested by `CR-110-BRC04` wave A and NOTHING
//          linked to it. The card's `Connect` went on opening `ConnectModal`,
//          so the screen was reachable only by typing its address. The PO,
//          from the deployed product: *"it is still showing modal - i think
//          routing issue - it is not reolsved"*.
// Rules:   CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
//          output — diff the running app) · law 2's MIRROR (a live screen
//          behind a dead control; assert the destination by ADDRESS and by
//          the screen id it opens) · law 7 (a check's output must distinguish
//          pass from fail TO A READER, and "what would make this pass
//          wrongly?") · `22-product-maintenance-process.md` step 4 (prove the
//          fix against the REPRODUCTION) and step 5 (regression-walk the
//          neighbours).
// ───────────────────────────────────────────────────────
/**
 * Press `Connect` the way a clerk would, and write down where it lands.
 *
 *     BASE=http://127.0.0.1:8411 node 10-scripts/def_int_5513_connect_door_walkthrough.mjs
 *
 * ⚠ **IT ASSERTS WHAT THE STACK SERVES BEFORE IT BELIEVES ANY SCREENSHOT**,
 * and that clause is paid for: on 2026-09-16 a front end was started on a port
 * another lane already held, so it never bound, the browser was quietly served
 * by the older stack, and its retired connectors were reported to the PO as a
 * product fault. A walk against the wrong backend is not a weaker proof — it
 * is a proof of a different product. The provider COUNT is read off the API
 * first and the walk refuses if it is not 28.
 *
 * ⚠ **THE FOUR SHAPES ARE FOUR AUTH STORIES, NOT FOUR NAMES.** One that signs
 * in with the vendor, one that takes a key we type, one that reads from us
 * with a key WE issue, and one drawn but not shipping. A sample of four of one
 * shape would say nothing about the other 24. No provider is named in the code
 * under test (`BR-INT-037`) — these are the fixtures a person looks at.
 *
 * ⚠ **A REFUSAL IS RECORDED AS A RESULT, NOT AS A FAILURE.** A *coming soon*
 * card SHOULD refuse and a card with no adapter SHOULD refuse, so a walk that
 * scored every refusal as a fault would bury the real ones. Each row says what
 * was pressed and what came back, and says whether that is the EXPECTED
 * outcome for that shape — which is the difference between a reader being able
 * to judge and a reader being told a number.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright-core");
const fs = await import("node:fs/promises");

const BASE = process.env.BASE ?? "http://127.0.0.1:8411";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "/tmp/def5513";
await fs.mkdir(OUT, { recursive: true });

/** key → [what shape it is, what pressing it MUST do]. */
const SHAPES = [
  ["email_microsoft", "signs in with the vendor (token exchange)", "door"],
  ["gis_esri", "takes a key we type (we hold theirs)", "door"],
  ["erp_aclarian", "reads from us with a key WE issue", "door"],
  ["accounting_file", "a file drop, no credential at all", "door"],
  ["sms_twilio", "drawn, not shipping — coming soon", "refuses"],
  ["geocoder_census", "live, but nothing here can dial it", "refuses"],
];

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForTimeout(2500);

// ── The stack check, before anything is believed ────────────────────────────
const grid = await page.evaluate(
  async (t) => (await (await fetch(`/api/${t}/integrations`)).json()),
  TENANT,
);
const served = (grid.providers ?? []).length;
console.log(`STACK: ${BASE} serves ${served} connectors`);
if (served !== 28) {
  console.log(`REFUSING TO WALK — expected 28, got ${served}. Wrong backend or wrong build.`);
  await browser.close();
  process.exit(2);
}

let bad = 0;
const say = (ok, line) => {
  console.log(`${ok ? "  ok  " : " FAIL "} ${line}`);
  if (!ok) bad += 1;
};

console.log("\n── 1 · the card's Connect, on four live shapes and two refusals ──");
for (const [key, shape, expect] of SHAPES) {
  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  const card = await page.$(`[data-provider="${key}"]`);
  if (card === null) { say(false, `${key}: NO CARD ON THE GRID`); continue; }

  if (expect === "refuses") {
    // The control must still be DRAWN and still be dead, with its reason.
    const held = await card.evaluate((n) => {
      const soon = n.querySelector('[data-coming-soon-connect="true"]');
      const noAdapter = n.querySelector('[data-not-connectable="true"]');
      const link = n.querySelector("[data-setup-link]");
      const el = soon ?? noAdapter;
      return {
        drawn: el !== null,
        disabled: el === null ? null : el.disabled === true || el.getAttribute("aria-disabled") === "true",
        isLink: link !== null,
        reason: n.querySelector('[data-not-connectable="true"]') === null ? null : n.innerText.split("\n").at(-1),
      };
    });
    say(held.drawn && held.disabled === true && !held.isLink,
      `${key} · ${shape} → control drawn and DEAD, no door — which is correct` +
      (held.reason === null ? "" : ` · reason on screen: "${held.reason}"`));
    await card.screenshot({ path: `${OUT}/refuses-${key}.png` });
    continue;
  }

  // ── the door itself: press it and see where the browser ends up ──────────
  const before = page.url();
  const link = await card.$("[data-setup-link]");
  if (link === null) { say(false, `${key} · ${shape} → NO DOOR: the card renders no set-up link`); continue; }
  const href = await link.getAttribute("href");
  const label = (await link.innerText()).trim();
  await link.click();
  await page.waitForTimeout(1600);
  const after = page.url();
  const dialog = await page.$('[role="dialog"], [data-modal]');
  const wanted = `/${TENANT}/settings/connectors/${key}/configure`;

  // ⚠ THE PAGE MUST HAVE ACTUALLY RENDERED, NOT MERELY BEEN NAVIGATED TO. A
  // URL bar is not a screen: `CR-110`'s own walk found that the product's
  // catch-all *"This screen is not built yet"* and a HELD connector's *"Coming
  // soon — not built yet"* are two different sentences, and scoring on the
  // shared phrase turned ruled refusals into faults. So this reads the screen's
  // own marks: the connector's name, and the panel wave A drew.
  const screen = await page.evaluate(() => ({
    notBuilt: document.body.innerText.includes("This screen is not built yet"),
    heading: document.querySelector("h1")?.innerText?.trim() ?? null,
    hasDetails: document.querySelector('[data-field-slot="true"]') !== null,
    back: document.querySelector("a[href$='/settings/integrations']")?.innerText?.trim() ?? null,
  }));

  say(
    after.endsWith(wanted) && !screen.notBuilt && screen.hasDetails && dialog === null,
    `${key} · ${shape}\n` +
      `         pressed "${label}" · href=${href}\n` +
      `         landed on ${after.replace(BASE, "")} (wanted ${wanted})\n` +
      `         screen: heading="${screen.heading}" · fields panel=${screen.hasDetails} · back="${screen.back}" · dialog=${dialog === null ? "none" : "OPENED"}`,
  );
  await page.screenshot({ path: `${OUT}/door-${key}.png`, fullPage: false });
  if (after === before) say(false, `${key}: the URL never changed — this is the defect itself`);
}

console.log("\n── 2 · REGRESSION · the modal still serves what it still owns ──");
// `manage` — a connected card. `email_smtp` is *not working*, so its control is
// *Fix it*, which is the SAME `manage` mode and the danger tier (B14 rule 6).
await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
await page.waitForTimeout(700);
{
  const card = await page.$('[data-provider="email_smtp"]');
  const btn = await card.$('button[data-card-action="manage"]');
  const label = btn === null ? null : (await btn.innerText()).trim();
  if (btn !== null) { await btn.click(); await page.waitForTimeout(1300); }
  const dialog = await page.$('[role="dialog"], [data-modal]');
  const text = dialog === null ? "" : (await dialog.innerText()).replace(/\n+/g, " · ").slice(0, 90);
  say(btn !== null && dialog !== null,
    `manage ("${label}") still opens the MODAL — not the screen · ${text}`);
  if (dialog !== null) await page.screenshot({ path: `${OUT}/regression-manage.png` });
}

// The test path that needs a typed recipient (BR-INT-026) also opens the modal.
await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
await page.waitForTimeout(700);
{
  const anyTest = await page.$('button[data-card-action="test"]');
  if (anyTest === null) {
    say(true, "no card is in the *untested* state on this tenant — the recipient-test path is unexercised here, and that is a GAP in this walk rather than a pass");
  } else {
    const label = (await anyTest.innerText()).trim();
    await anyTest.click();
    await page.waitForTimeout(1500);
    const dialog = await page.$('[role="dialog"], [data-modal]');
    say(dialog !== null, `test ("${label}") that needs a recipient still opens the MODAL`);
  }
}

console.log("\n── 3 · REGRESSION · the grid itself still works ──");
await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
await page.waitForTimeout(700);
{
  const cards = async () => (await page.$$("[data-provider]")).length;
  say((await cards()) === 28, `the grid draws all 28 cards`);

  await page.fill("[data-integrations-search]", "aclarian");
  await page.waitForTimeout(600);
  const searched = await cards();
  say(searched > 0 && searched < 28, `search narrows the grid (28 → ${searched})`);
  await page.fill("[data-integrations-search]", "");
  await page.waitForTimeout(500);

  const chip = await page.$('[data-category="erp"]');
  if (chip !== null) {
    await chip.click();
    await page.waitForTimeout(600);
    const chipped = await cards();
    say(chipped > 0 && chipped < 28, `the ERP category chip narrows the grid (28 → ${chipped})`);
    await (await page.$('[data-category="all"]')).click();
    await page.waitForTimeout(500);
  }

  const chooser = await page.$('summary[aria-label="Show or hide columns"]');
  if (chooser !== null) {
    await chooser.click();
    await page.waitForTimeout(500);
    const opened = await page.$$eval('input[type="checkbox"]', (n) => n.length);
    say(opened >= 3, `the column chooser opens and offers its ${opened} facts`);
    await page.keyboard.press("Escape");
  }
  await page.screenshot({ path: `${OUT}/regression-grid.png` });
}

console.log("\n── 4 · REGRESSION · the connection detail page still opens ──");
{
  await page.goto(`${BASE}/${TENANT}/settings/integrations/email_smtp`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const detail = await page.evaluate(() => ({
    notBuilt: document.body.innerText.includes("This screen is not built yet"),
    heading: document.querySelector("h1")?.innerText?.trim() ?? null,
  }));
  say(!detail.notBuilt && detail.heading !== null,
    `the connection view opens · heading="${detail.heading}"`);
  await page.screenshot({ path: `${OUT}/regression-connection-detail.png` });
}

console.log(
  `\n${bad === 0 ? "ALL CHECKS PASSED" : `${bad} CHECK(S) FAILED`} — screenshots in ${OUT}`,
);
await browser.close();
process.exit(bad === 0 ? 0 : 1);
