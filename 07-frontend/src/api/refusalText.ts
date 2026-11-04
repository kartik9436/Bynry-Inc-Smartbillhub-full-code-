// ── Trace ──────────────────────────────────────────────
// Component: FI-01 typed API client (B13 §2) — the refusal-copy half
// Story:    US-SHL-011 (EP-SHL-04 states & feedback)  Screens: every screen that can refuse
// Rules:    BR-SHL-020 r2 (PO 2026-08-19 — "server detail text should not reach
//           customer screens": the customer sentence comes from the catalogue
//           entry for `message_key` and from NOTHING else) ·
//           BR-SHL-020 r2 clause 3 (PO 2026-08-19 — a refusal the user cannot
//           act on says it is a system error and hands over an identifier they
//           can read aloud to support)
// Defects:  DEF-322 (422 refusals rendered engineering prose through
//           `params.detail`) · DEF-328 (`trace_id` complete on the backend and
//           rendered by nothing, anywhere)
// ───────────────────────────────────────────────────────
/**
 * ONE function turns a refusal into the sentence a utility reads.
 *
 * WHY IT IS ONE FUNCTION. Before DEF-322 there were six places that each wrote
 * `t(error.messageKey, error.params)` by hand, and `params` arrived straight
 * off the wire. Sixteen catalogue values interpolated `{{detail}}` — the free
 * text a service attaches to a `BizError` for engineers — so a clerk clicking
 * *Enrol in budget billing* read:
 *
 *     "That cannot be done: a per-account budget level override requires a
 *      REASON (BR-BIL-017 as OQ-068 closed it: allowed with reason + audit)"
 *
 * The PO's ruling (2026-08-19, decision log `bec921e`) is that server `detail`
 * text never reaches a customer screen. `detail` is NOT deleted — it still goes
 * to the audit attempt row and the server log, where support reads it. It just
 * stops being rendered. `stripDetail` below is the belt to the catalogue's
 * braces: even if someone reintroduces `{{detail}}` into a catalogue value, no
 * `detail` reaches i18next to fill it.
 *
 * ── THE SUPPORT REFERENCE (DEF-328) ───────────────────────────────────────
 * A refusal the user can never trigger says so and hands over an identifier
 * (PO 2026-08-19, decision log `3340c68`): *"if it is system error then you
 * tell user it is system erro this is error number or some identifier that they
 * can report to support"*. The identifier is NOT new — `trace_id` has been
 * generated per refusal, written to the BR-AUD-018 attempt row and returned in
 * every envelope since B12 §3. It was declared on the frontend type and
 * rendered by nothing.
 *
 * ⚠ IT IS SHORTENED FOR DISPLAY, AND THE SHORT FORM IS THE SEARCHABLE ONE.
 * The raw value is 32 hex characters; nobody dictates that over the phone. The
 * displayed form is the first eight, uppercased, split 4-4 — `5F2B-9C1D`. That
 * would be worse than useless if support could not look it up, so
 * `apps/audit/selectors.audit_queryset` accepts an entity-id PREFIX (dashes and
 * case ignored) and `GET /audit-log?f.entity_type=request&f.entity_id=5F2B-9C1D`
 * returns the attempt row carrying the full trace id. The two halves ship
 * together on purpose: a shortened id support cannot search by is worse than
 * none, because the user reads it out and the call stalls.
 */

import { type ApiError, UNEXPECTED_ERROR_KEY, isApiError, refusalParams } from "@/api/client";

export { refusalParams, supportRef, SUPPORT_REF_HEX, SUPPORT_REF_ABSENT } from "@/api/client";

export type Translator = (key: string, params?: Record<string, unknown>) => string;

/**
 * The sentence a screen shows for a caught error. Anything that is not an
 * `ApiError` (a thrown TypeError, an aborted fetch) has no catalogue key of its
 * own and falls back to the client's own copy.
 */
export function refusalText(t: Translator, error: unknown): string {
  if (!isApiError(error)) {
    return t(UNEXPECTED_ERROR_KEY);
  }
  const apiError = error as ApiError;
  return t(apiError.messageKey, refusalParams(apiError.params, apiError.traceId));
}

