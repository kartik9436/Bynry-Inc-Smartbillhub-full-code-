// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane CREWS — ruling 27 (*"user should be able
//           to view the crew performance"*): a technician's Performance tab and
//           the *This month* line on the Overview. Built from the IMAGES
//           `…/images/34-crews-one-technician-performance.png` and
//           `…/images/31-crews-one-technician-overview.png`.
// Server:   `GET /work/technicians/{slug}/performance?period=&page=&per=` and
//           the detail's `this_month` (P3.46, lane SRV-3 `2.502.0`) — the SAME
//           `tally` the Performance screen uses, so the tiles and the rows
//           cannot disagree. Nothing here does arithmetic beyond formatting.
// Rules:    B14 rule 2 · 12/16 (the shared pager) · 20 (`PlainTable`) · 33 ·
//           37 (the drawn *Sep 2026* is an illustration; the period list is
//           built from the server's own month) · 43 · 44 (`KPIStrip`)
// Tests:    src/features/work/crewsLane.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { KPIStrip } from "@/components/KPIStrip";
import { ListPager } from "@/components/ListPager";
import { Panel } from "@/components/Panel";
import { SelectField } from "@/components/FormModal";
import { PlainTable } from "@/components/Surfaces";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";
import { Note } from "@/components/TextBits";
import { Dash } from "@/features/customers/customersShared";

import { getTechnicianPerformance } from "./crewsEndpoints";
import type { PerformanceFigures } from "./crewsEndpoints";
import type { TechnicianDetail } from "./workEndpoints";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** `"100.0"` → `100%`; null → null (nothing was measured). */
export function pctText(value: string | null): string | null {
  if (value === null) return null;
  const n = Number(value);
  return Number.isFinite(n) ? `${Math.round(n)}%` : null;
}

/** Minutes against the estimate: *−4 min* early, *+3 min* late. */
export function minutesText(minutes: number | null, t: Translate): string | null {
  if (minutes === null) return null;
  const sign = minutes > 0 ? "+" : minutes < 0 ? "−" : "";
  return t("work.technician.performance.minutes", { value: `${sign}${Math.abs(minutes)}` });
}

function onTimePct(figures: PerformanceFigures): string | null {
  if (figures.on_time_of === 0) return null;
  return `${Math.round((figures.on_time / figures.on_time_of) * 100)}%`;
}

/** `2026-10` → *Oct 2026*, in the reader's language. */
function monthName(month: string, language: string): string {
  const [year, number] = month.split("-").map(Number);
  if (!year || !number) return month;
  return new Intl.DateTimeFormat(language, { month: "short", year: "numeric", timeZone: "UTC" }).format(
    new Date(Date.UTC(year, number - 1, 1)),
  );
}

function previousMonth(month: string): string {
  const [year, number] = month.split("-").map(Number);
  const prev = new Date(Date.UTC(year, number - 2, 1));
  return `${prev.getUTCFullYear()}-${String(prev.getUTCMonth() + 1).padStart(2, "0")}`;
}

/** Image 31's *This month* panel. */
export function ThisMonthPanel(props: { detail: TechnicianDetail }) {
  const { t } = useTranslation();
  const month = props.detail.this_month;
  if (month === undefined) return null;
  const parts = [
    { label: t("work.technician.month.closed"), value: String(month.closed) },
    { label: t("work.technician.month.firstVisit"), value: pctText(month.first_visit_pct) },
    { label: t("work.technician.month.onTime"), value: t("work.technician.month.ofCount", { on: month.on_time, of: month.on_time_of }) },
    { label: t("work.technician.month.vsEstimate"), value: minutesText(month.vs_estimate_minutes, t) },
  ];
  return (
    <Panel as="section" title={t("work.technician.month.title")} data-this-month="">
      <p className="m-0">
        {parts.map((part, index) => (
          <span key={part.label}>
            {index > 0 && " · "}
            {part.label} {part.value === null ? <Dash /> : <strong>{part.value}</strong>}
          </span>
        ))}
      </p>
    </Panel>
  );
}

/** Image 34. */
export function TechnicianPerformanceTab(props: { client: ApiClient; detail: TechnicianDetail }) {
  const { t, i18n } = useTranslation();
  const { detail } = props;
  const thisMonth = detail.this_month?.month ?? new Date().toISOString().slice(0, 7);
  const [period, setPeriod] = useState(thisMonth);
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(DEFAULT_PAGE_SIZE);

  const query = useQuery({
    queryKey: ["work", "technician", detail.slug, "performance", period, page, per],
    queryFn: () => getTechnicianPerformance(detail.slug, { period, page, per }, props.client),
  });
  const data = query.data;
  const lastMonth = previousMonth(thisMonth);
  const year = thisMonth.slice(0, 4);
  const options = [
    { value: thisMonth, label: t("work.technician.performance.thisMonth", { month: monthName(thisMonth, i18n.language) }) },
    { value: lastMonth, label: t("work.technician.performance.lastMonth", { month: monthName(lastMonth, i18n.language) }) },
    { value: year, label: t("work.technician.performance.thisYear", { year }) },
    { value: "", label: t("work.technician.performance.allTime") },
  ];
  const tiles = data?.tiles;
  const periodWords =
    period.length === 4 ? year : monthName(period, i18n.language);

  return (
    <div data-technician-performance="">
      <div className="mb-4 max-w-xs">
        <SelectField
          id="period"
          label={t("work.technician.performance.period")}
          value={period}
          onChange={(next) => {
            setPeriod(next);
            setPage(1);
          }}
          options={options}
        />
      </div>
      {query.isError ? (
        <Note>{t("work.technician.performance.failed")}</Note>
      ) : (
        <div data-technician-tiles="">
          <KPIStrip
            loading={tiles === undefined}
            kpis={
              tiles === undefined
                ? []
                : [
                    {
                      id: "closed",
                      label: t("work.technician.month.closed"),
                      value: tiles.closed,
                      // DEF-WRK-9640: All time has its own caption. The
                      // month/year one puts a preposition before the period
                      // word, and *In All time* (fr *En Depuis le début*)
                      // read wrong in ten of eleven languages.
                      detail:
                        period === ""
                          ? t("work.technician.performance.closedAllTime")
                          : t("work.technician.performance.closedIn", { period: periodWords }),
                    },
                    {
                      id: "on_time",
                      label: t("work.technician.performance.onTime"),
                      value: onTimePct(tiles) ?? "—",
                      detail: t("work.technician.performance.onTimeOf", { on: tiles.on_time, of: tiles.on_time_of }),
                    },
                    {
                      id: "first_visit",
                      label: t("work.technician.month.firstVisit"),
                      value: pctText(tiles.first_visit_pct) ?? "—",
                      detail: t("work.technician.performance.noFollowUp"),
                    },
                    {
                      id: "vs_estimate",
                      label: t("work.technician.month.vsEstimate"),
                      value: minutesText(tiles.vs_estimate_minutes, t) ?? "—",
                      detail:
                        tiles.vs_estimate_minutes === null
                          ? t("work.technician.performance.noEstimate")
                          : t("work.technician.performance.vsEstimatePct", { pct: pctText(tiles.vs_estimate_pct) ?? "—" }),
                    },
                  ]
            }
          />
        </div>
      )}
      <Panel as="section" title={t("work.technician.performance.byType")} data-by-job-type="">
        {data !== undefined && data.results.length === 0 ? (
          <Note>{t("work.technician.performance.none")}</Note>
        ) : (
          <PlainTable>
            <thead>
              <tr>
                <th>{t("work.technician.performance.col.type")}</th>
                <th className="text-right">{t("work.technician.performance.col.jobs")}</th>
                <th className="text-right">{t("work.technician.performance.col.onTime")}</th>
                <th className="text-right">{t("work.technician.performance.col.firstVisit")}</th>
                <th className="text-right">{t("work.technician.performance.col.vsEstimate")}</th>
              </tr>
            </thead>
            <tbody>
              {(data?.results ?? []).map((row) => (
                <tr key={row.job_type ?? "none"}>
                  <td>{row.job_type ?? <Dash />}</td>
                  <td className="text-right tabular-nums">{row.volume}</td>
                  <td className="text-right tabular-nums">{onTimePct(row) ?? <Dash />}</td>
                  <td className="text-right tabular-nums">{pctText(row.first_visit_pct) ?? <Dash />}</td>
                  <td className="text-right tabular-nums">{minutesText(row.vs_estimate_minutes, t) ?? <Dash />}</td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        )}
        {data !== undefined && data.count > 0 && (
          <ListPager
            total={data.count}
            page={page}
            per={per}
            onPage={setPage}
            onPer={(next) => {
              setPer(next);
              setPage(1);
            }}
          />
        )}
      </Panel>
    </div>
  );
}

export default TechnicianPerformanceTab;
