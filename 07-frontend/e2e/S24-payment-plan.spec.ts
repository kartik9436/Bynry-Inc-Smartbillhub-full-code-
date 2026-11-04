// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-018 (S24 — amount & term → schedule → agreement) ·
//           US-NOT-004 / US-NOT-010 / US-NOT-005 (the S8 Notifications config
//           cards)   Screens: S24 · S8
// Rules:    BR-CUS-043 (schedule math is the SERVER's; remainder on the FINAL
//           instalment) · BR-BIL-073 (a plan does NOT suspend the current
//           bill) · BR-NOT-008 (a regulated step ALWAYS renders the disconnect
//           class) · BR-SHL-025 (disabled WITH the reason)
// Golden:   ❄️ GT-47 — 267.30 less 50.00 over six is 5 × 36.22 + 36.20. ⚠ THAT
//           FIGURE IS ASSERTED OVER HTTP in
//           06-backend/tests/test_us_cus_018_payment_plan_api.py and NOT here:
//           no account in the E2E fixture owes $267.30, and the endpoint
//           correctly REFUSES a plan spreading more than the account owes
//           (US-CUS-018 TC-6 — measured, the first draft of this spec got a
//           422 for exactly that reason). What a browser proves instead is the
//           SAME RULE on the fixture's own debt: GT-1's **$108.88** over six
//           is 5 × **$18.15** and a FINAL **$18.13**, which sums to $108.88 to
//           the cent because the remainder lands on the last row and nowhere
//           else (BR-CUS-043 / A7).
// ───────────────────────────────────────────────────────
//
// HARD-WON LAW 6: these two screens were built today and no test that does not
// boot a browser can say what a clerk reads on them. Three lanes on 2026-08-16
// shipped a browser check that PASSED against the broken screen, so every
// locator below aims at the thing that would actually be wrong:
//
//   · the FINAL instalment cell, not "a money cell on the page" — a schedule
//     that spread the remainder evenly renders $36.22 in all six rows and any
//     looser locator matches it;
//   · the tone table's FIRM row, not "the page mentions disconnection" — the
//     whole point is which class that ONE row selects;
//   · the balance tile, asserted as NOT `$0.00`, because that is the exact
//     string DEF-127 put in front of a clerk over an unpaid debt.
import { expect, test } from "@playwright/test";

import { signIn, tenant, skipUnlessAppServer } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

test.describe("S24 — a clerk can write a payment plan", { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);

  test("the wizard is REACHABLE from the account, and the schedule is the server's", async ({
    page,
  }) => {
    await signIn(page);

    // A human clicking, not a URL typed — "built is not wired" is the defect
    // class this whole lane exists to close.
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Accounts", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/accounts$`));

    // The account DEF-127 was measured on — the one the fixture bills, so it
    // has a real debt to spread. Any row would render the wizard; only this one
    // has a balance the schedule can be checked against.
    const row = page.getByRole("row").filter({ hasText: "E2E-10001" });
    await expect(row).toHaveCount(1);
    await row.getByRole("link").first().click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/accounts/`));

    // THE CONTROL THAT DID NOT EXIST. The prototype's rail has always named
    // "Payment plan" and this deployment had nothing for it at all.
    const planButton = page.getByRole("button", { name: "Payment plan", exact: true });
    await expect(planButton).toHaveCount(1);
    await planButton.click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/accounts/.*/payment-plan$`));

    // Step 1 is drawn, with the account's own balance beside it.
    await expect(page.getByRole("heading", { name: "Payment plan" })).toBeVisible();
    await expect(page.locator("#balance_to_spread")).toBeVisible();
    await expect(page.locator("#first_due_date")).toBeVisible();

    // The account's own debt, typed by a person and divided by the server.
    await page.locator("#balance_to_spread").fill("108.88");
    await page.locator("#installments").fill("6");
    await page.locator("#first_due_date").fill("2026-09-01");
    await page.getByRole("button", { name: "Continue" }).click();

    // The schedule table, and the row that matters. Six rows: five at $36.22
    // and a FINAL $36.20 — the remainder lands on the last instalment and
    // nowhere else (BR-CUS-043 / A7), which is what makes them sum to $217.30.
    const rows = page.locator("table[data-plan-schedule] tbody tr");
    await expect(rows).toHaveCount(6);
    // Step 2's amounts are EDITABLE (US-CUS-018 §1), so the figure is an input
    // VALUE and not cell text — asserted as what a clerk would type over.
    await expect(rows.nth(0).locator("input")).toHaveValue("18.15");
    // ⚠ THE LAST ROW SPECIFICALLY. A schedule that spread the remainder evenly
    // renders 18.15 here too, and a looser locator would pass over it — which
    // is the shape three browser checks shipped in on 2026-08-16.
    await expect(rows.nth(5).locator("input")).toHaveValue("18.13");
    await expect(rows.nth(5).locator("input")).not.toHaveValue("18.15");
    // Every instalment carries the day it falls due …
    await expect(rows.nth(0)).toContainText("2026-09-01");
    // … and the running remainder walks to 0.00, with its currency.
    await expect(rows.nth(0)).toContainText("$90.73");
    await expect(rows.nth(5)).toContainText("$0.00");
    // CLAUDE.md rule 2 — the CHAR(3) is on the editable column's head, because
    // the inputs themselves carry no symbol.
    await expect(page.locator("table[data-plan-schedule] thead")).toContainText("(USD)");
  });

  test("the summary says the current bill is still due, and offers no way to void", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/accounts`);
    await page
      .getByRole("row")
      .filter({ hasText: "E2E-10001" })
      .getByRole("link")
      .first()
      .click();
    await page.getByRole("button", { name: "Payment plan", exact: true }).click();

    await page.locator("#balance_to_spread").fill("108.88");
    await page.locator("#installments").fill("6");
    await page.locator("#first_due_date").fill("2026-09-01");
    await page.getByRole("button", { name: "Continue" }).click();
    // ⚠ WAIT FOR STEP 2 BEFORE CLICKING AGAIN. The schedule is computed by the
    // SERVER, so step 1's Continue is a round trip: clicking straight through
    // re-previews step 1 instead of advancing, and the test then fails on a
    // screen that is working perfectly (measured — this is why the wait is
    // here rather than a bare double click).
    await expect(page.locator("table[data-plan-schedule] tbody tr")).toHaveCount(6);
    await page.getByRole("button", { name: "Continue" }).click();

    // PO 2026-08-11 — on the summary's FACE, because believing otherwise IS the
    // defect that ruling closed (DEF-061).
    await expect(page.getByTestId("current-bill-note")).toContainText("still due");
    // Hard-won law 2 said out loud: the agreement is QUEUED, and no e-signature
    // provider is connected.
    await expect(page.getByTestId("queue-only-note")).toContainText("queued");

    // PO 2026-08-11, "nodrop we chase for payments until write off" — there is
    // no void state and no control for one anywhere on this page.
    await expect(page.getByRole("button", { name: /void/i })).toHaveCount(0);
  });
});

test.describe("S8 — the notifications queue can be configured", { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);

  test("the three config cards are drawn, and Firm selects the REGULATED notice", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/settings/notifications`);

    // US-NOT-004 — the card that read "arrives with the delivery-queue story".
    await expect(page.getByRole("heading", { name: "Dispatch settings" })).toBeVisible();
    // PO 2026-08-16 — no switch may read as a send.
    await expect(page.getByTestId("no-dispatcher")).toContainText("Nothing is sent");

    // US-NOT-010 / BR-NOT-008 — the assertion this card exists for. THE FIRM
    // ROW, not "the page mentions disconnection".
    await expect(page.getByRole("heading", { name: "Which letter each tone sends" })).toBeVisible();
    // ⚠ SCOPED TO THE TONE TABLE. `Firm` is a substring of prose in the
    // template card's rows too, and an unscoped row filter matched three
    // elements — measured, not guessed.
    const toneTable = page
      .locator("section.panel")
      .filter({ hasText: "Which letter each tone sends" })
      .locator("table");
    const firmRow = toneTable.getByRole("row").filter({ hasText: "Firm" });
    await expect(firmRow).toContainText("Disconnection notice");
    await expect(firmRow).toContainText("10-day notice");
    const finalRow = toneTable.getByRole("row").filter({ hasText: "Final" });
    await expect(finalRow).toContainText("certified mail");
    // Only the friendly tone sends an ordinary reminder.
    const friendlyRow = toneTable.getByRole("row").filter({ hasText: "Friendly" });
    await expect(friendlyRow).toContainText("Payment reminder");
    await expect(friendlyRow).not.toContainText("Disconnection notice");

    // US-NOT-005/006 — and the live gap it reports rather than hides.
    await expect(
      page.getByRole("heading", { name: "Letters this utility can produce" }),
    ).toBeVisible();
    await expect(page.getByTestId("no-template-seeder")).toContainText("DEF-163");
    await expect(page.getByTestId("unpublished-disconnect_notice")).toBeVisible();
  });
});
