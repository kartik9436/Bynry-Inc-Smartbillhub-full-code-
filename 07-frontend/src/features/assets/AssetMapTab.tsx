// ── Trace ──────────────────────────────────────────────
// Change:   CR-028 AST-W5 T3 (B16 §4.6 · §10-D6 RULED 2026-08-22:
//           third-party tiles ACCEPTED; premises gained lat/lng; the geocoder
//           selection is recorded in apps/metering/geocode.py).
//           Screens: AST-03.
// Rules:    §10-D6 (the Esri tile egress is the ACCEPTED third-party choice —
//           r10's own layer, attribution required) · §10-D7 (no work-order
//           fact: r10's popup WO-#### lines are OMITTED, not faked) ·
//           BR-AST-026 (the uuid only ADDRESSES "Open details →") ·
//           BR-AST-031 (marker/filter states key off the behavior CLASS) ·
//           BR-SHL-011's spirit (an unknown filter value falls back) ·
//           B14 r21 (Tailwind)
// Impacts:  AssetRegistryPage.tsx (mounts this on ?tab=map) ·
//           GET /assets/geo (apps/assets/api.py) · package.json (leaflet —
//           the ONE dependency this CR adds, r10's own 1.9.4) ·
//           GET /integrations/page-policy (apps/integrations/page_policy.py —
//           `tile_host`, the ONE place the basemap's host is decided)
// Defects:  DEF-INT-4287 (2026-09-06) — this tab drew a flat grey rectangle on
//           the deployed build for EVERY tenant. See the note above
//           `ESRI_ATTRIBUTION` in `features/integrations/basemap.ts`, where
//           the tile code moved (CR-168-BRC10 P3.3); the fix is on both sides
//           of one payload.
// ───────────────────────────────────────────────────────
// AST-03 — the Assets map: Leaflet, r10's filter bar, three-state legend,
// popup card with "Open details →".
//
// HOW THE MAP STAYS TESTABLE WITHOUT TILES: everything decidable is a PURE
// export (filterGeoAssets · geoNeedsAttention · markerStyle · mapVocab), and
// Leaflet itself is loaded by DYNAMIC IMPORT inside useEffect — so a jsdom
// render exercises the filter bar, the count line and the legend while the
// canvas stays an empty <div>, and no test ever fights Leaflet for a canvas.
//
// THE TILE LAYER is r10's shape with the required "Tiles © Esri" attribution,
// and its HOST is the tenant's — read from `GET /integrations/page-policy`,
// which is the same row the Content-Security-Policy is generated from. Every
// pan sends tile requests (and therefore the viewport around tenant asset
// locations) to whichever server that names; on the shipped default that is
// Esri, and that egress is what §10-D6 ACCEPTED, stated here so nobody
// rediscovers it as a leak.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import type * as Leaflet from "leaflet";
import "leaflet/dist/leaflet.css";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { ASSET_MAX_PER, getAssetGeo } from "@/api/endpoints";
import type { AssetGeoRow } from "@/api/endpoints";
import { LoadingSkeleton } from "@/components/StateFrame";
import { syncTileLayer, useBasemap } from "@/features/integrations/basemap";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { AssetDash, assetDetailPath, useTranslator } from "./assetsShared";

export const assetGeoQueryKey = ["assets", "geo"] as const;

// ⚠ **THE TILE CODE LIVES IN `features/integrations/basemap.ts` (2026-10-04,
// `CR-168-BRC10` P3.3).** `ESRI_ATTRIBUTION`, `TILE_PATH`, `tileUrlFor`,
// `basemapState`, the page-policy read and the layer swap were defined HERE
// until the Work map became the second map to need them; they moved word for
// word, with their `DEF-INT-4287` and `DEF-AST-5201` notes, so both maps
// import one answer to *where do tiles come from* and neither holds a copy.
//: The demo plant's centre (r10's own setView) — the map recentres onto the
//: markers' bounds whenever any exist, so this only decides the empty view.
const DEFAULT_CENTER: [number, number] = [30.263, -97.74];
const DEFAULT_ZOOM = 13;

// Marker colors are CANVAS literals, not theme tokens: Leaflet paints SVG
// paths outside the styled DOM, and r10's two are kept verbatim.
const MARKER_BASE = "#201e1d";
const MARKER_WARN = "#ec3013";

// ── The pure half (provable without a browser or a network) ────────────────

export interface GeoFilters {
  q: string;
  type: "" | "meter" | "master" | "sub" | "device";
  status: "" | "active" | "attention" | "pending";
  service: string;
  area: string;
}

export const EMPTY_GEO_FILTERS: GeoFilters = {
  q: "",
  type: "",
  status: "",
  service: "",
  area: "",
};

/** r10's legend definition of "needs attention": repair, test due, pending —
 *  i.e. anything not simply in service, keyed off the behavior CLASS
 *  (BR-AST-031) plus the served BR-AST-007 test-due derivation. */
export function geoNeedsAttention(row: Pick<AssetGeoRow, "behavior_class" | "test_due">): boolean {
  return row.behavior_class !== "in_service" || row.test_due === true;
}

/** The r10 filter semantics, one predicate per control, AND-combined. */
export function filterGeoAssets(rows: readonly AssetGeoRow[], filters: GeoFilters): AssetGeoRow[] {
  const term = filters.q.trim().toLowerCase();
  return rows.filter((row) => {
    if (term !== "") {
      const haystack = [
        row.asset_no,
        row.premises ?? "",
        row.unit ?? "",
        row.role.kind === "sub" ? row.role.parent : "",
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(term)) {
        return false;
      }
    }
    if (filters.type === "meter" && row.tab !== "meters") {
      return false;
    }
    if (filters.type === "master" && row.role.kind !== "master") {
      return false;
    }
    if (filters.type === "sub" && row.tab !== "sub_meters") {
      return false;
    }
    if (filters.type === "device" && row.tab !== "behind_the_meter") {
      return false;
    }
    if (filters.status === "active" && geoNeedsAttention(row)) {
      return false;
    }
    if (
      filters.status === "attention" &&
      !(row.behavior_class === "out_of_service" || row.test_due === true)
    ) {
      return false;
    }
    if (filters.status === "pending" && row.behavior_class !== "available") {
      return false;
    }
    if (filters.service !== "" && row.service !== filters.service) {
      return false;
    }
    if (filters.area !== "" && row.area !== filters.area) {
      return false;
    }
    return true;
  });
}

/** The Service and Area filter vocabularies — the DATA's own, never a
 *  constant (a tenant's areas are their BR-MET-071 list). */
export function mapVocab(rows: readonly AssetGeoRow[]): {
  services: string[];
  areas: string[];
} {
  return {
    services: [...new Set(rows.map((row) => row.service).filter((s): s is string => !!s))].sort(),
    areas: [...new Set(rows.map((row) => row.area).filter((a): a is string => !!a))].sort(),
  };
}

/** r10's marker grammar: masters draw the HOLLOW RING (big, low fill), and
 *  needs-attention colors the mark. Pure, so the legend and the canvas can
 *  never disagree. */
export function markerStyle(row: AssetGeoRow): {
  radius: number;
  color: string;
  weight: number;
  fillColor: string;
  fillOpacity: number;
} {
  const master = row.role.kind === "master";
  const warn = geoNeedsAttention(row);
  const color = warn ? MARKER_WARN : MARKER_BASE;
  return {
    radius: master ? 10 : 7,
    color,
    weight: master ? 3 : 2,
    fillColor: color,
    fillOpacity: master ? 0.15 : 0.9,
  };
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface AssetMapTabProps {
  client?: ApiClient;
}

export function AssetMapTab(props: AssetMapTabProps) {
  const { t } = useTranslation();
  const translate = useTranslator();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const [filters, setFilters] = useState<GeoFilters>(EMPTY_GEO_FILTERS);

  const geo = useQuery({
    queryKey: assetGeoQueryKey,
    // DEF-AST-5199 — ASK for a page, and ask for the biggest one the server
    // will give. Reading EVERY page here would be wrong: `geo_view`'s own
    // docstring says this bound exists "so the tab cannot hand a browser 21 MB",
    // and that a map of page 1 of 3 is a map of the wrong day. The real answer
    // is a VIEWPORT read (DEF-MET-4301, still open). Until then the map draws
    // what it has and SAYS how many there are, which is the half that was lying.
    queryFn: () => getAssetGeo({ per: ASSET_MAX_PER }, client),
    retry: false,
  });

  const rows = useMemo(() => geo.data?.assets ?? [], [geo.data]);
  // The set's size, NEVER the page's. `rows.length` is one page and captioning
  // it as the total is the whole of DEF-AST-5199.
  const totalPlaced = geo.data?.assets_window?.total ?? rows.length;
  const shown = useMemo(() => filterGeoAssets(rows, filters), [rows, filters]);
  const vocab = useMemo(() => mapVocab(rows), [rows]);

  // CR-069 wave M — the registered tile host, from the connection the policy
  // is generated from (`tile_host`, by name — DEF-INT-4287). `ground` keeps a
  // FAILED read apart from a basemap switched OFF (DEF-AST-5201). Both live in
  // the shared basemap module now (CR-168-BRC10 P3.3).
  const { tileHost, tileUrl, answered: policyAnswered, ground } = useBasemap(client);

  const canvasRef = useRef<HTMLDivElement | null>(null);
  const leafletRef = useRef<{
    map: Leaflet.Map;
    layer: Leaflet.LayerGroup;
    lib: typeof Leaflet;
    // CR-069 wave M — kept so the tile layer can be RE-POINTED when the host
    // arrives, and REMOVED when the utility switches the basemap off. See the
    // note on the effect below.
    tiles: Leaflet.TileLayer | null;
    tileUrl: string | null;
  } | null>(null);

  // The Leaflet half — DYNAMIC import inside the effect, so jsdom renders
  // never load it (renderToStaticMarkup runs no effects) and the bundle only
  // pays for it on this tab.
  useEffect(() => {
    let disposed = false;
    void import("leaflet").then((lib) => {
      if (disposed || canvasRef.current === null) {
        return;
      }
      if (leafletRef.current === null) {
        const map = lib
          .map(canvasRef.current, { scrollWheelZoom: true })
          .setView(DEFAULT_CENTER, DEFAULT_ZOOM);
        leafletRef.current = {
          map,
          layer: lib.layerGroup().addTo(map),
          lib,
          tiles: null,
          tileUrl: null,
        };
      }
      // ⚠ **THE HOST ARRIVES AFTER THE MAP DOES, AND WITHOUT THIS IT WOULD
      // NEVER REACH IT.** `getPagePolicy` is a request; the map is built on the
      // first render, when its answer is still in flight. A `tileUrl` computed
      // correctly and never applied is hard-won law 2 exactly — the value
      // exists, `tsc` is happy, and the tenant's own tile server is silently
      // never drawn from. It runs in BOTH directions now: a host that goes away
      // takes the layer with it, so *switched off* is a map with no basemap
      // rather than a map still calling a host the policy refuses.
      if (policyAnswered) {
        syncTileLayer(lib, leafletRef.current.map, leafletRef.current, tileUrl);
      }
      const { map, layer } = leafletRef.current;
      layer.clearLayers();
      for (const row of shown) {
        const marker = lib
          .circleMarker([Number(row.lat), Number(row.lng)], markerStyle(row))
          .addTo(layer);
        marker.bindPopup(buildPopupCard(row));
      }
      if (shown.length > 0) {
        map.fitBounds(lib.latLngBounds(shown.map((row) => [Number(row.lat), Number(row.lng)])), {
          maxZoom: 15,
          padding: [24, 24],
        });
      }
    });
    return () => {
      disposed = true;
    };
    // buildPopupCard is stable per render pass; the markers are rebuilt from
    // `shown`, and `tileUrl` is here because the registered host arrives after
    // the first render (CR-069 wave M).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shown, tileUrl, policyAnswered]);

  useEffect(
    () => () => {
      leafletRef.current?.map.remove();
      leafletRef.current = null;
    },
    [],
  );

  /** The popup card, as a real DOM node so "Open details →" is a wired
   *  handler (a string onclick would be dead UI — hard-won law 2). The uuid
   *  only ADDRESSES the navigation; the card shows asset_no (BR-AST-026).
   *  NO work-order line — §10-D7. */
  function buildPopupCard(row: AssetGeoRow): HTMLElement {
    const card = document.createElement("div");
    card.className = "min-w-[210px] text-sm";
    const title = document.createElement("div");
    title.className = "text-sm font-heading font-bold";
    title.textContent = row.asset_no;
    const roleText =
      row.role.kind === "sub"
        ? t("assets.role.sub", { parent: row.role.parent })
        : row.role.kind === "master"
          ? t("assets.role.master", { count: row.role.count })
          : `${row.type_name}`;
    const role = document.createElement("span");
    role.className = "ml-1 text-xs font-normal opacity-70";
    role.textContent = roleText;
    title.appendChild(role);
    card.appendChild(title);
    const premise = document.createElement("div");
    premise.className = "my-1";
    premise.textContent = [row.premises, row.unit].filter(Boolean).join(" · ");
    card.appendChild(premise);
    // ── CR-089 wave A `PUJ-49` · `BR-MET-1162` (PO 2026-09-08) ──────────────
    // ⚠ **SAID ONLY WHEN IT IS THE UNIT'S OWN, AND THAT ASYMMETRY IS THE
    // POINT.** Reading the building's point is the ORDINARY case — all 1,109
    // units do it today — so labelling every one of 121 pins *from the
    // building* would be noise on a map, which is B14 rule 32's budget. A pin
    // that is the unit's OWN is the exception the ruling exists for and the
    // one a person needs told: it is why this cabin's marker is 300 metres
    // from its site office instead of stacked on it.
    if (row.point_source === "unit") {
      const own = document.createElement("div");
      own.className = "text-xs opacity-75";
      own.textContent = t("metering.unit.point.own");
      card.appendChild(own);
    }
    const read = document.createElement("div");
    read.className = "text-xs opacity-75";
    read.textContent =
      row.last_read !== null && row.last_read.consumption !== null && row.last_read.unit !== null
        ? t("assets.map.lastRead", {
            read: `${row.last_read.consumption} ${row.last_read.unit}${
              row.last_read.read_at !== null ? ` · ${row.last_read.read_at}` : ""
            }`,
          })
        : t("assets.map.noRead");
    card.appendChild(read);
    const status = document.createElement("div");
    status.className = "my-1 text-xs";
    status.style.color = geoNeedsAttention(row) ? MARKER_WARN : "inherit";
    status.textContent = row.status_name;
    card.appendChild(status);
    const open = document.createElement("button");
    open.type = "button";
    open.className =
      // DEF-617: `text-white` generated NO RULE. tailwind.css clears
      // `--color-*` to `initial`, so this theme has no `white` — the ink
      // that reads on a dark fill is `--color-bg`, which is what
      // ScreenIdTag and Toast both use on `bg-text`. Until this was
      // fixed the label inherited #201e1d on #ff563c.
      "mt-1.5 w-full cursor-pointer border-0 bg-accent-500 p-1.5 font-heading text-xs font-bold text-bg";
    open.textContent = t("assets.map.openDetails");
    open.addEventListener("click", () => navigate(tenantPath(assetDetailPath(row.id))));
    card.appendChild(open);
    return card;
  }

  if (geo.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (geo.data === undefined) {
    return (
      <p role="alert" className="text-base">
        {apiErrorText(geo.error, translate)}
      </p>
    );
  }

  return (
    <>
      {/* ── r10's filter bar, above the map ─────────────────────────────── */}
      {/* ── `DEF-MET-4959` · why these four selects carry NO class ──────
          `DEF-MET-4959` — **THIS CLASS WAS SIX UTILITIES AND EVERY ONE OF THEM WAS
          INERT.** Measured in Chromium at 1440 on `pine-hill`, on the element itself:

          |            | declared here | rendered |
          |---|---|---|
          | `min-h-8`  | 32px  | **36px** |
          | `px-2 py-1`| 4/8px | **6px 30px 6px 10px** |
          | `text-sm`  | 12px  | **14px** |
          | appearance | (unset) | `none`, with the product's chevron |

          `.view select` in `FormModal.css` supplies all four, `.view` is on `<main>`
          (`AppShell.tsx`), and a descendant selector outranks a single-class utility
          — so the numbers this component asked for never applied. The RENDERED
          values are the right ones (36px is the product's control height), which
          makes the declarations a lie rather than a loss: they read as this
          component's decision, they were never anyone's, and the next lane to "tidy"
          them would change nothing and believe it had.

          So they are gone and NOT replaced with higher-specificity copies — winning
          would give the map four 32px controls in a product of 36px ones. Removing
          them changes not one pixel; proved by reading the computed styles of all
          four selects before and after.

          ⚠ **WHAT THIS DOES NOT FIX, STATED RATHER THAN LEFT IMPLIED.** The chevron
          and the height still come from an ancestor these controls never ask for, so
          renaming that wrapper restyles them silently. That is true of EVERY
          `<select>` in the product — `DataTable`'s page-size control and
          `ChipMultiSelect`'s adder included — so it is a kit-wide question and not
          this component's to answer inside an Assets pass.
      */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          className="min-h-8 w-[220px] border border-field-border bg-surface px-2.5 py-1 text-sm"
          placeholder={t("assets.map.searchPlaceholder")}
          aria-label={t("assets.map.searchPlaceholder")}
          value={filters.q}
          onChange={(event) => setFilters({ ...filters, q: event.target.value })}
        />
        <select
          aria-label={t("assets.map.typeLabel")}
          value={filters.type}
          onChange={(event) =>
            setFilters({ ...filters, type: event.target.value as GeoFilters["type"] })
          }
        >
          <option value="">{t("assets.map.type.all")}</option>
          <option value="meter">{t("assets.map.type.meter")}</option>
          <option value="master">{t("assets.map.type.masters")}</option>
          <option value="sub">{t("assets.map.type.subs")}</option>
          <option value="device">{t("assets.map.type.device")}</option>
        </select>
        <select
          aria-label={t("assets.map.statusLabel")}
          value={filters.status}
          onChange={(event) =>
            setFilters({ ...filters, status: event.target.value as GeoFilters["status"] })
          }
        >
          <option value="">{t("assets.map.status.all")}</option>
          <option value="active">{t("assets.map.status.active")}</option>
          <option value="attention">{t("assets.map.status.attention")}</option>
          <option value="pending">{t("assets.map.status.pending")}</option>
        </select>
        <select
          aria-label={t("assets.map.serviceLabel")}
          value={filters.service}
          onChange={(event) => setFilters({ ...filters, service: event.target.value })}
        >
          <option value="">{t("assets.map.service.all")}</option>
          {/* DEF-763 — `rating.service.*`, the namespace with all ELEVEN codes
              (`TEN` until `CR-063` appended Fire at position 11; corrected
              2026-09-12, `DEF-MET-4964`). The filter is built from the
              tenant's OWN vocabulary — which is why nothing renders wrongly
              here and the count in the comment was the whole defect: a utility
              selling Storm water had `storm_water` in this menu, and one
              selling Fire has `fire`, neither because this file lists them. */}
          {vocab.services.map((service) => (
            <option key={service} value={service}>
              {t(`rating.service.${service}`, { defaultValue: service })}
            </option>
          ))}
        </select>
        <select
          aria-label={t("assets.map.areaLabel")}
          value={filters.area}
          onChange={(event) => setFilters({ ...filters, area: event.target.value })}
        >
          <option value="">{t("assets.map.area.all")}</option>
          {vocab.areas.map((area) => (
            <option key={area} value={area}>
              {area}
            </option>
          ))}
        </select>
        <span className="ml-auto text-sm opacity-70" role="status">
          {t("assets.map.showing", { shown: shown.length, total: totalPlaced })}
        </span>
      </div>

      {/* The canvas. Leaflet mounts here in the effect; with no geocoded
          premises the tab says so instead of drawing an empty world. */}
      {rows.length === 0 ? (
        <div className="border border-divider bg-surface p-8 text-center">
          <p className="m-0 font-heading text-h5">{t("assets.map.empty.title")}</p>
          <p className="mx-auto mt-2 max-w-[48ch] text-base opacity-75">
            {t("assets.map.empty.helper")}
          </p>
        </div>
      ) : (
        <div
          ref={canvasRef}
          data-map-canvas=""
          data-tile-host={tileHost ?? ""}
          className="h-[520px] border border-divider"
          role="application"
          aria-label={t("assets.map.canvasLabel")}
        />
      )}
      {/* ⚠ **A MAP WITH NO BACKGROUND MUST SAY WHY (`DEF-INT-4287`).** A tenant
          who switched the map service off and a product whose tiles are being
          refused draw the identical grey square, and that is exactly the shape
          hard-won law 7 warns about. B14 rule 32 — one short sentence, and only
          in the state it describes. */}
      {rows.length > 0 && ground.kind === "off" && (
        <p className="mt-2 text-sm opacity-75" data-no-tile-host="">
          {t("assets.map.noTileHost")}
        </p>
      )}
      {rows.length > 0 && ground.kind === "unavailable" && (
        <p className="mt-2 text-sm opacity-75" data-tile-policy-failed="">
          {t("assets.map.tilePolicyFailed")}
        </p>
      )}

      {/* ── The three-state legend (r10's own) ──────────────────────────── */}
      <div className="mt-2 flex flex-wrap gap-4 text-xs opacity-85">
        <span className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ background: MARKER_BASE }}
          />
          {t("assets.map.legend.healthy")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ background: MARKER_WARN }}
          />
          {t("assets.map.legend.attention")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className="inline-block h-2.5 w-2.5 rounded-full border-2"
            style={{ borderColor: MARKER_WARN }}
          />
          {t("assets.map.legend.master")}
        </span>
      </div>
      {rows.length > 0 && shown.length === 0 && (
        <p className="mt-2 text-base">
          {t("assets.map.noneMatch")} <AssetDash />
        </p>
      )}
    </>
  );
}

export default AssetMapTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-028/B16@2026-08-22 §4.6 + §10-D6/D7 (AST-W5 T3)
// generated: 2026-08-22 by the CR-028 AST-W5 lane · AMENDED 2026-09-06 by the CR-075 map lane (DEF-INT-4287 — the host comes from `tile_host` and this module keeps none of its own)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint --max-warnings 0✔ vitest (AssetNewTabs.test.tsx — the pure filter/marker law + the rendered bar/legend; Leaflet never loads under jsdom because renderToStaticMarkup runs no effects · AssetMapTiles.test.tsx — the tile-host contract, which had NO test of any kind until DEF-INT-4287) · i18n ×11 · 10-scripts/def_map_walkthrough.mjs counts the tiles that LOADED, which is the only check that can see this defect
// exceptions: E3 tiles come from Esri's public server with attribution "Tiles © Esri" — EVERY PAN sends the viewport (and so the neighbourhood of tenant asset locations) to a third party; that egress is exactly what §10-D6 ACCEPTED and it is stated here rather than discovered later · ⚠ the attribution string is Esri's and is NOT re-derived when a utility points the map at its OWN tile server (`R-7`), so that utility reads a credit for a service it is not using — small, real, and filed as `DEF-INT-4294` rather than left as a comment (hard-won law 1) · E4 marker colors are canvas literals (r10's #201e1d/#ec3013): Leaflet paints outside the themed DOM, so tokens cannot reach them · E3 the popup's r10 `WO-####` line is OMITTED (§10-D7 — Work is R5; a fake WO number would be worse than its absence)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
