// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 `P4.11` / `P4.13`.
//          Screen `3·1`, drawn on p036–p038, read as IMAGES per B14 rule 42.
// Rules:   B14 rule 43 (a piece of UI is built as a COMPONENT — and p038
//          names this screen as the one to watch: *"the shell dashboard's four
//          panels are inline in a 4,000-line page and cannot be reused. Every
//          panel here is a component from the first commit"*) · rule 44 (our
//          tokens and kit win over the drawing) · rule 33 (a LABEL ≤ 3 words;
//          RATIONALE is ZERO words on screen) · rule 21 (Tailwind only) ·
//          CLAUDE.md hard-won law 2's mirror (a live screen behind a dead
//          control)
// Tests:   07-frontend/src/features/reports/reportsDashboard.dom.test.tsx
// Impacts: the five panel components, which all compose this
// ───────────────────────────────────────────────────────
//
// THE FRAME EVERY PANEL ON `3·1` WEARS, AND THE DOOR IT DOES OR DOES NOT CARRY.
//
// ⚠ **THIS EXISTS BECAUSE p038 SAYS SO BY NAME.** RULES, verbatim: *"Rule 43 is
// the one to watch: the shell dashboard's four panels are inline in a 4,186-line
// page and cannot be reused. **Every panel here is a component from the first
// commit**, or this screen becomes the second place that mistake lives."*
//
// ⚠ **A PANEL WHOSE REPORT CANNOT BE PRODUCED DRAWS NO LINK AT ALL.** The
// server decides that — `report_params` is absent from the payload rather than
// present-and-ignored — so this component CANNOT render a door by forgetting to
// check a flag. That is hard-won law 2's mirror answered at the source: on
// 2026-09-05 the customer portal's front page had two working doors out of
// eight, every one of them a control that had gone on pointing at a screen
// after the reason for the hold changed.
//
// ⚠ **THE HEADING IS THREE WORDS AND THE REPORT'S NAME FOLLOWS IT** (B14
// rule 33 — a LABEL is ≤ 3 words and carries no sentence). *Where the money
// sits · AR Ageing →* is the drawing's own arrangement: the panel's question,
// then the report that answers it.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { Panel } from "@/components/Panel";

export interface DashboardPanelProps {
  /** The panel's own question — *Where the money sits*. Already translated. */
  title: string;
  /** The report behind it — *AR Ageing*. Already translated or resolved. */
  reportName: string;
  /** Where the door goes, INCLUDING the period (`P4.13`), or `null` for none. */
  to: string | null;
  /** The sentence for an absence, or `undefined`. Six words (B14 rule 33). */
  absence?: string;
  children?: ReactNode;
}

/**
 * One panel of `3·1`.
 *
 * ⚠ **`to` IS A WHOLE ADDRESS AND NEVER A KEY THIS COMPONENT BUILDS A PATH
 * FROM.** A component composing `/reports/${key}` cannot know the tenant, and a
 * tenant-less address is the protocol-relative `//reports/…` string CLAUDE.md
 * records under hard-won law 2 — a broken link that reads as a perfectly good
 * one to `toContain`. The page builds the address; this draws it.
 */
export function DashboardPanel(props: DashboardPanelProps) {
  const { t } = useTranslation();
  return (
    <Panel>
      <div className="mb-4 flex flex-wrap items-baseline gap-2">
        <h3 className="m-0 text-md font-semibold text-text">{props.title}</h3>
        {props.to === null ? (
          <span className="text-sm text-neutral-600" data-panel-report="">
            {props.reportName}
          </span>
        ) : (
          <Link
            to={props.to}
            className="text-sm text-accent no-underline hover:underline"
            data-panel-report=""
            data-panel-link=""
          >
            {t("reports.dashboard.openReport", { report: props.reportName })}
          </Link>
        )}
      </div>
      {props.absence !== undefined && (
        <p className="m-0 mb-3 text-sm text-neutral-600" data-panel-absence="">
          {props.absence}
        </p>
      )}
      {props.children}
    </Panel>
  );
}

export default DashboardPanel;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P4.11 · P4.13 (05-prototype/09 Reports Build Brief.pdf pp36-38, read as IMAGES per B14 rule 42)
// screens: 3·1
// generated: 2026-09-27 by lane REP-P4-DASH
// checklist: A=n/a(no backend half) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reportsDashboard.dom.test.tsx reported `Cannot find module './dashboard/DashboardPanel'` before this file existed. G31: this file is listed in styles/route-b-migrated.txt in the same commit.
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
