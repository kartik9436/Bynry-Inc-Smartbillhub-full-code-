// ── Trace ──────────────────────────────────────────────
// Change:   CR-156-BRC10 wave C — ALL 83 charge-code states photographed in the
//           product, each beside the reference image it is compared with
//           (05-prototype/charge-codes-2026-10-01/images, README index), and
//           the two pricings wave C built (DEF-RAT-8753) walked end to end.
// Journey:  08-qa/01-e2e/journeys/J76-charge-codes.md
// Run:      E2E_BASE_URL=http://127.0.0.1:<spa> \
//           E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//           npx playwright test e2e/CR-156-charge-codes-wave-c.spec.ts --workers=1
//           Needs a PRIVATE seeded database (tenant `brazosbend`): it enables
//           services, mints Settings codes and writes prices.
// Shots:    08-qa/screens/charge-codes-waveC-2026-10-01/<NN>-<state>.built.png
//           (NN = the reference image number; the reference is copied beside
//           it as <NN>-<state>.ref.png by the comparison step, not by this file).
// Figures:  every figure drawn in a reference image is an ILLUSTRATION (B14
//           rule 37); this walk sets data of the same SHAPE (sizes, classes,
//           a scheduled change, an unpriced size, a code with no GL).
// ───────────────────────────────────────────────────────
import { mkdirSync } from "node:fs";

import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

import { baseUrl, skipUnlessAppServer, tenant } from "./support/app";

const SHOTS = process.env.SHOTS ?? "../08-qa/screens/charge-codes-waveC-2026-10-01";
const EMAIL = process.env.E2E_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.E2E_PASSWORD ?? "S3cure!passw0rd";
const STAMP = String(Date.now() % 10000).padStart(4, "0");

// Tall enough that a whole wizard step is in the shot: the app frame scrolls
// its own content, so a full-page capture stops at the viewport.
test.use({ viewport: { width: 1440, height: 1800 } });
test.describe.configure({ mode: "serial" });
skipUnlessAppServer(test);

function iso(day: Date): string {
  return day.toISOString().slice(0, 10);
}
const TODAY = new Date();
const FUTURE = new Date(Date.UTC(TODAY.getUTCFullYear(), TODAY.getUTCMonth() + 1, 1));
const PAST = "2026-01-01";

const api = (path: string) => `${baseUrl()}/api/${tenant()}${path}`;

async function signIn(page: Page): Promise<void> {
  await page.goto(`/${tenant()}/signin`);
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.endsWith("/signin"), { timeout: 60_000 }),
    page.click('button[type="submit"]'),
  ]);
}

async function shot(page: Page, name: string): Promise<void> {
  mkdirSync(SHOTS, { recursive: true });
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${SHOTS}/${name}.built.png`, fullPage: true });
}

async function ok(response: { status(): number; text(): Promise<string> }): Promise<void> {
  expect(response.status(), await response.text()).toBeLessThan(300);
}

async function enable(request: APIRequestContext, service: string): Promise<void> {
  await ok(await request.put(api(`/settings/services/${service}`), { data: { enabled: true } }));
}

/** A Settings code — code and name only, the way Reference data mints one. */
async function mint(request: APIRequestContext, code: string, name: string): Promise<string> {
  await ok(await request.post(api("/lookups/charge_codes"), { data: { code, name } }));
  const list = await (await request.get(api(`/charges?q=${encodeURIComponent(code)}&per=50`))).json();
  const row = list.results.find((one: { code: string }) => one.code === code);
  expect(row, `${code} minted`).toBeTruthy();
  return row.id as string;
}

async function configure(request: APIRequestContext, id: string, body: Record<string, unknown>): Promise<void> {
  await ok(await request.patch(api(`/charges/${id}`), { data: body }));
}

async function charge(request: APIRequestContext, id: string) {
  return (await (await request.get(api(`/charges/${id}`))).json()) as Record<string, unknown> & {
    class_terms: { customer_class: string; percent_display: string; min_amount_display: string; effective_from: string }[];
    prices: { customer_class: string | null; percent_display: string | null; killed: boolean; effective_to: string | null }[];
    amount_rule: string;
  };
}

async function glOf(request: APIRequestContext, code: string): Promise<string | null> {
  const list = await (await request.get(api(`/charges?q=${encodeURIComponent(code)}&per=50`))).json();
  const row = list.results.find((one: { code: string; gl_account_id: string | null }) => one.code === code && one.gl_account_id);
  return row ? (row.gl_account_id as string) : null;
}

async function sizes(request: APIRequestContext, service: string): Promise<string[]> {
  const body = await (await request.get(api("/lookups/service_size_classes?per=200"))).json();
  return (body.results as { code: string; active: boolean; service: { code: string } | null }[])
    .filter((row) => row.active && row.service?.code === service)
    .map((row) => row.code);
}

const view = (id: string, tab: string) => `/${tenant()}/plans-rates/charge-codes/${id}?tab=${tab}`;

async function viewTabs(page: Page, id: string, prefix: number, slug: string, tabs: string[]): Promise<void> {
  let n = prefix;
  for (const tab of tabs) {
    await page.goto(view(id, tab));
    await expect(page.locator('[data-screen="CHG-01"]')).toBeVisible({ timeout: 30_000 });
    await shot(page, `${String(n).padStart(2, "0")}-view-${slug}-${tab}`);
    n += 1;
  }
}

async function cont(page: Page): Promise<void> {
  await page.getByRole("button", { name: /^Continue/ }).click();
}

async function pickCode(page: Page, code: string): Promise<void> {
  await page.locator("#cc-code").click();
  await page.getByRole("option", { name: new RegExp(`^${code} ·`) }).click();
}

async function startAdd(page: Page, kind: string, code: string, service?: string): Promise<void> {
  await page.goto(`/${tenant()}/plans-rates/charge-codes/new`);
  await page.locator("#cc-kind").selectOption(kind);
  if (service !== undefined) await page.locator("#cc-service").selectOption(service);
  await pickCode(page, code);
}

// Ids shared across the serial tests below.
const ids: Record<string, string> = {};
const CODE = (stem: string) => `${stem}${STAMP}`.slice(0, 20);

test.describe("CR-156-BRC10 wave C · the 83 charge-code states, built", () => {
  test("01–05 · the list, its chips and a search with no results", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/plans-rates/charge-codes`);
    await expect(page.locator("[data-kind-chips]")).toBeVisible({ timeout: 30_000 });
    await shot(page, "01-list-all");
    for (const [n, kind] of [[2, "base"], [3, "plan"], [4, "other"]] as const) {
      await page.locator(`[data-kind-chip="${kind}"]`).click();
      await expect(page).toHaveURL(new RegExp(`f\\.kind=${kind}`));
      await shot(page, `0${n}-list-${kind}`);
    }
    await page.goto(`/${tenant()}/plans-rates/charge-codes?q=ZZZ-NO-SUCH-CODE`);
    await expect(page.locator("[data-kind-chips]")).toBeVisible({ timeout: 30_000 });
    await shot(page, "05-list-no-results");
  });

  test("06–29 · View details for base and plan codes set up through the API", async ({ page }) => {
    await signIn(page);
    const request = page.context().request;
    for (const service of ["fire", "sewer", "trash", "solar", "battery"]) await enable(request, service);
    const gl = (await glOf(request, "RECON")) ?? (await glOf(request, "LATE"));
    const withGl = gl === null ? {} : { gl_account_id: gl };

    // BASE-FIRE — two fire sizes priced, and a change scheduled for next month.
    ids.fire = await mint(request, CODE("BFIRE"), "Fire base charge");
    const fire = await sizes(request, "fire");
    await configure(request, ids.fire, {
      kind: "base", is_base: true, service: "fire", charge_type: "recurring", amount_rule: "flat", auto_apply: true,
      amount: null, effective_from: PAST, ...withGl,
      size_amounts: [{ size_class: fire.find((s) => s === "FL-2") ?? fire[0], amount: "5.00" }, { size_class: fire.find((s) => s === "FL-6") ?? fire[1], amount: "20.00" }],
    });
    await configure(request, ids.fire, {
      effective_from: iso(FUTURE), reason: "Board approved, Oct 2026",
      size_amounts: [{ size_class: fire.find((s) => s === "FL-2") ?? fire[0], amount: "5.00" }, { size_class: fire.find((s) => s === "FL-6") ?? fire[1], amount: "24.00" }],
    });
    await viewTabs(page, ids.fire, 6, "base-BASE-FIRE", ["overview", "prices", "plans", "audit"]);

    // BASE-W — residential water meters, three sizes.
    ids.water = await mint(request, CODE("BW"), "Water base charge");
    await configure(request, ids.water, {
      kind: "base", is_base: true, service: "water", charge_type: "recurring", amount_rule: "flat", auto_apply: true,
      amount: null, effective_from: PAST, applies_to_customer_classes: ["residential"], ...withGl,
      size_amounts: [{ size_class: "W-58", amount: "8.00" }, { size_class: "W-34", amount: "8.00" }, { size_class: "W-1", amount: "11.50" }],
    });
    await viewTabs(page, ids.water, 10, "base-BASE-W", ["overview", "prices", "plans", "audit"]);

    // BASE-S — sewer, one amount.
    ids.sewer = await mint(request, CODE("BS"), "Sewer base charge");
    await configure(request, ids.sewer, {
      kind: "base", is_base: true, service: "sewer", charge_type: "recurring", amount_rule: "flat", auto_apply: true,
      amount: "9.00", size_amounts: [], effective_from: PAST, ...withGl,
    });
    await viewTabs(page, ids.sewer, 14, "base-BASE-S", ["overview", "prices", "plans", "audit"]);

    // BASE-T — trash, one size not priced.
    ids.trash = await mint(request, CODE("BT"), "Trash base charge");
    await configure(request, ids.trash, {
      kind: "base", is_base: true, service: "trash", charge_type: "recurring", amount_rule: "flat", auto_apply: true,
      amount: null, effective_from: PAST, ...withGl,
      size_amounts: [
        { size_class: "CART-35", amount: "9.00" }, { size_class: "CART-64", amount: "12.00" },
        { size_class: "CART-96", amount: "15.00" }, { size_class: "DUMP-2", amount: "40.00" },
        { size_class: "DUMP-4", amount: null },
      ],
    });
    await viewTabs(page, ids.trash, 18, "base-BASE-T", ["overview", "prices", "plans", "audit"]);

    // CONN — a plan code by meter size.
    ids.conn = await mint(request, CODE("CONN"), "Connection fee");
    await configure(request, ids.conn, {
      kind: "plan", charge_type: "one_time", service: "water", amount_rule: "flat", amount: null, effective_from: PAST, ...withGl,
      size_amounts: [{ size_class: "W-58", amount: "45.00" }, { size_class: "W-1", amount: "65.00" }, { size_class: "W-2", amount: "140.00" }],
    });
    await viewTabs(page, ids.conn, 22, "plan-CONN", ["overview", "prices", "plans", "audit"]);

    // DEPOSIT — a plan deposit by customer class.
    ids.deposit = await mint(request, CODE("DEP"), "Security deposit");
    await configure(request, ids.deposit, {
      kind: "plan", charge_type: "refundable", amount_rule: "flat", amount: null, effective_from: PAST, taxable_default: false, ...withGl,
      size_amounts: [{ size_class: "All sizes", customer_class: "residential", amount: "150.00" }, { size_class: "All sizes", customer_class: "commercial", amount: "500.00" }],
    });
    await viewTabs(page, ids.deposit, 26, "plan-DEPOSIT", ["overview", "prices", "plans", "audit"]);
  });

  test("46 · 61 · 67 · 30–33 · 76–78 · a PENALTY BY CUSTOMER CLASS, added, viewed, edited (DEF-RAT-8753)", async ({ page }) => {
    await signIn(page);
    const request = page.context().request;
    const code = CODE("LATE");
    ids.late = await mint(request, code, "Late payment fee");
    await startAdd(page, "plan", code);
    await page.locator("#cc-type").selectOption("penalty");
    await page.locator("#cc-priced-by").selectOption("class");
    await shot(page, "46-add-1-details-plan-penalty");
    await cont(page);
    await page.getByLabel(/^Percent 1$/).fill("1.50");
    await page.getByLabel(/^Minimum 1$/).fill("5.00");
    await page.getByLabel(/^Percent 2$/).fill("2.00");
    await page.getByLabel(/^Minimum 2$/).fill("10.00");
    await shot(page, "61-add-2-pricing-plan-penalty");
    await cont(page);
    await page.locator("#cc-effective-from").fill(iso(TODAY));
    await shot(page, "67-add-3-review-plan-penalty");
    await page.getByRole("button", { name: "Create charge code" }).click();
    await expect(page.getByText(`${code} created.`)).toBeVisible({ timeout: 30_000 });

    const created = await charge(request, ids.late);
    const terms = Object.fromEntries(created.class_terms.map((row) => [row.customer_class, `${row.percent_display} / ${row.min_amount_display}`]));
    expect(terms).toEqual({ residential: "1.50% / 5.00", commercial: "2.00% / 10.00" });
    expect(created.amount_rule).toBe("percent_with_minimum");

    await viewTabs(page, ids.late, 30, "plan-LATE", ["overview", "prices", "plans", "audit"]);

    await page.goto(`/${tenant()}/plans-rates/charge-codes/${ids.late}/edit`);
    await expect(page.locator("#cc-code")).toHaveValue(code, { timeout: 30_000 });
    await shot(page, "76-edit-1-details-plan-LATE");
    await cont(page);
    await page.getByLabel(/^Percent 2$/).fill("2.50");
    await shot(page, "77-edit-2-pricing-plan-LATE");
    await cont(page);
    await page.locator("#cc-effective-from").fill(iso(FUTURE));
    await page.locator("#cc-reason").fill("Board approved, walk");
    await shot(page, "78-edit-3-review-plan-LATE");
    await page.getByRole("button", { name: "Save change" }).click();
    await expect(page.getByText(`${code} saved.`)).toBeVisible({ timeout: 30_000 });
    // Dated and kept: commercial 2.00% closed the day before, 2.50% from the date.
    const edited = await charge(request, ids.late);
    const commercial = edited.prices.filter((row) => row.customer_class === "commercial");
    expect(commercial.map((row) => [row.percent_display, row.killed]).sort()).toEqual([["2.00%", true], ["2.50%", false]]);
    const residential = edited.prices.filter((row) => row.customer_class === "residential");
    expect(residential.map((row) => row.killed)).toEqual([false]);
  });

  test("48 · 64 · 70 · 72 · 40–42 · an amount ENTERED WHEN USED, added, viewed, and charged on a fee bill (DEF-RAT-8753)", async ({ page }) => {
    await signIn(page);
    const request = page.context().request;
    const code = CODE("TAP");
    ids.tap = await mint(request, code, "New service tap fee");
    await startAdd(page, "other", code);
    await shot(page, "48-add-1-details-other");
    await page.locator("#cc-amount-mode").selectOption("entered");
    await cont(page);
    await expect(page.locator('[data-charge-note="entered"]')).toBeVisible();
    await shot(page, "64-add-2-pricing-other-when-used");
    await cont(page);
    await page.locator("#cc-effective-from").fill(iso(TODAY));
    await shot(page, "70-add-3-review-other-when-used");
    await page.getByRole("button", { name: "Create charge code" }).click();
    await expect(page.getByText(`${code} created.`)).toBeVisible({ timeout: 30_000 });
    await shot(page, "72-add-3-review-saved");
    const created = await charge(request, ids.tap);
    expect(created.amount_rule).toBe("per_case");
    await viewTabs(page, ids.tap, 40, "other-TAP", ["overview", "prices", "audit"]);

    // The fee bill takes the clerk's amount for this code — the One-time preview.
    const gl = (await glOf(request, "RECON")) ?? (await glOf(request, "LATE"));
    if (gl !== null) await configure(request, ids.tap, { gl_account_id: gl });
    const accounts = await (await request.get(api("/accounts?per=5"))).json();
    const account = accounts.results[0];
    const preview = await request.post(api("/billing/one-time/preview"), {
      data: { kind: "fee", account_id: account.id, charge_code: code, bill_date: iso(TODAY), due_days: 21, entered_amount: "1250.00" },
    });
    await ok(preview);
    const body = await preview.json();
    // The fee's own block and the bill both carry the entered figure.
    expect(body.charge?.amount, JSON.stringify(body).slice(0, 800)).toMatch(/^1250\.00/);
    expect(JSON.stringify(body.bill ?? {})).toContain("1250.00");
  });

  test("34–39 · Other codes: one with no GL account, one with", async ({ page }) => {
    await signIn(page);
    const request = page.context().request;
    ids.app = await mint(request, CODE("APPFEE"), "Application processing fee");
    await configure(request, ids.app, { kind: "other", charge_type: "one_time", amount_rule: "flat", amount: "10.00", size_amounts: [], effective_from: PAST });
    await viewTabs(page, ids.app, 34, "other-APPFEE", ["overview", "prices", "audit"]);
    const gl = (await glOf(request, "RECON")) ?? (await glOf(request, "LATE"));
    ids.reread = await mint(request, CODE("REREAD"), "Meter re-read");
    await configure(request, ids.reread, {
      kind: "other", charge_type: "one_time", amount_rule: "flat", amount: "20.00", size_amounts: [], effective_from: PAST,
      ...(gl === null ? {} : { gl_account_id: gl }),
    });
    await viewTabs(page, ids.reread, 37, "other-REREAD", ["overview", "prices", "audit"]);
  });

  test("43–45 · 47 · 49 · 51–60 · 62–63 · 65–66 · 68–69 · 71 · the Add wizard, every remaining state", async ({ page }) => {
    await signIn(page);
    const request = page.context().request;
    const free = CODE("FREE");
    await mint(request, free, "Free code for the walk");

    await startAdd(page, "base", free, "trash");
    await shot(page, "43-add-1-details-base");
    for (const [n, type] of [[44, "one_time"], [45, "recurring"]] as const) {
      await startAdd(page, "plan", free);
      await page.locator("#cc-type").selectOption(type);
      await page.locator("#cc-priced-by").selectOption("one");
      await shot(page, `${n}-add-1-details-plan-${type === "one_time" ? "onetime" : "recurring"}`);
    }
    await startAdd(page, "plan", free);
    await page.locator("#cc-type").selectOption("refundable");
    await page.locator("#cc-priced-by").selectOption("class");
    await shot(page, "47-add-1-details-plan-deposit");

    await page.goto(`/${tenant()}/plans-rates/charge-codes/new`);
    await page.locator("#cc-kind").selectOption("plan");
    await page.locator("#cc-code").click();
    await expect(page.getByRole("listbox")).toBeVisible();
    await shot(page, "49-add-1-picker-open");

    for (const [n, service] of [[51, "water"], [52, "sewer"], [53, "trash"], [54, "fire"], [55, "solar"], [56, "battery"], [57, "electric"]] as const) {
      await startAdd(page, "base", free, service);
      await cont(page);
      if (service === "trash") {
        await page.getByLabel(/^Every class 1$/).fill("9.00");
        await page.getByLabel(/^Every class 2$/).fill("12.00");
      }
      await shot(page, `${n}-add-2-pricing-base-${service}`);
      if (service === "trash") {
        await cont(page);
        await shot(page, "65-add-3-review-base-trash");
      }
    }

    // 58 · 66 — a plan code priced by customer class.
    await startAdd(page, "plan", free);
    await page.locator("#cc-type").selectOption("one_time");
    await page.locator("#cc-priced-by").selectOption("class");
    await cont(page);
    await page.getByLabel(/^Amount 1$/).fill("25.00");
    await page.getByLabel(/^Amount 2$/).fill("50.00");
    await shot(page, "58-add-2-pricing-plan-by-class");
    await cont(page);
    await shot(page, "66-add-3-review-plan-by-class");

    // 59 — by asset size.
    await startAdd(page, "plan", free);
    await page.locator("#cc-type").selectOption("one_time");
    await page.locator("#cc-priced-by").selectOption("size");
    await cont(page);
    await shot(page, "59-add-2-pricing-plan-by-size");

    // 60 — one amount.
    await startAdd(page, "plan", free);
    await page.locator("#cc-type").selectOption("one_time");
    await page.locator("#cc-priced-by").selectOption("one");
    await cont(page);
    await page.getByLabel(/^Amount 1/).fill("2.95");
    await shot(page, "60-add-2-pricing-plan-one-amount");

    // 62 · 68 — a deposit by class.
    await startAdd(page, "plan", free);
    await page.locator("#cc-type").selectOption("refundable");
    await page.locator("#cc-priced-by").selectOption("class");
    await cont(page);
    await page.getByLabel(/^Amount 1$/).fill("150.00");
    await page.getByLabel(/^Amount 2$/).fill("500.00");
    await shot(page, "62-add-2-pricing-plan-deposit");
    await cont(page);
    await shot(page, "68-add-3-review-plan-deposit");

    // 63 · 69 · 71 — an other code, one amount; Create with no date.
    await startAdd(page, "other", free);
    await cont(page);
    await page.getByLabel(/^Amount 1/).fill("20.00");
    await shot(page, "63-add-2-pricing-other-one-amount");
    await cont(page);
    await shot(page, "69-add-3-review-other-one-amount");
    await page.getByRole("button", { name: "Create charge code" }).click();
    await expect(page.getByText("Pick a date.")).toBeVisible();
    await shot(page, "71-add-3-review-date-error");
  });

  test("73–75 · 79–83 · Edit a base and an other code; the reason error; saved", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/plans-rates/charge-codes/${ids.trash}/edit`);
    await expect(page.locator("#cc-code")).not.toHaveValue("", { timeout: 30_000 });
    await shot(page, "73-edit-1-details-base-BASE-T");
    await cont(page);
    await page.getByLabel(/^Every class 2$/).fill("13.00");
    await shot(page, "74-edit-2-pricing-base-BASE-T");
    await cont(page);
    await page.locator("#cc-effective-from").fill(iso(FUTURE));
    await page.locator("#cc-reason").fill("Board approved, walk");
    await shot(page, "75-edit-3-review-base-BASE-T");

    await page.goto(`/${tenant()}/plans-rates/charge-codes/${ids.app}/edit`);
    await expect(page.locator("#cc-code")).not.toHaveValue("", { timeout: 30_000 });
    await shot(page, "79-edit-1-details-other-APPFEE");
    await cont(page);
    await page.getByLabel(/^Amount 1/).fill("12.00");
    await shot(page, "80-edit-2-pricing-other-APPFEE");
    await cont(page);
    await page.locator("#cc-effective-from").fill(iso(FUTURE));
    await shot(page, "81-edit-3-review-other-APPFEE");
    await page.getByRole("button", { name: "Save change" }).click();
    // Billing cannot say whether the code was ever billed, so it counts as IN
    // USE (fail closed, DEF-079) and a reprice asks for a reason (BR-RAT-1016).
    await expect(page.getByText("Add a reason.")).toBeVisible({ timeout: 30_000 });
    await shot(page, "82-edit-3-review-reason-error");
    await page.locator("#cc-reason").fill("Board approved, walk");
    await page.getByRole("button", { name: "Save change" }).click();
    await expect(page.getByText(/saved\.$/).first()).toBeVisible({ timeout: 30_000 });
    await shot(page, "83-edit-3-review-saved");
  });

  test("50 · the picker with no free code (a battery base), last", async ({ page }) => {
    await signIn(page);
    const request = page.context().request;
    // The walk's own free codes (kind not yet set) would be offered for every
    // base; give them a kind first, so a service with no free code is real.
    const list = await (await request.get(api("/charges?q=FREE&per=100"))).json();
    for (const row of list.results as { id: string; kind: string | null }[]) {
      if (row.kind === null) {
        await configure(request, row.id, { kind: "other", charge_type: "one_time", amount_rule: "flat", amount: "1.00", size_amounts: [], effective_from: PAST });
      }
    }
    await page.goto(`/${tenant()}/plans-rates/charge-codes/new`);
    await page.locator("#cc-kind").selectOption("base");
    await page.locator("#cc-service").selectOption("battery");
    await page.locator("#cc-code").click();
    await expect(page.getByText("No free code. Add one in Settings.")).toBeVisible({ timeout: 15_000 });
    await shot(page, "50-add-1-picker-empty");
  });
});
