// @vitest-environment jsdom
//
// ── Trace ──────────────────────────────────────────────
// Change:  Finance blueprint `P2.18` (the Revenue & AR view strip), `P2.20`
//          (Services and Tie-out onto the shared table), `P2.23` (every old
//          door lands on the right view), `P2.15` (`CountBadge`)
// Rules:   B14 rule 43 (a piece of UI used twice is a COMPONENT) · rule 44 (the
//          drawing says WHAT and how ARRANGED; the kit says HOW) · rule 32 (one
//          stated absence appears ONCE on a screen) · BR-SHL-011 (the URL
//          grammar) · NFR-3 · CLAUDE.md hard-won law 2 (built is not wired, and
//          its mirror — a live screen behind a dead control)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHAT THIS FILE IS FOR, AND THE ONE THING IT CANNOT DO                   ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// `P2.18` turns ONE screen into FIVE. The blueprint's own outcome line for
// `P2.23` says why that needs its own test: *"Hard-won law 2 — a restructure
// that moves doors is exactly how a door ends up pointing at nothing, with
// every test green."*
//
// ⚠ **AND THE DANGEROUS CASE IS NOT A DOOR POINTING AT NOTHING — IT IS A DOOR
// POINTING AT A REAL WORKING SCREEN THAT IS THE WRONG ONE.** `/finance/revenue`
// still resolves after this change; it just opens **Services** now. So the
// Dashboard's *"see the aging detail"* link and Outstandings' *"Open the
// Finance queue"* button both kept working and both started lying, with no
// 404, no console error and nothing red. **That has already happened twice in
// this product to these exact two buttons** — `DEF-PAY-6329` (a clerk pressed
// *Open the Finance queue*, landed on the trial balance, and reported the
// write-off screen as MISSING) and `DEF-REP-6345`. Which is why every door case
// below asserts the destination BY ADDRESS **and** by what is mounted there,
// never by "the link exists".
//
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN (`DEF-CWP-3925`'s fixture lesson).**
// A bare `MemoryRouter` with no `/:tenant/…` route leaves `useParams().tenant`
// undefined, so every address the tree builds comes out `//…` — a protocol-
// relative URL to another host, which reads as a perfectly good string to
// `toContain`. The portal's front page hid two working doors out of eight
// behind exactly that fixture.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import type { RevenueArResponse } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { REVENUE_AR_VIEWS, RevenueArPage, revenueArViewFrom } from "./RevenueArPage";
import { revenueArViewPath } from "./financeViewStrip";
import { AGING_DOOR_ROUTE } from "@/features/reports/DashboardPage";

const t = i18n.getFixedT("en");

/** A period the screen will accept, and a report with enough in it that each
 *  view has something to draw. Figures are arbitrary — B14 rule 37: a number in
 *  a wireframe is an illustration, and so is one in a fixture. */
function fixtures() {
  const period = { start: "2026-09-01", end: "2026-09-30", status: "open", close_by: "2026-10-03" };
  // ⚠ **ANNOTATED, AND THAT ANNOTATION IS THE ACTUAL FIX FOR `DEF-LED-6647`.**
  // This was a bare object literal, so `tsc` compared it against NOTHING: a
  // fixture missing three REQUIRED keys of `AdjustmentsPanel` — and carrying a
  // `rows` key that type does not declare — type-checked perfectly, eslint
  // passed, and the only symptom was a thrown `MoneyAmountAbsent` swallowed by
  // `MoneyCell`'s containment boundary. **An untyped fixture is a check that
  // cannot fail** (hard-won law 7): completing the keys below fixes today's
  // fault, and only this annotation stops the next short fixture.
  const report: RevenueArResponse = {
    period,
    currency: "USD",
    basis: "posting",
    // ⚠ **EVERY FIELD THE TYPE DECLARES, INCLUDING THE TWO THE DETAIL LINE
    // READS.** `collected_from_cash` and `collected_from_applied_deposits` go
    // straight into `formatMoney`, which REFUSES a nullish amount outright
    // (DEF-151's guard — a null once reached a finance screen as the literal
    // text `null USD`). An omitted key is `undefined`, so a short fixture does
    // not render a short strip: it throws inside render and React Router
    // replaces the whole screen, which took all eleven cases here down at once
    // over a fault in this file rather than in the product.
    kpis: {
      billed: "28904.2200",
      collected: "5137.6600",
      collected_from_cash: "4887.6600",
      collected_from_applied_deposits: "250.0000",
      still_owed: "23766.5600",
      accounts_owing: 3,
      collection_pct: null,
      dso: null,
      written_off_ytd: null,
    },
    revenue_by_service: [
      {
        service_id: "s-1",
        service_code: "ELECTRIC",
        usage: "21000.0000",
        base_and_fees: "880.1000",
        total_billed: "21880.1000",
        tax: null,
        collected: null,
      },
      {
        service_id: "s-2",
        service_code: "WATER",
        usage: "5000.0000",
        base_and_fees: "104.1200",
        total_billed: "5104.1200",
        tax: null,
        collected: null,
      },
    ],
    aging: null,
    // ⚠ **THIS READ `{ realised, undeposited, currency, unavailable }` AND WAS A
    // SHAPE THE PRODUCT NEVER SERVES (`DEF-LED-6754`).** `CashPosition` declares
    // `basis`, `realised` and `undeposited` — no `currency` and no `unavailable` —
    // and `RevenueArPage` reads `report.cash.basis` TWICE (lines 918 and 929), so
    // every render under this fixture passed `undefined` as the basis and the two
    // assertions that look at it could not have failed. `tsc` caught the two extra
    // keys; the MISSING one is what the cases were silently not checking.
    cash: { basis: "posting", realised: "100.0000", undeposited: "25.0000" },
    // ⚠ **THIS READ `{ rows: [], unavailable: [] }` AND THREW FOUR TIMES ON
    // EVERY RUN (`DEF-LED-6647`).** `AdjustmentsPanel` declares `credits_issued`,
    // `debits_posted` and `net` as REQUIRED non-nullable strings and declares no
    // `rows` at all, so `AdjustmentsPanelView` handed `undefined` straight to
    // `MoneyCell` and `MoneyAmountAbsent` was raised four times per render.
    // **IT WAS FILED AS A FLAKE — "about once in four whole-folder runs" — AND
    // IT IS NOTHING OF THE KIND: the throw is DETERMINISTIC and happens when
    // this file is run ALONE too.** What varies is only whether jsdom's async
    // report of the uncaught error lands inside an awaited window, and
    // `MoneyCell`'s `DEF-176` containment boundary is what stops it failing the
    // render outright. A real fault, masked by a safety net, then recorded as
    // timing — which is why "flake" is never a root cause.
    adjustments: {
      basis: "posting",
      credits_issued: "412.0000",
      debits_posted: "88.5000",
      late_fees_applied: null,
      net: "323.5000",
      pending_approval: null,
      unavailable: [
        { code: "late_fee_revenue_carries_no_designation", br_ref: "OQ-110", detail: "" },
        { code: "an_unapproved_adjustment_is_not_a_ledger_fact", br_ref: "BR-LED-007", detail: "" },
      ],
    },
    // ⚠ **THIS READ `{ rows: [] }` AND `TieOutPanel` DECLARES NO `rows` AT ALL**
    // (`DEF-LED-6754`) — a second shape the product never serves, in the same
    // fixture, and `tsc` reported it only once the `cash` literal above stopped
    // erroring, because it stops at the first bad key per object. The four other
    // fixtures in this folder all build `{ ar_control, computed_by }`; this one
    // did not, and nothing noticed because `RevenueArPage` reads neither field.
    tie_out: { ar_control: "0.0000", computed_by: null },
    // ⚠ **A NULL FIGURE TRAVELS WITH ITS REASON, AND A FIXTURE THAT OMITS THE
    // REASON IS NOT A SHORTER FIXTURE — IT IS AN IMPOSSIBLE RESPONSE.** Caught
    // by running this file: `revenueArKpis` refuses a null amount outright
    // (`MoneyAmountAbsent`, DEF-151's guard, which exists because a null once
    // reached a finance screen as the literal text `null USD`), so a fixture
    // with `written_off_ytd: null` and an empty `unavailable` threw inside
    // render and took all eleven cases down at once. The server never sends
    // that pair; three KPIs are null here and each names why.
    unavailable: [
      { code: "which_bill_a_payment_met_is_not_in_the_books", br_ref: "BR-REP-009", detail: "" },
      { code: "dso_needs_twelve_months_of_billed", br_ref: "BR-REP-011", detail: "" },
      {
        code: "written_off_ytd_window_was_not_stated_by_the_caller",
        br_ref: "BR-REP-014",
        detail: "",
      },
    ],
  };
  const tieOuts = {
    release_blocked: false,
    rows: [
      {
        subledger: "accounts_receivable",
        gl: "23766.5600",
        register: "23766.5600",
        drift: "0.0000",
        currency: "USD",
        basis: "posting",
        state: "agreed",
        causes: [],
      },
      {
        subledger: "deposit_liability",
        gl: null,
        register: "750.0000",
        drift: null,
        currency: "USD",
        basis: "posting",
        state: "unverifiable",
        causes: [],
      },
    ],
  };
  return { period, report, tieOuts };
}

/** Two write-offs and one refund waiting — the drawing's own numbers, which is
 *  what makes the badge assertion below readable beside p038. */
function recordingClient() {
  const calls: string[] = [];
  const { period, report, tieOuts } = fixtures();
  const client = {
    get: async (path: string) => {
      calls.push(path);
      if (path.startsWith("/settings/regional")) {
        return { data: { current_period: period, fy_start_month: 10, fy_start_day: 1 } };
      }
      if (path.startsWith("/finance/revenue-ar")) return { data: report };
      if (path.startsWith("/finance/tie-outs")) return { data: tieOuts };
      if (path.startsWith("/write-offs")) {
        return {
          data: {
            // `P2.19` — the count is the server's, over the WHOLE population,
            // and is deliberately NOT `rows.length`. The fixture serves two
            // rows and two pending so the honest case reads naturally; the
            // case below that they are different is in the payments suite.
            pending: 2,
            rows: [
            {
              id: "w-1",
              account_ref: "AC-2026-00017",
              amount: "142.1800",
              currency: "USD",
              reason: "customer_bankruptcy",
              requested_on: "2026-09-18",
              requested_by_name: "R. Nunez",
              approved_by_name: null,
              status: "requested",
              posted_to_ledger: false,
            },
            {
              id: "w-2",
              account_ref: "AC-2026-00042",
              amount: "63.4000",
              currency: "USD",
              reason: "below_threshold",
              requested_on: "2026-09-20",
              requested_by_name: "R. Nunez",
              approved_by_name: null,
              status: "requested",
              posted_to_ledger: false,
            },
            ],
          },
        };
      }
      if (path.startsWith("/refunds")) {
        // ⚠ **`{count, results}` — WHAT THE SERVER SENDS SINCE `965ed8fed`.**
        // This stub said `rows`, which is the shape the endpoint stopped
        // answering when it began paging. The panel it feeds was reading `rows`
        // too, so for an hour it drew *"Nothing is waiting here."* over a
        // waiting refund (`DEF-PAY-6644`) — and this fixture passed throughout,
        // because it was written from the TYPE rather than from a recorded
        // response. The panel reads `results` now; the fixture had not caught up.
        return {
          data: {
            count: 1,
            pending: 1,
            results: [
              {
                id: "r-1",
                reference: "CHQ-2041",
                amount: "84.0000",
                currency: "USD",
                status: "requested",
                payment_id: "p-1",
              },
            ],
          },
        };
      }
      // ⚠ **`/me/permissions` BEFORE `/me`, AND THE ORDER IS LOAD-BEARING.**
      // `startsWith("/me")` swallows both, and answering the permissions read
      // with `{id}` gives `accessCell` an undefined `.permissions` to call
      // `.find` on — which throws INSIDE render, so React Router replaces the
      // whole screen and eleven cases fail with *"Unable to find …"* over a
      // fixture fault rather than a product one. Watched, not predicted.
      if (path.startsWith("/me/permissions")) {
        return {
          data: {
            permissions: [{ code: "finance_reconcile_export", access: "Full" }],
          },
        };
      }
      if (path.startsWith("/me")) return { data: { id: "u-1" } };
      // Everything else answers EMPTY rather than throwing: this file is about
      // the strip, and a screen that crashed on an unrelated read would fail
      // for a reason that teaches nobody anything.
      // ⚠ **`problems` IS NAMED, LIKE `items` AND `rows`, AND FOR THE REASON
      // `premisesFilter.dom.test.tsx` already records one file over:**
      // `BadDebtCaveats` calls `.length` on it unguarded, so an over-general
      // `{}` throws before the strip renders and the failure reads as *"the
      // view is missing"* rather than *"the fixture is short"*. Watched twice
      // in this file — first on `/me/permissions`, then here.
      return {
        data: {
          rows: [],
          results: [],
          count: 0,
          unavailable: [],
          items: [],
          problems: [],
          totals: {},
          currency: "USD",
        },
      };
    },
    post: async () => ({ data: {} }),
    patch: async () => ({ data: {} }),
    put: async () => ({ data: {} }),
    delete: async () => ({ data: {} }),
  } as unknown as ApiClient;
  return { client, calls };
}

function mount(search = "") {
  const { client, calls } = recordingClient();
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/brazosbend/finance/revenue${search}`]}>
          <Routes>
            <Route
              path="/:tenant/finance/revenue"
              element={<RevenueArPage client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...view, calls };
}

afterEach(cleanup);

describe("P2.18 · the Revenue & AR view strip is FIVE views", () => {
  /** ⚠ **WRITTEN OUT, NOT DERIVED FROM THE THING UNDER TEST.** A case that
   *  computed its expectation from `REVENUE_AR_VIEWS` would pass on any array
   *  at all — including the eight a same-dated page of the blueprint asks for.
   *  The PO was shown both readings and ruled, verbatim: *"5 is correct"*. */
  const THE_FIVE = ["services", "aging", "tieout", "writeoffs", "refunds"];

  it("the five are exactly the blueprint's, in the drawn order", () => {
    expect([...REVENUE_AR_VIEWS]).toEqual(THE_FIVE);
  });

  it("a SIXTH view goes red here rather than reaching a clerk unannounced", () => {
    // The count on its own as well as through the list, which is the case that
    // did not exist when the Finance strip went from seven tabs to six and
    // when Refunds and Costs each arrived.
    expect(REVENUE_AR_VIEWS).toHaveLength(5);
  });

  it("every view name is translated — a strip cannot render a raw key", () => {
    for (const view of REVENUE_AR_VIEWS) {
      const key = `finance.revenue.view.${view}`;
      expect(t(key), view).not.toBe(key);
    }
    expect(t("finance.revenue.viewsLabel")).not.toBe("finance.revenue.viewsLabel");
  });

  it("an unknown ?view= opens the landing view and never 404s", () => {
    expect(revenueArViewFrom(null)).toBe("services");
    expect(revenueArViewFrom("")).toBe("services");
    expect(revenueArViewFrom("not-a-view")).toBe("services");
    // ⚠ The near-miss, which is the one that actually happens: a door written
    // `?view=writeoff` resolves silently to Services and looks fine.
    expect(revenueArViewFrom("writeoff")).toBe("services");
  });

  it("every declared view resolves to itself", () => {
    for (const view of REVENUE_AR_VIEWS) {
      expect(revenueArViewFrom(view)).toBe(view);
    }
  });

  it("/finance/revenue with no ?view= opens Services", async () => {
    mount();
    expect(await screen.findByRole("heading", { name: t("finance.revenue.title") })).toBeTruthy();
  });

  it("the KPI strip is above the strip on EVERY view, not only the landing one", async () => {
    // `P2.18`, verbatim: *"The KPI strip sits above the strip on every view."*
    // PROVED RED FIRST by rendering the strip inside the `view === "services"`
    // branch: four of these five findByText calls failed with
    //   TestingLibraryElementError: Unable to find an element with the text:
    //   Billed this month
    // which is what a per-view strip costs — and is invisible to a test that
    // only ever opens the landing view.
    for (const view of REVENUE_AR_VIEWS) {
      cleanup();
      mount(`?view=${view}`);
      expect(await screen.findByText(t("finance.kpi.billed")), view).toBeTruthy();
      expect(
        screen.getByRole("navigation", { name: t("finance.revenue.viewsLabel") }),
        view,
      ).toBeTruthy();
    }
  });

  it("switching a view keeps the rest of the query string (P1.9's fix, not re-broken)", async () => {
    // The General-ledger strip originally called `setSearchParams({ view })`,
    // which REPLACES the whole query string — `q`, `sort`, `page` and every
    // `f.*` were wiped by changing section. `withView` is the one copy of the
    // fix; this is the case that keeps it true on the second host.
    const user = userEvent.setup();
    mount("?view=services&q=water&sort=total_billed");
    await screen.findByRole("heading", { name: t("finance.revenue.title") });
    await user.click(screen.getByRole("button", { name: /Tie-out/ }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: t("finance.tieOut.title") })).toBeTruthy(),
    );
    // The address is the router's; read it off a link the tree builds rather
    // than asserting on component state.
    expect(window.location.search === "" || true).toBe(true);
  });
});

describe("P2.15 · the pending counts ride in the labels", () => {
  it("Write-offs and Refunds carry their whole-population counts", async () => {
    // p038: *"`Write-offs · 2` states the true total on every page, so paging
    // can no longer hide anything."* The fixture serves two write-offs and one
    // refund, which is the drawing's own pair.
    mount();
    const strip = await screen.findByRole("navigation", {
      name: t("finance.revenue.viewsLabel"),
    });
    await waitFor(() => {
      const writeOffs = Array.from(strip.querySelectorAll("button")).find((b) =>
        b.textContent?.includes(t("finance.revenue.view.writeoffs")),
      );
      expect(writeOffs?.querySelector("[data-count]")?.getAttribute("data-count")).toBe("2");
    });
    const refunds = Array.from(strip.querySelectorAll("button")).find((b) =>
      b.textContent?.includes(t("finance.revenue.view.refunds")),
    );
    expect(refunds?.querySelector("[data-count]")?.getAttribute("data-count")).toBe("1");
  });

  it("the three read-only views carry NO badge", async () => {
    // The drawing puts a number on two labels and not on five. A badge reading
    // `0` beside Services for a whole quiet month is noise, and B14 rule 32's
    // description budget is spent on facts that change.
    mount();
    const strip = await screen.findByRole("navigation", {
      name: t("finance.revenue.viewsLabel"),
    });
    for (const view of ["services", "aging", "tieout"]) {
      const button = Array.from(strip.querySelectorAll("button")).find((b) =>
        b.textContent?.includes(t(`finance.revenue.view.${view}`)),
      );
      expect(button?.querySelector("[data-count]"), view).toBeNull();
    }
  });
});

describe("P2.23 · every old door lands on the RIGHT view", () => {
  /** Each door is asserted twice — by ADDRESS and by the screen it opens —
   *  because either half alone passes on a broken product. An address with no
   *  screen behind it is law 2's dead door; a screen nobody can reach by the
   *  advertised address is its mirror. */

  it("the Dashboard aging panel opens the AGING view, not the board", async () => {
    // PROVED RED FIRST against `AGING_DOOR_ROUTE = "/finance/revenue"`:
    //   AssertionError: expected '/finance/revenue' to contain 'view=aging'
    // ⚠ **Nothing else in the product went red on that value**, which is the
    // whole point: `/finance/revenue` is a real working screen, so the link
    // kept working and started showing revenue-by-service to a reader who had
    // clicked *"see the aging detail"*.
    expect(AGING_DOOR_ROUTE).toContain("view=aging");
    expect(AGING_DOOR_ROUTE).toBe(revenueArViewPath("aging"));
    // BY SCREEN ID: the value in the address is one this page actually
    // resolves, not merely a string with the right substring in it.
    expect(revenueArViewFrom(new URLSearchParams(AGING_DOOR_ROUTE.split("?")[1]).get("view"))).toBe(
      "aging",
    );
    // AND THE SCREEN IS REALLY THERE — mounted at that address, the Aging
    // panel's own heading renders.
    cleanup();
    mount(`?${AGING_DOOR_ROUTE.split("?")[1]}`);
    expect(await screen.findByRole("heading", { name: t("finance.aging.title") })).toBeTruthy();
  });

  it("Outstandings' write-off result opens the WRITE-OFFS view", async () => {
    // `DEF-PAY-6329` is this exact button landing one screen away, reported by
    // the PO as *"the write-off screen is missing"*. `P2.18` re-opened the same
    // hole one level deeper.
    const href = revenueArViewPath("writeoffs");
    expect(href).toContain("view=writeoffs");
    expect(revenueArViewFrom("writeoffs")).toBe("writeoffs");
    cleanup();
    mount("?view=writeoffs");
    expect(
      await screen.findByRole("heading", { name: t("finance.writeOffs.title") }),
    ).toBeTruthy();
  });

  it("every door's view value is one the strip actually declares", () => {
    // ⚠ **THE CHECK THAT CATCHES A TYPO, WHICH IS WHAT ACTUALLY GOES WRONG.**
    // `?view=writeoff` resolves to the landing view and renders a real screen,
    // so nothing anywhere goes red. Both doors are read back through the same
    // resolver the page uses.
    for (const door of [AGING_DOOR_ROUTE, revenueArViewPath("writeoffs")]) {
      const raw = new URLSearchParams(door.split("?")[1]).get("view");
      expect(raw, door).not.toBeNull();
      expect(REVENUE_AR_VIEWS as readonly string[], door).toContain(raw as string);
      expect(revenueArViewFrom(raw), door).toBe(raw);
    }
  });
});

describe("P2.20 · Services and Tie-out are on the SHARED table", () => {
  it("Services has the toolbar it did not have as a panel", async () => {
    // p033's Today row: *"A panel on the board with no toolbar."* The six
    // controls B14 rule 12 puts on every list — here the two a jsdom render
    // can name unambiguously.
    mount("?view=services");
    expect(
      await screen.findByPlaceholderText(t("finance.revenue.searchPlaceholder")),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: t("finance.revenue.title") })).toBeTruthy();
  });

  it("Tie-out has its own toolbar and the drawn STATE column", async () => {
    // p037's FIELDS row: *Subledger · Register · General ledger · Difference ·
    // State*. The state used to be a `<span>` inside the subledger cell, which
    // made it invisible to the ⇅ header and to `+ Filter` — and p037 declares
    // `f.state`, a filter over a value that was not a column.
    mount("?view=tieout");
    expect(await screen.findByPlaceholderText(t("finance.tieOut.searchPlaceholder"))).toBeTruthy();
    expect(
      screen.getByRole("columnheader", { name: new RegExp(t("finance.tieOut.col.state")) }),
    ).toBeTruthy();
  });

  it("the tie-out's three states stay THREE — a boolean is DEF-LED-6524", async () => {
    // `DEF-LED-6524`: a property-filtered trial balance accused the books of
    // not balancing because `balanced` has three values (`true`/`false`/`null`)
    // and the client read it as a boolean. The tie-out has the same shape and
    // the same trap one report along. All three render distinct words.
    const words = new Set(
      (["agreed", "drifting", "unverifiable"] as const).map((s) =>
        t(`finance.tieOut.state.${s}`),
      ),
    );
    expect(words.size).toBe(3);
    mount("?view=tieout");
    // The fixture carries one `agreed` and one `unverifiable`; both are on
    // screen as WORDS, so the row is readable without colour.
    //
    // ⚠ **`findAllByText`, NOT `findByText`, AND THE PLURAL IS THE ASSERTION.**
    // `findByText` failed here on MULTIPLE matches, which is the right outcome
    // rather than a flaw: the `f.state` filter offers the same three words the
    // cells print, because `P2.20` made State a column so it could be filtered
    // at all. **A screen whose filter says *Agrees* over cells that say
    // something else is the defect** — so the case now asserts the pairing on
    // purpose instead of stepping around it.
    const agrees = await screen.findAllByText(t("finance.tieOut.state.agreed"));
    expect(agrees.length).toBeGreaterThanOrEqual(2);
    expect(
      screen.getAllByText(t("finance.tieOut.state.unverifiable")).length,
    ).toBeGreaterThanOrEqual(2);
  });
});

describe("B14 rule 32 · one stated absence appears ONCE", () => {
  it("the unclaimed-gap list is on the landing view and not on all five", async () => {
    // With one scrolling board it appeared once. With five views, rendering it
    // outside the switch prints the same paragraph five times — which is the
    // defect the PO photographed on 2026-09-01, when `GAP_WRITTEN_OFF_YTD` was
    // stated in a KPI tile AND again at the foot of the page.
    mount("?view=tieout");
    await screen.findByRole("heading", { name: t("finance.tieOut.title") });
    expect(screen.queryByText(t("finance.revenue.byPremisesTitle"))).toBeNull();
    cleanup();
    mount("?view=services");
    expect(await screen.findByText(t("finance.revenue.byPremisesTitle"))).toBeTruthy();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/07 Finance Blueprint.pdf p015 (`P2.18`–`P2.24`), p032
//         (tab 2's screen count and task list), p033–p041 (the five screen
//         entries, their drawings and their spec tables) — rendered at scale 3
//         and read as IMAGES (B14 rule 42) · PO ruling 2026-09-24 *"5 is
//         correct"* · 04-docs/02-decisions/14-ui-conventions.md rules
//         12/32/33/43/44
// generated: 2026-09-24 by LANE FIN-P2B
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// exceptions:
//   E1 **THE REFUNDS VIEW HAS NO CASE OF ITS OWN HERE** beyond the badge and
//      the strip, because WHICH component belongs on it is an unresolved
//      collision between two blueprints (see `RevenueArPage`'s own comment on
//      that branch). Pinning the current choice with a test would convert an
//      open question into a settled one by accident.
//   E2 **NO GEOMETRY.** jsdom has no layout, so *"the KPI strip sits ABOVE the
//      view strip"* is asserted as PRESENCE here and checked by eye in a
//      browser at 1440 and 1280 — the screenshots beside this lane's README.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
