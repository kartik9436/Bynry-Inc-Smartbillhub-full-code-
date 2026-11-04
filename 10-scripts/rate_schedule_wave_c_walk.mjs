// ── RATE SCHEDULES WAVE C — EVERY SERVICE × EVERY METHOD, WALKED AS A CLERK ──
// CR-157-BRC10 wave C. The PO's request, verbatim (2026-10-01):
//   *"we ahve 11 utility servcies and 5 types of rates - please do real
//   combination water flat , water tired, electricity flat, tired, time of use,
//   demand, peak - sewer, trash flat and tiered - all combinations for all 11
//   services and some combinations for custoemr types - do end to end web walk -
//   ensure they are saved corrected - do udpated on these rates scheduled and see
//   the ya re correcyly reflected in plans, one saved the action and imapct on
//   ther areas should be measured and it should work properly"*
//
// THE MATRIX IS BUILT FROM THE CODE, NOT FROM THE REQUEST. Which methods a
// service allows is answered by three places, and all three say *every method,
// every service*:
//   · `06-backend/apps/rating/services.py` `TARIFF_MODELS` (seven) — the save
//     path's `_validate_version_fields` takes `model` through
//     `_choice(payload, "model", TARIFF_MODELS, …)` and nothing pairs a model
//     with a service (`_validate_schedule_identity` checks only that the service
//     is enabled; the one service rule in a structure is `percent_of_service`'s
//     basis not being itself).
//   · `07-frontend/src/features/rating/RateScheduleWizard.tsx`
//     `structureOptions()` — the Structure dropdown is `TARIFF_MODELS` for every
//     service, with *Base only* shown disabled (`41-add-1-structure-open.png`).
//   · `RateScheduleThreeStep.tsx` — `rs-structure` takes `structureOptions`
//     unfiltered by `current.service`.
// So 11 services × 7 methods = 77 rows at *Every class*, plus customer-class
// rows. What a service DOES narrow is the UNIT (`scheduleUomOptions`) and the
// base charge code (`is_base` codes of that service), and both are taken here
// exactly as the screen offers them.
//
// FOR EVERY ROW, through the screens: Add (three steps) → list + View details
// (Overview · Rates · Plans · Audit) → database (`10-scripts/rswalk_probe.py`,
// which reads the tables and asks `selectors.in_force_version` /
// `pricing_inputs`, billing's one projection) → Change the rate from the 1st
// of next month → Fix an error on the version in force → the plan screen →
// a one-time bill preview before and after the change where an account takes
// the service, and billing's own projection for every row.
//
// ⚠ IT WRITES. It needs a PRIVATE database (`rswalk_db`, a copy of
// `sbh_six74_seeded` migrated to HEAD): it switches on the four services the
// seed leaves off, mints a base charge code for each service that has none,
// and re-points the `Residential Standard (Elm St)` plan's slot for a service at
// each row's schedule in turn (a plan edit with a reason — a clerk's act).
//
//   RSW_BASE   default http://127.0.0.1:8972      RSW_TENANT default brazosbend
//   RSW_ONLY   run rows whose key starts with this text
//   RSW_PHASE  matrix | drawings | all (default all)
//   RSW_OUT    default 08-qa/screens/rate-schedules-waveC-2026-10-01
//   RSW_STATE  where per-row results are kept so a run can resume
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createInterface } from "node:readline";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.RSW_BASE || "http://127.0.0.1:8972";
const T = process.env.RSW_TENANT || "brazosbend";
const EMAIL = process.env.RSW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.RSW_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.RSW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const OUT = process.env.RSW_OUT || "08-qa/screens/rate-schedules-waveC-2026-10-01";
const REF = "05-prototype/rate-schedules-2026-10-01/images";
const STATE = process.env.RSW_STATE || `${OUT}/rswalk_state.json`;
const ONLY = process.env.RSW_ONLY || "";
const PHASE = process.env.RSW_PHASE || "all";
const STAMP = process.env.RSW_STAMP || String(Date.now() % 100000);
mkdirSync(`${OUT}/matrix`, { recursive: true });

// ── dates ──────────────────────────────────────────────────────────────────
const iso = (d) => d.toISOString().slice(0, 10);
// RSW_TODAY pins the walk's "today" (YYYY-MM-DD): a re-measure that runs past
// midnight must judge the schedules against the day they were added.
const NOW = process.env.RSW_TODAY ? new Date(`${process.env.RSW_TODAY}T12:00:00Z`) : new Date();
const TODAY = new Date(Date.UTC(NOW.getUTCFullYear(), NOW.getUTCMonth(), NOW.getUTCDate()));
const FUTURE = new Date(Date.UTC(TODAY.getUTCFullYear(), TODAY.getUTCMonth() + 1, 1));
const DAY_BEFORE = new Date(FUTURE.getTime() - 86_400_000);
const AFTER_END = new Date(Date.UTC(FUTURE.getUTCFullYear(), FUTURE.getUTCMonth() + 1, 0));
const INSIDE_V1 = new Date(Date.UTC(TODAY.getUTCFullYear(), TODAY.getUTCMonth(), 15));
const INSIDE_V2 = new Date(Date.UTC(FUTURE.getUTCFullYear(), FUTURE.getUTCMonth(), 15));
const MONTH_START = new Date(Date.UTC(TODAY.getUTCFullYear(), TODAY.getUTCMonth(), 1));

// ── the matrix ─────────────────────────────────────────────────────────────
const SERVICES = [
  "electric", "water", "gas", "sewer", "trash", "storm_water", "solar",
  "broadband", "thermal_heat", "battery", "fire",
];
const METHODS = ["flat", "tiered", "time_of_use", "demand", "seasonal", "capacity", "percent_of_service"];
const LABEL = {
  flat: "Flat", tiered: "Tiered", time_of_use: "TOU", demand: "Demand",
  seasonal: "Seasonal", capacity: "Capacity", percent_of_service: "Percent",
};
// Real-world prices per service: [added, fixed (the typo corrected), changed].
const PRICE = {
  electric: ["0.1245", "0.1195", "0.1320"],
  water: ["4.4096", "4.0496", "4.6500"],
  gas: ["0.9800", "0.9500", "1.0400"],
  sewer: ["5.0000", "4.8000", "5.4000"],
  trash: ["15.0000", "14.5000", "16.0000"],
  storm_water: ["3.2500", "3.1000", "3.5000"],
  solar: ["0.0800", "0.0750", "0.0900"],
  broadband: ["49.9900", "45.9900", "54.9900"],
  thermal_heat: ["0.0650", "0.0600", "0.0700"],
  battery: ["4.0000", "3.8000", "4.4000"],
  fire: ["12.0000", "11.5000", "13.0000"],
};
const PERCENT = ["40", "38", "45"];
// Per-size minimums: the FIRST size gets MIN[0], the second MIN[1].
const MIN = {
  electric: ["80.00", "120.00"], water: ["15.00", "40.00"], trash: ["25.00", "60.00"],
};
const minFor = (service) => MIN[service] ?? ["10.00", "20.00"];
// The size the preview account's meter carries (AC-2026-00001) — the walk
// prices that one first so the minimum per size can be measured on a bill.
const ACCOUNT_SIZE = {
  electric: "E-1P-100", water: "W-58", trash: "CART-96",
  // Part 2 (`10-scripts/rswalk_billable_setup.py`): each asset added to the
  // preview account's unit carries the first size the walk's schedules price.
  gas: "G-250", fire: "FL-2", storm_water: "SW-APT", solar: "SOL-P1",
  thermal_heat: "TH-T5", battery: "BAT-5", broadband: "BB-100",
};
// The base code each Every-class row binds. Water binds the institutional code
// because the preview account is Institutional, so its base is on the bill.
const BASE_CODE = {
  electric: "BASE-E", water: "BASE-W-J70", gas: "BASE-G-WC", sewer: "BASE-S", trash: "BASE-T",
  storm_water: "BASE-SW-WC", solar: "BASE-SOL-WC", broadband: "BASE-BB-WC",
  thermal_heat: "BASE-TH-WC", battery: "BASE-BAT-WC", fire: "BASE-FIRE-WC",
};
// Codes a service lacks on the seed, minted once in setup (amount, classes).
const MINT = {
  "BASE-G-WC": ["gas", "9.5000", []],
  "BASE-SW-WC": ["storm_water", "7.2500", []],
  "BASE-SOL-WC": ["solar", "5.0000", []],
  "BASE-BB-WC": ["broadband", "20.0000", []],
  "BASE-TH-WC": ["thermal_heat", "11.0000", []],
  "BASE-BAT-WC": ["battery", "6.0000", []],
  "BASE-FIRE-WC": ["fire", "12.0000", []],
  "BASE-E-COM": ["electric", "25.0000", ["commercial"]],
};

const ROWS = [];
for (const service of SERVICES) {
  for (const model of METHODS) {
    ROWS.push({ key: `${service}-${model}-every`, service, model, klass: null, base: BASE_CODE[service] });
  }
}
// Customer-class rows — Residential and Commercial for water, electric and
// trash, and every other class the seed has, once. The eight drawn schedules
// (`01-list-all.png`) are among them so the View details drawings photograph
// a schedule of the same shape.
const CLASS_ROWS = [
  ["water", "flat", "Residential", "BASE-W"],
  ["water", "flat", "Commercial", "BASE-W-COM"],
  ["water", "tiered", "Residential", "BASE-W"], // W-RES
  ["water", "seasonal", "Commercial", "BASE-W-COM"], // W-SEAS
  ["electric", "flat", "Residential", "BASE-E"],
  ["electric", "flat", "Commercial", "BASE-E-COM"],
  ["electric", "time_of_use", "Residential", "BASE-E"], // E-TOU
  ["electric", "demand", "Commercial", "BASE-E-COM"], // E-DEM
  ["trash", "flat", "Residential", "BASE-T"],
  ["trash", "capacity", "Commercial", "BASE-T"],
  ["sewer", "percent_of_service", "Residential", "BASE-S"], // SEW-PCT
  ["electric", "demand", "Industrial", "BASE-E-IND"],
  ["gas", "flat", "Agricultural", "BASE-G-WC"],
  ["water", "tiered", "Institutional", "BASE-W-J70"],
  ["sewer", "flat", "Municipal", "BASE-S"],
  ["trash", "tiered", "Builder or developer", "BASE-T"],
  ["storm_water", "flat", "Government", "BASE-SW-WC"],
];
for (const [service, model, klass, base] of CLASS_ROWS) {
  ROWS.push({ key: `${service}-${model}-${klass.toLowerCase().replace(/\W+/g, "_")}`, service, model, klass, base });
}

// Which matrix row each drawn View-details schedule is photographed from.
const VIEW_DRAWINGS = {
  "water-tiered-residential": ["08", "W-RES"],
  "sewer-flat-every": ["12", "SEWER"],
  "battery-capacity-every": ["16", "BATT"],
  "electric-time_of_use-residential": ["20", "E-TOU"],
  "electric-demand-commercial": ["24", "E-DEM"],
  "water-seasonal-commercial": ["28", "W-SEAS"],
  "trash-capacity-every": ["32", "TRASH"],
  "sewer-percent_of_service-residential": ["36", "SEW-PCT"],
};
// Which row photographs which Add drawing (step 2 and step 3 of a method).
const ADD_DRAWINGS = {
  "electric-flat-every": ["44-add-2-pricing-flat", "53-add-3-review-flat"],
  "water-tiered-residential": ["45-add-2-pricing-tiered", "54-add-3-review-tiered"],
  "electric-time_of_use-residential": ["46-add-2-pricing-tou", "55-add-3-review-tou"],
  "electric-demand-commercial": ["47-add-2-pricing-demand", "56-add-3-review-demand"],
  "water-seasonal-commercial": ["48-add-2-pricing-seasonal", "57-add-3-review-seasonal"],
  "trash-capacity-every": ["49-add-2-pricing-capacity", "58-add-3-review-capacity"],
  "sewer-percent_of_service-residential": ["50-add-2-pricing-pct", "59-add-3-review-pct"],
};
const FIRST_ROW = "water-tiered-residential"; // 40–43, 60, 61, 62–66, 67–71

// ── state ──────────────────────────────────────────────────────────────────
const state = existsSync(STATE) ? JSON.parse(readFileSync(STATE, "utf8")) : { rows: {}, drawings: {} };
const save = () => writeFileSync(STATE, JSON.stringify(state, null, 1));

// ── the probe (database + billing's own projection) ────────────────────────
const probe = spawn("nice", ["/tmp/venv_a5c/bin/python", "10-scripts/rswalk_probe.py"], {
  env: { ...process.env, RSW_TENANT: T },
  stdio: ["pipe", "pipe", "ignore"],
});
const probeLines = createInterface({ input: probe.stdout });
const waiting = [];
probeLines.on("line", (line) => waiting.shift()?.(JSON.parse(line)));
const ask = (obj) => new Promise((resolve) => { waiting.push(resolve); probe.stdin.write(JSON.stringify(obj) + "\n"); });

// ── browser ────────────────────────────────────────────────────────────────
const browser = await chromium.launch({ executablePath: CHROME });
const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await context.newPage();
page.setDefaultTimeout(30_000);
const api = (path) => `${BASE}/api/${T}${path}`;
let csrf = "";
async function call(method, path, data) {
  const response = await page.request.fetch(api(path), {
    method,
    data,
    headers: { "X-CSRFToken": csrf, Referer: `${BASE}/` },
  });
  const text = await response.text();
  let body = null;
  try { body = JSON.parse(text); } catch { body = text.slice(0, 300); }
  return { status: response.status(), body };
}

async function signIn() {
  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60_000 }),
    page.click('button[type="submit"]'),
  ]);
  csrf = (await context.cookies()).find((c) => c.name === "csrftoken")?.value ?? "";
}

async function shot(name, reference) {
  await page.waitForTimeout(400);
  // The app scrolls inside `main`, so a full-page shot is only the viewport:
  // the window is made as tall as the content for the photograph, so the
  // whole screen — its bottom bar included — is beside the drawing.
  const tall = await page.evaluate(() => {
    const main = document.querySelector("main");
    return main ? main.scrollHeight + main.getBoundingClientRect().top + 24 : 1100;
  });
  await page.setViewportSize({ width: 1440, height: Math.max(1100, Math.ceil(tall)) });
  await page.waitForTimeout(200);
  await page.screenshot({ path: `${OUT}/${name}.built.png`, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1100 });
  if (reference) copyFileSync(`${REF}/${reference}`, `${OUT}/${name}.reference.png`);
}
const matrixShot = (row, what) =>
  page.screenshot({ path: `${OUT}/matrix/${row.key}-${what}.png`, fullPage: true });

// ── setup ──────────────────────────────────────────────────────────────────
async function setup() {
  for (const code of ["storm_water", "solar", "thermal_heat", "battery"]) {
    const r = await call("PUT", `/settings/services/${code}`, { enabled: true });
    if (r.status >= 300) console.log(`setup: enabling ${code} → ${r.status} ${JSON.stringify(r.body).slice(0, 200)}`);
  }
  const listed = (await call("GET", "/charges?q=BASE&per=100")).body.results ?? [];
  for (const [code, [service, amount, classes]] of Object.entries(MINT)) {
    if (listed.some((row) => row.code === code)) continue;
    const r = await call("POST", "/charges", {
      code, name: `${service} base (walk)`, charge_type: "recurring", service,
      amount_rule: "flat", amount, is_base: true, kind: "base", applies_to_customer_classes: classes,
    });
    console.log(`setup: minted ${code} → ${r.status}`);
  }
  // Image 51 draws a trash size the base code does not price: a code priced
  // for the three carts only, so a dumpster row reads *Not priced*.
  if (!listed.some((row) => row.code === "BASE-T-SZ")) {
    const r = await call("POST", "/charges", {
      code: "BASE-T-SZ", name: "Trash base by size (walk)", charge_type: "recurring", service: "trash",
      amount_rule: "flat", is_base: true, kind: "base", applies_to_customer_classes: [],
      size_amounts: [
        { size_class: "CART-35", amount: "2.0000" },
        { size_class: "CART-64", amount: "2.5000" },
        { size_class: "CART-96", amount: "3.0000" },
      ],
    });
    console.log(`setup: minted BASE-T-SZ → ${r.status} ${r.status >= 300 ? JSON.stringify(r.body).slice(0, 200) : ""}`);
  }
}

let DRAWING = false;

// ── the wizard ─────────────────────────────────────────────────────────────
const cell = (name) => page.locator(`[data-cell="${name}"]`);
const actions = () => page.locator("[data-wizard=actions]");
async function next() {
  await actions().getByRole("button", { name: /^Continue|^Next/ }).click();
}
async function offeredValues(locator) {
  return locator.locator("option:not([disabled])").evaluateAll((options) =>
    options.map((o) => o.value).filter(Boolean),
  );
}
async function waitOffered(locator) {
  for (let i = 0; i < 60; i += 1) {
    if ((await offeredValues(locator)).length > 0) return offeredValues(locator);
    await page.waitForTimeout(250);
  }
  return [];
}

async function fillDetails(row, name) {
  await page.fill("#rs-name", name);
  await waitOffered(page.locator("#rs-service"));
  await page.selectOption("#rs-service", row.service);
  await page.selectOption("#rs-structure", row.model);
  if (row.klass) await page.selectOption("#rs-class", { label: row.klass });
  const units = await waitOffered(page.locator("#rs-unit"));
  if ((await page.inputValue("#rs-unit")) === "" && units.length > 0) await page.selectOption("#rs-unit", units[0]);
  await page.fill("#rs-base-code", row.base);
  await page.getByRole("option", { name: new RegExp(`^${row.base}\\b`) }).first().click();
}

/** Two base rows (the account's size first where one exists), each with its
 *  minimum, and the method's usage pricing. Returns what was typed. */
async function fillPricing(row) {
  const typed = { sizes: [], price: PRICE[row.service][0] };
  const addBase = () =>
    page.locator("[data-step=pricing]").getByRole("button", { name: "+ Add row" }).first();
  const mins = minFor(row.service);
  for (let i = 0; i < 2; i += 1) {
    if (await addBase().isDisabled().catch(() => true)) break;
    await addBase().click();
    const select = cell(`size-${i}`);
    if ((await select.count()) === 0) break; // an unsized service: *All sizes*
    const values = await offeredValues(select);
    const wanted = i === 0 && values.includes(ACCOUNT_SIZE[row.service]) ? ACCOUNT_SIZE[row.service] : values[0];
    await select.selectOption(wanted);
    await cell(`minimum-${i}`).fill(mins[i]);
    typed.sizes.push({ size: wanted, minimum: mins[i] });
  }
  const P = PRICE[row.service][0];
  const addUsage = () =>
    page.locator("[data-step=pricing]").getByRole("button", { name: "+ Add row" }).nth(1);
  switch (row.model) {
    case "flat":
      await cell("price-0").fill(P);
      break;
    case "tiered": {
      await cell("tier-to-0").fill("5");
      await cell("tier-price-0").fill(P);
      await addUsage().click();
      typed.tier2 = (Number(P) * 1.25).toFixed(4);
      await cell("tier-price-1").fill(typed.tier2);
      break;
    }
    case "time_of_use":
      await addUsage().click();
      await cell("window-0").selectOption("On-peak");
      await cell("days-0").selectOption("weekday");
      await cell("starts-0").fill("14:00");
      await cell("ends-0").fill("20:00");
      typed.peak = (Number(P) * 1.5).toFixed(4);
      await cell("window-price-0").fill(typed.peak);
      await addUsage().click();
      await cell("window-1").selectOption("Off-peak");
      await cell("days-1").selectOption("weekday");
      await cell("starts-1").fill("20:00");
      await cell("ends-1").fill("14:00");
      await cell("window-price-1").fill(P);
      break;
    case "demand":
      await cell("energy_rate_per_kwh").fill(P);
      await cell("demand_rate_per_kw").fill("11.00");
      break;
    case "seasonal":
      await addUsage().click();
      await cell("season-0").fill("All year");
      await cell("season-start-0").fill(`${TODAY.getUTCFullYear()}-01-01`);
      await cell("season-end-0").fill(`${TODAY.getUTCFullYear()}-12-31`);
      await cell("season-price-0").fill(P);
      break;
    case "capacity":
      await cell("price-0").fill(P);
      break;
    case "percent_of_service": {
      await page.locator("#percent-value").fill(PERCENT[0]);
      const basis = await waitOffered(page.locator("#percent-basis"));
      const pick = basis.includes("water") && row.service !== "water" ? "water" : basis[0];
      if (pick) await page.selectOption("#percent-basis", pick);
      typed.basis = pick ?? null;
      if (await page.locator("#percent-unit-price").count()) {
        await page.locator("#percent-unit-price").fill(P);
        typed.unitPrice = P;
      }
      typed.price = PERCENT[0];
      break;
    }
  }
  return typed;
}

/** The one figure Change and Fix edit, per method. */
async function editFigure(row, value) {
  switch (row.model) {
    case "flat":
    case "capacity":
      return cell("price-0").fill(value);
    case "tiered":
      return cell("tier-price-0").fill(value);
    case "time_of_use":
      return cell("window-price-1").fill(value);
    case "demand":
      return cell("energy_rate_per_kwh").fill(value);
    case "seasonal":
      return cell("season-price-0").fill(value);
    case "percent_of_service":
      return page.locator("#percent-value").fill(value);
  }
}
const figure = (row, which) =>
  row.model === "percent_of_service" ? PERCENT[which] : PRICE[row.service][which];

async function visibleProblem() {
  const alerts = await page.locator("[role=alert], [data-wizard=blocked], .text-danger-700").allInnerTexts().catch(() => []);
  return alerts.map((s) => s.replace(/\s+/g, " ").trim()).filter(Boolean).join(" | ").slice(0, 400);
}

async function findSchedule(name) {
  const r = await call("GET", `/rate-schedules?q=${encodeURIComponent(name)}&per=50`);
  return (r.body.results ?? []).find((one) => one.name === name) ?? null;
}

// ── the checks ─────────────────────────────────────────────────────────────
const sameMoney = (a, b) => a != null && b != null && Number(a).toFixed(4) === Number(b).toFixed(4);

function methodRowsOk(row, version, typed, price) {
  switch (row.model) {
    case "flat":
      return version.tiers.length === 1 && sameMoney(version.tiers[0].unit_price, price) && version.tiers[0].to_qty === null;
    case "tiered":
      return version.tiers.length === 2 && sameMoney(version.tiers[0].unit_price, price) && Number(version.tiers[0].to_qty) === 5;
    case "time_of_use":
      return version.windows.length === 2 && version.windows.some((w) => w.channel === "tou_on") && version.windows.some((w) => w.channel === "tou_off" && sameMoney(w.unit_price, price));
    case "demand":
      return version.demand.length === 1 && sameMoney(version.demand[0].energy_rate_per_kwh, price) && sameMoney(version.demand[0].demand_rate_per_kw, "11");
    case "seasonal":
      return version.seasons.length === 1 && version.tiers.some((t) => sameMoney(t.unit_price, price));
    case "capacity":
      return version.capacity.length === 1 && sameMoney(version.capacity[0].rate_per_unit, price);
    case "percent_of_service":
      return true; // the percent lives on the version's structure — read from the API below
  }
  return false;
}

function sizeRowsOk(version, typed) {
  if (typed.sizes.length === 0) return version.size_rows.length === 0;
  return typed.sizes.every((s) => version.size_rows.some((r) => r.size_class === s.size && sameMoney(r.minimum_bill, s.minimum)));
}

// ── the bill ───────────────────────────────────────────────────────────────
// The preview account and its meters (sizes recorded: W-58, E-1P-100, CART-96).
const ACCOUNT = { no: "AC-2026-00001", id: "01a0f601-62d1-7ef1-841e-5f4d885ef140" };
const ELM_PLAN = "01a0f601-5b62-73c9-8001-3745791af320";
// Part 2: the preview account's meters carry COMMITTED reads on 09-30, 10-31 and
// 11-30 (total, on-peak, off-peak, peak demand — `rswalk_billable_setup.py`),
// so October and November each bill their own month and nothing is typed.
// Per meter and month: total, on-peak, off-peak, peak kW.
const METER_QTY = {
  "E-55120": { before: [500, 150, 350, 12.5], after: [600, 180, 420, 14.0] },
  "W-10442": { before: [1, 0.4, 0.6, 1.2], after: [2, 0.8, 1.2, 1.5] },
  "W-10443": { before: [5, 2, 3, 1.3], after: [10, 4, 6, 1.6] },
  "G-WC-1": { before: [40, 12, 28, 2.5], after: [50, 15, 35, 3.0] },
  "S-WC-1": { before: [4, 1, 3, 0.6], after: [5, 2, 3, 0.7] },
};
// A line that names no meter belongs to the service's only one.
const SERVICE_METER = { electric: "E-55120", gas: "G-WC-1", sewer: "S-WC-1" };
// The base each COUNTED service's walk schedules bind (BASE-T, BASE-FIRE-WC),
// per asset — folded into the service's one line when no base line prints.
const COUNTED_BASE = { trash: 3, fire: 12 };
const PREVIEWABLE = new Set(SERVICES);

const SEWER_FLAT = "01a0f88d-2f81-7ebe-a5eb-82ea503050ab"; // WC C1 sewer Flat Every class
async function pointPlanAt(row, tariffId) {
  const plan = (await call("GET", `/plans/${ELM_PLAN}`)).body;
  const services = plan.rate_schedules
    .filter((b) => b.service !== row.service)
    .map((b) => ({ service: b.service, tariff: b.tariff_id }));
  services.push({ service: row.service, tariff: tariffId });
  // Water priced as a percent of electric puts no usage charge on water, so the
  // seeded sewer schedule (a percent of WATER usage) has nothing to take a
  // percent of and refuses the whole bill. Sewer is read from its own meter on
  // this account, so its slot prices that meter for this one row.
  if (row.service === "water" && row.model === "percent_of_service") {
    const sewer = services.find((b) => b.service === "sewer");
    if (sewer) sewer.tariff = SEWER_FLAT;
  }
  return call("PATCH", `/plans/${ELM_PLAN}`, { reason: `Wave C walk: ${row.key} prices ${row.service}`, services });
}

async function preview(which) {
  const start = which === "before" ? MONTH_START : FUTURE;
  const end = which === "before" ? DAY_BEFORE : AFTER_END;
  return call("POST", "/billing/one-time/preview", {
    account_id: ACCOUNT.id, kind: "interim", period_start: iso(start), period_end: iso(end),
    bill_date: iso(new Date(end.getTime() + 86_400_000)), due_days: 20,
  });
}

/** What the clerk would see priced for this row's service, and whether it is
 *  ONE version (the right one), the right rate, and the minimum per size. */
const BASIS_QTY = { before: { water: 6, electric: 500, gas: 40, sewer: 4 }, after: { water: 12, electric: 600, gas: 50, sewer: 5 } };
function judgeBill(row, body, expectFrom, price, sizes, tier2, which, typed) {
  if (!body || typeof body !== "object" || !body.rates) {
    const detail = String(body?.params?.detail ?? "");
    if (/NO per-window quantity|no peak-demand read/.test(detail)) {
      // Part 2: every METERED service on the preview account has on-peak,
      // off-peak and peak-demand reads, so this refusal now only reaches a
      // service the tenant counts or shares — which no read can ever reach.
      return { ok: false, expected: "—", got: "refused", note: "DEF-RAT-9015: a counted or shared service has no meter reads, so time of use and demand can never bill; the save now refuses them" };
    }
    if (/no tariff model plugin registered for 'seasonal'/.test(detail)) {
      return { ok: false, expected: "—", got: "refused", note: "REGRESSION: billing refuses a seasonal schedule again — the seasonal model was registered on 2026-10-01 (DEF-RAT-8832, OQ-234 closed 2026-09-07)" };
    }
    return { ok: false, expected: "—", got: "refused", note: `refused: ${body?.message_key ?? ""} ${body?.params?.sentence ?? JSON.stringify(body).slice(0, 160)}` };
  }
  const rates = body.rates.filter((r) => r.service === row.service);
  const versionLabels = [...new Set(rates.flatMap((r) => (r.versions ?? []).map((v) => v.from)))];
  const lines = (body.bill?.groups ?? []).flatMap((g) => g.lines).filter((l) => l.service === row.service);
  const got = lines.reduce((sum, l) => sum + Number(l.amount), 0);
  const svc = (body.services ?? []).find((s) => s.service === row.service);
  const out = {
    status: svc?.status ?? "—",
    versions: versionLabels,
    oneVersion: versionLabels.length === 1 && versionLabels[0] === expectFrom,
    got: got.toFixed(2),
    waiting: body.waiting_for ? `${body.waiting_for.reason}:${body.waiting_for.service_code}` : null,
  };
  if (out.status === "not_in_service" || out.status === "not_taken") {
    // The preview account has no meter (sewer, gas, fire) or does not take the
    // service: nothing to price, and the bill says so rather than a $0.00 line.
    return { ...out, ok: null, expected: "—", note: `the account's ${row.service} is ${out.status.replace(/_/g, " ")}` };
  }
  const round2 = (x) => Math.round(x * 100) / 100;
  // A meter with no recorded size (the sewer meter) has no minimum to meet.
  const sizeMin = sizes.find((s) => s.size === ACCOUNT_SIZE[row.service])?.minimum;
  const floor = sizeMin ? Number(sizeMin) : 0;
  const perMeter = {};
  for (const l of lines) (perMeter[l.asset_label ?? "_"] ??= []).push(l);
  let expected = 0;
  let known = true;
  let percentCounted = false;
  const checks = [];
  for (const meterLines of Object.values(perMeter)) {
    let priced = null;
    let pricedLine = null;
    if (["flat", "tiered", "seasonal"].includes(row.model)) {
      pricedLine = meterLines.find((l) => l.charge === "usage")
        // Part 2: a SUMMED capacity (storm water ERU, thermal tons, solar and
        // battery kW, broadband Mbps) prices as one `per_asset` line whose
        // quantity is the total; a counted fire line prints as the first
        // group's line at its size's price.
        ?? meterLines.find((l) => l.charge === "per_asset" && !(l.breakdown ?? []).some((b) => b.price_each != null))
        ?? meterLines.find((l) => l.charge !== "minimum" && (l.breakdown ?? []).length > 0 && sameMoney(l.rate, price));
      if (pricedLine) {
        const q = Number(pricedLine.quantity);
        const first = row.model === "tiered" ? Math.min(q, 5) : q;
        const rest = row.model === "tiered" ? Math.max(q - 5, 0) : 0;
        priced = round2(first * Number(price)) + round2(rest * Number(tier2 ?? 0));
        // A tiered line states its rate as the word *tiered*; its amount is checked.
        // (A counted service's one line states price + base as its rate, so
        // only a usage line's rate is the schedule's price.)
        if (pricedLine.charge === "usage" && !Number.isNaN(Number(pricedLine.rate))) checks.push(sameMoney(pricedLine.rate, price));
      } else {
        // A counted service (trash) prices per cart: one `per_asset` line whose
        // breakdown states each size's count and its price each.
        pricedLine = meterLines.find((l) => l.charge === "per_asset" && (l.breakdown ?? []).length > 0) ?? null;
        if (pricedLine) {
          priced = pricedLine.breakdown.reduce((s, b) => s + round2(Number(b.count ?? 1) * Number(b.price_each)), 0);
          checks.push(pricedLine.breakdown.every((b) => sameMoney(b.price_each, price)));
        }
      }
    } else if (row.model === "time_of_use" || row.model === "demand") {
      // Each window (or the energy and the peak kW) priced on its own and
      // rounded per line, as the engine does; the lines are checked as a sum.
      const meter = meterLines[0]?.asset_label ?? SERVICE_METER[row.service];
      const q = METER_QTY[meter]?.[which];
      const usage = meterLines.filter((l) => l.charge === "usage");
      if (q && usage.length > 0) {
        priced = row.model === "time_of_use"
          ? round2(q[1] * Number(typed.peak)) + round2(q[2] * Number(price))
          : round2(q[0] * Number(price)) + round2(q[3] * 11);
        pricedLine = { synthetic: true, breakdown: [] };
        meterLines.splice(0, meterLines.length, ...meterLines.filter((l) => !usage.includes(l)));
      }
    } else if (row.model === "capacity") {
      pricedLine = meterLines.find((l) => l.charge !== "minimum" && sameMoney(l.rate, price));
      if (pricedLine) priced = round2(Number(pricedLine.quantity) * Number(price));
    } else if (row.model === "percent_of_service") {
      pricedLine = meterLines.find((l) => l.charge === "percent");
      const basisQty = BASIS_QTY[which]?.[typed.basis];
      if (pricedLine && basisQty != null) {
        const q = (Number(price) / 100) * basisQty;
        checks.push(Math.abs(Number(pricedLine.quantity) - q) < 0.0001);
        // A percent of another service is ONE account-level figure, so it is
        // expected once however many meters the service has (DEF-BIL-9014).
        priced = percentCounted ? 0 : round2(q * Number(typed.unitPrice ?? pricedLine.rate));
        percentCounted = true;
      }
    }
    if (pricedLine == null || priced == null) {
      known = false;
      continue;
    }
    // A counted service (trash) folds its per-cart base INTO the priced line:
    // `breakdown` names each size's count and base, so it is added here.
    // (Only a `per_asset` line folds it; fire prints its base on a line of its
    // own beside a breakdown that merely names it.)
    const folds = pricedLine.charge === "per_asset" || pricedLine.charge === "percent";
    for (const b of folds ? pricedLine.breakdown ?? [] : []) {
      if (b.base_priced && b.base_each != null) priced += Number(b.count ?? 1) * Number(b.base_each);
    }
    // A COUNTED service (trash carts, fire lines) prints ONE line per service
    // with its base folded in and no breakdown (`DEF-BIL-8151`, PO "per
    // service"): with no base line beside it, the service's base is in it.
    const noBaseLine = !meterLines.some((l) => l !== pricedLine && l.charge === "base");
    if (folds && (pricedLine.breakdown ?? []).length === 0 && noBaseLine && COUNTED_BASE[row.service] != null) {
      priced += COUNTED_BASE[row.service];
    }
    const base = meterLines
      .filter((l) => l !== pricedLine && l.charge !== "minimum")
      .reduce((s, l) => s + Number(l.amount), 0);
    expected += Math.max(priced + base, floor);
  }
  if (known && lines.length > 0) {
    out.expected = expected.toFixed(2);
    out.ok = out.oneVersion && checks.every(Boolean) && Math.abs(expected - got) < 0.005;
    if (!out.ok && row.model === "percent_of_service" && Object.keys(perMeter).length > 1) {
      out.note = `DEF-BIL-9014: the percent is charged on each of ${Object.keys(perMeter).length} meters; expected once`;
    }
    if (!out.ok && Math.abs(got - expected - 0.01) < 0.005 && lines.some((l) => l.charge === "minimum")) {
      out.note = "DEF-RAT-9013: one cent over the minimum — the lines round on their own, the top-up is measured unrounded (finance ruling)";
    }
  } else {
    out.expected = "—";
    out.ok = out.oneVersion && !out.waiting && lines.length > 0;
    out.note = "figure not derived for this shape on this account; one version and a priced line checked";
  }
  return out;
}

// ── one row ────────────────────────────────────────────────────────────────
async function walkRow(row) {
  const name = `WC ${STAMP} ${row.service} ${LABEL[row.model]} ${row.klass ?? "Every class"}`;
  const r = { key: row.key, service: row.service, model: row.model, klass: row.klass ?? "Every class", name, notes: [] };
  // The drawings pass walks its own schedules into its own bucket, so the
  // photographs never overwrite a matrix row's measurements.
  (DRAWING ? (state.drawingRows ??= {}) : state.rows)[row.key] = r;
  const drawn = DRAWING ? ADD_DRAWINGS[row.key] : null;
  const first = DRAWING && row.key === FIRST_ROW;

  // 1 · ADD through the three steps
  try {
    await page.goto(`${BASE}/${T}/plans-rates/rates/new`, { waitUntil: "networkidle" });
    await page.locator("[data-step=details]").waitFor();
    if (first) {
      await next();
      await page.getByText("Add a name.").first().waitFor();
      await shot("43-add-1-errors", "43-add-1-errors.png");
    }
    await fillDetails(row, name);
    if (first) {
      await shot("40-add-1-details", "40-add-1-details.png");
      await page.locator("#rs-structure").focus();
      await shot("41-add-1-structure-open", "41-add-1-structure-open.png");
      await page.locator("#rs-base-code").click();
      await page.waitForTimeout(300);
      await shot("42-add-1-code-picker", "42-add-1-code-picker.png");
      await page.keyboard.press("Escape");
    }
    await next();
    await page.locator("[data-step=pricing]").waitFor({ timeout: 10_000 }).catch(async () => {
      throw new Error(`step 1 refused: ${await visibleProblem()}`);
    });
    r.typed = await fillPricing(row);
    await matrixShot(row, "1-pricing");
    if (drawn) await shot(drawn[0], `${drawn[0]}.png`);
    await next();
    await page.locator("[data-step=review]").waitFor({ timeout: 10_000 }).catch(async () => {
      throw new Error(`step 2 refused: ${await visibleProblem()}`);
    });
    const create = actions().getByRole("button", { name: "Create rate schedule" });
    if (first) {
      await create.click();
      await page.getByText("Pick a date.").first().waitFor();
      await shot("60-add-3-date-error", "60-add-3-date-error.png");
    }
    await page.locator("#rs-effective-from").fill(iso(TODAY));
    if (drawn) await shot(drawn[1], `${drawn[1]}.png`);
    await create.click();
    await page.getByText("New schedule created.").first().waitFor({ timeout: 20_000 }).catch(async () => {
      throw new Error(`create refused: ${await visibleProblem()}`);
    });
    if (first) await shot("61-add-3-saved", "61-add-3-saved.png");
    const card = await findSchedule(name);
    if (!card) throw new Error("saved, but the list does not hold it");
    r.id = card.id;
    r.add = card.structure === row.model && card.service === row.service && card.status === "active";
    if (!r.add) r.notes.push(`list row: structure ${card.structure} service ${card.service} status ${card.status}`);
  } catch (error) {
    r.add = false;
    r.notes.push(`ADD: ${String(error.message ?? error).split("\n")[0]}`);
    await matrixShot(row, "1-failed").catch(() => {});
    save();
    return r;
  }

  // the list row as the clerk sees it, and the four tabs
  try {
    await page.goto(`${BASE}/${T}/plans-rates/rates?q=${encodeURIComponent(name)}`, { waitUntil: "networkidle" });
    const listRow = page.getByRole("row").filter({ hasText: name });
    const text = (await listRow.first().innerText({ timeout: 10_000 })).replace(/\s+/g, " ");
    r.listText = text;
    const classWord = row.klass ?? "Every class";
    r.listOk = text.includes(classWord) && text.includes(row.base);
    if (!r.listOk) r.notes.push(`list row reads "${text.slice(0, 160)}"`);
    for (const tab of ["overview", "rates", "plans", "audit"]) {
      await page.goto(`${BASE}/${T}/plans-rates/rates/${r.id}?tab=${tab}`, { waitUntil: "networkidle" });
      await page.getByRole("tab", { selected: true }).waitFor();
      const failed = await page.getByText(/couldn.t load|something went wrong/i).count();
      if (failed) r.notes.push(`${tab} tab shows a load failure`);
    }
  } catch (error) {
    r.listOk = false;
    r.notes.push(`LIST/VIEW: ${String(error.message ?? error).split("\n")[0]}`);
  }

  // 2 · the database after Add
  const P = [figure(row, 0), figure(row, 1), figure(row, 2)];
  try {
    const facts = await ask({ op: "facts", tariff_id: r.id });
    const live = facts.versions;
    const v = live[0];
    const inForce = await ask({ op: "in_force", tariff_id: r.id, dates: [iso(INSIDE_V1)], size: r.typed.sizes[0]?.size ?? null });
    const one = inForce[iso(INSIDE_V1)];
    r.db = live.length === 1 && v.effective_from === iso(TODAY) && v.effective_to === null && v.model === row.model
      && methodRowsOk(row, v, r.typed, P[0]) && sizeRowsOk(v, r.typed)
      && one.in_force_versions.length === 1 && one.in_force_version === v.id;
    if (row.model === "percent_of_service") {
      const detail = (await call("GET", `/rate-schedules/${r.id}`)).body;
      const pct = detail.current_version?.structure?.percent;
      r.db = r.db && sameMoney(pct, P[0]);
    }
    if (!r.db) r.notes.push(`DB after add: ${JSON.stringify({ versions: live.length, from: v?.effective_from, to: v?.effective_to, model: v?.model, methodRows: methodRowsOk(row, v, r.typed, P[0]), sizes: sizeRowsOk(v, r.typed), inForce: one?.in_force_versions?.length, size_rows: v?.size_rows })}`.slice(0, 400));
    r.v1 = v?.id;
  } catch (error) {
    r.db = false;
    r.notes.push(`DB: ${error}`);
  }

  // 3a · CHANGE THE RATE from the 1st of next month
  try {
    await page.goto(`${BASE}/${T}/plans-rates/rates/${r.id}/edit`, { waitUntil: "networkidle" });
    await page.locator("[data-step=details]").waitFor();
    // DEF-RAT-8835 — the Edit's base code field shows the schedule's own code.
    const shownCode = await page.inputValue("#rs-base-code");
    if (shownCode !== row.base) r.notes.push(`EDIT: base charge code field reads "${shownCode}", not ${row.base}`);
    if (first) await shot("62-edit-change-1", "62-edit-change-1.png");
    await next();
    await page.locator("[data-step=pricing]").waitFor();
    await editFigure(row, P[2]);
    if (first) await shot("63-edit-change-2", "63-edit-change-2.png");
    await next();
    await page.locator("[data-step=review]").waitFor();
    await page.locator("#rs-effective-from").fill(iso(FUTURE));
    const commit = actions().getByRole("button", { name: "Create new version" });
    if (first) {
      await commit.click();
      await page.getByText("Add what changed.").first().waitFor();
      await shot("65-edit-change-reason-error", "65-edit-change-reason-error.png");
    }
    await page.locator("#rs-what-changed").fill(`Board approved ${P[2]} from ${iso(FUTURE)}`);
    if (first) await shot("64-edit-change-3", "64-edit-change-3.png");
    await commit.click();
    await page.getByText("saved as new version.").first().waitFor({ timeout: 20_000 }).catch(async () => {
      throw new Error(`change refused: ${await visibleProblem()}`);
    });
    if (first) await shot("66-edit-change-saved", "66-edit-change-saved.png");
    await verifyChange(row, r, false);
  } catch (error) {
    r.change = false;
    r.notes.push(`CHANGE: ${String(error.message ?? error).split("\n")[0]}`);
    await matrixShot(row, "3-change-failed").catch(() => {});
  }

  // 3b · FIX AN ERROR on the version in force
  try {
    await page.goto(`${BASE}/${T}/plans-rates/rates/${r.id}/edit`, { waitUntil: "networkidle" });
    await page.locator("[data-step=details]").waitFor();
    await page.getByText("Fix an error", { exact: true }).click();
    if (first) await shot("67-edit-correct-1", "67-edit-correct-1.png");
    await next();
    await page.locator("[data-step=pricing]").waitFor();
    await editFigure(row, P[1]);
    if (first) await shot("68-edit-correct-2", "68-edit-correct-2.png");
    await next();
    await page.locator("[data-step=review]").waitFor();
    const commit = actions().getByRole("button", { name: "Save correction" });
    if (first) {
      await commit.click();
      await page.getByText("Add a reason.").first().waitFor();
      await shot("70-edit-correct-reason-error", "70-edit-correct-reason-error.png");
    }
    await page.locator("#rs-reason").fill(`Typed ${P[0]} for ${P[1]}`);
    if (first) await shot("69-edit-correct-3", "69-edit-correct-3.png");
    await commit.click();
    await page.getByText("corrected.").first().waitFor({ timeout: 20_000 }).catch(async () => {
      throw new Error(`fix refused: ${await visibleProblem()}`);
    });
    if (first) await shot("71-edit-correct-saved", "71-edit-correct-saved.png");
    const facts = await ask({ op: "facts", tariff_id: r.id });
    const original = facts.versions.find((v) => v.id === r.v1);
    const fixed = facts.versions.find((v) => v.correction_reason === `Typed ${P[0]} for ${P[1]}`);
    const v2 = facts.versions.find((v) => v.id === r.v2);
    r.fixedOn = fixed ? (fixed.effective_from === iso(TODAY) ? "v1" : fixed.effective_from) : null;
    r.fix = Boolean(original && fixed) && original.superseded_by === fixed.id
      && fixed.effective_from === original.effective_from && fixed.effective_to === original.effective_to
      && (row.model === "percent_of_service" || methodRowsOk(row, fixed, r.typed, P[1]))
      && (!v2 || (v2.superseded_by === null && v2.effective_from === iso(FUTURE)));
    if (!r.fix) r.notes.push(`FIX: ${JSON.stringify({ original: original && { sup: original.superseded_by, from: original.effective_from, to: original.effective_to }, fixed: fixed && { from: fixed.effective_from, to: fixed.effective_to, rows: methodRowsOk(row, fixed, r.typed, P[1]) }, v2: v2 && { sup: v2.superseded_by, from: v2.effective_from } })}`.slice(0, 400));
    const answers = await ask({ op: "in_force", tariff_id: r.id, dates: [iso(INSIDE_V1), iso(INSIDE_V2)], size: r.typed.sizes[0]?.size ?? null });
    r.oneVersion = Object.values(answers).every((a) => a.in_force_versions.length === 1)
      && answers[iso(INSIDE_V1)].in_force_version === fixed?.id
      && answers[iso(INSIDE_V2)].in_force_version === r.v2
      && answers[iso(INSIDE_V1)].pricing?.version_id === fixed?.id
      && answers[iso(INSIDE_V2)].pricing?.version_id === r.v2;
    // The minimum billing's projection hands the engine for the first size.
    if (r.typed.sizes.length > 0) {
      const m1 = answers[iso(INSIDE_V1)].pricing?.minimum_bill;
      const m2 = answers[iso(INSIDE_V2)].pricing?.minimum_bill;
      r.minimumToBilling = sameMoney(m1, r.typed.sizes[0].minimum) && sameMoney(m2, r.typed.sizes[0].minimum);
      if (!r.minimumToBilling) r.notes.push(`minimum to billing: v1 ${m1} v2 ${m2} expected ${r.typed.sizes[0].minimum}`);
    }
    r.fixedId = fixed?.id;
  } catch (error) {
    r.fix = false;
    r.notes.push(`FIX: ${String(error.message ?? error).split("\n")[0]}`);
    await matrixShot(row, "3-fix-failed").catch(() => {});
  }

  // history — the Audit tab names both changes; audit_log holds them
  try {
    await page.goto(`${BASE}/${T}/plans-rates/rates/${r.id}?tab=audit`, { waitUntil: "networkidle" });
    await page.getByRole("tab", { selected: true }).waitFor();
    const text = (await page.locator("main").innerText()).replace(/\s+/g, " ");
    const sawChange = text.includes(`Board approved ${P[2]}`);
    const sawFix = text.includes(`Typed ${P[0]} for ${P[1]}`);
    const audit = await ask({ op: "audit", tariff_id: r.id });
    r.history = sawChange && sawFix && (audit.count ?? 0) >= 3;
    if (!r.history) r.notes.push(`HISTORY: audit tab change=${sawChange} fix=${sawFix}; audit_log rows ${audit.count ?? audit.error}`);
    await page.goto(`${BASE}/${T}/plans-rates/rates/${r.id}?tab=rates`, { waitUntil: "networkidle" });
    await page.getByRole("tab", { selected: true }).waitFor();
    await matrixShot(row, "2-rates-after");
  } catch (error) {
    r.history = false;
    r.notes.push(`HISTORY: ${String(error.message ?? error).split("\n")[0]}`);
  }

  if (!DRAWING) await impact(row, r);
  save();
  return r;
}

/** 3a's database half: the old version ends the day before, the new one starts
 *  on the date, nothing overlaps, and billing picks each on its own dates.
 *  `after_fix` is true on a re-check, when v1 has since been corrected. */
async function verifyChange(row, r, afterFix) {
  const P = [figure(row, 0), figure(row, 1), figure(row, 2)];
  const facts = await ask({ op: "facts", tariff_id: r.id });
  const v1 = afterFix
    ? facts.versions.find((v) => v.effective_from === iso(TODAY) && !v.superseded_by)
    : facts.versions.find((v) => v.id === r.v1);
  const v2 = facts.versions.find((v) => v.effective_from === iso(FUTURE) && !v.superseded_by);
  const dates = [iso(INSIDE_V1), iso(DAY_BEFORE), iso(FUTURE), iso(INSIDE_V2)];
  const answers = await ask({ op: "in_force", tariff_id: r.id, dates, size: r.typed.sizes[0]?.size ?? null });
  const onlyOne = dates.every((d) => answers[d].in_force_versions.length === 1);
  r.change = Boolean(v1 && v2) && v1.effective_to === iso(DAY_BEFORE) && v2.effective_to === null
    && onlyOne
    && answers[iso(INSIDE_V1)].in_force_version === v1.id && answers[iso(DAY_BEFORE)].in_force_version === v1.id
    && answers[iso(FUTURE)].in_force_version === v2.id && answers[iso(INSIDE_V2)].in_force_version === v2.id
    && Boolean(v2.change_reason?.startsWith("Board approved"));
  if (v2 && row.model !== "percent_of_service") r.change = r.change && methodRowsOk(row, v2, r.typed, P[2]);
  if (v2) r.change = r.change && sizeRowsOk(v2, r.typed);
  r.notes = r.notes.filter((n) => !n.startsWith("CHANGE:"));
  if (!r.change) r.notes.push(`CHANGE: ${JSON.stringify({ v1to: v1?.effective_to, v2: !!v2, v2rows: v2 ? methodRowsOk(row, v2, r.typed, P[2]) : null, v2sizes: v2?.size_rows, onlyOne, picks: dates.map((d) => answers[d].in_force_version === v1?.id ? "v1" : answers[d].in_force_version === v2?.id ? "v2" : answers[d].in_force_version) })}`.slice(0, 400));
  r.v2 = v2?.id;
}

// The Elm St plan's own schedules, as seeded — each row's slot is put back to
// its service's seeded schedule (or removed) once the row is measured, so one
// row's schedule never prices another row's bill (a sized gas schedule left on
// the plan is a gas fact on every later bill).
const ORIGINAL = {
  electric: "01a0f601-5b6a-74cd-92c9-08206350f2d5",
  water: "01a0f601-5b65-7915-a5fb-617778203e0e",
  // Part 2: the seeded gas schedule prices in therm and the gas meter added to
  // the preview account reads ccf, so a therm schedule on the plan refuses
  // EVERY bill on the account (BR-RAT-038 — correctly). The baseline gas slot is
  // the walk's own ccf schedule instead.
  gas: "01a0f88a-96ce-710b-814d-f1d13cde9cf0", // WC C1 gas Flat Every class
  sewer: "01a0f601-5b70-7ab8-83de-7e5ab764a2c6",
  trash: "01a0f601-5b6d-70f0-a2dd-29a374f55352",
  broadband: "01a0f601-5b7b-7126-9465-5d0e97e1eefd",
  fire: "01a0f601-5b77-70ba-9064-65d0953aa59b",
};
async function restorePlan() {
  const services = Object.entries(ORIGINAL).map(([service, tariff]) => ({ service, tariff }));
  const plan = (await call("GET", `/plans/${ELM_PLAN}`)).body;
  const now = Object.fromEntries(plan.rate_schedules.map((b) => [b.service, b.tariff_id]));
  if (Object.keys(now).length === services.length && services.every((s) => now[s.service] === s.tariff)) return;
  return call("PATCH", `/plans/${ELM_PLAN}`, { reason: "Wave C walk: the plan's own schedules back", services });
}

/** 4 · IMPACT on the plan screen and on a one-time bill. */
async function impact(row, r) {
  const P = [figure(row, 0), figure(row, 1), figure(row, 2)];
  const name = r.name;
  r.notes = r.notes.filter((n) => !/^(BILL|PLAN|IMPACT)/.test(n));
  try {
    await restorePlan();
    const pointed = await pointPlanAt(row, r.id);
    if (pointed.status >= 300) throw new Error(`plan edit refused ${pointed.status} ${JSON.stringify(pointed.body).slice(0, 200)}`);
    await page.goto(`${BASE}/${T}/plans-rates/plans/${ELM_PLAN}`, { waitUntil: "networkidle" });
    // Wait for the plan's schedules to load before reading (a slow box drew
    // the list late and read as "not named" twice in part 2).
    await page.getByText(name).first().waitFor({ timeout: 15_000 }).catch(() => {});
    const planText = (await page.locator("main").innerText()).replace(/\s+/g, " ");
    const futureShown = new Intl.DateTimeFormat("en-US", { month: "2-digit", day: "2-digit", year: "numeric", timeZone: "UTC" }).format(FUTURE);
    r.planNames = planText.includes(name);
    r.planDate = planText.includes(futureShown);
    r.plan = r.planNames && r.planDate;
    if (!r.plan) r.notes.push(`PLAN screen: names schedule=${r.planNames} shows ${futureShown}=${r.planDate}`);
    if (PREVIEWABLE.has(row.service)) {
      const before = await preview("before");
      const after = await preview("after");
      r.billBefore = judgeBill(row, before.body, iso(TODAY), P[1], r.typed.sizes, r.typed.tier2, "before", r.typed);
      r.billAfter = judgeBill(row, after.body, iso(FUTURE), P[2], r.typed.sizes, r.typed.tier2, "after", r.typed);
      r.bill = r.billBefore.ok === null && r.billAfter.ok === null ? null : Boolean(r.billBefore.ok && r.billAfter.ok);
      r.billFigure = `before ${r.billBefore.expected}/${r.billBefore.got} · after ${r.billAfter.expected}/${r.billAfter.got}`;
      if (!r.bill) r.notes.push(`BILL before ${JSON.stringify(r.billBefore).slice(0, 260)} after ${JSON.stringify(r.billAfter).slice(0, 260)}`);
    } else {
      r.bill = null; // no account takes the service — billing's projection only (oneVersion above)
      r.billFigure = "no account takes this service; projection only";
    }
  } catch (error) {
    r.plan = false;
    r.notes.push(`IMPACT: ${String(error.message ?? error).split("\n")[0]}`);
  }
  // Put the plan back so the next row's bill is priced by the seeded schedules.
  await restorePlan().catch(() => {});
}

// ── the list drawings, and the two step-2 states no matrix row draws ───────
async function drawings() {
  const list = `${BASE}/${T}/plans-rates/rates`;
  await page.goto(list, { waitUntil: "networkidle" });
  await shot("01-list-all", "01-list-all.png");
  const filters = [["02", "water", "Water"], ["03", "sewer", "Sewer"], ["04", "electric", "Electric"], ["05", "trash", "Trash"], ["06", "battery", "Battery"]];
  for (const [n, code, word] of filters) {
    await page.goto(list, { waitUntil: "networkidle" });
    const chip = page.getByRole("button", { name: new RegExp(`^${word}\\b`) }).first();
    if (await chip.count()) await chip.click();
    else await page.goto(`${list}?service=${code}`, { waitUntil: "networkidle" });
    await page.waitForLoadState("networkidle");
    await shot(`${n}-list-${code}`, `${n}-list-${code}.png`);
  }
  await page.goto(list, { waitUntil: "networkidle" });
  // The LIST's own search, not the shell's global one at the top of the page.
  await page.getByPlaceholder(/search rate schedule/i).first().fill("zzzz no such schedule");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(800);
  await shot("07-list-no-results", "07-list-no-results.png");

  // 08–39 — View details of the eight drawn shapes, photographed from the
  // matrix rows themselves (each has an Add, a Change and a Fix behind it).
  for (const [key, [n, code]] of Object.entries(VIEW_DRAWINGS)) {
    const id = state.rows[key]?.id;
    if (!id) continue;
    // On a plan while it is photographed, so Units and the Plans tab have a
    // plan to show (the matrix put every plan back when it measured the row).
    await pointPlanAt(ROWS.find((row) => row.key === key), id);
    for (const [i, tab] of ["overview", "rates", "plans", "audit"].entries()) {
      const nn = String(Number(n) + i).padStart(2, "0");
      await page.goto(`${BASE}/${T}/plans-rates/rates/${id}?tab=${tab}`, { waitUntil: "networkidle" });
      await page.getByRole("tab", { selected: true }).waitFor();
      await shot(`${nn}-view-${code}-${tab}`, `${nn}-view-${code}-${tab}.png`);
    }
    await restorePlan();
  }

  // 40–50, 53–71 — the Add and Edit states, on schedules of their own.
  DRAWING = true;
  const drawnRows = ROWS.filter((row) => ADD_DRAWINGS[row.key]);
  drawnRows.sort((a, b) => (a.key === FIRST_ROW ? -1 : b.key === FIRST_ROW ? 1 : 0));
  for (const row of drawnRows) {
    const r = await walkRow(row).catch((error) => ({ notes: [`CRASH ${error}`] }));
    console.log(`drawing row ${row.key}: ${r.notes?.length ? r.notes.join(" | ") : "ok"}`);
  }
  DRAWING = false;

  // 51 — trash with a size that has no base price; 52 — every size used.
  for (const [n, row, sizes] of [["51-add-2-pricing-unpriced-size", { service: "trash", model: "capacity", klass: null, base: "BASE-T-SZ" }, 1], ["52-add-2-pricing-every-size-used", { service: "broadband", model: "flat", klass: null, base: "BASE-BB-WC" }, 99]]) {
    await page.goto(`${BASE}/${T}/plans-rates/rates/new`, { waitUntil: "networkidle" });
    await fillDetails(row, `WC ${STAMP} drawing ${n.slice(0, 2)}`);
    await next();
    await page.locator("[data-step=pricing]").waitFor();
    const add = page.locator("[data-step=pricing]").getByRole("button", { name: "+ Add row" }).first();
    for (let i = 0; i < sizes && !(await add.isDisabled()); i += 1) {
      await add.click();
      const values = await offeredValues(cell(`size-${i}`));
      // 51: a dumpster, which BASE-T-SZ does not price (it prices the carts).
      await cell(`size-${i}`).selectOption(n.startsWith("51") ? (values.find((v) => v.startsWith("DUMP")) ?? values[0]) : values[0]);
    }
    await shot(n, `${n}.png`);
  }
}

// ── run ────────────────────────────────────────────────────────────────────
await signIn();
await setup();
console.log(`matrix: ${ROWS.length} rows (${SERVICES.length} services × ${METHODS.length} methods at Every class = ${SERVICES.length * METHODS.length}, + ${CLASS_ROWS.length} customer-class rows)`);
if (PHASE !== "drawings") {
  // The first row photographs the shared drawings, so it goes first.
  const order = [...ROWS.filter((r) => r.key === FIRST_ROW), ...ROWS.filter((r) => r.key !== FIRST_ROW)];
  for (const row of order) {
    if (ONLY && !row.key.startsWith(ONLY)) continue;
    if (process.env.RSW_REBILL && state.rows[row.key]?.id) {
      // Re-measure a row already walked: the change in the database, and its
      // impact on the plan and the bill. Nothing is added or edited again.
      const r = state.rows[row.key];
      await verifyChange(row, r, true);
      await impact(row, r);
      save();
      console.log(`${row.key.padEnd(44)} REBILL change ${r.change} plan ${r.plan} bill ${r.bill} ${r.billFigure ?? ""}${r.notes.length ? `\n    ${r.notes.join("\n    ")}` : ""}`);
      continue;
    }
    if (!ONLY && state.rows[row.key]?.done) continue;
    const t0 = Date.now();
    const r = await walkRow(row).catch((error) => ({ key: row.key, notes: [`CRASH ${error}`] }));
    r.done = true;
    r.seconds = Math.round((Date.now() - t0) / 1000);
    state.rows[row.key] = r;
    save();
    const mark = (v) => (v === true ? "ok" : v === false ? "FAIL" : v === null ? "n/a" : "—");
    console.log(`${row.key.padEnd(44)} add ${mark(r.add)} db ${mark(r.db)} change ${mark(r.change)} fix ${mark(r.fix)} hist ${mark(r.history)} one ${mark(r.oneVersion)} plan ${mark(r.plan)} bill ${mark(r.bill)} ${r.seconds}s${r.notes?.length ? `\n    ${r.notes.join("\n    ")}` : ""}`);
  }
}
if (PHASE !== "matrix") await drawings();
probe.stdin.end();
await browser.close();
