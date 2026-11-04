// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-114 — "NO HUMAN CAN PUT A UNIT ON A PLAN: the picker lists rate
//           SCHEDULES and the endpoint resolves rate PLANS, so every option the
//           screen offers is refused."
//           DEF-115 — "NO BILL IN THIS PRODUCT HAS EVER COME FROM A METER
//           READING — the read-import screen is unbuilt and meter_reads is
//           empty on a fully seeded stack."
// Stories:  US-MET-002/003 (S15 Assign plan) · US-MET-007/008/010 (S28 upload)
//           Screens: S15 · S25 · S28
// ───────────────────────────────────────────────────────
// The two defects, proved closed BY CLICKING — which is the only way either of
// them could have been found and the only way either can be shown fixed.
//
// PO ruling 2026-08-11: *"we ahve to prove against human clicking."* Both of
// these defects were invisible to ~2,000 unit tests and 21 gates, because both
// halves of each were correct on their own. So this file does what a clerk
// does: signs in with a password, opens a screen, picks the option the screen
// offers, and reads the answer off the page.
//
// WHAT EACH TEST ASSERTS, AND WHY THAT EXACT ASSERTION:
//
//   DEF-114 — it selects the FIRST option the picker itself offers, not an id
//     this file knows. That is the whole defect: every option the screen
//     offered came back "That plan wasn't found." A test that posted a plan id
//     of its own would have passed on the broken build.
//
//   DEF-115 — it uploads a reading through the wizard and then finds that
//     reading in the Reads list, WITH ITS UNIT. Before today the button that
//     starts this was disabled and said so.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

skipUnlessAppServer(test);

// The census FAILS a run that executed zero BROWSER assertions (DEF-057), and it
// counts a test as a browser test only when it carries this tag. These two are
// browser proofs and nothing else, so both describe blocks declare it. They do
// NOT use the `journey()` helper: neither is a catalog journey — they are the
// red-proofs for two defect rows.

test.describe("DEF-114 · a human can put a unit on a plan", { tag: [APP_SERVER_TAG] }, () => {
  test("S15: the plan the picker offers is the plan the endpoint accepts", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/premises/units`);

    // The first unit row's own "Assign plan" action.
    const assign = page.getByRole("button", { name: "Assign plan" }).first();
    await assign.waitFor();
    await assign.click();

    // BR-SHL-033: the plan picker is the searchable combobox — an input over a
    // listbox, opened by typing or by ArrowDown. Take whatever it offers: the
    // DEFECT was that everything it offered was refused, so a test that picked
    // an id of its own would have passed on the broken build.
    const picker = page.locator("#tariff_id");
    await picker.waitFor();
    await picker.press("ArrowDown");
    const options = page.locator('#tariff_id-listbox li[role="option"]');
    await expect
      .poll(async () => options.count(), { timeout: 15_000 })
      .toBeGreaterThan(0);
    const offeredLabel = (await options.first().textContent()) ?? "";
    expect(offeredLabel.trim(), "the picker offered no plan at all").not.toBe("");
    await options.first().click();

    await page.getByRole("button", { name: /Assign|Save/i }).last().click();

    // The refusal DEF-114 produced, in the words the user saw. Its absence is
    // the assertion; a 201 renders the modal closed and the screen refreshed.
    await expect(page.getByText("That plan wasn't found.")).toHaveCount(0);
    await expect(page.locator("#tariff_id")).toHaveCount(0, { timeout: 15_000 });
  });
});

test.describe("DEF-115 · a human can enter a meter reading", { tag: [APP_SERVER_TAG] }, () => {
  test.describe.configure({ mode: "serial" });

  /** One trip through S28, exactly as a clerk takes it. */
  async function uploadOneReading(page: Page, readDate: string, register: string): Promise<void> {
    await page.goto(`/${tenant()}/reads`);

    // DEF-115's own artefact: this control was DISABLED and carried the reason
    // "The upload wizard is not built in this release."
    const upload = page.getByRole("button", { name: "↑ Upload reads" });
    await upload.waitFor();
    await expect(upload).toBeEnabled();
    await upload.click();

    // Step 1 — tag the batch (BR-MET-014).
    await page.locator("#period_month").fill("2026-08-01");
    await page.locator("#source_detail").selectOption("walk_by");
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 2 — the published template's own columns, one flat-meter row.
    // M-7001 is the seeded Brazos Bend electric meter (EP-MET-03 §4).
    const csv =
      "meter_id,read_date,reading,channel,service,notes\n" +
      `M-7001,${readDate},${register},total,E,Access ok\n`;
    await page.locator("#reads-text").fill(csv);
    await page.getByRole("button", { name: "Stage the batch" }).click();
    await expect(page.getByText(/is staged with 1 row/)).toBeVisible({ timeout: 20_000 });
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 3 — the rules run server-side over the staged row.
    await page.getByRole("button", { name: "Run the rules" }).click();
    await expect(page.getByText("Rows in batch")).toBeVisible({ timeout: 20_000 });
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 4 — nothing to fix on a clean row; BR-MET-015 lets it through.
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 5 — certify and post. BR-MET-017: the stamp is on screen first.
    await expect(page.getByText("File hash (SHA-256)")).toBeVisible();
    // The native checkbox is visually replaced by the design system's own dot
    // (`CheckboxField` wraps it in `<label class="radio">`), so a human ticks it
    // by clicking the LABEL — and so does this. Calling `.check()` on the hidden
    // input would pass through a control no clerk can reach.
    await page.locator('label[for="certified"]').click();
    await expect(page.locator("#certified")).toBeChecked();
    await page.getByRole("button", { name: /Post batch/ }).click();

    // "N created · N failed", always — both figures, equal weight.
    await expect(page.getByText("The batch is posted.")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Readings created")).toBeVisible();
    await expect(page.getByText("Rows that did not become readings")).toBeVisible();
  }

  test("S25 → S28: upload reads is reachable, stages, validates and posts", async ({ page }) => {
    await signIn(page);
    await uploadOneReading(page, "2026-08-03", "42864");

    // The reading is REALLY on S25, at the meter it was entered against.
    await page.goto(`/${tenant()}/reads?tab=all`);
    await expect(page.getByText("M-7001").first()).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("42864.000000").first()).toBeVisible();
  });

  test("a SECOND reading produces a billable quantity — and it carries its unit", async ({
    page,
  }) => {
    // This is the sentence DEF-115 says has never been true: a quantity a bill
    // could be priced from, produced by a human entering a meter reading.
    //
    // It takes TWO readings, and that is the product being honest rather than a
    // gap: consumption is `(current − prior) × multiplier`, so a meter's FIRST
    // reading has no delta and `meter_reads.consumption` is correctly NULL. S25
    // renders that as "—" and NOT as 0 — a zero would claim the customer used
    // nothing. The second reading is where a usage figure exists, and CLAUDE.md
    // rule 3 says it may never appear without its unit.
    await signIn(page);
    await uploadOneReading(page, "2026-09-03", "43548");

    await page.goto(`/${tenant()}/reads?tab=all`);
    // 43548 − 42864 = 684 kWh, computed by the server at commit from the meter's
    // own unit. The screen prints the server's `usage_display` verbatim.
    await expect(page.getByText("684.000000 kWh").first()).toBeVisible({ timeout: 20_000 });
  });
});
