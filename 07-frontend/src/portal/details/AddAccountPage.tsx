// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-027 (EP-CWP-06). Screen: CWP-020 at
//           `/{tenant}/portal/accounts/add`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-033 (the code goes to the ADDED
//           account's own contact, never to the person adding it)
// Tests:    src/portal/details/AddAccount.dom.test.tsx
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
import { getMyAccounts, getSession } from "../api/portalClient";
import { PortalShell } from "../shell/PortalShell";
import { resolveCurrentAccount, useCurrentAccount } from "../shell/currentAccount";
import { AddAccountView } from "./AddAccount";

/**
 * `CWP-020` — the form that grows the account set.
 *
 * ⚠ **THE SWITCHER IS THE REASON THIS SCREEN EXISTS AND IS ALSO WHAT PROVES
 * IT WORKED.** A landlord adds their fifth account here and sees five in the
 * switcher on the next page; the set is re-derived on every request
 * (`BR-CWP-009`), so nothing on this page caches it and nothing needs to.
 */
export function AddAccountPage(props: { client?: ApiClient }) {
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
  //: ⚠ **THE BALANCES COME FROM THE SAME READ `CWP-023` TOTALS, NOT FROM A
  //: SECOND OPINION.** `BR-CWP-047` says no portal screen caches a balance,
  //: so this is a live read like every other; and using `my-accounts` rather
  //: than composing a figure here means the rail and the accounts list can
  //: never disagree about what an account owes. A failure is not fatal — the
  //: rail falls back to the account numbers it drew before.
  const balancesQuery = useQuery({
    queryKey: ["portal", "my-accounts", "add-account-rail"],
    //: ⚠ **THE RAIL WANTS EVERY ACCOUNT, SO IT ASKS FOR THEM** — `getMyAccounts`
    //: takes a page since `DEF-CWP-5747` and its default is fifty. This rail is
    //: the switcher's list, not a screen with a footer, so it names the top of
    //: the IS-2 vocabulary rather than accepting a page it cannot turn.
    queryFn: () => getMyAccounts({ per: 1000 }, client),
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
      <AddAccountView
        accounts={session.accounts}
        owing={Object.fromEntries(
          (balancesQuery.data?.accounts ?? []).map((row) => [
            row.id,
            { owing: row.owing, currency: row.currency },
          ]),
        )}
      />
    </PortalShell>
  );
}
