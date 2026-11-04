// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-033 · US-CWP-034 · US-CWP-035 (EP-CWP-07).
//           Screens: CWP-028 · CWP-029 · CWP-030, at
//           `/{tenant}/portal/bills/:number`, `…/document`, `…/comparison`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-047 (a bill's owing
//           figure is live, so nothing on these pages is cached) · B14 rule 31
//           (the address bar carries the bill NUMBER, never an id)
// Tests:    src/portal/bills/BillDetail.dom.test.tsx ·
//           src/portal/bills/PrintedBill.dom.test.tsx ·
//           src/portal/bills/BillComparison.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · screenIds.ts
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { getPortalFront } from "../api/guestClient";
import { getSession } from "../api/portalClient";
import { PortalShell } from "../shell/PortalShell";
import { resolveCurrentAccount, useCurrentAccount } from "../shell/currentAccount";
import { BillComparisonView } from "./BillComparison";
import { BillDetailView } from "./BillDetail";
import { PrintedBillView } from "./PrintedBill";

/** The signed-in shell the three bill screens share.
 *
 *  ⚠ **ONE FRAME, THREE PAGES, AND NOT ONE PAGE WITH THREE TABS.** Each screen
 *  has its own address because each is somewhere a customer is SENT — a bill's
 *  detail from the list, its document from an email, its explainer from a
 *  *why is this higher* link — and a tab state cannot be sent to anybody. */
function BillFrame(props: { client?: ApiClient; children: ReactNode }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const frontQuery = useQuery({
    queryKey: queryKeys.portalFront,
    queryFn: () => getPortalFront(client),
  });
  const sessionQuery = useQuery({
    queryKey: ["portal", "session"],
    queryFn: () => getSession(client),
  });
  const [current, setCurrent] = useCurrentAccount();

  if (frontQuery.isPending || sessionQuery.isPending) return <LoadingSkeleton variant="card" />;
  if (frontQuery.data === undefined || sessionQuery.data === undefined) {
    return (
      <FailedWithRetry
        title={t("portal.failedTitle")}
        reason={refusalText(t, frontQuery.error ?? sessionQuery.error)}
        onRetry={() => void sessionQuery.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }
  const session = sessionQuery.data;
  return (
    <PortalShell
      front={frontQuery.data}
      displayName={session.customer.display_name}
      accounts={session.accounts}
      currentAccountId={resolveCurrentAccount(session.accounts, current)}
      onAccountChange={setCurrent}
    >
      {props.children}
    </PortalShell>
  );
}

/** `CWP-028` — one bill, line by line. */
export function BillDetailPage(props: { client?: ApiClient }) {
  return (
    <BillFrame client={props.client}>
      <BillDetailView />
    </BillFrame>
  );
}

/** `CWP-029` — the bill as it was printed. */
export function PrintedBillPage(props: { client?: ApiClient }) {
  return (
    <BillFrame client={props.client}>
      <PrintedBillView />
    </BillFrame>
  );
}

/** `CWP-030` — why this bill is different. */
export function BillComparisonPage(props: { client?: ApiClient }) {
  return (
    <BillFrame client={props.client}>
      <BillComparisonView />
    </BillFrame>
  );
}
