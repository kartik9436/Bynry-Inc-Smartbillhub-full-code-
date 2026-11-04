// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-031 (EP-CWP-06). Screen: CWP-065 at
//           `/{tenant}/portal/account`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-013 (the switcher picks
//           WHICH account; there is no nesting and no default beyond the first)
// Tests:    src/portal/accounts/YourAccount.dom.test.tsx
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
import { YourAccountView } from "./YourAccount";

/**
 * `CWP-065` for **one** account — the one the switcher is on.
 *
 * ⚠ **THE ROUTE CARRIES NO ACCOUNT ID, AND THAT IS B14 RULE 31 AND NOT A
 * SHORTCUT.** A database id in an address bar is an id on screen; the switcher
 * already knows which account the customer is looking at, so the page asks it
 * rather than the URL. A landlord moves between their four with the switcher,
 * which is the control that exists for exactly this.
 */
export function YourAccountPage(props: { client?: ApiClient }) {
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
  const accountId = resolveCurrentAccount(session.accounts, current);
  return (
    <PortalShell
      front={frontQuery.data}
      displayName={session.customer.display_name}
      accounts={session.accounts}
      currentAccountId={accountId}
      onAccountChange={setCurrent}
    >
      {accountId ? (
        <YourAccountView accountId={accountId} />
      ) : (
        // B14 rule 17 — a login with no account yet says what fills the page.
        <p className="text-body text-neutral-600">{t("portal.home.noAccountsYet")}</p>
      )}
    </PortalShell>
  );
}
