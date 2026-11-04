// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-007 · US-CWP-009 (EP-CWP-03) — the report flow's one route.
//           Screens: CWP-006 → CWP-007 (sent) or the routed state (gas)
// Rules:    BR-CWP-005 (the tenant is the first path segment) · BR-CWP-007 ·
//           CR-068 §11c (one route per CWP screen) · CR-068 R8 (a portal that
//           is OFF shows the holding page and nothing else, on EVERY route) ·
//           B14 rule 36
// Defects:  DEF-CWP-4851 — this screen served in full at a utility that had
//           not switched its portal on.
// Tests:    src/portal/guest/ReportProblem.test.tsx
// Impacts:  src/portal/routing/portalRoutes.tsx · screenIds.ts
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";

import type { ReportResult } from "../api/guestClient";
import { getPortalFront } from "../api/guestClient";

import { GuestPage } from "./GuestPage";
import { ReportProblem } from "./ReportProblem";
import { ReportRouted } from "./ReportRouted";
import { ReportSent } from "./ReportSent";

/**
 * ⚠ **THE SCREEN ID ON THE PAGE CHANGES WITH THE STATE, AND THE ROUTE DOES
 * NOT.** `CWP-006` and `CWP-007` are one URL: a stranger who has just sent a
 * report has nowhere to be sent to and no session to carry them there, so the
 * confirmation replaces the form in place (`BR-CWP-028` — the reference IS the
 * record of the interaction). Each state tags itself, so a bug report can still
 * name the screen it was looking at.
 *
 * ⚠ **`GuestPage` AND NOT `GuestFrame` — `DEF-CWP-4851`.** This page drew the
 * frame itself and therefore never asked whether the portal was switched on,
 * so a utility that had not opened its portal still served this whole form.
 * `GuestPage` is the same frame with the switch read in front of it, and it is
 * what `/pay`, `/start-service` and `/ask` have always composed.
 *
 * ⚠ **THE FRONT READ IS STILL HERE AND IT IS NOT A SECOND REQUEST.**
 * `GuestPage` and this component ask for the same query key
 * (`queryKeys.portalFront`), so react-query serves both from one fetch. The
 * data is needed here because the report form's emergency fallback depends on
 * whether the utility has published a number at all.
 */
export function ReportPage(props: { client?: ApiClient }) {
  const client = props.client ?? api;
  const [result, setResult] = useState<ReportResult | null>(null);
  const frontQuery = useQuery({
    queryKey: queryKeys.portalFront,
    queryFn: () => getPortalFront(client),
  });

  return (
    <GuestPage client={client}>
      {result === null ? (
        <ReportProblem
          emergencyPhone={frontQuery.data?.emergency_phone ?? null}
          onSent={setResult}
          client={client}
        />
      ) : result.created ? (
        <ReportSent sent={result} />
      ) : (
        <ReportRouted routed={result} />
      )}
    </GuestPage>
  );
}
