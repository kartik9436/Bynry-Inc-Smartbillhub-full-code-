// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-4283 — the DEF-SHL-4272 Billing Clerk lockout survived
//          outside the shell, on every screen that read the admin-only
//          GET /settings/regional for itself.
//          Screens: S60 (Reports → By premises) · Payments → Refunds
// Rules:   BR-SHL-252 as amended 2026-09-06 · A4 `reports` (Clerk **Run**) ·
//          A4 `payments_record` (Clerk **Full**) · A4 `settings_lookups`
//          (Clerk has NO cell — unchanged) · BR-TEN-022 (the period is COMPUTED
//          and never stored) · hard-won law 2's fixture clause (mount a routed
//          component under the REAL path pattern)
// ───────────────────────────────────────────────────────
//
// A BILLING CLERK OPENS THE TWO SCREENS THAT WERE BROKEN, AGAINST A SERVER THAT
// REFUSES THEM AT `/settings/regional` THE WAY THE REAL ONE DOES.
//
// ⚠ **THE POINT OF THIS FILE IS THE 403 IT SERVES.** `GET /settings/regional`
// is `SettingsReadAnyWriteSystemAdmin` — `{system_admin, executive}` — so for a
// clerk it answers `403 AUTH-002`. Every other frontend suite in this repo
// passes formatting as a prop or seeds the query cache, and that is exactly why
// a total lockout survived a green suite and two passing browser walks
// (`DEF-SHL-4272`). So the client below **refuses every `/settings/…` path**
// and serves `/shell/display`, which any signed-in role may read. A screen that
// still reaches for the settings endpoint cannot draw here, and the list of
// paths it asked for is recorded so the assertion is evidence rather than an
// impression.
//
// ⚠ **MOUNTED UNDER THE REAL `/:tenant/…` PATH PATTERN, NEVER BARE.** A
// `MemoryRouter` with no `/:tenant/…` route leaves `useParams().tenant`
// undefined and every address a screen builds comes out `//reports/…` — a
// protocol-relative URL to another host that reads as a perfectly good string
// to `toContain`. That fixture shape is how `DEF-CWP-3925` hid, and the last
// case below asserts the pattern is doing its job before anything else is
// believed.
import { act, cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";
import type { ByPremisesResponse, MyPermissions, SessionUser } from "@/api/endpoints";
import { BY_PREMISES_ROUTE } from "./reportsShared";
import { REFUNDS_ROUTE } from "@/features/payments/paymentsShared";
import { ByPremisesReportPage } from "./ByPremisesReportPage";
import { RefundsPage } from "@/features/payments/RefundsPage";

afterEach(cleanup);

const TENANT = "brazosbend";

/** The seeded Billing Clerk. A4 gives this role NO `settings_lookups` cell. */
const CLERK: SessionUser = {
  id: "u9",
  full_name: "Sam Reyes",
  email: "sam.reyes@sample.test",
  phone: null,
  role: "billing_clerk",
  role_name: "Billing Clerk",
  must_change_password: false,
};

/**
 * What `GET /me/permissions` answers a Billing Clerk — A4's own rows.
 *
 * `reports: Run` and `payments_record: Full` are why these two screens are
 * theirs. There is deliberately **no `settings_lookups` row**, because A4 gives
 * them no cell at all, and that absence is the fact the whole defect turns on.
 */
const CLERK_PERMISSIONS: MyPermissions = {
  role: "billing_clerk",
  role_name: "Billing Clerk",
  permissions: [
    { code: "reports", label: "Reports", access: "Run" },
    { code: "payments_record", label: "Payments (record)", access: "Full" },
    { code: "premises_accounts", label: "Premises / Accounts", access: "Full" },
  ],
};

/** The period this tenant is actually in. Its fiscal year start IS set. */
const PERIOD = {
  fy_label: "FY2026",
  period: 9,
  start: "2026-09-01",
  end: "2026-09-30",
  status: "open",
};

const REPORT: ByPremisesResponse = {
  basis: "posting",
  currency: "USD",
  period: { start: PERIOD.start, end: PERIOD.end },
  // The read model's real answer today — US-LED-002 is unbuilt, so no journal
  // line carries a premises. The screen's job is to say so with the figure.
  available: false,
  rows: [],
  kpis: { premises: 0, billed: "0.0000", collected: "0.0000", owed: "0.0000" },
  unattributed_billed: "553.6900",
  unattributed_collected: "446.3700",
  unavailable: [],
};

/**
 * A server that answers a Billing Clerk the way the real one does.
 *
 * Every `/settings/…` path throws `403 AUTH-002`, exactly as
 * `SettingsReadAnyWriteSystemAdmin` does for this role. `/shell/display` is
 * served, as `ShellDisplayRead` does. Every path asked for is pushed onto
 * `seen`, so "did this screen reach for the admin endpoint" is answered by
 * evidence.
 */
function clerkClient(seen: string[]): ApiClient {
  // ⚠ THE WINDOW TRAVELS IN `options.query`, NOT IN THE PATH — so a recorder
  // that logged the path alone would have said "the report ran" while telling
  // you nothing about WHICH month it ran over, and the first draft of this file
  // then matched `/reports/by-premises` against a route actually spelled
  // `/reports/by_premises` and served the screen an empty body. Both were
  // caught by running it. Record the query with the path.
  const record = (path: string, options?: { query?: Record<string, unknown> }) => {
    const query = options?.query;
    const suffix =
      query && Object.keys(query).length > 0
        ? `?${Object.entries(query)
            .map(([k, v]) => `${k}=${String(v)}`)
            .join("&")}`
        : "";
    seen.push(`${path}${suffix}`);
  };
  const get = async (path: string, options?: { query?: Record<string, unknown> }) => {
    record(path, options);
    if (path.includes("/settings/")) {
      throw new ApiError(403, { code: "AUTH-002", message_key: "errors.forbidden" });
    }
    if (path.includes("by_premises")) return { data: REPORT, status: 200 };
    return { data: {}, status: 200 };
  };
  const write = async (path: string) => {
    record(path);
    return { data: {}, status: 200 };
  };
  const client = { request: get, get, post: write, put: write, patch: write, delete: write };
  return client as unknown as ApiClient;
}

/**
 * Let every query this render started actually run.
 *
 * ⚠ **WITHOUT THIS THE RED PROOF LIED ABOUT ITS OWN CAUSE.** React Query calls
 * a `queryFn` in a microtask, so an assertion made in the same tick as `render`
 * reads a screen mid-fetch. Run against the DEFECT, the recorder was still
 * empty and this file reported *"the mount failed"* — true-shaped, entirely
 * wrong, and exactly the shape hard-won law 7 calls *a check whose output
 * cannot distinguish pass from fail to a reader*.
 */
async function settle(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

/** Mount one screen at its REAL address, under the real `/:tenant/…` pattern. */
function open(route: string, element: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, CLERK);
  queryClient.setQueryData(queryKeys.myPermissions, CLERK_PERMISSIONS);
  // The ONE regional read a clerk's session legitimately holds, and the whole
  // point of the fix: the boot payload, carrying the period.
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  const router = createMemoryRouter([{ path: `/:tenant${route}`, element }], {
    initialEntries: [`/${TENANT}${route}`],
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The sentence a clerk saw instead of a period. */
const NO_PERIOD = i18n.t("settings.regional.noPeriod") as string;
/**
 * The Refunds page-head title — the proof the screen MOUNTED.
 *
 * ⚠ This was `PERIOD_LABEL` ("FY2026 · Period 9") until `DEF-PAY-6672`. `P4.10`
 * took the finance period off this screen deliberately when it moved out of
 * Finance, so the period is no longer a thing to assert here; what still has to
 * be proved is that the screen rendered, because every other assertion in that
 * case is a NEGATIVE and a negative is free on a blank page.
 */
const REFUNDS_TITLE = i18n.t("payments.refunds.title") as string;

describe("DEF-SHL-4283 — a Billing Clerk gets the tenant's period, not a false sentence", () => {
  it("the fixture can tell a working mount from a broken one", async () => {
    // ⚠ FIRST, BECAUSE EVERYTHING ELSE HERE IS WORTHLESS WITHOUT IT. A route
    // pattern with no `:tenant` segment leaves `useParams().tenant` undefined
    // and the screen's Back link comes out `//finance` — a protocol-relative
    // URL to another host that satisfies any `toContain`. This asserts the
    // tenant actually reached the screen, by reading an address it BUILT.
    const seen: string[] = [];
    open(BY_PREMISES_ROUTE, <ByPremisesReportPage client={clerkClient(seen)} />);
    await settle();
    const back = document.querySelector('a[href*="/finance"]');
    expect(back, "the screen drew no link back to Finance at all").not.toBeNull();
    expect(back?.getAttribute("href")).toBe(`/${TENANT}/finance`);
    expect(back?.getAttribute("href")).not.toMatch(/^\/\//);
  });

  it("Reports → By premises does NOT tell a clerk to set the fiscal year start", async () => {
    const seen: string[] = [];
    open(BY_PREMISES_ROUTE, <ByPremisesReportPage client={clerkClient(seen)} />);
    await settle();
    // ⚠ THE DEFECT, INVERTED. `settings.regional.noPeriod` reads "Set the
    // fiscal year start to see the current period." — false at this tenant,
    // whose start IS set, and pointing at a screen only a System Admin can
    // open. It was the whole screen for a clerk.
    expect(screen.queryByText(NO_PERIOD)).toBeNull();
  });

  it("…and the report is actually REQUESTED for them, which is the real damage", async () => {
    // A missing sentence is not proof the report ran. `enabled: period !== null`
    // is what silenced it, so the assertion is that the request HAPPENED.
    const seen: string[] = [];
    open(BY_PREMISES_ROUTE, <ByPremisesReportPage client={clerkClient(seen)} />);
    await settle();
    expect(
      seen.some((path) => path.includes("by_premises")),
      "the by-premises report was never requested for a Billing Clerk. Paths " +
        `the screen asked for: ${seen.join(", ") || "(none)"}`,
    ).toBe(true);
    // And it ran over the TENANT'S window, not a month computed in the browser.
    expect(seen.join(" ")).toContain(PERIOD.start);
    expect(seen.join(" ")).toContain(PERIOD.end);
  });

  it("Payments → Refunds does not tell a clerk to set the fiscal year start", async () => {
    // ⚠ **THIS CASE ASSERTED `PERIOD_LABEL` AND WAS RED FROM 2026-09-24 TO
    // 2026-09-25 (`DEF-PAY-6672`). THE SCREEN DID NOT REGRESS.** `P4.10`
    // (`CR-138-BRC07`, decision log 2026-09-23) moved Refunds OUT of Finance:
    // `REFUNDS_ROUTE` is `/payments/refunds`, the frame is `PageHeader` with
    // the payments seven, and `RefundsPage` records in its own body that the
    // finance period "left with the frame" because *"a refunds list is NOT
    // period-scoped either way: a request waits until somebody works it."*
    //
    // ⚠ **WHAT `DEF-SHL-4283` ACTUALLY RULED IS UNTOUCHED BY THAT MOVE**, and
    // it is what this case now asserts. The defect was a clerk being shown
    // *"Set the fiscal year start to see the current period."* — a FALSE
    // sentence at a tenant whose start IS set, pointing at a screen only a
    // System Admin can open. Not showing a period at all is not that defect.
    // The rule's own words are that a screen is served what it needs "in order
    // to DRAW ITSELF"; this screen no longer draws one.
    //
    // ⚠ **THE MOUNT IS ASSERTED FIRST, AND THAT IS NOT CEREMONY.** A lone
    // `queryByText(...).toBeNull()` passes on a screen that rendered NOTHING —
    // and when this case failed, the DOM was a skeleton, so the absence proved
    // nothing either way. That is the same false pass this file's own first
    // case was written to close, one screen over. Without this line the fix
    // for `DEF-PAY-6672` would itself have been a check that cannot fail.
    const seen: string[] = [];
    open(REFUNDS_ROUTE, <RefundsPage client={clerkClient(seen)} />);
    await settle();
    // A4's `payments_record` row gives a clerk **Full** here, and RefundsPage
    // says so in its own words: "gating the screen on the reconcile cell would
    // shut out the very person the raise route is for."
    expect(
      screen.getByRole("heading", { name: REFUNDS_TITLE, level: 1 }),
      "Refunds did not mount for a Billing Clerk at all, so the absence of the " +
        "no-period sentence below proves nothing",
    ).toBeTruthy();
    expect(screen.queryByText(NO_PERIOD)).toBeNull();
  });

  it("neither screen asks for /settings/regional at all", async () => {
    // The assertions above could in principle pass while a screen ALSO fired a
    // doomed settings request in the background. This says the read MOVED,
    // rather than merely that something else filled the gap.
    const cases: [string, (client: ApiClient) => ReactElement][] = [
      [BY_PREMISES_ROUTE, (client) => <ByPremisesReportPage client={client} />],
      [REFUNDS_ROUTE, (client) => <RefundsPage client={client} />],
    ];
    for (const [route, build] of cases) {
      const seen: string[] = [];
      open(route, build(clerkClient(seen)));
      await settle();
      expect(seen.length, `${route} made no requests at all — the mount failed`).toBeGreaterThan(0);
      expect(
        seen.filter((path) => path.includes("/settings/regional")),
        `${route} still reads the Admin/Executive settings endpoint`,
      ).toEqual([]);
      cleanup();
    }
  });

  it("and the clerk is STILL refused at Settings — the fix is a separation", () => {
    // ⚠ A RUN WHERE EVERYTHING ABOVE PASSES AND THIS FAILS MEANS SOMEBODY
    // WIDENED THE SETTINGS GATE AND RE-OPENED DEF-196. It also proves the
    // server this file models really does refuse, so the four cases above were
    // measured against a clerk who genuinely cannot read Settings — without it
    // they would pass just as well against a server that answers everything.
    const seen: string[] = [];
    const client = clerkClient(seen);
    return client.get("/settings/regional").then(
      () => {
        throw new Error("GET /settings/regional answered a Billing Clerk — DEF-196 is back");
      },
      (error: unknown) => {
        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).status).toBe(403);
        expect((error as ApiError).code).toBe("AUTH-002");
      },
    );
  });
});
