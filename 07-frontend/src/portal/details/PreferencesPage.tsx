// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-028 (EP-CWP-06). Screen: CWP-025 at
//           `/{tenant}/portal/my-details/preferences`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-010 (the account set is
//           the session's; no id in this address and none in a body)
// Tests:    src/portal/details/Preferences.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · screenIds.ts
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

import { PreferencesView } from "./Preferences";

/**
 * `CWP-025` — one page, and **no account in its address**.
 *
 * ⚠ **THE SWITCHER IS PRESENT AND THIS SCREEN IS NOT PER ACCOUNT**, the same
 * shape `CWP-024` takes and for the same reason: how a customer wants to be
 * reached is decided once and written to every account the login holds. The
 * body says how far the save reaches so the two cannot read as contradicting.
 */
export function PreferencesPage(props: { client?: ApiClient }) {
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
  // ⚠ **`useCurrentAccount` AND NOT A `useState` HERE — THIS FILE WAS THE ONE
  // PAGE THAT STILL HELD THE SWITCHER PER PAGE** (`DEF-CWP-3841`, whose own
  // write-up says *"sixteen files had it and one did not"*; a grep on
  // 2026-09-08 found seventeen and this one). A switcher held per page means
  // choosing `22 Palm Ct` on Usage and then pressing *How we contact you*
  // silently puts the customer back on the first account in the list.
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
      <PreferencesView />
    </PortalShell>
  );
}
