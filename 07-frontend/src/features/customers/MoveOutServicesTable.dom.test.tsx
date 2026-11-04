// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-10051 — move-out step 2, every service on the unit grouped
//           by billing basis (PO 2026-10-11, *"this is correct"*).
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7, habit 2):
//   * a cart left in the METERED table would still let the capacity table pass
//     — so the metered table's rows are counted and the cart asserted absent;
//   * a fetch slot on EVERY row would still be "present on metered rows" — so
//     the slot is asserted absent from the cart's group and from share rows;
//   * a gate that blocks everything would satisfy "a missing reading blocks" —
//     so the same assets are asserted to pass once Estimate is ticked.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import type { Translator } from "@/features/tenancy/settingsShared";
import i18n from "@/i18n";

import { effectiveReadsDraft } from "./moveReadsCapture";
import type { ReadsDraft } from "./moveReadsCapture";
import {
  MoveOutServicesTable,
  missingFinalReads,
  moveOutServicesPath,
  moveOutServicesQueryKey,
} from "./MoveOutServicesTable";
import type { MoveOutMeteredRow, MoveOutServices } from "./MoveOutServicesTable";
import { unitAssetsQueryKey } from "./UnitAssetsPanel";
import type { UnitAssetRow, UnitAssets } from "./UnitAssetsPanel";

afterEach(cleanup);

const t: Translator = (key, params) => i18n.t(key, params);
const UNIT = "unit-7042";
const MOVE_OUT = "2026-10-31";

function asset(row: Partial<UnitAssetRow> & { id: string }): UnitAssetRow {
  return {
    asset_no: null,
    type: null,
    type_name: null,
    category: "meters",
    qualifier: null,
    service: null,
    last_read: null,
    ...row,
  };
}

function assets(): UnitAssets {
  return {
    unit: { id: UNIT, unit_no: "7", label: "Unit 7", premises_id: "p-1", premise_no: "P-1", premise_address: "1 Elm" },
    groups: [
      {
        category: "meters",
        assets: [
          asset({ id: "a-04412", asset_no: "AST-04412", type_name: "Meter", service: null }),
          asset({
            id: "a-5042",
            asset_no: "W-5042",
            type_name: "Meter",
            qualifier: "master",
            service: "water",
            last_read: {
              read_id: "r-1",
              read_at: "2026-09-30",
              channel: "total",
              current_value: "2530.000000",
              current_value_display: "2530 kgal",
              consumption: null,
              unit: "kgal",
            },
          }),
        ],
      },
      { category: "sub_meters", assets: [] },
      {
        category: "behind_the_meter",
        assets: [
          asset({ id: "a-c1", asset_no: "CART-0001", type_name: "Trash cart", category: "behind_the_meter", service: "trash" }),
        ],
      },
      { category: "unclassified", assets: [] },
    ],
    reading_expected: { served: false, reason: "metered_declaration_has_no_reader", tracks: "DEF-495" },
  };
}

function services(): MoveOutServices {
  return {
    unit_id: UNIT,
    as_of: MOVE_OUT,
    services: [
      { service: "water", billing_basis: "metered" },
      { service: "sewer", billing_basis: "share" },
      { service: "trash", billing_basis: "capacity" },
    ],
    metered: [{ service: "water", asset_nos: ["W-5042"] }],
    share: [
      {
        service: "sewer",
        percent: "80.000000",
        percent_basis: "usage",
        basis_service: "water",
        source_asset_nos: ["W-5042"],
        terms_absent: null,
      },
    ],
    capacity: [
      {
        service: "trash",
        type_name: "Trash cart",
        size_class: "CART-96",
        size_name: "Trash 96-gallon cart",
        asset_nos: ["CART-0001", "CART-0002"],
        count: 2,
      },
    ],
  };
}

const fetched: MoveOutMeteredRow[] = [];

function Harness(props: { showErrors: boolean }) {
  const [typed, setTyped] = useState<ReadsDraft>({});
  const draft = effectiveReadsDraft(assets(), typed);
  return (
    <MoveOutServicesTable
      unitId={UNIT}
      draft={draft}
      onChange={setTyped}
      moveOutDate={MOVE_OUT}
      showErrors={props.showErrors}
      renderFetch={(row) => {
        fetched.push(row);
        return <span data-test-fetch={row.assetNo ?? ""} />;
      }}
      t={t}
      timeZone="America/Chicago"
      dateFormat="DD-MMM-YY"
    />
  );
}

function mount(showErrors = false) {
  fetched.length = 0;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(unitAssetsQueryKey(UNIT), assets());
  client.setQueryData(moveOutServicesQueryKey(UNIT, MOVE_OUT), services());
  render(
    <QueryClientProvider client={client}>
      <Harness showErrors={showErrors} />
    </QueryClientProvider>,
  );
}

function table(collection: string): HTMLElement {
  return document.querySelector(`[data-editable-table="${collection}"] table`) as HTMLElement;
}

function heads(collection: string): string[] {
  return [...table(collection).querySelectorAll("thead th")].map((th) => th.textContent?.trim() ?? "");
}

function rows(collection: string): HTMLElement[] {
  return [...table(collection).querySelectorAll("tbody tr")] as HTMLElement[];
}

describe("MoveOutServicesTable — every service on the unit, by billing basis", () => {
  it("draws the three groups with their columns", () => {
    mount();
    expect(heads("move-out-metered")).toEqual([
      "Asset #",
      "Type",
      "Service",
      "Register",
      "Last reading",
      "Last read on",
      "Reading",
      "Read date",
      "Estimate",
      "",
    ]);
    expect(heads("move-out-share")).toEqual(["Service", "Based on", "Comes from"]);
    expect(heads("move-out-capacity")).toEqual([
      "Asset #",
      "Type",
      "Service",
      "Size",
      "Count on unit",
      "Billed through",
    ]);
    // The cart is COUNTED, not read: it left the metered table.
    const metered = rows("move-out-metered");
    expect(metered).toHaveLength(2);
    expect(table("move-out-metered").textContent).not.toContain("CART-0001");
    const [share] = rows("move-out-share");
    expect(share?.textContent).toContain("Sewer");
    expect(share?.textContent).toContain("80.00% of Water usage");
    expect(share?.textContent).toContain("W-5042 final reading");
    const [carts] = rows("move-out-capacity");
    expect(carts?.textContent).toContain("CART-0001, CART-0002");
    expect(carts?.textContent).toContain("Trash 96-gallon cart");
    expect(carts?.textContent).toContain("2");
    expect(carts?.textContent).toContain("31-Oct-26");
    expect(carts?.textContent).not.toContain("CART-96");
  });

  it("a meter linked to no service says so instead of a dash", () => {
    mount();
    const unlinked = rows("move-out-metered").find((row) => row.textContent?.includes("AST-04412"));
    expect(unlinked?.textContent).toContain("Not linked to a service");
  });

  it("puts the fetch slot on readable metered rows only, carrying the move-out date", () => {
    mount();
    const slots = [...document.querySelectorAll("[data-fetch-slot]")].map((el) => el.getAttribute("data-fetch-slot"));
    expect(slots.sort()).toEqual(["AST-04412", "W-5042"]);
    expect(table("move-out-share").querySelector("[data-fetch-slot]")).toBeNull();
    expect(table("move-out-capacity").querySelector("[data-fetch-slot]")).toBeNull();
    const water = fetched.find((row) => row.assetNo === "W-5042");
    expect(water).toMatchObject({ assetId: "a-5042", uom: "kgal", moveOutDate: MOVE_OUT, service: "water" });
  });

  it("a metered row with no reading is required; Estimate clears it; share and capacity need nothing", async () => {
    // AST-04412 was never read, so the prefill leaves its box empty.
    const draft = effectiveReadsDraft(assets(), {});
    expect(missingFinalReads(assets(), draft)).toEqual(["a-04412"]);
    const estimated = { ...draft, "a-04412": { meterNo: "AST-04412", value: "", estimate: true, readAt: "" } };
    expect(missingFinalReads(assets(), estimated)).toEqual([]);

    const user = userEvent.setup();
    mount(true);
    const errors = () => [...document.querySelectorAll('[data-cell-error="reading"]')];
    expect(errors()).toHaveLength(1);
    expect(errors()[0]?.textContent).toBe("Enter a reading or check Estimate.");
    expect(table("move-out-share").querySelector("[data-cell-error]")).toBeNull();
    expect(table("move-out-capacity").querySelector("[data-cell-error]")).toBeNull();
    await user.click(document.getElementById("moveOut-estimate-a-04412") as HTMLElement);
    expect(errors()).toHaveLength(0);
  });

  it("a never-read meter ticked Estimate says no history ONCE, in the fetch slot (DEF-BIL-10129)", async () => {
    // The Estimate cell's own hint is the move-in's inference; on the move-out
    // the fetch slot carries the SERVER's answer, so the cell stays silent.
    const user = userEvent.setup();
    mount();
    await user.click(document.getElementById("moveOut-estimate-a-04412") as HTMLElement);
    expect((document.getElementById("moveOut-estimate-a-04412") as HTMLInputElement).checked).toBe(true);
    expect(document.querySelector('[data-move-in-estimate="no-history"]')).toBeNull();
  });

  it("asks the read AS OF the move-out date", () => {
    expect(moveOutServicesPath(UNIT, MOVE_OUT)).toBe(`/units/${UNIT}/move-out-services?as_of=2026-10-31`);
    expect(moveOutServicesPath(UNIT, "")).toBe(`/units/${UNIT}/move-out-services`);
  });
});
