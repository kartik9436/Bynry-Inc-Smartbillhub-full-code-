// @vitest-environment jsdom
/**
 * `DEF-PAY-10323` — the RECONCILED tile on the payment page.
 *
 * A batch reconciled one-to-one read *Banked, not matched*; the server now
 * serves the tie for both shapes, and the tile says which state it is in.
 */
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { PaymentReconciliation, PaymentSource } from "@/api/paymentDetailEndpoints";
import "@/i18n";

import { PaymentHeaderStrip } from "./paymentDetailShared";

afterEach(cleanup);

const SOURCE: PaymentSource = {
  origin: "entry",
  origin_is_derived: false,
  taken_by: null,
  counter_session_ref: null,
  channel: null,
  terminal: null,
  return_code: null,
};

function tie(overrides: Partial<PaymentReconciliation>): PaymentReconciliation {
  return {
    batch_code: "DEP-261021-0005",
    batch_status: "reconciled",
    matched_at: "2026-10-16T09:00:00+00:00",
    bank_line_count: 1,
    batch_count: 1,
    bank_posted_on: "2026-10-16",
    reconciled_at: "2026-10-16T09:00:00+00:00",
    reference: null,
    ...overrides,
  };
}

function strip(reconciled: PaymentReconciliation | null) {
  render(
    <PaymentHeaderStrip
      source={SOURCE}
      batchRef="DEP-261021-0005"
      reconciled={reconciled}
      status="cleared"
    />,
  );
  return screen.getByTestId("payment-header-strip");
}

describe("DEF-PAY-10323 — the RECONCILED tile", () => {
  it("a batch reconciled 1:1 reads Reconciled, never Banked, not matched", () => {
    const el = strip(tie({}));
    // "Reconciled" is also the tile's LABEL, so the sub-line is asserted whole.
    expect(el).toHaveTextContent("Reconciled · 1 batches, 1 bank line");
    expect(el).not.toHaveTextContent("Banked, not matched");
  });

  it("matched but not reconciled says Matched", () => {
    const el = strip(tie({ batch_status: "matched", reconciled_at: null }));
    expect(el).toHaveTextContent("Matched · 1 batches, 1 bank line");
    expect(el).not.toHaveTextContent("Banked, not matched");
  });

  it("an unmatched batch reads Banked, not matched", () => {
    const el = strip(
      tie({
        batch_status: "unmatched",
        matched_at: null,
        bank_line_count: null,
        batch_count: null,
        bank_posted_on: null,
        reconciled_at: null,
      }),
    );
    expect(el).toHaveTextContent("Banked, not matched");
  });
});
