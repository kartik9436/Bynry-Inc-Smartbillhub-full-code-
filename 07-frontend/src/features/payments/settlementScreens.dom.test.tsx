// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-139-BRC07` `P5.7` — screens **5·1 Settlements** and **5·2
//           Settlement**, from §03 tab 5 of
//           `05-prototype/06 Payments Page Blueprint.pdf` (p069–p072), read as
//           IMAGES at 2.0 (B14 rule 42).
// Rules:    B14 rule 12–17 (the table's controls) · 19 · 31 · 33 · 37 · 41 ·
//           43 · BR-SHL-011 · BR-TEN-043
// Defect:   DEF-PAY-6286 (the read `GET /settlements` no task row owned)
// ───────────────────────────────────────────────────────
// What a person can SEE and PRESS on the two Settlements screens.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ EVERY MOUNT IS UNDER THE REAL PATH PATTERN, AND ONE CASE CHECKS THAT THE
// PATTERN IS THE ROUTER'S OWN
// ══════════════════════════════════════════════════════════════════════════
// `DEF-CWP-3925`: a page mounted bare in a `MemoryRouter` with no `/:tenant/…`
// route leaves `useParams().tenant` undefined, so every address it builds comes
// out `//payments/…` — a protocol-relative URL to ANOTHER HOST, which reads as
// a perfectly good string to `toContain`. Six dead doors passed 391 cases that
// way.
//
// ⚠ **AND A FIXTURE THAT DECLARES ITS OWN ROUTE IS TESTING ITS OWN FIXTURE.**
// The same defect's other half was a hold-expiry test asserting a screen was
// REGISTERED at one address while the router mounted it at another, with every
// check passing over both. So the first case below walks `APP_ROUTES` — the
// array `App.tsx` actually hands to the router — and asserts the pattern is
// there. The fixtures then use that same pattern.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { RouteObject } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { APP_ROUTES } from "@/App";
import type { ApiClient } from "@/api/client";
import type {
  SettlementDetail,
  SettlementMembersResponse,
  SettlementsResponse,
} from "@/api/settlementEndpoints";
import { ToastProvider } from "@/components/Toast";
import { todayInZone } from "@/components/DateCell";

import { SettlementPage } from "./SettlementPage";
import { SettlementsTab } from "./SettlementsTab";
import {
  BankMark,
  SETTLEMENTS_ROUTE,
  settlementRoute,
  settlementStatusTone,
} from "./settlementsShared";

const TENANT = "brazosbend";
const ZONE = "America/Chicago";
const t = (key: string) => i18n.t(key);

/**
 * ⚠ **A NEUTRAL PROCESSOR NAME, ON PURPOSE.** The drawing prints `Stripe` and
 * `Worldpay` in its rows, and `BR-INT-037` / `G77` keep a vendor name out of
 * `apps/payments`. A fixture is not that module, but a test that hard-codes a
 * real processor is the string somebody later greps for and copies. The column
 * renders whatever the row carries, which is the property worth asserting.
 */
const PROVIDER = "sandbox_pay";
const CODE = "STL-260921-CARD";

/** p070's row shape. ⚠ **THE FIGURES ARE THIS FIXTURE'S, NOT THE DRAWING'S** —
 *  B14 rule 37: `$8,204.11` and the rest are illustrations, so nothing here is
 *  built to reach them and nothing asserts them. */
const LIST: SettlementsResponse = {
  rows: [
    {
      code: CODE,
      provider: PROVIDER,
      paid_out_at: "2026-09-21T02:14:00Z",
      payments: 46,
      gross: "8204.1100",
      fees: "156.8100",
      net: "8047.3000",
      currency: "USD",
      status: "matched",
      bank_reference: "BRM-2609-0044",
    },
    {
      code: "STL-260920-CARD",
      provider: PROVIDER,
      paid_out_at: "2026-09-20T02:09:00Z",
      payments: 39,
      gross: "6910.4400",
      fees: "131.2900",
      net: "6779.1500",
      currency: "USD",
      status: "received",
      bank_reference: null,
    },
  ],
  count: 2,
  totals: {
    currency: "USD",
    providers: [PROVIDER],
    paid_out_today: "8047.3000",
    paid_out_today_providers: 1,
    fees_this_month: "288.1000",
    fees_share_of_takings: "1.9",
    totals_unavailable: null,
    awaiting_settlement: "1204.8000",
    awaiting_settlement_payments: 31,
    unmatched: 1,
  },
};

/** The same list with the two DAY-SHAPED tiles absent, which is what the server
 *  answers when the caller named no business day (`BR-TEN-043`). */
const LIST_WITHOUT_A_DAY: SettlementsResponse = {
  ...LIST,
  totals: {
    ...LIST.totals,
    paid_out_today: null,
    paid_out_today_providers: null,
    fees_this_month: null,
    fees_share_of_takings: null,
    totals_unavailable: "as_of_missing",
  },
};

const DETAIL: SettlementDetail = {
  code: CODE,
  provider: PROVIDER,
  paid_out_at: "2026-09-21T02:14:00Z",
  payments: 46,
  gross: "8204.1100",
  fees: "156.8100",
  net: "8047.3000",
  currency: "USD",
  status: "matched",
  bank_reference: "BRM-2609-0044",
  fee_share: "1.91",
};

const MEMBERS: SettlementMembersResponse = {
  rows: [
    {
      payment_no: "PMT-2609-000412",
      taken_at: "2026-09-20T14:22:00Z",
      account_no: "AC-2026-00031",
      customer_name: "Grace Espinoza",
      reference: "auth 4471",
      gross: "802.4300",
      fee: "15.3400",
      currency: "USD",
    },
    {
      // ⚠ **THE TWO STATED ABSENCES, IN ONE ROW.** `payment_no` is nullable so
      // an import that cannot reach the series fails loudly instead of
      // colliding, and `customer_name` is null when customers holds no contact.
      // Both render WORDS — never the payment's key (B14 rule 31) and never a
      // blank cell that reads as a missing figure.
      payment_no: null,
      taken_at: "2026-09-20T13:58:00Z",
      account_no: "AC-2026-00012",
      customer_name: null,
      reference: null,
      gross: "118.6000",
      fee: "2.7100",
      currency: "USD",
    },
  ],
  count: 2,
};

/** A client whose reads are never called — the cache is seeded instead, because
 *  `renderToStaticMarkup` does not await a promise. */
const CLIENT = {} as ApiClient;

function collectPaths(routes: readonly RouteObject[], parent = ""): string[] {
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
      out.push(...collectPaths(route.children, here));
    }
  }
  return out;
}

function renderList(body: SettlementsResponse): string {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // ⚠ **THE CACHE IS SEEDED, AND WITHOUT THIS EVERY ASSERTION READS A LOADING
  // SKELETON AND PASSES NOTHING.** `renderToStaticMarkup` does not await, so an
  // unseeded `useQuery` is `undefined` on the only render there is. The key is
  // built exactly as the screen builds it — the table params plus the tenant's
  // own day — so a change to either is a change to both.
  const params = new URLSearchParams();
  params.set("sort", "paid_out_at");
  params.set("dir", "desc");
  // ⚠ **THE TENANT'S OWN DAY, FROM THE SAME FUNCTION THE SCREEN CALLS.** The
  // tab sends `as_of` because `BR-TEN-043` forbids the SERVER reading a clock,
  // so the key carries a day that moves. A literal here would match only on
  // one date and the tiles would silently render their skeleton for ever
  // after — which is what the first draft of this file did, and four cases
  // failed loudly, which is the good outcome.
  params.set("as_of", todayInZone(ZONE));
  client.setQueryData(["payments", "settlements", params.toString()], body);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ToastProvider>
        {/* THE REAL PATH PATTERN — see this file's header. */}
        <MemoryRouter initialEntries={[`/${TENANT}${SETTLEMENTS_ROUTE}`]}>
          <Routes>
            <Route
              path="/:tenant/payments/:tab"
              element={
                <SettlementsTab
                  client={CLIENT}
                  timeZone={ZONE}
                  dateFormat="MM/DD/YYYY"
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function renderDetail(detail: SettlementDetail, members: SettlementMembersResponse): string {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const params = new URLSearchParams();
  params.set("sort", "taken");
  params.set("dir", "desc");
  client.setQueryData(["payments", "settlement", detail.code], detail);
  client.setQueryData(
    ["payments", "settlement", detail.code, "members", params.toString()],
    members,
  );
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${settlementRoute(detail.code)}`]}>
          <Routes>
            <Route
              path="/:tenant/payments/settlements/:settlementRef"
              element={
                <SettlementPage
                  client={CLIENT}
                  timeZone={ZONE}
                  dateFormat="MM/DD/YYYY"
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE DOOR, ASSERTED AGAINST THE ROUTER RATHER THAN AGAINST A FIXTURE
// ══════════════════════════════════════════════════════════════════════════
describe("P5.7 · 5·2 is mounted where 5·1's row points", () => {
  it("App.tsx declares the pattern the row builds", () => {
    // ⚠ **THIS IS THE ONE CASE A SELF-DECLARED FIXTURE CANNOT WRITE.** Every
    // other case below mounts a route it declares itself, which proves the
    // component renders and proves nothing about the router. This walks
    // `APP_ROUTES` — the array `App.tsx` hands to `createBrowserRouter` — so a
    // screen registered at one address while the row points at another goes
    // RED here and nowhere else (`DEF-CWP-3925`).
    expect(collectPaths(APP_ROUTES)).toContain("/:tenant/payments/settlements/:settlementRef");
  });

  it("the route constant and the row's address are one string", () => {
    expect(SETTLEMENTS_ROUTE).toBe("/payments/settlements");
    expect(settlementRoute(CODE)).toBe(`${SETTLEMENTS_ROUTE}/${CODE}`);
  });

  it("a reference with a space or a slash is still one segment", () => {
    // A provider's own reference is THEIR string, not ours — `settlement_models`
    // says so — so it may carry anything. An unencoded `/` would turn one
    // payout's address into two segments and resolve to nothing.
    expect(settlementRoute("STL 26/09")).toBe("/payments/settlements/STL%2026%2F09");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 5·1 — THE LIST
// ══════════════════════════════════════════════════════════════════════════
describe("P5.7 · 5·1 Settlements draws what p070 draws", () => {
  it("draws the eight columns and the drawn search prompt", () => {
    const html = renderList(LIST);
    expect(html).toContain(t("payments.settlement.list.search"));
    for (const column of [
      "payments.settlement.list.col.settlement",
      "payments.settlement.list.col.provider",
      "payments.settlement.list.col.paidOut",
      "payments.settlement.list.col.payments",
      "payments.settlement.list.col.gross",
      "payments.settlement.list.col.fees",
      "payments.settlement.list.col.net",
      "payments.settlement.list.col.bank",
    ]) {
      expect(html, `${column} is not drawn`).toContain(t(column));
    }
  });

  it("names the payout by the PROVIDER'S reference and carries no uuid", () => {
    const html = renderList(LIST);
    expect(html).toContain(CODE);
    // B14 rule 31 in its strongest form: the payload has no `id` member at all,
    // so there is nothing for a cell to leak. Asserted as a property of the
    // wire rather than of this render.
    expect(Object.keys(LIST.rows[0]!)).not.toContain("id");
  });

  it("the row's eye opens 5·2 BY ADDRESS, with the tenant in it", () => {
    // ⚠ `//payments/settlements/STL-…` — what a fixture with no `/:tenant/…`
    // route produces — is a protocol-relative URL to another host and would
    // satisfy a naive `toContain(settlementRoute(CODE))`. That is exactly how
    // `DEF-CWP-3925` hid on the customer portal, so the tenant segment is part
    // of the assertion.
    const html = renderList(LIST);
    expect(html).toContain(`href="/${TENANT}${settlementRoute(CODE)}"`);
  });

  it("draws the four tiles p069 draws", () => {
    const html = renderList(LIST);
    for (const tile of [
      "payments.settlement.kpi.paidOutToday",
      "payments.settlement.kpi.awaiting",
      "payments.settlement.kpi.fees",
      "payments.settlement.kpi.unmatched",
    ]) {
      expect(html, `${tile} is not drawn`).toContain(t(tile));
    }
    // The AWAITING tile's own detail — 31 payments, from the server.
    expect(html).toContain(i18n.t("payments.settlement.kpi.awaitingDetail", { count: 31 }));
  });

  it("⚠ a day-shaped tile with no day states the ABSENCE and never a zero", () => {
    // `DEF-127`'s shape, which reached a live Counter tab this month: `?? "0"`
    // turns *"we cannot answer"* into *"nothing was paid out today"*, which is a
    // different and far more alarming statement. `BR-TEN-043` is why the server
    // can answer null at all.
    const html = renderList(LIST_WITHOUT_A_DAY);
    expect(html).toContain(t("payments.settlement.kpi.noDay"));
    expect(html).not.toContain("$0.00");
    // The two tiles that are NOT day-shaped still answer, which is the half of
    // this that an over-eager fix would break.
    expect(html).toContain(i18n.t("payments.settlement.kpi.awaitingDetail", { count: 31 }));
  });

  it("⚠ draws NO primary action — p070's own word is “None — this is a read”", () => {
    // B14 rule 41: the drawing IS the scope, and p072 spends a whole step on
    // this absence. A test that only asserted what IS drawn would pass over a
    // lane adding an Ingest or Match button here.
    const html = renderList(LIST);
    // ⚠ **`>Verb<`, NOT `>Verb` — THE FIRST DRAFT OF THIS CASE FAILED ON ITS
    // OWN STATUS PILL.** `>Match` is a prefix of `>Matched<`, which is the BANK
    // column's own word, so the loose form reported a Match button over a
    // screen that has none. Found by running it; it is hard-won law 7's
    // *looking at the wrong thing* in miniature, and worth the line because a
    // false RED here is indistinguishable from the defect this case is for.
    for (const verb of ["Ingest", "Match", "Approve", "Cancel", "Edit"]) {
      expect(html, `5·1 grew a ${verb} control`).not.toContain(`>${verb}<`);
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 5·2 — ONE PAYOUT
// ══════════════════════════════════════════════════════════════════════════
describe("P5.7 · 5·2 Settlement draws what p071 draws", () => {
  it("the page-head title is the payout's reference, not a uuid", () => {
    const html = renderDetail(DETAIL, MEMBERS);
    expect(html).toContain(CODE);
    expect(Object.keys(DETAIL)).not.toContain("id");
  });

  it("draws the four tiles and their sub-lines", () => {
    const html = renderDetail(DETAIL, MEMBERS);
    for (const tile of [
      "payments.settlement.detail.tile.gross",
      "payments.settlement.detail.tile.fees",
      "payments.settlement.detail.tile.net",
      "payments.settlement.detail.tile.bank",
    ]) {
      expect(html, `${tile} is not drawn`).toContain(t(tile));
    }
    expect(html).toContain(t("payments.settlement.detail.tile.grossDetail"));
    expect(html).toContain(t("payments.settlement.detail.tile.netDetail"));
    // ⚠ **THE PERCENTAGE IS THE SERVER'S AND IS PRINTED, NEVER COMPUTED.**
    // Dividing two decimal strings in the browser is a float division on a
    // money path (hard rule 2).
    expect(html).toContain("1.91%");
  });

  it("the member table draws p071's seven columns and its prompt", () => {
    const html = renderDetail(DETAIL, MEMBERS);
    expect(html).toContain(t("payments.settlement.members.search"));
    for (const column of [
      "payments.settlement.members.col.payment",
      "payments.settlement.members.col.taken",
      "payments.settlement.members.col.account",
      "payments.settlement.members.col.customer",
      "payments.settlement.members.col.reference",
      "payments.settlement.members.col.gross",
      "payments.settlement.members.col.fee",
    ]) {
      expect(html, `${column} is not drawn`).toContain(t(column));
    }
  });

  it("⚠ GROSS and FEE are two columns, because a fee is not a smaller payment", () => {
    // `CR-139-BRC07` §2.3, the money-correctness heart of the phase: a $100.00
    // card payment with a $2.90 fee is a $100.00 payment and a $2.90 expense.
    // The member row's own gross is the PAYMENT'S amount, and a screen that
    // showed `gross - fee` in one column would be the netted version wearing a
    // different hat.
    const html = renderDetail(DETAIL, MEMBERS);
    expect(html).toContain("$802.43");
    expect(html).toContain("$15.34");
    expect(html).not.toContain("$787.09");
  });

  it("a member with no payment number and no customer says so in WORDS", () => {
    const html = renderDetail(DETAIL, MEMBERS);
    expect(html).toContain(t("payments.settlement.members.noNumber"));
    expect(html).toContain(t("payments.settlement.members.noName"));
  });

  it("the header's ← exits to the Settlements TAB", () => {
    // B14 rule 1: the page header's `←` names where it EXITS to, and p071's
    // *Doors* row reads *"A row on 5·1. 1 door."*
    const html = renderDetail(DETAIL, MEMBERS);
    expect(html).toContain(`href="/${TENANT}${SETTLEMENTS_ROUTE}"`);
  });

  it("⚠ draws NO action at all — p072's step 3 is the specification", () => {
    const html = renderDetail(DETAIL, MEMBERS);
    for (const verb of ["Approve", "Cancel", "Edit", "Reverse", "Match"]) {
      expect(html, `5·2 grew a ${verb} control`).not.toContain(`>${verb}<`);
    }
    // ⚠ **AND THE HEAD'S ACTION ROW IS EMPTY, WHICH IS THE STRUCTURAL FORM OF
    // THE SAME CLAIM.** `PageHeader` always renders that row so the title does
    // not shift between tabs, so an empty one is visible in the markup — and a
    // verb list cannot be the only check, because a control this lane never
    // thought of would pass the loop above.
    expect(html).toContain('<div class="page-header-actions"></div>');
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE ONE FACT BOTH SCREENS DRAW — B14 RULE 43'S OWN TEST
// ══════════════════════════════════════════════════════════════════════════
describe("P5.7 · the bank mark is one component, so the two screens cannot drift", () => {
  it("a matched payout is the success tone and carries its credit", () => {
    expect(settlementStatusTone("matched")).toBe("success");
    const html = renderToStaticMarkup(
      <BankMark status="matched" reference="BRM-2609-0044" t={(key) => i18n.t(key)} />,
    );
    expect(html).toContain(t("payments.settlement.state.matched"));
    expect(html).toContain("BRM-2609-0044");
  });

  it("an unmatched payout warns, and prints no credit it does not have", () => {
    expect(settlementStatusTone("received")).toBe("warning");
    const html = renderToStaticMarkup(
      <BankMark status="received" reference={null} t={(key) => i18n.t(key)} />,
    );
    expect(html).toContain(t("payments.settlement.state.unmatched"));
    expect(html).not.toContain("BRM-");
  });

  it("a matched payout whose bank line has no reference still says matched", () => {
    // `bank_lines.reference` is nullable and B14 rule 31 forbids falling back
    // to the line's key, so the pill stands alone rather than printing an id
    // nobody could quote. The CHECK constraint guarantees the LINE exists.
    const html = renderToStaticMarkup(
      <BankMark status="matched" reference={null} t={(key) => i18n.t(key)} />,
    );
    expect(html).toContain(t("payments.settlement.state.matched"));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-139-BRC07 §4 row `P5.7` · blueprint p069–p072 as images at 2.0 · DEF-PAY-6286
// generated: 2026-09-23 by LANE P5-SCREENS
// checklist: A=n/a B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest src/features/payments/settlementScreens.dom.test.tsx · tsc --noEmit
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
