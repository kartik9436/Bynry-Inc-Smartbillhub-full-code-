// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  P1.6 (Reports Build Brief §02, Phase 1 · Catalogue) — "every
//          destination resolves. Assert each route target against the router's
//          own table, FAILING BY NAME."
// Defect:  DEF-REP-6812 — the "User activity audit" card pointed at
//          `/settings/audit-log`, which matches `settings/:tab`, which
//          `SettingsPage` resolves with `tabs.find(...) ?? tabs[0]`. The card
//          opened Settings → Company. Walked in a browser at 1440 and
//          confirmed before a line of this was written.
// Rules:   CLAUDE.md hard-won law 2, THE MIRROR — "G13 asks whether a prop is
//          passed; nothing asks whether a REFUSAL is still true" — and its
//          fixture clause: mount the routed component under the REAL path
//          pattern, or the one assertion that could catch this cannot be
//          written · hard-won law 7 (a check that reports zero over a scope it
//          silently excludes) · B14 rule 31.
//          Screens: S44
// ───────────────────────────────────────────────────────
//
// WHY A ROUTE TARGET NEEDS ITS OWN CHECK, AND WHY MATCHING IS NOT ENOUGH.
//
// `ROUTE_TARGETS` is six plain strings. Nothing in this product compares one
// with the router, so a wrong address is a typo that compiles. **And the
// obvious check — "does the router match it?" — passes on the defect**, because
// `/settings/audit-log` matches `settings/:tab` perfectly well; it is the
// SCREEN that then throws the value away. A destination is therefore checked in
// two halves, and they fail independently:
//
//   1 · THE ADDRESS IS ROUTED AT ALL — `matchRoutes` against `APP_ROUTES`,
//       which is the router's own table (`screenIds.test.tsx` already asserts
//       that `SCREEN_ROUTES` and `APP_ROUTES` hold the same paths, so there is
//       one table here and not two).
//   2 · THE SCREEN HONOURS EVERY PARAMETER THE ADDRESS FILLS. Where the matched
//       pattern carries a `:param`, the value must be one the receiving screen
//       actually declares — `SETTINGS_TABS`, `RATING_TABS` — read from the
//       screen's OWN table rather than from a copy, so the two cannot drift.
//
// ⚠ **AND A PARAMETER WITH NO DECLARED VOCABULARY IS A FAILURE, NOT A SKIP.**
// Hard-won law 7's fifth shape is a check reporting zero over a scope it
// silently excludes: `G32` said `0 unresolved` truthfully, of everything it
// could see, over 21 live refusals. So an unregistered `:param` FAILS and names
// itself, which costs the next lane one line in `PARAM_VOCABULARIES` and buys
// the guarantee that this file's green means what it says.
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter, matchRoutes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import type { ReportCard, ReportLibrary } from "@/api/reportsEndpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { RATING_TABS } from "@/features/rating/ratingShared";
import { SETTINGS_TABS } from "@/features/tenancy/SettingsPage";

import { ROUTE_TARGETS, ReportLibraryPage } from "./ReportLibraryPage";
import { REPORTS_ROUTE } from "./reportsShared";

afterEach(cleanup);

const TENANT = "brazosbend";

/**
 * The screens that take a path PARAMETER, and the values each one declares.
 *
 * Read from the screen's own exported table — never transcribed — so a tab
 * added or removed there moves this check with it.
 */
const PARAM_VOCABULARIES: Readonly<Record<string, readonly string[]>> = {
  "/:tenant/settings/:tab": SETTINGS_TABS.map((tab) => tab.id),
  "/:tenant/plans-rates/:tab": RATING_TABS.map((tab) => tab.id),
};

/** The pattern a match resolves to, as the router itself spells it. */
function matchedPattern(address: string): string | null {
  const matches = matchRoutes(APP_ROUTES, address);
  if (matches === null || matches.length === 0) {
    return null;
  }
  return matches[matches.length - 1].pathnameBase === undefined
    ? null
    : matches.reduce((acc, m) => {
        const part = m.route.path ?? "";
        if (part === "") {
          return acc;
        }
        return part.startsWith("/") ? part : `${acc}/${part}`;
      }, "");
}

/** Every `:param` in a pattern, paired with the value the address puts in it. */
function filledParams(pattern: string, address: string): { name: string; value: string }[] {
  const patternParts = pattern.split("/");
  const addressParts = address.split("/");
  const filled: { name: string; value: string }[] = [];
  patternParts.forEach((part, index) => {
    if (part.startsWith(":")) {
      filled.push({ name: part.slice(1), value: addressParts[index] ?? "" });
    }
  });
  return filled;
}

describe("P1.6 · every report-library destination resolves", () => {
  // One case per target, named by the target, so a failure reads as the brief
  // writes it: "S61 → /settings/audit-log matches no route".
  for (const [screenId, target] of Object.entries(ROUTE_TARGETS)) {
    it(`${screenId} → ${target} opens a screen the router has`, () => {
      const address = `/${TENANT}${target}`;
      const pattern = matchedPattern(address);

      expect(pattern, `${screenId} → ${target} matches no route`).not.toBeNull();

      for (const param of filledParams(pattern as string, address)) {
        if (param.name === "tenant") {
          continue;
        }
        const vocabulary = PARAM_VOCABULARIES[pattern as string];
        expect(
          vocabulary,
          `${screenId} → ${target} fills :${param.name} on ${pattern as string}, ` +
            "and no screen vocabulary is registered for it — register one rather " +
            "than letting this check pass over a parameter it cannot read",
        ).not.toBeUndefined();
        expect(
          vocabulary,
          `${screenId} → ${target} matches no route: "${param.value}" is not a ` +
            `${param.name} ${pattern as string} offers, so the screen falls back ` +
            "to its first one and the card opens somewhere else",
        ).toContain(param.value);
      }
    });
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// AND THE SAME ASSERTION THROUGH THE SCREEN, MOUNTED AT ITS REAL ADDRESS
// ═══════════════════════════════════════════════════════════════════════════
// The portal front page hid two working doors out of eight behind a fixture
// that mounted the component bare in a `MemoryRouter` with no `/:tenant/portal`
// route: `useParams().tenant` was undefined, every address came out
// `//portal/…` — a protocol-relative URL to another host — and `toContain` read
// it as a perfectly good string. So this mounts under `/:tenant/reports` and
// asserts the href a clerk would actually click.
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

// ⚠ **THE KEY MOVED WITH `P1.1` AND THE DOOR DID NOT.** `reports/0003` seeds
// this report as `audit_trail`; `user_activity_audit` was the twenty-three-card
// tuple's name for the same thing. The card, the screen and the defect this
// file exists for are unchanged — only the row's key is new.
const AUDIT_CARD: ReportCard = {
  key: "audit_trail",
  name: "Audit Trail",
  name_overridden: false,
  group: "compliance",
  group_name: "Compliance",
  sub_group: "compliance_audit",
  kind: "route",
  origin: "built_in",
  badge: "Audit",
  available: true,
  basis: null,
  basis_label: null,
  reason_code: null,
  reason_detail: null,
  routes_to_screen: "S61",
  service_codes: [],
  pinned: false,
};

const LIBRARY: ReportLibrary = {
  groups: [
    {
      code: "compliance",
      name: "Compliance",
      sub_groups: [{ code: "compliance_audit", name: "Audit" }],
    },
  ],
  group_total: 1,
  sub_group_total: 1,
  group_options: [{ code: "compliance", name: "Compliance" }],
  cards: [AUDIT_CARD],
  available: 1,
  total: 1,
  count: 1,
  page: 1,
  per: 50,
  pages: 1,
  origin: "standard",
    origin_counts: { standard: 1, custom: 0 },
  q: "",
  group: "",
  service: "",
};

function libraryServer(): ApiClient {
  const get = async (path: string) => {
    if (path === "/reports") {
      return { data: { ...LIBRARY, vocabularies: { services: [] } }, status: 200 };
    }
    return { data: {}, status: 200 };
  };
  const write = async () => ({ data: {}, status: 200 });
  return { request: get, get, post: write, put: write, patch: write, delete: write } as unknown as ApiClient;
}

describe("P1.6 · the audit card's own href, from the mounted screen", () => {
  it("points at the audit log and not at a Settings tab that does not exist", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    });
    queryClient.setQueryData(queryKeys.me, USER);
    queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
    queryClient.setQueryData(
      queryKeys.shellDisplay,
      shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
    );

    const router = createMemoryRouter(
      [{ path: `/:tenant${REPORTS_ROUTE}`, element: <ReportLibraryPage client={libraryServer()} /> }],
      { initialEntries: [`/${TENANT}${REPORTS_ROUTE}`] },
    );
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    const card = await screen.findByText("Audit Trail");
    const link = card.closest("a");
    expect(link, "the audit card is not a link at all").not.toBeNull();
    const href = (link as HTMLAnchorElement).getAttribute("href");

    // Not `//…` — the protocol-relative address a missing `:tenant` produces,
    // which reads as a good string to every substring assertion.
    expect(href?.startsWith("//")).toBe(false);
    expect(href).toBe(`/${TENANT}/audit-log`);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: P1.6 (05-prototype/09 Reports Build Brief.pdf §02 p10, read as an image)
// screens: S44
// generated: 2026-09-26 by lane REP-P1
// gates: RED PROVED FIRST — both describes failed on the tip: "S61 → /settings/audit-log matches no route: \"audit-log\" is not a tab /:tenant/settings/:tab offers", and the href case read "/brazosbend/settings/audit-log".
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
