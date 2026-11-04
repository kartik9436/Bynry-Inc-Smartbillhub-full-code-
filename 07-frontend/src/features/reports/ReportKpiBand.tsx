// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 2 · P2.13 — *"A tile with no number says so."*
//          Built from `05-prototype/09 Reports Build Brief.pdf` p024 (2·1a, the
//          KPI band) and p012 (the P2.13 row), read as RENDERED IMAGES per
//          B14 rule 42 — never from the text layer.
// Rules:   BR-REP-024 (a figure that cannot be computed prints its REASON —
//          never 0, never "null") · BR-REP-033 / the `E·1` pattern (the tile
//          reads **Not counted yet** with the reason in its support text) ·
//          BR-REP-001 (every money KPI labels its date basis) ·
//          B14 rule 31 (nothing internal is ever a visible value) ·
//          B14 rule 32 (a stated absence is CLOSED by default) ·
//          B14 rule 43 (a piece of UI used twice is a COMPONENT).
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHAT WAS ON THE SCREEN ON 2026-09-23, AND WHY IT IS TWO FAULTS          ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// The brief walked all four canned reports on an empty book and counted the
// result: **"three of the four printed a false multi-currency sentence"** and
// **"one printed the internal code `currency_not_derivable` beneath it"**.
//
//   1 · **THE SENTENCE WAS FALSE.** A read model publishes the currency its
//       figures ARE, and publishes none in two different worlds — a book
//       holding more than one currency, and a book holding nothing at all.
//       Every tile read the second as the first. An empty book is the state
//       every new tenant is in on its first day, so the false sentence is the
//       one most clerks would have met first. Fixed at the source in
//       `apps/reports/queries._no_currency_reason`, because the screen cannot
//       know which world it is in and must not guess.
//
//   2 · **THE CODE WAS ON SCREEN.** `detail="currency_not_derivable"` rendered
//       under the tile as those exact twenty-three characters. That is B14
//       rule 31's shape one field over, and it is fixed by DELETING the detail
//       rather than by translating it: the `reason_code` already carries why.
//
// ⚠ **AND A THIRD, FOUND BY WALKING IT HERE RATHER THAN BY READING THE BRIEF:**
// the five band tiles sent their share as `"42.0"` and the screen printed
// `42.0` — a number with no unit, where the drawing reads `42%`. `detail_kind`
// now says what the figure is and this file renders the unit (CLAUDE.md rule 3
// in spirit: a quantity is never drawn without saying what it is a quantity
// of).
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHY IT IS `AbsentFigure` AND NOT A SENTENCE IN A `<span>`               ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// B14 rule 32 was written FROM this exact strip: three of S36's six tiles
// resolved to a reason, each printed a three-sentence paragraph inside a 180px
// tile, the row went ragged, and the Product Owner photographed it. The
// ratified shape is a closed disclosure — the label **Not counted yet** is the
// summary and the reason is one click away — and it already ships on `E·1`.
// The brief's own P2.13 row says so in terms: *"No design work is needed."*
import { AbsentFigure } from "@/components/AbsentFigure";
import { moneyDisplay } from "./reportsShared";
import { MoneyCell } from "@/components/MoneyCell";
import type { ReportKpi, ReportResponse } from "@/api/reportsEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

import "@/features/ledger/finance.css";

/**
 * The words under a tile's number, or null when there are none.
 *
 * Pure and exported so the `42%` decision is provable without a browser — and
 * so the one thing this component must never do again (render a raw internal
 * code) is a function with a test rather than a JSX branch nobody reads.
 *
 * ⚠ **A `detail` WITH NO `detail_kind` IS A STRING A CLERK MAY READ.** Today
 * that is the billing register's *"$14,208.55 billed"* sub-line. It is passed
 * through unchanged, which is what every existing tile expects.
 */
export function kpiDetailText(kpi: ReportKpi): string | null {
  if (kpi.detail === null || kpi.detail === "") {
    return null;
  }
  return kpi.detail_kind === "share" ? `${kpi.detail}%` : kpi.detail;
}

/**
 * Is this tile's sub-line a MONEY figure?
 *
 * ⚠ **THE BILLING REGISTER PRINTED `15734.170000` UNDER ITS *Bills* TILE** —
 * storage precision, six decimals, no currency code — because the sub-line was
 * a decimal string rendered with `String(...)`. CLAUDE.md hard rule 2 says money
 * is stored to four places and **DISPLAYS two**, and BR-SHL-023 says there is
 * one formatting path. So a money sub-line goes through `MoneyCell` like every
 * other money figure in the product, and `detail_kind` is how the server says
 * which ones those are.
 */
export function isMoneyDetail(kpi: ReportKpi): boolean {
  return kpi.detail_kind === "money";
}

/**
 * One tile.
 *
 * ⚠ **A NULL VALUE NEVER REACHES A MONEY FORMATTER.** `MoneyCell` would render
 * `null USD`, which is the production defect of 2026-08-16 by name. The branch
 * is structural: `value === null` returns before any formatting happens.
 */
export function ReportKpiTile(props: {
  kpi: ReportKpi;
  currency: string | null;
  basis: ReportResponse["basis"];
  t: Translator;
  locale?: string;
}) {
  const { kpi, t } = props;
  const label = t(`reports.kpi.${kpi.key}`, { defaultValue: kpi.key });
  const detail = kpiDetailText(kpi);
  return (
    <div className="kpi" data-kpi={kpi.key}>
      <span className="k">{label}</span>
      <span className="v">
        {kpi.value === null ? (
          // BR-REP-024 + BR-REP-033 — **Not counted yet**, with the reason in
          // the support text, closed. Never 0, never a dash, never "null".
          <AbsentFigure
            label={t("reports.kpi.notCounted")}
            reason={t(`reports.kpi.absent.${kpi.reason_code ?? "unknown"}`, {
              defaultValue: t("reports.kpi.absent.unknown"),
            })}
          />
        ) : kpi.kind === "money" && props.currency !== null ? (
          <MoneyCell
            amount={String(kpi.value)}
            currency={props.currency}
            basis={props.basis}
            locale={props.locale}
          />
        ) : kpi.kind === "percent" ? (
          // ⚠ **CLAUDE.md HARD RULE 2 — A PERCENTAGE IS STORED TO SIX AND
          // DISPLAYED TO TWO**, and until `P6.11` this branch did not exist:
          // the tile printed the wire value, so `100.000000` reached the
          // screen. Found by photographing it (hard-won law 6) and not by any
          // test. It is TRIMMED here and never rounded upstream — the wire
          // keeps all six, because a report that rounds before it is displayed
          // cannot be reconciled against the figure it came from.
          `${Number(kpi.value).toFixed(2)}%`
        ) : kpi.kind === "money" ? (
          // ⚠ **A MONEY TILE WHOSE CURRENCY THE REPORT COULD NOT DERIVE STILL
          // READS TWO DECIMALS** (`DEF-REP-6902`). It is shown bare rather than
          // wearing a code it did not come from (`DEF-081` / `DEF-099`) — that
          // half is unchanged. What was wrong is that falling out of the money
          // branch also fell out of the FORMATTING: the tax remittance's DUE
          // BILLED tile printed `531.140000` in front of a clerk. CLAUDE.md
          // hard rule 2 counts digits; it does not ask whether a symbol is
          // available.
          moneyDisplay(String(kpi.value))
        ) : (
          // A count. Shown as it arrived.
          String(kpi.value)
        )}
      </span>
      {detail === null ? null : (
        <span className="d">
          {isMoneyDetail(kpi) && props.currency !== null ? (
            <MoneyCell amount={detail} currency={props.currency} locale={props.locale} />
          ) : isMoneyDetail(kpi) ? (
            // `DEF-REP-6841`'s sub-line, on a report with no derivable
            // currency — the same inch as the VALUE above.
            moneyDisplay(detail)
          ) : (
            detail
          )}
        </span>
      )}
    </div>
  );
}

/** The strip. Nothing at all when the report declares no tiles — the billing
 *  register's 2·1b drawing is a table with no KPI band, and an empty grid would
 *  leave a band of whitespace where the drawing has none. */
export function ReportKpiBand(props: {
  kpis: readonly ReportKpi[];
  currency: string | null;
  basis: ReportResponse["basis"];
  t: Translator;
  locale?: string;
}) {
  if (props.kpis.length === 0) {
    return null;
  }
  return (
    // ── `DEF-REP-7013` · THE BAND IS COMPACT ON A REPORT ────────────────────
    //
    // ⚠ **THE PRODUCT OWNER KEPT THE EMPTY TILE AND ASKED FOR A SHORTER
    // BAND**, in as many words: *"Keep the empty one — it is honest — but
    // make the band compact."* So nothing is removed: four tiles, one of them
    // still reading **Not counted yet** with its reason a click away
    // (`BR-REP-024` / `BR-REP-033`). What changes is the air around them —
    // 114px of band above the first row of a 39-row register.
    //
    // ⚠ **IT IS TIGHTER SPACING AND NOT A NEW TYPE SCALE.** The label, the
    // value and the sub-line keep `KPIStrip.css`'s own sizes, which are the
    // ruled steps (`--text-xs`, `--text-metric`, `--text-sm`) — shrinking a
    // KPI value for one screen is the *"six different table font sizes"* this
    // repo already paid for once. Only `padding` and `gap` move, from
    // `16px/8px` to `10px/4px`.
    //
    // ⚠ **THE OVERRIDES ARE UTILITIES AND NOT A STYLESHEET CLASS (B14 rule
    // 21), AND THEY WIN ON SPECIFICITY RATHER THAN ON ORDER.** `[&_.kpi]:…`
    // compiles to `.<utility> .kpi`, two class selectors against
    // `KPIStrip.css`'s one — so this is true wherever the bundler happens to
    // put the two files, which a same-specificity override would not be
    // (hard-won law 7: a check, or a rule, that passes by luck).
    //
    // ⚠ **THE SHARED `.kpi` IS UNTOUCHED, DELIBERATELY.** 137 screens mount a
    // KPI strip; retuning the kit's own tile on one report's authority is the
    // move B14 rule 44's own reasoning warns about. If every band should be
    // this tight, that is a ruling for all of them at once.
    <div className="kpi-grid mb-3 [&_.kpi]:gap-1 [&_.kpi]:py-2.5">
      {props.kpis.map((kpi) => (
        <ReportKpiTile
          key={kpi.key}
          kpi={kpi}
          currency={props.currency}
          basis={props.basis}
          t={props.t}
          locale={props.locale}
        />
      ))}
    </div>
  );
}
