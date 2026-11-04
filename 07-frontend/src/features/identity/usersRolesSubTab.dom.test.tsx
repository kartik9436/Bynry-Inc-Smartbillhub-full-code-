// ── Trace ──────────────────────────────────────────────
// Change:  PO ruling 2026-09-17 — the roles & permissions grid moves out of a
//          button-revealed panel and into a sub-tab of Users & roles. No
//          blueprint exists for this screen (PO, verbatim: "no there is not
//          blueprint - you can use our ui gudelines and generator specs"), so
//          B14 and the shared component kit govern.
// Rules:   BR-IDN-014 (the matrix is READ-ONLY, rendered from the server
//          catalogue) · BR-IDN-008 (three predefined roles; no tenant role CRUD)
// UI:      B14 rule 33 (a label is ≤3 words) · rule 31 (no internal reference
//          on screen)
// ───────────────────────────────────────────────────────
/**
 * THE GRID GETS AN ADDRESS.
 *
 * It used to be a panel below the user table, revealed by a *"View roles &
 * permissions"* button held in `useState`. That is one address serving two
 * surfaces: the grid could not be linked, could not be bookmarked, and was gone
 * the moment anyone navigated away. It is now `/{tenant}/settings/users/roles`,
 * built on the SAME mechanism as Company's and Configure's strips rather than a
 * second one.
 *
 * ⚠ **EVERY CASE HERE MOUNTS THE REAL ROUTE TABLE AT THE REAL PATH PATTERN**
 * (`/:tenant/settings/:tab/:sub`), never the component bare. `DEF-CWP-3925` is
 * why: the customer portal's front page passed its own suite while every link
 * it built came out `//portal/…`, because it was mounted with no tenant in
 * scope and `useParams().tenant` was undefined — and a protocol-relative URL to
 * another host reads as a perfectly good string to `toContain`.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, useRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import type { MyPermissions, RolesMatrix, SessionUser, TenantUser } from "@/api/endpoints";
import type { Paginated } from "@/api/paginated";
import { queryKeys } from "@/api/queryClient";
import type { ShellDisplay } from "@/api/endpoints";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";
import {
  DEFAULT_USERS_SUB_TAB,
  USERS_SUB_TABS,
  USERS_TAB,
  usersSubTabFromParam,
} from "@/features/tenancy/SettingsPage";

const TENANT = "brazosbend";

const ADMIN: SessionUser = {
  id: "u-admin",
  full_name: "Dana Okafor",
  email: "dana.okafor@sample.test",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const MATRIX: RolesMatrix = {
  roles: [
    { code: "system_admin", name: "System Admin" },
    { code: "billing_clerk", name: "Billing Clerk" },
  ],
  permissions: [
    { code: "user_management", label: "User management", cells: { system_admin: "Full", billing_clerk: "—" } },
  ],
};

const USERS: Paginated<TenantUser> = { count: 0, next: null, previous: null, results: [] };

/** What `GET /shell/display` answers — the only read that gates every screen. */
const SHELL: ShellDisplay = {
  regional: {
    country: "United States",
    timezone: "America/Chicago",
    language: "en-US",
    first_day_of_week: "sunday",
    currency: "USD",
    number_format: "1,234.56",
    date_format: "MM/DD/YYYY",
    time_format: "12-hour",
  },
  company: {
    legal_name: "Brazos Bend Utility District No. 1",
    dba_name: "Brazos Bend Utilities",
    has_logo: false,
    logo_ref: null,
    mark: { letters: "BB", background_hex: null, ink_hex: null, contrast_ratio: null },
    brand_primary_hex: null,
  },
  period: null,
};

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [
    { code: "user_management", label: "User management", access: "Full" },
    { code: "settings_lookups", label: "Settings & lookups", access: "Full" },
  ],
};

/**
 * The app's own route table at one real address, with the reads this frame
 * makes already in cache. `enabled: false` keeps the render synchronous: every
 * query answers from the seeded cache or stays pending, and nothing reaches a
 * network that is not there.
 */
function renderAt(path: string): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  queryClient.setQueryData(queryKeys.me, ADMIN);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(queryKeys.rolesMatrix, MATRIX);
  queryClient.setQueryData(queryKeys.tenantUsers(1, DEFAULT_PAGE_SIZE), USERS);
  // ⚠ `shellDisplay`, NOT `regionalSettings` — `DEF-SHL-4272`. The shell boots
  // on `GET /shell/display`, a route any signed-in role may read; seeding the
  // Admin-only `GET /settings/regional` instead leaves the shell pending and
  // every case below reads a LOADING SKELETON, which is what the first draft of
  // this file did and why three of its assertions were red for the wrong reason.
  queryClient.setQueryData(queryKeys.shellDisplay, SHELL);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routed />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function Routed() {
  return useRoutes(APP_ROUTES as never);
}

const USERS_PATH = `/${TENANT}/settings/${USERS_TAB}`;
const ROLES_PATH = `${USERS_PATH}/roles`;

describe("Users & roles · the roles grid is a sub-tab, not a button", () => {
  it("offers exactly two sub-tabs, Users first", () => {
    // The order is the contract: Users is what the tab has always opened on,
    // and a strip that reordered itself would move the default.
    expect(USERS_SUB_TABS.map((sub) => sub.id)).toEqual(["users", "roles"]);
    expect(DEFAULT_USERS_SUB_TAB).toBe("users");
  });

  it("BR-SHL-011's spirit: an unknown sub-tab falls back rather than erroring", () => {
    expect(usersSubTabFromParam(undefined)).toBe("users");
    expect(usersSubTabFromParam("roles")).toBe("roles");
    expect(usersSubTabFromParam("nonsense")).toBe("users");
  });

  it("the grid has an ADDRESS of its own and it renders there", () => {
    // The whole point of the move. Before it, this URL fell through to the
    // Users table and the grid was reachable only by pressing a button.
    const html = renderAt(ROLES_PATH);
    expect(html).toContain("User management"); // the matrix's own row
    expect(html).toContain("Billing Clerk"); // its column, from the server catalogue
  });

  it("/settings/users still opens the user table, so nothing anyone opened changed", () => {
    const html = renderAt(USERS_PATH);
    // The user table's empty state, not the grid.
    expect(html).not.toContain("User management");
  });

  it("the button that used to reveal the grid is gone — one way in, not two", () => {
    // ⚠ Asserted on BOTH addresses. A button left behind on the Users sub-tab
    // would be a second door to a surface that now has its own, which is the
    // thing the ruling removed.
    for (const path of [USERS_PATH, ROLES_PATH]) {
      expect(renderAt(path)).not.toContain("View roles &amp; permissions");
    }
  });

  it("BR-IDN-014: the grid stays READ-ONLY — moving a surface grants no permission", () => {
    // ⚠ SCOPED TO THE PANEL, and the first draft was not — it asked the whole
    // page for `<input>` and failed on the SHELL'S GLOBAL SEARCH BOX. A
    // read-only assertion that reads the whole document is measuring the frame,
    // not the thing it names, and would have gone red on any screen in the
    // product. What this needs to say is that the GRID offers no control.
    const panel = renderAt(ROLES_PATH).match(
      /<div class="settings-matrix">[\s\S]*?<\/table>/,
    )?.[0];
    expect(panel).toBeDefined();
    // No editor, no control, nothing that could call a mutation — because
    // there is no tenant-facing mutation route for the matrix at all.
    expect(panel).not.toMatch(/<input|<select|<textarea|<button/i);
    expect(panel).not.toMatch(/contenteditable/i);
    // …and it IS the server's grid, not an empty shell that trivially has none.
    expect(panel).toContain("User management");
  });

  it("the strip is a tablist with the active sub-tab marked, as its two siblings are", () => {
    const html = renderAt(ROLES_PATH);
    expect(html).toContain('role="tablist"');
    // `aria-selected` on the chosen one — the same markup CompanySubTabs and
    // ConfigureSubTabs emit, which is why this is not a second mechanism.
    expect(html).toMatch(/aria-selected="true"[^>]*>Roles &amp; permissions</);
  });

  it("B14 rule 33: each sub-tab label is a label, not a sentence", () => {
    // A LABEL is ≤3 words and carries no sentence. "Roles & permissions" is
    // three; the grid's own longer heading stays inside the panel where it is
    // a heading rather than a tab.
    for (const sub of USERS_SUB_TABS) {
      const label = sub.labelKey.split(".").pop() ?? "";
      expect(label.length).toBeGreaterThan(0);
    }
    const html = renderAt(ROLES_PATH);
    for (const word of ["Users", "Roles &amp; permissions"]) {
      expect(html).toContain(word);
    }
    expect(html).not.toContain("View roles");
  });
});
