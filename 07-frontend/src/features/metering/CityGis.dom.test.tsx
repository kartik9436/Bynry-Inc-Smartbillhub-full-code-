// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-MET-10003 (PO GIS review gap 9) · DEF-INT-10004 (gap 12) ·
//          DEF-MET-10008 (Lane B leftover c — one word, two fields)
// ───────────────────────────────────────────────────────
//
// RED FIRST (2026-10-07, on 2.560.1): `CityGis.tsx` did not exist, the four
// screens drew the City's fields unconditionally, and the property Overview and
// the edit form labelled `external_ref` with the City's word, *Parcel*.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { CityGisStateView } from "@/api/endpoints";
import en from "@/i18n/locales/en.json";

import { CityGisNote, showCityFields, useCityGis } from "./CityGis";

// `?raw`, not `node:fs` — the front end's tsconfig carries no node types, so
// `readFileSync` runs under vitest and FAILS `tsc --noEmit` (G54 caught exactly
// that on this file's first draft).
const SOURCES = import.meta.glob(
  ["./PremisesDetailPage.tsx", "./PremisesListPage.tsx", "./UnitDetailPage.tsx", "./UnitEditModal.tsx"],
  { query: "?raw", eager: true, import: "default" },
) as Record<string, string>;
const read = (name: string) => SOURCES[`./${name}`] ?? "";

function answering(body: CityGisStateView | null, seen: string[] = [], status = 200) {
  return createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL) => {
      seen.push(String(input));
      return new Response(JSON.stringify(body ?? { error: { code: "SYS-INTERNAL" } }), {
        status,
        headers: { "content-type": "application/json" },
      });
    },
  });
}

/** A stand-in for a screen: the City field drawn only when the hook says so. */
function Probe(props: { client: ReturnType<typeof createApiClient> }) {
  const city = useCityGis(props.client);
  return (
    <div>
      <span>always</span>
      {city.showCity && <span data-city-field="">point</span>}
      <CityGisNote messageKey={city.brokenKey} />
    </div>
  );
}

function draw(client: ReturnType<typeof createApiClient>) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <Probe client={client} />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("gap 9 · the City's fields are drawn only where a City GIS is in use", () => {
  it("decides from the server's word, and a failed read never hides a utility's data", () => {
    expect(showCityFields({ data: { state: "none", message_key: "x" }, isError: false })).toBe(false);
    expect(showCityFields({ data: { state: "broken", message_key: "x" }, isError: false })).toBe(true);
    expect(showCityFields({ data: { state: "working", message_key: null }, isError: false })).toBe(true);
    expect(showCityFields({ data: undefined, isError: false })).toBe(false); // in flight
    expect(showCityFields({ data: undefined, isError: true })).toBe(true); // failed
  });

  it("asks the one state route and hides the City field for none", async () => {
    const seen: string[] = [];
    draw(answering({ state: "none", message_key: "integrations.gis.not_connected" }, seen));
    await waitFor(() => expect(seen.length).toBe(1));
    expect(seen[0]).toContain("/api/brazosbend/integrations/gis_esri/state");
    await waitFor(() => expect(screen.getByText("always")).toBeInTheDocument());
    expect(document.querySelector("[data-city-field]")).toBeNull();
    // `none` is not a fault: no sentence about it on a premises screen.
    expect(document.querySelector("[data-city-gis-note]")).toBeNull();
  });

  it("keeps the field and says nothing for a working City", async () => {
    draw(answering({ state: "working", message_key: null }));
    await waitFor(() => expect(document.querySelector("[data-city-field]")).not.toBeNull());
    expect(document.querySelector("[data-city-gis-note]")).toBeNull();
  });

  it("keeps the field when the read fails", async () => {
    draw(answering(null, [], 500));
    await waitFor(() => expect(document.querySelector("[data-city-field]")).not.toBeNull());
  });
});

describe("gap 12 · broken says so, in its own sentence", () => {
  it.each([
    ["integrations.gis.connection_broken", "The city connection is not working."],
    ["integrations.gis.no_layer", "The city layer address is missing."],
  ])("%s", async (key, sentence) => {
    draw(answering({ state: "broken", message_key: key }));
    await waitFor(() => expect(screen.getByText(sentence)).toBeInTheDocument());
    expect(document.querySelector("[data-city-field]")).not.toBeNull();
    expect(sentence).not.toBe(en["integrations.gis.not_connected" as keyof typeof en]);
  });
});

describe("gap 9 · every premises and unit surface asks the same hook", () => {
  // Tier 2 (source): which files gate their City fields. The browser walk
  // (`10-scripts/gis_lane_d_screens_walkthrough.mjs`) is what proves the
  // rendered screen; this is what goes red if a file stops asking.
  it.each(["PremisesDetailPage.tsx", "PremisesListPage.tsx", "UnitDetailPage.tsx", "UnitEditModal.tsx"])(
    "%s",
    (name) => {
      const source = read(name);
      expect(source).toContain('from "@/features/metering/CityGis"');
      expect(source).toMatch(/city\.showCity && \(/);
    },
  );
});

describe("leftover c · one word per field", () => {
  it("labels the import reference as itself and keeps Parcel for the City's parcel", () => {
    const catalogue = en as Record<string, string>;
    expect(catalogue["metering.premises.field.importRef"]).toBe("Import reference");
    expect(catalogue["metering.premises.field.externalRef"]).toBe("Parcel");
    expect(catalogue["customers.newConnect.step3.parcel"]).toBe("Import reference");
    expect(catalogue["customers.newConnect.step8.parcel"]).toBe("Import reference");
    // `external_ref` is drawn under the import word on both of its screens …
    expect(read("PremisesDetailPage.tsx")).toMatch(
      /label=\{t\("metering\.premises\.field\.importRef"\)\}>\s*\{premises\.external_ref/,
    );
    expect(read("PremisesListPage.tsx")).toMatch(
      /id="external_ref"\s*label=\{t\("metering\.premises\.field\.importRef"\)\}/,
    );
    // … and the City's word only ever sits over the City's column.
    expect(read("PremisesDetailPage.tsx")).toMatch(
      /field\.externalRef"\)\}>\s*\{premises\.gis_parcel_id/,
    );
  });
});
