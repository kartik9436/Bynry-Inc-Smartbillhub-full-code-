// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-047 (EP-CWP-09). Screen: CWP-040 at
//           `/{tenant}/portal/autopay`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-013 (the switcher picks
//           WHICH account) · B14 rule 31 (no database id in the address)
// Tests:    src/portal/methods/Autopay.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx (already registered)
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { getPortalFront } from "../api/guestClient";
import { getSession } from "../api/portalClient";
import { PortalShell } from "../shell/PortalShell";
import { resolveCurrentAccount, useCurrentAccount } from "../shell/currentAccount";
import { AutopayView } from "./Autopay";

/**
 * `CWP-040` inside the signed-in shell.
 *
 * ⚠ **THIS FILE REPLACED A `ComingSoon` HOLDING SCREEN**, which was registered
 * at `/autopay` before any of the four phase-5 lanes started so that
 * `portalRoutes.tsx` and `screenIds.ts` were each written ONCE (law 11). The
 * holding component's own docstring says replacing it *"is the first act of its
 * wave"*, and the walkthrough fails on any `data-holding-screen` left in the
 * DOM — so this file existing is what closes that debt.
 *
 * ⚠ **NO ACCOUNT ID IN THE ADDRESS.** The switcher names the account, exactly
 * as `/plan` and `/account` do (B14 rule 31).
 */
export function AutopayPage(props: { client?: ApiClient }) {
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
      <PageHeader kicker={t("portal.autopay.kicker")} title={t("portal.autopay.title")} />
      {accountId ? (
        <AutopayView accountId={accountId} />
      ) : (
        // B14 rule 17 — a login with no account yet says what fills the page.
        <p className="text-body text-neutral-600">{t("portal.home.noAccountsYet")}</p>
      )}
    </PortalShell>
  );
}
