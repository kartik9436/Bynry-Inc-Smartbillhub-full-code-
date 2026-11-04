// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-10164 (PO 2026-10-17 — Premises and Units lists show
//           Created + Age, both sortable oldest ↔ newest).
// Rules:    BR-SHL-023 (tenant zone + regional format) · B14 rule 43 (one
//           component, two lists) · IS-2 (a sortable header sends the
//           server's own sort name)
// Tests:    features/metering/createdAgeColumns.dom.test.tsx
// ───────────────────────────────────────────────────────
// The two columns as ONE declaration, so the Premises list, the Units list —
// and any later list that shows when a record began — cannot draw them
// differently. Both headers send `sort=created` (`sortKey`): an age is only
// the distance from Created to today, so the two sort as one.
import { AgeCell } from "@/components/AgeCell";
import { DateCell, type RegionalDateFormat } from "@/components/DateCell";
import type { TableColumnConfig } from "@/components/tableTypes";
import { dayInZone } from "@/lib/age";

export const CREATED_SORT = "created";

export function createdAgeColumns<Row>(
  t: (key: string) => string,
  read: (row: Row) => string | null | undefined,
  regional: { timeZone: string; dateFormat: RegionalDateFormat },
): TableColumnConfig<Row>[] {
  return [
    {
      key: CREATED_SORT,
      label: t("common.col.created"),
      sortable: true,
      cell: (row) => {
        const day = dayInZone(read(row), regional.timeZone);
        return day === null ? (
          <span>—</span>
        ) : (
          <DateCell value={day} timeZone={regional.timeZone} dateFormat={regional.dateFormat} />
        );
      },
    },
    {
      key: "age",
      label: t("common.col.age"),
      sortable: true,
      sortKey: CREATED_SORT,
      cell: (row) => <AgeCell start={read(row)} timeZone={regional.timeZone} />,
    },
  ];
}
