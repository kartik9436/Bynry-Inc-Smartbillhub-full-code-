// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-052 (EP-CWP-10). Screen: CWP-043 at
//           `/{tenant}/portal/plan`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-013 (the switcher picks
//           WHICH account) · B14 rule 31 (no database id in the address)
// Tests:    src/portal/plans/YourPlan.dom.test.tsx
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
import { YourPlanView } from "./YourPlan";

/**
 * `CWP-043` for **one** account — the one the switcher is on.
 *
 * ⚠ **A PLAN BELONGS TO ONE ACCOUNT, SO THE ACCOUNT HAS TO BE NAMED — AND IT IS
 * NAMED BY THE SWITCHER RATHER THAN BY THE ADDRESS** (B14 rule 31, and
 * `/account`'s own reasoning). A landlord holding four accounts moves between
 * them with the control that exists for exactly that; the id travels in the
 * request, where it is intersected with the session's set in the query.
 *
 * ⚠ **CLOSED PLANS COME BACK WITH THE LIVE ONE**, so a customer reconciling a
 * statement from 2025 has something to reconcile it against.
 */
export function YourPlanPage(props: { client?: ApiClient }) {
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
        <YourPlanView accountId={accountId} />
      ) : (
        <p className="text-body text-neutral-600">{t("portal.home.noAccountsYet")}</p>
      )}
    </PortalShell>
  );
}
