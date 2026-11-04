// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-003 (EP-WRK-01) — every order the field has finished that
//           nobody has accepted, in one list. Screen: Work-009
//           (`wireframes/Work-009.png`), template W1.
// Rules:    BR-WRK-007 (the queue is `accepted_by IS NULL AND state =
//           completed` — a null, not a table) · BR-WRK-006 (an order with no
//           connection is IN the list, with a dash) · BR-SHL-010 (a capability
//           absent is not a gap) · B14 rules 2 · 17 · 20 · 31 · 32 · 33
// ───────────────────────────────────────────────────────
//
// WHAT THIS FILE IS FOR, AND WHAT IT DELIBERATELY CANNOT DO.
// These cases render the screen to STATIC MARKUP, so they can ask what the
// clerk is shown and never what a colour looks like. The two questions this
// file cannot answer — does the OUTCOME pill actually paint green, and does the
// footer sentence match the drawing on a real page — are the walkthrough's
// (`10-scripts/render-checks/cr070-b-fourteen-doors-and-the-queue.mjs`), which
// reads computed style in a real engine. Neither replaces the other and the
// split is stated so the next lane does not add a `toHaveStyle` here and
// believe it proved something (hard-won law 6).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { queryKeys } from "@/api/queryClient";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";

import {
  AWAITING_APPROVAL_SCREEN,
  AwaitingApprovalPage,
  awaitingApprovalTableConfig,
  waitingLabel,
} from "./AwaitingApprovalPage";
import type { AwaitingApprovalList, AwaitingApprovalRow } from "./workEndpoints";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** The drawing's own three rows (`10-execution-plan.md` task B4). */
function row(over: Partial<AwaitingApprovalRow> = {}): AwaitingApprovalRow {
  return {
    id: "wo-4906",
    order_no: "WO-4906",
    type: "Meter set",
    premise: { id: "p-1", premise_no: "P-00117", address: "500 Main St" },
    service: "gas",
    outcome: "passed",
    completed_at: "2026-08-29T09:00:00Z",
    waiting_days: 6,
    // CR-070 wave O — the cell links to the build's HOME, not to a screen
    // of its own; the premises is the home every build has today.
    connection: { id: "con-0117", connection_no: "CON-26-0117", home: { kind: "premises", id: "p-1" } },
    ...over,
  };
}

const PARTIAL = row({
  id: "wo-4903",
  order_no: "WO-4903",
  type: "Meter set",
  service: "water",
  outcome: "partially_done",
  waiting_days: 2,
});

/** `WO-4917 · Container delivery · Trash` — the third row of the drawing. */
const CONTAINER = row({
  id: "wo-4917",
  order_no: "WO-4917",
  type: "Container delivery",
  service: "trash",
  waiting_days: 1,
});

/**
 * The leak investigation on `77 Cedar Ct` — raised on an ADDRESS, with no
 * build at all. Phase 0 exists to make this order possible, and `BR-WRK-006`
 * says it belongs in this queue like any other.
 */
const LEAK = row({
  id: "wo-4823",
  order_no: "WO-4823",
  type: "Leak investigation",
  premise: { id: "p-2", premise_no: "P-00891", address: "77 Cedar Ct" },
  service: "water",
  connection: null,
  waiting_days: 0,
});

function list(rows: AwaitingApprovalRow[], oldest: number | null = null): AwaitingApprovalList {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    oldest_waiting: oldest,
  };
}

function render(data: AwaitingApprovalList | null): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: data !== null } },
  });
  if (data !== null) {
    queryClient.setQueryData(queryKeys.workAwaitingApproval(1, DEFAULT_PAGE_SIZE), data);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/work/awaiting-approval`]}>
          <AwaitingApprovalPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-WRK-003 — Work-009, the queue that is a null", () => {
  it("TC-1 — the drawing's three rows, oldest first, with the head it draws", () => {
    const html = render(list([row(), PARTIAL, CONTAINER], 6));
    expect(html).toContain("WO-4906");
    expect(html).toContain("WO-4903");
    expect(html).toContain("WO-4917");
    // B14 rule 2 — one page header, and the ONE sentence rule 32 allows.
    expect(html).toContain(t("work.approvals.title"));
    expect(html).toContain("The field has finished these. Nobody has accepted them yet.");
    // The screen carries its id (BR-WRK-005), and it is the minted one.
    expect(AWAITING_APPROVAL_SCREEN).toBe("WRK-20");
    expect(html).toContain('data-screen="WRK-20"');
  });

  it("TC-2 — the seven columns the drawing names, in its order", () => {
    const config = awaitingApprovalTableConfig(t, {
      select: () => null,
      order: () => null,
      connection: () => null,
      premise: () => null,
      outcome: () => null,
      completed: () => null,
      open: () => null,
    });
    // CR-168 P3.7 — image 21 draws a SELECT column first.
    expect(config.columns.map((column) => column.key)).toEqual([
      "select",
      "order_no",
      "connection",
      "premise",
      "service",
      "outcome",
      "completed_at",
      "waiting_days",
      "actions",
    ]);
  });

  it("TC-3 — BR-SHL-010: no search box, because the drawing has none and the server declares no q", () => {
    const config = awaitingApprovalTableConfig(t, {
      select: () => null,
      order: () => null,
      connection: () => null,
      premise: () => null,
      outcome: () => null,
      completed: () => null,
      open: () => null,
    });
    // ⚠ ABSENT, not empty. `DataTable` renders the box on `!== undefined`, so
    // `searchFields: []` would draw a live search field over an endpoint that
    // cannot filter — the dead control G43 caught before this screen shipped.
    expect(config.searchFields).toBeUndefined();
    expect(config.searchPlaceholder).toBeUndefined();
    const html = render(list([row()], 6));
    expect(html).not.toContain('type="search"');
  });

  it("TC-4 — the footer is about the WHOLE queue, not the page in hand", () => {
    const html = render(list([row(), PARTIAL, CONTAINER], 6));
    // The drawing: *"3 orders · oldest waiting 6 days"*.
    expect(html).toContain("3 orders · oldest waiting 6 days");
    // And the second figure comes from the SERVER, so a queue whose oldest row
    // is not on this page still reads correctly.
    const paged = render(list([CONTAINER], 6));
    expect(paged).toContain("oldest waiting 6 days");
  });

  it("TC-5 — WAITING is in words, and one day is not `1 days`", () => {
    expect(waitingLabel(6, t)).toBe("6 days");
    expect(waitingLabel(1, t)).toBe("1 day");
    expect(waitingLabel(null, t)).toBe("");
    // The footer reuses that phrase rather than baking a second plural in.
    expect(render(list([CONTAINER], 1))).toContain("1 order · oldest waiting 1 day");
  });

  it("TC-6 — BR-WRK-006: an order with no build is IN the list, with a dash", () => {
    const html = render(list([LEAK], 0));
    expect(html).toContain("WO-4823");
    // CR-168 image 21 — the ORDER cell is the number alone; the job's name
    // moved into the accept dialog, where the decision is made.
    expect(html).toContain("77 Cedar Ct");
    // A DASH under CONNECTION, never a blank cell and never a link.
    expect(html).not.toContain("CON-26-");
    expect(html).toContain("—");
  });

  it("TC-7 — B14 rule 32: no column name reaches the clerk's screen", () => {
    const html = render(list([row()], 6));
    // The drawing's own note bar said `accepted_by`. It does not ship.
    expect(html).not.toContain("accepted_by");
    expect(html).toContain("nobody has accepted them");
  });

  it("B14 rule 17 — the empty state says what is missing, and its door is LIVE (CR-168 P1.7)", () => {
    const html = render(list([], null));
    expect(html).toContain(t("work.approvals.empty.title"));
    expect(html).toContain("Jobs the field closes appear here.");
    // ⚠ INVERTED, NOT DELETED (hard-won law 2's mirror). This case asserted the
    // CTA was disabled with *"The field closes these, not here."* — a hold
    // whose destination, the Orders list, shipped in CR-070 wave H. The PO's
    // P1.7 released it; the case now fails if anyone re-disables it.
    expect(html).not.toContain("The field closes these, not here.");
    const cta = html.slice(html.indexOf("state-empty"));
    expect(cta.slice(0, cta.indexOf("</button>"))).not.toContain("disabled=");
    // No footer over an empty queue: "0 orders · oldest waiting 0 days" is a
    // sentence about something that does not exist.
    expect(html).not.toContain("data-approvals-footer");
  });

  it("every key this screen asks for resolves in all eleven catalogues", () => {
    const keys = [
      "work.tabs.approvals",
      "work.approvals.kicker",
      "work.approvals.title",
      "work.approvals.sentence",
      "work.approvals.note",
      "work.approvals.col.order",
      "work.approvals.col.connection",
      "work.approvals.col.premise",
      "work.approvals.col.service",
      "work.approvals.col.outcome",
      "work.approvals.col.completed",
      "work.approvals.col.waiting",
      "work.approvals.loadFailed",
      "work.approvals.empty.title",
      "work.approvals.empty.helper",
      "work.approvals.empty.cta",
    ];
    for (const key of keys) {
      expect(i18n.exists(key), key).toBe(true);
    }
    // The two plural keys answer through their suffixes, never bare.
    expect(i18n.exists("work.approvals.waiting.days_one")).toBe(true);
    expect(i18n.exists("work.approvals.footer_other")).toBe(true);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-003@ab786097 (EP-WRK-01) · 08-screen-layouts.md Work-009 · wireframes/Work-009.png · 10-execution-plan.md wave B task B4
// generated: 2026-09-04 by the CR-070 wave B build lane
// checklist: A=n/a(the backend half is tests/test_us_wrk_003_queue.py) B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST — with the CONNECTION cell's null branch returning "" instead of <Dash/>, TC-6 fails on the missing dash; with searchFields back at [], TC-3 fails and so does G43. Both quoted in the lane report. tsc · vitest · routeBUtilities.test.ts
// exceptions: colour and the rendered footer are the walkthrough's, not this file's — stated in the header so nobody adds a toHaveStyle here and believes it
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
