// ── Trace ──────────────────────────────────────────────
// Drawing: 05-prototype/one-time-bill-2026-09-30/ — the right-hand aside on
//          every step (inventory.md §1.5); *-36-state-already-billed.png (§6)
// Plan:    12-one-time-bill-build-plan.md F13 (already-billed), F14 (summary)
// ───────────────────────────────────────────────────────
/**
 * The summary aside — the kind, the total, charges · tax · lines, bill date and
 * due, then what the bill does with each service — and the already-billed
 * banner. Both read the server's preview; neither computes a figure.
 *
 * ⚠ **`Due` READS `—` WHILE STEP 1 HAS PROBLEMS**, as drawn: a due date derived
 * from a bill date or a days-to-pay the clerk still has to fix is a date the
 * bill will not carry.
 */
import { Link } from "react-router-dom";

import type { OneTimeBillDuplicate, OneTimeBillKind, OneTimeBillPreview } from "@/api/billingOpsEndpoints";
import { Button, ButtonLink } from "@/components/Button";
import type { Translator } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";

import { hasServiceSections, lineCount, serviceCounts, taxTotal } from "./oneTimeBillModel";
import { day, kindName, money } from "./oneTimeBillShared";
import type { OtbFormat } from "./oneTimeBillShared";

export type SummaryFootnote = "nothing" | "draft" | "sent";

const ROW = "flex items-center justify-between gap-3 text-base";

export function OneTimeSummary(props: {
  kind: OneTimeBillKind;
  preview: OneTimeBillPreview | null;
  billDate: string | null;
  dueDate: string | null;
  footnote: SummaryFootnote;
  /** DEF-BIL-8289 — step 1 is not filled in yet; say so instead of a figure. */
  waiting?: boolean;
  t: Translator;
  fmt: OtbFormat;
}) {
  const { preview, t, fmt } = props;
  const counts = serviceCounts(preview?.services ?? null);
  const lines = lineCount(preview);
  const warnings = preview?.warnings.length ?? 0;
  return (
    <Panel as="aside" aria-label={t("billing.oneTimeBill.summary.label")} data-otb-summary="">
      <p className="m-0 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
        {kindName(props.kind, t)}
      </p>
      <p className="m-0 mt-2 font-heading text-metric-lg font-semibold" data-otb-summary-total="">
        {preview === null ? "—" : money(preview.bill.total, fmt)}
      </p>
      {props.waiting === true && preview === null && (
        <p className="m-0 mt-1 text-base text-neutral-700" role="status" data-otb-summary-waiting="">
          {t("billing.oneTimeBill.summary.waiting")}
        </p>
      )}
      <div className="mt-3 flex flex-col gap-1.5">
        <div className={ROW}>
          <span>{t("billing.oneTimeBill.summary.charges")}</span>
          <span>{preview === null ? "—" : money(preview.bill.subtotal, fmt)}</span>
        </div>
        <div className={ROW}>
          <span>{t("billing.oneTimeBill.summary.tax")}</span>
          <span>{money(taxTotal(preview), fmt)}</span>
        </div>
        {preview !== null && preview.bill.one_time_charges !== undefined && preview.bill.one_time_charges !== null && (
          // DEF-BIL-8565 — the figures above add up to the total.
          <div className={ROW} data-otb-summary-one-time="">
            <span>{t("billing.oneTimeBill.bill.oneTimeCharges")}</span>
            <span>{money(preview.bill.one_time_charges, fmt)}</span>
          </div>
        )}
        <div className={ROW}>
          <span>{t("billing.oneTimeBill.summary.lines")}</span>
          <span>{lines ?? "—"}</span>
        </div>
      </div>
      <div className="mt-3 flex flex-col gap-1.5 border-t border-divider pt-3">
        <div className={ROW}>
          <span>{t("billing.oneTimeBill.summary.billDate")}</span>
          <span>{day(props.billDate, fmt)}</span>
        </div>
        <div className={ROW}>
          <span>{t("billing.oneTimeBill.summary.due")}</span>
          <span data-otb-summary-due="">{day(props.dueDate, fmt)}</span>
        </div>
      </div>
      {hasServiceSections(props.kind) && (preview === null || preview.services === null) && (
        // DEF-BIL-8282 — before a preview answers nothing is KNOWN about the
        // services, and "0 services" is a claim that there are none. It says
        // what is true: not checked yet.
        <div className="mt-3 flex flex-col gap-1.5 border-t border-divider pt-3" data-otb-summary-services="unknown">
          {(["billed", "notInService", "notTaken", "warnings"] as const).map((row) => (
            <div key={row} className={ROW}>
              <span>{t(`billing.oneTimeBill.summary.${row}`)}</span>
              <span>—</span>
            </div>
          ))}
          <p className="m-0 text-base text-neutral-700">{t("billing.oneTimeBill.summary.notChecked")}</p>
        </div>
      )}
      {hasServiceSections(props.kind) && preview !== null && preview.services !== null && (
        <div className="mt-3 flex flex-col gap-1.5 border-t border-divider pt-3">
          <div className={ROW}>
            <span>{t("billing.oneTimeBill.summary.billed")}</span>
            <StatusPill tone="success">
              {t("billing.oneTimeBill.summary.services", { count: counts.billed })}
            </StatusPill>
          </div>
          <div className={ROW}>
            <span>{t("billing.oneTimeBill.summary.notInService")}</span>
            <StatusPill tone="neutral">
              {t("billing.oneTimeBill.summary.noLine", { count: counts.notInService })}
            </StatusPill>
          </div>
          <div className={ROW}>
            <span>{t("billing.oneTimeBill.summary.notTaken")}</span>
            <StatusPill tone="neutral">{counts.notTaken}</StatusPill>
          </div>
          <div className={ROW}>
            <span>{t("billing.oneTimeBill.summary.warnings")}</span>
            <StatusPill tone={warnings > 0 ? "warning" : "neutral"}>{warnings}</StatusPill>
          </div>
        </div>
      )}
      <p className="m-0 mt-3 text-base text-neutral-700" data-otb-footnote={props.footnote}>
        {t(`billing.oneTimeBill.summary.foot.${props.footnote}`)}
      </p>
    </Panel>
  );
}

/**
 * `Already billed for this period.` — who, when, and a link to that bill.
 *
 * ⚠ `DEF-BIL-10068` (PO 2026-10-12, *"Do all three"*): a DRAFT for the period
 * is not a bill that went out. It reads *"Draft already exists for this
 * period."* with **Open draft** and **Discard draft** — and it is shown on
 * STEP 1, the moment the period is picked, where it used to arrive as a
 * refusal at step 3. An issued bill keeps the old sentence and its one link.
 */
export function AlreadyBilledBanner(props: {
  duplicate: OneTimeBillDuplicate;
  billHref: string | null;
  /** Discard the draft and start again — `POST /billing/runs/{id}/discard`. */
  onDiscard?: () => void;
  discarding?: boolean;
  t: Translator;
  fmt: OtbFormat;
}) {
  const { duplicate, t, fmt } = props;
  const facts = [
    duplicate.invoice_no,
    duplicate.ran_at === null ? null : day(duplicate.ran_at.slice(0, 10), fmt),
    duplicate.ran_by_name === null ? null : t("billing.oneTimeBill.duplicate.by", { name: duplicate.ran_by_name }),
  ].filter((part): part is string => part !== null && part !== "");
  if (duplicate.status === "draft") {
    return (
      <div
        className="m-0 mb-4 flex flex-wrap items-center gap-x-2 gap-y-2 bg-warning-100 px-4 py-3 text-base text-warning-700"
        role="alert"
        data-otb-duplicate="draft"
      >
        <strong>{t("billing.oneTimeBill.duplicate.draftTitle")}</strong>
        <span>{facts.join(" · ")}</span>
        <span className="ml-auto flex gap-2">
          {props.billHref !== null && (
            <ButtonLink size="sm" to={props.billHref}>
              {t("billing.oneTimeBill.duplicate.openDraft")}
            </ButtonLink>
          )}
          {props.onDiscard !== undefined && (
            <Button
              size="sm"
              variant="danger"
              disabled={props.discarding === true}
              onClick={props.onDiscard}
            >
              {t("billing.oneTimeBill.duplicate.discard")}
            </Button>
          )}
        </span>
      </div>
    );
  }
  return (
    <p
      className="m-0 mb-4 flex flex-wrap gap-x-2 bg-danger-100 px-4 py-3 text-base text-danger-700"
      role="alert"
      data-otb-duplicate=""
    >
      <strong>{t("billing.oneTimeBill.duplicate.title")}</strong>
      <span>{facts.join(" · ")}</span>
      {props.billHref !== null && (
        <Link to={props.billHref} className="font-semibold text-danger-700 underline">
          {t("billing.oneTimeBill.duplicate.open")}
        </Link>
      )}
    </p>
  );
}

/** A period's month in the reader's language — `"2026-08-01"` → `August`. */
export function monthName(isoDay: string | undefined, language: string): string {
  if (isoDay === undefined || isoDay === "") return "—";
  return new Intl.DateTimeFormat(language, { month: "long", timeZone: "UTC" }).format(
    new Date(`${isoDay}T00:00:00Z`),
  );
}

/**
 * `DEF-BIL-10069` (PO 2026-10-12, *"Okay"*) — *"August is closed. Posts to
 * October."*, on step 1 the moment the period is picked. The bill keeps its
 * service period; only the books' date moves (BR-TEN-038). It used to be met
 * as a refusal at Send. A fact, two sentences of at most four words (rule 33).
 */
export function ClosedMonthNote(props: {
  closed: { requested_period: string[]; posted_period: string[] };
  t: Translator;
  language: string;
}) {
  const { closed, t } = props;
  return (
    <p
      className="m-0 mb-4 bg-info-100 px-4 py-3 text-base text-info-700"
      role="status"
      data-otb-closed-month=""
    >
      {t("billing.oneTimeBill.closedMonth", {
        closed: monthName(closed.requested_period[0], props.language),
        posted: monthName(closed.posted_period[0], props.language),
      })}
    </p>
  );
}
