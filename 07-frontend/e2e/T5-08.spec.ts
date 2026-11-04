// ── Trace ──────────────────────────────────────────────
// Journey:  T5-08 — Export an OPEN period (the ERP never receives numbers that
//           can still move). `08-qa/01-e2e/journeys/T5-08-export-open-period.md`
//           is the spec; this file walks its five-row step table in order.
// Story:    US-LED-015 (period close) · US-LED-016 (the ERP export batch) ·
//           US-IDN-001 (sign in)
//           Screens: S3 · S42 (Finance → Export)
// Rules:    BR-LED-017 (export requires the covered period CLOSED — L-3b) ·
//           BR-LED-006 (a closed period locks) · BR-LED-018 (the close
//           checklist: WARN + CONFIRM with reason, never silent) · BR-LED-004
//           (a closed window exports) · NFR-16 (the refusal is server-side)
// Money:    none rendered by any step this product can reach; the journey's
//           only money claim is step 4's "extract matches the recorded batch's
//           figures", and no batch, extract or export surface exists. No figure
//           is typed here — `moneyTriple` is not called because no reachable
//           screen renders one, which is stated rather than faked with a
//           borrowed assertion.
// Tests:    this file. Fixture: 08-qa/01-e2e/stack/seed_e2e_fixture.py
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
//
// WHAT THIS RUN IS EXPECTED TO FIND, written before it ran and left standing.
//
// The wiring index says T5-08 is story-ready (US-LED-015 + US-LED-016 are both
// cited in a code Trace header). The product this stack boots has:
//
//   · `/finance/export` — a real route, a real tab in the S36 strip, whose body
//     is an `ArrivesWith` panel: there is no export control on it at all.
//   · no `periods` resource of any kind (`GET /api/{tenant}/periods` → 404), so
//     "the covered period is CLOSED" is not a state this product can be in.
//   · no tenant-scoped `exports` resource. `POST /api/exports` exists and is
//     the PLATFORM list-download (US-SHL-008 / IS-11) — a different thing that
//     takes a list key, not a period.
//
// So this journey is expected to stop at step 1. The spec still walks all five
// rows, because "which of the five is the first one the product cannot perform"
// is the finding, and a spec that stopped early would not know.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

const OPEN_PERIOD = "2026-07";
const CLOSED_PERIOD = "2026-06";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

journey("T5-08", "Export an OPEN period — the ERP never receives numbers that can still move", () => {
  // NOT serial: every test below signs in and builds its own precondition,
  // so the run reports which of the journey's rows hold rather than stopping
  // at the first that does not. Which row is the first the product cannot
  // perform is the deliverable.
  skipUnlessAppServer(test);

  test("step 1 — S42 must offer an export and refuse the OPEN period by name", async ({ page }) => {
    await signIn(page);

    // A human clicking: sidebar → Finance → Export.
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Finance", exact: true }).click();
    await page.getByRole("tab", { name: "Export" }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/finance/export$`));

    // BR-LED-017's refusal cannot be reached without a control that asks for
    // the export. The journey's step 1 is "requests an export covering
    // 2026-07"; this is that request.
    await expect(
      page.getByRole("button", { name: /export/i }).first(),
      "S42 must offer an export control for a finance user to request a period export",
    ).toBeVisible();
  });

  test("step 2 — the weekly-JE granularity choice never bypasses the closed-period rule", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/finance/export`);
    await expect(
      page.getByRole("radio", { name: /week/i }).or(page.getByRole("combobox", { name: /granularity/i })).first(),
      "S42 must offer the summary-JE / weekly-JE granularity choice BR-LED-017 governs",
    ).toBeVisible();
  });

  test("step 3 — POST /exports for the open period is refused server-side", async ({ page }) => {
    await signIn(page);
    const response = await page.request.post(api("/exports"), {
      data: { period: OPEN_PERIOD },
    });
    // BR-LED-017 / NFR-16: the server, not the UI, owns this refusal. A 409/422
    // naming the close requirement is the pass; a 404 means the resource that
    // would carry the rule is not mounted at all.
    expect(
      [409, 422],
      `POST /exports answered ${response.status()} — the tenant-scoped ERP export ` +
        "resource BR-LED-017 governs is not mounted",
    ).toContain(response.status());
  });

  test("step 4 — contrast: the CLOSED period exports", async ({ page }) => {
    await signIn(page);
    const response = await page.request.post(api("/exports"), {
      data: { period: CLOSED_PERIOD, granularity: "dimension_csv" },
    });
    expect(
      [200, 201, 202],
      `exporting a CLOSED period answered ${response.status()} — BR-LED-004's ` +
        "allowed path is not reachable either",
    ).toContain(response.status());
  });

  test("step 5 — RECOVERY: the close checklist closes 2026-07 and the export then succeeds", async ({
    page,
  }) => {
    await signIn(page);
    const close = await page.request.post(api(`/periods/${OPEN_PERIOD}/close`), {
      data: { reason: "T5-08 recovery — close per the BR-LED-018 checklist" },
    });
    expect(
      [200, 201, 202],
      `POST /periods/${OPEN_PERIOD}/close answered ${close.status()} — the ratified ` +
        "door out of every refusal in this journey does not exist",
    ).toContain(close.status());
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-08 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) NO money figure is asserted — the journey renders none on any
//   surface this product can reach, and borrowing a figure from another journey
//   to satisfy the house rule would be a money claim about a screen nobody can
//   open · (2) step 3 posts to the TENANT-scoped `/api/{tenant}/exports`, not
//   the platform `/api/exports`: the latter is US-SHL-008's list download and
//   takes a list key, so pointing this step at it would test a different thing
//   and pass for the wrong reason
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
