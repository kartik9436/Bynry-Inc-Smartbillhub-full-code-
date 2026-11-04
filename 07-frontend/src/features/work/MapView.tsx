// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-029 (the map — pins coloured by status and priority, hollow
//           when unassigned, click through to the job card)
//           Screens: a sub-screen of Work-007 (r10 `WRK-09`, undrawn in the
//           blueprint — `WM-23`)
// Rules:    BR-WRK-023 (pin colour reads the dispatch state; hollow means
//           unassigned) · BR-WRK-002 (coordinates come through the seam) ·
//           BR-WRK-026 (the same six filters, and a seventh is refused) ·
//           CLAUDE.md hard rule 8 (an address — and a coordinate — is the
//           PREMISES' and is derived by walking to it) · B14 rule 21
//           (Tailwind; on route-b-migrated.txt) · rule 31 (no database id is a
//           visible value) · rule 32 (one sentence per section)
// Tests:    src/features/work/MapView.test.tsx
// Impacts:  src/features/work/workEndpoints.ts · src/App.tsx (one route) ·
//           src/features/work/WorkShell.tsx (the Map tab) ·
//           src/routing/screenIds.ts (WRK-09)
// ───────────────────────────────────────────────────────
//
// ⚠⚠ **THE STRIP UNDER THE MAP IS THE PART THAT MATTERS, AND IT IS THE PART A
// MAP SCREEN NORMALLY LEAVES OUT.**
//
// A dispatcher looks at a map to see the day. If an order with no coordinate is
// silently dropped, the map is quietly LYING about the day — and unlike a list,
// **you cannot count pins**, so nothing on screen would ever reveal it. So the
// answer carries two lists and this screen draws both: the pins, and *not on
// the map* with its reason (`US-WRK-029` TC-3).
//
// The two reasons differ and are told apart on purpose:
//   * `premises_not_geocoded` — the address exists and nobody has placed it. A
//     dispatcher can fix this.
//   * `no_premises` — a network job at *Elm St & 3rd*. Nobody can fix it and
//     nobody should try; it is simply not a place.
//
// ⚠ **NO TILE HOST IS NAMED IN THIS FILE** (`US-WRK-029` TC-4). The basemap is
// the substrate's declared operation (`map_tiles_public`, `CR-069`), the same
// one `features/assets/AssetMapTab.tsx` already uses. A hardcoded host here
// would be a second answer to *where do tiles come from*, and the first thing
// that breaks when a utility runs offline.
//
// ⚠ **THE STREET GROUND (`CR-168-BRC10` P3.3, PO 2026-10-04 — decision log
// *"THE WORK MAP SHOWS AN ESRI STREET MAP"*; `OQ-WRK-12787` CLOSED;
// `DEF-WRK-9561`).** The tiles are the Assets map's, through the ONE module both
// maps import (`features/integrations/basemap.ts`): the tenant's `tile_host`
// from `GET /integrations/page-policy`, Esri's World Street Map path, *Tiles ©
// Esri*. Swapping the provider — a paid key, the utility's own tile server —
// changes that connection and never this screen.
//
// **THE PINS ARE STILL THIS SCREEN'S OWN BUTTONS**, laid over the map rather
// than handed to it as Leaflet markers, so a pin stays a real `<button>` a
// keyboard reaches and the strip below stays plain DOM. Leaflet only PROJECTS:
// once it is up it says where each coordinate is on screen, and every pin is
// placed by that one projection — the tiles' own — so a pin sits on its street.
// A tile that fails to load (host blocked, offline) costs that square of ground
// and nothing else: the projection does not need the tiles to arrive.
//
// ⚠ **NOTHING IS PAGED.** A map of page 1 of 3 is a map of the wrong day.
//
// ⚠ **JOBS AT ONE PLACE ARE ONE MARK WITH A COUNT (`CR-168-BRC10` P3.1,
// `DEF-WRK-9598`).** A coordinate is the PREMISES' (hard rule 8), so every job
// at one building lands on the same point — the demo day is 17 orders on 5
// spots. One button per job put twelve of them exactly UNDER another button:
// present in the DOM, so a count of buttons said 17, and unreachable, because
// only the top one takes a click. Now a place with more than one job draws ONE
// button carrying the count; pressing it lists the jobs beside the map
// (*N jobs at this place*, the blueprint's remedy 3), and each row opens its
// order. Mouse and keyboard reach the same orders by the same buttons.
// A cluster is HOLLOW when any job in it is unassigned: folding five jobs into
// one solid mark must not hide the one nobody is going to.
//
// ⚠ **THE KEY (`DEF-WRK-9599`, blueprint convention R10).** Hollow and solid
// encode a fact, and B14 rule 32 says a screen says what a control means. The
// key uses the list's OWN word for the hollow case (*Unassigned*, the same
// flag the list's pill reads) and its plain opposite for the solid one. The
// blueprint's draft key read *Scheduled or en route* for solid, which is false
// for an assigned job on hold or on site — rule 33 caps a fact AND requires it
// to be true.
import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import type * as Leaflet from "leaflet";
import "leaflet/dist/leaflet.css";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { StatusPill } from "@/components/StatusPill";
import { syncTileLayer, useBasemap } from "@/features/integrations/basemap";
import type { TileSlot } from "@/features/integrations/basemap";

import { dispatchStateTone } from "./OrdersPage";

import { getWorkOrderMap } from "./workEndpoints";
import type { MapPin, UnplacedOrder, WorkOrderDispatchState } from "./workEndpoints";

/** Where a pin sits inside the box, as a percentage of the plotted extent —
 * ONLY while there is no map to ask.
 *
 * ⚠ **THIS IS A PLACEMENT, NOT A PROJECTION, AND IT NEVER SHARES THE SCREEN
 * WITH ONE.** This note used to say that when the basemap arrived this function
 * would be DELETED rather than reconciled with the tile library's. The basemap
 * arrived on 2026-10-04 (`CR-168-BRC10` P3.3) and the half of that which
 * mattered holds: the two are never reconciled, because the moment Leaflet is
 * up it places EVERY pin and this is not consulted. It is kept for the one case
 * where there is no map at all — the map library's code failed to load — so the
 * pins and the strip still work then, which is P3.3's own condition.
 */
export function placeOf(
  pin: { lat: number; lng: number },
  bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number },
): { left: string; top: string } {
  const spanLat = bounds.maxLat - bounds.minLat || 1;
  const spanLng = bounds.maxLng - bounds.minLng || 1;
  // Inset to 10–90% so a pin on the edge of the extent is not half outside the
  // box, which reads as a bug rather than as a job at the edge of town.
  const x = 10 + ((pin.lng - bounds.minLng) / spanLng) * 80;
  const y = 10 + ((bounds.maxLat - pin.lat) / spanLat) * 80;
  return { left: `${x}%`, top: `${y}%` };
}

/** The jobs that share one point, in the server's order (priority, then
 *  number). Grouped on the coordinate to six places — about 0.1 m — because
 *  the point is the premises' and identical for every job there. */
export interface PlaceGroup {
  key: string;
  pins: MapPin[];
  hollow: boolean;
}

export function groupByPlace(pins: MapPin[]): PlaceGroup[] {
  const byKey = new Map<string, PlaceGroup>();
  for (const pin of pins) {
    const key = `${pin.lat.toFixed(6)},${pin.lng.toFixed(6)}`;
    const group = byKey.get(key);
    if (group === undefined) byKey.set(key, { key, pins: [pin], hollow: pin.hollow });
    else {
      group.pins.push(pin);
      group.hollow = group.hollow || pin.hollow;
    }
  }
  return Array.from(byKey.values());
}

export function boundsOf(pins: MapPin[]) {
  return {
    minLat: Math.min(...pins.map((pin) => pin.lat)),
    maxLat: Math.max(...pins.map((pin) => pin.lat)),
    minLng: Math.min(...pins.map((pin) => pin.lng)),
    maxLng: Math.max(...pins.map((pin) => pin.lng)),
  };
}

interface MapViewProps {
  /** The search box's text and the five chips, exactly as the LIST holds them.
   *  Passed in rather than read again here, so switching to Map keeps the
   *  narrowing a dispatcher already made (`US-WRK-029` TC-6). */
  q?: string;
  filters?: Record<string, string>;
  /** What a pin's card opens. Passed in because the ADDRESS of the job card is
   *  the router's business and not this component's — a path built here would
   *  be the second place that address is spelled.
   *
   *  ⚠ **REQUIRED, NOT OPTIONAL, AND THAT IS HARD-WON LAW 2 IN ONE PROP.** A
   *  map whose pins are decorative is dead UI: it renders, every test passes,
   *  and clicking a pin does nothing. `G13` exists because four such defects
   *  shipped in one day. Making this required means a caller that forgets it
   *  does not compile. */
  onOpen: (pin: MapPin | UnplacedOrder) => void;
  /** The API client; the page passes none and gets the app's own. */
  client?: ApiClient;
}

/** Leaflet decides the first view by fitting the pins, so this is only the
 *  closest a single-pin day zooms in. The Assets map uses the same 15. */
const MAX_FIT_ZOOM = 15;

type ScreenPoint = { left: string; top: string };

// ⚠ **TWO CLASSES ON THIS SCREEN NAMED COLOUR TOKENS THAT DO NOT EXIST, AND
// THEREFORE PAINTED NOTHING (`DEF-WRK-4053`, fixed 2026-09-05).**
//
// The map canvas asked for a neutral ground at step FIFTY and the neutral ramp
// starts at ONE HUNDRED; the unassigned pin asked for the danger colour with no
// step at all, and the danger ramp has only 100, 500 and 700. Tailwind emits no
// rule for either name, so the 420px map surface had no ground and the hollow
// pin — the one thing this screen exists to make findable, *a job nobody is
// going to* — was outlined in the inherited text colour rather than in red.
//
// ⚠ **WHY IT WAS EASY TO WRITE AND IMPOSSIBLE TO SEE.** The line immediately
// below the pin's asks for the ACCENT colour with no step and compiles, because
// the accent ramp does declare a bare token and the danger ramp does not. Two
// adjacent lines, one real and one inert, spelled the same way. And a class that
// compiles to nothing is still IN THE DOM, so `tsc`, eslint and every
// `toContain(...)` assertion pass over it — B14 rule 21's standing trap, and
// hard-won law 6 (no gate in this repo reads rendered output) is why it survived
// a wave. What DID catch it is `src/styles/routeBUtilities.test.ts`, which asks
// Tailwind whether each harvested token compiles; it was already red and naming
// both when this lane arrived.
//
// ⚠ **AND THE FIRST FIX RE-BROKE THE CHECK FROM THE COMMENT.** That harvester
// reads quoted literals inside class-attribute expressions, so a comment sitting
// in one that SPELLS the broken class re-reports it — three orphans where there
// had been two, the extra ones coming from the prose. `buttonKit.ts` records the
// same trap costing three commits. Hence this note lives here, above the JSX,
// and describes the two names rather than writing them.
export function MapView({ q = "", filters = {}, onOpen, client = api }: MapViewProps) {
  const { t } = useTranslation();
  const map = useQuery({
    queryKey: queryKeys.workOrderMap(q, filters),
    queryFn: () => getWorkOrderMap({ ...filters, q }, client),
  });
  const basemap = useBasemap(client);

  const pins = map.data?.pins ?? [];
  const unplaced = map.data?.unplaced ?? [];
  const bounds = pins.length > 0 ? boundsOf(pins) : null;
  const groups = groupByPlace(pins);
  // The place whose jobs are listed beside the map; `null` while none is.
  const [openPlace, setOpenPlace] = useState<string | null>(null);
  const openGroup = groups.find((group) => group.key === openPlace) ?? null;
  const panelHeadingId = useId();
  const firstJobRef = useRef<HTMLButtonElement | null>(null);

  // ── The Leaflet half — loaded on demand, as the Assets map does ──────────
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const leafletRef = useRef<{ map: Leaflet.Map; slot: TileSlot } | null>(null);
  const pinsRef = useRef<MapPin[]>(pins);
  pinsRef.current = pins;
  // Each pin's place on screen as the MAP projects it; `null` until it can.
  const [projected, setProjected] = useState<Record<string, ScreenPoint> | null>(null);
  // Re-run the effect when the DAY changes, not on every new array identity.
  const dayKey = pins.map((pin) => `${pin.id}:${pin.lat}:${pin.lng}`).join("|");

  useEffect(() => {
    if (pins.length === 0) {
      leafletRef.current?.map.remove();
      leafletRef.current = null;
      setProjected(null);
      return undefined;
    }
    let disposed = false;
    void import("leaflet")
      .then((lib) => {
        if (disposed || canvasRef.current === null) return;
        if (leafletRef.current === null) {
          // Zoom animation is off because the pins are DOM over the map, not
          // inside its panes: an animated zoom would scale the tiles under
          // pins that only move when it ends.
          const created = lib.map(canvasRef.current, {
            scrollWheelZoom: true,
            zoomAnimation: false,
          });
          const project = () => {
            const next: Record<string, ScreenPoint> = {};
            for (const pin of pinsRef.current) {
              const point = created.latLngToContainerPoint([pin.lat, pin.lng]);
              next[pin.id] = { left: `${point.x}px`, top: `${point.y}px` };
            }
            setProjected(next);
          };
          created.on("move zoom resize viewreset", project);
          leafletRef.current = { map: created, slot: { tiles: null, tileUrl: null } };
        }
        const current = leafletRef.current;
        // The fit comes first: Leaflet cannot project before it has a view.
        current.map.fitBounds(
          lib.latLngBounds(pinsRef.current.map((pin) => [pin.lat, pin.lng] as [number, number])),
          { maxZoom: MAX_FIT_ZOOM, padding: [24, 24] },
        );
        if (basemap.answered) syncTileLayer(lib, current.map, current.slot, basemap.tileUrl);
        const next: Record<string, ScreenPoint> = {};
        for (const pin of pinsRef.current) {
          const point = current.map.latLngToContainerPoint([pin.lat, pin.lng]);
          next[pin.id] = { left: `${point.x}px`, top: `${point.y}px` };
        }
        setProjected(next);
      })
      // The library's code failed to arrive: no map, and `placeOf` keeps the
      // pins and the strip working on the plain ground.
      .catch(() => undefined);
    return () => {
      disposed = true;
    };
    // `pins` is read through `pinsRef`; `dayKey` is its identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dayKey, basemap.answered, basemap.tileUrl]);

  // Opening the list narrows the map; Leaflet must re-measure its box (it then
  // fires `resize`, which re-projects every mark). Focus moves to the first
  // job, so a keyboard user's next Enter opens an order.
  const panelOpen = openGroup !== null;
  useEffect(() => {
    leafletRef.current?.map.invalidateSize();
  }, [panelOpen]);
  useEffect(() => {
    if (openPlace !== null) firstJobRef.current?.focus();
  }, [openPlace]);

  useEffect(
    () => () => {
      leafletRef.current?.map.remove();
      leafletRef.current = null;
    },
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start gap-4">
        <div
          className="relative h-[420px] min-w-0 flex-1 border border-divider bg-neutral-100"
          data-map="work-orders"
        >
          {bounds === null ? (
            <p className="p-4 text-base text-neutral-600">{t("work.map.empty")}</p>
          ) : (
            <>
              {/* The street ground. `isolate` keeps Leaflet's pane z-indexes
                  inside this box, so the marks drawn after it stay on top. */}
              <div
                ref={canvasRef}
                className="absolute inset-0 isolate"
                data-map-canvas=""
                data-tile-host={basemap.tileHost ?? ""}
              />
              <div className="pointer-events-none absolute inset-0 overflow-hidden">
                {groups.map((group) => {
                  const first = group.pins[0];
                  const place = projected?.[first.id] ?? placeOf(first, bounds);
                  if (group.pins.length === 1) {
                    return (
                      <button
                        key={group.key}
                        type="button"
                        onClick={() => onOpen(first)}
                        style={{ left: place.left, top: place.top }}
                        // ⚠ `hollow` is its OWN fact — a job nobody is going to —
                        // and it is drawn as an outline rather than as a colour,
                        // because the colour is already carrying the dispatch
                        // state. Two facts, two channels.
                        className={
                          first.hollow
                            ? "pointer-events-auto absolute h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-danger-500 bg-[transparent]"
                            : "pointer-events-auto absolute h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-accent bg-accent"
                        }
                        data-pin={first.order_no ?? first.id}
                        data-hollow={first.hollow ? "true" : "false"}
                        data-state={first.dispatch_state}
                        aria-label={t("work.map.pinLabel", {
                          order: first.order_no ?? "",
                          address: first.address ?? "",
                        })}
                      />
                    );
                  }
                  return (
                    <button
                      key={group.key}
                      type="button"
                      onClick={() => setOpenPlace(group.key)}
                      style={{ left: place.left, top: place.top }}
                      className={
                        group.hollow
                          ? "pointer-events-auto absolute flex h-7 w-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-danger-500 bg-bg text-xs font-extrabold text-danger-500"
                          : "pointer-events-auto absolute flex h-7 w-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-accent bg-accent text-xs font-extrabold text-bg"
                      }
                      data-cluster={group.key}
                      data-hollow={group.hollow ? "true" : "false"}
                      aria-expanded={openPlace === group.key}
                      aria-label={t("work.map.cluster.label", {
                        count: group.pins.length,
                        address: first.address ?? "",
                      })}
                    >
                      {group.pins.length}
                    </button>
                  );
                })}
              </div>
              {/* ── The key — what a hollow and a solid mark mean ───────── */}
              <div
                className="absolute bottom-3 left-3 flex flex-col gap-1 border border-divider bg-bg px-3 py-2 text-xs"
                data-map-key=""
              >
                <span className="font-bold">{t("work.map.key.title")}</span>
                <span className="flex items-center gap-2" data-key-entry="hollow">
                  <span
                    aria-hidden="true"
                    className="h-3 w-3 rounded-full border-2 border-danger-500"
                  />
                  {t("work.unassigned")}
                </span>
                <span className="flex items-center gap-2" data-key-entry="solid">
                  <span
                    aria-hidden="true"
                    className="h-3 w-3 rounded-full border-2 border-accent bg-accent"
                  />
                  {t("work.map.key.solid")}
                </span>
              </div>
            </>
          )}
        </div>

        {/* ── The jobs at one place, each a door to its order ─────────── */}
        {openGroup !== null ? (
          <section
            aria-labelledby={panelHeadingId}
            className="flex w-72 shrink-0 flex-col border border-divider p-3"
            data-cluster-panel={openGroup.key}
          >
            <h2
              id={panelHeadingId}
              className="text-xs font-bold uppercase tracking-wide text-neutral-700"
            >
              {t("work.map.cluster.title", { count: openGroup.pins.length })}
            </h2>
            <ul className="flex flex-col">
              {openGroup.pins.map((pin, index) => (
                <li key={pin.id} className="border-b border-divider">
                  <button
                    ref={index === 0 ? firstJobRef : undefined}
                    type="button"
                    className="flex w-full items-baseline gap-2 py-2 text-left text-sm"
                    onClick={() => onOpen(pin)}
                    data-cluster-job={pin.order_no ?? pin.id}
                  >
                    <span className="font-bold tabular-nums">{pin.order_no}</span>
                    <span className="text-neutral-700">
                      {t(`work.orders.dispatch.${pin.dispatch_state}`)}
                      {pin.hollow ? ` · ${t("work.unassigned")}` : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>

      {/* ── NOT ON THE MAP — never silently dropped ──────────────────── */}
      {unplaced.length > 0 ? (
        <section className="flex flex-col gap-2" data-strip="not-on-the-map">
          <h2 className="text-sm font-bold uppercase tracking-wide">
            {t("work.map.unplaced.title", { count: unplaced.length })}
          </h2>
          {/* B14 rule 32 — ONE sentence for the section. It says what the strip
              is, not why each row is in it; each row says that for itself. */}
          <p className="text-sm text-neutral-600">{t("work.map.unplaced.help")}</p>
          <ul className="flex flex-col gap-1">
            {unplaced.map((order) => (
              <li
                key={order.id}
                className="flex items-center gap-2 border border-divider px-3 py-2 text-base"
                data-unplaced={order.order_no ?? order.id}
              >
                <button
                  type="button"
                  className="font-medium underline"
                  onClick={() => onOpen(order)}
                >
                  {order.order_no}
                </button>
                <span>{order.type}</span>
                {order.priority ? (
                  <StatusPill tone={order.priority.colour}>{order.priority.name}</StatusPill>
                ) : null}
                <StatusPill
                  tone={dispatchStateTone(order.dispatch_state as WorkOrderDispatchState)}
                >
                  {t(`work.orders.dispatch.${order.dispatch_state}`)}
                </StatusPill>
                <span className="text-neutral-600">
                  {order.address ?? t(`work.map.reason.${order.reason}`)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
