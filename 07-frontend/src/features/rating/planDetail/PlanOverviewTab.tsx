// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 7 — the plan details OVERVIEW (images 24,
//           25): four tiles that open their tab, *Details* (nine facts), the
//           versions table and *See every change in Audit*.
// Defects:  DEF-RAT-9331 (customer classes and notes by NAME, never the old
//           "cannot be named here yet" sentence) · DEF-RAT-9285 (a note's class
//           by name) · DEF-RAT-9334 (Revenue and Exceptions tiles, *How a plan
//           works*, *Sample bill*, *Not recorded on a plan yet* — REMOVED, the
//           README's "Removed from the details page")
// Rules:    ruling 13 (*"Tiles open their tab"*) · B14 rules 31, 33, 37 ·
//           BR-RAT-087 (money is the server's figure, shown with `$` to two places)
// ───────────────────────────────────────────────────────
import type { PlanDetailRead } from "@/api/planDetailEndpoints";
import { FactBlock } from "@/components/FactBlock";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { Panel } from "@/components/Panel";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";

import { SECTION_HEADING } from "../planForm/planFormShared";
import { moneyShown, noteText, serviceWord } from "../planSections/PlanSections";
import { RatingStatusPill } from "../ratingShared";
import { DASH, classesText, dayShown, shownVersions, versionChangeText, windowText } from "./planDetailModel";
import type { PlanDetailTab, PlanRegional, Translator } from "./planDetailModel";

const INTENDED_KEYS = ["cap_proof", "min_demand_25kw", "owner_occupied"] as const;

function versionTone(status: string) {
  if (status === "in_force") return "success" as const;
  if (status === "scheduled" || status === "draft") return "info" as const;
  return "muted" as const;
}

/** A tile's detail line that OPENS its tab (ruling 13). */
function TileLink(props: { to: string; label: string; tab: PlanDetailTab }) {
  return (
    <InlineLinkTo to={props.to} className="text-sm" data-plan-tile-link={props.tab}>
      {props.label} <span aria-hidden="true">›</span>
    </InlineLinkTo>
  );
}

export function planTiles(
  read: PlanDetailRead,
  tabTo: (tab: PlanDetailTab) => string,
  t: Translator,
): KpiTile[] {
  const sections = read.sections;
  return [
    {
      id: "units",
      label: t("rating.planDetail.kpi.units"),
      value: read.units ?? DASH,
      detail: <TileLink to={tabTo("units")} tab="units" label={t("rating.planDetail.kpi.onThisPlan")} />,
    },
    {
      id: "base",
      label: t("rating.planSections.terms.monthly"),
      value: moneyShown(sections.base_total.amount_display, sections.currency),
      detail: <TileLink to={tabTo("services")} tab="services" label={t("rating.planDetail.kpi.allServices")} />,
    },
    {
      id: "services",
      label: t("rating.planDetail.kpi.services"),
      value: sections.services.length,
      detail: (
        <TileLink
          to={tabTo("services")}
          tab="services"
          label={sections.services.length === 0 ? DASH : sections.services.map((line) => serviceWord(line.service, line.name, t)).join(" · ")}
        />
      ),
    },
    {
      id: "taxes",
      label: t("rating.planSections.taxes.title"),
      value: sections.combined_tax_rate_display ?? DASH,
      detail: <TileLink to={tabTo("charges")} tab="charges" label={t("rating.planDetail.kpi.combined")} />,
    },
  ];
}

export function PlanOverviewTab(props: {
  read: PlanDetailRead;
  tabTo: (tab: PlanDetailTab) => string;
  regional: PlanRegional;
  t: Translator;
}) {
  const { read, t, regional } = props;
  const sections = read.sections;
  const details = sections.details;
  const intended = INTENDED_KEYS.filter((key) => details.intended_for[key]).map((key) =>
    t(`rating.planForm.intended.${key}`),
  );
  const window = read.plan_version;
  const noEnd = t("rating.taxes.list.noEnd");
  const versions = shownVersions(read.versions);
  return (
    <div className="flex flex-col gap-5" data-plan-overview="">
      <KPIStrip kpis={planTiles(read, props.tabTo, t)} />

      <Panel as="section" aria-labelledby="plan-detail-details">
        <h2 id="plan-detail-details" className={SECTION_HEADING}>
          {t("rating.planForm.step.details")}
        </h2>
        <FactBlock
          name="plan-details"
          variant="strip"
          columns={3}
          facts={[
            { id: "name", label: t("rating.planSections.plan.name"), value: details.name || DASH },
            { id: "code", label: t("rating.planSections.plan.code"), value: details.code || DASH },
            { id: "classes", label: t("rating.planSections.plan.classes"), value: classesText(sections, t) },
            { id: "description", label: t("rating.planSections.plan.description"), value: details.description ?? DASH },
            {
              id: "intended",
              label: t("rating.planSections.plan.intended"),
              value: intended.length === 0 ? DASH : intended.join(", "),
            },
            {
              id: "notes",
              label: t("rating.planSections.plan.notes"),
              value: details.notes.length === 0 ? DASH : details.notes.map((note) => noteText(note, t)).join("; "),
            },
            { id: "starts", label: t("rating.planDetail.starts"), value: dayShown(window?.effective_from, regional) },
            {
              id: "ends",
              label: t("rating.planDetail.ends"),
              value: window === null ? DASH : window.effective_to === null ? noEnd : dayShown(window.effective_to, regional),
            },
            {
              id: "minimum",
              label: t("rating.planSections.terms.minimum"),
              value:
                details.minimum_bill_display === null
                  ? t("rating.planSections.none")
                  : moneyShown(details.minimum_bill_display, sections.currency),
            },
          ]}
        />
        {versions.length > 0 && (
          <div className="mt-5 border border-divider" data-plan-versions="">
            <PlainTable>
              <thead>
                <tr>
                  <th scope="col">{t("rating.planDetail.versions.col.version")}</th>
                  <th scope="col">{t("rating.taxDetail.versions.dates")}</th>
                  <th scope="col">{t("rating.taxDetail.versions.status")}</th>
                  <th scope="col">{t("rating.history.col.change")}</th>
                </tr>
              </thead>
              <tbody>
                {versions.map((row) => (
                  <tr key={`${row.version}-${row.status}-${row.effective_from ?? ""}`} data-version-status={row.status}>
                    <td>{t("rating.discountDetail.versions.n", { n: row.version })}</td>
                    <td className="tabular-nums">{windowText(row.effective_from, row.effective_to, regional, noEnd)}</td>
                    <td>
                      <RatingStatusPill
                        tone={versionTone(row.status)}
                        stem="rating.planDetail.versionStatus"
                        value={row.status}
                      />
                    </td>
                    {/* `DEF-RAT-10031` — what this version changed, or the mark
                        for a copy written before the fix. */}
                    <td
                      className={row.terms_recorded === false ? "text-neutral-700" : "tabular-nums"}
                      data-version-change={row.terms_recorded === false ? "not-recorded" : "words"}
                    >
                      {versionChangeText(row, t)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          </div>
        )}
        <div className="mt-4">
          <InlineLinkTo className="font-semibold" to={props.tabTo("audit")} data-plan-see-audit="">
            {t("rating.taxDetail.seeAudit")}
          </InlineLinkTo>
        </div>
      </Panel>
    </div>
  );
}
