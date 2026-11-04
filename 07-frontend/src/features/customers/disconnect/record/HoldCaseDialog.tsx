// ── Trace ──────────────────────────────────────────────
// Change:   CR-125-BRC07 — blueprint p144, `Hold DSC-26-0003`. Action 1 of the
//           three the PO kept: *"i will consolidate actions - too many actions
//           - keep critical ones"*.
// Rules:    BR-CUS-039 (a hold stops the ladder) · BR-CUS-043 (a plan's
//           protection has no expiry of its own) · BR-CUS-096 (a dispute is
//           conditioned on an amount nothing stores) · B14 rule 38 (where the
//           drawing and our UI rules disagree about how a FORM is BUILT, the
//           UI rules win — what it CONTAINS is the drawing's) · rule 43 ·
//           rule 33 · BR-SHL-025 (a control this deployment cannot honour
//           renders DISABLED WITH ITS REASON, never hidden)
// ───────────────────────────────────────────────────────
/**
 * `Hold the case` — p144.
 *
 * ════════════════════════════════════════════════════════════════════════
 * ⛔ WHAT THIS DIALOG NO LONGER PROMISES, AND WHY THAT IS THE RULING
 * ════════════════════════════════════════════════════════════════════════
 * p144's `WHAT HOLDING WILL DO` table promises **three** immediate effects:
 * the cut date is cleared, the ladder stops, and the case moves to `On hold`.
 *
 * **Measured against the code that runs when this form is submitted, ONE of
 * the three is true.** `disconnects.record_protection` writes an
 * `AccountProtection` row and touches the case **not at all**:
 *
 *   * *the ladder stops* — **TRUE, and it is the design.** `halt_reason` is
 *     COMPUTED on every call and answers `protected` while a protection is in
 *     force. Nothing stores *"the ladder is running"* on purpose, because a
 *     RUN cached on a row outlives the debt.
 *   * *the cut date is cleared* — **FALSE.** `cut_scheduled_for` is unchanged.
 *   * *the case moves to `On hold`* — ✅ **TRUE SINCE 2026-09-25**
 *     (`DEF-CUS-6755`, lane CUTPATH). It read **FALSE** while `on_hold` was
 *     declared in the schema and assigned by nothing anywhere in the
 *     repository. `disconnects.displayed_state` now DERIVES it from the
 *     protections in force — a derivation and not a column, because a hold
 *     cached on a row outlives the thing that caused it and a payment plan's
 *     protection has no expiry to un-write it by. The drawn word is
 *     **segment**, which is exactly what a derivation reads.
 *
 * **So the dialog promises TWO of the three, and the third is stated as its own
 * consequence.** A clerk holding a SCHEDULED case must not believe the cut date
 * is gone, so the `Not now` half says it stays. The rows come from the SERVER
 * (`actions.hold.effects`), so this screen states no rule of its own.
 *
 * ⚠ **AND THE CUT DATE STAYING IS DRAWN AS ITS OWN CONSEQUENCE RATHER THAN
 * LEFT SILENT.** Deleting a promise and saying nothing in its place would be a
 * clerk discovering the date on the record afterwards. It is the fact they
 * need before pressing the button, so it is in the `Not now` half where it
 * belongs. The rows come from the SERVER (`actions.hold.effects`), so this
 * screen states no rule of its own and the day `disconnects.py` starts
 * clearing the date, one list moves and both surfaces move with it —
 * `test_disconnect_record_page.py` fails until they do.
 *
 * ════════════════════════════════════════════════════════════════════════
 * THE FOURTH REASON IS DRAWN AND IS NOT OFFERED — `DEF-CUS-6757`, 2026-09-25
 * ════════════════════════════════════════════════════════════════════════
 * p144 draws FOUR reasons and `record_protection` names THREE. *A bill is
 * disputed* cannot be recorded: nothing stores a disputed AMOUNT, which is why
 * `protection_check` already serves that row as `unavailable` and never as
 * `pass`.
 *
 * ⛔ **THIS PARAGRAPH ARGUED FOR DRAWING IT DISABLED AND THE ARGUMENT WAS
 * WRONG.** It cited `BR-SHL-025` — *a control this DEPLOYMENT cannot honour
 * renders disabled with its reason* — and that rule is about a thing some
 * tenant could switch on, which a clerk deserves to see and be told about.
 * **There is no deployment, tenant setting or future flag that makes this radio
 * pressable.** A permanent impossibility offered beside its own refusal is the
 * worst of both: it is the mirror of hard-won law 2, a dead control over a live
 * screen, and on a dialog with three real choices it costs a clerk a decision
 * every single time they open it.
 *
 * ⚠ **THE FACT IS NOT HIDDEN — IT MOVED TO WHERE IT IS A READ.** p143's drawn
 * question *"Disputed bill open?"* is still answered on the record's own
 * protections panel, and `DEF-CUS-6792` is the open row on whether it is
 * answerable at all. **What a disputed bill SHOULD do here is `OQ-CUS-12737`**
 * and it is not decided by removing a control that never worked.
 *
 * ⚠ **A DEVIATION FROM THE DRAWING, RECORDED RATHER THAN QUIET** (B14 rule 41,
 * and its honest half). Decision log, 2026-09-25, lane CUTPATH.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, FormModal } from "@/components/FormModal";

import type { DisconnectRecordDetail } from "./disconnectRecordEndpoints";
import { holdDisconnectCase } from "./disconnectRecordEndpoints";

/** The radio group's own id — the zod path AND what `useFieldError` is asked
 *  for, one string so the two can never drift (`DEF-CUS-6758`). */
const FIELD_KIND = "disconnect-hold-kind";
/** The `Review on` field's id, used the same way. */
const FIELD_REVIEW_ON = "disconnect-hold-review-on";

export function HoldCaseDialog(props: {
  record: DisconnectRecordDetail;
  /** BR-TEN-043 — the business date is the caller's, never a wall clock. */
  today: string;
  /** IS-8 — a date renders and is entered in the TENANT's format. */
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onHeld?: () => void;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const hold = props.record.actions?.hold;
  const kinds = hold?.kinds ?? [];
  const [kind, setKind] = useState(kinds[0] ?? "");
  const [reviewOn, setReviewOn] = useState("");

  // The server's own map, read rather than restated: `required` for a medical
  // certificate and a weather moratorium, `refused` for a payment plan.
  const reviewRule = hold?.review_date?.[kind] ?? "required";
  const reviewNeeded = reviewRule === "required";

  // ⛔ **THE KEYS ARE THE FIELD IDS AND THAT IS LOAD-BEARING — `DEF-CUS-6758`.**
  // `FormModal` DOES validate on submit and DOES block the post; the message is
  // then looked up with `useFieldError(props.id)`, **keyed by the input's id**,
  // while `collectFormErrors` keys its map by the **zod path**. This schema said
  // `review_on` and the field renders as `disconnect-hold-review-on`, so the
  // error was collected correctly and displayed nowhere: the button was live,
  // pressing it did nothing, and the clerk was told nothing at all — which is
  // worse than a refusal (B14 rule 33 wants the button to say what is missing).
  // Naming them identically is the version of this that cannot come apart
  // again; the two strings are now one string.
  const schema = z.object({
    [FIELD_KIND]: z.string().min(1, t("customers.disconnectRecord.hold.error.noReason")),
    [FIELD_REVIEW_ON]: reviewNeeded
      ? z.string().min(1, t("customers.disconnectRecord.hold.error.noReviewDate"))
      : z.string(),
  });

  const caseNo = props.record.case_no?.value ?? "";

  return (
    <FormModal
      title={t("customers.disconnectRecord.hold.title", { case: caseNo })}
      kicker={t("customers.disconnectRecord.hold.lede")}
      schema={schema}
      values={{ [FIELD_KIND]: kind, [FIELD_REVIEW_ON]: reviewOn }}
      submitLabel={t("customers.disconnectRecord.action.hold")}
      onClose={props.onClose}
      onSubmit={async () => {
        await holdDisconnectCase(
          props.record.actions.account_id,
          {
            kind,
            effective_from: props.today,
            // ⚠ **`null` AND NOT `""` FOR A PLAN.** `_optional_date` reads an
            // empty string as a value to parse and refuses it; the plan
            // protection must arrive with no date at all or
            // `record_protection` raises `plan_protection_takes_no_expiry`.
            expires_on: reviewNeeded ? reviewOn : null,
          },
          props.client ?? api,
        );
        props.onHeld?.();
        return { ok: true, toast: t("customers.disconnectRecord.hold.toast") };
      }}
    >
      <fieldset className="border-0 p-0">
        <legend className="text-xs font-semibold uppercase tracking-wide text-accent">
          {t("customers.disconnectRecord.hold.why")}
        </legend>
        <div className="mt-2 flex flex-col gap-2">
          {kinds.map((option) => (
            <label
              key={option}
              className={`flex min-w-0 flex-col gap-1 border p-3 ${
                kind === option ? "cursor-pointer border-accent bg-accent-100" : "cursor-pointer border-divider"
              }`}
            >
              <span className="flex items-center gap-2">
                <input
                  type="radio"
                  name="disconnect-hold-kind"
                  value={option}
                  checked={kind === option}
                  onChange={() => setKind(option)}
                />
                {/* BORROWED, NOT COPIED — `customers.disconnects.protection.*`
                    already names the three in eleven catalogues. */}
                <span className="font-semibold text-text">
                  {t(`customers.disconnects.protection.${option}`)}
                </span>
              </span>
              <span className="pl-6 text-sm text-neutral-700">
                {t(`customers.disconnectRecord.hold.means.${option}`)}
              </span>
            </label>
          ))}

          {/* ⛔ **p144's FOURTH REASON IS NOT OFFERED HERE — `DEF-CUS-6757`.**
              It was drawn DISABLED with the server's sentence under it, on
              `BR-SHL-025`'s authority, and that was the wrong rule for this
              control: `BR-SHL-025` is about something THIS DEPLOYMENT cannot
              honour — a thing some tenant could switch on, which a clerk
              deserves to see. **No deployment, tenant setting or future flag
              makes this one pressable.** `record_protection` refuses a fourth
              kind by name and nothing anywhere stores a disputed amount. A
              permanent impossibility offered beside its own refusal is the
              worst of both, and on a dialog with three real choices it costs a
              clerk a decision every time they open it.
              ⚠ **THE FACT ITSELF IS NOT HIDDEN FROM THE CLERK** — the record's
              own protections panel still answers p143's drawn question
              *"Disputed bill open?"*, where it is a READ rather than an offer
              to act. `OQ-CUS-12737` asks whether it should become a fourth hold
              kind; nothing is decided here. */}
        </div>
      </fieldset>

      {/* ⚠ **THE DATE FIELD IS ABSENT FOR A PAYMENT PLAN, AND THAT IS THE
          SERVER'S RULE RATHER THAN A TIDY-UP.** `BR-CUS-043` holds that
          protection *while the plan is active AND current*, and a missed
          instalment lifts it the next day with no grace (PO 2026-08-12,
          `OQ-170`, *"Immediate"*). A stored date here would be a second and
          slower answer to a question payments answers exactly — which is why
          `record_protection` refuses one by name. */}
      {reviewNeeded ? (
        <DatePickerField
          id={FIELD_REVIEW_ON}
          label={t("customers.disconnectRecord.hold.reviewOn")}
          value={reviewOn}
          onChange={setReviewOn}
          required
          dateFormat={props.dateFormat}
          help={t("customers.disconnectRecord.hold.reviewHelp")}
        />
      ) : (
        <p className="text-sm text-neutral-700" data-testid="disconnect-hold-no-review-date">
          {t("customers.disconnectRecord.hold.noReviewDate")}
        </p>
      )}

      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-accent">
          {t("customers.disconnectRecord.hold.will")}
        </h3>
        <table className="mt-2 w-full text-sm" data-testid="disconnect-hold-effects">
          <thead>
            <tr className="border-b border-neutral-300 text-left text-xs uppercase tracking-wide text-neutral-600">
              <th scope="col" className="py-2 font-medium">
                {t("customers.disconnectRecord.hold.col.then")}
              </th>
              <th scope="col" className="py-2 font-medium">
                {t("customers.disconnectRecord.hold.col.what")}
              </th>
            </tr>
          </thead>
          <tbody>
            {(hold?.effects ?? []).map((effect) => (
              <tr key={effect.code} className="border-b border-neutral-200">
                <td className="py-3 text-neutral-600">
                  {t(`customers.disconnectRecord.hold.when.${effect.when}`)}
                </td>
                <td className="py-3 text-neutral-900" data-effect={effect.code}>
                  {t(`customers.disconnectRecord.hold.effect.${effect.code}`)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </FormModal>
  );
}
