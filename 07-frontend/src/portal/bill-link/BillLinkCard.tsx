// ── Trace ──────────────────────────────────────────────
// Change:  DEF-BIL-10531 — the bill email's direct PDF link (PO 2026-10-22,
//          *"b direct PDF link"*)
// Rules:   B14 rule 43 (a COMPONENT, not code inside a page) · rule 21
//          (Tailwind only) · rule 31 (the token is never shown) · rule 33
//          (labels ≤3 words, facts ≤6, no rationale) · rule 35 (eleven native
//          catalogues) · the eight portal accessibility questions
// Tests:   src/portal/bill-link/BillLinkPage.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { WorkingButton } from "@/components/StateFrame";

import type { BillLinkOpen } from "../api/billLinkClient";
import { Card, KVList, SectionTitle } from "../components/primitives";
import { usePortalDate } from "../components/regional";
import { Announced } from "../components/a11y";

/** One bill the link opens: which bill, when it is due, and the PDF. */
export function BillLinkCard(props: {
  bill: BillLinkOpen;
  working: boolean;
  failed: boolean;
  onDownload: () => void;
}) {
  const { t } = useTranslation();
  const formatDate = usePortalDate();
  const { bill } = props;
  const rows = [
    { key: "bill", label: t("portal.billLink.billNo"), value: bill.bill_no ?? "—" },
    ...(bill.bill_date !== null
      ? [{ key: "date", label: t("portal.billLink.billDate"), value: formatDate(bill.bill_date) }]
      : []),
    ...(bill.due_date !== null
      ? [{ key: "due", label: t("portal.billLink.dueDate"), value: formatDate(bill.due_date) }]
      : []),
  ];
  return (
    <Card testId="bill-link">
      <div data-screen="bill-link" className="flex flex-col gap-4">
        <div>
          {bill.utility_name !== null ? <SectionTitle>{bill.utility_name}</SectionTitle> : null}
          <h1 className="text-h1 leading-tight text-neutral-900">{t("portal.billLink.title")}</h1>
        </div>
        <KVList rows={rows} />
        <div className="flex flex-col items-start gap-2">
          <WorkingButton working={props.working} onClick={props.onDownload}>
            {t("portal.billLink.download")}
          </WorkingButton>
          {props.failed ? (
            <Announced tone="error" className="text-base font-semibold text-danger-700">
              {t("portal.billLink.downloadFailed")}
            </Announced>
          ) : null}
          {bill.expires_on !== null ? (
            <p className="text-base text-neutral-600" data-bill-link-expires="">
              {t("portal.billLink.worksUntil", { date: formatDate(bill.expires_on) })}
            </p>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
