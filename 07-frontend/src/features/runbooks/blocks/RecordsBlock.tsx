// ── Trace ──────────────────────────────────────────────
// Story: US-RBS-016 · CR-075 wave C task C2 — block 4 of the twelve, and the
//        LAST one to be built. `C1b` deliberately left it: it is the only block
//        that PAGES, so it owns a request state, and a request state belongs to
//        the renderer (`RBS-006`) rather than to a block.
// Screens: RBS-006-R1 regions 4·5·6, and every RBS-006-R* except R4, R13, R19.
// Rules: `NFR-3` (every list pages server-side, `per` clamped
//        50/100/200/500/1000) · B14 rule 20 (ONE table type) · rule 12 (the
//        toolbar's order) · rule 16 (the pagination footer) · rule 31 (no
//        database id is ever the visible value of a field) · rule 36 (the
//        shared kit is how you comply) · `BR-RBS-020` (the report is composed
//        at close and FROZEN).
// Tests: src/features/runbooks/blocks/records.test.tsx
// ───────────────────────────────────────────────────────
//
// **THE BLOCK THAT PAGES, AND THE ONE THAT CARRIES THE COVERAGE GRID.**
// `display: "grid"` is the same block drawn as cells — `10-execution-plan.md`
// C1a, *"phase 2's coverage grid IS that grid mode"*. That is why phase 2 needs
// no new screen for it and why this file has two render paths rather than two
// components.
//
// ⚠ **IT USES `DataTable`, AND THE OTHER THREE TABULAR BLOCKS MUST NOT.**
// `ReportTable.tsx`'s own header states the split: Breakdown, Reconciled and
// Row decisions draw a FROZEN array and would have to invent an `onStateChange`
// that never fires. This block is the exception because its rows genuinely
// arrive a page at a time — `RecordsPayload.rows` is *the current page* and
// `total` is the server's count, exactly as `DataTableProps` already declares
// them (`rows` = "the CURRENT PAGE only", `totalRows` = "server-provided
// total"). Nothing here re-slices an array locally; a page change is a callback
// the renderer answers.
//
// ⚠ **THE STATE IS A PROP, NOT A `useState` HERE, AND THAT IS THE WHOLE REASON
// THIS FILE WAITED FOR `C2`.** A block holding its own query state would page a
// list the screen does not know it is paging, and the screen owns the URL, the
// fetch and the frozen report around it. `09-component-inventory.md`: *"every
// one of those is a question about a QUERY that the RENDERER holds and a block
// does not."*
//
// ⚠ **THE EMPTY STATE DRAWS NO CALL TO ACTION, AND THAT IS A RULED DIVERGENCE
// FROM B14 RULE 17.** Rule 17 asks for *what is missing and the action that
// fills it*, which is right for a list nobody has filled yet — the shape
// `EmptyList` is built for. A Check that finds nothing is the OPPOSITE: it is a
// good outcome, not a gap, and *"Nothing stops billing."* needs no button
// because there is nothing to do. `RecordsPayload.empty` is declared with two
// fields and no CTA for exactly this reason, so the type already carries the
// decision. The divergence is stamped in `08-screen-layouts.md`.
import { useTranslation } from "react-i18next";

import { ChipToggle, ChipRow } from "@/components/Chip";
import { DataTable } from "@/components/DataTable";
import { ListPager } from "@/components/ListPager";
import { RecordGrid } from "@/components/RecordGrid";
import type { RecordGridCell } from "@/components/RecordGrid";
import type { PageSize, TableConfig, TableRequestState } from "@/components/tableTypes";

import { ReportValueCell, reportValueText } from "./ReportValueCell";
import type { BlockContext, RecordsPayload, ReportRow } from "./types";

/** What the renderer hands this block besides its payload.
 *
 *  ⚠ Every field is REQUIRED. An optional callback nothing passes is dead UI —
 *  hard-won law 2, four defects in one day — and this block's whole purpose is
 *  to be driven from outside. `tsc` refuses a caller that forgets one. */
export interface RecordsBlockProps {
  payload: RecordsPayload;
  ctx: BlockContext;
  /** The query behind `payload.rows`. The renderer owns it and the URL. */
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  loading: boolean;
  /** Which chip is pressed, and what happens when another is. `null` while the
   *  payload declares none — the chips are per-runbook, not universal. */
  chip: { selected: string; onSelect: (id: string) => void } | null;
  /** Keys the saved column set (`table.<screenId>.columns`, BR-SHL-013). One
   *  runbook's findings table is not another's, so the runbook's key rides
   *  here rather than a bare `"RBS-006"` that would share one saved set across
   *  thirty-four different column lists. */
  screenId: string;
}

/** `payload.columns` → a `TableConfig`. The cell renderer is `ReportValueCell`
 *  for every column, which is what makes the twelve blocks draw thirty-four
 *  runbooks: each cell says what it IS and the kind picks the formatter, so no
 *  screen ever decides that money is money. */
function configFrom(payload: RecordsPayload, ctx: BlockContext, screenId: string): TableConfig<ReportRow> {
  return {
    screenId,
    getRowId: (row) => row.id,
    // ⚠ **THE FIRST COLUMN, AND THE ENGINE'S OWN ORDER IS WHAT SHIPS.** A
    // frozen report's rows arrive in the order the runbook produced them — for
    // runbook 1 that is step order, so the three blockers read before the six
    // warnings exactly as `RBS-006-R1` draws them. `defaultSort` is REQUIRED by
    // `TableConfig` and is what the pager's first request carries; it names the
    // first declared column so a table whose columns differ per runbook still
    // has a valid one, and a reader re-sorts from there.
    defaultSort: { sort: payload.columns[0]?.key ?? "id", dir: "asc" },
    columns: payload.columns.map((column) => ({
      key: column.key,
      label: column.label,
      sortable: column.sortable,
      numeric: column.numeric,
      // ⚠ `row.id` is never drawn — B14 rule 31. It is the key and nothing else.
      cell: (row: ReportRow) => {
        const value = row.cells[column.key];
        return value === undefined ? null : <ReportValueCell value={value} ctx={ctx} />;
      },
    })),
  };
}

/** Grid mode. Every cell is a real link — `RecordGrid` cannot express a dead
 *  one, which is why `linkKey` is required rather than optional.
 *
 *  ⚠ **`ctx.toHref`, NEVER `value.to` — `DEF-RBS-4354`, WHICH IS `DEF-RBS-4329`
 *  ONE DISPLAY MODE OVER.** Every runbook emits its routes TENANT-RELATIVE
 *  (`runbooks/test_bill/runs/<id>`, `settings/services`), because the shell is
 *  what knows the tenant. Handed straight to `<Link to>`, React Router resolves
 *  it against the CURRENT route — so from `/:tenant/runbooks/:key/runs/:runId`
 *  every coverage-grid cell would open
 *  `…/runs/<grid>/runbooks/test_bill/runs/<cell>` and land on nothing. The
 *  table path one screen down has called `ctx.toHref` since `DEF-RBS-4329`;
 *  this path was written before any runbook emitted a grid, so it had never
 *  been rendered with a real route and no check could see it: the component's
 *  own DOM test passes absolute paths straight in, `blocks.test.tsx` renders
 *  outside any tenant route, and an href assertion that ends with the route is
 *  satisfied by a wrongly PREFIXED one. */
function cellsFrom(payload: RecordsPayload, ctx: BlockContext): RecordGridCell[] {
  const grid = payload.grid;
  if (grid === undefined) {
    return [];
  }
  return payload.rows.map((row) => {
    const label = row.cells[grid.labelKey];
    const link = row.cells[grid.linkKey];
    const reason = grid.reasonKey === undefined ? undefined : row.cells[grid.reasonKey];
    return {
      id: row.id,
      label: reportValueText(label) ?? "",
      state: grid.stateByRowId[row.id] ?? "clean",
      // A `link` value carries where it goes; anything else has no destination
      // and the empty string is refused by `RecordGrid` rather than drawn dead.
      to: link !== undefined && link.kind === "link" ? ctx.toHref(link.to) : "",
      reason: reason === undefined ? undefined : (reportValueText(reason) ?? undefined),
    };
  });
}

export function RecordsBlock(props: RecordsBlockProps) {
  const { t } = useTranslation();
  const { payload, state, onStateChange } = props;

  // The chips are region 4 of `RBS-006-R1` — *All 9* · *Blockers 3* ·
  // *Warnings 6*, the selected one inverted to an ink fill. `ChipToggle` is the
  // kit's "one of a set, exactly one selected" control, so this row looks like
  // every other chip row in the product (B14 rule 36).
  const chips =
    payload.chips === undefined || payload.chips.length === 0 || props.chip === null ? null : (
      <ChipRow data-records-chips="">
        {payload.chips.map((entry) => (
          <ChipToggle
            key={entry.id}
            selected={props.chip !== null && props.chip.selected === entry.id}
            onClick={() => props.chip?.onSelect(entry.id)}
          >
            {`${entry.label} ${entry.count}`}
          </ChipToggle>
        ))}
      </ChipRow>
    );

  // ⚠ **THE EMPTY STATE IS THIS BLOCK'S, NOT `DataTable`'s.** `DataTable` draws
  // `EmptyList` when the total is zero, and `EmptyList` REQUIRES a CTA — so
  // letting it through would mean inventing a button for a Check that found
  // nothing wrong. Short-circuiting here is what lets the payload's two-field
  // `empty` stay two fields. See the header for the rule-17 divergence.
  if (!props.loading && payload.total === 0) {
    return (
      <section data-block="records" data-records-empty="">
        <div className="state-frame state-empty">
          <h4>{payload.empty.title}</h4>
          <p className="state-helper">{payload.empty.helper}</p>
        </div>
      </section>
    );
  }

  if (payload.display === "grid") {
    return (
      <section data-block="records" data-records-display="grid">
        {chips}
        <RecordGrid
          cells={cellsFrom(payload, props.ctx)}
          label={payload.empty.title}
          empty={<p className="state-helper">{payload.empty.helper}</p>}
        />
        {/* Grid mode pages too — `NFR-3` has no exception for a grid, and a
            utility at the top of the ICP puts 40,000 accounts through it. */}
        <ListPager
          total={payload.total}
          page={state.page}
          per={state.per}
          onPage={(page) => onStateChange({ ...state, page })}
          onPer={(per: PageSize) => onStateChange({ ...state, per, page: 1 })}
        />
      </section>
    );
  }

  return (
    <section data-block="records" data-records-display="table">
      <DataTable<ReportRow>
        config={configFrom(payload, props.ctx, props.screenId)}
        state={state}
        onStateChange={onStateChange}
        rows={payload.rows}
        totalRows={payload.total}
        loading={props.loading}
        filterBarSlot={chips}
        empty={{
          // Unreachable — the zero case returns above — but `DataTable` requires
          // the block, and a lie here would be a promise nobody keeps. The CTA
          // is drawn DISABLED with its reason, which is the honest shape for a
          // button that has nothing to open (BR-SHL-025).
          title: payload.empty.title,
          helper: payload.empty.helper,
          ctaLabel: t("runbooks.records.empty.cta"),
          ctaReason: t("runbooks.records.empty.reason"),
          onCta: () => undefined,
        }}
      />
    </section>
  );
}
