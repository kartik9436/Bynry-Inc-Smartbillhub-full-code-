// ── Trace ──────────────────────────────────────────────
// Stories:  US-WRK-055 (Finished jobs — the acceptance queue) · US-WRK-056
//           (Raised on site) · US-WRK-057 (Alerts) — EP-WRK-11, the office
//           side of the native field app (CR-187-BRC10, Walkthrough §4)
// Screen:   Work-034 · badge WRK-26 (minted in g29_allocated_badges.txt) —
//           ONE screen, four panes, four addresses:
//           /work/field · /work/field/raised · /work/field/alerts ·
//           /work/field/findings (route findings, BR-WRK-067, 2026-10-22) ·
//           /work/field/refused (refused field work, CR-194-BRC10, 2026-10-26)
// Rules:    B14 rule 2 (one page header; the Work strip is the header's) ·
//           rule 21 (Tailwind only — on route-b-migrated.txt from its first
//           commit) · rule 31 · rule 33 · rule 36 (compose the kit:
//           PageHeader, SubTabs, DataTable) · rule 43 (each pane is its own
//           component) · CLAUDE.md hard-won law 2 (the tab, the route and the
//           sub-tabs land in the same commit as the screen)
// Tests:    src/features/work/field/FieldDeskPage.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY ONE TAB WITH THREE PANES, AND NOT THREE TABS.** The Work strip
// already holds nine tabs; twelve does not fit a 1280 laptop without
// wrapping, and the strip is what a returning dispatcher reaches for first.
// All three lists are the same thing from the office's chair — what the
// HANDSETS sent back: jobs finished, orders raised on site, alerts answered
// or not — so they share one tab, *From the field*, and a sub-strip
// (`SubTabs`, the kit's second-level strip that Billing and Reports already
// use). Each pane has its OWN address, so a link to *Raised on site* survives
// a refresh and can be sent to someone.
//
// ⚠ **WHY *Raised on site* IS A PANE AND NOT A FILTER OF *Finished jobs*.**
// The rows are different things: a finished job carries an outcome, steps
// left and a cost; an order raised on site has not been worked yet and
// carries a position, a template version and a decision. One table cannot
// draw both honestly, and a filter that swapped every column would be a
// second screen pretending to be a control.
//
// ⚠ **NO DRAWING EXISTS FOR THIS SCREEN.** The field-app design names these
// surfaces in a table (Walkthrough §4) and draws none of them. The layout
// here is composed from the kit on `Work-009`'s pattern and is recorded as
// the stories' §1 text; the PO has not yet seen it (stated in the epic).
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { SubTabs } from "@/components/SubTabs";
import { useTenantPath } from "@/routing/tenantPath";

import {
  WORK_FIELD_ALERTS_ROUTE,
  WORK_FIELD_FINDINGS_ROUTE,
  WORK_FIELD_RAISED_ROUTE,
  WORK_FIELD_REFUSED_ROUTE,
  WORK_FIELD_ROUTE,
  useWorkTabs,
} from "../WorkShell";
import { FieldAlertsPane } from "./FieldAlertsPane";
import { FieldFindingsPane } from "./FieldFindingsPane";
import { FieldRaisedPane } from "./FieldRaisedPane";
import { FieldRefusedPane } from "./FieldRefusedPane";
import { FieldResultsPane } from "./FieldResultsPane";

export {
  WORK_FIELD_ALERTS_ROUTE,
  WORK_FIELD_FINDINGS_ROUTE,
  WORK_FIELD_RAISED_ROUTE,
  WORK_FIELD_REFUSED_ROUTE,
  WORK_FIELD_ROUTE,
} from "../WorkShell";

/** Minted, the next after `WRK-25` — r10 draws no office screen for a
 *  handset that did not exist when it was drawn. */
export const FIELD_DESK_SCREEN = "WRK-26";

export type FieldDeskView = "results" | "raised" | "alerts" | "findings" | "refused";

/** The panes in strip order, each with the address it lives at. */
export const FIELD_DESK_VIEWS: readonly { id: FieldDeskView; path: string; labelKey: string }[] = [
  { id: "results", path: WORK_FIELD_ROUTE, labelKey: "work.field.view.results" },
  { id: "raised", path: WORK_FIELD_RAISED_ROUTE, labelKey: "work.field.view.raised" },
  { id: "alerts", path: WORK_FIELD_ALERTS_ROUTE, labelKey: "work.field.view.alerts" },
  // BR-WRK-067 (PO 2026-10-22) — what readers found on a meter route.
  { id: "findings", path: WORK_FIELD_FINDINGS_ROUTE, labelKey: "work.field.view.findings" },
  // CR-194-BRC10 (PO 2026-10-26, *"store on both"*) — what the server refused.
  { id: "refused", path: WORK_FIELD_REFUSED_ROUTE, labelKey: "work.field.view.refused" },
];

export function FieldDeskPage(props: { view: FieldDeskView; client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const strip = useWorkTabs(t("work.field.sentence"));

  return (
    <div data-work-field="" data-screen={FIELD_DESK_SCREEN} data-field-view={props.view}>
      <PageHeader kicker={t("work.approvals.kicker")} title={t("work.field.title")} {...strip} />
      <SubTabs
        tabs={FIELD_DESK_VIEWS.map((view) => ({ id: view.id, label: t(view.labelKey) }))}
        activeId={props.view}
        label={t("work.field.views")}
        data-sub-tabs="field"
        onSelect={(id) => {
          const target = FIELD_DESK_VIEWS.find((view) => view.id === id);
          if (target !== undefined) navigate(tenantPath(target.path));
        }}
      />
      {props.view === "results" && <FieldResultsPane client={client} />}
      {props.view === "raised" && <FieldRaisedPane client={client} />}
      {props.view === "alerts" && <FieldAlertsPane client={client} />}
      {props.view === "findings" && <FieldFindingsPane client={client} />}
      {props.view === "refused" && <FieldRefusedPane client={client} />}
    </div>
  );
}

export default FieldDeskPage;
