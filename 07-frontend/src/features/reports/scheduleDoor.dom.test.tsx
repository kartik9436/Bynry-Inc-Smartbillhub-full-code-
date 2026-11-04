// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  `DEF-REP-6913` — `ScheduleReportDialog` was built, tested and
//          mounted by NOTHING. A person could not schedule a report in this
//          product. Drawing p034 (screen `2·3`) DOORS row, read as an IMAGE
//          per B14 rule 42: *"One: the Schedule button on 2·1. ⚠ It is
//          **disabled** where the report cannot be produced — you cannot
//          schedule a refusal (see 2·1d)."*
// Rules:   CLAUDE.md hard-won law 2 (built is not wired) AND ITS MIRROR (a
//          live screen behind a dead control) · law 2's fixture clause (mount
//          the routed component under the REAL path pattern) · law 7 clause
//          (2) — what would make this check pass WRONGLY · B14 rule 33.
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THIS TEST ASSERTS THE SCREEN, NOT THE COMPONENT                        ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// `scheduledTab.dom.test.tsx` already imports `ScheduleReportDialog` and
// renders it directly, and every one of its assertions passed on the day the
// defect was filed — because a dialog that renders when a TEST mounts it is
// not a dialog a PERSON can reach. That is exactly hard-won law 2 for a
// dialog rather than for a prop, and `G13` cannot see it: `G13` asks whether a
// declared prop is PASSED, never whether a built component is MOUNTED.
//
// So this file imports `ReportViewerPage` and NEVER `ScheduleReportDialog`.
// It mounts screen `2·1` at its real address and asks whether a person
// standing on it can get to `2·3`. If somebody deletes the button tomorrow,
// this goes red; if somebody deletes the dialog, this goes red. A test that
// imported the dialog would survive both.
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7 clause 2):
//
//   · **A bare `MemoryRouter`.** `useParams().tenant` would be undefined and
//     the screen would render something that is not this screen. The router
//     below mounts the real `/:tenant/reports/:reportKey`.
//   · **Matching a CLASS NAME or a `data-testid`.** Both survive a button that
//     opens nothing. The assertions below press the control and then require
//     the DIALOG'S OWN title and its three field labels — what it OPENS, by
//     what a person reads, which is what the defect asked for.
//   · **Asserting only the happy path.** A door drawn over a refusal is the
//     defect this repo files as the MIRROR of law 2, so the refusal cases
//     assert the button is DISABLED and, for a 403, ABSENT — a `getBy` that
//     only ever looks for presence cannot fail that way.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

import { ReportViewerPage } from "./ReportViewerPage";
import { REPORTS_ROUTE } from "./reportsShared";

afterEach(cleanup);

const t = i18n.getFixedT("en");
const TENANT = "brazosbend";

const USER: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@sample.test",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "reports", label: "Reports", access: "Full" }],
};

const PERIOD = {
  fy_label: "FY2026",
  period: 9,
  start: "2026-09-01",
  end: "2026-09-30",
  status: "open",
};

const REGISTER = {
  key: "billing_register",
  basis: "posting",
  window: { start: "2026-09-01", end: "2026-09-30" },
  currency: "USD",
  columns: ["invoice_no", "account_no", "amount"],
  rows: [{ invoice_id: "i1", invoice_no: "BL-2609-000001", account_no: "100244", amount: "247.87" }],
  kpis: [],
  totals: { amount: "247.87" },
  unavailable: [],
  grain: "bill",
  page: { page: 1, per: 50, total: 1, pages: 1 },
  controls: { sorts: ["invoice_no"], sort: "invoice_no", dir: "asc", searchable: true },
};

/** What `GET /reports/schedules` serves the dialog: the two SIGNED vocabularies
 *  and this tenant's own staff (`BR-REP-020`). The picker's options are SERVED,
 *  never typed out on the client — so a fixture that invented them would be
 *  testing the fixture. */
const SCHEDULE_PAGE = {
  rows: [],
  total: 0,
  page: 1,
  per: 50,
  cadences: ["daily", "weekly", "monthly", "monthly_on_cycle_close"],
  formats: ["csv"],
  statuses: ["on", "paused", "failing"],
  staff: [
    { id: "u1", name: "Dana Whitfield" },
    { id: "u2", name: "Sam Reyes" },
  ],
};

type Refusal = { status: number; code: string; message_key: string } | null;

/** A client that answers the report run however the case needs, and records
 *  every write so the commit case can assert the BODY rather than a toast. */
function client(refusal: Refusal = null): { client: ApiClient; posts: { path: string; body: unknown }[] } {
  const posts: { path: string; body: unknown }[] = [];
  const get = async (path: string) => {
    if (path.startsWith("/reports/schedules")) return { data: SCHEDULE_PAGE, status: 200 };
    if (path.startsWith("/reports/") && refusal) {
      // ⚠ A REAL `ApiError`. `isPermissionDenied` is `instanceof` plus the
      // status, so a duck-typed object walks straight past the 403 branch and
      // lands in the generic error panel — which is a fixture testing itself.
      throw new ApiError(refusal.status, {
        code: refusal.code,
        message_key: refusal.message_key,
      });
    }
    if (path.startsWith("/reports/")) return { data: REGISTER, status: 200 };
    if (path === "/reports") {
      return {
        data: { cards: [], vocabularies: { services: [], bill_types: [], purposes: [] } },
        status: 200,
      };
    }
    if (path.startsWith("/lookups/")) return { data: { results: [], count: 0 }, status: 200 };
    return { data: {}, status: 200 };
  };
  const post = async (path: string, body: unknown) => {
    posts.push({ path, body });
    return { data: { id: "s1" }, status: 201 };
  };
  const write = async () => ({ data: {}, status: 200 });
  return {
    posts,
    client: {
      request: get,
      get,
      post,
      put: write,
      patch: write,
      del: write,
      delete: write,
    } as unknown as ApiClient,
  };
}

function mountViewer(api: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  // ⚠ THE REAL PATH PATTERN — law 2's fixture clause.
  const router = createMemoryRouter(
    [
      {
        path: `/:tenant${REPORTS_ROUTE}/:reportKey`,
        element: <ReportViewerPage client={api} timeZone="America/Chicago" today="2026-09-26" />,
      },
    ],
    { initialEntries: [`/${TENANT}${REPORTS_ROUTE}/billing-register`] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return queryClient;
}

// ═══════════════════════════════════════════════════════════════════════════
// DEF-REP-6913 — THE DOOR EXISTS, AND IT OPENS ONTO `2·3`
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-6913 · screen 2·1 carries the ONE door to 2·3", () => {
  it("the report viewer draws a Schedule control", async () => {
    const { client: api } = client();
    mountViewer(api);
    await waitFor(() => expect(screen.getByText("BL-2609-000001")).toBeTruthy());
    const door = screen.getByRole("button", { name: t("reports.schedule.door") });
    expect(door).toBeTruthy();
    expect((door as HTMLButtonElement).disabled).toBe(false);
  });

  it("pressing it opens the dialog — its title and all THREE fields", async () => {
    const { client: api } = client();
    mountViewer(api);
    await waitFor(() => expect(screen.getByText("BL-2609-000001")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: t("reports.schedule.door") }));

    // What it OPENS, by what a person reads — never a class or a testid.
    await waitFor(() => expect(screen.getByText(t("reports.schedule.title"))).toBeTruthy());
    expect(screen.getByLabelText(new RegExp(t("reports.schedule.cadence")))).toBeTruthy();
    expect(screen.getByLabelText(new RegExp(t("reports.schedule.format")))).toBeTruthy();
    expect(screen.getAllByText(t("reports.schedule.sendTo")).length).toBeGreaterThan(0);
  });

  it("the commit reaches POST /reports/schedules carrying the report BEHIND it", async () => {
    const { client: api, posts } = client();
    mountViewer(api);
    await waitFor(() => expect(screen.getByText("BL-2609-000001")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: t("reports.schedule.door") }));
    await waitFor(() => expect(screen.getByText(t("reports.schedule.title"))).toBeTruthy());

    // One recipient, because `recipients` is `.min(1)`: a schedule with nobody
    // on it produces a file every month and tells no one.
    // ⚠ The kit's add control is a bare `<select>` (`ChipMultiSelect`), not a
    // button — driven here the way `scheduledTab.dom.test.tsx` drives it, by
    // the `data-chip-add` hook the component declares as its contract.
    const add = document.querySelector<HTMLSelectElement>('[data-chip-add="schedule-recipients"]');
    expect(add, "the recipients picker is not on screen").toBeTruthy();
    fireEvent.change(add as HTMLSelectElement, { target: { value: "u2" } });
    await waitFor(() => expect(screen.getByText("Sam Reyes")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: t("reports.schedule.commit") }));

    await waitFor(() => expect(posts.length).toBe(1));
    expect(posts[0].path).toBe("/reports/schedules");
    // ⚠ The report and its parameters are INHERITED from the screen behind
    // (p034). A body without them would type-check and schedule nothing.
    expect((posts[0].body as { definition_key: string }).definition_key).toBe("billing_register");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// LAW 2'S MIRROR — YOU CANNOT SCHEDULE A REFUSAL
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-6913 · the door is not drawn over a refusal", () => {
  it("a report that CANNOT BE PRODUCED offers a disabled Schedule", async () => {
    // p034 DOORS: *"It is disabled where the report cannot be produced — you
    // cannot schedule a refusal (see 2·1d)."*
    const { client: api } = client({
      status: 422,
      code: "VAL-020",
      message_key: "reports.library.unavailableGeneric",
    });
    mountViewer(api);
    await waitFor(() =>
      expect(screen.getByText(t("reports.premises.unavailableTitle"))).toBeTruthy(),
    );
    const door = screen.getByRole("button", { name: t("reports.schedule.door") });
    expect((door as HTMLButtonElement).disabled).toBe(true);
  });

  it("a report REFUSED TO THIS ROLE offers no Schedule at all", async () => {
    // The 403 branch replaces the whole screen, so there is no header to hang a
    // door on. Asserted so that a future refactor cannot quietly draw one.
    const { client: api } = client({
      status: 403,
      code: "AUTH-002",
      message_key: "reports.viewer.role_refused",
    });
    mountViewer(api);
    await waitFor(() => expect(screen.getByText(t("states.denied.title"))).toBeTruthy());
    expect(screen.queryByRole("button", { name: t("reports.schedule.door") })).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DEF-REP-6907 — A REPORT REFUSED FOR ONE ROLE IS NOT A MODULE-WIDE REFUSAL
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-6907 · the 403 renders the SERVER's sentence", () => {
  it("names the report, and does not claim the clerk cannot run reports", async () => {
    const { client: api } = client({
      status: 403,
      code: "AUTH-002",
      message_key: "reports.viewer.role_refused",
    });
    mountViewer(api);
    await waitFor(() => expect(screen.getByText(t("states.denied.title"))).toBeTruthy());
    // The six-word sentence that TRAVELS FROM THE SERVER.
    expect(screen.getByText(t("reports.viewer.role_refused"))).toBeTruthy();
    // ⚠ Both directions. The false sentence must be GONE, not merely
    // outnumbered — a one-directional assertion is what let this ship.
    expect(screen.queryByText(t("reports.denied"))).toBeNull();
  });
});
