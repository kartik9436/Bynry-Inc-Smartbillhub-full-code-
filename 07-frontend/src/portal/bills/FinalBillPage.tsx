// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-037 (EP-CWP-07). Screen: CWP-032 at
//           `/{tenant}/portal/final-bill`
// Rules:    CR-068 §11c (one page per route) · BR-CWP-047 (nothing cached) ·
//           B14 rule 31 (no account id in the address — the switcher names it)
// Tests:    src/portal/bills/FinalBill.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · screenIds.ts
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { Signed } from "../requests/RequestsPage";
import { useSignedOutState } from "../requests/signedOutState";
import { FinalBillView } from "./FinalBill";

/**
 * `CWP-032` inside the signed-in shell.
 *
 * ⚠ **IT COMPOSES `Signed` RATHER THAN A FOURTH COPY OF THE SHELL QUERIES.**
 * The branding-plus-session pair is identical on every signed-in screen, and a
 * copy of it is a copy of the account switcher's scoping — which is exactly the
 * defect `DEF-CWP-3900` records (a switcher held per page). `Signed` reads the
 * shared `useCurrentAccount` context, so choosing another property on Usage and
 * then opening the final bill shows THAT property's closing bill.
 */
export function FinalBillPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  /**
   * ⚠ **R-10 AND `CPB-17` — `DEF-CWP-4931`.** Signed out, this address drew
   * the STAFF panel with a **Download error report** button and no way to sign
   * in. It is the last screen a leaving customer ever opens, so it is the
   * worst place in the product to answer them with an engineer's control.
   */
  const unread = useSignedOutState();
  return (
    <Signed
      client={props.client}
      whenUnread={(state) => unread(state, t("portal.finalBill.reading"))}
    >
      {(accountId) =>
        accountId ? (
          <FinalBillView accountId={accountId} />
        ) : (
          <p className="text-body text-neutral-600">{t("portal.home.noAccountsYet")}</p>
        )
      }
    </Signed>
  );
}
