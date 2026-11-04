// ── Trace ──────────────────────────────────────────────
// Change:  the uniform correction verbs. PO ruling 2026-09-17, shown a table of
//          what each of the five priced objects does today: *"please fix all
//          these"*.
// Defects: DEF-RAT-5709 — a discount cannot be edited at all, not even a draft
//          nobody has submitted.
// Rules:   BR-RAT-1016 (the three verbs) · BR-RAT-104 (the shape it
//          generalises) · BR-RAT-077 / BR-RAT-109 (the approval workflow, which
//          nothing here touches) · CLAUDE.md hard rule 4
// ───────────────────────────────────────────────────────
/**
 * The two doors a discount had neither of, plus the one for its identity.
 *
 * ⚠ **WHY THIS IS A SEPARATE MODULE AND NOT THREE MORE FUNCTIONS IN
 * `endpoints.ts`.** That file is being edited by another lane this wave, and a
 * whole-file collision on a 5,000-line shared module is how a sibling's work
 * leaves the branch by subtraction (CLAUDE.md law 11). Three exported functions
 * in a file nobody else is holding cost nothing and collide with nobody. **They
 * belong in `endpoints.ts` and should move there the next time it is open** —
 * this note is the reason, so the move is a decision rather than a discovery.
 *
 * The shapes are `endpoints.ts`'s own: the shared `ApiClient` from `client.ts`
 * and the same `Record<string, unknown>` payload every other rating write
 * takes.
 */
import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";

/**
 * A 2xx with no body where the contract promises one is a server bug (B12 r1).
 * Throwing beats handing a screen a silent `null` it will render as blank.
 *
 * ⚠ **THE FOURTH COPY OF FIVE LINES, AND IT IS NAMED RATHER THAN HIDDEN.**
 * `endpoints.ts` declares this and does NOT export it. Exporting it means
 * editing a 5,000-line file another lane is holding this wave, which is the
 * whole-file collision law 11 exists to prevent — so the duplication is the
 * cheaper of two bad trades, for now. **When this module folds back into
 * `endpoints.ts`, this goes with it.**
 */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/**
 * `BR-RAT-1016` verb 1 — the discount's IDENTITY: its code, its name, who runs
 * the programme and where the money comes from.
 *
 * **Not the priced agreement.** What a discount is WORTH still goes through a
 * new dated version, because `BR-RAT-078` makes enrolments survive versioning.
 * This is the same class of fact as the GL account beside it — what the
 * programme is CALLED — and it is editable at any time, in any state.
 */
export async function updateDiscount(
  discountId: string,
  payload: Record<string, unknown>,
  client: ApiClient = api,
): Promise<Record<string, unknown>> {
  return requireData(
    await client.request<Record<string, unknown>>(`/discounts/${encodeURIComponent(discountId)}`, {
      method: "PATCH",
      body: payload,
    }),
  );
}

/**
 * `BR-RAT-1016` verb 1 — a DRAFT version that has never been submitted, edited
 * in place.
 *
 * In `correct_tax`'s own words: *"a draft is not history. It has never priced
 * anything, so there is nothing to preserve and nothing to explain."* No
 * reason, no version bump, no approval. The server refuses on any other status
 * and names the correction route in its refusal.
 */
export async function updateDiscountVersion(
  discountId: string,
  versionId: string,
  payload: Record<string, unknown>,
  client: ApiClient = api,
): Promise<Record<string, unknown>> {
  return requireData(
    await client.request<Record<string, unknown>>(
      `/discounts/${encodeURIComponent(discountId)}/versions/${encodeURIComponent(versionId)}`,
      { method: "PATCH", body: payload },
    ),
  );
}

/**
 * `BR-RAT-1016` verb 2 — a LIVE version restated over the SAME window, because
 * the figure recorded for a period that has already run was wrong.
 *
 * ⚠ **A POST TO A COLLECTION, NOT A PATCH, AND THE SHAPE IS THE RULE.** A
 * correction MINTS a row; the corrected version is never rewritten. It returns
 * the NEW version, which is the one now in force. **Nothing already billed
 * changes** (hard rule 4), and whether it must is `OQ-310` — which the
 * response names, so an operator who has just fixed a value is not left
 * believing the money is fixed.
 *
 * The window is the server's and is copied from the row being corrected: a
 * `effective_from` in this payload is IGNORED, deliberately, because a
 * correction that moved the window would be a backdated change wearing a
 * correction's clothes.
 */
export async function correctDiscountVersion(
  discountId: string,
  versionId: string,
  payload: Record<string, unknown>,
  client: ApiClient = api,
): Promise<Record<string, unknown>> {
  return requireData(
    await client.post<Record<string, unknown>>(
      `/discounts/${encodeURIComponent(discountId)}/versions/${encodeURIComponent(versionId)}/corrections`,
      payload,
    ),
  );
}
