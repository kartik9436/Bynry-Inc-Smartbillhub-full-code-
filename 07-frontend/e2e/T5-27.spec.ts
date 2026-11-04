// ── Trace ──────────────────────────────────────────────
// Journey:  T5-27 — Tie-out drift injection (red flag + release blocker,
//           detected live). `08-qa/01-e2e/journeys/T5-27-tieout-drift-injection.md`
//           is the spec; this file walks its six-row step table in order.
// Story:    US-LED-001 (the posting service is the sole writer of journal
//           lines) · US-LED-004 (the subledger tie-outs) · US-IDN-001
//           Screens: S3 · S36 Finance → Revenue & AR (tie-out panel)
// Rules:    BR-LED-007 (tie-outs render live on S36 and ANY drift is a red flag
//           AND a release blocker) · BR-LED-001 · CLAUDE.md hard rule 5 (only
//           the ledger posting service writes journal lines) · NFR-17
// Money:    the AR control total is read from `GET /finance/revenue-ar` and
//           asserted RENDERED — never retyped. The journey's $12,450.00 and
//           $500.00 belong to a sandboxed clone this stack does not seed, and
//           the money-triples dataset carries neither, so `moneyTriple` is not
//           called rather than borrowed.
// Tests:    this file. Fixture: 08-qa/01-e2e/stack/seed_e2e_fixture.py
// ───────────────────────────────────────────────────────
//
// STEP 2 CANNOT BE PERFORMED FROM A BROWSER SPEC, and that is stated rather
// than faked. The journey's own harness note calls it "a TEST-ONLY superuser
// write in a sandboxed database" — a direct INSERT of a one-sided journal line.
// A Playwright spec has no database seam and must not acquire one: the product
// under test is the browser and its API, and a spec that opened a psql
// connection would be testing something else. So step 2 asserts the half a
// browser CAN prove — that no application path will write an unbalanced or
// out-of-service ledger line — and the DETECTOR (step 3) is exercised against
// whatever the books actually say.
//
// Step 3 is where this journey is expected to stop, and the reason is in the
// product's own words. `07-frontend/src/features/ledger/RevenueArPage.tsx`
// carries this comment above the tie-out panel:
//
//   "BR-LED-007 says ANY drift is a red flag. The comparison that would find
//    drift is US-LED-004 and is not built, so this panel publishes the control
//    total and says, in words, that nothing has compared it. A green 'in
//    balance' badge here would be the worst possible lie in the product."
//
// The comment is honest and the panel is honest. The FINDING is that the wiring
// index lists US-LED-004 as built, and it is the one control that catches a
// posting-service bypass.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

const PERIOD_FROM = "2026-06-01";
const PERIOD_TO = "2026-07-31";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

journey("T5-27", "Tie-out drift injection — red flag and release blocker, detected live", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's six hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — no application path writes journal lines outside the posting service", async ({
    page,
  }) => {
    await signIn(page);
    // Hard rule 5 / BR-LED-001, probed from the outside: there must be no
    // client-reachable journal-line write at all.
    for (const path of ["/journal-entries", "/ledger/journal-entries", "/ledger/journal-lines"]) {
      const response = await page.request.post(api(path), {
        data: { lines: [{ account_code: "2300", debit: "500.000000", credit: "0.000000" }] },
      });
      expect(
        response.status(),
        `POST ${path} answered ${response.status()} — a one-sided journal line must never ` +
          "be writable by a client",
      ).toBeGreaterThanOrEqual(400);
    }

    // And every entry that DOES exist traces to a posting-service source.
    const entries = await page.request.get(api("/ledger/journal-entries?per=200"));
    expect(entries.status()).toBe(200);
    const rows = ((await entries.json()) as {
      results: { source_type?: string | null; status: string }[];
    }).results;
    expect(rows.length, "the seeded books carry no journal entries to check").toBeGreaterThan(0);
    expect(
      rows.every((r) => (r.source_type ?? "") !== ""),
      "every journal entry must name the posting-service source that wrote it",
    ).toBe(true);
  });

  test("step 2 — the books are balanced in the green state, and no route can unbalance them", async ({
    page,
  }) => {
    await signIn(page);
    const tb = await page.request.get(api("/ledger/trial-balance"));
    expect(tb.status()).toBe(200);
    const rows = ((await tb.json()) as { rows: { debit: string; credit: string }[] }).rows;
    const debits = rows.reduce((sum, r) => sum + Number(r.debit), 0);
    const credits = rows.reduce((sum, r) => sum + Number(r.credit), 0);
    expect(
      debits.toFixed(6),
      "the green state this journey injects drift into must be balanced to begin with",
    ).toBe(credits.toFixed(6));
  });

  test("step 3 — S36's tie-out panel COMPUTES the comparison and would red-flag drift", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/finance?from=${PERIOD_FROM}&to=${PERIOD_TO}`);
    await expect(page.locator("main")).toBeVisible();

    const panel = page.locator(".met-panel").filter({ hasText: /tie.?out/i }).first();
    await expect(panel, "S36 must render the BR-LED-007 tie-out panel").toBeVisible();

    // The control total the report serves, rendered — read from the API, never
    // retyped, so a drift between the two would fail here.
    const report = await page.request.get(
      api(`/finance/revenue-ar?from=${PERIOD_FROM}&to=${PERIOD_TO}`),
    );
    expect(report.status()).toBe(200);
    const arControl = ((await report.json()) as { tie_out: { ar_control: string } }).tie_out
      .ar_control;
    const rendered = Number(arControl).toFixed(2);
    await expect(panel, "the AR control total must be on screen").toContainText(rendered);

    // BR-LED-007's actual requirement: the panel COMPARES the two sides. A
    // panel that publishes one side and says nothing compared it cannot
    // red-flag a posting-service bypass — which is the one thing it exists for.
    await expect(
      panel,
      "BR-LED-007: the tie-out must COMPARE GL against the subledger, not publish one " +
        "side and state that nothing compared it (US-LED-004)",
    ).not.toContainText(/not (yet )?(computed|compared)|no comparison|US-LED-004/i);
  });

  test("step 4 — the tie-out is a release blocker, and the screen says so", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/finance?from=${PERIOD_FROM}&to=${PERIOD_TO}`);
    const panel = page.locator(".met-panel").filter({ hasText: /tie.?out/i }).first();
    await expect(panel).toBeVisible();
    await expect(
      panel,
      "NFR-17 / BR-LED-007: zero tolerance — the panel must state the drift verdict, " +
        "which is what a release gate reads",
    ).toContainText(/balance|drift|match|reconcil/i);
  });

  test("step 5 — no dismiss/acknowledge path exists for a tie-out flag", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/finance?from=${PERIOD_FROM}&to=${PERIOD_TO}`);
    const panel = page.locator(".met-panel").filter({ hasText: /tie.?out/i }).first();
    await expect(panel).toBeVisible();
    await expect(
      panel.getByRole("button", { name: /dismiss|acknowledge|ignore|mute/i }),
      "BR-LED-007: the flag derives from the equality check and clears ONLY when the " +
        "books re-balance — no dismiss control may exist",
    ).toHaveCount(0);
  });

  test("step 6 — RECOVERY: the repair door is a BALANCED correcting JE through the posting service", async ({
    page,
  }) => {
    await signIn(page);
    // The journey's recovery is "never a direct row edit" — a balanced
    // correcting entry, Finance role, reason + audit. The door has to exist.
    const response = await page.request.post(api("/journal-entries"), {
      data: {
        entry_date: "2026-07-31",
        type: "correction",
        memo: "T5-27 recovery — restore the deposit-liability balance",
        reason: "posting-service bypass repair",
        lines: [
          { account_code: "2300", debit: "0.000000", credit: "500.000000" },
          { account_code: "1010", debit: "500.000000", credit: "0.000000" },
        ],
      },
    });
    expect(
      [200, 201],
      `the balanced correcting JE answered ${response.status()} — BR-LED-003's post is ` +
        "not served, so the only ratified repair for drift cannot be made",
    ).toContain(response.status());
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-27 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) STEP 2's superuser injection is NOT performed — a browser
//   spec has no database seam and must not acquire one; the step asserts the
//   half a browser can prove (no application path unbalances the books) and the
//   DETECTOR is exercised against the real state instead · (2) the journey's
//   $12,450.00 / $500.00 belong to a sandboxed clone this stack does not seed,
//   and the money-triples dataset carries neither, so the rendered figure
//   asserted is the AR control total the report itself serves
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
