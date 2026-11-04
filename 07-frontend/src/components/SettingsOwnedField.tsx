// ── Trace ──────────────────────────────────────────────
// Story:    US-RBS-001 · US-RBS-016 (EP-RBS-01) — CR-075 wave C task C1a.
//           Screens: RBS-004-R8 (five on one screen) and nearly every setup
//           renderer — parameter type 9 of the eleven, `ref:setting`
// Rules:    B14 rule 36 (compose the kit; and *nothing dashed … ships to a
//           utility user* — the dashed border here is the RULED exception, see
//           below) · B14 rule 21 + its per-file clause · B14 rule 31 (no
//           database id is ever the visible value of a field) · B14 rule 1 (a
//           `→` names where it goes) · hard-won law 2 (built is not wired) ·
//           hard-won law 3 (defaults fail closed)
// Tests:    src/components/SettingsOwnedField.dom.test.tsx
// Impacts:  04-docs/05-modules/17-runbooks/09-component-inventory.md Part 5 §5
//           and Part 2 §`ref:setting` · 07-frontend/src/styles/route-b-migrated.txt
// ───────────────────────────────────────────────────────
//
// **A VALUE THAT ALREADY LIVES IN SETTINGS IS SHOWN, NEVER COPIED.**
// `09-component-inventory.md` Part 2 says what this is for in one sentence:
// *"Duplicating one is how a utility ends up with two ladders and no way to
// tell which one sent the notice."* `RBS-004-R8` draws five at once — *Ladder
// tiers · From Settings · 5 tiers*, *Grace days · From Settings · 3*, *Quiet
// hours · From Settings · 20:00–08:00*.
//
// ⚠ **THERE IS NO `value` PROP, AND THAT IS THE COMPONENT'S ENTIRE POINT.**
// Part 5 §5 states it as a rule rather than a preference: *"the component reads
// Settings and takes no value prop — a component with a value prop here is the
// bug."* `SettingsOwnedField.dom.test.tsx` reads this file's own source and
// fails if one appears, because `tsc` cannot refuse a prop nobody declared and
// the next lane's obvious convenience is exactly the thing being refused.
//
// ⚠ **SO IT READS THROUGH A CONTEXT, AND THE SHAPE IS COPIED DELIBERATELY FROM
// `TenantRegional.tsx` — INCLUDING THE PART THAT LOOKS INCONVENIENT.**
// That file records DEF-SHL-3964: the tenant's date format was carried as an
// OPTIONAL prop threaded through 160 call sites, the root never set it, every
// screen fell through to a plausible seed default, and a Texas utility read
// every timestamp six hours out — *with no crash, no blank and no raw key to
// notice*. Its cure is this one: publish once, and hold `null` until the value
// is actually known so a consumer can tell *not yet* from a real answer.
// **A default here would be a plausible wrong answer, which is the defect and
// not the cure.** So an unwired field draws a visible *Not loaded* rather than
// an empty box — hard-won law 2 in the one direction G13 cannot see.
//
// ⚠ **THE DASHED BORDER IS THE RULED EXCEPTION TO RULE 36, NOT A BREACH OF IT.**
// Rule 36 bans dashed borders as an ANNOTATION style. Part 4 §4 settles this
// case explicitly: *"a dashed border means THIS IS NOT YOURS TO EDIT HERE"*, it
// already carries that meaning in B14 rule 17's empty state, and by that test
// *"`ref:setting`'s dashed box passes"*. Nothing else in this component is
// dashed and nothing in it is monospaced.
import { createContext, useContext } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/**
 * What Settings currently says, published once for the whole app.
 *
 * `null` means **not known yet** and is the deliberate initial value — see the
 * header. A missing KEY inside a loaded map is a different thing again: it
 * means Settings has no such value, which is a fact worth drawing rather than
 * hiding.
 */
export type SettingsOwnedValues = Readonly<Record<string, ReactNode>>;

const SettingsOwnedContext = createContext<SettingsOwnedValues | null>(null);

/** Publishes the Settings-owned values. The app shell — or a screen's own
 *  loader — wraps the setup renderer in this. There is no default provider,
 *  for the reason the header gives. */
export function SettingsOwnedProvider(props: {
  values: SettingsOwnedValues | null;
  children: ReactNode;
}) {
  return (
    <SettingsOwnedContext.Provider value={props.values}>
      {props.children}
    </SettingsOwnedContext.Provider>
  );
}

/** What Settings says, or `null` while nobody has said. Exported so a screen can
 *  branch BEFORE it draws, the way `MoneyCell`'s `isAmountAbsent` lets a caller
 *  branch before the refusal. */
export function useSettingsOwnedValues(): SettingsOwnedValues | null {
  return useContext(SettingsOwnedContext);
}

export interface SettingsOwnedFieldProps {
  /** WHICH setting. A key into the published map — never rendered, so B14
   *  rule 31 is safe: what a reader sees is `label` and the value Settings
   *  gave, not this. */
  setting: string;
  /** The label a clerk reads: *Ladder tiers* · *Quiet hours*. Already
   *  translated, three words or fewer (B14 rule 33's LABEL cap). */
  label: string;
  /** Where **Open settings →** goes. REQUIRED: a read-only field with no way
   *  to reach the thing that owns it is a dead end, and B14 rule 1 says the
   *  arrow names where it goes. */
  to: string;
  /** *From Settings* — the provenance line, already translated. Required for
   *  the same reason the link is: the dashed border says *not yours to edit
   *  here* and this says WHERE it is edited. */
  ownedBy: string;
  /** The five words shown when the map has not arrived — *Not loaded* — and the
   *  different five shown when Settings has no such value. Already translated,
   *  and REQUIRED so an unwired field cannot render as a blank box. */
  absent: { notLoaded: string; notSet: string };
  /** The words on the link — *Open settings →*, already translated. */
  openLabel: string;
}

/**
 * The `ref:setting` parameter. `RBS-004-R8`'s Parameters panel.
 *
 * It renders three states and each is visibly different, because the whole
 * failure this component is guarding against is a wrong value that looks right:
 *
 *   loaded    — the value Settings holds, in the reader's own format
 *   not loaded — *Not loaded*, greyed. Nobody has published yet.
 *   not set    — *Not set in Settings*. Published, and Settings has no value.
 */
export function SettingsOwnedField(props: SettingsOwnedFieldProps) {
  const values = useSettingsOwnedValues();
  const known = values !== null && Object.prototype.hasOwnProperty.call(values, props.setting);
  const state = values === null ? "notLoaded" : known ? "loaded" : "notSet";
  // `known` already narrows in practice, but it is a boolean and `tsc` cannot
  // see that — so the value is pulled out here, where the null check IS the
  // narrowing, rather than silenced at the call site with a non-null assertion.
  const shown = known && values !== null ? values[props.setting] : null;
  return (
    <div
      className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border border-dashed border-neutral-400 px-3 py-2"
      data-settings-owned={props.setting}
      data-settings-state={state}
    >
      <span className="min-w-[140px] text-base text-neutral-900">{props.label}</span>
      <span className="text-xs text-neutral-600 uppercase" data-settings-owner="">
        {props.ownedBy}
      </span>
      <span className="text-md text-neutral-900" data-settings-value="">
        {state === "loaded" ? (
          shown
        ) : (
          <span className="text-neutral-600">
            {state === "notLoaded" ? props.absent.notLoaded : props.absent.notSet}
          </span>
        )}
      </span>
      <Link className="ms-auto text-base underline" to={props.to} data-settings-open="">
        {props.openLabel}
      </Link>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-001 · CR-075 wave C task C1a · 09-component-inventory.md Part 5 §5 · frame RBS-004-R8
// generated: 2026-09-06 by the CR-075 wave C build lane
// checklist: A=n/a B=n/a C✔ D=n/a E✔(RBS-004's Parameters panel composes it) F✔ G✔ H=n/a
// gates: vitest src/components/SettingsOwnedField.dom.test.tsx (including the source read that refuses a `value` prop) · runbookKitClasses · routeBUtilities · G31 · tsc
// exceptions: the dashed border, which B14 rule 36 permits here by Part 4 §4's ruling — a dashed border means "this is not yours to edit here"
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
