// ── Trace ──────────────────────────────────────────────
// Screen:   Meter Reads blueprint **entry 20**, the Still-to-read tab's bulk
//           bar — *"Estimate these · On the shortfall · Estimates the ticked
//           meters — the answer when nobody is going back out"* (p047's control
//           table), drawn on p045 beside *Send someone out*.
// Rules:    BR-MET-026 (the trailing-average estimate) · BR-MET-027 (two
//           consecutive, then somebody goes out) · BR-MET-030 (an estimate
//           carries a reason and an audit row) · BR-MET-058 (a register's OWN
//           history) · BR-MET-062 (a demand peak is never estimated) ·
//           BR-SHL-025 (a refusal is an answer with its reason) · hard rule 3
//           (a quantity carries its unit) · B14 rules 7 (the date input), 11
//           (the consequence before the commit), 31 (no uuid on screen),
//           32/33 (the budget and the word caps), 36 (compose the kit), 39
//           (label → input → helper)
// Tests:    BulkEstimateModal.test.tsx
// ───────────────────────────────────────────────────────
//
// **THE SHORTFALL'S FIRST ANSWER — fill the gap from history.**
//
// `SendSomeoneOutModal` is the other one and admits that somebody has to go and
// look; `BR-MET-027` makes that the ONLY answer once the consecutive-estimate
// cap is reached and `BR-MET-062` makes it the only answer for a demand peak,
// which is why the two controls sit side by side on the drawn row rather than
// one being a fallback for the other.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ NOTHING HERE COMPUTES A QUANTITY, CHOOSES A UNIT OR PICKS A ROUNDING
// ══════════════════════════════════════════════════════════════════════════
// `Q7`'s standing instruction, and B4/B5 are ❄️ FROZEN. The screen sends
// `(meter, register, date)` and a reason; every number in the answer is the
// server's, rendered with the unit the server composed. A consumption with no
// unit is refused by hard rule 3, and a dash is the honest answer.
//
// ⚠ **WHY A NEW DIALOG RATHER THAN ENTRY 19's.** p047 names *"Entry 19's
// dialog"* as what serves this action, and entry 19's dialog —
// `EstimateReadModal` — asks for ONE meter, ONE register and ONE date and
// answers about one record. A set of ticked meters is a different question with
// a different answer (a partial one, which is the whole point of `BR-MET-026`'s
// posture at scale), so it is its own surface composed from the same kit — B14
// rule 36's *"where the kit lacks a piece, add it"*, applied to this module's
// own dialogs. The PIPELINE is unchanged and is the server's.
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { ReadChaseRow } from "@/api/endpoints";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DatePickerField, FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Note } from "@/components/TextBits";

import { bulkEstimateReads } from "./readCycleEndpoints";
import type { BulkEstimateResult } from "./readCycleEndpoints";

const MEASURE = "max-w-measure";
const SENTENCE = "m-0 mb-2 max-w-measure text-sm leading-prose";
const OUTCOME = "mt-6 border-l-[3px] bg-surface p-4";
const OUTCOME_MADE = "border-l-success-500";
const OUTCOME_REFUSED = "border-l-warning-500";
const OUTCOME_TITLE = "m-0 mb-3 font-heading text-h4";

/**
 * `BR-MET-030` — a reason is required, and the DATE is the record's own.
 *
 * ⚠ **THE SCHEMA CONSTRAINS SHAPE, NEVER ARITHMETIC.** It refuses an empty
 * reason and a malformed date and nothing else; whether the estimate can be made
 * is `BR-MET-026`'s and the server's, and a client that pre-judged it would be a
 * second implementation of a ❄️ FROZEN rule.
 */
export const bulkEstimateSchema = z.object({
  read_at: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  reason: z.string().trim().min(1),
});

/** Every record the ticked meters owe: `(meter, register, date)`, expanded. */
export function bulkEstimateTargets(
  rows: readonly ReadChaseRow[],
  pickedAssetIds: readonly string[],
  readAt: string,
) {
  return rows
    .filter((row) => row.asset_id !== null && pickedAssetIds.includes(row.asset_id))
    .flatMap((row) =>
      row.missing_channels.map((channel) => ({
        asset_id: row.asset_id as string,
        meter_no: row.meter,
        channel,
        read_at: readAt,
      })),
    );
}

/**
 * The answer, rendered as the two halves it actually has.
 *
 * ⚠ **A PARTIAL ANSWER IS RENDERED AS A PARTIAL ANSWER.** Both lists are on
 * screen whenever both are non-empty. Showing only the successes is `DEF-708`'s
 * shape — an act reported that never happened — and here it would send a clerk
 * to a bill run believing forty gaps were filled when four were refused.
 */
export function BulkEstimateOutcome(props: {
  result: BulkEstimateResult;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const { result, t } = props;
  const made = result.estimated.length > 0;
  return (
    <div
      className={`${OUTCOME} ${made ? OUTCOME_MADE : OUTCOME_REFUSED}`}
      role="note"
      data-reads="bulk-estimate-outcome"
    >
      <h3 className={OUTCOME_TITLE}>
        {made
          ? t("metering.bulkEstimate.madeTitle", { count: result.estimated.length })
          : t("metering.bulkEstimate.noneMadeTitle")}
      </h3>
      {result.refused.length > 0 && (
        <>
          <p className={`${SENTENCE} font-semibold text-warning-700`}>
            {t("metering.bulkEstimate.refused", { count: result.refused.length })}
          </p>
          <ul className="m-0 list-none p-0">
            {result.refused.map((row, index) => (
              <li
                key={`${row.meter ?? index}-${row.channel}`}
                className="text-sm"
                // B14 rule 31 — the hook carries the meter NUMBER, so no uuid is
                // anywhere in this markup and the assertion that matters can be
                // written as a plain `not.toContain`.
                data-bulk-estimate-refused={row.meter ?? ""}
              >
                {row.meter ?? t("metering.bulkEstimate.unknownMeter")}
                {" · "}
                {t(`metering.reads.channel.${row.channel}`, { defaultValue: row.channel })}
                {row.message_key != null && row.message_key !== "" && (
                  <>
                    {" · "}
                    {/* `G18` — the server's own key, resolved. A key we do not
                        hold falls back to the generic sentence rather than
                        printing `metering.read.no_history` at a clerk. */}
                    {t(row.message_key, { defaultValue: t("metering.bulkEstimate.refusedGeneric") })}
                  </>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

export interface BulkEstimateModalProps {
  /** The whole shortfall — the dialog picks the ticked rows out of it itself, so
   *  the caller cannot hand it a meter and a register that disagree. */
  rows: readonly ReadChaseRow[];
  pickedAssetIds: readonly string[];
  /** IS-8 — the tenant's own date format, for the kit's date field. */
  dateFormat: RegionalDateFormat;
  /** The cycle's window start, as the read date's PREFILL. A reading taken for
   *  this window belongs in this window; typing over it always wins (BR-PAY-033's
   *  prefill posture, which `DatePickerField` already implements). */
  windowEnd: string;
  client?: ApiClient;
  onClose: () => void;
  onEstimated: () => void;
}

export function BulkEstimateModal(props: BulkEstimateModalProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [readAt, setReadAt] = useState(props.windowEnd);
  const [reason, setReason] = useState("");

  const picked = props.rows.filter(
    (row) => row.asset_id !== null && props.pickedAssetIds.includes(row.asset_id),
  );
  const targets = bulkEstimateTargets(props.rows, props.pickedAssetIds, readAt);

  const estimate = useMutation({
    mutationFn: () => bulkEstimateReads({ reason, targets }, client),
    onSuccess: (result) => {
      if (result.estimated.length > 0) {
        props.onEstimated();
      }
    },
  });

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      await estimate.mutateAsync();
      // `ok: true` REPORTS ONLY THAT THE REQUEST WAS ANSWERED. Which records
      // were filled is the outcome's to render, and the dialog stays open either
      // way — the same posture `EstimateReadModal` takes over its own refusal.
      return { ok: true };
    } catch (error) {
      return { ok: false, error: error as never };
    }
  }

  return (
    <FormModal
      title={t("metering.bulkEstimate.title")}
      kicker={t("metering.reads.kicker")}
      schema={bulkEstimateSchema}
      values={{ read_at: readAt, reason }}
      submitLabel={t("metering.bulkEstimate.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* B14 rule 32 — ONE sentence for this section; rule 33 caps an
          instruction at six words per sentence. */}
      <Note className={MEASURE}>{t("metering.bulkEstimate.lede")}</Note>

      {/* Two FACTS, each under six words: how many meters, how many records.
          They are different numbers and a clerk acts on both — a TOU meter short
          of three windows is one meter and three records. */}
      <p
        className="mb-3 text-sm"
        data-bulk-estimate-meters={picked.length}
        data-bulk-estimate-records={targets.length}
      >
        {t("metering.bulkEstimate.scope", { meters: picked.length, records: targets.length })}
      </p>

      {/* B14 rule 7 — the date INPUT, never a bare text field. */}
      <DatePickerField
        id="read_at"
        label={t("metering.bulkEstimate.readAt")}
        value={readAt}
        onChange={setReadAt}
        prefill={props.windowEnd}
        dateFormat={props.dateFormat}
        required
        help={t("metering.bulkEstimate.readAtHelp")}
      />

      <TextField
        id="reason"
        label={t("metering.bulkEstimate.reason")}
        value={reason}
        onChange={setReason}
        required
        help={t("metering.bulkEstimate.reasonHelp")}
      />

      {/* B14 rule 11 — the consequence, before the commit. Rule 33 caps it at
          six words per sentence and at most two sentences, and the 2026-09-14
          ruling cuts it to five or six meaningful words. */}
      <ConsequenceBox
        tone="check"
        tag={t("metering.bulkEstimate.consequence.tag")}
        title={t("metering.bulkEstimate.consequence.title")}
        body={t("metering.bulkEstimate.consequence.body")}
        data-consequence="reads-bulk-estimate"
      />

      {estimate.data !== undefined && (
        <BulkEstimateOutcome result={estimate.data} t={(key, params) => t(key, params)} />
      )}
    </FormModal>
  );
}

export default BulkEstimateModal;

// ── Lifecycle ─────────────────────────────────────────────
// packet: Meter Reads blueprint entry 20 (p045, p047) · `POST
//   /reads/bulk-estimate`, served since CR-038 and called by nothing until now
// generated: 2026-09-14 by the Meter Reads entry-20 lane
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · vitest BulkEstimateModal.test.tsx · G31 (this file is on
//   styles/route-b-migrated.txt, added in the commit that created it)
// exceptions:
//   E4 a NEW dialog rather than entry 19's — that one asks about ONE record and
//      this asks about a set, whose answer is partial by design (see the header)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
