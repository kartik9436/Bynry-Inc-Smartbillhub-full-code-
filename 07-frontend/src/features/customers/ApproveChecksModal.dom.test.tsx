// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CUS-6350 · DEF-CUS-6352 · DEF-CUS-6420
// Rulings:  PO 2026-09-23 — the two approved layouts, the new-connection rule
//           (*"only where the address is not in Premises — in any status"*),
//           and the fee (*"either fee is paid or waived - no other condition"*)
// Rules:    B14 rules 11, 31, 33, 36, 43 · BR-SHL-025
// ───────────────────────────────────────────────────────
//
// **ASSERTED ON THE RENDERED DOM, PER ROW.** The defect is a clerk not being
// TOLD, so every case reads what a clerk would read — the row's state, its
// words, the button's `disabled` PROPERTY and the reason beside it — rather
// than a prop or a class the component was handed.
//
// ⚠ **THE FIXTURES ARE THE SERVER'S SHAPE, TRANSCRIBED FROM
// `service_request.py`'s constructors**, with this file's own figures (B14
// rule 37 — a drawn number is an illustration). A fixture holding sentences
// instead of keys would prove nothing about the thing this window exists for.
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { internalReferencesIn } from "@/testSupport/internalReferences";

import { ApproveChecksModal } from "./ApproveChecksModal";
import type { ServiceRequestDetail } from "./serviceRequestEndpoints";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const C = "customers.serviceRequest.condition.";

interface Cond {
  key: string;
  state: string;
  blocking: boolean;
  message_key: string | null;
  params?: Record<string, unknown>;
}

function summary(rows: Cond[]) {
  return {
    clear: rows.filter((row) => row.state === "clear").length,
    total: rows.length,
    blocking: rows.filter((row) => row.blocking && row.state !== "clear").map((row) => row.key),
    outstanding: rows
      .filter((row) => !row.blocking && row.state !== "clear" && row.state !== "not_reached")
      .map((row) => row.key),
    conditions: rows.map((row) => ({ params: {}, ...row })),
  };
}

const WINDOWS = {
  move_in: {
    submit: "customers.serviceRequest.approveChecks.submit.move_in",
    lines: [
      "customers.serviceRequest.approveChecks.effect.move_in.first",
      "customers.serviceRequest.approveChecks.effect.move_in.second",
    ],
  },
  new_connection: {
    submit: "customers.serviceRequest.approveChecks.submit.new_connection",
    lines: [
      "customers.serviceRequest.approveChecks.effect.new_connection.first",
      "customers.serviceRequest.approveChecks.effect.new_connection.second",
    ],
  },
} as const;

const TAIL: Cond[] = [
  { key: "no_blocking_arrears", state: "clear", blocking: false, message_key: null },
  { key: "eligibility_evidence", state: "clear", blocking: false, message_key: null },
  {
    key: "documents_verified",
    state: "blocked",
    blocking: false,
    message_key: `${C}requiredDocumentMissing`,
    params: { count: 2, doc_types: "proof_of_identity,signed_service_agreement" },
  },
  { key: "fee_settled", state: "clear", blocking: false, message_key: null },
];

/** The PO's own case: U-00003 at highland park, occupied by AC-2026-00012. */
const MOVE_IN_OCCUPIED: Cond[] = [
  {
    key: "premises_on_file",
    state: "clear",
    blocking: false,
    message_key: `${C}propertyOnFile`,
    params: { property: "highland park", city: "Ottumwa", place: "highland park, Ottumwa" },
  },
  {
    key: "unit_chosen",
    state: "clear",
    blocking: false,
    message_key: `${C}unitChosen`,
    params: { unit_no: "U-00003", label: "1" },
  },
  {
    key: "unit_free",
    state: "blocked",
    blocking: true,
    message_key: `${C}unitOccupied`,
    params: { account_no: "AC-2026-00012" },
  },
  { key: "no_other_move_in", state: "clear", blocking: false, message_key: `${C}noOtherMoveIn` },
  ...TAIL,
];

const MOVE_IN_FREE: Cond[] = MOVE_IN_OCCUPIED.map((row) =>
  row.key === "unit_free"
    ? { key: "unit_free", state: "clear", blocking: false, message_key: `${C}unitFree` }
    : row,
);

const NEW_CONNECTION_CLEAR: Cond[] = [
  {
    key: "address_not_in_premises",
    state: "clear",
    blocking: false,
    message_key: `${C}addressNotInPremises`,
  },
  { key: "no_open_request_here", state: "clear", blocking: false, message_key: `${C}noOpenRequestHere` },
  ...TAIL,
];

const NEW_CONNECTION_NEAR: Cond[] = [
  {
    key: "address_not_in_premises",
    state: "choose",
    blocking: true,
    message_key: `${C}addressLooksLike`,
    params: {
      as_given: "highland pk",
      property: "Highland Park",
      place: "Highland Park, 58502",
      premises_id: "01a0a444-5ad2-7e88-be8a-bdb8aa86c05e",
      premise_no: "P-00074",
    },
  },
  { key: "no_open_request_here", state: "clear", blocking: false, message_key: `${C}noOpenRequestHere` },
  ...TAIL,
];

const FEE_UNPAID: Cond = {
  key: "fee_settled",
  state: "blocked",
  blocking: true,
  message_key: `${C}feeOutstandingAmount`,
  params: { amount: "45.0000", currency: "USD" },
};

function detail(moveIn: Cond[], newConnection: Cond[], collected = "70.0000"): ServiceRequestDetail {
  const money = (amount: string) => ({ amount, display: amount.slice(0, -2), currency: "USD" });
  return {
    header: { request_no: "SR-26-0016", applicant: "David, Tim" },
    actions: { approve_blocked_by: ["outcome"] },
    fees: {
      quoted: money("70.0000"),
      collected: money(collected),
      outstanding: money("0.0000"),
    },
    decision: {
      options: [],
      commit: { outcome: null },
      what_approving_will_do: {
        move_in: { window: WINDOWS.move_in, conditions: summary(moveIn) },
        new_connection: { window: WINDOWS.new_connection, conditions: summary(newConnection) },
      },
    },
  } as unknown as ServiceRequestDetail;
}

function open(
  one: ServiceRequestDetail,
  handlers: { onSubmit?: ReturnType<typeof vi.fn>; onSameProperty?: ReturnType<typeof vi.fn> } = {},
): void {
  render(
    <ApproveChecksModal
      detail={one}
      t={t}
      onClose={() => undefined}
      onSubmit={handlers.onSubmit ?? (() => Promise.resolve({ ok: true } as const))}
      onSameProperty={handlers.onSameProperty}
    />,
  );
}

function pick(kind: "move_in" | "new_connection"): void {
  fireEvent.click(document.querySelector(`[data-segment="${kind}"]`) as Element);
}

function row(key: string): HTMLElement {
  const el = document.querySelector(`[data-check="${key}"]`);
  expect(el, `no row for ${key}`).not.toBeNull();
  return el as HTMLElement;
}

function approveButton(kind: "move_in" | "new_connection"): HTMLButtonElement {
  return screen.getByRole("button", {
    name: t(`customers.serviceRequest.approveChecks.submit.${kind}`),
  }) as HTMLButtonElement;
}

describe("the Approve window — the PO's two approved layouts", () => {
  afterEach(cleanup);

  it("MOVE-IN: a ✗ names the occupier by account NUMBER and disables Approve, with its reason", () => {
    open(detail(MOVE_IN_OCCUPIED, NEW_CONNECTION_CLEAR));
    pick("move_in");

    expect(row("premises_on_file")).toHaveAttribute("data-check-state", "ok");
    expect(row("premises_on_file")).toHaveTextContent("highland park, Ottumwa");
    expect(row("unit_chosen")).toHaveTextContent("U-00003 · 1");
    expect(row("unit_free")).toHaveAttribute("data-check-state", "bad");
    expect(row("unit_free")).toHaveTextContent("AC-2026-00012");
    expect(row("documents_verified")).toHaveAttribute("data-check-state", "noted");
    expect(row("fee_settled")).toHaveTextContent("$70.00");

    // BR-SHL-025 — disabled WITH its reason, in words, on the screen.
    expect(approveButton("move_in")).toBeDisabled();
    const reason = document.querySelector("[data-commit-blocked]");
    expect(reason?.textContent).toContain(t(`${C}unit_free`));
  });

  it("MOVE-IN, unit free: Approve is live, reads 'Approve', and the two lines are the move-in's", () => {
    open(detail(MOVE_IN_FREE, NEW_CONNECTION_CLEAR));
    pick("move_in");
    expect(approveButton("move_in")).not.toBeDisabled();
    expect(document.querySelector("[data-commit-blocked]")).toBeNull();
    const box = document.querySelector('[data-consequence="approve-move_in"]');
    expect(box?.textContent).toContain(t("customers.serviceRequest.approveChecks.effect.move_in.first"));
    expect(box?.textContent).toContain(t("customers.serviceRequest.approveChecks.effect.move_in.second"));
  });

  it("DEF-CUS-6352 — nothing on a MOVE-IN says it raises a build", () => {
    open(detail(MOVE_IN_FREE, NEW_CONNECTION_CLEAR));
    pick("move_in");
    const text = document.body.textContent ?? "";
    for (const key of [
      "customers.serviceRequest.approveChecks.submit.new_connection",
      "customers.serviceRequest.approveChecks.effect.new_connection.first",
      "customers.serviceRequest.willDo.approve.job_is_raised_naming_this_request",
      "customers.serviceRequest.willDo.approve.the_outstanding_travels_with_it",
      "customers.serviceRequest.approve.documentsAsked",
    ]) {
      expect(text).not.toContain(t(key));
    }
    expect(text.toLowerCase()).not.toContain("build");
  });

  it("NEW CONNECTION: there is NO Unit-free row, and the two lines are the build's", () => {
    open(detail(MOVE_IN_FREE, NEW_CONNECTION_CLEAR));
    pick("new_connection");
    expect(document.querySelector('[data-check="unit_free"]')).toBeNull();
    expect(document.querySelector('[data-check="unit_chosen"]')).toBeNull();
    expect(row("address_not_in_premises")).toHaveTextContent(
      t("customers.serviceRequest.checkFact.addressNotInPremises"),
    );
    expect(row("no_open_request_here")).toHaveAttribute("data-check-state", "ok");
    expect(approveButton("new_connection")).not.toBeDisabled();
    expect(document.querySelector('[data-consequence="approve-new_connection"]')?.textContent).toContain(
      t("customers.serviceRequest.approveChecks.effect.new_connection.first"),
    );
  });

  it("NEW CONNECTION, near match: Approve stays OFF until the clerk answers; 'It's a new address' clears it and travels with the approval", async () => {
    const onSubmit = vi.fn(() => Promise.resolve({ ok: true } as const));
    const onSameProperty = vi.fn();
    open(detail(MOVE_IN_FREE, NEW_CONNECTION_NEAR), { onSubmit, onSameProperty });
    pick("new_connection");

    const near = row("address_not_in_premises");
    expect(near).toHaveAttribute("data-check-state", "noted");
    expect(near).toHaveTextContent("highland pk");
    expect(near).toHaveTextContent("Highland Park, 58502");
    expect(approveButton("new_connection")).toBeDisabled();
    expect(document.querySelector("[data-commit-blocked]")?.textContent).toBe(
      t("customers.serviceRequest.approveChecks.chooseFirst"),
    );

    // *Same property* PICKS the row through the capture door, by its id —
    // which rides in the payload and never on the screen (B14 rule 31).
    fireEvent.click(near.querySelector('[data-action="same-property"]') as Element);
    expect(onSameProperty).toHaveBeenCalledWith("01a0a444-5ad2-7e88-be8a-bdb8aa86c05e");
    expect(document.body.textContent).not.toContain("01a0a444");

    fireEvent.click(near.querySelector('[data-action="new-address"]') as Element);
    expect(row("address_not_in_premises")).toHaveAttribute("data-check-state", "ok");
    expect(row("address_not_in_premises")).toHaveTextContent(
      t("customers.serviceRequest.checkFact.addressDeclaredNew"),
    );
    expect(approveButton("new_connection")).not.toBeDisabled();
    fireEvent.click(approveButton("new_connection"));
    await vi.waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit).toHaveBeenCalledWith("new_connection", { addressIsNew: true, customFieldPicks: {} });
  });

  it("NEW CONNECTION in Premises: ✗ 'In Premises · use a move-in', Approve off", () => {
    const inPremises: Cond[] = [
      {
        key: "address_not_in_premises",
        state: "blocked",
        blocking: true,
        message_key: `${C}addressInPremises`,
        params: { property: "highland park" },
      },
      { key: "no_open_request_here", state: "not_reached", blocking: false, message_key: `${C}needsAddress` },
      ...TAIL,
    ];
    open(detail(MOVE_IN_FREE, inPremises));
    pick("new_connection");
    expect(row("address_not_in_premises")).toHaveAttribute("data-check-state", "bad");
    expect(row("address_not_in_premises")).toHaveTextContent(
      t("customers.serviceRequest.checkFact.addressInPremises"),
    );
    expect(row("no_open_request_here")).toHaveAttribute("data-check-state", "notReached");
    expect(approveButton("new_connection")).toBeDisabled();
  });

  // PO 2026-10-11, option A — graded before the click, not refused after it.
  it("address already in Premises: New connection is greyed out with its reason, and Move-in is picked", () => {
    const one = detail(MOVE_IN_FREE, NEW_CONNECTION_CLEAR);
    (one.decision as unknown as { options: unknown[] }).options = [
      {
        outcome: "new_connection",
        verdict: "not_possible",
        message_key: "customers.serviceRequest.checkFact.addressInPremises",
      },
      { outcome: "move_in", verdict: "possible", message_key: null },
    ];
    open(one);
    const newConnection = document.querySelector('[data-segment="new_connection"]') as HTMLElement;
    expect(newConnection).toHaveAttribute("data-segment-disabled", "true");
    expect(document.body.textContent).toContain(
      t("customers.serviceRequest.checkFact.addressInPremises"),
    );
    expect(document.querySelector('[data-segment="move_in"]')).toHaveAttribute("aria-checked", "true");
    expect(approveButton("move_in")).toBeEnabled();
  });

  it("DEF-CUS-6420 — an unpaid fee is ✗ at TWO decimals with its ways out in words, and holds Approve", () => {
    const withFee = MOVE_IN_FREE.map((one) => (one.key === "fee_settled" ? FEE_UNPAID : one));
    open(detail(withFee, NEW_CONNECTION_CLEAR, "0.0000"));
    pick("move_in");
    const fee = row("fee_settled");
    expect(fee).toHaveAttribute("data-check-state", "bad");
    expect(fee).toHaveTextContent("$45.00");
    expect(fee.textContent).not.toContain("45.0000");
    expect(fee.textContent).not.toContain("USD");
    expect(fee).toHaveTextContent(t("customers.serviceRequest.checkFact.feeWaysOut"));
    expect(approveButton("move_in")).toBeDisabled();
    // Rationale is zero words on screen (B14 rule 33) — the old sentence's
    // second half is gone everywhere.
    expect(document.body.textContent).not.toContain("Approval is not blocked");
  });

  it("the window leaks nothing internal — no id, no rule, no code", () => {
    open(detail(MOVE_IN_OCCUPIED, NEW_CONNECTION_NEAR));
    pick("move_in");
    expect(internalReferencesIn(document.body)).toEqual([]);
    const text = document.body.textContent ?? "";
    for (const leak of ["proof_of_identity", "unit_free", "no_blocking_arrears", "message_key"]) {
      expect(text).not.toContain(leak);
    }
    // No catalogue KEY rendered raw anywhere.
    expect(text).not.toContain("customers.serviceRequest.");
  });
});

// ── DEF-CUS-10251 — a portal request is approved only once staff set its
//    category (PO 2026-10-18, *"this is correct"*; image 05-approve.png) ─────
describe("DEF-CUS-10251 · Category to be set (image 05)", () => {
  afterEach(cleanup);

  /** A request from the portal, still with no category, and the customer's
   *  own words the window summarises. */
  function portalDetail(categoryToBeSet: boolean): ServiceRequestDetail {
    const base = detail(MOVE_IN_FREE, NEW_CONNECTION_CLEAR) as unknown as Record<string, unknown>;
    return {
      ...base,
      header: { request_no: "SR-26-0031", applicant: "Maria Lopez", channel: "customer_portal" },
      applicant: {
        name: "Maria Lopez",
        phone: "(734) 555-0182",
        email: null,
        co_applicant: { name: "Daniel Lopez", email: null, phone: null },
        co_applicants: [
          {
            full_name: "Daniel Lopez",
            relationship: "spouse",
            phone: null,
            email: null,
            contact_by: null,
            date_of_birth: "1986-09-30",
            responsible_for_bills: false,
            ssn_last4: null,
            driving_licence_last4: null,
          },
        ],
        identifier: { ssn_last4: "4471", ssn_present: false, stored_encrypted: false },
        category_to_be_set: categoryToBeSet,
        customer_category: { account_type: null, account_subtype: null, not_yet_categorised: true },
      },
      documents: { documents: [{ name: "maria-id.jpg" }, { name: "lease.pdf" }] },
    } as unknown as ServiceRequestDetail;
  }

  it("holds Approve with 'Set the category first.' while the category is not set", () => {
    render(
      <ApproveChecksModal
        detail={portalDetail(true)}
        t={t}
        onClose={() => undefined}
        onSubmit={() => Promise.resolve({ ok: true } as const)}
        categoryPicker={<div data-picker-slot="" />}
      />,
    );
    pick("move_in");
    expect(approveButton("move_in")).toBeDisabled();
    expect(document.querySelector("[data-commit-blocked]")?.textContent).toContain(
      t("customers.serviceRequest.categoryToSet.first"),
    );
    // The host's pickers are drawn FIRST, above the kind.
    const slot = document.querySelector("[data-picker-slot]") as Element;
    const kind = document.querySelector("[data-outcome-picker]") as Element;
    expect(slot.compareDocumentPosition(kind) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("is live again once the category is set", () => {
    render(
      <ApproveChecksModal
        detail={portalDetail(false)}
        t={t}
        onClose={() => undefined}
        onSubmit={() => Promise.resolve({ ok: true } as const)}
      />,
    );
    pick("move_in");
    expect(approveButton("move_in")).not.toBeDisabled();
  });

  it("shows what came from the customer — name, phone, SSN last four, co-applicant, documents", () => {
    render(
      <ApproveChecksModal
        detail={portalDetail(true)}
        t={t}
        onClose={() => undefined}
        onSubmit={() => Promise.resolve({ ok: true } as const)}
      />,
    );
    const from = document.querySelector("[data-from-the-customer]") as HTMLElement;
    expect(from.querySelector('[data-from-row="name"]')?.textContent).toContain("Maria Lopez");
    expect(from.querySelector('[data-from-row="phone"]')?.textContent).toContain("(734) 555-0182");
    expect(from.querySelector('[data-from-row="ssn"]')?.textContent).toContain(
      t("customers.serviceRequest.categoryToSet.from.ssnLast4", { last4: "4471" }),
    );
    expect(from.querySelector('[data-from-row="co_applicant"]')?.textContent).toContain(
      "Daniel Lopez (Spouse)",
    );
    expect(from.querySelector('[data-from-row="documents"]')?.textContent).toContain(
      "maria-id.jpg, lease.pdf",
    );
  });
});
