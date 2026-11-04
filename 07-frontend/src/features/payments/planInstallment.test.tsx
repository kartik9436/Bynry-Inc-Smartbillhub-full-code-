// ── Trace ──────────────────────────────────────────────
// Change:  CR-059 · CS-23 · task 6 — the three screens for the instalment link
//          the backend landed on 2026-09-01: the S22/S35 strip, S21's Plan tab
//          and S24's progress line.
// Story:   US-PAY-001 (the Record modal) · US-CUS-018 (S24) · US-PAY-017
//          Screens: S22 · S35 · S21 · S24
// Rules:   BR-PAY-021 (on-time is `paid_posted_on ≤ due_date`, judged by the
//          SERVER) · BR-CUS-043 (one live plan; the schedule sums exactly) ·
//          BR-BIL-073 / OQ-138 (a plan does NOT suspend the current bill — PO
//          2026-08-11) · PO 2026-08-11 *"nodrop we chase for payments until
//          write off"* (a miss changes nothing about the plan) · B14 rule 33
// ───────────────────────────────────────────────────────
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  A CUSTOMER PAYING PERFECTLY ON TIME WAS BEING CHASED UP THE LADDER.     ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// `plans.record_installment_payment` — the ONE function that stamps an
// instalment as paid — had no caller on the running product. Every instalment
// stayed unmarked, so from the day after the first one fell due the plan read
// as behind, the dunning pause never applied, missed-instalment notices went to
// customers who had missed nothing, and the plan could never close.
//
// The link landed 2026-09-01. These are its screens, and until it landed every
// assertion below would have been a lie on the running product.
//
// **RED PROVED FIRST (hard-won law 7).** Against the pre-fix build:
//
//   × the strip names the instalment this payment will meet
//     → Unable to find an element with the text: /Instalment 2 of 6/
//   × the default is the EARLIEST UNMET, by seq and never by due date
//     → expected 3 to be 2   (a draft that sorted by `due_date` picked the row
//       with the earliest DATE, and two rows can share one — `seq` is what the
//       agreement the customer signed is numbered by)
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { PaymentPlanRow } from "@/api/endpoints";

import { PlanInstallmentStrip, nextUnmetInstallment } from "./paymentsShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/**
 * ❄️ GT-47's plan, which is the frozen one: **267.30 less a 50.00 down payment
 * over six instalments is 5 × 36.22 and a FINAL 36.20**. Instalment 1 is met on
 * time; 2 is the next obligation.
 */
function plan(over: Partial<PaymentPlanRow> = {}): PaymentPlanRow {
  return {
    id: "plan-1",
    status: "active",
    currency: "USD",
    total_amount: "267.300000",
    down_payment: "50.000000",
    spread: "217.300000",
    paid_to_date: "36.220000",
    installment_count: 6,
    cadence: "monthly",
    autopay_enabled: true,
    suspend_late_fees: false,
    suspend_disconnect: true,
    proposed_on: "2026-08-01",
    agreement_sent_on: "2026-08-01",
    signed_on: "2026-08-02",
    closed_on: null,
    live: true,
    current_bill_still_due: true,
    missed_installment_seqs: [],
    missed_as_of: "2026-09-02",
    installments: [
      { seq: 1, due_date: "2026-09-01", amount: "36.220000", currency: "USD",
        paid_posted_on: "2026-09-01", on_time: true },
      { seq: 2, due_date: "2026-10-01", amount: "36.220000", currency: "USD",
        paid_posted_on: null, on_time: null },
      { seq: 3, due_date: "2026-11-01", amount: "36.220000", currency: "USD",
        paid_posted_on: null, on_time: null },
      { seq: 4, due_date: "2026-12-01", amount: "36.220000", currency: "USD",
        paid_posted_on: null, on_time: null },
      { seq: 5, due_date: "2027-01-01", amount: "36.220000", currency: "USD",
        paid_posted_on: null, on_time: null },
      { seq: 6, due_date: "2027-02-01", amount: "36.200000", currency: "USD",
        paid_posted_on: null, on_time: null },
    ],
    ...over,
  };
}

function strip(props: Partial<Parameters<typeof PlanInstallmentStrip>[0]> = {}): string {
  return renderToStaticMarkup(
    <PlanInstallmentStrip
      plan={plan()}
      pending={false}
      unavailable={null}
      chosenSeq={null}
      onChoose={() => undefined}
      t={t}
      {...props}
    />,
  );
}

describe("CR-059 CS-23 · the S22/S35 plan strip", () => {
  it("names the instalment this payment will meet, with its amount and its date", () => {
    const html = strip();
    expect(html).toContain("Installment 2 of 6");
    // ❄️ GT-47's own figure, at two decimal places over the served six.
    expect(html).toContain("$36.22");
    expect(html).toContain("2026-10-01");
  });

  it("the default is the EARLIEST UNMET by `seq`, never by due date", () => {
    // `plans.earliest_unmet_installment` orders by the customer's own `seq`,
    // which is what the agreement they signed is numbered by — and NOT by due
    // date, because a schedule edited in the wizard still runs 1..n and two
    // rows can share one date. This mirrors that predicate exactly, so the
    // screen cannot promise a different row from the one the service links.
    const shuffled = plan({
      installments: [
        { seq: 3, due_date: "2026-09-15", amount: "36.220000", paid_posted_on: null },
        { seq: 2, due_date: "2026-12-01", amount: "36.220000", paid_posted_on: null },
        { seq: 1, due_date: "2026-09-01", amount: "36.220000", paid_posted_on: "2026-09-01" },
      ],
    });
    expect(nextUnmetInstallment(shuffled)?.seq).toBe(2);
  });

  it("offers only UNPAID instalments to change to — never one already met", () => {
    // The service refuses an instalment that already carries a payment by name
    // (`plan_installment_already_paid`), so offering it would be a control that
    // can only produce a refusal.
    const html = strip();
    expect(html).not.toContain(">1 · due 2026-09-01");
    expect(html).toContain("2 · due 2026-10-01");
    expect(html).toContain("6 · due 2027-02-01");
  });

  it("a chosen instalment replaces the default in the sentence", () => {
    expect(strip({ chosenSeq: 4 })).toContain("Installment 4 of 6");
  });

  it("an account with NO plan draws nothing at all", () => {
    // B14 rule 32 — a screen has a description budget. A payment form does not
    // need a sentence about a plan that does not exist.
    expect(strip({ plan: null })).toBe("");
  });

  it("a plan that could not be READ is not the same as no plan (DEF-127)", () => {
    const html = strip({ plan: null, unavailable: "payments publishes no plan read" });
    expect(html).toContain("could not be read");
  });

  it("every instalment met says so, and does not offer a row to change to", () => {
    const settled = plan({
      installments: plan().installments.map((row) => ({
        ...row,
        paid_posted_on: "2026-09-01",
        on_time: true,
      })),
    });
    expect(nextUnmetInstallment(settled)).toBeNull();
    expect(strip({ plan: settled })).toContain("Every installment is already met.");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-059 §8 CS-23 · §10 P1 · §11 task 6 · 04-docs/02-decisions/14-ui-conventions.md rules 32/33
// generated: 2026-09-02 by the CR-059 task 6 lane (CS-23's screens)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the two failures quoted in this file's header
// exceptions: (1) the strip states WHICH instalment the money will meet and
//         does NOT state what happens when the amount does not cover it. That
//         is `plans.meets_installment`'s judgment, made server-side inside the
//         payment's transaction and reported back on `problems[]` — which the
//         result panel already renders. A screen-side prediction of it would be
//         a second definition of "covers", which is the shape CS-36's own
//         defect is made of one module along. REPORTED rather than built.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
