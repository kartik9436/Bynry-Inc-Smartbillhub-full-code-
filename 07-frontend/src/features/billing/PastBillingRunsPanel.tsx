// ── Trace ──────────────────────────────────────────────
// Change:   CR-101-BRC03 §07 — blueprint screen 27 `Past billing runs`
//           (`/:tenant/billing/history` · the `history` tab of S30 · S76
//           "exists behind S1"), built from p145–p146 of
//           `05-prototype/04 Billing, As Built.pdf` READ AS IMAGES at scale 2,
//           the table band again at scale 4 (B14 rule 42).
// Defects:  DEF-BIL-5351 (the grey panel over a working read — CLOSED here) ·
//           DEF-BIL-5352 (the run status never advances — the STATUS column
//           composes from evidence until it does) · DEF-BIL-5353 (two stale
//           claims in the runs read's docstring) · DEF-BIL-5371 (the read is
//           not paginated and serves no total)
// Rules:    B14 rule 15 (row actions are ICONS, never text links) · rule 16
//           (the pagination footer) · rule 20 (one table type) · rule 21
//           (Tailwind only — this file is on `src/styles/route-b-migrated.txt`)
//           · rule 31 (no database id is ever a visible value) · rule 32 (one
//           stated absence, a disclosure CLOSED by default) · rule 33 (a label
//           ≤ 3 words, a fact ≤ 6, rationale ZERO words on screen) · rule 37
//           (a drawn figure is an illustration) · CLAUDE.md hard rule 2 (money
//           displays at 2 decimals through MoneyCell, with its CHAR(3)) ·
//           NFR-3 (server pagination) · NFR-5 (no hard caps)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS REPLACED, AND WHY IT IS HARD-WON LAW 2'S MIRROR
// ══════════════════════════════════════════════════════════════════════════
// This tab rendered a grey panel reading *"Past billing runs list every run
// with what it produced and who signed it off. It arrives with the billing run
// work."* — over a read that has answered since `CR-029`, on a column that has
// been populated since it landed. A live refusal above a working endpoint:
// `G13` asks whether a prop is PASSED and nothing in this repo asks whether a
// REFUSAL IS STILL TRUE, so every suite, every gate and `tsc` passed over it.
//
// The blueprint says so about this screen in its own words (p145): the blocker
// the screen names on itself is **false in both halves that matter** — the
// endpoint is served and the actor column is populated and on the wire.
//
// ══════════════════════════════════════════════════════════════════════════
// THE THREE QUESTIONS THE TABLE ANSWERS, WHICH IS WHY IT IS SHAPED THIS WAY
// ══════════════════════════════════════════════════════════════════════════
// p145: *"what did we bill last month, who signed it off, and is this month's
// run continuous with it"*. The third one is the reason **PERIOD is its own
// column beside CYCLE rather than collapsed into it** — `08-A` and `08-B` both
// cover August because a utility bills in CYCLES, not months, and collapsing
// the period into the cycle name hides exactly the thing a clerk checks
// continuity against (p146, note 2).
//
// Two more notes from the same page are load-bearing and easy to "tidy" away:
//   · **An abandoned run is a ROW, and it is at zero.** A run that issued
//     nothing still occupies its number, and a run that vanished would leave a
//     clerk unable to explain a gap in the numbering to an auditor. Nothing
//     here filters a run out for having no bills.
//   · **Every row opens the run it names** — *"A table you cannot drill into is
//     a report, and this is a workspace."*
//
// ══════════════════════════════════════════════════════════════════════════
// THE DRAWN `Open` LINK IS BUILT AS AN ICON, AND THE DRILL-IN IS BUILT THRICE
// ══════════════════════════════════════════════════════════════════════════
// p146's last column is an unlabelled `Open` in link red on every row. **B14
// rule 15 is RATIFIED and G37-ENFORCED: row actions are ICONS with tooltips,
// never text links.** So the drawing loses on CONSTRUCTION and wins on CONTENT
// (rule 38's split, carried to a table): the drill-in it asks for is built
// three ways and every one of them is the drawn destination — the `RUN` cell is
// the identity link, the whole row carries `rowHref` to the same address, and
// the actions column holds the 👁 icon. Recorded in the conformance file and in
// the decision log of 2026-09-15; not raised, because nothing here contradicts
// a signed rule.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT IS NOT DRAWN HERE, AND WHY EACH ABSENCE IS AN ABSENCE RATHER THAN A GAP
// ══════════════════════════════════════════════════════════════════════════
// Measured against the live demo tenant, not against a docstring:
// `GET /billing/runs` serves `run_no`, `period_start`/`period_end`,
// `bills_issued`, `ran_by_name` and `cycle_id`. It serves **no money, no page
// total, no `q`, and no status or year filter**, and its `status` column is
// written `"draft"` at creation and never advances (`DEF-BIL-5352`).
//
//   · **VALUE** — drawn, and NOT built. ⚠ **AND NOT BECAUSE A RULE FORBIDS IT.**
//     `api.py` exception (3) and `selectors.bill_runs_list` both keep money off
//     this row citing `BR-MET-078` *"Money never touches these surfaces"* —
//     whose PO wording is *"you dont need late fees in this. so dont have
//     anything related to money when you create route and cycles"* and whose
//     subject is r10 `SET-07.3`, the route and cycle CREATION screens. A run
//     history row is neither, so that citation is out of scope. The column is
//     absent for the only reason that is true: **nothing serves a run's value
//     or its currency.** When one does it renders through `MoneyCell` with its
//     `CHAR(3)` like every other money figure in the product (hard rule 2).
//   · **The four tiles** — runs this year, bills issued, runs with exceptions,
//     longest run. Each is a SERVER aggregate over the whole year. Counting
//     them from the rows on screen would be a client-side total over a bounded
//     page, which `NFR-3` forbids and which would read as a fact.
//   · **Search, and the `Status` / `Year` filters** — the read accepts
//     `f.cycle_id` and nothing else. A search box that searches nothing and a
//     filter the server ignores are both a screen lying about what it did
//     (`DEF-1001`'s own finding, one screen over). **`Cycle` IS declared**,
//     because `f.cycle_id` is real.
//   · **`Export`** — p146 draws it twice, as a head button and as the toolbar's
//     `↓`. There is no export route for this read, so neither is drawn; a
//     control with nothing behind it is the defect this file was written to
//     remove.
//
// All of them are named ONCE, in the disclosure below (`RunGap` — structurally
// a `<details>` closed by default, B14 rule 32), and each carries a test that
// goes RED the day the field lands (`pastBillingRuns.dom.test.tsx`).
//
// ══════════════════════════════════════════════════════════════════════════
// THE CYCLE CELL PRINTS A CODE AND NEVER AN ID
// ══════════════════════════════════════════════════════════════════════════
// The read serves `cycle_id` and no label. B14 rule 31 — *"no Databse ID on
// screen - that is a rule"* — so the id is resolved to the cycle's own `code`
// through the tenant's cycle list, which is the picker vocabulary the run
// wizard already reads, and an id this tenant's list does not contain states
// the absence rather than printing a uuid at a person. The drawing's `09-A` is
// an illustration of a code (rule 37); a real one reads `CY-001`.
//
// ══════════════════════════════════════════════════════════════════════════
// THE FOOTER'S TOTAL, AND THE ONE CASE IT CANNOT ANSWER
// ══════════════════════════════════════════════════════════════════════════
// `GET /billing/runs` is bounded by `limit` (clamped 1…200) and serves no
// total, which is `NFR-3` and is `DEF-BIL-5371`. The footer therefore reads the
// envelope's `total` when one is served and falls back to the number of rows
// the server returned. **That is exact for every tenant whose run history fits
// one page and it is the fallback's whole lifetime** — the moment the read
// serves `total`, the `??` branch is dead and the test below names it.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getBillRunHistory, getCycles } from "@/api/endpoints";
import type { BillRunHistoryRow, BillRunTiles } from "@/api/endpoints";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { EyeIcon } from "@/components/icons";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { MoneyCell } from "@/components/MoneyCell";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash, useRegional } from "@/features/metering/meteringShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { RunGap, billRunPath } from "./billRunShared";
import { count } from "./bulkRun/bulkRunShared";

/**
 * One row of screen 27's table.
 *
 * ⚠ **THIS WAS A LOCAL INTERFACE WIDENING `BillRunHistoryRow`, AND A LOOKUP
 * THAT RESOLVED A CYCLE ID TO ITS CODE IN THE BROWSER, UNTIL 2026-09-15 — AND
 * BOTH ARE GONE, WHICH IS THE HANDSHAKE CLOSING.** The shared type did not
 * declare `ran_by_name` while the server served it, and the read served no
 * `cycle_code`, so the panel carried both rather than editing a live sibling
 * lane's file (law 11). That lane landed: the code, the value, the exception
 * counts and the actor are all on the shared type, so the local copies are
 * DELETED rather than left to drift into a second description of one row.
 */
export type PastRunRow = BillRunHistoryRow;

/**
 * The five words `bill_runs.status` now holds, and the tone each wears.
 *
 * ⚠ **THE FALLBACK IS THE LOAD-BEARING PART.** A sixth status added
 * server-side must not render as a catalogue KEY at a clerk, and must not be
 * silently dropped either — so an unrecognised value renders its own word in
 * the neutral tone and the screen stays honest about what the server said. This
 * is the one place the vocabulary is written on the front end; a screen that
 * needed a second copy would take it from here.
 */
const RUN_STATUS_TONES: Record<string, "neutral" | "success" | "info" | "warning"> = {
  draft: "neutral",
  issuing: "info",
  issued: "success",
  corrected: "warning",
  abandoned: "neutral",
};

/**
 * The drawn `PERIOD` cell — `01 – 30 Sep 2026`, one range in one cell.
 *
 * Both ends render through `DateCell`, which is the product's ONE date path
 * (BR-SHL-023/034) and the only thing that knows the tenant's regional format.
 * A range with one end missing shows the end it has rather than an em-dash
 * against nothing: a run scoped from a date with no close is a real row.
 */
export function PeriodCell(props: {
  row: PastRunRow;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { row } = props;
  if (row.period_start === null && row.period_end === null) {
    return <Dash>{props.t("billing.runs.cell.noPeriod")}</Dash>;
  }
  return (
    <span className="whitespace-nowrap">
      {row.period_start !== null && (
        <DateCell
          value={row.period_start}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      )}
      {row.period_start !== null && row.period_end !== null && <span aria-hidden="true"> – </span>}
      {row.period_end !== null && (
        <DateCell value={row.period_end} timeZone={props.timeZone} dateFormat={props.dateFormat} />
      )}
    </span>
  );
}

/**
 * Screen 27 — the whole of the `history` tab's body.
 *
 * `client` is threaded rather than reached for so the tab's tests drive a fake
 * one, exactly as the four sibling tabs do.
 */
export function PastBillingRunsPanel(props: { client?: ApiClient }) {
  const { t: translate } = useTranslation();
  const t = translate as Translator;
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional({});

  const [state, setState] = useState<TableRequestState>({
    q: "",
    // The read orders by period desc, then creation desc — newest first, which
    // is what the drawing lists and what a clerk opening this tab is looking
    // for. Declared here so the URL and the request agree (BR-SHL-011).
    sort: "period_start",
    dir: "desc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });

  // ONE read, and it is a PAGE: `{count, next, previous, results}` plus the
  // tiles, through `readListPageWith`, which asserts the envelope at runtime.
  // The query key carries every dimension the request does, so changing a
  // filter, the search or the page fetches rather than serving a stale page.
  const runsQuery = useQuery({
    queryKey: [
      "billing",
      "runs",
      "history",
      state.q,
      state.filters.cycle_id ?? "",
      state.filters.status ?? "",
      state.filters.year ?? "",
      state.page,
      state.per,
    ],
    queryFn: () =>
      getBillRunHistory(
        {
          q: state.q,
          cycleId: state.filters.cycle_id,
          status: state.filters.status,
          year: state.filters.year,
          page: state.page,
          per: state.per,
        },
        client,
      ),
  });
  // The picker VOCABULARY only — the codes the Cycle chip offers. The rows
  // carry their own `cycle_code`, so this is no longer a lookup the table
  // depends on: a slow or failed cycles read now costs the filter's options and
  // never the CYCLE column.
  const cyclesQuery = useQuery({
    queryKey: ["cycles", "all", "runs-history"],
    queryFn: () => getCycles(client),
  });

  const rows = runsQuery.data?.rows ?? [];
  const tiles: BillRunTiles | null = runsQuery.data?.tiles ?? null;
  const cycles = cyclesQuery.data ?? [];
  // The SERVER's total. Nothing here counts rows: at a 40,000-account utility a
  // client-side total is a page size wearing a total's clothes (`NFR-3`).
  const totalRows = runsQuery.data?.total ?? null;

  /**
   * The four tiles p146 draws, in the drawn order, from the server's own
   * aggregate over the year.
   *
   * ⚠ **THE MONEY SITS IN THE TILE'S DETAIL LINE RATHER THAN AS A `money`
   * TILE, AND THAT IS A CHOICE WITH A REASON.** `KpiTile`'s money variant makes
   * `basis` REQUIRED (BR-REP-001 — no unlabelled money KPI anywhere), and this
   * figure has no posting-or-clearing basis to declare: it is the sum of what a
   * year's runs billed. The drawn tile's headline is the COUNT and the money is
   * the line beneath it, so the count is the value and the money renders through
   * `MoneyCell` with its `CHAR(3)` — two decimals, hard rule 2 — in the detail.
   * Inventing a basis to satisfy a type would have been worse than either.
   */
  const kpis: KpiTile[] = tiles === null ? [] : tileRow(tiles, t);

  const config: TableConfig<PastRunRow> = {
    // Its own key, so the run history's column choices are not the bills
    // list's (TableConfig.screenId is the stored preference key).
    screenId: "S30.runs",
    getRowId: (row) => row.id,
    // The order the READ already applies — period desc, then creation desc. No
    // column declares `sortable`, because this read accepts no `sort` param: a
    // header a clerk can click that reorders nothing is a dead control.
    defaultSort: { sort: "period_start", dir: "desc" },
    // ⚠ **THE DRAWN DRILL-IN, AS A ROW TARGET.** p146: *"Every row opens the
    // run it names."* This activates the row's own identity link rather than
    // navigating itself, which is why the table does not require a router.
    rowHref: (row) => tenantPath(billRunPath(row.id)),
    // The three chips p146 draws, and the read accepts all three
    // (`f.cycle_id`, `f.status`, `f.year`). ⚠ The CYCLE chip's VALUE is the
    // id because that is what the wire takes; its LABEL is the code, which is
    // the only thing a clerk ever sees (B14 rule 31).
    filters: [
      {
        name: "cycle_id",
        label: t("billing.runs.filter.cycle"),
        options: cycles.map((cycle) => ({ value: cycle.id, label: cycle.code })),
      },
      {
        name: "status",
        label: t("billing.runs.filter.status"),
        // Derived from the tone map above rather than typed out a second time
        // — the service-list defect's shape (`SignupWizard`), one family down.
        options: Object.keys(RUN_STATUS_TONES).map((code) => ({
          value: code,
          label: t(`billing.runs.status.${code}`),
        })),
      },
      {
        name: "year",
        label: t("billing.runs.filter.year"),
        // The years a clerk can ask for, from the tenant's own data: the year
        // the tiles are counting and the four before it. Not a hardcoded range
        // and not a clock — the served `tiles.year` is the anchor.
        // ⚠ `tiles.year` is `number | null` on the shared type: a tenant with
        // no runs at all has no year to anchor on, and the chip then offers
        // nothing rather than five years counted back from a clock this repo
        // forbids reaching for (`BR-TEN-043`, `G6`).
        options:
          tiles === null || tiles.year === null
            ? []
            : [0, 1, 2, 3, 4].map((back) => ({
                value: String((tiles.year as number) - back),
                label: String((tiles.year as number) - back),
              })),
      },
    ],
    // `q` searches the run number, the cycle and the person — the three things
    // the drawn placeholder names, and the three the server actually matches.
    searchFields: ["run_no", "cycle", "ran_by"],
    searchPlaceholder: "billing.runs.search",
    columns: [
      {
        key: "run_no",
        label: t("billing.runs.col.run"),
        identity: true,
        cell: (row) =>
          row.run_no === null ? (
            // OQ-342 numbered runs from a real series and did NOT retro-number
            // the ones created before it. The id is not printed in its place.
            <Dash>{t("billing.runs.cell.noNumber")}</Dash>
          ) : (
            <InlineLinkTo to={tenantPath(billRunPath(row.id))}>{row.run_no}</InlineLinkTo>
          ),
      },
      {
        key: "cycle",
        label: t("billing.runs.col.cycle"),
        // The SERVER's code, not a lookup: `cycle_code` is served on the row.
        // A run scoped to no cycle — a one-off, an ad-hoc rebill — states that
        // rather than showing a blank, because *not on a cycle* is an answer.
        cell: (row) =>
          row.cycle_code == null ? (
            <Dash>{t("billing.runs.cell.noCycle")}</Dash>
          ) : (
            <span>{row.cycle_code}</span>
          ),
      },
      {
        key: "period",
        label: t("billing.runs.col.period"),
        cell: (row) => (
          <PeriodCell row={row} t={t} timeZone={timeZone} dateFormat={dateFormat} />
        ),
      },
      {
        key: "bills_issued",
        label: t("billing.runs.col.bills"),
        numeric: true,
        // An abandoned run reads 0 and is still a row (p146, note 3).
        cell: (row) => <span className="tabular-nums">{count(row.bills_issued)}</span>,
      },
      {
        key: "value",
        label: t("billing.runs.col.value"),
        numeric: true,
        // CLAUDE.md hard rule 2 — money is stored to 4 decimals and DISPLAYED
        // at 2, through the ONE MoneyCell, always beside its CHAR(3). A run
        // that issued nothing has no value to state rather than a zero.
        // `== null` catches a served null AND a field a fixture did not give —
        // see the note on the shared type. An amount without its currency is
        // never rendered: a bare number is a money claim with no unit.
        cell: (row) =>
          row.value == null || row.value_currency == null ? (
            <Dash>{t("billing.runs.cell.noValue")}</Dash>
          ) : (
            <MoneyCell amount={row.value} currency={row.value_currency} />
          ),
      },
      {
        key: "ran_by_name",
        label: t("billing.runs.col.runBy"),
        cell: (row) =>
          row.ran_by_name == null ? (
            <Dash>{t("billing.runs.cell.noRunBy")}</Dash>
          ) : (
            <span>{row.ran_by_name}</span>
          ),
      },
      {
        key: "status",
        label: t("billing.runs.col.status"),
        // ⚠ **IT READS `row.status` NOW, AND UNTIL 2026-09-15 IT COULD NOT.**
        // The column was written "draft" at creation and no writer advanced it
        // (`DEF-BIL-5352`), so this composed a sentence from `issued_at` and
        // `held` instead — which could say *Issued* and could never say
        // *Corrected* or *Abandoned*, the two words p146 draws and the reason
        // the screen exists. `runs.record_run_outcome` advances it now, so the
        // pill says what the run IS rather than what the evidence implies.
        cell: (row) => (
          <StatusPill tone={RUN_STATUS_TONES[row.status] ?? "neutral"}>
            {t(`billing.runs.status.${row.status}`, { defaultValue: row.status })}
          </StatusPill>
        ),
      },
      {
        key: "actions",
        label: t("billing.runs.col.actions"),
        cell: (row) => (
          <RowActions>
            {/* B14 rule 15's 👁, and a LINK rather than a button: a button
                breaks middle-click and the browser's own "open in new tab",
                which a clerk comparing two runs side by side actually uses. */}
            <RowActionLink
              label={t("billing.runs.action.open")}
              hint={t("billing.runs.action.openHint")}
              icon={<EyeIcon />}
              to={tenantPath(billRunPath(row.id))}
            />
          </RowActions>
        ),
      },
    ],
  };

  return (
    <section data-billing-tab="history">
      {/* The four drawn tiles, above the toolbar exactly as p146 stacks them.
          Absent while the first page is in flight, so the strip does not flash
          four zeroes at a clerk and then correct itself. */}
      {kpis.length > 0 && <KPIStrip kpis={kpis} loading={runsQuery.isPending} />}
      <DataTable<PastRunRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={totalRows}
        loading={runsQuery.isPending}
        error={
          runsQuery.isError
            ? {
                reason: apiErrorText(runsQuery.error, t),
                onRetry: () => void runsQuery.refetch(),
              }
            : null
        }
        empty={{
          title: t("billing.runs.empty"),
          helper: t("billing.runs.emptyHelper"),
        }}
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
        }
      />
      {/* B14 rule 32 — ONE stated absence, a disclosure CLOSED by default, and
          the reference stays on the DOM rather than on the clerk's screen
          (rules 31 and 33).
          ⚠ **IT NAMED FIVE ABSENCES UNTIL 2026-09-15 AND NAMES ONE NOW.** The
          value, the tiles, the search and the status and year filters are all
          served and all drawn; `Export` is the only thing p146 draws that this
          product cannot do, because no export route exists for this read. A
          disclosure that went on naming four things the screen had since grown
          would be the refusal this screen was built to remove, wearing a
          smaller hat. */}
      <RunGap
        title={t("billing.runs.gapTitle")}
        message={t("billing.runs.gap")}
        ruleRef="blueprint p146 · no export route for GET /billing/runs"
      />
    </section>
  );
}

/**
 * The four drawn tiles, in the drawn order, from the served aggregate.
 *
 * Each one is the server's own count over the year. **Nothing here adds
 * anything up**: a tile computed from the rows on screen would be a page's
 * arithmetic presented as a year's fact, which is `NFR-3` in the shape a clerk
 * would actually believe.
 */
export function tileRow(tiles: BillRunTiles, t: Translator): KpiTile[] {
  return [
    {
      id: "runs",
      label: t("billing.runs.tile.runs"),
      value: count(tiles.runs.count), // DEF-BIL-9007 — grouped: 40,017, never 40017
      detail: t("billing.runs.tile.runsDetail", { count: tiles.runs.cycles }),
    },
    {
      id: "bills",
      label: t("billing.runs.tile.bills"),
      value: count(tiles.bills_issued.count),
      // The money is the DETAIL line the drawing puts under the count — see the
      // note where `kpis` is built for why it is not a `money` tile.
      detail:
        tiles.bills_issued.value === null || tiles.bills_issued.currency === null ? (
          t("billing.runs.tile.noValue")
        ) : (
          <MoneyCell amount={tiles.bills_issued.value} currency={tiles.bills_issued.currency} />
        ),
    },
    {
      id: "exceptions",
      label: t("billing.runs.tile.exceptions"),
      value: count(tiles.exceptions.runs),
      detail: tiles.exceptions.all_resolved
        ? t("billing.runs.tile.allResolved")
        : t("billing.runs.tile.someOpen"),
    },
    {
      id: "longest",
      label: t("billing.runs.tile.longest"),
      // ⚠ **THE ONE DRAWN TILE WITH NOTHING BEHIND IT, AND IT IS TYPED THAT
      // WAY.** `BillRunTiles.longest_run` is `null` — not "nullable", but the
      // literal type — because NOTHING RECORDS HOW LONG A BILL RUN TOOK
      // (`DEF-BIL-5376`). p146 draws *58 min · 1,263 accounts*; the product
      // cannot answer either figure, so the tile states the absence rather
      // than printing a zero, which a clerk would read as *it took no time*.
      //
      // **The tripwire is `longestWhenItLands` below**: it fires the day the
      // type stops being `null`, which is the day this tile can be filled.
      value: t("billing.runs.tile.noLongest"),
    },
  ];
}

/**
 * ⚠ **A TRIPWIRE FOR THE LONGEST-RUN TILE (`DEF-BIL-5376`), AND IT IS HERE
 * RATHER THAN IN A TEST ON PURPOSE.** A hold with no test that fires when it
 * expires is a promise nobody is keeping (hard-won law 2), and a hold whose
 * test lives in a file somebody might delete is half a promise. While nothing
 * records a run's duration the served type is the literal `null`, so this
 * assignment compiles; the moment it becomes `{ minutes, accounts } | null`,
 * `tsc` goes RED on this line and names the tile that is owed a figure.
 */
const longestWhenItLands: BillRunTiles["longest_run"] = null;
void longestWhenItLands;

export default PastBillingRunsPanel;
