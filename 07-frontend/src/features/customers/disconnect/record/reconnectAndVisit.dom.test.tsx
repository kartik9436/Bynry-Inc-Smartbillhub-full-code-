// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   **PO ruling 2026-09-20** — *"The other half of the job. Today a
//           utility can cut supply and cannot restore it from the product."*
//           and *"The register reflects reality. Today a failed visit is
//           invisible and the case looks untouched."* (`BR-CUS-1083`,
//           `OQ-383` closed).
// Rules:    BR-PAY-036 · BR-CUS-1083 · BR-SHL-025 (a refused control renders
//           disabled WITH ITS REASON, as VISIBLE TEXT) · B14 rule 6 (the
//           danger tier is for DESTRUCTIVE commits) · rule 31 · rule 33 ·
//           hard-won law 2 **and its mirror**
// ───────────────────────────────────────────────────────
/**
 * What this file holds the way back to.
 *
 * **1 · A DOOR THAT IS NOT THERE.** `mark_reconnecting` and `restore_service`
 * were built, role-gated, tested and ROUTED on 2026-08-25 and were called by
 * NOTHING for 26 days. These cases assert the button EXISTS on the state that
 * can use it, by test id and by the address it posts to.
 *
 * **2 · A DEAD CONTROL OVER A LIVE SCREEN — law 2's mirror, which costs more.**
 * `Mark as cut` on a case cut last Tuesday can never become pressable again;
 * `cut_readiness` answers `already_cut` for ever. The case below asserts it is
 * **GONE**, not merely disabled, on a `cut` case.
 *
 * **3 · THE REFUSAL BEING A TOOLTIP.** A touch or keyboard user never sees a
 * `title`. Every refusal on this screen is visible text with `aria-describedby`
 * pointing at it.
 *
 * **4 · EITHER DIALOG POSTING SOMETHING OTHER THAN WHAT IT DREW.** The bodies
 * are asserted field by field against the real endpoints' contracts.
 *
 * **5 · THE FOUR OUTCOMES BEING TYPED OUT ON THE SCREEN.** They come from the
 * server with their destinations beside them. A fifth outcome must reach the
 * dialog on its own — the eleventh-service failure is silent, and this is where
 * it would be silent.
 *
 * ⚠ **RED PROVED FIRST for every case here**, through `vitest` in the jsdom
 * environment these run in — the harness that will run them. Each case's break
 * is named beside it.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { RecordVisitDialog } from "./RecordVisitDialog";
import type {
  DisconnectRecordDetail,
  DisconnectReconnectPanel,
  DisconnectVisitPanel,
} from "./disconnectRecordEndpoints";

afterEach(cleanup);

const ACCOUNT_ID = "01a0bf3d-13c5-7cfa-96a1-486d6b84f070";
const ABSENT = (code: string, detail: string) => ({ code, detail });

/** `A-11721 · DSC-26-0002` — the second cut this product ever completed. */
function reconnectPanel(over: Partial<DisconnectReconnectPanel> = {}): DisconnectReconnectPanel {
  return {
    step: "mark_reconnecting",
    ready: false,
    refusal: {
      code: "not_settled",
      br_ref: "`DSC-02.4` · B18 §5.8.1",
      detail: "this account still owes 1279.500000. …",
    },
    blockers: [],
    balance: { stored: "1279.5000", display: "1279.50", currency: "USD", unavailable: null },
    status_before_cut: null,
    status_absence: ABSENT("status_before_cut_not_resolvable", "nothing was recorded at the cut"),
    to_clear: {
      stored: null,
      display: null,
      currency: "USD",
      unavailable: null,
      total: { stored: "1354.5000", display: "1354.50" },
    } as DisconnectReconnectPanel["to_clear"],
    fee: { stored: "75.0000", display: "75.00" },
    fee_absence: null,
    deposit: {
      on_file: { stored: "0.0000", display: "0.00" },
      election: "held",
      new_deposit_required: false,
      detail: "the deposit is HELD",
    },
    cut_on: "2026-09-20",
    reconnected_on: null,
    visit: ABSENT("reconnection_visit_not_scheduled", "no visit booked"),
    ...over,
  };
}

function visitPanel(over: Partial<DisconnectVisitPanel> = {}): DisconnectVisitPanel {
  return {
    outcomes: [
      { code: "locked_gate", move: "clears_the_cut_date" },
      { code: "access_refused", move: "clears_the_cut_date" },
      { code: "paid_at_door", move: "clears_the_cut_date" },
      { code: "disputed", move: "stops_the_ladder" },
    ],
    can_record: true,
    refusal: null,
    recorded: [],
    follow_up: ABSENT("visit_outcome_raises_no_follow_up", "no crew is re-dispatched"),
    money: ABSENT("paid_at_door_records_no_amount", "customers writes no financial table"),
    ...over,
  };
}

function detail(over: Partial<DisconnectRecordDetail> = {}): DisconnectRecordDetail {
  return {
    case_no: { value: "DSC-26-0002", unavailable: null },
    customer_name: { value: "Halvorsen, P.", unavailable: null },
    address: { value: "88 Quarry Lane · Silver Creek, TX 78611", unavailable: null },
    customer_class: { value: "Residential", unavailable: null },
    state: { value: "cut", unavailable: null },
    tier: { value: "tier_3_48_hour", unavailable: null },
    cut_date: { value: "2026-09-20", unavailable: null },
    the_case: {
      account_no: { value: "A-11721", unavailable: null },
      owed: { stored: "1279.5000", display: "1279.50", currency: "USD", unavailable: null },
      oldest_debt: { value: null, unavailable: ABSENT("oldest_debt_age_has_no_source", "none") },
      tier: { value: "tier_3_48_hour", unavailable: null },
      cut_date: { value: "2026-09-20", unavailable: null },
      opened_on: { value: "2026-08-14", unavailable: null },
      raised_by: { value: null, unavailable: ABSENT("case_opener_not_recorded", "none") },
    },
    notices: {
      rows: [],
      state_column_unavailable: ABSENT("notice_delivery_state_is_null_by_rule", "by rule"),
      channel_column_empty: null,
      delivery: ABSENT("delivery_adapter_absent", "no adapter"),
    },
    protections: { as_of: "2026-09-20", checks: [], all_clear: true },
    what_a_cut_would_do: {
      services_affected: { value: ["electric", "water"], unavailable: null },
      reconnection_fee: {
        charge_code_configured: true,
        stored: "75.0000",
        display: "75.00",
        currency: "USD",
        unavailable: null,
      },
      account_status_becomes: ABSENT("disconnected_status_assigned_at_the_cut", "BR-CUS-107"),
      to_clear_before_reconnection: {
        stored: "1354.5000",
        display: "1354.50",
        currency: "USD",
        unavailable: null,
      },
      base_charges: ABSENT("base_charges_stop_at_the_cut", "BR-CUS-103"),
      not_a_close_out: ABSENT("a_cut_is_not_a_close_out", "the account stays open"),
    } as DisconnectRecordDetail["what_a_cut_would_do"],
    actions: {
      available: ["hold", "open_account", "mark_reconnecting"],
      account_id: ACCOUNT_ID,
      hold: {
        kinds: ["medical_certificate", "weather_moratorium", "payment_plan"],
        review_date: {
          medical_certificate: "required",
          payment_plan: "refused",
          weather_moratorium: "required",
        },
        dispute_unrecordable: ABSENT("dispute_is_not_a_protection", "nothing stores an amount"),
        effects: [],
        promises_not_kept: ABSENT("hold_clears_no_date_and_moves_no_state", "measured"),
      },
      mark_as_cut: {
        ready: false,
        refusal: { code: "already_cut", br_ref: "BR-CUS-039", detail: "already cut" },
        blockers: [],
      },
      reconnect: reconnectPanel(),
      visit: visitPanel({ can_record: false, refusal: ABSENT("visit_not_scheduled", "cut") }),
    },
    ...over,
  };
}

/** The stub client, narrowed to the two verbs so `.mock.calls` stays typed. */
function client(): ApiClient & { post: Mock; get: Mock } {
  return {
    post: vi.fn(async () => ({ status: 200, data: {} })),
    get: vi.fn(async () => ({ status: 200, data: {} })),
  } as unknown as ApiClient & { post: Mock; get: Mock };
}

describe("BR-CUS-1083 — a crew attends and does not cut", () => {
  function scheduled() {
    const base = detail();
    return detail({
      state: { value: "scheduled", unavailable: null },
      actions: {
        ...base.actions,
        available: ["hold", "open_account", "record_visit", "mark_as_cut"],
        visit: visitPanel(),
      },
    });
  }

  it("draws the four outcomes the SERVER sent, each with where it sends the case", async () => {
    // RED by typing the four into this component: a fifth outcome would then
    // exist in the database, be served by the API, pass `tsc` and every test —
    // and never appear on screen. That is the eleventh-service failure, and it
    // is silent.
    render(
      <ToastProvider>
        <RecordVisitDialog
          record={scheduled()}
          today="2026-09-20"
          dateFormat="MM/DD/YYYY"
          client={client()}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );
    expect(await screen.findByText("Locked gate")).toBeInTheDocument();
    expect(screen.getByText("Access refused")).toBeInTheDocument();
    expect(screen.getByText("Paid at the door")).toBeInTheDocument();
    expect(screen.getByText("Disputed at the door")).toBeInTheDocument();
    // ⚠ **THE MOVE IS THE HALF THE PO RULED ON**, so it is asserted beside the
    // word rather than left to the reader.
    expect(screen.getAllByText("The cut date is cleared.")).toHaveLength(3);
    expect(screen.getByText("The notice ladder stops.")).toBeInTheDocument();
  });

  it("says nobody is sent back out", async () => {
    // RED by dropping the note: a clerk records a locked gate and waits for a
    // crew this act never dispatched.
    render(
      <ToastProvider>
        <RecordVisitDialog
          record={scheduled()}
          today="2026-09-20"
          dateFormat="MM/DD/YYYY"
          client={client()}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );
    const note = await screen.findByTestId("disconnect-visit-no-follow-up");
    expect(note).toHaveTextContent("Nobody is sent back out.");
  });

  it("posts the outcome and the date, and omits an empty note", async () => {
    // RED by sending `note: ""`: the server stores an empty string as NULL, so
    // nothing breaks — and the screen has started telling the API that somebody
    // wrote nothing, which is a different fact from nobody writing a note.
    const api = client();
    render(
      <ToastProvider>
        <RecordVisitDialog
          record={scheduled()}
          today="2026-09-20"
          dateFormat="MM/DD/YYYY"
          client={api}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );
    await userEvent.click(await screen.findByRole("button", { name: "Record visit" }));
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const [url, body] = api.post.mock.calls[0];
    expect(url).toBe(`/accounts/${ACCOUNT_ID}/disconnect-case/visit`);
    expect(body).toEqual({ on_date: "2026-09-20", outcome: "locked_gate" });
  });

  it("carries the crew's own sentence when there is one", async () => {
    const api = client();
    render(
      <ToastProvider>
        <RecordVisitDialog
          record={scheduled()}
          today="2026-09-20"
          dateFormat="MM/DD/YYYY"
          client={api}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );
    await userEvent.type(
      await screen.findByLabelText(/In their words/),
      "Padlock on the meter box.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Record visit" }));
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    expect(api.post.mock.calls[0][1]).toEqual({
      on_date: "2026-09-20",
      outcome: "locked_gate",
      note: "Padlock on the meter box.",
    });
  });

  it("refuses the commit on a case no crew was sent to", async () => {
    // RED by dropping `commitBlocked`: the dialog submits on a CUT case and the
    // server refuses with `visit_not_scheduled`, which a clerk meets as an error
    // rather than as a sentence (`BR-SHL-025`).
    render(
      <ToastProvider>
        <RecordVisitDialog
          record={detail()}
          today="2026-09-20"
          dateFormat="MM/DD/YYYY"
          client={client()}
          onClose={() => undefined}
        />
      </ToastProvider>,
    );
    expect(await screen.findByText("No visit was due.")).toBeInTheDocument();
  });
});
