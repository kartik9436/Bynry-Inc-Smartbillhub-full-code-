// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-016 · US-RBS-001 · CR-075 wave C task C3 — `RBS-004`, the
//          setup renderer over a definition.
// Screens: RBS-004.1 … RBS-004.7 (seven tabs; the sheets and their frames).
// Rules:   `BR-RBS-012` (guards are absolute) · `BR-RBS-002` (a Check is
//          constructed with no writer) · `BR-RBS-042` (a tenant sets input
//          VALUES and nothing else) · B14 rule 31 (no database id is ever the
//          visible value of a field) · B14 rule 32 (description budget).
// Defects: DEF-RBS-4285 (this file's `why` and `summary` have no field behind
//          them yet) · DEF-RBS-4284 (the same drift, one level down).
// ───────────────────────────────────────────────────────
// THE SHAPE `RBS-004` DRAWS, AND WHY IT IS A VIEW MODEL RATHER THAN THE
// DEFINITION ITSELF.
//
// `08-screen-layouts.md`: *"`RBS-004` and `RBS-006` are RENDERERS, not pages.
// `RBS-004` renders a runbook's definition … Neither knows anything about a
// particular runbook: both read a declaration."* `RB-020`'s whole claim — that
// adding runbook 23 needs one Python module and NO frontend code — rests on
// this file being closed over all 26 setup renderers, so nothing here may name
// a runbook, a port, a category or a step.
//
// ══════════════════════════════════════════════════════════════════════════
// WHICH HALF IS DATA AND WHICH HALF IS CHROME — ONE RULE, APPLIED THROUGHOUT
// ══════════════════════════════════════════════════════════════════════════
// **A row whose LABEL is the same for all 26 runbooks is chrome and is
// translated in the screen. A row whose label VARIES by runbook is data and
// arrives already in the reader's language.**
//
// So `Schedule`, `Last run`, `Limits` carry chrome labels and data values —
// every runbook has a *Time zone* and a *Most per run*. `Scope` carries DATA
// labels, because those rows are the runbook's own `Parameter.label`s
// (`BR-RBS-042`: the inputs are the only thing a tenant sets), and *Accounts
// included · Services · Cycles · Account types* is runbook 8's list and nobody
// else's. Guards and steps are the same: `Guard.label` and `Step.label` are the
// definition's words.
//
// Getting this backwards in either direction is a real defect rather than a
// preference. Chrome pushed into the view model ships untranslatable English
// from a Python module; data pulled into the screen puts runbook 8's parameter
// names into a file that runbook 20 also renders.
//
// ══════════════════════════════════════════════════════════════════════════
// TWO FIELDS HERE HAVE NO ENGINE FIELD BEHIND THEM — `DEF-RBS-4285`
// ══════════════════════════════════════════════════════════════════════════
// `SetupStep.why` and `ActivityEntry.summary` are drawn in the FRAMES and
// declared NOWHERE in the contract. `contract.py`'s `Step` is
// `key · label · mode · run · writes`; `models.py`'s `RunbookVersion` is
// `definition (jsonb) · changed_by · changed_at`. Both dataclasses are correct
// on their own terms and every construction test passes over them, which is why
// the gap is only visible with the frame beside the code — the same comparison
// `DEF-RBS-4284` made one level down on the report payloads.
//
// **This file declares the shape the sheets require and invents neither
// field.** `why` is OPTIONAL and an absent one draws no line at all — never a
// placeholder, never a guess. `summary` is REQUIRED, so the Activity tab cannot
// be served without one and the gap fails loudly at the seam rather than
// quietly on the screen.

/** A key–value row: the shape every `PlainTable (Surfaces)` region draws.
 *
 *  ⚠ `label` and `value` are BOTH already in the reader's language. A row that
 *  needs a pill passes one as `value`; the renderer never inspects a string to
 *  decide whether it is a status. */
import type { SettingsFieldRow } from "./setupScope";

export interface SetupRow {
  /** Stable across renders. A React key and a walkthrough handle — **never
   *  rendered**, so B14 rule 31 holds by construction rather than by care. */
  id: string;
  label: string;
  value: SetupValue;
}

/** What sits on the right of a key–value row. Three shapes and no more: the
 *  sheets draw plain text, a status pill, and the stated absence. */
export type SetupValue =
  | { kind: "text"; text: string }
  | { kind: "pill"; label: string; tone: SetupTone }
  /** Settings has no value / the server sent none. The renderer draws the
   *  screen's own *Not set* rather than an empty cell, because an empty cell
   *  and a zero look identical and only one of them is a fact. */
  | { kind: "absent" };

/** The pill tones these seven tabs use. A subset of `StatusPill`'s six, named
 *  here so a view model cannot ask for one the sheets never draw. */
export type SetupTone = "success" | "warning" | "danger" | "neutral";

/** One step on the Steps tab (`RBS-004.2`). */
export interface SetupStep {
  id: string;
  /** `Step.label` — *Find accounts past due*. */
  label: string;
  /** The line under the title — *Balance over $5.00, due date passed*.
   *
   *  ⚠ **OPTIONAL BECAUSE THE CONTRACT HAS NOWHERE TO PUT IT** (`DEF-RBS-4285`).
   *  Absent draws NOTHING: no line, no dash, no placeholder. A placeholder here
   *  would be a screen inventing a fact, and the whole point of the line is
   *  that it is the rule that decides the step (`BR-RBS-010`). */
  why?: string;
  /** `Step.writes`. Drives the mono `read` / `writes` marker on the right, and
   *  nothing else — a step does not become dangerous by being drawn in red. */
  writes: boolean;
}

/** One row of *This can* (`RBS-004.1` region 9).
 *
 *  ⚠ **DERIVED FROM `ports[]`, AND DERIVED ON THE SERVER.** `08-screen-layouts.md`:
 *  *"**This can* states capability, not intention, and it is derived from the
 *  ports the runbook holds** … Nobody types it."* The port → capability map is
 *  written down NOWHERE in the pack: three rows are drawn against the thirteen
 *  ports `12-the-contract.md` §8 names, and one of the three — *Change bills* —
 *  maps to no port at all. Inventing that map in the front end would resolve an
 *  unstated design question by choosing a value AND break `RB-020`, because a
 *  fourteenth port would then need a frontend change. See the decision log,
 *  2026-09-06. */
export interface SetupCapability {
  id: string;
  /** *Send notices* · *Charge fees* · *Change bills* — already translated. */
  label: string;
  can: boolean;
}

/** One guard (`RBS-004.4`). `BR-RBS-012`: absolute, evaluated before any step,
 *  and it cannot be switched off — so there is no `enabled` field to set. */
export interface SetupGuard {
  id: string;
  /** `Guard.label` — *Medical protection*. */
  label: string;
}

/** One run on the Runs tab (`RBS-004.6`). */
export interface SetupRun {
  id: string;
  /** Already formatted in the tenant's zone and format (`BR-SHL-023` keeps ONE
   *  formatting path; a second one here is how a screen and an envelope end up
   *  disagreeing about a date). */
  when: string;
  outcome: { label: string; tone: SetupTone };
  /** *Acted* — right-aligned, tabular. `null` for a run that has not acted, and
   *  the sheet draws `—` for it rather than `0`: a run waiting has not acted on
   *  nobody, it has not acted yet. */
  acted: number | null;
}

/** One change on the Activity tab (`RBS-004.7`) — the tab an auditor asks for
 *  first. */
export interface SetupActivityEntry {
  id: string;
  /** `4` renders as `v4`. **A version number is a human-facing number under
   *  B14 rule 31's own escape clause** (`08-screen-layouts.md` says so in those
   *  words); the row's database id is the `id` above and is never drawn. */
  version: number;
  /** *Cap raised to 400* — ⚠ **no engine field carries this** (`DEF-RBS-4285`).
   *  REQUIRED so the gap fails at the seam rather than on the screen. */
  summary: string;
  /** *Dana W.* — a person's name, never a user id (B14 rule 31). */
  actor: string;
  /** *2 Sep* — already formatted, for the reason `SetupRun.when` gives. */
  when: string;
}

/** Everything `RBS-004` draws. One object, seven tabs, no runbook named. */
export interface RunbookSetupView {
  /** The URL slug — `collections-ladder`.
   *
   *  ⚠ **A SLUG IS NOT A DATABASE ID.** B14 rule 31 bans the id; `key` is the
   *  address a person can read, type and share, and it is what every route in
   *  `08-screen-layouts.md` is written with. The runbook's UUID is not on this
   *  interface at all — a field that does not exist cannot be rendered by
   *  accident, which is a stronger guarantee than a rule somebody polices. */
  key: string;
  /** *Collections ladder* — the H1. */
  name: string;
  /** `check` or `action`. Drives the *This can* absence sentence: a Check holds
   *  no ports at all (`BR-RBS-002`), so *nothing* is not an empty list, it is
   *  the safety promise, and the screen says so. */
  kind: "check" | "action";
  /** *Collections* — the category chip beside the subtitle, already translated. */
  category: string;
  /** *Sends the notice each account is due.* ONE sentence (B14 rule 32).
   *
   *  ⚠ **OPTIONAL SINCE WAVE `E4`, BECAUSE NOTHING SERVES IT** (`DEF-RBS-4309`).
   *  `RunbookDefinition` has no field for the card sentence at all — it is drawn
   *  on six cards of `RBS-002.1`, as the subtitle of `RBS-002.2`, and here — so
   *  a REQUIRED field would have forced the mapper to invent one. Absent draws
   *  NOTHING: no line, no dash, no placeholder, and the page head keeps its
   *  category chip. Same rule and the same reason as `SetupStep.why`. */
  purpose?: string;
  /** Drives **Pause** / **Resume**. */
  paused: boolean;

  /** `RBS-004.1` regions 4–5 — *Runs · Time zone · Next*. */
  schedule: { runs: SetupValue; timeZone: SetupValue; next: SetupValue };
  /** `RBS-004.1` regions 6–7 — *When · State · Planned*. `null` when the
   *  runbook has never run, and the renderer says so in one sentence rather
   *  than drawing three empty rows. */
  lastRun: { when: SetupValue; state: SetupValue; planned: SetupValue } | null;
  /** `RBS-004.1` regions 8–9 — *This can*. Empty for a Check, and that emptiness
   *  is drawn, not skipped. */
  capabilities: readonly SetupCapability[];

  /** `RBS-004.2`. */
  steps: readonly SetupStep[];
  /** The read-only note under the step list, when this runbook draws one.
   *
   *  ⚠ **THE SENTENCE IS THE SCREEN'S, THE DESTINATION IS THE DATA.** The frame
   *  writes *"Tier days and amounts are not edited here"* — eight words, and
   *  B14 rule 33 caps a refusal at five or six. The rule wins and the
   *  divergence is stamped in `08-screen-layouts.md`; only `to` comes from
   *  here, because only the destination varies by runbook. */
  settingsOwned: { to: string } | null;

  /** `RBS-004.3` region 2 — the runbook's own parameters (`BR-RBS-042`),
   *  every one EXCEPT those Settings owns. */
  scope: readonly SetupRow[];
  /** The `ref:setting` inputs — drawn read-only with a link to Settings, and
   *  with the value SETTINGS holds (`OQ-WRK-12793` → A, PO 2026-10-13). Never
   *  in `scope`, because a `scope` row's value is the runbook's own declared
   *  default for these, which is not the setting (`DEF-WRK-10122`). */
  settingsFields: readonly SettingsFieldRow[];
  /** *Matches 1,004 accounts today* — `resolve(params)`'s live count. `null`
   *  when it has not been computed, and then no note is drawn: a FACT line with
   *  no fact is worse than no line. */
  scopeMatches: number | null;

  /** `RBS-004.4` region 2. */
  guards: readonly SetupGuard[];

  /** `RBS-004.5` region 2 — *Most per run · Approval · Fees · Who can approve*.
   *  Chrome labels, data values, in that fixed order. */
  limits: {
    mostPerRun: SetupValue;
    approval: SetupValue;
    fees: SetupValue;
    whoCanApprove: SetupValue;
  };

  /** `RBS-004.6`. The CURRENT PAGE only — this list pages SERVER-SIDE (`NFR-3`,
   *  and CLAUDE.md's opening paragraph makes that flexibility the deliverable
   *  rather than the background). The renderer slices nothing. */
  runs: {
    rows: readonly SetupRun[];
    /** The server's total. `null` until the first response. */
    total: number | null;
    page: number;
    per: 50 | 100 | 200 | 500 | 1000;
    loading: boolean;
  };

  /** `RBS-004.7`, newest first. */
  activity: readonly SetupActivityEntry[];
}
