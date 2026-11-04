// ── Trace ──────────────────────────────────────────────
// Change:   Lane E wave 1 — SPLIT OUT OF `NewConnectWizard.tsx`, unchanged.
//           Lane H wave 2 — 2026-09-16 — **THE CELL STOPS BEING A TICK.** PO,
//           verbatim: *"units inherit all utility services from premises -
//           hence we have to show all utility services"* and *"it means you
//           will ahve unit, utility service, asset type, Size, installatiion
//           date, work order, occupany - default - also all these values
//           shoudl come as default"*. One row per unit × service, seven
//           columns, every one of them defaulted.
//           Built from `05-prototype/02 Accounts Menu Blueprint.pdf` p088–p089
//           rendered AS AN IMAGE (B14 rule 42), not from its extracted text.
//           **MAINTENANCE 2026-09-16 (2.278.2)** — `DEF-CUS-5480` and
//           `DEF-CUS-5481`, both reported by the PO from the running grid and
//           both invisible to every check in this repo. (1) The hidden labels
//           this grid draws escaped the screen's scroller and put a phantom
//           782px of empty page under it, which took the panel border and the
//           Back/Continue footer with them — fixed in the kit, see
//           `HIDDEN_FIELD` in `FormModal.tsx`. (2) The WORK ORDER cell is a
//           dropdown now, PO verbatim: *"work order is drop down - you can give
//           default values ot it - but you need to allow user to select it"*.
//           (3) The install date stopped drawing its own label on all fourteen
//           rows, which is what broke the row alignment (`DEF-SHL-5477`).
// Rules:    B18 §5.4.10 step 5 (*"availability belongs to the street, not to
//           a unit"*) · TC-NCT-6 (sewer derives from water, so a unit cannot
//           take sewer without it — a REFUSAL, not a warning) · BR-RAT-015
//           (sewer carries NO size class, by ruling) · BR-TEN-171 (the
//           ratified size classes) · BR-AST-042 / OQ-1361 (fire's asset type
//           is the fire line — PO 2026-10-02) · BR-MET-036 (occupancy is a UNIT fact) · B14
//           rule 21 (Tailwind only; this file is in `route-b-migrated.txt`) ·
//           rule 31 (no database id on screen) · rule 32 · rule 33 · rule 37
//           (a figure drawn in a wireframe is an ILLUSTRATION)
// Tests:    NewConnectWizard.test.tsx · NewConnectServicesStep.dom.test.tsx ·
//           10-scripts/def_cus_5480_step4_grid_walkthrough.mjs (the only one
//           that can see a LAYOUT fault — law 6)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THE GRID EXISTS AT ALL, AND WHY THE ARGUMENT IS NOT ON SCREEN
// ══════════════════════════════════════════════════════════════════════════
//
// The blueprint's own case for this grid is the COMMON AREA: *"It takes electric
// and water and no sewer — there is nothing to drain from a hallway and a car
// park."* p089 draws that sentence as a red callout under the table. **It is not
// rendered.** It is RATIONALE — why the product works this way — and B14 rule 33
// gives rationale zero words on screen. It is written here instead, which is
// what a docstring is for, and it is the reason every cell stays editable.
//
// **INHERITANCE IS A DEFAULT, NOT A LOCK.** Every unit opens with every service
// the premise takes already set, and the clerk drops the ones a particular unit
// does not take. That is the PO's *"units inherit all utility services from
// premises"* with the common area as its worked example.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT WAS DRAWN AND IS DELIBERATELY NOT BUILT
// ══════════════════════════════════════════════════════════════════════════
//
// ⛔ **THE DRAWN `Apply to all units` / `Choose per unit` RADIO IS DROPPED.**
// p088 draws it; inheritance makes the answer always *all*, so the second option
// is one nothing would ever pick — and a radio whose alternative is unreachable
// teaches a clerk a model the product does not have. The per-unit answer is the
// grid itself.
//
// ⚠ **THE DRAWN COUNTS ARE ILLUSTRATIONS (B14 rule 37).** p089 draws `Service
// points 20`, `Meters to fit 20`, `Work orders 9` and `6 units × 3 services =
// 18`. Not one of those is built to. Every count below is computed from the grid
// in front of the person, which is the whole reason the PO ruled they stay
// visible: *they change as the grid changes and are the only feedback that it is
// right*.
//
// ══════════════════════════════════════════════════════════════════════════
// WHERE EVERY DEFAULT COMES FROM — AND THE ONE THAT IS A JUDGMENT
// ══════════════════════════════════════════════════════════════════════════
//
// | Column         | Source                                                   |
// |----------------|----------------------------------------------------------|
// | Unit           | step 3's pattern                                         |
// | Utility service| `draft.premiseServices` — the tick list above this grid   |
// | Asset type     | `asset_types`, THE TENANT'S OWN LIST, over the map below  |
// | Size           | `service_size_classes`, THE TENANT'S OWN LIST, scoped     |
// | Install date   | the build's target activation date                       |
// | Work order     | the proposal already read for step 5, matched by service |
// | Occupancy      | `occupancyOfUnit()` — a UNIT fact, shared with step 3     |
//
// ⚠ **THE SERVICE COLUMN IS NEVER TYPED INTO THIS SCREEN, AND THAT IS THE
// THIRD TIME THAT DEFECT WOULD HAVE BEEN WRITTEN.** The eleven services are
// hand-typed in `SignupWizard.tsx` and `ratingShared.tsx`, which is why `fire` —
// the eleventh — never appeared on the sign-up screen although the row existed,
// the API served it, `tsc` passed and every test passed. Here the rows come from
// `draft.premiseServices`, which is the clerk's own tick list, so a twelfth
// service appears the day the tenant offers it. **A missing service here is a
// meter nobody fits.**
//
// ⚠ **SIZES ARE SERVICE-SCOPED AT THE SERVER AND FILTERED ON THAT, NOT ON A
// CODE PREFIX.** `CR-065` (PO 2026-09-02) made `service_size_classes` publish
// `service: {id, code} | null`, and **NULL MEANS "NOBODY HAS SAID" AND LISTS ON
// EVERY SERVICE** — a tenant's own row entered before that ruling keeps working.
// Reading `W-`/`E-`/`FL-` off the front of a code would be a second answer to
// *which service is this size for*, and it would hide every tenant row.
import { useMemo, useState } from "react";

import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { getLookupEntries, getTenantServices } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { enabledServiceRows } from "@/features/metering/ServicesAvailableField";
import { SelectField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { PlainTable, RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { Button } from "@/components/Button";
import type { ProposedWorkOrder } from "@/features/work/workEndpoints";

import type { NewConnectDraft, UnitServiceCell } from "./newConnectDraft";
import { occupancyOfUnit, unitServiceKey } from "./newConnectDraft";
import type { DraftUnit, OccupancyChoice, Translator } from "./newConnectShared";
import {
  OCCUPANCY_CELL_WORDS,
  SERVICE_ASSET_DEFAULT,
  assetTypesForService,
  gridCounts,
  gridRows,
  occupancyCellWord,
  orderForService,
  sizesForService,
  workOrderOptions,
} from "./NewConnectUnitsStep";
import type { GridRow } from "./NewConnectUnitsStep";
import { ServiceTicks, StepIntro } from "./newConnectStepKit";

// ══════════════════════════════════════════════════════════════════════════
// THE HELPERS MOVED TO `NewConnectUnitsStep.tsx` — CR-150-BRC09, 2026-09-28
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS STEP IS ABSORBED INTO STEP 3 AND ITS STEP ID IS GOING.** The PO
// folded eight steps into five — *"we dont want any information to be reduced
// or lost"* — and Map services is one of the two that fold into Units. The
// field-by-field audit of what moved where is
// `05-prototype/new-connect-redesign-2026-09-28/step3-absorbed-field-audit.md`.
//
// ⚠ **THE ARITHMETIC MOVED RATHER THAN BEING COPIED, AND THE DIRECTION IS WHY.**
// This file already imported `OCCUPANCY_CELL_WORDS` from `NewConnectUnitsStep`,
// so importing the helpers back would have made a CYCLE out of a fold. One
// definition, in the file that now owns the screen; re-exported here so every
// existing importer — `NewConnectWizard.test.tsx` among them — keeps working
// for the life of this step.
export {
  SERVICE_ASSET_DEFAULT,
  SERVICE_ASSET_TYPES,
  assetTypesForService,
  gridCounts,
  gridRows,
  orderForService,
  sizesForService,
  workOrderOptions,
} from "./NewConnectUnitsStep";
export type { GridRow } from "./NewConnectUnitsStep";

// ══════════════════════════════════════════════════════════════════════════
// STEP 4 · MAP SERVICES
// ══════════════════════════════════════════════════════════════════════════

export function ServicesStep(props: {
  draft: NewConnectDraft;
  breaches: { unit: string; service: string }[];
  sewerGaps: string[];
  units: readonly DraftUnit[];
  proposed: readonly ProposedWorkOrder[];
  client: ApiClient;
  onPatch: (next: Partial<NewConnectDraft>) => void;
  t: Translator;
}) {
  // ══════════════════════════════════════════════════════════════════════════
  // WHAT THIS UTILITY ACTUALLY SELLS — PO ruling 2026-09-21
  // ══════════════════════════════════════════════════════════════════════════
  //
  // PO, verbatim: *"here filter only active Utility services for that Tenant"*.
  //
  // ⚠ **THIS REPLACES A HAND-TYPED LIST OF ALL ELEVEN PLATFORM SERVICES**
  // (`newConnectShared.TEN_SERVICES`, now deleted). Measured on 2026-09-21: the
  // demo utility has **electric and water enabled and nine disabled**, so
  // **nine of eleven tick boxes could not commit** — the server refuses each by
  // name, *"gas isn't one of the services this utility bills"*, after all eight
  // steps. Step 2 of this same wizard already asked the same question with a
  // control that correctly offered only the two.
  //
  // ⚠ **`queryKeys.tenantServices` — THE SHARED KEY, NOT A NEW-CONNECT ONE.**
  // `GET /settings/services` is the one place that answers which services a
  // tenant sells; `ServicesAvailableField`, the premises wizard, the assets
  // wizard and the units list all read it through this key, so they share one
  // cache and cannot drift. A key of our own would be a fourth answer to a
  // question that already has one.
  //
  // ⚠ **`TENANT-ENABLED` IS NOT `AVAILABLE AT THIS ADDRESS`, AND BOTH ARE
  // REAL.** A utility may sell gas at an address with no gas main. This list is
  // the TENANT filter and what the clerk ticks below is the ADDRESS one
  // (`premises.services_available`, `BR-MET-003`). Collapsing them would lose
  // a real distinction the decision log names explicitly.
  const tenantServicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(props.client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  /** The enabled subset, in the platform's own seed order — which is the order
   *  `GET /settings/services` returns. Never re-sorted here. */
  const offeredServices = useMemo(
    () => enabledServiceRows(tenantServicesQuery.data).map((row) => row.service),
    [tenantServicesQuery.data],
  );

  const assetTypesQuery = useQuery({
    queryKey: ["lookups", "asset_types", "new-connect"],
    queryFn: () => getLookupEntries("asset_types", { per: 200 }, props.client),
  });
  const sizesQuery = useQuery({
    queryKey: ["lookups", "service_size_classes", "new-connect"],
    queryFn: () => getLookupEntries("service_size_classes", { per: 200 }, props.client),
  });

  const assetTypeRows = useMemo(
    () => (assetTypesQuery.data?.results ?? []) as { code: string; name: string; category?: string }[],
    [assetTypesQuery.data],
  );
  const sizeRows = useMemo(
    () => (sizesQuery.data?.results ?? []) as { code: string; name: string; service?: unknown }[],
    [sizesQuery.data],
  );
  /** Which asset types ARE meters, from the tenant's own `category`. The drawn
   *  *"one per service point"* is an illustration; this is the real answer. */
  const meterTypeCodes = useMemo(
    () => new Set(assetTypeRows.filter((row) => row.category === "meters").map((row) => row.code)),
    [assetTypeRows],
  );

  const rows = useMemo(() => gridRows(props.draft, props.units), [props.draft, props.units]);
  /** Every job on offer, computed ONCE for the whole grid rather than per row —
   *  the list is the same on all fourteen. */
  const orders = useMemo(() => workOrderOptions(props.proposed), [props.proposed]);

  const assetTypeOptions = (service: string) => assetTypesForService(assetTypeRows, service);
  const sizeOptions = (service: string) => sizesForService(sizeRows, service);

  /** Every column's DEFAULT, resolved in one place so the screen, the counts
   *  and the commit cannot disagree about the same row. */
  const resolvedAssetType = (row: GridRow): string => {
    if (row.cell.assetType !== undefined) {
      return row.cell.assetType;
    }
    const usual = SERVICE_ASSET_DEFAULT[row.service] ?? "";
    return assetTypeOptions(row.service).some((type) => type.code === usual) ? usual : "";
  };
  const resolvedSize = (row: GridRow): string =>
    row.cell.sizeClass ?? sizeOptions(row.service)[0]?.code ?? "";
  const resolvedOrderId = (row: GridRow): string =>
    row.cell.workOrderTemplateId ?? orderForService(props.proposed, row.service)?.template_id ?? "";

  const counts = gridCounts(rows, meterTypeCodes, resolvedAssetType, resolvedOrderId);

  const patchCell = (key: string, patch: Partial<UnitServiceCell>) =>
    props.onPatch({
      unitServiceGrid: {
        ...props.draft.unitServiceGrid,
        [key]: { ...(props.draft.unitServiceGrid[key] ?? {}), ...patch },
      },
    });

  /** Occupancy is a UNIT fact, so editing it on ONE row moves the unit — the
   *  same map step 3 writes, and never a second answer. */
  const setOccupancy = (label: string, choice: OccupancyChoice) =>
    props.onPatch({ unitOccupancy: { ...props.draft.unitOccupancy, [label]: choice } });

  /** Tick or clear ONE service across every unit — p089's `Tick a column` and
   *  `Clear a column` carried into the long grid, where a "column" is the
   *  service the drawn matrix had one per column of. */
  const setColumn = (service: string, taken: boolean) => {
    const next = { ...props.draft.unitServiceGrid };
    for (const unit of props.units) {
      const key = unitServiceKey(unit.label, service);
      next[key] = { ...(next[key] ?? {}), taken };
    }
    props.onPatch({ unitServiceGrid: next });
  };

  /** p089's `Copy unit 1 to all`: the first unit's whole answer — what it
   *  takes and every value on those rows — onto every other unit. The common
   *  area is INCLUDED, because a clerk who presses *all* means all; they can
   *  then drop its sewer, which is the case the grid exists for. */
  const copyFirstUnitToAll = () => {
    const first = props.units[0];
    if (first === undefined) {
      return;
    }
    const next = { ...props.draft.unitServiceGrid };
    for (const unit of props.units) {
      if (unit.label === first.label) {
        continue;
      }
      for (const row of rows.filter((candidate) => candidate.unit.label === first.label)) {
        next[unitServiceKey(unit.label, row.service)] = {
          taken: row.taken,
          assetType: resolvedAssetType(row),
          sizeClass: resolvedSize(row),
          workOrderTemplateId: resolvedOrderId(row),
        };
      }
    }
    props.onPatch({ unitServiceGrid: next });
  };

  // ⚠ **LOCAL STATE, NOT A DERIVED CONSTANT.** A `<select>` whose `onChange`
  // does nothing is a control that looks live and is not — hard-won law 2's
  // mirror, and the three buttons beside it would all act on the first service
  // whatever the clerk picked.
  const [columnService, setColumnService] = useState("");
  const activeColumn =
    columnService !== "" && props.draft.premiseServices.includes(columnService)
      ? columnService
      : (props.draft.premiseServices[0] ?? "");
  const serviceName = (code: string) => props.t(`rating.service.${code}`, { defaultValue: code });

  return (
    <>
      <Panel as="section">
        <StepIntro
          title={props.t("customers.newConnect.step5.premise", {
            defaultValue: "Services available at this premise",
          })}
        />
        {/* ⚠ **THE THREE STATES ARE DRAWN, NOT ONLY THE HAPPY ONE.** An empty
            tick list is a true answer only when the read SUCCEEDED and the
            tenant really sells nothing; while the read is in flight, or after
            it failed, the same empty list would say *"this utility sells
            nothing"* — a screen with only its default state is a third of a
            screen. Each sentence is a FACT at B14 rule 33's six words. */}
        {tenantServicesQuery.isPending ? (
          <p className="mb-2 text-md" data-services-loading="">
            {props.t("customers.newConnect.step5.servicesLoading")}
          </p>
        ) : tenantServicesQuery.isError ? (
          <RefusalStrip data-services-failed="">
            {props.t("customers.newConnect.step5.servicesFailed")}
          </RefusalStrip>
        ) : (
          <>
            <p className="mb-2 text-md" data-availability-count="">
              {props.t("customers.newConnect.step5.available", {
                defaultValue: "{{count}} of {{total}} available at this address",
                count: props.draft.premiseServices.length,
                // The TENANT's enabled count, never the platform's eleven.
                total: offeredServices.length,
              })}
            </p>
            <ServiceTicks
              id="nc_premise_services"
              offer={offeredServices}
              chosen={props.draft.premiseServices}
              onChange={(premiseServices) => props.onPatch({ premiseServices })}
              t={props.t}
            />
          </>
        )}
      </Panel>

      <Panel as="section">
        <StepIntro
          title={props.t("customers.newConnect.step5.units", {
            defaultValue: "Services at each unit",
          })}
        />

        {/* ── THE THREE COUNTS ────────────────────────────────────────────
            PO-ruled to stay visible: they change as the grid changes and are
            the only feedback that it is right. Every one is computed from the
            rows below — none is the drawn figure (B14 rule 37). */}
        <PlainTable data-grid-counts="">
          <tbody>
            <tr>
              <td>
                {props.t("customers.newConnect.step5.servicePoints", {
                  defaultValue: "Service points",
                })}
              </td>
              <td className="tabular-nums" data-count="service-points">
                {counts.servicePoints}
              </td>
            </tr>
            <tr>
              <td>
                {props.t("customers.newConnect.step5.metersToFit", { defaultValue: "Meters to fit" })}
              </td>
              <td className="tabular-nums" data-count="meters">
                {counts.meters}
              </td>
            </tr>
            <tr>
              <td>
                {props.t("customers.newConnect.step5.workOrders", { defaultValue: "Work orders" })}
              </td>
              <td className="tabular-nums" data-count="work-orders">
                {counts.workOrders}
              </td>
            </tr>
          </tbody>
        </PlainTable>

        {/* ── THE THREE SHORTCUTS (p089) ──────────────────────────────────── */}
        <div className="mt-3 flex flex-wrap items-end gap-2" data-grid-shortcuts="">
          <SelectField
            id="nc_grid_column"
            label={props.t("customers.newConnect.step5.column", { defaultValue: "Service" })}
            value={activeColumn}
            onChange={setColumnService}
            options={props.draft.premiseServices.map((code) => ({
              value: code,
              label: serviceName(code),
            }))}
          />
          <Button variant="secondary" onClick={() => setColumn(activeColumn, true)}>
            {props.t("customers.newConnect.step5.tickColumn", { defaultValue: "Tick a column" })}
          </Button>
          <Button variant="secondary" onClick={() => setColumn(activeColumn, false)}>
            {props.t("customers.newConnect.step5.clearColumn", { defaultValue: "Clear a column" })}
          </Button>
          <Button variant="secondary" onClick={copyFirstUnitToAll}>
            {props.t("customers.newConnect.step5.copyFirst", {
              defaultValue: "Copy unit 1 to all",
            })}
          </Button>
        </div>

        {props.draft.premiseServices.length === 0 && (
          <Note className="mt-2 max-w-measure">
            {props.t("customers.newConnect.step5.nothingAvailable", {
              defaultValue: "No service is ticked above.",
            })}
          </Note>
        )}

        {/* ══════════════════════════════════════════════════════════════
            THE PER-UNIT INSTALL DATE IS GONE — `DEF-CUS-6101`, 2026-09-21
            ══════════════════════════════════════════════════════════════
            ⛔ **SIXTEEN DATE PICKERS ON A SEVEN-UNIT BLOCK, AND THE COMMIT
            SENT NONE OF THEM.** The value was written into the draft's
            `unitServiceGrid` as `installDate` and `commitPlanOf` never read it
            back out: the payload's meters carry `unit_label`, `service` and
            `asset_no` and nothing else. Every test of this step asserted the
            cells RENDER and that *Copy unit 1 to all* propagated them — both
            true — and none asserted the payload carried what the grid
            collected. Hard-won law 2 in its plainest form, and `G13` cannot see
            it: it is not an unpassed prop, it is a field that writes correctly
            and is never read.

            ⚠ **THE COLUMN IS REMOVED RATHER THAN WIRED, AND THAT IS NOT AN
            ANSWER TO `OQ-MET-12571`.** That question asks WHERE a planned
            per-unit date should live and offers three shapes; it is OPEN and
            nothing here chooses one. What is decided is smaller and is this
            screen's own: **a field that says it will not keep what you type is
            worse than no field.** It sat over the sentence *"Per-unit dates are
            not stored yet"*, which is RATIONALE on screen — B14 rule 33 puts
            that at zero words — and the honest form of that sentence is not to
            ask at all.

            ⚠ **WHAT IS LOST IS A PER-ROW OVERRIDE, NOT THE DATE.** The build's
            own planned date is `targetActivation`, typed ONCE on step 1, and it
            travels and is stored as `connections.target_activation`. Every cell
            here defaulted from it. The day `OQ-MET-12571` is answered, the
            column comes back WITH somewhere for its value to go.

            ⚠ **AND IT MUST NOT BECOME `assets.install_date`** — PO 2026-09-21,
            *"install date on work order completion - yes"*, so that column
            holds what actually HAPPENED. `DEF-MET-6066` and `DEF-MET-6067`
            fixed the server half of the same ruling; this is the half that was
            left, where the screen still asked. */}
        <PlainTable data-unit-service-grid="">
          <thead>
            <tr>
              <th>{props.t("customers.newConnect.step4.unit", { defaultValue: "Unit" })}</th>
              <th>
                {props.t("customers.newConnect.step5.service", { defaultValue: "Utility service" })}
              </th>
              <th>
                {props.t("customers.newConnect.step5.assetType", { defaultValue: "Asset type" })}
              </th>
              <th>{props.t("customers.newConnect.step5.size", { defaultValue: "Size" })}</th>
              <th>
                {props.t("customers.newConnect.step5.workOrder", { defaultValue: "Work order" })}
              </th>
              <th>
                {props.t("customers.newConnect.step4.occupancy", { defaultValue: "Occupancy" })}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const types = assetTypeOptions(row.service);
              const sizes = sizeOptions(row.service);
              const occupancy = occupancyOfUnit(props.draft, row.unit);
              return (
                <tr key={row.key} data-grid-row={row.key} data-taken={row.taken ? "yes" : "no"}>
                  <td>{row.unit.label}</td>
                  <td>
                    {/* The drawn TICK, carried into the long grid. Unticking is
                        how the common area drops the sewer it cannot have. */}
                    <label className="inline-flex items-center gap-2 text-md">
                      <input
                        type="checkbox"
                        id={`nc_take_${row.key}`}
                        checked={row.taken}
                        onChange={(event) => patchCell(row.key, { taken: event.target.checked })}
                      />
                      <span>{serviceName(row.service)}</span>
                    </label>
                  </td>
                  <td>
                    {types.length === 0 ? (
                      /* A STATED ABSENCE, CLOSED BY DEFAULT (B14 rule 32). Fire
                         is BR-AST-042's open question and storm water has no
                         device at all — two different facts, one dash, and
                         neither of them a guess. */
                      <span aria-hidden="true">—</span>
                    ) : (
                      <SelectField
                        id={`nc_asset_${row.key}`}
                        labelHidden
                        label={props.t("customers.newConnect.step5.assetType", {
                          defaultValue: "Asset type",
                        })}
                        value={resolvedAssetType(row)}
                        onChange={(assetType) => patchCell(row.key, { assetType })}
                        options={types.map((type) => ({ value: type.code, label: type.name }))}
                        placeholder={props.t("customers.newConnect.step5.noAsset", {
                          defaultValue: "None",
                        })}
                      />
                    )}
                  </td>
                  <td>
                    {sizes.length === 0 ? (
                      /* Sewer, BY RULING — it is a share of the water usage
                         charge (BR-RAT-015), reads no register and has nothing
                         to size. Not a gap. */
                      <span aria-hidden="true">—</span>
                    ) : (
                      <SelectField
                        id={`nc_size_${row.key}`}
                        labelHidden
                        label={props.t("customers.newConnect.step5.size", { defaultValue: "Size" })}
                        value={resolvedSize(row)}
                        onChange={(sizeClass) => patchCell(row.key, { sizeClass })}
                        options={sizes.map((size) => ({ value: size.code, label: size.name }))}
                      />
                    )}
                  </td>
                  <td data-work-order={resolvedOrderId(row) === "" ? "none" : "set"}>
                    {/* ⚠ **A COLUMN THE CLERK DECIDES IS A CONTROL, NOT A WORD**
                        (`DEF-CUS-5481`). This cell printed the proposed template's
                        name as bare text while every other cell on the row was a
                        control, so a clerk who wanted a different job on ONE unit
                        had no way to say so. The value was always right, which is
                        why every assertion that reads the VALUE passed over it.
                        ⚠ **THE TEMPLATE'S NAME, NEVER ITS ID** (B14 rule 31): the
                        id is the option's value and a stamp target, and the word
                        a clerk reads is the template's own name. */}
                    {orders.length === 0 ? (
                      /* A STATED ABSENCE (B14 rule 32) — this build proposed no
                         jobs at all, so there is nothing to choose between. */
                      <span aria-hidden="true">—</span>
                    ) : (
                      <SelectField
                        id={`nc_workorder_${row.key}`}
                        labelHidden
                        label={props.t("customers.newConnect.step5.workOrder", {
                          defaultValue: "Work order",
                        })}
                        value={resolvedOrderId(row)}
                        onChange={(workOrderTemplateId) =>
                          patchCell(row.key, { workOrderTemplateId })
                        }
                        options={orders}
                        placeholder={props.t("customers.newConnect.step5.noOrder", {
                          defaultValue: "None",
                        })}
                      />
                    )}
                  </td>
                  <td data-occupancy={row.unit.isCommonArea ? "none" : occupancy}>
                    {occupancy === null ? (
                      <span aria-hidden="true">—</span>
                    ) : (
                      <SelectField
                        id={`nc_grid_occupancy_${row.key}`}
                        labelHidden
                        label={props.t("customers.newConnect.step4.occupancy", {
                          defaultValue: "Occupancy",
                        })}
                        value={occupancy}
                        onChange={(next) => setOccupancy(row.unit.label, next as OccupancyChoice)}
                        options={OCCUPANCY_CELL_WORDS.map((entry) => ({
                          value: entry.code,
                          label: occupancyCellWord(entry.code, props.t),
                        }))}
                      />
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </PlainTable>


        {/* Two refusals, and they are REFUSALS — Continue is blocked while
            either stands, because both describe service that cannot exist. */}
        {props.breaches.length > 0 && (
          <RefusalStrip data-breach="availability">
            {props.t("customers.newConnect.step5.breach", {
              defaultValue: "{{unit}} takes {{service}}. This address does not.",
              unit: props.breaches[0].unit,
              service: serviceName(props.breaches[0].service),
            })}
          </RefusalStrip>
        )}
        {props.sewerGaps.length > 0 && (
          <RefusalStrip data-breach="sewer-without-water">
            {props.t("customers.newConnect.step5.sewerNeedsWater", {
              defaultValue: "{{unit}} takes sewer, not water. Sewer follows water.",
              unit: props.sewerGaps[0],
            })}
          </RefusalStrip>
        )}
      </Panel>
    </>
  );
}
