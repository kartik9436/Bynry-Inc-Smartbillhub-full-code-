// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-006 (TOU Option B — TC-9: the utility says which meter
//           register each window reads; TC-10 the negatives) · US-RAT-012
//           (the engine that consumes it)   Screens: S9 · S11
// Rules:    BR-RAT-067 (THE UTILITY STATES WHICH REGISTER — PO ruling
//           2026-08-16 closing OQ-236) · BR-RAT-064 (SUPERSEDED price rank) ·
//           BR-RAT-021 (reads arrive PRE-SPLIT per window)
// Golden:   GT-17 (= WE-1): 120 x 0.22 + 200 x 0.14 + 380 x 0.09 = 88.60,
//           unmoved by this change
// Tests:    this file · 06-backend/tests/test_us_rat_006_tc9_window_register.py
// Impacts:  apps/rating/models.TimeOfUseWindow.channel 🔒
// ───────────────────────────────────────────────────────
//
// HARD-WON LAW 6 — diff the RUNNING app, because no gate looks at rendered
// output. The PO's ruling of 2026-08-16 is a sentence about a SCREEN, verbatim:
// *"make the rate wizard say which register is which"*. A backend column, a
// serializer field and a passing unit test can all exist while the wizard shows
// a clerk nothing, which is exactly hard-won law 2 (built is not wired). So the
// proof has to be a browser looking at the wizard.
//
// WHAT WAS WRONG. A customer's electric meter reports three numbers a month —
// on-peak, mid-peak, off-peak — and a time-of-use tariff prices three windows.
// Nothing in the schema said which number belonged to which window, so the
// engine matched them BY PRICE RANK. Paired as the utility means it, the
// reference bill's electric usage is 88.60; paired the other way round the same
// meter bills 122.40 — a 38 % overcharge, and neither document looks unusual.
import { writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";

test.describe("the rate wizard says which register is which @app-server", () => {
  skipUnlessAppServer(test);

  test("US-RAT-006 TC-9: a utility states the register on S11 and reads it back on S9", async ({
    page,
  }) => {
    test.setTimeout(300_000);

    await signIn(page);

    // ── S9 · what the seeded utility already SAID ──────────────────────────
    // The demo tenant's Residential Electric — TOU carries three summer windows
    // and a winter all-day one, and `seed_demo._TOU_WINDOWS` now STATES a
    // register for each. The card is where a clerk checks what was said, so the
    // card has to print it.
    await page.goto(`/${tenant()}/plans-rates`);
    await page.getByRole("tab", { name: /Rate schedules/ }).click();
    await page.getByText("Residential Electric — TOU").first().waitFor();
    await page.waitForLoadState("networkidle");
    const card = await page.locator("body").innerText();
    writeFileSync("test-results/tou-register-card.txt", card);
    await page.screenshot({ path: "test-results/tou-register-card.png", fullPage: true });

    // The register column exists and every window names one. Asserting the
    // NAMES rather than the header, because a header with an empty column
    // underneath is the shape of defect this whole lane exists to end.
    expect(card).toContain("Meter register");
    expect(card).toContain("On-peak register");
    expect(card).toContain("Mid-peak register");
    expect(card).toContain("Off-peak register");
    // And no window on this schedule is unstated — the refusal string must be
    // absent, or the demo tenant cannot bill electricity.
    expect(card).not.toContain("Not stated");

    // ── S11 · the FIELD, on the wizard the PO named ────────────────────────
    // Straight to the wizard's own route (App.tsx `plans-rates/rates/new`), so
    // this assertion is about the FIELD and cannot go green or red on how the
    // Plans & Rates page happens to label its button today.
    await page.goto(`/${tenant()}/plans-rates/rates/new`);
    await page.locator("#rate-name").waitFor();
    await page.locator("#rate-name").fill("Register proof — TOU");
    await page.locator("#rate-service").selectOption("electric");
    await page.getByRole("button", { name: /^Continue$/ }).click();
    // Step 2 · Pricing formula. Choosing time-of-use draws the Time-of-use card.
    await page.locator("#rate-model").waitFor();
    await page.locator("#rate-model").selectOption("time_of_use");
    await page.getByRole("button", { name: /Add window/ }).first().click();
    await page.locator("#window-register-0").waitFor();

    const options = await page
      .locator("#window-register-0 option")
      .evaluateAll((nodes) =>
        nodes.map((node) => ({
          value: (node as HTMLOptionElement).value,
          label: (node as HTMLOptionElement).textContent ?? "",
        })),
      );
    writeFileSync("test-results/tou-register-picker.json", JSON.stringify(options, null, 2));
    await page.screenshot({ path: "test-results/tou-register-wizard.png", fullPage: true });

    // Exactly the three registers a meter reports (B2 r8 / BR-MET-059), plus
    // the leading empty "Choose a register" — and the empty one is SELECTED,
    // because the answer is the utility's to give. A pre-selected register
    // would be the price-rank inference wearing a different hat.
    expect(options.map((option) => option.value)).toEqual([
      "",
      "tou_on",
      "tou_mid",
      "tou_off",
    ]);
    expect(options[1].label).toContain("On-peak");
    expect(options[3].label).toContain("Off-peak");
    await expect(page.locator("#window-register-0")).toHaveValue("");

    // The clerk is told what the field is FOR, in words about their meter.
    const wizard = await page.locator("body").innerText();
    writeFileSync("test-results/tou-register-wizard.txt", wizard);
    expect(wizard).toContain("Which number on the meter this window is billed from");

    // And it is a real control that accepts an answer — a disabled or
    // read-only picker would render identically in a screenshot.
    await page.locator("#window-register-0").selectOption("tou_mid");
    await expect(page.locator("#window-register-0")).toHaveValue("tou_mid");
  });
});
