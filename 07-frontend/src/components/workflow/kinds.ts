// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — the ETL runner is ONE implementation with `target`
//           parameterised (design B15 §11: "WFL-01.* The runner … new — ONE
//           implementation, `target` parameterised")
// Rules:    BR-MET-085 (a premises import loads premises and NOTHING else) ·
//           BR-MET-086 (a units import needs premises AND plans on file first) ·
//           BR-MET-087 (a units import creates no meter and no asset)
// Impacts:  components/workflow/** only.
// ───────────────────────────────────────────────────────
//
// THE FIVE STAGES, AND THE KINDS THAT TRAVEL THROUGH THEM.
//
// ⚠ A KIND IS COPY AND A ROUTE, NEVER BEHAVIOUR. Everything that differs
// between a premises run and a units run is a catalogue key or a path; the
// stages, the mapping table, the rules table, the dry run and the receipt are
// identical, which is the property B15 §4B ruled: *"import units will be
// similar to import premises — one runner, two targets. Everything in §4.1–§4.5
// applies unchanged."*
//
// ⚠ AND THE KINDS ARE DATA SO THE TENTH ONE COSTS AN OBJECT. r10 opens this
// runner for premises, units, accounts, reads, lockbox, bank statements, cost
// inputs, meters, sub-meters, devices and parts. Two are declared here because
// two are the two CR-023 designs; the shape is what the other eight need.
//
// ⚠ WHY KEYS AND NOT SENTENCES. A module-level constant cannot call `t()` — the
// i18n instance is not ready at import time and a translated string frozen at
// module scope never changes language. So a kind holds catalogue KEYS and the
// components resolve them. The keys are quoted dotted literals, which is what
// G18 reads as a call site, so a key here that no catalogue defines is caught.

import type { RowHandling, SourceChoice } from "./contract";

export type WorkflowStageId = "extract" | "transform" | "validate" | "load" | "result";

export interface WorkflowStage {
  id: WorkflowStageId;
  /** The word on the rail — "Extract". */
  labelKey: string;
  /** The stage's own question — "Where is the data coming from?". */
  titleKey: string;
  /** The line under it. `null` on Extract, whose blurb is the KIND's. */
  blurbKey: string | null;
  /**
   * The footer primary, which NAMES ITS DESTINATION (B14 rule 4: `Verb →`
   * advances, `Verb ✓` commits). `null` on Result, which has no next stage.
   */
  advanceKey: string | null;
  /**
   * ⚠ THE ONE STAGE THAT WRITES. B15 §4's own diagram marks it and r10 marks it
   * nowhere, while printing "nothing is written until you commit at stage four"
   * under the title — a promise about a stage the strip never points at.
   */
  writes: boolean;
}

export const WORKFLOW_STAGES: readonly WorkflowStage[] = [
  {
    id: "extract",
    labelKey: "workflow.stage.extract",
    titleKey: "workflow.extract.title",
    blurbKey: null,
    advanceKey: "workflow.advance.transform",
    writes: false,
  },
  {
    id: "transform",
    labelKey: "workflow.stage.transform",
    titleKey: "workflow.transform.title",
    blurbKey: "workflow.transform.blurb",
    advanceKey: "workflow.advance.validate",
    writes: false,
  },
  {
    id: "validate",
    labelKey: "workflow.stage.validate",
    titleKey: "workflow.validate.title",
    blurbKey: "workflow.validate.blurb",
    advanceKey: "workflow.advance.load",
    writes: false,
  },
  {
    id: "load",
    labelKey: "workflow.stage.load",
    titleKey: "workflow.load.title",
    blurbKey: "workflow.load.blurb",
    advanceKey: "workflow.advance.commit",
    writes: true,
  },
  {
    id: "result",
    labelKey: "workflow.stage.result",
    titleKey: "workflow.result.title",
    blurbKey: null,
    advanceKey: null,
    writes: false,
  },
];

/** The stage that writes, derived rather than typed twice. */
export const WRITING_STAGE = WORKFLOW_STAGES.findIndex((s) => s.writes) + 1;

export interface WorkflowKind {
  /** ⚠ `WorkflowKindId`, not `string` (tightened 2026-09-22, `P1.18`). It was
   *  `string`, so `WORKFLOW_KINDS[k].id` could not be handed to any function
   *  that takes a kind — and the per-kind RULES (`rollbackControlIsOffered`,
   *  `writeModeRefusals`, `workflowSourcesFor`) all take one. A map whose keys
   *  are an enum and whose `id` field is a free string is a map that cannot
   *  check it agrees with itself. */
  id: WorkflowKindId;
  /** "Workflow · Premises · CSV" — B14 rule 2's kicker. */
  kickerKey: string;
  /** Where `← ` exits to (B14 rule 1: the header's back names its EXIT). */
  returnLabelKey: string;
  returnTo: string;
  /** The Extract stage's own sub-line — the only per-kind stage copy. */
  extractBlurbKey: string;
  /** "Premises" — the dry run's Target row and the `Loads into` field. */
  targetLabelKey: string;
  /** The Result stage's primary — "Go to Premises →". */
  exitLabelKey: string;
  /** The Result stage's NEXT callout. */
  nextNoteKey: string;
  /**
   * ⛔ **DEF-623 — STAGE 5's ROLLBACK SENTENCE, PER TARGET AND REQUIRED.**
   *
   * `RollbackNotice` printed ONE sentence for every kind:
   * *"Rolling back reverses every premise and unit the run created. Units with
   * an active account on them are skipped."* True of premises, roughly true of
   * units, and **wrong for the three assets targets and for accounts** — which
   * were told, directly above a `danger`-tier button that reverses a load, that
   * rolling back would reverse premises and units.
   *
   * Every check passed on it: the key existed in all eleven catalogues (G32),
   * it was a `t()` call and not a literal (G27), the prop typed (tsc), and
   * `workflowStages.test.tsx` rendered the component and asserted it drew. No
   * gate in this repo asks whether a SHARED component's copy is TRUE for the
   * kind it is currently rendering.
   *
   * **The general lesson, which is the reusable half: in a kit parameterised by
   * target, an UNparameterised string is a claim about one target that every
   * other target repeats.** So this is REQUIRED — a seventh kind cannot be
   * registered without a lane writing the sentence for it, the same property
   * `kickerKey` and `extractBlurbKey` already have.
   *
   * ⚠ **AND IT CARRIES ITS ENGLISH, WHICH THE OTHER COPY FIELDS DO NOT.** The
   * module docstring's *"why keys and not sentences"* is about TRANSLATED
   * strings frozen at module scope, and that still holds: `en` is never
   * rendered when the catalogue answers. It is passed to `t()` as
   * `defaultValue`, so a key that has not yet reached `en.json` renders the
   * English sentence instead of the literal string `workflow.accounts.rollback`
   * — DEF-662/G27's failure mode, and the one place in this kit where the
   * fallback sits directly above a destructive control. G18's own documented
   * exclusion is exactly this shape: *"a `t()` call carrying `defaultValue` …
   * the author has stated in code that a missing key is the expected path"*.
   *
   * ⚠ **THE SENTENCES ARE THE SERVER'S BEHAVIOUR, NOT A PARAPHRASE.** Each was
   * read off `apps/metering/import_runs.py::rollback` and the service it hands
   * each row to, so what the operator reads before pressing is what the branch
   * for that target actually does.
   */
  rollbackBody: WorkflowRollbackBody;
  /**
   * ⛔ **CR-054 task 19 — STAGE 2's SUB-LINE AND STAGE 4's HEADING, PER TARGET
   * AND REQUIRED. Same fix as `rollbackBody` above, on two more strings that
   * were FALSE for a target that mounts this runner.**
   *
   * `WORKFLOW_STAGES` holds one `blurbKey` for stage 2 and one `titleKey` for
   * stage 4, and both were written for the `import_runs` pipeline:
   *
   *   * stage 2 promised *"Set it once and save it as a mapping template —
   *     every future run of this import reuses it."* **Reads deliberately keeps
   *     no mapping** (BR-MET-032: ONE published template, validate THEN accept,
   *     NO mapping memory) and says so six lines below on the same stage, so a
   *     clerk read the screen contradicting itself.
   *   * stage 4 read *"Dry run first. Then commit."* and **reads has no dry
   *     run** — there is no `dry-run` call anywhere in the reads pipeline, and
   *     the word does not appear in `UploadReadsWizard.tsx`. The heading named
   *     a rehearsal the product never performs, directly above the danger-tier
   *     control that writes.
   *
   * Both are the lesson `rollbackBody` records, verbatim: **in a kit
   * parameterised by target, an UNparameterised string is a claim about one
   * target that every other target repeats.** So both are REQUIRED here — an
   * eighth kind cannot be registered without a lane writing them — and both
   * carry their English as `defaultValue` for the same reason the rollback
   * sentence does (G18's documented exclusion; DEF-662's failure mode).
   *
   * The six `import_runs` kinds keep the existing catalogue keys, so no copy
   * moves for them and this change is a widening, not a rewrite.
   */
  transformBlurb: WorkflowCopy;
  loadTitle: WorkflowCopy;
  /**
   * ⚖️ **`CR-096-BRC02` — THE COPY A TARGET DRAWS IN ITS OWN WORDS, WHERE THE
   * SHARED STRING IS NOT WHAT ITS BLUEPRINT DRAWS. OPTIONAL, SO NO OTHER KIND
   * MOVES.**
   *
   * `rollbackBody`, `transformBlurb` and `loadTitle` above are three separate
   * fields that each exist for the SAME reason — one shared sentence that was
   * wrong for one target — and each was added the day that target's own screen
   * was read. This is the general form of all three, so a fourth string does
   * not need a fourth field.
   *
   * Meter Reads is the first target with a blueprint drawing of every one of
   * its five stages (B14 rules 41 and 42: the drawing IS the specification and
   * it is read as an image), and it draws a page head and four stage heads the
   * shared strings do not say:
   *
   * | Where | Shared copy | What the blueprint draws |
   * |---|---|---|
   * | page head | *"Extract, transform, validate, load."* | **Upload reads** |
   * | stage 1 | *"Where is the data coming from?"* | **The source** |
   * | stage 2 | *"Map their shape onto ours."* | **Columns** |
   * | stage 3 | *"Test it before you trust it."* | **The rules** |
   * | stage 5 | *"Loaded. Here's the receipt."* | **Posted** |
   *
   * ⚠ **AND THE RAIL'S PROMISE SENTENCE IS DRAWN NOWHERE**, which the blueprint
   * states rather than implies: *"This is the only stage that writes.
   * Everything before it was rehearsal."* is listed as **REMOVED** — *"11 words
   * of rationale. The `WRITES` chip on the rail says it without a sentence."*
   * B14 rule 33 is the rule behind it: rationale is ZERO words on screen. So
   * `railPromise: null` suppresses it for a kind whose rail already carries the
   * chip, and `undefined` keeps the shared sentence exactly as every other
   * target renders it today.
   *
   * ⚠ **EVERY VALUE HERE IS A `WorkflowCopy`, WHICH CARRIES ITS ENGLISH** — the
   * same `defaultValue` discipline `rollbackBody` records above, for the same
   * DEF-662/G27 reason.
   */
  own?: WorkflowOwnCopy;
  /**
   * ⚠ **STAGE-2 OPTIONS THE SERVER NEEDS AND THE MAPPING TABLE CANNOT CARRY —
   * DECLARED AS DATA, WHICH IS THE ONLY WAY THIS MODULE ALLOWS (DEF-626).**
   *
   * `transform` sends `options` beside `mapping` and `row_handling`, and the
   * runner had no way to fill it: the client's request type declared two keys
   * and the wizard built exactly those two. So the accounts target could not
   * be given its cutover date, the load refused every file carrying an opening
   * balance (BR-CUS-049), and there was no control anywhere in five stages
   * that could satisfy the refusal.
   *
   * The fix could not be `if (target === "accounts")` in the runner —
   * BR-MET-096 forbids exactly that, and this module's own docstring says a
   * kind is COPY AND A ROUTE, NEVER BEHAVIOUR. An option FIELD is neither: it
   * is a declaration the runner renders without knowing what it means. Adding
   * the reads target's period, or a lockbox deposit date, costs another entry
   * and no code.
   */
  options?: readonly WorkflowOptionField[];
}

/**
 * Stage 5's rollback sentence for ONE target: its catalogue key and the English
 * that key was written from.
 *
 * Two fields rather than one because a rollback sentence is the one string in
 * this kit that must never be able to render as its own key name — see
 * `WorkflowKind.rollbackBody`.
 */
/**
 * One per-kind string: its catalogue key and the English that key was written
 * from. `WorkflowRollbackBody` is this shape and keeps its own name because its
 * docstring is about the rollback sentence specifically.
 */
export interface WorkflowCopy {
  /** The catalogue key. Resolved by the component, never at module scope. */
  key: string;
  /** The English the key was written from, passed as i18next `defaultValue`. */
  en: string;
}

/**
 * See `WorkflowKind.own`. Every field is optional and `undefined` means "use
 * the shared copy", so a kind that declares none renders byte-for-byte what it
 * renders today.
 */
export interface WorkflowOwnCopy {
  /** The page-head title, in place of `workflow.title`. */
  pageTitle?: WorkflowCopy;
  /** `null` draws no promise sentence above the rail. */
  railPromise?: WorkflowCopy | null;
  /**
   * Per-stage head. A `blurb` of `null` draws no sub-line at all, which is how
   * a stage whose heading already says everything asks for silence rather than
   * falling through to the shared string.
   */
  stages?: Partial<
    Record<WorkflowStageId, { title?: WorkflowCopy; blurb?: WorkflowCopy | null }>
  >;
}

export interface WorkflowRollbackBody {
  /** The catalogue key. Resolved by `RollbackNotice`, never at module scope. */
  key: string;
  /** The English the key was written from, passed as i18next `defaultValue`. */
  en: string;
  /**
   * ⛔ **`P1.22` — THIS TARGET HAS NO ROLLBACK AT ALL, SO IT DRAWS NO BUTTON.**
   *
   * Every kind before payments could be rolled back, so the sentence above a
   * `danger`-tier control was always a WARNING and the control was always
   * right to be there. Payments is the first `import_runs` target where the
   * sentence is a **REFUSAL**: a posted payment cannot be unwritten
   * (CLAUDE.md hard rule 4), `_load_payments_rows` creates no rollback point,
   * and `import_runs.rollback` refuses the target by name before it reads
   * anything.
   *
   * ⚠ **WITHOUT THIS FLAG THE BUTTON RENDERS, BECAUSE `ImportWorkflowPage`
   * DRAWS IT FOR EVERY KIND.** Reads never hit that — it mounts
   * `UploadReadsWizard`, a different screen — so "reads refuses and shows no
   * button" was true by accident of routing rather than by any rule. Payments
   * mounts the shared runner, so the absence has to be STATED. That is
   * hard-won law 2's mirror: a live control over a screen that refuses, and
   * the thing nothing in this repo asks is whether a refusal is still true.
   *
   * `undefined` means the kind can be rolled back — so no existing kind moves.
   */
  refuses?: true;
}

/**
 * One stage-2 option. The runner renders it, validates it and sends it; it
 * never interprets it.
 *
 * `requiredWhenAnyMapped` is what keeps this DATA rather than a rule: the
 * runner asks *"is any of these targets mapped?"* — a question about the
 * mapping table it already holds — and never asks what an `ob_*` column IS.
 * An empty or absent list means the option is optional, always.
 */
export interface WorkflowOptionField {
  /** The key the server reads inside `options`. */
  id: string;
  /** `date` is the only kind any target needs today. */
  kind: "date";
  labelKey: string;
  helpKey: string;
  /** The refusal to show inline when it is required and empty. ⚠ This is the
   *  SERVER'S OWN refusal key, so the sentence the operator reads before
   *  submitting is the one they would have read after. */
  requiredMessageKey: string;
  /** Mapped-target names that make this option required. */
  requiredWhenAnyMapped?: readonly string[];
  /**
   * ⛔ **CR-047 (b) — WHAT LEAVING IT EMPTY MEANS, SAID WHERE IT IS LEFT
   * EMPTY.**
   *
   * An option that stops being required does not become unimportant; it
   * becomes a CHOICE, and a choice with no stated consequence is a coin toss.
   * The runner draws this sentence under the field whenever the field is
   * optional — it never asks what the option is, exactly as it never asks
   * what an `ob_*` column is (BR-MET-096).
   *
   * ⚠ Absent means the option simply has no consequence worth stating.
   */
  whenEmptyKey?: string;
}

/**
 * ⚠ THE `NEXT` CALLOUTS ARE THE PO'S 2026-08-21 RULING, NOT r10's COPY.
 * r10's premises receipt reads *"Units are next. Import them from the Units tab,
 * **or let single-unit premises create their own**."* BR-MET-085 withdraws the
 * second clause with the behaviour behind it — a premises load creates premises
 * and nothing else — so the sentence stops there. Do not restore it from the
 * screenshot; B15 §4A exists to stop exactly that.
 */
export type WorkflowKindId =
  | "premises"
  | "units"
  | "assets_meters"
  | "assets_submeters"
  | "assets_devices"
  | "accounts"
  | "parts"
  | "reads"
  | "payments";

/**
 * The two per-kind strings above, for the SEVEN targets that run through
 * `apps/metering/import_runs.py` — premises, units, the three assets targets,
 * accounts and parts. All seven really do offer a saved mapping template and
 * all seven really do dry-run before they load, so one constant for the seven
 * is a statement about a shared pipeline rather than the DEF-623 shape.
 *
 * ⚠ NAMED FOR THE PIPELINE, NOT FOR "THE DEFAULT". A seventh target arriving on
 * a different pipeline has to look at the name and notice it does not apply —
 * which is exactly what did NOT happen when reads joined this runner.
 */
const IMPORT_RUNS_TRANSFORM_BLURB: WorkflowCopy = {
  key: "workflow.transform.blurb",
  en: "Set it once and save it as a mapping template — every future run of this import reuses it.",
};
const IMPORT_RUNS_LOAD_TITLE: WorkflowCopy = {
  key: "workflow.load.title",
  en: "Dry run first. Then commit.",
};

/**
 * Stage 2's sub-line and stage 4's heading for the reads target, declared once
 * because two fields on the kind point at each (`transformBlurb`/`loadTitle`,
 * and `own.stages`). One object, so they cannot drift.
 */
const READS_TRANSFORM_BLURB: WorkflowCopy = {
  key: "workflow.reads.transformBlurb",
  en: "Nothing is remembered between files.",
};
const READS_LOAD_TITLE: WorkflowCopy = {
  key: "workflow.reads.loadTitle",
  en: "Certify it. Then post.",
};

export const WORKFLOW_KINDS: Record<WorkflowKindId, WorkflowKind> = {
  premises: {
    id: "premises",
    kickerKey: "workflow.premises.kicker",
    returnLabelKey: "workflow.premises.return",
    returnTo: "/premises",
    extractBlurbKey: "workflow.premises.blurb",
    targetLabelKey: "workflow.premises.target",
    exitLabelKey: "workflow.premises.exit",
    nextNoteKey: "workflow.premises.next",
    transformBlurb: IMPORT_RUNS_TRANSFORM_BLURB,
    loadTitle: IMPORT_RUNS_LOAD_TITLE,
    // BR-MET-099 / `import_runs.rollback`'s default branch: the premise row is
    // set inactive, never deleted, and `_is_occupied` keeps any premise that
    // has an active account on ANY of its units.
    rollbackBody: {
      key: "workflow.premises.rollback",
      en: "Rolling back deactivates every premise this run created. A premise is kept and reported if any unit on it now has an active account. Nothing is deleted.",
    },
  },
  units: {
    id: "units",
    kickerKey: "workflow.units.kicker",
    returnLabelKey: "workflow.units.return",
    returnTo: "/premises/units",
    extractBlurbKey: "workflow.units.blurb",
    targetLabelKey: "workflow.units.target",
    exitLabelKey: "workflow.units.exit",
    nextNoteKey: "workflow.units.next",
    transformBlurb: IMPORT_RUNS_TRANSFORM_BLURB,
    loadTitle: IMPORT_RUNS_LOAD_TITLE,
    // The same branch, `_is_occupied`'s TARGET_UNITS arm: occupancy is one
    // unit's own active account, not its premise's.
    rollbackBody: {
      key: "workflow.units.rollback",
      en: "Rolling back deactivates every unit this run created. A unit is kept and reported if it now has an active account on it. Nothing is deleted.",
    },
  },
  // ── CR-028 AST-W3 (BR-AST-046/BR-MET-096): the three assets targets. Data,
  // exactly as the module docstring promised — copy and a route, no behaviour.
  // All three exit to the Assets page with THEIR tab selected, matching the
  // tab-named button that opened them.
  assets_meters: {
    id: "assets_meters",
    kickerKey: "workflow.assets_meters.kicker",
    returnLabelKey: "workflow.assets_meters.return",
    returnTo: "/assets?tab=meters",
    extractBlurbKey: "workflow.assets_meters.blurb",
    targetLabelKey: "workflow.assets_meters.target",
    exitLabelKey: "workflow.assets_meters.exit",
    nextNoteKey: "workflow.assets_meters.next",
    transformBlurb: IMPORT_RUNS_TRANSFORM_BLURB,
    loadTitle: IMPORT_RUNS_LOAD_TITLE,
    // `import_runs.rollback`'s ASSETS_TARGETS branch →
    // `assets.services.rollback_from_import`: assignment closed, status back to
    // Inventory; kept on `read_count_for_asset > 0` or a terminal status.
    rollbackBody: {
      key: "workflow.assets_meters.rollback",
      en: "Rolling back closes the assignment on every meter this run created and returns it to Inventory. A meter is kept and reported if it already carries reads, or if it has been retired since the load. Nothing is deleted.",
    },
  },
  assets_submeters: {
    id: "assets_submeters",
    kickerKey: "workflow.assets_submeters.kicker",
    returnLabelKey: "workflow.assets_submeters.return",
    returnTo: "/assets?tab=sub_meters",
    extractBlurbKey: "workflow.assets_submeters.blurb",
    targetLabelKey: "workflow.assets_submeters.target",
    exitLabelKey: "workflow.assets_submeters.exit",
    nextNoteKey: "workflow.assets_submeters.next",
    transformBlurb: IMPORT_RUNS_TRANSFORM_BLURB,
    loadTitle: IMPORT_RUNS_LOAD_TITLE,
    // Same branch, same service — the target name is the only difference.
    rollbackBody: {
      key: "workflow.assets_submeters.rollback",
      en: "Rolling back closes the assignment on every sub-meter this run created and returns it to Inventory. A sub-meter is kept and reported if it already carries reads, or if it has been retired since the load. Nothing is deleted.",
    },
  },
  assets_devices: {
    id: "assets_devices",
    kickerKey: "workflow.assets_devices.kicker",
    returnLabelKey: "workflow.assets_devices.return",
    returnTo: "/assets?tab=behind_the_meter",
    extractBlurbKey: "workflow.assets_devices.blurb",
    targetLabelKey: "workflow.assets_devices.target",
    exitLabelKey: "workflow.assets_devices.exit",
    nextNoteKey: "workflow.assets_devices.next",
    transformBlurb: IMPORT_RUNS_TRANSFORM_BLURB,
    loadTitle: IMPORT_RUNS_LOAD_TITLE,
    // Same branch again; "device" is r10's Behind-the-meter tab vocabulary.
    rollbackBody: {
      key: "workflow.assets_devices.rollback",
      en: "Rolling back closes the assignment on every device this run created and returns it to Inventory. A device is kept and reported if it already carries reads, or if it has been retired since the load. Nothing is deleted.",
    },
  },
  // ── CR-030 W1 — accounts, the SIXTH target. This module's own docstring
  // predicted it: *"the kinds are DATA so the tenth one costs an object"* and
  // *"r10 opens this runner for premises, units, ACCOUNTS, reads, lockbox…"*.
  // One object and a route, exactly as promised — no behaviour anywhere.
  //
  // ⚠ It exits to the Accounts page's IMPORTS tab, matching the button that
  // opened it, the same rule the three assets kinds follow.
  // ── CR-077 · THE SEVENTH TARGET, AND IT RUNS ON THE SAME PIPELINE ────────
  // The PO asked for import starters for *"Premises, Units, Meters, Sub
  // meter,s Assets, Parts, Accounts, Reading"*. Parts is a TARGET of the one
  // ETL runner (`BR-MET-096`), so it takes the two shared strings below like
  // the other six; `reads` is the one kind on a different pipeline and still
  // declares its own.
  //
  // ⚠ **THE ROLLBACK SENTENCE IS ITS OWN AND IT HAS TO BE (`DEF-623`).** In a
  // kit parameterised by target, an unparameterised string is a claim about one
  // target that every other target repeats. What is true here and nowhere else:
  // a part that has been ISSUED to a job is kept and switched off, because
  // deleting it would take the job's materials record with it.
  parts: {
    id: "parts",
    kickerKey: "workflow.parts.kicker",
    returnLabelKey: "workflow.parts.return",
    returnTo: "/work/parts",
    extractBlurbKey: "workflow.parts.blurb",
    targetLabelKey: "workflow.parts.target",
    exitLabelKey: "workflow.parts.exit",
    nextNoteKey: "workflow.parts.next",
    transformBlurb: IMPORT_RUNS_TRANSFORM_BLURB,
    loadTitle: IMPORT_RUNS_LOAD_TITLE,
    rollbackBody: {
      key: "workflow.parts.rollback",
      en: "Rolling back removes every part this run added. A part that has already been issued to a job is kept and switched off instead — deleting it would take the materials record of that job with it.",
    },
  },
  accounts: {
    id: "accounts",
    kickerKey: "workflow.accounts.kicker",
    returnLabelKey: "workflow.accounts.return",
    returnTo: "/accounts?tab=imports",
    extractBlurbKey: "workflow.accounts.blurb",
    targetLabelKey: "workflow.accounts.target",
    exitLabelKey: "workflow.accounts.exit",
    nextNoteKey: "workflow.accounts.next",
    transformBlurb: IMPORT_RUNS_TRANSFORM_BLURB,
    loadTitle: IMPORT_RUNS_LOAD_TITLE,
    // ⚠ THE SENTENCE DEF-623 WAS FILED FOR. Three facts, all law:
    // (1) `customers.services.rollback_from_import` CLOSES the account as of
    //     the tenant's today and removes its opening buckets — never deletes;
    // (2) `kept_billed` is BR-CUS-047 / B18 §5.9.4 resting on hard rule 4:
    //     an issued invoice cannot be unmade, so the account it was issued to
    //     cannot be un-created. Stated FIRST because it is the one an operator
    //     of a real cutover will hit;
    // (3) `_refuse_accounts_rollback_with_opening_books` refuses the WHOLE run
    //     before touching a row when the load posted opening journal entries
    //     (OQ-352, unruled). That refusal is invisible on this screen until it
    //     fires, which is exactly the sentence an operator needed and did not
    //     get.
    rollbackBody: {
      key: "workflow.accounts.rollback",
      en: "Rolling back closes every account this run created and removes its opening balances. An account that has already been billed is kept and reported — an issued bill cannot be unmade. A run that posted opening balances cannot be rolled back at all.",
    },
    // ⛔ DEF-626 · BR-CUS-049 dates every opening journal entry at CUTOVER, and
    // BR-TEN-043 forbids reading a clock for the caller — so the server refuses
    // a file carrying any `ob_*` column until it is told the date. Defaulting to
    // today would date a utility's migrated books on the day somebody happened
    // to run the import: every ageing band wrong by the gap, silently, and
    // uncorrectable by edit once the entries post (hard rule 4).
    //
    // ⚠ It was required ONLY when an opening-balance column was mapped. An
    // account list with no balances needs no cutover, and demanding one would
    // put a mandatory field in front of the simplest import there is.
    //
    // The three keys already existed in all eleven catalogues — leftovers from
    // the deleted three-step modal, which HAD this control. Nothing was
    // translated for this fix; the copy outlived the screen that used it.
    //
    // ⛔ **AND IT IS NOT REQUIRED AT ALL ANY MORE — CR-047 (b), on the PO
    // ruling of 2026-08-27: the accounts LOAD and only the money waits.**
    //
    // `requiredWhenAnyMapped: ["ob_current", "ob_31_60", "ob_61_90",
    // "ob_90_plus"]` stood here, and it welded stage 2 shut for exactly the
    // operator the hold was built for: the one who has the file and does not
    // yet know which day their old system stopped being in charge of the
    // money. The server had already stopped refusing — `_load_accounts` sets
    // `opening_held = cutover is None`, writes the buckets under a provisional
    // date of today − 90 days and **calls the ledger not at all** — so the
    // wall was the screen's alone, and it stood in front of a door the server
    // had opened three days earlier.
    //
    // ⚠ **THE DATE IS NOT GONE, IT MOVED.** `confirm-changeover` on the
    // receipt is where it is asked for now, in the rule's own words, and
    // `whenEmptyKey` below is the sentence that says so BEFORE the choice is
    // made. Re-adding the requirement here without removing that control
    // would strand money by design; removing that control without this would
    // hide the wall rather than open the door. They are one change.
    options: [
      {
        id: "cutover_on",
        kind: "date",
        labelKey: "customers.import.file.cutover",
        helpKey: "customers.import.file.cutoverHelp",
        // Kept although nothing arms it today: it is the SERVER's own refusal
        // key (`customers.import.cutover_required`, still raised by
        // `_refuse_accounts_no_cutover`), and a field that regains a required
        // condition must not have to re-find the sentence for it.
        requiredMessageKey: "customers.import.cutover_required",
        whenEmptyKey: "customers.import.file.cutoverWhenEmpty",
      },
    ],
  },
  // ── CR-038 W7 — READS, THE SEVENTH TARGET, AND THE ONE THE PO ASKED FOR ──
  //
  // PO, 2026-08-26, verbatim: *"These are existing screens - We need to follow
  // tailwind wizard that we are using - i believe we are using same code for
  // various"*. The belief was verified TRUE and this object is what it costs:
  // reads had a SEPARATE five-step wizard (`UploadReadsWizard`, built
  // 2026-08-15 on `WizardFrame`) which drew its own header, its own rail and
  // its own footer while premises, units, three assets targets and accounts all
  // shared this one. This module's own docstring predicted the day —
  // *"r10 opens this runner for premises, units, accounts, READS, lockbox…"*.
  //
  // ⚠ **AND READS ARE THE FIRST TARGET WHOSE STAGES DRIVE A DIFFERENT SERVER
  // PIPELINE**, which is exactly why the kit's shape holds: a kind is COPY AND
  // A ROUTE, NEVER BEHAVIOUR. The other six run through `import_runs`; reads run
  // through `stage_read_batch → validate_read_batch → commit_read_batch`, with
  // sixteen VEE rules and an append-only supersede discipline none of the others
  // have. Nothing about that reaches this file — the runner draws the header,
  // the numbered rail and the footer, and the screen supplies its own bodies.
  //
  // ⚠ **NO `options` ENTRY, AND THE WRITE MODE IS WHY.** The accounts kind
  // declares `cutover_on` as an option field because the runner renders it. The
  // write mode is NOT an option field: `WorkflowOptionField` only knows
  // `kind: "date"`, and a mode carries a per-mode consequence sentence that a
  // generic date/text field could not render honestly.
  //
  // ⚠ **AND SINCE CR-042 IT IS NOT THIS KIND'S BUSINESS AT ALL.** The write
  // mode was drawn by each rail's own step-1 body — reads here, the ETL runner
  // in `ImportWorkflowPage` — and the two drifted into different shapes, different
  // captions and different catalogue keys. It is now ONE component,
  // `WriteModeChoice.tsx`, which every import mounts; a kind supplies only its
  // two consequence sentences, because that is the one thing that legitimately
  // differs between targets (BR-MET-210).
  // ⛔ **THE EIGHTH `import_runs` TARGET (`P1.1`/`P1.21`), AND THE FIRST ON
  // THIS RUNNER WHOSE STAGE-5 SENTENCE IS A REFUSAL.**
  //
  // ⚠ **REGISTERED HERE OR THE SEVEN CATALOGUE KEYS ARE DEAD COPY.** The
  // server can serve the target, `tsc` passes, every test passes, and the
  // runner simply never offers it — hard-won law 2, and exactly the shape
  // that kept an eleventh utility service off the sign-up screen.
  payments: {
    id: "payments",
    kickerKey: "workflow.payments.kicker",
    returnLabelKey: "workflow.payments.return",
    returnTo: "/payments",
    extractBlurbKey: "workflow.payments.blurb",
    targetLabelKey: "workflow.payments.target",
    exitLabelKey: "workflow.payments.exit",
    nextNoteKey: "workflow.payments.next",
    // This target runs through `import_runs` like the other seven, so it takes
    // the shared stage-2 and stage-4 strings: it really does offer a saved
    // mapping template and it really does dry-run before it loads.
    transformBlurb: IMPORT_RUNS_TRANSFORM_BLURB,
    loadTitle: IMPORT_RUNS_LOAD_TITLE,
    // ⛔ **`P1.22`. READ OFF THE SERVER, NOT PARAPHRASED** — `import_runs.
    // rollback`'s payments branch refuses by name, and `_load_payments_rows`
    // creates no rollback point for it to spend. `Discard this batch` before
    // the commit is the only way to throw a payments run away.
    //
    // ⚠ Two sentences of six words rather than one of twelve (B14 rule 33 on a
    // CONSEQUENCE before an irreversible act): the first says what is true,
    // the second says what to do instead.
    rollbackBody: {
      key: "workflow.payments.rollback",
      en: "A posted payment cannot be unwritten. Discard the batch before you commit.",
      refuses: true,
    },
  },
  reads: {
    id: "reads",
    kickerKey: "workflow.reads.kicker",
    returnLabelKey: "workflow.reads.return",
    returnTo: "/reads",
    extractBlurbKey: "workflow.reads.blurb",
    targetLabelKey: "workflow.reads.target",
    exitLabelKey: "workflow.reads.exit",
    nextNoteKey: "workflow.reads.next",
    // ⛔ CR-054 task 19 — the two strings that were FALSE on this target.
    //
    // BR-MET-032, verbatim: *"ONE published template, validate THEN accept, no
    // mapping memory"*. `read_import.detect_mapping` re-detects against the
    // published template on EVERY upload and nothing stores the result, which
    // is why this screen's own stage-2 note already read *"nothing is
    // remembered between files"* — six lines under a rail sub-line promising a
    // saved template. The screen contradicted itself, in the shared half.
    // ⚠ **TRIMMED TO THE DRAWING (`CR-096-BRC02`).** It read *"Columns are
    // matched to the published template on every upload. Nothing is remembered
    // between files."* — two sentences of 10 and 5 words, where B14 rule 33
    // caps an instruction at SIX per sentence. The blueprint's stage-2 drawing
    // keeps the second sentence and drops the first, which is the same fact
    // said once: a template that is re-detected every time is a template
    // nothing remembered. BR-MET-032 is unchanged; only the words are.
    transformBlurb: READS_TRANSFORM_BLURB,
    // There is NO dry run in the reads pipeline: `stage_read_batch` →
    // `validate_read_batch` → `commit_read_batch`, and no fourth call
    // rehearses the write. What stage 4 actually asks for is BR-MET-017's
    // certification, which is the gate on the commit — so the heading names
    // that instead of a rehearsal that never happens.
    loadTitle: READS_LOAD_TITLE,
    // ⛔ DEF-623's REQUIRED field, and for reads the true sentence is a
    // REFUSAL. Read off the server, not paraphrased: `import_runs.rollback`
    // has no reads branch and there is no reads rollback service anywhere —
    // because a posted read batch is IMMUTABLE (BR-MET-017) and a committed
    // reading can only ever be superseded by a new row (hard rule 4 / B2 DB-6),
    // never un-created. `discard_read_batch` covers the only reversible state,
    // and it refuses a posted batch by name.
    //
    // Saying "rolling back reverses every reading this run created" here would
    // be the exact DEF-623 failure — one target's sentence repeated over a
    // target where it is false — sitting above a danger-tier control, on the
    // one pipeline in the product where the claim would be a hard-rule
    // violation if anything acted on it.
    rollbackBody: {
      key: "workflow.reads.rollback",
      en: "A posted read batch cannot be rolled back. Every reading it committed is permanent, and a wrong one is corrected by uploading the right one — which supersedes it and keeps both on the record. Cancel before you post to discard the batch instead.",
    },
    // ⚖️ **THE BLUEPRINT'S OWN PAGE HEAD AND STAGE HEADS (`CR-096-BRC02`).**
    // Read off the five drawings as IMAGES (B14 rule 42), not off their text
    // layer. `transform` and `load` point at the SAME objects the two fields
    // above hold, so the two mechanisms cannot say different things about one
    // stage — the second copy of a fact is what hard-won law 5 exists to stop.
    own: {
      pageTitle: { key: "workflow.reads.pageTitle", en: "Upload reads" },
      // The `WRITES` chip on the rail says it without a sentence; see
      // `WorkflowOwnCopy.railPromise`.
      railPromise: null,
      stages: {
        extract: {
          title: { key: "workflow.reads.extractTitle", en: "The source" },
          // The cards and their six controls are the whole of this stage; the
          // shared sub-line restated the heading.
          blurb: null,
        },
        transform: {
          title: { key: "workflow.reads.transformTitle", en: "Columns" },
          blurb: READS_TRANSFORM_BLURB,
        },
        validate: {
          title: { key: "workflow.reads.validateTitle", en: "The rules" },
          blurb: {
            key: "workflow.reads.validateBlurb",
            en: "Errors block the load. Warnings do not.",
          },
        },
        load: { title: READS_LOAD_TITLE, blurb: null },
        result: {
          title: { key: "workflow.reads.resultTitle", en: "Posted" },
          blurb: null,
        },
      },
    },
  },
};

/**
 * Stage 1's four cards.
 *
 * ⚠ THREE OF THE FOUR ARE DRAWN AND REFUSE, WHICH IS THE POINT. r10 offers
 * File · SFTP · API · Manual as four live choices; this product has one. B15 §8
 * Q2 asks whether the other three are in scope for CR-023 and it is UNRULED, so
 * the honest shape is the stated absence: the card is listed, it says it is not
 * switched on, and it does not accept a press. Deleting them would make the
 * screen quietly disagree with the design; enabling them would answer an open
 * question by building it.
 *
 * ⚠ AND r10's KICKER LINE (`File` / `SFTP` / `API` / `Manual` above each title)
 * IS DELIBERATELY NOT DRAWN. Two of those four values are protocol acronyms
 * that are byte-identical in all eleven catalogues, and G15 fails a non-English
 * value identical to English unless it is added to a ratified allowlist —
 * loosening a ratified gate to print a word the title already says. The title
 * carries the meaning ("Pull from a server") and the sub-line the examples.
 */
/**
 * ⛔ **`P1.22`/`P1.23` — DOES THIS TARGET OFFER A ROLLBACK CONTROL AT ALL?**
 *
 * One function rather than a `kind.rollbackBody.refuses ?` scattered through a
 * 4,000-line page (B14 rule 43: a piece of UI is built as a COMPONENT, and
 * standalone code inside a page is not reuse). It exists mainly so the RULE
 * can be asserted without mounting a whole wizard — a refusal nothing asserts
 * is a refusal that rots, which is hard-won law 2's mirror and the reason
 * `P1.23` is a task at all.
 *
 * ⚠ **A `false` HERE IS A CLAIM ABOUT THE SERVER**, not a styling choice:
 * `import_runs.rollback` refuses this target by name and `_load_payments_rows`
 * creates no rollback point. A lane that makes this return `true` for payments
 * puts a live `danger`-tier button over a door the server keeps shut.
 */
export function rollbackControlIsOffered(kind: WorkflowKind): boolean {
  return kind.rollbackBody.refuses !== true;
}

/**
 * ⛔ **`P1.19` — THE SCAN PAPER CARD, AND WHY IT IS A CARD RATHER THAN A SCREEN.**
 *
 * Blueprint p067 ①, verbatim: *"Scan paper is the fifth card — a sack of cheques
 * is a SOURCE, never a second screen"*, and p068 ② gives the mechanism: *"A
 * barcode scanner is a keyboard — it types what it reads and presses Enter. No
 * driver, no integration, no pairing. So Scan paper is a source card and a
 * focused input, and everything after it is the runner: the same mapping, the
 * same rules, the same rejects, the same dry run, the same receipt."* The whole
 * outcome of the task is **one screen fewer**.
 *
 * ⚠ **IT WAS HELD FOR TWENTY DAYS, AND THE HOLD IS SPENT — `DEF-BIL-6325`,
 * 2026-09-23.** The reason was never a missing screen: it was a fact about our
 * own paper. Blueprint p068 ②, *"our printed bill carries no remittance
 * barcode"*. **It carries one now.** The PO, the same day: *"please enable it
 * and also start putting bar code on bills - we are still in beta and uat - we
 * ahve to make these changes now"*.
 *
 * ⚠⚠ **THE ORDER WAS THE WHOLE JOB, AND IT IS THE OPPOSITE OF HOW THE
 * INSTRUCTION READS.** *Enable it and also start putting bar code on bills*
 * puts the card first. Built that way round, a clerk selects Scan paper,
 * points a wedge scanner at one of our bills and gets NOTHING — hard-won law
 * 2's mirror, a live control over a door onto nothing, and the exact failure
 * `P5.15` is named for. So the BARS landed first and this flag moved second.
 *
 * ⚠ **AND IT WAS RELEASED ON A DECODE, NOT ON A SIGHTING.**
 * `06-backend/tests/test_def_bil_6325_barcode_round_trip.py` renders a real
 * bill, reads the filled rectangles out of the PDF's own content stream,
 * recovers the spaces between them by subtraction the way a decoder does, and
 * reads the symbol back to characters with a Code 39 table **written
 * independently of the one that drew it** — then asserts the string is
 * byte-identical to the line printed underneath. *The function was called* and
 * *N rectangles were drawn* are both true of a barcode no scanner can read.
 *
 * ⚠ **WHAT WAS ALREADY BUILT BEHIND THIS CARD, WHICH IS WHY RELEASING IT WAS
 * ONE LINE.** `components/workflow/ScanInput.tsx` is the focused field, `POST
 * /billing/remittance/parse` is the one door onto the grammar — it calls
 * `remittance.parse()` rather than re-deriving a second Code 39 mod-43 in
 * TypeScript — and `ImportWorkflowPage`'s Extract stage renders the input the
 * moment `available` flips. `P5.8` built all of it and deliberately left the
 * flag alone.
 *
 * ⚠ **THE TESTS THAT HELD IT WERE INVERTED, NOT DELETED.** Their own messages
 * said *delete this case*; deleting them would leave nothing asserting the
 * property that actually matters, which is not *the card is on* but **the card
 * is on IF AND ONLY IF our own paper can be scanned**.
 * `scanSourceIsReachableAndHeld.dom.test.tsx` now asserts the card is LIVE at
 * the address `App.tsx` really mounts, keeping every reachability assertion it
 * had; `test_cr139_p5_12_to_p5_15.py` reads this constant and
 * `documents.py` together and fails if either moves without the other. Split
 * them and a lane that takes the bars off the bill leaves this card live with
 * its own test still green (`BR-SHL-025`, hard-won law 2's mirror).
 */
const SCAN_PAPER_CARD: SourceChoice = {
  id: "scan",
  title_key: "workflow.source.scan.title",
  sub_key: "workflow.source.scan.sub",
  available: true,
  // ⚠ NO `unavailable_reason_key`. `workflow.source.scan.notYet` is RETIRED
  // from all eleven catalogues, not merely unreferenced: a refusal sentence
  // left in a catalogue is a sentence a later lane finds, believes and puts
  // back on screen (DEF-PAY-6274 is that exact shape, one day earlier).
};

export const WORKFLOW_SOURCES: readonly SourceChoice[] = [
  {
    id: "file",
    title_key: "workflow.source.file.title",
    sub_key: "workflow.source.file.sub",
    available: true,
  },
  {
    id: "sftp",
    title_key: "workflow.source.sftp.title",
    sub_key: "workflow.source.sftp.sub",
    available: false,
    unavailable_reason_key: "workflow.source.notYet",
  },
  {
    id: "api",
    title_key: "workflow.source.api.title",
    sub_key: "workflow.source.api.sub",
    available: false,
    unavailable_reason_key: "workflow.source.notYet",
  },
  {
    id: "manual",
    title_key: "workflow.source.manual.title",
    sub_key: "workflow.source.manual.sub",
    available: false,
    unavailable_reason_key: "workflow.source.notYet",
  },
];

/**
 * ⛔ **WHICH SOURCE CARDS THIS TARGET DRAWS (`P1.19`).**
 *
 * ⚠ **A FUNCTION RATHER THAN A FIFTH ENTRY IN `WORKFLOW_SOURCES`, BECAUSE THE
 * CARD IS NOT TRUE OF EVERY TARGET.** `WORKFLOW_SOURCES` is drawn by all eight
 * importers, and nobody scans a sack of premises: an unconditional fifth card
 * would put a permanently-refused control on seven screens that have no paper
 * to scan, which is B14 rule 32's noise and `BR-SHL-025` misapplied — that rule
 * is about a control a clerk EXPECTS and cannot use, not about every control
 * that could theoretically exist.
 *
 * It is the same shape as `rollbackControlIsOffered` one section up and for the
 * same reason: the rule lives in ONE place that can be asserted without
 * mounting a wizard, rather than as a `kind.id === "payments" ?` inside a
 * 4,000-line page (B14 rule 43).
 */
export function workflowSourcesFor(kind: WorkflowKindId): readonly SourceChoice[] {
  return kind === "payments" ? [...WORKFLOW_SOURCES, SCAN_PAPER_CARD] : WORKFLOW_SOURCES;
}

/**
 * ⛔ **`DEF-PAY-10772` — WHAT THE TRANSFORM TICKS START AS.** Every importer
 * starts with *"Drop exact duplicate rows"* ticked, which is right for a
 * premises or meter file (a pasted row twice is noise). **For payments it is
 * wrong:** an exact copy of a row IS the same cheque twice, and the lockbox
 * ruling (LBX-08) is that it is flagged and HELD for a person, while L2-08 is
 * that every row is loaded or rejected. Dropped before validation, the copy
 * reached neither — 5 rows read *Loaded 3 · Rejected 1* with the fifth in no
 * tile and no list. So payments starts with the tick OFF and
 * `PAY.CHEQUE_ONCE_IN_FILE` holds the copy, named and counted. A clerk may
 * still tick it; that is their choice, made on the screen that says so.
 */
export function rowHandlingDefaultsFor(kind: WorkflowKindId): RowHandling {
  return {
    drop_exact_duplicates: kind !== "payments",
    keep_latest_on_key: false,
    skip_rows_missing_required: false,
  };
}

/**
 * ⛔ **`P1.18` — WHICH WRITE MODES THIS TARGET REFUSES, AND WHY.**
 *
 * Blueprint p068 ③, verbatim: *"Payments offers one of the two. `options` is a
 * prop, so a target chooses what it passes — and **Insert & update** would mean
 * overwriting a payment already on file, which hard rule 4 forbids outright. So
 * it is drawn **present and refused, with its reason**, rather than silently
 * absent: **a clerk who has used the premises importer will look for it.**"*
 *
 * ⚠ **READ THAT LAST CLAUSE AGAIN, BECAUSE THE OBVIOUS IMPLEMENTATION BREAKS
 * IT.** `P1.18`'s own task row says *"payments passes ONE option"*, which reads
 * as a one-element array — and a one-element array makes the second mode
 * VANISH. A clerk who has used the premises importer then hunts for a control
 * somebody removed and learns nothing. One SELECTABLE option, two DRAWN.
 *
 * ⚠ **AND THE REFUSAL IS A CLAIM ABOUT THE SERVER, NOT A STYLING CHOICE.**
 * `apps/metering/import_runs.py::_refuse_payments_write_mode` refuses this
 * target's `upsert` BY NAME, with `message_key`
 * `metering.import.payments_insert_only`. Without this, the screen offers a
 * clerk a mode the server will reject after they have chosen their file —
 * hard-won law 2's mirror, a live refusal behind a control that says nothing.
 * A lane that empties this map puts that back.
 */
export function writeModeRefusals(
  kind: WorkflowKindId,
  t: (key: string) => string,
): Partial<Record<"insert" | "upsert", string>> {
  return kind === "payments" ? { upsert: t("workflow.writeMode.paymentsInsertOnly") } : {};
}

/**
 * The same rule, asked WITHOUT a translator, so a screen can pick its INITIAL
 * mode before it has resolved any copy.
 *
 * ⚠ **IT IS DERIVED FROM `writeModeRefusals` RATHER THAN BEING A SECOND LIST**
 * (hard-won law 5, one generated source). Two lists of which modes a target
 * refuses is exactly the *"two places that can disagree"* shape this product
 * keeps meeting — and the one that would drift is this one, because it has no
 * sentence to write and therefore no reason for anyone to look at it.
 */
export function writeModeIsRefused(kind: WorkflowKindId, mode: "insert" | "upsert"): boolean {
  return writeModeRefusals(kind, () => "refused")[mode] != null;
}

/**
 * The em-dash an absent value renders as.
 *
 * ⚠ IT IS A CODE CONSTANT AND NOT A CATALOGUE KEY, on purpose: a value
 * byte-identical in eleven catalogues fails G15's untranslated-value check
 * unless it is added to the UNIVERSAL allowlist, and "—" is already there once,
 * for the shared cells. Punctuation is not copy.
 */
export const ABSENT = "—";

/**
 * THE STANDARD LABELS EVERY RUN DRAWS, AS CATALOGUE KEYS.
 *
 * ⚠ THE FIGURES ARE THE SERVER'S AND THE LABELS ARE OURS, and the split is the
 * one `KPIStrip` already makes: a tile takes a *"pre-translated label from the
 * consuming screen's catalog keys"*, so a count arrives as a number and the
 * word beside it is localised here. A server that shipped display labels would
 * put English in a Hindi screen; a screen that invented its own words would give
 * the premises run and the units run two vocabularies for one figure.
 *
 * They live in this file rather than in each screen so the tenth workflow reads
 * the same words as the first — which is the ask this kit answers.
 */
export const WORKFLOW_COPY_KEYS = {
  /** Header action, shared by every kind. */
  saveMapping: "workflow.saveMapping",
  /** Stage 1 — the radio group's accessible name. */
  sourceLegend: "workflow.source.legend",
  /** Stage 2 — `AFTER TRANSFORM`, and its three figures. */
  afterTransform: "workflow.reconcile.afterTransform",
  rowsIn: "workflow.reconcile.rowsIn",
  duplicatesDropped: "workflow.reconcile.duplicatesDropped",
  rowsForward: "workflow.reconcile.rowsForward",
  rowHandlingLegend: "workflow.rows.legend",
  /**
   * Stage 3 — the KPI strip and the two tables.
   *
   * ⚠ **FIVE TILES, AND THREE OF THE FOUR OLD LABELS ARE RETIRED — `CR-036`
   * AMENDMENT 1 (f).** The finished premises run printed *"ROWS CHECKED 9881 ·
   * PASSED CLEAN 0 · ERRORS 0 · WARNINGS 9881"* and the Product Owner read it
   * as total failure — *"it rejected and shown all error"* — over a run in
   * which **not one row was blocked**. Every number was true. `Passed clean`
   * reads as *succeeded*, so `0` beside it reads as *nothing succeeded*; and
   * the figure that answers the actual question — how many rows arrive —
   * existed nowhere on the screen.
   *
   * `workflow.kpi.passedClean`, `.errors` and `.warnings` are RETIRED with
   * their tiles and are listed for deletion in
   * `scratchpad/newkeys-IMPORTFIX.json`; the four keys below replace them and
   * are rendered with `defaultValue` until the catalogue fan-in lands.
   */
  rowsChecked: "workflow.kpi.rowsChecked",
  willLoad: "workflow.kpi.willLoad",
  willNotLoad: "workflow.kpi.willNotLoad",
  loadsWithWarning: "workflow.kpi.loadsWithWarning",
  noRemarks: "workflow.kpi.noRemarks",
  rulesCaption: "workflow.rules.caption",
  rulesEmpty: "workflow.rules.empty",
  /** (f) — reserved for a FINISHED run that ran no rules. While the worker is
   *  still checking, the true sentence is *not yet*, and it is its own key. */
  rulesStillRunning: "workflow.rules.stillRunning",
  rejectsCaption: "workflow.rejects.caption",
  rejectsEmpty: "workflow.rejects.empty",
  rejectsStillRunning: "workflow.rejects.stillRunning",
  /**
   * Stage 4 — the dry-run figures.
   *
   * ⛔ **THE FOUR WRITE-MODE ENTRIES ARE GONE — CR-042.** `modeInsert`,
   * `modeUpsert`, `modeReplace` and `modeReplaceCaution` lived here and pointed
   * at `workflow.dry.mode.*`, which no catalogue defines any more: the two
   * surviving modes moved to the ONE shared control's key set
   * (`workflow.writeMode.*`, in `WriteModeChoice.tsx`) and the third mode was
   * withdrawn by the PO.
   *
   * ⚠ **THEY ARE DELETED RATHER THAN RE-POINTED, AND THE REASON IS THIS FILE'S
   * OWN RULE.** Its docstring says a key here is *"a quoted dotted literal,
   * which is what G18 reads as a call site, so a key here that no catalogue
   * defines is caught"* — and nothing caught these, because nothing consumed
   * them either: `WORKFLOW_COPY_KEYS.mode*` had no reader anywhere in `src`.
   * A constant pointing at a deleted key, read by nobody, is the `DEF-445`
   * shape — a pointer that outlives its target and reads as working code.
   * The write mode's copy belongs to the control that draws it.
   */
  willCreate: "workflow.dry.willCreate",
  willUpdate: "workflow.dry.willUpdate",
  willReject: "workflow.dry.willReject",
  scopeAffected: "workflow.dry.scope",
  target: "workflow.dry.target",
  /** Stage 5 — the KPI strip. */
  loaded: "workflow.kpi.loaded",
  rejected: "workflow.kpi.rejected",
  flagged: "workflow.kpi.flagged",
} as const;
