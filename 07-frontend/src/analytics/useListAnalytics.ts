// ── Trace ──────────────────────────────────────────────
// Change:  CR-169-BRC10 §2 — `list_searched` and `list_filtered`, COUNTS ONLY:
//          whether there was a search, which filter (its NAME, never its
//          value), and how many rows came back. Never the search text.
// Wired:   `components/DataTable.tsx` — the one list every screen draws, so
//          one call covers them all.
// Tests:   src/analytics/useListAnalytics.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useEffect, useRef } from "react";

import { track } from "./client";

export function useListAnalytics(list: {
  list: string;
  q: string;
  filters: Record<string, unknown>;
  settled: boolean;
  total: number | null | undefined;
}): void {
  const activeFilters = Object.entries(list.filters)
    .filter(([, value]) => value !== undefined && value !== null && value !== "" && !(Array.isArray(value) && value.length === 0))
    .map(([name]) => name)
    .sort();
  const signature = `${list.q}\u0000${activeFilters.join(",")}`;
  // What the list looked like when it first settled — its starting state is
  // not something a person did, so it is never sent.
  const seen = useRef<{ q: string; filters: string[] } | null>(null);

  useEffect(() => {
    if (!list.settled) {
      return;
    }
    const before = seen.current;
    seen.current = { q: list.q, filters: activeFilters };
    if (before === null) {
      return;
    }
    const resultCount = typeof list.total === "number" ? list.total : undefined;
    if (before.q !== list.q) {
      track("list_searched", { list: list.list, has_search: list.q !== "", result_count: resultCount });
    }
    for (const name of activeFilters) {
      if (!before.filters.includes(name)) {
        track("list_filtered", { list: list.list, filter: name, result_count: resultCount });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, list.settled]);
}
