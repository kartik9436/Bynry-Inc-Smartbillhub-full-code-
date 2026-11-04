// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-007 (EP-SHL-02 §Stories)  Screens: every filtered list screen (S9.plans/.rates/.charges/.discounts/.taxes, S15, S17, S30, S33, S34, …)
// Change:   CS-40 (CR-059 §0d.2) — *"sets 1–31 August and the list, its count and its total all narrow, and the range survives a refresh"*
// Defect:   DEF-442 — r10 draws ONE `+ Filter ▾` panel plus REMOVABLE CHIPS; we drew a labelled <select> per dimension · DEF-3504 — the bar could render option lists and nothing else, so no list in the product could offer a date range
// Rules:    BR-SHL-010 (only DECLARED capabilities render) · BR-SHL-011 (`f.<name>` URL grammar via the shared request state) · IS-4 (declared, AND-combined, chips + clear-all, URL-persisted) · B14 rule 21 (Tailwind utilities, no stylesheet rule added) · BR-SHL-023 / BR-SHL-034 (dates through the ONE formatter) · BR-SHL-033 (native date picker, manual entry too) · IS-8 (tenant regional format)
// ───────────────────────────────────────────────────────
// FE-03 FilterBar (B13 §1): the declared filter controls + the IS-4 active-filter
// chips, feeding DataTable's request state. Filters are DECLARED per screen in
// the capability-matrix config (TableConfig.filters) and AND-combined ON THE
// SERVER — this component only edits `state.filters`; the consumer serializes it
// to `f.<name>` params (BR-SHL-011, tableTypes helpers) and its A11 list request.
// It also feeds report params later (B13 FE-03).
//
// ⚠ THE DRAWING CHANGED ON 2026-08-21 AND THE SEMANTICS DID NOT (DEF-442).
// ─────────────────────────────────────────────────────────────────────────
// Product Owner, comparing our screens to r10: *"also look at Filter in Proto -
// it is panel and when you select somethibg it shows selection on screen ; look
// at filters you build"*. What we drew was one labelled `<select>` per dimension,
// permanently occupying the toolbar, with the applied state visible only INSIDE
// each closed select — so a table showing 1 of 7 rows could not say WHY, and a
// user could not remove one filter without first finding the right select.
//
// r10 draws (`SMARTBillHub.dc.html` line 763 for the toolbar, `table-tools.js`
// lines 119-177 for the runtime it drives — read for the SHAPE and the COPY, not
// ported, per the CLAUDE.md reference rule):
//
//   [All] [Svc: Water ×] [Status: Active ×]  [+ Filter ▾]  [columns icon]
//                                                 └─ opens ─┐
//                                          ┌───────────────────────────┐
//                                          │ FILTER BY                 │
//                                          │  Svc                      │
//                                          │   ☐ Electric  ☑ Water     │
//                                          │  Structure                │
//                                          │   ☐ Flat  ☐ Tiered …      │
//                                          └───────────────────────────┘
//
// EVERY IS-4 BEHAVIOUR IS UNCHANGED — same declared dimensions, same AND
// combination on the server, same `f.<name>` URL round-trip, same pure
// transitions below, same tests over them. Only the control shape moved.
//
// ⚠ SUPERSEDED FOR THE SERVICE DIMENSION 2026-10-02 — OQ-306 CLOSED (PO:
// *"Allow several services at once."*). `isMultiSelectFilter` (tableTypes)
// names the dimensions that multi-select and OR; every other dimension keeps
// the single-select behaviour described below, which was its history.
// ⚠ THE CHECKBOXES ARE SINGLE-SELECT, AND THAT IS A DELIBERATE DIVERGENCE
// (OQ-306). r10's panel keeps an ARRAY per column (`st.filters[oi].push(v)`), so
// its checkboxes really do multi-select and OR within a dimension. Ours cannot:
// `TableRequestState.filters` is `Record<string, string>` and BR-SHL-011's URL
// grammar is one `f.<name>=<value>` per dimension, both signed, and the SERVER
// applies them — widening that is an API change, not a drawing change. So a box
// here REPLACES its group's value instead of adding to it, and unticking the
// ticked box clears the dimension. The drawing is r10's because that is what the
// PO is looking at; the ambiguity is filed as OQ-306 rather than resolved by
// choosing a value (prime directive), and the chip row is what keeps the
// single-select honest — the user SEES the group's one value the instant it
// changes, which is the whole reason DEF-442 called the chips load-bearing.
//
// ⚠ AND IT GREW A SECOND KIND OF CONTROL ON 2026-09-03 (CS-40 · DEF-3504).
// ─────────────────────────────────────────────────────────────────────────
// Product Owner, walking all four Record payments tabs on the deployed build:
// *"I cannot filter payment by date"*. The server had accepted `posted_from`,
// `posted_to`, `cleared_from` and `cleared_to` all along and `endpoints.ts` had
// declared all four; THIS component was the gap, because a `TableFilterConfig`
// could only ever be an option list. So the payments screen declared the four
// option lists it could draw and told the clerk, in plain English on the tab,
// that the date ranges were not offered.
//
// A range declares `dateRange` on its config (tableTypes) and renders as TWO
// native date inputs inside the same `+ Filter ▾` panel, under the same
// `<legend>`, above one chip that reads the applied range in the TENANT's date
// format. Everything else is unchanged: same panel, same chip row, same
// clear-all, same `f.<name>` round trip — a range simply owns TWO of those
// params instead of one, which is what the server already accepts.
//
// ⚠ NOTHING RENDERS FOR A LIST THAT DOES NOT DECLARE ONE. BR-SHL-010 again:
// every list in the product shares this bar, so the option-list path is
// asserted BYTE-FOR-BYTE against two committed fixtures captured from the
// component at the commit before this landed. Structural assertions ("still two
// fieldsets") pass on markup that gained a wrapper or an attribute; bytes do
// not.
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { formatDate } from "./DateCell";
import { contentBoundsLeft, panelAlignClass, resolvePanelAnchor, type PanelAnchor } from "./popoverAnchor";
import {
  MULTI_VALUE_SEPARATOR,
  filterParamNames,
  filterValueList,
  isMultiSelectFilter,
} from "./tableTypes";
import type {
  TableFilterConfig,
  TableFilterDateRange,
  TableFilterPeriod,
  TableRequestState,
} from "./tableTypes";
import { PeriodPicker, periodChoiceLabel } from "./PeriodPicker";
import type { PeriodValue } from "./periodWindow";

import { buttonClasses } from "@/components/buttonKit";
import { Chip, ChipRow, ChipToggle } from "@/components/Chip";

// ── Request-state transitions (pure, testable without a browser) ───────────
// Filter changes return to page 1 — the result set changed (same derived law
// as DataTable's search/sort transitions).

export function setFilter(
  state: TableRequestState,
  name: string,
  value: string,
): TableRequestState {
  const filters = { ...state.filters };
  if (value === "") {
    delete filters[name]; // "All" / chip ✕ / unticking the box — the filter is simply absent
  } else {
    filters[name] = value;
  }
  return { ...state, filters, page: 1 };
}

export function clearAllFilters(state: TableRequestState): TableRequestState {
  return { ...state, filters: {}, page: 1 };
}

/**
 * ⚠ EXPORTED SO THE CHECKBOX'S BEHAVIOUR IS TESTABLE WITHOUT A DOM.
 *
 * **Single-select** (every dimension except those `isMultiSelectFilter`
 * names): ticking a box sets its group to that value; ticking the box that is
 * already set clears the group.
 *
 * **Multi-select** (`OQ-306` CLOSED, PO 2026-10-02: *"Allow several services at
 * once."*): ticking a box ADDS its value to the group and ticking it again
 * REMOVES it — r10's `st.filters[oi].push(v)`. The group's value is the picked
 * values joined by a comma, in the order they were ticked; removing the last
 * one clears the group, so an empty multi-select is the same absent filter as
 * an empty single-select.
 */
export function toggleFilterOption(
  state: TableRequestState,
  name: string,
  value: string,
): TableRequestState {
  if (!isMultiSelectFilter(name)) {
    return setFilter(state, name, state.filters[name] === value ? "" : value);
  }
  const picked = filterValueList(name, state.filters[name]);
  const next = picked.includes(value)
    ? picked.filter((one) => one !== value)
    : [...picked, value];
  return setFilter(state, name, next.join(MULTI_VALUE_SEPARATOR));
}

/** Is this option ticked? A multi-select group holds several (OQ-306). */
export function filterOptionChecked(
  state: TableRequestState,
  name: string,
  value: string,
): boolean {
  return filterValueList(name, state.filters[name]).includes(value);
}

/**
 * The declared groups a panel can honestly OFFER (BR-SHL-010, `DEF-1701`).
 *
 * Two shapes are dropped, and each is a rule rather than a preference:
 *
 *  · **A group with no options is a legend over nothing.** `DEF-782` drew
 *    exactly that on the units list — the heading "Service" with an empty body
 *    — and the assets registry carried the same `options: []` for weeks
 *    unnoticed, because that screen rendered no panel at all for it to show up
 *    in. What cannot be offered is not rendered.
 *  · **An empty-VALUE option is a leftover from the `<select>` era.** A
 *    `{ value: "", label: "All entities" }` cell was how a dropdown said
 *    "no filter"; in this panel the `All` chip IS that control, and a checkbox
 *    whose value is `""` can never read as checked (`state.filters[name]` is
 *    absent, not empty), so it would render permanently untickable.
 *
 * Pure, so both halves are provable without a browser.
 */
export function offerableFilters(
  declared: readonly TableFilterConfig[],
): TableFilterConfig[] {
  return declared
    .map((filter) =>
      filter.dateRange !== undefined || filter.period !== undefined
        ? filter
        : { ...filter, options: filter.options.filter((option) => option.value !== "") },
    )
    .filter(
      (filter) =>
        filter.dateRange !== undefined || filter.period !== undefined || filter.options.length > 0,
    );
}

/**
 * IS THIS DECLARED FILTER APPLIED? — one question, two shapes of answer.
 *
 * For an option list this is exactly what the bar asked before CS-40:
 * `state.filters[name] !== undefined`. For a date range it is EITHER end, which
 * is what makes a HALF-ENTERED range a first-class state rather than one
 * discovered on a screen: *from 1 August, no end* is a real thing a clerk means
 * and the chip below says so out loud.
 */
export function filterIsActive(
  filter: TableFilterConfig,
  state: TableRequestState,
): boolean {
  return filterParamNames(filter).some((param) => state.filters[param] !== undefined);
}

/**
 * The chip's ✕ on a date range clears BOTH ends, because the chip is ONE thing
 * to the clerk who is looking at it. Removing only the end you happened to
 * click would leave the list still filtered with no chip left saying so, which
 * is the DEF-442 complaint — a table showing 1 of 7 rows that cannot say why.
 */
export function clearDateRange(
  state: TableRequestState,
  range: TableFilterDateRange,
): TableRequestState {
  return setFilter(setFilter(state, range.from, ""), range.to, "");
}

/**
 * WHAT THE CHIP SAYS FOR A DATE RANGE — or `null` when it must not exist.
 *
 * ⚠ **`null` IS THE LOAD-BEARING RETURN AND IT IS WHY THIS IS A FUNCTION.**
 * DEF-3504 is, underneath, a complaint about a control that LOOKS as though it
 * narrowed something and did not. An untouched date range must therefore be
 * indistinguishable from a filter nobody declared: no chip, no `f.` param, no
 * clear-all, and the All chip still inverted. That is a property a test can
 * assert on a value, and it is asserted, rather than being left to be read off
 * rendered markup that no gate in this repo looks at (hard-won law 6).
 *
 * The three live shapes get three different sentences, not one sentence with a
 * blank in it: `1 Aug to 31 Aug`, `1 Aug onwards`, `Up to 31 Aug`. A chip
 * reading `01/08/2026 to ` is precisely the half-entered state rendered as
 * though it were broken.
 *
 * ⚠ IT RETURNS A `bound` AND NOT A CATALOGUE KEY, ON PURPOSE. G27 reads
 * LITERAL `t("…")` call sites; a key computed here and handed to `t()` at the
 * call site is invisible to it, and a typo in one would then reach a clerk as
 * the raw key — which is the exact defect G15 was written for. So the three
 * keys are spelled at the three `t()` calls in the chip below, where a gate can
 * see them, and this function decides only WHICH of the three is true.
 *
 * Dates render through `formatDate` — the ONE formatting path (BR-SHL-023 /
 * BR-SHL-034) — in the tenant's regional format, never `toLocaleDateString`.
 * The zone argument is `"UTC"` and is inert: `formatDate` short-circuits a
 * `YYYY-MM-DD` before any zone is consulted, because a calendar date is the
 * same calendar date in every tenant. Passing a zone we do not have here would
 * suggest it mattered.
 *
 * ⚠ AND THIS IS WHERE IS-8 IS HONOURED FOR A RANGE. The native
 * `<input type="date">` in the panel renders in the BROWSER's locale and
 * ignores the tenant setting completely, so the chip is the only place a tenant
 * whose format differs ever sees theirs — the same reason `DatePickerField`
 * carries its grey echo line, resolved here by the chip that was already going
 * to be on screen instead of by a second line under each of two inputs.
 */
export type DateRangeChip =
  | { bound: "both"; from: string; to: string }
  | { bound: "from"; from: string }
  | { bound: "to"; to: string };

export function dateRangeChipCopy(
  range: TableFilterDateRange,
  state: TableRequestState,
): DateRangeChip | null {
  const from = state.filters[range.from];
  const to = state.filters[range.to];
  const shown = (value: string) => formatDate(value, "UTC", range.dateFormat);
  if (from !== undefined && to !== undefined) {
    return { bound: "both", from: shown(from), to: shown(to) };
  }
  if (from !== undefined) {
    return { bound: "from", from: shown(from) };
  }
  if (to !== undefined) {
    return { bound: "to", to: shown(to) };
  }
  return null; // nothing entered — narrows nothing, and says nothing
}

// ⚠ r10's `.fchip` MOVED OUT OF THIS FILE ON 2026-09-04 (B14 rule 36 ·
// `DEF-3722`). It was a private constant here, so the Integrations grid — the
// next screen that needed a chip — could not reach it and wrote its own with a
// different radius, a different pair of colours and uppercase type. A visual
// decision only one file can read is a visual decision the next file makes
// again. It is `components/Chip.tsx` now; this bar renders it, and so does the
// grid, so there is genuinely one chip.

// r10 draws the panel's open-control as `btn btn-secondary btn-sm`. It is
// `buttonClasses()` and not `<Button>` because the open-control of a `<details>`
// has to BE the `<summary>` or the disclosure behaviour is lost — the one case
// buttonKit.ts sanctions the raw string for.
// ⚠ THE VARIANT AND SIZE ARE HOISTED OUT OF THE JSX ON PURPOSE.
// `routeBUtilities.test.ts` harvests every quoted literal inside a class
// attribute expression and asks Tailwind whether it compiles, so calling the
// kit helper with its two literal arguments inside that attribute reports both
// argument words as classes that render nothing — which they do, because they
// are not classes. Measured: that is exactly what it said before this hoist.
// The EXTRA utilities stay inside the template literal at the call site, so
// they are still read and still checked.
// ⚠ AND THE EXAMPLE IS DESCRIBED, NOT WRITTEN. Spelling that attribute out in
// a comment feeds the harvester from the comment itself — this file's first
// draft did exactly that and went red on the two argument words with the JSX
// already clean. buttonKit.ts records the same trap costing three commits.
/**
 * `DEF-LED-10071` J3 — apply a chosen period: the choice and both ends it
 * resolves to, together, back to page 1. The picker only ever hands over a
 * window that may be applied, so nothing half-typed reaches the URL.
 */
export function setPeriod(
  state: TableRequestState,
  period: TableFilterPeriod,
  next: PeriodValue,
): TableRequestState {
  const filters = {
    ...state.filters,
    [period.choice]: next.choice,
    [period.from]: next.from,
    [period.to]: next.to,
  };
  return { ...state, filters, page: 1 };
}

/** The period chip's ✕ — all three params go, because the chip is ONE thing (J4: no period). */
export function clearPeriod(state: TableRequestState, period: TableFilterPeriod): TableRequestState {
  const filters = { ...state.filters };
  delete filters[period.choice];
  delete filters[period.from];
  delete filters[period.to];
  return { ...state, filters, page: 1 };
}

/** What the picker is showing for a declared period, or `null` for none. */
export function periodValueOf(
  period: TableFilterPeriod,
  state: TableRequestState,
): PeriodValue | null {
  const choice = period.choices.find((one) => one === state.filters[period.choice]);
  const from = state.filters[period.from];
  const to = state.filters[period.to];
  if (choice === undefined || from === undefined || to === undefined) return null;
  return { choice, from, to };
}

const PANEL_TRIGGER_KIT = buttonClasses("secondary", "sm");

/**
 * The two date inputs of ONE declared range, inside the panel's own
 * `<fieldset>`/`<legend>` — so a screen reader announces "Posted, From" and
 * "Posted, To" exactly the way it announces "Svc, Water" for a checkbox.
 *
 * ⚠ **`input` IS A STYLESHEET CLASS AND THAT IS THE RIGHT ANSWER HERE, NOT AN
 * EXCEPTION TO B14 RULE 21.** Rule 21 says a new piece of UI adds NO class to a
 * stylesheet; `.input` is already declared (`FormModal.css`, and its
 * `[type="date"]` height rule with it), so reusing it adds nothing and makes
 * these two boxes the same 36px control as every other input in the product.
 * Building the same box out of utilities would be a second opinion about what
 * an input looks like — which is what rule 21 exists to prevent, not to cause.
 *
 * ⚠ **`min`/`max` CROSS-BIND THE TWO ENDS, AND THAT IS A HELP AND NOT A
 * GUARANTEE** (hard-won law 1 — a comment claiming a guarantee is not the
 * guarantee). A native picker greys out the days that would invert the range,
 * which is where a backwards range is actually entered. It does NOT prevent one
 * typed in, or one pasted into the URL. A backwards range is therefore still
 * reachable and is passed to the server exactly as entered: the list narrows to
 * the zero days between the two, the count and the total say zero, and the chip
 * says which range did it. That is the honest outcome, and it is the one
 * DEF-3504 asks for — a control whose result matches what it claims — rather
 * than a refusal that would leave the clerk with a value on screen that is not
 * being applied.
 */
function DateRangeGroup(props: {
  name: string;
  range: TableFilterDateRange;
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
}) {
  const { t } = useTranslation();
  const { name, range, state, onStateChange } = props;
  const from = state.filters[range.from] ?? "";
  const to = state.filters[range.to] ?? "";
  const ends: { param: string; value: string; caption: string; min?: string; max?: string }[] = [
    {
      param: range.from,
      value: from,
      caption: t("table.filters.dateFrom"),
      max: to === "" ? undefined : to,
    },
    {
      param: range.to,
      value: to,
      caption: t("table.filters.dateTo"),
      min: from === "" ? undefined : from,
    },
  ];
  return (
    <div className="flex flex-col gap-1">
      {ends.map((end) => (
        <label key={`${name}.${end.param}`} className="flex flex-col gap-1 text-btn-sm">
          <span className="opacity-75">{end.caption}</span>
          <input
            // BR-SHL-033: the native picker, and the same box accepts typing.
            type="date"
            className="input"
            value={end.value}
            min={end.min}
            max={end.max}
            onChange={(e) => onStateChange(setFilter(state, end.param, e.target.value))}
          />
        </label>
      ))}
    </div>
  );
}

/** The panel's fixed `w-[20rem]` in px — the number `resolvePanelAnchor` is
 *  given (DEF-SHL-10643). The panel itself is display:none when the toggle
 *  fires, so its own rect would read zero. */
const FILTER_PANEL_WIDTH_PX = 320;

export function FilterBar(props: {
  filters: TableFilterConfig[]; // the screen's declared set (BR-SHL-010: only these render)
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  /**
   * **THE `All` CHIP IS THE SCREEN'S, NOT THIS BAR'S — OPT-IN, ADDED 2026-10-01
   * (`CR-156-BRC10`, the charge-code list, images 01–04).** That list draws its
   * own `All · 30 · Base · 5 · Plan · 12 · Other · 13` chips in front of
   * `+ Filter ▾`, and a second `All` from this bar beside them reads as the same
   * control twice. `false` drops this bar's chip and nothing else; every applied
   * filter keeps its own ✕. Absent keeps every existing list exactly as it
   * renders today (B14 rule 36).
   */
  allChip?: boolean;
}) {
  const { t } = useTranslation();
  const { state, onStateChange } = props;
  // DEF-SHL-10643 — which side the panel hangs from, measured when it opens.
  const [anchor, setAnchor] = useState<PanelAnchor>({ align: "right", shiftPx: 0 });
  // CR-157-BRC10 wave B's `quickFilter` (one dimension drawn as toggle chips in
  // the row) was removed with its only caller, the rate-schedule list's service
  // chips (DEF-RAT-9103, PO 2026-10-02 — service belongs inside `+ Filter`).
  const declared = props.filters;
  const active = declared.filter((f) => filterIsActive(f, state));
  const none = active.length === 0;

  // BR-SHL-010: a screen that declares no filters gets no filter UI at all —
  // not an "All" chip over nothing and not a panel that would open on r10's own
  // "No filterable columns on this table." Rendering the toolbar furniture for
  // an absent capability is exactly what that rule forbids.
  if (props.filters.length === 0) {
    return null;
  }

  return (
    // r10 `.fbar` — flex, 8px gap, wraps. The gap is `ChipRow`'s now, decided
    // once for every chip row in the product (B14 rule 36).
    <ChipRow>
      {/* r10's `All` chip: INVERTED while nothing is applied (`.fchip.active`
          paints ink-on-paper), and the clear-all control the moment something
          is. IS-4 wants a clear-all only when there is something to clear, so
          the "Clear all" name appears only then — sighted users read the chip's
          state, screen readers get the action. */}
      {props.allChip !== false && (
        <ChipToggle
          selected={none}
          aria-label={none ? undefined : t("table.filters.clearAll")}
          title={none ? undefined : t("table.filters.clearAll")}
          onClick={() => onStateChange(clearAllFilters(state))}
        >
          {t("table.filters.all")}
        </ChipToggle>
      )}

      {/* IS-4 · DEF-442's load-bearing half: every applied filter is a chip,
          ON SCREEN, sitting between the All chip and the + Filter button exactly
          as r10 inserts it (`bar.insertBefore(chip, …tt-filter-btn)`). The ✕ is
          a real button with its own accessible name — r10 makes the whole chip
          clickable with a bare `×` glyph, which names nothing to a screen
          reader, so the ✕ is a labelled control here and the chip is not. */}
      {active.map((filter) => {
        // The chip's VALUE half and what its ✕ does are the only two things a
        // range does differently. Both are computed here so the chip itself —
        // its markup, its accessible name, its position in the row — is one
        // piece of code for both kinds and cannot drift into two.
        const range = filter.dateRange;
        let chipValue: string;
        let remove: () => void;
        const period = filter.period;
        if (period !== undefined) {
          // `DEF-LED-10071` J3 — *Period: Last 30 days*, or the two dates of a
          // Custom window in the utility's own format (P9).
          const value = periodValueOf(period, state);
          chipValue =
            value === null
              ? ""
              : value.choice === "custom"
                ? t("table.filters.dateRange", {
                    from: formatDate(value.from, "UTC", period.dateFormat),
                    to: formatDate(value.to, "UTC", period.dateFormat),
                  })
                : periodChoiceLabel(value.choice, t);
          remove = () => onStateChange(clearPeriod(state, period));
        } else if (range !== undefined) {
          const copy = dateRangeChipCopy(range, state);
          // `active` already established that one end is set, so `copy` cannot
          // be null here; the empty fallback keeps the type honest rather than
          // asserting non-null, and would render the label alone.
          chipValue =
            copy === null
              ? ""
              : copy.bound === "both"
                ? t("table.filters.dateRange", { from: copy.from, to: copy.to })
                : copy.bound === "from"
                  ? t("table.filters.dateRangeFrom", { from: copy.from })
                  : t("table.filters.dateRangeTo", { to: copy.to });
          remove = () => onStateChange(clearDateRange(state, range));
        } else {
          // OQ-306 — a multi-select group names EVERY picked value on its one
          // chip (`Service: Water, Sewer`); its ✕ clears the group, because the
          // chip is one thing to the clerk looking at it (the date range's
          // reasoning). A single-select group is a list of one.
          chipValue = filterValueList(filter.name, state.filters[filter.name])
            .map((value) => filter.options.find((o) => o.value === value)?.label ?? value)
            .join(", ");
          remove = () => onStateChange(setFilter(state, filter.name, ""));
        }
        return (
          <Chip
            key={filter.name}
            onRemove={remove}
            removeLabel={t("table.filters.remove", { label: filter.label })}
          >
            {t("table.filters.chip", { label: filter.label, value: chipValue })}
          </Chip>
        );
      })}

      {/* The panel. `<details>`/`<summary>` for the same reason DataTable's
          column chooser uses it: the disclosure is keyboard-operable and
          focus-manageable with no script, and one product should open its two
          toolbar panels the same way. */}
      {declared.length > 0 && (
      <details
        className="relative"
        // ⚠ DEF-SHL-10643 — `right-0` was unconditional, so on a toolbar with no
        //    search box (`+ Filter` first, 73px from the content column) the
        //    320px panel opened BEHIND THE SIDEBAR and its boxes could not be
        //    clicked. Measured from the SUMMARY on open, against the content
        //    column's left edge — the column picker's DEF-1085 arithmetic.
        onToggle={(event) => {
          if (!event.currentTarget.open) {
            return;
          }
          const summary = event.currentTarget.querySelector("summary");
          if (summary === null) {
            return;
          }
          const rect = summary.getBoundingClientRect();
          setAnchor(
            resolvePanelAnchor({
              anchorLeft: rect.left,
              anchorRight: rect.right,
              panelWidth: FILTER_PANEL_WIDTH_PX,
              viewportWidth: document.documentElement.clientWidth,
              boundsLeft: contentBoundsLeft(summary),
            }),
          );
        }}
      >
        <summary
          // r10: `btn btn-secondary btn-sm`, title "Filter by: Service,
          // Structure, Status" — the dimensions are named BEFORE the panel is
          // opened, which is the only thing the closed button can tell you.
          title={t("table.filters.titleList", {
            dimensions: declared.map((f) => f.label).join(", "),
          })}
          className={`${PANEL_TRIGGER_KIT} cursor-pointer list-none [&::-webkit-details-marker]:hidden`}
        >
          {t("table.filters.open")} <span aria-hidden="true">▾</span>
        </summary>
        {/* Width, border, shadow and placement match the column chooser beside
            it (DEF-440) so the two panels are one control family; 20rem is
            r10's own 320px. Fixed rather than min-width: a panel that reflows
            while the pointer is inside it moves the row being clicked. */}
        <div
          className={`absolute ${panelAlignClass(anchor.align)} top-[calc(100%+var(--space-1))] z-40 flex max-h-[70vh] w-[20rem] flex-col gap-2 overflow-auto border border-divider bg-surface p-3 shadow-md`}
          style={anchor.shiftPx === 0 ? undefined : { transform: `translateX(${String(anchor.shiftPx)}px)` }}
        >
          {/* r10 heads the panel `FILTER BY`. The copy is sentence case in the
              catalogue and uppercased here — same split as `table.columns.title`,
              so a translator is never asked to shout.
              ⚠ r10 sets 10px on this heading and our named type scale has no
              10px tier (B14 rules 5 and 20); `text-[10px]` is what G34 refuses.
              12px, as DEF-440 already settled for the column panel's heading. */}
          <p className="m-0 whitespace-nowrap font-heading text-btn-sm font-semibold uppercase tracking-wider text-neutral-600">
            {t("table.filters.title")}
          </p>
          {declared.map((filter) => (
            // fieldset/legend, not a styled <div>: a checkbox that says
            // "Water" is meaningless read out on its own, and the legend is
            // what makes a screen reader announce "Svc, Water".
            <fieldset key={filter.name} className="m-0 border-0 p-0">
              <legend className="mb-1 p-0 font-semibold opacity-75">{filter.label}</legend>
              {filter.period !== undefined && (
                <PeriodPicker
                  id={`f.${filter.name}`}
                  label={t("forms.period.quick")}
                  value={periodValueOf(filter.period, state)}
                  choices={filter.period.choices}
                  today={filter.period.today}
                  month={filter.period.month}
                  dateFormat={filter.period.dateFormat}
                  layout="stack"
                  onChange={(next) => {
                    if (filter.period !== undefined) {
                      onStateChange(setPeriod(state, filter.period, next));
                    }
                  }}
                />
              )}
              {filter.dateRange !== undefined && (
                <DateRangeGroup
                  name={filter.name}
                  range={filter.dateRange}
                  state={state}
                  onStateChange={onStateChange}
                />
              )}
              {filter.options.map((option) => {
                const checked = filterOptionChecked(state, filter.name, option.value);
                const level = filter.levels?.[option.value];
                return (
                  <label
                    key={option.value}
                    className={
                      level === 2
                        ? "flex cursor-pointer items-center gap-2 py-0.5 pl-5 text-btn-sm"
                        : level === 1
                          ? "flex cursor-pointer items-center gap-2 py-0.5 text-btn-sm font-semibold"
                          : "flex cursor-pointer items-center gap-2 py-0.5 text-btn-sm"
                    }
                    data-filter-level={level}
                  >
                    <input
                      type="checkbox"
                      className="shrink-0"
                      checked={checked}
                      onChange={() =>
                        onStateChange(toggleFilterOption(state, filter.name, option.value))
                      }
                    />
                    <span className="truncate">
                      {filter.counts?.[option.value] === undefined
                        ? option.label
                        : `${option.label} · ${filter.counts[option.value]}`}
                    </span>
                  </label>
                );
              })}
            </fieldset>
          ))}
        </div>
      </details>
      )}
    </ChipRow>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-007@e879338 (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-21 (DEF-442 — the three <select>s become r10's `+ Filter ▾` panel and its removable chip row; IS-4's behaviour, BR-SHL-011's URL grammar and every pure transition are untouched) · AMENDED 2026-09-03 by the CS-40 lane (DEF-3504 — a declared `dateRange` renders two native date boxes in the same panel and one chip in the tenant's date format; the option-list path is byte-identical and asserted so against two committed fixtures)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ tsc✔ eslint✔ vitest 31/31✔ (5 TC todo this packet — browser/journey/backend scope) · [CS-40 2026-09-03] tsc✔ eslint✔ g13✔ g15✔ g27✔ g31✔ g37✔ g43✔ g44✔ g45✔ routeBUtilities 10/10✔ vitest src/components+src/styles 36 files / 432 passed / 30 todo
// exceptions: E4 [DEF-442 2026-08-21] r10's panel multi-selects within a dimension and this one does not — `TableRequestState.filters` is one value per dimension and the server applies it, so widening it is an API change; filed as OQ-306 rather than chosen · E4 [DEF-442] r10's 10px panel heading renders at 12px — the named type scale has no 10px tier and G34 refuses the arbitrary value; same resolution DEF-440 took for the column panel · E2 [CS-40 2026-09-03] the date-range capability is UNWIRED on purpose — no list declares one yet, and the payments lane adds the two entries that make it visible. G13 is unaffected (it asks about optional PROPS, and this is a config key) and G45 is unaffected (it asks whether a screen declaring `filters` renders a control). This is hard-won law 2 accepted knowingly rather than papered over with a fake caller
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
