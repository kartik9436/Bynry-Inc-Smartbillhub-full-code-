// ── Trace ──────────────────────────────────────────────
// Story:    (none yet — hard-won law 8 is REPORTED in the mounting screens'
//           trailers) Change: CR-026 second half, the FRONTEND (PO 2026-08-22:
//           *"In Premises and Unit import - the sizes of CSV file scan be
//           50,000 or 100,000 units or premises at a time; how you will hnadle
//           such volume in upload"*)
//           Screens: WFL-01.premises.2-4 (the stage rail), PRM-04 (the run table)
// Rules:    BR-MET-085 (the figures on screen are the SERVER's — nothing here
//           counts, divides or estimates) · BR-MET-090 (the gauge is NOT the
//           run's record; a receipt never reads it) · BR-MET-102 (a running
//           import CANNOT be cancelled and this draws NO cancel control, not
//           even a disabled one) · BR-SHL-025 (a control that cannot act says
//           why — and BR-MET-102 is why that rule does NOT apply here) ·
//           B14 rule 21 (Tailwind, no new stylesheet class)
// Impacts:  ImportWorkflowPage.tsx (the stage rail's panel) ·
//           PremisesImportsTab.tsx (the run table's cell)
// ───────────────────────────────────────────────────────
// HOW A BACKGROUND IMPORT STAGE SAYS HOW FAR IT HAS GOT — CR-026's screen half.
//
// ⚠ **A SMALL FILE MUST LOOK EXACTLY AS IT DID YESTERDAY.** `run_dict` serves
// `progress: null` for every synchronous run, and every function here answers
// `null` on `null`: no panel, no bar, no cell, no extra sentence. A three-row
// import that suddenly grew a progress bar would be a regression, and it is the
// one thing this file is most able to break — which is why the `null` branch is
// the FIRST line of both components rather than a condition at the call site.
//
// ⚠ **EVERY NUMBER DRAWN HERE ARRIVED FROM THE SERVER, INCLUDING THE
// PERCENTAGE.** `import_progress.read` computes `pct` itself and states why:
// *"two clients would otherwise each divide by zero their own way on a 0-row
// file"*. So this file never writes `done / total`, and when the server sends
// `pct: null` (a stage with no denominator) it draws NO BAR — a bar at an
// invented width is a claim about a length nobody measured. That is BR-MET-085's
// discipline moved from the file hash to the counts.
//
// ⚠ **THERE IS NO CANCEL CONTROL HERE AND THERE IS NOT MEANT TO BE
// (`BR-MET-102`, PO 2026-08-22, verbatim: *"No"*).** A 100,000-row load runs
// for minutes in a worker and an operator who started the wrong file cannot
// stop it. That is a RULED NON-REQUIREMENT, not an unbuilt feature, so
// `BR-SHL-025`'s *"disabled WITH its reason"* — which exists for a control that
// cannot act YET — deliberately does not apply: a greyed-out Cancel would
// invite someone to sit and wait for it to light up. Draw nothing. What the
// panel draws INSTEAD is the door the rule names: the run finishes and its
// receipt offers the rollback, which deactivates everything the run loaded and
// deletes nothing. The anxiety a cancel button would have served is answered by
// telling the operator, while they watch, that the exit exists.
import { useTranslation } from "react-i18next";

import type { ImportProgress } from "@/api/endpoints";

/**
 * How often a screen asks *"how far?"*.
 *
 * Two seconds, and the figure is the SERVER's own arithmetic read back at it:
 * `import_progress` throttles the gauge to one write per 1,000 rows AND per
 * second, so a poll faster than a second cannot learn anything new and a poll
 * much slower than that makes a 100,000-row load look frozen. `read_run` is a
 * cheap read that writes nothing — `import_run_detail`'s docstring says *"a
 * screen asking 'how far?' every two seconds is not an event; that is also why
 * it must stay cheap enough to be asked that often"*.
 */
export const IMPORT_POLL_INTERVAL_MS = 2_000;

// ══════════════════════════════════════════════════════════════════════════
// CR-045 WAVE D · D.13–D.15 (DEF-1702) — THE THREE IMPORTS TABS' FILTER
// VOCABULARY, DEFINED ONCE
//
// AST-04, S81 and PRM-04 are three instantiations of ONE run table over ONE
// endpoint (BR-MET-096's one runner), and each tab's own trailer already
// REPORTS that they are copies rather than an extraction. This is the part of
// them that must not be copied: a status word or a target code spelled
// differently on one tab is a filter that silently answers "none".
//
// ⚠ **THE VALUES ARE THE SERVER'S OWN STRINGS.** `models.IMPORT_RUN_STATUSES`
// for the six statuses and `import_runs.TARGETS` for the six targets;
// `run_list` compares them with `=`, so a near-miss returns an empty list and
// reads as "you have never imported anything".
//
// ⚠ **AND EVERY LABEL BELOW ALREADY EXISTS IN ALL ELEVEN CATALOGUES.** The
// statuses are the pills the Status column already draws
// (`metering.imports.status.*`) and the targets are the words the workflow
// already names (`workflow.<target>.target`), so re-labelling them here would
// be a second vocabulary that can drift from the one on screen — the DEF-388
// shape. Only the two GROUP headings are new keys.

/** The six statuses a run can hold, in lifecycle order — `extracted` through
 *  the three terminal ones. Not a `Set`: order is what a filter panel shows. */
export const IMPORT_RUN_STATUS_CODES = [
  "extracted",
  "transformed",
  "validated",
  "loaded",
  "failed",
  "rolled_back",
] as const;

/** The six upload targets, in `import_runs.TARGETS` order. PRM-04 offers all
 *  six (it lists every target); AST-04 offers its own three; S81 offers none,
 *  because it is scoped to `accounts` and a one-option filter changes nothing
 *  — that scope is sent as a fixed `f.target` instead of drawn as a choice. */
export const IMPORT_TARGET_CODES = [
  "premises",
  "units",
  "assets_meters",
  "assets_submeters",
  "assets_devices",
  "accounts",
] as const;

/** `{ value, label }` for a subset of the run statuses, translated. */
export function importStatusFilterOptions(
  t: (key: string) => string,
  codes: readonly string[] = IMPORT_RUN_STATUS_CODES,
): { value: string; label: string }[] {
  return codes.map((code) => ({ value: code, label: t(`metering.imports.status.${code}`) }));
}

/** `{ value, label }` for a subset of the upload targets, translated. */
export function importTargetFilterOptions(
  t: (key: string) => string,
  codes: readonly string[] = IMPORT_TARGET_CODES,
): { value: string; label: string }[] {
  return codes.map((code) => ({ value: code, label: t(`workflow.${code}.target`) }));
}

/** The three stages that can be handed to a worker (`STAGE_JOBS`). */
export type DeferredStage = "transform" | "validate" | "load";

/** `import_progress`'s own stage names → this screen's wording. */
const STAGE_LINE_KEY: Record<string, string> = {
  transform: "metering.import.progress.transform",
  validate: "metering.import.progress.validate",
  load: "metering.import.progress.load",
};

/** The compact form the run table's cell uses. */
const STAGE_SHORT_KEY: Record<string, string> = {
  transform: "metering.import.progress.shortTransform",
  validate: "metering.import.progress.shortValidate",
  load: "metering.import.progress.shortLoad",
};

/**
 * A count, grouped the way the reader's locale groups counts.
 *
 * r10's own sentence is *"Validating… 62,000 of 100,000"* — the separators are
 * the point of the example, because six unbroken digits are the difference
 * between a figure and a smear. `toLocaleString` and not a hand-rolled regex:
 * the eleven catalogues do not all group in threes.
 */
function grouped(value: number): string {
  return value.toLocaleString();
}

/**
 * The one sentence both surfaces draw, built from the gauge and nothing else.
 *
 * ⚠ A stage this map has not met renders its own SERVER NAME rather than a
 * blank — the same posture `RULE_ACTION_KEY` takes one file over, and for the
 * same reason: `STAGE_JOBS` gains a target every time BR-MET-096's runner does,
 * and an empty progress line is worse than an untranslated one.
 */
export function importProgressLine(
  progress: ImportProgress,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  if (progress.state === "failed") {
    return progress.message === null || progress.message === ""
      ? t("metering.import.progress.failedNoMessage")
      : t("metering.import.progress.failed", { message: progress.message });
  }
  if (progress.state === "queued") return t("metering.import.progress.queued");
  const key = STAGE_LINE_KEY[progress.stage];
  if (key === undefined) {
    return t("metering.import.progress.rowsDone", { done: grouped(progress.done) });
  }
  if (progress.total === null) {
    return t("metering.import.progress.rowsDone", { done: grouped(progress.done) });
  }
  return t(key, { done: grouped(progress.done), total: grouped(progress.total) });
}

/**
 * **THE STAGE RAIL'S PROGRESS PANEL.** Drawn only while a stage is in a worker;
 * `null` in, nothing out.
 */
export function ImportProgressPanel({ progress }: { progress: ImportProgress | null }) {
  const { t } = useTranslation();
  // ⚠ THE SYNCHRONOUS RUN, FIRST LINE: a file under `ASYNC_ROW_BAR` has no
  // gauge and must show nothing new at all.
  if (progress === null) return null;

  const pct = progress.pct;
  const failed = progress.state === "failed";
  return (
    <section
      className="flex flex-col gap-2 bg-surface p-3"
      data-workflow="progress"
      data-progress-stage={progress.stage}
      data-progress-state={progress.state}
    >
      <p
        className="m-0 text-base font-bold tabular-nums"
        data-workflow="progress-line"
        aria-live="polite"
      >
        {importProgressLine(progress, t)}
      </p>

      {/* ⚠ NO BAR WITHOUT A DENOMINATOR. `pct` is `null` exactly when the
          server could not divide, and a bar drawn anyway would be a width
          nobody measured. The figure itself is never recomputed here. */}
      {pct !== null && !failed && (
        <div
          className="h-[6px] w-full overflow-hidden bg-[color-mix(in_srgb,var(--color-text)_12%,transparent)]"
          role="progressbar"
          aria-label={t("metering.import.progress.barLabel")}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          data-workflow="progress-bar"
        >
          <div className="h-[6px] bg-accent" style={{ width: `${pct}%` }} />
        </div>
      )}
      {pct !== null && !failed && (
        <p className="m-0 text-sm tabular-nums" data-workflow="progress-pct">
          {t("metering.import.progress.pct", { pct })}
        </p>
      )}

      {/* Why this run is not answering in the browser, and where the operator
          may go instead — the run table is the come-back-later surface and
          says so on the screen that makes them want one. */}
      {!failed && (
        <p className="m-0 max-w-measure text-sm leading-body text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {t("metering.import.progress.background")}
        </p>
      )}

      {/* ⚠ **BR-MET-102 — THIS PARAGRAPH IS WHAT REPLACES A CANCEL BUTTON.**
          There is no cancel and there is no disabled cancel; there is the
          ruled rollback, named here so the operator watching the wrong file
          load can see the exit before they need it. The window itself is NOT
          typed here — `import_runs.ROLLBACK_DAYS` owns the number and the
          receipt words it from the server's own date (the same posture
          `receiptDataOf` takes). A screen that typed "30 days" would be the
          screen making the promise. */}
      {!failed && (
        <p className="m-0 max-w-measure text-sm leading-body text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]"
          data-workflow="no-cancel"
        >
          {t("metering.import.progress.noCancel")}
        </p>
      )}
    </section>
  );
}

/**
 * **THE RUN TABLE'S CELL** — one in-flight run, made legible on the surface an
 * operator comes back to. Compact on purpose: the sentence the panel draws is
 * a paragraph and this is a column.
 */
export function ImportProgressCell({ progress }: { progress: ImportProgress | null }) {
  const { t } = useTranslation();
  // The em-dash every other absent cell in this table uses. A run that never
  // deferred has no gauge and never will (`import_progress`'s `NullReporter`).
  if (progress === null) return <span>—</span>;
  if (progress.state === "failed") {
    return <span data-progress-state="failed">{t("metering.imports.progress.stopped")}</span>;
  }
  if (progress.state === "queued") {
    return <span data-progress-state="queued">{t("metering.imports.progress.queued")}</span>;
  }
  const short = STAGE_SHORT_KEY[progress.stage];
  const label = short === undefined ? progress.stage : t(short);
  return (
    <span className="tabular-nums" data-progress-state={progress.state}>
      {progress.pct === null
        ? t("metering.imports.progress.cellNoPct", { stage: label, done: grouped(progress.done) })
        : t("metering.imports.progress.cell", { stage: label, pct: progress.pct })}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-026 second half — the frontend (12-governance/11-change-requests.md
//         §CR-026; backend contract in 06-backend/apps/metering/import_progress.py
//         and import_runs.run_dict) + BR-MET-102 (PO ruling 2026-08-22)
// generated: 2026-08-22 by the CR-026 closure lane
// checklist: A✔ B✔ C✔ D✔ E✔(mounted by ImportWorkflowPage and
//         PremisesImportsTab in the same commit — G40) F✔ G✔
//         H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest ImportProgress.dom.test.tsx✔ · g31/routeBUtilities (this
//         file is added to route-b-migrated.txt in the same commit) · g40
// exceptions: E3 the panel names the rollback WITHOUT its window, because
//         `ROLLBACK_DAYS` is the server's number and the receipt already words
//         the expiry from the server's own date · E3 no CANCEL control of any
//         kind is drawn, disabled or otherwise — BR-MET-102, and that is the
//         rule this file is most likely to have quietly violated later, which
//         is why a test asserts the absence
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
