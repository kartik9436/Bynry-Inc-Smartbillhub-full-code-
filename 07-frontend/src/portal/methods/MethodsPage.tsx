// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-046 (EP-CWP-09) · US-CWP-022 (EP-CWP-05). Screen: CWP-039
//           at `/{tenant}/portal/payment-methods`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-057 (a token, never a
//           card number) · BR-CWP-040 (step-up before a method changes)
// Tests:    src/portal/methods/Methods.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx (registered by the phase-5
//           address commit; NOT touched by this lane)
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";

import { getPortalFront } from "../api/guestClient";
import { getSession } from "../api/portalClient";
import { PortalShell } from "../shell/PortalShell";
import { resolveCurrentAccount, useCurrentAccount } from "../shell/currentAccount";
import { MethodsView } from "./Methods";

/**
 * `CWP-039` — **and this file REPLACED A HOLDING SCREEN, which was the first
 * act of this wave rather than the last** (`DEF-CWP-3925`).
 *
 * The six phase-5 addresses were registered once, before four lanes started,
 * because `portalRoutes.tsx` and `screenIds.ts` are one file each and a
 * pathspec commit takes a whole file (hard-won law 11). The cost was that a
 * real route answered with `ComingSoon` for a few hours. Replacing it here is
 * what pays that debt; `data-holding-screen` is gone from this address.
 */
export function MethodsPage(props: { client?: ApiClient }) {
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
      <MethodsView />
    </PortalShell>
  );
}
