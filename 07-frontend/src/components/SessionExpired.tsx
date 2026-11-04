// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-SHL-6378 (2026-09-23) — the PO, on production v2.344.0 as System
//           Admin: *"whenever user session expire system show this message -
//           You don't have access to this. Your role can't open Payments. … we
//           need to say your session is expired and login again. this happens
//           many places"*.
// Rules:    BR-SHL-009 (no tenant data readable once the session is gone; the
//           way out is the TENANT'S OWN sign-in page) · A18 §6 (the denial is a
//           ROLE refusal and only that) · B14 rule 4 (`Verb →` navigates) ·
//           B14 rule 21 (Tailwind, no stylesheet class) · B14 rule 33 (a label
//           ≤ 3 words, an instruction ≤ 6) · B14 rule 43 (a component, not code
//           inside a page)
// Screens:  shell-chrome — every authenticated screen (S7–S114) can end here
// Tests:    sessionExpiry.dom.test.tsx (the real shell, the real routes)
// ───────────────────────────────────────────────────────
// WHAT A DEAD SESSION LOOKS LIKE, SAID ONCE FOR EVERY SCREEN.
//
// A 401 is true of the whole product at once — no screen can do anything until
// the person signs in again — so it is not answered by the screen that happened
// to ask. `SessionExpiryBoundary` wraps the staff shell, listens on the one
// channel (`api/sessionExpiry.ts`, fed by the transport AND the query cache),
// and on the first announcement:
//   1. EMPTIES THE CACHE (BR-SHL-009) — the accounts, bills and payments the
//      tab was holding stop being readable the moment the server stops
//      vouching for whoever is looking at them;
//   2. REPLACES THE WHOLE SHELL with the card below — the sidebar and the page
//      unmount, so nothing drawn from the emptied cache is left on screen and
//      no query in them can ask again;
//   3. offers ONE way on: Sign in, to this tenant's own sign-in page, carrying
//      the page the person was on so they land back on it.
//
// ⚠ THE CARD SAYS NOTHING ABOUT WHY. How long a session lasts is on Settings →
// Security for an admin who wants it; on this card it would be rationale, which
// B14 rule 33 puts at zero words. Two facts and a door.
//
// ⚠ WHAT IS LOST, STATED HERE BECAUSE IT IS NOT STATED ON SCREEN: whatever the
// page held only in memory. A form half-filled is gone, except where its wizard
// already keeps a server draft — Move-in autosaves one (`wizardPark.ts`,
// `autosave: true`) and its address carries `?parked=`, so the way back resumes
// it from the last draft that was saved before the session ended. Every other
// wizard keeps a draft only when the clerk pressed Park.
import { useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";

import { resetAnalytics, track } from "@/analytics";
import { onSessionExpired } from "@/api/sessionExpiry";
import { ButtonLink } from "@/components/Button";
import { signInAgainDestination } from "@/routing/tenantPath";

/**
 * The card. Drawn on the sign-in page's own stage — the same ground, the same
 * 420px accent-topped card — because it is the step before that page, and a
 * person should recognise where the button is taking them.
 */
export function SessionExpiredFrame(props: { signInTo: string }) {
  const { t } = useTranslation();
  return (
    <main
      className="flex min-h-screen items-center justify-center bg-surface px-6 py-8"
      data-state="session-expired"
    >
      <div role="alert" className="w-full max-w-[420px] border-t-4 border-t-accent bg-bg p-8 shadow-md">
        <h1 className="my-2 text-h4">{t("shell.sessionExpired.title")}</h1>
        <p className="m-0 mb-4 text-md text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {t("shell.sessionExpired.instruction")}
        </p>
        <ButtonLink variant="primary" className="w-full justify-center" to={props.signInTo}>
          {t("shell.sessionExpired.signIn")}
        </ButtonLink>
      </div>
    </main>
  );
}

/**
 * The listener. Wraps the staff shell and nothing else — see
 * `api/sessionExpiry.ts` for why the sign-in page, the portal and the phone
 * must never be inside it.
 */
export function SessionExpiryBoundary(props: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { pathname, search } = useLocation();
  const [expired, setExpired] = useState(false);
  // Two layers announce the same 401 (the transport, then the cache), and a
  // page mid-load may fire several. The first one ends the session; the rest
  // must not clear a cache a second time or schedule another render.
  const ended = useRef(false);

  // ⚠ A LAYOUT EFFECT, NOT A PASSIVE ONE. Children's effects run before their
  // parent's, and a query starts fetching from a passive effect — so a passive
  // subscription here would be the LAST thing in the commit to run. Every
  // layout effect runs before every passive one, so this is listening before
  // the first request below it has been sent.
  useLayoutEffect(
    () =>
      onSessionExpired(() => {
        if (ended.current) {
          return;
        }
        ended.current = true;
        // CR-169-BRC10 §2 row 7 — a dead session is a sign-out too.
        track("user_signed_out", { reason: "session_expired" });
        resetAnalytics();
        queryClient.clear(); // BR-SHL-009 — before the card is shown, not after
        setExpired(true);
      }),
    [queryClient],
  );

  if (expired) {
    return <SessionExpiredFrame signInTo={signInAgainDestination(pathname, search)} />;
  }
  return <>{props.children}</>;
}

export default SessionExpiryBoundary;

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-SHL-6378 (maintenance — PO report, production v2.344.0)
// generated: 2026-09-23 by lane SESSION-EXPIRY
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the CHANGELOG entry for this version
// exceptions: E4 the card is drawn from the sign-in page's own stage rather
//         than from a blueprint frame — no blueprint draws an expired session,
//         and the PO's report names the words ("your session is expired and
//         login again"); the button carries B14 rule 4's `→` because it
//         navigates
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
