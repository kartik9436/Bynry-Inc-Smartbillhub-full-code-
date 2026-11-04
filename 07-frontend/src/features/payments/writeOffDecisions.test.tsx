// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · CS-25 · task 63 — Reject on a request and Reverse on an
//           approved write-off. The two doors landed 2026-09-01 and no screen
//           called either, so **an approved write-off could not be rejected or
//           undone by anybody.**
// Story:    US-PAY-012 (write-offs)   Screens: S36
// Rules:    BR-PAY-1120 (the four-state set; a rejection is a STATUS MOVE and a
//           reversal is a NEW ROW; both Admin-only on the SERVICE) ·
//           BR-PAY-020 · BR-PAY-002 (append-only) · BR-SHL-025 (a control this
//           deployment cannot honour renders VISIBLE and disabled with its
//           reason) · B14 rule 15 (row actions are icons with an accessible
//           name) · rule 31 (no database id is the visible value of a field)
// Defects:  DEF-3420 — every write-off refusal read as a payment-recording
//           error, in eleven languages, because the key resolved to the WRONG
//           sentence rather than to nothing.
// ───────────────────────────────────────────────────────
// The figures are US-PAY-012 TC-2's own: a **948.20** write-off, approved in
// August and put back in December, nets bad debt to **0.00** over the year.
import { cleanup } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { WriteOffApprovalRow } from "@/api/bankRecEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

import { WriteOffQueueTable, decisionBlockedReason } from "./WriteOffQueuePage";

const t: Translator = (key, params) => i18n.t(key, params);

function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

const ACCOUNT_UUID = "6d2f9a10-0000-4000-8000-0000000004a1";

function row(over: Partial<WriteOffApprovalRow> = {}): WriteOffApprovalRow {
  return {
    id: "wo-1",
    account_id: ACCOUNT_UUID,
    account_no: "A-10802",
    amount: "948.2000",
    currency: "USD",
    reason: "uncollectible",
    note: "Chased for four months.",
    status: "requested",
    requested_on: "2026-08-15",
    requested_by: "u-1",
    requested_by_name: "Dana Reed",
    approved_on: null,
    approved_by: null,
    approved_by_name: null,
    posted_to_ledger: false,
    journal_entry_id: null,
    ...over,
  };
}

function table(rows: WriteOffApprovalRow[]): string {
  // The account number is a record link (PO 2026-10-19), which builds a
  // tenant address — so the table mounts inside a tenant path.
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/acme/finance/revenue"]}>
      <WriteOffQueueTable
        rows={rows}
        currentUserId={null}
        t={t}
        onDecide={() => undefined}
      />
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CS-25 · the two decisions that had no way in", () => {
  it("a request waiting for a decision offers Refuse, and it is not disabled", () => {
    const html = table([row()]);
    expect(html).toContain(`aria-label="${escaped(t("payments.writeOffQueue.reject"))}"`);
    // The Refuse control on a `requested` row carries no reason and is live.
    expect(decisionBlockedReason(row(), "reject", t)).toBeUndefined();
  });

  it("an APPROVED write-off offers Put it back, which is the whole point", () => {
    const approved = row({ status: "approved", approved_on: "2026-08-16" });
    expect(decisionBlockedReason(approved, "reverse", t)).toBeUndefined();
    expect(table([approved])).toContain(
      `aria-label="${escaped(t("payments.writeOffQueue.reverse"))}"`,
    );
  });

  it("the wrong act on the wrong row is DISABLED WITH ITS REASON, never hidden", () => {
    // BR-SHL-025. A control that vanishes teaches that the product cannot do
    // the thing at all — which is what this screen taught for a day.
    const approved = row({ status: "approved" });
    expect(decisionBlockedReason(approved, "reject", t)).toBe(
      t("payments.writeOffQueue.blocked.reject"),
    );
    expect(decisionBlockedReason(row(), "reverse", t)).toBe(
      t("payments.writeOffQueue.blocked.reverse"),
    );
    const html = table([approved]);
    expect(html).toContain("disabled");
    expect(html).toContain(escaped(t("payments.writeOffQueue.blocked.reject")));
    // …and the control is still THERE, with its name.
    expect(html).toContain(`aria-label="${escaped(t("payments.writeOffQueue.reject"))}"`);
  });

  it("a decided row can be neither approved nor refused nor reversed", () => {
    for (const status of ["rejected", "reversed"]) {
      const decided = row({ status });
      expect(decisionBlockedReason(decided, "approve", t)).toBeDefined();
      expect(decisionBlockedReason(decided, "reject", t)).toBeDefined();
      expect(decisionBlockedReason(decided, "reverse", t)).toBeDefined();
    }
  });
});

describe("CS-25 · a refusal is a recorded decision, not a deletion", () => {
  it("names who refused it and prints the reason they gave", () => {
    const html = table([
      row({
        status: "rejected",
        rejected_on: "2026-08-18",
        rejected_by_name: "Priya Shah",
        rejection_reason: "The customer is on a payment plan and is meeting it.",
      }),
    ]);
    expect(html).toContain("Priya Shah");
    // The reason is *"the only thing the requester will be shown"* (CS-25), so
    // a queue that printed only the word `rejected` would send the same
    // request back tomorrow.
    expect(html).toContain(escaped("The customer is on a payment plan and is meeting it."));
  });

  it("a reversing row prints why the debt was taken back", () => {
    const html = table([
      row({
        status: "reversed",
        reverses_write_off_id: "wo-0",
        reversal_reason: "Approved against the wrong account.",
      }),
    ]);
    expect(html).toContain(escaped("Approved against the wrong account."));
    // B14 rule 31 — the write-off it corrects is a fact about another ROW and
    // its id is never printed.
    expect(html).not.toContain("wo-0");
  });
});

describe("B14 rule 31 · no database id is the visible value of a field", () => {
  it("an account with no number shows the stated absence, never its uuid", () => {
    // This cell read `account_no ?? account_id` until 2026-09-02 and printed a
    // raw uuid to a finance user, which is DEF-2580 one screen along.
    const html = table([row({ account_no: null })]);
    expect(html).not.toContain(ACCOUNT_UUID);
    expect(html).toContain(escaped(t("payments.writeOffQueue.noAccountNo")));
  });

  it("an account WITH a number still shows the number", () => {
    expect(table([row()])).toContain("A-10802");
  });
});

describe("B14 rule 15 · row actions are icons with an accessible name", () => {
  it("all three decisions render as named controls in one actions cell", () => {
    const html = table([row()]);
    for (const key of ["approve", "reject", "reverse"]) {
      expect(html).toContain(`aria-label="${escaped(t(`payments.writeOffQueue.${key}`))}"`);
    }
    // An icon with no accessible name renders beautifully and is unusable
    // without a mouse — the failure B14's own note on rule 15 names.
    expect(html).toContain("<svg");
  });
});

describe("DEF-3420 · a write-off refusal reads as a write-off refusal", () => {
  it("payments.write_off.refused resolves, and is not the payment sentence", () => {
    const sentence = t("payments.write_off.refused");
    expect(sentence).not.toBe("payments.write_off.refused");
    // ⚠ THE ASSERTION THAT MATTERS. The old key RESOLVED — that is why no gate
    // caught it — to *"This payment can't be recorded as asked. Check the date,
    // amount and account."*, shown to an approver who was not recording a
    // payment. G32 asks whether a key resolves; nothing asks whether the
    // sentence it resolves to is the right one.
    expect(sentence).not.toBe(t("payments.record.refused"));
    expect(sentence.toLowerCase()).not.toContain("payment");
  });

  it("every language answers it, not just English", () => {
    // The correction screen had to add its refusal in all eleven the same day
    // it shipped (DEF-3203), and a sentence missing in ten of them renders as
    // silence for everyone but the developer who wrote it.
    for (const lng of ["de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"]) {
      const sentence = i18n.getFixedT(lng)("payments.write_off.refused");
      expect(sentence).not.toBe("payments.write_off.refused");
      expect(sentence).not.toBe(i18n.getFixedT("en")("payments.write_off.refused"));
    }
  });
});
