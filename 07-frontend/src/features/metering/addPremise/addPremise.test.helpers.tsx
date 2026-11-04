// ── Trace ──────────────────────────────────────────────
// Change:   CR-177-BRC10 round C — one way to mount Add a premise in a test,
//           over a fake server that answers by PATH and records what was
//           posted. Shared by the page's tests and the neighbours that used to
//           mount the old wizard (route picker states, areas, services).
// ───────────────────────────────────────────────────────
// ⚠ **NO REAL CITY AND NO REAL SERVER.** Every answer here is written in the
// test; `check-address` answers whatever `world.check` says.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { createApiClient } from "@/api/client";
import type {
  CityCheckAnswer,
  CustomFieldRegistryEntry,
  LookupEntry,
  OwnerSearchRow,
  PremisesType,
  RouteRow,
  SameAddressPremise,
  TenantServiceRow,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { areaLookupQueryKey } from "../meteringShared";
import { routesQueryKey } from "../RoutesCyclesPage";
import { AddPremisePage } from "./AddPremisePage";

export const TEST_TENANT = "ottumwa-water-works";

export const TYPES: PremisesType[] = [
  { id: "t1", code: "single_family", name: "Single-family home", active: true, is_system: true },
  { id: "t2", code: "retired_kind", name: "Retired kind", active: false, is_system: false },
] as PremisesType[];

export function service(code: string, name: string, enabled = true): TenantServiceRow {
  return { service: code, name, enabled } as TenantServiceRow;
}

export const SERVICES: TenantServiceRow[] = [
  service("water", "Water"),
  service("sewer", "Sewer"),
  service("trash", "Trash"),
  service("electric", "Electric", false),
];

export function route(over: Partial<RouteRow> = {}): RouteRow {
  return {
    id: "r-12",
    code: "R-012",
    name: "North Silver Creek",
    route_type: "drive",
    feeder_ref: null,
    assigned_to: null,
    cycle_id: "c-3",
    cycle_code: "CYC-03",
    status: "active",
    members: 41,
    meters: 41,
    collected: null,
    ...over,
  } as RouteRow;
}

export const AREAS: LookupEntry[] = [
  { id: "a1", code: "NORTH", name: "North district", active: true, is_system: false, used_by: 0, parent_code: null, is_sub_area: false },
  { id: "a2", code: "NORTH-1", name: "North hills", active: true, is_system: false, used_by: 0, parent_code: "NORTH", is_sub_area: true },
];

export function owner(over: Partial<OwnerSearchRow> = {}): OwnerSearchRow {
  return {
    id: "acct-uuid-31",
    account_no: "AC-2026-00031",
    name: "Bramble Property Group",
    account_type: "commercial",
    account_type_name: "Commercial",
    party_kind: "company",
    managed_by: "Northside Management",
    status: "active",
    status_name: "Active",
    ...over,
  };
}

export interface World {
  services?: TenantServiceRow[];
  routes?: RouteRow[] | "reject" | "hang";
  customFields?: CustomFieldRegistryEntry[];
  check?: CityCheckAnswer;
  same?: SameAddressPremise | null;
  owners?: OwnerSearchRow[];
  /** What `POST /premises` answers: the created row, or a refusal envelope. */
  create?: { status: number; body: unknown };
}

export interface Sent {
  method: string;
  path: string;
  body: unknown;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

/** Mount the page under its REAL route pattern, so tenant paths are real. */
export function mountAddPremise(world: World = {}) {
  const sent: Sent[] = [];
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  qc.setQueryData(queryKeys.tenantServices, world.services ?? SERVICES);
  qc.setQueryData(["premises", "types"], TYPES);
  qc.setQueryData(areaLookupQueryKey, { count: AREAS.length, next: null, previous: null, results: AREAS });
  if (world.routes === undefined || Array.isArray(world.routes)) {
    qc.setQueryData(routesQueryKey, world.routes ?? [route()]);
  }
  qc.setQueryData(queryKeys.customFieldRegistry("premises", "S16", "input"), world.customFields ?? []);
  qc.setQueryData(queryKeys.customFieldRegistry("units", "S16", "input"), []);
  qc.setQueryData(queryKeys.customFieldRegistry("service_points", "S16", "input"), []);

  const client = createApiClient({
    tenant: TEST_TENANT,
    sleep: async () => undefined,
    maxAttempts: 1,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://localhost");
      const path = url.pathname.replace(`/api/${TEST_TENANT}`, "");
      const method = (init?.method ?? "GET").toUpperCase();
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      sent.push({ method, path: `${path}${url.search}`, body });
      if (path.startsWith("/routes")) {
        if (world.routes === "hang") return new Promise<Response>(() => undefined);
        return json({ detail: "boom" }, 500);
      }
      if (path === "/premises/number-preview") return json({ series_missing: false, number: "P-00086" });
      if (path === "/premises/same-address") return json({ same: world.same ?? null });
      if (path === "/premises/owner-search") {
        const q = (url.searchParams.get("q") ?? "").toLowerCase();
        const rows = (world.owners ?? []).filter(
          (row) => (row.name ?? "").toLowerCase().includes(q) || (row.account_no ?? "").toLowerCase().includes(q),
        );
        return json({ count: rows.length, next: null, previous: null, results: rows });
      }
      if (path.endsWith("/check-address")) {
        return json(world.check ?? { result: "not_connected", match: null, session: null, message_key: "integrations.gis.not_connected" });
      }
      if (method === "POST" && (path === "/premises" || path.endsWith("/gis_esri/premises"))) {
        const answer = world.create ?? { status: 201, body: { id: "new-1", premise_no: "P-00086", address_line: "x", units: [], warnings: [] } };
        return json(answer.body, answer.status);
      }
      return json([]);
    },
  });

  const view = render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/new`]}>
          <Routes>
            <Route path="/:tenant/premises/new" element={<AddPremisePage client={client} />} />
            <Route path="/:tenant/premises/:premisesId" element={<p data-testid="premise-page">opened</p>} />
            <Route path="/:tenant/premises" element={<p data-testid="premises-list">list</p>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...view, sent, qc };
}

/** The last POST that created a premise, by either door. */
export function createdBody(sent: readonly Sent[]): Record<string, unknown> | undefined {
  const posts = sent.filter((one) => one.method === "POST" && (one.path === "/premises" || one.path.endsWith("/gis_esri/premises")));
  return posts.at(-1)?.body as Record<string, unknown> | undefined;
}
