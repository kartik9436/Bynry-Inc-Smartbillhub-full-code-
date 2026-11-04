// ── Trace ──────────────────────────────────────────────
// Change:  CR-029 RC-W3-T5 (PO 2026-08-23) — SET-06 and SET-07 become
//          ADDRESSABLE full-page routes with their own screen ids, and Edit
//          opens PRE-FILLED.
// Design:  04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §4, §7
// Story:   US-MET-006 (EP-MET-02 §Stories)  Screens: SET-06.1–4 · SET-07.1–4
// Rules:   BR-SHL-011 (a stateful surface is addressable; unknown params fall
//          back) · BR-MET-035b (System Admin writes; everyone else read-only
//          WITH the reason) · BR-SHL-025 (server-computed access) ·
//          DEF-222 (an edit commits with "Save … ✓", never "Create … ✓")
// B14:     rule 1 (the header's ← names where it EXITS to) · 3 (steppers) ·
//          21 (Tailwind — this file adds no class to any stylesheet)
// Tests:   RoutesCyclesWizardPages.test.tsx
// ───────────────────────────────────────────────────────
/**
 * The four wizard PAGES — create route · edit route · create cycle · edit cycle.
 *
 * ⚠ **WHY THIS FILE EXISTS, AND THE DEFECT IT CLOSES IS ONE NO TEST COULD SEE.**
 * `SettingsRoutesCyclesTab` held the open wizard in `useState`. Three steps into
 * a new route, with 140 premises picked, **a refresh returned the user to the
 * list with nothing kept** — and every component test passed, because nothing in
 * a component test presses F5. BR-SHL-011 already required a URL for every other
 * stateful surface in this product; these four were the exception.
 *
 * ⚠ **THE PAGE IS A LOADER, NOT A SECOND WIZARD.** The steps, the pickers and
 * the commit all stay in `RoutesCyclesWizards.tsx` — a second implementation of
 * a four-step flow is the DEF-348 shape at screen scale. What lives here is the
 * three things a URL makes necessary: resolve the id, fetch the row so Edit
 * arrives PRE-FILLED, and decide where Cancel and Done navigate back to.
 *
 * ⚠ **THE EDITOR FETCHES ITS OWN ROW AND DOES NOT TRUST A ROUTER `state`.** A
 * pasted link, a bookmark and a browser reload all arrive with no state at all;
 * a wizard that pre-filled only when it was navigated to from the list would be
 * addressable in name and blank in fact.
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getCycleDetail, getMyPermissions, getRouteDetail } from "@/api/endpoints";
import type { CycleRow, RouteRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { useTenantPath } from "@/routing/tenantPath";

import { RC_DESC, ROUTES_CYCLES_PATH } from "./routesCyclesShared";
import { CycleWizard, RouteWizard } from "./RoutesCyclesWizards";
import { CELL_VIEW, accessFromPermissions } from "./SettingsPage";
import { apiErrorText, isPermissionDenied, SettingsDenied } from "./settingsShared";
import type { Translator } from "./settingsShared";

/**
 * BR-SHL-025 · BR-MET-035b — read-only is the SERVER's answer, never a role-name
 * check, and it is the same `settings_lookups` cell the Settings frame reads for
 * the Configure tab. A standalone page has no frame above it to inherit from, so
 * it asks the same question rather than assuming the answer.
 */
function useConfigureReadOnly(client: ApiClient): { readOnly: boolean; denied: boolean } {
  const permissions = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
  });
  const access = accessFromPermissions(permissions.data);
  if (access === null) {
    // Unknown is not "denied": the frame that gates this path already let the
    // user through, and refusing on a slow permissions read would flash a
    // denial at an admin. The write itself is still the server's to refuse.
    return { readOnly: false, denied: false };
  }
  return {
    readOnly: access.settings_lookups === CELL_VIEW,
    denied: access.settings_lookups !== CELL_VIEW && access.settings_lookups === "—",
  };
}

// ── SET-06 · the route wizard as a page ────────────────────────────────────

export interface WizardPageProps {
  client?: ApiClient;
}

export function RouteWizardPage(props: WizardPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const params = useParams();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const routeId = params.routeId ?? null;
  const { readOnly, denied } = useConfigureReadOnly(client);

  const routeQuery = useQuery({
    queryKey: ["routes", "detail", routeId ?? ""],
    queryFn: () => getRouteDetail(routeId ?? "", client),
    enabled: routeId !== null,
  });

  function exit(): void {
    navigate(tenantPath(ROUTES_CYCLES_PATH));
  }

  if (denied) {
    return <SettingsDenied helper={t("settings.denied.tab")} />;
  }
  if (routeId !== null && routeQuery.isPending) {
    // A18 §3 — the skeleton, and a sentence beside it. A bare skeleton on a
    // page reached by a pasted link tells a reader nothing about what is
    // arriving; the sentence names the route being opened.
    return (
      <div className="flex flex-col gap-2">
        <p className={RC_DESC}>{t("settings.routes.wizard.loading")}</p>
        <LoadingSkeleton variant="card" />
      </div>
    );
  }
  if (routeId !== null && routeQuery.data === undefined) {
    if (isPermissionDenied(routeQuery.error)) {
      return <SettingsDenied helper={t("settings.denied.tab")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.routes.failedTitle")}
        reason={apiErrorText(routeQuery.error, translate)}
        onRetry={() => void routeQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={exit}
      />
    );
  }

  return (
    <RouteWizard
      // ⚠ `null` OPENS THE CREATOR AND A ROW OPENS THE EDITOR — the wizard's own
      // `editing` flag is `route !== null`, and DEF-222's fix hangs off it: the
      // step-4 title AND the commit verb both change together.
      route={(routeQuery.data as RouteRow | undefined) ?? null}
      client={client}
      readOnly={readOnly}
      onDone={(message) => {
        fireToast(message);
        exit();
      }}
      onCancel={exit}
    />
  );
}

// ── SET-07 · the cycle wizard as a page ────────────────────────────────────

export function CycleWizardPage(props: WizardPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const params = useParams();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const cycleId = params.cycleId ?? null;
  const { readOnly, denied } = useConfigureReadOnly(client);

  // ⚠ **TWO WHOLE-LIST READS STOOD HERE AND BOTH ARE GONE (`DEF-MET-5743`).**
  // The note read *"THERE IS NO `GET /cycles/{id}` — the id route is
  // PATCH+DELETE only — and the wizard needs the ROUTES list anyway for its
  // step 2, so both come from the two list reads"*. **Both halves are false
  // now**: `GET /cycles/{id}` landed in RC-W3b (hard-won law 1 — a comment
  // describing a gap that has closed), and the wizard asks for the page of
  // routes it is drawing rather than being handed every route in the tenant.
  //
  // What that cost: opening the cycle editor walked `/cycles` AND `/routes`
  // to their last page before the first field rendered — at the top of T5,
  // dozens of round trips to edit one cycle's name.
  const cycleQuery = useQuery({
    queryKey: [...queryKeys.cycles, cycleId],
    queryFn: () => getCycleDetail(cycleId!, client),
    enabled: cycleId !== null,
  });

  function exit(): void {
    navigate(tenantPath(ROUTES_CYCLES_PATH));
  }

  if (denied) {
    return <SettingsDenied helper={t("settings.denied.tab")} />;
  }
  if (cycleId !== null && cycleQuery.isPending) {
    return (
      <div className="flex flex-col gap-2">
        <p className={RC_DESC}>{t("settings.cycles.wizard.loading")}</p>
        <LoadingSkeleton variant="card" />
      </div>
    );
  }
  if (cycleId !== null && cycleQuery.data === undefined) {
    const error = cycleQuery.error;
    if (isPermissionDenied(error)) {
      return <SettingsDenied helper={t("settings.denied.tab")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.routes.failedTitle")}
        reason={apiErrorText(error, translate)}
        onRetry={() => {
          void cycleQuery.refetch();
        }}
        onDownloadReport={() => undefined}
        onCancel={exit}
      />
    );
  }

  // ⚠ **READ BY ID, NOT FOUND IN A LIST.** This was `.find` over every cycle
  // in the tenant; `GET /cycles/{id}` serves the same `cycle_dict` the list
  // serves, schedule proposal included, so nothing on the screen changed the
  // day the scan became a fetch.
  const cycle: CycleRow | null = cycleId === null ? null : (cycleQuery.data ?? null);

  return (
    <CycleWizard
      cycle={cycle}
      client={client}
      readOnly={readOnly}
      onDone={(message) => {
        fireToast(message);
        exit();
      }}
      onCancel={exit}
    />
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-029 RC-W3-T5 (B17 §7)
// generated: 2026-08-23 by the RC-W3 frontend lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest (RoutesCyclesWizardPages.test.tsx)
// exceptions: E3 the cycle editor picks its row out of `GET /cycles` because there is no `GET /cycles/{id}` — the id route is PATCH+DELETE only; reported · E4 `useConfigureReadOnly` reads the SAME `settings_lookups` cell the Settings frame reads for the Configure tab, because a standalone page has no frame above it to inherit `readOnly` from · E3 NO browser walkthrough has happened for these pages (hard-won law 6)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
