// ── Trace ──────────────────────────────────────────────
// Story:   CR-142-BRC07 Phase 1 · P1.2 (search and the two filters, read
//          SERVER-SIDE) · P1.3 (screen 1·1) · P1.8 (the service list is the
//          tenant's enabled set, off the answer the catalogue already made).
//          Screens: S44
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT) · rule 21 (Tailwind
//          utilities, no stylesheet class) · rule 44 (the drawing says WHAT is
//          on the screen; our kit says how it is BUILT) · rule 33 (a LABEL is
//          three words; a FACT is six) · rule 31 (no database id is ever the
//          visible value of a field) · BR-REP-006 (a vocabulary is read LIVE)
// Tests:   src/features/reports/catalogueScreen.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ROW ONE OF SCREEN 1·1: SEARCH · THE APPLIED CHIPS · TWO FILTERS.
//
// ── WHAT THE DRAWING SHOWS, READ AS AN IMAGE (p20, scale 6) ─────────────────
//
//     [ Search this list          ]  Receivables ×   [All groups ⌄] [All services ⌄]
//
// Four things, in that order, on one baseline. The applied-filter chip sits
// BETWEEN the search box and the dropdowns, which is exactly where `FilterBar`
// already inserts one and where r10 inserts one before it.
//
// ⚠ **THE `▦` BUTTON AT THE FAR RIGHT OF THE DRAWN ROW IS NOT BUILT, AND THE
// DOCUMENT IS WHY.** Its own TABLE CONTROLS row for this screen (p21) reads
// *"Columns n/a, a card grid"*. `▦` is `DataTable`'s column chooser; 1·1 is not
// a table and has no columns to choose. Drawing it would be a control that
// opens onto nothing — hard-won law 2's mirror, the shape that left the portal
// with two working doors out of eight — so the drawing and the document
// disagree here and the document's own prose settles it. Recorded rather than
// silently dropped.
//
// ── WHY THESE ARE `SelectField`S AND NOT `FilterBar` ────────────────────────
//
// `FilterBar` renders r10's chip row: an `All` chip, the applied chips, and a
// `+ Filter ⌄` disclosure. That is a different SHAPE from two labelled
// dropdowns, and the shape is the drawing's to decide (B14 rule 41/44). What
// our standard decides is how each control is BUILT, so each dropdown is the
// kit's own `SelectField` and the chip is the kit's own `Chip` — the two pieces
// `FilterBar` itself is made of. Nothing here is hand-rolled.
//
// ⚠ **`labelHidden` IS THE DRAWING'S DOING AND THE ACCESSIBLE NAME IS OURS.**
// The drawn control carries no label above it; the first option names it (*All
// groups*). A sighted user reads that option, and `labelHidden` keeps a real
// `<label>` in the DOM for everyone else rather than a `<span>` that looks like
// one — which is the distinction `FilterRowAction` records costing a 1px
// misalignment when it was got wrong.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Chip } from "@/components/Chip";
import { FilterRow } from "@/components/FilterRow";
import { SelectField } from "@/components/FormModal";
import { createSearchDebouncer } from "@/components/searchDebounce";
import type { SearchDebouncer } from "@/components/searchDebounce";

export interface CatalogueQuery {
  q: string;
  group: string;
  service: string;
}

export interface CatalogueOption {
  code: string;
  name: string;
}

/**
 * The toolbar. Every control is CONTROLLED by `query` and reports through
 * `onChange`; nothing here filters anything.
 *
 * ⚠ **THAT IS `P1.2`'s WHOLE POINT AND IT IS WORTH SAYING IN THE FILE.** The
 * cheap version of this screen filters an array it was handed, which means the
 * endpoint must hand it every row — and `NFR-3` is breached in four places in
 * this product already, each one correct at 3,000 accounts and thirteen times
 * short at 40,000. A toolbar that only reports its state cannot become that.
 */
export function CatalogueToolbar(props: {
  query: CatalogueQuery;
  onChange: (next: CatalogueQuery) => void;
  groups: readonly CatalogueOption[];
  /** BR-REP-006 / P1.8 — the tenant's ENABLED services, off the same answer. */
  services: readonly CatalogueOption[];
}) {
  const { t } = useTranslation();
  const { query, onChange } = props;

  // The search box is local while typing and debounced into the request, which
  // is `DataTable`'s own behaviour through `DataTable`'s own debouncer — the
  // same 300ms and the same two-character floor, so this box and every other
  // search box in the product feel identical.
  const [typed, setTyped] = useState(query.q);
  const fireRef = useRef<(value: string) => void>(() => undefined);
  fireRef.current = (value) => onChange({ ...query, q: value });
  const debouncerRef = useRef<SearchDebouncer | null>(null);
  if (debouncerRef.current === null) {
    debouncerRef.current = createSearchDebouncer((value) => fireRef.current(value), query.q);
  }
  const debouncer = debouncerRef.current;
  useEffect(() => () => debouncerRef.current?.clear(), []);

  const groupName = props.groups.find((option) => option.code === query.group)?.name;
  const serviceName = props.services.find((option) => option.code === query.service)?.name;

  return (
    <div className="mb-6 flex flex-col gap-3" data-catalogue-toolbar="">
      <FilterRow data-filter-row="catalogue">
        <div className="relative flex min-w-[15rem] max-w-[32rem] flex-[1_1_20rem] items-center">
          <input
            className="input"
            type="search"
            data-catalogue-search=""
            value={typed}
            // B14 rule 19: the list's own prompt, and the SAME sentence as the
            // accessible name. The drawing writes "Search this list", which is
            // what this key already says in all eleven catalogues.
            placeholder={t("table.search.placeholder")}
            aria-label={t("table.search.placeholder")}
            onChange={(event) => {
              setTyped(event.target.value);
              debouncer.type(event.target.value);
            }}
          />
          {typed !== "" && (
            <button
              type="button"
              className="absolute right-2 cursor-pointer border-none bg-transparent text-btn-sm text-accent"
              aria-label={t("table.search.clear")}
              onClick={() => {
                setTyped("");
                debouncer.clear();
                onChange({ ...query, q: "" });
              }}
            >
              ✕
            </button>
          )}
        </div>

        <div className="min-w-[11rem]">
          <SelectField
            id="catalogue-group"
            label={t("reports.library.filter.group")}
            labelHidden
            value={query.group}
            placeholder={t("reports.library.filter.groupAll")}
            options={props.groups.map((option) => ({
              value: option.code,
              label: option.name,
            }))}
            onChange={(value) => onChange({ ...query, group: value })}
          />
        </div>

        <div className="min-w-[11rem]">
          <SelectField
            id="catalogue-service"
            label={t("reports.library.filter.service")}
            labelHidden
            value={query.service}
            placeholder={t("reports.library.filter.serviceAll")}
            options={props.services.map((option) => ({
              value: option.code,
              label: option.name,
            }))}
            onChange={(value) => onChange({ ...query, service: value })}
          />
        </div>
      </FilterRow>

      {/* The applied chips. Drawn between the search box and the dropdowns on
          p20; kept on their own line here because at 1280 the row is already
          four controls wide and a chip appearing mid-row reflows all of them.
          The chip is the kit's, so it cannot become a fourth chip shape. */}
      {(groupName !== undefined || serviceName !== undefined) && (
        <div className="flex flex-wrap gap-2" data-catalogue-chips="">
          {groupName !== undefined && (
            <Chip
              onRemove={() => onChange({ ...query, group: "" })}
              removeLabel={t("table.filters.remove", {
                label: t("reports.library.filter.group"),
              })}
            >
              {groupName}
            </Chip>
          )}
          {serviceName !== undefined && (
            <Chip
              onRemove={() => onChange({ ...query, service: "" })}
              removeLabel={t("table.filters.remove", {
                label: t("reports.library.filter.service"),
              })}
            >
              {serviceName}
            </Chip>
          )}
        </div>
      )}
    </div>
  );
}

export default CatalogueToolbar;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 Phase 1 · P1.2 · P1.3 · P1.8 (05-prototype/09 Reports Build Brief.pdf p19-p21 read as IMAGES per B14 rule 42)
// screens: S44
// generated: 2026-09-26 by lane REP-P1
// gates: RED PROVED FIRST — catalogueScreen.dom.test.tsx found no search box and no filter on /{tenant}/reports before this component existed
// exceptions: (1) the drawn `▦` column chooser is NOT built — the document's own TABLE CONTROLS row says "Columns n/a, a card grid", and a control onto nothing is hard-won law 2's mirror · (2) `SelectField` rather than `FilterBar`: the drawn SHAPE is two dropdowns, which is the drawing's to decide, and the kit decides how each is built
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
