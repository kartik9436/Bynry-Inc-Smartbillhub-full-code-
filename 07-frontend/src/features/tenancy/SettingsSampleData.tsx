// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-019 (EP-TEN-03 — tenant sample data: seed it, tag it, report
//           it, remove it)   Screens: S8 (Settings → Company profile — both
//           actions, BR-TEN-069)
// Rules:    BR-TEN-060 (an unwired seam is a NAMED line, not a skip) ·
//           BR-TEN-063 (idempotent, audited) · BR-TEN-064 (never automatic — a
//           human asks; the job runs in production) · BR-TEN-066 (removal is
//           partial-and-named) · BR-TEN-069 (BOTH actions live on Company
//           profile) · BR-SHL-020 (the six A18 states, composed not rebuilt) ·
//           BR-SHL-025 (a control this role may not use renders disabled WITH
//           its reason) · CLAUDE.md rule 7 (the write is audited server-side)
// ───────────────────────────────────────────────────────
// S8 → Company profile → **Sample data**: the provisioning follow-up a newly
// signed-up operator performs, and the first screen that can reach
// `apps/tenancy/sample_data.py`.
//
// WHY THIS SCREEN IS MOSTLY A REPORT
// -----------------------------------
// The orchestrator shipped 2026-08-15 complete, tested and unreachable —
// `E=deferred(no-frontend-half)` and no API half either. It is honest in a way
// that is easy to destroy from the UI side: every module in the sample set
// resolves to `skipped / seam_not_wired`, so a seed run creates ZERO rows.
//
// A screen over that has exactly one hard job, and it is the reason this file
// exists rather than a button: **render the reasons, never the zero.** The
// three ways to get it wrong were all available and all rejected:
//
//   1. a toast saying "Sample data loaded ✓" — the DEF-016 sentence, which is
//      how four empty Settings cards reached a live deployment;
//   2. a "0 records" counter — the DEF-127 shape, a zero standing in for
//      "I don't know", indistinguishable from a tenant that never asked;
//   3. an empty table with "no sample data" — which reads as an ANSWER.
//
// So the panel renders one line per module carrying the module's own
// `detail` sentence from the server, and the summary line says
// "nothing was loaded" whenever `succeeded` is false. `has_run` is what keeps
// the two zeros apart: a tenant that never pressed the button sees the
// never-asked state, not a report of nothing.
//
// WHY THE COUNT IS SAFE TO SHOW AND THE REPORT IS NOT OPTIONAL
// -------------------------------------------------------------
// `seeded_total` IS rendered, but only underneath the per-module lines and only
// once `has_run` is true — it is a MEASURED figure at that point (the run
// enumerated five blocks and recorded what each did), not a cache nothing
// filled. The distinction this whole release turns on is not "never show a
// zero"; it is "never show a zero that means I don't know".
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getSampleDataReport,
  removeSampleData,
  retrySampleDataBlock,
  seedSampleData,
} from "@/api/endpoints";
import type { SampleDataBlock, SampleDataBlocked, SampleDataReport } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { FailedWithRetry, LoadingSkeleton, WorkingButton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { Note } from "@/components/TextBits";

import { Panel, RefusalNotice, apiErrorText, isPermissionDenied, refusalOf } from "./settingsShared";
import type { Refusal, Translator } from "./settingsShared";

export const sampleDataQueryKey = ["settings", "sample-data"] as const;

/**
 * One module's line. `detail` is the SERVER's sentence, rendered verbatim.
 *
 * It is deliberately not translated and deliberately not summarised: it names
 * the exact seam function and the exact tables that need BR-TEN-057's column,
 * which is what makes the line actionable rather than decorative. A translated
 * paraphrase would drift from the code it names the moment either moved. The
 * LABELS around it are translated; the diagnostic is not, and this comment is
 * the record of that being a decision rather than an omission.
 */
function ModuleLine(props: { row: SampleDataBlocked; outcomeLabel: string }) {
  return (
    <li className="settings-sample-row">
      <span className="settings-sample-module">{props.row.label}</span>
      <span className="settings-sample-outcome">{props.outcomeLabel}</span>
      {props.row.detail !== null && props.row.detail !== "" && (
        <span className="settings-sample-detail" role="note">
          {props.row.detail}
        </span>
      )}
    </li>
  );
}

/**
 * ONE BLOCK's line — CR-039 wave B task 6, and the reason this panel changed.
 *
 * WHAT WAS MISSING, PRECISELY. The lines above are per MODULE, because
 * `sample_data_runs` is keyed that way (BR-TEN-060). **THIRTEEN of the sixteen
 * blocks share a module with another** — payments has four, and metering,
 * customers and billing have three each — so their outcomes were reconciled
 * worst-first into one verdict and the screen could not say WHICH of them
 * broke. The Product Owner's question was exactly that: *"we need to look at
 * what of 1 job fails and does not load the data"*.
 *
 * ⚠ **THIS SENTENCE HAS NOW BEEN STALE TWICE, AND THAT IS THE POINT OF THE
 * WARNING RATHER THAN AN ASIDE.** It read *"Four of the eleven blocks"* until
 * 2026-08-27, when CR-040 waves C and D added a refund block, a correction
 * block and a second billing block; it read *"ELEVEN of the fourteen … metering
 * has two"* until 2026-09-01, when the PO's third-cycle step added metering's
 * walk and payments' second-cycle collections. Both times a comment claiming a
 * measurement went on claiming it (hard-won law 1) while the figures above it —
 * counted off `SAMPLE_MODULES` at render time — moved underneath.
 * `test_cr040_e17_seeding_panel_blocks.py` holds a ratchet over the STRUCTURE
 * (no duplicate keys, every block declared as a root or with an edge) and over
 * no number in this paragraph, which is why the paragraph can go stale at all.
 *
 * THREE THINGS EACH LINE CARRIES, and each answers a different question:
 *
 *   1. **the count** — what this block actually wrote, this run. A seeded block
 *      showing 0 is not a bug: the seeders are insert-what-is-missing, so a
 *      replay honestly writes nothing;
 *   2. **the code** — `SD-…`, small and monospaced, for a support conversation
 *      and for counting across tenants. The sentence is for the person;
 *   3. **root or consequence** — because one early failure produces a cascade
 *      of dependent failures, each honest, and five reds for one cause is not a
 *      report an operator can act on. A CONSEQUENCE line names the block that
 *      actually broke.
 */
function BlockLine(props: {
  row: SampleDataBlock;
  t: Translator;
  onRetry?: (row: SampleDataBlock) => void;
  retrying: boolean;
  readOnly: boolean;
}) {
  const { row, t } = props;
  const seeded = row.outcome === "seeded";
  const isRoot = row.failure_class === "root";
  return (
    <li
      data-block={`${row.module}:${row.block}`}
      data-outcome={row.outcome}
      data-failure-class={row.failure_class ?? ""}
      className="flex flex-col gap-1 border-b border-divider py-2 last:border-b-0"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-medium text-neutral-900">{row.label}</span>
        <span className={seeded ? "text-sm text-success-700" : "text-sm text-danger-700"}>
          {t(`settings.sampleData.outcome.${row.outcome}`)}
        </span>
        <span className="text-sm text-neutral-700">
          {t("settings.sampleData.block.rows", { count: row.count })}
        </span>
        {row.error_code !== null && row.error_code !== "" && (
          <span className="font-mono text-xs uppercase tracking-wide text-neutral-600">
            {row.error_code}
          </span>
        )}
        {/* The whole point of the cascade marking: ROOT is the line to read
            first, and a CONSEQUENCE says whose consequence it is. */}
        {isRoot && (
          <span className="border border-danger-500 px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-danger-700">
            {t("settings.sampleData.block.root")}
          </span>
        )}
        {row.failure_class === "consequence" && (
          <span className="text-xs text-neutral-600">
            {t("settings.sampleData.block.consequence", {
              root: row.root_label ?? row.root_block ?? "",
            })}
          </span>
        )}
      </div>
      {row.detail !== null && row.detail !== "" && (
        // The SERVER's sentence, verbatim and untranslated — it names the exact
        // seam function and the exact tables, which is what makes it actionable.
        // B14 rule 18 (CR-041 task 5): the `--desc-measure` token's utility,
        // `max-w-measure`. NOT `max-w-prose`, which is a real Tailwind utility
        // and the WRONG cap — `65ch` against a rule written as 80% (DEF-900).
        <span className="max-w-measure text-sm text-neutral-700" role="note">
          {row.detail}
        </span>
      )}
      {!seeded && row.retryable && (
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            disabled={props.readOnly || props.retrying}
            title={props.readOnly ? t("settings.readOnlyReason") : undefined}
            onClick={props.onRetry === undefined ? undefined : () => props.onRetry?.(row)}
          >
            {props.retrying
              ? t("settings.sampleData.block.retrying")
              : t("settings.sampleData.block.retry")}
          </Button>
          {/* Said on the line rather than learned by pressing it: retrying a
              consequence before its root is fixed will fail again. */}
          {row.failure_class === "consequence" && (
            <span className="text-xs text-neutral-600">
              {t("settings.sampleData.block.retryRootFirst")}
            </span>
          )}
        </div>
      )}
    </li>
  );
}

/**
 * The report body. Split out so the never-asked state and the after-a-run state
 * are visibly two different renders rather than one render with a falsy branch
 * — the bug this feature is guarding against is precisely the two collapsing.
 */
export function SampleDataReportBody(props: {
  report: SampleDataReport;
  t: Translator;
  onRetry?: (row: SampleDataBlock) => void;
  retryingBlock?: string | null;
  readOnly?: boolean;
}) {
  const { report, t } = props;

  if (!report.has_run) {
    // NEVER ASKED. No counts at all, because there is nothing to count — an
    // operator who has not pressed the button has not been told anything.
    return (
      <p className="settings-sample-never" role="note">
        {t("settings.sampleData.neverRun")}
      </p>
    );
  }

  return (
    <>
      {/* BR-TEN-056 clause 3, as the FIRST thing read: a run with any skip does
          not report success, and the headline says so before any number. */}
      <p
        className={report.succeeded ? "settings-sample-ok" : "settings-sample-nothing"}
        role="note"
      >
        {report.succeeded
          ? t("settings.sampleData.loaded", { count: report.seeded_total })
          : t("settings.sampleData.nothingLoaded")}
      </p>
      {/* CR-039 wave B: the BLOCK lines when the run recorded them, the module
          lines when it did not. Never both — two lists over one ledger read as
          two different answers, and the finer one is the answer.

          ⚠ `blocks_recorded === false` with `has_run === true` is a real state
          and NOT an empty list: the run predates block-level reporting. Saying
          so is the DEF-127 posture one level down — a blank list would read as
          "this tenant has no blocks", which is a zero standing in for "I don't
          know". */}
      {report.blocks !== undefined && report.blocks.length > 0 ? (
        <ul className="m-0 list-none p-0">
          {report.blocks.map((row) => (
            <BlockLine
              key={`${row.module}:${row.block}`}
              row={row}
              t={t}
              onRetry={props.onRetry}
              retrying={props.retryingBlock === `${row.module}:${row.block}`}
              readOnly={props.readOnly === true}
            />
          ))}
        </ul>
      ) : (
        <>
          <ul className="settings-sample-list">
            {report.modules.map((row) => (
              <ModuleLine
                key={`${row.module}-${row.outcome}`}
                row={row}
                outcomeLabel={t(`settings.sampleData.outcome.${row.outcome}`)}
              />
            ))}
          </ul>
          <Note>{t("settings.sampleData.block.notRecorded")}</Note>
        </>
      )}
      {/* BR-TEN-060: these lines are advisory and never count toward the S62
          checklist — said on the screen, because an operator being shown red
          lines will otherwise reasonably assume their setup is incomplete. */}
      {!report.counts_toward_progress && (
        <Note>{t("settings.sampleData.advisory")}</Note>
      )}
    </>
  );
}

export interface SampleDataPanelProps {
  /** BR-SHL-025: a role with view-only on this cell gets both buttons disabled
   *  WITH the reason, never a vanished control. */
  readOnly: boolean;
  client?: ApiClient;
}

/**
 * BR-TEN-069: BOTH actions on Company profile, in one panel with the report
 * they act on — a "Load sample data" button somewhere else on the page from the
 * lines saying it loaded nothing is how the two get read separately.
 */
export function SampleDataPanel(props: SampleDataPanelProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const toast = useToast();

  const reportQuery = useQuery({
    queryKey: sampleDataQueryKey,
    queryFn: () => getSampleDataReport(client),
    retry: false,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: sampleDataQueryKey });
  };

  // US-SHL-012 TC-4: a FAILURE never fires a toast — it renders an A18 §4/§5
  // state. Both mutations therefore route their error into one inline refusal
  // and fire a toast only on a committed action.
  const seed = useMutation({
    mutationFn: () => seedSampleData(client),
    onSuccess: (report) => {
      invalidate();
      // THE TOAST TELLS THE TRUTH OR IT SAYS NOTHING GOOD. A success toast over
      // a run that seeded nothing is DEF-016 in one line of copy — a summary
      // nobody read reporting success over a seam that had never been written.
      toast(
        report.succeeded
          ? t("settings.sampleData.toast.loaded", { count: report.seeded_total })
          : t("settings.sampleData.toast.nothingLoaded"),
      );
    },
  });

  // CR-039 wave B task 8. Today the whole plant can be re-run and a single
  // failed block cannot — so an operator who fixed one named cause ("add a bill
  // template") had to re-walk all eleven blocks to find out whether it worked.
  //
  // `variables` is what tells the line which button is working: the mutation is
  // shared by every block, and marking them all busy would say we are running
  // eleven seeders when we are running one.
  const retry = useMutation({
    mutationFn: (row: SampleDataBlock) => retrySampleDataBlock(row.module, row.block, client),
    onSuccess: (result) => {
      invalidate();
      // The SAME rule the seed toast follows: a toast tells the truth or it says
      // nothing good. "Retried ✓" over a block that failed again is DEF-016 in
      // one line of copy.
      toast(
        result.block.outcome === "seeded"
          ? t("settings.sampleData.toast.blockRetried", {
              label: result.block.label,
              count: result.block.count,
            })
          : t("settings.sampleData.toast.blockStillFailing", { label: result.block.label }),
      );
    },
  });

  const remove = useMutation({
    mutationFn: () => removeSampleData(client),
    onSuccess: (outcome) => {
      invalidate();
      toast(
        outcome.removed > 0
          ? t("settings.sampleData.toast.removed", { count: outcome.removed })
          : t("settings.sampleData.toast.nothingRemoved"),
      );
    },
  });

  const refusal: Refusal | null =
    seed.error !== null
      ? refusalOf(seed.error, translate)
      : remove.error !== null
        ? refusalOf(remove.error, translate)
        : retry.error !== null
          ? refusalOf(retry.error, translate)
          : null;

  // A18 §6 — this tab's own GET answered 403. The panel says so and offers
  // neither button, because the server would refuse both.
  if (reportQuery.isError && isPermissionDenied(reportQuery.error)) {
    return (
      <Panel title={t("settings.sampleData.title")} hint={t("settings.sampleData.hint")}>
        <p className="settings-readonly" role="note">
          {t("settings.sampleData.denied")}
        </p>
      </Panel>
    );
  }

  if (reportQuery.isError) {
    return (
      <Panel title={t("settings.sampleData.title")} hint={t("settings.sampleData.hint")}>
        <FailedWithRetry
          title={t("settings.sampleData.failedTitle")}
          reason={apiErrorText(reportQuery.error, translate)}
          onRetry={() => void reportQuery.refetch()}
          onDownloadReport={() => undefined}
          onCancel={() => void reportQuery.refetch()}
        />
      </Panel>
    );
  }

  // ⚠ A RETRY IS DELIBERATELY NOT PART OF `working`. `working` disables the two
  // whole-plant buttons, and one block re-running is not a reason to stop an
  // operator loading or removing the set — but it IS a reason to disable that
  // one block's own button, which `retryingBlock` does instead.
  const working = seed.isPending || remove.isPending;
  const retryingBlock =
    retry.isPending && retry.variables !== undefined
      ? `${retry.variables.module}:${retry.variables.block}`
      : null;

  return (
    <Panel title={t("settings.sampleData.title")} hint={t("settings.sampleData.hint")}>
      {reportQuery.isPending || reportQuery.data === undefined ? (
        <LoadingSkeleton variant="card" />
      ) : (
        <SampleDataReportBody
          report={reportQuery.data}
          t={translate}
          onRetry={(row) => retry.mutate(row)}
          retryingBlock={retryingBlock}
          readOnly={props.readOnly}
        />
      )}

      <RefusalNotice refusal={refusal} />

      <div className="settings-sample-actions">
        {props.readOnly ? (
          <>
            <Button variant="primary"  disabled title={t("settings.readOnlyReason")}>
              {t("settings.sampleData.seed")}
            </Button>
            <Button variant="ghost"  disabled title={t("settings.readOnlyReason")}>
              {t("settings.sampleData.remove")}
            </Button>
            <span className="settings-readonly">{t("settings.readOnlyReason")}</span>
          </>
        ) : (
          <>
            <WorkingButton working={working} onClick={() => seed.mutate()}>
              {t("settings.sampleData.seed")}
            </WorkingButton>
            <Button
              variant="ghost"
              disabled={working}
              onClick={() => remove.mutate()}
            >
              {t("settings.sampleData.remove")}
            </Button>
          </>
        )}
      </div>

      {/* BR-TEN-064, stated rather than assumed: this runs in production, on
          request, and nothing schedules it. An operator pressing a button on a
          live tenant deserves to know which of those is true. */}
      <Note>{t("settings.sampleData.onRequest")}</Note>
    </Panel>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-019@c3b7d18 (EP-TEN-03 — the S8 surface half of the sample-data orchestrator; the engine and its honest report shipped 2026-08-15 with no API and no screen)
// generated: 2026-08-16 by story-coder (unreachable-screens lane — G23/DEF-112 surface debt)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — not a 🔒 path: no money figure, threshold or key is authored here; the panel renders counts the server measured and writes nothing)
// gates: see the lane report
// exceptions: (1) THE PER-MODULE `detail` SENTENCE IS RENDERED UNTRANSLATED, deliberately — it names the exact seam function (`apps.metering.services.seed_sample_records`) and the exact tables needing BR-TEN-057's column, which is what makes the line actionable; a translated paraphrase would drift from the code it names. Every LABEL around it goes through the catalogues. Reported as a deliberate divergence from the usual all-strings-translated posture rather than an i18n gap · (2) parts 1-3 of US-TEN-019 (the sample RECORDS, the `is_sample` tag, the removal itself) remain unbuilt and cannot be built from tenancy — this screen is the surface over part 4, the honest report, and it renders the other three as the named absences they are · (3) no confirm dialog on Remove: it removes nothing today and a modal asking a user to confirm a no-op teaches the wrong thing about the button. When the owning modules publish `remove_sample_records` the removal becomes destructive and this line is where the next lane learns a confirm step is then owed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
