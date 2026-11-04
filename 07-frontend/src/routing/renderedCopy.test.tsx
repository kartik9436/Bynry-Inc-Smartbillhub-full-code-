// ── Trace ──────────────────────────────────────────────
// Defects: DEF-FE-4058 (`billing.budget.filter.` printed its own dotted key as
//          the two filter buttons AND as every Status pill on S30's Budget
//          Bills tab, in all eleven languages) · DEF-LED-4638 (`/finance/revenue`
//          rendered an arrives-with panel headed *General ledger* whose message
//          was the raw key `finance.arrives.gl`, so the whole of S36 was
//          invisible and the strip highlighted the wrong tab) ·
//          DEF-CUS-4624 (the instrument: a screen-reader label that had always
//          ended `usage in {{unit}}`, which no amount of looking finds)
// Rules:   CLAUDE.md hard-won law 6 (no gate reads rendered output — this is
//          the nearest a test can get) · law 2's fixture clause (mount a routed
//          component under its REAL path pattern, or the one assertion that
//          could catch the bug cannot be written) · law 7 (proved RED first;
//          and "what would make this check pass WRONGLY") · B14 rule 32 (no
//          internal code in clerk-facing copy)
// ───────────────────────────────────────────────────────
/**
 * NO CLERK EVER READS AN INTERNAL NAME — asserted against the RENDERED PAGE.
 *
 * WHY THIS FILE EXISTS AND WHY IT IS NOT A GATE
 * ---------------------------------------------
 * `G112` asks whether a computed key's PREFIX names a family the catalogue
 * has. `G15` compares the eleven catalogues to each other. `G18` reads literal
 * keys. All three read TEXT, and CLAUDE.md hard-won law 6 says the thing none
 * of them does is look at rendered output — which is why the Product Owner has
 * been finding these on screen and we have not.
 *
 * This file renders the REAL route table on a memory history and asks two
 * questions of the markup that comes out:
 *
 *   1. does any token in it look like a catalogue key — a real top-level
 *      namespace of `en.json` followed by a dotted segment?
 *   2. does any `{{placeholder}}` survive into the page?
 *
 * (2) is the instrument that found `DEF-CUS-4624`, a chart's `aria-label`
 * spoken only to a screen reader. Nobody was ever going to see that by looking.
 *
 * ⚠ **THE ASSERTIONS BELOW NAME THE ENGLISH LITERAL AND NEVER `t(key)`.** Four
 * of the six faults on the Usage tab were invisible because their test put
 * `t(key, args)` on BOTH sides of a `toContain`: such a test takes the same
 * wrong value twice and can only prove the code agrees with itself. A raw key
 * satisfies it perfectly. So the expected strings here are typed out in
 * English, and they go red when the copy changes — which is the point, not a
 * maintenance cost.
 *
 * ⚠ **AND THE SWEEP CANNOT COVER WHAT IT CANNOT MOUNT, SO IT PRINTS ITS OWN
 * SCOPE** (law 7's "a declared blind spot with no NUMBER attached is
 * indistinguishable from an empty one"). It renders the routes in `SWEPT` and
 * nothing else; every read is seeded or disabled, so a screen's *loading* and
 * *empty* states are what gets swept, not its populated one. Adding a route is
 * one line and is the cheapest way to extend the only rendered-output check in
 * this repo.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, useRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
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
import enCatalogue from "@/i18n/locales/en.json";
import { internalReferencesInMarkup } from "@/testSupport/internalReferences";

const TENANT = "brazosbend";

const DANA: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@brazosbend.example",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

/** A4's cells for the two areas this file sweeps. Without them `useAccessCell`
 *  denies and the sweep would "pass" over A18 §6's denied frame — a screen it
 *  never reached. That is the false pass this seed exists to prevent. */
const ADMIN_PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [
    { code: "settings_lookups", label: "Settings & lookup tables", access: "Full" },
    { code: "user_management", label: "User management", access: "Full" },
    { code: "finance_reconcile_export", label: "Finance, reconcile & export", access: "Full" },
    { code: "reads_billing_runs", label: "Reads & billing runs", access: "Full" },
  ],
};

const COMPANY = {
  legal_name: null,
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
  mark: { letters: "", background_hex: null, ink_hex: null, contrast_ratio: null },
  brand_primary_hex: null,
  brand_accent_hex: null,
  remit_to_address: null,
  remit_payable_to: null,
  service_hours: null,
} as unknown as CompanyProfile;

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

const CHECKLIST: Checklist = { items: [], progress: { done: 0, total: 0 }, complete: false };

function RoutedApp() {
  return useRoutes(APP_ROUTES);
}

/** The REAL route table on a memory history. ⚠ Law 2's fixture clause: the
 *  component is mounted at its OWN address under the `/:tenant` pattern, never
 *  bare — `DEF-LED-4638` is precisely a screen reading a route param its route
 *  does not declare, and a bare mount cannot see that. */
function renderAt(url: string): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  queryClient.setQueryData(queryKeys.me, DANA);
  queryClient.setQueryData(queryKeys.myPermissions, ADMIN_PERMISSIONS);
  queryClient.setQueryData(queryKeys.companyProfile, COMPANY);
  queryClient.setQueryData(queryKeys.regionalSettings, REGIONAL);
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

/** ⚠ `en.json` is FLAT — 14,380 fully-dotted keys — so the namespaces are the
 *  first segment of each key and NOT `Object.keys`. The first draft of this
 *  helper used `Object.keys`, which made the alternation a list of complete
 *  keys, required a further dotted segment after one, and therefore matched
 *  NOTHING: it reported a clean sweep over three raw keys it was looking
 *  straight at. That is law 7's "structurally incapable of failing", authored
 *  and caught inside ten minutes, and it is why the fixtures below assert the
 *  helper BITES before any screen is trusted to be clean. */
const NAMESPACES = [
  ...new Set(Object.keys(enCatalogue as Record<string, unknown>).map((key) => key.split(".")[0])),
];

function rawCatalogueKeys(html: string): string[] {
  const pattern = new RegExp(`\\b(?:${NAMESPACES.join("|")})(?:\\.[A-Za-z0-9_-]+)+`, "g");
  return [...new Set(html.match(pattern) ?? [])];
}

function survivingPlaceholders(html: string): string[] {
  return [...new Set(html.match(/\{\{[^}]*\}\}/g) ?? [])];
}

describe("the two helpers BITE — proved before any screen is called clean", () => {
  it("a raw key in the markup is found", () => {
    expect(rawCatalogueKeys('<p>finance.arrives.gl</p>')).toEqual(["finance.arrives.gl"]);
    expect(rawCatalogueKeys('<span>billing.budget.filter.off_budget</span>')).toEqual([
      "billing.budget.filter.off_budget",
    ]);
  });

  it("an ordinary English sentence is not", () => {
    expect(rawCatalogueKeys("<p>On budget billing. Taken off. 1,234.56</p>")).toEqual([]);
  });

  it("an unfilled placeholder is found — the DEF-CUS-4624 instrument", () => {
    expect(survivingPlaceholders('<img alt="usage in {{unit}}">')).toEqual(["{{unit}}"]);
    expect(survivingPlaceholders("<p>21 month(s) have no reading</p>")).toEqual([]);
  });
});

// ── DEF-LED-4638 · S36 Revenue & AR is the screen at its own address ────────
describe("DEF-LED-4638 — /finance/revenue renders Revenue & AR, not General ledger", () => {
  const html = renderAt(`/${TENANT}/finance/revenue`);

  it("the Revenue & AR tab is the SELECTED one in the strip", () => {
    // By ADDRESS and by tab id, never by label: every Finance screen draws the
    // whole strip, so an assertion on the label passes on a route that reached
    // the wrong screen (the DEF-112 lesson, one screen over).
    expect(html).toContain('data-tab="revenue" aria-selected="true"');
    expect(html).toContain('data-tab="gl" aria-selected="false"');
  });

  it("it does not render the General ledger arrives-with panel", () => {
    // The exact rendered heading before the fix. `financeTabFrom(undefined)`
    // returned the landing tab, so this screen announced a different one.
    expect(html).not.toContain("<h3>General ledger</h3>");
  });

  it("no `finance.arrives.` key reaches the page", () => {
    expect(rawCatalogueKeys(html)).toEqual([]);
  });
});

// ── DEF-FE-4058 · S30 Budget Bills says its two states in English ──────────
describe("DEF-FE-4058 — the budget-bills filter and Status pill read as sentences", () => {
  const html = renderAt(`/${TENANT}/billing/budget`);

  it("both filter buttons carry ENGLISH, typed out here and not translated", () => {
    // The two values are not a guess and not what one call site passes:
    // `apps/billing/budget.py` declares STATUSES = (enrolled, off_budget) and
    // `GET /budget-billing` serves that tuple back as `statuses` on every read.
    expect(html).toContain("On budget billing");
    expect(html).toContain("Taken off");
  });

  it("no `billing.budget.filter.` key reaches the page", () => {
    expect(rawCatalogueKeys(html)).toEqual([]);
  });
});

// ── The sweep ──────────────────────────────────────────────────────────────
/** Every route this file mounts. It is the SCOPE of the check and it is
 *  printed rather than implied — a check that cannot cover its whole subject
 *  must say what it skipped beside what it checked (law 7). */
const SWEPT = [
  "/finance",
  "/finance/gl",
  "/finance/revenue",
  "/finance/deposits",
  "/finance/taxes",
  "/finance/cost-of-service",
  "/finance/export",
  // `/finance/write-offs` was swept here until CR-135 P1.10 deleted the route:
  // the queue is `WriteOffQueuePanel` inside `/finance/revenue`, which this
  // sweep already covers.
  "/finance/refunds",
  "/finance/nonsense-tab",
  "/billing",
  "/billing/budget",
  "/billing/fix",
  "/billing/one-time",
];

describe(`no internal name reaches a clerk — ${SWEPT.length} routes swept`, () => {
  it.each(SWEPT)("%s renders no raw catalogue key", (path) => {
    expect(rawCatalogueKeys(renderAt(`/${TENANT}${path}`))).toEqual([]);
  });

  it.each(SWEPT)("%s renders no unfilled {{placeholder}}", (path) => {
    expect(survivingPlaceholders(renderAt(`/${TENANT}${path}`))).toEqual([]);
  });

  // The THIRD question, added 2026-09-15 (`DEF-BIL-5339`): does any rule id,
  // open-question id, defect id or dotted Python identifier reach the page as
  // text or as a tooltip? The two above ask about a KEY that failed to resolve;
  // this asks about a VALUE that resolved to the wrong kind of sentence — the
  // Budget Bills tab printed `BR-RAT-043`, `OQ-237`, `OQ-142`,
  // `budget_service.enroll` and `budget.settle_up_gl_account` for four weeks
  // with both questions above green. ⚠ This sweep seeds no list data, so it
  // reads each route's loading/empty state; `budgetBillsClerkCopy.dom.test.tsx`
  // asks the same helper the same question of the POPULATED tab.
  it.each(SWEPT)("%s renders no rule id, question id or Python identifier", (path) => {
    expect(internalReferencesInMarkup(renderAt(`/${TENANT}${path}`))).toEqual([]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-FE-4058 (G112's park file, its last two prefixes) + DEF-LED-4638 (what one of them turned out to be) + B14 rules 32/35 + CLAUDE.md hard-won laws 2, 6, 7
// generated: 2026-09-08 by the raw-key lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST, at the pinned tip b768513e and through vitest itself — 7 failures: `expected [ 'finance.arrives.gl' ] to deeply equal []` (twice, once per describe), `expected '<div class="app-shell">…' to contain 'data-tab="revenue" aria-selected="tru…'`, `expected … not to contain '<h3>General ledger</h3>'`, `expected … to contain 'Taken off'`, and the two budget keys through the sweep. Then green on the fix: 36 passed. tsc✔ · eslint --max-warnings 0✔ · G112 PASS (0 raw families, 0 parked) · G15/G18/G17/G106/G116/G02 red BEFORE and AFTER with byte-identical detail (diffed, not asserted) · browser walkthrough 10-scripts/render-checks/def-fe-4058-two-raw-keys.mjs 8/8✔
// exceptions: E3 the sweep renders each screen's LOADING/EMPTY state — every query is seeded or disabled, so a populated table's copy is not covered here and the browser walkthrough is what covers it · E3 the three helper fixtures at the top exist because the FIRST draft of `rawCatalogueKeys` used `Object.keys(en.json)` as the namespace list, which (the catalogue being FLAT) made the alternation a list of whole keys and matched NOTHING — it reported a clean sweep over three raw keys it was looking straight at, and only asserting that the helper BITES could have caught it · E3 `renderToStaticMarkup` runs no effects, so anything a screen fills in after mount is outside this file's reach
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
