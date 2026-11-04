// ── Trace ──────────────────────────────────────────────
// Rule:    **PO ruling 2026-09-21** — *"in single bill we have final bill
//          workflow - so if clark want to complete the bill he can do it from
//          there - we will need to allow clark to complete the cut request
//          later without bill."* COMPLETING the cut request and RAISING its
//          final bill are two acts, and this dialog is where a clerk says
//          which one they are performing.
// Defect:  DEF-CUS-6063 — a cut whose final bill billing refused could never
//          be finished: `commit_cut` refuses `already_cut` by name and
//          BR-CUS-107's status is written from `commit_cut` and nowhere else.
//          DEF-CUS-6064 — and no screen ever said so.
// Rules:   BR-CUS-107 (`Disconnected` is written only when the days up to the
//          cut are billed) · BR-CUS-103 (base stops at the cut) ·
//          PO ruling 2026-08-30 (the disconnect is the WHOLE event) ·
//          B14 rule 43 (a piece of UI is a COMPONENT) · rule 33 (a label ≤ 3
//          words · a fact ≤ 6 · an instruction ≤ 6 per sentence · RATIONALE is
//          zero words on screen) · rule 6 (the danger tier is for a
//          DESTRUCTIVE commit, and this one is not) · CLAUDE.md rule 2
// ───────────────────────────────────────────────────────
/**
 * `Finish disconnection` — the second half of a cut that stopped half-way.
 *
 * ⚠ **IT IS NOT THE DANGER TIER, AND THAT IS NOT AN OVERSIGHT.** B14 rule 6
 * puts danger on a DESTRUCTIVE commit; `Mark as cut` takes a household's
 * supply away and wears it. This takes nothing away — the supply is already
 * off. It bills days the customer has already used and writes the status that
 * cut should have written, which is the act that stops them being billed
 * again. Dressing it in red would teach a clerk that red means *"important"*
 * rather than *"this cannot be undone"*.
 *
 * ⚠ **IT ASKS ONE QUESTION AND NO MORE, AND THE LINE IS NOT ARBITRARY.** This
 * paragraph read *"IT ASKS FOR NOTHING AND THAT IS THE WHOLE DESIGN"* until
 * 2026-09-21, and its reason still holds for every DATE and every FIGURE: the
 * window is the case's own cut date, the money is the engine's, the status is
 * BR-CUS-107's, and a date field here would be a clerk choosing how many days a
 * customer pays for. **The one thing the server cannot know is which of two
 * acts the clerk came to perform** — raise the final bill now, or complete the
 * cut request without one and raise it later from billing's own single-bill
 * workflow. So that is the only control, and it is a one-of-two rather than a
 * tick: both answers DO something, and a tick would make one of them the
 * unmarked default nobody chose.
 *
 * ⚠ **AND THE DAYS NOBODY BILLED ARE ON SCREEN BEFORE THE COMMIT, NOT AFTER
 * IT.** A `disconnected` account leaves the bill run, so completing without a
 * bill is the act that strands them. The PO ruled WHO raises the bill, not
 * that the days stop mattering — a clerk who is about to strand a window reads
 * it first, in the tenant's own date format.
 *
 * ⚠ **A REFUSED BILL IS SHOWN, NOT SWALLOWED.** The server answers 200 with
 * `finished: false` and the ENGINE's own sentence — *"This connection's size
 * is not recorded. Record the connection's size."* Until this dialog existed
 * that sentence reached an `audit_log` row and nothing else, and the person
 * who could act on it was the one person never shown it.
 *
 * ⚠ **THAT QUOTE WAS 63 WORDS UNTIL 2026-09-24 (`DEF-CUS-6550`), AND THIS
 * SCREEN NEEDED NO CHANGE FOR IT TO SHRINK — WHICH IS THE PARAGRAPH BELOW
 * WORKING.** The engine COMPOSES the sentence; this dialog LIFTS it. It used
 * to read *"service electric: base charge code BASE-E prices per connection
 * size and states no amount for size None. An unpriced size is REFUSED and
 * never substituted (PO ruling 2026-08-28) … Price that size on the charge
 * code, or record the connection's size. The run continues for every other
 * account."* — five times over B14 rule 33's cap, naming a ruling date and
 * printing a Python `None`, on this dialog as well as on ACC-06 step 3.
 * **Re-quoted here rather than left standing, because a comment quoting a
 * sentence the engine has stopped producing is hard-won law 1**, and nothing
 * in this repo checks a comment against the code it describes.
 *
 * ⚠ **BOTH HALVES ARE DRAWN, AND THE SPLIT IS `BR-SHL-020 r2`'s.** That rule
 * DROPS a server `detail` from a refusal envelope, because sixteen catalogue
 * strings once interpolated one and a clerk read engineering prose with BR-ids
 * in it (`DEF-322`). So the envelope carries a CATALOGUE line — short, in the
 * clerk's language, bound by B14 rule 33 — and the engine's sentence is
 * rendered BESIDE it rather than inside it. It is quoted rather than
 * paraphrased for `cut_readiness`' stated reason on this same screen: *"the
 * sentences are LIFTED, never restated"*, because a paraphrase of a refusal
 * goes stale the day the engine's words change and nothing notices.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FormModal, SegmentedField } from "@/components/FormModal";

import type { DisconnectFinishResult, DisconnectRecordDetail } from "./disconnectRecordEndpoints";
import { finishDisconnectCut } from "./disconnectRecordEndpoints";
import { FactRow, UnbilledDaysRow } from "./recordFacts";

/**
 * The one answer this dialog collects — WHICH OF TWO ACTS (PO 2026-09-21).
 *
 * ⚠ **`raise` IS THE DEFAULT AND IT IS THE SAFE ONE**, which is hard-won law 3
 * read onto a form: the option that leaves days billed by nobody is the option
 * a clerk has to type. Nothing is defaulted to `without`, on any path, ever —
 * including the path where billing has just refused.
 */
const RAISE_THE_BILL = "raise";
const WITHOUT_A_BILL = "without";
const CHOICE = z.object({ bill: z.enum([RAISE_THE_BILL, WITHOUT_A_BILL]) });

export function FinishCutDialog(props: {
  record: DisconnectRecordDetail;
  /** IS-8 — a date renders in the TENANT's zone AND format, never ISO. */
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onFinished?: () => void;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const record = props.record;
  // The server's answer when it still cannot bill. Held here rather than
  // toasted so the sentence STAYS on screen while the clerk reads it.
  const [refused, setRefused] = useState<DisconnectFinishResult | null>(null);
  // WHICH ACT — PO ruling 2026-09-21. `raise` until a clerk says otherwise.
  const [bill, setBill] = useState<string>(RAISE_THE_BILL);
  const withoutBill = bill === WITHOUT_A_BILL;
  const caseNo = record.case_no?.value ?? "";

  return (
    <FormModal
      title={t("customers.disconnectRecord.finishDialog.title", { case: caseNo })}
      kicker={t("customers.disconnectRecord.finishDialog.lede")}
      schema={CHOICE}
      values={{ bill }}
      submitLabel={t(
        withoutBill
          ? "customers.disconnectRecord.finishDialog.commitWithout"
          : "customers.disconnectRecord.action.finishCut",
      )}
      onClose={props.onClose}
      onSubmit={async () => {
        const answer = await finishDisconnectCut(
          record.actions.account_id,
          props.client ?? api,
          withoutBill,
        );
        if (!answer.finished) {
          // ⚠ **THE DIALOG STAYS OPEN.** `ok: false` keeps the frame up, which
          // is what a refusal needs: a toast that disappears is not a sentence
          // somebody can act on. The envelope carries a CATALOGUE key and no
          // `detail` — see the split above.
          setRefused(answer);
          return {
            ok: false,
            error: {
              code: "BIZ-RULE",
              message_key: "customers.disconnectRecord.finishDialog.stillBlocked",
            },
          };
        }
        props.onFinished?.();
        // Two acts, two sentences: a completion with no bill says so, because
        // *"the disconnection is finished"* over a cut nobody billed is the
        // product telling the clerk something that is not true.
        return {
          ok: true,
          toast: t(
            withoutBill
              ? "customers.disconnectRecord.finishDialog.toastWithout"
              : "customers.disconnectRecord.finishDialog.toast",
          ),
        };
      }}
    >
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-accent">
          {t("customers.disconnectRecord.finishDialog.what")}
        </h3>
        <dl className="mt-1" data-testid="disconnect-finish-what">
          <FactRow label={t("customers.disconnectRecord.cutDialog.account")}>
            {record.the_case?.account_no?.value}
            {record.customer_name?.value ? ` · ${record.customer_name.value}` : null}
          </FactRow>
          <FactRow label={t("customers.disconnectRecord.finishDialog.cutOn")}>
            {/* IS-8 — the tenant's zone and format. An ISO string here is the
                one thing a clerk never reads on any other screen. */}
            {record.the_case?.cut_date?.value ?? record.cut_date?.value ? (
              <DateCell
                value={(record.the_case?.cut_date?.value ?? record.cut_date?.value) as string}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            ) : null}
          </FactRow>
          {/* ⚠ **THE DAYS THIS ACT MAY STRAND, BEFORE IT IS COMMITTED.**
              Completing without a bill writes `Disconnected`, and a
              `disconnected` account leaves the bill run — so this window stops
              being picked up by any ordinary run the moment the clerk commits.
              It is drawn on BOTH answers, because it is equally true that
              raising the bill is what covers it. Same component as the record
              panel (B14 rule 43). */}
          <UnbilledDaysRow
            days={record.what_a_cut_would_do?.days_not_billed}
            label={t("customers.disconnectRecord.cut.daysNotBilled")}
            unknownLabel={t("customers.disconnectRecord.cut.daysNotBilledUnknown")}
            testId="disconnect-finish-unbilled"
            render={(from, to, days) => (
              <>
                <DateCell value={from} timeZone={props.timeZone} dateFormat={props.dateFormat} />
                {" – "}
                <DateCell value={to} timeZone={props.timeZone} dateFormat={props.dateFormat} />
                {" · "}
                {t("customers.disconnectRecord.cut.daysCount", { count: days })}
              </>
            )}
          />
        </dl>
      </section>

      {/* ── THE ONE QUESTION: WHICH OF TWO ACTS (PO ruling 2026-09-21) ──────
          B14 rule 38 — where a drawing and our UI rules disagree about how a
          FORM is built, the UI rules win; the kit's one-of-N control is
          `SegmentedField` and this adds no second opinion about radios. */}
      <SegmentedField
        id="disconnect-finish-bill"
        label={t("customers.disconnectRecord.finishDialog.billLabel")}
        value={bill}
        onChange={setBill}
        required
        options={[
          {
            value: RAISE_THE_BILL,
            label: t("customers.disconnectRecord.finishDialog.billRaise"),
          },
          {
            value: WITHOUT_A_BILL,
            label: t("customers.disconnectRecord.finishDialog.billWithout"),
          },
        ]}
      />

      {/* B14 rule 33: two sentences, six words or fewer each. */}
      <p className="text-sm text-neutral-700" data-testid="disconnect-finish-will">
        {t(
          withoutBill
            ? "customers.disconnectRecord.finishDialog.willWithout"
            : "customers.disconnectRecord.finishDialog.will",
        )}
      </p>

      {/* ⛔ THE ENGINE'S OWN SENTENCE, VISIBLE, AFTER A REFUSED ATTEMPT. */}
      {refused ? (
        <p
          role="alert"
          data-testid="disconnect-finish-refused"
          className="border border-danger-500 bg-danger-100 px-4 py-3 text-sm text-danger-700"
        >
          {/* The frame's own message already carries the catalogue line; this
              label is the two words that say WHOSE sentence follows. */}
          <span className="font-semibold">
            {t("customers.disconnectRecord.finishDialog.billingSays")}
          </span>{" "}
          <span data-testid="disconnect-finish-engine-sentence">
            {refused.cut_bill?.detail ?? ""}
          </span>
        </p>
      ) : null}
    </FormModal>
  );
}
