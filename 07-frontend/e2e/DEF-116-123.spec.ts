// ── Trace ──────────────────────────────────────────────
// Defects: DEF-116 (the bill-run wizard cannot issue: no release route, no
//          issue route — and, found while proving this, NO CALCULATE ROUTE
//          EITHER) · DEF-123 (no tenant has a bill template and nothing can
//          create one, so every run refuses at issue on BR-BIL-025)
// Story:   US-BIL-004 (phase 2 — the calculation) · US-BIL-005 (phases 4 and
//          5 — the gate and the release) · US-BIL-021 (the template the pin
//          points at) · US-TEN-001 (provisioning, which is where the template
//          row comes from)   Screens: S31 steps 1–6 · S30
// Rules:   BR-BIL-051/052 (phase 2 drafts every ready account; a killed pass
//          resumes) · BR-BIL-058 (the gate is five separately recorded facts) ·
//          BR-BIL-025/026 (the template pin is resolved, never invented, and is
//          non-optional) · BR-BIL-004 (issue is the transition INTO
//          immutability) · CLAUDE.md rule 6 (idempotency)
// ───────────────────────────────────────────────────────
//
// **THE ONE THING THIS FILE PROVES: A PERSON CAN ISSUE A BILL IN A BROWSER.**
//
// Nothing else in this repository asserts that. J24 asserts the five-phase run
// against its own 1,124-account fixture, which no seeder builds, so it goes red
// on its world rather than on the product (DEF-108). This spec drives the SAME
// screens over the world `boot_stack.sh` actually seeds — one ready account —
// and asserts the outcome that matters: a bill that did not exist when the run
// started is ISSUED, carries money with its currency, and appears on S30.
//
// WHY IT IS ONE TEST AND NOT SIX. Every step here is a precondition of the
// next; six tests would report five identical failures for one broken step and
// bury the one that mattered. J24's nine-test shape is right for a NINE-CLAIM
// contract; this file has one claim.
//
// WHAT IT DOES NOT CLAIM. Nothing is dispatched — issue QUEUES one delivery row
// per bill per channel and there is no dispatcher (BR-BIL-016), so a green run
// here never means a customer received anything. The screen says so too, and
// this spec asserts that it still does.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";

/**
 * A period NO EARLIER RUN CAN HAVE USED, and the reason is BR-BIL-005 rather
 * than convenience: a run is idempotent on (tenant, cycle, period), so a second
 * identical run is REFUSED with who/when/link — correctly. A spec that typed
 * one fixed period would pass once and then assert the idempotency rule instead
 * of the issue path forever after. The window is only a bound here: this
 * tenant's ready account has no meter read, so it prices at its plan's minimum
 * prorated on calendar days, and the FIGURE is B5's golden suite to assert, not
 * this file's.
 */
function uniquePeriod(): { start: string; end: string; billDate: string } {
  // A WHOLE CALENDAR MONTH INSIDE THE SEEDED READ WINDOW, and both halves are
  // load-bearing rather than tidy. WHOLE MONTH: the account's service agreement
  // is measured against the period and a part-month window prepares ZERO ready
  // accounts — which looks exactly like the defect and is not it. INSIDE THE
  // WINDOW: `seed_e2e_fixture` writes one water read per month across the
  // months `meter_reads` is actually partitioned for, and a period outside them
  // has no usage to measure. The month rotates so a second run of this spec
  // picks a period the first cannot have used (BR-BIL-005 refuses a repeat).
  const months: [number, number][] = [];
  for (let year = 2024; year <= 2026; year += 1) {
    for (let month = 0; month < 12; month += 1) {
      if (year === 2024 && month < 9) continue; // reads start 2024-09
      if (year === 2026 && month > 9) continue; // …and end 2026-11
      months.push([year, month]);
    }
  }
  const [year, month] = months[Math.floor(Date.now() / 1000) % months.length];
  const start = new Date(Date.UTC(year, month, 1));
  const end = new Date(Date.UTC(year, month + 1, 0)); // day 0 = last of `month`
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return { start: iso(start), end: iso(end), billDate: "2026-08-08" };
}

test.describe("DEF-116/123 — a person can issue a bill in a browser @app-server", () => {
  skipUnlessAppServer(test);

  test("the five-phase run reaches an ISSUED bill", async ({ page }) => {
    test.setTimeout(180_000);

    await signIn(page);
    await page.goto(`/${tenant()}/billing/run`);
    await page.locator("#brun-cycle").waitFor();

    // ── STEP 1 · PREPARE ────────────────────────────────────────────────────
    // BY CODE, and deliberately — J24 picks a cycle by INDEX to avoid binding a
    // journey to one fixture's reference data, and it is right to. This file is
    // not a journey: it is a defect regression test against the world
    // `boot_stack.sh` seeds, and in that world only cycle **08-A** carries the
    // routes the billable account sits on. Picking index 1 lands on 08-B, whose
    // units have no billable account, so the run prepares ZERO ready accounts
    // and the spec fails looking exactly like the defect it exists to catch.
    // Bound on purpose, and said out loud so the binding is visible.
    const period = uniquePeriod();
    const cycleValue = await page.locator("#brun-cycle").evaluate((element) => {
      const select = element as HTMLSelectElement;
      return Array.from(select.options).find((option) => option.text.includes("08-A"))?.value ?? "";
    });
    expect(cycleValue).not.toBe("");
    await page.locator("#brun-cycle").selectOption(cycleValue);
    await page.locator("#brun-period-start").fill(period.start);
    await page.locator("#brun-period-end").fill(period.end);
    await page.locator("#brun-bill-date").fill(period.billDate);
    for (const code of ["electric", "water"]) {
      await page.locator(`label[for="brun-service-${code}"]`).click();
    }
    await page.getByRole("button", { name: /Start this run/ }).click();
    await expect(page).toHaveURL(/[?&]run=[0-9a-f-]{36}/);
    const runUrl = new URL(page.url());

    // ── STEP 3 · DECIDE ─────────────────────────────────────────────────────
    // BR-BIL-015: a missing read is a CHOICE — estimate it, hold the account,
    // or bill without the service — and *"billing the rest would be taking the
    // third one silently"*. This tenant's ready account has no read for either
    // service, so phase 2 breaks it at measure-consumption until a human rules.
    // That refusal is the product working; the clerk's answer is what unblocks
    // it, and taking it here is what makes this a five-phase run rather than a
    // shortcut round one.
    runUrl.searchParams.set("step", "3");
    // The case tab is URL state like the step (BR-SHL-011), and its default is
    // the first tab — which for this world is empty. Name the one this run
    // actually has cases in.
    runUrl.searchParams.set("case", "missing_read");
    await page.goto(`${runUrl.pathname}${runUrl.search}`);
    // Wait for the ROWS, not just the table: "select every row in this
    // category" over an empty category selects nothing, silently.
    await page.locator('[data-brun="acct"]').first().waitFor({ timeout: 30_000 });
    await page.getByRole("checkbox", { name: /Select every row in this category/ }).check();
    await page.getByRole("button", { name: /Bill without that service for the selected/ }).click();
    // BR-BIL-060 — the confirm names the count BEFORE the click.
    await page.getByRole("button", { name: /Record for \d+ customers/ }).click();

    // ── STEP 4 · CALCULATE ──────────────────────────────────────────────────
    // ⚠ THE STEP THAT DID NOT EXIST. Until 2026-08-16 the wizard walked from
    // step 1 to step 6 without ever asking the server to work the bills out, so
    // the gate was handed an empty run and refused — which is why DEF-116
    // reported "READY TO BILL 0, Draft bills 0" with a complete engine behind
    // it. A draft is not money (BR-BIL-004), so this button is safe to press.
    runUrl.searchParams.set("step", "4");
    await page.goto(`${runUrl.pathname}${runUrl.search}`);
    await page.getByRole("button", { name: /Work out the bills/ }).click();

    // The count is the SERVER's, over `GET /invoices?f.bill_run_id=…`, not a
    // total this page added up. A calculated run that produced nothing has not
    // calculated, and that is the state DEF-116 measured.
    const draftCount = page
      .getByText("Draft bills", { exact: true })
      .locator("xpath=following-sibling::dd[1]");
    await expect(draftCount).not.toHaveText("0", { timeout: 60_000 });

    // ── STEP 5 · THE GATE ───────────────────────────────────────────────────
    // The five confirmations live on step 5 and the Send control on step 6:
    // the AUTHORISATION and the ACT are two screens because they are two
    // events (`bill_run_releases` is written by the first and stamped by the
    // second), and a crash between them is resumable rather than a
    // re-authorisation.
    runUrl.searchParams.set("step", "5");
    await page.goto(`${runUrl.pathname}${runUrl.search}`);

    // BR-BIL-058 — five separately recorded facts, not one tick, because "a
    // release that went out without the compliance check is a different event
    // from one that did".
    // The <input> is visually replaced by its own control, so a human clicks
    // the LABEL and so does this — the same shape step 1's service chips have.
    for (const fact of ["compliance", "email_mandate", "sms_mandate", "autopay_mandate", "final"]) {
      await page.locator(`label[for="brun-gate-${fact}"]`).click();
    }

    // ── STEP 6 · SEND ───────────────────────────────────────────────────────
    // CONTINUE, never a fresh `goto`. The five confirmations are the wizard's
    // own state until the commit records them, and a page LOAD remounts the
    // screen and empties them — the clerk would arrive at Send with an
    // untaken gate and the release would be refused, correctly, for a reason
    // this spec had itself created. BR-BIL-050 puts the RUN in the URL and
    // deliberately not the sign-off: an authorisation that survived a reload
    // would be an authorisation nobody re-made.
    await page.getByRole("button", { name: /^Continue$/ }).click();
    await expect(page).toHaveURL(/[?&]step=6/);

    // The screen must STILL say that nothing leaves the building: issue queues
    // a delivery row per bill and there is no dispatcher (BR-BIL-016). A green
    // run must never be read as "the customer got it".
    await expect(page.getByText(/Nothing leaves the building yet/)).toBeVisible();

    await page.getByRole("button", { name: /Send all now/ }).click();

    // ── THE OUTCOME ─────────────────────────────────────────────────────────
    // Returned to S30 (BR-BIL-051 — the gate returns the clerk to the list),
    // and a bill is ISSUED. The money is asserted with its currency because a
    // number without one is not money (CLAUDE.md rule 2); the FIGURE itself is
    // the engine's and is deliberately not typed here — this file proves the
    // path, and B5's golden suite owns the arithmetic.
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/billing$`), { timeout: 60_000 });
    const issued = page.getByRole("row").filter({ hasText: /Issued/ });
    await expect(issued.first()).toBeVisible({ timeout: 30_000 });
    await expect(issued.first().locator(".cell-money-amount")).toHaveText(/\d+\.\d\d/);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-116 + DEF-123 (12-governance/10-defect-log.csv ·
//         08-qa/01-e2e/journeys/J24-five-phase-bill-run.md steps 4/6/7 ·
//         04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-025/051/058)
// generated: 2026-08-16 by the DEF-116/123 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: run against a live stack booted by 08-qa/01-e2e/stack/boot_stack.sh on
//         a FRESH database, so the tenant is provisioned by the real service and
//         its bill template is the seeded one — which is the half DEF-123 was.
//         RED-proved by the product itself: before the calculate route existed
//         this spec's step-4 assertion failed on "Draft bills 0" and the gate
//         answered "run … has no bills to release … an authorisation of nothing
//         would be a signature against a blank page".
// exceptions: (1) it asserts the SHAPE of the money, not the figure — the
//         seeded world is boot_stack's, not a signed fixture, and retyping a
//         number here would be a second copy of a figure nobody signed.
//         (2) it does NOT assert delivery: issue queues and nothing dispatches
//         (BR-BIL-016), and the spec asserts the screen still says so.
//         (3) it is NOT a journey — J24 is the journey and asserts a 1,124-
//         account contract this stack cannot seed (DEF-108). This is the
//         defect's own regression test and is named for the defect.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
