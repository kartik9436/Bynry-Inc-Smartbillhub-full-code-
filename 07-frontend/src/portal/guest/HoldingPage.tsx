// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-001 (EP-CWP-01) TC-3 · US-CWP-069 TC-5 — the portal is off:
//           a holding page, no cards. Screens: CWP-001 (off state)
// Rules:    CLAUDE.md hard-won law 3 (defaults fail closed — a new tenant's
//           portal is OFF until a person turns it on) · CR-068 R8 · blueprint
//           B1 (*"turning the portal off shows a holding page; bills and
//           letters are unaffected"*) · rule 32 (one sentence)
// Tests:    src/portal/guest/FrontPage.test.tsx
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import type { PortalFront } from "../api/guestClient";

export function HoldingPage(props: { front: PortalFront }) {
  const { t } = useTranslation();
  return (
    <section
      className="mx-auto max-w-[640px] border border-neutral-200 bg-[white] p-4"
      data-screen="CWP-001"
      data-holding="true"
    >
      <p className="text-xs font-bold uppercase tracking-wide text-neutral-900">{props.front.tenant.name}</p>
      <h1 className="text-h1 leading-tight text-neutral-900">{t("portal.holding.title")}</h1>
      <p className="mt-1 text-body leading-relaxed text-neutral-600">{t("portal.holding.sentence")}</p>
    </section>
  );
}
