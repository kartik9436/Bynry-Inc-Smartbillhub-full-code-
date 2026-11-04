// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-008 (EP-SHL-02 — CSV export: the ONE Download control every
//           list screen fills its capability-row slot with) · US-MET-001 (S14) ·
//           US-MET-002 (S15) · US-MET-005 (S26/S27) · US-AST-001 (S49) ·
//           US-RAT-001 (S9 plans) · US-RAT-008 (charge codes) · US-RAT-009
//           (taxes & fees) · US-RAT-010 (rate-change history)
//           Screens: S14 · S15 · S26 · S27 · S49 · S9
// Rules:    BR-SHL-016 (the export runs SERVER-side under the caller's tenant
//           context; >50,000 rows refused; money exports write audit_log — none
//           of it re-implemented here) · BR-SHL-029 (the cap is the server's
//           number, rendered in the server's words) · BR-SHL-011 (the export
//           posts the list's CURRENT q/sort/dir/f.‹name› state) · BR-SHL-010
//           (the capability row IS the config: a screen that declares no export
//           renders no button) · BR-SHL-020 (the six A18 states, never a
//           bespoke spinner) · IS-11 (CSV always; XLSX has no prop to ask with)
// ───────────────────────────────────────────────────────
// The ONE export control (LAW 0). Nine list screens fill their DataTable
// `downloadSlot` — or their page header, for the two ops views that predate
// DataTable — with this component and nothing else.
//
// What it does, and just as importantly what it refuses to do:
//
//   1. **It posts the list's CURRENT request state**, unchanged: the same
//      TableRequestState the table is rendering, translated once by
//      `exportBodyFrom`. It never re-reads the URL, never re-derives filters,
//      and never adds one the screen is not showing — an export that did not
//      match the list would be worse than no export.
//
//   2. **It counts nothing.** The 50,000-row cap is measured server-side
//      against the same bounded query (BR-SHL-016/029); an oversize request
//      comes back 422 BIZ-CAP carrying the real count and the cap, and this
//      control renders the server's own sentence with those numbers.
//
//   3. **It adds no second poller.** A 202 is a job, and the client has ONE
//      job poller (`client.pollJob`, 11b §2.17) — the same one the S61 audit
//      export uses. This file starts no interval and holds no timer.
//
//   4. **It cannot ask for XLSX.** IS-11 forbids it in v1, and FE-14's
//      DownloadButton exposes no prop that could request it. That is
//      structural: there is nothing here to review each release.
//
// **Why S61 is not one of these nine.** The audit-log export is a DIFFERENT
// resource with a different rule (`POST /audit-log/export`, BR-AUD-014, its own
// hot/archive window and its own catalog sentence), so it keeps the control it
// already has. What is shared is what should be: the DownloadButton, the job
// poller, and the 202 contract. Folding S61 into this registry would mean
// giving an audit trail a list resource it does not have.
//
// **The completed state hands over the file.** `result_link` is the IS-11
// download route the server now serves (`GET /api/exports/{job_id}/file` — a
// PLATFORM path, un-tenanted like the job poller under the PO's 2026-08-10
// ruling), so a finished export renders a real anchor and
// the browser fetches the CSV with the filename the server put in
// Content-Disposition. Nothing here builds that URL: it is whatever the poll
// answered, so the day the artifact moves to an object store this file does
// not change. A job that finished with no link still SAYS so rather than
// rendering a dead one.
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { serverLinkHref } from "@/api/apiHref";
import { api } from "@/api/client";
import type { ApiClient, JobRecord } from "@/api/client";
import { requestListExport } from "@/api/endpoints";
import type { ExportResource } from "@/api/endpoints";
import { DownloadButton } from "@/components/DownloadButton";
import type { TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";


/** BR-SHL-011: the table's own state → the ratified POST /exports body. */
export function exportBodyFrom(resource: ExportResource, state: TableRequestState | null) {
  if (state === null) {
    // S26/S27 predate the table framework and carry no request state (their
    // endpoints are unpaginated plain arrays — the reported gap). An empty
    // body exports the whole list, which is exactly what those tabs show.
    return { resource, filters: {}, sort: null, dir: null, q: "" };
  }
  return {
    resource,
    filters: state.filters,
    sort: state.sort,
    dir: state.dir,
    q: state.q,
  };
}

/*
 * ⛔ **`exportCapRefusal` WAS HERE AND IS DELETED — `P2.4` (`CR-142-BRC07`,
 * 2026-09-26).** It rendered *"That's 62000 rows — more than the 50000 an
 * export can carry. Narrow your filters and try again."* from a 422 BIZ-CAP
 * the server no longer sends: `EXPORT_ROW_CAP` is gone and `NFR-5` forbids
 * putting one back, so **no list export is refused for being large**.
 *
 * DELETED rather than reworded, because B14 rule 33 puts rationale at ZERO
 * words on screen and a refusal that outlives what it refused over is
 * hard-won law 2's mirror — a live screen behind a dead control. The two keys
 * it spelled, `exports.capped` and `exports.row_cap_exceeded`, are retired
 * from all eleven catalogues through `10-scripts/i18n_fanin.py`.
 *
 * ⚠ **THE AUDIT EXPORT KEEPS ITS OWN, AND THAT IS NOT AN OVERSIGHT.**
 * `apps/audit/services.py` still caps at 50,000 under `BR-AUD-014` — another
 * module's rule, another module's to move — so `AuditLogPage.exportCapRefusal`
 * and `audit.export.capped` stay live and still fire.
 */

/**
 * The download the server left behind, or null.
 *
 * The ONE place either export screen decides "is there a file to fetch?" —
 * S61 imports it rather than re-reading `result_link` its own way (LAW 0).
 * Only a SUCCEEDED job can have one: a queued, running or failed job has
 * nothing to hand over, and the route would answer 404 anyway (HR-1).
 */
export function exportDownloadHref(job: JobRecord): string | null {
  if (job.status !== "succeeded") {
    return null;
  }
  const link = job.result_link;
  return link === null || link === "" ? null : serverLinkHref(link);
}

/**
 * The exception kinds whose message the SERVER wrote as a plain sentence for
 * a clerk (`DEF-TEN-9190`): `ExportNotStored` (`apps/tenancy/export_store.py`,
 * `plain_reason` — e.g. *"File storage did not answer."*) and `ExportStalled`
 * (`apps/tenancy/export_sweep.py`, `STALLED_ERROR`). Both list exports and the
 * print set are published through that one store, so both screens read this.
 */
const PLAIN_REASON_KINDS = ["ExportNotStored", "ExportStalled"] as const;

/**
 * Why a failed export failed, as the server's own plain sentence, or null.
 *
 * PO 2026-10-02 (decision log *"SEVEN PO ANSWERS IN ONE MESSAGE"* item 7): a
 * failed export shows its reason — *"The export didn't finish. File storage
 * did not answer."* A job's `error` is `Type: message` for ANY exception
 * (`core.jobs.failure_text`), so only the kinds above are shown: a crash's own
 * text (`KeyError: 'premise_no'`) is a diagnosis for support, never a sentence
 * for a clerk (B14 rule 32 — no internal code on screen). Anything else keeps
 * the generic sentence.
 */
export function exportFailureReason(job: JobRecord): string | null {
  if (job.status !== "failed" || job.error === null || job.error === undefined) {
    return null;
  }
  for (const kind of PLAIN_REASON_KINDS) {
    const prefix = `${kind}: `;
    if (job.error.startsWith(prefix)) {
      const reason = job.error.slice(prefix.length).trim();
      return reason === "" ? null : reason;
    }
  }
  return null;
}

export interface ExportOutcome {
  message: string;
  ok: boolean;
  /** The IS-11 download route, or null when there is nothing to link to. */
  href: string | null;
}

/**
 * The finished state: the sentence, and the link that goes with it. A job that
 * succeeded WITHOUT a link (the server reported no file) still says so — the
 * sentence never promises a download the anchor cannot deliver.
 */
export function exportOutcome(job: JobRecord, t: Translator): ExportOutcome {
  if (job.status !== "succeeded") {
    const reason = exportFailureReason(job);
    return {
      message: reason === null ? t("exports.failed") : t("exports.failedBecause", { reason }),
      ok: false,
      href: null,
    };
  }
  const href = exportDownloadHref(job);
  if (href === null) {
    return { message: t("exports.readyNoFile"), ok: true, href: null };
  }
  return { message: t("exports.ready"), ok: true, href };
}

/**
 * The status line under the button: the server's sentence, plus the download
 * when there is one. Exported as its own pure component so the completed state
 * can be PROVED as markup — the button's own notice is mutation state, which
 * static rendering never reaches.
 */
export function ExportNotice(props: { outcome: ExportOutcome; t: Translator }) {
  const { outcome, t } = props;
  return (
    // CR-018 Route B: ListExportButton.css (deleted) ported value for value.
    // Both states share the sentence shape — m-0, --text-sm, 42ch measure,
    // right-aligned, `wrap-anywhere` (server sentences carry unbreakable
    // tokens); the note is 65% ink written long-hand in srgb (the oklab
    // opacity modifier is not our colour — CR-018 Phase 1 §4), the refusal is
    // the danger register the settings surface uses (BR-SHL-020).
    <p
      className={
        outcome.ok
          ? "m-0 max-w-[42ch] text-right text-sm wrap-anywhere text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]"
          : "m-0 max-w-[42ch] text-right text-sm wrap-anywhere border-l-2 border-l-danger-500 bg-danger-100 px-2 py-1 text-danger-700"
      }
      role={outcome.ok ? "status" : "alert"}
    >
      {outcome.message}
      {outcome.href !== null && (
        <>
          {" "}
          {/* The href is the server's own result_link with this build's API
              origin in front (serverLinkHref, DEF-TEN-9189), followed as a
              plain navigation so the session cookie rides along and the
              server's Content-Disposition names the file. `download` states
              the intent; the header still wins on the name. */}
          <a className="font-semibold text-accent-700" href={outcome.href} download>
            {t("exports.download")}
          </a>
        </>
      )}
    </p>
  );
}

export interface ListExportButtonProps {
  resource: ExportResource;
  /** The table's live request state; null for the two ops views that have none. */
  state?: TableRequestState | null;
  client?: ApiClient; // test seam — screens never build their own transport
  /** BR-SHL-025: a role-blocked export renders disabled WITH the reason. */
  disabledReason?: string | null;
}

export function ListExportButton(props: ListExportButtonProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const fireToast = useToast();
  const [notice, setNotice] = useState<ExportOutcome | null>(null);

  const runExport = useMutation({
    mutationFn: async () => {
      const accepted = await requestListExport(
        exportBodyFrom(props.resource, props.state ?? null),
        client,
      );
      // B12 r1 / 11b §2.17: a 202 is a JOB — polled through the ONE helper.
      return client.pollJob(accepted.job_id);
    },
    onSuccess: (job) => {
      const outcome = exportOutcome(job, translate);
      setNotice(outcome);
      fireToast(outcome.message);
    },
    onError: (error: unknown) => {
      // Every failure renders as the plain-language refusal (BR-SHL-020).
      // There is no longer a size refusal to special-case — see above.
      setNotice({
        message: apiErrorText(error, translate),
        ok: false,
        href: null, // a refusal produced no file — there is nothing to link to
      });
    },
  });

  const blocked = props.disabledReason ?? null;

  return (
    // CR-018 Route B: `.list-export` — the one slot, button above, status line
    // under it, right-aligned (US-SHL-008 / IS-9). `data-resource` was already
    // the machine handle.
    <div className="flex flex-col items-end gap-1" data-resource={props.resource}>
      <span title={blocked ?? undefined}>
        {/* IS-11 by construction: CSV only — no `pdf` prop is passed and none
            can ask for XLSX. The guards are the server's and are never
            re-implemented here (BR-SHL-016). */}
        <DownloadButton
          onDownload={() => {
            setNotice(null);
            runExport.mutate();
          }}
          disabled={blocked !== null || runExport.isPending}
        />
      </span>
      {/* ⚠ THE REASON IS RENDERED, NOT ONLY THE `title` ABOVE (`DEF-SHL-4043`,
          found while fixing `EmptyList`). The prop's own doc says a blocked
          export "renders disabled WITH the reason" and until 2026-09-05 the
          only place that sentence went was the `<span>`'s tooltip — no hover
          on a touch screen, and nothing on the page either way. Third instance
          of one bug in this kit, after `SegmentedControl` (`DEF-WRK-3646`) and
          `EmptyList`. Utilities are lawful HERE because this file IS on
          `route-b-migrated.txt` — the same three classes in `StateFrame.tsx`
          would compile to nothing. */}
      {blocked !== null && (
        <p
          className="m-0 max-w-[42ch] text-right text-sm wrap-anywhere text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]"
          data-export-blocked-reason=""
        >
          {blocked}
        </p>
      )}
      {runExport.isPending && (
        <p
          className="m-0 max-w-[42ch] text-right text-sm wrap-anywhere text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]"
          role="status"
        >
          {t("exports.working")}
        </p>
      )}
      {notice !== null && !runExport.isPending && (
        <ExportNotice outcome={notice} t={translate} />
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-008@17df6a0 (EP-SHL-02 §Stories — hash = sha256/7 of the source epic; co-packets US-MET-001/002@947cf31 · US-MET-005@14f767b · US-AST-001@566072b · US-RAT-001@6304a38 · US-RAT-008/009@7d1a8ef · US-RAT-010@f69a661)
// generated: 2026-08-10 by story-coder v1 (list-export lane — the frontend half of POST /exports) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: ruff✔(E4/E7/E9/F on apps/core/config — the bar the baseline passes) black✔(this lane's 13 files; 32 pre-existing unformatted files are the repo baseline, untouched) py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped (unchanged) · migrate from empty✔ makemigrations --check --dry-run clean✔ (this lane adds NO migration) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ (227 stories, 459 BR refs, 60 OQs) · frontend tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · mypy NOT INSTALLED in this environment (recorded, not skipped silently) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E3 [SUPERSEDED 2026-09-12, `DEF-MET-4964` — the download route LANDED and this sentence did not move] this read "`result_link` is a `file://` artifact path — NO download route exists (IS-11 downloads are the reports W5 story), so the completed state NAMES the generated file as text instead of rendering an anchor the browser cannot follow; the moment a download endpoint lands, this one function (exportOutcome) becomes the link — REPORTED, not faked". It became the link, at :177, over the route this file's own :50 documents. The trailer went on stating an absence the code no longer had, read by nothing — `G38` checks an absence stated to a USER and reads no comment. ⚠ [CLOSED 2026-10-02] this read that on a deployment with `JOBS_EAGER=false` the anchor saved `file.json` containing a 404 because the worker wrote the artifact to a container disk the web process could not read (`DEF-MET-4954`); the file is now in S3 and the route answers a 302 to a 4-hour signed link that names the file, which this plain `<a href download>` follows unchanged · E3 S26/S27 carry no table request state (their endpoints are unpaginated plain arrays, the gap the metering frontend lane reported), so their exports post an empty state and cover the whole list, which is exactly what those tabs show · E3 IS-9's "visible columns" half is not sent: the ratified body carries no column state and column visibility is a per-user client preference (BR-SHL-013), so every file carries the capability row's DEFAULT columns — the backend packet reports the same gap · no second poller exists in this file: the 202 is followed through client.pollJob, the same helper S61 uses
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
