// ── Trace ──────────────────────────────────────────────
// Change:  CR-046 wave E (E1 · E2 · E3) — the import wizard's screens, after
//          the identifier stopped coming from the uploaded file.
// Screens: WFL-01 stages 1, 2 and 4 · /{tenant}/assets/import?target=assets_meters
// Rules:   CR-046 step 5 shape (1)-(5) · BR-MET-210 / CR-042 (two modes, at
//          step 1) · BR-AST-026 · OQ-840 CLOSED (Inventory/Spare vs
//          Installed/Active) · BR-AST-049
// ───────────────────────────────────────────────────────
//
// **WHY A BROWSER AND NOT ONLY THE VITEST SUITE.** Hard-won law 6: no gate in
// this repo looks at rendered output, and the nine defects of 2026-08-10 were
// found this way and by nothing else. The vitest half of this wave
// (`ImportIdentifierTruth.dom.test.tsx`) drives the same clicks against a
// MOCKED client — it proves the component renders what a stubbed server sends.
// It cannot prove the real server sends it, and CR-046's whole shape is that
// three of these fields were SERVED and drawn nowhere.
//
// So this file asserts on text a person reads, against a live Django and a
// live Postgres, and asserts NOTHING about a payload.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

const IMPORT_PATH = `/${tenant()}/assets/import?target=assets_meters`;

test.describe("CR-046 wave E — the meter import tells the truth about the number", () => {
  test("E1 · step 1 says a known row is REJECTED, and where a new number comes from", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(IMPORT_PATH);

    const consequence = page.locator('[data-workflow="write-mode-consequence"]');
    await expect(consequence).toBeVisible();

    // `insert` is the default (hard-won law 3), so this is what a clerk who
    // touches nothing is told.
    await expect(consequence).toContainText(/REJECTED/);
    await expect(consequence).toContainText(/Settings . Numbering/);
    // ⛔ The sentence CR-046 E1 struck. "Counted and shown to you" is REPORTING.
    await expect(consequence).not.toContainText(/counted and shown to you/i);

    // …and the other mode, which is the whole reason the choice is at step 1.
    await page.getByRole("radio", { name: /Insert & update/i }).click();
    await expect(consequence).toContainText(/UPDATES that record's details/);
  });

  test("E1 · the withdrawn third mode is not on the screen (CR-042)", async ({ page }) => {
    await signIn(page);
    await page.goto(IMPORT_PATH);
    const group = page.locator('[data-workflow="write-mode"]');
    await expect(group.getByRole("radio")).toHaveCount(2);
    await expect(group).not.toContainText(/Replace/i);
  });

  test("E2 · stage 2 shows the identifier column's header and its help, whole", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(IMPORT_PATH);

    // A real file, with NO number column — which is what a file built from the
    // downloadable template now looks like.
    await page.locator('input[type="file"]').setInputFiles({
      name: "meter_fleet_2026.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("SERIAL,SVC\nSN-4471,water\nSN-4472,water\n"),
    });
    await page.getByRole("button", { name: "Transform →" }).click();
    await expect(page.locator('[data-workflow="runner"]')).toHaveAttribute("data-stage", "2");

    const note = page.locator('[data-workflow="column-help-asset_no"]');
    await expect(note).toBeVisible();
    // The HEADER the operator matches against their own spreadsheet…
    await expect(note).toContainText("Meter number (existing only)");
    // …and the sentence, to its LAST clause — a help line that is clipped at
    // "LEAVE THIS BLANK" and never reaches "Your old system's number goes in
    // External reference" sends a migrating utility to overwrite the wrong
    // column. This is the "not truncated or swallowed" half of E2.
    await expect(note).toContainText("LEAVE THIS BLANK for a new meter");
    await expect(note).toContainText("Your old system's number goes in External reference");

    // Not truncated by CSS either — the rendered box must be tall enough to
    // hold the text it contains. A `line-clamp` would make these disagree.
    const clipped = await note.evaluate((el) => el.scrollHeight > el.clientHeight + 1);
    expect(clipped, "the help sentence is clipped by its own box").toBe(false);
  });
});
