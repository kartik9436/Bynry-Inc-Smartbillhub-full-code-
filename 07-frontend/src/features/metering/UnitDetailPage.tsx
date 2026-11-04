// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-002 (S15 unit detail — the BR-MET-045 tab set)
//           Screens: S15 (row → detail), links out to S14, S50, S61
// Rules:    BR-MET-036 (occupancy DERIVED — displayed, never editable) ·
//           BR-MET-045 (Unit detail = Overview · Assets · Account history · Plan history · Audit) ·
//           BR-MET-046 (a unit never leaves its premises) ·
//           BR-MET-040/042 (a unit may exist without a plan; a direct edit on an occupied
//           unit is an override the SERVER warns about) · BR-MET-048 (audited server-side) ·
//           BR-SHL-011 (the open tab is URL state) · BR-SHL-034 (one date formatter)
// ───────────────────────────────────────────────────────
// S15 detail. Two of the five tabs render the honest arrives-with state rather
// than an empty table, because an empty table is a CLAIM:
//
//   · **Account history** — the customers module owns no tables in W1.
//   · **Plan history** — BR-CUS-013's `unit_plan_assignments` rows are
//     rating-owned and the metering seam reports `history_recorded: false`
//     while that writer is unwired; no endpoint reads them back at all. The tab
//     shows the unit's CURRENT plan (which the unit row does carry) and names
//     what the history itself is waiting for.
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {useNavigate, useParams, useSearchParams} from "react-router-dom";

import { api } from "@/api/client";
import { CityGisNote, useCityGis } from "@/features/metering/CityGis";
import type { ApiClient } from "@/api/client";
import { z } from "zod";

import {
  getAccounts,
  getAssets,
  getLookupEntries,
  getPlan,
  getSizeBandedServices,
  getUnit,
  getUnitAccount,
  logAssetMaintenance,
  reassignAsset,
  updateUnit,
} from "@/api/endpoints";
import { UnitPricingPanel } from "@/features/customers/UnitPricingPanel";
import type {
  AccountRow,
  AssetRow,
  MaintenanceKind,
  UnitAccountFacts,
  UnitAccountProtection,
  UnitAccountResponse,
  UnitRow,
} from "@/api/endpoints";
import { DateCell, formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import type { MoneyBasis } from "@/components/MoneyCell";
import { MoneyCell } from "@/components/MoneyCell";
import { Kicker, Note } from "@/components/TextBits";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { Button, ButtonLink } from "@/components/Button";
import { Chip } from "@/components/Chip";
import {
  DatePickerField,
  FormModal,
  SelectField,
  TextField,
} from "@/components/FormModal";
import type { FormSubmitOutcome, ServerErrorEnvelope } from "@/components/FormModal";
import { InlineLinkTo, PlainTable, RefusalStrip } from "@/components/Surfaces";
import { DataTable } from "@/components/DataTable";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
// B14 rule 15 — row actions are ICONS with tooltips, and this is the kit's one
// container for them (`DEF-337`: four red words in one cell).
import { RowAction, RowActions } from "@/components/RowActions";
import { PencilIcon } from "@/components/icons";
// CLAUDE.md rule 3 — a quantity is never drawn without its unit.
import { UnitCell } from "@/components/UnitCell";
import { AssetStatusCell, assetDetailPath } from "@/features/assets/assetsShared";
import { Panel } from "@/components/Panel";
import { useToast } from "@/components/Toast";
import { WarningBox } from "@/components/WarningBox";
import {
  MAINTENANCE_KIND_VALUES,
  assetStagesQueryKey,
  legalTargets,
  stageOptionsFrom,
} from "@/features/assets/AssetLifecycleModals";
import { accountDetailPath } from "@/features/customers/customersShared";
// The ELEVEN in seed order, from the one place they are defined for the front
// end. Retyping them here is hard-won law 2 waiting to happen.
import { SERVICE_CODES } from "@/features/rating/ratingShared";
import { planDetailRoute } from "@/features/rating/planDetail/planDetailModel";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { MoveUnitModal } from "./MoveUnitModal";
import { toEnvelope } from "./PremisesListPage";
import { UnitEditModal } from "./UnitEditModal";
import { StatusChangeDialog } from "./StatusChangeDialog";
// ⚠ **IMPORTED, NEVER RE-IMPLEMENTED.** `isMeteredAsset` is the predicate the
// property's Assets tab groups by and `notReadKey` its three not-read
// sentences; a second copy here would be two definitions of *what can be
// read*, which is the shape `DEF-348` cost us for icons.
import {
  AuditTab,
  TabFooterCounts,
  isMeteredAsset,
  notReadKey,
  premisesAssetsQueryKey,
} from "./PremisesDetailPage";
import { UnitPlanModal, unitLabel } from "./UnitsListPage";
import { sizeClassesQueryKey } from "@/features/assets/AssetRegistryPage";
// `DEF-AST-7660` — the size control and its "is it required" question are the
// ASSETS module's (`BR-AST-500`), imported rather than re-typed here. B14 rule
// 43: a piece of UI is built as a COMPONENT; a fourth inline `<SelectField>`
// would be the drift `offersConnectionSize` was centralised to prevent.
import {
  ConnectionSizeField,
  sizeBandedServicesQueryKey,
  sizeRequiredForService,
} from "@/features/assets/assetsShared";
import {
  CELL_FULL,
  DASHBOARD_ROUTE,
  Dash,
  Fact,
  FactList,
  GuardedButton,
  OccupancyCell,
  PREMISES_PERMISSION,
  ServiceTags,
  UNITS_ROUTE,
  detailTabFrom,
  isDenied,
  premisesDetailPath,
  useRegional,
  unitStatusTone,
  ROLE_SYSTEM_ADMIN,
  useAccessCell,
  useTenantRole,
} from "./meteringShared";
import type { DetailTab, RegionalProps } from "./meteringShared";

// ── Pure pieces ────────────────────────────────────────────────────────────

/**
 * **THE SERVICES A UNIT CAN TAKE, IN THE ORDER THE ELEVEN ARE SEEDED.**
 *
 * ⚠ **`SERVICE_CODES` IS THE SEED ORDER AND IS NEVER RETYPED** — hard-won law 2's
 * other half: a hand-typed service list is how an eleventh service fails to
 * appear on screen, silently, and `SignupWizard.tsx` already has one. A code the
 * ordered list does not know (a tenant-added service) sorts to the END rather
 * than being dropped, because dropping it would lose real data.
 *
 * ⚠ **ONE DERIVATION, TWO READERS.** The header's sub-line and the Assign
 * panel's service picker must offer the same six words in the same order — two
 * copies of this sort would drift the first time either was touched, which is
 * the shape this file warns about three times already.
 */
export function servicesInSeedOrder(services: readonly string[]): string[] {
  const order = new Map(SERVICE_CODES.map((code, index) => [code, index]));
  return [...services].sort(
    (a, b) => (order.get(a) ?? SERVICE_CODES.length) - (order.get(b) ?? SERVICE_CODES.length),
  );
}

/**
 * The PRM-03 tab set — **r10's SIX, and the set already matched**:
 * Overview · Assets · Plan · Account · Occupancy · **Audit log**.
 *
 * ⚠ **`DEF-580` IS NOT ABOUT THE SET — IT IS ABOUT WHAT IS INSIDE IT.** The PO,
 * 2026-08-22, with five screenshots: *"Details view of Unit; UI does not match
 * with Prototype"*. The strip was right and the tab BODIES were never compared
 * to the drawing: the header held its three facts in each other's slots, the
 * Assets tab drew a bullet list where r10 draws a table with a heading, a
 * button and a rule callout, and the Plan and Account tabs ended in no action
 * at all where r10 ends each in a named one. The one strip change is the
 * LABEL: `Audit` → `Audit log`, r10's word (`DEF-578`'s other half).
 *
 *   · **Plan** and **Account** are r10's names for the two BR-MET-045 calls
 *     "Plan history" and "Account history", and they are the CURRENT state
 *     rather than a log: r10's Plan tab shows the plan in force and its
 *     schedules, its Account tab shows the account, its balance and its
 *     autopay. Renamed, so the tab and its contents agree. BR-MET-045 carries
 *     the amendment, dated.
 *   · **Occupancy** is the who-held-this-unit timeline, built from
 *     `GET /accounts?f.unit_id=`, which serves the occupant, the account, the
 *     start and the end. r10's closing read and final bill are **DEF-509** and
 *     are not drawn.
 */
export const UNIT_TAB_IDS = [
  "overview",
  "assets",
  "plan",
  "account",
  "occupancy",
  "audit",
] as const;
export const TAB_PARAM = "tab";

export const unitDetailQueryKey = (id: string) => ["units", "detail", id] as const;

/**
 * `DEF-MET-8362` — the unit Assets tab's registry page, keyed by the UNIT and
 * the page it shows. The prefix `["assets", "by-unit", unitId]` is what a
 * write on this unit invalidates, so every page of the tab refetches at once.
 * The defaults are the tab's first page, so a fixture can seed exactly the
 * key the tab asks for without knowing the table's internals.
 */
export const unitAssetsQueryKey = (
  unitId: string,
  page = 1,
  per: number = DEFAULT_PAGE_SIZE,
  dir: "asc" | "desc" = "asc",
) => ["assets", "by-unit", unitId, page, per, dir] as const;

export function unitTabs(t: Translator): DetailTab[] {
  return UNIT_TAB_IDS.map((id) => ({ id, label: t(`metering.units.tab.${id}`) }));
}

/**
 * r10's PRM-03 eyebrow, verbatim: `Unit · 1408 Elm Street · North · Route 3` —
 * the PREMISE this unit sits on, then its area path.
 *
 * The shipped kicker read `Unit · P-00001`: the premise NUMBER where r10 puts
 * the ADDRESS, and no area at all. Every part is omitted when the server did
 * not send it, so a unit on an untagged premise reads `Unit · 1408 Elm Street`.
 *
 * ⛔ The area path is NOT on the unit payload — `UnitRow` carries `premise_no`
 * and `premise_address` and no `area_path` (**DEF-590**), so the third and
 * fourth segments r10 draws are absent rather than fetched with a second
 * request or guessed from the route the unit is read on.
 */
export function unitKicker(unit: UnitRow, t: Translator): string {
  return [t("metering.units.kickerWord"), unit.premise_address ?? unit.premise_no]
    .filter((part) => part !== null && part !== "")
    .join(" · ");
}

/**
 * r10's H1: `Unit A · main house` — the unit's NUMBER and its LABEL, together,
 * because neither alone identifies a unit to a person. The shipped title was
 * the number alone and the label was demoted to the roll-up, which r10 uses for
 * the description instead.
 */
export function unitTitle(unit: UnitRow, t: Translator): string {
  const parts = [unit.unit_no, unit.label].filter(
    (part): part is string => part !== null && part !== "",
  );
  return parts.length === 0 ? t("metering.units.noNumber") : parts.join(" · ");
}

/**
 * r10's sub-line: `1,480 sq ft · Electric + Water + Sewer connected · access:
 * side gate, dog on property`.
 *
 * Two of the three are served — `square_feet` and the `services` set — and are
 * joined the way r10 joins them.
 *
 * ⛔ **THE ACCESS NOTE IS NOT SERVED AND IS NOT INVENTED (`DEF-591`).**
 * `UnitCore` carries no access or instruction field at all; r10's own example
 * ("dog on property") is a field-safety note, and inventing a reassuring blank
 * for it is the one kind of guess that could put a meter reader in front of a
 * dog nobody warned them about.
 */
export function unitSubline(unit: UnitRow, t: Translator): string | null {
  const parts: string[] = [];
  if (unit.square_feet !== null) {
    // r10 groups the thousands (`1,480 sq ft`). `toLocaleString` and not a
    // hand-rolled regex — the same call `importProgress` makes for the same
    // reason: a grouped figure reads as a figure, an ungrouped one as a smear.
    parts.push(t("metering.units.sqFt", { value: unit.square_feet.toLocaleString() }));
  }
  // ⚠ **"AVAILABLE", NOT "CONNECTED" — THE WORD HAD TO MOVE WITH THE SOURCE
  // (DEF-755).** This sentence read "… Electric + Water + Sewer **connected**"
  // and was TRUE while the field came from service points: a service point is
  // a meter's home, so what it listed really was connected. The field now comes
  // from the PREMISES (a unit's services ARE its premises' — PO 2026-08-26),
  // and a unit can have Water available with no meter and nothing connected. So
  // the key changed too: `metering.units.servicesConnected` is retired rather
  // than reworded, because a catalogue entry BEATS a code `defaultValue` — an
  // in-place reword would ship a fix nobody sees in ten languages.
  //
  // `null` (the premises was never asked) draws NO clause at all: a sub-line is
  // a summary, and "not recorded" belongs in the Services fact where it can be
  // read as the state it is, not smuggled into a list of what this unit has.
  if (unit.services !== null && unit.services.length > 0) {
    // ── U6 §1 SUB-LINE 2 — A LIST, IN SEED ORDER, ENDING ON A CLAUSE ────────
    // Drawn page 74, verbatim: *"The services line is a list, in the order the
    // eleven services are defined — `Water · Sewer · Trash · Solar · Battery ·
    // Fire` — not `"Sewer + Battery + Water + Trash + Solar + Fire available"`,
    // where the last word attaches itself to Fire."*
    //
    // ⚠ **THREE THINGS WERE WRONG AND THEY ARE THREE DIFFERENT FAULTS.**
    //   · The SEPARATOR was `+`, which reads as arithmetic on a screen whose
    //     other lines carry money; every other list in this product uses `·`.
    //   · NOTHING SORTED. The order was whatever the premises row happened to
    //     hold, so the same six services read differently on two units of one
    //     building and a clerk could not scan for a service by position.
    //   · The trailing word `available` attached itself to the last service —
    //     *"… Solar + Fire available"* reads as a claim about FIRE. The clause
    //     is set off by an em dash and names what the list is.
    //
    // ⚠ **`SERVICE_CODES` IS THE SEED ORDER AND IS NOT RETYPED HERE** — hard-won
    // law 2's other half and the skill's §12: a hand-typed service list is how
    // an eleventh service fails to appear on screen, silently. A code the
    // ordered list does not know (a tenant-added service) sorts to the END
    // rather than being dropped, because dropping it would lose real data.
    const seeded = servicesInSeedOrder(unit.services);
    parts.push(
      t("metering.units.servicesTheUnitCanTake", {
        // ⚠ **THE COUNT IS SUBSTITUTED AND IS NOT THE WORD `six`.** The frame's
        // "six" is THIS unit's own count, not a constant — a unit offering two
        // services must not say six — so the numeral is the only reading that
        // is right on every row, and it is the only one eleven catalogues can
        // carry without spelling out numbers.
        count: seeded.length,
        // ⚠ `rating.service.*` and NOT `metering.service.*` (DEF-763). The two
        // namespaces disagreed — ten codes against six — and the six-key one is
        // what four screens read, so a unit with Storm water, Solar,
        // Thermal/Heat or Battery printed its slug in this sub-line. One
        // namespace, because two that disagree drift again.
        services: seeded
          .map((service) => t(`rating.service.${service}`, { defaultValue: service }))
          .join(" · "),
      }),
    );
  }
  return parts.length === 0 ? null : parts.join(" · ");
}

/**
 * `F3`'s second tile — **what this unit owes**, in the four answers `C1`'s
 * `OwedCell` gives on the property's Units tab.
 *
 * ⚠ **THERE IS ONE DERIVATION OF THE MONEY AND THIS IS NOT A SECOND ONE.** The
 * figure is `unit.owed`, served by `customers.selectors.owed_for_units` — the
 * same block the accounts list, the S21 header, the units list and the
 * property's Units tab all read. Nothing is computed here. What is written
 * twice is the four-way BRANCH, and it is written twice for a reason the type
 * system forces: `KPIStrip` refuses an unlabelled money tile (`BR-REP-001` —
 * *"a MONEY tile declares `money` instead of `value`"*, with its date basis a
 * REQUIRED field), and a table cell has no such slot. `OwedCell` returns a
 * `<span>`; this returns a `KpiTile`. The shared classifier that would remove
 * even the branch belongs in `meteringShared`, and `OwedCell` lives in a file
 * this wave may not restructure — recorded rather than left implicit.
 *
 * The four, and collapsing any two of them would be a lie about money:
 *   · **a figure** with its currency and its `BR-REP-001` basis;
 *   · **a vacancy** — no occupying account, so nothing was measured at all,
 *     and the tile says who the base charge goes to instead (`BR-MET-094`,
 *     `BR-CUS-170`). **NEVER `0.00`**: a unit whose tenant left still owing has
 *     a CLOSED account `owed_for_units` excludes, and a manufactured zero there
 *     is `DEF-138` word for word;
 *   · **a common area**, which gets its own sentence rather than the vacancy
 *     one (`BR-MET-101`: the flag is what separates the two);
 *   · **could not be read** — the books could not be ASKED, which is a
 *     different statement from *nothing is owed* (`DEF-127`).
 */
export function unitOwedTile(unit: UnitRow, t: Translator): KpiTile {
  const label = t("metering.units.kpi.owed");
  const owed = unit.owed;
  if (owed === undefined) {
    return { id: "owed", label, value: <Dash /> };
  }
  if (owed === null) {
    return {
      id: "owed",
      label,
      value: (
        <span className="met-qualifier" data-owed-state="no-account">
          {t(
            unit.is_common_area
              ? "metering.units.account.commonAreaOwnerBilled"
              : "metering.units.owed.vacantOwnerBilled",
          )}
        </span>
      ),
    };
  }
  if (owed.balance === null || owed.balance_currency === null) {
    return {
      id: "owed",
      label,
      value: (
        <span className="met-qualifier" data-owed-state="unreadable">
          {t("metering.units.owed.unreadable")}
        </span>
      ),
      detail: t("metering.units.owed.unreadableWhy"),
    };
  }
  return {
    id: "owed",
    label,
    money: {
      amount: owed.balance,
      currency: owed.balance_currency,
      // BR-REP-001: the basis is the SERVER's own (`posting`), forwarded. A
      // default typed in here would label a figure with a basis nobody read.
      basis: (owed.balance_basis ?? "posting") as MoneyBasis,
    },
  };
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface UnitDetailPageProps extends RegionalProps {
  client?: ApiClient;
}

export function UnitDetailPage(props: UnitDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  // GIS Lane D (`DEF-MET-10003`, `DEF-INT-10004`) — the unit's point is a City
  // fact; drawn only where a City GIS is in use, with one line if it is broken.
  const city = useCityGis(client);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [planOpen, setPlanOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false); // CR-089 wave F · F6 (PUJ-44)
  const [moveOpen, setMoveOpen] = useState(false); // BR-MET-095 (CR-024)
  const [statusOpen, setStatusOpen] = useState(false); // BR-MET-1164 (CR-089 D2)
  const [planNotice, setPlanNotice] = useState<string | null>(null);
  const unitId = params.unitId ?? "";
  const tabs = unitTabs(translate);
  const active = detailTabFrom(searchParams.get(TAB_PARAM), tabs);
  const { timeZone, dateFormat } = useRegional(props);

  const cell = useAccessCell(PREMISES_PERMISSION, client);
  // CR-089 wave D — the STATUS control is the System Admin's alone
  // (`@require_role(SYSTEM_ADMIN)` on the endpoint), and A4's cell grades a
  // SURFACE rather than one act inside it: a Billing Clerk holds Full on
  // Premises/Accounts and may create and edit, and may NOT change a status.
  // Gating this on the cell would offer them a button that can only 403 —
  // US-MET-013's dispute control has the same shape and the same reason.
  const role = useTenantRole(client);
  const writeBlockedReason = cell === CELL_FULL || cell === null ? null : t("metering.rbac.readOnly");

  const unitQuery = useQuery({
    queryKey: unitDetailQueryKey(unitId),
    queryFn: () => getUnit(unitId, client),
    enabled: unitId !== "",
  });

  function selectTab(id: string): void {
    const next = new URLSearchParams(searchParams);
    next.set(TAB_PARAM, id);
    setSearchParams(next, { replace: true });
  }

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("metering.units.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (unitQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (unitQuery.data === undefined) {
    if (isPermissionDenied(unitQuery.error)) {
      return (
        <PermissionDenied
          helper={t("metering.units.denied")}
          onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
        />
      );
    }
    return (
      <FailedWithRetry
        title={t("metering.units.detail.failedTitle")}
        reason={apiErrorText(unitQuery.error, translate)}
        onRetry={() => void unitQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(UNITS_ROUTE))}
      />
    );
  }

  const unit: UnitRow = unitQuery.data;

  return (
    <div className="met-page">
      {/* US-SHL-020: the same header S14's detail wears — back → kicker → H1 +
          status → roll-up → strip. The arrow belongs to the component, so the
          back LABEL is the destination's own name (TC-5). */}
      <PageHeader
        backTo={{ to: tenantPath(UNITS_ROUTE), label: t("metering.units.title") }}
        // DEF-580 — r10's eyebrow names the PREMISE ADDRESS, its H1 is
        // `Unit A · main house` and its sub-line describes the unit. This
        // screen had the premise NUMBER in the eyebrow, the unit number alone
        // in the H1 and the label in the sub-line: the same facts, each in the
        // wrong slot, exactly as on PRM-02.
        kicker={unitKicker(unit, translate)}
        title={unitTitle(unit, translate)}
        rollup={unitSubline(unit, translate) ?? undefined}
        status={
          <>
            {/* BR-MET-036: the occupancy pill is part of the identity block —
                and it is a pill, not a control. */}
            <OccupancyCell occupancy={unit.occupancy} />
            <StatusPill tone={unitStatusTone(unit.status)}>
              {t(`metering.units.status.${unit.status}`, { defaultValue: unit.status })}
            </StatusPill>
            {/* BR-MET-101: the flag "must be visible everywhere it matters" —
                on the detail it joins the identity block, because "Common" is
                what separates this row from a vacant unit billed to the owner
                (BR-MET-094). r10's word, not a coined one. */}
            {unit.is_common_area && (
              <StatusPill tone="neutral">{t("metering.units.commonArea")}</StatusPill>
            )}
          </>
        }
        // B15 §2A: r10's unit header carries `● Occupied │ ✏ Edit │ ⇄ Move`
        // and — noted in the design because it is unusual — **NO primary
        // button**. So `Move` is a secondary here, and it is a WORD rather than
        // the ⇄ glyph: B14 rule 15's vocabulary is *"only for table actions ;
        // not for buttons"* (PO 2026-08-20). The glyph version of the same
        // action is the row action on the Units list.
        //
        // ── CR-089 wave F · `F6` (`PUJ-44`) — `✏ Edit` IS WIRED NOW ────────
        // ⚠ **THE COMMENT THAT STOOD HERE WAS TRUE WHEN IT WAS WRITTEN AND
        // THEN BECAME THE DEFECT.** It read *"`✏ Edit` is NOT wired here: the
        // unit edit form is the list's modal and it is bound to a list row's
        // refresh"* — an honest deferral, in r10's own button order, which then
        // sat on this screen while a clerk standing on a unit whose label was
        // wrong had to go back to a LIST to fix it. That is hard-won law 2's
        // mirror: not dead UI, but a live capability with no door on the screen
        // where a person needs it. PO 2026-09-08 asked for the door, and for
        // the plan to be applied or changed from the same form.
        //
        // The form is `UnitEditModal`'s, a component of this wave's own, so
        // `UnitsListPage`'s state contract is untouched — and it is EXPORTED so
        // that list can drop its private copy in one line (`DEF-MET-4731`).
        // Order is r10's: `✏ Edit │ ⇄ Move`, both secondaries, because r10's
        // unit header carries NO primary at all (B15 §2A).
        secondaryActions={
          <>
            <GuardedButton
              label={t("metering.action.edit")}
              reason={writeBlockedReason}
              onClick={() => setEditOpen(true)}
            />
            <GuardedButton
              label={t("metering.units.action.move")}
              reason={writeBlockedReason}
              onClick={() => setMoveOpen(true)}
            />
            {/* ── CR-089 wave D · D2 (`PUJ-48`) ──────────────────────────────
                PO 2026-09-08: *"Allow user to cahnge Unit and Premsies
                status"*. This page showed a status pill, offered no way to
                change it, and told the clerk to *"deactivate it and create it
                under the other premise"* — advice for a button nobody had
                built.

                ⚠ **ABSENT FOR ANYONE WHO MAY NOT PRESS IT, NOT GREYED**
                (CR-089's own words). A Billing Clerk holds Full on this surface
                and may not change a status, so the gate is the ROLE and not the
                cell. `null` — the permissions read has not landed — still
                renders it: BR-SHL-025's default is never to guess a role, and
                the endpoint's 403 is the boundary. */}
            {(role === ROLE_SYSTEM_ADMIN || role === null) && (
              <GuardedButton
                label={t("metering.status.action")}
                reason={null}
                // ⚠ **DANGER TIER — the U7/U8/U9 frames draw this control
                // emphasised, and B14 puts that tier on anything that ends
                // service.** Taking a unit out of service stops its billing and
                // its reads; it is the same class of act as a disconnect, and a
                // plain secondary beside `Edit` and `Move` made it look like a
                // third way to change a label (`DEF-MET-4766`).
                danger
                onClick={() => setStatusOpen(true)}
              />
            )}
          </>
        }
        tabs={tabs}
        activeTabId={active}
        tabsLabel={t("metering.units.detail.tabsLabel")}
        onTabSelect={(tab) => selectTab(tab.id)}
      />

      {planNotice !== null && (
        <RefusalStrip role="alert">
          {planNotice}
        </RefusalStrip>
      )}

      {/* ── CR-089 wave F · `F3` — THE FOUR TILES BELONG TO THE PAGE ───────
          PO 2026-09-08, verbatim: *"Kpis you ahve shown on Unit view - these
          KPis will be displayed across all views"*, and `CR-089` §3 reads it
          as the four named here: **Assets · Owed · Plan · Open work**, on all
          six tabs, *"exactly as the header and the tab strip already are"*.

          ⚠ **THE PLACEMENT HALF WAS ALREADY TRUE AND ONLY THE TILES WERE
          WRONG.** This strip has rendered OUTSIDE the tab bodies since
          `US-SHL-020`, so it has always survived a tab change; what it carried
          was `ACCOUNT · PLAN · METERS · SINCE`. Two of those four are the
          ruling's, under other names, and two are not:
            · `METERS` counted `unit.meters`, which has ALWAYS held every asset
              assigned to the unit — a cart and a fire line among them — so the
              NUMBER was right and the WORD was wrong. PO, same round:
              *"Unit → Overview -> Meter = assets"*. It is `Assets` now and it
              splits (`_asset_tile`, server-side, on `BR-AST-004`'s category).
            · `ACCOUNT` moves to the Overview as a whole block (`F2`), where it
              can carry the holder, the status, the money and the deposit
              instead of a number and a name.
            · `SINCE` stays on the Plan tab as *Effective from*, which is the
              same date under the label it has there.
            · `OWED` and `OPEN WORK` are new.

          ⚠ **AND THE COST — `CR-089` §5 flags this as the one ruling whose
          cost grows with tenant size, so it was designed rather than
          discovered.** All three new figures ride `GET /units/{id}`, the
          request this page already makes, so **the tiles cost no extra HTTP
          request on load and none on any of the five tab changes after it**
          (the tab is URL state and React Query serves the cached unit). What
          they cost is three extra queries on that one endpoint, paid by
          nothing else in the product: `unit_list_dict` is untouched, so the
          133-row units list and every internal caller are byte-identical.
          Measured, both numbers, in the wave's report. */}
      <KPIStrip
        kpis={[
          {
            id: "assets",
            label: t("metering.units.kpi.assets"),
            // `assets.total` is the SERVER's count and `unit.meters.length` is
            // the same number from the same read; the served one is used so a
            // payload that ever truncates the list cannot quietly shrink the
            // tile. `undefined` on a payload that predates the key.
            value: unit.assets?.total ?? unit.meters.length,
            detail:
              unit.assets === undefined
                ? undefined
                : // ⚠ **`metered`, NOT `bills` — AND THE KEY'S WORDING MOVED
                  // WITH IT (`DEF-MET-4766`).** The sentence read
                  // `{{bills}} bill · {{behind}} behind the meter`, so English
                  // rendered *"2 bill"* on any unit with more than one metered
                  // asset. The PREMISES tile one screen away has always said
                  // `{{metered}} metered · …` for exactly this concept, which is
                  // also what the frame draws — so this key now carries that
                  // sentence, word for word, in all eleven catalogues. Two tiles
                  // for one concept cannot drift if they hold the same words
                  // (B14 rule 34). The SERVER field is still `bills`; only the
                  // placeholder and the wording changed.
                  t("metering.units.kpi.assetsSplit", {
                    metered: unit.assets.bills,
                    behind: unit.assets.behind,
                  }),
          },
          unitOwedTile(unit, translate),
          {
            id: "plan",
            label: t("metering.units.kpi.plan"),
            value:
              unit.rate_plan_id === null ? (
                <Dash>{t("metering.units.plan.none")}</Dash>
              ) : (
                <PlanNameAndVersion planId={unit.rate_plan_id} client={client} t={translate} />
              ),
          },
          {
            id: "open-work",
            label: t("metering.units.kpi.openWork"),
            // ⚠ **`null` IS *WORK COULD NOT BE ASKED*, AND IT IS DRAWN AS A
            // DASH RATHER THAN A ZERO** (`DEF-075`). A `0` here says *nobody
            // is coming and nobody needs to*, which is a claim; a dash says
            // we do not know, which is the truth when the module is unwired.
            value: unit.open_work?.count ?? <Dash />,
            // ⚠ **A REAL ZERO GETS THE DRAWN SENTENCE; AN UNASKED ONE STILL
            // GETS NOTHING.** The frame draws `nothing booked` under this tile,
            // and it means *work answered, and there is none* — which is not
            // what a missing detail line says and is the opposite of what the
            // dash above means (`DEF-075`: `null` is *work could not be asked*).
            // The sentence is the PREMISES tile's own, already ratified in
            // eleven catalogues for this exact state (B14 rule 34).
            detail:
              unit.open_work?.count === undefined || unit.open_work.count === null
                ? undefined
                : unit.open_work.count === 0
                  ? t("metering.premises.kpi.openWorkNoneBooked")
                  : t("metering.units.kpi.openWorkDetail"),
          },
        ]}
      />

      {active === "overview" && (
        <Panel as="section">
          <h3>{t("metering.units.tab.overview")}</h3>
          <FactList>
            {/* ── CR-089 wave F · `F1` (`PUJ-29`) — THE UNIT'S OWN NUMBER ────
                PO 2026-09-08, verbatim: *"Unit → Overview - you are not
                showing unit ID here"*. It is in the H1 above (`SCW-U-041 ·
                Apt 101`) and it was in the KPI strip, the Plan tab, the
                Account tab and every audit row — and the one panel actually
                headed **Overview**, which is where a person looks for a
                unit's facts, listed the premise, the label, the type and the
                floor and never the number itself. `CR-089` §3 calls it *"the
                same drift that had the property number missing from the
                property page"*.
                ⚠ **IT IS FIRST, ahead of the premise.** The number identifies
                THIS row; the premise says where it sits. A fact list that
                opens with somebody else's identifier reads as a list about
                the building.
                ⚠ **AND `B14` RULE 31 DOES NOT REACH IT.** *"No database ID on
                screen"* is about our uuids; `unit_no` is the SERIES number a
                clerk reads out of `BR-MET-1165`'s allocator and quotes on the
                phone, exactly as `premise_no` and an account number are. */}
            <Fact label={t("metering.units.col.unitNo")}>
              {unit.unit_no ?? <Dash>{t("metering.units.noNumber")}</Dash>}
            </Fact>
            {/* ── U4 FACT ROW 1 — THE BUILDING, WITH ITS STREET *IN* IT ──────
                BR-MET-046: the premises is a LINK, never a picker.
                ⚠ **THE VALUE IS THE ADDRESS AND NOT THE PREMISE CODE**, which
                is the amber block's own defect on the drawn page: *"The Premise
                row shows a code; the street is in the heading above it, so the
                two halves of one fact sit in two places."* The frame answers it
                with one row headed `In this building` whose value is the
                street. `premise_no` survives as the fallback for a building
                whose address was never recorded — a code is better than
                nothing, and it is what a clerk would otherwise have to open the
                building to find.
                ⚠ **AND THE QUALIFIER THAT STOOD HERE IS GONE, BECAUSE IT WAS
                FALSE (`DEF-MET-4696`).** It read *"A unit never moves between
                premises. To relocate it, deactivate it and create it under the
                other premise."* `BR-MET-095` (`CR-024`) superseded that on
                2026-08-21 and this page's own header has carried `Move` since —
                so the sentence told a clerk to do the long way round while the
                short way sat forty pixels above it. The frame draws no
                qualifier on this row at all. Two other call sites still print
                it (`UnitEditModal`, `UnitsListPage`) and stay with
                `DEF-MET-4696`; only the one on this screen is this lane's. */}
            <Fact label={t("metering.units.field.inThisBuilding")}>
              <InlineLinkTo to={tenantPath(premisesDetailPath(unit.premises_id))}>
                {unit.premise_address ?? unit.premise_no ?? t("metering.premises.noNumber")}
              </InlineLinkTo>
            </Fact>
            <Fact label={t("metering.units.col.label")}>
              {unit.label ?? <Dash>{t("metering.services.notRecorded")}</Dash>}
            </Fact>
            <Fact label={t("metering.units.col.type")}>
              {unit.unit_type === null ? (
                <Dash>{t("metering.services.notRecorded")}</Dash>
              ) : (
                t(`metering.units.type.${unit.unit_type}`, { defaultValue: unit.unit_type })
              )}
            </Fact>
            {/* BR-MET-101: the flag as a stated FACT beside the type, because
                `unit_type` may read "Common area" while the FLAG is the
                queryable truth — a reader must be able to see which one this
                row actually carries. */}
            <Fact label={t("metering.units.field.commonArea")}>
              {unit.is_common_area ? (
                <StatusPill tone="neutral">{t("metering.units.commonArea")}</StatusPill>
              ) : (
                t("metering.units.commonAreaNo")
              )}
            </Fact>
            {/* ── U4 FACT ROWS 2 AND 3 — AN ABSENCE IS A WORD, NOT A DASH ────
                The frame draws `Not recorded` in the absent style on both, and
                a bare `—` is the one thing it cannot be read as: a dash reads
                as *this row does not apply*, where the fact is that nobody has
                measured it yet. `Dash` already carries `.met-muted` — italic,
                45% — so what changes is the WORD, not the style, and
                `metering.services.notRecorded` is the sentence this product
                already uses for exactly this.
                ⚠ **AND THE AREA CARRIES ITS UNIT.** `1480` alone is a number
                whose unit a reader has to assume; the frame writes
                `820 sq ft`, the same shape the sub-line and the edit form use,
                through the one composer (`metering.units.sqFt`). The label is
                `Floor area` — `Sq ft` put the unit in the LABEL and left the
                value bare, which is the drawn row inside out. */}
            <Fact label={t("metering.units.col.floor")}>
              {unit.floor_label ?? <Dash>{t("metering.services.notRecorded")}</Dash>}
            </Fact>
            <Fact label={t("metering.units.field.floorArea")}>
              {unit.square_feet === null ? (
                <Dash>{t("metering.services.notRecorded")}</Dash>
              ) : (
                t("metering.units.sqFt", { value: unit.square_feet.toLocaleString() })
              )}
            </Fact>
            <Fact label={t("metering.units.col.services")}>
              <ServiceTags services={unit.services} t={translate} />
            </Fact>
            {/* ── CR-089 wave A `PUJ-27` · `BR-MET-1162` (PO 2026-09-08) ─────
                WHERE THIS UNIT IS, AND WHICH OF THE TWO POINTS IT IS SHOWING.
                ⚠ **THE SECOND HALF IS THE RULE AND NOT A COURTESY.** The PO's
                confirmed reading: *"a unit may carry its own point and parcel,
                and where it does, that is the truth for that unit. Where it
                does not, it uses its building's."* A screen that printed the
                figures without saying which they were would be right about the
                numbers and wrong about the fact — a cabin 300m from its site
                office and a flat in the building read identically.
                ⚠ **THE ADDRESS IS STILL THE BUILDING'S** and is not repeated
                here: only the coordinate clause narrowed. */}
            {city.showCity && (
              <Fact label={t("metering.unit.point.label")}>
                <UnitPointFact unit={unit} client={client} t={translate} />
                <CityGisNote messageKey={city.brokenKey} />
              </Fact>
            )}
            {/* BR-MET-036 spelled out where a user might look for a control. */}
            <Fact label={t("metering.units.col.occupancy")}>
              <OccupancyCell occupancy={unit.occupancy} />
              <span className="met-qualifier"> {t("metering.units.occupancyDerivedNote")}</span>
            </Fact>
          </FactList>

          {/* ── CR-089 wave F · `F2` (`PUJ-28`) — THE ACCOUNT, NOT A NAME ──── */}
          <UnitOverviewAccount
            unit={unit}
            client={client}
            t={translate}
            regional={props}
            onOpenAccountTab={() => selectTab("account")}
          />
        </Panel>
      )}

      {active === "assets" && (
        <UnitAssetsTab
          unit={unit}
          client={client}
          t={translate}
          regional={props}
          writeBlockedReason={writeBlockedReason}
        />
      )}

      {active === "account" && (
        <UnitAccountTab unit={unit} client={client} t={translate} regional={props} />
      )}

      {active === "occupancy" && (
        <UnitOccupancyTab unit={unit} client={client} t={translate} regional={props} />
      )}

      {active === "plan" && (
        <Panel as="section">
          <h3>{t("metering.units.tab.plan")}</h3>
          <FactList>
            {/* DEF-121: this read `unit.default_tariff_id`, a key the server
                has never served — so a unit WITH a plan printed "No plan". The
                served key is `rate_plan_id` (selectors.unit_detail_dict). */}
            <Fact label={t("metering.units.plan.current")}>
              {unit.rate_plan_id === null ? (
                <Dash>{t("metering.units.plan.none")}</Dash>
              ) : (
                <PlanNameAndVersion planId={unit.rate_plan_id} client={client} t={translate} />
              )}
            </Fact>
            {/* ── CR-089 wave H · `H1` (`DEF-MET-4689`, `BR-MET-1167`) ──────
                ⚠ **`namedMonth`, AND IT IS THE FIX RATHER THAN A PREFERENCE.**
                This fact and the pricing panel's own `Effective from` forty
                pixels below it printed THE SAME DATE two ways — `06/01/2026`
                here (the tenant's format) and `2026-06-01` there (the stored
                string) — while the two period boxes underneath printed a third
                and fourth. Each formatter was right on its own, which is
                exactly why nothing caught it: the defect is a property of the
                SCREEN. Every date on this tab now reads `1 Jun 2026`, which
                cannot be read as 6 January.
                ⚠ **THE `ON PLAN SINCE` TILE ABOVE IS THE SAME DATE AND IS NOT
                THIS LANE'S** — the KPI strip belongs to wave F, which is
                rewriting it as this lands. It still prints the tenant format,
                so one date still has two shapes on this page; that half is
                `DEF-MET-4725` and it is filed rather than reached for. */}
            <Fact label={t("metering.units.plan.effectiveFrom")}>
              {unit.plan_effective_from === null ? (
                <Dash />
              ) : (
                <DateCell
                  value={unit.plan_effective_from}
                  timeZone={timeZone}
                  dateFormat={dateFormat}
                  namedMonth={true}
                />
              )}
            </Fact>
            {/* ⚠ **`Rate schedules` IS NAMED AS AN ABSENCE BY THE FRAME**
                (`U6` §15: *"No `Rate schedules` fact row in the plan panel"*),
                and it is an absence for a reason a reader can check: the
                pricing panel below carries `WHAT EACH SERVICE IS PRICED ON`
                with the schedule NAME on every service row, so this fact row
                said the same thing less well and forty pixels higher up.
                `PlanSchedules`, which drew it, had no other caller and is
                deleted (`DEF-GOV-10106`). */}
            {/* ── U6 §5 ROWS 6 AND 7 — A CLAUSE, NEVER A BARE WORD ─────────
                Drawn page 74, verbatim: *"Locked and standby say what they mean
                rather than `No` twice: whether a supervisor is needed, and
                whether anything bills while the unit is empty."*
                ⚠ **TWO ROWS READING `No` ARE INDISTINGUISHABLE**, and they are
                answers to two different questions a clerk cannot reconstruct
                from the label alone. The word stays and carries its consequence
                beside it, in the quiet tier every other qualifier on this page
                uses. */}
            <Fact label={t("metering.units.plan.locked")}>
              {unit.plan_locked ? t("metering.yes") : t("metering.no")}
              <span className="met-qualifier">
                {" "}
                {t(
                  unit.plan_locked
                    ? "metering.units.plan.lockedMeaning"
                    : "metering.units.plan.notLockedMeaning",
                )}
              </span>
            </Fact>
            {/* BR-MET-094 (PO 2026-08-21): a vacant unit IS billed and it is not
                a choice — so this flag is shown as the stored fact it is, and
                the tab does not offer a toggle the ruling removed. */}
            <Fact label={t("metering.units.plan.vacantStandby")}>
              {unit.vacant_standby_auto ? t("metering.yes") : t("metering.no")}
              <span className="met-qualifier">
                {" "}
                {t(
                  unit.vacant_standby_auto
                    ? "metering.units.plan.standbyMeaning"
                    : "metering.units.plan.noStandbyMeaning",
                )}
              </span>
            </Fact>
            {/* ⛔ **r10 PRINTS AN EVALUATED ELIGIBILITY VERDICT — "Passes —
                residential · 5/8" & 1φ 100A · inside city" — AND NOTHING IN THIS
                PRODUCT EVALUATES A RULE.** DEF-404: the rule builder does not
                exist and `eligibility_rule` is stored as authored and read by no
                code at all; `PlanRow.eligibility` carries the ticked boxes and
                its own contract says ADVISORY ONLY, *"nothing anywhere may read
                it as a gate"*. So there is no verdict to print, and a green
                "Passes" against a rule nobody ran is the most dangerous thing
                this screen could say. */}
            {/* ⚠ **THE SECOND AND LAST SITE OF `DEF-584`.** `ArrivesWithField`
                renders a `<div>`, and `FactList` is a `<dl class="met-facts">`
                — a CSS grid of `dt`/`dd` pairs. A grid item that is neither
                still takes a CELL, so the label column grew to the width of a
                full-width dashed callout and every value on this tab was
                squeezed into a ribbon down the right edge. Same construction the
                PO photographed on PRM-02's Overview. The absence is the same
                sentence; it is now the VALUE of its own row. */}
            {/* ── CR-089 wave H · `H2` (`DEF-MET-4693`) ─────────────────────
                ⚠ **THIS SENTENCE USED TO EXPLAIN OUR CODE TO A CLERK**, which
                B14 rule 32 forbids: *"Nothing checks a plan's eligibility rules
                yet. The rules are stored as they were written and no code reads
                them, so there is no result to show here."* True, and about our
                implementation rather than about the clerk's job.
                ⚠ **THE COMMENT BELOW IS STILL THE REASON THERE IS NO VERDICT,
                AND IT IS UNCHANGED.** What moved is who the sentence is written
                for. It is a CONSTANT and not a read of this plan's own
                `eligibility` column, so it is worded to be true of every
                tenant: nothing in this product turns a stored condition into a
                requirement, so no plan asks a customer to prove anything before
                it applies. Reading the plan's own conditions back and naming
                them here is a real improvement and is NOT made — it needs a
                field this panel is not served, and it is recorded on
                `BR-MET-1168` rather than half-built. */}
            <Fact label={t("metering.units.plan.eligibility")}>
              <span className="met-muted" data-tracks="DEF-404">
                {t("metering.units.plan.eligibilityArrivesWith")}
              </span>
            </Fact>
          </FactList>
          {/* CR-034 (PO 2026-08-25, on the live build): *"when i go on this
              screen it should show me what all details from plan are
              applicable"*. The facts above name the plan; they do not UNFOLD
              it — which rate schedule per service, which blocks, which charge
              codes, which taxes.
              ⚠ **THIS PANEL ALREADY EXISTED AND ONLY THE MOVE-IN WIZARD
              MOUNTED IT.** `GET /units/{id}/pricing` has been mounted since
              W5 T5.3 and `UnitPricingPanel` has rendered it since; the unit's
              own Plan tab — the obvious place to ask "what is this unit priced
              on" — never called it. Hard-won law 2 in a third shape: not
              built-and-unwired, but built, wired elsewhere, and missing from
              the screen that needs it. Mounting is the whole change; no new
              endpoint, no new figure.
              ⚠ **IT SHOWS; IT DOES NOT CHOOSE, and it performs NO ARITHMETIC.**
              Every value is a stored one forwarded verbatim from rating's own
              selectors (B4/B5 are ❄️ FROZEN, and a second implementation of
              billing math on a read endpoint is the worst outcome available).
              The WORKED MONTH the PO also asked for is deliberately absent and
              the panel says so: no callable prices a plan outside a bill run —
              `engine.price_bill` is fed by `billing/gather.py`, keyed on an
              ACCOUNT and a service period. That is CR-034 slice (b), its own
              story, unsized. */}
          {/* CR-034 (b) — `showPeriod` is passed HERE and nowhere else. The PO:
              *"showing in - what period you are reporting data for"*. Staff
              asking what a unit is priced on need to be able to ask it of a
              MONTH — a rate filing, a plan change or a size change moves the
              answer, and a screen that could only ever say "today" cannot show
              what a bill for July used. The move-in wizard mounts the same
              panel WITHOUT this prop, because a customer signing up is asking
              what they will pay, not what applied last July.
              ⚠ With no period the panel sends none, and the answer is the one
              it always gave: `as_of` = the tenant's today. No default month is
              invented — see `selectors.unit_pricing` for the calendar case that
              declined one. */}
          {/* ⚠ `showPeriod={true}` AND NOT THE JSX SHORTHAND `showPeriod`. G13 reads a
              caller as `prop=` followed by a brace or a quote, so the shorthand —
              which passes the prop perfectly well — reads to the gate as NOBODY
              PASSING IT, and the panel's period control was reported as dead UI.
              The gate is right to be literal; this is the form it can see. */}
          <UnitPricingPanel
            unitId={unit.id}
            t={translate}
            client={client}
            showPeriod={true}
            planFactsAbove={true}
          />
          {/* ⚠ **THE PLAN-HISTORY ARRIVES-WITH BLOCK IS GONE, AND THE FRAME
              NAMES IT AS AN ABSENCE** (`U6` §15: *"No plan-history arrives-with
              block"*, and §10's budget: *"Nothing else is on screen until asked
              for"*). `BR-CUS-013`'s append-only per-unit assignment history is
              still rating-owned and still read back by no route — `DEF-473` is
              OPEN and unchanged. What went is a paragraph explaining OUR
              implementation to a clerk, which is B14 rule 32's own ban, on a
              tab whose stated budget is one sentence per section. */}
          {/* ── U6 §8 · THE FOOTER BAR'S RIGHT HALF ────────────────────────
              ⚠ **SECONDARY, AND AT THE BOTTOM.** It was a PRIMARY sitting
              ABOVE the pricing panel — so the loudest control on the tab
              interrupted the answer a clerk came for, and `DEF-580`'s note
              above it recorded the tier change as deliberate. The frame draws
              it in the outline tier in a footer bar at the END of the frame,
              and page 75 says why the arrow is right: *"`Change plan →`. An
              arrow, because it opens a chooser rather than writing."*
              ⚠ **THE FRAME'S FOOTER IS ONE ROW WITH THE PERIOD SENTENCE ON ITS
              LEFT, AND THIS IS NOT THAT.** That sentence is rendered by
              `UnitPricingPanel`, which the move-in wizard also mounts;
              composing one row across the two components would put a
              plan-change control inside a panel that must never offer one
              (`BR-CUS-029`). The button is at the bottom, the sentence is at
              the top of the panel, and the divergence is recorded in the
              conformance file rather than solved by moving a control into the
              wizard. */}
          <div className="mt-3">
            <GuardedButton
              label={t("metering.units.action.changePlan")}
              reason={writeBlockedReason}
              variant="secondary"
              onClick={() => setPlanOpen(true)}
            />
          </div>
        </Panel>
      )}

      {active === "audit" && (
        <AuditTab entityType="unit" entityId={unit.id} t={translate} regional={props} />
      )}

      {/* CR-089 wave F · `F6` — the unit's own edit form, with the plan on it.
          ONE `PATCH /units/{id}` carries both, so a refused plan takes the
          label change back with it rather than leaving a clerk with half an
          edit and an error message about the other half. */}
      {editOpen && (
        <UnitEditModal
          unit={unit}
          client={client}
          regional={props}
          onClose={() => setEditOpen(false)}
          onSaved={(warningKey) => {
            // BR-MET-042's override sentence, shown in the SAME strip the plan
            // modal uses — one place a plan warning ever appears on this page.
            setPlanNotice(warningKey === null ? null : t(warningKey));
            setEditOpen(false);
            void unitQuery.refetch();
          }}
        />
      )}

      {/* BR-MET-095 (CR-024) — the same modal the Units list row opens, so the
          two doors cannot drift apart. */}
      {moveOpen && (
        <MoveUnitModal
          client={client}
          unit={unit}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          onClose={() => setMoveOpen(false)}
          onMoved={() => {
            setMoveOpen(false);
            void unitQuery.refetch();
          }}
        />
      )}

      {/* CR-089 wave D · D2 — BR-MET-1164: an open account holds the commit,
          and the attached assets are counted beside it because the clerk is
          about to strand them. */}
      {statusOpen && (
        <StatusChangeDialog
          subject="unit"
          id={unit.id}
          name={unitTitle(unit, translate)}
          client={client}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          onClose={() => setStatusOpen(false)}
          onChanged={() => {
            setStatusOpen(false);
            void unitQuery.refetch();
          }}
        />
      )}

      {planOpen && (
        <UnitPlanModal
          client={client}
          unitIds={[unit.id]}
          title={t("metering.units.plan.title", { unit: unitLabel(unit, translate) })}
          regional={props}
          onClose={() => setPlanOpen(false)}
          onAssigned={(warningKey) => {
            setPlanNotice(warningKey === null ? null : t(warningKey));
            setPlanOpen(false);
            void unitQuery.refetch();
          }}
        />
      )}
    </div>
  );
}

// ── Tab bodies (CR-023 P2) ─────────────────────────────────────────────────

/**
 * PRM-03's **Assets** tab — r10's shape: an `ASSETS ON THIS UNIT` heading with
 * a `+ Assign from inventory` primary beside it, a TABLE, and a `RULE` callout
 * saying what removing a meter does.
 *
 * ⚠ **THIS TAB DREW A BULLET LIST AND SAID THE SAME METER TWICE (`DEF-580`).**
 * The shipped body rendered `MetersCell` (the comma-joined numbers) and then a
 * `<ul>` of the same numbers underneath, inside a full-width bordered box — the
 * PO's screenshot shows `W-5000` printed twice, one above the other, with no
 * type, no install date and no status.
 *
 * ⚠ **AND THE REASON IT DID — *"the registry has a premises filter but NO unit
 * filter"* — WAS TRUE AND WAS NOT THE END OF IT.** `ASSET_FILTERS` still
 * declares no `unit_id`, so a unit's assets cannot be asked for in one query.
 * But every registry ROW carries `assigned_unit_id`, and this unit's premises
 * filter (`f.premises_id`, BR-AST-041) is a query the API DOES answer — the
 * same one PRM-02's Assets tab and its METERS tile already make, so React Query
 * serves all three from one request. Narrowing that answer by
 * `assigned_unit_id` is reading a served field, not inventing a filter.
 *
 * ⛔ **r10's `Last read` COLUMN IS NOT DRAWN — `DEF-592`.** `AssetRow` carries
 * no last read and no read date; the reads live in `meter_reads` and no route
 * joins them onto a registry row. A column of em-dashes under "Last read" is
 * not a blank, it is the sentence *"this meter has never been read"* — which is
 * exactly what a customer disputing a bill would quote back.
 *
 * ✔ **`+ Assign from inventory` IS WIRED (`DEF-593` CLOSED, CR-028 debt
 * sweep).** The button opens an inline searchable picker of the registry's
 * INVENTORY rows (`f.status=unassigned` — the same reserved filter the S49
 * Unassigned view uses); choosing one navigates to the assets module's own
 * full-page reassign (`/assets/:id/reassign?unit=<this unit>`) with THIS unit
 * preselected — the flow stays the assets module's, this tab only opens its
 * door. A role that may not write still gets the disabled-with-reason button
 * (BR-SHL-025), exactly as before.
 */
/**
 * ⚠ **`G1` AND `G2` — THE TWO HALVES OF ONE JOB, AND UNTIL NOW NEITHER WAS
 * HERE.**
 *
 * `G1`. The picker this replaces was a `SearchSelectField` whose placeholder
 * read *"Search inventory by asset #…"*, and that was the whole truth of it:
 * a clerk standing in the depot with a 5/8-inch water meter IN THEIR HAND had
 * to go and find its number somewhere else before they could look for it. The
 * registry has always been able to answer *what kind · what size · what
 * class · what stage*; nothing let a person ASK it in words. It does now —
 * `?terms=` is read by the SERVER against the tenant's own catalogues and the
 * reading comes back as chips (`AssetSearchResolution`).
 *
 * `G2`. Choosing a row used to NAVIGATE to `/assets/:id/reassign?unit=<this
 * unit>` — a one-step job finishing on a different screen, with the clerk
 * losing the unit they were standing on. **Assign ✓** posts the reassign from
 * here and the row appears in the table above.
 *
 * ⚠ **THE CHIPS ARE THE SERVER'S READING AND NOT THIS SCREEN'S.** Drawing them
 * from a client-side guess at what the words mean would let the chips and the
 * rows disagree, silently, forever — `BR-MET-1165`'s lesson one module over: a
 * preview is only true if it walks the loop the thing itself walks. The list
 * below is filtered by `resolved.filters`, and `resolved.chips` is that same
 * object's other half.
 *
 * ⚠ **THE STANDING NARROWING IS `f.assigned=false` AND NOT `f.status=
 * unassigned`, WHICH IS NOT A TIDY-UP.** A stage the clerk TYPES sets
 * `f.status`; if the picker also sent a status of its own, the explicit one
 * would win and the chip would be drawn over rows it did not filter — a chip
 * that lies. Two different keys compose; two values of one key cannot.
 *
 * ⚠ **THE ASSIGN BUTTON IS GATED ON THE ROW'S OWN `actions`** (BR-AST-006,
 * computed server-side), never on a rule copied here. `BR-AST-022` refuses an
 * assign unless the asset is available or in service, and a button that offers
 * what the server will refuse is worse than no button.
 */
export const unitAssignInventoryQueryKey = (terms: string) =>
  ["assets", "inventory-finder", terms] as const;

/** How long the box waits after the last keystroke before it asks the server. */
export const INVENTORY_SEARCH_DEBOUNCE_MS = 300;

/**
 * Take one chip's words back out of the box.
 *
 * ⚠ **THE CHIP'S `terms` IS WHAT IT ATE, NOT WHAT IT IS CALLED.** Typing
 * *5/8 water* matches the size class whose NAME is `Water 5/8"`; removing the
 * chip has to remove the two words the clerk typed, and removing the label
 * would leave the box saying something they never wrote. Exported so the test
 * asserts the same function the × presses.
 */
export function removeChipTerms(text: string, chipTerms: string): string {
  const eaten = chipTerms.toLowerCase().split(/\s+/).filter(Boolean);
  const kept: string[] = [];
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const at = eaten.indexOf(word.toLowerCase());
    if (at >= 0) {
      eaten.splice(at, 1); // one word out per word eaten — never all of them
      continue;
    }
    kept.push(word);
  }
  return kept.join(" ");
}

/**
 * **THE TENANT'S SIZE CATALOGUE, CODE → NAME** — one request, shared by both
 * tables on this tab through `sizeClassesQueryKey`.
 *
 * ⚠ **IT EXISTS BECAUSE THE TWO TABLES DISAGREED WITH EACH OTHER ABOUT THE
 * SAME FACT** (`DEF-MET-6926`). The shelf panel has resolved the code to the
 * tenant's name since it shipped; the on-unit table 250 lines below printed
 * `line.row.size_class` raw, so one screen showed `W-58` in its top table and
 * `Water 5/8"` in its bottom one, for the same meter size. The blueprint
 * (p68) draws `Class 200` and `5/8"` — NAMES — in both.
 *
 * ⚠ **THE COMMENT ON THE OLD CELL IS WHY IT SURVIVED, AND IT IS HARD-WON LAW
 * 1.** It called `size_class` *"the tenant's own code TEXT (`2"`, `Class 200`,
 * `96 gal`), which is a printed reference"*. It is a `service_size_classes`
 * LOOKUP CODE, and on `brazosbend` those codes read `W-58` and `E-1P-100`
 * (measured 2026-09-27). The claim was never checked against a row.
 */
function useSizeClassNames(client: ApiClient, enabled = true) {
  const query = useQuery({
    queryKey: sizeClassesQueryKey,
    queryFn: () => getLookupEntries("service_size_classes", { per: 200 }, client),
    enabled,
    staleTime: 5 * 60 * 1000,
  });
  return new Map((query.data?.results ?? []).map((entry) => [entry.code, entry.name]));
}

/**
 * The connection size a clerk reads: the tenant's NAME for the stored code.
 *
 * ⚠ **THE FALLBACK IS THE STORED VALUE, NEVER BLANK.** `BR-AST-500` keeps a
 * size on a meter that already priced with it after Settings retires the
 * class, so a code the catalogue no longer names must still say something.
 *
 * ⚠ **AND THE TWO EMPTY CASES ARE DIFFERENT SENTENCES** (`DEF-514`, and the
 * asset detail's `MeasurementPanel` settled this first): an em-dash cannot
 * tell *nobody recorded it* from *this thing has no such fact*. A meter with
 * no size is a gap worth closing; a cart has no service connection at all.
 */
function AssetSizeCell(props: { asset: AssetRow | undefined; names: Map<string, string>; t: Translator }) {
  const { asset, t } = props;
  if (asset === undefined) {
    return UNIT_ASSET_ABSENT;
  }
  if (asset.size_class === null || asset.size_class === undefined || asset.size_class === "") {
    const metered = isMeteredAsset(asset);
    return (
      <span data-size-absent={metered ? "unrecorded" : "n-a"}>
        {/* The kit's own absence element, so every quiet value on this tab is
            quiet the same way (B14 rules 43 and 44). */}
        <Dash>
          {t(
            metered
              ? "metering.units.assets.sizeUnrecorded"
              : "metering.units.assets.notMeasured",
          )}
        </Dash>
      </span>
    );
  }
  return <span>{props.names.get(asset.size_class) ?? asset.size_class}</span>;
}

/**
 * **WHAT THIS METER READS IN** — `kgal`, `kWh`, `ccf`.
 *
 * ⚠ **CLAUDE.md HARD RULE 3 IS WHY THIS IS A COLUMN AND NOT A NICETY.** On the
 * shelf table it is often the ONLY thing separating two rows: on `brazosbend`
 * four spare meters carry no size class at all, so `AST-04412`, `AST-04413`,
 * `AST-04414` and `M-5099` all read `Meter · —` — and three of them are water
 * and one is electric. A clerk picking a spare for a water service had nothing
 * on the screen to pick BY (`DEF-MET-6911`, the PO's own report).
 *
 * ⚠ **IT IS NOT THE DRAWN `Service` COLUMN AND DOES NOT PRETEND TO BE.** The
 * blueprint (p68) draws `Service` on this table; a shelf spare STORES no
 * service — `service_point_id` only exists once the asset sits on a unit — and
 * that gap is `OQ-AST-12485`, OPEN. A `Service` column would therefore be a
 * dash on every row forever, which is the PO's own third finding. The unit of
 * measure is the fact the product actually holds, on every measuring spare.
 *
 * ⚠ **A NON-MEASURING ASSET GETS WORDS, NOT A DASH.** `BR-AST-009` binds
 * `MEASURING_TYPES` only, so a cart, a battery or a backflow preventer has no
 * unit and correctly never will. Saying so is the difference between *we did
 * not fill this in* and *this question does not apply here*.
 */
function AssetUomCell(props: { asset: AssetRow | undefined; t: Translator }) {
  const { asset, t } = props;
  if (asset === undefined) {
    return UNIT_ASSET_ABSENT;
  }
  if (!isMeteredAsset(asset)) {
    return (
      <span data-uom-absent="n-a">
        <Dash>{t("metering.units.assets.notMeasured")}</Dash>
      </span>
    );
  }
  if (asset.unit === null || asset.unit === undefined || asset.unit === "") {
    return (
      <span data-uom-absent="unrecorded">
        <Dash>{t("metering.units.assets.uomUnrecorded")}</Dash>
      </span>
    );
  }
  // A unit is a WORD (kgal, kWh, ccf), not a figure — no tabular numerals.
  return <span>{asset.unit}</span>;
}

export function InventoryFinder(props: {
  unit: UnitRow;
  client: ApiClient;
  t: Translator;
  writeBlockedReason: string | null;
  onAssigned: (assetNo: string) => void;
  /**
   * The tab's own `ASSETS ON THIS UNIT` kicker, drawn by this component.
   *
   * ⚠ **IT IS A SLOT AND NOT A DECORATION, AND THE REASON IS LAYOUT.** The
   * trigger belongs on the heading row, right-aligned; the OPEN panel needs the
   * full width of the tab. A component living inside the heading's `ml-auto`
   * span can only ever be one of those, and the first build was — the search
   * box, its chips and a six-column result table were all squeezed into the
   * right half of the screen, over the unit's own table. Found by looking at
   * the screenshot, which is hard-won law 6 and nothing else.
   */
  heading?: ReactNode;
}) {
  const { t, unit } = props;
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [terms, setTerms] = useState("");
  const [refusal, setRefusal] = useState<string | null>(null);
  const [assigning, setAssigning] = useState<string | null>(null);
  /**
   * **WHICH SERVICE THE METER WILL SERVE ON THIS UNIT** (`DEF-MET-5860`).
   *
   * ⚠ **NO DEFAULT, AND THE EMPTY STRING IS THE WHOLE POINT.** PO ruling
   * 2026-09-19, verbatim: *"this is correct fix it"* — against *"**Default:
   * None.** Nothing may guess which service a meter serves"*. A picker that
   * pre-selected the unit's first service would put a water meter on a fire
   * line whenever a clerk pressed `Assign ✓` without reading it, and the
   * service decides what the meter is BILLED as.
   */
  const [service, setService] = useState("");
  /**
   * **THE CONNECTION SIZE THIS INSTALL DECLARES** (`DEF-AST-7660`, the Product
   * Owner's own report: *the clerk cannot set the connection size, so the size
   * column in the unit's table is blank*).
   *
   * ⚠ **A BLANK IS STILL LAWFUL AND THAT IS WHY THERE IS NO DEFAULT.**
   * `BR-AST-500` keeps NULL as a real answer, so nothing here guesses — and on
   * a service whose price BANDS by size the SERVER refuses the assign instead
   * (`assets.size_class_required_for_banded_service`), because whether a
   * service bands is ratified law the browser must not infer (`DEF-3098`).
   *
   * ⚠ **IT RESETS WITH THE ROW, NOT WITH THE PANEL.** A size belongs to the
   * device being assigned, so it is cleared after each successful `Assign ✓`;
   * carrying it to the next row would silently stamp one meter's diameter on
   * the next one a clerk picked off the shelf.
   */
  const [sizeClass, setSizeClass] = useState("");

  // The box asks the server when the typing stops, not on every keystroke.
  useEffect(() => {
    const timer = setTimeout(() => setTerms(text), INVENTORY_SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text]);

  // B14 rule 31 — the ratified size classes by NAME. The row carries the CODE
  // (`W-58`), which is a filter value and not a thing to put in front of a
  // clerk; the chip above already reads *Water 5/8"* and the column must agree
  // with it. One request, shared with the registry's own size picker.
  const sizeNames = useSizeClassNames(props.client, open);

  /** The tenant's ratified size classes, as the picker's OPTIONS — the same
   *  request `sizeNames` above reads for the column, so opening this panel
   *  costs no second call. */
  const sizeClassesQuery = useQuery({
    queryKey: sizeClassesQueryKey,
    queryFn: () => getLookupEntries("service_size_classes", { per: 200 }, props.client),
    enabled: open,
    staleTime: 5 * 60 * 1000,
  });

  /** ⚠ **WHICH SERVICES BAND IS THE SERVER'S ANSWER** (`DEF-AST-7660`). The
   *  browser may not derive it: *"this service has size classes, so it must
   *  band"* is `DEF-3098`'s retired proxy and would refuse a solar install
   *  over a size solar does not have. */
  const bandedQuery = useQuery({
    queryKey: sizeBandedServicesQueryKey,
    queryFn: () => getSizeBandedServices(props.client),
    enabled: open,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const sizeRequired = sizeRequiredForService(bandedQuery.data, service);

  const finderQuery = useQuery({
    queryKey: unitAssignInventoryQueryKey(terms.trim()),
    queryFn: () =>
      getAssets(
        { terms: terms.trim(), filters: { assigned: "false" }, per: 50 },
        props.client,
      ),
    enabled: open,
    staleTime: 60 * 1000,
  });

  const assign = useMutation({
    mutationFn: (asset: AssetRow) =>
      reassignAsset(
        asset.id,
        {
          unit_id: unit.id,
          record_final_read: false, // a shelf row has no read to take
          // ⚠ **THE SERVICE IS WHAT CREATES THE SERVICE POINT, AND WITHOUT IT
          // THE METER LANDS UNBILLABLE.** `_reassign_inner` has read `service`
          // and called `ensure_service_point` since the module shipped; this
          // screen posted `{unit_id, record_final_read}` and nothing else, so
          // `asset.service_point_id` stayed null and the tab's `Service` column
          // drew a dash on every meter a clerk assigned (`DEF-MET-5860`). The
          // capability was never missing — the ASK was. Hard-won law 2.
          //
          // Omitted rather than sent empty when nothing is chosen: the server
          // branches on truthiness, and a non-measuring asset — a backflow
          // preventer, a cart — takes no service at all and must not be made
          // to declare one (`BR-AST-009` binds `MEASURING_TYPES` only).
          ...(service === "" ? {} : { service }),
          // ⚠ **THE FACT THE BASE CHARGE IS PRICED ON** (`BR-RAT-108`,
          // `DEF-AST-7660`). Omitted rather than sent empty, for the same
          // reason `service` is: the server branches on truthiness, a blank
          // size is a lawful answer on a service that does not band
          // (`BR-AST-500`), and `""` would read as an instruction to clear
          // one the device already carries.
          ...(sizeClass === "" ? {} : { size_class: sizeClass }),
        },
        props.client,
      ),
    onMutate: (asset: AssetRow) => {
      setRefusal(null);
      setAssigning(asset.id);
    },
    onSuccess: (_result, asset: AssetRow) => {
      // ⚠ THE UNIT'S OWN PAYLOAD IS THE SPINE OF THE TABLE ABOVE (`unit.meters`),
      // so invalidating only the registry answer would leave the new row
      // invisible until a reload — the assign would look like it did nothing.
      void queryClient.invalidateQueries({ queryKey: unitDetailQueryKey(unit.id) });
      void queryClient.invalidateQueries({
        queryKey: premisesAssetsQueryKey(unit.premises_id),
      });
      void queryClient.invalidateQueries({ queryKey: ["assets", "by-unit", unit.id] });
      void queryClient.invalidateQueries({ queryKey: ["assets", "inventory-finder"] });
      // `DEF-AST-7660` — the size belongs to the DEVICE just assigned, so it
      // is cleared with the row. Carrying it would stamp one meter's diameter
      // on the next one picked off the shelf, silently and billably.
      setSizeClass("");
      props.onAssigned(asset.asset_no);
    },
    onError: (error: unknown) => setRefusal(apiErrorText(error, t)),
    onSettled: () => setAssigning(null),
  });

  // BR-SHL-025: a role that may not write keeps the disabled-with-reason button.
  const headingRow = (trailing: ReactNode) => (
    <div className="mb-3 flex flex-wrap items-center gap-3">
      {props.heading}
      <span className="ml-auto">{trailing}</span>
    </div>
  );
  if (props.writeBlockedReason !== null) {
    return headingRow(
      <GuardedButton
        label={t("metering.units.action.assignFromInventory")}
        reason={props.writeBlockedReason}
        variant="primary"
        onClick={() => undefined}
      />,
    );
  }
  if (!open) {
    return headingRow(
      <GuardedButton
        label={t("metering.units.action.assignFromInventory")}
        reason={null}
        variant="primary"
        onClick={() => setOpen(true)}
      />,
    );
  }

  const resolved = finderQuery.data?.resolved;
  const rows: readonly AssetRow[] = finderQuery.data?.results ?? [];
  return (
    <section className="mb-6 w-full" data-inventory-finder={unit.id}>
      {headingRow(
        <GuardedButton
          label={t("forms.cancel")}
          reason={null}
          onClick={() => {
            setOpen(false);
            setText("");
            setService("");
            setSizeClass("");
            setRefusal(null);
          }}
        />,
      )}
      <div className="max-w-measure">
        <TextField
          id="inventory-finder"
          label={t("metering.units.assets.findLabel", { unit: unitLabel(unit, t) })}
          value={text}
          onChange={setText}
          placeholder={t("metering.units.assets.findPlaceholder")}
          help={t("metering.units.assets.findHelp")}
        />
        {/* ⚠ **THE ASK THE PO RULED IN, AND IT OFFERS THIS UNIT'S SERVICES
            ONLY** — `unit.services` is the PREMISES' `services_available`
            inherited by the unit (`BR-MET-1161`), which is the same list the
            header's sub-line reads and the same bound the server enforces:
            `ensure_service_point` refuses a service the address does not offer
            (`BR-MET-119`) and one the utility does not sell (`BR-MET-003`).
            Offering all eleven would draw choices the server would refuse.

            ⚠ **`rating.service.*` AND NOT `metering.service.*`** — the two
            namespaces disagreed, ten codes against six, and the six-key one is
            what printed a raw slug for Storm water, Solar, Thermal/Heat and
            Battery (`DEF-763`). Fire is the eleventh and reaches the screen
            through `SERVICE_CODES` rather than a list typed here (`CR-063`).

            ⚠ **NO `help` LINE.** B14 rule 33: rationale — *why a meter needs a
            service* — is ZERO words on screen. The row's own refusal says what
            to do, and the frame's §10 allows no prose beyond the consequence
            line. `required` is not set either, because the requirement is
            conditional: it binds meters and sub-meters and not a cart, so it
            is stated per row where the condition can actually be read. */}
        <SelectField
          id="inventory-finder-service"
          label={t("assets.col.service")}
          value={service}
          onChange={setService}
          placeholder={t("metering.units.assets.servicePlaceholder")}
          options={servicesInSeedOrder(unit.services ?? []).map((code) => ({
            value: code,
            label: t(`rating.service.${code}`, { defaultValue: code }),
          }))}
        />
        {/* ⚠ **THE FIELD `DEF-AST-7660` IS.** Until 2026-09-28 this panel drew
            the two controls above and nothing else, so a meter assigned from
            the shelf kept whatever size it arrived with — for every meter the
            add wizard let through blank, that is NONE — and the unit's own
            SIZE column read *no size recorded* on a service whose base charge
            is picked by exactly that fact (`BR-RAT-108`). The refusal then
            arrived months later inside a bill run, as `SizeNotServed`.

            ⚠ **REQUIRED IS READ FROM THE SERVER, NEVER INFERRED HERE.**
            `sizeRequiredForService` consults the list `GET /assets/size-banded-
            services` sent; the server refuses the same case by name, so the
            mark on the label and the refusal cannot disagree.

            ⚠ **AND NOT BLANKET-REQUIRED.** On water, electric, gas, trash and
            fire it is required; on solar, battery, storm water, broadband and
            sewer the blank is the right answer and the field stays optional.
            Before a service is chosen it is optional too — there is nothing
            yet to judge it against. */}
        <ConnectionSizeField
          id="inventory-finder-size"
          value={sizeClass}
          onChange={setSizeClass}
          sizeClasses={sizeClassesQuery.data?.results ?? []}
          required={sizeRequired}
          t={t}
        />
      </div>

      {/* The words the server understood, each removable. B14 rule 31: the
          catalogue CODE never reaches the screen — only the tenant's name. */}
      {resolved !== undefined && resolved.chips.length > 0 && (
        <p
          className="mt-2 flex flex-wrap items-center gap-2"
          data-finder-chips=""
          data-testid="finder-chips"
        >
          {resolved.chips.map((chip) => (
            <span
              key={`${chip.key}:${chip.value}`}
              data-finder-chip={chip.key}
              className="inline-flex items-center gap-1 border border-neutral-300 px-2 py-1 text-sm"
            >
              {chip.label}
              <button
                type="button"
                className="btn btn-icon"
                aria-label={t("metering.units.assets.findChipRemove", { term: chip.label })}
                onClick={() => setText(removeChipTerms(text, chip.terms))}
              >
                ✕
              </button>
            </span>
          ))}
        </p>
      )}
      {/* A word nothing matched is SAID, never dropped: silence here reads as
          "we searched for that", and we did not. */}
      {resolved !== undefined && resolved.unmatched.length > 0 && (
        <p className="mt-1 text-sm text-neutral-700" role="note" data-finder-unmatched="">
          {t("metering.units.assets.findUnmatched", { terms: resolved.unmatched.join(", ") })}
        </p>
      )}

      {refusal !== null && <RefusalStrip>{refusal}</RefusalStrip>}

      {finderQuery.isPending ? (
        <LoadingSkeleton variant="table" />
      ) : rows.length === 0 ? (
        <p className="mt-2 met-panel-hint" role="note">
          {t("metering.units.assets.findEmpty")}
        </p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          {/* B14 rule 32 — one sentence, and it says which table this is. Two
              tables now stand on this tab and a reader has to be able to tell
              *what is on the shelf* from *what is on the unit* at a glance. */}
          <p className="m-0 mb-1 flex items-baseline gap-2">
            <span className="font-heading text-base font-semibold">
              {t("metering.units.assets.findResults")}
            </span>
            <span className="tabular-nums font-bold" data-finder-count="">
              {rows.length}
            </span>
          </p>
          <PlainTable>
            <thead>
              <tr>
                <th>{t("metering.units.assets.col.asset")}</th>
                <th>{t("metering.units.assets.col.type")}</th>
                {/* ⚠ **`Size`, NOT `Connection size`** — the blueprint (p68)
                    draws one column headed `Size` on this table, the on-unit
                    table above already says `Size`, and B14 rule 36 asks for
                    one word per thing across the product rather than one per
                    table. The conformance file's §14 has specified this since
                    it was written: *"No `Meter type` or `Connection size`
                    columns in the inventory panel; `Size` is one column."* */}
                <th>{t("assets.col.size")}</th>
                {/* ⚠ **THE UNIT OF MEASURE — CLAUDE.md HARD RULE 3.** See
                    `AssetUomCell`: it is what tells a `kgal` spare from a
                    `kWh` one when neither carries a size, which on this
                    tenant is four rows out of ten. */}
                <th>{t("assets.col.uom")}</th>
                <th>{t("assets.col.meterType")}</th>
                <th>{t("metering.units.col.status")}</th>
                <th>{t("metering.units.assets.col.assign")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((asset) => (
                <tr key={asset.id} data-finder-row={asset.asset_no}>
                  <td>
                    <InlineLinkTo to={tenantPath(assetDetailPath(asset.id))}>
                      {asset.asset_no}
                    </InlineLinkTo>
                  </td>
                  <td>{asset.type_name}</td>
                  <td>
                    <AssetSizeCell asset={asset} names={sizeNames} t={t} />
                  </td>
                  <td>
                    <AssetUomCell asset={asset} t={t} />
                  </td>
                  <td>
                    {asset.meter_type_name ?? (
                      /* ⚠ WORDS, NOT A DASH, FOR THE SAME REASON THE TWO
                         CELLS BESIDE IT CARRY THEM: a cart has no meter type
                         and never will (`BR-AST-044` classification 2 is null
                         on non-measuring types), so the dash was answering
                         *we do not know* to a question that does not apply. */
                      <span data-meter-type-absent="n-a">
                        <Dash>{t("metering.units.assets.notMeasured")}</Dash>
                      </span>
                    )}
                  </td>
                  <td>{asset.status_name}</td>
                  <td>
                    <GuardedButton
                      label={t("metering.units.assets.assignRow")}
                      // BR-AST-006/022: the server says which states may be
                      // assigned; this reads its answer rather than repeating
                      // the rule. A row that cannot be assigned keeps the
                      // button and says why (BR-SHL-025).
                      //
                      // ⚠ **AND A METER WITH NO SERVICE CHOSEN CANNOT BE
                      // PRESSED AT ALL** (`DEF-MET-5860`, `BR-AST-009`). The
                      // frame's own STATES block puts this refusal exactly
                      // here — *"Refused before the press, IN THE ROW"* — and
                      // unreachable beats refused-after-the-fact: a server
                      // refusal would bounce the clerk back to an empty shelf
                      // with their search gone.
                      //
                      // ⚠ **`isMeteredAsset` IS IMPORTED, NEVER RE-IMPLEMENTED,
                      // AND IT IS NOT A HAND-TYPED LIST.** It reads
                      // `BR-AST-004`'s category — the `meters` and `sub_meters`
                      // tabs — and on this tenant's thirteen seeded asset types
                      // that set is EXACTLY the server's `MEASURING_TYPES`
                      // (`meter`, `net_meter`, `sub_meter`), measured
                      // 2026-09-19. A backflow preventer, a cart, a PV panel
                      // and a battery are behind-the-meter and keep today's
                      // one-press assign with no service, which is the ruling:
                      // required for meters and sub-meters, optional for
                      // everything else.
                      reason={
                        !asset.actions.includes("assign")
                          ? t("metering.units.assets.assignNotAvailable")
                          : isMeteredAsset(asset) && service === ""
                            ? t("metering.units.assets.serviceFirst")
                            : null
                      }
                      working={assigning === asset.id}
                      // ⚠ `sm`, NOT `row`: the kit's `row` tier is a FIXED
                      // 32×32 icon box, so a two-word label wraps inside it —
                      // the first build shipped `Assign` over `✓` on two lines.
                      size="sm"
                      onClick={() => assign.mutate(asset)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      )}
    </section>
  );
}

/**
 * `G3` — an attached asset's STATUS changes from its own row.
 *
 * PO 2026-09-08, verbatim: *"ALso allow user to change status of assets
 * atatched to unit - during the edit process"*. Until this landed there was no
 * way to do it from the unit at all: the Assets tab drew a status column and
 * offered no control anywhere on the page, so a meter found faulty by the
 * person standing at the unit had to be found again in the asset registry.
 *
 * ⚠ **IT POSTS `POST /assets/{id}/maintenance`, WHICH IS NOT A DETOUR — IT IS
 * WHERE A STATUS CHANGE LIVES.** `BR-AST-018` makes the entry append-only and
 * `BR-AST-020` makes the transition legal-from-the-current-stage only; the
 * endpoint takes the date and the reason WITH the new stage and writes
 * `asset.status_changed` to the audit trail beside the entry. A `PATCH` of the
 * status column would have skipped every one of those.
 *
 * ⚠ **THE CHOICES ARE `legalTargets`, THE ASSETS MODULE'S OWN MIRROR OF THE
 * SERVER'S TRANSITION LAW** — not a list assembled here. On this tenant's
 * seeded stages that means an *Installed* meter offers exactly one target,
 * *Needs repair*, and the form says so rather than pretending to offer five.
 * The server re-checks and its 409 is what governs.
 *
 * ⚠ **RETIRE IS NOT ONE OF THEM AND MUST NOT BE.** `BR-AST-020/030` makes it
 * terminal and `BR-AST-032` makes it the System Admin's, through its own
 * wizard with a reason, a date and a book-value treatment. Offering *Retired*
 * in this little form would be a one-click irreversible act on a screen about
 * a flat.
 */
export function AttachedAssetStatusModal(props: {
  unit: UnitRow;
  asset: AssetRow;
  client: ApiClient;
  t: Translator;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onDone: (assetNo: string, statusName: string) => void;
}) {
  const { t, asset } = props;
  const queryClient = useQueryClient();
  const [values, setValues] = useState({
    status: "",
    kind: "repair" as MaintenanceKind,
    date: "",
    detail: "",
  });

  const stagesQuery = useQuery({
    queryKey: assetStagesQueryKey,
    queryFn: () => getLookupEntries("asset_statuses", { per: 200 }, props.client),
    staleTime: 5 * 60 * 1000,
  });
  const stages = stageOptionsFrom(stagesQuery.data?.results);
  const targets = legalTargets(stages, asset.status).filter(
    (stage) => stage.code !== asset.status,
  );

  return (
    <FormModal
      title={t("metering.units.assets.statusTitle", { asset: asset.asset_no })}
      kicker={t("metering.units.assets.statusKicker", { status: asset.status_name })}
      schema={attachedAssetStatusSchema(t)}
      values={values}
      submitLabel={t("metering.units.assets.statusSubmit")}
      onClose={props.onClose}
      onSubmit={async (): Promise<FormSubmitOutcome> => {
        try {
          const result = await logAssetMaintenance(
            asset.id,
            {
              kind: values.kind,
              detail: values.detail.trim(),
              date: values.date,
              status: values.status,
            },
            props.client,
          );
          void queryClient.invalidateQueries({ queryKey: unitDetailQueryKey(props.unit.id) });
          void queryClient.invalidateQueries({
            queryKey: premisesAssetsQueryKey(props.unit.premises_id),
          });
          void queryClient.invalidateQueries({
            queryKey: ["assets", "by-unit", props.unit.id],
          });
          const landed =
            stages.find((stage) => stage.code === result.resulting_status)?.name ??
            result.resulting_status;
          props.onDone(asset.asset_no, landed);
          props.onClose();
          return { ok: true };
        } catch (error) {
          // The server's own refusal, unchanged — an illegal transition is
          // BR-AST-020's 409 and it names the two stages.
          return { ok: false, error: toEnvelope(error) as ServerErrorEnvelope };
        }
      }}
    >
      {targets.length === 0 ? (
        // BR-AST-020 with nowhere to go is a real state — a retired meter, or a
        // tenant whose stages have no edge out of this one. Said, not hidden.
        <p role="note" className="met-panel-hint">
          {t("metering.units.assets.statusNoTargets", { status: asset.status_name })}
        </p>
      ) : (
        <SelectField
          id="status"
          label={t("metering.units.assets.statusField")}
          value={values.status}
          required
          placeholder={t("metering.units.assets.statusPlaceholder")}
          help={t("metering.units.assets.statusHelp")}
          options={targets.map((stage) => ({ value: stage.code, label: stage.name }))}
          onChange={(status) => setValues({ ...values, status })}
        />
      )}
      <SelectField
        id="kind"
        label={t("metering.units.assets.statusKind")}
        value={values.kind}
        options={MAINTENANCE_KIND_VALUES.map((kind) => ({
          value: kind,
          label: t(`assets.maintenance.kind.${kind}`),
        }))}
        onChange={(kind) => setValues({ ...values, kind: kind as MaintenanceKind })}
      />
      <DatePickerField
        id="date"
        label={t("metering.units.assets.statusDate")}
        value={values.date}
        dateFormat={props.dateFormat}
        help={t("metering.units.assets.statusDateHelp")}
        required
        onChange={(date) => setValues({ ...values, date })}
      />
      <TextField
        id="detail"
        label={t("metering.units.assets.statusReason")}
        value={values.detail}
        required
        help={t("metering.units.assets.statusReasonHelp")}
        onChange={(detail) => setValues({ ...values, detail })}
      />
    </FormModal>
  );
}

/** Client validation is UX only — the SERVER is authoritative (B8). */
export function attachedAssetStatusSchema(t: Translator) {
  return z.object({
    status: z.string().trim().min(1, t("metering.units.assets.statusRequired")),
    kind: z.string(),
    date: z.string().trim().min(1, t("metering.units.assets.statusDateRequired")),
    detail: z.string().trim().min(1, t("metering.units.assets.statusReasonRequired")),
  });
}

/**
 * `U5` — one row per asset on this unit, in the SIX drawn columns.
 *
 * ⚠ **`DataTable`, NOT `PlainTable`, AND THAT IS THE FRAME'S OWN WORD**
 * (`CR-089-p067-unit-assets.md` §11): *"`DataTable` and `FilterBar`, NOT
 * `PlainTable`. This is the same naming the premises half found five screens
 * away (`DEF-4739`): the shared table is what carries search, filters, the
 * column chooser, pagination and the footer counts."* A `PlainTable` is a
 * `<table>` and nothing else, so this tab had no column chooser, no pager and
 * no footer count — furniture B14 puts on every list table.
 *
 * ⚠ **NO `searchFields` AND NO `filters` ARE DECLARED, DELIBERATELY.** The
 * frame draws a consequence bar above this table and a toolbar on the
 * INVENTORY panel below it; `BR-SHL-010` is explicit that a list declaring no
 * filters gets no filter UI at all, so declaring one to "use FilterBar" would
 * put furniture on screen the drawing does not have.
 *
 * ⚠ **THREE COLUMNS ARRIVED THAT WERE SERVED ALL ALONG** — `Service`, `Size`
 * and `Last read`. Every one is on the registry row this tab already holds,
 * every one has a catalogue key nothing read, and the premises Assets tab five
 * screens away draws all three. That is `DEF-4740`'s shape a second time.
 */
export function UnitAssetsTab(props: {
  unit: UnitRow;
  client: ApiClient;
  t: Translator;
  regional: RegionalProps;
  writeBlockedReason: string | null;
}) {
  const { t, unit } = props;
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const { timeZone, dateFormat } = useRegional(props.regional);
  const [statusFor, setStatusFor] = useState<AssetRow | null>(null);
  const [state, setState] = useState<TableRequestState>(() => ({
    q: "",
    sort: "asset",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  }));
  // One request for the tenant's size catalogue, shared with the shelf panel
  // below through `sizeClassesQueryKey` — so both tables name a size the same
  // way and cannot drift apart again (`DEF-MET-6926`).
  const sizeNames = useSizeClassNames(props.client);
  // ⚠ **`DEF-MET-8362` — THE UNIT'S OWN ASSETS, ASKED OF THE SERVER, ONE PAGE
  // AT A TIME.** This read used to be the PREMISES' registry at a fixed
  // `per: 200`, narrowed here by `assigned_unit_id`. Once a premises held more
  // than 200 assets (the J71 walk's bulk cart upload put ~1,000 on 1408 Elm
  // St), any unit whose asset numbers sorted past row 200 found no registry
  // row and drew '—' for service, size and status. `f.unit_id` narrows by the
  // unit's CURRENT seat in SQL and the page is the table's own (NFR-3), so no
  // premises is ever too big for its units. `f.status=all` because the tab
  // lists everything seated on the unit, whatever stage it is at.
  const dir: "asc" | "desc" = state.dir === "desc" ? "desc" : "asc";
  const assetsQuery = useQuery({
    queryKey: unitAssetsQueryKey(unit.id, state.page, state.per, dir),
    queryFn: () =>
      getAssets(
        {
          filters: { unit_id: unit.id, status: "all" },
          sort: "asset_no",
          dir,
          page: state.page,
          per: state.per,
        },
        props.client,
      ),
    enabled: unit.id !== "",
  });

  // The server's page IS the spine now. The unit payload's `meters` still
  // carries the one fact the registry row does not — the `(sub)`/`(master)`
  // qualifier — so it is joined by id. The `assigned_unit_id` check is a
  // guard on the answer, not the narrowing: the server has already narrowed.
  const refs = new Map(unit.meters.map((meter) => [meter.id, meter]));
  const page: UnitAssetLine[] = (assetsQuery.data?.results ?? [])
    .filter((asset) => asset.assigned_unit_id === unit.id)
    .map((asset) => ({
      id: asset.id,
      meter: refs.get(asset.id) ?? {
        id: asset.id,
        asset_no: asset.asset_no,
        qualifier: null,
        tab: asset.tab,
      },
      row: asset,
    }));

  const config: TableConfig<UnitAssetLine> = {
    screenId: "PRM-03.assets",
    getRowId: (line) => line.id,
    defaultSort: { sort: "asset", dir: "asc" },
    columns: [
      {
        key: "asset",
        // ⚠ **`Asset`, WHERE THE FRAME HEADS THIS COLUMN `Meter`** — recorded
        // in the conformance file rather than followed. The frame's two drawn
        // rows are both meters, but this table carries everything ON the unit,
        // a trash cart and a fire line included, and a column headed `Meter`
        // over a cart is wrong in a way the drawing never had to consider. The
        // premises Assets tab — the same data, the same module, landed the same
        // week — says `Asset`, and B14 rule 36 asks for one word per thing
        // across the product rather than one per screen.
        label: t("metering.units.assets.col.asset"),
        identity: true,
        sortable: true,
        cell: (line) => (
          <span>
            {line.meter.id === null ? (
              line.meter.asset_no
            ) : (
              <InlineLinkTo to={tenantPath(assetDetailPath(line.meter.id))}>
                {line.meter.asset_no}
              </InlineLinkTo>
            )}
            {line.meter.qualifier !== null && (
              <span className="met-qualifier">
                {" "}
                {t(`metering.meters.qualifier.${line.meter.qualifier}`, {
                  defaultValue: line.meter.qualifier,
                })}
              </span>
            )}
          </span>
        ),
      },
      {
        // SERVED all along and never drawn. The name comes from
        // `rating.service.<code>` — THE service-name catalogue in this product,
        // not `metering.service.*`, which holds six of the eleven (`DEF-763`).
        key: "service",
        label: t("assets.col.service"),
        cell: (line) =>
          line.row?.service === null || line.row?.service === undefined || line.row.service === ""
            ? UNIT_ASSET_ABSENT
            : t(`rating.service.${line.row.service}`, { defaultValue: line.row.service }),
      },
      {
        // `BR-AST-500`'s size class, rendered as the tenant's NAME for the
        // stored code (`AssetSizeCell`).
        //
        // ⚠ **THIS CELL PRINTED THE RAW CODE UNTIL `DEF-MET-6926`, AND THE
        // COMMENT THAT STOOD HERE IS WHY NOBODY LOOKED.** It read: *"the
        // tenant's own code TEXT (`2"`, `Class 200`, `96 gal`), which is a
        // printed reference and never a database id"*. `size_class` is a
        // `service_size_classes` LOOKUP CODE — on `brazosbend` it reads
        // `W-58` and `E-1P-100`, measured 2026-09-27 — so this table said
        // `W-58` while the shelf panel on the SAME SCREEN said `Water 5/8"`
        // for that same meter size, and the blueprint (p68) draws the name in
        // both. Hard-won law 1: a comment claiming a guarantee is not the
        // guarantee.
        //
        // ⚠ **AND THE TEST FIXTURE AGREED WITH THE COMMENT, WHICH IS HOW IT
        // PASSED.** `UnitAssetsColumns.dom.test.tsx` seeds `size_class: '5/8"'`
        // — already a display string, a value production never holds. A
        // fixture that encodes the belief under test cannot test it; the cases
        // in `UnitAssetsUom.dom.test.tsx` seed the CODE and assert the NAME.
        key: "size",
        label: t("assets.col.size"),
        cell: (line) => <AssetSizeCell asset={line.row} names={sizeNames} t={t} />,
      },
      {
        // ⚠ **A PILL, NOT PLAIN TEXT.** `AssetStatusCell` is the registry's own
        // cell and it also carries `BR-AST-007`'s derived Test-due chip, which
        // is the one date on this tab with a deadline attached.
        key: "status",
        label: t("metering.units.col.status"),
        cell: (line) =>
          line.row === undefined ? UNIT_ASSET_ABSENT : <AssetStatusCell row={line.row} t={t} />,
      },
      {
        // ⚠ **`On since`, NOT `Installed`** — the frame's §14 names `Installed`
        // as an absence and `On since` as the drawn date column.
        //
        // ⚠ **AND IT READS `assigned_from`, NOT `install_date` (`DEF-MET-5861`).**
        // The column's own name settles it: *on since* asks how long this thing
        // has been ON THIS UNIT, which is the current assignment's `from_date`.
        // `install_date` is when the DEVICE was installed — a different fact,
        // and the one the registry's `Installed` column and the depreciation
        // age base both want. **A meter moved between units has ONE
        // installation and SEVERAL arrivals**, so the two diverge the first
        // time anything moves, and for a meter assigned from stock
        // `install_date` is null outright: `_validate_asset` requires one only
        // when a unit is given, so every spare on the shelf carries none and
        // this column drew a dash on every meter a clerk had just assigned.
        // `AssetFlowPages` reached the same conclusion for the reassign floor
        // and wrote it down: *"an assignment can start well after
        // installation"*.
        key: "onSince",
        label: t("metering.units.assets.col.onSince"),
        cell: (line) =>
          line.row === undefined ||
          line.row.assigned_from === null ||
          line.row.assigned_from === undefined ? (
            UNIT_ASSET_ABSENT
          ) : (
            // BR-SHL-034: every displayed date, one formatter.
            <DateCell value={line.row.assigned_from} timeZone={timeZone} dateFormat={dateFormat} />
          ),
      },
      {
        key: "lastRead",
        label: t("assets.col.lastRead"),
        cell: (line) =>
          line.row === undefined ? (
            UNIT_ASSET_ABSENT
          ) : (
            <UnitAssetLastReadCell
              asset={line.row}
              t={t}
              timeZone={timeZone}
              dateFormat={dateFormat}
            />
          ),
      },
      {
        // The unheaded action column the frame draws at the right.
        key: "actions",
        label: t("metering.col.actions"),
        cell: (line) => (
          <RowActions>
            {/* `G3`'s pencil. ⚠ IT IS AN ICON NOW, NOT A TEXT BUTTON (B14 rule
                15 and the frame's own `✎`): a text link in an action cell is
                `DEF-337` — *"four red words in one cell"* — and `RowActions`
                is the kit's one answer to it.
                ⚠ **AND IT IS DISABLED WITH ITS REASON RATHER THAN ABSENT when
                the registry row is missing** (`BR-SHL-025`). It used to render
                a dash, so a clerk hunting for the control learned nothing;
                without a registry row there is no current stage to transition
                FROM, and that is what the tooltip now says.
                ⚠ **THE FRAME ALSO DRAWS `−` AND `…` AND NEITHER IS BUILT.**
                Nothing in this product removes a meter from a unit yet — the
                consequence is stated in the rule line below the table and the
                control is the asset registry's. Recorded in the conformance
                file rather than invented here. */}
            <RowAction
              label={t("metering.units.assets.changeStatusAction")}
              icon={<PencilIcon />}
              reason={
                line.row === undefined
                  ? t("metering.units.assets.statusNoRegistryRow")
                  : props.writeBlockedReason
              }
              onClick={() => {
                if (line.row !== undefined) {
                  setStatusFor(line.row);
                }
              }}
            />
          </RowActions>
        ),
      },
    ],
  };

  return (
    <section className="flex flex-col gap-3">
      <InventoryFinder
        unit={unit}
        client={props.client}
        t={t}
        writeBlockedReason={props.writeBlockedReason}
        heading={<Kicker>{t("metering.units.assets.heading")}</Kicker>}
        onAssigned={(assetNo) =>
          fireToast(t("metering.units.assets.assignedToast", { asset: assetNo }))
        }
      />
      <DataTable<UnitAssetLine>
        config={config}
        state={state}
        onStateChange={setState}
        rows={page}
        totalRows={assetsQuery.data === undefined ? null : assetsQuery.data.count}
        loading={assetsQuery.isPending}
        empty={{
          title: t("metering.units.assetsEmpty"),
          // The drawn consequence, in the state where it matters most.
          helper: t("metering.units.assets.noneEmptyHelper"),
        }}
      />
      {/* r10's RULE callout, its own sentence. */}
      <Note>{t("metering.units.assets.rule")}</Note>
      {statusFor !== null && (
        <AttachedAssetStatusModal
          unit={unit}
          asset={statusFor}
          client={props.client}
          t={t}
          dateFormat={dateFormat}
          onClose={() => setStatusFor(null)}
          onDone={(assetNo, statusName) =>
            fireToast(
              t("metering.units.assets.statusToast", { asset: assetNo, status: statusName }),
            )
          }
        />
      )}
    </section>
  );
}

/** One line of the on-unit table: the unit's own reference, and the registry
 *  row behind it — the server's page for this unit (`DEF-MET-8362`). */
interface UnitAssetLine {
  id: string;
  meter: UnitRow["meters"][number];
  row: AssetRow | undefined;
}

/** A value the registry did not send, in the absent style the frame draws. */
const UNIT_ASSET_ABSENT = <Dash />;

/**
 * `Last read`, in the shape the frame draws — **a date AND a quantity with its
 * explicit unit** (`28 Aug · 4,182 kWh`), and three different sentences where
 * there is no date to draw.
 *
 * ⚠ **THE COLUMN WAS NOT MISSING BECAUSE IT COULD NOT BE SOURCED, AND THE
 * SCREEN SAID OTHERWISE.** `metering.units.assets.lastReadArrivesWith` stood
 * under this table claiming *"a registry row carries no reading and nothing
 * joins the reads onto it, so the column is left out"*. Both clauses are false:
 * `selectors.asset_page_rows` joins the latest read onto every meter and
 * sub-meter in ONE query and has since `CR-089` wave C, and the premises Assets
 * tab has drawn it since. That is hard-won law 1 — a comment claiming a
 * guarantee is not the guarantee — living in a user-visible string, where it
 * told a clerk the product could not do something it does.
 *
 * ⚠ **A DASH WOULD COLLAPSE THREE FACTS INTO ONE**: a meter nobody has read
 * yet is worth chasing, a fire line is not read AT ALL and never will be, and a
 * row the registry did not return is a gap in what we know. The three read
 * differently on purpose.
 *
 * ⚠ **THE QUANTITY IS `UnitCell`'s, NOT AN f-STRING** (CLAUDE.md rule 3,
 * `BR-MET-144`): consumption always carries its unit, and `formatQuantity`
 * inside that component is the one implementation — interpolating the served
 * decimal directly is `DEF-1120`, which printed `684.000000 kWh`.
 */
function UnitAssetLastReadCell(props: {
  asset: AssetRow;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { asset, t } = props;
  if (!isMeteredAsset(asset)) {
    return (
      <span className="met-muted" data-not-read={asset.type}>
        {t(notReadKey(asset.type))}
      </span>
    );
  }
  const read = asset.last_read ?? null;
  if (read === null || read.read_at === null) {
    return (
      <span className="met-muted" data-no-read-yet="">
        {t("metering.premises.assets.noReadYet")}
      </span>
    );
  }
  return (
    <span className="flex flex-wrap items-baseline gap-1">
      <DateCell value={read.read_at} timeZone={props.timeZone} dateFormat={props.dateFormat} />
      {/* ⚠ **THE READING COMES FIRST, AND IT IS THE FACT THE CLERK CAME FOR**
          (`DEF-MET-5862`, PO ruling 2026-09-19: *"fix it"*). This cell drew
          `consumption` alone, which is the USAGE since the previous read — so
          a meter's FIRST read, which has no previous value and therefore no
          consumption, showed a bare date over a reading that exists. The PO
          reported exactly that, having confirmed the reading was visible on
          the Reads list and on the asset's own tab.

          The alternative — keep showing usage and rename the column — was put
          to them and NOT chosen: the reading is what you check against the
          meter standing in front of you. */}
      {read.current_value !== null && read.current_value !== undefined && read.unit !== null && (
        <>
          <span aria-hidden="true" className="met-qualifier">
            ·
          </span>
          <UnitCell quantity={read.current_value} unit={read.unit} />
        </>
      )}
      {/* ⚠ **AND THE USAGE STAYS BESIDE IT WHEN THERE IS ONE — NEVER AS A
          ZERO.** A first read genuinely has no usage, and `0 kgal used` would
          state that the meter measured nothing, which is a different and false
          fact (`BR-MET-106`, `DEF-079` — *the quiet dash, never a zero*). The
          clause is simply absent, exactly as it is for an estimate, which by
          `BR-MET-028` has a usage and no reading — the mirror case, and the
          reason these two conditions are independent rather than nested. */}
      {read.consumption !== null && read.unit !== null && (
        <>
          <span aria-hidden="true" className="met-qualifier">
            ·
          </span>
          {/* ⚠ **`UnitCell` FOR BOTH NUMBERS, NOT AN f-STRING FOR EITHER**
              (CLAUDE.md rule 3, `BR-MET-144`): a quantity always carries its
              unit and `formatQuantity` is the one implementation — rounding
              half-up to two places and trimming trailing zeros. Interpolating
              the served decimal is `DEF-1120`, which printed `684.000000 kWh`.
              The qualifier is a separate word so the number keeps that one
              formatter rather than being rebuilt inside a sentence. */}
          <UnitCell quantity={read.consumption} unit={read.unit} />
          <span className="met-qualifier">{t("metering.units.assets.lastReadUsed")}</span>
        </>
      )}
    </span>
  );
}


/**
 * r10's `Residential Standard · v2` — the plan's NAME and the version in force.
 *
 * ⚠ **THIS LINE WAS UNBUILDABLE UNTIL 2026-08-21 AND IS NOT ANY MORE.** B15
 * §2A.3 claim 5 lists it as absent citing **DEF-410** (*"a plan has NO version
 * history"*), and Wave G closed DEF-410 the same day: `GET /plans/{id}` serves
 * `version` and a `versions` filing record (BR-RAT-111). So the version here is
 * the SERVER's own number, not a counter this screen kept.
 *
 * It also fixes what the tab printed before, which was the plan's UUID: the unit
 * payload carries `rate_plan_id` and no name, and rendering a uuid to a billing
 * clerk is DEF-332's rule broken by omission rather than by intent.
 *
 * ⚠ **AND IT WAS ONLY FIXED FOR THE SETTLED FRAME (DEF-2412, 2026-09-01).**
 * The name is FETCHED, so between the first paint and the response there was a
 * frame with nothing but the id in hand — and this function printed it, twice
 * over: once while loading and once, permanently, for a plan that could not be
 * read at all. The comment that stood here argued the second case was right
 * ("the id is at least traceable"), and it is — to an ENGINEER. To a billing
 * clerk it is 36 characters where a plan name belongs, which is what B14 rule
 * 31 was ratified about on 2026-08-30: *"no Databse ID on screen - that is a
 * rule"*.
 *
 * **Both frames now state the ABSENCE in words**, which is the posture the
 * account header was given the same day (`customers/accountDetailHeader.tsx`,
 * DEF-2419). **The id is not deleted, it MOVES** — rule 31's own sentence
 * allows the internal value to ride on `title` as evidence, so support and
 * engineering keep it and the clerk stops reading it.
 *
 * ⚠ **NO TEST IN THIS REPO COULD SEE THE FIRST FRAME**, which is why this one
 * has its own jsdom suite (`UnitPlanIdNeverShows.dom.test.tsx`) rather than an
 * assertion bolted onto a settled-state case: every other suite waits for the
 * data and then looks, and a transient is gone by then.
 */
export function PlanNameAndVersion(props: {
  planId: string;
  client: ApiClient;
  t: Translator;
}) {
  const planQuery = useQuery({
    queryKey: ["plans", "detail", props.planId],
    queryFn: () => getPlan(props.planId, props.client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const tenantPath = useTenantPath();
  const plan = planQuery.data;
  if (plan === undefined) {
    // Two different absences, said differently: the read is still running, or
    // the plan is gone / this role may not see it. `met-muted` is the same
    // quieter tier `Dash` uses for a value the server did not send.
    return (
      <span className="met-muted" title={props.planId}>
        {props.t(
          planQuery.isError ? "metering.units.plan.unreadable" : "metering.units.plan.loading",
        )}
      </span>
    );
  }
  // Record links (PO 2026-10-19): the plan's NAME opens the plan.
  return (
    <span>
      <InlineLinkTo to={tenantPath(planDetailRoute(props.planId))}>{plan.name}</InlineLinkTo>
      <span className="met-qualifier">
        {" "}
        {props.t("metering.units.plan.version", { version: plan.version })}
      </span>
    </span>
  );
}

/**
 * PRM-03's **Account** tab — CR-089 wave I, `PUJ-36` to `PUJ-41`.
 *
 * ⚠ **IT RENDERED FIVE FACTS AND EVERY ONE OF THEM WAS CORRECT** — account
 * number, status, start, balance, autopay — which is exactly why `DEF-CUS-4691`
 * was possible. The Product Owner walked it and asked *"what all other
 * infrmation we can display about accounts here - and expand the details"*, and
 * the answer was that the accounts table has 33 columns and six tables hanging
 * off it. What was missing is not information the product lacks; it is
 * information the product already holds and did not put here.
 *
 * **THE ORDER IS THE ORDER A CLERK NEEDS IT IN, NOT THE ORDER THE TABLES ARE
 * IN.** A protection is first because it is the only fact on this tab that
 * stops somebody doing something: a supervisor standing on a unit arranging a
 * shut-off has to meet it before anything else, and until this wave they could
 * not see it from here at all.
 *
 * **AUTOPAY IS NEVER DRAWN FROM ONE COLUMN** (`I3`). An account can be enrolled
 * AND be cash-only after two bounced payments, and then nothing is drafted.
 * *Autopay: on* alone is the wrong answer; the customer portal shipped it and
 * it cost a wave to find. The server reads the election and the sanction
 * together (`apps.payments.autopay.is_enrolled`) and sends ONE reading, so this
 * screen cannot re-derive it wrongly.
 *
 * **AN ABSENT ROW READS AS "NOT LOOKED UP"; A STATED "NONE" IS THE ANSWER**
 * (`I4`). The five money states are always drawn — payment plan, budget
 * billing, collections, bounced payments, tax exemption — because those are
 * what a clerk checks before promising anything, and a missing row is not a
 * negative answer. Each can also say *could not be read*, which is a THIRD
 * state and not a fancy way of saying none (`DEF-127`).
 *
 * **WHAT IS DELIBERATELY NOT DRAWN, AND WHY:**
 *   · `credit_tier` — served, and a computed cache that nothing computes
 *     (`BR-CUS-058`; `credit_tier_rules` is unbuilt). A letter on screen would
 *     read as a grade this utility awarded, which nobody did.
 *   · a protection's author BY NAME — `account_protections.set_by` holds a ROLE
 *     (`tenant` / `regulator`) and no column anywhere holds the person. Who
 *     typed it is in `audit_log`, which is pruned.
 */
export function UnitAccountTab(props: {
  unit: UnitRow;
  client: ApiClient;
  t: Translator;
  regional: RegionalProps;
}) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props.regional);
  const on = (value: string) => formatDate(value, timeZone, dateFormat);
  const accountQuery = useQuery({
    queryKey: unitAccountQueryKey(props.unit.id),
    queryFn: () => getUnitAccount(props.unit.id, props.client),
  });
  if (accountQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  const answer = accountQuery.data;
  if (answer === undefined || answer.facts_unavailable !== null) {
    // The module is unwired. NOT an empty tab — an empty tab would state that
    // this account has no protections, no notes and no plan, which are three
    // claims nobody made.
    return (
      <Panel as="section">
        <h3>{t("metering.units.tab.account")}</h3>
        <p className="met-panel-hint">{t("metering.units.account.factsUnavailable")}</p>
      </Panel>
    );
  }

  const current = answer.account;
  const facts = answer.facts;
  if (current === null || facts === null) {
    return <UnitAccountVacant answer={answer} t={t} tenantPath={tenantPath} />;
  }

  const held = facts.protections.in_force;
  return (
    <Panel as="section">
      <h3>{t("metering.units.tab.account")}</h3>

      {/* ── I1 · the banner, above every other fact ────────────────────────
          `DEF-CUS-4691`. `WarningBox` is the shared kit's dated warning and
          B14 rule 36 says the kit is how a screen complies; `now` is its
          danger tier, which the kit reserves for a state a person has to ACT
          on rather than notice. A protection is exactly that. */}
      {held.length > 0 && (
        <div className="mb-4 flex flex-col gap-2" data-testid="unit-account-protections">
          {held.map((protection) => (
            <WarningBox
              key={protection.id}
              tone="now"
              data-warning={`protection-${protection.kind}`}
              sentence={
                <>
                  <strong>{t("metering.units.account.protectionHeading")}</strong>{" "}
                  {protectionSentence(protection, t, on)}
                </>
              }
              note={t("metering.units.account.protectionNote")}
            />
          ))}
        </div>
      )}

      {/* ⚠ **THE FIRST GROUP HAD NO HEADING AT ALL** (`DEF-MET-4766`), while the
          key for it — `sectionAccount`, *"The account"* — sat ratified in all
          eleven catalogues and was rendered NOWHERE. Two of the three groups
          were headed, so an unheaded first one read as the panel's preamble
          rather than as a group, and the frame heads all three. */}
      <h4 className="text-h5 mt-2 mb-2">{t("metering.units.account.sectionAccount")}</h4>
      <FactList>
        <Fact label={t("metering.units.account.account")}>
          {current.account_no ?? <Dash />}
          {current.name !== null && <span className="met-qualifier"> · {current.name}</span>}
        </Fact>
        {/* The TENANT's own label for the status (BR-CUS-055 Reference data),
            never a code and never this screen's translation of one.
            ⚠ **A PILL, AND THE OPEN DATE IS THIS ROW'S QUALIFIER.** It was
            plain text with a `Start date` row of its own below it; the frame
            draws no separate start row and folds the date in here, because
            *when did this account open* is a fact ABOUT the status rather than
            a fact beside it. The frame's own RULES line says colour is never
            the only signal, so the pill carries the word too. */}
        <Fact label={t("metering.units.account.status")}>
          <StatusPill tone={current.closed_at === null ? "success" : "muted"}>
            {current.status_name}
          </StatusPill>
          {current.opened_at !== null && (
            <span className="met-qualifier">
              {" "}
              {t("metering.units.account.sinceDate", { date: on(current.opened_at) })}
            </span>
          )}
        </Fact>
        {/* ── I2 · the class, and what it decides ──────────────────────────
            Since `CR-087` a charge code can price per class — residential and
            commercial can be $8.00 and $34.00 for the same meter size — so
            this is not a label, it selects a figure on the bill. The clause
            beside it says so, which is why it is a qualifier on the ROW and
            not a section description (B14 rule 32's budget). */}
        <Fact label={t("metering.units.account.class")}>
          {facts.customer_class === null ? (
            <Dash />
          ) : (
            <>
              {facts.customer_class.name}
              {facts.customer_class.subtype_name !== null && (
                <span className="met-qualifier"> · {facts.customer_class.subtype_name}</span>
              )}
              <span className="met-qualifier"> · {t("metering.units.account.classDecides")}</span>
            </>
          )}
        </Fact>
        {/* ── `Reach them by` — ONE ROW, NAMING ALL THREE ANSWERS ──────────
            The frame draws a single row here and the built tab drew a whole
            third group for it (`Post came back` · `Bill goes` · `Preferred
            language`). Three rows to say *we have not been told anything* is
            three times the reading for one fact, and B14 rule 32's budget is a
            sentence per section.
            ⚠ **PRINT IS THE FLOOR (`BR-BIL-036`), so the sentence always opens
            on post** and the two electives only ADD a channel — a paperless
            account still gets its printed bill and the copy must not imply
            otherwise. When nothing has been elected AND no language is on
            file, the value is the stated absence in the absent style: nobody
            has told us anything, which is a different fact from *by post*. */}
        <Fact label={t("metering.units.account.reach")}>
          {!facts.reach.paperless &&
          !facts.reach.sms_reminders &&
          facts.reach.preferred_language === null ? (
            <Dash>{t("metering.units.account.reachNothing")}</Dash>
          ) : (
            <>
              {deliverySentence(facts.reach, t)}
              {facts.reach.preferred_language !== null && (
                <span className="met-qualifier"> · {facts.reach.preferred_language}</span>
              )}
            </>
          )}
        </Fact>
        {/* ── `Post` — WALKED FROM THE PREMISES, NEVER STORED HERE ──────────
            CLAUDE.md hard rule 8 (`BR-MET-1161`): an address lives on
            `premises` and NOWHERE else, and every other entity derives it by
            walking. `UnitRow.premise_address` IS that walk, already served.
            ⚠ **THE FRAME'S QUALIFIER READS *"the building's address; no
            separate billing address"* AND ONLY THE FIRST HALF IS DRAWN HERE.**
            A mailing address is `customers.addresses kind='mailing'` — one of
            hard rule 8's three exceptions and the place a landlord's bill
            actually goes — and it is NOT on this payload. Saying *no separate
            billing address* would assert an absence nobody looked for, which
            is `DEF-127`'s shape pointed at an address. Recorded in the U7
            conformance file rather than guessed.
            ⚠ **AND `Post came back` RIDES HERE RATHER THAN VANISHING.** The
            frame draws no bad-address row, but the flag is a live thing a clerk
            acts on and deleting a working signal because a drawing omits it is
            a loss the drawing did not ask for. It is a fact ABOUT this address,
            so it sits on this row. */}
        <Fact label={t("metering.units.account.post")}>
          {props.unit.premise_address === null ? (
            <Dash>{t("metering.units.account.postNone")}</Dash>
          ) : (
            props.unit.premise_address
          )}
          <span className="met-qualifier"> · {t("metering.units.account.postFromBuilding")}</span>
          {facts.reach.bad_address && (
            <>
              {" "}
              <strong data-bad-address="">{t("metering.units.account.postCameBack")}</strong>
            </>
          )}
        </Fact>
        {/* `BR-CUS-172` — the utility's OWN number from the system they came
            off. NOT one of our database ids, so B14 rule 31 does not reach it:
            this is the number a clerk reads out of the old ledger. The frame
            puts it in this group and calls it `In the old system`. */}
        <Fact label={t("metering.units.account.legacyRef")}>
          {facts.external_ref ?? <Dash />}
        </Fact>
      </FactList>

      <h4 className="text-h5 mt-6 mb-2">{t("metering.units.account.sectionStanding")}</h4>
      <FactList>
        {/* ── `Owed` LEADS THIS GROUP, WHERE THE FRAME PUTS IT ──────────────
            It used to be the LAST row of the unheaded first group, so the money
            group opened on autopay and the one figure a clerk on the phone is
            being asked about sat above the heading that says it is about money.
            ⚠ **THIS PRINTED `48.450000 USD` ON A CUSTOMER-FACING SCREEN —
            `DEF-595`.** The balance is a decimal STRING at the stored scale and
            it was interpolated raw, so a unit's Account tab showed SIX decimal
            places and no currency symbol. CLAUDE.md hard rule 2, PO re-signed
            2026-08-22 verbatim: *"MOney 4 decimal, percentage 6 decimal,
            display both 2 decimal"*. `MoneyCell` is the ONE formatter that
            keeps it — it takes the decimal string (never a float, never
            `toFixed`) and renders `$48.45`.
            ⚠ NULL BALANCE IS STILL NOT ZERO. `AccountRow.balance` is null when
            the books could not be asked, and its own contract says so in
            capitals: rendering "$0.00" there looks exactly like a settled
            account.
            ⚠ **THE DUE DATE IS A STATED ABSENCE AND IT IS THE ACCOUNT HEADER'S
            OWN.** The frame draws *"due 24 Sep 2026 · not yet overdue"* beside
            the figure. `BR-CUS-033` makes the due date the OLDEST STILL-OPEN
            bill's, and *which bill is still open* is a payments position
            nothing publishes. `AccountDetailPage`'s header states exactly that
            absence and the unit's own Overview block already reuses THAT key;
            this is the third reader of one sentence rather than a second
            wording of one gap (B14 rule 34). */}
        <Fact label={t("metering.units.account.balance")}>
          {current.balance === null ? (
            <Dash>{t("metering.units.account.balanceUnavailable")}</Dash>
          ) : (
            <MoneyCell
              amount={current.balance}
              currency={current.balance_currency ?? current.currency}
            />
          )}
          <span className="met-qualifier"> · {t("customers.account.awaits.dueDate")}</span>
        </Fact>
        {/* ── `Last bill` — SERVED ON THIS PAYLOAD, AND NOTHING READ IT ─────
            `AccountRow.last_bill_at` is the date this account's latest bill
            ISSUED, served since `DEF-127` on the same `selectors.account_row`
            the accounts LIST uses — so the date here and the date on S17
            cannot be two different answers. It rode this tab's own payload and
            no row drew it (`DEF-MET-4766`).
            ⚠ **NULL HERE IS A REAL ANSWER AND NOT AN UNREADABLE ONE**: the
            contract says it is null *only* when the account has genuinely never
            been billed, which is a sentence rather than a dash — a new account
            and an account whose bills we could not read must not look alike.
            ⛔ **NO BILL NUMBER.** The frame draws `BL-2608-000052` beside the
            date; the payload carries no invoice reference, and inventing a
            shape for one on a screen a clerk quotes from is the one guess this
            row must not make. Recorded in the U7 conformance file. */}
        <Fact label={t("metering.units.account.lastBill")}>
          {/* ⚠ **`== null`, CATCHING `undefined` TOO — AND THAT IS NOT
              SLOPPINESS.** `AccountRow.last_bill_at` is typed `string | null`,
              so `undefined` means the key was not served at all: a payload that
              predates it, or a fixture. `=== null` let that fall through to
              `DateCell`, which rendered an EMPTY `<time>` element — a blank cell
              a reader cannot distinguish from a rendering failure, and which
              `toContain` would never catch. Between an empty box and the stated
              absence, the absence is the only one that says something true. */}
          {current.last_bill_at == null ? (
            <Dash>{t("metering.units.account.lastBillNever")}</Dash>
          ) : (
            <DateCell value={current.last_bill_at} timeZone={timeZone} dateFormat={dateFormat} />
          )}
        </Fact>
        {/* ⚠ **DEPOSIT BEFORE AUTOPAY — the frame's order, and it was the
            other way round.** What the utility HOLDS comes before what it will
            TAKE: a deposit is money already in hand and it is what a clerk
            reaches for when a leaver asks what happens to it. */}
        <Fact label={t("metering.units.account.deposit")}>
          {facts.deposit.any ? (
            <>
              <MoneyCell amount={facts.deposit.held} currency={facts.deposit.currency} />
              {facts.deposit.received_on !== null && (
                <span className="met-qualifier">
                  {" · "}
                  {t("metering.units.account.depositTaken", { date: on(facts.deposit.received_on) })}
                </span>
              )}
            </>
          ) : (
            <Dash>{t("metering.units.account.depositNone")}</Dash>
          )}
        </Fact>
        {/* ── I3 · autopay, read together with cash-only ───────────────────
            The reading is the SERVER's single answer. Deriving it here from
            `elected && !cash_only` would be a second implementation of the
            rule `DEF-070` already cost this product once. */}
        <Fact label={t("metering.units.account.autopay")}>
          <span data-autopay={facts.autopay.reading}>{autopaySentence(facts.autopay, t)}</span>
        </Fact>
        <Fact label={t("metering.units.account.paymentPlan")}>
          {facts.payment_plan.state === "unreadable" ? (
            <Dash>{t("metering.units.account.couldNotRead")}</Dash>
          ) : facts.payment_plan.state === "none" ? (
            <Dash>{t("metering.units.account.paymentPlanNone")}</Dash>
          ) : (
            t("metering.units.account.paymentPlanRunning", { count: facts.payment_plan.running })
          )}
        </Fact>
        <Fact label={t("metering.units.account.budget")}>
          {facts.budget_billing.state === "unreadable" ? (
            <Dash>{t("metering.units.account.couldNotRead")}</Dash>
          ) : facts.budget_billing.state === "none" ? (
            <Dash>{t("metering.units.account.budgetNone")}</Dash>
          ) : (
            <>
              {t("metering.units.account.budgetOn")}
              {facts.budget_billing.level !== null && (
                <span className="met-qualifier">
                  {" · "}
                  <MoneyCell
                    amount={facts.budget_billing.level}
                    currency={facts.budget_billing.currency ?? current.currency}
                  />
                </span>
              )}
            </>
          )}
        </Fact>
        <Fact label={t("metering.units.account.collections")}>
          {facts.collections.state === "unreadable" ? (
            <Dash>{t("metering.units.account.couldNotRead")}</Dash>
          ) : facts.collections.state === "none" ? (
            <Dash>{t("metering.units.account.collectionsNone")}</Dash>
          ) : (
            <>
              {t("metering.units.account.collectionsOn")}
              {facts.collections.tier !== null && (
                <span className="met-qualifier"> · {facts.collections.tier}</span>
              )}
            </>
          )}
        </Fact>
        <Fact label={t("metering.units.account.bounced")}>
          {facts.bounced_payments.count}
        </Fact>
        <Fact label={t("metering.units.account.taxExempt")}>
          {facts.tax_exemption.claimed ? (
            <>
              {t("metering.units.account.taxExemptClaimed")}
              {facts.tax_exemption.expires_on !== null && (
                <span className="met-qualifier">
                  {" · "}
                  {t("metering.units.account.taxExemptUntil", {
                    date: on(facts.tax_exemption.expires_on),
                  })}
                </span>
              )}
            </>
          ) : (
            <Dash>{t("metering.units.account.taxExemptNone")}</Dash>
          )}
        </Fact>
      </FactList>

      {/* ── THE FRAME'S THIRD GROUP — `Before this` ───────────────────────
          *"The vacant gap is named with its cost. Four days between two
          accounts, and base charges for those days reached the owner. That is
          the commonest opening-balance dispute there is."*
          ⚠ **BOTH FACTS ARE ALREADY DERIVED IN THIS FILE AND NOTHING DREW
          THEM** (`DEF-MET-4766`). `occupancyTimeline` builds exactly this from
          `GET /accounts?f.unit_id=`, for the table on the Occupancy tab, and
          the two tabs share `unitAccountsQueryKey` — so React Query serves this
          from the read the neighbouring tab already made and a clerk who has
          opened either pays for one request, not two.
          ⚠ **NOTHING IS RE-DERIVED HERE.** `previousTenancy` below is one pure
          function over that same timeline; a second definition of *what came
          before* is how two screens end up disagreeing about a tenancy. */}
      <UnitAccountBefore
        unitId={props.unit.id}
        currentId={current.id}
        client={props.client}
        t={t}
        on={on}
      />

      {/* ── I5 · the notes the product already stores ─────────────────────
          ⚠ **A COUNT CHIP BESIDE THE HEADING, WHICH THE FRAME DRAWS AND THE
          TAB DID NOT.** A clerk scanning a protected account needs to know
          there are two notes before deciding to read them. `Chip` is the kit's
          own — with no `onRemove` it is the static form — rather than a fourth
          badge invented for one heading (B14 rule 36). */}
      <h4 className="text-h5 mt-6 mb-2 flex items-center gap-2">
        {t("metering.units.account.sectionNotes")}
        {facts.notes.length > 0 && <Chip>{facts.notes.length}</Chip>}
      </h4>
      {facts.notes.length === 0 ? (
        <p className="met-panel-hint">{t("metering.units.account.notesNone")}</p>
      ) : (
        // ⚠ **LABEL/VALUE ROWS, NOT A BULLET LIST.** The frame draws the notes
        // in the same shape as the fact rows above them, and it is the shape
        // that reads: a run-on line put the note's title, its body, its author,
        // its date and its visibility into one paragraph a clerk has to parse.
        // `FactList` is the same component the three groups above use, so the
        // notes line up with them instead of forming a fourth layout.
        <FactList>
          {facts.notes.map((note) => (
            <Fact
              key={note.id}
              label={`${note.pinned ? "📌 " : ""}${note.title ?? "—"}`}
            >
              {note.body !== null && <span>{note.body}</span>}
              <span className="met-qualifier">
                {" · "}
                {/* ⚠ **THREE STATES, NOT TWO.** A resolved name; an author we
                    hold and cannot name (`author_name` is null on EVERY note in
                    the product — `apps.identity.selectors` publishes no
                    `user_display_name`, `DEF-CUS-4704`); and no author at all,
                    which is a background job and is the only case that may say
                    *System*. Printing *System* over a real author would
                    attribute a clerk's note to a machine. */}
                {note.author_name ??
                  (note.author_id === null ? (
                    t("metering.units.account.noteSystem")
                  ) : (
                    // ⚠ **A LABELLED DASH, NOT A BARE ONE — AND IT IS THIS WAY
                    // ON EVERY NOTE IN THE PRODUCT.** `author_name` is null on
                    // ALL of them (`DEF-CUS-4704`: customers resolves
                    // `identity.selectors.user_display_name` and identity
                    // publishes no such callable), so this branch is not the
                    // rare case — it is the only case a clerk ever sees. A
                    // bare `—` sitting between the note's body and its date
                    // reads as stray punctuation; the state is real and it has
                    // to say what it is. It still must NOT say *System*, which
                    // would attribute a person's note to a machine.
                    <Dash>{t("metering.units.account.noteAuthorUnnamed")}</Dash>
                  ))}
                {note.created_at !== null && <>{" · "}{on(note.created_at)}</>}
                {/* ⚠ **BOTH VISIBILITY STATES ARE STATED IN WORDS, WHICH IS
                    THE FRAME'S OWN INSISTENCE.** Only the positive one used to
                    render, so a private note — a medical certificate, say —
                    said NOTHING about who can see it, and a clerk about to read
                    it down the phone had no way to tell it apart from a note
                    the customer already has. An absence is not an answer here;
                    it is the more dangerous of the two states. */}
                {" · "}
                {note.customer_visible
                  ? t("customers.account.note.customerVisiblePill")
                  : t("metering.units.account.notePrivate")}
              </span>
            </Fact>
          ))}
        </FactList>
      )}

      {/* DEF-580 — r10's Account tab ENDS in two named actions: `Open account →`
          and `Move-out…`.
          · `Open account →` is a LINK to the account this unit already names —
            a route that exists (S21), not a new capability.
          ⛔ `Move-out…` is rendered DISABLED WITH ITS REASON (BR-SHL-025).
            ⚠ **AND THE REASON WAS REWRITTEN ON 2026-09-08 (`DEF-CUS-4702`),
            BECAUSE THE OLD ONE HAD ROTTED.** It read *"This unit has no door to
            it yet"*, which a clerk reads as *the flow is not built* — and
            `MoveOutWizard` has been routed and live at
            `/{tenant}/accounts/{id}/move-out` since 2026-08-25. That is
            hard-won law 2's MIRROR: a live screen behind a dead control, with
            every check passing over it. The control STAYS held — this unit
            genuinely owns no door to that flow and building one is not this
            wave's — and the sentence now says where the flow lives, so the
            clerk can get there through `Open account →` beside it.
            `UnitAccountMoveOutHold.dom.test.tsx` is the test that fires the day
            a door does land here. */}
      <div className="flex items-center gap-2 mt-4">
        <ButtonLink variant="secondary" to={tenantPath(accountDetailPath(current.id))}>
          {t("metering.units.account.open")}
        </ButtonLink>
        {/* A common area has no tenant and therefore no move-out at all, so the
            control is not drawn for one rather than drawn and refused. */}
        {!answer.unit.is_common_area && (
          <GuardedButton
            label={t("metering.units.account.moveOut")}
            reason={t("metering.units.account.moveOutArrivesWith")}
            // ⚠ **DANGER TIER (`DEF-MET-4766`).** The frame draws this control
            // amber and right-aligned, and the frame's own RULES line says
            // *"the danger tier for anything that ends service"* — a move-out
            // closes the account, takes a final read and raises the final bill.
            // It rendered as an ordinary secondary beside `Open the account →`,
            // so the two read as a pair of equals. B14 puts the tier on the
            // commit, and a HELD control keeps its tier: `GuardedButton` draws
            // the disabled state in the variant it was given, so the day the
            // hold lifts the button is already the right colour.
            danger
            onClick={() => undefined}
          />
        )}
      </div>
    </Panel>
  );
}

/**
 * `Before this` — **THE PREVIOUS TENANCY AND THE GAP AFTER IT.**
 *
 * The U7 frame's third group, and the *WHAT CHANGED* block says why it is
 * drawn: *"The vacant gap is named with its cost. Four days between two
 * accounts, and base charges for those days reached the owner. That is the
 * commonest opening-balance dispute there is."*
 *
 * ⚠ **IT COSTS NO SECOND READ.** This calls `getAccounts({unit_id})` under
 * `unitAccountsQueryKey` — **the same key the Occupancy tab uses** — so a clerk
 * who has opened either tab issues nothing here, and one who opens this one
 * first has already paid for the neighbouring table.
 *
 * ⚠ **AND IT DERIVES NOTHING OF ITS OWN.** `occupancyTimeline` is the one
 * definition of *what came before and what the gap was*; a second derivation on
 * this tab is how the Account tab and the Occupancy tab end up disagreeing
 * about a tenancy that ended, which is the failure hard-won law 1 describes.
 *
 * ⛔ **THE FRAME'S `closed, nothing outstanding` CLAUSE IS NOT DRAWN HERE.**
 * `AccountRow.balance` would answer it, and the Occupancy tab one tab away now
 * draws exactly that figure in its `Left owing` column. Printing it twice
 * invites the two to be read as two facts, and `DEF-127` means a null there is
 * *the books could not be asked* rather than *nothing outstanding* — a sentence
 * this row cannot make honestly in the space of a qualifier. Recorded in the U7
 * conformance file.
 */
export function UnitAccountBefore(props: {
  unitId: string;
  currentId: string;
  client: ApiClient;
  t: Translator;
  on: (value: string) => string;
}) {
  const { t, on } = props;
  const accountsQuery = useQuery({
    queryKey: unitAccountsQueryKey(props.unitId),
    queryFn: () => getAccounts({ filters: { unit_id: props.unitId }, per: 50 }, props.client),
  });
  // The heading is drawn as soon as the group is: a group that appears only
  // once its data lands makes the page jump under a reader's eyes, and an
  // absent group reads as *this unit has no history* rather than *we are still
  // asking*.
  const heading = (
    <h4 className="text-h5 mt-6 mb-2">{t("metering.units.account.sectionBefore")}</h4>
  );
  if (accountsQuery.isPending) {
    return (
      <>
        {heading}
        <LoadingSkeleton variant="card" />
      </>
    );
  }
  const before = previousTenancy(accountsQuery.data?.results ?? [], props.currentId, todayISO());
  return (
    <>
      {heading}
      <FactList>
        <Fact label={t("metering.units.account.previousAccount")}>
          {before.previous === null ? (
            <Dash>{t("metering.units.account.previousNone")}</Dash>
          ) : (
            <>
              {before.previous.account_no ?? <Dash />}
              {before.previous.name !== null && (
                <span className="met-qualifier"> · {before.previous.name}</span>
              )}
              {before.previous.opened_at !== null && before.previous.closed_at !== null && (
                <span className="met-qualifier">
                  {" · "}
                  {t("metering.units.account.previousSpan", {
                    from: on(before.previous.opened_at),
                    to: on(before.previous.closed_at),
                  })}
                </span>
              )}
            </>
          )}
        </Fact>
        {/* ⚠ **THE GAP'S OWN DATES AND ITS OWN LENGTH**, which is what a
            landlord asked for — not the two TENANCY dates the CR's worked line
            names. `vacancyBetween` counts from the day after one tenancy ends
            to the day before the next begins, because `customers.services`
            bills a leaver THROUGH `moved_out_on`: a tenancy closing on the 28th
            OCCUPIED the 28th. That off-by-one is recorded in the decision log
            and is the Occupancy tab's convention too, so the two tabs cannot
            report a different number of days for one gap.
            A stated NONE rather than an omitted row: back-to-back tenancies are
            a real and common answer, and an absent row would read as *we did
            not look*. */}
        <Fact label={t("metering.units.account.vacantBetween")}>
          {before.gap === null ? (
            <Dash>
              {before.previous === null
                ? t("metering.units.account.previousNone")
                : t("metering.units.account.vacantBetweenNone")}
            </Dash>
          ) : (
            <>
              {t("metering.units.account.previousSpan", {
                from: on(before.gap.from),
                to: before.gap.to === null ? on(todayISO()) : on(before.gap.to),
              })}
              <span className="met-qualifier">
                {" · "}
                {t("metering.units.occupancy.vacantDays", { count: before.gap.days })}
                {" · "}
                {t("metering.units.account.vacantOwnerBilled")}
              </span>
            </>
          )}
        </Fact>
      </FactList>
    </>
  );
}

/** What the `Before this` group shows: the tenancy immediately before the one
 *  in force, and the gap that separated them.
 *
 *  ⚠ **READ OFF `occupancyTimeline`, NEVER RE-DERIVED.** The timeline is built
 *  oldest-first with each gap already placed between the two tenancies that
 *  produced it, so *the previous tenancy* is the entry before the current one
 *  and *the gap* is whatever sits between them. Both answers therefore agree
 *  with the Occupancy tab's table by construction rather than by review.
 *
 *  A current account the timeline does not carry — a row with no `opened_at`,
 *  which the timeline appends at the end rather than dating — yields nothing,
 *  because *what came before an undated tenancy* is a question with no answer. */
export function previousTenancy(
  rows: readonly AccountRow[],
  currentId: string,
  today: string,
): { previous: AccountRow | null; gap: Extract<OccupancyEntry, { kind: "vacancy" }> | null } {
  const timeline = occupancyTimeline(rows, today);
  const at = timeline.findIndex(
    (entry) => entry.kind === "tenancy" && entry.row.id === currentId,
  );
  if (at <= 0) {
    return { previous: null, gap: null };
  }
  const just = timeline[at - 1];
  if (just.kind === "vacancy") {
    const earlier = timeline[at - 2];
    return {
      previous: earlier !== undefined && earlier.kind === "tenancy" ? earlier.row : null,
      gap: just,
    };
  }
  return { previous: just.row, gap: null };
}

/**
 * The tab when nobody occupies the unit — `CR-089`: *"a vacant unit shows no
 * account: the tab says base charges bill to the owner, NAMES the owner's
 * account and links to it, rather than an empty table."*
 *
 * A **common area** is a different sentence from a vacancy and gets one: it was
 * never going to have a tenant, so *vacant* would be wrong and a move-out is
 * not offered on it at all.
 */
export function UnitAccountVacant(props: {
  answer: UnitAccountResponse;
  t: Translator;
  tenantPath: (path: string) => string;
}) {
  const { t, answer } = props;
  const common = answer.unit.is_common_area;
  return (
    <Panel as="section">
      <h3>{t("metering.units.tab.account")}</h3>
      <p className="met-panel-hint" data-no-account={answer.no_account_reason ?? ""}>
        <strong>
          {common
            ? t("metering.units.account.commonAreaTitle")
            : t("metering.units.account.vacantTitle")}
        </strong>{" "}
        {common
          ? t("metering.units.account.commonAreaOwnerBilled")
          : t("metering.units.account.vacantOwnerBilled")}
      </p>
      {answer.owner_account === null ? (
        <p className="met-panel-hint">{t("metering.units.account.ownerNone")}</p>
      ) : (
        <FactList>
          <Fact label={t("metering.units.account.ownerAccount")}>
            <InlineLinkTo to={props.tenantPath(accountDetailPath(answer.owner_account.id))}>
              {answer.owner_account.account_no ?? <Dash />}
            </InlineLinkTo>
            {answer.owner_account.name !== null && (
              <span className="met-qualifier"> · {answer.owner_account.name}</span>
            )}
          </Fact>
        </FactList>
      )}
    </Panel>
  );
}

/** One protection, as a sentence a supervisor can act on. */
export function protectionSentence(
  protection: UnitAccountProtection,
  t: Translator,
  on: (value: string) => string,
): string {
  const kind =
    protection.kind === "medical_certificate"
      ? t("metering.units.account.protectionMedical")
      : protection.kind === "weather_moratorium"
        ? t("metering.units.account.protectionWeather")
        : t("metering.units.account.protectionPlan");
  const lifetime =
    protection.expires_on === null
      ? t("metering.units.account.protectionOpenEnded")
      : t("metering.units.account.protectionUntil", { date: on(protection.expires_on) });
  // A ROLE, never a name — `account_protections` holds no person and the one
  // that does (`audit_log`) is pruned. `CR-089`'s worked example reads *"set by
  // D. Whitfield"*; that name is not in this product and is not invented here.
  const who =
    protection.set_by === "regulator"
      ? t("metering.units.account.protectionByRegulator")
      : t("metering.units.account.protectionByTenant");
  const since = t("metering.units.account.protectionSince", { date: on(protection.effective_from) });
  return `${kind}, ${lifetime} · ${who}, ${since}`;
}

/** Autopay's four true sentences and its one honest absence. */
export function autopaySentence(
  autopay: UnitAccountFacts["autopay"],
  t: Translator,
): string {
  switch (autopay.reading) {
    case "taken":
      return t("metering.units.account.autopayTaken");
    case "held_cash_only":
      return t("metering.units.account.autopayHeld", { count: autopay.nsf_count });
    case "not_elected_and_cash_only":
      return t("metering.units.account.autopayOffCashOnly", { count: autopay.nsf_count });
    case "not_elected":
      return t("metering.units.account.autopayOff");
    default:
      // `unreadable` — payments could not answer. NOT "off": *we could not
      // tell* and *they are not enrolled* are different statements and only the
      // second one is safe to act on.
      return t("metering.units.account.couldNotRead");
  }
}

/**
 * Where the bill goes. **Print is the FLOOR** (`BR-BIL-036`, PO 2026-08-10), so
 * every sentence starts with post and the two elections only ADD to it — a
 * paperless account still gets its printed bill, and copy implying otherwise
 * would be wrong about what the customer receives.
 */
export function deliverySentence(
  reach: UnitAccountFacts["reach"],
  t: Translator,
): string {
  if (reach.paperless && reach.sms_reminders) {
    return t("metering.units.account.deliveryPostEmailText");
  }
  if (reach.paperless) {
    return t("metering.units.account.deliveryPostEmail");
  }
  if (reach.sms_reminders) {
    return t("metering.units.account.deliveryPostText");
  }
  return t("metering.units.account.deliveryPost");
}


/**
 * PRM-03's **Occupancy** tab — who has held this unit, and when.
 *
 * r10 draws seven columns: `OCCUPANT │ ACCOUNT │ START │ END │ CLOSING READ │
 * FINAL BILL │ STATUS`. Five are served by `GET /accounts?f.unit_id=`.
 *
 * ⛔ **THE OTHER TWO ARE NOT DRAWN — DEF-509.** `apps/billing/final_bill.py`
 * computes a closing read and a final bill and no route reads either back by
 * unit. A column of em-dashes under "CLOSING READ" is not a blank, it is the
 * sentence *"there was no closing read"* — which is exactly what a customer
 * disputing a final bill would quote back.
 *
 * ⛔ **AND THE VACANCY ROWS ARE NOT DRAWN EITHER — OQ-316 / OQ-314.** r10 shows
 * a vacant STRETCH as a real row (`— vacant — · MA-1408 · owner · Base only ·
 * Vacancy billing`). BR-MET-094 CONFIRMED on 2026-08-21 that a vacant unit IS
 * billed automatically, and left two words open: whether the OWNER is the payer
 * (OQ-314's master account) and whether it is base-only or full (OQ-316). A row
 * naming a payer would answer both by drawing them.
 */
export function UnitOccupancyTab(props: {
  unit: UnitRow;
  client: ApiClient;
  t: Translator;
  regional: RegionalProps;
}) {
  const { t } = props;
  const { timeZone, dateFormat } = useRegional(props.regional);
  const accountsQuery = useQuery({
    queryKey: unitAccountsQueryKey(props.unit.id),
    queryFn: () => getAccounts({ filters: { unit_id: props.unit.id }, per: 50 }, props.client),
  });
  if (accountsQuery.isPending) {
    return <LoadingSkeleton variant="table" />;
  }
  const rows: readonly AccountRow[] = accountsQuery.data?.results ?? [];
  // ⚠ **A COMMON AREA IS NEVER VACANT** — the blueprint's own STATES block, and
  // `BR-MET-101`'s flag is what separates a hallway from a flat nobody is
  // renting. A gap between two owner accounts on a laundry is an accounting
  // gap, not an empty home, and drawing `Vacant` over it tells a landlord their
  // hallway stood empty. The gaps are suppressed for one; the tenancies are not.
  const common = props.unit.is_common_area;
  const whole = occupancyTimeline(rows, todayISO());
  const timeline = common ? whole.filter((entry) => entry.kind === "tenancy") : whole;
  // ⚠ **NEWEST FIRST, AND THE GAP STILL SITS BETWEEN ITS TWO TENANCIES.**
  // `occupancyTimeline` builds oldest-first because that is the only order in
  // which a gap can be PLACED between the two tenancies that produced it; the
  // frame reads the finished list upwards, which preserves that adjacency and
  // puts what is happening NOW at the top, where a clerk on the phone looks
  // first. Reversed at RENDER rather than in the helper, so the helper's
  // contract and its unit tests are untouched.
  const newestFirst = [...timeline].reverse();
  const vacancies = timeline.filter((entry) => entry.kind === "vacancy").length;
  return (
    <Panel as="section">
      <h3>{t("metering.units.tab.occupancy")}</h3>
      {timeline.length === 0 ? (
        // Two different sentences, because they are two different facts: a flat
        // nobody has ever rented, and a common area that was never going to be
        // rented at all. Both are the words this product already uses for them
        // (B14 rule 34) rather than a third one minted for this tab.
        <p className="met-panel-hint" data-occupancy-empty={common ? "common-area" : "never"}>
          {common ? (
            <>
              <strong>{t("metering.units.account.commonAreaTitle")}</strong>{" "}
              {t("metering.units.account.commonAreaOwnerBilled")}
            </>
          ) : (
            t("metering.units.occupancy.none")
          )}
        </p>
      ) : (
        <>
          <PlainTable>
            <thead>
              <tr>
                <th>{t("metering.units.occupancy.col.occupant")}</th>
                <th>{t("metering.units.occupancy.col.account")}</th>
                <th>{t("metering.units.occupancy.col.start")}</th>
                <th>{t("metering.units.occupancy.col.end")}</th>
                {/* ⚠ **RIGHT-ALIGNED AND TABULAR, WHICH IS THE FRAME'S OWN RULES
                    LINE** — *"Money right-aligned and tabular"*. A column of
                    figures that does not line up on the decimal point cannot be
                    scanned, which is the whole reason a money column exists. */}
                <th className="text-right">{t("metering.units.occupancy.col.leftOwing")}</th>
                <th>{t("metering.units.col.status")}</th>
              </tr>
            </thead>
            <tbody>
              {newestFirst.map((entry) =>
                entry.kind === "tenancy" ? (
                  <tr key={entry.row.id} data-occupancy-row="tenancy">
                    {/* The occupant of the OPEN tenancy is the one a clerk is
                        usually looking for, and the frame draws it bold. */}
                    <td>
                      {entry.row.name === null ? (
                        <Dash />
                      ) : entry.row.closed_at === null ? (
                        <strong>{entry.row.name}</strong>
                      ) : (
                        entry.row.name
                      )}
                    </td>
                    <td>{entry.row.account_no ?? <Dash />}</td>
                    <td>
                      {entry.row.opened_at === null ? (
                        <Dash />
                      ) : (
                        <DateCell
                          value={entry.row.opened_at}
                          timeZone={timeZone}
                          dateFormat={dateFormat}
                        />
                      )}
                    </td>
                    <td>
                      {entry.row.closed_at === null ? (
                        <span className="met-qualifier">
                          {t("metering.units.occupancy.current")}
                        </span>
                      ) : (
                        <DateCell
                          value={entry.row.closed_at}
                          timeZone={timeZone}
                          dateFormat={dateFormat}
                        />
                      )}
                    </td>
                    {/* ── `Left owing` — THE LEDGER'S FIGURE, ALREADY ON THIS
                        ROW (`DEF-MET-4766`) ───────────────────────────────────
                        `AccountRow.balance` has been the LEDGER's own figure
                        since `DEF-127` and comes back on the very read this tab
                        already makes; nothing new is asked of the server and
                        nothing is computed here.
                        ⚠ **NULL IS NOT ZERO, AND ON THIS COLUMN THAT MATTERS
                        MORE THAN ANYWHERE ELSE.** `balance` is null when the
                        books could not be asked, and `0.00` under *Left owing*
                        says *this tenant settled up* — which is exactly the
                        sentence a landlord would quote back at us. `MoneyCell`
                        is the one formatter (`DEF-595`: this screen once
                        printed six decimal places and no symbol). */}
                    <td className="text-right tabular-nums">
                      {entry.row.balance === null ? (
                        <Dash>{t("metering.units.account.balanceUnavailable")}</Dash>
                      ) : (
                        <MoneyCell
                          amount={entry.row.balance}
                          currency={entry.row.balance_currency ?? entry.row.currency}
                        />
                      )}
                    </td>
                    {/* ⚠ **THE OCCUPANCY WORD, NOT THE ACCOUNT'S STATUS NAME.**
                        The frame draws `CURRENT` · `CLOSED` · `VACANT PERIOD` —
                        three words about the TENANCY, which is what this table
                        is a history of. The cell used to print `status_name`,
                        the tenant's renameable label for the ACCOUNT (`Active`,
                        `Pending activation`…), which answers a different
                        question and reads as one on a row whose other five
                        cells are all about a stretch of time. The account's own
                        status is one click away on the Account tab.
                        `StatusPill` was already imported in this file and
                        unused in this table; colour is never the only signal,
                        so the pill carries the word too (the frame's RULES). */}
                    <td>
                      <StatusPill tone={entry.row.closed_at === null ? "success" : "muted"}>
                        {t(
                          entry.row.closed_at === null
                            ? "metering.units.occupancy.state.current"
                            : "metering.units.occupancy.state.closed",
                        )}
                      </StatusPill>
                    </td>
                  </tr>
                ) : (
                  // ── CR-089 wave F · `F4` (`PUJ-42`) — A VACANCY IS A ROW ────
                  <tr key={`vacancy-${entry.from}`} data-occupancy-row="vacancy">
                    {/* `metering.occupancy.vacant` — the SAME word the occupancy
                        pill uses, not a second one for one concept (B14 rule
                        34). A vacancy row that said "Empty" over a pill that
                        says "Vacant" would read as two states. */}
                    <td>
                      <em>{t("metering.occupancy.vacant")}</em>
                    </td>
                    {/* ⚠ **THE ACCOUNT CELL IS DELIBERATELY EMPTY AND NOT THE
                        OWNER'S NUMBER.** r10 draws `MA-1408 · owner` here.
                        `BR-CUS-170` does say the owner's master account carries
                        the base charge, and the Account tab NAMES it — but that
                        account is resolved per UNIT through
                        `master_account_covering_unit`, and printing it on a row
                        whose date range predates the coverage would assert that
                        THIS account was billed for THAT stretch, which nothing
                        recorded. The sentence beside the dates says who pays
                        today; the cell does not claim who paid then. */}
                    <td>
                      <Dash />
                    </td>
                    <td>
                      <DateCell value={entry.from} timeZone={timeZone} dateFormat={dateFormat} />
                    </td>
                    <td>
                      {entry.to === null ? (
                        // ⚠ **NOT the tenancy's word.** An open TENANCY reads
                        // *still here*; an open VACANCY is the opposite fact,
                        // and printing *still here* over an empty flat is the
                        // one reading this column must never produce.
                        <span className="met-qualifier">
                          {t("metering.units.occupancy.stillEmpty")}
                        </span>
                      ) : (
                        <DateCell value={entry.to} timeZone={timeZone} dateFormat={dateFormat} />
                      )}
                    </td>
                    {/* ⚠ **A DASH, NEVER `0.00`.** Nobody held the unit, so
                        nobody left owing anything — and a zero here would read
                        as a tenancy that settled up, which is a claim about a
                        person who does not exist. */}
                    <td className="text-right tabular-nums">
                      <Dash />
                    </td>
                    <td>
                      <StatusPill tone="neutral">
                        {t("metering.units.occupancy.state.vacantPeriod")}
                      </StatusPill>
                      {/* ⚠ **`metering.units.account.vacantOwnerBilled` AND NOT
                          `metering.units.owed.vacantOwnerBilled`.** They are one
                          concept in two shapes: the OWED one bundles the state
                          word — *"Vacant — base charges bill to the owner"* —
                          because on the units list's money column there is no
                          other word saying so. Here the Occupant cell already
                          says **Vacant**, and the bundled form printed it twice
                          on one row. This is wave I's own clause, already
                          ratified in all eleven catalogues, so B14 rule 34's
                          *one pair of words per concept* is kept rather than a
                          twelfth sentence minted for one table. Found by reading
                          the rendered row, not by a test. */}
                      <span className="met-qualifier">
                        {" "}
                        {t("metering.units.occupancy.vacantDays", { count: entry.days })}
                        {" · "}
                        {t("metering.units.account.vacantOwnerBilled")}
                      </span>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </PlainTable>
          {/* ── THE DRAWN FOOTER — *"a footer that counts the vacancies, which
              is the summary of the whole tab in one line"* ────────────────────
              `TabFooterCounts` is `PremisesDetailPage`'s, written for this
              blueprint's footers and already used on two premises tabs; a second
              copy here is how two footers acquire two type scales.
              ⚠ **THE DRAWN LINE ENDS *"in two years"* AND THIS ONE DOES NOT.**
              That window is the AUDIT log's (`BR-AUD-013`), not this read's:
              `GET /accounts?f.unit_id=` is bounded by nothing, so naming a
              period here would be a claim about a range nobody applied. The
              COUNT is what the drawing is actually for, and the count is true.
              A common area never reports a vacancy, so it gets the count alone. */}
          <TabFooterCounts>
            {t("metering.units.occupancy.footerShowing", { count: timeline.length })}
            {!common && (
              <>
                {" · "}
                {vacancies === 0
                  ? t("metering.units.occupancy.footerVacantNever")
                  : t("metering.units.occupancy.footerVacant", { count: vacancies })}
              </>
            )}
          </TabFooterCounts>
        </>
      )}
      {/* ⚠ **THIS ABSENCE NARROWED; IT DID NOT GO.** It used to say the gaps
          were not listed BECAUSE two things were unsettled — who receives the
          bill and whether it is base-only. `OQ-314`'s half is now BUILT
          (`accounts.kind='master'`, `master_account_covering_unit`,
          `BR-CUS-170`) and wave I already names the owner's account on the
          Account tab, so half the reason had rotted while the sentence sat
          here — hard-won law 1 in its ordinary form. What is still open is
          `OQ-316`'s remaining word: with a running toilet through 3 kgal, base
          -only bills $8.00 and full billing bills $20.00, and nobody has
          chosen. So the rows are drawn, they say the owner is billed, and they
          do NOT say what the figure is.
          ⚠ **ITS NEIGHBOUR WENT, AND THE DIFFERENCE IS WHY THIS ONE STAYS.**
          A second `ArrivesWith` stood here explaining why r10's `Closing read`
          and `Final bill` columns are missing (`DEF-509`). The blueprint has
          since RATIFIED a six-column table that contains neither, so those two
          are no longer an absence a clerk is owed a paragraph about — an
          explained absence whose explanation expired. `DEF-509` stays open
          because the underlying gap is real; the prose went because the frame
          it was arguing with is no longer the drawing. This one is different:
          `OQ-316` is a live question about MONEY on rows that ARE drawn. */}
      <ArrivesWith
        title={t("metering.units.occupancy.vacancyTitle")}
        message={t("metering.units.occupancy.vacancyArrivesWith")}
        tracks="OQ-316"
      />
    </Panel>
  );
}

/** The tenant's today as `YYYY-MM-DD`. A vacancy that has not ended is measured
 *  to today, and `DateCell` renders it in the tenant's own zone and format. */
function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

/** One entry of the occupancy timeline: a tenancy, or the gap before it. */
export type OccupancyEntry =
  | { kind: "tenancy"; row: AccountRow }
  | { kind: "vacancy"; from: string; to: string | null; days: number };

/**
 * `F4` (`PUJ-42`) — **THE GAPS BETWEEN TENANCIES, AS ROWS.**
 *
 * The tab drew *Occupant · Account · Start · End · Status* and nothing else, so
 * the stretches when NOBODY held the unit did not exist on the one screen whose
 * whole job is to say who held it and when. A landlord asking *how long did my
 * flat stand empty* could not be answered from the tab that exists to answer it.
 *
 * ⚠ **DERIVED FROM THE TENANCIES EITHER SIDE — NOTHING NEW IS STORED AND
 * NOTHING IS ASKED OF THE SERVER.** A vacancy is not a row anywhere in this
 * product and must not become one: it is the absence of an account, and a
 * stored vacancy would be a second copy of a fact the accounts already carry,
 * wrong the first time somebody backdates a move-in.
 *
 * ⚠ **A GAP IS COUNTED FROM THE DAY AFTER ONE TENANCY ENDS TO THE DAY BEFORE
 * THE NEXT BEGINS, INCLUSIVE.** A tenancy closing on the 28th and the next
 * opening on 1 June leaves **29 · 30 · 31 · four days**, which is
 * `CR-089`'s own worked figure (*"28 May to 1 Jun 2026 · 4 days"* — the
 * sentence names the two TENANCY dates and the count between them). Back-to-
 * back tenancies (`closed_at` + 1 day == the next `opened_at`) produce **no
 * row**: a zero-day vacancy is not a vacancy, and drawing one would put a
 * meaningless row between every pair of tenancies in the estate.
 *
 * ⚠ **THE TRAILING GAP IS OPEN-ENDED AND IS MEASURED TO TODAY.** A unit whose
 * last tenancy closed and which nobody has taken since is vacant NOW, which is
 * the case a landlord actually asks about. It draws *Current* in the End
 * column, the same word an open tenancy draws.
 *
 * ⛔ **NO LEADING GAP IS DRAWN.** The stretch before the FIRST tenancy would
 * have to start when the unit was created, and `UnitRow` carries no created-at;
 * inventing one from the first account's start would draw a zero-day row on
 * every unit in the product. Reported rather than guessed.
 *
 * ⛔ **A ROW WITH NO `opened_at` CANNOT BOUND A GAP** and is passed through as a
 * tenancy with no vacancy computed against it: a date nobody recorded is not a
 * date to subtract from.
 *
 * Ordered oldest first — the reverse of what `GET /accounts` returns — because
 * a timeline that reads downwards is the only order in which a gap sits
 * BETWEEN the two tenancies that produced it.
 */
export function occupancyTimeline(
  rows: readonly AccountRow[],
  today: string,
): readonly OccupancyEntry[] {
  const ordered = [...rows]
    .filter((row) => row.opened_at !== null)
    .sort((a, b) => (a.opened_at ?? "").localeCompare(b.opened_at ?? ""));
  const undated = rows.filter((row) => row.opened_at === null);
  const out: OccupancyEntry[] = [];
  let previousEnd: string | null = null;
  let previousWasOpen = false;
  for (const row of ordered) {
    if (previousEnd !== null && !previousWasOpen) {
      const gap = vacancyBetween(previousEnd, row.opened_at as string);
      if (gap !== null) {
        out.push(gap);
      }
    }
    out.push({ kind: "tenancy", row });
    previousEnd = row.closed_at;
    previousWasOpen = row.closed_at === null;
  }
  // The trailing gap: the last tenancy ENDED and nothing followed it.
  if (previousEnd !== null && !previousWasOpen) {
    const days = daysBetween(previousEnd, today);
    if (days > 0) {
      out.push({ kind: "vacancy", from: addDays(previousEnd, 1), to: null, days });
    }
  }
  return [...out, ...undated.map((row) => ({ kind: "tenancy" as const, row }))];
}

/** The gap between one tenancy's end and the next one's start, or null when
 *  they are back to back (or overlap, which is a data state this screen
 *  reports by drawing no vacancy rather than a negative one). */
export function vacancyBetween(closedAt: string, nextOpenedAt: string): OccupancyEntry | null {
  const days = daysBetween(closedAt, nextOpenedAt) - 1;
  if (days <= 0) {
    return null;
  }
  return {
    kind: "vacancy",
    from: addDays(closedAt, 1),
    to: addDays(nextOpenedAt, -1),
    days,
  };
}

/** Whole days from one calendar date to another. **UTC on purpose**: these are
 *  calendar dates with no time in them, and a local-zone `Date` shifts one of
 *  the two across a DST boundary and answers 3 for a four-day gap. */
export function daysBetween(from: string, to: string): number {
  const a = Date.parse(`${from}T00:00:00Z`);
  const b = Date.parse(`${to}T00:00:00Z`);
  if (Number.isNaN(a) || Number.isNaN(b)) {
    return 0;
  }
  return Math.round((b - a) / 86_400_000);
}

/** A calendar date shifted by whole days, back as `YYYY-MM-DD`. */
export function addDays(date: string, days: number): string {
  const at = Date.parse(`${date}T00:00:00Z`);
  if (Number.isNaN(at)) {
    return date;
  }
  return new Date(at + days * 86_400_000).toISOString().slice(0, 10);
}

/**
 * `F2` (`PUJ-28`) — **THE ACCOUNT ON THE OVERVIEW.**
 *
 * PO 2026-09-08, verbatim: *"Unit → Overview - please display account if
 * occupied"*. The Overview drew *Occupant / account · Quentin Ortega ·
 * AC-2026-00041* — a NAME with a number trailing it as a qualifier, which is
 * the wrong way round and is nine tenths of what a clerk opening a unit is
 * actually asking. `CR-089` §3 names the seven facts: *"The number, the
 * holder, the status, what is owed and when, the deposit held and whether
 * autopay will take it, with one link out."*
 *
 * ── IT COSTS NO SECOND READ OF THE SAME FACTS ──────────────────────────────
 * This calls `getUnitAccount` under `unitAccountQueryKey` — **the same key the
 * Account tab uses**, so React Query serves both from one request and a clerk
 * moving Overview → Account issues nothing at all. Wave I built
 * `customers/unit_account_facts.py` for that tab and the temptation here was to
 * assemble the same seven facts out of `GET /accounts?f.unit_id=`, which is
 * what the tab itself did before `DEF-CUS-4691` — and which cannot see a
 * deposit, a protection or an autopay reading at all, because those are not
 * columns on a list row.
 *
 * ⚠ **THE OVERVIEW IS A SUMMARY AND THE TAB IS THE RECORD.** Six facts here
 * against the tab's twenty-odd; the section closes on *Open the account tab →*
 * rather than repeating it. `B14` rule 32's budget is one sentence per section
 * and this section spends it on the vacancy case, where the sentence is the
 * whole content.
 *
 * ⚠ **"WHEN" IS A STATED ABSENCE AND IT IS THE ACCOUNT HEADER'S OWN, WORD FOR
 * WORD.** `CR-089`'s worked line reads *"Owes $61.40, due 24 Sep"*. There is no
 * due date to draw: `BR-CUS-033` makes it the OLDEST STILL-OPEN bill's, and
 * *which bill is still open* is a payments position nothing publishes —
 * `ledger.reporting.ar_positions` sums the AR account per customer and says
 * nothing per invoice. `AccountDetailPage`'s header already states exactly that
 * absence (`customers.account.awaits.dueDate`), and this reuses **that key**
 * rather than wording a second sentence about one gap: `B14` rule 34's *one
 * pair of words per concept* applies to an absence as much as to a fact, and
 * `CR-043` finding 11 is what an unlabelled *"Not known yet"* under a figure
 * costs — the PO read it as being about the balance.
 */
export function UnitOverviewAccount(props: {
  unit: UnitRow;
  client: ApiClient;
  t: Translator;
  regional: RegionalProps;
  /** ⚠ **REQUIRED, NOT OPTIONAL** (hard-won law 2). An optional handler that
   *  the one caller forgot to pass renders a button that does nothing, every
   *  test still passes, and the door is dead — which is the exact failure this
   *  section's own link is meant to fix. */
  onOpenAccountTab: () => void;
}) {
  const { t, unit } = props;
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props.regional);
  const on = (value: string) => formatDate(value, timeZone, dateFormat);
  const accountQuery = useQuery({
    queryKey: unitAccountQueryKey(unit.id),
    queryFn: () => getUnitAccount(unit.id, props.client),
  });

  const heading = <h4 className="text-h5 mt-6 mb-2">{t("metering.units.tab.account")}</h4>;

  if (accountQuery.isPending) {
    return (
      <>
        {heading}
        <LoadingSkeleton variant="card" />
      </>
    );
  }
  const answer = accountQuery.data;
  // The module is unwired. NOT an empty block — an empty block would state that
  // this unit has no account, which is a claim nobody made (wave I's own
  // reasoning on the tab, and the same sentence so the two cannot differ).
  if (answer === undefined || answer.facts_unavailable !== null) {
    return (
      <>
        {heading}
        <p className="met-panel-hint">{t("metering.units.account.factsUnavailable")}</p>
      </>
    );
  }

  const current = answer.account;
  const facts = answer.facts;

  // ── VACANT (and a common area, which is a different sentence) ────────────
  // `BR-MET-101`: the flag is what separates a hallway from a flat nobody is
  // renting, and telling a clerk a hallway is *vacant* is the one place those
  // two must not read alike. Both name the OWNER's account and link to it
  // (`BR-CUS-170`), because *base charges bill to the owner* with no owner
  // named is half a sentence.
  if (current === null || facts === null) {
    const common = unit.is_common_area;
    return (
      <>
        {heading}
        <p className="met-panel-hint" data-overview-account={answer.no_account_reason ?? "vacant"}>
          <strong>
            {common
              ? t("metering.units.account.commonAreaTitle")
              : t("metering.units.account.vacantTitle")}
          </strong>{" "}
          {common
            ? t("metering.units.account.commonAreaOwnerBilled")
            : t("metering.units.account.vacantOwnerBilled")}
        </p>
        {answer.owner_account === null ? (
          <p className="met-panel-hint">{t("metering.units.account.ownerNone")}</p>
        ) : (
          <FactList>
            <Fact label={t("metering.units.account.ownerAccount")}>
              <InlineLinkTo to={tenantPath(accountDetailPath(answer.owner_account.id))}>
                {answer.owner_account.account_no ?? <Dash />}
              </InlineLinkTo>
              {answer.owner_account.name !== null && (
                <span className="met-qualifier"> · {answer.owner_account.name}</span>
              )}
            </Fact>
          </FactList>
        )}
      </>
    );
  }

  return (
    <>
      {heading}
      <FactList>
        {/* The NUMBER leads and the holder is the qualifier — the reverse of
            what this Overview drew, and the whole of `F2`'s complaint. The
            number is what a clerk quotes on the phone and searches by. */}
        <Fact label={t("metering.units.account.account")}>
          <InlineLinkTo to={tenantPath(accountDetailPath(current.id))}>
            {current.account_no ?? <Dash />}
          </InlineLinkTo>
          {current.name !== null && <span className="met-qualifier"> · {current.name}</span>}
        </Fact>
        {/* The TENANT's own label for the status (`BR-CUS-055` reference data),
            never a code and never this screen's translation of one. */}
        <Fact label={t("metering.units.account.status")}>
          {current.status_name}
          {current.opened_at !== null && (
            <span className="met-qualifier">
              {" · "}
              {t("metering.units.account.sinceDate", { date: on(current.opened_at) })}
            </span>
          )}
        </Fact>
        {/* ⚠ **`MoneyCell`, NEVER THE RAW STRING** — `DEF-595` put
            `48.450000 USD` on this very screen. And a NULL balance is not zero:
            `AccountRow.balance` is null when the books could not be asked, and
            `$0.00` there looks exactly like a settled account (`DEF-127`).
            The due date beside it is the stated absence described above. */}
        <Fact label={t("metering.units.account.balance")}>
          {current.balance === null ? (
            <Dash>{t("metering.units.account.balanceUnavailable")}</Dash>
          ) : (
            <MoneyCell
              amount={current.balance}
              currency={current.balance_currency ?? current.currency}
            />
          )}
          <span className="met-qualifier">
            {" · "}
            {t("customers.account.awaits.dueDate")}
          </span>
        </Fact>
        <Fact label={t("metering.units.account.deposit")}>
          {facts.deposit.any ? (
            <>
              <MoneyCell amount={facts.deposit.held} currency={facts.deposit.currency} />
              {facts.deposit.received_on !== null && (
                <span className="met-qualifier">
                  {" · "}
                  {t("metering.units.account.depositTaken", { date: on(facts.deposit.received_on) })}
                </span>
              )}
            </>
          ) : (
            <Dash>{t("metering.units.account.depositNone")}</Dash>
          )}
        </Fact>
        {/* `I3`'s reading, SERVER-side: autopay and cash-only are read together
            because *enrolled* and *will actually be taken* are different facts.
            Deriving it here would be a second implementation of the rule
            `DEF-070` already cost this product once. */}
        <Fact label={t("metering.units.account.autopay")}>
          <span data-autopay={facts.autopay.reading}>{autopaySentence(facts.autopay, t)}</span>
        </Fact>
      </FactList>
      <div className="mt-3">
        {/* ONE link out (`CR-089` §3's own words). It goes to the unit's own
            Account TAB and not to S21: the tab is the fuller record of THIS
            unit's account and it is one click away without leaving the unit,
            which is the dead-end `F5` complains about in the other direction.
            S21 is reachable from there. */}
        <Button variant="secondary" size="sm" onClick={props.onOpenAccountTab}>
          {t("metering.units.overview.openAccountTab")}
        </Button>
      </div>
    </>
  );
}

export const unitAccountsQueryKey = (unitId: string) =>
  ["accounts", "by-unit", unitId] as const;

/**
 * `GET /units/{id}/account` — the Account tab's own key.
 *
 * ⚠ **A SEPARATE KEY FROM `unitAccountsQueryKey` ABOVE, WHICH THE OCCUPANCY TAB
 * STILL USES.** The two reads answer different questions: Occupancy wants EVERY
 * account this unit has ever carried, in order; this wants the ONE that
 * occupies it now, with everything hanging off it. Sharing a key would make the
 * timeline and the account tab invalidate each other for no reason and would
 * hand whichever loaded second the wrong shape.
 */
export const unitAccountQueryKey = (unitId: string) =>
  ["units", "account", unitId] as const;

/**
 * The account in force on the unit: the one with no end date, newest start
 * first. A unit with only closed accounts has no CURRENT account and this
 * returns null rather than the most recent closed one — "closed six months ago"
 * is not the account a clerk means when they open this tab.
 */
export function currentAccount(rows: readonly AccountRow[]): AccountRow | null {
  const open = rows.filter((row) => row.closed_at === null);
  if (open.length === 0) {
    return null;
  }
  return [...open].sort((a, b) => (b.opened_at ?? "").localeCompare(a.opened_at ?? ""))[0];
}

/**
 * `PUJ-27` · `BR-MET-1162` — a unit's point, and which of the two it is.
 *
 * ⚠ **THE FALLBACK IS SHOWN, NOT HIDDEN.** A flat reads its building's point
 * and SAYS SO; a cabin reads its own and says that. Both are correct answers
 * and they are different facts, which is exactly why the ruling requires the
 * screen to name which — printing two numbers alone would make a cabin 300
 * metres from its site office and a flat inside the building look identical.
 *
 * ⚠ **`point.source` COMES FROM THE SERVER AND IS NOT RE-DERIVED HERE.**
 * `selectors.unit_point` is the one definition of the fallback; a client that
 * decided it again from `lat`/`lng` would be a second one, and hard-won law 1
 * is what happens when two of them drift.
 *
 * ⚠ **THE FORM IS NOT A MAP.** PO 2026-09-08, verbatim: *"we dont need this
 * right now - Drag the pin to correct it"*. Two boxes, and both or neither —
 * the server refuses half a point by name, because half a point is neither
 * placed nor fallen back and the rule has no third state.
 */
export function UnitPointFact(props: {
  unit: UnitRow;
  client: ApiClient;
  t: Translator;
}) {
  const { unit, t } = props;
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [lat, setLat] = useState(unit.lat ?? "");
  const [lng, setLng] = useState(unit.lng ?? "");
  const [notice, setNotice] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => updateUnit(unit.id, body, props.client),
    onSuccess: () => {
      setEditing(false);
      setNotice(null);
      void queryClient.invalidateQueries({ queryKey: ["units", unit.id] });
    },
    // BR-SHL-020: plain language, from the server's own message_key — this is
    // where `metering.unit.point_needs_both` and the range refusal reach a
    // person. A refusal rendered as silence is the defect `PUJ-03` is about.
    onError: (error: unknown) => setNotice(apiErrorText(error, t)),
  });

  if (editing) {
    return (
      <>
        <TextField
          id="unit_lat"
          label={t("metering.premises.field.lat")}
          value={lat}
          onChange={setLat}
          numeric
        />
        <TextField
          id="unit_lng"
          label={t("metering.premises.field.lng")}
          value={lng}
          onChange={setLng}
          numeric
        />
        {notice !== null && <RefusalStrip>{notice}</RefusalStrip>}
        <Button
          size="sm"
          onClick={() =>
            save.mutate({ lat: lat.trim() || null, lng: lng.trim() || null })
          }
        >
          {t("metering.unit.point.save")}
        </Button>{" "}
        <Button variant="secondary" size="sm" onClick={() => setEditing(false)}>
          {t("confirm.cancel")}
        </Button>
      </>
    );
  }

  return (
    <>
      {unit.point.lat && unit.point.lng ? (
        <>
          {unit.point.lat}, {unit.point.lng}
          <span className="met-qualifier">
            {" · "}
            {unit.point.source === "unit"
              ? t("metering.unit.point.own")
              : t("metering.unit.point.fromBuilding")}
          </span>
        </>
      ) : (
        <Dash>{t("metering.unit.point.none")}</Dash>
      )}{" "}
      <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
        {unit.point.source === "unit"
          ? t("metering.unit.point.useBuilding")
          : t("metering.unit.point.give")}
      </Button>
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-002@947cf31 (story+rules snapshot hash — EP-MET-01; co-story US-MET-001@947cf31)
// generated: 2026-08-09 by story-coder v1 (W1 Premises & Units + Assets frontend lane) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-10 (US-SHL-020 conversion — this S15 detail wears the shared PageHeader too, which is what let `DetailTabs` be deleted)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [US-SHL-020 conversion 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 593 passed / 141 todo across 46 files✔ (567 passed / 138 todo was the pre-conversion baseline) · vite build✔ · run_gates 12 PASS · 0 FAIL · 2 SKIP✔ (G14 prototype-conformance included) · trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ — 296+83 was the pre-W1 baseline and a CONCURRENT Plans & Rates lane is adding to the same suite; this packet contributes 103 passing + 28 todo across 7 files and reduced nothing. The 28 todos are browser-interaction, server/RLS-isolation and unbuilt-neighbour-lane scope, each named in its own test · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: [2026-08-22 PRM-02/PRM-03 conformance lane · DEF-580/584/595] E3 the eyebrow stops at the premise ADDRESS: `UnitRow` carries no `area_path`, so r10's third and fourth segments (`North · Route 3`) are absent rather than fetched with a second request — DEF-590 · E3 the sub-line drops r10's `access: side gate, dog on property`: there is no access field on `UnitCore` or on `units`, and a reassuring blank in front of a meter reader is the one guess this screen must never make — DEF-591 · E3 the Assets table draws four of r10's five columns; `Last read` has no source on a registry row (DEF-592) and is stated under the table rather than rendered as em-dashes, which would read as "never read" · E3 `Move-out…` (DEF-594) is rendered DISABLED WITH ITS REASON under BR-SHL-025 — the flow is the Accounts module's and it is not wired to something adjacent (hard-won law 2) · [2026-08-22 CR-028 debt sweep] `+ Assign from inventory` is WIRED (DEF-593 CLOSED): inline inventory picker (`f.status=unassigned`) → the assets module's own `/assets/:id/reassign?unit=<id>` with this unit preselected; the write-blocked role keeps the disabled-with-reason button (tests: UnitAssignFromInventory.dom.test.tsx + AssetLifecycle.test.tsx preselect case) · E3 the Assets tab reads the PREMISES registry answer and narrows it by `assigned_unit_id` because ASSET_FILTERS still declares no `unit_id`; same query key PRM-02's Assets tab uses, so it costs no extra request · E3 the Occupancy table draws five of r10's seven columns — closing read and final bill are DEF-509 — and r10's GAP callout stays the two stated absences (DEF-509, OQ-316) rather than a sentence asserting base-only billing that OQ-316 has not ruled
// exceptions: E2 US-SHL-020 — this screen is S15's detail rather than one of the S14 screens the conversion ticket named; it was converted because it was the last `DetailTabs` caller, and leaving one behind would have kept a second tab-strip implementation alive for exactly one screen · E2 the back link's "←" belongs to PageHeader, so the label is `metering.units.title` and `metering.units.detail.back` ("← Units") is no longer read here — the rendered link is unchanged and the catalog key is untouched · E3 the Plan-history tab renders the unit's CURRENT plan plus the honest arrives-with note: BR-CUS-013's `unit_plan_assignments` rows are rating-owned, the metering seam reports `history_recorded:false` while that writer is unwired, and NO endpoint reads them back — reported · E3 the current plan renders as the tariff UUID because the unit payload carries `default_tariff_id` only (no name), and resolving it would need a per-tariff read the picker query does not guarantee — reported · E3 the Assets tab reads the unit's own `meters` because BR-AST-041's filter set has a premises filter but no unit filter · E3 the Account-history tab is the arrives-with state (customers owns no tables in W1)
// status: VERIFIED-UNRATIFIED (r10 conformance re-verified in Chromium 2026-08-22 — the header, the Assets table, the Plan and Account actions and the entity's own audit rows, all photographed)
// ──────────────────────────────────────────────────────────
