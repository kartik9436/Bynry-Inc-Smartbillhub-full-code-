// ── Trace ──────────────────────────────────────────────
// Change:   CR-126-BRC07 — the NEW CONNECT BUILD RECORD, drawn on blueprint
//           p098–p099 (Overview) and read as IMAGES per B14 rule 42.
// Rules:    `OQ-MET-12520` CLOSED on option C and CONFIRMED by the PO
//           (decision log 2026-09-20, commit `8cb9a379c`): *"MAKE THE BUILD
//           TAB COMPLETE."* ⛔ There is NO `/connections/{no}` screen — the
//           drawn record's CONTENT lands on the property's Build tab as
//           SECTIONS, and only the drawing's ADDRESS and TAB STRIP are
//           superseded · B14 rule 43 (a piece of UI is a COMPONENT; these
//           types are what make the sections importable rather than inline) ·
//           B14 rule 31 (no database id is ever a visible value — every
//           identifier below is a BUSINESS number: `CX-26-0007`, `PR-0731`,
//           `SR-26-0001`) · CLAUDE.md hard rule 8 (an address lives on
//           `premises`; `BuildPremise` is DERIVED by walking and is never
//           stored on the build) · CLAUDE.md hard rule 2 (money is a STRING,
//           stored to 4dp, displayed at 2)
// ───────────────────────────────────────────────────────
/**
 * The shape the drawn build record reads, section by section.
 *
 * ⚠ **EVERY FIELD IS NULLABLE ON PURPOSE, AND THAT IS THE POINT OF THIS FILE.**
 * The record read that serves these does not exist yet. The panels are written
 * against this type TODAY and mounted TODAY, so each one is wired rather than
 * dead (CLAUDE.md hard-won law 2, `G13`) — a field with no source arrives as
 * `null` and the panel draws the STATED ABSENCE the blueprint itself draws
 * (`— not yet`, `— not given`). When the read lands, the only change is that
 * more props are passed: no panel is restructured and no markup moves.
 *
 * ⚠ **A `null` HERE MEANS *NOT ANSWERED*, NEVER *ZERO* AND NEVER *EMPTY*.**
 * That is `DEF-075`'s posture, and it is why money is `BuildMoney | null`
 * rather than a string defaulting to `"0.00"`: a quote nobody has priced and a
 * quote priced at nothing are different facts, and `$0.00` over a null is the
 * defect `DEF-127` was filed for.
 *
 * ⚠ **NO FIGURE DRAWN ON THE BLUEPRINT IS A FACT TO BUILD TO** (B14 rule 37).
 * `7` units, `3 of 7` activated and `$3,030.00` are ILLUSTRATIONS. This file
 * declares the SHAPE those numbers arrive in and asserts nothing about them.
 */
import type { BuildMoney } from "../workEndpoints";

/** A counted pair the blueprint draws as `3 of 7`. */
export interface BuildCount {
  done: number;
  total: number;
}

/**
 * `LIVE STATE`, blueprint p098 lower-left / p099 upper-left.
 *
 * Six drawn rows, in the drawn order: State · Waiting on · Units activated ·
 * Service points live · Target activation · Activated at.
 */
export interface BuildLiveState {
  /** The build's own state token — rendered through the shared pill, never raw. */
  state: string;
  /** What the build is blocked on, in the clerk's words. `null` = nothing blocking. */
  waitingOn: string | null;
  unitsActivated: BuildCount | null;
  servicePointsLive: BuildCount | null;
  /** ISO date. Rendered through `DateCell` so the tenant's format decides. */
  targetActivation: string | null;
  /** ISO datetime, `null` until a build actually completes. No build ever has. */
  activatedAt: string | null;
}

/**
 * `OWNER AND SCOPE · STEP 1`, blueprint p099 left column.
 *
 * ⚠ **FIVE OF THESE SIX HAVE NO COLUMN ON THE BUILD TODAY** — measured in
 * `12-governance/28-new-connect-measured-2026-09-21.md` §3. `mode` is the one
 * that is served. The rest arrive `null` and draw their absence.
 */
export interface BuildOwnerScope {
  ownerType: string | null;
  /** The owner or developer's NAME — this is also the record's drawn title. */
  ownerName: string | null;
  prefix: string | null;
  externalReference: string | null;
  scope: string | null;
  /**
   * How the work is done, DERIVED from the build's work orders —
   * `connection_mode()`. One mode across every order → that mode; more than
   * one → `"mixed"`; **no orders yet → `null`** (`DEF-MET-7691`: this line
   * said `null` meant *the orders disagree*, and the panel was built to that
   * misreading).
   */
  mode: string | null;
  /**
   * What step 1 ANSWERED — `connections.mode`, the build's own stamp. Read
   * when `mode` is `null`, because a build with no orders has nothing to
   * derive from and the stamp is the only truth there is.
   */
  modeRecorded: string | null;
  /** ⊕ `CR-164-BRC10` wave 4 — the single-family owner's account: it holds
   *  the home (`lives_there`) or only pays (`billing_only`); `null` otherwise. */
  ownerAccountRole?: "lives_there" | "billing_only" | null;
}

/**
 * `THE PREMISE · STEP 2`, blueprint p098 lower-right / p099 upper-right.
 *
 * ⚠ **DERIVED BY WALKING TO `premises`, NEVER STORED ON THE BUILD** —
 * CLAUDE.md hard rule 8, `BR-MET-1161`: *"we are having addresses at one place
 * now — Premises and Units."* The blueprint says the same thing in its own
 * note under this block, and that note is RATIONALE, so it is ZERO WORDS ON
 * SCREEN (B14 rule 33) and lives here instead.
 */
export interface BuildPremise {
  premiseType: string | null;
  street: string | null;
  /** The drawn row reads *"units are named on the next tab"* when absent. */
  unitLabel: string | null;
  city: string | null;
  /** The administrative state (`TX`), NOT the build's state. */
  region: string | null;
  postalCode: string | null;
  parcelReference: string | null;
  readRoute: string | null;
  /** The premises BUSINESS number (`PR-0731`) — never the uuid (rule 31). */
  premisesNumber: string | null;
}

/**
 * `WHERE IT CAME FROM`, blueprint p099 lower-right.
 *
 * ⚠ **A REQUEST IS PROVENANCE, NEVER A DEPENDENCY** — `CR-126-BRC07` §2, PO
 * verbatim: *"this request is new work and recognized seperately from
 * applciation and hence we should not make it dependent on applciation #"*. So
 * `requestNo` is `null` for a build raised directly, and that is an ordinary
 * build rather than a broken one.
 */
export interface BuildProvenance {
  /** `SR-26-0001` — the business number, never the uuid. */
  requestNo: string | null;
  /** ISO date the request was approved. */
  requestApprovedOn: string | null;
  /** ⚠ NO SOURCE ANYWHERE today — measured §3. Always `null` until one exists. */
  approvedBy: string | null;
  createdAt: string | null;
  feeOutstanding: BuildMoney | null;
}

/**
 * The header strip, blueprint p098.
 *
 * ⚠ **THE TITLE IS THE OWNER'S NAME, NOT THE PROPERTY.** That is the drawing
 * and the PO confirmed it element by element on 2026-09-21. On the Build tab
 * the page head already belongs to the PREMISES, so this renders as a SECTION
 * heading and not at `32px` — B14 rule 40 governs the page head, which is not
 * this.
 */
export interface BuildRecordIdentity {
  /** `CX-26-0007`. Never the uuid (rule 31). */
  connectionNo: string | null;
  requestNo: string | null;
  ownerName: string | null;
  /** `Apartment block` — the customer-class chip. ⚠ NO SOURCE today (§3). */
  premiseType: string | null;
  state: string;
  waitingOn: string | null;
  targetActivation: string | null;
  /** Service tokens (`electric`, `water`, `sewer`) — DERIVED, never hand-typed. */
  services: string[];
}

/**
 * What the blocking banner needs to NAME THE JOB, blueprint p098.
 *
 * ⚠ **THE BANNER IS USELESS WITHOUT `orderNo`** — the drawing's whole point is
 * that it names `WO-26-0309` and sends the reader to it. A banner that says
 * something is blocked without saying WHICH job is the shape the PO rejected.
 * So the component renders NOTHING when there is no order to name, rather than
 * a vaguer sentence.
 */
export interface BuildGate {
  /** `WO-26-0309` — the work order that gates activation. */
  orderNo: string | null;
  /** How many units the gate is holding. */
  unitsHeld: number | null;
}
