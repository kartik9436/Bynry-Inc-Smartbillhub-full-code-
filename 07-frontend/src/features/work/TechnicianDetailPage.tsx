// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-021 (the technician detail and the three-step skills
//           wizard) · US-WRK-020 (the profile beside the login).
//           Screens: Work-024 (`wireframes/Work-024.png`) + the skills wizard,
//           an UNDRAWN SUB-SCREEN that takes no id (`01-overview.md` §6)
// Rules:    BR-WRK-028 · BR-WRK-030 · B14 rule 2 (one page header) · rule 3
//           (the wizard's numbered rail) · rule 5 (two button sizes) · rule 20
//           (one table type) · rule 21 (Tailwind; on route-b-migrated.txt) ·
//           rule 31 (no database id is a visible value) · rule 32 (one
//           sentence per section) · rule 36 (compose the kit) ·
//           BR-SHL-025 (disabled WITH its reason)
// Tests:    src/features/work/TechnicianDetailPage.test.tsx ·
//           src/features/work/crewsLane.dom.test.tsx
// Impacts:  src/features/work/CrewsPage.tsx (links here) · src/App.tsx ·
//           src/routing/screenIds.ts (WRK-08)
// ───────────────────────────────────────────────────────
//
// ⚠⚠ **THE *NOT HELD* ROWS ARE THE POINT OF THIS SCREEN, NOT A GAP IN IT.**
//
// `WS-24` draws three skill rows for R. Patel and one of them is *Water II ·
// Not held · Main repair · tap and service line*. The card's own reason is the
// deliverable: *"The Not held row matters as much as the two held ones: it
// tells a supervisor exactly which jobs a training course would unlock."*
//
// So the panel lists the tenant's WHOLE skill catalogue and marks which are
// held — it is not a list of this person's skills with the others missing. The
// server derives it (`apps/work/workforce.technician_detail`) rather than
// storing a `not_held` row, because a stored absence goes stale the moment a
// skill is added in Settings and there would then be two ways to answer *does
// she hold Water II*.
//
// ⚠ **CR-168-BRC10 ROUND 4 (lane CREWS) — FOUR TABS, FROM THE IMAGES
// `05-prototype/work-backoffice-2026-10-04/images/31–34`.** Rulings 27 and 28
// drew the two this file used to leave out: *Jobs* (P3.45 — the assignee
// column wave G added is how the server finds them) and *Performance*, plus
// *This month* on the Overview (P3.46 — SRV-3's `this_month`, the same tally
// the Performance screen uses), and the Certifications tab became a TABLE with
// add and renew (P3.48). Audit is not drawn on images 31–34 and is not here.
//
// ⚠ **A RUN-OUT CERTIFICATION WARNS AND NEVER REFUSES** — PO answer 2 of
// 2026-10-04 superseded `BR-WRK-030` for every tenant.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { detailTabFrom, Dash, GuardedButton, useRegional } from "@/features/metering/meteringShared";
import type { DetailTab } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { PrintDayDialog } from "./PrintDayDialog";
import { TechnicianStatusPill } from "./TechnicianStatusPill";
import { TechnicianDevicesPanel } from "./field/TechnicianDevicesPanel";
import { DailyLimitPanel } from "./TechnicianDailyLimit";
import { SkillsWizard } from "./SkillsWizard";
import { TechnicianCertificationsTab } from "./TechnicianCertificationsTab";
import { TechnicianJobsTab } from "./TechnicianJobsTab";
import { TechnicianPerformanceTab, ThisMonthPanel } from "./TechnicianPerformanceTab";
import { TechnicianTimesheetsTab } from "./TechnicianTimesheetsTab";
import { ExceptionsPanel, WorkingDaysPanel } from "./TechnicianWorkingDays";
import { listTechnicianJobs } from "./crewsEndpoints";
import { WORK_CREWS_ROUTE } from "./CrewsPage";
import { PROFICIENCY_FALLBACK } from "./workforceLabels";
import { getTechnician, setTechnicianAvailability } from "./workEndpoints";
import type { TechnicianDetail } from "./workEndpoints";

/** r10's own badge — `01-overview.md` §6, Work-024 ↔ WRK-08. Nothing minted. */
export const WORK_TECHNICIAN_SCREEN = "WRK-08";

/** `…/work/crews/:slug` — the technician detail lives UNDER the crews address,
 *  which is the address `WS-24` itself draws (`/brazosbend/work/crews/r-patel`). */
export const WORK_TECHNICIAN_ROUTE = "/work/crews/:slug";

const TAB_PARAM = "tab";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** Images 31–34's tabs, in the drawn order. */
export function technicianTabs(t: Translate): DetailTab[] {
  return [
    { id: "overview", label: t("work.technician.tab.overview") },
    { id: "jobs", label: t("work.technician.tab.jobs") },
    { id: "certifications", label: t("work.technician.tab.certifications") },
    { id: "performance", label: t("work.technician.tab.performance") },
    // CR-193-BRC10 (MQ-040 step 1) — the days the phone submitted.
    { id: "timesheets", label: t("work.technician.tab.timesheets") },
  ];
}

/** Image 31's meta line: *Meter I · Reads · Water I · shift 07:00–15:30 ·
 *  Field crew A · 1 open job*. `openJobs` is the server's count of the
 *  person's open jobs (`…/jobs?f.state=open`), absent until it arrives. */
export function metaLine(detail: TechnicianDetail, t: Translate, openJobs?: number): string {
  const held = detail.skills.filter((skill) => skill.proficiency !== "not_held");
  const parts = held.map((skill) => skill.name);
  if (detail.shift !== null) parts.push(t("work.technician.meta.shift", { shift: detail.shift }));
  if (detail.crew !== null) parts.push(detail.crew.name);
  if (openJobs !== undefined) parts.push(t("work.technician.meta.openJobs", { count: openJobs }));
  return parts.join(" · ");
}


export interface TechnicianDetailPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function TechnicianDetailPage(props: TechnicianDetailPageProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const translate: Translate = (key, params) => t(key, params);
  const params = useParams();
  const slug = params.slug ?? "";
  const [searchParams, setSearchParams] = useSearchParams();
  const [wizardOpen, setWizardOpen] = useState(false);
  // CR-168-BRC10 P6.3 (lane SRV-5) — ruling 3's *"a day's pack prints"*.
  const [printing, setPrinting] = useState(false);
  const regional = useRegional({});

  const tabs = useMemo(() => technicianTabs(translate), [t]); // eslint-disable-line react-hooks/exhaustive-deps
  const active = detailTabFrom(searchParams.get(TAB_PARAM), tabs);

  const detailQuery = useQuery({
    queryKey: queryKeys.workTechnician(slug),
    queryFn: () => getTechnician(slug, client),
    enabled: slug !== "",
  });
  const detail = detailQuery.data;

  const openJobsQuery = useQuery({
    queryKey: ["work", "technician", slug, "jobs", "open", "count"],
    queryFn: () => listTechnicianJobs(slug, { state: "open", per: 10 }, client),
    enabled: slug !== "",
  });

  const availability = useMutation({
    mutationFn: (next: "on_shift" | "unavailable") =>
      setTechnicianAvailability(slug, { status: next }, client),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["work"] }),
  });

  return (
    <div data-work-technician="" data-screen={WORK_TECHNICIAN_SCREEN}>
      <PageHeader
        // B14 rule 2 — ONE page header. A record DETAIL carries no module tab
        // strip: the strip is a strip of LISTS and a detail sits under its own
        // back link (`DEF-WRK-3724`, the shape every other detail takes).
        backTo={{
          to: tenantPath(WORK_CREWS_ROUTE),
          label: t("work.technician.back", { defaultValue: "Crews" }),
        }}
        kicker={
          detail === undefined
            ? t("work.technician.kicker", { defaultValue: "Technician" })
            : `${t("work.technician.kicker", { defaultValue: "Technician" })} · ${
                detail.role_label ?? ""
              }`
        }
        title={detail?.name ?? ""}
        rollup={
          detail === undefined ? undefined : (
            <span className="inline-flex items-center gap-2">
              <span>{metaLine(detail, translate, openJobsQuery.data?.count)}</span>
              <TechnicianStatusPill
                status={detail.status}
                since={detail.status_since}
                shiftEnded={detail.shift_ended}
              />
            </span>
          )
        }
        secondaryActions={
          <Button
            variant="secondary"
            data-action="print-day"
            disabled={detail === undefined || slug === ""}
            onClick={() => setPrinting(true)}
          >
            {t("work.technician.printDay")}
          </Button>
        }
        primaryAction={
          <>
            {/* `WS-24` draws *Assign skills* as the primary outline. It opens
                the three-step wizard as a SUB-SCREEN of this one, which is
                what `01-overview.md` §6 calls it — so it takes no screen id. */}
            <Button
              variant="primary"
              data-assign-skills=""
              disabled={detail === undefined}
              onClick={() => setWizardOpen(true)}
            >
              {t("work.technician.assignSkills", { defaultValue: "Assign skills" })}
            </Button>
            {/* ⚠ NOT A DELETE. `US-WRK-020` TC-5: a technician with jobs
                against their name is never removed — a deleted row leaves a
                job assigned to nobody with no way to see it happened. This is
                what a supervisor gets instead, and pressing it again on an
                unavailable person puts them back. */}
            <GuardedButton
              label={
                detail?.status === "unavailable"
                  ? t("work.technician.setAvailable", { defaultValue: "Set available" })
                  : t("work.technician.setUnavailable", { defaultValue: "Set unavailable" })
              }
              reason={
                detail === undefined
                  ? t("work.technician.loading", { defaultValue: "Still loading." })
                  : null
              }
              working={availability.isPending}
              onClick={() =>
                availability.mutate(
                  detail?.status === "unavailable" ? "on_shift" : "unavailable",
                )
              }
            />
          </>
        }
        tabs={tabs}
        activeTabId={active}
        tabsLabel={t("work.technician.tabs", { defaultValue: "Technician sections" })}
        onTabSelect={(tab) => {
          const next = new URLSearchParams(searchParams);
          next.set(TAB_PARAM, tab.id);
          setSearchParams(next, { replace: true });
        }}
      />

      {active === "overview" && <SkillsPanel detail={detail} t={translate} />}
      {active === "overview" && <CertificationsPanel detail={detail} t={translate} />}
      {active === "overview" && detail !== undefined && <ThisMonthPanel detail={detail} />}
      {/* CR-168-BRC10 §30 — the daily job limit, edited here (PO answer (2)). */}
      {active === "overview" && detail !== undefined && (
        <DailyLimitPanel
          client={client}
          detail={detail}
          onSaved={() => void queryClient.invalidateQueries({ queryKey: ["work"] })}
        />
      )}
      {/* CR-193-BRC10 (MQ-040 step 1) — the weekdays this person works, and
          the one-day exceptions to them. The phone's week is built from these. */}
      {active === "overview" && slug !== "" && <WorkingDaysPanel slug={slug} client={client} />}
      {active === "overview" && slug !== "" && (
        <ExceptionsPanel slug={slug} client={client} timeZone={regional.timeZone} dateFormat={regional.dateFormat} />
      )}
      {/* CR-187-BRC10 (US-WRK-058) — every handset this person signs in on,
          and the office's sign-out (R115). On the Overview, as its own group. */}
      {active === "overview" && slug !== "" && (
        <TechnicianDevicesPanel
          slug={slug}
          client={client}
          timeZone={regional.timeZone}
          dateFormat={regional.dateFormat}
        />
      )}
      {active === "jobs" && slug !== "" && <TechnicianJobsTab client={client} slug={slug} />}
      {active === "certifications" && detail !== undefined && (
        <TechnicianCertificationsTab client={client} detail={detail} />
      )}
      {active === "performance" && detail !== undefined && (
        <TechnicianPerformanceTab client={client} detail={detail} />
      )}
      {active === "timesheets" && slug !== "" && (
        <TechnicianTimesheetsTab
          slug={slug}
          client={client}
          timeZone={regional.timeZone}
          dateFormat={regional.dateFormat}
        />
      )}

      {detail !== undefined && detail.status === "unavailable" && (
        <Note data-technician-unavailable="">
          {detail.unavailable_reason === null
            ? t("work.technician.unavailable", { defaultValue: "Not available for work." })
            : t("work.technician.unavailableWhy", {
                reason: detail.unavailable_reason,
                defaultValue: "Not available for work — {{reason}}.",
              })}
        </Note>
      )}

      {detail !== undefined && (
        <Note data-technician-note="">
          {t("work.technician.note", {
            shift: detail.shift ?? "",
            van: detail.van ?? "",
            defaultValue: "Shift {{shift}}. Van {{van}}.",
          })}
        </Note>
      )}

      {printing && detail !== undefined && (
        <PrintDayDialog
          name={detail.name}
          holder={{ technician: slug }}
          tenantPath={tenantPath}
          timeZone={regional.timeZone}
          dateFormat={regional.dateFormat}
          onClose={() => setPrinting(false)}
        />
      )}
      {wizardOpen && detail !== undefined && (
        <SkillsWizard
          client={client}
          detail={detail}
          onClose={() => setWizardOpen(false)}
          onSaved={() => {
            setWizardOpen(false);
            void queryClient.invalidateQueries({ queryKey: ["work"] });
          }}
        />
      )}
    </div>
  );
}

/** `WS-24`'s SKILLS & PROFICIENCY panel — the held rows AND the not-held ones. */
export function SkillsPanel(props: { detail: TechnicianDetail | undefined; t: Translate }) {
  const { detail, t } = props;
  if (detail === undefined) return null;
  return (
    <Panel as="section" title={t("work.technician.skills.title", { defaultValue: "Skills" })}>
      {/* B14 rule 20 — the ONE table type. `PlainTable` is the kit's
          non-paged form of it, which is what a panel of five rows needs. */}
      <PlainTable data-technician-skills="">
        <thead>
          <tr>
            <th>{t("work.technician.skills.col.skill", { defaultValue: "Skill" })}</th>
            <th>
              {t("work.technician.skills.col.proficiency", { defaultValue: "Proficiency" })}
            </th>
            <th>
              {t("work.technician.skills.col.eligible", {
                defaultValue: "Makes them eligible for",
              })}
            </th>
          </tr>
        </thead>
        <tbody>
          {detail.skills.map((skill) => (
            <tr key={skill.skill_id} data-skill-row={skill.proficiency}>
              <td>{skill.name}</td>
              <td>
                {t(`work.technician.proficiency.${skill.proficiency}`, {
                  defaultValue: PROFICIENCY_FALLBACK[skill.proficiency],
                })}
              </td>
              <td>
                {(skill.eligible_for ?? []).length === 0 ? (
                  <Dash />
                ) : (
                  (skill.eligible_for ?? []).join(" · ")
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </Panel>
  );
}

/** `WS-24`'s CERTIFICATIONS panel — a chip row of name + expiry. */
export function CertificationsPanel(props: {
  detail: TechnicianDetail | undefined;
  t: Translate;
}) {
  const { detail, t } = props;
  if (detail === undefined) return null;
  return (
    <Panel
      as="section"
      title={t("work.technician.certifications.title", { defaultValue: "Certifications" })}
    >
      {detail.certifications.length === 0 ? (
        // B14 rule 17 — an empty state says what is missing, in one sentence.
        <Note>
          {t("work.technician.certifications.none", {
            defaultValue: "None recorded.",
          })}
        </Note>
      ) : (
        <p className="m-0 flex flex-wrap items-center gap-2" data-technician-certs="">
          {detail.certifications.map((cert) => (
            <span key={cert.certification_type_id} className="inline-flex items-center gap-1">
              <span>{cert.name ?? ""}</span>
              {cert.expires_on !== null && (
                <StatusPill tone="neutral">
                  {t("work.technician.certifications.expires", {
                    date: cert.expires_on,
                    defaultValue: "exp {{date}}",
                  })}
                </StatusPill>
              )}
            </span>
          ))}
        </p>
      )}
    </Panel>
  );
}

export default TechnicianDetailPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-021@2b08ba9f (EP-WRK-04) · 08-screen-layouts.md Work-024 · 09-component-inventory.md W5 · wireframes/Work-024.png
// generated: 2026-09-05 by the CR-070 wave F build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · eslint · vitest · routeBUtilities.test.ts · G31 (rule 21)
// exceptions: the *THIS MONTH* panel is NOT drawn — `work_orders` has no assignee column until wave G, so none of its three figures can be computed (law 2; stamped in 08-screen-layouts.md) · the Jobs and Audit tabs are NOT drawn, for the same reason WORK_TABS holds only the tabs whose screen exists (each later wave appends its own) · the skills wizard is a SUB-SCREEN and takes no screen id (01-overview.md §6)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
