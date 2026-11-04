// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-026 (EP-CWP-06). Screen: CWP-023 at `/{tenant}/portal/accounts`
// Rules:    CR-068 §11c (one page per route) · B14 rule 36 (compose the kit) ·
//           BR-CWP-047 (the table itself never caches; only the SHELL's
//           branding and session are queried)
// Tests:    src/portal/accounts/MyAccounts.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx
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
import { MyAccountsView } from "./MyAccounts";

/**
 * `CWP-023` inside the signed-in shell.
 *
 * ⚠ **THE SHELL'S TWO READS ARE CACHED AND THE TABLE'S IS NOT**, deliberately.
 * Branding and the session's account list are stable for a visit; the four
 * BALANCES are not, and `BR-CWP-047` is about the balances — *a credit that was
 * real on Tuesday can be spent by Thursday*. `MyAccountsView` calls the server
 * on every mount for exactly that reason, and putting it behind a query here
 * would undo it from the outside.
 */
export function MyAccountsPage(props: { client?: ApiClient }) {
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
      <MyAccountsView />
    </PortalShell>
  );
}
