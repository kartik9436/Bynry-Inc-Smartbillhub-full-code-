// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-039 (EP-RBS-05) — CR-075 wave T, the **Change scope** commit
//          that stopped refusing. Screens: RBS-004.3.
// Rules:   `BR-RBS-042` (a tenant sets input VALUES and nothing else; a domain
//          per input, resolved per tenant; one value, several, or *all*, and
//          *all* is stored as THE WORD) · `BR-RBS-038` (every edit writes a
//          version) · `BR-RBS-036` (the trust ratchet, now fired by a changed
//          input) · B14 rule 9 (chips, never a wall of checkboxes) · rule 31
//          (no database id is the visible value of a field) · `NFR-3`.
// Defects: DEF-RBS-4338 (a signed rule said a utility sets a runbook's inputs
//          and there was nowhere to save one).
// Tests:   src/features/runbooks/setupScope.test.ts
// ───────────────────────────────────────────────────────
/**
 * The draft **Change scope** collects, and the `PUT` body it becomes.
 *
 * Kept out of the page for `setupLimits.ts`'s reason: a test can then assert a
 * RULE — that *all* leaves as the word, that an untouched input sends nothing,
 * that an input this screen cannot edit is never sent at all — rather than an
 * impression of a rendered modal.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ***all* IS A RULE AND IT LEAVES THIS FILE AS A RULE**
 * ══════════════════════════════════════════════════════════════════════════
 * `BR-RBS-042` clause 1. The draft holds a MODE — *all* or *some* — beside the
 * chosen values, and `scopeToWire` sends the word `"all"` when the mode is
 * *all*, never the chips that happen to be on screen. Sending the expansion is
 * the failure the whole rule exists to stop: a utility that adds Trash next
 * month would be silently outside every runbook set to *all*, with no error, no
 * screen change and nothing anywhere to see.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHAT THIS SCREEN CAN AND CANNOT EDIT, COUNTED RATHER THAN IMPLIED
 * ══════════════════════════════════════════════════════════════════════════
 * `editableKind` sorts every declared input into one of five, and two of them
 * are deliberate refusals drawn WITH their reason (B14: a control a user may
 * not use is drawn disabled with its reason, never hidden):
 *
 *   `choice`   an enum over the runbook's own `choices` — a select.
 *   `domain`   an input over a BOUNDED tenant-resolved domain — chips + *all*
 *              when it takes several, a select when it takes one.
 *   `scalar`   money · integer · days · percent · text — a text box.
 *   `switch`   a toggle.
 *   `held`     everything else, and the reason travels with it:
 *                • an UNBOUNDED domain (`account`) — a picker over 40,000 rows
 *                  is the unpaginated dropdown `NFR-3` forbids, and it needs a
 *                  searching picker this kit does not have;
 *                • `ref:setting` — Settings owns the value and duplicating one
 *                  is how a utility ends up with two ladders (`RBR-03`);
 *                • `window` and `file` — a range picker and an upload control,
 *                  neither of which is in the kit (`09-component-inventory.md`
 *                  part 2 marks both ⬜).
 *
 * ⚠ **A `held` INPUT IS STILL DRAWN, AND IT IS NEVER SENT.** `scopeToWire`
 * carries only what a person could actually change, so a round trip through
 * this modal cannot rewrite a value the screen could not show them.
 */
import type { RunbookEditBody, WireParameterSetting } from "./setupWire";

/** Which control an input gets, or why it gets none. */
export type ScopeKind = "choice" | "domain" | "scalar" | "switch" | "held";

/** Why an input is drawn disabled. A key, because the sentence is chrome. */
export type ScopeHold = "unbounded" | "settings" | "noControl";

/** The domains whose whole membership is safe to put in a picker.
 *
 *  ⚠ **THE LIST IS HERE AND NOT INFERRED FROM THE ROW COUNT.** A domain that
 *  happens to hold three rows today is not bounded; `account` holds three rows
 *  in a demo tenant and 40,000 in a real one, and a client that decided by
 *  counting page 1 would draw a perfectly good picker right up to the customer
 *  who needs it most. `domains.DOMAIN_IS_BOUNDED` is the server's own statement
 *  of the same fact. */
export const BOUNDED_DOMAINS: readonly string[] = ["service", "period"];

export function editableKind(parameter: WireParameterSetting): ScopeKind {
  if (parameter.type === "ref:setting") return "held";
  if (parameter.type === "toggle") return "switch";
  if (parameter.domain !== null) {
    return BOUNDED_DOMAINS.includes(parameter.domain) ? "domain" : "held";
  }
  if (parameter.choices.length > 0) return "choice";
  if (["money", "integer", "days", "percent", "text"].includes(parameter.type)) return "scalar";
  return "held";
}

export function holdReason(parameter: WireParameterSetting): ScopeHold {
  if (parameter.type === "ref:setting") return "settings";
  if (parameter.domain !== null && !BOUNDED_DOMAINS.includes(parameter.domain)) {
    return "unbounded";
  }
  return "noControl";
}

/** One input, as the modal holds it while a person is editing.
 *
 *  `mode` is `BR-RBS-042` clause 1 made visible: *All* is not one of the
 *  values, it is a different answer to a different question. */
export interface ScopeEntry {
  name: string;
  kind: ScopeKind;
  multi: boolean;
  mode: "all" | "some";
  /** The chosen values, for a `multi` input. */
  values: string[];
  /** The single value, as typed or picked. Strings on the client for
   *  `setupLimits.ts`'s reason: a numeric input round-tripped through `Number`
   *  loses the difference between an empty box and a zero. */
  value: string;
}

export type ScopeDraft = Record<string, ScopeEntry>;

/** What the modal opens with — the runbook's own current values, never a
 *  remembered draft. A form seeded from anything but the server is a form that
 *  can silently re-send a stale answer. */
export function scopeDraft(parameters: readonly WireParameterSetting[]): ScopeDraft {
  const draft: ScopeDraft = {};
  for (const parameter of parameters) {
    const kind = editableKind(parameter);
    const isAll = parameter.value === "all";
    draft[parameter.name] = {
      name: parameter.name,
      kind,
      multi: parameter.multi,
      mode: isAll ? "all" : "some",
      values: Array.isArray(parameter.value) ? parameter.value.map(String) : [],
      value:
        parameter.value === null || parameter.value === undefined || isAll
          ? ""
          : typeof parameter.value === "boolean"
            ? String(parameter.value)
            : Array.isArray(parameter.value)
              ? ""
              : String(parameter.value),
    };
  }
  return draft;
}

/**
 * The `PUT` body — **the whole document, and only what a person could change.**
 *
 * ⚠ **THE WHOLE DOCUMENT AND NOT A DELTA**, matching `services.
 * _validated_parameters`: a delta has no way to say *put this input back to
 * what it shipped with*, because `{"services": null}` and *do not mention
 * services* are indistinguishable.
 *
 * ⚠ **AND *all* GOES AS THE WORD.** This is the one line the whole rule turns
 * on, and the tempting alternative — sending `entry.values` because they are
 * right there — passes every test that does not enable a service afterwards.
 */
export function scopeToWire(
  draft: ScopeDraft,
  parameters: readonly WireParameterSetting[],
): RunbookEditBody {
  const out: Record<string, unknown> = {};
  for (const parameter of parameters) {
    const entry = draft[parameter.name];
    if (entry === undefined || entry.kind === "held") continue;
    if (entry.multi) {
      out[parameter.name] = entry.mode === "all" ? "all" : entry.values;
      continue;
    }
    if (entry.kind === "switch") {
      out[parameter.name] = entry.value === "true";
      continue;
    }
    out[parameter.name] = entry.value.trim() === "" ? null : entry.value.trim();
  }
  return { parameters: out };
}

/* ── the Settings-owned inputs (`OQ-WRK-12793` → A, PO 2026-10-13) ──────── */

/** The inputs on this runbook that Settings owns. */
export function settingsOwnedParameters(
  parameters: readonly WireParameterSetting[],
): WireParameterSetting[] {
  return parameters.filter((one) => one.type === "ref:setting" && one.setting_key !== null);
}

/** One `ref:setting` input, as the screens draw it. */
export interface SettingsFieldRow {
  name: string;
  label: string;
  setting: string;
}

/** `WireParameterSetting[]` → the rows `RunbookSettingsFields` draws. */
export function settingsFieldRows(
  parameters: readonly WireParameterSetting[],
): SettingsFieldRow[] {
  return settingsOwnedParameters(parameters).map((one) => ({
    name: one.name,
    label: one.label,
    setting: one.setting_key ?? "",
  }));
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-039 (EP-RBS-05; CR-075 wave T) · BR-RBS-042 (PO 2026-09-06) · B14 rules 9 and 31 · NFR-3
// generated: 2026-09-07 by the CR-075 wave T build lane
// checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler, never npx) · vitest setupScope.test.ts
// exceptions: an UNBOUNDED domain, `window`, `file` and `ref:setting` are drawn DISABLED with their reason rather than hidden — each names why in `holdReason`, and none of them is ever sent
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
