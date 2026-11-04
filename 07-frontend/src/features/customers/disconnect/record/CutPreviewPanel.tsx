// ── Trace ──────────────────────────────────────────────
// Change:   CR-125-BRC07 — p143's `WHAT A CUT WOULD DO`, and its red banner.
// Rules:    BR-CUS-103 (base charges STOP at the cut) · BR-CUS-104 (the fee is
//           owed AT the cut) · BR-CUS-107 (`Disconnected`) · BR-BIL-007 (a fee
//           is the tenant's charge code, never a literal) · B14 rule 43 ·
//           rule 33 · CLAUDE.md rule 2
// ───────────────────────────────────────────────────────
/**
 * `WHAT A CUT WOULD DO` — a PREVIEW, and the heading says so.
 *
 * ⚠ **THE HEADING RUNS TO FIVE WORDS, TWO OVER B14 RULE 33's CAP, AND THAT IS
 * FILED RATHER THAN QUIETLY TAKEN EITHER WAY.** Every shorter form this lane
 * tried — *The cut*, *Cut preview* — turns a PREVIEW into a RECORD, and the
 * difference is the entire reason p143 carries a red banner under this panel.
 * A clerk who reads *The cut* on a case that has not been cut has been told
 * something false by a heading.
 *
 * ⛔ **EVERY CUT ON EVERY TENANT IN THIS TREE REFUSES ON THE RECONNECTION
 * CHARGE CODE, AND THIS PANEL RENDERS THE SERVER'S REFUSAL RATHER THAN A
 * NUMBER.** Three sources disagree: the drawing and the signed worked figure
 * say one amount, the seeded catalogue spells the code differently and prices
 * it at another, and `commit_cut` looks up a third spelling. **That is a money
 * figure and a fact only the Product Owner holds** — `CR-125-BRC07` §4 has it
 * as the one number they must settle. No literal reaches this file.
 */
import { useTranslation } from "react-i18next";

import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Panel } from "@/components/Panel";

import type { DisconnectRecordDetail } from "./disconnectRecordEndpoints";
import { Fact, FactRow, MoneyRow, UnbilledDaysRow } from "./recordFacts";

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-6051 — WHICH ANSWER THE SERVER GAVE ABOUT THE ACCOUNT'S STATUS
// ══════════════════════════════════════════════════════════════════════════
/**
 * `BR-CUS-107`'s `Disconnected` is written **only when the days up to the cut
 * are billed, or provably have nothing left to bill** (CR-052 W0, PO ruling
 * 2026-08-30). Until 2026-09-20 no cut had ever committed on any tenant, so
 * that condition could never be observed — and it never reached the copy.
 *
 * ⚠ **ON THE FIRST REAL CUTS IT FIRED.** `A-11721`'s case `DSC-26-0002` is
 * `cut` and the account still reads **Active**; `A-11340` read **Marked
 * disconnect**. Billing could not raise the final bill because the commercial
 * electric base charge prices per connection size and the connection has none.
 * **The hold is CORRECT** — writing the status removes the account from
 * `selectors.accounts_for_bill_run` with days still unbilled — and it is the
 * screen's silence about it that was the defect.
 *
 * ⚠ **THE ANSWER IS ON THE WIRE.** `commit_cut` returns
 * `account_status_written` and a whole `account_status_held` block, and
 * `what_a_cut_would_do.account_status_becomes` carries a CODE. This resolver
 * turns that code into a variant so neither surface states a constant.
 *
 * ⚠ **IT IS SHARED WITH `MarkAsCutDialog` ON PURPOSE**, the same way
 * `protectionAnswerKey` lives in `ProtectionsPanel` and is imported by the
 * dialog. The code→variant decision is ONE decision; the WORDS are two,
 * because a panel row is a FACT (≤ 6 words) and a dialog row is a CONSEQUENCE
 * before an irreversible act (≤ 6 words per sentence, at most two) — B14
 * rule 33. One resolver, two sets of copy.
 */
export type CutStatusAnswer = "written" | "held" | "unstated";

/** `disconnects.DISCONNECTED_STATUS_ASSIGNED` — the status IS written. */
export const CUT_STATUS_WRITTEN_CODE = "disconnected_status_assigned_at_the_cut";
/** `disconnects.CUT_BILL_BLOCKED_SO_STATUS_HELD` — it is deliberately HELD. */
export const CUT_STATUS_HELD_CODE = "cut_bill_blocked_status_not_written";

/**
 * ⚠ **AN UNKNOWN CODE ANSWERS `unstated`, NEVER `written`.** Falling through to
 * the promise is precisely this defect: the screen would go on claiming
 * `Disconnected` for an answer nobody taught it to read. On this row, saying
 * nothing is the only safe side of the fence.
 */
export function cutStatusAnswer(code: string | null | undefined): CutStatusAnswer {
  if (code === CUT_STATUS_WRITTEN_CODE) {
    return "written";
  }
  if (code === CUT_STATUS_HELD_CODE) {
    return "held";
  }
  return "unstated";
}

/** The panel's own copy for each answer — a FACT, so ≤ 6 words (B14 rule 33). */
const PANEL_STATUS_KEY: Record<CutStatusAnswer, string> = {
  written: "customers.disconnectRecord.cut.statusValue",
  held: "customers.disconnectRecord.cut.statusHeldValue",
  unstated: "customers.disconnectRecord.cut.statusNotStated",
};

/**
 * ⚠ **IT TAKES THE TENANT'S ZONE AND FORMAT SINCE 2026-09-21, AND IT IS THE
 * FIRST DATE THIS PANEL HAS EVER DRAWN.** `days_not_billed` is a date RANGE
 * (PO ruling 2026-09-21), and IS-8 says a date renders in the tenant's zone
 * AND format, never ISO — so the two props travel here exactly as they already
 * travel to the three sibling panels on this screen.
 */
export function CutPreviewPanel(props: {
  record: DisconnectRecordDetail;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const cut = props.record.what_a_cut_would_do;

  return (
    <Panel title={t("customers.disconnectRecord.section.cut")}>
      <dl className="mt-1" data-testid="disconnect-record-cut">
        {/* ⚠ **SERVICE CODES ARE TRANSLATED, NEVER PRINTED.** `electric` is a
            stored code and B14 rule 31 keeps it off the screen; the catalogue
            already carries all eleven services' names in eleven languages, so
            an eleventh service appears here on its own — which is hard-won
            law 2's `SignupWizard` lesson applied before it can bite. */}
        <Fact
          label={t("customers.disconnectRecord.cut.services")}
          fact={cut?.services_affected}
          absentLabel={t("customers.disconnectRecord.absent.noServices")}
          render={(value: string[]) =>
            value
              .map((code) => t(`rating.service.${code}`, { defaultValue: code }))
              .join(" · ")
          }
        />
        <MoneyRow
          label={t("customers.disconnectRecord.cut.fee")}
          money={cut?.reconnection_fee}
          absentLabel={t("customers.disconnectRecord.absent.noFee")}
          suffix={t("customers.disconnectRecord.cut.feeWhen")}
        />
        {/* ⚠ **BR-CUS-107, READ FROM THE PAYLOAD AND NO LONGER A CONSTANT
            (DEF-CUS-6051).** This row said `Disconnected` unconditionally, on
            every case including ones already cut whose status was HELD. The
            server names WHICH answer applies on
            `what_a_cut_would_do.account_status_becomes.code`, so the sentence
            is chosen by that code. The code travels as a `data-` attribute so a
            browser walk can see which answer rendered — never as prose on
            screen (DEF-332 · G28 · B14 rule 33's zero-words-of-rationale). */}
        <FactRow label={t("customers.disconnectRecord.cut.status")}>
          <span data-cut-status={cutStatusAnswer(cut?.account_status_becomes?.code)}>
            {t(PANEL_STATUS_KEY[cutStatusAnswer(cut?.account_status_becomes?.code)])}
          </span>
        </FactRow>
        <MoneyRow
          label={t("customers.disconnectRecord.cut.toClear")}
          money={cut?.to_clear_before_reconnection}
          absentLabel={t("customers.disconnectRecord.absent.noFee")}
        />
        {/* BR-CUS-103 (PO 2026-08-25, `OQ-380`, *"no"*) — base charges STOP at
            the cut. `DSC-02.4`'s drawn `Will` column said the opposite until
            that ruling reversed it, which is why this row states the current
            rule rather than the drawing's older sentence. */}
        <FactRow label={t("customers.disconnectRecord.cut.baseCharges")}>
          {t("customers.disconnectRecord.cut.baseChargesValue")}
        </FactRow>
        {/* ⚠ **THE DAYS NOBODY HAS BILLED — PO ruling 2026-09-21.** A cut may
            now be COMPLETED with no final bill, and a `disconnected` account
            leaves the bill run, so these days would otherwise stop being
            anywhere on the day the status was written. The PO ruled WHO raises
            the bill, not that the days stop mattering. The server derives the
            window on every read, so this row removes ITSELF once billing's
            single-bill workflow covers the cut day — nothing here clears a
            flag, and nothing here can go on claiming an absence that ended
            (hard-won law 1). */}
        <UnbilledDaysRow
          days={cut?.days_not_billed}
          label={t("customers.disconnectRecord.cut.daysNotBilled")}
          unknownLabel={t("customers.disconnectRecord.cut.daysNotBilledUnknown")}
          testId="disconnect-record-cut-unbilled"
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

      {/* ⛔ **THE PANEL PROMISES `Status becomes Disconnected` FOUR ROWS UP.
          ON A CUT WHERE THAT DID NOT HAPPEN, IT NOW SAYS SO** —
          `DEF-CUS-6064`. `commit_cut` has returned `cut_bill` and
          `account_status_held` since 2026-08-30 and nothing in this product
          had ever read either, so a cut case sat beside an account still
          reading `active` with no sentence anywhere explaining why.
          `role="alert"`: this is a state a person has to act on, unlike the
          standing banner below it. B14 rule 33 — two sentences, six words or
          fewer; the server's `detail` is RATIONALE and stays off the page. */}
      {cut?.cut_unfinished ? (
        <p
          role="alert"
          data-testid="disconnect-record-cut-unfinished"
          className="mt-4 border border-warning-500 bg-warning-100 px-4 py-3 text-sm font-semibold text-warning-700"
        >
          {t("customers.disconnectRecord.cut.unfinished")}{" "}
          {t("customers.disconnectRecord.cut.unfinishedBody")}
        </p>
      ) : null}

      {/* p143's red banner. TWO sentences of six words or fewer — B14 rule 33's
          consequence cap, and *two sentences of six beat one sentence of
          twelve*. `role="note"`: a standing fact, not an alert. */}
      <p
        role="note"
        data-testid="disconnect-record-not-a-closeout"
        className="mt-4 border border-danger-500 bg-danger-100 px-4 py-3 text-sm font-semibold text-danger-700"
      >
        {t("customers.disconnectRecord.cut.banner")}{" "}
        {t("customers.disconnectRecord.cut.bannerBody")}
      </p>
    </Panel>
  );
}
