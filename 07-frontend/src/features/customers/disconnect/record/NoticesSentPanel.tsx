// ── Trace ──────────────────────────────────────────────
// Change:   CR-125-BRC07 — p143's `NOTICES SENT`. The drawing gives FOUR
//           columns and the honest table is TWO.
// Rules:    BR-NOT-005 (a notice is WRITTEN; only a dispatcher sends) ·
//           BR-CUS-100 (proof of service is a person's attestation) · B14
//           rule 43 · rule 33
// ───────────────────────────────────────────────────────
/**
 * `NOTICES SENT` — and **it cannot be built as drawn, which is CORRECT
 * BEHAVIOUR rather than a gap.**
 *
 * p143 draws `NOTICE · SENT · CHANNEL · STATE`. Two of those four cannot be
 * filled by this product:
 *
 *   * **`STATE`** reads `disconnect_notices.delivery_state`, which is written
 *     NULL on every row **by a deliberate rule**: there is no email, SMS or
 *     print adapter in this release, so a `Sent` here would be this product
 *     telling a regulator it delivered a letter it cannot deliver. That is
 *     `DEF-692`'s shape and it is the one thing on this table whose absence is
 *     not merely untidy.
 *   * **`CHANNEL`** reads `service_channel`, which is the **proof-of-service**
 *     channel and not a send channel — null until a clerk attests to how a
 *     posted item went out. It IS drawn on a row that has been attested to,
 *     because there the fact is real.
 *
 * ⚠ **THE DRAWING'S OWN RED NOTE SAYS THE SAME** — *"Queued is not sent"* —
 * and the product already carries that sentence as
 * `disconnects.DELIVERY_UNAVAILABLE`. It is rendered as the panel's one note
 * rather than as a `Queued` chip on every row, because a chip is a claim about
 * a letter and this is a fact about the product.
 */
import { useTranslation } from "react-i18next";

import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Panel } from "@/components/Panel";

import type { DisconnectRecordDetail } from "./disconnectRecordEndpoints";

export function NoticesSentPanel(props: {
  record: DisconnectRecordDetail;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const notices = props.record.notices;
  const rows = notices?.rows ?? [];

  return (
    <Panel title={t("customers.disconnectRecord.section.notices")}>
      {rows.length === 0 ? (
        <p className="mt-2 text-sm text-neutral-600" data-testid="disconnect-record-no-notices">
          {t("customers.disconnectRecord.notices.empty")}
        </p>
      ) : (
        <table className="mt-2 w-full text-sm" data-testid="disconnect-record-notices">
          <thead>
            <tr className="border-b border-neutral-300 text-left text-xs uppercase tracking-wide text-neutral-600">
              <th scope="col" className="py-2 font-medium">
                {t("customers.disconnectRecord.notices.col.notice")}
              </th>
              <th scope="col" className="py-2 font-medium">
                {t("customers.disconnectRecord.notices.col.sent")}
              </th>
              {/* ⚠ **THE THIRD COLUMN APPEARS ONLY WHERE THE FACT DOES.** The
                  server answers `channel_column_empty` when no notice on this
                  case has been attested to, and a header over a column of
                  dashes tells a clerk to go looking for something nobody
                  recorded. */}
              {notices?.channel_column_empty === null ? (
                <th scope="col" className="py-2 font-medium">
                  {t("customers.disconnectRecord.notices.col.channel")}
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.tier}-${row.issued_on}`} className="border-b border-neutral-200">
                <td className="py-3 text-neutral-900">
                  {/* A stored tier CODE, translated (B14 rule 31). */}
                  {t(`customers.disconnect.notice.${row.tier}`, { defaultValue: row.tier })}
                </td>
                <td className="py-3 text-neutral-900">
                  <DateCell
                    value={row.issued_on}
                    timeZone={props.timeZone}
                    dateFormat={props.dateFormat}
                  />
                </td>
                {notices?.channel_column_empty === null ? (
                  <td className="py-3 text-neutral-900">
                    {row.channel
                      ? t(`customers.disconnect.channel.${row.channel}`, {
                          defaultValue: "",
                        })
                      : null}
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* The drawing's own red note. `role="note"` because it is a standing
          fact about this product, not an alert that has just fired.

          ⚠ **EVERY COLOUR NAME HERE IS A DECLARED TOKEN.** This theme declares
          `--color-danger-100/500/700` and NO `-50`, `-300`, `-800` and no bare
          `--color-danger`; a utility naming one of those compiles to nothing,
          stays in the DOM and passes `toContain`, `tsc` and eslint while the
          box draws with no colour at all (`DEF-SHL-5088`, `DEF-INT-4236`,
          `DEF-SHL-4281` — three defects, one sentence). */}
      <p
        role="note"
        data-testid="disconnect-record-queued-note"
        className="mt-4 border border-danger-500 bg-danger-100 px-4 py-3 text-sm font-semibold text-danger-700"
      >
        {t("customers.disconnectRecord.notices.queuedNotSent")}
      </p>
    </Panel>
  );
}
