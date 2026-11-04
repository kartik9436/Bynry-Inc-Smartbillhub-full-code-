// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-050 (EP-CWP-09). Screen: CWP-050 at
//           `/{tenant}/portal/fees`
// Rules:    CR-068 §11c (one page per route) · B14 rule 31 · rule 32 ·
//           BR-CWP-093 (nothing empty ever appears) · CR-068 R8 (a portal that
//           is OFF shows the holding page on EVERY route)
// Change:   CR-085 (2026-09-08) — a stranger may open this address. See
//           `PublicPricesView` below for what they are shown and why it is not
//           the price list the drawing asks for.
// Tests:    src/portal/payments/Fees.dom.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx (already registered)
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { getPortalFront } from "../api/guestClient";
import { getSession } from "../api/portalClient";
import { GuestPage } from "../guest/GuestPage";
import { Card, ErrandLink } from "../components/primitives";
import { PortalShell } from "../shell/PortalShell";
import { resolveCurrentAccount, useCurrentAccount } from "../shell/currentAccount";
import { FeesView } from "./Fees";

/**
 * A 401 is a VISITOR, not a fault — `AUTH-001` on `GET /portal/session`.
 *
 * ⚠ **TELLING THOSE TWO APART IS THE WHOLE OF THIS FIX.** Every signed-in
 * portal page treats *no session* and *the server broke* as one outcome
 * (`data === undefined`), which is right on a page only a customer can use and
 * wrong on this address: a stranger who typed `/fees` was shown a grey **Failed
 * · We could not open this page · Download error report** card, outside the
 * utility's frame, with no nav and no way back. Nothing was broken.
 */
function signedOut(error: unknown): boolean {
  return isApiError(error) && error.status === 401;
}

/**
 * `CWP-050` inside the signed-in shell.
 *
 * ⚠ **THIS FILE REPLACED A `ComingSoon` HOLDING SCREEN.** The route was
 * registered before any phase-5 lane started so `portalRoutes.tsx` and
 * `screenIds.ts` were written ONCE (law 11), and replacing the holding
 * component is the first act of the wave that owns it.
 *
 * ⚠ **NO ACCOUNT SWITCHER READ ON THE VIEW ITSELF, AND THAT IS DELIBERATE.**
 * The fees belong to a REQUEST, and the request belongs to the person rather
 * than to one account — an APPLICANT may not have an account at all yet. The
 * shell still renders the switcher because the frame is the frame, and
 * `FeesView` takes no account id.
 *
 * ⚠ **AND SINCE `CR-085` IT ANSWERS A STRANGER TOO.** One address, two
 * readers: a signed-in applicant reads what THEY have been quoted; a visitor
 * reads what the utility charges everybody. The second half is the drawing's
 * *Prices and fees*, and what it can honestly show today is stated in
 * `PublicPricesView`.
 */
export function FeesPage(props: { client?: ApiClient }) {
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
  // ⚠ **THE VISITOR'S BRANCH COMES FIRST, AND IT GOES THROUGH `GuestPage`
  // RATHER THAN STRAIGHT TO `GuestFrame`.** That is not tidiness: `GuestPage`
  // is where `CR-068` R8 is checked, so a utility that has switched its portal
  // off shows the holding page on this address like on every other. Reaching
  // for the frame directly would have made `/fees` the one guest screen that
  // stayed live after the switch was thrown.
  if (sessionQuery.data === undefined && signedOut(sessionQuery.error)) {
    return (
      <GuestPage client={client}>
        <PublicPricesView phone={frontQuery.data?.emergency_phone ?? null} />
      </GuestPage>
    );
  }
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
      <PageHeader kicker={t("portal.fees.kicker")} title={t("portal.fees.title")} />
      <FeesView />
    </PortalShell>
  );
}

/**
 * `CWP-050` AS A STRANGER SEES IT — the drawing's *Prices and fees*.
 *
 * ⚠ **IT DOES NOT DRAW THE PRICE LIST, AND THAT IS A DELIBERATE ABSENCE RATHER
 * THAN AN OVERSIGHT.** The drawing shows water tiers, base charges, fire-line
 * sizes and eleven one-off fees, and **every one of those figures is in the
 * database already** — the residential water tariff in force from 1 Aug 2026
 * carries `4.2400 / 6.8900 / 8.4800` per kgal, `BASE-W` is `8.0000`, and the
 * charge catalogue holds `CONN 45.00`, `RECON 45.00`, `NSF 30.00`,
 * `CC-CONV 2.95`, `PAPER 2.00` and `LATE 1.5% min 5.00`, figure for figure as
 * drawn.
 *
 * **What is missing is not data. It is the RULING about which of it is
 * public.** A tenant here has four published plans and twelve tariff versions;
 * `rating.TariffVersion.publish_public` exists for exactly this question, is
 * marked *capture-only v1 (no A1 screen)* in its own model, has never been
 * wired to anything, and is `false` on all twelve rows. Picking a plan, or
 * publishing everything, or reading that flag as the gate are three different
 * answers with three different consequences for a utility, and the prime
 * directive is unambiguous: an open question is not resolved by choosing a
 * value. So this screen is built to the boundary and the content is left
 * absent.
 *
 * ⚠ **WHICH IS ALSO THE DRAWING'S OWN STATE FOR THIS PAGE** — *"Not published:
 * The utility has not turned this page on: the phone number, not an empty
 * page."* One sentence and the number, never a heading with nothing under it
 * (`BR-CWP-093`, B14 rule 32).
 *
 * ⚠ **AND ONE REAL DOOR, BECAUSE ONE PRICE *IS* PUBLIC TODAY.**
 * `POST /public/premises/availability` quotes a connection fee and a deposit to
 * anybody who types an address, which is `CWP-008` at `/start-service` — the
 * only place in this product where a stranger reads a figure. Pointing at it is
 * worth more than repeating the phone number twice.
 */
function PublicPricesView(props: { phone: string | null }) {
  const { t } = useTranslation();
  return (
    <div data-screen="CWP-050">
      <PageHeader
        kicker={t("portal.fees.kicker")}
        title={t("portal.card.what_things_cost.title")}
        rollup={t("portal.card.what_things_cost.description")}
      />
      {/* ⚠ The card and the panel below it are two surfaces and they were
          drawn edge to edge — `Card` carries no outer margin and `Panel`'s
          `mb-4` is on its BOTTOM. Seen by looking at 390, which is the only way
          it could be (hard-won law 6). */}
      <div className="mb-4">
        <Card testId="fees-public">
          <p className="m-0 text-body text-neutral-700" data-prices-not-published="">
            {t("portal.fees.notPublishedHere")}
          </p>
          {props.phone ? (
            <p className="m-0 text-lead font-bold text-neutral-900" data-prices-phone="">
              {props.phone}
            </p>
          ) : null}
        </Card>
      </div>
      <Panel as="aside" title={t("portal.card.start_service.title")}>
        <p className="m-0 text-body text-neutral-700">
          {t("portal.card.start_service.description")}
        </p>
        {/* ⚠ A REAL DESTINATION, ASSERTED BY ADDRESS IN THE TEST rather than by
            label (`DEF-CWP-3925`): `/start-service` is routed, live, and is
            where a visitor gets a priced answer today. */}
        <div className="mt-3">
          <ErrandLink label={t("portal.card.start")} to="/start-service" />
        </div>
      </Panel>
    </div>
  );
}
