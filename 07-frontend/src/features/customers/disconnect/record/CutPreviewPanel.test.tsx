// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  `DEF-CUS-6051` — p143's `Status becomes` row read `Disconnected`
//          unconditionally, including on a case ALREADY CUT whose status was
//          deliberately held. Reproduced in a browser on 2026-09-20:
//          `DSC-26-0002` is `cut`, the panel said `Disconnected`, and its
//          account `A-11721` read **Active**, behaviour class `billable`.
// Rules:   BR-CUS-107 (`Disconnected` is written only when the days up to the
//          cut are billed — CR-052 W0, PO ruling 2026-08-30) · B14 rule 33 (a
//          FACT is ≤ 6 words; RATIONALE is ZERO words on screen) ·
//          CLAUDE.md hard-won law 2's mirror (a live claim whose condition
//          nobody re-checks).
// ───────────────────────────────────────────────────────
/**
 * What this file holds the panel to.
 *
 * **1 · THE STATUS ROW STAYING A CONSTANT.** It is the whole defect. The row
 * now reads `what_a_cut_would_do.account_status_becomes.code` and says a
 * different thing for each answer; a lane putting a literal back goes red here.
 *
 * **2 · AN UNKNOWN CODE FALLING THROUGH TO THE PROMISE.** The dangerous default
 * is `written`, because it is the one that keeps the screen claiming something
 * it cannot know. `unstated` is the only safe side of that fence.
 *
 * **3 · THE SERVER'S `detail` REACHING A CLERK.** Every one of these blocks
 * carries an engineer's paragraph. `BR-SHL-020` r2 and `DEF-742`: the SCREEN
 * authors the sentence, keyed off the code.
 *
 * ⚠ **RED PROVED FIRST**, through `vitest` in the jsdom environment these run
 * in — the harness that will run them. With the row put back to
 * `t("…cut.statusValue")` the held and unknown cases fail by name.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CutPreviewPanel, cutStatusAnswer } from "./CutPreviewPanel";
import type { DisconnectRecordDetail } from "./disconnectRecordEndpoints";

afterEach(cleanup);

/** IS-8 — a date renders in the TENANT's zone AND format, never ISO. The panel
 *  draws one since PO ruling 2026-09-21 (`days_not_billed`), so the fixture
 *  supplies what every other record panel on this screen is already given. */
const ZONE = "America/Chicago";
const FORMAT = "MM/DD/YYYY" as const;

/**
 * `disconnects.CUT_BILL_BLOCKED_SO_STATUS_HELD`, as the server writes it —
 * `detail` included, because a test whose fixture has no engineer's prose in it
 * cannot prove the screen keeps engineer's prose off the page.
 */
const HELD = {
  code: "cut_bill_blocked_status_not_written",
  br_ref: "BR-CUS-107 · BR-CUS-103 · BR-BIL-015 · PO ruling 2026-08-30",
  detail:
    "billing could not raise the final bill for the days before this cut, so the " +
    "`Disconnected` status was NOT written and the account stays in the bill run.",
};

const WRITTEN = {
  code: "disconnected_status_assigned_at_the_cut",
  br_ref: "BR-CUS-107 · BR-CUS-103 · BR-CUS-110 · PO ruling 2026-08-30",
  detail: "the cut writes BR-CUS-107's `Disconnected` status on the account.",
};

function record(becomes: unknown = WRITTEN): DisconnectRecordDetail {
  return {
    what_a_cut_would_do: {
      services_affected: { value: ["electric", "water"], unavailable: null },
      reconnection_fee: {
        charge_code_configured: true,
        stored: "75.0000",
        display: "75.00",
        currency: "USD",
        unavailable: null,
      },
      account_status_becomes: becomes,
      to_clear_before_reconnection: {
        stored: "8315.0000",
        display: "8315.00",
        currency: "USD",
        unavailable: null,
      },
      base_charges: { code: "cut_stops_base_at_the_cut", detail: "base charges stop" },
      not_a_close_out: { code: "a_cut_is_not_a_close_out", detail: "the account stays open" },
    },
  } as unknown as DisconnectRecordDetail;
}

function statusCell(): HTMLElement {
  const cell = screen
    .getByTestId("disconnect-record-cut")
    .querySelector("[data-cut-status]");
  expect(cell, "the status row carries no answer at all").not.toBeNull();
  return cell as HTMLElement;
}

describe("DEF-CUS-6051 — `Status becomes` is the server's answer, never a constant", () => {
  it("says `Disconnected` WITH ITS CONDITION when the server says it writes it", () => {
    render(<CutPreviewPanel record={record()} timeZone={ZONE} dateFormat={FORMAT} />);
    const cell = statusCell();
    expect(cell).toHaveAttribute("data-cut-status", "written");
    // ⚠ **THE CONDITION IS THE FIX.** `Disconnected` alone is what the row said
    // while no cut could complete anywhere, and it is a promise rather than a
    // fact. Six words — B14 rule 33's cap for a FACT.
    expect(cell).toHaveTextContent("Disconnected once the final bill lands");
    expect(cell.textContent?.trim().split(/\s+/)).toHaveLength(6);
  });

  it("says the status was NOT changed when the server says it was held", () => {
    render(<CutPreviewPanel record={record(HELD)} timeZone={ZONE} dateFormat={FORMAT} />);
    const cell = statusCell();
    expect(cell).toHaveAttribute("data-cut-status", "held");
    expect(cell).toHaveTextContent("Not changed by this cut");
    // The word that was wrong on both real cuts must be gone from this row.
    expect(cell).not.toHaveTextContent("Disconnected");
  });

  it("an UNKNOWN code states nothing — it never falls through to the promise", () => {
    render(<CutPreviewPanel record={record({ code: "zz_a_new_ruling", detail: "?" })} timeZone={ZONE} dateFormat={FORMAT} />);
    const cell = statusCell();
    expect(cell).toHaveAttribute("data-cut-status", "unstated");
    expect(cell).toHaveTextContent("Not stated");
    expect(cell).not.toHaveTextContent("Disconnected");
  });

  it("a MISSING block states nothing rather than assuming the happy answer", () => {
    // ⚠ **`null`, NOT `undefined`.** The first draft passed `undefined`, which
    // is exactly what a default parameter swallows — the fixture silently
    // became the WRITTEN one and the case asserted the happy path while
    // claiming to assert the absent one. A fixture that cannot tell a present
    // block from a missing one is the shape hard-won law 2 warns about, and it
    // was found by running the case rather than by reading it.
    render(<CutPreviewPanel record={record(null)} timeZone={ZONE} dateFormat={FORMAT} />);
    expect(statusCell()).toHaveAttribute("data-cut-status", "unstated");
    expect(statusCell()).toHaveTextContent("Not stated");
  });

  it("the server's `detail` never reaches the panel — the SCREEN owns the words", () => {
    // `BR-SHL-020` r2 · `DEF-742`. B14 rule 33 gives RATIONALE zero words on
    // screen, and every one of these blocks is rationale by construction.
    for (const block of [WRITTEN, HELD]) {
      cleanup();
      render(<CutPreviewPanel record={record(block)} timeZone={ZONE} dateFormat={FORMAT} />);
      const panel = screen.getByTestId("disconnect-record-cut");
      expect(panel).not.toHaveTextContent("accounts_for_bill_run");
      expect(panel).not.toHaveTextContent("BR-CUS-107");
      expect(panel).not.toHaveTextContent("PO ruling");
      expect(panel).not.toHaveTextContent(block.code);
    }
  });

  it("the other four rows are untouched — only the row the server answers moved", () => {
    render(<CutPreviewPanel record={record(HELD)} timeZone={ZONE} dateFormat={FORMAT} />);
    const panel = screen.getByTestId("disconnect-record-cut");
    expect(panel).toHaveTextContent("Electric · Water");
    expect(panel).toHaveTextContent("$75.00");
    expect(panel).toHaveTextContent("$8,315.00");
    expect(panel).toHaveTextContent("Stop at the cut");
  });
});

describe("cutStatusAnswer — the one decision, shared with the dialog", () => {
  it("names the two codes the product has and refuses to guess at anything else", () => {
    expect(cutStatusAnswer("disconnected_status_assigned_at_the_cut")).toBe("written");
    expect(cutStatusAnswer("cut_bill_blocked_status_not_written")).toBe("held");
    for (const unknown of [null, undefined, "", "written", "disconnected", "zz_new"]) {
      expect(cutStatusAnswer(unknown), `"${String(unknown)}" was read as an answer`).toBe(
        "unstated",
      );
    }
  });
});
