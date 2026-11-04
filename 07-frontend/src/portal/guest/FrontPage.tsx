// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-001 (EP-CWP-01) — the public front page. Screens: CWP-001
// Rules:    BR-CWP-005 (the tenant is the first path segment — the client
//           reads it off the address, the server resolves it before anything
//           is read) · BR-CWP-093 · CR-068 R8 (off → holding) · B14 rule 21
//           (this folder is on route-b-migrated.txt)
// Tests:    src/portal/guest/FrontPage.test.tsx
// Impacts:  src/portal/api/guestClient.ts · src/api/queryClient.ts
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Navigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";

import { getPortalFront } from "../api/guestClient";
import { getSession } from "../api/portalClient";
import { usePortalPath } from "../components/primitives";
import { GuestFrame } from "../shell/GuestFrame";

import { FrontPageView } from "./FrontPageView";
import { HoldingPage } from "./HoldingPage";

/**
 * `CWP-001` at `/{tenant}/portal`, **and the customer's home page for anybody
 * who is signed in** (`DEF-CWP-4900`).
 *
 * ⚠ **A SIGNED-IN CUSTOMER WHO OPENED `/{tenant}/portal` WAS SHOWN THE GUEST
 * FRONT PAGE WITH A *Sign in* BAR ON IT** — over an errand grid of things they
 * had already done by signing in. That address is the one a utility prints on a
 * bill and puts in an email, so it is the commonest way into the product, and
 * the blueprint spends a page on it: *"The portal serves the home page at both
 * `/{tenant}/portal` and `/{tenant}/portal/home` … **They must render the same
 * screen, not two that drift.**"*
 *
 * ⚠ **THE REDIRECT LIVES HERE AND NOT IN THE ROUTE TABLE, DELIBERATELY.**
 * `portalRoutes.tsx` is one file four lanes share and its own comment says
 * NO LANE TOUCHES IT (hard-won law 11 — the second lane to commit a shared file
 * silently reverts the first). One route entry still points at one component;
 * what changed is what that component decides.
 *
 * ⚠ **THE GUEST PAGE RENDERS WHILE THE SESSION READ IS IN FLIGHT, WHICH IS THE
 * RIGHT WAY ROUND AND IS STATED RATHER THAN LEFT TO BE FOUND.** Most visits to
 * this address have no session, so blocking the public page on an auth probe
 * would slow every one of them to show a skeleton to a stranger. A signed-in
 * customer arriving from inside the app has the session already in the cache
 * and never sees the guest page at all; one arriving cold on an emailed link
 * sees it for as long as `GET /portal/session` takes. `retry: false` keeps the
 * ordinary 401 a guest gets to exactly one request.
 */
export function FrontPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const path = usePortalPath();
  const frontQuery = useQuery({
    queryKey: queryKeys.portalFront,
    queryFn: () => getPortalFront(client),
  });
  //: The SAME key `HomePage` reads, so a customer who signed in a moment ago is
  //: already answered from the cache and two components cannot hold two
  //: opinions about whether somebody is signed in.
  const sessionQuery = useQuery({
    queryKey: ["portal", "session"],
    queryFn: () => getSession(client),
    retry: false,
  });

  if (sessionQuery.data !== undefined) {
    //: ⚠ **`replace`, so Back does not bounce between the two addresses.**
    return <Navigate to={path("/home")} replace />;
  }
  if (frontQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (frontQuery.data === undefined) {
    // An unknown utility on the address answers 404 (BR-CWP-005) — the same
    // shape as a foreign one, and the same sentence.
    return (
      <FailedWithRetry
        title={t("portal.failedTitle")}
        reason={refusalText(t, frontQuery.error)}
        onRetry={() => void frontQuery.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }
  const front = frontQuery.data;
  return (
    <GuestFrame front={front}>
      {front.is_live ? <FrontPageView front={front} /> : <HoldingPage front={front} />}
    </GuestFrame>
  );
}
