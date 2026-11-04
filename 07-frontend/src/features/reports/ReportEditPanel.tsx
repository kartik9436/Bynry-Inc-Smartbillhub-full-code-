// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 5 task `P5.3`
//          (*"Screen 2·2 — the edit panel beside the live table. Every change
//          re-runs the preview"*) and `P5.11` (*"Columns: reorder and rename"*).
//          Outcome `P5.3`: *"Adding a column shows it in the rows below
//          without a save."* Outcome `P5.11`: *"`Account` can become
//          `Account No` and move left, without touching code."*
//          Screens: 2·2 (A1 S47)
// Rules:   **PO ruling 2026-09-26 — A PANEL, NOT A WIZARD** (decision log,
//          2026-09-26). It breaks a 42-file `WizardFrame` convention and was
//          raised as such: *"A forward fence fights that, and commit-at-the-end
//          means you cannot see your report until you have finished describing
//          it."* Cited, not re-derived ·
//          B14 rule 43 (a piece of UI is built as a COMPONENT — this file is
//          why 2·2 is not 120 lines inline in the viewer) · rule 44 (the
//          drawing says WHAT is on screen and HOW ARRANGED; OUR standard says
//          how it is BUILT, and wins) · rule 40 (page head 32px — `PageHeader`
//          owns it, and this panel is not a page head) · rule 33 (a LABEL ≤ 3
//          words, a FACT ≤ 6, RATIONALE zero words on screen) · rule 31 (no
//          database id is ever the visible value of a field) · rule 21
//          (Tailwind utilities; this file is on `route-b-migrated.txt`) ·
//          rule 5 (two button sizes) · rule 12 (the table keeps its own toolbar)
// Tests:   07-frontend/src/features/reports/reportEditPanel.dom.test.tsx
// Impacts: ReportViewerPage.tsx (mounts it beside the table) ·
//          SaveReportAsModal.tsx (2·4, which this panel opens) ·
//          api/reportsEndpoints.ts (`getReportDatasets`)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PANEL IS ON THE RIGHT AND THE TABLE STAYS LIVE UNDERNEATH IT.**
// That is a SPATIAL fact and no sentence of the task table carries it — it was
// read off p31 as an image, which is B14 rule 42. At 1440 the drawing puts the
// report's table in the left column and a single narrow column of stacked
// sections on the right, running the full height of the content area. The table
// does not become a preview pane and it does not shrink to a thumbnail: it is
// the SAME table 2·1 renders, with its own toolbar, its own pager and its own
// rows, one column narrower.
//
// ⚠ **AND THAT IS THE RULING, NOT A LAYOUT PREFERENCE.** p31 callout ⑨: *"The
// table is live — every change above re-runs the preview underneath. This is
// why it is a panel and not a wizard: a forward fence would hide the one thing
// you are trying to see."* A wizard gives a numbered rail, a forward fence and
// one commit at the end, which is right for a linear task. Building a report is
// iterative — change a column, see the rows change, change it back.
//
// ⚠ **SEVEN SECTIONS, NOT TWO.** A summary of this screen called it *"two
// sections"*; the drawing has ① Report · ② Attributes · ③ Measures · ④ Filters
// · ⑤ Group & sort · ⑦ Where it lives, with ⑥ the unsaved marker in the rollup
// and ⑧ the calendar inside ①. Counted off the rendered page.
//
// ⚠ **AN UNTICKED COLUMN IS AN EMPTY BOX AND IS NEVER GREYED** (p31 callout ②,
// and it is the defect the PO found). Grey means *you cannot*; these you can.
// The first draft greyed them and the PO, looking at the panel, said *"the user
// cannot add columns"* — which was two thirds wrong and one third right, and
// the two thirds are fixed here: a column can be REORDERED and a heading can be
// RENAMED, both of which are definition data and neither of which needed a
// dataset change. The third is stated rather than hidden: you cannot invent a
// column the dataset does not produce, so the header says how many there ARE
// (*"4 of 7"*) and a clerk can see the list is complete rather than wondering
// what is behind the grey.
//
// ⚠ **B14 RULE 9 SAYS NO WALL OF CHECKBOXES AND THIS IS NOT ONE.** Rule 9's
// subject is a FIELD that picks several values from a flat set, and the kit's
// multi-select is the answer there. This is an ORDERED list whose rows each
// carry three affordances — show, move, rename — and a multi-select can express
// none of the last two. `P5.11` requires both by name. The kit is still what it
// is BUILT from (rule 44): the kit's checkbox, the kit's icon buttons, the
// kit's tokens and spacing, and not one class in a stylesheet.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { ChevronDownIcon, ChevronUpIcon, PencilIcon, TrashIcon } from "@/components/icons";
import { Panel } from "@/components/Panel";

import { reportWord } from "./reportsShared";

import type {
  ReportDataset,
  ReportDefinitionDraft,
  ReportVisibility,
} from "@/api/reportsEndpoints";

/** What the panel is holding — the definition, in flight, before any save.
 *
 *  ⚠ **`renames` IS NOT A DATASET CONCERN AND THAT IS `P5.11`'s WHOLE POINT.**
 *  `Account` becoming `Account No` changes no query and reads no new column: it
 *  is a heading a utility chose, so it lives on the definition and travels in
 *  `filters` under a reserved key the runner already passes through. */
export interface ReportDraftState {
  /** The dataset code, from `GET /reports/datasets`. Changing it RESETS columns
   *  and filters, because they belong to the dataset (p31 callout ①). */
  dataset: string;
  /** Ordered. The order IS the column order on the table — `P5.11`. */
  columns: string[];
  filters: Record<string, string>;
  /** At most three levels (`P2.17`, enforced server-side at save). */
  group_by: string[];
  sort: string[];
  group: string;
  sub_group: string | null;
  service_codes: string[];
  visibility: ReportVisibility;
  /** `{ column: heading }` — a utility's own words for a column. */
  renames: Record<string, string>;
}

/** A blank draft from a dataset and the definition a clerk opened. */
export function draftFrom(
  dataset: string,
  seed: Partial<ReportDraftState> = {},
): ReportDraftState {
  return {
    dataset,
    columns: [],
    filters: {},
    group_by: [],
    sort: [],
    group: "",
    sub_group: null,
    service_codes: [],
    // BR-REP-019 — private is the RULING, not a preference (`P5.7`).
    visibility: "private",
    renames: {},
    ...seed,
  };
}

/** The draft, as the wire wants it.
 *
 *  ⚠ **THE RENAMES RIDE IN `filters` UNDER ONE RESERVED KEY**, which
 *  `runner._DEFINITION_BOOKKEEPING` already passes through untouched. A second
 *  JSON column for them would be a migration for a label. */
export function draftToWire(
  draft: ReportDraftState,
  name: string,
  basedOn: string | null,
): ReportDefinitionDraft {
  // ⚠ **A FILTER ON THE BAR WITH NO VALUE IS *ALL*, AND *ALL* IS NOT A
  //    PARAMETER** (`DEF-REP-7080`). Since the filters section became
  //    progressive — only the filters a clerk has ADDED are drawn — a row's
  //    PRESENCE is what puts it on the slicer bar and its VALUE is what
  //    narrows the report. An added-but-blank row therefore has to reach the
  //    save as nothing at all, or `POST /reports/definitions` is handed
  //    `{"consumer_class": ""}` and the saved report asks for a class whose
  //    name is the empty string.
  const filters: Record<string, string> = {};
  for (const [name, value] of Object.entries(draft.filters)) {
    if (value !== "") filters[name] = value;
  }
  if (Object.keys(draft.renames).length > 0) {
    filters.renames = JSON.stringify(draft.renames);
  }
  return {
    name,
    dataset: draft.dataset,
    group: draft.group,
    sub_group: draft.sub_group,
    columns: draft.columns,
    filters,
    group_by: draft.group_by,
    sort: draft.sort,
    service_codes: draft.service_codes,
    visibility: draft.visibility,
    based_on: basedOn,
  };
}

/** Move `name` one place towards the front or the back of an ordered list.
 *
 *  Exported because it is arithmetic and `P5.11`'s outcome is asserted on it
 *  directly — *"`Account` can … move left"* — without mounting a drag. */
export function moved(order: string[], name: string, delta: -1 | 1): string[] {
  const at = order.indexOf(name);
  if (at < 0) return order;
  const to = at + delta;
  if (to < 0 || to >= order.length) return order;
  const next = [...order];
  next.splice(at, 1);
  next.splice(to, 0, name);
  return next;
}

function SectionHeading(props: { label: string; count?: string }) {
  return (
    <div className="mb-2 flex items-baseline justify-between gap-2">
      <h3 className="m-0 text-xs uppercase tracking-wide text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
        {props.label}
      </h3>
      {/* ⚠ A FACT, ≤ 6 words (rule 33): *"4 of 7"*, *"13 available"*. It is
          here because a clerk who can see the list is complete stops wondering
          what is hidden — p31 callout ②/④. */}
      {props.count === undefined ? null : (
        <span className="text-xs text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">{props.count}</span>
      )}
    </div>
  );
}

/** ⚠ `border-divider`, NOT `border-border` — `DEF-REP-6924`. `border` is not a
 *  colour this product declares: the theme's edge token is `--color-divider`,
 *  and Tailwind emits no rule at all for `border-border`. The three borders in
 *  this panel therefore drew at the browser's own `currentColor` default while
 *  `tsc`, eslint and `toHaveClass()` all passed. `G134` names a token like this
 *  one by running the real compiler over it; nothing else in the repo can. */
function Row(props: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 border-b border-divider px-2 py-1.5 last:border-b-0">
      {props.children}
    </div>
  );
}

/**
 * Screen 2·2's edit panel — the column on the right of the live table.
 *
 * ⚠ **IT OWNS NO TABLE AND FETCHES NO ROWS.** `onChange` fires on every
 * keystroke and tick, the page re-runs the report with the new definition, and
 * the rows below change. That is the whole of `P5.3`'s outcome — *"Adding a
 * column shows it in the rows below without a save"* — and it works because the
 * preview IS the viewer rather than a second renderer that could disagree
 * with it.
 */
export function ReportEditPanel(props: {
  dataset: ReportDataset | undefined;
  /** Every dataset this deployment declares, for section ①'s chooser. */
  datasets: ReportDataset[];
  draft: ReportDraftState;
  onChange: (next: ReportDraftState) => void;
  /** The catalogue's groups, for section ⑦. Served, never a literal (`P1.5`). */
  groups: { code: string; name: string; sub_groups: { code: string; name: string }[] }[];
  onSaveAs: () => void;
  onCancel: () => void;
  /** Absent means this is a built-in and the only way out is **Save as** —
   *  copy on write, and `Save` is not drawn at all rather than drawn dead. */
  onSave?: () => void;
  saving?: boolean;
  /** ⚠ **THE FIRST THING IN THE PANEL, AND IT IS A SLOT** (`DEF-REP-7070`).
   *  `ReportRequiredInputs` needs an API client to search; this panel needs
   *  none and must go on being mountable from a DOM test with no query client.
   *  So the PAGE composes it and hands it in, which is also why this file
   *  carries no idea of what a statement is. `undefined` on the forty-five
   *  reports that are about nothing in particular — and then no Panel is drawn
   *  at all, rather than an empty one. */
  requiredInputs?: React.ReactNode;
  /** ⚠ **THE COLUMNS *THIS REPORT* SERVES, WHERE THEY ARE NOT ITS DATASET'S**
   *  (`DEF-REP-7072`).
   *
   *  A report served by a MODULE VIEWER has a column vocabulary of its own: the
   *  statement serves seven names and the `journal_lines` dataset declares
   *  five, and the two lists intersect in `reference` and in nothing else. This
   *  panel drew the dataset's five, the runner honoured the dataset's five, and
   *  opening the editor therefore cut a seven-column statement to ONE column.
   *  **Neither half was wrong about its own vocabulary**, which is why `tsc`,
   *  every DOM case and every gate passed over it.
   *
   *  The server now publishes one list — the same function the runner honours —
   *  so the offer cannot outrun the honour. `undefined` on every one of the
   *  forty-five dataset-backed reports, which go on reading `dataset` exactly
   *  as they did; a report with this prop has NO measures section, because a
   *  viewer's columns are its columns and the dataset's measures are not among
   *  them. */
  columnChoices?: readonly string[];
  /** ⚠ **WHERE THIS STACK OF SECTIONS IS STANDING** (PO ruling 2026-09-28 —
   *  *"the report editor — panel or its own page - own page"*).
   *
   *  `"panel"` is exactly what shipped: a narrow `<aside>` beside the live
   *  table, with its own Cancel / Save as footer. `"page"` is the same
   *  sections, the same arithmetic and the same `columnChoices` contract,
   *  standing as the MAIN content of `ReportEditorPage` — so the width cap
   *  and the footer come off, because the page head owns the actions there
   *  (B14 rule 44: the kit says how a screen is built).
   *
   *  ⚠ **IT IS ONE COMPONENT AND NOT TWO, WHICH IS THE WHOLE REASON THIS PROP
   *  EXISTS** (B14 rule 43). A second copy of the sections for the page would
   *  be a second place for `columnChoices` to be forgotten — and forgetting it
   *  collapses a seven-column statement to one column with `tsc` and every
   *  test green (`DEF-REP-7072`). */
  variant?: "panel" | "page";
}) {
  const { t } = useTranslation();
  const { dataset, draft, onChange } = props;
  const variant = props.variant ?? "panel";
  // An `<aside>` is complementary to something else on the screen; on the page
  // these sections ARE the something else. The element is the meaning, so it
  // moves with the variant rather than being styled into looking right.
  const Wrapper = variant === "page" ? "div" : "aside";
  const [renaming, setRenaming] = useState<string | null>(null);

  // ⚠ **THE NAMES ONLY** — every use below reads `.name` and nothing else, and
  // a list of names is what the two sources have in common (`DEF-REP-7072`).
  const attributes = useMemo(() => {
    // The REPORT's own vocabulary wins where it has one: a module viewer serves
    // columns no dataset declares, and offering the dataset's instead is what
    // collapsed the statement to a single column.
    if (props.columnChoices !== undefined) return [...props.columnChoices];
    if (dataset === undefined) return [];
    const measures = new Set(dataset.measures.map((m) => m.name));
    return dataset.columns
      .filter((column) => !measures.has(column.name))
      .map((column) => column.name);
  }, [dataset, props.columnChoices]);

  // ⚠ The ORDER a clerk sees is the ORDER on the definition, then everything
  // they have not ticked. Sorting by the dataset's order would silently undo a
  // reorder every time the panel re-rendered.
  const ordered = useMemo(() => {
    const chosen = draft.columns.filter((name) => attributes.includes(name));
    const rest = attributes.filter((name) => !chosen.includes(name));
    return [...chosen, ...rest];
  }, [attributes, draft.columns]);

  // ⚠ **THE PANEL'S DISPLAY ORDER COVERS MEASURES TOO, AND THE FIRST TWO
  // DRAFTS DID NOT.** `ordered` is the ATTRIBUTE rows; a dataset's MEASURES —
  // `usage`, `amount` — are drawn in their own section and are columns on the
  // table just the same. Rebuilding `columns` from `ordered` alone therefore
  // dropped every measure the moment a clerk ticked anything: the browser walk
  // measured 8 columns becoming 5, and *Usage* and *Amount* left a billing
  // register without anybody asking. Attributes first, then measures in the
  // dataset's own order, and both toggling and reordering read THIS list — so
  // the table's column order is the panel's row order with no second rule.
  const displayOrder = useMemo(() => {
    // ⚠ **A MODULE VIEWER HAS NO DATASET MEASURES TO ADD** (`DEF-REP-7072`).
    // Its served list IS its columns; appending `journal_lines`' measures here
    // would put names back into the ticked set that the runner cannot honour,
    // which is the defect arriving through the other door.
    if (props.columnChoices !== undefined) return ordered;
    const measures = (dataset?.measures ?? [])
      .map((measure) => measure.name)
      .filter((name) => !ordered.includes(name));
    return [...ordered, ...measures];
  }, [ordered, dataset, props.columnChoices]);

  const set = (patch: Partial<ReportDraftState>) => onChange({ ...draft, ...patch });

  // ⚠ **A RE-TICKED COLUMN COMES BACK WHERE THE PANEL SHOWS IT, NOT AT THE
  // END.** The first draft appended, so unticking *Bill #* and ticking it
  // again moved it from first to last — the panel's own list said one thing and
  // the table said another, which is the drift `P5.11` exists to remove.
  // Walked in a browser on 2026-09-27; every DOM case passed over it, because
  // they assert the SET and not the ORDER.
  //
  // Rebuilding from `ordered` also means the table's column order IS the
  // panel's row order, always, with no second rule to keep in step.
  const toggle = (name: string) => {
    const wanted = new Set(draft.columns);
    if (wanted.has(name)) wanted.delete(name);
    else wanted.add(name);
    set({ columns: displayOrder.filter((one) => wanted.has(one)) });
  };

  const filterNames = dataset?.filters ?? [];
  // ── `DEF-REP-7080` · THE FILTERS SECTION DREW EVERY DECLARED FILTER ───────
  //
  // ⚠ **THIRTEEN DECLARED FILTERS DREW THIRTEEN STACKED ROWS, AND THE DRAWING
  // DRAWS THREE.** p31 §4 shows only the filters CARRYING A VALUE, then
  // `+ Add filter`, then the footer `Show on the bar · 4 of 13`. The old code
  // mapped `dataset.filters` whole, so the `journal_lines` dataset's ten and
  // the payments dataset's thirteen each became a wall a clerk had to scroll
  // past to reach *Group & sort* — which is a large part of what *"as a user I
  // don't know what I'm doing"* was looking at.
  //
  // ⚠ **PRESENCE PUTS A FILTER ON THE BAR; VALUE NARROWS THE REPORT.** The
  // drawing's own second row is `Consumer class → All`: a filter that is on
  // the bar and is not narrowing anything. So a key present with an empty
  // value is a legitimate state and the input no longer deletes the key when
  // it is cleared — the trash control does, and `draftToWire` drops the empty
  // value so the SAVE never carries it.
  const chosenFilters = filterNames.filter((name) => draft.filters[name] !== undefined);
  const offerableFilters = filterNames.filter((name) => draft.filters[name] === undefined);
  const onTheBar = chosenFilters.length;

  return (
    // ⚠ **WIDTH AND POSITION ARE THE DRAWING'S; THE NUMBERS ARE OURS**
    // (rule 44, and rule 37 — a figure drawn in a wireframe is an
    // illustration). The drawing puts a narrow fixed column on the right; the
    // width is a token on our scale rather than the pixels measured off the
    // page, and it collapses under the table at phone width because our
    // standard says a layout works at phone width and the drawing only ever
    // spoke at 1440.
    <Wrapper
      data-report-edit-panel
      data-report-edit-variant={variant}
      // ⚠ **THE WIDTH CAP IS THE PANEL'S AND ONLY THE PANEL'S.** On the page
      // this stack IS the content, so it takes the column its parent gives it
      // and the parent decides the measure (rule 44 — our standard owns how it
      // is built). `lg:w-60` on a page would reproduce the cramped column the
      // Product Owner was looking at when they asked for a page.
      className={
        variant === "page"
          ? "flex w-full flex-col gap-4"
          : "flex w-full shrink-0 flex-col gap-4 lg:w-60"
      }
      aria-label={t("reports.edit.eyebrow")}
    >
      {/* ⚠ **① IS NO LONGER THE FIRST THING — `DEF-REP-7070`.** A report that
          is ABOUT one record cannot answer anything until it has been told
          which one, so that question comes before the dataset, the columns and
          the filters. Before this, the statement editor opened on four tiles
          reading *Not counted yet* and a table reading *No rows match — Widen
          the dates or filters*, over an instruction that cannot work: no
          window contains rows until an account is named. The sentence that
          DOES explain it was four scroll-lengths below the fold.

          ⚠ **AND IT IS ABSENT WHERE NOTHING IS REQUIRED, WHICH IS THE HALF
          THAT IS EASY TO GET WRONG.** Forty-five of the forty-six reports
          declare no required input; a chooser on one of those is a step the
          screen invented. `requiredInputs` is `undefined` there and no Panel
          is drawn — not a Panel holding nothing. */}
      {props.requiredInputs === undefined ? null : <Panel>{props.requiredInputs}</Panel>}

      {/* ① REPORT */}
      <Panel>
        <SectionHeading label={t("reports.edit.section.report")} />
        {/* ⚠ **THE LABEL IS A SIBLING AND NOT A WRAPPER, AND THAT IS NOT A
            STYLE CHOICE — IT IS THE ONLY WAY THIS ROW READS AS A ROW**
            (`DEF-REP-7201`, measured in a browser at 1440 on 2026-09-28).
            `index.css` carries a global
            `.view label:has(> select) { flex-direction: column }`, which
            OUTRANKS this element's `flex items-center justify-between`: a
            utility class is (0,1,0) and that selector is (0,1,2). So the word
            *Dataset* drew CENTRED ABOVE its own select while the two rows
            underneath it — plain `<div>`s — drew label-left, value-right as
            the drawing shows. **Measured, not inferred:** `flexDirection`
            computed `column`, the label's box was 350×68 and the span sat at
            x=446 in a 384px column.

            ⚠ **AND IT IS THE TRAP THE SKILL FILE NAMES, ONE VARIANT ALONG:**
            the utilities compile, the class IS in the DOM, `tsc`, eslint,
            `toHaveClass` and `routeBUtilities.test.ts` all pass, and nothing
            in this repo reads a COMPUTED style. Fighting it with `flex-row`
            would lose on specificity; adding a stylesheet class is what rule
            21 forbids. **Not matching the selector is the fix** — and a
            sibling `<label htmlFor>` binds the control exactly as a wrapping
            one did. */}
        <div className="flex items-center justify-between gap-2 py-1 text-body">
          <label
            htmlFor="report-edit-dataset"
            className="text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]"
          >
            {t("reports.edit.field.dataset")}
          </label>
          <select
            id="report-edit-dataset"
            className="max-w-36 truncate bg-transparent text-right font-medium text-text"
            value={draft.dataset}
            onChange={(event) =>
              // ⚠ **CHANGING THE DATASET RESETS COLUMNS AND FILTERS** — p31
              // callout ①, *"because they belong to the dataset"*. Keeping them
              // would carry a name the new dataset does not produce, and the
              // save would then be refused for a column the clerk never typed.
              set({
                dataset: event.target.value,
                columns: [],
                filters: {},
                group_by: [],
                sort: [],
                renames: {},
              })
            }
          >
            {/* ⚠ **AN UNCHOSEN SUBJECT IS A REAL STATE NOW, AND ONLY ON A
                DRAFT THAT HAS ONE** (`DEF-REP-7640`). `/reports/custom/new`
                opens on `draftFrom("")` — subject unchosen, no columns, no
                filters — and a `<select>` whose `value` matches no option
                renders as the FIRST one in most browsers, so without this the
                screen would say *Invoices* over a draft holding nothing and
                the first press of `Save as` would have saved a dataset
                nobody picked.
                It is conditional because every other draft arrives with a
                dataset, and an *unchosen* option a clerk can go back to would
                be a way to break a report that is already working. It
                disappears the moment one is picked. */}
            {draft.dataset === "" ? (
              <option value="">{t("reports.edit.chooseDataset")}</option>
            ) : null}
            {/* ⚠ A dataset CODE — `journal_lines` — is not a word (`DEF-REP-7070`).
                `reports.dataset.<code>` is authored in all eleven catalogues; a
                code with no entry yet survives, because a blank option is a
                silence a clerk cannot report. */}
            {props.datasets.map((one) => (
              <option key={one.code} value={one.code}>
                {t(`reports.dataset.${one.code}`, { defaultValue: one.code })}
              </option>
            ))}
          </select>
        </div>
        {/* ⚠ A FACT, and the dataset's own words (`P2.23`): what ONE ROW is. */}
        <div className="flex items-center justify-between gap-2 py-1 text-body">
          <span className="text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">{t("reports.edit.field.grain")}</span>
          <span className="truncate font-medium text-text">{dataset?.grain ?? "—"}</span>
        </div>
        <div className="flex items-center justify-between gap-2 py-1 text-body">
          <span className="text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">{t("reports.edit.field.calendar")}</span>
          <span className="font-medium text-text">{dataset?.time_hierarchy ?? "—"}</span>
        </div>
      </Panel>

      {/* ② ATTRIBUTES — tick to show · move to reorder · pencil to rename */}
      <Panel>
        <SectionHeading
          label={t("reports.edit.section.attributes")}
          // ⚠ **`7 of 5` — `DEF-REP-7070`, AND BOTH NUMBERS WERE TRUE OF A
          // DIFFERENT THING.** `draft.columns` is EVERY column the report
          // serves — attributes AND measures, and on a MODULE VIEWER a set of
          // names the dataset never declared at all. `attributes.length` is
          // the rows in THIS section. So the statement, whose seven served
          // columns (`entry_date`, `charge`, `running_balance`, …) intersect
          // the `journal_lines` dataset's five attributes in NOTHING but
          // `reference`, headed five checkboxes with *7 of 5*.
          //
          // A count over a list says how many OF THAT LIST are on. So the
          // numerator is the intersection with the rows drawn underneath it,
          // and the two numbers can no longer describe different sets. On the
          // billing register this moves `8 of 12` to `6 of 12`: two of those
          // eight are MEASURES and are counted in the section below.
          count={t("reports.edit.shownOfTotal", {
            shown: ordered.filter((name) => draft.columns.includes(name)).length,
            total: ordered.length,
          })}
        />
        {ordered.map((name, index) => {
          const shown = draft.columns.includes(name);
          // A utility's own word wins; otherwise the catalogue's (`reportWord`).
          const heading = draft.renames[name] ?? reportWord(name, t);
          return (
            <Row key={name}>
              <input
                type="checkbox"
                // ⚠ **NEVER `disabled`.** An unticked column is an empty box, and
                // a disabled box is exactly the grey the PO objected to — it
                // reads as *you cannot* where the truth is *you have not*.
                checked={shown}
                onChange={() => toggle(name)}
                aria-label={heading}
              />
              {renaming === name ? (
                <input
                  className="min-w-0 flex-1 border border-field-border px-1 text-body"
                  autoFocus
                  defaultValue={heading}
                  onBlur={(event) => {
                    const typed = event.target.value.trim();
                    const renames = { ...draft.renames };
                    // Renaming back to the dataset's own word REMOVES the
                    // override rather than storing a copy of it, so a
                    // definition does not accumulate no-op renames.
                    if (typed === "" || typed === name) delete renames[name];
                    else renames[name] = typed;
                    set({ renames });
                    setRenaming(null);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") event.currentTarget.blur();
                    if (event.key === "Escape") setRenaming(null);
                  }}
                />
              ) : (
                <span className="min-w-0 flex-1 truncate text-body text-text">{heading}</span>
              )}
              <button
                type="button"
                className="text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] hover:text-text disabled:opacity-40"
                aria-label={`${t("reports.edit.moveUp")}: ${heading}`}
                disabled={index === 0}
                onClick={() => set(reorderAll(displayOrder, name, -1, draft))}
              >
                <ChevronUpIcon />
              </button>
              <button
                type="button"
                className="text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] hover:text-text disabled:opacity-40"
                aria-label={`${t("reports.edit.moveDown")}: ${heading}`}
                disabled={index === ordered.length - 1}
                onClick={() => set(reorderAll(displayOrder, name, 1, draft))}
              >
                <ChevronDownIcon />
              </button>
              <button
                type="button"
                className="text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] hover:text-text"
                aria-label={`${t("reports.edit.renameColumn")}: ${heading}`}
                onClick={() => setRenaming(name)}
              >
                <PencilIcon />
              </button>
            </Row>
          );
        })}
      </Panel>

      {/* ③ MEASURES — each one carries its own aggregation (p31 callout ③)
          ⚠ **NOT DRAWN AT ALL FOR A MODULE VIEWER** (`DEF-REP-7072`). A report
          that declares its own columns has no dataset measures to offer, and an
          EMPTY *Measures* Panel over a statement is a section that says nothing
          — the shape B14 rule 32's description budget and hard-won law 2's
          mirror both object to. Absent, never empty. */}
      {props.columnChoices !== undefined ? null : (
      <Panel>
        <SectionHeading label={t("reports.edit.section.measures")} />
        {(dataset?.measures ?? []).map((measure) => (
          <Row key={measure.name}>
            <span className="min-w-0 flex-1 truncate text-body text-text">
              {draft.renames[measure.name] ?? reportWord(measure.name, t)}
            </span>
            {/* ⚠ A count is a count and cannot be anything else, so its
                control is DIMMED rather than offering choices that would be
                refused. `aggregation` comes from the dataset — the footer then
                totals what the MEASURE says rather than what a renderer
                assumed.

                ⚠ **TWO CORRECTIONS BY LANE REP-P2-TAIL, 2026-09-27
                (`P2.21`, `DEF-REP-6872`), BOTH MEASURED AGAINST THE DRAWING
                ON p031 RATHER THAN AGAINST THIS COMMENT.**

                (1) **`recompute` IS DIMMED TOO, AND FOR A STRONGER REASON
                THAN `count`.** This branch tested `=== "count"` alone, so the
                `payments` dataset's `dso_days`, `collection_rate`,
                `share_pct` and `days_late` — four of its fourteen measures —
                drew as ordinary, choosable-looking measures. `datasets.py`
                says why they are not: *"the average of four route DSOs is not
                the utility's DSO"*, which is the SECOND of the three wrong
                numbers the brief's own p031 callout names.

                (2) **THE WORD IS THE CATALOGUE'S, NOT THE CODE.** This
                rendered `measure.aggregation` raw, so a clerk read *"sum"* and
                *"recompute"* — a database token on screen, in English, in all
                eleven languages. `reports.agg.<code>` is authored in each
                language (B14 rule 35). */}
            <span
              className={
                measure.aggregation === "count" || measure.aggregation === "recompute"
                  ? "text-xs text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]"
                  : "text-xs font-medium text-text"
              }
            >
              {t(`reports.agg.${measure.aggregation}`, {
                defaultValue: measure.aggregation,
              })}
            </span>
          </Row>
        ))}
      </Panel>
      )}

      {/* ④ FILTERS — every dimension the dataset declares, never hand-written */}
      <Panel>
        <SectionHeading
          label={t("reports.edit.section.filters")}
          count={t("reports.edit.available", { count: filterNames.length })}
        />
        {chosenFilters.map((name) => (
          <Row key={name}>
            {/* ⚠ The filter's own words, never `source_type` (`DEF-REP-7070`).
                A filter is NOT a column, so `reports.col.*` has no entry for
                most of these — `reportWord` falls through to the parameter
                catalogue the slicer bar has used since `P2.7`. */}
            <span className="min-w-0 flex-1 truncate text-body text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
              {reportWord(name, t)}
            </span>
            <input
              // ⚠ **A NAMED HOOK, BECAUSE `input[type="text"]` IS NOT ONE.**
              // The required-record chooser is also a text input inside this
              // stack, so a test counting text inputs counted it too — two
              // cases expecting ZERO filter rows failed on 1 and two expecting
              // ONE passed for the wrong reason. Law 7 clause 2, found by the
              // half that could still fail.
              data-report-filter={name}
              className="w-20 border border-field-border px-1 text-right text-body"
              value={draft.filters[name] ?? ""}
              aria-label={reportWord(name, t)}
              // ⚠ **CLEARING IT NO LONGER REMOVES THE ROW** (`DEF-REP-7080`).
              // An empty value is the drawing's own *All*: on the bar, not
              // narrowing. Deleting the key on an empty string made the row
              // vanish under the clerk mid-edit, which is the same class of
              // fault as the panel closing on a keystroke (`DEF-REP-7073`).
              onChange={(event) => set({ filters: { ...draft.filters, [name]: event.target.value } })}
              placeholder={t("reports.edit.all")}
            />
            <button
              type="button"
              className="text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] hover:text-text"
              aria-label={`${t("reports.edit.removeFilter")}: ${reportWord(name, t)}`}
              onClick={() => {
                const filters = { ...draft.filters };
                delete filters[name];
                set({ filters });
              }}
            >
              <TrashIcon />
            </button>
          </Row>
        ))}
        {/* ⚠ **`+ Add filter` IS A NATIVE SELECT AND NOT A MENU** — the kit's
            own control for picking one value from a served list, and the same
            one sections ① ⑤ ⑦ use three inches above it. It is absent, never
            drawn dead, when every declared filter is already on the bar: a
            control that can do nothing is hard-won law 2's mirror. */}
        {offerableFilters.length === 0 ? null : (
          <Row>
            <select
              className="min-w-0 flex-1 bg-transparent text-body text-text"
              value=""
              aria-label={t("reports.edit.addFilter")}
              onChange={(event) => {
                if (event.target.value === "") return;
                set({ filters: { ...draft.filters, [event.target.value]: "" } });
              }}
            >
              <option value="">{`+ ${t("reports.edit.addFilter")}`}</option>
              {offerableFilters.map((name) => (
                <option key={name} value={name}>
                  {reportWord(name, t)}
                </option>
              ))}
            </select>
          </Row>
        )}
        <div className="flex items-center justify-between gap-2 px-2 pt-2 text-xs text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
          <span>{t("reports.edit.showOnBar")}</span>
          <span>
            {t("reports.edit.shownOfTotal", { shown: onTheBar, total: filterNames.length })}
          </span>
        </div>
      </Panel>

      {/* ⑤ GROUP & SORT — three levels at most (`P2.17`) */}
      <Panel>
        <SectionHeading label={t("reports.edit.section.groupSort")} />
        {[0, 1, 2].map((level) => (
          <Row key={level}>
            <span className="min-w-0 flex-1 text-body text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
              {t("reports.edit.level", { n: level + 1 })}
            </span>
            <select
              className="max-w-28 truncate bg-transparent text-right font-medium text-text"
              value={draft.group_by[level] ?? ""}
              aria-label={t("reports.edit.level", { n: level + 1 })}
              onChange={(event) => {
                const next = [...draft.group_by];
                if (event.target.value === "") next.splice(level);
                else next[level] = event.target.value;
                set({ group_by: next.filter((one) => one !== "") });
              }}
            >
              <option value="">{t("reports.edit.none")}</option>
              {(dataset?.dimensions ?? []).map((dimension) => (
                <option key={dimension.name} value={dimension.name}>
                  {reportWord(dimension.name, t)}
                </option>
              ))}
            </select>
          </Row>
        ))}
      </Panel>

      {/* ⑦ WHERE IT LIVES — group, sub-group, services and visibility */}
      <Panel>
        <SectionHeading label={t("reports.edit.section.whereItLives")} />
        <Row>
          <span className="min-w-0 flex-1 text-body text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
            {t("reports.saveAs.group")}
          </span>
          <select
            className="max-w-28 truncate bg-transparent text-right font-medium text-text"
            value={draft.group}
            aria-label={t("reports.saveAs.group")}
            onChange={(event) => set({ group: event.target.value, sub_group: null })}
          >
            <option value="">{t("reports.edit.none")}</option>
            {props.groups.map((group) => (
              <option key={group.code} value={group.code}>
                {group.name}
              </option>
            ))}
          </select>
        </Row>
        <Row>
          <span className="min-w-0 flex-1 text-body text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
            {t("reports.saveAs.subGroup")}
          </span>
          <select
            className="max-w-28 truncate bg-transparent text-right font-medium text-text"
            value={draft.sub_group ?? ""}
            aria-label={t("reports.saveAs.subGroup")}
            onChange={(event) => set({ sub_group: event.target.value || null })}
          >
            <option value="">{t("reports.edit.none")}</option>
            {(props.groups.find((one) => one.code === draft.group)?.sub_groups ?? []).map(
              (sub) => (
                <option key={sub.code} value={sub.code}>
                  {sub.name}
                </option>
              ),
            )}
          </select>
        </Row>
        <Row>
          <span className="min-w-0 flex-1 text-body text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
            {t("reports.saveAs.visibleTo")}
          </span>
          <select
            className="bg-transparent text-right font-medium text-text"
            value={draft.visibility}
            aria-label={t("reports.saveAs.visibleTo")}
            onChange={(event) =>
              set({ visibility: event.target.value as ReportVisibility })
            }
          >
            <option value="private">{t("reports.saveAs.visibility.private")}</option>
            <option value="shared">{t("reports.saveAs.visibility.shared")}</option>
          </select>
        </Row>
      </Panel>

      {/* ⚠ **THE FOOTER'S ORDER IS OURS, NOT THE DRAWING'S** — B14 rule 38,
          which rule 44 now generalises: where a drawing and our UI rules
          disagree about how a form is BUILT, the UI rules win. Cancel is the
          ghost, the commit is filled, and the commit is last.

          ⚠ **AND ON THE PAGE THERE IS NO FOOTER AT ALL.** `PageHeader` owns a
          screen's actions in this product, and a page carrying both a header
          action row and a footer button row offers `Save as` twice — two doors
          onto one act, which is what p30 callout ① warns against by name. The
          drawing puts `Cancel` and `Save as` at the TOP RIGHT above the title,
          and that is where `PageHeader` puts them. */}
      {variant === "page" ? null : (
      <div className="flex items-center justify-end gap-2">
        <Button variant="ghost" onClick={props.onCancel}>
          {t("reports.edit.cancel")}
        </Button>
        {props.onSave === undefined ? null : (
          <Button variant="secondary" onClick={props.onSave} disabled={props.saving}>
            {t("reports.edit.save")}
          </Button>
        )}
        <Button variant="primary" onClick={props.onSaveAs} disabled={props.saving}>
          {t("reports.edit.saveAs")}
        </Button>
      </div>
      )}
    </Wrapper>
  );
}

/** A reorder applied to BOTH the visible order and the chosen set.
 *
 *  ⚠ **MOVING AN UNTICKED COLUMN STILL MOVES IT**, because a clerk who ticks it
 *  next expects it where they left it. The chosen list is then rebuilt in the
 *  new visible order rather than appended to, so the table's column order and
 *  the panel's row order cannot drift apart. */
function reorderAll(
  order: string[],
  name: string,
  delta: -1 | 1,
  draft: ReportDraftState,
): Partial<ReportDraftState> {
  const next = moved(order, name, delta);
  // ⚠ `order` is the panel's FULL display list — attributes and measures —
  // for the reason `displayOrder` gives. Passing the attribute list alone here
  // dropped every measure from the definition on a single arrow click.
  const chosen = new Set(draft.columns);
  return {
    columns: [
      ...next.filter((one) => chosen.has(one)),
      ...draft.columns.filter((one) => !next.includes(one)),
    ],
  };
}

export default ReportEditPanel;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 Phase 5 `P5.3`/`P5.11` (05-prototype/09 Reports Build Brief.pdf p16-p17 the task table, p31-p33 screen 2·2, read as IMAGES per B14 rule 42) · PO ruling 2026-09-26 "panel, not wizard" (12-governance/02-decision-log.md)
// screens: 2·2 (A1 S47)
// generated: 2026-09-27 by lane REP-P5; amended 2026-09-28 by lane REP-BUILD-YOUR-OWN (`DEF-REP-7640` — the dataset chooser offers an UNCHOSEN option, and only on a draft that has one, so `/reports/custom/new` can open on a real empty definition instead of showing the first dataset over a draft holding nothing); amended 2026-09-28 by lane REP-STMT-SCREEN (`DEF-REP-7072` — `columnChoices`: where a report declares its OWN columns the panel offers those and not its dataset's, and draws no Measures section, because a viewer's columns ARE its columns)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — see reportEditPanel.dom.test.tsx's own gates line. G31: this file is listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) B14 rule 9's multi-select is NOT used for the attribute list — rule 9's subject is a field picking values from a flat set, and this is an ORDERED list whose rows carry move and rename, which `P5.11` requires by name and a multi-select cannot express. The kit is still what it is BUILT from (rule 44) · (2) reordering is TWO BUTTONS rather than a drag — the drawing shows a drag handle, and a keyboard-reachable pair of buttons is what our standard gives for the same act; a drag with no keyboard path is a control half the readers cannot use · (3) the renames ride in `filters` under one reserved key the runner already passes through, rather than in a new column: a migration for a label is a migration nobody should pay for
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
