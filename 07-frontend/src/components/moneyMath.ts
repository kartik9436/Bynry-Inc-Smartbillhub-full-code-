// Story:    DEF-LED-6717 (the Revenue-by-service table and its own Total line
//           were struck on two different bases) · B14 rule 43 (a piece of UI is
//           built as a COMPONENT; standalone code inside a page is not reuse)
// Rules:    CLAUDE.md hard rule 2 — money is stored to 4 decimals, displayed 2,
//           and NEVER float.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY A TABLE FOOTS TO ITSELF, AND WHY THAT NEEDS ARITHMETIC RATHER THAN A KPI
// ══════════════════════════════════════════════════════════════════════════
// The Revenue-by-service table printed a **Total** line taken from
// `report.kpis.billed`. Both figures are right and they answer two different
// questions: the rows sum movement on the tenant's REVENUE accounts, and
// `kpis.billed` sums AR DEBITS from invoice-sourced entries. On books written
// entirely by the bill run they agree, so this survived every test. On a
// hand-typed journal entry they do not, and on 2026-09-25 the Product Owner
// photographed a table whose single row read `$50.00` above a Total of `$0.00`.
//
// CLAUDE.md records the resolution of exactly this shape in its `NFR-3`
// paragraph: a total and the rows under it are **the same aggregate over the
// same filtered set**, one of them windowed. So the Total is summed FROM THE
// ROWS, over everything the search and the filters kept — never from a
// neighbouring figure that happens to be close.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY `BigInt` AND NOT `Number`
// ══════════════════════════════════════════════════════════════════════════
// Hard rule 2 forbids float for money and gives no exception for a subtotal a
// screen works out for itself. `0.1 + 0.2` is the whole argument. Every amount
// on the wire is a fixed-point decimal STRING; this scales each to an integer
// number of ten-thousandths, adds exactly, and prints the string back. Nothing
// here ever holds a `number`.
//
// The scale is 4 because that is what hard rule 2 says money is WRITTEN to. An
// amount carrying more than 4 decimals is a wire contract violation rather than
// a rounding question, and it is REFUSED here (see below) instead of being
// quietly truncated — a screen that silently drops a digit of money is the
// defect this module exists to end, one layer down.

/**
 * The scale hard rule 2 WRITES money at. It is **not** a ceiling on what may be
 * added here, and the difference cost this module a rewrite before it shipped.
 *
 * ⚠ **THE WIRE SERVES SIX DECIMALS, NOT FOUR.** `apps/ledger/wire.money` is
 * fed out of `NUMERIC(18,6)` columns, which hard rule 2 keeps lawful as
 * containers even though the rule now governs writes at four. A first draft of
 * this file REFUSED anything past four and threw on the very first real
 * response it met — a guard that is incapable of passing (hard-won law 7's
 * third shape) dressed up as strictness. So the sum below is exact at whatever
 * scale it is HANDED, and this constant is the floor the result is padded to.
 */
export const MONEY_SCALE = 4;

const AMOUNT_RE = /^-?\d+(\.\d+)?$/;

/**
 * Thrown when an amount cannot be added exactly.
 *
 * It THROWS rather than returning a fallback, for `MoneyCell.formatMoney`'s own
 * reason: a money figure that silently becomes `0.00`, `NaN` or a truncated
 * value is worse than a page that says it could not do the sum. Nothing here is
 * ever rounded on the way in — a digit of money is never dropped quietly.
 */
export class MoneyAmountUnaddable extends Error {
  readonly amount: string;
  constructor(amount: string) {
    super(`money amount cannot be added exactly: ${JSON.stringify(amount)}`);
    this.name = "MoneyAmountUnaddable";
    this.amount = amount;
  }
}

/** How many decimal places this amount actually carries. */
export function amountScale(amount: string): number {
  const text = amount.trim();
  if (!AMOUNT_RE.test(text)) {
    throw new MoneyAmountUnaddable(amount);
  }
  const dot = text.indexOf(".");
  return dot === -1 ? 0 : text.length - dot - 1;
}

/** One fixed-point decimal string → an integer at `scale` places, exactly. */
export function scaledAmount(amount: string, scale: number): bigint {
  const own = amountScale(amount);
  if (own > scale) {
    // Scaling DOWN would drop a digit of money. Every caller here scales up.
    throw new MoneyAmountUnaddable(amount);
  }
  const text = amount.trim();
  const negative = text.startsWith("-");
  const digits = (negative ? text.slice(1) : text).replace(".", "");
  const value = BigInt(digits + "0".repeat(scale - own));
  return negative ? -value : value;
}

/** An integer at `scale` places → the fixed-point decimal string back. */
export function unscaledAmount(value: bigint, scale: number): string {
  const negative = value < 0n;
  const digits = (negative ? -value : value).toString().padStart(scale + 1, "0");
  const whole = digits.slice(0, digits.length - scale);
  const fraction = digits.slice(digits.length - scale);
  return `${negative ? "-" : ""}${whole}${scale === 0 ? "" : `.${fraction}`}`;
}

/**
 * Σ of fixed-point decimal amounts, exactly, as a fixed-point decimal string.
 *
 * The result carries the WIDEST scale it was handed (at least `MONEY_SCALE`),
 * so adding six-decimal wire amounts gives a six-decimal answer and nothing is
 * rounded anywhere on this path. `MoneyCell` is the one place a money figure
 * becomes two decimals, and it stays that way.
 *
 * An empty list sums to `"0.0000"` and not to `null`: a filter that keeps no
 * rows has a total, and it is zero. *"Nothing matched"* is the TABLE's sentence
 * (its empty state), not the total line's.
 */
export function sumAmounts(amounts: readonly string[]): string {
  const scale = amounts.reduce((widest, amount) => Math.max(widest, amountScale(amount)), MONEY_SCALE);
  let total = 0n;
  for (const amount of amounts) {
    total += scaledAmount(amount, scale);
  }
  return unscaledAmount(total, scale);
}

/**
 * **THE FIGURE A CLERK'S AMOUNT BOX STARTS AT — `DEF-RAT-9807`.** An *entered
 * when used* charge code may carry a default (`BR-RAT-1054` AMENDED
 * 2026-10-06), served as a 4- or 6-place string (`"10.0000"`, `"8.937500"`).
 * The box shows it the way a clerk would type it: trailing zeros past two
 * places dropped, never rounded — `"10.0000"` → `"10.00"`, `"8.937500"` →
 * `"8.9375"`, `"0.1000"` → `"0.10"` (hard rule 2: a unit price shows up to
 * four places, as many as it carries). Null, undefined or empty → `""`, an
 * empty box, which is exactly today's behaviour for a code with no default.
 * Pure string work: no float ever touches the figure.
 */
export function startingAmount(value: string | null | undefined): string {
  const raw = (value ?? "").trim();
  if (raw === "") return "";
  const match = /^(-?\d+)(?:\.(\d*))?$/.exec(raw);
  if (match === null) return raw;
  let frac = (match[2] ?? "").replace(/0+$/, "");
  if (frac.length < 2) frac = frac.padEnd(2, "0");
  return `${match[1]}.${frac}`;
}

/**
 * **A FIGURE MOVED BY A PERCENTAGE, EXACTLY, AT MONEY'S STORED FOUR PLACES**
 * (`CR-179-BRC10` — the report framework's *Change all prices by* shortcut
 * fills each proposed box from its "now" figure).
 *
 * `scaleByPercent("8.50", "5")` → `"8.9250"` · `scaleByPercent("0.105", "-10")`
 * → `"0.0945"` · `scaleByPercent("14.00", "2.5")` → `"14.3500"`.
 *
 * Integer arithmetic on the decimal strings, rounded half away from zero at
 * the fourth place (hard rule 2: stored to 4, never a float). Display is the
 * caller's — a money box shows 2, a unit price up to 4.
 */
export function scaleByPercent(amount: string, percent: string): string {
  const scale = Math.max(amountScale(amount), MONEY_SCALE);
  const value = scaledAmount(amount, scale);
  const percentScale = amountScale(percent);
  const moved = scaledAmount(percent, percentScale);
  const hundred = 100n * 10n ** BigInt(percentScale);
  const numerator = value * (hundred + moved);
  const denominator = hundred * 10n ** BigInt(scale - MONEY_SCALE);
  let quotient = numerator / denominator;
  const remainder = numerator % denominator;
  const magnitude = remainder < 0n ? -remainder : remainder;
  if (2n * magnitude >= denominator) {
    quotient += numerator < 0n ? -1n : 1n;
  }
  return unscaledAmount(quotient, MONEY_SCALE);
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-LED-6717 (PO, deployed v2.351.84, Finance → Revenue & AR → Services) · CLAUDE.md hard rule 2 · CLAUDE.md NFR-3 paragraph · B14 rules 43
// generated: 2026-09-25 by lane REV (maintenance, 12-governance/22-product-maintenance-process.md)
// checklist: A=n/a(no endpoint) B=n/a C✔ D=n/a E✔(RevenueByServiceTable) F✔ G✔ H=n/a
// gates: RED PROVED FIRST — revenueByServiceFoots.test.tsx asserted the rendered rows sum to the stated total and FAILED on the shipped page (expected "50.00", received "0.00") before this module existed; the verbatim failure is in the lane report.
// exceptions: (1) the result carries the WIDEST scale it was handed rather than a fixed four — the wire serves six decimals out of NUMERIC(18,6) and a fixed-four sum threw on the first real response it met, which is a guard incapable of passing (hard-won law 7); rounding to two is `MoneyCell`'s job and stays there
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
