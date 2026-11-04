// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-006 (EP-RBS-03) — CR-075 wave H task H3.
// Screens: RBS-007 (`S153`) at `/{tenant}/runbooks/work`.
// Rules:   `07-endpoints.md` row 17 · `NFR-3` · `BR-SHL-020` (a refusal is
//          plain language) · B14 rule 31.
// Tests:   WorkList.dom.test.tsx
// ───────────────────────────────────────────────────────
// THE PAGE THAT FEEDS `WorkList`, AND THE ONLY PLACE THAT KNOWS THERE IS A
// SERVER. The renderer is pure over its rows, its request state and TODAY —
// one definition of what the screen draws, assertable by a unit test, paintable
// by a render-check in a real browser, and drivable by the server.
//
// ⚠ **`today` IS RESOLVED HERE AND HANDED DOWN.** Gate `G6` and `BR-TEN-043`'s
// spirit: a clock read inside the renderer would make the Age column — the one
// number this screen exists to show — draw differently in a test and in a
// browser, and therefore unassertable.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { api } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { tenantPathFrom, useTenant, useTenantPath } from "@/routing/tenantPath";

import { getWorkItems, patchWorkItem } from "./workEndpoints";
import { WorkList } from "./WorkList";
import type { WorkChip, WorkItemRow } from "./workTypes";

/** The request this screen starts from. `sort` names the SERVER's own order —
 *  weight, then age — rather than asking for one it ignores. */
const INITIAL_STATE: TableRequestState = {
  q: "",
  sort: "weight",
  dir: "desc",
  page: 1,
  per: DEFAULT_PAGE_SIZE,
  filters: {},
};

export function WorkListPage(props: { client?: ApiClient; now?: Date }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const tenant = useTenant();
  const toHref = useTenantPath();
  const navigate = useNavigate();
  const showToast = useToast();
  const queryClient = useQueryClient();

  const [state, setState] = useState<TableRequestState>(INITIAL_STATE);
  const [chip, setChip] = useState<WorkChip>("all");

  const query = useQuery({
    // ONE key from the whole request. A page turn cannot answer from the cache
    // of a different page, and a chip cannot answer from another chip's.
    queryKey: ["work-items", state.q, chip, state.page, state.per],
    queryFn: () =>
      getWorkItems({ q: state.q, chip, page: state.page, per: state.per }, client),
  });

  /** Resolve and reopen — `PATCH /work-items/{id}`, one mutation for both,
   *  because they are one field with two values. */
  const setStatus = useMutation({
    mutationFn: (input: { id: string; status: "open" | "resolved" }) =>
      patchWorkItem(input.id, { status: input.status }, client),
    onSuccess: () => {
      // Every cached page and every chip count is now one row different.
      void queryClient.invalidateQueries({ queryKey: ["work-items"] });
    },
    onError: (error) => showToast(refusalText(t, error)),
  });

  const runbooksTo = tenantPathFrom(tenant, "runbooks");

  return (
    <WorkList
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
        // alone is how a person lands on an empty page 3 of a 2-page result and
        // reads it as *nothing here*.
        setState((current) => ({ ...current, page: 1 }));
      }}
      counts={query.data?.body.chips ?? null}
      onResolve={(row: WorkItemRow) =>
        setStatus.mutate({ id: row.id, status: "resolved" })
      }
      onReopen={(row: WorkItemRow) => setStatus.mutate({ id: row.id, status: "open" })}
      runbooksTo={runbooksTo}
      onRunACheck={() => navigate(runbooksTo)}
      toHref={toHref}
      // Injectable so the Age column can be asserted against a fixed day rather
      // than against whatever day the suite happens to run on.
      today={props.now ?? new Date()}
    />
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-006 (EP-RBS-03; CR-075 wave H task H3) · 07-endpoints.md row 17 · NFR-3
// generated: 2026-09-07 by the CR-075 wave H build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler, never npx) · vitest WorkList.dom.test.tsx · G13
// exceptions: none — every handler `WorkList` declares is required and is passed here
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
