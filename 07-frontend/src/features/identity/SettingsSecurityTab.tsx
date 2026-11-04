// ── Trace ──────────────────────────────────────────────
// Story:    US-IDN-010 (EP-IDN-04 §Stories)  Screens: S8 (Settings → Security)
// Change:   CR-155-BRC09 — the redesign the PO approved on 2026-09-29, built
//           from the images in `05-prototype/security-redesign-2026-09-29/`
//           (B14 rule 42: a screen is built from the drawing AS AN IMAGE).
// Rules:    BR-IDN-019 (ONE tenant-wide record; System Admin edits, Executive VIEWS; atomic save, audited) ·
//           BR-IDN-020 (IP allowlist = IPv4 CIDRs, empty = unrestricted, self-lockout guard) ·
//           BR-IDN-025 (seed defaults: min 8 · upper+lower+number on · symbol off · expiry Never) ·
//           BR-IDN-026 as amended by CR-145-BRC08 · BR-IDN-016 (values govern the next
//           password set immediately) · BR-IDN-028 (NO 2FA-requirement section exists on the v1 tab) ·
//           BR-SHL-025 (Executive sees disabled-with-reason) · BR-SHL-020 (plain-language failure) ·
//           B14 rules 31/32/33/42/43/44
// ───────────────────────────────────────────────────────
// S8 → Security.
//
// ── WHAT THE 2026-09-29 REDESIGN CHANGED, AND WHY EACH ONE ────────────────
// It shipped as FIVE cards in a three-then-two grid: Password policy · Access
// · Stay signed in, then Lockout · Audit log — four, three, two, then two and
// one. That left an empty column in the top row, a whole card whose entire
// content was one button, and **Save below the fold**. The PO approved three
// cards of four, four and three controls in ONE row, then Save, then a
// full-width Audit log card underneath.
//
// The grouping is the argument, not the tidying:
//   · **Sessions** takes *Stay signed in* out of its own card, because "how
//     long may a clerk stay signed in" is the same question as the idle
//     timeout and the hard limit, and a card of its own made it look like a
//     different one.
//   · **Signing in** takes the lockout pair and the address list, because
//     both answer *who gets in* — they sat in different ROWS before.
//   · The `SECURITY` kicker is gone. It sat 40px under a tab already reading
//     *Security* (B14 rule 32's description budget, and rule 2 makes the
//     kicker optional).
//   · Every *"Between 4 and 12 hours."* help line goes, because **a dropdown
//     IS its range**. Exactly one help line is kept — *"Applies to the next
//     sign-in."* on the hard limit — because that is a fact a clerk cannot
//     read off the control.
//   · The two platform facts (last 5 passwords blocked, temporary password
//     lasts 7 days) move from **Access** into **Passwords**, where they are
//     about the thing the card is about.
//   · `(optional)` leaves the address label. We mark what is REQUIRED.
//
// ── WHAT THIS FILE NO LONGER CONTAINS, WHICH IS THE POINT ─────────────────
// ⚠ **THE LAST TWO HAND-TYPED OPTION TUPLES ARE GONE — `DEF-IDN-7501`,
// CLOSED BY THE `CR-145-BRC08` `F2` LANE ON 2026-09-29, NOT BY THIS ONE.**
// `PW_MIN_LENGTH_OPTIONS = [8, 10, 12]` and `PW_EXPIRY_OPTIONS = [null, 90,
// 180]` lived at lines 100–101 of this file for weeks, under a comment
// calling them the server's tuples. `services.SETTING_LIMITS` publishes both
// now, so both dropdowns read `policy.limits` like every other control here,
// and **this file holds no list of allowed values at all.** This lane keeps
// that property through the redesign and does not re-introduce one.
//
// ⚠ **AND PUBLISHING A LIMIT IS NOT MAKING A SETTING** — the `F2` lane's
// warning, carried over verbatim in substance because it is the thing a
// reader of this file is most likely to get wrong. The password rules are
// OUTSIDE `CR-145` and did not move: minimum 8, expiry Never, last-5 history,
// a temporary password for 7 days. A lane reading those two published entries
// as per-utility has widened a ruling nobody made.
//
// ⚠ **AND IT HOLDS NO FALLBACK FOR `limits`, ON PURPOSE.** A default would be
// a fourth hand-typed copy of the server's tuples wearing a safety belt, and
// it would be wrong in exactly the case it exists for — an older server, or a
// newer one whose limits moved. Every control is built by `PolicyValueField`,
// which reads the SHAPE the server sent; a field the server publishes nothing
// for renders as a disabled chooser saying so, never as an empty dropdown.
//
// ⚠ **FOUR CONTROLS ARE STILL TYPED NUMBERS AND THE PO RULED THEM DROPDOWNS.**
// `absolute_session_hours`, `keep_signed_in_days`, `lockout_max_failed` and
// `lockout_minutes` arrive as `min`/`max` on the wire this hour; the SERVER
// lane is turning them into choice lists drawn from
// `05-prototype/security-redesign-2026-09-29/value-census-2026-09-29.md`.
// **This screen needs no edit on the day they land.** Typing the four lists
// here to make the screen match the drawing sooner is the precise defect
// `DEF-IDN-7501` was filed for, so it is not done.
//
// Two older rules still shape this file more than the fields do:
//   · BR-IDN-028 — the prototype's two 2FA checkboxes are NOT here. Not
//     disabled, not hidden behind a flag: absent. A control for a v2 feature
//     would imply the setting exists.
//   · BR-IDN-020 — the self-lockout guard is the SERVER's. A browser cannot
//     know its own public IP, so this screen validates CIDR SHAPE only and
//     renders the server's 409 (`errors.identity.allowlist_self_lockout`, with
//     the IP it saw) when the new list would lock the admin out.
//
// ⚠ **THE STANDING NOTE ABOUT THAT GUARD IS NOT DRAWN AND IS THEREFORE GONE.**
// *"The save is refused if your own address is not inside the ranges you
// enter."* is fifteen words of RATIONALE — why the product may refuse — which
// B14 rule 33 puts at zero words on screen. The refusal itself still renders,
// with the IP the server saw, at the moment it happens.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getSecurityPolicy,
  getSecurityPolicyAudit,
  saveSecurityPolicy,
} from "@/api/endpoints";
import type { SecurityPolicy, SecurityPolicyEdit } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { DateCell } from "@/components/DateCell";
import { CheckboxField, TextField, envelopeErrors } from "@/components/FormModal";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { Note } from "@/components/TextBits";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { FieldAppPinsCard } from "@/features/identity/FieldAppPinsCard";
import { SecurityAuditCard } from "@/features/identity/SecurityAuditCard";
import { PolicyValueField } from "@/features/identity/securityPolicyFields";

import {
  Panel,
  PanelGrid,
  RefusalNotice,
  SaveBar,
  SettingsDenied,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";

/** OQ-029 CLOSED: the audit-log viewer is S61 (tenant-scoped rows only). */
export const AUDIT_LOG_ROUTE = "/audit-log";

// `durationLabel` moved to `securityPolicyFields.tsx` with the rest of the
// value formatting (B14 rule 43). It is re-exported because two test files and
// `SignInPage` import it from here, and moving a symbol AND its importers in
// one commit is two changes wearing one hat.
export { durationLabel } from "@/features/identity/securityPolicyFields";

// ── Pure pieces ────────────────────────────────────────────────────────────

export interface SecurityDraft {
  pw_min_length: string;
  pw_require_mixed: boolean;
  pw_require_symbol: boolean;
  pw_expiry_days: string; // "" = Never (null on the wire)
  session_timeout_minutes: string;
  // CR-145-BRC08 — five settings that were platform-fixed before. Held as
  // STRINGS like every other field here: a half-typed "1" on the way to "12" is
  // not the number 1, and a control that renumbers under the typing hand is the
  // defect this shape exists to avoid.
  absolute_session_hours: string;
  keep_signed_in_offered: boolean;
  keep_signed_in_days: string;
  lockout_max_failed: string;
  lockout_minutes: string;
  field_capture_hours: string; // PO 2026-10-21 — the field app's capture life
  password_link_valid_days: string; // CR-188-BRC10 — an emailed link's life, days
  ip_allowlist: string; // comma-separated in the input, an array on the wire
}

export function draftFromPolicy(policy: SecurityPolicy): SecurityDraft {
  return {
    pw_min_length: String(policy.pw_min_length),
    pw_require_mixed: policy.pw_require_mixed,
    pw_require_symbol: policy.pw_require_symbol,
    pw_expiry_days: policy.pw_expiry_days === null ? "" : String(policy.pw_expiry_days),
    session_timeout_minutes: String(policy.session_timeout_minutes),
    absolute_session_hours: String(policy.absolute_session_hours),
    keep_signed_in_offered: policy.keep_signed_in_offered,
    keep_signed_in_days: String(policy.keep_signed_in_days),
    lockout_max_failed: String(policy.lockout_max_failed),
    lockout_minutes: String(policy.lockout_minutes),
    field_capture_hours: String(policy.field_capture_hours),
    password_link_valid_days: String(policy.password_link_valid_days),
    ip_allowlist: policy.ip_allowlist.join(", "),
  };
}

/** BR-IDN-020: comma-separated CIDRs; empty means unrestricted, not "none". */
export function parseAllowlist(raw: string): string[] {
  return raw
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => entry !== "");
}

// Shape only. WHICH ranges are acceptable — and whether they would lock the
// saving admin out — is the server's call (BR-IDN-020).
const CIDR_SHAPE = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\/(\d{1,2})$/;

export function invalidCidrs(raw: string): string[] {
  return parseAllowlist(raw).filter((entry) => {
    const match = CIDR_SHAPE.exec(entry);
    if (match === null) {
      return true;
    }
    const octets = [match[1], match[2], match[3], match[4]].map((part) => Number(part));
    const prefix = Number(match[5]);
    return octets.some((octet) => octet > 255) || prefix > 32;
  });
}

/**
 * The four settings the admin TYPES rather than picks **while the server
 * still serves them as ranges**, in the order they are drawn. Named once so
 * the diff, the render and the tests cannot disagree about which four they
 * are — the mistake `CR-145` was about.
 *
 * ⚠ **THE LIST OUTLIVES THE TYPING.** `securityChanges` uses it to decide
 * which fields go through `typedNumber` (an empty box posts nothing rather
 * than a zero), and that stays correct after the four become dropdowns: a
 * select's value is never empty, so the guard simply stops firing.
 */
export const NUMERIC_RANGE_FIELDS = [
  "absolute_session_hours",
  "keep_signed_in_days",
  "lockout_max_failed",
  "lockout_minutes",
] as const;

export type NumericRangeField = (typeof NUMERIC_RANGE_FIELDS)[number];

/**
 * A typed number, or `Number.NaN` for anything that is not one.
 *
 * ⚠ **AN EMPTY BOX IS NOT A ZERO.** `Number("")` is `0`, so a cleared field
 * would post `lockout_minutes: 0` — inside no range, refused by the server, and
 * refused with a sentence about a number the admin never typed. `NaN` is
 * dropped before the request instead, so an empty box posts nothing.
 */
function typedNumber(raw: string): number {
  const trimmed = raw.trim();
  return trimmed === "" ? Number.NaN : Number(trimmed);
}

export function securityChanges(
  draft: SecurityDraft,
  original: SecurityDraft,
): SecurityPolicyEdit {
  const changes: SecurityPolicyEdit = {};
  if (draft.pw_min_length !== original.pw_min_length) {
    changes.pw_min_length = Number.parseInt(draft.pw_min_length, 10);
  }
  if (draft.pw_require_mixed !== original.pw_require_mixed) {
    changes.pw_require_mixed = draft.pw_require_mixed;
  }
  if (draft.pw_require_symbol !== original.pw_require_symbol) {
    changes.pw_require_symbol = draft.pw_require_symbol;
  }
  if (draft.pw_expiry_days !== original.pw_expiry_days) {
    changes.pw_expiry_days =
      draft.pw_expiry_days === "" ? null : Number.parseInt(draft.pw_expiry_days, 10);
  }
  if (draft.session_timeout_minutes !== original.session_timeout_minutes) {
    changes.session_timeout_minutes = Number.parseInt(draft.session_timeout_minutes, 10);
  }
  // CR-145-BRC08's four ranges. A field the admin cleared posts nothing at all
  // rather than a zero the server would refuse in words about a value nobody
  // typed — see `typedNumber`.
  for (const field of NUMERIC_RANGE_FIELDS) {
    if (draft[field] !== original[field]) {
      const value = typedNumber(draft[field]);
      if (!Number.isNaN(value)) {
        changes[field] = value;
      }
    }
  }
  if (draft.keep_signed_in_offered !== original.keep_signed_in_offered) {
    changes.keep_signed_in_offered = draft.keep_signed_in_offered;
  }
  if (draft.field_capture_hours !== original.field_capture_hours) {
    // A dropdown: its value is never empty, so it is always a number.
    changes.field_capture_hours = Number.parseInt(draft.field_capture_hours, 10);
  }
  if (draft.password_link_valid_days !== original.password_link_valid_days) {
    changes.password_link_valid_days = Number.parseInt(draft.password_link_valid_days, 10);
  }
  if (draft.ip_allowlist !== original.ip_allowlist) {
    changes.ip_allowlist = parseAllowlist(draft.ip_allowlist);
  }
  return changes;
}

export function securityIsDirty(draft: SecurityDraft, original: SecurityDraft): boolean {
  return Object.keys(securityChanges(draft, original)).length > 0;
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface SecurityTabProps extends RegionalProps {
  readOnly: boolean; // A4: Executive = View (BR-IDN-019)
  client?: ApiClient;
}

export function SecurityTab(props: SecurityTabProps) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const fireToast = useToast();
  const queryClient = useQueryClient();
  // BR-SHL-034: an instant renders in the tenant's zone, through the shared
  // resolver — the audit card never formats a date itself.
  const { timeZone, dateFormat } = useRegional(props);

  const policyQuery = useQuery({
    queryKey: queryKeys.securityPolicy,
    queryFn: () => getSecurityPolicy(client),
  });

  // The Audit log card's own read. A SEPARATE query on purpose: the policy is
  // what the form edits and this is a record of what was edited, so one of
  // them failing must not take the other's screen down with it (`FailedWith
  // Retry` on the whole tab for an audit read that timed out would hide eight
  // working controls behind a list of five rows).
  const auditQuery = useQuery({
    queryKey: queryKeys.securityPolicyAudit,
    queryFn: () => getSecurityPolicyAudit(client),
    retry: false,
  });

  const [edits, setEdits] = useState<SecurityDraft | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const save = useMutation({
    mutationFn: (values: SecurityPolicyEdit) => saveSecurityPolicy(values, client),
    onSuccess: (saved: SecurityPolicy) => {
      queryClient.setQueryData(queryKeys.securityPolicy, saved);
      // The save IS what puts a row in the card below it (BR-TEN-016, written
      // server-side). Not invalidating here would leave a clerk looking at a
      // list that does not contain the change they just made — which reads as
      // "it was not recorded".
      void queryClient.invalidateQueries({ queryKey: queryKeys.securityPolicyAudit });
      setEdits(null);
      setFieldErrors({});
      setRefusal(null);
      fireToast(t("settings.security.saved"));
    },
    onError: (error: unknown) => {
      if (isApiError(error)) {
        const mapped = envelopeErrors(formErrorEnvelope(error), (key, params) => t(key, params));
        setFieldErrors(mapped.fields);
      }
      // BR-IDN-020: the self-lockout refusal renders here, naming the IP the
      // SERVER saw — nothing was saved.
      setRefusal(refusalOf(error, t));
    },
  });

  if (policyQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (policyQuery.data === undefined) {
    if (isPermissionDenied(policyQuery.error)) {
      // US-IDN-010 TC-8: a Billing Clerk gets A18 §6, not an empty form.
      return <SettingsDenied helper={t("settings.security.denied")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.security.failedTitle")}
        reason={apiErrorText(policyQuery.error, t)}
        onRetry={() => void policyQuery.refetch()}
      />
    );
  }

  const original = draftFromPolicy(policyQuery.data);
  const draft = edits ?? original;
  const limits = policyQuery.data.limits;
  function patch(change: Partial<SecurityDraft>): void {
    setEdits({ ...draft, ...change });
  }

  const badCidrs = invalidCidrs(draft.ip_allowlist);

  function handleSave(): void {
    setRefusal(null);
    if (badCidrs.length > 0) {
      // US-IDN-010 TC-4: inline, nothing posted.
      setFieldErrors({
        ip_allowlist: t("settings.security.badCidr", { value: badCidrs.join(", ") }),
      });
      return;
    }
    setFieldErrors({});
    save.mutate(securityChanges(draft, original));
  }

  return (
    <div className="settings-tab">
      {/* Three cards, one row, four / four / three controls. `.settings-grid`
          is `repeat(auto-fit, minmax(var(--panel-min, 320px), 1fr))` with
          `align-items: start` — each card its own height rather than stretched
          to its tallest neighbour, which is how the drawing shows them.

          ⚠ **`min="288px"` IS LOAD-BEARING AT 1280 AND WAS FOUND BY THE
          PHOTOGRAPH, NOT BY A TEST.** The PO approved this screen at 1280
          with three cards in one row. At the kit's 320px default they do not
          fit in the REAL frame: 1280 − 240 (sidebar) − 48 (`.view` padding)
          = 992px against 3 × 320 + 2 × 24 = 1008px, sixteen pixels short, so
          the third card dropped under the first. 288 makes it 912. The
          columns still grow to `1fr`, so nothing about the 1440 shape moves,
          and every other caller of `PanelGrid` keeps the 320px default. */}
      <PanelGrid min="288px">
        <Panel
          accent
          title={t("settings.security.password")}
          hint={t("settings.security.passwordHint")}
        >
          <PolicyValueField
            field="pw_min_length"
            limit={limits.pw_min_length}
            value={draft.pw_min_length}
            onChange={(v) => patch({ pw_min_length: v })}
            {...(fieldErrors.pw_min_length === undefined
              ? {}
              : { error: fieldErrors.pw_min_length })}
          />
          <CheckboxField
            id="pw_require_mixed"
            label={t("settings.security.requireMixed")}
            checked={draft.pw_require_mixed}
            onChange={(checked) => patch({ pw_require_mixed: checked })}
          />
          <CheckboxField
            id="pw_require_symbol"
            label={t("settings.security.requireSymbol")}
            checked={draft.pw_require_symbol}
            onChange={(checked) => patch({ pw_require_symbol: checked })}
          />
          <PolicyValueField
            field="pw_expiry_days"
            limit={limits.pw_expiry_days}
            value={draft.pw_expiry_days}
            onChange={(v) => patch({ pw_expiry_days: v })}
            {...(fieldErrors.pw_expiry_days === undefined
              ? {}
              : { error: fieldErrors.pw_expiry_days })}
          />
          {/* ONE note box, three sentences — as drawn. BR-IDN-016's "the new
              rules bite on the next password set" and the two facts that are
              still platform-fixed (the last-5 history and the 7-day temporary
              password). They are here rather than in a card about sessions
              because they are about PASSWORDS; that move is the redesign's,
              and their being here is what stops their absence from the
              controls reading as an omission. */}
          <Note>
            {t("settings.security.appliesNext")} {t("settings.security.fixedValues")}
          </Note>
        </Panel>

        <Panel
          accent
          title={t("settings.security.sessions")}
          hint={t("settings.security.sessionsHint")}
        >
          <PolicyValueField
            field="session_timeout_minutes"
            limit={limits.session_timeout_minutes}
            value={draft.session_timeout_minutes}
            onChange={(v) => patch({ session_timeout_minutes: v })}
            {...(fieldErrors.session_timeout_minutes === undefined
              ? {}
              : { error: fieldErrors.session_timeout_minutes })}
          />
          <PolicyValueField
            field="absolute_session_hours"
            limit={limits.absolute_session_hours}
            value={draft.absolute_session_hours}
            onChange={(v) => patch({ absolute_session_hours: v })}
            rangeHelpKey="settings.security.absoluteHoursHelp"
            // The ONE help line the redesign keeps: a clerk cannot tell from
            // the control that a change here does not shorten a session
            // already running.
            help={t("settings.security.absoluteHoursNote")}
            {...(fieldErrors.absolute_session_hours === undefined
              ? {}
              : { error: fieldErrors.absolute_session_hours })}
          />
          <CheckboxField
            id="keep_signed_in_offered"
            label={t("settings.security.keepSignedInOffered")}
            checked={draft.keep_signed_in_offered}
            onChange={(checked) => patch({ keep_signed_in_offered: checked })}
          />
          <PolicyValueField
            field="keep_signed_in_days"
            limit={limits.keep_signed_in_days}
            value={draft.keep_signed_in_days}
            onChange={(v) => patch({ keep_signed_in_days: v })}
            rangeHelpKey="settings.security.keepSignedInDaysHelp"
            {...(fieldErrors.keep_signed_in_days === undefined
              ? {}
              : { error: fieldErrors.keep_signed_in_days })}
          />
          {/* PO 2026-10-21, *"this should come from settings"* — how long a
              field app handset keeps capturing, and renewing its sign-in,
              without a password. A sign-in LENGTH, so it sits with the other
              session lengths. A dropdown the server publishes (1 hour to 30
              days); no help line, because the value carries its unit. */}
          <PolicyValueField
            field="field_capture_hours"
            limit={limits.field_capture_hours}
            value={draft.field_capture_hours}
            onChange={(v) => patch({ field_capture_hours: v })}
            {...(fieldErrors.field_capture_hours === undefined
              ? {}
              : { error: fieldErrors.field_capture_hours })}
          />
          {/* CR-188-BRC10 (PO 2026-10-22, "don't do any hardcoding") — how
              long an emailed one-time sign-in link works. Seeded 7 days. */}
          <PolicyValueField
            field="password_link_valid_days"
            limit={limits.password_link_valid_days}
            value={draft.password_link_valid_days}
            onChange={(v) => patch({ password_link_valid_days: v })}
            {...(fieldErrors.password_link_valid_days === undefined
              ? {}
              : { error: fieldErrors.password_link_valid_days })}
          />
        </Panel>

        <Panel
          accent
          title={t("settings.security.signingIn")}
          hint={t("settings.security.signingInHint")}
        >
          <PolicyValueField
            field="lockout_max_failed"
            limit={limits.lockout_max_failed}
            value={draft.lockout_max_failed}
            onChange={(v) => patch({ lockout_max_failed: v })}
            rangeHelpKey="settings.security.lockoutAttemptsHelp"
            {...(fieldErrors.lockout_max_failed === undefined
              ? {}
              : { error: fieldErrors.lockout_max_failed })}
          />
          <PolicyValueField
            field="lockout_minutes"
            limit={limits.lockout_minutes}
            value={draft.lockout_minutes}
            onChange={(v) => patch({ lockout_minutes: v })}
            rangeHelpKey="settings.security.lockoutMinutesHelp"
            {...(fieldErrors.lockout_minutes === undefined
              ? {}
              : { error: fieldErrors.lockout_minutes })}
          />
          {/* NOT a `PolicyValueField`: the allowlist is free text a person
              types, has no server-published limit, and never becomes a
              dropdown. `(optional)` left the label — we mark what is
              required, not what is not. */}
          <TextField
            id="ip_allowlist"
            label={t("settings.security.allowlist")}
            value={draft.ip_allowlist}
            onChange={(v) => patch({ ip_allowlist: v })}
            placeholder="203.0.113.0/24"
            help={t("settings.security.allowlistHelp")}
            {...(fieldErrors.ip_allowlist === undefined
              ? {}
              : { error: fieldErrors.ip_allowlist })}
          />
        </Panel>
      </PanelGrid>

      <RefusalNotice refusal={refusal} />

      <SaveBar
        saveLabel={t("settings.security.save")}
        working={save.isPending}
        dirty={securityIsDirty(draft, original)}
        readOnly={props.readOnly}
        // A4: Settings = View for an Executive (BR-IDN-019/BR-SHL-025).
        readOnlyReason={t("settings.security.readOnlyReason")}
        onSave={handleSave}
        onDiscard={() => {
          setEdits(null);
          setFieldErrors({});
          setRefusal(null);
        }}
      />

      {/* Full width, BELOW Save — the PO's own arrangement, 2026-09-29:
          *"keep it here only in this screen"* and *"i only need bigger real
          estate for audit logs - can you give a card layout for it"*. */}
      <SecurityAuditCard
        title={t("settings.security.audit")}
        hint={t("settings.security.auditHint")}
        viewAllTo={tenantPath(AUDIT_LOG_ROUTE)}
        viewAllLabel={t("settings.security.auditViewAll")}
        rows={auditQuery.data}
        isPending={auditQuery.isPending}
        failure={auditQuery.isError ? t("settings.security.auditFailed") : null}
        onRetry={() => void auditQuery.refetch()}
        emptyText={t("settings.security.auditEmpty")}
        columns={{
          when: t("settings.security.auditWhen"),
          who: t("settings.security.auditWho"),
          setting: t("settings.security.auditSetting"),
          change: t("settings.security.auditChange"),
        }}
        formatWhen={(iso) => (
          <DateCell value={iso} timeZone={timeZone} dateFormat={dateFormat} withTime />
        )}
        t={(key, params) => t(key, params)}
      />

      {/* OQ-FLD-12797 (PO 2026-10-24, *"use settings - security values set
          in staff portal"*): the keys the field app trusts. UNDER the audit
          card so the arrangement the PO approved on 2026-09-29 does not move;
          it saves itself, so it sits outside the three cards and their Save.
          ⚠ HIDDEN WHILE PINNING IS DORMANT (CR-195-BRC10, PO 2026-10-28
          "start A1"): no field-app build pins, so the card would be a live
          control that does nothing (law 2's mirror). The server's platform
          flag brings it back; the stored lists and the endpoint stay. */}
      {policyQuery.data.field_app_pinning_enabled === true ? (
        <FieldAppPinsCard
          readOnly={props.readOnly}
          readOnlyReason={t("settings.security.readOnlyReason")}
          client={client}
          timeZone={timeZone}
          dateFormat={dateFormat}
        />
      ) : null}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-IDN-010@493ea2f (story+rules snapshot hash — EP-IDN-04) · CR-155-BRC09
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane) · AMENDED 2026-09-28 (CR-145-BRC08, SESS-FRONTEND) · REDESIGNED 2026-09-29 by lane SEC-REDESIGN from the PO-approved images in 05-prototype/security-redesign-2026-09-29/ (B14 rule 42)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E3 "View all →" targets S61, which the audit module owns · E4 the
//   tab is System-Admin-editable / Executive-read-only per BR-IDN-019 and
//   `readOnly` is supplied by the Settings frame · E5 (CR-155-BRC09) FOUR of
//   the eight values are still typed numbers because the server serves them as
//   `min`/`max`; the PO ruled every value a dropdown and this lane does not
//   type a list to satisfy it — they become dropdowns with no edit here the
//   moment `SETTING_LIMITS` publishes their choices · E6 (CR-155-BRC09) the
//   Audit log card's read `GET /settings/security-policy/audit` is the SERVER
//   lane's and is not on the branch; the card renders its failure state until
//   it answers, never zero rows. Both reported.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
