#!/usr/bin/env node
// CR-181-BRC10 E1 (lane REOPEN, 2026-10-13) — Viktor Valdez moves back into
// SCW-U-022 with a balance, through the browser, both balance choices.
//
// Usage (a PRIVATE copy of the dev database — it COMMITS move-ins and a payment;
// Viktor's AC-2026-00022 must be CLOSED, owing money, before each pass):
//   RW_BASE=http://127.0.0.1:8085 RW_OUT=05-prototype/returning-customer-2026-10-13 \
//   RW_CHOICE=carry|pay_first RW_PREFIX=A node 10-scripts/cr181_returning_customer_walk.mjs
//
// `carry` · step 1 History shows what the last account owes → step 2 search
// (name + phone) answers *Same name and phone* + *Lived here last* → Link →
// *Reopen AC-2026-00022* · *Owes $…* → *Must pay first* first, Complete is
// REFUSED by name → back, *Carry it* → Complete → the account number is the
// same and Review / the details view read *Reopened … · $… carried*.
// `pay_first` · *Must pay first* → *Record payment* (Payments' own form) for
// the whole figure → *Nothing owed* → Complete.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.RW_BASE || "http://127.0.0.1:8085";
const T = process.env.RW_TENANT || "brazosbend";
const OUT = process.env.RW_OUT || "05-prototype/returning-customer-2026-10-13";
const EMAIL = process.env.RW_EMAIL || "sam.reyes@sample.test";
const PASSWORD = process.env.RW_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.RW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const UNIT = process.env.RW_UNIT || "SCW-U-022";
const DATE = process.env.RW_DATE || "10/13/2026";
const CHOICE = process.env.RW_CHOICE || "carry";
const PREFIX = process.env.RW_PREFIX || "A";
const NAME = process.env.RW_NAME || "Viktor Valdez";
const PHONE = process.env.RW_PHONE || "+1 (402) 555-1021";

const KILL = setTimeout(() => {
  console.error("REFUSED: walk exceeded 6 minutes — killing");
  process.exit(3);
}, 360000);

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
page.setDefaultTimeout(25000);
let failed = 0;
const check = (label, ok, detail = "") => {
  if (!ok) failed += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
};

async function shot(name) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(OUT, `${PREFIX}-${name}`), fullPage: true });
  console.log(`  shot ${PREFIX}-${name}`);
}
const onStep = (n) =>
  page.waitForSelector(`[data-wizard-step="${n}"][data-state="active"]`, { timeout: 20000 });
async function cont() {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(800);
  await page.getByRole("button", { name: "Continue" }).click();
}
async function advance(n) {
  await cont();
  const opened = await onStep(n).then(() => true, () => false);
  if (!opened) {
    const alerts = await page.locator('[role="alert"]').allInnerTexts().catch(() => []);
    await shot(`FAILED-step${n - 1}.png`);
    throw new Error(`step ${n} did not open — ${JSON.stringify(alerts.slice(0, 5))}`);
  }
}

try {
  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ]);

  // `RW_EXTRAS=MVI-26-0027,MVI-26-0030` — photograph the finished move-ins'
  // details and S66's *Reopen closed accounts within* (B4), and stop.
  if (process.env.RW_EXTRAS) {
    for (const ref of process.env.RW_EXTRAS.split(",")) {
      await page.goto(`${BASE}/${T}/moves/${ref}`, { waitUntil: "domcontentloaded" });
      await page.waitForSelector("[data-move-reopened]", { timeout: 20000 }).catch(() => undefined);
      const fact = await page.locator("[data-move-reopened]").innerText().catch(() => "");
      check(`${ref} details read the reopen`, /Reopened AC-2026-00022/.test(fact), fact);
      await shot(`details-${ref}.png`);
    }
    await page.goto(`${BASE}/${T}/settings/reference-data?list=billing_defaults`, { waitUntil: "domcontentloaded" });
    const setting = await page.waitForFunction(
      () => /Reopen closed accounts within/.test(document.body.innerText), null, { timeout: 20000 },
    ).then(() => true, () => false);
    check("S66 Billing defaults shows 'Reopen closed accounts within' (default 5 years)", setting);
    await page.getByText("Reopen closed accounts within", { exact: true }).scrollIntoViewIfNeeded().catch(() => undefined);
    await shot("settings-billing-defaults.png");
    throw new Error("EXTRAS_DONE");
  }

  // ── Step 1 · the vacant unit, and what its last account owes ─────────────
  await page.goto(`${BASE}/${T}/move-ins/new`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => (document.querySelector("#mvi_unit")?.options.length ?? 0) > 1, null, {
    timeout: 30000,
  });
  const value = await page.$eval(
    "#mvi_unit",
    (select, unit) => [...select.options].find((o) => o.textContent.includes(unit))?.value ?? "",
    UNIT,
  );
  check(`${UNIT} is offered as vacant`, value !== "");
  await page.selectOption("#mvi_unit", value);
  await page.waitForSelector('[data-unit-card="ready"]');
  await page.waitForLoadState("networkidle");
  const owesOnUnit = await page.locator("[data-unit-history-owes]").innerText().catch(() => "");
  check("step 1 History shows what the last account owes", /Owes \$/.test(owesOnUnit), owesOnUnit);
  const dateBox = page.locator("#opened_at");
  await dateBox.fill(DATE);
  await dateBox.press("Tab");
  // Opening reads at or above the last reads step 1 shows (BR-MET-129 refuses
  // one below): W-5021 last read 1,798 kgal, E-5021 3,877 kWh on 10/09/2026.
  const READS = JSON.parse(process.env.RW_READS || '{"W-5021":"1800","E-5021":"3880"}');
  for (const [meter, read] of Object.entries(READS)) {
    const box = page.locator(`#moveIn-open-read-${meter}`);
    if ((await box.count()) > 0) await box.fill(read);
  }
  await shot("1-unit.png");
  await advance(2);

  // ── Step 2 · the search, the two new levels, Link, Reopen ────────────────
  await page.waitForSelector("[data-move-in-customer]");
  await page.locator("label", { hasText: /^Person$/ }).first().click();
  await page.selectOption("#account_type", "residential").catch(() => undefined);
  await page.fill("#full_name", NAME);
  await page.fill("#phone", PHONE);
  await page.click("[data-search-customer-id]");
  const block = page.locator('[data-match-block="name_phone"], [data-match-block="last_occupant"]').first();
  const seen = await block.waitFor({ timeout: 15000 }).then(() => true, () => false);
  check("Search customer ID finds Viktor on name + phone (no SSN, no date of birth)", seen);
  const blockText = seen ? await block.innerText() : "";
  check("the level is labelled 'Same name and phone'", /Same name and phone/.test(blockText));
  check("and 'Lived here last'", /Lived here last/.test(blockText));
  check("his account and what it owes are listed", /AC-2026-00022/.test(blockText) && /\$[\d,]+\.\d{2} due/.test(blockText),
    (blockText.match(/\$[\d,]+\.\d{2}[^\n]*/g) || []).join(" | "));
  await shot("2a-search.png");
  await block.locator('[data-match-action="link"]').click();
  await page.waitForSelector('[data-reopen="offered"]');
  const offered = await page.locator('[data-reopen="offered"]').innerText();
  check("Reopen AC-2026-00022 is offered, with what it owes", /Reopen AC-2026-00022/.test(offered) && /Owes \$/.test(offered),
    offered.replace(/\s+/g, " ").slice(0, 160));
  await page.getByText("Must pay first", { exact: true }).click();
  await shot("2b-reopen-pay-first.png");

  if (CHOICE === "pay_first") {
    const owed = ((offered.match(/Owes \$([\d,]+\.\d{2})/) || [])[1] || "").replace(/,/g, "");
    await page.getByRole("button", { name: "Record payment" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor();
    await shot("2c-record-payment.png");
    const amount = dialog.locator("#amount");
    if ((await amount.count()) > 0) await amount.fill(owed);
    const method = dialog.locator("#method");
    if ((await method.count()) > 0) {
      const options = await method.locator("option").evaluateAll((os) => os.map((o) => o.value).filter(Boolean));
      // ACH: a check or cash needs an open counter till (BR-PAY-1186), which is
      // a cashier's act, not this walk's.
      const pick = options.find((o) => /^ach$/i.test(o)) || options[0];
      if (pick) await method.selectOption(pick);
    }
    const cleared = dialog.locator("#cleared_at");
    if ((await cleared.count()) > 0) {
      await cleared.fill(process.env.RW_PAID_ISO || "2026-10-13");
      await cleared.press("Tab");
    }
    const conf = dialog.locator("#confirmation");
    if ((await conf.count()) > 0) await conf.fill("2207");
    await shot("2d-record-payment-filled.png");
    await dialog.getByRole("button", { name: /Record/ }).last().click();
    const paid = await page.waitForSelector('[data-reopen-owes="0"], [data-reopen-owes="0.0000"]', { timeout: 20000 })
      .then(() => true, () => false);
    check("after Payments recorded the money the step reads Nothing owed", paid);
    await shot("2e-after-payment.png");
  }

  await advance(3);
  await page.waitForSelector("[data-fees-total]").catch(() => undefined);
  const addToBill = page.getByRole("radio", { name: "Add to bill" });
  if ((await addToBill.count()) > 0) await page.getByText("Add to bill", { exact: true }).first().click();
  await shot("3-billing.png");
  await advance(4);
  const review = await page.locator("[data-move-in-review]").innerText();
  check("Review says the account is reopened", /Reopened AC-2026-00022/.test(review),
    (review.match(/Reopened[^\n]*/) || [""])[0]);
  await shot("4-review.png");

  if (CHOICE === "carry") {
    // Must pay first while money is owed: Complete is refused by name.
    await page.getByRole("button", { name: /Complete move-in/ }).click();
    const refused = await page.waitForFunction(
      () => /Pay the old balance first\./.test(document.body.innerText), null, { timeout: 20000 },
    ).then(() => true, () => false);
    check("Complete is refused: 'Pay the old balance first.'", refused);
    // The refusal is the Customer step's to fix: the wizard lands there with it.
    const landed = await onStep(2).then(() => true, () => false);
    check("the refusal lands on the Customer step, beside the choice",
      landed && (await page.locator("[data-reopen-refusal]").count()) > 0);
    await page.locator("[data-reopen-refusal]").scrollIntoViewIfNeeded().catch(() => undefined);
    await shot("4b-refused-pay-first.png");
    await page.waitForSelector('[data-reopen="offered"]');
    await page.getByText("Carry it", { exact: true }).click();
    await shot("2f-carry.png");
    await advance(3);
    await advance(4);
    const review2 = await page.locator("[data-move-in-review]").innerText();
    check("Review reads the carried figure", /Reopened AC-2026-00022 · \$[\d,]+\.\d{2} carried/.test(review2),
      (review2.match(/Reopened[^\n]*/) || [""])[0]);
    await shot("4c-review-carry.png");
  }

  const answer = page.waitForResponse(
    (r) => r.request().method() === "POST" && /\/move-in$/.test(new URL(r.url()).pathname), { timeout: 45000 },
  ).then((r) => r.json()).catch(() => null);
  await page.getByRole("button", { name: /Complete move-in/ }).click();
  await page.waitForSelector('[data-screen="move-in-completed"]', { timeout: 45000 });
  const body = await answer;
  check("Complete reopened the SAME account", body?.account_no === "AC-2026-00022", body?.account_no ?? "");
  check(`the balance choice recorded is ${CHOICE}`, body?.reopened?.balance_choice === CHOICE,
    JSON.stringify(body?.reopened ?? null));
  console.log(`  RESULT ${JSON.stringify({ move_no: body?.move_no, account_no: body?.account_no, reopened: body?.reopened })}`);
  await shot("5-completed.png");

  if (body?.move_no) {
    await page.goto(`${BASE}/${T}/moves/${body.move_no}`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("[data-move-reopened]", { timeout: 20000 }).catch(() => undefined);
    const fact = await page.locator("[data-move-reopened]").innerText().catch(() => "");
    check("the move-in's details read Reopened AC-2026-00022", /Reopened AC-2026-00022/.test(fact), fact);
    await shot("6-details.png");
    await page.goto(`${BASE}/${T}/accounts?tab=move-ins`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("[data-move-in-reopened]", { timeout: 20000 }).catch(() => undefined);
    const listed = await page.locator("[data-move-in-reopened]").first().innerText().catch(() => "");
    check("the Move-ins list reads Reopened AC-2026-00022", /Reopened AC-2026-00022/.test(listed), listed);
    await shot("7-move-ins-list.png");
  }
} catch (error) {
  if (String(error).includes("EXTRAS_DONE")) {
    await browser.close();
    clearTimeout(KILL);
    console.log(failed === 0 ? "EXTRAS PASSED" : `EXTRAS: ${failed} FAILED`);
    process.exit(failed === 0 ? 0 : 1);
  }
  failed += 1;
  console.log(`  FAIL  ${String(error).split("\n")[0]}`);
  await page.screenshot({ path: join(OUT, `${PREFIX}-FAILED.png`), fullPage: true }).catch(() => undefined);
}
await browser.close();
clearTimeout(KILL);
console.log(failed === 0 ? "WALK PASSED" : `WALK: ${failed} FAILED`);
process.exit(failed === 0 ? 0 : 1);
