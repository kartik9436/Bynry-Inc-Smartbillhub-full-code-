// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave G — `G1` (`PUJ-30`), `G2` (`PUJ-31`), `G3` (`PUJ-32`).
//          SUPERSEDES the CR-028 debt-sweep version of this file, which pinned
//          the behaviour `G2` REVERSES: choosing an asset used to navigate to
//          `/assets/:id/reassign?unit=<this unit>` and finish a one-step job on
//          another screen, with the clerk losing the unit they stood on.
// Screens: PRM-03 Assets tab (S15 unit detail)
// Rules:   BR-AST-006 (the row's action set is the SERVER's) · BR-AST-011/017/
//          022 (assign to a unit; available or in service only) · BR-AST-018/
//          020 (a status change is an append-only entry with a legal target;
//          retire is terminal and is not one of them) · BR-AST-500 (the
//          connection size a search can now ask for) · BR-SHL-025 (a role that
//          may not write keeps the reason) · B14 rule 31 (no catalogue CODE on
//          screen — the tenant's own NAME)
// ───────────────────────────────────────────────────────
// ⚠ **THESE ASSERT THE REQUEST, NOT THE CACHE.** The version this replaces
// seeded the answer into React Query and asserted a string was in the markup,
// which proves the component and nothing about what travels to the server. The
// whole of `G1` is a query parameter — `?terms=` — so a test that never looks
// at a URL could pass over a box that searches nothing at all. Every case below
// records the fetches and reads them back.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { AssetRow, UnitRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import i18n from "@/i18n";

import {
  AttachedAssetStatusModal,
  InventoryFinder,
  removeChipTerms,
  unitAssignInventoryQueryKey,
} from "./UnitDetailPage";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function unit(): UnitRow {
  return {
    id: "u-101a",
    unit_no: "U-00101-A",
    premises_id: "p-101",
    premise_no: "P-00101",
    premise_address: "1408 Bluestem Ln",
    label: "Unit A",
    unit_type: "residential",
    floor_label: null,
    square_feet: null,
    rate_plan_id: null,
    plan_effective_from: null,
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    lat: null,
    lng: null,
    point: { lat: null, lng: null, source: "premises" as const },
    active: true,
    services: ["electric", "water"],
    meters: [],
    occupancy: "occupied",
    occupant: "Miller, Sarah",
    account_no: "A-00412",
    status: "active",
    metered_services: [],
    sub_metered: false,
  };
}

/** One shelved meter, as `GET /assets?terms=…&f.assigned=false` serves it. */
function spare(overrides: Partial<AssetRow> = {}): AssetRow {
  return {
    id: "inv-5100",
    asset_no: "W-5100",
    serial_no: null,
    type: "meter",
    type_name: "Meter",
    tab: "meters",
    status: "inventory",
    status_name: "Inventory",
    behavior_class: "available",
    meter_type: "walk_by",
    meter_type_name: "walk-by",
    read_method: "walk_by",
    read_method_name: "walk-by",
    multiplier: "1",
    size_class: "W-58",
    // The size AS A CLERK READS IT, beside the code (`DEF-AST-7130`).
    size_class_name: null,
    unit: "kgal",
    net_metering: false,
    manufacturer: "Badger Meter",
    model: null,
    install_date: null,
    parent_asset_no: null,
    service_point_id: null,
    assigned_unit_id: null,
    assigned_to: null,
    assigned_address: null,
    assigned: false,
    test_due: false,
    retire_date: null,
    retire_reason: null,
    replaced_by: null,
    actions: ["assign", "edit", "delete"],
    ...overrides,
  };
}

interface Chip {
  family: string;
  key: string;
  value: string;
  label: string;
  terms: string;
}

/** The `?terms=` answer: rows PLUS the server's own reading of the words. */
function finderAnswer(rows: AssetRow[], chips: Chip[], unmatched: string[]) {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    resolved: {
      filters: Object.fromEntries(chips.map((chip) => [chip.key, chip.value])),
      chips,
      unmatched,
    },
  };
}

/** A client that records every URL it is asked for and answers from a script. */
function recordingClient(script: (url: string) => unknown) {
  const seen: { url: string; body: unknown }[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      seen.push({
        url,
        body: init?.body === undefined || init.body === null ? null : JSON.parse(String(init.body)),
      });
      // ⚠ `528156cb9` (2026-09-28, `DEF-AST-7660`) made the finder ask the
      // server which services are size-banded before it renders. Every other
      // URL here was answered with the finder's page, so this one got a page
      // with no `banded` list and the form crashed on open — three cases red
      // from that commit. It is answered with the server's own shape; NO
      // service bands in this fixture, so no case here has to pick a size.
      const body = url.includes("/assets/size-banded-services")
        ? { banded: [], not_banded: [], not_ruled: [] }
        : script(url);
      return new Response(JSON.stringify(body ?? {}), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  return { client, seen };
}

/** Marks where a picked asset WOULD land, so `G2` can prove it no longer does. */
function ReassignLanding() {
  const location = useLocation();
  return <div data-testid="reassign-landing">{location.pathname + location.search}</div>;
}

function mountFinder(
  client: ReturnType<typeof recordingClient>["client"],
  writeBlockedReason: string | null = null,
  onAssigned: (assetNo: string) => void = () => undefined,
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/units/u-101a?tab=assets`]}>
          <Routes>
            <Route
              path="/:tenant/premises/units/:unitId"
              element={
                <InventoryFinder
                  unit={unit()}
                  client={client}
                  t={t}
                  writeBlockedReason={writeBlockedReason}
                  onAssigned={onAssigned}
                />
              }
            />
            <Route path="/:tenant/assets/:assetId/reassign" element={<ReassignLanding />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("G1 — the inventory search takes what a clerk is holding", () => {
  it("the typed words travel as ?terms= and come back as the server's chips", async () => {
    const user = userEvent.setup();
    const { client, seen } = recordingClient(() =>
      finderAnswer(
        [spare()],
        [
          {
            family: "size_class",
            key: "size_class",
            value: "W-58",
            label: 'Water 5/8"',
            terms: "5/8 water",
          },
          {
            family: "status",
            key: "status",
            value: "inventory",
            label: "Inventory",
            terms: "inventory",
          },
          { family: "type", key: "type", value: "meter", label: "Meter", terms: "meter" },
        ],
        ["depot"],
      ),
    );
    mountFinder(client);

    await user.click(screen.getByRole("button", { name: "+ Assign from inventory" }));
    await user.type(screen.getByLabelText(/Find one for/), "5/8 water meter inventory depot");

    // ⚠ **THE REQUEST IS THE ASSERTION.** A box that searched nothing would
    // still render every chip below, because the chips come out of the fixture.
    await waitFor(
      () => {
        const asked = seen.map((call) => call.url).filter((url) => url.includes("terms="));
        expect(asked.length).toBeGreaterThan(0);
        // `+` is how a space travels in a query string; the words are what
        // this asserts, not the encoding.
        expect(decodeURIComponent(asked[asked.length - 1]).replace(/\+/g, " ")).toContain(
          "terms=5/8 water meter inventory depot",
        );
        // The standing narrowing is the ASSIGNMENT predicate and never a
        // status: a status of our own would override a stage the clerk typed
        // and the chip would be drawn over rows it did not filter.
        expect(asked[asked.length - 1]).toContain("f.assigned=false");
        expect(asked[asked.length - 1]).not.toContain("f.status=");
      },
      { timeout: 3000 },
    );

    // The chips are asserted INSIDE their own container and not by page text:
    // *Inventory* and *Meter* are also the row's own stage and type cells, so a
    // bare `getByText` would pass on a page drawing no chips at all.
    const chips = await screen.findByTestId("finder-chips");
    expect(chips).toHaveTextContent('Water 5/8"');
    expect(chips).toHaveTextContent("Inventory");
    expect(chips).toHaveTextContent("Meter");
    // B14 rule 31 — the catalogue CODE is the FILTER's value and never the
    // visible one. `W-58` reaches the size cell as data and never a chip.
    expect(chips.textContent ?? "").not.toContain("W-58");
    // A word nothing in the tenant's catalogues matched is SAID, never dropped.
    expect(screen.getByText("Not one of your words: depot")).toBeInTheDocument();
  });

  it("removeChipTerms takes back exactly the words the chip ate", () => {
    expect(removeChipTerms("5/8 water meter inventory", "5/8 water")).toBe("meter inventory");
    // One word out per word eaten — a repeated word is not swept away with it.
    expect(removeChipTerms("meter meter inventory", "meter")).toBe("meter inventory");
    expect(removeChipTerms("5/8 WATER", "5/8 water")).toBe("");
  });

  it("nothing on the shelf matching is a sentence, not an empty table", async () => {
    const user = userEvent.setup();
    const { client } = recordingClient(() => finderAnswer([], [], ["zzz"]));
    mountFinder(client);
    await user.click(screen.getByRole("button", { name: "+ Assign from inventory" }));
    expect(await screen.findByText("Nothing on the shelf matches that.")).toBeInTheDocument();
  });
});

describe("G2 — assigning finishes on the unit", () => {
  it("Assign ✓ posts the reassign and does NOT open the asset's own page", async () => {
    const user = userEvent.setup();
    const assigned: string[] = [];
    const { client, seen } = recordingClient((url) =>
      url.includes("/reassign")
        ? { id: "inv-5100", asset_no: "W-5100", warnings: [] }
        : finderAnswer([spare()], [], []),
    );
    mountFinder(client, null, (assetNo) => assigned.push(assetNo));

    await user.click(screen.getByRole("button", { name: "+ Assign from inventory" }));
    // ⚠ **THE SERVICE IS CHOSEN FIRST, AND THIS STEP IS THE RULING** (PO
    // 2026-09-19, `DEF-MET-5860`). `W-5100` is a METER, so `Assign ✓` is
    // unreachable until a service is named — see the block below, which proves
    // exactly that. Before the ruling this line did not exist and the press
    // landed a meter on the unit with no service point at all.
    await user.selectOptions(await screen.findByLabelText("Service"), "water");
    await user.click(await screen.findByRole("button", { name: "Assign ✓" }));

    await waitFor(() => {
      const post = seen.find((call) => call.url.includes("/assets/inv-5100/reassign"));
      expect(post).toBeDefined();
      expect(post?.body).toMatchObject({ unit_id: "u-101a", record_final_read: false });
    });
    expect(assigned).toEqual(["W-5100"]);
    // ⚠ **THE RED PROOF FOR `G2`.** Before this wave the click NAVIGATED and
    // this element rendered; the whole task is that it no longer does.
    expect(screen.queryByTestId("reassign-landing")).toBeNull();
  });

  it("BR-AST-006/022: a row the server would refuse keeps the button and says why", async () => {
    const user = userEvent.setup();
    const { client } = recordingClient(() =>
      finderAnswer(
        [
          spare({
            status: "needs_repair",
            status_name: "Needs repair",
            behavior_class: "out_of_service",
            actions: ["view", "log_repair", "reassign", "retire"],
          }),
        ],
        [],
        [],
      ),
    );
    mountFinder(client);
    await user.click(screen.getByRole("button", { name: "+ Assign from inventory" }));
    const button = await screen.findByRole("button", { name: "Assign ✓" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", "Not free to assign");
  });

  it("BR-SHL-025: a role that may not write keeps the disabled button WITH its reason", () => {
    const { client } = recordingClient(() => finderAnswer([], [], []));
    mountFinder(client, "Read-only access");
    const button = screen.getByRole("button", { name: "+ Assign from inventory" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", "Read-only access");
  });
});

/**
 * **THE ASSIGN STEP ASKS WHICH SERVICE** — `DEF-MET-5860`, PO ruling
 * 2026-09-19, verbatim: *"this is correct fix it"*.
 *
 * The reported symptom: a clerk assigns a meter from inventory on a unit's
 * Assets tab and `Service`, `Size` and `On since` all show a dash. The service
 * was one of the three, and it is the one that makes the meter UNBILLABLE:
 * without it no service point is created and there is nothing for the bill run
 * to price.
 *
 * ⚠ **THE BACKEND WAS NEVER MISSING THIS.** `_reassign_inner` has read
 * `service` and called `ensure_service_point` since the module shipped, and
 * `POST /assets/{id}/reassign` passes the payload straight through. **The
 * screen posted `{unit_id, record_final_read: false}` and nothing else** — a
 * capability nothing calls, which is hard-won law 2 and cost exactly what an
 * absent one would have.
 *
 * ⚠ **LAW 7 — WHAT WOULD MAKE THESE PASS WRONGLY.** *"It posts a service"*
 * passes on the WRONG service, so every case below asserts the service that
 * was CHOSEN. *"The button is disabled"* passes on a row the server refuses
 * for some other reason, so the no-service case asserts the reason TEXT and
 * that **no request was made at all**.
 */
describe("the assign asks which service (DEF-MET-5860)", () => {
  /** A shelved sub-meter — `MEASURING_TYPES`' third member. */
  const subMeter = (): AssetRow =>
    spare({
      id: "inv-5200",
      asset_no: "W-5200",
      type: "sub_meter",
      type_name: "Sub-meter",
      tab: "sub_meters",
      parent_asset_no: "W-5100",
    });

  /** A shelved backflow preventer — behind the meter, measures nothing. */
  const backflow = (): AssetRow =>
    spare({
      id: "inv-5300",
      asset_no: "BF-5300",
      type: "backflow",
      type_name: "Backflow preventer",
      tab: "behind_the_meter",
      meter_type: null,
      meter_type_name: null,
      read_method: null,
      read_method_name: null,
      unit: null,
      size_class: null,
    });

  function shelf(row: AssetRow) {
    return recordingClient((url) =>
      url.includes("/reassign")
        ? { id: row.id, asset_no: row.asset_no, warnings: [] }
        : finderAnswer([row], [], []),
    );
  }

  it("offers only the services this unit can take, in seed order, with NO default", async () => {
    const user = userEvent.setup();
    const { client } = shelf(spare());
    mountFinder(client);
    await user.click(screen.getByRole("button", { name: "+ Assign from inventory" }));

    const picker = (await screen.findByLabelText("Service")) as HTMLSelectElement;
    // ⚠ **NO DEFAULT.** The ruling is explicit — *"Nothing may guess which
    // service a meter serves"* — so the leading option is the placeholder and
    // its value is the empty string.
    expect(picker.value).toBe("");
    const options = [...picker.options].map((option) => option.value);
    // The fixture unit takes electric and water. `SERVICE_CODES` seed order
    // puts electric FIRST, and the premises list happens to hold them that way
    // too — so the assertion is the WHOLE list, which would catch an eleven-
    // service picker as well as a mis-ordered two-service one.
    expect(options).toEqual(["", "electric", "water"]);
    expect([...picker.options].map((option) => option.textContent)).toEqual([
      "Choose a service",
      "Electric",
      "Water",
    ]);
  });

  it("a meter with no service chosen CANNOT be assigned — and nothing is posted", async () => {
    const user = userEvent.setup();
    const { client, seen } = shelf(spare());
    mountFinder(client);
    await user.click(screen.getByRole("button", { name: "+ Assign from inventory" }));

    const assign = await screen.findByRole("button", { name: "Assign ✓" });
    // ⚠ **UNREACHABLE, NOT REFUSED AFTER THE FACT.** A server refusal would
    // bounce the clerk back to an empty shelf with their search gone; the
    // frame's own STATES block puts this refusal *"before the press, in the
    // row"*.
    expect(assign).toBeDisabled();
    expect(assign).toHaveAttribute("title", "Choose a service first");

    await user.click(assign);
    // ⚠ **THE REQUEST IS THE ASSERTION.** A disabled button that still fired
    // its handler would pass the two lines above and lose the whole defect.
    expect(seen.filter((call) => call.url.includes("/reassign"))).toHaveLength(0);
  });

  it("a meter WITH a service posts that service, and it is the one chosen", async () => {
    const user = userEvent.setup();
    const { client, seen } = shelf(spare());
    mountFinder(client);
    await user.click(screen.getByRole("button", { name: "+ Assign from inventory" }));
    // `water` is the SECOND option, chosen deliberately: picking the first
    // would pass on a picker that silently defaults.
    await user.selectOptions(await screen.findByLabelText("Service"), "water");
    await user.click(await screen.findByRole("button", { name: "Assign ✓" }));

    await waitFor(() => {
      const post = seen.find((call) => call.url.includes("/assets/inv-5100/reassign"));
      expect(post).toBeDefined();
      expect(post?.body).toMatchObject({
        unit_id: "u-101a",
        record_final_read: false,
        service: "water",
      });
    });
  });

  it("a SUB-METER is held to the same rule as a meter", async () => {
    const user = userEvent.setup();
    const { client, seen } = shelf(subMeter());
    mountFinder(client);
    await user.click(screen.getByRole("button", { name: "+ Assign from inventory" }));

    const assign = await screen.findByRole("button", { name: "Assign ✓" });
    expect(assign).toHaveAttribute("title", "Choose a service first");

    await user.selectOptions(await screen.findByLabelText("Service"), "electric");
    await user.click(await screen.findByRole("button", { name: "Assign ✓" }));
    await waitFor(() => {
      const post = seen.find((call) => call.url.includes("/assets/inv-5200/reassign"));
      expect(post?.body).toMatchObject({ service: "electric" });
    });
  });

  it("a BACKFLOW PREVENTER assigns with no service, exactly as it did before", async () => {
    const user = userEvent.setup();
    const { client, seen } = shelf(backflow());
    mountFinder(client);
    await user.click(screen.getByRole("button", { name: "+ Assign from inventory" }));

    // ⚠ **OPTIONAL FOR EVERYTHING ELSE** — the ruling's own words. A backflow
    // preventer has no register, `BR-AST-009` binds `MEASURING_TYPES` only, and
    // a clerk must not be made to declare a service for a thing that has none.
    const assign = await screen.findByRole("button", { name: "Assign ✓" });
    expect(assign).toBeEnabled();
    await user.click(assign);

    await waitFor(() => {
      const post = seen.find((call) => call.url.includes("/assets/inv-5300/reassign"));
      expect(post).toBeDefined();
      expect(post?.body).toMatchObject({ unit_id: "u-101a", record_final_read: false });
      // Omitted, not sent empty: the server branches on truthiness and an
      // empty string would be a service nobody chose.
      expect(post?.body).not.toHaveProperty("service");
    });
  });
});

describe("G3 — an attached asset's status changes from its row", () => {
  const STAGES = {
    count: 5,
    next: null,
    previous: null,
    results: [
      { code: "inventory", name: "Inventory", active: true, behavior_class: "available" },
      { code: "active", name: "Installed", active: true, behavior_class: "in_service" },
      {
        code: "needs_repair",
        name: "Needs repair",
        active: true,
        behavior_class: "out_of_service",
      },
      { code: "in_repair", name: "In repair", active: true, behavior_class: "out_of_service" },
      { code: "retired", name: "Retired", active: true, behavior_class: "terminal" },
    ],
  };

  function mountStatus(client: ReturnType<typeof recordingClient>["client"], asset: AssetRow) {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/units/u-101a?tab=assets`]}>
            <Routes>
              <Route
                path="/:tenant/premises/units/:unitId"
                element={
                  <AttachedAssetStatusModal
                    unit={unit()}
                    asset={asset}
                    client={client}
                    t={t}
                    dateFormat="MM/DD/YYYY"
                    onClose={() => undefined}
                    onDone={() => undefined}
                  />
                }
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  it("the form posts a maintenance entry carrying the new stage, the date and the reason", async () => {
    const user = userEvent.setup();
    const { client, seen } = recordingClient((url) =>
      url.includes("/maintenance")
        ? { id: "m-1", resulting_status: "needs_repair", kind: "repair", date: "2026-09-08" }
        : STAGES,
    );
    mountStatus(
      client,
      spare({
        id: "a-5000",
        asset_no: "W-5000",
        status: "active",
        status_name: "Installed",
        behavior_class: "in_service",
        actions: ["view", "edit", "reassign", "log_repair", "retire"],
      }),
    );

    expect(await screen.findByText("Change the status of W-5000")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(/New status/)).toBeInTheDocument());
    const options = Array.from(
      (screen.getByLabelText(/New status/) as HTMLSelectElement).querySelectorAll("option"),
    ).map((option) => option.textContent);
    // BR-AST-020/030: retire is TERMINAL and is the System Admin's own wizard
    // with a reason, a date and a book-value treatment. It must not be one
    // click away on a screen about a flat.
    expect(options).toContain("Needs repair");
    expect(options).not.toContain("Retired");
    expect(options).not.toContain("Installed"); // "no change" is not a change

    await user.selectOptions(screen.getByLabelText(/New status/), "needs_repair");
    await user.type(screen.getByLabelText(/^On/), "2026-09-08");
    await user.type(screen.getByLabelText(/^Why/), "Register glass cracked");
    await user.click(screen.getByRole("button", { name: "Change status" }));

    await waitFor(() => {
      const post = seen.find((call) => call.url.includes("/assets/a-5000/maintenance"));
      expect(post).toBeDefined();
      expect(post?.body).toMatchObject({
        status: "needs_repair",
        kind: "repair",
        detail: "Register glass cracked",
        date: "2026-09-08",
      });
    });
  });

  it("a stage with nowhere legal to go says so instead of drawing an empty select", async () => {
    const { client } = recordingClient(() => STAGES);
    mountStatus(
      client,
      spare({
        id: "a-ret",
        asset_no: "W-9000",
        status: "retired",
        status_name: "Retired",
        behavior_class: "terminal",
        actions: ["view"],
      }),
    );
    expect(await screen.findByText("Retired has nowhere to move to.")).toBeInTheDocument();
    expect(screen.queryByLabelText(/New status/)).toBeNull();
  });
});

describe("the finder's query key", () => {
  it("is keyed by the terms, so two searches do not share one answer", () => {
    expect(unitAssignInventoryQueryKey("5/8 water")).not.toEqual(unitAssignInventoryQueryKey(""));
  });
});
