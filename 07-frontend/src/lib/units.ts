/**
 * `DEF-RAT-10220` — the screen's copy of the server's ONE unit-spelling rule
 * (`06-backend/core/units.py`): white space collapsed, case folded, never a
 * conversion. `KW`, ` kw ` and `kW` are one unit; `kWh` and `MWh` are not.
 * Used only to decide whether to WARN — the server decides what bills.
 */
export function unitKey(unit: string | null | undefined): string {
  return (unit ?? "").trim().split(/\s+/).filter(Boolean).join(" ").toLowerCase();
}

export function sameUnit(left: string | null | undefined, right: string | null | undefined): boolean {
  const a = unitKey(left);
  return a !== "" && a === unitKey(right);
}
