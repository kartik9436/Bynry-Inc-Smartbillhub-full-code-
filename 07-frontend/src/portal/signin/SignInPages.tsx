// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-016..020 (EP-CWP-05) — the FIVE getting-in routes.
//           ⚠ **THIS READ `EP-CWP-03` AND *four* UNTIL 2026-09-05 —
//           `DEF-CWP-3862`.** `EP-CWP-03` is *report a problem*; getting in
//           is `EP-CWP-05`, and 016..020 is five stories, not four.
//           ⚠ **THE WAVE-E SERIES WAS MISALIGNED — `DEF-CWP-3862`, corrected
//           2026-09-05. `EP-CWP-05` is the authority and NOTHING IS
//           RENUMBERED.** The screen ids were right all along; the STORY ids
//           in these headers were not. The map, both ways:
//             CWP-015 = US-CWP-016 the front door (sign in + three doors)
//             CWP-016 = US-CWP-017 find my account
//             CWP-017 = US-CWP-018 prove it is you (the code)
//             CWP-018 = US-CWP-019 choose a password
//             CWP-019 = US-CWP-020 forgotten password
//           Two series one apart make every wrong pairing look plausible, so
//           each header below cites BOTH — `US-CWP-018 (CWP-017)` — which is
//           the only form in which a bad pairing is visible on the line.
//           Screens: CWP-015 · CWP-016 · CWP-017 · CWP-018 · CWP-019 · CWP-022
// Rules:    BR-CWP-005 (an unknown utility on the address answers 404, the
//           same shape as a foreign one) · CR-068 §11c (one page per route) ·
//           B14 rule 36 (compose the shared kit)
// Tests:    src/portal/signin/Enrol.dom.test.tsx ·
//           src/portal/signin/ForgotPassword.dom.test.tsx. ⚠ **`SignIn.test
//           .tsx` AND `Enrol.test.tsx` BOTH NAMED HERE DO NOT EXIST
//           (`DEF-CWP-3862`, 2026-09-05) — the enrolment cases live in
//           `Enrol.dom.test.tsx`.** ⚠ **AND *"the reset has no test file at
//           all"* STOPPED BEING TRUE IN THE `CR-085` GUEST-ENTRANCE PASS**,
//           which wrote `ForgotPassword.dom.test.tsx`. **THE FRONT DOOR
//           (`CWP-015`, `FrontDoor.tsx`) STILL HAS NONE** — that half of
//           `DEF-CWP-3862` is open.
// Impacts:  src/portal/routing/portalRoutes.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE THREE ENROLMENT SCREENS SIT INSIDE THE `GuestFrame` AND NOT INSIDE
// THE `PortalShell`, AND THAT IS THE POINT OF THEM.** A person on `CWP-016` is
// not signed in — there is no account set to scope a tab strip to and no
// avatar to draw. Wrapping them in the shell would put six tabs above somebody
// who cannot open any of them.

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { queryKeys } from "@/api/queryClient";
import { getPortalFront } from "../api/guestClient";
import { getSession } from "../api/portalClient";
import { refusalText } from "@/api/refusalText";
import { GuestPage } from "../guest/GuestPage";
import { PortalShell } from "../shell/PortalShell";
import { resolveCurrentAccount, useCurrentAccount } from "../shell/currentAccount";
import { EnrolView } from "./Enrol";
import { ForgotPasswordView } from "./ForgotPassword";
import { FrontDoorView } from "./FrontDoor";
import { HomeView } from "../home/Home";

/** The utility's own branding, read once and shared by every page here. */
function useFront(client: ApiClient) {
  return useQuery({ queryKey: queryKeys.portalFront, queryFn: () => getPortalFront(client) });
}

/**
 * ⚠ **`GuestPageFrame` IS GONE AND THESE THREE SCREENS COMPOSE `GuestPage` —
 * `DEF-CWP-4851`, `CR-085` step 2 (2026-09-11).**
 *
 * It was a byte-for-byte copy of `guest/GuestPage.tsx` **minus one line**: the
 * line that reads `front.is_live`. So a utility that had not switched its
 * portal on served the holding page at `/{tenant}/portal` and, one address
 * over, **a live sign-in box, the whole three-step enrolment wizard and a live
 * password-reset mailer**, to anyone on the open internet who had bookmarked
 * one. Measured in a browser at 390 and at 1280 with `is_live:false` on the
 * wire: all three screens rendered in full.
 *
 * ⚠ **NOTHING COULD SEE IT, AND THE REASON IS WORTH THE PARAGRAPH.** Each
 * screen is tested at its own address against a fixture whose `is_live` is
 * true, so the question *does this screen respect the switch* belonged to no
 * test — `DEF-CWP-3925`'s shape one layer down. `tsc`, eslint and 960 cases
 * passed over it. And the duplicate read as diligence rather than as a defect:
 * it is short, it is correct about everything it does do, and the missing
 * line is invisible unless you diff it against the file it was copied from.
 *
 * **So the fix is not a fourth copy with the line put back — it is to delete
 * the copy** (B14 rule 36). `GuestPage` carries the rule, its docstring says
 * why, and a screen that composes it cannot forget.
 */

export function SignInPage(props: { client?: ApiClient }) {
  const client = props.client ?? api;
  const frontQuery = useFront(client);
  return (
    <GuestPage client={client}>
      {frontQuery.data ? <FrontDoorView front={frontQuery.data} /> : null}
    </GuestPage>
  );
}

export function EnrolPage(props: { client?: ApiClient }) {
  return (
    <GuestPage client={props.client}>
      <EnrolView />
    </GuestPage>
  );
}

export function ForgotPasswordPage(props: { client?: ApiClient }) {
  return (
    <GuestPage client={props.client}>
      <ForgotPasswordView />
    </GuestPage>
  );
}

/**
 * `CWP-022` inside the shell.
 *
 * ⚠ **THE SWITCHER'S VALUE IS STATE HERE AND A QUERY PARAMETER ON EVERY READ**
 * (`BR-CWP-010`). Changing it re-scopes every tab because every tab's read
 * carries it to the server, which intersects it with the session's own set —
 * not because this component filters anything. `HomeView` reads
 * `balance/summary`, which is the whole set by design: the lead tile is *what
 * do I owe*, and for a landlord that is four rows and a total.
 */
export function HomePage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const frontQuery = useFront(client);
  const sessionQuery = useQuery({ queryKey: ["portal", "session"], queryFn: () => getSession(client) });
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
      <HomeView />
    </PortalShell>
  );
}
