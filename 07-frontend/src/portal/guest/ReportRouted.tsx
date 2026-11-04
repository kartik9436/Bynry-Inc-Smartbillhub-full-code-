// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-007 (EP-CWP-03) TC-3 — *a smell of gas returns a phone
//           number and creates nothing*. Screens: CWP-006 (its second state)
// Rules:    US-CWP-007 §1, verbatim: ⚠ *"THE EMERGENCY PANEL IS ROUTING, NOT A
//           DISCLAIMER. A form that quietly accepts 'smell of gas' and queues
//           it behind a missed collection is worse than no form."* ·
//           B14 rule 36 (compose the kit) · rule 32 (one sentence)
// Tests:    src/portal/guest/ReportProblem.test.tsx
// Impacts:  06-backend/apps/portal/guest_api.reports (`created: false`)
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import type { ReportRoutedView } from "../api/guestClient";
import { Card, SectionTitle } from "../components/primitives";

/**
 * What a visitor sees instead of a confirmation. **There is no reference on
 * this screen, because nothing was created** — and saying "sent" over a row
 * that does not exist is the failure this whole path is designed against.
 */
export function ReportRouted(props: { routed: ReportRoutedView }) {
  const { t } = useTranslation();
  return (
    <div data-screen="CWP-006" data-routed="gas_smell">
      <Card testId="cwp006-routed">
        <SectionTitle>{t("portal.routed.kicker")}</SectionTitle>
        <h2 className="m-0 text-h3 font-bold leading-tight text-neutral-900">
          {t("portal.routed.title")}
        </h2>
        <p className="m-0 max-w-measure text-body text-neutral-700">
          {t("portal.routed.body")}{" "}
          <span className="font-bold text-neutral-900" data-emergency-phone="">
            {props.routed.emergency_phone ?? t("portal.routed.noPhone")}
          </span>
        </p>
        <p className="m-0 text-body text-neutral-600">{t("portal.routed.note")}</p>
      </Card>
    </div>
  );
}
