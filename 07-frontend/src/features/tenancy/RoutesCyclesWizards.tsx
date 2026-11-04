// ── Trace ──────────────────────────────────────────────
// Change:  CR-006 (PO 2026-08-16) — SET-06 Add/Edit Route and SET-07 Add/Edit
//          Cycle, four steps each, FULL PAGE and not a modal.
// Story:   US-MET-006 (EP-MET-02)  Screens: S8 → Routes & Cycles · r10 SET-06/07
// Rules:   BR-MET-073 (route code from the series, editable; service · area ·
//          reader · notes) · BR-MET-074 (a premises on another route MOVES,
//          with confirm) · BR-MET-075 (a meter may be excluded and stays on the
//          premises) · BR-MET-076 (Draft or Activate; a draft affects nothing) ·
//          BR-MET-077 (day-of-month DEFAULTS, not dates) · BR-MET-078 (NO money,
//          no late/penalty control, no fee clause in the preview) ·
//          BR-MET-080 (the coverage query) · BR-MET-081 (an edit lands next
//          read window, stated inline) · BR-MET-035b (System Admin only) ·
//          BR-SHL-018/019 (rail + one transactional commit) · BR-SHL-025
//          (read-only WITH the reason on the control)
// B14:     rule 3 (stepper) · 4 (button grammar: `+ Noun`, `Verb →`, `Verb ✓`) ·
//          5 (two button sizes) · 8 (dropdown chevron; 5+ searchable) ·
//          9 (multi-select as removable chips) · 10 (asterisk on the label) ·
//          11 (consequence preview before a commit) · 12 (toolbar + chips) ·
//          15 (icon row actions) · 16 (pagination footer) · 18 (80% measure)
// ───────────────────────────────────────────────────────
/**
 * The two wizards. They are FULL-PAGE flows, which is the CR's own word
 * (*"4-step wizard (full page, not modal)"*), and the reason is legible on
 * SET-06 step 2: a dual-pane picker over 214 premises with its own toolbar,
 * filter chips and pagination footer does not fit in a dialog, and the modal
 * this replaces said so out loud — its header comment recorded that membership
 * "needs the Premises & Units screens that do not exist in this app yet", so
 * it shipped the fields the endpoint accepted and stated where membership was
 * edited instead. Those screens exist now.
 *
 * ⚠ **THE MONEY BOUNDARY IS VISIBLE BY ABSENCE HERE, ON PURPOSE.** r10's
 * SET-07.3 draws a fourth control, `Late / penalty date`, and its preview
 * strip ends *"· late fee 31st"*. Neither is in this file. PO ruling
 * 2026-08-16: *"you dont need late fees in this. so dont have anything related
 * to money when you create route and cycles."* Grace has exactly one home —
 * Billing defaults, BR-BIL-002/008 — and a second screen that appears to
 * decide when a fee starts is worse than one screen that does. The preview
 * below therefore stops at `due`, and does not derive the missing clause from
 * elsewhere either: a fee date RENDERED here reads as this screen's field
 * however it was sourced.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  createCycle,
  createRoute,
  getCycleCoverage,
  getCycleRoutes,
  getLookupEntries,
  getNextCycleCode,
  getNextRouteCode,
  getRouteMeterPicker,
  getRoutePremisesMembers,
  getRoutePremisesPicker,
  getRoutesPage,
  getTenantServices,
  updateCycle,
  updateRoute,
} from "@/api/endpoints";
import type { CycleRow, LookupEntry, RoutePickerPremises, RouteRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import {
  CustomFieldsInput,
  customDataChanges,
  missingRequiredLabels,
  useCustomFieldRegistry,
} from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DataTable } from "@/components/DataTable";
import { ListPager, pageSlice } from "@/components/ListPager";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { DEFAULT_PAGE_SIZE, PAGE_SIZES } from "@/components/tableTypes";
import type { PageSize, TableColumnConfig, TableConfig, TableRequestState } from "@/components/tableTypes";
import { WizardFrame } from "@/components/WizardFrame";
import { Kicker } from "@/components/TextBits";
import type { WizardCommitOutcome } from "@/components/WizardFrame";
// ⚠ **THE AREA PAIR IS METERING'S, AND BORROWING IT IS THE POINT** (`DEF-TEN-5842`).
// `areaPayloadCode` is the ONE mapping from two controls to the one stored
// column; a second copy here is how a route and a premises come to disagree
// about what "sub-area chosen" means. Four files in this folder already import
// from `meteringShared` for exactly this reason.
import { sizeClassName, useSizeClassNames } from "@/features/assets/assetsShared";
import { NO_AREA, areaPayloadCode, subAreasOf, topLevelAreas } from "@/features/metering/meteringShared";
import type { AreaSelection } from "@/features/metering/meteringShared";

import {
  CYCLE_FREQUENCY_WORDS,
  PickerFilterChips,
  RC_DESC,
  effectiveStartDay,
  frequencyKey,
  pluralKey,
} from "./routesCyclesShared";
import { apiErrorText, ordinalDay } from "./settingsShared";
import type { Translator } from "./settingsShared";

// ── Pure pieces — testable without a browser ───────────────────────────────

/** BR-MET-073: r10 SET-06.1's three read types, in its order. */
export const ROUTE_TYPES = ["drive", "ami", "walk"] as const;

/**
 * The page size `Select all {n}` asks for while it walks (`DEF-TEN-5840`).
 *
 * ⚠ **IT IS THE TOP OF `PAGE_SIZES` BECAUSE THE SERVER CLAMPS TO IT.**
 * `core.pagination.clamp_page_size` rounds any `per` DOWN to the largest
 * allowed size not above it and caps the whole thing at 1,000 — so asking for
 * 40,000 is answered with 1,000 and asking for 1,500 is answered with 1,000.
 * Naming the real ceiling here is what makes the walk's arithmetic true; a
 * larger number would read as one request and silently be forty.
 */
const SELECT_ALL_PER: PageSize = PAGE_SIZES[PAGE_SIZES.length - 1];

/**
 * **WHICH OF THE TWO BOXES A STORED AREA CODE BELONGS IN** (`DEF-TEN-5842`).
 *
 * ⚠ **THE ROUTE SERIALIZER PUBLISHES NO `area_parent_code`, SO THE PAIR CANNOT
 * BE RE-OPENED THE WAY A PREMISES RE-OPENS IT.** `meteringShared`'s own
 * `areaSelectionFrom` reads `area_code` BESIDE `area_parent_code` precisely
 * because a bare code cannot say which box it came from, and its docstring
 * names the consequence of guessing: *"a client that guessed would put every
 * sub-area in the Area box and quietly re-tag the premises to its parent on the
 * next save."* `RouteRow` carries `area_code` and `area_name` and nothing else,
 * so that function cannot be used here.
 *
 * **It is resolved rather than guessed.** This wizard already reads the whole
 * area lookup for its picker, and every entry carries `is_sub_area` and
 * `parent_code` — so the authoritative answer is already in hand and costs no
 * request. Adding `area_parent_code` to the route serializer would work too and
 * is the tidier long-term shape; it is a backend change this lane does not own,
 * and it is NOT needed for correctness because of the line below.
 *
 * An unknown code returns the EMPTY pair rather than inventing a top-level
 * area: a route tagged to a district that has since been deleted must not
 * silently re-tag itself to a code nobody chose on the next save.
 */
export function areaSelectionFromEntries(
  code: string,
  entries: readonly LookupEntry[],
): AreaSelection {
  if (code === "") {
    return NO_AREA;
  }
  const match = entries.find((entry) => entry.code.toLowerCase() === code.toLowerCase());
  if (match === undefined) {
    return NO_AREA;
  }
  return match.is_sub_area === true
    ? { top: String(match.parent_code ?? ""), sub: match.code }
    : { top: match.code, sub: "" };
}

/**
 * BR-MET-077 **as amended by CR-029** — the EIGHT one-word business frequencies.
 *
 * ⚠ **THIS HELD THREE LOWERCASE CR-006 VALUES (`monthly` · `bi_monthly` ·
 * `quarterly`) UNTIL W5-T2, AND THAT WAS THE WIZARD SHIPPING THE WRONG
 * VOCABULARY.** The PO ruled it pre-CR, verbatim: *"we can capture start day,
 * frequency, monthly, weekly daily, biweekly, once in two months , quaterly etc
 * and days to complete it ; give business names to frequence - 1 word."* B17 §2
 * names all eight, the server has accepted only these words since RC-W1, the
 * landing and the detail render them, and the CREATE screen still offered three.
 * A utility that bills quarterly could pick that; one that bills weekly could
 * not, and nothing said so.
 *
 * The words are `routesCyclesShared`'s, not a second copy: one list, so the
 * option a person picks and the label the detail prints cannot disagree.
 */
export const CYCLE_FREQUENCIES = CYCLE_FREQUENCY_WORDS;

/**
 * BR-MET-074 — how many of the selected premises will MOVE off another route.
 *
 * r10 SET-06.4 renders it as *"12 premises currently on SCW-R2 move to this
 * route — SCW-R2 drops to 376 members. No bills change; only who reads them."*
 * That last clause is the whole reason this is computed and shown BEFORE the
 * commit (B14 rule 11): the write changes who READS a premises and nothing
 * about what it is billed, and a staff member who cannot see that will assume
 * the worse thing.
 */
/** Whatever can answer *"is this row picked"* and *"how many are picked"* —
 *  a `Set` of ids or, since `DEF-MET-5743`, the `Map` the wizard keeps so a
 *  selection survives paging. Widened rather than swapped: the SET-05 suite
 *  calls both of these with a `Set` and that reading is still the truth. */
export interface Selection {
  has: (id: string) => boolean;
  size: number;
}

export function movesFor(
  rows: readonly RoutePickerPremises[],
  selected: Selection,
): { route: string; count: number }[] {
  const tally = new Map<string, number>();
  for (const row of rows) {
    if (!selected.has(row.id) || row.current_route === null) {
      continue;
    }
    tally.set(row.current_route, (tally.get(row.current_route) ?? 0) + 1);
  }
  return [...tally.entries()]
    .map(([route, count]) => ({ route, count }))
    .sort((a, b) => a.route.localeCompare(b.route));
}

/** SET-06 step 2's counter: "143 selected · 156 units". */
export function selectionTotals(
  rows: readonly RoutePickerPremises[],
  selected: Selection,
): { premises: number; units: number; meters: number; unitIds: string[] } {
  let units = 0;
  let meters = 0;
  const unitIds: string[] = [];
  for (const row of rows) {
    if (!selected.has(row.id)) {
      continue;
    }
    units += row.units;
    meters += row.meters;
    unitIds.push(...row.unit_ids);
  }
  return { premises: selected.size, units, meters, unitIds };
}

/**
 * BR-MET-077 — the preview strip, **stopping at `due`**.
 *
 * r10's own string is *"Read 1–3 · exceptions cleared by 4th · bills out 5th ·
 * due 26th · late fee 31st"*. The last clause is dropped by ruling 1 and is
 * NOT computed, derived or fetched — see the file docstring.
 *
 * `wraps` is true when the due day falls on or before the bill day, which is a
 * normal Net-10 arrangement running into the following month. The server
 * deliberately does not refuse it (a hint written about one example must not
 * refuse a real cycle), so the preview is where it becomes visible.
 */
export function schedulePreview(days: {
  startDay: string;
  daysToComplete: string;
  bill: string;
  dueDays: string;
}): {
  readFrom: number;
  readTo: number;
  exceptionsBy: number;
  bill: number;
  due: number;
  wraps: boolean;
} | null {
  const startDay = Number(days.startDay);
  const daysToComplete = Number(days.daysToComplete);
  const bill = Number(days.bill);
  const dueDays = Number(days.dueDays);
  if (![startDay, bill].every((value) => Number.isInteger(value) && value >= 1 && value <= 31)) {
    return null;
  }
  if (!Number.isInteger(daysToComplete) || daysToComplete < 1) {
    return null;
  }
  if (!Number.isInteger(dueDays) || dueDays < 0) {
    return null;
  }
  // ⚠ **THE WINDOW IS DERIVED HERE, EXACTLY AS THE SERVER DERIVES IT** —
  // *"start day + N days IS the read window"* (B17 §2), INCLUSIVE, clamped at
  // 31 for the same reason `_check_cycle_days` clamps: a window opening on the
  // 29th with 5 days runs into the following month, and a day-of-month preview
  // cannot say so. The DETAIL page shows the real dates (SET-07D's Schedule
  // card, from the period engine); this strip is the shape, not the calendar.
  const readTo = Math.min(31, startDay + daysToComplete - 1);
  return {
    readFrom: startDay,
    readTo,
    exceptionsBy: Math.min(31, readTo + 1),
    bill,
    // The due DAY the preview draws is the bill day plus the cycle's due-days,
    // wrapped within a nominal 31-day month. `due_days` is what billing adds
    // (BR-BIL-024) and a day-of-month is what this strip speaks.
    due: ((bill + dueDays - 1) % 31) + 1,
    wraps: bill + dueDays > 31,
  };
}

export function isDayOfMonth(raw: string): boolean {
  const value = Number(raw);
  return Number.isInteger(value) && value >= 1 && value <= 31;
}

// ── Shared chrome ──────────────────────────────────────────────────────────

/* ⚠ `WizardPager` LIVED HERE AND IS NOW `components/ListPager` (CR-029
 * RC-W3-T7). It was already the footer's second implementation, and DEF-223
 * needed it on three more tables — the SET-06 meter list, the SET-07 route
 * picker and the two ops tabs — which would have made it the third and fourth.
 * B13 carries its kit row. The four `table.pager.*` keys and the `table-pager*`
 * classes are unchanged, so every footer in the product is still one thing. */

/**
 * B14 rule 11 — the consequence preview. *"Any form writing money, service
 * state or legal notices shows a 'what this will do' box before its commit
 * button."*
 *
 * Neither wizard writes money (BR-MET-078). Both write SERVICE STATE: which
 * crew reads a premises, and which cycle bills an account. So the rule applies
 * on its second clause, and the box is the r10 `exception` strip.
 */
/* ⚠ **MOVED INTO THE SHARED KIT ON 2026-09-05 (CR-070 wave E, B14 rule 36).**
 * This component was declared HERE — in a screen file — and read by this
 * screen's four call sites and nothing else, while `09-component-inventory.md`
 * lists it against THIRTEEN Work screens and the portal carries a third shape
 * of the same idea. It now lives in `components/ConsequenceBox.tsx`, unchanged
 * in every pixel and every `data-` hook, and this line re-exports it so every
 * call site and every assertion in this file's suite keeps working.
 *
 * The tone strings, the reason they are WHOLE strings rather than an
 * interpolation, and the two washes all travelled with it — read that file for
 * them. Nothing on the routes-and-cycles wizards renders differently. */
export { ConsequenceBox };

/** B14 rule 10 — the asterisk lives on the LABEL. */
function Field(props: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1" data-rcw="field">
      <span
        className={
          props.required
            ? "text-sm font-semibold after:text-danger-700 after:content-['_*']"
            : "text-sm font-semibold"
        }
      >
        {props.label}
      </span>
      {props.children}
      {props.hint !== undefined && (
        <span
          className="m-0 max-w-measure text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]"
          data-rcw="hint"
        >
          {props.hint}
        </span>
      )}
    </label>
  );
}

export interface WizardProps {
  client?: ApiClient;
  readOnly: boolean;
  onDone: (message: string) => void;
  onCancel: () => void;
}

// ═══════════════════════════════════════════════════════════════════════════
// SET-06 · ROUTE WIZARD
// ═══════════════════════════════════════════════════════════════════════════

export function RouteWizard(props: WizardProps & { route: RouteRow | null }) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const editing = props.route !== null;

  const [code, setCode] = useState(props.route?.code ?? "");
  const [name, setName] = useState(props.route?.name ?? "");
  const [routeType, setRouteType] = useState(props.route?.route_type ?? "drive");
  const [serviceCode, setServiceCode] = useState(props.route?.service_code ?? "");
  /**
   * ⚠ **AREA AND SUB-AREA ARE TWO CONTROLS, AND THIS SCREEN HAD ONE**
   * (`DEF-TEN-5842`). The PO ruled it on 2026-09-08, verbatim: *"these should be
   * 2 input fileds - Area · sub-area - not 1"*. That ruling was applied to the
   * premises screens the same day and **never reached this wizard**, which went
   * on drawing ONE select — under a label that literally read `Area · sub-area`,
   * so the screen named two fields and offered one. It is the shape this repo
   * keeps paying for: a ruling lands, and the surface nobody was looking at
   * keeps contradicting it (hard-won law 12's pointer rot, in a screen).
   *
   * **ONE STORED COLUMN, WHICH IS UNCHANGED.** `areaPayloadCode` sends the
   * SUB-AREA when one is chosen and otherwise the area — metering's own
   * mapping, borrowed rather than re-derived, so a route and a premises cannot
   * come to mean different things by the same code. `BR-MET-073` still gives a
   * route ONE area and nothing about what is written has moved.
   */
  const [area, setArea] = useState<AreaSelection>(NO_AREA);
  /** The stored code can only be split into the pair once the lookup has
   *  arrived to say which half it is — see `areaSelectionFromEntries`. A CREATE
   *  starts empty and needs no seeding at all. */
  const [areaSeeded, setAreaSeeded] = useState(!editing);
  const [notes, setNotes] = useState(props.route?.notes ?? "");
  const [nameError, setNameError] = useState(false);
  // CR-161-BRC10 W4 — the utility's own route fields (`ROUTE_FORM`). An EDIT
  // sends only what changed (`customDataChanges`), so a stored answer to a
  // field since switched off is never sent back and refused.
  const storedCustomData: CustomFieldValues = props.route?.custom_data ?? {};
  const [customData, setCustomData] = useState<CustomFieldValues>(storedCustomData);
  const [customMissing, setCustomMissing] = useState<string[]>([]);
  const customRegistry = useCustomFieldRegistry({
    entity: "routes",
    screen: "ROUTE_FORM",
    mode: "input",
    client,
  });

  // Step 2 state.
  const [search, setSearch] = useState("");
  /**
   * ⚠ **THIS WAS A SECOND, DISCONNECTED AREA STATE AND IT STARTED EMPTY**
   * (`DEF-TEN-5843`). Step 1 asked which area the route covers and the picker
   * then offered EVERY premises in the tenant — up to 40,000 rows at T5 — with
   * nothing carrying the answer across. `serviceCode` has always flowed from
   * step 1 into the picker's query; the area simply never did, which is what
   * made it a bug rather than a design.
   *
   * **IT IS A DEFAULT, NOT A LOCK.** The chips below are what the clerk sees
   * and edits; until they touch them, the applied filter is DERIVED from step
   * 1's answer (`appliedAreas`). A route genuinely does pick up a stray
   * property outside its area, so removing the chip — or pressing `All` —
   * widens it back to the whole tenant, and changing the area in step 1 starts
   * the derivation again rather than fighting a stale copy.
   */
  const [areaChips, setAreaChips] = useState<string[]>([]); // BR-MET-072 multi-select
  const [areaFilterTouched, setAreaFilterTouched] = useState(false);
  const [unassignedOnly, setUnassignedOnly] = useState(false);
  /**
   * ⚠ **THE SELECTION IS A MAP, AND THAT IS `DEF-MET-5743`'s SECOND HALF.**
   * It was a `Set` of ids over an array holding EVERY premises in the tenant,
   * so the running count, the move warnings and the meter list for step 3 were
   * all read back out of that array. With the picker paged, the array is one
   * page — and a selection made on page 1 would vanish from every one of those
   * the moment the clerk went to page 2, silently, with the row still ticked
   * when they came back. Keeping the ROW beside the id is what makes a
   * selection that spans pages mean anything.
   */
  const [selected, setSelected] = useState<Map<string, RoutePickerPremises>>(new Map());
  // The shared table's whole request state — search text, sort, page and page
  // size in one object, which is what `DataTable` reads and writes. `search`
  // above stays the SERVER's copy of `q`: the picker endpoint is what narrows
  // the rows, and the box is debounced by the kit before it gets here.
  const [tableState, setTableState] = useState<TableRequestState>({
    q: "",
    sort: "premise_no",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });
  // DEF-223, measured in Chromium: the step-3 meter list had NO pagination
  // footer, and B14 rule 16 exempts only a wizard SUMMARY table. A route with
  // 400 premises brings well over a thousand meters to this step.
  const [meterPage, setMeterPage] = useState(1);
  const [meterPer, setMeterPer] = useState<PageSize>(50);
  const [seeded, setSeeded] = useState(false);
  /** True while `Select all {n}` is in flight — the button disables itself so
   *  two presses cannot race to two different selections. */
  const [selectingAll, setSelectingAll] = useState(false);

  // Step 3 state — BR-MET-075. Excluded, not included: inclusion is the
  // ABSENCE of a row, so a premises added later brings its meters in without
  // anyone re-ticking them.
  const [excluded, setExcluded] = useState<Set<string>>(
    new Set(props.route?.excluded_asset_ids ?? []),
  );
  const [activate, setActivate] = useState(props.route?.status !== "draft");
  const [commitError, setCommitError] = useState<string | null>(null);

  /** The ONE area code this route is tagged with — the sub-area when one is
   *  chosen, otherwise the area (`BR-MET-071`, metering's own mapping). */
  const routeAreaCode = areaPayloadCode(area);
  /**
   * **THE AREAS THE PICKER IS ACTUALLY FILTERED BY** (`DEF-TEN-5843`).
   *
   * Derived while the clerk has not touched the chips, their own list
   * afterwards. ⚠ **DERIVED RATHER THAN COPIED ON ARRIVAL, DELIBERATELY.** A
   * copy made when step 2 opens goes stale the moment somebody steps back and
   * changes the area — the screen would then filter by an area no control on
   * it still shows, which is the *two disconnected states* bug this replaces
   * wearing a different hat. Deriving it means there is nothing to keep in
   * sync: step 1 IS the default, continuously, until the clerk overrides it.
   *
   * **BR-MET-072 does the rest**: a PARENT area matches every premises in it
   * AND in its sub-areas, so tagging a route `North district` opens the picker
   * on all of North including `NW` and `NE`, while tagging it
   * `North district · NW` opens on NW alone. The clerk's answer in step 1
   * decides the breadth, and neither reading is this screen's to invent.
   */
  const appliedAreas: string[] = areaFilterTouched
    ? areaChips
    : routeAreaCode === ""
      ? []
      : [routeAreaCode];

  /** Hand the chips back to the clerk. The first edit is what makes the filter
   *  theirs — after it, step 1 stops driving it. */
  function applyAreaFilter(next: string[]): void {
    setAreaChips(next);
    setAreaFilterTouched(true);
    setTableState((current) => ({ ...current, page: 1 }));
  }

  /** Step 1's answer changed, so the default it feeds must change with it —
   *  and a clerk who has NOT overridden the filter gets the new area applied
   *  rather than the old one left behind. */
  function changeRouteArea(next: AreaSelection): void {
    setArea(next);
    setAreaSeeded(true);
    setAreaChips([]);
    setAreaFilterTouched(false);
    setTableState((current) => ({ ...current, page: 1 }));
  }

  const nextCode = useQuery({
    queryKey: ["routes", "next-code"],
    queryFn: () => getNextRouteCode(client),
    enabled: !editing,
  });
  const services = useQuery({
    queryKey: ["settings", "services"],
    queryFn: () => getTenantServices(client),
  });
  const areas = useQuery({
    queryKey: ["lookups", "areas", "picker"],
    queryFn: () => getLookupEntries("areas", { per: 200 }, client),
  });
  // DEF-RAT-9321 — the meter table's Size column prints the NAME, not the code.
  const sizeNames = useSizeClassNames(client);
  /**
   * ⚠ **ONE PAGE, MATCHED AND ORDERED BY THE SERVER** (`DEF-MET-5743`,
   * `NFR-3`). This asked for every premises the filters matched — a bare array,
   * built server-side with a query per row — and then sorted and sliced it
   * here. The PO's report: *"Route setup becomes unusable at 5,000–10,000
   * premises"*.
   *
   * ⚠ **THE SORT AND THE PAGE ARE IN THE KEY BECAUSE THEY ARE IN THE
   * REQUEST.** Leaving either out is how a paged screen shows page 1's rows
   * under page 2's footer.
   */
  const picker = useQuery({
    queryKey: [
      "routes",
      "premises-picker",
      search,
      appliedAreas.join(","),
      serviceCode,
      unassignedOnly,
      props.route?.id ?? null,
      tableState.sort,
      tableState.dir,
      tableState.page,
      tableState.per,
    ],
    queryFn: () =>
      getRoutePremisesPicker(
        {
          q: search.length >= 2 ? search : undefined,
          areas: appliedAreas,
          service: serviceCode === "" ? null : serviceCode,
          unassignedOnly,
          routeId: props.route?.id ?? null,
          sort: tableState.sort,
          dir: tableState.dir,
          page: tableState.page,
          per: tableState.per,
        },
        client,
      ),
    placeholderData: (previous) => previous,
  });

  /**
   * The route's OWN members, for an edit — asked for by route, never found by
   * filtering the page in front of you.
   *
   * ⚠ **SEEDING FROM THE PAGE WOULD HAVE DELETED MEMBERS ON SAVE.** The commit
   * sends `premises_ids` as the whole membership, so a seed that saw only the
   * fifty rows on screen would have dropped every other member the moment the
   * clerk pressed Save — a silent removal, on a screen that looked right.
   */
  const members = useQuery({
    queryKey: ["routes", "premises-members", props.route?.id ?? null, serviceCode],
    queryFn: () =>
      getRoutePremisesMembers(
        props.route!.id,
        serviceCode === "" ? null : serviceCode,
        client,
      ),
    enabled: editing && props.route !== null,
  });

  // BR-MET-073: the pre-filled code is a SUGGESTION the admin may overtype, so
  // it seeds the field once and never fights the user's typing afterwards.
  if (!editing && !seeded && code === "" && nextCode.data?.code) {
    setCode(nextCode.data.code);
    setSeeded(true);
  }

  // DEF-218: TRUE while the code box still holds exactly what the server
  // previewed and the admin has not touched it. Compared against the PREVIEWED
  // VALUE rather than a "was seeded" boolean on purpose — a `seeded` flag stays
  // true after the admin edits the box, so it cannot tell an untouched pre-fill
  // from a code a human typed, and sending a human's code is the whole point of
  // keeping the field.
  const codeIsUntouchedPrefill =
    !editing && nextCode.data?.code !== undefined && code.trim() === nextCode.data.code;
  // An EDIT re-opens its own members. Seeded once, from the route's own
  // membership read — not from whichever page happens to have arrived.
  if (editing && !seeded && members.data) {
    setSelected(new Map(members.data.map((row) => [row.id, row])));
    setSeeded(true);
  }

  const rows = picker.data?.rows ?? [];
  /** Every row the FILTERS match, which is what the footer and `Select all`
   *  both state. `rows.length` is the page and would understate both. */
  const matching = picker.data?.total ?? 0;
  // ⚠ Computed from the SELECTION and no longer from the rows on screen: the
  // two were the same thing only while the browser held the whole tenant.
  const chosen = [...selected.values()];
  const totals = selectionTotals(chosen, selected);
  const moves = movesFor(chosen, selected);

  // ── `CR-131-BRC07` step 5 · THE PREMISES TICKED, NOT THEIR UNITS ─────────
  //
  // ⚠ This sent `totals.unitIds` — one `unit_id` query parameter per unit, at
  // **52 characters each**. On the property the Product Owner reported, 6
  // premises carried **726 units**, so the URL reached **37,994 characters**
  // against a 4–8 KB server limit: the request never arrived, and the table
  // below drew *"No meters yet"* over a route full of meters. Six premises ids
  // is about 250 characters.
  //
  // `per: "all"` because this table pages in the browser and the counter above
  // it states the whole set; the server has no cap (`NFR-5`), so asking for
  // everything is a request it can honour rather than a limit being dodged.
  const selectedPremisesIds = [...selected.keys()];
  const meters = useQuery({
    queryKey: ["routes", "meter-picker", selectedPremisesIds.join(","), props.route?.id ?? null],
    queryFn: () =>
      getRouteMeterPicker({ premisesIds: selectedPremisesIds, routeId: props.route?.id ?? null, per: "all" }, client),
    enabled: selectedPremisesIds.length > 0,
  });
  const meterRows = meters.data?.meters ?? [];
  const includedMeters = meterRows.filter((meter) => !excluded.has(meter.id)).length;

  const areaOptions: LookupEntry[] = areas.data?.results ?? [];
  /** BR-TEN-034 deactivates rather than deletes, so only ACTIVE rows are
   *  offerable — and metering's own two helpers decide which is which, rather
   *  than a second reading of `is_sub_area` written here. */
  const topAreas = topLevelAreas(areaOptions);
  const subAreas = subAreasOf(areaOptions, area.top);
  /**
   * An EDIT re-opens its stored code into the PAIR, once, as soon as the lookup
   * can say which of the two boxes it belongs in (`DEF-TEN-5842`). Seeded like
   * the code box and the membership above it: once, from the authoritative
   * read, never from whatever happens to be on screen.
   */
  if (!areaSeeded && areas.data) {
    setArea(areaSelectionFromEntries(props.route?.area_code ?? "", areaOptions));
    setAreaSeeded(true);
  }
  /** An area code as a person reads it — `North district · NW`, the same string
   *  the row's own Area column prints. Falls back to the CODE while the lookup
   *  is still in flight, which is honest and momentary; inventing a blank there
   *  would render a chip with no words in it. */
  function areaLabelFor(code: string): string {
    const entry = areaOptions.find((one) => one.code === code);
    if (entry === undefined) {
      return code;
    }
    return entry.parent_name ? `${String(entry.parent_name)} · ${entry.name}` : entry.name;
  }

  const commit = useMutation({
    mutationFn: async () => {
      const payload: Record<string, unknown> = {
        // DEF-218, PO ruling 2026-08-17 option (i): "the screen stops sending
        // the code and lets the server allocate."
        //
        // ⚠ THE PRE-FILLED CODE IS A PREVIEW AND ALLOCATES NOTHING.
        // `GET /…/next-code` shows what the series WOULD issue; the series only
        // advances when a create arrives with NO code ("an absent code is
        // use-the-series"). This screen sent the previewed code every time, so
        // the series never moved and the second save was refused with "already
        // exists" — a utility could create exactly one route and one cycle.
        //
        // So an UNTOUCHED pre-fill is omitted, and only a code the admin
        // actually typed or edited is sent. That keeps the human's own code
        // (and its duplicate refusal, which is a real and useful error) while
        // making the preview a preview.
        ...(codeIsUntouchedPrefill ? {} : { code: code.trim() }),
        name: name.trim(),
        route_type: routeType,
        service_code: serviceCode,
        // ONE column, unchanged (`BR-MET-073`): the sub-area when one is
        // chosen, otherwise the area. `DEF-TEN-5842` split the CONTROL in two
        // and moved nothing about what is written.
        area_code: routeAreaCode,
        notes: notes.trim(),
        // CR-161-BRC10 W4 — ALWAYS sent from this wizard (`{}` included): the
        // server reads the key as "typed on the route form", so a required
        // field binds here and never on a door that draws none.
        custom_data: editing ? customDataChanges(storedCustomData, customData) : customData,
        // BR-MET-076: the last step's choice, and the only place it is made.
        status: activate ? "active" : "draft",
        premises_ids: [...selected.keys()],
        excluded_asset_ids: [...excluded],
      };
      return editing ? updateRoute(props.route!.id, payload, client) : createRoute(payload, client);
    },
  });

  async function runCommit(): Promise<WizardCommitOutcome> {
    try {
      const saved = await commit.mutateAsync();
      props.onDone(
        t(editing ? "settings.routes.wizard.updated" : "settings.routes.wizard.created", {
          code: saved.code,
          premises: totals.premises,
          meters: includedMeters,
        }),
      );
      return { ok: true };
    } catch (error: unknown) {
      const reason = apiErrorText(error, translate);
      setCommitError(reason);
      return { ok: false, reason };
    }
  }

  if (services.isPending || areas.isPending) {
    return <LoadingSkeleton variant="card" />;
  }

  const readOnlyTitle = props.readOnly ? t("settings.readOnlyReason") : undefined;

  const stepOne = (
    <div className="flex flex-col gap-2.5">
      <h2 className="m-0 mt-2 mb-1 text-panel" data-rcw="title">
        {t("settings.routes.wizard.step1Title")}
      </h2>
      <div className="flex max-w-[640px] flex-col gap-3 border border-divider bg-surface p-3.5">
        <div className="grid grid-cols-[160px_1fr] gap-3 max-sm:grid-cols-1">
          <Field
            label={t("settings.routes.wizard.code")}
            hint={
              // A missing series row is REPORTED, never faked — CR-005 found
              // `JE-` had no row on any tenant and every manual journal entry
              // shipped unnumbered because nothing said so out loud.
              nextCode.data?.warnings.length
                ? t("settings.routes.wizard.codeSeriesMissing")
                : t("settings.routes.wizard.codeHint")
            }
          >
            <input
              className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text [font-feature-settings:'tnum']"
              data-rcw="code"
              value={code}
              disabled={props.readOnly}
              title={readOnlyTitle}
              onChange={(event) => setCode(event.target.value)}
            />
          </Field>
          <Field label={t("settings.routes.wizard.name")} required>
            <input
              className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text"
              value={name}
              disabled={props.readOnly}
              title={readOnlyTitle}
              placeholder={t("settings.routes.wizard.namePlaceholder")}
              aria-invalid={nameError || undefined}
              onChange={(event) => {
                setName(event.target.value);
                setNameError(false);
              }}
            />
          </Field>
        </div>
        {nameError && (
          <p className="m-0 text-sm text-danger-700" data-rcw="error" role="alert">
            {t("settings.routes.wizard.nameRequired")}
          </p>
        )}
        <div className="grid grid-cols-2 gap-3 max-sm:grid-cols-1">
          <Field label={t("settings.routes.wizard.readType")} required>
            <select
              className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text"
              value={routeType}
              disabled={props.readOnly}
              title={readOnlyTitle}
              onChange={(event) => setRouteType(event.target.value)}
            >
              {ROUTE_TYPES.map((value) => (
                <option key={value} value={value}>
                  {t(`settings.routes.wizard.type.${value}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label={t("settings.routes.wizard.service")}>
            <select
              className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text"
              value={serviceCode}
              disabled={props.readOnly}
              title={readOnlyTitle}
              onChange={(event) => setServiceCode(event.target.value)}
            >
              <option value="">{t("settings.routes.wizard.serviceAll")}</option>
              {(services.data ?? [])
                .filter((row) => row.enabled)
                .map((row) => (
                  <option key={row.service} value={row.service}>
                    {row.name}
                  </option>
                ))}
            </select>
          </Field>
          {/* ── `DEF-TEN-5842` · TWO CONTROLS, AS RULED ──────────────────────
              PO, 2026-09-08, verbatim: *"these should be 2 input fileds - Area
              · sub-area - not 1"*. The premises screens were corrected that
              day; this one was not, and its label has read `Area · sub-area`
              over a SINGLE box ever since — a field list promising two things
              and offering one.
              ⚠ **THE SUB-AREA BOX IS PRESENT AND EMPTY RATHER THAN ABSENT**,
              which is `AreaFields`' own decision on the premises screens and is
              copied deliberately: *"a control that materialises when you touch
              its neighbour is a control people do not find."* */}
          <Field label={t("metering.premises.field.area")}>
            <select
              className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text"
              value={area.top}
              disabled={props.readOnly}
              title={readOnlyTitle}
              data-rcw="area-top"
              onChange={(event) =>
                // Changing the AREA clears the sub-area — keeping `South · SE`
                // selected under `North` would store a code that contradicts
                // the box above it (`AreaFields`, same rule).
                changeRouteArea({ top: event.target.value, sub: "" })
              }
            >
              <option value="">{t("settings.routes.wizard.areaNone")}</option>
              {topAreas.map((entry) => (
                <option key={entry.id} value={entry.code}>
                  {entry.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("metering.premises.field.subArea")}>
            <select
              className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text"
              value={area.sub}
              // BR-SHL-025 — disabled WITH its reason, never a dead box. The
              // reason is the read-only one where that applies and otherwise
              // "pick an area first", which is what the help line says too.
              disabled={props.readOnly || area.top === ""}
              title={
                readOnlyTitle ??
                (area.top === ""
                  ? t("metering.premises.field.subAreaPickAreaFirst")
                  : undefined)
              }
              data-rcw="area-sub"
              onChange={(event) => changeRouteArea({ ...area, sub: event.target.value })}
            >
              {/* ⚠ **`No sub-area`, NOT `No area` — FOUND BY LOOKING AT THE
                  SCREEN (hard-won law 6).** The first cut reused the Area
                  box's own empty option here, so a route with `Downtown`
                  chosen above drew a Sub-area box reading *No area* — which
                  contradicts the control beside it and is the kind of thing
                  `tsc`, 27 vitest cases and every gate are green over, because
                  nothing in this repo reads rendered output. `AreaFields` has
                  always had the right string; this borrows it rather than
                  minting a twelfth. */}
              <option value="">{t("metering.premises.field.subAreaPlaceholder")}</option>
              {subAreas.map((entry) => (
                <option key={entry.id} value={entry.code}>
                  {entry.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("settings.routes.wizard.notes")}>
            <input
              className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text"
              value={notes}
              disabled={props.readOnly}
              title={readOnlyTitle}
              placeholder={t("settings.routes.wizard.notesPlaceholder")}
              onChange={(event) => setNotes(event.target.value)}
            />
          </Field>
        </div>
      </div>
      {/* CR-161-BRC10 W4 — the utility's OWN route fields. Renders nothing
          when the utility has placed none on this form. */}
      <CustomFieldsInput
        entity="routes"
        screen="ROUTE_FORM"
        values={customData}
        onChange={setCustomData}
        client={client}
      />
      {customMissing.length > 0 && (
        <p className="m-0 text-sm text-danger-700" role="alert" data-rcw="custom-missing">
          {t("customFields.requiredList", { fields: customMissing.join(", ") })}
        </p>
      )}
    </div>
  );

  // ── STEP 2 · THE PREMISES PICKER, ON THE SHARED TABLE ──────────────────
  // ⚠ **THIS WAS A HAND-ROLLED `<table>` WITH ITS OWN SEARCH BOX, ITS OWN
  //    `+ Filter` SELECT AND ITS OWN PAGER, AND THE PRODUCT OWNER REPORTED IT
  //    FROM THE DEPLOYED BUILD (2026-09-17):** *"we are not using table
  //    component toolkit - search, filter, colume selector - too much text"*.
  //    B14 rule 36 is the rule it broke — *the shared component kit is how you
  //    comply* — and the column selector was not merely styled differently, it
  //    **did not exist on this screen at all**.
  //
  // ⚠ **B14 RULE 16 DOES NOT EXEMPT IT, AND THE BLUEPRINT SAYS WHY.** The rule
  //    exempts a *wizard SUMMARY table*. This is a PICKER over every premises
  //    the filters match — 79 on the demo tenant, and a real utility's route is
  //    built from hundreds — so it is a list table that happens to live in a
  //    wizard. The Meter Reads blueprint draws the same distinction on its own
  //    stage-3 grid: *"Exempt as a wizard table — but the rows behind it are
  //    the whole batch, which is the finding."*
  //
  // ⚠ **WHAT THE MOVE DELIBERATELY KEEPS.** `Select all {n}` is not decoration:
  //    it selects everything matching the CURRENT filters, which is how a route
  //    over an entire area is built, and it is the one control that would have
  //    been lost by swapping tables. The running `n selected · n units` count
  //    keeps its place for the same reason.
  /**
   * `Select all {n}` — the WHOLE match set, from the server, in one request.
   *
   * ⚠ **NOT A WALK OF EVERY PAGE.** `per` is omitted, so the endpoint answers
   * the filtered set in one read; that is the same shape the export takes and
   * it happens only because a person pressed a button that states the count.
   * A failure leaves the selection untouched rather than half-applied — a
   * partially selected route is a route that quietly loses members on save.
   */
  async function selectEveryMatch(): Promise<void> {
    setSelectingAll(true);
    try {
      const everything = await getRoutePremisesPicker(
        {
          q: search.length >= 2 ? search : undefined,
          areas: appliedAreas,
          service: serviceCode === "" ? null : serviceCode,
          unassignedOnly,
          routeId: props.route?.id ?? null,
        },
        client,
      );
      setSelected(new Map(everything.rows.map((row) => [row.id, row])));
    } catch (error: unknown) {
      setCommitError(apiErrorText(error, translate));
    } finally {
      setSelectingAll(false);
    }
  }

  const premisesColumns: TableColumnConfig<RoutePickerPremises>[] = [
    {
      key: "select",
      label: t("settings.routes.wizard.col.select"),
      // LOCKED: a picker whose checkbox column can be hidden is a picker that
      // cannot pick. `locked` is honoured by the reducer as well as by the
      // checkbox, so a stored column set from another screen cannot drop it.
      locked: true,
      cell: (row) => (
        <input
          type="checkbox"
          checked={selected.has(row.id)}
          disabled={props.readOnly}
          title={readOnlyTitle}
          aria-label={t("settings.routes.wizard.selectPremises", { address: row.address_line })}
          onChange={(event) => {
            // The ROW goes in with the id — the count, the move warnings and
            // step 3's meter list all read it back, and after `DEF-MET-5743`
            // this is the only place that still has it in hand.
            const next = new Map(selected);
            if (event.target.checked) {
              next.set(row.id, row);
            } else {
              next.delete(row.id);
            }
            setSelected(next);
          }}
        />
      ),
    },
    {
      key: "premise_no",
      label: t("settings.routes.wizard.col.premise"),
      sortable: true,
      identity: true,
      // B14 rule 31: the PREMISE NUMBER is the human-facing reference; the row
      // id never reaches the screen. A premises with no number says so with a
      // dash rather than falling back to its uuid.
      cell: (row) => <b>{row.premise_no ?? "—"}</b>,
    },
    {
      key: "address_line",
      label: t("settings.routes.wizard.col.address"),
      sortable: true,
    },
    {
      key: "premises_type",
      label: t("settings.routes.wizard.col.type"),
      sortable: true,
      cell: (row) => row.premises_type ?? "—",
    },
    { key: "units", label: t("settings.routes.wizard.col.units"), numeric: true, sortable: true },
    // ⚠ **NOT SORTABLE, AND THAT IS THE HONEST HALF OF `DEF-MET-5743`.**
    // `meters` is derived through the assets seam and `current_route` through
    // the membership table, so neither is a column the database can ORDER BY —
    // and ordering by them would mean building every row in the tenant before
    // the slice, which is the defect this screen was rewritten to remove.
    // A header offering an ordering the request cannot ask for is the same
    // refusal `ACCOUNT_SORTS` already carries for `last_bill`.
    { key: "meters", label: t("settings.routes.wizard.col.meters"), numeric: true },
    {
      key: "area_path",
      label: t("settings.routes.wizard.col.area"),
      sortable: true,
      cell: (row) => row.area_path ?? "—",
    },
    {
      key: "current_route",
      label: t("settings.routes.wizard.col.currentRoute"),
      // NOT sortable — see `meters` above.
      // BR-MET-074: the move badge. Scoped to the service being built, so an
      // electric-route member is NOT badged while a water route is being made —
      // that move will never happen.
      cell: (row) =>
        row.current_route === null ? (
          "—"
        ) : (
          <StatusPill tone="warning">
            {t("settings.routes.wizard.onRoute", { route: row.current_route })}
          </StatusPill>
        ),
    },
  ];

  const premisesTable: TableConfig<RoutePickerPremises> = {
    // Its own preference key, so the clerk's column set here is not the one
    // SET-05's landing table stores.
    screenId: "SET-06.2",
    columns: premisesColumns,
    getRowId: (row) => row.id,
    // Declaring `searchFields` is what renders the kit's search box, and
    // `searchPlaceholder` is B14 rule 19 — this list says WHAT it matches
    // instead of "Search this list".
    searchFields: ["premise_no", "address_line"],
    searchPlaceholder: "settings.routes.wizard.searchPlaceholder",
    defaultSort: { sort: "premise_no", dir: "asc" },
  };

  // ⚠ `sortPickerRows` + `pageSlice` STOOD HERE AND BOTH ARE GONE
  // (`DEF-MET-5743`). The server sorts and slices; sorting a page of fifty in
  // the browser would order the page and not the list, which is a table whose
  // first row is not the first row.

  const stepTwo = (
    <div className="flex flex-col gap-2.5">
      <h2 className="m-0 mt-2 mb-1 text-panel" data-rcw="title">
        {t("settings.routes.wizard.step2Title")}
      </h2>
      <p className={RC_DESC}>{t("settings.routes.wizard.step2Lede")}</p>

      <DataTable<RoutePickerPremises>
        config={premisesTable}
        state={tableState}
        onStateChange={(next) => {
          // Search, sort, page AND page size all drive the SERVER query now
          // (`DEF-MET-5743`). A change to anything but the page returns to page
          // 1: the result set changed, so the old page number means nothing.
          const changedTheSet =
            next.q !== tableState.q || next.sort !== tableState.sort || next.dir !== tableState.dir;
          setSearch(next.q);
          setTableState(changedTheSet ? { ...next, page: 1 } : next);
        }}
        rows={rows}
        totalRows={matching}
        loading={picker.isPending}
        error={
          picker.isError ? { onRetry: () => void picker.refetch() } : null
        }
        empty={{
          title: t("settings.routes.wizard.pickerEmptyTitle"),
          helper: t("settings.routes.wizard.pickerEmptyBody"),
        }}
        filterBarSlot={
          /* ⚠ **`appliedAreas`, NOT `areaChips`** (`DEF-TEN-5843`). The chip row
             has to show the filter that is ACTUALLY ON — otherwise the clerk
             sees 40 rows of 40,000 with an empty filter bar above them and no
             way to tell why. The derived default renders as an ordinary
             REMOVABLE chip precisely so it is visible and reversible: it is a
             default, not a lock.
             The chip also says the area's NAME and not its code — `Area:
             NORTH-NW` explains nothing to a clerk reading `North district · NW`
             in the row beneath it. One string for one concept, which is
             `areaFilterOptions`' own rule. */
          <PickerFilterChips
            areaOptions={areaOptions.map((area) => ({
              value: area.code,
              label: area.parent_name ? `${String(area.parent_name)} · ${area.name}` : area.name,
            }))}
            areas={appliedAreas}
            onAreas={applyAreaFilter}
            unassigned={{
              on: unassignedOnly,
              onChange: (next) => {
                setUnassignedOnly(next);
                setTableState((current) => ({ ...current, page: 1 }));
              },
              label: t("settings.routes.wizard.filterUnassigned"),
              removeLabel: t("settings.routes.wizard.removeUnassignedFilter"),
            }}
            allLabel={t("settings.routes.wizard.filterAll")}
            addLabel={t("settings.routes.wizard.addFilter")}
            areaChipLabel={(code) =>
              t("settings.routes.wizard.areaChip", { area: areaLabelFor(code) })
            }
            removeAreaLabel={(code) =>
              t("settings.routes.wizard.removeAreaFilter", { area: areaLabelFor(code) })
            }
          />
        }
      />

      {/* The bulk bar and the running count — the two behaviours the shared
          table does not own (bulk selection is a later kit packet, per
          `DataTable`'s own header). They sit BELOW the table so the toolbar
          stays B14 rule 12's one bounded row. */}
      <div
        className="flex flex-wrap items-center gap-3 bg-[color-mix(in_srgb,var(--color-accent)_6%,transparent)] px-3 py-2 text-base"
        data-rcw="selectall"
      >
        {/* ⚠ **`Select all {n}` MEANS EVERY MATCHING ROW, SO IT ASKS FOR THEM**
            (`DEF-MET-5743`). It read `rows.map(...)` — which was every premises
            in the tenant while the browser held them all, and is ONE PAGE now.
            Left as it was, a button labelled "Select all 9,412" would have
            selected fifty and reported success: the exact silent truncation
            this lane was told not to introduce, on the control that builds a
            route over a whole area.

            It is ONE deliberate request on an explicit act, not a walk of every
            page — and the label states the number first, so nobody presses it
            without seeing what they are asking for. */}
        <Button
          variant="secondary"
          size="sm"
          disabled={props.readOnly || selectingAll}
          title={readOnlyTitle}
          onClick={() => {
            void selectEveryMatch();
          }}
        >
          {t("settings.routes.wizard.selectAllMatching", { count: matching })}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={props.readOnly}
          title={readOnlyTitle}
          onClick={() => setSelected(new Map())}
        >
          {t("settings.routes.wizard.clearSelection")}
        </Button>
        <span className="ml-auto text-base" data-rcw="count">
          {/* DEF-224: "1 selected" and not "1 selected" over a plural noun —
              `pluralKey` branches in CODE rather than through i18next's
              language-specific `_one`/`_other` suffixes, which would make the
              catalogues' key sets differ and turn G15 red. */}
          <b>
            {t(pluralKey("settings.routes.wizard.selectedCount", totals.premises), {
              count: totals.premises,
            })}
          </b>{" "}
          {t("settings.routes.wizard.unitsCount", { count: totals.units })}
        </span>
      </div>

      {/* BR-MET-074 — a CONSEQUENCE, which B14 rule 33 allows on screen at six
          words a sentence. It is the one sentence on this step that is not
          rationale: picking a premises MOVES it off the route it is on. */}
      <p className={RC_DESC}>{t("settings.routes.wizard.moveNote")}</p>
    </div>
  );

  const stepThree = (
    <div className="flex flex-col gap-2.5">
      <h2 className="m-0 mt-2 mb-1 text-panel" data-rcw="title">
        {t("settings.routes.wizard.step3Title")}
      </h2>
      <p className={RC_DESC}>{t("settings.routes.wizard.step3Lede")}</p>
      <div className="grid max-w-[640px] grid-cols-3 gap-3 max-sm:grid-cols-1" data-rcw="stats">
        <div className="border border-divider bg-surface p-3 text-center">
          <span className="block font-heading text-metric leading-body font-extrabold [font-feature-settings:'tnum'] [&_small]:text-base [&_small]:font-normal">
            {totals.premises}
          </span>
          <span className="text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            {t("settings.routes.wizard.stat.premises")}
          </span>
        </div>
        <div className="border border-divider bg-surface p-3 text-center">
          <span className="block font-heading text-metric leading-body font-extrabold [font-feature-settings:'tnum'] [&_small]:text-base [&_small]:font-normal">
            {totals.units}
          </span>
          <span className="text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            {t("settings.routes.wizard.stat.units")}
          </span>
        </div>
        <div className="border border-divider bg-surface p-3 text-center">
          {/* BR-MET-075: BOTH halves — "151 of 153" — so an exclusion is
              never invisible. */}
          <span className="block font-heading text-metric leading-body font-extrabold [font-feature-settings:'tnum'] [&_small]:text-base [&_small]:font-normal">
            {includedMeters}
            <small>{t("settings.routes.wizard.ofTotal", { total: meterRows.length })}</small>
          </span>
          <span className="text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            {t("settings.routes.wizard.stat.meters")}
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table
          className="w-full border-collapse text-table [&_th]:border-b [&_th]:border-b-divider [&_th]:px-2 [&_th]:py-1.5 [&_th]:text-left [&_td]:border-b [&_td]:border-b-divider [&_td]:px-2 [&_td]:py-1.5 [&_td]:text-left [&_th]:font-heading [&_th]:text-table-header [&_th]:font-semibold [&_th]:uppercase [&_th]:tracking-table-header [&_th]:text-[color-mix(in_srgb,var(--color-text)_60%,transparent)] [&_.cell-num]:text-right"
          data-rcw="table"
        >
          <caption className="absolute h-px w-px overflow-hidden whitespace-nowrap [clip:rect(0_0_0_0)]">
            {t("settings.routes.wizard.step3Title")}
          </caption>
          <thead>
            <tr>
              <th scope="col" className="w-7" />
              <th scope="col">{t("settings.routes.wizard.col.meter")}</th>
              <th scope="col">{t("settings.routes.wizard.col.premise")}</th>
              <th scope="col">{t("settings.routes.wizard.col.service")}</th>
              <th scope="col">{t("settings.routes.wizard.col.size")}</th>
              <th scope="col">{t("settings.routes.wizard.col.readMethod")}</th>
            </tr>
          </thead>
          <tbody>
            {pageSlice(meterRows, meterPage, meterPer).map((meter) => (
              <tr
                key={meter.id}
                className={
                  excluded.has(meter.id)
                    ? "bg-[color-mix(in_srgb,var(--color-accent)_5%,transparent)]"
                    : undefined
                }
              >
                <td className="w-7">
                  <input
                    type="checkbox"
                    checked={!excluded.has(meter.id)}
                    disabled={props.readOnly}
                    title={readOnlyTitle}
                    aria-label={t("settings.routes.wizard.includeMeter", {
                      meter: meter.asset_no ?? meter.id,
                    })}
                    onChange={(event) => {
                      const next = new Set(excluded);
                      if (event.target.checked) {
                        next.delete(meter.id);
                      } else {
                        next.add(meter.id);
                      }
                      setExcluded(next);
                    }}
                  />
                </td>
                <td>
                  <b>{meter.asset_no ?? "—"}</b>
                </td>
                <td>{meter.address_line}</td>
                <td>{meter.service_code ?? "—"}</td>
                <td>{sizeClassName(meter.size_class, sizeNames) ?? "—"}</td>
                <td>{meter.read_method ?? "—"}</td>
              </tr>
            ))}
            {/* ── `CR-131-BRC07` step 6 · A FAILURE SAYS SO ────────────────
                ⚠ **THIS TABLE DREW ITS EMPTY STATE OVER A REJECTED REQUEST.**
                *"No meters yet… Or none have meters fitted"* is TRUE of a
                route of unmetered properties and FALSE of a fetch that never
                came back, and the two were the same picture — which is why a
                clerk with 726 units saw a blank table and no reason, and is
                the false ABSENCE this repository keeps filing defects about.
                Three states now, and they are distinguishable: still loading ·
                could not ask · genuinely nothing there. */}
            {meterRows.length === 0 && meters.isPending && (
              <tr>
                <td colSpan={6} className="px-2 py-6 text-center">
                  <b>{t("settings.routes.wizard.metersLoading")}</b>
                </td>
              </tr>
            )}
            {meterRows.length === 0 && meters.isError && (
              <tr>
                <td colSpan={6} className="px-2 py-6 text-center [&_p]:mx-auto [&_p]:mt-1 [&_p]:max-w-none">
                  <b data-rcw="meters-failed">{t("settings.routes.wizard.metersFailedTitle")}</b>
                  <p className="m-0 max-w-measure text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                    {apiErrorText(meters.error, translate)}
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void meters.refetch()}
                  >
                    {t("settings.routes.wizard.metersRetry")}
                  </Button>
                </td>
              </tr>
            )}
            {meterRows.length === 0 && meters.isSuccess && (
              <tr>
                <td colSpan={6} className="px-2 py-6 text-center [&_p]:mx-auto [&_p]:mt-1 [&_p]:max-w-none">
                  <b>{t("settings.routes.wizard.metersEmptyTitle")}</b>
                  <p className="m-0 max-w-measure text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                    {t("settings.routes.wizard.metersEmptyBody")}
                  </p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {/* B14 rule 16 — DEF-223's second missing footer. */}
      <ListPager
        total={meterRows.length}
        page={meterPage}
        per={meterPer}
        onPage={setMeterPage}
        onPer={(value) => {
          setMeterPer(value);
          setMeterPage(1);
        }}
      />
      {(meters.data?.premises_without_meter ?? 0) > 0 && (
        <ConsequenceBox
          tone="check"
          title={t("settings.routes.wizard.noMeterTitle", {
            count: meters.data?.premises_without_meter ?? 0,
          })}
          body={t("settings.routes.wizard.noMeterBody")}
        />
      )}
    </div>
  );

  const stepFour = (
    <div className="flex flex-col gap-2.5">
      <h2 className="m-0 mt-2 mb-1 text-panel" data-rcw="title">
        {t(
          editing ? "settings.routes.wizard.step4TitleEdit" : "settings.routes.wizard.step4Title",
          {
            code: code || "—",
          },
        )}
      </h2>
      <div
        className="flex max-w-[640px] flex-col gap-3 border border-divider bg-surface p-3.5"
        data-rcw="summary"
      >
        <dl className="m-0 flex flex-col gap-1.5 text-base [&>div]:flex [&>div]:items-center [&>div]:justify-between [&>div]:gap-3 [&_dd]:m-0 [&_dt]:m-0">
          <div>
            <dt>{t("settings.routes.wizard.summary.route")}</dt>
            <dd>
              <b>
                {code} · {name || "—"}
              </b>
            </dd>
          </div>
          <div>
            <dt>{t("settings.routes.wizard.summary.readType")}</dt>
            <dd>
              <b>{t(`settings.routes.wizard.type.${routeType}`)}</b>
            </dd>
          </div>
          <div>
            <dt>{t("settings.routes.wizard.summary.service")}</dt>
            <dd>
              <b>{serviceCode === "" ? t("settings.routes.wizard.serviceAll") : serviceCode}</b>
            </dd>
          </div>
          <div>
            <dt>{t("settings.routes.wizard.summary.members")}</dt>
            <dd>
              <b className="[font-feature-settings:'tnum']">
                {totals.premises} · {totals.units}
              </b>
            </dd>
          </div>
          <div>
            <dt>{t("settings.routes.wizard.summary.meters")}</dt>
            <dd>
              <b className="[font-feature-settings:'tnum']">
                {t("settings.routes.wizard.metersWithExclusions", {
                  count: includedMeters,
                  excluded: excluded.size,
                })}
              </b>
            </dd>
          </div>
          <div>
            <dt>{t("settings.routes.wizard.summary.cycle")}</dt>
            <dd>
              <b>{props.route?.cycle_code ?? t("settings.routes.wizard.noCycle")}</b>
            </dd>
          </div>
        </dl>
      </div>

      {/* B14 rule 11 — the consequence, before the commit. */}
      {moves.map((move) => (
        <ConsequenceBox
          key={move.route}
          tone="move"
          title={t("settings.routes.wizard.moveTitle", {
            count: move.count,
            route: move.route,
          })}
          body={t("settings.routes.wizard.moveBody")}
        />
      ))}

      {/* BR-MET-081 — on an EDIT only. On a create there is nothing to take
          effect later, so saying so would be noise. */}
      {editing && props.route?.status === "active" && (
        <p className="m-0 max-w-measure text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)] font-semibold">
          {t("settings.routes.wizard.nextReadWindow")}
        </p>
      )}

      {/* BR-MET-076 — Draft or Activate, and this is the only place it is
          chosen. A draft stamps no service point, so Reads and Billing cannot
          see it. */}
      <fieldset className="flex max-w-[640px] items-center gap-[18px] border border-divider px-3 py-2.5">
        <legend className="text-sm font-semibold">{t("settings.routes.wizard.saveAs")}</legend>
        <label className="flex items-center gap-1.5 text-base">
          <input
            type="radio"
            name="route-lifecycle"
            checked={!activate}
            disabled={props.readOnly}
            onChange={() => setActivate(false)}
          />
          {t("settings.routes.wizard.saveDraft")}
        </label>
        <label className="flex items-center gap-1.5 text-base">
          <input
            type="radio"
            name="route-lifecycle"
            checked={activate}
            disabled={props.readOnly}
            onChange={() => setActivate(true)}
          />
          {t("settings.routes.wizard.activate")}
        </label>
      </fieldset>
      {commitError !== null && (
        <p className="m-0 text-sm text-danger-700" data-rcw="error" role="alert">
          {commitError}
        </p>
      )}
    </div>
  );

  return (
    <div className="flex max-w-[1060px] flex-col gap-3">
      {/* B14 rule 1 — a page header's ← names where it EXITS to; the stepper's
          own ← Back (inside WizardFrame) means only "previous step". */}
      <Button variant="ghost" className="self-start" onClick={props.onCancel}>
        {t("settings.routes.wizard.exit")}
      </Button>
      {/* B14 rule 2 — one shared page head: kicker, title. */}
      <header className="border-b-2 border-b-divider pb-[18px]">
        <Kicker>{t("settings.routes.wizard.headKicker")}</Kicker>
        <h1 className="m-0 mt-0.5 font-heading text-h3 font-extrabold" data-rcw="head-title">
          {t(editing ? "settings.routes.wizard.headEdit" : "settings.routes.wizard.headNew")}
        </h1>
      </header>
      <WizardFrame
        steps={[
          {
            id: "details",
            label: t("settings.routes.wizard.railDetails"),
            content: stepOne,
            validate: () => {
              const valid = name.trim().length > 0;
              setNameError(!valid);
              // CR-161-BRC10 W4 — a required own field is named before
              // Continue; the server's refusal stays the rule underneath.
              const missing = missingRequiredLabels(customRegistry.data ?? [], customData);
              setCustomMissing(missing);
              return valid && missing.length === 0;
            },
          },
          { id: "premises", label: t("settings.routes.wizard.railPremises"), content: stepTwo },
          { id: "meters", label: t("settings.routes.wizard.railMeters"), content: stepThree },
          { id: "review", label: t("settings.routes.wizard.railReview"), content: stepFour },
        ]}
        /* B14 rule 4 — `Verb ✓` commits. B14 rule 6 does NOT apply: creating
           or activating a route is not destructive, so it stays primary. */
        // DEF-222: the verb depends on BOTH facts. It used to swing only on
        // `activate`, so editing an existing row committed with "Create …✓"
        // directly under a step-4 title reading "Ready to save …" — two
        // sentences a person reads a second apart, disagreeing.
        commitLabel={t(
          editing
            ? activate
              ? "settings.routes.wizard.commitSave"
              : "settings.routes.wizard.commitSaveDraft"
            : activate
              ? "settings.routes.wizard.commitActivate"
              : "settings.routes.wizard.commitDraft",
        )}
        commitFailedTitle={t("settings.routes.wizard.commitFailed")}
        onCommit={runCommit}
        onCommitted={props.onCancel}
      />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// SET-07 · CYCLE WIZARD
// ═══════════════════════════════════════════════════════════════════════════

/**
 * ⚠ **THE `routes` PROP IS GONE (`DEF-MET-5743`).** The page above handed this
 * wizard EVERY route in the tenant — `getRoutes()`, which walks every page of
 * `/routes` at a thousand rows a time — and step 2 then searched, filtered,
 * sorted and sliced that array in the browser. The wizard asks for the page it
 * is drawing, and for the cycle's own routes when it is editing one.
 */
export function CycleWizard(props: WizardProps & { cycle: CycleRow | null }) {
  const { t, i18n } = useTranslation(); // i18n.language — DEF-224's ordinals
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const editing = props.cycle !== null;

  const [code, setCode] = useState(props.cycle?.code ?? "");
  const [name, setName] = useState(props.cycle?.name ?? "");
  const [frequency, setFrequency] = useState(props.cycle?.frequency ?? "monthly");
  const [nameError, setNameError] = useState(false);
  const [seeded, setSeeded] = useState(false);

  /**
   * ⚠ **A MAP, FOR THE REASON THE ROUTE WIZARD'S SELECTION IS ONE.** The totals
   * and the conflict badges below were read out of the whole-tenant array; with
   * one page in hand they have to be read out of the SELECTION, so the row
   * travels with the id. Seeded from ids alone when editing — `cycleRoutes`
   * below fills in their rows.
   */
  const [selected, setSelected] = useState<Map<string, RouteRow | null>>(
    new Map((props.cycle?.route_ids ?? []).map((id) => [id, null])),
  );
  const [routesSeeded, setRoutesSeeded] = useState(false);

  // ⚠ **THE RULED THREE FIELDS ABOUT TIME (B17 §2), AND THIS STEP DID NOT HAVE
  // THEM UNTIL W5-T2.** It wrote `read_day_from` / `read_day_to` / `due_day` —
  // three of the five columns metering 0021 dropped — so a cycle created
  // through the product carried no start day and no days-to-complete of its
  // own, and the server backfilled them from the pair. It worked, and the
  // screen the PO ruled did not exist. Held as strings because they are typed,
  // and validated before Continue.
  const [startDay, setStartDay] = useState(String(props.cycle?.start_day ?? ""));
  const [daysToComplete, setDaysToComplete] = useState(
    String(props.cycle?.days_to_complete ?? ""),
  );
  // D9 — the two DEFAULTS the cycle carries and the run may override. `dueDays`
  // is a COUNT of days after the bill date (BR-BIL-024), which is the fact
  // billing actually reads; the old `due_day` was a day-of-month that could
  // wrap and that nothing consumed.
  const [billDay, setBillDay] = useState(String(props.cycle?.bill_day ?? ""));
  const [dueDays, setDueDays] = useState(String(props.cycle?.due_days ?? ""));
  const [dayError, setDayError] = useState<string | null>(null);

  // OQ-340 — non-null ONLY when the cycle being edited has a stored start day
  // the engine ignores. A new cycle has no first run yet, so nothing is
  // decorative and nothing is said.
  const decorativeStartDay =
    props.cycle !== null && effectiveStartDay(props.cycle).decorative
      ? effectiveStartDay(props.cycle)
      : null;

  const [firstRun, setFirstRun] = useState(props.cycle?.first_run_date ?? "");
  const [activate, setActivate] = useState(props.cycle?.lifecycle_status !== "draft");
  const [commitError, setCommitError] = useState<string | null>(null);
  // The SET-07 step-2 picker's request state, on the shared table (DEF-223's
  // footer and DEF-TEN-5706's toolbar are both `DataTable`'s now). `routeSearch`
  // stays as the applied search term the row filter below reads.
  const [routeSearch, setRouteSearch] = useState("");
  const [onCycleOnly, setOnCycleOnly] = useState(false);
  /** True while `Select all {n}` is in flight — the button disables itself so
   *  two presses cannot race to two different selections (the route wizard's
   *  own reasoning, one screen along). */
  const [selectingAll, setSelectingAll] = useState(false);
  const [routeState, setRouteState] = useState<TableRequestState>({
    q: "",
    sort: "code",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });

  const nextCode = useQuery({
    queryKey: ["cycles", "next-code"],
    queryFn: () => getNextCycleCode(client),
    enabled: !editing,
  });
  if (!editing && !seeded && code === "" && nextCode.data?.code) {
    setCode(nextCode.data.code);
    setSeeded(true);
  }

  // DEF-218: TRUE while the code box still holds exactly what the server
  // previewed and the admin has not touched it. Compared against the PREVIEWED
  // VALUE rather than a "was seeded" boolean on purpose — a `seeded` flag stays
  // true after the admin edits the box, so it cannot tell an untouched pre-fill
  // from a code a human typed, and sending a human's code is the whole point of
  // keeping the field.
  const codeIsUntouchedPrefill =
    !editing && nextCode.data?.code !== undefined && code.trim() === nextCode.data.code;

  const coverage = useQuery({
    queryKey: ["cycles", "coverage", [...selected.keys()].sort().join(",")],
    queryFn: () => getCycleCoverage([...selected.keys()], client),
  });

  /** The cycle's OWN routes, when editing — bounded by the cycle, never by the
   *  tenant. It is what turns the seeded ids into rows the totals can add up. */
  const cycleRoutes = useQuery({
    queryKey: ["cycles", "routes", props.cycle?.id ?? null],
    queryFn: () => getCycleRoutes(props.cycle!.id, client),
    enabled: editing && props.cycle !== null,
  });
  if (editing && !routesSeeded && cycleRoutes.data) {
    setSelected(new Map(cycleRoutes.data.map((route) => [route.id, route])));
    setRoutesSeeded(true);
  }

  const totals = useMemo(() => {
    let members = 0;
    let meters = 0;
    for (const route of selected.values()) {
      // A seeded id whose row has not arrived adds nothing rather than a zero
      // that would read as "this route has no members".
      if (route !== null) {
        members += route.members;
        meters += route.meters;
      }
    }
    return { members, meters, routes: selected.size };
  }, [selected]);

  /* BR-MET-010 + CR-006: *"a route can belong to only one cycle per service —
     conflict badge + confirm-move"*. The badge is here; the MOVE is the
     server's, exactly as it is for premises on step 2 of the route wizard.
     ⚠ Read off the SELECTION since `DEF-MET-5743` — a route picked on page 1
     and warned about on page 1 must still be warned about on page 4. */
  const conflicts = [...selected.values()].filter(
    (route): route is RouteRow =>
      route !== null &&
      route.cycle_id !== null &&
      route.cycle_id !== (props.cycle?.id ?? null),
  );

  const preview = schedulePreview({ startDay, daysToComplete, bill: billDay, dueDays });

  const commit = useMutation({
    mutationFn: async () => {
      const payload: Record<string, unknown> = {
        // DEF-218 — same as the route wizard above: an untouched pre-fill is a
        // PREVIEW and is omitted so the server's series allocates.
        ...(codeIsUntouchedPrefill ? {} : { code: code.trim() }),
        name: name.trim(),
        frequency,
        status: activate ? "active" : "draft",
        route_ids: [...selected.keys()],
        // B17 §2's three fields about time (the third, frequency, is above),
        // and D9's two defaults. Nothing here names a dropped column.
        start_day: startDay === "" ? null : Number(startDay),
        days_to_complete: daysToComplete === "" ? null : Number(daysToComplete),
        bill_day: billDay === "" ? null : Number(billDay),
        due_days: dueDays === "" ? null : Number(dueDays),
        first_run_date: firstRun === "" ? null : firstRun,
      };
      return editing ? updateCycle(props.cycle!.id, payload, client) : createCycle(payload, client);
    },
  });

  async function runCommit(): Promise<WizardCommitOutcome> {
    try {
      const saved = await commit.mutateAsync();
      props.onDone(
        t(editing ? "settings.cycles.wizard.updated" : "settings.cycles.wizard.created", {
          code: saved.code,
          date: firstRun || "—",
        }),
      );
      return { ok: true };
    } catch (error: unknown) {
      const reason = apiErrorText(error, translate);
      setCommitError(reason);
      return { ok: false, reason };
    }
  }

  const readOnlyTitle = props.readOnly ? t("settings.readOnlyReason") : undefined;

  const stepOne = (
    <div className="flex flex-col gap-2.5">
      <h2 className="m-0 mt-2 mb-1 text-panel" data-rcw="title">
        {t("settings.cycles.wizard.step1Title")}
      </h2>
      {/* ⚠ **RULING 2 IS HONOURED BY WHAT THIS WIZARD STORES, NOT BY A
          PARAGRAPH EXPLAINING IT.** The lede here read *"A cycle is a group of
          routes — and through them, the premises, units and accounts billed
          together. You define the group here; the timing is confirmed when you
          actually run it"* — 32 words of RATIONALE, which B14 rule 33 (ratified
          2026-08-30, two weeks AFTER that ruling) puts at ZERO words on screen.
          The ruling itself is unchanged and is visible in the BUILD: four steps,
          day-of-month DEFAULTS rather than dates, and no money anywhere
          (BR-MET-078). `RoutesCyclesRulings.test.tsx` asserts those, which is
          the durable place for it — a sentence can be reworded, a stored column
          cannot. The full explanation still reaches a reader on the cycle
          DETAIL screen's `defaultsFootnote`, which DEF-606 owns. */}
      <div className="flex max-w-[640px] flex-col gap-3 border border-divider bg-surface p-3.5">
        <div className="grid grid-cols-[160px_1fr] gap-3 max-sm:grid-cols-1">
          <Field
            label={t("settings.cycles.wizard.code")}
            hint={t("settings.cycles.wizard.codeHint")}
          >
            <input
              className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text [font-feature-settings:'tnum']"
              data-rcw="code"
              value={code}
              disabled={props.readOnly}
              title={readOnlyTitle}
              onChange={(event) => setCode(event.target.value)}
            />
          </Field>
          <Field label={t("settings.cycles.wizard.name")} required>
            <input
              className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text"
              value={name}
              disabled={props.readOnly}
              title={readOnlyTitle}
              placeholder={t("settings.cycles.wizard.namePlaceholder")}
              aria-invalid={nameError || undefined}
              onChange={(event) => {
                setName(event.target.value);
                setNameError(false);
              }}
            />
          </Field>
        </div>
        {nameError && (
          <p className="m-0 text-sm text-danger-700" data-rcw="error" role="alert">
            {t("settings.cycles.wizard.nameRequired")}
          </p>
        )}
        <Field label={t("settings.cycles.wizard.frequency")} required>
          <select
            className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text max-w-[180px]"
            value={frequency}
            disabled={props.readOnly}
            title={readOnlyTitle}
            onChange={(event) => setFrequency(event.target.value)}
          >
            {CYCLE_FREQUENCIES.map((value) => (
              <option key={value} value={value}>
                {/* `frequencyKey` maps the word onto its catalogue entry, so the
                    option text here and the label on SET-05/SET-07D come from
                    ONE resolver. `settings.cycles.wizard.frequency.*` held only
                    the three CR-006 spellings and could not name the other
                    five. */}
                {t(frequencyKey(value) ?? "settings.cycles.wizard.frequency")}
              </option>
            ))}
          </select>
        </Field>
      </div>
    </div>
  );

  // DEF-223, measured in Chromium: this picker had *"no search, chips or
  // + Filter"* (B14 rule 12) while the SET-06 picker two steps away has all
  // three, and no pagination footer either (rule 16). A cycle picks from EVERY
  // route the tenant owns, so at 200 routes it was an unscrollable wall.
  //
  // ⚠ **THE SEARCH AND THE CHIP ARE THE SERVER'S FROM 2026-09-18
  // (`DEF-MET-5743`), AND THE NOTE THAT STOOD HERE WAS TRUE WHEN IT WAS
  // WRITTEN AND IS NOT NOW.** It read *"the search is CLIENT-SIDE and that is
  // honest here … `props.routes` is the WHOLE list, already in memory"* — and
  // it was honest, because the page had walked every route in the tenant into
  // that array. That is the walk this defect was filed for. With one page in
  // hand, a client-side filter would report "no routes match" about a route
  // sitting on page four, and the `on a cycle` chip would answer about fifty
  // rows while claiming to answer about the list.
  //
  // BR-MET-034 — the chip's own reason is unchanged: a route already on a
  // cycle is the row whose selection MOVES it, so being able to see only those
  // is the question the step asks, not decoration.
  const routePage = useQuery({
    queryKey: [
      "routes",
      "cycle-picker",
      routeSearch,
      onCycleOnly,
      routeState.sort,
      routeState.dir,
      routeState.page,
      routeState.per,
    ],
    queryFn: () =>
      getRoutesPage(
        {
          ...routeState,
          q: routeSearch.trim().length >= 2 ? routeSearch.trim() : "",
          filters: onCycleOnly ? { on_cycle: "1" } : {},
        },
        client,
      ),
    placeholderData: (previous) => previous,
  });
  const visibleRoutes = routePage.data?.rows ?? [];
  /** Every route the chip and the search match — what the footer and
   *  `Select all` state, and never the length of this page. */
  const matchingRoutes = routePage.data?.total ?? 0;

  /**
   * **`Select all {n}` — THE WHOLE MATCH SET, AND THIS STEP HAD NO SELECT-ALL
   * AT ALL** (`DEF-TEN-5840`, PO 2026-09-19: *"this is in premises/unit, route
   * and cycle creation context"*). Building a monthly cycle out of eighty
   * routes meant eighty clicks across two pages of fifty.
   *
   * ⚠ **IT WALKS PAGES, AND THE ROUTE WIZARD'S ONE-REQUEST VERSION IS NOT
   * COPYABLE HERE — THE TWO ENDPOINTS DIFFER AND ONLY ONE OF THEM SAYS SO.**
   * `GET /routes/premises-picker` carries NO maximum on `per` (its docstring
   * spells this out under `NFR-5`), so the route wizard omits `per` and is
   * answered with every matching row at once. `GET /routes` is an ordinary
   * `StandardPagination` list and `core.pagination.clamp_page_size` CLAMPS
   * `per` to 1,000 — silently, never as an error. So the obvious copy
   * (*"omit `per` and take what comes back"*) would have selected **fifty** —
   * the default page size — under a button labelled `Select all 3,412`, which
   * is precisely the data-loss trap the label exists to prevent.
   *
   * ⚠ **THE LOOP IS BOUNDED BY THE SERVER'S OWN `total`, NOT BY A GUESS.** It
   * stops when it holds them all or when a page comes back empty, so a total
   * that shifts under it terminates rather than spinning. A failure leaves the
   * selection UNTOUCHED rather than half-applied — a partially selected cycle
   * is a cycle that quietly loses routes on save.
   *
   * It is ONE deliberate act on an explicit press, and the label states the
   * number FIRST so nobody presses it without seeing what they are asking for.
   */
  async function selectEveryMatchingRoute(): Promise<void> {
    setSelectingAll(true);
    try {
      const collected = new Map<string, RouteRow>();
      for (let page = 1; ; page += 1) {
        const body = await getRoutesPage(
          {
            ...routeState,
            q: routeSearch.trim().length >= 2 ? routeSearch.trim() : "",
            filters: onCycleOnly ? { on_cycle: "1" } : {},
            page,
            per: SELECT_ALL_PER,
          },
          client,
        );
        for (const route of body.rows) {
          collected.set(route.id, route);
        }
        if (body.rows.length === 0 || collected.size >= (body.total ?? 0)) {
          break;
        }
      }
      setSelected(collected);
    } catch (error: unknown) {
      setCommitError(apiErrorText(error, translate));
    } finally {
      setSelectingAll(false);
    }
  }

  const routeColumns: TableColumnConfig<RouteRow>[] = [
    {
      key: "select",
      label: t("settings.cycles.wizard.col.select"),
      locked: true,
      cell: (route) => (
        <input
          type="checkbox"
          checked={selected.has(route.id)}
          disabled={props.readOnly}
          title={readOnlyTitle}
          aria-label={t("settings.cycles.wizard.selectRoute", { route: route.code })}
          onChange={(event) => {
            // The ROW goes in with the id — the totals and the conflict badges
            // read it back, and this is the only place that still has it.
            const next = new Map(selected);
            if (event.target.checked) {
              next.set(route.id, route);
            } else {
              next.delete(route.id);
            }
            setSelected(next);
          }}
        />
      ),
    },
    {
      key: "code",
      label: t("settings.routes.col.code"),
      sortable: true,
      identity: true,
      // B14 rule 31 — the ROUTE CODE is the human-facing reference. `route.id`
      // is never rendered.
      cell: (route) => <b>{route.code}</b>,
    },
    {
      key: "name",
      label: t("settings.routes.col.name"),
      sortable: true,
      cell: (route) => route.name ?? "—",
    },
    {
      key: "route_type",
      label: t("settings.routes.col.type"),
      sortable: true,
      cell: (route) =>
        route.route_type === null ? "—" : t(`settings.routes.wizard.type.${route.route_type}`),
    },
    { key: "members", label: t("settings.routes.col.members"), numeric: true, sortable: true },
    { key: "meters", label: t("settings.routes.col.meters"), numeric: true, sortable: true },
    {
      key: "cycle_code",
      label: t("settings.cycles.wizard.col.currentCycle"),
      sortable: true,
      cell: (route) =>
        route.cycle_code === null ? "—" : <StatusPill tone="warning">{route.cycle_code}</StatusPill>,
    },
  ];

  const routeTable: TableConfig<RouteRow> = {
    screenId: "SET-07.2",
    columns: routeColumns,
    getRowId: (route) => route.id,
    searchFields: ["code", "name"],
    searchPlaceholder: "settings.routes.searchPlaceholder",
    defaultSort: { sort: "code", dir: "asc" },
  };

  // ⚠ `sortPickerRows` + `pageSlice` STOOD HERE AND BOTH ARE GONE
  // (`DEF-MET-5743`). `/routes` sorts and slices — `ROUTE_SORTS` is its
  // vocabulary and it covers every column this table marks sortable.

  const stepTwo = (
    <div className="flex flex-col gap-2.5">
      <h2 className="m-0 mt-2 mb-1 text-panel" data-rcw="title">
        {t("settings.cycles.wizard.step2Title")}
      </h2>

      <DataTable<RouteRow>
        config={routeTable}
        state={routeState}
        onStateChange={(next) => {
          // Anything but a page change returns to page 1 — the result set
          // changed, so the old page number means nothing.
          const changedTheSet =
            next.q !== routeState.q || next.sort !== routeState.sort || next.dir !== routeState.dir;
          setRouteSearch(next.q);
          setRouteState(changedTheSet ? { ...next, page: 1 } : next);
        }}
        rows={visibleRoutes}
        totalRows={matchingRoutes}
        loading={routePage.isPending}
        empty={{
          title: t("settings.cycles.wizard.noRoutesTitle"),
          helper: t("settings.cycles.wizard.noRoutesBody"),
        }}
        filterBarSlot={
          <PickerFilterChips
            areaOptions={[]}
            areas={[]}
            onAreas={() => {
              /* a route carries no area — this dimension is absent here */
            }}
            unassigned={{
              on: onCycleOnly,
              onChange: (next) => {
                setOnCycleOnly(next);
                setRouteState((current) => ({ ...current, page: 1 }));
              },
              label: t("settings.cycles.wizard.filterOnCycle"),
              removeLabel: t("settings.cycles.wizard.removeOnCycleFilter"),
            }}
            allLabel={t("settings.routes.wizard.filterAll")}
            addLabel={t("settings.routes.wizard.addFilter")}
            areaChipLabel={(area) => area}
            removeAreaLabel={(area) => area}
          />
        }
      />

      {/* ── `DEF-TEN-5840` · THE BULK BAR THIS STEP NEVER HAD ────────────────
          The route wizard's step 2 has carried `Select all {n}` since CR-006;
          the cycle wizard's — the same shape of picker, over the same kind of
          list — has had only a running count. The PO scoped the gap in their
          own words on 2026-09-19: *"this is in premises/unit, route and cycle
          creation context"*.
          ⚠ **THE LABEL STATES THE COUNT OF EVERY MATCHING ROW, NEVER THE PAGE.**
          `matchingRoutes` is the server's total; `visibleRoutes.length` is
          fifty. A header checkbox ticking what is on screen, under a filter
          matching 3,412, is a clerk believing they selected 3,412 and acting on
          fifty — so the number on the button and the number the walk collects
          are the same number, deliberately.
          It sits BELOW the table so the toolbar stays B14 rule 12's one
          bounded row, exactly as the route wizard's does. */}
      <div
        className="flex flex-wrap items-center gap-3 bg-[color-mix(in_srgb,var(--color-accent)_6%,transparent)] px-3 py-2 text-base"
        data-rcw="selectall"
      >
        <Button
          variant="secondary"
          size="sm"
          disabled={props.readOnly || selectingAll}
          title={readOnlyTitle}
          onClick={() => {
            void selectEveryMatchingRoute();
          }}
        >
          {t("settings.routes.wizard.selectAllMatching", { count: matchingRoutes })}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={props.readOnly}
          title={readOnlyTitle}
          onClick={() => setSelected(new Map())}
        >
          {t("settings.routes.wizard.clearSelection")}
        </Button>
        {/* The running count — `DataTable` owns rows, not what a wizard has
            chosen from them. */}
        <span className="ml-auto text-base" data-rcw="count">
          <b>
            {t(pluralKey("settings.cycles.wizard.routesSelected", totals.routes), {
              count: totals.routes,
            })}
          </b>{" "}
          {t("settings.cycles.wizard.membersMeters", {
            members: totals.members,
            meters: totals.meters,
          })}
        </span>
      </div>
      {conflicts.length > 0 && (
        <ConsequenceBox
          tone="move"
          title={t("settings.cycles.wizard.conflictTitle", { count: conflicts.length })}
          body={t("settings.cycles.wizard.conflictBody", {
            routes: conflicts
              .map((route) => `${route.code} (${route.cycle_code ?? "—"})`)
              .join(", "),
          })}
        />
      )}
    </div>
  );

  const stepThree = (
    <div className="flex flex-col gap-2.5">
      <h2 className="m-0 mt-2 mb-1 text-panel" data-rcw="title">
        {t("settings.cycles.wizard.step3Title")}
      </h2>
      {/*
        RULING 3 — *"you can capture the defaults , but allow suer to override it
        during actual run"*. What is stored here is a NORMAL SHAPE, not a
        commitment: the run prefills from it and the staff member may change it
        there, for that run only.

        ⚠ **THIS LEDE WAS 44 WORDS AND IS NOW SIX.** It carried two things and
        only one of them was the ruling. The ruling's half survives on screen as
        a FACT — *"Defaults only. Each run can change them."* — because B14 rule
        33 caps a fact at six words and this is one. The other half was
        `DEF-607`'s repair, which separated the two DAY-OF-MONTH fields from the
        two COUNTS in prose; that fact belongs to the FIELDS and has moved to
        their own hints, where rule 32 puts it (*a row never repeats what its own
        control offers*, and the converse: the control is where its own fact
        goes). `Days to complete` had no hint at all before this, which is why
        the distinction had to be made in a paragraph in the first place.
      */}
      <p className={RC_DESC}>{t("settings.cycles.wizard.step3Lede")}</p>
      <div className="flex max-w-[640px] flex-col gap-3 border border-divider bg-surface p-3.5">
        <div className="grid grid-cols-2 gap-3 max-sm:grid-cols-1">
          {/* B17 §2's first two fields about time. START DAY is a day-of-month
              for Monthly and slower; DAYS TO COMPLETE is a length, not a day,
              which is why it carries no 1–31 hint. */}
          <Field
            label={t("settings.cycles.col.startDay")}
            hint={t("settings.cycles.wizard.dayHint")}
          >
            <input
              className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text max-w-[180px] [font-feature-settings:'tnum']"
              inputMode="numeric"
              value={startDay}
              disabled={props.readOnly}
              title={readOnlyTitle}
              onChange={(event) => {
                setStartDay(event.target.value);
                setDayError(null);
              }}
            />
            {/* ⚠ **OQ-340 SAID SO ON THE SCREEN WHERE THE FIELD IS TYPED.**
                PO, verbatim: *"A: first window 15–17 Sep (start day becomes
                decorative)"*. On a cycle whose first run disagrees with this
                box, typing a new number here changes NOTHING the product does
                — the first run is the anchor. A form control that quietly does
                not work is worse than one that is missing, so the box stays
                editable (the value is the operator's, and a later first run on
                that day will use it) and says what it is doing. Served, never
                derived here. */}
            {decorativeStartDay !== null && (
              <p className={`${RC_DESC} mt-1`} role="note" data-rcw="start-day-decorative">
                {t("settings.cycles.wizard.startDayDecorative", {
                  effective: decorativeStartDay.day,
                  stored: decorativeStartDay.stored,
                })}
              </p>
            )}
          </Field>
          {/* DEF-607's fact, now on the field it is about: this box is a COUNT
              of days, not a day of the month like the two beside it. It had no
              hint at all, which is why the 44-word lede above had to say so. */}
          <Field
            label={t("settings.cycles.col.daysToComplete")}
            hint={t("settings.cycles.wizard.countHint")}
          >
            <input
              className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text max-w-[180px] [font-feature-settings:'tnum']"
              inputMode="numeric"
              value={daysToComplete}
              disabled={props.readOnly}
              title={readOnlyTitle}
              onChange={(event) => {
                setDaysToComplete(event.target.value);
                setDayError(null);
              }}
            />
          </Field>
          <Field
            label={t("settings.cycles.wizard.billDay")}
            hint={t("settings.cycles.wizard.dayHint")}
          >
            <input
              className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text max-w-[180px] [font-feature-settings:'tnum']"
              inputMode="numeric"
              value={billDay}
              disabled={props.readOnly}
              title={readOnlyTitle}
              onChange={(event) => {
                setBillDay(event.target.value);
                setDayError(null);
              }}
            />
          </Field>
          {/* ⚠ DUE **DAYS**, NOT A DUE DAY (W5-T2). This box wrote
              `cycles.due_day`, a day-of-month that could wrap into the next
              month and that nothing consumed; the fact billing reads is
              `due_days` — a COUNT added to the bill date (BR-BIL-024) — which
              is also what S31 step 1 overrides per run under D9. The old
              column is dropped (metering 0021). */}
          <Field
            label={t("billing.run.field.dueDays")}
            hint={t("billing.run.field.dueDaysHelp")}
          >
            <input
              className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text max-w-[180px] [font-feature-settings:'tnum']"
              inputMode="numeric"
              value={dueDays}
              disabled={props.readOnly}
              title={readOnlyTitle}
              onChange={(event) => {
                setDueDays(event.target.value);
                setDayError(null);
              }}
            />
          </Field>
        </div>
        {dayError !== null && (
          <p className="m-0 text-sm text-danger-700" data-rcw="error" role="alert">
            {dayError}
          </p>
        )}
        {/*
          THE PREVIEW STOPS AT `due`. r10's own string ends "· late fee 31st";
          ruling 1 removed it, and it is not derived from Billing defaults
          either — a fee date rendered here reads as this screen's field
          however it was sourced (BR-MET-078).
        */}
        {preview !== null && (
          <div
            className="border border-divider bg-bg px-3.5 py-3 text-base leading-sample"
            data-rcw="preview"
          >
            <b>{t("settings.cycles.wizard.previewTitle")}</b>
            <p className="[font-feature-settings:'tnum']">
              {t("settings.cycles.wizard.previewBody", {
                readFrom: preview.readFrom,
                readTo: preview.readTo,
                // DEF-224: ordinals, per r10 — "5th", not "5".
                exceptionsBy: ordinalDay(Number(preview.exceptionsBy), i18n.language, t),
                bill: ordinalDay(Number(preview.bill), i18n.language, t),
                due: ordinalDay(Number(preview.due), i18n.language, t),
              })}
              {preview.wraps ? ` ${t("settings.cycles.wizard.previewWraps")}` : ""}
            </p>
          </div>
        )}
      </div>
    </div>
  );

  const stepFour = (
    <div className="flex flex-col gap-2.5">
      <h2 className="m-0 mt-2 mb-1 text-panel" data-rcw="title">
        {t(
          editing ? "settings.cycles.wizard.step4TitleEdit" : "settings.cycles.wizard.step4Title",
          { code: code || "—" },
        )}
      </h2>
      <div
        className="flex max-w-[640px] flex-col gap-3 border border-divider bg-surface p-3.5"
        data-rcw="summary"
      >
        <dl className="m-0 flex flex-col gap-1.5 text-base [&>div]:flex [&>div]:items-center [&>div]:justify-between [&>div]:gap-3 [&_dd]:m-0 [&_dt]:m-0">
          <div>
            <dt>{t("settings.cycles.wizard.summary.cycle")}</dt>
            <dd>
              <b>
                {code} · {name || "—"}
              </b>
            </dd>
          </div>
          <div>
            <dt>{t("settings.cycles.wizard.summary.frequency")}</dt>
            <dd>
              <b>{t(`settings.cycles.wizard.frequency.${frequency}`)}</b>
            </dd>
          </div>
          <div>
            <dt>{t("settings.cycles.wizard.summary.routes")}</dt>
            <dd>
              <b className="[font-feature-settings:'tnum']">
                {t(pluralKey("settings.cycles.wizard.routesMembers", totals.routes), {
                  routes: totals.routes,
                  members: totals.members,
                })}
              </b>
            </dd>
          </div>
          <div>
            <dt>{t("settings.cycles.wizard.summary.schedule")}</dt>
            <dd>
              <b className="[font-feature-settings:'tnum']">
                {preview === null
                  ? t("settings.cycles.wizard.noDefaults")
                  : t("settings.cycles.wizard.summaryScheduleValue", {
                      readFrom: preview.readFrom,
                      readTo: preview.readTo,
                      bill: preview.bill,
                      due: preview.due,
                    })}
              </b>
            </dd>
          </div>
          <div>
            <dt>{t("settings.cycles.wizard.summary.firstRun")}</dt>
            <dd>
              {/* B14 rule 7 — a DATE field uses the date input, never a bare
                  text box. The day-of-month DEFAULTS above are not dates and
                  correctly are not date inputs. */}
              <input
                type="date"
                className="min-h-8 border border-field-border bg-bg px-2 py-1.5 text-text max-w-[180px]"
                value={firstRun}
                disabled={props.readOnly}
                title={readOnlyTitle}
                aria-label={t("settings.cycles.wizard.summary.firstRun")}
                onChange={(event) => setFirstRun(event.target.value)}
              />
            </dd>
          </div>
        </dl>
      </div>

      {/* BR-MET-080 — a real query, computed INCLUDING the routes picked on
          step 2, because the number that matters is what will still be
          unscheduled AFTER this is created. */}
      {(coverage.data?.uncovered_accounts ?? 0) > 0 && (
        <ConsequenceBox
          tone="check"
          title={t("settings.cycles.wizard.uncoveredTitle", {
            count: coverage.data?.uncovered_accounts ?? 0,
          })}
          body={t("settings.cycles.wizard.uncoveredBody")}
        />
      )}

      {/* r10 SET-07.4's footer — the same immutability promise hard rule 4
          makes about issued invoices. */}
      <p className="m-0 max-w-measure text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
        {t("settings.cycles.wizard.firstRunNote")}
      </p>
      {editing && props.cycle?.lifecycle_status === "active" && (
        <p className="m-0 max-w-measure text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)] font-semibold">
          {t("settings.cycles.wizard.nextReadWindow")}
        </p>
      )}

      <fieldset className="flex max-w-[640px] items-center gap-[18px] border border-divider px-3 py-2.5">
        <legend className="text-sm font-semibold">{t("settings.cycles.wizard.saveAs")}</legend>
        <label className="flex items-center gap-1.5 text-base">
          <input
            type="radio"
            name="cycle-lifecycle"
            checked={!activate}
            disabled={props.readOnly}
            onChange={() => setActivate(false)}
          />
          {t("settings.cycles.wizard.saveDraft")}
        </label>
        <label className="flex items-center gap-1.5 text-base">
          <input
            type="radio"
            name="cycle-lifecycle"
            checked={activate}
            disabled={props.readOnly}
            onChange={() => setActivate(true)}
          />
          {t("settings.cycles.wizard.activate")}
        </label>
      </fieldset>
      <p className="m-0 max-w-measure text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
        {t("settings.cycles.wizard.auditNote")}
      </p>
      {commitError !== null && (
        <p className="m-0 text-sm text-danger-700" data-rcw="error" role="alert">
          {commitError}
        </p>
      )}
    </div>
  );

  return (
    <div className="flex max-w-[1060px] flex-col gap-3">
      <Button variant="ghost" className="self-start" onClick={props.onCancel}>
        {t("settings.cycles.wizard.exit")}
      </Button>
      <header className="border-b-2 border-b-divider pb-[18px]">
        <Kicker>{t("settings.cycles.wizard.headKicker")}</Kicker>
        <h1 className="m-0 mt-0.5 font-heading text-h3 font-extrabold" data-rcw="head-title">
          {t(editing ? "settings.cycles.wizard.headEdit" : "settings.cycles.wizard.headNew")}
        </h1>
      </header>
      <WizardFrame
        steps={[
          {
            id: "details",
            label: t("settings.cycles.wizard.railDetails"),
            content: stepOne,
            validate: () => {
              const valid = name.trim().length > 0;
              setNameError(!valid);
              return valid;
            },
          },
          { id: "routes", label: t("settings.cycles.wizard.railRoutes"), content: stepTwo },
          {
            id: "schedule",
            label: t("settings.cycles.wizard.railSchedule"),
            content: stepThree,
            validate: () => {
              // ⚠ THE GATE MOVED WITH THE FIELDS (W5-T2). Three of the four
              // boxes it checked are gone, and the two survivors are not the
              // same KIND of number: `startDay` and `billDay` are days of the
              // month (1–31), `daysToComplete` is a LENGTH (≥ 1) and `dueDays`
              // is a COUNT (≥ 0 — zero means due on the bill date, which
              // BR-MET-009 allows and a 1–31 check would have refused).
              const filled = [startDay, daysToComplete, billDay, dueDays].filter(
                (value) => value !== "",
              );
              if (filled.length === 0) {
                return true; // defaults are optional — a cycle may carry none
              }
              if (![startDay, billDay].filter((value) => value !== "").every(isDayOfMonth)) {
                setDayError(t("settings.cycles.wizard.dayRange"));
                return false;
              }
              if (daysToComplete !== "" && !(Number(daysToComplete) >= 1)) {
                setDayError(t("settings.cycles.wizard.readOrder"));
                return false;
              }
              if (dueDays !== "" && !(Number(dueDays) >= 0)) {
                setDayError(t("metering.cycle.due_days_range"));
                return false;
              }
              // BR-MET-077's surviving comparison, in the server's own terms:
              // the bill day may not fall before the day the derived window
              // CLOSES (`start_day + days_to_complete - 1`, clamped at 31).
              if (startDay !== "" && daysToComplete !== "" && billDay !== "") {
                const close = Math.min(31, Number(startDay) + Number(daysToComplete) - 1);
                if (Number(billDay) < close) {
                  setDayError(t("settings.cycles.wizard.billOrder"));
                  return false;
                }
              }
              return true;
            },
          },
          { id: "review", label: t("settings.cycles.wizard.railReview"), content: stepFour },
        ]}
        // DEF-222: the verb depends on BOTH facts. It used to swing only on
        // `activate`, so editing an existing row committed with "Create …✓"
        // directly under a step-4 title reading "Ready to save …" — two
        // sentences a person reads a second apart, disagreeing.
        commitLabel={t(
          editing
            ? activate
              ? "settings.cycles.wizard.commitSave"
              : "settings.cycles.wizard.commitSaveDraft"
            : activate
              ? "settings.cycles.wizard.commitActivate"
              : "settings.cycles.wizard.commitDraft",
        )}
        commitFailedTitle={t("settings.cycles.wizard.commitFailed")}
        onCommit={runCommit}
        onCommitted={props.onCancel}
      />
    </div>
  );
}
