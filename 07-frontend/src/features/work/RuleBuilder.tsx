// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 5, lane RULES — the rule builder, THREE steps
//           on the shared `WizardFrame`: Trigger · Notify · Review (images 57,
//           59, 61). Images 58 (*Assignment logic*) and 60 (*Escalation*) are
//           the two steps the 26 Sep ruling RETIRES; their one control each
//           lives on Trigger (*Give the job to*) and Notify (*When it
//           stalls*) — CR-168 §5.6 R9, R11.
// Tasks:    P3.17 (edit a rule) · P3.19 (the WizardFrame and the kit,
//           `DEF-WRK-5066`) · P3.37 (messages from Notifications, no second
//           copy) · P3.39 (the Review states tonight's count) · P3.64 (three
//           steps) · P3.65 (several triggers) · P3.66 · P3.67 · R8 (the
//           template and priority under the rule name, CR-168 §5.7)
// Rules:    README ruling 10 (*"every process should be able to set from the
//           form"*) · B14 rules 21, 31, 33, 36, 38, 41–44 · `BR-NOT-017` ·
//           `BR-NOT-021` as narrowed for Work (PO 2026-10-04) · `BR-WRK-033`
// Tests:    src/features/work/rules/cr168Rules.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE RULE IS WRITTEN AT THE LAST STEP AND NOWHERE EARLIER.** A rule saved
// at step 1 would sit on the list looking exactly like a working one; a rule
// has no draft state (`BR-WRK-033`). The Review states what it WILL do —
// tonight's count from `POST /work/rules/preview`, which writes nothing.
//
// ⚠ **ONE COMPONENT, THREE ADDRESSES.** `…/rules/new` writes a new rule,
// `…/rules/new?from=<id>` is *Duplicate* (the rule's own settings, a new
// name, a new row), `…/rules/<id>/edit` re-opens one. The step is `?step=`
// URL state, so ✎ Edit on the rule's page opens the step that owns the panel.
//
// NOT INSIDE `WorkShell`: a wizard sits under its own ← (`DEF-WRK-3724`).
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { CheckDropdown } from "@/components/CheckDropdown";
import { SelectField, TextField } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { CellNumber, CellSelect, CellStatic, CellText, CellTick, TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";
import { Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";
import { WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { Dash } from "@/features/customers/customersShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { WORK_RULES_ROUTE } from "./WorkShell";
import { createRule, getRule, previewRule, updateRule } from "./rules/ruleEndpoints";
import type { RuleProcess, RuleProcessParam } from "./rules/ruleEndpoints";
import { RuleSummary } from "./rules/RuleSummary";
import {
  RULE_BUILDER_STEPS,
  channelWord,
  draftFromRule,
  emptyRuleDraft,
  escalationWord,
  eventWord,
  newEscalation,
  newNotify,
  newTrigger,
  notifyStepVerdict,
  notifyWhenWord,
  notifyWhoWord,
  processWord,
  ruleWriteFrom,
  triggerStepVerdict,
  whoIsToldWord,
} from "./rules/ruleModel";
import type {
  EscalationDraft,
  NotifyDraft,
  ParamValue,
  RuleDraft,
  Translate,
  TriggerDraft,
} from "./rules/ruleModel";
import { useRuleLookups } from "./rules/useRuleLookups";
import type { RuleLookups } from "./rules/useRuleLookups";

/** The builder's badge — r10's `WRK-13` (`screenIds.ts`). */
export const WORK_RULE_BUILDER_SCREEN = "WRK-13";

/** Tenant-relative, like every route constant in this module (`DEF-WRK-4051`). */
export const WORK_RULE_BUILDER_ROUTE = `${WORK_RULES_ROUTE}/new`;
export const WORK_RULE_EDIT_ROUTE = `${WORK_RULES_ROUTE}/:ruleId/edit`;

/** Where *Edit* goes — one function, so the list, the rule's page and its
 *  panels cannot disagree about the address (law 5). */
export function ruleEditPath(ruleId: string, step?: number): string {
  const base = `${WORK_RULES_ROUTE}/${ruleId}/edit`;
  return step === undefined ? base : `${base}?step=${step}`;
}

/** Where *Duplicate* goes — the builder, filled from the rule. */
export function ruleDuplicatePath(ruleId: string): string {
  return `${WORK_RULE_BUILDER_ROUTE}?from=${encodeURIComponent(ruleId)}`;
}

const STEP_PARAM = "step";

function clampStep(raw: string | null): number {
  const parsed = Number(raw ?? "1");
  if (!Number.isInteger(parsed)) return 1;
  return Math.min(Math.max(1, parsed), RULE_BUILDER_STEPS.length);
}

const seqColumn = <Row,>(): TableArrayColumn<Row> => ({
  key: "seq",
  label: "#",
  cell: (_row, index) => <span className="tabular-nums">{index + 1}</span>,
});

// ══════════════════════════════════════════════════════════════════════════
// A TRIGGER'S SETTINGS — the *Settings* cell of image 57
// ══════════════════════════════════════════════════════════════════════════

/**
 * Each setting its PROCESS asks for, as the process serves it — never a list
 * typed here. A process with none says so (*Nothing to set*), as drawn.
 *
 * ⚠ **A QUANTITY IS NEVER WITHOUT ITS UNIT** (hard rule 3): the continuous-
 * flow minimum is drawn with the unit under it, and the unit is chosen from
 * the SERVICE's own units — a minimum in kgal on a water meter read in gal
 * would compare two different things.
 */
function TriggerSettings(props: {
  trigger: TriggerDraft;
  process: RuleProcess | undefined;
  lookups: RuleLookups;
  onChange: (params: Record<string, ParamValue>) => void;
  t: Translate;
}) {
  const { trigger, process, lookups, t } = props;
  const params = (process?.params ?? []).filter((param) => param.kind !== "setting" && param.kind !== "unit");
  const settings = (process?.params ?? []).filter((param) => param.kind === "setting");
  if (params.length === 0 && settings.length === 0) {
    return (
      <span className="text-base text-neutral-700" data-trigger-settings="none">
        {t("work.rules.settings.none")}
      </span>
    );
  }
  const set = (patch: Record<string, ParamValue>) => props.onChange({ ...trigger.params, ...patch });
  const service = typeof trigger.params.service === "string" ? trigger.params.service : "";
  const units = lookups.services.find((row) => row.value === service)?.units ?? [];

  return (
    <div className="flex flex-col gap-2" data-trigger-settings={trigger.kind}>
      {params.map((param) => (
        <ParamControl
          key={param.name}
          param={param}
          trigger={trigger}
          lookups={lookups}
          units={units}
          onSet={set}
          t={t}
        />
      ))}
      {settings.map((param) => {
        const figure = lookups.processes?.settings[param.name];
        return (
          <span key={param.name} className="text-base text-neutral-700" data-trigger-setting={param.name}>
            {t(param.label_key)} {figure === null || figure === undefined ? <Dash /> : String(figure)}
          </span>
        );
      })}
    </div>
  );
}

function ParamControl(props: {
  param: RuleProcessParam;
  trigger: TriggerDraft;
  lookups: RuleLookups;
  units: string[];
  onSet: (patch: Record<string, ParamValue>) => void;
  t: Translate;
}) {
  const { param, trigger, lookups, units, onSet, t } = props;
  const label = t(param.label_key);
  const value = trigger.params[param.name];
  const name = `${trigger.key}-${param.name}`;
  const caption = <span className="text-sm text-neutral-700">{label}</span>;

  if (param.kind === "bool") {
    return (
      <label className="inline-flex items-center gap-2 text-base">
        <CellTick label={label} name={name} checked={value === true} onChange={(next) => onSet({ [param.name]: next })} />
        {label}
      </label>
    );
  }
  if (param.kind === "asset_types") {
    return (
      <CheckDropdown
        id={name}
        label={label}
        allLabel={t("work.rules.settings.everyAssetType")}
        options={lookups.assetTypes}
        selected={Array.isArray(value) ? value : []}
        onChange={(next) => onSet({ [param.name]: next })}
      />
    );
  }
  if (param.kind === "service") {
    return (
      <span className="flex flex-col gap-1">
        {caption}
        <CellSelect
          label={label}
          name={name}
          value={typeof value === "string" ? value : ""}
          placeholder={t("work.rules.builder.pickService")}
          options={lookups.services}
          onChange={(next) => {
            const nextUnits = lookups.services.find((row) => row.value === next)?.units ?? [];
            const unit = typeof trigger.params.unit === "string" ? trigger.params.unit : "";
            // A unit the new service is not read in is cleared, never carried.
            onSet(
              unit !== "" && !nextUnits.includes(unit)
                ? { [param.name]: next, unit: "" }
                : { [param.name]: next },
            );
          }}
        />
      </span>
    );
  }
  if (param.kind === "choice") {
    // BR-WRK-067 — one value off the server's closed list (a route finding's
    // kind), each in its own words; the save refuses anything else.
    return (
      <span className="flex flex-col gap-1">
        {caption}
        <CellSelect
          label={label}
          name={name}
          value={typeof value === "string" ? value : ""}
          placeholder={t("work.rules.builder.pickFinding")}
          options={(param.options ?? []).map((option) => ({ value: option.value, label: t(option.label_key) }))}
          onChange={(next) => onSet({ [param.name]: next })}
        />
      </span>
    );
  }
  if (param.kind === "quantity" && param.unit_param !== undefined) {
    const unitName = param.unit_param;
    const unit = typeof trigger.params[unitName] === "string" ? (trigger.params[unitName] as string) : "";
    return (
      <span className="flex flex-col gap-1">
        {caption}
        <CellText
          label={label}
          name={name}
          value={typeof value === "string" ? value : ""}
          onChange={(next) => onSet({ [param.name]: next })}
        />
        <CellSelect
          label={t("work.rules.param.unit")}
          name={`${trigger.key}-${unitName}`}
          value={unit}
          placeholder={t("work.rules.builder.pickUnit")}
          options={units.map((code) => ({ value: code, label: code }))}
          blockedReason={units.length === 0 ? t("work.rules.builder.serviceFirst") : undefined}
          onChange={(next) => onSet({ [unitName]: next })}
        />
      </span>
    );
  }
  // An int — days, a count of reads.
  return (
    <span className="flex flex-col gap-1">
      {caption}
      <CellNumber
        label={label}
        name={name}
        min={param.minimum}
        value={typeof value === "string" ? value : ""}
        onChange={(next) => onSet({ [param.name]: next })}
      />
    </span>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 1 · TRIGGER — image 57
// ══════════════════════════════════════════════════════════════════════════

function TriggerStep(props: {
  draft: RuleDraft;
  onPatch: (next: Partial<RuleDraft>) => void;
  lookups: RuleLookups;
  t: Translate;
}) {
  const { draft, onPatch, lookups, t } = props;
  const processes = lookups.processes;
  const [adding, setAdding] = useState("");
  const processOptions = (processes?.results ?? []).map((row) => ({
    value: row.key,
    label: processWord(row.key, processes, t),
  }));

  const columns: TableArrayColumn<TriggerDraft>[] = [
    seqColumn<TriggerDraft>(),
    {
      key: "when",
      label: t("work.rules.col.whenThisHappens"),
      cell: (row, index) => (
        <CellSelect
          label={t("work.rules.col.whenThisHappens")}
          name={`trigger-${index + 1}-kind`}
          value={row.kind}
          placeholder={t("work.rules.builder.pickTrigger")}
          options={processOptions}
          onChange={(next) =>
            onPatch({
              triggers: draft.triggers.map((one) =>
                one.key === row.key ? { ...newTrigger(next, processes), key: one.key } : one,
              ),
            })
          }
        />
      ),
    },
    {
      key: "settings",
      label: t("work.rules.col.settings"),
      cell: (row) => (
        <TriggerSettings
          trigger={row}
          process={processes?.results.find((one) => one.key === row.kind)}
          lookups={lookups}
          t={t}
          onChange={(params) =>
            onPatch({ triggers: draft.triggers.map((one) => (one.key === row.key ? { ...one, params } : one)) })
          }
        />
      ),
    },
  ];

  const assignOptions = (processes?.assign_kinds ?? [])
    .filter((kind) => kind !== "technician" && kind !== "crew")
    .map((kind) => ({ value: kind, label: t(`work.rules.assign.${kind}`) }));
  const assignGroups = [
    {
      label: t("work.rules.assign.technicians"),
      options: lookups.technicians.map((row) => ({ value: `technician:${row.value}`, label: row.label })),
    },
    {
      label: t("work.rules.assign.crews"),
      options: lookups.crews.map((row) => ({ value: `crew:${row.value}`, label: row.label })),
    },
  ].filter((group) => group.options.length > 0);

  return (
    <div className="flex flex-col gap-4" data-rule-step="trigger">
      <Panel as="section" title={t("work.rules.builder.theRule")} data-rule-panel="rule">
        <div className="flex flex-col gap-3">
          <TextField
            id="rule-name"
            label={t("work.rules.builder.name")}
            required
            value={draft.name}
            onChange={(name) => onPatch({ name })}
          />
          {/* CR-168 §5.7 R8 — what the rule RAISES, under its name: the facts
              images 56 and 62 show (*Raises Meter exchange — residential at
              Low priority*). The drawing gives them no box of their own. */}
          <div className="grid grid-cols-2 gap-4">
            <SelectField
              id="rule-template"
              label={t("work.rules.builder.template")}
              required
              value={draft.templateId}
              placeholder={t("work.rules.builder.pickTemplate")}
              options={lookups.templates}
              onChange={(templateId) => onPatch({ templateId })}
            />
            <SelectField
              id="rule-priority"
              label={t("work.rules.col.priority")}
              value={draft.priorityId}
              placeholder={t("work.rules.builder.templatePriority")}
              options={lookups.priorities}
              onChange={(priorityId) => onPatch({ priorityId })}
            />
          </div>
        </div>
      </Panel>

      <TableArray<TriggerDraft>
        title={t("work.rules.col.whenThisHappens")}
        lead={<Note className="m-0">{t("work.rules.summary.anyRaises")}</Note>}
        collection="rule-triggers"
        columns={columns}
        rows={draft.triggers}
        rowKey={(row) => row.key}
        emptyText={t("work.rules.builder.noTriggerYet")}
        onChange={(triggers) => onPatch({ triggers })}
        removeLabel={t("work.rules.builder.removeTrigger")}
        footerLead={
          <CellSelect
            label={t("work.rules.builder.addTrigger")}
            name="add-trigger"
            value={adding}
            placeholder={t("work.rules.builder.addTrigger")}
            options={processOptions}
            onChange={setAdding}
          />
        }
        footerTrailing={
          <Button
            variant="secondary"
            size="sm"
            disabled={adding === ""}
            data-add-trigger=""
            onClick={() => {
              onPatch({ triggers: [...draft.triggers, newTrigger(adding, processes)] });
              setAdding("");
            }}
          >
            {t("work.rules.builder.add")}
          </Button>
        }
      />

      <Panel as="section" title={t("work.rules.builder.assignTo")} data-rule-panel="assign">
        <SelectField
          id="rule-assign"
          label={t("work.rules.builder.assignTo")}
          labelHidden
          value={draft.assignTo}
          options={assignOptions}
          groups={assignGroups}
          onChange={(assignTo) => onPatch({ assignTo: assignTo === "" ? "nobody" : assignTo })}
        />
      </Panel>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 2 · NOTIFY — image 59
// ══════════════════════════════════════════════════════════════════════════

function NotifyStep(props: {
  draft: RuleDraft;
  onPatch: (next: Partial<RuleDraft>) => void;
  lookups: RuleLookups;
  t: Translate;
}) {
  const { draft, onPatch, lookups, t } = props;
  const processes = lookups.processes;
  const [addingWhen, setAddingWhen] = useState("");
  const [addingKind, setAddingKind] = useState("");

  const whenOptions = (processes?.notify_when ?? []).map((when) => ({ value: when, label: notifyWhenWord(when, t) }));
  const whoOptions = (processes?.notify_who ?? []).map((who) => ({ value: who, label: notifyWhoWord(who, t) }));
  // `BR-NOT-017` — a message is Notifications' own row, picked, never typed.
  // The customer hears customer messages; the office hears staff ones.
  const messagesFor = (who: string) =>
    lookups.messages
      .filter((row) => (who === "customer" ? row.audience === "customer" : row.audience !== "customer"))
      .map((row) => ({ value: row.value, label: eventWord(row.value, t) }));
  const patchNotify = (key: string, next: Partial<NotifyDraft>) =>
    onPatch({ notify: draft.notify.map((row) => (row.key === key ? { ...row, ...next } : row)) });

  const notifyColumns: TableArrayColumn<NotifyDraft>[] = [
    seqColumn<NotifyDraft>(),
    {
      key: "when",
      label: t("work.rules.col.when"),
      cell: (row, index) => (
        <CellSelect
          label={t("work.rules.col.when")}
          name={`notify-${index + 1}-when`}
          value={row.when}
          placeholder={t("work.rules.builder.pickWhen")}
          options={whenOptions}
          onChange={(when) => patchNotify(row.key, { when })}
        />
      ),
    },
    {
      key: "who",
      label: t("work.rules.col.whoHears"),
      cell: (row, index) => (
        <CellSelect
          label={t("work.rules.col.whoHears")}
          name={`notify-${index + 1}-who`}
          value={row.who}
          placeholder={t("work.rules.builder.pickWho")}
          options={whoOptions}
          onChange={(who) => {
            // A message for the customer is not a message for the office.
            const keep = messagesFor(who).some((option) => option.value === row.eventKey);
            patchNotify(row.key, { who, eventKey: keep ? row.eventKey : "" });
          }}
        />
      ),
    },
    {
      key: "message",
      label: t("work.rules.col.message"),
      cell: (row, index) => (
        <CellSelect
          label={t("work.rules.col.message")}
          name={`notify-${index + 1}-message`}
          value={row.eventKey}
          placeholder={t("work.rules.builder.pickMessage")}
          options={row.who === "" ? [] : messagesFor(row.who)}
          blockedReason={row.who === "" ? t("work.rules.builder.whoFirst") : undefined}
          onChange={(eventKey) => patchNotify(row.key, { eventKey })}
        />
      ),
    },
    {
      key: "how",
      label: t("work.rules.col.how"),
      cell: (row) => {
        const channels = lookups.names.channels[row.eventKey] ?? [];
        return (
          <CellStatic name="notify-how">
            {channels.length === 0 ? <Dash /> : channels.map((channel) => channelWord(channel, t)).join(" · ")}
          </CellStatic>
        );
      },
    },
  ];

  const usedKinds = new Set(draft.escalations.map((row) => row.kind));
  const kindOptions = (processes?.escalation_kinds ?? []).map((kind) => ({
    value: kind,
    label: escalationWord(kind, t),
    disabled: usedKinds.has(kind),
  }));
  const alsoTellOptions = [
    ...lookups.roles.map((row) => ({ value: `role:${row.value}`, label: row.label })),
    ...lookups.people.map((row) => ({ value: `user:${row.value}`, label: row.label })),
  ];
  const patchEscalation = (key: string, next: Partial<EscalationDraft>) =>
    onPatch({ escalations: draft.escalations.map((row) => (row.key === key ? { ...row, ...next } : row)) });

  const stallColumns: TableArrayColumn<EscalationDraft>[] = [
    seqColumn<EscalationDraft>(),
    {
      key: "if",
      label: t("work.rules.col.if"),
      cell: (row, index) => (
        <CellSelect
          label={t("work.rules.col.if")}
          name={`stall-${index + 1}-kind`}
          value={row.kind}
          placeholder={t("work.rules.builder.pickEscalation")}
          options={kindOptions.map((option) => (option.value === row.kind ? { ...option, disabled: false } : option))}
          fit
          onChange={(kind) => patchEscalation(row.key, { kind })}
        />
      ),
    },
    {
      key: "after",
      label: t("work.rules.col.after"),
      cell: (row, index) => (
        <span className="flex flex-col gap-1">
          <CellNumber
            label={t("work.rules.col.after")}
            name={`stall-${index + 1}-hours`}
            min={1}
            value={row.afterHours}
            onChange={(afterHours) => patchEscalation(row.key, { afterHours })}
          />
          <span className="text-sm text-neutral-700">{t("work.rules.hoursUnit")}</span>
        </span>
      ),
    },
    {
      key: "told",
      label: t("work.rules.col.whoIsTold"),
      cell: (row) => (
        <CellStatic name="stall-told">{whoIsToldWord({ ...row, alsoTell: "" }, lookups.names, t)}</CellStatic>
      ),
    },
    {
      key: "also",
      label: t("work.rules.col.alsoTell"),
      cell: (row, index) => (
        <CellSelect
          label={t("work.rules.col.alsoTell")}
          name={`stall-${index + 1}-also`}
          value={row.alsoTell}
          placeholder={t("work.rules.alsoTell.nobody")}
          options={alsoTellOptions}
          fit
          onChange={(alsoTell) => patchEscalation(row.key, { alsoTell, alsoTellName: null })}
        />
      ),
    },
    {
      key: "message",
      label: t("work.rules.col.message"),
      // The escalation's message is its KIND's own (`EVENT_BY_KIND`), so it is
      // shown here and never offered as a picker the sender would ignore.
      cell: (row) => {
        const event = processes?.escalation_events[row.kind];
        return <CellStatic name="stall-message">{event === undefined ? <Dash /> : eventWord(event, t)}</CellStatic>;
      },
    },
  ];

  return (
    <div className="flex flex-col gap-4" data-rule-step="notify">
      <TableArray<NotifyDraft>
        title={t("work.rules.summary.whoHears")}
        lead={<Note className="m-0">{t("work.rules.builder.messagesFrom")}</Note>}
        collection="rule-notify"
        columns={notifyColumns}
        rows={draft.notify}
        rowKey={(row) => row.key}
        emptyText={t("work.rules.summary.nobodyHears")}
        onChange={(notify) => onPatch({ notify })}
        removeLabel={t("work.rules.builder.removeMessage")}
        footerLead={
          <CellSelect
            label={t("work.rules.builder.addMessage")}
            name="add-message"
            value={addingWhen}
            placeholder={t("work.rules.builder.addMessage")}
            options={whenOptions}
            onChange={setAddingWhen}
          />
        }
        footerTrailing={
          <Button
            variant="secondary"
            size="sm"
            disabled={addingWhen === ""}
            data-add-message=""
            onClick={() => {
              onPatch({ notify: [...draft.notify, newNotify(addingWhen)] });
              setAddingWhen("");
            }}
          >
            {t("work.rules.builder.add")}
          </Button>
        }
      />

      <TableArray<EscalationDraft>
        title={t("work.rules.summary.whenItStalls")}
        collection="rule-stalls"
        columns={stallColumns}
        rows={draft.escalations}
        rowKey={(row) => row.key}
        emptyText={t("work.rules.summary.noEscalation")}
        onChange={(escalations) => onPatch({ escalations })}
        removeLabel={t("work.rules.builder.removeEscalation")}
        footerLead={
          <CellSelect
            label={t("work.rules.builder.addEscalation")}
            name="add-escalation"
            value={addingKind}
            placeholder={t("work.rules.builder.addEscalation")}
            options={kindOptions}
            onChange={setAddingKind}
          />
        }
        footerTrailing={
          <Button
            variant="secondary"
            size="sm"
            disabled={addingKind === ""}
            data-add-escalation=""
            onClick={() => {
              onPatch({ escalations: [...draft.escalations, newEscalation(addingKind)] });
              setAddingKind("");
            }}
          >
            {t("work.rules.builder.add")}
          </Button>
        }
      />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 3 · REVIEW — image 61
// ══════════════════════════════════════════════════════════════════════════

function ReviewStep(props: {
  draft: RuleDraft;
  lookups: RuleLookups;
  client: ApiClient;
  onJump: (step: number) => void;
  t: Translate;
}) {
  const { draft, lookups, t } = props;
  const body = useMemo(() => {
    const write = ruleWriteFrom(draft, lookups.processes);
    return { triggers: write.triggers, template_id: write.template_id };
  }, [draft, lookups.processes]);
  // P3.39 — what the sweep WOULD raise tonight; the preview writes nothing.
  const preview = useQuery({
    queryKey: ["work", "rules", "preview", JSON.stringify(body)],
    queryFn: () => previewRule(body, props.client),
    enabled: body.template_id !== "" && body.triggers.length > 0,
    retry: false,
  });

  let count: ReactNode = null;
  if (preview.data !== undefined) {
    count = (
      <>
        <strong data-rule-tonight={preview.data.would_raise}>
          {t("work.rules.builder.tonightRaises", { count: preview.data.would_raise })}
        </strong>
        {/* `DEF-WRK-9661` — what the raise would refuse is said, never counted
            as a job: the Review read 4 where the sweep raised 3. */}
        {(preview.data.cannot_raise ?? 0) > 0 && (
          <span data-rule-cannot-raise={preview.data.cannot_raise}>
            {" "}
            {t("work.rules.builder.cannotRaise", { count: preview.data.cannot_raise })}
          </span>
        )}
      </>
    );
  } else if (preview.isError) {
    count = <span data-rule-tonight="failed">{apiErrorText(preview.error, t)}</span>;
  }

  return (
    <div className="flex flex-col gap-4" data-rule-step="review">
      <Panel as="section" title={t("work.rules.builder.reviewTitle")} data-rule-panel="will-do">
        <p className="m-0 text-base text-text">{count}</p>
        <Note className="mt-1">{t("work.rules.builder.nothingWritten")}</Note>
      </Panel>
      <RuleSummary
        draft={draft}
        processes={lookups.processes}
        names={lookups.names}
        edit={{ kind: "jump", onJump: props.onJump }}
      />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE BUILDER
// ══════════════════════════════════════════════════════════════════════════

export interface RuleBuilderProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function RuleBuilder(props: RuleBuilderProps = {}) {
  const { t } = useTranslation();
  const translate: Translate = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const routeParams = useParams();

  /** A uuid on `…/{id}/edit`; null on `…/new`. */
  const editingId = routeParams.ruleId ?? null;
  /** *Duplicate* — the rule whose settings fill a NEW rule. */
  const fromId = editingId === null ? searchParams.get("from") : null;
  const sourceId = editingId ?? fromId;

  const step = clampStep(searchParams.get(STEP_PARAM));
  const nav: WizardNavState = { step, reached: step };
  function setStep(next: WizardNavState): void {
    const query = new URLSearchParams(searchParams);
    query.set(STEP_PARAM, String(next.step));
    setSearchParams(query, { replace: true });
  }

  const lookups = useRuleLookups(client);
  const source = useQuery({
    queryKey: ["work", "rule", sourceId],
    queryFn: () => getRule(sourceId ?? "", client),
    enabled: sourceId !== null,
  });

  const [draft, setDraft] = useState<RuleDraft>(emptyRuleDraft);
  const filled = useRef(false);
  useEffect(() => {
    if (filled.current || source.data === undefined || lookups.processes === undefined) return;
    filled.current = true;
    const from = draftFromRule(source.data, lookups.processes);
    setDraft(
      editingId === null
        ? { ...from, name: translate("work.rules.builder.copyName", { name: source.data.name }) }
        : from,
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source.data, lookups.processes, editingId]);

  function patch(next: Partial<RuleDraft>): void {
    setDraft((current) => ({ ...current, ...next }));
  }

  async function runCommit(): Promise<WizardCommitOutcome> {
    try {
      const body = ruleWriteFrom(draft, lookups.processes);
      const saved =
        editingId === null
          ? await createRule({ ...body, enabled: true }, client)
          : await updateRule(editingId, body, client);
      void queryClient.invalidateQueries({ queryKey: ["work", "rules"] });
      void queryClient.invalidateQueries({ queryKey: ["work", "rule", saved.id] });
      fireToast(editingId === null ? translate("work.rules.created") : translate("work.rules.saved"));
      navigate(tenantPath(`${WORK_RULES_ROUTE}/${saved.id}`));
      return { ok: true };
    } catch (error) {
      // BR-SHL-020 — the server's own refusal, every answer still on screen.
      return { ok: false, reason: apiErrorText(error, translate) };
    }
  }

  const stepContent: Record<number, ReactNode> = {
    1: <TriggerStep draft={draft} onPatch={patch} lookups={lookups} t={translate} />,
    2: <NotifyStep draft={draft} onPatch={patch} lookups={lookups} t={translate} />,
    3: (
      <ReviewStep
        draft={draft}
        lookups={lookups}
        client={client}
        onJump={(target) => setStep({ step: target, reached: step })}
        t={translate}
      />
    ),
  };

  const steps: WizardStep[] = RULE_BUILDER_STEPS.map((spec, index) => ({
    id: spec.id,
    label: translate(spec.labelKey),
    content: stepContent[index + 1],
    validate:
      index === 0
        ? () => triggerStepVerdict(draft, lookups.processes, translate)
        : index === 1
          ? () => notifyStepVerdict(draft, translate)
          : () => true,
  }));

  return (
    <div data-rule-builder="" data-screen={WORK_RULE_BUILDER_SCREEN}>
      <PageHeader
        title={
          editingId === null ? translate("work.rules.builder.title") : translate("work.rules.builder.titleEdit")
        }
        backTo={{ to: tenantPath(WORK_RULES_ROUTE), label: translate("work.rules.title") }}
      />
      <WizardFrame
        steps={steps}
        nav={nav}
        onNavChange={setStep}
        commitLabel={editingId === null ? translate("work.rules.builder.activate") : translate("work.rules.builder.save")}
        commitFailedTitle={translate("work.rules.builder.failed")}
        onCommit={runCommit}
        onCommitted={() => undefined}
      />
    </div>
  );
}

export default RuleBuilder;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-168-BRC10 §5.6 R5–R12 · §5.7 R8 · §7.3 rules writes · §20.1 · images 57, 59, 61 (58, 60 retired)
// generated: 2026-09-05 by the CR-070 wave M build lane · rebuilt 2026-10-04 by lane RULES (round 5)
// checklist: A✔ B✔ C✔ D✔ E✔(three routes in App.tsx; + New rule, Edit, Duplicate and ✎ Edit point here) F✔ G✔ H=n/a
// gates: tsc · vitest src/features/work/rules · G31 (on route-b-migrated.txt) · G13 · i18n ×11
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
