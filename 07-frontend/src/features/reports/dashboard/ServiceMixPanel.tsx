// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 4 `P4.11`. Screen `3·1` region ⑦, drawn on p036
//          and annotated on p037 ⑦, read as IMAGES per B14 rule 42.
// Rules:   B14 rule 43 · rule 21 · CLAUDE.md hard rule 2 (money DISPLAY 2) ·
//          BR-REP-025 (the TENANT's own services, in the platform's seed order)
// Tests:   07-frontend/src/features/reports/reportsDashboard.dom.test.tsx
// Impacts: ReportsDashboardPage.tsx
// ───────────────────────────────────────────────────────
//
// `Service mix` — EVERY ENABLED SERVICE, PLUS THE NAMED REMAINDER.
//
// ⚠ **BARS ARE PROPORTIONAL TO THE LARGEST SERVICE AND NEVER TO A TOTAL**
// (p037 ⑦, verbatim: *"bars are proportional to the LARGEST service and never
// to a total, because eleven services can be enabled and a stacked bar of
// eleven is unreadable"*). `ContributionBars` already does exactly that and
// says so in its own header — *"the proportion is against the LARGEST ROW
// rather than against the total"* — so the arithmetic lives in ONE component
// rather than being repeated here (B14 rule 43, and the PO's *"dont create
// duplcate code"*).
//
// ⚠ **THE SERVICE ORDER IS THE SERVER'S AND IS NEVER TYPED HERE.** CLAUDE.md
// records the cost twice: the front end types the service list out by hand in
// `SignupWizard.tsx` and `ratingShared.tsx`, and an eleventh service therefore
// *"does NOT appear on screen on its own and it fails SILENTLY"*. The rows
// arrive in the tenant's own seed order and are rendered in the order given.
//
// ⚠ **A ROW WITH NO SERVICE IS THE NAMED REMAINDER AND IS KEPT LAST.** The
// drawing calls it *Not attributable* and draws it at `0.00`. Dropping a zero
// row would make the panel fail to add up to the report behind it, silently —
// which is the disagreement this whole screen is arranged to make impossible.
import { useTranslation } from "react-i18next";

import { ContributionBars } from "@/components/ContributionBars";
import { MoneyCell } from "@/components/MoneyCell";

import type { ServiceMixRow } from "@/api/dashboardTabEndpoints";

export interface ServiceMixPanelProps {
  services: readonly ServiceMixRow[];
  currency: string | null;
  locale?: string;
}

export function ServiceMixPanel(props: ServiceMixPanelProps) {
  const { t } = useTranslation();
  // ⚠ **A PERIOD WITH NO REVENUE DRAWS A SENTENCE AND NOT AN EMPTY BOX.**
  // Photographed at 1440 before this branch existed: September 2026 has no
  // revenue in this deployment, so `ContributionBars` rendered an empty `<ol>`
  // and the panel was a heading, a link and roughly two inches of nothing. A
  // reader cannot tell that apart from a panel that failed to load, which is
  // the state B14 rule 32 has a stated absence for. Six words, no reason
  // (rule 33 — RATIONALE is zero words on screen).
  if (props.services.length === 0) {
    return (
      <p className="m-0 text-sm text-neutral-600" data-panel-body="service_mix">
        {t("reports.dashboard.noRevenueThisPeriod")}
      </p>
    );
  }
  return (
    <div data-panel-body="service_mix">
      <ContributionBars
        label={t("reports.dashboard.panel.serviceMix")}
        rows={props.services.map((row, index) => ({
          id: row.service_code ?? `remainder-${index}`,
          label:
            row.service_code === null
              ? t("reports.dashboard.notAttributable")
              : t(`rating.service.${row.service_code}`, { defaultValue: row.service_code }),
          // See `AgeingBandsPanel` — a weight is a bar length, never a figure.
          weight: row.value === null ? 0 : Math.max(0, Number(row.value)),
          value:
            row.value === null ? (
              t("reports.dashboard.noFigure")
            ) : (
              <MoneyCell
                amount={row.value}
                currency={props.currency ?? "USD"}
                locale={props.locale}
              />
            ),
        }))}
      />
    </div>
  );
}

export default ServiceMixPanel;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P4.11 (05-prototype/09 Reports Build Brief.pdf p36 region ⑦ · p37 ⑦, read as IMAGES per B14 rule 42)
// screens: 3·1
// generated: 2026-09-27 by lane REP-P4-DASH
// checklist: A=n/a(no backend half) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reportsDashboard.dom.test.tsx reported `Cannot find module './dashboard/ServiceMixPanel'` before this file existed. G31: listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) a period with NO revenue draws a six-word sentence rather than an empty bar list — found by photographing the screen at 1440, which is the only thing that could have found it (hard-won law 6)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
