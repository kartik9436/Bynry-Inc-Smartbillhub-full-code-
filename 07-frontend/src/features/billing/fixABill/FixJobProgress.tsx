// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-BIL-10091 — bulk Fix a bill runs in the background
// Change:   CR-180-BRC10 · decision log 2026-10-13 (*FIX A BILL RELEASED IN
//           2.573.0*): bulk preview, Send and Approve-and-issue are jobs, with
//           progress on screen
// Rules:    NFR-4 (heavy work async, with progress) · B14 rules 21, 33, 43
// ───────────────────────────────────────────────────────
/**
 * One line of progress for a bulk act running in the background:
 * *"Working out 38 bills · 12 done"*. A FACT (B14 rule 33), so it is the
 * stage and the two counts and nothing else; `role="status"` so a screen
 * reader hears it move. Before the job has counted its bills it says
 * *"Waiting to start"* rather than *"0 of —"*.
 */
import type { CorrectionJobProgress } from "@/api/billingOpsEndpoints";

type Translate = (key: string, params?: Record<string, unknown>) => string;

export function FixJobProgress(props: {
  progress: CorrectionJobProgress | null;
  /** The stage to name before the server has reported one. */
  stage: "pricing" | "checking" | "sending" | "issuing";
  t: Translate;
}) {
  const { progress, t } = props;
  const stage = progress?.stage ?? props.stage;
  const counted = progress !== null && progress.total !== null && progress.total !== undefined;
  return (
    <p
      className="m-0 bg-neutral-100 px-4 py-2 text-base tabular-nums"
      role="status"
      data-fix-job={counted ? stage : "queued"}
    >
      {counted
        ? t(`billing.fixBill.job.${stage}`, { total: progress.total, done: progress.done })
        : t("billing.fixBill.job.queued")}
    </p>
  );
}
