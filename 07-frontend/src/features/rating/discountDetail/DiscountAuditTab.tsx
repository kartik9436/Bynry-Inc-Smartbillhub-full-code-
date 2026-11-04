// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 6 — the discount details AUDIT tab
//           (image 22): every change across the discount, its versions, its
//           plan links and its enrollments, with its reason.
// Defect:   DEF-RAT-9291 D31 (Audit showed versions only; stray "Discard
//           draft" heading) · D32 (the DATED note box)
// Defect:   DEF-1005 (no CSV — ⤓ live since the CR-166 follow-up, 2026-10-03)
// Rules:    NFR-3 (paged by the server; the CSV streams every row) · B14 rule 31 (NAMES, never ids) ·
//           rule 16 (the pagination footer) · hard rule 4 (`audit_log` is
//           pruned on retention, so the screen claims no permanence)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE VERSION ROWS MOVED TO OVERVIEW, AND THE DRAFT'S DISCARD TO MORE ▾.**
// Until this round the Audit tab WAS the version chain (`discountDetailTabs`,
// `DEF-RAT-5817`) with a *Discard draft* button on the draft row. The drawing
// puts the versions table at the foot of Overview (image 19) and this tab is
// `GET /discounts/{id}/audit` — a window onto `audit_log`. The discard did not
// go away: it is *Delete draft* in the header's More ▾.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import type { ApiClient } from "@/api/client";
import { getDiscountAuditCsv, getDiscountAuditPage } from "@/api/discountDetailEndpoints";
import type { DiscountAuditEntry } from "@/api/discountDetailEndpoints";
import { formatDate } from "@/components/DateCell";
import { DownloadButton } from "@/components/DownloadButton";
import { ListPager } from "@/components/ListPager";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton } from "@/components/StateFrame";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";
import { PAGE_SIZES } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";

import { SECTION_HEADING } from "../discountForm/discountFormShared";
import { saveCsv } from "../planDetail/saveCsv";
import { DASH, auditChange, auditWhat, auditWho } from "./discountDetailModel";
import type { DiscountRegional, Translator } from "./discountDetailModel";

export function DiscountAuditTab(props: {
  discountId: string;
  client: ApiClient;
  regional: DiscountRegional;
  t: Translator;
}) {
  const { t, regional } = props;
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(PAGE_SIZES[0]);
  const query = useQuery({
    queryKey: ["discounts", props.discountId, "audit", page, per],
    queryFn: () => getDiscountAuditPage(props.discountId, { page, per }, props.client),
    enabled: props.discountId !== "",
    placeholderData: (previous) => previous,
  });
  const rows: readonly DiscountAuditEntry[] = query.data?.rows ?? [];
  const total = query.data?.total ?? 0;
  const toast = useToast();

  async function download(): Promise<void> {
    try {
      saveCsv(await getDiscountAuditCsv(props.discountId, props.client), "discount-audit.csv");
    } catch {
      toast(t("rating.planDetail.csvFailed"));
    }
  }

  return (
    <Panel as="section" aria-labelledby="discount-detail-audit" data-discount-audit="">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 id="discount-detail-audit" className={`${SECTION_HEADING} mb-0`}>
          {t("rating.taxDetail.audit.title")}
        </h2>
        {/* Image 22's ⤓ — every row, streamed by the server (DEF-1005). */}
        <DownloadButton onDownload={() => void download()} />
      </div>
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
                  // An audit row carries no id on the wire; its place in the
                  // page is a stable key for one page.
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
