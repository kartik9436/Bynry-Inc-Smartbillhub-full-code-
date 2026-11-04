// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-006 (EP-TEN-05)  Screens: S8 (Settings → Company → Regional)
// Rules:    BR-TEN-081 (a typed posting DATE is midnight in the UTILITY'S OWN timezone —
//           PO 2026-08-12, OQ-153) · BR-TEN-020 (display-time transforms only) ·
//           BR-SHL-033 (a type-ahead is for lists PAST LONG_LIST_THRESHOLD; a list of
//           eight is a dropdown) · BR-TEN-024 (the PUT carries only what changed)
// Defect:   DEF-082 — "you did not fix time zone drop down in company settings"
//           (Product Owner, 2026-08-12, working chat session)
// ───────────────────────────────────────────────────────
// DEF-082, measured on the rendered output rather than argued.
//
// The field was NOT missing — it shipped 2026-08-09 as a SearchSelectField, a
// type-ahead combobox. Three things made it read as absent to the person using
// it, and each is asserted below:
//   1. It is not a drop-down. It is a text box that opens nothing on click and
//      offers nothing until you type — over a list of EIGHT, where BR-SHL-033's
//      own threshold (LONG_LIST_THRESHOLD = 10) says a type-ahead starts.
//      `05-prototype/UtilityBilling.html` line 4517 draws a `<select>`.
//   2. It renders EMPTY when the stored zone is outside the eight it hardcodes
//      — measured before the fix: `<input id="timezone" … value=""/>` for a
//      utility holding `America/Detroit`. The clock was set and invisible.
//   3. Nothing on the control said what the zone DOES. BR-TEN-081 is the reason
//      the field matters, and the screen never mentioned it.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { RegionalSettings } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { LONG_LIST_THRESHOLD } from "@/components/FormModal";
import { ToastProvider } from "@/components/Toast";

import {
  TIMEZONE_OPTIONS,
  RegionalTab,
  draftFromRegional,
  regionalChanges,
  timezoneOptions,
} from "./SettingsRegionalTab";

// §4 test data is Brazos Bend (America/Chicago); the Detroit variant is the
// utility whose stored zone the eight-item list cannot express.
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
  current_period: null,
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

/** The markup of the one field, so an assertion cannot pass on a neighbour. */
function timezoneField(html: string): string {
  const start = html.indexOf('for="timezone"');
  expect(start).toBeGreaterThan(0);
  return html.slice(start, html.indexOf("</select>", start) + "</select>".length);
}

describe("DEF-082 — the timezone control on Settings → Company → Regional", () => {
  it("DEF-082: it is a DROP-DOWN — every zone is visible without typing (BR-SHL-033)", () => {
    const field = timezoneField(renderTab(BRAZOS_BEND));
    expect(field).toContain('<select id="timezone"');
    // Not the type-ahead: a combobox over eight options is below the very
    // threshold BR-SHL-033 sets for one, and it opens nothing on a click.
    expect(field).not.toContain('role="combobox"');
    expect(TIMEZONE_OPTIONS.length).toBeLessThanOrEqual(LONG_LIST_THRESHOLD);
    for (const zone of TIMEZONE_OPTIONS) {
      expect(field).toContain(`value="${zone}"`);
    }
    // A1 §S8's eight, Phoenix (no DST) and the non-contiguous zones included.
    expect(TIMEZONE_OPTIONS).toContain("America/Phoenix");
    expect(TIMEZONE_OPTIONS).toContain("Pacific/Honolulu");
    expect(TIMEZONE_OPTIONS).toContain("America/Puerto_Rico");
  });

  it("DEF-082: the utility's OWN stored zone is shown and selected, even outside the eight", () => {
    // Measured before the fix: this rendered `value=""` — a clock that was set,
    // and a screen that showed nothing. One Save of any other field would then
    // have looked like a deliberate choice of blank.
    const field = timezoneField(renderTab({ ...BRAZOS_BEND, state: "MI", timezone: "America/Detroit" }));
    expect(field).toContain('<option value="America/Detroit" selected="">America/Detroit</option>');
    // The stored zone leads the list, and the eight are all still offered.
    expect(timezoneOptions("America/Detroit")[0]).toBe("America/Detroit");
    for (const zone of TIMEZONE_OPTIONS) {
      expect(timezoneOptions("America/Detroit")).toContain(zone);
    }
    // A stored zone that IS one of the eight neither duplicates nor reorders.
    expect(timezoneOptions("America/Chicago")).toEqual([...TIMEZONE_OPTIONS]);
    expect(timezoneOptions("")).toEqual([...TIMEZONE_OPTIONS]);
  });

  it("DEF-082 / BR-TEN-081: the control says what the zone DOES, in the user's words", () => {
    const html = renderTab(BRAZOS_BEND);
    expect(html).toContain("A date typed by staff is recorded at midnight in this timezone.");
  });

  it("DEF-082 (round trip): the zone picked on the screen is the zone the PUT carries", () => {
    const original = draftFromRegional(BRAZOS_BEND);
    expect(original.timezone).toBe("America/Chicago");
    expect(regionalChanges({ ...original, timezone: "America/Denver" }, original)).toEqual({
      timezone: "America/Denver",
    });
    // BR-TEN-024: touching another field never re-sends the zone, so a save
    // elsewhere on the tab can never quietly restate the utility's clock.
    expect(regionalChanges({ ...original, close_day: "5 days" }, original)).toEqual({
      close_day: "5 days",
    });
    // ...and a zone outside the eight survives a load with nothing else touched.
    const detroit = draftFromRegional({ ...BRAZOS_BEND, timezone: "America/Detroit" });
    expect(detroit.timezone).toBe("America/Detroit");
    expect(regionalChanges(detroit, detroit)).toEqual({});
  });

  it.todo(
    "DEF-082 (browser): clicking the closed control opens the list — the affordance the type-ahead never had; needs a live DOM (no jsdom in this suite)",
  );
  // BR-TEN-081 (write half) — **RETIRED 2026-08-15, DEF-094 FIXED.** This was a
  // named `it.todo` reading "…apps/payments/api._moment still anchors at
  // midnight UTC (OUT OF THIS LANE, reported)", and it did its job: it failed
  // loudly rather than letting DEF-082's closure read as the whole rule shipped.
  // `_moment` now anchors a bare date at midnight in the tenant's zone, read
  // through the payments seam from tenancy's own `tenant_timezone()`. The proof
  // is a BACKEND one and lives where the behaviour does —
  // 06-backend/tests/test_def_094_typed_date_write_half.py, which records the
  // typed 22 August as `2026-08-22T05:00:00Z` (22 Aug 00:00 Central) and was
  // red-proved reading back `2026-08-21` under the old anchor. A frontend todo
  // restating a closed backend guarantee would be the very thing DEF-094 is
  // about: a claim in one place about code in another (hard-won law 1).
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-006@0733260 (story+rules snapshot hash — EP-TEN-05; the DEF-082 defect lane, whose field US-TEN-006 §5 owns)
// generated: 2026-08-15 by story-coder v1 (DEF-082 tenant-timezone lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: proved RED first (law 7) on the SHIPPED markup, quoted in the file header — `expected 'for="timezone">Timezone</label><div c…' to contain '<select id="timezone"'` and, for the Detroit tenant, `<input id="timezone" … value=""/>`. After the fix 4 passed / 2 todo. tsc✔ eslint✔ vitest 947 passed / 185 todo across 65 files✔ (the 5 pre-lane failures in MoneyCell/BillDetailPage were the concurrent DEF-088 lane's and cleared while this lane ran)
// exceptions: ONE todo remains and it is out of reach here, not out of mind —
//         the click-to-open affordance needs a live DOM (this suite has no jsdom).
//         The SECOND todo (the WRITE half of BR-TEN-081) was RETIRED 2026-08-15 when
//         DEF-094 was fixed: apps/payments/api._moment now anchors a typed date at
//         midnight in the tenant's zone, and the proof lives with the behaviour in
//         06-backend/tests/test_def_094_typed_date_write_half.py. The retired todo is
//         replaced by a comment saying so rather than deleted, because the reason it
//         existed — a closed defect that claimed a guarantee it had not delivered — is
//         the finding, not the todo
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
