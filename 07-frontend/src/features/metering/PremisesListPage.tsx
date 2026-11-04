// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-001 (S14 Premises list tab — roll-up, capability row, row actions)
//           Screens: S14 (entered from the AppShell sidebar → Premises)
// Rules:    BR-MET-001 (a premise is tenant-scoped with an auto premise number; IS-1
//           deactivate-first) · BR-MET-003 (services shown ⊆ the tenant's enabled set) ·
//           BR-MET-034 (premises types are Reference data — the filter's options are the
//           tenant's list, never a hardcoded enum) · BR-MET-035 (roles: create/edit =
//           System Admin + Billing Clerk, deactivate/delete = System Admin) ·
//           BR-MET-037 (Delete only at zero units — otherwise the server refuses and
//           offers Deactivate) · BR-MET-047 (deactivation blockers are NAMED) ·
//           BR-MET-048 (every change writes an audit record — server-side) ·
//           BR-SHL-010/011/012 (the ONE table framework, its URL grammar, the A18 states) ·
//           BR-SHL-025 (the permission set gates the UI; the server enforces) ·
//           BR-SHL-032 (a confirm dialog NAMES the action it is about to take)
// ───────────────────────────────────────────────────────
// S14 — the premises registry.
//
// What this screen refuses to do:
//
//   · It never decides whether a delete is allowed. BR-MET-037's guard is a
//     server check against the LIVE unit count; the row hides Delete when the
//     count it was served is non-zero (convenience), and the refusal that comes
//     back from a stale row renders verbatim with its `alternative: deactivate`.
//
//   · It never invents a premises type. The Type filter's options are
//     `GET /premises/types` — the tenant's own Reference-data list (BR-MET-034).
//     A tenant that renamed "Single-family" sees its own label here.
//
//   · It never writes an audit line. Every mutation below is audited SERVER-side
//     (BR-MET-048); the copy says so, it never claims to have written one.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {useNavigate, useSearchParams} from "react-router-dom";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import { CityGisNote, useCityGis } from "@/features/metering/CityGis";
import type { ApiClient } from "@/api/client";
import {
  deletePremises,
  getLookupEntries,
  getPremises,
  getPremisesTypes,
  updatePremises,
} from "@/api/endpoints";
import { REFERENCE_STALE_MS } from "@/api/queryClient";
import type { PremisesRow, PremisesType } from "@/api/endpoints";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { createdAgeColumns } from "@/components/createdAgeColumns";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import { CustomFieldsInput, customDataChanges, useCustomFieldColumns } from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import { JurisdictionField } from "@/features/metering/JurisdictionField";
import { OwnerField } from "@/features/metering/OwnerField";
import {
  ownerAccountAsked,
  ownerAccountPayload,
  premisesOwnerAccount,
} from "@/features/metering/premisesOwnerContract";
import { OwnerMatchingPanel } from "@/features/metering/OwnerMatchingPanel";
import type { FormSubmitOutcome, ServerErrorEnvelope } from "@/components/FormModal";
import { PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { InlineLinkTo } from "@/components/Surfaces";
import { ListExportButton } from "@/features/exports/ListExportButton";
import {
  apiErrorText,
  isPermissionDenied,
  refusalOf,
  RefusalNotice,
} from "@/features/tenancy/settingsShared";
import type { Refusal, Translator } from "@/features/tenancy/settingsShared";
import { PencilIcon, PowerIcon, TrashIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { useTenantPath } from "@/routing/tenantPath";

import {
  AreaFields,
  CELL_FULL,
  DASHBOARD_ROUTE,
  PREMISES_ADD_ROUTE,
  PREMISES_IMPORT_ROUTE,
  PREMISES_PERMISSION,
  ServiceTags,
  areaFilterOptions,
  areaLookupQueryKey,
  areaPayloadCode,
  areaSelectionFrom,
  isDenied,
  premisesDetailPath,
  premisesStatusTone,
  resolveRegional,
  useAccessCell,
  useRegional,
} from "./meteringShared";
import type { AreaSelection } from "./meteringShared";
import { ServicesAvailableField, sameServices } from "./ServicesAvailableField";
import { StatusChangeDialog } from "./StatusChangeDialog";
import { PremisesFormSection } from "./premisesFormSections";

// ── Pure pieces (provable without a browser or a network) ──────────────────

/** US-MET-001 §5: the server's own status set, in its own order. */
export const PREMISES_STATUSES = ["draft", "pending", "active", "inactive"] as const;

export const premisesQueryKey = (query: string) => ["premises", query] as const;
export const premisesTypesQueryKey = ["premises", "types"] as const;

/**
 * BR-MET-037 as the ROW sees it: Delete is offered only at zero units. This is
 * a display decision over the count the server just served — the server
 * re-checks at commit and its refusal is what actually governs.
 */
export function canOfferDelete(row: PremisesRow): boolean {
  return row.units === 0;
}

// ── CR-089 `PUJ-01` · `DEF-4740` — **On the map** ─────────────────────────
/**
 * The three states the blueprint draws between *Owner* and *Status*, and the
 * three the filter offers. One function, so the COLUMN and the CHIP can never
 * disagree about what a row is.
 *
 * ⚠ **IT READS `gis_checked_at`, NEVER `gis_unchecked` ALONE, AND READING THE
 * FLAG WOULD BE WRONG ON EVERY PROPERTY IN THE PRODUCT.** `gis_unchecked` is
 * `NOT NULL DEFAULT false`, so *false* is what all 673 hold and what every
 * create that never mentions it gets — it means *nobody has looked*, not
 * *somebody checked*. Drawing **Checked** off that boolean would tell a clerk
 * the whole estate had been verified by a person who does not exist.
 * `PremisesDetailPage.gisCheckState` reaches the same conclusion for the
 * property's own page; this is the two-of-three version for a row, and it is
 * written here rather than imported because that file imports `PremisesEditModal`
 * from this one.
 *
 * ⚠ **HALF A POINT IS NOT PLACED.** `lat` without `lng` cannot be drawn on a
 * map either, which is the same predicate the server's *Not placed* filter uses
 * (`lat IS NULL OR lng IS NULL`) — one definition, two ends of the wire.
 */
export type PremisesMapState = "checked" | "placed_unchecked" | "not_placed";

export function premisesMapState(
  row: Pick<PremisesRow, "lat" | "lng" | "gis_checked_at">,
): PremisesMapState {
  if (!row.lat || !row.lng) {
    return "not_placed";
  }
  return row.gis_checked_at ? "checked" : "placed_unchecked";
}

/**
 * ⚠ **EVERY KEY IS A LITERAL AND NONE IS BUILT AS `` `…map.${state}` ``.** A
 * key assembled from a variable is a string no grep finds and no gate resolves
 * — G32's own declared blind spot — and a refusal or a label that fails to
 * resolve reaches a clerk as SILENCE rather than as an error. The same reason
 * `StatusChangeDialog` writes its hold keys out one per line.
 *
 * ⚠ **AND THESE THREE ARE THE FILTER'S WORDS TOO** (B14 rule 34: one pair of
 * words for one fact). The column reads `CHECKED` and the chip reads
 * `Checked ×` off this one map, so the list cannot say two things about the
 * state a clerk just filtered for.
 */
export const PREMISES_MAP_LABEL_KEYS: Record<PremisesMapState, string> = {
  // ⚠ `checked` BORROWS THE PROPERTY PAGE'S OWN WORD rather than minting a
  // twelfth *Checked*. `metering.premises.gis.checked` is what PRM-02 draws
  // under *Checked against GIS*, in all eleven catalogues; a second key would
  // be two words for one fact the moment either was re-worded (B14 rule 34,
  // DEF-348's shape).
  checked: "metering.premises.gis.checked",
  placed_unchecked: "metering.premises.map.placedUnchecked",
  not_placed: "metering.premises.map.notPlaced",
};

/**
 * ⚠ **TWO OF THE THREE SHARE A TONE, AND THAT IS THE DRAWING RATHER THAN AN
 * OVERSIGHT.** The blueprint draws `CHECKED` in the accent and both of the
 * others in the quiet grey, because the split that matters to a clerk is
 * *verified* against *not verified yet*; the two greys are degrees of the same
 * deficiency and the LABEL is what separates them. DEF-722's rule — two
 * statuses may not share a colour — is about OPPOSITE facts (*never started*
 * vs *cut off*), which these are not.
 */
export const PREMISES_MAP_TONES: Record<PremisesMapState, StatusTone> = {
  checked: "success",
  placed_unchecked: "neutral",
  not_placed: "neutral",
};

/**
 * The second line of the address cell — `Silver Creek, TX 78611`.
 *
 * The blueprint's own words: *"Street on the first line, town and postcode
 * beneath, so the eye reads a place rather than a row of fragments."* Returns
 * an empty string when the row carries none of the three, so the cell draws one
 * line rather than an empty second one.
 */
export function premisesLocality(
  row: Pick<PremisesRow, "city" | "state" | "postal_code">,
): string {
  const region = [row.state, row.postal_code].filter((part) => Boolean(part)).join(" ");
  return [row.city ?? "", region].filter((part) => part !== "").join(", ");
}

/**
 * The US-MET-001 capability row, as the shared table framework reads it
 * (BR-SHL-010: a capability that is not declared here is not rendered).
 */
export function premisesTableConfig(
  t: Translator,
  typeOptions: { value: string; label: string }[],
  // BR-MET-138 / DEF-836 — the AREA filter's options, hierarchy intact.
  // Passed in rather than fetched here for the reason `typeOptions` is: this
  // function is pure and its options ARE the tenant's own reference list.
  areaOptions: { value: string; label: string }[],
  cells: {
    premiseNo: (row: PremisesRow) => JSX.Element;
    // The column KEY is the server's sort name (`address`, `type`); the DATA
    // field beneath it is `address_line` / `premises_type_name`. The renderer
    // is what bridges the two, so the sort request stays the contract's.
    address: (row: PremisesRow) => JSX.Element;
    type: (row: PremisesRow) => JSX.Element;
    services: (row: PremisesRow) => JSX.Element;
    owner: (row: PremisesRow) => JSX.Element;
    // CR-089 `PUJ-01` / `DEF-4740` — the GIS wave's whole point on this list.
    onTheMap: (row: PremisesRow) => JSX.Element;
    status: (row: PremisesRow) => JSX.Element;
    actions: (row: PremisesRow) => JSX.Element;
  },
  // `DEF-MET-10164` — the tenant's zone and format for the Created and Age
  // columns. The page passes `useRegional`'s answer; a pure caller (a test)
  // may omit it and gets `resolveRegional`'s own fallback rules.
  regional?: { timeZone: string; dateFormat: RegionalDateFormat },
): TableConfig<PremisesRow> {
  return {
    screenId: "S14",
    columns: [
      // 7 default columns + 2 available (City, External ref) — the epic's row.
      {
        key: "premise_no",
        // Drawn `Premise`. It read `Premise ID` until 2026-09-10, which is the
        // word B14 rule 31 spends its whole sentence keeping off a screen — and
        // this column is not one: `P-00080` is a printed reference off the
        // tenant's own series, which is exactly what a clerk reads down the
        // phone. The key is this file's alone, so the value moved rather than a
        // second key being minted.
        label: t("metering.premises.col.premiseNo"),
        sortable: true,
        identity: true, // BR-SHL-013: the identity column can never be hidden
        cell: cells.premiseNo,
      },
      {
        key: "address",
        label: t("metering.premises.col.address"),
        sortable: true,
        cell: cells.address,
      },
      { key: "type", label: t("metering.premises.col.type"), sortable: true, cell: cells.type },
      { key: "units", label: t("metering.premises.col.units"), numeric: true },
      // ⚠ **THE HEADER IS `Services` AND THE FIELD LABEL IS `Utility services`,
      // AND THAT IS TWO SLOTS RATHER THAN TWO WORDS FOR ONE THING.** The
      // blueprint draws the short form in a nine-column header and the long
      // form on the edit form; `metering.premises.col.services` is what the
      // detail fact, the edit section and the add wizard's review row all read,
      // so shortening THAT key would have relabelled four other surfaces.
      { key: "services", label: t("metering.premises.col.servicesShort"), cell: cells.services },
      // ── `Owner` — THE ACCOUNT, NOT THE FREE-TEXT BOX ──────────────────
      // ⛔ **THIS COLUMN RENDERED `owner_manager` UNDER THE LABEL `Owner`, AND
      // THAT IS THE VOCABULARY DEFECT IN ONE CELL.** That column holds *"a
      // name, not an account"* — the property page says exactly that about the
      // same value, two screens away — so the list said `Owner` over a string
      // nothing can be billed to, while the real owner had no column at all.
      // The blueprint draws this column as `Owner` carrying `Creekside Holdings
      // LP` (`CR-089-p005` col 6): a PARTY, which is now the account.
      { key: "owner_manager", label: t("metering.premises.col.owner"), cell: cells.owner },
      // ── CR-089 `PUJ-01` · `DEF-4740` — **On the map** ───────────────────
      // ⚠ **DRAWN BETWEEN `Owner` AND `Status`, AND THE POSITION IS THE
      // SPECIFICATION.** `lat`, `lng` and `gis_checked_at` have been on this
      // row since wave A and NOTHING RENDERED THEM: a clerk could filter for
      // the broken ones and could not see which was which while scanning,
      // which is the one thing this wave exists to make possible.
      // Not sortable: the server declares no sort over the pair, and a header
      // that offers a sort the API drops is a control that lies.
      { key: "on_the_map", label: t("metering.premises.point.label"), cell: cells.onTheMap },
      {
        key: "status",
        label: t("metering.premises.col.status"),
        sortable: true,
        cell: cells.status,
      },
      // ── `DEF-MET-10164` · **Created** and **Age** (PO 2026-10-17) ────────
      // *"some of properties are 20,30 year old many time they need to sort,
      // oldest to newest"*. Default-visible, after Status; both headers send
      // `sort=created`. Age is since the RECORD was created — the PO declined
      // a Year built field — and is computed in the tenant's zone.
      ...createdAgeColumns<PremisesRow>(
        t,
        (row) => row.created_at,
        regional ?? resolveRegional({}, null, import.meta.env.MODE),
      ),
      // PO 2026-08-17 — available, not default. The seven default columns are
      // US-MET-001's ratified row and adding an eighth to a table nobody asked
      // to widen is a change the epic did not make; but a utility that has just
      // spent an afternoon tagging needs to SEE the result on the list, and the
      // column selector is exactly the control for that. `area_path` is the
      // server's own "South · SE" join, not a client re-derivation.
      { key: "area_path", label: t("metering.premises.col.area"), defaultVisible: false },
      { key: "city", label: t("metering.premises.col.city"), defaultVisible: false },
      {
        key: "external_ref",
        label: t("metering.premises.col.externalRef"),
        defaultVisible: false,
      },
      { key: "actions", label: t("metering.col.actions"), cell: cells.actions },
    ],
    getRowId: (row) => row.id,
    // IS-3: server-side search over the declared fields — EP-MET-01's S14
    // capability row, verbatim: `address, premise_no, owner_manager`.
    //
    // ⚠ **THE SERVER MATCHES A FOURTH FIELD NOBODY DECLARED — DEF-1003.**
    // `selectors.premises_list` ORs `address_line | premise_no | owner_manager
    // | city`. CR-041 task 2 briefly declared `city` here to make the row true
    // and `PremisesPage.test.tsx`'s `US-MET-001 TC-3` refused it — correctly:
    // that case pins this row to the EPIC's set, and the epic predates the
    // code (r11 step 2c). So the declaration stays at the epic's three, the
    // prompt below names the same three, and **DEF-1003 carries the fourth
    // leg** for whoever owns the epic. Widening a story's capability row from
    // inside a UI-consistency lane is exactly the quiet scope change the
    // change process exists to refuse.
    searchFields: ["address", "premise_no", "owner_manager"],
    // ⚠ **B14 rule 19, AND WIDER THAN r10's OWN SENTENCE — DELIBERATELY.**
    // r10 PRM-01 (line 651) draws `Search address…`. That is TRUE and it is
    // INCOMPLETE, and DEF-510's register row names this exact box as the reason
    // rule 19 exists: *"the premises search matches address, premise number,
    // owner and city and a user has no way to learn that."* So the prompt names
    // the three the story declares and the server keeps. It stops short of
    // `city` on purpose: advertising a leg no story owns would make the copy the
    // only place a capability is written down, which is how DEF-950 happened in
    // reverse.
    searchPlaceholder: "metering.premises.searchPlaceholder",
    filters: [
      { name: "type", label: t("metering.premises.filter.type"), options: typeOptions },
      {
        name: "status",
        label: t("metering.premises.filter.status"),
        options: PREMISES_STATUSES.map((status) => ({
          value: status,
          label: t(`metering.premises.status.${status}`),
        })),
      },
      // ── BR-MET-138 / DEF-836 · S14 CAN FINALLY BE FILTERED BY AREA ────────
      // PO 2026-08-16: *"in CR06 you can use area and sub area for
      // filtering"*. BR-MET-072 has specified this since that day and
      // `_area_predicate` has implemented it — for the ROUTE picker only. This
      // list declared `type` and `status`, the server ignored anything else by
      // name, and the check written to prove DEF-220 closed asked the list for
      // `NORTH` and got the whole tenant back, which is a chip that lies.
      //
      // ⚠ DECLARED ONLY WHEN THE TENANT HAS AREAS. A group with no options is
      // a control that opens onto nothing, and until fixture V2.48.0.1 most
      // tenants had four areas and no sub-area at all — so the SHAPE of this
      // filter has to survive both.
      ...(areaOptions.length > 0
        ? [
            {
              name: "area",
              label: t("metering.premises.filter.area"),
              options: areaOptions,
            },
          ]
        : []),
      // ── CR-089 wave A `PUJ-01` — **Needs a location** ────────────────────
      // ⚠ **657 of 673 PROPERTIES CARRY A POINT AND 16 DO NOT, AND UNTIL THIS
      // CHIP THERE WAS NO WAY TO ASK WHICH SIXTEEN.** A clerk could only find
      // them by opening properties one at a time; on the demo utility it is 6
      // of 79. The value strings ARE the server's (`needs_location`, `placed`)
      // — a second spelling on the client is how a chip comes to lie, which is
      // DEF-836 on this very list.
      // ⚠ Declared UNCONDITIONALLY, unlike `area` above: every tenant has
      // properties, so this group can never open onto nothing.
      //
      // ⚠ **THREE VALUES SINCE 2026-09-10, NOT TWO, AND THE THIRD IS THE ONE
      // THE BLUEPRINT ARGUES FOR:** *"a point that arrived from an address
      // lookup and a point a person has seen against the city map are
      // different degrees of confidence."* The old pair could only ask *is
      // there a point at all*, so the properties a person still has to check
      // were indistinguishable from the ones already checked — over half the
      // work the wave exists to end.
      //
      // ⚠ **THE VALUE STRINGS ARE THE SERVER'S** (`checked`,
      // `placed_unchecked`, `needs_location`) and `selectors.premises_list`
      // grew the first two in the same commit as this line. A client value the
      // server does not know falls through to NO filter, so the chip would come
      // back with the whole tenant looking like a filter that had found
      // everything — DEF-836, on this very list.
      //
      // ⚠ **`needs_location` KEEPS ITS SPELLING AND CHANGES ITS WORDS.** It is
      // the value in every URL a clerk has bookmarked since wave A and the one
      // the backend test pins; the blueprint's word for it is *Not placed*, so
      // the LABEL moved and the value did not. `placed` stays a server branch
      // and leaves this list — it is the union of the two states above it, so
      // offering it as a fourth choice would be a chip whose answer is two
      // other chips added together.
      {
        name: "location",
        label: t("metering.premises.point.label"),
        options: [
          { value: "checked", label: t(PREMISES_MAP_LABEL_KEYS.checked) },
          {
            value: "placed_unchecked",
            label: t(PREMISES_MAP_LABEL_KEYS.placed_unchecked),
          },
          { value: "needs_location", label: t(PREMISES_MAP_LABEL_KEYS.not_placed) },
        ],
      },
      // ── CR-089 wave B `B2` — **Needs an owner** ──────────────────────────
      // ⚠ **THIS CHIP IS THE OTHER HALF OF `B1` AND MUST NOT BE REMOVED WITHOUT
      // IT.** `B1` reverses the server's create-time owner requirement (PO
      // 2026-09-08, *"Owner = search ( it should be optional)"*), so a property
      // can now exist with nobody attached to it. CR-089 §2.1 names the cost in
      // the same sentence as the ruling: the list is *"what stops the reversal
      // creating orphans nobody can find"*.
      //
      // ⚠ **IT IS NOT THE OWNER-MATCHING BACKLOG WEARING A DIFFERENT NAME.**
      // PRM-04 lists addresses that hold a free-text NAME and no typed record —
      // 8 of 79 on the demo utility. This chip asks the question a BILL asks:
      // is there a party at all? — 73 of 79, and the 65 with neither a record
      // nor a name were on no list in this product before today.
      //
      // The value strings ARE the server's (`needs_owner`, `has_owner`); a
      // second spelling on the client is how a chip comes to lie, which is
      // DEF-836 on this very list. Declared unconditionally, like `location`
      // above: every tenant has properties, so it cannot open onto nothing.
      {
        name: "owner",
        label: t("metering.premises.filter.owner"),
        options: [
          { value: "needs_owner", label: t("metering.premises.owner.needs_owner") },
          { value: "has_owner", label: t("metering.premises.owner.has_owner") },
        ],
      },
    ],
    defaultSort: { sort: "premise_no", dir: "asc" },
  };
}

/** BR-MET-034: the filter's options ARE the tenant's Reference-data list. */
export function premisesTypeOptions(
  types: readonly PremisesType[] | undefined,
): { value: string; label: string }[] {
  return (types ?? [])
    .filter((type) => type.active)
    .map((type) => ({ value: type.code, label: type.name }));
}

/** The request state → the wrapper's params. One translation, one place. */
export function premisesParamsFrom(state: TableRequestState) {
  return {
    q: state.q,
    sort: state.sort,
    dir: state.dir,
    page: state.page,
    per: state.per,
    filters: state.filters,
  };
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface PremisesListPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

type PendingAction =
  | { kind: "deactivate"; row: PremisesRow }
  | { kind: "delete"; row: PremisesRow }
  | { kind: "edit"; row: PremisesRow };

export function PremisesListPage(props: PremisesListPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const cell = useAccessCell(PREMISES_PERMISSION, client);
  // `DEF-MET-10164` — the tenant's zone and format, for Created and Age.
  const regional = useRegional({});
  // BR-SHL-025: "Full" writes; anything else renders the control disabled WITH
  // the reason. The server refuses regardless — this only saves a round trip.
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("metering.rbac.readOnly");

  const typesQuery = useQuery({
    queryKey: premisesTypesQueryKey,
    queryFn: () => getPremisesTypes(client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  // BR-MET-138 — the SAME query key the S16/S14 area pickers use, so the three
  // controls on this screen never disagree about what areas exist.
  const areasQuery = useQuery({
    queryKey: areaLookupQueryKey,
    queryFn: () => getLookupEntries("areas", { per: 200 }, client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });

  const config = premisesTableConfig(
    translate,
    premisesTypeOptions(typesQuery.data),
    areaFilterOptions(areasQuery.data?.results ?? []),
    {
    premiseNo: (row) => (
      <InlineLinkTo to={tenantPath(premisesDetailPath(row.id))}>
        {row.premise_no ?? t("metering.premises.noNumber")}
      </InlineLinkTo>
    ),
    // ── `DEF-4740` · the address is ONE cell drawn on TWO lines ────────────
    // The blueprint: *"Street on the first line, town and postcode beneath in
    // the muted tone. It was four columns of fragments; the eye reads a place
    // now."*
    // ⚠ **NO TAILWIND UTILITY HERE.** This file is not on
    // `src/styles/route-b-migrated.txt`, so `block` or `text-sm` would be
    // classes no stylesheet declares — they render as NOTHING and `tsc`,
    // eslint and every `toContain("block")` pass over them (B14 rule 21's
    // per-file clause, DEF-974). A `<div>` is already block, `<strong>` is
    // already the strong tone, and `.met-qualifier` is a class the metering
    // stylesheet already declares as the muted smaller line — which is what
    // rule 21 is actually asking for.
    address: (row) => {
      const locality = premisesLocality(row);
      return (
        <div>
          <strong>{row.address_line ?? ""}</strong>
          {locality !== "" && <div className="met-qualifier">{locality}</div>}
        </div>
      );
    },
    type: (row) =>
      row.premises_type_name !== null ? (
        <span>{row.premises_type_name}</span>
      ) : (
        <span className="met-muted">{t("metering.premises.noType")}</span>
      ),
    services: (row) => <ServiceTags services={row.services_available} t={translate} />,
    // ⚠ **THE NUMBER RIDES FREE ON THIS LIST AND THE FULL EXPANSION DOES NOT.**
    // `DEF-324` measured the alternative at 304 calls answering one question,
    // so the server resolves every account id on the page in ONE query and
    // serves `master_account_expanded: false` to say the rest was not asked.
    // A screen that drew *no owner* off an unexpanded row would state something
    // the server never said — the same fault as rendering `0.00` for a balance
    // that could not be read.
    owner: (row) => {
      const account = premisesOwnerAccount(row);
      if (account !== null) {
        return (
          <span data-tracks="premises-owner-account">
            {account.name ?? translate("metering.premises.owner.unnamed")}
            {account.account_no === null ? "" : ` · ${account.account_no}`}
          </span>
        );
      }
      if (!ownerAccountAsked(row)) {
        // NOT ASKED. A blank cell here is honest; a chip would be a claim.
        return <span />;
      }
      // No account. The typed name is the only clue to who this is
      // (`BR-MET-151` matches an import against it) and it is NOT dropped — but
      // it is drawn in the absent style so it cannot be read as an account.
      return (
        <span className="met-muted" data-tracks="premises-owner-none">
          {row.owner_manager === null || row.owner_manager === ""
            ? translate("metering.premises.owner.needs_owner")
            : row.owner_manager}
        </span>
      );
    },
    // ── CR-089 `PUJ-01` · `DEF-4740` ──────────────────────────────────────
    // The kit's own pill, not a new component: B14 rule 36 — comply through
    // the kit rather than hand-rolling beside it — and it is the same pill the
    // Status column two places to the right already draws.
    onTheMap: (row) => {
      const state = premisesMapState(row);
      return (
        <StatusPill tone={PREMISES_MAP_TONES[state]}>
          {t(PREMISES_MAP_LABEL_KEYS[state])}
        </StatusPill>
      );
    },
    status: (row) => (
      <StatusPill tone={premisesStatusTone(row.status)}>
        {t(`metering.premises.status.${row.status}`, { defaultValue: row.status })}
      </StatusPill>
    ),
    actions: (row) => (
      <RowActions>
        {/* ── `DEF-MET-5841` · THE EYE IS GONE, AND IT IS A DELETION RATHER
            THAN A REPOINT ─────────────────────────────────────────────────
            It carried `US-MET-001`'s *"View units"* and went to
            `/premises/units?f.premises_id=…` — **the Units tab, filtered**, not
            the premise. The PO opened it in the beta and reported the mismatch
            twice: first *"should redirect to view detail of premise"*, then,
            on being told the premise NUMBER in the first column already does
            exactly that, *"remove Eye icon… not required since you ahve given
            view on P-00001"*. Two doors to one screen is one door too many;
            an eye that opens a different screen from the one it looks like it
            opens is worse than either.
            ⚠ **THE UNITS-BY-PREMISES PATH SURVIVES AND WAS CHECKED BEFORE THIS
            WAS DELETED** (`DEF-CUS-3653`'s lesson — *grep for the CONSUMERS,
            because an absence is invisible to every check this repo has*).
            `UnitsListPage` owns a `f.premises_id` FILTER FIELD of its own, the
            property's own page carries a Units tab, and the URL shape is
            unchanged and still routed — so nothing reached that list ONLY
            through this icon. What did go red is `PremisesPage.test.tsx`'s
            assertion on the `href`, and that red is correct: it is fixed rather
            than silenced. */}
        <RowAction
          label={t("metering.action.edit")}
          icon={<PencilIcon />}
          reason={writeBlockedReason}
          onClick={() => setPending({ kind: "edit", row })}
        />
        {/* ── `DEF-4743` — THE SECOND DOOR OUT OF SERVICE, POINTED AT THE
            REAL DIALOG (PO ruling 2026-09-10: *keep the shortcut, point it at
            the real dialog*) ────────────────────────────────────────────────
            ⚠ **THIS OPENED A PLAIN CONFIRM THAT ASKED NOTHING.** CR-089 wave D
            built `StatusChangeDialog` — the blockers, the danger tier, and the
            two facts `BR-TEN-043` wants recorded, a DATE and a REASON — and
            nobody asked whether the old route was retired. So a clerk who went
            through the property's page recorded both and a clerk who used this
            row action recorded neither, on the same act. Landing a screen and
            retiring the route it replaces are two acts and only the first
            feels like the work (hard-won law 2's mirror).
            ⚠ **THE LABEL FOLLOWS THE ROW'S STATUS**, because the dialog does:
            it reads the server's `target_status` and offers *Put back in
            service* on a property that is already out of it. A row action
            saying `Deactivate` over a dialog offering the opposite is the
            same lie one layer up. */}
        <RowAction
          label={
            row.status === "inactive"
              ? t("metering.premises.status.reactivateAction")
              : t("metering.premises.status.deactivateAction")
          }
          icon={<PowerIcon />}
          reason={writeBlockedReason}
          onClick={() => setPending({ kind: "deactivate", row })}
        />
        {/* BR-MET-037: Delete exists only at zero units. With units on the
            premise the control is DISABLED WITH THE REASON — the user learns
            the rule instead of hunting for a vanished button (BR-SHL-025). */}
        <RowAction
          label={t("metering.action.delete")}
          icon={<TrashIcon />}
          danger
          reason={
            canOfferDelete(row)
              ? writeBlockedReason
              : t("metering.premises.deleteBlockedHint", { units: row.units })
          }
          onClick={() => setPending({ kind: "delete", row })}
        />
      </RowActions>
    ),
  },
    regional,
  );
  // ── `CR-161-BRC10` W3 · `DEF-MET-9226` — the optional column ────────────
  // One column per Premises field the tenant switched to *Show as column* on
  // this list (default *Not shown*), placed before the row actions. A tenant
  // with none gets exactly the columns it always had.
  const customColumns = useCustomFieldColumns<PremisesRow>({
    entity: "premises",
    screen: "S14",
    valuesOf: (row) => [{ values: row.custom_data ?? {} }],
    client,
  });
  config.columns.splice(config.columns.length - 1, 0, ...customColumns);

  const state = parseTableParams(searchParams, config);
  function setState(next: TableRequestState): void {
    setSearchParams(serializeTableParams(next, config), { replace: true });
  }

  const listKey = premisesQueryKey(serializeTableParams(state, config).toString());
  const listQuery = useQuery({
    queryKey: listKey,
    queryFn: () => getPremises(premisesParamsFrom(state), client),
  });

  function afterWrite(messageKey: string, params?: Record<string, unknown>): void {
    setPending(null);
    setRefusal(null);
    void queryClient.invalidateQueries({ queryKey: ["premises"] });
    fireToast(t(messageKey, params));
  }

  // ⚠ **THERE IS NO `deactivate` MUTATION ON THIS SCREEN ANY MORE — `DEF-4743`.**
  // `POST /premises/{id}/deactivate` records no date and no reason; the wave-D
  // dialog posts `POST /premises/{id}/status`, which records both. The blockers
  // were already enforced on both doors off the same counts, so nothing unsafe
  // was getting through — what was lost was the audit facts, every time a clerk
  // used the row action instead of the property's page. The endpoint wrapper
  // stays in `api/endpoints.ts`: retiring a served route is the backend's act,
  // not a side effect of a screen change.
  const remove = useMutation({
    mutationFn: (row: PremisesRow) => deletePremises(row.id, client),
    onSuccess: (_void, variables) =>
      afterWrite("metering.premises.toast.deleted", { premise: label(variables, t) }),
    onError: (error: unknown) => setRefusal(refusalOf(error, translate)),
  });

  if (isDenied(cell)) {
    // BR-SHL-003 / A18 §6: a surface this role cannot reach is not drawn.
    return (
      <PermissionDenied
        helper={t("metering.premises.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (listQuery.data === undefined && listQuery.isError && isPermissionDenied(listQuery.error)) {
    return (
      <PermissionDenied
        helper={t("metering.premises.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }

  return (
    <>
      {/* ⚠ **NO PAGE HEADER AND NO KPI STRIP HERE ANY MORE — CR-023 P0.**
          This screen is a TAB BODY now: `PremisesTabsPage` owns the one head
          (B14 rule 2 / BR-SHL-044), its roll-up sentence and the three-tab
          strip, because r10 draws Premises · Units · Imports as ONE page and
          the head's actions change with the tab.

          The four counts that used to be a `KPIStrip` right here are the head's
          roll-up line now — r10's own `428 premises · 1,247 units · 34 vacant ·
          12 pending activation` — which is the placement delta the 2026-08-10
          conversion trailer reported and left. `metering.premises.kpi.*` are no
          longer read by this file; the shell's sentence replaces all four. */}
      <RefusalNotice refusal={refusal} />

      {/* CR-039 wave C task 13 — BR-MET-151's matching surface. `metering 0040`
          backfills NOTHING, because the PO's caveat forbids guessing which
          string is which party; this is where the names actually move, one
          decision at a time. It renders nothing at all when the backlog is
          empty, so a tenant that has finished never sees it again. */}
      <OwnerMatchingPanel client={client} />

      <DataTable<PremisesRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={listQuery.data?.results ?? []}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isPending}
        error={
          listQuery.isError && listQuery.data === undefined
            ? {
                reason: apiErrorText(listQuery.error, translate),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
        }
        // ⚠ **THERE IS NO SECOND TOOLBAR ROW ON THIS SCREEN ANY MORE
        //    (DEF-1700, PO 2026-08-27).** A type segment used to sit here —
        //    first in `downloadSlot`, then in `dimensionsSlot` after DEF-1085
        //    built that slot for it — drawing Apartment complex · Commercial
        //    building · Government building · Mixed-use · Mobile-home park ·
        //    Single-family under the toolbar. The Product Owner photographed it
        //    and ruled: *"as per our stadard first raw of tookkit is more than
        //    suficient"*. `type` was ALREADY a declared `TableConfig.filter`
        //    reading the same `GET /premises/types` and writing the same
        //    `f.type` param, so the segment was pure duplication and its
        //    removal loses nothing — see `12-governance/02-decision-log.md`,
        //    2026-08-27, for the measurement and the stamped r10 divergence.
        downloadSlot={
          <>
            {/* US-MET-001's capability row declares "Export: CSV (IS-9)"; the
                shared control posts THIS state and the server does the rest
                (BR-SHL-016 — nothing about the cap or the file is re-done). */}
            <ListExportButton resource="premises" state={state} client={client} />
          </>
        }
        empty={{
          title: t("metering.premises.emptyTitle"),
          helper: t("metering.premises.emptyHelper"),
          ctaLabel: t("metering.premises.action.new"),
          onCta: () => navigate(tenantPath(PREMISES_ADD_ROUTE)),
          // ⚠ **THE DRAWING OFFERS TWO WAYS OUT AND THIS BLOCK OFFERED ONE.**
          // Blueprint, verbatim: *"The empty state names what is missing and
          // offers the two ways to fill it — add one, **or import a list**."*
          // A utility's first act on this product is almost always the import,
          // and it was the one option the empty state did not mention: a door
          // a clerk had to already know about, on the one screen where they
          // know least.
          secondaryCtaLabel: t("metering.premises.action.importShort"),
          onSecondaryCta: () => navigate(tenantPath(PREMISES_IMPORT_ROUTE)),
        }}
      />

      <p className="settings-audit-line">{t("metering.auditLine")}</p>

      {/* BR-SHL-032: the confirm NAMES the action and its consequence. */}
      {/* `DEF-4743` — the SAME dialog `PremisesDetailPage` opens, so the date
          and the reason are recorded whichever door a clerk came through. */}
      {pending?.kind === "deactivate" && (
        <StatusChangeDialog
          subject="premises"
          id={pending.row.id}
          name={label(pending.row, t)}
          client={client}
          onClose={() => setPending(null)}
          // ⚠ **THE TOAST USES THE DIALOG'S OWN WORDS, NOT THE OLD
          //    `…toast.deactivated` ("is deactivated").** B14 rule 34: one pair
          //    of words for one fact. Pressing a button that says *Take out of
          //    service* and being told the property *is deactivated* is two
          //    vocabularies for one act, which is DEF-348's shape.
          onChanged={(status) =>
            afterWrite(
              status === "inactive"
                ? "metering.premises.status.toastOut"
                : "metering.premises.status.toastBack",
              { premise: label(pending.row, t) },
            )
          }
        />
      )}
      {pending?.kind === "delete" && (
        <ConfirmDialog
          // B14 rule 6 (DEF-718): delete a premise.
          confirmVariant="danger"
          title={t("metering.premises.confirm.deleteTitle", { premise: label(pending.row, t) })}
          consequence={t("metering.premises.confirm.deleteBody")}
          confirmLabel={t("metering.premises.confirm.deleteAction")}
          working={remove.isPending}
          onConfirm={() => remove.mutate(pending.row)}
          onCancel={() => setPending(null)}
        />
      )}
      {pending?.kind === "edit" && (
        <PremisesEditModal
          row={pending.row}
          types={typesQuery.data ?? []}
          client={client}
          onClose={() => setPending(null)}
          onSaved={() =>
            afterWrite("metering.premises.toast.saved", {
              premise: label(pending.row, t),
            })
          }
        />
      )}
    </>
  );
}

/** The row's human identifier — never the internal uuid (BR-AST-026's spirit). */
function label(row: PremisesRow, t: Translator): string {
  return row.premise_no ?? row.address_line ?? t("metering.premises.noNumber");
}

// ── Edit (US-MET-001 row action; the S16 wizard owns CREATE) ───────────────

/**
 * Exported for PRM-02's header `Edit` (CR-023 P2). ONE edit form for a premise,
 * reached from the list row and from the detail header — a second form would be
 * two places to add a field to and one of them would be forgotten, which is
 * DEF-021's shape.
 */
export function PremisesEditModal(props: {
  row: PremisesRow;
  types: readonly PremisesType[];
  client: ApiClient;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  // GIS Lane D (`DEF-MET-10003`) — the two coordinate boxes are City fields.
  const city = useCityGis(props.client);
  // CR-036 (h) / DEF-756. The list the clerk is EDITING, held apart from
  // `values` on purpose: `submit` has to be able to ask whether it changed.
  //
  // ⚠ **AND THAT IS THE WHOLE OF SCOPE ROW 5.** A premises whose column has
  // never been written holds SQL NULL — *never asked*, which is not the same
  // answer as *offers nothing* — and `premises_row_dict` serves both as `[]`.
  // So an UNCHANGED control sends NO field, the server's `_validate_premises`
  // leaves the column alone, and a clerk correcting a street name does not
  // silently convert an unanswered question into an answered one. A clerk who
  // actually changes the list sends it, empty included, because that IS an
  // answer.
  //
  // ⚠ **AND IT IS HELD AS `string[] | null`, NOT `?? []` (DEF-762).** The line
  // below read `props.row.services_available ?? []`, which was the only shape
  // available while the selector collapsed NULL into `[]`. It served the
  // no-backfill rule by accident — an untouched control compared equal to `[]`
  // and sent nothing — but it also meant a clerk could never RECORD "this
  // address offers nothing" on an address nobody had been asked about, because
  // that answer was already the form's starting value. Now `null` opens as
  // *Not recorded*, and the first touch makes it an array, which is an answer.
  const initialServices = props.row.services_available;
  const [services, setServices] = useState<string[] | null>(
    initialServices === null ? null : [...initialServices],
  );
  // CR-039 wave C task 10 / DEF-517. Held apart from `values` for the same
  // reason `services` above is: it is a THREE-state field and `values` is a
  // map of strings the zod schema validates. `undefined` never reaches here —
  // the selector serves the column as `true | false | null` (DEF-507).
  const [insideCity, setInsideCity] = useState<boolean | null>(
    props.row.inside_city_limits,
  );
  const [values, setValues] = useState({
    address_line: props.row.address_line ?? "",
    city: props.row.city ?? "",
    state: props.row.state ?? "",
    postal_code: props.row.postal_code ?? "",
    premises_type: props.row.premises_type ?? "",
    owner_manager: props.row.owner_manager ?? "",
    external_ref: props.row.external_ref ?? "",
    // ── CR-089 wave A `PUJ-19` — a point can be CORRECTED here ────────────
    // Re-opened from what the server stored, like every other control on this
    // form, and as STRINGS: what came off the wire is what goes back, so a
    // property nobody is repositioning saves the same six decimals it had.
    lat: props.row.lat ?? "",
    lng: props.row.lng ?? "",
  });
  // Re-opened from what the SERVER stored, never guessed: `area_parent_code` is
  // what tells the form whether a bare code belongs in the Area box or the
  // Sub-area box (BR-MET-071). A form that guessed would put every sub-area in
  // the Area box and silently re-tag the premises to its parent on save.
  const [area, setArea] = useState<AreaSelection>(areaSelectionFrom(props.row));
  // ── THE OWNER — the MASTER ACCOUNT this property names ──────────────────
  //
  // ⛔ **IT HELD AN OWNER RECORD'S ID UNTIL 2026-09-22 AND THE PO COULD NOT USE
  // IT (`DEF-MET-6155`).** Their report: *"in edit also we are unabel to search
  // owner"*. Measured in a browser: the control drew **0 options**, under
  // *"Not listed? Type the name below"* — an instruction that creates nothing.
  // Re-opened from what the SERVER stored, like every other control on this
  // form, through the one reader that applies the ruling's precedence.
  const openedAccount = premisesOwnerAccount(props.row);
  const [ownerAccountId, setOwnerAccountId] = useState<string | null>(openedAccount?.id ?? null);
  // `CR-161-BRC10` W3 · `DEF-MET-9226` — the tenant's own fields, re-opened on
  // what the server stored. The save sends only what CHANGED (a cleared box as
  // `null`), and the server merges it into the stored answers.
  const openedCustom = props.row.custom_data ?? {};
  const [customData, setCustomData] = useState<CustomFieldValues>(openedCustom);

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      // The premise NUMBER is system-derived from the tenant series
      // (BR-MET-001) and is not in this payload — there is no control for it.
      //
      // `area_code` IS always sent on an EDIT, empty string included: on this
      // screen an empty box is a deliberate "no area", and the server reads an
      // explicit empty as a clear and an ABSENT field as "leave it alone".
      await updatePremises(
        props.row.id,
        {
          ...values,
          area_code: areaPayloadCode(area),
          // CR-039 wave C task 10 — BR-RAT-101's three-state, ALWAYS sent.
          // Unlike `services_available` there is nothing to protect by
          // withholding it: the form opens on what the server stored, `null`
          // round-trips as `null`, and `update_premises` writes only fields
          // whose value actually CHANGED — so an untouched control produces no
          // write and no audit row. Withholding it instead would make the
          // "clear this back to not recorded" option unreachable.
          inside_city_limits: insideCity,
          // CR-039 wave C task 12 — ALWAYS sent, for JurisdictionField's own
          // reason: the form opens on what the server stored, `null`
          // round-trips as `null`, and `update_premises` writes only fields
          // that actually CHANGED, so an untouched control produces no write
          // and no audit row. Withholding it would make "clear this back to no
          // owner record" unreachable.
          //
          // ⚠ It does NOT clear `owner_manager`, and must not: that column is
          // what `open_account` reads for the default payer (`OQ-500`) and it
          // is the provenance of the match (BR-MET-151).
          //
          // ⛔ **`master_account_id`, NOT `owner_id` — AND THIS IS THE "later"
          // IN THE PO'S OWN SENTENCE**: *"we are unabel to find and map master
          // account to premises later"*. The PATCH door takes it, refuses
          // anything that is not an existing master account in this tenant BY
          // NAME rather than ignoring it, and `null` clears it. The key is
          // spelled in `premisesOwnerContract` and nowhere else.
          ...ownerAccountPayload(ownerAccountId),
          // ALWAYS sent, even empty: a required field placed Input on this
          // form must be able to refuse a save that leaves it blank.
          custom_data: customDataChanges(openedCustom, customData),
          // See `initialServices` above — absent means "leave the column alone".
          ...(sameServices(services, initialServices) || services === null
            ? {}
            : { services_available: services }),
        },
        props.client,
      );
      props.onSaved();
      return { ok: true };
    } catch (error) {
      return { ok: false, error: toEnvelope(error) };
    }
  }

  return (
    <FormModal
      title={t("metering.premises.edit.title", {
        premise: props.row.premise_no ?? props.row.address_line ?? "",
      })}
      kicker={t("metering.kicker")}
      schema={premisesEditSchema(t)}
      values={values}
      submitLabel={t("metering.premises.edit.save")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      {/* ══ CR-089 wave B `B8` — THE SAME SIX HEADINGS THE CREATE FORM DRAWS,
             IN THE SAME ORDER ═══════════════════════════════════════════════
          PO 2026-09-08, verbatim: *"05 Edit a property PRM-02 and create
          property screen should match - please update - it will help user to
          have simialr experience"*.
          ⚠ **THEY DID NOT MATCH, AND NOT BY A LITTLE.** This form asked for the
          parcel and the two coordinates LAST, under the owner; the create form
          asked for them FOURTH, right under the postal code. Same eight facts,
          two orders, and a clerk who learned one screen had to re-find every
          field on the other. Neither form had a heading of any kind.
          ⚠ **THE ORDER IS DECLARED IN `premisesFormSections.tsx` AND MAPPED BY
          BOTH FORMS**, so this is not two files agreeing by convention — a
          comment asking them to stay in step is a comment, and an exported
          array both files render is the thing itself. */}

      {/* ══ 1 · WHERE IT IS ══════════════════════════════════════════════ */}
      {/* ══ 1 · WHERE IS IT? ══════════════════════════════════════════════
          CR-089 `PUJ-18` — the drawn form has FOUR named groups, not six, and
          the parcel, the point and the GIS flag live INSIDE this one rather
          than in a group of their own. The commitment sentence said "the same
          six headings" and the frame drew four; PO ruling 2026-09-10: **the
          frame wins, correct the sentence.** */}
      <PremisesFormSection id="where" t={t}>
        <TextField
          id="address_line"
          label={t("metering.premises.field.address")}
          required
          value={values.address_line}
          onChange={(value) => setValues({ ...values, address_line: value })}
        />
        <TextField
          id="city"
          label={t("metering.premises.field.city")}
          value={values.city}
          onChange={(value) => setValues({ ...values, city: value })}
        />
        <TextField
          id="state"
          label={t("metering.premises.field.state")}
          value={values.state}
          onChange={(value) => setValues({ ...values, state: value })}
        />
        <TextField
          id="postal_code"
          label={t("metering.premises.field.postalCode")}
          value={values.postal_code}
          onChange={(value) => setValues({ ...values, postal_code: value })}
        />
        {/* ── `DEF-4741` — THE CONSEQUENCE BOX B14 RULE 11 REQUIRES ─────────
            Drawn immediately under the address row, inside the form, tagged
            `CHANGING AN ADDRESS`.
            ⚠ **THIS FILE IMPORTED `ConsequenceBox` ZERO TIMES**, while the kit
            held the component and B14 rule 11 has required one before any
            commit that changes service state since it was ratified. Moving an
            address moves which taxes and which rate apply, and it moves the
            envelopes with it — the blueprint says so in its own rules row.
            Rule 11 is RATIFIED AND UNENFORCED, like most of B14, because no
            gate here reads rendered output; both screens were walked and
            ticked done anyway.
            ⚠ **NO COUNTS.** The blueprint's sentence names four units, four
            meters, one route, two work orders and three accounts — and the
            standing caveat on every one of these plates is that the VALUES are
            illustrations while the labels and the presence are the
            specification. `PremisesRow` carries a unit count and nothing else
            of that list, so a sentence built from it would be three invented
            numbers beside one real one. What is true of every property is said
            instead.
            `tone="move"` is the kit's own word for *something is re-pointed*,
            which is exactly what follows an address. */}
        <ConsequenceBox
          tone="move"
          tag={t("metering.premises.edit.addressConsequenceTag")}
          title={t("metering.premises.edit.addressConsequenceTitle")}
          body={t("metering.premises.edit.addressConsequenceBody")}
          data-consequence="premises-address"
        />
        {/* CR-089 wave A `PUJ-20` · `BR-MET-1163` — the SAME column, under the
            name of what it holds.
            ⚠ **`Import reference` FROM 2026-10-07, AND IT READ `Parcel`
            (`DEF-MET-10008`).** `BR-MET-1173` (PO 2026-09-17) made this column
            the import match key and moved the City's parcel to `gis_parcel_id`;
            a clerk typing a parcel number here was writing the match key. */}
        <TextField
          id="external_ref"
          label={t("metering.premises.field.importRef")}
          value={values.external_ref}
          onChange={(value) => setValues({ ...values, external_ref: value })}
          help={t("metering.premises.field.importRefHelp")}
        />
        {/* ── CR-089 wave A `PUJ-19` — THE POINT, CORRECTED WHERE IT IS WRONG ──
            ⚠ **THE SERVER REFUSED THESE TWO FIELDS ON A PATCH UNTIL WAVE A**,
            deliberately — the only writers were the City and a deterministic
            seed, and *"a set value is never overwritten by either"*. The
            consequence was that a property placed on the wrong side of the
            street stayed there for ever. A clerk is now the one writer allowed
            to overwrite one.
            ⚠ NOT a draggable pin — PO 2026-09-08: *"we dont need this right
            now"*. Two figures, typed. */}
        {/* GIS Lane D (`DEF-MET-10003`) — drawn only where a City GIS is in
            use. Hidden boxes still carry the stored values in `values`, and
            `update_premises` writes only what CHANGED, so hiding them clears
            nothing. */}
        {city.showCity && (
          <>
            <TextField
              id="lat"
              label={t("metering.premises.field.lat")}
              value={values.lat}
              onChange={(value) => setValues({ ...values, lat: value })}
              numeric
            />
            <TextField
              id="lng"
              label={t("metering.premises.field.lng")}
              value={values.lng}
              onChange={(value) => setValues({ ...values, lng: value })}
              numeric
              help={t("metering.premises.point.help")}
            />
            <CityGisNote messageKey={city.brokenKey} />
          </>
        )}
      </PremisesFormSection>

      {/* ══ 2 · WHAT KIND OF PROPERTY IS IT? ═════════════════════════════
          The services control moves IN HERE, where the frame draws it — what a
          property can take is part of what kind of property it is. */}
      <PremisesFormSection id="kind" t={t}>
        {/* BR-MET-034: the tenant's Reference-data list, never a hardcoded set. */}
        <SelectField
          id="premises_type"
          label={t("metering.premises.field.type")}
          value={values.premises_type}
          placeholder={t("metering.premises.field.typePlaceholder")}
          options={props.types
            .filter((type) => type.active)
            .map((type) => ({ value: type.code, label: type.name }))}
          onChange={(value) => setValues({ ...values, premises_type: value })}
          help={t("metering.premises.field.typeHelp")}
        />
        {/* CR-039 wave C task 10 / DEF-517 — the flag that decides an
            outside-city surcharge on every bill at this address, and that no
            screen could set until now. Same component as S16 renders. */}
        <JurisdictionField value={insideCity} onChange={setInsideCity} t={t} />
        {/* CR-036 (h) — and for exactly the same reason: ONE services control,
            shared with S16, so a rule added to one is added to both. */}
        <ServicesAvailableField value={services} onChange={setServices} client={props.client} />
      </PremisesFormSection>

      {/* ══ 3 · WHO LOOKS AFTER IT? ══════════════════════════════════════
          Owner, and the area it belongs to — the frame groups them together
          because they answer one question. */}
      <PremisesFormSection id="owner" t={t}>
        {/* The MASTER ACCOUNT this property names, ABOVE the free-text box.
            Both are drawn because both are real and they are DIFFERENT FACTS:
            the account is who gets billed, `Managed by` is a name somebody
            typed, which is what `BR-MET-151` matches an import against.
            ⚠ `editing` gives this form the blueprint's own placeholder
            (`Search by name, or clear it…`) and the one sentence it draws under
            the card; the create form draws neither. */}
        <OwnerField
          value={ownerAccountId}
          onChange={(accountId) => setOwnerAccountId(accountId)}
          account={openedAccount}
          editing
          t={t}
          client={props.client}
        />
        {/* ⚠ **`Managed by`, NOT `Owner / manager` — ONE VOCABULARY.** The PO
            counted five wordings for one fact and ruled: *"owner and master
            account is confusing we ahve to use one volcabory"*. **Owner** is
            the surviving noun; this box is a DIFFERENT fact and now says which,
            in the blueprint's own word — `CR-089-p008` and `CR-089-p036` both
            label this row `Managed by`, with the helper `Only if different.` */}
        <TextField
          id="owner_manager"
          label={t("metering.premises.field.managedBy")}
          value={values.owner_manager}
          onChange={(value) => setValues({ ...values, owner_manager: value })}
        />
        {/* PO 2026-08-17 — the same two controls the add wizard renders, from the
            same component, so the two forms can never disagree. */}
        <AreaFields value={area} onChange={setArea} client={props.client} />
      </PremisesFormSection>

      {/* ══ 4 · READING AND BILLING ══════════════════════════════════════
          CR-089 `PUJ-18` — the fourth drawn group, and it did not exist.
          ⚠ **THE FIELDS STAY READ-ONLY, AND THAT IS A RULING BEATING A
          DRAWING RATHER THAN A GAP.** The frame draws `Read route` and
          `Billing cycle` as editable; three signed rules say otherwise —
          `BR-MET-074` makes a route change a MOVE, `CR-006` requires that move
          be confirmed on screen, and `BR-MET-083` boundary 2 says *"a move
          triggered by a form field on a different screen is a move nobody
          agreed to"*. The PO has twice ruled the same way this day (the audit
          window sentence, the search placeholder): **the frame governs where it
          made a decision, and loses where it simply did not consider a rule
          that already existed.** So the GROUP is built as drawn and the two
          facts are named in it; the route wizard stays where a move happens. */}
      <PremisesFormSection id="readingBilling" t={t}>
        {/* ⚠ **THE ROUTE IS READ-ONLY HERE AND THAT IS A RULING, NOT A GAP.**
            `B6` puts a route picker on the CREATE form; changing one afterwards
            is `BR-MET-074`'s MOVE, which CR-006 requires be confirmed on screen
            (*"selecting moves them, with confirm"*) — *"a move triggered by a
            form field on a different screen is a move nobody agreed to"*
            (`BR-MET-083` boundary 2). So this section states where the property
            sits and sends nobody anywhere they did not ask to go; the route
            wizard is where a move happens. Stated rather than left as an
            unexplained absence (B14 rule 32). */}
        <p className="met-panel-hint">{t("metering.premises.route.editElsewhere")}</p>
      </PremisesFormSection>
      {/* `CR-161-BRC10` W3 — Edit premise's slot. Nothing at all for a tenant
          with no field placed here. */}
      <CustomFieldsInput
        entity="premises"
        screen="PREMISE_EDIT"
        values={customData}
        onChange={setCustomData}
        client={props.client}
      />
    </FormModal>
  );
}

// ── Small shared bits for this screen's forms ──────────────────────────────

/** Client validation is UX only — the SERVER is authoritative (B8 forms). */
export function premisesEditSchema(t: Translator) {
  return z.object({
    address_line: z.string().trim().min(1, t("metering.premises.field.addressRequired")),
    city: z.string(),
    state: z.string(),
    postal_code: z.string(),
    premises_type: z.string(),
    owner_manager: z.string(),
    external_ref: z.string(),
    // CR-089 wave A `PUJ-19`. Plain strings here on purpose: the RANGE and the
    // number format are the server's refusals (`metering.premises.
    // coordinate_format` / `_range`), and a client rule that disagreed with the
    // server's would refuse a value the server accepts, or the reverse. Client
    // validation on this form is UX only — the header of this function says so.
    lat: z.string(),
    lng: z.string(),
  });
}

/** The ONE bridge from an ApiError to the FormModal envelope shape. */
export function toEnvelope(error: unknown): ServerErrorEnvelope {
  if (isApiError(error)) {
    return formErrorEnvelope(error);
  }
  return { code: "", message_key: "api.error.unexpected" };
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-001@947cf31 (story+rules snapshot hash — EP-MET-01 lead story)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-10 (US-SHL-020 conversion — S14 renders the shared PageHeader; the Premises/Units strip, its per-tab primary action and its per-tab explainer are declared, not drawn)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [US-SHL-020 conversion 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 593 passed / 141 todo across 46 files✔ (567 passed / 138 todo was the pre-conversion baseline) · vite build✔ · run_gates 12 PASS · 0 FAIL · 2 SKIP✔ (G14 prototype-conformance included) · [list-export lane 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ — 296+83 was the pre-W1 baseline and a CONCURRENT Plans & Rates lane is adding to the same suite; this packet contributes 103 passing + 28 todo across 7 files and reduced nothing. The 28 todos are browser-interaction, server/RLS-isolation and unbuilt-neighbour-lane scope, each named in its own test · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E2 US-SHL-020 — the prototype's premises head (UtilityBilling.html line 713) carries NO kicker; this screen rendered `metering.kicker` directly above the H1 and the duplicate is gone (DEF-021, the same defect S9 carried) · E2 `metering.premises.sub` is no longer rendered: BR-SHL-044 (b) puts that guidance in the per-tab explainer BELOW the strip, and `metering.premises.explainer.premises` is the prototype's own sentence for that slot. The catalog key is untouched (catalogs are outside this lane) — retiring it is the PO's call · E2 the prototype's roll-up line is the counts sentence ("428 premises · 1,247 units · 34 vacant · 12 pending activation"); this app serves those counts as the KPIStrip, which stays directly under the header rather than being folded into the roll-up slot — placement delta reported, not changed · E2 the prototype draws "Import CSV" on BOTH tabs; here it renders on the Premises route only, because it opens the PREMISES importer (`?mode=premises_csv`) and US-MET-002's capability row declares no CSV import for units — reported, not invented · E3 CLOSED (list-export lane 2026-08-10): US-MET-001's CSV export (IS-9) is WIRED — the shared DownloadButton posts this screen's request state to POST /exports, the route this trailer previously recorded as missing. What remains open is the DOWNLOAD of the produced file: `result_link` is a `file://` artifact path (IS-11 downloads are the reports W5 story), so the completed state names the file instead of rendering a dead link · E4 the Type filter and the edit form key off the type CODE while the list column renders `premises_type_name`; the server accepts either code or name, and the code is what a shared URL must carry
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
