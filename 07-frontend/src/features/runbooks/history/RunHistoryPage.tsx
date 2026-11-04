// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-007 (EP-RBS-03) — CR-075 wave I task I6.
// Screens: RBS-008 at `/{tenant}/runbooks/runs`.
// Rules:   `NFR-3` (the page number and the chip travel to the SERVER; nothing
//          here slices an array) · `BR-SHL-020` (a refusal is plain language).
// Tests:   RunHistory.dom.test.tsx
// ───────────────────────────────────────────────────────
// THE PAGE THAT FEEDS `RunHistory`, AND THE ONE THING IT HOLDS.
//
// `RunHistory` is pure over its rows and its request state. This file is the
// only place that knows there is a server.
//
// ⚠ **THE CHIP IS THIS FILE'S STATE AND IT GOES BACK TO THE SERVER.**
// `DataTable`'s `TableRequestState` carries `q`, `sort`, `dir`, `page`, `per`
// and `filters`; the chip row the sheet draws is not one of its declared
// filters, so the value lives here and travels as `f.kind` or `f.outcome`
// (`historyParams` decides which). Nothing anywhere slices the rows the server
// returned.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { api } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import type { PagedRows } from "@/api/paginated";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableRequestState } from "@/components/tableTypes";
import { tenantPathFrom, useTenant } from "@/routing/tenantPath";

import type { RunRow } from "../home/homeEndpoints";
import { listRunHistoryPage } from "./historyEndpoints";
import type { HistoryChipId } from "./historyEndpoints";
import { RunHistory } from "./RunHistory";

/** The request this screen starts from.
 *
 *  `sort` states the SERVER's own order — `-started_at` — rather than asking
 *  for one it ignores. `runs_list` passes `allowed_sorts=()`, so any other
 *  value would be silently discarded and the screen would be describing a sort
 *  that is not happening. */
const INITIAL_STATE: TableRequestState = {
  q: "",
  sort: "started_at",
  dir: "desc",
  page: 1,
  per: DEFAULT_PAGE_SIZE,
  filters: {},
};

export function RunHistoryPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const tenant = useTenant();
  const navigate = useNavigate();

  const [state, setState] = useState<TableRequestState>(INITIAL_STATE);
  const [chip, setChip] = useState<HistoryChipId>("all");

  const query = useQuery<PagedRows<RunRow>>({
    // ONE key from the whole request. A page turn cannot answer from the cache
    // of a different page, and a chip cannot answer from the cache of a
    // different chip.
    queryKey: ["runbooks", "history", state.q, chip, state.page, state.per],
    queryFn: () =>
      listRunHistoryPage({ q: state.q, chip, page: state.page, per: state.per }, client),
  });

  return (
    <RunHistory
      rows={query.data?.rows ?? []}
      total={query.data?.total ?? null}
      loading={query.isPending}
      error={
        query.isError
          ? { reason: refusalText(t, query.error), onRetry: () => void query.refetch() }
          : null
      }
      state={state}
      onStateChange={setState}
      chip={chip}
      onChip={(next) => {
        setChip(next);
        // A new filter is a new list, so it starts at page 1. Leaving the page
        // number alone is how a person lands on an empty page 3 of a 2-page
        // result and reads it as "nothing here".
        setState((current) => ({ ...current, page: 1 }));
      }}
      onBrowseRunbooks={() => navigate(tenantPathFrom(tenant, "runbooks/mine"))}
    />
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-007 (EP-RBS-03; CR-075 wave I task I6) · 07-endpoints.md row 8 · NFR-3
// generated: 2026-09-07 by the CR-075 wave I build lane
// checklist: A✔ B✔ C✔ D✔(GET /runbooks/runs, unchanged) E✔ F✔ G✔ H=n/a
// gates: ./node_modules/.bin/tsc --noEmit (the LOCAL compiler, never npx) · vitest RunHistory.dom.test.tsx · G13
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
