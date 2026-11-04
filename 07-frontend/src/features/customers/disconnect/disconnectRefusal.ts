// ── Trace ──────────────────────────────────────────────
// Defect:  **DEF-CUS-7680** — the disconnect wizard refused on step 4 and named
//          no reason. `POST /disconnects/schedule` answers `422
//          BIZ-COMPLETENESS` with the exact cause in `params.code`; nothing on
//          any screen read it, so eighteen distinct refusals reached a billing
//          clerk as *"This disconnect step can't be done as asked. Check the
//          case."* Reported by the Product Owner from deployed `v2.352.0`,
//          trace reference `2FA5-0006`, *"Diagnostic: none shown"*.
// Rules:   BR-SHL-020 r2 (server `detail` text never reaches a customer
//          screen — the CODE is what a screen branches on, the SENTENCE is the
//          catalogue's) · B14 rule 33 (a FACT ≤ 6 words · an INSTRUCTION ≤ 6
//          words per sentence, two short sentences beat one long one ·
//          RATIONALE is ZERO words on screen) · B14 rule 32 (no rule id and no
//          internal code in clerk-facing copy) · B14 rule 43 (a piece of UI is
//          built as a COMPONENT; standalone code inside a page is not reuse) ·
//          CLAUDE.md hard-won law 2 (built is not wired)
// Tests:   ../disconnectRefusal.dom.test.tsx · ../DisconnectWizard.test.tsx
// Impacts: ../DisconnectWizard.tsx (the commit failure) · steps/ChooseStep.tsx
//          (the step-1 pre-flight) · 06-backend/apps/customers/
//          transfer_disconnect_api.py (`_as_catalog_refusal`, which publishes
//          the code) · 06-backend/apps/customers/disconnect_reads.py
//          (`schedule_readiness`, which previews four of them)
// ───────────────────────────────────────────────────────
/**
 * ONE place that turns a disconnect refusal CODE into the sentence a clerk reads.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHY THIS IS A MODULE AND NOT THREE LINES IN THE WIZARD
 * ══════════════════════════════════════════════════════════════════════════
 * B14 rule 43: a piece of UI is built as a COMPONENT, and standalone code
 * inside a page is not reuse. Two surfaces need this answer already — the
 * wizard's commit failure and step 1's pre-flight — and they must not be able
 * to give a clerk two different sentences for one code. The record page's four
 * dialogs are the third, fourth, fifth and sixth (see the note on the key stem
 * below), and a seventh will arrive the day the list grows a bulk action.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * BRANCH ON THE CODE, NEVER ON THE ENGLISH
 * ══════════════════════════════════════════════════════════════════════════
 * `transfer_disconnect_api._as_catalog_refusal` states the contract in its own
 * docstring: *"The service's `code` rides alongside so a screen can branch
 * without parsing English."* It folds every `DisconnectRuleError` onto ONE
 * catalog code (`BIZ-COMPLETENESS`) and ONE message key
 * (`customers.disconnects.refused`), deliberately — *"picking among the nine
 * BIZ codes per refusal would be this layer INTERPRETING rules it does not
 * own"* — and publishes the difference in `params.code`.
 *
 * ⚠ **AND THE SERVICE'S OWN SENTENCE IS NOT THE ANSWER, EVEN THOUGH IT IS ON
 * THE WIRE.** `params.detail` carries prose written for an engineer — *"a cut
 * is scheduled after TIER 3 · 48-HOUR, the certified final notice
 * (BR-CUS-039: certified mail is REQUIRED on the final tier…)"* — and
 * `BR-SHL-020` r2 (PO 2026-08-19) rules that server `detail` never reaches a
 * customer screen. `api/client.refusalParams` deletes it before i18next can
 * see it, so it is not merely discouraged: it is gone by the time a screen
 * could render it. **The code selects a sentence we wrote; the detail goes to
 * the server log and the `BR-AUD-018` attempt row, where support reads it.**
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHY THE KEY STEM SAYS `disconnectRecord`, AND WHY IT IS NOT FORKED
 * ══════════════════════════════════════════════════════════════════════════
 * The family was minted by the disconnect RECORD page (`MarkAsCutDialog`,
 * `ReconnectDialog`, `RecordVisitDialog` and the page itself), so the stem
 * carries that screen's name. **It is the disconnect CASE's refusal
 * vocabulary, not one page's**, and it already holds 25 sentences in all
 * eleven languages — `already_cut`, `no_open_case`,
 * `collections_sequence_cannot_cut`, `protected`, `tier_3_proof_not_certified`
 * and the rest — every one of which the wizard can hit.
 *
 * **A second family keyed on the same codes would be a second answer**, and
 * this repository's most expensive recurring defect is two surfaces answering
 * one question differently (`DEF-127`'s shape). So the wizard reuses the stem
 * and this lane ADDED the seven codes it was missing rather than minting a
 * parallel `customers.disconnect.refused.*`. **Renaming the stem is a tidy-up
 * worth doing and it is not this defect's** — it would move 25 keys across
 * eleven catalogues and six call sites, which the maintenance process's
 * *minimal fix* step exists to keep out of a defect commit.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * AN UNMAPPED CODE FALLS BACK, AND THE FALLBACK IS THE OLD BEHAVIOUR EXACTLY
 * ══════════════════════════════════════════════════════════════════════════
 * A refusal this file has no sentence for renders what the screen rendered
 * before this lane: the catalogue value for the envelope's own `message_key`.
 * That is deliberate and it is the honest answer — **a blank is worse than a
 * generic**, and a clerk who reads nothing at all cannot even tell support
 * that something was refused. `DEF-320` is the row where an empty line was
 * chosen over a readable one and cost a support cycle.
 *
 * ⚠ **SO A NEW SERVER REFUSAL DEGRADES, IT DOES NOT BREAK** — which is the
 * property that lets the server add one without this file being in the same
 * commit. The cost is that it degrades SILENTLY, and nothing here can see it;
 * `06-backend/tests/test_def_cus_7680_schedule_refusals_carry_their_code.py`
 * is what holds the server end of the contract.
 */

import { isApiError } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import type { Translator } from "@/api/refusalText";

/**
 * The generic line, unchanged: what `customers.disconnects.refused` resolves
 * to. Named rather than inlined so the fallback and the tests that assert it
 * cannot drift apart.
 */
export const DISCONNECT_GENERIC_REFUSAL_KEY = "customers.disconnects.refused";

/**
 * The refusal codes the disconnect SCHEDULE can answer with, as measured
 * against `apps/customers/disconnects.schedule_cut`'s call graph on
 * 2026-09-28. **It is documentation and a test fixture, not a gate**: nothing
 * reads this array to decide what to render, because a code missing from it
 * must still fall back rather than break (see the header).
 *
 * ⚠ **EIGHTEEN, NOT SIX.** The defect report named six; the call graph raises
 * eighteen once `assert_treatments_expressible`, `assert_services_exist`,
 * `assert_cut_reachable`'s second ground, `assert_service_proved` and
 * `_require_running`'s halts are counted. Every one of them reached a clerk as
 * the same sentence. Counting what you found against what should be there is
 * CLAUDE.md law 7's fifth shape, and this array is that count written down.
 *
 * Two of `halt_reason`'s ten codes are deliberately absent —
 * `partial_pause_percent_not_set` and `partial_payment_pause` need
 * `paid_recently > 0`, which `_require_running` never passes — and
 * `ladder_complete` is skipped for a cut (`for_cut=True`). They carry
 * catalogue sentences anyway, from the record page.
 */
export const DISCONNECT_SCHEDULE_REFUSAL_CODES = [
  // payload — what the wizard sent
  "cut_reason_unknown",
  "deposit_disposition_unknown",
  "service_treatment_unknown",
  "service_code_unknown",
  "restrictor_is_a_third_state",
  // the case — all four knowable on step 1
  "no_open_case",
  "already_cut",
  "collections_sequence_cannot_cut",
  "account_closed_cannot_cut",
  "cut_before_final_tier",
  // the ladder — `_require_running`, with `for_cut`
  "stopped_by_hand",
  "nothing_owed",
  "balance_not_readable",
  "ladder_floor_not_readable",
  "below_ladder_floor",
  "protected",
  "payment_plan_pause",
  // the certified proof — `assert_service_proved`'s surviving refusal
  "tier_3_proof_not_certified",
] as const;

export type DisconnectRefusalCode = (typeof DISCONNECT_SCHEDULE_REFUSAL_CODES)[number];

/** One refusal a screen can show: the machine handle and nothing else. */
export interface DisconnectPreflightRefusal {
  code: string;
  br_ref: string;
  /** The service's own prose. **Carried, never rendered** — `BR-SHL-020` r2. */
  detail: string;
}

/**
 * The refusal code the server published, or `null` when this failure is not
 * one of ours (a dropped connection, a 403, a date the clerk left blank).
 *
 * ⚠ **IT READS `params.code` AND NEVER `ApiError.code`.** The two are
 * different facts with the same spelling: `ApiError.code` is the B12 catalog
 * code and is `BIZ-COMPLETENESS` for all eighteen of these, which is exactly
 * the collapse this defect is about.
 */
export function disconnectRefusalCode(error: unknown): string | null {
  if (!isApiError(error)) {
    return null;
  }
  const published = error.params.code;
  return typeof published === "string" && published !== "" ? published : null;
}

/**
 * The sentence for a refusal CODE, with the generic line as the fallback.
 *
 * Used by anything holding a code rather than a caught error — step 1's
 * pre-flight reads `GET /accounts/{id}/ladder`'s `schedule_readiness`, which
 * carries codes and no envelope.
 */
export function disconnectRefusalTextForCode(
  t: Translator,
  code: string | null | undefined,
): string {
  const generic = t(DISCONNECT_GENERIC_REFUSAL_KEY);
  if (code === null || code === undefined || code === "") {
    return generic;
  }
  // ⚠ **THE PREFIX IS A LITERAL IN THIS FILE ON PURPOSE.** `G18` reads a
  // template literal's static part as a key FAMILY and `G112` fails a family
  // no catalogue key begins with; a stem held in a variable is invisible to
  // both, and a key that resolves to nothing renders as the raw key string on
  // the screen that cuts somebody's supply off (`DEF-WRK-4036`).
  return t(`customers.disconnectRecord.refused.${code}`, { defaultValue: generic });
}

/**
 * The sentence for a caught API error — the wizard's commit failure.
 *
 * Falls back through `refusalText`, which is the ONE renderer every screen
 * uses (`DEF-322`), so a failure that is not a disconnect refusal reads
 * exactly as it read before this lane: a 403 says the role cannot do it, a
 * dropped connection says something went wrong with its support reference, and
 * a missing date still says *"Enter the cut date."*
 */
export function disconnectRefusalText(t: Translator, error: unknown): string {
  const fallback = refusalText(t, error);
  const code = disconnectRefusalCode(error);
  if (code === null) {
    return fallback;
  }
  return t(`customers.disconnectRecord.refused.${code}`, { defaultValue: fallback });
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-7680 (MAINTENANCE — 12-governance/22-product-maintenance-
//         process.md; reproduced in a browser and at the API before a line of
//         code was read)
// generated: 2026-09-28 by lane DSC-WIZARD-REFUSAL
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions:
//   E3 **THE KEY STEM STILL SAYS `disconnectRecord`** — see the header. It is
//      the disconnect case's one refusal vocabulary and forking it would be a
//      second answer; renaming it is a tidy-up outside this defect.
//   E1 ⛔ **AN UNMAPPED CODE DEGRADES SILENTLY, AND THE HALF THAT IS CHECKED
//      IS NOT THE HALF THAT BITES.** `disconnectRefusal.dom.test.tsx` asserts
//      that every code in `DISCONNECT_SCHEDULE_REFUSAL_CODES` resolves to a
//      catalogue sentence — so a key deleted here goes red. **What nothing
//      can see is a code the SERVER starts raising that this list never
//      learned**: the list is measured by hand off `schedule_cut`'s call
//      graph, and the two live on opposite sides of the wire. Such a refusal
//      renders the generic line, which is the defect surviving in miniature.
//      REPORTED rather than guarded, because the check that would close it is
//      a cross-stack one this repo does not have.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
