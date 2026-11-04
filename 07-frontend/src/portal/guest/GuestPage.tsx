// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-012 · 013 · 014 · 015 (EP-CWP-04) — every wave-C screen
//           lives inside the same frame as CWP-001. Screens: CWP-008 ·
//           CWP-047 · CWP-009 · CWP-010
// Rules:    BR-CWP-005 (the tenant is the first path segment; the frame is
//           drawn from the front-page read, so a screen cannot render before
//           the tenant has resolved) · CR-068 R8 (a portal that is OFF shows
//           the holding page and nothing else, on EVERY route) · B14 rule 21
// Tests:    src/portal/guest/StartService.test.tsx
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";

import { getPortalFront } from "../api/guestClient";
import { GuestFrame } from "../shell/GuestFrame";

import { HoldingPage } from "./HoldingPage";

/**
 * The frame every guest screen after `CWP-001` sits in.
 *
 * ⚠ **THE PORTAL BEING OFF IS CHECKED ON EVERY ROUTE, NOT ONLY THE FRONT
 * PAGE.** A utility that switched the portal off and still served
 * `/pine-hill/portal/start-service` would have turned nothing off — the front
 * page would be a holding notice with four live screens behind it, reachable
 * by anyone who had bookmarked one. So the switch is read here, once, and
 * every screen inherits it.
 */
export function GuestPage(props: { client?: ApiClient; children: ReactNode }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const frontQuery = useQuery({
    queryKey: queryKeys.portalFront,
    queryFn: () => getPortalFront(client),
  });

  if (frontQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (frontQuery.data === undefined) {
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
      {front.is_live ? props.children : <HoldingPage front={front} />}
    </GuestFrame>
  );
}
