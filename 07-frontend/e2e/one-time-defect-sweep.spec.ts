// ── Trace ──────────────────────────────────────────────
// Journey:  the one-time bill defect sweep, 2026-10-01
//           · 08-qa/01-e2e/journeys/one-time-defect-sweep-2026-10-01.md
// Request:  PO 2026-10-01, verbatim: "can you check these bugs based on actual
//           code - 26 older one-time bugs from 29–30 Sept still marked open …
//           Each needs re-checking on today's build, then either closed with
//           proof or fixed. and fix it"
// World:    a COPY of J75's `sbh_six` (Six Rivers Utility, eight one-time bills
//           already sent) — never `sbh_six` itself.
// ───────────────────────────────────────────────────────
//
//   E2E_TENANT=sixrivers E2E_EMAIL=priya@sixriversutility.com \
//   E2E_BASE_URL=http://127.0.0.1:<web> npx playwright test e2e/one-time-defect-sweep.spec.ts --workers=1
//
// Each test reproduces ONE clerk-facing claim of a September row on today's
// build and records what the screen actually says, so the row is closed on a
// screenshot rather than on a reading of the code.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { expandInnerScroller, signIn, skipUnlessAppServer, tenant } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

const WIDTH = Number(process.env.E2E_VIEWPORT ?? "1440");
const SHOTS = "../08-qa/screens/one-time-sweep-2026-10-01";
const RESULTS = `${SHOTS}/sweep-results.json`;
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const ISO_STAMP = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

function note(key: string, value: unknown): void {
  mkdirSync(SHOTS, { recursive: true });
  let all: Record<string, unknown> = {};
  try {
    all = JSON.parse(readFileSync(RESULTS, "utf8")) as Record<string, unknown>;
  } catch {
    all = {};
  }
  all[key] = value;
  writeFileSync(RESULTS, `${JSON.stringify(all, null, 2)}\n`);
}

async function shot(page: Page, name: string): Promise<void> {
  await page.waitForTimeout(400);
  await expandInnerScroller(page);
  await page.screenshot({ path: `${SHOTS}/${WIDTH}-${name}.png`, fullPage: true });
}

async function openKind(page: Page, kind: string): Promise<void> {
  await page.goto(`/${tenant()}/billing/one-time?kind=${kind}`);
  await expect(page.locator("[data-screen=one-time-bill]")).toBeVisible({ timeout: 30_000 });
}

async function pickAccount(page: Page, term: string, unit: string): Promise<void> {
  const combo = page.getByRole("combobox", { name: /Find account/ });
  await combo.fill(term);
  await expect(page.getByRole("option").first()).toBeVisible({ timeout: 20_000 });
  await page
    .getByRole("option")
    .filter({ hasText: new RegExp(`Unit ${unit}(?:Active|Closed|Pending|\\s|,|$)`) })
    .first()
    .click();
  await expect(page.locator("[data-facts=otb-account] [data-fact=plan]")).not.toContainText("—", {
    timeout: 15_000,
  });
}

async function continueStep(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.waitForTimeout(1500);
}

async function onStep(page: Page, n: number, timeout = 45_000): Promise<boolean> {
  try {
    await expect(page.locator(`[data-wizard-step="${n}"][data-state=active]`)).toBeVisible({ timeout });
    return true;
  } catch {
    return false;
  }
}

/** Words a clerk reads in step 1's content (the drawn panels), not the frame. */
async function stepWords(page: Page): Promise<{ words: number; text: string }> {
  // A closed <select>'s options are not read on screen, but innerText counts
  // every one — so the count walks the content's text WITHOUT them.
  const text = await page.locator("[data-wizard=content]").evaluate((root) => {
    const copy = root.cloneNode(true) as HTMLElement;
    copy.querySelectorAll("option, select").forEach((node) => node.remove());
    document.body.appendChild(copy);
    const shown = copy.innerText;
    copy.remove();
    return shown;
  });
  const words = text.split(/\s+/).filter((w) => /[A-Za-z0-9$]/.test(w)).length;
  return { words, text: text.replace(/\s+/g, " ").trim() };
}

test.describe(`one-time defect sweep, at ${WIDTH}`, { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);
  test.setTimeout(240_000);

  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: WIDTH, height: 1000 });
    await signIn(page);
  });

  test("7924 / 7960 — the Billing tab strip's One-time bill opens the redrawn page", async ({ page }) => {
    await page.goto(`/${tenant()}/billing`);
    await page.getByRole("tab", { name: "One-time bill" }).or(page.getByRole("link", { name: "One-time bill" })).first().click();
    await expect(page.locator("[data-screen=one-time-bill]")).toBeVisible({ timeout: 30_000 });
    const path = new URL(page.url()).pathname;
    note("door", { path, rail: await page.locator("[data-wizard=rail]").innerText() });
    expect(path).toBe(`/${tenant()}/billing/one-time`);
    await shot(page, "01-door");
  });

  test("7927 / 7928 — step 1: one account control; words per kind", async ({ page }) => {
    const words: Record<string, number> = {};
    const texts: Record<string, string> = {};
    for (const kind of ["interim", "first", "final", "backbill", "penalty", "fee"]) {
      await openKind(page, kind);
      await pickAccount(page, "Femi", "6");
      await page.waitForTimeout(800);
      const counted = await stepWords(page);
      words[kind] = counted.words;
      texts[kind] = counted.text;
      const panel = page.locator("[data-otb-panel=account]");
      note(`account-controls-${kind}`, {
        comboboxes: await panel.getByRole("combobox").count(),
        textboxes: await panel.getByRole("textbox").count(),
      });
      if (kind === "interim" || kind === "backbill") await shot(page, `02-step1-${kind}`);
    }
    note("step1-words", words);
    note("step1-text", texts);
    const panel = page.locator("[data-otb-panel=account]");
    expect(await panel.getByRole("combobox").count()).toBe(1);
  });

  test("8086 / 8087 / 8076 — every step-1 problem at once, each on its own field", async ({ page }) => {
    await openKind(page, "backbill");
    await pickAccount(page, "Femi", "6");
    await page.locator("#bill_date").fill("");
    await page.locator("#due_days").fill("");
    await continueStep(page);
    const banner = page.locator("[data-otb-problems]");
    await expect(banner).toBeVisible();
    const text = (await banner.innerText()).trim();
    note("problems", { text, reason_field: await page.locator("[aria-invalid=true]").count() });
    expect(text).toMatch(/reason/i);
    expect(text).toMatch(/bill date/i);
    expect(text).not.toMatch(/Choose an account and a period/);
    expect(text).not.toMatch(/cycle/i);
    await shot(page, "03-problems-at-once");
  });

  test("7967 — an already-billed period names the bill by its number", async ({ page }) => {
    await openKind(page, "interim");
    await pickAccount(page, "Ana", "1");
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-30");
    await continueStep(page);
    const banner = page.locator("[data-otb-duplicate]");
    await expect(banner).toBeVisible({ timeout: 30_000 });
    const text = (await banner.innerText()).trim();
    note("duplicate", text);
    expect(text).toMatch(/BL-\d{4}-\d{6}/);
    expect(text).not.toMatch(ISO_STAMP);
    expect(text).not.toMatch(UUID);
    await shot(page, "04-already-billed");
  });

  test("7968 — a first bill is priced from the move-in date the clerk sets, so the not-a-first-bill refusal cannot arise", async ({ page }) => {
    await openKind(page, "first");
    await pickAccount(page, "Femi", "6");
    await page.locator("#period_start").fill("2026-09-01");
    await page.locator("#period_end").fill("2026-09-20");
    await continueStep(page);
    const shown = (await page.locator("[data-screen=one-time-bill]").innerText()).replace(/\s+/g, " ");
    const refusal =
      (await page.locator("[data-wizard=blocked]").count()) > 0
        ? (await page.locator("[data-wizard=blocked]").first().innerText()).trim()
        : "";
    const reached = await onStep(page, 2, 30_000);
    note("first-from-clerk-move-in", { refusal, onStep2: reached });
    expect(reached, `step 1 passes — ${refusal}`).toBe(true);
    expect(shown).not.toMatch(/Check the cycle and dates, then retry/);
    expect(shown).not.toMatch(UUID);
    await shot(page, "05-first-bill-move-in-set-by-clerk");
  });

  test("7961 / 7962 / 7929 / 8075 — a fee bill walks every step and is sent from the screen", async ({ page }) => {
    await openKind(page, "fee");
    await pickAccount(page, "Ben", "2");
    const select = page.locator("#charge_code");
    await expect(select.locator("option", { hasText: /reconnect/i }).first()).toBeAttached({ timeout: 20_000 });
    const options = await select.locator("option").allInnerTexts();
    const recon = options.find((o) => /reconnect/i.test(o));
    expect(recon, `a reconnection fee is offered: ${options.join(" | ")}`).toBeTruthy();
    await select.selectOption({ label: recon as string });
    await continueStep(page);
    expect(await onStep(page, 2), "Account → Services").toBe(true);
    await shot(page, "06-fee-step2");
    await continueStep(page);
    expect(await onStep(page, 3), "Services → Review").toBe(true);
    await expect(page.locator("[data-otb-bill]")).toBeVisible();
    note("review-controls", await page.locator("[data-wizard=actions] button").allInnerTexts());
    await shot(page, "07-fee-review");
    await continueStep(page);
    expect(await onStep(page, 4, 60_000), "Review → Send").toBe(true);
    const send = page.getByRole("button", { name: /^Send .* bill$/ });
    await expect(send).toBeDisabled();
    for (const id of ["compliance", "email_mandate", "sms_mandate", "autopay_mandate", "final"]) {
      await page.locator(`#otb-confirm-${id}`).check({ force: true });
    }
    await expect(send).toBeEnabled();
    await shot(page, "08-fee-send");
    await send.click();
    await expect(page.locator("[data-otb-sent]")).toBeVisible({ timeout: 60_000 });
    const sentText = (await page.locator("[data-otb-sent]").innerText()).trim();
    note("fee-sent", sentText);
    expect(sentText).toMatch(/Bill .+ sent/);
    await shot(page, "09-fee-sent");
  });
});
