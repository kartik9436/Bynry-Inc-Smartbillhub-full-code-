// ── Trace ──────────────────────────────────────────────
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/inventory.md §1.4 — the
//           summary aside, growing per step (images 01–08, 25–36)
// Plan:     15-bulk-bill-run-build-plan.md F6 (Run to start with ServiceChips)
// Rules:    B14 rules 21, 31, 33, 43, 44
// ───────────────────────────────────────────────────────
/**
 * THE RUN, AT A GLANCE — the aside on Scope, Sign off and Send (Check is full
 * width, changes row 36). Its blocks appear as the run earns them: counts and
 * services on Scope; the Check result and the draft total once priced.
 *
 * A fact not yet valid reads `—` (image 05) — that is the drawn answer for a
 * field the clerk has not filled, not an absent figure.
 */
import type { ReactNode } from "react";

import type { ScopePreview } from "@/api/bulkRunEndpoints";
import { Panel } from "@/components/Panel";
import { ServiceChips } from "@/components/ServiceChips";
import { StatusPill } from "@/components/StatusPill";

import { AsideRow, Kicker, count, day, money, span } from "./bulkRunShared";
import type { RunFormat } from "./bulkRunShared";
import { periodDays } from "./ScopeStep";

export interface RunFacts {
  runNo: string | null;
  label: string;
  cycleName: string | null;
  periodStart: string;
  periodEnd: string;
  billDate: string;
  dueDays: string;
  dueDate: string | null;
  templateName: string | null;
}

export interface CheckResult {
  ready: number;
  decision: number;
  blocked: number;
}

function Block(props: { children: ReactNode; name: string }) {
  return (
    <div className="mt-4 flex flex-col gap-2 border-t border-divider pt-4" data-aside-block={props.name}>
      {props.children}
    </div>
  );
}

function orDash(value: string | null | undefined): string {
  return value === null || value === undefined || value === "" ? "—" : value;
}

/** DEF-BIL-8691 — the last run's value (D1 01, *Last run total*), read from the
 *  same paged Previous runs read the panel draws; `—` when it is not on it. */
function lastRunTotal(preview: ScopePreview | null, fmt: RunFormat): string {
  const last = preview?.previous_run ?? null;
  if (last === null) return "—";
  const row = (preview?.previous_runs?.results ?? []).find((one) => one.id === last.run_id) ?? null;
  return row === null || row.value === null || row.value === undefined
    ? "—"
    : money(row.value, { ...fmt, currency: row.value_currency ?? fmt.currency });
}

export function RunSummaryCard(props: {
  facts: RunFacts;
  /** Scope only: refusals and warnings, services, what the run covers. */
  scope?: { preview: ScopePreview | null; services: readonly string[] | null; refusalFields: ReadonlySet<string> };
  check?: CheckResult | null;
  drafts?: { total: string | null; bills: number | null; sent?: boolean } | null;
  fmt: RunFormat;
}) {
  const { facts, fmt } = props;
  const { t } = fmt;
  const bad = props.scope?.refusalFields ?? new Set<string>();
  const valid = (field: string, value: string) => (bad.has(field) ? "—" : orDash(value));
  const days = periodDays(facts.periodStart, facts.periodEnd);
  const period =
    bad.has("period_start") || bad.has("period_end") || days === null
      ? "—"
      : t("billing.bulkRun.aside.period", { period: span(facts.periodStart, facts.periodEnd, fmt), days });
  const preview = props.scope?.preview ?? null;
  const counts = preview?.counts ?? null;
  const last = preview?.previous_run ?? null;
  return (
    <Panel as="aside" aria-label={t("billing.bulkRun.aside.label")} data-run-summary="">
      <Kicker as="div">
        {facts.runNo === null
          ? t("billing.bulkRun.aside.toStart")
          : t("billing.bulkRun.aside.run", { run: facts.runNo })}
      </Kicker>
      <div className="mt-3 flex flex-col gap-2">
        <AsideRow label={t("billing.bulkRun.scope.field.label")} name="label">{valid("label", facts.label)}</AsideRow>
        <AsideRow label={t("billing.bulkRun.scope.field.cycle_id")} name="cycle">{orDash(facts.cycleName)}</AsideRow>
        <AsideRow label={t("billing.bulkRun.aside.periodLabel")} name="period">{period}</AsideRow>
        <AsideRow label={t("billing.bulkRun.scope.field.bill_date")} name="bill-date">
          {bad.has("bill_date") ? "—" : day(facts.billDate, fmt)}
        </AsideRow>
        <AsideRow label={t("billing.bulkRun.scope.field.due_days")} name="due-days">{valid("due_days", facts.dueDays)}</AsideRow>
        <AsideRow label={t("billing.bulkRun.aside.due")} name="due">
          {bad.has("due_days") || bad.has("bill_date") ? "—" : day(facts.dueDate, fmt)}
        </AsideRow>
        <AsideRow label={t("billing.bulkRun.aside.template")} name="template">
          {bad.has("template_id") ? "—" : orDash(facts.templateName)}
        </AsideRow>
      </div>

      {props.scope !== undefined && (
        <>
          <Block name="problems">
            <AsideRow label={t("billing.bulkRun.aside.toFix")} name="to-fix">
              <StatusPill tone={(preview?.refusals.length ?? 0) > 0 ? "danger" : "success"}>
                {count(preview?.refusals.length ?? 0)}
              </StatusPill>
            </AsideRow>
            <AsideRow label={t("billing.bulkRun.aside.warnings")} name="warnings">
              <StatusPill tone={(preview?.warnings.length ?? 0) > 0 ? "warning" : "neutral"}>
                {count(preview?.warnings.length ?? 0)}
              </StatusPill>
            </AsideRow>
          </Block>
          {(props.scope.services ?? []).length > 0 && (
            <Block name="services">
              <Kicker as="div">{t("billing.bulkRun.aside.services")}</Kicker>
              <ServiceChips services={props.scope.services} t={t} />
            </Block>
          )}
          {counts !== null && (
            <Block name="covers">
              <AsideRow label={t("billing.bulkRun.aside.units")}>{count(counts.units_in_cycle)}</AsideRow>
              <AsideRow label={t("billing.bulkRun.aside.accounts")}>{count(counts.accounts_to_bill)}</AsideRow>
              <AsideRow label={t("billing.bulkRun.aside.regularMaster")}>
                {`${count(counts.regular_accounts)} · ${count(counts.master_accounts)}`}
              </AsideRow>
              <AsideRow label={t("billing.bulkRun.aside.meters")}>{count(counts.meters)}</AsideRow>
              <AsideRow label={t("billing.bulkRun.aside.routes")}>{count(preview?.cycle?.routes ?? null)}</AsideRow>
            </Block>
          )}
          {preview !== null && preview.cycle !== null && (
            <Block name="last-run">
              <AsideRow label={t("billing.bulkRun.aside.lastRun")}>
                {last === null ? "—" : `${last.run_no ?? ""} · ${span(last.period_start, last.period_end, fmt)}`}
              </AsideRow>
              <AsideRow label={t("billing.bulkRun.aside.lastRunTotal")} name="last-run-total">
                {lastRunTotal(preview, fmt)}
              </AsideRow>
              <AsideRow label={t("billing.bulkRun.aside.followsOn")}>
                {preview.continuity.state === "unknown" ? (
                  "—"
                ) : (
                  <StatusPill
                    tone={
                      preview.continuity.state === "continuous"
                        ? "success"
                        : preview.continuity.state === "gap"
                          ? "warning"
                          : preview.continuity.state === "overlap"
                            ? "danger"
                            : "neutral"
                    }
                  >
                    {t(`billing.bulkRun.continuity.${preview.continuity.state}`)}
                  </StatusPill>
                )}
              </AsideRow>
            </Block>
          )}
        </>
      )}

      {props.check !== undefined && props.check !== null && (
        <Block name="check">
          <AsideRow label={t("billing.bulkRun.aside.ready")}>
            <StatusPill tone="success">{count(props.check.ready)}</StatusPill>
          </AsideRow>
          <AsideRow label={t("billing.bulkRun.aside.decision")}>
            <StatusPill tone="warning">{count(props.check.decision)}</StatusPill>
          </AsideRow>
          <AsideRow label={t("billing.bulkRun.aside.blocked")}>
            <StatusPill tone="danger">{count(props.check.blocked)}</StatusPill>
          </AsideRow>
        </Block>
      )}

      {props.drafts !== undefined && props.drafts !== null && (
        <Block name="drafts">
          <p className="m-0 font-heading text-metric-lg font-semibold" data-aside-total="">
            {money(props.drafts.total, fmt)}
          </p>
          <p className="m-0 text-base text-neutral-700">
            {/* DEF-BIL-9008 — once sent they are bills sent, never "draft bills". */}
            {t(props.drafts.sent ? "billing.bulkRun.aside.sentBills" : "billing.bulkRun.aside.draftBills", {
              count: props.drafts.bills ?? 0,
            })}
          </p>
        </Block>
      )}
    </Panel>
  );
}
