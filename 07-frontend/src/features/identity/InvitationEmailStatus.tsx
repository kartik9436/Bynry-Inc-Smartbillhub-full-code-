// ── Trace ──────────────────────────────────────────────
// Change:   CR-188-BRC10 (PO 2026-10-22, decision log *"Staff invitation email:
//           a one-time sign-in link, not a password; six answers"*)
// UI:       B14 rules 21 (Tailwind only — listed in route-b-migrated.txt),
//           33 (a fact ≤ 6 words; an instruction ≤ 6 words per sentence),
//           43 (a component, not page code)
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import type { InvitationEmail } from "@/api/endpoints";

/**
 * CR-188-BRC10 — the one line that says whether the link was emailed.
 * Emailed → a fact. Not emailed → an alert naming why, and what to do instead
 * (share the password shown below). Every reason the server can send has its
 * own sentence; an unknown one reads as the generic *could not be queued*.
 */
export function InvitationEmailStatus(props: {
  invitation: InvitationEmail;
  kind: "invite" | "reset";
}) {
  const { t } = useTranslation();
  const { invitation, kind } = props;
  if (invitation.status === "queued") {
    return (
      <p className="m-0 mb-2 text-sm text-success-700" data-testid="invitation-email-status">
        {t(kind === "reset" ? "settings.users.invite.resetEmailed" : "settings.users.invite.emailed", {
          email: invitation.email ?? "",
        })}
      </p>
    );
  }
  const reason = invitation.reason_code ?? "email_unavailable";
  return (
    <p
      className="m-0 mb-2 border-l-3 border-l-warning-500 bg-warning-100 p-3 text-sm text-warning-700"
      role="alert"
      data-testid="invitation-email-status"
    >
      {t(kind === "reset" ? "settings.users.invite.resetNotEmailed" : "settings.users.invite.notEmailed")}{" "}
      {t(`settings.users.invite.reason.${reason}`, {
        defaultValue: t("settings.users.invite.reason.email_unavailable"),
      })}{" "}
      {t("settings.users.invite.sharePassword")}
    </p>
  );
}
