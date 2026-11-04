// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Task:     P3.10 (row actions on the batch lines) · P3.11 (say when a locked
//           batch no longer sums) · P3.12 (multi-line resolve, with a running
//           residual) — Finance blueprint p016, p049–p055
//           Screens: S39 (3·2 Batch) · S40 (3·4 Resolve)
// Rules:    CLAUDE.md hard rule 2 (money exact, never float) · hard rule 4 and
//           its ONE narrow `payments` exception · BR-PAY-884 (Σ of reversals
//           may never exceed the payment) · BR-PAY-019 (reason AND GL on every
//           difference) · BR-SHL-025 (a control that cannot act is DISABLED
//           WITH ITS REASON) · B14 rule 15 (two visible, then `…`) · rule 31
//           (no database id is a visible value) · rule 43 (a piece of UI is a
//           COMPONENT)
// Defects:  DEF-PAY-6651 (the drift cannot be derived from `members`) ·
//           DEF-PAY-6652 (`.fin-num` out-ranked by `PlainTable`)
// ───────────────────────────────────────────────────────
// **WHAT THIS FILE CAN AND CANNOT SEE, SAID OUT LOUD.**
//
// It renders to static markup, so it can read STRUCTURE — is the control there,
// does it carry its reason, does the residual reach zero — and it can read PURE
// ARITHMETIC. **It cannot read a computed style**, so `DEF-PAY-6652`'s
// right-alignment is NOT asserted here: a `toContain("text-right")` would pass
// over the exact bug, because the class was always in the DOM and it was the
// CASCADE that dropped it. That one is measured in Chromium by
// `10-scripts/p3_batch_line_walkthrough.mjs`, with `getComputedStyle`.
//
// **AND THE WORKED FIGURES ARE THE BLUEPRINT'S, COPIED AND NEVER RECOMPUTED.**
// p054–p055's card day: a shortfall of **−172.50** that is a **−147.50**
// processor fee AND a **−25.00** chargeback. p049's lock case, measured on a
// real PostgreSQL batch: recorded **2,388.84**, one member of **501.33**
// returned, live **1,887.51**, drift **−501.33**.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { DepositBatchDetail, DepositBatchMember } from "@/api/bankRecEndpoints";
import { ToastProvider } from "@/components/Toast";

import { DepositBatchPage, depositBatchQueryKey, withRow } from "./DepositBatchPage";
import { driftOf, isZeroAmount, memberReverseBlockedReason, residualOf, stillStandsOf, sumOf } from "./depositsShared";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

function member(over: Partial<DepositBatchMember> = {}): DepositBatchMember {
  return {
    payment_id: "01a0d3f3-a229-7062-9bf0-a792996f9af5",
    payment_no: "PY-260808-0040",
    confirmation: "4471",
    memo: "counter cheque",
    account_id: "01a0d3f3-0000-0000-0000-000000000001",
    account_no: "AC-2026-00045",
    amount: "501.330000",
    reversed_amount: "0.000000",
    currency: "USD",
    status: "cleared",
    posted_at: "2026-08-08T10:00:00Z",
    cleared_at: "2026-08-08T10:00:00Z",
    ...over,
  };
}

function detail(over: Partial<DepositBatchDetail> = {}): DepositBatchDetail {
  return {
    batch: {
      id: "01a0d3f3-8b66-7ff6-bf08-d43a6ce6ffa7",
      code: "DEP-260808-0002",
      method_code: "cheque",
      method_name: "Cheque",
      deposited_on: "2026-08-08",
      recorded_total: "2388.840000",
      bank_total: "2388.840000",
      difference: "0.000000",
      currency: "USD",
      payment_count: 9,
      status: "reconciled",
      locked: true,
    },
    live_total: "2388.840000",
    members: [member()],
    bank_line: null,
    trail: [],
    resolutions: [],
    unavailable: [],
    ...over,
  };
}

function renderDetail(seed: DepositBatchDetail): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(depositBatchQueryKey(seed.batch.id), seed);
  // ⚠ Mounted under the REAL path pattern. A bare `MemoryRouter` leaves
  // `useParams().tenant` undefined and every address the page builds comes out
  // `//payments/…` — a protocol-relative URL to another host, which reads as a
  // perfectly good string to `toContain` (hard-won law 2's fixture note).
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/finance/deposits/${seed.batch.id}`]}>
          <Routes>
            <Route path="/:tenant/finance/deposits/:batchId" element={<DepositBatchPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("P3.11 — a locked batch that no longer sums says so", () => {
  it("DEF-PAY-6651: the drift comes from live_total, and Σ members can never show it", () => {
    // The state measured on PostgreSQL: the reversing row is NOT a member and
    // the original's amount does not move, so the members still sum to exactly
    // what was frozen at the cut.
    const reversed = member({ reversed_amount: "501.330000" });
    // The member's own amount does NOT move when it is reversed (hard rule 4),
    // so Σ members is still the total frozen at the cut…
    expect(reversed.amount).toBe("501.330000");
    expect(sumOf(["2388.840000"])).toBe("2388.840000");
    // …which is why the OLD prescription — Σ(members) − recorded_total —
    // answers 0.00 on a batch that is 501.33 short.
    expect(driftOf("2388.840000", sumOf(["2388.840000"]))).toBe("0.000000");
    // The served figure tells the truth.
    expect(driftOf("2388.840000", "1887.510000")).toBe("-501.330000");
  });

  it("shows the Live payments tile, and names the gap only when there is one", () => {
    const steady = renderDetail(detail());
    expect(steady).toContain(t("payments.deposits.kpi.livePayments"));
    expect(steady).toContain(t("payments.deposits.kpi.reversalsIncluded"));
    expect(steady).not.toContain(t("payments.deposits.kpi.sinceTheCut"));

    const drifted = renderDetail(
      detail({
        live_total: "1887.510000",
        members: [member({ reversed_amount: "501.330000" })],
      }),
    );
    expect(drifted).toContain(t("payments.deposits.kpi.sinceTheCut"));
    // The FIGURE, formatted, not the raw six-decimal wire value.
    expect(drifted).toContain("1,887.51");
    expect(drifted).toContain("501.33");
    // …and the line that moved is marked, so the gap is attributable.
    expect(drifted).toContain(t("payments.deposits.memberReversed"));
  });

  it("states the absence rather than rendering a plausible $0.00", () => {
    const html = renderDetail(detail({ live_total: null }));
    expect(html).toContain(t("payments.deposits.kpi.liveUnavailable"));
    expect(driftOf("2388.840000", null)).toBeNull();
    // `null` is "we do not know", and it is never zero.
    expect(isZeroAmount(null)).toBe(false);
  });
});

describe("P3.10 — the three acts on a batch line", () => {
  it("draws two visible icons and an overflow, not three icons (B14 rule 15)", () => {
    const html = renderDetail(detail());
    expect(html).toContain(t("payments.detail.view"));
    expect(html).toContain(t("payments.correct.action"));
    expect(html).toContain(t("payments.reverse.action"));
    expect(html).toContain(t("table.rowActions.more"));
    // The reverse lives INSIDE the disclosure the `…` opens.
    const more = html.slice(html.indexOf("data-row-more"));
    expect(more).toContain(t("payments.reverse.action"));
  });

  it("addresses the payment by its NUMBER and never by a uuid (B14 rule 31)", () => {
    const html = renderDetail(detail());
    expect(html).toContain(`/${TENANT}/payments/PY-260808-0040`);
    expect(html).not.toContain("01a0d3f3-a229-7062-9bf0-a792996f9af5");
  });

  it("falls back to the id only when the row carries no number", () => {
    const html = renderDetail(detail({ members: [member({ payment_no: null })] }));
    expect(html).toContain(`/${TENANT}/payments/01a0d3f3-a229-7062-9bf0-a792996f9af5`);
  });

  it("BR-SHL-025: reverse is disabled WITH its reason when nothing still stands", () => {
    const spent = member({ reversed_amount: "501.330000" });
    expect(stillStandsOf(spent.amount, spent.reversed_amount)).toBe("0.000000");
    expect(memberReverseBlockedReason(spent, "system_admin", t)).toBe(
      t("payments.reverse.nothingStands"),
    );
    const html = renderDetail(detail({ members: [spent] }));
    expect(html).toContain(t("payments.reverse.nothingStands"));
    // Disabled, not removed — the clerk learns the rule.
    expect(html).toContain(t("payments.reverse.action"));
  });

  it("the LOCK is not a reason, because the service permits a reversal inside one", () => {
    // `_refuse_if_batch_locked` allows it (PO 2026-08-12, OQ-134). A screen
    // that greyed it here would contradict the service — and it is exactly the
    // case P3.11 exists to surface.
    const locked = detail({ batch: { ...detail().batch, locked: true, status: "reconciled" } });
    expect(memberReverseBlockedReason(locked.members[0], "system_admin", t)).toBeNull();
  });

  it("mirrors the service's other refusals and invents none", () => {
    expect(memberReverseBlockedReason(member(), "billing_clerk", t)).toBe(
      t("payments.reverse.adminOnly"),
    );
    expect(memberReverseBlockedReason(member({ status: "processing" }), null, t)).toBe(
      t("payments.reverse.notCleared"),
    );
    expect(memberReverseBlockedReason(member({ status: "reversed" }), null, t)).toBe(
      t("payments.reverse.isReversal"),
    );
    expect(memberReverseBlockedReason(member({ amount: "-501.330000" }), null, t)).toBe(
      t("payments.reverse.isReversal"),
    );
    // A null role OFFERS the control: the read may not have answered and the
    // server is the boundary either way.
    expect(memberReverseBlockedReason(member(), null, t)).toBeNull();
  });

  it("carries the memo, so a correction opens over what is there", () => {
    // Without this the memo box opens blank on a payment that has one, and the
    // first thing a clerk types replaces it.
    expect(member().memo).toBe("counter cheque");
  });
});

describe("P3.12 — one row per cause, and a residual that must reach zero", () => {
  // p054's worked case, verbatim: a card day short by $172.50 is routinely a
  // $147.50 processor fee AND a $25.00 chargeback.
  const FEE = "-147.50";
  const CHARGEBACK = "-25.00";
  const SHORT = "-172.500000";

  it("the blueprint's own case reconciles at exactly $0.00", () => {
    expect(residualOf(SHORT, [FEE])).toBe("-25.000000");
    expect(residualOf(SHORT, [FEE, CHARGEBACK])).toBe("0.000000");
    expect(isZeroAmount(residualOf(SHORT, [FEE, CHARGEBACK]))).toBe(true);
  });

  it("is exact at every magnitude NUMERIC(18,6) allows, where a float is not", () => {
    // ⚠⚠ **THIS ASSERTION WAS REWRITTEN AFTER A SABOTAGE RUN SHOWED IT COULD
    // NOT FAIL.** The first version claimed the blueprint's own figures break a
    // float; they do not (`DEF-PAY-6650` — `5120.40 - 4972.90` is exactly
    // `147.5` here, and so is `-172.50 - -147.50`). Replacing `residualOf`'s
    // body with `(Number(a) - Number(b)).toFixed(6)` then kept all sixteen
    // tests GREEN — because at ordinary money magnitudes the float error is
    // ~1e-12 and `toFixed(6)` rounds it away. **A check that cannot fail is
    // worse than no check**, so it now asserts the case that DOES separate the
    // two, and the sabotage was re-run against it.
    expect(Number("5120.40") - Number("4972.90")).toBe(147.5);
    expect(Number(SHORT) - Number(FEE)).toBe(-25);

    // The top of the column. `NUMERIC(18,6)` holds twelve integer digits, and
    // there the float's own spacing is coarser than the sixth decimal, so
    // rounding cannot hide it: the float answers `1000000000000.000000` and
    // loses the figure entirely.
    const huge = "999999999999.999999";
    expect((Number(huge) - Number("0.000001")).toFixed(6)).toBe("1000000000000.000000");
    expect(residualOf(huge, ["0.000001"])).toBe("999999999999.999998");

    // And the blueprint's own case, exactly.
    expect(residualOf(SHORT, [FEE])).toBe("-25.000000");
    expect(sumOf([FEE, CHARGEBACK])).toBe("-172.500000");
  });

  it("one forced reason cannot express the case — which is why the row repeats", () => {
    const rows = [
      { reason_code: "processor_fee", gl_account_id: "gl-6800", amount: FEE, note: "Sep settlement" },
      { reason_code: "returned_item", gl_account_id: "gl-1200", amount: CHARGEBACK, note: "Case 55120" },
    ];
    // Two reasons and two GL accounts, which is the whole point: filing the
    // $25 chargeback as a fee defeats CS-18.
    expect(new Set(rows.map((row) => row.reason_code)).size).toBe(2);
    expect(new Set(rows.map((row) => row.gl_account_id)).size).toBe(2);
    expect(residualOf(SHORT, rows.map((row) => row.amount))).toBe("0.000000");
  });

  it("an unreadable amount is NOT zero — the one state a plausible zero must not open", () => {
    expect(residualOf(SHORT, [FEE, "abc"])).toBeNull();
    expect(isZeroAmount(residualOf(SHORT, [FEE, "abc"]))).toBe(false);
    // …and neither is a bank that has not spoken.
    expect(residualOf(null, [FEE])).toBeNull();
  });

  it("the modal draws the trio and blocks the commit until the residual is zero", () => {
    const html = renderDetail(
      detail({
        batch: {
          ...detail().batch,
          status: "matched",
          locked: false,
          bank_total: "2216.340000",
          difference: SHORT,
        },
        bank_line: {
          bank_line_id: "bl-1",
          posted_on: "2026-08-10",
          reference: "DEPOSIT DEP-260808-0002",
          amount: "2216.340000",
          currency: "USD",
          line_no: 1,
          bank_account_name: "Chase Operating",
          bank_account_mask: "4021",
          statement_import_id: "si-1",
          period_start: "2026-08-01",
          period_end: "2026-08-31",
        },
      }),
    );
    // The door to the modal is on the page head while the batch is unlocked
    // and has a bank line.
    expect(html).toContain(t("payments.deposits.resolveDifference"));
  });

  it("drives the modal: two rows, the residual reaches $0.00, and the commit unblocks", () => {
    // ⚠⚠ **THIS TEST EXISTS BECAUSE A SABOTAGE RUN FOUND NOTHING WITHOUT IT.**
    // Changing the page to send only `drafts.slice(0, 1)` — i.e. throwing away
    // every explanation but the first, which is exactly the defect `P3.12`
    // repairs — left all sixteen tests and all 40 deposit tests GREEN. Every
    // other case in this file exercises `residualOf` DIRECTLY, so none of them
    // could see what the SCREEN does with it. This one opens the form and
    // types into it.
    const seed = detail({
      batch: {
        ...detail().batch,
        status: "matched",
        locked: false,
        bank_total: "2216.340000",
        difference: SHORT,
      },
      bank_line: {
        bank_line_id: "bl-1",
        posted_on: "2026-08-10",
        reference: "DEPOSIT DEP-260808-0002",
        amount: "2216.340000",
        currency: "USD",
        line_no: 1,
        bank_account_name: "Chase Operating",
        bank_account_mask: "4021",
        statement_import_id: "si-1",
        period_start: "2026-08-01",
        period_end: "2026-08-31",
      },
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(depositBatchQueryKey(seed.batch.id), seed);
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}/finance/deposits/${seed.batch.id}`]}>
            <Routes>
              <Route path="/:tenant/finance/deposits/:batchId" element={<DepositBatchPage />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: t("payments.deposits.resolveDifference") }));

    // It opens with ONE row, pre-filled with the WHOLE difference — and that
    // row alone already ties, which is the state a clerk must be able to leave.
    const residual = () => screen.getByTestId("resolve-residual").textContent ?? "";
    expect(residual()).toContain("$0.00");

    // The card day is not one cause. Split it: the fee here…
    const amountAt = (index: number) =>
      document.getElementById(`resolutions.${index}.amount`) as HTMLInputElement;
    fireEvent.change(amountAt(0), { target: { value: FEE } });
    // …and now $25.00 is unexplained and the commit says so.
    expect(residual()).toContain("$25.00");
    expect(screen.getByText(t("payments.deposits.form.residualBlocks"))).toBeTruthy();

    // A second row, for the chargeback — its own reason and its own GL.
    fireEvent.click(screen.getByRole("button", { name: t("payments.deposits.form.addExplanation") }));
    expect(amountAt(1)).toBeTruthy();
    fireEvent.change(amountAt(1), { target: { value: CHARGEBACK } });

    // p055's end state: Difference −$172.50, Explained −$172.50, Residual $0.00.
    expect(residual()).toContain("$0.00");
    expect(screen.queryByText(t("payments.deposits.form.residualBlocks"))).toBeNull();
  });

  it("the ✕ on the only row is disabled WITH its reason, not hidden (BR-SHL-025)", () => {
    const seed = detail({
      batch: { ...detail().batch, status: "matched", locked: false, difference: SHORT },
      bank_line: {
        bank_line_id: "bl-1",
        posted_on: "2026-08-10",
        reference: "r",
        amount: "2216.340000",
        currency: "USD",
        line_no: 1,
        bank_account_name: "Chase Operating",
        bank_account_mask: "4021",
        statement_import_id: "si-1",
        period_start: "2026-08-01",
        period_end: "2026-08-31",
      },
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(depositBatchQueryKey(seed.batch.id), seed);
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}/finance/deposits/${seed.batch.id}`]}>
            <Routes>
              <Route path="/:tenant/finance/deposits/:batchId" element={<DepositBatchPage />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: t("payments.deposits.resolveDifference") }));
    const remove = screen.getByRole("button", { name: t("payments.deposits.form.removeRow") });
    expect(remove.hasAttribute("disabled")).toBe(true);
    expect(remove.getAttribute("title")).toBe(t("payments.deposits.form.needsOneRow"));
  });

  it("withRow changes one row and leaves its neighbours alone", () => {
    const rows = [
      { reason_code: "a", gl_account_id: "g1", amount: FEE, note: "" },
      { reason_code: "b", gl_account_id: "g2", amount: CHARGEBACK, note: "" },
    ];
    const next = withRow(rows, 1, { amount: "-30.00" });
    expect(next[0]).toEqual(rows[0]);
    expect(next[1].amount).toBe("-30.00");
    expect(next[1].reason_code).toBe("b");
    // The array React holds is not mutated.
    expect(rows[1].amount).toBe(CHARGEBACK);
  });
});
