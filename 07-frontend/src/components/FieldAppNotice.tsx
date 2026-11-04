// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-IDN-9777 (2026-10-06, PO) — a Field Technician at the STAFF
//          web app's door was told only "Sign in on the field app."
// Rules:   BR-WRK-043 / OQ-WRK-1494 (technicians use the mobile app only) ·
//          B14 rule 33 — this message is a PO-RULED EXCEPTION to the six-word
//          cap, for these two screens only (decision log 2026-10-06) · rule 43
//          (one piece of UI, one component) · rule 21 (Tailwind utilities)
// ───────────────────────────────────────────────────────
/**
 * THE WRONG-DOOR NOTICE FOR A FIELD TECHNICIAN — the two sentences the PO
 * approved on 2026-10-06, verbatim, and one button into the field app:
 *
 *   "Field Technicians do not have access to the staff portal."
 *   "Please sign in on the Field Technician mobile app instead."
 *   [Open the field app]
 *
 * Two places show it, and they are the only two (that is the scope of the
 * ruling): the sign-in page's error box when the server refuses a technician
 * at the web door, and the staff shell's whole page when its boot read answers
 * 403. `layout` picks between them; the words and the button are the same.
 *
 * The button is an `<a href>` because it NAVIGATES — into the field app, which
 * is its own application root. On the shell the web session must be ended
 * first, so `onOpen` takes over the click and does that; without it the link
 * simply goes.
 */
import { useTranslation } from "react-i18next";
import type { MouseEvent } from "react";

import { AuthCard } from "@/components/AuthCard";
import { ButtonAnchor } from "@/components/Button";

/** The server's refusal key — the first sentence. */
export const FIELD_APP_ONLY_KEY = "identity.signIn.fieldAppOnly";

export interface FieldAppNoticeProps {
  /** `alert` — inside the sign-in form; `page` — the whole screen. */
  layout: "alert" | "page";
  /** The field app's sign-in address, tenant-qualified. */
  href: string;
  /** Runs instead of plain navigation (the shell signs out first). */
  onOpen?: () => void;
}

export function FieldAppNotice({ layout, href, onOpen }: FieldAppNoticeProps) {
  const { t } = useTranslation();
  const open = (
    <ButtonAnchor
      variant="primary"
      className="w-full justify-center"
      href={href}
      onClick={
        onOpen === undefined
          ? undefined
          : (event: MouseEvent<HTMLAnchorElement>) => {
              event.preventDefault();
              onOpen();
            }
      }
    >
      {t("identity.signIn.openFieldApp")}
    </ButtonAnchor>
  );

  if (layout === "page") {
    return (
      <AuthCard
        page="field-app-only"
        title={t(FIELD_APP_ONLY_KEY)}
        lede={t("identity.signIn.fieldAppOnlyNext")}
      >
        {open}
      </AuthCard>
    );
  }

  return (
    <div
      className="m-0 mb-4 border-l-3 border-l-danger-500 bg-danger-100 p-3 text-base text-danger-700"
      role="alert"
      data-def-ref="DEF-IDN-9777"
    >
      <p className="m-0">{t(FIELD_APP_ONLY_KEY)}</p>
      <p className="m-0 mt-1">{t("identity.signIn.fieldAppOnlyNext")}</p>
      <div className="mt-3">{open}</div>
    </div>
  );
}
