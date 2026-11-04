// ── Trace ──────────────────────────────────────────────
// Story:    US-IDN-002 (EP-IDN-01 §Stories)  Screens: no A1 id — see `exceptions`
// Defect:   DEF-IDN-5653 — every invited user was locked out. Sign-in SUCCEEDED,
//           redirected here, and this screen did not exist.
// Rules:    BR-IDN-022 (forced change on first sign-in; no app surface until it
//           is done) · BR-IDN-011 (a successful forced change ACTIVATES an
//           INVITED membership) · BR-IDN-005 (it revokes every PRIOR session) ·
//           BR-IDN-021 (no email is sent — the temp password is handed over) ·
//           BR-SHL-017 (field kit + inline validation) · BR-SHL-020 (plain language)
// UI:       B14 rule 21 (Tailwind utilities, no stylesheet class — this file is
//           on `styles/route-b-migrated.txt`) · rule 31 (no internal reference
//           on screen) · rule 33 (on-screen text is capped by what it is for)
// ───────────────────────────────────────────────────────
/**
 * THE FORCED PASSWORD CHANGE, at `/{tenant}/change-password`.
 *
 * Every user a System Admin invites arrives here: `services.create_user` hands
 * out a temporary password and sets `must_change_password`, sign-in succeeds,
 * and `SignInPage` sends them to this address instead of the dashboard. Until
 * this file existed the address had NOTHING behind it, so an invited user was
 * authenticated and stranded — and could not dig their way out, because the
 * only thing that clears the flag is this screen and a password RESET sets the
 * same flag again.
 *
 * FOUR THINGS ABOUT THIS SCREEN ARE DECIDED BY THE SERVER, NOT BY TASTE. Each
 * one was read out of the code rather than assumed, and each is the reason a
 * reasonable-looking alternative is wrong:
 *
 * 1 · IT RENDERS OUTSIDE THE APP SHELL, and that is what the defect was.
 *     `App.tsx` had already written the requirement down — *"When that screen
 *     lands it must render OUTSIDE the shell, since it gates every app
 *     screen."* Inside the shell it cannot work even in principle: the shell
 *     boots by reading the tenant's own settings, `IdentitySessionAuthentication`
 *     refuses every one of those reads while a change is owed, and the shell
 *     dies on its own first fetch. That is exactly what the PO photographed —
 *     *"We couldn't load your regional settings."* with a Retry button, on this
 *     address. So this route is a SIBLING of `signin`, not a child of the shell.
 *
 * 2 · IT NEVER ASKS FOR THE CURRENT PASSWORD. `services.change_password` reads
 *     `forced = actor.must_change_password` and skips the current-password
 *     check entirely when it is set. A field the server ignores, in front of a
 *     user who by definition holds only a temporary credential, is a locked
 *     door with no keyhole.
 *
 * 3 · IT DOES NOT FETCH THE TENANT'S PASSWORD RULES, AND NOT FOR WANT OF AN
 *     ENDPOINT. `GET /settings/security-policy` exists and has a client. It is
 *     UNREACHABLE from this state: `identity/auth.py`'s `_FORCED_CHANGE_EXEMPT`
 *     admits exactly two calls while a change is owed — `POST /me/password` and
 *     `DELETE /auth/session` — and every other authenticated read is refused
 *     403 `errors.auth.password_change_required`. Listing the rules here would
 *     therefore mean HARDCODING a copy of a per-tenant policy, which drifts the
 *     first time a utility raises its minimum length. So the rules come from
 *     the server's own refusal: `validate_new_password` returns one
 *     `field_error` per broken rule, and they render on the field.
 *
 * 4 · AFTER THE CHANGE THE SESSION IS ENDED AND THE USER SIGNS IN AGAIN —
 *     A PO RULING, NOT A SERVER REQUIREMENT (`CR-170-BRC10`, BR-IDN-022 as
 *     amended 2026-10-05: *"once user set the password user redirect to login
 *     page"*). The server would let the session survive: `MePasswordView`
 *     passes `current_session=request.auth` and `revoke_sessions(except_session=…)`
 *     excludes it. So this screen ends it itself, through the EXISTING sign-out
 *     — `signOut()`, `DELETE /auth/session`, which `_FORCED_CHANGE_EXEMPT`
 *     admits — forgets the cached session exactly as the shell's sign-out does,
 *     and lands on the door the person came in by with `?changed=1`, which the
 *     sign-in page turns into *"Password changed. Sign in again."* once.
 *     ⚠ UNTIL 2026-10-05 THIS POINT ARGUED THE OPPOSITE — that sending the user
 *     back to sign-in made them type the password they had just chosen "for no
 *     reason the server asked for". That was true of the server and is now
 *     overruled by the PO; the reason is theirs, and it is recorded here so the
 *     next reader does not "fix" it back.
 *
 * ⚠ **IT IS THE FORCED CHANGE ONLY.** A user who does not owe one is sent to
 * the dashboard rather than shown a form that would fail: without
 * `must_change_password` the server requires `current_password`, which this
 * screen deliberately does not collect. The shell's *"Change password"* user-
 * menu item is that OTHER screen and stays held — see the report.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { resetAnalytics, track } from "@/analytics";
import { changePassword, getMe, signOut } from "@/api/endpoints";
import type { ApiClient } from "@/api/client";
import { api, isApiError } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { PasswordField, collectFormErrors } from "@/components/FormModal";
import { WorkingButton } from "@/components/StateFrame";
import { AuthCard } from "@/components/AuthCard";
import {
  DASHBOARD_ROUTE,
  FIELD_APP_HOME,
  FIELD_APP_SIGN_IN,
  PASSWORD_CHANGED_PARAM,
} from "@/features/identity/SignInPage";
import { RETURN_PARAM, SIGNIN_SEGMENT, safeReturnPath, useTenantPath } from "@/routing/tenantPath";

// ── Pure pieces (provable without a browser or a network) ──────────────────

// ⚠ **THIS FILE DEFINES NO ROUTE CONSTANT OF ITS OWN, ON PURPOSE.** The address
// is `SignInPage`'s `FORCED_PASSWORD_CHANGE_ROUTE`, and `App.tsx` mounts THAT —
// so the door and the room behind it are one string and cannot drift apart.
// `DEF-IDN-5653` is what a second spelling costs.

/**
 * BR-SHL-017 client validation — UX only; the SERVER is authoritative (B8).
 *
 * It asks the two things the server would answer identically and instantly:
 * that both boxes are filled, and that they match. It deliberately checks NO
 * length, case or symbol rule, because those are the tenant's policy and this
 * screen is not allowed to hold a copy of it (see 3 in the file docstring).
 */
export function changePasswordSchema(t: (key: string) => string) {
  return z
    .object({
      new_password: z.string().min(1, t("identity.changePassword.required")),
      confirm_password: z.string().min(1, t("identity.changePassword.required")),
    })
    .refine((values) => values.new_password === values.confirm_password, {
      path: ["confirm_password"],
      message: t("identity.changePassword.mismatch"),
    });
}

/**
 * The server's refusal, split the way the screen renders it.
 *
 * `validate_new_password` raises ONE ValidationError carrying one `field_error`
 * per broken rule, all of them on `new_password`, plus a form-level
 * `message_key` of `errors.identity.password_policy` — whose English reads
 * *"…doesn't meet the rules below"*. There are no rules below on this screen,
 * so rendering both would print a sentence that points at nothing. The field
 * errors ARE the rules, so when there are any they are the whole answer and the
 * form-level line is dropped; when there are none (an expired temp password, a
 * mismatch the client let through) the form-level line is all there is.
 *
 * Pure, so the split is provable without a network — and it takes the ENVELOPE
 * rather than the error object so a test can hand it a shape rather than build
 * an `ApiError`.
 */
export interface PasswordRefusal {
  /** Every rule the new password broke, in the server's order, ready to read. */
  fieldMessages: readonly { field: string; key: string; params: Record<string, unknown> }[];
  /** The whole-form refusal, or null when the field messages carry it. */
  formKey: string | null;
  formParams: Record<string, unknown>;
}

export function splitPasswordRefusal(envelope: {
  message_key: string;
  params?: Record<string, unknown>;
  field_errors?: readonly { field: string | null; message_key: string; params?: Record<string, unknown> }[];
}): PasswordRefusal {
  const fieldMessages = (envelope.field_errors ?? [])
    .filter((entry) => entry.field !== null)
    .map((entry) => ({
      field: entry.field as string,
      key: entry.message_key,
      params: entry.params ?? {},
    }));
  return {
    fieldMessages,
    formKey: fieldMessages.length > 0 ? null : envelope.message_key,
    formParams: envelope.params ?? {},
  };
}

/**
 * CR-170-BRC10 — the sign-in door a completed forced change returns to, with
 * the one-time flag. Pure, so the rule is provable without a browser.
 *
 * The person came in by one of two doors and goes back out by the same one: a
 * field technician (whose way on was the phone) to the field app's sign-in,
 * everyone else to the staff sign-in — the staff door would refuse a
 * technician's login (`BR-WRK-043`).
 */
export function signInAfterPasswordChange(destination: string): string {
  const door = destination === FIELD_APP_HOME ? FIELD_APP_SIGN_IN : SIGNIN_SEGMENT;
  return `${door}?${PASSWORD_CHANGED_PARAM}=1`;
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface ChangePasswordPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function ChangePasswordPage(props: ChangePasswordPageProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const client = props.client ?? api;
  // DEF-WRK-9583 — where the person was going before the change was owed (an
  // invited field technician: the phone). `safeReturnPath` keeps it inside
  // this tenant; anything it will not vouch for is the Dashboard, as before.
  const [searchParams] = useSearchParams();
  const destination = safeReturnPath(searchParams.get(RETURN_PARAM)) ?? DASHBOARD_ROUTE;

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<PasswordRefusal | null>(null);

  // ⚠ **THE SESSION IS READ FROM CACHE AND IS ALLOWED TO BE ABSENT, AND BOTH
  // HALVES OF THAT COST A ROUND OF THIS DEFECT.**
  //
  // `GET /me` is one of the calls `_FORCED_CHANGE_EXEMPT` does NOT admit — a
  // user who owes a change gets 403 on it like every other read — so this
  // screen can never FETCH the session, and `enabled` is off for good.
  //
  // It can also never REQUIRE it. `SignInPage` navigates here straight after
  // `POST /auth/session`, and until the companion change in that file it wrote
  // nothing into this key, so the cache was empty on the one path that matters.
  // The first draft of this screen treated "no session in cache" as "not signed
  // in" and redirected to `/signin` — which sent the invited user back to the
  // door they had just come through, i.e. THE SAME LOCKOUT WITH A TIDIER
  // BOUNCE. ⚠ **AND EVERY TEST PASSED, because the fixture seeds this key**:
  // the harness handed the screen a state the product never produced. That is
  // why the walkthrough exists and why it is the proof that counts (law 6).
  //
  // So: a session in cache is used to GREET the user and to step aside for
  // somebody who owes no change. No session in cache — a reload on this
  // address, a cold tab — still renders the form, because the person standing
  // here has a temporary password and nothing else to try.
  const meQuery = useQuery({
    queryKey: queryKeys.me,
    queryFn: () => getMe(client),
    enabled: false,
  });

  const mutation = useMutation({
    mutationFn: () =>
      changePassword({ new_password: newPassword, confirm_password: confirmPassword }, client),
    onSuccess: async () => {
      // CR-170-BRC10 (see 4 in the file docstring) — the session is ENDED
      // through the existing sign-out, then the person signs in again with the
      // password they just chose. A failed DELETE still lands them on sign-in,
      // as the shell's own sign-out does: the cookie is httpOnly and the
      // server refuses a dead one on the next request anyway.
      try {
        await signOut(client);
      } catch {
        // deliberately nothing — the shell's sign-out fails on the same side
      }
      track("user_signed_out", { reason: "password_changed" });
      resetAnalytics();
      queryClient.clear(); // BR-SHL-009 — nothing of the old session readable after
      // `replace`, so Back cannot return to a form whose session is gone. No
      // toast: the sign-in page says it once, in the PO's words.
      navigate(tenantPath(signInAfterPasswordChange(destination)), { replace: true });
    },
    onError: (error: unknown) => {
      if (isApiError(error)) {
        setRefusal(
          splitPasswordRefusal({
            message_key: error.messageKey,
            params: error.params,
            field_errors: error.fieldErrors,
          }),
        );
        return;
      }
      setRefusal({ fieldMessages: [], formKey: "api.error.unexpected", formParams: {} });
    },
  });

  function handleSubmit(): void {
    if (mutation.isPending) {
      return; // one submit in flight (A18 §3) — double-clicks are harmless
    }
    const validation = collectFormErrors(changePasswordSchema(t), {
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
    setFieldErrors(validation.errors);
    if (validation.count > 0) {
      return; // nothing is posted until the shape is right
    }
    setRefusal(null);
    mutation.mutate();
  }

  const session = meQuery.data;
  // Only a POSITIVE answer moves anybody: a session that says the change is
  // already done. Absence is not an answer and must not be treated as one.
  if (session !== undefined && !session.must_change_password) {
    return <Navigate to={tenantPath(destination)} replace />;
  }

  // The server's rules for the new password, each on the field it refused.
  // Joined rather than truncated: rule 33 prefers two short sentences to one
  // long one, and the server already writes them that way.
  const serverFieldError = (field: string): string | undefined => {
    const messages = (refusal?.fieldMessages ?? [])
      .filter((entry) => entry.field === field)
      .map((entry) => t(entry.key, entry.params));
    return messages.length === 0 ? undefined : messages.join(" ");
  };

  return (
    // The stage and the card are SignInPage's — since CR-170-BRC10 literally,
    // one `AuthCard` (B14 rule 43): this is the screen immediately after it and
    // a user crosses between them in one click.
    <AuthCard
      page="change-password"
      kicker={t("identity.changePassword.kicker")}
      title={t("identity.changePassword.title")}
      lede={t("identity.changePassword.lede")}
    >
        {/* Which account this is about. Rule 31: an email address is what the
            person uses to sign in, not an internal identifier. It is DROPPED
            rather than faked when the session is not in cache — a line that
            says "Signed in as undefined" is worse than no line. */}
        {session !== undefined && (
          <p className="m-0 mb-4 text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
            {t("identity.changePassword.signedInAs", { email: session.email })}
          </p>
        )}

        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            handleSubmit();
          }}
        >
          <PasswordField
            id="change-password-new"
            label={t("identity.changePassword.newPassword")}
            value={newPassword}
            onChange={setNewPassword}
            required
            autoComplete="new-password"
            error={fieldErrors.new_password ?? serverFieldError("new_password")}
          />

          <PasswordField
            id="change-password-confirm"
            label={t("identity.changePassword.confirmPassword")}
            value={confirmPassword}
            onChange={setConfirmPassword}
            required
            autoComplete="new-password"
            error={fieldErrors.confirm_password ?? serverFieldError("confirm_password")}
          />

          {refusal?.formKey != null && (
            <p
              className="m-0 mb-4 border-l-3 border-l-danger-500 bg-danger-100 p-3 text-base text-danger-700"
              role="alert"
            >
              {t(refusal.formKey, refusal.formParams)}
            </p>
          )}

          {/* `.signin-actions .btn` was a PARENT rule (full-width, centred
              label); Route B has no parent selector, so it travels down as the
              [&_.btn] variant — the same move SignInPage records. */}
          {/* `mt-4` where SignInPage gets its gap from the keep-signed-in row.
              This screen has no such row, so without it the commit button sits
              flush against the confirm field — visible side by side with its
              sibling, which is the only way this kind of thing is ever found
              (law 6). */}
          <div className="mt-4 flex [&_.btn]:w-full [&_.btn]:justify-center">
            <WorkingButton working={mutation.isPending} type="submit">
              {t("identity.changePassword.submit")}
            </WorkingButton>
          </div>
        </form>
    </AuthCard>
  );
}
