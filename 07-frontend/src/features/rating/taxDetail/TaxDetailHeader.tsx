// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 3 task 6 — the tax details HEADER (images 18–23).
// Defect:   DEF-RAT-9272 P29 (kicker repeats itself) · P30 (header says
//           little) · P31 (long sentence under the title) · P35 (four buttons)
// Rules:    PO round 7 (2026-10-03) — name + code · Active · version · Over 20%
//           · authority · dates · Filing due (active only) · Next (only when
//           saved) · B14 rule 31 · rule 33 · rule 40 (32px title, PageHeader)
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";

import { PageHeader } from "@/components/PageHeader";
import type { PageHeaderTab } from "@/components/PageHeader";
import { StatusPill } from "@/components/StatusPill";
import type { TaxDetailRow } from "@/api/taxDetailEndpoints";
import { formatDate } from "@/components/DateCell";

import { TaxStatusCell, TaxVersionTag } from "../taxListParts";
import {
  authorityText,
  filingDueShown,
  scheduledNextShown,
  taxIsOverTwenty,
  taxWindowText,
} from "./taxDetailModel";
import type { TaxRegional, Translator } from "./taxDetailModel";

/** A thin divider between two header facts, as the drawing draws it. */
function Divider() {
  return <span aria-hidden="true" className="h-4 w-px bg-divider" />;
}

/**
 * The line under the title: the three pills, then the authority and window,
 * then *Filing due* and *Next* each behind a divider. Every part is a FACT —
 * nothing here explains anything (P31, B14 rule 33).
 */
export function TaxHeaderFacts(props: { row: TaxDetailRow; regional: TaxRegional; t: Translator }) {
  const { row, regional, t } = props;
  const authority = authorityText(row, t);
  const window = taxWindowText(row, regional, t);
  const place = [authority, window].filter((part): part is string => part !== null).join(" · ");
  const next = row.scheduled_next ?? null;
  return (
    <span className="flex flex-wrap items-center gap-2 text-base text-neutral-700" data-tax-header-facts="">
      <TaxStatusCell status={row.status} />
      <TaxVersionTag version={row.version} />
      {taxIsOverTwenty(row) && <StatusPill tone="warning">{t("rating.taxes.list.overTwenty")}</StatusPill>}
      {place !== "" && <span data-tax-header-window="">{place}</span>}
      {filingDueShown(row) && (
        <>
          <Divider />
          <span data-tax-header-due="">
            {t("rating.taxDetail.header.filingDue")}{" "}
            <strong className="font-semibold text-neutral-900">
              {formatDate(row.next_filing_due ?? "", regional.timeZone, regional.dateFormat)}
            </strong>
          </span>
        </>
      )}
      {scheduledNextShown(row) && next !== null && (
        <>
          <Divider />
          <span data-tax-header-next="">
            {t("rating.taxDetail.header.next")}{" "}
            <strong className="font-semibold text-neutral-900">
              {t("rating.taxDetail.header.nextValue", {
                rate: next.rate_display ?? "—",
                date: formatDate(next.effective_from ?? "", regional.timeZone, regional.dateFormat),
              })}
            </strong>
          </span>
        </>
      )}
    </span>
  );
}

/**
 * The header: back link, the NAME with its CODE beside it, the facts line, the
 * actions and the tab strip — the kit's one `PageHeader` (BR-SHL-044).
 *
 * ⚠ **NO KICKER.** Today's `TAX · CITY · CITY` (P29) said the kind twice and
 * the authority once; the drawing has no kicker at all, and the authority now
 * sits in the facts line where it is read once.
 */
export function TaxDetailHeader(props: {
  row: TaxDetailRow;
  regional: TaxRegional;
  backTo: string;
  actions: ReactNode;
  tabs: readonly PageHeaderTab[];
  activeTab: string;
  onTab: (id: string) => void;
  t: Translator;
}) {
  const { row, t } = props;
  return (
    <PageHeader
      backTo={{ to: props.backTo, label: t("rating.taxDetail.back") }}
      title={row.name}
      titleAfter={
        row.code === null || row.code.trim() === "" ? undefined : (
          <span className="ms-3 align-middle text-base font-semibold uppercase text-neutral-700" data-tax-code="">
            {row.code}
          </span>
        )
      }
      rollup={<TaxHeaderFacts row={row} regional={props.regional} t={t} />}
      secondaryActions={props.actions}
      tabs={props.tabs}
      activeTabId={props.activeTab}
      tabsLabel={t("rating.taxDetail.tabsLabel")}
      onTabSelect={(tab) => props.onTab(tab.id)}
    />
  );
}
