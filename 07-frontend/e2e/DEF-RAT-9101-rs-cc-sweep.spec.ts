// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-RAT-9101 (page actions top-right) · DEF-RAT-9102 (Base charges
//           From) · DEF-RAT-9103 (service inside + Filter) · DEF-RAT-9104
//           (charge-code wizard footer)
// Ruling:   decision log 2026-10-02 — page actions on a details view or a list
//           go top-right in the page head; the Add/Edit wizard keeps its footer.
//           PO 2026-10-02: "can you fix rate schedule and charge code ralted uI
//           issues" — a B14 sweep of every rate-schedule and charge-code screen.
// Run:      E2E_BASE_URL=http://127.0.0.1:<spa> \
//           E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//           npx playwright test e2e/DEF-RAT-9101-rs-cc-sweep.spec.ts
//           Needs a PRIVATE seeded database (`seed_demo`, tenant `brazosbend`).
// Shots:    08-qa/screens/rs-cc-ui-sweep-2026-10-02/<NN>-<screen>.png (1440)
//           and metrics.json — per screen, MEASURED at 1440 AND 1280: sideways
//           scroll, clipped text, the H1's size, what the page head holds, the
//           wizard footer's order and span, button heights, date and money
//           shapes, and anything that looks like a database id.
// ───────────────────────────────────────────────────────
/**
 * ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7 clause 2): a screenshot
 * proves nothing about 1280, so every screen is MEASURED at both widths and the
 * numbers are written beside the photo; and the app scrolls inside its own
 * frame, so overflow is read on `main.view` as well as on the document.
 */
import { mkdirSync, writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { baseUrl, expandInnerScroller, skipUnlessAppServer, tenant } from "./support/app";

const SHOTS = process.env.SHOTS ?? "../08-qa/screens/rs-cc-ui-sweep-2026-10-02";
const HEAD_SHOTS = process.env.HEAD_SHOTS ?? "../08-qa/screens/page-head-actions-2026-10-02";
const EMAIL = process.env.E2E_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.E2E_PASSWORD ?? "S3cure!passw0rd";
const STAMP = String(Date.now() % 100000);

test.use({ viewport: { width: 1440, height: 1000 }, actionTimeout: 20_000 });
test.describe.configure({ mode: "serial" });
skipUnlessAppServer(test);

const api = (path: string) => `${baseUrl()}/api/${tenant()}${path}`;
const metrics: Record<string, unknown> = {};

async function signIn(page: Page): Promise<void> {
  await page.goto(`/${tenant()}/signin`);
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.endsWith("/signin"), { timeout: 60_000 }),
    page.click('button[type="submit"]'),
  ]);
}

/** Everything a reader checks against B14, read off the rendered page. */
async function measure(page: Page): Promise<Record<string, unknown>> {
  return page.evaluate(() => {
    const main = document.querySelector<HTMLElement>("main.view") ?? document.body;
    const text = main.innerText;
    const h1 = main.querySelector("h1");
    const head = [...main.querySelectorAll(".page-header-actions button, .page-header-actions a")].map(
      (node) => (node.textContent ?? "").trim(),
    );
    const bar = main.querySelector<HTMLElement>("[data-wizard=actions]");
    let footer: Record<string, unknown> | null = null;
    if (bar !== null) {
      const layout = bar.parentElement?.closest<HTMLElement>("[data-rs-layout],[data-charge-layout]") ?? null;
      footer = {
        left: [...bar.querySelectorAll("[data-wizard=left] button")].map((n) => (n.textContent ?? "").trim()),
        right: [...bar.querySelectorAll(":scope > button")].map((n) => (n.textContent ?? "").trim()),
        autoMargins: [...bar.children].filter((n) => getComputedStyle(n).marginLeft === "auto" || n.classList.contains("mr-auto")).length,
        width: Math.round(bar.getBoundingClientRect().width),
        layoutWidth: layout === null ? null : Math.round(layout.getBoundingClientRect().width),
      };
    }
    const clipped: string[] = [];
    for (const node of main.querySelectorAll<HTMLElement>("label, th, td, button, a, span, p, dt, dd, h1, h2, h3, option")) {
      if (node.children.length > 0 && node.tagName !== "BUTTON") continue;
      const style = getComputedStyle(node);
      const hides = style.overflow === "hidden" || style.overflowX === "hidden" || style.textOverflow === "ellipsis";
      if (hides && node.scrollWidth > node.clientWidth + 1 && (node.textContent ?? "").trim() !== "") {
        clipped.push((node.textContent ?? "").trim().slice(0, 60));
      }
    }
    const heights = new Set<number>();
    for (const button of main.querySelectorAll<HTMLElement>("button")) {
      const r = button.getBoundingClientRect();
      if (r.height > 0 && (button.textContent ?? "").trim().length > 1) heights.add(Math.round(r.height));
    }
    return {
      h1: h1 === null ? null : { text: (h1.textContent ?? "").trim(), size: getComputedStyle(h1).fontSize },
      head,
      bottomBar: main.querySelectorAll("[data-rs-actions]").length,
      quickChips: main.querySelectorAll("[data-quick-filter]").length,
      footer,
      sideways: {
        document: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        main: main.scrollWidth > main.clientWidth + 1,
        mainScroll: main.scrollWidth,
        mainClient: main.clientWidth,
        // DEF-RAT-9112: a list scrolls inside its OWN wrapper, which neither
        // number above can see — measured here, not assumed.
        table: [...main.querySelectorAll<HTMLElement>("table")].some(
          (table) => table.parentElement !== null && table.parentElement.scrollWidth > table.parentElement.clientWidth + 1,
        ),
      },
      clipped: clipped.slice(0, 12),
      buttonHeights: [...heights].sort((a, b) => a - b),
      dates: [...new Set(text.match(/\b\d{2}\/\d{2}\/\d{4}\b|\b\d{1,2}-[A-Z][a-z]{2}-\d{2}\b|\b[A-Z][a-z]{2} \d{1,2}, \d{4}\b|\b\d{4}-\d{2}-\d{2}\b/g) ?? [])].slice(0, 8),
      longMoney: [...new Set(text.match(/\$\d[\d,]*\.\d{3,}/g) ?? [])].slice(0, 8),
      uuids: (text.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g) ?? []).length,
      epoch: text.includes("01/01/2000") || text.includes("2000-01-01"),
    };
  });
}

/** Measure at 1440 and 1280, photograph at 1440. */
async function capture(page: Page, name: string, extraDir?: string): Promise<void> {
  mkdirSync(SHOTS, { recursive: true });
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(400);
  const at1440 = await measure(page);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.waitForTimeout(300);
  const at1280 = await measure(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.waitForTimeout(300);
  metrics[name] = { at1440, at1280 };
  await expandInnerScroller(page);
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
  if (extraDir !== undefined) {
    mkdirSync(extraDir, { recursive: true });
    await page.screenshot({ path: `${extraDir}/${name}.png`, fullPage: true });
  }
  writeFileSync(`${SHOTS}/metrics.json`, JSON.stringify(metrics, null, 2));
}

interface Row {
  id: string;
  name: string;
  code?: string;
  service: string;
  structure?: string | null;
  kind?: string | null;
}

async function list(page: Page, path: string): Promise<Row[]> {
  const response = await page.request.get(api(path));
  expect(response.status(), await response.text()).toBe(200);
  const body = await response.json();
  return (body.results ?? body) as Row[];
}

const next = (page: Page) =>
  page.locator("[data-wizard=actions]").getByRole("button", { name: /^Continue|^Next/ }).click();

test("rate schedules — list, filter, details tabs, Add and Edit steps", { tag: "@app-server" }, async ({ page }) => {
  test.setTimeout(600_000);
  await signIn(page);
  const rates = `/${tenant()}/plans-rates/rates`;
  await page.goto(rates);
  await expect(page.locator("table.data-table tbody tr").first()).toBeVisible({ timeout: 60_000 });
  await capture(page, "01-rs-list", HEAD_SHOTS);
  await page.locator("details > summary").first().click();
  await capture(page, "02-rs-list-filter-open");
  await page.goto(`${rates}?f.service=water`);
  await expect(page.locator("table.data-table tbody tr").first()).toBeVisible();
  await capture(page, "03-rs-list-service-tag");
  await page.goto(`${rates}?q=ZZZ-NO-SUCH`);
  await page.waitForTimeout(800);
  await capture(page, "04-rs-list-no-results");

  const cards = await list(page, "/rate-schedules?per=100");
  const water = cards.find((c) => c.service === "water" && c.structure === "tiered") ?? cards[0];
  let n = 5;
  for (const tab of ["overview", "rates", "plans", "audit"]) {
    await page.goto(`${rates}/${water.id}?tab=${tab}`);
    await expect(page.getByRole("tab", { selected: true })).toBeVisible({ timeout: 30_000 });
    await capture(page, `${String(n).padStart(2, "0")}-rs-view-${tab}`, HEAD_SHOTS);
    n += 1;
  }
  const battery = cards.find((c) => c.service === "battery") ?? cards.find((c) => c.service !== "water");
  if (battery !== undefined) {
    await page.goto(`${rates}/${battery.id}?tab=rates`);
    await expect(page.getByRole("tab", { selected: true })).toBeVisible({ timeout: 30_000 });
    await capture(page, "09-rs-view-rates-backfilled", HEAD_SHOTS);
  }

  // Add — the three steps, the step-1 errors.
  await page.goto(rates);
  await page.locator(".page-header-actions").getByRole("button", { name: /New rate schedule/ }).click();
  await expect(page.locator("[data-step=details]")).toBeVisible({ timeout: 30_000 });
  await capture(page, "10-rs-add-1-details");
  await next(page);
  await capture(page, "11-rs-add-1-errors");
  await page.fill("#rs-name", `Sweep flat ${STAMP}`);
  await page.selectOption("#rs-service", "electric");
  await page.selectOption("#rs-structure", "flat");
  const offered = () =>
    page
      .locator("#rs-unit option:not([disabled])")
      .evaluateAll((options) => options.map((o) => (o as HTMLOptionElement).value).filter(Boolean));
  await expect.poll(async () => (await offered()).length, { timeout: 15_000 }).toBeGreaterThan(0);
  if ((await page.inputValue("#rs-unit")) === "") await page.selectOption("#rs-unit", (await offered())[0]);
  await page.fill("#rs-base-code", "BASE-E");
  await page.getByRole("option", { name: /^BASE-E\b/ }).first().click();
  await next(page);
  await expect(page.locator("[data-step=pricing]")).toBeVisible();
  await capture(page, "12-rs-add-2-pricing");
  await next(page);
  await expect(page.locator("[data-step=review]")).toBeVisible();
  await capture(page, "13-rs-add-3-review");

  // Edit — Change the rate, step 1 and 3.
  await page.goto(`${rates}/${water.id}/edit`);
  await expect(page.locator("[data-step=details]")).toBeVisible({ timeout: 30_000 });
  await capture(page, "14-rs-edit-1");
  await next(page);
  await capture(page, "15-rs-edit-2");
  await next(page);
  await capture(page, "16-rs-edit-3");
});

test("charge codes — list, details by kind, Add and Edit steps", { tag: "@app-server" }, async ({ page }) => {
  test.setTimeout(600_000);
  await signIn(page);
  const codes = `/${tenant()}/plans-rates/charge-codes`;
  await page.goto(codes);
  await expect(page.locator("[data-kind-chips]")).toBeVisible({ timeout: 60_000 });
  await capture(page, "20-cc-list", HEAD_SHOTS);
  await page.locator("details > summary").first().click();
  await capture(page, "21-cc-list-filter-open");
  await page.goto(`${codes}?q=ZZZ-NO-SUCH`);
  await page.waitForTimeout(800);
  await capture(page, "22-cc-list-no-results");

  const rows = await list(page, "/charges?per=200");
  let n = 23;
  for (const kind of ["base", "plan", "other"]) {
    const row = rows.find((r) => r.kind === kind);
    if (row === undefined) continue;
    await page.goto(`${codes}/${row.id}`);
    await expect(page.locator('[data-screen="CHG-01"]')).toBeVisible({ timeout: 30_000 });
    const tabs = await page.getByRole("tab").evaluateAll((nodes) => nodes.map((x) => x.getAttribute("data-tab") ?? x.id));
    await capture(page, `${n}-cc-view-${kind}-overview`, kind === "base" ? HEAD_SHOTS : undefined);
    n += 1;
    for (const tab of tabs.slice(1)) {
      if (!tab) continue;
      await page.goto(`${codes}/${row.id}?tab=${tab}`);
      await expect(page.locator('[data-screen="CHG-01"]')).toBeVisible({ timeout: 30_000 });
      await capture(page, `${n}-cc-view-${kind}-${tab}`);
      n += 1;
    }
  }

  // Add — step 1, its errors.
  await page.goto(codes);
  await page.locator(".page-header-actions").getByRole("button", { name: /New charge code/ }).click();
  await expect(page.locator("#cc-kind")).toBeVisible({ timeout: 30_000 });
  await capture(page, "40-cc-add-1");
  // Continue is disabled until a kind is chosen, so step 1 has no error state
  // to photograph empty; pick a kind and photograph the step as it grows.
  const kinds = await page
    .locator("#cc-kind option")
    .evaluateAll((options) => options.map((o) => (o as HTMLOptionElement).value).filter(Boolean));
  await page.locator("#cc-kind").selectOption(kinds[0]);
  await capture(page, "41-cc-add-1-kind-chosen");

  // Edit a base code — the three steps.
  const base = rows.find((r) => r.kind === "base");
  if (base !== undefined) {
    await page.goto(`${codes}/${base.id}/edit`);
    await expect(page.locator("[data-charge-layout]")).toBeVisible({ timeout: 30_000 });
    await capture(page, "42-cc-edit-1");
    await next(page);
    await capture(page, "43-cc-edit-2");
    await next(page);
    await capture(page, "44-cc-edit-3");
  }
});
