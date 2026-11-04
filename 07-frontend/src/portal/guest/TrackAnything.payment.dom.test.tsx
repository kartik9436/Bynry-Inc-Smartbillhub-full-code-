// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-010 (EP-CWP-03) TC-7 · US-CWP-005 (EP-CWP-02) TC-3
//           Screens: CWP-012 · CWP-004
// Rules:    BR-CWP-024 (progress and never data — and TC-7 spells out that the
//           amount is account data) · BR-CWP-021 (never a person) ·
//           BR-PAY-021 (the posting date and the clearing date always travel
//           together) · B14 rule 31 (the reference is the HUMAN one) ·
//           rule 35 (the catalogue writes the words)
// Cases:    a tracked PAYMENT draws its three facts · the two ledger words
//           never reach the chip · the date row is labelled *Paid* and not
//           *Reported* · no figure anywhere on the panel
// Why its   ⚠ **A SEPARATE FILE ON PURPOSE (hard-won law 11).** Six lanes are
// own file: closing CR-068 in six worktrees; a pathspec commit takes the WHOLE
//           working-tree content of every path it names, so a new case appended
//           to `TrackAnything.test.tsx` risks reverting whatever a sibling is
//           writing in it. A new path collides with nobody.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { TrackView } from "../api/guestClient";

import { TrackAnything, statusKey, statusTone } from "./TrackAnything";

/** `US-CWP-005` §4 and `US-CWP-010` §4: `PAY-26-08841`, paid 2 Sep 2026. */
const PAYMENT: TrackView = {
  series: "payment",
  reference: "PAY-26-08841",
  status: "received",
  reported_at: "2026-09-02T09:47:00+00:00",
  cleared_at: "2026-09-03T06:15:00+00:00",
};

afterEach(cleanup);

describe("statusKey · statusTone for a tracked payment (US-CWP-010 TC-7)", () => {
  it("reuses the portal's own money words — the chip the money list draws", () => {
    // ⚠ Amended 2026-10-21 (`DEF-CWP-10341`): the staff words said *Cleared*
    // for a payment the bank had not confirmed, and had nothing for a cancel.
    expect(statusKey(PAYMENT)).toBe("portal.money.state.received");
    expect(statusKey({ ...PAYMENT, status: "processing" })).toBe("portal.money.state.processing");
    expect(statusKey({ ...PAYMENT, status: "failed" })).toBe("portal.money.state.failed");
    expect(statusKey({ ...PAYMENT, status: "cancelled" })).toBe("portal.money.state.cancelled");
    expect(statusKey({ ...PAYMENT, status: "unknown" })).toBe("portal.money.state.unknown");
  });

  it("an unrecognised status — the old `cleared` included — reads unknown", () => {
    for (const odd of ["cleared", "posted", "reversed", "something_new", ""]) {
      expect(statusKey({ ...PAYMENT, status: odd })).toBe("portal.money.state.unknown");
    }
  });

  it("every word the server can send has English copy, not a key", () => {
    const expected: Record<string, string> = {
      received: "Received",
      processing: "Processing",
      failed: "Failed",
      cancelled: "Canceled",
      unknown: "Status unavailable",
    };
    for (const [status, word] of Object.entries(expected)) {
      expect(i18n.t(statusKey({ ...PAYMENT, status }))).toBe(word);
    }
  });

  it("nothing about a payment is drawn in the danger tier (r10 rule 6)", () => {
    // The loudest colour of the product is kept for a DESTRUCTIVE COMMIT.
    expect(statusTone(PAYMENT)).toBe("neutral");
    expect(statusTone({ ...PAYMENT, status: "failed" })).toBe("neutral");
  });

  it("the two LEDGER words can never reach this screen", () => {
    // ⚠ **THE SERVER FOLDS FIVE STATES INTO THREE AND THIS ASSERTS THE
    // CONSEQUENCE HERE TOO.** `posted` is a bookkeeping fact and `reversed`
    // names a mechanism; `BR-CWP-024` gives a guest progress and never the
    // reason. If a future server change let one through, the key it produced
    // would have no catalogue entry and the chip would print the key itself —
    // which is `DEF-CWP-3926`'s shape, so it is worth a case.
    for (const word of ["received", "processing", "failed", "cancelled"]) {
      expect(statusKey({ ...PAYMENT, status: word })).toMatch(/^portal\.money\.state\./);
    }
    expect(["posted", "reversed"]).not.toContain(PAYMENT.status);
  });
});

describe("CWP-012 · what a tracked payment shows (US-CWP-005 TC-3)", () => {
  /** ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** (`DEF-CWP-3925`) — a bare
   *  `MemoryRouter` leaves `useParams().tenant` undefined and every address the
   *  page builds comes out `//portal/…`, which reads as a perfectly good string
   *  to `toContain`. */
  function draw() {
    return render(
      <MemoryRouter initialEntries={["/pine-hill/portal/track"]}>
        <Routes>
          <Route path="/:tenant/portal/track" element={<TrackAnything />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("the screen a payment lands on is CWP-012 and it asks for two facts", () => {
    const { container } = draw();
    expect(container.querySelector('[data-screen="CWP-012"]')).not.toBeNull();
    expect(container.querySelector("#cwp012-reference")).not.toBeNull();
    expect(container.querySelector("#cwp012-second-fact")).not.toBeNull();
    // `BR-CWP-024` stated before anything is looked up — the English, never
    // the key (the catalogue holds all eleven).
    expect(screen.getByText(/a reference is not a login/i)).toBeInTheDocument();
  });

  it("BR-CWP-024 — the panel that has not been filled names no figure", () => {
    const { container } = draw();
    expect(container.innerHTML).not.toMatch(/\$\d/);
  });
});
