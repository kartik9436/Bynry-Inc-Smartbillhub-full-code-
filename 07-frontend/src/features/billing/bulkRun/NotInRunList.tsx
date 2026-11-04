// ── Trace ──────────────────────────────────────────────
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/25, 29 (Sign off), 35, 36
//           (Sent) · inventory.md §5.6, §6.3, §6.4
// Story:    US-BIL-041 (TC-1 … TC-5) · US-BIL-039 TC-3 (See filters)
// Plan:     15-bulk-bill-run-build-plan.md B20 · A9 · F14 · F15 · F19
// Rules:    changes rows 40, 42 · BR-BIL-1054 · NFR-3 · B14 rules 21, 31, 33, 43
// Defects:  DEF-BIL-8223 (Leave for next cycle — closed here)
// ───────────────────────────────────────────────────────
/**
 * NOT IN THIS RUN — ONE SERVED LIST, TWO ACTION SETS.
 *
 * It reads `GET …/not-in-run` — ONE PAGE, filtered by group on the server
 * (NFR-3): blocked accounts (with their first blocking tag), accounts held by
 * a decision or still waiting on one, accounts with nothing to bill, accounts
 * the clerk LEFT OUT, and — as UNIT rows with no checkbox — units with nobody
 * to bill. After Send each account row carries its Pending-billing state: the
 * days it has waited, *Next cycle* when the clerk left it for the next cycle,
 * or *Caught up* once a later run billed it.
 *
 * On Sign off a row's *Fix in Check* goes back to Check on its tag. After Send
 * a selection starts a catch-up run (`POST …/catch-up`) or is LEFT FOR THE
 * NEXT CYCLE (`POST …/not-in-run/leave-for-next-cycle`, DEF-BIL-8223).
 *
 * The filter is CONTROLLED, because Who is billed's *See* links press it
 * (changes row 42: every *See* filters this list; no side panel).
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import type { ApiClient } from "@/api/client";
import { DEFAULT_STALE_MS } from "@/api/queryClient";
import { getNotInRun, notInRunKey } from "@/api/bulkRunEndpoints";
import type { NotInRunGroup, ServedNotInRunRow } from "@/api/bulkRunEndpoints";
import { Button } from "@/components/Button";
import type { Translator } from "@/components/FormModal";
import { ListPager } from "@/components/ListPager";
import { SegmentedControl } from "@/components/SegmentedControl";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import type { PageSize } from "@/components/tableTypes";

import { CollapsiblePanel, PanelAside, RUN_TABLE, TableScroll, placeLine } from "./bulkRunShared";

export type NotInRunFilter = "all" | NotInRunGroup;

const GROUP_TONE: Record<NotInRunGroup, StatusTone> = {
  blocked: "danger",
  held: "warning",
  nothing: "neutral",
  left_out: "neutral",
  waived: "neutral",
  nobody: "info",
};

const GROUPS: readonly NotInRunGroup[] = ["blocked", "held", "nothing", "left_out", "waived", "nobody"];

/** Why a row is not billed — its first blocking tag, or why it is held. */
export function whyNot(row: ServedNotInRunRow, t: Translator): string | null {
  if (row.group === "blocked" && row.reason !== null) {
    const name = t(`billing.run.reason.${row.reason}`, { defaultValue: row.reason });
    return row.also > 0 ? t("billing.bulkRun.notInRun.andMore", { name, count: row.also }) : name;
  }
  if (row.group === "held") {
    return row.reason === "waiting_on_a_decision" ? t("billing.bulkRun.notInRun.reason.waiting") : t("billing.bulkRun.notInRun.reason.hold");
  }
  return null;
}

function QueueCell(props: { row: ServedNotInRunRow; t: Translator }) {
  const { row, t } = props;
  const queue = row.queue;
  if (queue === null) return <>—</>;
  if (queue.resolved_by_run_id !== null) return <StatusPill tone="success">{t("billing.bulkRun.notInRun.caughtUp")}</StatusPill>;
  if (queue.next_cycle) return <StatusPill tone="neutral">{t("billing.bulkRun.notInRun.nextCycleSet")}</StatusPill>;
  return <>{t("billing.bulkRun.notInRun.days", { count: queue.age_days ?? 0 })}</>;
}

/** DEF-BIL-8809 — the list's first page size, which the page also asks for
 *  beside the run read so the list finds its first page answered. */
export const NOT_IN_RUN_FIRST_PER: PageSize = 50;

/** One key and one request for both modes. `as_of` is always sent: it only
 *  adds each held row's age, which Sent draws and Sign off does not, so one
 *  answer serves both and the page can ask before it knows which it is. */
export const notInRunListKey = (runId: string, group: string, page: number, per: number, asOf: string) =>
  [...notInRunKey(runId, group, page, per), asOf] as const;

export function getNotInRunPage(
  runId: string,
  group: string,
  page: number,
  per: number,
  asOf: string,
  client: ApiClient,
) {
  return getNotInRun(runId, { group, page, per, as_of: asOf }, client);
}

export function NotInRunList(props: {
  mode: "signoff" | "sent";
  runId: string;
  client: ApiClient;
  /** The clerk's today (BR-TEN-043) — the days each queued row has waited. */
  asOf: string;
  filter: NotInRunFilter;
  onFilter: (filter: NotInRunFilter) => void;
  /** Sign off: go to Check on this row's tag (and its Fix-account panel). */
  onFixInCheck: (row: ServedNotInRunRow) => void;
  /** Sent: start a catch-up run for these accounts. */
  onCatchUp: (accountIds: readonly string[]) => void;
  /** Sent: leave these accounts for the next cycle (DEF-BIL-8223). */
  onLeaveForNextCycle: (accountIds: readonly string[]) => void;
  working: boolean;
  links: { addAccount: (unitId: string | null) => string; pending: string; unit: (unitId: string) => string };
  t: Translator;
}) {
  const { t } = props;
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(NOT_IN_RUN_FIRST_PER);
  const listQuery = useQuery({
    queryKey: notInRunListKey(props.runId, props.filter, page, per, props.asOf),
    queryFn: () => getNotInRunPage(props.runId, props.filter, page, per, props.asOf, props.client),
    // DEF-BIL-8809 — the page asked the first page beside the run read; the
    // list mounting a moment later takes that answer rather than asking again.
    staleTime: DEFAULT_STALE_MS,
    retry: false,
    placeholderData: (previous) => previous,
  });
  const data = listQuery.data ?? null;
  const rows = data?.results ?? [];
  const counts = data?.counts ?? null;
  // A waived account is not carried (PO 2026-09-30 case 2): never caught up.
  const selectable = (row: ServedNotInRunRow) =>
    row.kind === "account" &&
    row.account_id !== null &&
    row.group !== "waived" &&
    (props.mode === "signoff" || row.queue?.resolved_by_run_id == null);
  const chosen = [...selected];
  // DEF-BIL-9008 — each count takes its own plural ("1 unit", never "1 units").
  const aside =
    counts === null
      ? null
      : [
          t("billing.bulkRun.notInRun.headAccounts", { count: counts.accounts }),
          t("billing.bulkRun.notInRun.headUnits", { count: counts.units }),
          ...(props.mode === "sent" ? [t("billing.bulkRun.notInRun.headPending")] : []),
        ].join(" · ");
  const total = counts === null ? 0 : counts.accounts + counts.units;

  return (
    <div id="not-in-run" data-not-in-run={props.mode}>
      <CollapsiblePanel
        id="not-in-run"
        title={t("billing.bulkRun.notInRun.title")}
        toggleLabel={t("billing.bulkRun.notInRun.title")}
        aside={aside === null ? undefined : <PanelAside>{aside}</PanelAside>}
      >
        <div className="flex flex-col gap-2 border border-divider bg-surface px-3 py-2">
          <div className="flex flex-wrap items-center gap-3">
            <SegmentedControl
              name="not-in-run"
              label={t("billing.bulkRun.notInRun.filterLabel")}
              segments={[
                { id: "all", label: t("billing.bulkRun.notInRun.all", { count: total }) },
                ...GROUPS.map((group) => ({
                  id: group,
                  label: t(`billing.bulkRun.notInRun.${group === "left_out" ? "leftOut" : group}`, { count: counts?.[group] ?? 0 }),
                })),
              ]}
              active={props.filter}
              onSelect={(id) => {
                props.onFilter(id as NotInRunFilter);
                setPage(1);
              }}
            />
            {props.mode === "sent" && (
              <>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={chosen.length === 0 || props.working}
                  onClick={() => {
                    props.onCatchUp(chosen);
                    setSelected(new Set());
                  }}
                  data-catch-up=""
                >
                  {chosen.length === 0
                    ? t("billing.bulkRun.notInRun.catchUp")
                    : t("billing.bulkRun.notInRun.catchUpN", { count: chosen.length })}
                </Button>
                <Button
                  size="sm"
                  disabled={chosen.length === 0 || props.working}
                  onClick={() => {
                    props.onLeaveForNextCycle(chosen);
                    setSelected(new Set());
                  }}
                  data-next-cycle=""
                >
                  {t("billing.bulkRun.notInRun.nextCycle")}
                </Button>
                <a href={props.links.pending} className="font-heading font-semibold text-accent-700 underline" data-link="pending">
                  {t("billing.bulkRun.notInRun.openPending")}
                </a>
              </>
            )}
          </div>
          {props.mode === "signoff" && <p className="m-0 text-base text-neutral-700">{t("billing.bulkRun.notInRun.note")}</p>}
        </div>

        {rows.length === 0 ? (
          <p className="m-0 mt-3 text-base text-neutral-700" role="status">
            {t("billing.bulkRun.notInRun.empty")}
          </p>
        ) : (
          <TableScroll>
            <PlainTable className={`${RUN_TABLE} mt-3`} data-run-table="not-in-run">
              <thead>
                <tr>
                  <th scope="col" className="w-8">
                    <span className="sr-only">{t("billing.bulkRun.check.selectPage")}</span>
                  </th>
                  <th scope="col">{t("billing.bulkRun.col.account")}</th>
                  <th scope="col">{t("billing.bulkRun.col.unit")}</th>
                  <th scope="col">{t("billing.bulkRun.col.whyNot")}</th>
                  <th scope="col">
                    {props.mode === "sent" ? t("billing.bulkRun.col.waiting") : t("billing.bulkRun.col.fix")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const why = whyNot(row, t);
                  return (
                    <tr key={row.key} data-not-in-run-row={row.group}>
                      <td>
                        {props.mode === "sent" && selectable(row) && (
                          <input
                            type="checkbox"
                            aria-label={t("billing.bulkRun.check.selectRow", { account: row.account_no ?? "" })}
                            checked={selected.has(row.account_id as string)}
                            onChange={() =>
                              setSelected((was) => {
                                const next = new Set(was);
                                const id = row.account_id as string;
                                if (next.has(id)) next.delete(id);
                                else next.add(id);
                                return next;
                              })
                            }
                          />
                        )}
                      </td>
                      <td>
                        {row.kind === "unit" ? (
                          <span className="text-neutral-700">{t("billing.bulkRun.notInRun.noAccount")}</span>
                        ) : (
                          <>
                            <span className="font-heading font-semibold">{row.account_no ?? "—"}</span>
                            {row.customer_name !== null && <span className="block text-neutral-700">{row.customer_name}</span>}
                          </>
                        )}
                      </td>
                      <td>
                        {row.unit_id === null ? (
                          "—"
                        ) : (
                          <a href={props.links.unit(row.unit_id)} target="_blank" rel="noreferrer" className="text-accent-700 underline">
                            {placeLine(row) ?? t("billing.bulkRun.check.openUnit")}
                          </a>
                        )}
                      </td>
                      <td>
                        <span className="flex flex-wrap items-center gap-2">
                          <StatusPill tone={GROUP_TONE[row.group]}>{t(`billing.bulkRun.notInRun.kind.${row.group}`)}</StatusPill>
                          {why !== null && <span>{why}</span>}
                        </span>
                      </td>
                      <td>
                        {props.mode === "sent" && row.kind === "account" ? (
                          <QueueCell row={row} t={t} />
                        ) : row.kind === "unit" ? (
                          <a
                            href={props.links.addAccount(row.unit_id)}
                            target="_blank"
                            rel="noreferrer"
                            className="text-accent-700 underline"
                            data-link="add-account"
                          >
                            {t("billing.bulkRun.addAccount")}
                          </a>
                        ) : row.group === "blocked" || row.group === "held" || row.group === "left_out" ? (
                          <button
                            type="button"
                            className="cursor-pointer border-0 bg-transparent p-0 text-accent-700 underline"
                            onClick={() => props.onFixInCheck(row)}
                            data-fix-in-check=""
                          >
                            {t("billing.bulkRun.notInRun.fixInCheck")}
                          </button>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </PlainTable>
          </TableScroll>
        )}
        {(data?.count ?? 0) > 0 && (
          <ListPager total={data?.count ?? 0} page={page} per={per} onPage={setPage} onPer={(next) => { setPer(next); setPage(1); }} />
        )}
      </CollapsiblePanel>
    </div>
  );
}
