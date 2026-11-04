// ── Trace ──────────────────────────────────────────────
// Change:   CR-156-BRC10 wave B — the charge-code screens rebuilt from
//           05-prototype/charge-codes-2026-10-01/images (83 states).
// Journey:  Add → View → Edit (a price changed FROM A FUTURE DATE) for one BASE,
//           one PLAN and one OTHER code, on a seeded tenant, in Chromium at 1440.
//           After each edit the price history is read back through the API:
//           the old row is CLOSED the day before the new date and marked
//           killed, and the new price is a NEW row — never an overwrite.
// Run:      E2E_BASE_URL=http://127.0.0.1:<spa> \
//           E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//           npx playwright test e2e/CR-156-charge-codes-wave-b.spec.ts
//           Needs a PRIVATE seeded database (tenant `brazosbend`); it mints three
//           Settings codes and writes prices.
// Shots:    08-qa/screens/charge-codes-waveB-2026-10-01/<NN>-<state>.built.png,
//           NN = the reference image the state is compared with.
// ───────────────────────────────────────────────────────
import { mkdirSync } from "node:fs";

import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

import { baseUrl, skipUnlessAppServer, tenant } from "./support/app";

const SHOTS = process.env.SHOTS ?? "../08-qa/screens/charge-codes-waveB-2026-10-01";
const EMAIL = process.env.E2E_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.E2E_PASSWORD ?? "S3cure!passw0rd";
const STAMP = String(Date.now() % 100000);

test.use({ viewport: { width: 1440, height: 1100 } });
skipUnlessAppServer(test);

function iso(day: Date): string {
  return day.toISOString().slice(0, 10);
}
const TODAY = new Date();
const FUTURE = new Date(Date.UTC(TODAY.getUTCFullYear(), TODAY.getUTCMonth() + 1, 1)); // the 1st of next month
const DAY_BEFORE_FUTURE = new Date(FUTURE.getTime() - 86_400_000);

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

async function shot(page: Page, name: string): Promise<void> {
  mkdirSync(SHOTS, { recursive: true });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${SHOTS}/${name}.built.png`, fullPage: true });
}

/** A code minted the way Settings → Reference data mints one: code and name only. */
async function mintSettingsCode(request: APIRequestContext, code: string, name: string): Promise<void> {
  const response = await request.post(api("/lookups/charge_codes"), { data: { code, name } });
  expect(response.status(), await response.text()).toBeLessThan(300);
}

async function enableService(request: APIRequestContext, service: string): Promise<void> {
  const response = await request.put(api(`/settings/services/${service}`), { data: { enabled: true } });
  expect(response.status(), await response.text()).toBeLessThan(300);
}

async function chargeByCode(request: APIRequestContext, code: string) {
  const list = await (await request.get(api(`/charges?q=${encodeURIComponent(code)}&per=50`))).json();
  const row = list.results.find((one: { code: string }) => one.code === code);
  expect(row, `charge ${code} listed`).toBeTruthy();
  return (await (await request.get(api(`/charges/${row.id}`))).json()) as {
    id: string;
    kind: string;
    prices: { size_class: string; customer_class: string | null; amount_display: string | null; effective_from: string; effective_to: string | null; killed: boolean }[];
    versions: { state: string; effective_from: string }[];
  };
}

async function cont(page: Page): Promise<void> {
  await page.getByRole("button", { name: /^Continue/ }).click();
}

async function pickCode(page: Page, code: string): Promise<void> {
  await page.locator("#cc-code").click();
  await page.getByRole("option", { name: new RegExp(`^${code} ·`) }).click();
}

async function setDate(page: Page, id: string, value: string): Promise<void> {
  await page.locator(`#${id}`).fill(value);
}

/** The one assertion this journey exists for: dated, closed, never overwritten. */
function expectClosedAndNew(
  prices: { size_class: string; customer_class: string | null; amount_display: string | null; effective_from: string; effective_to: string | null; killed: boolean }[],
  sizeClass: string,
  before: string,
  after: string,
) {
  const rows = prices.filter((row) => row.size_class === sizeClass && row.customer_class === null);
  const old = rows.find((row) => row.amount_display === before);
  const next = rows.find((row) => row.amount_display === after);
  expect(old, `${sizeClass} ${before} kept`).toBeTruthy();
  expect(next, `${sizeClass} ${after} added`).toBeTruthy();
  expect(old?.killed).toBe(true);
  expect(old?.effective_to).toBe(iso(DAY_BEFORE_FUTURE));
  expect(next?.effective_from).toBe(iso(FUTURE));
  expect(next?.effective_to).toBeNull();
  expect(next?.killed).toBe(false);
}

test.describe("CR-156-BRC10 wave B · Add → View → Edit, base · plan · other", () => {
  test("the list draws Kind, Priced by and the kind chips", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/plans-rates/charge-codes`);
    await expect(page.locator("[data-kind-chips]")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('thead th:has-text("Kind")')).toBeVisible();
    await expect(page.locator('thead th:has-text("Priced by")')).toBeVisible();
    await shot(page, "01-list-all");
    await page.locator('[data-kind-chip="base"]').click();
    await expect(page).toHaveURL(/f\.kind=base/);
    await shot(page, "02-list-base");
    await page.locator('[data-kind-chip="plan"]').click();
    await shot(page, "03-list-plan");
    await page.locator('[data-kind-chip="other"]').click();
    await shot(page, "04-list-other");
  });

  test("BASE: add a trash base by size, view it, reprice one size from a future date", async ({ page }) => {
    await signIn(page);
    const request = page.context().request;
    await enableService(request, "trash");
    const code = `BASE-T${STAMP}`.slice(0, 20);
    await mintSettingsCode(request, code, "Trash base charge");

    await page.goto(`/${tenant()}/plans-rates/charge-codes/new`);
    await page.locator("#cc-kind").selectOption("base");
    await page.locator("#cc-service").selectOption("trash");
    await pickCode(page, code);
    await expect(page.locator("#cc-name")).toHaveValue("Trash base charge");
    await shot(page, "43-add-1-details-base");
    await cont(page);
    // Every trash size starts as a row (size order); two are priced and the
    // rest stay "Not priced", which the note under the table counts.
    await expect(page.locator('[data-cell="size-0"]')).not.toHaveValue("");
    await page.getByLabel(/^Every class 1$/).fill("9.00");
    await page.getByLabel(/^Every class 2$/).fill("12.00");
    await expect(page.locator('[data-charge-note="not-priced"]')).toBeVisible();
    await shot(page, "53-add-2-pricing-base-trash");
    await cont(page);
    await page.getByRole("button", { name: "Create charge code" }).click();
    await expect(page.getByText("Pick a date.")).toBeVisible();
    await shot(page, "71-add-3-review-date-error");
    await setDate(page, "cc-effective-from", iso(TODAY));
    await page.getByRole("button", { name: "Create charge code" }).click();
    await expect(page.getByText(`${code} created.`)).toBeVisible({ timeout: 30_000 });
    await shot(page, "72-add-3-review-saved");

    const created = await chargeByCode(request, code);
    expect(created.kind).toBe("base");
    await page.goto(`/${tenant()}/plans-rates/charge-codes/${created.id}`);
    await expect(page.getByRole("heading", { name: "Trash base charge" })).toBeVisible({ timeout: 30_000 });
    await shot(page, "18-view-base-BASE-T-overview");
    await page.getByRole("tab", { name: "Prices" }).click();
    await shot(page, "19-view-base-BASE-T-prices");

    await page.goto(`/${tenant()}/plans-rates/charge-codes/${created.id}/edit`);
    await expect(page.locator("#cc-code")).toHaveValue(code, { timeout: 30_000 });
    await shot(page, "73-edit-1-details-base-BASE-T");
    await cont(page);
    const second = page.getByLabel(/^Every class 2$/);
    const was = await second.inputValue();
    await second.fill("13.00");
    await shot(page, "74-edit-2-pricing-base-BASE-T");
    await cont(page);
    await setDate(page, "cc-effective-from", iso(FUTURE));
    await page.locator("#cc-reason").fill("Board approved, walk");
    await shot(page, "75-edit-3-review-base-BASE-T");
    await page.getByRole("button", { name: "Save change" }).click();
    await expect(page.getByText(`${code} saved.`)).toBeVisible({ timeout: 30_000 });
    await shot(page, "83-edit-3-review-saved");

    const edited = await chargeByCode(request, code);
    const sizeRow = edited.prices.find((row) => row.amount_display === "13.00");
    expectClosedAndNew(edited.prices, sizeRow?.size_class ?? "", was, "13.00");
    expect(edited.versions[0].state).toBe("scheduled");
    await page.goto(`/${tenant()}/plans-rates/charge-codes/${created.id}?tab=audit`);
    await expect(page.getByText("Change scheduled.")).toBeVisible({ timeout: 30_000 });
    await shot(page, "09-view-base-audit-scheduled");
  });

  test("PLAN: add a one-amount plan code, view it, reprice it from a future date", async ({ page }) => {
    await signIn(page);
    const request = page.context().request;
    const code = `PLAN-${STAMP}`;
    await mintSettingsCode(request, code, "Account transfer fee");
    await page.goto(`/${tenant()}/plans-rates/charge-codes/new`);
    await page.locator("#cc-kind").selectOption("plan");
    await pickCode(page, code);
    await page.locator("#cc-priced-by").selectOption("one");
    await shot(page, "44-add-1-details-plan-onetime");
    await cont(page);
    await page.getByLabel(/^Amount 1/).fill("15.00");
    await shot(page, "60-add-2-pricing-plan-one-amount");
    await cont(page);
    await setDate(page, "cc-effective-from", iso(TODAY));
    await page.getByRole("button", { name: "Create charge code" }).click();
    await expect(page.getByText(`${code} created.`)).toBeVisible({ timeout: 30_000 });

    const created = await chargeByCode(request, code);
    expect(created.kind).toBe("plan");
    await page.goto(`/${tenant()}/plans-rates/charge-codes/${created.id}`);
    await expect(page.getByRole("heading", { name: "Account transfer fee" })).toBeVisible({ timeout: 30_000 });
    await shot(page, "22-view-plan-overview");
    await page.getByRole("tab", { name: "Prices" }).click();
    await shot(page, "23-view-plan-prices");

    await page.goto(`/${tenant()}/plans-rates/charge-codes/${created.id}/edit`);
    await expect(page.locator("#cc-code")).toHaveValue(code, { timeout: 30_000 });
    await shot(page, "76-edit-1-details-plan");
    await cont(page);
    await page.getByLabel(/^Amount 1/).fill("20.00");
    await shot(page, "77-edit-2-pricing-plan");
    await cont(page);
    await setDate(page, "cc-effective-from", iso(FUTURE));
    await page.locator("#cc-reason").fill("Board approved, walk");
    await shot(page, "78-edit-3-review-plan");
    await page.getByRole("button", { name: "Save change" }).click();
    await expect(page.getByText(`${code} saved.`)).toBeVisible({ timeout: 30_000 });
    expectClosedAndNew((await chargeByCode(request, code)).prices, "All sizes", "15.00", "20.00");
  });

  test("OTHER: add a one-amount other code, view it, reprice it from a future date", async ({ page }) => {
    await signIn(page);
    const request = page.context().request;
    const code = `OTH-${STAMP}`;
    await mintSettingsCode(request, code, "Meter re-read");
    await page.goto(`/${tenant()}/plans-rates/charge-codes/new`);
    await page.locator("#cc-kind").selectOption("other");
    await pickCode(page, code);
    await shot(page, "48-add-1-details-other");
    await cont(page);
    await page.getByLabel(/^Amount 1/).fill("20.00");
    await shot(page, "63-add-2-pricing-other-one-amount");
    await cont(page);
    await setDate(page, "cc-effective-from", iso(TODAY));
    await shot(page, "69-add-3-review-other-one-amount");
    await page.getByRole("button", { name: "Create charge code" }).click();
    await expect(page.getByText(`${code} created.`)).toBeVisible({ timeout: 30_000 });

    const created = await chargeByCode(request, code);
    expect(created.kind).toBe("other");
    await page.goto(`/${tenant()}/plans-rates/charge-codes/${created.id}`);
    await expect(page.getByRole("heading", { name: "Meter re-read" })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("tab", { name: "Plans" })).toHaveCount(0);
    await shot(page, "37-view-other-REREAD-overview");

    await page.goto(`/${tenant()}/plans-rates/charge-codes/${created.id}/edit`);
    await expect(page.locator("#cc-code")).toHaveValue(code, { timeout: 30_000 });
    await shot(page, "79-edit-1-details-other");
    await cont(page);
    await page.getByLabel(/^Amount 1/).fill("25.00");
    await shot(page, "80-edit-2-pricing-other");
    await cont(page);
    await setDate(page, "cc-effective-from", iso(FUTURE));
    await page.getByRole("button", { name: "Save change" }).click();
    await expect(page.getByText("Add a reason.")).toBeVisible();
    await shot(page, "82-edit-3-review-reason-error");
    await page.locator("#cc-reason").fill("Board approved, walk");
    await page.getByRole("button", { name: "Save change" }).click();
    await expect(page.getByText(`${code} saved.`)).toBeVisible({ timeout: 30_000 });
    await shot(page, "81-edit-3-review-other-saved");
    expectClosedAndNew((await chargeByCode(request, code)).prices, "All sizes", "20.00", "25.00");
  });
});
