// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6662 — Finance → Revenue & AR's page head carried
//          *"↓ Download period pack"* DISABLED, titled *"The period pack is
//          not built."*, on all five views. The period pack IS built: it is
//          `US-LED-016`'s export batch, `GET /finance/export/batches` and
//          `.../{id}/file` are mounted, the Close & export screen hands a
//          month over, and four real files were downloaded from it on
//          2026-09-24.
// Rules:   BR-SHL-025 (a control this deployment cannot honour renders
//          DISABLED WITH ITS REASON, never hidden) · B14 rule 43 (a piece of
//          UI is a COMPONENT; standalone code inside a page is not reuse) ·
//          B14 rule 33 (a refusal is a FACT, ≤ 6 words) · B14 rule 31 (no
//          database id is ever the visible value of a field) ·
//          CLAUDE.md hard-won law 2's MIRROR (a live screen behind a dead
//          control).
// ───────────────────────────────────────────────────────
/**
 * THE PERIOD PACK, AS A DOOR THAT TELLS THE TRUTH IN BOTH STATES.
 *
 * ⚠ **THE MECHANISM THAT PRODUCED `DEF-LED-6662` IS A RULE WITH A CLOCK IN
 * IT.** The refusal was correct the day it was written — the export batch did
 * not exist — and it rotted silently on the day the batch landed, because
 * landing the batch and releasing the control that pointed at it are two acts
 * and only the first one feels like the work. Nothing in this repository reads
 * a rendered `title`, so the sentence went on being wrong through every gate,
 * every `tsc` and every suite.
 *
 * ⚠ **SO THE REFUSAL HERE IS DERIVED, NEVER TYPED.** The pack for a period
 * exists exactly when a batch covering that period has been handed over, and
 * that is a fact this component READS. When one exists the control is a real
 * `<a download>` onto the batch's file; when none does, it is still refused —
 * but with *"No month has been handed over yet."*, which is a statement about
 * the books rather than a claim about what the product can do.
 *
 * ⚠ **AN ORDINARY LINK, NOT A FETCH** — the same choice the export history
 * table below makes, for the same reason: the BROWSER must be the thing that
 * saves the file, `Content-Disposition: attachment` is what tells it to, and
 * `<a download>` gets the keyboard and the context menu for free. The href is
 * the API path and is tenant-scoped, because the batch is.
 *
 * ⚠ **THE BATCH ID IS IN THE `href` AND ON NO SCREEN** (B14 rule 31). A pack
 * is named by its period, which is what the head already says.
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { apiHref } from "@/api/apiHref";
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getExportBatches } from "@/api/endpoints";
import type { ExportBatchRow, ReportPeriod } from "@/api/endpoints";
import { ButtonAnchor } from "@/components/Button";
import { GuardedButton } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

/**
 * The handed-over batch whose window CONTAINS the open period, or `null`.
 *
 * ⚠ **CONTAINS RATHER THAN EQUALS, AND THAT IS NOT LENIENCE.** A hand-over is
 * bounded by a from/to window a clerk chooses on 6·2; the commonest one is the
 * month itself, but a quarter-long batch genuinely carries this month's
 * figures and a reader asking for "the pack for September" is right to be
 * given it. A batch that merely OVERLAPS is not offered: half a month's
 * figures under a control that says *period pack* would be the same class of
 * untrue sentence this component exists to remove.
 *
 * The newest match wins, because a period handed over twice to two
 * destinations has two packs and the later one is the one a clerk means.
 */
export function packForPeriod(
  rows: readonly ExportBatchRow[],
  period: ReportPeriod | null,
): ExportBatchRow | null {
  if (period === null) return null;
  const covering = rows.filter(
    (row) =>
      row.period.start !== "" &&
      row.period.end !== "" &&
      row.period.start <= period.start &&
      row.period.end >= period.end,
  );
  if (covering.length === 0) return null;
  return covering.reduce((newest, row) =>
    (row.created_at ?? "") >= (newest.created_at ?? "") ? row : newest,
  );
}

export function PeriodPackButton(props: {
  period: ReportPeriod | null;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;

  // `retry: false` — a failed read must refuse rather than spin. The refusal
  // it falls back to is the honest one: nothing can be shown to have been
  // handed over, so nothing is offered.
  const history = useQuery({
    queryKey: ["finance", "export", "batches", "period-pack"],
    queryFn: () => getExportBatches({}, client),
    retry: false,
  });

  const pack = packForPeriod(history.data?.rows ?? [], props.period);

  if (pack === null) {
    return (
      <GuardedButton
        label={t("finance.action.periodPack")}
        reason={t("finance.export.historyEmpty")}
        onClick={() => undefined}
      />
    );
  }
  return (
    <ButtonAnchor
      /* ⚠ **THE COMPONENT, NOT `buttonClasses` (B14 rules 21, 43 and 44).** An
         anchor is the right ELEMENT — the browser has to be what saves the file
         — and `ButtonAnchor` IS an `<a>`, spreading `href` and `download`
         straight through, so nothing is given up by using it.
         ⚠ **IT PASSED THE VARIANT NAME TO `buttonKit` INSIDE A className
         EXPRESSION, AND `routeBUtilities` THEN REPORTED THAT VARIANT NAME AS A
         CLASS NO STYLESHEET DECLARES.** Both readers extract from a className
         position and cannot tell a bare string literal there from a class name.
         The call was CORRECT and the red was real: a variant name leaking into
         the class-token stream is the hole Route B was bought to close, and
         `buttonKit`'s own docstring already says every caller but `<summary>`
         and `GuardedButton` should render the component instead.
         ⚠ **DO NOT QUOTE THE OLD LINE BACK INTO THIS COMMENT TO EXPLAIN IT.**
         The checker reads source TEXT, so writing the offending expression in
         prose re-creates the exact orphan this change removed — which is what
         the first draft of this comment did, and the gate caught it. */
      variant="secondary"
      data-testid="download-period-pack"
      href={apiHref(tenantPath(`/finance/export/batches/${pack.batch_id}/file`))}
      download
    >
      {t("finance.action.periodPack")}
    </ButtonAnchor>
  );
}
