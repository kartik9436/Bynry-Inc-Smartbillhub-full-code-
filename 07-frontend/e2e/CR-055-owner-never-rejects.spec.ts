// ── Trace ──────────────────────────────────────────────
// Change:  CR-055 — a premises upload never rejects a row because of the
//          owner's name (12-governance/11-change-requests.md · ## CR-055)
// Ruling:  PO 2026-08-31 — an owner name matching two or more existing owners
//          LOADS the premises with no owner, flagged, exactly as a blank owner
//          column already does. The row is not rejected.
// Rules:   BR-MET-401 as amended 2026-08-31 · BR-MET-402 · B14 rule 31 (no
//          database id is ever the visible value of a field)
// Screens: WFL-01.premises stages 1-5 · /{tenant}/premises/import?target=premises
// ───────────────────────────────────────────────────────
//
// **WHY A BROWSER AND NOT ONLY THE PYTEST AND VITEST SUITES.** PO ruling
// 2026-08-30, verbatim: *"All UI screen should be confirm using real broswer
// testing and not just based on test cases"*. Hard-won law 6 says the same
// thing from the other end: no gate in this repo looks at rendered output, and
// the nine defects of 2026-08-10 were found this way and by nothing else.
//
// The backend suite proves the RUN records the two counts. It cannot prove the
// screen draws them — and CR-055's whole mitigation is a number a person reads
// on a receipt, so a count that is served and drawn nowhere is the change
// half-built (hard-won law 2: built is not wired).
//
// ⚠ **THIS FILE ASSERTS ON WHAT A PERSON READS AND NOTHING ABOUT A PAYLOAD.**
// It drives the real wizard against a live Django and a live Postgres, uploads
// a real CSV, and reads the receipt.
//
// ⚠ **THE TWO LOOK-ALIKE OWNERS ARE FIXTURE, NOT PRODUCT.** `near` needs two
// owner records whose names collapse onto one key, and the import may not
// create a party (BR-MET-402 clause 5). They are seeded by
// `08-qa/01-e2e/stack/seed_cr055_owners.py` before this spec runs; the spec
// skips with an honest reason if they are absent, rather than passing over a
// world where the case cannot arise.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

const IMPORT_PATH = `/${tenant()}/premises/import?target=premises`;

// The two parties already on file, and the third spelling the FILE carries.
// `_normalise_owner_name` strips legal forms only, so all three share the key
// `ridge property` while none of them is an exact match for the cell.
const NEAR_A = "Ridge Property LLC";
const NEAR_B = "Ridge Property, L.L.C.";
const AMBIGUOUS = "Ridge Property Inc";

// Five rows, one per owner answer plus a repeat of the ambiguous spelling, so
// the receipt has something to say about all of them at once. PREMISE_ID and
// PROP_TYPE are blank on purpose: a premise id not already on file is a tier-2
// ERROR under the 2026-08-27 numbering ruling, and either column would reject
// rows for a reason that has nothing to do with owners.
const CSV = [
  "PREMISE_ID,ADDR1,CITY,STATE,ZIP,PROP_TYPE,SVC_AVAIL,OWNER,LEGACY_KEY",
  `,71 Cypress Way,Katy,TX,77494,,water,${NEAR_A},CR55-1`,
  ",72 Cypress Way,Katy,TX,77494,,water,,CR55-2",
  `,73 Cypress Way,Katy,TX,77494,,water,"${AMBIGUOUS}",CR55-3`,
  `,74 Cypress Way,Katy,TX,77494,,water,"${AMBIGUOUS}",CR55-4`,
  ",75 Cypress Way,Katy,TX,77494,,water,Bluestem Holdings Trust,CR55-5",
  "",
].join("\n");

test.describe("CR-055 — the premises upload rejects no row on owner grounds", () => {
  test("the receipt draws BOTH kinds of ownerless and names the two parties @app-server", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    await signIn(page);
    await page.goto(IMPORT_PATH);

    // ── stage 1 · the file ───────────────────────────────────────────────
    await page.locator('input[type="file"]').setInputFiles({
      name: "cr055_premises.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(CSV),
    });
    await page.getByRole("button", { name: "Transform →" }).click();
    await expect(page.locator('[data-workflow="runner"]')).toHaveAttribute("data-stage", "2");

    // ── stage 2 · the mapping. The OWNER header auto-detects to the TYPED
    //    owner column (DEF-1247), which is what every owner rule reads.
    await page.getByRole("button", { name: "Validate →" }).click();
    await expect(page.locator('[data-workflow="runner"]')).toHaveAttribute("data-stage", "3", {
      timeout: 60_000,
    });

    // ⛔ **THE HEADLINE, ON THE SCREEN A PERSON READS.** Before CR-055 the two
    // ambiguous rows were ERRORS: they were thrown out, and a one-row file of
    // them could not even be committed without an approval. Nothing here is
    // rejected.
    const outcome = page.locator('[data-workflow="validate-outcome"]');
    await expect(outcome).toBeVisible();
    await expect(outcome).not.toContainText(/pick which party it is/i);

    await page.getByRole("button", { name: "Load →" }).click();
    await expect(page.locator('[data-workflow="runner"]')).toHaveAttribute("data-stage", "4", {
      timeout: 60_000,
    });

    // ── stage 4 · commit ─────────────────────────────────────────────────
    await page.getByRole("button", { name: "Commit load ✓" }).click();
    await expect(page.locator('[data-workflow="runner"]')).toHaveAttribute("data-stage", "5", {
      timeout: 90_000,
    });

    // ── stage 5 · THE RECEIPT, which is the whole mitigation ─────────────
    const strip = page.locator('[data-workflow="reconcile"]');
    await expect(strip).toBeVisible();

    // Five rows landed and NONE was rejected.
    await expect(strip.locator('[data-workflow-figure="loaded"]')).toContainText("5");
    await expect(strip.locator('[data-workflow-figure="rejected"]')).toContainText("0");

    // The total, and then the two halves — which is what CR-055 task 2 buys.
    const total = strip.locator('[data-workflow-figure="no-owner"]');
    await expect(total).toBeVisible();
    await expect(total).toContainText("3");
    await expect(total).toHaveAttribute("data-flagged", "true");

    const blank = strip.locator('[data-workflow-figure="owner-blank"]');
    await expect(blank).toBeVisible();
    await expect(blank).toContainText("1");
    await expect(blank).toContainText(/needs research/i);

    const ambiguous = strip.locator('[data-workflow-figure="owner-ambiguous"]');
    await expect(ambiguous).toBeVisible();
    await expect(ambiguous).toContainText("2");
    await expect(ambiguous).toContainText(/needs a decision/i);

    // ⛔ **AND THE PARTIES BY NAME**, so the person settling it is choosing
    // between two landlords rather than re-running the search.
    const panel = page.locator('[data-workflow="owner-ambiguities"]');
    await expect(panel).toBeVisible();
    await expect(panel).toContainText(NEAR_A);
    await expect(panel).toContainText(NEAR_B);
    await expect(panel).toContainText(AMBIGUOUS);
    // One line per SPELLING, not per row: two addresses, one decision.
    await expect(panel.locator("li")).toHaveCount(1);

    // ⚠ **B14 rule 31 — no database id is ever the visible value of a field.**
    // The server drops the owner id from these entries; this is the assertion
    // that a uuid never reaches the receipt.
    const drawn = (await panel.innerText()).trim();
    expect(drawn).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
  });
});
