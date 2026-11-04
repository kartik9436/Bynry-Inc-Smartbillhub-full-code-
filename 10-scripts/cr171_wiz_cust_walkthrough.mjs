#!/usr/bin/env node
// CR-171-BRC10 lane MVI-WIZ-CUST — walk the move-in's step 2 · Customer at 1440
// and photograph the states images 33–40 draw, for the side-by-side with
// `05-prototype/movein-redesign-2026-10-05/images/`.
//
// Usage (after `10-scripts/cr171_wiz_cust_seed.py`, which puts a person with an
// SSN and a company with a Tax ID on file and prints a vacant unit):
//   MWC_BASE=http://127.0.0.1:5725 MWC_UNIT=SCW-U-353 \
//   MWC_OUT=08-qa/movein-2026-10-05/after/wizard-customer \
//   node 10-scripts/cr171_wiz_cust_walkthrough.mjs
//
// It commits NOTHING: it stops on step 2. Each shot asserts it is not blank —
// the h1 and the step-2 panel must be on it — and that the state it is named
// after is really on screen (the match block, the co-owner card …).
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.MWC_BASE || "http://127.0.0.1:5725";
const T = process.env.MWC_TENANT || "brazosbend";
const UNIT = process.env.MWC_UNIT || "SCW-U-353";
const OUT = process.env.MWC_OUT || "08-qa/movein-2026-10-05/after/wizard-customer";
const EMAIL = process.env.MWC_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MWC_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.MWC_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME });
// The app frame scrolls inside its own container, so a full-page shot of a
// 900px viewport is 900px. A tall viewport shows the whole step at 1440 wide.
const HEIGHT = Number(process.env.MWC_HEIGHT || 2600);
const context = await browser.newContext({ viewport: { width: 1440, height: HEIGHT } });
const page = await context.newPage();
page.setDefaultTimeout(25000);
await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);

let failed = 0;
async function shot(name, mustSee) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(400);
  const title = (await page.locator("h1").first().innerText()).trim();
  const present = (await page.locator("[data-move-in-customer]").count()) > 0 && (await page.locator(mustSee).count()) > 0;
  if (title === "" || !present) {
    failed += 1;
    console.log(`  ✗ ${name} — blank or missing ${mustSee} (h1: "${title}")`);
  } else {
    console.log(`  ✓ ${name} — ${title} · ${mustSee}`);
  }
  await page.screenshot({ path: join(OUT, name), fullPage: true });
}
const fill = (id, value) => page.fill(`#${id}`, value);

try {
  // ── step 1 · Unit: the vacant unit and a date, then Continue ────────────
  await page.goto(`${BASE}/${T}/move-ins/new`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#mvi_unit option:nth-child(2)", { state: "attached" });
  const value = await page.$eval(
    "#mvi_unit",
    (select, unit) => [...select.options].find((o) => o.textContent.includes(unit))?.value ?? "",
    UNIT,
  );
  if (!value) throw new Error(`unit ${UNIT} is not in the vacant list`);
  await page.selectOption("#mvi_unit", value);
  await page.waitForLoadState("networkidle");
  const dateBox = page.locator("#opened_at");
  if ((await dateBox.inputValue()) === "") {
    await dateBox.fill("10/10/2026");
    await dateBox.press("Tab");
  }
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForSelector('[data-wizard-step="2"][data-state="active"]');
  await page.waitForSelector("[data-move-in-customer]");

  // ── image 33: a person, co-owner ticked, the documents table, mailing ──
  await page.locator("label", { hasText: /^Person$/ }).first().click();
  await page.selectOption("#account_type", { index: 0 }).catch(() => undefined);
  await fill("full_name", "Nilesh G");
  await fill("email", "nilesh@bynry.io");
  await fill("phone", "(732) 630-0285");
  await page.selectOption("#contact_by", "email");
  await fill("dob", "06/18/2001");
  await page.keyboard.press("Tab");
  await fill("driving_licence", "DL986735");
  await fill("gov_id_last4", "2323");
  await page.click("label[for='co_owner_enabled']");
  await fill("co_owner_0_full_name", "Riya G");
  await page.selectOption("#co_owner_0_relationship", "spouse");
  await fill("co_owner_0_phone", "(732) 555-0144");
  await page.click("label[for='co_owner_0_responsible_for_bills']");
  // Image 33 draws the card CLOSED (its summary line); image 38 opens it.
  const cardToggle = page.locator('[data-tick-panel="co_owner"] button[aria-expanded]').first();
  await cardToggle.click();
  await shot("33-customer-person.png", '[data-tick-panel="co_owner"] button[aria-expanded="false"]');

  // ── image 38: the co-owner card open ────────────────────────────────────
  await cardToggle.click();
  await shot("38-co-owner-open.png", '[data-co-owner-card="1"]');

  // ── a possible match: an SSN nobody holds, but Nilesh G's name AND date
  //    of birth — Q5's possible (images 35's tier as the amended §9.IDN draws it)
  await fill("ssn", "111-22-3333");
  await page.click("[data-search-customer-id]");
  await page.waitForSelector('[data-match-block="possible"]');
  await shot("35-search-possible-name-and-dob.png", '[data-match-block="possible"]');

  // ── image 36: somebody nobody holds → New customer ──────────────────────
  await fill("full_name", "Priya Shah");
  await fill("dob", "03/02/1999");
  await page.keyboard.press("Tab");
  await page.click("[data-search-customer-id]");
  await page.waitForSelector('[data-customer-match="new"]');
  await shot("36-search-new.png", '[data-customer-match="new"]');
  await fill("full_name", "Nilesh G");
  await fill("dob", "06/18/2001");
  await page.keyboard.press("Tab");

  // ── image 34: the SSN on file → Existing customer ───────────────────────
  await fill("ssn", "210-80-9662");
  await page.click("[data-search-customer-id]");
  await page.waitForSelector('[data-match-block="found"]');
  await shot("34-search-found.png", '[data-match-block="found"]');

  // ── image 37: Link customer → Linked ────────────────────────────────────
  await page.click('[data-match-action="link"]');
  await page.waitForSelector('[data-match-block="linked"]');
  await shot("37-search-linked.png", '[data-match-block="linked"]');

  // ── image 35 (superseded): a name alone is NOT shown ────────────────────
  await page.click('[data-match-action="unlink"]');
  await fill("ssn", "");
  await fill("driving_licence", "");
  await fill("gov_id_last4", "");
  await fill("dob", "01/01/1990");
  await page.keyboard.press("Tab");
  await fill("phone", "(641) 555-0000");
  await page.click("[data-search-customer-id]");
  await page.waitForSelector('[data-customer-match="new"], [data-customer-match="nothing"]');
  const nameOnly = await page.locator("[data-match-block]").count();
  if (nameOnly !== 0) {
    failed += 1;
    console.log("  ✗ 35 — a name alone drew a match block");
  }
  await shot("35b-name-only-not-shown.png", "[data-customer-match]");

  // ── image 39: a document row added and uploaded, mailing entered ────────
  await page.click('[data-array-action="add-document"]');
  const select = page.locator('[data-cell="doc-type"]').last();
  await select.selectOption("tenancy_agreement_or_deed");
  const pdf = join(OUT, "deed.pdf");
  writeFileSync(pdf, "%PDF-1.7\n1 0 obj\n<< /Title (Deed) >>\n" + "D".repeat(2000) + "\n%%EOF");
  await page.locator('[data-editable-table="move-in-documents"] input[type="file"]').last().setInputFiles(pdf);
  await page.waitForSelector('[data-doc-file="staged"]');
  await page.click("label[for='mailing_same']");
  await fill("mailing_line1", "PO Box 4471");
  await fill("mailing_city", "Ottumwa");
  await shot("39-document-added-mailing-entered.png", '[data-doc-file="staged"]');

  // ── image 40: a company — legal name … PO, owners, the Tax ID found ─────
  await page.locator("label", { hasText: /^Company$/ }).first().click();
  await fill("full_name", "Kestrel Holdings LLC");
  await fill("trading_as", "Kestrel Bakery");
  await page.selectOption("#business_type", "llc");
  await fill("tax_id", "47-1234567");
  await page.selectOption("#registered_in", "IA");
  await page.click("[data-search-customer-id]");
  await page.waitForSelector('[data-match-block="found"]');
  await page.click('[data-match-action="link"]');
  await page.waitForSelector('[data-match-block="linked"]');
  if ((await page.locator("#contact_full_name").inputValue()) === "") await fill("contact_full_name", "Nilesh G");
  await fill("contact_job_title", "Owner");
  // The person's co-owner card carries over (the tick stays on); tick only if off.
  if (!(await page.locator("#officer_enabled").isChecked())) await page.click("label[for='officer_enabled']");
  await fill("officer_0_full_name", "Arun Mehta");
  await fill("officer_0_title", "Managing member");
  await fill("officer_0_ownership_pct", "50");
  await page.click("label[for='officer_0_signs_for_company']");
  await shot("40-customer-company.png", '[data-customer-panel="contact"]');

  // ── Continue with nothing missing reaches step 3 ────────────────────────
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForSelector('[data-wizard-step="3"][data-state="active"]', { timeout: 20000 });
  console.log("  ✓ Continue from a complete company step reaches step 3");

  // ── and on to Complete, when MWC_COMPLETE=1 (it WRITES — a lane database) ─
  if (process.env.MWC_COMPLETE === "1") {
    await page.getByRole("button", { name: "Continue" }).click();
    await page.waitForSelector('[data-wizard-step="4"][data-state="active"]', { timeout: 20000 });
    await page.getByRole("button", { name: /Complete move-in/ }).click();
    await page.waitForSelector('[data-screen="move-in-completed"]', { timeout: 30000 });
    await page.screenshot({ path: join(OUT, "48-completed-from-customer-walk.png"), fullPage: true });
    console.log(`  ✓ completed — ${(await page.locator('[data-screen="move-in-completed"]').innerText()).split("\n").slice(0, 3).join(" | ")}`);
  }
} catch (error) {
  failed += 1;
  console.log(`  ✗ ${String(error).split("\n")[0]}`);
  await page.screenshot({ path: join(OUT, "FAILED.png"), fullPage: true }).catch(() => undefined);
}
await browser.close();
clearTimeout(KILL);
console.log(failed === 0 ? "ALL SHOTS TAKEN" : `${failed} FAILED`);
process.exit(failed === 0 ? 0 : 1);
