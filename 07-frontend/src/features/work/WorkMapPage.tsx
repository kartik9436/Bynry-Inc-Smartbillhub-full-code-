// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-029 (the map, a sub-screen of Work-007)
//           Screens: r10 `WRK-09` (`WM-23`, undrawn in the blueprint)
// Rules:    BR-WRK-023 (pin colour reads the dispatch state) · BR-WRK-026 (the
//           same six filters) · B14 rule 2 (one page header) · rule 21
//           (Tailwind; on route-b-migrated.txt) · rule 32 (one sentence)
// Tests:    src/features/work/MapView.test.tsx
// Impacts:  src/App.tsx (one route) · src/features/work/WorkShell.tsx (the Map
//           tab) · src/routing/screenIds.ts (WRK-09)
// ───────────────────────────────────────────────────────
//
// The page is deliberately THIN: it owns the header and the address, `MapView`
// owns the pins and the strip. Splitting them is what lets the map be dropped
// into `Work-007` as a panel later without carrying a second page header with
// it (B14 rule 2 — one header, and two would be the visible symptom).
//
// ⚠ **THE FILTERS COME FROM THE URL, NOT FROM COMPONENT STATE.** A dispatcher
// who narrowed the list to Area = North and then pressed Map must still be
// looking at North — `US-WRK-029` TC-6 — and the only way that survives a page
// load is for the narrowing to live in the address.
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import { useTenantPath } from "@/routing/tenantPath";

import { MapView } from "./MapView";
import { workOrderDetailPath } from "./OrderDetailPage";
import { useWorkTabs } from "./WorkShell";

/** The five chips beside the search box — `BR-WRK-026`'s six, minus `q`, which
 *  the map passes separately. Spelled here rather than imported from the list's
 *  table config because the SERVER is the authority (it answers `400` on a
 *  seventh) and this is only which of them to forward. */
const FILTER_PARAMS = ["type", "status", "priority", "technician", "area"] as const;

export function WorkMapPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const [params] = useSearchParams();

  const filters: Record<string, string> = {};
  for (const name of FILTER_PARAMS) {
    const value = params.get(name);
    if (value) filters[name] = value;
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={t("work.map.title")}
        rollup={t("work.map.description")}
        {...useWorkTabs()}
      />
      <MapView
        q={params.get("q") ?? ""}
        filters={filters}
        // A pin opens the ORDER'S OWN PAGE (`WRK-02`), never its edit page
        // (`CR-168-BRC10` P3.2, `DEF-WRK-9576` — it opened the edit form until
        // round 3). The address comes from the ONE constant the Orders list's
        // 👁 uses, so the list and the map cannot disagree about where an
        // order opens (law 5). Built here and not inside `MapView`, so the map
        // can be reused in a panel without a second copy of the path.
        onOpen={(pin) => navigate(tenantPath(workOrderDetailPath("", pin.id).slice(1)))}
      />
    </div>
  );
}
