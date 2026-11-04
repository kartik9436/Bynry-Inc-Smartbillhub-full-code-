// ── Trace ──────────────────────────────────────────────
// Defects: DEF-MET-6118 — the build's only *Add service* control posted the
//          literal `{ service: "water" }`. One service, always water, one press
//          at a time, on an endpoint that takes any of the tenant's enabled
//          services and a unit id.
// Rules:   PO ruling 2026-09-21 (*"here filter only active Utility services for
//          that Tenant"*) — the same ruling step 4 of the wizard obeys, read
//          through the same door · CLAUDE.md hard-won law 2 (an eleventh
//          service must appear on screen on its own; a hand-typed list fails
//          SILENTLY) · `B14` rule 43 (a piece of UI is a COMPONENT) · rule 33
//          (a LABEL is ≤ 3 words and carries no sentence) · rule 21 (utilities,
//          no stylesheet class) · `BR-SHL-025` (a refused control carries its
//          reason where it is READ, not only in a `title`)
// Tests:   src/features/work/buildRecord/AddServiceChoice.dom.test.tsx
//          10-scripts/def_met_6118_add_service_walkthrough.mjs (the browser half)
// ───────────────────────────────────────────────────────
/**
 * *Add service* — **which service, and at which unit.**
 *
 * ⚠ **THE ESCAPE REASON IS WHY THIS COMPONENT EXISTS AT ALL.** The button
 * worked, the endpoint worked, and a test asserting that pressing it adds a
 * service PASSED — because it did. Nothing asserted that a control offering
 * *Add service* can add the services this utility **sells**. It is the
 * hand-typed-list shape one step on: not a list that is wrong, **a list of
 * exactly one**, and a literal that happens to suit the demo tenant stays
 * invisible until a utility sells something else.
 *
 * ⚠ **THE OPTIONS ARE A QUERY'S ANSWER AND NEVER A LIST IN THIS FILE.** They
 * are read from `GET /settings/services` through `queryKeys.tenantServices` —
 * the door step 4 of the New Connect wizard now reads, and the one
 * `ServicesAvailableField`, the premises wizard and the assets wizard already
 * share. `CLAUDE.md` names the two hand-typed copies that survive elsewhere
 * (`SignupWizard.tsx` and `ratingShared.tsx`) as hard-won law 2; a third here
 * would be a fourth answer to a question that already has one, and it would be
 * wrong for every tenant that turns a service on tomorrow.
 *
 * ⚠ **`unit_id` IS OPTIONAL BECAUSE A SERVICE NEED NOT BE PER-UNIT.**
 * `connection_services.unit` is nullable by design — *"a per-premise main tap
 * belongs to the build, not to any one of its 25 units"* (B18 §8.2) — so the
 * unit control offers the whole build as its first option rather than forcing
 * a choice the data model does not require.
 *
 * ⚠ **IT OFFERS WHAT THE TENANT SELLS, NOT WHAT THE ADDRESS HAS.** Those are
 * two different filters and both are real: a utility may sell gas at an address
 * with no gas main (`premises.services_available`, `BR-MET-003`). This control
 * names the TENANT one and the server refuses the other, in its own sentence,
 * which is where that refusal already lives.
 */


/** One option, in the words the tenant gave the service on Settings. */
export interface AddServiceOption {
  code: string;
  name: string;
}

/** One unit this build touches, as the record's own units section names it. */
export interface AddServiceUnit {
  id: string;
  label: string;
}

/** What the control sends. `unitId` null is the build itself — a main tap. */
export interface AddServiceChoiceValue {
  service: string;
  unitId: string | null;
}
