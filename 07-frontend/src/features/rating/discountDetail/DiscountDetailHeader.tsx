// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 6 — the discount details HEADER
//           (images 19, 23, 24, 26).
// Defect:   DEF-RAT-9291 D19 (kicker DISCOUNT · AUTOPAY · PERCENTAGE · V1) ·
//           D20 (overlay paragraph under the title) · D22 (four buttons)
// Rules:    README point 6 · B14 rule 31 · rule 33 · rule 40 (32px title,
//           the kit's PageHeader)
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";

import type { DiscountDetailRow } from "@/api/discountDetailEndpoints";
import { formatDate } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import type { PageHeaderTab } from "@/components/PageHeader";

import { DiscountStatusCell } from "../discountListParts";
import { TaxVersionTag } from "../taxListParts";
import { headerPlace, nextShown } from "./discountDetailModel";
import type { DiscountRegional, Translator } from "./discountDetailModel";

/** A thin divider between two header facts, as the drawing draws it. */
function Divider() {
  return <span aria-hidden="true" className="h-4 w-px bg-divider" />;
}

/**
 * The line under the title: status, version, then *Type · window*, then *Next*
 * behind a divider when a later value is approved. Every part is a FACT.
 */
export function DiscountHeaderFacts(props: { row: DiscountDetailRow; regional: DiscountRegional; t: Translator }) {
  const { row, regional, t } = props;
  const place = headerPlace(row, regional, t);
  const next = row.scheduled_next ?? null;
  return (
    <span className="flex flex-wrap items-center gap-2 text-base text-neutral-700" data-discount-header-facts="">
      <DiscountStatusCell status={row.status} />
      <TaxVersionTag version={row.version ?? row.version_no} />
      {place !== "" && <span data-discount-header-window="">{place}</span>}
      {nextShown(row) && next !== null && (
        <>
          <Divider />
          <span data-discount-header-next="">
            {t("rating.taxDetail.header.next")}{" "}
            <strong className="font-semibold text-neutral-900">
              {t("rating.taxDetail.header.nextValue", {
                rate: next.value_display ?? "—",
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
 * Back link, the NAME with its CODE beside it, the facts line, the actions and
 * the tab strip — the kit's one `PageHeader`. No kicker (D19) and no sentence
 * under the title (D20).
 */
export function DiscountDetailHeader(props: {
  row: DiscountDetailRow;
  regional: DiscountRegional;
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
      backTo={{ to: props.backTo, label: t("rating.discountForm.back") }}
      title={row.name}
      titleAfter={
        row.code.trim() === "" ? undefined : (
          <span className="ms-3 align-middle text-base font-semibold uppercase text-neutral-700" data-discount-code="">
            {row.code}
          </span>
        )
      }
      rollup={<DiscountHeaderFacts row={row} regional={props.regional} t={t} />}
      secondaryActions={props.actions}
      tabs={props.tabs}
      activeTabId={props.activeTab}
      tabsLabel={t("rating.discountDetail.tabsLabel")}
      onTabSelect={(tab) => props.onTab(tab.id)}
    />
  );
}
