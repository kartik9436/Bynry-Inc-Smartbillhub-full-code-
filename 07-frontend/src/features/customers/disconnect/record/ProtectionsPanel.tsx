// ── Trace ──────────────────────────────────────────────
// Change:   CR-125-BRC07 — p143's `PROTECTIONS CHECKED`. Four questions, and
//           the fourth cannot be answered.
// Rules:    BR-CUS-039 · BR-CUS-043 · BR-CUS-096 · B14 rule 43 · rule 33
// ───────────────────────────────────────────────────────
/**
 * `PROTECTIONS CHECKED` — four questions, **three answerable**.
 *
 * ⚠ **`unavailable` IS NOT `pass`, AND THAT IS THE WHOLE POINT OF THE THIRD
 * VALUE.** Nothing in this repository stores a disputed AMOUNT — no model, no
 * table, no seam — so the drawn *Disputed bill open?* row answers *unavailable*
 * rather than *No*. A green clearance derived from a table that does not exist
 * would authorise a cut.
 *
 * ⚠ **THE DRAWING GIVES A `CHECKED` DATE PER ROW AND THE PAYLOAD CARRIES ONE
 * FOR ALL FOUR, SO ONE IS DRAWN.** A protection is not *checked* on a date and
 * stored; it is COMPUTED, now, from the rows in force — which is the module's
 * own design (*"a RUN cached on a row outlives the debt"*). Four identical
 * dates down a column read as four separate attestations and are one read, so
 * the date is stated once for the section. Inventing a per-row checked-at
 * would be this screen recording an attestation nobody made.
 *
 * ⚠ **THE FOUR QUESTIONS ARE THE DRAWING'S OWN WORDS AND THEY RUN TO FOUR
 * WORDS, ONE OVER B14 RULE 33's LABEL CAP.** That divergence is deliberate and
 * is filed rather than silently taken either way: *"Medical certificate?"*
 * asks whether one is required and *"Medical certificate on file?"* asks
 * whether one is HELD, and those are different questions on the screen that
 * authorises a cut. Rule 33's own text refuses to cut below clarity.
 */
import { useTranslation } from "react-i18next";

import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Panel } from "@/components/Panel";

import type { DisconnectProtectionRow, DisconnectRecordDetail } from "./disconnectRecordEndpoints";

/** The answer a clerk reads, per outcome. Never a colour alone (B14). */
export function protectionAnswerKey(row: DisconnectProtectionRow): string {
  if (row.outcome === "unavailable") return "customers.disconnectRecord.outcome.unavailable";
  // ⚠ **`pass` READS `No` AND `fail` READS `Yes`, WHICH LOOKS BACKWARDS AND IS
  // NOT.** The column's header is the QUESTION — *is a medical certificate on
  // file?* — so `pass` (no protection is in force) is answered *No*. The
  // server's vocabulary is about the CUT passing; the screen's is about the
  // question. Naming them apart here is what stops a later lane "fixing" one
  // into the other.
  return row.outcome === "fail" ? "customers.account.yes" : "customers.account.no";
}

export function ProtectionsPanel(props: {
  record: DisconnectRecordDetail;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const protections = props.record.protections;
  const rows = protections?.checks ?? [];

  return (
    <Panel title={t("customers.disconnectRecord.section.protections")}>
      <table className="mt-2 w-full text-sm" data-testid="disconnect-record-protections">
        <thead>
          <tr className="border-b border-neutral-300 text-left text-xs uppercase tracking-wide text-neutral-600">
            <th scope="col" className="py-2 font-medium">
              {t("customers.disconnectRecord.check.col.question")}
            </th>
            <th scope="col" className="py-2 font-medium">
              {t("customers.disconnectRecord.check.col.answer")}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.check} className="border-b border-neutral-200">
              <td className="py-3 text-neutral-900">
                {t(`customers.disconnectRecord.check.${row.check}`, { defaultValue: row.check })}
              </td>
              <td
                className="py-3 text-neutral-900"
                data-outcome={row.outcome}
                /* The server's `reason` is RATIONALE — zero words on screen
                   (B14 rule 33) — and rides on the attribute for anybody
                   debugging, exactly as an absence's `detail` does. */
                title={row.reason}
              >
                {t(protectionAnswerKey(row))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {protections?.as_of ? (
        <p className="mt-3 text-sm text-neutral-600" data-testid="disconnect-record-checked-on">
          {t("customers.disconnectRecord.check.asOf")}{" "}
          <DateCell
            value={protections.as_of}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        </p>
      ) : null}
    </Panel>
  );
}
