// ── Trace ──────────────────────────────────────────
// Change:   the DISCONNECT WIZARD REBUILD of 2026-09-25 (`DEF-CUS-6750`…`DEF-CUS-6753`, MAINTENANCE — `12-governance/22-product-maintenance-process.md`) — **THE DISCONNECT WIZARD GOES FROM FIVE STEPS TO
//           FOUR**: `Choose · Check · Schedule · Confirm`. This file is the one
//           shape all four steps read and write.
// Rules:    **BR-CUS-1096** (a protection WARNS and never refuses) ·
//           **BR-CUS-1097** (the balance need not be clear to reconnect;
//           supersedes `BR-CUS-104`'s gate clause) · **BR-CUS-1098** (a master
//           account's cut is a building's cut; an occupant's protection warns) ·
//           **BR-CUS-1099** (no recorded proof of certified service WARNS) ·
//           **BR-CUS-1100** (the block marks the ACCOUNT and the CUSTOMER) ·
//           BR-CUS-103/105 · BR-BIL-007 · B14 rules 20, 21, 31, 33, 41, 42, 43,
//           44
// Tests:    ../DisconnectWizard.test.tsx
// ─────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · EVERY COLLECTION ON THIS WIZARD IS A TABLE ARRAY, AND THAT IS WHY THE
//     DRAFT IS ARRAYS OF ROWS RATHER THAN PARALLEL RECORDS
// ══════════════════════════════════════════════════════════════════════════
// The four drawings (`Step1Choose` · `Step2Check` · `Step3Schedule` ·
// `Step4Confirm`, and their four master variants) draw the SAME shape four
// times: a panel, a heading, a right-hand fact, a table whose rows the clerk
// may add to and remove from, an `+ Add a …` button and a running fact beside
// it. Services, checks, service points and notice recipients are all that one
// shape.
//
// ⚠ **THE PREVIOUS DRAFT HELD `treatments` AS A `Record` AND NOTHING ELSE**, so
// a service the clerk removed could only be expressed as an ABSENT KEY — which
// is indistinguishable from a service the account never had. A table array
// needs an ORDER and needs to hold a row whose value is not yet chosen, and a
// record holds neither. `scheduleCutPlanOf` still hands the server the record
// shape it demands; the record is DERIVED at the moment of the write and is no
// longer the thing the screen edits.
//
// ⚠ **`hydrateForm` CANNOT TELL AN ARRAY FROM AN OBJECT** — it compares
// `typeof`, and both are `"object"` — so a parked draft carrying
// `serviceRows: {}` would survive it and then crash `.map`. `hydrateDraft`
// below is `hydrateForm` plus that one coercion, and it is why this module
// exports a hydrator of its own rather than calling the shared one directly.
import { hydrateForm } from "../wizardPark";
import type { ScheduleCutPlan } from "../transferDisconnectEndpoints";
import { DEPOSIT_HELD, TREATMENT_FULL, TREATMENT_LEAVE } from "../transferDisconnectShared";
import type { DepositDisposition, ServiceTreatment } from "../transferDisconnectShared";

// ══════════════════════════════════════════════════════════════════════════
// 2 · THE MARK ON A CHECK — `Recorded` · `Checked` · `Not required`
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **IT IS THE CLERK'S OWN CHECKLIST AND NOTHING ON IT IS MANDATORY.** The
// product answers three of the checks itself (`protection_check`); the rest are
// questions a person asks somebody and then records having asked. A check with
// no mark is a check nobody has got to, and Continue does not care — which is
// the whole of item 3.4 and is the same posture `BR-CUS-1096` takes one level
// up: the screen states what is true and does not stop the clerk.
//
// ⚠ **`Not required` IS A RECORDED DECISION AND NOT AN ABSENCE.** Before this
// rebuild a clerk could not say *this one does not apply here* anywhere in the
// product, so the only way past a check that did not apply was to leave it
// blank — which reads identically to having forgotten it.
export const MARK_RECORDED = "recorded";
export const MARK_CHECKED = "checked";
export const MARK_NOT_REQUIRED = "not_required";

/** The three marks, in the drawn order of the `MARK` column's dropdown.
 *  ⚠ **`Recorded` IS `B14` RULE 34's WORD** — *held here* is **Recorded**
 *  everywhere, in all eleven catalogues — so it is spelled that way and not
 *  *On file*, which is what the drawing's ANSWER cell happens to say about a
 *  certificate. Those are two different facts in two different columns. */
export const CHECK_MARKS = [
  { code: MARK_RECORDED, en: "Recorded" },
  { code: MARK_CHECKED, en: "Checked" },
  { code: MARK_NOT_REQUIRED, en: "Not required" },
] as const;

export type CheckMark = (typeof CHECK_MARKS)[number]["code"] | "";

/**
 * **THE SIX CHECKS A DISCONNECT ARRIVES WITH**, in `Step2Check.png`'s own
 * order, with *Four more available* beside the add button — which is `10 − 6`
 * and is COUNTED rather than typed.
 *
 * ⚠ **THE TABLE MUST NOT ARRIVE EMPTY, AND IT DID.** Measured in Chromium on
 * 2026-09-25: step 2 rendered its heading, its add button and NO ROWS, so a
 * clerk arrived at the most safety-critical step in this product and was shown
 * nothing to check. `data-editable-empty` was there and every unit case passed,
 * because each one handed the step its own rows. **Only the browser saw it** —
 * hard-won law 6, and the reason the walk exists.
 *
 * ⚠ **WHY THESE SIX AND NOT ALL TEN.** Four are what `protection_check`
 * actually answers (medical · weather moratorium · payment plan · open dispute,
 * the last as `unavailable`). `notice_served` and `life_support` are drawn
 * beside them because a clerk asks those two of somebody and records having
 * asked — which is what the MARK column is for. The other four are one click
 * away and nothing is hidden: `+ Add a check` offers them and says how many
 * there are.
 */
export const SEEDED_CHECKS: readonly string[] = [
  "medical",
  "moratorium",
  "payment_plan",
  "dispute",
  "notice_served",
  "life_support",
];

/** The six seeded rows, unmarked. ⚠ **UNMARKED IS THE POINT** — a mark says a
 *  person looked, and nothing may say that on the clerk's behalf. */
export function seededChecks(): DisconnectCheckRow[] {
  return SEEDED_CHECKS.map((code) => ({ code, mark: "" as CheckMark }));
}

/** A row of step 2's `What was checked`. `code` keys into `PROTECTION_CHECKS`
 *  for the label and into `protection_check`'s answer for the ANSWER cell. */
export interface DisconnectCheckRow {
  code: string;
  mark: CheckMark;
}

// ══════════════════════════════════════════════════════════════════════════
// 3 · THE VISIT ON A SERVICE POINT
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **`BR-CUS-1098`: A MASTER ACCOUNT GETS ONE WORK ORDER PER AFFECTED SERVICE
// POINT**, which may be twenty-five. That is why step 3's table is keyed by
// SERVICE POINT rather than by service — the regular case has one point per
// service and reads identically, and the master case is the reason the column
// is not called *Service*.
export const VISIT_WORK_ORDER = "work_order";
export const VISIT_NONE = "no_visit";

export const VISIT_KINDS = [
  { code: VISIT_WORK_ORDER, en: "Work order" },
  { code: VISIT_NONE, en: "No visit" },
] as const;

export type VisitKind = (typeof VISIT_KINDS)[number]["code"] | "";

/** A row of step 3's `Who goes`. `point` is the DISPLAY key the row was built
 *  from — a service code for a regular account, a service code plus the
 *  building/units split for a master. ⚠ It is never a database id (B14 rule
 *  31); `label` is what a clerk reads and `point` is what the row is keyed by. */
export interface DisconnectVisitRow {
  point: string;
  label: string;
  meter: string;
  visit: VisitKind;
  instruction: string;
  /** The work order this row has already raised, `""` while none has been.
   *  ⚠ **NOTHING IN THIS LANE RAISES ONE** — see `ScheduleStep`'s §3. */
  workOrder: string;
}

/** A row of step 1's `Which services`. */
export interface DisconnectServiceRow {
  code: string;
  /** Drawn `METER` on a regular account and `POINTS` on a master — one column,
   *  two questions, and the step decides which it is asking. */
  meter: string;
  treatment: ServiceTreatment | "";
  /** The drawn `NOTE` / `WHO IT REACHES` cell. Derived on the master variant
   *  from the occupant count; `""` on a regular account, which draws `—`. */
  note: string;
}

/** A row of step 3's master-variant `Notice` table — `WHO IS NOTIFIED · HOW
 *  MANY · HOW IT IS SERVED · PROOF REFERENCE`.
 *
 *  ⚠ **IT IS `…RecipientRow` AND NOT `…NoticeRow` FOR A REASON WORTH A LINE:**
 *  `disconnect/disconnectNotices.ts` already exports a `DisconnectNoticeRow`,
 *  which is the SERVER's row for a notice that has been sent. Two types one
 *  import apart, both about notices, with one name between them is how a screen
 *  reads a sent letter as a recipient it is about to add. */
export interface DisconnectRecipientRow {
  audience: string;
  count: number;
  channel: string;
  reference: string;
}

/** `WHO IS NOTIFIED`'s two drawn values. A third would be a new fact about who
 *  a utility must tell, which is a ruling rather than a string. */
export const AUDIENCE_OWNER = "owner";
export const AUDIENCE_OCCUPANTS = "occupants";

// ══════════════════════════════════════════════════════════════════════════
// 4 · THE DRAFT
// ══════════════════════════════════════════════════════════════════════════

export interface DisconnectDraft {
  /** The account whose service is being cut, found through the PUBLISHED search
   *  (`BR-CUS-053`) by account number, customer name, service address or meter. */
  accountId: string;
  /** One of `CUT_REASONS`. Nothing branches on it; `schedule_cut` records it. */
  reason: string;
  /** Step 1's table array. */
  services: DisconnectServiceRow[];
  /** Step 2's table array. */
  checks: DisconnectCheckRow[];
  /**
   * Step 2's `What happened`.
   *
   * ⚠ **IT IS KEPT — ITEM 3.13.** The five-step wizard drew this box, took what
   * the clerk typed and threw it away: nothing on the draft held it and nothing
   * in the commit sent it. It is draft data now and it travels with the
   * schedule, which is the same move `CR-125-BRC07` made for the proof of
   * service and for the same reason.
   */
  whatHappened: string;
  /** `Scheduled cut date`. REQUIRED, and Continue says so by name — item 3.6. */
  cutOn: string;
  /** Step 3's `Who goes` table array. */
  visits: DisconnectVisitRow[];
  /** Step 3's master-variant `Notice` table array; empty on a regular account,
   *  whose notice is a form rather than a table (both are drawn). */
  recipients: DisconnectRecipientRow[];
  /** Step 4's `What happens to it`. ● **Hold it** is the default and is the
   *  option that moves no money. */
  deposit: DepositDisposition;
  /** The proof of certified service, as draft data. */
  proof: DisconnectProof;
}

/**
 * `DSC-02.3`'s `Proof that it was served`, as data rather than as a write.
 *
 * ⚠ `servedOn` is REQUIRED BY THE SERVER and is drawn NOWHERE; `signedForOn`
 * is optional. A certified item is posted on one day and signed for on another
 * and the statutory period counts from the FIRST, so copying one date into both
 * would manufacture a legal date.
 *
 * ⚠ **AND UNDER `BR-CUS-1099` AN EMPTY PROOF NO LONGER BLOCKS.** PO 2026-09-25,
 * verbatim: *"So we warn user , but we dont stop user"*. The screen asks for it
 * and warns when it is absent. See `ScheduleStep`'s §2 for what the server
 * still does, which is a different statement from what the screen does.
 */
export interface DisconnectProof {
  channel: string;
  reference: string;
  servedOn: string;
  signedForOn: string;
}

export function emptyDisconnectProof(): DisconnectProof {
  return { channel: "", reference: "", servedOn: "", signedForOn: "" };
}

/** Whether the clerk has typed everything `record_proof_of_service` requires.
 *  `signedForOn` is deliberately NOT here — `BR-CUS-100` makes it optional and
 *  the server does not read it. */
export function proofIsComplete(proof: DisconnectProof): boolean {
  return proof.channel !== "" && proof.reference.trim() !== "" && proof.servedOn !== "";
}

/** Whether the clerk has STARTED a proof. A half-typed one must fail the commit
 *  loudly rather than be dropped — dropping it is how a legal attestation
 *  silently does not happen. ⚠ **THIS IS NOT `BR-CUS-1099`'s CASE.** That
 *  ruling is about an EMPTY proof, which now warns and proceeds; this is about
 *  a HALF-TYPED one, which the server would refuse field by field. */
export function proofIsStarted(proof: DisconnectProof): boolean {
  return (
    proof.channel !== "" ||
    proof.reference.trim() !== "" ||
    proof.servedOn !== "" ||
    proof.signedForOn !== ""
  );
}

export function emptyDisconnectDraft(): DisconnectDraft {
  return {
    accountId: "",
    reason: "",
    services: [],
    checks: [],
    whatHappened: "",
    cutOn: "",
    visits: [],
    recipients: [],
    deposit: DEPOSIT_HELD,
    proof: emptyDisconnectProof(),
  };
}

/**
 * `hydrateForm` plus the coercion it cannot make.
 *
 * ⚠ **`typeof [] === typeof {} === "object"`**, so the shared hydrator will
 * happily put a parked `{}` into a field the screen then calls `.map` on.
 * Under `BR-SHL-048` (b) a parked draft is evidence of TYPING and of nothing
 * else, so anything that is not an array of the right shape is dropped back to
 * the empty draft's `[]` rather than repaired.
 */
export function hydrateDraft(parked: unknown): DisconnectDraft {
  const empty = emptyDisconnectDraft();
  const out = hydrateForm(empty, parked);
  const fields = out as unknown as Record<string, unknown>;
  for (const key of ["services", "checks", "visits", "recipients"] as const) {
    if (!Array.isArray(out[key])) {
      fields[key] = [];
    }
  }
  if (typeof out.proof !== "object" || out.proof === null || Array.isArray(out.proof)) {
    out.proof = emptyDisconnectProof();
  } else {
    out.proof = hydrateForm(emptyDisconnectProof(), out.proof);
  }
  return out;
}

// ══════════════════════════════════════════════════════════════════════════
// 5 · WHAT THE COMMIT SENDS
// ══════════════════════════════════════════════════════════════════════════

/** The treatments record `schedule_cut` demands, derived from the table array.
 *
 *  ⚠ **A ROW WITH NO TREATMENT CHOSEN IS LEFT OUT RATHER THAN DEFAULTED.** A
 *  blank cell means the clerk has not decided, and defaulting it either way
 *  would decide for them — one direction cuts a service nobody asked to cut. */
export function treatmentsOf(draft: DisconnectDraft): Record<string, ServiceTreatment> {
  const out: Record<string, ServiceTreatment> = {};
  for (const row of draft.services) {
    if (row.treatment !== "" && row.code !== "") {
      out[row.code] = row.treatment;
    }
  }
  return out;
}

/** What step 4's commit sends. `schedule_cut`'s own keyword arguments. */
export function scheduleCutPlanOf(draft: DisconnectDraft): ScheduleCutPlan {
  // ⚠ `DEF-CUS-9631` — THE ROWS STEP 3 COUNTS ARE THE ROWS THE COMMIT SENDS.
  // The confirm step said *1 work orders will be raised* and this plan carried
  // none, so the server raised none. `point` is the service code the row was
  // seeded from (an added row has none, and the server then uses the
  // account's services).
  const visits = draft.visits
    .filter((row) => row.visit === VISIT_WORK_ORDER)
    .map((row) => ({ service: row.point.trim() === "" ? null : row.point, instruction: row.instruction.trim() }));
  return {
    account_id: draft.accountId.trim(),
    cut_on: draft.cutOn,
    reason: draft.reason === "" ? null : draft.reason,
    services: treatmentsOf(draft),
    deposit: draft.deposit,
    ...(visits.length > 0 ? { visits } : {}),
  };
}

/** The services marked for a full cut. */
export function servicesCut(draft: DisconnectDraft): string[] {
  return draft.services
    .filter((row) => row.treatment === TREATMENT_FULL)
    .map((row) => row.code)
    .sort();
}

/** The services the clerk has chosen to leave on. */
export function servicesLeft(draft: DisconnectDraft): string[] {
  return draft.services
    .filter((row) => row.treatment === TREATMENT_LEAVE)
    .map((row) => row.code)
    .sort();
}

/** How many work orders step 3 will ask for — the running fact beside
 *  `+ Add a service point`. */
export function workOrderCount(draft: DisconnectDraft): number {
  return draft.visits.filter((row) => row.visit === VISIT_WORK_ORDER).length;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: the DISCONNECT WIZARD REBUILD of 2026-09-25 (`DEF-CUS-6750`…`DEF-CUS-6753`, MAINTENANCE — `12-governance/22-product-maintenance-process.md`) · BR-CUS-1096 · BR-CUS-1097 · BR-CUS-1098 ·
//         BR-CUS-1099 · BR-CUS-1100 · BR-CUS-100 · BR-CUS-103 · BR-CUS-105 ·
//         BR-BIL-007 · BR-SHL-048 · B14 rules 33, 34, 43
// generated: 2026-09-25 by lane WIZARD
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
