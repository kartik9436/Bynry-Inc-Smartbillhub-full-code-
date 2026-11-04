// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — Stage 2 TRANSFORM, the column map (design B15 §4.2)
// Rules:    BR-MET-088 (the transform stage offers the REAL target columns, not
//           a fixed list of labels) · B14 rule 20 (one table type, body 13.5px
//           / header 12px — inherited from `PlainTable`) · B14 rule 8 (one
//           chevron style: the picker is the shared `.input` select) ·
//           B14 rule 21 (Tailwind)
// Impacts:  components/workflow/WorkflowRunner.tsx composes this.
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";

import type { MappingRow, MappingStatus, TargetColumn } from "./contract";
import { ABSENT } from "./kinds";
import * as WF from "./workflowKit";

/**
 * `SOURCE COLUMN │ SAMPLE VALUE │ MAPS TO │ TRANSFORM │ status`.
 *
 * ⚠ `targets` IS A PROP AND THAT IS BR-MET-088, VERBATIM: *"at the transform
 * screen - you can choose actual column you have from table"*. The picker is
 * populated from `GET /imports/{id}/columns` for THIS run's target, including
 * the tenant's own custom fields — so a column that exists can always be
 * mapped and a column that does not can never be offered. A hand-written label
 * list is the failure the rule names: it drifts from the schema, an operator
 * maps onto a label with nothing behind it, and the value is silently dropped.
 *
 * ⚠ `— ignore —` IS AN EXPLICIT CHOICE AND NOT THE EMPTY OPTION. "Ignored on
 * purpose" and "nobody mapped it" are different answers, and `MappingRow.status`
 * keeps them apart: `ignored` is a decision, `unmapped` is one nobody has taken.
 * Collapsing them is how a migration silently discards the customer's own key —
 * B15 §4.2A's `LEGACY_KEY` box costs reconciliation, re-import matching and the
 * answer to *"what happened to property 88214"*, none of it visible on the day.
 *
 * ⚠ ONE TABLE TYPE. This is `PlainTable` — the same small table 51 other sites
 * draw — so B14 rule 20's two tiers arrive by construction rather than by
 * diligence. The only classes this file adds are alignment and tabular figures.
 */
export interface MappingTableProps {
  rows: readonly MappingRow[];
  /** BR-MET-088 — the target's REAL columns, served per run. */
  targets: readonly TargetColumn[];
  /** Unique per runner instance, so two runners on one page keep distinct ids. */
  idPrefix: string;
  onTargetChange: (sourceColumn: string, targetColumn: string | null) => void;
  /**
   * ⛔ **CR-054 task 18 — THE MAPPING AS A STATEMENT, FOR A TARGET THAT CANNOT
   * REMAP.** The reads pipeline detects its mapping against ONE published
   * template on every upload and offers no remap route — BR-MET-032, verbatim:
   * *"ONE published template, validate THEN accept, no mapping memory"*. There
   * is no `PATCH .../mapping` anywhere in `apps/metering/api.py` for a read
   * batch.
   *
   * So the picker is not rendered on that mount. Drawing a live `<select>` over
   * an endpoint that does not exist is hard-won law 2 exactly — a control that
   * changes nothing, passing every test, on a screen a clerk trusts — and it is
   * the same failure `SourceCards` refuses when it draws SFTP disabled rather
   * than live.
   *
   * The other four columns are unchanged, which is the point: the clerk gains
   * the SAMPLE VALUE and the status chip without being handed a fake control.
   * Omitted (every existing caller), this component behaves exactly as before.
   */
  readOnly?: boolean;
}

/** Literal keys, so G18 can see every one of them as a call site. */
const STATUS_KEY: Record<MappingStatus, string> = {
  matched: "workflow.map.status.matched",
  ignored: "workflow.map.status.ignored",
  unmapped: "workflow.map.status.unmapped",
};

/** A12 §Semantic tokens: tone is MEANING. `unmapped` is a warning rather than a
 *  danger because a run can legitimately carry an unmapped column right up to
 *  the point a required one is missing — which is a RULE's job to say, at
 *  stage 3, not a chip's. */
const STATUS_TONE: Record<MappingStatus, StatusTone> = {
  matched: "success",
  ignored: "neutral",
  unmapped: "warning",
};

/** The sentinel the `— ignore —` option carries. It is not "" — an empty option
 *  value is what a browser sends for "nothing chosen", and this choice is the
 *  opposite of nothing chosen. */
const IGNORE_VALUE = "__ignore__";

/**
 * Plan U9 (PO 2026-09-30) — the targets in their served order, cut into runs
 * of one GROUP each. A target with no group (every non-asset target, and the
 * custom fields) is its own ungrouped run, so a flat list renders exactly as
 * before.
 */
export function groupTargets(
  targets: readonly TargetColumn[],
): [string | null, TargetColumn[]][] {
  const runs: [string | null, TargetColumn[]][] = [];
  for (const target of targets) {
    const group = target.group ?? null;
    const last = runs[runs.length - 1];
    if (last && last[0] === group) {
      last[1].push(target);
    } else {
      runs.push([group, [target]]);
    }
  }
  return runs;
}

/**
 * DEF-AST-8361 — the server declares `— ignore —` as a target too (BR-MET-088),
 * and this table always appends its own ignore option, so a served list drew
 * it twice. This table owns the one option; the served copy is dropped here.
 */
export function pickableTargets(targets: readonly TargetColumn[]): TargetColumn[] {
  return targets.filter((target) => target.id !== IGNORE_VALUE);
}

export function MappingTable({
  rows,
  targets,
  idPrefix,
  onTargetChange,
  readOnly = false,
}: MappingTableProps) {
  const { t } = useTranslation();
  const labelOf = (targetColumn: string | null): string =>
    targetColumn === null || targetColumn === IGNORE_VALUE
      ? t("workflow.map.ignore")
      : (targets.find((target) => target.id === targetColumn)?.label ?? targetColumn);
  return (
    <div className={WF.TABLE_WRAP} data-workflow="mapping">
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("workflow.map.col.source")}</th>
            <th scope="col">{t("workflow.map.col.sample")}</th>
            <th scope="col">{t("workflow.map.col.target")}</th>
            <th scope="col">{t("workflow.map.col.transform")}</th>
            <th scope="col">{t("workflow.map.col.status")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const id = `${idPrefix}-map-${row.source_column}`;
            return (
              <tr key={row.source_column} data-workflow-map-status={row.status}>
                <td>{row.source_column}</td>
                <td className={WF.CELL_MUTED}>{row.sample_value}</td>
                <td>
                  {readOnly ? (
                    <span data-workflow="map-target">{labelOf(row.target_column)}</span>
                  ) : (
                  <select
                    id={id}
                    className="input"
                    aria-label={t("workflow.map.rowLabel", { source: row.source_column })}
                    value={row.target_column === null ? IGNORE_VALUE : row.target_column}
                    onChange={(e) =>
                      onTargetChange(
                        row.source_column,
                        e.target.value === IGNORE_VALUE ? null : e.target.value,
                      )
                    }
                  >
                    {groupTargets(pickableTargets(targets)).map(([group, members]) =>
                      group === null ? (
                        members.map((target) => (
                          <option key={target.id} value={target.id}>
                            {target.label}
                          </option>
                        ))
                      ) : (
                        <optgroup key={group} label={group}>
                          {members.map((target) => (
                            <option key={target.id} value={target.id}>
                              {target.label}
                            </option>
                          ))}
                        </optgroup>
                      ),
                    )}
                    {/* Last, and always present: a tenant with a genuinely
                        meaningless column must be able to say so out loud. */}
                    <option value={IGNORE_VALUE}>{t("workflow.map.ignore")}</option>
                  </select>
                  )}
                </td>
                <td className={WF.CELL_MUTED}>{row.transform_label ?? ABSENT}</td>
                <td>
                  <StatusPill tone={STATUS_TONE[row.status]}>{t(STATUS_KEY[row.status])}</StatusPill>
                </td>
              </tr>
            );
          })}
        </tbody>
      </PlainTable>
    </div>
  );
}
