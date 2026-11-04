/**
 * SizeBreakdown — the size × count × base a capacity bill line was priced from.
 *
 * PO ruling 2026-10-01 (decision log *"CAPACITY SERVICES: THE BASE IS LOOKED UP
 * BY SIZE ON EVERY BILL"* and *"GO: THE NINE CHANGES"*, items 7 and 8):
 * *"i want tracbility -> billing -> account -> unit -> plan -> rate schedule ->
 * base charge -> size and amount"*. Worked: two 96-gallon carts, base $3.00 a
 * cart, carts $15.00 each →
 *
 *     Trash 96-gallon cart × 2 · base $3.00 · $15.00 each
 *
 * ONE component for the two screens that show it (B14 rule 43): the bill
 * detail line (`BillDetailPage`) reads the line's stored `pricing_trace`
 * (`billing/0039`), and the one-time bill's review step reads the line's
 * `breakdown` (`one_time_answer.size_breakdown`). Each row is a FACT, so it
 * stays a fact's length (B14 rule 33) and carries no rationale.
 *
 * A size with no base price prints *base not priced* — the bill went out with
 * that size's base at $0.00 (PO 2026-10-01: a warning, never a refusal).
 */
import type { ReactNode } from "react";

export interface SizeBreakdownRow {
  size: string | null;
  size_label?: string | null;
  count: number | null;
  base_each: string | null;
  price_each?: string | null;
  base_priced?: boolean;
}

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** The rows that say something: a size with a COUNT. A metered service's one
 *  base has no count and is not a breakdown. */
export function breakdownRows(rows: readonly SizeBreakdownRow[] | null | undefined): SizeBreakdownRow[] {
  return (rows ?? []).filter((row) => row.count !== null && row.count !== undefined);
}

export function SizeBreakdown(props: {
  rows: readonly SizeBreakdownRow[] | null | undefined;
  /** Formats a stored four-place figure as money in the bill's currency. */
  formatAmount: (amount: string) => string;
  t: Translate;
}): ReactNode {
  const rows = breakdownRows(props.rows);
  if (rows.length === 0) return null;
  const { t } = props;
  return (
    <span className="mt-1 block text-sm" data-size-breakdown="">
      {rows.map((row, index) => {
        const size = row.size_label ?? row.size ?? "";
        const params = {
          size,
          count: row.count,
          base: props.formatAmount(row.base_each ?? "0"),
          price: row.price_each ? props.formatAmount(row.price_each) : "",
        };
        const key =
          row.base_priced === false
            ? row.price_each
              ? "billing.bill.line.sizeNoBasePrice"
              : "billing.bill.line.sizeNoBase"
            : row.price_each
              ? "billing.bill.line.sizeBasePrice"
              : "billing.bill.line.sizeBase";
        return (
          <span key={`${row.size ?? ""}-${index}`} className="block" data-size={row.size ?? ""}>
            {t(key, params)}
          </span>
        );
      })}
    </span>
  );
}
