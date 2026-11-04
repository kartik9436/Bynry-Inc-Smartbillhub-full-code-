// ── Trace ──────────────────────────────────────────────
// Change:   Record links (PO ruling 2026-10-19, decision log "Record links
//           (navigation design)") — group 2: the Account page's Plan group.
// Screens:  S21 (Account detail · Overview · Plan)
// Rules:    B14 rule 31 (no database id is a visible value — the plan id
//           builds the address only) · rule 43 (a piece of UI is a component)
//           · BR-CUS-010 (the plan is READ FROM THE UNIT)
// Tests:    src/routing/recordLinksJobB.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// The plan's NAME, as a link to that plan's page when the server sent the
// plan's id (`unit_plan.id`, the unit's own `rate_plan_id`). A payload with no
// id — a server older than the field — keeps the name as text, and no name at
// all is the stated absence the rest of the group draws.
//
// It is its own file so the Account page's Overview carries one line for it:
// that page is edited by more than one lane at a time.

import { InlineLinkTo } from "@/components/Surfaces";
import type { AccountUnitPlan } from "@/api/endpoints";
import { Dash } from "@/features/metering/meteringShared";
import { planDetailRoute } from "@/features/rating/planDetail/planDetailModel";
import { useTenantPath } from "@/routing/tenantPath";

export function AccountPlanName(props: { plan: AccountUnitPlan | null | undefined }) {
  const tenantPath = useTenantPath();
  const plan = props.plan;
  if (plan === null || plan === undefined || plan.name === null) {
    return <Dash />;
  }
  if (plan.id === null || plan.id === undefined || plan.id === "") {
    return <>{plan.name}</>;
  }
  return <InlineLinkTo to={tenantPath(planDetailRoute(plan.id))}>{plan.name}</InlineLinkTo>;
}
