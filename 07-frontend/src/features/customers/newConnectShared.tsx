// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W6 — the pure half of S87 (the wizard) and S88 (the
//           connection detail): the vocabularies both screens name, the four
//           service families §5.4.5 defines, and the derivations the wizard
//           runs on its own draft. Split out so neither screen owns a rule the
//           other also needs, and so every one of them is testable without a
//           browser.
//           Lane TEXT — 2026-09-28 — `unitPatternSentence` is DELETED with the
//           sentence it built (PO reported bug 1, *"To Much text on every step
//           reduce it"*). Its only caller was step 3, and an exported helper
//           nobody calls is dead code the 8→5 restructure would re-mount.
// Rules:    B18 §5.4.5 (the four service families and what "installation" means
//           for each) · §5.4.10 step 3 (the unit pattern) · step 4 (*"availability
//           belongs to the street, not to a unit"*) · step 5 (the plan-coverage
//           warning) · step 8 (the seven-count manifest and the four-way
//           occupancy radio) · BR-MET-112 (nothing is written until step 8) ·
//           CR-032 (`activated`, never `energised`) · B14 rule 21 (Tailwind
//           only — this file declares no class and, being mostly pure
//           functions, renders almost nothing)
// Questions: OQ-249 (the Work module is R5 — `we_schedule` is refused by name) ·
//           OQ-370 (which characteristic keys each flat service has — NOT
//           answered here; the wizard collects nothing it cannot name)
// Tests:    NewConnectWizard.test.tsx · ConnectionDetailPage.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THE DERIVATIONS ARE PURE FUNCTIONS AND NOT COMPONENT BODIES
// ══════════════════════════════════════════════════════════════════════════
// Four of them decide something a person will act on — how many units get
// built, which service the street can supply, which plan leaves a service
// unpriced, and what the commit will make. Each is drawn with a worked figure
// in B18 (26 units · 5 of 10 available · *"Residential Standard does not cover
// storm water"* · the seven-count manifest), and each of those figures is a
// case a test can pin. Inside a component body none of them is reachable
// except by rendering, and a rendered assertion cannot tell a wrong number from
// a missing one.
import type { ReactNode } from "react";

import { Note } from "@/components/TextBits";
import { problemWords } from "@/features/payments/paymentsShared";

export type Translator = (key: string, params?: Record<string, unknown>) => string;

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE FOUR SERVICE FAMILIES — B18 §5.4.5, and the gate is the load-bearing
//     column
// ══════════════════════════════════════════════════════════════════════════
//
// | Family   | Services                          | Gate                        |
// | Metered  | Electric · Water · Gas            | Meter set — EXCEPT gas      |
// | Derived  | Sewer                             | the water it derives from   |
// | Capacity | Solar · Battery                   | Permission to operate       |
//   (capacity takes NO meter since 2026-10-02 — `takesAMeter`, DEF-MET-9037)
// | Flat     | Trash · Storm water · Broadband · Fire · Thermal | delivery/activation/assessment |
//
// ⚠ **THE FAMILY DECIDES WHETHER A UNIT GETS A METER**, which is the only
// reason this table is in the wizard at all: step 8's manifest says `Meters 50`
// on a build of 26 units, and 50 is *25 electric + 25 water* — the SEWER on
// those same units adds none, because sewer is derived, and the common area's
// trash and storm water add none, because those are flat. Getting the family
// wrong changes a number a crew is sent to fit.

// ⚠ **`thermal_heat` LEFT THIS FAMILY ON 2026-09-07 (`CR-080`) AND A UNIT
// TAKING IT NO LONGER GETS A METER FITTED.** PO verbatim: *"connected tonnage
// - it is capacity not metering; i will ahve 100 tonne or 200 tonne etc"*.
// **This is the line that changes what a crew is sent to do**, which is why
// the table above exists at all: a 26-unit build selling water and thermal
// used to read `Meters 50` on step 8's manifest and now reads `Meters 25`.
export const METERED_SERVICES = ["electric", "water", "gas"] as const;
export const DERIVED_SERVICES = ["sewer"] as const;
export const CAPACITY_SERVICES = ["solar", "battery"] as const;
// ⚠ `fire` JOINED THIS FAMILY ON 2026-09-02 (CR-063, DEF-3091) AND NOT THE
// CAPACITY ONE, WHICH READS BACKWARDS UNTIL YOU KNOW WHAT THESE FOUR NAMES
// DECIDE. This table answers ONE question — does a unit taking this service
// get a meter fitted — and fire takes none: it is billed by COUNTING the
// lines and hydrants installed, exactly as trash is billed by counting carts.
// `capacity` here means "paired with a net meter" (solar, battery), which is
// a different fact from the billing basis of the same name.
// Before this line `serviceFamily("fire")` answered `unknown`, and
// `takesAMeter` therefore answered false — the right answer for the wrong
// reason, and one that stops being right the day the unknown branch changes.
// ⚠ **AND `thermal_heat` JOINED IT ON 2026-09-07 (`CR-080`), WHICH READS
// BACKWARDS FOR THE SAME REASON FIRE DOES.** Thermal is `capacity` in
// `BR-TEN-1180`'s vocabulary — billed on the connected tonnage recorded on the
// unit — but `capacity` HERE means *"paired with a net meter"* (solar,
// battery), which is a different fact from the billing basis of the same name.
// A thermal building takes no meter and no net meter, so it is `flat` by the
// one question this table answers.
export const FLAT_SERVICES = [
  "trash",
  "storm_water",
  "broadband",
  "fire",
  "thermal_heat",
] as const;

// ══════════════════════════════════════════════════════════════════════════
// `TEN_SERVICES` IS DELETED — PO ruling 2026-09-21
// ══════════════════════════════════════════════════════════════════════════
//
// It held all ELEVEN platform services, by hand, in seed order, and step 4's
// tick list was its only reader. PO, verbatim: *"here filter only active
// Utility services for that Tenant"* — so the list is now read from
// `GET /settings/services` through `queryKeys.tenantServices`, the same source
// `ServicesAvailableField`, the premises wizard and the assets wizard already
// use, and `gridRows` derives its explicit set from the grid's own keys.
//
// ⚠ **IT WAS THE THIRD HAND-TYPED COPY OF THIS LIST IN THE FRONT END AND
// `CLAUDE.md` NAMES THE OTHER TWO** — `SignupWizard.tsx`'s tick-list and
// `ratingShared.tsx`'s badge map — as hard-won law 2: *"an eleventh service
// does NOT appear on screen on its own and it fails SILENTLY"*. Measured the
// day it went: the demo utility sells **two** of the eleven, so **nine tick
// boxes offered a service the commit refuses by name**, after all eight steps.
// **The ruling kills the class rather than renumbering the constant.**
//
// ⚠ **THE FOUR FAMILY TABLES ABOVE ARE NOT THE SAME THING AND DO NOT GO.**
// They answer *does a unit taking this service get a meter fitted* — a
// PLATFORM fact about a service's shape, not a question about which services a
// tenant sells — and `serviceFamily` deliberately answers `unknown` for a code
// it does not recognise rather than folding it into `metered`.

/**
 * ⊕ **`DEF-MET-9222` — THE TWO SERVICES WHOSE SIZE IS A FACT ABOUT THE UNIT.**
 * The server's `connections.UNIT_CAPACITY_CHARACTERISTIC`, mirrored: storm
 * water's class (an ERU count, PO 2026-09-02) and thermal's connected tonnage
 * (PO 2026-09-07, *"it is capacity not metering"*). Nobody installs an ERU or a
 * ton, so no device carries the size — the size step 3 shows on the row
 * travels on the row itself (`unit_services[].size_class`) and the commit
 * records it on the unit. Until 2026-10-03 it travelled nowhere and both
 * services billed `$0.00`.
 */
export const UNIT_CAPACITY_SERVICES = ["storm_water", "thermal_heat"] as const;

export function capacityIsOnTheUnit(code: string): boolean {
  return (UNIT_CAPACITY_SERVICES as readonly string[]).includes(code);
}

export type ServiceFamily = "metered" | "derived" | "capacity" | "flat" | "unknown";

export function serviceFamily(code: string): ServiceFamily {
  if ((METERED_SERVICES as readonly string[]).includes(code)) {
    return "metered";
  }
  if ((DERIVED_SERVICES as readonly string[]).includes(code)) {
    return "derived";
  }
  if ((CAPACITY_SERVICES as readonly string[]).includes(code)) {
    return "capacity";
  }
  if ((FLAT_SERVICES as readonly string[]).includes(code)) {
    return "flat";
  }
  // A tenant-added code. NOT silently folded into "metered" — that would put a
  // meter in the manifest for a service nobody said had one.
  return "unknown";
}

/** Does a unit taking this service get a meter installed? Only a METERED
 *  service does. Derived and flat services do not, and an unknown family does
 *  not, because guessing yes builds hardware.
 *
 *  ⚠ **CAPACITY ANSWERED `true` UNTIL 2026-10-02 AND NOW ANSWERS `false`
 *  (`DEF-MET-9037`).** §5.4.5 paired solar and battery with a net meter. PO
 *  ruling 2026-10-02, verbatim: *"we are not doing net metering right now -
 *  we are doing capacity based panel - A · The net meter doesn't count toward
 *  capacity. Capacity is the panels or battery only."* So a solar or battery
 *  build fits no meter: its size is the panels' and batteries' kW, sent on
 *  `unit_services`. Fitting an unsized meter there made the bill REFUSE once
 *  it was installed. **This is a number a crew is sent to work to**: a
 *  26-unit block selling water and solar now reads `Meters 26`, not `52`. */
export function takesAMeter(code: string): boolean {
  return serviceFamily(code) === "metered";
}

// ══════════════════════════════════════════════════════════════════════════
// 2 · STEP 3 — THE UNIT PATTERN. `Apt` · `101` → `125` produces `Apt 101–125`,
//     25 units, **plus the common area, which is ticked by default**
// ══════════════════════════════════════════════════════════════════════════

export interface UnitPattern {
  prefix: string;
  from: string;
  to: string;
  includeCommonArea: boolean;
}

export interface DraftUnit {
  label: string;
  isCommonArea: boolean;
}

/**
 * B18 §5.4.10 step 4, and the drawn table's own footing: **`Showing 9 of 26
 * units · common area included`** — 25 + 1.
 *
 * ⛔ **THE COMMON AREA IS NO LONGER TICKED BY DEFAULT — `BR-MET-1179`, PO
 * ruling 2026-09-21.** It was, and the screen's reason was *"Corridors, car
 * park, irrigation. It always exists and nobody remembers to add it"*, copied
 * from the drawing. **That default is what made the trap the acceptance walk
 * found:** a clerk building a HOUSE has no unit numbers to type, so they left
 * `from`/`to` empty and carried on — and the build came out as **one common
 * area and no dwelling at all**, with nothing on screen saying it was wrong.
 *
 * ⚠ **OPTIONAL, NEVER PRE-SELECTED — AND NEVER FORBIDDEN.** The tick is offered
 * on EVERY premise type and a clerk who asks for a shared unit on a house gets
 * one. A four-code refusal was briefly built here and the PO removed it in
 * their own words: *"i said Comemrcial Building also Common area is optional
 * not mandetory , I did not say No common area"*. **Do not reason about common
 * areas from type names** — measured on the seeded demo, the one property that
 * has a common area is a commercial building and all three apartment complexes
 * have none.
 *
 * ⚠ **B18 ALREADY DREW IT UNTICKED.** Its own §5.4.10 note records that the
 * drawn checkbox renders UNTICKED beside the sentence arguing for a tick, which
 * was read as a drawing inconsistency and NOT copied. The drawing was right.
 *
 * ⚠ **A RANGE THAT DOES NOT PARSE PRODUCES NOTHING, NEVER ONE UNIT.** An
 * unreadable `from`/`to` is a question, and answering it with a single unit
 * would build a 1-unit premises for a 25-unit development in silence.
 */
export function expandUnitPattern(pattern: UnitPattern): DraftUnit[] {
  const units: DraftUnit[] = [];
  const from = Number.parseInt(pattern.from, 10);
  const to = Number.parseInt(pattern.to, 10);
  if (Number.isFinite(from) && Number.isFinite(to) && to >= from) {
    for (let n = from; n <= to; n += 1) {
      const prefix = pattern.prefix.trim();
      units.push({ label: prefix === "" ? String(n) : `${prefix} ${n}`, isCommonArea: false });
    }
  }
  if (pattern.includeCommonArea) {
    units.push({ label: COMMON_AREA_LABEL, isCommonArea: true });
  }
  return units;
}

export const COMMON_AREA_LABEL = "Common area";

// ⚠ **`unitPatternSentence` IS DELETED (PO 2026-09-28, reported bug 1).** It
// built *"Produces Apt 101–125 — 25 units, editable below."* for step 3, which
// the redesign drawing lists under *Removed from this step*: it restated the
// From/To boxes above it and the table below it, and *"editable below"* was
// rationale (B14 rule 33, zero words on screen). Its only caller was
// `NewConnectUnitsStep`, and an exported helper nobody calls is the dead code
// hard-won law 1 is about — so it went with the sentence rather than being
// left here for the 8→5 restructure to find and re-mount.

// ══════════════════════════════════════════════════════════════════════════
// 3 · STEP 5 — AVAILABILITY IS THE STREET'S, NOT THE UNIT'S
// ══════════════════════════════════════════════════════════════════════════

/**
 * B18 §5.4.10 step 5's own load-bearing sentence:
 *
 * > *"**Availability belongs to the street, not to a unit.** The grid below can
 * > only offer what is ticked here — **this is the check that stops somebody
 * > connecting gas where there is no gas main.**"*
 *
 * So the fact is two-level and **the second can never exceed the first**. This
 * returns every breach rather than a boolean, because a clerk fixing one needs
 * to know which unit and which service — *"invalid"* is not actionable.
 */
export function availabilityBreaches(
  premiseServices: readonly string[],
  unitServices: Readonly<Record<string, readonly string[]>>,
): { unit: string; service: string }[] {
  const available = new Set(premiseServices);
  const breaches: { unit: string; service: string }[] = [];
  for (const [unit, services] of Object.entries(unitServices)) {
    for (const service of services) {
      if (!available.has(service)) {
        breaches.push({ unit, service });
      }
    }
  }
  return breaches;
}

/**
 * **TC-NCT-6 — sewer derives from water, so a unit cannot take sewer without
 * it.** B18 §5.4.5: sewer's captured fact is *"which service it derives from,
 * and the %"*, and its GATE is *"The water service it derives from"*.
 *
 * ⚠ **THIS IS A REFUSAL, NOT A WARNING**, and it is the one place the wizard
 * refuses a mapping outright: a sewer line priced as a percentage of a water
 * bill that does not exist has no basis at all.
 */
export function sewerWithoutWater(
  unitServices: Readonly<Record<string, readonly string[]>>,
): string[] {
  return Object.entries(unitServices)
    .filter(([, services]) => services.includes("sewer") && !services.includes("water"))
    .map(([unit]) => unit);
}

// ══════════════════════════════════════════════════════════════════════════
// 4 · STEP 6 — THE PLAN-COVERAGE CHECK, drawn as a warning
// ══════════════════════════════════════════════════════════════════════════

/**
 * B18 §5.4.10 step 6, drawn verbatim:
 *
 * > **WON'T COVER** — *"Common area takes trash and storm water. Commercial
 * > Standard covers both, but **Residential Standard does not — do not apply it
 * > there**."*
 *
 * So the wizard compares the plan's covered services against the services
 * MAPPED to the unit and names which choice would leave a mapped service
 * unpriced.
 *
 * ⚠ **IT WARNS AND DOES NOT REFUSE.** A service mapped and unpriced is a real
 * shape — the PO's own *"an absent characteristic bills zero"* ruling of the
 * same day accepts a bill that under-charges rather than one that refuses — and
 * a wizard that blocked here would stop a utility doing something it may
 * legitimately intend.
 *
 * ⚠ **AND `covers` UNKNOWN IS NOT `covers` NOTHING.** Passing `null` for a plan
 * whose covered set the screen has not been told returns NO warning and the
 * screen says the check could not run; returning "everything is uncovered"
 * would put a false red warning on every unit.
 */
export function planCoverageGaps(
  mapped: readonly string[],
  covers: readonly string[] | null,
): string[] {
  if (covers === null) {
    return [];
  }
  const covered = new Set(covers);
  return mapped.filter((service) => !covered.has(service));
}

// ══════════════════════════════════════════════════════════════════════════
// 5 · STEP 9 — THE COMMIT MANIFEST. Seven counts, not one row.
// ══════════════════════════════════════════════════════════════════════════

/**
 * `NCT-03.9`'s `What will be created`, and every number ties to an earlier step:
 *
 *     Customer             1        ← step 1, BR-MET-111
 *     Premises             1        ← step 3
 *     Units               26        ← step 4: 25 apartments + 1 common area
 *     Meters              50        ← step 5: 25 electric + 25 water
 *     Sub-meter links     24        ← ⚠ NOT COUNTED HERE. See below.
 *     Plan assignments    26        ← step 6, one per unit
 *     One-time charges  $14,435.00  ← step 7's footed total
 *
 * ⚠ **`subMeterLinks` IS `null` AND THAT IS COPIED FROM THE SERVER, NOT
 * INVENTED.** `commit_connection` returns `sub_meter_links: None` with a stated
 * absence — *"A sub-meter link is an assets relationship and this module has no
 * seam that writes one. Reported rather than counted as 0 — a zero would read as
 * 'we made none' where the truth is 'we cannot make them from here'."* The
 * wizard's preview must say the same thing the commit will say, or the person
 * pressing the button is told one number and given another.
 *
 * ⚠ **`oneTimeCharges` IS THE SERVER'S DISPLAY STRING OR `null`.** It is never
 * summed here: money is rounded once, server-side (hard rule 2, B4), and a
 * total this client added up would be the second rounding path DEF-088 removed.
 */
export interface ManifestPreview {
  customers: number;
  premises: number;
  units: number;
  meters: number;
  subMeterLinks: null;
  planAssignments: number;
  oneTimeCharges: string | null;
}

export function manifestPreview(args: {
  units: readonly DraftUnit[];
  unitServices: Readonly<Record<string, readonly string[]>>;
  unitsWithAPlan: number;
  ownerBecomesACustomer: boolean;
  quoteDisplay: string | null;
}): ManifestPreview {
  let meters = 0;
  for (const unit of args.units) {
    for (const service of args.unitServices[unit.label] ?? []) {
      if (takesAMeter(service)) {
        meters += 1;
      }
    }
  }
  return {
    // BR-MET-111 — the owner captured at step 1 BECOMES a customer, which is
    // what makes them billable at step 6. Without them the connection charges
    // have nowhere to go (DEF-650).
    customers: args.ownerBecomesACustomer ? 1 : 0,
    premises: args.units.length > 0 ? 1 : 0,
    units: args.units.length,
    meters,
    subMeterLinks: null,
    planAssignments: args.unitsWithAPlan,
    oneTimeCharges: args.quoteDisplay,
  };
}

// ══════════════════════════════════════════════════════════════════════════
// 6 · STEP 9 — THE FOUR-WAY OCCUPANCY RADIO, and it closed a money conflict
// ══════════════════════════════════════════════════════════════════════════
//
// B18 §5.4.10 step 6's footnote said *"vacant units bill nothing"*; BR-MET-105
// says an empty unit's **$30.50/month accrues to the owner**. Step 8 resolves
// it: the footnote was describing **the DEFAULT**, and BR-MET-105 is drawn here
// verbatim as the SECOND option. Both statements are true and this radio
// selects between them. No defect; BR-MET-105 stands unamended.

// ⛔ **TWO CHOICES FROM 2026-10-02, NOT FOUR — PO ruling (option A, `DEF-CUS-9050`,
// `DEF-CUS-9082`): *"in our case master account - this is correct"*.** An empty
// unit's base charges go to the owner's master account until a tenant moves in
// (base only, never usage; only where a master exists — two or more homes). So
// *Vacant · base charges only* and *Landlord-billed between tenants* were one
// behaviour and are one choice, and *Open an account now* is removed: units
// start vacant (BR-MET-116) and a tenant's account opens through Move-in. The
// billing is the run's own rule (`gather._unbilled_unit_tariffs`), read from
// who occupies the unit, never from this answer.
export const OCCUPANCY_CHOICES = ["vacant_service_off", "vacant_base_only"] as const;

export type OccupancyChoice = (typeof OCCUPANCY_CHOICES)[number];

/** A parked build saved before 2026-10-02 may hold a retired choice; it reads
 *  as the choice that now does what it promised. */
export const RETIRED_OCCUPANCY: Readonly<Record<string, OccupancyChoice>> = {
  landlord_billed: "vacant_base_only",
  open_account_now: "vacant_service_off",
};

/** The live choice for a stored value, retired ones mapped (see above). */
export function liveOccupancy(value: string): OccupancyChoice {
  if ((OCCUPANCY_CHOICES as readonly string[]).includes(value)) {
    return value as OccupancyChoice;
  }
  return RETIRED_OCCUPANCY[value] ?? OCCUPANCY_DEFAULT;
}

export const OCCUPANCY_DEFAULT: OccupancyChoice = "vacant_service_off";

// ══════════════════════════════════════════════════════════════════════════
// 7 · SHARED RENDERING — the two things both screens do with an ABSENCE
// ══════════════════════════════════════════════════════════════════════════

/**
 * A value the product cannot produce, rendered as the REASON it cannot.
 *
 * ⚠ **THIS COMPONENT EXISTS SO THAT NO SCREEN IN THIS FEATURE EVER TYPES
 * `?? 0` OR `?? "—"` OVER A MISSING FIGURE.** CLAUDE.md's fifth absolute rule
 * for this lane: *"`null` beside an `unavailable` reason IS the feature"*. A
 * bare dash is not that — it reads as "none" — so the dash carries the sentence
 * with it, and a screen reader gets the sentence rather than a hyphen.
 */
export function AbsentValue(props: { reason: string; tracks?: string }): ReactNode {
  return (
    <span className="inline-flex flex-col gap-0.5" data-absent="" data-tracks={props.tracks}>
      <span aria-hidden="true">—</span>
      <Note as="span" className="max-w-measure">
        {props.reason}
      </Note>
    </span>
  );
}

/** Money the server priced, or the reason it could not. NEVER a client-side
 *  rounding of `stored` and never `$0.00` over a null (DEF-088, DEF-127). */
export function MoneyOrReason(props: {
  money: { stored: string | null; display: string | null } | null | undefined;
  reason: string;
  tracks?: string;
}): ReactNode {
  const display = props.money?.display ?? null;
  if (display === null || display === "") {
    return <AbsentValue reason={props.reason} tracks={props.tracks} />;
  }
  return <span className="tabular-nums">{display}</span>;
}

// ══════════════════════════════════════════════════════════════════════════
// 8 · THE TWO ROUTES, DECLARED ONCE
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **DECLARED HERE AND NOT IN `customersShared.tsx`**, which holds every other
// customers route: that file is another lane's today and law 11's whole subject
// is what a pathspec commit does to a file two lanes are editing. The constants
// are exported, so `App.tsx` and any link imports them rather than re-typing a
// path — which is the thing declaring them once actually buys.
//
// ⚠ **TOP-LEVEL, NOT UNDER `/accounts`.** A connection is not account-scoped —
// `NCT-02`'s own header says a new connect *"may finish with no account"*, and
// the terminal state of a build is units vacant with no account at all. Hanging
// it off `:accountId` (as move-in and move-out correctly are) would require an
// account that does not exist.

/** S87 — the nine-step wizard. A static segment, so it can never be read as a
 *  connection id. */
export const NEW_CONNECT_ROUTE = "/connections/new";

/**
 * The `/connections` path space — the wizard above, and the build's own page.
 *
 * ⛔ **SUPERSEDED 2026-09-28 (`CR-151-BRC09`) — the paragraphs below describe
 * wave O and are kept as history.** A build HAS its own page again, `NCT-02`,
 * mounted at `/connections/:connectionId` on `BuildDetailPage`; `G93` no longer
 * refuses a link to it. `buildPagePath` below is the one builder for that
 * address (`DEF-CUS-9175`).
 *
 * ⚠ **`connectionDetailPath` IS GONE, DELIBERATELY (CR-070 wave O, 2026-09-04).**
 * PO: *"you cannot have two differnt screen - this is an integration problem"*.
 * `/connections/<uuid>` is no longer a place a person navigates to; the build's
 * progress, units, work orders and charges are reached from the **premises**
 * and from the **account**, and `features/work/workEndpoints.buildHomePath` is
 * the one function that says where.
 *
 * The path helper is DELETED rather than deprecated on purpose: a helper left
 * in place is one autocomplete away from putting the retired destination back,
 * and nothing in this repo reads a comment. `G93` fails a link to
 * `/connections/<id>` from anywhere in `07-frontend/src`, so the compiler and
 * the gate both answer now.
 *
 * The ROUTE constant stays: `App.tsx` still mounts that address, on
 * `BuildRedirect`, so every bookmark a clerk made keeps working.
 */
export const CONNECTIONS_ROUTE = "/connections";

/**
 * **The build's own page — `NCT-02`, `/connections/<id>` (`CR-151-BRC09`).**
 *
 * ⚠ **`DEF-CUS-9175` — THE CREATED SCREEN'S *Open the connection* WENT TO THE
 * OWNER'S ACCOUNT.** PO, 2026-10-02: *"on open connection it is going to
 * Account it should go to new connect request link"*. `CR-151-BRC09` gave the
 * build its page back and moved exactly one door onto it (`NewConnectsTab`'s
 * `rowDoor`); the wizard's completion and the Build panel's connection number
 * kept pointing at `buildHomePath`, which answers where a build LIVES, not
 * where a person opens it. One builder, so those doors cannot disagree again.
 */
export function buildPagePath(connectionId: string): string {
  return `${CONNECTIONS_ROUTE}/${encodeURIComponent(connectionId)}`;
}

/**
 * **`?build=<id>` on the wizard — the way back into a build that is still a
 * DRAFT (`DEF-CUS-6132`, `BR-SHL-048 (d)`).**
 *
 * PO ruling 2026-09-21: *"this is big problem - we cannot create two build -
 * you can update the existing build"* — and *update the existing build* is not
 * satisfied by code that updates it correctly down a path no clerk can walk.
 * On the acceptance walk the only way on was to type the address in by hand.
 *
 * ⚠ **THIS IS THE ONE BUILDER FOR THAT ADDRESS**, for the reason
 * `parkedDrafts.resumePath` is the one builder for `?parked=`: two places
 * naming the wizard's query string is two places to get it wrong, and this one
 * is read by the connection cell AND by the row action, which must not
 * disagree about where the same row goes.
 *
 * ⚠ **IT IS NOT `buildHomePath`'s JOB AND MUST NOT BECOME ONE.** That function
 * answers where a build LIVES — the account that owns it, else the premises —
 * and the approval queue, the dispatcher, the wizard's completion screen and
 * the bookmark redirect all read it. A DRAFT has no life there yet: its number
 * led to the property page with every action greyed, and where the address had
 * not resolved it led nowhere at all.
 */
export function draftBuildPath(connectionId: string): string {
  return `${NEW_CONNECT_ROUTE}?build=${encodeURIComponent(connectionId)}`;
}

/**
 * **Is this row a build a clerk can still walk into?** `submitted_at IS NULL`,
 * which the row publishes as `state === "draft"`.
 *
 * A function rather than a literal at each call site, because the two doors on
 * a New connects row must answer it identically — and because the day a second
 * unfinished state appears, one edit covers both.
 */
export function isDraftBuild(state: string): boolean {
  return state === "draft";
}

/**
 * BR-SHL-046 — **ONE declared step list**, read by the wizard's rail and by
 * anything that shows progress against it. The rule was written from DEF-648,
 * where a wizard header said six steps and a list column said four: *"Two
 * literals that happen to agree today is exactly the state this defect was
 * found in, and it recurs the day a seventh step appears."*
 *
 * ⚠ **FIVE SINCE 2026-09-28 — `CR-150-BRC09`, PO ruling, verbatim: *"these
 * steps are good - we need 1 word - for every step"* and *"we dont want any
 * information to be reduced or lost - 8 steps → 5"*.** It was EIGHT, and
 * before 2026-09-16 NINE.
 *
 * ⚠ **THE DRAWINGS ARE THE SPECIFICATION AND THEY SUPERSEDE THE BLUEPRINT'S
 * EIGHT** — `05-prototype/new-connect-redesign-2026-09-28/`, seven PNGs, read
 * as IMAGES (B14 rule 42). The Accounts blueprint draws eight steps and B14
 * rule 41 makes a blueprint exact; rule 41's own text names the one exception
 * — a drawing the PO has ruled on directly — and this is it. **A wizard's STEP
 * COUNT is a FLOW**, which is the exact word that cost the bill run its shape
 * (`DEF-GOV-5248`), so it is written out here rather than left to be inferred:
 * **no lane may build eight steps because the blueprint draws eight.**
 *
 * ⚠ **THE THREE THAT WENT ARE ABSORBED, NOT DELETED** — *"we dont want any
 * information to be reduced or lost"*. `services` and `plans` (work orders)
 * fold into **`units`**, which the drawing's step 3 draws as one table with a
 * service row per unit and a WORK ORDER column; `communication` folds into
 * **`review`**, whose drawing carries the Messages table with *+ Add template*.
 * Every field they asked is still asked — `newConnectAbsorbedSteps.dom.test.tsx`
 * is the check that says so, and it reads rendered output.
 *
 * ⚠ **`owner` IS NOW `customer`, ID AND ALL.** The PO's word for the step is
 * *Customer* and an id saying `owner` for a step named Customer is a second,
 * quieter assertion about its contents — the same rot that made `moveShared`
 * rename `plan` to `preferences`. **No server refusal has ever stamped
 * `owner`** (`connections.py` declares exactly three: `premise`, `units`,
 * `charges`), so nothing resolves against the old spelling.
 *
 * ⚠ **THE NUMBERS ARE INDEXES AND THIS FLOW SHRANK, SO A STORED STEP IS
 * REMAPPED AND NEVER CLAMPED** — `newConnectStoredStep` below.
 */
export const NEW_CONNECT_STEPS = [
  // ⚠ `labelKey` is LITERAL on every row so G18 can see the catalogue keys —
  // a template key (`customers.newConnect.step.${id}`) renders perfectly and is
  // invisible to the gate, so all five would report as dead entries the day
  // they are translated (WizardFrame's park reasons carry the same note).
  //
  // ⚠ **ONE WORD EACH, AND THAT IS THE RULING RATHER THAN A STYLE CHOICE** —
  // *"we need 1 word - for every step"*. The words are the drawn rail's, read
  // off all five PNGs: Customer · Premise · Units · Charges · Review.
  { id: "customer", labelKey: "customers.newConnect.step.customer", en: "Customer" },
  { id: "premise", labelKey: "customers.newConnect.step.premise", en: "Premise" },
  // ⚠ **THIS ONE STEP CARRIES THREE OF THE OLD EIGHT** — units, the per-unit
  // services grid and the work orders. The drawing's step 3 is one *Units and
  // service points* table grouped by unit, with `+ Add row` and
  // `+ Add work order` beneath it (`step3-units.png`, `step3a-add-row.png`,
  // `step3b-add-work-order.png`).
  { id: "units", labelKey: "customers.newConnect.step.units", en: "Units" },
  { id: "charges", labelKey: "customers.newConnect.step.charges", en: "Charges" },
  // ⚠ **REVIEW CARRIES THE MESSAGES TABLE NOW** — old step 7. `step5-review.png`
  // draws it as an editable table inside the review, with `+ Add template`.
  // The word is *Review*, not *Review & confirm*: one word per step.
  { id: "review", labelKey: "customers.newConnect.step.review", en: "Review" },
] as const;

/**
 * **A STORED STEP, IN THE FIVE-STEP SHAPE — the explicit old→new map.**
 *
 * ⚠ **THIS EXISTS BECAUSE A CLAMP ANSWERS THE WRONG QUESTION ONCE A FLOW
 * SHRINKS.** `clampToSteps` asks *is this number in range*; what a reopened
 * draft needs answered is *which step is this number now*. Every stored number
 * from 1 to 5 is already in range for a five-step list, so the clamp passes it
 * straight through — and four of those five are then WRONG:
 *
 * | parked at (of 8) | should open at (of 5) | a bare clamp gives | |
 * |---|---|---|---|
 * | 1 · Owner & scope | 1 · Customer | 1 | right |
 * | 2 · Premise | 2 · Premise | 2 | right |
 * | 3 · Units | 3 · Units | 3 | right |
 * | **4 · Map services** | **3 · Units** | **4 · Charges** | ⛔ **WRONG** |
 * | **5 · Work orders** | **3 · Units** | **5 · Review** | ⛔ **WRONG** |
 * | **6 · Charges** | **4 · Charges** | 5 · Review | ⛔ **WRONG** |
 * | **7 · Communication** | **5 · Review** | 5 | right by luck |
 * | **8 · Review** | **5 · Review** | 5 | right by luck |
 *
 * **The worked case, and it is the one that costs money:** a clerk parks on
 * old step 6 · *Charges* waiting on a deposit. Under a bare clamp they reopen
 * on **Review**, one step PAST the charge lines and the payment terms, looking
 * at *Create connection* with the thing they were waiting for unentered. Under
 * this map they reopen on **Charges**, where they left off.
 *
 * ⚠ **THE MAP IS THE PO's, NOT A DERIVATION** — `CR-150-BRC09` §0: *"a build
 * parked on an old step reopens on its mapped one — 1→1, 2→2, 3/4/5→3, 6→4,
 * 7/8→5 — nothing a clerk already typed is lost"*.
 *
 * ⚠ **THE CLAMP IS NOT REMOVED AND MUST NOT BE.** It still guards a number
 * that is out of range for some other reason — a corrupted row, a hand-edited
 * `?step=`, a flow that gains a step later. This map runs FIRST; a number it
 * does not know is handed through untouched and the clamp still catches it.
 * That is also what makes it safe to apply to a number stored AFTER today: a
 * five-step draft parked at 3 maps to 3.
 */
export const NEW_CONNECT_STORED_STEP: Readonly<Record<number, number>> = {
  1: 1,
  2: 2,
  3: 3,
  4: 3,
  5: 3,
  6: 4,
  7: 5,
  8: 5,
};

/** A step stored under the EIGHT-step shape, read in the five-step one.
 *
 *  ⚠ **THIS IS THE PARKED-DRAFT DOOR. THE ADDRESS BAR USES
 *  `newConnectAddressStep` BELOW, AND THE TWO ARE DELIBERATELY DIFFERENT.** */
export function newConnectStoredStep(stored: number): number {
  if (!Number.isInteger(stored)) {
    return stored;
  }
  return NEW_CONNECT_STORED_STEP[stored] ?? stored;
}

/**
 * **THE SAME MAP, FOR `?step=` — AND IT ONLY TOUCHES 6, 7 AND 8.**
 *
 * ⚠ **A STORED NUMBER AND AN ADDRESS NUMBER ARE NOT THE SAME FACT, AND
 * APPLYING ONE MAP TO BOTH BREAKS THE WIZARD'S OWN NAVIGATION.** Measured
 * while building this: with the full map on `?step=`, pressing **Continue**
 * on step 3 writes `?step=4`, the map reads that back as *old step 4 · Map
 * services* and returns **3**, and the clerk is walled on Units forever. The
 * suite caught it; nothing else would have, because every constant, every
 * count and `tsc` were all correct.
 *
 * ⚠ **THE DISCRIMINATOR IS THE ONLY ONE THERE IS: A NUMBER ABOVE FIVE CANNOT
 * BE A FIVE-STEP STEP.** 6, 7 and 8 are unambiguously off the old list and are
 * mapped. 1 to 5 are ambiguous — `?step=4` is *Charges* today and was *Map
 * services* yesterday — and are left alone.
 *
 * ⚠ **AND THE AMBIGUOUS HALF COSTS A CLERK NOTHING, WHICH IS WHY THIS IS THE
 * RIGHT WAY ROUND.** A bare `?step=` link carries no draft: nothing is written
 * until the last button (`BR-MET-112`) and the draft lives in component state,
 * so an old bookmark to step 4 opens an EMPTY wizard on *Charges* instead of
 * an EMPTY wizard on *Units*. There is no typing to lose. A link that DOES
 * carry work carries `?parked=` or `?build=` with it, and the park hydration
 * rewrites `?step=` to its own mapped landing — through `newConnectStoredStep`,
 * the FULL map — a moment after mount.
 */
export function newConnectAddressStep(raw: number): number {
  if (!Number.isInteger(raw) || raw <= NEW_CONNECT_STEPS.length) {
    return raw;
  }
  return newConnectStoredStep(raw);
}

/**
 * **THE POSITION OF A STEP, BY ITS ID** — `1` for `customer`, `4` for
 * `charges`.
 *
 * ⚠ **IT EXISTS SO NOTHING TYPES A STEP NUMBER.** The review step's four
 * *Edit* links each need the number of the step that captured the group, and a
 * literal there is right until the day the list changes shape — which is
 * today, for the second time in twelve days. `stepOwningRefusal` already
 * resolves the server's step ID this way for exactly the same reason.
 *
 * ⚠ **AN UNKNOWN ID ANSWERS `null`, IT DOES NOT GUESS.** A caller that gets
 * `null` has named a step this wizard does not declare, which is a bug in the
 * caller and not a destination to invent.
 */
export function newConnectStepNumber(id: string): number | null {
  const at = NEW_CONNECT_STEPS.findIndex((step) => step.id === id);
  return at < 0 ? null : at + 1;
}

// ══════════════════════════════════════════════════════════════════════════
// 9 · THE BUILD RECORD'S FOUR VOCABULARIES, IN WORDS — `DEF-MET-7805`
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE BUILD DETAIL PAGE PRINTED MACHINE TOKENS TO A CLERK IN FOUR PLACES,
// AND IT IS `DEF-MET-6453`'s SHAPE FOR THE FIFTH TIME.** Measured in a browser
// on `CON-26-0001`, 2026-09-28: the header pill read `requested`, the Units
// tab's STATE column read `requested` on eight rows, the Messages tab read
// `build_created` · `email` · `new_connect_confirmed` · `not_sent` across
// SEVEN rows and FOUR columns, and the Audit tab's WHAT column read
// `connection.committed`. Every one came from the same line shape —
// a `t()` on a key family that resolves in NONE of the eleven catalogues,
// with the CODE as its `defaultValue` — so the code is what a clerk reads,
// and **a code is not copy** (B14 rule 32).
//
// ⚠ **A `t()` WITH A `defaultValue` CAN NEVER THROW OR WARN**, no gate in this
// repo reads rendered output, and `G112` counts `defaultValue`s without asking
// whether one is a machine token. So this was found by a browser walk and by
// nothing else (hard-won law 6), on a page that had been live for hours.
//
// ⚠ **THE STATES ARE NOT HERE, DELIBERATELY.** `NewConnectsTab.STATE_LABELS`
// already holds that vocabulary and `newConnectStateLabels.test.ts` already
// asserts it complete against the SERVER's `CONNECTION_STATES`. The build
// record reads `connectionStateLabel` rather than taking a second opinion:
// two vocabularies for one idea is how two screens start disagreeing, which is
// B14 rule 34's reasoning one register along.
//
// ⚠ **THESE ARE `defaultValue`s AND NOT COPY**, exactly as `MOVE_OUT_STATE_
// LABELS` and `DisconnectsTab`'s own map are. The moment the text lane adds
// the keys the catalogues win; until then a clerk reads a word rather than a
// token. Every value is inside B14 rule 33's caps for a table cell.

/** The seven occasions `connection_messages` knows — three that send on
 *  commit and four `NOT_AT_CREATION` rows the record still lists.
 *
 *  ⚠ **`unit_energised` READS *Unit activated*, AND THAT IS A RULING RATHER
 *  THAN A PREFERENCE.** PO 2026-09-21, verbatim: *"we ahe to say activate"* —
 *  already ruled once on 2026-08-25 (`CR-032`, shipped `2.46.0`), so the word
 *  reaching a screen here was a MISSED INSTANCE of an old ruling and not a new
 *  question. `buildRecordPanels.test.tsx` has asserted `not.toMatch(/energi[sz]/i)`
 *  for the panels since they landed; the tabs were never asked.
 *  **The CODE is untouched** — it is the server's stable token, renaming it is
 *  a different change, and only the WORD is a clerk's business. */
export const BUILD_MESSAGE_OCCASION: Record<string, string> = {
  // The first three are STEP 7's own words, read from here rather than typed
  // again — `NewConnectCommunicationStep` and this page must not drift.
  build_created: "Build confirmed",
  contract: "The contract",
  quote_and_what_is_owed: "Quote and what is owed",
  schedule_of_works: "Schedule of works",
  inspection_booked: "Inspection booked",
  welcome_pack: "Welcome pack",
  unit_energised: "Unit activated",
};

/** `Occasion.channels`. Step 7 draws the same two words. */
export const BUILD_MESSAGE_CHANNEL: Record<string, string> = {
  email: "Email",
  pdf_print: "Print",
};

/** `messages.STATE_*` as the record serves them. Every row is `not_sent`
 *  today (`OQ-NOT-12521`), which is the STATE and not the reason — the reason
 *  has its own column and its own key family. */
export const BUILD_MESSAGE_STATE: Record<string, string> = {
  not_sent: "Not sent",
  not_asked: "Not asked",
  sent: "Sent",
  failed: "Failed",
};

/** The three template CLASSES this product seeds.
 *
 *  ⚠ **AN UNLISTED CODE IS SHOWN AS IT IS, AND THAT IS NOT THE DEFECT
 *  REPEATING.** A tenant publishes their own templates and names them
 *  themselves, so an unmapped code is the TENANT's word rather than ours;
 *  inventing one would be the product overwriting a name a utility chose.
 *  Only our own seeded classes are translated. */
export const BUILD_TEMPLATE_CLASS: Record<string, string> = {
  new_connect_confirmed: "New connect confirmed",
  contract_service_agreement: "Service agreement",
  new_connect_quote: "Connection quote",
};

/** The ten `connection.*` audit actions `apps/metering/connections.py` writes.
 *  Each reads as WHAT HAPPENED, in the past tense a clerk scanning a history
 *  expects, and none is over three words (B14 rule 33). */
export const BUILD_AUDIT_ACTION: Record<string, string> = {
  "connection.created": "Build started",
  "connection.submitted": "Build submitted",
  "connection.committed": "Build created",
  "connection.owner_account_created": "Owner account opened",
  "connection.held": "Put on hold",
  "connection.released": "Taken off hold",
  "connection.cancelled": "Build cancelled",
  "connection.waiting_on_set": "Waiting on recorded",
  "connection.payer_tagged": "Payer recorded",
  "connection.communication_sent": "Message sent",
};

/**
 * One map lookup, one `t()`, one place to get it wrong.
 *
 * ⚠ **THE FALLBACK IS THE CODE AND THAT IS ON PURPOSE.** A value this product
 * does not know is either a tenant's own word — which we must not overwrite —
 * or a vocabulary that grew on the server without the screen being told, which
 * is a finding and must be VISIBLE rather than swallowed into a blank cell.
 * An empty cell looks like nothing happened; a strange word gets reported.
 */
export function buildWord(
  words: Record<string, string>,
  code: string,
  keyPrefix: string,
  t: Translator,
): string {
  return t(`${keyPrefix}.${code}`, { defaultValue: words[code] ?? code });
}

// ══════════════════════════════════════════════════════════════════════════
// 10 · THE COMMIT'S STATED ABSENCES, AS FACTS — `DEF-CUS-7692`
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE `Created` SCREEN PRINTED 86 WORDS OF THE SERVER'S OWN ENGLISH
// RATIONALE**, measured in a browser on 2026-09-28 after a build was committed
// end to end. `NewConnectDone` rendered `{absence.detail}` — prose written in
// `apps/metering/connections.py` — so the last thing a clerk read after thirty
// acts was:
//
//   *"Nobody put a charge on this build, so there is nothing to raise. A build
//   prices itself from the charge codes a clerk picks and the quantities step 4
//   counts; none was sent. Reported rather than counted as $0.00 — a zero would
//   read as 'this build was free'."*
//
//   *"A sub-meter link is an assets relationship and this module has no seam
//   that writes one. Reported rather than counted as 0 — a zero would read as
//   'we made none' where the truth is 'we cannot make them from here'."*
//
// **TWO RULES AT ONCE.** B14 rule 33 puts RATIONALE — *why the product works
// this way* — at ZERO WORDS ON SCREEN, and `BR-SHL-020 r2` says the sentence
// is composed in the eleven catalogues from a key with nothing English
// crossing the wire. `absence.detail` is server prose, so `G112`'s
// `defaultValue` count could not see it, `G15`'s key count could not see it,
// and no gate here reads rendered output.
//
// ⚠ **THE SWEEP THAT OWNS THIS COPY ALREADY DELETED THE SAME TWO SENTENCES
// FROM STEP 8** (`2db5700c4`, 2026-09-28 — *"New Connect loses 35 sentences a
// clerk had to read"*, PO bugs 1 and 14). Its scope came from the drawing's
// *Removed from this step* lists, and **the Created screen is not a step**, so
// it was never in scope and the words survived one screen later.
//
// ⚠ **RULE 33 REMOVES RATIONALE RATHER THAN SHORTENING IT, SO WHAT IS LEFT IS
// THE FACT AND ONLY THE FACT.** The absences are still STATED — `NewConnectDone`'s
// own docstring is right that a person who has just built 26 units must not
// find out later — but *why* the platform cannot do a thing belongs in the
// code and the register, which is where the server's `detail` still goes: it
// stays on the payload untouched, for support and for the log.

/** One short fact per `unavailable[]` code the commit itself can answer with.
 *
 *  ⚠ **SIX CODES ARE `connections.py`'s OWN** —
 *  `premises_created_at_step_1_not_at_commit` (filtered out by both commit
 *  doors today, mapped so it cannot surprise anyone), `build_names_no_charge`,
 *  `quote_has_no_chargeable_line`, `no_door_from_metering`,
 *  `unmetered_services_are_not_on_the_payload` and
 *  `template_republished_since_proposal`. **TWO MORE ARRIVE WITH A PAYMENT
 *  TAKEN AT STEP 4** (`DEF-CUS-9174`): `payment_exceeded_the_bill_and_carries_
 *  as_credit` (connections.py's own, `BR-PAY-010`) and
 *  `recipient_absent_on_record` (the receipt's queue write, notifications).
 *  Each value is a FACT at six words or fewer (B14 rule 33) and none of them
 *  says why. The catalogue holds them under `customers.newConnect.done.absence.`
 *  in all eleven languages; these English strings are only the fallback. */
export const COMMIT_ABSENCE_FACT: Record<string, string> = {
  build_names_no_charge: "No charge on this build.",
  quote_has_no_chargeable_line: "Nothing on the quote to charge.",
  no_door_from_metering: "No sub-meter links.",
  unmetered_services_are_not_on_the_payload: "Unmetered services not recorded.",
  template_republished_since_proposal: "Order uses the published version.",
  premises_created_at_step_1_not_at_commit: "The address already existed.",
  payment_exceeded_the_bill_and_carries_as_credit: "Extra payment held as credit.",
  recipient_absent_on_record: "A receipt has no recipient.",
};

/** ⊕ `DEF-MET-9245` — the same absence, said of the ONE copy that had no
 *  address. A FACT, six words or fewer (B14 rule 33). */
export const RECEIPT_COPY_ABSENT: Record<string, string> = {
  sms: "Text receipt: no mobile number.",
  email: "Email receipt: no email address.",
};

/**
 * Codes that reach the Created screen and are NOT for a clerk — bookkeeping
 * notes about how the platform did its work, each with nothing to act on.
 *
 * ⚠ **`DEF-CUS-9174` — THESE PRINTED AS RAW CODES.** PO, 2026-10-02, with a
 * screenshot: *"do not show databse id on this screen"*. Measured in Chromium
 * the same day on a real commit with a payment taken at step 4: twelve tokens
 * such as `template_pin_resolved_at_queue_write` (three times) and
 * `print_floor_channel_added` (twice). `BR-MET-1187` forwards the payment's own
 * `problems` onto the commit's `unavailable[]`, and the receipt's queue writes
 * ride those problems, so the list is open-ended — `connections.py`'s six were
 * never the whole of it. Listed here BY NAME with the reason, so a later lane
 * meeting one with no words finds out why rather than assuming it was missed:
 *
 *   * `receipt_queued`, `receipt_email_queued`, `receipt_sms_queued` — a
 *     receipt was queued. That is the platform working, not an absence.
 *   * `template_pin_resolved_at_queue_write` — which letter version the queue
 *     row pinned. Internal provenance.
 *   * `print_floor_channel_added` — a printed copy was added because the rule
 *     says one always goes. Rationale, zero words (rule 33).
 *   * `channel_has_no_rule_toggle` — the utility's message rules have no switch
 *     for this channel. Nothing a counter clerk can act on.
 *   * `invoice_composition_unavailable` — the payment met whole bills only; a
 *     build raises one bill, so it says nothing here. Payments still words it
 *     on its own screens, where several bills are in play.
 *
 * ⚠ **AND A CODE IN NEITHER LIST RENDERS NOTHING — NEVER ITSELF.** This
 * reverses `DEF-CUS-7692`'s fallback, which printed an unknown code on purpose
 * *"so it gets reported"*; the PO has now reported it, and B14 rule 31 puts
 * anything internal at zero on screen. `problemWords` is payments' one reading
 * of its own family and makes the same choice.
 */
export const COMMIT_NOTES_NOT_FOR_A_CLERK: readonly string[] = [
  "receipt_queued",
  "receipt_email_queued",
  "receipt_sms_queued",
  "template_pin_resolved_at_queue_write",
  "print_floor_channel_added",
  "channel_has_no_rule_toggle",
  "invoice_composition_unavailable",
];

/**
 * The sentence for one stated absence, or `null` when a clerk is shown nothing.
 *
 * ⛔ **SUPERSEDED (`DEF-CUS-9174`, 2026-10-02):** this read *"AN UNKNOWN CODE
 * RENDERS THE CODE … A strange short token is ugly and gets REPORTED"*. It was
 * reported — twelve of them, by the PO, as a defect. Falling back to `detail`
 * is still wrong (that is `DEF-CUS-7692` returning), and the code is now wrong
 * too (B14 rule 31). The server's own six are still enumerated in
 * `newConnectDoneAbsences.dom.test.tsx`, so a NEW commit code still goes red
 * there rather than vanishing.
 *
 * Three sources, in order: a bookkeeping note is dropped; the commit's own
 * codes read `customers.newConnect.done.absence.<code>`; anything else is a
 * payment's problem riding the commit (`BR-MET-1187`) and reads PAYMENTS' own
 * words through `problemWords` — B14 rule 43, one reading of that family, so a
 * payment that has not cleared says the same thing here as on the payment
 * itself. A code with no words anywhere is `null`, never the code.
 */
export function commitAbsenceFact(
  code: string,
  t: Translator,
  channel?: string | null,
): string | null {
  if (COMMIT_NOTES_NOT_FOR_A_CLERK.includes(code)) {
    return null;
  }
  // ⊕ `DEF-MET-9245` — a receipt copy with no address names ITS channel. The
  // bare sentence read as if nobody got a receipt while email and print had
  // both gone; a text with no mobile number is ordinary (BR-BIL-036).
  const perChannel = code === "recipient_absent_on_record" && channel ? RECEIPT_COPY_ABSENT[channel] : undefined;
  if (perChannel !== undefined) {
    return t(`customers.newConnect.done.absence.recipient_absent_on_record_${channel}`, {
      defaultValue: perChannel,
    });
  }
  if (code in COMMIT_ABSENCE_FACT) {
    return t(`customers.newConnect.done.absence.${code}`, {
      defaultValue: COMMIT_ABSENCE_FACT[code],
    });
  }
  return problemWords(t, code);
}

/**
 * The Created screen's notes: one per distinct SENTENCE, in arrival order.
 *
 * ⚠ **DE-DUPLICATED BY WHAT IS SHOWN, NOT BY CODE.** One commit queued three
 * receipts and the same code arrived three times; two codes that read the same
 * sentence must not print it twice either.
 */
export function commitAbsenceNotes(
  absences: readonly { code?: string | null; channel?: string | null }[],
  t: Translator,
): { code: string; sentence: string }[] {
  const seen = new Set<string>();
  const notes: { code: string; sentence: string }[] = [];
  for (const absence of absences) {
    const code = absence.code ?? "";
    if (code === "") continue;
    const sentence = commitAbsenceFact(code, t, absence.channel);
    if (sentence === null || sentence.trim() === "" || seen.has(sentence)) continue;
    seen.add(sentence);
    notes.push({ code, sentence });
  }
  return notes;
}
