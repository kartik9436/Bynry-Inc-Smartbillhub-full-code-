// ── Trace ──────────────────────────────────────────────
// Story:    US-IDN-010 (EP-IDN-04 §Stories)  Screens: S8 (Settings → Security)
// Change:   CR-155-BRC09 — the Settings → Security redesign the PO approved on
//           2026-09-29 (`05-prototype/security-redesign-2026-09-29/`).
// Rules:    BR-IDN-025 · BR-IDN-026 as amended by CR-145-BRC08 (what an admin
//           may choose lives ONCE, in `services.SETTING_LIMITS`, and is served
//           beside the values) · B14 rule 8 (one chevron; zero native selects)
//           · B14 rule 21 (Tailwind utilities, no stylesheet class) ·
//           B14 rule 31 (no database id is the visible value of a field) ·
//           B14 rule 43 (a piece of UI is a COMPONENT, never inlined in a
//           page) · BR-SHL-025 (a control that cannot act says why)
// ───────────────────────────────────────────────────────
// ONE CONTROL THAT RENDERS WHATEVER THE SERVER PUBLISHES, AND ONE FORMATTER
// THAT EVERY SURFACE SHOWING A POLICY VALUE GOES THROUGH.
//
// ⚠ **WHY THIS FILE EXISTS AT ALL, IN ONE SENTENCE: `DEF-IDN-7501`.** The
// Security tab carried `[8, 10, 12]` and `[null, 90, 180]` as TypeScript
// literals for weeks, under a comment calling them *"the server's validated
// tuples"* — a claim nothing re-checked (hard-won law 1), and one no gate in
// this repo CAN check, because comparing a TypeScript literal with a Python
// tuple is not a thing any of them do. The day the server took a
// 14-character minimum, this screen would never have offered it: `tsc` green,
// eslint green, every test green, and a clerk simply unable to choose a value
// the product accepts. That is the SignupWizard eleventh-service failure
// (CLAUDE.md, hard-won law 2) wearing different clothes.
//
// **So nothing here types a list.** `optionsFromLimit` reads the entry the
// server sent and builds the dropdown from it, and `PolicyValueField` reads
// the SHAPE of that entry and picks the control:
//
//     { choices: [...] }        → a dropdown of exactly those values
//     { min: n, max: m }        → a number the admin types, with the server's
//                                 own range stated as the help line
//     anything else, or absent  → a DISABLED chooser holding today's value
//
// ⚠ **THE THIRD BRANCH IS THE ONE WORTH READING.** It is not defensive
// tidiness: `DEF-IDN-7501`'s own repair note says reading a key the server
// does not send *"would put an empty dropdown on a live screen, which is a
// worse failure than a stale one"*. An empty dropdown is a live control that
// cannot be used and says nothing about why — law 2's mirror. A disabled
// chooser still SHOWS the value in force and states that it cannot be changed
// here (BR-SHL-025), which is the honest shape of "the server did not publish
// this".
//
// ⚠ **AND THE TWO SHAPES ARE A MOMENT IN TIME, NOT A DESIGN.** The PO ruled
// on 2026-09-29 that **every value on this screen is a dropdown** (verbatim:
// *"(a) Short dropdown, list chosen from real use - Dropdown"*), and the
// SERVER lane is turning `absolute_session_hours`, `keep_signed_in_days`,
// `lockout_max_failed` and `lockout_minutes` from ranges into choice lists
// drawn from `05-prototype/security-redesign-2026-09-29/value-census-2026-09-29.md`.
// **This file needs no edit on the day they land**: those four entries start
// arriving with `choices`, the first branch takes them, and their help lines
// go — because a dropdown IS its range, which is the drawing's own reason for
// deleting every *"Between 4 and 12 hours."* line.
//
// ⚠ **`securityValueLabel` IS THE OTHER HALF, AND IT IS WHY THE AUDIT CARD
// CANNOT DRIFT FROM THE CONTROLS.** The approved drawing requires the audit
// log to render a value *"the way the control renders it"* — `480 minutes →
// 60 minutes`, never a raw integer. A second formatter in the audit card
// would satisfy that on the day it was written and stop satisfying it the
// first time either side changed. There is one function, both surfaces call
// it, and a test asserts the dropdown's own option text equals what the audit
// card prints for the same number.
import { useTranslation } from "react-i18next";

import { SelectField, TextField } from "@/components/FormModal";

/**
 * Every setting the Security tab can show a VALUE for — the ten columns of
 * `security_policies` a System Admin edits, plus nothing else.
 *
 * It is a closed union rather than `string` so that a new setting cannot be
 * added to the audit card, or to a control, without this file being told how
 * to render it: `securityValueLabel`'s switch is exhaustive and `tsc` refuses
 * an unhandled member. That is the check `DEF-IDN-7501` did not have.
 */
export const SECURITY_SETTING_KEYS = [
  "pw_min_length",
  "pw_require_mixed",
  "pw_require_symbol",
  "pw_expiry_days",
  "session_timeout_minutes",
  "absolute_session_hours",
  "keep_signed_in_offered",
  "keep_signed_in_days",
  "lockout_max_failed",
  "lockout_minutes",
  "ip_allowlist",
  "field_capture_hours",
  // CR-188-BRC10 — an emailed sign-in link's life, days (PO 2026-10-22).
  "password_link_valid_days",
] as const;

export type SecuritySettingKey = (typeof SECURITY_SETTING_KEYS)[number];

export type Translator = (key: string, params?: Record<string, unknown>) => string;

/** The `settings.security.*` key whose text is the control's own label. The
 *  audit card names a setting with the SAME key, so the SETTING column and the
 *  control above it cannot say two different words for one thing. */
export const SECURITY_SETTING_LABEL_KEY: Record<SecuritySettingKey, string> = {
  pw_min_length: "settings.security.minLength",
  pw_require_mixed: "settings.security.requireMixed",
  pw_require_symbol: "settings.security.requireSymbol",
  pw_expiry_days: "settings.security.expiry",
  session_timeout_minutes: "settings.security.sessionTimeout",
  absolute_session_hours: "settings.security.absoluteHours",
  keep_signed_in_offered: "settings.security.keepSignedInOffered",
  keep_signed_in_days: "settings.security.keepSignedInDays",
  lockout_max_failed: "settings.security.lockoutAttempts",
  lockout_minutes: "settings.security.lockoutMinutes",
  ip_allowlist: "settings.security.allowlist",
  field_capture_hours: "settings.security.fieldCapture",
  password_link_valid_days: "settings.security.linkValidDays",
};

/**
 * A duration in minutes, named the way a person says it.
 *
 * ⚠ **THIS REPLACED A LABEL-PER-VALUE CATALOGUE KEY, AND THAT WAS THE SAME
 * DEFECT ONE LAYER DOWN.** The tab used to render
 * `` t(`settings.security.timeout.${minutes}`) `` against four keys named for
 * the four values — a hand-typed list wearing a catalogue's clothes. The day
 * the server offers 15 or 45, that call renders **the key itself** on screen:
 * not an error, not a blank, the literal string `settings.security.timeout.15`.
 * Deriving the label from the number cannot fail that way.
 *
 * ⚠ **IT MOVED HERE FROM `SettingsSecurityTab.tsx` UNCHANGED (B14 rule 43).**
 * A formatter the audit card and three controls all need is not page code.
 */
export function durationLabel(minutes: number, t: Translator): string {
  return minutes % 60 === 0
    ? t("settings.security.optionHours", { count: minutes / 60 })
    : t("settings.security.optionMinutes", { count: minutes });
}

/**
 * ONE value, rendered the way this screen renders it — the option text in a
 * dropdown AND the before/after in the audit card, from one function.
 *
 * ⚠ **THE UNIT IS INSIDE THE VALUE AND THAT IS THE POINT OF THE REDESIGN.**
 * `12 hours`, `5 tries`, `15 minutes`, `30 days`, `8 characters`. It is what
 * lets every label stay a name of three words or fewer (B14 rule 33) and what
 * let the *"Between 4 and 12 hours."* help lines go: a reader gets the unit
 * from the value they are choosing rather than from a sentence under it.
 *
 * ⚠ **`null` IS A REAL VALUE FOR `pw_expiry_days` AND MEANS NEVER** — not
 * "unset", not "empty". It is the seeded default (BR-IDN-025).
 */
export function securityValueLabel(
  field: SecuritySettingKey,
  value: unknown,
  t: Translator,
): string {
  switch (field) {
    case "pw_min_length":
      return t("settings.security.optionCharacters", { count: Number(value) });
    case "pw_expiry_days":
      return value === null || value === "" || value === undefined
        ? t("settings.security.expiryNever")
        : t("settings.security.expiryDays", { days: Number(value) });
    case "session_timeout_minutes":
    case "lockout_minutes":
      return durationLabel(Number(value), t);
    case "absolute_session_hours":
      return t("settings.security.optionHours", { count: Number(value) });
    case "keep_signed_in_days":
    case "password_link_valid_days":
      return t("settings.security.optionDays", { count: Number(value) });
    case "lockout_max_failed":
      return t("settings.security.optionTries", { count: Number(value) });
    case "field_capture_hours": {
      // HOURS on the wire (PO 2026-10-21). Whole days read as days — `7 days`,
      // not `168 hours` — and the rest as hours (`36 hours`, `1 hour`).
      const hours = Number(value);
      return hours % 24 === 0
        ? t("settings.security.optionDays", { count: hours / 24 })
        : t("settings.security.optionHours", { count: hours });
    }
    case "pw_require_mixed":
    case "pw_require_symbol":
    case "keep_signed_in_offered":
      return value === true || value === "true"
        ? t("settings.security.on")
        : t("settings.security.off");
    case "ip_allowlist": {
      // The audit card shows what was there before a list was first set, and
      // "nothing" is a fact a clerk must be able to read — a blank cell reads
      // as a rendering bug. The controls never reach this branch: an empty
      // allowlist is an empty text box, which says it itself.
      const text = Array.isArray(value) ? value.join(", ") : String(value ?? "");
      return text.trim() === "" ? t("settings.security.addressesEmpty") : text;
    }
  }
}

// ── What the server published, read by SHAPE ───────────────────────────────

/** A closed list the admin picks from. `null` is a legal member (`Never`). */
export interface PolicyChoiceLimit {
  choices: (number | null)[];
}
/** A floor and a ceiling the admin types between. */
export interface PolicyRangeLimit {
  min: number;
  max: number;
}

/**
 * The `choices` array, or `null` when this entry is not a choice list.
 *
 * ⚠ **IT READS THE SERVED OBJECT AND NOT THE TYPESCRIPT TYPE.** The two are
 * allowed to disagree, and while the server lane is mid-flight they DO: a
 * declared `SecurityPolicyRange` arrives carrying `choices` the hour the four
 * lists land, and `tsc` cannot see that because extra keys on a JSON response
 * are simply invisible to it (the `CommitManifest` lesson, decision log
 * 2026-09-28). Narrowing on the runtime value is what lets the screen follow
 * the server on the day it moves rather than on the day somebody remembers.
 */
export function limitChoices(limit: unknown): (number | null)[] | null {
  if (typeof limit !== "object" || limit === null) {
    return null;
  }
  const candidate = (limit as { choices?: unknown }).choices;
  return Array.isArray(candidate) ? (candidate as (number | null)[]) : null;
}

/** The `min`/`max` pair, or `null` when this entry is not a range. */
export function limitRange(limit: unknown): PolicyRangeLimit | null {
  if (typeof limit !== "object" || limit === null) {
    return null;
  }
  const { min, max } = limit as { min?: unknown; max?: unknown };
  return typeof min === "number" && typeof max === "number" ? { min, max } : null;
}

/**
 * The dropdown's options, built from the server's list and labelled by the one
 * formatter. The wire value of `null` (`Never`) travels as `""`, which is what
 * `SecurityDraft` already holds and what `securityChanges` already turns back
 * into `null` — a `<select>` has no null.
 */
export function optionsFromLimit(
  field: SecuritySettingKey,
  choices: (number | null)[],
  t: Translator,
): { value: string; label: string }[] {
  return choices.map((choice) => ({
    value: choice === null ? "" : String(choice),
    label: securityValueLabel(field, choice, t),
  }));
}

// ── The control ────────────────────────────────────────────────────────────

export interface PolicyValueFieldProps {
  field: SecuritySettingKey;
  /** Exactly what the server sent under `limits[field]`, untouched. */
  limit: unknown;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  /** Rendered under the control. The redesign keeps exactly one of these —
   *  *"Applies to the next sign-in."* on the hard limit — because it is a fact
   *  a clerk cannot read off the control. */
  help?: string;
  /** The range help line, keyed by `{{min}}`/`{{max}}`. Used ONLY by the range
   *  branch, and it disappears with that branch the day the list lands. */
  rangeHelpKey?: string;
  disabled?: boolean;
}

/**
 * One setting, rendered by the shape of the limit the server published.
 *
 * ⚠ **NEVER A BARE `<select>` — B14 rule 8's chevron gate stands at zero
 * native selects across the product**, so the kit's `SelectField` is the only
 * dropdown this screen may draw. Same for `TextField`: the range branch needs
 * `aria-describedby` wired to the error slot, which is what
 * `securityRangeRefusal.dom.test.tsx` follows to prove an out-of-range refusal
 * lands on the control the server named and on no other.
 */
export function PolicyValueField(props: PolicyValueFieldProps) {
  const { t } = useTranslation();
  const label = t(SECURITY_SETTING_LABEL_KEY[props.field]);
  const choices = limitChoices(props.limit);

  if (choices !== null) {
    return (
      <SelectField
        id={props.field}
        label={label}
        value={props.value}
        onChange={props.onChange}
        options={optionsFromLimit(props.field, choices, (key, params) => t(key, params))}
        {...(props.help === undefined ? {} : { help: props.help })}
        {...(props.error === undefined ? {} : { error: props.error })}
        {...(props.disabled === true ? { disabled: true } : {})}
      />
    );
  }

  const range = limitRange(props.limit);
  if (range !== null && props.rangeHelpKey !== undefined) {
    // ⚠ THE INTERIM SHAPE, AND IT IS HONEST RATHER THAN CONVENIENT. The PO
    // ruled every value a dropdown; four of them are still ranges on the wire
    // this hour. A screen that drew a dropdown anyway would have to type the
    // list itself — which is the whole defect this file was written to end.
    // So it draws what the server can actually back, states the range as the
    // server's own numbers, and changes shape by itself the day the list lands.
    // ⚠ THE RANGE LINE AND THE KEPT HELP LINE ARE BOTH FACTS AND BOTH BELONG
    // TO THE CONTROL, so they share one `help` slot rather than one of them
    // being dropped. B14 rule 33: *two sentences of six beat one sentence of
    // twelve.* The range half goes the day the list lands; the other stays.
    const rangeText = t(props.rangeHelpKey, { min: range.min, max: range.max });
    return (
      <TextField
        id={props.field}
        label={label}
        value={props.value}
        onChange={props.onChange}
        numeric
        help={props.help === undefined ? rangeText : `${rangeText} ${props.help}`}
        {...(props.error === undefined ? {} : { error: props.error })}
        {...(props.disabled === true ? { disabled: true } : {})}
      />
    );
  }

  // Neither shape — the server published nothing this screen can build a
  // control from. It shows the value in force and says it cannot be changed
  // here (BR-SHL-025), rather than an empty dropdown that looks usable.
  return (
    <SelectField
      id={props.field}
      label={label}
      value={props.value}
      onChange={props.onChange}
      options={[{ value: props.value, label: securityValueLabel(props.field, props.value, t) }]}
      disabled
      help={t("settings.security.choiceUnavailable")}
      {...(props.error === undefined ? {} : { error: props.error })}
    />
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-155-BRC09 (SEC-REDESIGN lane) · US-IDN-010@493ea2f
// generated: 2026-09-29 by lane SEC-REDESIGN, built from the approved images
//   in 05-prototype/security-redesign-2026-09-29/ (B14 rule 42)
// exceptions: the four ranges CR-145 left as `min`/`max` are drawn by the
//   range branch until the SERVER lane publishes their choice lists; the PO's
//   2026-09-29 ruling says dropdown and this lane does not type a list to
//   satisfy it — reported.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
