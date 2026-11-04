// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-135 P1.13 — "a guard on the deletion". P1.10 deleted the
//          orphaned `/finance/write-offs` route; this is the test that fails
//          if it is mounted again.
// Story:   US-PAY-012 (write-offs)   Screens: S36 area (Finance · Revenue & AR)
// Rules:   BR-PAY-020 (initiated in Payments, approved in Finance) ·
//          CLAUDE.md hard-won law 2's mirror (a live screen behind a dead
//          control) · law 7 ("ask what would make this check pass wrongly";
//          proved RED in the harness that runs it) · B14 rule 43
// ───────────────────────────────────────────────────────
/**
 * ONE WRITE-OFF QUEUE, NOT TWO — ASSERTED BY ADDRESS AND BY COMPONENT.
 *
 * ⚠ **WHY A TEST AND NOT A COMMENT.** The Payments blueprint's §05 audit says
 * it plainly: *"every test asks whether a screen renders at its own address,
 * which is the one place a door is not needed — and a test doing exactly that
 * is what kept the orphan looking alive. **Nothing asks whether two components
 * answer the same question.**"* This file is that question, written down.
 *
 * ⚠ **THREE ASSERTIONS, AND THE THIRD IS THE ONE THAT MATTERS.** The first two
 * would both pass on a product with NO write-off queue at all — deleting the
 * panel as well would make them greener, which is law 7's "what would make this
 * check pass wrongly". So the third asserts the surviving queue is really
 * there, by its own rendered heading, at the address a clerk actually reaches.
 *
 * ⚠ **AND IT IS `APP_ROUTES`, NEVER A HAND-TYPED LIST.** A second copy of the
 * route table is a second thing to keep true; this reads the router's own.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import type { RouteObject } from "react-router-dom";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { APP_ROUTES } from "@/App";
import type { WriteOffApprovalRow } from "@/api/bankRecEndpoints";
import { WriteOffQueuePanel, writeOffQueueQueryKey } from "@/features/ledger/RevenueArPage";
import { api } from "@/api/client";

/** Every address the router serves, as a FULL pattern — the same flattening
 *  `screenIds.test.tsx` performs, for the same reason: a nested route's own
 *  `path` is a segment, not an address, and a check that read the segments
 *  alone would never see `finance/write-offs` at all. */
function addresses(routes: readonly RouteObject[], parent = ""): string[] {
  const out: string[] = [];
  for (const route of routes) {
    let here = parent;
    if (typeof route.path === "string") {
      here = route.path.startsWith("/")
        ? route.path
        : `${parent === "/" ? "" : parent}/${route.path}`;
      out.push(here);
    }
    if (route.children) {
      out.push(...addresses(route.children, here));
    }
  }
  return out;
}

/** US-PAY-012 TC-1's own figure — the **948.20** request that is waiting and
 *  `posted_to_ledger` false until somebody approves it. */
// ⚠ **AN ARRAY, NOT AN ENVELOPE, SINCE `CR-138-BRC07` `P4.9` (2026-09-23).**
// The panel asked `endpoints.getWriteOffs`, which answers `{rows}`; it asks
// `bankRecEndpoints.getWriteOffApprovalQueue` now, which FOLLOWS the envelope
// and answers the rows. The reason for the swap is the drawing: screen 7·3b
// puts **ASKED BY** in its fourth column, and only the wider read carries
// `requested_by_name`. A queue that cannot say who asked is a two-person
// control with one name in it.
//
// **The fixture is a claim about the server, so it moves when the call does.**
const WAITING: WriteOffApprovalRow[] = [
  {
    id: "wo-1",
    account_id: "acc-1",
    account_no: "AC-2026-00001",
    amount: "948.2000",
    currency: "USD",
    // ⚠ **ONE OF THE FOUR THE CATALOGUE NAMES.** `uncollectable` is not a
    // reason this product has — nearest is `uncollectible_120_days`, spelled
    // differently — so it rendered as its own raw key the moment rows came
    // back, and nothing here noticed. `DEF-PAY-6270`.
    reason: "uncollectible_120_days",
    note: "",
    status: "requested",
    requested_on: "2026-09-18",
    requested_by: "u2",
    requested_by_name: "D. Whitfield",
    approved_on: null,
    approved_by: null,
    approved_by_name: null,
    posted_to_ledger: false,
    journal_entry_id: null,
  },
];

/** The SURVIVING queue, rendered with its rows already in the cache — the
 *  panel `CR-060` §8b folded into Revenue & AR. It reads no route param, but
 *  its account numbers are record links (PO 2026-10-19) that build a tenant
 *  address, so it mounts inside a tenant path. */
function renderSurvivingQueue(): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  // ⚠ **THE ENVELOPE, NOT THE BARE ARRAY, SINCE 2026-09-24 (Finance `P2.19`).**
  // `getWriteOffApprovalQueue` used to answer the rows; it answers
  // `{ rows, pending }` now, so the pending count can reach the Revenue & AR
  // view label. The cache this seeds must hold what the query function
  // returns, or the panel reads `undefined.rows` and renders an empty queue —
  // which would have passed three of the four cases in this file.
  queryClient.setQueryData(writeOffQueueQueryKey, { rows: WAITING, pending: WAITING.length });
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/acme/finance/revenue"]}>
      <QueryClientProvider client={queryClient}>
        <WriteOffQueuePanel t={i18n.t.bind(i18n)} client={api} asOf="2026-09-22" />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("CR-135 P1.10/P1.13 — the write-off queue exists once", () => {
  it("the flattener is not an empty loop", () => {
    // DEF-057's shape, and the reason it is here: every assertion below is a
    // `not.toContain` over this array, so an `addresses()` that returned `[]`
    // would report a clean pass over a product that had re-mounted the orphan.
    expect(addresses(APP_ROUTES as RouteObject[]).length).toBeGreaterThanOrEqual(50);
  });

  it("no route serves /finance/write-offs", () => {
    expect(addresses(APP_ROUTES as RouteObject[])).not.toContain("/:tenant/finance/write-offs");
  });

  it("no route anywhere mounts a standalone write-off queue", () => {
    // By ADDRESS above, and by SHAPE here: re-mounting the same page at a
    // different address is the same defect, and the address check alone would
    // pass over it.
    const mounted = addresses(APP_ROUTES as RouteObject[]).filter((path) =>
      /write-?offs?$/i.test(path),
    );
    expect(mounted).toEqual([]);
  });

  it("the queue that survived still renders its rows and its Approve control", () => {
    // The assertion that stops "delete BOTH" from reading as a pass, which is
    // what the three above would do on a product with no write-off queue at
    // all. The English literal, never `t(key)` — a test with `t()` on both
    // sides takes the same wrong value twice and a raw key satisfies it.
    expect(i18n.t("finance.writeOffs.title")).toBe("Write-offs waiting for approval");
    const html = renderSurvivingQueue();
    expect(html).toContain("Write-offs waiting for approval");
    expect(html).toContain("AC-2026-00001");
    expect(html).toContain("948.20");
    // The control is the shared table's now, so it wears the shared table's
    // label. `payments.writeOff.approve` is *"Approve it"*, the `<ul>`'s own
    // string; `payments.writeOffQueue.approve` is *"Approve"*, which is what
    // the drawing puts on the button and what every other caller already used.
    expect(html).toContain(i18n.t("payments.writeOffQueue.approve"));
    // **THE REASON REACHES THE CLERK AS WORDS, NOT AS A KEY.** i18next returns
    // the key itself when it cannot resolve one, so an unknown reason puts
    // `payments.writeOff.reason.<whatever>` on screen and every assertion
    // above still passes. This is the line that fails if that happens again —
    // B14 rule 32, no internal code in clerk-facing copy.
    expect(html).toContain(i18n.t("payments.writeOff.reason.uncollectible_120_days"));
    expect(html).not.toContain("payments.writeOff.reason.");
  });
});

// ── Lifecycle ──────────────────────────────────────────────
// packet: CR-135 phase 1 (P1.10 the deletion · P1.13 this guard), lane P1-B
// generated: 2026-09-22 by story-coder (payments phase 1 — screens that make
//   finished engines reachable)
// proof: RED FIRST, in vitest, which is the harness that runs it — the route
//   and its `screenIds.ts` row were put back, `vitest run
//   src/features/payments/writeOffOneQueue.test.tsx` failed on assertions 2
//   and 3 naming `/:tenant/finance/write-offs`, and both were removed again.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
