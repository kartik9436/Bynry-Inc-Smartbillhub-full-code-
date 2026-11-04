// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-001 (S9 Plans tab + the header roll-up + the History exit) ·
//           US-RAT-004 (Rate schedules tab) · US-RAT-008 (Charge codes tab) ·
//           US-RAT-009 (Taxes & fees tab) · US-RAT-010/011 (History + bulk rate change)
//           Screens: S9
// Change:   CR-013 part 3 — the Discounts tab is mounted here (§18 row 10). It is the
//           SIXTH entry and r10 draws five; Rate changes was neither removed nor
//           moved, because that is the Product Owner's ruling to make (OQ-286).
// Rules:    BR-SHL-001 (the sidebar's Plans & Rates children are these tabs' paths) ·
//           BR-SHL-003 (an unreachable surface is not drawn) · BR-SHL-011 (URL grammar;
//           an unknown tab falls back, never errors) · BR-SHL-012 (the six A18 states) ·
//           BR-SHL-020 (plain-language failure) · BR-SHL-025 (gating from the SERVER's
//           permission set — `GET /me/permissions`) · BR-SHL-034 (dates via the shared
//           formatter) · BR-RAT-025 (plan-as-bundle: what the explainer copy says) ·
//           BR-RAT-030 (lifecycle) · BR-RAT-031 (no approval state anywhere)
// ───────────────────────────────────────────────────────
// S9 — the Plans & Rates hub: one tab frame over five lists.
//
// Three things this frame settles for every tab below it:
//
//   1. **Who may write.** ONE `GET /me/permissions` read resolves the A4
//      `plans_rates` cell and hands each tab a `readOnly` boolean. A4 gives
//      Billing Clerk and Executive "View", so for them every create/publish/
//      archive/bulk control renders disabled WITH its reason (US-RAT-001 TC-6,
//      US-RAT-011 TC-7) — and the server still refuses a forged write.
//
//   2. **Which tab.** The tab is URL state, because the sidebar's four
//      Plans & Rates children are exactly these paths (AppShell SHELL_NAV).
//
//   3. **The roll-up.** "N plans · N rate schedules · N charge codes ·
//      effective <date>" is served BY THE SERVER on `GET /plans` — no count is
//      computed here, and the effective date goes through DateCell like every
//      other date on the screen.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getMyPermissions, getPlans } from "@/api/endpoints";
import type { RatingRollup } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { useTenantPath } from "@/routing/tenantPath";

import { ChargeCodesTab } from "./ChargeCodesTab";
import { DiscountsTab } from "./DiscountsTab";
import { PlansTab } from "./PlansTab";
import { RateChangesTab } from "./RateChangesTab";
import { RateSchedulesTab } from "./RateSchedulesTab";
import { TaxesFeesTab } from "./TaxesFeesTab";
import {
  DASHBOARD_ROUTE,
  HISTORY_TAB,
  RATING_TABS,
  RATING_TAB_STRIP,
  ratingAccess,
  ratingIsDenied,
  ratingIsReadOnly,
  ratingTabFromParam,
} from "./ratingShared";
import type { RatingTabRender } from "./ratingShared";

import "./PlansRates.css";
import { useRegional } from "@/features/metering/meteringShared";

// The roll-up rides on the plans list because the API exposes no roll-up
// resource of its own; this key holds the unfiltered first page so the header
// stays stable while a tab's own list is being filtered underneath it.
export const ROLLUP_QUERY_KEY = "rollup";

export interface PlansRatesPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
  // IS-8: the tenant TZ + date format arrive with US-SHL-013's formatting
  // service wiring. DateCell REQUIRES both, so the seed values stand in rather
  // than any hand-rolled formatting on this screen (BR-SHL-034).
  timeZone?: string;
  dateFormat?: RegionalDateFormat;
}

export function PlansRatesPage(props: PlansRatesPageProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const client = props.client ?? api;
  // DEF-SHL-3964 — this used to spell its own copy of the seed default, one
  // layer below the resolver. Same defect, same cure: the tenant's own setting.
  // (The first wording of this comment named a prop in backtick-quoted code and
  // G13's scanner read the COMMENT as a prop reference — ten false positives.
  // A comment that contains code-shaped text is code to anything that greps.)
  const { timeZone, dateFormat } = useRegional(props);
  const activeId = ratingTabFromParam(params.tab);

  // BR-SHL-025: the caller's OWN A4 row. Readable by any tenant role, so this
  // is the read that can actually gate a Clerk's view (the /roles grid cannot).
  const permissionsQuery = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  const rollupQuery = useQuery({
    queryKey: queryKeys.plans(ROLLUP_QUERY_KEY),
    queryFn: () => getPlans({}, client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });

  if (permissionsQuery.isPending) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }

  const access = ratingAccess(permissionsQuery.data);
  if (ratingIsDenied(access)) {
    // BR-SHL-003: a role with "—" on plans_rates never sees the surface at all.
    return (
      <PermissionDenied
        helper={t("rating.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  const readOnly = ratingIsReadOnly(access);
  const active = RATING_TABS.find((tab) => tab.id === activeId) ?? RATING_TABS[0];

  // US-SHL-020: this screen no longer draws a header. It DECLARES one — the
  // tab strip, the guidance under it and the slot the active tab's button
  // lands in are all config now, so the next screen inherits the layout
  // instead of re-deriving it (and getting it wrong in its own way, DEF-021).
  const headerTabs = RATING_TAB_STRIP.map((tab) => ({
    id: tab.id,
    label: t(tab.labelKey),
    explainer: tab.explainerKey === undefined ? undefined : t(tab.explainerKey),
  }));

  return (
    <div className="rating-page">
      {/* The tab body renders FIRST and hands back two pieces (addendum r2):
          the button it owns — which for Charge codes and Taxes & fees opens a
          modal held in that tab's own state — and its content. The frame puts
          the first in the header's one primary slot and the second below. */}
      <RatingTabBody
        tabId={active.id}
        readOnly={readOnly}
        client={client}
        timeZone={timeZone}
        dateFormat={dateFormat}
        render={({ action, body }) => (
          <>
            <PageHeader
              // No kicker: the prototype's Plans & Rates head is an H1 and its
              // roll-up. This screen used to render the kicker "Plans & Rates"
              // directly above the H1 "Plans & Rates" (DEF-021).
              title={t("rating.title")}
              rollup={
                rollupQuery.data === undefined ? undefined : (
                  <RollupLine
                    rollup={rollupQuery.data.rollup}
                    timeZone={timeZone}
                    dateFormat={dateFormat}
                  />
                )
              }
              secondaryActions={
                // History is a DESTINATION, not another view of these records,
                // so the prototype gives it a button beside the primary rather
                // than a fifth tab.
                <Button
                  variant="secondary"
                  aria-current={active.id === "history" ? "page" : undefined}
                  onClick={() => navigate(tenantPath(HISTORY_TAB.path))}
                >
                  {t("rating.tab.history")}
                </Button>
              }
              primaryAction={action}
              tabs={headerTabs}
              // On the History route this matches no tab: the strip draws with
              // nothing selected rather than lighting up Plans.
              activeTabId={active.id}
              tabsLabel={t("rating.tabsLabel")}
              onTabSelect={(tab) => {
                const target = RATING_TABS.find((entry) => entry.id === tab.id);
                if (target !== undefined) {
                  navigate(tenantPath(target.path));
                }
              }}
            />
            {body}
          </>
        )}
      />
    </div>
  );
}

/**
 * US-RAT-001 §5: every number here is the SERVER's own count, and the date is
 * the server's own in-force `effective_from`. Nothing is derived on screen —
 * a client-side count would drift the moment a filter was applied.
 */
export function RollupLine(props: {
  rollup: RatingRollup;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const { rollup } = props;
  return (
    <p className="rating-rollup">
      <span>{t("rating.rollup.plans", { count: rollup.plans })}</span>
      <span aria-hidden="true"> · </span>
      <span>{t("rating.rollup.schedules", { count: rollup.rate_schedules })}</span>
      <span aria-hidden="true"> · </span>
      <span>{t("rating.rollup.charges", { count: rollup.charge_codes })}</span>
      {/* DEF-443 — r10 counts six things here and we counted three. */}
      <span aria-hidden="true"> · </span>
      <span>{t("rating.rollup.discounts", { count: rollup.discounts })}</span>
      <span aria-hidden="true"> · </span>
      <span>{t("rating.rollup.taxes", { count: rollup.taxes })}</span>
      {/* Contracts are CR-020, deferred by the PO. The server sends `null` to
          mean THE PRODUCT holds no contracts, which is not the same as a
          tenant having none — so the count renders only once there is one to
          render, rather than drawing a `0` that reads as a fact about this
          utility's data. */}
      {rollup.contracts !== null && (
        <>
          <span aria-hidden="true"> · </span>
          <span>{t("rating.rollup.contracts", { count: rollup.contracts })}</span>
        </>
      )}
      {rollup.effective_from !== null && (
        <>
          <span aria-hidden="true"> · </span>
          <span>
            {t("rating.rollup.effective")}{" "}
            {/* BR-SHL-034: even a header date goes through the ONE formatter. */}
            <DateCell
              value={rollup.effective_from}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
          </span>
        </>
      )}
    </p>
  );
}

/**
 * Which tab is mounted — and nothing else. `render` is passed straight through
 * to it, so the frame above decides where the tab's own button and the tab's
 * own content are placed, and this switch stays a switch.
 */
function RatingTabBody(props: {
  tabId: string;
  readOnly: boolean;
  client: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  render: RatingTabRender;
}) {
  const { tabId, ...rest } = props;
  switch (tabId) {
    case "rates":
      return <RateSchedulesTab {...rest} />;
    case "charge-codes":
      return <ChargeCodesTab {...rest} />;
    // CR-013 part 3 · §18 row 10. ⚠ THIS IS THE SIXTH TAB and r10 draws five —
    // it has Discounts where this frame also keeps `history` (Rate changes).
    // Nothing here removes or moves Rate changes: whether it is kept, folded
    // into the rate detail's `Versions & filings` tab, or retired is the
    // Product Owner's to rule, and a lane must not decide it by deletion.
    case "discounts":
      return <DiscountsTab {...rest} />;
    case "taxes-fees":
      return <TaxesFeesTab {...rest} />;
    case "history":
      return <RateChangesTab {...rest} />;
    default:
      return <PlansTab {...rest} />;
  }
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RAT-001@6304a38 (story+rules snapshot hash — EP-RAT-01 lead story; co-packets EP-RAT-02@0b56fac · EP-RAT-03@7d1a8ef · EP-RAT-04@f69a661)
// generated: 2026-08-09 by story-coder v1 (W1 Plans & Rates frontend lane — the S9 hub) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E2 US-SHL-020 — the prototype's Plans & Rates head carries NO kicker; this screen rendered the kicker "Plans & Rates" directly above the H1 "Plans & Rates" and the duplicate is now gone (DEF-021) · E4 the roll-up has no endpoint of its own — it is served alongside `GET /plans`, so this frame issues one unfiltered plans read purely for the header while the Plans tab issues its own filtered one; reported rather than faking a count client-side · E2 the History tab is not in BR-SHL-001's ratified sidebar child list (see ratingShared.tsx) · E4 [CLOSED 2026-09-05, DEF-SHL-3964] tenant TZ + date format come from the pair the shell publishes; the hand-written `?? "UTC"` / `?? "MM/DD/YYYY"` this screen carried are gone
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
