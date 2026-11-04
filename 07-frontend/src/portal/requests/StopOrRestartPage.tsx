// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-062 (EP-CWP-11). Screen: CWP-052 at
//           `/{tenant}/portal/stop-or-restart`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-047 (nothing here is
//           cached) · B14 rule 31 (no account id in the address — the
//           switcher names the account)
// Tests:    src/portal/requests/StopOrRestart.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · screenIds.ts
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getSession } from "../api/portalClient";
import { Signed } from "./RequestsPage";
import { useSignedOutState } from "./signedOutState";
import { StopOrRestartView } from "./StopOrRestart";

/**
 * `CWP-052` inside the signed-in shell.
 *
 * ⚠ **THIS ONE NEEDS THE ACCOUNT AND `CWP-046` DOES NOT, AND THE DIFFERENCE IS
 * THE MONEY.** The standing charge and the connection fee are the ACCOUNT's own
 * plan's, so a landlord holding four accounts has four different answers; the
 * request hub next door is the LOGIN's list and could not be narrowed. The
 * ADDRESS still carries no id either way — the switcher names the account
 * (B14 rule 31).
 */
export function StopOrRestartPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  /**
   * ⚠ **A CUSTOMER SIGNED OUT AT THIS ADDRESS USED TO MEET THE STAFF FAILURE
   * PANEL — `DEF-CWP-4931`, R-10 and `CPB-17`.** Measured at 1280 and 390 on
   * 2026-09-11: *Failed · We could not open this page · You're signed out.
   * Sign in again to continue.* with **Retry · Download error report ·
   * Cancel** — an engineer's control on a customer's screen, and no way to
   * sign in beside the one sentence telling them to.
   */
  const unread = useSignedOutState();
  /**
   * ⚠ **THE SAME QUERY KEY `Signed` ALREADY HOLDS, SO THIS COSTS NO REQUEST.**
   * Wireframe s20's first step is *which property*, and `Signed` hands down
   * only the CHOSEN account's id — enough for the money, not enough to draw a
   * chooser. React Query answers `["portal","session"]` out of the cache the
   * frame above has already filled, so this reads the list rather than fetching
   * it, and the chooser writes back through `useCurrentAccount` — the same
   * context the switcher in the bar uses, so the two cannot disagree about
   * which property is being stopped (`DEF-CWP-3841`'s lesson).
   */
  const session = useQuery({
    queryKey: ["portal", "session"],
    queryFn: () => getSession(client),
  });
  return (
    <Signed
      client={props.client}
      whenUnread={(state) => unread(state, t("portal.stopRestart.reading"))}
    >
      {(accountId) =>
        accountId ? (
          <StopOrRestartView accountId={accountId} accounts={session.data?.accounts} />
        ) : (
          // B14 rule 17 — a login with no account yet says what fills the page.
          <p className="text-body text-neutral-600">{t("portal.home.noAccountsYet")}</p>
        )
      }
    </Signed>
  );
}
