// ── Trace ──────────────────────────────────────────────
// Change:  CR-167-BRC10 round 2 tasks 4 and 5 (lane PLAN-FORM) — walk the New
//          plan form in a real browser at 1440 and photograph each built state
//          beside images 04–23 of `05-prototype/plans-2026-10-03/images/`.
// ───────────────────────────────────────────────────────
//
// Expects:
//   * the API — `manage.py runserver 127.0.0.1:8161` on PostgreSQL 16
//     (`sbh_planform`: `migrate` + `seed_demo` + `load_sample_data --tenant
//     brazosbend`; Brazos Bend, Dana);
//   * the SPA — `vite build --mode wolocal`, then
//     `PORT=5261 API_PROXY_TARGET=http://127.0.0.1:8161 node 07-frontend/server.mjs`.
//
//   OUT=08-qa/plans-2026-10-03/form node 10-scripts/cr167_plan_form_walk.mjs
//
// ⚠ **TWO MODES, AND THE PHOTOGRAPHS SAY WHICH.** `GET /plans/form-options` and
// §7.3's `POST /plans` are the server lane's (task 3). Run with nothing set and
// the walk goes to the real server for everything; a route it does not serve
// yet shows as empty dropdowns. Run with `CONTRACT=1` and the walk answers
// exactly those two routes from `CONTRACT_OPTIONS` below — the agreed §7.3/§7.6
// shape filled with the IMAGE's own figures — and everything else (sign-in,
// the frame, permissions, the shell's currency) is still the real server.
// Every photograph in CONTRACT mode is named `…-contract.png`.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5261";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr167-form";
const CONTRACT = process.env.CONTRACT === "1";
const SUFFIX = CONTRACT ? "-contract" : "-server";
mkdirSync(OUT, { recursive: true });

function ref(id, kind, code, name, version, from) {
  return { id, kind, code, name, version, version_label: null, effective_from: from, effective_to: null, next: null };
}
function sched(id, code, name, version, from, modelLabel) {
  return { ...ref(id, "schedule", code, name, version, from), model: "x", model_label: modelLabel };
}
const sizes = (rows) => rows.map(([c, l, a]) => ({ size_class: c, size_label: l, amount_display: a }));
const usage = (kind, rows) => ({ kind: "x", kind_label: kind, rows: rows.map(([label, rate]) => ({ label, rate_display: rate })) });

/** The image's own figures (README: "every figure in an image is an
 *  ILLUSTRATION" — they are used here only to photograph the same states). */
const CONTRACT_OPTIONS = {
  currency: "USD",
  customer_classes: [
    { value: "c-res", label: "Residential" },
    { value: "c-com", label: "Commercial" },
    { value: "c-ind", label: "Industrial" },
    { value: "c-agr", label: "Agricultural" },
  ],
  services: [
    { value: "water", label: "Water", gl: { code: "4110", name: "Water revenue" } },
    { value: "sewer", label: "Sewer", gl: { code: "4120", name: "Sewer revenue" } },
    { value: "trash", label: "Trash", gl: { code: "4130", name: "Trash revenue" } },
    { value: "fire", label: "Fire", gl: { code: "4155", name: "Fire revenue" } },
  ],
  schedules: [
    {
      ref: sched("s-w", "RW", "Residential water (inclining tiers)", 4, "2026-09-30", null),
      service: "water",
      base: {
        code: ref("b-w1", "base_code", "BASE-W1", "Water base", 2, "2026-09-01"),
        sized_by_label: "meter size",
        by_size: sizes([["58", '5/8"', "10.00"], ["1", '1"', "18.00"], ["2", '2"', "40.00"]]),
        flat_display: null, state: "ok", codes: ["BASE-W1"], monthly_amount: "10.0000",
      },
      minimum: { by_size: sizes([["58", '5/8"', "5.00"], ["1", '1"', "5.00"], ["2", '2"', "5.00"]]), flat_display: null },
      usage: usage("Block (per month)", [["0 – 5 kgal", "$4.24 per kgal"], ["5 – 15 kgal", "$6.89 per kgal"], ["Over 15 kgal", "$8.48 per kgal"]]),
    },
    {
      ref: sched("s-s", "SF", "Sewer flat rate", 3, "2026-09-28", "Flat"),
      service: "sewer",
      base: { code: ref("b-s", "base_code", "BASE-S", "Sewer base", 1, "2026-08-01"), sized_by_label: null, by_size: [], flat_display: "9.00", state: "ok", codes: ["BASE-S"], monthly_amount: "9.0000" },
      minimum: { by_size: [], flat_display: null },
      usage: usage(null, [["Each month", "$14.00 flat"]]),
    },
    {
      ref: sched("s-t", "TM", "Trash (monthly, not measured)", 1, "2026-08-01", null),
      service: "trash",
      base: { code: ref("b-t", "base_code", "BASE-T", "Trash base", 1, "2026-08-01"), sized_by_label: "cart size", by_size: sizes([["64", "64 gal cart", "0.00"], ["96", "96 gal cart", "0.00"]]), flat_display: null, state: "ok", codes: ["BASE-T"], monthly_amount: "0.0000" },
      minimum: { by_size: [], flat_display: null },
      usage: usage("Per cart, per month", [["64 gal cart", "$15.00"], ["96 gal cart", "$20.00"]]),
    },
    {
      ref: sched("s-f", "FC", "Fire capacity", 2, "2026-09-03", "Tiered"),
      service: "fire",
      base: { code: ref("b-f", "base_code", "BASE-FIRE", "Fire base", 2, "2026-09-03"), sized_by_label: "fire line size", by_size: sizes([["2", '2" line', "0.00"], ["4", '4" line', "0.00"], ["6", '6" line', "0.00"]]), flat_display: null, state: "ok", codes: ["BASE-FIRE"], monthly_amount: "0.0000" },
      minimum: { by_size: [], flat_display: null },
      usage: usage("Per line, per month", [['2" line', "$12.00"], ['4" line', "$30.00"], ['6" line', "$60.00"]]),
    },
  ],
  charge_codes: [
    {
      ref: ref("cc-late", "charge_code", "LATE", "Late payment fee", 1, "2026-08-01"),
      priced_by: "class",
      rows: [
        { class_or_size_label: "Residential", amount_display: null, percent_display: "1.50%", min_display: "5.00" },
        { class_or_size_label: "Commercial", amount_display: null, percent_display: "2.00%", min_display: "10.00" },
      ],
      gl: { code: "2610", name: "Late fees" }, type_label: "Penalty", when_label: "After the due date", default_on_new_plan: true,
    },
    {
      ref: ref("cc-recon", "charge_code", "RECON", "Reconnection fee", 2, "2026-09-15"),
      priced_by: "one_amount",
      rows: [{ class_or_size_label: "", amount_display: "75.00", percent_display: null, min_display: null }],
      gl: { code: "4310", name: "Service fees" }, type_label: "One-time", when_label: "On reconnection", default_on_new_plan: false,
    },
    {
      ref: ref("cc-nsf", "charge_code", "NSF", "Returned payment fee", 1, "2026-08-01"),
      priced_by: "one_amount",
      rows: [{ class_or_size_label: "", amount_display: "30.00", percent_display: null, min_display: null }],
      gl: { code: "4320", name: "Returned payments" }, type_label: "One-time", when_label: "On a returned payment", default_on_new_plan: false,
    },
  ],
  taxes: [
    { ref: ref("t-st", "tax", "TX-ST", "TX State Utility Tax", 1, "2026-01-01"), rate_display: "6.25%", rate_percent: "6.250000", what_is_taxed_label: "Usage and base charges", gl: { code: "2200-02", name: "Tax payable · State" }, authority: null, brought_by: "attached" },
    { ref: ref("t-bx", "tax", "BEXAR", "Bexar County", 3, "2026-01-01"), rate_display: "2%", rate_percent: "2.000000", what_is_taxed_label: "Usage and base charges", gl: { code: "2200-01", name: "Tax payable · Local" }, authority: null, brought_by: "attached" },
    { ref: ref("t-cf", "tax", "CITY-FR", "City franchise fee", 2, "2026-09-01"), rate_display: "3%", rate_percent: "3.000000", what_is_taxed_label: "Usage and base charges", gl: { code: "2200-03", name: "Fees payable · City" }, authority: null, brought_by: "attached" },
  ],
  deposit_codes: [
    {
      ref: ref("d-dep", "deposit_code", "DEPOSIT", "Security deposit", 2, "2026-09-01"),
      priced_by: "class",
      rows: [
        { class_or_size_label: "Residential", amount_display: "150.00", percent_display: null, min_display: null },
        { class_or_size_label: "Commercial", amount_display: "300.00", percent_display: null, min_display: null },
      ],
      gl: { code: "2300", name: "Deposits held" },
    },
    {
      ref: ref("d-meter", "deposit_code", "MTRDEP", "Meter deposit", 1, "2026-08-01"),
      priced_by: "class",
      rows: [{ class_or_size_label: "Commercial", amount_display: "500.00", percent_display: null, min_display: null }],
      gl: { code: "2300", name: "Deposits held" },
    },
  ],
  discounts: [
    { ref: ref("ds-sen", "discount", "SENIOR", "Senior discount", 1, "2026-08-01"), value_display: "15%", gl: { code: "4760", name: "Customer discounts" }, enrolled: 12, offered_from: null, offered_until: null },
    { ref: ref("ds-auto", "discount", "AUTOPAY", "Autopay discount", 1, "2026-08-01"), value_display: "0.5%", gl: { code: "4760", name: "Customer discounts" }, enrolled: 0, offered_from: null, offered_until: null },
  ],
};

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const say = (...parts) => console.log(...parts);
const posted = [];
if (CONTRACT) {
  await page.route("**/api/*/plans/form-options*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(CONTRACT_OPTIONS) }),
  );
  await page.route("**/api/*/plans", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const body = JSON.parse(route.request().postData() ?? "{}");
    posted.push(body);
    return route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ id: "walk-plan", name: body.details?.name ?? "", status: body.publish ? "published" : "draft", effective_from: body.effective_from ?? null }),
    });
  });
} else {
  page.on("response", async (res) => {
    const path = new URL(res.url()).pathname;
    if (/\/plans(\/form-options)?(\?|$)/.test(path + "?")) {
      say(`  server ${res.request().method()} ${path} → ${res.status()}`);
      if (path.endsWith("/plans/form-options") && res.ok()) served = await res.json();
      if (res.request().method() === "POST") posted.push(JSON.parse(res.request().postData() ?? "{}"));
    }
  });
}
// ⊕ lane PLAN-API (CR-167 task 3): the option VALUES the walk picks. CONTRACT
// mode keeps the fixture's ids; against the real server they are read from the
// `GET /plans/form-options` the page itself made (Brazos Bend sells electric and
// water, so the services are those two, and it has two taxes).
let served = null;
function values() {
  if (CONTRACT) {
    return {
      services: [["water", "s-w"], ["sewer", "s-s"], ["trash", "s-t"]],
      last: ["fire", "s-f"],
      cls: "c-res", recon: "cc-recon", taxes: ["t-st", "t-bx"], third: "t-cf",
      deposit: "d-dep", senior: "ds-sen", autopay: "ds-auto",
    };
  }
  const sched = (service, re) => served.schedules.find((s) => s.service === service && re.test(s.ref.name)).ref.id;
  const code = (list, c) => served[list].find((row) => row.ref.code === c).ref.id;
  return {
    services: [["water", sched("water", /^Sample — Residential water/)]],
    last: ["electric", sched("electric", /^Sample — Electric usage/)],
    cls: served.customer_classes.find((c) => c.label === "Residential").value,
    recon: code("charge_codes", "RECON"),
    taxes: [served.taxes[0].ref.id],
    third: served.taxes[1].ref.id,
    deposit: code("deposit_codes", "DEPOSIT"),
    senior: code("discounts", "SENIOR"),
    autopay: code("discounts", "AUTOPAY"),
  };
}

async function shot(name, caption) {
  await page.waitForTimeout(700);
  // The app frame scrolls its own main column, so a full-page photograph is
  // only the viewport: grow the viewport to the column's height first —
  // after shrinking it back, so a short state is not photographed at the
  // previous state's height.
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(200);
  const height = await page.evaluate(() => {
    const scroller = [...document.querySelectorAll("main, main *")].find(
      (el) => el.scrollHeight > el.clientHeight + 4 && getComputedStyle(el).overflowY !== "visible",
    );
    const main = document.querySelector("main");
    const top = main ? main.getBoundingClientRect().top : 0;
    return Math.ceil(Math.max(900, (scroller ?? main ?? document.body).scrollHeight + top + 40));
  });
  await page.setViewportSize({ width: 1440, height });
  await page.screenshot({ path: `${OUT}/${name}${SUFFIX}.png`, fullPage: true });
  say(`=== ${name}${SUFFIX}.png — ${caption}`);
}
const click = (name) => page.getByRole("button", { name, exact: true }).click();
async function pickLast(label, value) {
  const boxes = page.getByRole("combobox", { name: label, exact: true });
  await boxes.nth((await boxes.count()) - 1).selectOption(value);
}
async function addRow(button) {
  await click(button);
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.getByRole("button", { name: /sign in/i }).click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

async function openNew() {
  await page.goto(`${BASE}/${TENANT}/plans-rates/plans/new`, { waitUntil: "networkidle" });
  await page.getByLabel(/^Plan name/).waitFor();
}

// ── Run 1: publish (images 04–22) ─────────────────────────────────────────
await openNew();
await shot("04-new-1-details-empty", "step 1 Details, empty");
await click("Continue");
await shot("05-new-1-details-errors", "Continue on empty: each missing box named");
await page.getByRole("button", { name: /^Customer classes/ }).click();
await shot("06-new-1-classes-dropdown", "Customer classes dropdown, Every customer class first");
await page.keyboard.press("Escape");
await page.getByLabel(/^Plan name/).fill("Residential City Plan");
await page.getByLabel(/^Code/).fill("RCP");
const V = values();
{
  await page.getByRole("button", { name: /^Customer classes/ }).click();
  await page.getByRole("checkbox", { name: "Residential", exact: true }).check();
  await page.keyboard.press("Escape");
}
await page.getByLabel(/^Description for customers/).fill("Water, sewer, trash and fire for homes inside the city.");
await addRow("+ Add note");
{
  await pickLast("Attribute", "customer_class");
  await pickLast("Operator", "is");
  await pickLast("Value", V.cls);
}
await shot("07-new-1-details-filled", "step 1 filled");
await click("Continue");
await page.getByText("Services and rate schedules").waitFor();
{
  for (const [service, schedule] of V.services) {
    await addRow("+ Add service");
    await pickLast("Service", service);
    await pickLast("Rate schedule", schedule);
  }
  await page.getByLabel(/^Outside-city premises pay more/).selectOption("yes");
  await page.fill("#plan-surcharge", "25");
  const ticks = page.getByRole("checkbox", { name: "Surcharge", exact: true });
  await ticks.nth(0).check();
  if (V.services.length > 1) await ticks.nth(1).check();
}
await shot("08-new-2-services-filled", "step 2 services with schedule, base, minimum");
{
  await addRow("+ Add service");
  await shot("09-new-2-services-row-added", "empty service row added");
  await click("Continue");
  await shot("10-new-2-services-row-error", "empty row refused by name");
  await pickLast("Service", V.last[0]);
  await pickLast("Rate schedule", V.last[1]);
  await shot("11-new-2-services-all-added", "fire picked; + Add service greyed, All added.");
  await shot("12-new-2-surcharge-on", "outside-city surcharge on, Surcharge tick per row");
  await click("Continue");
  await page.getByRole("button", { name: "+ Add charge code" }).waitFor();
  await addRow("+ Add charge code");
  await pickLast("Charge code", V.recon);
  for (const tax of V.taxes) {
    await addRow("+ Add tax");
    await pickLast("Tax", tax);
  }
  await shot("13-new-3-charges-filled", "step 3 charge codes (LATE pre-filled) and taxes");
  await addRow("+ Add tax");
  await pickLast("Tax", V.third);
  await shot("14-new-3-tax-added", "third tax added, All added.");
  await addRow("+ Add charge code");
  await click("Continue");
  await shot("15-new-3-charges-error", "empty charge-code row refused");
  const removes = page.locator('[data-array="plan-charges"]').getByRole("button", { name: /Remove/ });
  await removes.nth((await removes.count()) - 1).click();
  await shot("16-new-3-row-removed", "empty row removed with ×");
  await click("Continue");
  await page.getByRole("button", { name: "+ Add deposit" }).waitFor();
  await addRow("+ Add deposit");
  await pickLast("Deposit", V.deposit);
  await addRow("+ Add discount");
  await pickLast("Discount", V.senior);
  await page.fill("#plan-discount-from-0", "2026-09-01");
  await page.fill("#plan-discount-until-0", "2026-10-31");
  await page.getByLabel(/^Minimum bill/).fill("10");
  await shot("17-new-4-billing-filled", "step 4 deposits, discounts, budget billing, minimum bill");
  await addRow("+ Add discount");
  await pickLast("Discount", V.autopay);
  await page.fill("#plan-discount-from-1", "2026-11-01");
  await shot("18-new-4-discount-added", "second discount with offered from");
  await addRow("+ Add deposit");
  await click("Continue");
  await shot("19-new-4-billing-error", "empty deposit row refused");
  const depRemoves = page.locator('[data-array="plan-deposits"]').getByRole("button", { name: /Remove/ });
  await depRemoves.nth((await depRemoves.count()) - 1).click();
  await click("Continue");
  await page.getByRole("button", { name: "Publish plan" }).waitFor();
  await page.fill("#plan-starts", "2026-11-01");
  await page.setViewportSize({ width: 1440, height: 1500 });
  await page.screenshot({ path: `${OUT}/20-new-5-review-top${SUFFIX}.png` });
  say(`=== 20-new-5-review-top${SUFFIX}.png — Review, top of page`);
  await shot("21-new-5-review", "Review, full page ending in Save as draft · Publish plan");
  await click("Publish plan");
  await page.getByText("Residential City Plan published", { exact: true }).waitFor();
  await shot("22-new-6-published", "published");
  say("POSTED (publish):", JSON.stringify(posted[posted.length - 1]));

  // ── Run 2: save as draft (image 23) ─────────────────────────────────────
  await openNew();
  await page.getByLabel(/^Plan name/).fill("Residential City Plan");
  await page.getByLabel(/^Name|^Plan name/).first().fill(CONTRACT ? "Residential City Plan" : "Residential City Plan (draft)");
  await page.getByLabel(/^Code/).fill(CONTRACT ? "RCP" : "RCP-D");
  await click("Continue");
  for (const [service, schedule] of V.services) {
    await addRow("+ Add service");
    await pickLast("Service", service);
    await pickLast("Rate schedule", schedule);
  }
  await click("Continue");
  await page.getByRole("button", { name: "+ Add charge code" }).waitFor();
  await click("Continue");
  await page.getByRole("button", { name: "+ Add deposit" }).waitFor();
  await click("Continue");
  await click("Save as draft");
  await page.getByText(CONTRACT ? "Residential City Plan saved" : "Residential City Plan (draft) saved", { exact: true }).waitFor();
  await shot("23-new-6-saved-draft", "saved as a draft");
  say("POSTED (draft):", JSON.stringify(posted[posted.length - 1]));
}
await browser.close();
