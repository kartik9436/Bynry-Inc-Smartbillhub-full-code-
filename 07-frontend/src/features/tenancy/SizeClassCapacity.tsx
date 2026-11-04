// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-RAT-10220 (PO 2026-10-17, decision log "SOLAR/BATTERY BILL THE
//           SUM OF INSTALLED kW; A TENANT-ADDED SIZE CARRIES ITS OWN CAPACITY")
// Screen:   S8 → Reference data → Utility service size classes (Add / Edit, list)
// Rules:    BR-TEN-171 (a summing service's size IS a quantity) · CLAUDE.md
//           hard rule 2 (a quantity travels as a string, never a float) and
//           hard rule 3 (it always shows its unit) · B14 rule 43 (a piece of UI
//           is a component) · rule 33 (a label ≤ 3 words)
// ───────────────────────────────────────────────────────
/**
 * The CAPACITY of a utility-service size class — the field and the cell.
 *
 * PO 2026-10-17: a size added in Settings *"enters its kW (e.g. 47.84), stored
 * to 4 decimals"*, and *"do not hard code anything … it should able to handle
 * dyanmic capacities"*. So WHICH services ask is never a list here: the server
 * publishes `capacity_uom` on each service (`/settings/services`, from
 * `service_size_classes.capacity_uom_for_service`) and this field is drawn
 * exactly when the chosen service has one — kW for solar and battery, ton for
 * thermal, Mbps for broadband, ERU for storm water; never for trash, fire or a
 * banded service, which COUNT or pick a rate.
 *
 * The value is the clerk's own string and goes to the server as typed; the
 * server owns the rule (> 0, at most 4 decimals) and its refusal lands under
 * this input by its id, `capacity`.
 */
import type { LookupEntry, TenantServiceRow } from "@/api/endpoints";
import { TextField } from "@/components/FormModal";

import type { Translator } from "./settingsShared";

/** The unit the chosen service's sizes sum in, or `null` when it does not sum. */
export function capacityUomFor(
  services: readonly Pick<TenantServiceRow, "service" | "capacity_uom">[],
  serviceCode: string,
): string | null {
  if (serviceCode === "") return null;
  const row = services.find((one) => one.service === serviceCode);
  return row?.capacity_uom ?? null;
}

/** `"47.8400"` → `"47.84"`: a stored 4-dp quantity shown with its own places. */
export function trimCapacity(value: string): string {
  if (!value.includes(".")) return value;
  return value.replace(/0+$/, "").replace(/\.$/, "");
}

/** The list cell: `47.84 kW`, or an em dash where the size carries none. */
export function capacityText(row: Pick<LookupEntry, "capacity" | "capacity_uom">): string {
  const capacity = typeof row.capacity === "string" ? row.capacity : null;
  const uom = typeof row.capacity_uom === "string" ? row.capacity_uom : null;
  if (capacity === null || uom === null) return "—";
  return `${trimCapacity(capacity)} ${uom}`;
}

export function SizeClassCapacityField(props: {
  uom: string;
  value: string;
  onChange: (value: string) => void;
  t: Translator;
}) {
  return (
    <div data-field="capacity" data-capacity-uom={props.uom}>
      <TextField
        id="capacity"
        label={props.t("settings.reference.capacityLabel", { uom: props.uom })}
        value={props.value}
        onChange={props.onChange}
        numeric
        required
        autoComplete="off"
      />
    </div>
  );
}
