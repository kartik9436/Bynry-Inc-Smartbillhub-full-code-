// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 4 `P4.11`. Screen `3·1` region ⑥, drawn on p036
//          and annotated on p037 ⑥, read as IMAGES per B14 rule 42.
// Rules:   B14 rule 43 (a COMPONENT) · rule 21 · CLAUDE.md hard rule 2
//          (money DISPLAY 2) · BR-REP-030 (five signed ageing bands)
// Tests:   07-frontend/src/features/reports/reportsDashboard.dom.test.tsx
// Impacts: ReportsDashboardPage.tsx
// ───────────────────────────────────────────────────────
//
// `Where the money sits` — THE FIVE SIGNED BANDS, ONE COLOUR FOR EVERY BAR.
//
// ⚠ **ONE COLOUR, AND p037 ⑥ ARGUES IT RATHER THAN ASSERTING IT.** Verbatim:
// *"⚠ **One colour for every bar, on purpose.** A first draft coloured them by
// size, so the `Current` band — the healthy one — came out warning-coloured
// because it was the biggest. **Colour that encodes magnitude reads as a
// judgment**, and on an ageing chart it is the exact opposite of the truth."*
//
// ⚠ **SO `AgeingCards` IS NOT REUSED HERE, AND THAT IS DELIBERATE RATHER THAN
// AN OVERSIGHT.** The kit has one, and its own header says *"THE TONE IS THE
// BAND'S, NOT THE FIGURE'S"* — it colours `90+` in the danger tier by position.
// That is right for the Finance ageing screen, where the bands are FILTERS a
// clerk presses. Here they are five rows of a monthly read and p037 rules them
// one colour, so the component that encodes a tone is the wrong component. The
// one that fits is `ContributionBars`, whose documented denominator is *the
// largest row and never the total* — which is what these bars need too.
//
// ⚠ **THE SHARES ARE NOT FORCED TO 100.** They arrive rounded from the server
// and are rendered as given. Redistributing a remainder would show a share no
// band actually has — and p037 ⑥ prints the drawn figures *58+25+9+4+4* to say
// so.
import { useTranslation } from "react-i18next";

import { ContributionBars } from "@/components/ContributionBars";
import { MoneyCell } from "@/components/MoneyCell";

import type { AgeingBandRow } from "@/api/dashboardTabEndpoints";

export interface AgeingBandsPanelProps {
  bands: readonly AgeingBandRow[];
  currency: string | null;
  locale?: string;
}

export function AgeingBandsPanel(props: AgeingBandsPanelProps) {
  const { t } = useTranslation();
  return (
    <div data-panel-body="where_the_money_sits">
      <ContributionBars
        label={t("reports.dashboard.panel.whereMoneySits")}
        rows={props.bands.map((band) => ({
          id: band.band,
          // The band's own name from the catalogue (`G15`), never the machine
          // token — `d31_60` on screen would be B14 rule 31's cousin.
          label: t(`reports.dashboard.band.${band.band}`, { defaultValue: band.band }),
          detail:
            band.share_pct === null
              ? undefined
              : t("reports.dashboard.share", { pct: band.share_pct }),
          // ⚠ **A WEIGHT IS A BAR LENGTH AND NEVER A DISPLAYED FIGURE.** Hard
          // rule 2 keeps money off floats where it is stored or shown; the bar
          // is neither, and the amount beside it is the exact decimal string.
          weight: band.value === null ? 0 : Math.max(0, Number(band.value)),
          value:
            band.value === null ? (
              t("reports.dashboard.noFigure")
            ) : (
              <MoneyCell
                amount={band.value}
                currency={props.currency ?? "USD"}
                locale={props.locale}
              />
            ),
        }))}
      />
    </div>
  );
}

export default AgeingBandsPanel;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P4.11 (05-prototype/09 Reports Build Brief.pdf p36 region ⑥ · p37 ⑥, read as IMAGES per B14 rule 42)
// screens: 3·1
// generated: 2026-09-27 by lane REP-P4-DASH
// checklist: A=n/a(no backend half) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reportsDashboard.dom.test.tsx reported `Cannot find module './dashboard/AgeingBandsPanel'` before this file existed. G31: listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) the kit's `AgeingCards` is NOT reused — it encodes a TONE per band by position, which p37 ⑥ rules out for this panel by name. Stated rather than left for the next reader to wonder at
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
