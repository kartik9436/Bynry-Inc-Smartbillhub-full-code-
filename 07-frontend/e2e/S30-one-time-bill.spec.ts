// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-010 · US-BIL-011 · US-BIL-012 · US-BIL-013 · US-BIL-014
//           Screens: S30 (One-time bill tab)
// ───────────────────────────────────────────────────────
// S30's One-time bill tab in a real browser, asserting the things that were
// ACTUALLY wrong — not "the page rendered".
//
// The defect this closes is hard-won law 2, five times over: `first_bill.py`,
// `final_bill.py`, `single.py`, `backbill.py` and `penalty.py` had shipped
// complete and tested and were reachable from nothing but their own test files.
// The tab itself EXISTED in `BILLING_TABS` and rendered an "arrives with"
// placeholder, so a check that merely asserted "the tab is there" would have
// passed against the broken product every day this week.
//
// So this asserts, in order:
//
//   1. **The tab reaches a real screen**, not the placeholder it used to show.
//      The placeholder is the thing that was there before; its ABSENCE is the
//      whole of "built is now wired".
//   2. **The kind select offers the five kinds** — including the two the
//      prototype does not have (first bill, penalty) and NOT the one that has
//      no story (Deposit invoice, hard-won law 8).
//   3. **There is NO amount input and no "+ Add line" button anywhere on the
//      screen.** BR-BIL-020 supersedes the prototype's editable line table in
//      writing, and this is the assertion that a later lane "restoring the
//      prototype" would fail.
//   4. **Both money gaps are stated on the screen before a clerk drafts** —
//      OQ-241 (the bill cannot be sent) and OQ-242 (a partial window charges a
//      full base charge). Both are SERVED by the API, so this also proves the
//      route is live and answering: the browser cannot compose these sentences
//      for itself.
import { expect, test } from "@playwright/test";

import { bootApp, signIn } from "./support/app";

test("S30 · the One-time bill tab reaches five engines, offers no amount field, and states both money gaps @app-server", async ({
  page,
}) => {
  await signIn(page);
  await bootApp(page);

  await page.goto("/brazosbend/billing/one-time");

  // 1 · The screen is REACHED. `ModulePlaceholder` renders the W0 scaffold
  // marker, which is what an unrouted path shows (DEF-152/DEF-129 shape).
  await expect(page.locator("[data-not-built-yet]")).toHaveCount(0);

  // The tab is in S30's strip, so a human gets here by clicking.
  await expect(page.getByRole("tab", { name: /one-time bill/i })).toBeVisible();

  // 2 · The kind select. Five options, and the two the prototype lacks are
  // among them because both have stories and complete engines.
  const kind = page.locator("#one_time_kind");
  await expect(kind).toBeVisible();
  await expect(kind.locator("option")).toHaveCount(5);
  await expect(kind.locator("option", { hasText: /final/i })).toHaveCount(1);
  await expect(kind.locator("option", { hasText: /first bill/i })).toHaveCount(1);
  await expect(kind.locator("option", { hasText: /penalty|theft/i })).toHaveCount(1);
  // The prototype's fourth kind has NO story (law 8) and is not offered.
  await expect(kind.locator("option", { hasText: /deposit invoice/i })).toHaveCount(0);

  // 3 · BR-BIL-020, in the DOM. The prototype draws an editable amount per line
  // and a "+ Add line" button; neither exists here and neither may return.
  await expect(page.getByRole("button", { name: /\+ add line/i })).toHaveCount(0);
  await expect(page.locator("#one_time_amount")).toHaveCount(0);
  await expect(page.locator('input[name="amount"]')).toHaveCount(0);

  // 4 · The account picker and the period are the step-1 fields the tab needs.
  await expect(page.locator("#one_time_account_query")).toBeVisible();
  await expect(page.locator("#one_time_account_id")).toBeVisible();
  await expect(page.locator("#one_time_period_start")).toBeVisible();
  await expect(page.locator("#one_time_period_end")).toBeVisible();

  // 5 · Choosing the catch-up kind swaps the ONE period for a LIST of them.
  // `backbill.py` refuses to invent a cadence, and the screen must not either:
  // 18 kgal priced as one period puts 13 kgal in the top tier where six monthly
  // groups put 6 — $25.00 on one service, on a bill that foots either way.
  await kind.selectOption("backbill");
  await expect(page.locator("#one_time_sub_start_0")).toBeVisible();
  await expect(page.locator("#one_time_reason_code")).toBeVisible();
  await page.getByRole("button", { name: /add another period/i }).click();
  await expect(page.locator("#one_time_sub_start_1")).toBeVisible();
});

test("S30 · the two money gaps are SERVED and rendered before a clerk drafts @app-server", async ({
  page,
}) => {
  await signIn(page);
  await bootApp(page);
  await page.goto("/brazosbend/billing/one-time");

  // Drive the real preview against the real engines: pick the first account the
  // server offers, state a window, and ask what the customer would owe.
  await page.locator("#one_time_account_query").fill("AC");
  const account = page.locator("#one_time_account_id");
  await expect(account.locator("option")).not.toHaveCount(1, { timeout: 15_000 });
  await account.selectOption({ index: 1 });
  await page.locator("#one_time_period_start").fill("2026-07-01");
  await page.locator("#one_time_period_end").fill("2026-07-31");
  await page.getByRole("button", { name: /see what they'd owe/i }).click();

  // The gap notes come from the SERVER's `unavailable` list, so their presence
  // proves the route is mounted and answering — the browser cannot compose
  // these sentences. Both are real money and both are open questions.
  const gaps = page.locator('[data-bil="gaps"]');
  await expect(gaps).toBeVisible({ timeout: 20_000 });
  await gaps.locator("summary").click();
  // OQ-241 — a one-time bill drafts and cannot be sent.
  await expect(gaps.getByText(/cannot be ISSUED|due date/i).first()).toBeVisible();
  // OQ-242 — a partial window charges a full period's base charge.
  await expect(gaps.getByText(/13\.49/)).toBeVisible();
});
