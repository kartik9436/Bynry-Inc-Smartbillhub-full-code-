// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 2 task 3 — PO 2026-10-03 on CR-008: *"Pick it
//           when you create the tax; change it later only in Settings -a llow
//           it"*. `PATCH /taxes/{id}` refuses a live tax's liability account by
//           name; Settings › Accounting re-points it through this one door.
// ───────────────────────────────────────────────────────
import { api } from "./client";
import type { ApiClient } from "./client";
import type { TaxRow } from "./endpoints";

/** `PATCH /taxes/{id}/gl-account` — `{liability_gl_account_id: uuid | null}`. */
export async function updateTaxGlAccount(
  taxId: string,
  changes: Record<string, unknown>,
  client: ApiClient = api,
): Promise<TaxRow> {
  const response = await client.patch<TaxRow>(
    `/taxes/${encodeURIComponent(taxId)}/gl-account`,
    changes,
  );
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}
