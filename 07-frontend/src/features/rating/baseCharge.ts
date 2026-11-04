// ── Trace ──────────────────────────────────────────────
// Story:    DEF-431 (the base charge is served as ONE scalar, so a rate matrix
//           shows the same base against every connection size) · DEF-430
//           (RAT-02's matrix still draws one row for every size).
//           Screens: RAT-02 (S11 detail) · RAT-03 (S11 wizard)
// Rules:    BR-RAT-088 CONFIRMED (PO 2026-08-20 — the CHARGE CODE owns the base
//           amount; `tariff_versions.base_charge` and the plan's own base both
//           stop being sources) · §A3 "one source, two surfaces" (the rate
//           matrix DISPLAYS the value, attributed, and cannot edit it) ·
//           BR-RAT-087 (the client never formats money) · DEF-277 ("blank base
//           = size not served" — absent is never zero)
// Tests:    src/features/rating/RateScheduleDetail.test.tsx ·
//           src/features/rating/RateScheduleWizard.test.tsx
// Impacts:  RateScheduleDetail.MatrixTab · RateScheduleWizard.SizeMatrixStep
// ───────────────────────────────────────────────────────
/**
 * WHERE A CONNECTION SIZE'S BASE AMOUNT COMES FROM — one answer, two screens.
 *
 * BR-RAT-088 gives the base to the charge code, and §A3 spells out what that
 * leaves a rate schedule: *"one source, two surfaces"* — RAT-02 and RAT-03 both
 * DISPLAY the amount, attributed (`$12.00 · from BASE-W`), and neither can edit
 * it. Two screens showing one fact is exactly where two implementations start
 * disagreeing, so the resolution lives here and both import it.
 *
 * **The worked cost of getting it wrong, as shown to the PO:** a 5/8"
 * residential water account where the plan, the schedule and `BASE-W` each say
 * `$12.00` bills **$24.00** — **$23,069.50 a month across 1,247 connections** —
 * *"and no test catches it, because both rows are individually correct and only
 * the rule makes the total wrong."*
 *
 * This module reads. It never posts, and there is deliberately no writer in it.
 */
import type { ChargeRow, ChargeSizeAmount } from "@/api/endpoints";

/**
 * BR-RAT-088 · which charge code owns this service's base, or `null`.
 *
 * **DECLARED, never inferred from the code string.** `Charge.is_base` is the
 * flag and CHG-02's step 1 is where a tenant sets it; matching `BASE-<service>`
 * would break the moment a tenant names theirs `SERVICE-CHG`, and it would break
 * silently. A code scoped to `null` — "Any service" — is not a service's base:
 * the server's own gate asks `is_base=True, service_id=<this service>`, and this
 * mirrors it exactly so the screen and the refusal agree.
 */
export function baseChargeFor(charges: readonly ChargeRow[], service: string): ChargeRow | null {
  if (service === "") {
    return null;
  }
  return (
    charges.find(
      (charge) => charge.is_base && charge.service === service && charge.status !== "inactive",
    ) ?? null
  );
}

/**
 * `CR-120-BRC06` · `BR-RAT-1025` — **WHICH CODE OWNS THIS SCHEDULE'S BASE, WHEN
 * THE SCHEDULE IS ALLOWED TO SAY.**
 *
 * PO ruling 2026-09-19, verbatim: *"no this is not correct ; So: plan → rate
 * schedule -> charge code → base charges - this is correct"*, and on why it
 * reverses nothing: *"we are not bindng base charges in rate schedule - you
 * were taking it default; now we are making it explicit it is a same rule -
 * change is default -> expliciate"*.
 *
 * **Two places a schedule's base can be decided, and the order matters:**
 *   1. `tariff_versions.base_charge_code` — what the SCHEDULE NAMES, and what
 *      the ENGINE reads first (`resolution.resolve_base_charge`).
 *   2. the `is_base` code for the service — the inferred route, unchanged, and
 *      what every schedule that exists today uses.
 *
 * ⚠ **THE SHAPE IS `PlanWizard.lateFeeSourceCharge`'s AND THE CITATION IS
 * DELIBERATE** (`BR-RAT-1011` / `CR-078`, PO 2026-09-07): *"Two places a plan
 * can name it, and the order matters: 1. `rate_plans.late_fee_charge` — what
 * the ENGINE actually reads. 2. an attached charge code"*. One pattern for two
 * bindings beats two patterns that happen to agree.
 *
 * ⚠ **A BOUND ID THE CATALOGUE DOES NOT CARRY RETURNS `null`, NOT THE INFERRED
 * CODE.** That is the same fail direction the engine takes and it is the point
 * of the binding: falling back here would draw one code on screen while the
 * bill uses another, with neither visibly wrong. The screen renders the
 * absence and the server refuses the activation
 * (`services._guard_bound_base_charge_code`), so the two agree about which
 * world they are in.
 *
 * **`boundId` of `""` or `null` is not an error** — it is the ordinary state
 * and it means *this schedule has not said*, which is question 2's job.
 */
export function boundBaseChargeFor(
  charges: readonly ChargeRow[],
  service: string,
  boundId: string | null | undefined,
): ChargeRow | null {
  if (boundId !== null && boundId !== undefined && boundId !== "") {
    return charges.find((charge) => charge.id === boundId) ?? null;
  }
  return baseChargeFor(charges, service);
}

/**
 * Whether this schedule's base is NAMED rather than inferred — the one fact a
 * screen needs to decide which sentence to print beside the code.
 *
 * It answers the question in the draft's own terms and never by comparing the
 * two codes, because **on every tenant today they are the SAME code**: a
 * comparison would report "inferred" for a binding a person deliberately made.
 */
export function baseChargeIsNamed(boundId: string | null | undefined): boolean {
  return boundId !== null && boundId !== undefined && boundId !== "";
}

/**
 * What a matrix cell should print for one connection size's base.
 *
 * Four outcomes, and the third and fourth are why this is a type rather than a
 * string:
 *
 *   · `"per-size"`   — `charge_code_amounts` has a row for this size WITH an
 *                      amount. r10's water matrix: 5/8" `$12.00`, 2" `$64.00`.
 *   · `"flat"`       — the code has no per-size rows at all, so its single
 *                      `amount_display` is the base for every size. This is
 *                      what every charge code in the database says today, and
 *                      it is honest rather than wrong: a utility with one base
 *                      really does charge it at every size.
 *   · `"not-served"` — a row EXISTS for this size and its amount is null.
 *                      DEF-277's *"blank base = size not served"*: the bill
 *                      REFUSES rather than charging `$0.00`. A screen must draw
 *                      this differently from `"no-amount"` below, because one
 *                      says *we do not serve 2"* and the other says *nobody has
 *                      priced the base yet*.
 *   · `"no-amount"`  — the code is declared and carries no amount anywhere.
 *
 * ⚠ **`amountDisplay` IS THE SERVER'S OWN TWO-PLACE STRING** (BR-RAT-087) and
 * is passed through character for character. Nothing here parses, scales,
 * rounds or sums a money value — that is the server's job, and a component
 * doing it is the client-side money arithmetic CLAUDE.md hard rule 2 forbids.
 */
export type BaseAmountKind = "per-size" | "flat" | "not-served" | "no-amount";

export interface BaseAmount {
  kind: BaseAmountKind;
  /** The two-place string to print, or null when there is nothing to print. */
  amountDisplay: string | null;
  /** The code the amount is attributed to — `from BASE-W`. */
  code: string;
}

function rowFor(
  amounts: readonly ChargeSizeAmount[],
  sizeClass: string | null,
): ChargeSizeAmount | undefined {
  if (sizeClass === null) {
    return undefined;
  }
  return amounts.find((row) => row.size_class === sizeClass);
}

/**
 * DEF-431 · the base for ONE size, from the code that owns it.
 *
 * `sizeClass` is `null` for the row that prices every size — a schedule with no
 * size axis at all draws exactly one row, and that row asks for the code's flat
 * amount. So a null size never matches a per-size row: it is a question about
 * the code, not about a size.
 */
export function baseAmountForSize(charge: ChargeRow, sizeClass: string | null): BaseAmount {
  const row = rowFor(charge.size_amounts, sizeClass);
  if (row !== undefined) {
    return row.amount_display === null
      ? { kind: "not-served", amountDisplay: null, code: charge.code }
      : { kind: "per-size", amountDisplay: row.amount_display, code: charge.code };
  }
  // No row for this size. The code's single amount is the base — which is the
  // TRUE answer for a code that does not vary by size, and the honest one for a
  // size a partially-filled table has not reached yet.
  return charge.amount_display === null
    ? { kind: "no-amount", amountDisplay: null, code: charge.code }
    : { kind: "flat", amountDisplay: charge.amount_display, code: charge.code };
}

/**
 * Whether this code prices the base BY SIZE at all.
 *
 * The screens use it to decide which sentence to print under the column: a code
 * with no per-size rows shows the same figure on every row and must SAY SO
 * (DEF-431's own reading — *"rendered with the gap stated rather than left to
 * look like five equal bases"*), while a code that does vary needs no such note.
 */
export function pricesBaseBySize(charge: ChargeRow | null): boolean {
  return charge !== null && charge.size_amounts.length > 0;
}
