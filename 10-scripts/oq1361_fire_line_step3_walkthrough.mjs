#!/usr/bin/env node
// ── oq1361_fire_line_step3_walkthrough.mjs ──────────────────────────────────
//
// CLICK NEW CONNECT STEP 3 FOR A FIRE BUILD AND PHOTOGRAPH THE FIRE LINES.
//
// PO ruling 2026-10-02 (`OQ-1361`, decision log "THREE PO RULINGS IN ONE
// MESSAGE" (2)), verbatim: *"A · A fire service gets a "fire line" item with a
// size (2" to 10"), like a trash cart. The clerk picks the size on New
// Connection."* The DOM cases prove the markup; only a browser says the screen
// is the one a clerk sees (CLAUDE.md hard-won law 6).
//
// The walk: one unit, `+ Add row` → Fire, size 6"; `+ Add row` → Fire twice
// more, each set to 2". That is the build whose first bill is
// `$60.00 + 2 × $12.00 = $84.00` (proved on PostgreSQL by
// `06-backend/tests/test_oq_1361_fire_lines_and_no_net_meter_pg.py`).
//
// WHAT IT CHECKS beyond the picture — and what would make each pass wrongly:
//   * the fire row's Asset reads the tenant's fire-line NAME, not a code and
//     not a dash (a dash is what it drew before the ruling);
//   * the three Size selects read FL-6, FL-2, FL-2 in that order — asserted
//     by VALUE, so a row that rendered and held nothing cannot pass;
//   * fire's size list is fire's own: no water or electric size offered;
//   * any 5xx anywhere in the run;
//   * ⊕ `DEF-CUS-9093` (2026-10-02) — the Asset cell's chosen NAME is not cut
//     off, at 1440 AND 1280: the selected option's text, measured in the
//     select's own font, plus its padding, must fit the select's width. A
//     screenshot cannot fail; this can. And Fire is ticked on step 2 first, so
//     the picture carries no "This address does not." strip.
//
// ⚠ The bundle must be built `--mode compose` (DEF-INF-7802) and the tenant
// must SELL fire — the walk refuses by name when Fire is not offered.
//
//   SMOKE_BASE (http://127.0.0.1:8992) · SMOKE_TENANT · SMOKE_EMAIL ·
//   SMOKE_PASSWORD · SMOKE_OUT · SMOKE_CHROME
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.SMOKE_BASE ?? "http://127.0.0.1:8992").replace(/\/$/, "");
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "08-qa/screens/fire-line-2026-10-02";

const failures = [];
const fail = (m) => {
  failures.push(m);
  console.error(`  ✗ ${m}`);
};
const note = (m) => console.log(`  · ${m}`);

function resolveChromium() {
  if (process.env.SMOKE_CHROME && existsSync(process.env.SMOKE_CHROME)) return process.env.SMOKE_CHROME;
  const wanted = chromium.executablePath();
  if (existsSync(wanted)) return wanted;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  const found = existsSync(root)
    ? readdirSync(root)
        .filter((name) => name.startsWith("chromium-"))
        .map((name) => join(root, name, "chrome-linux", "chrome"))
        .filter(existsSync)
    : [];
  if (found.length === 0) return wanted;
  console.log(`  · pinned chromium absent (${wanted}); taking ${found[0]}`);
  return found[0];
}

const TABLE = '[data-array="units-and-service-points"]';

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(15000);
  page.on("response", (response) => {
    if (response.status() >= 500) fail(`${response.status()} ${response.url()}`);
  });

  console.log(`── sign in as ${EMAIL}`);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 }).catch(() => undefined);
  if (/signin/.test(page.url())) {
    fail(`sign-in did not leave /signin: ${(await page.locator("body").innerText()).slice(0, 200)}`);
    await browser.close();
    return;
  }

  console.log("── New Connect step 2: tick Fire, then step 3");
  await page.goto(`${BASE}/${TENANT}/connections/new?step=2`, { waitUntil: "networkidle" });
  await page.locator("#services_available-add").selectOption("fire");
  await page.waitForTimeout(300);
  // Continue, as a clerk does — the rail's cells are not doors (WizardFrame),
  // and a reload would drop the draft. A new address needs its street lines.
  await page.fill("#nc_address", "12 Hose Reel Rd");
  await page.fill("#nc_city", "Katy").catch(() => undefined);
  await page.fill("#nc_state", "TX").catch(() => undefined);
  await page.fill("#nc_zip", "77494").catch(() => undefined);
  // Step 2 asks for a plan; the first published one is enough for a picture.
  await page.locator("#nc_plan").selectOption({ index: 1 });
  await page.waitForTimeout(300);
  await page.getByRole("button", { name: /^Continue/ }).first().click();
  await page.waitForTimeout(800);
  if (!/step=3/.test(page.url())) {
    const said = (await page.locator("main").innerText().catch(() => "")).replace(/\s+/g, " ");
    fail(`Continue did not open step 3 (at ${page.url()}). The page says: ${said.slice(0, 1500)}`);
    await page.screenshot({ path: join(OUT, "step2-refused.png"), fullPage: true });
    await browser.close();
    return;
  }
  await page.fill("#nc_from", "1");
  await page.fill("#nc_to", "1");
  await page.waitForTimeout(400);

  const serviceSelects = () => page.locator(`${TABLE} select[data-cell="service"]`);
  const sizeSelects = () => page.locator(`${TABLE} select[data-cell="size"]`);

  // Fire was ticked on step 2, so the unit arrives with ONE fire row; two more
  // pieces — each via `+ Add row` → Fire.
  for (let n = 0; n < 2; n += 1) {
    await page.locator('[data-array-action="add-row"]').click();
    await page.waitForTimeout(300);
    const pending = serviceSelects().last();
    const offered = await pending.locator("option").allInnerTexts();
    if (!offered.some((word) => /fire/i.test(word))) {
      fail(`Fire is not offered by the service cell (offered: ${offered.join(", ")}) — the tenant must sell fire`);
      await page.screenshot({ path: join(OUT, "step3-no-fire.png"), fullPage: true });
      await browser.close();
      return;
    }
    await pending.selectOption("fire");
    await page.waitForTimeout(500);
  }

  const sizes = sizeSelects();
  const count = await sizes.count();
  if (count !== 3) fail(`expected 3 fire size selects (one row + two pieces), found ${count}`);
  const wanted = ["FL-6", "FL-2", "FL-2"];
  for (let i = 0; i < Math.min(count, 3); i += 1) {
    await sizes.nth(i).selectOption(wanted[i]);
    await page.waitForTimeout(250);
  }
  const values = [];
  for (let i = 0; i < (await sizes.count()); i += 1) values.push(await sizes.nth(i).inputValue());
  if (JSON.stringify(values) !== JSON.stringify(wanted)) fail(`sizes read ${JSON.stringify(values)}, wanted ${JSON.stringify(wanted)}`);
  else note(`three fire lines: ${values.join(" · ")}`);

  const fireOptions = await sizes.first().locator("option").evaluateAll((nodes) => nodes.map((n) => n.value).filter(Boolean));
  if (fireOptions.some((code) => !code.startsWith("FL-"))) fail(`fire's size list holds another service's size: ${fireOptions.join(", ")}`);
  else note(`fire's size list: ${fireOptions.join(", ")}`);

  const asset = page.locator(`${TABLE} select[data-cell="asset"]`).first();
  const assetWord = await asset.evaluate((node) => node.options[node.selectedIndex]?.text ?? "");
  if (!/fire/i.test(assetWord)) fail(`the fire row's Asset reads "${assetWord}", not the fire line`);
  else note(`Asset reads "${assetWord}"`);

  if ((await page.getByText("This address does not.").count()) > 0) {
    fail('the "This address does not." strip is on the page although Fire was ticked on step 2');
  }

  /** Does the select show its chosen option's whole name? */
  const clipped = (locator) =>
    locator.evaluate((node) => {
      const text = node.options[node.selectedIndex]?.text ?? "";
      const style = getComputedStyle(node);
      const canvas = document.createElement("canvas").getContext("2d");
      canvas.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      const needed =
        canvas.measureText(text).width +
        parseFloat(style.paddingLeft) +
        parseFloat(style.paddingRight) +
        parseFloat(style.borderLeftWidth) +
        parseFloat(style.borderRightWidth);
      return { text, needed: Math.ceil(needed), width: node.getBoundingClientRect().width };
    });

  for (const width of [1440, 1280]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.waitForTimeout(300);
    const got = await clipped(asset);
    if (got.needed > got.width + 0.5) {
      fail(`at ${width} the Asset cell shows "${got.text}" in ${Math.round(got.width)}px; it needs ${got.needed}px — cut off`);
    } else {
      note(`at ${width} "${got.text}" fits (${got.needed}px in ${Math.round(got.width)}px)`);
    }
    const pageScroll = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    if (pageScroll) fail(`at ${width} the PAGE scrolls sideways`);
    const shot = join(OUT, `step3-fire-lines-${width}.png`);
    await page.locator('[data-array="units-and-service-points"]').scrollIntoViewIfNeeded();
    await page.screenshot({ path: shot, fullPage: true });
    note(`photographed → ${shot}`);
  }
  await browser.close();
}

main()
  .catch((error) => fail(String(error?.stack ?? error)))
  .finally(() => {
    console.log(failures.length === 0 ? "PASS" : `FAIL (${failures.length})`);
    process.exitCode = failures.length === 0 ? 0 : 1;
  });
