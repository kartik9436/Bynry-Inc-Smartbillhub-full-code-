// ── Trace ──────────────────────────────────────────────
// Change:   `P0.7` of `05-prototype/06 Payments Page Blueprint.pdf` — *"isoToday()
//           reads the tenant timezone"*. PO ruling 2026-09-22, verbatim:
//           *"Going forward only"*.
// Rules:    BR-PAY-033 (the posting date is pre-filled and overridable) ·
//           BR-SHL-023 (tenant TZ + regional format, ONE formatting path) ·
//           BR-TEN-043 (a business day is named by the caller, never read from
//           a server clock) · B14 rule 43 (a piece of UI is the kit's, not a
//           second copy) · CLAUDE.md hard rule 4 (`posted_at` is frozen, so
//           this fix is forward-only by law as well as by ruling)
// Screens:  S32 Summary · S34 Debtors · S35 Record payment
// ───────────────────────────────────────────────────────
//
// **THE WORKED CASE, AND IT IS THE BLUEPRINT'S OWN:** a clerk finishes a 17:30
// shift in UTC−7. It is already tomorrow in UTC. The screen used to propose
// `new Date().toISOString().slice(0, 10)` — the UTC day — so every payment that
// clerk recorded in the last six and a half hours of their shift was stamped
// into the NEXT business day: a late-fee test (`posted_at ≤ due_date`) run
// against the wrong day, and a deposit batch on the wrong drawer.
//
// ⚠ **WHY THIS TEST IS WRITTEN WITH TWO ZONES AND NOT ONE.** A single
// assertion — *"the field reads 2026-09-22"* — passes for the wrong reason on
// any machine whose own clock happens to agree, and passes forever if someone
// reinstates a UTC slice while CI runs in UTC. So the case pins ONE frozen
// instant and renders it TWICE, in two zones that are on different calendar
// days at that instant, and asserts the two screens disagree. A UTC slice
// cannot produce two answers; nothing that reads the browser's own zone can
// either. That is the false pass this case is built to make impossible.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { ToastProvider } from "@/components/Toast";
import { todayInZone } from "@/components/DateCell";
import { PaymentsPage } from "./PaymentsPage";

const TENANT = "brazosbend";

/** 17:30 on 22 September in UTC−7 — and 00:30 on the 23rd in UTC.
 *  The whole defect lives in the gap between those two sentences. */
const END_OF_SHIFT = new Date("2026-09-23T00:30:00Z");

const WEST = "America/Los_Angeles"; // UTC−7 in September
const EAST = "Australia/Sydney"; // UTC+10 — already the 23rd, and then some

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN**, not bare inside a `MemoryRouter`.
 * `DEF-CWP-3925` hid for days behind a fixture with no `/:tenant/...` route:
 * `useParams().tenant` came back undefined, every address the page built came
 * out `//portal/…`, and `toContain` read that as a perfectly good string.
 */
function renderAt(timeZone: string): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/payments`]}>
          <Routes>
            <Route
              path="/:tenant/payments"
              element={<PaymentsPage timeZone={timeZone} dateFormat="YYYY-MM-DD" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The `value` the summary's as-of date field rendered. */
function asOfValue(html: string): string | null {
  const field = html.slice(html.indexOf('id="summary_as_of"'));
  const match = /value="([^"]*)"/.exec(field.slice(0, 400));
  return match === null ? null : match[1];
}

describe("P0.7 — the day this screen proposes is the TENANT's day", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(END_OF_SHIFT);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("the kit's todayInZone answers per zone, and the two zones disagree at this instant", () => {
    // The precondition the case rests on, asserted rather than assumed: if
    // these two were ever equal the assertions below would pass vacuously.
    expect(todayInZone(WEST)).toBe("2026-09-22");
    expect(todayInZone(EAST)).toBe("2026-09-23");
    expect(todayInZone(WEST)).not.toBe(todayInZone(EAST));
    // And the UTC day — what the deleted `isoToday()` returned — is the 23rd,
    // so a tenant in UTC−7 was being offered tomorrow.
    expect(new Date().toISOString().slice(0, 10)).toBe("2026-09-23");
  });

  it("a utility in UTC−7 is offered 22 September while UTC has already rolled over", () => {
    expect(asOfValue(renderAt(WEST))).toBe("2026-09-22");
  });

  // ⚠ **THIS CASE ALONE PROVES NOTHING AND IS KEPT ANYWAY.** At this instant
  // `Australia/Sydney` and UTC agree, so a UTC slice passes it — it went GREEN
  // against the pre-fix code in the red proof, exactly as it should have. It is
  // here as the OTHER half of the pair: what it rules out is a fix that returns
  // a constant, or one that always answers the west.
  it("the SAME instant in UTC+10 is offered 23 September — one clock, two answers", () => {
    expect(asOfValue(renderAt(EAST))).toBe("2026-09-23");
  });

  it("no second answer to 'what day is it here' is exported by this module", async () => {
    // B14 rule 43 and the `DEF-MET-4991` lesson: `todayInZone` already existed
    // in the kit when `isoToday` was written, and two helpers answering one
    // question is how two screens come to disagree about a business day. This
    // fails the moment somebody re-adds a local one under either name.
    //
    // ⚠ **THIS CASE WAS FIRST WRITTEN AS A REGEX OVER THE FILE'S SOURCE AND
    // THAT WAS THE WRONG INSTRUMENT** — it matched the UTC expression inside
    // the COMMENT that explains why the expression is gone, so it went red over
    // a file that was already correct. A text scan cannot tell code from prose
    // about code; the module's exported shape can.
    const page = await import("./PaymentsPage");
    const actions = await import("@/features/customers/AccountActions");
    expect(Object.keys(page)).not.toContain("isoToday");
    expect(Object.keys(actions)).not.toContain("isoToday");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// generated: 2026-09-22 by the payments blueprint phase-0 front-end lane (P0.7)
// gates: RED PROVED FIRST — against `PaymentsPage.tsx` at 1a67fa46c, where
//        `isoToday()` returned the UTC day, cases 2 and 3 both rendered
//        `2026-09-23` and case 2 failed with
//        `expected '2026-09-23' to be '2026-09-22'`; case 4 failed on the
//        `export function isoToday` match. tsc✔ · vitest✔
// exceptions: (1) this file asserts the PROPOSED day only. The WRITE half —
//        `apps/payments/api._moment` anchoring a bare `YYYY-MM-DD` at midnight
//        UTC — is `DEF-094` and is backend, another lane's file; it is
//        REPORTED here and not fixed · (2) `billingOpsShared.todayIso()` is the
//        same UTC slice in the billing module and is deliberately untouched
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
