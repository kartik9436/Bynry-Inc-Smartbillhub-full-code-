// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-004 (S19 Move-In wizard, step 1 · Unit) · CR-171-BRC10
//           P2.18 (unit + card + four groups) · P2.19 (Move-in date) · P2.20
//           (Services and meters) · P2.21 (Field visit) — images 30, 31, 32
// Rules:    BR-CUS-017 · BR-CUS-020 · BR-CUS-021 · BR-CUS-022 · BR-CUS-056 ·
//           BR-CUS-1101 (which of the unit's services start) · BR-AST-003 (a
//           sub-meter and a device nest under their meter) · BR-MET-129 (below
//           the last read — advice here, the commit is metering's) ·
//           BR-WRK-055 · hard rules 3 (a reading carries its unit) and 8 (the
//           address is walked from the premises, by the server) · B14 rules
//           21 (Tailwind; on route-b-migrated.txt), 31 (no code or id on
//           screen), 33, 37 (a drawn figure is an illustration), 41–44
// Data:     `GET /units/{id}/move-in-facts` · `GET /units/{id}/move-in-meters`
//           · `POST /units/{id}/move-in-meters/check` (§9.FLOW) · the Field
//           visit's own reads (`FieldVisitOrders`, `layout="panel"`)
// Tests:    moveInWizard/StepUnit.dom.test.tsx · MoveInWizard.test.tsx
// ───────────────────────────────────────────────────────
// **IMAGE 30, BUILT FROM THE PICTURE (B14 rule 42) AND TO OUR UI STANDARD
// (rule 44).** Four boxes, top to bottom: *Unit* (the vacant-unit picker, the
// unit's card and its Building · Unit · Owner · History groups), *Move-in
// date*, *Services and meters* (a Start tick per service, the meter tree, the
// opening read with its unit, a ▸ that opens the meter's facts — image 31 —
// and *Below the last read.* the moment it is typed — image 32), and *Field
// visit*. Park / Continue are the frame's.
//
// ⚠ **THE OLD THREE PANELS ARE GONE, NOT KEPT BESIDE THE NEW ONES.** The
// services chip-picker (`ChipMultiSelect`), the facts list (previous account,
// *the unit keeps its last plan*) and the eight-column reading table
// (`MoveInReadingsTable`, which the move-out and the transfer still mount)
// were three answers to what image 30 draws as one table and one card. A
// Start tick replaces the chip-picker and writes the SAME state
// (`setChosenServices`), so the payload and a parked draft are unchanged.
//
// ⚠ **WHAT IS NOT DRAWN AND WHY (rule 33 puts the why here, not on screen).**
// *Follows water* (sewer priced on water's volume) is a RATING fact the read
// does not serve, so an unmetered service says *Not metered* and nothing more;
// the drawn *Sized by W-5000 less W-5000-S1* is the same fact and is not
// invented. *Earliest start* is not drawn: the date's own refusal names it.
import { useQuery } from "@tanstack/react-query";
import { cloneElement, isValidElement, useEffect, useMemo, useState } from "react";
import type { ReactElement, ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { ApiClient, ApiResponse } from "@/api/client";
import { Button } from "@/components/Button";
import { Chip } from "@/components/Chip";
import { formatDate, todayInZone } from "@/components/DateCell";
import { formatMoney } from "@/components/MoneyCell";
import { DatePickerField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo, RefusalStrip } from "@/components/Surfaces";
import { CellTick, TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";
import { formatQuantity } from "@/components/UnitCell";
import type { WizardStepVerdict } from "@/components/WizardFrame";
import { MeterReadingEntry, readDateProblem } from "@/features/metering/MeterReadingEntry";
import type { ReadDateProblem } from "@/features/metering/MeterReadingEntry";
import { unitDetailPath } from "@/features/metering/meteringShared";
import { ServiceTags } from "@/features/rating/ratingShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { FieldVisitOrders, fieldVisitProblem } from "@/features/work/FieldVisitOrders";
import type { FieldVisitValue } from "@/features/work/FieldVisitOrders";
import { useTenantPath } from "@/routing/tenantPath";

import { getUnitMoveInFacts, getUnitMoveInMeters } from "../moveDetail/moveDetailEndpoints";
import { readFirst } from "../meterTreeOrder";
import { READ_DATE_CLEARED, withReadDraft } from "../moveReadsCapture";
import type { ReadDraftRow, ReadsDraft } from "../moveReadsCapture";
import type { MoveInWizardContext, StepOwn } from "./moveInWizardContext";

// ══════════════════════════════════════════════════════════════════════════
// The reads (§9.FLOW) — the full answer this step draws
// ══════════════════════════════════════════════════════════════════════════

/** `GET /units/{id}/move-in-facts`, as served (§9.FLOW P1.17). The details
 *  view types the slice IT draws (`moveDetailEndpoints.UnitMoveInFacts`);
 *  this is the whole answer, read through the same fetcher. */
export interface StepUnitFacts {
  unit: {
    id: string;
    unit_no: string | null;
    label: string | null;
    unit_type: string | null;
    floor_label: string | null;
    square_feet: number | string | null;
    is_common_area: boolean;
    occupancy: "vacant" | "occupied";
    address: { line1: string | null; city: string | null; state: string | null; postal_code: string | null } | null;
  };
  building: {
    premise_no: string | null;
    name: string | null;
    premises_type: string | null;
    premises_type_name: string | null;
    inside_city_limits: boolean | null;
    area_code: string | null;
    area_name: string | null;
    parcel: string | null;
    parcel_verified: boolean | null;
    routes: {
      code: string;
      name: string | null;
      service: string | null;
      cycle_code: string | null;
      cycle_name: string | null;
    }[];
  };
  owner: { name: string | null; account_no: string | null; status_name: string | null; billed_while_vacant: boolean } | null;
  history: {
    first_occupant: boolean;
    previous: {
      account_no: string | null;
      name: string | null;
      closed_at: string | null;
      /** CR-181-BRC10 F1 — what it still owes, the LEDGER's decimal string;
       *  `null` = the books cannot say (never drawn as 0). */
      outstanding?: string | null;
      currency?: string | null;
    } | null;
    /** `null` = rating cannot say — never drawn as 0. */
    plan_changes: number | null;
  };
}

/** One row of `GET /units/{id}/move-in-meters` (§9.FLOW P1.18; `facts` and
 *  `size_name` from lane MVI-WIZ-UNIT, §15). */
export interface StepUnitMeter {
  asset_no: string;
  kind: string;
  type_name: string | null;
  location_note: string | null;
  size_class: string | null;
  size_name?: string | null;
  reads_as: { multiplier: string | null; digits: number | null } | null;
  unit: string | null;
  last_read: { value: string; unit: string | null; read_at: string | null; channel?: string | null } | null;
  needs_opening_read: boolean;
  last_test_date: string | null;
  test_interval_months: number | null;
  facts?: {
    serial_no: string | null;
    meter_type_name: string | null;
    read_method_name: string | null;
    installed_on: string | null;
    manufacturer: string | null;
    model: string | null;
    seal_no: string | null;
    certified_to: string | null;
  };
  children: StepUnitMeter[];
}

export interface StepUnitMeters {
  unit_id: string;
  services: { service: string; start: boolean; metered: boolean; meters: StepUnitMeter[] }[];
  unplaced: StepUnitMeter[];
  counts: { services: number; meters: number; devices: number; opening_reads_needed: number };
  assets_readable: boolean;
}

interface BelowLastRow {
  meter_no: string;
  value: unknown;
  last_value: unknown;
  unit: string | null;
  below_last_read: boolean | null;
}

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** `POST /units/{id}/move-in-meters/check` — image 32. Advice only; it
 *  writes nothing and the commit is still metering's (`BR-MET-129`). */
export async function checkOpeningReads(
  unitId: string,
  reads: readonly { meter_no: string; value: string }[],
  client: ApiClient,
): Promise<{ rows: BelowLastRow[] }> {
  return requireData(
    await client.post<{ rows: BelowLastRow[] }>(`/units/${encodeURIComponent(unitId)}/move-in-meters/check`, {
      reads,
    }),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// Pure helpers — provable without a browser
// ══════════════════════════════════════════════════════════════════════════

/** One line of *Services and meters*, in the drawn order. */
export interface MeterLine {
  key: string;
  /** The service this line belongs to, or `null` for a meter on no offered
   *  service (`unplaced` — SHOWN, never dropped). */
  service: string | null;
  /** The service's first line carries its Start tick and its name. */
  head: boolean;
  /** `null` on an unmetered service's one line. */
  meter: StepUnitMeter | null;
  /** 0 = a meter; 1+ = a sub-meter or device under it (BR-AST-003). */
  depth: number;
}

export function meterLines(read: StepUnitMeters | undefined): MeterLine[] {
  if (read === undefined) return [];
  const out: MeterLine[] = [];
  const walk = (service: string | null, meter: StepUnitMeter, depth: number, head: boolean) => {
    out.push({ key: `${service ?? "-"}:${meter.asset_no}`, service, head, meter, depth });
    // Image 30's order: what is READ (a sub-meter) before what is not (a
    // device behind the meter); within each, the server's order. The ONE
    // helper the details view uses too (`DEF-CUS-9765`).
    const children = readFirst(meter.children ?? []);
    for (const child of children) walk(service, child, depth + 1, false);
  };
  for (const service of read.services ?? []) {
    if ((service.meters ?? []).length === 0) {
      out.push({ key: `${service.service}:-`, service: service.service, head: true, meter: null, depth: 0 });
      continue;
    }
    service.meters.forEach((meter, index) => walk(service.service, meter, 0, index === 0));
  }
  for (const meter of read.unplaced ?? []) walk(null, meter, 0, false);
  return out;
}

/** A reading a clerk typed, by meter NUMBER — the key this step writes, and
 *  for a draft parked before it (keyed by asset id), the row whose `meterNo`
 *  is that number. */
export function draftFor(draft: ReadsDraft, assetNo: string): ReadDraftRow | undefined {
  return draft[assetNo] ?? Object.values(draft).find((row) => row.meterNo === assetNo);
}

/** Does this line take an opening read? A meter or sub-meter on a STARTED
 *  service (a meter on no offered service always may). A device never does. */
export function takesRead(line: MeterLine, started: readonly string[]): boolean {
  if (line.meter === null || !line.meter.needs_opening_read) return false;
  return line.service === null || started.includes(line.service);
}

/**
 * The started meters still waiting for an opening read.
 *
 * ⚠ **REQUIRED, AS IMAGE 30 MARKS IT — UNLESS A VISIT IS BOOKED.** The drawing
 * puts `*` on *Opening read* AND raises a *Move-in read* visit in the same
 * picture; a box a technician will fill cannot also be one the clerk must.
 * So the reads are required when the field visit has no row, and optional
 * when it has one (decision log, lane MVI-WIZ-UNIT). An estimate carried by a
 * draft parked under the old table counts as an answer.
 */
export function missingOpeningReads(
  lines: readonly MeterLine[],
  started: readonly string[],
  draft: ReadsDraft,
  visit: FieldVisitValue,
): string[] {
  if (!visit.none && visit.rows.length > 0) return [];
  return lines
    .filter((line) => takesRead(line, started))
    .map((line) => line.meter?.asset_no ?? "")
    .filter((assetNo) => {
      const row = draftFor(draft, assetNo);
      return row === undefined || (!row.estimate && row.value.trim() === "");
    });
}

/** The date an opening read's box shows: the clerk's, or the move-in day. */
export function openingReadDate(row: ReadDraftRow | undefined, openedAt: string): string {
  const own = row?.readAt.trim() ?? "";
  if (own === READ_DATE_CLEARED) return "";
  return own === "" ? openedAt : own;
}

/**
 * `DEF-CUS-10165` — **every typed opening read whose date is not lawful**,
 * by meter number. PO 2026-10-17, verbatim: *"Move-in, step 1 (opening) -
 * read date is required"*. Only a row with a VALUE is judged: an untyped
 * row posts nothing and has no date to be wrong. The bounds are
 * `MeterReadingEntry`'s own (`readDateProblem`): not after `today` (the
 * tenant's), not before the meter's last reading.
 */
export function openingReadDateProblems(
  lines: readonly MeterLine[],
  started: readonly string[],
  draft: ReadsDraft,
  openedAt: string,
  today: string,
): Map<string, ReadDateProblem> {
  const out = new Map<string, ReadDateProblem>();
  for (const line of lines) {
    if (!takesRead(line, started) || line.meter === null) continue;
    const row = draftFor(draft, line.meter.asset_no);
    if (row === undefined || row.estimate || row.value.trim() === "") continue;
    const problem = readDateProblem(openingReadDate(row, openedAt), {
      minDate: line.meter.last_read?.read_at ?? null,
      maxDate: today,
    });
    if (problem !== null) out.set(line.meter.asset_no, problem);
  }
  return out;
}

/** `×1 · 6 digits` — the multiplier trimmed of its six storage zeros. */
function readsAsText(meter: StepUnitMeter, t: Translator): string | null {
  if (meter.reads_as === null || meter.reads_as.multiplier === null || meter.reads_as.digits === null) {
    return null;
  }
  return t("customers.moveIn.meters.readsAs", {
    multiplier: formatQuantity(meter.reads_as.multiplier),
    digits: meter.reads_as.digits,
  });
}

/** A device's next test: its last test plus its interval, ISO. */
export function testDue(lastTest: string | null, months: number | null): string | null {
  if (lastTest === null || months === null) return null;
  const [y, m, d] = lastTest.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(y, m - 1 + months, d)).toISOString().slice(0, 10);
}

/** A ledger figure that is a debt — `null`/absent (unreadable) is not drawn. */
const owesMoney = (amount: string | null | undefined): boolean =>
  typeof amount === "string" && Number(amount) > 0;

const joined = (parts: readonly (string | null | undefined | false)[]): string =>
  parts.filter((part): part is string => typeof part === "string" && part !== "").join(" · ");

// ══════════════════════════════════════════════════════════════════════════
// Step 1 as the rail draws it
// ══════════════════════════════════════════════════════════════════════════

export function StepUnit(props: { ctx: MoveInWizardContext }) {
  const { ctx } = props;
  const { t } = ctx;
  const unitId = ctx.outgoingUnitId;
  const facts = useQuery({
    queryKey: ["move-in-step-unit-facts", unitId],
    queryFn: () => getUnitMoveInFacts(unitId, ctx.client) as unknown as Promise<StepUnitFacts>,
    enabled: unitId !== "",
    retry: false,
  });
  const meters = useQuery({
    queryKey: ["move-in-step-unit-meters", unitId],
    queryFn: () => getUnitMoveInMeters(unitId, ctx.client) as unknown as Promise<StepUnitMeters>,
    enabled: unitId !== "",
    retry: false,
  });
  const lines = useMemo(() => meterLines(meters.data), [meters.data]);
  // The lines this step drew, held as the step's OWN state so the verdict —
  // which the wizard calls with the context alone — checks the same meters
  // the table shows (`ctx.own.unit`, DEF-CUS-9729).
  const setOwn = ctx.own.unit.set;
  useEffect(() => {
    setOwn({ lines });
  }, [lines, setOwn]);
  const meterOptions = lines
    .filter((line) => line.meter !== null && line.depth === 0)
    .map((line) => ({
      value: line.meter?.asset_no ?? "",
      // `DEF-WRK-9784` — the row's Work order list is this service's templates.
      service: line.service,
      label: joined([
        line.meter?.asset_no,
        line.service === null ? null : t(`rating.service.${line.service}`, { defaultValue: line.service }),
      ]),
    }));

  const card = (
    <UnitCard facts={facts.data} pending={facts.isPending && unitId !== ""} failed={facts.isError} ctx={ctx} />
  );
  // The picker is the wizard's (`MoveInUnitPick`); the card goes INSIDE its
  // panel, as image 30 draws one box. On the account-scoped road there is no
  // picker, and the card has a *Unit* box of its own.
  const unitBox =
    ctx.picker !== null && isValidElement(ctx.picker) ? (
      cloneElement(ctx.picker as ReactElement<{ children?: ReactNode }>, { children: card })
    ) : (
      <Panel data-move-pick="unit">
        <h3 className="m-0 font-heading text-base font-semibold text-text">{t("customers.moveIn.find.panel")}</h3>
        {card}
      </Panel>
    );

  return (
    <div className="flex flex-col gap-5" data-step-unit="">
      {unitBox}
      {/* `DEF-CUS-10192` — on the standalone road the unit search's own
          warning (*"… is still on this unit. Start a move-out for them
          first."*) says this, with the one way forward; drawing this strip
          as well told the clerk twice, the second time with rationale. */}
      {ctx.unitFree || ctx.picker !== null ? null : (
        // BR-CUS-017: one active account per unit — the commit WILL be refused.
        <RefusalStrip role="alert">{t("customers.moveIn.unit.stillOccupied")}</RefusalStrip>
      )}
      <MoveInDatePanel ctx={ctx} />
      <ServicesAndMeters
        ctx={ctx}
        read={meters.data}
        pending={meters.isPending && unitId !== ""}
        failed={meters.isError}
        lines={lines}
      />
      {/* The ONE field-visit component every flow mounts (decision log
          2026-09-23), drawn as image 30's panel. Orders are raised when the
          move-in completes (`BR-WRK-055`), never on Continue. */}
      <FieldVisitOrders
        flowKind="move_in"
        layout="panel"
        value={ctx.fieldVisit}
        onChange={ctx.setFieldVisit}
        showErrors={ctx.tried.unit}
        services={ctx.ticked}
        meters={meterOptions}
        defaultDue={ctx.openedAt === "" ? undefined : ctx.openedAt}
        unitId={unitId === "" ? undefined : unitId}
        dateFormat={ctx.dateFormat}
        timeZone={ctx.timeZone}
        t={t}
        client={ctx.client}
      />
    </div>
  );
}

/**
 * Continue on step 1.
 *
 * ⛔ **A STRING, NOT `false`, FOR THE SERVICES (`DEF-936`)** — the server's
 * own sentence for the same refusal. The date, the opening reads and the work
 * orders turn red only once Continue was pressed.
 */
/** The service a meter on this step's lines measures, by its number. */
function meterServiceOn(lines: readonly MeterLine[], assetNo: string): string | undefined {
  return lines.find((line) => line.meter?.asset_no === assetNo)?.service ?? undefined;
}

export function stepUnitVerdict(ctx: MoveInWizardContext): WizardStepVerdict {
  if (!ctx.unitFree) {
    return false;
  }
  if (ctx.serviceOffer.length > 0 && ctx.ticked.length === 0) {
    return ctx.t("customers.move_in.services_required");
  }
  ctx.markTried("unit");
  const lines = ctx.own.unit.value.lines;
  return (
    ctx.dateProblem === null &&
    fieldVisitProblem(ctx.fieldVisit, (assetNo) => meterServiceOn(lines, assetNo)) === null &&
    missingOpeningReads(lines, ctx.ticked, ctx.readsDraft, ctx.fieldVisit).length === 0 &&
    // DEF-CUS-10165 — a typed reading's date is required and bounded.
    openingReadDateProblems(lines, ctx.ticked, ctx.readsDraft, ctx.openedAt, todayInZone(ctx.timeZone)).size === 0
  );
}

/**
 * This step's own state, held by the wizard across the rail (see `StepOwn`):
 * the meter lines the table drew, which the verdict reads to know which
 * opening reads are still missing. Nothing of it reaches the commit or a
 * parked draft — it is re-read from the server whenever the step is drawn,
 * and everything step 1 asks the clerk is state the wizard already holds and
 * parks (the unit, the services, the date, the reads, the visit).
 */
export interface StepUnitOwn {
  lines: readonly MeterLine[];
}

export function useStepUnitOwn(): StepOwn<StepUnitOwn> {
  const [value, set] = useState<StepUnitOwn>({ lines: [] });
  return { value, set, payload: {}, park: {}, hydrate: () => undefined };
}

// ══════════════════════════════════════════════════════════════════════════
// P2.18 · the unit card and its four groups
// ══════════════════════════════════════════════════════════════════════════

function Group(props: { title: string; head: ReactNode; lines: ReactNode[]; name: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 px-4 py-3" data-unit-group={props.name}>
      <span className="font-heading text-table-header font-semibold uppercase tracking-table-header text-neutral-700">
        {props.title}
      </span>
      <span className="font-heading text-base font-semibold text-text">{props.head}</span>
      {props.lines.map((line, index) => (
        <span key={index} className="text-sm text-neutral-700">
          {line}
        </span>
      ))}
    </div>
  );
}

/** *8 Quarry Lane, Ottumwa, IA 52501 · Kestrel Park ph. 2* — walked by the
 *  server from the premises (hard rule 8); the screen only joins it. */
function whereLine(facts: StepUnitFacts): string {
  const address = facts.unit.address;
  const street =
    address === null
      ? null
      : [address.line1, [address.city, [address.state, address.postal_code].filter(Boolean).join(" ")].filter(Boolean).join(", ")]
          .filter((part) => part !== null && part !== "")
          .join(", ");
  return joined([street, facts.building.name]);
}

function UnitCard(props: {
  facts: StepUnitFacts | undefined;
  pending: boolean;
  failed: boolean;
  ctx: MoveInWizardContext;
}) {
  const { ctx } = props;
  const { t } = ctx;
  const tenantPath = useTenantPath();
  const { i18n } = useTranslation();
  if (ctx.outgoingUnitId === "") return null;
  if (props.pending) return <LoadingSkeleton variant="card" />;
  if (props.failed || props.facts === undefined) {
    return (
      <RefusalStrip className="mt-4" role="alert" data-unit-card="failed">
        {t("customers.moveIn.unitCard.failed")}
      </RefusalStrip>
    );
  }
  const { unit, building, owner, history } = props.facts;
  const where = whereLine(props.facts);
  const unitType =
    unit.unit_type === null
      ? null
      : t(`metering.units.type.${unit.unit_type}`, { defaultValue: unit.unit_type.replace(/_/gu, " ") });
  const routes = building.routes ?? [];
  const routeNames = [...new Set(routes.map((row) => row.name ?? row.code))];
  const cycleNames = [
    ...new Set(routes.map((row) => row.cycle_name ?? row.cycle_code).filter((name): name is string => !!name)),
  ];
  const squareFeet =
    unit.square_feet === null || unit.square_feet === "" ? null : Number(unit.square_feet);

  return (
    <div className="mt-4 flex flex-col gap-4" data-unit-card="ready">
      <div className="flex items-start justify-between gap-4 border border-divider bg-neutral-100 px-4 py-3">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="font-heading text-h3 font-bold text-text" data-unit-card-title="">
            {joined([unit.unit_no, unit.label])}
          </span>
          {where === "" ? null : <span className="text-base text-neutral-700">{where}</span>}
        </div>
        <span className="flex flex-none flex-wrap items-center gap-2" data-unit-card-chips="">
          <StatusPill tone={unit.occupancy === "vacant" ? "success" : "warning"}>
            {t(`customers.moveIn.unitCard.${unit.occupancy}`)}
          </StatusPill>
          {unitType === null ? null : <Chip>{unitType}</Chip>}
          {history.first_occupant ? <Chip>{t("customers.moveIn.unitCard.firstOccupant")}</Chip> : null}
        </span>
      </div>
      <div className="grid grid-cols-4 divide-x divide-divider border border-divider">
        <Group
          name="building"
          title={t("customers.moveIn.unitCard.group.building")}
          head={joined([building.premise_no, building.name])}
          lines={[
            joined([
              building.premises_type_name,
              building.inside_city_limits === null
                ? null
                : t(
                    building.inside_city_limits
                      ? "customers.moveIn.unitCard.insideLimits"
                      : "customers.moveIn.unitCard.outsideLimits",
                  ),
            ]),
            joined([
              (building.area_name ?? building.area_code)
                ? t("customers.moveIn.unitCard.area", { area: building.area_name ?? building.area_code })
                : null,
              building.parcel ? t("customers.moveIn.unitCard.parcel", { parcel: building.parcel }) : null,
              building.parcel && building.parcel_verified !== null
                ? t(
                    building.parcel_verified
                      ? "customers.moveIn.unitCard.verified"
                      : "customers.moveIn.unitCard.unverified",
                  )
                : null,
            ]),
            joined([
              routeNames.length === 0
                ? null
                : t("customers.moveIn.unitCard.route", { route: routeNames.join(", ") }),
              cycleNames.length === 0
                ? null
                : t("customers.moveIn.unitCard.cycle", { cycle: cycleNames.join(", ") }),
            ]),
          ].filter((line) => line !== "")}
        />
        <Group
          name="unit"
          title={t("customers.moveIn.unitCard.group.unit")}
          head={joined([unitType, unit.floor_label])}
          lines={[
            squareFeet === null || Number.isNaN(squareFeet)
              ? ""
              : t("customers.moveIn.unitCard.squareFeet", {
                  count: squareFeet,
                  value: formatQuantity(String(squareFeet)),
                }),
            t(
              unit.is_common_area
                ? "customers.moveIn.unitCard.commonArea"
                : "customers.moveIn.unitCard.notCommonArea",
            ),
          ].filter((line) => line !== "")}
        />
        <Group
          name="owner"
          title={t("customers.moveIn.unitCard.group.owner")}
          head={owner === null ? t("customers.moveIn.unitCard.noOwner") : (owner.name ?? owner.account_no ?? "")}
          lines={
            owner === null
              ? []
              : [
                  owner.account_no ?? "",
                  owner.billed_while_vacant ? t("customers.moveIn.unitCard.billedWhileVacant") : "",
                ].filter((line) => line !== "")
          }
        />
        <Group
          name="history"
          title={t("customers.moveIn.unitCard.group.history")}
          head={
            history.first_occupant || history.previous === null
              ? t("customers.moveIn.unitCard.firstOccupant")
              : (history.previous.name ?? history.previous.account_no ?? "")
          }
          lines={[
            history.previous === null || history.first_occupant
              ? ""
              : joined([
                  history.previous.account_no,
                  history.previous.closed_at === null
                    ? null
                    : t("customers.moveIn.unitCard.closedOn", {
                        date: formatDate(history.previous.closed_at, ctx.timeZone, ctx.dateFormat),
                      }),
                ]),
            // CR-181-BRC10 F1 — what the last account still owes (the ledger's).
            history.previous === null || history.first_occupant || !owesMoney(history.previous.outstanding) ? (
              ""
            ) : (
              <span data-unit-history-owes={history.previous.outstanding ?? ""}>
                <StatusPill tone="danger">
                  {t("customers.moveIn.reopen.owes", {
                    amount: formatMoney(
                      history.previous.outstanding ?? "0",
                      history.previous.currency ?? "USD",
                      i18n.language,
                    ),
                  })}
                </StatusPill>
              </span>
            ),
            history.plan_changes === null || history.plan_changes === 0 ? (
              ""
            ) : (
              <>
                {t("customers.moveIn.unitCard.planChanged", { count: history.plan_changes })}
                {" · "}
                <InlineLinkTo to={`${tenantPath(unitDetailPath(unit.id))}?tab=plan`} data-unit-plan-history="">
                  {t("customers.moveIn.unitCard.see")}
                </InlineLinkTo>
              </>
            ),
          ].filter((line) => line !== "")}
        />
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// P2.19 · Move-in date
// ══════════════════════════════════════════════════════════════════════════

function MoveInDatePanel(props: { ctx: MoveInWizardContext }) {
  const { ctx } = props;
  const { t } = ctx;
  return (
    <Panel data-move-in-date="">
      <h3 className="m-0 mb-4 font-heading text-base font-semibold text-text">{t("customers.moveIn.date.title")}</h3>
      <div className="w-64">
        {/* BR-PAY-033's shape, BR-CUS-056's value: the proposal is the day
            after the outgoing account's move day; anything typed wins.
            `DEF-CUS-6358` — the utility's own date format. */}
        <DatePickerField
          id="opened_at"
          label={t("customers.moveIn.field.movedInOn")}
          required
          regional
          value={ctx.openedAt}
          prefill={ctx.earliest ?? undefined}
          dateFormat={ctx.dateFormat}
          onChange={ctx.setOpenedAt}
          help={t("customers.moveIn.date.help")}
          error={
            ctx.dateProblem === "on_or_before_move_day"
              ? t("customers.moveIn.start.onMoveDay")
              : ctx.tried.unit && ctx.dateProblem === "required"
                ? t("customers.moveIn.date.required")
                : undefined
          }
        />
      </div>
    </Panel>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// P2.20 · Services and meters
// ══════════════════════════════════════════════════════════════════════════

/** The typed readings worth asking about, settled 300 ms after the last key
 *  (IS-3's debounce, so a clerk typing 1,031 asks once and not four times). */
function useSettledReads(lines: readonly MeterLine[], draft: ReadsDraft): { meter_no: string; value: string }[] {
  const typed = lines
    .filter((line) => line.meter !== null && line.meter.last_read !== null)
    .map((line) => ({
      meter_no: line.meter?.asset_no ?? "",
      value: draftFor(draft, line.meter?.asset_no ?? "")?.value.trim() ?? "",
    }))
    .filter((row) => row.value !== "" && !Number.isNaN(Number(row.value)));
  const key = JSON.stringify(typed);
  const [settled, setSettled] = useState(key);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(key), 300);
    return () => clearTimeout(timer);
  }, [key]);
  return JSON.parse(settled) as { meter_no: string; value: string }[];
}

function ServicesAndMeters(props: {
  ctx: MoveInWizardContext;
  read: StepUnitMeters | undefined;
  pending: boolean;
  failed: boolean;
  lines: MeterLine[];
}) {
  const { ctx, lines } = props;
  const { t } = ctx;
  const [open, setOpen] = useState<readonly string[]>([]);
  // DEF-CUS-10050 — the meters whose box holds a FETCHED reading, so a value
  // typed over one drops the head-end's read date with it. A row never
  // fetched types exactly as before.
  const [fetched, setFetched] = useState<readonly string[]>([]);
  const settled = useSettledReads(lines, ctx.readsDraft);
  const check = useQuery({
    queryKey: ["move-in-step-unit-check", ctx.outgoingUnitId, JSON.stringify(settled)],
    queryFn: () => checkOpeningReads(ctx.outgoingUnitId, settled, ctx.client),
    enabled: ctx.outgoingUnitId !== "" && settled.length > 0,
    retry: false,
  });
  if (ctx.outgoingUnitId === "") return null;
  if (props.pending) {
    return (
      <Panel data-move-in-meters="loading">
        <LoadingSkeleton variant="table" />
      </Panel>
    );
  }
  if (props.failed || props.read === undefined) {
    return (
      <Panel data-move-in-meters="failed">
        <RefusalStrip role="alert">{t("customers.moveIn.meters.failed")}</RefusalStrip>
      </Panel>
    );
  }
  // Below the last read: the server's answer, and only while the box still
  // holds the value it answered about (a stale warning is worse than none).
  const below = new Set(
    (check.data?.rows ?? [])
      .filter((row) => row.below_last_read === true)
      .filter((row) =>
        lines.some(
          (line) =>
            line.meter?.asset_no === row.meter_no &&
            draftFor(ctx.readsDraft, row.meter_no)?.value.trim() === String(row.value),
        ),
      )
      .map((row) => row.meter_no),
  );
  const started = ctx.ticked;
  const today = todayInZone(ctx.timeZone);
  // A date that is already wrong is named at once — it is a fact about what
  // was typed, not a field left empty — so it does not wait for Continue.
  const datesBad = openingReadDateProblems(lines, started, ctx.readsDraft, ctx.openedAt, today);
  const missing = ctx.tried.unit
    ? new Set(missingOpeningReads(lines, started, ctx.readsDraft, ctx.fieldVisit))
    : new Set<string>();
  const counts = props.read.counts;
  const services = props.read.services ?? [];
  const startedCount = services.filter((service) => started.includes(service.service)).length;
  const needed = lines.filter((line) => takesRead(line, started)).length;

  function toggle(service: string, on: boolean): void {
    const next = on ? [...new Set([...started, service])] : started.filter((code) => code !== service);
    // The drawn order — the offer's — so the payload compares cleanly.
    ctx.setChosenServices(services.map((row) => row.service).filter((code) => next.includes(code)));
    if (!on) {
      // A service that does not start takes no opening read: its typed
      // readings leave the draft rather than riding to the commit.
      const drop = new Set(
        lines
          .filter((line) => line.service === service && line.meter !== null)
          .map((line) => line.meter?.asset_no ?? ""),
      );
      const kept: ReadsDraft = {};
      for (const [key, row] of Object.entries(ctx.readsDraft)) {
        if (!drop.has(row.meterNo)) kept[key] = row;
      }
      ctx.setReadsDraft(kept);
    }
  }

  const dash = <span className="text-neutral-700">—</span>;

  const columns: TableArrayColumn<MeterLine>[] = [
    {
      key: "start",
      label: t("customers.moveIn.meters.col.start"),
      cell: (line) =>
        line.head && line.service !== null ? (
          <CellTick
            name={`start-${line.service}`}
            label={t("customers.moveIn.meters.startLabel", {
              service: t(`rating.service.${line.service}`, { defaultValue: line.service }),
            })}
            checked={started.includes(line.service)}
            onChange={(on) => toggle(line.service ?? "", on)}
          />
        ) : null,
    },
    {
      key: "service",
      label: t("customers.moveIn.meters.col.service"),
      cell: (line) => {
        if (line.depth > 0 && line.meter !== null) {
          return (
            <span className="flex items-center gap-2 pl-2">
              <span aria-hidden="true" className="text-neutral-600">
                └
              </span>
              <StatusPill tone={line.meter.kind === "sub_meter" ? "warning" : "neutral"}>
                {t(`customers.moveIn.meters.kind.${line.meter.kind}`, { defaultValue: line.meter.type_name ?? "" })}
              </StatusPill>
            </span>
          );
        }
        if (!line.head || line.service === null) return null;
        const service = services.find((row) => row.service === line.service);
        return (
          <span className="flex flex-col">
            <span className="flex items-center gap-2 font-semibold text-text">
              <ServiceTags services={[line.service]} />
              {t(`rating.service.${line.service}`, { defaultValue: line.service })}
            </span>
            <span className="text-sm text-neutral-700">
              {t(service?.metered === false ? "customers.moveIn.meters.notMetered" : "customers.moveIn.meters.metered")}
            </span>
          </span>
        );
      },
    },
    {
      key: "meter",
      label: t("customers.moveIn.meters.col.meter"),
      cell: (line) =>
        line.meter === null ? (
          dash
        ) : (
          <span className="flex flex-col" data-meter-row={line.meter.asset_no}>
            <span className="tabular-nums text-text">{line.meter.asset_no}</span>
            {(line.meter.location_note ?? line.meter.type_name) ? (
              <span className="text-sm text-neutral-700">{line.meter.location_note ?? line.meter.type_name}</span>
            ) : null}
          </span>
        ),
    },
    {
      key: "size",
      label: t("customers.moveIn.meters.col.size"),
      // The tenant's NAME for the size, never its code (B14 rule 31).
      cell: (line) => (line.meter?.size_name ? line.meter.size_name : dash),
    },
    {
      key: "readsAs",
      label: t("customers.moveIn.meters.col.readsAs"),
      cell: (line) => (line.meter === null ? dash : (readsAsText(line.meter, t) ?? dash)),
    },
    {
      key: "lastRead",
      label: t("customers.moveIn.meters.col.lastRead"),
      numeric: true,
      cell: (line) =>
        line.meter?.last_read ? (
          <span className="flex flex-col items-end">
            <span>
              {/* Hard rule 3: the reading travels with its unit. */}
              {joined([formatQuantity(line.meter.last_read.value)])}{" "}
              {line.meter.last_read.unit ?? line.meter.unit ?? ""}
            </span>
            {line.meter.last_read.read_at ? (
              <span className="text-sm text-neutral-700">
                {formatDate(line.meter.last_read.read_at, ctx.timeZone, ctx.dateFormat)}
              </span>
            ) : null}
          </span>
        ) : (
          dash
        ),
    },
    {
      key: "openingRead",
      label: t("customers.moveIn.meters.col.openingRead"),
      numeric: true,
      header: (
        <>
          {t("customers.moveIn.meters.col.openingRead")}
          <span className="field-required" aria-hidden="true">
            *
          </span>
          {" · "}
          {t("customers.moveIn.reads.col.readDate")}
          <span className="field-required" aria-hidden="true">
            *
          </span>
        </>
      ),
      cell: (line) => {
        const meter = line.meter;
        if (meter === null) return dash;
        if (!meter.needs_opening_read) {
          // A device is never read; its next test is what a clerk taking
          // over needs to know (image 30: *Not read · test due 03/2027*).
          const due = testDue(meter.last_test_date, meter.test_interval_months);
          return (
            <span className="text-sm text-neutral-700" data-device-test={meter.asset_no}>
              {due === null
                ? t("customers.moveIn.meters.notRead")
                : t("customers.moveIn.meters.notReadTestDue", {
                    date: formatDate(due, ctx.timeZone, ctx.dateFormat),
                  })}
            </span>
          );
        }
        if (!takesRead(line, started)) return dash;
        const row = draftFor(ctx.readsDraft, meter.asset_no);
        const isBelow = below.has(meter.asset_no);
        const unit = meter.unit ?? meter.last_read?.unit ?? "";
        return (
          <span className="flex justify-end text-left" data-opening-read={meter.asset_no}>
            {/* DEF-CUS-10050 (Fetch, metered rows only — this cell is reached
                only by a meter or sub-meter on a started service) and
                DEF-CUS-10165 (the read date, required). ONE shared component
                for reading + date + Fetch (PO 2026-10-17, *"use same code
                components"*). No Estimate: *"estimate will not be reuired in
                move in"*. A fetched reading keeps the meter's own date. */}
            <MeterReadingEntry
              meterNo={meter.asset_no}
              idPrefix={`moveIn-open-read-${meter.asset_no}`}
              readingLabel={t("customers.moveIn.meters.readLabel", { meter: meter.asset_no })}
              unit={unit === "" ? null : unit}
              lastReading={
                meter.last_read === null ? null : { value: meter.last_read.value, readAt: meter.last_read.read_at }
              }
              value={row?.value ?? ""}
              readDate={openingReadDate(row, ctx.openedAt)}
              estimate={row?.estimate === true}
              fetched={fetched.includes(meter.asset_no)}
              defaultReadDate={ctx.openedAt}
              // `DEF-CUS-10190` — the earliest lawful read date, said outright:
              // the meter's last reading, which after a move-out raised from
              // this move-in IS the old occupant's closing read (carried here).
              minDate={meter.last_read?.read_at?.slice(0, 10) ?? undefined}
              maxDate={today}
              showFetch
              labelsHidden
              required
              showDateError={ctx.tried.unit || (datesBad.get(meter.asset_no) ?? "required") !== "required"}
              warning={isBelow ? t("customers.moveIn.meters.belowLast") : undefined}
              error={missing.has(meter.asset_no) ? t("customers.moveIn.meters.readRequired") : undefined}
              client={ctx.client}
              t={t}
              timeZone={ctx.timeZone}
              dateFormat={ctx.dateFormat}
              onChange={(next) => {
                const isFetched = fetched.includes(meter.asset_no);
                if (next.fetched !== isFetched) {
                  setFetched((now) =>
                    next.fetched ? [...now, meter.asset_no] : now.filter((no) => no !== meter.asset_no),
                  );
                }
                ctx.setReadsDraft(
                  withReadDraft(ctx.readsDraft, meter.asset_no, meter.asset_no, {
                    value: next.value,
                    // The move-in day is DEFERRED (`""`), so a later change of
                    // the move-in date still carries an untouched row with it.
                    readAt: next.fetched
                      ? next.readDate
                      : next.readDate === ""
                        ? READ_DATE_CLEARED
                        : next.readDate === ctx.openedAt
                          ? ""
                          : next.readDate,
                  }),
                );
              }}
            />
          </span>
        );
      },
    },
    {
      key: "more",
      label: t("customers.moveIn.meters.col.more"),
      header: <span className="sr-only">{t("customers.moveIn.meters.col.more")}</span>,
      cell: (line) => {
        const meter = line.meter;
        if (meter === null || line.depth > 0 || meter.facts === undefined) return null;
        const isOpen = open.includes(meter.asset_no);
        const name = t(isOpen ? "customers.moveIn.meters.collapse" : "customers.moveIn.meters.expand", {
          meter: meter.asset_no,
        });
        return (
          <Button
            size="row"
            variant="secondary"
            aria-expanded={isOpen}
            aria-label={name}
            title={name}
            data-meter-expand={meter.asset_no}
            onClick={() => setOpen(isOpen ? open.filter((no) => no !== meter.asset_no) : [...open, meter.asset_no])}
          >
            {isOpen ? "▾" : "▸"}
          </Button>
        );
      },
    },
  ];

  /** Image 31 — *W-5000 · SN 77123 · Positive displacement · Manual read ·
   *  Installed Jan 2026 · Badger M25 · Seal S-0912 · Certified to 03/03/2027*.
   *  A fact not recorded is left out, never written as *unknown*. */
  const factsLine = (meter: StepUnitMeter): ReactNode => {
    const f = meter.facts;
    if (f === undefined) return undefined;
    const makeModel = [f.manufacturer, f.model].filter(Boolean).join(" ");
    const rest = joined([
      f.serial_no ? t("customers.moveIn.meters.facts.serial", { serial: f.serial_no }) : null,
      f.meter_type_name,
      // A meter class and a read method can carry the same name (*walk-by*);
      // the fact is said once.
      f.read_method_name === f.meter_type_name ? null : f.read_method_name,
      f.installed_on
        ? t("customers.moveIn.meters.facts.installed", {
            date: formatDate(f.installed_on, ctx.timeZone, ctx.dateFormat),
          })
        : null,
      makeModel,
      f.seal_no ? t("customers.moveIn.meters.facts.seal", { seal: f.seal_no }) : null,
      f.certified_to
        ? t("customers.moveIn.meters.facts.certified", {
            date: formatDate(f.certified_to, ctx.timeZone, ctx.dateFormat),
          })
        : null,
    ]);
    return (
      <span data-meter-facts={meter.asset_no}>
        <span className="font-semibold">{meter.asset_no}</span>
        {rest === "" ? null : <> · {rest}</>}
      </span>
    );
  };

  return (
    <TableArray<MeterLine>
      readOnly
      title={t("customers.moveIn.meters.title")}
      fact={joined([
        t("customers.moveIn.meters.count.services", { count: counts.services }),
        t("customers.moveIn.meters.count.meters", { count: counts.meters }),
        counts.devices > 0 ? t("customers.moveIn.meters.count.devices", { count: counts.devices }) : null,
      ])}
      collection="move-in-meters"
      columns={columns}
      rows={lines}
      rowKey={(line) => line.key}
      emptyText={t("customers.moveIn.meters.none")}
      rowNested={(line) => line.depth > 0}
      rowDetail={(line) =>
        line.meter !== null && line.depth === 0 && open.includes(line.meter.asset_no)
          ? factsLine(line.meter)
          : undefined
      }
      note={joined([
        services.length === 0
          ? null
          : t("customers.moveIn.meters.startCount", { started: startedCount, count: services.length }),
        t("customers.moveIn.meters.readsNeeded", { count: needed }),
      ])}
    />
  );
}
