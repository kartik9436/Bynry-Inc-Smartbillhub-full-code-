// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-013 (EP-SHL-05 §Stories)  Screens: every consumption display (S7, S25, S26, S28, S30, …)
// Rules:    BR-SHL-023 (explicit unit, one formatting path)
// ───────────────────────────────────────────────────────
// FE-12 UnitCell (B13 §1): consumption with its EXPLICIT unit — a bare
// quantity never renders (CLAUDE.md rule 3). `unit` is a REQUIRED prop, so a
// consuming screen cannot compile without naming one; the label itself is the
// tenant's UoM reference data (Settings → Services & UoM), served with the
// quantity. The quantity is a decimal STRING and renders at its SIGNIFICANT
// precision — grouped for reading, never parsed into a float, never re-rounded
// (reads carry meaningful precision; inventing or dropping a SIGNIFICANT digit
// here would be a silent data change).
// ⚠ AMENDED AGAIN 2026-08-27 (DEF-1120, BR-SHL-250 §4). "Its SIGNIFICANT
// precision" was this file's answer while no rule existed, and the PO ruled one
// on 2026-08-27: BR-MET-144, *at most two decimals, trailing zeros trimmed*.
// This file had implemented the trim and not the rounding, so `26.243700 kgal`
// read `26.2437 kgal` here and `26.24 kgal` on the reads list, where the SERVER
// composes the same figure. `roundQuantityHalfUp` below is the missing half and
// it works on the decimal string — never on a float.
// ⚠ AMENDED 2026-08-24 (DEF-646). This line used to say "exactly as served",
// and that WAS the bug: the server sends BR-MET-019's `NUMERIC(18,6)`, so
// "exactly as served" put `1016.000000` and `8.000000 kgal` on the Meters tab.
// Trailing zeros are stripped now — a storage artefact, not a measurement, and
// removing them changes no value. Significant digits are untouched; the safety
// cases in the test file pin that.
// Until the tenant Regional settings feed arrives (US-SHL-013 service wiring),
// consumers that pass no locale get the en-US seed format.
const DEFAULT_QUANTITY_LOCALE = "en-US";

const DECIMAL_STRING_RE = /^-?\d+(\.\d+)?$/;

// Same narrow string-overload surface as MoneyCell: ES2023 Intl accepts
// decimal strings; the ES2022 TS lib lags. The value never becomes a float.
interface DecimalStringFormatter {
  format(value: string): string;
}

/**
 * The same decimal string with only its INSIGNIFICANT trailing zeros gone:
 * `1016.250000` → `1016.25`, `1016.000000` → `1016`, `0.000001` untouched.
 *
 * ⚠ **EXTRACTED 2026-08-27 (OQ-394's move-out prefill) SO THERE IS ONE
 * DERIVATION OF DEF-646's RULE AND NOT TWO.** `formatQuantity` below trims AND
 * groups for reading (`42,864`), and a GROUPED string can never go into an
 * input the clerk submits — the commas would reach the server as part of a
 * decimal. The move-out reading box needs the trim WITHOUT the grouping, so
 * the trim became its own function rather than a second copy of the regex.
 *
 * Malformed input comes back verbatim, exactly as `formatQuantity` treats it:
 * verbatim beats a guess.
 */
export function trimQuantity(quantity: string): string {
  if (!DECIMAL_STRING_RE.test(quantity)) {
    return quantity;
  }
  const [whole, fraction = ""] = quantity.split(".");
  const kept = fraction.replace(/0+$/, "");
  return kept === "" ? whole : `${whole}.${kept}`;
}

/**
 * **BR-MET-144's FIRST HALF, DONE ON STRINGS — at most two decimals, rounding
 * HALF-UP, and never through a float.**
 *
 * ⚠ **THIS FUNCTION IS THE HALF THIS FILE WAS MISSING (DEF-1120).** The rule
 * has two clauses and until now `formatQuantity` implemented only the second:
 * it trimmed the trailing zeros of `8.000000` and left `26.243700` at four
 * places. So the SAME consumption read `26.24 kgal` on the reads list — where
 * the server composes `usage_display` through
 * `apps/metering/quantity_display.py`, which rounds — and `26.2437 kgal` in
 * every `UnitCell` in the product. Two implementations of one signed rule, one
 * of them half (BR-SHL-250 §4).
 *
 * `Number(...)` is not used and must not be: a register reading is a
 * `NUMERIC(18,6)` that can exceed a double's 15 significant digits, and
 * `MoneyCell` next door already refuses floats for the same reason
 * (CLAUDE.md hard rule 2). The rounding is done by inspecting the decimal
 * STRING, so nothing is ever parsed.
 *
 * HALF-UP means AWAY FROM ZERO, matching `Decimal(ROUND_HALF_UP)` on the
 * server and B4's direction for money: `8.125` → `8.13`, `-8.125` → `-8.13`.
 */
function roundQuantityHalfUp(quantity: string): string {
  const negative = quantity.startsWith("-");
  const magnitude = negative ? quantity.slice(1) : quantity;
  const [whole, fraction = ""] = magnitude.split(".");
  if (fraction.length <= 2) {
    return quantity;
  }
  const kept = fraction.slice(0, 2);
  // Half-up on the decimal STRING: the discarded tail rounds the kept digits
  // up when its first digit is 5 or more. `8.129` → `13`; `8.124` → `12`.
  const roundUp = fraction.charCodeAt(2) >= "5".charCodeAt(0);
  let digits = `${whole}${kept}`;
  if (roundUp) {
    // Increment the integer spelled by `digits`, right to left, so a carry
    // walks correctly through `9.99` → `10.00` without ever becoming a Number.
    const out = digits.split("");
    let index = out.length - 1;
    for (; index >= 0; index -= 1) {
      if (out[index] === "9") {
        out[index] = "0";
      } else {
        out[index] = String(Number(out[index]) + 1);
        break;
      }
    }
    digits = index < 0 ? `1${out.join("")}` : out.join("");
  }
  const cut = digits.length - 2;
  const roundedWhole = cut <= 0 ? "0" : digits.slice(0, cut);
  const roundedFraction = digits.slice(Math.max(cut, 0)).padStart(2, "0");
  return `${negative ? "-" : ""}${roundedWhole}.${roundedFraction}`;
}

export function formatQuantity(
  quantity: string,
  locale: string = DEFAULT_QUANTITY_LOCALE,
): string {
  if (!DECIMAL_STRING_RE.test(quantity)) {
    return quantity; // malformed — verbatim beats NaN or a guess
  }
  // ⚠ TRAILING ZEROS ARE STRIPPED (DEF-646, PO 2026-08-24: *"meter reads are
  // whole numbers - youa re shoiwing 4 decimal"*, on a Meters tab reading
  // `1016.000000` and `8.000000 kgal`).
  //
  // THIS IS NOT THE "DROPPING DIGITS" THE HEADER WARNS ABOUT, and the
  // distinction is the whole fix. That warning is about SIGNIFICANT digits: a
  // read of `1016.25` must never render as `1016`, because the .25 is a
  // measurement and losing it changes what a clerk sees in a billing dispute.
  // A TRAILING ZERO carries no measurement at all — `8.000000` and `8` are the
  // same number to the last bit. The six zeros are an artefact of BR-MET-019's
  // `NUMERIC(18,6)` storage column arriving on the wire, not something a meter
  // ever produced.
  //
  // So: zeros are removed from the END of the fraction only, nothing is
  // rounded, and no non-zero digit can be reached. `1016.250000` → `1016.25`;
  // `1016.000000` → `1016`; `0.000001` → `0.000001`, untouched.
  //
  // ⚠ AND THE RULE THE PO CITED DOES NOT ACTUALLY COVER THIS — see DEF-646.
  // CLAUDE.md hard rule 2 fixes display at 2 decimals for MONEY and
  // PERCENTAGES. A meter read is neither, and BR-MET-019 says consumption is
  // stored UNROUNDED on purpose. No signed rule has ever said how many
  // decimals a QUANTITY shows, which is why this rendered raw. Stripping
  // insignificant zeros is the one correction that needs no new rule, because
  // it changes no value; what number of decimals a quantity should ROUND to is
  // still open and is filed rather than guessed at here.
  // ⚠ ROUND FIRST, THEN TRIM — the order is the rule and reversing it is
  // DEF-1120. Trimming `26.243700` gives `26.2437`, which has no trailing zero
  // left to remove and is still four places; rounding first gives `26.24`,
  // which then has nothing to trim. Rounding after a trim can also RE-CREATE a
  // trailing zero (`8.996` → `9.00`), which is why the trim is the second step
  // and not the first.
  const rounded = roundQuantityHalfUp(quantity);
  const fraction = trimQuantity(rounded).split(".")[1] ?? "";
  const digits = Math.min(20, fraction.length);
  const formatter = new Intl.NumberFormat(locale, {
    // Exactly the served precision: no Intl default 3-digit rounding, no
    // invented trailing zeros — display formatting only, never a data change.
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }) as unknown as DecimalStringFormatter;
  return formatter.format(rounded);
}

export interface UnitCellProps {
  quantity: string; // decimal string from the API — never a number
  unit: string; // REQUIRED (CLAUDE.md rule 3) — tenant UoM label, served with the quantity
  locale?: string; // tenant Regional number format (IS-8)
}

export function UnitCell(props: UnitCellProps) {
  // CR-018 Route B: UnitCell.css (deleted) ported value for value.
  // `.cell-unit` -> tabular-nums + whitespace-nowrap (A12: quantities align in
  // columns); `.cell-unit-qty`'s `font-feature-settings:"tnum"` (DEF-327) ->
  // `tabular-nums`, the kit's spelling of the same feature (workflowKit.ts
  // NUM_CELL precedent); `.cell-unit-label` -> text-sm text-neutral-700.
  // `data-cell="unit"` is the machine handle the class name used to double as
  // (CLAUDE.md rule 3 assertions grep for it).
  return (
    <span className="tabular-nums whitespace-nowrap" data-cell="unit">
      <span className="tabular-nums">{formatQuantity(props.quantity, props.locale)}</span>
      {" " /* non-breaking: the quantity never wraps away from its unit */}
      <span className="text-sm text-neutral-700">{props.unit}</span>
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-013@1e89ecb (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
