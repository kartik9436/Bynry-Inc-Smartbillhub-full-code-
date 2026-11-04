// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-013 (EP-SHL-05 §Stories)  Screens: every date/timestamp display (S17, S30, S33, S39, …)
// Rules:    BR-SHL-023 (tenant TZ + regional format)
// ───────────────────────────────────────────────────────
// TC tests for FE-13 DateCell: tenant Regional format + tenant timezone,
// with calendar dates immune to timezone day-shift.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DateCell, browserDateText, formatDate, regionalDateEcho } from "./DateCell";
import type { RegionalDateFormat } from "./DateCell";

describe("US-SHL-013 — DateCell (FE-13): tenant TZ + regional format rendering", () => {
  it("US-SHL-013 TC-1 (date half): due date 2026-08-25 renders '08/25/2026' (MM/DD/YYYY); switching the tenant format re-renders '25/08/2026' with no code change", () => {
    // §4 test data: Silver Creek MM/DD/YYYY vs Harbor Point DD/MM/YYYY.
    expect(formatDate("2026-08-25", "America/Boise", "MM/DD/YYYY")).toBe("08/25/2026");
    expect(formatDate("2026-08-25", "America/Boise", "DD/MM/YYYY")).toBe("25/08/2026");
    expect(formatDate("2026-08-25", "America/Boise", "YYYY-MM-DD")).toBe("2026-08-25");

    const html = renderToStaticMarkup(
      <DateCell value="2026-08-25" timeZone="America/Boise" dateFormat="MM/DD/YYYY" />,
    );
    expect(html).toContain('dateTime="2026-08-25"'); // machine value kept alongside
    expect(html).toContain("08/25/2026");
  });

  it("US-SHL-013 (calendar-date law): a date-only value never shifts a day through a timezone — the due date IS the due date", () => {
    // UTC+14 and UTC-11 would flip a Date()-parsed midnight either way.
    expect(formatDate("2026-08-25", "Pacific/Kiritimati", "MM/DD/YYYY")).toBe("08/25/2026");
    expect(formatDate("2026-08-25", "Pacific/Midway", "MM/DD/YYYY")).toBe("08/25/2026");
  });

  it("US-SHL-013 (tenant TZ): an instant converts INTO the tenant timezone — 03:30Z on the 6th is 21:30 on the 5th in America/Boise", () => {
    expect(formatDate("2026-08-06T03:30:00Z", "America/Boise", "MM/DD/YYYY")).toBe("08/05/2026");
    expect(formatDate("2026-08-06T03:30:00Z", "America/Boise", "MM/DD/YYYY", true)).toBe(
      "08/05/2026 21:30",
    );
  });

  it("US-SHL-013 (negative): malformed values and unknown timezones render verbatim — never 'Invalid Date', never a crash", () => {
    expect(formatDate("soon", "America/Boise", "MM/DD/YYYY")).toBe("soon");
    expect(formatDate("2026-08-06T03:30:00Z", "Not/AZone", "MM/DD/YYYY")).toBe(
      "2026-08-06T03:30:00Z",
    );
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-013@1e89ecb (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

describe("US-SHL-013 — six date formats (PO ruling 2026-08-10)", () => {
  // "You have to give more date formats." Three became six. All numeric: a
  // month-name format would need month names in each of the eleven BR-SHL-041
  // locales, making a format choice depend on a translation catalog.
  const CASES: ReadonlyArray<[RegionalDateFormat, string]> = [
    ["MM/DD/YYYY", "08/25/2026"],
    ["DD/MM/YYYY", "25/08/2026"],
    ["YYYY-MM-DD", "2026-08-25"],
    ["DD.MM.YYYY", "25.08.2026"],
    ["DD-MM-YYYY", "25-08-2026"],
    ["YYYY/MM/DD", "2026/08/25"],
  ];

  it.each(CASES)("renders a calendar date as %s", (format, expected) => {
    expect(formatDate("2026-08-25", "UTC", format)).toBe(expected);
  });

  it("DD-MMM-YY renders a localized month name and a 2-digit year", () => {
    // PO 2026-08-10 "we also need DD-MMM-YY". The month NAME comes from Intl in
    // the app's language, which is why this one format may carry prose at all.
    expect(formatDate("2026-08-25", "UTC", "DD-MMM-YY", false, "en")).toBe("25-Aug-26");
    expect(formatDate("2026-01-02", "UTC", "DD-MMM-YY", false, "en")).toBe("02-Jan-26");
  });

  it("DD-MMM-YY is already correct in the other BR-SHL-041 locales", () => {
    // No catalogue entry exists for any of these — Intl ships them, so adding a
    // twelfth language cannot leave this format stale.
    for (const locale of ["de", "es", "fr", "it", "pt-BR", "ja", "ko", "hi", "id"]) {
      const out = formatDate("2026-08-25", "UTC", "DD-MMM-YY", false, locale);
      expect(out.startsWith("25-")).toBe(true);
      expect(out.endsWith("-26")).toBe(true);
    }
    // …and they are genuinely localized, not English in disguise. (German is a
    // poor witness here: its August abbreviation IS "Aug". Spanish and Japanese
    // are not.)
    expect(formatDate("2026-08-25", "UTC", "DD-MMM-YY", false, "es")).toBe("25-ago-26");
    expect(formatDate("2026-08-25", "UTC", "DD-MMM-YY", false, "ja")).toBe("25-8\u6708-26");
    expect(formatDate("2026-10-25", "UTC", "DD-MMM-YY", false, "de")).toBe("25-Okt-26");
  });

  it("keeps a calendar date the SAME date in every zone (BR-SHL-023)", () => {
    // The new formats must not reintroduce a Date() round-trip: 2026-08-25 is
    // the 25th in Honolulu and in New York alike.
    for (const [format, expected] of CASES) {
      expect(formatDate("2026-08-25", "Pacific/Honolulu", format)).toBe(expected);
      expect(formatDate("2026-08-25", "America/New_York", format)).toBe(expected);
    }
  });
});

// ── CR-043 finding 15 — a date field printing its own value twice ──────────
//
// PO, on the Run bills wizard: *Period from* showed `08/01/2026` in the picker
// and `08/01/2026` again as grey text underneath it. The grey line is IS-8 and
// is not a bug — the native control renders in the BROWSER's locale, never the
// tenant's — so the fix is to show it only where it says something new.

describe("regionalDateEcho — IS-8 without saying it twice (CR-043 finding 15)", () => {
  it("is SILENT when the browser is already printing exactly the tenant format", () => {
    // A US tenant on a US browser: the picker reads 08/01/2026 and so did the
    // line beneath it. Nothing is lost by dropping the second copy.
    expect(regionalDateEcho("2026-08-01", "MM/DD/YYYY", "en-US")).toBeNull();
    expect(regionalDateEcho("2026-08-01", "YYYY-MM-DD", "en-CA")).toBeNull();
  });

  it("SPEAKS whenever the tenant's format differs — which is the whole reason it exists", () => {
    // ⛔ THE CASE THAT MUST NOT REGRESS. A German tenant on a US-configured
    // browser sees `08/01/2026` in the box and their format is `01.08.2026`.
    // This line is the ONLY place their format appears; deleting it outright,
    // which is what "remove the duplicate" would have meant, breaks IS-8 for
    // exactly the tenants IS-8 was written for.
    expect(regionalDateEcho("2026-08-01", "DD.MM.YYYY", "en-US")).toBe("01.08.2026");
    expect(regionalDateEcho("2026-08-01", "DD-MMM-YY", "en-US")).toBe("01-Aug-26");
    expect(regionalDateEcho("2026-08-01", "MM/DD/YYYY", "de-DE")).toBe("08/01/2026");
  });

  it("errs toward SHOWING it — an empty value says nothing, an unreadable one says the format", () => {
    expect(regionalDateEcho("", "MM/DD/YYYY", "en-US")).toBeNull(); // nothing to echo
    // A locale tag Intl cannot resolve must not silently suppress IS-8.
    expect(browserDateText("2026-08-01", "not a locale")).toBeNull();
    expect(regionalDateEcho("2026-08-01", "MM/DD/YYYY", "not a locale")).toBe("08/01/2026");
  });

  it("never routes a calendar date through a zone (BR-SHL-023, this file's law)", () => {
    // The comparison builds a Date to hand to Intl. Noon UTC + timeZone:"UTC"
    // is why 2026-08-01 cannot become 07-31 for a browser east or west of it.
    expect(browserDateText("2026-08-01", "en-US")).toBe("08/01/2026");
    expect(browserDateText("2026-01-01", "en-US")).toBe("01/01/2026");
    expect(browserDateText("2026-12-31", "en-US")).toBe("12/31/2026");
  });
});
