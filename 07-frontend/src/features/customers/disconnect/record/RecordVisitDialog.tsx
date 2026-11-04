// ── Trace ──────────────────────────────────────────────
// Change:   **BR-CUS-1083 · PO ruling 2026-09-20**, verbatim: *"The register
//           reflects reality. Today a failed visit is invisible and the case
//           looks untouched."* Closes `OQ-383`, open since 2026-08-25.
// Drawing:  ⚠ **NONE.** p135–p144 of `02 Accounts Menu Blueprint.pdf` (read as
//           IMAGES, B14 rule 42) draw no visit screen; the section's own
//           `Why Blocked` note says *"what happens when a crew attends and does
//           not cut … those are rulings, not code."* Built to the shared kit
//           and to `HoldCaseDialog` (p144), the nearest worked example of a
//           reason-radio dialog on this same record.
// Rules:    BR-CUS-1083 · BR-CUS-039 (the three stop reasons) · BR-CUS-037
//           (customers writes no financial table) · B14 rule 6 (the danger tier
//           is for destructive commits — this is not one) · rule 31 · rule 33
//           (label ≤ 3 words · fact ≤ 6 · RATIONALE is zero words on screen) ·
//           rule 38 · rule 43 · BR-SHL-025
// ───────────────────────────────────────────────────────
/**
 * `Record visit` — the crew attended and did not cut.
 *
 * ════════════════════════════════════════════════════════════════════════
 * EVERY OUTCOME CARRIES WHERE IT SENDS THE CASE
 * ════════════════════════════════════════════════════════════════════════
 * The PO ruled *"each must move the case somewhere, not merely annotate it"*,
 * and that half is the half a clerk has to know **before** pressing. Three of
 * the four take the cut date off the calendar and put the case back to
 * `At notice`; a doorstep dispute stops the ladder. A dialog that listed four
 * words with no consequences would be asking somebody to guess.
 *
 * ⚠ **THE FOUR AND THEIR MOVES COME FROM THE SERVER** (`actions.visit.outcomes`),
 * never from a list typed here. CLAUDE.md's hard-won law 2 in its silent form:
 * the eleventh service exists, the API serves it, `tsc` and every test pass,
 * and the screen simply never offers it. A fifth outcome would reach this
 * dialog on its own, with its own destination beside it.
 *
 * ════════════════════════════════════════════════════════════════════════
 * ⛔ WHAT IT DOES NOT DO, AND THE SCREEN SAYS SO
 * ════════════════════════════════════════════════════════════════════════
 *   * **It takes no money.** A crew holding a cheque is not a posted payment,
 *     and `apps/customers` writes no financial table. Recording *paid at the
 *     door* takes the cut date off and nothing else; the payment goes on the
 *     payments screen and the ladder stops itself when it posts.
 *   * **It sends nobody back out.** A new visit is a NEW CUT DATE, set in the
 *     wizard — which is the act that serves the notice the date is counted
 *     from. There is no *re-schedule* here and inventing one would be writing a
 *     notice period nobody served.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, FormModal, TextField } from "@/components/FormModal";

import type { DisconnectRecordDetail } from "./disconnectRecordEndpoints";
import { recordDisconnectCaseVisit } from "./disconnectRecordEndpoints";

export function RecordVisitDialog(props: {
  record: DisconnectRecordDetail;
  /** BR-TEN-043 — the business date is the caller's, never a wall clock. */
  today: string;
  /** IS-8 — a date renders and is entered in the TENANT's format. */
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onRecorded?: () => void;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const record = props.record;
  const panel = record.actions?.visit;
  const outcomes = panel?.outcomes ?? [];
  const [outcome, setOutcome] = useState(outcomes[0]?.code ?? "");
  // ⚠ **THE DATE DEFAULTS TO TODAY AND IS NOT FIXED TO IT.** A failed visit is
  // usually recorded the next morning, and a date this dialog forced would put
  // a crew at a meter on a day nobody was there.
  const [visitedOn, setVisitedOn] = useState(props.today);
  const [note, setNote] = useState("");

  const schema = z.object({
    // `DEF-CUS-6758` — THE KEY IS THE FIELD ID. `FormModal` looks the message
    // up with `useFieldError(props.id)` and `collectFormErrors` keys its map by
    // the zod path, so two different names mean a collected error that renders
    // nowhere: the button stays live, the post is blocked, and the clerk is told
    // nothing at all. One string, so they cannot drift.
    "disconnect-visit-outcome": z.string().min(1, t("customers.disconnectRecord.visit.error.noOutcome")),
    "disconnect-visit-on": z.string().min(1, t("customers.disconnectRecord.visit.error.noDate")),
  });

  const caseNo = record.case_no?.value ?? "";

  return (
    <FormModal
      title={t("customers.disconnectRecord.visit.title", { case: caseNo })}
      kicker={t("customers.disconnectRecord.visit.lede")}
      schema={schema}
      values={{ "disconnect-visit-outcome": outcome, "disconnect-visit-on": visitedOn }}
      submitLabel={t("customers.disconnectRecord.action.recordVisit")}
      // ⚠ **NOT THE DANGER TIER** (B14 rule 6). Recording what a crew found
      // takes nothing away from anybody; it is the act that stops a case
      // claiming a cut is still due.
      commitBlocked={
        panel?.can_record === false
          ? t("customers.disconnectRecord.refused.visit_not_scheduled", {
              defaultValue: t("customers.disconnectRecord.refused.generic"),
            })
          : undefined
      }
      onClose={props.onClose}
      onSubmit={async () => {
        await recordDisconnectCaseVisit(
          record.actions.account_id,
          {
            on_date: visitedOn,
            outcome,
            // ⚠ **OMITTED RATHER THAN SENT EMPTY.** *Nobody wrote a note* and
            // *somebody wrote nothing* are the same fact, and two spellings of
            // one fact is how a screen draws a blank line where it meant an
            // absence.
            ...(note.trim() ? { note: note.trim() } : {}),
          },
          props.client ?? api,
        );
        props.onRecorded?.();
        return { ok: true, toast: t("customers.disconnectRecord.visit.toast") };
      }}
    >
      <fieldset className="border-0 p-0">
        <legend className="text-xs font-semibold uppercase tracking-wide text-accent">
          {t("customers.disconnectRecord.visit.what")}
        </legend>
        <div className="mt-2 flex flex-col gap-2">
          {outcomes.map((option) => (
            <label
              key={option.code}
              data-outcome={option.code}
              className={`flex min-w-0 cursor-pointer flex-col gap-1 border p-3 ${
                outcome === option.code ? "border-accent bg-accent-100" : "border-divider"
              }`}
            >
              <span className="flex items-center gap-2">
                <input
                  type="radio"
                  name="disconnect-visit-outcome"
                  value={option.code}
                  checked={outcome === option.code}
                  onChange={() => setOutcome(option.code)}
                />
                <span className="font-semibold text-text">
                  {t(`customers.disconnectRecord.visit.outcome.${option.code}`)}
                </span>
              </span>
              {/* WHERE IT SENDS THE CASE — a FACT, ≤ 6 words (B14 rule 33), and
                  the server's own mapping rather than this screen's opinion. */}
              <span className="pl-6 text-sm text-neutral-700" data-move={option.move}>
                {t(`customers.disconnectRecord.visit.move.${option.move}`)}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <DatePickerField
        id="disconnect-visit-on"
        label={t("customers.disconnectRecord.visit.visitedOn")}
        value={visitedOn}
        onChange={setVisitedOn}
        required
        dateFormat={props.dateFormat}
        help={t("customers.disconnectRecord.visit.visitedOnHelp")}
      />

      {/* The crew's own sentence — the `What happened` line p137 draws on the
          stop dialog, reused here because it is the same kind of evidence about
          the same kind of act. OPTIONAL: a required note would refuse the
          recording, and a refused recording leaves the case advertising a cut
          date that has passed. */}
      <TextField
        id="disconnect-visit-note"
        label={t("customers.disconnectRecord.visit.note")}
        value={note}
        onChange={setNote}
        help={t("customers.disconnectRecord.visit.noteHelp")}
      />

      {/* ⛔ **NOBODY IS SENT BACK OUT.** Drawn as a fact so a clerk does not
          wait for a crew this act never dispatched (hard-won law 2's mirror). */}
      <p
        role="note"
        data-testid="disconnect-visit-no-follow-up"
        className="border border-divider bg-neutral-100 px-4 py-3 text-sm font-semibold text-neutral-900"
      >
        {t("customers.disconnectRecord.visit.noFollowUp")}
      </p>

      {/* What is already on this case, newest first. Absent on the first visit
          rather than drawn as an empty table. */}
      {panel?.recorded?.length ? (
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-accent">
            {t("customers.disconnectRecord.visit.already")}
          </h3>
          <table className="mt-2 w-full text-sm" data-testid="disconnect-visit-recorded">
            <tbody>
              {panel.recorded.map((row) => (
                <tr key={row.visit_id} className="border-b border-neutral-200">
                  <td className="py-2 text-neutral-600">{row.visited_on}</td>
                  <td className="py-2 text-neutral-900" data-outcome={row.outcome}>
                    {t(`customers.disconnectRecord.visit.outcome.${row.outcome}`, {
                      defaultValue: row.outcome,
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </FormModal>
  );
}
