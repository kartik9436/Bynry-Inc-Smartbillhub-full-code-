// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 2 task 4 — the New discount form's lists.
// Contract: CR-166-BRC10 §9 — `GET /discounts/form-options` (task 3 serves it).
// Rules:    PO 2026-10-03 (*"Program owner - make this drop down"*, *"Exclusivity
//           group - can you make this drop down"*, *"Who qualifies * - drop
//           down"*) · hard-won law 2 (a list typed out by hand in the front end
//           fails SILENTLY when the server adds a row — so the form never holds
//           one)
// ───────────────────────────────────────────────────────
//
// Every list the New discount form renders comes from here. A route that is
// not served yet, or a key that is missing, is an EMPTY list — the form then
// shows an empty dropdown and keeps working (round-2 brief). Nothing here
// invents a fallback value.
import { api } from "./client";
import type { ApiClient } from "./client";

export interface DiscountFormOption {
  value: string;
  label: string;
}

/** A *Who qualifies* row: whether the SYSTEM can check it or the customer
 *  must SHOW PROOF. Ruling 3 (2026-10-03): only a `system` condition may be
 *  Automatic. */
export interface DiscountEligibilityOption extends DiscountFormOption {
  checked_by: "system" | "proof";
}

export interface DiscountFormOptions {
  program_owners: DiscountFormOption[];
  exclusivity_groups: DiscountFormOption[];
  eligibility: DiscountEligibilityOption[];
  enrollment_modes: DiscountFormOption[];
  verification: DiscountFormOption[];
  lapse: DiscountFormOption[];
  budget_periods: DiscountFormOption[];
  budget_out: DiscountFormOption[];
  types: DiscountFormOption[];
  applies_to: DiscountFormOption[];
}

export const EMPTY_DISCOUNT_FORM_OPTIONS: DiscountFormOptions = {
  program_owners: [],
  exclusivity_groups: [],
  eligibility: [],
  enrollment_modes: [],
  verification: [],
  lapse: [],
  budget_periods: [],
  budget_out: [],
  types: [],
  applies_to: [],
};

export const DISCOUNT_FORM_OPTIONS_PATH = "/discounts/form-options";

function optionList(raw: unknown): DiscountFormOption[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .filter(
      (row): row is DiscountFormOption =>
        typeof row === "object" &&
        row !== null &&
        typeof (row as DiscountFormOption).value === "string" &&
        typeof (row as DiscountFormOption).label === "string",
    )
    .map((row) => ({ value: row.value, label: row.label }));
}

/** A row whose `checked_by` is neither word is dropped rather than guessed:
 *  offering it as `system` would let a proof condition be Automatic. */
function eligibilityList(raw: unknown): DiscountEligibilityOption[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const rows: DiscountEligibilityOption[] = [];
  for (const row of raw as unknown[]) {
    const [option] = optionList([row]);
    const checkedBy = (row as { checked_by?: unknown }).checked_by;
    if (option !== undefined && (checkedBy === "system" || checkedBy === "proof")) {
      rows.push({ ...option, checked_by: checkedBy });
    }
  }
  return rows;
}

export async function getDiscountFormOptions(client: ApiClient = api): Promise<DiscountFormOptions> {
  const response = await client.get<Partial<Record<keyof DiscountFormOptions, unknown>>>(
    DISCOUNT_FORM_OPTIONS_PATH,
  );
  const body = response.data ?? {};
  return {
    program_owners: optionList(body.program_owners),
    exclusivity_groups: optionList(body.exclusivity_groups),
    eligibility: eligibilityList(body.eligibility),
    enrollment_modes: optionList(body.enrollment_modes),
    verification: optionList(body.verification),
    lapse: optionList(body.lapse),
    budget_periods: optionList(body.budget_periods),
    budget_out: optionList(body.budget_out),
    types: optionList(body.types),
    applies_to: optionList(body.applies_to),
  };
}
