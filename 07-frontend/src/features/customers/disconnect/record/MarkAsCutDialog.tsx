// ── Trace ──────────────────────────────────────────────
// Change:   CR-125-BRC07 — blueprint p145, `Mark DSC-26-0003 as cut`. Action 3
//           of the three the PO kept, and the only DESTRUCTIVE one.
// Defect:   DEF-CUS-10166 — the closing reading at the cut (PO 2026-10-17,
//           decision log *"WHERE A USER ENTERS A METER READING"*, gap 3:
//           *closing reading + read date + Fetch; no estimate*).
// Rules:    BR-CUS-100 (no proof, no cut) · BR-CUS-103 (base charges stop) ·
//           BR-CUS-104 (the fee is owed at the cut) · BR-CUS-107
//           (`Disconnected`) · B14 rule 6 (danger tier on a destructive
//           commit) · rule 38 · rule 43 · rule 33 (a CONSEQUENCE before an
//           irreversible act: ≤ 6 words per sentence, at most two, never cut
//           below clarity) · BR-SHL-025
// ───────────────────────────────────────────────────────
/**
 * `Mark as cut` — p145. **The most serious act in this product**, and the only
 * one on this record that takes something away from a household.
 *
 * ⚠ **DANGER TIER, BECAUSE IT IS A DESTRUCTIVE COMMIT** (B14 rule 6). It is
 * also not reversible by repeating it: `commit_cut` refuses a second cut by
 * name — *"a cut is recorded once: re-recording it would re-quote the
 * reconnection fee and re-date the enforcement, and the record a utility shows
 * a regulator cannot be re-pointed afterwards."*
 *
 * ⛔ **p145 DRAWS `Who did it · Field crew · WO-26-0402` AND IT IS NOT A
 * FIELD.** `commit_cut` takes `cut_on` and `final_reads` and nothing else:
 * there is no column on `disconnect_cases` for the crew, and no vocabulary
 * exists for a crew outcome at all (`disconnects.CREW_OUTCOME_UNRECORDABLE`,
 * `OQ-383` — a dog loose, a locked gate, the customer paying the driver on the
 * doorstep). **A select that cannot be recorded is a dead control** (hard-won
 * law 2), so the row states the absence and offers nothing. Drawing the select
 * and dropping its value on submit would be worse than either: a clerk would
 * believe they had named a crew.
 *
 * ⚠ **THE FOUR PROTECTIONS ARE RE-DRAWN HERE AND THAT IS NOT DUPLICATION.**
 * p145's own note is the reason: *"They are asked again on the day. An answer
 * from when the notice went out is five days old, and a medical certificate
 * that arrived yesterday is exactly the thing that must stop this."* They come
 * from the same payload the record reads, refreshed when this dialog opens.
 *
 * ⚠ **CLOSING READINGS — `DEF-CUS-10166`.** One row per read meter the server
 * names (`actions.closing_reads.meters`, the meters on a service this case
 * cuts), each through the shared `MeterReadingEntry`: the reading, its read
 * date (opening on the cut date, never after today, never before the meter's
 * last reading) and Fetch with `asOf` = the cut date. No Estimate (the ruling).
 *
 * **REQUIRED PER METER UNLESS THE CLERK TICKS *No access* — OUR JUDGMENT,
 * STATED.** `commit_cut` already has a no-read path: with no `final_reads` it
 * cuts and bills to the last reading on file, which is what every cut did
 * before this dialog took a reading. A crew that cut at the curb stop and
 * could not reach the dial is real, so refusing the cut would block a lawful
 * act; leaving the box optional would let a typed-in-a-hurry cut post nothing
 * silently. So a meter needs a reading OR an explicit *No access*, and a
 * ticked meter simply sends no row — nothing is invented and nothing new is
 * stored (no column records the tick; the absence of the reading is the fact).
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { RegionalDateFormat } from "@/components/DateCell";
import { CheckboxField, DatePickerField, FormModal } from "@/components/FormModal";
import { MoneyCell } from "@/components/MoneyCell";
import { useToast } from "@/components/Toast";
import { MeterReadingEntry, READ_DATE_PROBLEM_KEY, readDateProblem } from "@/features/metering/MeterReadingEntry";

import type { CutStatusAnswer } from "./CutPreviewPanel";
import { CUT_STATUS_HELD_CODE, cutStatusAnswer } from "./CutPreviewPanel";
import type { ClosingReadMeter, DisconnectRecordDetail } from "./disconnectRecordEndpoints";
import { markDisconnectCaseCut } from "./disconnectRecordEndpoints";
import { protectionAnswerKey } from "./ProtectionsPanel";
import { FactRow } from "./recordFacts";

/**
 * p145's `WHAT MARKING IT CUT WILL DO` — five drawn rows.
 *
 * ⚠ **THEY ARE NOT ALL RULES, WHICH IS WHAT THIS LINE USED TO SAY
 * (DEF-CUS-6051).** `status_disconnected` is CONDITIONAL — `BR-CUS-107`'s
 * `Disconnected` is written only when the days up to the cut are billed — and
 * the row stated it as a certainty because, until 2026-09-20, no cut had ever
 * committed anywhere and the condition could not be seen. Its sentence is now
 * chosen by the server's `account_status_becomes.code`; see `cutStatusAnswer`.
 *
 * ⚠ **THE HOLD DIALOG READS ITS EFFECTS FROM THE PAYLOAD AND THIS ONE DOES
 * NOT**, which is the asymmetry that let a promise sit here as a constant:
 * `actions.hold.effects` is served, and this list is typed out. The other four
 * rows are left as they are and are REPORTED rather than quietly widened —
 * `billing_keeps_running` cannot be true at the same time as
 * `status_disconnected`, because writing that status is exactly what ends the
 * bill run. Which sentence survives is a decision about what a clerk is
 * promised rather than an edit: `DEF-CUS-6078`.
 */
const CUT_EFFECTS: { when: "now" | "not_now"; code: string }[] = [
  { when: "now", code: "status_disconnected" },
  { when: "now", code: "ladder_stops" },
  { when: "now", code: "fee_raised" },
  { when: "not_now", code: "account_stays_open" },
  { when: "not_now", code: "billing_keeps_running" },
];

/**
 * The dialog's own copy for each status answer — a CONSEQUENCE before an
 * irreversible act, so ≤ 6 words per sentence and at most two (B14 rule 33).
 * The panel says the same thing in six words because a FACT has a tighter cap;
 * the decision behind both is `cutStatusAnswer`, imported rather than repeated.
 */
const DIALOG_STATUS_KEY: Record<CutStatusAnswer, string> = {
  written: "customers.disconnectRecord.cutDialog.effect.status_disconnected",
  held: "customers.disconnectRecord.cutDialog.effect.status_held",
  unstated: "customers.disconnectRecord.cutDialog.effect.status_not_stated",
};

/**
 * ⚠ **WHAT `commit_cut` SAID ABOUT THE STATUS, READ OFF ITS OWN RESPONSE.**
 *
 * `markDisconnectCaseCut` is typed `Promise<unknown>` and the dialog threw the
 * answer away — the whole of `DEF-CUS-6051`. The response carries
 * `account_status_written` (the code it wrote, or `null`) and, when the final
 * bill could not be raised, an `account_status_held` block with `code`,
 * `br_ref` and a `detail`.
 *
 * ⛔ **`detail` IS AN ENGINEER'S SENTENCE AND NEVER REACHES A CLERK** —
 * `BR-SHL-020` r2 and `DEF-742`. The SCREEN authors the words, keyed off the
 * `code`, exactly as `DISCONNECT_ABSENCE_COPY` does one module over.
 *
 * Narrowed here rather than in `disconnectRecordEndpoints.ts` because that file
 * is another lane's; a structural read needs no edit to it.
 */
function heldStatusCode(result: unknown): string | null {
  // ⚠ **`markDisconnectCaseCut` RETURNS THE ENVELOPE, NOT THE PAYLOAD.**
  // `ApiClient.post` resolves `{ status, data, etag, notModified }`, so the
  // block is at `.data.account_status_held`. A first draft of this function
  // read `result.account_status_held` and was always `null` — it would have
  // shown the OLD fixed sentence on every cut, which is the defect with extra
  // steps. The unwrapped shape is accepted too, so tidying the endpoint helper
  // to return `.data` cannot silently switch this back off.
  const envelope = result as { data?: unknown } | null;
  const body =
    typeof envelope === "object" && envelope !== null && "data" in envelope
      ? envelope.data
      : result;
  if (typeof body !== "object" || body === null) {
    return null;
  }
  const held = (body as { account_status_held?: unknown }).account_status_held;
  if (typeof held !== "object" || held === null) {
    return null;
  }
  const code = (held as { code?: unknown }).code;
  // ⚠ **`""` IS "HELD, REASON UNREADABLE" AND IS NOT `null`.** The two must
  // not collapse: `null` means the status WAS written and earns the ordinary
  // sentence, and a held block with no code still means it was not.
  return typeof code === "string" ? code : "";
}

/** One meter's closing reading, as the dialog holds it. */
interface ClosingRead {
  value: string;
  readDate: string;
  /** The clerk set the date; until then it follows the cut date. */
  dateTouched: boolean;
  fetched: boolean;
  /** The crew could not reach the dial — no row is sent for this meter. */
  noAccess: boolean;
}

/** The DOM id seed for a meter's reading row — never a database id. */
export const closingReadId = (assetNo: string): string => `disconnect-cut-read-${assetNo}`;

export function MarkAsCutDialog(props: {
  record: DisconnectRecordDetail;
  today: string;
  /** IS-8 — a date renders and is entered in the TENANT's format. */
  dateFormat: RegionalDateFormat;
  /** The tenant's zone, for a fetched reading's date. */
  timeZone?: string;
  onClose: () => void;
  onCut?: () => void;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  // ⚠ **THE TOAST IS FIRED HERE AND NOT RETURNED (DEF-CUS-6076).** `FormModal`
  // reads only `outcome.ok` and drops the `toast` member its own prop comment
  // promises to fire, so every `{ ok: true, toast }` in this product has been
  // silent. That is filed as its own defect against the shared component; what
  // it costs THIS dialog is the one channel the cut's outcome can reach a
  // clerk through, so the message is queued directly.
  const toast = useToast();
  const record = props.record;
  const readiness = record.actions?.mark_as_cut;
  // ⚠ **THE EARLIEST LAWFUL DATE IS THE DEFAULT AND NOT TODAY.** `DSC-02.3`
  // locks it — *"EARLIEST LAWFUL CUT · Locked — computed, not chosen"* — and
  // `commit_cut` refuses a date before it, because that is the notice period
  // the customer was given.
  const [cutOn, setCutOn] = useState(record.the_case?.cut_date?.value ?? props.today);
  // DEF-CUS-10166 — one closing reading per meter. A read date the clerk has
  // not touched FOLLOWS the cut date, so moving the cut moves it too.
  const meters: readonly ClosingReadMeter[] = record.actions?.closing_reads?.meters ?? [];
  const [reads, setReads] = useState<Record<string, ClosingRead>>({});
  const readOf = (meter: ClosingReadMeter): ClosingRead =>
    reads[meter.asset_no] ?? { value: "", readDate: "", dateTouched: false, fetched: false, noAccess: false };
  const shownDate = (row: ClosingRead) => (row.dateTouched || row.fetched ? row.readDate : cutOn);
  const put = (assetNo: string, row: ClosingRead) => setReads((was) => ({ ...was, [assetNo]: row }));

  // `DEF-CUS-6758` — THE KEY IS THE FIELD ID. `FormModal` looks the message
  // up with `useFieldError(props.id)` and `collectFormErrors` keys its map by
  // the zod path, so two different names mean a collected error that renders
  // nowhere: the button stays live, the post is blocked, and the clerk is told
  // nothing at all. One string, so they cannot drift — and the reading rows'
  // keys are `MeterReadingEntry`'s own ids for the same reason.
  const shape: Record<string, z.ZodTypeAny> = {
    "disconnect-cut-on": z.string().min(1, t("customers.disconnectRecord.cutDialog.error.noDate")),
  };
  const values: Record<string, string> = { "disconnect-cut-on": cutOn };
  for (const meter of meters) {
    const row = readOf(meter);
    if (row.noAccess) continue;
    const id = closingReadId(meter.asset_no);
    shape[`${id}-value`] = z.string().trim().min(1, t("customers.disconnectRecord.cutDialog.read.required"));
    shape[`${id}-date`] = z.string().superRefine((day, ctx) => {
      const problem = readDateProblem(day, { minDate: meter.last_read?.read_at ?? null, maxDate: props.today || null });
      if (problem !== null) ctx.addIssue({ code: z.ZodIssueCode.custom, message: t(READ_DATE_PROBLEM_KEY[problem]) });
    });
    values[`${id}-value`] = row.value;
    values[`${id}-date`] = shownDate(row);
  }
  const schema = z.object(shape);
  const finalReads = meters
    .filter((meter) => !readOf(meter).noAccess)
    .map((meter) => ({ meter_no: meter.asset_no, value: readOf(meter).value.trim(), read_at: shownDate(readOf(meter)) }));

  const caseNo = record.case_no?.value ?? "";
  const fee = record.what_a_cut_would_do?.reconnection_fee;
  // DEF-CUS-6051 — which answer the server gives about the status, BEFORE the
  // act. Resolved once, used by the effect row and by its `data-` attribute.
  const statusAnswer = cutStatusAnswer(
    record.what_a_cut_would_do?.account_status_becomes?.code,
  );

  return (
    <FormModal
      title={t("customers.disconnectRecord.cutDialog.title", { case: caseNo })}
      kicker={t("customers.disconnectRecord.cutDialog.lede")}
      schema={schema}
      values={values}
      submitLabel={t("customers.disconnectRecord.action.markCut")}
      // B14 rule 6 — the danger tier, because this is the destructive commit.
      submitVariant="danger"
      // ⚠ **A SECOND GUARD AND NOT THE FIRST.** The header button is already
      // disabled when the server refuses; this catches the case where the
      // record was read before something changed, and it keeps the FORM live
      // so a clerk reads what will be asked (`BR-SHL-025`, R4's posture).
      commitBlocked={
        readiness?.ready
          ? undefined
          : t(
              `customers.disconnectRecord.refused.${readiness?.refusal?.code ?? "generic"}`,
              { defaultValue: t("customers.disconnectRecord.refused.generic") },
            )
      }
      onClose={props.onClose}
      onSubmit={async () => {
        // ⚠ **THE ANSWER IS READ NOW, AND IT USED TO BE THROWN AWAY
        // (DEF-CUS-6051).** `commit_cut` states whether it wrote
        // `Disconnected` or deliberately held it, and this dialog discarded the
        // response and showed one fixed sentence — which on both cuts this
        // product has performed was the wrong one.
        const result = await markDisconnectCaseCut(
          record.actions.account_id,
          // DEF-CUS-10166 — the closing readings, when the case has meters.
          finalReads.length === 0 ? { cut_on: cutOn } : { cut_on: cutOn, final_reads: finalReads },
          props.client ?? api,
        );
        const held = heldStatusCode(result);
        toast(
          held === null
            ? t("customers.disconnectRecord.cutDialog.toast")
            : held === CUT_STATUS_HELD_CODE
              ? // The one reason the product has: the final bill could not be
                // raised, so the account stays in the bill run. The SCREEN's
                // words, keyed off the code — `detail` is an engineer's
                // sentence and stays on the audit row (BR-SHL-020 r2, DEF-742).
                t("customers.disconnectRecord.cutDialog.toastBillBlocked")
              : // A held code nobody has taught this screen yet. It still says
                // the status did not move, because that much IS known — the
                // alternative is the fixed sentence that was the defect.
                t("customers.disconnectRecord.cutDialog.toastStatusHeld"),
        );
        props.onCut?.();
        return { ok: true };
      }}
    >
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-accent">
          {t("customers.disconnectRecord.cutDialog.what")}
        </h3>
        <dl className="mt-1" data-testid="disconnect-cut-what">
          <FactRow label={t("customers.disconnectRecord.cutDialog.account")}>
            {record.the_case?.account_no?.value}
            {record.customer_name?.value ? ` · ${record.customer_name.value}` : null}
          </FactRow>
          {/* Hard rule 8 — walked to the premises by the server; this dialog
              declares no address and copies none. */}
          <FactRow label={t("customers.disconnectRecord.cutDialog.address")}>
            {record.address?.value ?? t("customers.disconnectRecord.absent.notRecorded")}
          </FactRow>
          <FactRow label={t("customers.disconnectRecord.cutDialog.services")}>
            {(record.what_a_cut_would_do?.services_affected?.value ?? [])
              .map((code) => t(`rating.service.${code}`, { defaultValue: code }))
              .join(" · ") || t("customers.disconnectRecord.absent.noServices")}
          </FactRow>
        </dl>
      </section>

      <DatePickerField
        id="disconnect-cut-on"
        label={t("customers.disconnectRecord.cutDialog.cutOn")}
        value={cutOn}
        onChange={setCutOn}
        required
        dateFormat={props.dateFormat}
        help={t("customers.disconnectRecord.cutDialog.cutOnHelp")}
      />

      {meters.length === 0 ? null : (
        <section data-testid="disconnect-cut-reads">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-accent">
            {t("customers.disconnectRecord.cutDialog.reads")}
          </h3>
          <ul className="mt-2 flex flex-col gap-3">
            {meters.map((meter) => {
              const row = readOf(meter);
              return (
                <li key={meter.asset_no} className="flex flex-col gap-2" data-closing-read={meter.asset_no}>
                  {row.noAccess ? null : (
                    <MeterReadingEntry
                      meterNo={meter.asset_no}
                      idPrefix={closingReadId(meter.asset_no)}
                      unit={meter.unit}
                      lastReading={
                        meter.last_read === null
                          ? null
                          : { value: meter.last_read.value, readAt: meter.last_read.read_at }
                      }
                      value={row.value}
                      readDate={shownDate(row)}
                      fetched={row.fetched}
                      defaultReadDate={cutOn}
                      // The same lower bound the schema above holds.
                      minDate={meter.last_read?.read_at?.slice(0, 10) ?? undefined}
                      asOf={cutOn === "" ? undefined : cutOn}
                      maxDate={props.today || undefined}
                      showFetch
                      showLastReading
                      required
                      client={props.client ?? api}
                      t={t}
                      timeZone={props.timeZone ?? "UTC"}
                      dateFormat={props.dateFormat}
                      onChange={(next) =>
                        put(meter.asset_no, {
                          ...row,
                          value: next.value,
                          fetched: next.fetched,
                          readDate: next.readDate,
                          dateTouched: next.fetched ? false : row.dateTouched || next.readDate !== shownDate(row),
                        })
                      }
                    />
                  )}
                  <CheckboxField
                    id={`${closingReadId(meter.asset_no)}-no-access`}
                    label={t("customers.disconnectRecord.cutDialog.read.noAccess", { meter: meter.asset_no })}
                    checked={row.noAccess}
                    onChange={(noAccess) => put(meter.asset_no, { ...row, noAccess })}
                  />
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {/* ⛔ p145's `Who did it` — DRAWN, AND NOT A CONTROL. */}
      <p className="text-sm text-neutral-700" data-testid="disconnect-cut-no-crew">
        <span className="font-medium text-neutral-900">
          {t("customers.disconnectRecord.cutDialog.whoDidIt")}
        </span>{" "}
        {t("customers.disconnectRecord.cutDialog.whoAbsent")}
      </p>

      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-accent">
          {t("customers.disconnectRecord.cutDialog.protections")}
        </h3>
        <table className="mt-2 w-full text-sm" data-testid="disconnect-cut-protections">
          <tbody>
            {(record.protections?.checks ?? []).map((row) => (
              <tr key={row.check} className="border-b border-neutral-200">
                <td className="py-2 text-neutral-900">
                  {t(`customers.disconnectRecord.check.${row.check}`, {
                    defaultValue: row.check,
                  })}
                </td>
                <td className="py-2 text-right text-neutral-900" data-outcome={row.outcome}>
                  {t(protectionAnswerKey(row))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-accent">
          {t("customers.disconnectRecord.cutDialog.will")}
        </h3>
        <table className="mt-2 w-full text-sm" data-testid="disconnect-cut-effects">
          <tbody>
            {CUT_EFFECTS.map((effect) => (
              <tr key={effect.code} className="border-b border-neutral-200">
                <td className="py-2 align-top text-neutral-600">
                  {t(`customers.disconnectRecord.hold.when.${effect.when}`)}
                </td>
                <td
                  className="py-2 text-neutral-900"
                  data-effect={effect.code}
                  {...(effect.code === "status_disconnected"
                    ? { "data-cut-status": statusAnswer }
                    : {})}
                >
                  {/* ⚠ **ONE ROW OF THE FIVE IS A READ AND NOT A CONSTANT
                      (DEF-CUS-6051).** The status row's sentence is chosen by
                      the server's `account_status_becomes.code`; the answer
                      also travels as a `data-` attribute so a browser walk can
                      see which one rendered, never as prose on screen. */}
                  {effect.code === "status_disconnected"
                    ? t(DIALOG_STATUS_KEY[statusAnswer])
                    : t(`customers.disconnectRecord.cutDialog.effect.${effect.code}`)}
                  {/* ⚠ **THE FEE ROW CARRIES THE SERVER'S FIGURE OR NO FIGURE.**
                      p145 draws an amount in this sentence and B14 rule 37 makes
                      every drawn number an ILLUSTRATION; the price is the
                      tenant's charge code (`BR-BIL-007`) and three sources
                      disagree about it today. No literal is written here. */}
                  {effect.code === "fee_raised" && fee?.stored ? (
                    <>
                      {" "}
                      <MoneyCell amount={fee.stored} currency={fee.currency ?? "USD"} />
                    </>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* p145's red banner — the same sentence p143 carries, from the same
          catalogue key, so the record and the dialog cannot word it two ways. */}
      <p
        role="note"
        data-testid="disconnect-cut-not-a-closeout"
        className="border border-danger-500 bg-danger-100 px-4 py-3 text-sm font-semibold text-danger-700"
      >
        {t("customers.disconnectRecord.cut.banner")}{" "}
        {t("customers.disconnectRecord.cutDialog.closeOutBody")}
      </p>
    </FormModal>
  );
}
