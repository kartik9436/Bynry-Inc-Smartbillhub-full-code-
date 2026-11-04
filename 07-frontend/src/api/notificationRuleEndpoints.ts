// ── Trace ──────────────────────────────────────────────
// Story:    US-NOT-017 (SET-12D the event rule page — CR-009's ONE remaining
//           blocker, DEF-286: the cards become EDITORS)   Screens: S8
// Rules:    BR-NOT-017 (ONE HOME for every notification rule) ·
//           BR-NOT-021 (staff recipient is RULED — no client may send one) ·
//           BR-NOT-006 (language modes) · BR-SHL-025 (a control that may not
//           act renders WITH its reason) · CLAUDE.md law 11's TS/Python
//           boundary discipline (DEF-522/526/531/535: five field names were
//           hand-copied wrong across it in ONE day)
// Tests:    07-frontend/src/features/tenancy/SettingsNotificationRule.dom.test.tsx ·
//           07-frontend/src/features/notifications/NotificationRules.test.tsx
// Impacts:  07-frontend/src/features/notifications/NotificationRules.tsx (the
//           only consumer) · 06-backend/apps/notifications/rule_service.py
//           (EDITABLE_RULE_FIELDS / EDITABLE_CHANNEL_FIELDS, which every
//           spelling below is read from) · rules_api.py (the PUT this feeds)
// ───────────────────────────────────────────────────────
// The SET-12D EDIT vocabulary and the diff builder — its own file, the
// `bankRecEndpoints.ts` / `billingOpsEndpoints.ts` precedent: `endpoints.ts`
// holds two or three lanes' half-finished work on any afternoon, so one
// family, one file, one lane's diff. Nothing here re-exports or shadows what
// `endpoints.ts` already publishes — the PUT wrapper (`updateNotificationRule`)
// and the read types stay THERE and are imported, because two wrappers for one
// route are two spellings free to disagree.
//
// ══════════════════════════════════════════════════════════════════════════
// EVERY STRING BELOW IS READ FROM THE PYTHON THAT CONSUMES IT, BY NAME
// ══════════════════════════════════════════════════════════════════════════
// DEF-522/526/531/535: five field names were hand-copied wrong across this
// codebase's TS/Python boundary in one day. So every constant here cites the
// exact Python source, and `SettingsNotificationRule.dom.test.tsx` asserts the
// wire keys leaving a real save against these spellings.
import { getTemplateCatalog } from "./endpoints";
import type { NotificationRuleDetail, NotificationRulePatch } from "./endpoints";
import type { ApiClient } from "./client";
import { api } from "./client";

/** `rule_service.EDITABLE_RULE_FIELDS` (rule_service.py:107), spelling for
 *  spelling and in the same order. A key outside this set is refused BY NAME
 *  by `update_rule`, so the diff builder below can emit these and only these. */
export const EDITABLE_RULE_FIELDS = [
  "enabled",
  "customer_scope",
  "service_scope",
  "plan_class",
  "skip_accounts_on_payment_plan",
  "trigger_mode",
  "offset_days",
  "fixed_time",
  "quiet_hours_mode",
  "failure_policy",
] as const;

/** `rule_service.EDITABLE_CHANNEL_FIELDS` (rule_service.py:121). */
export const EDITABLE_CHANNEL_FIELDS = ["enabled", "template_code", "language_mode"] as const;

/** `rule_catalog.CUSTOMER_SCOPES` — all_contacts · primary_only. */
export const CUSTOMER_SCOPES = ["all_contacts", "primary_only"] as const;

/** `rule_catalog.PLAN_CLASSES` — all · residential · commercial. */
export const PLAN_CLASSES = ["all", "residential", "commercial"] as const;

/** `rule_catalog.TRIGGER_MODES` — immediate · offset_days · fixed_time. */
export const TRIGGER_MODES = ["immediate", "offset_days", "fixed_time"] as const;

/** `rule_catalog.QUIET_HOURS_MODES` — respect · override. */
export const QUIET_HOURS_MODES = ["respect", "override"] as const;

/** `rule_catalog.FAILURE_POLICIES` — retry_3_days_then_email · retry_once · none. */
export const FAILURE_POLICIES = ["retry_3_days_then_email", "retry_once", "none"] as const;

/** `rule_catalog.LANGUAGE_MODES` (BR-NOT-006) — auto · english_only. */
export const LANGUAGE_MODES = ["auto", "english_only"] as const;

/** What the SET-12D editors hold while a System Admin types. Strings
 *  throughout, because `<input>`/`<select>` values are strings and the diff
 *  builder — not the components — owns the conversion to wire types. */
export interface NotificationRuleDraft {
  customer_scope: string;
  service_scope: string;
  plan_class: string;
  skip_accounts_on_payment_plan: boolean;
  trigger_mode: string;
  /** As typed. "" = none; parsed to an integer only at diff time. */
  offset_days: string;
  /** "HH:MM" wall-clock tenant time (rules_api._time_field parses it), "" = none. */
  fixed_time: string;
  quiet_hours_mode: string;
  failure_policy: string;
  /** channel → its three editable fields. `template_code: ""` means null —
   *  a `<select>` cannot hold null, so the mapping lives here, once. */
  channels: Record<string, { enabled: boolean; template_code: string; language_mode: string }>;
}

/** The server's rule, as a draft — what the editors open showing. A tenant who
 *  opens the page and saves nothing must produce NO wire call (the service
 *  refuses an empty save, and it is right to). */
export function draftOf(detail: NotificationRuleDetail): NotificationRuleDraft {
  const channels: NotificationRuleDraft["channels"] = {};
  for (const row of detail.channel_rules) {
    channels[row.channel] = {
      enabled: row.enabled,
      template_code: row.template_code ?? "",
      language_mode: row.language_mode,
    };
  }
  return {
    customer_scope: detail.customer_scope,
    service_scope: detail.service_scope,
    plan_class: detail.plan_class,
    skip_accounts_on_payment_plan: detail.skip_accounts_on_payment_plan,
    trigger_mode: detail.trigger_mode,
    offset_days: detail.offset_days === null ? "" : String(detail.offset_days),
    fixed_time: detail.fixed_time ?? "",
    quiet_hours_mode: detail.quiet_hours_mode,
    failure_policy: detail.failure_policy,
    channels,
  };
}

/** A whole number of days, or null for "". Anything else is `undefined` —
 *  the caller must block the save and say so, never send it. */
export function parsedOffsetDays(raw: string): number | null | undefined {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  if (!/^\d+$/.test(trimmed)) return undefined;
  return Number(trimmed);
}

/** The client-side half of `_refuse_incoherent_timing` — the trigger mode and
 *  its argument as a PAIR, checked before the wire so a System Admin reads a
 *  field error beside the field rather than a refusal strip after a round
 *  trip. The SERVER's check stays the enforcement (BR-SHL-025). */
export function timingProblem(draft: NotificationRuleDraft): "offset_days" | "fixed_time" | null {
  if (draft.trigger_mode === "offset_days" && parsedOffsetDays(draft.offset_days) === undefined) {
    return "offset_days";
  }
  if (draft.trigger_mode === "offset_days" && draft.offset_days.trim() === "") {
    return "offset_days";
  }
  if (draft.trigger_mode === "fixed_time") {
    if (!/^\d{1,2}:\d{2}$/.test(draft.fixed_time.trim())) return "fixed_time";
  }
  return null;
}

/**
 * The PARTIAL change set `update_rule` asks for — *"Pass only what is
 * changing"* — or `null` when nothing changed, so the caller can refuse to
 * fire an empty save the server would refuse anyway.
 *
 * The timing trio travels TOGETHER whenever any of it moved: `update_rule`
 * validates the mode and its argument as a pair after both are applied, so a
 * save that switches to `offset_days` must carry the mode, the number AND the
 * cleared `fixed_time` in one payload. Unchanged members of the trio are
 * skipped server-side (`current == value` continues), so sending them is
 * lossless and never audited as a change.
 */
export function ruleSavePatch(
  detail: NotificationRuleDetail,
  draft: NotificationRuleDraft,
): NotificationRulePatch | null {
  const patch: NotificationRulePatch = {};

  // Audience — customer events only. A staff event's editors never render
  // (BR-NOT-021: the recipient is ruled, and `_validated` refuses a
  // customer_scope on a staff rule even unchanged), so its draft always equals
  // the server and none of these keys is ever emitted for one.
  if (draft.customer_scope !== detail.customer_scope) patch.customer_scope = draft.customer_scope;
  if (draft.service_scope !== detail.service_scope) patch.service_scope = draft.service_scope;
  if (draft.plan_class !== detail.plan_class) patch.plan_class = draft.plan_class;
  if (draft.skip_accounts_on_payment_plan !== detail.skip_accounts_on_payment_plan) {
    patch.skip_accounts_on_payment_plan = draft.skip_accounts_on_payment_plan;
  }

  // Timing — the coherent trio.
  const draftOffset = parsedOffsetDays(draft.offset_days);
  const draftTime = draft.fixed_time.trim() === "" ? null : draft.fixed_time.trim();
  const timingMoved =
    draft.trigger_mode !== detail.trigger_mode ||
    draftOffset !== detail.offset_days ||
    draftTime !== detail.fixed_time;
  if (timingMoved) {
    if (draftOffset === undefined) {
      // Unparseable — the screen blocks this save (`timingProblem`); reaching
      // here is a programming error and must not become a silent wire guess.
      throw new Error("offset_days is not a whole number; the save must be blocked, not sent");
    }
    patch.trigger_mode = draft.trigger_mode;
    patch.offset_days = draft.trigger_mode === "offset_days" ? draftOffset : null;
    patch.fixed_time = draft.trigger_mode === "fixed_time" ? draftTime : null;
  }
  if (draft.quiet_hours_mode !== detail.quiet_hours_mode) {
    patch.quiet_hours_mode = draft.quiet_hours_mode;
  }
  if (draft.failure_policy !== detail.failure_policy) patch.failure_policy = draft.failure_policy;

  // Channels — per-channel partial patches, only for rows that moved.
  const channels: NonNullable<NotificationRulePatch["channels"]> = {};
  for (const row of detail.channel_rules) {
    const edited = draft.channels[row.channel];
    if (edited === undefined) continue;
    const channelPatch: { enabled?: boolean; template_code?: string | null; language_mode?: string } =
      {};
    if (edited.enabled !== row.enabled) channelPatch.enabled = edited.enabled;
    const editedTemplate = edited.template_code === "" ? null : edited.template_code;
    if (editedTemplate !== row.template_code) channelPatch.template_code = editedTemplate;
    if (edited.language_mode !== row.language_mode) channelPatch.language_mode = edited.language_mode;
    if (Object.keys(channelPatch).length > 0) channels[row.channel] = channelPatch;
  }
  if (Object.keys(channels).length > 0) patch.channels = channels;

  return Object.keys(patch).length === 0 ? null : patch;
}

/** One template the picker can offer — a CLASS from the Templates catalog,
 *  which is exactly what a channel row stores (`_validated_channel`: *"a
 *  template code is a class from the Templates catalog"*). */
export interface NotificationTemplateOption {
  code: string;
  name: string;
  /** False = no variant of this class has a published body yet. Offered
   *  anyway — the class is real and renderable the day one is published — but
   *  the picker labels it, because BR-SHL-025 says a control states its own
   *  limits. */
  has_published: boolean;
}

/**
 * REAL template codes for the pickers, from the templates read path
 * (`GET /template-catalog` — SET-09's own route), grouped by channel.
 *
 * Nothing is invented here: a class with no `channel` fact
 * (`catalogs.CLASSES_WITHOUT_CATALOG` — nobody has defined its merge fields)
 * is left out, because offering it on a guessed channel would queue a message
 * the renderer for that channel cannot render. The event's currently-stored
 * code is re-added by the card if the catalog page missed it, so the select
 * always shows the truth it opened with.
 */
export async function getTemplateOptionsByChannel(
  client: ApiClient = api,
): Promise<Record<string, NotificationTemplateOption[]>> {
  // 500 covers the whole catalog (48 classes today; `pagination.PAGE_SIZES`
  // clamps, never errors, if that ever stops being true a second page is a
  // follow-up, not a crash).
  const page = await getTemplateCatalog({ per: 500 }, client);
  const byChannel: Record<string, NotificationTemplateOption[]> = {};
  for (const row of page.results) {
    if (row.channel === null) continue;
    const bucket = (byChannel[row.channel] ??= []);
    bucket.push({ code: row.code, name: row.name, has_published: row.has_published });
  }
  for (const bucket of Object.values(byChannel)) {
    bucket.sort((a, b) => a.name.localeCompare(b.name));
  }
  return byChannel;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-NOT-017@def286 (12-governance/10-defect-log.csv DEF-286 · 12-governance/11-change-requests.md → CR-009 closure record · apps/notifications/rule_service.py EDITABLE_RULE_FIELDS + EDITABLE_CHANNEL_FIELDS + rule_catalog.py vocabularies, read by name · templates_api.template_catalog, the options read path)
// generated: 2026-08-22 by story-coder (W13 DEF-286 lane)
// checklist: A✔ B✔ C✔ D=n/a(no backend change — every route this feeds already exists) E=deferred(the screen is NotificationRules.tsx) F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest (SettingsNotificationRule.dom.test.tsx asserts the wire keys leaving a REAL save against rule_service's spellings; proved RED first with a deliberately wrong `quietHoursMode` key — transcript in the commit message)
// exceptions: (1) NO staff_recipient key can leave this module — BR-NOT-021; the diff builder has no code path that emits one. (2) The picker offers CLASS codes, not template VARIANTS: `template_code` is the stored field and `update_rule` accepts nothing variant-shaped, so a variant picker would need a wire that does not exist (OQ-332; decision-log row 2026-08-22). (3) `getTemplateOptionsByChannel` leaves out a class with no channel fact rather than guessing one.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
