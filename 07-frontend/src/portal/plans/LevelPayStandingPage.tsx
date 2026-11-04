// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-055 (EP-CWP-10). Screen: CWP-066 at
//           `/{tenant}/portal/level-pay/standing`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-047 (nothing cached) ·
//           B14 rule 31 (no account id in the address — the switcher names it)
// Tests:    src/portal/plans/LevelPayStanding.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · screenIds.ts
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { Signed } from "../requests/RequestsPage";
import { LevelPayStandingView } from "./LevelPayStanding";

/**
 * `CWP-066` inside the signed-in shell.
 *
 * ⚠ **ITS ADDRESS SITS UNDER `CWP-044`'s AND THAT IS THE RELATIONSHIP.**
 * `/level-pay` is *what would I pay if I joined*; `/level-pay/standing` is
 * *what am I paying and where do I stand*. Two addresses because they are two
 * places a customer is sent — the first from the plans tab, the second from a
 * *how am I doing* link on the bill — and a tab state cannot be put in a link.
 */
export function LevelPayStandingPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  return (
    <Signed client={props.client}>
      {(accountId) =>
        accountId ? (
          <LevelPayStandingView accountId={accountId} />
        ) : (
          <p className="text-body text-neutral-600">{t("portal.home.noAccountsYet")}</p>
        )
      }
    </Signed>
  );
}
