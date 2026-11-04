// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-MET-9685 — Reads › *Send someone out* asked
//          `GET /work/flows/meter-read/{asset}/proposed`; the server's generic
//          `/proposed` route takes the FLOW TOKEN, which is `meter_read`, and
//          answered 422 `work.fromFlows.unknownFlow`, so the modal said the
//          utility had published no templates (found by lane WALK-B, CR-168
//          round 7, walking W7 on PostgreSQL).
// Rules:   BR-WRK-055 · `apps/work/from_flows.py` `FLOW_METER_READ = "meter_read"`
// ───────────────────────────────────────────────────────
//
// ⚠ WHAT WOULD MAKE THIS PASS WRONGLY: asserting the path against a constant
// this file defines. It is pinned to the server's own token — the read route
// is `work/flows/<str:flow_kind>/<str:flow_id>/proposed` and the kind is the
// `work_orders.source` token `meter_read`; only the RAISE has the fixed
// `meter-read` segment.
import { describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";

import { proposeMeterFieldWork, raiseMeterFieldWork } from "./readsFieldWorkEndpoints";

function recorder(paths: string[]): ApiClient {
  return {
    get: async (path: string) => {
      paths.push(`GET ${path}`);
      return { status: 200, data: { proposed: [], flow: { kind: "meter_read", ref: "W-7001" } } };
    },
    post: async (path: string) => {
      paths.push(`POST ${path}`);
      return { status: 200, data: { raised: [], not_raised: [], warning: null } };
    },
  } as unknown as ApiClient;
}

describe("DEF-MET-9685 — the Reads door asks the server by the flow's own token", () => {
  it("the offer is read from /work/flows/meter_read/{asset}/proposed", async () => {
    const paths: string[] = [];
    await proposeMeterFieldWork("01a109dd-1424-7c8e-bec4-f5ca0d068ea1", recorder(paths));
    expect(paths).toEqual(["GET /work/flows/meter_read/01a109dd-1424-7c8e-bec4-f5ca0d068ea1/proposed"]);
  });

  it("the raise keeps its own fixed route, /work/flows/meter-read/raise", async () => {
    const paths: string[] = [];
    await raiseMeterFieldWork({ meters: ["01a109dd-1424-7c8e-bec4-f5ca0d068ea1"], templateIds: ["tpl-1"] }, recorder(paths));
    expect(paths).toEqual(["POST /work/flows/meter-read/raise"]);
  });
});
