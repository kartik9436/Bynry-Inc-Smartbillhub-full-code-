// ── Trace ──────────────────────────────────────────────
// Change:   **THE NEW CONNECT REDESIGN OF 2026-09-28 — STEP 3 ABSORBS TWO WHOLE
//           STEPS.** `CR-150-BRC09`, PO verbatim: *"these steps are good - we
//           need 1 word - for every step"* and *"we dont want any information
//           to be reduced or lost - 8 steps → 5"*. Old step 4 **Map services**
//           and old step 5 **Work orders** fold into this one, **and their step
//           ids are gone** — so a field missed here is a field the product
//           loses. The field-by-field audit, both directions, is
//           `05-prototype/new-connect-redesign-2026-09-28/`
//           `step3-absorbed-field-audit.md`, and it is a deliverable of this
//           lane rather than a note.
//           Built from `step3-units.png`, `step3a-add-row.png` and
//           `step3b-add-work-order.png` **AS IMAGES** (B14 rule 42), with
//           spacing, sizes, the type scale and the kit from B14 (rule 44).
//           Earlier: Lane E wave 1 split this out of `NewConnectWizard.tsx`;
//           Lane H wave 2 (2026-09-16) made occupancy a column; Lane TEXT
//           (2026-09-28) deleted two sentences under B14 rule 33.
// Rules:    B14 rule 42 (the drawing is an IMAGE) · rule 44 (our UI standard
//           decides HOW it is built) · rule 43 (a piece of UI is a COMPONENT —
//           this screen writes no table of its own, it composes `TableArray`) ·
//           rule 20 (ONE table type) · rule 21 (Tailwind only; this file is on
//           `src/styles/route-b-migrated.txt`) · rule 31 (no database id is
//           ever the visible value of a field) · rule 32 (the description
//           budget) · rule 33 (a LABEL ≤ 3 words · a FACT ≤ 6 · an INSTRUCTION
//           ≤ 6 per sentence · RATIONALE **zero**) · rule 37 (every figure on
//           the drawing is an ILLUSTRATION) · BR-SHL-025 (a control that cannot
//           act is DISABLED WITH ITS REASON) · BR-MET-1179 (a common area is
//           optional everywhere, mandatory nowhere) · BR-MET-036 (`units` has
//           NO occupancy column — this is an instruction to the commit) ·
//           BR-MET-116 · BR-WRK-008 (*copy, never link*) · BR-WRK-013 (the job
//           that COMPLETES the connection is the TEMPLATE's flag) · BR-WRK-011
//           (version 0 is a draft and cannot be used) · BR-RAT-015 (sewer
//           carries no size class) · BR-AST-042 / OQ-1361 (fire's asset type is
//           the FIRE LINE — PO 2026-10-02) · DEF-MET-9037 (solar and battery
//           take no net meter — PO 2026-10-02) · TC-NCT-6 (sewer follows water) · hard rule 2 (no
//           money is multiplied in this client) · hard rule 8 (a unit refines a
//           premises by LABEL)
// Questions: ⛔ **`OQ-CUS-12770` — OPEN — IS WHY THERE IS NO `Qty` COLUMN.**
//           The drawing draws one, badged NEW. It asks whether a charge's
//           quantity is typed per line or counted, **and it multiplies a price
//           on a real invoice**; `CR-150-BRC09` §5 says in terms *"the Qty
//           column is drawn and not built until the PO rules"*. Nothing here
//           chooses a value for it. **A cell rendering a figure nothing reads
//           would be worse than its absence** — that is `DEF-CUS-6101`'s exact
//           shape, sixteen date pickers whose value the commit never sent.
// Tests:    NewConnectUnitsStep.dom.test.tsx · NewConnectWizard.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · NEITHER "DIALOG" IS A DIALOG, AND THE DRAWINGS SAY SO THEMSELVES
// ══════════════════════════════════════════════════════════════════════════
//
// `+ Add row` and `+ Add work order` each got their own drawn screen because
// the PO asked for one — *"you ahve to show screens what wil happen when user
// press Add row and add work order - screens are required"*. **Both drawings
// then rule out a dialog in their own words.** `step3a-add-row.png`: *"A row
// appears at the bottom of the unit you added it to, empty and ready to type.
// **Nothing opens on top of the screen.**"* `step3b-add-work-order.png`:
// *"Also in place, at the bottom of the table."* Decision log answer 13(e)
// settles it: *"neither opens a dialog: the row is added in place, at the
// bottom of the group you were in"*.
//
// ⚠ **A BRIEF CALLING THEM DIALOGS IS NOT THE SPECIFICATION — THE IMAGE IS**
// (B14 rule 42). Built in place.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · WHY OCCUPANCY IS ASKED HERE AND NOT ON THE LAST STEP
// ══════════════════════════════════════════════════════════════════════════
//
// PO, 2026-09-28: *"why dont you keep this with units itself"*. Occupancy was
// ONE four-way choice for the whole build, asked on the review step, over four
// explanatory lines that were themselves a rule 33 breach. It is a COLUMN here
// and a control in the common selection, and **the review step shows it and no
// longer asks it** (`DEF-CUS-7613`).
//
// **The case that could not be expressed before:** a six-unit build where unit
// 4 already has a tenant moving in and the other five do not.
//
// ⚠ **NONE OF THIS IS A COLUMN IN THE DATABASE.** `BR-MET-036` keeps
// `units.occupancy` deliberately absent. What this decides is WHICH UNITS GET
// AN ACCOUNT OPENED at commit — an instruction, not a field.
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · WHAT IS DRAWN AND IS DELIBERATELY NOT BUILT
// ══════════════════════════════════════════════════════════════════════════
//
// Each of these is stamped in `step3-absorbed-field-audit.md` §E as well, so a
// reader who has the drawing and not this file still finds it.
//
//   * **`Qty`** — `OQ-CUS-12770`, above.
//   * **The red ring round the new row** in both add-screens. Both frames are
//     titled *"The new row"* and the outline points at the row the prose is
//     about; nothing says the product draws it. `TableArray`'s own exception
//     E1 already records this for the kit.
//   * **Every explanatory paragraph on the drawing** — *"Occupancy options:
//     …"*, *"An extra work order not tied to a service becomes its own row…"*,
//     *"Filled in for you: …"*, *"Waiting on you: …"*, *"The search offers
//     published templates only…"*. Every one is RATIONALE, which B14 rule 33
//     gives **zero words on screen**, and rule 33 says rationale is REMOVED and
//     never shortened. *"Required before Continue. Rows stay editable."* is an
//     INSTRUCTION at six words a sentence and IS built.
//
// ══════════════════════════════════════════════════════════════════════════
// 4 · THE HELPERS BELOW MOVED HERE FROM `NewConnectServicesStep.tsx`
// ══════════════════════════════════════════════════════════════════════════
//
// They are the absorbed step's own arithmetic and they did not change. They
// moved because that file already imported `OCCUPANCY_CELL_WORDS` from this
// one, so importing them back would have made a cycle out of a fold. That file
// re-exports them for the life of its own step, which keeps every existing
// importer working and keeps ONE definition.
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { getLookupEntries, getTenantServices } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EditableTable } from "@/components/EditableTable";
import { CheckboxField, DatePickerField, SelectField, TextField } from "@/components/FormModal";
import { KPIStrip } from "@/components/KPIStrip";
import { Panel } from "@/components/Panel";
import { InlineLinkTo, RefusalStrip } from "@/components/Surfaces";
import {
  CellSelect,
  CellStatic,
  CellText,
  CellTick,
  TableArray,
} from "@/components/TableArray";
import type { TableArrayColumn, TableArrayGroup } from "@/components/TableArray";
import { Note } from "@/components/TextBits";
import { enabledServiceRows } from "@/features/metering/ServicesAvailableField";
import { UNIT_TYPES } from "@/features/metering/UnitsListPage";
import { WORK_ORDER_TEMPLATES_ROUTE } from "@/features/work/TemplatesPage";
import type { ProposedWorkOrder } from "@/features/work/workEndpoints";
import { listTemplates } from "@/features/work/workEndpoints";
import { useTenantPath } from "@/routing/tenantPath";

import type { NewConnectDraft, UnitServiceCell } from "./newConnectDraft";
import { occupancyOfUnit, unitServiceKey } from "./newConnectDraft";
import type {
  DraftUnit,
  OccupancyChoice,
  Translator,
  UnitPattern,
} from "./newConnectShared";
import { capacityIsOnTheUnit } from "./newConnectShared";
import { FieldGrid } from "./serviceRequestShared";

// ══════════════════════════════════════════════════════════════════════════
// THE COLUMN'S WORDS — SHORT ON PURPOSE (B14 rule 33)
// ══════════════════════════════════════════════════════════════════════════

/**
 * The occupancy choices as a TABLE CELL says them.
 *
 * ⚠ **THESE ARE DELIBERATELY NOT `OCCUPANCY_COPY`'s SENTENCES.** That list is
 * written for a radio, where each option carries a sub-line explaining it. A
 * radio has room for that; a cell repeated six, twenty-six or two hundred times
 * does not, and B14 rule 33 caps a fact at six words.
 *
 * ⚠ **THE TWO LISTS MUST NOT DRIFT, SO THE CODES ARE THE JOIN.** A code here
 * that `OCCUPANCY_CHOICES` does not hold is a typo that would render an empty
 * cell; `occupancyLabelCodes` below is exported so the test can assert the two
 * sets are equal rather than eyeballing them.
 */
export const OCCUPANCY_CELL_WORDS: readonly { code: OccupancyChoice; en: string }[] = [
  { code: "vacant_service_off", en: "Vacant" },
  { code: "vacant_base_only", en: "Vacant · base only" },
];

export function occupancyLabelCodes(): string[] {
  return OCCUPANCY_CELL_WORDS.map((row) => row.code);
}

/** A cell's word for one choice, translated. */
export function occupancyCellWord(code: OccupancyChoice, t: Translator): string {
  const row = OCCUPANCY_CELL_WORDS.find((entry) => entry.code === code);
  return t(`customers.newConnect.occupancy.cell.${code}`, {
    defaultValue: row?.en ?? code,
  });
}

// ══════════════════════════════════════════════════════════════════════════
// WHICH ASSET TYPES A SERVICE OFFERS — moved from the absorbed step, unchanged
// ══════════════════════════════════════════════════════════════════════════

/**
 * **THIS IS A JUDGMENT, NOT A RULING, AND IT IS WRITTEN DOWN SO IT CAN BE
 * OVERTURNED AGAINST A ROW.**
 *
 * There is no service → asset-type mapping anywhere in this repo. `asset_types`
 * carries a `category` (`meters` · `sub_meters` · `behind_the_meter`) and that
 * is the S49 tab partition, not a service filter. The map below is the decision
 * log's (2026-09-16), taken from the catalogue's own names.
 *
 * ⚠ **THE CODES ARE FILTERED AGAINST THE TENANT'S OWN `asset_types` LIST AND
 * ARE NEVER RENDERED FROM HERE.** This decides ORDER and OFFERING; the words a
 * clerk reads are the tenant's row names.
 *
 * ⊕ **FIRE TAKES THE FIRE LINE — PO ruling 2026-10-02 (`OQ-1361`, its
 * fire-line half CLOSED), verbatim:** *"A · A fire service gets a "fire line"
 * item with a size (2" to 10"), like a trash cart. The clerk picks the size on
 * New Connection."* Fire was absent from this map until that day, so a fire
 * row drew a dash and the build created nothing a bill could count. The sizes
 * are fire's own ladder from the tenant's `service_size_classes` (six seeded
 * diameters, tenant-editable; `OQ-1360` is the going-live customer's list and
 * is untouched). Each further fire line is one more row (`UnitServiceCell.more`).
 *
 * ⊖ **SOLAR AND BATTERY NO LONGER OFFER A NET METER — PO ruling 2026-10-02
 * (`DEF-MET-9037`):** *"we are not doing net metering right now … Capacity is
 * the panels or battery only."*
 *
 * ⛔ **STORM WATER IS ABSENT FOR A DIFFERENT REASON AND IT IS NOT A GAP.** It
 * is billed on area, not on a device (`DEF-2388`).
 *
 * ⊖ **THERMAL/HEAT IS ABSENT FOR STORM WATER'S REASON — `DEF-MET-9222`.** It
 * offered *Meter* and defaulted to it until 2026-10-03, three weeks after
 * `CR-080` (PO 2026-09-07: *"connected tonnage - it is capacity not
 * metering"*) stopped the commit fitting one. So step 5 counted a meter per
 * thermal unit that Create never made (the walk's S2: review **6**, created
 * **4**). The row keeps its SIZE — the tonnage — which is what is billed.
 */
export const SERVICE_ASSET_TYPES: Readonly<Record<string, readonly string[]>> = {
  electric: ["meter", "net_meter", "sub_meter", "battery", "ev_charger", "pv", "transformer", "generator"],
  water: ["meter", "sub_meter", "backflow"],
  gas: ["meter", "sub_meter"],
  // Commonly none — sewer is billed off the water it derives from (BR-RAT-015)
  // — but a utility that meters its own sewer exists, so the option is offered.
  sewer: ["meter", "sub_meter"],
  trash: ["container_cart"],
  solar: ["pv", "battery"],
  broadband: ["modem_cpe"],
  battery: ["battery"],
  fire: ["fire_line"],
};

/**
 * The USUAL asset type for a service — the one the row arrives on.
 *
 * ⚠ **OFFERING AND DEFAULTING ARE TWO DIFFERENT QUESTIONS, AND SEWER IS WHY.**
 * `SERVICE_ASSET_TYPES` offers sewer a meter, because a utility that meters its
 * own sewer exists. **Sewer has no entry here on purpose:** defaulting it would
 * put a meter on every sewer connection in the build — seven of them on a
 * six-unit development, each one a job somebody has to cancel.
 */
export const SERVICE_ASSET_DEFAULT: Readonly<Record<string, string>> = {
  electric: "meter",
  water: "meter",
  gas: "meter",
  trash: "container_cart",
  solar: "pv",
  broadband: "modem_cpe",
  battery: "battery",
  fire: "fire_line",
};

// ══════════════════════════════════════════════════════════════════════════
// THE ROWS — moved from the absorbed step, unchanged
// ══════════════════════════════════════════════════════════════════════════

export interface GridRow {
  unit: DraftUnit;
  service: string;
  taken: boolean;
  cell: UnitServiceCell;
  key: string;
}

/**
 * Every row the table shows: one per unit × service.
 *
 * ⚠ **THE UNION WITH EXPLICIT `taken: true` IS WHAT KEEPS THE AVAILABILITY
 * REFUSAL CAPABLE OF FIRING.** Rows derived from `premiseServices` alone can
 * never name a service the street does not have, which would make the refusal
 * structurally incapable of failing — CLAUDE.md law 7's second shape.
 *
 * ⚠ **THE EXPLICIT SET IS READ OUT OF THE GRID'S OWN KEYS, NOT OUT OF A LIST
 * OF SERVICES** (PO ruling 2026-09-21). A key is `${label}\u001F${service}` and
 * U+001F was chosen precisely because no unit label can hold one, so splitting
 * the key back is exact. **A twelfth service needs no change here at all.**
 */
/**
 * ⊕ `DEF-CUS-10046` — *Creates 1 unit* / *Creates 5 units*: the DWELLINGS the
 * From/To range makes (the common area is its own tick box), or nothing while
 * both boxes are empty.
 */
export function rangeCountLine(
  pattern: NewConnectDraft["pattern"],
  units: readonly DraftUnit[],
  t: Translator,
): string | undefined {
  if (pattern.from.trim() === "" && pattern.to.trim() === "") return undefined;
  const count = units.filter((unit) => !unit.isCommonArea).length;
  return t("customers.newConnect.units.creates", { count });
}

export function gridRows(draft: NewConnectDraft, units: readonly DraftUnit[]): GridRow[] {
  const rows: GridRow[] = [];
  for (const unit of units) {
    const prefix = unitServiceKey(unit.label, "");
    const explicit = Object.keys(draft.unitServiceGrid).filter(
      (key) => key.startsWith(prefix) && draft.unitServiceGrid[key]?.taken === true,
    );
    const services = [...draft.premiseServices];
    for (const key of explicit) {
      const service = key.slice(prefix.length);
      if (service !== "" && !services.includes(service)) {
        services.push(service);
      }
    }
    for (const service of services) {
      const key = unitServiceKey(unit.label, service);
      const cell = draft.unitServiceGrid[key] ?? {};
      rows.push({ unit, service, key, cell, taken: cell.taken !== false });
    }
  }
  return rows;
}

/** What `service_size_classes` offers for ONE service: the rows tagged with it,
 *  plus the untagged ones, which CR-065 rules list everywhere. */
export function sizesForService(
  entries: readonly { code: string; name: string; service?: unknown }[],
  service: string,
): { code: string; name: string }[] {
  return entries
    .filter((row) => {
      const tag = row.service as { code?: string } | null | undefined;
      return tag == null || tag.code === service;
    })
    .map((row) => ({ code: row.code, name: row.name }));
}

/** The first number a size's NAME carries — `2"` → 2, `1½"` → 1.5, `3/4"` →
 *  0.75, `1,000+ CFH` → 1000, `10 kW` → 10 — or `null` for a name with none
 *  (*Apartment building*). */
export function sizeMagnitude(name: string): number | null {
  const m = /(\d[\d,]*)(?:\s*(½|¼|¾)|\s*[- ]?\s*(\d+)\/(\d+)|\/(\d+)|\.(\d+))?/.exec(name);
  if (m === null) return null;
  const whole = Number(m[1].replace(/,/g, ""));
  if (m[2] !== undefined) return whole + ({ "½": 0.5, "¼": 0.25, "¾": 0.75 } as const)[m[2] as "½"];
  if (m[3] !== undefined && m[4] !== undefined) return whole + Number(m[3]) / Number(m[4]);
  if (m[5] !== undefined) return whole / Number(m[5]);
  if (m[6] !== undefined) return Number(`${whole}.${m[6]}`);
  return whole;
}

/** ⊕ **`DEF-CUS-9220` — THE SIZE LIST IN SIZE ORDER, FOR THE EYE ONLY.** The
 *  utility's rows arrive sorted by NAME, so a clerk read *Fire line 10", 12",
 *  2", 4"…* and *Water 3", 3/4", 4"* (the New Connection end-to-end walk,
 *  2026-10-02). This orders what the dropdown DRAWS by the number each name
 *  carries, names without one last in their served order. ⚠ **IT DOES NOT
 *  CHANGE A ROW'S DEFAULT** — `resolvedSize` still takes the first SERVED row,
 *  because which size a row assumes when nobody picks one reaches a bill, and
 *  moving it is not a display fix. */
export function bySize<T extends { name: string }>(rows: readonly T[]): T[] {
  return rows
    .map((row, at) => ({ row, at, n: sizeMagnitude(row.name) }))
    .sort((a, b) =>
      a.n === null && b.n === null
        ? a.at - b.at
        : a.n === null
          ? 1
          : b.n === null
            ? -1
            : a.n - b.n || a.at - b.at,
    )
    .map((one) => one.row);
}

/** What `asset_types` offers for ONE service, in the judgment's order, keeping
 *  only codes the tenant actually has. */
export function assetTypesForService(
  entries: readonly { code: string; name: string }[],
  service: string,
): { code: string; name: string }[] {
  const offered = SERVICE_ASSET_TYPES[service] ?? [];
  const have = new Map(entries.map((row) => [row.code, row.name]));
  return offered.filter((code) => have.has(code)).map((code) => ({ code, name: have.get(code) ?? code }));
}

/** The device a row carries: the clerk's own pick, else the service's usual
 *  device when the tenant has it, else none. One function so the step, the
 *  tiles and the wizard's Continue check cannot disagree about a row. */
export function resolvedAssetTypeOf(
  row: GridRow,
  assetTypeRows: readonly { code: string; name: string }[],
): string {
  if (row.cell.assetType !== undefined) {
    return row.cell.assetType;
  }
  const usual = SERVICE_ASSET_DEFAULT[row.service] ?? "";
  return assetTypesForService(assetTypeRows, row.service).some((type) => type.code === usual)
    ? usual
    : "";
}

/**
 * ⊕ **`DEF-CUS-9267` — A SIZE IS NEVER ASSUMED (hard-won law 3, defaults fail
 * closed).** Until 2026-10-03 a row with no size picked showed, pinned and sent
 * the FIRST size the tenant's list served, so every storm-water unit silently
 * took *Apartment building* (6 ERU) — the list's first row by name — and every
 * cart, fire line, tonnage and meter took whatever sorted first. The size box
 * now starts empty and Continue names each row still missing one.
 *
 * A row needs a size when its service HAS sizes and the size is the unit's own
 * (storm water, thermal), or the service has no device to pick, or a device is
 * on the row. A row whose clerk chose *None* for the device has nothing to size.
 * A further piece (`more`) with no size is missing too. Returns the rows in the
 * table's order; how they are SHOWN is the caller's.
 */
export function rowsMissingSize(
  draft: NewConnectDraft,
  units: readonly DraftUnit[],
  sizeRows: readonly { code: string; name: string; service?: unknown }[],
  assetTypeRows: readonly { code: string; name: string }[],
): GridRow[] {
  return gridRows(draft, units).filter((row) => {
    if (!row.taken || sizesForService(sizeRows, row.service).length === 0) {
      return false;
    }
    const needsOne =
      capacityIsOnTheUnit(row.service) ||
      assetTypesForService(assetTypeRows, row.service).length === 0 ||
      resolvedAssetTypeOf(row, assetTypeRows) !== "";
    if (!needsOne) {
      return false;
    }
    return (
      (row.cell.sizeClass ?? "").trim() === "" ||
      (row.cell.more ?? []).some((size) => size.trim() === "")
    );
  });
}

/** The work-order template that fits ONE service. Matched on the template's OWN
 *  service, never on a name. */
export function orderForService(
  proposed: readonly ProposedWorkOrder[],
  service: string,
): ProposedWorkOrder | null {
  // `CR-168-BRC10` P3.42 — a Work rule on *a new connection is built* that
  // proposes a job for this service decides what the row ARRIVES on; the
  // clerk may still change it. Otherwise the first, as before.
  return (
    proposed.find((order) => order.service?.code === service && order.preselected_by) ??
    proposed.find((order) => order.service?.code === service) ??
    null
  );
}

/**
 * Every job a clerk may put on ONE row.
 *
 * ⚠ **THE WHOLE PROPOSAL, NOT THE ONE THAT MATCHES THE SERVICE**
 * (`DEF-CUS-5481`, PO 2026-09-16). `orderForService` decides what the row
 * ARRIVES on; this decides what the clerk may change it to.
 *
 * ⚠ **DEDUPED BY `template_id`, IN THE PROPOSAL'S OWN ORDER.** One template can
 * be proposed for two services, and the same template twice is two identical
 * words a clerk has to choose between.
 */
export function workOrderOptions(
  proposed: readonly ProposedWorkOrder[],
  /** P3.42 — how an option a Work rule proposed says so, e.g. *By rule: X*. */
  byRule?: (name: string) => string,
): { value: string; label: string }[] {
  const seen = new Set<string>();
  const out: { value: string; label: string }[] = [];
  for (const order of proposed) {
    if (seen.has(order.template_id)) {
      continue;
    }
    seen.add(order.template_id);
    // B14 rule 31: the id is the option's VALUE and the name is what is read.
    out.push({
      value: order.template_id,
      label:
        order.preselected_by && byRule ? `${order.name} · ${byRule(order.preselected_by.name)}` : order.name,
    });
  }
  return out;
}

/**
 * The counts behind the four tiles — computed from the rows, never drawn.
 *
 * ⚠ **`workOrders` COUNTS DISTINCT TEMPLATES AND NOT ROWS, BECAUSE THAT IS WHAT
 * THE COMMIT WILL ACTUALLY WRITE.** `commit_connection` raises one order per
 * entry in the payload's `work_orders` list, and that entry carries **no unit**
 * — so eighteen rows naming one template can only ever become one order.
 * Printing 18 here would promise a clerk orders that are never written. Whether
 * a build should raise one order PER UNIT is `OQ-MET-12382`.
 *
 * ⚠ **SUPERSEDED FOR THE COMMIT ON 2026-10-03 (`DEF-MET-9223`)**: the commit
 * now raises each job on the unit its row names (`commitWorkOrdersOf`), and
 * step 5 counts that list. This tile figure is not drawn on step 3 today.
 */
export function gridCounts(
  rows: readonly GridRow[],
  meterTypeCodes: ReadonlySet<string>,
  resolvedAssetType: (row: GridRow) => string,
  resolvedOrderId: (row: GridRow) => string,
): { servicePoints: number; meters: number; workOrders: number } {
  const taken = rows.filter((row) => row.taken);
  const orders = new Set<string>();
  let meters = 0;
  for (const row of taken) {
    if (meterTypeCodes.has(resolvedAssetType(row))) {
      meters += 1;
    }
    const order = resolvedOrderId(row);
    if (order !== "") {
      orders.add(order);
    }
  }
  return { servicePoints: taken.length, meters, workOrders: orders.size };
}

/**
 * ⊕ **`CR-164-BRC10` item 15 — THE UNIT TYPES A DWELLING MAY TAKE**, the
 * utility's own active rows (`/lookups/unit_types`, `BR-MET-084`) by name.
 * `common_area` is not offered: a common area is the *Include a common-area
 * unit* tick, not a type a dwelling can be given (`BR-MET-101`).
 */
export function unitTypeChoices(
  rows: readonly { code: string; name: string; active?: boolean }[],
  t: Translator,
): { value: string; label: string }[] {
  const served = rows.filter((row) => row.active !== false && row.code !== "common_area");
  if (served.length > 0) {
    return served.map((row) => ({ value: row.code, label: row.name }));
  }
  return UNIT_TYPES.filter((code) => code !== "common_area").map((code) => ({
    value: code,
    label: t(`metering.units.type.${code}`, { defaultValue: code }),
  }));
}

/**
 * ⊕ **`CR-164-BRC10` items 21, 29 — METERS AND BEHIND-THE-METER DEVICES
 * COUNTED APART.** Step 5's *At a glance* drew one *Meters* tile over every
 * device, so a solar build's panels and batteries read as meters. The tenant's
 * own `asset_types.category` (`meters` · `sub_meters` · `behind_the_meter`)
 * decides, with each row's type resolved exactly as this step resolves it —
 * the clerk's pick, else the service's usual device where the tenant has it.
 * Each extra piece on a row (`more`) is one more device of the same type.
 */
export function equipmentCounts(
  draft: NewConnectDraft,
  units: readonly DraftUnit[],
  assetTypeRows: readonly { code: string; name: string; category?: string }[],
): { meters: number; subMeters: number; behindTheMeter: number; other: number } {
  const category = new Map(assetTypeRows.map((row) => [row.code, row.category ?? ""]));
  const out = { meters: 0, subMeters: 0, behindTheMeter: 0, other: 0 };
  for (const row of gridRows(draft, units)) {
    if (!row.taken) continue;
    let type = row.cell.assetType;
    if (type === undefined) {
      const usual = SERVICE_ASSET_DEFAULT[row.service] ?? "";
      type = assetTypesForService(assetTypeRows, row.service).some((one) => one.code === usual)
        ? usual
        : "";
    }
    // ⊕ `DEF-MET-9222` — a type the service no longer offers (a thermal
    // `meter` parked before the fix) is not a device Create will make.
    if (type === "" || !(SERVICE_ASSET_TYPES[row.service] ?? []).includes(type)) continue;
    const pieces = 1 + (row.cell.more?.length ?? 0);
    const kind = category.get(type);
    if (kind === "meters") out.meters += pieces;
    else if (kind === "sub_meters") out.subMeters += pieces;
    else if (kind === "behind_the_meter") out.behindTheMeter += pieces;
    else out.other += pieces;
  }
  return out;
}

// ══════════════════════════════════════════════════════════════════════════
// ⊕ `DEF-CUS-9840` — A SERVICE ROW'S PIECES, COUNTED AND SUMMED
// ══════════════════════════════════════════════════════════════════════════
//
// PO ruling (a), 2026-10-06: ONE work order for a unit's service, ONE asset per
// panel, the bill on the SUM of installed kW (`BR-RAT-090`). So the service row
// says how many pieces it holds and — for a service that SUMS — their total:
// *Solar · 3 panels · 21 kW*. A COUNTED service (carts, fire lines) shows the
// count only, which is all its bill reads.

/** One size-class row as the lookup serves it, `capacity` included. */
export interface SizeRow {
  code: string;
  name: string;
  service?: unknown;
  /** The ratified figure for this size on its service, as a string — `null`
   *  for a counted or banded service, or a code the ladder does not hold. */
  capacity?: string | null;
  capacity_uom?: string | null;
}

/** Every piece on a service row, in order: the row's own size, then `more`. */
export function pieceSizes(cell: UnitServiceCell): string[] {
  return [cell.sizeClass ?? "", ...(cell.more ?? [])].map((size) => size.trim());
}

/** A quantity string as ten-thousandths — never a float (hard rule 3's figure
 *  travels as text; the ladder never carries more than 4 places). */
function tenThousandths(value: string): number | null {
  const m = /^(\d+)(?:\.(\d{1,4}))?$/.exec(value.trim());
  if (m === null) return null;
  return Number(m[1]) * 10000 + Number((m[2] ?? "").padEnd(4, "0"));
}

/**
 * **How many pieces the row holds, and their summed capacity when the service
 * sums.** `total` is `null` — and the screen sums NOTHING — when any piece has
 * no size, any size carries no capacity, or two sizes disagree about the unit:
 * a partial sum is the plausible wrong number `BR-RAT-090` refuses to bill.
 * The figures are the tenant's size-class rows (`capacity` on the lookup),
 * never a kW typed here per size.
 */
export function piecesTotal(
  cell: UnitServiceCell,
  sizes: readonly SizeRow[],
): { count: number; total: string | null; uom: string | null } {
  const pieces = pieceSizes(cell);
  const byCode = new Map(sizes.map((row) => [row.code, row]));
  let sum = 0;
  let uom: string | null = null;
  for (const code of pieces) {
    const row = byCode.get(code);
    const part = row?.capacity == null ? null : tenThousandths(row.capacity);
    const unit = row?.capacity_uom ?? null;
    if (part === null || unit === null || (uom !== null && unit !== uom)) {
      return { count: pieces.length, total: null, uom: null };
    }
    uom = unit;
    sum += part;
  }
  const whole = Math.floor(sum / 10000);
  const frac = String(sum % 10000).padStart(4, "0").replace(/0+$/, "");
  return { count: pieces.length, total: frac === "" ? String(whole) : `${whole}.${frac}`, uom };
}

/** One asset Create will make for a sized piece — Review's list. */
export interface PlannedAsset {
  unit: string;
  service: string;
  type: string;
  size: string;
}

/**
 * **Every piece of sized equipment Create will make, one entry per asset** —
 * read off `commitUnitServicesOf`'s own payload so Review cannot list an
 * asset the commit does not send (`DEF-MET-5428`'s shape).
 */
export function plannedAssets(
  unitServices: readonly {
    unit_label: string;
    service: string;
    equipment: readonly { type: string; size_class: string; count: number }[];
  }[],
): PlannedAsset[] {
  const out: PlannedAsset[] = [];
  for (const row of unitServices) {
    for (const piece of row.equipment) {
      for (let n = 0; n < piece.count; n += 1) {
        out.push({ unit: row.unit_label, service: row.service, type: piece.type, size: piece.size_class });
      }
    }
  }
  return out;
}

// ══════════════════════════════════════════════════════════════════════════
// WHERE A BUILD-LEVEL WORK ORDER SITS — `Applies to`
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE SCOPE IS A SCREEN FACT AND NOT A COMMIT FACT, AND SAYING SO IS THE
// POINT.** `commitPlanOf` sends `{template_id, template_version}` per order and
// **nothing else** — no unit, no service point. So `Applies to` decides WHICH
// GROUP THE ROW SITS IN and nothing more, exactly as the drawing describes it:
// *"Pick a unit and the row moves into that unit's group."* Writing a unit into
// the payload from here would be `DEF-CUS-6101`'s shape — a value the clerk
// types that the commit never reads.
//
// It is carried on the order's own `scope` string, which the commit also does
// not send, so no second field is invented for it.
export const WHOLE_BUILD = "build";

/** The group key a build-level order sits under, from its `scope`. */
export function orderGroupKey(scope: string): string {
  return scope.startsWith("unit:") ? `unit:${scope.slice(5)}` : WHOLE_BUILD;
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 3 · THE UNITS
// ══════════════════════════════════════════════════════════════════════════

/** One row of the table, which is now three different things. */
type Row =
  | { kind: "service"; id: string; unit: DraftUnit; grid: GridRow }
  /** `+ Add row` — empty and ready to type, held in this component until a
   *  service is chosen, because until then it has no key to be stored under. */
  | { kind: "pending"; id: string; unit: DraftUnit }
  /** `+ Add work order` — an order that belongs to the build. */
  | { kind: "order"; id: string; order: ProposedWorkOrder }
  /** One MORE piece of a service row's device — a second cart, a 2" fire line
   *  beside a 6" one (`OQ-1361`). It sizes itself and nothing else: the
   *  device, the job and the occupancy are the service row's. `index` is its
   *  place in `cell.more`. */
  | { kind: "piece"; id: string; unit: DraftUnit; grid: GridRow; index: number };

export function UnitsStep(props: {
  draft: NewConnectDraft;
  units: readonly DraftUnit[];
  /**
   * **WHAT THE PICKED ADDRESS ALREADY HOLDS — `DEF-MET-6111` LAYER 1.**
   *
   * ⚠ **WIRED, NOT OPTIONAL-AND-UNPASSED (hard-won law 2).** A build on a NEW
   * address passes `[]`, which is a different fact from *nobody asked*.
   */
  labelsAlreadyHere: readonly string[];
  /** A unit taking a service the street does not have. Computed by the wizard,
   *  which also refuses Continue on it — one answer, not two. */
  breaches: { unit: string; service: string }[];
  /** A unit taking sewer without water (TC-NCT-6). Same single answer. */
  sewerGaps: string[];
  /** The jobs this build needs — the read, minus removals, plus additions. */
  proposed: readonly ProposedWorkOrder[];
  proposalsUnavailable: boolean;
  onPatch: (next: Partial<NewConnectDraft>) => void;
  client: ApiClient;
  t: Translator;
  dateFormat: Parameters<typeof DatePickerField>[0]["dateFormat"];
}) {
  const tenantPath = useTenantPath();
  const set = (patch: Partial<UnitPattern>) =>
    props.onPatch({ pattern: { ...props.draft.pattern, ...patch } });

  // ── THE TENANT'S OWN CATALOGUES ──────────────────────────────────────────
  // ⚠ **`queryKeys.tenantServices` — THE SHARED KEY, NOT A NEW-CONNECT ONE.**
  // `GET /settings/services` is the one place that answers which services a
  // tenant sells; four screens read it through this key and cannot drift.
  const tenantServicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(props.client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
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
  // ⊕ `CR-164-BRC10` item 15 — the utility's own unit types (`BR-MET-084`).
  const unitTypesQuery = useQuery({
    queryKey: ["lookups", "unit_types", "new-connect"],
    queryFn: () => getLookupEntries("unit_types", { per: 200 }, props.client),
    retry: false,
  });
  const unitTypeOptions = unitTypeChoices(
    (unitTypesQuery.data?.results ?? []) as { code: string; name: string; active?: boolean }[],
    props.t,
  );
  const setUnitType = (label: string, unitType: string) =>
    props.onPatch({ unitTypes: { ...(props.draft.unitTypes ?? {}), [label]: unitType } });
  // ⚠ **A DRAFT TEMPLATE IS NOT OFFERED AND NEITHER IS AN INACTIVE ONE**
  // (`BR-WRK-011` — version 0 is a DRAFT and is not a version), so adding one
  // would stamp `template_version: 0` and `BR-WRK-008`'s *copy, never link*
  // would have nothing to name.
  const templatesQuery = useQuery({
    queryKey: ["connection-wizard-templates"],
    queryFn: () => listTemplates({ per: 200 }, props.client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const assetTypeRows = useMemo(
    () => (assetTypesQuery.data?.results ?? []) as { code: string; name: string; category?: string }[],
    [assetTypesQuery.data],
  );
  const sizeRows = useMemo(() => (sizesQuery.data?.results ?? []) as SizeRow[], [sizesQuery.data]);
  /** Which asset types ARE meters, from the tenant's own `category`. The drawn
   *  *"one per service point"* is an illustration; this is the real answer. */
  const meterTypeCodes = useMemo(
    () => new Set(assetTypeRows.filter((row) => row.category === "meters").map((row) => row.code)),
    [assetTypeRows],
  );

  const serviceName = (code: string) => props.t(`rating.service.${code}`, { defaultValue: code });
  const grid = useMemo(() => gridRows(props.draft, props.units), [props.draft, props.units]);
  const orders = useMemo(
    () => workOrderOptions(props.proposed, (name) => props.t("work.fieldVisitOrders.byRule", { name })),
    // `props.t` is stable per language; the proposal is what changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [props.proposed],
  );
  const assetTypeOptions = (service: string) => assetTypesForService(assetTypeRows, service);
  const sizeOptions = (service: string) => sizesForService(sizeRows, service);

  /** Every column's DEFAULT, resolved in one place so the screen, the tiles and
   *  the commit cannot disagree about the same row. */
  const resolvedAssetType = (row: GridRow): string => resolvedAssetTypeOf(row, assetTypeRows);
  // ⊕ `DEF-CUS-9267` — NO FIRST-ROW FALLBACK. The size is the clerk's pick or
  // nothing; Continue names a row still missing one (`rowsMissingSize`).
  const resolvedSize = (row: GridRow): string => row.cell.sizeClass ?? "";
  const resolvedOrderId = (row: GridRow): string =>
    row.cell.workOrderTemplateId ?? orderForService(props.proposed, row.service)?.template_id ?? "";

  const counts = gridCounts(grid, meterTypeCodes, resolvedAssetType, resolvedOrderId);

  // ── `DEF-MET-6119` · WHAT THE ROW SHOWS IS WHAT THE COMMIT SENDS ─────────
  // A row arrives showing its service's usual DEVICE, resolved HERE from
  // catalogues only this step loads. `commitPlanOf` is a pure function over
  // the draft and cannot resolve it, so the shown device is pinned into the
  // cell once the catalogues have arrived — a clerk's own choice is never
  // touched (only an ABSENT member is filled), and a meter is never pinned
  // because a meter travels on `meters`.
  // ⊖ **`DEF-CUS-9267` — THE SIZE IS NO LONGER PINNED, BECAUSE IT IS NO LONGER
  // DEFAULTED.** It pinned the first served size, which put *Apartment
  // building* (6 ERU) on every storm-water unit nobody looked at.
  const catalogueReady = assetTypesQuery.data !== undefined && sizesQuery.data !== undefined;
  useEffect(() => {
    if (!catalogueReady) {
      return;
    }
    const pinned: Record<string, UnitServiceCell> = {};
    for (const row of grid) {
      if (!row.taken || row.cell.assetType !== undefined || capacityIsOnTheUnit(row.service)) {
        continue;
      }
      const type = resolvedAssetType(row);
      if (type === "" || meterTypeCodes.has(type)) {
        continue;
      }
      pinned[row.key] = { ...row.cell, assetType: type };
    }
    if (Object.keys(pinned).length > 0) {
      props.onPatch({ unitServiceGrid: { ...props.draft.unitServiceGrid, ...pinned } });
    }
    // The resolvers close over the catalogues already listed; re-running on
    // their identity would loop on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalogueReady, grid, meterTypeCodes]);

  const patchCell = (key: string, patch: Partial<UnitServiceCell>) =>
    props.onPatch({
      unitServiceGrid: {
        ...props.draft.unitServiceGrid,
        [key]: { ...(props.draft.unitServiceGrid[key] ?? {}), ...patch },
      },
    });
  /** Occupancy is a UNIT fact, so editing it on ONE row moves the unit — the
   *  same map the common selection writes, and never a second answer. */
  const setOccupancy = (label: string, choice: OccupancyChoice) =>
    props.onPatch({ unitOccupancy: { ...props.draft.unitOccupancy, [label]: choice } });

  // ── THE COMMON SELECTION ─────────────────────────────────────────────────
  // ⚠ **IT IS A FORM, NOT A SECOND SOURCE OF TRUTH.** What it holds lives here
  // until *Apply to all* is pressed; the rows are the answer afterwards, and
  // they stay editable — PO, of exactly that: *"this is correct"*.
  const [commonCells, setCommonCells] = useState<Record<string, UnitServiceCell>>({});
  const [applied, setApplied] = useState(false);
  const commonRows: GridRow[] = props.draft.premiseServices.map((service) => ({
    unit: props.units[0] ?? { label: "", isCommonArea: false },
    service,
    key: service,
    cell: commonCells[service] ?? {},
    taken: true,
  }));
  const patchCommon = (service: string, patch: Partial<UnitServiceCell>) =>
    setCommonCells((current) => ({
      ...current,
      [service]: { ...(current[service] ?? {}), ...patch },
    }));

  /** *Apply to all* — the drawn primary act. It writes the common selection
   *  onto every unit, and every cell stays editable afterwards. */
  const applyToAll = () => {
    const next = { ...props.draft.unitServiceGrid };
    for (const unit of props.units) {
      for (const row of commonRows) {
        next[unitServiceKey(unit.label, row.service)] = {
          ...(next[unitServiceKey(unit.label, row.service)] ?? {}),
          taken: true,
          assetType: resolvedAssetType(row),
          // An unpicked common size leaves each row's own pick standing.
          ...(resolvedSize(row) === "" ? {} : { sizeClass: resolvedSize(row) }),
          workOrderTemplateId: resolvedOrderId(row),
        };
      }
    }
    const common = (props.draft.commonUnitType ?? "").trim();
    props.onPatch({
      unitServiceGrid: next,
      ...(common === ""
        ? {}
        : {
            unitTypes: {
              ...(props.draft.unitTypes ?? {}),
              ...Object.fromEntries(
                props.units.filter((unit) => !unit.isCommonArea).map((unit) => [unit.label, common]),
              ),
            },
          }),
    });
    setApplied(true);
  };
  /**
   * ⊕ **`DEF-CUS-9199` — *Press Apply to all first* ONLY WHILE THE ROWS ARE
   * EMPTY.** It was keyed on a flag that lives in this component, so walking
   * Back and Next brought it back over rows already filled. The rows are the
   * answer: once any taken row carries a device, a size or a job, there is
   * nothing left to apply first.
   */
  const rowsEmpty = !grid.some(
    (row) =>
      row.taken &&
      (row.cell.assetType !== undefined ||
        row.cell.sizeClass !== undefined ||
        row.cell.workOrderTemplateId !== undefined),
  );

  // ── THE THREE ROW KINDS ──────────────────────────────────────────────────
  const [pending, setPending] = useState<{ id: string; label: string }[]>([]);
  const [lastUnit, setLastUnit] = useState("");
  /** Folded by default except the first, which is how the drawing rests. Every
   *  row is one press away, so nothing is unreachable. */
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const isOpen = (key: string, first: boolean) => openGroups[key] ?? first;

  const buildOrders = props.draft.addedWorkOrders;
  const rows: Row[] = [];
  for (const unit of props.units) {
    const mine = grid.filter((candidate) => candidate.unit.label === unit.label);
    for (const row of mine) {
      rows.push({ kind: "service", id: row.key, unit, grid: row });
      if (row.taken) {
        (row.cell.more ?? []).forEach((_size, index) => {
          rows.push({ kind: "piece", id: `${row.key}\u001Fpiece:${index}`, unit, grid: row, index });
        });
      }
    }
    const typed = pending.filter((candidate) => candidate.label === unit.label);
    for (const row of typed) {
      rows.push({ kind: "pending", id: row.id, unit });
    }
    // ⚠ **A UNIT WITH NO SERVICE YET STILL APPEARS, AS ONE EMPTY ROW.**
    // `EditableTable` draws its groups only while the row list is non-empty,
    // so without this a build whose services are not yet chosen would render
    // the empty state and **every unit would silently vanish** — taking the
    // duplicate-label refusal (`DEF-MET-6111`) with it. An absence is
    // invisible to every check this repo has (`DEF-CUS-3653`), which is why
    // the row is made rather than the case left to be noticed.
    if (mine.length === 0 && typed.length === 0) {
      rows.push({ kind: "pending", id: `pending:auto:${unit.label}`, unit });
    }
    for (const order of buildOrders.filter(
      (candidate) => orderGroupKey(candidate.scope) === `unit:${unit.label}`,
    )) {
      rows.push({ kind: "order", id: `order:${order.template_id}`, order });
    }
  }
  for (const order of buildOrders.filter((candidate) => orderGroupKey(candidate.scope) === WHOLE_BUILD)) {
    rows.push({ kind: "order", id: `order:${order.template_id}`, order });
  }

  const groups: TableArrayGroup[] = props.units.map((unit, index) => {
    const key = `unit:${unit.label}`;
    const kind = unit.isCommonArea
      ? props.t("customers.newConnect.step4.common", { defaultValue: "Common area" })
      : props.t("customers.newConnect.step4.dwelling", { defaultValue: "Dwelling" });
    const breach = props.breaches.find((one) => one.unit === unit.label);
    const sewerGap = props.sewerGaps.includes(unit.label);
    return {
      key,
      heading: `${unit.label} · ${kind}`,
      summary: props.t("customers.newConnect.units.points", {
        defaultValue: "{{count}} service points",
        count: grid.filter((row) => row.unit.label === unit.label && row.taken).length,
      }),
      // The drawing puts BOTH refusals under the unit's own heading.
      error: breach
        ? props.t("customers.newConnect.step5.breach", {
            defaultValue: "{{unit}} takes {{service}}. This address does not.",
            unit: breach.unit,
            service: serviceName(breach.service),
          })
        : sewerGap
          ? props.t("customers.newConnect.step5.sewerNeedsWater", {
              defaultValue: "{{unit}} takes sewer, not water. Sewer follows water.",
              unit: unit.label,
            })
          : props.labelsAlreadyHere.includes(unit.label)
            ? props.t("customers.newConnect.step4.labelTakenCell", {
                defaultValue: "Already exists here.",
              })
            : undefined,
      collapsed: !isOpen(key, index === 0),
      onToggle: () => setOpenGroups((current) => ({ ...current, [key]: !isOpen(key, index === 0) })),
    };
  });
  if (buildOrders.some((order) => orderGroupKey(order.scope) === WHOLE_BUILD)) {
    groups.push({
      key: WHOLE_BUILD,
      heading: props.t("customers.newConnect.units.wholeBuild", { defaultValue: "Whole build" }),
    });
  }

  /** Where `+ Add row` puts its row: the group the clerk was last in, which is
   *  the drawing's *"the unit you added it to"*. */
  const targetUnit = props.units.find((unit) => unit.label === lastUnit) ?? props.units[0];

  /** ⊕ `DEF-CUS-9840` — a service row with pieces under it, waiting on the
   *  clerk's yes before it goes with all of them. */
  const [confirmRemove, setConfirmRemove] = useState<GridRow | null>(null);
  const removeRow = (row: Row) => {
    if (row.kind === "service") {
      // ✕ on the service row takes its pieces with it, so it asks first; ✕ on
      // a piece (below) removes that piece only.
      if ((row.grid.cell.more ?? []).length > 0) {
        setConfirmRemove(row.grid);
        return;
      }
      patchCell(row.grid.key, { taken: false });
      return;
    }
    if (row.kind === "piece") {
      patchCell(row.grid.key, {
        more: (row.grid.cell.more ?? []).filter((_size, index) => index !== row.index),
      });
      return;
    }
    if (row.kind === "pending") {
      setPending((current) => current.filter((one) => one.id !== row.id));
      return;
    }
    // ⚠ A REMOVAL CLEARS THE ADDITION TOO, or removing a job the clerk added
    // leaves it in `addedWorkOrders` and the two lists disagree.
    props.onPatch({
      removedWorkOrderTemplateIds: [
        ...props.draft.removedWorkOrderTemplateIds,
        row.order.template_id,
      ],
      addedWorkOrders: props.draft.addedWorkOrders.filter(
        (one) => one.template_id !== row.order.template_id,
      ),
    });
  };

  /** `Applies to` — whole build, one unit, or one service point. */
  const appliesToOptions = [
    { value: WHOLE_BUILD, label: props.t("customers.newConnect.units.wholeBuild", { defaultValue: "Whole build" }) },
    ...props.units.map((unit) => ({ value: `unit:${unit.label}`, label: unit.label })),
    ...grid
      .filter((row) => row.taken)
      .map((row) => ({
        value: `sp:${row.unit.label}\u001F${row.service}`,
        label: `${row.unit.label} · ${serviceName(row.service)}`,
      })),
  ];
  const setAppliesTo = (templateId: string, scope: string) =>
    props.onPatch({
      addedWorkOrders: props.draft.addedWorkOrders.map((one) =>
        one.template_id === templateId ? { ...one, scope } : one,
      ),
    });

  const dash = <span aria-hidden="true">—</span>;

  // ── ⊕ `DEF-CUS-9840` · THE PIECES' WORDS ───────────────────────────────
  // The noun is keyed by the DEVICE's own code (`pv`, `container_cart`, …), the
  // `rating.service.<code>` posture: a device with no word of its own reads the
  // generic *piece*, so a new device type needs no edit here.
  /** *Panel 2* — the sub-row's own name. */
  const pieceLabel = (device: string, n: number) =>
    props.t(`customers.newConnect.units.piece.${device}`, {
      n,
      defaultValue: props.t("customers.newConnect.units.piece.any", { n, defaultValue: `Piece ${n}` }),
    });
  /** *3 panels · 21 kW* — the service row's count and, when it sums, total. */
  const piecesSummary = (row: GridRow): string => {
    const { count, total, uom } = piecesTotal(row.cell, sizeRows);
    const device = resolvedAssetType(row);
    const noun = props.t(`customers.newConnect.units.pieces.${device}`, {
      count,
      defaultValue: props.t("customers.newConnect.units.pieces.any", {
        count,
        defaultValue: `${count} pieces`,
      }),
    });
    return total === null || uom === null ? noun : `${noun} · ${total} ${uom}`;
  };
  /** The reason a piece's job, completion and occupancy are not its own. */
  const sameAs = (row: GridRow) =>
    props.t("customers.newConnect.units.sameAsRow", {
      service: serviceName(row.service),
      defaultValue: `Same as ${serviceName(row.service)} row`,
    });

  const columns: TableArrayColumn<Row>[] = [
    {
      key: "unit",
      label: props.t("customers.newConnect.step4.unit", { defaultValue: "Unit" }),
      groupOnce: true,
      cell: (row) =>
        row.kind === "order" ? (
          // ⊕ `CR-164-BRC10` item 17 — where a job applies is chosen ON ITS
          // ROW, editable, rather than in a second list under the table.
          <CellSelect
            name="applies-to"
            label={props.t("customers.newConnect.units.appliesTo", { defaultValue: "Applies to" })}
            value={row.order.scope}
            placeholder="—"
            options={appliesToOptions}
            onChange={(scope) => setAppliesTo(row.order.template_id, scope)}
          />
        ) : (
          <CellText
            name="unit"
            label={props.t("customers.newConnect.step4.unit", { defaultValue: "Unit" })}
            value={row.unit.label}
            // A unit is named by the pattern above; typing over it here would
            // be a second answer to the same question (hard rule 8: a unit
            // refines a premises by LABEL, and the pattern owns that label).
            blockedReason={props.t("customers.newConnect.units.unitFixed", {
              defaultValue: "Named by the range above.",
            })}
            onChange={() => undefined}
          />
        ),
    },
    {
      key: "kind",
      label: props.t("customers.newConnect.step4.kind", { defaultValue: "Kind" }),
      groupOnce: true,
      cell: (row) =>
        row.kind === "order" ? (
          <CellStatic name="kind">{dash}</CellStatic>
        ) : row.unit.isCommonArea || unitTypeOptions.length === 0 ? (
          <CellStatic name="kind">
            {row.unit.isCommonArea
              ? props.t("customers.newConnect.step4.common", { defaultValue: "Common area" })
              : props.t("customers.newConnect.step4.dwelling", { defaultValue: "Dwelling" })}
          </CellStatic>
        ) : (
          // ⊕ `CR-164-BRC10` item 15 — the unit's TYPE, per row.
          <CellSelect
            name="unit-type"
            label={props.t("customers.newConnect.units.unitType", { defaultValue: "Unit type" })}
            value={props.draft.unitTypes?.[row.unit.label] ?? ""}
            placeholder={props.t("customers.newConnect.step4.dwelling", { defaultValue: "Dwelling" })}
            options={unitTypeOptions}
            onChange={(unitType) => setUnitType(row.unit.label, unitType)}
          />
        ),
    },
    {
      key: "service",
      label: props.t("customers.newConnect.units.service", { defaultValue: "Service" }),
      cell: (row) => {
        if (row.kind === "order") {
          return <CellStatic name="service">{dash}</CellStatic>;
        }
        if (row.kind === "piece") {
          // ⊕ `DEF-CUS-9840` — a SUB-ROW of its service row: *↳ Panel 2 · 10 kW*.
          const size = (row.grid.cell.more ?? [])[row.index] ?? "";
          const sizeName = sizeOptions(row.grid.service).find((one) => one.code === size)?.name;
          return (
            <span className="block pl-4" data-piece-of={row.grid.service}>
              <CellStatic name="service">
                {`↳ ${pieceLabel(resolvedAssetType(row.grid), row.index + 2)}`}
                {sizeName === undefined ? null : ` · ${sizeName}`}
              </CellStatic>
            </span>
          );
        }
        const value = row.kind === "service" ? row.grid.service : "";
        // ⊕ `DEF-CUS-9840` — the service row says how many pieces it holds and,
        // for a service that sums, their total: *3 panels · 21 kW*.
        const summary =
          row.kind === "service" && row.grid.taken && (row.grid.cell.more ?? []).length > 0
            ? piecesSummary(row.grid)
            : null;
        return (
          <>
          <CellSelect
            name="service"
            label={props.t("customers.newConnect.units.service", { defaultValue: "Service" })}
            value={value}
            placeholder={props.t("customers.newConnect.units.chooseService", {
              defaultValue: "Choose a service",
            })}
            options={offeredServices.map((code) => ({ value: code, label: serviceName(code) }))}
            onChange={(service) => {
              setLastUnit(row.unit.label);
              if (service === "") {
                return;
              }
              const key = unitServiceKey(row.unit.label, service);
              const taken = grid.find((one) => one.key === key && one.taken);
              const device = taken === undefined ? "" : resolvedAssetType(taken);
              // ⊕ `OQ-1361` — the service is already on this unit and is sized
              // by a COUNTED device (a cart, a fire line, a panel): the new row
              // is one more piece of it, never a second service row.
              // ⊕ `DEF-CUS-9267` — the new piece copies the size the CLERK
              // picked on the row, and starts empty when they picked none:
              // never the list's first row. Continue asks for an empty one.
              if (taken !== undefined && device !== "" && !meterTypeCodes.has(device)) {
                patchCell(key, { more: [...(taken.cell.more ?? []), resolvedSize(taken)] });
              } else {
                patchCell(key, { taken: true });
              }
              if (row.kind === "pending") {
                setPending((current) => current.filter((one) => one.id !== row.id));
              }
            }}
          />
          {summary === null ? null : (
            <Note as="span" className="block" data-pieces-summary={row.kind === "service" ? row.grid.key : ""}>
              {summary}
            </Note>
          )}
          </>
        );
      },
    },
    {
      key: "asset",
      label: props.t("customers.newConnect.units.asset", { defaultValue: "Asset" }),
      cell: (row) => {
        if (row.kind === "piece") {
          // The service row's device — a piece is more of the same thing.
          const code = resolvedAssetType(row.grid);
          return (
            <CellStatic name="asset">
              {assetTypeOptions(row.grid.service).find((type) => type.code === code)?.name ?? dash}
            </CellStatic>
          );
        }
        if (row.kind !== "service") {
          // `step3a-add-row.png` greys Asset and Size on a new row and says why
          // in its own words; BR-SHL-025 puts the reason on the control.
          return row.kind === "pending" ? (
            <CellSelect
              name="asset"
              label={props.t("customers.newConnect.units.asset", { defaultValue: "Asset" })}
              value=""
              placeholder="—"
              options={[]}
              blockedReason={props.t("customers.newConnect.units.needsService", {
                defaultValue: "Choose a service first.",
              })}
              onChange={() => undefined}
            />
          ) : (
            <CellStatic name="asset">{dash}</CellStatic>
          );
        }
        const types = assetTypeOptions(row.grid.service);
        // A STATED ABSENCE, CLOSED BY DEFAULT (B14 rule 32). Storm water has no
        // device at all (`DEF-2388`); fire has had the fire line since the PO
        // ruled `OQ-1361` on 2026-10-02.
        return types.length === 0 ? (
          <CellStatic name="asset">{dash}</CellStatic>
        ) : (
          <CellSelect
            name="asset"
            fit
            label={props.t("customers.newConnect.units.asset", { defaultValue: "Asset" })}
            value={resolvedAssetType(row.grid)}
            placeholder={props.t("customers.newConnect.step5.noAsset", { defaultValue: "None" })}
            options={types.map((type) => ({ value: type.code, label: type.name }))}
            onChange={(assetType) => patchCell(row.grid.key, { assetType })}
          />
        );
      },
    },
    {
      key: "size",
      label: props.t("customers.newConnect.step5.size", { defaultValue: "Size" }),
      cell: (row) => {
        if (row.kind === "piece") {
          const more = row.grid.cell.more ?? [];
          return (
            <CellSelect
              name="size"
              fit
              label={props.t("customers.newConnect.step5.size", { defaultValue: "Size" })}
              value={more[row.index] ?? ""}
              placeholder="—"
              options={bySize(sizeOptions(row.grid.service)).map((size) => ({
                value: size.code,
                label: size.name,
              }))}
              onChange={(sizeClass) =>
                patchCell(row.grid.key, {
                  more: more.map((one, index) => (index === row.index ? sizeClass : one)),
                })
              }
            />
          );
        }
        if (row.kind !== "service") {
          return row.kind === "pending" ? (
            <CellSelect
              name="size"
              label={props.t("customers.newConnect.step5.size", { defaultValue: "Size" })}
              value=""
              placeholder="—"
              options={[]}
              blockedReason={props.t("customers.newConnect.units.needsService", {
                defaultValue: "Choose a service first.",
              })}
              onChange={() => undefined}
            />
          ) : (
            <CellStatic name="size">{dash}</CellStatic>
          );
        }
        const sizes = sizeOptions(row.grid.service);
        // Sewer, BY RULING — a share of the water usage charge (BR-RAT-015),
        // reads no register and has nothing to size. Not a gap.
        return sizes.length === 0 ? (
          <CellStatic name="size">{dash}</CellStatic>
        ) : (
          <CellSelect
            name="size"
            fit
            label={props.t("customers.newConnect.step5.size", { defaultValue: "Size" })}
            value={resolvedSize(row.grid)}
            placeholder="—"
            options={bySize(sizes).map((size) => ({ value: size.code, label: size.name }))}
            onChange={(sizeClass) => patchCell(row.grid.key, { sizeClass })}
          />
        );
      },
    },
    {
      key: "workOrder",
      label: props.t("customers.newConnect.step5.workOrder", { defaultValue: "Work order" }),
      cell: (row) => {
        if (row.kind === "order") {
          // ⊕ `CR-164-BRC10` item 16 — a build-level job's row carries the
          // work-order dropdown too, so the job can be changed in place.
          return (
            <CellSelect
              name="work-order"
              label={props.t("customers.newConnect.step5.workOrder", { defaultValue: "Work order" })}
              value={row.order.template_id}
              placeholder="—"
              options={[
                { value: row.order.template_id, label: row.order.name },
                ...addable.map((candidate) => ({ value: candidate.id, label: candidate.name })),
              ]}
              onChange={(templateId) => replaceOrder(row.order.template_id, templateId)}
            />
          );
        }
        // A STATED ABSENCE (B14 rule 32) — this build proposed no jobs at all.
        if (orders.length === 0) {
          return <CellStatic name="work-order">{dash}</CellStatic>;
        }
        // ⊕ `DEF-CUS-9840` — PO ruling (a): a piece is fitted by its service
        // row's ONE job. It drew a dash, which read as *no job*; it now shows
        // that job, greyed, and says whose it is. Editable on the service row.
        if (row.kind === "piece") {
          return (
            <>
              <CellSelect
                name="work-order"
                label={props.t("customers.newConnect.step5.workOrder", { defaultValue: "Work order" })}
                value={resolvedOrderId(row.grid)}
                placeholder={props.t("customers.newConnect.step5.noOrder", { defaultValue: "None" })}
                options={orders}
                blockedReason={sameAs(row.grid)}
                onChange={() => undefined}
              />
              <Note as="span" className="block" data-same-as={row.grid.key}>
                {sameAs(row.grid)}
              </Note>
            </>
          );
        }
        return (
          <CellSelect
            name="work-order"
            label={props.t("customers.newConnect.step5.workOrder", { defaultValue: "Work order" })}
            value={row.kind === "service" ? resolvedOrderId(row.grid) : ""}
            placeholder={props.t("customers.newConnect.step5.noOrder", { defaultValue: "None" })}
            options={orders}
            blockedReason={
              row.kind === "pending"
                ? props.t("customers.newConnect.units.needsService", {
                    defaultValue: "Choose a service first.",
                  })
                : undefined
            }
            onChange={(workOrderTemplateId) =>
              row.kind === "service" ? patchCell(row.grid.key, { workOrderTemplateId }) : undefined
            }
          />
        );
      },
    },
    {
      key: "completes",
      label: props.t("customers.newConnect.units.completes", { defaultValue: "Completes" }),
      cell: (row) => {
        // ⚠ **`BR-WRK-013` — THE FLAG IS THE TEMPLATE'S OWN, NEVER A CLERK'S.**
        // On gas the completing job is the light-up and never the meter set. A
        // tick a clerk could set would let the build claim a service is live
        // when the template says it is not, so the drawn box is rendered and
        // refused WITH ITS REASON (BR-SHL-025) rather than dropped.
        // ⊕ `DEF-CUS-9840` — a piece shows its service row's tick, greyed,
        // with whose it is (the same one job completes them all).
        const templateId =
          row.kind === "order"
            ? row.order.template_id
            : row.kind === "service" || row.kind === "piece"
              ? resolvedOrderId(row.grid)
              : "";
        const order = props.proposed.find((one) => one.template_id === templateId);
        return (
          <CellTick
            name="completes"
            label={props.t("customers.newConnect.units.completes", { defaultValue: "Completes" })}
            checked={order?.is_gate === true}
            blockedReason={
              row.kind === "piece"
                ? sameAs(row.grid)
                : props.t("customers.newConnect.units.completesSet", {
                    defaultValue: "Set by the template.",
                  })
            }
            onChange={() => undefined}
          />
        );
      },
    },
    {
      key: "occupancy",
      label: props.t("customers.newConnect.step4.occupancy", { defaultValue: "Occupancy" }),
      cell: (row) => {
        if (row.kind === "order") {
          return <CellStatic name="occupancy">{dash}</CellStatic>;
        }
        const occupancy = occupancyOfUnit(props.draft, row.unit);
        // ⊕ `DEF-CUS-9840` — occupancy is the UNIT's, so a piece shows the
        // unit's answer greyed; it is changed on the service row.
        if (row.kind === "piece" && occupancy !== null) {
          return (
            <CellSelect
              name="occupancy"
              label={props.t("customers.newConnect.step4.occupancy", { defaultValue: "Occupancy" })}
              value={occupancy}
              placeholder="—"
              options={OCCUPANCY_CELL_WORDS.map((entry) => ({
                value: entry.code,
                label: occupancyCellWord(entry.code, props.t),
              }))}
              blockedReason={sameAs(row.grid)}
              onChange={() => undefined}
            />
          );
        }
        // ⚠ **A DASH, NOT A BLANK AND NOT A DEFAULT.** A corridor is not vacant
        // or occupied — it is not a dwelling.
        return occupancy === null ? (
          <CellStatic name="occupancy">{dash}</CellStatic>
        ) : (
          <CellSelect
            name="occupancy"
            label={props.t("customers.newConnect.step4.occupancy", { defaultValue: "Occupancy" })}
            value={occupancy}
            placeholder="—"
            options={OCCUPANCY_CELL_WORDS.map((entry) => ({
              value: entry.code,
              label: occupancyCellWord(entry.code, props.t),
            }))}
            onChange={(next) => setOccupancy(row.unit.label, next as OccupancyChoice)}
          />
        );
      },
    },
  ];

  // The common selection's five columns are the units table's middle five, with
  // no Unit, Kind, Completes or Occupancy — occupancy is a field above it, once.
  const commonColumns: TableArrayColumn<GridRow>[] = [
    {
      key: "service",
      label: props.t("customers.newConnect.units.service", { defaultValue: "Service" }),
      cell: (row) => <CellStatic name="service">{serviceName(row.service)}</CellStatic>,
    },
    {
      key: "asset",
      label: props.t("customers.newConnect.units.asset", { defaultValue: "Asset" }),
      cell: (row) => {
        const types = assetTypeOptions(row.service);
        return types.length === 0 ? (
          <CellStatic name="asset">{dash}</CellStatic>
        ) : (
          <CellSelect
            name="asset"
            fit
            label={props.t("customers.newConnect.units.asset", { defaultValue: "Asset" })}
            value={resolvedAssetType(row)}
            placeholder={props.t("customers.newConnect.step5.noAsset", { defaultValue: "None" })}
            options={types.map((type) => ({ value: type.code, label: type.name }))}
            onChange={(assetType) => patchCommon(row.service, { assetType })}
          />
        );
      },
    },
    {
      key: "size",
      label: props.t("customers.newConnect.step5.size", { defaultValue: "Size" }),
      cell: (row) => {
        const sizes = sizeOptions(row.service);
        return sizes.length === 0 ? (
          <CellStatic name="size">{dash}</CellStatic>
        ) : (
          <CellSelect
            name="size"
            fit
            label={props.t("customers.newConnect.step5.size", { defaultValue: "Size" })}
            value={resolvedSize(row)}
            placeholder="—"
            options={bySize(sizes).map((size) => ({ value: size.code, label: size.name }))}
            onChange={(sizeClass) => patchCommon(row.service, { sizeClass })}
          />
        );
      },
    },
    {
      key: "workOrder",
      label: props.t("customers.newConnect.step5.workOrder", { defaultValue: "Work order" }),
      cell: (row) =>
        orders.length === 0 ? (
          <CellStatic name="work-order">{dash}</CellStatic>
        ) : (
          <CellSelect
            name="work-order"
            label={props.t("customers.newConnect.step5.workOrder", { defaultValue: "Work order" })}
            value={resolvedOrderId(row)}
            placeholder={props.t("customers.newConnect.step5.noOrder", { defaultValue: "None" })}
            options={orders}
            onChange={(workOrderTemplateId) => patchCommon(row.service, { workOrderTemplateId })}
          />
        ),
    },
  ];

  const addable = (templatesQuery.data?.results ?? []).filter(
    (row) =>
      row.status === "published" &&
      row.version > 0 &&
      !props.proposed.some((one) => one.template_id === row.id),
  );
  /** ⊕ `CR-164-BRC10` item 17 — where the next added job applies. */
  const [newScope, setNewScope] = useState<string>(WHOLE_BUILD);
  /** Add one catalogue job, in `getProposedWorkOrders`' own shape, so the
   *  list, the manifest and `commitPlanOf`'s `work_orders` read one vocabulary. */
  const addOrder = (templateId: string, scope: string, without?: string) => {
    const row = addable.find((candidate) => candidate.id === templateId);
    if (row === undefined) {
      return;
    }
    props.onPatch({
      addedWorkOrders: [
        ...props.draft.addedWorkOrders.filter((one) => one.template_id !== without),
        {
          template_id: row.id,
          template_no: row.template_no,
          name: row.name,
          service: row.service,
          scope,
          sequence: row.sequence,
          job_type: row.job_type,
          is_gate: row.is_gate,
          version: row.version,
          est_duration_minutes: row.est_duration_minutes,
        },
      ],
      removedWorkOrderTemplateIds: props.draft.removedWorkOrderTemplateIds.filter(
        (one) => one !== row.id,
      ),
    });
  };
  /** ⊕ item 16 — change an added job's template in place, keeping its scope. */
  const replaceOrder = (fromId: string, toId: string) => {
    if (fromId === toId) return;
    const scope =
      props.draft.addedWorkOrders.find((one) => one.template_id === fromId)?.scope ?? WHOLE_BUILD;
    addOrder(toId, scope, fromId);
  };

  return (
    <>
      {/* ── THE FOUR TILES ────────────────────────────────────────────────
          Every figure is COMPUTED from the rows in front of the person. None
          is the drawn number (B14 rule 37), and the PO ruled these stay
          visible because they are the only feedback that the table is right. */}
      <KPIStrip
        kpis={[
          {
            id: "services-here",
            label: props.t("customers.newConnect.units.servicesHere", {
              defaultValue: "Services here",
            }),
            value: props.t("customers.newConnect.units.ofTotal", {
              defaultValue: "{{count}} of {{total}}",
              count: props.draft.premiseServices.length,
              total: offeredServices.length,
            }),
          },
          {
            id: "service-points",
            label: props.t("customers.newConnect.step5.servicePoints", {
              defaultValue: "Service points",
            }),
            value: counts.servicePoints,
          },
          {
            id: "meters",
            label: props.t("customers.newConnect.step5.metersToFit", {
              defaultValue: "Meters to fit",
            }),
            value: counts.meters,
          },
          {
            id: "work-orders",
            label: props.t("customers.newConnect.step5.workOrders", {
              defaultValue: "Work orders",
            }),
            // ⊕ `DEF-CUS-9197` — the count the COMMIT writes: one order per
            // surviving proposal (`commitPlanOf`'s `work_orders`), the same
            // figure step 5 shows. Distinct templates on the rows undercounted
            // a whole-build order no row names.
            value: props.t("customers.newConnect.units.willBeWritten", {
              defaultValue: "{{count}} will be written",
              count: props.proposed.length,
            }),
          },
        ]}
      />

      {/* ══════════════════════════════════════════════════════════════════
          THE COMMON SELECTION
          ══════════════════════════════════════════════════════════════════ */}
      <Panel
        as="section"
        title={props.t("customers.newConnect.units.common", { defaultValue: "Common selection" })}
      >
        <FieldGrid columns={2}>
          <TextField
            id="nc_from"
            label={props.t("customers.newConnect.units.unitsFrom", { defaultValue: "Units from" })}
            numeric
            value={props.draft.pattern.from}
            onChange={(from) => set({ from })}
          />
          <TextField
            id="nc_to"
            label={props.t("customers.newConnect.step4.to", { defaultValue: "To" })}
            numeric
            value={props.draft.pattern.to}
            onChange={(to) => set({ to })}
            // ⊕ **`DEF-CUS-10046` (PO 2026-10-11, SR-26-0027) — HOW MANY UNITS
            // THE RANGE MAKES, AS A FACT.** Step 2's `2` arrived here as *from 2
            // to 2* — ONE unit labelled `2` — where the PO expected two, and
            // nothing on screen said which. Step 2's box stays a LABEL (its own
            // help says so); this states the count so the clerk can see it and
            // correct the range. It is not `unitPatternSentence`, retired on
            // 2026-09-28 for restating the boxes with rationale: a count is a
            // fact the boxes do not show (B14 rule 33, ≤ 6 words).
            help={rangeCountLine(props.draft.pattern, props.units, props.t)}
          />
          <SelectField
            id="nc_common_occupancy"
            label={props.t("customers.newConnect.step4.occupancy", { defaultValue: "Occupancy" })}
            value={props.draft.occupancy}
            onChange={(occupancy) => props.onPatch({ occupancy: occupancy as OccupancyChoice })}
            options={OCCUPANCY_CELL_WORDS.map((entry) => ({
              value: entry.code,
              label: occupancyCellWord(entry.code, props.t),
            }))}
          />
          {/* ⊕ `CR-164-BRC10` item 15 — the unit type, set for every dwelling
              by *Apply to all*; each row can still change its own. */}
          {unitTypeOptions.length > 0 && (
            <SelectField
              id="nc_common_unit_type"
              label={props.t("customers.newConnect.units.unitType", { defaultValue: "Unit type" })}
              value={props.draft.commonUnitType ?? ""}
              placeholder={props.t("customers.newConnect.units.chooseUnitType", {
                defaultValue: "Choose a unit type",
              })}
              onChange={(commonUnitType) => props.onPatch({ commonUnitType })}
              options={unitTypeOptions}
            />
          )}
          {/* ⚠ **ASKED ONCE, HERE — it moved off the absorbed Work orders
              step.** It is the SAME `draft.targetActivation` the commit already
              sends; only the screen it is asked on moved. */}
          <DatePickerField
            id="nc_target"
            label={props.t("customers.newConnect.step5.target", {
              defaultValue: "Target activation date",
            })}
            value={props.draft.targetActivation}
            dateFormat={props.dateFormat}
            onChange={(targetActivation) => props.onPatch({ targetActivation })}
          />
        </FieldGrid>

        <div className="mt-3 flex flex-wrap items-center gap-3">
          {/* ⛔ **`BR-MET-1179` — OFFERED ON EVERY TYPE, AND NOT TICKED BY
              DEFAULT.** PO 2026-09-21: *"Common area is optional not
              mandetory"*. A clerk who wants one on a house ticks this box. */}
          <CheckboxField
            id="nc_common_area"
            label={props.t("customers.newConnect.step4.commonArea", {
              defaultValue: "Include a common-area unit",
            })}
            checked={props.draft.pattern.includeCommonArea}
            onChange={(includeCommonArea) => set({ includeCommonArea })}
          />
          {/* ⛔ DRAWN AND NOT BUILT, STILL DISABLED. There is no upload door, so
              it keeps `BR-SHL-025`'s reason in its `title` and says nothing on
              screen (B14 rule 33 — why a control is absent is rationale). */}
          <Button
            variant="secondary"
            disabled
            title={props.t("customers.newConnect.step4.uploadWhy", {
              defaultValue: "Not built yet. Add the units here.",
            })}
          >
            {props.t("customers.newConnect.step4.upload", {
              defaultValue: "↑ Upload a unit schedule",
            })}
          </Button>
        </div>

        {/* ⚠ **`EditableTable` DIRECTLY, NOT `TableArray`, AND THE DIFFERENCE
            IS A HEADING.** `TableArray` is the kit's FRAME — its own docstring
            says so: *"a panel, a heading, a fact on the heading's right, a
            footer of actions"*. This table is already inside the common
            selection's panel and under its heading, so wrapping it in a second
            frame printed **Common selection twice**, one inside the other,
            with two borders. Seen in a browser at 1440 and fixed there (law
            6); no gate reads rendered output and nothing else could have found
            it. The units table below IS its own collection and keeps the
            frame. */}
        <div className="mt-4">
          <EditableTable<GridRow>
            readOnly
            caption=""
            numbered={false}
            reorderable={false}
            columns={commonColumns}
            rows={commonRows}
            rowKey={(row) => row.key}
            emptyText={props.t("customers.newConnect.units.noServices", {
              defaultValue: "No service chosen. Pick one on Premise.",
            })}
            data-collection="common-selection"
          />
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button variant="primary" data-apply-to-all="" onClick={applyToAll}>
            {props.t("customers.newConnect.units.applyToAll", { defaultValue: "Apply to all" })}
          </Button>
          {/* An INSTRUCTION at six words a sentence (B14 rule 33). */}
          {rowsEmpty && (
            <Note as="span" data-apply-note="">
              {props.t("customers.newConnect.units.applyNote", {
                defaultValue: "Required before Continue. Rows stay editable.",
              })}
            </Note>
          )}
        </div>
      </Panel>

      {/* ══════════════════════════════════════════════════════════════════
          UNITS AND SERVICE POINTS
          ══════════════════════════════════════════════════════════════════ */}
      {/* ⛔ **`DEF-MET-6111` — THE ADDRESS ANSWERS BEFORE THE CLERK COMMITS.**
          PO ruling 2026-09-21. A label this building already holds cannot be
          created (`uq_units_tenant_premises_label`), and until this strip the
          clerk learned that from the database, as an HTTP 500, eight steps
          later. It names the FIRST clash; each unit's own group names its own,
          which is where a list is legible. **Kept through the fold: the
          drawing draws a screen and not this state, so its silence is not a
          decision to remove a ruled refusal.** */}
      {props.units.some((unit) => props.labelsAlreadyHere.includes(unit.label)) && (
        <RefusalStrip data-labels-taken="">
          {props.t("customers.newConnect.step4.labelTaken", {
            defaultValue: "{{label}} already exists here. Change the unit numbers.",
            label:
              props.units.find((unit) => props.labelsAlreadyHere.includes(unit.label))?.label ?? "",
          })}
        </RefusalStrip>
      )}

      {props.proposalsUnavailable && (
        <RefusalStrip data-proposals="unavailable">
          {props.t("customers.newConnect.step5.ordersFailed", {
            defaultValue: "Work orders could not be loaded. The build can still be created.",
          })}
        </RefusalStrip>
      )}

      <TableArray<Row>
        collection="units-and-service-points"
        title={props.t("customers.newConnect.units.title", {
          defaultValue: "Units and service points",
        })}
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        groups={groups}
        groupOf={(row) => (row.kind === "order" ? orderGroupKey(row.order.scope) : `unit:${row.unit.label}`)}
        // ⊕ `DEF-CUS-9840` — a piece is a SUB-ROW of the service row above it.
        rowNested={(row) => row.kind === "piece"}
        emptyText={props.t("customers.newConnect.units.empty", {
          defaultValue: "No units yet. Type a range above.",
        })}
        removeLabel={props.t("customers.newConnect.units.remove", { defaultValue: "Remove row" })}
        // ⚠ **THE KIT'S ✕ SPLICES A FLAT LIST, AND TWO OF THIS TABLE'S THREE
        // ROW KINDS ARE NOT IN ONE.** A pending row lives in this component and
        // a build order lives in `draft.addedWorkOrders`, so splicing would
        // drop the wrong thing. The row that LEFT is read out of the list the
        // kit hands back and routed to the writer that owns it — the kit's own
        // control, in the drawn column, with a real handler behind it.
        onChange={(next) => {
          const kept = new Set(next.map((row) => row.id));
          const gone = rows.find((row) => !kept.has(row.id));
          if (gone !== undefined) {
            removeRow(gone);
          }
        }}
        actions={[
          {
            key: "add-row",
            label: props.t("customers.newConnect.units.addRow", { defaultValue: "+ Add row" }),
            onClick: () => {
              if (targetUnit === undefined) {
                return;
              }
              setLastUnit(targetUnit.label);
              setOpenGroups((current) => ({ ...current, [`unit:${targetUnit.label}`]: true }));
              setPending((current) => [
                ...current,
                { id: `pending:${current.length}:${targetUnit.label}`, label: targetUnit.label },
              ]);
            },
            blockedReason:
              props.units.length === 0
                ? props.t("customers.newConnect.units.noUnitsYet", {
                    defaultValue: "Type a unit range first.",
                  })
                : undefined,
          },
          {
            key: "add-work-order",
            label: props.t("customers.newConnect.units.addOrder", {
              defaultValue: "+ Add work order",
            }),
            // The picker sits under the table; the button takes the clerk to it.
            onClick: () => document.getElementById("nc_add_order")?.focus(),
            blockedReason: templatesQuery.isError
              ? props.t("customers.newConnect.step5.templatesFailed", {
                  defaultValue: "Templates could not be loaded. Nothing more can be added.",
                })
              : undefined,
          },
        ]}
      >
        {/* ── `+ Add work order` — THE ROW IT ADDS, IN PLACE ────────────────
            `step3b-add-work-order.png`: the row carries a template SEARCH and
            an `Applies to`, and Service, Asset and Size read —. */}
        <div className="mt-4" data-add-order="picker">
          {/* ⊕ **`CR-164-BRC10` item 17 — ONE *Applies to* AND ONE WORK-ORDER
              DROPDOWN.** It was a template search plus an *Applies to* per
              added job, stacked under the table; the PO asked for one pair, and
              the added job then lives in the table as an editable row. */}
          <FieldGrid columns={2}>
            <SelectField
              id="nc_add_order_applies"
              label={props.t("customers.newConnect.units.appliesTo", { defaultValue: "Applies to" })}
              value={newScope}
              onChange={setNewScope}
              options={appliesToOptions}
            />
            <SelectField
              id="nc_add_order"
              label={props.t("customers.newConnect.step5.addLabel", {
                defaultValue: "Work order template",
              })}
              value=""
              placeholder={props.t("customers.newConnect.units.chooseOrder", {
                defaultValue: "Choose a work order",
              })}
              options={addable.map((row) => ({
                // B14 rule 31 — the id is the VALUE and the name is what is read.
                value: row.id,
                label: row.service === null ? row.name : `${row.name} · ${row.service.name}`,
              }))}
              onChange={(templateId) => addOrder(templateId, newScope)}
            />
          </FieldGrid>
        </div>

        {/* B14 rule 17 — what is missing AND how to fill it. */}
        {props.proposed.length === 0 && !props.proposalsUnavailable && (
          <div className="mt-3" data-proposals="none">
            <Note className="max-w-measure">
              {props.t("customers.newConnect.step5.ordersNone", {
                defaultValue: "No template covers these services.",
              })}
            </Note>
            <p className="mt-1">
              <InlineLinkTo to={tenantPath(WORK_ORDER_TEMPLATES_ROUTE)}>
                {props.t("customers.newConnect.step5.ordersWrite", {
                  defaultValue: "Write a template",
                })}
              </InlineLinkTo>
            </p>
          </div>
        )}
      </TableArray>

      {/* ⚠ **THE COMMON SELECTION IS REQUIRED BEFORE CONTINUE**, and the wizard
          refuses on it. This says WHICH act is outstanding, once, as a fact. */}
      {!applied && rowsEmpty && props.units.length > 0 && (
        <RefusalStrip data-apply-required="">
          {props.t("customers.newConnect.units.applyFirst", {
            defaultValue: "Press Apply to all first.",
          })}
        </RefusalStrip>
      )}

      {/* ⊕ `DEF-CUS-9840` — ✕ on a service row that holds pieces. A CONSEQUENCE
          before an act, two short sentences (B14 rule 33); danger tier because
          the pieces go with it (rule 6). */}
      {confirmRemove !== null && (
        <ConfirmDialog
          title={props.t("customers.newConnect.units.removeAllTitle", {
            service: serviceName(confirmRemove.service),
            unit: confirmRemove.unit.label,
            defaultValue: `Remove ${serviceName(confirmRemove.service)} from ${confirmRemove.unit.label}?`,
          })}
          consequence={props.t("customers.newConnect.units.removeAllConsequence", {
            summary: piecesSummary(confirmRemove),
            defaultValue: `All ${piecesSummary(confirmRemove)} go too.`,
          })}
          confirmLabel={props.t("customers.newConnect.units.removeAllConfirm", {
            defaultValue: "Remove all ✓",
          })}
          confirmVariant="danger"
          working={false}
          onCancel={() => setConfirmRemove(null)}
          onConfirm={() => {
            patchCell(confirmRemove.key, { taken: false, more: [] });
            setConfirmRemove(null);
          }}
        />
      )}
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-150-BRC09 task T3 · 05-prototype/new-connect-redesign-2026-09-28/{step3-units,step3a-add-row,step3b-add-work-order}.png read AS IMAGES · the absorbed-field audit beside them · decision log 2026-09-28 answers 13, 14, 15 · B14 rules 17, 20, 21, 31, 32, 33, 37, 42, 43, 44
// generated: 2026-09-29 by lane STEP-3
// checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own) E✔ F✔ G✔ H=n/a
// gates: tsc · vitest src/features/customers/NewConnectUnitsStep.dom.test.tsx · routeBUtilities (this file is on src/styles/route-b-migrated.txt) · G31
// exceptions:
//   E1 **NO `Qty` COLUMN.** `OQ-CUS-12770` is OPEN and it multiplies a price on
//      a real invoice; `CR-150-BRC09` §5 forbids building it until the PO
//      rules. Absent rather than inert — see the header.
//   E2 the red ring round the new row in the two add-screens is NOT built;
//      both frames are explainers and the outline points at the row the prose
//      is about.
//   E3 every explanatory paragraph on the three drawings is NOT built — B14
//      rule 33 gives rationale zero words on screen, and removes rather than
//      shortens it.
//   E4 the strings here are `t(key, {defaultValue})` and are NOT fanned into
//      the eleven catalogues, which is what all seven sibling NewConnect step
//      files do. Catalogue parity (G15) is unaffected because no key is added
//      to any catalogue. Flagged to the TEXT lane rather than invented in ten
//      languages (B14 rule 35 — a catalogue is written in its own language).
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
