// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-007 (S28 steps 1–2 — batch context, CSV upload & column
//           mapping, incl. manual entry) · US-MET-008 (steps 3–4 — the
//           validation run and per-row dispositions) · US-MET-009 (duplicate
//           -vs-committed and replace-as-correction) · US-MET-010 (step 5 —
//           the compliance stamp and the atomic commit) · US-MET-017 (one row
//           per channel)   Screens: S28 (entered from S25, feeds S25/S29)
// Rules:    BR-MET-012 (import is STAGED — no meter_reads row exists until the
//           step-5 commit) · BR-MET-013 (mapping auto-detects by header,
//           re-detected on every upload) · BR-MET-014 (batch tags inherit to
//           every row unless a column overrides it) · BR-MET-015 (severity
//           model: errors MUST be resolved, warnings may be accepted only with
//           a recorded reason) · BR-MET-017 (the permanent compliance stamp) ·
//           BR-MET-018 🔒 (file+tags idempotency — an identical re-submission
//           is BLOCKED, OQ-044 closure option b) · BR-MET-032 (ONE published
//           template, validate THEN accept, no mapping memory) · BR-MET-052
//           (the VEE catalog) · BR-MET-054 (Cancel DISCARDS; the record is
//           retained for audit) · BR-MET-055 (imports run async — NOT true on
//           this deployment; see §"What this screen refuses to promise") ·
//           BR-MET-059 (the channel model — every staged row carries an
//           explicit channel) · BR-SHL-018/019 (wizard rail + ONE
//           transactional commit) · BR-SHL-020 (plain-language absence) ·
//           BR-SHL-025 (a control this release cannot offer renders disabled
//           WITH its reason) · BR-SHL-034 (one date formatter)
// Defect:   DEF-115 (2026-08-15, CRITICAL) — "NO BILL IN THIS PRODUCT HAS EVER
//           COME FROM A METER READING."
// ───────────────────────────────────────────────────────
// S28 — Upload reads. The first step of a meter-to-cash product, built on day
// five of it having none.
//
// WHY THIS SCREEN EXISTS, in the defect's own words: *"`meter_reads` holds 0
// rows on a fully seeded stack, and no screen can add one … no bill in this
// product has ever been produced from a meter reading."* The whole import
// pipeline — parser, published template, VEE engine, dispositions, supersede,
// estimation, the compliance stamp, the atomic commit — shipped on 2026-08-10
// under its own tests with NOTHING in front of it, and the S25 header carried a
// disabled button that said so honestly. Honest, and still a product whose
// central claim had never once been performed by a human. That is hard-won law
// 2 at the largest scale the register has recorded.
//
// WHAT THIS SCREEN REFUSES TO PROMISE — four things, each because the server
// does not do it and a screen that implied otherwise would be worse than a gap:
//
//   1. **No "we'll email you when it's done".** ⚠ This item read *"No
//      progress bar"* too, because the commit ran SYNCHRONOUSLY — and 480
//      readings then took ~60 s inside a request the web worker is killed at
//      (`DEF-MET-8106`). Since 2026-09-30 a batch over the server's bar posts
//      in a worker (BR-MET-055): the post answers 202 with a job, stage 4
//      draws that job's `N of M` (`ReadPostProgress`), and the receipt is
//      collected when the job succeeds. A batch at or below the bar still
//      posts while the clerk waits, exactly as before.
//   2. **No AMI feed replay — AND THE CARD IS NO LONGER DRAWN AT ALL
//      (CR-038 W3, 2026-08-26).** This paragraph used to say the opposite:
//      *"The card is drawn DISABLED with that reason (BR-SHL-025) rather than
//      dropped."* BR-MET-123 (PO 2026-08-26) rules the other way, verbatim:
//      *"there is no integration yet; but it should not stop us from tagging
//      the soruce and accepting the CSV or excel file"* — the rule's clause 3
//      names the DEF-520 posture, *"a transport card with nothing behind it is
//      not offered"*. So the two cards this step offers are the two lawful
//      TRANSPORTS, file and manual, and the AMI capability is where it always
//      actually belonged: in the SOURCE TAG below, where a file collected by
//      AMI is tagged `ami` and uploaded as a file. The server still refuses
//      `source_kind: "ami_replay"` — defence in depth for a payload no screen
//      can now compose.
//   3. **No supervisor co-sign toggle.** OQ-042 closed it as a tenant setting
//      (default ON) and no endpoint serves that setting — `read_batch_dict`
//      returns `cosigned_by` and nothing writes it. Drawing the checkbox would
//      offer a control that changes nothing.
//   4. **No usage figure on a staged row.** The prototype's step-4 table has a
//      Usage column. A staged row is a REGISTER READING, and consumption is
//      computed at commit from the meter — `_post_row` writes
//      `unit=asset.unit` — so the staged payload carries neither a consumption
//      nor a unit. CLAUDE.md rule 3 says a consumption always carries an
//      explicit unit; the only way to obey it here is to not print one. The
//      column is named and its absence explained, and the committed reading
//      shows its usage WITH its unit on S25 a click later.
//
// AND ONE THING IT INSISTS ON: **"N created · N failed", always**, both figures
// with equal weight, on every commit. A partial success that reads as a success
// is the defect BR-MET-038's sibling rule exists to prevent, and it is the
// shape the accounts importer (S68) and the premises importer (S16) already
// use — this is the third importer in the product and it invents nothing.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient, JobRecord } from "@/api/client";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import {
  READ_CHANNELS,
  cosignReadBatch,
  discardReadBatch,
  getCycles,
  getReadBatch,
  getReadBatchResults,
  getReadMethods,
  getReadingSheet,
  getReadingSheetSummary,
  getReadsTemplate,
  READ_SHAPES,
  getReadBatchPostReceipt,
  getRoutes,
  getTenantServices,
  isDeferredPost,
  postReadBatch,
  setBatchDemandReset,
  setReadRowDemandReset,
  setReadRowDisposition,
  stageReadBatch,
  validateReadBatch,
} from "@/api/endpoints";
import type {
  CycleRow,
  ReadBatchCounts,
  ReadBatchPosted,
  ReadBatchStaged,
  ReadBatchValidation,
  ReadImportBatchRow,
  ReadCycleCoverage,
  ReadManualRow,
  ReadMethodOption,
  ReadShape,
  ReadingSheetSummary,
  RouteRow,
  TenantServiceRow,
} from "@/api/endpoints";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import {
  CheckboxField,
  DatePickerField,
  SelectField,
  TextField,
} from "@/components/FormModal";
// CR-038 W7 — `PageHeader` is no longer imported here. The shared
// `WorkflowRunner` draws it (BR-SHL-044: ONE page header for every screen,
// workflows included), which is the point of moving to the rail: this screen
// used to draw its own beside a second frame's.
import { PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable, RefusalStrip } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
// CR-038 W7 — the SHARED rail. `WizardFrame` is no longer mounted here; the
// types above are kept because `steps`/`nav` are still this screen's own shape
// and nothing is gained by renaming five state variables.
// ⚠ **CR-054 task 18 — THE KIT, NOT TWO OF ITS EXPORTS.** This screen imported
// exactly `WorkflowRunner` and `WORKFLOW_KINDS` and then hand-rolled every panel
// inside them, against twenty stylesheet classes. Its sibling on the same rail —
// `ImportWorkflowPage.tsx` — mounts the kit and carries ZERO stylesheet classes.
// One import path (`components/workflow/index.ts`) exists precisely so a screen
// cannot reach half the kit and re-invent the other half.
import {
  MappingTable,
  ReconcileStrip,
  RuleResultsTable,
  SourceCards,
  DropZone,
  WorkflowRunner,
  WORKFLOW_KINDS,
} from "@/components/workflow";
import type {
  MappingRow,
  ReceivedFile,
  ReconcileFigure,
  RuleResult,
  SourceChoice,
  TargetColumn,
} from "@/components/workflow";
import * as WF from "@/components/workflow/workflowKit";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  DemandResetBulkControl,
  DemandResetRowToggle,
  StagedRegisterValue,
} from "./demandShared";
import type { DemandResetReport } from "./demandShared";
// CR-038 W7's new UI, in Tailwind utilities, in ONE place (B14 rule 21). This
// screen is not on Route B, so it imports the controls and adds no class token
// of its own — the same handover `demandShared` already made for W4.
import {
  CosignPanel,
  CycleShortfall,
  DEFAULT_READ_WRITE_MODE,
  PostSplitStatement,
  RefusedBilledRows,
  RegisterCompleteness,
  RejectsDownload,
  SupersededSummary,
  TieredDateWarning,
  WriteModeField,
  WriteModeStated,
} from "./readsImportRail";
import { ReadPostProgress } from "./ReadPostProgress";
import { SendSomeoneOutModal } from "./SendSomeoneOutModal";
import type { RegisterGroup } from "./readsImportRail";
import type { ReadWriteMode } from "./readsImportRail";
import {
  CELL_FULL,
  DASHBOARD_ROUTE,
  Dash,
  PREMISES_PERMISSION,
  ROLE_EXECUTIVE,
  ROLE_SYSTEM_ADMIN,
  isDenied,
  useRegional,
  useAccessCell,
  useTenantRole,
} from "./meteringShared";
import type { RegionalProps } from "./meteringShared";
import { ActorName, READS_ROUTE, READS_UPLOAD_ROUTE } from "./readsShared";
// CR-054 task 9 — the ONE reader of the tenant's enabled subset. Re-deriving
// `rows.filter(r => r.enabled)` here would be a second answer to a question
// BR-MET-003's control already answers (hard-won law 5).
import { enabledServiceRows } from "./ServicesAvailableField";

import "./reads.css";

// ── Pure pieces (provable without a browser or a network) ─────────────────

/** The prototype's five steps, in its own order and its own words. */
export const UPLOAD_STEP_IDS = ["source", "upload", "validate", "review", "post"] as const;
export type UploadStepId = (typeof UPLOAD_STEP_IDS)[number];

/**
 * THE TRANSPORTS — how the reading physically arrives (BR-MET-123 clause 2,
 * verbatim: *"The only transports are file upload — CSV or Excel (.xlsx) — and
 * manual entry"*).
 *
 * `ami_replay` IS DELIBERATELY NOT IN THIS LIST any more (CR-038 W3). It was
 * offered as a third, disabled card under BR-SHL-025; BR-MET-123 clause 3
 * supersedes that reading for this control — *"a transport card with nothing
 * behind it is not offered (the DEF-520 posture)"*. The constant survives so
 * the server's refusal keeps a name on this side, and nothing renders it.
 */
export const SOURCE_KIND_CSV = "csv";
export const SOURCE_KIND_MANUAL = "manual";
/** Refused by the server; NOT offered by any control. Kept for the refusal. */
export const SOURCE_KIND_AMI = "ami_replay";
export const SOURCE_KINDS = [SOURCE_KIND_CSV, SOURCE_KIND_MANUAL] as const;

/**
 * ⛔ **`models.SOURCE_DETAILS` — THE OLD SIX, NO LONGER OFFERED AT STEP 1.**
 *
 * These are the batch's legacy "Read source" values and they are ONE OF THE
 * THREE VOCABULARIES CR-038 W3 collapsed. The measured problem: the METER
 * carried the PO's five words, the BATCH carried these six, the committed READ
 * stored three — and AMR and Mobile had nowhere to land at all.
 *
 * The step-1 control is now the READ METHOD, drawn from the tenant's own
 * `read_methods` list (`getReadMethods`). This array stays exported for ONE
 * reason: reads already on file carry these words, and S25/S29 still render
 * them beside the derived method rather than hiding history.
 */
export const SOURCE_DETAILS = [
  "walk_by",
  "drive_by",
  "self_read",
  "field_visit",
  "ami_itron",
  "ami_sensus",
] as const;

/** `models.DISPOSITIONS` (US-MET-008 §5). */
export const DISPOSITIONS = [
  "accept",
  "accept_with_flag",
  "override",
  "estimate",
  "reject",
  "field_visit",
  "skip",
] as const;
export type Disposition = (typeof DISPOSITIONS)[number];

/**
 * BR-MET-015, as a data structure rather than as care: an ERROR row is never
 * offered a plain `accept`. The server refuses it
 * (`metering.read_row.error_needs_resolution`) and this list is why the option
 * is not on the screen to begin with.
 */
export function dispositionsFor(severity: string): readonly Disposition[] {
  if (severity === "error") {
    return ["override", "reject", "field_visit", "skip"];
  }
  if (severity === "warning") {
    return ["accept_with_flag", "override", "estimate", "reject", "field_visit", "skip"];
  }
  return ["accept", "override", "reject"];
}

/**
 * BR-MET-015: every disposition but a plain `accept` records WHY. Mirrored
 * from `services._REASON_REQUIRED` so the screen can ask before the round trip;
 * the server refuses regardless, which is the half that governs.
 */
export const REASON_REQUIRED: readonly Disposition[] = [
  "accept_with_flag",
  "override",
  "reject",
  "skip",
  "field_visit",
];

export function reasonRequired(disposition: string): boolean {
  return (REASON_REQUIRED as readonly string[]).includes(disposition);
}

/**
 * ~~BR-MET-015: the commit is only reachable at zero unresolved errors.~~
 * ⚠ **SUPERSEDED AS A GATE BY BR-MET-940 (CR-054 task 14/15, 2026-08-30).** An
 * unresolved error gates ITS OWN ROW and no longer the batch, so this is a
 * COUNT the screen states and no longer a fence it enforces. The function is
 * kept and still called for exactly the reason `services._unresolved_errors`
 * is kept on the server: *which* rows nobody has decided is the whole of the
 * ruling's second half.
 */
export function unresolvedErrorRows(rows: readonly ReadImportBatchRow[]): ReadImportBatchRow[] {
  return rows.filter((row) => row.severity === "error" && row.disposition === null);
}

// ── CR-054 task 15 · WHAT WILL POST, AND WHAT WILL NOT ─────────────────────
//
// ⛔ **THE SERVER PUBLISHES THIS SPLIT ONLY AFTER THE POST, AND THE BUTTON HAS
// TO NAME IT BEFORE (`OQ-1200`).** `commit_read_batch` answers `posted_reads`,
// `held_reads` and `unresolved_errors`; `validate_read_batch` answers none of
// them, and `selectors.read_batch_counts` cannot be summed into them either —
// it has no bucket for *"an error row nobody has decided"*, which is precisely
// the term the split turns on. So the pre-post figure is derived here, and it
// is derived as a LITERAL PORT of the one server function that decides it.
//
// ⚠ **THE FUNCTION IT PORTS IS `apps/metering/read_rejects.would_hold`, WHOSE
// OWN DOCSTRING SAYS WHY IT EXISTS: *"a pre-post rejects file that disagrees
// with what the post actually holds is worse than none: the clerk fixes rows
// that would have gone in and re-uploads rows that would not."*** The same
// sentence governs a banner that names a number and a button that names a
// number, so the three clauses below are that function's three clauses, in its
// order, and any change to it is a change here. It re-judges NOTHING: every
// input is a verdict the server stored on the row at stage 3.
//
// ⚠ **AND IT CANNOT BE EXACT ABOUT TWO THINGS, WHICH `would_hold` ALSO NAMES:**
// a head billed since stage 3, and a write the database refuses. Both produce
// MORE holds at post, never fewer, so `willPost` is a CEILING. The receipt
// prints the server's own `held_reads`, so the forecast is never left standing
// as the record.
export const HOLD_UNRESOLVED_ERROR = "unresolved_error";
export const HOLD_DISPOSITIONED_OUT = "dispositioned_out";
export const HOLD_INCOMPLETE_ROW = "incomplete_row";

/** `models.POSTING_DISPOSITIONS` — the three that file a reading. */
const POSTING_DISPOSITIONS: readonly string[] = ["accept", "accept_with_flag", "override"];

/**
 * Why this staged row would NOT post if the batch were posted now, or `null`.
 * The port of `read_rejects.would_hold`; see the block above.
 */
export function wouldHoldRow(row: ReadImportBatchRow): string | null {
  // BR-MET-129 (PO 2026-08-26): an undispositioned OK or WARNING row POSTS —
  // *"if reading are colelcted we have to store the reading, we can give the
  // warning, but we cannot reject the reading"*. This synthesized `accept` is
  // never recorded anywhere; it exists only to answer the question.
  const disposition =
    row.disposition ?? (row.severity === "ok" || row.severity === "warning" ? "accept" : null);
  if (disposition === null || !POSTING_DISPOSITIONS.includes(disposition)) {
    return row.disposition === null && row.severity === "error"
      ? HOLD_UNRESOLVED_ERROR
      : HOLD_DISPOSITIONED_OUT;
  }
  // `meter_no` IS the server's `meter_no_raw` (`selectors.read_row_dict`), which
  // is the field `would_hold` reads — not the resolved asset.
  if (
    row.meter_read_id === null &&
    (row.meter_no === null || row.read_at === null || row.value === null)
  ) {
    return HOLD_INCOMPLETE_ROW;
  }
  return null;
}

export interface PostSplit {
  willPost: number;
  willHold: number;
  unresolvedErrors: number;
  /** The rows that would be held, in row order — what the two surfaces name. */
  heldRowNos: number[];
  /**
   * ⛔ **THE SELF-CHECK, AND IT IS NOT DECORATION.** `counts.rows` is the
   * SERVER's tally of the batch; `rows` is what this screen fetched. If a fetch
   * was partial, or a row was staged after the last refresh, the split would be
   * a confident wrong number on the screen immediately before an irreversible
   * click. `read_batch_counts` carries its own `reconciles` for exactly this
   * reason (DEF-016 — a silently dropped row), and the screen refuses to state
   * a split it cannot reconcile rather than rounding the difference away.
   */
  reconciles: boolean;
}

export function postSplit(
  rows: readonly ReadImportBatchRow[],
  counts: ReadBatchCounts | null,
): PostSplit {
  const held: number[] = [];
  let unresolved = 0;
  for (const row of rows) {
    const reason = wouldHoldRow(row);
    if (reason === null) continue;
    held.push(row.row_no);
    if (reason === HOLD_UNRESOLVED_ERROR) unresolved += 1;
  }
  const total = counts?.rows ?? rows.length;
  return {
    willPost: Math.max(0, rows.length - held.length),
    willHold: held.length,
    unresolvedErrors: unresolved,
    heldRowNos: held,
    reconciles: rows.length === total,
  };
}

/** The step-4 segment filter — the prototype's All / Errors / Warnings. */
export const REVIEW_SEGMENTS = ["all", "error", "warning"] as const;
export type ReviewSegment = (typeof REVIEW_SEGMENTS)[number];

export function reviewRows(
  rows: readonly ReadImportBatchRow[],
  segment: ReviewSegment,
): ReadImportBatchRow[] {
  const flagged = rows.filter((row) => row.severity !== "ok");
  return segment === "all" ? flagged : flagged.filter((row) => row.severity === segment);
}

/**
 * The prototype's "Rule outcomes" table, tallied from the STORED verdicts.
 *
 * Counting stored outcomes is not re-deriving one — no threshold is compared
 * here (BR-MET-056). Rules that could not run are counted separately, because
 * a batch reporting "everything passed" while four rules never executed is
 * hard-won law 1 in data form.
 */
export interface RuleTally {
  rule: string;
  severity: string;
  hits: number;
}

export function ruleTally(rows: readonly ReadImportBatchRow[]): RuleTally[] {
  const seen = new Map<string, RuleTally>();
  for (const row of rows) {
    for (const outcome of row.rule_outcomes ?? []) {
      if (outcome.severity === "ok") {
        continue; // a passed rule is not a finding
      }
      const key = `${outcome.rule}|${outcome.severity}`;
      const entry = seen.get(key);
      if (entry === undefined) {
        seen.set(key, { rule: outcome.rule, severity: outcome.severity, hits: 1 });
      } else {
        entry.hits += 1;
      }
    }
  }
  // Errors first, then warnings, then the rules that could not run; alpha
  // within a band so the table is stable between validations.
  const rank: Record<string, number> = { error: 0, warning: 1, not_evaluated: 2 };
  return [...seen.values()].sort(
    (a, b) => (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3) || a.rule.localeCompare(b.rule),
  );
}

/**
 * A staged row's own failure lines. Parse errors ride as a `parse` outcome
 * whose detail carries the read_import code; every other outcome is a rule.
 * An UNKNOWN code renders with its raw name rather than being swallowed — a
 * reason the screen cannot name is still a reason the clerk must see.
 */
export function rowReasonText(row: ReadImportBatchRow, t: Translator): string {
  const parts: string[] = [];
  for (const outcome of row.rule_outcomes ?? []) {
    if (outcome.severity === "ok" || outcome.severity === "not_evaluated") {
      continue;
    }
    if (outcome.rule === "parse") {
      const code = (outcome.detail as Record<string, unknown> | undefined)?.code;
      parts.push(
        t(`metering.read_import.${String(code)}`, { defaultValue: String(code ?? outcome.rule) }),
      );
      continue;
    }
    parts.push(t(`metering.reads.status.${outcome.rule}`, { defaultValue: outcome.rule }));
  }
  return parts.join(" · ");
}

/** BR-MET-014: the batch tags, exactly as `_validate_batch_tags` reads them. */
export interface BatchTags {
  source_kind: string;
  source_detail: string;
  /** BR-MET-123's SOURCE TAG — a `read_methods` code, or "" for none stated. */
  read_method: string;
  period_month: string;
  cycle_id: string;
  route_id: string;
}

/**
 * **CR-054 task 9 — the clerk's service choice, as the ONE tag the batch can
 * hold.** Pure, exported and unit-tested, because this is the whole of
 * `DEF-2673` expressed in four lines and it must not be re-derived inline where
 * a later edit can quietly change it.
 *
 * `read_import_batches.service` is one `TextField` whose NULL means *every
 * service*, so there are exactly two lawful payloads:
 *
 *   * `null` → the field is OMITTED. Sent for the default (every enabled
 *     service chosen) AND for any subset of two or more, because those are the
 *     same statement to this server: *not one particular service*. Each row's
 *     own `service` column then decides, which is what the screen says.
 *   * a code → sent, and BR-MET-014 inherits it to every row that does not name
 *     its own service. This is the shape task 10's `service_coherence` needs in
 *     order to warn that a water meter is in a batch tagged Electric.
 *
 * ⚠ **AN EMPTY CHOICE ANSWERS `null` TOO, AND THE CONTROL MAKES IT UNREACHABLE
 * ANYWAY.** Two guards for one hazard is deliberate: were the last chip ever
 * removable, "no service" would post the identical payload to "every service"
 * and nothing downstream could tell the clerk which they meant.
 */
export function serviceTagFor(chosen: readonly string[] | null): string | null {
  if (chosen === null || chosen.length !== 1) {
    return null;
  }
  const code = chosen[0].trim();
  return code === "" ? null : code;
}

export function emptyManualRow(): ReadManualRow {
  // ⚖️ **Q7 (PO 2026-09-14) — THE REGISTER IS CHOSEN, AND UNTIL IT IS CHOSEN IT
  // IS EMPTY.**
  //
  // ⚠ **THIS LINE READ `channel: "total"` AND ITS COMMENT CLAIMED THE OPPOSITE
  // OF WHAT IT DID** — *"the channel is EXPLICIT from the first keystroke"*
  // over a value the clerk never touched. That is hard-won law 1 exactly: a
  // comment claiming a guarantee is not the guarantee. The reasoning was sound
  // and aimed at the right target (the server would default an absent channel
  // to `total`), but pre-selecting `total` on the CLIENT is the same default
  // one layer up, and it is the layer a person is looking at.
  //
  // ⚠ **WHY IT MATTERS MORE HERE THAN ANYWHERE ELSE IN THE MODULE.** A reading
  // recorded against the wrong register is PERMANENT: `supersede_read` takes a
  // value and a reason and nothing else, and migration `0007`'s trigger freezes
  // the channel. On a demand plan the UNITS differ, which is how `DEF-797` put
  // **412 kW through a kWh price — $154 against $4,532**. An upload is the
  // highest-volume way to get a register wrong, and a pre-selected dropdown on
  // a five-row grid is the cheapest possible way to do it by accident.
  //
  // ⚠ **AND THIS CHOOSES NOTHING, WHICH IS THE CONSTRAINT.** The PO declined to
  // classify `DEF-797` — B4/B5 are ❄️ FROZEN and move only by a finance re-sign
  // — so no rounding, no unit and no estimate is decided here. Refusing to
  // guess is not a decision about billing; it is the absence of one.
  return { meter_id: "", read_date: "", reading: "", channel: "" };
}

/**
 * Filled rows that still have no register — Q7's refusal, computed once so the
 * button, its reason and any test all read the SAME answer (hard-won law 5).
 */
export function manualRowsMissingRegister(
  rows: readonly ReadManualRow[],
): ReadManualRow[] {
  return filledManualRows(rows).filter((row) => row.channel.trim() === "");
}

export function filledManualRows(rows: readonly ReadManualRow[]): ReadManualRow[] {
  return rows.filter((row) => row.meter_id.trim() !== "" || row.reading.trim() !== "");
}

// ── CR-054 task 18 · what this screen hands to the shared kit ──────────────

/**
 * The two lawful TRANSPORTS as the kit's own `SourceChoice`, so stage 1 draws
 * the same cards as the other six targets (BR-MET-123 clause 2).
 *
 * ⚠ THERE IS NO THIRD, DISABLED CARD HERE and that is deliberate — clause 3,
 * verbatim: *"a transport card with nothing behind it is not offered (the
 * DEF-520 posture)"*. `SourceCards` CAN draw an unavailable card with its
 * reason, and the premises runner uses that for SFTP and API; reads' AMI
 * capability is a source TAG, not a transport, and lives in the read-method
 * picker below.
 */
export const READS_SOURCE_CHOICES: readonly SourceChoice[] = [
  {
    id: SOURCE_KIND_CSV,
    title_key: "metering.reads.sourceKind.csv",
    sub_key: "metering.upload.source.blurb.csv",
    available: true,
  },
  {
    id: SOURCE_KIND_MANUAL,
    title_key: "metering.reads.sourceKind.manual",
    sub_key: "metering.upload.source.blurb.manual",
    available: true,
  },
];

/** The first CSV line, split on commas. Deliberately not a CSV parser: it reads
 *  a header row and one sample row for DISPLAY, and a quoted comma showing up in
 *  a sample cell is a cosmetic wrong, not a parsed value anybody acts on. The
 *  file is parsed by ONE parser and it is the server's (BR-MET-032). */
function csvCells(line: string): string[] {
  return line.split(",").map((cell) => cell.trim().replace(/^"|"$/g, ""));
}

/**
 * Stage 2's mapping, in the kit's shape — **one row per column the CLERK sent**,
 * with a SAMPLE VALUE out of their own file.
 *
 * ⚠ THE SAMPLE IS THEIR FILE, NOT AN INVENTION. `ImportWorkflowPage` leaves this
 * column empty and files `DEF-521`, because its file lives on the server and
 * stage 1's answer ships no sample row. Reads is the opposite case: the browser
 * HAS the bytes — a clerk either picked the file here or pasted it — so the
 * first non-empty cell under each header is real evidence and costs no endpoint.
 *
 * ⚠ AND THE MAPPING IS INVERTED ON PURPOSE. The server answers
 * `{template_field: their_header | null}`; the kit's table reads
 * `{their_column → template field}`, which is the direction a clerk checks
 * ("what did MY column become?"). Template fields the file did not carry are
 * NOT smuggled in as rows with an empty source column — they are named
 * separately by `unmappedTargets`, because a row whose source column is blank
 * is not a row of this table.
 */
export function fileMappingRows(
  text: string,
  mapping: Record<string, string | null>,
): MappingRow[] {
  const lines = text.split(/\r?\n/).filter((line) => line.trim() !== "");
  if (lines.length === 0) {
    return [];
  }
  const headers = csvCells(lines[0] ?? "");
  const samples = lines.slice(1).map(csvCells);
  const targetOf = new Map<string, string>();
  for (const [target, header] of Object.entries(mapping)) {
    if (header !== null && header !== "") {
      targetOf.set(header.trim().toLowerCase(), target);
    }
  }
  return headers.map((header, index) => {
    const target = targetOf.get(header.toLowerCase()) ?? null;
    const sample = samples.find((cells) => (cells[index] ?? "") !== "")?.[index] ?? "";
    return {
      source_column: header,
      sample_value: sample,
      target_column: target,
      status: target === null ? "unmapped" : "matched",
      transform_label: null,
    };
  });
}

/** Template fields the file did not carry — every one optional, because the
 *  server stages nothing at all when a REQUIRED column is missing (US-MET-007
 *  TC-5). Named rather than silent: a clerk who meant to send `notes` and
 *  mistyped the header has no other way to find out. */
export function unmappedTargets(mapping: Record<string, string | null>): string[] {
  return Object.entries(mapping)
    .filter(([, header]) => header === null || header === "")
    .map(([target]) => target);
}

/**
 * **CR-054 task 11 — WHAT IS IN THIS FILE**, as the kit's figure rows.
 *
 * Rows · meters · services · reading dates · and the count PER REGISTER. Every
 * figure is a group-by over the rows the server already staged — no endpoint,
 * no second count, and no threshold compared (BR-MET-056).
 *
 * ⚠ THE PER-REGISTER LINE IS THE ONE THAT EARNS THE PANEL. CR-054's measured
 * finding is that a clerk is never told a time-of-use tariff needs four rows per
 * meter, and `tou_on` appears on no screen in the product. A file with 58 rows
 * and 58 `Total register` lines, staged against a cycle whose meters are
 * time-of-use, is wrong in a way this panel states the moment it is staged —
 * rather than at stage 3, or at the bill run.
 */
export function fileComposition(
  rows: readonly ReadImportBatchRow[],
  t: Translator,
): ReconcileFigure[] {
  const meters = new Set<string>();
  const services = new Set<string>();
  const dates = new Set<string>();
  const registers = new Map<string, number>();
  for (const row of rows) {
    if (row.meter_no !== null) meters.add(row.meter_no);
    if (row.service !== null) services.add(row.service);
    const when = row.read_at ?? row.read_at_raw;
    if (when !== null && when !== "") dates.add(when.slice(0, 10));
    registers.set(row.channel, (registers.get(row.channel) ?? 0) + 1);
  }
  const figures: ReconcileFigure[] = [
    { id: "rows", label: t("metering.upload.kpi.rows"), value: rows.length, flagged: false },
    {
      id: "meters",
      label: t("metering.routes.col.meters"),
      value: meters.size,
      flagged: false,
    },
    {
      id: "services",
      label: t("metering.units.col.services"),
      // The service CODES the file carries, spelled out — a clerk who tagged a
      // water batch Electric sees two words, not a count of one.
      value: services.size === 0 ? ABSENT_TEXT : [...services].sort().join(" · "),
      flagged: false,
    },
    {
      id: "dates",
      label: t("metering.reads.col.readAt"),
      value: dates.size === 0 ? ABSENT_TEXT : [...dates].sort().join(" · "),
      flagged: false,
    },
  ];
  // The canonical register order is `READ_CHANNELS`' own — a channel the server
  // adds tomorrow is not in it, sorts last and is still LISTED, which is why the
  // lookup is widened rather than the value narrowed (BR-MET-059 is extensible
  // BY VALUE, so a client-side union is a claim that ages).
  const channelOrder = (channel: string): number => {
    const at = (READ_CHANNELS as readonly string[]).indexOf(channel);
    return at === -1 ? READ_CHANNELS.length : at;
  };
  for (const [channel, count] of [...registers.entries()].sort(
    (a, b) => channelOrder(a[0]) - channelOrder(b[0]) || a[0].localeCompare(b[0]),
  )) {
    figures.push({
      id: `register-${channel}`,
      label: t(`metering.reads.channel.${channel}`, { defaultValue: channel }),
      value: count,
      flagged: false,
    });
  }
  return figures;
}

/** The em-dash an absent value renders as. A code constant and not a catalogue
 *  key, for the reason the kit's own `ABSENT` records: a value byte-identical in
 *  eleven catalogues fails G15 unless allowlisted, and punctuation is not copy. */
const ABSENT_TEXT = "—";

/**
 * The kit's `RuleResult` rows, from what the SERVER stored — the tallied
 * verdicts, plus every rule that could NOT run, in ONE table.
 *
 * ⚠ **FOLDING THE TWO IS BR-MET-091's OWN SHAPE, NOT A TIDY-UP.** This screen
 * drew a rules table and then, separately, a bulleted list headed *"Rules that
 * could not run"* — so a clerk reading the table saw three rules where four were
 * expected and had to notice a second block to learn why. `RuleResultsTable`
 * lists an unavailable rule IN PLACE, chipped `Cannot run`, with its reason:
 * *"a screen listing three rules where four were expected tells the operator
 * nothing"*.
 *
 * ⚠ AND THE ACTION COLUMN IS BR-MET-015, NOT AN INVENTION. BR-MET-090 wants
 * severity and action as two columns; for reads the action is the rule the whole
 * review step runs on — an error MUST be resolved, a warning may be accepted
 * with a reason on the record.
 */
export function ruleResults(
  rows: readonly ReadImportBatchRow[],
  unevaluated: readonly { rule: string; reason: string }[],
  t: Translator,
): RuleResult[] {
  // ⚠ **A `not_evaluated` TALLY IS NOT A WARNING, AND MAPPING IT TO ONE PRINTED
  // EVERY UNAVAILABLE RULE TWICE.** `ruleTally` counts every non-`ok` outcome,
  // `not_evaluated` included; the first draft folded that band into `warning`,
  // so the browser showed *"Meter factor · Warning · 6"* one row above *"Meter
  // factor · Cannot run"* — the same rule, contradicting itself, on the screen
  // BR-MET-091 exists to make honest. The unavailable half below already lists
  // them WITH the server's reason, which is the row that carries the meaning.
  const results: RuleResult[] = ruleTally(rows)
    .filter((entry) => entry.severity === "error" || entry.severity === "warning")
    .map((entry) => ({
    code: `${entry.rule}|${entry.severity}`,
    sentence: t(`metering.reads.status.${entry.rule}`, { defaultValue: entry.rule }),
    severity: entry.severity === "error" ? "error" : "warning",
    action_label:
      entry.severity === "error"
        ? t("metering.upload.validate.actionError")
        : t("metering.upload.validate.actionWarning"),
    hits: entry.hits,
    available: true,
    unavailable_reason: null,
  }));
  for (const entry of unevaluated) {
    results.push({
      code: `unevaluated|${entry.rule}`,
      sentence: t(`metering.reads.status.${entry.rule}`, { defaultValue: entry.rule }),
      severity: "off",
      action_label: "",
      hits: 0,
      available: false,
      unavailable_reason: t(`metering.read.reason.${entry.reason}`, { defaultValue: entry.reason }),
    });
  }
  return results;
}

/**
 * The one rule this screen groups BY NAME (BR-MET-049 / US-MET-018).
 *
 * ⛔ **THIS WAS `"plan_register_completeness"` AND THE TABLE DREW NOTHING —
 * DEF-2441, found by the render check and by nothing else.**
 * `plan_register_completeness` is the FUNCTION in `apps/metering/validation.py`;
 * the code that reaches the row is `RULE_PLAN_REGISTERS = "plan_registers"`, and
 * CR-054's own prose names the function. So `registerGroups` matched no outcome,
 * returned an empty array, and `RegisterCompleteness` correctly rendered `null`
 * — an empty screen where every figure was present in the payload.
 *
 * ⚠ **AND THE UNIT TEST PASSED ON IT, WHICH IS THE FINDING.** The fixture in
 * `CR054ReadsUpload.dom.test.tsx` was written from the same prose, so it carried
 * the same wrong name and the test asserted this lane's own mistake back at
 * itself — hard-won law 6 exactly: *no gate looks at rendered output*, and a
 * fixture is not the server. The fixture now carries the SERVER's code, and the
 * name is written here once so the two cannot drift again.
 */
export const RULE_PLAN_REGISTERS = "plan_registers";

/**
 * **CR-054 task 12 — THE REGISTER-COMPLETENESS TABLE, GROUPED BY PLAN MODEL.**
 *
 * ⚠ **EVERY FIGURE HERE IS ALREADY ON THE ROW AND NOTHING ON SCREEN GROUPED
 * THEM.** `validation.plan_register_completeness` records `expected`,
 * `received`, `missing` and a human `summary` per (meter, date), and
 * `completeness.ExpectedRegisters.detail()` adds the `plan_model` that produced
 * the set. A clerk could read one row's warning sentence and nothing told them
 * *"nine of your eleven time-of-use meters are short three windows each"*.
 *
 * ⚠ **DEDUPED BY (METER, DATE), BECAUSE THE VERDICT IS A GROUP RULE.**
 * `services.validate_read_batch` attaches this outcome to EVERY row of the
 * meter's group — deliberately, so a clerk reading one row sees it — so a naive
 * tally over rows counts a four-register time-of-use meter four times and
 * reports 44 expected registers where the plan expects 11.
 *
 * ⚠ **A METER WHOSE SET COULD NOT BE RESOLVED IS NOT IN HERE AT ALL.** That
 * outcome is `not_evaluated` and is reported once on the batch summary, which is
 * `RuleResultsTable`'s unavailable row above. Counting it as "short" would say a
 * meter is missing registers when the truth is that nobody could say what it
 * expects (the DEF-075 posture).
 */
export function registerGroups(rows: readonly ReadImportBatchRow[]): RegisterGroup[] {
  interface Seen {
    expected: string[];
    received: string[];
    missing: string[];
    rowNos: number[];
    /** The METER this (meter, date) key belongs to — its anchor and its number.
     *  `assetId` is empty when the file named a meter the registry could not
     *  resolve; such a row can be estimated but nobody can be sent to it, so it
     *  is dropped from `shortMeters` rather than raised against a blank. */
    assetId: string;
    meterNo: string;
  }
  const byMeterDate = new Map<string, { model: string; seen: Seen }>();
  for (const row of rows) {
    for (const outcome of row.rule_outcomes ?? []) {
      if (outcome.rule !== RULE_PLAN_REGISTERS) continue;
      if (outcome.severity !== "ok" && outcome.severity !== "warning") continue;
      const detail = (outcome.detail ?? {}) as Record<string, unknown>;
      const key = `${row.asset_id ?? row.meter_no ?? ""}|${row.read_at ?? row.read_at_raw ?? ""}`;
      const existing = byMeterDate.get(key);
      if (existing === undefined) {
        byMeterDate.set(key, {
          model: String(detail.plan_model ?? ""),
          seen: {
            expected: (detail.expected as string[] | undefined) ?? [],
            received: (detail.received as string[] | undefined) ?? [],
            missing: (detail.missing as string[] | undefined) ?? [],
            rowNos: [row.row_no],
            assetId: row.asset_id ?? "",
            meterNo: row.meter_no ?? "",
          },
        });
      } else {
        existing.seen.rowNos.push(row.row_no);
      }
    }
  }
  const byModel = new Map<string, RegisterGroup>();
  for (const { model, seen } of byMeterDate.values()) {
    const group = byModel.get(model) ?? {
      planModel: model,
      meters: 0,
      short: 0,
      expects: 0,
      arrived: 0,
      missing: 0,
      missingChannels: [],
      rowNos: [],
      shortMeters: [],
    };
    group.meters += 1;
    group.expects += seen.expected.length;
    group.arrived += seen.received.filter((channel) => seen.expected.includes(channel)).length;
    group.missing += seen.missing.length;
    if (seen.missing.length > 0) {
      group.short += 1;
      // Only a SHORT meter's rows are offered to the bulk actions (task 13): a
      // complete meter has nothing to estimate and nobody to send out.
      group.rowNos.push(...seen.rowNos);
      // ONE ENTRY PER METER, and `rowNos` is not it — a TOU meter short of
      // three windows contributes three staged rows and exactly one visit.
      if (seen.assetId !== "" && !group.shortMeters.some((m) => m.assetId === seen.assetId)) {
        group.shortMeters.push({ assetId: seen.assetId, meterNo: seen.meterNo });
      }
      for (const channel of seen.missing) {
        if (!group.missingChannels.includes(channel)) group.missingChannels.push(channel);
      }
    }
    byModel.set(model, group);
  }
  return [...byModel.values()].sort(
    (a, b) => b.short - a.short || a.planModel.localeCompare(b.planModel),
  );
}

// ── CR-054 task 25 · A TIERED READ DATE OFF THE STATED MONTH ───────────────
//
// See `TieredDateWarning` in `readsImportRail.tsx` for the rule and the reason.
// This is the selection half: the plan model comes from the SERVER's own
// `plan_registers` outcome (`detail.plan_model`, stamped by
// `completeness.PlanRegisterResolver`), so no tariff shape is re-derived here.
export const PLAN_MODEL_TIERED = "tiered";

export function tieredRowsOffMonth(
  rows: readonly ReadImportBatchRow[],
  periodMonth: string,
): number[] {
  const month = periodMonth.slice(0, 7);
  if (month.length !== 7) return [];
  const out: number[] = [];
  for (const row of rows) {
    const tiered = (row.rule_outcomes ?? []).some(
      (outcome) =>
        outcome.rule === RULE_PLAN_REGISTERS &&
        String(((outcome.detail ?? {}) as Record<string, unknown>).plan_model ?? "") ===
          PLAN_MODEL_TIERED,
    );
    if (!tiered) continue;
    // The PARSED date only. `read_at_raw` is a string the parser refused, and a
    // row whose date would not parse already errors by name — flagging it here
    // as a tier hazard would be a second, weaker sentence about the same cell.
    if (row.read_at === null) continue;
    if (row.read_at.slice(0, 7) !== month) out.push(row.row_no);
  }
  return out;
}

/** Browser-side save of the published template. */
function saveTextFile(name: string, body: string): void {
  const url = URL.createObjectURL(new Blob([body], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

function severityTone(severity: string): "success" | "warning" | "danger" | "neutral" {
  if (severity === "ok") {
    return "success";
  }
  if (severity === "error") {
    return "danger";
  }
  if (severity === "warning") {
    return "warning";
  }
  return "neutral";
}

// ── CR-054 task 9 — THE UTILITY-SERVICE CONTROL ───────────────────────────

/**
 * **The services this file covers, on stage 1.** CR-054 task 9, and the PO's
 * own words on 2026-08-30: *"for upload - we have cycle, Reading date, reading
 * methods, utility service - 1 or more in cycle"*.
 *
 * ⚠ **B14 RULE 9 — REMOVABLE CHIPS + AN ADD CONTROL, NEVER A WALL OF
 * CHECKBOXES.** `ServicesAvailableField` is the house precedent for exactly
 * this question against exactly this endpoint, and this control is its shape.
 * It is NOT that component reused: that one is bound to the premises field id
 * `services_available`, and every one of its four empty-state sentences is
 * about an ADDRESS (*"nobody has been asked about this address yet"*). What IS
 * reused is the part that must never fork — `enabledServiceRows` and the one
 * `GET /settings/services` query key, so a tenant that switches Solar on
 * tomorrow sees it here and on S16 without a second list being edited.
 *
 * ⚠ **THE OPTIONS ARE THE TENANT'S ENABLED SET, NEVER A CONSTANT.** Ten
 * services exist platform-wide (BR-RAT-024) and a utility sells a subset.
 * `_validate_batch_tags` refuses a `service` outside `enabled_service_codes()`
 * by name, so a hardcoded list here would offer a choice the server rejects.
 *
 * ⚠ **AND THE STORAGE ACCEPTS EXACTLY TWO SHAPES — `DEF-2673`.**
 * `read_import_batches.service` is ONE `TextField` whose NULL means *every
 * service*, so the batch can record **one code** or **all of them** and nothing
 * in between. Widening it is a schema change on the table carrying hard rule
 * 6's `tag_fingerprint`, and no CR-054 task asks for one — DEF-2673's own
 * closing sentence tells this lane to build to the two shapes rather than
 * discover the third at integration. So:
 *
 *   * **one service chosen** → the code is sent, and BR-MET-014 inherits it to
 *     every row that does not name its own;
 *   * **two or more chosen** (the default is all of them) → nothing is sent,
 *     the batch stores NULL, and each row's own `service` column decides.
 *
 * **The screen states the CONSEQUENCE and never the mechanism.** CR-054's copy
 * rule: keep the sentence that states a consequence, delete the sentence that
 * explains what is not built. The 36-word note this control replaces was
 * exactly the second kind — DEF-2671 — and a paragraph about a `TextField`
 * would be the same mistake with a different subject. The gap lives in the
 * register, which is where a reader finds it.
 *
 * ⚠ **THE LAST CHIP CANNOT BE REMOVED.** An empty control and a full one would
 * send the identical payload, so "no service" and "every service" would be one
 * state wearing two faces. The last remove is drawn DISABLED with its reason
 * (BR-SHL-025) rather than silently ignoring the press.
 */
function ServiceTagField(props: {
  /** `null` = untouched, which MEANS every enabled service. Kept distinct from
   *  an array so the default tracks the query instead of flashing "none" for
   *  the moment before `GET /settings/services` answers. */
  chosen: readonly string[] | null;
  enabled: readonly TenantServiceRow[];
  /** The answer is IN and empty, or it could not be read — two different facts
   *  and only the second gets a sentence. */
  unavailable: boolean;
  onChange: (next: string[]) => void;
  t: Translator;
}) {
  const { t, enabled } = props;
  const nameOf = (code: string): string =>
    enabled.find((row) => row.service === code)?.name ??
    t(`rating.service.${code}`, { defaultValue: code });
  // The tenant's own seed order, always — so this control, S16 and the export
  // list the services in one sequence (BR-RAT-024's order).
  const codes = enabled.map((row) => row.service);
  const chosen = props.chosen === null ? codes : codes.filter((c) => props.chosen?.includes(c));
  const remaining = codes.filter((code) => !chosen.includes(code));
  const fact =
    chosen.length === 1
      ? t("metering.upload.field.servicesTagOne", { service: nameOf(chosen[0]) })
      : t("metering.upload.field.servicesTagMany");
  return (
    <div className="field">
      <label id="reads-services-label" htmlFor="reads-services-add">
        {t("metering.upload.field.services")}
      </label>
      <p className="field-help" id="reads-services-help">
        {t("metering.upload.field.servicesHelp")}
      </p>
      <div
        className="flex flex-wrap items-center gap-1.5"
        role="group"
        data-reads="services"
        aria-labelledby="reads-services-label"
        aria-describedby="reads-services-help"
      >
        {/* B14 rule 9's chips. Rule 31: the chip's visible value is the
            service's NAME — `electric` is the stored code and never the label
            (the same reason the reading sheet prints *On-peak* beside a key
            carrying `tou_on`). */}
        {chosen.map((code) => (
          <button
            key={code}
            type="button"
            data-reads="service-chip"
            data-reads-service={code}
            disabled={chosen.length === 1}
            title={chosen.length === 1 ? t("metering.upload.field.servicesKeepOne") : undefined}
            className="cursor-pointer border border-divider bg-transparent bg-none px-2 py-[3px] text-sm text-inherit hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:text-neutral-600"
            aria-label={t("metering.upload.field.servicesRemove", { service: nameOf(code) })}
            onClick={() => props.onChange(chosen.filter((kept) => kept !== code))}
          >
            {nameOf(code)} x
          </button>
        ))}
        <select
          id="reads-services-add"
          data-reads="service-add"
          className="min-h-[26px] w-auto border border-field-border bg-bg px-1.5 py-0.5 text-sm text-text"
          value=""
          disabled={remaining.length === 0}
          onChange={(event) => {
            const code = event.target.value;
            if (code !== "" && !chosen.includes(code)) {
              props.onChange(codes.filter((c) => c === code || chosen.includes(c)));
            }
          }}
        >
          <option value="">
            {remaining.length === 0
              ? t("metering.upload.field.servicesAllAdded")
              : t("metering.upload.field.servicesAdd")}
          </option>
          {remaining.map((row) => (
            <option key={row} value={row}>
              {nameOf(row)}
            </option>
          ))}
        </select>
      </div>
      {/* The CONSEQUENCE of the choice, restated as it changes — never the
          mechanism behind it. */}
      {!props.unavailable && chosen.length > 0 && (
        <p className={WF.STAGE_BLURB} data-reads="service-fact">
          {fact}
        </p>
      )}
      {/* The list could not be read. Said out loud rather than drawn as an
          empty menu, which is indistinguishable from "you sell nothing"
          (hard-won law 1 / BR-SHL-025). */}
      {props.unavailable && (
        <p className={WF.STAGE_BLURB} data-reads="service-unavailable">
          {t("metering.upload.field.servicesUnavailable")}
        </p>
      )}
    </div>
  );
}

// ── Step 1 — Source & context (US-MET-007) ────────────────────────────────

function SourceStep(props: {
  tags: BatchTags;
  cycles: readonly CycleRow[];
  routes: readonly RouteRow[];
  readMethods: readonly ReadMethodOption[];
  readMethodsUnavailable: boolean;
  /** CR-054 task 9 — the tenant's enabled services and the clerk's choice. */
  services: readonly TenantServiceRow[];
  servicesUnavailable: boolean;
  serviceTags: readonly string[] | null;
  onServiceTags: (next: string[]) => void;
  onTags: (next: BatchTags) => void;
  /** CR-038 W7 — the stage-1 PREMISE (CR-036 (g)), beside the stage-1 tags. */
  writeMode: ReadWriteMode;
  onWriteMode: (next: ReadWriteMode) => void;
  dateFormat: ReturnType<typeof useRegional>["dateFormat"];
  t: Translator;
}) {
  const { t, tags } = props;
  return (
    <Panel>
      {/* ⚖️ **NO PANEL HEADING HERE (`CR-096-BRC02`).** The blueprint draws
          stage 1 as `STAGE 1 OF 5 · EXTRACT` over **The source**, and then the
          cards — ONE heading. This panel used to print a second one saying the
          same thing in different words (*"Where are these readings coming
          from?"* under the runner's *"Where is the data coming from?"*), plus a
          sub-line the drawing does not carry. The heading is the runner's, per
          this target's own `stageCopy`; B14 rule 32's description budget is one
          sentence per section and the drawing spends it on none. */}

      {/* ⚠ **CR-054 task 18 — THE KIT'S CARDS.** This block was a hand-rolled
          `.chooser` / `.chooser-option` / `.co-title` / `.co-desc` radio group
          with a per-branch class literal and a fourteen-line comment about
          DEF-1000's interpolation trap. `SourceCards` is the same control every
          other target on this rail already draws — a disabled card is a disabled
          RADIO there, not a div that swallows a press — so the accessibility and
          the keyboard behaviour arrive by construction.

          BR-MET-123 clause 3 still holds: TWO transports, no third card. The AMI
          capability is the source TAG below. */}
      <SourceCards
        legend={t("metering.upload.source.cardsLabel")}
        choices={READS_SOURCE_CHOICES}
        selectedId={tags.source_kind}
        groupName="reads-source"
        onSelect={(id) => props.onTags({ ...tags, source_kind: id })}
      />
      <p className={WF.STAGE_BLURB}>{t("metering.upload.source.amiTagged")}</p>

      {/* ⚖️ **TWO FIELDS PER ROW, AS DRAWN AND AS RULED (`CR-096-BRC02`).** The
          blueprint pairs `Reading month` with `Cycle` and `Route` with `How
          were these read?`; these six controls were a single stacked column.
          **The drawing and the UI rules AGREE here**, which is why it is built
          rather than recorded as a divergence — B14 rule 38 hands form
          CONSTRUCTION to the rules, and the rule is *"at most two fields on a
          line, and a field that needs the width takes the row"*. The two that
          need the width take it: the service chips and the write mode, below.
          `gap-x-5` is `--space-5`, the 20px field→field step rule 39 ratified;
          the rows stack at narrow widths, which costs nothing on a staff screen
          built for 1280 and up. */}
      <div className="grid grid-cols-1 gap-x-5 md:grid-cols-2">
      {/* BR-MET-014's tags. The server truncates any date in the month to its
          first day, so the control is a plain date field rather than a month
          list nobody serves. */}
      <DatePickerField
        id="period_month"
        label={t("metering.upload.field.periodMonth")}
        required
        value={tags.period_month}
        dateFormat={props.dateFormat}
        onChange={(value) => props.onTags({ ...tags, period_month: value })}
        help={t("metering.upload.field.periodMonthHelp")}
      />
      <SelectField
        id="cycle_id"
        label={t("metering.upload.field.cycle")}
        value={tags.cycle_id}
        placeholder={t("metering.upload.field.cyclePlaceholder")}
        options={props.cycles.map((cycle) => ({ value: cycle.id, label: cycle.code }))}
        onChange={(value) => props.onTags({ ...tags, cycle_id: value })}
        help={t("metering.upload.field.cycleHelp")}
      />
      <SelectField
        id="route_id"
        label={t("metering.upload.field.route")}
        value={tags.route_id}
        placeholder={t("metering.upload.field.routePlaceholder")}
        options={props.routes.map((route) => ({
          value: route.id,
          label: route.name === null ? route.code : `${route.code} · ${route.name}`,
        }))}
        onChange={(value) => props.onTags({ ...tags, route_id: value })}
        help={t("metering.upload.field.routeHelp")}
      />
      {/* THE SOURCE TAG — the ONE read-method vocabulary (BR-MET-123).
          The options are the TENANT's `read_methods` list, not a constant in
          this file: a System Admin edits it on the S8 reference-data card, and
          a hardcoded copy would drift the day they add a sixth. The six legacy
          `source_detail` values are no longer offered — that control was one
          of the three competing vocabularies this change collapsed. */}
      {props.readMethodsUnavailable ? (
        <p className={WF.STAGE_BLURB}>{t("metering.upload.field.readMethodUnavailable")}</p>
      ) : (
        <SelectField
          id="read_method"
          label={t("metering.upload.field.readMethod")}
          value={tags.read_method}
          placeholder={t("metering.upload.field.readMethodPlaceholder")}
          options={props.readMethods.map((method) => ({
            value: method.code,
            label: t(`metering.reads.readMethod.${method.code}`, { defaultValue: method.name }),
          }))}
          onChange={(value) => props.onTags({ ...tags, read_method: value })}
          help={t("metering.upload.field.readMethodHelp")}
        />
      )}
      </div>
      {/* ⛔ **CR-054 — THE 36-WORD NOTE THAT STOOD HERE IS GONE, AND THE
          CONTROL IT APOLOGISED FOR IS BELOW IT.** The note read: *"There is no
          utility-service tag on this screen: the tag is optional (empty means
          every service) and no endpoint a Billing Clerk may call lists this
          utility's enabled services, so the control would be empty.
          Reported."* — the longest string on stage 1, explaining to a clerk why
          a field they never asked about was absent.

          **Its second clause was never true** (`DEF-2671`): `GET
          /settings/services` has carried `AnyTenantRole` — all three roles — in
          its first commit and every commit since. Task 20 deleted the sentence
          from all eleven catalogues; task 9 is the control, and it is the one
          directly below. */}
      <ServiceTagField
        chosen={props.serviceTags}
        enabled={props.services}
        unavailable={props.servicesUnavailable}
        onChange={props.onServiceTags}
        t={t}
      />

      {/* ⚠ **CR-038 W7 task 3 — THE WRITE MODE, AT STAGE 1 AND NOWHERE ELSE
          (CR-036 (g) · DEF-770).** It sits LAST on this stage deliberately:
          the five controls above are facts ABOUT the file (when, which cycle,
          which route, who read it, which services) and this is the one question
          about what the file MEANS. The premises importer settled on the same
          ordering. ⚠ The count in that first clause was FOUR until CR-054 task
          9 added the service control — a number in a comment is a claim like
          any other (hard-won law 1).

          Every class in `WriteModeField` is a Tailwind utility living in
          `readsImportRail.tsx` (B14 rule 21), and the control is imported
          rather than re-drawn here. ⚠ **The clause that used to follow —
          *"this screen is not on Route B"* — was true when it was written and
          is FALSE now:** `UploadReadsWizard.tsx` joined
          `styles/route-b-migrated.txt` on 2026-08-27 (DEF-1000), which is what
          lets CR-054 task 9's chips above write utilities at all. A stale
          reason is hard-won law 1 in miniature, so it is corrected here rather
          than left to mislead the next lane into reusing a stylesheet class it
          does not need. */}
      <WriteModeField value={props.writeMode} onChange={props.onWriteMode} t={t} />
    </Panel>
  );
}

// ── Step 2 — Upload / enter (US-MET-007 · US-MET-017) ─────────────────────

/**
 * **CR-054 task 6 — THE READING SHEET, BESIDE THE BLANK TEMPLATE.**
 *
 * The button names its own number — *"↓ Reading sheet for CY-001 · 18 rows"* —
 * from `GET /cycles/{id}/reading-sheet/summary`, which is the SAME builder the
 * CSV route runs. A button that has to download the file to learn its size
 * downloads it twice, and two counting paths is how a button starts promising
 * 1,180 rows over a file with 1,176 (hard-won law 5).
 *
 * ⚠ **IT IS OFFERED BESIDE THE BLANK TEMPLATE, NEVER INSTEAD OF IT.** The blank
 * template is BR-MET-032's one published file and is what a utility with its own
 * hand-held collector, or no cycle tagged, actually needs. The sheet is the
 * PO's ask of 2026-08-30 — *"instead of they figuring out what to do we have
 * hande dthem all details"* — and it needs a cycle to know which meters to list.
 *
 * ⚠ **DISABLED WITH ITS REASON, THREE WAYS (BR-SHL-025).** No cycle tagged on
 * stage 1; the cycle has no read window (the server answers 200 with
 * `window_absent_reason` precisely so this control can say so without a failed
 * request); or the sheet is empty. Each states which, in the SERVER's own words
 * where the server has them.
 */
function ReadingSheetButton(props: {
  cycleCode: string | null;
  summary: ReadingSheetSummary | null;
  loading: boolean;
  error: string | null;
  downloading: boolean;
  onDownload: () => void;
  t: Translator;
}) {
  const { t } = props;
  const reason =
    props.cycleCode === null
      ? t("metering.upload.file.sheetNoCycle")
      : props.error !== null
        ? props.error
        : props.summary === null
          ? null
          : props.summary.window_absent_reason !== null
            ? t("metering.read.reason.cycle_window_not_set")
            : props.summary.rows === 0
              ? t("metering.upload.file.sheetEmpty")
              : null;
  const ready = reason === null && props.summary !== null && !props.loading;
  return (
    <div data-reads="reading-sheet">
      <Button
        variant="secondary"
        disabled={!ready || props.downloading}
        onClick={props.onDownload}
      >
        {ready && props.summary !== null
          ? t("metering.upload.file.sheetDownload", {
              cycle: props.summary.cycle_code,
              rows: props.summary.rows,
            })
          : t("metering.upload.file.sheetDownloadPlain")}
      </Button>
      {reason !== null && (
        <p className={WF.STAGE_BLURB} data-reads="reading-sheet-reason">
          {reason}
        </p>
      )}
    </div>
  );
}

function UploadStep(props: {
  tags: BatchTags;
  text: string;
  fileName: string;
  manual: readonly ReadManualRow[];
  staging: boolean;
  stageError: string | null;
  batch: ReadBatchStaged | null;
  /** The rows the SERVER staged — task 11's panel and stage 3 read ONE array. */
  rows: readonly ReadImportBatchRow[];
  sheet: {
    cycleCode: string | null;
    summary: ReadingSheetSummary | null;
    loading: boolean;
    error: string | null;
    downloading: boolean;
    onDownload: () => void;
  };
  onText: (text: string, name: string) => void;
  onManual: (rows: ReadManualRow[]) => void;
  /** `CR-077` — which of the four read shapes to hand out. The SHAPE is the
   *  parameter because the template is one file: same header, same mapping,
   *  different worked rows. */
  onDownloadStarter: (shape: ReadShape) => void;
  onStage: () => void;
  /** IS-8 — the tenant's Regional date format, for the kit's date field. */
  dateFormat: ReturnType<typeof useRegional>["dateFormat"];
  t: Translator;
}) {
  const { t } = props;
  const manualMode = props.tags.source_kind === SOURCE_KIND_MANUAL;
  // ⚖️ **Q7 — A ROW WITH NO REGISTER DOES NOT STAGE, AND THE BUTTON SAYS WHY.**
  // The register is the one field on this grid whose mistake cannot be undone
  // (`supersede_read` takes a value and a reason; migration `0007`'s trigger
  // freezes the channel), so the refusal sits BEFORE the write rather than in a
  // correction afterwards. Nothing about billing is decided here — an unchosen
  // register is simply not an answer.
  const missingRegister = manualMode ? manualRowsMissingRegister(props.manual) : [];
  const ready = manualMode
    ? filledManualRows(props.manual).length > 0 && missingRegister.length === 0
    : props.text.trim() !== "";
  const fileInput = useRef<HTMLInputElement>(null);
  const staged = props.batch;
  // ⚠ THE FACTS ARE THE SERVER'S, and before it has answered there are none.
  // `size_label` is the BYTES THE BROWSER HOLDS, which is the one fact the
  // browser genuinely owns; the row count and the SHA-256 are the server's and
  // appear when it has spoken (BR-MET-018: the hash is what identifies a batch,
  // and a client-supplied one proves nothing).
  const received: ReceivedFile | null =
    props.text.trim() === ""
      ? null
      : {
          name: staged?.compliance.file_name ?? props.fileName,
          rows: staged?.counts.rows ?? 0,
          size_label: `${Math.max(1, Math.round(new Blob([props.text]).size / 1024))} KB`,
          sha256: staged?.compliance.file_hash ?? "",
        };
  const mappingRows = staged === null ? [] : fileMappingRows(props.text, staged.mapping);
  const absentTargets = staged === null ? [] : unmappedTargets(staged.mapping);
  // BR-MET-032 forbids a remembered mapping and no route remaps a read batch, so
  // the picker is not drawn — but the column still needs its LABELS, which are
  // this screen's own template vocabulary.
  const mappingTargets: TargetColumn[] = mappingRows
    .map((row) => row.target_column)
    .filter((target): target is string => target !== null)
    .map((target) => ({
      id: target,
      // CR-161-BRC10 W4 — a utility's own reading field is named by its LABEL,
      // served beside the mapping; the template's own columns by the catalogue.
      label:
        staged?.mapping_labels?.[target] ??
        t(`metering.upload.target.${target}`, { defaultValue: target }),
      required: false,
    }));

  return (
    <Panel>
      <h3>{manualMode ? t("metering.upload.manual.title") : t("metering.upload.file.title")}</h3>
      <p className={WF.STAGE_BLURB}>
        {manualMode ? t("metering.upload.manual.hint") : t("metering.upload.file.hint")}
      </p>

      {!manualMode && (
        <>
          {/* BR-MET-032: the PUBLISHED template comes first, and CR-054's
              pre-filled READING SHEET beside it. "Upload your reads" without the
              column list is not a feature; handing a clerk a blank template and
              six decisions they are never told about is barely one.

              ⚠ **FOUR STARTERS SINCE `CR-077`, AND THE SHAPE IS THE FILE
              LAYOUT RATHER THAN THE TARIFF.** One button handed out one worked
              example — energy plus a peak row — so a utility on time-of-use
              meters had to work out from the column list that three rows share
              a date, and a net-metering utility that `export` is a row and not
              a column. Each button downloads the SAME header with that shape's
              rows under it; the mapping step behaves identically for all four,
              which is what BR-MET-032's "exactly one published template" means.

              ⚠ **THERE IS NO SEASONAL BUTTON AND ITS ABSENCE IS THE POINT.** A
              season is a property of the price list, worked out from the date
              on the reading, so a seasonal read is a flat read on a date. A
              fifth button would send a clerk looking for a column no parser
              reads. */}
          <div className="mt-3 mb-2 flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">
              {t("metering.upload.file.starters")}
            </span>
            {READ_SHAPES.map((shape) => (
              <Button
                key={shape}
                variant="secondary"
                size="sm"
                onClick={() => props.onDownloadStarter(shape)}
                data-testid={`reads-starter-${shape}`}
              >
                {t(`metering.upload.file.starter.${shape}`)}
              </Button>
            ))}
          </div>
          <div className="mb-4 flex flex-wrap items-start gap-3">
            <ReadingSheetButton
              cycleCode={props.sheet.cycleCode}
              summary={props.sheet.summary}
              loading={props.sheet.loading}
              error={props.sheet.error}
              downloading={props.sheet.downloading}
              onDownload={props.sheet.onDownload}
              t={t}
            />
          </div>

          {/* ⚠ **CR-054 task 18 — THE KIT'S DROP TARGET.** The bare
              `<input type="file" class="input">` in a `.field` div is gone: this
              is the same target the other six workflows draw, and it STATES WHAT
              IT RECEIVED — the name, the row count and the SHA-256 the receipt
              promises at stage 5. A hash a clerk first meets on the receipt is a
              hash they cannot compare against anything. */}
          <input
            ref={fileInput}
            id="reads-file"
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file === undefined) {
                return;
              }
              void file.text().then((text) => props.onText(text, file.name));
            }}
          />
          <DropZone file={received} onBrowse={() => fileInput.current?.click()} />

          {/* A pasted CSV is the same input by another route — and it is what
              makes this step provable without a browser file dialog. */}
          <TextField
            id="reads-text"
            label={t("metering.upload.file.paste")}
            multiline
            value={props.text}
            onChange={(value) => props.onText(value, props.fileName)}
          />
        </>
      )}

      {manualMode && (
        <>
          <div className={WF.TABLE_WRAP} data-reads="manual-grid">
            <PlainTable>
              <thead>
                <tr>
                  <th scope="col">{t("metering.upload.manual.col.meter")}</th>
                  <th scope="col">{t("metering.upload.manual.col.date")}</th>
                  <th scope="col">{t("metering.upload.manual.col.channel")}</th>
                  <th scope="col">{t("metering.upload.manual.col.reading")}</th>
                  <th scope="col">{t("metering.upload.manual.col.notes")}</th>
                </tr>
              </thead>
              <tbody>
                {props.manual.map((row, index) => (
                  <tr key={index}>
                    <td>
                      <input
                        className="input"
                        aria-label={t("metering.upload.manual.col.meter")}
                        value={row.meter_id}
                        onChange={(event) =>
                          props.onManual(
                            props.manual.map((entry, i) =>
                              i === index ? { ...entry, meter_id: event.target.value } : entry,
                            ),
                          )
                        }
                      />
                    </td>
                    <td>
                      {/* ⚖️ **THE KIT'S DATE FIELD, NOT A RAW `<input
                          type="date">` (`CR-096-BRC02`).** The blueprint draws
                          this cell as the product's own date control and says
                          so in its own note — the manual grid is *"drawn to the
                          kit"*, and two of its five cells were hand-rolled with
                          `className="input"` while stage 1, three panels
                          earlier, used the kit for the same kind of choice.
                          **It is not a cosmetic difference:** a bare native box
                          takes its calendar, its parsing and its keyboard from
                          the BROWSER, so the control a clerk meets changes with
                          the machine they sit at. `labelHidden` because the
                          column header is the label. */}
                      <DatePickerField
                        id={`reads-manual-date-${index}`}
                        label={t("metering.upload.manual.col.date")}
                        labelHidden
                        value={row.read_date}
                        dateFormat={props.dateFormat}
                        onChange={(value) =>
                          props.onManual(
                            props.manual.map((entry, i) =>
                              i === index ? { ...entry, read_date: value } : entry,
                            ),
                          )
                        }
                      />
                    </td>
                    <td>
                      {/* ⚖️ **Q7 (PO 2026-09-14, *"Put this first"*) — THE ONE
                          CONTROL ON THIS SCREEN THAT CAN COST $4,378.**
                          BR-MET-059: one row per register per date, and the
                          register is CHOSEN, never assumed. The placeholder is
                          the choice not yet made, so a clerk cannot stage a
                          reading against a register they never looked at — and
                          `Stage the batch` refuses with its reason until every
                          filled row has one. **The options are `READ_CHANNELS`,
                          the shared constant that mirrors the server's own
                          `models.CHANNELS`** — never a list typed out here,
                          which is the failure that keeps an eleventh service
                          off the sign-up screen. */}
                      <SelectField
                        id={`reads-manual-register-${index}`}
                        label={t("metering.upload.manual.col.channel")}
                        labelHidden
                        required
                        value={row.channel}
                        placeholder={t("metering.upload.manual.registerPlaceholder")}
                        options={READ_CHANNELS.map((channel) => ({
                          value: channel,
                          label: t(`metering.reads.channel.${channel}`),
                        }))}
                        onChange={(value) =>
                          props.onManual(
                            props.manual.map((entry, i) =>
                              i === index ? { ...entry, channel: value } : entry,
                            ),
                          )
                        }
                      />
                    </td>
                    <td className={WF.NUM_CELL}>
                      <input
                        className="input cell-num"
                        inputMode="decimal"
                        aria-label={t("metering.upload.manual.col.reading")}
                        value={row.reading}
                        onChange={(event) =>
                          props.onManual(
                            props.manual.map((entry, i) =>
                              i === index ? { ...entry, reading: event.target.value } : entry,
                            ),
                          )
                        }
                      />
                    </td>
                    <td>
                      <input
                        className="input"
                        aria-label={t("metering.upload.manual.col.notes")}
                        value={row.notes ?? ""}
                        onChange={(event) =>
                          props.onManual(
                            props.manual.map((entry, i) =>
                              i === index ? { ...entry, notes: event.target.value } : entry,
                            ),
                          )
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          </div>
          <Button
            variant="ghost"
            onClick={() => props.onManual([...props.manual, emptyManualRow()])}
          >
            {t("metering.upload.manual.addRow")}
          </Button>
          {/* ⛔ **CR-054 task 20 — THE 40-WORD `ArrivesWith` HERE IS DELETED.**
              It explained that the plan-aware entry form (US-MET-017) is not
              built. That is the third kind of sentence CR-054's copy rule
              deletes: it explains what is not built, to a clerk who is typing
              readings and cannot act on it. The story is still US-MET-017 and
              the register column above is still the thing that stages a
              time-of-use meter — both of which a reader finds in the register,
              which is what the register is for. */}
        </>
      )}

      <Button
        variant="primary"
        disabled={!ready || props.staging}
        onClick={props.onStage}
      >
        {props.staging ? t("metering.upload.file.staging") : t("metering.upload.file.stage")}
      </Button>
      {/* ⚖️ **Q7 — A DISABLED CONTROL OWES THE READER ITS REASON**
          (`BR-SHL-025`), and this refusal is a STATE rather than a permanent
          one, which is the Q6 test for disabling rather than removing. Six
          words per sentence, B14 rule 33's instruction cap. */}
      {missingRegister.length > 0 && (
        <p className={WF.STAGE_BLURB} data-reads="manual-register-missing">
          {t("metering.upload.manual.registerMissing")}
        </p>
      )}
      {props.stageError !== null && (
        <RefusalStrip role="alert">
          {props.stageError}
        </RefusalStrip>
      )}

      {staged !== null && (
        <>
          <p className={WF.STAGE_BLURB} role="status">
            {t("metering.upload.file.staged", {
              rows: staged.counts.rows,
              batch: staged.batch_no ?? staged.id,
            })}
          </p>

          {/* ⚖️ **CR-054 task 11 — WHAT IS IN THIS FILE.** Rows, meters,
              services, reading dates and the count PER REGISTER, grouped from
              the rows the server already staged. It answers the question a clerk
              cannot otherwise ask until stage 3: *is this the file I meant to
              send?* — and the per-register line is the one that catches a
              time-of-use cycle uploaded with one row per meter. */}
          {props.rows.length > 0 && (
            <ReconcileStrip
              caption={t("metering.upload.file.inFile.caption")}
              figures={fileComposition(props.rows, t)}
              layout="rows"
            />
          )}

          {/* BR-MET-013: the mapping the server auto-detected against the
              published template — now with a SAMPLE VALUE out of the clerk's own
              file, which is the column that turns "your header became
              `read_date`" into something checkable. DISPLAY only: BR-MET-032
              forbids a remembered mapping and no route remaps a read batch, so
              the kit's picker is not drawn (`readOnly`). */}
          {mappingRows.length > 0 && (
            <MappingTable
              rows={mappingRows}
              targets={mappingTargets}
              idPrefix="reads-map"
              onTargetChange={() => undefined}
              readOnly
            />
          )}
          {absentTargets.length > 0 && (
            <p className={WF.STAGE_BLURB} data-reads="mapping-absent">
              {t("metering.upload.file.unmappedTargets", {
                columns: absentTargets
                  .map((target) => t(`metering.upload.target.${target}`, { defaultValue: target }))
                  .join(", "),
              })}
            </p>
          )}
          <p className={WF.STAGE_BLURB}>{t("metering.upload.file.nothingPostedYet")}</p>
        </>
      )}
    </Panel>
  );
}

// ── Step 3 — Validation (US-MET-008) ──────────────────────────────────────

/**
 * The five figures of the validate stage, as the kit's own tiles.
 *
 * ⚠ **`MISSING` IS A REAL NUMBER NOW, AND THE 33-WORD NOTE THAT STOOD IN ITS
 * PLACE WAS FALSE (hard-won law 1, CR-054 task 20).** It read: *"How many
 * readings a cycle should have is worked out from each unit's plan, and that
 * calculation is not built. A zero here would say nothing is missing, which is a
 * different claim."* The first sentence stopped being true when CR-038 W1 built
 * `BR-MET-049`'s resolver: `validate_read_batch` answers `cycle_coverage` with
 * `expected`, `received` and `missing`, and the stage-4 shortfall panel has been
 * rendering it since. This tile went on printing an em-dash and an explanation
 * of an absence that had been filled — which is exactly the shape G38 exists for
 * and the shape DEF-445 cost a support cycle to learn.
 *
 * The SECOND sentence still holds, so the em-dash survives for the case it was
 * written for: when the batch carries no cycle there is nothing to measure
 * against, and the server says so in `cycle_coverage_absent_reason`.
 */
export function validationTiles(
  validation: ReadBatchValidation,
  t: Translator,
): ReconcileFigure[] {
  const counts = validation.counts;
  const coverage = validation.cycle_coverage ?? null;
  return [
    { id: "rows", label: t("metering.upload.kpi.rows"), value: counts.rows, flagged: false },
    { id: "passed", label: t("metering.upload.kpi.passed"), value: counts.passed, flagged: false },
    {
      id: "warnings",
      label: t("metering.upload.kpi.warnings"),
      value: counts.warnings,
      flagged: counts.warnings > 0,
    },
    {
      id: "errors",
      label: t("metering.upload.kpi.errors"),
      value: counts.errors,
      flagged: counts.errors > 0,
    },
    {
      id: "missing",
      label: t("metering.upload.kpi.missing"),
      // ⛔ DEF-2440 — `coverage.missing` is a field the server has never sent,
      // so this tile rendered EMPTY: not an em-dash, not a zero, nothing at all.
      value: coverage === null ? ABSENT_TEXT : coverage.missing_after_batch,
      flagged: coverage !== null && coverage.missing_after_batch > 0,
    },
  ];
}

function ValidateStep(props: {
  validation: ReadBatchValidation | null;
  // The staged rows come from `GET /read-batches/{id}`, NOT from the validate
  // answer: that endpoint returns the batch and its counts and no rows at all.
  // Reading `validation.rows` crashed this screen in a browser with
  // "TypeError: t is not iterable" — found by clicking, by nothing else.
  rows: readonly ReadImportBatchRow[];
  running: boolean;
  error: string | null;
  onRun: () => void;
  /** CR-054 task 13 — the two bulk actions on a shortfall group. */
  bulkBusy: boolean;
  onEstimateGroup: (group: RegisterGroup) => void;
  onFieldVisitGroup: (group: RegisterGroup) => void;
  t: Translator;
}) {
  const { t } = props;
  return (
    <Panel>
      {/* ⚖️ **NO PANEL HEADING (`CR-096-BRC02`).** The blueprint draws stage 3
          as `STAGE 3 OF 5 · VALIDATE` over **The rules** and *"Errors block the
          load. Warnings do not."*, then the button — ONE heading and ONE
          sentence. This panel printed a second heading and a second sentence
          under the runner's own, which is twice B14 rule 32's budget on a
          screen that already carries a five-tile strip, two tables and four
          segments. The heading is the runner's, per this target's `stageCopy`. */}
      <Button
        variant="primary"
        disabled={props.running}
        onClick={props.onRun}
      >
        {props.running ? t("metering.upload.validate.running") : t("metering.upload.validate.run")}
      </Button>
      {props.error !== null && (
        <RefusalStrip role="alert">
          {props.error}
        </RefusalStrip>
      )}
      {props.validation !== null && (
        <>
          <ReconcileStrip
            caption={null}
            figures={validationTiles(props.validation, t)}
            layout="tiles"
            tiles={5}
          />
          {/* The server's own reconciliation: every row lands in exactly one
              severity bucket. A false here is a row that vanished between the
              file and the summary, and that is worth its own line. */}
          {!props.validation.counts.reconciles && (
            <RefusalStrip role="alert">
              {t("metering.upload.validate.doesNotReconcile", {
                rows: props.validation.counts.rows,
                total: props.validation.counts.severity_total,
              })}
            </RefusalStrip>
          )}
          {/* BR-MET-020's fail-safe half. A batch that reports "everything
              passed" while rules never ran is the comment-as-guarantee failure
              in data form, so the rules that could NOT run are named. */}
          {!props.validation.validation_config_present && (
            <RefusalStrip role="alert">
              {t("metering.upload.validate.noConfig")}
            </RefusalStrip>
          )}
          {/* ⚠ **CR-054 task 18 — ONE TABLE WHERE THERE WERE TWO.** The
              `Rules that could not run` bulleted list is gone: `RuleResultsTable`
              lists an unavailable rule IN PLACE with its reason, which is
              BR-MET-091's own shape and the reason the kit's table has an
              `available` column at all. */}
          <RuleResultsTable
            caption={t("metering.upload.validate.outcomesCaption")}
            rules={ruleResults(props.rows, props.validation.unevaluated_rules, t)}
            emptyMessage={t("metering.upload.validate.allClear")}
          />
          {/* ⚖️ **CR-054 tasks 12 and 13 — THE REGISTER-COMPLETENESS TABLE.** */}
          <RegisterCompleteness
            groups={registerGroups(props.rows)}
            busy={props.bulkBusy}
            onEstimate={props.onEstimateGroup}
            onFieldVisit={props.onFieldVisitGroup}
            t={t}
          />
        </>
      )}
    </Panel>
  );
}

// ── Step 4 — Review & fix (US-MET-008 · US-MET-009) ───────────────────────

function ReviewStep(props: {
  rows: readonly ReadImportBatchRow[];
  segment: ReviewSegment;
  pending: Record<number, { disposition: string; reason: string; value: string }>;
  saving: number | null;
  error: string | null;
  onSegment: (segment: ReviewSegment) => void;
  onEdit: (
    rowNo: number,
    patch: Partial<{ disposition: string; reason: string; value: string }>,
  ) => void;
  onSave: (row: ReadImportBatchRow) => void;
  onAcceptAllWarnings: () => void;
  /** BR-MET-051 (CR-038 W4) — the reset, in bulk and per row. */
  demandReset: DemandResetReport | null;
  demandResetBusy: boolean;
  onDemandResetAll: () => void;
  onDemandResetRow: (row: ReadImportBatchRow, noted: boolean) => void;
  /** ⛔ DEF-2443 (CR-054 task 21) — the ONE date formatter (BR-SHL-034). */
  timeZone: string;
  dateFormat: ReturnType<typeof useRegional>["dateFormat"];
  /** CR-054 task 15 — what will post and what will not, from `postSplit()`. */
  split: PostSplit;
  /** CR-054 task 17 — the rejects file, offered HERE as well as on the
   *  receipt. `null` until the batch has been validated (BR-SHL-025). */
  onDownloadRejects: (() => void) | null;
  rejectsBusy: boolean;
  rejectsError: string | null;
  /** CR-054 task 25 — tiered rows dated off the stated reading month. */
  tieredOffMonth: readonly number[];
  periodMonth: string;
  t: Translator;
}) {
  const { t } = props;
  const visible = reviewRows(props.rows, props.segment);
  const flagged = props.rows.filter((row) => row.severity !== "ok");

  return (
    <Panel>
      <h3>{t("metering.upload.review.title")}</h3>
      <p className={WF.STAGE_BLURB}>{t("metering.upload.review.hint")}</p>

      {/* DEF-896's third site: a pill group is a flex row, not `.met-filters`'
          200px-minimum grid. This file IS on `src/styles/route-b-migrated.txt`
          (added 2026-08-27 by DEF-1000's own entry), so a Tailwind utility here
          is compiled and rendered — which is the half DEF-974 says to check
          BEFORE writing one. */}
      <div className="flex flex-wrap gap-2">
        {REVIEW_SEGMENTS.map((segment) => (
          <Button
            key={segment}
            variant={props.segment === segment ? "secondary" : "ghost"}
            aria-pressed={props.segment === segment}
            onClick={() => props.onSegment(segment)}
          >
            {t(`metering.upload.review.segment.${segment}`, {
              count:
                segment === "all"
                  ? flagged.length
                  : flagged.filter((row) => row.severity === segment).length,
            })}
          </Button>
        ))}
        {/* The prototype's bulk action. It records a REASON on every row it
            touches (BR-MET-015) — a bulk accept that stored no reason would be
            the rule with its evidence removed. */}
        <Button variant="ghost"  onClick={props.onAcceptAllWarnings}>
          {t("metering.upload.review.acceptAllWarnings")}
        </Button>
        {/* BR-MET-051's bulk sibling (CR-038 W4). It acts on EVERY demand row in
            the batch, not only the flagged ones the table below is filtered to,
            because a reset is a fact about the register. */}
        <DemandResetBulkControl
          rows={props.rows}
          busy={props.demandResetBusy}
          report={props.demandReset}
          onNote={props.onDemandResetAll}
          t={t}
        />
      </div>

      {/* ⚖️ **CR-054 TASK 15 — A STATEMENT, NOT A REFUSAL.** What stood here was
          a `RefusalStrip` reading *"{{count}} error row(s) still need a
          decision before this batch can post."* — read in a browser at 2.94.0,
          the same day `commit_read_batch` stopped refusing. It described a
          refusal the server no longer makes, above a `Load →` this screen had
          disabled, so a clerk with 2 bad rows in 1,180 could not reach the
          behaviour the PO asked for at all. Both halves go together: the
          sentence AND the fence below. */}
      <PostSplitStatement
        willPost={props.split.willPost}
        willHold={props.split.willHold}
        unresolvedErrors={props.split.unresolvedErrors}
        reconciles={props.split.reconciles}
        onDownload={props.onDownloadRejects}
        downloading={props.rejectsBusy}
        downloadError={props.rejectsError}
        t={t}
      />
      {/* CR-054 task 25 — B4.4's tier boundaries scale with the period, so a
          mistyped date reprices every band and the bill still looks right. */}
      <TieredDateWarning rowNos={props.tieredOffMonth} statedMonth={props.periodMonth} t={t} />

      {visible.length === 0 ? (
        <p className={WF.STAGE_BLURB}>{t("metering.upload.review.nothingFlagged")}</p>
      ) : (
        <div className={WF.TABLE_WRAP} data-reads="review-rows">
        <PlainTable>
          <thead>
            <tr>
              <th scope="col">{t("metering.upload.col.row")}</th>
              <th scope="col">{t("metering.reads.col.meter")}</th>
              <th scope="col">{t("metering.reads.col.readAt")}</th>
              <th scope="col">{t("metering.reads.col.channel")}</th>
              <th scope="col" className={WF.NUM_HEAD}>{t("metering.upload.col.register")}</th>
              <th scope="col">{t("metering.upload.col.reason")}</th>
              <th scope="col">{t("metering.upload.col.action")}</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => {
              const draft = props.pending[row.row_no] ?? {
                disposition: row.disposition ?? "",
                reason: row.disposition_reason ?? "",
                value: row.value ?? "",
              };
              return (
                <tr key={row.row_no}>
                  <td className={WF.NUM_CELL}>{row.row_no}</td>
                  <td>{row.meter_no ?? <Dash />}</td>
                  {/* ⛔ **DEF-2443 (CR-054 task 21) — THE READ DATE WENT
                      THROUGH NO FORMATTER AT ALL.** This cell was
                      `{row.read_at ?? row.read_at_raw ?? <Dash />}`, so a clerk
                      reviewing flagged rows read
                      `2026-08-03T00:00:00+00:00` — the raw ISO instant, with
                      its offset — on the one screen in the product where a
                      wrong read date is still cheap to fix. Every other date in
                      the product renders `08/14/2026` through `DateCell`, which
                      is BR-SHL-034 in one component ("one date formatter").
                      `read_at_raw` is the clerk's OWN cell as they typed it and
                      is NOT put through the formatter: a string the parser
                      refused is evidence, and re-rendering it would hide what
                      they have to correct. */}
                  <td>
                    {row.read_at !== null ? (
                      <DateCell
                        value={row.read_at}
                        timeZone={props.timeZone}
                        dateFormat={props.dateFormat}
                      />
                    ) : (
                      (row.read_at_raw ?? <Dash />)
                    )}
                  </td>
                  <td>
                    {t(`metering.reads.channel.${row.channel}`, { defaultValue: row.channel })}
                  </td>
                  {/* The REGISTER reading WITH ITS UNIT — BR-MET-143. `kW` on a
                      demand row, `kWh` on the energy row of the same meter, so a
                      clerk approving 1,180 rows can SEE the unit that commits
                      (DEF-797 shipped a peak stamped kWh: $154.00 against a
                      correct $4,532.00). There is still no USAGE column: the
                      consumption is computed at commit. */}
                  <td className={WF.NUM_CELL}>
                    <StagedRegisterValue value={row.value} unit={row.unit} t={t} />
                  </td>
                  <td>
                    <StatusPill tone={severityTone(row.severity)}>
                      {t(`metering.read.severity.${row.severity}`, { defaultValue: row.severity })}
                    </StatusPill>{" "}
                    {rowReasonText(row, t)}
                  </td>
                  <td>
                    <select
                      className="input"
                      aria-label={t("metering.upload.col.action")}
                      value={draft.disposition}
                      onChange={(event) =>
                        props.onEdit(row.row_no, { disposition: event.target.value })
                      }
                    >
                      <option value="">{t("metering.upload.review.choose")}</option>
                      {dispositionsFor(row.severity).map((disposition) => (
                        <option key={disposition} value={disposition}>
                          {t(`metering.upload.disposition.${disposition}`)}
                        </option>
                      ))}
                    </select>
                    {draft.disposition === "override" && (
                      <input
                        className="input cell-num"
                        inputMode="decimal"
                        aria-label={t("metering.upload.review.overrideValue")}
                        placeholder={t("metering.upload.review.overrideValue")}
                        value={draft.value}
                        onChange={(event) =>
                          props.onEdit(row.row_no, { value: event.target.value })
                        }
                      />
                    )}
                    {reasonRequired(draft.disposition) && (
                      <input
                        className="input"
                        aria-label={t("metering.upload.review.reason")}
                        placeholder={t("metering.upload.review.reason")}
                        value={draft.reason}
                        onChange={(event) =>
                          props.onEdit(row.row_no, { reason: event.target.value })
                        }
                      />
                    )}
                    <Button
                      variant="ghost"
                      disabled={draft.disposition === "" || props.saving === row.row_no}
                      onClick={() => props.onSave(row)}
                    >
                      {props.saving === row.row_no
                        ? t("metering.upload.review.saving")
                        : t("metering.upload.review.save")}
                    </Button>
                    {/* BR-MET-051 — the per-row reset, offered where the
                        SERVER says the row is the demand register. */}
                    <DemandResetRowToggle
                      row={row}
                      busy={props.demandResetBusy}
                      onToggle={props.onDemandResetRow}
                      t={t}
                    />
                    {row.disposition !== null && (
                      <span className="met-qualifier">
                        {" "}
                        {t("metering.upload.review.recorded", {
                          disposition: t(`metering.upload.disposition.${row.disposition}`, {
                            defaultValue: row.disposition,
                          }),
                        })}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </PlainTable>
        </div>
      )}
      {props.error !== null && (
        <RefusalStrip role="alert">
          {props.error}
        </RefusalStrip>
      )}
      {/* US-MET-009's Replace-existing path is the `override` disposition on a
          duplicate row: the commit APPENDS a superseding read and closes the
          old head (BR-MET-016/053). It is not a separate control, because it is
          not a separate write. */}
      <p className={WF.STAGE_BLURB}>{t("metering.upload.review.duplicateNote")}</p>
    </Panel>
  );
}

// ── Step 5 — Compliance & post (US-MET-010) ───────────────────────────────

function PostStep(props: {
  batch: ReadBatchValidation | ReadBatchStaged;
  certified: boolean;
  writeBlockedReason: string | null;
  timeZone: string;
  dateFormat: ReturnType<typeof useRegional>["dateFormat"];
  onCertified: (value: boolean) => void;
  /** CR-038 W7 — the premise, STATED here and changed at the stage that owns
   *  it. DEF-770: two controls for one setting, and nothing said which won. */
  writeMode: ReadWriteMode;
  onChangeWriteMode: () => void;
  /** BR-MET-130 — the shortfall, on the screen where the post happens.
   *  ⛔ DEF-2440: the SERVER's field names, not three that nothing sends. */
  coverage: ReadCycleCoverage | null;
  coverageAbsentReason: string | null;
  /** OQ-042 — the co-sign, whose writer landed with CR-038 W7 task 5. */
  mayCosign: boolean;
  cosignBusy: boolean;
  cosignError: string | null;
  onCosign: () => void;
  /** CR-054 task 15 — the same `postSplit()` stage 3 stated and the button names. */
  split: PostSplit;
  /** DEF-MET-8106 — the background post's job while it runs; `null` when the
   *  post runs while the clerk waits (at or below the server's bar). */
  postJob: JobRecord | null;
  t: Translator;
}) {
  const { t, batch, split } = props;
  const counts = batch.counts;
  return (
    <>
      {/* ⚖️ **FIVE PANELS, AS DRAWN (`CR-096-BRC02`, p029-p030).** Stage 4 was
          ONE panel holding a stamp, a seven-row strip, a checkbox, a co-sign, a
          coverage line and two notes in a single column. The blueprint draws it
          as five named groups — **EVIDENCE · COMPOSITION · COVERAGE · CO-SIGN ·
          CERTIFY** — which is the PO's Panel ruling of 2026-09-12 (*"in detail
          section use Panel to information groups"*) applied to the last screen
          before an irreversible write. The runner's stage head carries the
          heading (*"Certify it. Then post."*), so no panel repeats it. */}
      <Panel>
        <h3>{t("metering.upload.post.panel.evidence")}</h3>
      {/* BR-MET-017: the permanent stamp, exactly as the server built it. */}
      <dl className="met-facts">
        <dt>{t("metering.read.compliance.batch")}</dt>
        <dd>{batch.batch_no ?? t("metering.reads.batchUnnumbered") /* DEF-SHL-6348 */}</dd>
        <dt>{t("metering.read.compliance.source")}</dt>
        <dd>
          {t(`metering.reads.sourceKind.${batch.source_kind}`, { defaultValue: batch.source_kind })}
          {batch.compliance.file_name !== null && ` · ${batch.compliance.file_name}`}
        </dd>
        <dt>{t("metering.read.compliance.hash")}</dt>
        <dd>{batch.compliance.file_hash ?? <Dash>{t("metering.upload.post.noHash")}</Dash>}</dd>
        <dt>{t("metering.read.compliance.uploadedBy")}</dt>
        {/* ⚠ **THE THIRD SURFACE WITH DEF-899's DEFECT, AND THE PO NEVER SAW
            THIS ONE.** S28's post receipt printed the uploader's raw primary
            key and then EXPLAINED it — *"The stamp stores the uploader's
            internal id; their name is not served with it"* — to the clerk who
            had just posted the batch and knew perfectly well who they were.
            BR-MET-163: the name is served now, so the sentence and the key
            both go. Same component as S29's panel, so the two cannot drift. */}
        <dd>
          <ActorName
            id={batch.compliance.uploaded_by}
            name={batch.compliance.uploaded_by_name ?? null}
            t={t}
          />
        </dd>
        <dt>{t("metering.read.compliance.uploadedAt")}</dt>
        <dd>
          {batch.compliance.uploaded_at === null ? (
            <Dash />
          ) : (
            <DateCell
              value={batch.compliance.uploaded_at}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
              withTime
            />
          )}
        </dd>
        <dt>{t("metering.read.compliance.session")}</dt>
        <dd>
          {/* ⚖️ **"NOT CAPTURED", NEVER AN EM DASH (`CR-096-BRC02`).** The
              server stamps these from the REQUEST, never from client input, and
              on a same-origin call in this deployment both arrive empty. The
              row rendered `— · —`, and the blueprint's own note says why that is
              wrong: *"An em dash reads as NOTHING TO SAY; the audit row's whole
              job is to say whether there is."* An auditor asking *"where was
              this posted from?"* eighteen months from now must be able to tell
              "we did not record it" from "this field is not filled in". */}
          {batch.compliance.session_ref === null && batch.compliance.ip === null ? (
            <span data-reads="session-not-captured" className="text-danger-700">
              {t("metering.upload.post.sessionNotCaptured")}
            </span>
          ) : (
            <>
              {batch.compliance.session_ref ?? <Dash />} · {batch.compliance.ip ?? <Dash />}
            </>
          )}
        </dd>
      </dl>
      </Panel>

      <Panel>
        <h3>{t("metering.upload.post.panel.composition")}</h3>
      {/* ⚖️ **FOUR COUNTS, AS DRAWN — WILL POST · HELD BACK · NO DECISION ·
          REJECTED (`CR-096-BRC02`).** This strip carried SEVEN figures in a
          `rows` ledger; the blueprint draws four tiles with two-word labels,
          and its own annotation says so: *"Composition · four counts, labels cut
          to two words · B14 33"*. The three that go — estimate requested, field
          visit, skipped — are not lost facts, they are SUBSETS of the four that
          remain: each is already counted in *will post* or *held back*, so
          printing them beside the totals invited exactly the arithmetic a clerk
          cannot do in their head.

          ⚠ **DEF-2731's LESSON IS UNTOUCHED AND IS WHY THE SOURCE IS
          `postSplit()`.** `counts.accepted` is the number of rows a PERSON
          accepted, and since BR-MET-129 an undispositioned OK or WARNING row
          posts too — so this strip once read *"Rows that will become readings:
          0"* over a batch that filed five. The figures here are the SAME
          `postSplit()` stage 3 states and the footer names, derived once. */}
      <ReconcileStrip
        caption={null}
        layout="tiles"
        tiles={4}
        figures={[
          {
            id: "will-post",
            label: t("metering.upload.post.willPost"),
            value: split.willPost,
            flagged: false,
          },
          {
            id: "will-hold",
            label: t("metering.upload.post.willHold"),
            value: split.willHold,
            flagged: split.willHold > 0,
          },
          {
            id: "unresolved",
            label: t("metering.upload.post.unresolved"),
            value: split.unresolvedErrors,
            flagged: split.unresolvedErrors > 0,
          },
          {
            id: "rejected",
            label: t("metering.upload.post.rejected"),
            value: counts.rejected,
            flagged: counts.rejected > 0,
          },
        ]}
      />
      <p className={WF.STAGE_BLURB}>{t("metering.upload.post.compositionNote")}</p>
      </Panel>

      {/* ⚖️ **BR-MET-130 (PO 2026-08-26): "allow it"** — and the rule's own
          condition, *"what is mandatory is the SHOWING"*. The blueprint gives
          coverage a Panel of its own, between the composition and the
          certification, because it answers a different question: not *what is
          in this file* but *what is still missing from the cycle*. */}
      <Panel>
        <h3>{t("metering.upload.post.panel.coverage")}</h3>
        <CycleShortfall
          coverage={props.coverage}
          absentReason={props.coverageAbsentReason}
          t={t}
        />
      </Panel>

      {/* ⚠ **CR-038 W7 — this was a STATED ABSENCE until that lane, and the
          right call at the time: nothing in the product could write a co-sign.
          `services.cosign_read_batch` is the writer that column never had.**
          ⚠ **LEFT EXACTLY AS IT WAS BY THIS LANE, DELIBERATELY.** `MR-17` — the
          BLOCKING half — was withdrawn by the PO on 2026-09-14 (*"we do not
          need confirmation or sign off from another person"*), reversing
          `OQ-042`'s closure. Nothing here was added, wired or widened; the
          existing optional control and its "does not hold the post" sentence
          are REPORTED rather than edited, so one lane owns the removal. */}
      <CosignPanel
        cosignedBy={batch.compliance.cosigned_by}
        cosignedAt={batch.compliance.cosigned_at ?? null}
        blocksPost={batch.compliance.cosign_blocks_post === true}
        mayCosign={props.mayCosign}
        busy={props.cosignBusy}
        onCosign={props.onCosign}
        formatWhen={(iso) => (
          <DateCell value={iso} timeZone={props.timeZone} dateFormat={props.dateFormat} />
        )}
        t={t}
      />
      {props.cosignError !== null && (
        <RefusalStrip role="alert">{props.cosignError}</RefusalStrip>
      )}

      <Panel>
        <h3>{t("metering.upload.post.panel.certify")}</h3>
      {/* BR-MET-017: certification is required before Post enables. */}
      <CheckboxField
        id="certified"
        label={t("metering.upload.post.certify")}
        checked={props.certified}
        onChange={props.onCertified}
      />
      {/* ⚖️ **THE CONSEQUENCE, ABOVE THE CONTROL THAT CAUSES IT
          (`CR-096-BRC02` · B14 rules 11 and 33).** Two sentences, four words
          and six: *"This creates N readings."* + *"A posted reading cannot be
          un-created."* Rule 33 allows a consequence before an irreversible act
          at most two sentences of six, and this is the act it was written for —
          `commit_read_batch` appends to `meter_reads`, and hard rule 4 makes
          every row of it permanent. The count is `postSplit()`'s, the same one
          the strip above and the footer below state, derived once. */}
      <p className={WF.STAGE_BLURB} data-reads="certify-consequence">
        <b>{t("metering.upload.post.createsReadings", { count: split.willPost })}</b>{" "}
        {t("metering.upload.post.neverUncreated")}
      </p>
      </Panel>

      {/* ⛔ DEF-770 — the mode is STATED, never offered a second time. */}
      <WriteModeStated
        value={props.writeMode}
        onChangeRequested={props.onChangeWriteMode}
        t={t}
      />

      {/* ⚖️ **BR-MET-055 — THE POST'S PROGRESS, FROM ITS JOB (DEF-MET-8106).**
          This place held *"Posting happens while you wait."*, stated because
          the post ran synchronously and a bar over a blocking call would be an
          animation with nothing behind it (DEF-115). It stopped being true the
          day a batch over the server's bar began posting in a worker, so the
          sentence is RETIRED rather than reworded (B14 rule 33: why the product
          works this way is zero words on screen) and what stands here instead
          is the job's own `N of M`, drawn only while there IS a job. */}
      <ReadPostProgress job={props.postJob} t={t} />
      {props.writeBlockedReason !== null && (
        <RefusalStrip role="alert">
          {props.writeBlockedReason}
        </RefusalStrip>
      )}
    </>
  );
}

function ResultPanel(props: {
  result: ReadBatchPosted;
  onDone: () => void;
  /** CR-054 task 17 — the SECOND offer of the rejects file. */
  onDownloadRejects: (() => void) | null;
  rejectsBusy: boolean;
  rejectsError: string | null;
  t: Translator;
}) {
  const { t, result } = props;
  // "N created · N failed", ALWAYS (BR-MET-038's discipline, the shape S16 and
  // S68 already use).
  //
  // ⛔ **`failed` NOW READS THE SERVER'S OWN `held_reads` (BR-MET-940).** It was
  // `counts.rows - posted_reads`, which is the same number and is a SECOND
  // derivation of it — and the receipt has the real one now, on the payload,
  // named by the ruling. The subtraction is kept only as a fallback for a batch
  // posted by a build older than 2.94.0.
  const created = result.posted_reads;
  const failed = result.held_reads ?? Math.max(0, result.counts.rows - created);
  const unresolved = result.unresolved_errors ?? 0;
  return (
    <div role="status" data-reads="receipt">
      {/* ⚖️ **THREE PANELS, AS DRAWN (`CR-096-BRC02`, p033-p034).** The
          blueprint's own note says why it is three and not one: *"a receipt is
          three separate objects — what happened, what did not, and the batch
          itself."* This was ONE panel with a three-row fact list, a sentence
          that once did not add up, two conditional blocks and a button. The
          runner's stage head carries the heading — **Posted**. */}
      <Panel>
        <h3>{t("metering.upload.result.panel.composition")}</h3>
        {/* ⚠ **FOUR COUNTS, AND `SUPERSEDED` IS ONE OF THEM.** CR-038 W7's
            finding stands: 41 readings ADDED and 41 readings CORRECTED answered
            identically until `superseded_reads` was served, and on a
            corrections upload the second is the one the clerk came for. The
            blueprint draws it as a peer of POSTED rather than a note below.
            `held_reads` is BR-MET-940's own figure; the subtraction is kept
            only for a batch posted by a build older than 2.94.0. */}
        <ReconcileStrip
          caption={null}
          layout="tiles"
          tiles={4}
          figures={[
            { id: "posted", label: t("metering.upload.result.created"), value: created, flagged: false },
            {
              id: "superseded",
              label: t("metering.upload.result.superseded"),
              value: result.superseded_reads ?? 0,
              flagged: false,
            },
            { id: "held", label: t("metering.upload.result.failed"), value: failed, flagged: failed > 0 },
            {
              id: "refused",
              label: t("metering.upload.result.refused"),
              value: (result.skipped_rows ?? []).filter(
                (row) => row.reason === "billed_read_refused",
              ).length,
              flagged: false,
            },
          ]}
        />
        {/* ⛔ **DEF-2731's SECOND SURFACE IS STILL GONE.** A breakdown sentence
            here once read *"1 rejected · 0 · 0 · 5 left without a decision"*
            under ONE row that did not become a reading — six, over one. The
            five were undispositioned warnings, which BR-MET-129 FILES rather
            than holds, so they were in the created count directly above. Every
            figure in the strip is the server's own and is about one thing. */}
        {unresolved > 0 && (
          <p className={WF.STAGE_BLURB} data-reads="result-unresolved">
            {t("metering.upload.result.unresolved", { count: unresolved })}
          </p>
        )}
      </Panel>

      {/* ⚖️ **HELD BACK — only when something was.** An empty panel reading
          "0 rows could not be filed" is a panel a clerk reads and learns
          nothing from. */}
      {failed > 0 && (
        <Panel>
          <h3>{t("metering.upload.result.panel.heldBack")}</h3>
          {/* ⚖️ **CR-054 TASK 17, THE SECOND OFFER.** Stage 3 forecasts; this
              is the fact, and the receipt is the one a clerk comes back to an
              hour later. */}
          <RejectsDownload
            count={failed}
            onDownload={props.onDownloadRejects}
            downloading={props.rejectsBusy}
            error={props.rejectsError}
            where="receipt"
            t={t}
          />
        </Panel>
      )}

      {/* ⚖️ **BR-MET-127 — THE READINGS THIS UPLOAD REFUSED, BY NAME.** A batch
          that posts 1,179 of 1,180 and prints only the 1,179 is DEF-659 one row
          wide: the clerk walks away and one customer's correction is never
          made. */}
      <RefusedBilledRows
        rows={result.skipped_rows ?? []}
        total={
          (result.skipped_rows ?? []).filter((row) => row.reason === "billed_read_refused").length
        }
        t={t}
      />

      <Panel>
        <h3>{t("metering.upload.result.panel.batch")}</h3>
        <dl className="met-facts">
          <dt>{t("metering.read.compliance.batch")}</dt>
          {/* B14 rule 31 — the HUMAN-facing batch number, never the key. The
              uuid rides on `title` as evidence and reaches no clerk. */}
          <dd title={result.id}>
            {result.batch_no ?? t("metering.reads.batchUnnumbered", { defaultValue: "—" })}
          </dd>
          <dt>{t("metering.upload.result.rollback")}</dt>
          {/* ⚖️ **THE ROLLBACK ROW SAYS *Not available* RATHER THAN OFFERING
              ONE (`CR-096-BRC02`).** The shared runner's rollback sentence is,
              for reads, a REFUSAL: a posted read batch is immutable
              (BR-MET-017) and a committed reading can only ever be SUPERSEDED,
              never un-created (hard rule 4 / B2 DB-6). `import_runs.rollback`
              has no reads branch and no reads rollback service exists. Printing
              the runner's generic *"rolling back reverses every reading this
              run created"* here would be one target's sentence repeated where
              it is false — DEF-623 exactly — above the one pipeline in the
              product where acting on it would breach a hard rule. */}
          <dd>
            <span className="text-danger-700" data-reads="rollback-unavailable">
              {t("metering.upload.result.rollbackUnavailable")}
            </span>
          </dd>
        </dl>
        <p className={WF.STAGE_BLURB}>{t("metering.upload.result.supersededNotUncreated")}</p>
      </Panel>

      {/* CR-038 W7 — the two figures `posted_reads` could never tell apart,
          said in words where the strip states them as numbers. */}
      <SupersededSummary
        count={result.superseded_reads ?? 0}
        mode={(result.write_mode ?? DEFAULT_READ_WRITE_MODE) as ReadWriteMode}
        t={t}
      />
      {/* BR-MET-055 / DEF-115 — the commit ran synchronously; SAID, not drawn
          as a bar over a call that had already returned. */}
      {result.async === false && (
        <p className={WF.STAGE_BLURB}>{t("metering.upload.result.sync")}</p>
      )}

      {/* ⚖️ **STAGE 5 HAS A FOOTER, AND THE RUNNER CANNOT DRAW IT.**
          `WORKFLOW_STAGES[4].advanceKey` is `null`, so the runner renders no
          footer on the receipt and `WorkflowRunner.test.tsx` asserts exactly
          that for every target. The blueprint draws two controls on a footer
          line here — the rejects file on the left, `Back to Reads` on the
          right — so the receipt draws its own, in the frame's footer shape. */}
      <div className={WF.FOOTER} data-reads="receipt-footer">
        {failed > 0 && props.onDownloadRejects !== null && (
          <Button
            variant="secondary"
            disabled={props.rejectsBusy}
            onClick={props.onDownloadRejects}
          >
            {t("metering.upload.result.rejectsFile")}
          </Button>
        )}
        <Button variant="primary" onClick={props.onDone}>
          {t("metering.upload.result.viewReads")}
        </Button>
      </div>
    </div>
  );
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface UploadReadsWizardProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function UploadReadsWizard(props: UploadReadsWizardProps) {
  const client = props.client ?? api;
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props);
  const cell = useAccessCell(PREMISES_PERMISSION, client);
  /**
   * OQ-042's closure names the qualifying roles — *"supervisor =
   * SysAdmin/Executive"* — and the SERVER enforces it (`@require_role`). This
   * decides only whether the co-sign button is offered ENABLED or drawn
   * disabled WITH its reason (BR-SHL-025); it is never the security boundary.
   *
   * ⚠ `useTenantRole` and not `useAccessCell`, for the reason `meteringShared`
   * already writes down for the dispute-clear control: A4's matrix grades a
   * SURFACE, and gating on the Reads cell would offer this to every Billing
   * Clerk, who would then meet a 403.
   */
  const role = useTenantRole(client);
  const mayCosign = role === ROLE_SYSTEM_ADMIN || role === ROLE_EXECUTIVE;

  const [nav, setNav] = useState<WizardNavState>({ step: 1, reached: 1 });
  const [tags, setTags] = useState<BatchTags>({
    source_kind: SOURCE_KIND_CSV,
    source_detail: "",
    read_method: "",
    period_month: "",
    cycle_id: "",
    route_id: "",
  });
  // ── CR-054 task 9 — WHICH SERVICES THIS FILE COVERS ──────────────────────
  // `null` is the untouched state and MEANS every enabled service — the CR's
  // *"defaulting to every enabled service"*. It is deliberately not an array
  // seeded from the query: an array would be `[]` for the moment before
  // `GET /settings/services` answers, and the control would flash "no services"
  // and then fill in, which reads as a screen changing its mind.
  const [serviceTags, setServiceTags] = useState<readonly string[] | null>(null);
  const [text, setText] = useState("");
  const [fileName, setFileName] = useState("reads.csv");
  const [manual, setManual] = useState<ReadManualRow[]>([
    emptyManualRow(),
    emptyManualRow(),
    emptyManualRow(),
  ]);
  const [batch, setBatch] = useState<ReadBatchStaged | null>(null);
  const [validation, setValidation] = useState<ReadBatchValidation | null>(null);
  const [rows, setRows] = useState<readonly ReadImportBatchRow[]>([]);
  const [stageError, setStageError] = useState<string | null>(null);
  const [validateError, setValidateError] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [segment, setSegment] = useState<ReviewSegment>("all");
  const [pending, setPending] = useState<
    Record<number, { disposition: string; reason: string; value: string }>
  >({});
  const [savingRow, setSavingRow] = useState<number | null>(null);
  // BR-MET-051 — what the last reset write did, PER ROW, kept so the clerk who
  // clicked can read the answer rather than a bare count.
  const [demandReset, setDemandReset] = useState<DemandResetReport | null>(null);
  const [demandResetBusy, setDemandResetBusy] = useState(false);
  /** CR-054 task 13 — one flag for both group actions; they share a loop. */
  const [bulkBusy, setBulkBusy] = useState(false);
  /** The shortfall group a clerk pressed *Send someone out* on, or `null`.
   *  Opening the dialog writes NOTHING (`from_flows` rule 1). */
  const [visitGroup, setVisitGroup] = useState<RegisterGroup | null>(null);
  const [certified, setCertified] = useState(false);
  const [result, setResult] = useState<ReadBatchPosted | null>(null);
  /** DEF-MET-8106 — the background post's job record while it runs. */
  const [postJob, setPostJob] = useState<JobRecord | null>(null);
  // ── CR-038 W7 task 3 — THE WRITE MODE, THE STAGE-1 PREMISE ───────────────
  // PO 2026-08-26, verbatim: *"we need insert, insert update, repalce option in
  // step 1 of wirzard"*, and on placement (CR-036 (g)): *"you need at step 1 or
  // 2 itself - this is important decision how you will process the data and
  // upload it"*.
  //
  // ⚠ It defaults to `insert`, matching the server's own default — hard-won law
  // 3, the unsafe option must be the one you type. Choosing a different mode
  // INVALIDATES a staged batch, for the same reason a new file does: the
  // premise is stored ON the batch at staging, so a mode picked after staging
  // would be a control the clerk changed and the server never heard.
  const [writeMode, setWriteMode] = useState<ReadWriteMode>(DEFAULT_READ_WRITE_MODE);
  const [cosignBusy, setCosignBusy] = useState(false);
  const [cosignError, setCosignError] = useState<string | null>(null);
  const [committing, setCommitting] = useState(false);
  const [commitError, setCommitError] = useState<string | null>(null);
  // ── CR-054 task 17 — the rejects file, downloaded from TWO surfaces ───────
  // One piece of state for both, because it is one request against one batch:
  // two flags would let stage 3 spin while the receipt's button looked idle.
  const [rejectsBusy, setRejectsBusy] = useState(false);
  const [rejectsError, setRejectsError] = useState<string | null>(null);

  const cyclesQuery = useQuery({
    queryKey: uploadCyclesKey,
    queryFn: () => getCycles(client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const routesQuery = useQuery({
    queryKey: uploadRoutesKey,
    queryFn: () => getRoutes(client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  // BR-MET-123's tag vocabulary, from the tenant's own reference list. `retry:
  // false` matches the two queries above: a clerk waiting on three retries for
  // a picker is worse than a picker that says it is unavailable.
  const readMethodsQuery = useQuery({
    queryKey: uploadReadMethodsKey,
    queryFn: () => getReadMethods(client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const readMethods = readMethodsQuery.data ?? [];
  // Says "unavailable" only once the answer is IN and empty — never while it
  // is still loading, which would flash an absence that is not one.
  const readMethodsUnavailable = !readMethodsQuery.isPending && readMethods.length === 0;

  // ── CR-054 task 9 — the tenant's ENABLED services ────────────────────────
  // ⚠ `queryKeys.tenantServices`, the SHARED key — not an `upload-reads` key of
  // its own like the three above. This is the same list `ServicesAvailableField`
  // and the settings screen read, and a per-screen key would fetch it a second
  // time and let the two caches disagree about which services a tenant sells.
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const enabledServices = enabledServiceRows(servicesQuery.data);
  // Could not be READ, which is not the same as "this tenant sells nothing" —
  // `data === undefined` after the query settled is the first, an empty enabled
  // subset is the second, and only the first gets a sentence.
  const servicesUnavailable = !servicesQuery.isPending && servicesQuery.data === undefined;

  const stageMutation = useMutation({
    mutationFn: () =>
      stageReadBatch(
        {
          source_kind: tags.source_kind,
          ...(tags.source_detail === "" ? {} : { source_detail: tags.source_detail }),
          // Omitted when unstated: BR-MET-014 makes the tag optional and the
          // server stores NULL, which reads as "not stated". Sending "" would
          // be a method nobody chose.
          ...(tags.read_method === "" ? {} : { read_method: tags.read_method }),
          // CR-038 W7 — ALWAYS sent, unlike the optional tags above. The mode
          // is a premise the commit branches on, not a tag: the server has to
          // hold one of the three at all times, and an omitted key would leave
          // the batch on `insert` while the screen showed `Replace`.
          write_mode: writeMode,
          period_month: tags.period_month,
          ...(tags.cycle_id === "" ? {} : { cycle_id: tags.cycle_id }),
          ...(tags.route_id === "" ? {} : { route_id: tags.route_id }),
          // CR-054 task 9. Omitted for every service and for any subset of two
          // or more — `serviceTagFor` is where that rule lives and why.
          ...(serviceTagFor(serviceTags) === null
            ? {}
            : { service: serviceTagFor(serviceTags) as string }),
          ...(tags.source_kind === SOURCE_KIND_MANUAL
            ? { rows: filledManualRows(manual) }
            : { file_name: fileName, file_content: text }),
        },
        client,
      ),
    onSuccess: (staged) => {
      setBatch(staged);
      setValidation(null);
      setStageError(null);
      // ⚖️ **CR-054 task 11 — THE STAGED ROWS, AT THE STAGE THEY WERE STAGED.**
      // `POST /read-batches` answers the batch and its counts and NO rows (the
      // type says so, and reading `validation.rows` once crashed this screen).
      // The "what is in this file" panel needs the rows, and so does stage 3 —
      // so ONE array is fetched here and both read it. A second group-by over a
      // second fetch is how a panel starts disagreeing with the table under it.
      //
      // It is deliberately NOT awaited inside the mutation: a slow row fetch
      // must not turn a successful stage into a failed one, and the panel is
      // conditioned on `rows.length > 0` so it simply appears when it arrives.
      void getReadBatch(staged.id, client)
        .then((detail) => setRows(detail.rows))
        .catch(() => setRows([]));
    },
    onError: (error) => {
      // A whole-file refusal (size, encoding, no header, an unmapped required
      // column) stages NOTHING — US-MET-007 TC-5/TC-6. The reason is the
      // server's own, rendered rather than summarised.
      setBatch(null);
      setStageError(apiErrorText(error, translate));
    },
  });

  // TWO calls, and the second is not optional: `/validate` runs the engine and
  // answers the batch SUMMARY; the staged rows themselves come back only from
  // `GET /read-batches/{id}`. The screen needs both — the counts for step 3 and
  // the rows for step 4 — so they travel together and can never disagree about
  // which run they describe.
  // ── CR-054 task 6 — THE READING SHEET, SUMMARISED BEFORE IT IS FETCHED ──
  //
  // The button names its own number, so it asks for the COUNT first: same
  // builder, counted, never a second count (hard-won law 5). `enabled` keys it
  // to the cycle and the month a clerk actually chose on stage 1 — with no
  // cycle there is no meter list to build a sheet from, and the control says so
  // rather than firing a request that cannot succeed.
  const sheetPeriod = tags.period_month === "" ? "" : tags.period_month.slice(0, 7);
  const sheetQuery = useQuery({
    queryKey: [...uploadReadingSheetKey, tags.cycle_id, sheetPeriod],
    queryFn: () =>
      getReadingSheetSummary(tags.cycle_id, { period: sheetPeriod || undefined }, client),
    enabled: tags.cycle_id !== "",
    staleTime: 60 * 1000,
    retry: false,
  });
  const [sheetDownloading, setSheetDownloading] = useState(false);

  const validateMutation = useMutation({
    mutationFn: async () => {
      const summary = await validateReadBatch(batch?.id ?? "", client);
      const detail = await getReadBatch(batch?.id ?? "", client);
      return { summary, detail };
    },
    onSuccess: ({ summary, detail }) => {
      setValidation(summary);
      setRows(detail.rows);
      setValidateError(null);
    },
    onError: (error) => setValidateError(apiErrorText(error, translate)),
  });

  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("metering.rbac.readOnly");

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("metering.reads.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }

  function editRow(
    rowNo: number,
    patch: Partial<{ disposition: string; reason: string; value: string }>,
  ): void {
    setPending((current) => {
      const existing = current[rowNo] ?? { disposition: "", reason: "", value: "" };
      return { ...current, [rowNo]: { ...existing, ...patch } };
    });
  }

  async function saveRow(row: ReadImportBatchRow): Promise<void> {
    const draft = pending[row.row_no];
    if (draft === undefined || draft.disposition === "") {
      return;
    }
    setSavingRow(row.row_no);
    try {
      await setReadRowDisposition(
        batch?.id ?? "",
        row.row_no,
        {
          disposition: draft.disposition,
          ...(draft.reason === "" ? {} : { reason: draft.reason }),
          ...(draft.disposition === "override" ? { value: draft.value } : {}),
        },
        client,
      );
      setRowError(null);
      // An override re-runs the engine server-side, so the whole batch is
      // re-read rather than this one row patched into place — a stale sibling
      // row is how a resolved error keeps blocking the commit.
      await validateMutation.mutateAsync();
    } catch (error) {
      setRowError(apiErrorText(error, translate));
    } finally {
      setSavingRow(null);
    }
  }

  // ── BR-MET-051 (CR-038 W4) — the demand reset, noted at the review step ──
  //
  // Both handlers re-read the batch afterwards rather than patching the row
  // into place: the same discipline `saveRow` uses, and for the same reason —
  // a screen holding a stale sibling row is how a resolved state keeps looking
  // unresolved. `bulk` is ONE call rather than a loop of per-row calls (the
  // `acceptAllWarnings` shape) because the SERVER already loops and audits per
  // row; a client loop over 600 demand rows would be 600 round trips for a
  // write the server can make once, and it would give a half-finished answer
  // if the tab closed mid-way.
  async function noteDemandResetAll(): Promise<void> {
    setRowError(null);
    setDemandResetBusy(true);
    try {
      const outcome = await setBatchDemandReset(batch?.id ?? "", { noted: true }, client);
      setDemandReset({ noted: outcome.noted, skipped: outcome.skipped });
      await validateMutation.mutateAsync();
    } catch (error) {
      setRowError(apiErrorText(error, translate));
    } finally {
      setDemandResetBusy(false);
    }
  }

  async function noteDemandResetRow(row: ReadImportBatchRow, noted: boolean): Promise<void> {
    setRowError(null);
    setDemandResetBusy(true);
    try {
      await setReadRowDemandReset(batch?.id ?? "", row.row_no, { noted }, client);
      await validateMutation.mutateAsync();
    } catch (error) {
      setRowError(apiErrorText(error, translate));
    } finally {
      setDemandResetBusy(false);
    }
  }

  /**
   * **CR-054 task 13 — THE TWO BULK ACTIONS ON A SHORTFALL GROUP.**
   *
   * A time-of-use cycle whose file carries one row per meter leaves nine meters
   * each short three windows. Deciding those one row at a time is the work this
   * table exists to remove — and both actions are ordinary dispositions
   * (`dispositionsFor("warning")` offers both), so nothing new can be asked of
   * the server here.
   *
   * ⚠ **A REASON IS RECORDED ON EVERY ROW, INCLUDING THE ONE THAT DOES NOT
   * REQUIRE IT.** BR-MET-015 demands one for `field_visit` and not for
   * `estimate`; a bulk action that stored no reason would be the rule with its
   * evidence removed, which is the argument `acceptAllWarnings` already makes
   * one function down.
   *
   * ⚠ **IT ACTS ONLY ON THE ROWS THE GROUP NAMES.** `registerGroups` collects
   * `rowNos` from SHORT meters only — a complete meter has nothing to estimate
   * and nobody to send out — and a row that already carries a decision is left
   * alone, so pressing twice does not overwrite a clerk's own call.
   *
   * ⚠ **A CLIENT LOOP, NOT ONE CALL, AND THAT IS AN HONEST LIMIT.** There is no
   * bulk-disposition route (`PATCH /read-batches/{id}/rows/{row_no}` is the only
   * writer), unlike BR-MET-051's reset which the server loops server-side. On a
   * shortfall group of a few dozen meters that is a few dozen round trips; on a
   * four-figure one it would not be good enough, and that is REPORTED rather
   * than hidden behind a spinner.
   */
  async function disposeGroup(group: RegisterGroup, disposition: Disposition): Promise<void> {
    const reason = t("metering.upload.registers.bulkReason");
    setRowError(null);
    setBulkBusy(true);
    try {
      for (const rowNo of group.rowNos) {
        const row = rows.find((entry) => entry.row_no === rowNo);
        if (row === undefined || row.disposition !== null) {
          continue;
        }
        await setReadRowDisposition(batch?.id ?? "", rowNo, { disposition, reason }, client);
      }
      await validateMutation.mutateAsync();
    } catch (error) {
      setRowError(apiErrorText(error, translate));
    } finally {
      setBulkBusy(false);
    }
  }

  async function acceptAllWarnings(): Promise<void> {
    const reason = t("metering.upload.review.bulkReason");
    setRowError(null);
    for (const row of rows) {
      if (row.severity !== "warning" || row.disposition !== null) {
        continue;
      }
      try {
        await setReadRowDisposition(
          batch?.id ?? "",
          row.row_no,
          { disposition: "accept_with_flag", reason },
          client,
        );
      } catch (error) {
        setRowError(apiErrorText(error, translate));
        break;
      }
    }
    await validateMutation.mutateAsync();
  }

  /**
   * ⚖️ **CR-054 TASK 15 — WHAT THIS BATCH WILL DO, DERIVED ONCE.**
   *
   * Stage 3's statement, stage 4's figures and the commit button's own number
   * are three renderings of ONE answer, so they are computed once here. Three
   * call sites each doing their own tally is how a banner comes to promise
   * 1,178 above a button that says 1,180 — and this screen has already paid for
   * two derivations of one number (hard-won law 5, and DEF-2441 one wave ago).
   *
   * `validation ?? batch` is the same fallback stage 4's panel uses, so the
   * denominator is the server's own `counts.rows` whichever of the two the
   * screen currently holds.
   */
  const split = postSplit(rows, (validation ?? batch)?.counts ?? null);
  /** CR-054 task 25 — computed here for the same reason: one answer, one place. */
  const tieredOffMonth = tieredRowsOffMonth(rows, tags.period_month);

  /**
   * CR-054 task 17 — the same download from stage 3 and from the receipt.
   *
   * ⚠ **`null` RATHER THAN A DISABLED-LOOKING LIVE BUTTON.** `results.csv`
   * refuses a batch below `validated` (`read_rejects._refuse_not_decided`), and
   * its refusal keys say *"run"* and *"loaded"* where reads says *"batch"* and
   * *"posted"* — the two sentences the backend lane recorded as OWED and could
   * not write into eleven catalogues (`DEF-2733`). Offering nothing to press
   * until the state is right means the clerk never meets somebody else's noun.
   */
  const rejectsDownload =
    batch !== null && (validation !== null || batch.status === "validated" || result !== null)
      ? () => {
          setRejectsBusy(true);
          setRejectsError(null);
          void getReadBatchResults(batch.id, "failures", client)
            .then((body) => saveTextFile(`${batch.batch_no ?? batch.id}-failures.csv`, body))
            .catch((error) => setRejectsError(apiErrorText(error, translate)))
            .finally(() => setRejectsBusy(false));
        }
      : null;

  const steps: WizardStep[] = [
    {
      id: "source",
      label: t("metering.upload.step.source"),
      content: (
        <SourceStep
          tags={tags}
          cycles={cyclesQuery.data ?? []}
          routes={routesQuery.data ?? []}
          readMethods={readMethods}
          readMethodsUnavailable={readMethodsUnavailable}
          services={enabledServices}
          servicesUnavailable={servicesUnavailable}
          serviceTags={serviceTags}
          onServiceTags={setServiceTags}
          onTags={setTags}
          writeMode={writeMode}
          // CR-038 W7 — the premise is stored ON the batch at staging, so a
          // mode changed AFTER staging would be a control the clerk moved and
          // the server never heard. Same invalidation a new file causes, and
          // for the same reason.
          onWriteMode={(next) => {
            setWriteMode(next);
            setBatch(null);
            setValidation(null);
            setRows([]);
          }}
          dateFormat={dateFormat}
          t={translate}
        />
      ),
      // The server requires a reading month; it is asked here so the clerk is
      // not sent to step 2 to be turned back. The `ami_replay` half of this
      // check is gone with the card that could set it (CR-038 W3) — the
      // server's refusal stands, and no control can now compose that payload.
      // The read method is NOT required: BR-MET-014 makes every batch tag
      // optional, and a mandatory picker would force a clerk to state a method
      // they may not know for a file somebody emailed them.
      validate: () => tags.period_month !== "",
    },
    {
      id: "upload",
      label: t("metering.upload.step.upload"),
      content: (
        <UploadStep
          tags={tags}
          text={text}
          fileName={fileName}
          manual={manual}
          staging={stageMutation.isPending}
          stageError={stageError}
          batch={batch}
          rows={rows}
          sheet={{
            cycleCode:
              (cyclesQuery.data ?? []).find((cycle) => cycle.id === tags.cycle_id)?.code ?? null,
            summary: sheetQuery.data ?? null,
            loading: sheetQuery.isPending && tags.cycle_id !== "",
            error: sheetQuery.error === null ? null : apiErrorText(sheetQuery.error, translate),
            downloading: sheetDownloading,
            onDownload: () => {
              const summary = sheetQuery.data;
              if (summary === undefined) return;
              setSheetDownloading(true);
              void getReadingSheet(tags.cycle_id, { period: sheetPeriod || undefined }, client)
                .then((body) => saveTextFile(summary.filename, body))
                .finally(() => setSheetDownloading(false));
            },
          }}
          onText={(nextText, nextName) => {
            setText(nextText);
            setFileName(nextName);
            // A new file invalidates the staged batch: continuing on the
            // PREVIOUS file's preview is how somebody posts the wrong 600 rows.
            setBatch(null);
            setValidation(null);
            setRows([]);
          }}
          onManual={(next) => {
            setManual(next);
            setBatch(null);
            setValidation(null);
            setRows([]);
          }}
          onDownloadStarter={(shape) => {
            void getReadsTemplate(shape, client).then((file) =>
              saveTextFile(file.filename, file.body),
            );
          }}
          onStage={() => stageMutation.mutate()}
          dateFormat={dateFormat}
          t={translate}
        />
      ),
      // BR-MET-012: nothing moves forward until the SERVER has staged. The
      // counts on the next step are the server's, never a client-side guess.
      validate: () => batch !== null,
    },
    {
      // ⚠ **CR-038 W7 — `validate` AND `review` ARE ONE RAIL STAGE NOW, AND
      // THAT IS WHAT "ONE RAIL" COST.**
      //
      // The shared runner has FIVE stages and they are named and numbered in
      // `components/workflow/kinds.ts`: Extract · Transform · Validate · Load ·
      // Result. Reads had five steps too — source · upload · validate · review
      // · post — plus a result panel that REPLACED the wizard, which is six
      // surfaces against the rail's five. Something had to fold, and these two
      // are the pair that were always one question: *does this data check out?*
      // The premises importer's stage 3 already does exactly this — the KPI
      // strip and the rules table AND the reject list with its per-row fixes,
      // in one body — so this is the rail's existing shape, not a new one.
      //
      // Nothing is lost: both panels render, in order, and the forward fence is
      // still the stricter of the two conditions (validated AND no unresolved
      // error rows — BR-MET-015's error half, which BR-MET-129 leaves standing).
      id: "validate",
      label: t("metering.upload.step.validate"),
      content: (
        <>
          <ValidateStep
            validation={validation}
            rows={rows}
            running={validateMutation.isPending}
            error={validateError}
            onRun={() => validateMutation.mutate()}
            bulkBusy={bulkBusy}
            onEstimateGroup={(group) => void disposeGroup(group, "estimate")}
            // ⚠ **THIS USED TO WRITE A ROW DISPOSITION AND NOTHING ELSE, AND
            // THE BUTTON SAID *Send someone out*.** Nobody went out: the whole
            // act was `disposition = field_visit` on the staged rows, and the
            // work order the words promise did not exist. That is hard-won
            // law 2's mirror — a live control over a door that was never built
            // — and it is what the PO's ruling of 2026-09-14 closes.
            //
            // It now OPENS the dialog (`from_flows` rule 1: the raise is
            // OFFERED, never automatic), and the dialog writes the disposition
            // FIRST through `onRecordDecision` before asking Work for the
            // visit, so a raise that fails cannot cost the clerk their decision
            // (`BR-WRK-055`).
            onFieldVisitGroup={setVisitGroup}
            t={translate}
          />
          <ReviewStep
          rows={rows}
          split={split}
          onDownloadRejects={rejectsDownload}
          rejectsBusy={rejectsBusy}
          rejectsError={rejectsError}
          tieredOffMonth={tieredOffMonth}
          periodMonth={tags.period_month}
          segment={segment}
          pending={pending}
          saving={savingRow}
          error={rowError}
          onSegment={setSegment}
          onEdit={editRow}
          onSave={(row) => void saveRow(row)}
          onAcceptAllWarnings={() => void acceptAllWarnings()}
          demandReset={demandReset}
          demandResetBusy={demandResetBusy}
          onDemandResetAll={() => void noteDemandResetAll()}
            onDemandResetRow={(row, noted) => void noteDemandResetRow(row, noted)}
            timeZone={timeZone}
            dateFormat={dateFormat}
            t={translate}
          />
        </>
      ),
      // ⛔ **CR-054 TASK 15 — THE ERROR CLAUSE OF THIS FENCE IS GONE, AND
      // REMOVING IT IS THE POINT OF THE TASK.**
      //
      // It read `validation !== null && unresolvedErrorRows(rows).length === 0`
      // and it was ~~BR-MET-015 / US-MET-008 TC-5~~ — **SUPERSEDED 2026-08-30 BY
      // BR-MET-940**, PO verbatim: *"all or nothing will not work - we accept
      // what is correct and rejct what i not correct"*. `commit_read_batch` no
      // longer raises `errors_need_resolution`; an error gates its own ROW. So
      // this fence was refusing on the screen's behalf a thing the server had
      // stopped refusing, and a clerk with 2 bad rows in 1,180 could not reach
      // stage 4 at all — the ruling shipped in the backend and was unreachable
      // through the only door to it (hard-won law 2, one wave later).
      //
      // ⚠ **THE VALIDATION CLAUSE STAYS, AND IT IS NOT THE SAME KIND OF THING.**
      // "Has the run happened" is a question about whether there is anything to
      // decide about; "are all errors resolved" was a policy. The first is still
      // true — stage 4 prints a composition of verdicts that do not exist before
      // the run, and `results.csv` itself refuses a batch below `validated`.
      validate: () => validation !== null,
    },
    {
      id: "post",
      label: t("metering.upload.step.post"),
      content:
        batch === null ? (
          <p className={WF.STAGE_BLURB}>{t("metering.upload.post.nothingStaged")}</p>
        ) : (
          <PostStep
            batch={validation ?? batch}
            certified={certified}
            writeBlockedReason={writeBlockedReason}
            timeZone={timeZone}
            dateFormat={dateFormat}
            onCertified={setCertified}
            writeMode={writeMode}
            // DEF-770's fix — `Change it` walks to the stage that OWNS the
            // control rather than drawing a second one here.
            onChangeWriteMode={() => setNav({ ...nav, step: 1 })}
            coverage={validation?.cycle_coverage ?? null}
            coverageAbsentReason={validation?.cycle_coverage_absent_reason ?? null}
            mayCosign={mayCosign}
            cosignBusy={cosignBusy}
            cosignError={cosignError}
            onCosign={() => void cosign()}
            split={split}
            postJob={postJob}
            t={translate}
          />
        ),
    },
    {
      // ⚠ **STAGE 5 — THE RECEIPT IS A STAGE NOW, NOT A REPLACEMENT.**
      //
      // This wizard used to render `<ResultPanel>` INSTEAD of the whole frame
      // once the commit returned — the header, the rail and the footer all
      // vanished. Every other importer keeps the rail and lands the operator on
      // its fifth stage, and `WORKFLOW_STAGES[4]` already declares the shape
      // this needs: `advanceKey: null`, so the runner draws no footer and the
      // receipt's own actions live in its body beside what they act on.
      //
      // The practical difference is that a clerk who has just posted 1,180
      // readings can still SEE which run they are looking at.
      id: "result",
      label: t("metering.upload.step.result", { defaultValue: "Result" }),
      content:
        result === null ? (
          <p className={WF.STAGE_BLURB}>{t("metering.upload.post.nothingStaged")}</p>
        ) : (
          <ResultPanel
            result={result}
            onDone={() => navigate(tenantPath(READS_ROUTE))}
            onDownloadRejects={rejectsDownload}
            rejectsBusy={rejectsBusy}
            rejectsError={rejectsError}
            t={translate}
          />
        ),
    },
  ];

  async function commit(): Promise<WizardCommitOutcome> {
    if (batch === null) {
      return { ok: false, reason: t("metering.upload.post.nothingStaged") };
    }
    if (!certified) {
      return { ok: false, reason: t("metering.upload.post.certifyFirst") };
    }
    try {
      const answer = await postReadBatch(batch.id, { certified: true }, client);
      let posted: ReadBatchPosted;
      if (isDeferredPost(answer)) {
        // ⛔ DEF-MET-8106 — the batch is over the server's bar and is posting
        // in a worker. The request answered at once; the job's `N of M` is
        // drawn on this stage while it runs (the button stays disabled —
        // `committing` — for the whole wait), and the receipt is collected
        // from `receipt_url` once the job says it succeeded. A job that FAILED
        // posted nothing (one transaction), and says so in its own words.
        setPostJob({
          id: answer.job_id,
          kind: "metering.read_batch_post",
          status: "queued",
          progress: { done: 0, total: answer.rows_to_post },
          result_link: null,
          error: null,
        });
        const finished = await client.pollJob(answer.job_id, { onProgress: setPostJob });
        if (finished.status !== "succeeded") {
          setPostJob(null);
          return { ok: false, reason: t("metering.upload.post.progress.failed") };
        }
        posted = await getReadBatchPostReceipt(batch.id, client);
        setPostJob(null);
      } else {
        posted = answer;
      }
      setResult(posted);
      // CR-038 W7 — the receipt is stage 5 of the rail, so the commit ADVANCES
      // rather than replacing the frame. `reached` moves with it; the operator
      // can still walk back and read what they posted against.
      setNav({ step: 5, reached: 5 });
      return { ok: true };
    } catch (error) {
      // BR-MET-018's replay block and BR-MET-015's unresolved-errors refusal
      // both land here as the server's own plain-language line. Neither is
      // pre-empted by a disabled button: the server owns both rules.
      setPostJob(null);
      return { ok: false, reason: apiErrorText(error, translate) };
    }
  }

  /**
   * CR-038 W7 task 5 — the co-sign.
   *
   * Its own busy flag rather than a mutation, because it is not part of the
   * flow: it neither advances a stage nor blocks one (`cosign_blocks_post` is
   * `false` — DEF-815), and a failed co-sign must leave the operator exactly
   * where they were with the reason on screen.
   */
  async function cosign(): Promise<void> {
    if (batch === null) return;
    setCosignBusy(true);
    setCosignError(null);
    try {
      const signed = await cosignReadBatch(batch.id, client);
      setBatch(signed);
      // The stage-4 panel reads `validation ?? batch`, so a validated batch
      // must carry the signature too or the control would appear to do
      // nothing — hard-won law 2 in miniature, one render away.
      setValidation((current) =>
        current === null ? null : { ...current, compliance: signed.compliance },
      );
    } catch (error) {
      setCosignError(apiErrorText(error, translate));
    } finally {
      setCosignBusy(false);
    }
  }

  /**
   * ⚠ **THE FOUR ADVANCES, AND WHY STAGE 4 IS DIFFERENT.**
   *
   * `WorkflowRunner` gives a rail and a footer; the flow decides what each
   * primary DOES. Three of these navigate and one WRITES, which is exactly the
   * grammar `WORKFLOW_STAGES` encodes (`Verb →` three times, `Commit load ✓`
   * once, on the only stage marked `writes: true` and rendered in the danger
   * tier — B14 rules 4 and 6).
   *
   * ⚠ **THE SINGLE-FLIGHT GUARD IS CARRIED BY HAND HERE**, because it came free
   * with `WizardFrame` and does not with the runner (BR-SHL-019: ONE
   * transactional commit). `committing` disables the button for the whole
   * round trip, and a failure leaves every entered state intact with the
   * server's own sentence above the footer (A18 §4) rather than resetting the
   * flow — which on a 1,180-row batch would be the worse bug of the two.
   */
  function advanceFrom(step: number): void {
    if (step === 4) {
      if (committing) return;
      setCommitting(true);
      setCommitError(null);
      void commit()
        .then((outcome) => {
          if (!outcome.ok) setCommitError(outcome.reason ?? null);
        })
        .finally(() => setCommitting(false));
      return;
    }
    const next = Math.min(step + 1, steps.length);
    setNav({ step: next, reached: Math.max(nav.reached, next) });
  }

  const currentStep = steps[nav.step - 1];
  const advanceBlocked =
    (currentStep?.validate !== undefined && !currentStep.validate()) ||
    // ⚖️ **THE COMMIT IS DISABLED UNTIL THE TICK (`CR-096-BRC02`, p030).** It
    // was ENABLED with the certification unticked: the click was accepted, the
    // server refused, and the screen answered *"Tick the certification before
    // posting the batch."* — a refusal AFTER the press. The blueprint's own
    // note is the instruction: *"the commit is disabled until the tick, with
    // the reason under it and the consequence above it — so the refusal arrives
    // BEFORE the click rather than after it."* BR-SHL-025 is the rule; the
    // reason travels with it, in `footerNote` below.
    (nav.step === 4 && (!certified || committing || writeBlockedReason !== null));

  return (
    <div className="met-page rd-page">
      {/* ⚠ **CR-038 W7 — THE ONE RAIL. This block used to be a `PageHeader` and
          a `WizardFrame`, and that pair IS the defect the PO reported.**

          PO, 2026-08-26, verbatim: *"These are existing screens - We need to
          follow tailwind wizard that we are using - i believe we are using
          same code for various"*. The belief was verified TRUE: premises,
          units, three assets targets and accounts all mount
          `components/workflow/WorkflowRunner` — one implementation with `kind`
          parameterised, whose own docstring named reads as a future target
          from its first commit. Reads were the exception, on a second frame,
          with a second header, a second rail and a second footer grammar.

          Everything the runner brings is what the PO was asking for and none
          of it is behaviour: `PageHeader` with the kicker and the exit link
          (BR-SHL-044), the numbered `StageBar` with `reached` as its forward
          fence (BR-SHL-018), the stage head, and the footer whose primary
          NAMES ITS DESTINATION and takes the DANGER tier on the one stage that
          writes (B14 rules 4 and 6). The reads PIPELINE is untouched — it is
          still `stage → validate → post` against metering's own services, and
          not one line of it reaches the kit. A kind is copy and a route. */}
      <WorkflowRunner
        kind={WORKFLOW_KINDS.reads}
        stage={nav.step}
        reached={nav.reached}
        onStageChange={(step) => setNav({ ...nav, step })}
        headerAction={null}
        onBack={() => {
          if (nav.step === 1) navigate(tenantPath(READS_ROUTE));
          else setNav({ ...nav, step: nav.step - 1 });
        }}
        onAdvance={() => advanceFrom(nav.step)}
        advanceDisabled={advanceBlocked}
        // ⚖️ **CR-054 TASK 15 — AN IRREVERSIBLE CLICK STATES ITS SCOPE.** The
        // footer primary read *"Commit load ✓"* on every target. Since
        // BR-MET-940 the reads commit files SOME of the rows, so the words no
        // longer describe the act: they are the same on a file that posts all
        // 1,180 and on one that posts 1,178 and hands 2 back. It names its own
        // number now, from the SAME `postSplit()` the banner two stages back
        // stated — one derivation, so the two can never disagree.
        //
        // ⚠ `null` on every other stage, which keeps `WORKFLOW_STAGES`' own
        // `Verb →` grammar exactly as it was (B14 rule 4); only the writing
        // stage's label moves, and only while the split reconciles.
        // ⚖️ **`Post readings` — TWO WORDS, NO COUNT (`CR-096-BRC02`).** The
        // label read *"Commit {{count}} rows ✓"*. CR-054 task 15 put the count
        // there for a good reason — an irreversible click should state its
        // scope — and the blueprint keeps the reason while moving the number:
        // *"A label is ≤ 3 words and carries no sentence; the count was what
        // broke the grammar."* It is the same defect as stage 3's "1 rows will
        // post", one control along. The scope is now the FACT beside the button
        // (`footerAside`), where it can be a sentence and can be pluralised.
        advanceLabel={nav.step === 4 ? translate("metering.upload.post.commit") : null}
        footerAside={
          nav.step === 4 && split.reconciles
            ? translate("metering.upload.post.willPostFact", { count: split.willPost })
            : null
        }
        footerNote={
          nav.step === 4 && !certified ? translate("metering.upload.post.certifyFirst") : null
        }
        // BR-MET-054: Cancel DISCARDS the staged batch — it is not destroyed,
        // it is marked discarded and retained for audit, and it never appears
        // in Reads. Nothing is committed, so there is nothing to undo.
        // ⚠ Drawn ON the footer line beside `← Back`, where the decision is
        // being made; it used to render below the whole frame.
        footerSecondary={
          batch !== null && result === null ? (
            <Button
              variant="ghost"
              onClick={() => {
                void discardReadBatch(batch.id, client).finally(() =>
                  navigate(tenantPath(READS_ROUTE)),
                );
              }}
            >
              {t("metering.upload.discard")}
            </Button>
          ) : null
        }
      >
        {/* A18 §4 — a refused commit keeps every entered state and puts the
            server's own sentence where the operator is looking. `WizardFrame`
            did this for us; on the runner the flow owns it. */}
        {writeBlockedReason !== null && (
          <RefusalStrip role="alert">{writeBlockedReason}</RefusalStrip>
        )}
        {commitError !== null && <RefusalStrip role="alert">{commitError}</RefusalStrip>}
        {currentStep?.content}
      </WorkflowRunner>
      {/* ⚠ **OUTSIDE THE RUNNER, AND THAT IS NOT A DETAIL.** `FormModal` is the
          kit's dialog and owns its own overlay; nesting it inside the stage
          body would put a scrolling wizard behind a control that is supposed to
          be the only thing a clerk can reach. B14 rule 30 was DECLINED, so this
          follows the estimate precedent the PO ruled on the instance instead:
          *"for estimate reads - keep it modal"*. */}
      {visitGroup !== null && (
        <SendSomeoneOutModal
          meters={visitGroup.shortMeters}
          client={client}
          onClose={() => setVisitGroup(null)}
          // `BR-WRK-055` — the clerk's own decision, written FIRST and
          // independently of whether Work can be reached.
          onRecordDecision={() => disposeGroup(visitGroup, "field_visit")}
        />
      )}
    </div>
  );
}

export const uploadCyclesKey = ["cycles", "upload-reads"] as const;
export const uploadReadMethodsKey = ["read-methods", "upload-reads"] as const;
/** CR-054 task 6 — keyed on the cycle and the month, so changing either asks
 *  again rather than naming the previous cycle's row count. */
export const uploadReadingSheetKey = ["reading-sheet", "upload-reads"] as const;
export const uploadRoutesKey = ["routes", "upload-reads"] as const;
export { READS_UPLOAD_ROUTE };

export default UploadReadsWizard;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-007@7c9c034 (EP-MET-03 lead story, sha1 of the epic file; co-stories US-MET-008 · US-MET-009 · US-MET-010 · US-MET-017) + DEF-115
// generated: 2026-08-15 by the DEF-114/115 lane — the first screen over the shipped read-import pipeline · AMENDED 2026-08-27 (DEF-951 — the post receipt printed the uploader's primary key AND a sentence explaining it; `ActorName` renders the person, BR-MET-163)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report
// exceptions: [DEF-MET-8106, 2026-09-30 — SUPERSEDES the old first entry, which read "NO async job and NO progress bar"] a batch over the server's post bar posts as a BE-07 job; stage 4 draws the job's N of M and the receipt is fetched from `receipt_url` when it succeeds · E3 the AMI feed replay card is DRAWN DISABLED with the server's own reason (`metering.read_batch.ami_replay_disabled`, B7 head-end seam) rather than dropped (BR-SHL-025) · E3 NO supervisor co-sign control: OQ-042 closed it as a tenant setting default-ON and no endpoint serves that setting — `read_batch_dict` returns `cosigned_by` and nothing writes it, so the checkbox would change nothing; stated in an arrives-with block · E3 NO "email a batch receipt to Finance": the notifications dispatch is a cross-module service call with no endpoint on this route · E3 NO usage column on a staged row, although the prototype draws one: a staged row is a REGISTER reading and consumption is computed at commit from the meter (`_post_row` writes `unit=asset.unit`), so the staged payload carries neither quantity nor unit — printing one would break CLAUDE.md rule 3, and the committed reading shows its usage WITH its unit on S25 · E3 NO Premise column (the prototype's step-4 table has one) — `read_row_dict` serves no premise, and joining it client-side would be inventing the link · E3 the "Missing records" KPI renders "—" and not 0: BR-MET-049's plan-driven completeness is US-MET-018 and unbuilt, and a 0 would read as "nothing is missing" · E3 the Utility-service batch tag is NOT offered: it is optional server-side (null = all services) and no role-safe endpoint lists a tenant's enabled service codes, so a Billing Clerk would meet an empty control — S25 omits the same filter for the same reason, reported · E3 the plan-aware TOU/demand entry form (US-MET-017) is not built; the manual grid carries an explicit per-row channel, which is what stages a TOU meter today, and the arrives-with block names the story · E4 US-MET-009's "Replace existing" is the `override` disposition rather than a separate control, because it is not a separate write — the commit appends a superseding read and closes the old head · E4 the commit result REPLACES the wizard instead of firing a toast (the S68 precedent): a posting result with its composition is not something to put in a notification that disappears
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
