// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.12 — the Work tab (image 27): the account's work
//           orders and *+ Add work order*.
// Rules:    B14 rule 43 — Work's own `WorkOrdersTab` on its `account` host is
//           the table (the account detail and the premises detail mount the
//           same one); nothing is re-drawn here.
// Data:     `GET /accounts/{id}/work-orders` (Work's); its *Raise work here* is
//           the drawn add door. The move's own door (§9.FLOW) is in More ▾.
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { WorkOrdersTab } from "@/features/work/buildViews";

import { DetailGroup, EmptyLine } from "./moveDetailParts";
import type { Regional } from "./moveDetailParts";

export function MoveWorkTab(props: { accountId: string | null; regional: Regional; client?: ApiClient }) {
  const { t } = useTranslation();
  const [openOrderId, setOpenOrderId] = useState<string | null>(null);
  // ⚠ NOT WRAPPED IN A SECOND GROUP: Work's tab draws its own *Work orders*
  // band and its own raise door (*Raise work here*), which is image 27's
  // *+ Add work order*; a wrapper would draw both twice. The move's own
  // *Add a work order* (§9.FLOW) stays in the head's More ▾ while a read is due.
  if (props.accountId === null) {
    return (
      <DetailGroup title={t("customers.moveDetail.section.workOrders")} name="work">
        <EmptyLine>{t("customers.moveDetail.work.noAccountYet")}</EmptyLine>
      </DetailGroup>
    );
  }
  return (
    <div data-move-tab="work">
      <WorkOrdersTab
        host="account"
        hostId={props.accountId}
        t={t}
        timeZone={props.regional.timeZone}
        dateFormat={props.regional.dateFormat}
        openOrderId={openOrderId}
        onOpenOrder={setOpenOrderId}
        client={props.client}
      />
    </div>
  );
}
