// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-040 (EP-WRK-08) — the phone shell: a web app, installable
//           and offline-first, under `/{tenant}/work/mobile/`, with the
//           technician's identity from their login. Screens: Work-010, Work-011
// Rules:    BR-WRK-045 (a WEB app, not a native shell — decision log
//           2026-09-03) · BR-WRK-036 (the offline marker is ALWAYS visible) ·
//           B14 rule 21 (Tailwind only; this file is on route-b-migrated.txt
//           from its first commit) · rule 31 (no database id is a visible
//           value) · rule 32 (a description budget) · rule 33 (a refusal caps
//           at five or six words) · rule 36 (the shared kit is how you comply)
// Tests:    src/features/work/mobile/MobileApp.test.tsx ·
//           src/features/work/mobile/heldPanes.test.ts
// Impacts:  src/App.tsx (ONE route, a sibling of the staff shell) ·
//           src/routing/screenIds.ts · 10-scripts/gates/g29_allocated_badges.txt
// ───────────────────────────────────────────────────────
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";

import { useStaffAnalytics } from "@/analytics";
import { isApiError } from "@/api/client";
import { getMe, signOut } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { SignInPage } from "@/features/identity/SignInPage";

import { stopFix } from "./location";
import { flushOutbox, issueCaptureToken } from "./mobileEndpoints";
import { captureToken, currentUser, forgetActiveUser, restoreActiveUser, setActiveUser } from "./offlineStore";

import { JobPage } from "./JobPage";
import { PhotosPane } from "./PhotosPane";
import { ReadingsPane } from "./ReadingsPane";
import { ClosePane } from "./ClosePane";
import { SignaturePane } from "./SignaturePane";
import { TodayPage } from "./TodayPage";
import { registerFieldServiceWorker } from "./serviceWorker";

/**
 * Everything under `/{tenant}/work/mobile` — the field app.
 *
 * ⚠ **A THIRD APPLICATION ROOT, AND IT IS MOUNTED LIKE THE PORTAL AND NOT LIKE
 * A FEATURE.** `App.tsx` gives it one route, a SIBLING of `ShellWithSession`,
 * for the reason `PortalApp` is mounted that way: it has no staff sidebar, no
 * global search and no page header, and a phone in a meter pit must not
 * download or render any of them. It DOES share the session — unlike the
 * portal, the technician signs in with the staff login (`OQ-WRK-1494`, closed
 * 2026-09-04: one `users` table, a `surface_scope` column).
 *
 * ⚠ **THE FOUR BOTTOM TABS ARE `WS-10`'s AND TWO OF THEM ARE HELD.** *Today ·
 * Week · Parts · Help*. Today and Week are the same list over two windows
 * (`US-WRK-040` TC-7). Parts and Help are per-JOB, so they are reached from a
 * job rather than from the frame — the frame's tab for each would be a door to
 * a screen that cannot exist without knowing which job. That is stated here
 * because a later lane WILL look at four drawn tabs and two mounted ones and
 * read it as an omission.
 */
export function MobileApp() {
  const { t, i18n } = useTranslation();
  const { tenant } = useParams();

  useEffect(() => {
    // ⚠ REGISTERED HERE AND NOWHERE ELSE. The staff app and the portal must not
    // install a worker they have no use for: its scope is `/` (there is no
    // fixed directory to serve it from, the tenant being dynamic), so an
    // unconditional registration in `main.tsx` would put it in front of every
    // surface for every user. Mounting the field app is the consent.
    void registerFieldServiceWorker();
  }, []);

  const base = `/${tenant ?? ""}/work/mobile`;
  const onSignIn = useLocation().pathname.replace(/\/+$/, "").endsWith("/work/mobile/signin");

  // ── DEF-WRK-9583 · THE FIELD APP'S OWN DOOR ────────────────────────────
  // A phone with no session is sent to `signin` below, which declares the
  // `mobile` surface to the server (`BR-WRK-043`). ⚠ ONLY ON A 401: offline
  // is a network error, not an answer, and must keep the day from the store
  // (`BR-WRK-036`); a 403 is a password change owed, which sign-in routed.
  const session = useQuery({
    queryKey: queryKeys.me,
    queryFn: () => getMe(),
    retry: false,
    enabled: !onSignIn,
  });
  // CR-169-BRC10 — the field app is staff (ruling 18 of CR-168-BRC10):
  // identified by internal id, grouped by utility, `app: "field"`.
  useStaffAnalytics({
    userId: session.data?.id,
    role: session.data?.role,
    tenant: tenant ?? "",
    app: "field",
    language: i18n.language,
  });
  const identity = useFieldIdentity(session.data?.id ?? null, session.isError, !onSignIn);
  useBackgroundSend(!onSignIn);
  const signOutHere = useFieldSignOut(base);

  if (!onSignIn && isApiError(session.error) && session.error.status === 401) {
    return <Navigate to={`${base}/signin`} replace />;
  }
  if (onSignIn) {
    return (
      <Routes>
        <Route path="signin" element={<SignInPage surface="mobile" />} />
      </Routes>
    );
  }

  if (!identity) {
    // Until WHOSE phone this is is known, nothing per-login is read — a Today
    // list drawn before that would be keyed to nobody (CR-168 §F, `BR-WRK-059`).
    return null;
  }

  return (
    <div className="min-h-screen bg-bg text-text flex flex-col">
      <main className="flex-1 pb-16">
        <Routes>
          <Route index element={<TodayPage />} />
          <Route path="week" element={<TodayPage days={7} />} />
          <Route path="jobs/:orderId" element={<JobPage />} />
          {/*
            CR-070 wave K. ⚠ These three addresses are ALSO in
            `MOBILE_ROUTE_PATHS`, and they have to be: `heldPanes.test.ts`
            reads that list, not this JSX, and a route mounted here but missing
            there would leave a hold passing over a screen that had landed —
            the exact failure the whole mechanism exists to prevent.
          */}
          <Route path="jobs/:orderId/readings" element={<ReadingsPane />} />
          <Route path="jobs/:orderId/photos" element={<PhotosPane />} />
          <Route path="jobs/:orderId/signature" element={<SignaturePane />} />
          {/* CR-070 wave L — `Work-012`'s close. */}
          <Route path="jobs/:orderId/close" element={<ClosePane />} />
          {/* DEF-WRK-9583 — rendered above, without the bottom bar; listed
              here so the JSX and `MOBILE_ROUTE_PATHS` still agree. */}
          <Route path="signin" element={<SignInPage surface="mobile" />} />
        </Routes>
      </main>

      {/*
        `WS-10`'s bottom bar. `fixed` because a technician scrolls a day list
        with a thumb and the way back must not scroll away — which is the same
        reason `BR-WRK-036`'s marker is in the header rather than in the list.
      */}
      <nav
        className="fixed bottom-0 left-0 right-0 border-t border-divider bg-surface flex"
        aria-label={t("work.mobile.nav.label")}
      >
        <MobileTab to={base} end label={t("work.mobile.nav.today")} />
        <MobileTab to={`${base}/week`} label={t("work.mobile.nav.week")} />
        {/* CR-168-BRC10 §F — ONE TABLET, SEVERAL TECHNICIANS IN TURN
            (`BR-WRK-059`/`060`). Sign-out is never blocked and never deletes:
            unsent work stays on the phone under its captor's token. */}
        <button
          type="button"
          className="flex-1 text-center py-3 text-sm text-neutral-600"
          data-action="sign-out"
          onClick={() => void signOutHere()}
        >
          {t("shell.user.signOut")}
        </button>
      </nav>
    </div>
  );
}

function MobileTab({ to, label, end }: { to: string; label: string; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        [
          "flex-1 text-center py-3 text-sm",
          // A 44px-tall target. A technician taps this with a glove on.
          isActive ? "text-accent font-semibold" : "text-neutral-600",
        ].join(" ")
      }
    >
      {label}
    </NavLink>
  );
}

/**
 * WHO is signed in on this phone, and the capture token their work carries
 * (CR-168-BRC10 §F, `BR-WRK-059`). Returns true once the phone knows.
 *
 * Online: the session names the user; if this phone holds no token for them
 * yet, one is asked for (`POST /work/mobile/capture-token`) and kept. Offline
 * (the session read failed for want of a network, not with a 401): the last
 * login this phone saw is restored, and that technician's own token is still
 * on the phone — so work captured in a basement is still theirs.
 */
function useFieldIdentity(userId: string | null, failed: boolean, enabled: boolean): boolean {
  const [known, setKnown] = useState(false);
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    void (async () => {
      if (userId) {
        if (currentUser() !== userId || !(await captureToken(userId))) {
          let token: string | null = (await captureToken(userId)) ?? null;
          try {
            token = (await issueCaptureToken({ device_label: deviceLabel() })).capture_token;
          } catch {
            // No token this time (a login with no technician profile, or the
            // signal dropped): items go without one and the server checks the
            // job against the session, as before.
          }
          await setActiveUser(userId, token);
        }
      } else if (failed) {
        await restoreActiveUser();
      } else {
        return;
      }
      if (live) setKnown(true);
    })();
    return () => {
      live = false;
    };
  }, [userId, failed, enabled]);
  return known;
}

function deviceLabel(): string {
  return typeof navigator !== "undefined" ? navigator.userAgent.slice(0, 60) : "";
}

/**
 * Send the outbox whenever there is a signal: on opening, when the network
 * comes back, and every 30 seconds while it is up (TECHNICIAN SYNC DESIGN (4):
 * *"a background queue with retry"*). Whoever is signed in is only the COURIER:
 * every item carries its own captor's token.
 */
function useBackgroundSend(enabled: boolean): void {
  useEffect(() => {
    if (!enabled) return;
    const send = () => {
      if (typeof navigator !== "undefined" && navigator.onLine === false) return;
      void flushOutbox().catch(() => undefined);
    };
    send();
    window.addEventListener("online", send);
    const timer = window.setInterval(send, 30_000);
    return () => {
      window.removeEventListener("online", send);
      window.clearInterval(timer);
    };
  }, [enabled]);
}

/**
 * Sign out on a shared tablet — NEVER BLOCKED, NEVER DELETES (`BR-WRK-060`).
 * The server session is ended if there is a signal; with none, the phone
 * forgets who is signed in anyway, and the next login starts from its own
 * empty day. Everything the last technician captured stays queued under
 * their token and uploads as soon as there is signal, whoever is signed in.
 */
function useFieldSignOut(base: string): () => Promise<void> {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  return async () => {
    stopFix();
    await forgetActiveUser();
    try {
      await signOut();
    } catch {
      // Offline: the session ends on the server at its own expiry, and the
      // next sign-in replaces it. Sign-out is not blocked for want of signal.
    }
    queryClient.removeQueries({ queryKey: queryKeys.me });
    navigate(`${base}/signin`, { replace: true });
  };
}
