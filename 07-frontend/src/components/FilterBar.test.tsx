// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-007 (EP-SHL-02 §Stories)  Screens: S34 (widest filtered list — §4 test data) · S33 (Record payments — CS-40's own screen)
// Change:   CS-40 (CR-059 §0d.2)
// Defect:   DEF-3504 (the bar could render option lists and nothing else)
// Rules:    BR-SHL-011 (f.<name> URL grammar) · BR-SHL-010 (only DECLARED capabilities render) · BR-SHL-023 / BR-SHL-034 (one date-formatting path) · IS-8
// ───────────────────────────────────────────────────────
// TC tests for FE-03 FilterBar. Markup asserts on react-dom/server static
// output; state laws run through the exported pure transitions (EP-SHL-04
// conventions — no DOM library, no new dependencies).
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n"; // initializes the i18next singleton with the five catalogs

// Read through Vite's own `?raw` and not `node:fs`: this app carries no
// `@types/node` on purpose, so a static `node:fs` import passes vitest and
// FAILS `tsc --noEmit`. `DataTable.test.tsx` records the same trap.
import optionsOnlyApplied from "./__fixtures__/FilterBar.optionsOnly.applied.baseline.html?raw";
import optionsOnlyClear from "./__fixtures__/FilterBar.optionsOnly.clear.baseline.html?raw";

import {
  FilterBar,
  clearAllFilters,
  clearDateRange,
  dateRangeChipCopy,
  filterIsActive,
  offerableFilters,
  setFilter,
  toggleFilterOption,
} from "./FilterBar";
import { clientPage } from "./clientTable";
import {
  dateRangeFilter,
  defaultRequestState,
  filterParamNames,
  filterValueList,
  isMultiSelectFilter,
  isCalendarDate,
  parseTableParams,
  serializeTableParams,
} from "./tableTypes";
import type { TableConfig, TableFilterDateRange } from "./tableTypes";

const noop = () => undefined;

type OutstandingRow = {
  id: string;
  account_no: string;
  name: string;
  balance: string;
  age: string;
  class: string;
};

// S34 Outstandings capability-matrix row (per US-SHL-007 §4 test data: 184
// outstanding accounts; filters Age bucket + Class).
const s34Config: TableConfig<OutstandingRow> = {
  screenId: "S34",
  columns: [
    { key: "account_no", label: "Account #", identity: true, sortable: true },
    { key: "name", label: "Name", sortable: true },
    { key: "balance", label: "Balance", sortable: true, numeric: true },
    { key: "age", label: "Age" },
    { key: "class", label: "Class" },
  ],
  getRowId: (row) => row.id,
  searchFields: ["account_no", "name"],
  filters: [
    {
      name: "age",
      label: "Age bucket",
      options: [
        { value: "30to60", label: "30–60" },
        { value: "60plus", label: "60+" },
      ],
    },
    {
      name: "class",
      label: "Class",
      options: [
        { value: "residential", label: "Residential" },
        { value: "commercial", label: "Commercial" },
      ],
    },
  ],
  defaultSort: { sort: "balance", dir: "desc" },
};

describe("US-SHL-007 — filters with URL persistence (FE-03 FilterBar)", () => {
  it("US-SHL-007 TC-1: Age=60+ AND Class=Residential → two chips + clear-all; the URL carries f.age=60plus&f.class=residential", () => {
    let state = defaultRequestState(s34Config);
    state = setFilter(state, "age", "60plus");
    state = setFilter(state, "class", "residential");
    // Filters are AND-combined ON THE SERVER — the state simply carries both.
    expect(state.filters).toEqual({ age: "60plus", class: "residential" });
    expect(state.page).toBe(1); // a filter change returns to page 1

    // BR-SHL-011: the f.<name> grammar, serialized by the consumer.
    const params = serializeTableParams(state, s34Config);
    expect(params.get("f.age")).toBe("60plus");
    expect(params.get("f.class")).toBe("residential");

    const html = renderToStaticMarkup(
      <FilterBar filters={s34Config.filters ?? []} state={state} onStateChange={noop} />,
    );
    // ⚠ This counted `filter-chip"` — a CLASS NAME — until 2026-08-20, so it
    // broke the moment the chips became Tailwind utilities even though the
    // chips themselves were unchanged. It now counts the per-chip REMOVE
    // control, which is what IS-4 actually requires and what a user can see.
    expect((html.match(/aria-label="Remove /g) ?? []).length).toBe(2); // two chips
    expect(html).toContain("Age bucket: 60+");
    expect(html).toContain("Class: Residential"); // chip shows labels, not raw codes
    expect(html).toContain("Clear all");
  });

  it("US-SHL-007 TC-2: pasting the URL into a fresh session restores the identical state (parse ∘ serialize round-trip)", () => {
    let state = defaultRequestState(s34Config);
    state = setFilter(state, "age", "60plus");
    state = setFilter(state, "class", "residential");
    state = { ...state, sort: "balance", dir: "asc", page: 2, per: 100, q: "A-104" };

    // A fresh session has only the URL string — full state must restore from it
    // alone (BR-SHL-011: shareable/bookmarkable).
    const url = serializeTableParams(state, s34Config).toString();
    const restored = parseTableParams(new URLSearchParams(url), s34Config);
    expect(restored).toEqual(state);
  });

  it("US-SHL-007 TC-6: 'Clear all' removes every filter, drops all f.* params, and returns to page 1", () => {
    let state = defaultRequestState(s34Config);
    state = setFilter(state, "age", "60plus");
    state = setFilter(state, "class", "residential");
    state = { ...state, page: 3 };

    const cleared = clearAllFilters(state);
    expect(cleared.filters).toEqual({});
    expect(cleared.page).toBe(1);
    expect(serializeTableParams(cleared, s34Config).toString()).not.toContain("f.");

    // With nothing active: no chips and no clear-all — just the All chip and
    // the + Filter button. (Read "the declared selects" until DEF-442 redrew
    // them; the ASSERTIONS below are about chips and never named the control.)
    const html = renderToStaticMarkup(
      <FilterBar filters={s34Config.filters ?? []} state={cleared} onStateChange={noop} />,
    );
    expect(html).not.toContain('aria-label="Remove ');
    expect(html).not.toContain("Clear all");
  });

  // ── Supplementary (non-TC) coverage ──────────────────────────────────────
  // ⚠ AMENDED 2026-08-21 (DEF-442). This asserted `<select` ×2 and `>All<` ×2 —
  // the CONTROL SHAPE — because that is what FE-03 first drew. r10 draws one
  // `+ Filter ▾` panel of grouped checkboxes instead, so the assertions below
  // read the panel. THE RULE IS UNCHANGED: BR-SHL-010 still says only the
  // DECLARED set renders, IS-4 still says active filters are chips with a
  // clear-all, and the three TCs above — which ask about the STATE and the URL —
  // were untouched by the redraw and passed through it without an edit.
  it("US-SHL-007 (IS-4, as redrawn by DEF-442): each DECLARED filter is a checkbox GROUP inside the + Filter panel; a chip's ✕ removes just that filter", () => {
    let state = defaultRequestState(s34Config);
    state = setFilter(state, "age", "60plus");

    const html = renderToStaticMarkup(
      <FilterBar filters={s34Config.filters ?? []} state={state} onStateChange={noop} />,
    );
    // One panel, not one control per dimension.
    expect((html.match(/<details/g) ?? []).length).toBe(1);
    expect(html).toContain("+ Filter");
    expect(html).toContain("Filter by"); // the FILTER BY heading, uppercased in CSS
    // BR-SHL-010: only the declared set renders — one <fieldset>/<legend> group
    // per declared dimension, and a checkbox per declared option.
    expect((html.match(/<fieldset/g) ?? []).length).toBe(2);
    expect(html).toContain("<legend");
    expect(html).toContain("Age bucket");
    expect((html.match(/type="checkbox"/g) ?? []).length).toBe(4); // 2 + 2 options
    expect(html).toContain("Residential");
    // The applied value is ticked INSIDE the panel and shown as a chip OUTSIDE
    // it — the second is the half DEF-442 says was missing.
    expect((html.match(/checked=""/g) ?? []).length).toBe(1);
    expect(html).toContain("Age bucket: 60+");
    expect(html).toContain("Remove the Age bucket filter"); // per-chip ✕, aria-labeled

    // ✕ on the Age chip = setting it back to "": only that filter goes.
    const withBoth = setFilter(state, "class", "commercial");
    const removed = setFilter(withBoth, "age", "");
    expect(removed.filters).toEqual({ class: "commercial" });
  });

  it("DEF-442: NO <select> renders in the filter bar — the regression guard for the drawing the PO reported", () => {
    let state = defaultRequestState(s34Config);
    state = setFilter(state, "age", "60plus");
    const html = renderToStaticMarkup(
      <FilterBar filters={s34Config.filters ?? []} state={state} onStateChange={noop} />,
    );
    // Written against the DEFECT, not against the fix: this string is exactly
    // what the screen carried when the Product Owner said *"look at filters you
    // build"*, and it is 3 on the pre-DEF-442 component.
    expect((html.match(/<select/g) ?? []).length).toBe(0);
  });

  it("DEF-442: the All chip is inverted while nothing is applied and becomes the clear-all once something is (IS-4's clear-all, r10's `.fchip.active`)", () => {
    const clear = defaultRequestState(s34Config);
    const clearHtml = renderToStaticMarkup(
      <FilterBar filters={s34Config.filters ?? []} state={clear} onStateChange={noop} />,
    );
    expect(clearHtml).toContain('aria-pressed="true"');
    expect(clearHtml).not.toContain("Clear all"); // TC-6: nothing to clear, no clear-all offered

    const applied = setFilter(clear, "age", "60plus");
    const appliedHtml = renderToStaticMarkup(
      <FilterBar filters={s34Config.filters ?? []} state={applied} onStateChange={noop} />,
    );
    expect(appliedHtml).toContain('aria-pressed="false"');
    expect(appliedHtml).toContain("Clear all");
  });

  it("BR-SHL-010: a screen that declares NO filters renders no filter furniture at all — not an All chip over nothing", () => {
    const state = defaultRequestState(s34Config);
    const html = renderToStaticMarkup(
      <FilterBar filters={[]} state={state} onStateChange={noop} />,
    );
    expect(html).toBe("");
  });

  it("DEF-442 / OQ-306: a checkbox is SINGLE-select — ticking a second value in one dimension REPLACES the first, and re-ticking the set value clears the dimension", () => {
    // ⚠ This is the divergence from r10, pinned so it cannot be quietly
    // "fixed" into r10's multi-select: `TableRequestState.filters` is one value
    // per dimension and BR-SHL-011 serializes one `f.<name>=<value>`, both
    // signed, and the SERVER applies them. Widening it is an API change and is
    // OQ-306, not a drawing change. If this test goes red, read OQ-306 first.
    let state = defaultRequestState(s34Config);
    state = toggleFilterOption(state, "age", "60plus");
    expect(state.filters).toEqual({ age: "60plus" });

    state = toggleFilterOption(state, "age", "30to60"); // a second box in the SAME group
    expect(state.filters).toEqual({ age: "30to60" }); // replaces, never accumulates

    state = toggleFilterOption(state, "class", "residential"); // a DIFFERENT group ANDs
    expect(state.filters).toEqual({ age: "30to60", class: "residential" });

    state = toggleFilterOption(state, "age", "30to60"); // unticking the set box
    expect(state.filters).toEqual({ class: "residential" });
    expect(state.page).toBe(1); // every filter change returns to page 1
  });
});

// ══════════════════════════════════════════════════════════════════════════
// OQ-306 CLOSED — PO 2026-10-02, verbatim: *"Allow several services at once."*
// Shown: a clerk reviewing Water and Sewer schedules together. The SERVICE
// dimension multi-selects and ORs; every other dimension (the S34 test above)
// stays single-select.
// ══════════════════════════════════════════════════════════════════════════
type ScheduleRow = { id: string; name: string; service: string };

const scheduleConfig: TableConfig<ScheduleRow> = {
  screenId: "S9.rates",
  columns: [
    { key: "name", label: "Name", identity: true, sortable: true },
    { key: "service", label: "Service" },
  ],
  getRowId: (row) => row.id,
  filters: [
    {
      name: "service",
      label: "Service",
      options: [
        { value: "water", label: "Water" },
        { value: "sewer", label: "Sewer" },
        { value: "trash", label: "Trash" },
      ],
    },
    {
      name: "status",
      label: "Status",
      options: [{ value: "active", label: "Active" }],
    },
  ],
  defaultSort: { sort: "name", dir: "asc" },
};

const SCHEDULES: ScheduleRow[] = [
  { id: "1", name: "Residential water", service: "water" },
  { id: "2", name: "Residential sewer", service: "sewer" },
  { id: "3", name: "Weekly trash", service: "trash" },
];

const scheduleSpec = {
  search: (row: ScheduleRow) => [row.name],
  filter: (row: ScheduleRow, name: string, value: string) =>
    name === "service" ? row.service === value : true,
  sortValue: (row: ScheduleRow) => row.name,
};

describe("OQ-306 — the service filter takes several values at once", () => {
  it("picking Water and Sewer keeps both and drops Trash; the one chip reads both", () => {
    let state = defaultRequestState(scheduleConfig);
    state = toggleFilterOption(state, "service", "water");
    state = toggleFilterOption(state, "service", "sewer"); // ADDS, never replaces
    expect(state.filters).toEqual({ service: "water,sewer" });
    expect(state.page).toBe(1);

    const { page } = clientPage(SCHEDULES, state, scheduleSpec);
    expect(page.map((row) => row.service)).toEqual(["sewer", "water"]);
    expect(page.some((row) => row.service === "trash")).toBe(false);

    const html = renderToStaticMarkup(
      <FilterBar filters={scheduleConfig.filters ?? []} state={state} onStateChange={noop} />,
    );
    expect(html).toContain("Service: Water, Sewer");
    expect((html.match(/aria-label="Remove /g) ?? []).length).toBe(1); // ONE chip
    // Both boxes read as ticked in the panel, Trash does not.
    expect((html.match(/checked=""/g) ?? []).length).toBe(2);
  });

  it("re-ticking one value removes only that one; the last one out clears the group", () => {
    let state = defaultRequestState(scheduleConfig);
    state = toggleFilterOption(state, "service", "water");
    state = toggleFilterOption(state, "service", "sewer");
    state = toggleFilterOption(state, "service", "water");
    expect(state.filters).toEqual({ service: "sewer" });
    state = toggleFilterOption(state, "service", "sewer");
    expect(state.filters).toEqual({}); // absent, exactly like an empty single-select
  });

  it("the wire stays one string: f.service=water,sewer, and it round-trips", () => {
    let state = defaultRequestState(scheduleConfig);
    state = toggleFilterOption(state, "service", "water");
    state = toggleFilterOption(state, "service", "sewer");
    const params = serializeTableParams(state, scheduleConfig);
    expect(params.get("f.service")).toBe("water,sewer");
    expect(parseTableParams(params, scheduleConfig).filters).toEqual({ service: "water,sewer" });
  });

  it("other dimensions stay single-select and still AND with the services", () => {
    let state = defaultRequestState(scheduleConfig);
    state = toggleFilterOption(state, "service", "water");
    state = toggleFilterOption(state, "service", "sewer");
    state = toggleFilterOption(state, "status", "active");
    expect(state.filters).toEqual({ service: "water,sewer", status: "active" });
    expect(isMultiSelectFilter("status")).toBe(false);
    expect(filterValueList("status", "a,b")).toEqual(["a,b"]); // never split
  });
});

// ══════════════════════════════════════════════════════════════════════════
// CS-40 · DEF-3504 — FILTER A LIST BY DATE RANGE
// ══════════════════════════════════════════════════════════════════════════
//
// The Product Owner, walking all four Record payments tabs on the deployed
// build (2026-09-03): *"I cannot filter payment by date"*.
//
// `apps/payments/selectors.py` already matched `posted_from`, `posted_to`,
// `cleared_from` and `cleared_to`; `api/endpoints.ts` already declared all
// four in `PAYMENT_FILTERS`. The gap was one shared component: a
// `TableFilterConfig` was `{name, label, options}` and this bar could draw an
// option list and nothing else, so the payments screen drew the four option
// lists it could and stated the other two as absent, in plain English, on the
// tab.
//
// ⚠ EVERY LIST IN THE PRODUCT SHARES THIS BAR, so the acceptance below is in
// two halves and the second is the one that carries the risk: the date range
// must work, and every list that declares none must render BYTE-FOR-BYTE what
// it rendered before.
//
// PROVED RED BEFORE TRUSTED GREEN (hard-won law 7) — each block quotes the
// verbatim failure it was first shown to produce.

/** S33 Record payments, as the payments lane will declare it: the four option
 *  lists it already draws are irrelevant here, so this config carries the one
 *  new thing — the posted-date range, on the SERVER's own two param names. */
type PaymentRowStub = { id: string; posted_at: string };

const postedRange: TableFilterDateRange = {
  from: "posted_from",
  to: "posted_to",
  dateFormat: "DD/MM/YYYY",
};

const s33Config: TableConfig<PaymentRowStub> = {
  screenId: "S33",
  columns: [
    { key: "id", label: "Payment #", identity: true },
    { key: "posted_at", label: "Posted", sortable: true },
  ],
  getRowId: (row) => row.id,
  filters: [
    {
      name: "status",
      label: "Status",
      options: [
        { value: "cleared", label: "Cleared" },
        { value: "processing", label: "Processing" },
      ],
    },
    dateRangeFilter({
      name: "posted",
      label: "Posted",
      from: "posted_from",
      to: "posted_to",
      dateFormat: "DD/MM/YYYY",
    }),
  ],
  defaultSort: { sort: "posted_at", dir: "desc" },
};

function renderS33(state: ReturnType<typeof defaultRequestState<PaymentRowStub>>): string {
  return renderToStaticMarkup(
    <FilterBar filters={s33Config.filters ?? []} state={state} onStateChange={noop} />,
  );
}

describe("CS-40 — a clerk narrows a list to 1–31 August (DEF-3504)", () => {
  it("CS-40 (the acceptance line): 1–31 August lands on the SERVER's two param names, and the URL carries both", () => {
    // ⚠ RED FIRST, on the component as the PO photographed it: with
    // `TableFilterConfig` still `{name, label, options}` this test could not
    // even be written — `dateRangeFilter` did not exist and the declaration
    // above failed to compile:
    //     error TS2305: Module '"./tableTypes"' has no exported member
    //     'dateRangeFilter'.
    // Which is the honest shape of the defect: not a wrong value on screen, a
    // capability the shared bar did not have.
    let state = defaultRequestState(s33Config);
    state = { ...state, page: 4 };
    state = setFilter(state, "posted_from", "2026-08-01");
    state = setFilter(state, "posted_to", "2026-08-31");

    // ONE control and ONE chip to the clerk; TWO ordinary entries on the wire,
    // keyed by the names the server already matches. No new param shape, no
    // `from..to` encoding, nothing for either side to learn.
    expect(state.filters).toEqual({ posted_from: "2026-08-01", posted_to: "2026-08-31" });
    expect(state.page).toBe(1); // the result set changed — back to page 1

    const params = serializeTableParams(state, s33Config);
    expect(params.get("f.posted_from")).toBe("2026-08-01");
    expect(params.get("f.posted_to")).toBe("2026-08-31");
    // The group's own `name` is the chip's identity and a React key. It is
    // NEVER a URL param when a range is declared — a `f.posted=` would be a
    // third parameter the server has never heard of.
    expect(params.get("f.posted")).toBeNull();
  });

  it("CS-40: the range SURVIVES A REFRESH — parse ∘ serialize restores it from the URL alone", () => {
    let state = defaultRequestState(s33Config);
    state = setFilter(state, "posted_from", "2026-08-01");
    state = setFilter(state, "posted_to", "2026-08-31");
    state = setFilter(state, "status", "cleared");
    state = { ...state, page: 2, per: 100, q: "PMT-2608" };

    // A fresh session holds only the URL string (BR-SHL-011: shareable and
    // bookmarkable). This is the same round trip US-SHL-007 TC-2 asserts for
    // option filters, and it is the whole of "survives a refresh".
    const url = serializeTableParams(state, s33Config).toString();
    expect(parseTableParams(new URLSearchParams(url), s33Config)).toEqual(state);
  });

  it("CS-40: AN EMPTY RANGE NARROWS NOTHING, AND SAYS SO — no chip, no clear-all, no `f.` param", () => {
    // ⚠ THIS IS THE DEFECT READ THE OTHER WAY ROUND. DEF-3504's own sentence
    // on the payments tab was that *"an empty date box would narrow nothing
    // while looking as though it had"*. An untouched range must therefore be
    // indistinguishable from a filter nobody declared.
    const state = defaultRequestState(s33Config);
    expect(dateRangeChipCopy(postedRange, state)).toBeNull();
    expect(filterIsActive(s33Config.filters?.[1] ?? { name: "", label: "", options: [] }, state)).toBe(
      false,
    );
    expect(serializeTableParams(state, s33Config).toString()).not.toContain("f.");

    const html = renderS33(state);
    expect(html).not.toContain('aria-label="Remove '); // no chip
    expect(html).not.toContain("Clear all"); // nothing to clear
    expect(html).toContain('aria-pressed="true"'); // the All chip is still the applied one
    // The two boxes ARE drawn — the capability exists and is reachable — and
    // both are empty. An empty box that is present is the honest state; the
    // dishonest one is a chip claiming a range nobody entered.
    expect((html.match(/type="date"/g) ?? []).length).toBe(2);
    expect(html).not.toContain('value="2026');
  });

  it("CS-40: A HALF-ENTERED RANGE NAMES THE OPEN END — never a dangling separator", () => {
    // ⚠ RED FIRST. The first draft rendered one sentence with a blank in it and
    // the chip read `Posted: 01/08/2026 to `, which is exactly the "looks as
    // though it filtered" complaint wearing different clothes. Three shapes,
    // three sentences.
    const base = defaultRequestState(s33Config);

    const fromOnly = setFilter(base, "posted_from", "2026-08-01");
    expect(dateRangeChipCopy(postedRange, fromOnly)).toEqual({
      bound: "from",
      from: "01/08/2026",
    });
    const fromHtml = renderS33(fromOnly);
    expect(fromHtml).toContain("Posted: 01/08/2026 onwards");
    expect(fromHtml).not.toContain("01/08/2026 to <"); // no blank second half

    const toOnly = setFilter(base, "posted_to", "2026-08-31");
    expect(dateRangeChipCopy(postedRange, toOnly)).toEqual({ bound: "to", to: "31/08/2026" });
    expect(renderS33(toOnly)).toContain("Posted: Up to 31/08/2026");

    const both = setFilter(fromOnly, "posted_to", "2026-08-31");
    expect(dateRangeChipCopy(postedRange, both)).toEqual({
      bound: "both",
      from: "01/08/2026",
      to: "31/08/2026",
    });
    expect(renderS33(both)).toContain("Posted: 01/08/2026 to 31/08/2026");
  });

  it("CS-40 / IS-8: the chip renders in the TENANT's date format, through the ONE formatter", () => {
    // The native `<input type="date">` renders in the BROWSER's locale and
    // ignores the tenant setting completely, so the chip is the only place a
    // tenant whose format differs ever sees theirs (the same reason
    // `DatePickerField` carries its grey echo line). Same state, two tenants,
    // two chips — which is only possible because the value goes through
    // `formatDate` (BR-SHL-023 / BR-SHL-034) and never `toLocaleDateString`.
    let state = defaultRequestState(s33Config);
    state = setFilter(state, "posted_from", "2026-08-01");
    state = setFilter(state, "posted_to", "2026-08-31");

    expect(dateRangeChipCopy(postedRange, state)).toEqual({
      bound: "both",
      from: "01/08/2026",
      to: "31/08/2026",
    });
    expect(dateRangeChipCopy({ ...postedRange, dateFormat: "MM/DD/YYYY" }, state)).toEqual({
      bound: "both",
      from: "08/01/2026",
      to: "08/31/2026",
    });
    expect(dateRangeChipCopy({ ...postedRange, dateFormat: "DD-MMM-YY" }, state)).toEqual({
      bound: "both",
      from: "01-Aug-26",
      to: "31-Aug-26",
    });
  });

  it("CS-40: the chip's ✕ clears BOTH ends — one chip, one removal", () => {
    // ⚠ RED FIRST: clearing only the end that happened to be clicked left the
    // list still filtered with no chip saying so, which is DEF-442's original
    // complaint — a table showing 1 of 7 rows that cannot say why.
    let state = defaultRequestState(s33Config);
    state = setFilter(state, "posted_from", "2026-08-01");
    state = setFilter(state, "posted_to", "2026-08-31");
    state = setFilter(state, "status", "cleared");

    const cleared = clearDateRange(state, postedRange);
    expect(cleared.filters).toEqual({ status: "cleared" }); // the OTHER filter survives
    expect(cleared.page).toBe(1);
    expect(dateRangeChipCopy(postedRange, cleared)).toBeNull();

    // And Clear all still takes everything, the range included.
    expect(clearAllFilters(state).filters).toEqual({});
  });

  it("CS-40 / BR-SHL-011: a URL end that is not a real calendar day is DROPPED, and the list is honestly unfiltered", () => {
    // ⚠ RED FIRST. Before `isCalendarDate` guarded the parse, this restored
    //     { posted_from: 'banana', posted_to: '2026-02-31' }
    // and the chip beside the list read `Posted: banana to 31/02/2026` over
    // rows the server had not filtered that way. BR-SHL-011 already rules that
    // an invalid value falls back and never reaches an error screen; this is
    // that rule at the date boundary.
    const url = "f.posted_from=banana&f.posted_to=2026-02-31&f.status=cleared";
    const restored = parseTableParams(new URLSearchParams(url), s33Config);
    expect(restored.filters).toEqual({ status: "cleared" });
    expect(dateRangeChipCopy(postedRange, restored)).toBeNull();

    // A shape check alone is not enough and that is why the arithmetic exists:
    // both of these match `^\d{4}-\d{2}-\d{2}$` and neither is a day.
    expect(isCalendarDate("2026-02-31")).toBe(false);
    expect(isCalendarDate("2026-13-01")).toBe(false);
    expect(isCalendarDate("2026-00-10")).toBe(false);
    expect(isCalendarDate("2026-08-00")).toBe(false);
    expect(isCalendarDate("2026-8-1")).toBe(false); // unpadded is not the grammar
    expect(isCalendarDate("")).toBe(false);
    // Leap years, by the real rule and not by "divisible by four".
    expect(isCalendarDate("2024-02-29")).toBe(true);
    expect(isCalendarDate("2026-02-29")).toBe(false);
    expect(isCalendarDate("1900-02-29")).toBe(false); // century, not a leap year
    expect(isCalendarDate("2000-02-29")).toBe(true); // 400, and it is
    expect(isCalendarDate("2026-08-31")).toBe(true);
  });

  it("CS-40: a range survives `offerableFilters`, which drops a group with no OPTIONS", () => {
    // ⚠ RED FIRST, and this one is a trap the DEF-1701 rule sets for its own
    // successor: a date range legitimately has NO options, so the existing
    // "a group with no options is a legend over nothing" filter deleted it
    // outright. The bar rendered one fieldset where two were declared and no
    // date control at all, silently — the shape of failure this whole defect
    // is about. Eight of the thirty call sites route through this function.
    const declared = s33Config.filters ?? [];
    expect(offerableFilters(declared).map((f) => f.name)).toEqual(["status", "posted"]);
    // The option group's `<select>`-era empty-value sentinel is still stripped,
    // and a group left with nothing is still dropped.
    expect(
      offerableFilters([
        { name: "svc", label: "Service", options: [{ value: "", label: "All services" }] },
      ]),
    ).toEqual([]);
  });

  it("CS-40: the panel draws the range as two dated boxes under ONE legend, and no checkbox", () => {
    let state = defaultRequestState(s33Config);
    state = setFilter(state, "posted_from", "2026-08-01");
    const html = renderS33(state);

    // One panel, one fieldset per DECLARED dimension — the range is a
    // dimension, not a second panel and not a control in the toolbar row.
    expect((html.match(/<details/g) ?? []).length).toBe(1);
    expect((html.match(/<fieldset/g) ?? []).length).toBe(2);
    expect((html.match(/type="date"/g) ?? []).length).toBe(2);
    // Two options on `status` and nothing extra: the range contributes no
    // checkbox at all.
    expect((html.match(/type="checkbox"/g) ?? []).length).toBe(2);
    expect(html).toContain("From");
    expect(html).toContain("To");
    expect(html).toContain('value="2026-08-01"');
    // `min`/`max` cross-bind the two ends so a native picker greys out the days
    // that would invert the range. A HELP, not a guarantee (hard-won law 1) —
    // a typed or pasted backwards range still reaches the server, narrows to
    // the zero days between the two, and says so in the chip.
    expect(html).toContain('min="2026-08-01"');

    // The three chip sentences must be real copy, never a raw key on a screen
    // (the defect G15 exists for). G27 sees them because they are spelled as
    // literals at the `t()` call sites; this asserts they RESOLVE.
    expect(html).not.toContain("table.filters.date");
  });

  it("CS-40 (BR-SHL-010, backward compatibility): a list declaring NO range renders BYTE-IDENTICALLY to the pre-change bar", () => {
    // ⚠ `__fixtures__/FilterBar.optionsOnly.*.baseline.html` were captured from
    // this component at HEAD BEFORE the capability was written. They are the
    // only artefacts that can answer "did all thirty call sites keep their
    // exact output". Structural assertions ("still two fieldsets") pass on
    // markup that gained a wrapper, an attribute or a whitespace text node;
    // bytes do not — and this bar is on EVERY list in the product, so a
    // regression here is a regression everywhere.
    //
    // REGENERATING THEM IS A DELIBERATE ACT. A future change that legitimately
    // moves this markup re-captures both files in the same commit, and the diff
    // is then the reviewable statement of what moved on every list screen.
    //
    // ⚠ RECAPTURED 2026-09-04 (B14 rule 36 · `DEF-3722`), and here is the
    // statement the diff makes. r10's `.fchip` left this file for the KIT —
    // `components/Chip.tsx` — because it was a private constant that no other
    // screen could reach, so the Integrations grid wrote its own rounded pill
    // instead. Rendering the kit's chip changes THREE things in these bytes and
    // nothing else: the row gains `data-chip-row=""`, each chip gains
    // `data-chip="selected|resting"`, and the applied chip now writes
    // `bg-transparent` explicitly where it previously left the property unset.
    // Every class that draws a pixel is unchanged, and the attribute order
    // moved because the component writes its own `data-` marks first. Checked
    // against a browser before recapture, not assumed.
    const clear = defaultRequestState(s34Config);
    expect(
      renderToStaticMarkup(
        <FilterBar filters={s34Config.filters ?? []} state={clear} onStateChange={noop} />,
      ),
    ).toBe(optionsOnlyClear);

    const applied = setFilter(clear, "age", "60plus");
    expect(
      renderToStaticMarkup(
        <FilterBar filters={s34Config.filters ?? []} state={applied} onStateChange={noop} />,
      ),
    ).toBe(optionsOnlyApplied);

    // ⚠ AND THE COMPARISON CAN TELL PASS FROM FAIL (law 7, and DEF-182's lesson
    // that a check whose output cannot distinguish the two is worse than no
    // check). The SAME comparison against the SAME fixture, with a range
    // declared, must go red — otherwise the two assertions above prove only
    // that a string was read from disk.
    expect(
      renderToStaticMarkup(
        <FilterBar
          filters={[
            ...(s34Config.filters ?? []),
            dateRangeFilter({
              name: "posted",
              label: "Posted",
              from: "posted_from",
              to: "posted_to",
              dateFormat: "DD/MM/YYYY",
            }),
          ]}
          state={clear}
          onStateChange={noop}
        />,
      ),
    ).not.toBe(optionsOnlyClear);
  });

  it("CS-40: `filterParamNames` is the ONE statement of which `f.` params a filter owns", () => {
    // Both halves of the round trip walk this, so parse and serialize cannot
    // disagree about a range's grammar. For an option filter it returns exactly
    // what both functions did before this landed, which is what keeps the
    // fixtures above byte-identical.
    expect(filterParamNames({ name: "status", label: "Status", options: [] })).toEqual(["status"]);
    expect(filterParamNames(s33Config.filters?.[1] as never)).toEqual([
      "posted_from",
      "posted_to",
    ]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-007@e879338 (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-09-03 by the CS-40 lane (eleven cases for the date range, each one first shown RED against the mechanism it guards — the seven mutations and their verbatim failures are named in the docstrings)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ tsc✔ eslint✔ vitest 31/31✔ (5 TC todo this packet — browser/journey/backend scope) · [CS-40 2026-09-03] vitest FilterBar 19/19✔ (8 → 19)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
