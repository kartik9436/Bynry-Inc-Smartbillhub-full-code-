// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-063 · US-CWP-065 · US-CWP-066 (EP-CWP-11).
//           Screens: CWP-051 · CWP-055 · CWP-054
// Rules:    CR-068 §11c (one page per route) · BR-CWP-047 (nothing here is
//           cached — a request's state moves when a clerk touches it) ·
//           B14 rule 31 (`:reference` is an `SR-` number and `:number` is a
//           `BL-` number; not one database id between them)
// Tests:    src/portal/requests/TrackRequest.dom.test.tsx ·
//           DisputeBill.dom.test.tsx · AskAQuestion.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · screenIds.ts
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useParams, useSearchParams } from "react-router-dom";
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
import { AskAQuestionView } from "./AskAQuestion";
import { DisputeBillView } from "./DisputeBill";
import { TrackRequestView } from "./TrackRequest";

/**
 * The shell every one of these three screens sits inside — written once here
 * rather than three times, which is the same move `BillPages.tsx` makes.
 *
 * ⚠ **THE SWITCHER IS DRAWN AND THE SCREENS DO NOT READ IT, AND THAT IS
 * CORRECT.** A service request belongs to a person rather than to one account
 * (`OQ-CWP-1680` is the question of what makes one *theirs* at all), and a bill
 * is named by its own number. The switcher stays because removing it from three
 * screens in a shell that has it everywhere else would read as a bug.
 */
function InsideTheShell(props: { client?: ApiClient; children: ReactNode }) {
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
      {props.children}
    </PortalShell>
  );
}

/** `CWP-051` at `/{tenant}/portal/requests/:reference`. */
export function TrackRequestPage(props: { client?: ApiClient }) {
  const { reference } = useParams();
  return (
    <InsideTheShell client={props.client}>
      <TrackRequestView reference={reference ?? ""} />
    </InsideTheShell>
  );
}

/** `CWP-055` at `/{tenant}/portal/bills/:number/dispute`. */
export function DisputeBillPage(props: { client?: ApiClient }) {
  const { number } = useParams();
  return (
    <InsideTheShell client={props.client}>
      <DisputeBillView number={number ?? ""} />
    </InsideTheShell>
  );
}

/**
 * `CWP-054` at `/{tenant}/portal/ask-a-question`, optionally `?bill=BL-…`.
 *
 * ⚠ **THE BILL ARRIVES IN A QUERY STRING AND NOT IN THE PATH**, because a
 * question with no bill is a normal question (`US-CWP-066` TC-5) and a path
 * segment cannot be absent. It is a bill NUMBER either way — never a row id
 * (B14 rule 31).
 */
export function AskAQuestionPage(props: { client?: ApiClient }) {
  const [search] = useSearchParams();
  return (
    <InsideTheShell client={props.client}>
      <AskAQuestionView billNumber={search.get("bill")} />
    </InsideTheShell>
  );
}
