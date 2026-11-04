// ── Trace ──────────────────────────────────────────────
// Change:   CR-173-BRC10 — a connection's named field group (New World /
//           Logos's *Send to City folder*): read, save, test, resend.
// Server:   06-backend/apps/integrations/file_drop_api.py
// ───────────────────────────────────────────────────────
//
// Its own file rather than four more functions in `integrationsEndpoints.ts`,
// which other lanes append to the same day (hard-won law 11, mechanism two).
//
// ⚠ NO RESPONSE CARRIES A PASSWORD. `password_hint` is `••••` + the last four
// (BR-INT-003); the password travels IN only, once, in the body of a save.

import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";

export interface FileDelivery {
  day: string; // ISO date — the DATA day, the one in the file name
  filename: string;
  folder: string;
  status: "sending" | "sent" | "failed";
  is_resend: boolean;
  receipt_count: number;
  unbalanced_count: number;
  unresolved_gl_count: number;
  failure: string | null;
  started_by_name: string | null;
  finished_at: string | null;
}

export interface FieldGroupView {
  group: string;
  connected: boolean;
  settings: Record<string, string>;
  password_hint: string | null;
  set_up: boolean;
  deliveries: FileDelivery[];
}

export interface FieldGroupTest {
  ok: boolean;
  sentence: string;
  server_key: string | null;
  server_key_captured: boolean;
  test_file: string | null;
  trace: string;
}

export interface ResendResult {
  done: boolean;
  code: string;
  sentence: string;
  filename: string;
  receipt_count: number;
}

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

function path(key: string, group: string): string {
  return `/integrations/${encodeURIComponent(key)}/groups/${encodeURIComponent(group)}`;
}

export async function getFieldGroup(
  key: string,
  group: string,
  client: ApiClient = api,
): Promise<FieldGroupView> {
  return requireData(await client.get<FieldGroupView>(path(key, group)));
}

/** Save the whole section. A blank password keeps the stored one. */
export async function saveFieldGroup(
  key: string,
  group: string,
  fields: Record<string, string>,
  client: ApiClient = api,
): Promise<FieldGroupView> {
  return requireData(await client.put<FieldGroupView>(path(key, group), { fields }));
}

/** **Test connection** — signs in and WRITES a test file. 200 either way. */
export async function testFieldGroup(
  key: string,
  group: string,
  client: ApiClient = api,
): Promise<FieldGroupTest> {
  return requireData(await client.post<FieldGroupTest>(`${path(key, group)}/test`, {}));
}

/** A person sends one day again, with a reason. */
export async function resendFieldGroupDay(
  key: string,
  group: string,
  day: string,
  reason: string,
  client: ApiClient = api,
): Promise<ResendResult> {
  return requireData(
    await client.post<ResendResult>(`${path(key, group)}/resend`, { day, reason }),
  );
}
