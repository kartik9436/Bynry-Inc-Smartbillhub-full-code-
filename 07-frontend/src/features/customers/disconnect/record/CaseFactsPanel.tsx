// ── Trace ──────────────────────────────────────────────
// Change:   CR-125-BRC07 — p143's first panel, `THE CASE`. Six drawn rows.
// Rules:    B14 rule 43 (a component, addressable on its own) · rule 31 (the
//           account NUMBER, never its id; the tier CODE is translated) ·
//           rule 33 (labels ≤ 3 words) · CLAUDE.md rule 2 (money at 2dp)
// ───────────────────────────────────────────────────────
/**
 * `THE CASE` — account · owed · oldest debt · tier · cut date · raised by.
 *
 * ⛔ **TWO OF THE SIX DRAWN ROWS HAVE NO SOURCE ANYWHERE IN THE PRODUCT** and
 * both are drawn as a stated absence rather than left off the page:
 *
 *   * `Oldest debt · 62 days past due` — no column, no read, no seam answers
 *     how old the oldest unpaid item is.
 *   * the NAME half of `Raised by · S. Ortiz · 04/14/2026` — `disconnect_cases`
 *     has `opened_on` and no actor column. **The DATE half is real and IS
 *     drawn**, as its own row, because an absence covering both would hide a
 *     date the table actually holds.
 *
 * Leaving either row off would be worse than showing it empty: a clerk who
 * cannot see the row cannot know the product does not hold it, and the next
 * lane derives it from something nearby.
 */
import { useTranslation } from "react-i18next";

import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Panel } from "@/components/Panel";

import { CaseVisitValue } from "./CaseVisitValue";
import type { DisconnectCaseVisits, DisconnectRecordDetail } from "./disconnectRecordEndpoints";
import { Fact, MoneyRow } from "./recordFacts";

export function CaseFactsPanel(props: {
  record: DisconnectRecordDetail;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const theCase = props.record.the_case;
  const day = (iso: string) => (
    <DateCell value={iso} timeZone={props.timeZone} dateFormat={props.dateFormat} />
  );

  return (
    <Panel title={t("customers.disconnectRecord.section.theCase")}>
      <dl className="mt-1" data-testid="disconnect-record-case">
        <Fact
          label={t("customers.disconnectRecord.fact.account")}
          fact={theCase?.account_no}
          absentLabel={t("customers.disconnectRecord.absent.notRecorded")}
          render={(value: string) => value}
        />
        <MoneyRow
          label={t("customers.disconnectRecord.fact.owed")}
          money={theCase?.owed}
          absentLabel={t("customers.disconnectRecord.absent.notReadable")}
        />
        {/* ⛔ The first of the two. */}
        <Fact
          label={t("customers.disconnectRecord.fact.oldestDebt")}
          fact={theCase?.oldest_debt}
          absentLabel={t("customers.disconnectRecord.absent.noAge")}
          render={(value: string) => value}
        />
        {/* A stored CODE is never a visible value (B14 rule 31) — what a clerk
            reads is the notice vocabulary this product already has in eleven
            catalogues. `customers.disconnect.notice.*` is BORROWED rather than
            copied: minting `disconnectRecord.tier.*` would be eleven new
            strings free to drift from eleven that exist, which is the reasoning
            B14 rule 34 settles for `Recorded`. */}
        <Fact
          label={t("customers.disconnectRecord.fact.tier")}
          fact={theCase?.tier}
          absentLabel={t("customers.disconnectRecord.absent.noneYet")}
          render={(value: string) =>
            t(`customers.disconnect.notice.${value}`, { defaultValue: "" })
          }
        />
        <Fact
          label={t("customers.disconnectRecord.fact.cutDate")}
          fact={theCase?.cut_date}
          absentLabel={t("customers.disconnectRecord.absent.noCutDate")}
          render={(value: string) => day(value)}
        />
        {/* `DEF-CUS-9696` — the crew the wizard sent, beside the date it was
            sent for. Borrows the move record's words (rule 34). */}
        <Fact
          label={t("customers.moveRecord.owed.visit")}
          fact={props.record.work_orders}
          absentLabel={t("customers.disconnectRecord.absent.noneYet")}
          render={(value: DisconnectCaseVisits) => <CaseVisitValue visits={value} />}
        />
        {/* `DEF-CUS-10657` — PO C1 2026-10-29, *"Restore = Reconnect
            request"*: the request's status is its reconnect jobs, drawn the
            same way as the cut visit above. Absent until a request exists. */}
        {props.record.reconnect_work_orders ? (
          <Fact
            label={t("customers.disconnectRecord.fact.reconnectVisit")}
            fact={props.record.reconnect_work_orders}
            absentLabel={t("customers.disconnectRecord.absent.noneYet")}
            render={(value: DisconnectCaseVisits) => <CaseVisitValue visits={value} />}
          />
        ) : null}
        <Fact
          label={t("customers.disconnectRecord.fact.openedOn")}
          fact={theCase?.opened_on}
          absentLabel={t("customers.disconnectRecord.absent.notRecorded")}
          render={(value: string) => day(value)}
        />
        {/* ⛔ The second. Its absence label says *the name is not kept* and
            never *nobody* — somebody opened this case, and the difference
            between *nobody did* and *we did not record who* is the whole
            reason it is a row rather than a blank. */}
        <Fact
          label={t("customers.disconnectRecord.fact.raisedBy")}
          fact={theCase?.raised_by}
          absentLabel={t("customers.disconnectRecord.absent.noName")}
          render={(value: string) => value}
        />
      </dl>
    </Panel>
  );
}
