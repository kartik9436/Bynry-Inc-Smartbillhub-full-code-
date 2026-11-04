// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-8106 — posting 480 readings ran inside the request, took
//           ~60 s, and the web worker was killed after the readings were
//           saved: the clerk saw *Internal Server Error*.
// Ruling:   PO 2026-09-30, decision log "READS UPLOAD 500 ON 480 READINGS",
//           fix (A): a large batch posts as a background job WITH PROGRESS.
// Rules:    BR-MET-055 (the post as a job with progress) · B14 rule 33 (a fact
//           ≤ 6 words; rationale is zero words on screen) · B14 rule 43 (a
//           piece of UI is a component) · B14 rule 21 (Tailwind utilities)
// Impacts:  UploadReadsWizard.tsx (stage 4, while the post job runs)
// ───────────────────────────────────────────────────────
import type { JobRecord } from "@/api/client";
import type { Translator } from "@/features/tenancy/settingsShared";

/**
 * **HOW FAR A BACKGROUND POST HAS GOT** — `N of M` readings, from the job record.
 *
 * ⚠ **THE TWO INTEGERS THE SERVER WROTE, AND NOTHING DIVIDED.** `GET /jobs/{id}`
 * serves `progress: {done, total}` and no percentage, so — like the bill run's
 * `RunProgressLine`, which argues this at length — no bar and no width is
 * drawn here: a width is a claim about a length the server did not state.
 * `total` is `null` before the worker's first report, and the line then says
 * *so far* rather than *of 0*.
 *
 * `null` in, nothing out: a batch at or below the server's bar posts while the
 * clerk waits and has no job to show.
 */
export function ReadPostProgress(props: { job: JobRecord | null; t: Translator }) {
  const { job, t } = props;
  if (job === null) return null;
  const done = job.progress?.done ?? 0;
  const total = job.progress?.total ?? null;
  const line =
    job.status === "failed"
      ? t("metering.upload.post.progress.failed")
      : job.status === "queued"
        ? t("metering.upload.post.progress.queued")
        : total === null
          ? t("metering.upload.post.progress.soFar", { done: done.toLocaleString() })
          : t("metering.upload.post.progress.ofTotal", {
              done: done.toLocaleString(),
              total: total.toLocaleString(),
            });
  return (
    <div
      className="my-3 border-l-[3px] border-l-accent bg-[color-mix(in_srgb,var(--color-text)_3%,transparent)] p-3"
      data-read-post="progress"
      data-read-post-state={job.status}
      role="status"
      aria-live="polite"
    >
      <p className="m-0 text-base font-semibold tabular-nums">{line}</p>
    </div>
  );
}
