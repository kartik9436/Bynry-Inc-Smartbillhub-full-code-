// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 5, lane RULES — what a rule DOES, in three
//           panels: Trigger · Who hears · When it stalls. The builder's Review
//           (image 61) and one rule's Overview (image 62) draw it identically.
// Tasks:    P3.39 · P3.62 · P3.66 · P3.67
// Rules:    B14 rule 43 (one component, two screens) · rule 20 (the kit's
//           table — `TableArray`, read-only) · rule 31 (names, never ids) ·
//           rule 33 (labels ≤ 3 words; no rationale) · `BR-NOT-021` as
//           narrowed for Work (PO 2026-10-04: *Also tell* ADDS people)
// ───────────────────────────────────────────────────────
import { Fragment } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";
import { Dash } from "@/features/customers/customersShared";

import type { RuleProcesses } from "./ruleEndpoints";
import {
  assignWord,
  channelWord,
  escalationWord,
  eventWord,
  notifyWhenWord,
  notifyWhoWord,
  processWord,
  settingsWords,
  whoIsToldWord,
} from "./ruleModel";
import type {
  EscalationDraft,
  NotifyDraft,
  RuleDraft,
  RuleNames,
  Translate,
  TriggerDraft,
} from "./ruleModel";

/** Which builder step owns each panel — the ✎ Edit target. */
export const RULE_SUMMARY_STEP = { trigger: 1, notify: 2, stalls: 2 } as const;

export type RuleSummaryEdit =
  | { kind: "link"; href: (step: number) => string }
  | { kind: "jump"; onJump: (step: number) => void };

/**
 * A translated sentence with some of its values in bold — *Raises **Meter
 * exchange — residential** at **Low** priority.* The catalogue owns the whole
 * sentence and its word order (B14 rule 35); this only finds the values in it.
 */
export function Emphasised(props: {
  t: Translate;
  i18nKey: string;
  values: Record<string, string | number>;
  strong: readonly string[];
}): ReactNode {
  const marks: Record<string, string | number> = { ...props.values };
  for (const name of props.strong) marks[name] = `\u0001${name}\u0001`;
  const text = props.t(props.i18nKey, marks);
  const parts = text.split("\u0001");
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 && props.strong.includes(part) ? (
          <strong key={index}>{String(props.values[part] ?? "")}</strong>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        ),
      )}
    </>
  );
}

function EditAction(props: { edit: RuleSummaryEdit | undefined; step: number; section: string }) {
  const { t } = useTranslation();
  if (props.edit === undefined) return null;
  const label = t("work.rules.summary.editSection", { section: props.section });
  const text = t("work.rules.summary.edit");
  const className =
    "bg-transparent p-0 text-sm font-semibold text-accent hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent";
  if (props.edit.kind === "link") {
    return (
      <Link className={className} to={props.edit.href(props.step)} aria-label={label} data-rule-edit={props.step}>
        {text}
      </Link>
    );
  }
  const onJump = props.edit.onJump;
  return (
    <button type="button" className={className} aria-label={label} onClick={() => onJump(props.step)} data-rule-edit={props.step}>
      {text}
    </button>
  );
}

/** The `#` cell. `TableArray` draws no number column of its own, and these
 *  three tables are drawn numbered (images 57, 59, 61, 62). */
const numberColumn = <Row,>(): TableArrayColumn<Row> => ({
  key: "seq",
  label: "#",
  cell: (_row, index) => <span className="tabular-nums">{index + 1}</span>,
});

export interface RuleSummaryProps {
  draft: RuleDraft;
  processes: RuleProcesses | undefined;
  names: RuleNames;
  edit?: RuleSummaryEdit;
}

/** The three panels — Trigger, Who hears, When it stalls. */
export function RuleSummary(props: RuleSummaryProps) {
  const { t } = useTranslation();
  const tr: Translate = (key, params) => t(key, params);
  const { draft, processes, names, edit } = props;

  const triggerColumns: TableArrayColumn<TriggerDraft>[] = [
    numberColumn<TriggerDraft>(),
    {
      key: "when",
      label: tr("work.rules.col.whenThisHappens"),
      cell: (row) => processWord(row.kind, processes, tr),
    },
    {
      key: "settings",
      label: tr("work.rules.col.settings"),
      cell: (row) => settingsWords(row, processes, names, tr),
    },
  ];
  const notifyColumns: TableArrayColumn<NotifyDraft>[] = [
    { key: "when", label: tr("work.rules.col.when"), cell: (row) => (row.when === "" ? <Dash /> : notifyWhenWord(row.when, tr)) },
    { key: "who", label: tr("work.rules.col.whoHears"), cell: (row) => (row.who === "" ? <Dash /> : notifyWhoWord(row.who, tr)) },
    { key: "message", label: tr("work.rules.col.message"), cell: (row) => (row.eventKey === "" ? <Dash /> : eventWord(row.eventKey, tr)) },
    {
      key: "how",
      label: tr("work.rules.col.how"),
      cell: (row) => {
        const channels = names.channels[row.eventKey] ?? [];
        return channels.length === 0 ? <Dash /> : channels.map((channel) => channelWord(channel, tr)).join(" · ");
      },
    },
  ];
  const stallColumns: TableArrayColumn<EscalationDraft>[] = [
    { key: "if", label: tr("work.rules.col.if"), cell: (row) => escalationWord(row.kind, tr) },
    {
      key: "after",
      label: tr("work.rules.col.after"),
      cell: (row) => tr("work.rules.hours", { count: Number.parseInt(row.afterHours, 10) || 0 }),
    },
    { key: "told", label: tr("work.rules.col.whoIsTold"), cell: (row) => whoIsToldWord(row, names, tr) },
    {
      key: "message",
      label: tr("work.rules.col.message"),
      cell: (row) => {
        const event = processes?.escalation_events[row.kind];
        return event === undefined ? <Dash /> : eventWord(event, tr);
      },
    },
  ];

  const triggerTitle = tr("work.rules.builder.step.trigger");
  const notifyTitle = tr("work.rules.summary.whoHears");
  const stallsTitle = tr("work.rules.summary.whenItStalls");

  // ⚠ **EACH PANEL IS THE KIT'S `TableArray` ITSELF, NOT A TABLE INSIDE A
  // PANEL.** `TableArray` draws its own panel; wrapping it in a second one
  // drew a box in a box. The ✎ Edit sits in the heading's right-hand slot —
  // where images 61 and 62 draw it.
  return (
    <div className="flex flex-col gap-4" data-rule-summary="">
      <TableArray<TriggerDraft>
        readOnly
        title={triggerTitle}
        fact={<EditAction edit={edit} step={RULE_SUMMARY_STEP.trigger} section={triggerTitle} />}
        lead={<p className="m-0 text-base text-text">{tr("work.rules.summary.anyRaises")}</p>}
        collection="rule-summary-triggers"
        columns={triggerColumns}
        rows={draft.triggers}
        rowKey={(row) => row.key}
        emptyText={tr("work.rules.summary.noTrigger")}
      >
        <p className="mt-3 mb-0 text-base text-text" data-rule-goes-to="">
          <Emphasised
            t={tr}
            i18nKey="work.rules.summary.goesTo"
            values={{ who: assignWord(draft.assignTo, names, tr) }}
            strong={["who"]}
          />
        </p>
      </TableArray>

      <TableArray<NotifyDraft>
        readOnly
        title={notifyTitle}
        fact={<EditAction edit={edit} step={RULE_SUMMARY_STEP.notify} section={notifyTitle} />}
        collection="rule-summary-notify"
        columns={notifyColumns}
        rows={draft.notify}
        rowKey={(row) => row.key}
        emptyText={tr("work.rules.summary.nobodyHears")}
      />

      <TableArray<EscalationDraft>
        readOnly
        title={stallsTitle}
        fact={<EditAction edit={edit} step={RULE_SUMMARY_STEP.stalls} section={stallsTitle} />}
        collection="rule-summary-stalls"
        columns={stallColumns}
        rows={draft.escalations}
        rowKey={(row) => row.key}
        emptyText={tr("work.rules.summary.noEscalation")}
      />
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-168-BRC10 §5.6 R10–R12 · images 61, 62
// generated: 2026-10-04 by lane RULES (round 5)
// checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
// gates: tsc · vitest src/features/work/rules · G31 (on route-b-migrated.txt)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
