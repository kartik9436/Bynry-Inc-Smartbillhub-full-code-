// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-029 (EP-WRK-05) TC-1, TC-3, TC-4
// Rules:    BR-WRK-023 (hollow means unassigned) · CR-069 (tiles come through
//           the substrate, never a hardcoded host) · B14 rule 32
// Tests:    this file
// Change:   CR-168-BRC10 P3.1 + P3.2 (round 3, lane MAP2) — jobs at one place
//           cluster under one mark with a count, every order reachable by mouse
//           and keyboard (DEF-WRK-9598); a key for hollow vs solid
//           (DEF-WRK-9599); a pin opens the ORDER, never its edit page
//           (DEF-WRK-9576)
//           CR-168-BRC10 P3.3 (2026-10-04) — the street ground under the pins,
//           from the ONE basemap module the Assets map also imports
//           (`OQ-WRK-12787` CLOSED; decision log *"THE WORK MAP SHOWS AN ESRI
//           STREET MAP"*) · DEF-WRK-9561 (pins on a blank canvas)
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { ESRI_ATTRIBUTION, TILE_PATH } from "@/features/integrations/basemap";
import assetMapSource from "@/features/assets/AssetMapTab.tsx?raw";

import { MapView, boundsOf, placeOf } from "./MapView";
// Vite's `?raw` gives the file's own SOURCE, so TC-4 can be what it is meant to
// be — a grep for a tile host — instead of a check on the module's exports,
// which could never fail (`DEF-182`: a check whose output cannot distinguish
// pass from fail is worse than no check, because it is trusted).
import mapViewSource from "./MapView.tsx?raw";
import mapPageSource from "./WorkMapPage.tsx?raw";
import { WorkMapPage } from "./WorkMapPage";

const PINS = [
  { id: "1", lat: 30.24, lng: -97.78 },
  { id: "2", lat: 30.28, lng: -97.72 },
  { id: "3", lat: 30.26, lng: -97.75 },
];

describe("US-WRK-029 — the pins", () => {
  it("TC-1 · every pin lands inside the box, never on its edge", () => {
    // A pin half outside the frame reads as a bug rather than as a job at the
    // edge of town, which is why the placement insets to 10–90%.
    const bounds = boundsOf(PINS as never);
    for (const pin of PINS) {
      const { left, top } = placeOf(pin, bounds);
      const x = Number.parseFloat(left);
      const y = Number.parseFloat(top);
      expect(x).toBeGreaterThanOrEqual(10);
      expect(x).toBeLessThanOrEqual(90);
      expect(y).toBeGreaterThanOrEqual(10);
      expect(y).toBeLessThanOrEqual(90);
    }
  });

  it("north is UP and east is RIGHT — a map that mirrors is worse than none", () => {
    const bounds = boundsOf(PINS as never);
    const north = placeOf({ lat: 30.28, lng: -97.75 }, bounds);
    const south = placeOf({ lat: 30.24, lng: -97.75 }, bounds);
    // `top` grows DOWNWARD in CSS, so the northern pin must have the smaller
    // value. Getting this backwards produces a map that looks plausible and is
    // upside down — nothing but an assertion catches it.
    expect(Number.parseFloat(north.top)).toBeLessThan(Number.parseFloat(south.top));

    const east = placeOf({ lat: 30.26, lng: -97.72 }, bounds);
    const west = placeOf({ lat: 30.26, lng: -97.78 }, bounds);
    expect(Number.parseFloat(east.left)).toBeGreaterThan(Number.parseFloat(west.left));
  });

  it("a single pin does not divide by zero — it sits in the middle", () => {
    const one = [{ id: "1", lat: 30.26, lng: -97.75 }];
    const place = placeOf(one[0], boundsOf(one as never));
    expect(Number.isFinite(Number.parseFloat(place.left))).toBe(true);
    expect(Number.isFinite(Number.parseFloat(place.top))).toBe(true);
  });

  it("TC-4 · neither map file names a tile host", () => {
    // The basemap is the substrate's declared operation (`map_tiles_public`,
    // CR-069), the same one `features/assets/AssetMapTab.tsx` uses. A hardcoded
    // host here would be a second answer to *where do tiles come from* and the
    // first thing that breaks when a utility runs offline.
    for (const source of [mapViewSource, mapPageSource]) {
      expect(source).not.toMatch(/https?:\/\/[a-z0-9.-]*tile/i);
      expect(source).not.toMatch(/openstreetmap|mapbox|maptiler|arcgis|\{z\}\/\{x\}/i);
    }
  });
});

// ── CR-168-BRC10 P3.3 — the street ground (DEF-WRK-9561) ───────────────────
//
// Leaflet cannot be mounted under jsdom (it throws on `_removePath` during
// cleanup — see `AssetMapPolicyFailure.dom.test.tsx`), so it is replaced by a
// fake that RECORDS what the screen asked of it: which tile template, with
// which attribution, and where it was asked to project each pin. The pins are
// the screen's own buttons, so they are real DOM here and are clicked for real.
const leafletCalls = vi.hoisted(() => ({
  tileLayers: [] as { url: string; options: Record<string, unknown> }[],
  maps: 0,
  removed: 0,
}));

vi.mock("leaflet", () => {
  const map = () => {
    leafletCalls.maps += 1;
    const handlers: Record<string, () => void> = {};
    const self = {
      setView: () => self,
      fitBounds: () => self,
      invalidateSize: () => self,
      on: (names: string, fn: () => void) => {
        for (const name of names.split(" ")) handlers[name] = fn;
        return self;
      },
      // A plain linear stand-in for Web Mercator: east is right, north is up.
      latLngToContainerPoint: (at: [number, number]) => ({
        x: (at[1] + 98) * 1000,
        y: (31 - at[0]) * 1000,
      }),
      remove: () => {
        leafletCalls.removed += 1;
      },
    };
    return self;
  };
  const tileLayer = (url: string, options: Record<string, unknown>) => {
    const layer = {
      addTo: () => {
        leafletCalls.tileLayers.push({ url, options });
        return layer;
      },
      remove: () => undefined,
    };
    return layer;
  };
  const latLngBounds = (points: unknown) => points;
  return { default: { map, tileLayer, latLngBounds }, map, tileLayer, latLngBounds };
});

const ESRI = "https://server.arcgisonline.com";
const ok = (data: unknown) =>
  ({ status: 200, data, etag: null, notModified: false }) as ApiResponse<unknown>;

const PIN = (id: string, lat: number, lng: number, hollow = false) => ({
  id,
  order_no: `WO-${id}`,
  type: "Meter exchange",
  priority: null,
  technician: null,
  dispatch_state: hollow ? "unassigned" : "scheduled",
  due_at: null,
  lat,
  lng,
  address: `${id} Main St`,
  hollow,
});

const DAY = {
  pins: [PIN("101", 30.24, -97.78, true), PIN("102", 30.28, -97.72)],
  unplaced: [
    {
      id: "103",
      order_no: "WO-103",
      type: "Hydrant flush",
      priority: null,
      technician: null,
      dispatch_state: "unassigned",
      due_at: null,
      address: null,
      reason: "no_premises" as const,
    },
  ],
  total: 3,
};

/** Answers the map and the page policy; `policy` decides the tile host, or
 *  throws to stand for a policy read that FAILED. */
function client(policy: { tile_host: string | null } | "fail"): ApiClient {
  return {
    get: async (path: string) => {
      if (path.startsWith("/work-orders/map")) return ok(DAY);
      if (path === "/integrations/page-policy") {
        if (policy === "fail") throw new Error("Server Error (500)");
        return ok({ policy: "", hosts: {}, browser_operations: [], ...policy });
      }
      throw new Error(`unexpected read: ${path}`);
    },
  } as unknown as ApiClient;
}

function mount(apiClient: ApiClient, onOpen = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MapView onOpen={onOpen} client={apiClient} />
    </QueryClientProvider>,
  );
  return onOpen;
}

async function mapBox(): Promise<HTMLElement> {
  return waitFor(() => {
    const box = document.querySelector<HTMLElement>('[data-map="work-orders"]');
    if (box === null || box.querySelector("[data-pin]") === null) throw new Error("no pins yet");
    return box;
  });
}

describe("CR-168 P3.3 — the street map behind the pins", () => {
  beforeEach(() => {
    leafletCalls.tileLayers.length = 0;
    leafletCalls.maps = 0;
    leafletCalls.removed = 0;
  });
  afterEach(() => cleanup());

  it("the tile code has ONE home, and both maps import it", () => {
    // A copy would be a second answer to *where do tiles come from*.
    for (const source of [mapViewSource, assetMapSource]) {
      expect(source).toContain('from "@/features/integrations/basemap"');
      expect(source).not.toMatch(
        /World_Street_Map|export const ESRI_ATTRIBUTION|export function tileUrlFor/,
      );
    }
  });

  it("draws the tenant's tile_host as the street ground, with Tiles © Esri", async () => {
    mount(client({ tile_host: ESRI }));
    await waitFor(() => expect(leafletCalls.tileLayers).toHaveLength(1));
    expect(leafletCalls.tileLayers[0].url).toBe(`${ESRI}${TILE_PATH}`);
    expect(leafletCalls.tileLayers[0].options.attribution).toBe(ESRI_ATTRIBUTION);
    expect(ESRI_ATTRIBUTION).toBe("Tiles © Esri");
  });

  it("a swapped tile_host (a paid key, our own server) needs no screen change", async () => {
    mount(client({ tile_host: "https://tiles.brazosbend.example/" }));
    await waitFor(() => expect(leafletCalls.tileLayers).toHaveLength(1));
    expect(leafletCalls.tileLayers[0].url).toBe(`https://tiles.brazosbend.example${TILE_PATH}`);
  });

  it("the map projects the pins, and they stay the screen's own buttons", async () => {
    const onOpen = mount(client({ tile_host: ESRI }));
    const box = await mapBox();
    await waitFor(() => expect(leafletCalls.maps).toBe(1));
    const hollow = await waitFor(() => {
      const pin = box.querySelector<HTMLButtonElement>('[data-pin="WO-101"]');
      if (pin === null || !pin.style.left.endsWith("px")) throw new Error("not projected yet");
      return pin;
    });
    const filled = box.querySelector<HTMLButtonElement>('[data-pin="WO-102"]')!;
    // East is right and north is up, through the map's own projection.
    expect(Number.parseFloat(filled.style.left)).toBeGreaterThan(
      Number.parseFloat(hollow.style.left),
    );
    expect(Number.parseFloat(filled.style.top)).toBeLessThan(Number.parseFloat(hollow.style.top));
    expect(hollow.dataset.hollow).toBe("true");
    await userEvent.click(hollow);
    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ id: "101" }));
  });

  for (const [name, policy] of [
    ["switched off (tile_host null)", { tile_host: null }],
    ["a FAILED policy read", "fail"],
  ] as const) {
    it(`${name}: no tile layer, and the pins and the list still work`, async () => {
      const onOpen = mount(client(policy));
      const box = await mapBox();
      await waitFor(() => expect(box.querySelectorAll("[data-pin]")).toHaveLength(2));
      await waitFor(() => expect(leafletCalls.maps).toBe(1));
      expect(leafletCalls.tileLayers).toHaveLength(0);
      await userEvent.click(box.querySelector<HTMLButtonElement>('[data-pin="WO-102"]')!);
      expect(onOpen).toHaveBeenLastCalledWith(expect.objectContaining({ id: "102" }));
      const strip = document.querySelector<HTMLElement>('[data-strip="not-on-the-map"]')!;
      await userEvent.click(within(strip).getByRole("button", { name: "WO-103" }));
      expect(onOpen).toHaveBeenLastCalledWith(expect.objectContaining({ id: "103" }));
    });
  }
});

// ── CR-168-BRC10 P3.1 / P3.2 — every job reachable, and a pin opens the order ─
//
// The demo day is 17 open orders on 5 spots. One button per pin put twelve of
// them UNDER another button: present in the DOM (so a count of buttons said 17)
// and unreachable by a click (DEF-WRK-9598). The assertion that matters is
// therefore REACHABILITY — every order id is openable from a control a person
// can see — not presence.
function dayClient(day: unknown): ApiClient {
  return {
    get: async (path: string) => {
      if (path.startsWith("/work-orders/map")) return ok(day);
      if (path === "/integrations/page-policy") return ok({ policy: "", hosts: {}, browser_operations: [], tile_host: null });
      throw new Error(`unexpected read: ${path}`);
    },
  } as unknown as ApiClient;
}

const STACKED = {
  pins: [
    PIN("201", 30.25, -97.75),
    PIN("202", 30.25, -97.75, true),
    PIN("203", 30.25, -97.75),
    PIN("204", 30.27, -97.71),
  ],
  unplaced: [],
  total: 4,
};

describe("CR-168 P3.1 — jobs at one place cluster, and every one is reachable", () => {
  beforeEach(() => {
    leafletCalls.maps = 0;
  });
  afterEach(() => cleanup());

  it("three jobs at one spot draw ONE mark carrying 3; the lone job keeps its pin", async () => {
    mount(dayClient(STACKED));
    const box = await mapBox();
    const clusters = box.querySelectorAll<HTMLButtonElement>("[data-cluster]");
    expect(clusters).toHaveLength(1);
    expect(clusters[0].textContent).toBe("3");
    expect(clusters[0].getAttribute("aria-label")).toBe("3 jobs at 201 Main St");
    // Nothing is stacked any more: every visible mark is at its own place.
    expect(box.querySelectorAll("[data-pin]")).toHaveLength(1);
    expect(box.querySelector('[data-pin="WO-204"]')).not.toBeNull();
  });

  it("a cluster with ANY unassigned job is hollow — the fact a dispatcher scans for is never hidden", async () => {
    mount(dayClient(STACKED));
    const box = await mapBox();
    expect(box.querySelector<HTMLElement>("[data-cluster]")!.dataset.hollow).toBe("true");
  });

  it("by MOUSE: the cluster opens its list, and each job in it opens that order", async () => {
    const onOpen = mount(dayClient(STACKED));
    const box = await mapBox();
    await userEvent.click(box.querySelector<HTMLButtonElement>("[data-cluster]")!);
    const panel = await screen.findByRole("region", { name: "3 jobs at this place" });
    const orders = within(panel).getAllByRole("button");
    expect(orders.map((b) => b.textContent)).toEqual([
      expect.stringContaining("WO-201"),
      expect.stringContaining("WO-202"),
      expect.stringContaining("WO-203"),
    ]);
    await userEvent.click(within(panel).getByRole("button", { name: /WO-202/ }));
    expect(onOpen).toHaveBeenLastCalledWith(expect.objectContaining({ id: "202" }));
  });

  it("by KEYBOARD alone: Tab reaches the cluster, Enter opens it, Tab + Enter opens an order", async () => {
    const onOpen = mount(dayClient(STACKED));
    const box = await mapBox();
    const user = userEvent.setup();
    const cluster = box.querySelector<HTMLButtonElement>("[data-cluster]")!;
    for (let i = 0; i < 10 && document.activeElement !== cluster; i += 1) await user.tab();
    expect(document.activeElement).toBe(cluster);
    await user.keyboard("{Enter}");
    const panel = await screen.findByRole("region", { name: "3 jobs at this place" });
    // Focus moves INTO the list, so the next key press is on an order.
    await waitFor(() => expect(panel.contains(document.activeElement)).toBe(true));
    await user.keyboard("{Enter}");
    expect(onOpen).toHaveBeenLastCalledWith(expect.objectContaining({ id: "201" }));
  });

  it("all 17 demo orders on 5 spots are reachable (the beta's own day)", async () => {
    const spots = [
      [30.21, -97.8, 3],
      [30.29, -97.74, 4],
      [30.25, -97.7, 5],
      [30.23, -97.76, 3],
      [30.26, -97.77, 2],
    ] as const;
    let n = 300;
    const pins = spots.flatMap(([lat, lng, count]) =>
      Array.from({ length: count }, () => PIN(String((n += 1)), lat, lng, n % 2 === 0)),
    );
    const onOpen = mount(dayClient({ pins, unplaced: [], total: pins.length }));
    const box = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-map="work-orders"]');
      if (found === null || found.querySelector("[data-cluster]") === null) throw new Error("no marks yet");
      return found;
    });
    const marks = box.querySelectorAll("[data-cluster], [data-pin]");
    expect(marks).toHaveLength(5);
    const reached = new Set<string>();
    for (const cluster of Array.from(box.querySelectorAll<HTMLButtonElement>("[data-cluster]"))) {
      await userEvent.click(cluster);
      const panel = await screen.findByRole("region", { name: /jobs at this place/ });
      for (const order of within(panel).getAllByRole("button")) {
        await userEvent.click(order);
        reached.add((onOpen.mock.lastCall![0] as { id: string }).id);
      }
    }
    expect(reached.size).toBe(17);
  });
});

describe("CR-168 — the key says what a hollow and a solid mark mean (DEF-WRK-9599)", () => {
  afterEach(() => cleanup());

  it("draws Key · Unassigned (hollow) · Assigned (solid), in the list's own words", async () => {
    mount(dayClient(STACKED));
    await mapBox();
    const key = document.querySelector<HTMLElement>('[data-map-key]')!;
    expect(key).not.toBeNull();
    expect(within(key).getByText("Key")).toBeTruthy();
    const entries = Array.from(key.querySelectorAll<HTMLElement>("[data-key-entry]"));
    expect(entries.map((e) => [e.dataset.keyEntry, e.textContent?.trim()])).toEqual([
      ["hollow", "Unassigned"],
      ["solid", "Assigned"],
    ]);
  });
});

describe("CR-168 P3.2 — a pin opens the ORDER, not its edit page (DEF-WRK-9576)", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("clicking a pin on /:tenant/work/map lands on /:tenant/work/orders/{id}", async () => {
    vi.spyOn(api, "get").mockImplementation(((path: string) =>
      dayClient(STACKED).get(path)) as never);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/brazosbend/work/map"]}>
          <Routes>
            <Route path="/:tenant/work/map" element={<WorkMapPage />} />
            <Route path="/:tenant/work/orders/:orderNo" element={<p data-landed="order">order</p>} />
            <Route path="/:tenant/work/orders/:orderNo/edit" element={<p data-landed="edit">edit</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const box = await mapBox();
    await userEvent.click(box.querySelector<HTMLButtonElement>('[data-pin="WO-204"]')!);
    await waitFor(() => expect(document.querySelector("[data-landed]")).not.toBeNull());
    expect(document.querySelector<HTMLElement>("[data-landed]")!.dataset.landed).toBe("order");
  });

  it("the page builds the address from the ONE constant the Orders list uses", () => {
    expect(mapPageSource).toContain("workOrderDetailPath");
    expect(mapPageSource).not.toMatch(/\/edit`/);
  });
});
