// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-018 · US-RBS-003 — CR-075 wave D tasks D3 and D4.
// Screens: RBS-002 (`S148`) Templates · RBS-003 (`S149`) My runbooks.
// Rules:   `07-endpoints.md` rows 1 and 4 · `BR-RBS-025` (a category with no
//          template is never drawn as a filter) · `TC-RBS-20` · `NFR-3`
//          (server pagination) · B14 rule 31 (no database id on screen).
// Defects: DEF-RBS-4284 (the engine and the renderer agreed on NAMES and
//          disagreed on every PAYLOAD, both suites green) — the reason every
//          field below is transcribed from `apps/runbooks/selectors.py` rather
//          than from a build sheet. DEF-RBS-4309 (the four facts RBS-002 draws
//          and the wire does not carry).
// ───────────────────────────────────────────────────────
// THE WIRE, EXACTLY AS `D1` SERVES IT — AND THE FOUR FACTS IT DOES NOT.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THESE TYPES WERE READ OFF THE SERVER AND NOT OFF THE BUILD SHEET
// ══════════════════════════════════════════════════════════════════════════
// `DEF-RBS-4284`: the engine's frozen report and wave C's renderer disagreed on
// ALL SIX payloads runbook 1 emits, with both suites green, because only the
// twelve block NAMES were ever checked. The same trap is one level up here — a
// screen that describes its own wire is checked against nothing. So every field
// below was transcribed from `selectors.templates_page` and
// `selectors.catalogue_page`, and `libraryEndpoints.ts` asserts the envelope at
// runtime rather than trusting these declarations.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ FOUR THINGS `RBS-002` DRAWS THAT `GET /runbooks/templates` DOES NOT SERVE
// ══════════════════════════════════════════════════════════════════════════
// Recorded as `DEF-RBS-4309`, filed BEFORE this file was written. Not invented
// here, in either direction — a front end that fills them in resolves an
// unstated design question by choosing a value, which is what `RB-020` (adding
// runbook 23 needs one Python module and NO frontend code) exists to prevent
// and what the wave C lane refused to do for *This can*.
//
//   1. **The card's one sentence** — *Finds what stops a bill run before it
//      starts.* `RunbookDefinition` declares no purpose field at all.
//   2. **The detail's step labels** — `RBS-002.2` draws *Pick one account per
//      plan · Price each one · Group by outcome*; the row serves `steps` as a
//      COUNT and nothing else.
//   3. **Reads** — *Accounts, plans, reads*. No `reads[]` declaration exists.
//   4. **Runs for** — *About 40 seconds*. No duration estimate exists.
//
// Each is typed as OPTIONAL below, so the day `D1` serves it the screen draws
// it with no frontend change — and until then an absent one draws **nothing at
// all**, never a dash and never a placeholder. That is the wave C lane's rule
// for `Step.why` and it is the same reason: a placeholder is indistinguishable
// from a real empty value, and it hides the gap this file exists to show.

/** The two kinds. `models.KINDS`. */
export type RunbookKind = "check" | "action";

/**
 * A template's state FOR THIS TENANT (`07-endpoints.md` row 4).
 *
 * ⚠ **`unavailable` IS SERVED BY NOTHING TODAY AND THAT IS AN ABSENCE, NOT A
 * BUG.** `selectors.templates_page` says so in its own docstring: a template is
 * unavailable when it needs a switched-off capability, which is a read through
 * the tenancy seam that no shipped runbook declares. It is in this union
 * because `RBS-002.1` draws that card (*Budget billing is switched off for
 * you*) and the branch must exist for the day the seam answers — not because
 * anything produces it now.
 */
export type TemplateState = "added" | "not_added" | "unavailable";

/** One row of `GET /runbooks/templates`. */
export interface TemplateRow {
  /** The registry key — `configuration_check`. **A key is not a database id**
   *  (B14 rule 31): it is the address a person can read, type and share, and it
   *  is what every route in `08-screen-layouts.md` is written with. The
   *  template's UUID is not on this interface, and a field that does not exist
   *  cannot be rendered by accident. */
  template_key: string;
  name: string;
  kind: RunbookKind;
  /** One of the sixteen (`models.CATEGORIES`) — a CODE, never drawn raw. */
  category: string;
  tags: string[];
  subject_type: string;
  unit_of_work: string;
  triggers: string[];
  /** How many steps it has. ⚠ **A COUNT, NOT THE LABELS** — see note 2 above. */
  steps: number;
  /** The write ports it holds. Empty for a Check, and `BR-RBS-002` makes that
   *  emptiness the safety promise rather than an omission. */
  ports: string[];
  writes_nothing: boolean;
  state: TemplateState;
  unavailable_reason: string | null;
  /** ⚠ **NOT SERVED TODAY** (`DEF-RBS-4309`, note 1). */
  description?: string | null;
  /** ⚠ **NOT SERVED TODAY** (`DEF-RBS-4309`, note 2). */
  step_labels?: string[];
  /** ⚠ **NOT SERVED TODAY** (`DEF-RBS-4309`, note 3). */
  reads?: string | null;
  /** ⚠ **NOT SERVED TODAY** (`DEF-RBS-4309`, note 4). */
  runs_for?: string | null;
}

/** One category chip, as the SERVER counted it.
 *
 *  ⚠ **THIS IS `TC-RBS-20` AND IT IS THE WHOLE POINT OF `RBS-002`.** The chips
 *  are built from the templates PRESENT and never from the fixed sixteen
 *  (`BR-RBS-025`): *a category with no runbook is never drawn as a filter*,
 *  because a chip that filters to nothing is dead UI (hard-won law 2). The
 *  counting is done once, in `selectors._template_category_chips`, so the
 *  number has ONE answer rather than one per screen — and no screen may count
 *  the rows it happens to be showing, because that is a page, not a library. */
export interface CategoryChip {
  category: string;
  count: number;
}

/** One kind chip — `all`, `check`, `action`, each with the server's count. */
export interface KindChip {
  kind: "all" | RunbookKind;
  count: number;
}

/** Everything `GET /runbooks/templates` puts on the wire beside the page.
 *
 *  ⚠ **THE CHIPS ARE SPREAD ONTO THE ENVELOPE, NOT RETURNED BESIDE IT** —
 *  `apps/runbooks/api.py` spells `{**_envelope(...), "category_chips": …}` for
 *  exactly the reason `DEF-AST-4120` records: `_envelope` builds a fresh dict
 *  and silently discards every other key. `readListPageWith` is what hands both
 *  halves back from the same object. */
export interface TemplateChipCounts {
  category_chips: CategoryChip[];
  kind_chips: KindChip[];
}

/** The last-run summary `catalogue_page` attaches to each runbook. */
export interface CatalogueLastRun {
  /** The run's id — an ADDRESS for `RBS-006`, never drawn as a value
   *  (B14 rule 31). */
  id: string;
  status: string;
  mode: string;
  trigger: string;
  /** ISO, or `null`. ⚠ **`started_at` IS NEVER STAMPED** (`DEF-RBS-4291`), so
   *  today this is null on every run and the screen says *Not started yet*
   *  rather than drawing an empty cell. */
  started_at: string | null;
  finished_at: string | null;
  took_seconds: number | null;
  counts: Record<string, number>;
}

/** One row of `GET /runbooks` — this tenant's configured runbooks. */
export interface CatalogueRow {
  key: string;
  name: string;
  kind: RunbookKind;
  category: string;
  tags: string[];
  origin: string;
  enabled: boolean;
  trigger_kind: string;
  cap: number | null;
  current_version: number;
  /** `null` for a runbook the shipped registry does not hold — a clone (wave
   *  E). Served as unknown rather than guessed either way. */
  writes_nothing: boolean | null;
  last_run: CatalogueLastRun | null;
  open_items: number;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-018 · US-RBS-003 (CR-075 wave D tasks D3/D4) · 07-endpoints.md rows 1 and 4 · BR-RBS-025 · TC-RBS-20
// generated: 2026-09-06 by the CR-075 wave D D3/D4 build lane
// checklist: A✔ B=n/a(types) C✔ D✔ E=n/a F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler) · vitest
// exceptions: four optional fields describe facts D1 does not serve (DEF-RBS-4309); each is named in the header rather than filled in
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
