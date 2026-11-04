// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-001 (the shell's URLs) · US-IDN-001 (per-tenant sign-in) ·
//           US-TEN-001 (signup lands in the new tenant) · US-TEN-003 (S62 deep links) ·
//           US-TEN-005 (the deep-link target this file uses: S8 Company)
//           Screens: S1, S3, S8, S62, S110–S114 + every authenticated screen
// Rules:    BR-TEN-003 (the tenant comes from the REQUEST — the URL's first path segment
//           since PO 2026-08-10) · BR-IDN-001 (resolve the tenant first) ·
//           BR-SHL-001/BR-SHL-004 (nav + breadcrumb targets) · BR-SHL-020 (the failed state
//           a 404 renders is the ORDINARY one)
// ───────────────────────────────────────────────────────
// The acceptance tests for the PO's 2026-08-10 path-tenancy ruling. Four things
// have to be true and stay true:
//
//   1. a deep link `/{tenant}/settings/company` renders that screen, with the
//      tenant in scope for its links and its API calls;
//   2. internal navigation KEEPS the tenant segment — no screen can walk out of
//      the utility it is in;
//   3. signup ends inside the new tenant (`/{tenant}/checklist`) with no
//      cross-host link anywhere;
//   4. a 404 from a foreign tenant's path renders the ORDINARY not-found state
//      — never "switch tenant?", never a silent redirect to the session's own.
//
// (4) is the control the ruling makes load-bearing: one origin means the
// browser no longer isolates tenants, so the server binds the session to its
// tenant and answers 404 elsewhere. The UI's whole job is to not undermine
// that by being helpful.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, useRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import i18n, { LOCALE_CODES } from "@/i18n";
import { APP_ROUTES } from "@/App";
import { apiPath, createApiClient } from "@/api/client";
import { getCompanyProfile } from "@/api/endpoints";
import type {
  Checklist,
  CompanyProfile,
  MyPermissions,
  RegionalSettings,
  SessionUser,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";
import { CompanyTab } from "@/features/tenancy/SettingsCompanyTab";
import { CHECKLIST_SEGMENT } from "@/features/tenancy/SignupWizard";

import {
  PUBLIC_SEGMENTS,
  SIGNIN_SEGMENT,
  tenantFromPathname,
  tenantPathFrom,
  withinTenant,
} from "./tenantPath";

const TENANT = "brazosbend";
const OTHER = "lonestar";

const DANA: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@brazosbend.example",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const ADMIN_PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [
    { code: "settings_lookups", label: "Settings & lookup tables", access: "Full" },
    { code: "user_management", label: "User management", access: "Full" },
    // A4's "Finance / reconcile / export" row — System Admin is Full. Seeded
    // 2026-08-15 by the DEF-112 lane so a deep link to a Finance tab renders
    // that tab's SCREEN here rather than A18 §6's denied frame: without the
    // cell, `useAccessCell` denies and a routing test would "pass" on a route
    // that reached nothing. This is a routing suite, so the access decision
    // must not be what it is measuring.
    { code: "finance_reconcile_export", label: "Finance, reconcile & export", access: "Full" },
  ],
};

// Just enough of each screen's own read for it to render its real body rather
// than an A18 §3 skeleton — the data itself belongs to those screens' suites.
const COMPANY: CompanyProfile = {
  legal_name: null,
  // CR-060 C7 — the server serves both on every read; `utility` is the seed.
  organisation_type: "utility",
  organisation_types: ["utility", "sub_metering", "hoa"],
  dba_name: null,
  ein: null,
  state_utility_id: null,
  mailing_address: null,
  support_phone: null,
  support_email: null,
  website: null,
  logo_file_id: null,
  logo: null,
  has_logo: false,
  logo_ref: null,
  mark: { letters: "", background_hex: null, ink_hex: null, contrast_ratio: null },
  brand_primary_hex: null,
  brand_accent_hex: null,
  remit_to_address: null,
  remit_payable_to: null,
  service_hours: null,
};

const REGIONAL: RegionalSettings = {
  country: "United States",
  state: "TX",
  timezone: "America/Chicago",
  language: "en-US",
  first_day_of_week: "sunday",
  currency: "USD",
  number_format: "1,234.56",
  date_format: "MM/DD/YYYY",
  time_format: "12-hour",
  fy_start_month: 10,
  fy_start_day: 1,
  accounting_method: "accrual",
  close_cadence: "monthly",
  close_day: "3rd business day",
  lock_closed_periods: true,
  current_period: null,
};

// Both targets the S62 checklist deep-links into Settings, as the SERVER sends
// them (apps/tenancy/selectors.py CHECKLIST_TARGETS): `fiscal_billing` still
// points at the pre-nesting `settings/regional`, so that URL has to keep
// working — the frontend cannot rewrite the server's fragment.
const CHECKLIST: Checklist = {
  items: [
    {
      item: "company_profile",
      kind: "computed",
      done: false,
      source: null,
      target: "settings/company",
    },
    {
      item: "fiscal_billing",
      kind: "computed",
      done: false,
      source: null,
      target: "settings/regional",
    },
  ],
  progress: { done: 0, total: 2 },
  complete: false,
};

/** The REAL route table, mounted on a memory history — no browser needed. */
function RoutedApp() {
  return useRoutes(APP_ROUTES);
}

function renderAt(url: string): string {
  const queryClient = new QueryClient({
    // Nothing may fetch: this suite is about ROUTING, so every read is seeded
    // and a query that has no seed renders its honest loading state.
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  queryClient.setQueryData(queryKeys.me, DANA);
  queryClient.setQueryData(queryKeys.myPermissions, ADMIN_PERMISSIONS);
  queryClient.setQueryData(queryKeys.companyProfile, COMPANY);
  queryClient.setQueryData(queryKeys.regionalSettings, REGIONAL);
  // DEF-SHL-4272 — the app shell boots on `GET /shell/display`, not on the two
  // Admin/Executive settings reads. Both are still seeded above because the
  // SETTINGS SCREENS this suite deep-links into read them; this is the shell's
  // own key, and without it every routed screen below renders the shell's
  // loading skeleton instead of the screen.
  queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(REGIONAL));
  queryClient.setQueryData(queryKeys.checklist, CHECKLIST);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[url]}>
          <RoutedApp />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("path tenancy — the URL shape (PO ruling 2026-08-10)", () => {
  it("the tenant IS the first path segment, and the public surface has none", () => {
    expect(tenantFromPathname("/brazosbend/settings/company")).toBe("brazosbend");
    expect(tenantFromPathname("/brazosbend")).toBe("brazosbend");
    expect(tenantFromPathname("/lonestar/signin")).toBe("lonestar");
    // The public surface: root and the three reserved segments.
    expect(tenantFromPathname("/")).toBe("");
    expect(tenantFromPathname("")).toBe("");
    for (const segment of PUBLIC_SEGMENTS) {
      expect(tenantFromPathname(`/${segment}`)).toBe("");
      expect(tenantFromPathname(`/${segment}/anything`)).toBe("");
    }
  });

  it("tenantPath is the ONE builder: relative segment in, real URL out", () => {
    expect(tenantPathFrom(TENANT, "/settings/company")).toBe("/brazosbend/settings/company");
    expect(tenantPathFrom(OTHER, "/settings/company")).toBe("/lonestar/settings/company");
    // A query string rides along untouched (list screens link with filters).
    expect(tenantPathFrom(TENANT, "/premises/units?f.premises_id=p-101")).toBe(
      "/brazosbend/premises/units?f.premises_id=p-101",
    );
    // With no tenant in scope the segment comes back as-is — the helper never
    // invents a tenant to fill the gap.
    expect(tenantPathFrom("", "/dashboard")).toBe("/dashboard");
    // …and `withinTenant` is its exact inverse, which is what lets the nav and
    // breadcrumb config stay written once, tenant-relative.
    expect(withinTenant("/brazosbend/settings/company")).toBe("/settings/company");
    expect(withinTenant("/brazosbend")).toBe("/");
    expect(withinTenant("/signup")).toBe("/signup");
    for (const path of ["/dashboard", "/premises/units", "/plans-rates/rates"]) {
      expect(withinTenant(tenantPathFrom(TENANT, path))).toBe(path);
    }
  });

  it("the API mirrors it: /api/{tenant}/… for tenant work, /api/… for the rest", () => {
    expect(apiPath(TENANT, "/settings/company")).toBe("/api/brazosbend/settings/company");
    expect(apiPath(TENANT, `${SIGNIN_SEGMENT}`)).toBe("/api/brazosbend/signin");
    expect(apiPath(TENANT, "/public/pricing-plans")).toBe("/api/public/pricing-plans");
    expect(apiPath("", "/tenants")).toBe("/api/tenants");
  });
});

describe("path tenancy — deep links and navigation", () => {
  it("a deep link to /brazosbend/settings/company renders S8 Company with the tenant in scope", () => {
    const html = renderAt(`/${TENANT}/settings/company`);
    // The screen itself, inside the shell (not the W0 placeholder, not a 404):
    // S8's frame, with the Company tab selected and its BODY rendered.
    expect(html).toContain('class="app-shell"');
    expect(html).toContain('class="settings-tabs"');
    expect(html).toContain("Utility details"); // the Company tab's own panel
    expect(html).toContain('aria-selected="true"');
    expect(html).not.toContain("data-not-built-yet"); // DEF-152: the catch-all, by its marker
    // The tenant is in scope for everything the frame draws around it: this is
    // what "survives a refresh" means — the URL alone carries the tenant, so a
    // pasted link reconstructs the whole context.
    expect(html).toContain('href="/brazosbend/settings"');
    expect(html).toContain('href="/brazosbend/dashboard"');
    expect(html).not.toContain('href="/settings"');
    expect(html).not.toContain('href="/dashboard"');
    // The breadcrumb resolves from the tenant-relative path — it says Settings,
    // not "brazosbend".
    expect(html).toContain('<span class="cur">Settings</span>');
  });

  it("Company's SUB-tab is a deep link too: /settings/company/regional renders Regional", () => {
    // The prototype nests "Regional, formats & fiscal calendar" inside Company;
    // nesting it must not cost it its own URL. This goes through the REAL route
    // table, so it proves `settings/:tab/:sub` is wired, not just resolvable.
    const html = renderAt(`/${TENANT}/settings/company/regional`);
    expect(html).toContain('class="app-shell"');
    expect(html).toContain("Regional, formats &amp; fiscal calendar");
    expect(html).toContain("Location &amp; language"); // the Regional panel itself
    expect(html).not.toContain("data-not-built-yet"); // DEF-152: the catch-all, by its marker
    expect(html).toContain('<span class="cur">Settings</span>');
  });

  it("the checklist's own `settings/regional` fragment still points at a routed screen", () => {
    // The S62 link is built from the SERVER's fragment; it must not 404 or land
    // on the W0 marker. The route it hits is a redirect, and a <Navigate>
    // renders nothing — so what is proven here is that the URL is claimed by a
    // real route rather than falling through to `*`.
    const html = renderAt(`/${TENANT}/checklist`);
    expect(html).toContain('href="/brazosbend/settings/regional"');
    expect(renderAt(`/${TENANT}/settings/regional`)).not.toContain("data-not-built-yet");
  });

  it("the SAME deep link under another tenant renders the same screen, pointing everywhere else", () => {
    const html = renderAt(`/${OTHER}/settings/company`);
    expect(html).toContain("Utility details");
    expect(html).toContain('href="/lonestar/settings"');
    expect(html).not.toContain("/brazosbend/");
  });

  it("every internal link on a rendered screen keeps the tenant segment", () => {
    // The whole surface, not a sampled link: any href that leaves the tenant
    // (or forgets it) fails here.
    for (const url of [
      `/${TENANT}/dashboard`,
      `/${TENANT}/settings/company`,
      `/${TENANT}/checklist`,
    ]) {
      const all = [...renderAt(url).matchAll(/href="([^"]*)"/g)].map((m) => m[1]);
      // AMENDED 2026-08-21 (DEF-450). The top bar gained r10's help control and
      // it points OUT of the product, so it is the one href in the frame that
      // must NOT carry a tenant segment. It is excluded EXPLICITLY — exactly
      // one, and absolute — rather than by loosening the assertion below, which
      // would then also pass on an internal link that had quietly lost its
      // tenant. That is the whole thing this TC exists to catch.
      //
      // ⚠ **AMENDED AGAIN 2026-10-02: ZERO, NOT ONE — RED SINCE 2026-09-29
      // (`3c818324f`, `DEF-SHL-7825`).** That help href went to another
      // company's product documentation; `HELP_ROUTE` is now `null` and the
      // control is disabled with its reason until `OQ-307` is answered, so the
      // frame draws NO external link at all. `AppShell.test.tsx`'s BR-SHL-001
      // case deleted its own carve-out the same day and asserts zero; this is
      // the same rule, made to agree with it. The day a help destination
      // exists this goes red again, deliberately.
      const external = all.filter((href) => href.startsWith("http"));
      expect(external, `on ${url}`).toHaveLength(0);
      const hrefs = all.filter((href) => !href.startsWith("http"));
      expect(hrefs.length).toBeGreaterThan(0);
      for (const href of hrefs) {
        expect(href.startsWith(`/${TENANT}/`), `${href} on ${url}`).toBe(true);
      }
    }
  });

  it("the tenant's root lands on the Dashboard inside the tenant, never at the app root", () => {
    const html = renderAt(`/${TENANT}`);
    // A <Navigate> renders nothing, so what is proven here is that the redirect
    // target is tenant-relative: the shell it lands in is the tenant's.
    expect(html).not.toContain('href="/dashboard"');
    expect(tenantPathFrom(TENANT, "/dashboard")).toBe("/brazosbend/dashboard");
  });

  it("the public surface stays at the root and is NOT wrapped in the shell", () => {
    const pricing = renderAt("/");
    expect(pricing).toContain('data-public-page="pricing"'); // CR-018: the class became utilities
    expect(pricing).not.toContain('class="app-shell"');
    const signup = renderAt("/signup");
    expect(signup).toContain('data-signup="page"'); // CR-018: the class became utilities
    expect(signup).not.toContain('class="app-shell"');
    // Sign-in is per-tenant and also outside the shell — there is no session yet.
    const signin = renderAt(`/${TENANT}${SIGNIN_SEGMENT}`);
    // CR-018 Route B: the handle is `data-page="signin"` now — the class name
    // it grepped for was deleted with SignInPage.css.
    expect(signin).toContain('data-page="signin"');
    expect(signin).not.toContain('class="app-shell"');
    expect(signin).toContain("Signing in to brazosbend");
  });
});

describe("path tenancy — signup ends INSIDE the new tenant (BR-TEN-045 obsolete)", () => {
  it("the S114 commit's destination is /{tenant}/checklist, and that route renders S62", () => {
    const destination = tenantPathFrom(TENANT, CHECKLIST_SEGMENT);
    expect(destination).toBe("/brazosbend/checklist");
    const html = renderAt(destination);
    // CR-018 Route B: the handle is `data-page="checklist"` now.
    expect(html).toContain('data-page="checklist"');
    expect(html).toContain('class="app-shell"'); // signed in, inside the frame
  });

  it("no cross-host link exists anywhere on the signup surface", () => {
    const html = renderAt("/signup");
    expect(html).not.toContain("http://");
    expect(html).not.toContain("https://");
    expect(html).not.toContain("smartbillhub.app");
    // The copy that used to send the owner to another address is gone from
    // EVERY catalog, not merely unrendered. The loop reads LOCALE_CODES rather
    // than a written-out five (2026-08-11, eleven-locale lane) so a catalogue
    // added tomorrow is covered the day it lands.
    for (const language of LOCALE_CODES) {
      expect(
        i18n.getResource(language, "translation", "tenancy.signup.success.go"),
      ).toBeUndefined();
    }
  });
});

describe("path tenancy — a foreign tenant's path is an ORDINARY 404", () => {
  // The session is bound to its tenant server-side; presenting it on another
  // tenant's path answers 404 (never 403, which would confirm the tenant
  // exists). The UI renders that like any other not-found: it must not offer to
  // switch tenant, and it must not redirect to the session's own path.
  const NOT_FOUND = {
    code: null,
    message_key: "api.error.unexpected",
    params: {},
    field_errors: [],
    br_ref: null,
    trace_id: "7c1f",
  };

  function foreignTenantClient() {
    const urls: string[] = [];
    const client = createApiClient({
      // The URL the browser is on: Dana's session belongs to brazosbend, but
      // the path says lonestar. The client sends exactly what the path says —
      // it does not "correct" the request to the session's own tenant.
      tenant: OTHER,
      fetchImpl: async (input: RequestInfo | URL) => {
        urls.push(String(input));
        return new Response(JSON.stringify(NOT_FOUND), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        });
      },
      sleep: () => Promise.resolve(),
    });
    return { client, urls };
  }

  it("the request goes to the path's tenant — the client never rewrites it", async () => {
    const { client, urls } = foreignTenantClient();
    await getCompanyProfile(client).catch(() => undefined);
    expect(urls).toEqual(["/api/lonestar/settings/company"]);
  });

  it("the screen renders the ordinary failed state — no 'switch tenant', no redirect", async () => {
    const { client } = foreignTenantClient();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    // The read failed, so there is no data — exactly what a 404 leaves behind.
    // (The tab renders from cache in its own suite; here the cache is empty.)
    await queryClient
      .fetchQuery({ queryKey: queryKeys.companyProfile, queryFn: () => getCompanyProfile(client) })
      .catch(() => undefined);

    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${OTHER}/settings/company`]}>
            <CompanyTab readOnly={false} client={client} />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );

    // A18's shared failed/loading state — the SAME thing an unknown id or a
    // dropped connection renders. Nothing about tenants appears.
    expect(html).toMatch(/state-failed|skeleton/);
    for (const forbidden of [
      "switch tenant",
      "Switch tenant",
      "another utility",
      "brazosbend", // never names the session's own tenant as an alternative
    ]) {
      expect(html).not.toContain(forbidden);
    }
    // …and no data leaked from the tenant the session DOES belong to.
    expect(html).not.toContain("Brazos Bend");
  });

  it("a 404 is a 404: the app has no code that turns one into a tenant switch", () => {
    // Structural, so it cannot rot: the ONE URL builder takes a tenant and a
    // segment, and there is no path through it that swaps one tenant for
    // another. A screen can only ever build a link inside the tenant it is in.
    expect(tenantPathFrom(OTHER, "/settings/company")).toBe("/lonestar/settings/company");
    expect(tenantFromPathname("/lonestar/settings/company")).toBe(OTHER);
    expect(withinTenant("/lonestar/settings/company")).toBe("/settings/company");
  });

  it.todo(
    "server scope (the ruling's acceptance criterion): a brazosbend session presenting on /api/lonestar/… is answered 404, not 403 and not a switch — the concurrent backend lane's isolation suite (G5)",
  );
  it.todo(
    "browser scope → Playwright journey: paste a foreign tenant's deep link with a live session; the not-found state renders and the address bar does NOT change",
  );
});

describe("DEF-112 — the four Finance tabs resolve to a screen, not to a placeholder", () => {
  // The defect was measured in a browser: Finance → Export to accounting
  // rendered "Handing the period to an accounting package arrives with the
  // export-batch story. No file is written yet." and **zero of the five
  // checklist items appeared**, while `close_checklist`, `close_period`,
  // `reopen_period` and the export batch with its four gates were all built,
  // unit-tested and correct.
  //
  // This is the SPA half of "built is not wired", asserted on the REAL route
  // table. **What is asserted is the tab's own EXPLAINER**, not its tab LABEL:
  // the label sits in the five-tab strip that every Finance screen renders, so
  // an assertion on it passes even when `/finance/gl` falls through to the
  // catch-all — which is exactly the state this defect describes. It was tried
  // that way first and did NOT go red when the three routes were deleted. The
  // explainer is rendered only by the ACTIVE tab's own screen, so it is the
  // string that distinguishes "the route reaches this screen" from "the route
  // reaches the Finance page".
  //
  // ⚠ **`/finance/export`'s ANCHOR IS NO LONGER ITS EXPLAINER, AND THAT IS
  // `DEF-LED-6655` (red 2026-09-24 → 2026-09-25).** `P5.9` set
  // `explainer=""` on `CloseExportPage` DELIBERATELY — the paragraph was 28
  // words of RATIONALE and B14 rule 33 puts rationale at ZERO words on screen —
  // and this case went on asserting the deleted sentence. **The screen was
  // never broken:** the route resolves, the breadcrumb reads "Close & export"
  // and the placeholder is absent, so the guard's own second assertion was
  // green throughout while its first one failed. A test that fails for the
  // reason its subject was CORRECTLY changed is hard-won law 7's *looking at
  // the wrong thing*, and it is why this red was filed three times, by three
  // lanes, with three different invented causes (`DEF-REP-6528`,
  // `DEF-GOV-6604`, and this row).
  //
  // ⚠ **THE REPLACEMENT IS DELIBERATELY NOT COPY.** Copy is what rotted, and
  // it will rot again the next time rule 33 is counted over a screen. The tab
  // strip's own selected state is STRUCTURE: `CloseExportPage` renders
  // `FinanceHeader activeTab={…FINANCE_TAB_EXPORT}`, so the pair
  // `data-tab="export"` + `aria-selected="true"` appears only when THIS screen
  // drew the strip. **PROVED RED BOTH WAYS before it was trusted green**
  // (law 7): pointing the route at `GeneralLedgerPage` fails it — the strip
  // renders but Export is `aria-selected="false"` — and deleting the route
  // fails the placeholder assertion below. The sibling `not.toContain` lines
  // are unchanged and still carry the DEF-112 guard.
  const TABS: [string, string][] = [
    ["/finance/gl", "Read-only trial balance for the period"],
    ["/finance/taxes", "Tax you billed and tax you collected for each authority"],
    ["/finance/export", 'data-tab="export" aria-selected="true"'],
  ];

  it.each(TABS)("a deep link to %s reaches the screen that owns it", (path, explainer) => {
    const html = renderAt(`/${TENANT}${path}`);
    expect(html).toContain(explainer);
    // ModulePlaceholder is the other thing these paths could fall through to.
    expect(html).not.toContain("This module arrives in a later wave");
  });

  it("the deposits tab reaches S37 — it stopped saying 'arrives with' on 2026-08-16", () => {
    // ⚠ AMENDED 2026-08-16 (returned-mail lane). This case used to assert the
    // OPPOSITE — that `/finance/deposits` still rendered
    // `finance.arrives.deposits`, *"Deposits and bank reconciliation arrive with
    // their own stories"* — and it was right when written: EP-PAY-06 had no
    // screen. **US-PAY-020/022 built S37 that morning** (`DepositsPage`, routed
    // in `App.tsx` above `deposits/:batchId`), so the sentence it asserted is
    // no longer rendered anywhere and the case went red for the best possible
    // reason: the placeholder it was guarding got paid off.
    //
    // It is amended rather than deleted, because the fifth Finance tab still
    // needs the same proof its three siblings get — the tab's OWN explainer,
    // never its tab LABEL, which every Finance screen renders in the strip and
    // which therefore passes on a route that reached the wrong screen.
    const html = renderAt(`/${TENANT}/finance/deposits`);
    expect(html).toContain("Each day&#x27;s payments grouped into a deposit");
    expect(html).not.toContain("Deposits and bank reconciliation arrive with their own stories");
    expect(html).not.toContain("This module arrives in a later wave");
    expect(html).not.toContain("data-not-built-yet"); // DEF-152: the catch-all, by its marker
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-001@b16a4de (story+rules snapshot hash — the shell owns the app's URL shape; co-packets US-TEN-001@d5f8c32, US-IDN-001@402b6db, US-TEN-003@d5f8c32)
// generated: 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10) · AMENDED 2026-08-10 by story-coder v1 (Settings → Company sub-tab lane: `settings/:tab/:sub` and the `settings/regional` redirect are routing contracts, so the two deep-link tests live in this suite; the S62 fixture now carries BOTH Settings targets the server sends)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest✔ · 2026-08-10 Company sub-tab re-run: tsc✔ eslint✔ vitest 604 passed / 142 todo across 46 files✔ (593 + 141 across 46 was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 13 PASS · 0 FAIL · 1 SKIP
// exceptions: E4 the 404 acceptance criterion is only half-provable here — the FE half (the request goes to the path's tenant, the refusal renders as the ordinary state, nothing offers a switch) is tested; the SERVER half (404 rather than 403) is the concurrent backend lane's, recorded as an it.todo rather than faked with a stub that would prove nothing · E4 the `settings/regional` redirect is asserted as "the URL is claimed by a real route, not the `*` marker": a <Navigate> renders nothing under renderToStaticMarkup (no effects, no jsdom in this project), so the address-bar half is an it.todo in SettingsPage.test.tsx for Playwright
// amended:   2026-08-15 by story-coder (DEF-112 lane) — a DEF-112 block: a deep link to each of the three new Finance tabs must reach the SCREEN that owns it. It asserts the tab's own EXPLAINER and not its tab LABEL, because the label sits in the five-tab strip every Finance screen renders and an assertion on it did NOT go red when the three routes were deleted — the exact state the defect describes. `ADMIN_PERMISSIONS` gained A4's `finance_reconcile_export` cell so the access decision is not what this routing suite measures. RED-PROVED with the three routes removed: three failures, `expected '<div class="app-shell">…' to contain 'Read-only trial balance for the period'` and its two siblings.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
