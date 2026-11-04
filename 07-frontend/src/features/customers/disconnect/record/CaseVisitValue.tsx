// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-9696 — the disconnect case page listed no work order. Since
//           DEF-CUS-9631 (2.520.2) the wizard's cut visit is raised
//           (`source = disconnect`, `source_ref` = the case number); the case
//           record now serves it as `work_orders` and this draws it.
// Rules:    B14 rule 31 (the job's WO- number, never its id) · rule 43 (a piece
//           of UI is a component) · rule 34 (one vocabulary — the move record's
//           own visit words are BORROWED, not re-minted)
// Tests:    src/features/customers/disconnect/record/DisconnectRecordPage.test.tsx
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { InlineLinkTo } from "@/components/Surfaces";
import { useTenantPath } from "@/routing/tenantPath";

import type { DisconnectCaseVisits } from "./disconnectRecordEndpoints";

/** `1 raised · 0 done · 0 accepted` and each job's number, linked to it. */
export function CaseVisitValue(props: { visits: DisconnectCaseVisits }) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const { visits } = props;
  return (
    <span data-case-visits="">
      {t("customers.moveRecord.owed.visitCounts", {
        raised: visits.raised,
        done: visits.done,
        accepted: visits.accepted,
      })}
      {visits.orders.map((order) => (
        <span key={order.order_no}>
          {" · "}
          <InlineLinkTo
            to={tenantPath(`/work/orders/${order.order_no}`)}
            data-case-visit-order={order.order_no}
          >
            {order.order_no}
          </InlineLinkTo>
        </span>
      ))}
    </span>
  );
}
