// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-028 (EP-CWP-06). Screen: CWP-024 at
//           `/{tenant}/portal/my-details`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-010 (the account set is
//           the session's; there is no id in this address and none in a body)
// Tests:    src/portal/details/MyDetails.dom.test.tsx
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
import { MyDetailsView } from "./MyDetails";

/**
 * `CWP-024` — one page, and **no account in its address**.
 *
 * ⚠ **THE SWITCHER IS PRESENT BUT THIS SCREEN IS NOT PER ACCOUNT**, which is
 * the one thing to understand about it: a contact detail is edited once and
 * written to every account the login holds (`US-CWP-028` TC-10). The shell
 * keeps the switcher because a customer navigating away needs it, and the body
 * says how far the save reaches so the two cannot be read as contradicting.
 */
export function MyDetailsPage(props: { client?: ApiClient }) {
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
      <MyDetailsView />
    </PortalShell>
  );
}
