// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane CREWS — P3.49 (Crews as THREE lists),
//           P3.43 (Add crew member on the Crews page), P3.27 (Add a crew), the
//           Add a contractor form. Built from the IMAGES
//           `05-prototype/work-backoffice-2026-10-04/images/25` (Technicians),
//           `27` (Crews), `28` (Contractors), `26`, `29`, `30` (the add forms).
// Rulings:  30 (*"one table is confusing"* — three lists; supersedes the last
//           sentence of `BR-WRK-028`) · 26 (the page leads to adding a crew
//           member) · 31 (Add a crew and Add a contractor are drawn) · PO answer
//           2 of 2026-10-04 (a lapsed certification WARNS, for every tenant —
//           `BR-WRK-030` superseded; `DEF-WRK-9634`) · 36 (a contractor's
//           phone-only logins wait for the field-app document — NOT built, and
//           no control pretends)
// Rules:    B14 rule 2 (one header, actions top right) · 12/16 (the kit's table
//           toolbar and pager) · 17 (an empty state says what is missing) · 19
//           (each list's own search prompt) · 20 (one table type) · 21
//           (Tailwind; on route-b-migrated.txt) · 31 (no database id visible) ·
//           33 (copy caps) · 37 (a drawn figure is an illustration) · 42 (built
//           from the image) · 43 · 44 (our kit's spacing and type win)
// Tests:    src/features/work/crewsLane.dom.test.tsx ·
//           src/features/work/CrewsPage.test.tsx
// Impacts:  src/features/work/WorkShell.tsx (the Crews tab) ·
//           src/routing/screenIds.ts (WRK-07) · src/App.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **WHICH LIST IS SHOWN LIVES IN THE ADDRESS (`?view=crews`)**, so a refresh,
// a bookmark and the back button all land on the list the person was reading.
// Technicians is the default and carries no parameter.
//
// ⚠ **EACH LIST IS ITS OWN SERVER PAGE.** `GET /work/crews?view=…` cuts the
// list in SQL and answers the three tab badges as `COUNT(*)` over the utility
// (lane SRV-3, P3.4) — the badges never count a page.
//
// ⚠ **THE HEADER'S BUTTONS FOLLOW THE LIST** — image 25 draws *+ Add crew
// member* alone, image 27 draws it beside *+ Add a crew*, image 28 draws *+ Add
// a contractor* alone. A contractor's people are not added here: ruling 36 gives
// them phone-only logins and that waits for the field-app document.
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { PrinterIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { SegmentedControl } from "@/components/SegmentedControl";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";
import { useRegional } from "@/features/metering/meteringShared";
import { seedQueryFromUrl } from "@/routing/seedQueryFromUrl";
import { useTenantPath } from "@/routing/tenantPath";

import { AddContractorModal } from "./AddContractorModal";
import { AddCrewMemberModal } from "./AddCrewMemberModal";
import { AddCrewModal } from "./AddCrewModal";
import { PrintDayDialog } from "./PrintDayDialog";
import { TechnicianStatusPill } from "./TechnicianStatusPill";
import { useWorkTabs, WORK_CREWS_ROUTE } from "./WorkShell";
import { getCertificationWatch } from "./workEndpoints";
import type { CertificationWatch, HeldCertification, HeldSkill } from "./workEndpoints";
import { listCrewsView } from "./crewsEndpoints";
import type { CrewListRow, CrewsView, CrewsViewCounts, TechnicianListRow } from "./crewsEndpoints";

/** r10's own badge for the crews screen — `01-overview.md` §6, Work-023 ↔ WRK-07. */
export const WORK_CREWS_SCREEN = "WRK-07";

/** `…/work/crews/r-patel` — built from the SLUG, never the id (B14 rule 31). */
export { WORK_CREWS_ROUTE } from "./WorkShell";
export function technicianDetailPath(slug: string): string {
  return `${WORK_CREWS_ROUTE}/${slug}`;
}

export const CREWS_VIEWS: readonly CrewsView[] = ["technicians", "crews", "contractors"];
const VIEW_PARAM = "view";

/** Which list the address names; anything else is the default list. */
export function crewsViewFrom(raw: string | null): CrewsView {
  return CREWS_VIEWS.includes(raw as CrewsView) ? (raw as CrewsView) : "technicians";
}

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** A skill list as the drawing writes it: *Water I · Meter I · Reads*. */
export function skillsText(skills: readonly HeldSkill[]): string {
  return skills.map((skill) => skill.name).join(" · ");
}

function certificationsText(rows: readonly HeldCertification[]): string {
  return rows.map((row) => row.name).filter(Boolean).join(" · ");
}

/** Does any certification of this person run out within 30 days — or has it
 *  already? Measured against the SERVER's `today`, never the browser's clock,
 *  so this pill and the watch below cannot disagree on one screen. */
export function expiringSoon(
  row: { certifications: readonly HeldCertification[] },
  today: string,
): boolean {
  const now = Date.parse(`${today}T00:00:00Z`);
  if (Number.isNaN(now)) return false;
  return row.certifications.some((cert) => {
    if (cert.expires_on === null) return false;
    const expiry = Date.parse(`${cert.expires_on}T00:00:00Z`);
    if (Number.isNaN(expiry)) return false;
    return expiry - now <= 30 * 24 * 60 * 60 * 1000;
  });
}

/**
 * `DEF-WRK-9639` — which pill, if any: `expired` once a certificate's date has
 * PASSED, `expiring` within 30 days, else none. The watch below the list
 * already told the two apart; the row's pill read *cert expiring* over a
 * certificate that had lapsed twelve days earlier. Same server `today`.
 */
export function certificationState(
  row: { certifications: readonly HeldCertification[] },
  today: string,
): "expired" | "expiring" | null {
  const now = Date.parse(`${today}T00:00:00Z`);
  if (Number.isNaN(now)) return null;
  let soon = false;
  for (const cert of row.certifications) {
    if (cert.expires_on === null) continue;
    const expiry = Date.parse(`${cert.expires_on}T00:00:00Z`);
    if (Number.isNaN(expiry)) continue;
    if (expiry < now) return "expired";
    if (expiry - now <= 30 * 24 * 60 * 60 * 1000) soon = true;
  }
  return soon ? "expiring" : null;
}

/** The pill each state draws — two words, two tiers. */
export const CERT_PILL = {
  expired: { tone: "danger", key: "work.crews.certExpired" },
  expiring: { tone: "warning", key: "work.crews.certExpiring" },
} as const;

/** Image 25's columns, in the drawing's order. */
export function technicianListConfig(
  t: Translate,
  cells: { technician: (row: TechnicianListRow) => React.ReactNode },
): TableConfig<TechnicianListRow> {
  return {
    screenId: WORK_CREWS_SCREEN,
    getRowId: (row) => row.id,
    searchFields: ["name", "skills", "crew"],
    searchPlaceholder: "work.crews.search",
    defaultSort: { sort: "name", dir: "asc" },
    columns: [
      {
        key: "name",
        label: t("work.crews.col.technician"),
        identity: true,
        sortable: true,
        cell: cells.technician,
      },
      {
        key: "crew",
        label: t("work.crews.col.crew"),
        sortable: true,
        cell: (row) => (row.crew === null ? <Dash /> : <span>{row.crew.name}</span>),
      },
      {
        key: "role_label",
        label: t("work.crews.col.jobTitle"),
        cell: (row) => (row.role_label === null ? <Dash /> : <span>{row.role_label}</span>),
      },
      {
        key: "skills",
        label: t("work.crews.col.skills"),
        cell: (row) => (row.skills.length === 0 ? <Dash /> : <span>{skillsText(row.skills)}</span>),
      },
      {
        key: "certifications",
        label: t("work.crews.col.certifications"),
        cell: (row) =>
          row.certifications.length === 0 ? (
            <Dash />
          ) : (
            <span>{certificationsText(row.certifications)}</span>
          ),
      },
      {
        key: "shift",
        label: t("work.crews.col.shift"),
        cell: (row) =>
          row.shift === null ? <Dash /> : <span className="tabular-nums">{row.shift}</span>,
      },
      {
        key: "status",
        label: t("work.crews.col.status"),
        // FB-033 — *Off duty · since 15:30*, *Shift ended · 17:02*.
        cell: (row) => (
          <TechnicianStatusPill status={row.status} since={row.status_since} shiftEnded={row.shift_ended} />
        ),
      },
    ],
  };
}

function activePill(row: CrewListRow, t: Translate) {
  return (
    <StatusPill tone={row.active ? "success" : "muted"}>
      {row.active ? t("work.crews.status.active") : t("work.crews.status.inactive")}
    </StatusPill>
  );
}

/** Image 27's columns, in the drawing's order — plus, when the page passes
 *  them, the row's actions (`DEF-WRK-9672`: *Print day…*, the crew's half of
 *  ruling 3's day pack, which the technician page has carried since SRV-5). */
export function crewListConfig(
  t: Translate,
  actions?: (row: CrewListRow) => ReactNode,
): TableConfig<CrewListRow> {
  return {
    screenId: WORK_CREWS_SCREEN,
    getRowId: (row) => row.id,
    searchFields: ["name", "members", "skills"],
    searchPlaceholder: "work.crews.searchCrews",
    defaultSort: { sort: "name", dir: "asc" },
    columns: [
      {
        key: "name",
        label: t("work.crews.col.crew"),
        identity: true,
        sortable: true,
        cell: (row) => <strong>{row.name}</strong>,
      },
      {
        key: "members",
        label: t("work.crews.col.members"),
        sortable: true,
        // Image 27: *D. Ortiz · R. Patel · 2 people* — the names (lane SRV-4's
        // `member_names`), then the COUNTED members, muted. The count stays the
        // server's `COUNT(*)` and is never the length of the names.
        cell: (row) => (
          <span data-crew-member-names={row.member_names.length}>
            {row.member_names.length > 0 && <span>{row.member_names.join(" · ")}</span>}
            <span className="italic tabular-nums text-neutral-600" data-crew-members={row.members}>
              {row.member_names.length > 0 ? " · " : ""}
              {t("work.crews.members.count", { count: row.members })}
            </span>
          </span>
        ),
      },
      {
        key: "role_label",
        label: t("work.crews.col.does"),
        cell: (row) => (row.role_label === null ? <Dash /> : <span>{row.role_label}</span>),
      },
      {
        key: "skills",
        label: t("work.crews.col.skills"),
        cell: (row) => (row.skills.length === 0 ? <Dash /> : <span>{skillsText(row.skills)}</span>),
      },
      {
        key: "shift",
        label: t("work.crews.col.shift"),
        cell: (row) =>
          row.shift === null ? <Dash /> : <span className="tabular-nums">{row.shift}</span>,
      },
      { key: "status", label: t("work.crews.col.status"), cell: (row) => activePill(row, t) },
      ...(actions === undefined
        ? []
        : [{ key: "actions", label: t("work.crews.col.actions"), cell: actions }]),
    ],
  };
}

/** Image 28's columns, in the drawing's order. */
export function contractorListConfig(t: Translate): TableConfig<CrewListRow> {
  return {
    screenId: WORK_CREWS_SCREEN,
    getRowId: (row) => row.id,
    searchFields: ["name", "skills"],
    searchPlaceholder: "work.crews.searchContractors",
    defaultSort: { sort: "name", dir: "asc" },
    columns: [
      {
        key: "name",
        label: t("work.crews.col.contractor"),
        identity: true,
        sortable: true,
        cell: (row) => <strong>{row.name}</strong>,
      },
      {
        key: "skills",
        label: t("work.crews.col.skills"),
        cell: (row) => (row.skills.length === 0 ? <Dash /> : <span>{skillsText(row.skills)}</span>),
      },
      {
        key: "shift",
        label: t("work.crews.col.hours"),
        // No set hours is BY ARRANGEMENT — a fact about the arrangement, so it
        // is words and not a dash.
        cell: (row) =>
          row.shift === null ? (
            <span>{t("work.crews.hours.byArrangement")}</span>
          ) : (
            <span className="tabular-nums">{row.shift}</span>
          ),
      },
      { key: "status", label: t("work.crews.col.status"), cell: (row) => activePill(row, t) },
    ],
  };
}

export interface CrewsPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

type Adding = "member" | "crew" | "contractor" | null;

/** Images 25, 27, 28: the head, the three lists, and the watch. */
export function CrewsPage(props: CrewsPageProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const translate: Translate = (key, params) => t(key, params);
  const [searchParams, setSearchParams] = useSearchParams();
  const view = crewsViewFrom(searchParams.get(VIEW_PARAM));
  const [adding, setAdding] = useState<Adding>(null);

  const watchQuery = useQuery({
    queryKey: queryKeys.workCertificationWatch(),
    queryFn: () => getCertificationWatch(client),
  });
  const watch = watchQuery.data;

  const technicianConfig = useMemo(
    () =>
      technicianListConfig(translate, {
        technician: (row) => (
          <span className="inline-flex items-center gap-2">
            <InlineLinkTo to={tenantPath(technicianDetailPath(row.slug))}>{row.name}</InlineLinkTo>
            {(() => {
              const state = watch === undefined ? null : certificationState(row, watch.today);
              return state === null ? null : (
                <StatusPill tone={CERT_PILL[state].tone}>
                  {t(CERT_PILL[state].key)}
                </StatusPill>
              );
            })()}
          </span>
        ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, watch?.today],
  );
  // `DEF-WRK-9672` — the crew's day pack, by the crew's SLUG (B14 rule 31),
  // through the SAME dialog the technician page opens (B14 rule 43).
  const [printing, setPrinting] = useState<CrewListRow | null>(null);
  const regional = useRegional({});
  const crewConfig = useMemo(
    () =>
      crewListConfig(translate, (row) => (
        <RowActions>
          <RowAction
            icon={<PrinterIcon />}
            label={t("work.crews.printDay")}
            onClick={() => setPrinting(row)}
          />
        </RowActions>
      )),
    [t], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const contractorConfig = useMemo(() => contractorListConfig(translate), [t]); // eslint-disable-line react-hooks/exhaustive-deps

  // Universal search's *View all* opens this list as `?q=<term>` (DEF-WRK-4094);
  // seeded ONCE, at mount, into the list the address names.
  const [states, setStates] = useState<Record<CrewsView, TableRequestState>>(() => {
    const seeded = {
      technicians: defaultRequestState(technicianConfig),
      crews: defaultRequestState(crewConfig),
      contractors: defaultRequestState(contractorConfig),
    };
    return { ...seeded, [view]: seedQueryFromUrl(seeded[view], searchParams) };
  });
  const state = states[view];
  const setState = (next: TableRequestState) => setStates((all) => ({ ...all, [view]: next }));

  const listQuery = useQuery({
    queryKey: [...queryKeys.workCrews(state.q, state.page, state.per), view, state.sort, state.dir],
    queryFn: () =>
      listCrewsView(
        view,
        { q: state.q, page: state.page, per: state.per, sort: state.sort, dir: state.dir },
        client,
      ),
  });
  const counts: CrewsViewCounts | undefined = listQuery.data?.counts;

  const strip = useWorkTabs(t("work.crews.sentence"));

  function chooseView(next: string) {
    const params = new URLSearchParams(searchParams);
    if (next === "technicians") params.delete(VIEW_PARAM);
    else params.set(VIEW_PARAM, next);
    params.delete("q");
    setSearchParams(params, { replace: true });
  }

  const addMember = (variant: "primary" | "secondary") => (
    <Button variant={variant} data-add-crew-member="" onClick={() => setAdding("member")}>
      {t("work.crews.addMember")}
    </Button>
  );

  const done = () => {
    setAdding(null);
    void queryClient.invalidateQueries({ queryKey: ["work"] });
  };

  const shared = {
    state,
    onStateChange: setState,
    totalRows: listQuery.data?.count ?? null,
    loading: listQuery.isPending,
    error: listQuery.isError
      ? { reason: t("work.crews.loadFailed"), onRetry: () => void listQuery.refetch() }
      : null,
  };

  return (
    <div data-work-crews="" data-screen={WORK_CREWS_SCREEN} data-crews-view={view}>
      <PageHeader
        // B14 rule 2 — ONE page header, and it carries the module's tab strip.
        kicker={t("work.crews.kicker")}
        title={t("work.crews.title")}
        {...strip}
        secondaryActions={view === "crews" ? addMember("secondary") : undefined}
        primaryAction={
          view === "technicians" ? (
            addMember("primary")
          ) : view === "crews" ? (
            <Button variant="primary" data-add-crew="" onClick={() => setAdding("crew")}>
              {t("work.crews.addCrew")}
            </Button>
          ) : (
            <Button variant="primary" data-add-contractor="" onClick={() => setAdding("contractor")}>
              {t("work.crews.addContractor")}
            </Button>
          )
        }
      />

      <SegmentedControl
        className="mb-4"
        name="crews-view"
        label={t("work.crews.views")}
        active={view}
        onSelect={chooseView}
        segments={CREWS_VIEWS.map((id) => ({
          id,
          label: t(`work.crews.view.${id}`),
          count: counts?.[id],
        }))}
      />

      {view === "technicians" && (
        <DataTable<TechnicianListRow>
          key="technicians"
          config={technicianConfig}
          rows={(listQuery.data?.results ?? []) as TechnicianListRow[]}
          {...shared}
          empty={{
            title: t("work.crews.empty.technicians"),
            helper: t("work.crews.empty.technicianHelper"),
            ctaLabel: t("work.crews.addMember"),
            ctaVariant: "secondary",
            onCta: () => setAdding("member"),
          }}
        />
      )}
      {view === "crews" && (
        <DataTable<CrewListRow>
          key="crews"
          config={crewConfig}
          rows={(listQuery.data?.results ?? []) as CrewListRow[]}
          {...shared}
          empty={{
            title: t("work.crews.empty.crews"),
            helper: t("work.crews.empty.crewHelper"),
            ctaLabel: t("work.crews.addCrew"),
            ctaVariant: "secondary",
            onCta: () => setAdding("crew"),
          }}
        />
      )}
      {view === "contractors" && (
        <DataTable<CrewListRow>
          key="contractors"
          config={contractorConfig}
          rows={(listQuery.data?.results ?? []) as CrewListRow[]}
          {...shared}
          empty={{
            title: t("work.crews.empty.contractors"),
            helper: t("work.crews.empty.contractorHelper"),
            ctaLabel: t("work.crews.addContractor"),
            ctaVariant: "secondary",
            onCta: () => setAdding("contractor"),
          }}
        />
      )}

      {view === "technicians" && <CertificationWatchBox watch={watch} />}

      {adding === "member" && (
        <AddCrewMemberModal client={client} onClose={() => setAdding(null)} onAdded={done} />
      )}
      {adding === "crew" && (
        <AddCrewModal client={client} onClose={() => setAdding(null)} onAdded={done} />
      )}
      {adding === "contractor" && (
        <AddContractorModal client={client} onClose={() => setAdding(null)} onAdded={done} />
      )}
      {printing !== null && (
        <PrintDayDialog
          name={printing.name}
          holder={{ crew: printing.slug }}
          tenantPath={tenantPath}
          timeZone={regional.timeZone}
          dateFormat={regional.dateFormat}
          onClose={() => setPrinting(null)}
        />
      )}
    </div>
  );
}

/**
 * The watch — `Panel tone="warning"`, the kit's amber-bordered box (B14 rule
 * 36; `DEF-CWP-3655` was four screens growing four boxes).
 *
 * ⚠ **IT WARNS AND NEVER SAYS ANYBODY IS BLOCKED (`DEF-WRK-9634`).** PO answer
 * 2 of 2026-10-04 — *"(a) Warn only, the same as skills."* — superseded
 * `BR-WRK-030` for every tenant, so the *blocked from N template types*
 * sentence this box drew where a utility had switched blocking on is gone with
 * the setting it described, whatever the server still sends in `blocks`. A
 * certification already run out reads *expired*, a coming one *expires*.
 */
export function CertificationWatchBox(props: { watch: CertificationWatch | undefined }) {
  const { t } = useTranslation();
  const watch = props.watch;
  if (watch === undefined || watch.windows.length === 0) return null;
  return (
    <Panel tone="warning" as="section" title={t("work.crews.watch.title")} data-cert-watch="">
      {watch.windows.map((window) => (
        <p key={window.days} className="m-0 mb-1 text-sm">
          <strong>{t("work.crews.watch.window", { days: window.days })}</strong>
          {" — "}
          {window.entries.map((entry, index) => (
            <span
              key={`${entry.technician_slug}-${entry.expires_on}`}
              data-cert-watch-entry={entry.expired ? "expired" : "expiring"}
            >
              {index > 0 && " · "}
              {t(entry.expired ? "work.crews.watch.expired" : "work.crews.watch.entry", {
                technician: entry.technician,
                certification: entry.certification ?? "",
                date: entry.expires_on,
              })}
            </span>
          ))}
        </p>
      ))}
    </Panel>
  );
}

export default CrewsPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-168-BRC10 §5.5 (C1–C4) · §8 R4 CREWS · images 25–30 (read as IMAGES)
// generated: 2026-10-04 by lane CREWS (round 4), replacing the CR-070 wave F one-table screen
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST — crewsLane.dom.test.tsx 14 of 14 red on the one-table screen (it read /work/crews with no view; no Crews 2 segment; no Add a crew; the watch said "blocked from 4 template types") · tsc · eslint · vitest · routeBUtilities.test.ts (on route-b-migrated.txt)
// exceptions: E4 the Crews list's MEMBERS column draws the names (lane CREWS-2, on SRV-4's `member_names`) as text and not in the drawn link colour — the server serves names without the technicians' addresses, so a coloured name would look pressable and open nothing · E4 C2's column chooser has no drawn home and is the kit table's own control · E4 the drawing's search box stands above the table; here it is the kit table toolbar's search (rule 12), the same control in the kit's position
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
