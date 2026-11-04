// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — Stage 3 VALIDATE, `RULES THAT RAN` (design B15 §4.3)
// Rules:    BR-MET-090 (severity and action are TWO columns, and a run stores
//           the rules AS THEY WERE) · BR-MET-091 (a rule the product cannot
//           evaluate is DECLARED and marked unavailable, never omitted) ·
//           B14 rule 20 (one table type) · B14 rule 21 (Tailwind)
// Impacts:  components/workflow/WorkflowRunner.tsx composes this.
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";

import type { RuleResult, RuleSeverity } from "./contract";
import { ABSENT } from "./kinds";
import * as WF from "./workflowKit";

/**
 * `RULE │ SEVERITY │ HITS │ ACTION`, severity as a chip.
 *
 * ⚠ A RULE MARKED `available: false` RENDERS **WITH ITS REASON**, NOT OMITTED —
 * BR-MET-091. r10's only ERROR-severity rule on a premises import is *"Address
 * must geocode inside the service territory"*, and this product has no geocoder
 * and no service-territory boundary. Dropping the row would leave a premises
 * import with NO error-severity rule at all while the stage above it promises
 * *"errors block the load"* — a screen listing three rules where four were
 * expected tells the operator nothing, and the promise becomes one the product
 * cannot keep. So the row is listed, chipped `Cannot run`, and says why.
 *
 * ⚠ SEVERITY AND ACTION ARE TWO COLUMNS AND THAT IS DELIBERATE (BR-MET-090).
 * r10's own table proves why: *"Premise type exists in the lookup table ·
 * **Warning** · 2 · **Default to Residential**"* is a WARNING that performs a
 * WRITE the operator never asked for. Two premises silently become Residential
 * and price as Residential. Showing the pair side by side is what makes that
 * visible before the load rather than after it.
 *
 * ⚠ HITS ARE RIGHT-ALIGNED AND TABULAR (B15 §9 note 6). An unavailable rule
 * shows an em-dash and not `0`: zero hits means the rule ran and found nothing,
 * which is the opposite of what happened.
 */
export interface RuleResultsTableProps {
  caption: string;
  rules: readonly RuleResult[];
  /** Rendered when the list is empty — B14 rule 17, every list says what is
   *  missing. A validate stage with no rules at all is a real state and a
   *  worrying one. */
  emptyMessage: string;
}

/** Literal keys, so G18 sees every one as a call site. */
const SEVERITY_KEY: Record<RuleSeverity, string> = {
  error: "workflow.rules.severity.error",
  warning: "workflow.rules.severity.warning",
  pass: "workflow.rules.severity.pass",
  off: "workflow.rules.severity.off",
};

const SEVERITY_TONE: Record<RuleSeverity, StatusTone> = {
  error: "danger",
  warning: "warning",
  pass: "success",
  off: "neutral",
};

export function RuleResultsTable({ caption, rules, emptyMessage }: RuleResultsTableProps) {
  const { t } = useTranslation();
  return (
    <div className={WF.TABLE_WRAP} data-workflow="rules">
      <PlainTable>
        <caption className={WF.TABLE_CAPTION}>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">{t("workflow.rules.col.rule")}</th>
            <th scope="col">{t("workflow.rules.col.severity")}</th>
            <th scope="col" className={WF.NUM_HEAD}>
              {t("workflow.rules.col.hits")}
            </th>
            <th scope="col">{t("workflow.rules.col.action")}</th>
          </tr>
        </thead>
        <tbody>
          {rules.length === 0 && (
            <tr>
              <td colSpan={4}>{emptyMessage}</td>
            </tr>
          )}
          {rules.map((rule) => (
            <tr
              key={rule.code}
              data-workflow-rule={rule.code}
              data-available={rule.available ? "true" : "false"}
            >
              <td>
                {rule.sentence}
                {!rule.available && rule.unavailable_reason !== null && (
                  <span className={WF.CELL_REASON} data-workflow="rule-reason">
                    {rule.unavailable_reason}
                  </span>
                )}
              </td>
              <td>
                {rule.available ? (
                  <StatusPill tone={SEVERITY_TONE[rule.severity]}>
                    {t(SEVERITY_KEY[rule.severity])}
                  </StatusPill>
                ) : (
                  <StatusPill tone="neutral">{t("workflow.rules.unavailable")}</StatusPill>
                )}
              </td>
              <td className={WF.NUM_CELL}>{rule.available ? rule.hits : ABSENT}</td>
              <td className={WF.CELL_MUTED}>{rule.action_label}</td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </div>
  );
}
