// ── Trace ──────────────────────────────────────────────
// Story:    US-AST-001 (S49 registry — tabs, filters, per-state row actions) ·
//           US-AST-004 (S50 header — all three classifications)
//           Screens: S49, S50, S51, S52, S53, S54, S55
// Rules:    BR-AST-004 (tabs partition by type CATEGORY — every asset on exactly one) ·
//           BR-AST-005 (status-filter semantics; Unassigned = no current assignment) ·
//           BR-AST-006 (row actions vary by state — the SERVER computes the set) ·
//           BR-AST-007 ("Test due" is DERIVED, never a stored status) ·
//           BR-AST-026 (three identifiers; the internal uuid is NEVER displayed) ·
//           BR-AST-031 (lifecycle stages are Reference data with a behavior class) ·
//           BR-AST-043 (meter_types and read_methods are two catalogs) ·
//           BR-AST-044 (an asset carries BOTH classifications plus read method; all three
//           show on the detail view and both are filterable; meter_type is UNAVAILABLE on
//           non-measuring types and the server REFUSES it)
// ───────────────────────────────────────────────────────
// The pieces S49–S55 share.
//
// The rule this file exists to make unbreakable is BR-AST-006: the action set
// is the SERVER's `actions` array, computed from the stage's behavior class.
// Nothing here re-derives "can I retire this?" from a status string — a tenant
// that renamed "Needs repair" would break every such guess, which is exactly
// why BR-AST-031 put a behavior class under the label in the first place.
//
// The second is BR-AST-026: `asset_no` is the identity a user reads, `serial_no`
// is the physical one, and the uuid is addressing only. No component below ever
// renders `id`.
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";

import type {
  AssetBillingChain,
  AssetBtmKpis,
  AssetDetail,
  AssetMetersKpis,
  AssetRow,
  AssetTab,
} from "@/api/endpoints";
import { getLookupEntries } from "@/api/endpoints";
import { AgeCell } from "@/components/AgeCell";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { SelectField } from "@/components/FormModal";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import type { Translator } from "@/features/tenancy/settingsShared";
import { ageBetween } from "@/lib/age";

// ── Routes ─────────────────────────────────────────────────────────────────
// BR-SHL-001 gives the sidebar an `assets` section at `/assets`; the detail
// hangs off it so the breadcrumb and the active-nav highlight keep working.

export const ASSETS_ROUTE = "/assets";

export function assetDetailPath(assetId: string): string {
  return `${ASSETS_ROUTE}/${encodeURIComponent(assetId)}`;
}

// ── CR-028 AST-W4: the four lifecycle flows are FULL-PAGE SCREENS, not modals
// (PO 2026-08-22, B16 §5.2 as amended: "as per r10 - it is not modal").
// AST-05 add wizard · AST-06 reassign · AST-07 log repair/test · AST-08 retire.
// `?class=` carries the registry tab into the add wizard so "+ Add sub-meter"
// opens on the right asset class — the same URL-state discipline as `?tab=`.

export function assetNewPath(tab?: AssetTab): string {
  return tab === undefined ? `${ASSETS_ROUTE}/new` : `${ASSETS_ROUTE}/new?class=${tab}`;
}

export function assetReassignPath(assetId: string): string {
  return `${assetDetailPath(assetId)}/reassign`;
}

export function assetMaintenanceNewPath(assetId: string): string {
  return `${assetDetailPath(assetId)}/maintenance/new`;
}

export function assetRetirePath(assetId: string): string {
  return `${assetDetailPath(assetId)}/retire`;
}

// ── `AST-B-12` — EDIT IS A FULL PAGE AT ITS OWN ADDRESS, NOT A DIALOG ──────
// PO instruction 2026-09-11, verbatim: "this should be form and not modal."
// It puts the fifth surface in line with the four above, which stopped being
// dialogs on 2026-08-22 for the same reason ("as per r10 - it is not modal").
//
// ⚠ **THE ADDRESS IS THE CAPABILITY, NOT A CONSEQUENCE OF IT.** A dialog could
// only ever be opened by pressing a pencil in a registry row, so a correction
// could not be linked to, bookmarked, sent to a colleague or returned to after
// a refresh. That is what CR-092's `AST-B-12` asks for in its own words — "at
// an address they can come back to" — and it is why this helper exists rather
// than the page being reached by a piece of local state.

export function assetEditPath(assetId: string): string {
  return `${assetDetailPath(assetId)}/edit`;
}

// ── Tabs (BR-AST-004) ──────────────────────────────────────────────────────

export const ASSET_TAB_IDS: readonly AssetTab[] = ["meters", "sub_meters", "behind_the_meter"];

/**
 * BR-AST-009/BR-AST-044: "measuring" is a property of the type's CATEGORY, not
 * a hardcoded list of type codes — a tenant-added meter type lands on the
 * meters tab and is measuring for exactly the same reason the seeded ones are.
 * meter_type, service and an explicit UoM apply here and nowhere else.
 */
export const MEASURING_TABS: readonly AssetTab[] = ["meters", "sub_meters"];

export function isMeasuringCategory(category: string | null | undefined): boolean {
  return category !== null && category !== undefined
    ? (MEASURING_TABS as readonly string[]).includes(category)
    : false;
}

/**
 * Does an asset in this class, declaring this service, stand ON a service
 * connection — so that a CONNECTION SIZE is a fact about it?
 * **BR-AST-530 judgment 4 as AMENDED 2026-09-01 (`DEF-2414`).**
 *
 * ⚠ **IT LIVES HERE, IN ONE PLACE, BECAUSE JUDGMENT 4 ASKED FOR THAT IN
 * TERMS** — *"held in FOUR places that cannot drift: the add wizard's control,
 * its payload builder, the edit form's control and its payload builder"*. Four
 * copies of `=== "meters"` could not drift while the rule was one word long;
 * the moment it grew a second clause they could, so the four call this instead.
 *
 * **The boundary is POSITION, which is the reason judgment 4 itself gave:** a
 * sub-meter *"sits BEHIND a service connection rather than on one"* and is
 * still excluded. What changed is that the original wording said METERS and
 * the original reason said ON A CONNECTION, and a **trash cart** is on one — it
 * is the equipment the connection IS. PO 2026-09-01: *"we will ahve to set in
 * seeder as well as in setting the sizes also on Units"*, confirmed the same
 * day as *"this is correct - The size stays on the equipment record, not on the
 * unit itself."*
 *
 * **A DECLARED SERVICE is what distinguishes the two kinds of device.** A cart
 * declares `service: trash`; a backflow preventer, an EV charger and a comms
 * endpoint declare none (`BR-AST-009` — a non-measuring device belongs to a
 * customer, not to a connection), so they are offered nothing and their payload
 * carries nothing. Testing the TYPE instead would hardcode `container_cart` and
 * answer wrongly for the next non-measuring thing that stands on a connection —
 * storm water's and broadband's equipment, both `capacity` services under the
 * PO ruling of 2026-09-01 (`DEF-2409`).
 */
export function offersConnectionSize(
  category: string | null | undefined,
  service: string | null | undefined,
): boolean {
  if (isMeasuringCategory(category)) {
    return category === "meters";
  }
  return (service ?? "").trim() !== "";
}

/**
 * ⛔ **THE SIZES OF THIS ASSET'S OWN SERVICE — plan U4/U10 (PO 2026-09-30).**
 * The upload now refuses a size from another service's list
 * (`AST.SIZE_FOR_SERVICE`: *"W-58 is a size for Water, not for Trash."*), so
 * the add and edit screens offer the same set the upload accepts: active rows
 * tagged to THIS service, plus untagged rows (`service_scope_filter`'s rule —
 * an untagged size is *"nobody has said"* and lists everywhere). With no
 * service chosen yet, every active size is offered, as before.
 */
export function sizeOptionsForService(
  rows: readonly { code: string; name: string; active: boolean; service?: { code: string } | null }[],
  service: string | null | undefined,
): { value: string; label: string }[] {
  const chosen = (service ?? "").trim();
  return rows
    .filter((row) => row.active)
    .filter((row) => chosen === "" || !row.service || row.service.code === chosen)
    .map((row) => ({ value: row.code, label: row.name }));
}

// ── The connection size, as ONE control (BR-AST-500 · DEF-AST-7660) ────────

/** One request per tenant for "which services price by size band". */
export const sizeBandedServicesQueryKey = ["assets", "size-banded-services"] as const;

/** The tenant's ratified size classes, code → name. Shared with the registry's
 *  own picker and with the unit tab's SIZE column, so no two screens can name
 *  one size differently (`DEF-MET-6926`). */
export const assetSizeClassesQueryKey = ["lookups", "service_size_classes"] as const;

/**
 * **THE TENANT'S SIZE CATALOGUE, CODE → NAME** (`DEF-RAT-9321`) — one cached
 * request every screen that prints a connection size shares.
 *
 * ⚠ **A SIZE CODE IS AN INTERNAL KEY AND NEVER THE VISIBLE VALUE** (B14 rule
 * 31's spirit, rule 33). The PO, on Ottumwa's `BASE-W-FIRE` at 2.455.0: *"sizes
 * should be user friendly language - youa re showing internal codes"* — the
 * charge code's Size picker listed `W-58, W-34, W-1 …` where a clerk reads
 * `Water 5/8"`. The code stays what is STORED and POSTED; only the words move.
 * Inactive rows are kept on purpose: a size Settings retired still names the
 * meter or price that already carries it (`BR-AST-500`).
 */
export function useSizeClassNames(client?: ApiClient, enabled = true): ReadonlyMap<string, string> {
  const query = useQuery({
    queryKey: assetSizeClassesQueryKey,
    queryFn: () => getLookupEntries("service_size_classes", { per: 200 }, client),
    enabled,
    staleTime: 5 * 60 * 1000,
  });
  return new Map((query.data?.results ?? []).map((entry) => [entry.code, entry.name]));
}

/** A stored size code as a clerk reads it: the tenant's NAME. `null` for no
 *  size; a code the catalogue no longer holds keeps its stored text rather
 *  than going blank (the unit page's rule, `DEF-MET-6926`). */
export function sizeClassName(
  code: string | null | undefined,
  names: ReadonlyMap<string, string>,
): string | null {
  if (code === null || code === undefined || code === "") return null;
  return names.get(code) ?? code;
}

/**
 * **IS A CONNECTION SIZE REQUIRED FOR THIS SERVICE?** — `DEF-AST-7660`.
 *
 * ⚠ **THE ANSWER IS THE SERVER'S AND IS NEVER DERIVED HERE.** *"The tenant has
 * size classes for this service, so it must band"* is `DEF-3098`'s retired
 * proxy: it stopped being true when `CR-062` gave solar, battery, storm water
 * and broadband a CATALOGUE of installable equipment, and a screen asking it
 * would refuse a solar install over a size that service does not have. All
 * this does is read the list the server already sent.
 *
 * ⚠ **THREE ANSWERS, NOT TWO.** `false` for a service ruled not to band, and
 * `false` for one whose bands were never ruled — but the
 * two are different facts and only the first one means *blank is lawful*. A
 * screen must not claim the second is optional; it must simply not require it,
 * which is what returning `false` does and what the placeholder's silence says.
 * `false` while the answer is still loading, for the same reason: a field that
 * flickers into `required` is worse than one that never claimed to be.
 */
export function sizeRequiredForService(
  answer: { banded: string[] } | undefined,
  serviceCode: string,
): boolean {
  if (answer === undefined || serviceCode === "") {
    return false;
  }
  return answer.banded.includes(serviceCode);
}

/**
 * **THE CONNECTION SIZE PICKER — ONE COMPONENT, NOT A FOURTH COPY OF A
 * `<SelectField>`** (B14 rule 43: a piece of UI is built as a COMPONENT;
 * standalone code inside a page is not reuse).
 *
 * ⚠ **IT IS HERE BECAUSE `DEF-AST-7661` COUNTED THREE ASSIGN FORMS THAT ALREADY
 * DISAGREE.** The add wizard asks for the size and the service; the AST-06
 * reassign page asks for neither; the unit tab's `+ Assign from inventory`
 * panel asked for the service alone, which is `DEF-AST-7660` — the Product
 * Owner's own report. Handing the next of those a control it can import is the
 * only part of that disagreement this lane is entitled to fix.
 *
 * ⚠ **THE OPTION LIST IS THE TENANT'S ACTIVE SIZE CLASSES AND IS NOT NARROWED
 * BY SERVICE.** `BR-TEN-078` — the list is NOT service-scoped and the row names
 * its service in its own display name (`Water 5/8"`, `Electric 1φ 100A`), so
 * `W-58` on an electric meter is a DATA error a person can see rather than a
 * shape the screen forbids. The two doors `DEF-1900` built filter on `active`
 * and nothing else, and a third door narrowing differently would be the drift
 * `offersConnectionSize` exists to prevent.
 *
 * ⚠ **NO `help` LINE WHEN IT IS REQUIRED.** B14 rule 33 puts RATIONALE — *why
 * this meter needs a size and the last one did not* — at ZERO words on screen.
 * The server's refusal says what to do, and the reason lives in
 * `services._guard_declared_size`'s docstring, which is what a docstring is for.
 */
export function ConnectionSizeField(props: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  sizeClasses: readonly { code: string; name: string; active: boolean }[];
  required: boolean;
  error?: string;
  t: Translator;
}) {
  const { t } = props;
  return (
    <SelectField
      id={props.id}
      label={t("assets.col.sizeClass")}
      value={props.value}
      placeholder={t("assets.form.sizeClassPlaceholder")}
      options={props.sizeClasses
        .filter((entry) => entry.active)
        .map((entry) => ({ value: entry.code, label: entry.name }))}
      onChange={props.onChange}
      required={props.required}
      error={props.error}
    />
  );
}

// ── Status filter vocabulary (BR-AST-005) ──────────────────────────────────
// "all" includes retired · "unassigned" = no CURRENT assignment row · the
// remaining values are stage CODES the tenant's own Reference-data list owns,
// so the option list is BUILT FROM that list, never from a constant here.

export const STATUS_FILTER_ALL = "all";
export const STATUS_FILTER_UNASSIGNED = "unassigned";
/** CR-028 AST-W5: the Inventory drill's reserved value — behavior CLASS
 *  `available` server-side (BR-AST-031: the class, never a stage label), so
 *  the stock line's link survives a tenant who renamed their stages. */
export const STATUS_FILTER_UNINSTALLED = "uninstalled";

// ── Row actions (BR-AST-006) ───────────────────────────────────────────────

export type AssetAction = "view" | "edit" | "assign" | "reassign" | "log_repair" | "retire" | "delete";

/** The SERVER's own answer for "what may be done to this row, in this state". */
export function hasAction(row: AssetRow, action: AssetAction): boolean {
  return row.actions.includes(action);
}

/**
 * BR-AST-006: a backflow device's repair action is labelled "Log test" — the
 * prototype's own wording. The ACTION is identical; only the copy differs.
 *
 * CR-028 AST-W2 (B16 §5.1b (A)): the rule generalised — ANY non-measuring
 * device with a test cadence logs tests, not repairs. `has_test_cadence` is
 * the SERVER's fact (interval or explicit certification due); backflow stays
 * named so a payload predating the field keeps r10's wording.
 */
export function repairActionKey(row: AssetRow): string {
  const testingDevice =
    row.type === "backflow" ||
    (row.tab === "behind_the_meter" && row.has_test_cadence === true);
  return testingDevice ? "assets.action.logTest" : "assets.action.logRepair";
}

/** BR-AST-031: the tone follows the BEHAVIOR CLASS, never the tenant's label. */
export function behaviorTone(behaviorClass: string): StatusTone {
  if (behaviorClass === "in_service") {
    return "success";
  }
  if (behaviorClass === "out_of_service") {
    return "warning";
  }
  if (behaviorClass === "terminal") {
    return "danger";
  }
  return "neutral"; // available (Inventory/Spare) and any tenant-added class
}

// ── Display pieces ─────────────────────────────────────────────────────────

/**
 * The status pill plus BR-AST-007's derived "Test due" chip. The chip is a
 * DISPLAY state computed server-side from last_test_date + interval; the stored
 * status is untouched, which is why both render side by side.
 */
export function AssetStatusCell(props: { row: AssetRow; t: Translator }) {
  const { row, t } = props;
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <StatusPill tone={behaviorTone(row.behavior_class)}>{row.status_name}</StatusPill>
      {row.test_due && (
        <span
          className="border border-warning-500 px-1 text-xs uppercase tracking-label text-warning-700"
          // CR-018 Route B: `.ast-chip` was the handle AssetRegistry.test.tsx
          // reached for; a class that is now a utility string cannot be one.
          data-asset-chip="test-due"
          title={t("assets.testDueHelp")}
        >
          {t("assets.testDue")}
        </span>
      )}
    </span>
  );
}

/**
 * The registry's AGE cell (`DEF-AST-10178`, PO ruling 2026-10-17 *"this is all
 * corect"*) — the shared `AgeCell`, never a copy of it (PO: *"use same code
 * components"*; B14 rule 43). The server says where the age starts
 * (`age_start`: install → purchase → record) and where it stops (`age_end`,
 * the retire date); this only picks the note and the tone.
 *
 * ⚠ **THE END IS THE PAGE'S `today` WHEN THE ASSET IS NOT RETIRED**, never the
 * cell's own clock: the page already holds the tenant's today (and a test or a
 * walk pins it), so the age and every other date on the screen are one day.
 *
 * *Past life* is age ≥ `expected_life_years`, counted in whole years — the
 * same comparison the download's `past_life` makes.
 */
export function AssetAgeCell(props: {
  row: AssetRow;
  today: string;
  timeZone: string;
  t: Translator;
}) {
  const { row, today, timeZone, t } = props;
  if (row.age_start === undefined || row.age_start === "") return <AssetDash />;
  const end = row.age_end ?? today;
  const age = ageBetween(row.age_start, end, timeZone);
  const life = row.expected_life_years ?? null;
  const pastLife = age !== null && life !== null && life > 0 && age.years >= life;
  const from =
    row.age_start_source === "purchase"
      ? t("assets.age.fromPurchase")
      : row.age_start_source === "record"
        ? t("assets.age.fromRecord")
        : null;
  const notes = [pastLife ? t("assets.age.pastLife") : null, from].filter(
    (note): note is string => note !== null,
  );
  return (
    <AgeCell
      start={row.age_start}
      end={end}
      timeZone={timeZone}
      note={notes.length > 0 ? notes.join(" · ") : undefined}
      tone={pastLife ? "danger" : undefined}
    />
  );
}

/** A value the server did not send. Visibly quieter than data, never blank. */
export function AssetDash() {
  return <span className="italic text-[color-mix(in_srgb,var(--color-text)_45%,transparent)]">—</span>;
}

// ── CR-028 AST-W1 — the r10 registry's display pieces (B16 §4.1–§4.3, §4.8) ─

/**
 * "10.000000" → "10" · "1.5000" → "1.5" · "24.0000" → "24".
 *
 * DISPLAY trimming only (the deployed registry printed `1.000000` where r10
 * draws `×1` — B16 §4.8's measured drift): the value itself stays the served
 * decimal string everywhere it travels, and nothing here parses it to a float.
 */
export function trimDecimalZeros(value: string): string {
  if (!/^-?\d+\.\d+$/.test(value)) {
    return value; // integers and anything malformed pass through verbatim
  }
  return value.replace(/0+$/, "").replace(/\.$/, "");
}

/**
 * The Role column's three states (r10 AST-01): a sub names its master, a
 * master carries the accent tag with its SERVED child count (`sub_count` —
 * never a client-side guess), everything else is Standard.
 */
export type AssetRole =
  | { kind: "sub"; parent: string }
  | { kind: "master"; count: number }
  | { kind: "standard" };

export function roleOf(row: AssetRow): AssetRole {
  if (row.parent_asset_no !== null) {
    return { kind: "sub", parent: row.parent_asset_no };
  }
  const children = row.sub_count ?? 0;
  if (children > 0) {
    return { kind: "master", count: children };
  }
  return { kind: "standard" };
}

/**
 * ── The KPI strips' honesty gate (B16 T1) ──────────────────────────────────
 *
 * The list payload serves NO registry-wide aggregate, so the only numbers the
 * strip may show are ones counted over the COMPLETE tab population: page 1,
 * no search, no user filter, and every row of the result set loaded. Anything
 * less and a card would present a page's count as the utility's — so it shows
 * the quiet dash instead (`data-kpi-absent`), never an invented number.
 */
export function kpiRowsComplete(
  state: { q: string; page: number; filters: Record<string, string> },
  rowCount: number,
  totalRows: number | null,
): boolean {
  return (
    state.q.trim() === "" &&
    Object.keys(state.filters).length === 0 &&
    state.page === 1 &&
    totalRows !== null &&
    rowCount >= totalRows
  );
}

export interface MetersKpis {
  inService: number | null;
  masters: number | null;
  subs: number | null;
  amiPct: number | null;
  needsRepair: number | null;
  inInventory: number | null;
  pastCertification: number | null;
}

/** r10's four Meters cards (BR-AST-031: every count keys off the behavior
 *  CLASS, never the tenant's stage label).
 *
 *  ⚠ **THE SERVED FIGURES WIN, AND THE CLIENT COUNT IS NOW THE FALLBACK
 *  (`DEF-MET-4953`, PO ruling 2026-09-12 "a) Fix the figures").** The count
 *  below was only ever allowed to render over a COMPLETE result set, so a
 *  tenant with more meters than fit one page — and every filtered view at any
 *  page size — met four em-dashes under four headings. Measured on
 *  `pine-hill`: 110 meters, 50 to a page, four dashes on load.
 *
 *  The gate was right and the read was missing; `GET /assets` now carries
 *  `kpis` for this tab. The client arithmetic stays because an older answer
 *  (or a tab whose payload predates this) must still be able to show the
 *  truth it can see rather than nothing at all. */
export function metersKpis(
  rows: readonly AssetRow[],
  complete: boolean,
  served?: AssetMetersKpis,
): MetersKpis {
  if (served !== undefined) {
    return {
      inService: served.in_service,
      masters: served.masters,
      subs: served.subs,
      amiPct: served.ami_pct,
      needsRepair: served.needs_repair,
      inInventory: served.in_inventory,
      pastCertification: served.past_certification,
    };
  }
  if (!complete) {
    return {
      inService: null,
      masters: null,
      subs: null,
      amiPct: null,
      needsRepair: null,
      inInventory: null,
      pastCertification: null,
    };
  }
  const inService = rows.filter((row) => row.behavior_class === "in_service");
  const ami = inService.filter((row) => row.meter_type === "ami").length;
  return {
    inService: inService.length,
    masters: rows.filter((row) => (row.sub_count ?? 0) > 0).length,
    // Each sub bills its own unit (BR-AST-003), so the served child counts sum
    // to the sub population without loading the other tab.
    subs: rows.reduce((sum, row) => sum + (row.sub_count ?? 0), 0),
    amiPct: inService.length === 0 ? null : Math.round((100 * ami) / inService.length),
    needsRepair: rows.filter((row) => row.behavior_class === "out_of_service").length,
    inInventory: rows.filter((row) => row.behavior_class === "available").length,
    pastCertification: rows.filter((row) => row.test_due).length, // BR-AST-007 derived
  };
}

export interface BtmKpis {
  devices: number | null;
  exporting: number | null;
}

/** r10's BTM strip under the D2 ruling: three cards, no credited dollars, no
 *  tariff. The exported-kWh card's VALUE stays absent — no channel quantity is
 *  served on the list payload, and a number is never invented (BR-AST-025
 *  allows the quantity; the read that would carry it is not on this payload). */
export function btmKpis(
  rows: readonly AssetRow[],
  complete: boolean,
  served?: AssetBtmKpis,
): BtmKpis {
  // `DEF-MET-4953` — as `metersKpis` above: the served pair wins and the
  // client count remains the fallback. The third card was already served.
  if (served !== undefined) {
    return { devices: served.devices, exporting: served.exporting };
  }
  if (!complete) {
    return { devices: null, exporting: null };
  }
  return {
    devices: rows.length,
    exporting: rows.filter(
      (row) => row.export_capacity_kw !== null && row.export_capacity_kw !== undefined,
    ).length,
  };
}

/**
 * The S50 header sub-line: service · multiplier · installed · assigned to.
 * Returns the PARTS, so the caller composes them with its own separators and
 * no sentence is string-built for translation (B8/TD-16).
 */
export function headerFacts(row: AssetRow): { unit: string | null; multiplier: string } {
  return { unit: row.unit, multiplier: row.multiplier };
}

// ── THE ASSET CONTEXT LINE — ONE IMPLEMENTATION, EVERY ASSET HEADER ───────
//
// ⚠ **IT WAS WRITTEN TWICE UNTIL THIS COMMIT, AND THE TWO COPIES HAD ALREADY
// DRIFTED — HARD-WON LAW 5 IN ITS PUREST FORM.** `AssetDetailPage` composed it
// inline inside its render function; `AssetFlowPages.assetContextParts`
// composed it again for Reassign, Log repair and the three Retire steps. The
// second copy's own docstring said so and asked for exactly this move:
// *"a change to either must be made to both, and this comment is the only
// thing saying so."* A comment is not the guarantee (law 1) — by the time it
// was read the two disagreed in four places, one of which blanked a screen:
//
//   1 · **`billing_chain` was defended on the flows and NOT on the detail
//       page.** Measured in a browser on 2026-09-13, on a payload with the
//       field removed at the wire: the three flow screens rendered their line
//       normally and the detail page rendered *"Unexpected Application Error!
//       Cannot read properties of undefined (reading 'premises_id')"* — no
//       header, no tabs, no panels. `AssetDetail` declares the field REQUIRED
//       so `tsc` cannot see the gap, and a payload written before
//       `BR-AST-039`'s chain was served arrives without one.
//   2 · the SERVICE word was resolved by a named helper on one side and by an
//       inline `t()` on the other — the same key namespace typed twice, which
//       is the shape `DEF-763` already cost once;
//   3 · the account leg filtered its two fields by TRUTHINESS on one side and
//       by an explicit null/empty test on the other (same output for
//       `string | null`, and only by luck);
//   4 · the service leg's own null test was `!= null` on one side and
//       `!== null && !== undefined` on the other.
//
// **THE DRAWING, READ AS AN IMAGE (B14 rule 42).** Page 35 figure 10 (detail)
// and page 88 figure 31 (reassign) draw the SAME line, which is why one
// implementation is not merely tidier but the only thing that can be right:
//
//     118 Bayou Bend Dr · Unit A · ACC-20194 Ruth Alvarez · Water · Installed Feb 2024
//     118 Bayou Bend Dr · Unit 1 · ACC-20194 Ruth Alvarez · Water · Installed Jan 2026
//
// Order: **address · unit · account · service · installed**. Page 36's header
// rule 1 states it in words — *"the place line leading with the address and
// carrying the account … and the multiplier gone from it, because a ×1 is
// configuration rather than identity"*. The multiplier belongs to the
// Measurement panel and the words *assigned to* are on neither figure.
// Rule 37: the drawn address, unit and account number are ILLUSTRATIONS —
// what is specified is the ORDER and which facts appear.

/**
 * A chain with every leg empty — what to read when the payload carries NO
 * `billing_chain` at all.
 *
 * ⚠ **IT IS A NAMED CONSTANT BECAUSE THE FIELD IS READ IN MORE THAN ONE
 * PLACE, AND THE SECOND READ WAS STILL UNGUARDED ON 2026-09-13.** Defending
 * the context line alone moved the detail page's crash rather than curing it:
 * measured in a browser on a payload with the field deleted at the wire, the
 * error went from *"Cannot read properties of undefined (reading
 * `premises_id`)"* — the header — to *"…(reading `account`)"* — the Assignment
 * panel, further down the same screen. Same blank page, different line. A
 * second copy of the object literal would have been the same drift this whole
 * section exists to end, so there is one.
 *
 * **Nothing downstream needs a special case for it**: the panel already draws
 * *Inventory (unassigned)* for a null premises and a dash for a null unit and
 * account, which is `AST-R-03`'s stated absence and is the honest answer for a
 * payload that never carried a chain.
 */
export const EMPTY_BILLING_CHAIN: AssetBillingChain = {
  premises_id: null,
  premise_no: null,
  premise_address: null,
  unit_id: null,
  unit_label: null,
  account: null,
};

/**
 * The legs of the asset context line, in the drawn order, as PARTS — so the
 * separator is written in exactly one place (`AssetContextLine` below) and no
 * sentence is string-built for translation.
 *
 * ⚠ **THE INVENTORY TEST IS `assigned`, NOT "IS THERE AN ADDRESS", AND AN
 * EARLIER DRAFT GOT IT WRONG.** `assigned_address` is the REGISTRY ROW's copy
 * of a walk that may be STALE: a payload can carry `assigned: false` with
 * `premises_id: null` and still hold the last address the thing was at, so an
 * address-first fallback drew a battery sitting in a warehouse at *1408 Elm
 * Street*. `AssetDetail.test.tsx`'s BATTERY fixture carries exactly that pair
 * on purpose, and it is what found it — not the browser walk, which happened
 * to land on an asset whose stale copy was null.
 */
function assetContextParts(
  asset: AssetDetail,
  t: Translator,
  regional: { timeZone: string; dateFormat: RegionalDateFormat },
): ReactNode[] {
  const parts: ReactNode[] = [];
  /**
   * ⚠ **DEFAULTED, BECAUSE A MISSING `billing_chain` TOOK A WHOLE SCREEN
   * DOWN** — see fault 1 above. On a flow the header is the frame around the
   * form, so a header that throws takes the form with it and the person gets
   * a blank page instead of a reassign; on the detail page it takes the tabs
   * and every panel with it. Found by `AssetWizardExit.dom`, which
   * mounts the retire wizard on exactly such a payload, and reproduced in a
   * browser on both surfaces before this was moved.
   */
  const chain = asset.billing_chain ?? EMPTY_BILLING_CHAIN;
  if (asset.tab === "sub_meters" && asset.parent_asset_no !== null) {
    // A sub-meter's MASTER leads — figure 11's *"Sub of E-5000 · 118 Bayou
    // Bend Dr · …"*. It is the fact that places the thing, so it sits where
    // the address sits on every other kind.
    parts.push(t("assets.detail.subOf", { parent: asset.parent_asset_no }));
  }
  const inInventory = chain.premises_id === null && !asset.assigned;
  if (inInventory) {
    // The drawing's own sentence for stock (page 36, `AST-04412`) — an honest
    // absence rather than the four dashes a chain of empty legs would draw.
    parts.push(t("assets.detail.inInventory"));
  } else {
    // Hard rule 8: the address is WALKED TO, never stored here. The LIVE chain
    // answers first; `assigned_address` is the registry row's copy of the same
    // walk and `parent_premises` is the master's, for a payload that carries
    // one and not the other.
    const placeAddress =
      chain.premise_address ?? asset.assigned_address ?? asset.parent_premises ?? null;
    if (placeAddress != null) {
      parts.push(placeAddress);
    }
    const placeUnit = chain.unit_label ?? asset.assigned_to ?? null;
    if (placeUnit != null && placeUnit !== placeAddress) {
      parts.push(placeUnit);
    }
    if (chain.account !== null) {
      // Plain text, NOT a link: the Assignment panel's own row is the link,
      // and the same destination said twice in one screen is `AST-R-09`.
      parts.push(
        [chain.account.account_no, chain.account.customer_name]
          .filter((part): part is string => part !== null && part !== "")
          .join(" "),
      );
    }
  }
  if (asset.service !== null && asset.service !== undefined) {
    parts.push(serviceLabel(asset.service, t));
  }
  if (asset.install_date !== null) {
    parts.push(
      <>
        {t("assets.detail.installed")}{" "}
        {/* BR-SHL-034: even a header date goes through the ONE formatter —
            r10's month-year density via the shared monthYear prop. */}
        <DateCell
          value={asset.install_date}
          timeZone={regional.timeZone}
          dateFormat={regional.dateFormat}
          monthYear
        />
      </>,
    );
  }
  return parts;
}

/**
 * ONE label per service code product-wide — and `rating.service.*` is that one
 * (`DEF-763`). It read `metering.service.*`, which holds six of the eleven
 * platform codes, so an asset on Storm water, Solar, Thermal/Heat or Battery
 * showed a clerk `storm_water`. Nothing broke and no gate fired: the
 * `defaultValue` below is exactly what hid it — which is also why this lives
 * here rather than being typed out a third time.
 */
export function serviceLabel(service: string, t: Translator): string {
  return t(`rating.service.${service}`, { defaultValue: service });
}

/**
 * The asset context line, rendered — the legs joined by ` · `.
 *
 * ⚠ **THE JOIN MOVED WITH THE PARTS ON PURPOSE.** A separator written on two
 * screens is the same drift risk one layer down, and it is the half a reader
 * would not think to check. Each screen keeps its own wrapper and its own
 * attention strip — the flows suppress the strip on Reassign's confirm panel
 * (fig 32) and the detail page never does — but the LINE itself is this.
 */
export function AssetContextLine(props: {
  asset: AssetDetail;
  t: Translator;
  regional: { timeZone: string; dateFormat: RegionalDateFormat };
}): ReactNode {
  const parts = assetContextParts(props.asset, props.t, props.regional);
  return (
    <>
      {parts.map((part, index) => (
        // A static, order-stable join — the index IS the identity here.
        <span key={index}>
          {index > 0 && " · "}
          {part}
        </span>
      ))}
    </>
  );
}

/**
 * The register a read belongs to, in words — `DEF-MET-4969`.
 *
 * ⚠ **THE VOCABULARY ALREADY SHIPPED, IN ALL ELEVEN CATALOGUES.**
 * `metering.reads.channel.*` holds all seven codes — `total` → *Total
 * register*, `tou_on` → *On-peak*, `demand` → *Demand* — and six files in the
 * neighbouring module already resolve it. The asset's Reads tab printed
 * `tou_on` and `tou_mid` to a clerk while asserting, in a lifecycle comment,
 * that *"no signed vocabulary maps a register to a display word"*. That is
 * hard-won law 1 in its quietest form: a claim about an ABSENCE, written where
 * it reads as a decision rather than as something that went stale.
 *
 * ⚠ **IT LIVES HERE AND NOT ON EITHER SCREEN, BECAUSE THERE ARE TWO** — the
 * read log in `AssetDetailPage` and the register panels in `AssetUsageStrip`,
 * and the second imports nothing from the first (the first mounts it, so the
 * other direction is a cycle). A word resolved twice is a word that disagrees
 * with itself the first time a catalogue changes.
 *
 * The `defaultValue` is the code, so an eighth register a future migration
 * adds shows something rather than a blank cell — a fallback, not the design.
 */
export function channelLabel(channel: string | null, t: Translator): string | null {
  if (channel === null || channel === "") {
    return null;
  }
  return t(`metering.reads.channel.${channel}`, { defaultValue: channel });
}

/** The one place that turns a translation function into the shared shape. */
export function useTranslator(): Translator {
  const { t } = useTranslation();
  return (key, params) => t(key, params);
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AST-001@566072b (story+rules snapshot hash — EP-AST-01 registry story; co-packets EP-AST-02@9f23548 · EP-AST-03@e1a4db0 · EP-AST-04@5be132f)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-22 by the CR-028 AST-W1 lane (B16 §4.1–§4.3: trimDecimalZeros for r10's ×1/×10 display, roleOf for the Role column, and the KPI helpers — metersKpis/btmKpis count ONLY over a complete unfiltered result set (kpiRowsComplete), else every card shows the quiet dash; no aggregate is served and none is invented) · AMENDED 2026-08-22 by the CR-028 AST-W2 lane (repairActionKey generalised per B16 §5.1b (A): any BTM device whose served has_test_cadence is true logs tests; backflow stays named for pre-field payloads) · AMENDED 2026-08-22 by the CR-028 AST-W4 lane (the four full-page flow paths — assetNewPath/assetReassignPath/assetMaintenanceNewPath/assetRetirePath; ClassificationBlock DELETED — dead since W2 folded the classifications into Specifications, and G40 counted it: 2 unmounted against a baseline of 1, back to 1 with this cut) · AMENDED 2026-08-22 by the CR-028 AST-W5 lane (STATUS_FILTER_UNINSTALLED — the Inventory drill's reserved behavior-class value)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ — 296+83 was the pre-W1 baseline and a CONCURRENT Plans & Rates lane is adding to the same suite; this packet contributes 103 passing + 28 todo across 7 files and reduced nothing. The 28 todos are browser-interaction, server/RLS-isolation and unbuilt-neighbour-lane scope, each named in its own test
// exceptions: E4 "measuring" is derived from the type's CATEGORY (the tab partition BR-AST-004 defines) rather than from the server's own `MEASURING_TYPES` code set, which no endpoint exposes — the two agree for every seeded type, and the category is what a tenant-added type carries
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
