// ── Trace ──────────────────────────────────────────────
// CR:       CR-197-BRC10 — the ONE GL mapping list. Typed wrappers over
//           `06-backend/apps/ledger/gl_mapping_api.py`.
// Rules:    NFR-3 (paged, searched and filtered by the server) · B14 rule 31
//           (`key` and `account.id` are ADDRESSES, never drawn)
// Tests:    src/features/ledger/glMappingList.dom.test.tsx
// ───────────────────────────────────────────────────────
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export const GL_MAPPING_GROUPS = ["billing", "payments"] as const;
export type GlMappingGroup = (typeof GL_MAPPING_GROUPS)[number];

/** The eleven types, in the order the list and the Add form read them. */
export const GL_MAPPING_TYPES = [
  "service_revenue",
  "charge_code",
  "discount",
  "tax",
  "adjustment",
  "bill_payment",
  "deposit",
  "refund",
  "write_off",
  "other_payments",
  "system_account",
] as const;
export type GlMappingType = (typeof GL_MAPPING_TYPES)[number];

export const GL_MAPPING_GROUP_OF: Record<GlMappingType, GlMappingGroup> = {
  service_revenue: "billing",
  charge_code: "billing",
  discount: "billing",
  tax: "billing",
  adjustment: "billing",
  bill_payment: "payments",
  deposit: "payments",
  refund: "payments",
  write_off: "payments",
  other_payments: "payments",
  system_account: "payments",
};

export const GL_MAPPING_STATUSES = ["mapped", "not_mapped", "disabled"] as const;
export type GlMappingStatus = (typeof GL_MAPPING_STATUSES)[number];

export interface GlMappingAccount {
  /** An address for the picker — never drawn. */
  id: string;
  code: string;
  name: string;
}

export interface GlMappingRow {
  /** Opaque row address (`chg:<id>`, `svc:solar:usage:*` …) — never drawn. */
  key: string;
  group: GlMappingGroup;
  type: GlMappingType;
  mapped_for: string;
  mapped_for_key: string | null;
  detail: string | null;
  detail_key: string | null;
  detail_params: Record<string, string | null>;
  account: GlMappingAccount | null;
  status: GlMappingStatus;
  can_disable: boolean;
  can_enable: boolean;
  kinds: string[];
}

export interface GlMappingPage {
  count: number;
  page: number;
  per: number;
  results: GlMappingRow[];
  counts: { total: number; not_mapped: number; disabled: number };
  gl_accounts: GlMappingAccount[];
}

export interface GlMappingListQuery {
  q?: string;
  type?: string;
  status?: string;
  gl_account?: string;
  page?: number;
  per?: number;
}

export interface GlMappingAccountOption extends GlMappingAccount {
  type: string;
}

export interface GlMappingAddOptions {
  types: { type: GlMappingType; group: GlMappingGroup; open: number }[];
  items?: GlMappingRow[];
  accounts?: GlMappingAccountOption[];
}

export interface GlMappingEditOptions {
  row: GlMappingRow;
  accounts: GlMappingAccountOption[];
}

const BASE = "/ledger/gl-mappings/rows";

export const glMappingKeys = {
  all: ["ledger", "gl-mapping-rows"] as const,
  list: (query: GlMappingListQuery) => ["ledger", "gl-mapping-rows", "list", query] as const,
  add: (type: string) => ["ledger", "gl-mapping-rows", "add", type] as const,
  edit: (key: string) => ["ledger", "gl-mapping-rows", "edit", key] as const,
};

function blankToUndefined(value: string | undefined): string | undefined {
  return value === undefined || value.trim() === "" ? undefined : value.trim();
}

export async function listGlMappings(
  query: GlMappingListQuery,
  client: ApiClient = api,
): Promise<GlMappingPage> {
  return requireData(
    await client.get<GlMappingPage>(BASE, {
      query: {
        q: blankToUndefined(query.q),
        "f.type": blankToUndefined(query.type),
        "f.status": blankToUndefined(query.status),
        "f.gl_account": blankToUndefined(query.gl_account),
        page: query.page,
        per: query.per,
      },
    }),
  );
}

export async function glMappingAddOptions(
  type: string,
  client: ApiClient = api,
): Promise<GlMappingAddOptions> {
  return requireData(
    await client.get<GlMappingAddOptions>(`${BASE}/add-options`, {
      query: { type: blankToUndefined(type) },
    }),
  );
}

export async function glMappingEditOptions(
  key: string,
  client: ApiClient = api,
): Promise<GlMappingEditOptions> {
  return requireData(await client.get<GlMappingEditOptions>(`${BASE}/edit-options`, { query: { key } }));
}

export async function saveGlMapping(
  body: { act: "add" | "edit"; key: string; account_id: string },
  client: ApiClient = api,
): Promise<GlMappingRow> {
  return requireData(await client.post<GlMappingRow>(BASE, body));
}

export async function setGlMappingEnabled(
  key: string,
  enabled: boolean,
  client: ApiClient = api,
): Promise<unknown> {
  return requireData(await client.post<unknown>(`${BASE}/${enabled ? "enable" : "disable"}`, { key }));
}
