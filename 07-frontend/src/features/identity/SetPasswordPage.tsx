// ── Trace ──────────────────────────────────────────────
// Change:   CR-188-BRC10 (PO 2026-10-22, decision log *"Staff invitation email:
//           a one-time sign-in link, not a password; six answers"*)
// Rules:    BR-IDN-022 (the person sets their own password; then signs in
//           again — as amended 2026-10-05) · BR-IDN-011 (it activates an
//           invited membership) · BR-IDN-002 (one refusal for every dead link)
// UI:       B14 rules 21 (Tailwind only), 33 (text capped by purpose), 43
//           (built on the shared AuthCard and PasswordField)
// ───────────────────────────────────────────────────────
/**
 * THE SET-PASSWORD PAGE, at `/{tenant}/set-password#token=…` — public, signed out.
 *
 * ⚠ **THE TOKEN ARRIVES IN THE URL FRAGMENT** (decision log 2026-10-22,
 * MERGE-ACCESS): a browser never sends a fragment to a server, so no server or
 * proxy log holds it. A link emailed before that change carries `?token=…` and
 * still works for its lifetime; the fragment wins where both are present. The
 * token is held in state and taken off the address bar (`routing/useLinkSecret`).
 *
 * The emailed one-time sign-in link lands here. The page first asks the
 * server whether the link is live (`POST auth/password-link/check`) — so a
 * person with a dead link is told before they type a password — then takes
 * New + Confirm and spends it (`/complete`). On success the person signs in
 * with the password they chose, exactly as after the forced change
 * (`?changed=1` → *"Password changed. Sign in again."*).
 *
 * Like `ChangePasswordPage`, it does not restate the utility's password rules:
 * the server's refusal names each broken rule on the field.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { checkPasswordLink, completePasswordLink } from "@/api/endpoints";
import type { ApiClient } from "@/api/client";
import { api, isApiError } from "@/api/client";
import { AuthCard } from "@/components/AuthCard";
import { ButtonLink } from "@/components/Button";
import { PasswordField, collectFormErrors } from "@/components/FormModal";
import { LoadingSkeleton, WorkingButton } from "@/components/StateFrame";
import {
  changePasswordSchema,
  splitPasswordRefusal,
  type PasswordRefusal,
} from "@/features/identity/ChangePasswordPage";
import { PASSWORD_CHANGED_PARAM, SET_PASSWORD_TOKEN_PARAM } from "@/features/identity/SignInPage";
import { useLinkSecret } from "@/routing/useLinkSecret";
import { SIGNIN_SEGMENT, useTenantPath } from "@/routing/tenantPath";

export interface SetPasswordPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

/** The one refusal every dead link gets (BR-IDN-002). */
export const LINK_NOT_ACCEPTED_KEY = "errors.identity.password_link_not_accepted";

const TOKEN_KEYS = [SET_PASSWORD_TOKEN_PARAM] as const;

export function SetPasswordPage(props: SetPasswordPageProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  // Held after the address is cleaned, so the replace never reads as "no token".
  const token = useLinkSecret(TOKEN_KEYS)[SET_PASSWORD_TOKEN_PARAM] ?? "";

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<PasswordRefusal | null>(null);
  const [dead, setDead] = useState(false);

  const check = useQuery({
    queryKey: ["password-link", token],
    queryFn: () => checkPasswordLink(token, client),
    enabled: token !== "",
    retry: false,
    staleTime: Infinity,
  });

  const mutation = useMutation({
    mutationFn: () =>
      completePasswordLink(
        { token, new_password: newPassword, confirm_password: confirmPassword },
        client,
      ),
    onSuccess: () => {
      navigate(tenantPath(`${SIGNIN_SEGMENT}?${PASSWORD_CHANGED_PARAM}=1`), { replace: true });
    },
    onError: (error: unknown) => {
      if (isApiError(error) && error.messageKey === LINK_NOT_ACCEPTED_KEY) {
        setDead(true);
        return;
      }
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

  if (token !== "" && check.isPending) {
    return (
      <AuthCard page="set-password" title={t("identity.setPassword.title")}>
        <LoadingSkeleton variant="card" rows={2} />
      </AuthCard>
    );
  }

  if (token === "" || check.isError || dead) {
    return (
      <AuthCard
        page="set-password"
        title={t("identity.setPassword.deadTitle")}
        lede={t("identity.setPassword.deadBody")}
      >
        <ButtonLink
          variant="primary"
          className="w-full justify-center"
          to={tenantPath(SIGNIN_SEGMENT)}
        >
          {t("identity.forgotPassword.back")}
        </ButtonLink>
      </AuthCard>
    );
  }

  function handleSubmit(): void {
    if (mutation.isPending) {
      return;
    }
    const validation = collectFormErrors(changePasswordSchema(t), {
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
    setFieldErrors(validation.errors);
    if (validation.count > 0) {
      return;
    }
    setRefusal(null);
    mutation.mutate();
  }

  const serverFieldError = (field: string): string | undefined => {
    const messages = (refusal?.fieldMessages ?? [])
      .filter((entry) => entry.field === field)
      .map((entry) => t(entry.key, entry.params));
    return messages.length === 0 ? undefined : messages.join(" ");
  };

  return (
    <AuthCard
      page="set-password"
      kicker={check.data?.utility_name}
      title={t("identity.setPassword.title")}
      lede={t("identity.setPassword.lede")}
    >
      {check.data !== undefined && (
        <p className="m-0 mb-4 text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
          {t("identity.setPassword.for", { email: check.data.email })}
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
          id="set-password-new"
          label={t("identity.changePassword.newPassword")}
          value={newPassword}
          onChange={setNewPassword}
          required
          autoComplete="new-password"
          error={fieldErrors.new_password ?? serverFieldError("new_password")}
        />
        <PasswordField
          id="set-password-confirm"
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
        <div className="mt-4 flex [&_.btn]:w-full [&_.btn]:justify-center">
          <WorkingButton working={mutation.isPending} type="submit">
            {t("identity.setPassword.submit")}
          </WorkingButton>
        </div>
      </form>
    </AuthCard>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// generated: 2026-10-22 by lane STAFF-INVITE (CR-188-BRC10)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
