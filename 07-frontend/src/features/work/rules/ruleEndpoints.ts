// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 5, lane RULES — the reads and writes the Rules
//           list (image 56), the three-step builder (57, 59, 61) and one
//           rule's page (62–64) are typed against.
// Tasks:    P3.16–P3.19 · P3.37 · P3.39 · P3.60 · P3.62–P3.64 · P3.66 · P3.67
// Rules:    CR-168 §7.3 *"Fixtures come from the server"* — every type here is
//           checked by `tsc` against a RECORDING in
//           `recordedServerShapes.typecheck.ts` (`work.rules`, `work.rule`,
//           `work.rules.processes`, `work.rule.jobs`, `work.rule.audit`) ·
//           B14 rule 31 (an `id` is an address, never a visible value)
// ───────────────────────────────────────────────────────
//
// ⚠ **A SEPARATE FILE, NOT FOUR HUNDRED MORE LINES OF `workEndpoints.ts`.**
// That file is edited by every Work lane at once (hard-won law 11); the rules
// reads belong to one lane and live beside the screens that read them.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { readListPage } from "@/api/paginated";
import type { PagedRows } from "@/api/paginated";

import type { WorkOrderDispatchRow } from "../workEndpoints";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** One setting a process asks for (`GET /work/rules/processes`). */
export interface RuleProcessParam {
  name: string;
  /** `int · bool · asset_types · service · quantity · unit · setting · choice`. A
   *  `setting` is another screen's figure, shown and never sent. */
  kind: string;
  default: unknown;
  required: boolean;
  label_key: string;
  minimum?: number;
  /** For a `quantity`: the sibling param that carries its unit (hard rule 3). */
  unit_param?: string;
  /** For a `choice`: the closed list the server holds, each value with its
   *  own catalogue key (`BR-WRK-067`'s finding kinds). The form types none. */
  options?: { value: string; label_key: string }[];
}

/** One of the twelve processes a rule can be set on (P3.30). */
export interface RuleProcess {
  /** The process key — also the label a raised job reads (`DEF-WRK-4096`). */
  key: string;
  /** English, served for a reader with no catalogue; the screen reads
   *  `label_key`. */
  label: string;
  label_key: string;
  module: string;
  module_label_key: string;
  source_label: string;
  /** `overnight` — read by the 02:00 sweep; `screen` — pre-selects a job on a
   *  clerk's screen; `retry` — shapes a failed job's retry. */
  moment: string;
  params: RuleProcessParam[];
}

/** `GET /work/rules/processes` — the processes ONCE, and every vocabulary the
 *  Notify step offers, so the form types no literal. */
export interface RuleProcesses {
  results: RuleProcess[];
  settings: Record<string, unknown>;
  assign_kinds: string[];
  escalation_kinds: string[];
  notify_when: string[];
  notify_who: string[];
  also_tell_kinds: string[];
  /** Which catalogue message each escalation kind sends (lane RULES). The
   *  escalation's message is the kind's own, so the screen SHOWS it and offers
   *  no picker that the sender would ignore. */
  escalation_events: Record<string, string>;
}

export interface RuleTrigger {
  seq: number;
  kind: string;
  params: Record<string, unknown>;
  module: string | null;
  moment: string | null;
}

export interface RuleNotifyRow {
  event_key: string;
  when: string | null;
  who: string | null;
}

export interface RuleAlsoTell {
  kind: string;
  id: string;
  /** A person's name; null for a role, which the screen names from `/roles`. */
  name: string | null;
}

export interface RuleEscalation {
  kind: string;
  after_hours: number;
  event_key: string | null;
  also_tell: RuleAlsoTell[];
}

/** One rule — a row of `GET /work/rules` and the body of `GET /work/rules/{id}`.
 *
 *  ⚠ `id`, `template.id`, `priority.id` and `assign_to.id` are ADDRESSES (B14
 *  rule 31); every value the screens draw is a name, a word or a count. */
export interface WorkRule {
  id: string;
  name: string;
  source_module: string;
  trigger_kind: string;
  params: Record<string, unknown>;
  triggers: RuleTrigger[];
  template: { id: string; name: string | null };
  priority: { id: string; name: string } | null;
  assignment: Record<string, unknown>;
  assign_to: { kind: string; id: string | null };
  notifications: RuleNotifyRow[];
  escalation: Record<string, unknown>;
  escalations: RuleEscalation[];
  enabled: boolean;
  /** A trigger missing a setting its process now requires — the rule raises
   *  nothing until it is set (`DEF-WRK-4097`). */
  incomplete: { seq: number; param: string }[];
  this_month: number;
  jobs_raised: number;
  last_fired_at: string | null;
}

/** What the sweep WOULD raise tonight — read only. */
export interface RuleTonight {
  subjects: number;
  would_raise: number;
  already_open: number;
  /** `DEF-WRK-9661` — subjects the raise would REFUSE, counted apart from
   *  `would_raise` so the Review promises what the sweep raises. */
  cannot_raise: number;
  /** The raise's own refusal key → how many. */
  cannot_raise_reasons: Record<string, number>;
}

export interface WorkRuleDetail extends WorkRule {
  tonight: RuleTonight;
}

/** One line of a rule's own history (image 64) — names and words, no ids. */
export interface RuleAuditRow {
  at: string | null;
  by: { name: string | null };
  /** `created · edited · turned_on · turned_off`. */
  act: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
}

/** The write — `POST /work/rules` and `PATCH /work/rules/{id}` (§7.3). */
export interface RuleWrite {
  name: string;
  triggers: { kind: string; params: Record<string, unknown> }[];
  template_id: string;
  priority_id: string | null;
  assign_to: { kind: string; id?: string };
  notifications: { event_key: string; when: string | null; who: string | null }[];
  escalations: {
    kind: string;
    after_hours: number;
    also_tell: { kind: string; id: string }[];
  }[];
  enabled?: boolean;
}

/** `GET /work/rules?q=` — paged in SQL; `q` searches the rule's name, its
 *  template and its process words (P3.18, `DEF-WRK-9573`). */
export async function listRules(
  query: { q?: string; page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<PagedRows<WorkRule>> {
  const q = query.q?.trim();
  return readListPage<WorkRule>(
    "/work/rules",
    { q: q === "" ? undefined : q, page: query.page, per: query.per },
    client,
  );
}

export async function getRule(ruleId: string, client: ApiClient = api): Promise<WorkRuleDetail> {
  return requireData(await client.get<WorkRuleDetail>(`/work/rules/${encodeURIComponent(ruleId)}`));
}

export async function getRuleProcesses(client: ApiClient = api): Promise<RuleProcesses> {
  return requireData(await client.get<RuleProcesses>("/work/rules/processes"));
}

export async function createRule(body: RuleWrite, client: ApiClient = api): Promise<WorkRule> {
  return requireData(await client.post<WorkRule>("/work/rules", body));
}

export async function updateRule(
  ruleId: string,
  body: RuleWrite,
  client: ApiClient = api,
): Promise<WorkRule> {
  return requireData(
    await client.patch<WorkRule>(`/work/rules/${encodeURIComponent(ruleId)}`, body),
  );
}

export async function setRuleEnabled(
  ruleId: string,
  enabled: boolean,
  client: ApiClient = api,
): Promise<WorkRule> {
  const verb = enabled ? "enable" : "disable";
  return requireData(
    await client.post<WorkRule>(`/work/rules/${encodeURIComponent(ruleId)}/${verb}`, {}),
  );
}

/** `POST /work/rules/preview` — the Review's *Tonight it raises N jobs*. Writes
 *  nothing (P3.39). */
export async function previewRule(
  body: { triggers: RuleWrite["triggers"]; template_id: string },
  client: ApiClient = api,
): Promise<RuleTonight> {
  return requireData(await client.post<RuleTonight>("/work/rules/preview", body));
}

export async function listRuleJobs(
  ruleId: string,
  query: { page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<PagedRows<WorkOrderDispatchRow>> {
  return readListPage<WorkOrderDispatchRow>(
    `/work/rules/${encodeURIComponent(ruleId)}/jobs`,
    { page: query.page, per: query.per },
    client,
  );
}

export async function listRuleAudit(
  ruleId: string,
  query: { page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<PagedRows<RuleAuditRow>> {
  return readListPage<RuleAuditRow>(
    `/work/rules/${encodeURIComponent(ruleId)}/audit`,
    { page: query.page, per: query.per },
    client,
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-168-BRC10 §7.3 rules rows · §20.1 (lane SRV-4's server) · images 56–64
// generated: 2026-10-04 by lane RULES (round 5)
// checklist: A✔ B✔ C✔ D✔ E=n/a F✔ G✔ H=n/a
// gates: tsc (recordedServerShapes.typecheck.ts) · vitest src/features/work/rules
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
