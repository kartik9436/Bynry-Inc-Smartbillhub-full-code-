// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-4739 — "Five property tabs use the small in-panel table, so
//          search, filters, the column chooser, pagination and footer counts
//          are absent from all five at once"
//          DEF-4740 — "Nine drawn columns and rows are absent from six premises
//          screens although the API already serves every one of them"
// Screens: PRM-02 · Premises → a premise → Units | Assets | Audit log
// Drawn:   04-docs/05-modules/04-metering/conformance/CR-089-p022-property-units.md
//          · CR-089-p028-property-assets.md · CR-089-p034-property-audit-log.md
//          (from `05-prototype/Premises & Units Blueprint 2.pdf`, pages 22-24,
//          28-32 and 34-36 — rendered and read as PAGES, not as extracted text)
// Rules:   BR-SHL-010 (only DECLARED capabilities render) · BR-SHL-011 (URL
//          grammar) · BR-SHL-013 (column visibility) · BR-MET-036 (occupancy is
//          DERIVED) · BR-MET-094 + BR-CUS-170 (a vacancy IS billed, to the
//          owner) · BR-MET-101 (a common area is a unit with a flag) ·
//          BR-AST-004 (the category is the server's) · BR-AST-500 (the size
//          class) · BR-AUD-003 / BR-AUD-010 (one audit surface) · B14 rule 12
//          (the toolbar's grammar) · B14 rule 32 (the description budget)
// ───────────────────────────────────────────────────────
//
// WHY THIS IS ITS OWN FILE AND NOT MORE CASES IN `PremisesPage.test.tsx`.
// Three lanes are working in this tree and that file is one of the ones they
// are in. A pathspec commit takes the WHOLE file, so adding to it would either
// publish a sibling's in-flight work or revert it (CLAUDE.md law 11,
// mechanisms two and five). The cases that had to move — the ones asserting the
// superseded design — were edited there because they could not stay; everything
// NEW is here, where this lane is the only writer.
//
// ⚠ **WHAT THIS FILE CANNOT TELL YOU, STATED RATHER THAN GLOSSED.** It renders
// to static markup, so it can prove PRESENCE, ORDER and the exact STRING of
// every drawn label — which is three of the seven checks the UI skill's §4
// comparison asks for. Alignment, spacing rhythm, weight and colour need a
// browser and a person, and there is no stack in this container. Those four are
// reported as unverified rather than asserted here in a form that would pass
// over a wrong screen.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { AuditListResult, AuditRow, PremisesDetail, UnitRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  AuditFromCell,
  PremisesDetailPage,
  entityAuditQueryKey,
  premisesAssetsQueryKey,
  premisesDetailQueryKey,
  tabMatches,
  tabRowsForPage,
} from "./PremisesDetailPage";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

// ── Fixtures ───────────────────────────────────────────────────────────────
// Deliberately this file's own, for the reason in the header: the shared test
// file's fixtures cannot be imported without importing its describe blocks, and
// this lane must not be a writer in it.

function premise(over: Partial<PremisesDetail> = {}): PremisesDetail {
  return {
    id: "p-101",
    premise_no: "P-00101",
    name: null,
    address_line: "412 Cypress Row",
    city: "Silver Creek",
    state: "TX",
    postal_code: "78611",
    inside_city_limits: null,
    area_code: null,
    area_name: null,
    area_parent_code: null,
    area_path: null,
    premises_type: "apartment",
    premises_type_name: "Apartment complex",
    services_available: ["electric", "water"],
    owner_manager: "Creekside Holdings LP",
    owner: null,
    owner_unmatched: false,
    external_ref: null,
    gis_unchecked: false,
    lat: "30.752104",
    lng: "-98.238391",
    gis_checked_at: null,
    gis_checked_by: null,
    status: "active",
    units: 4,
    unit_rows: [],
    units_common: 0,
    ...over,
  };
}

function unitRow(over: Partial<UnitRow> = {}): UnitRow {
  return {
    id: "u-1",
    unit_no: "U-01144",
    premises_id: "p-101",
    premise_no: "P-00101",
    premise_address: "412 Cypress Row",
    label: "1",
    unit_type: "residential",
    floor_label: "Ground",
    square_feet: null,
    rate_plan_id: null,
    plan_effective_from: null,
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    lat: null,
    lng: null,
    point: { lat: null, lng: null, source: "premises" as const },
    active: true,
    services: ["electric", "water"],
    meters: [
      { id: "m1", asset_no: "E-01", qualifier: null },
      { id: "m2", asset_no: "W-01", qualifier: null },
    ],
    occupancy: "occupied",
    occupant: "M. Alvarez",
    account_no: "A-10517",
    status: "active",
    metered_services: [],
    sub_metered: false,
    ...over,
  };
}

const OWED_6140 = {
  account_id: "acc-1",
  account_no: "A-10517",
  balance: "61.4000",
  balance_currency: "USD",
  balance_basis: "posting",
  balance_unavailable: [] as string[],
  balance_not_yet_billable: false,
};

function auditRow(over: Partial<AuditRow> = {}): AuditRow {
  return {
    id: "au-1",
    created_at: "2026-09-08T15:42:00Z",
    actor: { id: "u-1", name: "D. Whitfield" },
    action: "premises.updated",
    entity_type: "premises",
    entity_id: "p-101",
    summary: "route: — → Route 12",
    source: null,
    ...over,
  };
}

function auditResult(rows: Partial<AuditRow>[]): AuditListResult {
  const results = rows.map((row, index) => auditRow({ id: `au-${String(index + 1)}`, ...row }));
  return {
    page: { count: results.length, next: null, previous: null, results },
    window: { window: "hot", from: "2024-09-08T00:00:00Z" },
  };
}

function renderTab(
  path: string,
  detail: PremisesDetail,
  assets: unknown[] = [],
  audit: AuditListResult | null = null,
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(premisesDetailQueryKey(detail.id), detail);
  queryClient.setQueryData(premisesAssetsQueryKey(detail.id), {
    count: assets.length,
    next: null,
    previous: null,
    results: assets,
  });
  if (audit !== null) {
    queryClient.setQueryData(entityAuditQueryKey("premises", detail.id), audit);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* ⚠ MOUNTED UNDER THE REAL PATH PATTERN. A bare `MemoryRouter` with no
            `/:tenant/…` route leaves `useParams().tenant` undefined and every
            link the page builds comes out `//premises/…` — a protocol-relative
            URL to another host, which reads as a perfectly good string to
            `toContain` (hard-won law 2). */}
        <MemoryRouter initialEntries={[`/${TENANT}${path}`]}>
          <Routes>
            <Route path="/:tenant/premises/:premisesId" element={<PremisesDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Where each `<th>` sits, so ORDER can be asserted in a static render. */
function headerOrder(html: string, headers: string[]): number[] {
  return headers.map((header) => html.indexOf(`>${header}<`));
}

/** ORDER is the §4 check that catches a right column in the wrong place. */
function expectHeadersInOrder(html: string, headers: string[]): void {
  const positions = headerOrder(html, headers);
  for (const [index, at] of positions.entries()) {
    expect(at, `the drawn header "${headers[index]}" is not on the screen`).toBeGreaterThan(-1);
  }
  expect(positions, "the drawn columns are not in the drawn order").toEqual(
    [...positions].sort((a, b) => a - b),
  );
}

// ── The paging arithmetic, without a browser ───────────────────────────────
//
// These two are where an off-by-one hides, and they are pure precisely so the
// boundary can be driven directly rather than inferred from rendered rows.

describe("DEF-4739 — the client-side page and search these three tabs apply", () => {
  /** 60 rows, so the 50-row default page has a real boundary to get wrong. */
  const rows = Array.from({ length: 60 }, (_, index) => `row-${String(index)}`);
  const at = (page: number) =>
    tabRowsForPage(rows, { q: "", sort: "x", dir: "asc", page, per: 50, filters: {} });

  it("page one is the first `per` rows and page two starts exactly after them", () => {
    expect(at(1)).toHaveLength(50);
    expect(at(1)[0]).toBe("row-0");
    expect(at(1)[49]).toBe("row-49");
    // ⚠ THE BOUNDARY, WHICH IS THE ONLY THING THIS FUNCTION CAN GET WRONG: no
    // row is dropped between the pages and none is drawn on both.
    expect(at(2)).toHaveLength(10);
    expect(at(2)[0]).toBe("row-50");
    expect([...at(1), ...at(2)]).toEqual(rows);
    // A page past the end is EMPTY rather than a crash — `DataTable` clamps
    // the number, and this is what it clamps against.
    expect(at(3)).toEqual([]);
  });

  it("an empty query matches everything, which is what a sub-two-character search sends", () => {
    // IS-3: `DataTable`'s debouncer fires `""` for anything under two
    // characters, so one letter must narrow NOTHING here exactly as it narrows
    // nothing on a served list.
    expect(tabMatches(["Alvarez", null], "")).toBe(true);
    expect(tabMatches(["Alvarez", null], "alva")).toBe(true);
    expect(tabMatches(["Alvarez", null], "ALVA")).toBe(true);
    expect(tabMatches([null, undefined], "alva")).toBe(false);
    // A field the server did not send is not a match and is not a crash.
    expect(tabMatches([undefined], "")).toBe(true);
  });
});

// ── The Units tab ──────────────────────────────────────────────────────────

describe("DEF-4739 / DEF-4740 — PRM-02 Units, against the drawn frame", () => {
  const UNITS: UnitRow[] = [
    unitRow(),
    unitRow({
      id: "u-4",
      unit_no: "U-01147",
      label: "4",
      floor_label: null,
      occupancy: "vacant",
      occupant: null,
      account_no: null,
      status: "vacant",
      meters: [],
      owed: null,
    }),
  ];

  it("the shared table furniture is there — search, the All chip, + Filter, Columns, the pager", () => {
    const html = renderTab("/premises/p-101?tab=units", premise({ unit_rows: UNITS }));
    // The drawn toolbar, left to right: `Search units…` · `ALL` · `+ Filter ⌄`.
    expect(html).toContain('placeholder="Search units…"');
    expect(html).toContain(">All<");
    expect(html).toContain("+ Filter ");
    // The column chooser and the pagination footer, which `PlainTable` has no
    // way to draw and which is the whole of DEF-4739.
    expect(html).toContain('aria-label="Show or hide columns"');
    expect(html).toContain('class="table-pager"');
    expect(html).toContain("1–2 of 2");
  });

  it("the EIGHT drawn columns, in the drawn order, with Owed BEFORE Status", () => {
    const html = renderTab("/premises/p-101?tab=units", premise({ unit_rows: UNITS }));
    // ⚠ `Unit` is the sorted identity column, so its header is a sort button
    // and `>Unit<` is followed by the arrow span — which is why the helper
    // matches `>Unit<` and not `>Unit</th>`.
    expectHeadersInOrder(html, ["Unit", "Type", "Floor", "Meters", "Occupant", "Owed", "Status"]);
    // ⚠ **AND `Unit ID` IS NOT A COLUMN OF ITS OWN (`DEF-4740`).** The tab drew
    // `Unit ID` and `Unit` side by side; the blueprint draws ONE cell.
    expect(html).not.toContain(">Unit ID<");
  });

  it("column one is ONE cell — the label leads, the unit number sits under it, quiet", () => {
    const html = renderTab("/premises/p-101?tab=units", premise({ unit_rows: [unitRow()] }));
    expect(html).toContain('data-unit-no="U-01144"');
    // Both are shown and the LABEL is the one the eye meets first: *"a clerk
    // reads the number down the phone and says the label to a resident."*
    expect(html.indexOf(">1<")).toBeLessThan(html.indexOf("U-01144"));
    // The blueprint corrects an earlier draft of its own here, in writing: the
    // unit number is `unit_no`, the tenant's own printed series, and B14 rule
    // 31 does not reach it. It is still not a uuid.
    expect(html).not.toContain("u-1<");
  });

  it("Floor is drawn, and an unrecorded floor is drawn as an ABSENCE rather than blank", () => {
    const html = renderTab("/premises/p-101?tab=units", premise({ unit_rows: UNITS }));
    expect(html).toContain("Ground");
    expect(html).toContain("none yet");
  });

  it("the vacancy sentence is in the OCCUPANT cell, where the blueprint draws it", () => {
    const html = renderTab("/premises/p-101?tab=units", premise({ unit_rows: UNITS }));
    // An occupied unit: a NAME and its account, not a state word.
    expect(html).toContain("M. Alvarez");
    expect(html).toContain("A-10517");
    expect(html).toContain('data-occupant-state="named"');
    // A vacant one: *"a dash on that row reads as `nothing is billed`, which is
    // the opposite of true"* (BR-MET-094 + BR-CUS-170).
    expect(html).toContain('data-occupant-state="vacant"');
    expect(html).toContain("Vacant — base charges bill to the owner");
  });

  it("a REAL zero prints 0.00 and an unmeasured unit never manufactures one", () => {
    // PO ruling 2026-09-10: the sentence moves to Occupant and `Owed` shows
    // `0.00` — *"but keep the existing protection: show 0.00 only when the
    // balance really is zero, never manufactured over a real debt."*
    const zero = renderTab(
      "/premises/p-101?tab=units",
      premise({ unit_rows: [unitRow({ owed: { ...OWED_6140, balance: "0.0000" } })] }),
    );
    expect(zero).toContain("$0.00");
    expect(zero).toContain('data-owed-state="figure"');

    // …and the unlet row, whose books were never asked at all. DEF-138 is the
    // record of what a manufactured zero costs: a guard reading a column
    // nobody writes and answering *nothing owed* over an unpaid 108.88.
    const unlet = renderTab("/premises/p-101?tab=units", premise({ unit_rows: UNITS }));
    expect(unlet).toContain('data-owed-state="no-account"');
    expect(unlet).toContain("Not measured");
    expect(unlet).not.toContain("$0.00");
  });

  it("the footer says how many are occupied and how many are vacant", () => {
    const html = renderTab("/premises/p-101?tab=units", premise({ unit_rows: UNITS }));
    expect(html).toContain('data-tab-footer-counts=""');
    expect(html).toContain("1 occupied, 1 vacant");
  });

  it("B14 rule 32 — the drawn tab carries NO PROSE, and the old hint line is gone", () => {
    // *"Eight columns, one search, no prose"*: no explainer paragraph, no
    // callout, no hint line anywhere on this tab.
    const html = renderTab("/premises/p-101?tab=units", premise({ unit_rows: UNITS }));
    expect(html).not.toContain("Accounts attach to units, not to premises.");
  });

  it("no units at all OFFERS to add them, and says a property with none bills nothing", () => {
    const html = renderTab("/premises/p-101?tab=units", premise({ unit_rows: [] }));
    expect(html).toContain("No units on this property yet");
    expect(html).toContain("A property with no units bills nothing.");
    expect(html).toContain("+ New unit");
    // A18 §1: the empty block replaces the whole table region — never an empty
    // header row over nothing.
    expect(html).not.toContain('class="data-table"');
  });
});

// ── The Assets tab ─────────────────────────────────────────────────────────

describe("DEF-4739 / DEF-4740 — PRM-02 Assets, against the drawn frame", () => {
  const ASSETS = [
    {
      id: "a1",
      asset_no: "MTR-40990",
      tab: "meters",
      type: "meter",
      type_name: "Meter",
      service: "water",
      size_class: "Class 200",
      meter_type_name: "AMI",
      read_method_name: "AMI",
      behavior_class: "in_service",
      status_name: "In service",
      test_due: false,
      assigned_to: null,
      install_date: "2026-06-01",
      last_read: { consumption: "96.0000", unit: "kgal", read_at: "2026-08-28" },
    },
    {
      id: "a2",
      asset_no: "FIR-00311",
      tab: "behind_the_meter",
      type: "fire_line",
      type_name: "Fire service line",
      service: "fire",
      size_class: "6 in",
      meter_type_name: null,
      read_method_name: null,
      behavior_class: "in_service",
      status_name: "In service",
      test_due: false,
      assigned_to: "Unit 1",
      install_date: "2026-06-01",
    },
  ];

  it("the shared table furniture is there, with the drawn search prompt", () => {
    const html = renderTab("/premises/p-101?tab=assets", premise(), ASSETS);
    expect(html).toContain('placeholder="Search by number, type or where it is…"');
    expect(html).toContain(">All<");
    expect(html).toContain("+ Filter ");
    expect(html).toContain('aria-label="Show or hide columns"');
    expect(html).toContain('class="table-pager"');
  });

  it("the NINE drawn columns, in the drawn order", () => {
    const html = renderTab("/premises/p-101?tab=assets", premise(), ASSETS);
    expectHeadersInOrder(html, [
      "Asset",
      "What it is",
      "Service",
      "Size",
      "Where",
      "Installed",
      "Last read",
      "Status",
    ]);
  });

  it("Service and Size were SERVED and never drawn — that is DEF-4740 in one line", () => {
    const html = renderTab("/premises/p-101?tab=assets", premise(), ASSETS);
    // The service NAME comes from `rating.service.<code>`, the one service
    // vocabulary in this product — there is no second map here.
    expect(html).toContain("Water");
    expect(html).toContain("Fire");
    // BR-AST-500's size class is the tenant's own code TEXT, which is what the
    // asset detail already shows: a printed reference, never a database id.
    expect(html).toContain("Class 200");
    expect(html).toContain("6 in");
  });

  it("Where says the unit, or *the property itself* — in words, in the absent style", () => {
    const html = renderTab("/premises/p-101?tab=assets", premise(), ASSETS);
    expect(html).toContain("Unit 1");
    expect(html).toContain("the property itself");
    // `assigned_to: null` is a FACT (the asset hangs on the property), so it
    // must never come out as the same dash a missing value would draw.
    expect(html).toMatch(/class="italic[^"]*">the property itself</);
  });

  it("the status is a PILL, as the frame draws it", () => {
    const html = renderTab("/premises/p-101?tab=assets", premise(), ASSETS);
    expect(html).toContain('class="pill');
    expect(html).toContain("In service");
  });

  it("nothing installed LINKS TO THE UNITS and says why it matters", () => {
    const html = renderTab("/premises/p-101?tab=assets", premise(), []);
    expect(html).toContain("Nothing is installed here yet");
    expect(html).toContain("A meter on a unit starts billing.");
    expect(html).toContain("Open the units →");
  });
});

// ── The Audit log tab ──────────────────────────────────────────────────────

describe("DEF-4740 — PRM-02 Audit log: From and To as columns", () => {
  it("the SIX drawn columns, in the drawn order, and no disclosure anywhere", () => {
    const html = renderTab(
      "/premises/p-101?tab=audit",
      premise(),
      [],
      auditResult([{ before: { route: null }, after: { route: "Route 12" } }]),
    );
    expectHeadersInOrder(html, ["When", "Who", "What changed", "From", "To"]);
    // *"There is no Expand control and no disclosure anywhere in the drawn
    // table"* — because seeing what a field used to say is the whole use of an
    // audit log, and a press per row is what the amber block calls the problem.
    expect(html).not.toContain("Expand");
    expect(html).not.toContain("aria-expanded");
  });

  it("an ABSENT previous value is drawn as an absence — `None → Route 12` is a different fact", () => {
    const html = renderTab(
      "/premises/p-101?tab=audit",
      premise(),
      [],
      auditResult([{ before: { route: null }, after: { route: "Route 12" } }]),
    );
    expect(html).toContain('data-audit-field="route"');
    expect(html).toContain("Route 12");
    // ⚠ **THE SHARPEST MISS ON THIS SCREEN.** Rendered as nothing, a route
    // being SET reads exactly like a route being CHANGED. The absent style is
    // what separates them, so it is asserted as markup rather than as a word.
    expect(html).toMatch(/data-audit-from="route"><span class="italic[^"]*">Not set</);
  });

  // ⚠ **THESE THREE DRIVE `AuditFromCell` DIRECTLY, AND THAT IS NOT
  // BELT-AND-BRACES.** Proving the guards red first (law 7) found that the
  // whole-row render CANNOT reach the cell's `before === null` branch: the
  // `From` column short-circuits a creation to ONE dash before it gets there,
  // so a break planted in that branch left the suite green. A branch no test
  // can fail is a branch nobody is checking, and the cell is exported for
  // reuse — so its three forms are asserted where they can actually go red.
  describe("AuditFromCell — the three drawn forms of a previous value", () => {
    const cell = (before: string | null) =>
      renderToStaticMarkup(
        <AuditFromCell field={{ key: "route", label: "Read route", before, after: "Route 12" }} t={t} />,
      );

    it("no previous value AT ALL is the dash — a creation, not an empty field", () => {
      expect(cell(null)).toBe('<span class="met-muted">—</span>');
    });

    it("a previous value that was EMPTY is the absent style, never blank", () => {
      expect(cell("Not set")).toMatch(/^<span class="italic[^"]*">Not set<\/span>$/);
    });

    it("a previous value somebody typed is drawn plainly", () => {
      expect(cell("Route 9")).toBe("<span>Route 9</span>");
    });
  });

  it("a CREATION draws `—` in From, because there was no previous value at all", () => {
    const html = renderTab(
      "/premises/p-101?tab=audit",
      premise(),
      [],
      auditResult([
        {
          action: "premises.created",
          before: null,
          after: { address_line: "412 Cypress Row", premises_type_name: "Apartment complex" },
        },
      ]),
    );
    // The event, not a list of the fields a brand-new record happens to have —
    // which is what the frame draws on its own `Property added` row.
    expect(html).toContain("Premises added");
    // ⚠ `—` IS NOT THE ABSENT STYLE HERE, AND THAT IS THE POINT: the absent
    // style means *there was a field and it was empty*; the dash means *there
    // was no previous value to have*. Three drawn forms, three different facts.
    expect(html).toContain('<span class="met-muted">—</span>');
  });

  it("`Actor` is `Who`, and a system job is still NAMED (BR-AUD-003)", () => {
    const html = renderTab(
      "/premises/p-101?tab=audit",
      premise(),
      [],
      auditResult([{ actor: null, before: { route: null }, after: { route: "Route 12" } }]),
    );
    expect(html).toContain(">Who<");
    expect(html).not.toContain(">Actor<");
    expect(html).toContain("System job");
  });

  it("a whole-record snapshot says how many more it is not showing, rather than walling the row", () => {
    const html = renderTab(
      "/premises/p-101?tab=audit",
      premise(),
      [],
      auditResult([
        {
          action: "premises.created",
          before: null,
          after: {
            address_line: "412 Cypress Row",
            city: "Silver Creek",
            state: "TX",
            postal_code: "78611",
            premises_type_name: "Apartment complex",
          },
        },
      ]),
    );
    // Five recorded values, three lines, and the count of what the cap hid.
    expect(html).toContain("+2 more");
  });

  it("PO 2026-09-10 — the full-log link and the window sentence are KEPT", () => {
    // *"Keep it as it is"*: the frame draws neither, and an unstated absence
    // reads as *it never happened*. The window is bounded server-side
    // (BR-AUD-006 / BR-AUD-013) and the archive opt-in lives in S61.
    const html = renderTab(
      "/premises/p-101?tab=audit",
      premise(),
      [],
      auditResult([{ before: { route: null }, after: { route: "Route 12" } }]),
    );
    expect(html).toContain("Open the audit log for this record →");
    expect(html).toContain("/audit-log?f.entity_type=premises&amp;f.entity_id=p-101");
    expect(html).toContain("Showing the last 2 years");
  });

  it("the shared toolbar is there, with this tab's own search prompt and no Columns control", () => {
    const html = renderTab(
      "/premises/p-101?tab=audit",
      premise(),
      [],
      auditResult([{ before: { route: null }, after: { route: "Route 12" } }]),
    );
    expect(html).toContain('placeholder="Search this history…"');
    expect(html).toContain(">All<");
    expect(html).toContain("+ Filter ");
    // ⚠ **THE FRAME DRAWS NO `▦ Columns` ON THIS TAB AND THE KIT DRAWS ONE ON
    // EVERY LIST.** Recorded as a divergence rather than suppressed: hiding a
    // shared control on one screen is a per-screen exception to B14 rule 12,
    // which is a bigger act than the divergence it would fix.
    expect(html).toContain('aria-label="Show or hide columns"');
  });
});
