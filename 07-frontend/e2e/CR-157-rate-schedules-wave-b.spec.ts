// ── Trace ──────────────────────────────────────────────
// Change:   CR-157-BRC10 wave B — the rate-schedule screens rebuilt from
//           05-prototype/rate-schedules-2026-10-01/images (71 states).
// Journey:  View details — Overview, Rates, Plans and Audit — for one TIERED
//           water schedule, and the Rates tab for one schedule of another
//           method · Add one schedule of each of the SEVEN methods · Change
//           the rate from a future date · Fix an error — on a seeded tenant,
//           in Chromium at 1440. After each edit the versions are read back
//           through the API: a change is a NEW version and the old one ends
//           the day before; a fix keeps the dates and states its reason.
// Run:      E2E_BASE_URL=http://127.0.0.1:<spa> \
//           E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//           npx playwright test e2e/CR-157-rate-schedules-wave-b.spec.ts
//           Needs a PRIVATE seeded database (`seed_demo`, tenant `brazosbend`).
// Shots:    08-qa/screens/rate-schedules-waveB-2026-10-01/<NN>-<state>.built.png
//           beside <NN>-<state>.reference.png, NN = the reference image number.
// ───────────────────────────────────────────────────────
import { copyFileSync, mkdirSync } from "node:fs";

import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

import { baseUrl, skipUnlessAppServer, tenant } from "./support/app";

const SHOTS = process.env.SHOTS ?? "../08-qa/screens/rate-schedules-waveB-2026-10-01";
const REFERENCE = "../05-prototype/rate-schedules-2026-10-01/images";
const EMAIL = process.env.E2E_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.E2E_PASSWORD ?? "S3cure!passw0rd";

test.use({ viewport: { width: 1440, height: 1100 } });
skipUnlessAppServer(test);

async function signIn(page: Page): Promise<void> {
  await page.goto(`/${tenant()}/signin`);
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.endsWith("/signin"), { timeout: 60_000 }),
    page.click('button[type="submit"]'),
  ]);
}

const api = (path: string) => `${baseUrl()}/api/${tenant()}${path}`;

/** The built screen, with the drawing it was built from copied in beside it. */
async function shot(page: Page, name: string, reference: string): Promise<void> {
  mkdirSync(SHOTS, { recursive: true });
  await page.waitForTimeout(500);
  // A wizard's buttons live in its bottom footer, and the app scrolls inside
  // its own frame, so a full-page shot stops at the viewport. Bring the footer
  // into view (the least scroll that shows it). View details and the list keep
  // theirs in the page head (DEF-RAT-9101), which is always in view.
  const bar = page.locator("[data-wizard=actions]").first();
  if ((await bar.count()) > 0) {
    await bar.evaluate((node) => {
      // Clear of the screen-id tag in the corner.
      (node as HTMLElement).style.scrollMarginBottom = "56px";
      node.scrollIntoView({ block: "nearest" });
    });
    await page.waitForTimeout(200);
  }
  await page.screenshot({ path: `${SHOTS}/${name}.built.png`, fullPage: true });
  copyFileSync(`${REFERENCE}/${reference}`, `${SHOTS}/${name}.reference.png`);
}

interface Card {
  id: string;
  name: string;
  service: string;
  structure: string | null;
}

async function schedules(request: APIRequestContext): Promise<Card[]> {
  const response = await request.get(api("/rate-schedules?per=100"));
  expect(response.status(), await response.text()).toBe(200);
  const body = await response.json();
  return (body.results ?? body) as Card[];
}

const modelOf = (card: Card): string => card.structure ?? "";

async function openTab(page: Page, id: string, tab: string): Promise<void> {
  await page.goto(`/${tenant()}/plans-rates/rates/${id}?tab=${tab}`);
  await expect(page.getByRole("tab", { selected: true })).toBeVisible();
  await expect(page.locator("[aria-busy='true']")).toHaveCount(0);
}

test("View details — a tiered water schedule's four tabs, and another method's Rates", { tag: "@app-server" }, async ({ page }) => {
  await signIn(page);
  const cards = await schedules(page.request);
  const water = cards.find((card) => card.service === "water" && modelOf(card) === "tiered");
  expect(water, "a tiered water schedule is seeded").toBeTruthy();

  // DEF-RAT-9101 — the list, with `New rate schedule` top-right in the page head.
  await page.goto(`/${tenant()}/plans-rates/rates`);
  await expect(page.locator("table.data-table tbody tr").first()).toBeVisible();
  await expect(page.locator(".page-header-actions").getByRole("button", { name: /New rate schedule/ })).toBeVisible();
  await shot(page, "01-list-all", "01-list-all.png");

  await openTab(page, water!.id, "overview");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(water!.name);
  await shot(page, "08-view-water-tiered-overview", "08-view-W-RES-overview.png");

  await openTab(page, water!.id, "rates");
  await expect(page.getByRole("tab", { selected: true })).toHaveText(/Rates/);
  await shot(page, "09-view-water-tiered-rates", "09-view-W-RES-rates.png");

  await openTab(page, water!.id, "plans");
  await shot(page, "10-view-water-tiered-plans", "10-view-W-RES-plans.png");

  await openTab(page, water!.id, "audit");
  await shot(page, "11-view-water-tiered-audit", "11-view-W-RES-audit.png");

  // One schedule of another method, its Rates tab beside the drawing of that method.
  const references: Record<string, [string, string]> = {
    tou: ["21-view-tou-rates", "21-view-E-TOU-rates.png"],
    demand: ["25-view-demand-rates", "25-view-E-DEM-rates.png"],
    seasonal: ["29-view-seasonal-rates", "29-view-W-SEAS-rates.png"],
    capacity: ["33-view-capacity-rates", "33-view-TRASH-rates.png"],
    percent: ["37-view-percent-rates", "37-view-SEW-PCT-rates.png"],
    flat: ["13-view-flat-rates", "13-view-SEWER-rates.png"],
  };
  const other = cards.find((card) => modelOf(card) in references && modelOf(card) !== "tiered");
  if (other) {
    const [name, reference] = references[modelOf(other)];
    await openTab(page, other.id, "rates");
    await shot(page, name, reference);
  }
});

// ── Add · Change the rate · Fix an error ───────────────────────────────────

const STAMP = String(Date.now() % 100000);

async function next(page: Page): Promise<void> {
  await page.locator("[data-wizard=actions]").getByRole("button", { name: /^Continue|^Next/ }).click();
}

async function details(page: Page, name: string, service: string, model: string, base: string) {
  await page.fill("#rs-name", name);
  await page.selectOption("#rs-service", service);
  await page.selectOption("#rs-structure", model);
  // The first unit the service offers — the wizard disables the rest. The
  // list arrives with the service's lookups, so wait for it rather than race it.
  const offered = () =>
    page
      .locator("#rs-unit option:not([disabled])")
      .evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value).filter(Boolean));
  await expect.poll(async () => (await offered()).length, { timeout: 15_000 }).toBeGreaterThan(0);
  if ((await page.inputValue("#rs-unit")) === "") {
    await page.selectOption("#rs-unit", (await offered())[0]);
  }
  await page.fill("#rs-base-code", base);
  await page.getByRole("option", { name: new RegExp(`^${base}\\b`) }).first().click();
}

function iso(day: Date): string {
  return day.toISOString().slice(0, 10);
}
const TODAY = new Date();
const FUTURE = new Date(Date.UTC(TODAY.getUTCFullYear(), TODAY.getUTCMonth() + 1, 1)); // the 1st of next month

const cell = (page: Page, name: string) => page.locator(`[data-cell="${name}"]`);

async function chooseFirst(page: Page, name: string): Promise<void> {
  const values = await cell(page, name)
    .locator("option:not([disabled])")
    .evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value).filter(Boolean));
  await cell(page, name).selectOption(values[0]);
}

async function addRow(page: Page, panel: "base" | "usage"): Promise<void> {
  const index = panel === "base" ? 0 : 1;
  await page.locator("[data-step=pricing]").getByRole("button", { name: "+ Add row" }).nth(index).click();
}

/** Step 2 for one method — one base size, and the usage the method needs. */
async function pricing(page: Page, model: string): Promise<void> {
  await addRow(page, "base");
  await chooseFirst(page, "size-0");
  switch (model) {
    case "flat":
      await cell(page, "price-0").fill("0.1200");
      break;
    case "tiered":
      await cell(page, "tier-to-0").fill("5");
      await cell(page, "tier-price-0").fill("4.4096");
      await addRow(page, "usage");
      await cell(page, "tier-price-1").fill("5.21");
      break;
    case "time_of_use":
      // Every hour of the day in exactly one window (US-RAT-006 TC-5).
      await addRow(page, "usage");
      await cell(page, "window-0").selectOption("On-peak");
      await cell(page, "days-0").selectOption("weekday");
      await cell(page, "starts-0").fill("14:00");
      await cell(page, "ends-0").fill("20:00");
      await cell(page, "window-price-0").fill("0.18");
      await addRow(page, "usage");
      await cell(page, "window-1").selectOption("Off-peak");
      await cell(page, "days-1").selectOption("weekday");
      await cell(page, "starts-1").fill("20:00");
      await cell(page, "ends-1").fill("14:00");
      await cell(page, "window-price-1").fill("0.09");
      await expect(page.locator("[data-register]").first()).toHaveAttribute("data-register", "tou_on");
      break;
    case "demand":
      await cell(page, "energy_rate_per_kwh").fill("0.085");
      await cell(page, "demand_rate_per_kw").fill("11");
      break;
    case "seasonal":
      await addRow(page, "usage");
      await cell(page, "season-0").fill("All year");
      await cell(page, "season-start-0").fill(`${TODAY.getUTCFullYear()}-01-01`);
      await cell(page, "season-end-0").fill(`${TODAY.getUTCFullYear()}-12-31`);
      await cell(page, "season-price-0").fill("4.50");
      break;
    case "capacity":
      await cell(page, "price-0").fill("3.00");
      break;
    case "percent_of_service":
      await page.getByLabel("Percentage", { exact: true }).fill("10");
      await page.getByLabel(/^Based on/).selectOption({ index: 1 });
      await page.getByLabel("Price per unit", { exact: true }).fill("4.40");
      break;
  }
}

const METHODS: [string, string, string, string, string][] = [
  ["flat", "electric", "BASE-E", "44-add-2-pricing-flat", "53-add-3-review-flat"],
  ["tiered", "water", "BASE-W", "45-add-2-pricing-tiered", "54-add-3-review-tiered"],
  ["time_of_use", "electric", "BASE-E", "46-add-2-pricing-tou", "55-add-3-review-tou"],
  ["demand", "electric", "BASE-E", "47-add-2-pricing-demand", "56-add-3-review-demand"],
  ["seasonal", "water", "BASE-W", "48-add-2-pricing-seasonal", "57-add-3-review-seasonal"],
  ["capacity", "electric", "BASE-E", "49-add-2-pricing-capacity", "58-add-3-review-capacity"],
  ["percent_of_service", "water", "BASE-W", "50-add-2-pricing-pct", "59-add-3-review-pct"],
];

const LABEL: Record<string, string> = {
  flat: "Flat",
  tiered: "Tiered",
  time_of_use: "Time of use",
  demand: "Demand",
  seasonal: "Seasonal",
  capacity: "Capacity",
  percent_of_service: "Percent",
};

test("Add — one rate schedule of each of the seven methods", { tag: "@app-server" }, async ({ page }) => {
  test.setTimeout(300_000);
  await signIn(page);
  for (const [model, service, base, pricingShot, reviewShot] of METHODS) {
    const name = `E2E ${LABEL[model]} ${STAMP}`;
    await page.goto(`/${tenant()}/plans-rates/rates/new`);
    await expect(page.locator("[data-step=details]")).toBeVisible();
    if (model === "flat") {
      await shot(page, "40-add-1-details", "40-add-1-details.png");
      await next(page);
      await expect(page.getByText("Add a name.").first()).toBeVisible();
      await shot(page, "43-add-1-errors", "43-add-1-errors.png");
    }
    await details(page, name, service, model, base);
    await next(page);
    await expect(page.locator("[data-step=pricing]")).toBeVisible();
    await pricing(page, model);
    await shot(page, pricingShot, `${pricingShot}.png`);
    await next(page);
    await expect(page.locator("[data-step=review]")).toBeVisible();
    if (model === "flat") {
      await page.locator("[data-wizard=actions]").getByRole("button", { name: "Create rate schedule" }).click();
      await expect(page.getByText("Pick a date.").first()).toBeVisible();
      await shot(page, "60-add-3-date-error", "60-add-3-date-error.png");
    }
    await page.locator("#rs-effective-from").fill(iso(TODAY));
    await shot(page, reviewShot, `${reviewShot}.png`);
    await page.locator("[data-wizard=actions]").getByRole("button", { name: "Create rate schedule" }).click();
    await expect(page.getByText("New schedule created.").first()).toBeVisible();
    if (model === "flat") {
      await shot(page, "61-add-3-saved", "61-add-3-saved.png");
    }
    const card = (await schedules(page.request)).find((one) => one.name === name);
    expect(card, `${name} listed`).toBeTruthy();
    expect(modelOf(card!)).toBe(model);
  }
});

interface DetailBody {
  versions: {
    id: string;
    effective_from: string | null;
    effective_to: string | null;
    corrects: string | null;
    superseded_by: string | null;
    change_reason: string | null;
    correction_reason: string | null;
    structure: { tiers?: { unit_price: string }[] };
  }[];
}

async function scheduleDetail(page: Page, id: string): Promise<DetailBody> {
  const response = await page.request.get(api(`/rate-schedules/${id}`));
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()) as DetailBody;
}

/** A fresh tiered water schedule, in force from today, made through the API. */
async function freshTiered(page: Page, name: string): Promise<string> {
  const codes = await (await page.request.get(api("/charges?q=BASE-W&per=50"))).json();
  const base = codes.results.find((row: { code: string }) => row.code === "BASE-W");
  const response = await page.request.post(api("/rate-schedules"), {
    data: {
      name,
      model: "tiered",
      service: "water",
      uom: "kgal",
      base_charge_code: base.id,
      size_rows: [{ size_class: "W-58" }],
      structure: { tiers: [{ from_qty: "0", to_qty: null, unit_price: "4.4096" }] },
      effective_from: iso(TODAY),
      effective_to: null,
    },
  });
  expect(response.status(), await response.text()).toBeLessThan(300);
  return ((await response.json()) as { id: string }).id;
}

test("Edit — Change the rate from a future date: a NEW version, the old one closed the day before", { tag: "@app-server" }, async ({ page }) => {
  await signIn(page);
  const id = await freshTiered(page, `E2E change ${STAMP}`);
  await page.goto(`/${tenant()}/plans-rates/rates/${id}/edit`);
  await expect(page.locator("[data-step=details]")).toBeVisible();
  await expect(page.locator("#rs-service")).toBeDisabled();
  await shot(page, "62-edit-change-1", "62-edit-change-1.png");
  await next(page);
  await cell(page, "tier-price-0").fill("4.6500");
  await shot(page, "63-edit-change-2", "63-edit-change-2.png");
  await next(page);
  await page.locator("#rs-effective-from").fill(iso(FUTURE));
  const commit = page.locator("[data-wizard=actions]").getByRole("button", { name: "Create new version" });
  await commit.click();
  await expect(page.getByText("Add what changed.").first()).toBeVisible();
  await shot(page, "65-edit-change-reason-error", "65-edit-change-reason-error.png");
  await page.locator("#rs-what-changed").fill("Board approved new tier price");
  await shot(page, "64-edit-change-3", "64-edit-change-3.png");
  await commit.click();
  await expect(page.getByText("saved as new version.").first()).toBeVisible();
  await expect(page.locator("[data-rs-aside]")).toContainText("v2"); // the schedule's second version
  await shot(page, "66-edit-change-saved", "66-edit-change-saved.png");

  const versions = (await scheduleDetail(page, id)).versions;
  const added = versions.find((row) => row.effective_from === iso(FUTURE));
  const before = versions.find((row) => row.effective_from === iso(TODAY));
  expect(added, "a new version from the future date").toBeTruthy();
  expect(added?.change_reason).toBe("Board approved new tier price");
  expect(added?.structure.tiers?.[0].unit_price).toMatch(/^4\.65/);
  // the version in force keeps its price and now ends the day before
  expect(before?.structure.tiers?.[0].unit_price).toMatch(/^4\.4096/);
  expect(before?.effective_to).toBe(iso(new Date(FUTURE.getTime() - 86_400_000)));
});

test("Edit — Fix an error: the version in force corrected, same dates, with a reason", { tag: "@app-server" }, async ({ page }) => {
  await signIn(page);
  const id = await freshTiered(page, `E2E fix ${STAMP}`);
  await page.goto(`/${tenant()}/plans-rates/rates/${id}/edit`);
  await expect(page.locator("[data-step=details]")).toBeVisible();
  await page.getByText("Fix an error", { exact: true }).click();
  await expect(page.getByRole("radio", { name: "Fix an error" })).toBeChecked();
  await expect(page.locator("#rs-structure")).toBeDisabled();
  await shot(page, "67-edit-correct-1", "67-edit-correct-1.png");
  await next(page);
  await cell(page, "tier-price-0").fill("4.0496");
  await shot(page, "68-edit-correct-2", "68-edit-correct-2.png");
  await next(page);
  await expect(page.locator("#rs-effective-from")).toHaveCount(0); // no dates on a correction
  const commit = page.locator("[data-wizard=actions]").getByRole("button", { name: "Save correction" });
  await commit.click();
  await expect(page.getByText("Add a reason.").first()).toBeVisible();
  await shot(page, "70-edit-correct-reason-error", "70-edit-correct-reason-error.png");
  await page.locator("#rs-reason").fill("Typed 4.4096 for 4.0496");
  await shot(page, "69-edit-correct-3", "69-edit-correct-3.png");
  await commit.click();
  await expect(page.getByText("corrected.").first()).toBeVisible();
  await expect(page.locator("[data-rs-aside]")).toContainText("v1 (corrected)");
  await shot(page, "71-edit-correct-saved", "71-edit-correct-saved.png");

  const versions = (await scheduleDetail(page, id)).versions;
  const fixed = versions.find((row) => row.correction_reason === "Typed 4.4096 for 4.0496");
  const wrong = versions.find((row) => row !== fixed);
  expect(fixed, "a correcting version").toBeTruthy();
  expect(wrong, "the wrong version is kept").toBeTruthy();
  expect(versions).toHaveLength(2);
  // Same dates: the correction prices exactly the days the wrong version did.
  expect(fixed?.effective_from).toBe(iso(TODAY));
  expect(fixed?.effective_to).toBeNull();
  expect(fixed?.structure.tiers?.[0].unit_price).toMatch(/^4\.0496/);
  expect(wrong?.structure.tiers?.[0].unit_price).toMatch(/^4\.4096/);
});
