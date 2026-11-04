// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-2310 — `tenant_services.metered` had a reader and NO WRITER, so
//          BR-RAT-081's declaration could not be made from any screen or API.
//          DEF-2311 — `billed_uom` likewise.
// Screens: S8 (Settings → Services & UoM) · route /{tenant}/settings/services
// Rules:   BR-RAT-081 (a utility DECLARES a service metered or unmetered — PO
//          2026-08-20) · BR-TEN-810 (the declaration is written on S8, shown on
//          every row on or off, and is forward-only) · BR-TEN-811 (the
//          conversion factor is required for a METERED service only) ·
//          BR-TEN-026 (enable/disable) · BR-SHL-032 (the confirm names the act)
// ───────────────────────────────────────────────────────
//
// **THE BAR, verbatim from the PO (13-change-process §8):** *"in this session
// CR is not closed until we have confirm user is able to perform tasks using
// screen/broswer/UI"*. This file is that confirmation for the one task this
// lane exists to make possible: **a utility telling the product it does not put
// a meter on a service.**
//
// Everything below asserts TEXT A PERSON READS in a real browser against a real
// Django + Postgres. There is not one API call in this file.
//
// ⚠ IT FLIPS THE DECLARATION BOTH WAYS ON PURPOSE. The seeded tenant already
// carries `trash: unmetered` (this lane's own `seed_demo` block), so asserting
// only that it reads "Unmetered" would prove the SEED and say nothing about the
// screen. So the walkthrough sets it to Metered, reads the row back, sets it to
// Unmetered again, and reads it back — a control that can only be pushed one
// way is half a control.
import { expect, test } from "@playwright/test";

import { baseUrl, signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

const SERVICES_PATH = "/settings/services";

/** The `<tr>` a service's name is in — the row a person points at. */
function serviceRow(page: import("@playwright/test").Page, name: string) {
  return page.locator("tr").filter({ has: page.getByRole("cell", { name, exact: true }) });
}

/**
 * Choose one option of the metering segmented control — BY ITS LABEL.
 *
 * ⚠ AND THE REASON IS WORTH A BROWSER TEST'S TIME, because it cost this one a
 * five-minute timeout. `FormModal.css` styles `.seg-opt input` as
 * `position:absolute; opacity:0; width:0; height:0; pointer-events:none` — the
 * real radio is present, focusable and announced, and it has NO BOX. So
 * `getByRole("radio").check()` resolves the element and then waits forever for
 * it to become visible:
 *
 *     locator resolved to <input type="radio" name="metered" value="metered"/>
 *     527 x waiting for element to be visible, enabled and stable
 *     - element is not visible
 *
 * A human clicks the WORDS, and the wrapping `<label>` carries that click to
 * the input. This does the same. Anything else here would be driving a control
 * no person can reach — which is the whole thing a browser check exists to
 * avoid.
 */
async function chooseMetering(
  page: import("@playwright/test").Page,
  option: "Metered" | "Unmetered",
): Promise<void> {
  await page.locator("label.seg-opt", { hasText: new RegExp(`^${option} \u2014`) }).click();
}

async function openServices(page: import("@playwright/test").Page): Promise<void> {
  await page.goto(`${baseUrl()}/${tenant()}${SERVICES_PATH}`);
  // DEF-176's lesson: wait for the DATA, not the paint. A list's rows do not
  // exist until they arrive, and a check that ran on first paint would assert
  // over an empty table and pass.
  await expect(serviceRow(page, "Water")).toBeVisible({ timeout: 20_000 });
}

test.describe("DEF-2310 — a utility declares a service unmetered, on the screen", () => {
  test("the Metering column is on every row, and the modal writes it both ways @app-server", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);
    await openServices(page);

    // ── 1. THE COLUMN EXISTS AND SAYS SOMETHING TRUE ABOUT EVERY SERVICE ──
    await expect(page.getByRole("columnheader", { name: "Metering" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Billed unit" })).toBeVisible();
    // Water is metered — the column's own safe default, on a service that is on.
    await expect(serviceRow(page, "Water")).toContainText("Metered");
    // Trash is DECLARED unmetered by the seed while the service itself is OFF.
    // Both facts on one row is BR-TEN-810's point: a declaration a tenant
    // cannot SEE is what let this column sit unwritten for eight days.
    const trash = serviceRow(page, "Trash");
    await expect(trash).toContainText("Unmetered");
    await expect(trash).toContainText("cart");

    // ── 2. THE SERVICE IS ON — turning it on if this stack left it off ───
    // Written to work either way ON PURPOSE. `seed_demo` DECLARES trash and
    // deliberately does not enable it (that is DEF-1250/DEF-2490's ground), and
    // the E2E fixture enables it on top; a spec that hard-coded either state
    // would go red on a stack seeded the other way and prove nothing about this
    // screen. BR-SHL-032 is still exercised when the click happens: the confirm
    // names the action rather than saying OK.
    if ((await trash.textContent())?.includes("Off")) {
      await trash.getByRole("button", { name: "Enable" }).click();
      await page.getByRole("button", { name: "Turn on Trash" }).click();
    }
    await expect(serviceRow(page, "Trash")).toContainText("On", { timeout: 20_000 });

    // ── 3. DECLARE IT METERED — the direction that must also work ────────
    await serviceRow(page, "Trash").getByRole("button", { name: "Service settings" }).click();
    await expect(page.getByText("Trash settings")).toBeVisible();
    await chooseMetering(page, "Metered");
    // A metered service billed in a unit its register does not read needs the
    // factor (BR-TEN-811) — and month→cart has none, so clear the billed unit
    // exactly as a clerk would have to.
    await page.locator("#billed_uom").selectOption("");
    await page.getByRole("button", { name: "Save settings" }).click();
    await expect(serviceRow(page, "Trash")).toContainText("Metered", { timeout: 20_000 });
    await expect(serviceRow(page, "Trash")).not.toContainText("Unmetered");

    // ── 4. AND BACK — the declaration this lane exists for ───────────────
    await serviceRow(page, "Trash").getByRole("button", { name: "Service settings" }).click();
    await chooseMetering(page, "Unmetered");
    await page.locator("#billed_uom").selectOption("cart");
    await page.getByRole("button", { name: "Save settings" }).click();
    const after = serviceRow(page, "Trash");
    await expect(after).toContainText("Unmetered", { timeout: 20_000 });
    await expect(after).toContainText("cart");
  });
});

// ── THE RUN RECORD ─────────────────────────────────────────────────────────
//
// | run | stack | result |
// |---|---|---|
// | 2026-08-28 | `boot_stack.sh` on a fresh `sbh_e2e_def2310`, Django 8041 + the
//   BUILT SPA on 8091, Chromium 1194 | **1 passed (27.6s)**. Signed in as the
//   seeded owner, opened Settings → Services, read the two new columns off the
//   table, turned Trash on through its confirm, set it Metered, read the row
//   back, set it Unmetered with `cart`, read the row back. |
//
// **AND THE FIGURE THIS EXISTS FOR, ON THE SAME DATABASE, minutes later:**
// account `AC-2026-00002` at *103 Willow Bend Dr, Unit 1* — three carts on the
// unit — priced by the real bill run for July 2026:
//
//     trash  usage  qty=3.000000 cart  amount=45.000000
//
// **`3 × $15.00 = $45.00`, and the only thing that made trash unmetered on that
// tenant was this screen and the seed.** Nobody edited a row. The bill run
// itself was driven from the product's own services rather than from a browser
// — that is a different screen and another lane's flow, and it is stated here
// rather than implied.

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-2310@8febad7 (defect register + BR-TEN-810/BR-TEN-811)
// generated: 2026-08-28 by the service-declaration lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: the $45.00 bill itself is NOT driven from a browser here — a bill run over the seeded estate is a different screen and a different lane's flow; it is proved from real rows by 06-backend/tests/test_def_2310_service_declaration.py::tc8, where the declaration is made ONLY through the settings service
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
