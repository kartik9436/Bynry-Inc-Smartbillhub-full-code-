// @vitest-environment jsdom
// DEF-CUS-9728 — the Unit & reads tab's SIZE column prints the size's NAME
// (`size_name`, served by `GET /units/{id}/move-in-meters` since 2.538.0),
// never its internal code (`W-58`), as step 1 of the wizard already does.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { UnitReadsTab } from "./UnitReadsTab";

afterEach(cleanup);

const meter = (asset_no: string, size_class: string | null, size_name: string | null) => ({
  asset_no,
  kind: "meter",
  type_name: "Water meter",
  location_note: null,
  size_class,
  size_name,
  unit: "kgal",
  last_read: null,
  needs_opening_read: true,
  children: [],
});

function mountTab() {
  const get = vi.fn(async (url: string) => {
    if (url.endsWith("/move-in-meters")) {
      return {
        status: 200,
        data: {
          unit_id: "u-1",
          services: [{ service: "water", metered: true, meters: [meter("W-5041", "W-58", 'Water 5/8"'), meter("W-5042", null, null)] }],
          unplaced: [],
        },
      };
    }
    return { status: 404, data: null };
  });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <UnitReadsTab unitId="u-1" readings={[]} regional={{ timeZone: "UTC", dateFormat: "MM/DD/YYYY" }} client={{ get } as never} />
    </QueryClientProvider>,
  );
}

describe("DEF-CUS-9728 · the Size column names the size", () => {
  it("prints Water 5/8\" and never the code W-58", async () => {
    mountTab();
    await waitFor(() => expect(screen.getByText("W-5041")).toBeInTheDocument());
    const row = screen.getByText("W-5041").closest("tr") as HTMLElement;
    expect(row).toHaveTextContent('Water 5/8"');
    expect(row).not.toHaveTextContent("W-58");
    const bare = screen.getByText("W-5042").closest("tr") as HTMLElement;
    expect(bare.querySelectorAll("td")[2]).toHaveTextContent("—");
  });
});

describe("DEF-CUS-9765 · image 24's order and its Source column", () => {
  const child = (asset_no: string, kind: string, needs: boolean) => ({
    ...meter(asset_no, null, null),
    kind,
    needs_opening_read: needs,
  });
  function mountTree(readings: unknown[]) {
    const get = vi.fn(async (url: string) =>
      url.endsWith("/move-in-meters")
        ? {
            status: 200,
            data: {
              unit_id: "u-1",
              services: [
                {
                  service: "water",
                  metered: true,
                  // The server's order puts the DEVICE first — the photograph's case.
                  meters: [
                    {
                      ...meter("W-5000", null, null),
                      children: [child("BF-0217", "behind_the_meter", false), child("W-5000-S1", "sub_meter", true)],
                    },
                  ],
                },
              ],
              unplaced: [],
            },
          }
        : { status: 404, data: null },
    );
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <UnitReadsTab unitId="u-1" readings={readings as never} regional={{ timeZone: "UTC", dateFormat: "MM/DD/YYYY" }} client={{ get } as never} />
      </QueryClientProvider>,
    );
  }

  it("lists the meter, then the sub-meter, then the device", async () => {
    mountTree([]);
    await waitFor(() => expect(screen.getByText("W-5000")).toBeInTheDocument());
    const ids = Array.from(document.querySelectorAll("[data-move-reads] tbody tr")).map(
      (tr) => (tr.querySelector("td")?.textContent ?? "").replace("└", "").trim(),
    );
    expect(ids).toEqual(["W-5000", "W-5000-S1", "BF-0217"]);
  });

  it("draws Source after Opening read: Entered at move-in, a later read, Not read", async () => {
    mountTree([
      { register: "W-5000 · total", reading: "1031", unit: "kgal", read_at: "2026-10-10", how: "read", event: "move_in" },
      { register: "W-5000-S1 · total", reading: "214", unit: "kgal", read_at: "2026-10-12", how: "read", event: null },
    ]);
    await waitFor(() => expect(screen.getByText("W-5000")).toBeInTheDocument());
    const heads = Array.from(document.querySelectorAll("[data-move-reads] thead th")).map((th) => th.textContent);
    expect(heads).toEqual(["ID", "Kind", "Size", "Last read", "Opening read", "Source", "State"]);
    const source = (id: string) =>
      (screen.getByText(id).closest("tr") as HTMLElement).querySelector("[data-read-source]");
    expect(source("W-5000")).toHaveTextContent("Entered at move-in");
    expect(source("W-5000-S1")).toHaveTextContent("Meter read");
    expect(source("BF-0217")).toHaveTextContent("Not read");
  });
});
