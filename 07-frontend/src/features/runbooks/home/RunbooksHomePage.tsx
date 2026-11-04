// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-003 (EP-RBS-01) — CR-075 wave D task D2. The routed half of
//          `RBS-001`. Screens: RBS-001 (`S147`).
// Rules:   NFR-3 (every list pages server-side; the footer's total is the
//          SERVER's `count`) · NFR-5 (no cap) · BR-SHL-012 (the shared loading
//          state) · DEF-SHL-4283 (a screen reads the tenant's zone and format
//          from the SHELL, never from the Admin-only settings route)
// Defects: DEF-RBS-4305 (one status per read, so this page makes three)
// Tests:   src/features/runbooks/home/RunbooksHome.dom.test.tsx
// Impacts: src/App.tsx (the `runbooks` index route)
// ───────────────────────────────────────────────────────
/**
 * Fetch, then hand `RunbooksHome` everything it draws.
 *
 * The split is `RunResultPage` / `RunResult`'s, already used twice in this
 * module: the page knows about the network and the tenant slug, the screen
 * knows about pixels, and the screen's DOM test can therefore mount a state
 * that no fixture could otherwise produce — a run in flight, a failed read, an
 * empty product.
 *
 * ⚠ **THREE READS, ONE PER STATUS THE FILTER CAN EXPRESS** (`DEF-RBS-4305`).
 * See `homeEndpoints.ts` for why there are three rather than one; the short
 * version is that `f.outcome` takes a single word and this screen draws two
 * sets of statuses.
 *
 * ⚠ **`nothingHasRunYet` IS COMPUTED FROM THE SERVER'S TOTALS, NEVER FROM ROW
 * COUNTS.** `rows.length === 0` is also true of page 7 of a 300-run history,
 * and a screen that answers *"Nothing has run yet"* to a clerk who is paging
 * through their own runs is worse than one that shows an empty table.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { LoadingSkeleton } from "@/components/StateFrame";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableRequestState } from "@/components/tableTypes";
import { useTenantRegional } from "@/components/TenantRegional";
import { useTenant } from "@/routing/tenantPath";

import { listRunHistory, listRunsAwaitingApproval, listRunsInFlight } from "./homeEndpoints";
import type { RunRow } from "./homeEndpoints";
import { RunbooksHome, RUNBOOKS_HOME_SCREEN } from "./RunbooksHome";
import { homeKpis } from "./runbooksHomeModel";

export { RUNBOOKS_HOME_SCREEN };

/** Both tables start at page 1, 50 rows — `NFR-3`'s default and the server's. */
function startState(sort: string): TableRequestState {
  return defaultRequestState({
    screenId: RUNBOOKS_HOME_SCREEN,
    columns: [],
    getRowId: () => "",
    defaultSort: { sort, dir: "desc" },
  });
}

export function RunbooksHomePage(props: { client?: ApiClient } = {}) {
  const client = props.client ?? api;
  const { t } = useTranslation();
  const tenant = useTenant();
  // The tenant's zone and format come from the SHELL (`GET /shell/display`,
  // readable by every signed-in role), never from `GET /settings/regional`,
  // which is Admin/Executive only — `DEF-SHL-4283`.
  const regional = useTenantRegional();

  const [needsYouState, setNeedsYouState] = useState<TableRequestState>(() =>
    startState("started"),
  );
  const [historyState, setHistoryState] = useState<TableRequestState>(() =>
    startState("finished"),
  );

  const needsYouQuery = useQuery({
    queryKey: ["runbooks", "home", "needsYou", needsYouState.page, needsYouState.per],
    queryFn: () =>
      listRunsAwaitingApproval({ page: needsYouState.page, per: needsYouState.per }, client),
  });

  const inFlightQuery = useQuery({
    queryKey: ["runbooks", "home", "inFlight"],
    queryFn: () => listRunsInFlight(client),
  });

  const historyQuery = useQuery({
    queryKey: ["runbooks", "home", "history", historyState.page, historyState.per],
    queryFn: () => listRunHistory({ page: historyState.page, per: historyState.per }, client),
  });

  if (regional === null) {
    // BR-SHL-012 — the shared loading state, never a screen-local one.
    return <LoadingSkeleton variant="table" />;
  }

  const needsYouTotal = needsYouQuery.data?.total ?? null;
  const inFlightTotal = inFlightQuery.data?.total ?? null;
  const historyTotal = historyQuery.data?.total ?? null;
  const inFlightRows: readonly RunRow[] = inFlightQuery.data?.rows ?? [];

  // Every total is the server's own `count`. The `?? 0` below is only ever
  // rendered when `kpisLoading` is false — i.e. when both reads have answered —
  // because a strip drawn while a count is still `null` would print a confident
  // ZERO under *Waiting for you*, which reads as *nothing is waiting for you*.
  // That was live for one paint and the screenshot is what found it.
  const kpisLoading = needsYouQuery.isPending || inFlightQuery.isPending;
  const kpis = homeKpis({
    awaitingApproval: needsYouTotal ?? 0,
    running: inFlightTotal ?? 0,
  });

  const settled =
    needsYouTotal !== null && inFlightTotal !== null && historyTotal !== null;

  return (
    <RunbooksHome
      tenant={tenant}
      kpis={kpis}
      kpisLoading={kpisLoading}
      inFlight={inFlightRows.length > 0 ? inFlightRows[0] : null}
      needsYou={{
        rows: needsYouQuery.data?.rows ?? [],
        total: needsYouTotal,
        state: needsYouState,
        onStateChange: setNeedsYouState,
        loading: needsYouQuery.isPending,
        error: needsYouQuery.isError ? refusalText(t, needsYouQuery.error) : null,
        onRetry: () => void needsYouQuery.refetch(),
      }}
      history={{
        rows: historyQuery.data?.rows ?? [],
        total: historyTotal,
        state: historyState,
        onStateChange: setHistoryState,
        loading: historyQuery.isPending,
        error: historyQuery.isError ? refusalText(t, historyQuery.error) : null,
        onRetry: () => void historyQuery.refetch(),
      }}
      regional={{ timeZone: regional.timeZone, dateFormat: regional.dateFormat }}
      nothingHasRunYet={
        settled && needsYouTotal === 0 && inFlightTotal === 0 && historyTotal === 0
      }
    />
  );
}

export default RunbooksHomePage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-003 (EP-RBS-01; CR-075 wave D task D2)
// generated: 2026-09-06 by the CR-075 wave D task D2 build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a(no 🔒 path)
// gates: tsc✔ (the LOCAL compiler) · vitest (RunbooksHome.dom.test.tsx mounts THIS page under the real /:tenant/runbooks pattern)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
