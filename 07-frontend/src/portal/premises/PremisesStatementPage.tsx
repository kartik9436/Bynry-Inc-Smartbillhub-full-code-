// ── Trace ──────────────────────────────────────────────
// Story:    CR-142-BRC07 Phase 4 · `P4.15`. Screen: CWP-078 at
//           `/{tenant}/portal/property` (⚠ NO id in the address — the
//           switcher already knows WHICH account, and a database id in a URL
//           is a database id on screen, B14 rule 31)
// Rules:    CR-068 §11c (one page per route) · B14 rule 36 (compose the kit) ·
//           rule 17 (a login with no account says what fills the page) ·
//           BR-CWP-047 (the statement itself never caches; only the SHELL's
//           branding and session are queried)
// Tests:    src/portal/premises/PremisesStatement.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · portal/routing/screenIds.ts
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
import { PremisesStatementView } from "./PremisesStatement";

/**
 * The calendar month the statement opens on.
 *
 * ⚠ **THE SCREEN DECIDES THE WINDOW AND THE SERVER REFUSES TO** (`BR-TEN-043`,
 * and the endpoint's own docstring): a route that defaulted the period would
 * put a window on the page the reader never asked for, and would answer a
 * bookmark differently next month. The caller holding the date is this.
 *
 * ⚠ **A CALENDAR MONTH, NOT THIRTY DAYS.** `P4.12` ruled the same thing for
 * the dashboard and the reasoning carries: *"thirty days straddles two cycles
 * and answers nobody's question"*. A bill covers a period; a statement that
 * cut across two of them would not foot to either.
 */
export function currentMonth(today: Date): { from: string; to: string } {
  const first = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), 1));
  const last = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth() + 1, 0));
  return { from: iso(first), to: iso(last) };
}

function iso(value: Date): string {
  return value.toISOString().slice(0, 10);
}

/** `CWP-078` inside the signed-in shell. */
export function PremisesStatementPage(props: { client?: ApiClient; today?: Date }) {
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
  const window = currentMonth(props.today ?? new Date());
  return (
    <PortalShell
      front={frontQuery.data}
      displayName={session.customer.display_name}
      accounts={session.accounts}
      currentAccountId={accountId}
      onAccountChange={setCurrent}
    >
      {accountId ? (
        <PremisesStatementView accountId={accountId} from={window.from} to={window.to} />
      ) : (
        // B14 rule 17 — a login with no account yet says what fills the page.
        <p className="text-body text-neutral-600" data-statement-noaccount="">
          {t("portal.property.noAccount")}
        </p>
      )}
    </PortalShell>
  );
}
