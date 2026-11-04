// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 3 task 6 — the tax details AUDIT tab (image 20).
//           PO 2026-10-03: *"in audit we can have histroy - rate history is
//           not adding uch value"* — every change, with its reason, here.
// Defect:   DEF-RAT-9272 P38 · P39 · P40
// Rules:    NFR-3 (paged by the server) · B14 rule 31 (NAMES, never ids) ·
//           rule 16 (the pagination footer) · hard rule 4 (`audit_log` is
//           pruned on retention, so a short trail is a true answer)
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS READS `GET /taxes/{id}/audit` — A WINDOW ONTO `audit_log` — AND
// THAT IS THE RULING, NOT THE MISTAKE CR-087's NOTE WARNED ABOUT.** The old
// Audit tab rendered the tax's OWN version chain and `DefinitionDetailPage`
// refused any audit read, because then the tab was a RATE HISTORY and an
// audit trail is a different record. The PO's round-6 ruling split the two:
// the versions table moved to Overview (the priced states bills resolve to),
// and Audit became *every change with its reason* — which is what `audit_log`
// is for. Both records are on the page now, each where the drawing puts it.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import type { ApiClient } from "@/api/client";
import { getTaxAuditPage } from "@/api/taxDetailEndpoints";
import type { TaxAuditEntry } from "@/api/taxDetailEndpoints";
import { formatDate } from "@/components/DateCell";
import { ListPager } from "@/components/ListPager";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton } from "@/components/StateFrame";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { PAGE_SIZES } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";

import { SECTION_HEADING } from "../taxForm/taxFormShared";
import { DASH, auditChange, auditWhat, auditWho } from "./taxDetailModel";
import type { TaxRegional, Translator } from "./taxDetailModel";

export function TaxAuditTab(props: { taxId: string; client: ApiClient; regional: TaxRegional; t: Translator }) {
  const { t, regional } = props;
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(PAGE_SIZES[0]);
  const query = useQuery({
    queryKey: ["taxes", props.taxId, "audit", page, per],
    queryFn: () => getTaxAuditPage(props.taxId, { page, per }, props.client),
    enabled: props.taxId !== "",
    placeholderData: (previous) => previous,
  });
  const rows: readonly TaxAuditEntry[] = query.data?.rows ?? [];
  const total = query.data?.total ?? 0;

  return (
    <Panel as="section" aria-labelledby="tax-detail-audit" data-tax-audit="">
      <h2 id="tax-detail-audit" className={SECTION_HEADING}>
        {t("rating.taxDetail.audit.title")}
      </h2>
      {query.isPending ? (
        <LoadingSkeleton variant="table" />
      ) : query.isError ? (
        <Note>{t("rating.taxDetail.audit.failed")}</Note>
      ) : rows.length === 0 ? (
        <Note>{t("rating.taxDetail.audit.empty")}</Note>
      ) : (
        <>
          <div className="border border-divider">
            <PlainTable>
              <thead>
                <tr>
                  <th scope="col">{t("rating.taxDetail.audit.col.when")}</th>
                  <th scope="col">{t("rating.taxDetail.audit.col.who")}</th>
                  <th scope="col">{t("rating.taxDetail.audit.col.what")}</th>
                  <th scope="col">{t("rating.taxDetail.audit.col.change")}</th>
                  <th scope="col">{t("rating.taxDetail.audit.col.reason")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  // An audit row carries no id of its own on the wire; its
                  // place in the page is a stable key for one page.
                  <tr key={`${row.at ?? ""}-${index}`} data-audit-action={row.action}>
                    <td className="whitespace-nowrap tabular-nums">
                      {row.at === null ? DASH : formatDate(row.at, regional.timeZone, regional.dateFormat, true)}
                    </td>
                    <td>{auditWho(row, t)}</td>
                    <td>{auditWhat(row.action, t)}</td>
                    <td>{auditChange(row, t, regional)}</td>
                    <td>{row.reason === null || row.reason.trim() === "" ? DASH : row.reason}</td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          </div>
          <ListPager
            page={page}
            per={per}
            total={total}
            onPage={setPage}
            onPer={(next) => {
              setPer(next);
              setPage(1);
            }}
          />
        </>
      )}
    </Panel>
  );
}
