// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 5, lane RULES — one rule's own page: Overview ·
//           Jobs · Audit (images 62, 63, 64). It did not exist: the address
//           opened *"This screen is not built yet"* (`a62-rule-detail`).
// Tasks:    P3.62 (the rule detail view and its route) · P3.63 (open, edit,
//           duplicate) · P3.17 (edit a rule) · `DEF-WRK-9564`
// Rules:    README ruling 16 (*"the action buttons should be on the top right
//           side"*) · B14 rules 2, 20, 31 (names, never ids), 33, 36, 41–44 ·
//           `BR-WRK-033` (a rule that is off raises nothing and keeps its
//           memory) · hard rule 7 (the Audit tab reads `audit_log`)
// Tests:    src/features/work/rules/cr168Rules.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **NOT INSIDE `WorkShell`.** Images 62–64 draw the module strip over the
// rule; every Work record page (one order, one technician, one template) sits
// under its own ← instead, because the strip is a strip of LISTS
// (`DEF-WRK-3724`). The same choice here keeps one shape for a record page in
// this module; the divergence is written in `RULES-side-by-side.md`.
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button, ButtonLink } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { useTenantRegional } from "@/components/TenantRegional";
import { useToast } from "@/components/Toast";
import { EyeIcon } from "@/components/icons";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";
import { detailTabFrom } from "@/features/metering/meteringShared";
import type { DetailTab } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { workOrderDetailPath } from "./OrderDetailPage";
import { dispatchStateTone, workOrderOutcomeTone, workOrderStateTone } from "./OrdersPage";
import { ruleDuplicatePath, ruleEditPath } from "./RuleBuilder";
import { WORK_RULES_ROUTE } from "./WorkShell";
import type { WorkOrderDispatchRow } from "./workEndpoints";
import { getRule, listRuleAudit, listRuleJobs, setRuleEnabled } from "./rules/ruleEndpoints";
import type { RuleAuditRow, WorkRuleDetail } from "./rules/ruleEndpoints";
import { Emphasised, RuleSummary } from "./rules/RuleSummary";
import { draftFromRule, processWord } from "./rules/ruleModel";
import type { RuleNames, Translate } from "./rules/ruleModel";
import { useRuleLookups } from "./rules/useRuleLookups";
import { WhereCell } from "./WhereCell";

/** One rule's page. Images 62–64 carry r10's `WRK-06` (the rules screen); the
 *  record is its child, so a dotted sub-id and no new number (the way
 *  `WRK-10.import` sits under the parts register). */
export const WORK_RULE_DETAIL_SCREEN = "WRK-06.rule";

/** The route — declared AFTER `…/rules/new` in `App.tsx`, or `new` is read as
 *  a rule's id. */
export const WORK_RULE_DETAIL_ROUTE = `${WORK_RULES_ROUTE}/:ruleId`;

export function ruleDetailPath(ruleId: string, tab?: string): string {
  const base = `${WORK_RULES_ROUTE}/${ruleId}`;
  return tab === undefined ? base : `${base}?tab=${tab}`;
}

const TAB_PARAM = "tab";

/** Images 62–64's three tabs, in the drawing's order. Audit is last. */
export function ruleTabs(t: Translate): DetailTab[] {
  return [
    { id: "overview", label: t("work.rules.page.tab.overview") },
    { id: "jobs", label: t("work.rules.page.tab.jobs") },
    { id: "audit", label: t("work.rules.page.tab.audit") },
  ];
}

function When(props: { value: string | null; withTime?: boolean }) {
  const regional = useTenantRegional();
  if (props.value === null) return <Dash />;
  if (regional === null) return <span className="tabular-nums">{props.value.slice(0, 10)}</span>;
  return (
    <DateCell
      value={props.value}
      timeZone={regional.timeZone}
      dateFormat={regional.dateFormat}
      withTime={props.withTime}
    />
  );
}

// ── Overview — image 62 ───────────────────────────────────────────────────

function OverviewTab(props: {
  rule: WorkRuleDetail;
  names: RuleNames;
  processes: ReturnType<typeof useRuleLookups>["processes"];
  editHref: (step: number) => string;
  t: Translate;
}) {
  const { rule, t } = props;
  const draft = useMemo(() => draftFromRule(rule, props.processes), [rule, props.processes]);
  return (
    <div className="flex flex-col gap-4">
      <Panel as="section" title={rule.name} data-rule-panel="head">
        <p className="m-0 flex flex-wrap items-center gap-2 text-base text-text">
          <StatusPill tone={rule.enabled ? "success" : "neutral"}>
            {rule.enabled ? t("work.rules.on") : t("work.rules.off")}
          </StatusPill>
          <span data-rule-raises="">
            {rule.priority === null ? (
              <Emphasised
                t={t}
                i18nKey="work.rules.page.raises"
                values={{ template: rule.template.name ?? "" }}
                strong={["template"]}
              />
            ) : (
              <Emphasised
                t={t}
                i18nKey="work.rules.page.raisesAt"
                values={{ template: rule.template.name ?? "", priority: rule.priority.name }}
                strong={["template", "priority"]}
              />
            )}
          </span>
        </p>
        <Note className="mt-1" data-rule-tonight-line="">
          {t(rule.enabled ? "work.rules.page.tonightOn" : "work.rules.page.tonightOff", {
            count: rule.tonight.would_raise,
          })}{" "}
          {(rule.tonight.cannot_raise ?? 0) > 0 && (
            <span data-rule-cannot-raise={rule.tonight.cannot_raise}>
              {t("work.rules.builder.cannotRaise", { count: rule.tonight.cannot_raise })}{" "}
            </span>
          )}
          {rule.last_fired_at === null ? (
            t("work.rules.page.neverFired")
          ) : (
            <>
              {t("work.rules.page.lastFired")} <When value={rule.last_fired_at} />
            </>
          )}
        </Note>
        {rule.incomplete.length > 0 && (
          <p className="mt-2 mb-0 text-base font-semibold text-danger-500" data-rule-incomplete="">
            {t("work.rules.page.incomplete")}
          </p>
        )}
      </Panel>
      <RuleSummary
        draft={draft}
        processes={props.processes}
        names={props.names}
        edit={{ kind: "link", href: props.editHref }}
      />
    </div>
  );
}

// ── Jobs — image 63 ───────────────────────────────────────────────────────

function jobsConfig(
  t: Translate,
  cells: { order: (row: WorkOrderDispatchRow) => ReactNode; open: (row: WorkOrderDispatchRow) => ReactNode },
): TableConfig<WorkOrderDispatchRow> {
  return {
    screenId: WORK_RULE_DETAIL_SCREEN,
    getRowId: (row) => row.id,
    defaultSort: { sort: "raised", dir: "desc" },
    columns: [
      { key: "order_no", label: t("work.rules.jobs.col.order"), identity: true, cell: cells.order },
      {
        key: "premise",
        label: t("work.rules.jobs.col.premise"),
        cell: (row) => <WhereCell premise={row.premise} storedAt={row.stored_at} />,
      },
      { key: "raised", label: t("work.rules.jobs.col.raised"), cell: (row) => <When value={row.raised_at} /> },
      {
        key: "state",
        label: t("work.rules.jobs.col.state"),
        cell: (row) =>
          row.state === "completed" ? (
            <StatusPill tone={workOrderStateTone(row.state)}>{t("work.orders.state.completed")}</StatusPill>
          ) : (
            <StatusPill tone={dispatchStateTone(row.dispatch_state)}>
              {t(`work.orders.dispatch.${row.dispatch_state}`)}
            </StatusPill>
          ),
      },
      {
        key: "outcome",
        label: t("work.rules.jobs.col.outcome"),
        cell: (row) =>
          row.outcome === null ? (
            <Dash />
          ) : (
            <StatusPill tone={workOrderOutcomeTone(row.outcome)}>{t(`work.orders.outcome.${row.outcome}`)}</StatusPill>
          ),
      },
      { key: "actions", label: t("work.rules.col.actions"), cell: cells.open },
    ],
  };
}

function JobsTab(props: { ruleId: string; client: ApiClient; t: Translate }) {
  const { t } = props;
  const params = useParams();
  const tenant = params.tenant ?? "";
  const config = useMemo(
    () =>
      jobsConfig(t, {
        order: (row) => <InlineLinkTo to={workOrderDetailPath(tenant, row.id)}>{row.order_no ?? ""}</InlineLinkTo>,
        open: (row) => (
          <RowActions>
            <RowActionLink
              label={t("work.rules.jobs.open", { order: row.order_no ?? "" })}
              icon={<EyeIcon />}
              to={workOrderDetailPath(tenant, row.id)}
            />
          </RowActions>
        ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [tenant],
  );
  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));
  const query = useQuery({
    queryKey: ["work", "rule", props.ruleId, "jobs", state.page, state.per],
    queryFn: () => listRuleJobs(props.ruleId, { page: state.page, per: state.per }, props.client),
  });
  return (
    <div data-rule-jobs="">
      <Note className="mb-3">{t("work.rules.jobs.lede")}</Note>
      <DataTable<WorkOrderDispatchRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={query.data?.rows ?? []}
        totalRows={query.data?.total ?? null}
        loading={query.isPending}
        error={query.isError ? { reason: t("work.rules.jobs.failed"), onRetry: () => void query.refetch() } : null}
        empty={{ title: t("work.rules.jobs.empty"), helper: t("work.rules.jobs.emptyHelper") }}
      />
    </div>
  );
}

// ── Audit — image 64 ──────────────────────────────────────────────────────

/** The words for each act. LITERAL keys, so `G18` can see every one. */
const ACT_KEY: Record<string, string> = {
  created: "work.rules.audit.act.created",
  edited: "work.rules.audit.act.edited",
  turned_on: "work.rules.audit.act.turnedOn",
  turned_off: "work.rules.audit.act.turnedOff",
};

/** One side of a change, in words — a name, the triggers by their process's
 *  words, On or Off. Never an id (B14 rule 31). */
export function auditSide(
  side: Record<string, unknown>,
  other: Record<string, unknown>,
  processes: ReturnType<typeof useRuleLookups>["processes"],
  t: Translate,
): string | null {
  const bits: string[] = [];
  const changed = (key: string) => JSON.stringify(side[key]) !== JSON.stringify(other[key]);
  if (typeof side.name === "string" && changed("name")) bits.push(side.name);
  if (Array.isArray(side.triggers) && changed("triggers")) {
    bits.push(side.triggers.map((kind) => processWord(String(kind), processes, t)).join(", "));
  }
  if (typeof side.enabled === "boolean" && changed("enabled")) {
    bits.push(side.enabled ? t("work.rules.on") : t("work.rules.off"));
  }
  return bits.length === 0 ? null : bits.join(" · ");
}

function AuditTab(props: {
  ruleId: string;
  client: ApiClient;
  processes: ReturnType<typeof useRuleLookups>["processes"];
  t: Translate;
}) {
  const { t, processes } = props;
  const config = useMemo<TableConfig<RuleAuditRow>>(
    () => ({
      screenId: WORK_RULE_DETAIL_SCREEN,
      getRowId: (row) => `${row.at ?? ""}-${row.act}`,
      defaultSort: { sort: "at", dir: "desc" },
      columns: [
        { key: "at", label: t("work.rules.audit.col.when"), identity: true, cell: (row) => <When value={row.at} withTime /> },
        { key: "by", label: t("work.rules.audit.col.who"), cell: (row) => row.by.name ?? <Dash /> },
        {
          key: "what",
          label: t("work.rules.audit.col.what"),
          cell: (row) => t(ACT_KEY[row.act] ?? "work.rules.audit.act.other"),
        },
        {
          key: "from",
          label: t("work.rules.audit.col.from"),
          cell: (row) => (row.act === "created" ? <Dash /> : auditSide(row.before, row.after, processes, t) ?? <Dash />),
        },
        {
          key: "to",
          label: t("work.rules.audit.col.to"),
          cell: (row) => (row.act === "created" ? <Dash /> : auditSide(row.after, row.before, processes, t) ?? <Dash />),
        },
      ],
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [processes],
  );
  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));
  const query = useQuery({
    queryKey: ["work", "rule", props.ruleId, "audit", state.page, state.per],
    queryFn: () => listRuleAudit(props.ruleId, { page: state.page, per: state.per }, props.client),
  });
  return (
    <div data-rule-audit="">
      <Note className="mb-3">{t("work.rules.audit.lede")}</Note>
      <DataTable<RuleAuditRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={query.data?.rows ?? []}
        totalRows={query.data?.total ?? null}
        loading={query.isPending}
        error={query.isError ? { reason: t("work.rules.audit.failed"), onRetry: () => void query.refetch() } : null}
        empty={{ title: t("work.rules.audit.empty"), helper: t("work.rules.audit.emptyHelper") }}
      />
    </div>
  );
}

// ── The page ──────────────────────────────────────────────────────────────

export interface RuleDetailPageProps {
  client?: ApiClient; // test seam
}

export function RuleDetailPage(props: RuleDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const params = useParams();
  const ruleId = params.ruleId ?? "";
  const [searchParams, setSearchParams] = useSearchParams();
  const tabs = ruleTabs(translate);
  const active = detailTabFrom(searchParams.get(TAB_PARAM), tabs);

  const ruleQuery = useQuery({
    queryKey: ["work", "rule", ruleId],
    queryFn: () => getRule(ruleId, client),
    enabled: ruleId !== "",
  });
  const lookups = useRuleLookups(client, active !== "jobs");
  const rule = ruleQuery.data;

  const toggle = useMutation({
    mutationFn: (next: boolean) => setRuleEnabled(ruleId, next, client),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ["work", "rule", ruleId] });
      void queryClient.invalidateQueries({ queryKey: ["work", "rules"] });
      fireToast(saved.enabled ? translate("work.rules.turnedOn") : translate("work.rules.turnedOff"));
    },
  });

  return (
    <div data-rule-detail="" data-screen={WORK_RULE_DETAIL_SCREEN}>
      <PageHeader
        backTo={{ to: tenantPath(WORK_RULES_ROUTE), label: translate("work.rules.title") }}
        title={rule?.name ?? translate("work.rules.page.loading")}
        // README ruling 16 — the actions top right; the drawing's three.
        secondaryActions={
          rule === undefined ? undefined : (
            <>
              <ButtonLink variant="secondary" data-rule-edit-head="" to={tenantPath(ruleEditPath(ruleId))}>
                {translate("work.rules.page.edit")}
              </ButtonLink>
              <ButtonLink variant="secondary" data-rule-duplicate="" to={tenantPath(ruleDuplicatePath(ruleId))}>
                {translate("work.rules.page.duplicate")}
              </ButtonLink>
              <Button
                variant="secondary"
                data-rule-toggle-head=""
                disabled={toggle.isPending}
                onClick={() => toggle.mutate(!rule.enabled)}
              >
                {rule.enabled ? translate("work.rules.turnOff") : translate("work.rules.turnOn")}
              </Button>
            </>
          )
        }
        tabs={tabs}
        activeTabId={active}
        tabsLabel={translate("work.rules.page.tabs")}
        onTabSelect={(tab) => {
          const next = new URLSearchParams(searchParams);
          next.set(TAB_PARAM, tab.id);
          setSearchParams(next, { replace: true });
        }}
      />
      {ruleQuery.isError && <Note data-rule-failed="">{translate("work.rules.page.failed")}</Note>}
      {rule !== undefined && active === "overview" && (
        <OverviewTab
          rule={rule}
          names={lookups.names}
          processes={lookups.processes}
          editHref={(step) => tenantPath(ruleEditPath(ruleId, step))}
          t={translate}
        />
      )}
      {rule !== undefined && active === "jobs" && <JobsTab ruleId={ruleId} client={client} t={translate} />}
      {rule !== undefined && active === "audit" && (
        <AuditTab ruleId={ruleId} client={client} processes={lookups.processes} t={translate} />
      )}
    </div>
  );
}

export default RuleDetailPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-168-BRC10 §5.6 · §7.3 rules reads · §20.1 · images 62, 63, 64
// generated: 2026-10-04 by lane RULES (round 5)
// checklist: A✔ B✔ C✔ D✔ E✔(routed in App.tsx; the list's row name, 👁 and the builder's commit point here) F✔ G✔ H=n/a
// gates: tsc · vitest src/features/work/rules · G31 (on route-b-migrated.txt) · G13 · i18n ×11
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
