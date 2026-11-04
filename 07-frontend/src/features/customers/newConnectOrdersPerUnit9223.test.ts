// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-9223 — every work order was raised on the WHOLE build;
//           the unit the clerk chose (step 3's row pick, `Applies to`) was
//           never sent.
// Found:    the New Connection end-to-end web walk, 2026-10-02 / 03
//           (08-qa/screens/nc-e2e-walk-2026-10-03/RESULTS.md).
// Server:   06-backend/tests/test_def_met_9223_orders_per_unit.py
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import type { ProposedWorkOrder } from "@/features/work/workEndpoints";

import type { UnitServiceCell } from "./newConnectDraft";
import { commitPlanOf, commitWorkOrdersOf, emptyDraft, unitServiceKey } from "./newConnectDraft";

function twoUnitDraft(services: string[], grid: Record<string, UnitServiceCell> = {}) {
  return {
    ...emptyDraft(),
    premiseServices: services,
    pattern: { prefix: "Unit ", from: "1", to: "2", includeCommonArea: false },
    unitServiceGrid: grid,
  };
}

function order(id: string, scope: string, service: string | null): ProposedWorkOrder {
  return {
    template_id: id,
    template_no: null,
    name: `Job ${id}`,
    service: service === null ? null : { id: service, code: service, name: service },
    scope,
    sequence: 1,
    job_type: null,
    is_gate: false,
    version: 3,
    est_duration_minutes: null,
  };
}

describe("DEF-MET-9223 — each work order is raised on the unit the clerk chose", () => {
  const services = ["water", "electric"];

  it("a per-unit template on two units' rows is two orders, one per unit", () => {
    const draft = twoUnitDraft(services);
    const proposed = [order("meter-set", "per_unit", "water")];
    const sent = commitPlanOf(draft, null, proposed).work_orders;
    expect(sent).toEqual([
      { template_id: "meter-set", template_version: 3, unit_label: "Unit 1", service: "water" },
      { template_id: "meter-set", template_version: 3, unit_label: "Unit 2", service: "water" },
    ]);
  });

  it("a row's own pick moves the job to that row only", () => {
    const draft = twoUnitDraft(services, {
      [unitServiceKey("Unit 2", "water")]: { workOrderTemplateId: "inspect" },
    });
    const proposed = [order("meter-set", "per_asset", "water"), order("inspect", "per_asset", null)];
    const sent = commitPlanOf(draft, null, proposed).work_orders;
    expect(sent).toEqual([
      { template_id: "meter-set", template_version: 3, unit_label: "Unit 1", service: "water" },
      { template_id: "inspect", template_version: 3, unit_label: "Unit 2", service: "water" },
    ]);
  });

  it("every per-unit job of a service goes on each unit taking it, not only the row's default", () => {
    // The walk's S2 after the first fix: water proposes *Site inspection*
    // (per premise), *Tap and service line* (per unit) and *Meter set* (per
    // asset). A row's cell names ONE job, so the second and third were named
    // by no row and stayed on the whole build.
    const draft = twoUnitDraft(["water"]);
    const proposed = [
      order("site", "per_premise", "water"),
      order("tap", "per_unit", "water"),
      order("meter-set", "per_asset", "water"),
    ];
    expect(commitPlanOf(draft, null, proposed).work_orders).toEqual([
      { template_id: "site", template_version: 3 },
      { template_id: "tap", template_version: 3, unit_label: "Unit 1", service: "water" },
      { template_id: "tap", template_version: 3, unit_label: "Unit 2", service: "water" },
      { template_id: "meter-set", template_version: 3, unit_label: "Unit 1", service: "water" },
      { template_id: "meter-set", template_version: 3, unit_label: "Unit 2", service: "water" },
    ]);
  });

  it("a per-premise template stays one order on the whole build", () => {
    const draft = twoUnitDraft(services);
    const sent = commitPlanOf(draft, null, [order("site", "per_premise", "water")]).work_orders;
    expect(sent).toEqual([{ template_id: "site", template_version: 3 }]);
  });

  it("an added job goes where its Applies to says", () => {
    const draft = twoUnitDraft(services);
    const proposed = [
      order("a", "unit:Unit 2", null),
      order("b", "build", null),
      order("c", `sp:Unit 1\u001Felectric`, null),
    ];
    expect(commitPlanOf(draft, null, proposed).work_orders).toEqual([
      { template_id: "a", template_version: 3, unit_label: "Unit 2" },
      { template_id: "b", template_version: 3 },
      { template_id: "c", template_version: 3, unit_label: "Unit 1", service: "electric" },
    ]);
  });

  it("the review's count is the commit's own list", () => {
    const draft = twoUnitDraft(services);
    const proposed = [order("meter-set", "per_unit", "water"), order("site", "per_premise", null)];
    expect(commitWorkOrdersOf(draft, proposed)).toHaveLength(3);
    expect(commitWorkOrdersOf(draft, proposed)).toEqual(commitPlanOf(draft, null, proposed).work_orders);
  });
});
