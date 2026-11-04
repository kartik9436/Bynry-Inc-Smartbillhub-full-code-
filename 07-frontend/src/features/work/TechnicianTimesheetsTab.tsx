// ── Trace ──────────────────────────────────────────────
// Change:   CR-193-BRC10 — MQ-040 STEP 1 (decision log 2026-10-26, *"Timesheet
//           Submit the day to the office, office sees submitted days"*): the
//           technician page's *Timesheets* tab.
// Server:   GET /work/technicians/{slug}/timesheets?page=&per= (newest first)
// Rules:    NFR-3 (paged by the server) · B14 rule 20 (the one table type) ·
//           rule 21 (Tailwind; on route-b-migrated.txt) · rule 31 (no job or
//           row id on screen) · rule 33 (labels ≤ 3 words) · rule 43
// Tests:    src/features/work/TechnicianShifts.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// A submitted day is a SNAPSHOT the phone handed in (`shifts.submit_day`): what
// the clocks said at that moment. It is read here and corrected nowhere here —
// a correction is the office's act on the job's labour, and the snapshot keeps
// what the technician actually submitted.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { DateCell } from "@/components/DateCell";
import { ListPager } from "@/components/ListPager";
import { Panel } from "@/components/Panel";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { PAGE_SIZES } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";

import { listTimesheets } from "./shiftsEndpoints";

/** `99` → `1h 39m`, `14` → `14m` — the field app's own form (`me/format.ts`). */
export function minutesText(minutes: number): string {
  const whole = Math.max(0, Math.round(minutes));
  const h = Math.floor(whole / 60);
  const m = whole % 60;
  return h > 0 ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

export function TechnicianTimesheetsTab(props: {
  slug: string;
  client: ApiClient;
  timeZone: string;
  dateFormat: Parameters<typeof DateCell>[0]["dateFormat"];
}) {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(PAGE_SIZES[0]);
  const list = useQuery({
    queryKey: ["work", "technician", props.slug, "timesheets", page, per],
    queryFn: () => listTimesheets(props.slug, { page, per }, props.client),
  });
  const rows = list.data?.rows ?? [];
  return (
    <Panel as="section" title={t("work.technician.timesheets.title")} data-technician-timesheets="">
      {list.isError ? (
        <Note>{t("work.technician.timesheets.failed")}</Note>
      ) : list.data !== undefined && rows.length === 0 ? (
        <Note data-timesheets-empty="">{t("work.technician.timesheets.empty")}</Note>
      ) : list.data === undefined ? null : (
        <>
          <PlainTable data-timesheets-table="">
            <thead>
              <tr>
                <th>{t("work.technician.timesheets.col.date")}</th>
                <th className="text-right">{t("work.technician.timesheets.col.jobs")}</th>
                <th className="text-right">{t("work.technician.timesheets.col.onSite")}</th>
                <th className="text-right">{t("work.technician.timesheets.col.travel")}</th>
                <th>{t("work.technician.timesheets.col.submitted")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.date} data-timesheet-day={row.date}>
                  <td>
                    <DateCell value={row.date} timeZone={props.timeZone} dateFormat={props.dateFormat} />
                  </td>
                  <td className="text-right tabular-nums">{row.jobs}</td>
                  <td className="text-right tabular-nums">{minutesText(row.labour_minutes)}</td>
                  <td className="text-right tabular-nums">{minutesText(row.travel_minutes)}</td>
                  <td>
                    <DateCell value={row.submitted_at} timeZone={props.timeZone} dateFormat={props.dateFormat} withTime />
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
          <ListPager
            total={list.data.total}
            page={page}
            per={per}
            onPage={setPage}
            onPer={(next) => {
              setPer(next);
              setPage(1);
            }}
          />
        </>
      )}
    </Panel>
  );
}

export default TechnicianTimesheetsTab;
