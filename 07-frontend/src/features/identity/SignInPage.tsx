// ── Trace ──────────────────────────────────────────────
// Story:    US-IDN-001 (EP-IDN-01 §Stories)  Screens: S3 (sign-in card on S2 shares this surface)
// Rules:    BR-IDN-001 (the tenant resolves FIRST, then the credentials — source is the URL's tenant
//           segment since the PO's 2026-08-10 path-tenancy ruling) · BR-IDN-002 (ONE generic failure) ·
//           BR-IDN-003/BR-IDN-025 (the utility's N failed attempts → its M-minute lock, DEF-IDN-10620) · BR-IDN-022/BR-IDN-023 (forced change; no reset endpoint in v1) ·
//           BR-IDN-026 ("Keep me signed in" off by default) · BR-SHL-017 (field kit + inline validation) · BR-SHL-020 (plain language)
// ───────────────────────────────────────────────────────
// S3 Sign-in, at `/{tenant}/signin` (PO 2026-08-10 path tenancy). Composed from
// the registry: the US-SHL-009 field kit (TextField/PasswordField/CheckboxField
// + collectFormErrors) and StateFrame's WorkingButton. Nothing about
// authentication is decided here — the server owns every verdict:
//   · the TENANT comes from the ROUTE (BR-IDN-001, whose source moved from the
//     Host's first label to the URL's first path segment). This page still
//     sends no tenant in the body: the transport puts it in the URL it posts to
//     (`POST /api/{tenant}/auth/session`), and the page only displays which
//     utility that is, so the visitor knows where they are signing in;
//   · every failure renders ONE generic message (BR-IDN-002). The page never
//     inspects the error code to say more: bad password, unknown email,
//     deactivated membership and an active lock are indistinguishable BY LAW.
//     ⚠ ONE EXCEPTION, BY RULE (DEF-WRK-9583): `BR-WRK-043`'s wrong-door
//     refusal is named, because the server reaches it only after the password
//     checked out — see `surfaceRefusalKey`;
//   · ⚠ A LOCKED LOGIN IS NAMED, BY THE SERVER, WITH THE UTILITY'S MINUTES
//     (`DEF-IDN-10620`, PO 2026-10-27: *"the same message has to appear when
//     the user was locked out"*). This line used to be a browser-side count
//     that said "after 5 failed attempts … 15 minutes" whatever the utility
//     had set in Settings › Security — a hardcoded 5 and 15 the PO ruled out.
//     The server's `auth.sign_in.locked` refusal carries `minutes`, and the
//     page renders exactly that (`signInFailureLine`);
//   · "Forgot password?" LINKS to its own public page (BR-IDN-023 as amended
//     2026-10-05, CR-170-BRC10) — v1 still has no reset endpoint and sends no
//     staff auth email (BR-IDN-021); the inline notice that stood here is gone;
//   · `?changed=1` — the one-time arrival from a completed forced change —
//     shows "Password changed. Sign in again." and is then stripped from the
//     address, so a reload or a bookmark never shows it again (CR-170-BRC10);
//   · `must_change_password` in the session payload routes to the forced-change
//     screen before any app screen (BR-IDN-022); that screen is US-IDN-002's
//     packet — this page owns the redirect only.
// Copy is A13-silent for sign-in errors; the keys below are PROPOSED copy
// reported to the PO batch (prototype has the labels, not the failures).
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { identifyStaff, track } from "@/analytics";
import { getSignInOptions, signIn } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import type { SessionUser, SignInSurface } from "@/api/endpoints";
import type { ApiClient } from "@/api/client";
import { api, ApiError } from "@/api/client";
import { AuthCard } from "@/components/AuthCard";
import { ButtonLink } from "@/components/Button";
import { FIELD_APP_ONLY_KEY, FieldAppNotice } from "@/components/FieldAppNotice";
import { CheckboxField, PasswordField, TextField, collectFormErrors } from "@/components/FormModal";
import { WorkingButton } from "@/components/StateFrame";
import { SIGNIN_HELP_ROUTE } from "@/routing/tenantPath";
import { RETURN_PARAM, safeReturnPath, useTenant, useTenantPath } from "@/routing/tenantPath";


// ── Pure pieces (provable without a browser or a network) ──────────────────

export const DASHBOARD_ROUTE = "/dashboard";
// BR-IDN-022: the forced-change screen gates every app screen. US-IDN-002 owns
// the screen; this constant is the contract between the two packets.
export const FORCED_PASSWORD_CHANGE_ROUTE = "/change-password";
// CR-170-BRC10 (BR-IDN-023 as amended 2026-10-05): the forgot-password page.
// `App.tsx` mounts THIS constant and the link below reads it — one string for
// the door and the room, as `FORCED_PASSWORD_CHANGE_ROUTE` already is.
export const FORGOT_PASSWORD_ROUTE = "/forgot-password";
// CR-188-BRC10 (PO 2026-10-22): where an emailed one-time sign-in link lands.
// The server builds the link from `PUBLIC_APP_ORIGIN` + `/{tenant}` + this
// segment (`apps/identity/password_links.SET_PASSWORD_SEGMENT`); App.tsx mounts
// THIS constant. `SetPasswordPage.test.tsx` pins the two spellings together.
export const SET_PASSWORD_ROUTE = "/set-password";
export const SET_PASSWORD_TOKEN_PARAM = "token";
/**
 * CR-170-BRC10 (BR-IDN-022 as amended 2026-10-05): the one-time flag the forced
 * change sets on its way back here. It is consumed on arrival — read once into
 * state, then stripped from the address with `replace`.
 */
export const PASSWORD_CHANGED_PARAM = "changed";

/** Where "Forgot password?" goes from a door; the field app's carries its own way back. */
export function forgotPasswordPath(surface: SignInSurface): string {
  return surface === "mobile"
    ? `${FORGOT_PASSWORD_ROUTE}?${RETURN_PARAM}=${encodeURIComponent(FIELD_APP_SIGN_IN)}`
    : FORGOT_PASSWORD_ROUTE;
}

/**
 * `DEF-IDN-10620` — the server's refusal for a LOCKED login (BR-IDN-025, as
 * amended by `CR-145-BRC08`: the count and the minutes are the utility's own).
 * *"Too many wrong attempts. Try again in {{minutes}} minutes."*
 */
export const LOCKED_KEY = "auth.sign_in.locked";

/** The utility's lock period from a locked refusal, or null for anything else. */
export function lockedMinutes(error: unknown): number | null {
  if (!(error instanceof ApiError) || error.status !== 401 || error.messageKey !== LOCKED_KEY) {
    return null;
  }
  const minutes = error.params.minutes;
  return typeof minutes === "number" && Number.isFinite(minutes) && minutes > 0 ? minutes : null;
}

/**
 * The ONE line a failed sign-in shows (BR-IDN-002): the generic sentence for
 * every failure, except a lock the SERVER names (`DEF-IDN-10620`), which says
 * the utility's own minutes. Nothing else about the refusal reaches the copy.
 */
export function signInFailureLine(error: unknown, t: (key: string, options?: Record<string, unknown>) => string): string {
  const minutes = lockedMinutes(error);
  return minutes !== null ? t(LOCKED_KEY, { minutes }) : t("identity.signIn.failed");
}

/**
 * BR-IDN-022: a temp password lands on the forced-change screen, never the app.
 *
 * `returnTo` is where a person whose session ENDED was when it did
 * (`DEF-SHL-6378`) — already passed through `safeReturnPath`, so it is a
 * tenant-relative path that cannot leave this tenant. It never outranks the
 * forced change: a password that must be changed is changed first.
 */
export function routeAfterSignIn(
  user: SessionUser,
  returnTo: string | null = null,
  home: string = DASHBOARD_ROUTE,
): string {
  if (user.must_change_password) {
    // DEF-WRK-9583 — the forced change comes first, and then an INVITED field
    // technician goes to the phone, never the staff dashboard their login
    // cannot use. Only the door's own HOME is carried: `returnTo` is still
    // dropped here, exactly as before (`signInReturnPath.dom.test.tsx`).
    return home === DASHBOARD_ROUTE
      ? FORCED_PASSWORD_CHANGE_ROUTE
      : `${FORCED_PASSWORD_CHANGE_ROUTE}?${RETURN_PARAM}=${encodeURIComponent(home)}`;
  }
  return returnTo ?? home;
}

/** DEF-WRK-9583 — where the field app lands, relative to the tenant. */
export const FIELD_APP_HOME = "/work/mobile";
/** DEF-WRK-9583 — the field app's own sign-in door. */
export const FIELD_APP_SIGN_IN = `${FIELD_APP_HOME}/signin`;

/**
 * DEF-WRK-9583 — the ONE kind of refusal this page names (`BR-WRK-043`).
 *
 * The credentials were CORRECT and the person is at the wrong door, so naming
 * it discloses nothing `BR-IDN-002` protects — the server only reaches this
 * refusal after the password has been checked. Every other failure still
 * returns `null` here and renders the one generic line. A list, not a prefix
 * match, so a new server key can never widen what this page discloses.
 */
export const NAMED_SURFACE_REFUSALS: readonly string[] = [
  "identity.signIn.fieldAppOnly",
  "identity.signIn.webAppOnly",
];

export function surfaceRefusalKey(error: unknown): string | null {
  return error instanceof ApiError &&
    error.status === 403 &&
    NAMED_SURFACE_REFUSALS.includes(error.messageKey)
    ? error.messageKey
    : null;
}

/**
 * BR-IDN-002, made mechanical: this function takes NO error. There is no
 * parameter through which a wrong password, an unknown email, a deactivated
 * membership or a throttle could reach the copy — so they cannot be told apart.
 * The only thing that changes the line is THIS browser's own attempt count
 * (BR-IDN-025), which is a policy statement, not an account disclosure.
 */
/**
 * DEF-533 — classify a sign-in failure. PURE, so the rule is provable without
 * a browser (the house style: `signOutDestination`, `signInFailureLine`).
 *
 * A 404 is NOT a credentials failure: the server answers not-found for the
 * whole `/api/{tenant}/auth/session` path, which means THE TENANT does not
 * exist — the state `DEF-532` stranded the PO in (`/premises/signin`, a door
 * for a utility named "premises"). Flattening it into *"check your email and
 * password"* is a lie that locks the user out: no password can ever work.
 * Everything else stays flattened on purpose (BR-IDN-004's one-message rule).
 */
export function signInFailureKind(error: unknown): "unknown-tenant" | "credentials" {
  return error instanceof ApiError && error.status === 404 ? "unknown-tenant" : "credentials";
}


/** BR-SHL-017 client validation — UX only; the SERVER is authoritative (B8). */
export function signInSchema(t: (key: string) => string) {
  return z.object({
    email: z.string().email(t("identity.signIn.invalidEmail")),
    password: z.string().min(1, t("identity.signIn.passwordRequired")),
  });
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface SignInPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
  // The tenant the route names (BR-IDN-001). Test seam only: the real value is
  // the URL's own tenant segment, which is also what the server reads.
  tenant?: string;
  /**
   * DEF-WRK-9583 — the app this door belongs to (`BR-WRK-043`). The field app
   * mounts this page at `/{tenant}/work/mobile/signin` with `"mobile"`; every
   * other mount is the web. Sent to the server, which decides.
   */
  surface?: SignInSurface;
}

export function SignInPage(props: SignInPageProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const tenantPath = useTenantPath();
  const routeTenant = useTenant();
  // DEF-SHL-6378 — the page to go back to after a session ended under it.
  // Anything `safeReturnPath` will not vouch for is dropped, never repaired:
  // the person lands on the Dashboard exactly as they did before this existed.
  const [searchParams, setSearchParams] = useSearchParams();
  const returnTo = safeReturnPath(searchParams.get(RETURN_PARAM));
  // CR-170-BRC10 — read ONCE, then consumed below; the state outlives the strip.
  const [passwordChanged] = useState(() => searchParams.get(PASSWORD_CHANGED_PARAM) === "1");
  useEffect(() => {
    if (searchParams.has(PASSWORD_CHANGED_PARAM)) {
      const rest = new URLSearchParams(searchParams);
      rest.delete(PASSWORD_CHANGED_PARAM);
      setSearchParams(rest, { replace: true });
    }
  }, [searchParams, setSearchParams]);
  const client = props.client ?? api;
  const tenant = props.tenant ?? routeTenant;
  const surface: SignInSurface = props.surface ?? "web";
  const home = surface === "mobile" ? FIELD_APP_HOME : DASHBOARD_ROUTE;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [keepSignedIn, setKeepSignedIn] = useState(false); // off by default (BR-IDN-026)
  /**
   * ⚠ **CR-145-BRC08 — DOES THIS UTILITY OFFER THE TICK BOX AT ALL?**
   *
   * A PUBLIC, un-authenticated read (`B13`), and it has to be: there is no
   * session on a sign-in screen, and `GET /settings/security-policy` — where
   * this fact also lives — is System-Admin-only. A screen that decided its own
   * controls from a 401 would be deciding them from an error path.
   *
   * **It is not retried and it does not block the form.** Signing in is the job
   * of this page; whether a convenience is offered is not worth a spinner, and
   * the password fields must be usable while this is still in flight.
   */
  const signInOptions = useQuery({
    queryKey: queryKeys.signInOptions(tenant),
    queryFn: () => getSignInOptions(client),
    retry: false,
  });
  /**
   * ⚠ **ABSENT UNTIL PROVEN OFFERED, WHICH IS THE FAIL-CLOSED READING
   * (hard-won law 3).** `undefined` is *"we have not been told"* and renders
   * NOTHING — never the box. Showing it while the answer is in flight would
   * put a control on screen that may be about to vanish under the cursor, and
   * showing it when the read FAILED would offer a utility the very thing its
   * admin switched off. The cost of being wrong the safe way is one tick box a
   * person does not see; the cost of being wrong the other way is a promise
   * the server will not keep.
   */
  const offersKeepSignedIn = signInOptions.data?.keep_signed_in_offered === true;
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [failed, setFailed] = useState(false);
  const [failureLine, setFailureLine] = useState("");
  // DEF-WRK-9583 — right credentials, wrong door: the server's own sentence.
  const [wrongDoor, setWrongDoor] = useState<string | null>(null);
  // DEF-533 — the tenant in the URL does not exist. Not a sign-in failure.
  const [unknownTenant, setUnknownTenant] = useState(false);
  const [working, setWorking] = useState(false);

  async function handleSubmit(): Promise<void> {
    if (working) {
      return; // one submit in flight (A18 §3) — double-clicks are harmless
    }
    const validation = collectFormErrors(signInSchema(t), { email, password });
    setFieldErrors(validation.errors);
    if (validation.count > 0) {
      return; // nothing is posted until the shape is right
    }
    setWorking(true);
    try {
      // CR-145-BRC08: a utility that does not OFFER it never receives it. The
      // box cannot be ticked while it is hidden, so this reads as belt and
      // braces — it is not. The state survives the answer arriving, so a person
      // who ticked the box on a utility that offers it and then landed on one
      // that does not would otherwise post a `true` nothing on screen said.
      const user = await signIn(
        { email, password, keep_signed_in: offersKeepSignedIn && keepSignedIn, surface },
        client,
      );
      setFailed(false);
      setWrongDoor(null);
      // ⚠ **THE SESSION IS PUT IN THE CACHE HERE, AND `DEF-IDN-5653` IS WHY.**
      // `POST /auth/session` answers with exactly the payload `GET /me` serves,
      // and this was throwing it away — every screen after this had to fetch it
      // again. That is merely wasteful for an ordinary user and it is FATAL for
      // a user who owes a password change: `identity/auth.py`'s
      // `_FORCED_CHANGE_EXEMPT` refuses `GET /me` to exactly that person, so
      // the forced-change screen this function is about to navigate to could
      // never learn who it was talking to. The one moment the app is allowed to
      // know is this one, so it writes it down.
      queryClient.setQueryData(queryKeys.me, user);
      // CR-169-BRC10 — identified HERE, before the event, so the sign-in lands
      // on the person and not on an anonymous visitor. Internal id only.
      identifyStaff({
        userId: user.id,
        role: user.role,
        tenant,
        app: surface === "mobile" ? "field" : "staff",
        language: i18n.language,
      });
      track("user_signed_in", { surface });
      // Both targets are tenant screens: the session belongs to THIS tenant, so
      // it lands on this tenant's path (BR-IDN-022 chooses which one).
      navigate(tenantPath(routeAfterSignIn(user, returnTo, home)));
    } catch (error) {
      // BR-IDN-002: the reason is deliberately not read. ANY failure — wrong
      // password, unknown email, inactive membership, lock, throttle — renders
      // the same message, with the same absence of field-level marking.
      //
      // ⚠ **ONE failure is NOT flattened, and it is the one that stranded the
      // PO (`DEF-533`).** A 404 here does not mean a wrong password — it means
      // THE TENANT ITSELF does not exist: the server answers not-found for the
      // whole `/api/{tenant}/auth/session` path. That happens when a dropped
      // tenant segment corrupts the URL (`DEF-532` put the PO on
      // `/premises/settings/security`; signing out then landed on
      // `/premises/signin`, a door for a utility named "premises"). Rendering
      // *"check your email and password"* on that door is a lie that locks the
      // user out — no password will ever work. So a 404 renders the
      // unknown-utility state, whose one action is the `/signin-help` landing
      // that exists precisely to ask which utility you meant.
      if (signInFailureKind(error) === "unknown-tenant") {
        track("user_sign_in_failed", { surface, reason: "unknown_tenant" });
        setUnknownTenant(true);
        return;
      }
      // DEF-WRK-9583 — NOT a failed attempt: the password was right, the
      // server counted nothing, so neither does this browser's lockout line.
      const doorKey = surfaceRefusalKey(error);
      if (doorKey !== null) {
        track("user_sign_in_failed", { surface, reason: "wrong_door" });
        setFailed(false);
        setWrongDoor(doorKey);
        setPassword("");
        return;
      }
      // BR-IDN-002's one flattened reason — except a lock the SERVER names,
      // which says the utility's own minutes (`DEF-IDN-10620`).
      track("user_sign_in_failed", {
        surface,
        reason: lockedMinutes(error) !== null ? "locked" : "refused",
      });
      setWrongDoor(null);
      setFailureLine(signInFailureLine(error, t));
      setFailed(true);
      setPassword("");
    } finally {
      setWorking(false);
    }
  }

  // CR-018 Route B: SignInPage.css (deleted) ported value for value — the
  // full-viewport centred stage holding the 420px accent-topped card the
  // signed reference draws — and since CR-170-BRC10 that stage and card are
  // ONE component, `AuthCard`, shared with the forced change and the
  // forgot-password page (B14 rule 43). `data-page="signin"` carries the
  // machine handle (tenantPath.test.tsx proves this page renders outside the
  // app shell).
  return (
    <AuthCard
      page="signin"
      kicker={surface === "mobile" ? t("work.mobile.nav.label") : t("identity.signIn.kicker")}
      title={t("identity.signIn.title")}
      lede={t("identity.signIn.lede")}
    >
        {passwordChanged && (
          // CR-170-BRC10 — the arrival from a completed forced change, once.
          <p
            className="m-0 mb-4 border-l-3 border-l-success-500 bg-success-100 p-3 text-base leading-body"
            role="status"
            data-cr-ref="CR-170-BRC10"
          >
            {t("identity.signIn.passwordChanged")}
          </p>
        )}
        {tenant !== "" && (
          // BR-IDN-001: the tenant is whatever the path segment resolves to —
          // shown so the user knows which utility they are signing in to. It is
          // DISPLAY only: nothing here lets them change it, and the server
          // reads the same segment off the request.
          <p className="m-0 mb-4 text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">{t("identity.signIn.tenant", { tenant })}</p>
        )}

        {/* DEF-533 — this door leads nowhere: the tenant in the URL does not
            exist, so no credentials can ever work here. Saying "check your
            password" would be a lie that locks the user out. The one action is
            the tenant-less help landing, which asks which utility you meant. */}
        {unknownTenant && (
          <div className="m-0 mb-4 border-l-3 border-l-danger-500 bg-danger-100 p-3 text-base text-danger-700" role="alert" data-def-ref="DEF-533">
            <p>{t("identity.signIn.unknownTenant", { tenant })}</p>
            <p>
              <a href={SIGNIN_HELP_ROUTE}>{t("identity.signIn.unknownTenantHelp")}</a>
            </p>
          </div>
        )}

        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            void handleSubmit();
          }}
        >
          <TextField
            id="signin-email"
            label={t("identity.signIn.email")}
            value={email}
            onChange={setEmail}
            required
            placeholder={t("identity.signIn.emailPlaceholder")}
            error={fieldErrors.email}
          />

          {/* The kit's PasswordField (BR-SHL-017) — the local input this page
              used to carry is gone, so S3 and S114 now share ONE definition. */}
          <PasswordField
            id="signin-password"
            label={t("identity.signIn.password")}
            value={password}
            onChange={setPassword}
            required
            autoComplete="current-password"
            error={fieldErrors.password}
          />

          {/* CR-145-BRC08 — the tick box is this utility's to offer. When it
              is not offered the row still holds "Forgot password?", which is
              why `justify-between` keeps that link at the right-hand edge with
              or without a box beside it. */}
          <div className="mx-0 mb-4 mt-1 flex items-center justify-between gap-2">
            {offersKeepSignedIn ? (
              <CheckboxField
                id="signin-keep"
                label={t("identity.signIn.keepSignedIn")}
                checked={keepSignedIn}
                onChange={setKeepSignedIn}
              />
            ) : (
              // ⚠ NOTHING IS SAID ABOUT THE ABSENCE. B14 rule 33 puts rationale
              // at ZERO words on screen, and "your utility has switched this
              // off" is rationale. The span holds the row's left edge so the
              // "Forgot password?" link does not slide across when the box is
              // not there — an empty element, not a message.
              <span />
            )}
            {/* CR-170-BRC10 — a LINK to its own page (BR-IDN-023 as amended
                2026-10-05). It navigates, so it is a link and not a button. */}
            <ButtonLink
              variant="ghost"
              className="p-0 text-sm"
              to={tenantPath(forgotPasswordPath(surface))}
            >
              {t("identity.signIn.forgot")}
            </ButtonLink>
          </div>

          {/* DEF-IDN-9777 — a technician at the web door gets the PO's two
              sentences (2026-10-06) and a real button into the field app;
              the plain "Field app" line under one sentence did not read as
              a way out. The other named door keeps its one sentence. */}
          {wrongDoor === FIELD_APP_ONLY_KEY ? (
            <FieldAppNotice layout="alert" href={tenantPath(FIELD_APP_SIGN_IN)} />
          ) : (
            wrongDoor !== null && (
              <div
                className="m-0 mb-4 border-l-3 border-l-danger-500 bg-danger-100 p-3 text-base text-danger-700"
                role="alert"
                data-def-ref="DEF-WRK-9583"
              >
                <p className="m-0">{t(wrongDoor)}</p>
              </div>
            )
          )}

          {failed && (
            // BR-IDN-002: ONE generic message, form-level (never under a field,
            // which would say WHICH input the server disliked).
            <p className="m-0 mb-4 border-l-3 border-l-danger-500 bg-danger-100 p-3 text-base text-danger-700" role="alert">
              {failureLine}
            </p>
          )}

          {/* `.signin-actions .btn` was a PARENT rule (full-width, centred
              label); Route B has no parent selector, so it travels down as the
              [&_.btn] variant — the same move DownloadButton recorded. */}
          <div className="flex [&_.btn]:w-full [&_.btn]:justify-center">
            <WorkingButton working={working} type="submit">
              {t("identity.signIn.submit")}
            </WorkingButton>
          </div>
        </form>
    </AuthCard>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-IDN-001@402b6db (story+rules snapshot hash — EP-IDN-01)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ tsc✔ eslint✔ vitest 239/239✔ (4 todo this file's suite — browser/journey/v2-deferred scope) · run_gates 9 PASS · 2 FAIL · 1 SKIP — BOTH FAILs are 06-backend-owned and in flight from the two backend lanes (G5 isolation collection errors, G10 backend stories still missing test_us_*_tc* files); reproduced IDENTICALLY with 07-frontend stashed, so nothing in this packet caused them · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E4 A13 designs no sign-in failure copy — the generic/lockout keys are PROPOSED copy, reported (the earlier E1 "no password control in the BR-SHL-017 field kit" is CLOSED: FormModal's PasswordField now owns it and this page composes it) · E4 the line naming which utility you are signing in to changed from a HOST to the tenant slug (`identity.signIn.tenant`, five locales) because the host no longer identifies a tenant — PROPOSED copy like its neighbours, reported
// amended: 2026-09-23 by lane SESSION-EXPIRY (DEF-SHL-6378) — the page reads ONE
//         query parameter, `?next=`, the tenant-relative page a person was on
//         when their session ended, and lands there after signing in. It goes
//         through `safeReturnPath` (routing/tenantPath.ts): a value that could
//         leave the origin or the tenant is dropped and the Dashboard is used,
//         so this is not an open redirect. The forced password change still
//         comes first.
// amended: 2026-10-04 by lane IDN-FIX (DEF-WRK-9583, CR-168-BRC10 R2) — a
//         `surface` prop: the field app mounts this page at
//         `/{tenant}/work/mobile/signin` as `"mobile"`, sends it, and lands on
//         the phone. ONE refusal is now named rather than flattened — the
//         wrong-door refusal of `BR-WRK-043`, reached by the server only AFTER
//         the password checked out, so it is no oracle (`surfaceRefusalKey`).
//         Every other failure still renders the one generic line.
// amended: 2026-10-05 by lane PWD (CR-170-BRC10) — "Forgot password?" is a
//         link to `/{tenant}/forgot-password` and the inline notice is gone;
//         `?changed=1` shows "Password changed. Sign in again." once; the
//         stage and card are the shared `AuthCard`.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
