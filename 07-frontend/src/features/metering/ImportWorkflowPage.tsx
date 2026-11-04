// ── Trace ──────────────────────────────────────────────
// Story:    (none yet — hard-won law 8 is REPORTED here, see the trailer)
//           Change:  CR-023 P5 · DEF-520 (the mount) · CR-023 W2 (stages 4
//           and 5) · DEF-535 (the rules/rejects adapter) · CR-026 (the
//           background stages' progress — the screen half) · CR-036 amd 1 (f)
//           2026-08-26 (the stage-3 strip contradicted the progress bar, and
//           carried no count of the rows that WILL load) · CR-036 amd 2 (g)
//           2026-08-26 (the write mode is a PREMISE and is chosen at stage 1)
//           Screens: WFL-01 (r10 badge; A1 allocates no id — reported)
// Rules:    BR-MET-096 (ONE workflow for premises and units; only Transform
//           differs) · BR-MET-085 (stage 1 stages every row and writes none) ·
//           BR-MET-088 (the MAPS TO list is the target's REAL columns) ·
//           BR-MET-090 (the rules are shown AS THEY RAN; severity and action
//           are TWO columns) · BR-MET-091 (what blocks a load is served, never
//           recomputed on screen) · BR-MET-098 (approval past 5% OR 10 rows;
//           an Owner or an Admin approves) · BR-MET-099 ("replace" deactivates,
//           skips the occupied, never deletes, and states all three numbers
//           before it commits) · BR-MET-100 (an unplanned unit is COUNTED AND
//           FINDABLE) · BR-SHL-025 (a control you may not use is DISABLED with
//           its reason, never hidden) · B14 rule 11 (a consequence preview
//           before a commit) · B14 rule 21 (Tailwind, no new stylesheet) ·
//           BR-MET-102 (a running import CANNOT be cancelled — no cancel
//           control is drawn here, not even a disabled one)
// ───────────────────────────────────────────────────────
// WFL-01 — Extract · Transform · Validate · Load · Result.
//
// ⚠ **THIS FILE EXISTS BECAUSE THE KIT WAS BUILT AND NOTHING RENDERED IT
// (`DEF-520`, critical, PO 2026-08-21).** Twelve components under
// `components/workflow/**`, four live endpoints and 39 backend tests for stages
// 1–3 were all on the branch, and `grep WorkflowRunner` outside its own
// directory returned ZERO callers — so the Imports buttons still opened
// `AddPremisesWizard`, the pre-CR-023 three-step path. The PO deployed, clicked
// Import, and got the old wizard. Hard-won law 2, and `G13` could not see it
// because `G13` asks about PROPS and this was a question about MOUNTS.
//
// ⚠ **ONE PAGE, TWO TARGETS — AND THAT IS THE RULE, NOT A CONVENIENCE
// (`BR-MET-096`, PO 2026-08-21).** Verbatim: *"same process for premises and
// Unit - only at tranform stage we differntate field for premises and Units"*.
// So `target` is a PROP, the server looks the field map and the rule set up
// from it, and there is no `ImportUnitsPage` beside this one. Everything the
// operator sees — the four source cards, the drop zone, the mapping table, the
// validate tiles, the rejects editor, the dry run, the receipt — is the same
// component tree for both. **A second page per target would be two
// implementations of one ruled process, and they would diverge at the first
// defect.**
//
// ⚠ **STAGE 4 COMMITS NOW, AND EVERY FIGURE ON IT IS THE SERVER'S.** This note
// used to say the opposite — the dry run was computed from stage 3's counts and
// `Commit load ✓` was disabled, because `POST /imports/<id>/load` did not exist
// and three of its rules were unruled. All three were ruled on 2026-08-21
// (`BR-MET-098` the approval bars, `BR-MET-099` what *replace* does, `BR-MET-097`
// the address), and both routes are mounted.
//
// **NOTHING ON THIS STAGE IS COMPUTED ON SCREEN.** `POST /imports/<id>/dry-run`
// is re-posted whenever the operator lands on stage 4 or changes the write
// mode, and the panel prints what comes back — B15 §16 TC-16: *"a dry run that
// lies is worse than none"*. The server computes it with the SAME function the
// commit acts on (`_load_locked` calls `dry_run` itself), so the sentence read
// and the rows touched cannot disagree; a screen re-deriving *"will create"*
// from a row count would report a number the loader never uses (`DEF-380`).
//
// ⚠ **STAGE 5 DRAWS THE `/load` RESPONSE AND DOES NOT RE-READ IT.** The
// receipt this screen shows is the one the commit answered with — the same
// payload `GET /imports/<id>/receipt` serves since the `DEF-541` fix made
// every door answer for a loaded run. `Roll back this run` is LIVE for the
// same reason (`DEF-552` — it stayed disabled for a day after the engine
// could honour it, claiming "not switched on yet" over a working endpoint):
// two-step danger confirm, and the receipt redraws from the rollback's own
// answer, which states what was reversed and what was kept occupied.
//
// ⚠ **CR-026 — THREE OF THESE FIVE STAGES CAN ANSWER 202, AND A 202 IS NOT A
// RESULT.** Over `import_runs.ASYNC_ROW_BAR` (5,000 rows) transform, validate
// and load are handed to a worker and answer immediately with the run, a job id
// and `deferred: true` — and with NONE of the stage's own output: no rules, no
// rejects, no new counts, no receipt. So each `onSuccess` below asks that one
// question first and, when the answer is yes, draws NOTHING and starts polling
// `GET /imports/{id}` instead. Reading a 202 as a result is the failure this
// screen is most able to produce: it would print a reconcile strip of zeros, or
// "No rules ran on this file", over a run the worker has not begun.
//
// ⚠ **AND A SMALL FILE MUST BE UNTOUCHED.** `run_dict` serves `progress: null`
// for every synchronous run and the deferral flag is simply absent, so on a
// three-row import `deferredStage` never leaves `null`, no poll is issued and
// `ImportProgressPanel` renders `null`. That is the property most at risk here
// and it is pinned by a test.
//
// ⚠ **THERE IS NO CANCEL CONTROL ON THIS SCREEN (`BR-MET-102`, PO 2026-08-22,
// verbatim: *"No"*), AND NOT A DISABLED ONE EITHER.** `BR-SHL-025` exists for a
// control that cannot act YET; a cancel that is ruled never to exist is not a
// gap to explain, and greying one out would invite an operator to wait for it
// to light up. What the progress panel offers instead is the door the ruling
// names: the run finishes, and the receipt's rollback deactivates everything it
// loaded. The accepted cost is written into the rule — a 100,000-row mistake is
// a 100,000-row rollback, not a stop.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { UNEXPECTED_ERROR_KEY, api, diagnosticOf, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import i18n from "@/i18n";
import {
  confirmImportChangeover,
  dryRunImport,
  extractImport,
  fixImportRow,
  getImportColumns,
  getImportResultsCsv,
  getImportReceipt,
  getImportRun,
  getImportSample,
  getImportTemplateNotes,
  getLookupEntries,
  isImportStageFinished,
  loadImport,
  rollbackImport,
  saveImportMapping,
  transformImport,
  validateImport,
} from "@/api/endpoints";
import type {
  ImportColumnsResult,
  ImportDryRun,
  ImportExtractResult,
  ImportMappingSpec,
  ImportTemplateNotes,
  ImportProgress,
  ImportReceiptResult,
  ImportRejectedRow,
  ImportRuleResult,
  ImportTarget,
  ImportTransformRequest,
  ImportOwnerAmbiguity,
  ImportUnplannedPlan,
  ImportValidateResult,
  ImportWriteMode,
} from "@/api/endpoints";
import { Button, ButtonLink } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import {
  CheckboxField,
  DatePickerField,
  SelectField,
  TextField,
} from "@/components/FormModal";
import { DEFAULT_PAGE_SIZE, type PageSize } from "@/components/tableTypes";
import { Note } from "@/components/TextBits";
import {
  DropZone,
  DryRunPanel,
  MappingTable,
  Receipt,
  ReconcileStrip,
  RejectList,
  RollbackNotice,
  RowHandlingOptions,
  RuleResultsTable,
  rowHandlingDefaultsFor,
  SourceCards,
  WORKFLOW_KINDS,
  workflowSourcesFor,
  writeModeIsRefused,
  writeModeRefusals,
  WorkflowRunner,
  WriteModeField,
  rollbackControlIsOffered,
  writeModeOptions,
} from "@/components/workflow";
import type {
  LoadOptions,
  MappingRow,
  ReceivedFile,
  ReceiptData,
  RejectedRow,
  RowHandling,
  RuleResult,
  TargetColumn,
} from "@/components/workflow";
import * as WF from "@/components/workflow/workflowKit";
import { refusalOf, RefusalNotice } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  IMPORT_POLL_INTERVAL_MS,
  ImportProgressPanel,
  type DeferredStage,
} from "./importProgress";

import { useRegional } from "./meteringShared";
// `CR-139-BRC07` `P5.8` — the focused input behind the Scan paper card, and the
// one door onto the remittance grammar. A COMPONENT rather than a block inside
// this 3,100-line page (B14 rule 43).
import { ScanInput } from "@/components/workflow/ScanInput";
import type { ScannedRemittance } from "@/api/remittanceEndpoints";

/** The source card every target switches on. Two of the other three state
 *  their reason; the fifth is `SOURCE_SCAN` below and belongs to payments. */
const SOURCE_FILE = "file";

/**
 * ⛔ **`CR-139-BRC07` `P5.8` — THE FIFTH CARD, SWITCHED ON.** Blueprint p068 ②:
 * *"A barcode scanner is a keyboard — it types what it reads and presses Enter.
 * No driver, no integration, no pairing. So Scan paper is a source card and a
 * focused input, and everything after it is the runner: the same mapping, the
 * same rules, the same rejects, the same dry run, the same receipt."*
 *
 * ⚠ **AND *EVERYTHING AFTER IT IS THE RUNNER* IS IMPLEMENTED LITERALLY.** The
 * scanned rows are turned into a CSV `File` and handed to the SAME
 * `chosenFile` state a browsed file lands in, so stages 2 to 5 cannot tell the
 * two apart and no stage below this one learned a new word. The alternative — a
 * second extract path keyed on the source — is the *two answers to one
 * question* shape this phase keeps filing.
 */
const SOURCE_SCAN = "scan";

// ⚠⚠ **THE CARD IS STILL HELD AND THIS BRANCH IS THEREFORE UNREACHABLE TODAY —
// DELIBERATELY, AND THE REASON IS MEASURED.** `P5.10` shipped the remittance
// LINE onto the stub and its BARS are still owed: `remittance.bars()` is
// specified in full and `documents.py` calls `compose_for_invoice` and never
// `bars()`. A wedge scanner reads BARS. Switching the card on today would put a
// focused field in front of a clerk holding a sack of bills a scanner reads
// NOTHING from — hard-won law 2's mirror pointing the other way, a live control
// over a door that opens onto nothing, and exactly what
// `scanSourceIsReachableAndHeld.dom.test.tsx` was written to refuse.
//
// **The wiring lands with the component on purpose.** The day the bars are
// drawn, releasing this is ONE line in `kinds.ts` (`available: true`) plus one
// catalogue retire — not a build — and `paymentsSourceAndWriteMode.test.tsx`
// keeps the input from rotting unseen in the meantime by mounting it directly.

/**
 * The scanned bills as the payments importer's own CSV.
 *
 * ⚠ **THE HEADER NAMES ARE THE ONES THE PAYMENTS TARGET ALREADY MAPS**, so
 * stage 2 proposes the same mapping it proposes for a lockbox file and the
 * clerk sees one screen rather than two. A scan carries no tender, no posting
 * date and no confirmation — those are stage 2's options exactly as they are
 * for a file — so the CSV states only what the barcode said.
 */
function scannedCsv(rows: readonly ScannedRemittance[]): File {
  const header = "account_no,invoice_no,amount";
  const body = rows.map((row) => `${row.account_no},${row.invoice_no},${row.amount}`);
  return new File([[header, ...body].join("\n")], "scanned-bills.csv", { type: "text/csv" });
}

/**
 * The two column KINDS whose `help` already has a hand-placed sentence on
 * stage 2 (`DEF-771` the plan column, `DEF-1077` the unit column). Every other
 * column that declares `help` is drawn by `helpColumns` — see the note there.
 *
 * ⚠ **A SET, SO THAT ADDING A HAND-PLACED SENTENCE IS ONE LINE AND FORGETTING
 * TO IS A VISIBLE DUPLICATE** rather than a silent one: a kind left out of
 * this set renders twice, on screen, where a person sees it.
 */
const HELP_DRAWN_BY_KIND: ReadonlySet<string> = new Set(["plan_ref", "unit_ref"]);

/**
 * **WHAT A COUNT LOOKS LIKE BEFORE IT HAS BEEN COUNTED — `CR-036` (f).**
 *
 * ⚠ An em-dash and NOT a `0`. A zero is a measurement; this is the absence of
 * one, and the two must not print the same glyph (BR-MET-085, and hard-won law
 * 1 in figure form). It is punctuation rather than a word, so it needs no
 * catalogue entry and reads the same in all eleven locales; the sentence that
 * says *why* there is no figure is beneath the strip, in words, translated.
 */
const NOT_YET = "—";

/**
 * `BR-MET-098`'s bars are **DATA, NOT SCREEN CONSTANTS** — and they used to be
 * two `const`s here.
 *
 * The rule makes both figures the TENANT's to set, and `DEF-435` is what a
 * threshold typed into a screen and enforced by nobody costs. So the
 * percentage, the row count, this run's reject count and its batch size all
 * arrive on `dry-run`'s `approval` block and this file prints what it is given.
 * The one thing kept here is the WORDING, because the server does not localise.
 *
 * ⚠ **TWO BARS, NOT ONE, AND THE SECOND ONE IS WHY.** A percentage alone
 * punishes small files, and the people running small corrective imports run
 * them most often: 5% of a 20-row batch is **1 row**, and of an 8-row batch
 * **0.4** — so every correction with a single bad row would stop for approval,
 * which is the rule staff learn to route around. A count alone has the mirror
 * flaw: **200 rejects in a 5,000-row migration is 4%** and would pass unseen.
 * The approver is an Owner or an Admin — the same two roles as `BR-RAT-091`'s
 * 10% rate-change bar, and the server refuses a Billing Clerk who ticks the box.
 */
const APPROVAL_BECAUSE_KEY: Record<"percent" | "rows", string> = {
  percent: "metering.import.approvalBecausePercent",
  rows: "metering.import.approvalBecauseRows",
};

/**
 * `BR-MET-090` keeps SEVERITY and ACTION in two columns, and the ACTION half
 * arrives as a CODE (`reject_row`, `flag_only`, …) rather than as a sentence —
 * `import_rules`' own trailer says why: a tier-3 rule is tenant prose with no
 * catalogue key, so the server holds no display strings for this table at all.
 * The words are therefore the screen's, here, where they can be translated.
 *
 * ⚠ An unknown code renders as ITSELF rather than as a blank cell. A rule set
 * is configurable by design (`BR-MET-090` tier 3), so a code this map has not
 * met is a thing that will happen — and an empty ACTION column is the failure
 * `DEF-535` already shipped once.
 */
const RULE_ACTION_KEY: Record<string, string> = {
  reject_row: "workflow.rules.action.reject_row",
  skip_on_load: "workflow.rules.action.skip_on_load",
  flag_only: "workflow.rules.action.flag_only",
  default_to: "workflow.rules.action.default_to",
};

/**
 * `FileReader` gives us `data:<mime>;base64,<payload>` and the server wants the
 * payload. Split on the FIRST comma only: base64 never contains one, but a
 * filename-derived mime type can.
 */
function base64Of(dataUrl: string): string {
  const comma = dataUrl.indexOf(",");
  return comma === -1 ? dataUrl : dataUrl.slice(comma + 1);
}

function readAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("file_unreadable"));
    reader.onload = () => resolve(base64Of(String(reader.result ?? "")));
    reader.readAsDataURL(file);
  });
}

/**
 * The drop zone reads `rows` and a formatted size from the SERVER's answer, so
 * before stage 1 has run there is nothing truthful to show but the name. Rows
 * stay at 0 and the hash is empty until the server has actually counted and
 * hashed — the UI never guesses either (BR-MET-085: the hash on screen is the
 * server's, computed over the bytes it received, not over the bytes we sent).
 */
function receivedFileOf(
  chosen: File | null,
  run: ImportExtractResult | null,
  sizeLabel: (bytes: number) => string,
): ReceivedFile | null {
  if (run !== null) {
    return {
      name: run.file_name ?? "",
      rows: run.counts.in ?? 0,
      size_label: sizeLabel(run.file_bytes ?? 0),
      sha256: run.file_hash ?? "",
    };
  }
  if (chosen === null) return null;
  return { name: chosen.name, rows: 0, size_label: sizeLabel(chosen.size), sha256: "" };
}

/** Stage 2's rows: one per header the file actually had (BR-MET-088). */
function mappingRowsOf(
  run: ImportExtractResult | null,
  chosen: Record<string, string | null>,
  labelOf: (target: string) => string,
): MappingRow[] {
  if (run === null) return [];
  return run.headers.map((header) => {
    const target = chosen[header] ?? null;
    return {
      source_column: header,
      // `CR-168` · `DEF-WRK-9588` / `DEF-521` — stage 1's answer now carries
      // the first non-empty cell per header, so an operator can tell `part_no`
      // from `name` at a glance (image 39). Empty — never invented — when the
      // server has none (a re-read run, or an identity column).
      sample_value: run.samples?.[header] ?? "",
      target_column: target,
      status: target === null ? "unmapped" : target === "__ignore__" ? "ignored" : "matched",
      transform_label: target === null || target === "__ignore__" ? null : labelOf(target),
    };
  });
}

/**
 * The kit's `RuleResult`, built from what the server actually sends.
 *
 * ⚠ **THIS FUNCTION EXISTS BECAUSE OF `DEF-535`.** `contract.ts` declares
 * `action_label`, `import_runs.rule_results` sends `action` + `action_value`,
 * and the ACTION column of the shipped Validate stage has rendered `undefined`
 * since the day it mounted. `tsc` could not see it: the endpoint type declared
 * the kit's name, so both halves agreed with each other and neither agreed with
 * Python. The wording is the client's job either way — see `RULE_ACTION_KEY`.
 */
function ruleRowsOf(
  rules: readonly ImportRuleResult[],
  t: (key: string, params?: Record<string, unknown>) => string,
): RuleResult[] {
  return rules.map((rule) => ({
    code: rule.code,
    sentence: rule.sentence,
    severity: rule.severity,
    action_label:
      rule.action_value === null || rule.action_value === ""
        ? t(RULE_ACTION_KEY[rule.action] ?? rule.action)
        : `${t(RULE_ACTION_KEY[rule.action] ?? rule.action)} · ${rule.action_value}`,
    hits: rule.hits,
    available: rule.available,
    unavailable_reason: rule.unavailable_reason,
  }));
}

/** `DEF-535` again: three of these four names were wrong for a whole release. */
function rejectRowsOf(rejects: readonly ImportRejectedRow[]): RejectedRow[] {
  return rejects.map((reject) => ({
    row_number: reject.row_no,
    key: reject.source_key ?? "",
    problem: reject.problem,
    suggested_fix: reject.fix_hint ?? "",
    // D8: the row's source cells travel to the inline "fix here" editor.
    raw: reject.raw,
    // `BR-MET-1032`: which of them the server is showing as `••••6789`. Built
    // is not wired (hard-won law 2) — a prop the page does not pass is a
    // feature that does not exist, and here the missing prop would silently
    // hand the editor a mask to append digits to.
    masked: reject.masked,
  }));
}

/**
 * Stage 5's six fields, worded here because the server sends DATES and the kit
 * wants SENTENCES.
 *
 * ⚠ `finished_label` and `duration_label` are required by `ReceiptProps` and
 * are rendered by NOTHING — `Receipt.tsx` draws source, hash, run by, session,
 * mapping and rollback, and never those two. They are filled from the run's own
 * timestamps rather than from `""` so that the day the component draws them it
 * draws something true; the dead pair is REPORTED, not papered over.
 *
 * ⚠ **THE ROLLBACK EXPIRY IS WORDED FROM THE SERVER'S DATE AND IS NEVER "30
 * DAYS" TYPED HERE.** `import_runs.ROLLBACK_DAYS` owns the window; if this file
 * held the number, this file would be making the promise.
 */
/**
 * A dry-run figure that has not arrived yet.
 *
 * ⚠ **AN ABSENT COUNT IS NOT A ZERO.** Printing `0` beside *"Existing records
 * updated"* while the rehearsal is still in flight tells the operator nothing
 * will be overwritten — which is a claim, and is the shape the old
 * `notComputed` string was written for. The em-dash the rest of the product
 * uses for an absent value is a code constant, not copy (`ABSENT` in the kit),
 * but this cell wants a SENTENCE because it is transient rather than empty.
 */
function figureOf(value: number | undefined, pending = "…"): string {
  return value === undefined ? pending : String(value);
}

function receiptDataOf(
  result: ImportReceiptResult,
  t: (key: string, params?: Record<string, unknown>) => string,
  formatWhen: (iso: string) => string,
): ReceiptData {
  const point = result.receipt.rollback_point;
  return {
    run_id: result.receipt.run_id,
    finished_label:
      result.receipt.finished_at === null ? "" : formatWhen(result.receipt.finished_at),
    duration_label:
      result.started_at === null || result.receipt.finished_at === null
        ? ""
        : t("metering.import.durationSeconds", {
            seconds: Math.max(
              0,
              Math.round(
                (Date.parse(result.receipt.finished_at) - Date.parse(result.started_at)) / 1000,
              ),
            ),
          }),
    source_label: result.receipt.source_label,
    file_sha256: result.receipt.file_sha256,
    file_hash_verified: result.receipt.file_hash_verified,
    run_by: result.receipt.run_by,
    session_and_ip: result.receipt.session_and_ip,
    mapping_used: result.receipt.mapping_used,
    rollback_point:
      point === null
        ? null
        : {
            id: point.id,
            expiry_label:
              point.expires_at === null
                ? t("metering.import.rollbackNoExpiry")
                : t("metering.import.rollbackExpires", { date: formatWhen(point.expires_at) }),
          },
  };
}

/** Browser-side save of the server's sample file (CR-025) — the same shape
 *  `UploadReadsWizard` uses for the published reads template (BR-MET-032). */
/**
 * **`DEF-771` CLAUSE 3 — 9,881 FLAGGED ROWS IS NOT A REVIEW ANYBODY CAN
 * PERFORM.**
 *
 * `BR-MET-100` is unchanged and stays the PO's option B: a row whose plan
 * cannot be resolved LOADS, unplanned and flagged, because that is right for
 * one typo. What was missing is the sentence a person can act on — HOW MANY
 * rows, WHICH plan they all named, and WHY it could not be used. One line per
 * DISTINCT plan, worst first, so a 9,881-row mistake reads as one line.
 *
 * Every word after the count is the SERVER's: `detail` is the same sentence
 * flagged on each of those rows and `fix_hint` is the act that fixes it, so
 * the receipt and the row can never say two different things about one plan.
 */
function UnplannedPlans({
  entries,
  title,
}: {
  entries: ImportUnplannedPlan[];
  title: string;
}) {
  const { t } = useTranslation();
  if (entries.length === 0) return null;
  return (
    <div
      className="bg-[color-mix(in_srgb,var(--color-accent)_8%,transparent)] p-3 text-sm leading-body"
      data-workflow="unplanned-plans"
      role="note"
    >
      <p className="font-heading font-bold">{title}</p>
      <ul className="mt-1 list-disc pl-5">
        {entries.map((entry) => (
          <li key={entry.asked_for} data-workflow-unplanned-plan={entry.asked_for}>
            {t("metering.import.unplannedPlanEntry", {
              rows: entry.rows,
              plan: entry.asked_for,
              defaultValue: "{{rows}} row(s) named “{{plan}}”.",
            })}{" "}
            {entry.detail} {entry.fix_hint}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * **CR-055 — THE AMBIGUOUS OWNER NAMES, ONE LINE PER SPELLING.**
 *
 * PO ruling 2026-08-31: an owner name matching two or more parties LOADS the
 * premises with no owner instead of rejecting the row. The receipt count is the
 * only thing that stops that being a quiet way to lose revenue — and a count
 * alone cannot be reviewed, which is `DEF-771` clause 3's lesson applied to a
 * different column. 400 addresses carrying one misspelt landlord is ONE
 * decision, so this is one line per distinct spelling, worst first.
 *
 * ⚠ **IT NAMES THE PARTIES AND OFFERS NO BUTTON, ON PURPOSE.** The import may
 * not pick between two parties (PO decision 3, which CR-055 did not reverse),
 * and a one-click "use this one" here would be that decision wearing a
 * different hat. The act belongs on the Owner matching surface, where a person
 * is looking at one address.
 */
function OwnerAmbiguities({ entries }: { entries: ImportOwnerAmbiguity[] }) {
  const { t } = useTranslation();
  if (entries.length === 0) return null;
  return (
    <div
      className="bg-[color-mix(in_srgb,var(--color-accent)_8%,transparent)] p-3 text-sm leading-body"
      data-workflow="owner-ambiguities"
      role="note"
    >
      <p className="font-heading font-bold">{t("metering.import.ownerAmbiguousTitle")}</p>
      <ul className="mt-1 list-disc pl-5">
        {entries.map((entry) => (
          <li key={entry.asked_for} data-workflow-owner-ambiguity={entry.asked_for}>
            {t("metering.import.ownerAmbiguousEntry", {
              rows: entry.rows,
              owner: entry.asked_for,
              candidates: entry.candidates.join(", "),
            })}
          </li>
        ))}
      </ul>
    </div>
  );
}

function saveTextFile(name: string, body: string): void {
  const url = URL.createObjectURL(new Blob([body], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

export interface ImportWorkflowPageProps {
  /** BR-MET-096: the ONLY thing that differs between the two workflows. */
  target: ImportTarget;
  client?: ApiClient;
}

/**
 * ⛔ **`DEF-MET-10784` (PO 2026-10-31 P12 = A) — THE SUPPORT LINE IS FOR A
 * FAILURE WITH NO SENTENCE, NOT FOR EVERY REFUSAL.** DEF-964 wired
 * `diagnosticOf` under the strip because the PO's stage-4 commit failed behind
 * *"Something went wrong."* and nothing else. It rendered for EVERY failure, so
 * a refused re-upload read *"File already loaded as IMP-0012."* and then
 * *"HTTP 409 · BIZ-IDEMPOTENT · ref 5F2B-9C1D"* under it — the raw code the PO
 * ruled off this screen in plain words (*"never 'HTTP 409 · BIZ-IDEMPOTENT'"*).
 *
 * So the line is drawn only when the strip above could NOT say what happened:
 * not an `ApiError` at all (nothing answered), a 5xx, the generic
 * `api.error.unexpected`, or a key no catalogue holds. A named refusal — any
 * 4xx whose sentence exists, on any of the seven import targets — says its
 * sentence and nothing else. The reference still reaches support: it is on the
 * strip's `data-br-ref`, in the audit row and in the server log.
 */
export function supportLineOf(failure: unknown, exists: (key: string) => boolean): string | null {
  if (failure === null || failure === undefined) {
    return null;
  }
  if (
    isApiError(failure) &&
    failure.status < 500 &&
    failure.messageKey !== UNEXPECTED_ERROR_KEY &&
    exists(failure.messageKey)
  ) {
    return null;
  }
  return diagnosticOf(failure);
}

/**
 * Plan U9 (PO 2026-09-30) — the catalogue key for a served asset-sheet group.
 * The plan tables name two groups differently on the devices sheet (*Device
 * details*, *Dates and testing*), so the sheet picks the words; the served
 * group code is the same on all three.
 */
export function assetGroupKey(group: string, target: string): string {
  const devices = target === "assets_devices";
  if (group === "details") {
    return devices ? "assets.upload.group.details_device" : "assets.upload.group.details_meter";
  }
  if (group === "dates" && devices) {
    return "assets.upload.group.dates_device";
  }
  return `assets.upload.group.${group}`;
}

export function ImportWorkflowPage({ target, client = api }: ImportWorkflowPageProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fileInput = useRef<HTMLInputElement | null>(null);
  // DEF-SHL-3964 — the tenant's own zone and format, read ONCE at the top of
  // this (very long) component and used at the three places below that used to
  // name `SEED_TIME_ZONE` / `SEED_DATE_FORMAT` directly. Hoisted because
  // `useRegional` reads a context: two of the three sites are inside
  // conditional JSX branches.
  const { timeZone: tenantTimeZone, dateFormat: tenantDateFormat } = useRegional({});

  const kind = WORKFLOW_KINDS[target];
  const [stage, setStage] = useState(1);
  const [reached, setReached] = useState(1);
  const [failure, setFailure] = useState<unknown>(null);

  // Stage 1 state.
  const [sourceId, setSourceId] = useState(SOURCE_FILE);
  const [chosenFile, setChosenFile] = useState<File | null>(null);
  // `P5.8` — what the scanner has typed so far. Empty for every other source
  // and for every other target, which is why it costs nothing to hold here.
  const [scanned, setScanned] = useState<readonly ScannedRemittance[]>([]);
  const [batchLabel, setBatchLabel] = useState("");
  const [mappingId, setMappingId] = useState("");
  const [run, setRun] = useState<ImportExtractResult | null>(null);

  // Stage 2 state.
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  // PO 2026-10-30 Q7 = A — *"Save mapping as template" switched on with a
  // name; applied automatically when a file's headers match*. Saved when the
  // operator confirms the mapping (stage 2 → 3), with the map as they see it.
  const [saveTemplate, setSaveTemplate] = useState(false);
  const [templateName, setTemplateName] = useState("");
  const [savedTemplate, setSavedTemplate] = useState<string | null>(null);
  const templateNameMissing = saveTemplate && templateName.trim() === "";
  // DEF-PAY-10772 — payments starts with Drop exact duplicate rows OFF.
  const [rowHandling, setRowHandling] = useState<RowHandling>(() => rowHandlingDefaultsFor(target));
  /**
   * ⛔ **`DEF-751` — THE SPEC IS KEPT, NOT ONLY THE COUNTS.** Stage 2's answer
   * carries `mapping_spec.date_format`, `.column_problems` and
   * `.empty_columns` (`BR-MET-117` (3), `CR-036` (i)) and this state used to
   * throw all three away one line after they arrived. `null` until the server
   * has answered — never `{}`, because "no problems found" and "not asked yet"
   * are different screens (`BR-MET-085`).
   */
  const [transformed, setTransformed] = useState<{
    counts: Record<string, number>;
    spec: ImportMappingSpec | null;
  } | null>(null);
  // ⛔ DEF-626 — the stage-2 options this kind DECLARES. The runner holds them
  // as opaque strings: it never learns what `cutover_on` means, only that the
  // accounts kind declares one and that it is required once an opening-balance
  // column is mapped. BR-MET-096, kept.
  const [options, setOptions] = useState<Record<string, string>>({});

  // Stage 3 state.
  const [checked, setChecked] = useState<ImportValidateResult | null>(null);

  // Stage 4 state.
  //
  // ⚠ **`P1.18` — THE INITIAL MODE IS THE FIRST ONE THIS TARGET DOES NOT
  // REFUSE, NEVER A HARDCODED `"insert"`.** It happens to BE `insert` for every
  // target today, which is exactly why a constant here would have looked right
  // for as long as it took some future target to refuse the other one — and
  // then a clerk would post a value the server rejects without ever having
  // touched a control. `writeModeIsRefused` asks the same rule the cards draw.
  const [writeMode, setWriteMode] = useState<ImportWriteMode>(() =>
    writeModeIsRefused(kind.id, "insert") ? "upsert" : "insert",
  );
  const [loadOptions, setLoadOptions] = useState<LoadOptions>({
    create_rollback_point: true,
    notify_on_finish: false,
  });
  /**
   * `BR-MET-098`'s second approval, as an EXPLICIT ACT.
   *
   * ⚠ **THE COMMIT MUST ASK, NOT ASSUME.** Sending `approved: true` with every
   * load — or on the retry after a refusal — would satisfy the server and
   * defeat the rule: the whole point of a second approval is that a person
   * reads the numbers and says yes. So the tick is its own control, it starts
   * off on every run, and it RESETS whenever the write mode changes, because a
   * different mode is a different set of consequences to approve.
   */
  const [approved, setApproved] = useState(false);

  /**
   * **CR-026 — which stage is running in a worker right now, or `null`.**
   *
   * ⚠ **`null` IS THE WHOLE SMALL-FILE GUARANTEE.** A run at or under
   * `import_runs.ASYNC_ROW_BAR` (5,000 rows) answers 200 with its results and
   * this never leaves `null`, so the poll never starts, the panel never
   * renders, and a three-row import is byte-for-byte the screen it was before
   * CR-026. The engine decides — the client reads `deferred` off the answer
   * and never forms its own opinion about how big is big.
   */
  const [deferredStage, setDeferredStage] = useState<DeferredStage | null>(null);
  /** The worker's own last words when a stage died — see `liveProgress`. */
  const [stageFailure, setStageFailure] = useState<ImportProgress | null>(null);

  // Stage 5 state — the `/load` answer, drawn as-is (see the header note).
  const [receipt, setReceipt] = useState<ImportReceiptResult | null>(null);
  // DEF-552 — the rollback is armed by one click and fired by a second, the
  // same two-step the danger tier gives every destructive commit (B14 rule 6).
  const [rollbackArmed, setRollbackArmed] = useState(false);
  /**
   * ⛔ **CR-047 (a) — THE DATE THAT RELEASES A HELD OPENING BATCH.**
   *
   * ⚠ **IT STARTS EMPTY AND IS NEVER SEEDED FROM `changeover_provisional`.**
   * The provisional date is *today − 90 days* — a number this product chose so
   * that a migration's books are recognisable while somebody finds the real
   * date. Pre-filling the box with it would turn a placeholder nobody chose
   * into a date somebody appears to have typed, and one click would weld it
   * into an immutable journal entry (hard rule 4). `BR-TEN-043` is the rule and
   * this is the field it was written about.
   */
  const [changeoverOn, setChangeoverOn] = useState("");
  /**
   * ⛔ **CR-047 (14) — WHICH PAGE OF THE RECEIPT'S FAILURE LIST IS OPEN.**
   *
   * A separate pair from stage 3's, on purpose: the two lists are DIFFERENT
   * LISTS. Stage 3's holds the rows the checks refused; the receipt's holds
   * those PLUS every row the write itself refused (PO ruling 2026-08-29 — a
   * failed row is reported and skipped and the next row is read), so its total
   * is larger and its page one is the load's own answer rather than validate's.
   * Sharing the state would page one list with the other's offset.
   */
  const [resultPage, setResultPage] = useState(1);
  const [resultPer, setResultPer] = useState<PageSize>(DEFAULT_PAGE_SIZE);

  const columns = useQuery<ImportColumnsResult>({
    queryKey: ["import-columns", run?.id],
    enabled: run !== null,
    queryFn: () => getImportColumns(String(run?.id), client),
  });

  /**
   * ⛔ **`DEF-1077` — WHAT THE TEMPLATE'S COLUMNS TAKE, ON THE STAGE THAT
   * HANDS THE TEMPLATE OVER.**
   *
   * PO verbatim, 2026-08-27: *"when we add assets we have to tie them to
   * units; and in CSV file that we download there is not unit ID or unit name
   * that we can provide - what about this"*.
   *
   * The same server sentences `columns` above already feeds to stage 2 — but
   * stage 2 is one stage too late. By then the file is written. This asks the
   * SAMPLE'S OWN URL for them (`Accept: application/json`), so the notes
   * cannot describe a template other than the one the button downloads, and it
   * needs no run: at stage 1 there is not one yet, which is exactly why the
   * stage-2 query could never have served this.
   */
  /** Q7 — this target's saved templates, for stage 1's list. Recognition is
   *  automatic (an exact header match picks one); the list lets an operator
   *  name one outright. Tenancy serves every target's rows, so they are
   *  filtered here by the target this run loads into. */
  const savedTemplates = useQuery({
    queryKey: ["import-mapping-templates", target],
    enabled: stage === 1,
    queryFn: () => getLookupEntries("import_mappings", { per: 100 }, client),
  });
  const templateOptions = (savedTemplates.data?.results ?? [])
    .filter((entry) => entry.active && entry.target === target)
    .map((entry) => ({ value: entry.id, label: entry.name }));

  const templateNotes = useQuery<ImportTemplateNotes>({
    queryKey: ["import-template-notes", target],
    enabled: stage === 1,
    queryFn: () => getImportTemplateNotes(target, client),
  });

  /**
   * The rehearsal. **A POST that writes nothing**, re-issued when the operator
   * lands on stage 4 and again on every change of write mode — the mode is in
   * the query key, so picking `Replace the batch` fetches the three numbers
   * `BR-MET-099` requires before that mode may commit.
   *
   * `enabled` waits for stage 4 AND for a validated run: a dry run of an
   * unvalidated run is refused server-side, and a refusal on arrival would put
   * a red notice over a stage the operator has not done anything on yet.
   */
  const dryRun = useQuery<ImportDryRun>({
    queryKey: ["import-dry-run", run?.id, writeMode],
    enabled: stage >= 4 && run !== null && checked !== null,
    queryFn: () => dryRunImport(String(run?.id), writeMode, client),
  });

  /**
   * **THE POLL — `GET /imports/{id}` every two seconds while a stage is in a
   * worker, and NOT ONE REQUEST MORE.**
   *
   * `enabled` is the deferral flag, so a synchronous run issues zero polls.
   * `refetchInterval` reads the SERVER's own `state` and stops itself the
   * moment the gauge says `done` or `failed` — a terminal state ends the
   * polling rather than a poll count or a timeout, because the run is the
   * thing that finished and only it knows.
   *
   * ⚠ It is keyed on the STAGE as well as the run, so `transform → validate`
   * starts a fresh query rather than reusing a cache entry whose `progress`
   * still says the previous stage is `done` — which would complete the new
   * stage instantly, on the old stage's word.
   */
  const polled = useQuery<ImportValidateResult>({
    queryKey: ["import-run", run?.id, deferredStage],
    enabled: deferredStage !== null && run !== null,
    retry: false,
    refetchInterval: (query) =>
      isImportStageFinished(query.state.data?.progress) ? false : IMPORT_POLL_INTERVAL_MS,
    queryFn: () => getImportRun(String(run?.id), client),
  });

  /**
   * **THE REJECT PAGE — `GET /imports/{id}?reject_offset=&reject_limit=`
   * (`DEF-766`).**
   *
   * The run payload carries ONE WINDOW of the reject list, because every reject
   * rides with its full `raw` source cells (the inline editor edits exactly
   * those) and the poll above asks for that payload every two seconds: on the
   * PO's own all-reject run the unbounded list was **4.28 MB every two seconds**
   * to draw a fifty-row table. So the server sends the page the table draws,
   * and the TOTAL beside it — the operator reads *"9,881 rejected"*, never
   * *"50"*.
   *
   * ⚠ **PAGE ONE COSTS NO REQUEST.** `checked` already holds the server's
   * default window, so this query is `enabled` only once the operator asks for
   * a page that is not it. A screen that re-fetched page one would have turned a
   * payload fix into an extra round trip on every run.
   *
   * ⚠ **THE TOTAL IS IN THE KEY.** A fix re-runs stages 2–3 and the reject list
   * shrinks by one; keying on it means the open page is re-read against the new
   * list rather than left showing rows that are no longer rejected.
   */
  const [rejectPage, setRejectPage] = useState(1);
  const [rejectPer, setRejectPer] = useState<PageSize>(DEFAULT_PAGE_SIZE);
  const rejectFirstPage = rejectPage === 1 && rejectPer === DEFAULT_PAGE_SIZE;
  const rejectTotal = checked?.rejects_window?.total ?? checked?.rejects.length ?? 0;
  const rejectWindow = useQuery<ImportValidateResult>({
    queryKey: ["import-rejects", run?.id, rejectPage, rejectPer, rejectTotal],
    enabled: run !== null && checked !== null && !rejectFirstPage,
    queryFn: () =>
      getImportRun(String(run?.id), client, {
        offset: (rejectPage - 1) * rejectPer,
        limit: rejectPer,
      }),
  });
  const rejectRows: ImportRejectedRow[] = rejectFirstPage
    ? (checked?.rejects ?? [])
    : (rejectWindow.data?.rejects ?? []);

  /**
   * ⛔ **CR-047 (14) — THE SAME WINDOW, FOR THE RECEIPT'S OWN LIST.**
   *
   * PO ruling 2026-08-29, verbatim: *"if it is fail - you display on screen
   * shich record failed and why (dont write to dB) and continue to uplaod next
   * record"*. A row that fails at the WRITE no longer stops the run, so the
   * receipt has a failure list of its own — the checks' rejects PLUS the
   * write's — and it is a longer list than stage 3's, on a run that has
   * finished.
   *
   * ⚠ **PAGE ONE COSTS NO REQUEST**, exactly as at stage 3: the `/load`
   * answer already carries the server's default window. Anything else is a
   * read of the same `GET /imports/{id}` surface with an offset.
   *
   * ⚠ **AND THE TOTAL IS IN THE KEY** for the same reason it is at stage 3:
   * confirming a changeover redraws the receipt, and a page held open against
   * a list that has changed underneath is rows that are no longer true.
   */
  const resultTotal = receipt?.rejects_window?.total ?? receipt?.rejects.length ?? 0;
  const resultFirstPage = resultPage === 1 && resultPer === DEFAULT_PAGE_SIZE;
  const resultWindow = useQuery<ImportValidateResult>({
    queryKey: ["import-result-rejects", run?.id, resultPage, resultPer, resultTotal],
    enabled: stage >= 5 && run !== null && receipt !== null && !resultFirstPage,
    queryFn: () =>
      getImportRun(String(run?.id), client, {
        offset: (resultPage - 1) * resultPer,
        limit: resultPer,
      }),
  });
  const resultRejectRows: ImportRejectedRow[] = resultFirstPage
    ? (receipt?.rejects ?? [])
    : (resultWindow.data?.rejects ?? []);

  /**
   * ⛔ **CR-047 (15) — THE TWO FILES, FETCHED AND HANDED OVER.**
   *
   * PO ruling 2026-08-29: *"at the end we need 2 CsV file 1 for success record
   * and other for failed records"*. The bodies are the SERVER's; this only
   * names the file. `saveTextFile` is the same browser-side save the stage-1
   * sample already uses, so there is one download mechanism on this screen and
   * not two.
   */
  function downloadResults(kind: "successes" | "failures"): void {
    void getImportResultsCsv(String(run?.id), kind, client)
      .then((body) => {
        setFailure(null);
        // The run's own number, so two downloads from two runs do not land in
        // a Downloads folder as `results.csv` and `results (1).csv`.
        const stamp = receipt?.receipt.run_no ?? String(run?.id);
        saveTextFile(`${stamp}_${kind}.csv`, body);
      })
      .catch(setFailure);
  }

  /**
   * A deferred LOAD finishes with a RECEIPT, and the poll surface does not
   * serve one: `read_run` calls `run_dict(with_rules=True)`, which carries the
   * rules and the rejects and no `receipt` block. `GET /imports/{id}/receipt`
   * is the route that builds it (and answers for a loaded run since DEF-541),
   * so the worker finishing is followed by exactly one more read.
   */
  const fetchReceipt = useMutation({
    mutationFn: () => getImportReceipt(String(run?.id), client),
    onSuccess: (result) => {
      setReceipt(result);
      setFailure(null);
      setStage(5);
      setReached(5);
    },
    onError: setFailure,
  });

  const targets: TargetColumn[] = useMemo(
    () =>
      (columns.data?.columns ?? []).map((column) => ({
        id: column.target,
        label: column.label,
        required: column.required,
        // Plan U9 — the asset sheets' six groups, as headings in the picker.
        ...(column.group ? { group: t(assetGroupKey(column.group, target)) } : {}),
      })),
    [columns.data, target, t],
  );

  const labelOf = useMemo(() => {
    const byId = new Map(targets.map((column) => [column.id, column.label]));
    return (id: string) => byId.get(id) ?? id;
  }, [targets]);

  /**
   * **`DEF-751` / `BR-MET-117` (3) — WHAT THE SERVER ALREADY KNEW AND TOLD
   * NOBODY.**
   *
   * Three fields, served since BR-MET-117's backend half landed, with ZERO
   * frontend consumers between them: the format dates are read as, the mapped
   * columns that could not be read, and the mapped columns that are EMPTY. The
   * last of those is the whole of `CR-036` (i) — 9,881 premises loaded with no
   * services, `Matched` on the column, no error anywhere, and the run knew.
   *
   * ⚠ **TWO SOURCES, ON PURPOSE, BECAUSE THEY ANSWER AT DIFFERENT TIMES.**
   * `GET /imports/{id}/columns` carries `date_format` per DATE column and is
   * available at stage 2, BEFORE a 9,881-row file is transformed — which is
   * the only moment the operator can still change the file or the setting.
   * `mapping_spec` exists only once stage 2 has RUN, so the per-column verdicts
   * are stage 3's. Neither is derived from the other and neither is guessed.
   */
  const dateColumns = useMemo(
    () => (columns.data?.columns ?? []).filter((column) => column.kind === "date"),
    [columns.data],
  );
  /** The tenant's declared format, off the first DATE column that carries one.
   *  Every date column carries the SAME value (`_with_date_format` stamps one
   *  tenant-level setting onto each), so this is a read, not a choice. `null`
   *  is the tenant that has declared none — the state in which every dated row
   *  is refused, and so the one that most needs saying out loud. */
  const declaredDateFormat = dateColumns.reduce<string | null>(
    (found, column) => found ?? column.date_format ?? null,
    null,
  );
  /** Which of the operator's OWN columns are being read as dates, right now,
   *  as they map. Named rather than counted: "read as dates" is only useful
   *  when it says which. */
  const mappedDateColumns = Object.entries(mapping)
    .filter(([, target]) => dateColumns.some((column) => column.target === target))
    .map(([source, target]) => `${source} → ${labelOf(String(target))}`);

  /**
   * **`DEF-771` — WHAT THE `Plan` COLUMN ACTUALLY TAKES, SAID AT STAGE 2.**
   *
   * The column is labelled *Plan* and its aliases are `plan`, `rate plan` and
   * `tariff`; the matcher behind it held plan CODES only. A utility's
   * 9,881-row file said `city customer plan` in every cell, mapped clean,
   * showed `Matched`, and loaded 9,881 units with no plan. The matcher takes
   * a code OR a name now — and this is `BR-MET-117` (3)'s posture applied to
   * the same screen: **say it where the file can still be changed**, not on a
   * receipt one stage after the writing.
   *
   * The sentence is the SERVER's (`UNITS_FIELD_OVERRIDES["rate_plan"].help`),
   * never invented here — a screen that wrote its own copy about a matcher it
   * cannot see is how the two came apart in the first place.
   */
  const planColumn = (columns.data?.columns ?? []).find(
    (column) => column.kind === "plan_ref" && (column.help ?? "") !== "",
  );
  const mappedPlanColumns = Object.entries(mapping)
    .filter(([, target]) => target === planColumn?.target)
    .map(([source, target]) => `${source} → ${labelOf(String(target))}`);

  /**
   * ⛔ **`DEF-1077` — WHAT THE `Unit` COLUMN TAKES, SAID WHERE THE FILE CAN
   * STILL BE CHANGED.** PO verbatim, 2026-08-27: *"when we add assets we have
   * to tie them to units; and in CSV file that we download there is not unit
   * ID or unit name that we can provide - what about this"*. The column IS
   * there and that is the whole complaint — it was headed `unit_ref`, and the
   * three shapes it accepts (the unit number, a `premises · label` pair, or a
   * bare label unique in the tenant) lived only in two Python docstrings.
   *
   * The words are the SERVER'S, exactly as `planColumn` above: a screen that
   * writes its own copy about a matcher it cannot see is how `DEF-771`'s two
   * halves came apart. This is that same fix on a second column, and the
   * `Note` below is the same one.
   */
  const unitColumn = (columns.data?.columns ?? []).find(
    (column) => column.kind === "unit_ref" && (column.help ?? "") !== "",
  );

  /**
   * ⛔ **`CR-046` E2 — EVERY OTHER COLUMN THAT EXPLAINS ITSELF, DRAWN BECAUSE
   * IT EXPLAINS ITSELF AND NOT BECAUSE THIS FILE KNOWS ITS NAME.**
   *
   * The two `find`s above name a `kind` each, which was right for one column
   * and does not survive a THIRD. On 2026-08-27 the meters template's
   * identifier column changed meaning — *"an EXISTING number, if this row
   * updates a meter already in SMARTBillHub — blank for a new one"* — and
   * `_asset_number_column` shipped a `help` sentence saying exactly that. It
   * was served on `GET /imports/{id}/columns`, typed in
   * `ImportTargetColumn.help`, and **rendered nowhere**, because `asset_no`
   * is a plain `text` column and neither `find` was looking for it. An
   * operator on the one screen that can still change the file read nothing at
   * all about the column whose meaning had just moved.
   *
   * ⚠ **SO THE RULE HERE IS THE SERVER'S, NOT THIS FILE'S**: a column that
   * declares `help` gets its sentence drawn. That is what makes waves C2–C4
   * free — the moment `premise_no`, `unit_no` and `account_no` declare theirs,
   * three more screens start telling the truth with no frontend change, and
   * `DEF-771`'s own warning (*"a screen that wrote its own copy about a
   * matcher it cannot see is how the two came apart"*) is honoured by
   * construction rather than by diligence.
   *
   * ⚠ **THE LABEL IS DRAWN WITH IT, AND THAT IS THE OTHER HALF OF E2.** The
   * header is what the operator has to recognise in their own file, and the
   * `MAPS TO` picker only shows it for a column something is already mapped
   * to — which the identifier column, blank by design, normally is not.
   */
  const helpColumns = (columns.data?.columns ?? []).filter(
    (column) =>
      (column.help ?? "") !== "" && !HELP_DRAWN_BY_KIND.has(column.kind),
  );

  const mappingSpec = transformed?.spec ?? null;
  /** ⚠ `?? []` and NOT `?? null`: an older run's spec predates BR-MET-117 and
   *  carries neither key, and "the server did not say" must draw the same
   *  nothing as "the server said none" — the alternative is an empty red panel
   *  on every historical run. */
  const emptyColumns = mappingSpec?.empty_columns ?? [];
  const columnProblems = mappingSpec?.column_problems ?? [];

  const sizeLabel = (bytes: number) => `${Math.max(1, Math.round(bytes / 1024))} KB`;

  /**
   * A server timestamp, in the tenant's own zone.
   *
   * ⚠ **DEF-SHL-3964** — this said *"THE SEED DEFAULTS, DELIBERATELY AND NOT
   * SILENTLY"* and reasoned that nothing passes this runner regional props, so
   * a prop would be dead UI. Both facts were correct and the result was every
   * import timestamp rendered in UTC and MM/DD/YYYY on a tenant that had chosen
   * neither. The shell publishes the tenant's pair, so no prop is needed.
   */
  const formatWhen = (iso: string) =>
    formatDate(iso, tenantTimeZone, tenantDateFormat, true);

  /**
   * Which declared options are REQUIRED for the mapping as it stands, and
   * which of those are still empty.
   *
   * ⚠ The question asked here is *"is any of these targets mapped?"* — about
   * the mapping table the runner already holds. It is never *"what is an
   * `ob_*` column?"*, which is the question BR-MET-096 forbids this file from
   * being able to answer.
   */
  const mappedTargets = useMemo(
    () => new Set(Object.values(mapping).filter((value): value is string => value !== null)),
    [mapping],
  );
  // ⚠ Memoised because `kind.options ?? []` builds a NEW array on every render
  // when a kind declares none, which would re-run the memo below every time.
  const optionFields = useMemo(() => kind.options ?? [], [kind]);
  const requiredOptionIds = useMemo(
    () =>
      new Set(
        optionFields
          .filter((field) => (field.requiredWhenAnyMapped ?? []).some((t) => mappedTargets.has(t)))
          .map((field) => field.id),
      ),
    [optionFields, mappedTargets],
  );
  const missingOptions = optionFields.filter(
    (field) => requiredOptionIds.has(field.id) && (options[field.id] ?? "").trim() === "",
  );

  const extract = useMutation({
    mutationFn: async () => {
      if (chosenFile === null) throw new Error("no_file");
      return extractImport(
        {
          target,
          source_kind: "file",
          file_name: chosenFile.name,
          // ⚠ `content_b64` — DEF-526. The server reads this name and no other.
          content_b64: await readAsBase64(chosenFile),
          mapping_id: mappingId === "" ? null : mappingId,
          batch_label: batchLabel === "" ? null : batchLabel,
          // ⛔ **`CR-046` wave B — the step-1 choice now REACHES the server at
          // step 1.** `WriteModeField` has been on this screen since CR-036
          // (g) and its value travelled no further than React state until the
          // dry run. Stage 3 needs it to apply the PO's ruling (*"in case of
          // insert - reject it"*), and a field the server declares that no
          // caller passes is dead UI — hard-won law 2, which G13 enforces.
          write_mode: writeMode,
        },
        client,
      );
    },
    onSuccess: (result) => {
      setRun(result);
      // The server's own guess seeds the table; the operator overrides it in
      // stage 2 and the override is what gets sent back.
      setMapping({ ...result.detected_mapping });
      setFailure(null);
      setStage(2);
      setReached((previous) => Math.max(previous, 2));
    },
    onError: setFailure,
  });

  const transform = useMutation({
    mutationFn: async () => {
      const payload: ImportTransformRequest = {
        // ⚠ `mapping` — DEF-531. The server reads this key and no other.
        mapping: Object.fromEntries(
          Object.entries(mapping)
            .filter(([, value]) => value !== null)
            .map(([source, value]) => [source, { target: String(value) }]),
        ),
        // ⛔ **`DEF-522` IS CLOSED HERE AND ON THE SERVER, AND THERE IS NO
        // TRANSLATION LEFT TO DO.** The kit used to declare the middle option
        // as `keep_latest_on_duplicate_key` while `ROW_HANDLING_KEYS` has
        // always called it `keep_latest_on_key`, and stage 2 read its options
        // with `bool(payload.get(key))` — so the kit's spelling was not
        // refused, it was read as FALSE, and an operator who ticked *"keep the
        // latest row when a key appears twice"* got the FIRST row kept. This
        // site carried a hand-written mapping between the two spellings, which
        // fixed THIS caller and left every other one silently wrong.
        // **`contract.ts` now spells all three the way the wire does**, so the
        // three names below are the SERVER's, read off `ROW_HANDLING_KEYS`,
        // and there is no translation left to get wrong. The server REFUSES an
        // unrecognised key by name now, so the next divergence is a 400 rather
        // than a wrong answer nobody can see.
        //
        // ⚠ **SPELLED OUT RATHER THAN SPREAD, and `tsc` is why**: `RowHandling`
        // is an interface with no index signature, so it is not assignable to
        // the wire's `Record<string, boolean>`. Widening the interface to take
        // one would let ANY key through this call untyped, which is the exact
        // tolerance that made DEF-522 invisible on the server.
        row_handling: {
          drop_exact_duplicates: rowHandling.drop_exact_duplicates,
          keep_latest_on_key: rowHandling.keep_latest_on_key,
          skip_rows_missing_required: rowHandling.skip_rows_missing_required,
        },
      };
      // ⛔ DEF-626. Only non-empty values travel: sending `{cutover_on: ""}`
      // would put an empty string where the server expects a date, and its
      // refusal would then be about the FORMAT rather than the absence.
      const declared = Object.fromEntries(
        optionFields
          .map((field) => [field.id, (options[field.id] ?? "").trim()] as const)
          .filter(([, value]) => value !== ""),
      );
      if (Object.keys(declared).length > 0) {
        payload.options = declared;
      }
      const result = await transformImport(String(run?.id), payload, client);
      // Q7 — saved only once the mapping it records has been accepted, so a
      // map the server refused is never kept as a template.
      if (saveTemplate && run !== null) {
        const saved = await saveImportMapping(
          String(run.id),
          { name: templateName.trim(), mapping },
          client,
        );
        setSavedTemplate(saved.name);
        setSaveTemplate(false);
      }
      return result;
    },
    onSuccess: (result) => {
      setFailure(null);
      // ⚠ **CR-026 — A 202 CARRIES NO RESULTS, SO NOTHING MAY BE DRAWN FROM
      // IT.** `_defer` answers `run_dict(run)` plus the job: the counts in it
      // are stage 1's, not stage 2's, and `duplicates_dropped` is still 0
      // because the work has not happened. Reading them here would print a
      // reconcile strip of zeros over a file the worker is still mapping. So
      // the screen stays where it is, the panel takes over, and the poll's
      // payload — not this one — is what advances the run.
      if (result.deferred === true) {
        setStageFailure(null);
        setDeferredStage("transform");
        return;
      }
      setTransformed({ counts: result.counts, spec: result.mapping_spec ?? null });
      setStage(3);
      setReached((previous) => Math.max(previous, 3));
      // Validate runs on ARRIVAL, so stage 3 is never an empty promise.
      validate.mutate();
    },
    onError: setFailure,
  });

  const validate = useMutation({
    // ⛔ **`CR-046` wave B — the mode travels WITH the judging.** Stage 3
    // rejects a row naming a record already on file under `insert` and merely
    // notes it under `insert & update` (PO 2026-08-27), so a stage 3 that did
    // not know the mode would judge every run as though no mode were chosen.
    mutationFn: () => validateImport(String(run?.id), writeMode, client),
    onSuccess: (result) => {
      // ⚠ **STAGE 3 SHOWS ITS OWN RESULTS AND DOES NOT JUMP (`DEF-530`).**
      // This used to `setStage(4)` here, which meant an operator ARRIVED at
      // Validate with nothing computed, and the moment it computed they were
      // on Load — so *"Test it before you trust it"* rendered four zero tiles
      // and *"No rules ran on this file"* over a run the server had already
      // checked (3 rows, 3 warnings, 8 rules). The screen contradicted the
      // database, and only a browser walkthrough could see it.
      setFailure(null);
      // CR-026 — the 202 carries no `rules` and no `rejects` at all, so
      // `setChecked` on it would put "No rules ran on this file" over a run
      // the worker has not started. The panel says what is happening instead.
      if (result.deferred === true) {
        setStageFailure(null);
        setDeferredStage("validate");
        return;
      }
      setChecked(result);
      setReached((previous) => Math.max(previous, 3));
    },
    onError: setFailure,
  });

  /**
   * D8 (CR-028 debt sweep) — stage 3's inline correction: PATCH one reject
   * row's raw cells, then RE-RUN stages 2–3. The server sends the run back to
   * `extracted` (a fixed cell invalidates its mapping and its judgment —
   * `fix_row`'s own law), so the stale verdict is dropped and transform
   * re-runs with the mapping already on screen; its onSuccess chains validate,
   * landing the operator back here over FRESH results. Never a commit over a
   * stale verdict.
   */
  const fixRow = useMutation({
    mutationFn: (input: { rowNo: number; values: Record<string, string | null> }) =>
      fixImportRow(String(run?.id), input.rowNo, input.values, client),
    onSuccess: () => {
      setFailure(null);
      setChecked(null);
      // DEF-766 — the list the operator was paging through no longer exists:
      // the fixed row leaves it and every row after it moves up one. Page one
      // of the NEW list is the only page it is honest to be on.
      setRejectPage(1);
      transform.mutate();
    },
    onError: setFailure,
  });

  /**
   * Stage 4 · LOAD — **the only call this screen makes that writes.**
   *
   * ⚠ It sends `approved` only when the server ASKED for it. A screen that
   * always sent `true` would turn `BR-MET-098` off from the client side.
   */
  const commit = useMutation({
    mutationFn: () =>
      loadImport(
        String(run?.id),
        {
          write_mode: writeMode,
          create_rollback_point: loadOptions.create_rollback_point,
          ...(dryRun.data?.approval.required === true ? { approved } : {}),
        },
        client,
      ),
    onSuccess: (result) => {
      setFailure(null);
      // ⚠ CR-026 — a deferred load has WRITTEN NOTHING YET, so there is no
      // receipt to draw and stage 5 must not open. `_defer` answers before the
      // worker has touched a row; the receipt is fetched when the gauge says
      // the load is done. The three answers the engine still gives on THIS
      // call — an already-loaded run's same receipt, an unvalidated run's
      // refusal, and BR-MET-098's approval bar — all arrive as a 200 or as an
      // error, never as a 202, so this branch cannot swallow one.
      if (result.deferred === true) {
        setStageFailure(null);
        setDeferredStage("load");
        return;
      }
      setReceipt(result);
      setStage(5);
      setReached(5);
    },
    onError: setFailure,
  });

  /**
   * ⛔ **CR-047 (a) — `POST /imports/{id}/confirm-changeover`, THE ONLY DOOR
   * OUT OF THE HOLD** (PO ruling 2026-08-27).
   *
   * ⚠ **THE ROUTE HAD BEEN COMPLETE FOR TWO DAYS WITH NO CALL SITE ANYWHERE.**
   * The receipt drew `opening_held` as a flagged figure — *"412 opening
   * balances waiting for your changeover date"* — and offered nothing to do
   * about it, so the only screen that names the problem was also the screen
   * that could not solve it. Hard-won law 2: built is not wired.
   *
   * ⚠ **NO CLIENT-SIDE DATE VALIDATION, DELIBERATELY.** The server refuses a
   * FUTURE date by name and this screen surfaces that refusal through the same
   * `RefusalNotice` every other failure here uses. A second validator in the
   * browser would have to re-implement *"today"* in the TENANT's zone, which
   * this runner does not have (`meteringShared`'s stated posture), and the two
   * would disagree on exactly the days that matter.
   *
   * The answer is the SAME receipt shape `/load` and `/rollback` return, so
   * stage 5 redraws from it with no special case.
   */
  const confirmChangeover = useMutation({
    mutationFn: () => confirmImportChangeover(String(run?.id), changeoverOn, client),
    onSuccess: (result) => {
      setReceipt(result);
      setFailure(null);
      // The box is emptied because the thing it was for has happened. Leaving
      // the date in a field that is about to disappear is harmless; leaving it
      // in one that a second run could reuse is not.
      setChangeoverOn("");
    },
    onError: setFailure,
  });

  // DEF-552 — LIVE, not disabled-with-a-stale-reason: the endpoint has
  // answered since the DEF-541 fix. The receipt redraws from the rollback's
  // own answer (it DEACTIVATES, never deletes, and says what it kept).
  const rollback = useMutation({
    mutationFn: () => rollbackImport(String(run?.id), client),
    onSuccess: (result) => {
      setReceipt(result);
      setFailure(null);
      setRollbackArmed(false);
    },
    onError: setFailure,
  });

  /**
   * **WHAT HAPPENS WHEN THE WORKER FINISHES.** One effect, driven by the
   * SERVER's `state` and by nothing this screen decides.
   *
   * ⚠ **THE STAGE IS CHECKED AS WELL AS THE STATE.** A gauge row is ONE ROW
   * PER RUN, overwritten in place (`import_run_progress`'s `ON CONFLICT
   * (run_id)`), so the instant a stage finishes the row still reads
   * `stage: "transform", state: "done"` until the next stage's first write.
   * Advancing on `state === "done"` alone would therefore complete
   * *validate* the moment it was enqueued, on *transform*'s word — and the
   * screen would jump to stage 4 with nothing checked, which is DEF-530
   * wearing a different hat.
   *
   * ⚠ **AND A FAILED STAGE STOPS EVERYTHING.** `import_progress.failed`
   * carries the worker's own message; it is shown, the poll stops (a terminal
   * state ends the interval), and the run does not advance. A worker that died
   * is not a stage that passed.
   */
  const polledProgress = polled.data?.progress ?? null;
  useEffect(() => {
    if (deferredStage === null || polledProgress === null) return;
    if (polledProgress.stage !== deferredStage) return;
    if (polledProgress.state === "failed") {
      setStageFailure(polledProgress);
      setDeferredStage(null);
      return;
    }
    if (polledProgress.state !== "done") return;
    const finished = polled.data;
    if (finished === undefined) return;
    setDeferredStage(null);
    if (deferredStage === "transform") {
      setTransformed({ counts: finished.counts, spec: finished.mapping_spec ?? null });
      setStage(3);
      setReached((previous) => Math.max(previous, 3));
      validate.mutate();
    } else if (deferredStage === "validate") {
      setChecked(finished);
      setReached((previous) => Math.max(previous, 3));
    } else {
      fetchReceipt.mutate();
    }
    // `polled.data` and the two mutations are stable enough for this to fire
    // once per finished stage: `deferredStage` is cleared on the same tick, so
    // the guard above refuses every later render of the same payload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [polledProgress, deferredStage]);

  const busy = extract.isPending || transform.isPending || validate.isPending;

  /**
   * **THE GAUGE TO DRAW — and `null` for every synchronous run.**
   *
   * ⚠ **A FAILED STAGE HAS TO OUTLIVE ITS OWN POLL.** Clearing `deferredStage`
   * changes the query key, so `polled.data` is gone on the very next render —
   * the worker's message would flash and vanish. So the failure is COPIED into
   * state when it is read, and the panel keeps drawing it until the operator
   * starts another stage. A screen that loses the only sentence explaining why
   * nothing happened is worse than one that never had it.
   */
  const liveProgress = deferredStage === null ? stageFailure : polledProgress;

  /** Handed over, and the worker has not filed its first report yet. There is
   *  no figure to draw and none is invented (BR-MET-085). */
  const awaitingFirstReport = deferredStage !== null && polledProgress === null;

  // CR-028: the exit is the KIND's declared home, not a hardcoded pair — the
  // three assets targets exit to the Assets page (their `returnTo`), premises
  // and units keep the exact routes they always had (their kinds declare the
  // same constants).
  const exitTo = tenantPath(kind.returnTo);

  function advance() {
    if (stage === 1) extract.mutate();
    else if (stage === 2) transform.mutate();
    else if (stage === 3) {
      // The results are already on screen (validate ran on arrival), so this
      // only moves the operator on — it does not re-run the rules.
      setStage(4);
      setReached((previous) => Math.max(previous, 4));
    } else if (stage === 4) commit.mutate();
    // Stage 5 has no footer — r10's own shape, and there is nothing after it.
  }

  /** A different mode is a different set of consequences to approve. */
  function chooseWriteMode(next: string) {
    setWriteMode(next as ImportWriteMode);
    setApproved(false);
  }

  /**
   * **THE TWO WRITE MODES, DECLARED ONCE AND OFFERED ONCE — `CR-042` /
   * `BR-MET-210`, on top of `CR-036` AMENDMENT 2 (g).**
   *
   * PO, 2026-08-26, verbatim, answering where the re-import option lives after
   * being told it is on stage 4: *"you need at step 1 or 2 itself - this is
   * important decision how you will process the data and upload it"*.
   *
   * ⚠ **THE MODE IS A PREMISE, NOT A CONFIRMATION.** It decides what the FILE
   * MEANS — a first load, a correction, or a replacement — and stages 2 and 3
   * were already reporting against an assumption nobody had asked the operator
   * to make. The PO's own screenshots prove it: stage 3 said *"This premise ID
   * is already on file — **the write mode decides what happens to it**"* on a
   * screen that still refused to show the write mode.
   *
   * So the choice is made at **stage 1**, beside the file it is a statement
   * about, and NOT at stage 2: stage 2 is about which column is which, and a
   * mapping question and a "what does this file mean" question are different
   * kinds of question. Stage 1 already carries the other three facts about the
   * file — what it loads into, what it is called, how it is encoded — and this
   * is the fourth.
   *
   * ⚠ **AND IT IS STILL CHANGEABLE AT THE STAGE-4 DRY RUN — BUT NOT OFFERED
   * THERE (DEF-770).** A premise that cannot be revised before committing is a
   * trap, not a decision; a SECOND control for it invites the question of which
   * one wins. So stage 4 STATES the mode and its `Change it` walks back here.
   * `writeMode` is in the dry run's query key, so changing it re-runs the
   * rehearsal exactly as it did before.
   *
   * ⛔ **`replace` IS WITHDRAWN — CR-042, PO 2026-08-27**: *"in all imports - we
   * need 2 option on step 1 insert, insert & update; replace option is not
   * required"*. On THIS rail that removes a real behaviour — BR-MET-099's
   * deactivate-what-is-missing — so the server keeps the behaviour and refuses
   * the mode by name, and **OQ-580** asks the PO how a utility retires a premise
   * it no longer serves. Do not re-add the option here without that ruling.
   *
   * ⚠ **AND THE LIST IS NO LONGER THIS FILE'S.** It comes from the ONE shared
   * control (`components/workflow/WriteModeChoice`), which is what stopped this
   * screen and the reads upload printing two different translations of the same
   * two options in eight of eleven languages.
   */
  const writeModes = writeModeOptions(
    t,
    {
      // `CR-168` image 38 — a part number comes off the FILE, so the shared
      // sentence's *"takes its number from Settings → Numbering"* is false for
      // parts. The drawn sentence ends *Every other row is created.*
      insert: t(
        kind.id === "parts"
          ? "workflow.parts.insertConsequence"
          : "metering.import.writeMode.insertConsequence",
      ),
      upsert: t("metering.import.writeMode.upsertConsequence"),
    },
    // ⚠ `P1.18` — A MODE THIS TARGET REFUSES IS DRAWN, DISABLED, WITH ITS
    // REASON. It is NOT dropped from the list: the blueprint's words are *"a
    // clerk who has used the premises importer will look for it"*, which is
    // BR-SHL-025 exactly. Passing a shorter array would be the obvious
    // implementation and would make the control vanish.
    writeModeRefusals(kind.id, t),
  );

  /**
   * **HOW MANY ROWS WILL ACTUALLY ARRIVE — `CR-036` AMENDMENT 1 (f).**
   *
   * `checked − errors`, and EXACT rather than an estimate: `_loadable_rows`
   * excludes `duplicate`, `skipped` and `rejected`; the first two were already
   * gone before validate counted (`checked = len(payloads)`); and `errors` is
   * precisely the set validate marked `rejected`. Same arithmetic, same rows,
   * either side of the wire — so this is a restatement of the server's own
   * figures and not a screen re-deriving a number the loader never uses.
   *
   * ⚠ `null` WHENEVER EITHER FIGURE IS ABSENT, so the tile draws the em-dash
   * rather than `NaN`. `counts` is a `Record<string, number>`: a key the server
   * did not send reads `undefined`, and `undefined` in a subtraction is a tile
   * that says nothing at all in the loudest possible way.
   */
  const checkedCount = checked?.counts.checked;
  const blockedCount = checked?.counts.errors;
  const willLoadCount =
    checkedCount === undefined || blockedCount === undefined
      ? null
      : checkedCount - blockedCount;

  /**
   * ⛔ **`CR-046` E3 — WHAT THE COMMIT WILL CALL THE ROWS IT CREATES.**
   *
   * PO 2026-08-27: *"we have number system set in the settings, we shoudl call
   * that function and get unique number and assign it"* — and the ruling's own
   * closing clause, *"the dry run states the numbers it will issue rather than
   * echoing the file's."*
   *
   * ⚠ **THE BLOCK IS THE SERVER'S AND THIS SCREEN COMPUTES NO PART OF IT.**
   * `asset_no_preview_run` walks BE-06's preview contract by an OFFSET, so it
   * ALLOCATES NOTHING and a rehearsal may be run twice; a screen deriving
   * *"M-00042 … M-00061"* from `next_number + count` would print numbers the
   * loader never uses the first time a per-type prefix appeared in the file
   * (`BR-AST-026`: the prefix is per TYPE, the sequence is shared).
   */
  const willIssue = dryRun.data?.will_issue;
  /**
   * ⚠ **DOES THIS TARGET ISSUE NUMBERS AT ALL — ASKED OF THE PAYLOAD, NEVER
   * OF A LIST OF TARGET NAMES IN THIS FILE.**
   *
   * `will_create_to_inventory` is `_dry_run_assets`' own marker: only that
   * branch sends it, and only that branch calls `_issued_numbers_block`. The
   * strip four lines below already uses the same key for the same question,
   * so this asks it once more rather than inventing a second answer.
   *
   * ⚠ **AND THIS IS WHY THE UNSET SENTENCE IS SAFE TO SAY.** Absent
   * `will_issue` has three possible causes — no series row, nothing to create,
   * or a target that does not issue yet (`CR-046` waves C2–C4). The first is
   * the only one left once the other two are excluded, so the screen states a
   * fact rather than guessing at one. Say it for `premises` today and it would
   * be a lie: that target takes its number from the file until C2 lands.
   */
  const targetIssuesNumbers = dryRun.data?.will_create_to_inventory !== undefined;
  /**
   * `_issued_numbers_block` returns `{}` — and the key never travels — when the
   * tenant has no series row for these records. Its own docstring says *"the
   * screen then says the numbering is unset rather than printing an invented
   * range"*, and until now **no screen said anything at all**: hard-won law 1,
   * a comment claiming a guarantee is not the guarantee. The commit's refusal
   * (`assets.asset_no_required_no_series`) is the same fact one stage later,
   * after the operator has mapped a file for nothing.
   */
  const numberingUnset =
    targetIssuesNumbers && willIssue === undefined && (dryRun.data?.will_create ?? 0) > 0;

  const approval = dryRun.data?.approval ?? null;
  /**
   * `BR-SHL-025` — a control that cannot act says WHY. Three reasons, in the
   * order the operator meets them.
   */
  const commitBlockedReason =
    dryRun.data === undefined
      ? t("metering.import.dryRunPending")
      : approval !== null && approval.required && !approved
        ? t("metering.import.approvalBlocked")
        : null;

  function back() {
    if (stage === 1) navigate(exitTo);
    else setStage(stage - 1);
  }

  const advanceDisabled =
    busy ||
    commit.isPending ||
    // CR-026 — a stage in a worker owns the run until it finishes. There is no
    // CANCEL here (BR-MET-102) and no way to start a second stage over the top
    // of the first; the footer's one button simply cannot act while the gauge
    // is running, which is the honest reading of a run that has left the
    // browser.
    deferredStage !== null ||
    fetchReceipt.isPending ||
    // `P5.8` — the scan source advances on having scanned something, exactly
    // as the file source advances on having a file. Both end in a `chosenFile`;
    // what differs is where it came from.
    (stage === 1 && chosenFile === null) ||
    (stage === 1 && sourceId !== SOURCE_FILE && sourceId !== SOURCE_SCAN) ||
    // ⛔ DEF-626 — a required option that is empty blocks stage 2 the way an
    // unmapped required column does. The server would refuse at stage 4, the
    // ONE stage that writes, three clicks later; refusing here says the same
    // sentence at the step that can act on it.
    (stage === 2 &&
      (run === null || targets.length === 0 || missingOptions.length > 0 || templateNameMissing)) ||
    (stage === 3 && run === null) ||
    (stage === 4 && commitBlockedReason !== null) ||
    stage >= 5;

  /**
   * ⛔ **CR-047 (16) — WHAT THE ACCOUNTS TOOK FROM THEIR UNITS, AND WHAT THE
   * DIFFERENCE MEANS.**
   *
   * PO ruling 2026-08-29, verbatim: *"if account is created then we need to
   * inherit details form units"*. The server counts how many actually did.
   *
   * ⚠ **`undefined` IS THE ANSWER "NOBODY COUNTED", AND IT IS NOT A ZERO
   * (`DEF-127`, the AbsentFigure discipline).** A run loaded before the counter
   * existed sends no key at all; read as `0` the screen would flag every
   * historical accounts receipt as entirely unwired — a claim about somebody's
   * books, printed with confidence, that nothing measured. So both figures are
   * `null` unless the server sent the number, and a `null` figure is not drawn.
   *
   * ⚠ **THE DIFFERENCE IS ITS OWN FIGURE, WHICH IS THE WHOLE POINT.** `Loaded`
   * adds a wired account to an unwired one and prints the sum, so *"4 loaded"*
   * reads as four billable accounts when one of them has nothing to bill. That
   * arithmetic is exactly what made this invisible until a bill run.
   *
   * ⚠ It uses `counts.created` and not `receipt.loaded`: `loaded` is
   * `created + updated`, and an account that was already on file did not take
   * anything from a unit on this run — subtracting from the wrong total would
   * report an update as an unwired create.
   */
  const withServices = receipt?.receipt.with_services;
  const createdCount = receipt?.counts.created;
  const withoutServices =
    withServices === undefined || createdCount === undefined
      ? null
      : Math.max(0, createdCount - withServices);
  /** The receipt's own record vocabulary — "accounts", "premises", "meters" —
   *  so one screen's copy serves seven targets without a branch. */
  const recordsWord = t(kind.targetLabelKey).toLowerCase();

  return (
    <WorkflowRunner
      kind={kind}
      stage={stage}
      reached={reached}
      onStageChange={(next) => {
        if (next <= reached) setStage(next);
      }}
      // ⛔ `DEF-PAY-10779` (PO 2026-10-30 Q7 = A). r10 drew `Save mapping as
      // template` here as a button, held DISABLED over `DEF-512` long after
      // the server could save a map. The PO's answer is a choice switched on
      // WITH A NAME, which is a form field on the mapping step (B14 rule 38:
      // how a form is built is the UI rules'), so it lives there now and the
      // dead header button is gone rather than left refusing.
      headerAction={null}
      onBack={back}
      onAdvance={advance}
      advanceDisabled={advanceDisabled}
    >
      <RefusalNotice refusal={failure === null ? null : refusalOf(failure, t)} />

      {/* ⛔ **DEF-964 — THE REFUSAL ON THE ONE SCREEN IN THIS WORKFLOW THAT
          WRITES HAD TO BE ABLE TO NAME ITSELF, AND COULD NOT.**

          The PO's stage-4 commit failed behind a clean rehearsal and the strip
          above said, in full: *"Something went wrong. Nothing was saved — try
          again."* Nothing else. No status, no code, no reference — so the
          report that reached this repo could not be diagnosed from it, and the
          sentence invited the operator to repeat a failing write.

          `client.asEnvelope()` substitutes `api.error.unexpected` whenever the
          answer is not the ratified envelope — a proxy 502, an HTML body, a
          fetch that never returned — and `refusalText` falls back to the same
          key for anything that is not an `ApiError` at all (`requireData`
          throws a bare `Error` on a null body). All three arrive here as one
          indistinguishable sentence.

          ⚠ **THIS LINE ALREADY EXISTED AND WAS WIRED TO TWO SCREENS.**
          `diagnosticOf` was built on the PO's own ruling of 2026-08-10 —
          *"unable to see what is the error on screen — hence as user I'm
          unable to see what is happening"*, reported when the pricing page
          showed this exact sentence over a 502 — and it reached `StateFrame`
          and the public pricing page and not the import wizard. Built is not
          wired (hard-won law 2).

          Codes and identifiers ONLY, never server prose, so TD-16/G14 are
          untouched — and it is deliberately NOT a `br_ref` (DEF-332: our
          internal rule ids do not belong on a utility's screen). The trace
          reference it prints is the SHORT searchable form support looks up by
          prefix. `null` when there is genuinely nothing to say, and then
          nothing renders — an empty row would be its own small lie. */}
      {supportLineOf(failure, (key) => i18n.exists(key)) !== null ? (
        <p className={`mb-3 -mt-1 text-sm ${WF.CELL_MUTED}`} data-diagnostic="import">
          <code>{supportLineOf(failure, (key) => i18n.exists(key))}</code>
        </p>
      ) : null}

      {/* ⚠ **CR-026 — THE ONLY THING A BIG FILE ADDS TO THIS SCREEN.**
          `liveProgress` is `null` for every synchronous run and the panel
          returns `null` on `null`, so a three-row import renders exactly the
          markup it rendered before this change. **And there is NO CANCEL
          CONTROL in or beside it — BR-MET-102 (PO 2026-08-22, verbatim "No"),
          not even a disabled one:** a cancel that is ruled never to exist is
          not a gap for BR-SHL-025 to explain, and greying one out would invite
          an operator to wait for it to light up. The panel names the ruled
          30-day rollback instead, which is the door a wrong file leaves by. */}
      <ImportProgressPanel progress={liveProgress} />
      {awaitingFirstReport && liveProgress === null && (
        <Note data-workflow="progress-starting">{t("metering.import.progress.starting")}</Note>
      )}

      {/* ⛔ **`DEF-2487` — "QUEUED" IS A STATUS UNTIL IT IS A SYMPTOM.**

          The engine refuses to hand a stage to the queue when no worker answers
          its ping, so this is the case that refusal cannot cover: a worker that
          dies in the second AFTER it answered, or a broker that drops the
          message. `apps/tenancy/tasks.send` swallows a dispatch failure by
          design — the record is the truth and a later worker can still claim it
          — which is right, and which means the gauge simply rests `queued` and
          the bar never moves. Without this the operator watches a progress
          panel for a job nothing will ever pick up, and the only place the
          fault is written down is a container log they cannot read.

          ⚠ **THE SERVER DECIDES WHEN, NOT THIS SCREEN** (`stalled`), for the
          same reason it computes `pct`: how long is too long is a property of
          the deployment's dispatch latency, which a browser knows nothing
          about.

          ⚠ **AND IT SAYS "NOTHING HAS BEEN WRITTEN"**, because that is the
          first question a person asks of a stuck commit and the answer is the
          one thing that makes waiting safe: the load is one transaction, so a
          job that never ran wrote nothing at all. */}
      {liveProgress?.stalled === true && (
        <div className={WF.CALLOUT} data-workflow="progress-stalled" role="status">
          <p className={WF.CALLOUT_BODY}>
            {t("metering.import.queuedStalled", {
              seconds: liveProgress.stalled_after_seconds ?? 30,
            })}
          </p>
        </div>
      )}

      {stage === 1 && (
        <div className="flex flex-col gap-6">
          {/* `P1.19` — the card list is the TARGET's, not a module constant.
              Payments draws a fifth, `Scan paper`, because a sack of cheques
              is a SOURCE and never a second screen; no other target has paper
              to scan, and an unconditional fifth card would put a permanently
              refused control on seven screens. The rule is in `kinds.ts` so it
              can be asserted without mounting this wizard. */}
          <SourceCards
            legend={t("workflow.source.legend")}
            choices={workflowSourcesFor(kind.id)}
            selectedId={sourceId}
            groupName="import-source"
            onSelect={setSourceId}
          />

          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            onChange={(event) => {
              const picked = event.target.files?.[0] ?? null;
              setChosenFile(picked);
              // A different file is a different run: everything downstream of
              // stage 1 is stale, and leaving it on screen would show one
              // file's name over another file's rules.
              setRun(null);
              setTransformed(null);
              setChecked(null);
              setReached(1);
            }}
          />
          {/* ⛔ **`CR-139-BRC07` `P5.8` — THE SCAN SOURCE, SWITCHED ON.** The
              fifth card is not a second screen: p067 ① says *"a sack of cheques
              is a SOURCE, never a second screen"*, so choosing it swaps THIS
              stage's target and leaves every stage below untouched. The scanned
              rows become the same `chosenFile` a browsed file lands in, which
              is what makes *"everything after it is the runner"* literally
              true rather than a claim in a comment (hard-won law 1). */}
          {sourceId === SOURCE_SCAN ? (
            <ScanInput
              client={client}
              rows={scanned}
              onRowsChange={(rows) => {
                setScanned(rows);
                // A different set of rows is a different run: everything
                // downstream of stage 1 is stale, exactly as it is when a
                // different file is picked.
                setChosenFile(rows.length === 0 ? null : scannedCsv(rows));
                setRun(null);
                setTransformed(null);
                setChecked(null);
                setReached(1);
              }}
            />
          ) : (
            <DropZone
              file={receivedFileOf(chosenFile, run, sizeLabel)}
              onBrowse={() => fileInput.current?.click()}
            />
          )}

          {/* CR-025 (PO 2026-08-21: "we will need sample CSV files to be
              downloaded at every import at step 1"). The file is the SERVER's
              — header row derived from the target's real columns (BR-MET-088)
              with one example row — so this control fetches, never composes. */}
          <div>
            <Button
              variant="secondary"
              onClick={() => {
                void getImportSample(target, client).then((body) =>
                  saveTextFile(`${target}_sample.csv`, body),
                );
              }}
            >
              {t("metering.import.sampleCsv")}
            </Button>
          </div>

          {/* ⛔ **`DEF-1077` — WHAT TO PUT IN THE COLUMNS, BESIDE THE BUTTON
              THAT HANDS OVER THE FILE.** The header row reads `Unit` now
              rather than `unit_ref`, which tells an operator WHICH column it
              is; these sentences tell them what goes IN it — the unit number,
              a premises-and-label pair, or a bare label unique in this
              utility. The words are the SERVER'S, exactly as at stage 2: a
              screen that writes its own copy about a matcher it cannot see is
              how `DEF-771`'s two halves came apart.

              `blank_reason` is a reading of THIS tenant, not copy about a
              column — it appears only when the utility has no units on file at
              all, which is the state the PO was in, and it names the build
              order rather than saying "leave it blank" (which is true, and
              would seat every meter in inventory — `DEF-1079`'s pairing). */}
          {(templateNotes.data?.columns ?? []).map((column) => (
            <Note key={column.target} data-template-note={column.target}>
              <b>{column.label}</b>
              {" — "}
              {column.help}
              {column.blank_reason === "" ? null : (
                <>
                  {column.help === "" ? "" : " "}
                  <span data-template-blank-reason={column.target}>{column.blank_reason}</span>
                </>
              )}
            </Note>
          ))}

          <div className="grid gap-4 md:grid-cols-2">
            {/* The mapping list is EMPTY and says so: `tenancy.ImportMapping`
                holds no column map (`DEF-512`), so there is no saved template
                to offer. The id lives here and NOT in the sentence — G28/CR-016:
                keep the honesty, drop the provenance. The help text used to end
                "the mapping record holds no column map (DEF-512)", which told a
                clerk our defect number and then described a database row. */}
            <SelectField
              id="import-mapping"
              label={t("metering.import.mappingTemplate")}
              value={mappingId}
              options={templateOptions}
              placeholder={t("metering.import.mappingNone")}
              help={t("metering.import.mappingAuto")}
              onChange={setMappingId}
            />
            <TextField
              id="import-encoding"
              label={t("metering.import.encoding")}
              value={run?.encoding_delimiter ?? t("metering.import.encodingDetected")}
              readOnly
              help={t("metering.import.encodingHelp")}
              onChange={() => undefined}
            />
            <TextField
              id="import-target"
              label={t("metering.import.loadsInto")}
              value={t(kind.targetLabelKey)}
              readOnly
              help={t("metering.import.loadsIntoHelp")}
              onChange={() => undefined}
            />
            <TextField
              id="import-batch-label"
              label={t("metering.import.batchLabel")}
              value={batchLabel}
              placeholder={t("metering.import.batchLabelPlaceholder")}
              onChange={setBatchLabel}
            />
          </div>

          {/* ⚠ **CR-036 AMENDMENT 2 (g) + CR-042 / BR-MET-210 — THE WRITE
              MODE, AT STEP 1, THROUGH THE ONE SHARED CONTROL.** See
              `writeModes` above for the PO's words and the reason it is a
              premise rather than a confirmation. Stage 4 STATES it and offers
              `Change it`, which walks back here (DEF-770).

              This used to be a local `SegmentedField` captioned "Write mode".
              It is now the same component the reads upload mounts, with the
              same caption, the same two options and the same catalogue keys —
              which is the whole of what the PO asked for when they said the
              control behaves differently in different places. */}
          <WriteModeField
            value={writeMode}
            onChange={chooseWriteMode}
            options={writeModes}
            idPrefix="import"
            t={t}
          />
        </div>
      )}

      {stage === 2 && (
        <div className="flex flex-col gap-6">
          {/* BR-MET-096: THIS is the stage that differs between the targets,
              and it differs only in the list the server sends back. */}
          {/* Q7 — the template an exact header match applied, named. */}
          {run?.recognised_template ? (
            <Note data-workflow="template-used">
              {t("metering.import.templateUsed", { name: run.recognised_template.name })}
            </Note>
          ) : null}
          <MappingTable
            rows={mappingRowsOf(run, mapping, labelOf)}
            targets={targets}
            idPrefix="import-map"
            onTargetChange={(source, next) =>
              setMapping((previous) => ({ ...previous, [source]: next }))
            }
          />
          {/* ⛔ DEF-626 — the options this KIND declares, rendered by a runner
              that does not know what any of them are. Above `RowHandlingOptions`
              because a cutover date is a fact about the FILE, and row handling
              is a choice about how to read it. */}
          {optionFields.map((field) => (
            <div key={field.id} className="flex flex-col gap-1">
              <DatePickerField
                id={`import-option-${field.id}`}
                label={t(field.labelKey)}
                value={options[field.id] ?? ""}
                onChange={(value) =>
                  setOptions((previous) => ({ ...previous, [field.id]: value }))
                }
                // ⚠ NO `prefill`. `DatePickerField` would propose it once on
                // mount and the operator would carry a date nobody chose into a
                // migration — BR-TEN-043's reason, and the cutover is the field
                // where a silent default is worst: every ageing band would be
                // wrong by the gap, uncorrectably (hard rule 4).
                dateFormat={tenantDateFormat}
                required={requiredOptionIds.has(field.id)}
                help={t(field.helpKey)}
                error={
                  missingOptions.some((missing) => missing.id === field.id)
                    ? t(field.requiredMessageKey)
                    : undefined
                }
              />
              {/* ⛔ **CR-047 (b) — THE CONSEQUENCE OF LEAVING IT EMPTY, SAID
                  WHERE IT IS LEFT EMPTY.** This field used to BLOCK the stage;
                  the PO ruled on 2026-08-27 that the accounts load and only
                  the money waits, so it is a choice now — and a choice with no
                  stated consequence is a coin toss. Drawn only while the field
                  is genuinely optional: a field that IS required already says
                  what it wants, in the server's own refusal, one line up. */}
              {field.whenEmptyKey !== undefined && !requiredOptionIds.has(field.id) && (
                <Note data-workflow={`option-when-empty-${field.id}`}>
                  {t(field.whenEmptyKey)}
                </Note>
              )}
            </div>
          ))}
          {/* ⚠ **`DEF-751` / `BR-MET-117` (3) — THE FORMAT DATES ARE READ AS,
              ON THE SCREEN WHERE IT CAN STILL BE CHANGED.** PO verbatim: *"or
              when date matching happen at transform level - show the format -
              and in case any issue highlight it there itself"*. The server has
              stamped every offered DATE column with this value since the rule
              landed and no screen read it, so the operator met the alternative
              instead: 9,881 rows mapped, `Matched` beside every column, and
              *"1/1/2026 is not a date this import can read"* on all 9,881 of
              them one whole stage later.

              Drawn only when the target HAS date columns — a premises file
              with none needs no sentence about dates. */}
          {dateColumns.length > 0 && (
            <div data-workflow="date-format" className="flex flex-col gap-1">
              {declaredDateFormat === null ? (
                /* The tenant that declared no format. Provisioning defaults one
                   (`tenancy.services` → `DATE_FORMATS[0]`), so this should be
                   unreachable — and "should be unreachable" is exactly what
                   this repo keeps being caught by. Under BR-MET-117 (1) an
                   unset format has no authority to match against, so EVERY
                   dated cell is refused; that is worth an accent block, not a
                   caption. */
                <p
                  className="bg-[color-mix(in_srgb,var(--color-accent)_8%,transparent)] p-3 text-sm leading-body"
                  data-workflow="date-format-unset"
                >
                  {t("metering.import.dateFormatNone", {
                    defaultValue:
                      "This utility has not set a date format, so no date column can be read and every row carrying a date will be refused. Set one in Settings → Regional before you go on.",
                  })}
                </p>
              ) : (
                <Note data-workflow="date-format-declared">
                  {t("metering.import.dateFormatIs", {
                    format: declaredDateFormat,
                    defaultValue:
                      "Dates are read as {{format}}, the format this utility has set. A cell written any other way is refused rather than guessed at, because 3/4/2026 is two different real days and neither reading raises. If your file writes dates differently, change the setting in Settings → Regional — you do not have to re-cut the file.",
                  })}
                </Note>
              )}
              {mappedDateColumns.length > 0 && (
                <Note data-workflow="date-format-columns">
                  {t("metering.import.dateFormatColumns", {
                    columns: mappedDateColumns.join(" · "),
                    defaultValue: "Read as dates: {{columns}}.",
                  })}
                </Note>
              )}
            </div>
          )}
          {/* ⚠ **`DEF-771` — THE COLUMN SAYS WHICH OF A PLAN'S TWO NAMES IT
              TAKES.** Drawn only for a target that HAS a plan column, and the
              words are the server's own. */}
          {planColumn !== undefined && (
            <Note data-workflow="plan-column-help">
              {mappedPlanColumns.length > 0
                ? `${t("metering.import.planColumnMapped", {
                    columns: mappedPlanColumns.join(" · "),
                    defaultValue: "Read as plans: {{columns}}.",
                  })} `
                : ""}
              {planColumn.help}
            </Note>
          )}
          {/* ⚠ **`DEF-1077` — THE SAME SENTENCE FOR THE `Unit` COLUMN, AND
              THE SAME REASON.** Drawn only for a target that HAS one (the
              three assets targets), and only once the server has sent its
              words. */}
          {unitColumn !== undefined && (
            <Note data-workflow="unit-column-help">{unitColumn.help}</Note>
          )}
          {/* ⛔ **`CR-046` E2 — THE COLUMN WHOSE MEANING CHANGED, SAYING SO
              WHERE THE FILE CAN STILL BE CHANGED.** Header first, because
              that is the string an operator matches against their own
              spreadsheet; the sentence after it, whole and unclamped — a
              truncated help line about a column that must be left BLANK
              would be worse than none. */}
          {helpColumns.map((column) => (
            <Note key={column.target} data-workflow={`column-help-${column.target}`}>
              <b>{column.label}</b>
              {" — "}
              {column.help}
            </Note>
          ))}
          <RowHandlingOptions
            value={rowHandling}
            idPrefix="import-rows"
            onChange={setRowHandling}
          />
          {/* Q7 (PO 2026-10-30) — "Save mapping as template", switched on with
              a name. Kept when the mapping is confirmed (Validate). */}
          <div className="flex flex-col gap-3" data-workflow="save-template">
            <CheckboxField
              id="import-save-template"
              label={t("workflow.saveMapping")}
              checked={saveTemplate}
              onChange={setSaveTemplate}
            />
            {saveTemplate ? (
              <TextField
                id="import-template-name"
                label={t("metering.import.templateName")}
                value={templateName}
                required
                help={templateNameMissing ? t("metering.import.templateNameRequired") : undefined}
                onChange={setTemplateName}
              />
            ) : null}
          </div>
          <ReconcileStrip
            caption={t("workflow.reconcile.afterTransform")}
            layout="rows"
            figures={[
              {
                id: "in",
                label: t("workflow.reconcile.rowsIn"),
                value: transformed?.counts.in ?? run?.counts.in ?? 0,
                flagged: false,
              },
              {
                id: "dropped",
                label: t("workflow.reconcile.duplicatesDropped"),
                value: transformed?.counts.duplicates_dropped ?? 0,
                flagged: (transformed?.counts.duplicates_dropped ?? 0) > 0,
              },
              {
                id: "forward",
                label: t("workflow.reconcile.rowsForward"),
                // `CR-168` · `DEF-WRK-9588` — before Validate is pressed no
                // transform has run, and this read *0* over a 5-row file that
                // Validate then checked as 5. Until the transform answers,
                // every row in goes forward (nothing has been dropped yet).
                value: transformed?.counts.forward ?? run?.counts.in ?? 0,
                flagged: false,
              },
            ]}
          />
        </div>
      )}

      {stage === 3 && (
        <div className="flex flex-col gap-6">
          {savedTemplate !== null ? (
            <Note data-workflow="template-saved">
              {t("metering.import.templateSaved", { name: savedTemplate })}
            </Note>
          ) : null}
          {/* ⚠ **`CR-036` AMENDMENT 1 (f) — A COUNT THAT HAS NOT BEEN
              COMPUTED IS NOT A ZERO.** On the live deployment this strip read
              *"ROWS CHECKED 0 · PASSED CLEAN 0 · ERRORS 0 · WARNINGS 0"* under
              the heading *"Rules that ran"* and the sentence *"No rules ran on
              this file."* — while the progress bar beside it read *"Validating…
              1,646 of 9,881 · 16% complete"*. Two halves of one screen
              contradicting each other, and the half a person believes is the
              half with numbers on it. The true statement was **not yet**; the
              screen said **none**.

              `checked` is `null` until the server has answered with a verdict —
              on a background run that is the whole time the worker is
              validating, and again after a row is fixed and stages 2–3 re-run.
              So every figure below is drawn as an em-dash until there is a
              figure, and both tables say *still checking* instead of *nothing
              found*. BR-MET-085's rule, in its smallest form: never invent a
              number the server has not sent. */}
          <ReconcileStrip
            caption={null}
            layout="tiles"
            tiles={5}
            figures={[
              {
                id: "checked",
                label: t("workflow.kpi.rowsChecked"),
                value: checked?.counts.checked ?? NOT_YET,
                flagged: false,
              },
              {
                /* ⚠ **THE TILE THE OPERATOR ACTUALLY NEEDED, AND IT DID NOT
                   EXIST.** The finished premises run read *"ROWS CHECKED 9881 ·
                   PASSED CLEAN 0 · ERRORS 0 · WARNINGS 9881"* and the PO read it
                   as total failure — *"it rejected and shown all error"*. **Not
                   one row was blocked.** Four true numbers, and no answer to the
                   only question being asked, so the reader assembled the wrong
                   one out of the two loudest.

                   It is `checked − errors` and that is EXACT, not an estimate:
                   `import_runs._loadable_rows` excludes `duplicate`, `skipped`
                   and `rejected`, the first two were already gone before
                   validate counted (`checked = len(payloads)`), and `errors` is
                   precisely the rows validate marked `rejected`. Same
                   arithmetic, same rows, either side of the wire. */
                id: "will-load",
                label: t("workflow.kpi.willLoad", { defaultValue: "Will load" }),
                value: willLoadCount ?? NOT_YET,
                flagged: false,
              },
              {
                /* Was "Errors". A count of errors is a fact about the checks;
                   what an operator needs is the consequence, and the
                   consequence is that these rows do not arrive. */
                id: "errors",
                label: t("workflow.kpi.willNotLoad", { defaultValue: "Blocked — will not load" }),
                value: checked?.counts.errors ?? NOT_YET,
                flagged: (checked?.counts.errors ?? 0) > 0,
              },
              {
                /* Was "Warnings" — which the PO read as a second kind of
                   failure when 9,881 of them sat beside "Passed clean 0". A
                   warning does not stop a row. Say so in the label. */
                id: "warnings",
                label: t("workflow.kpi.loadsWithWarning", {
                  defaultValue: "Loads, with a warning",
                }),
                value: checked?.counts.warnings ?? NOT_YET,
                flagged: false,
              },
              {
                /* Was "Passed clean", which reads as *succeeded* — so `0`
                   beside it reads as *nothing succeeded*, which is what
                   happened. It is the count of rows with no remark of any kind,
                   and now it says only that. */
                id: "clean",
                label: t("workflow.kpi.noRemarks", { defaultValue: "No remarks at all" }),
                value: checked?.counts.clean ?? NOT_YET,
                flagged: false,
              },
            ]}
          />

          {/* The same five figures as one English sentence, because the strip
              is what was misread. Drawn only once there is a verdict. */}
          {checked !== null && willLoadCount !== null && (
            <Note data-workflow="validate-outcome">
              {t("metering.import.validateOutcome", {
                willLoad: willLoadCount,
                blocked: checked.counts.errors,
                warned: checked.counts.warnings,
                records: t(kind.targetLabelKey).toLowerCase(),
                defaultValue:
                  "{{willLoad}} of these {{records}} will load and {{blocked}} are blocked. {{warned}} carry a warning — a warning does not stop a row; it is worth a look before you commit.",
              })}
            </Note>
          )}

          {/* ⛔ **`CR-036` (i) / `DEF-751` — THE ONE SILENT FAILURE IN THE
              WHOLE IMPORT, SAID OUT LOUD AT LAST.**

              A utility mapped `services_available`, stage 2 marked it
              `Matched`, stage 3 found ZERO errors, 9,881 premises loaded — and
              every one of them reads *"No services"*. Measured by exhaustion
              over 11 realistic values: no code drops a value, every
              unrecognised token rejects its row loudly and BY NAME, and the
              only input that produces this is an EMPTY CELL. The run knew:
              `_empty_columns` has served the answer all along and nothing drew
              it.

              It cannot reject and must not default — an empty cell is a legal
              value (`BR-RAT-101`) — so it is SAID, here, at the last stage
              before anything is written. */}
          {emptyColumns.length > 0 && (
            <div
              className="bg-[color-mix(in_srgb,var(--color-accent)_8%,transparent)] p-3 text-sm leading-body"
              data-workflow="empty-columns"
              role="note"
            >
              <p className="font-heading font-bold">
                {t("metering.import.emptyColumnsTitle", {
                  defaultValue: "Mapped, and empty on every row",
                })}
              </p>
              <ul className="mt-1 list-disc pl-5">
                {emptyColumns.map((column) => (
                  <li key={column.target} data-workflow-empty-column={column.target}>
                    {t("metering.import.emptyColumnEntry", {
                      label: labelOf(column.target),
                      source: column.source_column ?? column.target,
                      rows: column.rows,
                      defaultValue:
                        "{{label}} — mapped from {{source}}, and blank in all {{rows}} rows. Nothing will be written to it.",
                    })}
                  </li>
                ))}
              </ul>
              <p className="mt-1">
                {t("metering.import.emptyColumnsBody", {
                  defaultValue:
                    "Nothing else on this screen will mention this: the column reads Matched, no row is rejected and no rule fires — Matched is about the heading, never about the cells. If that is the wrong column, or the file was cut without it, go back to step 2 before you load.",
                })}
              </p>
            </div>
          )}

          {/* **`BR-MET-117` (3) — the mapped columns stage 2 could not READ**,
              per column with the first offending row and one real cell, rather
              than as 9,881 identical reject lines further down the page. */}
          {columnProblems.length > 0 && (
            <div
              className="bg-[color-mix(in_srgb,var(--color-accent)_8%,transparent)] p-3 text-sm leading-body"
              data-workflow="column-problems"
              role="note"
            >
              <p className="font-heading font-bold">
                {t("metering.import.columnProblemsTitle", {
                  defaultValue: "Columns that could not be read",
                })}
              </p>
              <ul className="mt-1 list-disc pl-5">
                {columnProblems.map((problem) => (
                  <li key={problem.target} data-workflow-problem-column={problem.target}>
                    {t("metering.import.columnProblemEntry", {
                      label: labelOf(problem.target),
                      source: problem.source_column ?? problem.target,
                      rows: problem.rows,
                      firstRow: problem.first_row,
                      example: problem.example ?? "",
                      defaultValue:
                        "{{label}} — mapped from {{source}}. {{rows}} row(s) could not be read; the first is row {{firstRow}}, “{{example}}”.",
                    })}
                    {problem.problem === null ? null : ` ${problem.problem}`}
                    {problem.fix_hint === null ? null : ` ${problem.fix_hint}`}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* The format the run ACTUALLY read its dates as — the same statement
              stage 2 made, restated where the verdict is, so an operator
              reading a reject list is never left to guess which format the
              refusal was measured against (`BR-MET-117` (2)'s posture: name
              both sides). */}
          {mappingSpec?.date_format != null && (
            <Note data-workflow="date-format-used">
              {t("metering.import.dateFormatUsed", {
                format: mappingSpec.date_format,
                defaultValue: "Dates in this file were read as {{format}}.",
              })}
            </Note>
          )}

          {/* ⚠ **`CR-036` AMENDMENT 2 (g) — THE CHECKS NAME THE PREMISE THEY
              WERE RUN UNDER.** The PO's own screenshot has this stage saying
              *"This premise ID is already on file — the write mode decides what
              happens to it"* on a screen that never showed the write mode. It
              is chosen at stage 1 now, so this stage can say which one it read
              the file under, and stage 4 can still change it. */}
          <Note data-workflow="checked-under-mode">
            {t("metering.import.checkedUnderMode", {
              mode: writeModes.find((mode) => mode.id === writeMode)?.label ?? writeMode,
              defaultValue:
                "Checked as “{{mode}}”, the choice made at step 1. You can change it at the dry run before anything is written, and the rehearsal there is redone against the new choice.",
            })}
          </Note>

          {/* BR-MET-090: the rules AS THEY RAN, including the ones that could
              not run and why — never a tidied list of the ones that did. */}
          {/* ⚠ **BOTH LISTS GO THROUGH AN ADAPTER, AND THAT IS `DEF-535`.**
              These used to be passed straight through, so the ACTION column
              and the reject list's ROW / KEY / SUGGESTED FIX cells rendered
              `undefined` on every real run — the server spells them `action` /
              `action_value` and `row_no` / `source_key` / `fix_hint`. The
              mapping lives HERE, at the boundary between the two contracts,
              exactly as `row_handling`'s does for `DEF-522`. */}
          <RuleResultsTable
            caption={t("workflow.rules.caption")}
            rules={ruleRowsOf(checked?.rules ?? [], t)}
            /* (f) — "No rules ran on this file." is reserved for a FINISHED
               run that ran none. While the worker is still checking, the true
               sentence is *not yet*. */
            emptyMessage={
              checked === null
                ? t("workflow.rules.stillRunning", {
                    defaultValue:
                      "The checks are still running on this file. Nothing has been decided yet — the count beside the bar says how far along they are.",
                  })
                : t("workflow.rules.empty")
            }
          />
          <RejectList
            caption={t("workflow.rejects.caption")}
            /* DEF-766 — ONE PAGE, sliced by the server. `serverPage` hands the
               footer the server's own total and turns a page click into the
               request above; without it the table would page an array that is
               only ever fifty rows long and the operator would read "50" under
               a run that rejected 9,881. */
            rejects={rejectRowsOf(rejectRows)}
            serverPage={
              checked?.rejects_window === undefined
                ? undefined
                : {
                    total: checked.rejects_window.total,
                    page: rejectPage,
                    per: rejectPer,
                    onPage: setRejectPage,
                    onPer: (next) => {
                      setRejectPer(next);
                      setRejectPage(1);
                    },
                  }
            }
            emptyMessage={
              checked === null
                ? t("workflow.rejects.stillRunning", {
                    defaultValue:
                      "Nothing to fix yet — the checks are still running on this file.",
                  })
                : t("workflow.rejects.empty")
            }
            // D8: the r10 caption's promise made real — per-row inline fix
            // feeding PATCH /imports/{id}/rows/{row_no}, then stages 2–3
            // re-run over the corrected cells.
            onFix={(rowNo, values) => fixRow.mutate({ rowNo, values })}
            fixing={fixRow.isPending || transform.isPending || validate.isPending}
          />
        </div>
      )}

      {stage === 4 && (
        <div className="flex flex-col gap-6">
          {/* ⚠ EVERY FIGURE HERE IS THE SERVER'S. This panel used to print
              stage 3's counts and the string "Not counted yet" for updates;
              `POST /imports/<id>/dry-run` now answers all of them, computed by
              the same function the commit acts on. */}
          <DryRunPanel
            idPrefix="import-load"
            figures={[
              {
                id: "create",
                label: t("workflow.dry.willCreate"),
                value: figureOf(dryRun.data?.will_create),
                numeric: dryRun.data !== undefined,
              },
              // ⛔ **`DEF-1079` — "WILL CREATE 20" IS NOT AN HONEST NUMBER ON
              //     ITS OWN, ON AN ASSETS TARGET.** The PO rehearsed twenty
              //     meters, read "Will create 20 · Existing records updated 0
              //     · Rows rejected 0", and nothing on this strip said all
              //     twenty were going into INVENTORY — twenty meters that
              //     cannot take a reading or be billed until somebody assigns
              //     them. The two figures SUM to `will_create`, so they read
              //     as a breakdown of the number above rather than as new
              //     totals. Drawn only when the server sends them: the three
              //     non-assets targets have no such split, and a zero there
              //     would be a claim about something that does not exist.
              ...(dryRun.data?.will_create_to_inventory === undefined
                ? []
                : [
                    {
                      id: "create-in-service",
                      label: t("workflow.dry.willCreateInService"),
                      value: figureOf(dryRun.data?.will_create_in_service),
                      numeric: true,
                    },
                    {
                      id: "create-to-inventory",
                      label: t("workflow.dry.willCreateToInventory"),
                      value: figureOf(dryRun.data?.will_create_to_inventory),
                      numeric: true,
                    },
                  ]),
              {
                id: "update",
                label: t("workflow.dry.willUpdate"),
                value: figureOf(dryRun.data?.will_update),
                numeric: dryRun.data !== undefined,
              },
              {
                id: "reject",
                label: t("workflow.dry.willReject"),
                value: figureOf(dryRun.data?.rejected),
                numeric: dryRun.data !== undefined,
              },
              // ⛔ **CR-046 — *"in case of insert - reject it"* (PO 2026-08-27).**
              //     Under `insert` a row naming a record already on file does
              //     not load, and until this landed the strip said nothing
              //     about it at all: `will_update` simply went to 0 and the
              //     operator was left to infer that rows had vanished.
              //     ⚠ DRAWN ONLY WHEN NON-ZERO: a `0` under `upsert` would be a
              //     claim about a mode that rejects nothing by design, which is
              //     the reasoning BR-MET-099's three figures already follow.
              ...(dryRun.data?.will_reject_existing
                ? [
                    {
                      id: "reject-existing",
                      label: t("workflow.dry.willRejectExisting"),
                      value: String(dryRun.data.will_reject_existing),
                      numeric: true,
                    },
                  ]
                : []),
              // BR-MET-100's figure travels with the run it belongs to and is
              // drawn only for a UNITS import, because a premises has no plan.
              ...(target === "units"
                ? [
                    {
                      id: "unplanned",
                      label: t("workflow.dry.unplannedUnits"),
                      value: figureOf(dryRun.data?.unplanned_units),
                      numeric: dryRun.data !== undefined,
                    },
                  ]
                : []),
              // ── BR-MET-099's three numbers, and ONLY for `replace` ────────
              // The server omits them on the other two modes because none of
              // them is true there; a zero would read as "nothing will be
              // retired" on a mode that retires nothing by design.
              ...(dryRun.data?.will_deactivate === undefined
                ? []
                : [
                    {
                      id: "not-in-file",
                      label: t("workflow.dry.notInFile"),
                      value: String(dryRun.data.not_in_file ?? 0),
                      numeric: true,
                    },
                    {
                      id: "skipped-occupied",
                      label: t("workflow.dry.skippedOccupied"),
                      value: String(dryRun.data.skipped_occupied ?? 0),
                      numeric: true,
                    },
                    {
                      id: "will-deactivate",
                      label: t("workflow.dry.willDeactivate"),
                      value: String(dryRun.data.will_deactivate),
                      numeric: true,
                    },
                  ]),
              {
                id: "target",
                label: t("workflow.dry.target"),
                value: t(kind.targetLabelKey),
                numeric: false,
              },
            ]}
            // CR-036 (g) — the SAME list stage 1 offers. Declared once, above.
            modes={writeModes}
            selectedModeId={writeMode}
            // ⚠ DEF-770 — stage 4 STATES the mode and does not offer a second
            // control for it. PO: "Write mode from this screen may not required
            // . it is already added on step 1". `back()` steps one stage at a
            // time, so this is the same road an operator already has, named.
            onChangeModeRequested={() => setStage(1)}
            approval={{
              // DATA, not a screen constant (DEF-435) — both bars, this run's
              // reject count and its batch size all arrive on `dry-run`.
              threshold_pct: approval?.threshold_pct ?? 0,
              rejected: approval?.rejected ?? 0,
              of_rows: approval?.of_rows ?? 0,
              always_requires:
                approval === null
                  ? null
                  : t("metering.import.approvalBars", {
                      pct: approval.threshold_pct,
                      rows: approval.threshold_rows,
                    }),
            }}
            options={loadOptions}
            onOptionsChange={setLoadOptions}
            offerRollbackPoint={rollbackControlIsOffered(kind)}
          />

          {/* ⛔ **`CR-046` E3 — THE NUMBERS, ON THE LAST SCREEN BEFORE THE
              WRITE.** A rehearsal that printed *"Will create 20"* and nothing
              else left the operator with no way to learn what those twenty
              meters would be CALLED — on the very change that took the naming
              away from them. Drawn only when the server sent the block; the
              alternative branch is a STATED ABSENCE and never a blank. */}
          {willIssue !== undefined && (
            <div className="flex flex-col gap-2" data-workflow="will-issue">
              <p className="font-heading font-bold">{t("metering.import.willIssueTitle")}</p>
              <Note data-workflow="will-issue-range">
                {t("metering.import.willIssueRange", {
                  numbers: willIssue.numbers.join(" · "),
                  /* ⚠ `last` is the number the FINAL created row gets, so
                     twenty rows never read as the five the preview caps at
                     (`PREVIEW_NUMBERS_SHOWN`). `null` only when the run
                     creates nothing, which this branch has already excluded —
                     the fallback is the last number actually shown rather
                     than an empty gap. */
                  last:
                    willIssue.last ?? willIssue.numbers[willIssue.numbers.length - 1] ?? "",
                })}
              </Note>
              <Note>{t("metering.import.willIssueSentence")}</Note>
            </div>
          )}
          {numberingUnset && (
            <Note data-workflow="will-issue-unset">{t("metering.import.willIssueUnset")}</Note>
          )}

          {/* ⚠ **`DEF-771` — THE TILE SAYS 9,881 AND NEVER WHICH PLAN.** The
              rehearsal is the last screen before anything is written, so it is
              the one where naming the plan can still save the run. */}
          <UnplannedPlans
            entries={dryRun.data?.unplanned_plans ?? []}
            title={t("metering.import.unplannedPlansWillTitle", {
              defaultValue: "These units will be created with no plan",
            })}
          />

          {/* ⚠ **BR-MET-099 IN WORDS, BEFORE THE COMMIT** — the rule's own
              sentence shape: *"69 premises are on file and not in this file.
              41 have active accounts and will be skipped. 28 will be
              deactivated."* It is a paragraph and not three tiles because the
              rule requires the run to SAY it, and because the middle number is
              the one an operator has to read: rows that are NOT going to be
              retired, and why. */}
          {dryRun.data?.will_deactivate !== undefined && (
            <Note data-workflow="replace-sentence">
              {t("metering.import.replaceSentence", {
                notInFile: dryRun.data.not_in_file ?? 0,
                skipped: dryRun.data.skipped_occupied ?? 0,
                deactivate: dryRun.data.will_deactivate,
                records: t(kind.targetLabelKey).toLowerCase(),
              })}
            </Note>
          )}

          {/* ⚠ **THE COMMIT ASKS FOR THE APPROVAL; IT NEVER ASSUMES IT.**
              `BR-MET-098` is a second pair of EYES, so the tick is its own
              control, it names WHICH bar was crossed, and `Commit load ✓`
              stays disabled with its reason until somebody makes it. An Owner
              or an Admin approves — the server refuses a Billing Clerk who
              sends it (BR-RAT-091's pair, DEF-545 for the engine half). */}
          {approval !== null && approval.required && (
            <div className="flex flex-col gap-2" data-workflow="approval-gate">
              <Note>
                {t(APPROVAL_BECAUSE_KEY[approval.because ?? "percent"], {
                  rejected: approval.rejected,
                  rows: approval.of_rows,
                  pct: approval.threshold_pct,
                  bar: approval.threshold_rows,
                })}
              </Note>
              <CheckboxField
                id="import-load-approved"
                label={t("metering.import.approvalConfirm")}
                checked={approved}
                onChange={setApproved}
              />
            </div>
          )}

          {/* ⛔ **`DEF-2487` — THE LIST OF WHAT FAILED, AT THE MOMENT SOMEBODY
              NEEDS IT, WHICH IS THE MOMENT WE DID NOT OFFER IT.**

              Both result files hung off the stage-5 Result screen, and a commit
              that fails never reaches stage 5. So an operator whose load fell
              over sat HERE, reading *"Rows rejected 41"*, with no way to learn
              which forty-one or why — and the only thing that lets them fix
              their spreadsheet and try again is that list.

              ⚠ **`downloadResults` IS REUSED, NOT COPIED.** One download
              mechanism on this screen, one filename convention, one failure
              handler. The server serves the failures half from `validated`
              onward for the same reason (`_refuse_failures_not_decided`); the
              SUCCESSES half is deliberately not offered here, because nothing
              has loaded yet and a file with a header and no rows reads as an
              answer.

              ⚠ **DRAWN ONLY WHEN THE REHEARSAL FOUND SOMETHING**, exactly as
              stage 5 draws its own: a *"download the rows that failed"* button
              over a clean run offers an empty file and reads as an accusation.
              The Product Owner's 1,048-account run rejected nothing, so on that
              run this stays invisible — the timeout was the fault there, and
              this block is for the runs where it is the file. */}
          {(dryRun.data?.rejected ?? 0) > 0 && (
            <div className="flex flex-col gap-2" data-workflow="stage4-failures">
              <Note>{t("metering.import.failuresBeforeCommitNote")}</Note>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" onClick={() => downloadResults("failures")}>
                  {t("metering.import.downloadFailures", {
                    count: dryRun.data?.rejected ?? 0,
                  })}
                </Button>
              </div>
            </div>
          )}

          <Note>
            {commitBlockedReason ?? t("metering.import.commitNote")}
          </Note>
        </div>
      )}

      {stage === 5 && receipt !== null && (
        <div className="flex flex-col gap-6">
          {/* r10's result KPIs, read from what the run RECORDED (BR-MET-090
              past the commit) — never recounted from the database. */}
          <ReconcileStrip
            caption={null}
            layout="tiles"
            figures={[
              {
                id: "loaded",
                label: t("workflow.kpi.loaded"),
                value: receipt.receipt.loaded,
                flagged: false,
              },
              {
                id: "rejected",
                label: t("workflow.kpi.rejected"),
                value: receipt.receipt.rejected,
                flagged: receipt.receipt.rejected > 0,
              },
              {
                id: "flagged",
                label: t("workflow.kpi.flagged"),
                value: receipt.receipt.flagged,
                flagged: receipt.receipt.flagged > 0,
              },
              // ⛔ **CR-047 (16) — WHAT THE NEW ACCOUNTS INHERITED FROM THEIR
              //     UNITS (PO ruling 2026-08-29).** Beside `loaded`, because
              //     the pair is the statement: four accounts arrived and three
              //     of them can be billed.
              //     ⚠ `undefined` draws NOTHING. It is *"nobody counted"*, and
              //     printing 0 would flag every pre-ruling receipt as wholly
              //     unwired — a claim about somebody's books nothing measured.
              ...(withServices === undefined
                ? []
                : [
                    {
                      id: "with-services",
                      label: t("workflow.receipt.withServices"),
                      value: withServices,
                      flagged: false,
                    },
                  ]),
              // ⚠ **AND THE DIFFERENCE IS ITS OWN FLAGGED FIGURE.** An account
              //     wired to nothing loads clean, counts as *loaded*, and
              //     cannot be billed — so adding it to a wired one and printing
              //     the sum is exactly what hid this until a bill run. It is
              //     work owed, not a statistic.
              ...(withoutServices !== null && withoutServices > 0
                ? [
                    {
                      id: "without-services",
                      label: t("workflow.receipt.withoutServices"),
                      value: withoutServices,
                      flagged: true,
                    },
                  ]
                : []),
              // BR-MET-100: *"a build that writes the flag and surfaces it
              // nowhere has implemented option C"*. This is the surface.
              ...(target === "units"
                ? [
                    {
                      id: "unplanned",
                      label: t("workflow.dry.unplannedUnits"),
                      value: receipt.receipt.unplanned_units,
                      flagged: receipt.receipt.unplanned_units > 0,
                    },
                  ]
                : []),
              // ⛔ **CR-046 — the rows that did NOT load because they named a
              //     record already on file.** The PO chose the word *reject*
              //     over *skip*: a skip reads as "nothing needed doing", a
              //     reject reads as "this row did not load".
              ...(receipt.receipt.rejected_existing
                ? [
                    {
                      id: "rejected-existing",
                      label: t("workflow.receipt.rejectedExisting"),
                      value: receipt.receipt.rejected_existing,
                      flagged: true,
                    },
                  ]
                : []),
              // ⛔ **ADDRESSES THAT LOADED WITH NOBODY TO CHARGE (PO ruling
              //     2026-08-27).** A blank Owner column LOADS — that is the
              //     ruling — and the cost is that the address cannot be billed
              //     until somebody fills the owner in. **This figure is the
              //     whole mitigation**: without it those rows are silently
              //     indistinguishable from complete ones, and a utility
              //     discovers the gap at its first bill run instead of here.
              //     `flagged` on purpose — it is work owed, not a statistic.
              ...(target === "premises" && receipt.receipt.premises_with_no_owner
                ? [
                    {
                      id: "no-owner",
                      label: t("workflow.receipt.premisesWithNoOwner"),
                      value: receipt.receipt.premises_with_no_owner,
                      flagged: true,
                    },
                  ]
                : []),
              // ⛔ **CR-055 — THE SAME TOTAL, SPLIT INTO THE TWO KINDS OF WORK
              //     IT REPRESENTS (PO ruling 2026-08-31).** An ambiguous owner
              //     name now LOADS ownerless instead of being rejected, so it
              //     joins the figure above. **Both halves have nobody to
              //     charge and need OPPOSITE work from a person** — a blank
              //     needs RESEARCH, an ambiguity needs a DECISION between two
              //     named parties the file already knows — and merging them
              //     into one number throws away the half an operator can
              //     settle from this screen today.
              //     ⚠ Drawn only when the component is non-zero. A run loaded
              //     before 2026-08-31 carries NEITHER key, and `0` beside a
              //     non-zero total would read as *"none of them were blanks"*
              //     — a claim about somebody's migration that nothing measured.
              ...(target === "premises" && receipt.receipt.premises_owner_blank
                ? [
                    {
                      id: "owner-blank",
                      label: t("workflow.receipt.premisesOwnerBlank"),
                      value: receipt.receipt.premises_owner_blank,
                      flagged: true,
                    },
                  ]
                : []),
              ...(target === "premises" && receipt.receipt.premises_owner_ambiguous
                ? [
                    {
                      id: "owner-ambiguous",
                      label: t("workflow.receipt.premisesOwnerAmbiguous"),
                      value: receipt.receipt.premises_owner_ambiguous,
                      flagged: true,
                    },
                  ]
                : []),
              // An address offering NO services refuses every service on every
              // unit under it — and the symptom appears two uploads later, as
              // meters rejected for a service the utility plainly sells. Said
              // here, where the operator is still looking at the premises run.
              ...(target === "premises" && receipt.receipt.premises_with_no_services
                ? [
                    {
                      id: "no-services",
                      label: t("workflow.receipt.premisesWithNoServices"),
                      value: receipt.receipt.premises_with_no_services,
                      flagged: true,
                    },
                  ]
                : []),
              // ⛔ **CR-058 W3 · THE TWO SENTENCES THE RULING ASKS FOR (PO
              //     2026-09-01).** *"If owner name is given and one identify
              //     given - DL, SSN, Phone or Tax ID - then you create master
              //     account and Customer ID - otherwise dont create
              //     anything"*, and `CR-058` task 12: **the receipt must say
              //     which rows got an owner account and which are waiting for
              //     someone to identify the owner.**
              //     ⚠ The first is NOT `flagged` — it is work that got DONE,
              //     and colouring it as owed would make a good migration read
              //     like a bad one. The three below it are all owed work.
              ...(target === "premises" && receipt.receipt.premises_owner_accounts_created
                ? [
                    {
                      id: "owner-accounts-created",
                      label: t("workflow.receipt.premisesOwnerAccountsCreated"),
                      value: receipt.receipt.premises_owner_accounts_created,
                      flagged: false,
                    },
                  ]
                : []),
              // ⚠ **THIS ONE IS THE MITIGATION, NOT A STATISTIC.** The address
              //     loaded and nobody was created for it, so it has nobody to
              //     charge — and without the number those rows are silently
              //     indistinguishable from complete ones.
              ...(target === "premises" && receipt.receipt.premises_owner_awaiting_identity
                ? [
                    {
                      id: "owner-awaiting-identity",
                      label: t("workflow.receipt.premisesOwnerAwaitingIdentity"),
                      value: receipt.receipt.premises_owner_awaiting_identity,
                      flagged: true,
                    },
                  ]
                : []),
              // Counted apart because the WORK is different: choosing a
              //     category from a list, versus going to find an identifier.
              ...(target === "premises" && receipt.receipt.premises_owner_no_account_type
                ? [
                    {
                      id: "owner-no-account-type",
                      label: t("workflow.receipt.premisesOwnerNoAccountType"),
                      value: receipt.receipt.premises_owner_no_account_type,
                      flagged: true,
                    },
                  ]
                : []),
              ...(target === "premises" && receipt.receipt.premises_owner_identity_mismatch
                ? [
                    {
                      id: "owner-identity-mismatch",
                      label: t("workflow.receipt.premisesOwnerIdentityMismatch"),
                      value: receipt.receipt.premises_owner_identity_mismatch,
                      flagged: true,
                    },
                  ]
                : []),
              ...(target === "premises" && receipt.receipt.premises_owner_account_refused
                ? [
                    {
                      id: "owner-account-refused",
                      label: t("workflow.receipt.premisesOwnerAccountRefused"),
                      value: receipt.receipt.premises_owner_account_refused,
                      flagged: true,
                    },
                  ]
                : []),
              // ⛔ **CR-058 W7 · WHAT THIS FILE SAID ABOUT ITS CUSTOMERS (PO
              //     ruling 2026-09-01).** *"Without identifier we cannot create
              //     Customer ID or master account ot regular account"* — so an
              //     accounts receipt has to separate the rows that brought a
              //     customer in, the rows that joined one already on file, and
              //     the rows that named somebody and identified nobody.
              //     ⚠ The first two are work that got DONE and are not
              //     `flagged`; colouring them as owed would make a good
              //     migration read like a bad one.
              ...(target === "accounts" && receipt.receipt.customers_created
                ? [
                    {
                      id: "customers-created",
                      label: t("workflow.receipt.customersCreated"),
                      value: receipt.receipt.customers_created,
                      flagged: false,
                    },
                  ]
                : []),
              ...(target === "accounts" && receipt.receipt.customers_matched
                ? [
                    {
                      id: "customers-matched",
                      label: t("workflow.receipt.customersMatched"),
                      value: receipt.receipt.customers_matched,
                      flagged: false,
                    },
                  ]
                : []),
              // ⚠ **THIS ONE IS THE MITIGATION, NOT A STATISTIC.** Nothing
              //     loaded for those rows — no account and no customer — and
              //     without the number a migration that identified half its
              //     customers is indistinguishable from a finished one.
              ...(target === "accounts" && receipt.receipt.accounts_awaiting_identity
                ? [
                    {
                      id: "accounts-awaiting-identity",
                      label: t("workflow.receipt.accountsAwaitingIdentity"),
                      value: receipt.receipt.accounts_awaiting_identity,
                      flagged: true,
                    },
                  ]
                : []),
              // Counted apart because the WORK is different: saying whether
              //     somebody is a person or a company is a dropdown; finding an
              //     identifier is a trip to a filing cabinet.
              ...(target === "accounts" && receipt.receipt.accounts_identity_mismatch
                ? [
                    {
                      id: "accounts-identity-mismatch",
                      label: t("workflow.receipt.accountsIdentityMismatch"),
                      value: receipt.receipt.accounts_identity_mismatch,
                      flagged: true,
                    },
                  ]
                : []),
              // How many identifiers this run took from the tenant's series.
              // Recorded rather than derived so a receipt read a year from now
              // says where those numbers came from without anyone having to
              // know the rule. ⚠ Always 0 on the accounts target.
              ...(receipt.receipt.numbers_issued_from_series
                ? [
                    {
                      id: "numbers-issued",
                      label: t("workflow.receipt.numbersIssued"),
                      value: receipt.receipt.numbers_issued_from_series,
                      flagged: false,
                    },
                  ]
                : []),
              // ⛔ **OPENING BALANCES THIS RUN IS HOLDING (PO ruling
              //     2026-08-27).** The accounts are on file and no journal
              //     entry exists — the only state in which the changeover date
              //     is still changeable, because hard rule 4 makes a posted
              //     entry permanent. **A migration that is 90% done must not
              //     look identical to a finished one**, so the count is drawn
              //     and it is `flagged`: it is work owed, not a statistic. An
              //     operator who closes this tab believing the books are on the
              //     system finds out at the first bill run that no account has
              //     a balance.
              ...(receipt.receipt.opening_held
                ? [
                    {
                      id: "opening-held",
                      label: t("workflow.receipt.openingHeld"),
                      value: receipt.receipt.opening_held,
                      flagged: true,
                    },
                  ]
                : []),
              // BR-MET-099's outcome, on the receipt as well as the rehearsal.
              ...(receipt.receipt.deactivated > 0 || receipt.receipt.skipped_occupied > 0
                ? [
                    {
                      id: "deactivated",
                      label: t("workflow.kpi.deactivated"),
                      value: receipt.receipt.deactivated,
                      flagged: true,
                    },
                    {
                      id: "skipped-occupied",
                      label: t("workflow.dry.skippedOccupied"),
                      value: receipt.receipt.skipped_occupied,
                      flagged: false,
                    },
                  ]
                : []),
            ]}
          />

          {/* ⛔ **CR-047 (16) — THE FLAGGED FIGURE, AS A SENTENCE.** The tile
              says *how many*; this says *what it costs and what to do*, which
              is the half a person can act on. Drawn only when there IS a
              difference — a run where every account took its services needs no
              paragraph about the ones that did not. */}
          {withoutServices !== null && withoutServices > 0 && (
            <Note data-workflow="without-services-note">
              {t("metering.import.withoutServicesNote", {
                count: withoutServices,
                created: createdCount,
                records: recordsWord,
              })}
            </Note>
          )}

          {/* `DEF-771` — the same lines, as LOADED. An operator who did not
              read the rehearsal still has to be able to act on the receipt. */}
          <UnplannedPlans
            entries={receipt.receipt.unplanned_plans ?? []}
            title={t("metering.import.unplannedPlansDidTitle", {
              defaultValue: "These units were created with no plan",
            })}
          />

          {/* ⛔ **CR-055 — WHICH PARTIES EACH AMBIGUOUS SPELLING LOOKED LIKE.**
              The count above says HOW MANY addresses are waiting on a decision;
              this says WHICH decision, by name, so the person settling it does
              not have to re-run the search the import already ran.
              ⚠ **Names, never ids (B14 rule 31)** — the server drops the owner
              id from these entries, and a landlord is recognised by name. */}
          <OwnerAmbiguities entries={receipt.receipt.premises_owner_ambiguous_names ?? []} />

          {/* ⛔ **CR-047 (17 a) — THE DOOR OUT OF THE HOLD, ON THE SCREEN THAT
              NAMES THE HOLD.**

              PO ruling 2026-08-27: the accounts LOAD and only the money waits.
              `opening_held` has been drawn as a flagged figure since that day
              and there was **nothing on this screen, or anywhere in the
              product, that could end the wait** — `POST .../confirm-changeover`
              was complete on the server and had no client wrapper and no call
              site (hard-won law 2).

              ⚠ **THE LABEL IS THE RULE'S OWN SENTENCE, NOT THE WORD
              *CUTOVER*.** `confirm_changeover_date`'s docstring says so in as
              many words: *"the last day your old system was in charge of the
              money — that is what the screen must ask for, in those words"*.
              The PO met *cutover* on a screen that blocked them and could not
              tell what it was for; nobody at a two-person utility will do
              better.

              ⚠ **B14 rule 11 — THE CONSEQUENCE BEFORE THE COMMIT**, and here
              the consequence is permanence: the moment this posts, an immutable
              journal entry exists (hard rule 4) and the date can only be
              corrected by a new entry. The sentence says that BEFORE the
              button, with the provisional date the balances are sitting under
              right now, so the operator can see what they are replacing.

              ⚠ **NO CLIENT-SIDE DATE CHECK.** The server refuses a future date
              BY NAME and the refusal lands in the strip at the top of this
              runner like every other. A browser-side re-implementation would
              need *today* in the tenant's zone, which this runner does not
              have — so the two would disagree on exactly the days that
              matter. */}
          {receipt.receipt.opening_held ? (
            <div
              className="flex flex-col gap-3 bg-[color-mix(in_srgb,var(--color-accent)_8%,transparent)] p-3 text-sm leading-body"
              data-workflow="changeover"
              role="note"
            >
              <p className="font-heading font-bold">{t("metering.import.changeoverTitle")}</p>
              <p className="m-0 max-w-measure">
                {t("metering.import.changeoverHeld", {
                  count: receipt.receipt.opening_held,
                  date:
                    receipt.receipt.changeover_provisional ??
                    t("workflow.receipt.notRecorded"),
                })}
              </p>
              <DatePickerField
                id="import-changeover-on"
                label={t("metering.import.changeoverLabel")}
                value={changeoverOn}
                onChange={setChangeoverOn}
                // ⚠ NO `prefill`, and `changeover_provisional` is precisely why:
                // it is *today − 90 days*, a placeholder this product chose so
                // the books stay recognisable while somebody finds the real
                // date. Proposing it here would turn a number nobody chose into
                // one that looks typed, and one click welds it into an entry
                // that cannot be edited (BR-TEN-043, hard rule 4).
                dateFormat={tenantDateFormat}
                required
                help={t("metering.import.changeoverHelp")}
              />
              <div>
                <Button
                  variant="primary"
                  disabled={changeoverOn.trim() === "" || confirmChangeover.isPending}
                  onClick={() => confirmChangeover.mutate()}
                >
                  {t("metering.import.changeoverAction")}
                </Button>
              </div>
            </div>
          ) : receipt.receipt.changeover_on ? (
            /* Posted. The receipt keeps saying WHEN, because that date is the
               one every ageing band, reminder and late fee is measured from and
               it can no longer be changed. */
            <Note data-workflow="changeover-done">
              {t("metering.import.changeoverDone", { date: receipt.receipt.changeover_on })}
            </Note>
          ) : null}

          {/* ⛔ **CR-047 (14) — THE ROWS THAT DID NOT LOAD, ON THE RECEIPT.**

              PO ruling 2026-08-29, verbatim: *"if it is success then you read
              next record, if it is fail - you display on screen shich record
              failed and why (dont write to dB) and continue to uplaod next
              record"*.

              ⚠ **ONE LIST, NOT TWO — AND IT IS `RejectList`.** A person reading
              a receipt asks one question: *what did not load?* Splitting the
              checks' refusals from the write's would make them answer it twice
              and would put a second reject table in the product for the first
              maintainer to diverge. The stage-4 failures arrive on the SAME row
              records with `outcome`, `problem` and `fix_hint` populated, so the
              adapter that already exists reads them unchanged.

              ⚠ **AND IT PAGES, WHICH IS `CR-036` AMENDMENT 1 (b) INHERITED
              RATHER THAN RE-LEARNED.** A units file once rejected 9,881 of
              9,881 rows and this table drew every one of them: 69,241 nodes and
              a 3.6-second render, on which the PO clicked a control that had
              not repainted. The receipt's list can be exactly that long.

              ⚠ **NO `onFix`.** `Fix here…` sends the run back to `extracted` so
              stages 2–3 re-run — over a run that has ALREADY WRITTEN. Offering
              it after the commit would invite an operator to re-validate a
              finished load; the file is the place to correct these rows, which
              is what the sentence below says. */}
          {resultTotal > 0 && (
            <div className="flex flex-col gap-2">
              <RejectList
                caption={t("metering.import.failedRowsCaption")}
                rejects={rejectRowsOf(resultRejectRows)}
                serverPage={
                  receipt.rejects_window === undefined
                    ? undefined
                    : {
                        total: receipt.rejects_window.total,
                        page: resultPage,
                        per: resultPer,
                        onPage: setResultPage,
                        onPer: (next) => {
                          setResultPer(next);
                          setResultPage(1);
                        },
                      }
                }
                emptyMessage={t("metering.import.failedRowsEmpty")}
              />
              <Note data-workflow="failed-rows-note">{t("metering.import.failedRowsNote")}</Note>
            </div>
          )}

          {/* ⛔ **CR-047 (15) — THE TWO FILES.** PO ruling 2026-08-29: *"at the
              end we need 2 CsV file 1 for success record and other for failed
              records"*.

              ⚠ **LABELLED FOR A PERSON, NOT FOR A MACHINE.** `kind=successes`
              is the wire; *"Download the accounts that loaded"* is the button.
              And the failures button CARRIES ITS COUNT, so an operator knows
              how big the job in front of them is before they open the file —
              the same argument `opening_held` makes one block up.

              ⚠ **THE FAILURES BUTTON IS DRAWN ONLY WHEN THERE ARE FAILURES.**
              A "download the rows that failed" button over a clean run offers
              an empty file and reads as an accusation. */}
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => downloadResults("successes")}>
              {t("metering.import.downloadSuccesses", { records: recordsWord })}
            </Button>
            {resultTotal > 0 && (
              <Button variant="secondary" onClick={() => downloadResults("failures")}>
                {t("metering.import.downloadFailures", { count: resultTotal })}
              </Button>
            )}
          </div>

          <Receipt
            receipt={receiptDataOf(receipt, t, formatWhen)}
            showRollback={rollbackControlIsOffered(kind)}
          />

          {/* ⚠ **THE SENTENCE COMES BEFORE THE BUTTON** (B14 rule 11 applied
              to a reversal). LIVE since DEF-552: one click arms, a second
              fires — the danger tier's two-step on a destructive commit. A run
              already rolled back states so instead of offering it twice. */}
          <RollbackNotice
            /* DEF-623: the sentence is THIS target's, not premises' for all six. */
            body={kind.rollbackBody}
            /* ⛔ **`P1.22` — A KIND WHOSE SENTENCE IS A REFUSAL DRAWS NO
               CONTROL.** For every kind before payments the sentence was a
               WARNING and the button was right to be there; for payments it is
               a REFUSAL — a posted payment cannot be unwritten (hard rule 4),
               the server refuses the target by name, and no rollback point is
               ever created. Drawing the button anyway would be a live control
               over a door that is shut: hard-won law 2's mirror, in the one
               place money lands in bulk.

               ⚠ Reads refuses too and never showed a button — but only
               because it mounts a DIFFERENT screen. That was true by accident
               of routing. This is true by rule. */
            action={
              !rollbackControlIsOffered(kind) ? null : receipt.status === "rolled_back" ? (
                <p className="text-sm font-medium">
                  {t("metering.import.rolledBack", {
                    reversed: receipt.counts?.rolled_back ?? 0,
                    kept: receipt.counts?.kept_occupied ?? 0,
                  })}
                </p>
              ) : !rollbackArmed ? (
                <Button variant="danger" onClick={() => setRollbackArmed(true)}>
                  {t("workflow.rollback.action")}
                </Button>
              ) : (
                <div className="flex items-center gap-3">
                  <Button
                    variant="danger"
                    disabled={rollback.isPending}
                    onClick={() => rollback.mutate()}
                  >
                    {t("metering.import.rollbackConfirm")}
                  </Button>
                  <Button variant="secondary" onClick={() => setRollbackArmed(false)}>
                    {t("confirm.cancel")}
                  </Button>
                </div>
              )
            }
          />

          <Note>{t(kind.nextNoteKey)}</Note>
          <div>
            <ButtonLink variant="primary" to={exitTo}>
              {t(kind.exitLabelKey)}
            </ButtonLink>
          </div>
        </div>
      )}

    </WorkflowRunner>
  );
}

export default ImportWorkflowPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-023 P5 · DEF-520 (the mount) + CR-023 W2 (stages 4 and 5 —
//         B15 §4.4/§4.5 · §12 rows 5–9; BR-MET-098 · BR-MET-099 · BR-MET-100,
//         PO rulings 2026-08-21) + DEF-535 (the rules/rejects adapter)
// generated: 2026-08-21 by the DEF-520 lane · AMENDED 2026-08-22 by the CR-023 · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (the exit route reads the KIND's own returnTo — the three assets kinds exit to Assets; premises/units are byte-identical) · AMENDED 2026-08-26 by lane PAYLOAD (DEF-766 — the reject list travels as a WINDOW: run_dict serves REJECT_WINDOW_DEFAULT = 50 rejects plus rejects_window {total, offset, limit}, GET /imports/{id} takes ?reject_offset/?reject_limit, and the stage-3 table pages through the SERVER. The poll surface was building the whole list with every row's raw cells every two seconds — 4.28 MB on the PO's 9,881-reject run. Measured: a 600-reject run answers 26,401 B where the unbounded list answered 273,302 B, and the payload no longer grows with the reject count at all — 60 rejects 26,392 B, 600 rejects 26,401 B)
//         W2 stage-4/5 lane
// checklist: A✔ B✔ C✔ D✔(all five stages call live endpoints; CR-026's poll
//         proved by a real over-the-bar file walked in a browser) E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest ImportWorkflowPage.test.tsx + ImportWorkflowPage.dom.
//         test.tsx + ImportLoadStage.dom.test.tsx✔ · g13 · g31 (no new
//         stylesheet class) · g38 (the stage-4 stated absence is REMOVED here —
//         stage 4 commits) · g40 (this file is where `Receipt` and
//         `RollbackNotice` are finally mounted; the baseline falls 3 → 1 in the
//         same commit)
// exceptions: E3 **NO STORY OWNS THIS SCREEN — hard-won law 8, reported rather
//         than invented.** B15 §11 lists WFL-01 as new and the epics have not
//         been re-authored; A1 allocates no id · E3 stage 2's SAMPLE VALUE
//         column is empty because stage 1's answer ships no sample row
//         (`DEF-521`) · E3 `Save mapping as template` is disabled with its
//         reason (`DEF-512`) · E3 **stage 5 draws the `/load` response and does
//         not re-read `GET /imports/{id}/receipt`**, because that route is
//         refused by the engine for every loaded run (`DEF-541`) — the payload
//         is identical, so this is a routing detour and not a missing feature ·
//         E3 `Roll back this run` is DISABLED WITH ITS REASON for the same
//         defect: no run in this product can be rolled back today · E3 the
//         kit's `ReceiptProps` requires `finished_label` and `duration_label`
//         and `Receipt.tsx` renders NEITHER — filled from the run's own
//         timestamps rather than from `""`, and REPORTED · E3 the dry run's
//         `unplanned_units` is the server's and is currently wrong for a units
//         run (`DEF-544`); the screen prints what it is served rather than
//         correcting it, because a screen that recomputed a server figure is
//         `DEF-380` · E4 regional formatting uses the SEED defaults
//         (`meteringShared`'s stated posture) because nothing passes this
//         runner regional props and an unwired prop is dead UI (G13) · E3
//         **CR-026: no CANCEL control of any kind, disabled or otherwise —
//         `BR-MET-102` rules it a non-requirement, and the absence is asserted
//         by `ImportProgress.dom.test.tsx` because it is exactly the kind of
//         rule a later well-meaning lane violates by adding a helpful button**
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
