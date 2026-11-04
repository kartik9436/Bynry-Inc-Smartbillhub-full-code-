// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-10190 — Move-in step 1 listed only vacant units.
// Ruling:   PO 2026-10-17, decision log *"MOVE-IN SEARCHES ALL UNITS, NOT ONLY
//           VACANT ONES"* + *"Same day"* (verbatim there).
// Data:     `GET /move-ins/units?q=&page=&per=` · `POST /move-ins/handover`
//           (06-backend/apps/customers/move_in_units.py)
// Tests:    moveInWizard/MoveInUnitSearch.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * The wire shapes and the reads behind Move-in step 1's unit search.
 *
 * ⚠ **THE HOOK LIVES HERE AND IS CALLED BY THE WIZARD, NOT BY THE PICKER.**
 * `MoveInUnitPick` is mounted in static-markup tests that provide no
 * `QueryClientProvider` (`moveShared.tsx` records why), so the query is the
 * wizard's and the picker draws what it is handed — `useAccountSearch`'s
 * posture for the move-out's account finder.
 *
 * ⚠ **WHAT A MOVE-IN MAY DO ON A UNIT IS THE SERVER'S ANSWER.** `selectable`,
 * `path` and `reason_key` are read, never derived from `state` here, so the
 * screen and the commit cannot disagree about a blocked unit.
 */
import { useQuery } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import type { ApiClient } from "@/api/client";
import type { Paginated } from "@/api/paginated";

import { getUnitMoveInMeters } from "../moveDetail/moveDetailEndpoints";
import type { ReadsDraft } from "../moveReadsCapture";

export type MoveInUnitState =
  | "vacant"
  | "closed"
  | "active"
  | "vacation_hold"
  | "marked_disconnect"
  | "disconnected"
  | "move_out_in_progress"
  | "pending_activation";

export type MoveInUnitPath = "move_in" | "move_out_first" | "close_out_first";

export interface MoveInUnitRow {
  id: string;
  unit_no: string | null;
  label: string | null;
  premise_no: string | null;
  premise_name: string | null;
  address: { line1: string | null; city: string | null; state: string | null; postal_code: string | null };
  meters: string[];
  state: MoveInUnitState;
  occupant: {
    account_id: string;
    account_no: string | null;
    name: string | null;
    status_name: string | null;
    closed_at: string | null;
  } | null;
  selectable: boolean;
  path: MoveInUnitPath | null;
  reason_key: string | null;
}

export interface MoveInHandoverAnswer {
  path: "move_out_first" | "close_out_first";
  account_id: string;
  account_no: string | null;
  unit_id: string;
  move_in_park_id: string | null;
  move_out_park_id: string | null;
  moved_out_on: string | null;
}

/** Rows a page: the product's smallest page size. `core.pagination` clamps
 *  `per` to 50/100/200/500/1000, so asking for fewer is served 50 — and a
 *  pager counting pages of ten would then be wrong (found on the walk). */
export const MOVE_IN_UNIT_PER = 50;

export async function searchMoveInUnits(
  term: string,
  page: number,
  client: ApiClient,
): Promise<Paginated<MoveInUnitRow>> {
  const response = await client.get<Paginated<MoveInUnitRow>>("/move-ins/units", {
    query: { q: term, page: String(page), per: String(MOVE_IN_UNIT_PER) },
  });
  if (response.data === null) throw new Error(`empty ${response.status} body`);
  return response.data;
}

export async function startMoveInHandover(
  body: { unit_id: string; opened_at: string; move_in_park_id: string | null },
  client: ApiClient,
): Promise<MoveInHandoverAnswer> {
  const response = await client.post<MoveInHandoverAnswer>("/move-ins/handover", body);
  if (response.data === null) throw new Error(`empty ${response.status} body`);
  return response.data;
}

/** ONE unit's row by id (`?unit_id=`) — a resumed draft re-reads its unit. */
export async function searchMoveInUnitRow(unitId: string, client: ApiClient): Promise<MoveInUnitRow | null> {
  const response = await client.get<Paginated<MoveInUnitRow>>("/move-ins/units", {
    query: { unit_id: unitId },
  });
  return response.data?.results[0] ?? null;
}

export interface MoveInUnitSearchState {
  rows: readonly MoveInUnitRow[];
  total: number;
  loading: boolean;
  failed: boolean;
}

export function useMoveInUnitSearch(
  term: string,
  page: number,
  client: ApiClient,
  enabled: boolean,
): MoveInUnitSearchState {
  const query = useQuery({
    queryKey: ["move-in-unit-search", term, page],
    queryFn: () => searchMoveInUnits(term, page, client),
    enabled,
    staleTime: 15 * 1000,
    retry: false,
  });
  return {
    rows: query.data?.results ?? [],
    total: query.data?.count ?? 0,
    loading: enabled && query.isPending,
    failed: query.isError,
  };
}

interface CarryMeter {
  asset_no: string;
  last_read: { value: string; read_at: string | null } | null;
  needs_opening_read?: boolean;
  children?: CarryMeter[];
}

/**
 * **THE OPENING READS, CARRIED FROM THE CLOSING READS** (PO 2026-10-17: *"once
 * it completes, the clerk returns to the move-in with the opening reading
 * prefilled from the closing reading"*). Every readable meter whose box is
 * still empty takes its last committed reading — which, right after the
 * move-out, IS the closing reading — dated the move-in day (DEF-CUS-10191).
 *
 * ⚠ **ONLY ON `?carry=reads`.** `DEF-CUS-6362` keeps an ordinary move-in's
 * boxes EMPTY, because a prefilled box nobody touched records a reading nobody
 * took. Here the reading WAS taken, minutes ago, on the move-out.
 */
export function carriedReads(
  read: { services?: { meters: CarryMeter[] }[]; unplaced?: CarryMeter[] } | undefined,
  draft: ReadsDraft,
): ReadsDraft | null {
  if (read === undefined) return null;
  const next: ReadsDraft = { ...draft };
  let changed = false;
  const walk = (meter: CarryMeter) => {
    const has = next[meter.asset_no] ?? Object.values(next).find((row) => row.meterNo === meter.asset_no);
    if (meter.last_read !== null && meter.needs_opening_read !== false && has === undefined) {
      next[meter.asset_no] = {
        meterNo: meter.asset_no,
        // `DEF-CUS-10191` — the box shows what a clerk reads (`5894`), never
        // the server's six storage decimals (`5894.000000`).
        value: meter.last_read.value.includes(".")
          ? meter.last_read.value.replace(/0+$/u, "").replace(/\.$/u, "")
          : meter.last_read.value,
        estimate: false,
        // `DEF-CUS-10191` — DEFERRED to the move-in day, not the closing
        // read's own date. That date IS the closing reading, and the read
        // door files the same (meter, day, value) as already recorded
        // (BR-MET-1189) — so the new account got no opening read at all.
        // The same value on the move-in day is BR-CUS-056's *"the next day
        // from the same reading"*.
        readAt: "",
      };
      changed = true;
    }
    for (const child of meter.children ?? []) walk(child);
  };
  for (const service of read.services ?? []) for (const meter of service.meters) walk(meter);
  for (const meter of read.unplaced ?? []) walk(meter);
  return changed ? next : null;
}

/** Seeds the draft ONCE per unit when the move-in came back from a move-out. */
export function useCarriedClosingReads(args: {
  enabled: boolean;
  unitId: string;
  client: ApiClient;
  draft: ReadsDraft;
  setDraft: (draft: ReadsDraft) => void;
}): void {
  const { enabled, unitId } = args;
  const meters = useQuery({
    // The SAME key step 1 reads, so this is one request and one cache entry.
    queryKey: ["move-in-step-unit-meters", unitId],
    queryFn: () => getUnitMoveInMeters(unitId, args.client),
    enabled: enabled && unitId !== "",
    retry: false,
  });
  const done = useRef<string | null>(null);
  useEffect(() => {
    if (!enabled || unitId === "" || meters.data === undefined || done.current === unitId) return;
    done.current = unitId;
    const next = carriedReads(meters.data as unknown as { services: { meters: CarryMeter[] }[] }, args.draft);
    if (next !== null) args.setDraft(next);
    // The draft is read at the moment the meters arrive and never again.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, unitId, meters.data]);
}

/**
 * `DEF-CUS-10193` — **a finished move-out forgets what this browser held about
 * the tenancy it ended.** The move-out wizard cached the account as ACTIVE,
 * and the move-in it was raised from cached the unit's accounts, meters, card
 * and search rows from before; *Back to move-in* is an in-app navigation, so
 * every one of those was served first — and the resumed step 1 believed the
 * unit was still held, so its first Continue did nothing (found on the walk).
 * The account key is `AccountDetailPage.accountDetailQueryKey`'s spelling,
 * written out because that module imports this file's neighbours.
 */
export async function forgetTenancyAfterMoveOut(
  queryClient: QueryClient,
  ids: { accountId: string; unitId: string; moveInParkId?: string | null },
): Promise<void> {
  // `DEF-CUS-10195` (walk W7) — the parked move-in's draft is DROPPED, not
  // invalidated: `useWizardPark` holds a draft for good (`staleTime:
  // Infinity`) and hydrates from whatever it holds, so the copy read when
  // the draft was first written (empty) came back on the way back and was
  // autosaved over the real one — the unit and the date were lost.
  if (ids.moveInParkId) {
    queryClient.removeQueries({ queryKey: ["wizard-park", ids.moveInParkId], exact: true });
  }
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["accounts", "detail", ids.accountId] }),
    queryClient.invalidateQueries({ queryKey: ["move-in-unit-accounts", ids.unitId] }),
    queryClient.invalidateQueries({ queryKey: ["move-in-step-unit-meters", ids.unitId] }),
    queryClient.invalidateQueries({ queryKey: ["move-in-step-unit-facts", ids.unitId] }),
    queryClient.invalidateQueries({ queryKey: ["move-in-unit-row", ids.unitId] }),
    queryClient.invalidateQueries({ queryKey: ["move-in-unit-search"] }),
  ]);
}

/** `?carry=reads` — the move-in was resumed from a finished move-out, so its
 *  opening reads are the closing reads just taken (PO 2026-10-17). */
export const CARRY_PARAM = "carry";
export const CARRY_READS = "reads";

/** The parked move-in a move-out was raised from, on the move-out's draft. */
export const FROM_MOVE_IN_VALUE = "from_move_in";

/** *Back to move-in* — the parked move-in, resumed with the reads carried.
 *  Literal rather than imported from `moveShared` (which imports this file's
 *  neighbours): `/move-ins/new` is `MOVE_IN_WIZARD_ROUTE`. */
export function moveInResumePath(moveInParkId: string): string {
  return `/move-ins/new?parked=${encodeURIComponent(moveInParkId)}&${CARRY_PARAM}=${CARRY_READS}`;
}
