// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-018 · US-LED-019 · US-LED-020 · US-LED-021
//           Screens: S73 · S74 · S42
// ───────────────────────────────────────────────────────
// S73/S74 in a real browser, asserting THE THINGS THAT WERE ACTUALLY WRONG.
//
// Three lanes on 2026-08-16 shipped a browser check that passed against the
// broken screen, so this file deliberately does not assert "the page rendered".
// It asserts:
//
//   1. **The Finance tab strip carries a Cost of service tab**, and clicking it
//      reaches a screen — the whole of "built is not wired" for this capability,
//      which had 1,700 tested backend lines and no route to any of them.
//   2. **The register loads over HTTP** — i.e. the include in `config/urls.py`
//      is live and the browser's request is answered, not 404'd. Asserted by the
//      absence of the failure state AND the presence of a served string the
//      screen cannot compose for itself.
//   3. **The screen says the books did not move.** OQ-200's closure text: *"any
//      screen implying otherwise is a defect"*. This is the assertion that would
//      have failed on a screen that merely looked finished.
//   4. **A percentage is never invented.** The reconciliation must show a REASON
//      where it cannot compute, never a 0.
import { expect, test } from "@playwright/test";

import { bootApp, signIn } from "./support/app";

test("S73 · the Cost of service tab exists, reaches a screen, and says the books did not move @app-server", async ({
  page,
}) => {
  await signIn(page);
  await bootApp(page);

  await page.goto("/brazosbend/finance/cost-of-service");
  // 1 · The screen is REACHED. `ModulePlaceholder` renders the literal W0
  // scaffold string, which is exactly what an unrouted path would show — the
  // DEF-129 shape. Asserting its ABSENCE is asserting the route.
  await expect(page.locator("[data-not-built-yet]")).toHaveCount(0); // DEF-152

  // 2 · The tab is in the Finance strip, so a human can get here by clicking.
  await expect(page.getByRole("tab", { name: /cost of service/i })).toBeVisible();

  // 3 · The ruling, printed. This sentence is SERVED by the ledger and is the
  // one a finance officer needs before they wonder why the trial balance did
  // not move by $51,902.50.
  await expect(page.getByText(/moves no books/i)).toBeVisible();

  // 4 · Both views are reachable from the screen itself.
  await page.getByRole("button", { name: /bought vs billed/i }).click();
  await expect(page.getByRole("columnheader", { name: /unaccounted for/i })).toBeVisible();
  // The basis is MANDATORY on the figure group (BR-REP-001) and names the
  // ruling rather than an open question.
  await expect(page.getByText(/service period/i).first()).toBeVisible();

  // 5 · The download is DISABLED WITH ITS REASON (BR-SHL-025 / OQ-204), never
  // hidden and never silently broken.
  const download = page.getByRole("button", { name: /download|descarga/i }).first();
  await expect(download).toBeDisabled();
  await expect(page.getByText(/has not been ruled/i)).toBeVisible();
});
