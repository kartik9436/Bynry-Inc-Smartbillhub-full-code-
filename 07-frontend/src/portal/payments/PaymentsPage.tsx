// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-048 (EP-CWP-09). Screen: CWP-041 at
//           `/{tenant}/portal/payments`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-047 (nothing here is
//           cached; only the shell's branding and session are queried) ·
//           B14 rule 31 (no account id in the address)
// Tests:    src/portal/payments/Payments.dom.test.tsx
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
import { PaymentsView } from "./Payments";

/**
 * `CWP-041` inside the signed-in shell.
 *
 * ⚠ **NO ACCOUNT ID IN THE ADDRESS AND NONE IN THE READ.** The money list is
 * one person reconciling one bank statement across every account they hold —
 * the same scope `/bills` and `/documents` take — so the session's set IS the
 * filter and it is applied in the server's query (`BR-CWP-010`).
 */
export function PaymentsPage(props: { client?: ApiClient }) {
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
      <PaymentsView accountId={accountId} />
    </PortalShell>
  );
}
