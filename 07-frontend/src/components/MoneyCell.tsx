// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-013 (EP-SHL-05 §Stories)  Screens: every money display (S7, S17, S21, S30, S33, S36, …)
// Rules:    BR-SHL-023 (one formatting path, 2dp at display) · BR-TEN-080 (display 2 · API 4 · storage 6) · BR-REP-001 (basis label) · BR-SHL-015 (display-only money)
// ───────────────────────────────────────────────────────
// FE-11 MoneyCell (B13 §1): THE money display. Money arrives from the API as a
// decimal STRING (stored NUMERIC(18,6), served at 4 dp, + CHAR(3) currency,
// A11 audit G9) and is rendered — never parsed into a float, never recomputed
// (CLAUDE.md rule 2).
//
// THE THREE PRECISION BOUNDARIES (BR-TEN-080, PO 2026-08-12, OQ-159 + OQ-186):
//   STORAGE 6 dp — NUMERIC(18,6), unchanged, hard rule 2 and B2's signed DDL.
//   API      4 dp — so no computed precision is lost in transit.
//   DISPLAY  2 dp — what a person reads. THIS FILE IS THAT BOUNDARY.
// A tax line computing to 8.2985 travels as "8.2985" and reads $8.30 here.
//
// WHY THIS CELL NOW TRIMS, WHEN IT USED TO REFUSE TO. Until DEF-088 this
// function asked Intl for `max(2, fraction.length)` places on the stated
// principle that "the SERVER rounds money for display — this cell NEVER
// rounds", and showed an over-precise figure rather than hiding it. That was
// answered by the PO on 2026-08-12: the wire deliberately carries 4 dp, so
// there is nothing anomalous left to surface, and a customer was being shown
// $8.2985 — a working figure, not a price (DEF-088, PO verbatim: "Currently UI
// is howing 4 decimals on screen"). Display trimming is NOT a second rounding
// site in the money math: the ledger still REFUSES a posting past 2 dp rather
// than rounding it (BR-LED-025), finalization still rounds exactly once (B4 ❄️),
// and nothing here is ever written back — this is the last inch before a pair
// of eyes. It is done in ONE place (BR-SHL-023) so no component can round for
// itself and no two screens can disagree.
//
// HOW, WITHOUT FLOATS. Intl.NumberFormat V3 takes the decimal STRING and
// rounds on its exact mathematical value, so "8.005" → $8.01. Any path through
// Number()/toFixed renders $8.00, because 8.005 as an IEEE-754 double is
// 8.00499999999999989 — MoneyCell.test.tsx asserts that case as the float
// detector. `roundingMode: "halfExpand"` is half-away-from-zero, which is
// B4.4's finance-signed half-up (Python's decimal.ROUND_HALF_UP) — the display
// applies the SAME convention the backend applies at finalization, stated
// explicitly rather than inherited from an engine default.
//
// The optional `basis` prop renders the BR-REP-001 date-basis label so no
// money number ships unlabeled where the consuming screen declares one.
// `locale` is the tenant's Regional number format (IS-8); the real value is
// fed by US-SHL-013's formatting-service wiring — the prop exists so zero
// per-screen format code is ever written. Locale changes the separators and
// the symbol, never the count: 2 dp in en-US, 2 dp in de-DE.
import { Component } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import "./MoneyCell.css";

/** The date basis a money figure is read on, LABELLED beside it — `BR-REP-001`
 *  (PO ruling 2026-08-08): billing-side numbers read the POSTING date, cash and
 *  bank-side numbers read the CLEARING date, and **no unlabelled money number
 *  ships anywhere**.
 *
 *  ⚠ **`priced` IS A THIRD VALUE AND IT FILLS A GAP THE SIGNED RULE NEVER
 *  ADDRESSED — `DEF-RBS-4350`.** That rule maps two KINDS of number onto two
 *  dates, and when it was signed nothing in the product produced a third kind:
 *  an amount that has been **worked out and never entered in the books**. A
 *  runbook's test bill is exactly that — its own result screen says *"Nothing
 *  was written and no bill number was used"* two inches under a strip that was
 *  labelling the total **Posting date**.
 *
 *  Neither signed mapping is touched: billing-side is still posting, cash-side
 *  is still clearing, and the rule's purpose — no unlabelled money number — is
 *  better served, not weakened. Recorded in the decision log rather than put to
 *  the Product Owner, because nothing is being reversed (hard-won law 13). */
export type MoneyBasis = "posting" | "clearing" | "priced";

// Until the tenant Regional settings feed arrives (US-SHL-013 service wiring),
// consumers that pass no locale get the en-US seed format.
export const DEFAULT_MONEY_LOCALE = "en-US";

// BR-TEN-080: what a person reads is 2 decimals, everywhere, in every locale.
export const MONEY_DISPLAY_DECIMALS = 2;

/**
 * **FOUR — a tariff RATE is a third kind of number (OQ-620(a), PO 2026-08-27).**
 *
 * PO verbatim: *"What does a tariff rate show? Four ($0.1420). A rate is not
 * money and not a quantity - 4 decimal places"*.
 *
 * ⚠ **THIS DOES NOT CHANGE `MONEY_DISPLAY_DECIMALS` AND MUST NOT BE READ AS
 * CHANGING IT.** Money is still 2 (`$64.57`) and a quantity is still at most 2
 * with its zeros TRIMMED (`5 kgal`, `UnitCell`). Three kinds, three rules, and
 * all three produce a well-formed string from the same stored `8.290000` —
 * `$8.29`, `8.29` and `$8.2900` — which is why reaching for the wrong one is
 * invisible.
 */
export const RATE_DISPLAY_DECIMALS = 4;

/**
 * **…AND AT LEAST TWO — UNIT PRICES UP TO 4 DECIMALS, TOTALS AT 2 (PO ruling
 * 2026-10-02, verbatim: *"Show unit prices with up to 4 decimals and keep
 * every total at 2."*).** This NARROWS the 4-places-zeros-kept reading of
 * OQ-620(a) above: a per-unit PRICE (a rate, a tier price, a per-unit charge)
 * shows as many decimals as it carries, up to four, and the zeros after the
 * second are dropped — `$0.0425`, `$0.10`, `$12.50`, and `$8.29` where this
 * printed `$8.2900`. Four is still the ceiling (`RATE_DISPLAY_DECIMALS`) and
 * two is the floor, so a price never reads with fewer places than money does.
 *
 * Shown to the PO: a water schedule at `$0.0425` per gallon read `$0.04` under
 * the 2-decimal rule, which over 10,000 gallons reads as `$400.00` against the
 * `$425.00` actually billed. Every AMOUNT — a line total, a bill total, a
 * balance, a minimum, a base charge — stays `formatMoney`'s 2. Display only:
 * storage and the arithmetic are untouched.
 */
export const RATE_MIN_DISPLAY_DECIMALS = MONEY_DISPLAY_DECIMALS;

const DECIMAL_STRING_RE = /^-?\d+(\.\d+)?$/;

/** The number format the WIRE uses — `.` as the decimal mark, no grouping.
 *  Used by `formatMoneyInput` alone, and it is not the tenant's Regional
 *  format on purpose: see that function. */
const WIRE_NUMBER_LOCALE = "en-US";

// ES2023 Intl.NumberFormat accepts decimal STRINGS (the "mathematical value"
// path) and takes `roundingMode` — the amount never passes through
// Number()/float (CLAUDE.md rule 2). The shipped TS lib (ES2022) types
// format() as number-only and has no roundingMode, so both are surfaced by
// these two narrow declarations, not by a value cast.
interface DecimalStringFormatter {
  format(value: string): string;
}

interface MoneyFormatOptions extends Intl.NumberFormatOptions {
  // "halfExpand" = ties away from zero = B4.4's half-up.
  roundingMode?: "halfExpand";
}

/**
 * THE REFUSAL (DEF-151, 2026-08-16). A money renderer cannot render an absence.
 *
 * `apps/ledger/wire.py` serves `written_off_ytd: null` on every deployment, the
 * frontend type said `string`, and the null arrived here. It missed
 * `DECIMAL_STRING_RE`, took the "malformed amount renders verbatim" branch
 * below, and a finance officer read the literal text **`null USD`** on S36 — a
 * word where a figure belongs, beside five tiles that said *Not available* with
 * a reason. That verbatim fallback is right for a malformed amount (`"12.3.4"`
 * beats `NaN`); it is exactly wrong for an ABSENT one.
 *
 * So absence is refused at the boundary instead. The reason it is a THROW and
 * not a quiet dash: rendering an absence requires a REASON, and this component
 * has none to give — `financeShared.AbsentFigure` makes `reason` a required prop
 * precisely so that "render an absence silently" is unexpressible, and a
 * MoneyCell that invented a dash here would be the second, silent path around
 * that rule. A screen holding a nullable figure must branch BEFORE it gets here.
 *
 * The type is the first line of defence and this is the backstop: `tsc` now
 * refuses `string | null` at every call site, and this catches the case where a
 * type once again turns out to be narrower than the wire — loudly, in the tests
 * and in the browser console, rather than as a word on a finance screen.
 */
export class MoneyAmountAbsent extends Error {
  constructor(currency: string) {
    super(
      `MoneyCell was handed an absent amount for ${currency}. A figure the books ` +
        `will not state is rendered by AbsentFigure WITH its reason — never as ` +
        `money, and never as a zero (DEF-151).`,
    );
    this.name = "MoneyAmountAbsent";
  }
}

/**
 * THE TEST A CALLER MUST MAKE BEFORE IT GETS HERE (DEF-176, 2026-08-16).
 *
 * `MoneyAmountAbsent` above says *"a screen holding a nullable figure must
 * branch BEFORE it gets here"*. Every screen did — and one of them branched on
 * `=== null`, which is not the same question.
 *
 * `apps/ledger/wire.py` OMITTED `tax` and `collected` from each row of S36's
 * Revenue-by-service table while `endpoints.ts` declared both as members. An
 * absent key reads `undefined`, `undefined === null` is false, the branch chose
 * the money path, and the refusal above threw — so React Router replaced the
 * ENTIRE Finance route with its error boundary. **A column that should have read
 * "—" killed the page.**
 *
 * So the question a caller asks is *"did a figure arrive?"* and not *"is this
 * value null?"*, and it is asked in ONE place so no screen can ask it its own
 * way. The predicate narrows, so the else-branch types as `string` and `tsc`
 * still refuses a nullable amount at the call site — this is the belt beside
 * that brace, not a replacement for it.
 */
export function isAmountAbsent(
  amount: string | null | undefined,
): amount is null | undefined {
  return amount === null || amount === undefined;
}

export function formatMoney(
  amount: string,
  currency: string,
  locale: string = DEFAULT_MONEY_LOCALE,
): string {
  // Guarded at runtime as well as in the type: DEF-151 is what a served null
  // does when only the type was asked. The widening cast is deliberate — the
  // declared type already forbids this, and the whole point of the check is the
  // case where the declared type turns out to be a claim rather than a fact.
  const supplied = amount as string | null | undefined;
  if (supplied === null || supplied === undefined) {
    throw new MoneyAmountAbsent(currency);
  }
  if (!DECIMAL_STRING_RE.test(amount)) {
    // A malformed amount renders verbatim with its code — never NaN, never a
    // client-side guess at what the server meant.
    return `${amount} ${currency}`;
  }
  try {
    const options: MoneyFormatOptions = {
      style: "currency",
      currency, // CHAR(3) code rides WITH the amount — never assumed (B2)
      // BR-TEN-080: exactly 2 dp on screen. min == max, so "148.6" pads to
      // "$148.60" and "8.2985" trims to "$8.30" — one rule, both directions.
      minimumFractionDigits: MONEY_DISPLAY_DECIMALS,
      maximumFractionDigits: MONEY_DISPLAY_DECIMALS,
      // B4.4 ❄️ half-up, over the decimal string's exact value (see header).
      roundingMode: "halfExpand",
    };
    const formatter = new Intl.NumberFormat(locale, options) as unknown as DecimalStringFormatter;
    return formatter.format(amount);
  } catch {
    // Unknown currency code (RangeError) — verbatim beats a crashed screen.
    return `${amount} ${currency}`;
  }
}

/**
 * **THE SAME FIGURE, SHAPED FOR AN INPUT BOX: exactly 2 decimals, no symbol,
 * no grouping and no locale (`DEF-CUS-4999` / `DEF-CUS-5008`, 2026-09-12).**
 *
 * `formatMoneyInput("2410.000000")` -> `"2410.00"` ·
 * `formatMoneyInput("247.300000")` -> `"247.30"` ·
 * `formatMoneyInput("8.005")` -> `"8.01"`.
 *
 * **WHY IT IS HERE AND NOT AT THE CALL SITE.** S22's Record payment modal
 * pre-filled its amount box with the raw served column — `247.300000` — and a
 * clerk accepting that default sent six decimals to
 * `POST /accounts/{id}/payments` on the common path. `formatMoney` cannot be
 * used for it: a box a person types into and a server parses may not carry
 * `$` or a thousands separator. Writing the trim at the call site instead
 * would be the second money-formatting path BR-SHL-023 forbids, so it lives
 * beside `formatMoney` and shares its every decision — the same
 * `DECIMAL_STRING_RE`, the same `MONEY_DISPLAY_DECIMALS`, the same
 * `roundingMode: "halfExpand"` (B4.4 ❄️ half-up), the same refusal to touch a
 * float.
 *
 * ⚠ **THE LOCALE IS PINNED TO THE WIRE'S AND IS NOT A PARAMETER, WHICH IS THE
 * OPPOSITE OF EVERY OTHER FUNCTION IN THIS FILE.** `formatMoney` takes the
 * tenant's Regional format because it renders for eyes; this renders a value
 * that goes BACK to the server, and `de-DE` would produce `2410,00` — which
 * the serializer refuses. Read-only money is localised; an editable amount is
 * not, and inviting a caller to pass a locale here would invite exactly that
 * bug.
 *
 * ⚠ **AN ABSENT AMOUNT IS THE EMPTY STRING, NOT A ZERO AND NOT A THROW.** This
 * is the initial value of a REQUIRED field: an empty box asks the clerk for
 * the figure, where `0.00` would be a number nobody read off a cheque and
 * which submits cleanly. `formatMoney`'s refusal (`MoneyAmountAbsent`) is
 * right for a cell and wrong here — a form cannot render "a figure did not
 * arrive" into a text input.
 *
 * A malformed amount is returned VERBATIM, exactly as `formatMoney` does, so
 * the clerk sees what the server actually sent rather than a client's guess at
 * what it meant.
 */
export function formatMoneyInput(amount: string | null | undefined): string {
  if (isAmountAbsent(amount)) {
    return "";
  }
  if (!DECIMAL_STRING_RE.test(amount)) {
    return amount;
  }
  try {
    const options: MoneyFormatOptions = {
      style: "decimal",
      minimumFractionDigits: MONEY_DISPLAY_DECIMALS,
      maximumFractionDigits: MONEY_DISPLAY_DECIMALS,
      useGrouping: false,
      roundingMode: "halfExpand",
    };
    const formatter = new Intl.NumberFormat(
      WIRE_NUMBER_LOCALE,
      options,
    ) as unknown as DecimalStringFormatter;
    return formatter.format(amount);
  } catch {
    return amount;
  }
}

/**
 * **A UNIT PRICE: up to four decimals, at least two (PO ruling 2026-10-02 —
 * *"Show unit prices with up to 4 decimals and keep every total at 2."*).**
 *
 * `formatRate("0.042500", "USD")` -> `"$0.0425"` ·
 * `formatRate("0.142000", "USD")` -> `"$0.142"` ·
 * `formatRate("0.100000", "USD")` -> `"$0.10"` ·
 * `formatRate("12.5", "USD")` -> `"$12.50"` ·
 * `formatRate("0.14205", "USD")` -> `"$0.1421"` (half-up at the fourth).
 *
 * ⚠ **SUPERSEDES THE ZEROS-KEPT HALF OF OQ-620(a) (2026-08-27), NOT ITS
 * PRECISION.** That ruling put a rate at four places with its zeros kept
 * (`$8.2900`); this one keeps the four places a price CARRIES and drops the
 * zeros after the second. What OQ-620(a) protected still holds: a rate is
 * never cut to money's two, because `$0.0425` read as `$0.04` prints a figure
 * that cannot reproduce the line it priced.
 *
 * ⚠ **IT IS STILL NOT `formatQuantity`.** A quantity trims to `5 kgal`; a
 * price never reads with fewer than two places (`$5.00`, never `$5`).
 *
 * Everything else is `formatMoney`'s behaviour and is deliberately shared with
 * it: the decimal STRING never becomes a float (a `NUMERIC(18,6)` rate can
 * exceed a double), the currency code rides WITH the value and is never
 * assumed, half-up matches B4's direction, and a malformed value or an unknown
 * currency renders verbatim rather than crashing a screen.
 *
 * ⚠ **NEVER REACH FOR THIS ON A LINE AMOUNT.** An amount is money and has
 * CLAUDE.md hard rule 2; `$64.5700` is wrong in the same way `8.00 kgal` is.
 */
export function formatRate(
  rate: string,
  currency: string,
  locale: string = DEFAULT_MONEY_LOCALE,
): string {
  const supplied = rate as string | null | undefined;
  if (supplied === null || supplied === undefined) {
    throw new MoneyAmountAbsent(currency);
  }
  if (!DECIMAL_STRING_RE.test(rate)) {
    return `${rate} ${currency}`;
  }
  try {
    const options: MoneyFormatOptions = {
      style: "currency",
      currency,
      // 2026-10-02 ruling: min 2, max 4. "12.5" pads to "$12.50", "0.0425"
      // keeps all four, "8.290000" drops to "$8.29" and "0.14205" rounds
      // half-up to "$0.1421" — Intl drops the zeros between the two bounds.
      minimumFractionDigits: RATE_MIN_DISPLAY_DECIMALS,
      maximumFractionDigits: RATE_DISPLAY_DECIMALS,
      roundingMode: "halfExpand",
    };
    const formatter = new Intl.NumberFormat(locale, options) as unknown as DecimalStringFormatter;
    return formatter.format(rate);
  } catch {
    return `${rate} ${currency}`;
  }
}

/**
 * **THE SAME UNIT PRICE WHERE NO CURRENCY TRAVELS WITH IT** — `formatRate`'s
 * every decision (2 to 4 places, half-up, the decimal string never a float)
 * with no symbol: `formatRateNumber("0.002500")` -> `"0.0025"`.
 *
 * For a sentence whose catalogue entry carries no symbol and whose row carries
 * no currency — the Taxes list's *"0.0025 per kWh"*, beside the server's own
 * *"5.00 per bill"* — where inventing a currency would break hard rule 2
 * (a currency is served, never assumed). Before 2026-10-02 that cell printed
 * the six stored places, `0.002500 per kWh`.
 */
export function formatRateNumber(rate: string, locale: string = DEFAULT_MONEY_LOCALE): string {
  if (!DECIMAL_STRING_RE.test(rate)) {
    return rate;
  }
  try {
    const options: MoneyFormatOptions = {
      style: "decimal",
      minimumFractionDigits: RATE_MIN_DISPLAY_DECIMALS,
      maximumFractionDigits: RATE_DISPLAY_DECIMALS,
      roundingMode: "halfExpand",
    };
    const formatter = new Intl.NumberFormat(locale, options) as unknown as DecimalStringFormatter;
    return formatter.format(rate);
  } catch {
    return rate;
  }
}

export interface MoneyCellProps {
  amount: string; // decimal string from the API — never a number
  currency: string; // ISO 4217 CHAR(3), served with the amount
  locale?: string; // tenant Regional number format (IS-8)
  basis?: MoneyBasis; // BR-REP-001: label where the screen declares one
}

function MoneyAmount(props: MoneyCellProps) {
  const { t } = useTranslation();
  return (
    <span className="cell-money">
      <span className="cell-money-amount">
        {formatMoney(props.amount, props.currency, props.locale)}
      </span>
      {props.basis !== undefined && (
        // BR-REP-001: posting vs clearing named right beside the figure.
        <span className="cell-money-basis">{t(`cells.basis.${props.basis}`)}</span>
      )}
    </span>
  );
}

/** What a contained failure renders. Never money, never a zero, never `null` —
 *  one sentence saying a figure did not arrive, from the catalogues like every
 *  other sentence in this product. `role="note"` matches `AbsentFigure`: this
 *  is a stated absence, not an alert that just fired. */
function MoneyUnrenderable() {
  const { t } = useTranslation();
  return (
    <span className="cell-money cell-money-unrenderable" role="note">
      {t("cells.money.unrenderable")}
    </span>
  );
}

/**
 * ⚠ THE BLAST RADIUS OF THE REFUSAL ABOVE, BOUNDED TO ONE CELL (DEF-176).
 *
 * DEF-151 made this component REFUSE an absent amount, and that reasoning is
 * right and stays. What it did not account for is the second-order effect, and
 * it is the general lesson worth keeping from DEF-176:
 *
 *   **Hardening a renderer to refuse bad input converts every unguarded caller
 *   from a cosmetic defect into an outage.**
 *
 * `MoneyCell` is called from 60+ files. Before DEF-151 an unguarded one printed
 * a wrong cell; after it, an unguarded one throws during render, React unwinds
 * to the nearest boundary — and `App.tsx` builds the app with
 * `createBrowserRouter`, whose nearest boundary is the ROUTE. So one bad figure
 * in one table cell replaced the entire Finance screen with *"Unexpected
 * Application Error!"*: no sidebar, no tabs, no page. **A wrong tile became a
 * dead page, which is strictly worse than the defect it fixed.**
 *
 * This boundary is what makes that trade one-directional. The refusal still
 * happens, the error still reaches the console and still fails
 * `renderToStaticMarkup` in the tests (React's server renderer does not run
 * error boundaries, which is deliberate here — a null in a unit test must still
 * go RED), and a live screen loses ONE CELL instead of everything.
 *
 * **It is containment, NOT a licence to stop branching.** A caller that knows a
 * figure can be absent still owes the reader a REASON — `financeShared.
 * AbsentFigure` with the server's own gap sentence — and this fallback cannot
 * give one, because at this depth there is nothing to give. Landing here is
 * always a defect; it is just no longer an outage.
 */
class MoneyBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  override state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  override componentDidCatch(error: Error): void {
    // LOUD, always. A contained failure that logged nothing would be this
    // boundary quietly becoming the "render an absence silently" path that
    // `AbsentFigure`'s required `reason` exists to make unexpressible.
    console.error(
      "MoneyCell could not render a figure and the cell was contained (DEF-176). " +
        "The CALLER must branch on an absent amount and render AbsentFigure with its " +
        "reason — this fallback has no reason to give.",
      error,
    );
  }

  override render(): ReactNode {
    return this.state.failed ? <MoneyUnrenderable /> : this.props.children;
  }
}

export function MoneyCell(props: MoneyCellProps) {
  return (
    <MoneyBoundary>
      <MoneyAmount {...props} />
    </MoneyBoundary>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-013@1e89ecb (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope) · [2026-08-15 DEF-088 display-precision lane] RED PROVED FIRST — the S30 tax line rendered `<span class="cell-money-amount">$8.2985</span>` and all 6 new assertions failed against the pre-fix formatter (verbatim in the lane report). MEASURED, THIS LANE'S OWN FILES ONLY: MoneyCell.test.tsx 8 tests (was 6) · BillDetailPage.test.tsx 22 tests / 3 skipped (was 20 / 3) · PaymentsPage.test.tsx 17 tests (was 15) — 44 passed / 3 todo across the three, all green. The FULL suite total is deliberately not quoted: a concurrent 07-frontend settings lane was adding files throughout, so no whole-suite number here would be reproducible. tsc --noEmit✔ · eslint --max-warnings 0✔ · vite build✔ · node --test server.test.mjs 10/10✔ · tsc -p tsconfig.e2e.json✔ · run_gates: 20 PASS · 0 FAIL at this lane's 17:55 baseline; the failures present at hand-off are named in the lane report and none is this lane's — no file it touched appears in any of them
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
