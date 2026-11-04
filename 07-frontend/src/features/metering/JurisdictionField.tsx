// ── Trace ──────────────────────────────────────────────
// Change:  CR-039 wave C task 10 — *"a way to SET jurisdiction"*. The
//          provisioning trace (2026-08-26) finding 3: *"Jurisdiction
//          (inside/outside city) can be written by NOTHING. It decides an
//          outside-city surcharge on every bill at an address; the bill run
//          treats it unstated as an exception. Read side built, write side
//          absent."*
// Defect:  DEF-517 (the column has no writer at any layer) · DEF-507 (the READ
//          half, shipped 2026-08-26, whose own comment says *"where an edit
//          control belongs … is a bigger question than this defect —
//          REPORTED, not invented"*). This is that control.
// Screens: S16 (the guided add, single-premise step) · PRM-01/PRM-02 edit modal
// Rules:   BR-RAT-101 (the flag lives on the premises; `None` is a THIRD state,
//          never a default) · BR-RAT-102 (the plan states the factor, the
//          premises states the side — a line is surcharged only when BOTH
//          gates open) · B14 rule 21 (new UI is Tailwind utilities and adds NO
//          class to a stylesheet — this file declares none and asks for none;
//          it renders the shared `SelectField`)
// Question: OQ-423 — changing this flag changes what the address is charged.
//          Forward-only is what the product DOES (hard rule 4: an issued
//          invoice is immutable); whether a correction owes an adjustment on
//          bills already issued is the PO's, and is not answered here.
// ───────────────────────────────────────────────────────
// ONE control, two screens — the same reason `AreaFields` and
// `ServicesAvailableField` exist: a second copy is a second place to add a
// rule to, and one of them gets forgotten.
//
// ⚠ **THREE OPTIONS, NOT A CHECKBOX, AND THAT IS THE WHOLE DESIGN.** A checkbox
// has two states. `premises.inside_city_limits` has three — `true` inside,
// `false` outside, `null` **nobody recorded it** — and the third is not a
// tidiness detail: it is what stops the product answering a money question on
// the utility's behalf. BR-RAT-101, verbatim: *"assuming inside under-charges a
// customer the utility may be entitled to surcharge, while assuming outside
// over-charges one who never agreed to it. A default of either would be a
// silent pricing decision on data nobody entered."* A checkbox would make every
// premises anyone opened an answer, and the answer it defaults to (unticked =
// outside) is the one that ADDS a surcharge.
//
// ⚠ **AND THE OPTION VALUES ARE `inside` / `outside`, NEVER `true` / `false`.**
// A `<select>` yields strings, so `"false"` is TRUTHY in JavaScript and one
// missing conversion anywhere between here and the request body would price an
// inside-city address as outside. Words cannot be coerced by accident; the two
// functions below are the only place the conversion happens, they are exported,
// and `JurisdictionField.test.tsx` asserts the round trip in both directions.
import { SelectField } from "@/components/FormModal";
import type { Translator } from "@/features/tenancy/settingsShared";

/** The three option values. `""` is the unrecorded state — the placeholder. */
export const JURISDICTION_UNRECORDED = "";
export const JURISDICTION_INSIDE = "inside";
export const JURISDICTION_OUTSIDE = "outside";

/**
 * The stored three-state as this control's option value.
 *
 * `null` → `""`, and NOT `"outside"`: the dash the detail screen renders for an
 * unrecorded flag (`jurisdictionText` in PremisesDetailPage) and the empty
 * option here are the same statement, and the form must re-open on what the
 * server stored rather than on a guess.
 */
export function jurisdictionOption(inside: boolean | null | undefined): string {
  if (inside === true) {
    return JURISDICTION_INSIDE;
  }
  if (inside === false) {
    return JURISDICTION_OUTSIDE;
  }
  return JURISDICTION_UNRECORDED;
}

/**
 * The option value as the payload's three-state.
 *
 * Anything this function does not recognise becomes `null` — *not recorded* —
 * because that is the ONE value of the three that adds no charge to anybody's
 * bill and refuses rather than misprices at the bill run (BR-RAT-102's fourth
 * case). A fall-through that guessed `false` would surcharge on a typo.
 */
export function jurisdictionPayloadValue(option: string): boolean | null {
  if (option === JURISDICTION_INSIDE) {
    return true;
  }
  if (option === JURISDICTION_OUTSIDE) {
    return false;
  }
  return null;
}

export function JurisdictionField(props: {
  value: boolean | null | undefined;
  onChange: (value: boolean | null) => void;
  t: Translator;
}) {
  const { t } = props;
  return (
    <SelectField
      id="inside_city_limits"
      label={t("metering.premises.field.jurisdiction")}
      value={jurisdictionOption(props.value)}
      placeholder={t("metering.premises.jurisdiction.notRecorded", {
        defaultValue: "Not recorded",
      })}
      options={[
        {
          value: JURISDICTION_INSIDE,
          label: t("metering.premises.jurisdiction.inside", {
            defaultValue: "Inside city limits",
          }),
        },
        {
          value: JURISDICTION_OUTSIDE,
          label: t("metering.premises.jurisdiction.outside", {
            defaultValue: "Outside city limits",
          }),
        },
      ]}
      onChange={(option) => props.onChange(jurisdictionPayloadValue(option))}
      help={t("metering.premises.jurisdiction.help", {
        defaultValue:
          "Outside the city limits, a plan that states a surcharge multiplies this address's bills.",
      })}
    />
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-039 wave C tasks 10-11 (jurisdiction) — 12-governance/11-change-requests.md
// generated: 2026-08-27 by the CR-039 wave C jurisdiction lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// exceptions:
//   E3 r10's PRM-02 draws the jurisdiction as a READ line (*"Inside city
//      limits — no ×1.5 multiplier"*) and draws no editor for it anywhere, so
//      this control has no prototype to conform to. It is placed on the two
//      forms that already own every other premises fact (the S16 single step
//      and the PRM-01 edit modal) rather than invented as a screen of its own.
//   E3 the *"— no ×1.5 multiplier"* half of r10's sentence is NOT rendered
//      here, for the reason PremisesDetailPage already records: whether this
//      premises' plan carries a multiplier is a RATING fact this payload has
//      no field for, and stating it from the flag alone would invent a rate.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
