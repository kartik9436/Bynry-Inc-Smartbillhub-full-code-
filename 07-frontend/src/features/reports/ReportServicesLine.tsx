// ── Trace ──────────────────────────────────────────────
// Change:   DEF-REP-7010 — the Billing Register's SERVICES column, reported by
//           the Product Owner from the deployed build (`v2.380.3`, screen
//           `RPT-02`, `/{tenant}/reports/billing-register`): the same six words
//           — `battery · fire · sewer · solar · trash · water` — repeated
//           verbatim on all 41 rows, in about a quarter of the table's width,
//           wrapping every row onto two lines.
//           Screens: `RPT-02`/`S46` (the report viewer) and every report that
//           serves a `services` column.
// Rules:    The rule the PO agreed, verbatim from the change: *"collapse to a
//           single line ABOVE the table when every row matches, otherwise chips
//           per row"* — never *remove the column* ·
//           B14 rule 43 (a piece of UI is built as a COMPONENT; standalone code
//           inside a page is not reuse — which is why this is a file and not
//           forty lines inside a 4,000-line viewer) ·
//           B14 rule 44 (our UI standard wins over the drawing, INCLUDING the
//           frame: 2·1b draws the services as plain text, the product's own
//           entity headers draw service CHIPS, and the standard decides) ·
//           B14 rule 33 (a LABEL is ≤ 3 words and no sentence; RATIONALE is
//           ZERO words on screen — this line never explains why it collapsed) ·
//           B14 rule 31 (a chip shows the service's NAME, never its code) ·
//           B14 rule 21 (Tailwind utilities, no stylesheet class — this file is
//           registered in `styles/route-b-migrated.txt`).
// Tests:    07-frontend/src/features/reports/reportServicesLine.dom.test.tsx ·
//           10-scripts/def_rep_7010_report_viewer_walkthrough.mjs (the browser
//           walk — hard-won law 6: no gate in this repo reads rendered output).
// ───────────────────────────────────────────────────────
/**
 * **`EVERY ROW   ▪ELECTRIC ▪FIRE ▪GAS ▪SEWER ▪TRASH ▪WATER`** — the services
 * a report's rows all carry, said ONCE, above the table.
 *
 * ╔════════════════════════════════════════════════════════════════════════╗
 * ║  WHY THIS IS NOT *"DROP THE COLUMN"*                                   ║
 * ╚════════════════════════════════════════════════════════════════════════╝
 *
 * A utility with six services bills all six on every account, so the column
 * repeats itself 41 times and tells a clerk nothing. A utility with a mixed
 * book does not, and there the column is the whole point — which service is
 * on this bill is the question the register is being read for. **So the same
 * report is two different screens depending on its data**, and the deciding
 * question is asked of the ROWS, not of the report key: see `uniformServices`.
 *
 * ⚠ **AND IT IS A FACT, NOT AN EXPLANATION.** The label is two words. It does
 * not say *"the services column was hidden because every row matched"* —
 * that is RATIONALE, which B14 rule 33 puts at zero words on screen, and this
 * docstring is where it belongs.
 *
 * ⚠ **IT HOLDS NO LIST OF SERVICES**, deliberately, and neither does
 * `ServiceChips` beneath it. A twelfth service needs nothing here: it keeps
 * its own text and takes `serviceBadge`'s neutral token. Hard-won law 2 and
 * the skill's §12 — the front end typed the service list out by hand in two
 * places and an eleventh service *failed silently*.
 */
import { ServiceChips } from "@/components/ServiceChips";
import type { ReportRow, ReportGroupRow } from "@/api/reportsEndpoints";
import { isReportGroupRow } from "@/api/reportsEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

/**
 * The one service list every FACT row carries — or `null` when they differ,
 * when there are none, or when this column is not a service list at all.
 *
 * Pure and exported, because *"otherwise chips per row"* is half the rule the
 * PO agreed and a rule proved in one direction only is half proved.
 *
 * ⚠ **GROUP ROWS ARE SKIPPED AND NEVER COUNTED AS A MISMATCH** (`P2.18`). A
 * subtotal row holds `__kind__`, `value`, `rows` and `subtotals` and no
 * `services` at all, so reading one as a fact row would make every grouped
 * report look mixed and collapse nothing, forever.
 *
 * ⚠ **ORDER IS PART OF *THE SAME*.** The server sorts a bill's services, so
 * two rows that agree arrive identical; comparing as SETS would let a screen
 * claim a match it cannot draw — the chips would have to be drawn in one of
 * the two orders and the other row's would then be wrong.
 *
 * ⚠ **AN EMPTY LIST IS A MISMATCH, NOT A MATCH.** A report whose every row
 * carries no services has nothing to say above the table, and drawing an
 * empty line there would be a heading promising something it has nothing to
 * put under it (`DEF-LED-6729`'s shape).
 */
export function uniformServices(
  rows: readonly (ReportRow | ReportGroupRow)[],
  column: string,
): string[] | null {
  let shared: string[] | null = null;
  let facts = 0;
  for (const row of rows) {
    if (isReportGroupRow(row)) {
      continue;
    }
    const value = (row as ReportRow)[column];
    if (!Array.isArray(value) || value.length === 0) {
      return null;
    }
    const codes = value.map((code) => String(code));
    if (shared === null) {
      shared = codes;
    } else if (shared.length !== codes.length || shared.some((code, at) => code !== codes[at])) {
      return null;
    }
    facts += 1;
  }
  return facts === 0 ? null : shared;
}

/**
 * The collapsed line, above the table.
 *
 * Renders nothing at all when there is nothing to collapse — the caller passes
 * `uniformServices`' answer straight through, so the two halves of the rule
 * cannot drift apart.
 */
export function ReportServicesLine(props: {
  /** `uniformServices`' answer. `null` draws nothing. */
  services: readonly string[] | null;
  t: Translator;
}) {
  if (props.services === null || props.services.length === 0) {
    return null;
  }
  return (
    <p
      className="mb-3 mt-0 flex flex-wrap items-center gap-x-3 gap-y-1.5"
      data-services-line=""
    >
      {/* A LABEL: two words, no sentence (B14 rule 33). The chips beside it
          finish the statement — *every row · electric · fire · …* — and
          nothing here says why the column is not in the table. */}
      <span className="font-heading text-xs font-semibold uppercase tracking-label text-neutral-600">
        {props.t("reports.services.everyRow")}
      </span>
      <ServiceChips services={props.services} t={props.t} />
    </p>
  );
}

export default ReportServicesLine;
