// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: `DEF-PAY-6331` — the cheque number was collected on RAISE, days
//          before a cheque existed, and `POST /refunds/{id}/issue` accepted
//          none, so the real number had nowhere to go.
//          `DEF-PAY-6332` — neither money-out form carried its consequence
//          box, and Issue committed money in the STANDARD tier, like Save.
// Rules:   B14 rule 11 (a consequence preview before a commit that writes
//          money) · B14 rule 6 (danger tier on a destructive commit) · B14
//          rule 33 (a consequence is ≤6 words per sentence, at most two,
//          never cut below clarity) · B14 rule 43 (a piece of UI is a
//          COMPONENT — the kit's `ConsequenceBox`, not a shape this screen
//          invents) · BR-PAY-014 (*"check/ACH v1"*) · US-PAY-011 §5
//          (*"required for check"*)
// Blueprint:05-prototype/06 Payments Page Blueprint.pdf p076-p078, read as
//          IMAGES at scale 2.0 (B14 rule 42). 6·3a's TODAY row: *"Built.
//          Missing only the consequence box."* 6·3b's: *"Built. The commit
//          renders in the standard tier, like Save."*
// Screens: S58 · 6·3a Raise a refund · 6·3b Issue this refund
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS A SEPARATE FILE FROM `consequenceOnMoneyForms.dom.test.tsx`,
// AND WHY THAT IS A COMPROMISE RATHER THAN A PREFERENCE
// ══════════════════════════════════════════════════════════════════════════
// `DEF-PAY-6332`'s own remedy column says to EXTEND that file rather than
// write a third, and its reasoning is right: *"a rule-enforcing test whose
// file list is hand-maintained will keep missing the next form"* — which is
// exactly how the two forms where money actually LEAVES the utility came to be
// the two that file did not cover.
//
// It is a separate file anyway because on 2026-09-23 that file is mid-flight
// under another lane (`DEF-PAY-6317` renames `RecordPaymentModal` to
// `RecordPaymentForm`, and the rename's own screen file is uncommitted). A
// pathspec commit takes the WHOLE file, so editing it here would publish that
// lane's change without the component it names and turn the branch red —
// CLAUDE.md law 11, mechanism five, `DEF-168`.
//
// **THE FOLD IS THE FOLLOW-UP, AND IT HAS A SHAPE:** one exported list of the
// money-out forms, asserted over, so a new one cannot be added without
// appearing in the check. Recorded here rather than left as an intention,
// because an intention in a lane report is a thing nobody can count.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";

import { ToastProvider } from "@/components/Toast";
import type { ApiClient } from "@/api/client";
import type { AccountRow, PaymentRow, RefundRow } from "@/api/endpoints";

import { RaiseRefundModal, RefundActModal } from "./RefundsPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const TENANT = "brazosbend";

/** 6·3b's own worked row, and PE-9's figures where the drawing does not
 *  contradict them. The drawn `$246.00` is an ILLUSTRATION (B14 rule 37); what
 *  is asserted below is that the box states THE REFUND'S figure, not that it
 *  states any particular one. */
function refund(overrides: Partial<RefundRow> = {}): RefundRow {
  return {
    id: "rfd-0041",
    payment_id: "pay-0418",
    amount: "246.0000",
    currency: "USD",
    status: "approved",
    method: "check",
    reference: null,
    reason: "Closed in credit",
    requested_by: "Dana Whitfield",
    requested_at: "2026-09-18",
    approved_by: "M. Duarte",
    approved_at: "2026-09-20",
    issued_at: null,
    cleared_at: null,
    voided_at: null,
    void_reason: null,
    journal_entry_id: null,
    void_journal_entry_id: null,
    ...overrides,
  } as RefundRow;
}

function account(): AccountRow {
  return {
    id: "acc-0050",
    account_no: "AC-2026-00050",
    customer_no: "CU-2026-00050",
    name: "Raman, Priya",
    premise: "1408 Elm St · A",
    services: ["electric"],
    balance: "-246.000000",
    balance_currency: "USD",
    currency: "USD",
    status: "active",
    status_name: "Active",
    kind: "regular",
  } as unknown as AccountRow;
}

/** The overpayment the raise form draws back — PE-4's shape.
 *
 *  ⚠ **IT HAS TO BE SERVED OR THE FORM CANNOT BE SUBMITTED AT ALL**, and that
 *  is the fixture lesson rather than a detail: `raiseRefundSchema` requires a
 *  `payment_id`, so a test that served an empty payment list would watch the
 *  form refuse itself and could then assert anything at all about a body that
 *  was never sent. */
function payment(): PaymentRow {
  return {
    id: "pay-0418",
    payment_no: "PMT-2609-000418",
    account_id: "acc-0050",
    account_no: "AC-2026-00050",
    amount: "350.0000",
    currency: "USD",
    status: "cleared",
    type: "payment",
    method: "check",
    posted_at: "2026-09-01",
    cleared_at: "2026-09-01",
    applied_to: [],
  } as unknown as PaymentRow;
}

/** Serves the account search and the payment picker — the raise form's two
 *  reads. `post` is captured so the BODY can be asserted, which is the only
 *  place `DEF-PAY-6331`'s wire half is visible. */
function client(): ApiClient & { post: ReturnType<typeof vi.fn> } {
  const post = vi.fn().mockResolvedValue({
    data: { credit_position_after: "0.0000", currency: "USD", created: true },
  });
  return {
    get: vi.fn().mockImplementation((path: string) => {
      if (path === "/accounts") {
        const rows = [account()];
        return Promise.resolve({
          data: { results: rows, count: rows.length, page: 1, per: 50 },
        });
      }
      if (path === "/payments") {
        const rows = [payment()];
        return Promise.resolve({
          data: { results: rows, count: rows.length, page: 1, per: 50 },
        });
      }
      return Promise.resolve({ data: { results: [], count: 0 } });
    }),
    post,
  } as unknown as ApiClient & { post: ReturnType<typeof vi.fn> };
}

/** ⚠ **MOUNTED UNDER THE REAL PATH PATTERN**, for `DEF-CWP-3925`'s reason: a
 *  bare `MemoryRouter` leaves `useParams().tenant` undefined and every address
 *  a mounted screen builds comes out pointing at another host — a string a
 *  `toContain` reads as perfectly good. */
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

function raiseForm(api = client()) {
  const view = mount(
    <RaiseRefundModal
      client={api}
      dateFormat="MM/DD/YYYY"
      locale="en-US"
      onClose={() => undefined}
      onRaised={() => undefined}
    />,
  );
  return { ...view, api };
}

function issueForm(row: RefundRow = refund(), api = client()) {
  const view = mount(
    <RefundActModal
      client={api}
      act="issue"
      refund={row}
      dateFormat="MM/DD/YYYY"
      locale="en-US"
      onClose={() => undefined}
      onDone={() => undefined}
    />,
  );
  return { ...view, api };
}

/** Type an account number, wait for the served options, pick the row.
 *
 *  ⚠ **ONE CONTROL, ID `account_id` — AND THIS HELPER DROVE THE OLD TWO UNTIL
 *  IT WENT RED.** `AccountPickerFields` used to render a `#account_query` box
 *  beside a `#account_id` select; it is now a single `RemoteSearchSelectField`
 *  whose input IS `#account_id` and whose rows are `[role="option"]`, and the
 *  old box *"is gone with the second control"* (`paymentsShared.tsx`). The
 *  shape to copy is `accountSearch.dom.test.tsx`'s — one harness for one
 *  control, rather than a second understanding of it.
 *
 *  ⚠ **SCOPED TO THIS RENDER'S CONTAINER, NEVER `document`**, so a null says
 *  which form was missing rather than reporting about whatever else is mounted.
 */
async function chooseAccount(root: HTMLElement): Promise<void> {
  const box = root.querySelector<HTMLInputElement>("#account_id");
  expect(box, "the raise form did not render its account search").not.toBeNull();
  fireEvent.focus(box as HTMLInputElement);
  fireEvent.change(box as HTMLInputElement, { target: { value: "AC-2026-00050" } });
  await waitFor(() =>
    expect(root.querySelectorAll('[role="option"]').length).toBeGreaterThan(0),
  );
  fireEvent.click(root.querySelectorAll('[role="option"]')[0]);
}

/** Pick the served overpayment. Required: a refund still names ONE payment
 *  until `CS-7`'s picker is removed, and the schema refuses a blank. */
async function choosePayment(root: HTMLElement): Promise<void> {
  await waitFor(() => {
    const picker = root.querySelector<HTMLSelectElement>("#payment_id");
    expect(picker).not.toBeNull();
    expect((picker as HTMLSelectElement).options.length).toBeGreaterThan(1);
  });
  fireEvent.change(root.querySelector("#payment_id") as HTMLSelectElement, {
    target: { value: "pay-0418" },
  });
}

// ══════════════════════════════════════════════════════════════════════════
// DEF-PAY-6331 — the cheque number is collected where the cheque is written
// ══════════════════════════════════════════════════════════════════════════

describe("DEF-PAY-6331 — 6·3a Raise", () => {
  it("asks for NO cheque number, because no cheque exists yet", () => {
    const { container } = raiseForm();
    expect(container.querySelector("#reference")).toBeNull();
    // Asserted by the clerk's own word as well as by the id, because a field
    // renamed rather than removed would pass the id check alone.
    expect(container.textContent).not.toContain(t("payments.refunds.col.reference"));
  });

  it("never sends one on the wire", async () => {
    const { api, container } = raiseForm();
    await chooseAccount(container);
    await choosePayment(container);
    fireEvent.change(container.querySelector("#amount") as HTMLInputElement, {
      target: { value: "246.00" },
    });
    fireEvent.change(container.querySelector("#requested_at") as HTMLInputElement, {
      target: { value: "2026-09-18" },
    });
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const [path, body] = api.post.mock.calls[0] as [string, Record<string, unknown>];
    expect(path).toBe("/accounts/acc-0050/refunds");
    expect(body).not.toHaveProperty("reference");
  });
});

describe("DEF-PAY-6331 — 6·3b Issue", () => {
  it("asks for the cheque number, and requires it", () => {
    const { container } = issueForm();
    const field = container.querySelector<HTMLInputElement>("#reference");
    expect(field).not.toBeNull();
    expect(field).toBeRequired();
    expect(container.textContent).toContain(t("payments.refunds.col.reference"));
  });

  it("refuses to commit without one, before the server is asked", async () => {
    const { api, container } = issueForm();
    fireEvent.change(container.querySelector("#acted_at") as HTMLInputElement, {
      target: { value: "2026-09-21" },
    });
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);
    await waitFor(() =>
      expect(container.textContent).toContain(t("payments.refunds.chequeNumberRequired")),
    );
    expect(api.post).not.toHaveBeenCalled();
  });

  it("sends it on the wire when it is given", async () => {
    const { api, container } = issueForm();
    fireEvent.change(container.querySelector("#reference") as HTMLInputElement, {
      target: { value: "10307" },
    });
    fireEvent.change(container.querySelector("#acted_at") as HTMLInputElement, {
      target: { value: "2026-09-21" },
    });
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const [path, body] = api.post.mock.calls[0] as [string, Record<string, unknown>];
    expect(path).toBe("/refunds/rfd-0041/issue");
    expect(body.reference).toBe("10307");
  });

  it("shows nothing to fill for a BANK TRANSFER — only a cheque has one", () => {
    const { container } = issueForm(refund({ method: "ach" }));
    expect(container.querySelector("#reference")).toBeNull();
  });

  it("opens showing a number the row already carries, rather than an empty box", () => {
    const { container } = issueForm(refund({ reference: "10241" }));
    expect(container.querySelector<HTMLInputElement>("#reference")?.value).toBe("10241");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-PAY-6332 — a consequence box on both, and the danger tier on Issue
// ══════════════════════════════════════════════════════════════════════════

describe("DEF-PAY-6332 — 6·3a Raise", () => {
  it("draws the box once there is a figure to state", async () => {
    const { container } = raiseForm();
    expect(container.querySelector('[data-consequence="raise"]')).toBeNull();
    await chooseAccount(container);
    fireEvent.change(container.querySelector("#amount") as HTMLInputElement, {
      target: { value: "246.00" },
    });
    await waitFor(() =>
      expect(container.querySelector('[data-consequence="raise"]')).not.toBeNull(),
    );
    const box = container.querySelector('[data-consequence="raise"]');
    // The figure, the clerk's own way — and the sentence that says approval
    // stands between the ask and the money.
    expect(box?.textContent).toContain("$246.00");
    expect(box?.textContent).toContain(t("payments.refunds.raise.consequence.body"));
  });

  it("draws nothing on an empty form", () => {
    const { container } = raiseForm();
    expect(container.querySelector('[data-consequence="raise"]')).toBeNull();
  });

  it("never invents a currency when no account has been chosen", () => {
    const { container } = raiseForm();
    fireEvent.change(container.querySelector("#amount") as HTMLInputElement, {
      target: { value: "246.00" },
    });
    // An amount with no account has no currency, and BR-SHL-023 is one money
    // path: the box waits rather than picking one.
    expect(container.querySelector('[data-consequence="raise"]')).toBeNull();
  });
});

describe("DEF-PAY-6332 — 6·3b Issue", () => {
  it("draws the box, with the refund's own figure", () => {
    const { container } = issueForm();
    const box = container.querySelector('[data-consequence="issue"]');
    expect(box).not.toBeNull();
    expect(box?.textContent).toContain("$246.00");
    expect(box?.textContent).toContain(t("payments.refunds.issue.consequence.body"));
  });

  it("commits in the DANGER tier — money out is not Save", () => {
    const { container } = issueForm();
    const commit = container.querySelector('button[type="submit"]');
    expect(commit).not.toBeNull();
    expect(commit).toHaveAttribute("data-variant", "danger");
  });

  it("and the retired warning is GONE, not merely quieter", () => {
    const { container } = issueForm();
    // `payments.refunds.issueWarning` said "The money leaves now." four lines
    // above a box that says the same thing AND names the figure. B14 rule 32
    // caps the description budget; the second copy is the one a clerk learns
    // to read past. i18next renders a missing key as the key itself, so this
    // also catches a catalogue entry that came back.
    expect(container.textContent).not.toContain("payments.refunds.issueWarning");
    expect(container.textContent).not.toContain("The money leaves now.");
  });
});

describe("DEF-PAY-6332 — the tier is spent where it means something", () => {
  it.each(["approve", "clear", "void"] as const)(
    "leaves %s in the standard tier",
    (act) => {
      const { container } = mount(
        <RefundActModal
          client={client()}
          act={act}
          refund={refund({ status: act === "approve" ? "requested" : "issued" })}
          dateFormat="MM/DD/YYYY"
          locale="en-US"
          onClose={() => undefined}
          onDone={() => undefined}
        />,
      );
      // Approving moves no money, clearing posts nothing, and a void RESTORES
      // a credit. A tier spent on every act warns about nothing.
      expect(container.querySelector('button[type="submit"]')).not.toHaveAttribute(
        "data-variant",
        "danger",
      );
    },
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-PAY-6331 · DEF-PAY-6332 · 05-prototype/06 Payments Page Blueprint.pdf p076-p078 (images, scale 2.0) · 04-docs/02-decisions/14-ui-conventions.md rules 6, 11, 32, 33, 37, 38, 42, 43
// generated: 2026-09-23 by lane REFUND-MONEY
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
