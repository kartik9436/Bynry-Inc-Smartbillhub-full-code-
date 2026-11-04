// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-059 · CS-4 · task 12 — P1, the open-bill picker and its running
//          remainder. Its backend half is task 11
//          (`GET /accounts/{id}/open-bills`, closing OQ-154).
// Story:   US-PAY-001 (the S22/S35 Record modal's allocation choice) ·
//          US-PAY-006 (allocation — the open bills a payment meets)
//          Screens: S22 · S35 (the Record modal on S33 and on S21)
// Rules:   BR-PAY-001 (the four staff choices — `specific` and `split` are the
//          two this picker switches on) · BR-BIL-004 (an issued bill's total is
//          immutable) · BR-BIL-072 (a budget bill ASKS for its level, not its
//          total — PO 2026-08-11 *"Level is due"*) · BR-TEN-042 (one currency) ·
//          B14 rule 31 (no database id is the visible value of a field) ·
//          CLAUDE.md rule 2 (money is a decimal string beside its CHAR(3);
//          never a float, displayed at 2 dp)
// ───────────────────────────────────────────────────────
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE ONE ASSERTION THIS FILE EXISTS FOR: 47.87 IS OFFERED, 247.87 IS NOT ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// The repo's own worked figure, `PE-2`: `BL-2608-018410` was issued at **247.87**
// and a 200.00 payment left **47.87** open. A picker built on `GET /invoices`
// would have offered the clerk 247.87 as the figure to aim at, and money aimed
// at 247.87 on a bill that owes 47.87 is a wrong allocation **nobody looking at
// the screen can see is wrong**. That is why the two choices shipped disabled
// for three weeks rather than shipping over the bill list.
//
// **RED PROVED FIRST (hard-won law 7).** Each assertion below was run against
// the pre-fix build before it was trusted green; the transcript is in the lane
// report. The shapes:
//
//   · the picker did not render at all — `Unable to find an element with the
//     text: Still owes` — because `specific` was `disabled: true` and nothing
//     drew a list;
//   · with the flags removed but the reason left in place,
//     `expected '…are switched off because we cannot yet show what each open
//     bill still owes…' not to contain 'switched off'`;
//   · with a picker that read `total` instead of `open_balance` — the exact
//     mistake CS-4 exists to prevent, run here and quoted verbatim:
//
//         × the picker aims at what a bill STILL OWES
//           → expected 'Owes $92.87 across 2 billsApplyBill #…' to contain '$47.87'
//         Tests  1 failed | 12 passed (13)
//
//     Note WHICH assertion caught it and which did not: the header still read
//     `Owes $92.87 across 2 bills` (the server sums it, so the sabotage could
//     not move it) and the row still showed `$247.87`. **Only an assertion that
//     names the figure a clerk aims at can see this**, which is why the OWES
//     column is read cell-by-cell rather than by a `toContain` over the table.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { OpenBillPosition } from "@/api/endpoints";
import i18n from "@/i18n";
import en from "@/i18n/locales/en.json";

import { OpenBillPicker, remainingToAllocate, targetsBody } from "./paymentsShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/**
 * `PE-2`'s position as `GET /accounts/{id}/open-bills` serves it — money at
 * FOUR decimal places on the wire (BR-TEN-080), rendered at two.
 *
 * `BL-2608-018410` is the bill the whole change is about: issued 247.87, 200.00
 * already allocated, **47.87 still open**. `BL-2607-018311` is a second, wholly
 * unpaid bill, so the position totals 45.00 + 47.87 = **92.87 across 2 bills**.
 */
function position(over: Partial<OpenBillPosition> = {}): OpenBillPosition {
  return {
    account_id: "acc-1042",
    account_no: "ACC-1042",
    currency: "USD",
    bills: [
      {
        invoice_id: "inv-018311",
        number: "BL-2607-018311",
        issued_on: "2026-07-08",
        total: "45.0000",
        amount_due: "45.0000",
        allocated: "0.0000",
        open_balance: "45.0000",
        currency: "USD",
        composition: null,
      },
      {
        invoice_id: "inv-018410",
        number: "BL-2608-018410",
        issued_on: "2026-08-08",
        total: "247.8700",
        amount_due: "247.8700",
        allocated: "200.0000",
        open_balance: "47.8700",
        currency: "USD",
        composition: null,
      },
    ],
    total_open: "92.8700",
    bill_count: 2,
    problems: [],
    ...over,
  };
}

function draw(props: {
  mode?: "specific" | "split";
  amount?: string;
  targets?: Record<string, string>;
  onTargets?: (next: Record<string, string>) => void;
  pos?: OpenBillPosition | undefined;
  pending?: boolean;
  failed?: boolean;
}) {
  return render(
    <OpenBillPicker
      position={
        props.pos === undefined && props.pending !== true && props.failed !== true
          ? position()
          : props.pos
      }
      pending={props.pending === true}
      failed={props.failed === true}
      mode={props.mode ?? "specific"}
      amount={props.amount ?? "100.00"}
      targets={props.targets ?? {}}
      onTargets={props.onTargets ?? (() => undefined)}
      t={t}
    />,
  );
}

afterEach(cleanup);

describe("CR-059 CS-4 · the picker aims at what a bill STILL OWES", () => {
  it("offers 47.87 for a bill issued at 247.87 — and shows both, so the clerk can see why", () => {
    const { container } = draw({});
    const text = container.textContent ?? "";
    // BOTH figures are on the row, which is the sentence CS-4 exists to make
    // sayable: "issued 247.87 · still owes 47.87".
    expect(text).toContain("$247.87");
    expect(text).toContain("$47.87");
    // And the OWES column — the one a clerk aims at — is the open balance.
    const owesCells = Array.from(container.querySelectorAll("tbody tr")).map(
      (row) => row.querySelectorAll("td")[4]?.textContent ?? "",
    );
    expect(owesCells).toEqual(["$45.00", "$47.87"]);
  });

  it("the header is the SERVER's sum over exactly these rows — 92.87 across 2 bills", () => {
    const { container } = draw({});
    expect(container.textContent ?? "").toContain("Owes $92.87 across 2 bills");
  });

  it("B14 rule 31: no invoice id reaches the screen, in text or in markup", () => {
    const { container } = draw({});
    expect(container.textContent ?? "").not.toContain("inv-018410");
    // Not on `title` either — unlike a plan name, a bill HAS a human-facing
    // number, so rule 31's "may ride on title" branch does not apply here.
    expect(container.innerHTML).not.toContain("inv-018410");
    expect(container.textContent ?? "").toContain("BL-2608-018410");
  });
});

describe("CR-059 CS-4 · the running remainder", () => {
  it("falls as the clerk aims money, and the arithmetic is exact", () => {
    // A clerk holding 100.00 who splits 47.87 onto the corrected bill has 52.13
    // left — computed on the exact NUMERIC grid, never through a float.
    const { container } = draw({
      mode: "split",
      amount: "100.00",
      targets: { "BL-2608-018410": "47.87" },
    });
    expect(container.textContent ?? "").toContain("Left to allocate $52.13");
  });

  it("goes NEGATIVE rather than flooring at zero when more is aimed than held", () => {
    // Flooring would hide exactly the mistake this control exists to prevent.
    const { container } = draw({
      mode: "split",
      amount: "40.00",
      targets: { "BL-2608-018410": "47.87" },
    });
    expect(container.textContent ?? "").toContain("-$52.13".slice(0, 1) + "$7.87");
  });

  it("a box that is not a decimal makes the remainder UNKNOWN, never smaller", () => {
    const { container } = draw({
      mode: "split",
      amount: "100.00",
      targets: { "BL-2608-018410": "4x.87" },
    });
    expect(container.textContent ?? "").toContain("Remaining amount cannot be read.");
    expect(remainingToAllocate("100.00", { A: "4x.87" })).toBeNull();
  });
});

describe("CR-059 CS-4 · the control is WIRED (hard-won law 2, G13)", () => {
  it("picking a bill under `specific` replaces the aim — one bill means one", () => {
    const seen: Record<string, string>[] = [];
    const { container } = draw({ mode: "specific", onTargets: (next) => seen.push(next) });
    const radios = container.querySelectorAll('input[type="radio"]');
    expect(radios).toHaveLength(2);
    fireEvent.click(radios[1]);
    expect(seen).toEqual([{ "BL-2608-018410": "" }]);
    // A second pick REPLACES rather than adds.
    fireEvent.click(radios[0]);
    expect(seen[1]).toEqual({ "BL-2607-018311": "" });
  });

  it("typing an amount under `split` records it against that bill's NUMBER", () => {
    const seen: Record<string, string>[] = [];
    const { container } = draw({ mode: "split", onTargets: (next) => seen.push(next) });
    const boxes = container.querySelectorAll('input[type="text"]');
    expect(boxes).toHaveLength(2);
    fireEvent.change(boxes[1], { target: { value: "47.87" } });
    expect(seen).toEqual([{ "BL-2608-018410": "47.87" }]);
    // The body carries the NUMBER, which is what the API takes — never the id.
    expect(targetsBody(seen[0])).toEqual([{ invoice_number: "BL-2608-018410", amount: "47.87" }]);
  });

  it("clearing a box removes the aim rather than sending an empty amount", () => {
    const seen: Record<string, string>[] = [];
    const { container } = draw({
      mode: "split",
      targets: { "BL-2608-018410": "47.87" },
      onTargets: (next) => seen.push(next),
    });
    const boxes = container.querySelectorAll('input[type="text"]');
    fireEvent.change(boxes[1], { target: { value: "" } });
    expect(seen).toEqual([{}]);
  });
});

describe("CR-059 CS-4 · the three states that are not a list", () => {
  it("in flight says so — it does not draw an empty picker", () => {
    const { container } = draw({ pending: true, pos: undefined });
    expect(container.textContent ?? "").toContain("Reading the open bills…");
    expect(container.querySelector("table")).toBeNull();
  });

  it("a read that failed says so — an empty list would claim nothing is owed", () => {
    const { container } = draw({ failed: true, pos: undefined });
    expect(container.textContent ?? "").toContain("Open bills could not be read.");
  });

  it("nothing open is a MEASURED fact, and names where the money goes", () => {
    draw({ pos: position({ bills: [], total_open: "0.0000", bill_count: 0 }) });
    expect(screen.getByText("No bill is open. This becomes account credit.")).toBeInTheDocument();
  });
});

describe("CR-059 CS-4 · the refusal text is GONE", () => {
  it("the key that said the picker was unavailable is deleted from the catalogue", () => {
    // ⚠ It was ONE key rendered TWICE — `allocationChoiceReason()` in
    // `paymentsShared`, called from `PaymentsPage` and from `AccountActions`.
    // CS-4's Proof: *"the two disabled options become enabled and the on-screen
    // reason text is deleted with them"*. An orphaned string is one a future
    // screen re-renders, so it leaves the catalogue rather than the call sites.
    expect(Object.keys(en)).not.toContain("payments.applyTo.pickerUnavailable");
    expect(t("payments.applyTo.specific")).toBe("A specific bill");
    expect(t("payments.applyTo.split")).toBe("Split across bills");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-059 §8 CS-4 · §10 P1 · §11 task 12 · 12-governance/01-open-questions.md OQ-154 (CLOSED, PO 2026-08-12 "Build the open-balance read") · 04-docs/02-decisions/14-ui-conventions.md rules 21/31/32/33
// generated: 2026-09-02 by the CR-059 task 12 lane (CS-4's screens)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the three shapes quoted in the header were each run
//        against the pre-fix build before any assertion was trusted green
// exceptions: (1) NO PAGINATION on the picker's table (B14 rule 16). It is a
//        form control over one account's open bills, not a list screen, and
//        rule 16 exempts a wizard summary table for the same reason — a page
//        boundary through the set a clerk is aiming at would hide a bill they
//        were told to pay. A utility of this size does not hold an account with
//        50 open bills; if one ever does, this is the place that has to grow a
//        pager and the exception is where a reader will look.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
