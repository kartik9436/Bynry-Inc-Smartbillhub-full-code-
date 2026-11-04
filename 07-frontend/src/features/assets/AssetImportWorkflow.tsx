// ── Trace ──────────────────────────────────────────────
// Change:   CR-028 AST-W1 T5 — BR-AST-046 (PO 2026-08-22, verbatim in CR-028's
//           record: "Currently Import is model - that should be converted in
//           to workflow - on all tabs as required - import name mathcing with
//           tab"). Every assets import entry point NAVIGATES to the ONE ETL
//           workflow runner (BR-MET-096) with its tab's target preselected:
//           Meters → assets_meters · Sub-meters → assets_submeters · Behind
//           the meter → assets_devices.
// Rules:    BR-AST-046 (tab-named imports on the one runner) · BR-MET-096
//           (new imports arrive as TARGETS, never as new pipelines) ·
//           BR-SHL-025 (a thing this deployment cannot honour renders WITH
//           its reason, never blank) · BR-SHL-020 (plain language, no codes)
// Impacts:  App.tsx (the /assets/import route) · AssetRegistryPage.tsx (the
//           per-tab import buttons) · components/workflow/kinds.ts (AST-W3
//           registers the three targets there; this file starts mounting the
//           real runner the commit that lands)
// ───────────────────────────────────────────────────────
// THE ROUTE THE THREE IMPORT BUTTONS LAND ON.
//
// AST-W3 LANDED (2026-08-22): the three assets kinds ARE in `WORKFLOW_KINDS`
// and the backend's `IMPORT_TARGETS` carries the matching targets, so this
// route now mounts the REAL five-stage runner for all three — exactly as this
// file promised, with no change to its own logic. The honest not-available
// state below still exists and still fires, but only for a target genuinely
// nobody registered (e.g. B16 §4.7b's PROPOSED-not-extracted `assets_stock`,
// or a mangled query string) — never for the three shipped tabs.
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { ButtonLink } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";
import { WORKFLOW_KINDS } from "@/components/workflow";
import { ImportWorkflowPage } from "@/features/metering/ImportWorkflowPage";
import type { ImportTarget } from "@/api/endpoints";
import { useTenantPath } from "@/routing/tenantPath";

import { ASSETS_ROUTE } from "./assetsShared";
import type { AssetTab } from "@/api/endpoints";

/** BR-AST-046: the tab → runner-target map, in B16 §4.7b's own vocabulary. */
export const ASSET_IMPORT_TARGETS: Readonly<Record<AssetTab, string>> = {
  meters: "assets_meters",
  sub_meters: "assets_submeters",
  behind_the_meter: "assets_devices",
};

/** Where a tab's `↑ Import …` button navigates (tenant prefix added by the
 *  caller through `useTenantPath`, like every other route constant). */
export function assetImportPath(tab: AssetTab): string {
  return `/assets/import?target=${ASSET_IMPORT_TARGETS[tab]}`;
}

export function AssetImportWorkflowPage() {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const [searchParams] = useSearchParams();
  const target = searchParams.get("target") ?? ASSET_IMPORT_TARGETS.meters;

  // A REGISTERED target mounts the real five-stage runner — one runner, one
  // implementation, the target the only difference (BR-MET-096).
  if (target in WORKFLOW_KINDS) {
    return <ImportWorkflowPage target={target as ImportTarget} />;
  }

  // An unregistered target states the absence with its reason (BR-SHL-025) —
  // plain words, no wave names, no rule ids in the prose (BR-SHL-020). The
  // machine-readable citation rides as data, the G38 discipline.
  return (
    <div className="px-4 pt-6 pb-8">
      <PageHeader title={t("assets.import.unavailable.title")} />
      <div
        className="max-w-xl border border-divider bg-surface px-4 py-4"
        role="note"
        data-tracks="BR-AST-046"
      >
        <p className="m-0 mb-4 text-base">{t("assets.import.unavailable.body")}</p>
        <ButtonLink variant="secondary" to={tenantPath(ASSETS_ROUTE)}>
          {t("assets.import.unavailable.back")}
        </ButtonLink>
      </div>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AST-001@566072b (story+rules snapshot hash — EP-AST-01, the registry this entry point belongs to; change packet CR-028@B16: 04-docs/02-decisions/16-cr028-assets-design.md §4.7/§4.7b · BR-AST-045/046 in 05-assets/02-business-rules.md · AST-W1 T5)
// generated: 2026-08-22 by the CR-028 AST-W1 lane · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (AST-W3 T1 landed: the three kinds are IN WORKFLOW_KINDS, so this route mounts the real runner for them; the stated absence now covers only genuinely unregistered targets)
// checklist: A✔ B✔ C✔ D=deferred(no API call of its own — the runner owns the endpoints; the unavailable state calls nothing) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint --max-warnings 0✔ vitest (AssetRegistry.test.tsx asserts the per-tab paths and the not-available state) · trace_lint✔
// exceptions: E3 the three assets kinds are NOT in WORKFLOW_KINDS yet — that registration is AST-W3 T1 (backend IMPORT_TARGETS + frontend kinds), so today every assets target renders the stated absence; the ImportTarget cast at the mount site is the seam AST-W3 widens · E4 the target travels as a QUERY param where premises/units are fixed props on their routes — three buttons share one route, and the runner still receives the same prop shape
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
