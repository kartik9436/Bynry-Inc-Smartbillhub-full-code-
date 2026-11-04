// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-012 (S25 reads list) · US-MET-019 (S25 Needs-attention landing)
//           Screens: S25
// Rules:    BR-MET-016 (lineage HEADS only) · BR-MET-021 (the flag vocabulary) ·
//           BR-MET-049 (Missing derives from the plan-required set — BUILT since
//           2026-08-26, so a NUMBER; this line said "unbuilt, so null" and the
//           screen believed it for a day — DEF-815) ·
//           BR-MET-132 (the chip counts OPEN and CLOSED-BUT-UNBILLED windows) ·
//           BR-MET-055 (server pagination + the 2-year hot window + archive opt-in) ·
//           BR-MET-059 (the channel model) · BR-MET-060 (the landing is Needs attention,
//           on every open) · BR-SHL-010 (an undeclared capability never renders) ·
//           BR-SHL-011 (URL grammar) · BR-SHL-025 (disabled WITH the reason)
// ───────────────────────────────────────────────────────
// §4 test data is the EP-MET-04 seed (Brazos Bend, cycle 08-A) rendered through
// the mocked client seam — no network, ever.
//
// The three assertions worth naming, because each is a defect this codebase has
// already paid for once:
//   · a usage cell without its unit (CLAUDE.md rule 3);
//   · a Missing chip whose caption contradicts the count printed above it, or
//     which hides the meters whose required set could not be stated (DEF-815);
//   · a header control that is live onto a screen nobody built.
//
// RED PROOF for the three chip assertions amended on 2026-08-26, MEASURED
// rather than asserted (hard-won law 7). `attentionTiles` was put back on
// `counts.missing ?? <span>—</span>` with the plain `missingWhy` detail,
// `isAllClear` back on `(counts.missing ?? 0) === 0`, and the en caption back to
// its shipped wording. `npx vitest run src/features/metering/ReadsPage.test.tsx`
// measured `3 failed | 24 passed | 3 todo (30)`:
//   × US-MET-019 TC-3 …states BR-MET-132's predicate
//     → expected 'Missing counts the plan-required reco…' not to contain 'not built'
//   × DEF-815: unresolvable meters ride beside the count, never behind it
//     → expected '<div class="met-page rd-page">…' to contain '11 meter(s) could not be checked — no…'
//   × US-MET-019 TC-6: 0 · 0 · 0 renders the all-clear state
//     → expected true to be false
// The rendered HTML in the second failure is the defect verbatim: `<span
// class="v">3</span>` sitting directly above "That computation is not built, so
// this is unknown rather than zero." Reverting the revert: `27 passed`.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { MyPermissions, Paginated, ReadRow } from "@/api/endpoints";
import { EXPORT_RESOURCES, READ_CHANNELS, READ_FILTERS, READ_SORTS } from "@/api/endpoints";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import {
  ReadBatchCell,
  ReadsListPage,
  RouteSheetModal,
  channelFilterOptions,
  readStatusFilterOptions,
  readsParamsFrom,
  readsQueryKey,
  readsTableConfig,
  routeSheetSchema,
  serviceFilterOptions,
} from "./ReadsListPage";
import { LONG_LIST_THRESHOLD } from "@/components/FormModal";
import { PREMISES_PERMISSION } from "./meteringShared";
import {
  CHIP_DISPUTED_FILTER,
  CHIP_FLAGGED_FILTER,
  UsageCell,
  READS_TAB_ALL,
  READS_TAB_CYCLES,
  flaggedOutcomes,
  mathLine,
  outcomeTally,
  readStatusTone,
  readsTabFromParam,
  unevaluatedOutcomes,
} from "./readsShared";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const CELLS = {
  meter: () => <span />,
  readAt: () => <span />,
  cycle: () => <span />,
  route: () => <span />,
  service: () => <span />,
  premise: () => <span />,
  usage: () => <span />,
  status: () => <span />,
  channel: () => <span />,
  source: () => <span />,
  days: () => <span />,
  batch: () => <span />,
  priorValue: () => <span />,
  currentValue: () => <span />,
  // CR-038 W5 task 7 — the bulk-selection checkbox is a CELL in this config.
  select: () => <input type="checkbox" />,
};
const CONFIG = readsTableConfig(
  t,
  { routes: [], cycles: [], services: [] },
  (row) => `/${TEST_TENANT}/reads/${row.id}`,
  CELLS,
);

/** EP-MET-04 §4: M-7001's clean August read (684 kWh over 31 days). */
function read(over: Partial<ReadRow> = {}): ReadRow {
  return {
    id: "r-7001-aug",
    meter: "M-7001",
    asset_id: "a-7001",
    // DEF-045 closed (CR-038 W5): the four RDS-01 columns, served.
    cycle: "08-A",
    cycle_id: "c-08a",
    route: "R-1",
    route_id: "rt-1",
    service: "electric",
    premise: "1408 Elm Street",
    premise_no: "P-00101",
    premises_id: "p-1408",
    unit_label: "Unit A",
    unit_id: "u-1408a",
    channel: "total",
    read_at: "2026-08-03",
    period_start: "2026-07-03",
    period_end: "2026-08-03",
    prior_value: "42180.000000",
    current_value: "42864.000000",
    prior_value_display: "42180 kWh",
    current_value_display: "42864 kWh",
    multiplier: "1.000000",
    consumption: "684.000000",
    unit: "kWh",
    usage_display: "684 kWh",
    days_since_prior: 31,
    source: "import",
    source_detail: "walk_by",
    // CR-038 W3 — a pre-change read: no method was recorded, so the server
    // DERIVES `walk_by` from the old source_detail and marks it derived.
    // `read_dict` serves `read_type` too (export vs consumption) — DEF-816.
    read_type: "consumption",
    read_method: "walk_by",
    read_method_origin: "derived",
    status: "ok",
    lifecycle: "committed",
    rule_outcomes: [
      { rule: "high", severity: "ok", detail: { ratio_pct: "104.5", threshold_pct: "200" } },
      { rule: "days_threshold", severity: "ok", detail: { days: 31, flag_bounds: [25, 35] } },
    ],
    import_batch_id: "b-2608-04",
    // The batch NUMBER a clerk reads — B14 rule 31. The id above stays for
    // `title`, because a batch its series never numbered is a real state.
    import_batch_no: "RB-2608-0044",
    disposition: null,
    disposition_reason: null,
    estimation_method: null,
    consecutive_estimate_no: null,
    trues_up_read_ids: [],
    superseded_by_id: null,
    superseded_at: null,
    supersede_reason: null,
    disputed_at: null,
    dispute_reason: null,
    disputed: false,
    disputed_by: null,
    dispute_cleared_at: null,
    dispute_cleared_by: null,
    demand_reset_noted: false,
    is_peak: false,
    ...over,
  };
}

/** EP-MET-04 §4: M-7204's high-usage water read — 26.24 kgal at 312%. */
function flaggedRead(): ReadRow {
  return read({
    id: "r-7204-aug",
    meter: "M-7204",
    unit: "kgal",
    consumption: "26.240000",
    usage_display: "26.24 kgal",
    prior_value: "412000.000000",
    current_value: "438240.000000",
    prior_value_display: "412000 kgal",
    current_value_display: "438240 kgal",
    status: "high",
    rule_outcomes: [
      {
        rule: "high",
        severity: "warning",
        detail: {
          ratio_pct: "312.0000000000",
          threshold_pct: "200",
          absolute_floor: "1",
          absolute_floor_unit: "kgal",
          trailing_average: "8.400000",
        },
      },
      { rule: "factor_flag", severity: "not_evaluated", detail: { reason: "threshold_not_ratified" } },
    ],
  });
}

/** EP-MET-04 §4: M-7108, an estimate — consumption, and NO register value. */
function estimatedRead(): ReadRow {
  return read({
    id: "r-7108-aug",
    meter: "M-7108",
    prior_value: null,
    current_value: null,
    prior_value_display: null,
    current_value_display: null,
    consumption: "612.000000",
    usage_display: "612 kWh",
    status: "estimated",
    source: "estimated",
    source_detail: null,
    estimation_method: "trailing_3_cycle_daily_average",
    consecutive_estimate_no: 1,
    rule_outcomes: [],
  });
}

function listPage(rows: ReadRow[]): Paginated<ReadRow> {
  return { count: rows.length, next: null, previous: null, results: rows };
}


function permissions(access: string): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access }],
  };
}

function renderReads(
  path: string,
  seed: {
    list?: Paginated<ReadRow>;
    access?: string;
    archive?: boolean;
  } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const search = new URLSearchParams(path.split("?")[1] ?? "");
  const state = parseTableParams(search, CONFIG);
  const archive = seed.archive ?? search.get("archive") === "true";
  if (seed.list !== undefined) {
    queryClient.setQueryData(
      readsQueryKey(`${serializeTableParams(state, CONFIG).toString()}|${archive}`),
      seed.list,
    );
  }
  if (seed.access !== undefined) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access));
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <ReadsListPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * The route-sheet dialog's pure half, rendered once for the four tests that
 * read it. Both vocabularies are supplied because BR-MET-162 makes route and
 * cycle equals — a helper that fed only routes could not fail on the defect.
 */
function renderSheetPicker(): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[`/${TEST_TENANT}/reads`]}>
      <RouteSheetModal
        routes={[
          { id: "rt-1", code: "R-1", name: "Downtown" } as never,
          { id: "rt-2", code: "R-2", name: null } as never,
        ]}
        cycles={[{ id: "c-08a", code: "08-A" } as never]}
        buildHref={(scope, id) => `/api/${TEST_TENANT}/${scope}/${id}/route-sheet`}
        onClose={() => undefined}
      />
    </MemoryRouter>,
  );
}

describe("S25 — the reads list (US-MET-012)", () => {
  it("US-MET-012 TC-1: every usage cell renders WITH its unit — the server's usage_display, never a bare number", () => {
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, {
      list: listPage([read(), flaggedRead(), estimatedRead()]),
    });
    // CLAUDE.md rule 3. Each of the three rows carries its own unit, and the
    // two units differ — a screen that had assumed one would fail here.
    expect(html).toContain("684 kWh");
    expect(html).toContain("26.24 kgal");
    expect(html).toContain("612 kWh");
    // ...and no row prints the consumption stripped of its unit.
    expect(html).not.toContain(">684.000000<");
    expect(html).not.toContain(">26.240000<");
  });

  // ── DEF-895 · BR-MET-160 — the SOURCE cell answers in as few words as it can

  it("DEF-895: the SOURCE cell carries NO parenthetical about our own migration", () => {
    // PO 2026-08-27, on the live app: "you dont have to provide sub text in
    // bracket". The default fixture IS the defect — `read_method: walk_by`,
    // `read_method_origin: derived`, `source_detail: walk_by` — so the cell
    // rendered `Walk-by (from the old source tag) · Manual entry · Walk-by`.
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([read()]) });
    expect(html).toContain(t("metering.reads.readMethod.walk_by"));
    expect(html).not.toContain(t("metering.reads.readMethod.derivedSuffix"));
    // ⚠ AND THE THIRD PART WAS A LITERAL DUPLICATE: a DERIVED method is
    // derived FROM `source_detail`, so the cell printed "Walk-by" twice. Once
    // is the assertion — a `not.toContain` could never have seen this.
    expect(html.split(t("metering.reads.readMethod.walk_by")).length - 1).toBe(1);
    // BR-MET-160 (4): the TRANSPORT stays. It is a different fact about the
    // reading, not a footnote about our history (BR-MET-123).
    expect(html).toContain(t("metering.reads.source.import"));
  });

  it("DEF-895: the provenance is NOT deleted — S29 still states it", () => {
    // The bracket moved, it did not vanish: the key is alive and the read
    // detail page renders it. A fix that deleted the fact would pass the test
    // above and lose something a clerk can legitimately need.
    expect(t("metering.reads.readMethod.derivedSuffix")).not.toBe(
      "metering.reads.readMethod.derivedSuffix",
    );
  });

  // ── DEF-896 · the toolbar is r10 RDS-01's ONE row ────────────────────────

  it("DEF-896: the filter slot is no longer the .met-filters full-width GRID", () => {
    // `.met-filters` is `display:grid; width:100%`. Dropped into
    // `.table-toolbar`'s flex row it consumed the WHOLE line, so `All` and
    // `+ Filter` fell below the search box, the archive checkbox floated into
    // the middle as a grid column, and Download CSV plus the column icon
    // wrapped to a SECOND row far right. r10 RDS-01 draws ONE compact row.
    // ⚠ The identical fix landed on the UNITS list on 2026-08-26 with the
    // identical diagnosis, and nothing swept the sibling screen.
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([read()]) });
    expect(html).not.toContain('class="met-filters"');
    expect(html).not.toContain('class="rd-archive"');
    // The controls themselves are all still there — this is a LAYOUT fix, and
    // a fix that dropped a control would pass the two assertions above.
    expect(html).toContain(t("table.filters.all"));
    expect(html).toContain(t("table.filters.open"));
    expect(html).toContain(t("metering.reads.archive.label"));
  });

  it("DEF-1085 · DEF-1700: there is ONE toolbar row, and it is bounded", () => {
    // ⚠ **THIS TEST HAS NOW BEEN WRONG TWICE AND BOTH REWRITES ARE THE POINT.**
    //
    // Draft 1 asserted r10's DOM ORDER inside one `.table-toolbar` — and every
    // one of those assertions passed on the screen the PO photographed wrapping
    // onto two lines. Order is not capacity.
    //
    // Draft 2 (DEF-1085) asserted a BOUNDED row one plus a DESIGNED second row
    // carrying the dimension controls. That was true, and the PO then ruled the
    // second row out of existence: *"as per our stadard first raw of tookkit is
    // more than suficient"* (DEF-1700). A test that pins a container the ruling
    // deleted would have to be deleted with it, which is how a claim gets lost.
    //
    // **Draft 3 keeps the property both drafts were reaching for and drops the
    // container:** row one carries B14 rule 12's set, the IS-9 export and the
    // archive scope switch, in rule 12's order — and there is NO second row.
    // The set is bounded, so it cannot outgrow the line the way ~1,360px of
    // controls did against the ~1,150px a 1,440px laptop leaves.
    //
    // No gate in this repo reads rendered output (hard-won law 6) and jsdom
    // computes no layout, so this still cannot SEE a wrapped row. What it can
    // see is WHICH controls are in the toolbar, and that is the property the
    // capacity decision actually rests on.
    const page = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([read()]) });
    // ⚠ INDEX INSIDE THE CONTAINER, NOT THE PAGE. An earlier draft searched the
    // whole document and went red on `at("All") = 2207 < at("Search meter #…")
    // = 2368` — because the TAB STRIP above the toolbar carries the word too,
    // and `indexOf` matches a substring anywhere. A false failure and a false
    // pass are the same bug (DEF-182): the check has to look where the claim is.
    const rowOneStart = page.indexOf('class="table-toolbar"');
    expect(rowOneStart).toBeGreaterThan(-1);
    // **THE CLAUSE THAT REPLACES THE SECOND-ROW ASSERTIONS.** DEF-1700 removed
    // `DataTable.dimensionsSlot` outright, so the marker it rendered may never
    // reappear on this screen.
    expect(page).not.toContain('data-table-row="dimensions"');
    const rowOne = page.slice(rowOneStart, page.indexOf("<table", rowOneStart));

    const at = (html: string, needle: string, where: string) => {
      const index = html.indexOf(needle);
      expect(index, `not in ${where}: ${needle}`).toBeGreaterThan(-1);
      return index;
    };

    // Row one, in rule 12's order, with the export and the ▦ after the spacer.
    expect(at(rowOne, t("metering.reads.searchPlaceholder"), "row one")).toBeLessThan(
      at(rowOne, t("table.filters.all"), "row one"),
    );
    expect(at(rowOne, t("table.filters.all"), "row one")).toBeLessThan(
      at(rowOne, t("table.filters.open"), "row one"),
    );
    // The archive opt-in is back on row one (DEF-1700). It is NOT a filter and
    // cannot become one — it rides `?archive=` outside BR-SHL-011's `f.`
    // namespace because US-MET-012 TC-10 keeps it off the export state — so it
    // duplicates nothing in the panel to its left, which is precisely what the
    // two deleted segments did.
    expect(at(rowOne, t("table.filters.open"), "row one")).toBeLessThan(
      at(rowOne, t("metering.reads.archive.label"), "row one"),
    );
    expect(at(rowOne, t("metering.reads.archive.label"), "row one")).toBeLessThan(
      at(rowOne, "table-toolbar-spacer", "row one"),
    );
    expect(at(rowOne, "table-toolbar-spacer", "row one")).toBeLessThan(
      at(rowOne, t("table.columns.title"), "row one"),
    );

    // **THE CAPACITY CLAUSE.** No dimension chip group may be anywhere on the
    // toolbar. Asserted on the CONTROL's own markup rather than on the two
    // catalogue strings the segments used to render: those keys are deleted
    // with the control (`metering.reads.filter.allRoutes` / `.allStatuses`),
    // and `t()` on a deleted key returns the key itself — so a string
    // assertion would pass for the wrong reason from the moment it was
    // written, which is DEF-182's failure exactly.
    expect(rowOne).not.toContain('class="seg"');
    expect(rowOne).not.toContain('role="radiogroup"');
  });

  it("DEF-896: the search box says what it searches (B14 rule 19)", () => {
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([read()]) });
    expect(html).toContain(t("metering.reads.searchPlaceholder"));
    // DEF-510's fallback told a clerk nothing at all.
    expect(html).not.toContain(t("table.search.placeholder"));
    // ⚠ **THIS LINE ASSERTED THE OPPOSITE UNTIL 2026-09-14 AND IT WAS RIGHT
    // THEN — REWRITTEN WITH THE RULING, NEVER DELETED.** It read
    // `expect(…).not.toContain("address")`, because r10's RDS-01 draws
    // *"Meter #, address…"* while `selectors.read_list` filtered
    // `asset__asset_no__icontains` and nothing else: naming a field the
    // endpoint ignores is the DEF-950 trap, and the copy stated what was
    // actually searched. **The server searches the premise address as of
    // MR-27**, so the divergence is over and DEF-950 is closed.
    expect(t("metering.reads.searchPlaceholder")).toContain("address");
    // ⚠ **AND THE COPY ALONE IS NOT THE GUARD — A PLACEHOLDER IS A SENTENCE
    // AND NO CHECK CAN TELL WHETHER A SENTENCE IS TRUE** (B14 rule 19's own
    // amendment says so). What makes this honest is that the screen DECLARES
    // both fields, so a later lane narrowing the server has something here to
    // break rather than a promise nothing measures.
    expect(CONFIG.searchFields).toEqual(["meter", "premise"]);
  });

  it("DEF-1700: r10's route and status pills are GONE, and both dimensions are still offered", () => {
    // ⚠ **THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-08-27 AND THE RULING
    // REVERSED IT — rewritten with the ruling cited, never deleted** (the same
    // discipline CR-045 applied to `ReadsPage.test.tsx:409`).
    //
    // It read *"DEF-896: r10's route and status pills are drawn, from the
    // tenant's OWN routes"* and asserted the two `All routes` / `All statuses`
    // cells were in the markup. Both catalogue keys are deleted with the
    // control, so the claim is now made against the CONTROL's own markup. The Product Owner photographed the result and ruled, of the
    // same control on the premises list: *"as per our stadard first raw of
    // tookkit is more than suficient ; how many places such isue is there - I
    // can see it in unit also"* (`DEF-1700`). Reads carried TWO of them.
    //
    // **What makes the removal lossless is the second half of this test**, and
    // it is the half that would go red if a later lane deleted the dimension
    // instead of the duplicate control: `route` and `status` are DECLARED
    // filters on this screen's own `TableConfig`, so `+ Filter` offers both,
    // from the same option sources, writing the same `f.route` / `f.status`.
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([read()]) });
    // No segmented control of any kind survives on this toolbar. `.seg` is the
    // class the deleted `SegmentedFilter` drew; a radiogroup here would be the
    // same chip row wearing another component's name.
    expect(html).not.toContain('class="seg"');
    expect(html).not.toContain('role="radiogroup"');
    // …and BOTH dimensions are still reachable, in the one panel.
    expect(html).toContain(t("table.filters.open"));
    const declared = (CONFIG.filters ?? []).map((filter) => filter.name);
    expect(declared).toContain("route");
    expect(declared).toContain("status");
    // The status cells are the SERVED three. r10 draws a fourth, "Pending",
    // and it is deliberately absent: BR-MET-049 derives it from the
    // plan-required set, `GET /reads` declares no such filter, and BE-05
    // IGNORES an undeclared `f.` param — so a Pending cell would silently
    // return every read. One vocabulary, and now exactly one control over it.
    expect(readStatusFilterOptions(t).map((option) => option.value)).toEqual([
      "ok",
      "flagged",
      "estimated",
    ]);
  });

  it("DEF-896/DEF-952: the two-line prose above the toolbar is gone, and it was stale", () => {
    // r10 RDS-01 draws NO paragraph over this list. And the sentence had been
    // wrong since BR-MET-131 retired the read DRAWER — its last clause read
    // "and the drawer shows every version behind it", on the busiest screen in
    // the module. Its one load-bearing fact rides under the table instead.
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([read()]) });
    expect(html).not.toContain("metering.reads.explainer.all");
    expect(html).not.toContain("drawer");
    // ⚠ **AND THE LINE UNDER THE TABLE IS GONE TOO (MR-31, B14 rule 33).**
    // *"A corrected reading appears once: the list shows the current version of
    // each chain."* — fourteen words, and RATIONALE: it explains why the list
    // looks the way it does. Rule 33 caps rationale at ZERO words on screen,
    // and the blueprint's copy budget measured this exact string and cut it.
    // The fact it carried has not changed and is not lost — it is BR-MET-016,
    // it is in this screen's own header comment, and `read_list` enforces it.
    expect(t("metering.reads.headsOnlyNote")).toBe("metering.reads.headsOnlyNote");
    expect(html).not.toContain("current version of each chain");
    // What SURVIVES the budget is the archive line — two sentences, five words
    // and six, an INSTRUCTION rather than rationale, and it passed the measure.
    expect(html).toContain(t("metering.reads.archive.off"));
  });

  it("US-MET-012 TC-1: an estimated read is VISIBLY estimated in the list (BR-MET-029)", () => {
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([estimatedRead()]) });
    expect(html).toContain(t("metering.reads.estimatedBadge"));
    expect(html).toContain(t("metering.reads.status.estimated"));
    // An estimate is a lawful bill input that travels flagged, so it is
    // warning-toned — never the clean "success" pill an actual read gets.
    expect(readStatusTone("estimated")).toBe("warning");
    expect(readStatusTone("ok")).toBe("success");
  });

  it("BR-MET-135: a GENERATION read names its register in the Usage column — it is not usage", () => {
    // **CR-038 W6, PO 2026-08-26: *"please add generation"*.** A device's
    // produced quantity is *"distinct from `export` … and never summed with
    // consumption"*. This column is headed **Usage**, so a bare 612 kWh sitting
    // in it is that claim made by a label — a person reading the list totals it
    // in their head. The register names itself beside the number instead.
    //
    // Guard proved RED first — the `isNonConsumptionChannel` branch removed
    // from `UsageCell`:
    //   AssertionError: expected '…684.000000 kWh…' to contain
    //   'data-cell="non-consumption-channel"'
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, {
      list: listPage([
        read({
          id: "r-pv-1001-aug",
          meter: "PV-1001",
          channel: "generation",
          consumption: "612.000000",
          usage_display: "612 kWh",
        }),
      ]),
    });
    expect(html).toContain('data-cell="non-consumption-channel"');
    expect(html).toContain(t("metering.reads.channel.generation"));
    expect(html).toContain(t("metering.reads.notConsumptionWhy"));
  });

  it("BR-MET-135: an ordinary consumption read gets NO such badge", () => {
    // The other half, and the reason the first case can fail: a badge on every
    // row would prove nothing at all.
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([read()]) });
    expect(html).not.toContain('data-cell="non-consumption-channel"');
  });

  it("US-MET-012 TC-2: the status filter offers exactly the SERVED vocabulary — OK · Flagged · Estimated, and no Pending", () => {
    const values = readStatusFilterOptions(t).map((option) => option.value);
    expect(values).toEqual(["ok", "flagged", "estimated"]);
    // BR-MET-049 derives Pending from the plan-required record set and
    // `GET /reads` declares no such filter; BE-05 IGNORES an undeclared `f.`
    // param, so a Pending option would silently return every read.
    expect(values).not.toContain("pending");
  });

  it("US-MET-012 TC-2: filters and sorts are declared ONLY where the server serves them (BR-SHL-010)", () => {
    const declaredFilters = (CONFIG.filters ?? []).map((filter) => filter.name);
    for (const name of declaredFilters) {
      expect(READ_FILTERS as readonly string[]).toContain(name);
    }
    // RENDERED as of CR-038 W5. This assertion used to be its inverse — the
    // filter was served and deliberately not offered while
    // `GET /settings/services` was System-Admin-only. That endpoint is
    // AnyTenantRole now, so the control exists with the tenant's own enabled
    // vocabulary. (RED-proved by flipping: the old config had no `service`.)
    expect(declaredFilters).toContain("service");
    // Every sortable column names a sort the server actually accepts.
    for (const column of CONFIG.columns.filter((c) => c.sortable === true)) {
      expect(READ_SORTS as readonly string[]).toContain(column.key);
    }
    // The capability row's default: read_at, newest first.
    expect(CONFIG.defaultSort).toEqual({ sort: "read_at", dir: "desc" });
  });

  it("US-MET-012 TC-2: the channel filter is BR-MET-059's enum, in full", () => {
    expect(channelFilterOptions(t).map((option) => option.value)).toEqual([...READ_CHANNELS]);
  });

  it("US-MET-012 TC-1 (DEF-045 closed): the four RDS-01 columns render — cycle, route, service and premise·unit", () => {
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([read()]) });
    // Column headers, in the capability row's vocabulary…
    expect(html).toContain(t("metering.reads.col.cycle"));
    expect(html).toContain(t("metering.reads.col.route"));
    expect(html).toContain(t("metering.reads.col.service"));
    expect(html).toContain(t("metering.reads.col.premise"));
    // …and the SERVED values — never a client-side join.
    expect(html).toContain("08-A");
    expect(html).toContain("R-1");
    // RDS-01's premise cell: address · unit label, one cell of two facts.
    expect(html).toContain("1408 Elm Street");
    expect(html).toContain("Unit A");
  });

  it("US-MET-012 TC-1 (DEF-045): a stock meter's linkage cells DASH — an honest absence, never an invented route", () => {
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, {
      list: listPage([
        read({
          cycle: null,
          cycle_id: null,
          route: null,
          route_id: null,
          service: null,
          premise: null,
          premise_no: null,
          premises_id: null,
          unit_label: null,
          unit_id: null,
        }),
      ]),
    });
    expect(html).toContain(t("metering.reads.col.cycle"));
    expect(html).not.toContain("08-A");
  });

  it("US-MET-012: the service filter offers the TENANT's enabled vocabulary (values are service CODES)", () => {
    const options = serviceFilterOptions([
      { service: "electric", name: "Electric", enabled: true } as never,
      { service: "water", name: "Water", enabled: true } as never,
      { service: "gas", name: "Gas", enabled: false } as never,
    ]);
    // The server filters `service__code`, so the VALUE is the code; a disabled
    // service is not offered — the same posture as the Units filter.
    expect(options).toEqual([
      { value: "electric", label: "Electric" },
      { value: "water", label: "Water" },
    ]);
  });

  it("IS-9 (DEF-034 class closed for S25): `reads` is a REGISTERED export resource and the table mounts the ONE export control", () => {
    // The frontend's registry mirror must carry it, or requestListExport
    // could not name it…
    expect(EXPORT_RESOURCES as readonly string[]).toContain("reads");
    // …and the All-reads table renders the shared Download control.
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([read()]) });
    expect(html).toContain('data-resource="reads"');
  });

  it("CR-038 W5: a row's identity cell is a real LINK to the S29 page (tenantPath discipline)", () => {
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([read()]) });
    expect(html).toContain(`href="/${TEST_TENANT}/reads/r-7001-aug"`);
  });

  it("US-MET-012 TC-10: the request is server-paginated and the hot window is the DEFAULT (BR-MET-055)", () => {
    const state = parseTableParams(new URLSearchParams(""), CONFIG);
    expect(readsParamsFrom(state, false).archive).toBe(false);
    expect(readsParamsFrom(state, false).per).toBe(50); // IS-2 as amended
    // The opt-in is explicit and travels as its own param, never as a filter.
    expect(readsParamsFrom(state, true).archive).toBe(true);
    expect(Object.keys(readsParamsFrom(state, true).filters)).not.toContain("archive");
  });

  it("US-MET-012 TC-10: the default view SAYS which window it is showing", () => {
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([read()]) });
    expect(html).toContain(t("metering.reads.archive.off"));
    expect(html).toContain(t("metering.reads.archive.label"));
  });

  it("US-MET-012 TC-1: a superseded read never reaches the list — the screen resolves no lineage of its own (BR-MET-016)", () => {
    // The selector filters `superseded_by_id IS NULL` server-side. The screen's
    // half of that guarantee is that it does NO grouping, de-duplication or
    // chain-walking of its own: it renders the page the server returned.
    const head = read();
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([head]) });
    expect(html).toContain("M-7001");
    // ⚠ The lineage-head guarantee is unchanged; the SENTENCE about it is cut
    // (MR-31). What proves the guarantee is the ROW SET the server returns, so
    // this counts rows — a corrected reading appears ONCE. Counting occurrences
    // of the meter NUMBER would not: it rides on the link, its aria-label and
    // the select checkbox's label, so one row spells it three times.
    expect(html.match(/data-table-row/g)?.length).toBe(1);
  });

  it("US-MET-012 TC-8: Upload reads AND Route sheet are LIVE controls (DEF-115 · CR-038 W5)", () => {
    const html = renderReads("/reads");
    // DEF-115: "↑ Upload reads" was disabled with an honest reason — and the
    // consequence was that `meter_reads` held 0 rows on a fully seeded stack
    // and no bill in this product had ever come from a meter reading. S28
    // exists now, so the button must NOT be disabled and must NOT carry the
    // old reason. A `title` is how GuardedButton renders a refusal, so its
    // absence on this button is the assertion.
    expect(html).toContain(t("metering.reads.action.upload"));
    expect(html).toMatch(/data-variant="primary"[^>]*>↑ Upload reads/);
    // Route sheet went LIVE with CR-038 W5: the server renders the sheet from
    // the walk order and the button opens the route picker. This assertion
    // used to be its inverse (disabled with `routeSheetUnavailable`) — that
    // key no longer exists, which is the RED proof of the flip.
    expect(html).toContain(t("metering.reads.action.routeSheet"));
    expect(html).not.toContain("routeSheetUnavailable");
  });

  it("CR-038 W5: the route-sheet picker opens the SERVER's print-ready page for the chosen route", () => {
    // The modal's pure half: the href is the API path under the tenant
    // (DEF-532's law travels through the caller's tenantPath), and the schema
    // refuses an empty pick.
    const html = renderSheetPicker();
    expect(html).toContain(t("metering.reads.routeSheet.title"));
    expect(html).toContain("R-1 · Downtown");
    expect(html).toContain("R-2");
    expect(routeSheetSchema(t).safeParse({ scope: "routes", target: "" }).success).toBe(false);
    expect(routeSheetSchema(t).safeParse({ scope: "routes", target: "rt-1" }).success).toBe(true);
  });

  // ── DEF-898 · BR-MET-162 — a sheet is printed for a route OR a cycle ─────

  // ── MR-06 (blueprint entry 17) — a clerk with hundreds of routes types ──

  /**
   * The same dialog with an arbitrary number of routes on it.
   *
   * ⚠ **THE COUNT IS DERIVED FROM THE KIT'S OWN CONSTANT, NEVER TYPED.** B14
   * rule 37: a figure drawn in a wireframe is an illustration. `MR-06` is about
   * a THRESHOLD, so a test that hard-coded 11 would be asserting today's value
   * of `LONG_LIST_THRESHOLD` rather than the behaviour, and would go green on a
   * screen that had stopped consulting it.
   */
  function renderSheetPickerWithRoutes(count: number): string {
    return renderToStaticMarkup(
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/reads`]}>
        <RouteSheetModal
          routes={Array.from({ length: count }, (_unused, index) => ({
            id: `rt-${index}`,
            code: `R-${index}`,
            name: null,
          })) as never}
          cycles={[{ id: "c-08a", code: "08-A" } as never]}
          buildHref={(scope, id) => `/api/${TEST_TENANT}/${scope}/${id}/route-sheet`}
          onClose={() => undefined}
        />
      </MemoryRouter>,
    );
  }

  it("MR-06: a route list past the kit's threshold is TYPE-TO-FILTER, not a scroll list", () => {
    // BR-SHL-033 through the kit's own `LONG_LIST_THRESHOLD`. The blueprint's
    // read of this branch was that `SearchSelectField` appeared in NONE of the
    // module's four picker files; this is the route sheet's half of that.
    //
    // ⚠ Asserted on the ARIA role rather than on a class, because the role is
    // the contract a keyboard and a screen reader actually meet — and because
    // a class assertion passes on a utility that compiles to nothing.
    const long = renderSheetPickerWithRoutes(LONG_LIST_THRESHOLD + 1);
    expect(long).toContain('role="combobox"');
    expect(long).toContain('aria-autocomplete="list"');
  });

  it("MR-06: a six-route tenant sees exactly what it saw before — no type-ahead", () => {
    // The other direction, and it is the half that stops this becoming a
    // product-wide change on one screen's authority: at or under the threshold
    // the control is still the shared select. A one-directional test would
    // pass on a screen that had made EVERY picker searchable.
    const short = renderSheetPickerWithRoutes(LONG_LIST_THRESHOLD);
    expect(short).not.toContain('role="combobox"');
    expect(short).toContain("<select");
  });

  it("DEF-898: the picker asks WHAT YOU ARE HOLDING — a route or a cycle", () => {
    // PO 2026-08-27, verbatim: "allow route of Cycle - both". The dialog
    // offered a single required "Choose a route…" and nothing else, while the
    // generated sheet ALREADY printed its cycle in the header — so the cycle
    // was a first-class fact of the artefact with no way to ask for one.
    const html = renderSheetPicker();
    expect(html).toContain(t("metering.reads.routeSheet.scopeLabel"));
    expect(html).toContain(t("metering.reads.routeSheet.scopeRoute"));
    expect(html).toContain(t("metering.reads.routeSheet.scopeCycle"));
  });

  it("DEF-898: the cycle is a real answer to the SCHEMA, not only a word on screen", () => {
    // ⚠ These two assertions belong together and that is the point of the
    // test. Rendering the CHOICE without widening the schema would leave a
    // dialog that offers a cycle and then refuses it — a control live onto
    // nothing — and a test that read only the rendered markup would pass on it.
    expect(routeSheetSchema(t).safeParse({ scope: "cycles", target: "c-08a" }).success).toBe(true);
    expect(routeSheetSchema(t).safeParse({ scope: "cycles", target: "" }).success).toBe(false);
    // A scope nobody serves is refused rather than pasted into a URL segment.
    expect(routeSheetSchema(t).safeParse({ scope: "premises", target: "p-1" }).success).toBe(false);
  });

  it("DEF-898: the cycle picker says what a cycle sheet IS before it prints", () => {
    // BR-MET-162 (3): one section per ACTIVE route, each in its OWN walk
    // order — not one merged sequence. A clerk expecting a single walk should
    // learn that here, not from the page that comes back. And the refusal now
    // names both things a clerk can be holding.
    expect(t("metering.reads.routeSheet.cycleHelp")).toContain("route");
    expect(t("metering.reads.routeSheet.required")).toContain("cycle");
  });

  it("US-MET-012 TC-8: a '—' permission cell denies the whole screen (A18 §6)", () => {
    const html = renderReads("/reads", { access: "—" });
    expect(html).toContain(t("metering.reads.denied"));
    expect(html).not.toContain(t("metering.reads.archive.label"));
  });

  it("US-MET-012 TC-1: the math line is ASSEMBLED from stored operands and never evaluated", () => {
    const line = mathLine(read(), t);
    expect(line).toContain("42864.000000");
    expect(line).toContain("42180.000000");
    expect(line).toContain("1.000000");
    // The result is the SERVER's own figure, unit included — not 42864 − 42180.
    //
    // ⚠ **THE NEGATION HERE HAD TO BE REWRITTEN, NOT JUST RENUMBERED
    // (DEF-1120).** It used to read `toContain("684.000000 kWh")` followed by
    // `not.toContain("684 ")`, and the pair worked only because the SERVER's
    // string was six places and a client-computed one would have been bare:
    // the two shapes were distinguishable by their decimals alone. BR-MET-144
    // makes the server send `684 kWh`, so `684 ` now appears in the honest
    // output and the old negation would fail on correct code — a check whose
    // output cannot distinguish pass from fail (DEF-182).
    //
    // What the case is actually for is that the result is COPIED from
    // `usage_display` rather than derived, so that is what it asserts now:
    // the exact served string, and no arithmetic result beside it.
    expect(line).toContain(read().usage_display as string);
    expect(read().usage_display).toBe("684 kWh");
    // The operands stay at their STORED precision — the math line is the
    // engine's working, not a display of a quantity (BR-MET-056).
    expect(line).toContain("(42864.000000");
    // An estimate has no register pair (BR-MET-028), so there is no math line.
    expect(mathLine(estimatedRead(), t)).toBeNull();
  });

  it("US-MET-012 TC-1: stored rule outcomes are partitioned, never recomputed", () => {
    const flagged = flaggedRead();
    expect(flaggedOutcomes(flagged).map((o) => o.rule)).toEqual(["high"]);
    expect(unevaluatedOutcomes(flagged).map((o) => o.rule)).toEqual(["factor_flag"]);
    // The tally counts only the rules that RAN — a rule that could not run must
    // never flatter the fraction (CLAUDE.md law 1).
    expect(outcomeTally(flagged)).toEqual({ passed: 0, evaluated: 1 });
    expect(outcomeTally(read())).toEqual({ passed: 2, evaluated: 2 });
  });
});

describe("S25 — the landing, and what the retired tab left behind", () => {
  // ⚠ **THIS BLOCK USED TO ASSERT THE OPPOSITE, AND THE OPPOSITE WAS RIGHT.**
  // It held eight cases over `Needs attention` — the three tiles, the Missing
  // caption, the unresolved-meter line, the two drill-ins and the all-clear
  // panel — against `BR-MET-060`. That rule is stamped **SUPERSEDED
  // 2026-09-12** on the PO's own words, *"Need Attention — does not add any
  // value"*, and `US-MET-019` is retired with it.
  //
  // **The cases are REPLACED rather than deleted, and each replacement asserts
  // where its subject went.** A suite that simply loses eight cases cannot tell
  // the next reader whether the behaviour was withdrawn or merely stopped being
  // tested, and the two look identical in a green run.

  it("MR-26: Reads OPENS on All reads, and every unknown tab falls back to it", () => {
    // The fallback IS the landing rule, in one line of code — which is also
    // what carries the retired tab's own bookmarks: `?tab=attention` is now an
    // unknown value and lands on the readings rather than on nothing.
    expect(readsTabFromParam(null)).toBe(READS_TAB_ALL);
    expect(readsTabFromParam("nonsense")).toBe(READS_TAB_ALL);
    expect(readsTabFromParam("attention")).toBe(READS_TAB_ALL);
    expect(readsTabFromParam(READS_TAB_ALL)).toBe(READS_TAB_ALL);
    expect(readsTabFromParam(READS_TAB_CYCLES)).toBe(READS_TAB_CYCLES);
  });

  it("MR-26: a bare /reads renders the TABLE, not three tiles", () => {
    const html = renderReads("/reads", { list: listPage([read()]) });
    // The readings are what a clerk lands on.
    expect(html).toContain("M-7001");
    expect(html).toContain(t("metering.reads.col.previous"));
    // And the tiles are gone. Asserted against the KPI strip's own markup and
    // the tab's own label — never against the word "Flagged", which is still a
    // perfectly good status FILTER option a few pixels away. A test that reads
    // a word instead of a component cannot tell a withdrawn tile from a
    // surviving filter, and those are exactly the two things this ruling
    // separates.
    expect(html).not.toContain("kpi-strip");
    expect(html).not.toContain("rd-allclear");
    expect(html).not.toContain("rd-chip-drill");
  });

  it("MR-26: the tab strip is All reads and Read cycles, and nothing else", () => {
    const html = renderReads("/reads", { list: listPage([read()]) });
    expect(html).toContain(t("metering.reads.tab.all"));
    expect(html).toContain(t("metering.reads.tab.cycles"));
    expect(html).not.toContain("metering.reads.tab.attention");
  });

  it("MR-26: the retired tab's copy is gone from every catalogue, not merely unrendered", () => {
    // ⚠ **THE ASSERTION THAT ACTUALLY MATTERS.** A key left in the catalogues
    // renders as itself the moment anything asks for it, and `i18next` answers
    // a missing key with the key STRING rather than throwing — so "the tab is
    // gone" and "the tab's copy is gone" are two different claims and only the
    // second stops it coming back by accident.
    for (const key of [
      "metering.reads.tab.attention",
      "metering.reads.explainer.attention",
      "metering.reads.attention.allClear",
      "metering.reads.attention.note",
      "metering.reads.chip.flagged",
      "metering.reads.chip.missing",
      "metering.reads.chip.missingWhy",
      "metering.reads.chip.drillFlagged",
    ]) {
      expect(t(key)).toBe(key);
    }
  });

  it("MR-26: Flagged and Disputed SURVIVE the move, as filters the server declares", () => {
    // Page 8 of the blueprint: *"Flagged → the status filter on entry 02, which
    // counts with the same predicate the tile did. Disputed → the disputed
    // filter, likewise."* The tiles are gone; the two slices are not, so this
    // is the case that proves nothing a clerk could reach was lost.
    const names = (CONFIG.filters ?? []).map((f) => f.name);
    expect(names).toContain("status");
    expect(names).toContain("disputed");
    // The guard that keeps it honest: the filter each one sets is one the
    // SERVER declares. BE-05 IGNORES an undeclared `f.` param, so a filter the
    // server has never heard of returns the WHOLE list while looking like a
    // slice — which is why the chip could not drill in before 2026-08-16.
    expect(READ_FILTERS as readonly string[]).toContain(Object.keys(CHIP_DISPUTED_FILTER)[0]);
    expect(READ_FILTERS as readonly string[]).toContain(Object.keys(CHIP_FLAGGED_FILTER)[0]);
    // And `flagged` is the server's own composite status, not a fourth word.
    expect(readStatusFilterOptions(t).map((o) => o.value)).toContain(
      CHIP_FLAGGED_FILTER.status,
    );
  });

  it("MR-26: Missing does NOT survive, and this test is the record of why", () => {
    // *"Missing has no filter and never has — the server cannot slice the reads
    // list that way."* It moves to the cycle detail, which is the only place
    // the number means anything: a cycle has a window and an expected set.
    // **Asserted as an ABSENCE on purpose** — the failure mode this guards is a
    // later lane adding a `missing` filter here because the word looks like it
    // belongs, and getting the whole list back.
    const names = (CONFIG.filters ?? []).map((f) => f.name);
    expect(names).not.toContain("missing");
    expect(READ_FILTERS as readonly string[]).not.toContain("missing");
  });

  // ── MR-27 · MR-04 — the three changes that live inside the column picker ──

  it("MR-27: the register column and its filter both read Register, and neither says Channel", () => {
    // ⚠ **ONE WORD FOR ONE THING.** The stored column is `meter_reads.channel`
    // and the KEY still names it — that is the fact a developer needs — but a
    // clerk reads `Register`, and a clerk who filters by register and then
    // shows the column must see the same word twice. The wrong-register trap
    // is what makes this more than tidiness: a reading filed against the wrong
    // register is PERMANENT, and on a demand plan the units differ.
    const col = CONFIG.columns.find((c) => c.key === "channel");
    expect(col?.label).toBe("Register");
    expect(CONFIG.filters?.find((f) => f.name === "channel")?.label).toBe("Register");
    expect(t("metering.reads.col.channel")).not.toContain("Channel");
    // The register VALUES are untouched — `Total register`, `On-peak` — because
    // only the word for the DIMENSION moved.
    expect(channelFilterOptions(t).map((o) => o.label)).toContain(
      t("metering.reads.channel.total"),
    );
  });

  it("MR-27: the four hidden columns are declared in the DRAWN order", () => {
    // The picker renders `config.columns` as declared, so the declaration IS
    // the panel's order: … Status · Register · Batch · Days since prior.
    // `days_since_prior` used to sit between the first two.
    const hidden = CONFIG.columns.filter((c) => c.defaultVisible === false).map((c) => c.key);
    expect(hidden).toEqual(["channel", "import_batch_id", "days_since_prior"]);
    // And the eleven a clerk sees by default, in the drawn order.
    expect(
      CONFIG.columns.filter((c) => c.defaultVisible !== false).map((c) => c.key),
    ).toEqual([
      "select", "meter", "read_at", "cycle", "route", "service", "premise",
      "prior_value", "current_value", "usage", "source", "status",
    ]);
  });

  it("MR-04: the Batch column reads a NUMBER, and the uuid rides on title (B14 rule 31)", () => {
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}&cols=import_batch_id`, {
      list: listPage([read()]),
    });
    // ⚠ **THE REAL RENDERER, NOT `CONFIG`'s.** `CONFIG` is built with stub
    // cells (`() => <span />`) so the column SET can be asserted without the
    // page — which means an assertion aimed through it at a CELL tests the stub
    // and passes on anything. Two of these cases did exactly that and showed it
    // only by failing on an empty span.
    expect(CONFIG.columns.find((c) => c.key === "import_batch_id")).toBeDefined();
    const markup = renderToStaticMarkup(<ReadBatchCell row={read()} t={t} />);
    expect(markup).toContain("RB-2608-0044");
    // ⚠ **READ THE VALUE, NOT THE MARKUP.** Rule 31's own sentence puts the
    // internal value on `title`, so a check over the whole DOM string goes
    // GREEN on a breach and RED on a correct fix. The uuid must be absent from
    // what a clerk READS and present as evidence.
    expect(markup).toContain('title="b-2608-04"');
    expect(markup.replace(/title="[^"]*"/g, "")).not.toContain("b-2608-04");
    expect(html).not.toContain(">b-2608-04<");
  });

  it("MR-04: a batch its series never numbered says so in WORDS, id still on title", () => {
    // `read_import_batches.batch_no` is NULLABLE, so this is a real state and
    // it is why the id is served BESIDE the number rather than replaced by it:
    // the screen has to tell "this batch has no number" apart from "this
    // reading has no batch", and a uuid cannot say either.
    const markup = renderToStaticMarkup(
      <ReadBatchCell row={read({ import_batch_no: null })} t={t} />,
    );
    expect(markup).toContain(t("metering.reads.batchUnnumbered"));
    expect(markup).toContain('title="b-2608-04"');
    expect(markup.replace(/title="[^"]*"/g, "")).not.toContain("b-2608-04");
  });

  it("MR-04: a reading with no batch at all dashes — the most common shape", () => {
    // `commit_read` writes history directly, an AMI row arrives from a feed,
    // and a quick manual entry belongs to no import batch.
    const markup = renderToStaticMarkup(
      <ReadBatchCell row={read({ import_batch_id: null, import_batch_no: null })} t={t} />,
    );
    expect(markup).not.toContain(t("metering.reads.batchUnnumbered"));
    expect(markup).not.toContain("RB-2608-0044");
  });

  it("the whole row opens the reading, and the identity link is still the thing a keyboard reaches", () => {
    // ⚠ **THE ROW CLICK IS A MOUSE CONVENIENCE OVER A REAL LINK, NEVER A
    // REPLACEMENT FOR ONE.** A `<tr>` cannot be focused, so a list whose only
    // affordance is a row click is unreachable without a mouse — the
    // clickable-`<div>` defect wearing a table's clothes. Both halves are
    // asserted because shipping only the first is the defect.
    expect(CONFIG.rowHref?.(read())).toBe(`/${TEST_TENANT}/reads/r-7001-aug`);
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([read()]) });
    expect(html).toContain(`data-row-href="/${TEST_TENANT}/reads/r-7001-aug"`);
    expect(html).toContain(`href="/${TEST_TENANT}/reads/r-7001-aug"`);
  });

  it("hard rule 3: Previous, Current and Usage are SERVER-composed and carry their unit", () => {
    const html = renderReads(`/reads?tab=${READS_TAB_ALL}`, { list: listPage([read()]) });
    // Q9 (PO 2026-09-14, "as drawn") is satisfied by BR-MET-144 on the server:
    // the stored `42864.000000` reaches this screen already composed. Nothing
    // here rounds, scales or reformats a quantity — this list renders three
    // strings it was handed.
    expect(html).toContain(read().usage_display);
    expect(html).toContain(read().prior_value_display);
    expect(html).toContain(read().current_value_display);
    expect(html).not.toContain(".000000");
    // A bare number is refused; a dash is the honest answer — asserted against
    // the REAL `UsageCell`, which takes the whole row and reads the server's
    // composed string, and has no prop that could be handed a bare number.
    const noUnit = renderToStaticMarkup(<UsageCell row={read({ usage_display: null })} />);
    expect(noUnit).not.toMatch(/\d/);
    expect(renderToStaticMarkup(<UsageCell row={read()} />)).toContain("kWh");
  });

  it.todo(
    "MR-26 (browser): choosing Read cycles rewrites the URL to ?tab=cycles and renders the cycles table — a tab click needs a live browser",
  );
  it.todo(
    "US-MET-012 TC-9 (server): tenant isolation on the reads list is the G5 isolation suite's, on live Postgres",
  );
  it.todo(
    "US-MET-012 TC-3..7 (unserved): the per-flag fix actions (Accept / Investigate / Change multiplier / Schedule field visit) have NO endpoint — `meter_reads.fix_disposition` exists with no writer and no route, so there is nothing to test until one lands",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-012@34f14b6 (story+rules snapshot hash — EP-MET-04 list story; co-story US-MET-019@34f14b6)
// generated: 2026-08-11 by story-coder v1 (W2 reads frontend lane — S25/S29)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see ReadsListPage.tsx's trailer — one lane, one gate run
// exceptions: E4 the chip CLICK (US-MET-019 TC-2) needs a live browser and stays an honest it.todo — the half a static render proves, that the chip's filter is the server's own `flagged` status and that the count and the slice ask one question, is asserted here · E4 US-MET-012 TC-3..7 have no test because they have no endpoint: the per-flag fix actions write `meter_reads.fix_disposition`, which no service and no route sets · E4 the isolation half (TC-9) is the G5 suite's, on live Postgres
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

describe("record links (PO 2026-10-19) — the reads list's record cells", () => {
  it("cycle, route, address and unit each open their own page", () => {
    const html = renderReads("/reads", { list: listPage([read()]) });
    expect(html).toContain(`href="/${TEST_TENANT}/reads/cycles/c-08a"`);
    expect(html).toContain(`href="/${TEST_TENANT}/reads/routes/rt-1"`);
    expect(html).toContain(`href="/${TEST_TENANT}/premises/p-1408"`);
    expect(html).toContain(`href="/${TEST_TENANT}/premises/units/u-1408a"`);
  });
});
