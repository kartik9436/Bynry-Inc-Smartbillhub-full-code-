// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-018 (versions, and what v2 means — the four v1 orders still
//           read v1) · US-WRK-015 (Duplicate · Deactivate · Delete-refused) ·
//           US-WRK-013 (the header a person reads).
//           Screens: Work-022 (`wireframes/Work-022.png`), template W5
// Rules:    BR-WRK-008 (copy, never link) · BR-WRK-012 (versioned; Delete
//           refused while referenced; Deactivate instead) · BR-SHL-025 (a
//           control that cannot act is DISABLED WITH ITS REASON) · B14 rules
//           2 · 5 · 6 (danger tier on a destructive commit) · 20 · 21 · 31
//           (no database id is a visible value) · 32 (one sentence per
//           section)
// Tests:    src/features/work/TemplateDetailPage.test.tsx
// Impacts:  src/features/work/workEndpoints.ts · TemplatesPage.tsx (the row
//           action opens this) · src/routing/screenIds.ts (WRK-15) ·
//           src/App.tsx (one route)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE VERSIONS TAB IS THE WHOLE ARGUMENT OF `BR-WRK-008` MADE VISIBLE.**
// *"Copy, never link"* is a sentence in a rules file until a supervisor can
// see **v2 · 31 orders · Current** above **v1 · 4 orders · Superseded** and
// read, underneath, that the four v1 orders still read v1. The count is
// computed from `work_orders` at read time — nothing caches it on the version
// row, because a cached count is a second answer to a question the orders
// table already answers, and it is the copy that goes stale (PO, 2026-09-05:
// *"two answers to one question is how a figure drifts"*).
//
// ⚠ **DELETE SHIPS DISABLED AND SAYS WHY, AND THE SERVER REFUSES ANYWAY.**
// `BR-SHL-025` asks for both halves and this screen is where forgetting one
// would be invisible: a screen that only greyed the control would leave a
// template a scripted `DELETE` could still remove out from under 35 orders.
// The reason carries the NUMBER, because *"it has produced work orders"*
// invites the question *"how many?"* and a screen that made a person ask again
// has not answered.
//
// ⚠ **`Edit template` IS LIVE SINCE 2026-09-05, AND THE HOLD DOING ITS JOB IS
// WHY.** This paragraph said the control was NOT rendered because the
// eight-step builder was wave E's, and it said so beside a test that asserted
// the absence BY NAME so the day `TemplateBuilder.tsx` landed the suite would
// go red and say which button was owed. It landed; the suite went red; the
// button is here, pointing at `…/work/templates/{id}/edit`.
//
// **That is the whole of `DEF-CWP-3925`'s prevention, run once end to end:**
// *when you write a hold, write the test that fires when the hold expires, in
// the same commit* — and when you land the screen, grep for the control that
// was holding it. The test is now the mirror of what it was: it asserts the
// button EXISTS and asserts its DESTINATION, so a future refactor that quietly
// unpoints it fails too.
//
// ⚠ **TWO FIGURES IN THE DRAWING ARE NOT COPIED, AND `03-field-map.md` §5 SAYS
// WHY.** The kicker draws *40 min · 1 technician* where `Work-013` says *45
// min* for the same template, and the change note reads *"opening-read max 999
// → 999"*, which changes nothing and reads as a slip. Neither is invented
// here: the meta line reads the template's OWN estimate and crew size, and the
// change note is whatever the person who published it typed.
import { useTranslation } from "react-i18next";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, diagnosticOf, isApiError } from "@/api/client";
import { getLookupEntries } from "@/api/endpoints";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ButtonLink } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { ListPager } from "@/components/ListPager";
import { Panel } from "@/components/Panel";
import { FailedWithRetry } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import {
  detailTabFrom,
  Dash,
  GuardedButton,
  useRegional,
} from "@/features/metering/meteringShared";
import type { DetailTab, RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { WORK_ORDER_TEMPLATES_ROUTE } from "./TemplatesPage";
// CR-070 wave E — ONE function says where the builder opens a template, so
// this screen and the list cannot disagree about the address (law 5). The
// dependency runs one way (`TemplateBuilder` never imports this file), so
// there is no cycle of the kind `DEF-WRK-3955` found in the tab strip.
import { templateEditPath } from "./TemplateBuilder";
import { draftFromTemplate } from "./templateBuilderModel";
import { TemplateSummary } from "./TemplateSummary";
import {
  deleteTemplate,
  duplicateTemplate,
  getTemplate,
  getTemplateAudit,
  getTemplateVersions,
  setTemplateActive,
} from "./workEndpoints";
import type { TemplateAuditRow, TemplateDetail, TemplateVersions } from "./workEndpoints";

/** r10's own badge for the template detail — `01-overview.md` §6, Work-022 ↔
 *  WRK-15. */
export const WORK_TEMPLATE_DETAIL_SCREEN = "WRK-15";

/** The route, with its own id segment. Declared AFTER the list's static path
 *  so the `/connections/new` trap `App.tsx` records cannot bite. */
export const WORK_TEMPLATE_DETAIL_ROUTE = `${WORK_ORDER_TEMPLATES_ROUTE}/:templateId`;

const TAB_PARAM = "tab";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/**
 * `Work-022`'s four tabs, in the drawing's order.
 *
 * Exported so the test can assert the set without a DOM. **Audit is last and
 * stays last**, which is this product's convention on every detail screen.
 */
export function templateTabs(t: Translate): DetailTab[] {
  return [
    { id: "overview", label: t("work.template.tab.overview", { defaultValue: "Overview" }) },
    { id: "usage", label: t("work.template.tab.usage", { defaultValue: "Usage" }) },
    { id: "versions", label: t("work.template.tab.versions", { defaultValue: "Versions" }) },
    { id: "audit", label: t("work.template.tab.audit", { defaultValue: "Audit" }) },
  ];
}

/**
 * Why `Delete` cannot be pressed, in the words a person reads — or `null` when
 * it can.
 *
 * Exported and pure, because this is the sentence `BR-WRK-012` is made of and
 * a test that had to mount a screen to check it would be a test nobody runs.
 */
export function deleteBlockedReason(
  detail: TemplateDetail | undefined,
  t: Translate,
): string | null {
  if (detail === undefined) {
    return t("work.template.delete.loading", { defaultValue: "Still loading." });
  }
  if (detail.orders_raised > 0) {
    return t("work.template.delete.referenced", {
      count: detail.orders_raised,
      defaultValue: "{{count}} work orders came from this template.",
    });
  }
  return null;
}

export interface TemplateDetailPageProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function TemplateDetailPage(props: TemplateDetailPageProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const translate: Translate = (key, params) => t(key, params);
  const params = useParams();
  const templateId = params.templateId ?? "";
  const [searchParams, setSearchParams] = useSearchParams();

  const tabs = templateTabs(translate);
  const active = detailTabFrom(searchParams.get(TAB_PARAM), tabs);

  const detailQuery = useQuery({
    queryKey: queryKeys.workTemplate(templateId),
    queryFn: () => getTemplate(templateId, client),
    enabled: templateId !== "",
  });
  // The summary names asset types; the template holds their ids (B14 rule 31).
  const assetTypesQuery = useQuery({
    queryKey: ["work-template-asset-types"],
    queryFn: () => getLookupEntries("asset_types", { per: 200 }, client),
    enabled: active === "overview",
  });
  const versionsQuery = useQuery({
    queryKey: queryKeys.workTemplateVersions(templateId),
    queryFn: () => getTemplateVersions(templateId, client),
    enabled: templateId !== "",
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["work", "templates"] });
    void queryClient.invalidateQueries({ queryKey: ["work", "template", templateId] });
  };

  const duplicate = useMutation({
    mutationFn: () => duplicateTemplate(templateId, client),
    onSuccess: invalidate,
  });
  const toggleActive = useMutation({
    mutationFn: (next: boolean) => setTemplateActive(templateId, next, client),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: () => deleteTemplate(templateId, client),
    onSuccess: invalidate,
  });

  const detail = detailQuery.data;
  const blocked = deleteBlockedReason(detail, translate);
  // BR-SHL-034 — ONE date formatter. The versions table printed
  // `published_at.slice(0, 10)`, which is the server's ISO day with the letters
  // cut off it: a US utility read `2026-03-28` where every other date on every
  // other screen reads `03/28/2026`, and a tenant on a different format read
  // the wrong one silently. Reads the tenant's own pair, published by the shell
  // (DEF-SHL-3964) — there is no seed fallback behind it any more.
  const regional = useRegional(props);
  const navigate = useNavigate();

  // ── A18 §4 — a read that FAILED is its own state (`DEF-WRK-4637`) ────────
  // The header used to read *Loading* for ever over a 404, with Edit,
  // Duplicate, Deactivate and Delete drawn live over nothing. The same
  // three-branch shape `OrderDetailPage` took for `DEF-WRK-4518`: the way back
  // stays, the commands go, and the failure is named.
  if (detailQuery.isError) {
    const notFound = isApiError(detailQuery.error) && detailQuery.error.status === 404;
    return (
      <div data-work-template-detail="" data-screen={WORK_TEMPLATE_DETAIL_SCREEN} data-template-failed="">
        <PageHeader
          backTo={{
            to: tenantPath(WORK_ORDER_TEMPLATES_ROUTE),
            label: t("work.template.back", { defaultValue: "Templates" }),
          }}
          title={t("work.template.kicker")}
        />
        <FailedWithRetry
          title={t("work.template.failedTitle")}
          reason={notFound ? t("work.template.notFound") : t("work.template.unreadable")}
          onRetry={() => void detailQuery.refetch()}
          onDownloadReport={() => undefined}
          onCancel={() => navigate(tenantPath(WORK_ORDER_TEMPLATES_ROUTE))}
          diagnostic={diagnosticOf(detailQuery.error)}
        />
      </div>
    );
  }

  return (
    <div data-work-template-detail="" data-screen={WORK_TEMPLATE_DETAIL_SCREEN}>
      <PageHeader
        backTo={{
          to: tenantPath(WORK_ORDER_TEMPLATES_ROUTE),
          label: t("work.template.back", { defaultValue: "Templates" }),
        }}
        // B14 rule 31 — the KICKER carries the number and the version, which
        // are what a supervisor quotes. The uuid is in the URL and nowhere on
        // screen.
        kicker={kickerFor(detail, translate)}
        title={detail?.name ?? t("work.template.loading", { defaultValue: "Loading" })}
        status={
          detail === undefined ? null : (
            <StatusPill tone={detail.active ? "success" : "muted"}>
              {translate(detail.active ? "work.template.active" : "work.template.inactive", {
                defaultValue: detail.active ? "Active" : "Inactive",
              })}
            </StatusPill>
          )
        }
        rollup={detail === undefined ? undefined : <span>{metaFor(detail, translate)}</span>}
        secondaryActions={
          <>
            {/* `Work-022`'s primary — the eight-step builder, opened at step 1
                on THIS template (CR-070 wave E, `US-WRK-016`). A `ButtonLink`
                and not a button: it NAVIGATES, so middle-click and open-in-new-
                tab keep working, which is the same reason the kit has one. */}
            <ButtonLink
              variant="primary"
              data-edit-template=""
              to={tenantPath(templateEditPath(templateId))}
            >
              {t("work.template.edit", { defaultValue: "Edit template" })}
            </ButtonLink>
            <GuardedButton
              label={t("work.template.duplicate", { defaultValue: "Duplicate" })}
              reason={detail === undefined ? t("work.template.delete.loading", { defaultValue: "Still loading." }) : null}
              working={duplicate.isPending}
              onClick={() => duplicate.mutate()}
            />
            <GuardedButton
              label={
                detail?.active === false
                  ? t("work.template.reactivate", { defaultValue: "Reactivate" })
                  : t("work.template.deactivate", { defaultValue: "Deactivate" })
              }
              reason={detail === undefined ? t("work.template.delete.loading", { defaultValue: "Still loading." }) : null}
              working={toggleActive.isPending}
              onClick={() => toggleActive.mutate(detail?.active === false)}
            />
            {/* B14 rule 6 — the DANGER tier, because this is a destructive
                commit. `BR-SHL-025` — disabled WITH its reason, and the reason
                carries the count. */}
            <GuardedButton
              label={t("work.template.delete", { defaultValue: "Delete" })}
              reason={blocked}
              danger
              working={remove.isPending}
              onClick={() => remove.mutate()}
            />
          </>
        }
        tabs={tabs}
        activeTabId={active}
        tabsLabel={t("work.template.tabs", { defaultValue: "Template sections" })}
        onTabSelect={(tab) => {
          const next = new URLSearchParams(searchParams);
          next.set(TAB_PARAM, tab.id);
          setSearchParams(next, { replace: true });
        }}
      />

      {active === "overview" && (
        <OverviewTab
          detail={detail}
          assetTypeNames={assetTypesQuery.data?.results ?? []}
          editHref={(step) => `${tenantPath(templateEditPath(templateId))}?step=${step}`}
        />
      )}
      {active === "usage" && <UsageTab versions={versionsQuery.data} t={translate} />}
      {active === "versions" && (
        <VersionsTab versions={versionsQuery.data} t={translate} regional={regional} />
      )}
      {active === "audit" && (
        <AuditTab templateId={templateId} client={client} t={translate} regional={regional} />
      )}
    </div>
  );
}

/** *SERVICE TEMPLATE · ST-0002 · V2* — the drawing's kicker, minus the uuid. */
function kickerFor(detail: TemplateDetail | undefined, t: Translate): string {
  if (detail === undefined) return t("work.template.kicker", { defaultValue: "Service template" });
  const parts = [t("work.template.kicker", { defaultValue: "Service template" })];
  if (detail.template_no !== null) parts.push(detail.template_no);
  if (detail.version >= 1) {
    parts.push(
      t("work.template.version", { version: detail.version, defaultValue: "v{{version}}" }),
    );
  }
  return parts.join(" · ");
}

/** *45 min · 1 technician* — read from the template's own columns, never from
 *  the drawing's figure (`03-field-map.md` §5 records the disagreement). */
function metaFor(detail: TemplateDetail, t: Translate): string {
  const bits: string[] = [];
  if (detail.est_duration_minutes !== null) {
    bits.push(
      t("work.templates.minutes", {
        count: detail.est_duration_minutes,
        defaultValue: "{{count}} min",
      }),
    );
  }
  bits.push(
    t("work.template.crew", {
      count: detail.crew_size,
      defaultValue: "{{count}} technician",
    }),
  );
  return bits.join(" · ");
}

/**
 * Image 44 — the template, every row of it (ruling 8, P3.26). The SAME
 * `TemplateSummary` the builder's Review draws (B14 rule 43); ✎ Edit is a link
 * to the builder at the step that owns the section.
 */
function OverviewTab(props: {
  detail: TemplateDetail | undefined;
  assetTypeNames: { id: string; name: string }[];
  editHref: (step: number) => string;
}) {
  const { detail } = props;
  if (detail === undefined) return null;
  const draft = draftFromTemplate(detail);
  return (
    <TemplateSummary
      draft={draft}
      names={{
        service: detail.service?.name ?? null,
        jobType: detail.job_type?.name ?? null,
        skill: detail.skill?.name ?? null,
        safetyKit: detail.safety_kit?.name ?? null,
        assetTypes: draft.assetTypeIds
          .map((id) => props.assetTypeNames.find((row) => row.id === id)?.name ?? null)
          .filter((name): name is string => name !== null),
      }}
      edit={{ kind: "link", href: props.editHref }}
    />
  );
}

/** P3.29 — *1 order raised across 2 versions*: each count in the catalogue's
 *  own plural, never a number pasted into a plural noun. */
export function usageSentence(orders: number, versions: number, t: Translate): string {
  return t("work.template.usageWords", {
    orders: t("work.template.ordersRaised", { count: orders, defaultValue: "{{count}} orders raised" }),
    versions: t("work.template.versionsCount", { count: versions, defaultValue: "{{count}} versions" }),
    defaultValue: "{{orders}} across {{versions}}",
  });
}

function UsageTab(props: { versions: TemplateVersions | undefined; t: Translate }) {
  const { versions, t } = props;
  if (versions === undefined) return null;
  return (
    <Panel as="section">
      <Note className="tabular-nums" data-template-usage="">
        {usageSentence(versions.orders_raised, versions.versions.length, t)}
      </Note>
    </Panel>
  );
}

function VersionsTab(props: {
  versions: TemplateVersions | undefined;
  t: Translate;
  regional: { timeZone: string; dateFormat: RegionalDateFormat };
}) {
  const { versions, t } = props;
  if (versions === undefined) return null;
  if (versions.versions.length === 0) {
    return (
      <Panel as="section">
        {/* B14 rule 32 — one sentence, and it is TRUE rather than reassuring:
            a draft has never been published, so it genuinely has no version. */}
        <Note data-template-no-versions="">
          {t("work.template.versions.none", {
            defaultValue: "This template has not been published yet.",
          })}
        </Note>
      </Panel>
    );
  }
  return (
    <Panel as="section">
      {/* ⚠ **THE KIT'S TABLE, NOT A SECOND ONE (B14 rules 20 and 36, 2026-09-05).**
          This was a hand-rolled `<table className="w-full text-left">`: no
          13.5px body type, no 12px uppercase header tier, no divider under a
          row. Rule 20 says the product has ONE table type and `PlainTable` is
          the small-in-a-panel one — 51 other sites draw it — so a template's
          version history looked like nothing else in the product on a screen a
          supervisor reads to settle an argument. */}
      <PlainTable data-template-versions="">
        <thead>
          <tr>
            <th scope="col">{t("work.template.col.version", { defaultValue: "Version" })}</th>
            <th scope="col">{t("work.template.col.published", { defaultValue: "Published" })}</th>
            <th scope="col">{t("work.template.col.changed", { defaultValue: "What changed" })}</th>
            <th scope="col">{t("work.template.col.orders", { defaultValue: "Orders raised" })}</th>
            <th scope="col">{t("work.templates.col.status", { defaultValue: "Status" })}</th>
          </tr>
        </thead>
        <tbody>
          {versions.versions.map((row) => (
            <tr key={row.version}>
              <td className="tabular-nums">
                {t("work.template.version", {
                  version: row.version,
                  defaultValue: "v{{version}}",
                })}
              </td>
              <td>
                <DateCell
                  value={row.published_at}
                  timeZone={props.regional.timeZone}
                  dateFormat={props.regional.dateFormat}
                />
              </td>
              <td>{row.change_note === null ? <Dash /> : row.change_note}</td>
              <td className="tabular-nums">{row.orders_raised}</td>
              <td>
                <StatusPill tone={row.status === "current" ? "success" : "muted"}>
                  {t(`work.template.versionStatus.${row.status}`, {
                    defaultValue: row.status === "current" ? "Current" : "Superseded",
                  })}
                </StatusPill>
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>

      {/* `Work-022`'s CountFooter, and the sentence is the RULE made readable:
          publishing v2 rewrote nothing. The superseded row's own count is what
          proves it, so the sentence names that count rather than asserting the
          rule in the abstract. */}
      <Note className="tabular-nums" data-template-versions-footer="">
        {t("work.template.versions.footerWords", {
          usage: usageSentence(versions.orders_raised, versions.versions.length, t),
          defaultValue: "{{usage}} — nothing was rewritten",
        })}
      </Note>
    </Panel>
  );
}

/** The words for each act and each replaced list. LITERAL keys, so `G18`
 *  can see every one (a template key renders and is invisible to the gate). */
const AUDIT_ACT: Record<string, { key: string; en: string }> = {
  created: { key: "work.template.audit.act.created", en: "Created" },
  updated: { key: "work.template.audit.act.updated", en: "Details changed" },
  deactivated: { key: "work.template.audit.act.deactivated", en: "Deactivated" },
  reactivated: { key: "work.template.audit.act.reactivated", en: "Reactivated" },
  duplicated: { key: "work.template.audit.act.duplicated", en: "Duplicated" },
  help_document_stored: { key: "work.template.audit.act.helpDocument", en: "Help document added" },
  deleted: { key: "work.template.audit.act.deleted", en: "Deleted" },
};
const AUDIT_REPLACED: Record<string, { key: string; en: string }> = {
  details: { key: "work.template.audit.replaced.details", en: "What the technician sees changed" },
  safety: { key: "work.template.audit.replaced.safety", en: "Safety checks changed" },
  tasks: { key: "work.template.audit.replaced.tasks", en: "Tasks changed" },
  materials: { key: "work.template.audit.replaced.materials", en: "Materials changed" },
  readings: { key: "work.template.audit.replaced.readings", en: "Readings changed" },
  help: { key: "work.template.audit.replaced.help", en: "Help changed" },
  "asset-types": { key: "work.template.audit.replaced.assetTypes", en: "Asset types changed" },
};

/** What one line of the trail says happened — the act, in words, and for a
 *  replaced list WHICH list (`collection`). An act this screen has no words
 *  for reads as *Changed* rather than as its code (B14 rule 31). */
export function auditActText(row: TemplateAuditRow, t: Translate): string {
  if (row.act === "published") {
    return t("work.template.audit.act.published", { version: row.version ?? 0, defaultValue: "Published v{{version}}" });
  }
  const words = row.act === "replaced" ? AUDIT_REPLACED[row.collection ?? ""] : AUDIT_ACT[row.act];
  if (words === undefined) return t("work.template.audit.act.other", { defaultValue: "Changed" });
  return t(words.key, { defaultValue: words.en });
}

/**
 * Image 47 — the change history (P3.28). The trail `audit_log` held for every
 * builder write, read through `GET …/audit`, paged on the server.
 *
 * ⚠ **THE HOLD SENTENCE IS DELETED IN THE COMMIT THAT READS THE TRAIL** (*"The
 * change history opens with the next release."*), and a test asserts it is
 * gone — otherwise the history exists and the page still denies it, which is
 * `DEF-CWP-3925`'s shape.
 */
function AuditTab(props: {
  templateId: string;
  client: ApiClient;
  t: Translate;
  regional: { timeZone: string; dateFormat: RegionalDateFormat };
}) {
  const { t } = props;
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<50 | 100 | 200 | 500 | 1000>(50);
  const query = useQuery({
    queryKey: ["work", "template", props.templateId, "audit", page, per],
    queryFn: () => getTemplateAudit(props.templateId, { page, per }, props.client),
    enabled: props.templateId !== "",
  });
  const data = query.data;
  if (query.isError) {
    return (
      <Panel as="section">
        <Note data-template-audit-failed="">
          {t("work.template.audit.failed", { defaultValue: "The history could not be read." })}
        </Note>
      </Panel>
    );
  }
  if (data === undefined) return null;
  return (
    <Panel as="section">
      {data.results.length === 0 ? (
        <Note data-template-audit-empty="">
          {t("work.template.audit.empty", { defaultValue: "No changes recorded yet." })}
        </Note>
      ) : (
        <PlainTable data-template-audit="">
          <thead>
            <tr>
              <th scope="col">{t("work.template.audit.col.when", { defaultValue: "When" })}</th>
              <th scope="col">{t("work.template.audit.col.who", { defaultValue: "Who" })}</th>
              <th scope="col">{t("work.template.audit.col.what", { defaultValue: "What" })}</th>
              <th scope="col">{t("work.template.col.version", { defaultValue: "Version" })}</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((row, index) => (
              <tr key={`${row.at}-${index}`}>
                <td>
                  <DateCell value={row.at} timeZone={props.regional.timeZone} dateFormat={props.regional.dateFormat} />
                </td>
                <td>{row.by === null ? <Dash /> : row.by.name}</td>
                <td>{auditActText(row, t)}</td>
                <td className="tabular-nums">
                  {row.version === null || row.version === 0 ? (
                    <Dash />
                  ) : (
                    t("work.template.version", { version: row.version, defaultValue: "v{{version}}" })
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}
      <ListPager
        total={data.count}
        page={page}
        per={per}
        onPage={setPage}
        onPer={(next) => {
          setPer(next as typeof per);
          setPage(1);
        }}
      />
    </Panel>
  );
}

export default TemplateDetailPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-018/015/013@6eedbd26 (EP-WRK-03) · 08-screen-layouts.md Work-022 · 09-component-inventory.md W5 · wireframes/Work-022.png
// generated: 2026-09-05 by the CR-070 wave D build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · vitest src/features/work · G31 (via src/styles/route-b-migrated.txt) · G13
// exceptions: E3 the Audit tab states one sentence rather than reading the trail — the audit READER is wave M's, and the rows exist today. ⚠ THE SENTENCE IS A HOLD WITH A CLOCK IN IT (*"opens with the next release"*) AND NOTHING FIRES WHEN WAVE M LANDS; that is `DEF-CWP-3925`'s exact shape and the test it asks for is owed · E4 there is no `VERSIONS` caption above the versions table — the drawing draws one and no list in the product does; decided once for the module in `08-screen-layouts.md`
// ⚠ THIS LINE CLAIMED `Edit template` WAS NOT RENDERED UNTIL 2026-09-05 (DEF-WRK-4046), and it has been rendered since wave E landed the eight-step builder — the `ButtonLink` is ~250 lines above. The file's own ⚠ paragraph *"`Edit template` IS LIVE SINCE 2026-09-05"* was written in the commit that landed it and this line was not touched, which is the same miss `TemplatesPage.tsx` made three times over. The locale-key clause was expired too: all eleven catalogues carry the 72 `work.template*` keys.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
