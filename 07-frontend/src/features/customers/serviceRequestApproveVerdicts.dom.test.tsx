// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   PO ratification 2026-09-20, *"this is correct"* — **THE APPROVE
//           DIALOG'S OUTCOMES ARE GATED BY THE EVIDENCE** (decision log,
//           `SEVEN PO RATIFICATIONS FROM ONE SITTING`, §2). The verdicts have
//           existed in `service_request._verdict_for` since the module was
//           written and the dialog was not reading them, so all five options
//           were offered flat on every request.
// Rules:    BR-SHL-025 (a control this state cannot honour is DISABLED WITH
//           ITS REASON, never hidden) · B14 rule 33 (a LABEL is ≤ 3 words;
//           RATIONALE is zero words on screen) · rule 31 (no database id on
//           screen) · rule 21 (Tailwind utilities) · rule 35
// Questions: **OQ-356 is OPEN and is asserted PRESENT, never resolved** —
//           `disconnect` returns `possible` and is rendered exactly so.
// ───────────────────────────────────────────────────────
//
// WHY THIS FILE EXISTS RATHER THAN THREE MORE CASES IN THE STATIC SUITE
// ---------------------------------------------------------------------
// `disabled` is a PROPERTY, not a string. `renderToStaticMarkup` can be asked
// whether the markup contains `disabled=""`, which is the check that cannot
// tell a disabled `new_connection` from a disabled `move_out` in the same
// dialog — hard-won law 7's *a check whose output cannot distinguish pass from
// fail*. A real DOM can be asked of ONE radio whether IT is disabled and which
// sentence is tied to it, so that is what this asks.
//
// ⚠ **MOUNTED UNDER THE REAL `/:tenant/…` PATH PATTERN.** A bare
// `MemoryRouter` with no such route leaves `useParams()` empty and every
// address a component builds comes out `//…`, which reads as a perfectly good
// string to `toContain`. That is how `DEF-CWP-3925` hid, and it is why the
// route below is spelled out even though this dialog builds no address.
import "@testing-library/jest-dom/vitest";
// `screen` went when the Approve modal lost `A move-out`, `A transfer` and
// `A disconnect` (PO report 2026-09-22, row 8): the case that queried for them
// by name went with them, and this file now reads the rendered markup directly.
import { cleanup, fireEvent, render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { internalReferencesIn } from "@/testSupport/internalReferences";

import { ApproveChecksModal } from "./ApproveChecksModal";
import { APPROVE_OUTCOMES } from "./serviceRequestEndpoints";
import type { OutcomeVerdict, ServiceRequestDetail } from "./serviceRequestEndpoints";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** `service_request.outcome_verdicts(evidence)`, one evidence state at a time.
 *
 *  These are the SERVER's three verdicts and its five `_REASON_KEY` sentences,
 *  transcribed from `_verdict_for` rather than invented here — the screen owns
 *  no rule and neither does its test. */
const EVIDENCE: Record<string, OutcomeVerdict[]> = {
  // A premise record already exists at the address, and the applicant holds
  // nothing — anywhere. Three of the five are refused at once.
  premiseExistsAndApplicantHoldsNothing: [
    // ⛔ **`new_connection` IS `possible` HERE SINCE `DEF-CUS-6109`
    // (2026-09-21), AND THIS FIXTURE SAID `not_possible` WITH ITS
    // `premiseExists` SENTENCE.** The server withdrew that refusal because
    // **Accounts blueprint p089 draws the opposite on this exact evidence**:
    // `SR-26-0001` matched `PR-0731 · exact` and the approve modal draws
    // `A new connection` LIVE, over the callout *"Nothing is preselected,
    // deliberately. The resolver matched this address to PR-0731 exactly, and
    // that is EVIDENCE — not the decision."* An existing property with no
    // service is an ordinary new connection.
    //
    // ⚠ **A FIXTURE TRANSCRIBED FROM A RULE GOES STALE WHEN THE RULE MOVES,
    // AND NOTHING GOES RED** — this file's own header says these are
    // *"transcribed from `_verdict_for` rather than invented here"*, which is
    // exactly why the transcription has to be re-read when the source changes.
    { outcome: "new_connection", verdict: "possible", message_key: null },
    { outcome: "move_in", verdict: "possible", message_key: null },
    {
      outcome: "move_out",
      verdict: "not_possible",
      message_key: "customers.serviceRequest.verdict.moveOut.noAccountHere",
    },
    {
      outcome: "transfer",
      verdict: "not_possible",
      message_key: "customers.serviceRequest.verdict.transfer.noLiveAccount",
    },
    { outcome: "disconnect", verdict: "possible", message_key: null },
  ],
  // The resolver found NO premise record: a new connection is what the
  // evidence fits. The applicant still holds nothing, so two stay refused.
  noPremiseRecord: [
    {
      outcome: "new_connection",
      verdict: "fits_the_evidence",
      message_key: "customers.serviceRequest.verdict.newConnection.noPremiseRecord",
    },
    { outcome: "move_in", verdict: "possible", message_key: null },
    {
      outcome: "move_out",
      verdict: "not_possible",
      message_key: "customers.serviceRequest.verdict.moveOut.noAccountHere",
    },
    {
      outcome: "transfer",
      verdict: "not_possible",
      message_key: "customers.serviceRequest.verdict.transfer.noLiveAccount",
    },
    { outcome: "disconnect", verdict: "possible", message_key: null },
  ],
  // The unit is served and vacant and the applicant holds a live account at
  // this address: a move-in fits, and NOTHING is refused.
  servedVacantAndHoldsAnAccountHere: [
    { outcome: "new_connection", verdict: "possible", message_key: null },
    {
      outcome: "move_in",
      verdict: "fits_the_evidence",
      message_key: "customers.serviceRequest.verdict.moveIn.servedAndVacant",
    },
    { outcome: "move_out", verdict: "possible", message_key: null },
    { outcome: "transfer", verdict: "possible", message_key: null },
    { outcome: "disconnect", verdict: "possible", message_key: null },
  ],
  // An older server that serves no verdicts at all. Nothing is gated — a
  // control is never greyed on a guess.
  serverSendsNoVerdicts: [],
};

/** Only what `ApproveChecksModal` reads before a kind is picked.
 *
 *  ⚠ **REWRITTEN 2026-09-23 (`DEF-CUS-6350`) FOR THE KIT WINDOW.** The
 *  dialog these cases were written against drew hand-rolled radio CARDS with
 *  the verdict sentence under each; the window the PO approved that day draws
 *  the two kinds as the kit's `SegmentedControl` (B14 rules 36/38) with a
 *  refused kind DISABLED WITH ITS REASON as visible text (the segment's own
 *  `disabledReason`), and a suggestion as one line beside it. **Every
 *  behaviour the old cases guarded is still asserted**; only the selectors
 *  moved. The figures below are this fixture's own — B14 rule 37. */
function detailWith(options: OutcomeVerdict[]): ServiceRequestDetail {
  const money = (amount: string, display: string) => ({ amount, display, currency: "USD" });
  return {
    header: { request_no: "SR-26-0071", applicant: "Okonkwo, Adaeze" },
    actions: { approve_blocked_by: [] },
    fees: {
      quoted: money("130.0000", "130.00"),
      collected: money("25.0000", "25.00"),
      outstanding: money("105.0000", "105.00"),
    },
    decision: { options, what_approving_will_do: {}, commit: { outcome: null } },
  } as unknown as ServiceRequestDetail;
}

function openApprove(options: OutcomeVerdict[]): void {
  render(
    <MemoryRouter initialEntries={["/brazosbend/requests/sr-71"]}>
      <Routes>
        <Route
          path="/:tenant/requests/:requestId"
          element={
            <ApproveChecksModal
              detail={detailWith(options)}
              t={t}
              onClose={() => undefined}
              onSubmit={() => Promise.resolve({ ok: true } as const)}
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

function segment(outcome: string): HTMLButtonElement {
  const el = document.querySelector(`[data-segment="${outcome}"]`);
  expect(el).not.toBeNull();
  return el as HTMLButtonElement;
}

describe("PO 2026-09-20 §2 · each kind carries ITS OWN verdict", () => {
  afterEach(cleanup);

  it("a premise already exists and the applicant holds nothing — both kinds stay live, and the three removed outcomes are simply absent", () => {
    openApprove(EVIDENCE.premiseExistsAndApplicantHoldsNothing);
    // ⛔ `DEF-CUS-6109` — the kind is not greyed on this evidence. Since
    // 2026-09-23 the PLACE is a check ROW (*Address · In Premises · use a
    // move-in*), not a greyed control: a greyed kind would hide the checks the
    // clerk needs to read.
    expect(segment("new_connection")).not.toBeDisabled();
    expect(segment("move_in")).not.toBeDisabled();
    // PO 2026-09-22 — not greyed, not hidden behind a condition: ABSENT.
    for (const gone of ["move_out", "transfer", "disconnect"]) {
      expect(document.querySelector(`[data-segment="${gone}"]`)).toBeNull();
    }
    expect(document.querySelectorAll("[data-segment]")).toHaveLength(2);
  });

  it("no premise record — the new connection is SUGGESTED, and it is still choosable", () => {
    openApprove(EVIDENCE.noPremiseRecord);
    expect(document.querySelector('[data-verdict-badge="new_connection"]')?.textContent).toBe(
      t("customers.serviceRequest.approveChecks.suggested", {
        kind: t("customers.serviceRequest.approveChecks.kindOption.new_connection"),
      }),
    );
    expect(segment("new_connection")).not.toBeDisabled();
    // A suggestion is not a decision: *"Nothing is preselected."*
    expect(segment("new_connection")).toHaveAttribute("aria-checked", "false");
    expect(document.querySelectorAll("[data-verdict-badge]")).toHaveLength(1);
    // …and picking it still works (hard-won law 2's mirror).
    fireEvent.click(segment("new_connection"));
    expect(segment("new_connection")).toHaveAttribute("aria-checked", "true");
  });

  it("the unit is served and vacant — the MOVE-IN is suggested and nothing is refused", () => {
    openApprove(EVIDENCE.servedVacantAndHoldsAnAccountHere);
    expect(document.querySelector('[data-verdict-badge="move_in"]')?.textContent).toBe(
      t("customers.serviceRequest.approveChecks.suggested", {
        kind: t("customers.serviceRequest.approveChecks.kindOption.move_in"),
      }),
    );
    for (const outcome of APPROVE_OUTCOMES) {
      expect(segment(outcome)).not.toBeDisabled();
    }
  });

  it("a refused kind is DISABLED WITH ITS REASON, in words — BR-SHL-025", () => {
    openApprove([
      {
        outcome: "move_in",
        verdict: "not_possible",
        message_key: "customers.serviceRequest.verdict.moveOut.noAccountHere",
      },
      { outcome: "new_connection", verdict: "possible", message_key: null },
    ]);
    expect(segment("move_in")).toBeDisabled();
    expect(document.querySelector('[data-segment-reason="move_in"]')?.textContent).toBe(
      t("customers.serviceRequest.verdict.moveOut.noAccountHere"),
    );
    expect(segment("new_connection")).not.toBeDisabled();
  });

  it("a verdict for a removed outcome is IGNORED, never drawn — OQ-356 is still OPEN", () => {
    for (const state of [
      EVIDENCE.premiseExistsAndApplicantHoldsNothing,
      EVIDENCE.noPremiseRecord,
      EVIDENCE.servedVacantAndHoldsAnAccountHere,
    ]) {
      openApprove(state);
      expect(document.querySelector('[data-segment="disconnect"]')).toBeNull();
      expect(document.querySelector('[data-verdict-badge="disconnect"]')).toBeNull();
      cleanup();
    }
  });

  it("a server that sends no verdicts gates NOTHING — never a guess", () => {
    openApprove(EVIDENCE.serverSendsNoVerdicts);
    for (const outcome of APPROVE_OUTCOMES) {
      expect(segment(outcome)).not.toBeDisabled();
    }
    expect(document.querySelectorAll("[data-verdict-badge]")).toHaveLength(0);
  });

  it("the words are short and no code reaches the clerk — B14 rules 31 and 33", () => {
    expect(
      t("customers.serviceRequest.approveChecks.kindOption.new_connection").split(/\s+/).length,
    ).toBeLessThanOrEqual(3);
    openApprove(EVIDENCE.premiseExistsAndApplicantHoldsNothing);
    const text = document.body.textContent ?? "";
    for (const leak of ["not_possible", "fits_the_evidence", "message_key", "new_connection"]) {
      expect(text).not.toContain(leak);
    }
    expect(internalReferencesIn(document.body)).toEqual([]);
  });
});
