// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-057 (CWP-057 at `/{tenant}/portal/overdue`) · US-CWP-058
//           (CWP-056 at `/help-paying`) · US-CWP-059 (CWP-064 at
//           `/protections`) · US-CWP-056 (CWP-045 at `/money-back`)
// Rules:    CR-068 §11c (one page per route) · BR-CWP-013 (the switcher picks
//           WHICH account) · B14 rule 31 (no database id in the address)
// Tests:    src/portal/arrears/*.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · screenIds.ts
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";
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
import { HelpPayingView } from "./HelpPaying";
import { MoneyBackView } from "./MoneyBack";
import { OverdueView } from "./Overdue";
import { ProtectionsView } from "./Protections";

/**
 * The shell all four arrears screens share — **the switcher names the account
 * and the address never does** (B14 rule 31, `/account`'s own reading).
 *
 * ⚠ **ONE WRAPPER RATHER THAN FOUR NEAR-IDENTICAL ONES.** `YourPlanPage`,
 * `LevelPayPage`, `PlanOfferPage` and `AskForPlanPage` are four copies of this
 * same twenty lines; writing a fifth, sixth, seventh and eighth is how a
 * loading state or a refusal comes to differ between screens a customer moves
 * between in one sitting.
 *
 * ⚠ **THE SWITCHER IS THE SHARED ONE, NOT A `useState` PER PAGE
 * (`US-CWP-023`).** A local piece of state here would render a control that
 * looks like an account switcher, moves, and is forgotten the moment the
 * customer follows a link — which is the defect `currentAccount.tsx` was
 * written to close, and these four screens are exactly the ones a landlord
 * moves between in one sitting.
 */
function ArrearsPage(props: { client?: ApiClient; render: (accountId: string) => ReactNode }) {
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
        props.render(accountId)
      ) : (
        <p className="text-body text-neutral-600">{t("portal.home.noAccountsYet")}</p>
      )}
    </PortalShell>
  );
}

/** `CWP-057` — what happens if this is not paid, and what it would cost. */
export function OverduePage(props: { client?: ApiClient }) {
  return (
    <ArrearsPage
      client={props.client}
      render={(accountId) => <OverdueView accountId={accountId} />}
    />
  );
}

/** `CWP-056` — help paying: three doors, and one of them is not a door. */
export function HelpPayingPage(props: { client?: ApiClient }) {
  return (
    <ArrearsPage
      client={props.client}
      render={(accountId) => <HelpPayingView accountId={accountId} />}
    />
  );
}

/** `CWP-064` — what is protecting your supply. */
export function ProtectionsPage(props: { client?: ApiClient }) {
  return (
    <ArrearsPage
      client={props.client}
      render={(accountId) => <ProtectionsView accountId={accountId} />}
    />
  );
}

/** `CWP-045` — credits and refunds in flight, and they are different things. */
export function MoneyBackPage(props: { client?: ApiClient }) {
  return (
    <ArrearsPage
      client={props.client}
      render={(accountId) => <MoneyBackView accountId={accountId} />}
    />
  );
}
