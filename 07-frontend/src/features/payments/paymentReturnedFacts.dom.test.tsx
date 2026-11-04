// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-PAY-10016 (a returned payment said nothing near its status) ·
//          DEF-PAY-10017 (the history printed the raw reason word `nsf`)
// Screen:  S33 the payment page — the header strip's STATUS cell and ⑦ History
// Rules:   B14 rule 31/35 (a code is never shown; the catalogue's words are) ·
//          CLAUDE.md hard rule 4 (the original keeps its own status)
// ───────────────────────────────────────────────────────
// RED FIRST (law 7) at 2.561.2: the NOTE cell read `nsf` and the status cell
// read only *Cleared*.
// ⚠ What would pass wrongly: a panel that translated EVERY note — so a note a
// person typed is asserted to print as typed, even when it happens to be `nsf`.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { PaymentHeaderStrip, PaymentHistoryPanel } from "./paymentDetailShared";

afterEach(cleanup);

const SOURCE = {
  origin: "agent",
  origin_is_derived: false,
  taken_by: "USPayments",
  counter_session_ref: null,
  channel: null,
  terminal: null,
  return_code: null,
};

describe("DEF-PAY-10016 — a returned payment says so beside its status", () => {
  it("reads Cleared · Returned by the bank", () => {
    render(
      <PaymentHeaderStrip
        source={SOURCE}
        batchRef={null}
        reconciled={null}
        status="cleared"
        reversedFor="nsf"
      />,
    );
    const strip = screen.getByTestId("payment-header-strip");
    expect(strip).toHaveTextContent("Cleared");
    expect(strip).toHaveTextContent("Returned by the bank");
  });

  it("a payment nobody took back says nothing more", () => {
    render(
      <PaymentHeaderStrip source={SOURCE} batchRef={null} reconciled={null} status="cleared" />,
    );
    expect(screen.getByTestId("payment-header-strip")).not.toHaveTextContent("Returned");
  });
});

describe("DEF-PAY-10017 — a reason code reads in the catalogue's words", () => {
  it("prints Returned by the bank, never nsf", () => {
    render(
      <PaymentHistoryPanel
        rows={[
          {
            at: "2026-10-07T12:00:00Z",
            what: "payment.nsf",
            who: null,
            note: "nsf",
            note_key: "payments.reverse.reason.nsf",
          },
          {
            at: "2026-10-07T11:00:00Z",
            what: "payment.recorded",
            who: null,
            note: "nsf",
            note_key: null,
          },
        ]}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
      />,
    );
    const cells = Array.from(document.querySelectorAll("tbody tr")).map(
      (row) => row.lastElementChild?.textContent ?? "",
    );
    expect(cells[0]).toBe("Returned by the bank");
    // Words a person typed stay theirs.
    expect(cells[1]).toBe("nsf");
  });
});
