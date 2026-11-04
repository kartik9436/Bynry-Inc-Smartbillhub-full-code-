// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:   US-MET-002 (S15 unit detail — the Occupancy tab) · CR-089 `F4`
//          Screens: S15 (PRM-03, Occupancy)
// Spec:    04-docs/05-modules/04-metering/conformance/CR-089-p083-unit-occupancy.md
//          — rows 1 (no `Left owing`), 2 (no footer), 6 (an expired explanation
//          still on screen), 8 (order), 9–13 (labels and the pill), 16 (weight)
//          and 18 (a common area is never vacant)
// Defect:  DEF-MET-4766 — the tab leaves out facts the payload it already reads
//          is serving
// Rules:   DEF-127 (a null balance is NOT zero) · BR-MET-101 (the common-area
//          flag) · B14 rule 34 (one pair of words per concept) · B14 rule 37
//          (a drawn figure is an illustration) · CLAUDE.md hard rule 2 (money
//          stored to four decimals, displayed to two)
// ───────────────────────────────────────────────────────
// ⚠ **NOT ONE DRAWN FIGURE IS ASSERTED HERE** (B14 rule 37, ratified
// 2026-09-10: *"Treat every number drawn in a wireframe as an illustration,
// never a fact to build to."*). The blueprint inks one account number and start
// year into this frame and a DIFFERENT pair for the same tenancy two pages
// earlier — read as facts those are irreconcilable, read as illustrations they
// agree about the SHAPE, and the shape is what this file pins. Every value
// below is this harness's own.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { AccountRow, UnitRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { UnitDetailPage, unitAccountsQueryKey, unitDetailQueryKey } from "./UnitDetailPage";
import { premisesAssetsQueryKey } from "./PremisesDetailPage";
import { UNIT } from "./unitAccountFixture";

const TEST_TENANT = "brazosbend";
const UNIT_ID = "u-101a";
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;

function tenancy(over: Partial<AccountRow>): AccountRow {
  return {
    id: `acc-${String(over.account_no)}`,
    account_no: "AC-A",
    name: "A Tenant",
    status_name: "Active",
    currency: "USD",
    balance: null,
    balance_currency: null,
    opened_at: "2025-01-01",
    closed_at: null,
    ...over,
  } as unknown as AccountRow;
}

const EARLIER = tenancy({
  account_no: "AC-EARLIER",
  name: "An Earlier Tenant",
  status_name: "Closed",
  opened_at: "2024-02-03",
  closed_at: "2025-05-28",
  // The LEDGER's own figure, on the very row this tab already reads.
  balance: "61.400000",
  balance_currency: "USD",
});
const CURRENT = tenancy({
  account_no: "AC-CURRENT",
  name: "The Current Tenant",
  status_name: "Active",
  opened_at: "2025-06-01",
  closed_at: null,
  balance: "0.000000",
  balance_currency: "USD",
});

function renderOccupancy(rows: readonly AccountRow[], unit: Partial<UnitRow> = {}): string {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(unitDetailQueryKey(UNIT_ID), { ...UNIT, ...unit });
  client.setQueryData(unitAccountsQueryKey(UNIT_ID), { count: rows.length, results: rows });
  client.setQueryData(premisesAssetsQueryKey(UNIT.premises_id), {
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  // Mounted under the REAL path pattern — a bare `MemoryRouter` leaves
  // `useParams().tenant` undefined and every link the page builds comes out
  // protocol-relative, which reads as a perfectly good string to `toContain`
  // (hard-won law 2's fixture clause).
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/units/${UNIT_ID}?tab=occupancy`]}>
          <Routes>
            <Route path="/:tenant/premises/units/:unitId" element={<UnitDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** What a reader actually sees: `renderToStaticMarkup` escapes an apostrophe to
 *  `&#x27;`, so a catalogue sentence carrying one never matches the raw markup —
 *  a false RED that reads exactly like a missing string. */
function asRead(html: string): string {
  return html.replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&");
}

/** The header cells of the occupancy table, in the order they render. */
function headers(html: string): string[] {
  const table = html.slice(html.indexOf("<thead>"), html.indexOf("</thead>"));
  return [...table.matchAll(/<th[^>]*>(.*?)<\/th>/g)].map((m) => m[1].replace(/<[^>]*>/g, ""));
}

describe("U8 · the Occupancy table draws the six drawn columns", () => {
  it("names them in the drawn order, with the money column last but one", () => {
    // The frame: Occupant · Account · From · To · Left owing · Status. The
    // built table had FIVE and no money column at all, while the figure came
    // back on the very query this tab makes.
    expect(headers(renderOccupancy([CURRENT, EARLIER]))).toEqual([
      t("metering.units.occupancy.col.occupant"),
      t("metering.units.occupancy.col.account"),
      t("metering.units.occupancy.col.start"),
      t("metering.units.occupancy.col.end"),
      t("metering.units.occupancy.col.leftOwing"),
      t("metering.units.col.status"),
    ]);
  });

  it("says From and To, not Start and End", () => {
    // The two ends of a TENANCY, which is what this table is a history of.
    expect(t("metering.units.occupancy.col.start")).toBe("From");
    expect(t("metering.units.occupancy.col.end")).toBe("To");
  });

  it("draws the money right-aligned and tabular, which is the frame's own RULES line", () => {
    const html = renderOccupancy([CURRENT, EARLIER]);
    const cells = [...html.matchAll(/<td class="([^"]*)"/g)].map((m) => m[1]);
    expect(cells.some((c) => c.includes("text-right") && c.includes("tabular-nums"))).toBe(true);
  });

  it("renders what the tenant LEFT OWING through MoneyCell, at two decimals", () => {
    // CLAUDE.md hard rule 2 — stored to four, displayed to two. `DEF-595` put
    // `48.450000 USD` on this very screen once.
    const html = renderOccupancy([CURRENT, EARLIER]);
    expect(html).toContain("$61.40");
    expect(html).not.toContain("61.400000");
  });

  it("a balance the books could not answer is NOT drawn as zero (DEF-127)", () => {
    // The single most dangerous substitution on this column: `0.00` under
    // *Left owing* reads as *this tenant settled up*.
    const unreadable = tenancy({
      account_no: "AC-UNREADABLE",
      status_name: "Closed",
      opened_at: "2024-01-01",
      closed_at: "2024-12-31",
      balance: null,
      balance_currency: null,
    });
    const html = renderOccupancy([unreadable]);
    expect(asRead(html)).toContain(t("metering.units.account.balanceUnavailable"));
    expect(html).not.toContain("$0.00");
  });
});

describe("U8 · the words on a row are the tenancy's, not the account's", () => {
  it("an open tenancy reads 'still here' rather than 'Current' in the To column", () => {
    expect(renderOccupancy([CURRENT, EARLIER])).toContain(t("metering.units.occupancy.current"));
    expect(t("metering.units.occupancy.current")).toBe("still here");
  });

  it("an open VACANCY does not borrow the tenancy's word", () => {
    // *still here* over an empty flat is the one reading this column must never
    // produce. A trailing gap is measured to today and says so its own way.
    const closedOnly = tenancy({
      account_no: "AC-GONE",
      status_name: "Closed",
      opened_at: "2024-01-01",
      closed_at: "2024-06-30",
      balance: "0.000000",
      balance_currency: "USD",
    });
    const html = renderOccupancy([closedOnly]);
    expect(html).toContain(t("metering.units.occupancy.stillEmpty"));
  });

  it("the status cell is a PILL carrying the occupancy word, never the account's status name", () => {
    const html = renderOccupancy([CURRENT, EARLIER]);
    expect(html).toContain(t("metering.units.occupancy.state.current"));
    expect(html).toContain(t("metering.units.occupancy.state.closed"));
    expect(html).toContain(t("metering.units.occupancy.state.vacantPeriod"));
    // A pill, so colour is never the only signal (the frame's RULES line).
    expect(html).toMatch(/<span class="pill[^"]*">[^<]*Current</);
  });

  it("the occupant of the OPEN tenancy is bold and a past one is not", () => {
    const html = renderOccupancy([CURRENT, EARLIER]);
    expect(html).toContain("<strong>The Current Tenant</strong>");
    expect(html).not.toContain("<strong>An Earlier Tenant</strong>");
  });
});

describe("U8 · order, footer, and the paragraph that expired", () => {
  it("reads NEWEST FIRST, with the gap still between the two tenancies it separates", () => {
    const html = renderOccupancy([CURRENT, EARLIER]);
    const current = html.indexOf("The Current Tenant");
    const vacancy = html.indexOf('data-occupancy-row="vacancy"');
    const earlier = html.indexOf("An Earlier Tenant");
    expect(current).toBeGreaterThan(-1);
    expect(vacancy).toBeGreaterThan(current);
    expect(earlier).toBeGreaterThan(vacancy);
  });

  it("counts the rows and the vacancies in the drawn footer line", () => {
    const html = renderOccupancy([CURRENT, EARLIER]);
    expect(html).toContain('data-tab-footer-counts=""');
    expect(html).toContain(t("metering.units.occupancy.footerShowing", { count: 3 }));
    expect(html).toContain(t("metering.units.occupancy.footerVacant", { count: 1 }));
  });

  it("says so when a unit has never stood empty, rather than leaving the clause off", () => {
    const html = renderOccupancy([CURRENT]);
    expect(html).toContain(t("metering.units.occupancy.footerVacantNever"));
  });

  it("no longer explains why r10's Closing read and Final bill are missing", () => {
    // An explained absence whose explanation EXPIRED: the blueprint has since
    // ratified a six-column table containing neither, so the paragraph is no
    // longer owed to a clerk and the frame's budget is "six columns, no prose".
    // `DEF-509` stays OPEN — the gap is real — but the prose goes.
    const html = renderOccupancy([CURRENT, EARLIER]);
    expect(html).not.toContain('data-tracks="DEF-509"');
    // The `OQ-316` note STAYS: a live question about money on rows that ARE
    // drawn is a different kind of absence from an explanation of something the
    // drawing no longer asks for.
    expect(html).toContain('data-tracks="OQ-316"');
  });
});

describe("U8 · a common area is never vacant (BR-MET-101)", () => {
  it("draws no vacancy row for one, however wide the gap between its accounts", () => {
    const html = renderOccupancy([CURRENT, EARLIER], { is_common_area: true });
    expect(html).not.toContain('data-occupancy-row="vacancy"');
    expect(html).toContain('data-occupancy-row="tenancy"');
  });

  it("an empty one gets the common-area sentence, not 'nobody has ever been attached'", () => {
    const html = renderOccupancy([], { is_common_area: true });
    expect(html).toContain('data-occupancy-empty="common-area"');
    expect(asRead(html)).toContain(t("metering.units.account.commonAreaOwnerBilled"));
    expect(asRead(html)).not.toContain(t("metering.units.occupancy.none"));
  });
});
