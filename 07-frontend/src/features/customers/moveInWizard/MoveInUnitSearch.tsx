// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-10190 — Move-in step 1 listed only vacant units.
// Ruling:   PO 2026-10-17, decision log *"MOVE-IN SEARCHES ALL UNITS, NOT ONLY
//           VACANT ONES"* + *"Same day"* — vacant first; occupied units shown
//           with a warning and *Start move-out*; *Move-out in progress* and
//           *Pending activation* shown and NOT selectable; removed not listed.
// Rules:    B14 rules 21 (Tailwind; on route-b-migrated.txt), 31 (no id on
//           screen), 33 (labels ≤ 3 words, facts ≤ 6, no rationale), 43 (a
//           COMPONENT, not code inside a page) · IS-3 (debounced search)
// Data:     the wizard's `useMoveInUnitSearch` (moveInUnitSearch.ts)
// Tests:    MoveInUnitSearch.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * **SEARCH EVERY UNIT; PICK ONE; SEE WHAT HAS TO HAPPEN FIRST.**
 *
 * A pure render over what the wizard hands it — the query is the wizard's (see
 * `moveInUnitSearch.ts`). Each row: the unit, its address, its meters, a STATE
 * chip and the occupant. A row the server says is not selectable is greyed and
 * carries its reason; it has no *Use* button at all.
 *
 * Once a unit is chosen the rows fold to one line with *Change*, and — when
 * somebody is still on it — the warning the PO approved (*"warning is good"*)
 * with the one way forward: *Start move-out* (or *Close out* for a cut
 * account, which settles through the close-out act, BR-CUS-430).
 */
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/Button";
import { TextField } from "@/components/FormModal";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { createSearchDebouncer } from "@/components/searchDebounce";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import type { Translator } from "@/features/tenancy/settingsShared";

import { MOVE_IN_UNIT_PER } from "./moveInUnitSearch";
import type { MoveInUnitRow, MoveInUnitSearchState, MoveInUnitState } from "./moveInUnitSearch";

const TONE: Record<MoveInUnitState, StatusTone> = {
  vacant: "success",
  closed: "success",
  active: "warning",
  vacation_hold: "warning",
  marked_disconnect: "warning",
  disconnected: "warning",
  move_out_in_progress: "muted",
  pending_activation: "muted",
};

const joined = (parts: readonly (string | null | undefined)[]): string =>
  parts.filter((part): part is string => typeof part === "string" && part.trim() !== "").join(" · ");

/** `500 Main St, Ottumwa, IA 52501` — the premises' own address (hard rule 8). */
export function unitAddressLine(row: MoveInUnitRow): string {
  // A row with no address block draws no address — never a crash of step 1.
  const a = row.address ?? { line1: null, city: null, state: null, postal_code: null };
  const tail = [a.state, a.postal_code].filter(Boolean).join(" ");
  return [a.line1, a.city, tail].filter((part) => part !== null && part !== undefined && part !== "").join(", ");
}

/** `U-00104 · Apt 104` — what a clerk calls the unit. */
export function unitTitle(row: MoveInUnitRow): string {
  return joined([row.unit_no, row.label]);
}

/** Does a chosen row need the old occupant settled first? */
export function needsSettlingFirst(row: MoveInUnitRow | null): boolean {
  return row !== null && (row.path === "move_out_first" || row.path === "close_out_first");
}

export interface MoveInUnitSearchProps {
  term: string;
  onTermChange: (term: string) => void;
  page: number;
  onPage: (page: number) => void;
  search: MoveInUnitSearchState;
  /** The chosen unit's row (kept by the wizard), or `null`. */
  chosen: MoveInUnitRow | null;
  onChoose: (row: MoveInUnitRow) => void;
  onChange: () => void;
  /** *Start move-out* / *Close out* — the wizard's handover. */
  onSettleFirst: (row: MoveInUnitRow) => void;
  /** Why the handover cannot be pressed yet (no move-in date), or null. */
  settleBlockedReason: string | null;
  settling: boolean;
  settleRefusal: string | null;
  t: Translator;
}

export function MoveInUnitSearch(props: MoveInUnitSearchProps) {
  const { t, chosen } = props;
  const [typed, setTyped] = useState(props.term);
  const debouncer = useMemo(
    () => createSearchDebouncer((q) => props.onTermChange(q), props.term, { minChars: 2 }),
    // The debouncer is built once; the wizard's setter is stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
  useEffect(() => setTyped(props.term), [props.term]);

  if (chosen !== null) {
    return (
      <div className="flex flex-col gap-3" data-move-in-unit-search="chosen">
        <div className="flex items-center justify-between gap-4 border border-divider px-4 py-3">
          <span className="flex min-w-0 flex-col gap-1">
            <span className="font-heading text-base font-semibold text-text">{unitTitle(chosen)}</span>
            <span className="text-sm text-neutral-700">{unitAddressLine(chosen)}</span>
          </span>
          <span className="flex flex-none items-center gap-3">
            <StatusPill tone={TONE[chosen.state]}>{t(`customers.moveIn.unitSearch.state.${chosen.state}`)}</StatusPill>
            <Button size="sm" onClick={props.onChange} data-move-in-unit-change="">
              {t("customers.moveIn.unitSearch.change")}
            </Button>
          </span>
        </div>
        {needsSettlingFirst(chosen) ? (
          <div className="flex flex-col gap-3" data-move-in-unit-occupied={chosen.path ?? ""}>
            <RefusalStrip role="alert">
              {t(
                chosen.path === "close_out_first"
                  ? "customers.moveIn.unitSearch.cutWarning"
                  : "customers.moveIn.unitSearch.occupiedWarning",
                { name: chosen.occupant?.name ?? chosen.occupant?.account_no ?? "" },
              )}
            </RefusalStrip>
            <span className="flex flex-wrap items-center gap-3">
              <Button
                variant="primary"
                disabled={props.settleBlockedReason !== null || props.settling}
                onClick={() => props.onSettleFirst(chosen)}
                data-move-in-start-move-out=""
              >
                {t(
                  chosen.path === "close_out_first"
                    ? "customers.moveIn.unitSearch.startCloseOut"
                    : "customers.moveIn.unitSearch.startMoveOut",
                )}
              </Button>
              {props.settleBlockedReason === null ? null : (
                <span className="text-sm text-neutral-700" data-move-in-settle-why="">
                  {props.settleBlockedReason}
                </span>
              )}
            </span>
            {props.settleRefusal === null ? null : (
              <RefusalStrip role="alert" data-move-in-settle-refused="">
                {props.settleRefusal}
              </RefusalStrip>
            )}
          </div>
        ) : null}
      </div>
    );
  }

  const pages = Math.max(1, Math.ceil(props.search.total / MOVE_IN_UNIT_PER));
  return (
    <div className="flex flex-col gap-3" data-move-in-unit-search="searching">
      <TextField
        id="mvi_unit_search"
        label={t("customers.moveIn.unitSearch.label")}
        required
        value={typed}
        placeholder={t("customers.moveIn.unitSearch.placeholder")}
        onChange={(value) => {
          setTyped(value);
          debouncer.type(value.trim());
        }}
      />
      {props.search.failed ? (
        <RefusalStrip role="alert" data-move-pick-state="units-failed">
          {t("customers.moveIn.unitSearch.failed")}
        </RefusalStrip>
      ) : null}
      {props.search.loading ? (
        <Note data-move-in-unit-search-state="loading">{t("customers.moveIn.unitSearch.loading")}</Note>
      ) : null}
      {!props.search.loading && !props.search.failed && props.search.rows.length === 0 ? (
        <Note data-move-in-unit-search-state="empty">{t("customers.moveIn.unitSearch.none")}</Note>
      ) : null}
      {props.search.rows.length === 0 ? null : (
        <table className="w-full border-collapse text-table" data-move-in-unit-results="">
          <thead>
            <tr className="border-b border-divider text-left font-heading text-table-header uppercase tracking-table-header text-neutral-700">
              <th className="p-2">{t("customers.moveIn.unitSearch.col.unit")}</th>
              <th className="p-2">{t("customers.moveIn.unitSearch.col.meters")}</th>
              <th className="p-2">{t("customers.moveIn.unitSearch.col.status")}</th>
              <th className="p-2">{t("customers.moveIn.unitSearch.col.occupant")}</th>
              <th className="p-2" aria-label={t("customers.moveIn.unitSearch.col.action")} />
            </tr>
          </thead>
          <tbody>
            {props.search.rows.map((row) => (
              <tr
                key={row.id}
                className={`border-b border-divider align-top ${row.selectable ? "" : "bg-neutral-100 text-neutral-600"}`}
                data-move-in-unit-row={row.state}
                data-selectable={row.selectable ? "yes" : "no"}
              >
                <td className="p-2">
                  <span className="flex flex-col gap-1">
                    <span className={row.selectable ? "font-semibold text-text" : "font-semibold"}>
                      {unitTitle(row)}
                    </span>
                    <span className="text-sm">{joined([unitAddressLine(row), row.premise_no])}</span>
                  </span>
                </td>
                <td className="p-2 text-sm">{row.meters.length === 0 ? "—" : row.meters.join(", ")}</td>
                <td className="p-2">
                  <span className="flex flex-col items-start gap-1">
                    <StatusPill tone={TONE[row.state]}>{t(`customers.moveIn.unitSearch.state.${row.state}`)}</StatusPill>
                    {row.reason_key === null ? null : (
                      <span className="text-sm" data-move-in-unit-reason="">
                        {t(row.reason_key)}
                      </span>
                    )}
                  </span>
                </td>
                <td className="p-2 text-sm">
                  {row.occupant === null ? "—" : joined([row.occupant.name, row.occupant.account_no])}
                </td>
                <td className="p-2 text-right">
                  {row.selectable ? (
                    <Button size="sm" onClick={() => props.onChoose(row)} data-move-in-unit-use={row.unit_no ?? ""}>
                      {t("customers.moveIn.unitSearch.use")}
                    </Button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {props.search.total > MOVE_IN_UNIT_PER ? (
        <span className="flex items-center justify-end gap-3 text-sm text-neutral-700" data-move-in-unit-pager="">
          {t("table.pager.pageOf", { page: props.page, pages })}
          <Button
            size="sm"
            disabled={props.page <= 1}
            aria-label={t("table.pager.prev")}
            onClick={() => props.onPage(props.page - 1)}
          >
            ‹
          </Button>
          <Button
            size="sm"
            disabled={props.page >= pages}
            aria-label={t("table.pager.next")}
            onClick={() => props.onPage(props.page + 1)}
          >
            ›
          </Button>
        </span>
      ) : null}
    </div>
  );
}
