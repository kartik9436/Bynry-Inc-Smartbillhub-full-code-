// ── Trace ──────────────────────────────────────────────
// Change:  CR-171-BRC10 P2.28–P2.31 (lane MVI-WIZ-BILL) — the reads the
//          move-in's Billing step makes before the account exists (images
//          41–44). Contract: CR-171-BRC10 §9.MONEY.
// Server:  06-backend/apps/customers/move_in_money_api.py ·
//          apps/customers/move_fees.py · apps/rating/move_in_fees.py
// Rules:   CLAUDE.md hard rule 2 (every amount is the server's 4-place STRING;
//          nothing here parses or rounds one) · OQ-BIL-12788 CLOSED (a) (a
//          move-in fee is never taxed at move-in — `taxed_at_move_in: false`
//          on every row, so this file carries no tax figure at all)
// ───────────────────────────────────────────────────────
/**
 * A file of its own so it adds no hunk to `endpoints.ts`, which several lanes
 * edit at once (the reason `rateScheduleReads.ts` gives for the same shape).
 */
import type { ApiClient, ApiResponse } from "./client";
import { api } from "./client";
import type { PlanSections } from "./planFormEndpoints";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** Why a fee row has no figure — rating's own names (§9.MONEY). */
export type MoveFeeRefusal =
  | "size_required"
  | "size_not_recorded"
  | "size_not_priced"
  | "no_price"
  | "percent_has_no_basis"
  | "unknown_code"
  | "not_a_one_time_code"
  | "not_for_this_class"
  | "rating_not_wired"
  | string;

/** One row of the Fees table — `GET /move-ins/fees` and `/fees/quote`. */
export interface MoveFeeRow {
  kind: "deposit" | "fee";
  source: "plan" | "charge_code";
  code: string;
  name?: string | null;
  service?: string | null;
  /** 4-place string, or `null` while unpriced (a `per_case` code, a refusal). */
  amount: string | null;
  locked?: boolean;
  priced_by?: "flat" | "size" | "per_case" | "percent" | string;
  /** DEF-RAT-9807 — a `per_case` code's optional default, 4-place, which the
   *  row's amount box starts at; `null`/absent when it has none. */
  default_amount?: string | null;
  size_class?: string | null;
  refusal: MoveFeeRefusal | null;
  /** Always `false` — `OQ-BIL-12788` (a). Never drawn as *Taxable*. */
  taxed_at_move_in: false;
}

export interface MoveInFees {
  unit_id: string;
  account_type: string;
  services: string[];
  currency: string;
  /** Σ of the rows WITH a figure, 4-place. */
  total: string;
  deposit: Record<string, unknown> | null;
  rows: MoveFeeRow[];
}

/** One node of the meter → sub-meter → device tree (image 42). */
export interface MoveInAssetNode {
  asset_no: string | null;
  type: string | null;
  qualifier: string | null;
  size_class: string | null;
  children: MoveInAssetNode[];
}

/** One row of the claim list. `pairs_with` (`DEF-RAT-9833`, PO D2 (b) and
 *  ruling 4, 2026-10-06) names the account setting an Autopay or Paperless
 *  discount is kept matched to — the step switches it On when the row is
 *  picked; `null` for a discount a person applies for. */
export type ClaimableDiscount = PlanSections["discounts"][number] & {
  pairs_with?: "autopay" | "paperless" | null;
};

export interface MoveInPricing {
  unit_id: string;
  account_type: string;
  services: string[];
  plan_absent: null | "unit_has_no_plan" | string;
  /** The plan's sections, narrowed by rating to this move-in. `null` with
   *  `plan_absent` set. */
  plan:
    | (PlanSections & {
        /** The day the sections were read for — *Version on 10/10/2026*. */
        as_of?: string;
        plan_version?: { version: number; effective_from: string | null; status?: string } | null;
        narrowed_to?: { customer_class?: string | null; services?: string[]; sizes?: Record<string, string | null> };
        /** The plan's discounts a clerk may CLAIM — every one but the
         *  automatic ones no person may add (`DEF-CUS-9779`; since
         *  2026-10-06, `DEF-RAT-9833`, Autopay and Paperless are claimable
         *  again). `discounts` stays whole for the plan panel. */
        claimable_discounts?: ClaimableDiscount[];
      })
    | null;
  deposit: Record<string, unknown> | null;
  fees: { rows: MoveFeeRow[]; total: string; currency: string };
  assets: { service: string; assets: MoveInAssetNode[] }[];
  move_in_fees_taxed: false;
}

/** The query every read takes. `services` = the Start ticks; absent = every
 *  service the unit carries. */
export interface MoveInMoneyQuery {
  unitId: string;
  accountType: string;
  services?: readonly string[];
}

function query(params: MoveInMoneyQuery, extra: Record<string, string> = {}): Record<string, string> {
  const out: Record<string, string> = { unit_id: params.unitId, account_type: params.accountType, ...extra };
  if (params.services !== undefined && params.services.length > 0) {
    out.services = params.services.join(",");
  }
  return out;
}

/** `GET /move-ins/fees` — image 41's locked rows (deposit + plan fees). */
export async function getMoveInFees(params: MoveInMoneyQuery, client: ApiClient = api): Promise<MoveInFees> {
  return requireData(await client.get<MoveInFees>("/move-ins/fees", { query: query(params) }));
}

/** `GET /move-ins/fees/quote` — one code a clerk typed (image 43). */
export async function getMoveInFeeQuote(
  params: MoveInMoneyQuery & { code: string },
  client: ApiClient = api,
): Promise<MoveFeeRow> {
  return requireData(
    await client.get<MoveFeeRow>("/move-ins/fees/quote", { query: query(params, { code: params.code }) }),
  );
}

/** `GET /move-ins/pricing` — the Plan panel and *See full rates* (image 42). */
export async function getMoveInPricing(params: MoveInMoneyQuery, client: ApiClient = api): Promise<MoveInPricing> {
  return requireData(await client.get<MoveInPricing>("/move-ins/pricing", { query: query(params) }));
}

export const moveInMoneyKeys = {
  fees: (p: MoveInMoneyQuery) => ["customers", "move-ins", "fees", p.unitId, p.accountType, ...(p.services ?? [])] as const,
  pricing: (p: MoveInMoneyQuery) =>
    ["customers", "move-ins", "pricing", p.unitId, p.accountType, ...(p.services ?? [])] as const,
};
