// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-010 (the parts register — part number, description,
//           category, unit and unit cost, and NO stock level, because none
//           lawfully exists) · US-WRK-009 (the categories it groups by).
//           Screens: Work-025 (asserted for what it must NOT show)
// Rules:    BR-WRK-019 (part no · name · category · uom · unit cost 4 dp
//           displayed 2 — and NO stock level, NO reorder point) ·
//           CLAUDE.md hard rule 2 (4 stored, 2 displayed) · hard rule 3 (a
//           quantity carries its unit) · B14 rule 2 (one page header) ·
//           rule 16 (the shared table's pager footer) · rule 17 (an empty
//           state says what is missing and how to fill it) · rule 19 (this
//           list's own search prompt) · rule 20 (one table type) · rule 21
//           (Tailwind; on route-b-migrated.txt) · rule 31 (no database id is
//           a visible value) · rule 32 (one sentence; no rule id in clerk
//           copy) · BR-SHL-025 (a control that cannot be honoured yet is
//           disabled WITH ITS REASON)
// Tests:    src/features/work/PartsPage.test.tsx
// Impacts:  src/features/work/workEndpoints.ts · src/features/work/
//           WorkShell.tsx (the Parts tab) · src/routing/screenIds.ts (WRK-10)
//           · src/api/queryClient.ts (`queryKeys.workParts`)
// ───────────────────────────────────────────────────────
//
// ⚠⚠ **THIS SCREEN IS ASSERTED FOR WHAT IT DOES NOT SHOW, AND THAT IS THE
// WHOLE POINT OF IT.**
//
// `wireframes/Work-025.png` draws a STOCK register: `MTR-W58 · Water meter
// 5/8" · Yard · On hand 184 · Reorder at 60 · In cover`, the same part on
// *Van 12* as a second row, a banner reading *"Reorder — 2 parts at or below
// reorder level. Roughly 320 units needed to restore cover"*, and a note bar
// saying *"Issues deduct stock the moment they are recorded."*
//
// **The commitment card that specifies this very screen says the opposite** —
// *"No stock levels, no reorder points"* — because the Assets design's own
// decision D5 parked a parts-stock table when Assets was ruled into scope.
// Where a drawing disagrees with its own card, the CARD wins
// (`08-screen-layouts.md`, and the PO's 2026-09-03 ruling that the pack is the
// layout authority does not make a drawing outrank the rule it illustrates).
// The contradiction is filed as `DEF-WRK-3550`; whether a stock table may
// exist at all is `OQ-WRK-1490`, OPEN and routed to the Product Owner.
//
// So: **no ON HAND column, no REORDER AT column, no LOCATION column, no
// reorder banner and no In-cover / Below-reorder pill.** The server publishes
// no such key (`apps/work/selectors.PART_ROW_KEYS`), `POST /work/parts`
// refuses one as an unknown field, and `PartsPage.test.tsx` asserts every one
// of the three by NAME — so a lane cannot add stock quietly from either end.
//
// ⚠ AND NO SENTENCE EXPLAINING THE ABSENCE EITHER. B14 rule 32 gives a screen
// one sentence per section and closes a stated absence by default; a note bar
// reading *"stock levels are not built yet"* would be an internal decision
// printed on a clerk's screen. The absence is recorded here, in the register,
// and in the layouts file — three places a person who needs it will look, and
// none of them is the register a clerk uses to look up a price.
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { Button, ButtonLink } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { FilterBar } from "@/components/FilterBar";
import { PencilIcon, PowerIcon, RetireIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { SegmentedControl } from "@/components/SegmentedControl";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/StatusPill";
import { MoneyCell } from "@/components/MoneyCell";
import { defaultRequestState } from "@/components/tableTypes";
import { seedQueryFromUrl } from "@/routing/seedQueryFromUrl";
import { useTenantPath } from "@/routing/tenantPath";
import type {
  TableConfig,
  TableFilterConfig,
  TableRequestState,
} from "@/components/tableTypes";
import { getLookupEntries } from "@/api/endpoints";
import { Dash } from "@/features/customers/customersShared";

import { AddPartModal } from "./AddPartModal";
import { PartIssueLog } from "./PartIssueLog";
import { useWorkTabs } from "./WorkShell";
import { listParts, updatePart } from "./workEndpoints";
import type { PartRow } from "./workEndpoints";

/** r10's own badge for the parts screen — `01-overview.md` §6, Work-025 ↔ WRK-10. */
export const WORK_PARTS_SCREEN = "WRK-10";

/** The tenant currency this register prices in. `US-WRK-010`'s figures are USD
 *  and every seeded tenant is a US utility; the day a tenant is not, this reads
 *  the tenant's own currency rather than a constant — which is a Regional
 *  setting story, not a parts one. */
const REGISTER_CURRENCY = "USD";

/**
 * Work-025's two segments.
 *
 * ⚠ **THE FIRST ONE IS LABELLED *Register*, AND THE DRAWING LABELS IT *Stock
 * register*.** Dropping the word is the same correction the ON HAND column
 * gets, one level up: a register with no stock in it must not be titled after
 * the thing it does not hold. The divergence is stamped in
 * `08-screen-layouts.md` beside the columns it belongs with.
 *
 * The Issue log is `WM-22`'s and arrives in wave N. It ships VISIBLE AND
 * DISABLED WITH ITS REASON (`BR-SHL-025`) rather than hidden: a person looking
 * for "who took the last two water meters" learns that the answer is coming,
 * instead of concluding the product cannot answer it.
 */
type SegmentId = "register" | "issues";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/**
 * The table's declaration — Work-025's six columns, in the drawing's order,
 * MINUS the three the card forbids. Exported so the test can read the column
 * set without a DOM and assert the three absences by name.
 */
export function partsTableConfig(
  t: Translate,
  cells: {
    category: (row: PartRow) => React.ReactNode;
    unitCost: (row: PartRow) => React.ReactNode;
    status: (row: PartRow) => React.ReactNode;
    /** CR-168 P3.8 / P3.9 — the row's pencil and its switch. Absent = no
     *  action column (the static test reads the column set without one). */
    actions?: (row: PartRow) => React.ReactNode;
  },
  filters: TableFilterConfig[] = [],
): TableConfig<PartRow> {
  return {
    screenId: WORK_PARTS_SCREEN,
    getRowId: (row) => row.id,
    // B14 rule 19 — what the search MATCHES, as the server matches it
    // (`apps/work/selectors.parts_page`: part number OR description).
    searchFields: ["part_no", "name"],
    searchPlaceholder: "work.parts.search",
    filters,
    // The server fixes the order (part number, ascending): a register is a
    // list a person scans, and this only seeds `defaultRequestState`.
    defaultSort: { sort: "part_no", dir: "asc" },
    columns: [
      {
        key: "part_no",
        label: t("work.parts.col.partNo"),
        identity: true,
        cell: (row) => <span className="tabular-nums">{row.part_no}</span>,
      },
      // ruling 32 (PO 2026-09-24) — the part has a NAME; the drawing's
      // DESCRIPTION column is the same field under its old word.
      {
        key: "name",
        label: t("work.parts.col.name"),
        cell: (row) => <span>{row.name}</span>,
      },
      { key: "category", label: t("work.parts.col.category"), cell: cells.category },
      // hard rule 3 — the unit is a COLUMN, not a suffix glued onto the cost.
      {
        key: "unit_of_measure",
        label: t("work.parts.col.unit"),
        cell: (row) => <span>{row.unit_of_measure}</span>,
      },
      {
        key: "unit_cost",
        label: t("work.parts.col.unitCost"),
        numeric: true,
        cell: cells.unitCost,
      },
      { key: "active", label: t("work.parts.col.status"), cell: cells.status },
      ...(cells.actions === undefined
        ? []
        : [
            {
              key: "actions",
              label: t("work.parts.col.actions"),
              cell: cells.actions,
            },
          ]),
    ],
  };
}

export interface PartsPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

/** Work-025 at wave C: the head, the segments, and the register. */
export function PartsPage(props: PartsPageProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const translate: Translate = (key, params) => t(key, params);
  const [segment, setSegment] = useState<SegmentId>("register");
  const [adding, setAdding] = useState(false);
  // CR-168 P3.8 — the part the pencil opened, in the same form as Add part.
  const [editing, setEditing] = useState<PartRow | null>(null);
  // CR-168 P3.9 — the part waiting on the Retire confirm (danger tier).
  const [retiring, setRetiring] = useState<PartRow | null>(null);
  const [switching, setSwitching] = useState(false);

  async function setActive(row: PartRow, active: boolean) {
    setSwitching(true);
    try {
      await updatePart(row.id, { active }, client);
      await queryClient.invalidateQueries({ queryKey: ["work", "parts"] });
    } finally {
      setSwitching(false);
      setRetiring(null);
    }
  }

  // ── CR-168 P3.10 · DEF-WRK-9580 — Category · Unit · Status ─────────────────
  // The categories from the list that owns them (a CODE on the wire, the NAME
  // on screen — B14 rule 31); the units from the register itself, served beside
  // the page; the statuses are the two the column draws.
  const categoriesQuery = useQuery({
    queryKey: ["lookups", "work_parts_categories", "picker"],
    queryFn: () => getLookupEntries("work_parts_categories", { per: 200 }, client),
    retry: false,
  });
  // The Unit filter's choices ride beside each page (`GET /work/parts`'s
  // `units`); the last ones served are kept while the next page loads.
  const unitsRef = useRef<string[]>([]);
  const [servedUnits, setServedUnits] = useState<string[]>([]);
  const units = servedUnits;
  const filters: TableFilterConfig[] = useMemo(
    () => [
      {
        name: "category",
        label: t("work.parts.filter.category"),
        options: [
          ...(categoriesQuery.data?.results ?? []).map((row) => ({
            value: row.code,
            label: row.name,
          })),
          { value: "none", label: t("work.parts.add.categoryNone") },
        ],
      },
      {
        name: "unit",
        label: t("work.parts.filter.unit"),
        options: units.map((unit) => ({ value: unit, label: unit })),
      },
      {
        name: "status",
        label: t("work.parts.filter.status"),
        options: [
          { value: "active", label: t("work.parts.status.active") },
          { value: "inactive", label: t("work.parts.status.inactive") },
        ],
      },
    ],
    [t, categoriesQuery.data, units],
  );

  const config = useMemo(
    () =>
      partsTableConfig(translate, {
        // A part with no category reads as a DASH, never as a blank: a blank
        // cell reads as a bug and a dash reads as "none" (Work-007's own
        // convention, kept identical here).
        category: (row) => (row.category === null ? <Dash /> : <span>{row.category.name}</span>),
        // CLAUDE.md hard rule 2 — the server sends `"92.4000"` and MoneyCell is
        // the one display boundary that trims it to `$92.40`. The string is
        // never parsed into a number on the way (a float here is the exact
        // thing rule 2 forbids).
        unitCost: (row) => <MoneyCell amount={row.unit_cost} currency={REGISTER_CURRENCY} />,
        status: (row) => (
          <StatusPill tone={row.active ? "success" : "muted"}>
            {translate(row.active ? "work.parts.status.active" : "work.parts.status.inactive")}
          </StatusPill>
        ),
        // B14 rule 13 — row actions are ICONS with their name on the button.
        // Edit opens the Add part form filled; Retire asks first (danger tier,
        // rule 6); Reactivate is the undo and needs no confirm.
        actions: (row) => (
          <RowActions>
            <RowAction
              icon={<PencilIcon />}
              label={translate("work.parts.edit")}
              onClick={() => setEditing(row)}
              testId={`edit-part-${row.part_no}`}
            />
            {row.active ? (
              <RowAction
                icon={<RetireIcon />}
                label={translate("work.parts.retire")}
                danger
                onClick={() => setRetiring(row)}
                testId={`retire-part-${row.part_no}`}
              />
            ) : (
              <RowAction
                icon={<PowerIcon />}
                label={translate("work.parts.reactivate")}
                onClick={() => void setActive(row, true)}
                testId={`reactivate-part-${row.part_no}`}
              />
            )}
          </RowActions>
        ),
      }, filters),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, filters],
  );

  // ── DEF-WRK-4094 · CR-073 ────────────────────────────────────────────
  // Universal search's per-group "View all" opens this list as
  // `?q=<term>` (BR-SHL-011's grammar). This screen held its table state
  // locally and never read the query string, so that link promised a
  // filtered list and delivered the whole register — with `tsc` green, the
  // route resolving and the screen rendering perfectly.
  // Seeded ONCE, at mount, and only `q`: this screen does not WRITE the URL
  // back, so reading a page or a sort it will never write would restore, on
  // reload, a state the user had since left. See seedQueryFromUrl's docstring.
  const [searchParams] = useSearchParams();
  const [state, setState] = useState<TableRequestState>(() =>
    seedQueryFromUrl(defaultRequestState(config), searchParams),
  );

  const listQuery = useQuery({
    queryKey: queryKeys.workParts(state.q, state.page, state.per, state.filters),
    queryFn: () =>
      listParts(
        { q: state.q, page: state.page, per: state.per, filters: state.filters },
        client,
      ),
  });
  const latestUnits = listQuery.data?.units;
  if (latestUnits !== undefined && latestUnits.join("\n") !== unitsRef.current.join("\n")) {
    unitsRef.current = latestUnits;
    setServedUnits(latestUnits);
  }

  // The module strip, as the shared header's own props — read at the top level
  // of the component, never inside the JSX, so the hook rule holds by shape.
  const strip = useWorkTabs(t("work.parts.sentence"));
  const tenantPath = useTenantPath();

  return (
    <div data-work-parts="" data-screen={WORK_PARTS_SCREEN}>
      <PageHeader
        // B14 rule 2 — ONE page header, and it carries the module's tab strip:
        // kicker · title · the strip · the one sentence. Until 2026-09-05 the
        // strip was a hand-rolled `<nav>` drawn ABOVE this header by
        // `WorkShell`, which is what made Work the only module in the product
        // whose tabs were boxed rather than underlined (`DEF-WRK-3955`).
        //
        // ⚠ THE SENTENCE IS THE TAB'S EXPLAINER AND NOT A ROLL-UP: the roll-up
        // slot sets no width and `.page-header-explainer` sets
        // `max-width: var(--desc-measure)` — B14 rule 18's 80% cap, which this
        // description ran past on every screen wider than the sentence.
        //
        // The drawing's sentence is *"A system of record — what you own, where
        // it sits, and who took it."* Two of its three clauses describe things
        // this screen does not have (a location, an issue log), so the sentence
        // says what the screen IS rather than what it was drawn as.
        kicker={t("work.parts.kicker")}
        title={t("work.parts.title")}
        {...strip}
        primaryAction={
          // B14 rule 5 (two sizes) and rule 6 (this is not a destructive
          // commit): the shared button kit, never a hand-rolled `btn` class —
          // `btn-secondary` is a stylesheet name and this file is on
          // `route-b-migrated.txt`, where a stylesheet name that the compiler
          // does not emit renders as NOTHING (`routeBUtilities.test.ts` caught
          // exactly that on the first draft of this line).
          <div className="flex gap-2">
            {/* ── CR-077 · THE DOOR TO THE PARTS UPLOAD ────────────────────
                The PO asked for import starters for parts alongside premises,
                units, meters, sub-meters, assets and accounts. It is the SAME
                five-stage runner every one of those uses — the target is the
                only difference (`BR-MET-096`) — so this is a link to a route
                and not a second wizard.

                ⚠ **SECONDARY, and the order is B14 rule 5's:** adding one part
                is what a clerk does every week and uploading a list is what
                they do once, so the primary stays *Add part*. It is a real
                `<a>` through `ButtonLink` rather than a `<span>` with an
                onClick — hard-won law 2's mirror, a live screen behind a dead
                control, is what a non-navigating "link" here would be. */}
            <ButtonLink variant="secondary" to={tenantPath("/work/parts/import")}>
              {t("work.parts.import")}
            </ButtonLink>
            <Button variant="primary" data-add-part="" onClick={() => setAdding(true)}>
              {t("work.parts.add")}
            </Button>
          </div>
        }
      />

      <SegmentedControl
        className="mb-4"
        label={t("work.parts.segments")}
        active={segment}
        onSelect={(id) => setSegment(id as SegmentId)}
        // CR-168 P3.11 · DEF-WRK-9574 — the Issue log is RELEASED: its
        // endpoint, its wrapper and parts on jobs have all landed, so the
        // segment opens the log instead of explaining why it cannot.
        segments={[
          { id: "register", label: t("work.parts.segment.register") },
          { id: "issues", label: t("work.parts.segment.issues") },
        ]}
      />

      {segment === "issues" ? (
        <PartIssueLog client={client} />
      ) : (
      <DataTable<PartRow>
        config={config}
        state={state}
        onStateChange={setState}
        filterBarSlot={<FilterBar filters={filters} state={state} onStateChange={setState} />}
        rows={listQuery.data?.results ?? []}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isPending}
        error={
          listQuery.isError
            ? { reason: t("work.parts.loadFailed"), onRetry: () => void listQuery.refetch() }
            : null
        }
        empty={{
          title: t("work.parts.empty.title"),
          helper: t("work.parts.empty.helper"),
          ctaLabel: t("work.parts.empty.cta"),
          // B14 rule 4 / BR-SHL-044 — the page header two hundred pixels above
          // already carries `+ Add part` as this screen's ONE primary, and an
          // empty register drew the same words in the same red a second time.
          // r10 rule 17 still gets the action that fills the list; rule 4 gets
          // its one primary (PO 2026-09-04, `DEF-3722`).
          ctaVariant: "secondary",
          onCta: () => setAdding(true),
        }}
      />
      )}

      {(adding || editing !== null) && (
        <AddPartModal
          client={client}
          part={editing ?? undefined}
          onClose={() => {
            setAdding(false);
            setEditing(null);
          }}
          onAdded={() => {
            setAdding(false);
            setEditing(null);
            void queryClient.invalidateQueries({ queryKey: ["work", "parts"] });
          }}
        />
      )}

      {retiring !== null && (
        <ConfirmDialog
          title={t("work.parts.retireConfirm.title", { part: retiring.part_no })}
          consequence={t("work.parts.retireConfirm.consequence")}
          confirmLabel={t("work.parts.retireConfirm.confirm")}
          confirmVariant="danger"
          working={switching}
          onConfirm={() => void setActive(retiring, false)}
          onCancel={() => setRetiring(null)}
        />
      )}
    </div>
  );
}

export default PartsPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-010@81bb7e45 · US-WRK-009@81bb7e45 (EP-WRK-02) · 08-screen-layouts.md Work-025 · 09-component-inventory.md W1 + SegmentedControl · wireframes/Work-025.png
// generated: 2026-09-04 by the CR-070 wave C build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST — with an `on_hand` column added to partsTableConfig, PartsPage.test.tsx fails "the register draws no stock column"; quoted in the lane report. tsc · eslint · vitest · routeBUtilities.test.ts · the cr070-c walkthrough (computed style, no sideways scroll, no id in clerk copy)
// exceptions: ON HAND · REORDER AT · LOCATION · the reorder banner · the In-cover pill are NOT drawn — the card over the drawing (DEF-WRK-3550, OQ-WRK-1490) · the Issue log segment is disabled with its reason until wave N (WM-22) · the first segment reads *Register*, not the drawing's *Stock register* · E4 the DESCRIPTION is *What your crews fit, and what each one costs.* and not the drawing's *A system of record — what you own, where it sits, and who took it.* — two of the drawing's three clauses promise capabilities this screen does not have (*where it sits* is the LOCATION column, *who took it* is the ISSUE LOG, both held), and a sentence promising two absent things is worse than a shorter one (rule 32). It returns to the drawing's wording when the issue log lands in wave N · E4 a **UNIT** column is ADDED between CATEGORY and UNIT COST, which the drawing does not draw — CLAUDE.md hard rule 3, a quantity carries its unit, and *78.40* is a price per something the drawing never names. The only column on these six screens the product adds rather than drops · E4 no `STOCK REGISTER` / `ISSUE LOG` captions above the tables — the module-wide decision in `08-screen-layouts.md`
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
