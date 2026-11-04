// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-141-BRC07 — a refund's check number may be corrected, the same
//          way a payment's can (OQ-PAY-12614, CLOSED 2026-09-23, option b).
// Ruling:  PO, verbatim, 2026-09-23: *"One thing needs your sign-off, because
//          it is a money record: (b) Allow a correction, the same way you
//          allowed it for payments on 2 September"*. SHOWN: *Dana sends a
//          refund of $91.60 by check #10241 but types #10214; as built it can
//          never be changed.*
// Rules:   B14 rule 15 (an ICON with an accessible name) · rule 11 (the
//          consequence box) · rule 33 (rationale is ZERO words on screen — no
//          sentence about how long the old number is kept) · BR-SHL-025
//          (disabled WITH its reason, never hidden) · BR-PAY-1071
// Screens: S58 — the refunds list's row action and the form it opens
// ───────────────────────────────────────────────────────
//
// The figures are the PO's, copied: $91.60, sent as #10241, keyed as #10214.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider, partialMatchKey } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { RefundRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { RefundCorrectCheckModal, refundCorrectBlockedReason } from "./RefundCorrectCheckModal";
import {
  REFUNDS_REFRESH_KEYS,
  RefundRowActions,
  refundsAndCreditsQueryKey,
  refundsQueryKey,
} from "./RefundsPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const TENANT = "brazosbend";
const CHECK_WRITTEN = "10241";
const CHECK_TYPED = "10214";

/** The PO's refund, as `selectors.refund_row` serves it once issued. */
function refund(overrides: Partial<RefundRow> = {}): RefundRow {
  return {
    id: "rfd-9160",
    payment_id: "pay-0418",
    // ⚠ `P3.3` — `RefundRow` gained `account_id`, which the server has served
    // since `CR-059` CS-7 and the type omitted. `payments/0018` makes the
    // column NOT NULL, so a fixture without one describes a row that cannot
    // exist: a refund with no account is a cheque with no addressee.
    account_id: "acc-1042",
    amount: "91.6000",
    currency: "USD",
    status: "issued",
    method: "check",
    reference: CHECK_TYPED,
    reason: "Overpayment",
    requested_by: "user-marcus",
    requested_at: "2026-09-21T09:00:00Z",
    approved_by: "user-dana",
    approved_at: "2026-09-21T09:30:00Z",
    issued_at: "2026-09-21T10:00:00Z",
    cleared_at: null,
    voided_at: null,
    void_reason: null,
    journal_entry_id: "je-1",
    void_journal_entry_id: null,
    ...overrides,
  };
}

function client(): ApiClient & { post: ReturnType<typeof vi.fn> } {
  const post = vi.fn().mockResolvedValue({
    data: {
      refund_id: "rfd-9160",
      refund: refund({ reference: CHECK_WRITTEN }),
      corrected: { reference: CHECK_WRITTEN },
      previous: { reference: CHECK_TYPED },
      note: "stub reads 10241",
      unavailable: [],
    },
  });
  return { get: vi.fn(), post } as unknown as ApiClient & { post: ReturnType<typeof vi.fn> };
}

/** Mounted under the REAL path pattern (`DEF-CWP-3925`'s fixture lesson). */
function mount(node: JSX.Element) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/payments/refunds`]}>
          <Routes>
            <Route path="/:tenant/payments/:tab" element={node} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function form(row: RefundRow = refund(), api = client()) {
  const onCorrected = vi.fn();
  const view = mount(
    <RefundCorrectCheckModal
      client={api}
      refund={row}
      onClose={() => undefined}
      onCorrected={onCorrected}
    />,
  );
  return { ...view, api, onCorrected };
}

function type(root: HTMLElement, id: string, value: string): void {
  fireEvent.change(root.querySelector(`#${id}`) as HTMLInputElement, { target: { value } });
}

describe("CR-141 · who may correct, and on which row — the SERVICE's refusals, mirrored", () => {
  it("an Admin and a Billing Clerk may; an Executive may not", () => {
    expect(refundCorrectBlockedReason(refund(), "system_admin", t)).toBeNull();
    expect(refundCorrectBlockedReason(refund(), "billing_clerk", t)).toBeNull();
    expect(refundCorrectBlockedReason(refund(), "executive", t)).toBe(
      t("payments.refunds.adminOrClerkOnly"),
    );
    // A role not answered yet OFFERS the control; the service is the boundary.
    expect(refundCorrectBlockedReason(refund(), null, t)).toBeNull();
  });

  it("a refund with no check number has nothing to correct — the first is Issue's", () => {
    for (const row of [
      refund({ status: "approved", reference: null }),
      refund({ method: "ach", reference: null }),
      refund({ reference: "  " }),
    ]) {
      expect(refundCorrectBlockedReason(row, "system_admin", t)).toBe(
        t("payments.refunds.correct.noNumber"),
      );
    }
  });

  it("a canceled refund is closed", () => {
    expect(refundCorrectBlockedReason(refund({ status: "void" }), "system_admin", t)).toBe(
      t("payments.refunds.correct.closed"),
    );
  });

  it("a CLEARED refund may still be corrected — the bank line is where a typo is found", () => {
    expect(
      refundCorrectBlockedReason(refund({ status: "cleared" }), "billing_clerk", t),
    ).toBeNull();
  });
});

describe("CR-141 · the row action (B14 rule 15)", () => {
  function acts(row: RefundRow, role: string | null) {
    return renderToStaticMarkup(
      <RefundRowActions
        refund={row}
        role={role}
        t={t}
        onAct={() => undefined}
        onCorrect={() => undefined}
      />,
    );
  }

  it("is an icon named *Correct check number*, enabled on an issued refund", () => {
    const html = acts(refund(), "billing_clerk");
    expect(html).toContain(`aria-label="${t("payments.refunds.action.correct")}"`);
    expect(html).not.toContain(`>${t("payments.refunds.action.correct")}<`);
  });

  it("is drawn DISABLED WITH ITS REASON on a refund that has no number, never hidden", () => {
    const html = acts(refund({ status: "approved", reference: null }), "system_admin");
    expect(html).toContain(`aria-label="${t("payments.refunds.action.correct")}"`);
    expect(html).toContain(`title="${t("payments.refunds.correct.noNumber")}"`);
  });
});

describe("CR-141 · the form — the new number and why, nothing else", () => {
  it("opens on the number the row holds, and asks only for it and a reason", () => {
    const { container } = form();
    const number = container.querySelector<HTMLInputElement>("#reference");
    expect(number?.value).toBe(CHECK_TYPED);
    expect(number).toBeRequired();
    expect(container.querySelector("#note")).toBeRequired();
    // The payment door's other two fields are NOT signed for a refund.
    expect(container.querySelector("#memo")).toBeNull();
    expect(container.querySelector("#tender_id")).toBeNull();
    expect(container.querySelector("#amount")).toBeNull();
    expect(container.querySelector("#method")).toBeNull();
  });

  it("states that no money moves, in the kit's consequence box", () => {
    const { container } = form();
    const box = container.querySelector('[data-consequence="correct-check"]');
    expect(box).not.toBeNull();
    expect(box?.textContent).toContain(t("payments.refunds.correct.consequence.title"));
    expect(box?.textContent).toContain(t("payments.refunds.correct.consequence.body"));
  });

  it("says NOTHING about how long the old number is kept (B14 rule 33, OQ-1340)", () => {
    // The payment door's `CorrectionRetentionNote` was a `<details>`; it was
    // DELETED for exactly this reason (`P3.18`) and must not come back here.
    const { container } = form();
    expect(container.querySelector("details")).toBeNull();
    const text = (container.textContent ?? "").toLowerCase();
    for (const word of ["audit", "retention", "pruned", "permanent", "kept", "forever"]) {
      expect(text).not.toContain(word);
    }
  });

  it("sends the new number and the note to the named door — and nothing else", async () => {
    const { api, container, onCorrected } = form();
    type(container, "reference", ` ${CHECK_WRITTEN} `);
    type(container, "note", "the check stub reads 10241");
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const [path, body] = api.post.mock.calls[0] as [string, Record<string, unknown>];
    expect(path).toBe("/refunds/rfd-9160/correct-reference");
    expect(body).toEqual({ reference: CHECK_WRITTEN, note: "the check stub reads 10241" });
    await waitFor(() => expect(onCorrected).toHaveBeenCalled());
  });

  it("refuses the same number before the server is asked", async () => {
    const { api, container } = form();
    type(container, "note", "re-read");
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);
    await waitFor(() =>
      expect(container.textContent).toContain(t("payments.refunds.correct.sameNumber")),
    );
    expect(api.post).not.toHaveBeenCalled();
  });

  it("refuses a blank number and a blank reason before the server is asked", async () => {
    const { api, container } = form();
    type(container, "reference", "   ");
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);
    await waitFor(() =>
      expect(container.textContent).toContain(t("payments.refunds.correct.numberRequired")),
    );
    expect(container.textContent).toContain(t("payments.correct.noteRequired"));
    expect(api.post).not.toHaveBeenCalled();
  });
});

describe("CR-141 · the copy is US English (the catalogue sweep's rule)", () => {
  it("says *check*, never *cheque*, in every new English string", () => {
    for (const key of [
      "payments.refunds.action.correct",
      "payments.refunds.correct.number",
      "payments.refunds.correct.numberRequired",
      "payments.refunds.correct.sameNumber",
      "payments.refunds.correct.consequence.body",
      "payments.refunds.correct.noNumber",
      "payments.refunds.correct.refused",
    ]) {
      const text = i18n.t(key, { lng: "en" });
      expect(text).not.toMatch(/cheque/i);
      expect(text).toMatch(/check/i);
    }
  });
});

describe("DEF-PAY-6398 · an act refreshes every list the page reads", () => {
  it("each query key the page reads is covered by a refresh key, by TanStack's own matcher", () => {
    // `partialMatchKey` is the function `invalidateQueries` itself uses, so this
    // asks the real question — would the refresh reach this query — rather than
    // a string comparison that reads `"refunds"` as a prefix of
    // `"refunds-and-credits"`, which is exactly the mistake the defect was.
    const readKeys = [
      refundsAndCreditsQueryKey(1, 25, ""),
      refundsAndCreditsQueryKey(3, 50, "refund"),
      refundsQueryKey("requested"),
    ];
    for (const key of readKeys) {
      const covered = REFUNDS_REFRESH_KEYS.some((refreshKey) =>
        partialMatchKey([...key], [...refreshKey]),
      );
      expect(covered, JSON.stringify(key)).toBe(true);
    }
  });
});
