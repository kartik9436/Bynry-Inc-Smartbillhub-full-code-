// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-7991 (2026-09-29) — a clerk on the One-time bill screen read
//          "R2: 4 versions of schedule '01a0b366-61fa-7f50-8cc4-25fa070287cc'
//          are in force for 'sewer' on 2026-10-29 (01a0b366-…, 01a0b388-…,
//          01a0b424-…, 01a0e712-…)". FOUR database uuids on screen.
// Rules:   B14 rule 31 (no database id is ever the visible value of a field —
//          PO, "no Databse ID on screen - that is a rule") · rule 32 (no rule
//          id or internal code in clerk-facing copy) · rule 33 (rationale is
//          ZERO words on screen) · rule 43 (a piece of UI is a COMPONENT, not
//          standalone code inside a page) · BR-SHL-020 r2 (server detail text
//          does not reach customer screens) · the 2026-08-19 ruling DEF-322
//          (a served sentence's words come from its `message_key`'s catalogue
//          entry and from nothing else)
// Impacts: features/billing/billingOpsShared.tsx (GapNotes, six lists) ·
//          features/billing/oneTimeConfirmShared.ts · features/billing/
//          billRunShared.tsx · features/customers/moveShared.tsx
// ───────────────────────────────────────────────────────

/**
 * WHY THIS IS A MODULE AND NOT FOUR COPIES IN FOUR PAGES.
 *
 * `BR-SHL-020 r2` already forbids server `detail` text on a customer screen,
 * and `refusalParams` in `api/client.ts` enforces it with `delete rest.detail`
 * — **on an ApiError's params**. Every string this file exists for arrives in
 * a **200-response body** instead, so that stripper is not anywhere near it
 * and never was. The guard existed and could not see the shape.
 *
 * Four render sites showed the raw engine sentence: `GapNotes` (feeding six
 * lists), the one-time confirm step, the bill-run shadow table and the
 * move-in / move-out final-bill preview. B14 rule 43 says a piece of UI is a
 * component rather than standalone code in a page, so the reading of a served
 * refusal is here, once, and the four sites call it.
 */

import type { Translator } from "@/features/tenancy/settingsShared";

/** The three fields a served refusal may carry beside its reason code. */
export interface ServedRefusal {
  /** The catalogue key the clerk's sentence resolves through, when the server
   *  states one (`DEF-BIL-5339`'s vehicle, reused by `DEF-RAT-7991`). */
  message_key?: string | null;
  /** The FACTS that sentence interpolates — a service, a date, a count, a
   *  connection size. Never an id: `G139` fails the server on one. */
  message_params?: Record<string, unknown> | null;
  /** Plain English. The id-free mirror of the `en` sentence where a key is
   *  stated; the ENGINEER's sentence, uuids and all, where one is not. */
  detail?: string | null;
}

/**
 * A uuid, in the two shapes this product writes them: dashed (`01a0b366-61fa-
 * 7f50-8cc4-25fa070287cc`) and the bare 8-hex truncation `G69` was written for.
 * Anchored on word boundaries so an ordinary word of four hex letters — `face`,
 * `added` — cannot match, which was measured rather than assumed.
 */
const UUID_SHAPED =
  /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|\b[0-9a-f]{32}\b/i;

/** The last-resort sentence. Six words, twice — B14 rule 33. */
export const REFUSAL_FALLBACK_KEY = "rating.refusal.unavailable";

/**
 * The words a clerk may read about `served`, or null when there is nothing to
 * say. **The one reader of a served refusal in this front end.**
 *
 * Three outcomes, in order:
 *
 *   1. a `message_key` -> the CATALOGUE sentence for it, in the clerk's own
 *      language, interpolated with the server's facts. A `service` parameter
 *      is resolved through `rating.service.<code>` HERE rather than in the
 *      catalogue value, so no catalogue entry carries a dotted identifier
 *      (rule 32) and eleven files stay free of one;
 *   2. no key, and a `detail` with no uuid in it -> that sentence, exactly as
 *      every one of these surfaces rendered it before (`DEF-CUS-6464`: a bare
 *      reason code breaks rule 32, so the sentence is the right thing to show);
 *   3. no key and a uuid in `detail` -> the fallback sentence. **Not the
 *      engineer's text with the ids cut out of it**: a sentence with holes in
 *      reads as a bug, and rule 33 says rationale is removed rather than
 *      shortened. This branch is the client-side half of the guard and it is
 *      what makes a NEW uuid-bearing refusal safe before anyone notices it.
 */
export function refusalSentence(served: ServedRefusal | null | undefined, t: Translator): string | null {
  if (!served) {
    return null;
  }
  const key = typeof served.message_key === "string" ? served.message_key : "";
  if (key) {
    return t(key, localisedParams(served.message_params, t));
  }
  const detail = typeof served.detail === "string" ? served.detail.trim() : "";
  if (!detail) {
    return null;
  }
  if (UUID_SHAPED.test(detail)) {
    return t(REFUSAL_FALLBACK_KEY);
  }
  return detail;
}

/**
 * The server's facts, with `service` turned into the clerk's own word.
 *
 * The server states the PLATFORM code (`sewer`, `storm_water`) because that is
 * what the rating chain narrows on; the eleven catalogues already hold the
 * label under `rating.service.<code>` for all eleven services. Any other
 * parameter passes through untouched.
 */
function localisedParams(
  params: Record<string, unknown> | null | undefined,
  t: Translator,
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...(params ?? {}) };
  const service = out.service;
  if (typeof service === "string" && service) {
    out.service = t(`rating.service.${service}`, { defaultValue: service });
  }
  return out;
}
