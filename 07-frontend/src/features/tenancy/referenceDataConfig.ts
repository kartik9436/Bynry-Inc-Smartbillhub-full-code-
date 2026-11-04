// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-009 · US-TEN-010 · US-TEN-011 (EP-TEN-07 §Stories)  Screens: S8 (Reference data),
//           S63 (Holiday calendar), S64, S66, S69, S70, S71 (rule cards)
//           AMENDED 2026-08-15 (tenant custom-fields lane): US-TEN-014 (EP-TEN-09 — the Custom fields card, kind "custom": BR-TEN-047
//           puts it in this grid and mints no new screen ID, but its resource is not a lookup list)
// Rules:    BR-SHL-035 (EVERY Reference-data item is a CARD whose management view uses the same shell —
//           a rule page is a card whose view happens to be a FORM, never a differently-shaped screen) ·
//           BR-TEN-029 (card counts computed live) · BR-TEN-031 (tenancy renders; the OWNING module
//           validates and writes) · BR-TEN-036 (seeded + tenant-extensible lists) · BR-TEN-037 (tax
//           jurisdictions are tenant-entered) · BR-TEN-033 (the templates card is navigation only) ·
//           BR-TEN-039 · BR-TEN-041 (the rule cards S63/S64/S66/S69/S70/S71) · BR-AST-043 (meter types
//           and read methods are separate lists)
//           AMENDED 2026-08-28 (DEF-203): BR-PAY-850 — the tenant's own BANK ACCOUNTS are a card in this
//           grid (PO 2026-08-28, *"capture bank account in configure. Keep them in section which is
//           logical"*), owned and written by payments; its detail slot is the display mask, never an
//           account number.
//           AMENDED 2026-08-17 (CR-004 task A3): BR-TEN-078 — a lookup row may carry a utility-service
//           scope where NULL means "All services", and `uoms` is the ONLY list that uses it. The card
//           declares it with `serviceScoped`; the column is never derived from the payload.
// ───────────────────────────────────────────────────────
// THE CONFIG. BR-SHL-035's "new reference data = a new card + its config, never
// a new layout" is only true if adding a card is data — so every card in the
// grid is a row here and there is exactly one management view (SettingsReference
// Data.tsx) that reads it.
//
// Three kinds of card, one shell:
//   · kind "list"  — the ONE config-driven list view (US-TEN-010/011) serves it.
//                    `detailField` names the OWNING module's extra column; the
//                    framework renders it, the owner validates it (BR-TEN-031).
//   · kind "rules" — a rule page (S63/S64/S66/S69/S70/S71). It renders in the
//                    SAME frame with the same back-link/header/save/audit line;
//                    only the body is a form instead of a table.
//   · kind "link"  — navigation only (BR-TEN-033 Document & message templates).
//   · kind "custom" — the TENANT'S OWN field definitions (EP-TEN-09). BR-TEN-047
//                    puts them inside this framework ("follow same UI structure
//                    of Reference data") and no new screen ID is minted, but the
//                    resource is NOT a lookup list: a definition has an entity, a
//                    data type, options and a placement map, and it has no
//                    `code`/`used_by` at all. So it is its own kind with its own
//                    body inside the SAME frame, rather than a lookup list
//                    pretending to be something it is not.
//
// A card is NOT a claim that data exists. `GET /lookups` returns only the lists
// whose owning lane has landed, and the grid renders the intersection of that
// answer with this config — so a list the server does not serve simply is not
// drawn, and a config row the server does serve renders with its live count.
// Cards the server cannot serve at all yet (today: account statuses and types,
// whose module owns no tables) carry `arrivesWithKey` and render the honest
// state inside the same frame instead of a form that posts nowhere. The five
// S64–S71 rule pages no longer do: their endpoints landed, so they open as
// forms — in that same frame, through settingsRulePages.ts.

import type { LookupCardState } from "../../api/endpoints";

export type ReferenceCardKind = "list" | "rules" | "link" | "custom";

export interface ReferenceDetailColumn {
  /** The owning module's field on the serialized row (BR-TEN-031). */
  field: string;
  labelKey: string;
  /**
   * DEF-TEN-8754 — a field whose stored value is a fixed code (`behind_the_meter`)
   * is shown through the catalogue key `<prefix><value>`; a value with no key
   * falls back to itself, so a new code is never hidden. B14 rule 31.
   */
  valueLabelKeyPrefix?: string;
}

/**
 * r10 SET-04 files every card under a MODULE heading. The group is presentation
 * and belongs here rather than on the server: `GET /lookups` answers
 * `{list, owner, count}`, and **owner is not the group** — `reason_codes` is
 * owned by billing (BR-TEN-031) while r10 files it under Plans & Rates, and
 * `uoms` is owned by tenancy and files under Platform-wide. Deriving the
 * heading from `owner` would put four cards in the wrong section.
 */
export type ReferenceCardGroup =
  | "platform"
  | "plansRates"
  | "premises"
  | "assets"
  | "accounts"
  | "reads"
  | "billing"
  | "payments"
  | "work"
  | "finance"
  // `CR-142-BRC07` `P4.6`/`P5.5` — the drawing's eleventh heading (p047
  // legend ④). It sits LAST because that is where the blueprint draws it,
  // under FINANCE, and because a section a utility configures once belongs
  // after the lists it uses every day.
  | "reports";

/** The heading order r10 draws them in. */
export const REFERENCE_GROUP_ORDER: readonly ReferenceCardGroup[] = [
  "platform",
  "plansRates",
  "premises",
  "assets",
  "accounts",
  "reads",
  "billing",
  "payments",
  "work",
  "finance",
  "reports",
];

/**
 * `DEF-TEN-4478` — the words a SELF-PARENTED list uses for its own two levels.
 *
 * A list like `areas` holds two different things and one screen makes both, so
 * the Add dialog has to ASK which. Every string that answer changes lives here
 * rather than in the view, for `parentList`'s reason: a hierarchy is a ruling
 * about ONE list, and its nouns are that list's own.
 *
 * ⚠ **FOUR TITLE KEYS AND NOT ONE WITH A `{{level}}` PARAMETER.** A title is a
 * sentence, and *"Add a sub-area"* is not *"Add"* + a noun in German, Japanese
 * or Hindi — the article, the case and the word order all move. B14 rule 35
 * says a catalogue is written in its own language rather than translated from
 * English, and a parameterised title makes that impossible to obey.
 */
export interface SelfParentedLevels {
  /** The chooser's own label — it names the question, not the answer. */
  chooseKey: string;
  /** The two segments, in order: the top level first. */
  topKey: string;
  subKey: string;
  /** The dialog title, which FOLLOWS the chooser (that is the whole defect). */
  addTopTitleKey: string;
  addSubTitleKey: string;
  editTopTitleKey: string;
  editSubTitleKey: string;
  /** The parent picker, which is drawn ONLY under the sub level and is
   *  REQUIRED there — so its placeholder asks for a choice and never offers
   *  "none". Blank is still what an Area sends; it is simply no longer a thing
   *  the person can pick by accident. */
  parentLabelKey: string;
  parentPlaceholderKey: string;
  parentRequiredKey: string;
  parentNoneAvailableKey: string;
  /** The *"· 3 sub-areas"* suffix on a top-level row's NAME, in this list's own
   *  noun. It is a plural key, so the catalogues hold `_one` and `_other`. */
  countKey: string;
}

export interface ReferenceCard {
  /** The server's list code (`GET /lookups` → `list`) or the rule page's id. */
  code: string;
  kind: ReferenceCardKind;
  /** r10 SET-04's module heading this card sits under. */
  group: ReferenceCardGroup;
  labelKey: string;
  /** The card's "sample values" line — copy, so it is a catalog key. */
  sampleKey: string;
  /** Which module owns content + validation (BR-TEN-031), for the frame header. */
  owner: string;
  /** kind "list": the list-specific third column, when the owner serves one. */
  detailField?: ReferenceDetailColumn;
  /**
   * CR-004 task A3 · BR-TEN-078 — this list's rows carry a UTILITY SERVICE
   * scope, so the list view draws r10 SET-04's **Utility service** column.
   *
   * OPT-IN, ONE FLAG PER CARD, and deliberately NOT derived from the payload.
   * Three reasons, each of which has already cost something:
   *
   * 1. **A list that publishes no `service` key is not service-scoped, and
   *    ABSENT is a different fact from `null`.** `LookupEntry.service` is typed
   *    `?: LookupServiceRef | null` for exactly that reason: absent means "this
   *    list has no scope at all", `null` means the VALUE "All services". Deriving
   *    the column from `rows.some(r => r.service !== undefined)` collapses the
   *    two — and would then have to guess what an unscoped list's blank cell
   *    means. A blank column reads as "no value", which is a claim.
   * 2. **A derived column flickers.** The rows arrive per page, so a list whose
   *    first page happened to publish no scope would gain a column on page two.
   *    A column is part of the SCREEN's contract (BR-SHL-013 keeps identity
   *    columns fixed); it cannot depend on which rows loaded.
   * 3. **The scope is a RULING, not a shape.** BR-TEN-078 (PO 2026-08-17,
   *    *"I have clariffied - already - dont attached them to service"*) scoped
   *    exactly ONE list — `uoms` — and it is **TWO since 2026-09-02**:
   *    `service_size_classes` joined it when the PO reversed that ruling for
   *    that one list (CR-065, *"in Setting a capacity needs to tags to utility
   *    services ."*, sent with a screenshot of the Fire rate schedule pricing
   *    *Electric CT-metered*). Nine more are CONFIRMED unscoped and the rest are
   *    unruled and unscoped by default, because switching a list on later is one
   *    line while switching it off after tenants have entered scoped data is a
   *    migration. **This flag is what made that a one-line change, which is the
   *    whole argument for it** — a derivation would have turned a backend lane
   *    adding a column into a screen change nobody asked for.
   *
   * r10's own SET-04 draws the column on EVERY sub-screen, and its values for
   * the other lists come from a regex over the row text (`SVC_GUESS` in the
   * prototype source), not from data. That is prototype scaffolding, not a
   * requirement — the design is the layout, the ruling is the law.
   */
  serviceScoped?: true;
  /**
   * `CR-162-BRC10` (PO 2026-10-02, verbatim: *"we will need this on screen in
   * setting so user can provide the it and set it"*, reframed the same day:
   * *"when we say premises type has account type - master or regular attached
   * … then when you create account dont you want to use this field when you
   * are creating accounts"*) — the premises-type list carries an ACCOUNT TYPE
   * per row, *Master account* or *Regular account*. The table draws an
   * "Account type" column and the Add / Edit form asks it, REQUIRED with no
   * default; the server refuses a blank (`metering.lookups.
   * account_kind_required`). A FLAG on the one card that has it, for
   * `serviceScoped`'s reason: a column is a ruling about one list, never
   * sniffed from a payload.
   */
  accountKind?: true;
  /**
   * `CR-187-BRC10` (PO answer 9, 2026-10-21: a job MAY be pushed as urgent or
   * emergency automatically) — the work-priority card's rows carry a PUSH KIND:
   * how an assignment at that priority rings on the technician's phone. A
   * "Phone alert" column and a three-way choice on Add / Edit. A flag for
   * `accountKind`'s reason.
   */
  pushKind?: true;
  /**
   * `DEF-RAT-10220` (PO 2026-10-17) — the size-class card's rows carry a
   * CAPACITY for a service that sums: a "Capacity" column on the list, and a
   * "Capacity (kW)" field on Add / Edit drawn only when the chosen service
   * publishes a `capacity_uom`. A flag for `accountKind`'s reason.
   */
  capacity?: true;
  /**
   * `DEF-CUS-9808` — the card whose rows can be STOPPED from being offered on
   * new accounts while every existing record keeps them (`legacy`, BR-CUS-094's
   * third axis). PO ruling 2026-09-18 (OQ-CUS-12407 option a): any tenant admin,
   * any row, seeded rows included — which is how a utility that bills a school
   * district offers Government (and its Schools sub-type) again. A flag on the
   * one card that has the column, for `accountKind`'s reason.
   */
  legacyToggle?: true;
  /** kind "link": where the card navigates instead of opening a view. */
  target?: string;
  /**
   * Present = there is no endpoint behind this card yet. The management view
   * renders the honest state inside the SAME frame (BR-SHL-035) — never a form
   * that posts nowhere, never a faked count.
   */
  arrivesWithKey?: string;
  /**
   * BR-TEN-029 has no storage on this list: the owning table carries no
   * active/deleted_at column, so the server answers 409 BIZ-STATE
   * (`rating.lookups.deactivate_unsupported`) instead of recording nothing.
   * The row's Deactivate control therefore renders DISABLED WITH THE REASON
   * (BR-SHL-025) rather than as a live button that always fails.
   */
  deactivateUnsupportedKey?: string;
  /**
   * The owning module accepts CODE and NAME here and refuses every other field
   * as unknown — amounts, percents, rates and GL accounts belong to the money
   * screens (S12 charges, S13 taxes). The view says so, so the card is never
   * mistaken for a back door into B4-governed config (BR-TEN-031).
   */
  codeNameOnlyKey?: string;
  /**
   * BR-MET-066b · DEF-221 — this list is a TWO-LEVEL hierarchy, so its editor
   * offers a **Parent** picker and its table shows which rows are sub-areas.
   *
   * Exactly one card uses it (`areas`), and it is a FLAG for the same reason
   * `serviceScoped` is: a hierarchy is a RULING about one list, not a shape to
   * sniff out of a payload. r10's card is titled *"Areas & sub-areas"*, the
   * server has enforced two levels since CR-006 — `settings.areas.parent_self`,
   * `settings.areas.parent_is_sub_area`, `settings.areas.has_sub_areas` — and
   * for a day the ONLY thing missing was a control that sent `parent_code`.
   * Two dropdowns in the route wizard rendered `parent_name ? "A · B" : B` and
   * nothing in the product could ever produce a `parent_name`: a dead branch
   * the unwired-prop gate cannot see, because it reads props and this was data.
   *
   * ⚠ **IT CARRIES ITS OWN TWO WORDS SINCE `DEF-TEN-4478` (2026-09-07), AND
   * THAT IS WHY IT IS NO LONGER THE BARE `true`.** DEF-221 gave the list a
   * parent picker and stopped there, so the Add dialog was identical for both
   * halves of a card called *"Areas & sub-areas"* — same title, same fields,
   * same buttons — and the only thing separating them was one line of help
   * text above a dropdown. The PO opened it and said so: *"on add screen there
   * is not differnt whether Im addding area or sub areas"*. The fix is a
   * segmented **Area / Sub-area** chooser, and a chooser needs NOUNS. Putting
   * them here rather than in the view is `parentList`'s own argument one flag
   * along: a second self-parented list would need four different sentences and
   * a hard-coded default would silently give it areas' words.
   *
   * `parentList`'s cards get NO chooser and that is deliberate — there the
   * parent is REQUIRED (`customers.lookups.parent_required`), so there is no
   * second thing to choose between and a two-segment control offering one real
   * answer would be a control that lies.
   */
  hierarchical?: SelfParentedLevels;
  /**
   * CR-010 (PO 2026-08-17, "Part-10 confirmations" 10.0) — this list is the
   * SECOND level of a two-level tree whose PARENT rows live in **another
   * list**. Exactly one card uses it (`account_subtypes`, parents =
   * `account_types`).
   *
   * It is `hierarchical`'s sibling, not its replacement: `areas` keeps its
   * self-parenting flag untouched, because its parents are its OWN top-level
   * rows and its copy ("Parent area", "None — this is a top-level area") is
   * area-law. A cross-list tree needs FOUR different sentences — the parent
   * column is "Account type", the picker has no honest "none" (the ratified
   * tree is two-level, so the server REQUIRES a parent on every new or edited
   * row: `customers.lookups.parent_required`) — so the keys ride the config
   * rather than a second hard-coded set in the view. The mechanism in the ONE
   * view is shared: same Parent column reading the server's `parent_name`,
   * same picker sending `parent_code`, only the source list and the words
   * change.
   */
  parentList?: {
    /** The list whose rows the Parent picker offers (`GET /lookups/{code}`). */
    code: string;
    /** The parent column's and picker's label. */
    labelKey: string;
    /** Picker placeholder — worded for a REQUIRED parent, never "none". */
    placeholderKey: string;
    /** Help under the picker. */
    helpKey: string;
    /** Shown when the parent list served no offerable row. */
    noneAvailableKey: string;
  };
}

/**
 * The card grid, in A1's order: the prototype's eight, the A2 r4 asset lookups,
 * the BR-AST-043 split of meter types vs read methods, then the BR-TEN-039 /
 * BR-TEN-041 rule cards.
 */
export const REFERENCE_CARDS: readonly ReferenceCard[] = [
  {
    code: "uoms",
    group: "platform",
    kind: "list",
    labelKey: "settings.reference.card.uoms",
    sampleKey: "settings.reference.sample.uoms",
    owner: "tenancy",
    // BR-TEN-078: the ONLY service-scoped list today. `UomLookupHandler`
    // publishes `service: {id, code} | null` on every row and no other handler
    // publishes the key at all — so this flag and that serializer are one
    // statement, made in two places. Adding it to a second card without the
    // owning handler publishing `service` would draw an empty column.
    serviceScoped: true,
  },
  {
    code: "charge_codes",
    group: "plansRates",
    kind: "list",
    labelKey: "settings.reference.card.charge_codes",
    sampleKey: "settings.reference.sample.charge_codes",
    owner: "rating",
    // rating's handler landed: its serialized detail slot is what KIND of
    // charge the row is. The money fields are deliberately NOT here — they
    // live on S12, which is what `codeNameOnlyKey` tells the user.
    detailField: { field: "charge_type", labelKey: "settings.reference.col.chargeType" },
    codeNameOnlyKey: "settings.reference.codeNameOnly.charges",
  },
  {
    code: "tax_jurisdictions",
    group: "plansRates",
    kind: "list",
    labelKey: "settings.reference.card.tax_jurisdictions",
    sampleKey: "settings.reference.sample.tax_jurisdictions",
    owner: "rating", // BR-TEN-037: tenant-entered, not a global registry
    // The jurisdiction's own detail: which level of government it is (S13).
    detailField: { field: "level", labelKey: "settings.reference.col.level" },
    codeNameOnlyKey: "settings.reference.codeNameOnly.taxes",
    // `tax_jurisdictions` has no active column at all, so deactivation is a
    // 409, not a state change. Offering the control would be offering a
    // dead one.
    deactivateUnsupportedKey: "settings.reference.deactivateUnsupported",
  },
  // CR-166-BRC10 (PO 2026-10-03): the three discount dropdowns, editable per
  // utility — *"Program owner - make this drop down"*, *"Exclusivity group -
  // can you make this drop down"*, *"Who qualifies * - drop down"*. Rating
  // owns content and validation (`apps/rating/discount_lists.py`).
  {
    code: "discount_program_owners",
    group: "plansRates",
    kind: "list",
    labelKey: "settings.reference.card.discount_program_owners",
    sampleKey: "settings.reference.sample.discount_program_owners",
    owner: "rating",
  },
  {
    code: "discount_exclusivity_groups",
    group: "plansRates",
    kind: "list",
    labelKey: "settings.reference.card.discount_exclusivity_groups",
    sampleKey: "settings.reference.sample.discount_exclusivity_groups",
    owner: "rating",
  },
  {
    code: "discount_eligibility",
    group: "plansRates",
    kind: "list",
    labelKey: "settings.reference.card.discount_eligibility",
    sampleKey: "settings.reference.sample.discount_eligibility",
    owner: "rating",
    // Ruling 3: a value a utility adds here is always *customer shows proof*;
    // the four *system checks* are seeded. The server serves `checked_by` on
    // each row; no column is drawn for it because r10 draws none (G14).
  },
  {
    code: "reason_codes",
    group: "plansRates",
    kind: "list",
    labelKey: "settings.reference.card.reason_codes",
    sampleKey: "settings.reference.sample.reason_codes",
    owner: "billing",
  },
  {
    code: "payment_methods",
    group: "payments",
    kind: "list",
    labelKey: "settings.reference.card.payment_methods",
    sampleKey: "settings.reference.sample.payment_methods",
    owner: "payments",
  },
  // DEF-203 · PO ruling 2026-08-28, verbatim: *"capture bank account in
  // configure. Keep them in section which is logical"*. The logical section is
  // this grid: a tenant-maintained named list with an active flag, deactivated
  // and never deleted (BR-TEN-034's shape). `bank_accounts` had a model, a
  // unique key, an RLS policy and TWO readers and NO writer anywhere, so bank
  // reconciliation could not run for any real tenant — the only creator in the
  // repo was a test fixture, which is exactly what hid it.
  //
  // BR-SHL-035 makes this DATA: a card + its config, never a new layout, and
  // NO new screen ID is minted. The detail slot is the display MASK — the last
  // digits a person recognises in *"Chase Operating ••4021"*. It is
  // deliberately NOT the account number and the owning module refuses a fifth
  // digit: B2 §6's posture is that a column you do not store cannot leak.
  //
  // The card starts EMPTY on every tenant and that is correct — nobody but the
  // utility knows what their accounts are called, so nothing seeds it
  // (`UNSEEDABLE_REFERENCE_LISTS`, with the reason written out).
  {
    code: "bank_accounts",
    group: "payments",
    kind: "list",
    labelKey: "settings.reference.card.bank_accounts",
    sampleKey: "settings.reference.sample.bank_accounts",
    owner: "payments", // BR-TEN-031: payments owns the table, so payments writes
    detailField: { field: "mask", labelKey: "settings.reference.col.mask" },
  },
  {
    code: "meter_types",
    group: "assets",
    kind: "list",
    labelKey: "settings.reference.card.meter_types",
    sampleKey: "settings.reference.sample.meter_types",
    owner: "metering",
  },
  {
    code: "read_methods",
    group: "reads",
    kind: "list",
    labelKey: "settings.reference.card.read_methods",
    sampleKey: "settings.reference.sample.read_methods",
    owner: "metering",
  },
  {
    code: "asset_types",
    group: "assets",
    kind: "list",
    labelKey: "settings.reference.card.asset_types",
    sampleKey: "settings.reference.sample.asset_types",
    owner: "assets",
    // BR-AST-004/009/042: `category` keys the S49 tab partition, so it is the
    // column that makes this list readable.
    detailField: {
      field: "category",
      labelKey: "settings.reference.col.category",
      valueLabelKeyPrefix: "assets.tab.",
    },
  },
  {
    code: "asset_statuses",
    group: "assets",
    kind: "list",
    labelKey: "settings.reference.card.asset_statuses",
    sampleKey: "settings.reference.sample.asset_statuses",
    owner: "assets",
    // BR-AST-031: every lifecycle stage maps to a behavior class.
    detailField: { field: "behavior_class", labelKey: "settings.reference.col.behaviorClass" },
  },
  // DEF-235 (2026-08-17): both cards carried `arrivesWithKey` — "Nothing is
  // stored for them yet" — for a WEEK after the W2 customers slice landed the
  // tables, the seeder and both live handlers (apps/customers/lookups.py
  // registers them from AppConfig.ready(); account_statuses is STRUCTURAL, so
  // it seeds even with the S111 toggle off). The claim and the fix lived in
  // different repositories of truth and nothing joined them; the frontend
  // placeholder pin test asserted the defect was correct. The keys are gone,
  // so both cards drive tenancy's existing `/lookups/{list}` endpoints like
  // every other live list. CR-010 item 3 orders this fix in as many words.
  {
    code: "account_statuses",
    group: "accounts",
    kind: "list",
    labelKey: "settings.reference.card.account_statuses",
    sampleKey: "settings.reference.sample.account_statuses",
    owner: "customers",
    // BR-CUS-055: every status maps to a billing behavior class.
    detailField: { field: "behavior_class", labelKey: "settings.reference.col.behaviorClass" },
  },
  {
    code: "account_types",
    group: "accounts",
    kind: "list",
    labelKey: "settings.reference.card.account_types",
    sampleKey: "settings.reference.sample.account_types",
    owner: "customers",
    legacyToggle: true,
  },
  // CR-010 ("Part-10 confirmations" 10.0, PO 2026-08-17: "add them") — the
  // tree's tenant-editable SECOND level, in the same Accounts group and the
  // same S8 frame as its read-only platform parents: the two cards together
  // are S65 "Account types & sub-types". Every row shows which type it sits
  // under (the Parent column), and the editor's picker offers the four
  // platform types — parents from ANOTHER list, which is what `parentList`
  // exists for.
  {
    code: "account_subtypes",
    group: "accounts",
    kind: "list",
    labelKey: "settings.reference.card.account_subtypes",
    sampleKey: "settings.reference.sample.account_subtypes",
    owner: "customers",
    parentList: {
      code: "account_types",
      labelKey: "settings.reference.col.parentType",
      placeholderKey: "settings.reference.parentTypeSelect",
      helpKey: "settings.reference.parentTypeHelp",
      noneAvailableKey: "settings.reference.parentTypeNoneAvailable",
    },
  },
  // `DEF-CUS-10445` (PO 2026-10-22) — the service request acknowledgement's
  // default target days, seeded 15 (*"Default 15 days"*, *"don't do any
  // hardcoding"*). A RULES card on the server's `service-requests` family;
  // TENANCY's because the number lives on `tenant_settings`, filed under
  // ACCOUNTS because service requests are an Accounts screen.
  {
    code: "service_requests",
    group: "accounts",
    kind: "rules",
    labelKey: "settings.reference.card.service_requests",
    sampleKey: "settings.reference.sample.service_requests",
    owner: "tenancy",
  },
  // EP-TEN-09 — appended after Account statuses/types, which is where the S8
  // capability row puts it ("fixed card order (appended after Account
  // statuses)"). Its count comes from the SAME `GET /lookups` answer as every
  // other card, so the grid stays one fetch (BR-TEN-029, live).
  {
    code: "custom_fields",
    group: "platform",
    kind: "custom",
    labelKey: "settings.reference.card.custom_fields",
    sampleKey: "settings.reference.sample.custom_fields",
    owner: "tenancy",
  },
  // CR-068 wave D (2026-09-04) — US-CWP-074. ⚠ **NOTHING IN THIS PRODUCT HAS
  // EVER MODELLED A PHYSICAL PLACE**: no office, branch, counter or location
  // row exists anywhere in the schema, so the RECORD is genuinely new. The
  // SCREEN is not — a card with a list and an editor behind it is the shape
  // this file already repeats twenty-odd times, which is exactly why the
  // story asks for a card here rather than a screen of its own.
  {
    code: "service_centres",
    group: "platform",
    kind: "rules",
    labelKey: "settings.reference.card.service_centres",
    sampleKey: "settings.reference.sample.service_centres",
    owner: "tenancy",
  },
  // ── The rule pages. Same card, same frame; the view is a form (BR-SHL-035) ──
  {
    code: "holidays",
    group: "platform",
    kind: "rules",
    labelKey: "settings.reference.card.holidays",
    sampleKey: "settings.reference.sample.holidays",
    owner: "tenancy",
  },
  // The five S64–S71 pages are LIVE: `GET|PUT /settings/{slug}` now exists for
  // each, so they open as forms in the SAME frame (BR-SHL-035) instead of
  // stating a gap. Their field law is settingsRulePages.ts; nothing about them
  // is a differently-shaped screen.
  {
    code: "read_validation",
    group: "reads",
    kind: "rules",
    labelKey: "settings.reference.card.read_validation",
    sampleKey: "settings.reference.sample.read_validation",
    owner: "metering",
  },
  // `CR-192-BRC10` (MQ-033 task 11) — PO, verbatim: *"3. Settings → Reads"*.
  // A utility's own meter-read FORMATS, under the READS heading beside the two
  // cards already there. A `kind: "link"` for `work_parts`' reason: the body is
  // a SCREEN — a paged list, a builder, versions — not a code-plus-name lookup.
  // `GET /lookups` never answers for it, so it draws no count (the number of
  // formats is the list's own fact, one click away).
  {
    code: "read_formats",
    group: "reads",
    kind: "link",
    labelKey: "settings.reference.card.read_formats",
    sampleKey: "settings.reference.sample.read_formats",
    owner: "metering",
    target: "/settings/reference-data/read-formats", // BR-TEN-033: navigation only
  },
  // DEF-MET-10609 — PO 2026-10-26, verbatim: *"yes do it"* — ONE list of
  // can't-read reasons for route readings AND job readings, here under READS
  // beside Read formats. A `kind: "link"` for the read formats' reason: the
  // body is a screen (paged list, add, rename, reorder, switch, delete).
  {
    code: "cant_read_reasons",
    group: "reads",
    kind: "link",
    labelKey: "settings.reference.card.cant_read_reasons",
    sampleKey: "settings.reference.sample.cant_read_reasons",
    owner: "metering",
    target: "/settings/reference-data/cant-read-reasons", // BR-TEN-033: navigation only
  },
  {
    code: "billing_defaults",
    group: "billing",
    kind: "rules",
    labelKey: "settings.reference.card.billing_defaults",
    sampleKey: "settings.reference.sample.billing_defaults",
    owner: "billing",
  },
  {
    code: "budget_billing",
    group: "billing",
    kind: "rules",
    labelKey: "settings.reference.card.budget_billing",
    sampleKey: "settings.reference.sample.budget_billing",
    owner: "billing",
  },
  {
    code: "collections_notices",
    group: "payments",
    kind: "rules",
    labelKey: "settings.reference.card.collections_notices",
    sampleKey: "settings.reference.sample.collections_notices",
    owner: "payments",
  },
  // ── CR-004 task C · FINANCE CONTROLS IS NOT A CARD HERE ANY MORE ────────
  // PO 2026-08-16, asked whether Finance controls had been dropped or moved:
  // *"this is moved to accounting tab"*. r10's SET-04 grid draws exactly one
  // card under its FINANCE heading — Import mappings — and no Finance controls
  // card, which is the same statement in the design.
  //
  // Only the ENTRY POINT moved. `FINANCE_CONTROLS_PAGE` and `RULE_PAGES` in
  // settingsRulePages.ts are untouched, the `GET|PUT /settings/finance-controls`
  // endpoint is untouched, and the page renders through the SAME `RulePageView`
  // it always did — now as a section of `SettingsAccountingTab.tsx` instead of a
  // card body inside `SettingsFrame`. Deleting the row here is therefore what
  // "moved" looks like in this file, and NOT a scope cut.
  //
  // A stale bookmark to `?list=finance_controls` is safe by the mechanism that
  // already existed: `referenceCard()` answers null for an unknown code and
  // `openCardFrom()` falls back to the grid (BR-SHL-011's spirit) — the same
  // path `?list=nonsense` takes. Nothing 500s and no empty frame is drawn.
  // ── CR-004: the six r10 SET-04 lists tenancy now hosts ──────────────────
  // Real cards, not placeholders: each has a table, a handler and a seeded
  // vocabulary, so `GET /lookups` returns a count and the ONE list view drives
  // full CRUD. `owner` names the module that owns CONTENT (BR-TEN-031), not
  // the module hosting the table — the card header shows the owner.
  {
    code: "areas",
    group: "platform",
    kind: "list",
    labelKey: "settings.reference.card.areas",
    sampleKey: "settings.reference.sample.areas",
    owner: "metering",
    // BR-MET-066b — the one hierarchical list. DEF-221: the card was named
    // "Areas & sub-areas" and no screen could create the second half.
    // DEF-TEN-4478: it could create both and said which in neither the title
    // nor any control, so the two nouns are declared here and the dialog is
    // built from them.
    hierarchical: {
      chooseKey: "settings.reference.level.choose",
      topKey: "settings.reference.level.area",
      subKey: "settings.reference.level.subArea",
      addTopTitleKey: "settings.reference.level.addArea",
      addSubTitleKey: "settings.reference.level.addSubArea",
      editTopTitleKey: "settings.reference.level.editArea",
      editSubTitleKey: "settings.reference.level.editSubArea",
      parentLabelKey: "settings.reference.col.parent",
      parentPlaceholderKey: "settings.reference.parentAreaSelect",
      parentRequiredKey: "settings.reference.parentAreaRequired",
      parentNoneAvailableKey: "settings.reference.parentNoneAvailable",
      countKey: "settings.reference.subAreaCount",
    },
  },
  {
    // RENAMED 2026-08-27 — BR-TEN-170. PO verbatim: *"it is utility service
    // size class"*. Four of the five services BR-TEN-171 adds have NO METER —
    // storm water is sized by the property, broadband by the tier bought,
    // solar by inverter capacity, battery by its rating — so the old name
    // could not hold them without lying about what it was sizing. The hosted
    // TABLE is still `meter_size_classes` (DEF-970); this is the name a
    // person meets.
    code: "service_size_classes",
    group: "plansRates",
    kind: "list",
    labelKey: "settings.reference.card.service_size_classes",
    sampleKey: "settings.reference.sample.service_size_classes",
    owner: "metering",
    // CR-065 (PO 2026-09-02): the SECOND scoped list. The Fire rate schedule
    // was offering Electric CT-metered, and the fix is the tag — set here, on
    // the row, so a size a tenant adds themselves can carry one too.
    serviceScoped: true,
    // DEF-RAT-10220 — and a size of a SUMMING service carries its capacity.
    capacity: true,
  },
  // DEF-236 / CR-010 item 2 (PO 2026-08-17: *"why no screen"*): premises
  // types had 5 seeded rows in every tenant from 2026-08-10 — BR-MET-034,
  // structural, required by the S16 wizard — and NO card anywhere, the only
  // reference list in the product with rows and no door. The handler is
  // apps/metering/lookups.py; the endpoint is tenancy's existing
  // /lookups/{list}; this entry is the door.
  {
    code: "premises_types",
    group: "premises",
    kind: "list",
    labelKey: "settings.reference.card.premises_types",
    sampleKey: "settings.reference.sample.premises_types",
    owner: "metering",
    // CR-162-BRC10 — the ACCOUNT TYPE a premises of this type takes.
    accountKind: true,
  },
  // CR-010 A-4 (PO 2026-08-17: "this is correct" on "Premise & unit types
  // (one card, two levels)") — the UNIT_TYPES tuple becomes editable rows
  // (BR-MET-084). r10 SET-04 draws ONE card for both vocabularies; here that
  // surface is the PREMISES group's two sibling cards, because the ONE list
  // view is one-list-per-card (BR-SHL-035) and the DEF-236 join guard pairs
  // every declared list with its own card — recorded as a build choice in the
  // decision log, 2026-08-18.
  {
    code: "unit_types",
    group: "premises",
    kind: "list",
    labelKey: "settings.reference.card.unit_types",
    sampleKey: "settings.reference.sample.unit_types",
    owner: "metering",
  },
  {
    code: "occupancy_statuses",
    group: "premises",
    kind: "list",
    labelKey: "settings.reference.card.occupancy_statuses",
    sampleKey: "settings.reference.sample.occupancy_statuses",
    owner: "metering",
  },
  {
    code: "device_types",
    group: "assets",
    kind: "list",
    labelKey: "settings.reference.card.device_types",
    sampleKey: "settings.reference.sample.device_types",
    owner: "metering",
  },
  {
    code: "certification_types",
    group: "assets",
    kind: "list",
    labelKey: "settings.reference.card.certification_types",
    sampleKey: "settings.reference.sample.certification_types",
    owner: "metering",
  },
  {
    code: "import_mappings",
    group: "finance",
    kind: "list",
    labelKey: "settings.reference.card.import_mappings",
    sampleKey: "settings.reference.sample.import_mappings",
    owner: "ledger",
  },
  // ── r10 SET-04 · WORK ────────────────────────────────────────────────────
  //
  // ⚠ **THE FOUR CARDS BELOW CARRIED `arrivesWithKey` FROM 2026-08-16 TO
  // 2026-09-04, AND THEY WERE TELLING THE TRUTH RIGHT UP TO THE DAY THEY
  // STOPPED.** The sentence they rendered — *"Field work is not part of this
  // release yet, so there is nothing to configure here"* — was correct, and
  // this block's own comment said why: *"no module in the map owns a work
  // order, a crew, a skill or a parts stock, so there is no table to host a row
  // and no owner to author a handler. That is OQ-249."*
  //
  // The Product Owner ruled on 2026-09-03 that Work *"will become the module
  // itself"*. `apps/work` is the eleventh code module, it owns all five tables
  // (`work/0001`, `US-WRK-007`–`010`) and it registers the handlers from its
  // own `AppConfig.ready()` — so the sentence would now be FALSE, and
  // `settings.reference.arrivesWith.work` is DELETED from all eleven
  // catalogues in the same commit that removes these four keys. A stated
  // absence outliving its cause is the failure `G38` exists for.
  //
  // **The block gains two cards and it still moves as one.** Work order types
  // (`WM-04`) is the fifth list; Parts is a `kind: "link"` because the register
  // is a SCREEN — six columns, its own segmented control — and not a
  // code-plus-name lookup. That is `BR-TEN-033`'s own precedent (the Document
  // & message templates card navigates and does not list), and it means one
  // parts register rather than a weaker second one inside a Settings modal.
  {
    code: "work_order_types",
    group: "work",
    kind: "list",
    labelKey: "settings.reference.card.work_order_types",
    sampleKey: "settings.reference.sample.work_order_types",
    owner: "work",
    // BR-WRK-017 · WM-04 — what a clerk needs to see beside the name is which
    // priority a job of this kind gets by default. The other three columns the
    // card names (estimated duration, customer-present, default template) have
    // no editor until the New work order wizard needs them (wave G) and the
    // first template exists (wave D); the card carries ONE detail by design
    // (BR-SHL-035's one management view), so it carries the one that decides
    // when the job is due.
    detailField: {
      field: "default_priority",
      labelKey: "settings.reference.col.defaultPriority",
    },
    // ⚠ **THE SECOND SELF-PARENTED LIST, AND THE ONE `DEF-TEN-4478`'s BLOCK
    // WAS BUILT FOR** (`BR-WRK-058`, PO ruling 2026-09-07). The Product Owner
    // rejected the eight flat rows this card shipped with — *"this is not
    // correct - you will ahve to think from all Utilty services point of
    // view"* — and supplied nine TYPES with eighteen SUB-TYPES beneath them,
    // then twenty-four more, one group per utility service.
    //
    // Every string here is this list's OWN noun. Inheriting areas' defaults
    // would have drawn *"Parent area"*, *"Add a sub-area"* and *"· 3
    // sub-areas"* over work order types — correct-looking, wrong, and
    // invisible to `tsc` and to every test, which is exactly why the words
    // moved onto the card the day a second list needed them.
    hierarchical: {
      chooseKey: "settings.reference.level.chooseWorkType",
      topKey: "settings.reference.level.workType",
      subKey: "settings.reference.level.workSubType",
      addTopTitleKey: "settings.reference.level.addWorkType",
      addSubTitleKey: "settings.reference.level.addWorkSubType",
      editTopTitleKey: "settings.reference.level.editWorkType",
      editSubTitleKey: "settings.reference.level.editWorkSubType",
      parentLabelKey: "settings.reference.col.parentWorkType",
      parentPlaceholderKey: "settings.reference.parentWorkTypeSelect",
      parentRequiredKey: "settings.reference.parentWorkTypeRequired",
      parentNoneAvailableKey: "settings.reference.parentWorkTypeNoneAvailable",
      countKey: "settings.reference.subTypeCount",
    },
  },
  {
    code: "work_priorities",
    group: "work",
    kind: "list",
    labelKey: "settings.reference.card.work_priorities",
    sampleKey: "settings.reference.sample.work_priorities",
    owner: "work",
    // BR-WRK-018 — a priority carries a PROMISE, and the promise is the column.
    // The server publishes `sla_hours` (the integer) and `sla_hours_text`
    // (*"4 h"*); the card names the text one because CLAUDE.md hard rule 3
    // wants the unit travelling with the number, and putting the "h" in the
    // front end would put it in eleven catalogues instead of one serializer.
    detailField: { field: "sla_hours_text", labelKey: "settings.reference.col.sla" },
    // CR-187-BRC10 — how an assignment at this priority rings on the phone.
    pushKind: true,
  },
  {
    code: "work_skills",
    group: "work",
    kind: "list",
    labelKey: "settings.reference.card.work_skills",
    sampleKey: "settings.reference.sample.work_skills",
    owner: "work",
  },
  {
    code: "work_safety_kits",
    group: "work",
    kind: "list",
    labelKey: "settings.reference.card.work_safety_kits",
    sampleKey: "settings.reference.sample.work_safety_kits",
    owner: "work",
    // The kit's CONTENTS — one comma-separated line, which is how a person
    // writes a kit. `items` is the array underneath and the template builder's
    // safety step reads that (wave E).
    detailField: { field: "items_text", labelKey: "settings.reference.col.items" },
  },
  {
    code: "work_parts_categories",
    group: "work",
    kind: "list",
    labelKey: "settings.reference.card.work_parts_categories",
    sampleKey: "settings.reference.sample.work_parts_categories",
    owner: "work",
  },
  {
    // ⚠ NOT A LOOKUP LIST, AND THE CODE IS NOT A SERVER LIST CODE. `GET
    // /lookups` never answers for this card, so `referenceCardViews` renders
    // it with `state: "absent"` and no count — which is right: the number of
    // parts a utility holds is not a Settings fact, and the register that owns
    // it is one click away.
    code: "work_parts",
    group: "work",
    kind: "link",
    labelKey: "settings.reference.card.work_parts",
    sampleKey: "settings.reference.sample.work_parts",
    owner: "work",
    target: "/work/parts", // BR-TEN-033: navigation only
  },
  // ── REPORTS · `CR-142-BRC07` `P4.6` (drawing p047 legend ④) ─────────────
  //
  // ⚠ **TWO CARDS OF THE FOUR THE DRAWING SHOWS, AND THE OTHER TWO ARE NOT
  // HERE RATHER THAN HERE AND EMPTY.** p048's TASK row splits the section on
  // purpose — *"`P4.6` lands retention and the default format one phase
  // earlier, because Tab 3's expiry helper needs them and schedules cannot be
  // built without a format"* — and `Report groups` and `Delivery` are `P5.5`'s
  // half. Neither has a lookup handler today, and a card declared with no
  // endpoint draws a count nobody served (`arrivesWithKey` exists for an
  // honest promise, and a promise with no dated owner is what hard-won law 2's
  // mirror is about). They are tracked as `P5.5`'s remainder in
  // `CR-142-BRC07-reports-framework.md` §12.4.
  //
  // ⚠ **NEITHER CARD SHOWS A VALUE LINE, AND THE DRAWING DOES** — p047 draws
  // *"3 days"* under File retention and *"CSV"* under Default format. B14 rule
  // 37 makes a drawn figure an ILLUSTRATION, and the three rule cards this
  // product already ships (`billing_defaults`, `budget_billing`,
  // `read_validation`) show none. Drawing one here would mean the grid reading
  // five settings families to head five cards, and a tenant on seven days
  // would read *"3 days"* on the card and *"7"* inside it.
  {
    code: "file_retention",
    group: "reports",
    kind: "rules",
    labelKey: "settings.reference.card.file_retention",
    sampleKey: "settings.reference.sample.file_retention",
    // ⚠ **TENANCY, NOT REPORTS, AND THAT IS THE BOUNDARY ANSWER.** The number
    // governs `apps/tenancy/exports.ARTIFACT_RETENTION_DAYS` — the kernel every
    // list export in this product runs through, audit's and the platform's as
    // well as reports'. The REPORTS heading is presentation, exactly as
    // `reason_codes` is billing's and files under Plans & Rates.
    owner: "tenancy",
  },
  {
    code: "default_format",
    group: "reports",
    kind: "rules",
    labelKey: "settings.reference.card.default_format",
    sampleKey: "settings.reference.sample.default_format",
    owner: "tenancy",
  },
  // ── `BR-REP-044` · `CR-142-BRC07` `P5.5`'s fourth card (PO ruling
  //    2026-09-27, option (a) of two, answered *"a"*) ──────────────────────
  //
  // p075's data table draws this as a LIST — *"Delivery — Where a schedule
  // sends its file. A list, because a utility has more than one recipient."*
  // **It is a LINK instead, and that is the ruling rather than a shortcut.**
  // Recipients are stored PER SCHEDULE (`report_schedules.recipients`), never
  // per tenant: the AR ageing goes to Dana weekly and the cash report to the
  // finance officer monthly, so *"the utility's recipients"* is not a thing
  // that exists to list. Option (b) — a tenant-level recipient table — is
  // storage Phase 5's own mix excludes (**0 DB**). So the card points at
  // `4·1 Scheduled`, where the recipients actually live, and duplicates
  // nothing. That is `BR-TEN-033`'s precedent, the same one `templates` and
  // `work_parts` already stand on.
  //
  // ⚠ **DELIBERATELY NOT `arrivesWithKey`.** A *"coming soon"* card with no
  // dated owner is hard-won law 2's mirror with better manners, and
  // `retentionDoor.dom.test.tsx` held `referenceCard("delivery")` to NULL
  // precisely so the day it arrived the case would name itself. It did.
  {
    code: "delivery",
    group: "reports",
    kind: "link",
    labelKey: "settings.reference.card.delivery",
    sampleKey: "settings.reference.sample.delivery",
    // ⚠ REPORTS, unlike its two neighbours in this group. `file_retention` and
    // `default_format` are tenancy's because the numbers they govern live in
    // the platform export kernel; a report SCHEDULE is reports' own.
    owner: "reports",
    target: "/reports/scheduled", // BR-TEN-033: navigation only
  },
  {
    code: "templates",
    group: "billing",
    kind: "link",
    labelKey: "settings.reference.card.templates",
    sampleKey: "settings.reference.sample.templates",
    owner: "notifications",
    target: "/settings/templates", // BR-TEN-033: navigation only
  },
];

export function referenceCard(code: string): ReferenceCard | null {
  return REFERENCE_CARDS.find((card) => card.code === code) ?? null;
}

/**
 * Every card the ONE config-driven management view is responsible for.
 *
 * This deliberately INCLUDES cards carrying `arrivesWithKey`. Excluding them
 * was tried and reverted: `account_statuses` and `account_types` have carried
 * that key since 2026-08-09, so "exclude the ones with no endpoint" would have
 * silently reclassified two shipped cards while adding four new ones — a
 * change nobody asked for, hidden inside one nobody would question.
 * `placeholderCards()` below is the set that answers "which have no endpoint".
 */
export function listCards(): readonly ReferenceCard[] {
  return REFERENCE_CARDS.filter((card) => card.kind === "list");
}

/**
 * Cards DECLARED in the grid with no endpoint behind them yet.
 *
 * Pinned by its own assertion so this set cannot grow silently: a card added
 * here is a promise to the user that something is coming, and a card that
 * quietly LEAVES here without gaining a handler is a card that vanished from
 * the grid. Both should be somebody's deliberate act.
 */
export function placeholderCards(): readonly ReferenceCard[] {
  return REFERENCE_CARDS.filter(
    (card) => card.kind === "list" && card.arrivesWithKey !== undefined,
  );
}

/** The rule pages — same frame, form body (BR-SHL-035). */
export function ruleCards(): readonly ReferenceCard[] {
  return REFERENCE_CARDS.filter((card) => card.kind === "rules");
}

export interface ReferenceCardView {
  card: ReferenceCard;
  /**
   * BR-TEN-029: the live count from `GET /lookups`, or null when the server
   * serves no count for this card. Null renders the A18 empty-state line —
   * writing 0 would claim the list is empty, which is a different statement.
   */
  count: number | null;
  /**
   * ⚠ DEF-336. Null used to be ONE fact and it was really three, so the grid
   * drew a blank for two of them: a list nobody has set up, a card that holds
   * settings and has no list to count, and a list whose rows provably exist
   * where this screen cannot take the count (the server's `uncounted`, from
   * DEF-026). The PO photographed the BILLING section — three cards, three
   * bare chevrons — beside WORK's honest "Not set up yet" and read it as
   * missing configuration.
   *
   * `absent` means the server served no card at all for this config row.
   */
  state: LookupCardState | "absent";
}

/**
 * The grid the user sees: this config joined to the SERVER's card answer.
 * A config row the server does not serve keeps its place ONLY when it carries
 * an `arrivesWithKey` (an honest promise) or is a rule/link card; a list card
 * with neither is dropped, because drawing it would imply data that does not
 * exist. Order comes from the config, never from the server's array order.
 */
export function referenceCardViews(
  serverCards: readonly {
    list: string;
    count: number | null;
    state?: LookupCardState;
  }[],
): ReferenceCardView[] {
  const served = new Map(serverCards.map((card) => [card.list, card]));
  const views: ReferenceCardView[] = [];
  for (const card of REFERENCE_CARDS) {
    const row = served.get(card.code);
    if (row !== undefined) {
      // ⚠ DEF-336: the COUNT is carried whatever the card's kind is. It used to
      // be read only for `kind: "list"`, so `custom_fields` — which the server
      // has always counted — threw its number away at the last step and drew a
      // bare chevron. A count the server took is a fact about the tenant, not a
      // property of the card's shape.
      views.push({ card, count: row.count, state: row.state ?? "seeded" });
      continue;
    }
    if (card.kind !== "list" || card.arrivesWithKey !== undefined) {
      views.push({ card, count: null, state: "absent" });
    }
  }
  return views;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane) · AMENDED 2026-08-09 by story-coder (frontend integration lane: the five rule cards go live, the four dark catalog cards gain their owners' detail slots + refusal config) · AMENDED 2026-08-15 by story-coder (tenant custom-fields lane) · AMENDED 2026-08-16 by story-coder (CR-004 task C — the `finance_controls` card is REMOVED from this grid; PO: "this is moved to accounting tab", and r10 SET-04 draws only Import mappings under FINANCE) · AMENDED 2026-08-17 by story-coder (CR-004 task A3 — `serviceScoped` added to ReferenceCard and set on `uoms` ALONE, per BR-TEN-078; opt-in rather than derived because a list that publishes no `service` key is not service-scoped and ABSENT is a different fact from `null`) · AMENDED 2026-08-28 by story-coder (DEF-203 — the `bank_accounts` card, PO ruling *"capture bank account in configure"*; a `kind: "list"` row with the display MASK as its detail field, owned and written by payments per BR-TEN-031, and NO new screen ID minted)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 296 passed / 83 todo across 30 files✔ (239+72 baseline unchanged and green; this packet adds 57 passing + 11 todo — the todos are browser-interaction, server/RLS and unbuilt-neighbour-screen scope)
// exceptions: E4 [2026-08-16, CR-004 task C] `finance_controls` is GONE from REFERENCE_CARDS and `ruleCards()` is five, not six — the S71 page now opens as a SECTION of Settings → Accounting (SettingsAccountingTab.tsx), through the same RulePageView and the same `GET|PUT /settings/finance-controls`. `FINANCE_CONTROLS_PAGE`/`RULE_PAGES`/`rulePageForCard("finance_controls")` are deliberately UNCHANGED — only the entry point moved, so settingsRulePages.ts stays the single source of the field law · E4 the "finance" GROUP survives the removal because `import_mappings` still sits in it, which is exactly what r10 SET-04 draws (one card under FINANCE); had it emptied, `ReferenceCardGrid` already drops a heading with no cards · E3 S65 "Account types & sub-types" (BR-TEN-039) is carried as the `account_types` list card, since the customers module owns no tables yet — reported rather than modelled as a separate rule page · E4 `reason_codes` and `payment_methods` carry NO detail column because tenancy's hosted handler serializes code + name only (the owning lanes have authored no extra field) — a guessed column would render blank and read as "no value" (BR-TEN-031) · E3 `tax_jurisdictions` has no `code` column and no active column at all: the framework's code slot is served by the NAME, and deactivate answers 409 — both carried here as config (`codeNameOnlyKey`, `deactivateUnsupportedKey`) and surfaced by the ONE list view, per the backend's own reported gaps · E4 `charge_codes`/`tax_jurisdictions` cards mint and rename CODES only — the money fields are refused as unknown by the owner and stay on S12/S13, which the view states rather than silently dropping
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
