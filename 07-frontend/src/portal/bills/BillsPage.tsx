// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-032 (EP-CWP-07). Screen: CWP-027 at `/{tenant}/portal/bills`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-047 (the list itself is
//           never cached; only the shell's branding and session are queried)
// Tests:    src/portal/bills/Bills.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · screenIds.ts
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
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
import { BillsView } from "./Bills";

/** `CWP-027` inside the signed-in shell. The list is read on every mount —
 *  every row carries a live owing figure (`BR-CWP-047`). */
export function BillsPage(props: { client?: ApiClient }) {
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
  // ⚠ **THE ACCOUNT IS RESOLVED ONCE AND USED TWICE** — as the switcher's
  // value and as the list's scope — so the header and the table cannot name
  // different accounts (`BR-CWP-010`, `US-CWP-023` TC-2).
  const accountId = resolveCurrentAccount(session.accounts, current);
  return (
    <PortalShell
      front={frontQuery.data}
      displayName={session.customer.display_name}
      accounts={session.accounts}
      currentAccountId={accountId}
      onAccountChange={setCurrent}
    >
      <BillsView accountId={accountId} />
    </PortalShell>
  );
}
