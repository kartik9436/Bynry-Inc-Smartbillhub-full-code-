// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 3 `P3.2` (screen
//          `5·2`) and `P3.4` (re-run). Drawing p42 (the dialog) and p43 (its
//          FOR/DOORS/PRIMARY ACTION/FIELDS rows and callout ④), read as
//          IMAGES per B14 rule 42.
// Rules:   B14 rule 44 (the drawing says WHAT; our standard says how it is
//          BUILT and wins) · rule 43 (component) · rule 33 (LABEL ≤ 3 words ·
//          FACT ≤ 6 · RATIONALE zero) · rule 31 (no database id on screen) ·
//          rule 5 (one primary per surface) · BR-SHL-021 (a toast is text
//          only) · BR-REP-018 (3-day retention)
// Tests:   07-frontend/src/features/reports/runHistory.dom.test.tsx
// Impacts: RunHistoryPage.tsx · api/runHistoryEndpoints.ts
// ───────────────────────────────────────────────────────
//
// SCREEN `5·2` — ONE RUN, OPENED. *"Getting a file back, or reproducing a
// figure somebody is querying"* (p43 FOR).
//
// ════════════════════════════════════════════════════════════════════════════
// THE DOWNLOAD BUTTON IS LABELLED HERE AND AN ICON ON `2·1`, AND p43 SETTLES IT
// ════════════════════════════════════════════════════════════════════════════
// Verbatim, from the PRIMARY ACTION row: *"Download CSV. ⚠ **Labelled here and
// an icon on 2·1, and that is not an inconsistency**: on 2·1 it is
// `DownloadButton` in a toolbar, which the shipped component renders as a
// 36×36 icon; here it is a dialog footer, where a button carries its verb."*
//
// So this file does NOT use `DownloadButton`. Checked in the code rather than
// taken from the rule: `components/DownloadButton.tsx` renders
// `className="h-9 w-9 justify-center px-0"` with the sentence moved to
// `aria-label` and `title` — 36×36, no label, since `CR-045 A.3`, because it
// cost ~130px of a toolbar that was already over budget. A dialog footer has
// no such budget and a footer button with no words in it is a puzzle.
//
// ════════════════════════════════════════════════════════════════════════════
// RE-RUN — `P3.4`
// ════════════════════════════════════════════════════════════════════════════
// p43 callout ④, verbatim: *"Writes: a new `jobs` row with **the original
// parameters, unchanged** · an `audit_log` row. The ledger: nothing.
// Elsewhere: a new row at the top of **`5·1`**; the old run and its file are
// untouched. ⚠ Two figures may differ, because the data moved — **which is the
// point of keeping both runs rather than replacing one**."*
//
// ⚠ **IT GOES BACK THROUGH `POST /exports`, WHICH IS §8.2's RIGHT PATH.** The
// brief: *"The right path never holds a page"*, and *"build on those three
// calls; do not invent a fourth"*. Re-run is the FIRST call again with the
// stored parameters — measured on the running product on 2026-09-27, **202 in
// 0.117s**. It is emphatically not a fetch-and-re-render of this dialog.
//
// ⚠ **RE-RUN IS THE GHOST TIER AND `Download CSV` IS THE PRIMARY.** p42 draws
// `Re-run` as plain text to the LEFT of the outlined primary, which is B14
// rule 5's one-primary-per-surface. A clerk opening a finished run is there to
// get the file; re-running is the rarer, heavier act.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { serverLinkHref } from "@/api/apiHref";
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { ReportRun } from "@/api/runHistoryEndpoints";
import { getReportRun, rerunReport } from "@/api/runHistoryEndpoints";
import { Button, buttonClasses } from "@/components/Button";
import { ModalShell } from "@/components/FormModal";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";

/** The download anchor's kit classes, resolved ONCE at module scope.
 *
 * ⚠ **IT IS HOISTED FOR A READER THAT IS NOT A HUMAN** — `DEF-REP-6924`. Both
 * class-name readers in this repo (`g31_declared_classes.py` and
 * `styles/routeBUtilities.test.ts`, one grammar in
 * `classname-grammar/patterns.json`) take the QUOTED STRINGS out of a
 * `className={…}` expression, because that is the only way to see a class in
 * markup that builds one. Call the kit INSIDE that attribute and its two
 * ARGUMENTS read as two class names — `G134` correctly reported the variant and
 * the size as tokens that compile to no CSS rule.
 *
 * ⚠ **AND DO NOT WRITE THE OLD LINE OUT IN A COMMENT TO EXPLAIN IT.** The
 * grammar reads source TEXT and has no idea what a comment is, so the first
 * draft of this note quoted the offending markup verbatim and `G134` went on
 * reporting both tokens — out of the paragraph describing their removal.
 * Measured: the fix landed, the gate stayed red, and the only thing still
 * asking for them was this docstring.
 *
 * They were never on the element — the string `buttonClasses` returns is the
 * real one — so this is a check reporting a token the page does not ask for,
 * and the cost of leaving it is law 7's: a true red in a list of reds is one
 * nobody reads. Every other kit call in the product is already hoisted this way
 * (`FILTER_TRIGGER_KIT`, `PANEL_TRIGGER_KIT`, `DOOR`, `COMMIT_DANGER`); this
 * was the one inline call site left. */
const DOWNLOAD_KIT = buttonClasses("primary", "default");

const TONES: Record<ReportRun["status"], StatusTone> = {
  queued: "neutral",
  running: "info",
  ready: "success",
  failed: "danger",
  expired: "muted",
};

export function RunDialog(props: {
  runId: string;
  client?: ApiClient;
  onClose: () => void;
  onRerun: () => void;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const client = props.client ?? api;

  const run = useQuery({
    queryKey: ["report-run", props.runId],
    queryFn: () => getReportRun(props.runId, client),
    retry: false,
  });

  const rerun = useMutation({
    mutationFn: () => rerunReport(run.data as ReportRun, client),
    // US-SHL-012: a toast fires on a COMMITTED action and never on a failure.
    // The server answers 202 and a worker writes the file, so the honest
    // statement is that the run was ASKED FOR.
    onSuccess: () => {
      toast(t("reports.export.queued"));
      props.onRerun();
    },
  });

  const value = run.data;

  return (
    <ModalShell
      // p42's dialog head: the report's NAME, and under it *when · who · how
      // many rows*. Never the run's id (B14 rule 31).
      title={
        value === undefined
          ? t("reports.history.run.loading")
          : t(`reports.card.${value.report}.name`, { defaultValue: value.report })
      }
      onClose={props.onClose}
    >
      <div className="modal-body" data-screen="5.2">
        {value === undefined ? null : (
          <>
            <p className="mt-0 mb-5 text-sm text-neutral-600" data-run-subline>
              {[
                value.ran_at === null ? null : new Date(value.ran_at).toLocaleString(),
                value.started_by ?? t("reports.history.schedule"),
                value.rows === null
                  ? null
                  : t("reports.history.run.rows", { count: value.rows }),
              ]
                .filter((part) => part !== null)
                .join(" · ")}
            </p>

            {/* p43 FIELDS: Report · when · who · rows · parameters · status ·
                expiry. The first four are the sub-line above; these three are
                the drawn read-only fields. */}
            <ReadOnlyField label={t("reports.history.run.parameters")}>
              {describeFilters(value.filters, t)}
            </ReadOnlyField>

            <ReadOnlyField label={t("reports.history.run.status")}>
              <StatusPill tone={TONES[value.status]}>
                {t(`reports.history.status.${value.status}`)}
              </StatusPill>
              {/* A18 §4 — a FAILED run says what went wrong, where the clerk
                  is. ⚠ The server's sentence, not a cheerful substitute. */}
              {value.status === "failed" && value.error !== null ? (
                <span className="ml-3 text-sm text-danger-700" role="alert" data-run-error>
                  {value.error}
                </span>
              ) : null}
            </ReadOnlyField>

            {value.expires_at === null ? null : (
              <ReadOnlyField
                label={t("reports.history.run.expires")}
                // p43 RULES: *"Obeys B14 5 · 33 (the expiry helper is a fact in
                // six words)"*. It states WHAT is true of this file, never WHY
                // the product keeps it three days — that is rationale and is
                // zero words on screen.
                help={t("reports.history.retention")}
              >
                {new Date(value.expires_at).toLocaleDateString(undefined, {
                  day: "numeric",
                  month: "short",
                })}
              </ReadOnlyField>
            )}
          </>
        )}
      </div>

      <div className="modal-foot">
        {/* ⚠ **RE-RUN IS OFFERED ONLY WHERE THERE IS SOMETHING TO REPRODUCE.**
            A queued or running job re-run would be a second job doing the same
            work — and the `jobs` table's own idempotency constraint (one active
            job per tenant + kind + scope) is what would refuse it, at the
            server, after the click. A control that will be refused is one that
            should not be drawn. An EXPIRED run keeps its Re-run: that is the
            case the button exists for. */}
        {value === undefined || value.status === "queued" || value.status === "running" ? null : (
          <Button
            variant="ghost"
            data-run-rerun
            disabled={rerun.isPending}
            onClick={() => rerun.mutate()}
          >
            {t("reports.history.run.rerun")}
          </Button>
        )}
        {/* ⚠ **NO ADDRESS, NO CONTROL** — the same rule as the FILE cell on
            `5·1`, and the reason this screen exists. An expired run shows no
            download at all rather than a disabled one: BR-SHL-025 disables a
            control this DEPLOYMENT cannot honour and says why, and this is not
            that — there is simply nothing to download, which the `Expires`
            field and the status pill already say. A greyed *Download CSV* would
            be a second, quieter claim that a file is nearly there. */}
        {value?.file == null ? null : (
          // ⚠ **AN `<a download>`, NOT A `<button>` — AND NOT `ButtonLink`
          // EITHER.** The kit has two: `Button` (a `<button>`) and
          // `ButtonLink` (a router `<Link>`, for in-app navigation). This is
          // neither: it leaves the SPA for a streamed file, so it needs a real
          // `href` the browser downloads and middle-click opens. `buttonClasses`
          // is the kit's own styling entry point, so the control is built to the
          // standard (rule 44) without pretending to be a component it is not.
          <a
            href={serverLinkHref(value.file)}
            download
            data-run-download
            data-variant="primary"
            className={DOWNLOAD_KIT}
          >
            {t("reports.history.run.download")}
          </a>
        )}
      </div>
    </ModalShell>
  );
}

/** A drawn field that holds a FACT rather than an input — p42's three boxes.
 *
 * ⚠ **A COMPONENT, NOT 3×12 LINES INLINE** (B14 rule 43, ratified after *"use
 * it"* turned out to mean 120 lines inside a 4,186-line page). It is local to
 * this file because it is this dialog's shape; the day a second screen wants
 * it, it moves to the kit rather than being copied. */
function ReadOnlyField(props: { label: string; help?: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <div className="mb-1.5 font-heading text-sm font-semibold text-text">{props.label}</div>
      <div className="flex min-h-9 items-center border border-divider px-3 py-2 text-body text-text">
        {props.children}
      </div>
      {props.help === undefined ? null : (
        <div className="mt-1.5 text-sm text-neutral-600">{props.help}</div>
      )}
    </div>
  );
}

function describeFilters(
  filters: Record<string, string>,
  t: (key: string) => string,
): string {
  const entries = Object.entries(filters).filter(([, value]) => value !== "" && value !== null);
  if (entries.length === 0) return t("reports.history.run.noParameters");
  const from = filters.from ?? "";
  const to = filters.to ?? "";
  if (from !== "" && to !== "") return `${from} – ${to}`;
  return entries.map(([, value]) => String(value)).join(" · ");
}

export default RunDialog;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P3.2 · P3.4 (05-prototype/09 Reports Build Brief.pdf p42-p43, read as images per B14 rule 42)
// screens: 5·2
// generated: 2026-09-27 by lane REP-P3
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — `runHistory.dom.test.tsx` was run before this file existed and reported `Cannot find module './RunDialog'`. G31: this file is listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) `Download CSV` is a LABELLED button here and a 36×36 icon on 2·1 — p43's PRIMARY ACTION row settles that explicitly and it is not a divergence · (2) Re-run is withheld on a queued/running job, which the drawing does not say, because the `jobs` idempotency constraint would refuse it at the server after the click · (3) the drawing draws `Delete` and `Pause` on the SCHEDULE dialog `4·2`, not here: a run has no write surface at all (p43 WRITE SURFACES — *"Edit / Update NOTHING — a run is a historical fact"*)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
