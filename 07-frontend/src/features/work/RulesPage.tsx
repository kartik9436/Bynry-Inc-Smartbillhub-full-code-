// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-037 (EP-WRK-07) — rules that raise work orders on their
//           own. Screen: image 56 (`05-prototype/work-backoffice-2026-10-04`),
//           r10's `WRK-06`.
// Change:   CR-168-BRC10 round 5, lane RULES — a permanent *+ New rule* top
//           right, a search that searches, LAST FIRED, and open · edit ·
//           duplicate on every row.
// Tasks:    P3.16 · P3.18 · P3.60 · P3.63 · `DEF-WRK-9564` · `DEF-WRK-9573`
// Rules:    BR-WRK-033 (a rule that is off raises nothing; the list shows this
//           month's count) · README ruling 16 (actions top right) · B14 rule 2
//           (one page header) · rule 11 (the consequence box) · rule 15 (icons
//           for row actions) · rule 20 (one table type) · rule 21 (Tailwind;
//           on route-b-migrated.txt) · rule 31 (no database id is a visible
//           value) · rule 33 · rule 36 (the kit)
// Tests:    src/features/work/rules/cr168Rules.dom.test.tsx ·
//           src/features/work/RulesPage.test.tsx ·
//           src/features/work/recordedShapes.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS SCREEN IS WHERE A UTILITY DECIDES WHAT HAPPENS WHILE NOBODY IS
// THERE.** Every other list in this module shows work somebody asked for; this
// one shows standing instructions a machine carries out at 02:00, and what a
// supervisor needs at a glance is which of them are ON.
//
// ⚠ **THE ENABLED SWITCH IS NOT DANGER-TIER.** Switching a rule off destroys
// nothing — the sweep's memory of what it has raised is KEPT, so a rule turned
// off in December and on in March does not re-raise every subject it has ever
// seen (`BR-WRK-033`).
//
// ⚠ **`ruleCanRaise` IS GONE, AND WITH IT THE DASH IT DREW.** It hid THIS
// MONTH for four of five sources because the raise stamped a module name the
// order table refused (`DEF-WRK-4096`). Lane SRV-4 fixed the stamp (2.512.0),
// so every count is now a fact; the one thing that still cannot raise is a
// trigger missing a setting (`incomplete`), and that row says so with a dash.
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button, ButtonLink } from "@/components/Button";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { useTenantRegional } from "@/components/TenantRegional";
import { useToast } from "@/components/Toast";
import { CopyIcon, EyeIcon, PencilIcon } from "@/components/icons";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";
import { useTenantPath } from "@/routing/tenantPath";

import { WORK_RULE_BUILDER_ROUTE, ruleDuplicatePath, ruleEditPath } from "./RuleBuilder";
import { ruleDetailPath } from "./RuleDetailPage";
import { useWorkTabs, WORK_RULES_ROUTE } from "./WorkShell";
import { getRuleProcesses, listRules, setRuleEnabled } from "./rules/ruleEndpoints";
import type { RuleProcesses, WorkRule } from "./rules/ruleEndpoints";
import { processWord, ruleModules } from "./rules/ruleModel";
import type { Translate } from "./rules/ruleModel";

/** r10's own badge for the rules screen — image 56 ↔ `WRK-06`. */
export const WORK_RULES_SCREEN = "WRK-06";

export { WORK_RULE_BUILDER_ROUTE, WORK_RULES_ROUTE };

/**
 * Image 56's columns, in the drawing's order:
 * RULE · SOURCE MODULE · TRIGGER · TEMPLATE RAISED · PRIORITY · THIS MONTH ·
 * LAST FIRED · ENABLED · ACTIONS.
 *
 * Exported so a test can read the column set with no DOM, and assert that no
 * database id is among the visible values (B14 rule 31).
 */
export const RULE_COLUMNS = [
  "name",
  "source_module",
  "trigger_kind",
  "template",
  "priority",
  "this_month",
  "last_fired",
  "enabled",
  "actions",
] as const;

function LastFired(props: { rule: WorkRule; t: Translate }) {
  const regional = useTenantRegional();
  const { rule, t } = props;
  if (rule.last_fired_at === null) return <span>{t("work.rules.never")}</span>;
  return (
    <span className="flex flex-col">
      {regional === null ? (
        <span className="tabular-nums">{rule.last_fired_at.slice(0, 10)}</span>
      ) : (
        <DateCell value={rule.last_fired_at} timeZone={regional.timeZone} dateFormat={regional.dateFormat} />
      )}
      <span className="text-sm text-neutral-700" data-jobs-raised="">
        {t("work.rules.jobsRaised", { count: rule.jobs_raised })}
      </span>
    </span>
  );
}

export function rulesTableConfig(
  t: Translate,
  processes: RuleProcesses | undefined,
  cells: {
    name: (row: WorkRule) => ReactNode;
    toggle: (row: WorkRule) => ReactNode;
    actions: (row: WorkRule) => ReactNode;
  },
): TableConfig<WorkRule> {
  return {
    screenId: WORK_RULES_SCREEN,
    getRowId: (row) => row.id,
    // P3.18 — the server searches the rule's name, its template and its
    // process words (`GET /work/rules?q=`); the box is wired to it.
    searchFields: ["name", "template", "trigger"],
    searchPlaceholder: "work.rules.search",
    defaultSort: { sort: "name", dir: "asc" },
    columns: [
      { key: "name", label: t("work.rules.col.rule"), identity: true, cell: cells.name },
      { key: "source_module", label: t("work.rules.col.source"), cell: (row) => ruleModules(row, t) || <Dash /> },
      {
        key: "trigger_kind",
        label: t("work.rules.col.trigger"),
        cell: (row) =>
          row.triggers.length === 0 ? (
            <Dash />
          ) : (
            <span className="flex flex-col">
              {row.triggers.map((trigger) => (
                <span key={trigger.seq}>{processWord(trigger.kind, processes, t)}</span>
              ))}
            </span>
          ),
      },
      { key: "template", label: t("work.rules.col.template"), cell: (row) => row.template.name ?? <Dash /> },
      {
        key: "priority",
        label: t("work.rules.col.priority"),
        // NULL is a DASH and never *Normal*: a rule naming no priority lets
        // the template's own default stand.
        cell: (row) => row.priority?.name ?? <Dash />,
      },
      {
        key: "this_month",
        label: t("work.rules.col.thisMonth"),
        numeric: true,
        // A trigger missing a setting raises nothing; a zero there would read
        // as *nothing needed raising*.
        cell: (row) => (row.incomplete.length > 0 ? <Dash /> : row.this_month),
      },
      { key: "last_fired", label: t("work.rules.col.lastFired"), cell: (row) => <LastFired rule={row} t={t} /> },
      { key: "enabled", label: t("work.rules.col.enabled"), cell: cells.toggle },
      { key: "actions", label: t("work.rules.col.actions"), cell: cells.actions },
    ],
  };
}

export function RulesPage(props: { client?: ApiClient } = {}) {
  const client = props.client ?? api;
  const { t } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const fireToast = useToast();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();

  const toggle = useMutation({
    mutationFn: (row: WorkRule) => setRuleEnabled(row.id, !row.enabled, client),
    onSuccess: (row) => {
      void queryClient.invalidateQueries({ queryKey: ["work", "rules"] });
      fireToast(row.enabled ? translate("work.rules.turnedOn") : translate("work.rules.turnedOff"));
    },
  });

  const processes = useQuery({
    queryKey: ["work", "rules", "processes"],
    queryFn: () => getRuleProcesses(client),
  });

  const config = useMemo(
    () =>
      rulesTableConfig(translate, processes.data, {
        name: (row) => <InlineLinkTo to={tenantPath(ruleDetailPath(row.id))}>{row.name}</InlineLinkTo>,
        toggle: (row) => (
          <span className="inline-flex items-center gap-2">
            <StatusPill tone={row.enabled ? "success" : "neutral"}>
              {row.enabled ? translate("work.rules.on") : translate("work.rules.off")}
            </StatusPill>
            <Button size="sm" variant="ghost" data-rule-toggle={row.id} onClick={() => toggle.mutate(row)}>
              {row.enabled ? translate("work.rules.turnOff") : translate("work.rules.turnOn")}
            </Button>
          </span>
        ),
        // B14 rule 15 — ICONS with accessible names: open, edit, duplicate
        // (image 56's three; P3.63).
        actions: (row) => (
          <RowActions>
            <RowActionLink
              label={translate("work.rules.action.open", { name: row.name })}
              icon={<EyeIcon />}
              to={tenantPath(ruleDetailPath(row.id))}
            />
            <RowActionLink
              label={translate("work.rules.action.edit", { name: row.name })}
              icon={<PencilIcon />}
              to={tenantPath(ruleEditPath(row.id))}
            />
            <RowActionLink
              label={translate("work.rules.action.duplicate", { name: row.name })}
              icon={<CopyIcon />}
              to={tenantPath(ruleDuplicatePath(row.id))}
            />
          </RowActions>
        ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, processes.data],
  );
  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  const query = useQuery({
    queryKey: ["work", "rules", state.q, state.page, state.per],
    queryFn: () => listRules({ q: state.q, page: state.page, per: state.per }, client),
  });
  // The consequence box says what runs tonight, which a search does not
  // change — so it counts the UNSEARCHED page (the same query as the table's
  // whenever the box is empty).
  const unsearched = useQuery({
    queryKey: ["work", "rules", "", state.page, state.per],
    queryFn: () => listRules({ page: state.page, per: state.per }, client),
  });

  const rows = query.data?.rows ?? [];
  const onCount = (unsearched.data?.rows ?? []).filter((row) => row.enabled).length;
  const strip = useWorkTabs(translate("work.rules.lede"));

  return (
    <section aria-label={translate("work.rules.title")} data-screen={WORK_RULES_SCREEN}>
      {/* B14 rule 2 — ONE page header, carrying the module's tab strip and,
          top right, the permanent create (README ruling 16, P3.16). */}
      <PageHeader
        title={translate("work.rules.title")}
        secondaryActions={
          <ButtonLink variant="primary" data-new-rule="" to={tenantPath(WORK_RULE_BUILDER_ROUTE)}>
            {translate("work.rules.new")}
          </ButtonLink>
        }
        {...strip}
      />

      {/* B14 rule 11 + rule 32 — ONE sentence: what runs tonight. */}
      <ConsequenceBox
        tone="check"
        title={translate("work.rules.consequenceTitle")}
        body={translate("work.rules.consequenceBody", { on: onCount })}
        data-consequence="work-rules"
      />

      <DataTable<WorkRule>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={query.data?.total ?? null}
        loading={query.isPending}
        error={
          query.isError
            ? { reason: translate("work.rules.loadFailed"), onRetry: () => void query.refetch() }
            : null
        }
        empty={{
          title: translate("work.rules.empty.title"),
          helper: translate("work.rules.empty.helper"),
          ctaLabel: translate("work.rules.empty.cta"),
          onCta: () => navigate(tenantPath(WORK_RULE_BUILDER_ROUTE)),
        }}
      />
    </section>
  );
}

export default RulesPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-037@5e48ae29 (EP-WRK-07) · CR-168-BRC10 §5.6 R1–R4 · image 56
// generated: 2026-09-05 by the CR-070 wave M build lane · rebuilt 2026-10-04 by lane RULES (round 5)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · vitest · G31 (rule 21 — this file is on route-b-migrated.txt) · i18n ×11
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
