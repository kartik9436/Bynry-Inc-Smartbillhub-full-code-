// @vitest-environment jsdom
// CR-171-BRC10 P2.04 · P2.06 · P2.13 · P2.14 · P2.38 — the move-in details
// view, mounted at its REAL address (`/:tenant/moves/:ref`), for every status.
//
// What is held here, and why each is a test rather than a note:
//   * the buttons each status draws, in their drawn slots (images 03–17);
//   * a COMPLETED move-in has no `Open the account` / `Open the customer`
//     doors any more (S1 superseded by v18 / v22);
//   * the request modals send what §9.REQ says, and Decline is the danger tier;
//   * Cancel follows the PREVIEW's own answer — held while it refuses, live
//     with the refund it serves once it allows (OQ-CUS-12790 (a), built 2.541.0);
//   * the request page's *Open in Move-ins* door points at `/moves/SR-…` and the
//     screen it opens is this one (hard-won law 2: the hold-expiry test is the
//     address, written in the commit that builds the door).
import i18n from "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { auditEventSentence } from "@/features/audit/auditEvents";

import { MOVE_RECORD_ROUTE, MOVE_RECORD_SCREEN, MoveRecordPage, moveRecordPath } from "../MoveRecordPage";
import { moveInActionSlots } from "../moveRecordActions";
import type { MoveInStatus } from "../moveRecordActions";
import { cancelLines } from "./MoveActionsModals";
import { moveInEditPath, moveInStartPath } from "./MoveInDetail";

afterEach(cleanup);

const TENANT = "brazosbend";
const ABSENT = { code: "nothing_is_taken_before_complete", br_ref: "—", detail: "taken at Complete" };
const fact = (value: unknown = null) => ({ value, unavailable: value === null ? ABSENT : null });

function requestRecord(status: MoveInStatus, actions: string[]) {
  return {
    state: "request",
    kind: "move_in",
    status,
    reference: "SR-26-0014",
    move_no: null,
    title: "Verma, Asha",
    address_line: "301 Mill Pond Ln · Unit 4A",
    effective_on: "2026-10-12",
    request: { id: "req-14", request_no: "SR-26-0014", state: "submitted" },
    actions,
    step: null,
    chips: { requested_on: "2026-10-03", moves_in_on: "2026-10-12" },
    tiles: {
      move_in_date: { value: "2026-10-12", basis: "requested" },
      services: { count: 2, codes: ["water", "sewer"] },
      documents: { attached: 2, outstanding: { key: "documents_verified", params: { verified: 2, total: 2 } } },
      unit: { vacant: true, unit_label: "Unit 4A" },
    },
    facts: {
      request: {
        request_no: "SR-26-0014",
        channel: "portal",
        submitted_on: "2026-10-03",
        move_in_date: "2026-10-12",
        unit: { id: "unit-311", label: "Unit 4A", line: "301 Mill Pond Ln · Unit 4A" },
        building: { id: "prem-63", premise_no: "P-00063", address: "301 Mill Pond Ln" },
        unit_is_vacant: true,
        services: [{ code: "water" }, { code: "sewer" }],
        plan: { name: "Sample — Residential", code: "SCW-RES", version: 3, since: "2026-08-01" },
        customer_type: { account_type: "residential", account_type_name: "Residential", account_subtype: "Multi-family" },
      },
      who: {
        kind: "person",
        name: "Verma, Asha",
        matched: null,
        matched_absence: { code: "no_existing_customer" },
        email: "asha.v@example.com",
        phone: "(641) 555-0182",
        mailing_same: true,
        mailing: null,
      },
    },
    tab_counts: { documents: 2, messages: 1, audit: 2 },
    still_open: [],
    what_happened: {},
    opening_reads: { rows: [], unavailable: ABSENT },
  };
}

function jobRecord(status: MoveInStatus, over: Record<string, unknown> = {}) {
  const committed = status === "waiting_on_a_read" || status === "completed" || status === "cancelled";
  return {
    state: committed ? "completed" : status === "draft" ? "in_flight" : "approved",
    kind: "move_in",
    status,
    reference: "MVI-26-0011",
    move_no: "MVI-26-0011",
    title: "G, Nilesh",
    address_line: "301 Mill Pond Ln · Unit 3B",
    effective_on: "2026-10-10",
    park_id: status === "draft" ? "park-1" : null,
    request: { id: "req-14", request_no: "SR-26-0014", state: "approved" },
    actions: [],
    step: status === "draft" ? { reached: 3, of: 4, id: "billing", name: "Billing" } : null,
    chips: { unread_registers: 0, reads_committed: 1 },
    tiles: {
      opening_reads: { taken: 1, of: 2, recorded_on: "2026-10-10", unavailable: null },
      fees: { total: "95.0000", currency: "USD", lines: 2, paid: null, unavailable: null },
      work_orders: { raised: 0, open: 0, unavailable: null },
      messages: { count: null, unavailable: ABSENT },
    },
    facts: {
      details: {
        move_no: "MVI-26-0011",
        from_request: { id: "req-14", request_no: "SR-26-0014" },
        moved_in_on: "2026-10-10",
        customer: { id: null, customer_no: "CU-000412", name: "G, Nilesh" },
        account: committed ? { id: "acc-58", account_no: "AC-2026-00058" } : null,
        plan: { name: "Sample — Residential", code: "SCW-RES", version: 3, since: "2026-08-01" },
        unit: { id: "unit-308", label: "Unit 3B", line: "301 Mill Pond Ln · Unit 3B" },
        building: { id: "prem-63", premise_no: "P-00063", address: "301 Mill Pond Ln" },
        services: [{ code: "water" }, { code: "sewer" }],
        from_account: fact(),
        earliest_legal_start: fact(),
        committed_by: fact({ name: "Dana Whitfield", at: "2026-10-05" }),
      },
    },
    tab_counts: { work: 0, messages: null },
    still_open: committed ? [{ kind: "opening_read", register: "SM-7041" }] : [],
    what_happened: {},
    opening_reads: {
      rows: committed
        ? [
            { register: "W-5041 · total", reading: "2531.000000", unit: "kgal", read_at: "2026-10-10", how: "read" },
            { register: "SM-7041", reading: null, read_at: null, how: "not_estimated" },
          ]
        : [],
      unavailable: committed ? null : ABSENT,
    },
    money_taken: {
      required: fact(),
      taken: fact(),
      taken_on: null,
      tender: fact(),
      still_to_collect: fact(),
    },
    still_owed: { demand_register: fact(), visit: fact(), carry_forward: fact() },
    doors: {
      account: committed ? fact({ account_id: "acc-58", account_no: "AC-2026-00058" }) : fact(),
      customer: fact(),
    },
    fee_lines: [],
    co_owners: [],
    ...over,
  };
}

function mount(record: Record<string, unknown>, extra: { post?: ReturnType<typeof vi.fn>; get?: (url: string) => unknown } = {}) {
  const ref = String(record.reference);
  const post = extra.post ?? vi.fn(async () => ({ status: 200, data: {} }));
  const empty = { count: 0, next: null, previous: null, results: [] };
  const client = {
    get: vi.fn(async (url: string) => {
      const answered = extra.get?.(url);
      if (answered !== undefined) return { status: 200, data: answered };
      if (url.startsWith("/moves/")) return { status: 200, data: record };
      if (url.includes("/documents")) return { status: 200, data: { documents: [] } };
      return { status: 200, data: empty };
    }),
    post,
    delete: vi.fn(async () => ({ status: 204, data: null })),
  } as never;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/${TENANT}${moveRecordPath(ref)}`]}>
        <Routes>
          <Route
            path={`/:tenant${MOVE_RECORD_ROUTE}`}
            element={<MoveRecordPage client={client} timeZone="UTC" dateFormat="MM/DD/YYYY" />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { post, client };
}

async function head(): Promise<HTMLElement> {
  await waitFor(() => expect(document.querySelector("[data-screen='move-in-detail']")).toBeInTheDocument());
  return document.querySelector("[data-screen='move-in-detail']") as HTMLElement;
}

function headActions(): string[] {
  return Array.from(document.querySelectorAll("[data-testid^='move-action-']")).map(
    (el) => el.getAttribute("data-action") ?? "",
  );
}
function moreItems(): string[] {
  return Array.from(document.querySelectorAll("[data-testid^='move-more-']")).map((el) =>
    (el.getAttribute("data-testid") ?? "").replace("move-more-", ""),
  );
}

// ══════════════════════════════════════════════════════════════════════════
describe("CR-171 P2.04 · the buttons each status draws (images 03–17)", () => {
  const cases: [MoveInStatus, Record<string, unknown>, string[], string[]][] = [
    ["to_approve", requestRecord("to_approve", ["approve", "ask_for_more", "edit", "decline"]), ["askForMore", "approve"], ["edit", "decline"]],
    ["waiting_on_customer", requestRecord("waiting_on_customer", ["approve", "resend_ask", "edit", "decline"]), ["resendAsk", "approve"], ["edit", "decline"]],
    ["declined", requestRecord("declined", ["reopen"]), [], ["reopen"]],
    ["not_started", jobRecord("not_started"), ["start"], ["edit", "cancel"]],
    ["draft", jobRecord("draft"), ["edit"], ["discardDraft"]],
    ["waiting_on_a_read", jobRecord("waiting_on_a_read"), ["changeDate", "enterOpeningRead"], ["addWorkOrder", "sendMessage", "cancel"]],
    ["completed", jobRecord("completed"), [], ["sendMessage", "print"]],
    ["cancelled", jobRecord("cancelled"), [], []],
  ];
  it.each(cases)("%s — head and More ▾ as drawn", async (status, record, inHead, inMore) => {
    mount(record);
    const screenRoot = await head();
    expect(screenRoot).toHaveAttribute("data-status", status);
    expect(headActions()).toEqual(inHead);
    expect(moreItems()).toEqual(inMore);
  });

  it("exactly one primary in the head, whatever the status (B14 rule 2)", () => {
    for (const status of ["to_approve", "not_started", "draft", "waiting_on_a_read"] as const) {
      const slots = moveInActionSlots(status, ["approve", "ask_for_more", "edit", "decline"]);
      expect(slots.primary).not.toBeNull();
    }
    expect(moveInActionSlots("completed").primary).toBeNull();
  });

  it("Decline, Cancel and Discard are the danger tier inside More ▾ (B14 rule 6)", async () => {
    mount(requestRecord("to_approve", ["approve", "ask_for_more", "edit", "decline"]));
    await head();
    expect(screen.getByTestId("move-more-decline").className).toContain("danger");
    expect(screen.getByTestId("move-more-edit").className).not.toContain("danger");
  });

  it("S1 superseded — a COMPLETED move-in has no Open the account / Open the customer doors", async () => {
    mount(jobRecord("completed"));
    await head();
    expect(screen.queryByTestId("move-record-open-account")).toBeNull();
    expect(screen.queryByTestId("move-record-open-customer")).toBeNull();
    expect(screen.queryByText(/Open the account/)).toBeNull();
  });

  it("the head carries the name, the reference, the status chip and the address", async () => {
    mount(requestRecord("to_approve", ["approve", "ask_for_more", "edit", "decline"]));
    await head();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Verma, Asha");
    expect(document.querySelector("[data-move-reference]")).toHaveTextContent("SR-26-0014");
    expect(document.querySelector("[data-move-status]")).toHaveTextContent("To approve");
    expect(document.querySelector("[data-move-where]")).toHaveTextContent("301 Mill Pond Ln · Unit 4A");
    expect(screen.getByRole("link", { name: /Move-ins/ })).toHaveAttribute("href", `/${TENANT}/accounts?tab=move-ins`);
  });
});

describe("CR-171 P2.06 · the request modals send what §9.REQ names", () => {
  it("Approve posts outcome move_in and shows one EFFECT line", async () => {
    const { post } = mount(requestRecord("to_approve", ["approve", "ask_for_more", "edit", "decline"]));
    await head();
    await userEvent.click(screen.getByTestId("move-action-approve"));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("EFFECT")).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: /Approve/ }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toBe("/service-requests/req-14/approve");
    expect(post.mock.calls[0][1]).toMatchObject({ outcome: "move_in" });
  });

  it("Decline is refused empty, then sends reason, code `other` and the same letter (J2)", async () => {
    const { post } = mount(requestRecord("to_approve", ["approve", "ask_for_more", "edit", "decline"]));
    await head();
    await userEvent.click(document.querySelector("[data-move-more] summary") as HTMLElement);
    await userEvent.click(screen.getByTestId("move-more-decline"));
    const dialog = await screen.findByRole("dialog");
    const commit = within(dialog).getByRole("button", { name: /^Decline$/ });
    expect(commit.getAttribute("data-variant") ?? commit.className).toContain("danger");
    await userEvent.click(commit);
    expect(post).not.toHaveBeenCalled();
    await userEvent.type(within(dialog).getByRole("textbox"), "Lease not signed");
    await userEvent.click(commit);
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toBe("/service-requests/req-14/refuse");
    expect(post.mock.calls[0][1]).toEqual({
      reason: "Lease not signed",
      reason_code: "other",
      message_to_applicant: "Lease not signed",
    });
  });

  it("Ask for more is a modal and posts request_info with the letter", async () => {
    const { post } = mount(requestRecord("to_approve", ["approve", "ask_for_more", "edit", "decline"]));
    await head();
    await userEvent.click(screen.getByTestId("move-action-askForMore"));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading")).toHaveTextContent("Ask Verma, Asha for more");
    await userEvent.type(within(dialog).getByRole("textbox"), "A signed lease");
    await userEvent.click(within(dialog).getByRole("button", { name: /^Send$/ }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toBe("/service-requests/req-14/transitions");
    expect(post.mock.calls[0][1]).toMatchObject({
      action: "request_info",
      reason: "A signed lease",
      message_to_applicant: "A signed lease",
    });
  });

  it("Resend the ask posts the new door with no body of the clerk's", async () => {
    const { post } = mount(requestRecord("waiting_on_customer", ["approve", "resend_ask", "edit", "decline"]));
    await head();
    await userEvent.click(screen.getByTestId("move-action-resendAsk"));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toBe("/service-requests/req-14/resend-ask");
  });
});

describe("CR-171 P2.13 · the move-in's own doors", () => {
  it("Cancel is HELD while the preview refuses, in the preview's own words", async () => {
    // Nothing about WHY is hard-coded here: the screen draws whatever refusal
    // the preview serves. A held deposit no longer refuses (ruling 4,
    // OQ-CUS-12790 (a), 2.541.0) — a bill already issued still does.
    const { post } = mount(jobRecord("waiting_on_a_read"), {
      get: (url) =>
        url.endsWith("/cancel-preview")
          ? {
              kind: "committed",
              move_no: "MVI-26-0011",
              allowed: false,
              refusal: { code: "move_in_cancel_bill_issued", message_key: "customers.moveIn.cancel.billIssued" },
              reverses: {
                account: { account_no: "AC-2026-00058", closes_on: "2026-10-09" },
                refund: { amount: "175.0000", currency: "USD" },
                work_orders: ["WO-0062"],
                reads_kept: 1,
                unit_after: "vacant",
              },
            }
          : undefined,
    });
    await head();
    await userEvent.click(document.querySelector("[data-move-more] summary") as HTMLElement);
    await userEvent.click(screen.getByTestId("move-more-cancel"));
    const dialog = await screen.findByRole("dialog");
    const sentence = i18n.t("customers.moveIn.cancel.billIssued");
    await waitFor(() => expect(within(dialog).getByText(sentence)).toBeInTheDocument());
    expect(within(dialog).getByRole("button", { name: /Cancel move-in/ })).toBeDisabled();
    expect(post).not.toHaveBeenCalled();
  });

  it("the held-deposit refusal is retired — the server can no longer send it (2.541.0)", () => {
    expect(i18n.exists("customers.moveIn.cancel.depositHeld")).toBe(false);
  });

  it("Cancel is LIVE and lists the refund once the preview allows it (OQ-CUS-12790 (a))", async () => {
    const { post } = mount(jobRecord("waiting_on_a_read"), {
      get: (url) =>
        url.endsWith("/cancel-preview")
          ? {
              kind: "committed",
              move_no: "MVI-26-0011",
              allowed: true,
              refusal: null,
              reverses: {
                account: { account_no: "AC-2026-00058", closes_on: "2026-10-09" },
                refund: { amount: "175.0000", currency: "USD" },
                work_orders: [],
                reads_kept: 1,
                unit_after: "vacant",
              },
            }
          : undefined,
    });
    await head();
    await userEvent.click(document.querySelector("[data-move-more] summary") as HTMLElement);
    await userEvent.click(screen.getByTestId("move-more-cancel"));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(within(dialog).getByText(/\$175\.00/)).toBeInTheDocument());
    const commit = within(dialog).getByRole("button", { name: /Cancel move-in/ });
    expect(commit).not.toBeDisabled();
    await userEvent.click(commit);
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toBe("/moves/MVI-26-0011/cancel");
  });

  it("the cancel preview's lines are J6's, read from the server and never derived", () => {
    const t = (key: string, o?: Record<string, unknown>) => `${key}${o ? JSON.stringify(o) : ""}`;
    const lines = cancelLines(
      {
        kind: "committed",
        move_no: "MVI-26-0011",
        allowed: true,
        refusal: null,
        reverses: {
          account: { account_no: "AC-2026-00058", closes_on: "2026-10-09" },
          refund: { amount: "0.0000", currency: "USD" },
          work_orders: ["WO-0062"],
          reads_kept: 1,
          unit_after: "vacant",
        },
      },
      t,
    );
    expect(lines).toEqual([
      'customers.moveDetail.cancel.account{"account":"AC-2026-00058"}',
      'customers.moveDetail.cancel.workOrders{"orders":"WO-0062"}',
      "customers.moveDetail.cancel.unit",
    ]);
  });

  it("DEF-CUS-9789 — each uncleared payment the press calls off is its own line, and no refund line", () => {
    const t = (key: string, o?: Record<string, unknown>) => `${key}${o ? JSON.stringify(o) : ""}`;
    const lines = cancelLines(
      {
        kind: "committed",
        move_no: "MVI-26-0007",
        allowed: true,
        refusal: null,
        reverses: {
          account: { account_no: "AC-2026-00057", closes_on: "2026-10-09" },
          refund: { amount: "0.0000", currency: "USD" },
          called_off: [
            { payment_no: "PMT-2610-000041", amount: "150.0000", currency: "USD" },
            { payment_no: "PMT-2610-000042", amount: "25.0000", currency: "USD" },
          ],
          work_orders: [],
          reads_kept: 1,
          unit_after: "vacant",
        },
      },
      t,
    );
    expect(lines.filter((line) => line.includes("calledOff"))).toHaveLength(2);
    expect(lines[1]).toContain("PMT-2610-000041");
    expect(lines[1]).toContain("$150.00");
    expect(lines.some((line) => line.includes("cancel.refund"))).toBe(false);
  });

  it("Enter opening read posts the METER number of each unread register", async () => {
    const { post } = mount(jobRecord("waiting_on_a_read"));
    await head();
    await userEvent.click(screen.getByTestId("move-action-enterOpeningRead"));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("SM-7041"), "214");
    await userEvent.click(within(dialog).getByRole("button", { name: /Save reads/ }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][0]).toBe("/moves/MVI-26-0011/opening-reads");
    // DEF-CUS-10167 — the row carries the date its box showed: the move-in date.
    expect(post.mock.calls[0][1]).toEqual({ reads: [{ meter_no: "SM-7041", value: "214", read_at: "2026-10-10" }] });
  });

  // ── DEF-CUS-10167 — Enter opening read takes a READ DATE and Fetch ────────
  // WHAT WOULD MAKE THESE PASS WRONGLY: a date box that is drawn and never
  // posted (the body is asserted); a refused date that still posts (NO post
  // is asserted); a last reading read from the wrong unit (the stub answers
  // only for unit-308, the record's own).
  const UNIT_METERS = {
    unit_id: "unit-308",
    services: [
      {
        service: "water",
        metered: true,
        meters: [
          {
            asset_no: "SM-7041",
            kind: "sub_meter",
            type_name: "Sub-meter",
            location_note: null,
            size_class: null,
            unit: "kgal",
            last_read: { value: "210.000000", unit: "kgal", read_at: "2026-10-05" },
            needs_opening_read: true,
            children: [],
          },
        ],
      },
    ],
    unplaced: [],
  };
  const unitMeters = (url: string) => (url === "/units/unit-308/move-in-meters" ? UNIT_METERS : undefined);

  it("DEF-CUS-10167 — the read date opens on the move-in date; a chosen earlier one posts", async () => {
    const { post } = mount(jobRecord("waiting_on_a_read"), { get: unitMeters });
    await head();
    await userEvent.click(screen.getByTestId("move-action-enterOpeningRead"));
    const dialog = await screen.findByRole("dialog");
    const date = within(dialog).getByLabelText(/^Read date for SM-7041/);
    expect(date).toHaveValue("10/10/2026");
    await waitFor(() => expect(within(dialog).getByText("Last 210 kgal · 10/05/2026")).toBeInTheDocument());
    await userEvent.type(within(dialog).getByLabelText("SM-7041"), "214");
    await userEvent.clear(date);
    await userEvent.type(date, "10/08/2026");
    await userEvent.click(within(dialog).getByRole("button", { name: /Save reads/ }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1]).toEqual({ reads: [{ meter_no: "SM-7041", value: "214", read_at: "2026-10-08" }] });
  });

  it("DEF-CUS-10167 — a date before the meter's last reading, or after today, does not post", async () => {
    const { post } = mount(jobRecord("waiting_on_a_read"), { get: unitMeters });
    await head();
    await userEvent.click(screen.getByTestId("move-action-enterOpeningRead"));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(within(dialog).getByText("Last 210 kgal · 10/05/2026")).toBeInTheDocument());
    await userEvent.type(within(dialog).getByLabelText("SM-7041"), "214");
    const date = within(dialog).getByLabelText(/^Read date for SM-7041/);
    await userEvent.clear(date);
    await userEvent.type(date, "10/01/2026");
    await userEvent.click(within(dialog).getByRole("button", { name: /Save reads/ }));
    expect(await within(dialog).findByText("Earlier than the last reading.")).toBeInTheDocument();
    await userEvent.clear(date);
    await userEvent.type(date, "12/31/2099");
    await userEvent.click(within(dialog).getByRole("button", { name: /Save reads/ }));
    expect(await within(dialog).findByText("Read date is after today.")).toBeInTheDocument();
    expect(post.mock.calls.filter(([path]) => String(path).endsWith("/opening-reads"))).toHaveLength(0);
  });

  it("DEF-CUS-10167 — Fetch fills the reading with the meter's own date", async () => {
    const post = vi.fn(async (path: string) =>
      path === "/integrations/meter-reading/fetch"
        ? {
            status: 200,
            data: {
              result: "fetched",
              reading: { meter_no: "SM-7041", value: "216", unit: "kgal", read_on: "2026-10-09" },
              message_key: null,
            },
          }
        : { status: 200, data: {} },
    );
    mount(jobRecord("waiting_on_a_read"), { get: unitMeters, post });
    await head();
    await userEvent.click(screen.getByTestId("move-action-enterOpeningRead"));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(within(dialog).getByText("Last 210 kgal · 10/05/2026")).toBeInTheDocument());
    await userEvent.click(within(dialog).getByRole("button", { name: "Fetch reading for SM-7041" }));
    await waitFor(() => expect(within(dialog).getByLabelText("SM-7041")).toHaveValue("216"));
    expect(within(dialog).getByLabelText(/^Read date for SM-7041/)).toHaveValue("10/09/2026");
    await userEvent.click(within(dialog).getByRole("button", { name: /Save reads/ }));
    await waitFor(() => expect(post.mock.calls.some(([path]) => String(path).endsWith("/opening-reads"))).toBe(true));
    const saved = post.mock.calls.find(([path]) => String(path).endsWith("/opening-reads")) as unknown[];
    expect(saved[1]).toEqual({ reads: [{ meter_no: "SM-7041", value: "216", read_at: "2026-10-09" }] });
  });

  it("DEF-CUS-9726 — Enter opening read offers exactly the meters the record names unread", async () => {
    // The server's ONE definition (first read on/after the move-in date) now
    // serves the chip and the rows, so the screen follows the rows alone: a
    // meter the record calls read is never offered, even under the chip.
    mount(
      jobRecord("waiting_on_a_read", {
        opening_reads: {
          rows: [
            { register: "E-5041 · total", reading: "3817.000000", unit: "kWh", read_at: "2026-10-03", how: "read" },
            { register: "W-5041 · total", reading: "2531.000000", unit: "kgal", read_at: "2026-10-03", how: "read" },
          ],
          unavailable: null,
        },
      }),
    );
    await head();
    await userEvent.click(screen.getByTestId("move-action-enterOpeningRead"));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByLabelText("E-5041")).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText("W-5041")).not.toBeInTheDocument();
  });

  it("Start and Edit open the four-step form by the request; a draft's Edit resumes its park", () => {
    const job = jobRecord("not_started") as never;
    expect(moveInStartPath(job)).toBe("/move-ins/new?request=req-14");
    expect(moveInEditPath(job)).toBe("/move-ins/new?request=req-14&edit=1");
    expect(moveInEditPath(jobRecord("draft") as never)).toContain("parked=park-1");
  });
});

describe("CR-171 P2.38 · the request page's door opens THIS screen", () => {
  it("`/moves/SR-…` is the address and S19.moveRecord the screen", () => {
    expect(moveRecordPath("SR-26-0014")).toBe("/moves/SR-26-0014");
    expect(MOVE_RECORD_ROUTE).toBe("/moves/:ref");
    expect(MOVE_RECORD_SCREEN).toBe("S19.moveRecord");
  });

  it("an SR- reference mounted at that address renders the move-in details view", async () => {
    mount(requestRecord("to_approve", ["approve", "ask_for_more", "edit", "decline"]));
    const root = await head();
    expect(root).toHaveAttribute("data-status", "to_approve");
  });
});

describe("DEF-AUD-9727 · a move-in's audit rows are described, never 'Activity recorded'", () => {
  it.each([
    "move_in.fees_recorded",
    "move_in.payment_taken",
    "move_in.opening_reads_entered",
    "move_in_job.cancelled",
  ])("%s resolves to a known sentence", (action) => {
    const t = ((key: string, o?: { defaultValue?: string }) => o?.defaultValue ?? key) as never;
    expect(auditEventSentence(action, t).known).toBe(true);
  });
});

describe("DEF-CUS-9763 · a unit is named by its number and label (images 03–17)", () => {
  it("the request's Unit cell reads SCW-U-311 · Unit 4A, the number linked, and the tile says the number", async () => {
    const record = requestRecord("to_approve", ["approve", "ask_for_more", "edit", "decline"]);
    record.tiles.unit = { ...record.tiles.unit, unit_no: "SCW-U-311" } as never;
    record.facts.request.unit = { ...record.facts.request.unit, unit_no: "SCW-U-311" } as never;
    mount(record);
    await head();
    const cell = await waitFor(() => {
      const found = document.querySelector("[data-fact='unit'] dd");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(cell).toHaveTextContent("SCW-U-311 · Unit 4A");
    expect(within(cell).getByRole("link", { name: "SCW-U-311" })).toBeInTheDocument();
    // Image 03's Unit tile caption is the NUMBER.
    expect(document.querySelector("[data-kpi-tiles]")).toHaveTextContent("VacantSCW-U-311");
  });

  it("the completed move-in's Unit cell reads the same way", async () => {
    const record = jobRecord("completed");
    (record.facts.details.unit as Record<string, unknown>).unit_no = "SCW-U-308";
    mount(record);
    await head();
    const cell = await waitFor(() => {
      const found = document.querySelector("[data-fact='unit'] dd");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(cell).toHaveTextContent("SCW-U-308 · Unit 3B");
    expect(within(cell).getByRole("link", { name: "SCW-U-308" })).toBeInTheDocument();
  });
});
