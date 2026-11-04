// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-060 (EP-CWP-11). Screen: CWP-046 at `/{tenant}/portal/requests`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-047 (nothing here is
//           cached; only the shell's branding and session are queried)
// Tests:    src/portal/requests/Requests.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · screenIds.ts ·
//           src/portal/requests/StopOrRestartPage.tsx (composes `Signed`)
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
import { RequestsView } from "./Requests";

/**
 * The signed-in shell every request screen sits in.
 *
 * ⚠ **ONE WRAPPER FOR THE WHOLE EPIC, AND IT IS NOT A SHORTCUT.**
 * `BillPages.tsx` already does this for `CWP-028`, `CWP-029` and `CWP-030`: the
 * branding-plus-session query pair is identical on every signed-in screen, and
 * a second copy of it is a second place the account switcher's scope could go
 * wrong. Each screen still carries its own `data-screen` and its own route.
 *
 * ⚠ **THE CHOSEN ACCOUNT COMES FROM `useCurrentAccount` AND NOT FROM A
 * `useState` HERE — THIS FILE SHIPPED WITH THE `useState` AND IT WAS
 * `DEF-CWP-3900` ALL OVER AGAIN (`DEF-CWP-3841`).** That defect is recorded by
 * a sibling in this same wave: a switcher held per PAGE means choosing
 * `22 Palm Ct` on Usage and then pressing Requests silently puts the customer
 * back on `1408 Elm St · A`. Every other signed-in page had been converted to
 * the shared context; this one was written from a copy that predated the fix,
 * and a `grep` for `useCurrentAccount` across `src/portal` is what found it —
 * sixteen files had it and one did not.
 */
export function Signed(props: {
  client?: ApiClient;
  /**
   * What to draw while the shell's own two reads are in flight, and what to
   * draw when they do not come back.
   *
   * ⚠ **OPTIONAL, AND OMITTING IT LEAVES THIS FILE'S OWN SCREENS BYTE-IDENTICAL
   * — WHICH IS WHY IT IS A PROP AND NOT A REWRITE (`CR-085` step 2 lane 3).**
   * The default below is `@/components/StateFrame`'s `FailedWithRetry`: a red
   * *Failed* pill, *"the address may be wrong"*, and a **Download error
   * report** button. That is the STAFF panel, and on a customer's screen it is
   * wrong twice over — it offers a member of the public an error report they
   * have nowhere to send (`components/states.tsx` says so in its own docstring),
   * and it offers **no way to sign in** to a visitor whose session has ended,
   * which is R-10 (*"the thing they can do about it must be on that same
   * screen, next to the message"*) and blueprint spec `CPB-17` together.
   *
   * ⚠ **IT IS WRONG ON ALL FOUR OF THIS WRAPPER'S ROUTES AND ON TEN MORE PAGE
   * FILES BESIDES — `DEF-CWP-4931`.** Two of the four are `CR-085` lane 3's
   * (`/stop-or-restart`, `/final-bill`) and they pass this prop; the other two
   * belong to lanes running in those files right now, so their behaviour is
   * untouched rather than improved without their knowledge. The defect row
   * carries the full list so the next lane can finish it in one pass.
   */
  whenUnread?: (state: {
    kind: "loading" | "failed";
    /** The refusal's own sentence — `errors.auth-001` is *"You're signed out.
     *  Sign in again to continue."*, which is already right. Empty while
     *  loading, because nothing has refused. */
    sentence: string;
    retry: () => void;
  }) => ReactNode;
  children: (accountId: string | null) => ReactNode;
}) {
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

  const retry = () => void sessionQuery.refetch();
  if (frontQuery.isPending || sessionQuery.isPending) {
    return props.whenUnread ? (
      <>{props.whenUnread({ kind: "loading", sentence: "", retry })}</>
    ) : (
      <LoadingSkeleton variant="card" />
    );
  }
  if (frontQuery.data === undefined || sessionQuery.data === undefined) {
    const sentence = refusalText(t, frontQuery.error ?? sessionQuery.error);
    if (props.whenUnread) return <>{props.whenUnread({ kind: "failed", sentence, retry })}</>;
    return (
      <FailedWithRetry
        title={t("portal.failedTitle")}
        reason={sentence}
        onRetry={retry}
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
      {props.children(accountId)}
    </PortalShell>
  );
}

/**
 * `CWP-046` inside the signed-in shell.
 *
 * ⚠ **IT DOES NOT WAIT FOR AN ACCOUNT AND EVERY OTHER SIGNED-IN PAGE DOES.** A
 * portal service request carries no account at all (`BR-CWP-026`), so the hub
 * is the LOGIN's — and a customer whose account list is empty still has six
 * things they may ask the utility for.
 */
export function RequestsPage(props: { client?: ApiClient }) {
  return <Signed client={props.client}>{() => <RequestsView />}</Signed>;
}
