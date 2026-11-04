// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-3964 (2026-09-05) — the PO, on the running product:
//          *"date and time format is set in the settings, plus we save
//          location - but date shown everywhere in the product does not change
//          with that format change. If I change the language it changes across
//          entire app, date does not change."*
// Rules:   IS-8 (a date renders in the TENANT's regional format) ·
//          BR-SHL-023 (the tenant's zone, one formatting path) ·
//          hard-won law 3 (defaults fail closed) · law 6 (assert RENDERED
//          OUTPUT — no gate in this repo looks at it)
// ───────────────────────────────────────────────────────
// ⚠ **THE CHECK THIS PRODUCT NEVER HAD, AND WHY EVERY OTHER ONE PASSED.**
//
// 4,862 frontend tests were green on the day the PO reported this. Dozens of
// them render a date. Not one could have caught it, and the reason is a single
// line in each — here is a real one, from `AuditLogPage.test.tsx`:
//
//     <AuditLogPage timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />
//
// The test hands the screen the format and then asserts the format it handed
// it. That proves `formatDate` works. It cannot say a word about whether the
// TENANT'S OWN setting ever reaches the screen — which was the whole defect.
//
// So this file never passes a format to anything. It puts the setting where
// the PRODUCT puts it — the answer to `GET /settings/regional`, which is what
// Settings → Regional writes and what `ShellWithSession` reads — mounts the
// REAL routes through the REAL shell, and reads the date off the DOM.
//
// The screen under test is **Settings → Users** (`/{tenant}/settings/users`),
// picked because its `Last active` column renders an INSTANT with a time, so
// one fixture proves both halves at once: the FORMAT and the ZONE. The instant
// is `2026-09-05T01:30:00Z`, which is deliberately just after midnight UTC —
// in `America/Chicago` that is the evening of the day BEFORE, so a zone that
// does not reach the screen shows the wrong DAY and not merely the wrong hour.
// That is the PO's own worst case: *a payment taken at 7pm local shows as the
// next day.*
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { APP_ROUTES } from "@/App";
import type {
  MyPermissions,
  RegionalSettings,
  RolesMatrix,
  SessionUser,
  ShellDisplay,
  TenantUser,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { REGIONAL_UNPUBLISHED, resolveRegional } from "@/features/metering/meteringShared";
import { tenantRegionalOf } from "@/components/ShellWithSession";
import { ToastProvider } from "@/components/Toast";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";

import SHELL_SOURCE from "./ShellWithSession.tsx?raw";
import METERING_SHARED_SOURCE from "../features/metering/meteringShared.tsx?raw";

afterEach(cleanup);

const TENANT = "brazosbend";

/** 01:30 UTC — the evening BEFORE in every American zone. */
const LAST_ACTIVE = "2026-09-05T01:30:00Z";

const ADMIN: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@brazosbend.example",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const MATRIX: RolesMatrix = {
  roles: [{ code: "system_admin", name: "System Admin" }],
  permissions: [
    { code: "settings_lookups", label: "Settings & lookup tables", cells: { system_admin: "Full" } },
    { code: "user_management", label: "User management", cells: { system_admin: "Full" } },
  ],
};

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [
    { code: "settings_lookups", label: "Settings & lookup tables", access: "Full" },
    { code: "user_management", label: "User management", access: "Full" },
  ],
};

const STAFF: TenantUser[] = [
  {
    id: "u1",
    name: "Dana Whitfield",
    email: "dana@brazosbend.example",
    role: "system_admin",
    role_name: "System Admin",
    last_active_at: LAST_ACTIVE,
    status: "active",
  },
];

/** What `GET /settings/regional` answers — i.e. what the tenant SAVED. */
function saved(timezone: string, dateFormat: string): RegionalSettings {
  return {
    country: "United States",
    state: "TX",
    timezone,
    language: "en-US",
    first_day_of_week: "sunday",
    currency: "USD",
    number_format: "1,234.56",
    date_format: dateFormat,
    time_format: "12-hour",
    fy_start_month: 1,
    fy_start_day: 1,
    accounting_method: "accrual",
    close_cadence: "monthly",
    close_day: "last day",
    lock_closed_periods: false,
    current_period: null,
  };
}

/**
 * `GET /shell/display` — what the app shell ACTUALLY boots on since
 * DEF-SHL-4272 (2026-09-06). The display half of the same saved values, plus
 * the branding, on a route any signed-in role may read.
 *
 * ⚠ **THIS SEED MOVED, AND THE MOVE IS THE POINT OF `DEF-SHL-4272`.** It used
 * to be `queryKeys.regionalSettings` — `GET /settings/regional`, which is
 * Admin/Executive only, so **a Billing Clerk got 403 and every screen in the
 * product rendered the shell's failure state** for sixteen days. The four
 * finance-policy fields below are DELIBERATELY absent from this payload: a
 * clerk does not receive a utility's close policy in order to draw a date.
 */
function boot(regional: RegionalSettings): ShellDisplay {
  return {
    regional: {
      country: regional.country,
      timezone: regional.timezone,
      language: regional.language,
      first_day_of_week: regional.first_day_of_week,
      currency: regional.currency,
      number_format: regional.number_format,
      date_format: regional.date_format,
      time_format: regional.time_format,
    },
    company: {
      legal_name: "Brazos Bend Utility District No. 1",
      dba_name: "Brazos Bend Utilities",
      has_logo: false,
      logo_ref: null,
      mark: { letters: "BB", background_hex: null, ink_hex: null, contrast_ratio: null },
      brand_primary_hex: null,
    },
    // DEF-SHL-4283 — the computed period card WITHOUT `close_by`. These cases
    // are about the date FORMAT reaching the screen and never draw a period, so
    // the honest value here is the tenant's own: `current_period` when the
    // fixture has one, and `null` when it has not set a fiscal year start.
    period:
      regional.current_period === null
        ? null
        : {
            fy_label: regional.current_period.fy_label,
            period: regional.current_period.period,
            start: regional.current_period.start,
            end: regional.current_period.end,
            status: regional.current_period.status,
          },
  };
}

/**
 * The product, at `/{tenant}/settings/users`, with the tenant's regional
 * settings as the ONLY thing that varies between cases.
 *
 * `regional === null` seeds nothing, which is how a tenant whose settings have
 * not arrived is spelled.
 */
function openUsersScreen(regional: RegionalSettings | null, user: SessionUser = ADMIN): void {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, user);
  queryClient.setQueryData(queryKeys.rolesMatrix, MATRIX);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(queryKeys.tenantUsers(1, DEFAULT_PAGE_SIZE), {
    count: STAFF.length,
    next: null,
    previous: null,
    results: STAFF,
  });
  if (regional !== null) {
    queryClient.setQueryData(queryKeys.shellDisplay, boot(regional));
  }
  const router = createMemoryRouter(APP_ROUTES, {
    initialEntries: [`/${TENANT}/settings/users`],
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The `<time>` element the Last active column renders, by its machine value. */
function lastActiveText(): string {
  const cell = document.querySelector(`time[datetime="${LAST_ACTIVE}"]`);
  expect(cell).not.toBeNull();
  return (cell?.textContent ?? "").trim();
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE SETTING REACHES THE SCREEN — three tenants, one unchanged screen
// ══════════════════════════════════════════════════════════════════════════

describe("DEF-SHL-3964 — a date on a screen is the TENANT'S date", () => {
  it("America/Chicago + DD/MM/YYYY renders 04/09/2026 20:30, not 09/05/2026 01:30", () => {
    openUsersScreen(saved("America/Chicago", "DD/MM/YYYY"));
    // 01:30 UTC on the 5th is 20:30 on the 4th in Chicago. Both halves of the
    // defect are in this one string: the DAY comes from the zone, the ORDER of
    // the numbers comes from the format, and nothing in this file handed the
    // screen either one.
    expect(lastActiveText()).toBe("04/09/2026 20:30");
    // The seed answer, stated as its own negative so a regression NAMES itself.
    expect(lastActiveText()).not.toBe("09/05/2026 01:30");
  });

  it("UTC + MM/DD/YYYY renders 09/05/2026 01:30 — the same screen, a different tenant", () => {
    openUsersScreen(saved("UTC", "MM/DD/YYYY"));
    expect(lastActiveText()).toBe("09/05/2026 01:30");
  });

  it("Asia/Kolkata + YYYY-MM-DD renders 2026-09-05 07:00 — a half-hour offset, too", () => {
    // A third answer matters: two would still be satisfiable by a coin flip.
    // The half-hour offset also proves the zone is applied by `Intl` rather
    // than by an hour count somebody wrote down.
    openUsersScreen(saved("Asia/Kolkata", "YYYY-MM-DD"));
    expect(lastActiveText()).toBe("2026-09-05 07:00");
  });

  it("changing the setting changes the screen — the PO's actual complaint", () => {
    openUsersScreen(saved("America/Chicago", "DD/MM/YYYY"));
    const chicago = lastActiveText();
    cleanup();
    openUsersScreen(saved("UTC", "MM/DD/YYYY"));
    expect(lastActiveText()).not.toBe(chicago);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 1b · AND IT REACHES A BILLING CLERK'S SCREEN TOO (DEF-SHL-4272)
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **EVERY FIXTURE IN THIS REPOSITORY SIGNS IN AS A SYSTEM ADMIN, WHICH IS
// WHY A CLERK COULD NOT USE THE PRODUCT AT ALL FOR SIXTEEN DAYS.** The cases
// above are no exception — `ADMIN` is `system_admin`. This one is the same
// screen, the same instant and the same saved settings, drawn for a Billing
// Clerk, so a role assumption anywhere between the shell and the cell has
// somewhere to go red.

describe("DEF-SHL-4272 — the product draws for a Billing Clerk", () => {
  const CLERK: SessionUser = {
    id: "u2",
    full_name: "Sam Reyes",
    email: "sam.reyes@sample.test",
    phone: null,
    role: "billing_clerk",
    role_name: "Billing Clerk",
    must_change_password: false,
  };

  it("a clerk's screen renders the tenant's own date, not a failure state", () => {
    openUsersScreen(saved("America/Chicago", "DD/MM/YYYY"), CLERK);
    // The exact string an admin gets one describe block up. A clerk saw NONE
    // of this between 2026-08-21 and 2026-09-06 — they got
    // "We couldn't load your regional settings." over every route.
    expect(lastActiveText()).toBe("04/09/2026 20:30");
  });

  it("the shell's failure sentence is nowhere on a clerk's screen", () => {
    openUsersScreen(saved("America/Chicago", "DD/MM/YYYY"), CLERK);
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("regional settings");
    expect(body).not.toContain("Try again");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 2 · BEFORE THE SETTING ARRIVES, NOTHING IS INVENTED (decision D3/D4)
// ══════════════════════════════════════════════════════════════════════════

describe("DEF-SHL-3964 — no screen renders a date the tenant did not choose", () => {
  it("with the settings unread, the row is not drawn at all — no seed date appears", () => {
    openUsersScreen(null);
    // The shell holds. The point is not WHICH holding state is drawn, it is
    // that no date is: a plausible wrong date is the defect, and a screen that
    // waits is the decision (D3).
    expect(document.querySelector(`time[datetime="${LAST_ACTIVE}"]`)).toBeNull();
    expect(document.body.textContent ?? "").not.toContain("09/05/2026");
    expect(document.body.textContent ?? "").not.toContain("01:30");
  });

  it("a date_format the renderer cannot draw is NOT KNOWN, never `undefined` on screen", () => {
    // `tenant_settings.date_format` is a bare TEXT column. An unrecognised
    // value used to reach `arrange()`, whose switch has no default — the cell
    // would have read `undefined`. It now reads as not-yet-known and holds.
    expect(tenantRegionalOf(saved("America/Chicago", "swedish"))).toBeNull();
    expect(tenantRegionalOf(saved("", "DD/MM/YYYY"))).toBeNull();
    expect(tenantRegionalOf(undefined)).toBeNull();
    expect(tenantRegionalOf(saved("America/Chicago", "DD/MM/YYYY"))).toEqual({
      timeZone: "America/Chicago",
      dateFormat: "DD/MM/YYYY",
    });
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 3 · THE TWO SETTINGS ON ONE PAGE ARE NOW WIRED THE SAME WAY
// ══════════════════════════════════════════════════════════════════════════

describe("DEF-SHL-3964 — the shell reads all three fields, not just language", () => {
  it("hard-won law 2: `timezone` and `date_format` are READ, not merely served", () => {
    // Language was applied globally and worked; the other two were read by
    // nobody. This asserts the read exists at all — the DOM cases above prove
    // it arrives — because the whole defect was one field being taken off a
    // response and its two neighbours left there.
    expect(SHELL_SOURCE).toContain("displayQuery.data?.regional.language");
    expect(SHELL_SOURCE).toContain("tenantRegionalOf(displayQuery.data?.regional)");
    expect(SHELL_SOURCE).toContain("TenantRegionalProvider");
    // DEF-SHL-4272 — and it reads them off the endpoint EVERY ROLE may call.
    // The two it used to boot on are Admin/Executive only, so naming them here
    // is what goes red if a later lane points the shell back at them.
    expect(SHELL_SOURCE).toContain("getShellDisplay");
    expect(SHELL_SOURCE).not.toContain("getRegionalSettings");
    expect(SHELL_SOURCE).not.toContain("getCompanyProfile");
  });

  it("in the SHIPPED product there is no fallback at all — it throws (law 3)", () => {
    // `resolveRegional` takes the build mode as an argument precisely so this
    // case can exist. Under `vite build` Vite substitutes the literal
    // "production" and strips the test branch, so this IS the shipped
    // behaviour: nothing published, nothing supplied, no plausible wrong date.
    expect(() => resolveRegional({}, null, "production")).toThrow(REGIONAL_UNPUBLISHED);
    expect(() => resolveRegional({}, null, "development")).toThrow(REGIONAL_UNPUBLISHED);
    // Half an answer is not an answer: a zone with no format cannot render.
    expect(() => resolveRegional({ timeZone: "America/Chicago" }, null, "production")).toThrow();
    // What the tenant published is returned untouched, in every mode.
    expect(
      resolveRegional({}, { timeZone: "America/Chicago", dateFormat: "DD/MM/YYYY" }, "production"),
    ).toEqual({ timeZone: "America/Chicago", dateFormat: "DD/MM/YYYY" });
    // An explicitly supplied prop still wins over the published pair — the 160
    // existing call sites that genuinely pass one keep working.
    expect(
      resolveRegional(
        { dateFormat: "YYYY-MM-DD" },
        { timeZone: "America/Chicago", dateFormat: "DD/MM/YYYY" },
        "production",
      ),
    ).toEqual({ timeZone: "America/Chicago", dateFormat: "YYYY-MM-DD" });
  });

  it("under TEST it falls back to the seed pair, and that is a STATED weakness", () => {
    // 86 test files render a date without saying which tenant they are testing.
    // They inherited this and were green while the product was broken. The
    // fallback is kept so this lane is a wire and not an 86-file rewrite; the
    // sweep is filed separately. This case exists so the compromise is visible
    // rather than discovered later by someone reading the source.
    expect(resolveRegional({}, null, "test")).toEqual({
      timeZone: "UTC",
      dateFormat: "MM/DD/YYYY",
    });
  });

  it("the seed constants are OUT of the resolution path (hard-won law 3)", () => {
    // `useRegional` resolves props → context and stops. A `??` onto a constant
    // here is the defect returning, and it returns silently — which is why it
    // is asserted on the source rather than left to a rendered case to notice.
    const body = METERING_SHARED_SOURCE.slice(
      METERING_SHARED_SOURCE.indexOf("export function resolveRegional("),
    );
    expect(body).toContain("props.timeZone ?? published?.timeZone");
    expect(body).toContain('if (mode === "test")');
    // ⚠ THE ASSERTION IS ABOUT WHAT COMES BEFORE THE GATE, AND THE FIRST DRAFT
    // GOT THIS WRONG. It banned `?? SEED_…` anywhere in the function, and then
    // went red on the per-field test fallback INSIDE the `mode === "test"`
    // branch — which is the one place the seed is allowed. A check that cannot
    // tell the sanctioned use from the defect is worse than no check, because
    // the way to make it green is to delete the sanctioned one.
    //
    // So: the resolution ABOVE the gate — the part that runs in the shipped
    // product — may not name a seed constant at all.
    const beforeTheGate = body.slice(0, body.indexOf('if (mode === "test")'));
    expect(beforeTheGate).not.toContain("SEED_TIME_ZONE");
    expect(beforeTheGate).not.toContain("SEED_DATE_FORMAT");
  });

  it("nothing in the product falls back to a hand-written format any more", () => {
    // The brief named two files. A sweep found fifteen. This is the assertion
    // that stops the sixteenth: no source file may spell the seed pair as a
    // display fallback.
    const modules = import.meta.glob("../features/**/*.tsx", {
      query: "?raw",
      import: "default",
      eager: true,
    }) as Record<string, string>;
    const offenders = Object.entries(modules)
      .filter(([path]) => !path.includes(".test."))
      .filter(([, source]) =>
        source
          .split("\n")
          // A `//` line is prose. Several files QUOTE the old fallback in a
          // comment explaining what was removed, and that is documentation, not
          // a rendering path — reading it as an offender would push the next
          // author into deleting the explanation to make a check go green.
          .filter((line) => !line.trimStart().startsWith("//") && !line.trimStart().startsWith("*"))
          .some((line) => /\?\?\s*"(MM\/DD\/YYYY|UTC)"/.test(line)),
      )
      .map(([path]) => path);
    expect(offenders).toEqual([]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-SHL-3964 (lane REGION)
// generated: 2026-09-05 by lane REGION
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
