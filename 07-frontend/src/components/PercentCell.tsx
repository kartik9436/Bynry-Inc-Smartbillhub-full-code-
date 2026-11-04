// ── Trace ──────────────────────────────────────────────
// Story:    US-RBS-016 (EP-RBS-01) — CR-075 wave C task C1c.
//           Screens: every percentage on a runbook result — RBS-006-R4 (+38%
//           Usage), RBS-006-R16 (+4.7% Revenue), RBS-006-R2 (0.29% Of total ·
//           limit 0.05%), and every `percent` parameter on RBS-004
// Rules:    CLAUDE.md hard rule 2 (percentages stored to 6, DISPLAY 2 — PO
//           re-sign 2026-08-22: *"MOney 4 decimal, percentage 6 decimal,
//           display both 2 decimal"*) · OQ-286 CLOSED (PO 2026-08-20: *"for
//           perctnage you can have 6 decimal places"*) · BR-SHL-023 (ONE
//           formatting path — no screen formats for itself) · B14 rule 36
//           (compose the shared kit; this lands BESIDE MoneyCell, not in a
//           runbooks-local helper) · B14 rule 21 + its per-file clause
// Tests:    src/components/PercentCell.test.tsx (static) ·
//           src/components/PercentCell.dom.test.tsx (the tone map, asked of
//           the real Tailwind compiler — see the note on DEF-SHL-4281 below)
// Impacts:  04-docs/05-modules/17-runbooks/08-screen-layouts.md (the stamped
//           divergence: not one percentage in any of the 75 build sheets is
//           drawn at two decimals, and the RULE wins) ·
//           04-docs/05-modules/17-runbooks/09-component-inventory.md Part 5 §6
//           (which named this file before any code existed) ·
//           07-frontend/src/styles/route-b-migrated.txt
// ───────────────────────────────────────────────────────
//
// **THE FOURTH KIND OF NUMBER, AND THE FRONT END HAD NO CODE FOR IT AT ALL.**
// `MoneyCell.tsx` next door exports `formatMoney` (2 dp) and `formatRate`
// (2–4 dp since 2026-10-02) and nothing for a percent — verified 2026-09-06, zero
// occurrences of `formatPercent` anywhere under `src/`. So twelve runbook
// screens were each about to choose their own, and three screens already had:
// `AssetDetailPage.tsx` builds its own `Intl` formatter, `RoutesCyclesPage.tsx`
// interpolates `${progress}%`, `RateScheduleWizard.tsx` interpolates a constant.
// That is the drift BR-SHL-023 exists to prevent.
//
// ⚠ **AND THE CONVENTION CANNOT BE GUESSED — THE PRODUCT USES BOTH.**
// `06-backend/core/money_fields.py` says so in as many words: a percent is
// stored *"either as a fraction (`0.062500`) or as percent points (`40`) — the
// product uses both conventions"*. `taxes.rate` holds `0.062500` and means
// 6.25%; a threshold column holds `40` and means 40%.
//
// **A formatter that picks one is wrong by a factor of 100 on the other, on a
// money path, silently.** And magnitude cannot decide it either: `0.5` is a
// perfectly ordinary value under BOTH readings — 50.00% as a fraction, 0.50% as
// points — so a "less than 1 must be a fraction" heuristic answers confidently
// and wrongly on the one case where it matters. Recorded in the decision log
// 2026-09-06 with that worked figure rather than left to be re-derived.
//
// **So the convention is a REQUIRED argument.** It is the same shape `UnitCell`
// uses for hard rule 3 (the unit is compile-required, never assumed) and
// `KpiMoney` uses for `basis`: `tsc` refuses a call that does not say which kind
// of number it is holding, so "forgot to think about it" is unexpressible rather
// than merely discouraged.
import type { ReactNode } from "react";

import { DEFAULT_MONEY_LOCALE, MoneyAmountAbsent } from "./MoneyCell";

/**
 * Hard rule 2's percentage half: **what a person reads is two decimals**,
 * in every locale and under both conventions. `0.062500` is `6.25%`.
 *
 * ⚠ It is deliberately NOT `RATE_DISPLAY_DECIMALS`. A rate shows four because a
 * rate is multiplied by a quantity before it becomes money and its precision
 * compounds (OQ-620, PO 2026-08-27). A percentage is already the finished
 * figure a clerk reads, so hard rule 2 applies to it unchanged.
 */
export const PERCENT_DISPLAY_DECIMALS = 2;

/**
 * **Which kind of number the caller is holding. There is no default.**
 *
 * `fraction` — stored as a proportion: `"0.062500"` reads **6.25%**. This is
 *   what `percent_field()` calls *"a fraction"* and what `taxes.rate` holds.
 *   `PERCENT_PLACES = 6` exists precisely so a fraction can carry four decimals
 *   of percent without truncating.
 *
 * `points`   — stored as percent points: `"40"` reads **40.00%**, `"4.7"` reads
 *   **4.70%**. This is what a threshold or a computed change carries — the
 *   `+38%` on `RBS-006-R4` and the `+4.7%` on `RBS-006-R16`.
 */
export type PercentBasis = "fraction" | "points";

const DECIMAL_STRING_RE = /^-?\d+(\.\d+)?$/;

interface DecimalStringFormatter {
  format(value: string): string;
}

interface PercentFormatOptions extends Intl.NumberFormatOptions {
  // "halfExpand" = ties away from zero = B4.4's finance-signed half-up.
  roundingMode?: "halfExpand";
}

/**
 * Percent points → the fraction `Intl` wants, **by moving the decimal point,
 * never by dividing.**
 *
 * ⚠ **`Number(v) / 100` IS WRONG AND THE TEST FOR IT IS NOT CONTRIVED.**
 * `formatPercent("0.175", "points")` is `0.18%` on the exact value and `0.17%`
 * through a double, because `0.175 / 100` is `0.0017499999999999998`. Measured
 * across three-decimal points values, that shape diverges on `0.175`, `0.205`,
 * `0.235`, `0.285`, `0.305`, `0.355` and onward — every tie, in the direction
 * that reads LOWER. `PercentCell.test.tsx` asserts `0.175` as the float
 * detector, the way `MoneyCell.test.tsx` asserts `8.005`.
 *
 * A decimal shift on the string is exact for every value a `NUMERIC(18,6)`
 * column can hold, including ones a double cannot represent at all.
 */
function pointsToFraction(points: string): string {
  const negative = points.startsWith("-");
  const magnitude = negative ? points.slice(1) : points;
  const [whole, decimals = ""] = magnitude.split(".");
  // Two leading zeros so a value under 100 still has digits to give up.
  const padded = whole.padStart(3, "0");
  const cut = padded.length - 2;
  const shifted = `${padded.slice(0, cut)}.${padded.slice(cut)}${decimals}`;
  return negative ? `-${shifted}` : shifted;
}

/**
 * **THE percentage display.** `formatPercent("0.062500", "fraction")` →
 * `"6.25%"` · `formatPercent("40", "points")` → `"40.00%"`.
 *
 * Everything here is deliberately `formatMoney`'s behaviour, because a screen
 * that formats its two kinds of number by two different sets of rules is a
 * screen where one of them is wrong:
 *
 * * the value stays a decimal **STRING** and never becomes a float — a
 *   `NUMERIC(18,6)` percentage can exceed a double, and the ties above show it
 *   changes the answer well before it exceeds one;
 * * `roundingMode: "halfExpand"` is B4.4's half-up, so the display applies the
 *   same convention the backend applies at finalization;
 * * `min === max` pads as well as trims: `"0.047"` is `4.70%` and `"0.062537"`
 *   is `6.25%`, one setting in both directions;
 * * a malformed value renders **verbatim** rather than as `NaN%` — a working
 *   figure beats a client-side guess at what the server meant;
 * * an ABSENT value **throws** (`MoneyAmountAbsent`, shared with money) rather
 *   than inventing a dash. DEF-151's reasoning holds unchanged here: rendering
 *   an absence requires a REASON and this function has none to give, so the
 *   caller must branch before it gets here.
 *
 * ⚠ **The `%` is placed by the locale, never appended.** `6,25 %` in de-DE and
 * `%6,25` in tr-TR — a template literal would put the sign on the wrong side in
 * Turkish, which is exactly the kind of thing eleven catalogues are for.
 */
export function formatPercent(
  value: string,
  basis: PercentBasis,
  locale: string = DEFAULT_MONEY_LOCALE,
): string {
  // Guarded at runtime as well as in the type — DEF-151 is what a served null
  // does when only the type was asked, and a type is a claim until it is not.
  const supplied = value as string | null | undefined;
  if (supplied === null || supplied === undefined) {
    throw new MoneyAmountAbsent("%");
  }
  if (!DECIMAL_STRING_RE.test(value)) {
    return `${value}%`;
  }
  const fraction = basis === "points" ? pointsToFraction(value) : value;
  try {
    const options: PercentFormatOptions = {
      style: "percent",
      minimumFractionDigits: PERCENT_DISPLAY_DECIMALS,
      maximumFractionDigits: PERCENT_DISPLAY_DECIMALS,
      roundingMode: "halfExpand",
    };
    const formatter = new Intl.NumberFormat(locale, options) as unknown as DecimalStringFormatter;
    return formatter.format(fraction);
  } catch {
    return `${value}%`;
  }
}

/**
 * **The FIGURE of a percentage, without its sign** — for a catalogue sentence
 * that places the `%` itself (*"{{share}}% of money posted"*). `DEF-PAY-9644`:
 * the Payments Summary total printed `99.900000%` because its sentence took the
 * exact sum raw; hard rule 2 says two places, and the rows beside it must say
 * the same. Points only (`"35.2"` → `"35.20"`), because a sentence that holds
 * its own `%` is holding points. Same rounding and the same malformed-value
 * rule as `formatPercent` — one formatting path (BR-SHL-023).
 */
export function formatPercentFigure(points: string, locale: string = DEFAULT_MONEY_LOCALE): string {
  if (!DECIMAL_STRING_RE.test(points)) {
    return points;
  }
  try {
    const options: PercentFormatOptions = {
      minimumFractionDigits: PERCENT_DISPLAY_DECIMALS,
      maximumFractionDigits: PERCENT_DISPLAY_DECIMALS,
      roundingMode: "halfExpand",
    };
    const formatter = new Intl.NumberFormat(locale, options) as unknown as DecimalStringFormatter;
    return formatter.format(points);
  } catch {
    return points;
  }
}

/** Which way a percentage points, when the screen says so. Colour is meaning
 *  here and nothing else: `RBS-006-R4` draws `+38%` neutral beside a red
 *  `+$82.20`, because a bill going up is the finding and the usage figure is
 *  the explanation. A caller that does not declare a direction gets none. */
export type PercentDirection = "up" | "down" | "flat";

// ⚠ WHOLE STRINGS PER DIRECTION, NEVER AN INTERPOLATION. Tailwind's scanner
// cannot see `text-${tone}-700`, and a class the compiler never emitted renders
// as NOTHING while every `toContain` assertion still passes.
//
// ⚠ AND EVERY TOKEN HERE WAS ASKED OF THE COMPILER RATHER THAN READ OFF THE
// SHEET (DEF-SHL-4281, filed by this lane). `WarningBox.tsx` asks for
// `border-danger`, which this theme does not declare — there is
// `--color-danger-500` and `--color-danger-700` and no bare `--color-danger` —
// so its danger tone draws with no colour at all. `routeBUtilities.test.ts`
// exists to catch exactly that and is GREEN over it: its `kit_constant` pattern
// is `const NAME =`, which requires the equals sign to follow the identifier,
// so a constant carrying a TYPE ANNOTATION — like this one — matches nothing
// and every class inside it is invisible to both readers. Measured: 33 such
// constants across the 310 files on the ledger, `buttonKit.ts` and
// `StatusPill.tsx` among them. Until the grammar learns the annotated form,
// a tone map owes its own compiler assertion; `PercentCell.dom.test.tsx` is
// this one's, and it fails on a token this theme does not declare.
// ⚠ AND EACH ENTRY IS THE **WHOLE** class attribute, `tabular-nums` included —
// not a fragment glued on at the call site. The first draft interpolated the
// tone directly onto the end of the `tabular-nums` stem, with no space between
// them, and `routeBUtilities.test.ts` refused it by name: *"a className built at
// runtime is invisible to Tailwind's scanner — use a token in `style`, or a
// whole string literal per branch."* An interpolation SEPARATED by a space
// leaves whole tokens on both sides and is fine; one glued to a stem can produce
// a class name that exists in no source file, so the compiler never emits a rule
// for it. A real red this lane caused and a real guard catching it, recorded
// here rather than quietly repaired.
//
// ⚠ AND THE SECOND RED WAS THIS VERY COMMENT. The guard reads RAW SOURCE and
// does not strip comments, so the first version of the paragraph above — which
// quoted the offending line verbatim to explain it — tripped the guard by
// itself, in a file that no longer had the defect. Describing the shape in
// words is the fix; a check that cannot tell an example from an occurrence is
// worth knowing about before the next lane spends the same ten minutes.
const DIRECTION_CLASS: Record<PercentDirection | "none", string> = {
  up: "tabular-nums text-danger-700",
  down: "tabular-nums text-success-700",
  flat: "tabular-nums text-neutral-700",
  none: "tabular-nums",
};

export interface PercentCellProps {
  /** Decimal string from the API — never a number. */
  value: string;
  /** REQUIRED: fraction or percent points. There is no safe default. */
  basis: PercentBasis;
  /** Tenant Regional number format (IS-8). */
  locale?: string;
  /** Colour the figure by which way it points. Omit for no colour at all. */
  direction?: PercentDirection;
  /** A sign in front of the figure — `RBS-006-R16` draws `+4.7%`, and the plus
   *  is meaning rather than decoration: it says this is a CHANGE, not a level.
   *  `Intl` writes a minus for a negative value on its own, so this only ever
   *  adds the plus. */
  signed?: boolean;
}

/**
 * A percentage, drawn. `RBS-006-R2`'s *0.29% — Of total · limit 0.05%*.
 *
 * Numeric, so it is `tabular-nums` and right-alignable in a column — the same
 * reason `MoneyCell` is. B14 rule 20's table body size is inherited from the
 * cell rather than set here, so this composes into a `DataTable` without
 * fighting it.
 */
export function PercentCell(props: PercentCellProps) {
  const drawn = formatPercent(props.value, props.basis, props.locale);
  const positive = !drawn.trimStart().startsWith("-");
  const direction = props.direction ?? "none";
  return (
    <span
      className={DIRECTION_CLASS[direction]}
      data-percent=""
      data-percent-basis={props.basis}
      data-percent-direction={direction}
    >
      {props.signed === true && positive ? "+" : ""}
      {drawn}
    </span>
  );
}

/** What a `Records` column hands its cell renderer. Kept beside the cell so a
 *  block never builds one of these by hand. */
export function percentCell(
  value: string,
  basis: PercentBasis,
  extra?: Omit<PercentCellProps, "value" | "basis">,
): ReactNode {
  return <PercentCell value={value} basis={basis} {...extra} />;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-016 · CR-075 wave C task C1c · 09-component-inventory.md Part 5 §6 + Part 4 §7
// generated: 2026-09-06 by the CR-075 wave C build lane
// checklist: A=n/a B=n/a C✔ D=n/a E✔(the twelve blocks compose it; PercentCell is Part 5's sixth) F✔ G✔ H=n/a
// gates: vitest src/components/PercentCell.test.tsx + .dom.test.tsx · routeBUtilities (every class asked of the real compiler) · G31 (rule 21 — utilities only, no stylesheet class added) · tsc
// exceptions: the 75 build sheets draw percentages at 0 or 1 decimal; hard rule 2 wins and the divergence is stamped in 08-screen-layouts.md
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
