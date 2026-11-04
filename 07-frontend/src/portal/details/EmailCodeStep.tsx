// ── Trace ──────────────────────────────────────────────
// Change:   CR-189-BRC10 — a signed-in customer's new email is confirmed by a
//           code sent to it (PO 2026-10-22, option A; DEF-CWP-10401).
// Rules:    decision log 2026-10-22 "Who moves the portal sign-in email…" ·
//           B14 rules 21 (Tailwind; `portal/` is on route-b-migrated.txt) ·
//           33 (a refusal is five or six words) · 35 (the catalogue writes the
//           words) · 43 (a piece of UI is a component)
// Tests:    src/portal/details/MyDetails.dom.test.tsx
// Impacts:  src/portal/details/MyDetails.tsx (its one caller)
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { DialInput, DisabledCommit, FormField } from "../components/primitives";
import {
  confirmSignedInEmailChange,
  startSignedInEmailChange,
  type UpdateEmailStarted,
} from "../api/updateEmailClient";
import { Announced } from "../components/a11y";

/** A code went out; this is what the step needs to show and to confirm. */
export interface PendingEmail {
  email: string;
  ref: string;
  sentTo: string;
  minutes: number;
}

/** The sentence for a refusal key the two calls can answer (all catalogued). */
export function emailCodeRefusal(reason: string | undefined): string {
  switch (reason) {
    case "email_required":
    case "email_invalid":
    case "start_again":
      return `portal.updateEmail.reason.${reason}`;
    case "unchanged":
      return "portal.myDetails.emailCode.unchanged";
    case "expired":
    case "locked":
      return `portal.enrol.code.${reason}`;
    default:
      return "portal.enrol.code.wrong";
  }
}

/** Ask for a code to `email`. `null` pending means refused, with its key. */
export async function startEmailCode(
  email: string,
): Promise<{ pending: PendingEmail | null; refusal: string | null }> {
  const started: UpdateEmailStarted = await startSignedInEmailChange({ email });
  if (!started.ok || !started.ref) {
    return { pending: null, refusal: emailCodeRefusal(started.reason) };
  }
  return {
    pending: {
      email,
      ref: started.ref,
      sentTo: started.sent_to ?? "",
      minutes: started.expires_in_minutes ?? 0,
    },
    refusal: null,
  };
}

/**
 * The code step under *My details*' email box. Nothing has moved yet: only
 * when the code comes back do the contact email and the sign-in email change
 * together (the server's `confirm_signed_in_change`).
 */
export function EmailCodeStep(props: {
  pending: PendingEmail;
  onResent: (pending: PendingEmail) => void;
  onDone: () => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [code, setCode] = useState("");
  const [working, setWorking] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);

  function confirm() {
    setWorking(true);
    setRefused(null);
    confirmSignedInEmailChange({ ref: props.pending.ref, code, email: props.pending.email })
      .then((done) => {
        setWorking(false);
        if (done.ok) props.onDone();
        else setRefused(t(emailCodeRefusal(done.reason)));
      })
      .catch(() => {
        setWorking(false);
        setRefused(t("portal.myDetails.couldNotSave"));
      });
  }

  function resend() {
    setRefused(null);
    setCode("");
    startEmailCode(props.pending.email)
      .then((answer) => {
        if (answer.pending !== null) props.onResent(answer.pending);
        else setRefused(t(answer.refusal ?? "portal.enrol.code.wrong"));
      })
      .catch(() => setRefused(t("portal.myDetails.couldNotSave")));
  }

  return (
    <div className="flex flex-col gap-3" data-my-email-code="">
      <p className="text-md font-semibold text-neutral-900">
        {t("portal.myDetails.emailCode.title")}
      </p>
      <p className="text-body leading-relaxed text-neutral-600" role="status">
        {t("portal.updateEmail.sentTo")}{" "}
        <strong data-my-email-sentto="">{props.pending.sentTo}</strong>
        {". "}
        {t("portal.updateEmail.lasts", { count: props.pending.minutes })}
      </p>
      <div className="flex max-w-[240px] flex-col gap-3">
        <FormField id="my-email-code" label={t("portal.enrol.sixDigit")} required>
          <DialInput id="my-email-code" value={code} onChange={setCode} maxLength={6} />
        </FormField>
      </div>
      {refused !== null ? (
        <Announced tone="error" className="text-body font-semibold text-danger-700" data-my-email-refused="">
          {refused}
        </Announced>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        {code.trim() === "" ? (
          // F-22 (`DEF-CWP-10569`): a Confirm with no code says why, as text
          // tied to the button — the words Add an account already uses.
          <DisabledCommit label={t("portal.updateEmail.confirm")} reason={t("portal.addAccount.needCode")} />
        ) : (
          <Button variant="primary" disabled={working} onClick={confirm}>
            {t("portal.updateEmail.confirm")}
          </Button>
        )}
        <Button variant="secondary" size="sm" onClick={resend}>
          {t("portal.enrol.resend")}
        </Button>
        <Button variant="ghost" size="sm" onClick={props.onCancel}>
          {t("portal.myDetails.emailCode.keepOld")}
        </Button>
      </div>
    </div>
  );
}
