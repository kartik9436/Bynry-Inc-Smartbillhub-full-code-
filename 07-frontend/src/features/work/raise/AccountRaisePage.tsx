// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 3, lane RAISE — image 19, *Raise from an
//           account* (1·4e): ruling 35, P2.4, DEF-WRK-4752.
// Rules:    B14 rule 3 (the step bar is the head) · rule 31 · rule 42.
// Tests:    src/features/work/raise/cr168RaiseAccount.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **A PAGE OF ITS OWN AND NOT A CHILD OF THE ACCOUNT PAGE.** The account's
// eight quick actions are child routes drawn in a dialog over the account
// (`BR-CUS-1051`); image 19 draws this one full page, under *ACCOUNTS ›
// AC-… › NEW ORDER*, with the Accounts nav lit. So `App.tsx` mounts it beside
// the account route, the way the standalone Move-in and Move-out are.
import { useParams } from "react-router-dom";

import type { ApiClient } from "@/api/client";

import { RaiseWizard } from "./RaiseWizard";

/** The route pattern — no `/:tenant`, like every route constant (`DEF-WRK-4051`). */
export const ACCOUNT_RAISE_ROUTE = "/accounts/:accountId/work-orders/new";

/** The screen-registry spelling, which carries the tenant. */
export const ACCOUNT_RAISE_SCREEN_PATH = `/:tenant${ACCOUNT_RAISE_ROUTE}`;

export function accountRaisePath(accountId: string): string {
  return `/accounts/${encodeURIComponent(accountId)}/work-orders/new`;
}

export function AccountRaisePage(props: { client?: ApiClient }) {
  const { accountId = "" } = useParams();
  return <RaiseWizard origin={{ kind: "account", accountId }} client={props.client} />;
}
