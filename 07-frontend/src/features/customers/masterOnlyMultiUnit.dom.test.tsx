// ── Trace ──────────────────────────────────────────────
// Rule:     BR-CUS-1114 / BR-CUS-1115 — a master account only on a premises of
//           two or more units (PO ruling 2026-10-02, decision log top row:
//           *"single family hime, single unit, we should not do master account"*).
// Defect:   DEF-CUS-9113
// ───────────────────────────────────────────────────────
// RED FIRST: before `buildOpensOwnerMaster` a one-unit build sent
// `create_owner_account: true` (the server then opened a master holding no
// service), the master button had no single-unit reason, and the request page
// linked *Owner's master account* on a one-unit address.
//
// ⚠ WHAT WOULD MAKE THESE PASS WRONGLY: a one-unit draft with NO owner named
// (it sends `false` for that reason) — so every draft here names an owner; and
// a link asserted absent on a fixture whose job is not a move-in — so the job
// is a move-in with a request and a property, which is when the door draws.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { singleUnitMasterReason } from "@/features/metering/CommonAreasTab";
import type { UnitRow } from "@/api/endpoints";

import {
  buildOpensOwnerMaster,
  commitPlanOf,
  emptyDraft,
  ownerMasterRefusedForSingleUnit,
} from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import { ServiceRequestJobLink } from "./ServiceRequestJobLink";

const t = (key: string, params?: Record<string, unknown>) => i18next.t(key, params ?? {});
const REASON = "Single unit. Open a regular account.";

function draftWith(to: string, scope = "new_premise"): NewConnectDraft {
  const blank = emptyDraft();
  return {
    ...blank,
    scope,
    owner: { ...blank.owner, name: "Kestrel Energy Co-op" },
    pattern: { prefix: "Unit", from: "1", to, includeCommonArea: false },
  };
}

describe("BR-CUS-1114 — New Connect opens an owner's master account only on 2+ units", () => {
  it("a one-unit new build sends no owner account and says why", () => {
    const draft = draftWith("1");
    expect(buildOpensOwnerMaster(draft)).toBe(false);
    expect(commitPlanOf(draft, null).create_owner_account).toBe(false);
    expect(ownerMasterRefusedForSingleUnit(draft)).toBe(true);
  });

  it("a two-unit build (a duplex) still opens one", () => {
    const draft = draftWith("2");
    expect(buildOpensOwnerMaster(draft)).toBe(true);
    expect(commitPlanOf(draft, null).create_owner_account).toBe(true);
    expect(ownerMasterRefusedForSingleUnit(draft)).toBe(false);
  });

  it("one unit ADDED to an address on file makes two, so it still opens", () => {
    expect(buildOpensOwnerMaster(draftWith("1", "new_units"))).toBe(true);
  });

  it("a common area does not make a house a building", () => {
    const draft = draftWith("1");
    const withLaundry = { ...draft, pattern: { ...draft.pattern, includeCommonArea: true } };
    expect(buildOpensOwnerMaster(withLaundry)).toBe(false);
  });
});

describe("BR-CUS-1114 — the property's master form", () => {
  const unit = (status: string, common = false) =>
    ({ status, is_common_area: common }) as unknown as UnitRow;
  it("closes on one live home with the reason, and opens on three", () => {
    expect(singleUnitMasterReason([unit("vacant")], t)).toBe(REASON);
    expect(singleUnitMasterReason([unit("vacant"), unit("inactive")], t)).toBe(REASON);
    // A house with a laundry flagged common is still one home.
    expect(singleUnitMasterReason([unit("vacant"), unit("vacant", true)], t)).toBe(REASON);
    expect(singleUnitMasterReason([unit("vacant"), unit("active"), unit("vacant")], t)).toBeNull();
  });
});

describe("BR-CUS-1114 — the request page's Owner's master account door", () => {
  function render(premisesUnits: number | null) {
    return renderToStaticMarkup(
      <MemoryRouter initialEntries={["/brazosbend/requests/r1"]}>
        <Routes>
          <Route
            path="/:tenant/requests/:id"
            element={
              <ServiceRequestJobLink
                job={{ kind: "move_in", number: "MVI-26-0001", id: "j1", state: "pending" }}
                t={t}
                requestId="r1"
                premisesId="p1"
                premisesUnits={premisesUnits}
              />
            }
          />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("is closed with its reason on a one-unit address", () => {
    const html = render(1);
    expect(html).toContain("data-request-owner-master-closed");
    expect(html).toContain(REASON);
    expect(html).not.toContain("data-request-owner-master=\"\"");
  });

  it("is a link on a three-unit address", () => {
    const html = render(3);
    expect(html).toContain("data-request-owner-master=\"\"");
    expect(html).toContain("/brazosbend/premises/p1?tab=common-areas");
    expect(html).not.toContain(REASON);
  });
});
