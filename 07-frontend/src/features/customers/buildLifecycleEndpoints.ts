// ── Trace ──────────────────────────────────────────────
// Change:   CR-162-BRC10 — the New Connection lifecycle: Approve / Activate,
//           the To-do tab with notes, Add unit.
// Server:   06-backend/apps/metering/connection_activation.py ·
//           apps/metering/connections.py (todo_list, reopen_outstanding,
//           update_note, add_unit_to_build) · apps/metering/api.py routes.
// ───────────────────────────────────────────────────────
// ⚠ **A FILE OF ITS OWN, NOT MORE LINES IN `newConnectEndpoints.ts`.** That
// file is the wizard's and the Charges/Messages lanes' too; these doors are the
// lifecycle's and nothing else calls them.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

/** A 2xx with no body where the contract promises one is a server bug (B12
 *  r1). Restated rather than imported, as `newConnectEndpoints` does. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** One asset standing on a unit × service row — named by its NUMBER, its type
 *  and stage by their LABELS (B14 rule 31: never an id on screen). */
export interface BuildAssetRow {
  id: string;
  asset_no: string | null;
  type: string;
  type_name: string;
  size_class: string | null;
  status: string;
  status_name: string;
  install_date: string | null;
}

export interface BuildOrderRef {
  id: string;
  order_no: string | null;
  type: string;
  state: string;
  outcome: string | null;
  is_gate: boolean;
  unit_label: string | null;
  service: string | null;
}

/** One service at one unit — `connection_services`, with what stands on it. */
export interface ActivationRow {
  id: string;
  unit_id: string | null;
  unit_label: string | null;
  unit_type: string | null;
  unit_state: "pending" | "partly_activated" | "activated";
  service: string;
  state: string;
  activated_at: string | null;
  assets: BuildAssetRow[];
  qty: number;
  work_orders: BuildOrderRef[];
  open_orders: (string | null)[];
  blocked_by_gate: string | null;
  ready: boolean;
}

/** `GET /connections/{id}/activation`. */
export interface ActivationRead {
  connection_id: string;
  connection_no: string | null;
  state: string;
  /** The accounts open on the build's units — what *Cancel build* lists
   *  (ruled B: listed, never closed by the cancel). */
  accounts_on_units: {
    id: string;
    account_no: string | null;
    customer_name: string | null;
    unit_label: string | null;
  }[];
  can_activate: boolean;
  /** A catalogue key, or `null` — why nothing on this build can activate. */
  refusal: string | null;
  rows: ActivationRow[];
  ready_ids: string[];
  orders_total: number;
  open_orders: BuildOrderRef[];
  open_todos: { id: string; title: string }[];
}

export const activationQueryKey = (connectionId: string) =>
  ["connections", connectionId, "activation"] as const;

export async function getActivation(
  connectionId: string,
  client: ApiClient = api,
): Promise<ActivationRead> {
  return requireData(
    await client.get<ActivationRead>(`/connections/${connectionId}/activation`),
  );
}

export interface ActivationResult {
  id: string;
  connection_no: string | null;
  connection_state: string;
  activated: { id: string; unit_label: string | null; service: string }[];
  already_activated: string[];
  assets_installed: { id: string; asset_no: string | null; install_date: string }[];
}

/** `POST /connections/{id}/activate` — the rows to switch on, and whether the
 *  clerk has seen the open-orders warning (*Activate what is ready*). */
export async function activateServices(
  connectionId: string,
  body: { service_ids: string[]; acknowledge_open_orders: boolean },
  client: ApiClient = api,
): Promise<ActivationResult> {
  return requireData(
    await client.post<ActivationResult>(`/connections/${connectionId}/activate`, body),
  );
}

/** One row of the To-do tab — a to-do or a note. */
export interface BuildTodoRow {
  id: string;
  kind: "todo" | "note";
  title: string;
  detail: string | null;
  source: string;
  written_by: string | null;
  /** The viewer wrote it — the screen offers *Edit* on their own notes only. */
  mine: boolean;
  written_at: string;
  done: boolean;
  done_by: string | null;
  done_at: string | null;
}

export interface BuildTodoList {
  connection_id: string;
  rows: BuildTodoRow[];
  todos_open: number;
  notes: number;
}

export const todosQueryKey = (connectionId: string) =>
  ["connections", connectionId, "todos"] as const;

export async function getBuildTodos(
  connectionId: string,
  client: ApiClient = api,
): Promise<BuildTodoList> {
  return requireData(await client.get<BuildTodoList>(`/connections/${connectionId}/todos`));
}

/** *+ Add a to-do* and *+ Add a note* — one door, `kind` says which. */
export async function addBuildTodo(
  connectionId: string,
  body: { title: string; kind: "todo" | "note" },
  client: ApiClient = api,
): Promise<{ id: string; title: string; kind: string }> {
  return requireData(await client.post(`/connections/${connectionId}/outstanding-work`, body));
}

/** *Reopen* on a to-do marked Done. */
export async function reopenBuildTodo(
  connectionId: string,
  todoId: string,
  client: ApiClient = api,
): Promise<{ id: string; reopened: boolean }> {
  return requireData(
    await client.post(`/connections/${connectionId}/outstanding-work/${todoId}/reopen`, {}),
  );
}

/** *Edit* on the viewer's own note — the server refuses anybody else's. */
export async function editBuildNote(
  connectionId: string,
  todoId: string,
  title: string,
  client: ApiClient = api,
): Promise<{ id: string; title: string }> {
  return requireData(
    await client.post(`/connections/${connectionId}/outstanding-work/${todoId}/edit`, { title }),
  );
}

/** *Add unit* — a new unit at the build's address with the services it takes. */
export async function addBuildUnit(
  connectionId: string,
  body: { label: string; unit_type?: string | null; services: string[] },
  client: ApiClient = api,
): Promise<{ id: string; unit_id: string; label: string; services: string[] }> {
  return requireData(await client.post(`/connections/${connectionId}/units`, body));
}

/** `GET /accounts/{id}/build` — the build this account belongs to, and
 *  whether its unit still waits on that build's approval (ruled B: the account
 *  is open and billing waits). `awaiting_activation` is `null` once the unit is
 *  active, and for every account no build ever touched. */
export interface AccountBuildStatus {
  build: { id: string; connection_no: string | null; state: string } | null;
  awaiting_activation: { connection_id: string | null; connection_no: string | null } | null;
}

export const accountBuildStatusKey = (accountId: string) =>
  ["accounts", accountId, "build-status"] as const;

export async function getAccountBuildStatus(
  accountId: string,
  client: ApiClient = api,
): Promise<AccountBuildStatus> {
  const data = requireData(await client.get<AccountBuildStatus>(`/accounts/${accountId}/build`));
  return { build: data.build ?? null, awaiting_activation: data.awaiting_activation ?? null };
}
