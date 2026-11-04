// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 P3.3 — the Work map gets the Assets map's street
//           ground. PO 2026-10-04 (decision log *"THE WORK MAP SHOWS AN ESRI
//           STREET MAP"*): reuse the Assets map's tile code through ONE shared
//           module both maps import, never a copy. `OQ-WRK-12787` CLOSED.
// Rules:    B16 §10-D6 (the Esri tile egress is ACCEPTED; attribution
//           required) · DEF-INT-4287 (the host has ONE home — the server's
//           `tile_host` — and no map file names one) · DEF-AST-5201 (a failed
//           policy read is not a switched-off basemap)
// Tests:    src/features/assets/AssetMapTiles.test.tsx ·
//           src/features/assets/AssetMapPolicyFailure.dom.test.tsx ·
//           src/features/work/MapView.test.tsx
// Impacts:  src/features/assets/AssetMapTab.tsx (AST-03) ·
//           src/features/work/MapView.tsx (WRK-09) ·
//           GET /integrations/page-policy (apps/integrations/page_policy.py)
// ───────────────────────────────────────────────────────
//
// **THE BASEMAP — THE STREET GROUND UNDER EVERY MAP IN THE PRODUCT, IN ONE
// PLACE.** Moved here word for word from `features/assets/AssetMapTab.tsx` on
// 2026-10-04, when the Work map became the second map to need it. Two copies of
// *where tiles come from* would be two answers, and the first one to drift is
// the one that draws a grey square on a live tenant (`DEF-INT-4287`).
//
// ⚠ **THERE IS NO TILE HOST IN THIS FILE, AND THERE MUST NEVER BE ONE.** The
// host has exactly ONE home — the server, in `live_calls.py`, which is also
// where the generated Content-Security-Policy reads it. `GET
// /integrations/page-policy` answers `tile_host`; a `null` there means the
// utility switched the basemap off. That is what keeps the provider swappable:
// a paid Esri key or the utility's own tile server is a change to the
// connection the policy is generated from, and NO screen changes.
//
// Every pan sends tile requests — and therefore the viewport around the
// tenant's assets and jobs — to whichever server `tile_host` names. On the
// shipped default that is Esri, and that egress is what §10-D6 ACCEPTED for
// Assets and the PO accepted again for Work on 2026-10-04, stated here so
// nobody rediscovers it as a leak.
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import type * as Leaflet from "leaflet";

import type { ApiClient } from "@/api/client";
import { getPagePolicy } from "@/api/endpoints";

// r10's own layer (assets-map.js): Esri World Street Map. Attribution is a
// Leaflet/Esri REQUIREMENT and is not translated copy.
export const ESRI_ATTRIBUTION = "Tiles © Esri";
/** The path Esri's World Street Map serves tiles at, under any host. */
export const TILE_PATH = "/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}";

/** The page policy's cache key — one key, so two maps on one visit share one read. */
export const pagePolicyQueryKey = ["integrations", "page-policy"] as const;

/**
 * The tile template for a permitted host, or `null` when there is none.
 *
 * ⚠ **`null` IS A STATE AND NOT A MISSING VALUE.** It means the utility has
 * switched the basemap off; the map then draws its markers over a plain ground.
 * It must never fall back to a host of its own, because a host the policy does
 * not permit draws a blank grey grid and no error anybody can read — which is
 * the defect this signature exists to make unrepeatable.
 */
export function tileUrlFor(host: string | null | undefined): string | null {
  const trimmed = (host ?? "").trim().replace(/\/+$/, "");
  return trimmed === "" ? null : `${trimmed}${TILE_PATH}`;
}

/**
 * What the ground under the markers is doing — THREE states, not two.
 *
 * ⚠ **`DEF-AST-5201`.** A basemap the utility switched OFF and a policy read
 * that FAILED both mean "draw no tile layer", and for the layer that is the same
 * instruction. For a sentence underneath it they are opposite facts: one is a
 * choice the utility made, the other is the product not working. Folding them
 * together told a clerk their utility had switched the map off when the server
 * had in fact answered 500 — which the PO met on the deployed build on
 * 2026-09-13.
 *
 * It is a pure function because a Leaflet map cannot be mounted in jsdom, so
 * this is the only half of the decision a test can reach.
 */
export type BasemapState =
  | { kind: "pending" }
  | { kind: "drawing"; tileUrl: string }
  | { kind: "off" }
  | { kind: "unavailable" };

export function basemapState(input: {
  host: string | null | undefined;
  answered: boolean;
  failed: boolean;
}): BasemapState {
  if (input.failed) return { kind: "unavailable" };
  if (!input.answered) return { kind: "pending" };
  const url = tileUrlFor(input.host);
  return url === null ? { kind: "off" } : { kind: "drawing", tileUrl: url };
}

/**
 * The tenant's basemap, read from the page policy.
 *
 * ⚠ `tile_host`, BY NAME — never `hosts["img-src"][0]` (`DEF-INT-4287`).
 * `img-src` is a DIRECTIVE and holds every image origin the page may fetch, so
 * its first entry is whichever sorted first and not necessarily the map's.
 *
 * `answered` folds a FAILED read into the answered state, which is right for
 * the tile LAYER (errored and switched-off both mean "draw none") — and
 * `ground` keeps them apart for anything that has to SAY which it is.
 * The answer has not arrived on the first render, and *not yet* is not
 * *switched off*: a map must not act on `tileUrl` until `answered`.
 */
export function useBasemap(client: ApiClient) {
  const policy = useQuery({
    queryKey: pagePolicyQueryKey,
    queryFn: () => getPagePolicy(client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const tileHost = policy.data?.tile_host;
  const tileUrl = useMemo(() => tileUrlFor(tileHost), [tileHost]);
  const answered = policy.data !== undefined || policy.isError;
  const failed = policy.isError;
  const ground = useMemo(
    () => basemapState({ host: tileHost, answered, failed }),
    [tileHost, answered, failed],
  );
  return { tileHost, tileUrl, answered, ground };
}

/** Where a map keeps the tile layer it drew, so it can be re-pointed. */
export interface TileSlot {
  tiles: Leaflet.TileLayer | null;
  tileUrl: string | null;
}

/**
 * Point a Leaflet map's street ground at `tileUrl` — add, swap or remove.
 *
 * ⚠ **THE HOST ARRIVES AFTER THE MAP DOES, AND WITHOUT THIS IT WOULD NEVER
 * REACH IT.** The policy is a request; the map is built on the first render,
 * when its answer is still in flight. A `tileUrl` computed correctly and never
 * applied is hard-won law 2 exactly. It runs in BOTH directions: a host that
 * goes away takes the layer with it, so *switched off* is a map with no basemap
 * rather than a map still calling a host the policy refuses.
 *
 * A tile that fails to LOAD (host blocked, offline) is Leaflet's own business
 * and costs that square of ground only — nothing a map draws on top of it
 * depends on the tiles arriving.
 */
export function syncTileLayer(
  lib: typeof Leaflet,
  map: Leaflet.Map,
  slot: TileSlot,
  tileUrl: string | null,
): void {
  if (slot.tileUrl === tileUrl) return;
  slot.tiles?.remove();
  slot.tiles =
    tileUrl === null ? null : lib.tileLayer(tileUrl, { attribution: ESRI_ATTRIBUTION }).addTo(map);
  slot.tileUrl = tileUrl;
}
