// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-006 (EP-TEN-05 §Stories)  Screens: S8 (Settings → Regional, formats & fiscal)
// Rules:    BR-TEN-020 (display-time transforms only) · BR-TEN-021/BR-TEN-042 (currency forward-only,
//           then LOCKED — 409 BIZ-LOCKED) · BR-TEN-022 (period card computed server-side) ·
//           BR-TEN-038 (closed-period behaviour is the ledger's) · BR-SHL-034 (ONE formatting path)
// ───────────────────────────────────────────────────────
// §4 test data is Brazos Bend: America/Chicago · USD · MM/DD/YYYY · FY starts
// October 1 · reference date 2026-08-08 → FY2026 Period 11.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type { RegionalSettings } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { RefusalNotice, refusalOf } from "./settingsShared";
import {
  PREVIEW_AMOUNT,
  PREVIEW_DATE,
  RegionalTab,
  asDateFormat,
  currencyIsChanging,
  draftFromRegional,
  localeForNumberFormat,
  regionalChanges,
  regionalIsDirty,
} from "./SettingsRegionalTab";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const BRAZOS_BEND: RegionalSettings = {
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
  current_period: {
    fy_label: "FY2026",
    period: 11,
    start: "2026-08-01",
    end: "2026-08-31",
    status: "open",
    close_by: "2026-09-03",
  },
};

function renderTab(settings: RegionalSettings): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.regionalSettings, settings);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <RegionalTab readOnly={false} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("US-TEN-006 — Regional, formats & fiscal calendar tab", () => {
  it("US-TEN-006 TC-1: the live preview renders the tenant's own date and money through the SHARED formatters", () => {
    const html = renderTab(BRAZOS_BEND);
    // MM/DD/YYYY + USD via formatDate/formatMoney — the same path every other
    // screen uses (BR-SHL-034), so the preview cannot drift from reality.
    expect(html).toContain("08/08/2026");
    expect(html).toContain("$1,234.56");
    expect(html).toContain("Week starts Sunday · America/Chicago");
    expect(PREVIEW_DATE).toBe("2026-08-08");
    expect(PREVIEW_AMOUNT).toBe("1234.56");
  });

  it("⚠ DEF-753: choosing DD-MMM-YY says on screen that CSV IMPORT reads English month names only", () => {
    // ⚠ **THE ONE FORMAT THAT BEHAVES DIFFERENTLY IN THE TWO DIRECTIONS.** The
    // app WRITES this month name through Intl in the tenant's own language — a
    // German utility sees `25-Okt-26` in the preview one line above — and the
    // CSV importer READS it with `%b` in the C locale, which takes English
    // abbreviations only. MEASURED on the parser: `25-Aug-26` parses;
    // `25-Okt-26`, `25-Mär-26` and `25-mars-26` are refused. Refusing is the
    // safe half (nothing is mis-dated); the harm was refusing with no reason a
    // clerk could act on, so the moment of CHOICE says it.
    const html = renderTab({ ...BRAZOS_BEND, date_format: "DD-MMM-YY" });
    expect(html).toContain('data-tracks="DEF-753"');
    expect(html).toContain("ENGLISH month names only");
    // The twelve words it accepts, so nobody guesses which spelling of October.
    expect(html).toContain("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec");
    // …and the note names the failure a German utility actually met.
    expect(html).toContain("25-Okt-26");
  });

  it("⚠ DEF-753: the other six formats carry no such note — they have no month name to trap anyone", () => {
    for (const format of ["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD", "DD.MM.YYYY", "DD-MM-YYYY", "YYYY/MM/DD"] as const) {
      const html = renderTab({ ...BRAZOS_BEND, date_format: format });
      expect(html).not.toContain('data-tracks="DEF-753"');
      expect(html).not.toContain("ENGLISH month names only");
    }
  });

  it("US-TEN-006 TC-2: the date format is what re-renders — nothing about storage changes", () => {
    const iso = renderTab({ ...BRAZOS_BEND, date_format: "YYYY-MM-DD" });
    expect(iso).toContain("2026-08-08");
    expect(iso).not.toContain("08/08/2026");
    expect(asDateFormat("DD/MM/YYYY")).toBe("DD/MM/YYYY");
    // An unknown stored format falls back to ISO rather than crashing a screen.
    expect(asDateFormat("swedish")).toBe("YYYY-MM-DD");
    // IS-8 number format maps to the ONE money formatter's locale.
    expect(localeForNumberFormat("1.234,56")).toBe("de-DE");
    expect(localeForNumberFormat("1,234.56")).toBe("en-US");
  });

  it("US-TEN-006 TC-3 / BR-TEN-022: the period card is the SERVER's computation, rendered verbatim", () => {
    const html = renderTab(BRAZOS_BEND);
    expect(html).toContain("FY2026 · Period 11");
    expect(html).toContain("08/01/2026");
    expect(html).toContain("08/31/2026");
    expect(html).toContain("09/03/2026");
    // No fiscal arithmetic exists in this screen: with no card served, it says
    // so instead of computing one.
    const noPeriod = renderTab({ ...BRAZOS_BEND, current_period: null });
    expect(noPeriod).toContain("Set the fiscal year start to see the current period.");
  });

  it("US-TEN-006 TC-4 / BR-TEN-042: the currency LOCK is the server's 409, rendered with its reason and br_ref", () => {
    // The screen never predicts the lock — it detects only that the user is
    // changing the currency, which is what triggers the BR-TEN-021 warning.
    const original = draftFromRegional(BRAZOS_BEND);
    expect(currencyIsChanging(original, original)).toBe(false);
    expect(currencyIsChanging({ ...original, currency: "CAD" }, original)).toBe(true);
    // A tenant with no currency yet is not "changing" one.
    const fresh = draftFromRegional({ ...BRAZOS_BEND, currency: null });
    expect(currencyIsChanging({ ...fresh, currency: "USD" }, fresh)).toBe(false);

    // And when the server refuses, THAT is what the user reads.
    const locked = new ApiError(409, {
      code: "BIZ-LOCKED",
      message_key: "settings.regional.currency_locked",
      params: { currency: "USD" },
      br_ref: "BR-TEN-042",
    });
    const refusal = refusalOf(locked, t);
    expect(refusal.message).toBe(
      "Currency stays USD — this utility already has financial records. Nothing was changed.",
    );
    expect(refusal.brRef).toBe("BR-TEN-042");
    const html = renderToStaticMarkup(<RefusalNotice refusal={refusal} />);
    expect(html).toContain("Currency stays USD");
    expect(html).toContain("BR-TEN-042");
    expect(html).toContain('role="alert"');
  });

  it("BR-TEN-024: the PUT carries only what changed, with numbers parsed and blanks nulled", () => {
    const original = draftFromRegional(BRAZOS_BEND);
    expect(regionalIsDirty(original, original)).toBe(false);
    expect(regionalChanges(original, original)).toEqual({});
    expect(regionalChanges({ ...original, fy_start_month: "1" }, original)).toEqual({
      fy_start_month: 1,
    });
    expect(regionalChanges({ ...original, close_day: "" }, original)).toEqual({ close_day: null });
    expect(regionalChanges({ ...original, lock_closed_periods: false }, original)).toEqual({
      lock_closed_periods: false,
    });
    // `current_period` is computed-display and can never be sent back.
    expect(Object.keys(regionalChanges(original, original))).not.toContain("current_period");
  });

  it("BR-TEN-020 / BR-TEN-038: the tab states no-restatement and the ruled closed-period behaviour", () => {
    const html = renderTab(BRAZOS_BEND);
    expect(html).toContain("Changing these does not restate historical bills.");
    expect(html).toContain("posts to the earliest open period with an audit note");
    expect(html).toContain("Only a System Admin can reopen a period.");
  });

  it.todo(
    "US-TEN-006 TC-5 (neg): 'February 30' is refused — the server owns the month/day pairing and answers settings.regional.bad_day",
  );
  it.todo(
    "US-TEN-006 TC-6 (neg): a disabled 'Español — coming soon' option — E2 with the shipped server, which accepts twelve languages since BR-SHL-041's eleven-locale expansion landed 2026-08-11 (reported)",
  );
  it.todo("US-TEN-006 TC-7 (isolation): per-tenant formats — server/RLS scope (G5)");
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-006@0733260 (story+rules snapshot hash — EP-TEN-05)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 228 passed / 71 todo across 28 files✔ (144+40 baseline unchanged; this packet adds 84 passing + 31 todo — the todos are browser/journey, server-enforcement and unwired-endpoint scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
