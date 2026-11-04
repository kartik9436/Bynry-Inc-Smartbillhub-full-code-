// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-IDN-10365 (CR-187-BRC10) — the office never saw a field
//           technician's phone app code. `POST users` answered it and the web
//           showed only the temporary password; `POST users/{id}/activation-code`
//           had no button.
// Rules:    R105 (CR-187-BRC10: the office hands a technician a six-character
//           code that claims the native app; valid 7 days) · BR-IDN-022 (a
//           credential is shown ONCE, never retrievable) · B14 rules 21 (new UI
//           is Tailwind), 31 (nothing internal on screen), 33 (label ≤ 3 words,
//           fact ≤ 6), 43 (a piece of UI is a component)
// ───────────────────────────────────────────────────────
/**
 * The panel that carries a phone app code. It is a COMPONENT rather than markup
 * inside `SettingsUsersTab` (B14 rule 43) because two places show one: the
 * add-user result, beside the temporary password, and the row action that
 * issues a new code. Both are the same once-only value with the same expiry.
 *
 * It takes the code as a prop and has no other way to obtain one — no fetch,
 * no cache read, no stored fallback — so it cannot show a code the server did
 * not just return. The server keeps only an HMAC of it; once this panel is
 * dismissed, the only recovery is a NEW code, which voids this one.
 *
 * The Copy button reports only what actually happened: `navigator.clipboard`
 * is absent in a non-secure context, and a Copy that silently did nothing
 * would read as success (`IssuedKeyPanel`'s precedent, `MachineKeysPage`).
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Kicker, Note } from "@/components/TextBits";

export interface IssuedActivationCode {
  code: string;
  /** ISO instant — issued + 7 days (`ACTIVATION_CODE_VALID_DAYS`). */
  expiresAt: string;
}

export function PhoneAppCodePanel(props: {
  issued: IssuedActivationCode;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** Standalone (a reissue) names who the code is for; inside the add-user
   *  result the surrounding panel already does. */
  forEmail?: string;
  /** Standalone only — inside the add-user result one dismiss closes both. */
  onDismiss?: () => void;
}) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(props.issued.code);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div
      className="flex flex-col items-start gap-2 border border-divider bg-surface p-4"
      data-phone-app-code=""
      role={props.onDismiss === undefined ? undefined : "alert"}
    >
      <Kicker>{t("settings.users.phoneCode.kicker")}</Kicker>
      {props.forEmail !== undefined && (
        <p className="m-0 text-base">{t("settings.users.tempPassword.for", { email: props.forEmail })}</p>
      )}
      <code
        className="select-all border border-divider bg-bg px-3 py-2 font-heading text-h3 tracking-widest"
        data-phone-app-code-value=""
      >
        {props.issued.code}
      </code>
      <p className="m-0 text-base">
        {t("settings.users.phoneCode.expires", {
          date: formatDate(props.issued.expiresAt, props.timeZone, props.dateFormat),
        })}
      </p>
      <Note>{t("settings.users.phoneCode.onceOnly")}</Note>
      <div className="flex items-center gap-3">
        <Button variant="primary" size="sm" type="button" onClick={() => void copy()}>
          {copied ? t("settings.users.phoneCode.copied") : t("settings.users.phoneCode.copy")}
        </Button>
        {props.onDismiss !== undefined && (
          <Button variant="secondary" size="sm" type="button" onClick={props.onDismiss}>
            {t("settings.users.tempPassword.dismiss")}
          </Button>
        )}
      </div>
    </div>
  );
}
