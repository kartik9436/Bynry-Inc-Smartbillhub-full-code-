// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 5, lane RULES — the rule builder's draft and
//           every word the three rule screens say about a rule, as pure
//           functions a test can read with no DOM.
// Tasks:    P3.19 · P3.64 (three steps) · P3.65 (several triggers) · P3.66
//           (the notifications table) · P3.67 (escalations are rows)
// Rules:    B14 rule 31 (no database id is a visible value) · rule 33 ·
//           rule 35 (every word from the catalogue) · hard rule 3 (a
//           consumption figure carries its unit) · `BR-NOT-017` (a message is
//           a catalogue key, never text) · `BR-NOT-021` as narrowed for Work
//           escalations (PO 2026-10-04: *Also tell* ADDS, never removes)
// ───────────────────────────────────────────────────────
//
// ⚠ **ONE DRAFT FOR THREE SCREENS.** The builder edits it, the builder's
// Review draws it, and one rule's Overview draws the SAME thing built from the
// server's rule (`draftFromRule`) — so the Review and the Overview cannot say
// two different things about one rule (B14 rule 43).
//
// ⚠ **NOTHING HERE IS A LITERAL LIST OF PROCESSES, KINDS OR MESSAGES.** Every
// vocabulary — the twelve processes and their settings, who a job can go to,
// the seven escalations, when and who hears — arrives from
// `GET /work/rules/processes`, and the messages from Notifications. The old
// builder's `TRIGGERS_BY_SOURCE` (five pairs typed in the browser) is gone
// with the source-module select the drawing retired (CR-168 §5.6 R6).
import type {
  RuleProcess,
  RuleProcesses,
  RuleWrite,
  WorkRule,
} from "./ruleEndpoints";

export type Translate = (key: string, params?: Record<string, unknown>) => string;

/** The builder's three steps, in the drawing's order (images 57, 59, 61; the
 *  26 Sep ruling retires *Assignment* and *Escalation* — images 58 and 60). */
export const RULE_BUILDER_STEPS = [
  { id: "trigger", labelKey: "work.rules.builder.step.trigger" },
  { id: "notify", labelKey: "work.rules.builder.step.notify" },
  { id: "review", labelKey: "work.rules.builder.step.review" },
] as const;

export type ParamValue = string | boolean | string[];

export interface TriggerDraft {
  /** A row key for React — never sent, never shown. */
  key: string;
  kind: string;
  params: Record<string, ParamValue>;
}

export interface NotifyDraft {
  key: string;
  when: string;
  who: string;
  eventKey: string;
}

export interface EscalationDraft {
  key: string;
  kind: string;
  afterHours: string;
  /** `""` (nobody), `role:<code>` or `user:<id>` — one *Also tell*, as drawn. */
  alsoTell: string;
  /** A person's served name, kept so a rule re-opened names them before the
   *  people list has loaded. */
  alsoTellName: string | null;
}

export interface RuleDraft {
  name: string;
  triggers: TriggerDraft[];
  templateId: string;
  priorityId: string;
  /** `nobody · area · skill · technician:<id> · crew:<id>`. */
  assignTo: string;
  notify: NotifyDraft[];
  escalations: EscalationDraft[];
}

let counter = 0;
export function rowKey(prefix: string): string {
  counter += 1;
  return `${prefix}-${counter}`;
}

export function emptyRuleDraft(): RuleDraft {
  return {
    name: "",
    triggers: [],
    templateId: "",
    priorityId: "",
    assignTo: "nobody",
    notify: [],
    escalations: [],
  };
}

/** A process's own starting settings — its served defaults, as the form holds
 *  them (numbers as strings: nothing here parses a figure). */
export function defaultParams(process: RuleProcess | undefined): Record<string, ParamValue> {
  const out: Record<string, ParamValue> = {};
  for (const param of process?.params ?? []) {
    if (param.kind === "setting") continue;
    out[param.name] = paramFromWire(param.kind, param.default);
  }
  return out;
}

function paramFromWire(kind: string, value: unknown): ParamValue {
  if (kind === "bool") return value === true;
  if (kind === "asset_types") return Array.isArray(value) ? value.map(String) : [];
  if (value === null || value === undefined) return "";
  return String(value);
}

export function newTrigger(kind: string, processes: RuleProcesses | undefined): TriggerDraft {
  const process = processes?.results.find((row) => row.key === kind);
  return { key: rowKey("trigger"), kind, params: defaultParams(process) };
}

export function newEscalation(kind: string): EscalationDraft {
  return { key: rowKey("escalation"), kind, afterHours: "", alsoTell: "", alsoTellName: null };
}

export function newNotify(when: string): NotifyDraft {
  return { key: rowKey("notify"), when, who: "", eventKey: "" };
}

/** The rule as the builder holds it — for Edit, Duplicate and the Overview. */
export function draftFromRule(rule: WorkRule, processes: RuleProcesses | undefined): RuleDraft {
  const assign = rule.assign_to ?? { kind: "nobody", id: null };
  return {
    name: rule.name,
    triggers: rule.triggers.map((trigger) => {
      const process = processes?.results.find((row) => row.key === trigger.kind);
      const params = defaultParams(process);
      for (const param of process?.params ?? []) {
        if (param.kind === "setting") continue;
        if (param.name in trigger.params) params[param.name] = paramFromWire(param.kind, trigger.params[param.name]);
      }
      return { key: rowKey("trigger"), kind: trigger.kind, params };
    }),
    templateId: rule.template.id,
    priorityId: rule.priority?.id ?? "",
    assignTo:
      (assign.kind === "technician" || assign.kind === "crew") && assign.id
        ? `${assign.kind}:${assign.id}`
        : assign.kind || "nobody",
    notify: rule.notifications.map((row) => ({
      key: rowKey("notify"),
      when: row.when ?? "",
      who: row.who ?? "",
      eventKey: row.event_key,
    })),
    escalations: rule.escalations.map((row) => {
      const first = row.also_tell[0];
      return {
        key: rowKey("escalation"),
        kind: row.kind,
        afterHours: String(row.after_hours),
        alsoTell: first === undefined ? "" : `${first.kind}:${first.id}`,
        alsoTellName: first?.name ?? null,
      };
    }),
  };
}

function paramToWire(kind: string, value: ParamValue | undefined): unknown {
  if (value === undefined) return undefined;
  if (kind === "bool") return value === true;
  if (kind === "asset_types") return Array.isArray(value) ? value : [];
  const text = typeof value === "string" ? value.trim() : "";
  if (text === "") return undefined;
  // An int is sent as the person typed it; the SERVER parses it and refuses a
  // bad one with its own words. A quantity stays a string (hard rule 2's
  // posture: a figure is never a float in a browser).
  return text;
}

/** The body `POST /work/rules` and `PATCH /work/rules/{id}` take (§7.3). */
export function ruleWriteFrom(draft: RuleDraft, processes: RuleProcesses | undefined): RuleWrite {
  const [assignKind, assignId] = draft.assignTo.split(":");
  return {
    name: draft.name.trim(),
    triggers: draft.triggers.map((trigger) => {
      const process = processes?.results.find((row) => row.key === trigger.kind);
      const params: Record<string, unknown> = {};
      for (const param of process?.params ?? []) {
        if (param.kind === "setting") continue;
        const value = paramToWire(param.kind, trigger.params[param.name]);
        if (value !== undefined) params[param.name] = value;
      }
      return { kind: trigger.kind, params };
    }),
    template_id: draft.templateId,
    priority_id: draft.priorityId === "" ? null : draft.priorityId,
    assign_to: assignId ? { kind: assignKind, id: assignId } : { kind: assignKind || "nobody" },
    notifications: draft.notify.map((row) => ({
      event_key: row.eventKey,
      when: row.when === "" ? null : row.when,
      who: row.who === "" ? null : row.who,
    })),
    escalations: draft.escalations.map((row) => {
      const [kind, id] = row.alsoTell.split(":");
      return {
        kind: row.kind,
        after_hours: Number.parseInt(row.afterHours, 10),
        also_tell: id ? [{ kind, id }] : [],
      };
    }),
  };
}

/** A required setting the person has not filled — by trigger row. */
export function missingParams(
  trigger: TriggerDraft,
  processes: RuleProcesses | undefined,
): string[] {
  const process = processes?.results.find((row) => row.key === trigger.kind);
  return (process?.params ?? [])
    .filter((param) => param.required && param.kind !== "setting")
    .filter((param) => {
      const value = trigger.params[param.name];
      return value === undefined || value === "" || (Array.isArray(value) && value.length === 0);
    })
    .map((param) => param.name);
}

/** Why the Trigger step cannot continue, or `true`. B14 rule 33: an
 *  instruction, six words or fewer. */
export function triggerStepVerdict(
  draft: RuleDraft,
  processes: RuleProcesses | undefined,
  t: Translate,
): true | string {
  if (draft.name.trim() === "") return t("work.rules.builder.needName");
  if (draft.templateId === "") return t("work.rules.builder.needTemplate");
  if (draft.triggers.length === 0) return t("work.rules.builder.needTrigger");
  if (draft.triggers.some((trigger) => missingParams(trigger, processes).length > 0)) {
    return t("work.rules.builder.needSetting");
  }
  return true;
}

export function hoursValid(value: string): boolean {
  return /^\d+$/.test(value.trim()) && Number.parseInt(value, 10) >= 1;
}

/** Why the Notify step cannot continue, or `true`. */
export function notifyStepVerdict(draft: RuleDraft, t: Translate): true | string {
  if (draft.notify.some((row) => row.who === "" || row.eventKey === "")) {
    return t("work.rules.builder.needMessage");
  }
  if (draft.escalations.some((row) => !hoursValid(row.afterHours))) {
    return t("work.rules.builder.needHours");
  }
  return true;
}

// ── Words ─────────────────────────────────────────────────────────────────

export function processWord(kind: string, processes: RuleProcesses | undefined, t: Translate): string {
  const process = processes?.results.find((row) => row.key === kind);
  if (process === undefined) return t("work.rules.process.unknown");
  return t(process.label_key, { defaultValue: process.label });
}

export function moduleWord(module: string | null, t: Translate): string {
  if (module === null || module === "") return "";
  return t(`work.rules.module.${module}`);
}

/** The rule list's SOURCE MODULE — the modules of its triggers, once each. */
export function ruleModules(rule: WorkRule, t: Translate): string {
  const seen: string[] = [];
  for (const trigger of rule.triggers) {
    if (trigger.module !== null && !seen.includes(trigger.module)) seen.push(trigger.module);
  }
  return seen.map((module) => moduleWord(module, t)).join(" · ");
}

export function assignKindWord(kind: string, t: Translate): string {
  return t(`work.rules.assign.${kind}`);
}

export function escalationWord(kind: string, t: Translate): string {
  return t(`work.rules.escalation.${kind}`);
}

export function notifyWhenWord(when: string, t: Translate): string {
  return t(`work.rules.notify.when.${when}`);
}

export function notifyWhoWord(who: string, t: Translate): string {
  return t(`work.rules.notify.who.${who}`);
}

export function eventWord(eventKey: string, t: Translate): string {
  return t(`notifications.rules.event.${eventKey}`);
}

export function channelWord(channel: string, t: Translate): string {
  return t(`notifications.rules.channel.${channel}`);
}

/** Names the screens need for values the rule holds as ids (B14 rule 31). */
export interface RuleNames {
  templates: Record<string, string>;
  priorities: Record<string, string>;
  technicians: Record<string, string>;
  crews: Record<string, string>;
  roles: Record<string, string>;
  people: Record<string, string>;
  services: Record<string, string>;
  assetTypes: Record<string, string>;
  /** Each message's channels — the *How* column. */
  channels: Record<string, string[]>;
}

export function emptyNames(): RuleNames {
  return {
    templates: {},
    priorities: {},
    technicians: {},
    crews: {},
    roles: {},
    people: {},
    services: {},
    assetTypes: {},
    channels: {},
  };
}

/** *Whoever has the skill*, *D. Ortiz*, *Field crew A*, *Nobody yet*. */
export function assignWord(assignTo: string, names: RuleNames, t: Translate): string {
  const [kind, id] = assignTo.split(":");
  if (kind === "technician" && id) return names.technicians[id] ?? t("work.rules.assign.technician");
  if (kind === "crew" && id) return names.crews[id] ?? t("work.rules.assign.crew");
  return assignKindWord(kind || "nobody", t);
}

/** *The area supervisor* — a role by its name, a person by theirs. */
export function alsoTellWord(row: EscalationDraft, names: RuleNames, t: Translate): string | null {
  if (row.alsoTell === "") return null;
  const [kind, id] = row.alsoTell.split(":");
  if (kind === "role") return names.roles[id] ?? t("work.rules.alsoTell.role");
  return names.people[id] ?? row.alsoTellName ?? t("work.rules.alsoTell.person");
}

/** *Whoever acted · System Admins · the area supervisor* (`BR-NOT-021`, plus
 *  the row's *Also tell*). */
export function whoIsToldWord(row: EscalationDraft, names: RuleNames, t: Translate): string {
  const derived = t("work.rules.escalation.derived");
  const extra = alsoTellWord(row, names, t);
  return extra === null ? derived : `${derived} · ${extra}`;
}

/** The *Settings* cell of one trigger, read back: *Minimum 5 kgal*, *Nothing
 *  to set*. Every figure carries its unit (hard rule 3). */
export function settingsWords(
  trigger: TriggerDraft,
  processes: RuleProcesses | undefined,
  names: RuleNames,
  t: Translate,
): string {
  const process = processes?.results.find((row) => row.key === trigger.kind);
  const params = process?.params ?? [];
  const unitParams = new Set(params.map((param) => param.unit_param).filter(Boolean));
  const bits: string[] = [];
  for (const param of params) {
    if (unitParams.has(param.name)) continue;
    const label = t(param.label_key);
    if (param.kind === "setting") {
      const figure = processes?.settings[param.name];
      if (figure !== null && figure !== undefined) bits.push(`${label} ${String(figure)}`);
      continue;
    }
    const value = trigger.params[param.name];
    if (param.kind === "bool") {
      if (value === true) bits.push(label);
      continue;
    }
    if (param.kind === "asset_types") {
      const ids = Array.isArray(value) ? value : [];
      bits.push(
        ids.length === 0
          ? t("work.rules.settings.everyAssetType")
          : ids.map((id) => names.assetTypes[id] ?? t("work.rules.settings.assetType")).join(", "),
      );
      continue;
    }
    if (typeof value !== "string" || value === "") continue;
    if (param.kind === "service") {
      bits.push(names.services[value] ?? value);
      continue;
    }
    if (param.kind === "quantity" && param.unit_param) {
      const unit = trigger.params[param.unit_param];
      bits.push(`${label} ${value}${typeof unit === "string" && unit !== "" ? ` ${unit}` : ""}`);
      continue;
    }
    bits.push(`${label} ${value}`);
  }
  return bits.length === 0 ? t("work.rules.settings.none") : bits.join(" · ");
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-168-BRC10 §5.6 (R5–R12), §7.3 rules writes, §20.1 · images 57, 59, 61, 62
// generated: 2026-10-04 by lane RULES (round 5)
// checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
// gates: tsc · vitest src/features/work/rules
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
