// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-009 (EP-TEN-07 — the S8 frame the whole Settings lane lives in) ·
//           US-IDN-008 (GET /me/permissions — the caller's own A4 row)  Screens: S8
// Rules:    BR-SHL-003 (an unreachable surface is not drawn) · BR-SHL-025 (gating from the SERVER's
//           permission set) · BR-IDN-009 (Settings is System Admin; Executive views) ·
//           BR-SHL-011 (an unknown URL value falls back, never errors)
// ───────────────────────────────────────────────────────
// The frame's laws, proved through its exported pure pieces plus static markup.
// The heart of it: no test here asserts "role X sees tab Y" from a role NAME —
// every expectation is driven by a permission GRID the server supplies, which
// is exactly what BR-SHL-025 requires of the code.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes, matchRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import type {
  CompanyProfile,
  MyPermissions,
  RegionalSettings,
  RolesMatrix,
  SessionUser,
  TenantServiceRow,
} from "@/api/endpoints";
import { api } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import {
  CELL_FULL,
  CELL_NONE,
  CELL_VIEW,
  COMPANY_SUB_TABS,
  CONFIGURE_SUB_TABS,
  CONFIGURE_TAB,
  DEFAULT_COMPANY_SUB_TAB,
  DEFAULT_SETTINGS_TAB,
  LEGACY_SETTINGS_TAB_PATHS,
  SETTINGS_TABS,
  SettingsPage,
  SettingsTabBody,
  accessFromPermissions,
  companySubTabFromParam,
  configureSubTabFromParam,
  legacySettingsPath,
  resolveSettingsAccess,
  settingsTabFromParam,
  tabIsReadOnly,
  visibleSettingsTabs,
} from "./SettingsPage";
import type { SettingsTab } from "./SettingsPage";

// The server's own A4 grid (identity models.A4_MATRIX), as `GET /roles` serves it.
const MATRIX: RolesMatrix = {
  roles: [
    { code: "system_admin", name: "System Admin" },
    { code: "billing_clerk", name: "Billing Clerk" },
    { code: "executive", name: "Executive" },
  ],
  permissions: [
    {
      code: "settings_lookups",
      label: "Settings & lookup tables",
      cells: { system_admin: "Full", executive: "View" },
    },
    { code: "user_management", label: "User management", cells: { system_admin: "Full" } },
  ],
};

function member(role: string): SessionUser {
  return {
    id: "u1",
    full_name: "Dana Whitfield",
    email: "dana@brazosbend.example",
    phone: null,
    role,
    role_name: role,
    must_change_password: false,
  };
}

// `GET /me/permissions` — the caller's OWN row of that same grid, which is the
// read this frame actually gates on. Any tenant role may make it, which is why
// it replaced the probe-a-tab-and-read-the-403 behaviour.
const PERMISSIONS: Record<string, MyPermissions> = {
  system_admin: {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [
      { code: "settings_lookups", label: "Settings & lookup tables", access: "Full" },
      { code: "user_management", label: "User management", access: "Full" },
    ],
  },
  executive: {
    role: "executive",
    role_name: "Executive",
    permissions: [
      { code: "settings_lookups", label: "Settings & lookup tables", access: "View" },
      { code: "user_management", label: "User management", access: "—" },
    ],
  },
  billing_clerk: {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [
      { code: "settings_lookups", label: "Settings & lookup tables", access: "—" },
      { code: "user_management", label: "User management", access: "—" },
    ],
  },
};

// Enough of the Company tab's own read to prove the frame's read-only verdict
// reaches a tab BODY — the frame passes it down, the body renders it.
const COMPANY: CompanyProfile = {
  legal_name: "Brazos Bend Utility District No. 1",
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

// US-TEN-006 §4 test data (Brazos Bend), enough for the Regional sub-tab to
// render its real panels instead of an A18 §3 skeleton.
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

// US-BIL-009 §4: one enabled service pointing at BR-BIL-067's own worked
// account (Silver Creek Water is seeded 4110 · 4115 · 4120 and nothing else).
const ACCOUNTING_SERVICES: TenantServiceRow[] = [
  {
    service: "water",
    name: "Water",
    enabled: true,
    primary_uom: "kgal",
    alt_uom: null,
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    revenue_account: { id: "acc-4110", code: "4110", name: "Water usage revenue" },
    base_revenue_account: { id: "acc-4115", code: "4115", name: "Water base revenue" },
    rate_schedules: 2,
    active_accounts: 568,
  },
];

/**
 * `tab` is the URL PATH under `/settings/` — "company" or "company/regional" —
 * because the Company tab now has a second level and both are linkable.
 */
function renderSettings(
  tab: string,
  me: SessionUser,
  matrix: RolesMatrix | null,
  permissions: MyPermissions | null = null,
  company: CompanyProfile | null = null,
  regional: RegionalSettings | null = null,
  // US-BIL-009: the Accounting tab's own read, seeded so the mounted BODY is
  // its real panels rather than the A18 §3 skeleton every unseeded tab shows.
  services: TenantServiceRow[] | null = null,
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.me, me);
  queryClient.setQueryData(queryKeys.rolesMatrix, matrix);
  queryClient.setQueryData(queryKeys.myPermissions, permissions);
  if (company !== null) {
    queryClient.setQueryData(queryKeys.companyProfile, company);
  }
  if (regional !== null) {
    queryClient.setQueryData(queryKeys.regionalSettings, regional);
  }
  if (services !== null) {
    queryClient.setQueryData(queryKeys.tenantServices, services);
  }
  // Every other tab body reads its own endpoint; nothing is seeded for them
  // here, so they render their A18 §3 skeleton. This suite is about the FRAME.
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* PO 2026-08-10: S8 lives at `/{tenant}/settings/:tab`; the Company
            tab's own strip adds `/:sub`, exactly as APP_ROUTES declares it. */}
        <MemoryRouter initialEntries={[`/brazosbend/settings/${tab}`]}>
          <Routes>
            <Route path="/:tenant/settings/:tab" element={<SettingsPage />} />
            <Route path="/:tenant/settings/:tab/:sub" element={<SettingsPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * The BODY alone, for a tab this suite makes up (DEF-INT-3632). The frame
 * reads `SETTINGS_TABS`, and no real tab declares `arrivesWithKey` any more,
 * so the honest-state mechanism is proved on a tab of the test's own.
 */
function renderTabBody(tab: SettingsTab): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/brazosbend/settings/${tab.id}`]}>
          <SettingsTabBody tab={tab} sub={undefined} readOnly={false} client={api} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Every label whose tab button is marked selected, outer strip first. */
function activeTabLabels(html: string): string[] {
  return [...html.matchAll(/<button[^>]*aria-selected="true"[^>]*>(.*?)<\/button>/g)].map(
    (match) => match[1],
  );
}

function tablistCount(html: string): number {
  return html.split('role="tablist"').length - 1;
}

describe("US-TEN-009 — the S8 Settings frame (tab order, RBAC gating, honest states)", () => {
  it("renders the A1 tab set in its ratified order, with Company first and Users & roles second (r7)", () => {
    const ids = SETTINGS_TABS.map((tab) => tab.id);
    // The prototype's own strip: Company, then Users & roles. Regional is NOT
    // one of them — it is Company's second SUB-tab (see the sub-tab suite).
    expect(ids.slice(0, 2)).toEqual(["company", "users"]);
    // CR-001 (PO 2026-08-11): `number-series` is NO LONGER a top-level tab —
    // it moved under Configure with Routes & Cycles and Templates, and eleven
    // tabs became eight. The checklist contract it used to satisfy here is
    // proved one suite down, where the redirect that keeps its URL alive is.
    for (const target of ["company", "services", "users"]) {
      expect(ids).toContain(target);
    }
    expect(ids).not.toContain("number-series");
    expect(ids).toContain(CONFIGURE_TAB);
    // S8 → Accounting, added 2026-08-11: the GL code mapping surface for
    // BR-BIL-067 / BR-BIL-069. NINE tabs, where CR-001 measured eight fitting
    // on one line and eleven wrapping — recorded here rather than left to be
    // discovered, and put to the PO as OQ-151.
    expect(ids).toContain("accounting");
    // 2026-10-22: Notifications left the top row for Configure (PO: *"Settings
    // → Configure → Notifications, sitting next to Templates"*) — EIGHT.
    expect(ids).not.toContain("notifications");
    expect(ids).toHaveLength(8);
    // CR-001 is NOT eroded by that addition: Configure still carries exactly
    // the four children the PO named, and Accounting is not a fifth.
    // CR-068 wave A (2026-09-03): a FIFTH segment, the portal's back office —
    // deliberately a Configure child and not a tenth top-level tab (EP-CWP-12).
    expect(CONFIGURE_SUB_TABS.map((sub) => sub.id)).toEqual([
      "reference-data",
      "routes-cycles",
      "number-series",
      "templates",
      "notifications",
      "customer-portal",
    ]);
    expect(DEFAULT_SETTINGS_TAB).toBe("company");
  });

  it("BR-SHL-011: an unknown :tab falls back to Company instead of erroring", () => {
    expect(settingsTabFromParam(undefined)).toBe("company");
    expect(settingsTabFromParam("security")).toBe("security");
    expect(settingsTabFromParam("not-a-tab")).toBe("company");
  });

  it("BR-SHL-025: access is copied out of the SERVER's grid — no role name is interpreted here", () => {
    const admin = resolveSettingsAccess(member("system_admin"), MATRIX);
    expect(admin).toEqual({ settings_lookups: CELL_FULL, user_management: CELL_FULL });
    const exec = resolveSettingsAccess(member("executive"), MATRIX);
    expect(exec).toEqual({ settings_lookups: CELL_VIEW, user_management: CELL_NONE });
    const clerk = resolveSettingsAccess(member("billing_clerk"), MATRIX);
    expect(clerk).toEqual({ settings_lookups: CELL_NONE, user_management: CELL_NONE });
    // A role the grid does not mention gets "—", never an assumed default.
    expect(resolveSettingsAccess(member("auditor"), MATRIX)?.settings_lookups).toBe(CELL_NONE);
    // No grid = hide nothing; each tab's own 403 is then the boundary.
    expect(resolveSettingsAccess(member("system_admin"), null)).toBeNull();
  });

  it("BR-SHL-003 / BR-IDN-009: Users & roles is drawn only where the grid says the role may reach it", () => {
    const adminTabs = visibleSettingsTabs(
      SETTINGS_TABS,
      resolveSettingsAccess(member("system_admin"), MATRIX),
    );
    expect(adminTabs.map((tab) => tab.id)).toContain("users");

    const execTabs = visibleSettingsTabs(
      SETTINGS_TABS,
      resolveSettingsAccess(member("executive"), MATRIX),
    );
    expect(execTabs.map((tab) => tab.id)).not.toContain("users");
    expect(execTabs.map((tab) => tab.id)).toContain("security");

    // A4: Settings is "—" for a Billing Clerk — the whole page, not one tab.
    const clerkTabs = visibleSettingsTabs(
      SETTINGS_TABS,
      resolveSettingsAccess(member("billing_clerk"), MATRIX),
    );
    expect(clerkTabs).toHaveLength(0);
  });

  it("BR-SHL-025: a 'View' cell renders the tab read-only rather than hiding it", () => {
    const exec = resolveSettingsAccess(member("executive"), MATRIX);
    const security = SETTINGS_TABS.find((tab) => tab.id === "security");
    const company = SETTINGS_TABS.find((tab) => tab.id === "company");
    expect(security).toBeDefined();
    expect(company).toBeDefined();
    expect(tabIsReadOnly(security!, exec)).toBe(true);
    expect(tabIsReadOnly(company!, exec)).toBe(true);
    expect(tabIsReadOnly(company!, resolveSettingsAccess(member("system_admin"), MATRIX))).toBe(
      false,
    );
  });

  it("a Billing Clerk gets the A18 §6 permission-denied block for the whole page", () => {
    const html = renderSettings("company", member("billing_clerk"), MATRIX);
    expect(html).toContain("state-denied");
    expect(html).toContain("Settings is for System Admins");
    // Nothing of the tab bar renders behind the block.
    expect(html).not.toContain('role="tablist"');
  });

  it("a System Admin sees the tab bar with the active tab marked", () => {
    const html = renderSettings("security", member("system_admin"), MATRIX);
    expect(html).toContain('role="tablist"');
    expect(html).toContain("Users &amp; roles");
    expect(html).toContain('aria-selected="true"');
  });

  it("US-BIL-009: /settings/accounting is REACHABLE and mounts the GL mapping, not an honest-state card", () => {
    // Hard-won law 2 in its own words: a tab in a constant that the frame never
    // mounts is dead UI. This asserts the FRAME→BODY wiring, not the constant —
    // the strip offers the label, the URL resolves it, and the body that comes
    // back is the mapping screen's own panel.
    const html = renderSettings(
      "accounting",
      member("system_admin"),
      MATRIX,
      PERMISSIONS.system_admin,
      null,
      null,
      ACCOUNTING_SERVICES,
    );
    expect(html).toContain(">Accounting<");
    expect(html).toContain('aria-selected="true"');
    // The tab's OWN content, from SettingsAccountingTab.
    //
    // ⚠ 2026-08-17 (CR-008): the Accounting tab became THREE sub-tabs — chart
    // of accounts · GL mapping · finance controls — so it no longer opens on
    // the service-revenue panel and this used to assert that panel's title.
    // Asserted on the sub-tab STRIP instead, which is what the frame's job
    // actually is: this case exists to prove `/settings/accounting` mounts the
    // real tab rather than an honest-state placeholder, and the strip proves
    // that without pinning which sub-tab happens to open first.
    expect(html).toContain("Chart of accounts");
    // Same reason as above: the tax mapping now lives on the GL-mapping
    // SUB-TAB, not on the tab's landing panel. The strip is what proves the
    // real tab mounted.
    expect(html).toContain("GL mapping");
    // And it is emphatically NOT the "arrives with …" placeholder.
    expect(html).not.toContain("settings-arrives");
  });

  it("the Notifications tab is the delivery dashboard, not an 'arrives with' note (DEF-128)", () => {
    // It rendered "Channels, quiet hours …" while 7,084 lines of notifications
    // engine sat behind an api.py of 72 bytes that no URLconf named. The routes
    // are mounted (A11 Addendum r4) and this tab draws them, so the placeholder
    // stopped being true — and a string claiming a state of the product is a
    // claim, not a note (hard-won law 1). Unseeded, the body renders its A18 §3
    // skeleton like every other live tab; what it must NEVER be again is the
    // honest-absence frame.
    // 2026-10-22: it is Configure's segment now, next to Templates.
    const html = renderSettings(CONFIGURE_TAB, member("system_admin"), MATRIX);
    expect(html).toContain(">Notifications<");
    expect(html).not.toContain("settings-arrives");
    expect(html).not.toContain("Channels, quiet hours");
  });

  it("a tab declaring arrivesWithKey renders the honest state, never a form — and Integrations, mounted, never does (DEF-INT-3632)", () => {
    // ⚠ BILLING PLAN LEFT THIS LIST ON 2026-08-27 (DEF-1092) and INTEGRATIONS
    // LEFT IT ON 2026-09-03 — CR-069 wave A mounted the grid and deleted the
    // sentence this case used to look for, and the case sat red pointing at a
    // tab that no longer existed (DEF-INT-3632; wave D filed the same case as
    // DEF-INT-3622). What it proves is the
    // MECHANISM: any tab that declares the key renders the A18 absence box and
    // no control. So it is proved on a tab of the test's own — the real
    // Integrations tab's shape with the key put back — and no longer borrows
    // whichever real tab happened to be unbuilt that week.
    const integrations = SETTINGS_TABS.find((tab) => tab.id === "integrations");
    expect(integrations).toBeDefined();
    const probe: SettingsTab = {
      ...(integrations as SettingsTab),
      id: "arrives-probe",
      arrivesWithKey: "settings.arrivesWith.unknown",
    };
    const html = renderTabBody(probe);
    expect(html).toContain("settings-arrives");
    expect(html).toContain("This tab has nothing behind it yet.");
    // The proof that it is not a fake form: no inputs, no save control.
    expect(html).not.toContain("<input");
    expect(html).not.toContain('data-variant="primary"');

    // And the opposite on the real tab: Integrations is a screen now. Nothing
    // is seeded here, so its body is the grid's loading state — never the
    // absence box, and never the sentence wave A deleted.
    const live = renderSettings("integrations", member("system_admin"), MATRIX);
    expect(live).not.toContain("settings-arrives");
    expect(live).not.toContain("Accounting, payment, meter and email connections");
  });

  it("the Billing plan tab is the subscription screen, not an 'arrives with' note (DEF-1092)", () => {
    // It said *"Your SMARTBillHub subscription, invoices and payment method
    // arrive with the Billing plan feature"* in all eleven catalogues while
    // `subscriptions` had been seeded since tenancy/0005 — sixteen days — and
    // CR-039 wave F put `implementation_orders`, `addons` and `tenant_addons`
    // behind the same sentence. A tenant carried a quotable IMPL-26-0001 that
    // no human being could see anywhere in the product. This is DEF-128's case
    // one tab over: a string claiming a state of the product is a claim, not a
    // note (hard-won law 1).
    //
    // Unseeded, the body renders its A18 §3 skeleton like every other live
    // tab; what it must never be again is the honest-absence frame over the
    // WHOLE feature. Two thirds of that sentence are still true — the invoices
    // (S108) and the payment method (S109) — and they are now stated ON the
    // screen, beside the things that do render.
    const html = renderSettings("billing-plan", member("system_admin"), MATRIX);
    expect(html).toContain(">Billing plan<");
    expect(html).not.toContain("settings-arrives");
    expect(html).not.toContain("arrive with the Billing plan feature");
  });

  it.todo(
    "US-TEN-009 TC-5 (isolation): a second tenant's admin sees only their own tab data — server/RLS scope (G5)",
  );
  it.todo(
    "browser scope → Playwright: clicking a tab pushes /settings/<tab> and a reload lands on the same tab",
  );
});

describe("US-IDN-008 — tab visibility comes from GET /me/permissions, not from probing a 403", () => {
  it("BR-SHL-025: the caller's OWN A4 row is the gating source, copied cell for cell", () => {
    expect(accessFromPermissions(PERMISSIONS.executive)).toEqual({
      settings_lookups: CELL_VIEW,
      user_management: CELL_NONE,
    });
    expect(accessFromPermissions(PERMISSIONS.system_admin)).toEqual({
      settings_lookups: CELL_FULL,
      user_management: CELL_FULL,
    });
    expect(accessFromPermissions(PERMISSIONS.billing_clerk)).toEqual({
      settings_lookups: CELL_NONE,
      user_management: CELL_NONE,
    });
    // A permission row the payload does not mention reads "—", never an
    // assumed default — the same posture the /roles grid path takes.
    expect(
      accessFromPermissions({ role: "auditor", role_name: "Auditor", permissions: [] })
        ?.settings_lookups,
    ).toBe(CELL_NONE);
    // Unreadable permissions = hide nothing; the 403 backstop takes over.
    expect(accessFromPermissions(null)).toBeNull();
    expect(accessFromPermissions(undefined)).toBeNull();
  });

  it("a '—' tab is HIDDEN: an Executive never sees Users & roles", () => {
    const html = renderSettings("company", member("executive"), null, PERMISSIONS.executive, COMPANY);
    expect(html).toContain('role="tablist"');
    // Settings & lookup tables is "View" for an Executive, so the frame renders…
    expect(html).toContain("Company");
    expect(html).toContain("Configure"); // CR-001 — was "Reference data"
    // …but user_management is "—", so that tab is not drawn at all.
    expect(html).not.toContain("Users &amp; roles");
  });

  it("a 'View' tab renders READ-ONLY with the reason, rather than vanishing", () => {
    const html = renderSettings("company", member("executive"), null, PERMISSIONS.executive, COMPANY);
    // The tab is drawn, its data is drawn, and the write control is disabled
    // WITH its reason — BR-SHL-025's shape, not a hidden surface.
    expect(html).toContain("Brazos Bend Utility District No. 1");
    expect(html).toContain("Your role can view this, but not change it.");
    expect(html).toContain("disabled");
  });

  it("a Billing Clerk's '—' on Settings hides the whole page, from the permission read alone", () => {
    // No /roles grid is seeded here at all: this proves the gating no longer
    // depends on the System-Admin-only catalog a clerk could never fetch.
    const html = renderSettings("company", member("billing_clerk"), null, PERMISSIONS.billing_clerk);
    expect(html).toContain("state-denied");
    expect(html).not.toContain('role="tablist"');
  });

  it("the /roles grid stays the BACKSTOP when the permission read itself fails", () => {
    const html = renderSettings("company", member("system_admin"), MATRIX, null);
    expect(html).toContain('role="tablist"');
    expect(html).toContain("Users &amp; roles");
  });

  it("BR-SHL-025: with neither source readable, nothing is hidden — the server's 403 is the boundary", () => {
    const tabs = visibleSettingsTabs(SETTINGS_TABS, null);
    expect(tabs).toHaveLength(SETTINGS_TABS.length);
  });

  it.todo(
    "US-IDN-008 (server): the permission payload grants nothing — a client that lies about it still gets 403 (backend scope)",
  );
});

// The divergence this suite closes: 05-prototype/UtilityBilling.html gives
// Settings TEN top-level tabs and puts "Company profile" / "Regional, formats &
// fiscal calendar" in a SECOND-LEVEL `.settings-tabs` strip inside the Company
// tab body. The app shipped Regional as an eleventh top-level tab, one level
// too high, and Company with no strip at all.
describe("S8 → Company: the prototype's second-level strip (UtilityBilling.html §Settings)", () => {
  const ADMIN = member("system_admin");
  const render = (path: string): string =>
    renderSettings(path, ADMIN, MATRIX, null, COMPANY, REGIONAL);

  it("Regional is NOT a top-level tab any more — the ten the prototype draws are the ten drawn", () => {
    expect(SETTINGS_TABS.map((tab) => tab.id)).not.toContain("regional");
    const html = render("company");
    // The old top-level label is gone from the strip entirely.
    expect(html).not.toContain("Regional &amp; formats");
  });

  it("the Company tab body carries a second strip, with the prototype's own two labels verbatim", () => {
    const html = render("company");
    // Two strips: Settings' own, and Company's — nested, exactly as the
    // prototype nests `.settings-tabs` inside `show_company`.
    expect(tablistCount(html)).toBe(2);
    expect(html).toContain("Company profile");
    expect(html).toContain("Regional, formats &amp; fiscal calendar");
    // …and it is a `.settings-tabs` strip, not a second PageHeader: exactly one
    // <h1> on the page (G14 shape, BR-SHL-044's skeleton).
    expect(html.split("<h1").length - 1).toBe(1);
  });

  it("each sub-tab renders its OWN panel, and only its own", () => {
    const profile = render("company");
    expect(profile).toContain("Utility details"); // US-TEN-005's first panel
    // r10 SET-01.profile copy.
    expect(profile).toContain("Save changes");
    expect(profile).not.toContain("Fiscal calendar");

    const regional = render("company/regional");
    expect(regional).toContain("Location &amp; language"); // US-TEN-006's first panel
    expect(regional).toContain("Fiscal calendar");
    expect(regional).toContain("Save regional &amp; fiscal settings");
    expect(regional).not.toContain("Utility details");
  });

  it("the sub-tab is URL state, so `/settings/company/regional` is linkable", () => {
    expect(activeTabLabels(render("company"))).toEqual(["Company", "Company profile"]);
    expect(activeTabLabels(render("company/regional"))).toEqual([
      "Company",
      "Regional, formats &amp; fiscal calendar",
    ]);
  });

  it("BR-SHL-011's spirit: an unknown `:sub` falls back to Company profile, it never errors", () => {
    expect(companySubTabFromParam(undefined)).toBe(DEFAULT_COMPANY_SUB_TAB);
    expect(companySubTabFromParam("regional")).toBe("regional");
    expect(companySubTabFromParam("not-a-sub-tab")).toBe(DEFAULT_COMPANY_SUB_TAB);
    expect(DEFAULT_COMPANY_SUB_TAB).toBe("profile");
    expect(COMPANY_SUB_TABS.map((sub) => sub.id)).toEqual(["profile", "regional"]);

    const html = render("company/not-a-sub-tab");
    expect(activeTabLabels(html)).toEqual(["Company", "Company profile"]);
    expect(html).toContain("Utility details");
  });

  it("BR-SHL-025: the frame's read-only verdict still reaches BOTH sub-tabs", () => {
    // Settings & lookup tables is "View" for an Executive — the sub-tab it
    // lands on is disabled-with-reason either way, never hidden.
    const profile = renderSettings("company", member("executive"), MATRIX, null, COMPANY, REGIONAL);
    const regional = renderSettings(
      "company/regional",
      member("executive"),
      MATRIX,
      null,
      COMPANY,
      REGIONAL,
    );
    for (const html of [profile, regional]) {
      expect(html).toContain("Your role can view this, but not change it.");
      expect(html).toContain("disabled");
    }
  });
});

describe("the deep links into Settings still resolve after the nesting (US-TEN-003's contract)", () => {
  // `apps/tenancy/selectors.py CHECKLIST_TARGETS` is SERVER data this frontend
  // cannot change; every fragment it sends must keep landing on a screen.
  const routeFor = (url: string): string | undefined => {
    const matches = matchRoutes(APP_ROUTES, url);
    return matches === null ? undefined : matches[matches.length - 1]?.route.path;
  };

  it("the three unmoved targets still match the Settings route", () => {
    for (const target of ["company", "services", "users"]) {
      expect(routeFor(`/brazosbend/settings/${target}`)).toBe("settings/:tab");
    }
  });

  it("CR-001: the three MOVED tabs redirect rather than 404 — the point of the change", () => {
    // `settings/number-series` is a checklist target the SERVER sends
    // (apps/tenancy/selectors.py CHECKLIST_TARGETS), and the Reference data
    // screen links to `/settings/templates` for the BR-TEN-033 document
    // pointer. Both were live before CR-001 moved them one level down. A tab
    // move that 404s a live checklist link would be the change request causing
    // a defect, which is why each keeps a static redirect route ranked above
    // `settings/:tab`.
    for (const [tab, target] of [
      ["routes-cycles", "/settings/reference-data/routes-cycles"],
      ["number-series", "/settings/reference-data/number-series"],
      ["templates", "/settings/reference-data/templates"],
    ] as const) {
      expect(LEGACY_SETTINGS_TAB_PATHS[tab]).toBe(target);
      expect(legacySettingsPath(tab)).toBe(target);
      expect(routeFor(`/brazosbend/settings/${tab}`)).toBe(`settings/${tab}`);
    }
  });

  it("CR-001: Configure's own sub-tab URLs route, and an unknown :sub falls back", () => {
    expect(routeFor("/brazosbend/settings/reference-data/number-series")).toBe(
      "settings/:tab/:sub",
    );
    expect(configureSubTabFromParam(undefined)).toBe("reference-data");
    expect(configureSubTabFromParam("templates")).toBe("templates");
    expect(configureSubTabFromParam("not-a-sub-tab")).toBe("reference-data");
  });

  it("`settings/regional` — the checklist's fiscal_billing target — REDIRECTS rather than 404s", () => {
    expect(LEGACY_SETTINGS_TAB_PATHS.regional).toBe("/settings/company/regional");
    expect(legacySettingsPath("regional")).toBe("/settings/company/regional");
    expect(legacySettingsPath("company")).toBeNull();
    expect(legacySettingsPath(undefined)).toBeNull();
    // A dedicated static route, ranked above `settings/:tab`, carries it.
    expect(routeFor("/brazosbend/settings/regional")).toBe("settings/regional");
  });

  it("the canonical sub-tab URL is routed", () => {
    expect(routeFor("/brazosbend/settings/company/regional")).toBe("settings/:tab/:sub");
    expect(routeFor("/brazosbend/settings/company/profile")).toBe("settings/:tab/:sub");
  });

  it.todo(
    "browser scope → Playwright: /settings/regional lands the address bar on /settings/company/regional",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07; co-packet EP-IDN-03@c4e29d2)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane) · AMENDED 2026-08-09 by story-coder (frontend integration lane: permission-driven tab visibility) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-10 by story-coder v1 (Settings → Company sub-tab lane: the second-level strip, its URL state, its fallback, and the deep links it must not break)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 296 passed / 83 todo across 30 files✔ (239+72 baseline unchanged and green; this packet adds 57 passing + 11 todo — the todos are browser-interaction, server/RLS and unbuilt-neighbour-screen scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔ · 2026-08-10 Company sub-tab re-run: tsc✔ eslint✔ vitest 604 passed / 142 todo across 46 files✔ (593 + 141 across 46 was the pre-lane baseline) · vite build✔ · run_gates 13 PASS · 0 FAIL · 1 SKIP
// exceptions: E4 law 7 (prove the guard RED first) is satisfied by running this suite against the UNCHANGED frame: 9 checks failed — "Regional is NOT a top-level tab any more", "the Company tab body carries a second strip", "each sub-tab renders its OWN panel", "the sub-tab is URL state", "an unknown `:sub` falls back", "`settings/regional` REDIRECTS", "the canonical sub-tab URL is routed", the amended tab-order check, and the routing suite's "/settings/company/regional renders Regional". The output is in this lane's report · E4 the address-bar half of the redirect stays an it.todo: a <Navigate> renders nothing under renderToStaticMarkup and this project has no jsdom environment, so what is proven here is that the old URL is claimed by a redirect route and that the redirect's target is the canonical sub-tab path — the navigation itself is Playwright scope
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
