// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W7 task 7.11 — **S90, the DISCONNECTS tab, FRONTEND half.**
//           The read model and `GET /disconnects` landed 2026-08-25 carrying
//           `B=deferred(no-frontend-half — S90's rendering is task 7.11's
//           frontend lane)`; the PO reported the hole from a live build:
//           *"nothing on new connect + on all of these screens"*. This is that
//           half.
// Rules:    BR-CUS-039 (the tiers) · BR-CUS-043 (an active, current plan pauses
//           the ladder) · BR-NOT-005 (a notice is WRITTEN; only the dispatcher
//           sends) · BR-SHL-010 · BR-SHL-011 (this list owns NO query string —
//           DEF-664) · BR-SHL-023 (ONE money formatting path) · BR-SHL-025 (a
//           control that cannot be used renders DISABLED WITH ITS REASON) ·
//           CLAUDE.md hard rule 2 (money DISPLAYS at 2 dp — the SERVER rounds) ·
//           B14 rules 5, 12, 16, 17, 19, 20, 21
// Questions: ⛔ **OQ-374 — OPEN and BLOCKING five of six segments.** ⛔ **OQ-366
//           — OPEN: no row on this screen names a chased party.**
// Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.8.1 (the five
//           tiles) · §5.8.2 (six segments, six tier chips, the LAST NOTICE
//           delivery claim, the accented CUT DATE) · §5.8.3 (the ladder and the
//           three protections) · §5.8.5 (TC-DSC-1..9) · §5.8.6 (the nine rows)
// Tests:    07-frontend/src/features/customers/DisconnectsTab.test.tsx
// Impacts:  AccountsListPage.tsx (the mount + `ACCOUNTS_BUILT_TABS`) ·
//           06-backend `GET /disconnects` (live)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · `LAST NOTICE` IS A DELIVERY CLAIM THIS PRODUCT CANNOT MAKE
// ══════════════════════════════════════════════════════════════════════════
// B18 §5.8.2 draws the column as `emailed` · `posted` · `certified sent` ·
// `certified signed` · `—`, and the SAME SECTION carries the design's own
// warning against it:
//
// > **`LAST NOTICE` is a delivery claim the product cannot currently make.**
// > There is **no email, SMS or print adapter in this release** — the in-app
// > bell is the only channel that delivers anything. `certified signed` asserts
// > a signature came back. **This column is drawn against a capability that
// > does not exist**, and a lane must render the absence rather than fabricate
// > a delivery state.
//
// So this cell renders **two facts and nothing else**: which TIER the notice
// was, and the DATE it was issued. `delivery_state` is written NULL by the
// writer and read NULL here, and **no branch in this file can produce the
// string `emailed`, `posted`, `certified sent` or `certified signed`** — there
// is no map from a delivery state to a label anywhere below, which is the only
// form of that guarantee a test can check. TC-DSC-6.
//
// The reason travels with the cell so a clerk who expected a channel learns why
// there is none, rather than reading the absence as data we lost.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · SIX SEGMENTS, ONE LIVE — OQ-374, OPEN
// ══════════════════════════════════════════════════════════════════════════
// §5.8.2 draws `All · At notice · Due to cut · On hold · Cut · Reconnecting` as
// an exclusive strip, and the two facts underneath are INDEPENDENT AXES:
// `On hold` is computed from the account's protections (`STATE_ON_HOLD` is
// declared, is in the migration's CHECK vocabulary and is **assigned nowhere in
// the repository** — measured 2026-08-25), while the other four are the stored
// `disconnect_cases.state`. A case at `notice_sent` whose account files a
// medical certificate satisfies `At notice` AND `On hold`, which is the path
// §5.8.3's own ladder diagram draws (`T1 · T2 · T3 -.-> HOLD`).
//
// **Which one holds the row is stated by no rule**, so `list_disconnects`
// serves `segment=all` and refuses the rest by name; the API turns that into a
// sentence rather than a 500. This screen therefore draws **all six**, with
// `All` selected and the other five DISABLED CARRYING THE SERVER'S OWN REASON
// (BR-SHL-025) — and it **never calls the route to discover the refusal**,
// because every response already says so in words. The five names, labels and
// sentences come from `segments[]` on the payload; nothing is typed here.
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · THE `TIER` CELL SERVES A LIST, AND THIS SCREEN DROPS NOTHING FROM IT
// ══════════════════════════════════════════════════════════════════════════
// B18 draws ONE bordered chip per row. The product can produce TWO — a tier
// reached AND a protection in force, or two protections — and no rule ranks
// them (the same OQ-374). The server serves every applicable chip in the drawn
// order with `ambiguous: true`, and this cell renders them all: **picking one
// would invent a precedence, and dropping one would hide a protection from a
// screen that authorises a cut.**
//
// The `—` is an ABSENCE with two causes a screen must tell apart, and both are
// served as sentences: `no_tier_reached` (nothing has been sent; the row is
// here for a protection, a cut awaiting payment, or a reconnection visit) and
// `unmapped_rung` (payments' `second_5_day`, which B18 draws no chip for —
// mapping it onto TIER 2 or TIER 3 would be a statement to a regulator about
// what a customer was told).
//
// ══════════════════════════════════════════════════════════════════════════
// 4 · `OWED` CAN BE UNREADABLE, AND `$0.00` IS THE ONE THING IT MUST NOT SAY
// ══════════════════════════════════════════════════════════════════════════
// DEF-127, in `selectors._balance_cells`' own words: a fabricated `$0.00`
// *"looks exactly like a settled account"* — and on THIS tab it looks like an
// account nobody should be chasing. `owed.display` is null when the ledger
// reading failed, and the cell then renders the server's reason.
//
// ⚠ **THE FIGURE IS `display`, NOT `stored`, AND IT IS NOT RE-ROUNDED HERE.**
// Hard rule 2: money is stored to 4 dp and DISPLAYS at 2, and the rounding for
// a human happens once — server-side, through `disconnects._money`, the same
// formatter `case_payload` uses. `MoneyCell` is still the one that prints it
// (BR-SHL-023: one money formatting path, one currency symbol), and handing it
// the already-2-dp string is idempotent: `min == max == 2`.
//
// ⚠ **`A-11507` OWES `$0.00` AND IS ON THIS TAB (TC-DSC-8)** — paid, awaiting a
// reconnection visit. A REAL zero and an unreadable figure therefore both
// appear on this screen and must look different, which is exactly why the
// absence is a sentence and not a dash.
//
// ══════════════════════════════════════════════════════════════════════════
// 5 · WHAT §5.8.2 DRAWS THAT THIS DOES NOT, EACH WITH ITS REASON
// ══════════════════════════════════════════════════════════════════════════
//   * **A `+ New disconnect` primary and any row action.** The S22 notice modal
//     and the five-step flow have no route in this application (measured
//     2026-08-25), and §5.8.4 step 5 is a **danger-tier commit** — a button
//     onto nothing is bad; a danger button onto nothing is worse. The empty
//     state's CTA is drawn disabled with the reason.
//   * **A sort control.** `_rows_for` orders by account number and takes no
//     `sort` param — deliberately NOT by urgency, because ranking `At notice`,
//     `Due to cut` and `On hold` against each other is the same unruled
//     precedence §2 refuses to take.
//   * **OQ-366's chased party.** No row names one, and a collections-sequence
//     row says so out loud. J08 step 2b: *"a green assertion naming either
//     party is a FAILURE."*
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DataTable } from "@/components/DataTable";
import { EyeIcon } from "@/components/icons";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { FilterBar, offerableFilters } from "@/components/FilterBar";
import { DateCell } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { MoneyCell } from "@/components/MoneyCell";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableFilterConfig, TableRequestState } from "@/components/tableTypes";
import { InlineLinkTo } from "@/components/Surfaces";
import { useTenantPath } from "@/routing/tenantPath";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";

// `DEF-CUS-5994` — the three controls the five worklists share, now that a
// parked draft is a ROW rather than a panel above the table.
import {
  ParkedBadge,
  ParkedDiscardDialog,
  ParkedDraftActions,
  ParkedWhyCell,
} from "./parkedDrafts";
import type { ParkedDiscardTarget } from "./parkedDrafts";
// The list's own cells, as COMPONENTS rather than code written into this page
// (B14 rule 43, PO: *"make them coponents - dont write stand alone code ,
// engineer it"*). `CaseNumberCell` and `DisconnectStateBadge` were added
// 2026-09-25 for `DEF-CUS-6744`, `DEF-CUS-6747` and `DEF-CUS-6749`.
//
// ⛔ **`DisconnectStateChips` AND `DisconnectDueChips` ARE NO LONGER IMPORTED.**
// The quick-view rows they drew are gone — one filter list now, see the note on
// `filterBarSlot` below. Both files are still on disk and are REPORTED as
// orphans rather than deleted here.
import { CaseNumberCell } from "./disconnect/list/CaseNumberCell";
import { DisconnectStateBadge } from "./disconnect/list/DisconnectStateBadge";
// PO 2026-09-20 — the cell that stops a date in the past reading as a tidy row.
import { CutDateCell } from "./disconnect/list/CutDateCell";
// `CR-125-BRC07` — the row action's destination. It landed in `4ff860296`, and
// this import is the hold being RELEASED in the same breath as the screen
// (hard-won law 2's mirror).
import { disconnectRecordPath } from "./disconnect/record/disconnectRecordEndpoints";
import { accountDetailPath } from "./customersShared";
import { DISCONNECT_WIZARD_ROUTE } from "./transferDisconnectShared";
import { DISCONNECT_SEGMENT_ALL, listDisconnects, rowsOf, totalOf } from "./worklistEndpoints";
import type { WorklistFilterState } from "./worklistEndpoints";
import type {
  DisconnectLastNotice,
  DisconnectList,
  DisconnectOwed,
  DisconnectRow,
  DisconnectTierCell,
} from "./worklistEndpoints";

/** The screen id `TableConfig` keys its column preference on. **No story owns
 *  S90** — `disconnects.py` filed it for the write half and
 *  `disconnect_reads.py` for the read half (hard-won law 8). REPORTED. */
export const DISCONNECTS_TABLE_SCREEN = "S90";

/**
 * §5.8.2's chip tones, carried as DATA by the server so B14's colour decision
 * is made once, in the design: TIER 3 in the **accent**, the three HELD chips
 * in **grey**, the rest ordinary ink.
 *
 * ⚠ A tone this map does not know renders as ordinary ink rather than as
 * nothing — an unrecognised tone must never make a chip disappear from a screen
 * that authorises a cut.
 */
const CHIP_TONE_CLASS: Record<string, string> = {
  ink: "border-neutral-400 text-text",
  accent: "border-accent text-accent-700",
  grey: "border-neutral-300 text-neutral-700",
};

/**
 * English fallbacks for the two vocabularies this screen names — `defaultValue`s,
 * not copy. The catalogues own the words the moment the locale lane adds the
 * keys; this lane may not edit `src/i18n/locales/*.json`, and a raw
 * `customers.disconnects.state.notice_sent` on the tab would be a second defect
 * on top of the empty one being fixed. Keys and sentences are REPORTED.
 *
 * §5.8.6 spells the states `Reconnecting` · `Cut` · `Scheduled` · `Notice sent`
 * · `On hold`. The three protections are `disconnects.PROTECTIONS`' own kinds
 * and B18 names them *"medical, plans, moratorium"*.
 */
/**
 * ⚠ **`notice_sent` READS `At notice` AND `scheduled` READS `Due to cut` FROM
 * `CR-125-BRC07` (2026-09-20), AND BOTH WORDS ARE THE DRAWING'S.** p142 of the
 * Accounts blueprint spells this column *At notice* / *Due to cut* / *On hold ·
 * medical*; §5.8.6 spelled it *Notice sent* / *Scheduled*, which is the STORED
 * code translated into English rather than the word a clerk was shown. B14
 * rule 41: the product UI matches the blueprint exactly.
 *
 * ⚠ **THE CODES DID NOT MOVE AND NOTHING SERVER-SIDE DID EITHER.** These are
 * `defaultValue`s under `customers.disconnects.state.<code>`; the same two keys
 * carry the new words in all eleven catalogues, so the filter panel's options
 * and this cell say the same thing without either one typing a vocabulary.
 *
 * ⚠ **THREE OF THE SERVER'S EIGHT STATES WERE MISSING AND RENDERED AS THEIR
 * CODES (`DEF-CUS-6053`).** A clerk opening the filter panel read *At notice ·
 * Due to cut · On hold · Cut · Reconnecting* and then `closed_out`,
 * `in_progress_draft`, `parked`. The list's own docstring below says a state
 * added to `disconnects.py` reaches this panel with no edit — which is TRUE,
 * and what it reached it as was its code.
 *
 * ⚠ **`Draft` AND `Parked` ARE THE WORDS `MoveInsTab` ALREADY USES**, minted on
 * the same day by `DEF-CUS-5994` and deliberately identical: two spellings for
 * one concept is two things to get wrong. `Closed out` is `BR-CUS-430`'s eighth
 * state (PO 2026-08-27) — the account the case belongs to is finished — and it
 * is two words because B14 rule 33 gives a LABEL three.
 *
 * ⚠ **THE MAP IS ASSERTED COMPLETE AGAINST THE SERVER'S VOCABULARY** by
 * `disconnectStateLabels.test.ts`, which parses `CASE_STATES` out of
 * `apps/customers/disconnects.py` and the two minted draft codes out of
 * `disconnect_reads.py`. A hand-maintained map keyed on a server vocabulary
 * fails SILENTLY — the same shape, and the same remedy, as
 * `signupServices.test.ts` asserting eleven services against the seed.
 */
//
// ⚠⚠ **THE WORDS MOVED AGAIN ON 2026-09-25, AND THIS TIME TO THE CLERK'S OWN
// SIX (PO, through the Disconnects-list redesign): `Notified · Scheduled · Off
// · Paid · Restored · Held`.** The note above records them moving from §5.8.6's
// stored-code English to p142's `At notice` / `Due to cut`; this is the third
// spelling and the first one that is not a translation of an internal word.
// `Reconnecting` described the SYSTEM's state machine, `Paid` describes what
// happened to the customer; `Cut` is the act and `Off` is the condition a clerk
// is looking for. **The codes did not move and no server value changed** —
// these are `defaultValue`s under the same eleven keys.
//
// ⛔ **AND `Paid` WAS WITHDRAWN ON 2026-10-29 (`DEF-CUS-10667`, PO *"1A"*).**
// It was true of what happened to the customer only while a case could reach
// `reconnecting` on a settled account; `BR-CUS-1097` (2026-09-25) let an owing
// account proceed, and DSC-26-0001 read `Paid` owing $8,315.00. The fourth
// word is **`Reconnecting`** — on the tile, in the cell, in the filter and on
// the case head chip, which borrows these keys.
//
// ⚠ **`closed_out` READS `Closed` AND IS A SEVENTH WORD.** The six do not cover
// it and folding it onto one of them would say something false; see
// `DisconnectStateBadge` §2. REPORTED.
const STATE_LABELS: Record<string, string> = {
  notice_sent: "Notified",
  scheduled: "Scheduled",
  on_hold: "Held",
  cut: "Off",
  // `DEF-CUS-10667` (PO 2026-10-29, *"1A"*): `Reconnecting`, never `Paid` —
  // since `BR-CUS-1097` a case reaches this state still OWING money.
  reconnecting: "Reconnecting",
  // `BR-CUS-430` (PO 2026-08-27, closing DEF-724) — the eighth state, reached
  // from `cut` and from nowhere else. It is DRAWN by the server (`drawn: true`)
  // and was the only drawn state with no word at all.
  closed_out: "Closed",
  // `BR-CUS-430` (PO 2026-08-27, closing DEF-724) — the eighth state, reached
  // from `cut` and from nowhere else. It is DRAWN by the server (`drawn: true`)
  // and was the only drawn state with no word at all.
  stopped: "Stopped",
  restored: "Restored",
  // `DEF-CUS-5994`'s two, which are facts about a `wizard_parks` row rather
  // than about a raised case — which is why the server marks them `drawn:
  // false` and why neither could reuse a stored case state.
  in_progress_draft: "Draft",
  parked: "Parked",
};

/**
 * One state code → the word a clerk reads, or an honest absence. **Never the
 * code** (`DEF-CUS-6053`).
 *
 * ⚠ **A MISSING LABEL FAILS LOUDLY IN THREE PLACES, AND THE SCREEN IS THE
 * QUIETEST OF THEM.** Rendering `closed_out` is how a missing word stays
 * invisible for a month: it looks deliberate, it is never blank, and no gate in
 * this repo reads clerk-facing copy. So (1) `disconnectStateLabels.test.ts`
 * goes RED when the server's vocabulary grows past this map, (2) landing here
 * writes a `console.error` naming the code — `MoneyCell`'s posture, *"LOUD,
 * always"* — and (3) the cell states an absence rather than the code.
 *
 * ⚠ **THE SERVER'S OWN `label` IS READ WHEN IT SENDS ONE**, which it does for
 * `in_progress_draft` and `parked` and which nothing has ever looked at. It
 * sits BELOW the catalogue and below this map, because it is English from a
 * payload and the catalogues carry eleven languages — but above the absence,
 * because a real word beats *not named yet*.
 */
export function disconnectStateLabel(
  code: string,
  t: (key: string, params?: Record<string, unknown>) => string,
  servedLabel?: string | null,
): string {
  const known = STATE_LABELS[code] ?? (servedLabel === null ? undefined : servedLabel);
  if (known === undefined) {
    console.error(
      `DisconnectsTab: the server offers the state "${code}" and STATE_LABELS has no word ` +
        "for it, so the row states an absence rather than the code (DEF-CUS-6053). Add the " +
        "label and the eleven catalogue keys; disconnectStateLabels.test.ts is already red.",
    );
    return t("customers.disconnects.state.unnamed", { defaultValue: "Not named yet" });
  }
  return t(`customers.disconnects.state.${code}`, { defaultValue: known });
}

/**
 * `BR-CUS-1083`'s four outcomes, as `defaultValue`s — the catalogues own the
 * words. The set is CLOSED server-side (a CHECK constraint and a service
 * guard), so an unknown code here is a programming error rather than a new
 * outcome; it falls through to the code on `data-state-visit`, where a walk
 * reads it and a clerk does not.
 *
 * ⚠ **THREE OF THE FOUR CLEAR THE CUT DATE**, which is exactly why the list
 * needs these words at all (`DEF-CUS-6749`): the case goes back to
 * `notice_sent` and, without this, reads like a case nobody has visited.
 */
const VISIT_OUTCOME_LABELS: Record<string, string> = {
  locked_gate: "Locked gate",
  access_refused: "Access refused",
  paid_at_door: "Paid at door",
  disputed: "Disputed",
};

const PROTECTION_LABELS: Record<string, string> = {
  medical_certificate: "Medical certificate",
  payment_plan: "Payment plan",
  weather_moratorium: "Weather moratorium",
};

// ══════════════════════════════════════════════════════════════════════════
// THE SCREEN'S OWN VOICE — DEF-742
// ══════════════════════════════════════════════════════════════════════════
/**
 * ⛔ **WHAT THIS REPLACED.** Every absence on this tab used to render the
 * server's `detail` — the diagnostic `disconnect_reads.py` writes for an
 * ENGINEER — straight into the DOM, as visible text under the table, as the
 * `title` on six cells, and as the reason on the segment chips. A billing clerk
 * hovering a dash read *"this account sits on payments' `second_5_day` rung,
 * which B18 §5.8.2 draws NO chip for"*.
 *
 * ⚠ **AND THE EXPENSIVE PART IS THAT THIS TAB WAS OUTSIDE A GUARD THAT ALREADY
 * EXISTED.** DEF-731 was filed from what the PO happened to CLICK and was fixed
 * on exactly those screens — the two Move tabs and the transfer wizard —
 * leaving `screenVoice.guard.test.tsx` covering three surfaces of a module-wide
 * pattern. A guard's PRESENCE reads as protection, which is why a coverage gap
 * inside one costs more than no guard at all. That test now renders this tab
 * too; the fix and its guard land together.
 *
 * **The shape is DEF-731's, deliberately unchanged**: the SCREEN authors the
 * sentence, keyed off the absence's `code`; `detail` stays in
 * `disconnect_reads.py` as the diagnostic it is; and the tracking id travels as
 * a `data-` attribute, never as prose (DEF-332 · G28).
 *
 * A code with no sentence here falls through to one honest generic line rather
 * than to the server's — an unknown absence must not re-open the defect.
 */
export const DISCONNECT_ABSENCE_COPY: Record<string, string> = {
  segment_precedence_unruled:
    "This account is both on hold and has a case open. Which of the two this filter should " +
    "count has not been decided, so it appears under both.",
  ledger_publishes_no_per_account_ar_position:
    "What this customer owes cannot be read from the books at the moment, so no figure is " +
    "shown here. A blank is not the same as nothing owed.",
  no_tier_reached:
    "No notice has been sent on this account, so it has not reached a step on the reminder " +
    "ladder yet.",
  unmapped_rung:
    "This account is on a reminder step this list has no label for, so nothing is shown. The " +
    "step itself is recorded.",
  more_than_one_chip_applies:
    "More than one reminder step applies to this account. Which one should win has not been " +
    "decided, so both are shown rather than one picked for you.",
  delivery_adapter_absent:
    "How a notice reached the customer is not recorded. This release does not send email, " +
    "post or SMS — the in-app bell is the only channel.",
  cut_accrual_caption_superseded:
    "Charges stop on the day the service is cut. Anything owed before then stays owed.",
  no_case_opened:
    "No disconnection case has been opened for this account. It is on this list because a " +
    "protection is in force.",
  numbering_series_missing:
    "No number format has been set up for disconnection cases, so this one has no reference " +
    "yet. The case itself is real — only its reference is missing.",
  chase_subject_unresolved:
    "Who should be chased for this debt has not been decided, so nobody is named here.",
};

/** The one sentence a person may read for an absence on this tab. Never
 *  `detail`. Mirrors `MoveInsTab.absenceCopy`, and mirrors it on purpose:
 *  two shapes for one rule is two things to get wrong. */
export function disconnectAbsenceCopy(
  absence: { code?: string | null } | undefined | null,
  t: (key: string, params?: Record<string, unknown>) => string,
): string | undefined {
  if (absence === undefined || absence === null) {
    return undefined;
  }
  const code = absence.code ?? "";
  const known = DISCONNECT_ABSENCE_COPY[code];
  return known === undefined
    ? t("customers.disconnects.absent.unknown", {
        defaultValue:
          "SMART360 Next cannot show this yet, so nothing is shown here rather than a value " +
          "nobody worked out.",
      })
    : t(`customers.disconnects.absent.${code}`, { defaultValue: known });
}

export function chipToneClass(tone: string): string {
  return CHIP_TONE_CLASS[tone] ?? CHIP_TONE_CLASS.ink;
}

/**
 * The one dimension `DSC-01` declares — the STORED case state (CR-045 wave G,
 * `DEF-1702`).
 *
 * ⚠ **THIS REPLACED `disconnectSegments`, AND A SEGMENT AND A FILTER ARE NOT
 * THE SAME QUESTION.** The removed function built B18 §5.8.2's six-tab strip
 * from `payload.segments`; five of the six were always `supported: false` and
 * the sixth was always the active one, so the strip could not be operated at
 * all — it occupied the slot B14 rule 12 reserves for the filter and narrowed
 * nothing, which is how this screen was counted twice as *having* a filter
 * (`DEF-1702`).
 *
 * **A SEGMENT is an exclusive partition** — every row belongs to exactly one
 * tab. On this list `On hold` is COMPUTED from the account's protections while
 * `At notice`, `Due to cut`, `Cut` and `Reconnecting` are the stored
 * `disconnect_cases.state`, so a protected account with an open case satisfies
 * two at once and **no rule ranks them**. That is `OQ-374`, OPEN, and it is why
 * `?segment=` still refuses everything but `all`.
 *
 * **A FILTER is a predicate:** *does this row's stored `state` equal X*. It
 * needs no ranking, no exclusivity and no precedence, it hides nothing, and it
 * decides no part of OQ-374 — so it is answerable today and the segments are
 * not. `payload.segments` is still served and still unchanged; this screen just
 * no longer draws a control over it.
 *
 * ⚠ **THE VOCABULARY IS `states` ON THE PAYLOAD AND NOT `segments`.**
 * `DISCONNECT_FILTER_STATES` is `CASE_STATES` minus the codes `open_cases`
 * excludes, derived by subtraction on the server — a state that takes the row
 * OFF this list can never be a useful option here. Nothing is typed on this
 * side (BR-SHL-010), so a state added to `disconnects.py` reaches this panel
 * with no edit, and `STATE_LABELS` stays a `defaultValue` map rather than
 * becoming a second vocabulary.
 */
export function disconnectFilterGroups(
  /**
   * ⚠ **`label` IS ON THE WIRE AND WAS READ BY NOTHING (`DEF-CUS-6053`).**
   * `disconnect_reads.py` sends one for `in_progress_draft` and `parked`.
   * Widened HERE rather than on `WorklistFilterState`, which is another
   * lane's file and is shared by four tabs.
   */
  states: (WorklistFilterState & { label?: string | null })[] | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
  /** PO 2026-09-20 — the `f.due` vocabulary. OPTIONAL and last, so every
   *  existing caller compiles and renders exactly what it rendered before. */
  dues?: WorklistFilterState[],
): TableFilterConfig[] {
  return [
    {
      name: "state",
      label: t("customers.disconnects.col.state", { defaultValue: "State" }),
      options: (states ?? []).map((state) => ({
        value: state.code,
        // ⛔ **WAS `… ?? state.code` (`DEF-CUS-6053`).** Three of the server's
        // eight states had no word here and this line rendered their codes.
        label: disconnectStateLabel(state.code, t, state.label),
      })),
    },
    // PO 2026-09-20 — the SECOND dimension. `offerableFilters` drops a group
    // with no options, so a deployment whose server predates `dues` renders
    // exactly the panel it renders today (`DEF-782`'s posture).
    {
      name: "due",
      label: t("customers.disconnects.col.cutDate", { defaultValue: "Cut date" }),
      options: (dues ?? []).map((due) => ({
        value: due.code,
        // The server's word, translatable, never invented here (BR-SHL-010).
        label: t(`customers.disconnects.due.${due.code}`, {
          defaultValue: due.label ?? due.code,
        }),
      })),
    },
  ];
}

// ══════════════════════════════════════════════════════════════════════════
// THE CELLS
// ══════════════════════════════════════════════════════════════════════════

/** §4 — the ledger's figure, or its stated absence. Never a fabricated zero. */
export function OwedCell(props: {
  owed: DisconnectOwed;
  /** DEF-742 — the cell states the absence in the READER's words. Optional for
   *  the same reason as `disconnectSegments`: the English default stands in. */
  t?: (key: string, params?: Record<string, unknown>) => string;
}) {
  const { owed } = props;
  const owedTranslate =
    props.t ??
    ((_key: string, params?: Record<string, unknown>) =>
      String((params as { defaultValue?: string } | undefined)?.defaultValue ?? ""));
  if (owed.display === null || owed.currency === null) {
    // The reading FAILED. A dash would read as "nothing owed" on the one screen
    // where that is the most expensive thing to say wrongly (DEF-127).
    return (
      <span
        role="note"
        className="text-sm text-neutral-700"
        data-owed-absent=""
        data-tracks={owed.unavailable?.[0]?.br_ref ?? owed.unavailable?.[0]?.code}
      >
        {/* ⛔ DEF-742 — was `owed.unavailable?.[0]?.detail`, an engineer's
            sentence rendered as body copy on the row where saying the wrong
            thing about money costs most (DEF-127). */}
        {disconnectAbsenceCopy(owed.unavailable?.[0], owedTranslate) ?? ""}
      </span>
    );
  }
  // BR-SHL-023 — the ONE money path. `display` is the server's 2-dp string
  // (hard rule 2), so this formats and does not re-round.
  return (
    <span data-owed-display={owed.display}>
      <MoneyCell amount={owed.display} currency={owed.currency} />
    </span>
  );
}

/** §3 — every applicable chip, in the drawn order, and never a chosen one. */
export function TierCell(props: {
  tier: DisconnectTierCell;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  // ── THE PROTECTION CHIPS LEAVE THIS COLUMN (the 2026-09-25 redesign) ────
  //
  // ⛔ **A HELD ROW SAID ITS PROTECTION TWICE** — `HELD · WEATHER MORATORIUM`
  //    in TIER and `Held / Weather moratorium` in STATE, side by side on the
  //    same row. **Both drawings agree the Tier cell on a held row is `—`**:
  //    the blueprint's p142 draws it, and so does the redesign.
  //
  // ⚠ **THIS ONLY BECAME SAFE WHEN THE STATE CELL STARTED CARRYING IT.** The
  //    cell's own §3 said, correctly, that *"dropping one would hide a
  //    protection from a screen that authorises a cut"* — and that was true
  //    while STATE printed a run-on of two state words and nothing else.
  //    `DisconnectStateBadge` now gives the protection the badge AND names the
  //    kind under it, so nothing is hidden; it is said ONCE, in the column
  //    whose question it answers.
  //
  // ⚠ **THE SERVER STILL SERVES EVERY CHIP AND `OQ-374` IS UNTOUCHED.**
  //    `chips_for` is unchanged: the payload carries the protection chips with
  //    `ambiguous` intact, and this is a rendering choice on one screen rather
  //    than a narrowing of the read. A second consumer still gets everything.
  //
  // ⚠ **`ambiguous` IS RECOMPUTED OVER WHAT IS LEFT.** A row that was
  //    "ambiguous" only because a tier chip and a protection chip both applied
  //    is no longer ambiguous HERE — the two facts are now in two columns —
  //    so printing *two apply* over a single visible chip would be a note
  //    about something a clerk cannot see.
  const tier = {
    ...props.tier,
    chips: props.tier.chips.filter((chip) => !chip.code.startsWith("held_")),
  };
  const ambiguous = tier.chips.length > 1 && props.tier.ambiguous;
  if (tier.chips.length === 0) {
    // B18's `—`, with WHICH absence it is said in words: nothing sent yet, or a
    // rung this design draws no chip for.
    return (
      <span
        role="note"
        className="text-sm text-neutral-700"
        data-tier-absent={tier.unavailable[0]?.code}
        data-tracks={tier.unavailable[0]?.br_ref}
        // ⛔ DEF-742 — a `title` IS copy: a clerk hovering this dash read the
        // server's own diagnostic. The tooltip now carries the reader's
        // sentence about the same fact.
        title={disconnectAbsenceCopy(tier.unavailable[0], props.t)}
      >
        —
      </span>
    );
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-1" data-tier-ambiguous={ambiguous}>
      {tier.chips.map((chip) => (
        <span
          key={chip.code}
          // §5.8.2: *"a bordered chip"*. B14 rule 5's small tier for the type,
          // which is the size every other chip in the product uses.
          className={`inline-flex items-center border px-1.5 py-0.5 text-xs uppercase tracking-wide ${chipToneClass(chip.tone)}`}
          data-chip={chip.code}
        >
          {chip.label}
        </span>
      ))}
      {ambiguous && (
        // Two chips on a cell B18 draws with one. The row is not wrong — the
        // RULE is missing — so the note explains rather than apologising.
        <span
          role="note"
          className="text-xs text-neutral-700"
          data-chips-ambiguous=""
          data-tracks={tier.unavailable[0]?.tracks}
          title={disconnectAbsenceCopy(tier.unavailable[0], props.t)} /* DEF-742 */
        >
          {/* ⚠ NOT `customers.disconnects.tier.ambiguous` — that key already
              exists and holds the BACKEND'S refusal sentence: "More than one
              chip applies here. Which one wins is undecided." Rendering it
              inside a chip cell would put a full sentence where a two-word
              fragment belongs, on every ambiguous row. Two slots, two keys.
              The long one stays with the payload that raises it. */}
          {props.t("customers.disconnects.tier.ambiguousShort", {
            defaultValue: "two apply",
          })}
        </span>
      )}
    </span>
  );
}

/**
 * §1 — the tier and the issued date, and NO delivery claim, ever.
 *
 * ⚠ There is deliberately no `delivery_state` branch in this function. A map
 * from `emailed`/`posted`/`certified sent`/`certified signed` to a label is the
 * thing B18 forbids, and its ABSENCE from the source is what makes the
 * guarantee checkable rather than promised (hard-won law 1).
 */
export function LastNoticeCell(props: {
  notice: DisconnectLastNotice;
  t: (key: string, params?: Record<string, unknown>) => string;
  timeZone: string;
  dateFormat: Parameters<typeof DateCell>[0]["dateFormat"];
}) {
  const { notice } = props;
  if (notice.issued_on === null) {
    // No notice on this case at all. §5.8.6 draws `—` on the three HELD rows,
    // which never entered the ladder.
    return (
      <span
        className="text-neutral-700"
        title={disconnectAbsenceCopy(notice.unavailable, props.t)} /* DEF-742 */
        data-notice-none=""
      >
        —
      </span>
    );
  }
  return (
    // ── `CR-125-BRC07` — ONE LINE, `TIER · DATE`, WHICH IS WHAT p142 DRAWS ──
    //
    // This cell was a COLUMN of three: the date, the tier under it, and the
    // sentence *"how it was delivered is not recorded"* under that, on every
    // row. p142 draws `10-day · 04/24/2026` — one line, two facts, the order
    // this now uses.
    //
    // ⚠ **THE SENTENCE LEFT THE SCREEN AND THE GUARANTEE DID NOT.** It is
    // RATIONALE — *why* there is no channel — and B14 rule 33 gives rationale
    // ZERO WORDS ON SCREEN. Rule 33 also says rationale is REMOVED and not
    // shortened, which matters here because it was SEVEN words against a
    // six-word cap for a fact and would still have been rationale at six. It
    // was also a SECOND COPY: the reader's sentence already rides on this
    // cell's `title`, which is where BR-SHL-025 puts a reason — on the thing it
    // is about — and a clerk who expected a channel still finds it there.
    //
    // ⛔ **TC-DSC-6 IS UNTOUCHED AND IS STRONGER FOR IT.** The guarantee is
    // that NO DELIVERY CLAIM is rendered — there is no map from `emailed` /
    // `posted` / `certified sent` / `certified signed` to a label anywhere in
    // this file, which is the only form of that promise a test can check. The
    // `data-delivery-absent` marker moves onto this wrapper, beside the `title`
    // it belongs with, so the case that asserts it is unchanged.
    <span
      className="inline-flex flex-col"
      data-last-notice=""
      data-delivery-absent=""
      data-tracks={notice.unavailable.br_ref}
      // The delivery adapter's absence rides on the cell it is about
      // (BR-SHL-025's placement), so a clerk expecting a channel learns why
      // there is none instead of reading a gap as lost data.
      title={disconnectAbsenceCopy(notice.unavailable, props.t)} /* DEF-742 */
    >
      {/* ⚠ **`whitespace-nowrap`, BECAUSE THE FIRST DRAFT WRAPPED MID-LABEL.**
          Walked at 1440, the cell broke as `TIER 2 ·` / `10-DAY · 04/24/2026`
          — two lines where p142 draws one, and a line ending on a middle dot.
          The two facts are one line in the drawing and they are one line here.

          ⚠ **AND THE TIER WORD IS THE SERVER'S, NOT THIS SCREEN'S.** p142
          writes `10-day · 04/24/2026`; the payload's chip label is
          `TIER 2 · 10-DAY`, which carries a separator of its own and makes
          THREE segments where the drawing draws two. The labels come from
          `disconnect_reads`' `chips`, so shortening them is a server change
          and is REPORTED rather than taken here. */}
      <span className="inline-flex items-center gap-1 whitespace-nowrap">
        {notice.tier !== null && (
          <>
            <span data-notice-tier={notice.tier}>
              {props.t(`customers.disconnects.chip.${notice.tier}`, { defaultValue: notice.tier })}
            </span>
            <span aria-hidden="true">·</span>
          </>
        )}
        <DateCell
          value={notice.issued_on}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      </span>
    </span>
  );
}

export function disconnectsTableConfig(
  t: (key: string, params?: Record<string, unknown>) => string,
  cells: {
    owed: (row: DisconnectRow) => JSX.Element;
    tier: (row: DisconnectRow) => JSX.Element;
    cutDate: (row: DisconnectRow) => JSX.Element;
    lastNotice: (row: DisconnectRow) => JSX.Element;
    state: (row: DisconnectRow) => JSX.Element;
    actions: (row: DisconnectRow) => JSX.Element;
    /** Record links (PO 2026-10-19): the account cell. Absent, the number
     *  is plain text — a bare config, as a test builds it. */
    account?: (row: DisconnectRow) => JSX.Element;
  },
): TableConfig<DisconnectRow> {
  return {
    screenId: DISCONNECTS_TABLE_SCREEN,
    getRowId: (row) => row.account_id,
    // The four legs `_search_account_ids` really ORs, each through the reader
    // that already owns it, so this box finds exactly what the Accounts box
    // finds.
    // ⚠ **`case_no` JOINED THE LEGS ON 2026-09-20 (`CR-125-BRC07`).** p142
    // prompts *"Search by case #, account, customer or address"*, and the case
    // number is the FIRST COLUMN on every row — the one thing a clerk quotes
    // down a telephone — while the query could not reach it. The server added
    // the leg (`disconnect_reads.SEARCH_HINT` and its `legs` tuple) and this
    // declaration follows it in the same breath, because a prompt naming a leg
    // the query does not have is `DEF-950` and a leg no prompt names is
    // hard-won law 2 wearing a search box.
    searchFields: ["case_no", "customer", "account_no", "address", "meter_no"],
    // ✅ **B14 rule 19's prompt is WIRED (CR-041 task 2).** It was "OWED" here
    // for two days because the lane that wrote this config could not edit the
    // catalogues — and the locale lane then ADDED the key, in all eleven
    // languages, and nothing ever pointed a screen at it. Hard-won law 2 exactly:
    // built is not wired, and the copy sat translated and unreachable while the
    // box said "Search this list".
    // The sentence is B18 §5.8.2's own, which `disconnect_reads.SEARCH_HINT`
    // also serves verbatim, so the drawn prompt and the served hint agree.
    searchPlaceholder: "customers.disconnects.list.searchPlaceholder",
    // ⚠ NO SORT — see §5 of this file's header. The order is the server's and
    // is account number, deliberately not urgency.
    // ── `BR-CUS-1046` (PO 2026-09-10, EXTENDED 2026-09-12) ──────────────────
    // *"It should always sort it by the creation order. The new newly created
    // entries should always show on the top."* The name is the SERVER's sort
    // name; `created` orders `created_at DESC, id DESC`.
    //
    // ⚠ **`created` IS NOT A COLUMN ON THIS TABLE, AND THAT IS DELIBERATE.**
    // Neither the blueprint nor B18 draws a Created column here, and the skill's
    // §2.5 is explicit that an absence is a decision: *say so, do not add it*.
    // So no header carries the glyph while the list is on its default, and the
    // sentence under the pager is what states the ordering — which is the
    // mechanism this screen already used for exactly that job.
    // ⚠ **THIS TAB OPENED ON `account_no` ASCENDING**, and said so under its
    // pager. Sortable now, so the alphabet is one click. The new default is not a
    // claim about URGENCY — §3's segment precedence is still unruled and this
    // lane does not rank a ladder against a protection.
    defaultSort: { sort: "created", dir: "desc" },
    columns: [
      {
        // ⚠ **CR-039 WAVE D TASK 16 — B18 §5.8.2 DRAWS EIGHT COLUMNS AND THIS
        // IS A NINTH.** The design's eight follow it unchanged; this one is
        // the CR's finding 5 made reachable: *"A clerk cannot quote a
        // reference."* The divergence is stamped here and in
        // `disconnect_reads.COLUMNS`.
        //
        // ⚠ **AMENDED 2026-08-27 — "an ABSENCE on every row today" WAS TRUE FOR
        // A FEW HOURS.** `OQ-427` closed on the PO's *"it needs its own
        // series"*, so a case opened on a re-seeded tenant prints
        // `DSC-26-0001` onwards here, through the same cell and with no change
        // to this file.
        //
        // ⛔ **BOTH ABSENCES REMAIN REACHABLE AND THE CELL STILL RENDERS THE
        // SERVER'S OWN SENTENCE RATHER THAN ONE OF ITS OWN.** `OQ-427` on a
        // real case with no number — a host provisioned before the ruling holds
        // no series row until it is re-seeded — and `no_case_opened` on §5.8.6's
        // three HELD rows, which are here for a protection and never entered
        // the ladder. Merging those two into one dash would tell a clerk
        // numbering is broken on a row where nothing was ever opened.
        key: "reference",
        // ⚠ **`Case #`, NOT `Reference` — `CR-125-BRC07`.** p142 heads this
        // column `CASE #` and every row under it reads `DSC-26-0003`, which is
        // what a clerk quotes down a telephone. *Reference* was this lane's own
        // word for it. The KEY did not move, so no catalogue loses a string.
        // B14 rule 31 is untouched: `case_no` is the case's SERIES number, not
        // its database id, and the id is still nowhere on this screen.
        label: t("customers.disconnects.col.reference", { defaultValue: "Case #" }),
        // ⛔ **WAS `RecordNumberCell`, WHICH PRINTS THE SERVER'S WHOLE
        //    SENTENCE — `DEF-CUS-6744`.** 22 words in a table cell, on every
        //    row that is here for a protection, rendering the row **277px
        //    tall** against a normal row's 80px. Measured in Chromium, not
        //    eyeballed. B14 rule 33 puts rationale at ZERO words on screen and
        //    says it is REMOVED rather than shortened.
        //
        // ⚠ **THE SHARED COMPONENT IS DELIBERATELY UNCHANGED.** Four screens
        //    mount it and three are other lanes'; changing it would have
        //    redrawn Transfers, Move-outs and Move-ins in this commit. The same
        //    paragraph is still on two of them and is REPORTED, not fixed here.
        cell: (row) => (
          <CaseNumberCell number={row.case_no} unavailable={row.case_no_unavailable} />
        ),
      },
      {
        key: "account_no",
        // `BR-CUS-1046` — SORTABLE, and the key IS the server's sort name.
        sortable: true,
        label: t("customers.disconnects.col.account", { defaultValue: "Account" }),
        identity: true,
        cell: (row) =>
          cells.account !== undefined ? (
            cells.account(row)
          ) : (
            <span className="tabular-nums">{row.account_no}</span>
          ),
      },
      {
        key: "customer",
        label: t("customers.disconnects.col.customer", { defaultValue: "Customer" }),
        // ⚠ THE NAME IS A FACT ABOUT THE ROW AND NEVER A CLAIM ABOUT WHO IS
        // BEING CHASED (OQ-366). The account shown is the one the debt was
        // measured on; `subject` is null on every row the server sends.
        cell: (row) =>
          row.customer === null || row.customer === "" ? (
            <span aria-hidden="true">—</span>
          ) : (
            <span>{row.customer}</span>
          ),
      },
      {
        key: "address",
        label: t("customers.disconnects.col.address", { defaultValue: "Address" }),
        cell: (row) =>
          row.address === null || row.address === "" ? (
            <span aria-hidden="true">—</span>
          ) : (
            <span>{row.address}</span>
          ),
      },
      {
        key: "owed",
        label: t("customers.disconnects.col.owed", { defaultValue: "Owed" }),
        numeric: true,
        cell: cells.owed,
      },
      {
        key: "tier",
        label: t("customers.disconnects.col.tier", { defaultValue: "Tier" }),
        cell: cells.tier,
      },
      {
        key: "cut_date",
        label: t("customers.disconnects.col.cutDate", { defaultValue: "Cut date" }),
        cell: cells.cutDate,
      },
      {
        // ══════════════════════════════════════════════════════════════════
        // `DEF-CUS-6745` — OFF BY DEFAULT, AND STILL IN THE CHOOSER
        // ══════════════════════════════════════════════════════════════════
        // ⛔ **THIS COLUMN IS 242px WIDE AND IT PUT THE TABLE PAST THE
        //    VIEWPORT.** Ten columns came to 1453px inside a window with no
        //    horizontal scroll container, so the ACTIONS header — and the only
        //    row action on this screen — was CLIPPED: by 13px at 1440 and by
        //    **173px at 1280**, where a clerk could not reach the eye at all.
        //
        // ⚠ **THE DRAWING AND THE BLUEPRINT DISAGREE HERE AND THIS IS THE
        //    ANSWER THAT KEEPS BOTH.** p142 draws `LAST NOTICE`; the redesign
        //    drawing does not, and draws a column chooser instead. Deleting the
        //    column would overrule the blueprint on its own layout; leaving it
        //    on keeps the table off the screen. `defaultVisible: false` does
        //    neither: the column EXISTS, it is listed in the `▦` panel, and one
        //    click brings it back — which is what a chooser is for.
        //
        // ⚠ **NOTHING ELSE ABOUT THE COLUMN MOVED.** It still renders two facts
        //    and no delivery state (TC-DSC-6): there is still no map from
        //    `emailed`/`posted`/`certified sent`/`certified signed` to a label
        //    anywhere in this file, which is the checkable form of B18's own
        //    warning and is asserted by a case.
        key: "last_notice",
        defaultVisible: false,
        label: t("customers.disconnects.col.lastNotice", { defaultValue: "Last notice" }),
        cell: cells.lastNotice,
      },
      {
        key: "state",
        label: t("customers.disconnects.col.state", { defaultValue: "State" }),
        cell: cells.state,
      },
      {
        // ══════════════════════════════════════════════════════════════════
        // `↗ Open` — THE HOLD THAT EXPIRED, RELEASED IN THE SAME BREATH
        // ══════════════════════════════════════════════════════════════════
        // p142 draws this action on every row and p143 draws what it opens at
        // `/brazosbend/disconnects/dsc-26-0003`. Both pages carried the
        // blueprint's own caption *"no disconnect case page exists"*, so this
        // lane OMITTED the control — hard-won law 2's mirror: a live control
        // onto a screen that is not there is worse than no control.
        //
        // **`DisconnectRecordPage` landed in `4ff860296` and the hold is over.**
        // Landing a screen and releasing the thing that pointed at it are two
        // acts and only the first feels like the work; this is the second one.
        //
        // ⚠ **B14 RULE 15 BEATS THE DRAWN BUTTON, AND THAT IS RULE 38's SPLIT.**
        // p142 draws a bordered `↗ Open`; rule 15 says a row action is an
        // UNLABELLED ICON with a tooltip, max two visible. Where a drawing and
        // our UI rules disagree about how a control is BUILT, the UI rules win —
        // a labelled button here would change every table in the product on one
        // screen's authority. WHAT the cell contains is still the drawing's, and
        // the drawing says: one action, open the case.
        //
        // ⚠ **A ROW WITH NO CASE NUMBER CANNOT OPEN, AND SAYS SO (BR-SHL-025).**
        // The record is addressed by its REFERENCE, so the two absences this
        // list already distinguishes both land here: a protection-only row never
        // opened a case, and a case on a tenant with no numbering series has no
        // reference yet. Disabled with the reason, never hidden — a control
        // somebody removed is a rule the clerk has to guess.
        key: "actions",
        label: t("customers.disconnects.col.actions", { defaultValue: "Actions" }),
        cell: cells.actions,
      },
    ],
    // ── CR-045 wave G · `DEF-1702` — STATE, and state only ────────────────
    // ⚠ **THE DIMENSION IS DECLARED HERE; THE OPTIONS ARE NOT.**
    // `parseTableParams`/`serializeTableParams` read only `filter.name`, which
    // is what makes `?f.state=cut` survive a reload (BR-SHL-011), and the name
    // is a static capability of this screen. The VALUES are the server's and
    // arrive on the response, so this call passes no states; the panel is
    // handed `disconnectFilterGroups(listQuery.data?.states, …)` at render.
    filters: disconnectFilterGroups(undefined, t),
  };
}

export function disconnectsQueryKey(state: TableRequestState): readonly unknown[] {
  // `state.filters` is IN THE KEY. Without it react-query answers the filtered
  // request from the unfiltered page already in cache and the list does not
  // move — a filter that looks broken while the request was never made.
  return [
    "disconnects",
    DISCONNECT_SEGMENT_ALL,
    state.q,
    state.page,
    state.per,
    state.filters,
    // ⚠ **`state.sort` AND `state.dir` ARE IN THE KEY FOR THE REASON
    // `state.filters` IS (`BR-CUS-1046`).** Without them react-query answers a
    // re-sorted request from the previously-sorted page already in cache: the
    // header's arrow flips, the rows do not move, and no request is ever made.
    // That is `state.filters`' own defect one column along.
    state.sort,
    state.dir,
  ];
}

/**
 * B18 §5.8.1's five tiles — 4 · 2 · 3 · 1 · 1 over §5.8.6's nine rows.
 *
 * ⚠ **THE TILES OVERLAP BY DESIGN** (`AT NOTICE`'s four include the two
 * scheduled rows `DUE TO CUT THIS WEEK` also counts; 4+2+3+1+1 = 11 over nine
 * rows). A KPI is a count and may double-count; a SEGMENT is a place a row
 * lives, which is why the segments are the thing OQ-374 blocks and these are
 * not.
 *
 * ⚠ **`CUT, AWAITING PAYMENT` DOES NOT PRINT ITS DRAWN CAPTION.** §5.8.1 writes
 * *"still accruing base charges"* and calls it *"a money statement: the meter
 * is off and the base charge is not"*. **SUPERSEDED (BR-CUS-103, PO 2026-08-25
 * closing OQ-380, answer "no" → base charges STOP at the cut).**
 *
 * ⚠ **THIS COMMENT SAID SOMETHING ELSE UNTIL 2026-08-25 AND IT WAS TRUE WHEN
 * WRITTEN** — *"Whether a cut account keeps accruing is BILLING's behaviour and
 * no rule in this packet states it"*. A rule states it now, so the tile is no
 * longer withholding an UNVERIFIED caption: it is withholding a caption the PO
 * ruled FALSE (DEF-716). The old sentence is kept rather than deleted so a
 * reader holding r10 can find it and be told it no longer binds.
 *
 * The tile therefore says what the figure IS — a count of cases in the cut
 * state — and the server's reason rides in the title.
 *
 * ⚠ **AND IT STOPS THERE ON PURPOSE.** It makes no claim about what those
 * customers OWE: the $75.00 reconnection fee still does not reach the balance
 * (DEF-708, open), so a caption implying a cut account's balance is complete
 * would put a new false statement where the old one was.
 */
export function disconnectsKpis(
  payload: DisconnectList | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
): KpiTile[] {
  const kpis = payload?.kpis;
  // ── THE DRAWN ORDER AND THE DRAWN WORDS · the 2026-09-25 redesign ────────
  // The drawing draws five tiles: `NOTIFIED · SCHEDULED · OFF · PAID · HELD`,
  // in that order, each over a caption of three or four words.
  //
  // ⚠ **THE ORDER MOVED AND THE FIGURES DID NOT.** This strip read at-notice ·
  // due-to-cut · cut-awaiting · **on-hold** · reconnections, from p142; the
  // drawing puts HELD last and PAID fourth. Every tile is the SAME served
  // number it was before — `at_notice`, `due_to_cut_this_week`,
  // `cut_awaiting_payment`, `reconnections_due`, `on_hold_protected`. Nothing
  // is re-derived on this screen; there is one calendar in this product.
  //
  // ⚠ **THE WORDS ARE THE STATE COLUMN'S WORDS, WHICH IS THE POINT.** A tile
  // reading `NOTIFIED` over a column reading `At notice` was two vocabularies
  // for one fact; the six clerk words are now the only set on this screen, so a
  // clerk who reads a tile can find its rows by their badge.
  //
  // ⚠ **EVERY LABEL IS ONE WORD AND EVERY CAPTION IS A FACT UNDER SIX** (B14
  // rule 33 — a LABEL gets three words, a FACT six).
  return [
    {
      id: "at-notice",
      label: t("customers.disconnects.kpi.atNotice", { defaultValue: "Notified" }),
      value: kpis?.at_notice ?? 0,
      detail: t("customers.disconnects.kpi.atNoticeDetail", {
        defaultValue: "Ladder running",
      }),
    },
    {
      id: "due-to-cut",
      label: t("customers.disconnects.kpi.dueToCut", { defaultValue: "Scheduled" }),
      value: kpis?.due_to_cut_this_week ?? 0,
      // ⚠ **THE CAPTION STATES WHAT THE FIGURE IS, AND THAT IS UNCHANGED.**
      // `_within_the_week` is seven days forward, inclusive at both ends, so a
      // cut booked for Friday is in this figure on Monday. p142 captions the
      // tile *"the date has arrived"* and the drawing *"Within seven days"* —
      // the drawing is the one that is TRUE of the served number, which is why
      // it can be printed verbatim where p142's could not (`DEF-716`).
      detail: t("customers.disconnects.kpi.dueToCutDetail", {
        defaultValue: "Within seven days",
      }),
    },
    {
      id: "cut-awaiting",
      label: t("customers.disconnects.kpi.cutAwaiting", { defaultValue: "Off" }),
      value: kpis?.cut_awaiting_payment ?? 0,
      detail: (
        <span
          title={disconnectAbsenceCopy(kpis?.cut_awaiting_payment_unavailable, t)} /* DEF-742 */
          data-tracks={kpis?.cut_awaiting_payment_unavailable.br_ref}
        >
          {/* The drawing's caption, and it is true at every value — not
              p142's `nothing disconnected`, which is a statement about the
              drawn ZERO and reads as a contradiction over a figure of 3
              (B14 rule 37: a drawn figure is an illustration). */}
          {t("customers.disconnects.kpi.cutAwaitingDetail", {
            defaultValue: "Service disconnected",
          })}
        </span>
      ),
    },
    {
      id: "reconnections",
      label: t("customers.disconnects.kpi.reconnections", { defaultValue: "Reconnecting" }),
      value: kpis?.reconnections_due ?? 0,
      detail: t("customers.disconnects.kpi.reconnectionsDetail", {
        defaultValue: "Awaiting a visit",
      }),
    },
    {
      id: "on-hold",
      label: t("customers.disconnects.kpi.onHold", { defaultValue: "Held" }),
      value: kpis?.on_hold_protected ?? 0,
      detail: t("customers.disconnects.kpi.onHoldDetail", {
        defaultValue: "A protection is in force",
      }),
    },
  ];
}

export interface DisconnectsTabProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
  /**
   * ⚠ **`CR-125-BRC07` — HOW THE HEAD'S THIRD FRAGMENT GETS ITS NUMBER, AND IT
   * IS `DEF-CUS-5953`'s OWN REMEDY IN ITS OWN WORDS:** *"each tab publishing
   * its SERVED `kpis.open` to the head, the way this screen publishes its
   * breadcrumb leaf."*
   *
   * p142 draws `10 tabs · Disconnects · 3 open cases`. `AccountsListPage` owns
   * that line and serves TEN tabs, so it cannot ask for the number itself: a
   * second read from the head would be a SECOND DEFINITION of *open* on one
   * screen — the hazard the PO ruled on for the Move-outs tile on 2026-09-19,
   * choosing *leave it*, because a figure that contradicts its own caption is
   * worse than a missing one.
   *
   * So the tab, which already holds the response, hands up the figure the
   * SERVER computed and nothing is derived twice. `undefined` until the first
   * response answers, and the head then OMITS the fragment rather than
   * printing a zero it was never told.
   *
   * Optional: the other nine tabs do not publish one yet, so nothing else
   * changes and no sibling file is touched.
   */
  onOpenCaseCount?: (count: number | undefined) => void;
}

export function DisconnectsTab(props: DisconnectsTabProps) {
  // ⚠ **THE DISCARD DIALOG'S STATE LIVES HERE AND NOT IN THE ROW
  // (`DEF-CUS-6011`).** `DataTable` rebuilds `columnDefs` on every render, so
  // `flexRender` hands React a new component type each time and the whole cell
  // subtree is unmounted and remounted — **a `useState` inside a cell is
  // destroyed by the very re-render that setting it caused.** The first draft
  // kept `confirming` in `ParkedDraftActions`, and the dialog never opened, in
  // the browser or under vitest. `DEF-CUS-5994`.
  const [discarding, setDiscarding] = useState<ParkedDiscardTarget | null>(null);
  const { t } = useTranslation();
  const translate = (key: string, params?: Record<string, unknown>): string => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props);

  const config = useMemo(
    () =>
      disconnectsTableConfig(translate, {
        // Record links (PO 2026-10-19): the account number opens the account.
        account: (row) => (
          <InlineLinkTo
            className="tabular-nums"
            to={tenantPath(accountDetailPath(row.account_id))}
          >
            {row.account_no}
          </InlineLinkTo>
        ),
        owed: (row) => <OwedCell owed={row.owed} t={t} />,
        tier: (row) => <TierCell tier={row.tier} t={translate} />,
        // §5.8.2: *"`CUT DATE` renders in the accent when it is this week"*.
        // The accent is a FACT about the date and the SERVER decides it —
        // `_within_the_week` is inclusive at both ends and FORWARD-LOOKING
        // ONLY, so until 2026-09-20 a cut booked for last Monday rendered in
        // exactly the same plain text as one booked for next month. That is
        // the PO's own sentence, in a table cell.
        //
        // ⚠ **BOTH FACTS ARE THE SERVER'S AND NEITHER IS RE-DERIVED HERE** —
        // one calendar in this product. `CutDateCell` §2 has the reasoning.
        cutDate: (row) => (
          <CutDateCell
            hasDate={row.cut_date !== null}
            isThisWeek={row.cut_date_is_this_week}
            due={row.cut_due}
            t={translate}
            date={
              row.cut_date === null ? null : (
                <DateCell value={row.cut_date} timeZone={timeZone} dateFormat={dateFormat} />
              )
            }
          />
        ),
        lastNotice: (row) => (
          <LastNoticeCell
            notice={row.last_notice}
            t={translate}
            timeZone={timeZone}
            dateFormat={dateFormat}
          />
        ),
        state: (row) =>
          // ⚠ **REQUIREMENT 1 OF `CR-035` AMENDMENT 1, MET ON THE ROW INSTEAD
          // OF ABOVE THE TABLE (`DEF-CUS-5994`).** *"A clerk cannot mistake a
          // draft for a job that happened"* was the pinned panel's dashed
          // border and its own block; the panel is gone and the requirement is
          // not. **The two controls ride in this cell rather than in a new
          // ACTIONS column**, because this table's columns are the drawing's
          // and a column nobody drew is not invented here — B14 rule 38 gives
          // the UI rules the FORM and leaves what a screen CONTAINS to the
          // blueprint. The state cell is where a row already declares what
          // kind of thing it is, which is exactly what a draft needs to say.
          (row.park_id ?? "") !== "" ? (
            <span className="flex flex-col items-start gap-1" data-disconnect-draft={row.park_id}>
              <ParkedBadge parked={(row.waiting_on ?? "") !== ""} t={translate} />
              <ParkedWhyCell row={row} timeZone={timeZone} dateFormat={dateFormat} />
              <ParkedDraftActions
                flow="disconnect"
                onDiscard={setDiscarding}
                parkId={String(row.park_id)}
                subjectLabel={row.customer ?? row.account_no ?? ""}
              />
            </span>
          ) : (
            // `DEF-CUS-6747` · `DEF-CUS-6749` — ONE word in the column, the
            // reason beneath it, and the crew's last attendance beneath that.
            // The protection words and the outcome word are resolved HERE,
            // because this file owns this screen's vocabulary; the badge owns
            // the shape. `DisconnectStateBadge` §1 has the reasoning for why
            // this ranks nothing and `OQ-374` is untouched.
            <DisconnectStateBadge
              stored={row.state.stored}
              held={row.state.held_by.map((kind) =>
                translate(`customers.disconnects.protection.${kind}`, {
                  defaultValue: PROTECTION_LABELS[kind] ?? kind,
                }),
              )}
              storedLabel={
                row.state.stored === null
                  ? ""
                  : disconnectStateLabel(row.state.stored, translate)
              }
              heldLabel={translate("customers.disconnects.state.on_hold", {
                defaultValue: "Held",
              })}
              visit={row.visit ?? null}
              visitLabel={
                row.visit == null
                  ? null
                  : translate("customers.disconnects.visit.seen", {
                      defaultValue: "Visited",
                    }) +
                    " · " +
                    translate(`customers.disconnects.visit.${row.visit.outcome}`, {
                      defaultValue: VISIT_OUTCOME_LABELS[row.visit.outcome] ?? row.visit.outcome,
                    })
              }
              visitDate={
                row.visit == null ? null : (
                  <DateCell
                    value={row.visit.visited_on}
                    timeZone={timeZone}
                    dateFormat={dateFormat}
                  />
                )
              }
              title={disconnectAbsenceCopy(row.state.unavailable, translate)}
            />
          ),
        // ── `↗ Open` — THE HOLD RELEASED, AND ITS DESTINATION IMPORTED ──────
        // `disconnectRecordPath` is the record lane's OWN helper. Retyping
        // `/disconnects/${ref}` here would buy two spellings of one address,
        // which is the same defect that let this lane's hold pass over a live
        // screen one level up (`DEF-CUS-6042`).
        // ══════════════════════════════════════════════════════════════════
        // `DEF-CUS-6748` — THE EYE OPENS SOMETHING ON EVERY ROW
        // ══════════════════════════════════════════════════════════════════
        // ⛔ **IT WAS DISABLED ON EVERY PROTECTION-ONLY ROW**, reading *"This
        //    row has no case reference."* — true, correct under `BR-SHL-025`,
        //    and it left two of six rows with NO working control at all. That
        //    is hard-won law 2's mirror: a live screen behind a dead control,
        //    and the refusal being TRUE is exactly what hid it. `BR-SHL-025`
        //    asks whether a refusal is STATED; nothing asked whether the row
        //    had any door at all.
        //
        // ⚠ **THE PRODUCT OWNER WAS ASKED AND HAS NOT ANSWERED — BOTH OPTIONS
        //    ARE STILL OPEN.** Either those rows leave this list, or the eye
        //    opens the account. **This lane took the second, as the LESS
        //    DESTRUCTIVE of the two**, and it is a judgment recorded in the
        //    decision log rather than a ruling: dropping the rows would remove
        //    a held account from the one screen that says a utility may not cut
        //    it, and would silently change the HELD tile's meaning against the
        //    list beneath it. Adding a door removes nothing and is one line to
        //    reverse.
        //
        // ⚠ **A ROW WITH A CASE STILL OPENS THE CASE.** The destination is the
        //    row's OWN best answer rather than one address for all rows: a case
        //    row opens `/disconnects/{case}` through the record lane's own
        //    helper, and a protection row opens the account it is about. Both
        //    are live screens; neither is a guess.
        //
        // ⚠ **B14 rule 31 IS UNTOUCHED.** `account_id` is in the ADDRESS, never
        //    a visible value — the same thing `AccountDetailPage` already does
        //    for a linked account, which shows the number and links by id.
        actions: (row) => (
          <RowActions>
            <RowActionLink
              label={
                (row.case_no ?? "") === ""
                  ? t("customers.disconnects.action.openAccount", {
                      defaultValue: "Open the account",
                    })
                  : t("customers.disconnects.action.open", {
                      defaultValue: "Open the case",
                    })
              }
              icon={<EyeIcon />}
              // ⚠ **NO `reason`, AND THAT IS THE FIX.** The control is live on
              // every row this list can serve; there is no longer a class of
              // row that is offered nothing.
              reason={null}
              to={
                (row.case_no ?? "") === ""
                  ? tenantPath(accountDetailPath(row.account_id).slice(1))
                  : tenantPath(disconnectRecordPath(String(row.case_no)).slice(1))
              }
            />
          </RowActions>
        ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, timeZone, dateFormat],
  );

  // DEF-664 — the table state is THIS COMPONENT'S; the query string belongs to
  // the Accounts page. See `NewConnectsTab` §1 for the whole rule.
  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  const listQuery = useQuery({
    queryKey: disconnectsQueryKey(state),
    queryFn: () =>
      listDisconnects(
        {
          q: state.q,
          page: state.page,
          per: state.per,
          filters: state.filters,
          // `BR-CUS-1046` — the clerk's chosen column reaches the `ORDER BY`.
          sort: state.sort,
          dir: state.dir,
        },
        client,
      ),
  });

  // ⚠ **IN AN EFFECT, NOT IN THE RENDER.** Calling the parent's setter while
  // this component is rendering is a React warning at best and a render loop at
  // worst; the effect fires after commit and only when the served number
  // actually moves. The count is the SERVER's `open_case_count` and is never
  // `rows.length` or `total` — see the field's own note on `DisconnectList`.
  const openCaseCount = listQuery.data?.open_case_count;
  const publishOpenCaseCount = props.onOpenCaseCount;
  useEffect(() => {
    publishOpenCaseCount?.(openCaseCount);
  }, [publishOpenCaseCount, openCaseCount]);

  return (
    <div data-embedded="" data-screen={DISCONNECTS_TABLE_SCREEN}>
      {/* `DEF-CUS-5994` — the parked draft's DISCARD confirmation, mounted ONCE
          and ABOVE the table. It is here rather than in the row because a
          `DataTable` cell is unmounted and remounted on every render
          (`DEF-CUS-6011`), so state set by a click inside one does not survive
          the render that click causes. It draws nothing until a clerk asks. */}
      <ParkedDiscardDialog
        flow="disconnect"
        target={discarding}
        onClose={() => setDiscarding(null)}
        client={client}
      />
      <KPIStrip kpis={disconnectsKpis(listQuery.data, translate)} loading={listQuery.isPending} />

      {/* ⛔ **NO `downloadSlot`, AND THIS IS THE STATED ABSENCE CR-041 TASK 4
          ASKS FOR — NOT A FORGOTTEN PROP (DEF-1005).**

          `POST /exports` resolves only the resources a module REGISTERS, and an
          unregistered one is a plain 404, never a guessed queryset. Nothing
          registers `disconnects`, so BR-SHL-010 keeps the capability unrendered:
          an undeclared capability is not drawn. Not drawn DISABLED either —
          BR-SHL-025 is for a control this ROLE cannot use, not one the PRODUCT
          does not have.

          EP-CUS-08's S90 capability row says the same in one word — **Export: NONE**.

          ⚠ A DOWNLOAD BUTTON HERE WOULD BE A CONTROL WIRED TO A 404 — hard-won
          law 2, which this repo has four instances of from a single day. The
          capability is OWED and unruled, and **DEF-1005 carries it** so this
          sentence expires when the row does rather than outliving its reason
          (DEF-445). */}
      <DataTable<DisconnectRow>
        config={config}
        // ── CR-045 wave G · `DEF-1702` — THE `+ Filter ▾` PANEL, AND THE
        //    SEGMENT STRIP THAT USED TO SIT HERE IS GONE ───────────────────
        //
        // ⚠ **WHAT WAS REMOVED AND WHY, BECAUSE IT WAS DELIBERATE WORK AND NOT
        //    LEFTOVER.** This slot held `<WorklistSegments … onSelect={() =>
        //    undefined}>` — B18 §5.8.2's six tabs, five of them permanently
        //    `supported: false` and the sixth permanently the active one. It
        //    could not be operated: there was no state for `onSelect` to write
        //    and nothing for a click to change. **A row of buttons that cannot
        //    be pressed is a STATEMENT, and it was being drawn in the slot B14
        //    rule 12 reserves for the FILTER** — so this screen read as filtered
        //    in a screenshot and was scored as having a filter control twice
        //    while having none (`DEF-1702`'s undercount, both times).
        //
        // ⚠ **THE RULE THAT DECIDES IT IS THE ONE THIS FILE ALREADY APPLIES
        //    FOUR LINES UP.** The `downloadSlot` comment above states it
        //    exactly: *"Not drawn DISABLED either — BR-SHL-025 is for a control
        //    this ROLE cannot use, not one the PRODUCT does not have."* The
        //    segments are a capability the PRODUCT does not have — no rule ranks
        //    them (`OQ-374`) — so BR-SHL-010 keeps them undrawn, on the same
        //    reasoning, in the same file. Until now this file argued both ways.
        //
        // ⚠ **NOTHING ABOUT OQ-374 IS DECIDED HERE.** `payload.segments` is
        //    still served with every `supported`/`unavailable` field intact, the
        //    route still refuses every segment but `all`, and OQ-374 stays OPEN
        //    with the strip as its stated remedy. When it closes, the strip
        //    comes back — as a control that works.
        //
        // The panel's groups are built from the RESPONSE, so the options are
        // the server's vocabulary and never a copy of it (BR-SHL-010);
        // `offerableFilters` drops the group entirely before the first response
        // rather than drawing a legend over nothing (`DEF-782`).
        // ══════════════════════════════════════════════════════════════════
        // ONE FILTER LIST, AND THE QUICK-VIEW CHIPS ARE GONE (PO, 2026-09-25)
        // ══════════════════════════════════════════════════════════════════
        // ⛔ **WHAT WAS REMOVED AND WHY, BECAUSE IT WAS DELIBERATE WORK.** This
        //    slot held two chip rows — `DisconnectStateChips` (p142's `Due to
        //    cut · At notice · Reconnections · All`, with the note *"A held
        //    case still appears."*) and `DisconnectDueChips` (`Due now ·
        //    Overdue`) — in FRONT of the `+ Filter ▾` panel. Both wrote the
        //    same `f.state` / `f.due` the panel writes, so the screen offered
        //    **the same things twice** and a clerk had two places to answer one
        //    question. The redesign drawing draws the toolbar as search, `All`,
        //    `+ Filter` and the column chooser, and nothing else.
        //
        // ⚠ **NO FILTER CAPABILITY WAS LOST.** Every value the chips offered is
        //    an option in the panel, from the same served vocabulary — the
        //    chips never had a source of their own. `All` is still here: it is
        //    `FilterBar`'s own chip, inverted while nothing is applied and the
        //    clear-all the moment something is, which is what the drawing draws.
        //
        // ⚠ **`DisconnectStateChips.tsx` AND `DisconnectDueChips.tsx` ARE LEFT
        //    ON DISK AND ARE NOW IMPORTED BY NOTHING BUT A TEST.** Deleting
        //    them is a separate act with its own blast radius
        //    (`DisconnectsListDrawing.dom.test.tsx` imports both), and this
        //    lane REPORTS the orphan rather than reaching past its own fix —
        //    an unimported component is dead weight, not a live defect.
        //
        // ⚠ **THE `note` THE CHIPS CARRIED IS NOT RE-HOMED, DELIBERATELY.** *"A
        //    held case still appears."* is RATIONALE — why the product behaves
        //    as it does — and B14 rule 33 puts that at ZERO words on screen,
        //    removed rather than shortened. The row it explains says it better:
        //    a held case now carries the `Held` badge and its reason.
        //
        // The panel's groups are built from the RESPONSE, so the options are
        // the server's vocabulary and never a copy of it (BR-SHL-010);
        // `offerableFilters` drops the group entirely before the first response
        // rather than drawing a legend over nothing (`DEF-782`).
        filterBarSlot={
          <FilterBar
            filters={offerableFilters(
              disconnectFilterGroups(listQuery.data?.states, translate, listQuery.data?.dues),
            )}
            state={state}
            onStateChange={setState}
          />
        }
        state={state}
        onStateChange={setState}
        rows={rowsOf<DisconnectRow>(listQuery.data)}
        totalRows={totalOf(listQuery.data)}
        loading={listQuery.isPending}
        error={
          listQuery.isError
            ? {
                reason: t("customers.disconnects.list.loadFailed", {
                  defaultValue: "The disconnects could not be loaded.",
                }),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        empty={{
          title: t("customers.disconnects.list.emptyTitle", {
            defaultValue: "Nobody is on the ladder",
          }),
          helper: t("customers.disconnects.list.emptyHelper", {
            defaultValue:
              "Accounts appear here once a reminder goes out, and leave on their own when the customer pays or agrees a payment plan.",
          }),
          ctaLabel: t("customers.disconnects.action.new", { defaultValue: "Start a disconnect" }),
          // ⚠ **WAS DISABLED, AND IS LIVE FROM 2026-08-25 (lane W7WIZ).** The
          // reason it carried — *"the disconnect flow is not built yet"*, plus
          // the true observation that a live button onto nothing is bad and a
          // DANGER one is worse — held while `DSC-02` had no route. It does
          // now. ⚠ And the flow it opens SCHEDULES a cut; it never performs
          // one, so this button is not itself the destructive act.
          onCta: () => navigate(tenantPath(DISCONNECT_WIZARD_ROUTE)),
        }}
      />

      <p className="mt-2 text-sm text-neutral-700">
        {t("customers.disconnects.list.sortFootnote")}
      </p>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W7 task 7.11 (S90, frontend half) · B18 §5.8.1 · §5.8.2 ·
//         §5.8.3 · §5.8.5 · §5.8.6 · `apps/customers/disconnect_reads.py` ·
//         `GET /disconnects` · OQ-374 (OPEN) · OQ-366 (OPEN) · DEF-127 ·
//         DEF-664 (the embedded rule) · hard-won law 8 (no story owns S90)
// generated: 2026-08-25 by lane F-TABS (the frontend half of three worklists)
// checklist: A=n/a(no backend half in this lane) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions: E2 **the exception that stood here is SUPERSEDED BY CR-045 WAVE G
//         (2026-08-27, `DEF-1702`) and is kept rather than deleted (hard-won law
//         1).** It read: *"E3 five of six segments are DISABLED WITH THEIR REASON
//         — OQ-374 is OPEN and the screen never calls the route to discover the
//         refusal"*. It was true, and the control it described could not be
//         operated: the sixth segment was the one already active, so
//         `onSelect={() => undefined}` had nothing to write. **The strip is
//         DELETED** — BR-SHL-025 governs a control this ROLE cannot use, not one
//         the PRODUCT does not have, which is the distinction this same trailer
//         already draws for the missing `Export`. **OQ-374 IS STILL OPEN and the
//         second half of the old sentence still holds: the screen never asks for
//         a segment**, and a case asserts it · E3 **the toolbar now carries a
//         REAL `+ Filter ▾`** — `f.state` over the STORED case states
//         (`DISCONNECT_FILTER_STATES`), applied by the server before paging. It
//         is not the six segments in another shape: `on_hold` is computed from
//         the account's protections and is not offered · E3 **no delivery state is rendered anywhere**: there is no
//         map from `emailed`/`posted`/`certified sent`/`certified signed` to a
//         label in this file, which is the checkable form of B18's own warning
//         (TC-DSC-6) · E3 `OWED` renders the server's reason when the ledger
//         reading failed and never `$0.00` (DEF-127) — and `A-11507`'s REAL
//         `$0.00` is on this tab, so the two must look different · E3 the TIER
//         cell serves every applicable chip and flags ambiguity rather than
//         picking one (OQ-374) · E3 no primary, no row action: the S22 modal
//         and the five-step danger-tier flow have no route (law 2) · E3 no
//         sortable column: the server takes no `sort`, and ranking the
//         urgencies is the same unruled precedence · E3 OQ-366 — no row names a
//         chased party; the CUSTOMER column states the account the debt was
//         measured on · E3 no story owns S90 (law 8) — OWED
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
