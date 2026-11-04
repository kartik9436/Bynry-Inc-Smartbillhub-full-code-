// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-040 · US-CWP-041 · US-CWP-043 (EP-CWP-08). Screens CWP-033
//           at `/{tenant}/portal/usage`, CWP-034 at `/…/readings`, CWP-037 at
//           `/…/equipment`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-010 (changing the
//           switcher re-scopes every tab — the account id comes from the
//           SESSION's set, never from the address) · B14 rule 31 (no database
//           id in a URL either) · BR-CWP-047 (nothing here is cached)
// Tests:    src/portal/usage/Usage.dom.test.tsx ·
//           src/portal/usage/Readings.dom.test.tsx ·
//           src/portal/usage/Equipment.dom.test.tsx
// Defects:  DEF-CWP-3903 — the two continuation citations were bare
//           filenames, which resolve against no root, so G95 reported two
//           real and passing tests as missing. A Trace line is read by a
//           machine as well as by a person: every path on it is written
//           from the repo root.
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
import { EquipmentView } from "./Equipment";
import { ReadingsView } from "./Readings";
import { SendReadingView } from "./SendReading";
import { UsageView } from "./Usage";

/**
 * The shell all three of wave H's screens sit in.
 *
 * ⚠ **NO ACCOUNT ID IN ANY OF THESE ADDRESSES** (B14 rule 31, and `CWP-065`
 * took the same decision one wave earlier): the switcher knows which account is
 * being read, and a uuid in a URL is a database id on screen. The id handed to
 * the view comes from the session's own set, which is also what makes
 * `BR-CWP-010` hold — a customer cannot type another account into the bar.
 *
 * ⚠ **ONE WRAPPER, THREE SCREENS, AND THAT IS THE KIT RULE APPLIED TO A PAGE**
 * (B14 rule 36). Three copies of the same twenty lines is how three screens
 * start disagreeing about what to draw while the session is loading.
 */
function UsageFrame(props: { client?: ApiClient; render: (accountId: string) => JSX.Element }) {
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
      {/* An account set can be empty only in a state enrolment refuses to
          create, so this is a guard rather than a screen — and it says so
          rather than rendering a chart of nothing. */}
      {accountId === null ? (
        <p className="text-body text-neutral-600">{t("portal.usage.noAccount")}</p>
      ) : (
        props.render(accountId)
      )}
    </PortalShell>
  );
}

/** `CWP-033` — usage. */
export function UsagePage(props: { client?: ApiClient }) {
  return <UsageFrame client={props.client} render={(id) => <UsageView accountId={id} />} />;
}

/** `CWP-034` — every reading. */
export function ReadingsPage(props: { client?: ApiClient }) {
  return <UsageFrame client={props.client} render={(id) => <ReadingsView accountId={id} />} />;
}

/** `CWP-037` — meters and equipment. */
/** `CWP-035` — *Send us your reading* (`US-CWP-042`, `DEF-CWP-10175`). */
export function SendReadingPage(props: { client?: ApiClient }) {
  return <UsageFrame client={props.client} render={(id) => <SendReadingView accountId={id} />} />;
}

export function EquipmentPage(props: { client?: ApiClient }) {
  return <UsageFrame client={props.client} render={(id) => <EquipmentView accountId={id} />} />;
}
