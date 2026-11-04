// ── Trace ──────────────────────────────────────────────
// Change:   Lane E wave 1 — SPLIT OUT OF `NewConnectWizard.tsx`, unchanged.
//           The wizard held all eight steps in one ~1,900-line file and five
//           lanes are queued on different steps; in this shared tree two lanes
//           in one file is how work gets reverted by subtraction (CLAUDE.md
//           law 11, eight recorded occurrences). One file per step, and the
//           DRAFT is the piece they all read.
// Rules:    BR-MET-112 (*"nothing is written until step 8"* — this module makes
//           no request at all; it only shapes what the last step posts) ·
//           BR-MET-111 (the owner captured at step 1 BECOMES a customer) ·
//           BR-MET-113 (the owner gets an ACCOUNT and the quote is tagged to
//           it) · hard rule 2 (no money is summed here — `quoteTotal` travels
//           as the server's own string)
// Tests:    NewConnectWizard.test.tsx imports `emptyDraft`, `draftUnits`,
//           `draftUnitServices`, `draftManifest` and `commitPlanOf` through
//           `NewConnectWizard.tsx`, which re-exports every one of them.
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY THE DRAFT IS NOT IN `newConnectShared.tsx`.** That file is the pure
// half BOTH this wizard and the connection detail screen read. The draft is the
// WIZARD's own state shape — nothing outside the wizard has one — so putting it
// there would hand a second screen a type it can never hold. It is also the one
// piece every step file needs, which is why it is a file of its own rather than
// a section of the orchestrator: a step lane that imports the orchestrator to
// get a type would build the import cycle this split exists to prevent.
import type {
  CommitPlan,
  ConnectionDetail,
  RequestPrefillDocument,
} from "./newConnectEndpoints";
// ⚠ **THE PARK HELPERS, NOT THE PARK STORE.** `hydrateForm` and
// `parkedStringList` are pure functions on a JSON blob; `wizardPark.ts` also
// exports a React hook and a transport, and importing the module pulls neither
// into this one's graph — it takes no `react-query` dependency here because
// nothing in this file calls the hook.
import { hydrateForm, parkedStringList } from "./wizardPark";
import type { WizardParkSubjectRef } from "./wizardParkEndpoints";
import { coOwnersPayload, emptyCoOwner, hydrateCoOwners, idOnFileMask } from "./CoOwnerCards";
import type { CoOwnerDraft } from "./CoOwnerCards";
import type { CustomerSearchRow } from "./customerEndpoints";
import type { MoveInDocDraft } from "./MoveInDocumentsTable";
import { billingPayload, billingProblems, emptyStepBillingOwn } from "./moveInWizard/billingModel";
import type { BillingProblem, StepBillingOwn } from "./moveInWizard/billingModel";
import {
  OCCUPANCY_DEFAULT,
  expandUnitPattern,
  liveOccupancy,
  manifestPreview,
  capacityIsOnTheUnit,
  serviceFamily,
  takesAMeter,
} from "./newConnectShared";
import type {
  DraftUnit,
  ManifestPreview,
  OccupancyChoice,
  UnitPattern,
} from "./newConnectShared";
// CR-070 wave E — the proposal is a server READ and the draft deliberately
// keeps no copy of it, so only the TYPE crosses this boundary.
import type { ProposedWorkOrder } from "@/features/work/workEndpoints";

// ══════════════════════════════════════════════════════════════════════════
// THE DRAFT
// ══════════════════════════════════════════════════════════════════════════

/** Step 1. **`Becomes a customer`** — the green badge and the mechanism in the
 *  screen's own words: *"These details create a customer record, which is what
 *  makes the owner billable at step 6. Without them the connection charges have
 *  nowhere to go."* This is DEF-650's missing party (BR-MET-111). */
export interface OwnerForm {
  name: string;
  kind: string;
  /**
   * **The customer CATEGORY — `account_type`, the platform's own class
   * (`BR-CUS-053`), drawn `NEW` on `step1-customer.png` and required there.**
   *
   * ⚠ **IT IS NOT `kind` AND IT IS NOT `partyKind`, AND ALL THREE ARE ON ONE
   * ROW OF THE DRAWING.** `kind` is the owner's RELATION to the building
   * (builder, landlord, occupier). `partyKind` is person or company, which
   * decides which identifier counts. **This** is what the utility bills them
   * AS — residential, commercial, industrial — and it is the tenant's own
   * list, read through `useAccountCategories`, never typed into a screen.
   */
  category: string;
  subCategory: string;
  /** Drawn `NEW` on `step1-customer.png`, optional, `MM/DD/YYYY` in the
   *  drawing and an ISO `YYYY-MM-DD` here — `DatePickerField` owns the
   *  regional rendering and nothing in this wizard formats a date itself. */
  dateOfBirth: string;
  email: string;
  phone: string;
  /**
   * The drawn **External system reference**, placeholder *"if known"*, optional
   * — the owner's id in whatever the utility ran before this product.
   *
   * ⚠ **IT BELONGS TO THE OWNER RATHER THAN TO THE BUILD, AND THE DRAWING PUTS
   * IT THERE:** it sits inside the *Who is asking* group, under *Owner or
   * developer*. The backend home it is written for is `customers.external_ref`
   * — a nullable text column, unique per tenant, that `apps/customers/models.py`
   * describes as *"the LEGACY system's identifier"*. **Nothing reads it yet**,
   * and that is a property of the DOOR rather than of this field: the wizard's
   * commit (`POST /connections/commit` with no id) is still unserved, so no
   * member of `CommitPlan` is read today. See `newConnectEndpoints.ts`.
   */
  externalRef: string;
  /**
   * **`person` · `company` · `""` for unstated — and it is NOT `kind`**
   * (`DEF-MET-5438`, decision log 2026-09-16 §3).
   *
   * ⛔ **NEVER DERIVED FROM `kind` ABOVE.** `OWNER_KINDS` is a CLASSIFICATION —
   * builder or developer, property owner, landlord, occupier — and all four are
   * refused by the accounts door's `_validate_customer_kind` BY NAME. A
   * landlord is routinely a person and routinely a company, so deriving one
   * from the other would write an invented answer into a customer's permanent
   * record. It is asked BY NAME or it is not answered.
   */
  partyKind: string;
  /** A person's, and only a person's (`BR-CUS-1022`). */
  ssn: string;
  drivingLicence: string;
  /** A company's, and only a company's. */
  taxId: string;
  /**
   * ⊕ **`DEF-CUS-9074` — the LAST FOUR of the Tax ID a business typed on its
   * portal application**, `""` when there is none. Never sent: the server
   * reads the number where it is stored once (`DEF-CWP-9045`). It is what lets
   * step 1 stop holding a new business for a number the application holds.
   * Optional because a parked draft may predate it.
   */
  applicationTaxIdLast4?: string;
  /**
   * ⊕ **`DEF-CUS-9828` (N2) — the LAST FOUR of an SSN or a driving licence
   * given ON THE REQUEST**, `""` when there is none. Shown beside the empty box
   * (*Provided on the request · ends 1234*); never sent and never copied into
   * the box — the number is the request's and is read where it is stored.
   */
  applicationSsnLast4?: string;
  applicationLicenceLast4?: string;
  /**
   * **The customer the clerk PICKED out of the search** — `BR-CUS-019`, *"the
   * clerk's explicit answer wins over everything"*.
   *
   * ⚠ **THE ID TRAVELS AND THE NUMBER IS WHAT IS SHOWN** (B14 rule 31). Both
   * are kept because they answer different questions: `matchedCustomerId` is
   * what `customer.customer_id` names in the payload, and `matchedCustomerNo`
   * (`C-00902`) is the only one of the two a clerk may ever see.
   */
  matchedCustomerId: string | null;
  matchedCustomerNo: string | null;
  /**
   * ⊕ `CR-164-BRC10` item 11 — the customers the clerk answered *Not this
   * person* for. Held on the DRAFT so Back to step 1 does not ask again.
   * Never sent; optional because a parked draft predates it.
   */
  dismissedMatchIds?: string[];
  /**
   * ⊕ lane CF-1 (2026-10-18) — the shared customer form's *Contact by* and
   * *Government ID* (its last four, BR-CUS-045), sent on the owner block and
   * written on the account's contact. Optional: a parked draft predates them.
   */
  contactBy?: string;
  govIdLast4?: string;
  /** ⊕ lane CF-1 — the search row the clerk linked, so the Identity panel's
   *  one-line *Linked* state draws it. Never sent. */
  matchedRow?: CustomerSearchRow | null;
}

/** ⚠ **NO LONGER THE LIST STEP 1 OFFERS (`DEF-CUS-9192`, `CR-164-BRC10`).**
 *  Step 1's *Owner type* now reads the utility's own owner list,
 *  `/lookups/owner_categories` (`BR-TEN-150`: `owner_occupier` · `landlord` ·
 *  `property_manager` · `hoa` · `builder`, edited in Settings). These four are
 *  the codes builds were STORED under before that, and they are kept ONLY so a
 *  record written then still reads as words (`buildViews.stepOneLabel`); a
 *  build made today stores the tenant's code. Do not offer them on a screen. */
export const OWNER_KINDS = [
  { code: "builder_developer", en: "Builder or developer" },
  { code: "property_owner", en: "Property owner" },
  { code: "landlord", en: "Landlord" },
  { code: "occupier", en: "Occupier" },
] as const;

/** ⚠ **NO LONGER THE LIST STEP 1 OFFERS (`DEF-CUS-9822`, 2026-10-06).** Step 1's
 *  *Sub-category* now offers the utility's own sub-types under the chosen
 *  category (Settings › Account types, `accountSubtypesUnder`). These two are
 *  kept ONLY so a draft stored with one still reads as words; do not offer
 *  them on a screen, and they are never sent as an account's sub-type. */
export const OWNER_SUBCATEGORIES = [
  { code: "construction_temporary", en: "Construction temporary" },
  { code: "permanent", en: "Permanent" },
] as const;

/** `DEF-CUS-9822` — the owner block's `account_subtype`, or nothing: empty and
 *  the two pre-list codes above send none. */
export function ownerAccountSubtype(subCategory: string): { account_subtype?: string } {
  const code = subCategory.trim();
  if (code === "" || OWNER_SUBCATEGORIES.some((row) => row.code === code)) return {};
  return { account_subtype: code };
}

/** Step 1's three exclusive cards and their sub-lines, which ARE the
 *  definitions.
 *
 *  ⚠ **`sub` IS NO LONGER RENDERED (PO 2026-09-28, reported bug 1).** The three
 *  sub-lines printed under the radio on step 1; the redesign drawing lists them
 *  under *Removed from this step* — each repeated what its own option already
 *  said, which is B14 rule 32, and the remainder was rationale at rule 33's
 *  zero words. They are kept here because this table IS the definition of the
 *  three choices and rule 33 puts rationale in the code. **Do not re-mount them
 *  on a screen.** */
export const CONNECT_SCOPES = [
  {
    code: "new_premise",
    en: "A new premise",
    sub: "nothing is served at this address yet",
  },
  {
    code: "new_units",
    en: "New units at an existing premise",
    sub: "the building is served; these units are not",
  },
  {
    code: "new_service",
    en: "A new service at an existing unit",
    sub: "they have service and want one more",
  },
] as const;

/**
 * ══════════════════════════════════════════════════════════════════════════
 * **HOW THE WORK IS DONE — THE THREE MODES AND THEIR WORDS (`DEF-CUS-6100`)**
 * ══════════════════════════════════════════════════════════════════════════
 *
 * ⚠ **THE REVIEW SCREEN PRINTED `our_crew` TO A CLERK, ON THE LAST SCREEN
 * BEFORE THE COMMIT, ON EVERY ONE OF SEVEN BUILDS WALKED.** Step 1's radios
 * read *Our crew did it* and *External system* because they passed a
 * `defaultValue`; step 8 asked the same catalogue key with `defaultValue:
 * draft.mode` and so printed the STORED CODE. B14 rule 31 — no database value
 * is ever the visible value of a field — and rule 32 keeps internal codes out
 * of clerk-facing copy.
 *
 * ⚠ **ONE LIST, SO THE TWO SCREENS CANNOT DISAGREE.** The words were typed out
 * at the radios and nowhere else, which is what let a second reader of the same
 * fact invent its own fallback. This is `CONNECT_SCOPES`' shape, one field
 * along, and `connectModeWord` is the only way either screen reads it.
 */
export const CONNECT_MODES = [
  { code: "our_crew", en: "Our crew did it" },
  { code: "external", en: "External system" },
  // Drawn, and DEAD: the backend raises `NotImplementedError("OQ-249")` for it
  // and step 1 offers it disabled beside the two real ones (B14 rule 37 —
  // `We schedule it` is drawn SELECTED and that is an illustration). It is in
  // this list because a draft parked before the control was disabled can still
  // hold it, and the review screen must then read a WORD.
  { code: "we_schedule", en: "We schedule it" },
] as const;

/** What `connection_mode()` answers when a build's orders DISAGREE — a real
 *  and normal state, never a choice. It is deliberately not in the list above:
 *  that list draws the wizard's radios (`DEF-CUS-7804`). */
export const MODE_MIXED = "mixed";

/**
 * One mode code → the word a clerk reads. **Never the code** (`DEF-CUS-6100`).
 *
 * ⚠ **A MISSING WORD FAILS LOUDLY RATHER THAN FALLING BACK TO THE CODE**, which
 * is `DisconnectsTab.disconnectStateLabel`'s posture and is deliberately the
 * same one: rendering the code is how a missing label stays invisible — it
 * looks deliberate, it is never blank, and no gate in this repo reads
 * clerk-facing copy. So landing on an unknown mode writes a `console.error`
 * naming it and the screen states an absence instead.
 *
 * ⚠ **THE CATALOGUE KEY IS ASKED FIRST AND THE ENGLISH IS THE FALLBACK**, so a
 * German clerk reads German the day the key is translated and nobody reads a
 * raw identifier in the meantime.
 *
 * ⚠ **`mixed` IS A DERIVED READING AND IS NOT IN `CONNECT_MODES` —
 * `DEF-CUS-7804`, 2026-09-29.** `connections.connection_mode()` answers
 * *"one mode across every order → that mode; more than one → `mixed`, which
 * is a real and normal state"* (§8.3: *"a utility that does its own water
 * work and contracts out gas is the normal case, not the edge"*), and the New
 * connects list's `Mode` column shows it. It is handled HERE rather than in
 * that column, because the whole argument for this function is that one fact
 * has one reader — and it is kept OUT of `CONNECT_MODES`, because that list
 * renders the wizard's RADIOS and `mixed` is not a thing a clerk may choose.
 */
export function connectModeWord(
  mode: string,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  if (mode === MODE_MIXED) {
    return t(`customers.newConnect.mode.${MODE_MIXED}`, { defaultValue: "Mixed" });
  }
  const known = CONNECT_MODES.find((one) => one.code === mode);
  if (known === undefined) {
    console.error(
      `NewConnect: the draft holds the mode "${mode}" and CONNECT_MODES has no word for ` +
        "it, so the screen states an absence rather than the code (DEF-CUS-6100). Add the " +
        "mode and its eleven catalogue keys; newConnectModeWords.test.ts is already red.",
    );
    return t("customers.newConnect.mode.unnamed", { defaultValue: "Not named yet" });
  }
  return t(`customers.newConnect.mode.${known.code}`, { defaultValue: known.en });
}

/**
 * One scope code → the word a clerk reads — `CONNECT_SCOPES`' own `en` behind
 * the catalogue key, with the same loud absence as the mode above.
 *
 * ⚠ **IT WAS NOT BROKEN AND IT IS HERE ANYWAY**, because the review screen
 * spelled the fallback out inline (`CONNECT_SCOPES.find(…)?.en ?? draft.scope`)
 * — correct today and one careless edit from printing `new_premise`. Two
 * readings of one fact in one file is what `DEF-CUS-6100` was.
 */
export function connectScopeWord(
  scope: string,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  const known = CONNECT_SCOPES.find((one) => one.code === scope);
  if (known === undefined) {
    console.error(
      `NewConnect: the draft holds the scope "${scope}" and CONNECT_SCOPES has no word ` +
        "for it, so the screen states an absence rather than the code (DEF-CUS-6100).",
    );
    return t("customers.newConnect.scope.unnamed", { defaultValue: "Not named yet" });
  }
  return t(`customers.newConnect.scope.${known.code}`, { defaultValue: known.en });
}

/**
 * One cell of step 4's grid that the clerk has moved OFF its default.
 *
 * Every member is optional and an absent member means *"still the default"*.
 * The defaults themselves live on the step, next to the catalogues they are
 * read from, because they change with the premise and with the tenant's own
 * reference lists — a value frozen into the draft would stop following them.
 */
export interface UnitServiceCell {
  /** `false` DROPS this service at this unit. Inheritance is a default, not a
   *  lock — the common area takes electric and water and no sewer. */
  taken?: boolean;
  /** `asset_types.code` — the tenant's own catalogue row. */
  assetType?: string;
  /** `service_size_classes.code`. */
  sizeClass?: string;
  /**
   * **MORE PIECES OF THE SAME DEVICE ON THIS UNIT — one size each (`OQ-1361`
   * fire-line half, PO 2026-10-02: *"A fire service gets a "fire line" item
   * with a size … like a trash cart"*).** The row above is the FIRST piece;
   * each entry here is one more, added with `+ Add row`. A 6" fire line and
   * two 2" lines is `sizeClass: "FL-6"`, `more: ["FL-2", "FL-2"]`, and the
   * commit sends it as `FL-6 × 1` and `FL-2 × 2`.
   *
   * ⚠ **A ROW PER PIECE AND NOT A `Qty` CELL, ON PURPOSE.** The step's columns
   * are the PO's (decision log 2026-09-28, 13(c)) and the drawn `Qty` is held
   * by `OQ-CUS-12770`, OPEN, because it multiplies a price on an invoice. A
   * cart has always been one row; a second cart, a second fire line or a third
   * panel is one more row of the same kind — so the count is COUNTED from the
   * rows, never typed.
   */
  more?: string[];
  /* ⛔ **`installDate` WAS HERE AND IS GONE — `DEF-CUS-6101`, 2026-09-21.**
     Step 4 drew one date picker per unit-service — sixteen on a seven-unit
     block — the value landed here correctly, and `commitPlanOf` never read it
     back out: the payload's meters carry `unit_label`, `service` and `asset_no`
     and nothing else. A field on this type with no reader is where the
     keystrokes went. **Where a planned per-unit date should live is
     `OQ-MET-12571`, OPEN**, and nothing here answers it — the build's own
     planned date is `targetActivation`, typed once at step 1, and that one does
     travel. Do not re-add this key without the payload that carries it. */
  /** `work_order_templates.id` — a stamp target, never shown (B14 rule 31). */
  workOrderTemplateId?: string;
}

/**
 * The grid's key. **A UNIT LABEL CAN CONTAIN ANYTHING A PERSON TYPES** — a
 * prefix of `Bldg-A/2` is ordinary — so the separator is the ASCII UNIT
 * SEPARATOR rather than a hyphen or a slash, which a label can hold and which
 * would then collide two different rows onto one cell.
 *
 * WARNING: IT IS WRITTEN AS AN ESCAPE ON PURPOSE. A raw U+001F in the source
 * is INVISIBLE - it survives no copy-paste, no reformat and no careful
 * reader, and the day it is lost every key silently becomes `1electric`.
 */
export function unitServiceKey(unitLabel: string, service: string): string {
  return `${unitLabel}\u001F${service}`;
}

export interface NewConnectDraft {
  /**
   * **`DEF-CUS-6109` — the DRAFT BUILD this wizard is finishing, or `null`.**
   *
   * PO ruling 2026-09-21: approving an application into a new connection
   * *"may create a new conenct request - as draft request"*, so on that path
   * the `connections` row exists before step 1 and the last button FINISHES it
   * instead of creating a second build beside it. `commitPlanOf` sends it as
   * `connection_id`.
   *
   * ⛔ **`null` IS THE ORDINARY CASE AND MUST STAY ORDINARY.** A build a clerk
   * starts directly has no application and no draft, and every step, every
   * rule and the commit behave identically — `request_id` is PROVENANCE, never
   * a dependency (`BR-MET-1178`).
   */
  connectionId: string | null;
  /**
   * **`BR-SHL-048 (d)` — that build's own number, `CON-26-0129`.**
   *
   * PO ruling 2026-09-21: *"this is big problem - we cannot create two build -
   * you can update the existing build"*. `connectionId` above is what the
   * commit finishes; this is what a clerk READS while it is unfinished. The
   * park copies it onto `subject_ref`, the server takes it as the draft's
   * `reference`, and the New connects tab draws it — so the row a parked
   * wizard leaves behind names the build it belongs to instead of nothing.
   *
   * ⚠ **IT IS CARRIED, NEVER COMPOSED.** Nothing here builds a `CON-` string;
   * it is the server's own number, copied, and `null` wherever there is no
   * build yet.
   */
  connectionNo: string | null;
  /** The application this build came from, for the *where this came from* line
   *  step 1 shows. `null` on a build raised directly. */
  requestNo: string | null;
  owner: OwnerForm;
  scope: string;
  targetActivation: string;
  mode: string;
  premise: {
    /**
     * ⚠ **THE PREMISES THE CLERK PICKED OUT OF THE REGISTER, OR `""` FOR A NEW
     * ONE — `DEF-CUS-5468`.** Hard rule 8 puts an address on `premises` and
     * nowhere else, which makes this wizard the one door in the product that
     * can create a SECOND row for a building that already has one. The search
     * on step 2 is that rule enforced at the only place it can be enforced.
     *
     * Set means the build hangs off an address already on file, and
     * `commitPlanOf` sends it as `premises.id` — the key `commit_new_connect`
     * turns into `premises_id` instead of creating anything.
     */
    premisesId: string;
    /** `CR-161-BRC10` W3 — the tenant's own Premises fields typed on this step
     *  for a NEW property. Optional so every draft parked before it opens. */
    customData?: Record<string, unknown>;
    /** `premises.name` — the building's own name, which a warehouse, a campus
     *  or a pump station has and a house does not. The column has always
     *  existed; nothing asked for it (`DEF-CUS-5468`). */
    name: string;
    address: string;
    /**
     * ⚠ **THREE FIELDS, NOT ONE BOX — the blueprint p087 draws `City *`,
     * `State *` and `ZIP code *` beside the street line (`DEF-CUS-5468`).**
     * `AddPremisesWizard` has collected all three since S16 shipped, so the
     * two doors that create a property now agree about what an address is.
     * Before this, every property built here left `premise_locality` null and
     * the account header's town line was blank forever.
     */
    city: string;
    state: string;
    postalCode: string;
    premiseType: string;
    /**
     * `CR-162-BRC10` (Q1) — the ACCOUNT TYPE the chosen premises type takes
     * (`master` / `regular`), copied from the tenant's own premises-type row
     * whenever the type changes (`NewConnectWizard`). Optional because a draft
     * parked before it existed has none; absent or `""` means *not known*, and
     * the master rule then counts homes, as on 2.442.0.
     */
    accountKind?: string;
    parcelRef: string;
    readRoute: string;
    /**
     * **`Unit, apt. or suite` — ENABLED AND OPTIONAL SINCE THE 2026-09-28
     * DRAWING, WHERE IT WAS DISABLED AND EMPTY BEFORE.**
     *
     * The redesign's own *Changed 28 Sep, on your review* note: *"Unit, apt.
     * or suite is enabled and optional. It is part of the postal address; unit
     * labels stay on step 3."* So this is the POSTAL line — `Suite 200` on an
     * envelope — and it is **not** a unit record. The units themselves are
     * still named by `pattern` on step 3, and hard rule 8 is untouched: this
     * is part of the premises' own address, stored with it.
     */
    unit: string;
    /**
     * **The building's point — `premises.lat` / `premises.lng`, drawn `NEW`.**
     *
     * PO: *"you should include lat and long and verified tag - all these will
     * be options"*. Held as STRINGS, never numbers: what the clerk typed is
     * what is sent, and a float round-trip is how `41.019800` becomes
     * `41.0197999999`.
     *
     * ⚠ **THIS IS THE BUILDING'S AND NOT A UNIT'S.** `BR-MET-1162` lets a UNIT
     * carry its own pair, and where it does those are the truth for that unit
     * — with the building's as the fallback. The rule's last clause is a
     * screen obligation: *every screen showing a point says which of the two
     * it is showing*, which this step does in one line beside these boxes.
     */
    lat: string;
    lng: string;
    /** The drawn `Location verified` tick, optional. A point somebody has
     *  stood on is a different fact from a point somebody typed. */
    locationVerified: boolean;
  };
  /**
   * **THE SECOND PERSON ON THE ACCOUNT — the drawing's `Co-applicant NEW`.**
   *
   * `null` until the clerk presses *Add a co-applicant*, which is the drawn
   * state: the panel holds one button and nothing else until then. The fields
   * it opens are the owner's own — *"Opens the same fields as the owner."* —
   * so the same `OwnerForm` shape is reused rather than a second one declared,
   * and one identity rule (`accountIdentityShortfall`) can read both.
   */
  coApplicant: OwnerForm | null;
  /**
   * **WHERE THE BILL GOES — `customers.addresses` `kind='mailing'`.**
   *
   * ⚠ **THIS IS ONE OF HARD RULE 8's THREE NAMED EXCEPTIONS AND NOT A SECOND
   * COPY OF THE SERVICE ADDRESS.** The rule puts an address on `premises` and
   * nowhere else; the mailing address is a DIFFERENT FACT — for a landlord it
   * is another building entirely — and the rule names it by name.
   *
   * ⚠ **`sameAsService` TICKED IS THE DRAWN DEFAULT, AND WHILE IT IS TICKED
   * THE FIVE BOXES ARE READ-ONLY AND WALKED FROM THE PREMISE.** They are not
   * a copy the clerk may edit into disagreement with step 2; untick and they
   * become their own answer.
   */
  mailing: {
    sameAsService: boolean;
    address: string;
    unit: string;
    city: string;
    state: string;
    postalCode: string;
  };
  /** How this customer is written to and in what language — the drawing's
   *  `Communication NEW` panel. `language` empty means *the utility's own*,
   *  which `PortalLanguageField` fills from `GET /shell/display`. */
  communication: {
    language: string;
    paperlessBill: boolean;
    smsReminders: boolean;
  };
  /**
   * **THE TENANT'S OWN EXTRA ACCOUNT FIELDS — the drawing's `Account details`.**
   *
   * ⚠ **THE THREE FIELDS DRAWN THERE ARE AN EXAMPLE AND NOT A LIST TO TYPE
   * OUT**, and the drawing says so in its own words: *"The clerk fills these
   * in. They are the extra fields this utility set up in Settings, so the
   * three drawn here are only an example … Nothing appears if the utility set
   * none up."* That is `CustomFieldsInput`, exactly — and hand-typing *Service
   * area · Rate class code · Legacy account no.* here would be the third
   * hand-typed list of a thing the server owns (the `fire` defect's shape).
   */
  accountCustomData: Record<string, unknown>;
  /**
   * ⊕ **`CR-164-BRC10` wave 2 — the OWNER's own customer fields**, the slot
   * `NEW_CONNECTION_OWNER` (`tenancy.custom_fields.SLOTS`). Sent as the owner
   * block's `customer_custom_data` and written on the customer this build
   * creates. Optional because a parked draft predates it.
   */
  ownerCustomData?: Record<string, unknown>;
  pattern: UnitPattern;
  /** Step 4 — what the STREET can deliver. The grid below can only offer what
   *  is ticked here. */
  premiseServices: string[];
  /** Step 4's `Apply to all units` bulk row, for the non-common-area units. */
  apartmentServices: string[];
  /** The common area's own set — trash and storm water on the drawn build. */
  commonAreaServices: string[];
  /** Step 5 — a published plan id, or "" for none chosen. */
  planApartments: string;
  planCommonArea: string;
  /** Step 8's four-way radio. */
  occupancy: OccupancyChoice;
  /**
   * **THE OWNER ACCOUNT'S BILLING PREFERENCES — `step4-charges.png`'s
   * *Billing preferences* panel, `CR-150-BRC09` task 11.**
   *
   * ⚠ **THEY TRAVEL, AND THAT IS THE WHOLE REASON THEY ARE ON THE DRAFT AND
   * NOT COMPONENT STATE.** `customers.CREATE_FIELDS` has accepted `autopay`,
   * `tax_exempt`, `tax_exempt_ref` and `tax_exempt_expires` since the module
   * was built; New Connect's own `create_owner_account` assembled a fixed
   * dict and forwarded none of them, so four drawn boxes would have been four
   * values discarded at commit — `DEF-CUS-5485`'s shape (*"THE THREE COMMIT
   * FIELDS NOBODY SENT"*), and hard-won law 2.
   *
   * ⚠ **THEY LAND ON THE OWNER'S ACCOUNT AND NOWHERE ELSE.** A build that
   * opens no owner account has no account for a preference to sit on, and
   * nothing here invents one — `BR-MET-112`.
   *
   * ⚠ **`autopay` IS CAPTURE-ONLY IN v1** (`BR-CUS-059`). Ticking it records
   * an intention; no payment path reads it yet. That is a fact about the
   * platform, stated here and at ZERO words on screen (B14 rule 33).
   */
  billing: {
    autopay: boolean;
    taxExempt: boolean;
    /** The certificate number. Sent as `tax_exempt_ref`. */
    taxExemptRef: string;
    /** When the exemption lapses. Sent as `tax_exempt_expires`. */
    taxExemptExpires: string;
  };
  /**
   * **THE MESSAGES THE CLERK TOOK OFF THE LIST — the `x` on
   * `step5-review.png`'s Messages table.**
   *
   * ⚠ **THE REMOVALS ARE STORED, NEVER THE THREE DEFAULTS**, for the reason
   * `removedWorkOrderTemplateIds` stores only subtractions: the three
   * occasions are the PO's ruling and the server's `OCCASIONS` tuple, so a
   * copy of them here would be a second opinion about a ruling.
   *
   * ⚠ **IT REACHES THE SERVER AS `messages.send`, AND THE DOOR HAS BEEN OPEN
   * THE WHOLE TIME.** `connection_messages.queue_on_commit` takes
   * `{send, templates}` and `commit_connection` passes `data["messages"]`
   * straight into it; the wizard sent nothing. Hard-won law 2.
   */
  messagesOff: string[];
  /**
   * **THE TEMPLATE A CLERK PICKED PER MESSAGE — `+ Add template`.**
   *
   * Keyed by the OCCASION's code, valued by the template CODE the picker
   * offered. Sent as `messages.templates`, which `_fire_one` reads as
   * `override_template`. An absent key means *use the published default*.
   */
  messageTemplates: Record<string, string>;
  /**
   * Step 3 — **OCCUPANCY PER UNIT**, keyed by unit label (PO 2026-09-16:
   * *"please provide default values to Table · Unit · Kind, Table ·
   * Occupancy"*).
   *
   * ⚠ **AN ABSENT KEY IS THE DEFAULT, NOT AN EMPTY ANSWER.** Only a unit the
   * clerk has actually moved is stored, so a build with six units and one
   * tenant moving in holds ONE entry rather than six. `occupancyOfUnit()` is
   * the only reader and it falls back to `OCCUPANCY_DEFAULT`
   * (`vacant_service_off`, `BR-MET-116`).
   *
   * ⚠ **THIS IS AN INSTRUCTION TO THE COMMIT, NOT A COLUMN TO WRITE.**
   * `units` has no occupancy column and that is deliberate — `BR-MET-036`,
   * and `models.py` says so about itself: *"units.occupancy/status
   * deliberately absent"*. What this decides is which units get an account
   * opened, and nothing else.
   */
  unitOccupancy: Record<string, OccupancyChoice>;
  /**
   * ⊕ **`CR-164-BRC10` item 15 — EACH DWELLING's UNIT TYPE, by label**, from
   * the utility's own `unit_types` list. Set for all at once by step 3's
   * Common selection (*Apply to all*) and per unit on its row. The server has
   * stored `units[].unit_type` since `CR-162-BRC10` and nothing sent it.
   * Optional because a parked draft predates it.
   */
  unitTypes?: Record<string, string>;
  /** The Common selection's own unit type, before *Apply to all*. */
  commonUnitType?: string;
  /**
   * Step 4 — the grid's per-row DEVIATIONS, keyed by `unitServiceKey()`.
   *
   * ⚠ **ONLY WHAT THE CLERK CHANGED IS STORED, FOR THE SAME REASON
   * `removedWorkOrderTemplateIds` stores only subtractions.** Every row of the
   * grid is defaulted — the service is inherited from the premise, the asset
   * type and size come from the catalogues, the install date is the target
   * activation — so a copy of all seven values per row would be a second
   * answer that goes stale the moment step 2's address or step 4's
   * availability changes. An absent cell means *"still the default"*, which
   * re-derives itself.
   */
  unitServiceGrid: Record<string, UnitServiceCell>;
  /**
   * CR-070 wave E — the proposed work orders the clerk has REMOVED, by
   * template id.
   *
   * ⚠ **THE REMOVALS ARE STORED, NOT THE PROPOSALS.** The proposal is a READ
   * (`GET /connections/proposed-work-orders`) and it changes as step 4 changes;
   * keeping a copy in the draft would be a second answer to *which jobs does
   * this build need* that goes stale the moment a service is ticked. So the
   * draft holds only the person's own subtractions, and the list is the read
   * minus them.
   */
  removedWorkOrderTemplateIds: string[];
  /**
   * `DEF-CUS-5482` — the work orders the clerk has ADDED, whole.
   *
   * PO 2026-09-16, verbatim: *"now on this step we should show work order
   * already selected from allow user to add few more work order"*. Until this
   * the list was remove-only.
   *
   * ⚠ **THE WHOLE ROW IS STORED WHERE `removedWorkOrderTemplateIds` STORES AN
   * ID, AND THE ASYMMETRY IS THE POINT.** A removal is a subtraction from a
   * read that will be re-run, so an id suffices. An ADDITION is not in that
   * read at all — it came from the template CATALOGUE, not from the services
   * chosen — so nothing would put the name or the version back. A parked draft
   * resumed in a browser that has not run the templates query would show a line
   * with no name and stamp `template_version` from nothing (`BR-WRK-008`,
   * *copy, never link*, needs the version to name which copy).
   */
  addedWorkOrders: ProposedWorkOrder[];
  /**
   * Step 6 · *Who is billed* — `02 Accounts Menu Blueprint.pdf` p090.
   *
   * One of `owner_account` · `each_unit_first_bill` · `connection`, travelling
   * to the commit as `quote_payer`. The last two are REFUSED by
   * `metering.connections._quote_payer` with their real reasons, and the screen
   * refuses them too rather than sending a choice the server will decline.
   */
  quotePayer: QuotePayer;
  /**
   * Step 6 · payment terms, in days, travelling as `quote_due_days`.
   *
   * ⚠ **THIS FIELD IS WHY NO BUILD HAS EVER RAISED A CHARGE** (`DEF-CUS-5485`).
   * `_post_connection_quote` returns the `quote_payment_terms_not_captured`
   * absence and posts NOTHING when it is missing, and no caller in the product
   * sent it — `fee_bill.raise_quote_bill`'s own docstring says so: *"no caller
   * in the product sends that field - the wizard does not collect it. Every
   * real commit therefore takes the payment terms not captured branch"*.
   *
   * ⚠ **EMPTY IS LAWFUL AND IS NOT A ZERO.** `BR-BIL-024` is *"due date = bill
   * date + the cycle's due-days"* and a build's bill has no cycle; the PO ruled
   * on 2026-08-23 that the terms are captured by the clerk and never guessed.
   * A default here would start a late-fee clock on a real customer's invoice
   * from a number no signed document contains.
   */
  quoteDueDays: string;
  /** Step 6 · *Posting date* — *"The day this payment counts from."* An EVENT
   *  date and never a wall clock (`BR-TEN-043`, gate `G6`); empty means the
   *  server falls back to the day the clerk pressed commit, which is its own
   *  documented behaviour and not a guess this screen makes. */
  quotePostingDate: string;
  /**
   * Step 6 · **THE LINES THIS BUILD IS CHARGING — `BR-MET-1178`, PO ruling
   * 2026-09-21.**
   *
   * Verbatim: *"…this request is new work and recognized seperately from
   * applcaition and hence we should not make it dependent on applciation #"*.
   * A build a developer started has no application to take a quote from, so it
   * prices ITSELF.
   *
   * ⚠ **A LINE IS A CODE AND A BASIS. THE QUANTITY IS NOT STORED HERE.** It is
   * COUNTED from step 4 at the moment the commit is assembled (`quoteCounts`),
   * which is the drawing's own red sentence on p094: *"Every quantity is
   * counted from the services grid, not typed. … change a tick on step 4 and
   * these move with it."* Storing a number would freeze a count that step 4 is
   * still free to change, and the two would disagree with nothing able to see
   * it.
   *
   * ⚠ **AND THERE IS NO AMOUNT ANYWHERE IN THIS TYPE.** Billing reads the
   * price off the tenant's own charge row and multiplies (`BR-BIL-007`,
   * `BR-BIL-020`); `CLAUDE.md` hard rule 2 rounds once, on the server. A
   * figure computed here would be the second rounding path.
   */
  quoteLines: BuildChargeLine[];
  /**
   * Step 6 · *Taking the money now* — **is a payment being taken at the
   * counter with this build?** (`BR-MET-1187`, `DEF-CUS-7611`.)
   *
   * ⚠ **`"none"` IS THE DEFAULT AND IT IS THE ORDINARY ANSWER.**
   * `_payment_taken_at_the_counter`'s own docstring: *"`None` is the ordinary
   * answer and it is the drawn default — No payment now. A build is committed
   * with an invoice and no receipt, and the developer pays it like any other
   * bill."* Nothing below travels when this is `"none"`.
   *
   * ⚠ **TWO CHOICES WHERE THE DRAWING DRAWS THREE, AND THE MISSING ONE IS
   * DELIBERATE — decision log 2026-09-28.** p096 draws *Yes — a deposit
   * against the quote · No, invoice it on activation · No, the developer pays
   * per unit*. The third is the PAYER restated, and the payer is the radio
   * group six inches above it, whose `each_unit_first_bill` the server
   * REFUSES by name. A control offering an answer the product declines is a
   * live control that lies (hard-won law 2's mirror), so the two no-payment
   * options are one: *No payment now*.
   */
  takePayment: TakePayment;
  /**
   * Step 6 · *Method* — **the TENANT's own method CODE, never a drawn label.**
   *
   * ⚠ **IT COMES FROM `GET /payments` `methods[]` AND NEVER FROM A LIST TYPED
   * HERE** (`BR-PAY-026`, and the `SignupWizard` lesson in CLAUDE.md: a
   * hand-typed catalogue fails SILENTLY when the catalogue moves). The
   * drawing's *Cheque* is the code `check` and its *Bank transfer* is `ach` or
   * `wire`; a clerk who typed `cheque` at a utility that spells it `check`
   * used to read *"Something went wrong on our side"* after thirty-three acts.
   */
  paymentMethod: string;
  /** Step 6 · *Reference* — the cheque or confirmation number, as typed. */
  paymentReference: string;
  /**
   * **Step 4 · *Payment date* — WHEN THE MONEY WAS TAKEN, and it is a SECOND
   * FACT rather than a second copy of the posting date** (`CR-150-BRC09`
   * task 11; `step4-charges.png` draws both, with different labels).
   *
   * ⚠ **BLANK IS THE ORDINARY ANSWER AND MEANS *the same day the charge
   * posts*.** `paymentTakenOf` then sends the posting date, which is exactly
   * what this wizard sent before the box existed — *"they are one event"*
   * (`BR-TEN-043`, `G6`) — so nothing already committed changes meaning.
   *
   * ⚠ **AN EVENT DATE, NEVER A CLOCK.** Not prefilled: a payment taken on
   * Friday and keyed on Monday is a Friday payment.
   */
  paymentDate: string;
  /** Step 6 · *Amount taken* — the clerk's own string, **never a figure this
   *  file computes, sums or rounds** (hard rule 2; `DEF-088`, `DEF-127`). A
   *  part payment is lawful and the rest stays outstanding. */
  paymentAmount: string;
  // ⛔ NO *Clearing date* (DEF-CUS-10324, CR-186-BRC10, PO 2026-10-21). Every
  // payment is `posted` at entry — applied to the build's bill and journalled
  // at once — and becomes `cleared` only when its deposit batch is reconciled
  // with the bank. No screen sets a clearing date, so this step asks none.
  /**
   * Step 1 · **the owner's papers, held until the commit — PO 2026-09-21.**
   * See `DraftDocument` for why a file cannot travel with the commit and where
   * these are filed instead.
   */
  ownerDocuments: DraftDocument[];
  /**
   * ⊕ **`DEF-CUS-9828` (N2) — THE REQUEST'S OWN DOCUMENTS, LINKED NOT COPIED.**
   * Listed on step 1 as already brought in; the server files them on the
   * owner's account at Create, by reference (`carry_request_documents`).
   * Nothing here is uploaded or sent. `requestId` is where they open from
   * (the request's own content route). Optional: a parked draft predates both.
   */
  requestId?: string | null;
  requestDocuments?: RequestPrefillDocument[];
  /**
   * ⊕ **lane CF-1 (2026-10-18) — THE SHARED CO-OWNER CARDS** (drawing set
   * `customer-forms-2026-10-18`, image 06: *Co-owners · Has co-owners*, one
   * folding card per person, *+ Add co-owner*). They replace the single
   * `coApplicant` panel; a parked draft that holds only `coApplicant` reads
   * as one card (`draftCoOwners`). Sent as `co_owners`, the word move-in uses.
   */
  coOwnersOn?: boolean;
  coOwners?: CoOwnerDraft[];
  /**
   * ⊕ lane CF-1 — the rows of Move-in's documents table. A row's `card_id`
   * names the `ownerDocuments` entry holding its file (a LOCAL key, B14 rule
   * 31); only files a row still names are filed after the commit.
   */
  ownerDocDrafts?: MoveInDocDraft[];
  /** ⊕ lane CF-1 — the charges step's *Set preferences* tick (Move-in's
   *  Preferences panel). Absent: ticked when an answer is already held. */
  prefsOn?: boolean;
  /**
   * ⊕ **lane CF-1 — Move-in's TAX and DISCOUNTS panels on the charges step**
   * (drawing set `customer-forms-2026-10-18`, image 02; coordinator, PO
   * *"this is correct"*). Move-in's own form state for the two panels, so
   * `TaxSection` and `DiscountsSection` mount unchanged; sent as Move-in's
   * commit sends them (`billingPayload` → `tax_exemption`, `discount_claims`).
   * Absent on a draft from before, which keeps the old blanket tax boxes.
   */
  moveInExtras?: NewConnectMoveInExtras;
}

/** The slice of Move-in's Billing-step state the two panels read. */
export type NewConnectMoveInExtras = Pick<StepBillingOwn, "discountsOn" | "discounts" | "taxOn" | "tax">;

/** Move-in's whole Billing-step state around New Connect's slice — no fees,
 *  no payment, no preferences (those are New Connect's own). */
export function moveInExtrasOwn(draft: NewConnectDraft): StepBillingOwn {
  return { ...emptyStepBillingOwn(), prefsOn: false, ...(draft.moveInExtras ?? {}) };
}

/** What holds the charges step in the two panels — Move-in's own rules. */
export function moveInExtrasProblems(draft: NewConnectDraft): BillingProblem[] {
  if (draft.moveInExtras === undefined) return [];
  return billingProblems(moveInExtrasOwn(draft)).filter(
    (problem) => problem.startsWith("tax_") || problem === "discount_row",
  );
}

/** The catalogue key for one of those problems (Move-in's own words). */
export const MOVE_IN_EXTRAS_PROBLEM_KEY: Readonly<Record<string, string>> = {
  tax_category: "customers.moveIn.tax.categoryRequired",
  tax_ref: "customers.moveIn.tax.refRequired",
  tax_expires: "customers.moveIn.tax.expiresRequired",
  tax_file: "customers.moveIn.tax.fileRequired",
  discount_row: "customers.moveIn.discounts.required",
};

/**
 * ⊕ lane CF-1 — the owner block's exemption and claims, exactly as Move-in's
 * commit carries them (`billingPayload`, with no fee rows): the blanket
 * `tax_exempt` is sent false and the certificate block alone carries an
 * exemption (`DEF-CUS-9724`). A draft from before the panels sends nothing.
 */
export function ownerMoveInExtras(draft: NewConnectDraft): Record<string, unknown> {
  if (draft.moveInExtras === undefined) return {};
  const out = billingPayload(moveInExtrasOwn(draft));
  return { ...out, tax_exempt: false, tax_exempt_ref: null, tax_exempt_expires: null };
}

/** The three debtors p090 draws. Two of them are drawn refused or are refused
 *  by the server, and both refusals are real — see `NewConnectChargesStep`. */
export type QuotePayer = "owner_account" | "each_unit_first_bill" | "connection";

/** *Taking the money now* — `"none"` is the default and sends no payment key
 *  at all; `"deposit"` is the drawn *Yes — a deposit against the quote*. See
 *  `NewConnectDraft.takePayment` for why there are two and not the drawn
 *  three. */
export type TakePayment = "none" | "deposit";

/**
 * **THE THREE BASES A BUILD'S CHARGE IS COUNTED ON — p094's own BASIS column.**
 *
 * ⚠⚠ **THE SPELLING IS BILLING'S, WITH SPACES, AND IT IS THE WHOLE REASON THIS
 * IS A CONSTANT.** `apps/billing/fee_bill.BASIS_UNITS` keys on `"per unit"` ·
 * `"per meter"` · `"per premise"`, and its own docstring says why it is a MAP
 * rather than a `.removeprefix("per ")`: *"a typo becomes a unit nobody defined
 * and it lands on an immutable document (hard rule 4)"*. An underscored
 * spelling is refused two modules away with a message no clerk can act on.
 * **A new basis is a ruling, not a string.**
 */
export const BUILD_CHARGE_BASES = ["per unit", "per meter", "per premise"] as const;
export type BuildChargeBasis = (typeof BUILD_CHARGE_BASES)[number];

/** One line of the build's own quote: a charge code the clerk picked out of
 *  the tenant's catalogue, and what it is counted on. */
export interface BuildChargeLine {
  chargeCode: string;
  basis: BuildChargeBasis;
}

/**
 * **ONE DOCUMENT THE CLERK TOOK OFF THE OWNER AT STEP 1 — PO 2026-09-21.**
 *
 * Verbatim: *"Step 1 — Owner & scope (p92) + you ahve to take documents - rest
 * is all good"*.
 *
 * ⚠ **IT HOLDS A BROWSER `File`, SO IT NEVER CROSSES THE COMMIT PAYLOAD AND IT
 * NEVER GOES IN A PARKED DRAFT.** `BR-MET-112` is *nothing is written until
 * step 8*, and a file is not JSON: it is uploaded AFTER the commit, against the
 * owner's account, through the door that already exists
 * (`POST /accounts/{id}/documents`). The decision log of 2026-09-21 rules
 * exactly that — *"nothing is owned by anybody else, so the owner's documents
 * may be captured at step 1 and filed against what the commit creates"* — and
 * says why the transfer wizard's own question (`OQ-CUS-12522`, where a BUYER's
 * papers go while the account is still the SELLER's) does not apply here.
 *
 * ⚠ **`id` IS A LOCAL KEY AND IS NEVER A DATABASE ID** (B14 rule 31). The row
 * does not exist on any server until the commit has run, and the screen never
 * prints this value.
 */
export interface DraftDocument {
  id: string;
  docType: string;
  name: string;
  whatItProves: string;
  /**
   * **THE DRAWN `DOCUMENT NUMBER` COLUMN, CARRIED AT LAST.**
   *
   * ⚠ **THE FORM HAS ASKED FOR THIS SINCE 2026-09-22 AND THE DRAFT DROPPED
   * IT ON THE FLOOR.** `DocumentCaptureForm` — the shared component this step
   * mounts — grew the box on the service-request ruling, and
   * `draftDocumentRows` had to serve `document_number: null` into a column
   * the drawing draws with a value in it, because there was nowhere to keep
   * what the clerk typed. `step1-customer.png` draws the column `NEW` with
   * `•••• 2291` in it, so the missing half is built here.
   *
   * ⚠ **THE SCREEN NEVER SHOWS MORE THAN THE LAST FOUR** — the form's own
   * placeholder says *Last 4 show*, and the shared table masks it.
   *
   * ⚠ **OPTIONAL, AND THAT IS A DELIBERATE NARROWING RATHER THAN A SHRUG.**
   * `DraftDocument` is shared with the TRANSFER wizard, which builds rows of
   * its own and asks for no number; making this required would have edited
   * four files in two other features to add `documentNumber: ""` — a mass
   * shared-file rewrite for no user-visible change, which is what law 11
   * exists to prevent. **It is NOT an optional prop nothing passes** (hard-won
   * law 2): New Connect's step 1 passes it on every row it creates, and
   * `newConnectSteps12Redesign.dom.test.tsx` reads the rendered cell.
   */
  documentNumber?: string;
  required: boolean;
  file: File;
  /**
   * ⊕ **`DEF-CUS-9824` (N4, PO 2026-10-06) — WHO ATTACHED IT AND WHEN, while
   * the build is still a draft.** The clerk at the desk IS the uploader; the
   * table read a dash because nothing was kept. An ISO instant, rendered by the
   * shared table in the utility's zone and date format. Optional because the
   * transfer wizard builds rows of its own and a parked row predates it.
   */
  attachedAt?: string;
  attachedBy?: string;
}

export function emptyDraft(): NewConnectDraft {
  return {
    // `DEF-CUS-6109` — set only when the wizard was opened on a build an
    // approval already raised. Nothing in the eight steps branches on it; only
    // the commit does.
    connectionId: null,
    // `BR-SHL-048 (d)` — the number of that same build, for the clerk to read.
    connectionNo: null,
    requestNo: null,
    owner: {
      name: "",
      kind: "",
      // ⚠ NOT DEFAULTED TO `residential`. It is required and it decides how
      // the customer is billed; a default would answer it invisibly for a
      // warehouse. The drawing shows a value because every drawn figure is an
      // illustration (B14 rule 37), never a fact to build to.
      category: "",
      subCategory: "",
      dateOfBirth: "",
      email: "",
      phone: "",
      externalRef: "",
      // ⚠ NOT DEFAULTED TO `person`. An unstated kind is a REAL answer that
      // mints no customer number and says so; pre-selecting one would make
      // that answer invisible and would pick for a sole trader.
      partyKind: "",
      ssn: "",
      drivingLicence: "",
      taxId: "",
      matchedCustomerId: null,
      matchedCustomerNo: null,
    },
    scope: "new_premise",
    targetActivation: "",
    // §8.3's three modes with the first DISABLED; `our_crew` is the drawn
    // selection and the only one that needs no further build.
    mode: "our_crew",
    premise: {
      premisesId: "",
      name: "",
      address: "",
      city: "",
      state: "",
      postalCode: "",
      premiseType: "",
      parcelRef: "",
      readRoute: "",
      unit: "",
      // ⚠ EMPTY IS *NOBODY HAS GIVEN A POINT*, WHICH IS NOT `0, 0` — a real
      // place in the Gulf of Guinea. All three are optional and a map that
      // has nothing to show shows nothing.
      lat: "",
      lng: "",
      locationVerified: false,
    },
    // The drawn state of the Co-applicant panel: one button, no fields.
    coApplicant: null,
    // ⚠ TICKED, WHICH IS THE DRAWING'S OWN STATE — the bill goes to the
    // building unless somebody says otherwise, and that is the common case.
    mailing: {
      sameAsService: true,
      address: "",
      unit: "",
      city: "",
      state: "",
      postalCode: "",
    },
    // ⚠ `language` EMPTY IS *THE UTILITY'S OWN*, NOT *ENGLISH*.
    // `PortalLanguageField` fills it from `GET /shell/display`, so a Spanish
    // utility does not have every new customer defaulted into English.
    communication: { language: "", paperlessBill: false, smsReminders: false },
    accountCustomData: {},
    // ⚠ THE COMMON AREA IS TICKED BY DEFAULT — *"It always exists and nobody
    // remembers to add it"* (step 3's own justification).
    // ⛔ **`BR-MET-1179` — NOT PRE-SELECTED, AND THIS ONE WORD IS THE RULE.**
    // PO 2026-09-21: *"build this rule - no common area for single family or
    // related classes"*, corrected the same day to *optional, never mandatory*
    // on EVERY type. It read `true`, copied from B18's own argument —
    // *"Corridors, car park, irrigation. It always exists and nobody remembers
    // to add it"* — and that default is what the acceptance walk caught: a
    // clerk building a house has no unit numbers to type, left the boxes empty,
    // carried on, and committed **one common area and no dwelling at all**.
    // B18's drawing already rendered this box UNTICKED; the prose beside it was
    // read as the authority and the drawing as an inconsistency. It was not.
    pattern: { prefix: "", from: "", to: "", includeCommonArea: false },
    premiseServices: [],
    apartmentServices: [],
    commonAreaServices: [],
    planApartments: "",
    planCommonArea: "",
    occupancy: OCCUPANCY_DEFAULT,
    // ⚠ **BOTH FLAGS START FALSE AND BOTH BOXES START EMPTY.** Not electing is
    // the answer every account in the product already carries, and a
    // pre-ticked tax exemption is a tax decision this wizard would be making
    // for a utility.
    billing: { autopay: false, taxExempt: false, taxExemptRef: "", taxExemptExpires: "" },
    // ⚠ **EMPTY MEANS ALL THREE ARE ON, WHICH IS THE PO's RULING.**
    messagesOff: [],
    messageTemplates: {},
    // ⚠ BOTH START EMPTY AND THAT IS THE FILLED-IN STATE, NOT A BLANK ONE.
    // An absent entry means the row is still on its default, which is what
    // *"the table arrives filled in"* actually requires: a clerk who changes
    // nothing still commits six defaulted units.
    unitOccupancy: {},
    unitServiceGrid: {},
    removedWorkOrderTemplateIds: [],
    addedWorkOrders: [],
    quotePayer: "owner_account",
    quoteDueDays: "",
    quotePostingDate: "",
    quoteLines: [],
    // ⚠ **NO PAYMENT, AND EVERY BOX EMPTY — `BR-MET-1187`.** *No payment now*
    // is the ordinary answer.
    takePayment: "none",
    paymentMethod: "",
    paymentReference: "",
    paymentAmount: "",
    // Blank means *the day the charge posts*; see the field's own note.
    paymentDate: "",
    ownerDocuments: [],
  };
}

/**
 * `owner.party_kind` and `owner.identity` as the commit sends them — **the two
 * keys the account door reads, assembled in ONE place** (`BR-CUS-1022`,
 * `BR-CUS-1023`, decision log 2026-09-16 §2 and §3).
 *
 * ⚠ **THE IDENTITY TRAVELS ONLY WHEN A PARTY KIND IS STATED** — `BR-CUS-1022`,
 * and it is not caution: evidence presented against an unstated kind *cannot be
 * assessed at all*, so sending it regardless turns one refusal that names the
 * missing dropdown into a field error about the evidence. One missing thing,
 * one sentence.
 *
 * ⚠ **A PERSON'S EVIDENCE AND A COMPANY'S ARE DISJOINT, AND THE WRONG ONE IS
 * REFUSED BY NAME RATHER THAN IGNORED.** The server's per-kind lists accept
 * `{date_of_birth, ssn, driving_licence, phone}` for a person and
 * `{tax_id, phone}` for a company, so a Tax ID sent under `person` fails the
 * whole payload. The branch below is that rule, not tidiness.
 *
 * ⚠ **THE PHONE IS AN IDENTITY CLAIM FOR A PERSON ONLY** — the decision log's
 * own worked pair (2026-09-16 §2): *Marisol Ibarra*, landlord, phone
 * `555-0182` and nothing else, opens a master account; *Brazos Bend
 * Developments LLC* on the SAME phone and no Tax ID is still refused, because a
 * phone does not mint a number for a company. It is sent for both kinds and the
 * DOOR applies that rule — a second copy of it here is a second thing to drift.
 */
export function ownerIdentityPayload(owner: OwnerForm): Record<string, unknown> {
  const kind = owner.partyKind.trim();
  if (kind === "") return {};
  const identity: Record<string, string> = {};
  if (kind === "company") {
    if (owner.taxId.trim() !== "") identity.tax_id = owner.taxId.trim();
  } else {
    // ⊕ `DEF-CUS-9256` — the date of birth step 1 asks for travels too. It is
    // on the server's person list and is what makes a later owner with the
    // same name a POSSIBLE match; it was typed, checked (18+, not future) and
    // then dropped here, so every committed owner's record read no birth date.
    if (owner.dateOfBirth.trim() !== "") identity.date_of_birth = owner.dateOfBirth.trim();
    if (owner.ssn.trim() !== "") identity.ssn = owner.ssn.trim();
    if (owner.drivingLicence.trim() !== "")
      identity.driving_licence = owner.drivingLicence.trim();
  }
  if (owner.phone.trim() !== "") identity.phone = owner.phone.trim();
  return Object.keys(identity).length === 0
    ? { party_kind: kind }
    : { party_kind: kind, identity };
}

/**
 * The occupancy of ONE unit — the per-unit answer, or the build's own.
 *
 * ⚠ **THE FALLBACK IS `draft.occupancy` AND NOT THE CONSTANT, WHICH IS WHAT
 * MAKES THE REVIEW STEP'S RADIO STILL MEAN SOMETHING.** The ruling says the
 * whole-build choice *"becomes the thing that SETS them all rather than a
 * separate answer"* — so a clerk who picks *landlord-billed* on the last step
 * moves every unit they have not already moved by hand, and no second answer
 * exists to disagree with the first. `draft.occupancy` is itself
 * `OCCUPANCY_DEFAULT`, so an untouched build is `vacant_service_off` on every
 * row, which is `BR-MET-116` (PO 2026-08-25, *"unit will be all vacant right
 * now"*) and is the reason the commit may open the owner's master account at
 * all.
 *
 * ⚠ **AN EXPLICIT PER-UNIT CHOICE OUTRANKS A LATER BULK ONE, DELIBERATELY.**
 * Unit 4 having a tenant moving in is the case the whole column exists for;
 * silently resetting it when somebody touches the review radio would lose the
 * one fact the clerk went out of their way to record. The column shows it, so
 * it is never hidden.
 *
 * ⚠ **THE COMMON AREA HAS NONE AND `null` IS THAT FACT.** The blueprint draws
 * `—` in its cell (p088) because a corridor is not vacant or occupied; it is
 * not a dwelling at all. Returning a choice for it would put a common area
 * into the set of things that can have a tenant.
 */
export function occupancyOfUnit(
  draft: NewConnectDraft,
  unit: DraftUnit,
): OccupancyChoice | null {
  if (unit.isCommonArea) {
    return null;
  }
  // `DEF-CUS-9050` — a parked build may hold a choice retired on 2026-10-02.
  return liveOccupancy(String(draft.unitOccupancy[unit.label] ?? draft.occupancy));
}

/** Every unit the draft would create, and what each takes. Derived in ONE place
 *  so step 4's breach check, step 5's coverage warning and step 8's manifest
 *  cannot disagree about the same build. */
export function draftUnits(draft: NewConnectDraft): DraftUnit[] {
  return expandUnitPattern(draft.pattern);
}

/**
 * What each unit takes — **INHERITED FROM THE PREMISE, MINUS WHAT THE CLERK
 * DROPPED** (PO 2026-09-16: *"units inherit all utility services from premises
 * - hence we have to show all utility services"*).
 *
 * ⚠ **`apartmentServices` AND `commonAreaServices` NO LONGER DECIDE THIS, AND
 * THAT IS THE WHOLE RULING.** They were ONE set for every dwelling and one for
 * the common area, so *"unit 4 does not take gas"* had no shape at all. The
 * per-unit answer is step 4's grid, which stores only DEVIATIONS — so a build
 * nobody has edited inherits everything and holds an empty map.
 *
 * ⚠ **THE UNION WITH AN EXPLICIT `taken: true` IS DELIBERATE AND IT KEEPS THE
 * AVAILABILITY REFUSAL ALIVE.** Derived from `premiseServices` alone, a unit
 * could never name a service the street does not have, and
 * `availabilityBreaches` would become a check structurally incapable of firing
 * — CLAUDE.md law 7's second shape — with a refusal strip no clerk could ever
 * see. A clerk who ticks gas on the grid and then unticks gas in the
 * availability list above is in exactly that state, and the refusal is what
 * tells them.
 */
export function draftUnitServices(draft: NewConnectDraft): Record<string, string[]> {
  const map: Record<string, string[]> = {};
  for (const unit of draftUnits(draft)) {
    const taken: string[] = [];
    const seen = new Set<string>();
    for (const service of draft.premiseServices) {
      seen.add(service);
      if (draft.unitServiceGrid[unitServiceKey(unit.label, service)]?.taken !== false) {
        taken.push(service);
      }
    }
    for (const [key, cell] of Object.entries(draft.unitServiceGrid)) {
      if (cell.taken !== true) {
        continue;
      }
      const cut = key.indexOf("");
      if (cut < 0 || key.slice(0, cut) !== unit.label) {
        continue;
      }
      const service = key.slice(cut + 1);
      if (!seen.has(service)) {
        seen.add(service);
        taken.push(service);
      }
    }
    map[unit.label] = taken;
  }
  return map;
}

/** `BR-CUS-1114` — the fewest units a premises must hold for a master account.
 *  The server's `customers.services.MASTER_ACCOUNT_MIN_UNITS`; the server
 *  refuses below it whatever this sends. */
export const MASTER_ACCOUNT_MIN_UNITS = 2;

/**
 * `BR-CUS-1114` (PO 2026-10-02: *"single family hime, single unit, we should
 * not do master account"*) — does this build open the owner's MASTER account?
 * Only where an owner is named AND the address will hold two or more
 * DWELLINGS (a common area is not a home — the server's
 * `dwelling_units_at_premises`). A new address counts the dwellings this build
 * makes; dwellings added to an address on file join the ones already there, so
 * one more makes at least two. A
 * single-unit build opens none: its applicant gets a REGULAR account on the
 * one unit (Move-in), which holds the services.
 */
export function buildOpensOwnerMaster(
  draft: NewConnectDraft,
  units: readonly DraftUnit[] = draftUnits(draft),
): boolean {
  if (draft.owner.name.trim() === "") {
    return false;
  }
  // `CR-162-BRC10` (Q1, PO 2026-10-02) — THE PREMISES TYPE DECIDES, not how
  // many units were typed: an apartment complex gets its owner a master
  // account with one unit entered, a single-family home never does. The
  // answer is the utility's own setting on the type (`account_kind`); only a
  // type nobody has answered falls back to counting homes.
  if (draft.premise.accountKind === "master") {
    return true;
  }
  if (draft.premise.accountKind === "regular") {
    return false;
  }
  const homes = units.filter((unit) => !unit.isCommonArea).length;
  const atTheAddress = draft.scope === "new_units" && homes > 0 ? homes + 1 : homes;
  return atTheAddress >= MASTER_ACCOUNT_MIN_UNITS;
}

/**
 * ⊕ **`DEF-CUS-9228` — DOES THIS BUILD OPEN THE OWNER'S OWN *REGULAR* ACCOUNT?**
 *
 * PO ruling 2026-10-02 (decision log *"SEVEN PO ANSWERS IN ONE MESSAGE"*, item
 * 1): *"A. The owner asked for the work, so the owner pays."* A single-family
 * home has no master account (`BR-CUS-1114`, unchanged), so at Create its
 * owner gets a regular account on the one home, and the build's charges are
 * billed to it. True exactly where the server takes that path
 * (`connections._single_family_home`): an owner named, the premises TYPE says
 * *Regular account*, a NEW address, and one home. Anything else opens nothing
 * here — two homes on a single-family type are refused by the server, and a
 * home added at an address on file is not this wizard's to count.
 */
export function buildOpensOwnerRegular(
  draft: NewConnectDraft,
  units: readonly DraftUnit[] = draftUnits(draft),
): boolean {
  if (draft.owner.name.trim() === "" || draft.premise.accountKind !== "regular") {
    return false;
  }
  if (draft.premise.premisesId !== "") {
    return false;
  }
  return units.filter((unit) => !unit.isCommonArea).length === 1;
}

/**
 * ⊕ **`CR-164-BRC10` wave 4 — DOES THIS OWNER'S ACCOUNT HOLD THE HOME?** The
 * server's `connections.OWNER_TYPES_THAT_LIVE_THERE`, mirrored. Every type but
 * an owner-occupier opens the owner's account BILLING ONLY (the same under the
 * PO's answers B and C). An owner-occupier keeps today's behaviour and holds
 * the home while `OQ-CUS-12785` is OPEN (PO 2026-10-03: *"i dont know yet"*);
 * under B this list becomes empty.
 */
export const OWNER_TYPES_THAT_LIVE_THERE: readonly string[] = ["owner_occupier", "occupier"];

export function ownerLivesThere(ownerType: string | null | undefined): boolean {
  return OWNER_TYPES_THAT_LIVE_THERE.includes((ownerType ?? "").trim().toLowerCase());
}

/** ⊕ `DEF-CUS-9228` — does Create open ANY owner's account (master or the
 *  single-family owner's own)? It is the commit's `create_owner_account`, the
 *  customer step 5 counts and the payer step 4 offers. */
export function buildOpensOwnerAccount(
  draft: NewConnectDraft,
  units: readonly DraftUnit[] = draftUnits(draft),
): boolean {
  return buildOpensOwnerMaster(draft, units) || buildOpensOwnerRegular(draft, units);
}

/** ⊕ `DEF-CUS-9228` — a charge on step 4 with nobody to bill it to. Since the
 *  PO's ruling this is only a build that opens no owner's account at all. */
export function noOneToBill(draft: NewConnectDraft): boolean {
  return draft.quoteLines.length > 0 && !buildOpensOwnerAccount(draft);
}

/**
 * ⊕ **`DEF-CUS-10047` — WHICH OF THE OWNER'S TWO ACCOUNTS THIS BUILD IS ABOUT.**
 *
 * The one Create opens, where it opens one (`buildOpensOwnerRegular` /
 * `buildOpensOwnerMaster`). Where it opens NONE, the one the premises TYPE
 * would open (`accountKind`), so step 4's *Who is billed* names the account
 * the clerk is short of rather than always saying *Master account*: the PO's
 * SR-26-0027 read *"Master account · John doe"* over a single-family home.
 */
export function ownerAccountKind(
  draft: NewConnectDraft,
  units: readonly DraftUnit[] = draftUnits(draft),
): "master" | "regular" {
  if (buildOpensOwnerRegular(draft, units)) return "regular";
  if (buildOpensOwnerMaster(draft, units)) return "master";
  return draft.premise.accountKind === "regular" ? "regular" : "master";
}

/**
 * ⊕ **`DEF-CUS-10048` — WHY A CHARGE HAS NOBODY TO BILL, IN THE TERMS OF THE
 * THING THAT IS ACTUALLY MISSING.** The catalogue key of step 4's refusal, or
 * `null` when there is no charge or Create opens the owner's account.
 *
 * PO, 2026-10-11: accounts and payment are all created at submission, so the
 * refusal must never fire *for want of an account the submission creates*. It
 * fires exactly where the commit's `create_owner_account` would be false —
 * the server's own case, and then the charge truly has nobody to be billed
 * to. What was wrong was the SENTENCE: *"No master account to bill"* for every
 * cause, including a single-family home (which never takes a master account)
 * and a draft with no owner named. Each cause now names its own fix:
 *
 *   * no owner name → step 1;
 *   * no premise type → step 2 (the type decides master or regular,
 *     `CR-162-BRC10` Q1);
 *   * a Regular type with other than one home → step 3 (`BR-CUS-1114`: a
 *     single-family home is one unit);
 *   * a Regular type at an address already on file → no regular account;
 *   * otherwise (a type the utility has not answered, fewer than two homes)
 *     → no master account, the counting rule that applies there.
 *
 * ⚠ The OWNER TYPE (step 1's *Choose an owner type*) is not on this list on
 * purpose: it decides whether the owner's account HOLDS the home
 * (`ownerLivesThere`), never whether one opens.
 */
export function noOneToBillReason(
  draft: NewConnectDraft,
  units: readonly DraftUnit[] = draftUnits(draft),
): string | null {
  if (draft.quoteLines.length === 0 || buildOpensOwnerAccount(draft, units)) return null;
  if (draft.owner.name.trim() === "") return "customers.newConnect.step6.nameOwnerToBill";
  const kind = draft.premise.accountKind ?? "";
  if (kind === "" && draft.premise.premiseType.trim() === "") {
    return "customers.newConnect.step6.typeToBill";
  }
  if (kind === "regular") {
    const homes = units.filter((unit) => !unit.isCommonArea).length;
    return homes !== 1
      ? "customers.newConnect.step6.oneHomeToBill"
      : "customers.newConnect.step6.noRegularToBill";
  }
  return "customers.newConnect.step6.noMasterToBill";
}

/** True where an owner is named but the build opens no owner's account — the
 *  review step says why. */
export function ownerMasterRefusedForSingleUnit(draft: NewConnectDraft): boolean {
  return draft.owner.name.trim() !== "" && !buildOpensOwnerAccount(draft);
}

/** The wizard's own preview of what the commit will make. It is the SAME shape
 *  the server answers with, so what a person is shown before pressing and what
 *  they are told after are one vocabulary. */
export function draftManifest(
  draft: NewConnectDraft,
  quoteDisplay: string | null,
): ManifestPreview {
  const units = draftUnits(draft);
  const services = draftUnitServices(draft);
  // ⚠ **A COMMON AREA IS COUNTED AS *WITHOUT* A PLAN AND THAT IS CORRECT, NOT A
  // BUG TO FIX (PO ruling 2026-09-16, `DEF-CUS-5496`).** `planCommonArea` is
  // asked by no screen and is always `""`, so a common area falls out of this
  // count — which is exactly what the commit now does too, since
  // `commitPlanOf` sends it no assignment at all. The two agree, which is the
  // whole promise of this function: what a clerk is shown before pressing and
  // what they are told after are one vocabulary.
  // **So a seven-unit build correctly reviews as SIX units with a plan.** Do
  // not "repair" this by making `planCommonArea` required again — that is the
  // defect above, and it refused every build with a common area.
  const withPlan = units.filter((unit) =>
    unit.isCommonArea ? draft.planCommonArea !== "" : draft.planApartments !== "",
  ).length;
  return manifestPreview({
    units,
    unitServices: services,
    unitsWithAPlan: withPlan,
    // `BR-CUS-1114` — a single-unit build opens no owner's master account;
    // ⊕ `DEF-CUS-9228` — a single-family home opens the owner's own one.
    ownerBecomesACustomer: buildOpensOwnerAccount(draft, units),
    quoteDisplay,
  });
}

/** What step 8 posts. Assembled from the draft in one place, so nothing the
 *  screen shows and the payload sends can drift apart. */
/**
 * **`DEF-CUS-6109` — THE DRAFT BUILD AN APPROVAL RAISED, POURED INTO THE
 * WIZARD'S OWN SHAPE.**
 *
 * PO ruling 2026-09-21, verbatim: *"then approve applciation may create a new
 * conenct request - as draft request - this request is new work and recognized
 * seperately from applcaition and hence we should not make it dependent on
 * applciation #"*. The build exists before step 1; this is what the clerk finds
 * already filled in when the wizard opens on it.
 *
 * ⚠ **EVERY FIELD HERE IS A STARTING POINT AND NONE OF THEM IS LOCKED.** The
 * PO's challenge that produced this defect was that the application already
 * holds the facts — *"we take details on customer when service request is
 * created - that mean you ahve both customer details and premises details"* —
 * and the answer to holding them is to OFFER them, not to decide with them. The
 * clerk overtypes anything, and the commit sends what is on screen.
 *
 * ⚠ **THE OWNER IS STILL REQUIRED AT STEP 1 AND THIS DOES NOT SATISFY IT.** An
 * applicant is who ASKED; an owner is who the property and the money belong to,
 * and the PO confirmed on 2026-09-21 that step 1 always asks. So the applicant
 * is offered as the owner's name and contact — which is right far more often
 * than not — and `ownerIdentityShortfall` still blocks the step until a party
 * kind and an identifier are there. Nothing here weakens a gate.
 *
 * ⚠ **THE UNIT PATTERN IS DELIBERATELY NOT PREFILLED**, although the request
 * carries `units_on_property`. That number is *how many units the applicant
 * says are on the property*; a pattern is PREFIX, FROM and TO, and turning six
 * into `1 … 6` would be this function inventing six LABELS nobody typed —
 * labels that then reach `uq_units_tenant_premises_label` and every bill after
 * it. It is served on `prefill` for the step to show and for the clerk to act
 * on.
 *
 * ⚠ **`scope` FOLLOWS THE BUILD'S OWN ROW RATHER THAN THE DEFAULT.** A draft
 * that already names a premises is not *a new premise*, and leaving the default
 * would put an actively wrong answer in front of the clerk on the shape
 * question that decides every step after it.
 */
export function draftFromRaisedBuild(
  current: NewConnectDraft,
  build: ConnectionDetail,
): NewConnectDraft {
  const pre = build.prefill;
  const premises = build.premises;
  return {
    ...current,
    connectionId: build.id,
    // `BR-SHL-048 (d)` — copied, never composed. It rides the park so the row
    // a parked wizard leaves on the New connects tab names its build.
    connectionNo: build.connection_no,
    requestNo: build.request_no,
    mode: build.mode ?? current.mode,
    targetActivation: build.target_activation ?? current.targetActivation,
    // ⊕ `DEF-CUS-9074` — the services the applicant ticked, where the clerk
    // has chosen none yet. Step 2 read *No services* over an application for
    // all six.
    premiseServices:
      current.premiseServices.length > 0 ? current.premiseServices : [...(pre?.service_codes ?? [])],
    scope: premises === null ? "new_premise" : "new_units",
    // ⊕ `DEF-CUS-9828` (N2) — the request's documents, LINKED (listed on step
    // 1, filed on the owner's account by the server at Create).
    requestId: pre?.request_id ?? current.requestId ?? null,
    requestDocuments: pre?.documents ?? current.requestDocuments ?? [],
    // ⊕ `DEF-CUS-9828` — step 3's unit, from the applicant's own `Apt-12`,
    // only for an address the resolver did not match and a pattern nobody
    // has typed (a matched building already has its units).
    pattern:
      premises === null && current.pattern.from === "" && current.pattern.to === ""
        ? { ...current.pattern, ...unitPatternFromGiven(pre?.address_unit_as_given ?? null) }
        : current.pattern,
    mailing: mailingFromRequest(current.mailing, pre?.mailing_address ?? null),
    accountCustomData: fillEmptyAnswers(current.accountCustomData, pre?.account_custom_data),
    ownerCustomData: fillEmptyAnswers(current.ownerCustomData ?? {}, pre?.customer_custom_data),
    communication: {
      ...current.communication,
      language: current.communication.language || (pre?.preferred_language ?? ""),
      // ⊕ lane CF-1 — the request's Preferences (a tick the clerk set wins).
      paperlessBill: current.communication.paperlessBill || pre?.paperless === true,
      smsReminders: current.communication.smsReminders || pre?.sms_reminders === true,
    },
    // ⊕ lane CF-1 (2026-10-18) — the request's co-applicant CARDS, whole,
    // where the clerk has none yet (their identifiers are carried by the
    // server at Create, by name — `carry_request_co_owner_numbers`).
    ...(current.coOwners === undefined && (pre?.co_applicants ?? []).length > 0
      ? { coOwnersOn: true, coOwners: coOwnersFromRequest(pre?.co_applicants ?? []) }
      : {}),
    coApplicant:
      current.coApplicant !== null || !pre?.co_applicant
        ? current.coApplicant
        : {
            ...emptyDraft().owner,
            name: pre.co_applicant.name,
            email: pre.co_applicant.email,
            phone: pre.co_applicant.phone,
            partyKind: "person",
          },
    owner: {
      ...current.owner,
      // ⊕ `DEF-CUS-9828` — FILL ONLY WHAT IS EMPTY. These three overwrote the
      // clerk's typing on every resume until 2026-10-06.
      name: current.owner.name || (pre?.applicant_name ?? ""),
      email: current.owner.email || (pre?.applicant_email ?? ""),
      phone: current.owner.phone || (pre?.applicant_phone ?? ""),
      // ⊕ `DEF-CUS-9828` — the sub-type picked on the request, only under the
      // class the draft holds (a sub-type under another class is no answer).
      subCategory:
        current.owner.subCategory ||
        ((current.owner.category || (pre?.account_type_code ?? "")) === (pre?.account_type_code ?? "")
          ? (pre?.account_subtype_code ?? "")
          : ""),
      applicationSsnLast4: pre?.ssn_last4 ?? "",
      applicationLicenceLast4: pre?.driving_licence_last4 ?? "",
      // ⚠ **`business` IS THE APPLICATION'S WORD AND `company` IS THE ACCOUNT
      // DOOR'S.** Two spellings of one fact, and reading one as the other is
      // `DEF-MET-5438` one table over. "" for anything else, because an
      // unstated kind is a real answer (`emptyDraft`'s own note).
      partyKind: applicantPartyKind(pre?.applicant_kind ?? null) || current.owner.partyKind,
      // ⊕ `DEF-CUS-9074` — the class the clerk picked on the request and a
      // person's date of birth, only where the draft holds none (a resumed
      // draft is what the clerk left behind, and it wins).
      category: current.owner.category || (pre?.account_type_code ?? ""),
      dateOfBirth: current.owner.dateOfBirth || (pre?.date_of_birth ?? ""),
      applicationTaxIdLast4: pre?.tax_id_present === true ? (pre.tax_id_last4 ?? "") : "",
      // A customer the application already matched is NAMED rather than
      // described — `BR-CUS-019`, and it is what lets the identifier go
      // untyped. The display name comes from `name` above.
      matchedCustomerId: pre?.matched_customer_id ?? current.owner.matchedCustomerId,
      // ⊕ lane CF-1 — *Contact by* and the government ID, only where empty.
      contactBy: current.owner.contactBy || (pre?.contact_by ?? ""),
      govIdLast4: current.owner.govIdLast4 || (pre?.gov_id_last4 ?? ""),
    },
    premise: {
      ...current.premise,
      // Set on the resolved shape: the build already hangs off this address and
      // `commitPlanOf` sends it as `premises.id`, so nothing is created.
      premisesId: premises?.id ?? "",
      name: premises?.name ?? current.premise.name,
      // ⚠ **`address_as_given` IS WHAT THE APPLICANT TYPED** (`BR-CUS-070`) and
      // is offered ONLY where the resolver matched nothing — which is exactly
      // the case the wizard is being asked to turn into a property.
      // ⊕ `DEF-CUS-9828` — a matched premises still wins; otherwise the
      // applicant's words fill only an EMPTY box.
      address: premises?.address ?? (current.premise.address || (pre?.address_as_given ?? "")),
      // ⊕ `DEF-CUS-9828` — the applicant's town, state and ZIP (`BR-CUS-1091`)
      // in US order, for an address the resolver did not match.
      // ⊕ `DEF-CUS-10045` — over a MATCHED premises the town, state and ZIP
      // are the register's own (served on `premises` since this fix); the
      // boxes are read-only there and drew EMPTY before, because nothing
      // filled them. Absent on the register stays absent, never a guess.
      city:
        premises !== null
          ? current.premise.city || (premises.city ?? "")
          : current.premise.city || (pre?.address_city_as_given ?? ""),
      // ⊕ `DEF-CUS-9835` — and where the request gives no state (the portal
      // asks none), the utility's own, into an EMPTY box only.
      state:
        premises !== null
          ? current.premise.state || (premises.state ?? "")
          : current.premise.state || pre?.address_state_as_given || (pre?.utility_state ?? ""),
      postalCode:
        premises !== null
          ? current.premise.postalCode || (premises.postal_code ?? "")
          : current.premise.postalCode || (pre?.address_postal_code_as_given ?? ""),
      // ⊕ `DEF-CUS-10045` — the applicant's `Unit, apt. or suite` (the postal
      // line, `BR-CUS-1091`), into an EMPTY box only. It names no unit record:
      // the units are still the step-3 range (`unitPatternFromGiven` below).
      unit: current.premise.unit || (pre?.address_unit_as_given ?? ""),
      parcelRef: current.premise.parcelRef || (pre?.plot_or_parcel ?? ""),
      premiseType: current.premise.premiseType || (pre?.property_type ?? ""),
    },
  };
}

/**
 * ⊕ `DEF-CUS-9828` — step 3's pattern for the ONE unit the applicant named
 * (`Apt-12` → prefix `Apt`, 12 to 12, which the product labels `Apt 12`), or
 * nothing when the words carry no number to start from.
 */
export function unitPatternFromGiven(
  given: string | null,
): Partial<Pick<UnitPattern, "prefix" | "from" | "to">> {
  const match = /^(.*?)[\s#.-]*(\d+)\s*$/.exec((given ?? "").trim());
  if (match === null) return {};
  return { prefix: match[1].trim(), from: String(Number(match[2])), to: String(Number(match[2])) };
}

/** ⊕ `DEF-CUS-9828` — where the bill goes, from the request, only over an
 *  untouched block (still *Same as service address* with nothing typed). */
function mailingFromRequest(
  current: NewConnectDraft["mailing"],
  given: NonNullable<ConnectionDetail["prefill"]>["mailing_address"] | null,
): NewConnectDraft["mailing"] {
  const untouched =
    current.sameAsService &&
    [current.address, current.unit, current.city, current.state, current.postalCode].every(
      (part) => part === "",
    );
  if (!untouched || given === null || given === undefined || !(given.line1 ?? "").trim()) {
    return current;
  }
  return {
    sameAsService: false,
    address: given.line1 ?? "",
    unit: given.line2 ?? "",
    city: given.city ?? "",
    state: given.state ?? "",
    postalCode: given.postal_code ?? "",
  };
}

/** ⊕ `DEF-CUS-9828` — the utility's own answers typed on the request, where
 *  the clerk has typed nothing for that field. */
function fillEmptyAnswers(
  current: Record<string, unknown>,
  given: Record<string, unknown> | undefined,
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...(given ?? {}) };
  for (const [key, value] of Object.entries(current)) {
    if (value !== "" && value !== null && value !== undefined) out[key] = value;
  }
  return out;
}

/** `person` · `business` (the application's words) → `person` · `company` (the
 *  accounts door's). Anything else is "" — unstated, which mints no customer
 *  number and says so. */
export function applicantPartyKind(kind: string | null): string {
  if (kind === "person") return "person";
  if (kind === "business" || kind === "company") return "company";
  return "";
}


// ══════════════════════════════════════════════════════════════════════════
// `BR-SHL-048 (d)` — READING THE BUILD BACK OUT OF A PARKED DRAFT
// ══════════════════════════════════════════════════════════════════════════
//
// PO ruling 2026-09-21, verbatim: *"this is big problem - we cannot create two
// build - you can update the existing build"*.
//
// ⚠ **THESE EXIST BECAUSE `hydrateForm` CANNOT DO IT AND MUST NOT BE MADE TO
// (`DEF-CUS-6135`).** That helper keeps a parked value only where `typeof
// value === typeof empty[key]`, which is exactly what refuses a week-old
// `unitId: 42` and `autopay: "yes"` — a real guard, shared by all five
// wizards. An EMPTY draft holds `null` for `connectionId`, `connectionNo` and
// `requestNo`; `typeof null` is `"object"` and the parked value is a
// `"string"`, so all three were dropped on every resume. **Loosening
// `hydrateForm` would weaken that guard for move-in, move-out, transfer and
// disconnect to fix one field in one wizard**, so the three fields are read
// back BY NAME here instead.
//
// ⚠ **`subject_ref` FIRST, `values.draft` SECOND, AND THE SECOND IS NOT
// TIDINESS.** `subject_ref` is where the ruling puts a copied id; drafts parked
// before this fix have nothing there and carry the id inside `values.draft`,
// and they are sitting on a beta tenant's tab right now. Without the fallback
// every one of them would still mint a second build the first time somebody
// picked it up.

/** A JSON object, or `{}` — the same narrowing `hydrateForm` opens with. */
function parkedObject(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

/** One parked scalar as a non-empty string, else `null`. An empty string is
 *  *not filled in*, which for these three fields is the same as absent. */
export function parkedScalar(source: unknown, key: string): string | null {
  const value = parkedObject(source)[key];
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

/** What `useWizardPark` hands `onHydrate`, narrowed to the two fields read
 *  here — a structural parameter, so this module takes no import from the park
 *  store and nothing closes a cycle. */
export interface ParkedNewConnect {
  subject_ref?: unknown;
  values: Record<string, unknown>;
}

/** The park's own two places, in the ruling's order. */
function fromThePark(row: ParkedNewConnect, key: string, draftKey: string): string | null {
  return parkedScalar(row.subject_ref, key) ?? parkedScalar(row.values.draft, draftKey);
}

/** **The build this parked wizard was finishing**, or `null` for a New Connect
 *  started from scratch. `commitPlanOf` sends it as `connection_id`, which is
 *  the difference between finishing `CON-26-0129` and minting `CON-26-0132`. */
export function parkedBuildId(row: ParkedNewConnect): string | null {
  return fromThePark(row, "connection_id", "connectionId");
}

/** That build's own NUMBER, for the clerk to read. Never composed here. */
export function parkedBuildNo(row: ParkedNewConnect): string | null {
  return fromThePark(row, "connection_no", "connectionNo");
}

/**
 * **What a park CARRIES about the build it is finishing** — `subject_ref`.
 *
 * `BR-SHL-048 (d)`, PO 2026-09-21: *"this is big problem - we cannot create two
 * build - you can update the existing build"*.
 *
 * ⚠ **THIS WAS THE LITERAL `{}` IN THE WIZARD UNTIL TODAY, AND THE SENTENCE
 * DEFENDING IT WAS TRUE WHEN IT WAS WRITTEN (`DEF-CUS-6135`).** It read *"a new
 * connect has no premise id, no unit id and no account id until it commits —
 * there is nothing to copy"*. `DEF-CUS-6109` made approving an application
 * raise the build BEFORE the wizard opens, and from that day there WAS.
 *
 * ⚠ **COPIED VALUES, STILL NOT A FOREIGN KEY — clause (a) is UNTOUCHED.** Two
 * strings in a JSON column give nothing to join on, so deleting the build is
 * still not blocked by a forgotten draft and no report can still reach one.
 *
 * ⚠ **IT IS A FUNCTION SO A CASE CAN CALL THE REAL THING.** A test that built
 * this object itself would be asserting its own fixture — law 7's *structurally
 * incapable of failing* — and this is one of the two halves the defect was made
 * of.
 */
export function parkSubjectRefOf(draft: NewConnectDraft): WizardParkSubjectRef {
  if (draft.connectionId === null) {
    // A New Connect started from SCRATCH. `BR-MET-112` unchanged: there is no
    // build to name and the last press creates exactly one.
    return {};
  }
  return {
    connection_id: draft.connectionId,
    // The NUMBER as well as the id: the id is what the commit finishes, the
    // number is what the New connects tab prints so the row a parked wizard
    // leaves names its build instead of nothing.
    connection_no: draft.connectionNo ?? "",
  };
}

/**
 * **A parked draft, put back into a wizard's state** — `onHydrate`'s whole body.
 *
 * ⚠ **IT IS A FUNCTION RATHER THAN A CLOSURE IN THE WIZARD BECAUSE THAT IS
 * WHERE `DEF-CUS-6135` LIVED AND NOTHING COULD REACH IT.** The id was parked
 * correctly and dropped one line later, inside a callback a test can only get
 * at by driving eight steps of a browser — so the suite proved the PARK and
 * never the RESUME, `tsc` was clean, and the only symptom was a row nobody
 * looks at. Pulled out here, the thing that broke is one call a case can make.
 *
 * ⚠ **THE NESTED FORMS ARE HYDRATED ONE AT A TIME, NOT IN ONE SPREAD.**
 * `hydrateForm` checks a field against the EMPTY draft's own type, which is
 * enough for a scalar and is NOT enough for `owner`, `premise` and `pattern`:
 * each is an object, so `typeof` matches whatever object arrives — `{}`, or one
 * with `name: 42`. Narrowing each in turn is what stops a week-old draft
 * putting a number where step 1 expects a name, which would pass `validate()`
 * (`.trim()` on a number throws) and take the screen down.
 *
 * ⚠ **AND THE THREE IDENTITY FIELDS ARE READ BACK BY NAME, BECAUSE THAT SAME
 * `typeof` RULE DROPS THEM.** An empty draft holds `null` for `connectionId`,
 * `connectionNo` and `requestNo`; `typeof null` is `"object"` and the parked
 * value is a `"string"`, so every one was silently lost on resume. Loosening
 * `hydrateForm` would weaken a guard all five wizards share to fix three fields
 * in one of them (`BR-SHL-048 (d)`).
 */
export function draftFromPark(row: ParkedNewConnect): NewConnectDraft {
  const blank = emptyDraft();
  const parked = hydrateForm(blank, row.values.draft);
  // ⊕ lane CF-1 — the optional fields `hydrateForm` cannot see (the empty
  // draft does not hold them), each narrowed by hand.
  const raw = (row.values.draft ?? {}) as Record<string, unknown>;
  const rawOwner = (typeof raw.owner === "object" && raw.owner !== null ? raw.owner : {}) as Record<
    string,
    unknown
  >;
  const text = (value: unknown): string => (typeof value === "string" ? value : "");
  return {
    ...parked,
    connectionId: parkedBuildId(row),
    connectionNo: parkedBuildNo(row),
    requestNo: parkedScalar(row.values.draft, "requestNo"),
    ...(Array.isArray(raw.coOwners)
      ? { coOwners: hydrateCoOwners(raw.coOwners), coOwnersOn: raw.coOwnersOn === true }
      : {}),
    owner: {
      ...hydrateForm(blank.owner, parked.owner),
      contactBy: text(rawOwner.contactBy),
      govIdLast4: text(rawOwner.govIdLast4),
    },
    premise: hydrateForm(blank.premise, parked.premise),
    pattern: hydrateForm(blank.pattern, parked.pattern),
    // `billing` is an OBJECT, so `hydrateForm`'s `typeof` check matches any
    // object at all — `{}` included — exactly as it does for `owner`,
    // `premise` and `pattern`. Narrowed here for the same reason they are.
    billing: hydrateForm(blank.billing, parked.billing),
    messagesOff: parkedStringList(parked.messagesOff),
    premiseServices: parkedStringList(parked.premiseServices),
    apartmentServices: parkedStringList(parked.apartmentServices),
    commonAreaServices: parkedStringList(parked.commonAreaServices),
  };
}


/**
 * ⚠ **`parkedId` IS A FOURTH ARGUMENT AND NOT A FIELD ON THE DRAFT
 * (`BR-SHL-048 (d)`).** `?parked=` is URL state that `useWizardPark` owns; a
 * copy of it inside the draft would be a second answer to *which draft am I*,
 * free to disagree with the address bar — and the draft is the thing that gets
 * SERIALISED INTO the park, so it would also store its own id inside itself.
 * It is optional, so every existing caller and every test still compiles and
 * sends `null`, which is what a wizard that was never parked means.
 */
/** The asset types that ARE meters — the `meters` tab of `asset_types`
 *  (`assets.SEED_ASSET_TYPES`). A meter is never sent as SIZED equipment: it
 *  is read, not counted or summed. */
const METER_DEVICE_TYPES: ReadonlySet<string> = new Set(["meter", "net_meter", "sub_meter"]);

/**
 * **`DEF-MET-6119` — the services a meter does not carry, and their sizes.**
 *
 * Step 4's grid has always held a device type and a size per unit × service,
 * and until 2026-10-01 nothing sent either: the payload had no member for a
 * service without a meter, so a build selling trash, fire, sewer or storm
 * water recorded none of them, and no cart, fire line, panel or battery was
 * created to say how big the service is. Those are what the bill COUNTS or
 * SUMS (`BR-RAT-090`, `BR-TEN-171`), so the account billed `$0.00` for them.
 *
 * Every taken service that is not METERED gets a row — the derived and flat
 * ones because nothing else carries them, and solar and battery because their
 * capacity is the panels and batteries (PO 2026-10-02: *"Capacity is the
 * panels or battery only"* — and they take no net meter at all now,
 * `DEF-MET-9037`). The device and size are the CELL's, which the step pins to
 * the defaults it shows (`NewConnectUnitsStep`), so what was on screen is what
 * is sent — and each further row of the same service is one more piece
 * (`piecesBySize`).
 */
/**
 * **The row's pieces, COUNTED by size** — the first piece is the row's own
 * `sizeClass`, each `more` entry one further piece (`OQ-1361`). Sizes keep the
 * order the clerk first used them in, so `FL-6, FL-2, FL-2` is sent as
 * `[FL-6 × 1, FL-2 × 2]`. A piece with no size is not sent: the server refuses
 * an unsized piece by name (`BR-TEN-171`), and the step pins a size on every
 * row it shows.
 */
export function piecesBySize(
  type: string,
  cell: UnitServiceCell,
): { type: string; size_class: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const raw of [cell.sizeClass ?? "", ...(cell.more ?? [])]) {
    const size = raw.trim();
    if (size !== "") {
      counts.set(size, (counts.get(size) ?? 0) + 1);
    }
  }
  return [...counts].map(([size_class, count]) => ({ type, size_class, count }));
}

export function commitUnitServicesOf(
  draft: NewConnectDraft,
  units: readonly DraftUnit[],
  services: Record<string, string[]>,
): CommitPlan["unit_services"] {
  const rows: CommitPlan["unit_services"] = [];
  for (const unit of units) {
    for (const service of services[unit.label] ?? []) {
      if (serviceFamily(service) === "metered") {
        continue;
      }
      const cell = draft.unitServiceGrid[unitServiceKey(unit.label, service)] ?? {};
      const type = (cell.assetType ?? "").trim();
      // ⊕ `DEF-MET-9222` — storm water's class and thermal's tonnage are the
      // UNIT's size, carried by no device; the row's own size travels here and
      // the commit records it on the unit. Step 3 pins the shown default into
      // the cell, so what was on screen is what is sent.
      const unitSize = capacityIsOnTheUnit(service) ? (cell.sizeClass ?? "").trim() : "";
      rows.push({
        unit_label: unit.label,
        service,
        equipment:
          type !== "" && !METER_DEVICE_TYPES.has(type) && !capacityIsOnTheUnit(service)
            ? piecesBySize(type, cell)
            : [],
        ...(unitSize === "" ? {} : { size_class: unitSize }),
      });
    }
  }
  return rows;
}

/**
 * ⊕ **`DEF-MET-9223` — EACH WORK ORDER ON THE UNIT THE CLERK CHOSE.**
 *
 * Until 2026-10-03 every entry was `{template_id, template_version}` and
 * nothing else, so the commit raised every job on the WHOLE build: a per-unit
 * *Meter set* on a 2-unit build was one order with no unit, and one whole-build
 * gate held every unit of its service back. The server has read `unit_label`
 * and `service` on each entry since `DEF-MET-5428`; nothing sent them.
 *
 * **Where each job goes — the clerk's own choices, never a guess:**
 *  * a job added with *Applies to* goes where that says — `unit:<label>` on the
 *    unit, `sp:<label>␟<service>` on that service point, `build` on the whole
 *    build;
 *  * a proposed job goes on every taken step-3 row of ITS service, unless the
 *    clerk swapped that row's job away from it, and on any row whose *Work
 *    order* cell names it. `per_unit` is one order per unit, `per_asset` one
 *    per row;
 *  * a `per_premise` job (or any other scope), or one no row names, stays one
 *    order on the whole build — which is what *Whole build* means.
 *
 * ⚠ **ONE LIST, TWO READERS.** Step 5's *Work orders* count is this list's
 * length, so the review cannot promise a number the commit does not raise.
 */
export function commitWorkOrdersOf(
  draft: NewConnectDraft,
  proposed: readonly ProposedWorkOrder[],
): CommitPlan["work_orders"] {
  const units = draftUnits(draft);
  const services = draftUnitServices(draft);
  const proposedFor = (service: string) =>
    proposed.find((one) => one.service?.code === service)?.template_id ?? "";
  const out: CommitPlan["work_orders"] = [];
  for (const order of proposed) {
    const base = { template_id: order.template_id, template_version: order.version };
    const scope = order.scope ?? "";
    if (scope.startsWith("unit:")) {
      out.push({ ...base, unit_label: scope.slice(5) });
      continue;
    }
    if (scope.startsWith("sp:")) {
      const [label, service] = scope.slice(3).split("\u001F");
      out.push({ ...base, unit_label: label, ...(service ? { service } : {}) });
      continue;
    }
    const rows: { unit_label: string; service: string }[] = [];
    if (scope === "per_unit" || scope === "per_asset") {
      for (const unit of units) {
        for (const service of services[unit.label] ?? []) {
          const cell = draft.unitServiceGrid[unitServiceKey(unit.label, service)];
          const picked = cell?.workOrderTemplateId;
          // ⊕ The walk's re-run: a row's cell names ONE job, so a service's
          // second and third jobs (*Tap and service line*, *Meter set*) were
          // named by no row and stayed on the whole build. A job of the row's
          // own service stands on it unless the clerk swapped the row's
          // default AWAY from this job; a job the clerk picked stands on it
          // whatever its service.
          const ofThisService = order.service?.code === service;
          const swappedAway =
            picked !== undefined &&
            picked !== order.template_id &&
            proposedFor(service) === order.template_id;
          if (picked === order.template_id || (ofThisService && !swappedAway)) {
            rows.push({ unit_label: unit.label, service });
          }
        }
      }
    }
    if (rows.length === 0) {
      out.push(base);
      continue;
    }
    if (scope === "per_unit") {
      for (const label of [...new Set(rows.map((row) => row.unit_label))]) {
        const mine = [...new Set(rows.filter((row) => row.unit_label === label).map((row) => row.service))];
        out.push({ ...base, unit_label: label, ...(mine.length === 1 ? { service: mine[0] } : {}) });
      }
      continue;
    }
    for (const row of rows) {
      out.push({ ...base, unit_label: row.unit_label, service: row.service });
    }
  }
  return out;
}

/**
 * ⊕ `DEF-CUS-9830` — the co-applicant as ONE co-owner row, or nothing.
 * Nothing for no panel and for a panel left with no name (step 1 refuses that
 * before the commit; a name-less row is never sent). Blank facts are `null`.
 */
export function coOwnersOf(
  person: OwnerForm | null,
): { co_owners?: Record<string, string | null>[] } {
  if (person === null || person.name.trim() === "") return {};
  const given = (value: string): string | null => (value.trim() === "" ? null : value.trim());
  return {
    co_owners: [
      {
        full_name: person.name.trim(),
        email: given(person.email),
        phone: given(person.phone),
        date_of_birth: given(person.dateOfBirth),
        ssn: given(person.ssn),
        driving_licence: given(person.drivingLicence),
      },
    ],
  };
}

/**
 * ⊕ lane CF-1 (2026-10-18) — the step's co-owner cards and their tick. A draft
 * written before the cards (one `coApplicant`) reads as ONE ticked card with
 * that person's answers, so nothing a clerk parked is lost.
 */
export function draftCoOwners(draft: NewConnectDraft): { on: boolean; rows: CoOwnerDraft[] } {
  if (draft.coOwners !== undefined) {
    return { on: draft.coOwnersOn ?? draft.coOwners.length > 0, rows: draft.coOwners };
  }
  const person = draft.coApplicant;
  if (person === null) return { on: false, rows: [] };
  return {
    on: true,
    rows: [
      {
        ...emptyCoOwner(),
        full_name: person.name,
        email: person.email,
        phone: person.phone,
        date_of_birth: person.dateOfBirth,
        ssn: person.ssn,
        driving_licence: person.drivingLicence,
      },
    ],
  };
}

/**
 * ⊕ lane CF-1 — the owner block's `co_owners`, from the cards. A company
 * owner's people are OWNERS OR OFFICERS (move-in's own rule, by the holder's
 * kind). A card with no name is not sent; unticked sends nothing. A draft
 * still holding only the old `coApplicant` keeps its old payload exactly
 * (`coOwnersOf`).
 */
export function draftCoOwnersPayload(draft: NewConnectDraft): { co_owners?: Record<string, unknown>[] } {
  if (draft.coOwners === undefined) return coOwnersOf(draft.coApplicant);
  const { on, rows } = draftCoOwners(draft);
  const named = rows.filter((row) => row.full_name.trim() !== "");
  if (!on || named.length === 0) return {};
  return {
    co_owners: coOwnersPayload(draft.owner.partyKind === "company" ? "officer" : "co_owner", named),
  };
}

/**
 * ⊕ **`DEF-CUS-10222` (lane CF-1) — WHERE THE BILL GOES, SENT AT LAST.** Step 1
 * has asked for a mailing address since `CR-150-BRC09` and the commit never
 * carried it, so every owner's account opened with none. Unticked with a
 * street: one `kind: "mailing"` row in the accounts door's own words (hard
 * rule 8's named exception). Ticked: an EMPTY list, which the server reads as
 * *the bill goes to the building* — never omitted, because an omitted key lets
 * a request's own mailing address fill it (`_carry_application_mailing`).
 */
export function ownerMailingAddresses(draft: NewConnectDraft): { addresses: Record<string, string>[] } {
  const mailing = draft.mailing;
  const line1 = mailing.address.trim();
  if (mailing.sameAsService || line1 === "") return { addresses: [] };
  const row: Record<string, string> = { kind: "mailing", line1 };
  const put = (key: string, value: string) => {
    if (value.trim() !== "") row[key] = value.trim();
  };
  put("line2", mailing.unit);
  put("city", mailing.city);
  put("state", mailing.state);
  put("postal_code", mailing.postalCode);
  return { addresses: [row] };
}

/** ⊕ lane CF-1 — the files to file on the owner's account after the commit:
 *  with Move-in's table, only those a row still names (a file the clerk took
 *  off a row is not filed); a draft from before the table files all it holds. */
export function ownerDocumentsToFile(draft: NewConnectDraft): DraftDocument[] {
  if (draft.ownerDocDrafts === undefined) return draft.ownerDocuments;
  const named = new Set(draft.ownerDocDrafts.map((row) => row.card_id).filter((id) => id !== ""));
  return draft.ownerDocuments.filter((doc) => named.has(doc.id));
}

/** ⊕ lane CF-1 — the owner's *Contact by* and government ID, only when typed. */
export function ownerContactFacts(owner: OwnerForm): Record<string, string> {
  const out: Record<string, string> = {};
  if ((owner.contactBy ?? "").trim() !== "") out.contact_by = (owner.contactBy ?? "").trim();
  if ((owner.govIdLast4 ?? "").trim() !== "") out.gov_id_last4 = (owner.govIdLast4 ?? "").trim();
  return out;
}

/** ⊕ lane CF-1 — the request's co-applicant cards as the step's cards (their
 *  SSN and licence are never served, so those boxes stay empty). */
export function coOwnersFromRequest(
  cards: NonNullable<NonNullable<ConnectionDetail["prefill"]>["co_applicants"]>,
): CoOwnerDraft[] {
  return hydrateCoOwners(
    cards.map((card) => ({
      full_name: card.full_name,
      relationship: card.relationship ?? "",
      phone: card.phone ?? "",
      email: card.email ?? "",
      contact_by: card.contact_by ?? "",
      date_of_birth: card.date_of_birth ?? "",
      responsible_for_bills: card.responsible_for_bills === true,
    })),
  ).map((row, index) => ({
    ...row,
    // ⊕ `DEF-CUS-10232` — the summary says an ID is on file (its mask).
    id_on_file: idOnFileMask(cards[index]?.ssn_last4, cards[index]?.driving_licence_last4),
  }));
}

/**
 * ⊕ `DEF-CUS-9830` — PO ruling 2026-10-06: *"make SSN, Email, Phone , DOb
 * optional for co applicant"*. Only her NAME is required; an email is checked
 * for its shape only when given (the server's own test: an `@` inside it).
 * Returns the catalogue key of the first shortfall, or `null`.
 */
export function coApplicantShortfall(person: OwnerForm | null): string | null {
  if (person === null) return null;
  if (person.name.trim() === "") return "customers.newConnect.step1.coApplicantNameRequired";
  const email = person.email.trim();
  if (email !== "" && (!email.includes("@") || email.startsWith("@") || email.endsWith("@"))) {
    return "customers.contact.email_format";
  }
  return null;
}

export function commitPlanOf(
  draft: NewConnectDraft,
  quoteTotal: string | null,
  proposed?: readonly ProposedWorkOrder[],
  parkedId?: string | null,
  submitToken?: string | null,
): CommitPlan {
  const units = draftUnits(draft);
  const services = draftUnitServices(draft);
  const meters: CommitPlan["meters"] = [];
  for (const unit of units) {
    for (const service of services[unit.label] ?? []) {
      if (takesAMeter(service)) {
        // ⚠ `asset_no: null` is deliberate and is step 8's own `Outstanding
        // work` item 1: *"50 meters still read 'to assign' — bulk assign them
        // or the crew has nothing to fit"*. A number invented here would be a
        // meter serial nobody has.
        // ⊕ `DEF-MET-9221` — the meter's SIZE, the one step 3 shows on its
        // row (*Water 1"*, *Electric 1φ 100A*). It never travelled, so every
        // meter a build fitted was unsized, and on a size-banded service
        // `BR-RAT-108` cannot pick the base charge without it.
        const size = (draft.unitServiceGrid[unitServiceKey(unit.label, service)]?.sizeClass ?? "").trim();
        meters.push({
          unit_label: unit.label,
          service,
          asset_no: null,
          ...(size === "" ? {} : { size_class: size }),
        });
      }
    }
  }
  const unitServices = commitUnitServicesOf(draft, units, services);
  return {
    premises: {
      // ⚠ **A PICKED ADDRESS IS NAMED, NEVER RE-CREATED (`DEF-CUS-5468`).**
      // `commit_new_connect` reads this key FIRST: set, it becomes
      // `premises_id` and nothing below is written; null, and the block builds
      // a new property through `create_premises`. Hard rule 8 is why the
      // search exists — this is the one door that can make a second row for a
      // building that already has one.
      id: draft.premise.premisesId === "" ? null : draft.premise.premisesId,
      // `premises.name` — the column has always existed and nothing asked for
      // it. NULL rather than "" so an unnamed house is *not named* rather than
      // named the empty string.
      name: draft.premise.name.trim() === "" ? null : draft.premise.name.trim(),
      address: draft.premise.address.trim(),
      // ⚠ **THE TOWN, SENT FOR THE FIRST TIME (`DEF-CUS-5468` / `DEF-MET-5469`).**
      // `_validate_premises` has accepted `city`, `state` and `postal_code`
      // since `US-MET-001` and this door's own translation table carried none
      // of the three, so every property built by this wizard held NULL for all
      // of them — and `accountDetailHeader` walks to the premises for its
      // `Austin, TX 78704` line, which was therefore blank forever with `tsc`
      // and every test green. That is `DEF-CUS-3653` exactly, one door over.
      city: draft.premise.city.trim() === "" ? null : draft.premise.city.trim(),
      state: draft.premise.state.trim() === "" ? null : draft.premise.state.trim(),
      postal_code:
        draft.premise.postalCode.trim() === "" ? null : draft.premise.postalCode.trim(),
      premise_type: draft.premise.premiseType === "" ? null : draft.premise.premiseType,
      parcel_ref: draft.premise.parcelRef.trim() === "" ? null : draft.premise.parcelRef.trim(),
      read_route: draft.premise.readRoute.trim() === "" ? null : draft.premise.readRoute.trim(),
      // ⚠ **STEP 4'S TICKS, SENT FOR THE FIRST TIME (`DEF-MET-5465`).** They
      // decide what every unit below may be metered for and they went no
      // further than the browser, so the property was created with
      // `services_available` NULL — and `BR-MET-003`'s inner bound (`DEF-772`)
      // then refused every meter on it with *"nobody has been asked which
      // services this address offers"*. A clerk who ticked Electric and Water
      // two steps earlier was told exactly that, and the whole build was lost.
      services_available: [...draft.premiseServices],
      // `CR-161-BRC10` W3 · `DEF-MET-9226` — the new property's own field
      // answers, only when it IS new and only when something was typed; the
      // door validates them for *New Connection · Step 2 Premise*.
      ...(draft.premise.premisesId === "" &&
      Object.keys(draft.premise.customData ?? {}).length > 0
        ? { custom_data: draft.premise.customData }
        : {}),
    },
    mode: draft.mode,
    // ⚠ **STEP 1'S SCOPE, SENT FOR THE FIRST TIME (`DEF-CUS-5435`).** It has
    // decided the shape of this whole draft since the wizard was built — how
    // many units the pattern makes, whether a common area exists — and it went
    // no further than the browser, so the server was handed the CONSEQUENCES of
    // a choice and never the choice. `connections` has no column for it today;
    // this is the contract asking for one, and the sentence above the interface
    // says what reads it (nothing, yet).
    scope: draft.scope,
    // ⚠ **THE PREFIX'S EFFECT ALREADY TRAVELLED; THE PREFIX ITSELF DID NOT.**
    // `expandUnitPattern` builds `Apt 1 … Apt 26` and `units[].label` carries
    // every one of them, so a build committed today lands with its prefix baked
    // into 26 labels and no record of what it WAS. Sending it once means a
    // later unit can be added to the same building under the same naming
    // without a person re-reading a label and guessing.
    units_prefix: draft.pattern.prefix.trim() === "" ? null : draft.pattern.prefix.trim(),
    target_activation: draft.targetActivation === "" ? null : draft.targetActivation,
    // ⚠ **STILL `null`, AND SINCE `DEF-CUS-6109` THAT IS THE ANSWER RATHER
    // THAN A GAP.** Where an application raised this build, the request is
    // already on the `connections` row — `create_connection` wrote it when the
    // draft was raised — so sending it again from a browser would be a second
    // writer for one fact. Where there was no application there is nothing to
    // send, and `BR-MET-1178` says a build prices itself without one.
    service_request_id: null,
    // `DEF-CUS-6109` — which build this press finishes. `null` starts a new one.
    connection_id: draft.connectionId,
    // `BR-SHL-048 (d)` — the draft that was holding this typing. The server
    // discards it inside the commit, so one piece of work leaves one row.
    wizard_park_id: parkedId ?? null,
    // ── `DEF-CUS-8021` · CLAUDE.md HARD RULE 6 · THE DOUBLE-CLICK ─────────
    //
    // ⚠ **PRESSING *Create connection* TWICE BUILT TWO OF EVERYTHING.** The
    // identical payload posted twice with the parcel box EMPTY answered 200
    // both times — `CON-26-0130` and `CON-26-0131`, two accounts, two
    // customers, two properties at one address and **two payments of $250.00,
    // each posting its own balanced ledger pair.** With a parcel typed the
    // second press was refused `409 premises.external_ref_taken`, which is a
    // uniqueness constraint on a different column and not idempotency at all
    // — which is exactly why the first walk of this check passed.
    //
    // ⚠ **THE TOKEN NAMES THE BUILD AND NOT THE PRESS.** A token minted here,
    // on every call, would be a new string every time and would protect
    // nothing; a token minted with the draft is stable across every press of
    // one build and new for the next one. That is why it arrives as an
    // ARGUMENT — this function is called on each press, and the caller is the
    // thing that lives as long as the build does. `NewConnectWizard` holds it
    // in a ref, the same shape and for the same reason as `parkedId` above.
    //
    // ⚠ **`null` IS A REAL CASE AND IS NOT A BUG HERE.** A test or another
    // caller that sends none gets a build with no replay protection and the
    // server says so on `unavailable`. What must never be null is the
    // WIZARD's, and `NewConnectCommitToken.dom.test.tsx` is what asserts it.
    commit_token: submitToken ?? null,
    // ⊕ `CR-164-BRC10` item 15 — the unit type travels (`CR-162-BRC10` stores
    // it, resolved through `_resolve_unit_type`). Absent when none was chosen,
    // so the column stays NULL rather than a guessed default.
    units: units.map((unit) => {
      const unitType = unit.isCommonArea ? "" : (draft.unitTypes?.[unit.label] ?? "").trim();
      return {
        label: unit.label,
        is_common_area: unit.isCommonArea,
        ...(unitType === "" ? {} : { unit_type: unitType }),
      };
    }),
    meters,
    unit_services: unitServices,
    // ⚠ **A COMMON AREA IS SENT NO PLAN AT ALL, AND THAT IS A PO RULING, NOT A
    // GAP (2026-09-16, `DEF-CUS-5496`).** Put to the PO as three options — its
    // own plan, the dwellings' plan, or none — and they chose NONE.
    //
    // ⚠ **THE FILTER IS WHY THIS COSTS NO MONEY-PATH CHANGE, AND IT IS THE
    // WHOLE POINT.** The PO's own words for this option were *"needs the server
    // to stop requiring one — a money-path change"*, and it does not: the
    // commit LOOPS over `plan_assignments` (`connections.py:3720`), so a unit
    // that is not IN the list is simply never assigned one. `_apply_unit_plan`
    // keeps refusing an empty `tariff_id` by name, exactly as it did
    // (`metering/services.py:2486`, `metering.plan.tariff_required`). We send
    // one fewer row; we do not loosen a rule. Never "fix" this by relaxing that
    // check — the refusal is what stops a DWELLING going out unpriced.
    //
    // ⚠ **BEFORE THIS, EVERY BUILD WITH A COMMON AREA WAS REFUSED OUTRIGHT.**
    // The row below used to read `unit.isCommonArea ? draft.planCommonArea :
    // draft.planApartments`, and when the plan question moved to step 2 only
    // `planApartments` moved with it — so the common area posted `tariff_id:
    // null` and the clerk was told *"Choose a plan"* on a build where they had.
    // An apartment complex with a common area is this wizard's default shape.
    //
    // ⚠ **THE CONSEQUENCE, STATED BECAUSE NOTHING ELSE STATES IT:** a unit with
    // no plan is a state the product already models (`unit_has_no_plan`), and
    // it CANNOT later be activated as a billing account without a plan being
    // chosen then (`customers.account.plan_required_at_activation`). That is
    // correct for a hallway and it is a real step for anyone who later bills
    // one.
    plan_assignments: units
      .filter((unit) => !unit.isCommonArea)
      .map((unit) => ({
        unit_label: unit.label,
        tariff_id: draft.planApartments || null,
      })),
    // BR-MET-113 (OQ-367 CLOSED, PO 2026-08-25): *"You will have to assign
    // account number to owner and tag everything to account number"*.
    // `BR-CUS-1114` (PO 2026-10-02) — and only on a building of two or more
    // units; the server refuses a master on a single unit whatever is sent.
    // ⊕ `DEF-CUS-9228` (PO 2026-10-02, item 1) — and on a single-family home,
    // the owner's own REGULAR account, which the server opens on the one home.
    create_owner_account: buildOpensOwnerAccount(draft, units),
    owner: {
      name: draft.owner.name.trim(),
      kind: draft.owner.kind,
      // ⊕ **`DEF-CUS-9047` — THE CATEGORY STEP 1 REQUIRES, AND NEVER SENT.**
      // The owner's master account opened in the request's class or as
      // `commercial` whatever the clerk picked here; `connections.py` has read
      // `account_type` off this block all along. Omitted when nothing is
      // picked, so the request's own class still decides then.
      ...(draft.owner.category ? { account_type: draft.owner.category } : {}),
      sub_category: draft.owner.subCategory,
      // ⊕ **`DEF-CUS-9822` (N1) — THE SUB-TYPE, IN THE ACCOUNT DOOR'S OWN
      // WORD, AS MOVE-IN SENDS IT** (`account_subtype`, the code). The wizard's
      // `sub_category` above is dropped by the server's translation; this is
      // what reaches the owner's account. Omitted for none and for a code
      // stored before the list was the utility's own.
      ...ownerAccountSubtype(draft.owner.subCategory),
      email: draft.owner.email.trim(),
      phone: draft.owner.phone.trim(),
      // ⚠ **THE PARTY KIND AND THE IDENTITY, WHICH DECIDE WHETHER THE ACCOUNT
      // DOOR OPENS AT ALL** (`DEF-MET-5093`, `DEF-MET-5438`, `DEF-CUS-5467`).
      // Without them `refuse_account_without_identity` refuses the whole build
      // with `customers.account.identity_kind_required`, so a clerk who filled
      // in every drawn field was told their build could not be created.
      ...ownerIdentityPayload(draft.owner),
      // ⚠ **THE PICKED CUSTOMER, IN THE ACCOUNTS DOOR'S OWN VOCABULARY.**
      // `_owner_block_in_the_doors_language` translates the wizard's words into
      // a `customer` block and is explicit that it is *"a translation, never an
      // override"* — a caller that already assembled one properly keeps what it
      // wrote. This is that caller: once a clerk has POINTED AT a row the
      // wizard is no longer describing a party, it is NAMING one, and
      // `customer_id` is the strongest statement the door accepts
      // (`BR-CUS-019`). It is also what lets the identifier go untyped —
      // `refuse_account_without_identity` returns early on a named customer,
      // which is the whole of *"if found, attach and do not retype"*.
      ...(draft.owner.matchedCustomerId === null
        ? {}
        : {
            customer: {
              customer_id: draft.owner.matchedCustomerId,
              display_name: draft.owner.name.trim(),
              kind: draft.owner.partyKind || null,
            },
          }),
      // `customers.external_ref` is the home this is written for — nullable,
      // unique per tenant, the LEGACY identifier. NULL rather than "" so the
      // uniqueness constraint's partial index behaves: two owners with no
      // legacy id are not two owners with the same one.
      external_ref: draft.owner.externalRef.trim() === "" ? null : draft.owner.externalRef.trim(),
      // ── `CR-150-BRC09` task 11 · STEP 4's BILLING PREFERENCES ───────────
      //
      // ⚠ **FOUR COLUMNS THE ACCOUNTS DOOR HAS ALWAYS ACCEPTED AND THIS
      // WIZARD HAS NEVER SENT.** `customers.CREATE_FIELDS` lists all four by
      // name, and `create_owner_account` assembled a fixed dict that carried
      // none of them — so four drawn boxes would have been four values
      // discarded at the commit (`DEF-CUS-5485`, hard-won law 2).
      //
      // ⚠ **`null` RATHER THAN `""` ON BOTH TEXT FIELDS**, the posture every
      // other nullable on this payload already takes. **The two flags are
      // sent always**: a boolean has no absence, and `false` is the clerk
      // leaving it unticked, which is a real answer.
      autopay: draft.billing.autopay,
      tax_exempt: draft.billing.taxExempt,
      tax_exempt_ref:
        draft.billing.taxExemptRef.trim() === "" ? null : draft.billing.taxExemptRef.trim(),
      tax_exempt_expires:
        draft.billing.taxExemptExpires === "" ? null : draft.billing.taxExemptExpires,
      // ⊕ **`DEF-CUS-9159` (CR-161-BRC10 W3) — STEP 1'S *ACCOUNT DETAILS*,
      // TYPED, SHOWN AND NEVER SENT.** The utility's own account fields render
      // on step 1 (slot `S18`) and this block had no key for them, so the
      // build's account opened without them. Sent ALWAYS, empty included: the
      // server checks them as the `S18` slot only when the owner's account
      // opens, so a required field drawn on step 1 needs its answer.
      custom_data: draft.accountCustomData,
      // ⊕ `CR-164-BRC10` wave 2 — sent ALWAYS for a new owner, empty included,
      // so a required field placed on Step 1 is checked (`DEF-CUS-9191`'s
      // lesson); never over a customer the clerk picked, whose record this
      // build does not rewrite.
      ...(draft.owner.matchedCustomerId === null
        ? { customer_custom_data: draft.ownerCustomData ?? {} }
        : {}),
      // ⊕ **`CR-164-BRC10` / `DEF-CUS-9195` — STEP 1's COMMUNICATION PANEL,
      // SENT FOR THE FIRST TIME** (`DEF-CUS-7863` named it among the ten facts
      // that never reached the server). `null` for an unpicked language, which
      // the accounts door stores as *no preference* — never English.
      preferred_language:
        draft.communication.language.trim() === "" ? null : draft.communication.language.trim(),
      paperless: draft.communication.paperlessBill,
      sms_reminders: draft.communication.smsReminders,
      // ⊕ **`DEF-CUS-9830` (PO ruling 2026-10-06, option (a)) — THE
      // CO-APPLICANT IS SENT, AND SAVED AS A CO-OWNER ON THE NEW ACCOUNT**,
      // in move-in's own word (`co_owners`) so the server's one writer of
      // that record takes her. Only her name is required; every other fact
      // is sent only when typed (`null` for a blank, which the server stores
      // as *not given*). A request's co-applicant (`DEF-CUS-9828`) is this
      // same panel, prefilled, and travels the same way.
      // ⊕ lane CF-1 (2026-10-18) — the shared co-owner CARDS, one row each.
      ...draftCoOwnersPayload(draft),
      // ⊕ lane CF-1 — `DEF-CUS-10222`, where the bill goes, and the shared
      // form's *Contact by* and government ID (written on the contact).
      ...ownerMailingAddresses(draft),
      ...ownerContactFacts(draft.owner),
      // ⊕ lane CF-1 — Move-in's exemption certificate and discount claims.
      ...ownerMoveInExtras(draft),
    },
    quote_total: quoteTotal,
    occupancy: draft.occupancy,
    // ⚠ **CR-070 wave E — WHAT STEP 6 LEFT STANDING, AND IT TRAVELS AS
    // TEMPLATE IDS AND VERSIONS.** `BR-WRK-008` is *copy, never link*: the
    // order takes its own copy of the template's rows when it is raised, and
    // the VERSION is what says which copy. So the commit names both, and the
    // server raises the orders inside the same transaction as the build
    // (`BR-MET-112` — nothing until step 8).
    //
    // ⚠ The caller has to hand in the surviving proposal: this function reads
    // the DRAFT, and the proposal itself is a server read that the draft
    // deliberately does not copy (see `removedWorkOrderTemplateIds`).
    // ⊕ `DEF-MET-9223` — and each on the unit the clerk chose.
    work_orders: commitWorkOrdersOf(draft, proposed ?? []),
    // ── STEP 6's THREE QUOTE FIELDS, SENT FOR THE FIRST TIME
    //    (`DEF-CUS-5485`) ────────────────────────────────────────────────────
    //
    // ⚠ **THE COMMIT HAS ACCEPTED ALL THREE SINCE `CR-109` AND NOTHING SENT
    // THEM**, which is why the proved money path — invoice `BL-2609-000082` at
    // `$800.00`, `DR 1200` against `CR 4600 $270.00` and `CR 4630 $530.00`,
    // observed on real PostgreSQL — was unreachable from the product. Hard-won
    // law 2: an engine nothing passes anything to is not a feature.
    //
    // ⚠ **`null` RATHER THAN A DEFAULT ON EVERY ONE.** `quote_due_days` absent
    // makes the server report `quote_payment_terms_not_captured` and commit the
    // build anyway; a number invented here would start a late-fee clock on a
    // real invoice. `quote_posting_date` absent makes the server use the day
    // the clerk pressed commit, which is ITS documented fallback, not ours.
    quote_payer: draft.quotePayer,
    quote_due_days:
      draft.quoteDueDays.trim() === "" ? null : Number(draft.quoteDueDays.trim()),
    quote_posting_date: draft.quotePostingDate === "" ? null : draft.quotePostingDate,
    // ── `BR-MET-1178` · THE BUILD'S OWN CHARGE LINES ──────────────────────
    //
    // ⚠ **THE QUANTITY IS COUNTED HERE AND NOWHERE ELSE, AT THE MOMENT OF THE
    // COMMIT.** p094, in red: *"Every quantity is counted from the services
    // grid, not typed. Six units, twenty service points, one premise — change
    // a tick on step 4 and these move with it."* The draft stores the CODE and
    // the BASIS; the number comes from `buildChargeQuantities`, which reads
    // step 4. A number stored beside the code would freeze a count step 4 is
    // still free to change.
    //
    // ⚠ **A LINE THAT COUNTS NOTHING IS NOT SENT.** The server refuses a zero
    // BY NAME — a line priced `$0.00` prints on a real customer's bill as a
    // charge that was free — so the screen drops it rather than making the
    // clerk read a refusal about a line they cannot see the count of.
    quote_lines: quoteLinesOf(draft),
    // ── `BR-MET-1187` · THE PAYMENT TAKEN AT THE COUNTER ──────────────────
    //
    // ⚠ **THE SERVER HAS TAKEN THESE SINCE `2.391.0` AND THE WIZARD SENT
    // NONE OF THEM** (`DEF-CUS-7611`), so a clerk holding a cheque had to key
    // it twice — once here and once on Record a payment — and the build's own
    // Charges tab showed nothing taken. Hard-won law 2: an engine nothing
    // passes anything to is not a feature.
    //
    // ⚠ **`payment_date` IS THE POSTING DATE THE STEP ALREADY COLLECTS, AND
    // THERE IS DELIBERATELY NOT A SECOND DATE BOX.** p096 draws ONE *Posting
    // date* inside *Taking the money now* and the screen already has it; the
    // server's own rule is the same one — *"THE PAYMENT'S DATE FALLS BACK TO
    // THE CHARGE'S POSTING DATE AND NOT TO A CLOCK … they are one event"*
    // (`BR-TEN-043`, `G6`). Sent explicitly rather than left to that fallback
    // so the wire says what the screen means.
    //
    // ⚠ **AND NOTHING HERE SENDS A TOTAL.** The amount is the clerk's own
    // string, unparsed and unrounded; hard rule 2 rounds once, on the server
    // (`DEF-088`, `DEF-127`).
    ...paymentTakenOf(draft),
    // ── `CR-150-BRC09` task 13 · THE MESSAGES TABLE, FOLDED INTO REVIEW ───
    //
    // ⚠ **`queue_on_commit` HAS TAKEN THIS ARGUMENT SINCE THE MESSAGES WERE
    // BUILT AND NO CALLER EVER FILLED IT.** `commit_connection` passes
    // `data["messages"]` into it unchanged, and the door's own docstring
    // calls it *"step 7's slice of the commit payload — the clerk's ticks and
    // their template picks"*. There was no slice, so the step rendered its
    // three ticks DISABLED on the reasoning that nothing chosen there could
    // travel. **That was true of the WIRE and never of the DOOR.**
    //
    // ⚠ **SUBTRACTIONS ONLY.** An absent code means the occasion's own
    // `send_by_default`, which is what the PO ruled and what the drawing
    // draws.
    messages: messageChoicesOf(draft),
  };
}

/**
 * **WHAT THE CLERK DID TO THE MESSAGES TABLE, IN THE DOOR'S OWN SHAPE.**
 *
 * ⚠ **IT IS A FUNCTION FOR THE REASON `paymentTakenOf` IS ONE** — the Review
 * step shows the same answer it is about to send, and two spellings of one
 * payload is a screen showing a clerk something the commit will not do
 * (`DEF-MET-5428`).
 *
 * ⚠ **`send` HOLDS ONLY `false` ENTRIES.** `_fire_one` reads an absent code
 * as the occasion's default, so listing the kept ones would add nothing and
 * would freeze today's three against a server tuple free to grow.
 */
export function messageChoicesOf(
  draft: NewConnectDraft,
): { send?: Record<string, boolean>; templates?: Record<string, string> } {
  const send: Record<string, boolean> = {};
  for (const code of draft.messagesOff) {
    send[code] = false;
  }
  const out: { send?: Record<string, boolean>; templates?: Record<string, string> } = {};
  if (Object.keys(send).length > 0) {
    out.send = send;
  }
  if (Object.keys(draft.messageTemplates).length > 0) {
    out.templates = { ...draft.messageTemplates };
  }
  return out;
}

/**
 * **THE FIVE PAYMENT KEYS, OR NONE AT ALL — `BR-MET-1187`, `PAYMENT_FIELDS`.**
 *
 * ⚠ **`takePayment: "none"` SENDS NOTHING RATHER THAN NULLS.** The server's
 * `_payment_taken_at_the_counter` returns `None` when neither a tender nor an
 * amount is stated and refuses *"an amount with no tender"* and *"a tender
 * with no amount"* by name — so a half-filled block that the clerk then
 * switched back to *No payment now* must not reach it. The state is cleared on
 * the screen too, and both together are what stop a hidden field from posting
 * (the `RecordPaymentPage` rule, one screen over).
 *
 * ⛔ **`payment_cleared_date` IS NEVER SENT (DEF-CUS-10324, CR-186-BRC10).**
 * The payment is `posted` at entry; only bank reconciliation clears it, and
 * the server no longer reads the key.
 *
 * ⚠ **`payment_memo` IS NOT SENT BECAUSE NO BOX ON THIS STEP COLLECTS ONE.**
 * p096 draws *Take payment · Method · Reference · Amount taken · Posting date
 * · Clearing date* and no memo (its *Clearing date* is retired by CR-186, a
 * ruling over the drawing); a key sent from a field that does not exist
 * would be a value nobody typed. The server takes it and will take it the day
 * the drawing asks for one.
 */
export function paymentTakenOf(
  draft: NewConnectDraft,
): Partial<Pick<CommitPlan, "payment_method" | "payment_amount" | "payment_date" | "payment_reference">> {
  if (draft.takePayment !== "deposit") {
    return {};
  }
  return {
    payment_method: draft.paymentMethod === "" ? null : draft.paymentMethod,
    payment_amount: draft.paymentAmount.trim() === "" ? null : draft.paymentAmount.trim(),
    // ⚠ **THE CLERK'S OWN DATE WHERE THEY GAVE ONE, THE CHARGE'S OTHERWISE.**
    // `step4-charges.png` draws a *Payment date* beside the tender, and the
    // server has always taken `payment_date` as its own key. Left blank this
    // falls back to the posting date, which is byte-for-byte what this
    // function sent before the box existed (`BR-TEN-043`, `G6`).
    payment_date:
      draft.paymentDate !== ""
        ? draft.paymentDate
        : draft.quotePostingDate === ""
          ? null
          : draft.quotePostingDate,
    payment_reference: draft.paymentReference.trim() === "" ? null : draft.paymentReference.trim(),
  };
}

/**
 * **THE BUILD'S CHARGE LINES, IN THE SHAPE THE SERVER TAKES.**
 *
 * ⚠ **IT IS A FUNCTION RATHER THAN SIX LINES INSIDE `commitPlanOf` BECAUSE
 * STEP 6 NOW ASKS THE SAME QUESTION (`DEF-CUS-6115`).** The screen previews
 * what the build will cost by posting these lines to
 * `POST /connections/quote-preview`, and the commit posts the identical lines
 * to `POST /connections/commit`. **Two spellings of one payload is a screen
 * showing a clerk a figure the commit will not raise** — `DEF-MET-5428`'s shape
 * on a money path — so there is exactly one.
 *
 * ⚠ **THE QUANTITY IS COUNTED FROM STEP 4 AT THE MOMENT IT IS ASKED FOR**, and
 * never stored beside the code: p094, in red, *"Every quantity is counted from
 * the services grid, not typed … change a tick on step 4 and these move with
 * it."* A number frozen on the draft would be one step 4 is still free to
 * change underneath.
 *
 * ⚠ **A LINE THAT COUNTS NOTHING IS NOT SENT**, on either path. The server
 * refuses a zero by name — a line priced `$0.00` prints on a real customer's
 * bill as a charge that was free — so the screen drops it rather than making
 * the clerk read a refusal about a line whose count they cannot see.
 */
export function quoteLinesOf(draft: NewConnectDraft): CommitPlan["quote_lines"] {
  const quantities = buildChargeQuantities(draft);
  return draft.quoteLines
    .map((line) => ({
      charge_code: line.chargeCode,
      quantity: quantities[line.basis],
      basis: line.basis,
    }))
    .filter((line) => line.quantity > 0);
}

/**
 * **WHAT EACH BASIS COUNTS ON THIS BUILD — p094's QTY column.**
 *
 * ⚠ **IT IS DEFINED HERE RATHER THAN ON THE SCREEN BECAUSE BOTH THE SCREEN AND
 * THE COMMIT NEED IT.** `NewConnectChargesStep.quoteCounts` answers the same
 * three numbers for the table a clerk reads; this is the same arithmetic for
 * the payload, keyed by the BASIS strings billing spells. Two spellings of one
 * count is `DEF-MET-5428`'s shape — a screen showing itself a figure the server
 * never received — so the screen reads THIS.
 */
export function buildChargeQuantities(draft: NewConnectDraft): Record<BuildChargeBasis, number> {
  const units = draftUnits(draft);
  const services = draftUnitServices(draft);
  let meters = 0;
  for (const unit of units) {
    for (const service of services[unit.label] ?? []) {
      if (takesAMeter(service)) {
        meters += 1;
      }
    }
  }
  return {
    // The drawn caption is *"Six units, twenty service points, one premise"* on
    // a build of six dwellings plus a common area — so `per unit` counts the
    // DWELLINGS and the common area has its own `per premise` line.
    "per unit": units.filter((unit) => !unit.isCommonArea).length,
    "per meter": meters,
    "per premise": units.length > 0 ? 1 : 0,
  };
}
