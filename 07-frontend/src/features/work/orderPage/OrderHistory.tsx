// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 2, lane ORDER-PAGE — the Audit tab, image 08.
// Tasks:    P1.16 (dates read as dates, in the utility's own zone) · P1.17 (the
//           history says who acted, and on whom: To · By · When · Window) ·
//           P4.2 (the whole story of a job reads in order — every act the
//           server serves, P4.11, lane SRV-1)
// Fixes:    DEF-WRK-9584 — raw ISO timestamps, and *Who* naming the technician
//           for an act the dispatcher did.
// ───────────────────────────────────────────────────────
//
// ⚠ **`who` IS THE PERSON THE JOB WENT TO, `by` IS THE PERSON WHO DID IT.**
// The server has served both since wave G (`dispatch.order_audit`); the tab
// drew one column headed *Who* from `who`, so *Assigned · Who: D. Ortiz* read
// as D. Ortiz assigning the job. Two columns, named for what each one is.
//
// ⚠ **AN ACT THE CATALOGUE DOES NOT KNOW SHOWS AS A GENERIC WORD, NEVER AS ITS
// TOKEN** (B14 rule 31's spirit — an enum code is internal). SRV-1's union adds
// acts; each has a word in all eleven catalogues, and a sixteenth that arrives
// before its word reads *Changed* rather than `sent_back`.
import { useTranslation } from "react-i18next";

import { Panel } from "@/components/Panel";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { Dash } from "@/features/metering/meteringShared";

import type { OrderHistoryRow } from "./orderPageEndpoints";
import { historyBy } from "./orderPageEndpoints";
import { whenText, windowText } from "./orderFormat";
import type { Regional } from "./orderFormat";

/** Every act §7.3 serves, plus `raised` — each has a catalogue word. */
export const ORDER_HISTORY_ACTS = [
  "raised",
  "assign",
  "unassign",
  "reassign",
  "schedule",
  "depart",
  "arrive",
  "hold",
  "resume",
  "cancel",
  "priority",
  "completed",
  "accepted",
  "sent_back",
  "accepted_by_technician",
  "declined_by_technician",
] as const;

const KNOWN = new Set<string>(ORDER_HISTORY_ACTS);

export function OrderHistoryTab(props: { rows: OrderHistoryRow[]; regional: Regional }) {
  const { t } = useTranslation();
  if (props.rows.length === 0) {
    return (
      <Panel title={t("work.order.audit.title")}>
        <Note>{t("work.order.audit.empty")}</Note>
      </Panel>
    );
  }
  return (
    <Panel title={t("work.order.audit.title")}>
      <PlainTable>
        <thead>
          <tr>
            <th>{t("work.order.audit.act")}</th>
            <th>{t("work.order.audit.to")}</th>
            <th>{t("work.order.audit.by")}</th>
            <th>{t("work.order.audit.when")}</th>
            <th>{t("work.order.audit.window")}</th>
          </tr>
        </thead>
        <tbody>
          {props.rows.map((entry, index) => {
            const window =
              windowText(entry.window_start, entry.window_end, props.regional) ??
              whenText(entry.scheduled_for, props.regional);
            return (
              <tr key={index} data-audit-row={index} data-audit-act={entry.act}>
                <td>
                  {KNOWN.has(entry.act) ? t(`work.order.audit.acts.${entry.act}`) : t("work.order.audit.acts.other")}
                  {entry.reason ? (
                    <span className="mt-1 block text-sm text-neutral-600" data-audit-reason="">
                      {entry.reason}
                    </span>
                  ) : null}
                </td>
                <td>{entry.who?.name ?? <Dash />}</td>
                <td data-audit-by="">{historyBy(entry) ?? <Dash />}</td>
                <td data-audit-when="">{whenText(entry.at, props.regional) ?? <Dash />}</td>
                <td>{window ?? <Dash />}</td>
              </tr>
            );
          })}
        </tbody>
      </PlainTable>
    </Panel>
  );
}
