// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 5, lane PERFORMANCE — P5.4, the schedule board:
//           *"Drag a job to a technician; see a day's load. Over-assignment is
//           visible."* (blueprint §02, capabilities C17, C18). NAMED, NOT DRAWN
//           — built from the component kit under B14 rule 44 in image 65's
//           style, and put to the PO as a photograph.
// Reads:    P5.11 — *"The three new screens read existing endpoints"*:
//           `GET /work-orders?technician=none&page=&per=` (the jobs nobody
//           holds) and `GET /work/candidates?on=&page=&per=` (everybody a job
//           may be given, with `jobs_that_day` and `off_that_day` for the day
//           asked about, in the utility's calendar).
// Writes:   `POST /work-orders/bulk {act: "assign"}` — ONE row per order,
//           one savepoint per order on the server (`BR-WRK-027`, law 14).
// Rules:    NFR-3 (both lists page on the server) · NFR-5 · B14 rules 15, 20
//           (every selection table is the kit `TableArray`), 21, 31, 33, 44 ·
//           ruling 2 (advice never blocks — an over-assigned name is still a
//           name you may choose).
// Tests:    src/features/work/performance/cr168Performance.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **OVER-ASSIGNED MEANS TWO THINGS HERE, BOTH STORED FACTS** — amended
// 2026-10-05 (`CR-168-BRC10` §30, lane BOARDS). Until then it meant one: a
// holder OFF that day who still holds jobs on it, because no jobs-per-day
// capacity was stored and *more than six* would have been a number this screen
// invented. The PO then answered (2), verbatim: *"(b) Add a daily limit per
// technician (default 6), editable on the technician's page."* So a technician
// carries `daily_job_limit` and the server says `over_daily_limit` when the
// day's jobs exceed it — limit 6, D. Ortiz holding 7, red, beside the existing
// *Off, has jobs*. The figure is the SERVER's and the technician's page's; this
// screen still types no number. A crew carries no limit.
//
// ⚠ **DRAG IS THE QUICK WAY, NEVER THE ONLY WAY.** A dragged job lands on a
// holder; the same act is a tick in the jobs table and *Give ✓* on the holder's
// row, so a keyboard and a screen reader reach every assignment a mouse can.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { formatDate, todayInZone } from "@/components/DateCell";
import { ListPager } from "@/components/ListPager";
import { StatusPill } from "@/components/StatusPill";
import { TableArray } from "@/components/TableArray";
import type { PageSize } from "@/components/tableTypes";
import { useRegional } from "@/features/metering/meteringShared";
import i18n from "@/i18n";

import { listRaiseCandidates } from "../raise/raiseEndpoints";
import { windowMoments } from "../visitWindow";
import type { WindowChoice } from "../visitWindow";
import { bulkWorkOrders, listWorkOrders } from "../workEndpoints";
import type { BulkOutcome, Candidate, WorkOrderDispatchRow } from "../workEndpoints";

type Translate = (key: string, params?: Record<string, unknown>) => string;
type BoardWindow = Exclude<WindowChoice, "exact">;
const BOARD_WINDOWS: readonly BoardWindow[] = ["morning", "afternoon", "any"];
const DRAG_TYPE = "text/plain";

/** What a holder's day looks like, from the server's facts. */
export type HolderLoad = "offDutyHolding" | "over" | "off" | "limit" | "busy" | "free";

/** `over` — off that day and still holding jobs on it; `limit` — on that day
 *  and holding MORE jobs than their daily limit (§30). Both are the data's own
 *  facts (see the header). `jobs_that_day` null = not said.
 *
 *  `offDutyHolding` — FB-033 D3 (PO 2026-10-31, *"jobs already assigned stay
 *  with the technician … the office board marks them 'assignee off duty'"*):
 *  the technician said *Off duty* on the phone and still holds jobs that day.
 *  Nothing moves; the dispatcher decides. */
export function holderLoad(candidate: Candidate): HolderLoad {
  const jobs = candidate.advice.jobs_that_day ?? 0;
  if (candidate.advice.availability?.status === "off_duty" && jobs > 0) return "offDutyHolding";
  if (candidate.advice.off_that_day) return jobs > 0 ? "over" : "off";
  if (candidate.advice.over_daily_limit === true) return "limit";
  return jobs > 0 ? "busy" : "free";
}

/** The two moments a drop writes — the raise's own rule for *Any time*: the
 *  whole day, never nothing, so the job is counted on the day it was dropped
 *  on (decision log, CR-168 round 3 RAISE (6)). */
export function dropMoments(day: string, slot: BoardWindow): { window_start: string; window_end: string } {
  if (slot === "any") return { window_start: `${day}T00:00:00`, window_end: `${day}T23:59:00` };
  const moments = windowMoments(day, slot);
  return { window_start: moments.window_start ?? `${day}T00:00:00`, window_end: moments.window_end ?? `${day}T23:59:00` };
}

/** The one write — `assign` on the bulk route, a technician or a crew. */
export function giveBody(ids: readonly string[], holder: Candidate, day: string, slot: BoardWindow) {
  return {
    act: "assign" as const,
    ids: [...ids],
    ...(holder.kind === "person" ? { technician_id: holder.id } : { crew_id: holder.id }),
    ...dropMoments(day, slot),
  };
}

function LoadPill(props: { candidate: Candidate; t: Translate }) {
  const load = holderLoad(props.candidate);
  if (load === "offDutyHolding") {
    return <StatusPill tone="danger">{props.t("work.schedule.load.assigneeOffDuty")}</StatusPill>;
  }
  if (load === "over") return <StatusPill tone="danger">{props.t("work.schedule.load.over")}</StatusPill>;
  if (load === "off") return <StatusPill tone="neutral">{props.t("work.schedule.load.off")}</StatusPill>;
  if (load === "limit") {
    return (
      <StatusPill tone="danger">
        {props.t("work.schedule.load.overLimit", { limit: props.candidate.advice.daily_job_limit ?? "" })}
      </StatusPill>
    );
  }
  if (load === "busy") return <StatusPill tone="info">{props.t("work.schedule.load.busy")}</StatusPill>;
  return <StatusPill tone="success">{props.t("work.schedule.load.free")}</StatusPill>;
}

/** P5.4 — the day, the jobs nobody holds, and everybody's load that day. */
export function ScheduleBoard(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const { timeZone, dateFormat } = useRegional({});
  const translate: Translate = (key, params) => t(key, params);

  const [day, setDay] = useState(() => todayInZone(timeZone));
  const [slot, setSlot] = useState<BoardWindow>("morning");
  const [jobsPage, setJobsPage] = useState(1);
  const [jobsPer, setJobsPer] = useState<PageSize>(50);
  const [holdersPage, setHoldersPage] = useState(1);
  const [holdersPer, setHoldersPer] = useState<PageSize>(50);
  const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [answer, setAnswer] = useState<{ outcome: BulkOutcome; name: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const jobs = useQuery({
    queryKey: ["work", "schedule", "queue", jobsPage, jobsPer],
    queryFn: () => listWorkOrders({ technician: "none", page: jobsPage, per: jobsPer }, client),
  });
  const holders = useQuery({
    queryKey: ["work", "schedule", "holders", day, holdersPage, holdersPer],
    queryFn: () => listRaiseCandidates({ on: day, page: holdersPage, per: holdersPer }, client),
    enabled: day !== "",
  });

  const jobRows = jobs.data?.results ?? [];
  const holderRows = holders.data?.results ?? [];
  const orderNoOf = new Map(jobRows.map((row) => [row.id, row.order_no ?? ""]));

  async function give(ids: readonly string[], holder: Candidate) {
    if (ids.length === 0 || busy) return;
    setBusy(true);
    try {
      const outcome = await bulkWorkOrders(giveBody(ids, holder, day, slot), client);
      setAnswer({ outcome, name: holder.name });
      setChosen(new Set());
      await queryClient.invalidateQueries({ queryKey: ["work", "schedule"] });
    } catch {
      setAnswer({
        outcome: { act: "assign", results: ids.map((id) => ({ id, ok: false })), done: 0, failed: ids.length },
        name: holder.name,
      });
    } finally {
      setBusy(false);
    }
  }

  function toggle(id: string, ticked: boolean) {
    setChosen((current) => {
      const next = new Set(current);
      if (ticked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  const dropZone = (holder: Candidate) => ({
    onDragOver: (event: React.DragEvent) => {
      event.preventDefault();
      setDropTarget(holder.id);
    },
    onDragLeave: () => setDropTarget((current) => (current === holder.id ? null : current)),
    onDrop: (event: React.DragEvent) => {
      event.preventDefault();
      setDropTarget(null);
      const id = event.dataTransfer.getData(DRAG_TYPE);
      if (id !== "") void give([id], holder);
    },
  });

  return (
    <div className="flex flex-col gap-4" data-schedule-board="">
      <div className="flex flex-wrap items-end gap-4" data-schedule-day="">
        <label className="flex flex-col gap-1 text-base">
          <span className="font-semibold">{t("work.schedule.day")}</span>
          <input
            type="date"
            className="input w-48"
            value={day}
            onChange={(event) => {
              setDay(event.target.value);
              setHoldersPage(1);
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-base">
          <span className="font-semibold">{t("work.schedule.window")}</span>
          <select
            className="input w-48"
            value={slot}
            onChange={(event) => setSlot(event.target.value as BoardWindow)}
          >
            {BOARD_WINDOWS.map((choice) => (
              <option key={choice} value={choice}>
                {t(`work.edit.window.${choice}`)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {answer !== null && (
        <p
          className={`m-0 text-base ${answer.outcome.failed > 0 ? "text-danger-700" : "text-neutral-800"}`}
          role="status"
          data-schedule-answer=""
        >
          {answer.outcome.done > 0 && t("work.schedule.given", { count: answer.outcome.done, name: answer.name })}{" "}
          {answer.outcome.failed > 0 &&
            t("work.schedule.notGiven", {
              count: answer.outcome.failed,
              reason: (() => {
                const key = answer.outcome.results.find((row) => !row.ok)?.reason;
                return key !== undefined && i18n.exists(key) ? t(key) : t("work.schedule.refusedGeneric");
              })(),
            })}
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div data-testid="schedule-queue">
          <TableArray<WorkOrderDispatchRow>
            readOnly
            title={t("work.schedule.queue")}
            collection="schedule-queue"
            fact={t("work.schedule.queueFact", { count: jobs.data?.count ?? 0, chosen: chosen.size })}
            columns={[
              {
                key: "tick",
                label: t("work.schedule.tick"),
                cell: (row) => (
                  <input
                    type="checkbox"
                    aria-label={t("work.schedule.tickJob", { order: row.order_no ?? "" })}
                    checked={chosen.has(row.id)}
                    onChange={(event) => toggle(row.id, event.target.checked)}
                  />
                ),
              },
              {
                key: "order",
                label: t("work.schedule.col.order"),
                cell: (row) => (
                  <span
                    draggable
                    className="inline-flex cursor-grab items-center gap-1 whitespace-nowrap font-semibold"
                    data-drag-order={row.order_no ?? ""}
                    onDragStart={(event) => {
                      event.dataTransfer.setData(DRAG_TYPE, row.id);
                      event.dataTransfer.effectAllowed = "move";
                    }}
                  >
                    <span aria-hidden="true">⠿</span>
                    {row.order_no ?? "—"}
                  </span>
                ),
              },
              { key: "type", label: t("work.schedule.col.type"), cell: (row) => row.type },
              { key: "where", label: t("work.schedule.col.where"), cell: (row) => row.premise?.address ?? "—" },
              {
                key: "due",
                label: t("work.schedule.col.due"),
                cell: (row) =>
                  row.due_at === null ? "—" : (
                    <span className="tabular-nums">{formatDate(row.due_at, timeZone, dateFormat)}</span>
                  ),
              },
            ]}
            rows={jobRows}
            rowKey={(row) => row.id}
            emptyText={jobs.isPending ? t("work.schedule.loading") : t("work.schedule.queueEmpty")}
            note={t("work.schedule.queueNote")}
          >
            {(jobs.data?.count ?? 0) > jobRows.length || jobsPage > 1 ? (
              <ListPager
                total={jobs.data?.count ?? 0}
                page={jobsPage}
                per={jobsPer}
                onPage={setJobsPage}
                onPer={(per) => {
                  setJobsPer(per);
                  setJobsPage(1);
                }}
              />
            ) : null}
          </TableArray>
        </div>

        <div data-testid="schedule-holders">
          <TableArray<Candidate>
            readOnly
            title={t("work.schedule.holders")}
            collection="schedule-holders"
            fact={formatDate(day, timeZone, dateFormat)}
            columns={[
              {
                key: "name",
                label: t("work.schedule.col.name"),
                cell: (row) => (
                  <div
                    className={`-m-2 p-2 ${dropTarget === row.id ? "outline-2 outline-dashed outline-accent" : ""}`}
                    data-drop-holder={row.name}
                    {...dropZone(row)}
                  >
                    <span className="font-semibold">{row.name}</span>
                    <span className="block text-sm text-neutral-700">{t(`work.schedule.kind.${row.kind}`)}</span>
                  </div>
                ),
              },
              {
                key: "jobs",
                label: t("work.schedule.col.jobs"),
                numeric: true,
                cell: (row) => (
                  <span className="tabular-nums" data-holder-jobs={row.name}>
                    {row.advice.jobs_that_day ?? "—"}
                  </span>
                ),
              },
              {
                key: "load",
                label: t("work.schedule.col.load"),
                cell: (row) => (
                  <span data-holder-load={holderLoad(row)}>
                    <LoadPill candidate={row} t={translate} />
                  </span>
                ),
              },
              {
                key: "give",
                label: t("work.schedule.col.give"),
                cell: (row) => (
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={chosen.size === 0 || busy}
                    title={chosen.size === 0 ? t("work.schedule.tickFirst") : undefined}
                    data-give-to={row.name}
                    aria-label={t("work.schedule.giveTo", {
                      count: chosen.size,
                      name: row.name,
                      orders: [...chosen].map((id) => orderNoOf.get(id) ?? "").join(", "),
                    })}
                    onClick={() => void give([...chosen], row)}
                  >
                    {t("work.schedule.give")}
                  </Button>
                ),
              },
            ]}
            rows={holderRows}
            rowKey={(row) => `${row.kind}:${row.id}`}
            emptyText={holders.isPending ? t("work.schedule.loading") : t("work.schedule.holdersEmpty")}
          >
            {(holders.data?.count ?? 0) > holderRows.length || holdersPage > 1 ? (
              <ListPager
                total={holders.data?.count ?? 0}
                page={holdersPage}
                per={holdersPer}
                onPage={setHoldersPage}
                onPer={(per) => {
                  setHoldersPer(per);
                  setHoldersPage(1);
                }}
              />
            ) : null}
          </TableArray>
        </div>
      </div>
    </div>
  );
}
