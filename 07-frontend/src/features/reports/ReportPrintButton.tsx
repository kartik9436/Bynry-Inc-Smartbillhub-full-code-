// ── Trace ──────────────────────────────────────────────
// Change:  CR-185-BRC10 D4 — the Owner summary is a DOCUMENT the utility hands
//          a landlord (PO 2026-10-14: *"Summary document only: one monthly
//          statement with a section per property and a grand total"*), so the
//          report viewer offers Print beside Download for a report that says it
//          is printable.
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT) · rule 44 (our kit wins) ·
//          rule 21 (Tailwind utilities; this file is in route-b-migrated.txt) ·
//          rule 33 (a label, no sentence) · hard-won law 2's mirror (drawn only
//          where the server declares it)
// Tests:   07-frontend/src/features/reports/ownerSummaryReport.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { PrinterIcon } from "@/components/icons";

/**
 * The browser's own print of the page — the table, its totals and its head.
 *
 * ⚠ **ICON-ONLY, THE SAME SHAPE AS `DownloadButton`**, because they sit side by
 * side in the table's download slot: two buttons of one kind in one slot read
 * as one toolbar. The word is the `aria-label` and the `title`, exactly as the
 * download glyph carries `download.csv`.
 *
 * `print` is injectable so a test can see the call without opening a dialog.
 */
export function ReportPrintButton(props: { print?: () => void }) {
  const { t } = useTranslation();
  const label = t("reports.print");
  return (
    <Button
      variant="secondary"
      className="ml-2 h-9 w-9 justify-center px-0 print:hidden"
      data-report-print="button"
      aria-label={label}
      title={label}
      onClick={() => (props.print ?? (() => window.print()))()}
    >
      <PrinterIcon />
    </Button>
  );
}

export default ReportPrintButton;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-185-BRC10 · decision log 2026-10-14 "LANDLORD D2–D5" (D4)
// generated: 2026-10-14 by lane OWNER-D4D5
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
