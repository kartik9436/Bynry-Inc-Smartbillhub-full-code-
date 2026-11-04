// ── Trace ──────────────────────────────────────────────
// Change:   B14 rule 36 (PO 2026-09-04) — ⚠ breach **(d)**, named in the rule
//           itself: *"the portal's Overview drew on/off as bordered
//           word-buttons rather than a control"*. The rule's own remedy:
//           **"compose the kit. Where the kit lacks a piece, ADD IT TO THE
//           KIT — one component, one visual decision, every screen"**.
// Rules:    B14 rule 36 · rule 5 (two button sizes; a switch is neither, it is
//           a control) · BR-SHL-025 (a control that cannot act is DISABLED
//           WITH its reason, never hidden)
// Tests:    src/components/Switch.test.tsx
// Impacts:  features/tenancy/SettingsCustomerPortalTab.tsx (CWP-069's five
//           switches and the live switch) · SettingsPortalTips.tsx ·
//           SettingsServiceCentres.tsx — three screens, ONE decision
// ───────────────────────────────────────────────────────
//
// THE ON/OFF CONTROL, ONCE.
//
// ⚠ **WHAT THIS REPLACES, AND WHY A COMPONENT AND NOT A CLASS.** Three screens
// had each written `<button role="switch">` with their own border, their own
// two words and their own padding — the same drift rule 36 caught in four
// different hand-rolled chips. The accessible name is a REQUIRED prop for the
// reason `RowActions` gives: a control with no name passes every text-absence
// check in the suite and is unusable without a mouse.
//
// ⚠ **AND IT DOES NOT WRITE THE WORDS.** *On* and *Off* live in the eleven
// catalogues and are handed in, because a component that reached for `t()`
// would fix one utility's vocabulary for every screen that ever uses it.

import { Button } from "./Button";

export function Switch(props: {
  on: boolean;
  /** The accessible name — what this switch is for, not its state. */
  label: string;
  onLabel: string;
  offLabel: string;
  disabled?: boolean;
  /** BR-SHL-025: why it cannot be used, when it cannot. */
  reason?: string | null;
  onChange: (on: boolean) => void;
  /** For a walkthrough and a test to find one switch among five. */
  testKey?: string;
}) {
  const blocked = props.disabled === true || (props.reason ?? null) !== null;
  return (
    <Button
      // The kit's own two tiers say the state: a switch that is ON is a
      // committed choice (`primary`), OFF is the quiet one (`secondary`).
      // Neither is `danger` — rule 6 reserves that for destructive commits and
      // turning a portal switch off is not one.
      variant={props.on ? "primary" : "secondary"}
      size="sm"
      role="switch"
      aria-checked={props.on}
      aria-label={props.label}
      title={props.reason ?? props.label}
      disabled={blocked}
      onClick={() => props.onChange(!props.on)}
      data-switch-state={props.on ? "on" : "off"}
      data-switch-key={props.testKey}
    >
      {props.on ? props.onLabel : props.offLabel}
    </Button>
  );
}
