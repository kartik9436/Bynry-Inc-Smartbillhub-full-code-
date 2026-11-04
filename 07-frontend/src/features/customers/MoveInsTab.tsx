// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W5 — **the MOVE-INS tab, FRONTEND half.** The PO reported
//           every Accounts tab empty; five have since been built and this is one
//           of the last two. Until now it rendered `<ArrivesWith … tracks=
//           "OQ-350" />` — a panel saying the list *"arrives later"* — which is
//           hard-won law 2: an honest note that adds up to a screen a user
//           experiences as broken.
// Rules:    BR-CUS-018 (the draft window this list IS) · BR-CUS-022 (an
//           occupying account without a start date could never be billed —
//           which is why `waiting` is a blockage and not a label) · BR-CUS-023
//           (the deposit is a LOOKUP, so its SENTENCE has no store) ·
//           BR-CUS-024 (carry-forward mechanics PROPOSED) · BR-CUS-080 (the
//           SR→child link is TEXT) · BR-SHL-010 (an undeclared capability is
//           not rendered) · BR-SHL-011 (this list owns NO query string —
//           DEF-664) · BR-SHL-012 · BR-SHL-025 (a control that cannot be used
//           renders DISABLED WITH ITS REASON) · CLAUDE.md hard rule 2 (money
//           DISPLAYS at 2 dp — the SERVER rounds, this file never does) ·
//           B14 rules 5, 12, 16, 17, 19, 20, 21
// Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.5.1 (the five
//           tiles) · §5.5.2 (the eight columns, the segments, the footnote) ·
//           §5.5.7 (the five drawn rows)
// Tests:    07-frontend/src/features/customers/MoveInsTab.test.tsx
// Impacts:  AccountsListPage.tsx (the mount + `ACCOUNTS_BUILT_TABS`) ·
//           06-backend `GET /move-ins` (REPORTED — `api.py` is another lane's)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · WHAT THIS TAB IS SHOWING, BECAUSE IT IS NOT WHAT B18 DRAWS
// ══════════════════════════════════════════════════════════════════════════
// There is no `move_ins` table. A move-in is the LIFE OF A DRAFT ACCOUNT: it
// begins when `services.create_account` writes a BR-CUS-018 draft — *"never
// billed, derives no occupancy and does not block the unit"* — and it ends when
// `services.activate_account` makes that account occupy its unit. Which is this
// tab's own copy, in code: *"from the day a new occupant is booked in to the
// day their account opens"*.
//
// So a row LEAVES this list when the move-in completes. Two consequences the
// screen has to state rather than let a user infer:
//
//   · **`Done` is not a segment this product can fill.** B18 §5.5.7 draws two
//     `Done` rows; the window closes when the account opens, and no rule sets a
//     retention window for a finished move-in. The segment renders DISABLED
//     with the server's reason.
//   · **`— draft` rows are not here either.** §5.5.2 draws `— draft` in italic
//     where the wizard has not created an account; a draft with no account is a
//     `service_requests` row and lives on the Requests tab. §5.5.7 says so
//     itself — *"the linked request IS the draft"*.
//
// Both are rendered as a note UNDER the table rather than as a page-level
// "what this cannot do yet" panel — the PO deleted three of those from the
// accounts screens on 2026-08-24. These two explain rows a user can COUNT
// against §5.5.7 and against the Requests tab, which is a fact about the
// product rather than a note about our backlog.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · THE DEPOSIT CELL NEVER SAYS `waived`, AND THAT IS THE POINT OF IT
// ══════════════════════════════════════════════════════════════════════════
// §5.5.2 draws DEPOSIT as *"a sentence, not a number alone"* — `waived` · `on
// first bill` · `carried $153.50` · `collected $150.00` · `—`. Which of those
// applies is a DISPOSITION and **no column records one**: `deposit_on_file`
// holds an amount and is a REFUSED field on both doors that edit an account,
// because BR-CUS-023 makes it a lookup.
//
// So a deposit nobody recorded and a deposit deliberately waived hold the same
// value, and printing `waived` for a zero states a decision nobody made. This
// screen renders the AMOUNT the server read and the REASON the sentence is
// missing, and it branches on the server's `recorded` boolean rather than on
// the number — because `0.00` is a real amount and `—` would hide it.
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · WHAT §5.5.2 DRAWS THAT THIS DOES NOT, EACH WITH ITS REASON
// ══════════════════════════════════════════════════════════════════════════
//   * **The five-segment STEP bar.** The server serves the DENOMINATOR and no
//     numerator — there is no wizard store, so the step a clerk reached is not
//     readable. The cell draws the five segments EMPTY and carries the reason,
//     which is a truer thing than an invented `1 of 5`.
//   * **A row action / the hover *"Completed — opens at the review step"*.**
//     Both reopen the wizard at a step, and there is no step to reopen at.
//     `MoveInWizard` exists but is reached from the UNIT's own page; a row
//     action here would be a link onto a step this product cannot restore.
//   * **A `+ New move-in` primary.** The page header's one primary slot belongs
//     to `AccountsListPage` (B14 rule 4 / BR-SHL-044). The empty state's CTA is
//     drawn DISABLED with that reason (BR-SHL-025).
//   * **A sort control.** `move_ins_queryset` orders by move-in date soonest
//     first and accepts no `sort`, so no column is declared sortable.
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { getTenantServices } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FilterBar, offerableFilters } from "@/components/FilterBar";
import { EyeIcon, PencilIcon, PlayIcon, ReviewIcon } from "@/components/icons";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { MoneyCell } from "@/components/MoneyCell";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { defaultRequestState } from "@/components/tableTypes";
import type {
  TableConfig,
  TableFilterConfig,
  TableRequestState,
} from "@/components/tableTypes";
import { formatQuantity } from "@/components/UnitCell";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { enabledServiceRows } from "@/features/metering/ServicesAvailableField";
import { ServiceTags as ServiceSquares } from "@/features/rating/ratingShared";
import { useTenantPath } from "@/routing/tenantPath";

// `REQUEST_PARAM` is the wizard's own name for *fill me from this request* —
// imported, never restated, so the list's Start and the details view's Start
// cannot drift onto two spellings. Nothing in that file is edited here.
import { REQUEST_PARAM as MOVE_IN_REQUEST_PARAM } from "./MoveInWizard";
import { moveRecordPath } from "./MoveRecordPage";
import { MOVE_IN_WIZARD_ROUTE } from "./moveShared";
// `DEF-CUS-7900` — the ONE builder for `?parked=<id>`; the draft row's Resume
// icon goes through it.
import { resumePath } from "./parkedDrafts";
import { rowsOf, totalOf, worklistFilterParams } from "./worklistEndpoints";
import type { WorklistAbsence, WorklistMoney } from "./worklistEndpoints";

/** The screen id `TableConfig` keys its column preference on.
 *
 *  ⚠ **NO A1 ID AND NO STORY.** A1 allocates S19 to the move-in WIZARD and
 *  nothing to this worklist; `move_reads.py` filed the same finding for the
 *  backend half (hard-won law 8, as S86/S89/S90 each did). The key is namespaced
 *  off the wizard's id so two different tables cannot share one saved column set
 *  (DEF-647's rule), and a real id is OWED. REPORTED, not invented. */
export const MOVE_INS_TABLE_SCREEN = "S19.moveIns";


// ══════════════════════════════════════════════════════════════════════════
// THE SHARED SHAPES — both move tabs answer the SAME envelope, by design
// ══════════════════════════════════════════════════════════════════════════
/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated rather than imported from `worklistEndpoints.ts` so this lane adds
 *  no coupling to a file another lane may be editing — `bankRecEndpoints`' own
 *  rule, and the reason `worklistEndpoints` restated it in the first place. */
export function requireMoveData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/**
 * One drawn state segment, with whether this product can fill it.
 *
 * `drawn` is the field a reader of this payload needs and B18 does not have:
 * `false` means the CODE is this product's own, minted because the data holds a
 * fact the design has no segment for (`due` here, `closed` on the move-outs
 * tab). Nothing on screen may present a minted code as a design segment.
 */
export interface MoveStateSegment {
  code: string;
  label: string;
  drawn: boolean;
  supported: boolean;
  unavailable: WorklistAbsence | null;
}

/** A cell whose figure has no store — the STEP bar on both tabs, and READS. */
export interface MoveAbsentCell {
  unavailable: WorklistAbsence;
}

export interface MoveStepCell extends Omit<MoveAbsentCell, "unavailable"> {
  /**
   * ⚠ **NULLABLE SINCE 2026-09-19, AND THAT IS THE POINT OF THE RULING.** This
   * cell inherited `MoveAbsentCell` — *"a cell whose figure has no store"* —
   * because on both tabs there never was one. An unfinished move-out HAS a
   * step, so its cell carries a number and no reason at all, and a type that
   * demanded a reason would have forced the server to invent one.
   */
  unavailable: WorklistAbsence | null;
  /**
   * The step a clerk actually reached, or `null` where none is stored.
   *
   * ⚠ **THIS COMMENT READ *"⛔ ALWAYS `null`. There is no wizard store"* UNTIL
   * 2026-09-19, AND BOTH HALVES WERE WRONG.** There has been a wizard store
   * since `CR-035`, and since the PO's ruling of that day (`yes` — the
   * Move-outs list shows the move-outs that have not finished yet) an
   * unfinished move-out row carries a real number here. It is still `null` on
   * every closed move-out, every draft account and every pending move-in job,
   * and `unavailable` says which of those it is.
   */
  reached: number | null;
  /** Served so the bar can be drawn with the right number of EMPTY segments.
   *  On the move-outs tab this is BR-SHL-046's SIX and never B18's superseded
   *  four. */
  of: number;
}

/**
 * §5.5.2's READS cell and §5.6.2's FINAL READ cell — ONE shape, both tabs.
 *
 * ⚠ **REWRITTEN 2026-08-26 (CR-038 W9 · DEF-786). Until then this interface
 * said `state: string | null` with the comment "⛔ ALWAYS `null` — customers
 * publishes no metering read seam", and it extended `MoveAbsentCell`, whose
 * `unavailable` is NON-nullable.** Both were true when they were written and
 * both were false the moment `apps/customers/seams.reads_for_unit` landed: the
 * server now derives `taken`/`due` per row, names the meters that are missing,
 * and serves `unavailable: null` on a row it could answer.
 *
 * DEF-786 is what that mismatch cost — *"the new payload reaches the browser
 * and nothing draws it"* — and it is hard-won law 2 in its exact shape: the
 * cell was null-tolerant, so nothing crashed; the guard's declared set was
 * untouched, so nothing went red; the feature simply did not exist on screen.
 *
 * The interface no longer extends `MoveAbsentCell` for a reason worth stating:
 * `unavailable` is nullable HERE and non-nullable THERE, and TypeScript will
 * not let an extending interface widen a member. Sharing the base by loosening
 * it would have made every OTHER absent cell claim it might be answered.
 */
export interface MoveReadsCell {
  /**
   * `taken` · `due` · `estimated`, or `null` when the server could not answer —
   * and `null` is never "no reads": the reason is in `unavailable` (DEF-075).
   *
   * ⚠ `estimated` reaches a FINAL READ cell ONLY, and only off the
   * settlement's own stored flag (`accounts.final_read_state`). A move-ins row
   * carrying it is a bug in the server, not a state this screen renders
   * specially.
   */
  state: string | null;
  /** The row's OWN event date the state was measured against (ISO), never a
   *  clock read here — `opened_at` for a move-in, `closed_at` for a move-out. */
  measured_against: string | null;
  /** Meters currently on the unit. `0` with an absence beside it means the
   *  unit has none, which is a configuration fact and not a verdict. */
  meters_total: number | null;
  /** How many of them have a committed head at/after `measured_against`. */
  meters_read: number | null;
  /** The asset numbers with no covering head — NAMED, so a clerk chases a
   *  meter rather than a unit. Empty on a `taken` row. */
  missing: string[];
  /**
   * ⚠ **RIDES BESIDE A SERVED STATE, IT DOES NOT REPLACE ONE.** A close that
   * predates `accounts.final_read_state` serves the derived `taken`/`due` AND
   * `final_read_state_not_recorded`; a screen that treated `unavailable` as
   * "instead of" would hide the state it did have.
   */
  unavailable: WorklistAbsence | null;
}

/** §5.5.2's DEPOSIT column — see §2. */
export interface MoveDepositCell {
  /** ⚠ **NULLABLE SINCE 2026-09-16 (`BR-CUS-1077`)** — a deposit is held ON an
   *  account and a pending job has not opened one, so there is no currency to
   *  name and no amount to show. `recorded` is `false` and the absence says
   *  which of the two kinds of nothing this is. */
  currency: string | null;
  amount: WorklistMoney | null;
  /** The fact the screen branches on. `false` means *no deposit is recorded*,
   *  which is NOT `waived` and NOT `—`. */
  recorded: boolean;
  /** ⛔ ALWAYS `null` — the disposition has no column. */
  sentence: string | null;
  unavailable: WorklistAbsence[];
}

/** BR-CUS-080's link, when the request was linked with the account number. */
export interface MoveLinkedRequest {
  id: string;
  request_no: string | null;
  waiting_on: string | null;
  park_note: string | null;
  state: string;
  requested_start: string | null;
}

export interface MoveCustomerAbsence {
  code: string;
  br_ref?: string;
  detail: string;
}

/** `BR-CUS-1077` (PO 2026-09-16, *"it should do B"*) — **this tab serves TWO
 *  kinds of row.** A draft ACCOUNT, which it has always shown, and a PENDING
 *  JOB, which approving a move-in now raises and which has no account at all.
 *
 *  ⚠ **THE SERVER SAYS WHICH; THIS SCREEN NEVER INFERS IT.** Inferring "it must
 *  be a job because the account number is missing" would be a second
 *  implementation of the rule, and the two would disagree the first time either
 *  moved — which is `DEF-127`'s shape, where a blank cell and an absent fact
 *  read the same way once rendered. */
export const ROW_KIND_ACCOUNT = "account";
export const ROW_KIND_PENDING_JOB = "pending_job";
/** ⚠ **THE THIRD KIND, 2026-09-20 (`DEF-CUS-5994`)** — the move-in a clerk
 *  STARTED and put down. PO, verbatim: *"remove it - it is anyway in the list
 *  so we dont need it sepretely - if it is not in list add it"*. Until that day
 *  this row was drawn on a pinned PANEL above this table (`CR-035` amendment 1)
 *  and this list could not see it at all. */
export const ROW_KIND_PARKED_MOVE_IN = "parked_move_in";

/** §9.LIST's OPENING READ cell — committed rows answer it; every other row
 *  carries `state: null` and `no_opening_read_before_complete`. */
export interface MoveInOpeningRead {
  state: string | null;
  meters_total: number | null;
  meters_read: number | null;
  missing: string[];
  readings: { register: string; reading: string | null; unit: string | null }[];
  unavailable: WorklistAbsence | null;
}

export interface MoveInRow {
  /** CR-039 wave D 17–19 — the same pair every job-record flow serves.
   *  ⚠ **NULL ON EVERY ROW OF THIS TAB, AND THAT IS CORRECT.** This list is the
   *  BR-CUS-018 draft window and a row LEAVES it when the move-in completes —
   *  which is exactly when `services.move_in` writes the record. So the cell
   *  states *"this move-in has not completed"* rather than a settings gap. */
  move_no: string | null;
  move_no_unavailable: WorklistAbsence | null;
  /** `account` or `pending_job` — see `ROW_KIND_ACCOUNT` above. */
  row_kind: string;
  /** The pending job's id, and `null` on an account row. It is what the table
   *  keys a job row by; B14 rule 31 keeps it off the screen. */
  job_id: string | null;
  /** ⚠ **NULLABLE SINCE 2026-09-16** — a pending job has no account. */
  account_id: string | null;
  /** ⚠ **`null` ON A PENDING JOB, WHICH IS §5.5.2's ITALIC `— draft`.** It was
   *  never null on an account row and still is not; `account_absence` beside it
   *  says WHY, so the cell is a sentence rather than a dash. */
  account_no: string | null;
  /** Why there is no account number — `null` on an account row. */
  account_absence?: MoveCustomerAbsence | null;
  customer: string | null;
  customer_no: string | null;
  /** CR-181-BRC10 — the account this move-in reopened (a record row only). */
  reopened?: { account_no: string; balance_choice: string | null } | null;
  /** `customer_entity` (BR-CUS-054) or `primary_contact` (the S17 fallback).
   *  Two different facts, and the screen says which it is showing. */
  customer_source: string | null;
  customer_absence?: MoveCustomerAbsence | null;
  /** `null` on a pending job whose application resolved to a premises but not
   *  to a unit — `SR-26-0024` on the demo tenant is exactly that. The ADDRESS
   *  is still shown: the server walks to the premises (hard rule 8). */
  unit_id: string | null;
  unit: string | null;
  move_in_date: string | null;
  move_in_date_absence?: MoveCustomerAbsence | null;
  step: MoveStepCell & {
    /** The four-step id and name a draft reached (`unit` · `customer` ·
     *  `billing` · `review`), `null` elsewhere. */
    id?: string | null;
    name?: string | null;
    /** `true` on a committed move-in — image 01's `Done`. */
    done?: boolean;
  };
  /** The seven-step screen's READS cell; `opening_read` replaces it here. */
  reads?: MoveReadsCell;
  /** `null` on a request row — a request holds no deposit. */
  deposit: MoveDepositCell | null;
  state?: string;
  starting_this_week?: boolean;
  booked_in_on: string | null;
  age_days: number | null;
  request?: MoveLinkedRequest | null;
  request_absence?: { code: string } | null;
  /** `BR-CUS-1077` — what the clerk still owes this job, read back live through
   *  the link. Unchecked documents no longer block an approval (PO 2026-09-16,
   *  *"lets not make it mandetory"*), and *not mandatory* is not *not
   *  mentioned*: the outstanding list travels with the job. `null` on an
   *  account row and on a job with nothing outstanding. */
  documents_outstanding?: { key: string; state: string; message_key: string | null } | null;
  /** ⚠ **`DEF-CUS-5994` — the draft's own id, and `null` on the other two
   *  kinds.** It is what `getRowId` keys a draft row by and what `resumePath`
   *  builds `?parked=<id>` from; B14 rule 31 keeps it off the screen. */
  park_id?: string | null;
  /** The parked facts, served flat and `null`/absent on a record row. Each was
   *  on the removed panel and NONE of them is anywhere else — `parked_by_name`
   *  in particular is what `CR-035` amendment 1 put in place of the
   *  mine/everyone's toggle it dissolved. */
  waiting_on?: string | null;
  park_note?: string | null;
  remind_on?: string | null;
  parked_at?: string | null;
  parked_by_name?: string | null;
  // ── `CR-171-BRC10` §9.LIST — the redesigned list's keys ─────────────────
  /** One of the eight (`MOVE_IN_STATUSES`) — the pill, the icon and the
   *  filter all read it. Optional only because an older server omits it. */
  status?: string;
  /** What the row links to: `/moves/{reference}` — `SR-…` or `MVI-…`. */
  reference?: string | null;
  /** The row's ONE icon: `review` · `start` · `resume` · `view`. */
  action?: string;
  /** Service codes, or `null` on a draft that has not ticked any yet. */
  services?: string[] | null;
  opening_read?: MoveInOpeningRead | null;
  request_id?: string | null;
  record_id?: string | null;

}

/** Image 01's five tiles (§9.LIST `kpis`), each counted over the WHOLE list.
 *  Every one is optional because an older server does not send it, and a
 *  missing tile draws `—`, never `0`. The server also still serves the
 *  seven-step screen's keys; this screen reads none of them. */
export interface MoveInKpis {
  to_approve?: number;
  not_started?: number;
  drafts?: number;
  starting_this_week?: number;
  waiting_on_a_read?: number;
  by_status?: Record<string, number>;
}

export interface MoveInList {
  rows: MoveInRow[];
  kpis: MoveInKpis;
  page: number;
  per: number;
  total: number;
  pages: number;
  columns: string[];
  /** The seven-step screen's segments, still served; not read here. */
  states?: MoveStateSegment[];
  /** §9.LIST — the eight statuses and the filter's groups. */
  statuses?: string[];
  status_groups?: Record<string, string[]>;
  /** CR-045 wave D · D.9 — the `f.<name>` names this list accepts. */
  filters?: string[];
  search: {
    hint: string;
    min_chars: number;
    legs: string[];
    unavailable: WorklistAbsence[];
  };
  /** B18 §5.7.3's counting contract, honoured and published. */
  exclusion: { callout: string; contract: string[]; half_account_ids: string[] };
  /** What this LIST cannot show at all, as opposed to what a CELL cannot say. */
  unavailable: WorklistAbsence[];
  as_of: string;
}

/** CR-045 wave D · D.9 / D.10 — the two move tabs declare ONE dimension each,
 *  and they are not the same one. See `moveInFilterGroups` and
 *  `moveOutFilterGroups` for why move-outs gets a WINDOW and not a state. */
/** ⚠ **`status` AND `service` SINCE `CR-171-BRC10` P2.01.** It was `["state"]`
 *  — the seven-step screen's derived state — and this screen no longer sends
 *  it; the server still honours it for its own suites (§9.LIST). */
export const MOVE_IN_LIST_FILTERS = ["status", "service"] as const;
export const MOVE_OUT_LIST_FILTERS = ["closed"] as const;

export interface MoveListQuery {
  q?: string;
  page?: number;
  per?: number;
  /** `BR-CUS-1046` — the clerk's chosen column, as the SERVER's sort name.
   *
   * ⚠ **BOTH HALVES OR NEITHER (hard-won law 2).** Declaring a column
   * `sortable` renders the control; carrying the name to the server is what
   * makes pressing it do anything. Until 2026-09-12 this list declared no
   * sortable column AND sent no `sort`, which was at least consistent. Adding
   * one without the other is a live control over a fixed order — it looks like
   * it works, and `tsc` and every test pass. */
  sort?: string;
  dir?: "asc" | "desc";
  /** BR-SHL-011's declared dimensions, serialized as `f.<name>`. */
  filters?: Record<string, string>;
}

/**
 * `GET /move-ins`.
 *
 * ⛔ **NO `segment` PARAMETER, and it is `listConnections`' reason exactly.**
 * Two of the five DRAWN segments cannot be filled and the server says so on
 * every response; a wrapper that took a segment would let the screen discover
 * that by CALLING it.
 *
 * ✅ **`f.state` IS A DIFFERENT THING AND IT IS SENT (CR-045 wave G,
 * `DEF-1702`).** A segment is an exclusive tab; a filter is a predicate on
 * `move_in_state`. `MOVE_IN_FILTERS` accepts exactly the codes `MOVE_IN_STATES`
 * marks `supported` — the two the schema cannot hold are NOT offered, because a
 * filter that returns an empty list forever reads as *"there are none"*.
 *
 * ⚠ **IT IS APPLIED IN THE QUERYSET, BEFORE PAGING.** `move_ins_queryset`
 * negates `move_in_state`'s own three branches in SQL, so the `total` moves
 * with the filter. Narrowing in the browser would narrow the PAGE IN HAND —
 * a subset of a subset, under an authoritative-looking total.
 *
 * ⚠ **`sort`/`dir` ARE CARRIED SINCE 2026-09-12 (`BR-CUS-1046`).** This note
 * read *"`sort`/`dir` are absent: §5.5.2 fixes the order — 'Sorted by move-in
 * date, soonest first' — and the server accepts no sort param"*, which was true
 * of both halves. `move_ins_queryset` takes a `sort` now, the default is the
 * creation order, and §5.5.2's ordering is `sort=move_in_date`.
 */
export async function listMoveIns(
  query: MoveListQuery = {},
  client: ApiClient = api,
): Promise<MoveInList> {
  return requireMoveData(
    await client.get<MoveInList>("/move-ins", {
      query: {
        q: query.q === undefined || query.q === "" ? undefined : query.q,
        page: query.page,
        per: query.per,
        // `BR-CUS-1046` — the chosen ordering, so it reaches the `ORDER BY` and
        // survives a refresh in the URL rather than living only in component
        // state (the rule's own second clause).
        sort: query.sort,
        dir: query.dir,
        ...worklistFilterParams(query.filters, MOVE_IN_LIST_FILTERS),
      },
    }),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE SHARED CELLS — both move tabs render these, so one absence looks the
// same on both tabs of one screen
// ══════════════════════════════════════════════════════════════════════════
/**
 * ⛔ **DEF-731 — THE SERVER'S `detail` IS A DIAGNOSTIC AND MUST NOT REACH THE
 * DOM.** This map is the fix, and the reasoning it displaced is written below
 * rather than deleted.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHAT WENT WRONG, IN ONE SENTENCE A CLERK ACTUALLY READ
 * ══════════════════════════════════════════════════════════════════════════
 * Until this commit these two tabs rendered the absence dictionaries authored
 * in `06-backend/apps/customers/move_reads.py` straight onto the page, so the
 * paragraph under the Move-outs table read:
 *
 *     "`services.move_out` writes `closed_at`, the terminal status and the
 *      agreement end dates in ONE transaction, and `accounts` carries no
 *      `scheduled_move_out_on` … `MOVE_OUT_FIELDS` will not even accept a date
 *      to park … `sample_data.py`'s W5 block measured the same thing from the
 *      seeding side and wrote `account_notes` rows instead."
 *
 * Every clause of that is TRUE and every clause is addressed to an engineer.
 * The Product Owner found it walking the deployed build — *"this text is note
 * required on screen"* — and no gate in this repo could have, because prose in
 * a component is indistinguishable from copy to every check that exists.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ THE ABSENCE IS KEPT. ONLY THE VOICE CHANGES.
 * ══════════════════════════════════════════════════════════════════════════
 * Deleting these statements would trade a badly-worded truth for a lie of
 * omission, which hard-won law 2 and G38 both price higher than bad wording.
 * `07-frontend/src/features/work/TemplatesPage.tsx` is the register the
 * PO praised and this map copies it: **state the absence in the reader's
 * language, name no module, file, field or design section, and say what the
 * person can do instead.**
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHY THE SCREEN OWNS THE SENTENCE AND THE SERVER DOES NOT
 * ══════════════════════════════════════════════════════════════════════════
 * The obvious alternative is to rewrite `detail` in the backend. It was
 * measured and rejected: these dictionaries are assembled from FOUR modules —
 * `move_reads`, `move_out_settlement` (a ❄️-adjacent money engine), the ledger
 * seam and the service-request reads — and they are read by tests, by the
 * seeder and by other screens as DIAGNOSTICS. Rewriting a diagnostic into copy
 * loses the diagnostic; leaving it and adding a second field puts the same
 * words in two places, which is hard-won law 5. So the payload keeps its
 * engineering sentence for us, and the SCREEN says the sentence for the reader
 * — keyed off `code`, which is the stable machine identifier the server already
 * publishes for exactly this purpose.
 *
 * ⚠ **AN UNKNOWN CODE FALLS BACK TO A SENTENCE, NEVER TO SILENCE AND NEVER TO
 * THE DIAGNOSTIC.** A new server absence this map has not learned yet still
 * tells the reader something is missing; `screenVoice.guard.test.tsx` asserts
 * every code these two tabs can serve has its own words, so the fallback is a
 * safety net and not a hiding place.
 */
export const ABSENCE_COPY: Record<string, string> = {
  // ⚠ THE THREE BELOW JOINED 2026-08-27 (CR-039 wave D 17–19) and are the
  // three ways the new `Reference` cell can be empty. They are separate
  // sentences on purpose: a clerk acts differently on each, and one shared
  // "cannot be shown" would be DEF-127's shape on a brand-new column.
  move_predates_the_record:
    "This move happened before we started keeping a record of one, so there is no " +
    "reference to quote. Nothing is missing from this utility's setup.",
  // ⚠ **NARROWED 2026-09-22 (`BR-CUS-1090`), IN THE SAME COMMIT AS THE SERVER
  // AND THE CELL.** It said *"The reference appears when the account opens"* —
  // false since `CR-122-BRC06` numbered a parked draft on 2026-09-20, and false
  // twice over now that an approved job is numbered at the press. This is the
  // TOOLTIP now, not the cell (`DEF-CUS-6177`), which is why it may be a
  // sentence at all: rule 32 puts a stated absence behind a disclosure, CLOSED
  // by default, and rule 33's six words govern what is on screen at rest.
  move_in_not_completed:
    "No number has been issued for this move-in yet. One is issued when a service request " +
    "is approved, or when somebody opens the move-in wizard.",
  numbering_series_missing:
    "No number format has been set up for these yet, so nothing has been issued. The move " +
    "itself went through; only its reference is missing. Settings → Numbering is where the " +
    "format is chosen.",
  // `CR-171-BRC10` §9.LIST — the OPENING READ cell of every row that is not
  // a committed move-in. A dash on screen; this is its tooltip.
  no_opening_read_before_complete: "Opening reads are taken at Complete.",
  move_step_has_no_store:
    "How far along a move-in or move-out has got is not recorded anywhere yet, so this bar " +
    "is left empty rather than filled in with a guess.",
  unit_reads_not_readable_from_customers:
    "Whether a meter reading has been taken cannot be shown on this list. Look the reading " +
    "up under Meter Reads.",
  // ⚠ THE THREE BELOW JOINED 2026-08-26 (CR-038 W9 · DEF-786). Each is served
  // by `move_reads.py` and, until this commit, fell through to the generic
  // fallback sentence — which says "cannot be shown" about three different
  // things a clerk can act on differently.
  unit_has_no_meters:
    "No meter is fitted at this unit, so there is no reading to take. This is how the unit " +
    "is set up — it is not a reading that was missed.",
  reads_state_needs_a_service_start_date:
    "There is no service start date, so there is nothing to measure a reading against yet. " +
    "Set the start date and the reading state appears with it.",
  final_read_state_not_recorded:
    "Whether the closing bill used a real reading or an estimated one was not recorded for " +
    "this move-out. The reading state shown beside this is worked out from the meter as it " +
    "stands today.",
  deposit_disposition_has_no_column:
    "Only the deposit amount on file is kept, not what was decided about it. A blank here " +
    "means nothing was recorded — it does not mean the deposit was waived.",
  deposit_carry_election_has_no_column:
    "Nobody has been asked yet whether a deposit should move across from a closed account, " +
    "so there is nothing to count. This is not a count of none.",
  waiting_on_has_no_vocabulary:
    "This counts move-ins waiting on anything, not only documents. What a move-in is " +
    "waiting on is written in the clerk's own words, so it cannot be narrowed down.",
  completed_move_in_has_no_retention_window:
    "A move-in leaves this list the moment its account opens, so finished move-ins are not " +
    "shown here. There is no setting yet for how long to keep them.",
  // ⚠ **KEPT, AND ITS SENTENCE IS NOW HALF TRUE — `BR-CUS-1077`, 2026-09-16.**
  // An APPROVED move-in with no account IS listed here now; an unapproved one
  // still is not. The server stopped serving this code on the Move-ins list the
  // day the ruling landed and serves `unapproved_move_in_is_a_request` instead,
  // but the code stays in this map: a copy map is read by whatever the server
  // sends, and a code with no entry falls through to a generic sentence that
  // says "cannot be shown" about something a clerk can act on.
  parked_draft_has_no_account_row:
    "A move-in nobody has approved yet is not listed here. It stays on the Requests tab " +
    "until a clerk approves it.",
  unapproved_move_in_is_a_request:
    "A move-in nobody has approved yet is an application, not a job, so it is on the " +
    "Requests tab. It joins this list the moment a clerk approves it.",
  pending_move_in_has_no_account:
    "This move-in has been approved and nobody has done it yet, so there is no account " +
    "number. Approving raises the job; the account is made when somebody runs the move-in.",
  pending_move_in_has_no_deposit_on_file:
    "A deposit is held on an account, and this move-in has not opened one. Nothing is held " +
    "and nothing was waived; what to collect is decided when somebody runs the move-in.",
  pending_job_closes_on_the_recorded_move:
    "A move-in leaves this list when somebody runs it from the application it came from. " +
    "Run it another way and it stays here beside the account it made.",
  pending_job_has_no_account_number_to_search:
    "Searching by account number finds the move-ins that already have one. A move-in " +
    "nobody has started answers to the applicant's name or the request number.",
  no_requested_start_date:
    "The application named no start date. Nothing is blocked by that — the date is settled " +
    "when somebody runs the move-in, and it is what the account opens with.",
  request_leg_matches_only_linked_refs:
    "Searching by request number finds a move-in only where the request was linked to the " +
    "new account. If you get no result, the link may be missing rather than the move-in.",
  account_has_no_customer_link:
    "No customer is recorded on this account. That is the account as it stands, not " +
    "something that failed to load.",
  service_start_date_not_set:
    "No service start date. The account cannot be opened until one is set, and that is what " +
    "this move-in is waiting on.",
  // ⚠ **REWRITTEN 2026-09-19 — the old sentence was FALSE and it was on screen.**
  // It read *"A move-out that has not gone through yet is not kept anywhere, so
  // this list shows only the ones already closed."* The PO ruled the unfinished
  // ones onto the list that day (`yes`), and they were always kept — a parked
  // wizard is a `wizard_parks` row. What is left is the one true case: a
  // move-out nobody has started.
  move_out_before_close_has_no_store:
    "A move-out nobody has started yet is not kept anywhere. One a clerk began and put " +
    "down is listed here, with the step they reached.",
  parked_move_out_has_no_reference:
    "This move-out has not finished, so it has no number yet. The number is given when it " +
    "is completed; nothing that was typed is lost.",
  parked_move_out_has_no_settlement:
    "Nothing is settled until the account closes. Open the account to see what is owed " +
    "today.",
  parked_move_out_has_no_account_yet:
    "Nobody has chosen the account yet. It is picked when this move-out is taken back up.",
  parked_move_out_account_not_found:
    "The account this move-out named can no longer be read. Taking it back up asks for " +
    "another one.",
  parked_move_out_has_no_account_number_to_search:
    "Searching by account number finds the move-outs that are finished. An unfinished one " +
    "answers to the name it was started under.",
  parked_move_out_date_not_chosen_yet:
    "No move-out date yet. It is asked for later in the move-out, and nothing that was " +
    "typed is lost.",
  parked_move_out_customer_from_the_draft_label:
    "This name was copied when the move-out was started and has not been read again since.",
  move_out_window_has_no_closing_edge:
    "A closed account stays on this list. Nothing takes it off, because the final bill that " +
    "would finish it cannot be seen from here.",
  move_out_has_no_request_link:
    "You cannot search move-outs by request number. A move-out is not linked back to the " +
    "request it came from, so searching by one would find nothing.",
  final_bill_not_stated:
    "The final bill for a closing account cannot be seen from here, so no settlement can be " +
    "worked out. What is held and what is owed are shown separately; neither is a settlement.",
  deposit_interest_not_accrued:
    "Interest on a deposit is not worked out anywhere in SMART360 Next yet, so only the " +
    "amount held is shown.",
  settlement_terms_not_read_on_a_list:
    "A full settlement also weighs credit on the account, the customer's other accounts and " +
    "any open dispute. None of those is read on this list — open the account itself for the " +
    "whole picture.",
  ledger_publishes_no_per_account_ar_position:
    "What this customer owes could not be read from the books, so no figure is shown. It is " +
    "not zero — nothing was worked out.",
  // BR-CUS-096 SUSPENDED (PO 2026-10-11): with no dispute store the server
  // reads "no dispute" and refunds, so this code arrives only if a published
  // store fails to answer. The sentence no longer claims a standing hold.
  open_disputes_not_readable:
    "The dispute record could not be read, so this refund waits.",
  other_accounts_not_readable:
    "The customer's other accounts could not be read, so nothing is refunded before they " +
    "have been checked.",
  export_credit_exceeds_final_bill:
    "There is more export credit than the final bill uses up, and what happens to the rest " +
    "has not been decided yet. Nothing here writes it off.",
  sibling_credit_rule_unsigned:
    "Credit sitting on another of this customer's accounts is shown but never used here. " +
    "Whether it can be put towards this one has not been decided.",
  held_excess_has_no_release_path:
    "Money held back over a dispute stays held. There is no step on this screen that " +
    "releases it.",
};

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-6177` — A TABLE CELL IS A VALUE, NOT AN EXPLANATION (B14 rule 33)
// ══════════════════════════════════════════════════════════════════════════
//
// ⛔ **THE PO OPENED THIS TAB AND FOUND WHOLE PARAGRAPHS INSIDE TABLE CELLS.**
// Three sentences of rationale in a column headed `Reference`; the generic
// *"SMART360 Next cannot show this yet, so nothing is shown here rather than a
// figure nobody worked out."* in one headed `Customer`.
//
// **B14 rule 33 caps ON-SCREEN TEXT BY WHAT IT IS FOR**: a LABEL ≤ 3 words with
// no sentence, a FACT ≤ 6 words, and **RATIONALE — why the product works this
// way, why a value is absent — is ZERO WORDS ON SCREEN.** Rule 32 gives the
// whole screen a description budget and says a stated absence is CLOSED by
// default. A cell is the tightest place either rule applies.
//
// ⚠ **THE FIX IS THREE WORDS, NOT NO WORDS, AND THAT DISTINCTION IS THE WHOLE
// DESIGN.** Deleting the absence would trade a badly-worded truth for a lie of
// omission, which this repo has recorded as the more expensive failure
// (`BR-SHL-025`, `G38`, `DEF-445`, `DEF-127`). So the cell shows the SHORT
// fact and `ABSENCE_COPY`'s sentence stays in the `title` — visible on hover,
// closed by default, exactly what rule 32 asks for.
//
// ⚠ **THE ACCOUNT CELL ON THE SAME ROW ALREADY DID THIS**, and has since
// `BR-CUS-1077`: `— draft` with the sentence in the tooltip. So this is two
// cells being brought into line with their own neighbour rather than a new
// pattern, which is also why no shared component moved and why the Move-outs,
// Transfers and Disconnects tabs are untouched by this fix.
//
// ⚠ **AN UNKNOWN CODE RENDERS `—` AND KEEPS ITS SENTENCE.** It is the same
// posture `ABSENCE_COPY` takes one map down: a code this map has not learned
// yet must still tell the reader something is missing rather than render the
// server's diagnostic or nothing at all.
export const ABSENCE_SHORT: Record<string, string> = {
  // ── the REFERENCE column's three absences ──────────────────────────────
  // ⚠ Its sentence was narrowed by `BR-CUS-1090` in the same commit as this
  // map: a number is issued at approval or when a wizard is opened, so the
  // short form says *not issued* rather than *not completed*.
  move_in_not_completed: "Not issued yet",
  move_predates_the_record: "No record kept",
  numbering_series_missing: "No number format",
  // ── the CUSTOMER column ────────────────────────────────────────────────
  // ⛔ NOT `—`: a draft holds a name somebody typed and has created nobody, and
  // a bare dash would read as *this move-in has no customer*.
  parked_move_in_customer_is_still_being_typed: "Not created yet",
  account_has_no_customer_link: "No customer linked",
  // ── the ACCOUNT column, for a row that is not a pending job ─────────────
  pending_move_in_has_no_account: "Not opened yet",
  parked_move_in_has_no_account: "Not opened yet",
  // ── the READS and STEP columns ─────────────────────────────────────────
  move_step_has_no_store: "Not recorded",
  unit_has_no_meters: "No meter fitted",
  unit_reads_not_readable_from_customers: "Not readable here",
  reads_state_needs_a_service_start_date: "No start date",
  // `DEF-CUS-7902` — the Move-outs FINAL READ cell draws this BESIDE a served
  // state (`Taken`), and with no short form it fell to `—`: the reassuring
  // half showed and the missing flag read as nothing.
  final_read_state_not_recorded: "Source not recorded",
};

/**
 * ONE VALUE THAT IS ABSENT, as a table cell is allowed to say it.
 *
 * B14 rule 43 — a piece of UI is a COMPONENT, so the next cell that has to
 * render an absence does not have to remember any of the above. Three words or
 * a dash on screen; the reader's whole sentence in the tooltip; the tracking id
 * in `data-tracks`, where `G38` reads it and a clerk cannot.
 */
export function MoveAbsenceValue(props: {
  absence: WorklistAbsence | MoveCustomerAbsence | undefined | null;
  marker: string;
}) {
  const { t } = useTranslation();
  const code = props.absence?.code ?? "";
  const short = ABSENCE_SHORT[code];
  return (
    <MoveAbsenceNote absence={props.absence} marker={props.marker}>
      <span className="text-neutral-700">
        {short === undefined
          ? "\u2014"
          : t(`customers.move.absentShort.${code}`, { defaultValue: short })}
      </span>
    </MoveAbsenceNote>
  );
}

/** The one sentence a person may read for an absence. Never `detail`. */
export function absenceCopy(
  absence: { code?: string | null } | undefined | null,
  t: (key: string, params?: Record<string, unknown>) => string,
): string | null {
  if (absence === undefined || absence === null) {
    return null;
  }
  const code = absence.code ?? "";
  const known = ABSENCE_COPY[code];
  return known === undefined
    ? t("customers.move.absent.unknown", {
        defaultValue:
          "SMART360 Next cannot show this yet, so nothing is shown here rather than a figure " +
          "nobody worked out.",
      })
    : t(`customers.move.absent.${code}`, { defaultValue: known });
}

/**
 * A stated absence, rendered as the thing a user reads instead of a figure.
 *
 * ⚠ **THE TRACKING ID IS AN ATTRIBUTE AND NEVER PART OF THE SENTENCE**
 * (DEF-332 / G28): `BR-CUS-022` means nothing to a billing clerk. `data-tracks`
 * is how G38's mechanism survives this rewrite — the id is present for us and
 * absent from what a person reads, which is both halves of the PO's 2026-08-19
 * ruling.
 *
 * ⛔ **`detail` NO LONGER REACHES THE DOM — NOT AS TEXT AND NOT AS A TOOLTIP**
 * (DEF-731). It was the `title` until 2026-08-26, and a `title` is copy: a
 * clerk hovering a cell read the same engineering prose the paragraph under the
 * table showed. The tooltip now carries the reader's sentence, so hovering a
 * short cell label ("Not readable here") gives the long form of the SAME
 * statement instead of a different one addressed to somebody else.
 */
export function MoveAbsenceNote(props: {
  absence: WorklistAbsence | MoveCustomerAbsence | undefined | null;
  marker?: string;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  const absence = props.absence ?? null;
  const copy = absenceCopy(absence, t);
  return (
    <span
      role="note"
      className="block text-sm text-neutral-700"
      data-move-absent={props.marker ?? ""}
      data-tracks={absence?.br_ref ?? absence?.code}
      title={copy ?? undefined}
    >
      {props.children ?? copy ?? ""}
    </span>
  );
}

/**
 * §5.5.2 / §5.6.2's STEP cell — the bar, and either the step reached or the
 * reason there is none.
 *
 * ⚠ **THE SEGMENT COUNT IS THE SERVER'S `of`, NEVER A LITERAL HERE.** On the
 * move-outs tab that number is BR-SHL-046's SIX, superseding B18 §5.6.2's
 * drawn `of 4`; a `4` typed into this file is exactly the reintroduction the
 * server carries the constant to prevent.
 *
 * ⚠ **IT DREW EVERY SEGMENT EMPTY UNTIL 2026-09-19 AND SAID SO IN A COMMENT —
 * *"nothing is filled because nothing is known"*.** That was true of every row
 * either tab could hold at the time. The PO ruled the unfinished move-outs onto
 * the Move-outs list that day (`yes`), and one of those carries a REAL step off
 * its own `wizard_parks` row — the Accounts blueprint p117 draws it as
 * `2 of 6`. So the bar fills to `reached` when the server sends one.
 *
 * ⛔ **AND IT STILL DRAWS EMPTY WITH A REASON WHEREVER `reached` IS NULL**,
 * which is every closed move-out, every draft account and every pending
 * move-in job. Four code paths close an account and only one is the wizard, so
 * a full bar on a closed row would claim a clerk walked six steps they never
 * saw. **`reached` is the server's answer and this component never derives
 * one.**
 */
export function MoveStepBar(props: { step: MoveStepCell; label: string }) {
  const { t } = useTranslation();
  const { step } = props;
  const reached = step.reached;
  return (
    <span
      className="inline-flex flex-col gap-1"
      data-step-of={step.of}
      data-step-reached={reached ?? ""}
    >
      {/* ⚠⚠ **THE BAR IS DRAWN ONLY WHERE THERE IS A STEP TO DRAW — 2026-09-25,
          `DEF-CUS-6770`.** It used to render `step.of` empty segments on EVERY
          row, so a closed move-out showed **two grey dashes stacked over the
          words `Step not recorded`**: one absence, stated twice, and the top
          half drawn as placeholder furniture. **The blueprint has no bar at
          all** — p119 draws this column as `6 of 6` · `2 of 6` · `6 of 6`,
          plain text — so an EMPTY bar was never in the drawing in any form.
          The filled bar stays where the server sends a `reached`, which is the
          only row it ever said anything about. */}
      {reached !== null && (
        <span className="inline-flex items-center gap-0.5" aria-hidden="true">
          {Array.from({ length: step.of }, (_unused, index) => (
            <span
              key={index}
              className={
                index < reached ? "h-1 w-3 bg-neutral-700" : "h-1 w-3 bg-neutral-200"
              }
              data-step-segment={index + 1}
            />
          ))}
        </span>
      )}
      {reached === null ? (
        <MoveAbsenceNote absence={step.unavailable} marker="step">
          {props.label}
        </MoveAbsenceNote>
      ) : (
        // p117's own cell, and it is a FACT rather than a sentence: three
        // words, inside B14 rule 33's six.
        <span className="block text-sm text-neutral-700" data-step-progress={`${reached}/${step.of}`}>
          {t("customers.move.step.progress", {
            defaultValue: "{{reached}} of {{of}}",
            reached,
            of: step.of,
          })}
        </span>
      )}
    </span>
  );
}

/**
 * §5.5.2's READS cell and §5.6.2's FINAL READ cell — **ONE component, both
 * tabs**, so the same fact cannot be worded two ways on one screen.
 *
 * ⚠ **THIS IS DEF-786's FIX.** Both tabs drew an unconditional
 * *"Not readable here"* over a payload that had carried a real state since the
 * W9 seam landed. The absence is KEPT — `unavailable` still has three ways to
 * arrive and every one of them still says its own sentence — but it is now the
 * branch it always claimed to be rather than the only branch.
 *
 * THREE THINGS ARE DRAWN, and the second is the one a clerk actually works
 * from:
 *
 *   1. the STATE word — `taken` / `due`, plus `estimated` on a final cell;
 *   2. the COUNT, `2 of 3 read`, which turns a `due` into a size;
 *   3. the MISSING METER NUMBERS, so the next action is a meter and not a
 *      hunt. They are the `title`, not a wall of text in the row.
 *
 * ⚠ **AN ABSENCE MAY RIDE BESIDE A SERVED STATE AND IS NOT SWALLOWED BY ONE.**
 * `final_read_state_not_recorded` is exactly that case: the derived state is
 * real, and *how the settlement got its reading* is unrecorded. Rendering only
 * one of the two would be the half-truth the absence was minted to prevent.
 *
 * ⚠ **NO TONE IS THE `danger` TIER.** B14 reserves it for destructive commits;
 * a reading that has not been taken yet is work to do, not a warning about
 * something irreversible.
 */
export function MoveReadsCellView(props: {
  reads: MoveReadsCell;
  /** `reads` on the move-ins tab, `final-read` on the move-outs tab — the
   *  `data-move-absent` marker the guards and the DOM tests key off. */
  marker: string;
  /** The words shown when the server served NO state at all. */
  notReadableLabel: string;
  /** A FINAL READ cell may say `estimated`; a READS cell may not. */
  final?: boolean;
}) {
  const { t } = useTranslation();
  const { reads } = props;
  if (reads.state === null) {
    return (
      <MoveAbsenceNote absence={reads.unavailable} marker={props.marker}>
        {props.notReadableLabel}
      </MoveAbsenceNote>
    );
  }
  const estimated = props.final === true && reads.state === "estimated";
  const label = estimated
    ? t("customers.move.reads.estimated", { defaultValue: "Estimated" })
    : reads.state === "taken"
      ? t("customers.move.reads.taken", { defaultValue: "Taken" })
      : t("customers.move.reads.due", { defaultValue: "Due" });
  // `taken` is done; `due` and B18's amber `estimated` are both work, and the
  // WORD is what tells them apart — the colour only says "look at me".
  const tone = reads.state === "taken" ? "text-success-700" : "text-warning-700";
  const total = reads.meters_total ?? 0;
  const read = reads.meters_read ?? 0;
  return (
    <span
      className="inline-flex flex-col gap-0.5"
      data-reads-state={reads.state}
      data-reads-measured-against={reads.measured_against ?? ""}
    >
      <span className={tone}>{label}</span>
      <span
        className="text-sm tabular-nums text-neutral-700"
        data-reads-count={`${read}/${total}`}
        // The meters still to read, NAMED — as the tooltip, so the row stays a
        // row. `missing` is empty on a `taken` cell, so nothing is promised.
        title={reads.missing.length > 0 ? reads.missing.join(", ") : undefined}
      >
        {t("customers.move.reads.count", {
          defaultValue: "{{read}} of {{total}} read",
          read,
          total,
        })}
      </span>
      {reads.unavailable !== null && (
        // ⚠ BESIDE, never INSTEAD OF — see the component docstring.
        // `DEF-CUS-6177` — and BESIDE a figure is the tightest place of all for
        // a paragraph, so it is three words here too.
        <MoveAbsenceValue absence={reads.unavailable} marker={`${props.marker}-note`} />
      )}
    </span>
  );
}

/**
 * The CUSTOMER cell, with WHICH name it is showing.
 *
 * BR-CUS-054's entity is the right answer; the primary CONTACT is the S17
 * fallback for an account created before that entity existed. They are
 * different facts and the number is only ever the entity's, so a row showing
 * the fallback shows no number rather than an empty one.
 */
export function MoveCustomerCell(props: {
  name: string | null;
  number: string | null;
  absence: MoveCustomerAbsence | null;
}) {
  if (props.name === null) {
    // `DEF-CUS-6177` — three words, not a paragraph. This rendered the whole
    // `ABSENCE_COPY` sentence until 2026-09-22, and on a parked draft (whose
    // code this map had never learned) that was the generic *"SMARTBillHub
    // cannot show this yet…"* fallback, in a column headed `Customer`.
    return <MoveAbsenceValue absence={props.absence} marker="customer" />;
  }
  return (
    <span className="inline-flex flex-col">
      <span>{props.name}</span>
      {props.number !== null && (
        <span className="tabular-nums text-neutral-700">{props.number}</span>
      )}
    </span>
  );
}


// ══════════════════════════════════════════════════════════════════════════
// THE MOVE-INS LIST — `CR-171-BRC10` P2.01 · P2.02 (lane MVI-LIST-UI), built
// from `05-prototype/movein-redesign-2026-10-05/images/01-list.png` and
// `02-list-filter-open-chips.png` read AS IMAGES (B14 rule 42), our UI
// standard deciding spacing, sizes and components (rule 44).
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **ONE STATUS PER ROW, AND IT IS THE SERVER'S** (`move_in_list.STATUSES`,
// §9.LIST). The pill, the row icon and the filter all read the same `status`
// and `action`, so the list cannot say *To approve* over a row whose icon
// opens a record (the `DEF-127` shape). Nothing here derives a status.
//
// ⚠ **WHAT THE OLD SCREEN SAID AND THIS ONE DOES NOT, ON PURPOSE:** the two
// footnotes under the table (S3 — requests are rows now; S4 — finished
// move-ins stay) and the sort sentence are gone (rule 33: rationale is zero
// words); the ACCOUNT and READS columns became SERVICES and OPENING READ; the
// `f.state` filter and the three old tiles are no longer read by this screen
// (the server still serves both for its own suites — §9.LIST).

/** The eight statuses, in `move_in_list.STATUSES`' order. */
export const MOVE_IN_STATUSES = [
  "to_approve",
  "waiting_on_customer",
  "declined",
  "not_started",
  "draft",
  "waiting_on_a_read",
  "completed",
  "cancelled",
] as const;

/** Image 02's Status radio, as the GROUPS the server accepts in `f.status`.
 *  `closed` (declined + cancelled) is served and not drawn; it sits under the
 *  bar's `All` chip, which is the kit's clear-all (B14 rule 12). */
export const MOVE_IN_STATUS_FILTER_GROUPS = ["to_approve", "open", "completed"] as const;

const MOVE_IN_STATUS_LABELS: Record<string, string> = {
  to_approve: "To approve",
  waiting_on_customer: "Waiting on customer",
  declined: "Declined",
  not_started: "Not started",
  draft: "Draft",
  waiting_on_a_read: "Waiting on a read",
  completed: "Completed",
  cancelled: "Cancelled",
};

const MOVE_IN_STATUS_GROUP_LABELS: Record<string, string> = {
  to_approve: "To approve",
  open: "Open",
  completed: "Completed",
};

/**
 * The pill's tone. Image 01 draws amber for the two that need a clerk
 * (To approve, Waiting on a read), blue for Not started, grey for a draft and
 * green for Completed. A request waiting on its customer is amber for the
 * reason To approve is: somebody owes the next move. Declined and Cancelled
 * are finished and quiet.
 */
export function moveInStatusTone(status: string): StatusTone {
  switch (status) {
    case "to_approve":
    case "waiting_on_customer":
    case "waiting_on_a_read":
      return "warning";
    case "not_started":
      return "info";
    case "completed":
      return "success";
    case "declined":
    case "cancelled":
      return "muted";
    default:
      return "neutral";
  }
}

/** The pill's words. A draft carries its age (image 01's `DRAFT · 2 DAYS`). */
export function moveInStatusLabel(
  row: Pick<MoveInRow, "status" | "age_days">,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  const status = row.status ?? "";
  const label = t(`customers.moveIns.status.${status}`, {
    defaultValue: MOVE_IN_STATUS_LABELS[status] ?? status,
  });
  if (status === "draft" && typeof row.age_days === "number") {
    return t("customers.moveIns.status.draftAge", {
      count: row.age_days,
      label,
      defaultValue: "{{label}} · {{count}} days",
    });
  }
  return label;
}

/**
 * The `+ Filter ▾` panel's two dimensions (image 02): **Status** — the three
 * drawn groups — and **Service** — the tenant's enabled services, several at
 * once (`OQ-306` closed, the kit's multi-select by name).
 *
 * ⚠ **STATUS IS A GROUP NAME ON THE WIRE**, never the eight statuses: the
 * server reads `f.status=open` as not started + draft + waiting on a read, so
 * the filter and the tiles cannot disagree about what *open* means.
 */
export function moveInFilterGroups(
  serviceOptions: { value: string; label: string }[],
  t: (key: string, params?: Record<string, unknown>) => string,
): TableFilterConfig[] {
  return [
    {
      name: "status",
      label: t("customers.moveIns.filter.status", { defaultValue: "Status" }),
      options: MOVE_IN_STATUS_FILTER_GROUPS.map((group) => ({
        value: group,
        label: t(`customers.moveIns.statusGroup.${group}`, {
          defaultValue: MOVE_IN_STATUS_GROUP_LABELS[group],
        }),
      })),
    },
    {
      name: "service",
      label: t("customers.moveIns.filter.service", { defaultValue: "Service" }),
      options: serviceOptions,
    },
  ];
}

/** The row's door — what the reference and the icon open. Every row with a
 *  reference opens its details view (`/moves/{reference}`, §9.LIST — the
 *  details view answers an `SR-` too); the ICON may open somewhere else. */
export function moveInDetailsPath(row: Pick<MoveInRow, "reference">): string | null {
  return row.reference === null || row.reference === undefined || row.reference === ""
    ? null
    : moveRecordPath(row.reference);
}

/**
 * Where the row's ONE icon goes (image 01), off the server's `action`:
 *
 *   * `review` (To approve, Waiting on customer) → the details view, where
 *     Approve, Ask for more and Decline live (images 03–06);
 *   * `start` (Not started) → the wizard, filled from the approved request —
 *     the same door the details view's **Start** uses. A legacy draft account
 *     with no request opens its details view instead;
 *   * `resume` (Draft) → the wizard at its parked draft (`resumePath`, the ONE
 *     builder for `?parked=`), which keeps the PO's 2026-09-29 ruling
 *     (`DEF-CUS-7900`: a draft opens in the wizard) on the row's icon;
 *   * `view` → the details view.
 *
 * `null` when the row has nowhere to go — and then no icon is drawn at all
 * (a control over no destination is law 2's mirror).
 */
export function moveInActionPath(row: MoveInRow): string | null {
  switch (row.action) {
    case "start":
      return row.request !== null && row.request !== undefined && row.request.id !== ""
        ? `${MOVE_IN_WIZARD_ROUTE}?${MOVE_IN_REQUEST_PARAM}=${encodeURIComponent(row.request.id)}`
        : moveInDetailsPath(row);
    case "resume":
      return (row.park_id ?? "") === ""
        ? moveInDetailsPath(row)
        : resumePath({ id: String(row.park_id), flow: "move_in" });
    default:
      return moveInDetailsPath(row);
  }
}

/** ⚠ **`{ icon: … }` ENTRIES RENDERED AS `<entry.icon />`, NOT BARE
 *  FUNCTIONS UNDER AN INDEX (`DEF-GOV-10106`).** As `ACTION_ICONS[action]`
 *  read into a local and drawn `<Icon />`, `ReviewIcon` was on screen on every
 *  *To approve* row while `G40` — which sees a lookup table only as a
 *  `<x.prop` render beside a `prop: Name` entry in one file — reported it as
 *  rendered by nothing. Same table, same icons; the shape is the one the gate
 *  can read. */
const ACTION_ICONS: Record<string, { icon: () => JSX.Element }> = {
  review: { icon: ReviewIcon },
  start: { icon: PlayIcon },
  resume: { icon: PencilIcon },
  view: { icon: EyeIcon },
};

const ACTION_LABELS: Record<string, string> = {
  review: "Review {{reference}}",
  start: "Start {{reference}}",
  resume: "Resume {{reference}}",
  view: "View {{reference}}",
};

/** The row's one icon, with its tooltip and a screen-reader name that says
 *  WHICH move-in (P2.02) — *"Review SR-26-0014"*, never a bare *"Review"*
 *  read out six times down a table. */
export function MoveInRowAction(props: { row: MoveInRow }) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const { row } = props;
  const action = row.action ?? "view";
  const to = moveInActionPath(row);
  const entry = ACTION_ICONS[action];
  if (to === null || entry === undefined) {
    return <></>;
  }
  const label = t(`customers.moveIns.rowAction.${action}`, {
    reference: row.reference ?? "",
    defaultValue: ACTION_LABELS[action],
  });
  return (
    // The kit's ghost row action (B14 rules 15 and 44): image 01 draws each
    // icon in a bordered square, and our component kit decides how a row
    // action is built — the same glyph button every other list uses.
    <span className="inline-flex" data-move-in-action={action}>
      <RowActions>
        <RowActionLink label={label} icon={<entry.icon />} to={tenantPath(to)} />
      </RowActions>
    </span>
  );
}

/** Image 01's STEP cell: `—` before anybody started, `3 of 4 · Billing` on a
 *  draft, `Done` once the move-in is complete. */
export function MoveInStepCell(props: { step: MoveInRow["step"] }) {
  const { t } = useTranslation();
  const step = props.step;
  if (step.done === true) {
    return (
      <span data-step-done="">{t("customers.moveIns.step.done", { defaultValue: "Done" })}</span>
    );
  }
  if (step.reached === null) {
    return <span aria-label={t("customers.moveIns.cell.none", { defaultValue: "None" })}>—</span>;
  }
  const name =
    step.id === null || step.id === undefined
      ? step.name ?? ""
      : t(`customers.moveIns.stepName.${step.id}`, { defaultValue: step.name ?? step.id });
  return (
    <span data-step-progress={`${step.reached}/${step.of}`}>
      {name === ""
        ? t("customers.move.step.progress", {
            defaultValue: "{{reached}} of {{of}}",
            reached: step.reached,
            of: step.of,
          })
        : t("customers.moveIns.step.progressNamed", {
            defaultValue: "{{reached}} of {{of}} · {{name}}",
            reached: step.reached,
            of: step.of,
            name,
          })}
    </span>
  );
}

/** Image 01's OPENING READ: `—` before Complete, `Waiting` while a meter is
 *  unread, the readings with their units once taken. */
export function MoveInOpeningReadCell(props: { read: MoveInOpeningRead | null | undefined }) {
  const { t } = useTranslation();
  const read = props.read;
  if (read === null || read === undefined || read.state === null) {
    return <MoveAbsenceValue absence={read?.unavailable ?? null} marker="opening-read" />;
  }
  if (read.state !== "taken") {
    return (
      <span
        data-opening-read={read.state}
        title={read.missing.length > 0 ? read.missing.join(", ") : undefined}
      >
        {t("customers.moveIns.openingRead.waiting", { defaultValue: "Waiting" })}
      </span>
    );
  }
  if (read.readings.length === 0) {
    return (
      <span data-opening-read="taken">
        {t("customers.moveIns.openingRead.taken", { defaultValue: "Taken" })}
      </span>
    );
  }
  return (
    <span data-opening-read="taken" className="tabular-nums">
      {read.readings
        .map((reading) =>
          reading.reading === null
            ? reading.register
            : [formatQuantity(reading.reading), reading.unit ?? ""].join(" ").trim(),
        )
        .join(" · ")}
    </span>
  );
}

/** Image 01's DEPOSIT: the amount held, or `—`. The reason a deposit is not
 *  shown stays in the tooltip (rule 33: rationale is zero words on screen). */
export function MoveInDepositCell(props: { deposit: MoveDepositCell | null | undefined }) {
  const deposit = props.deposit;
  if (
    deposit !== null &&
    deposit !== undefined &&
    deposit.recorded &&
    deposit.amount !== null &&
    deposit.amount.display !== null &&
    deposit.currency !== null
  ) {
    return (
      <span data-deposit-display={deposit.amount.display}>
        <MoneyCell amount={deposit.amount.display} currency={deposit.currency} />
      </span>
    );
  }
  return <MoveAbsenceValue absence={deposit?.unavailable[0] ?? null} marker="deposit" />;
}

export function moveInsTableConfig(
  t: (key: string, params?: Record<string, unknown>) => string,
  cells: {
    /** The reference, as a routed door. Passed in because this function takes
     *  no router, so a config case can be tested without mounting a page. */
    reference: (row: MoveInRow) => JSX.Element;
    moveInDate: (row: MoveInRow) => JSX.Element;
    action: (row: MoveInRow) => JSX.Element;
  },
): TableConfig<MoveInRow> {
  return {
    screenId: MOVE_INS_TABLE_SCREEN,
    // Five kinds of row, five kinds of id; the reference first because every
    // kind but a numberless legacy draft carries one, and it is unique.
    getRowId: (row) =>
      row.reference ?? row.park_id ?? row.request_id ?? row.job_id ?? row.account_id ?? "",
    searchFields: ["customer", "unit", "reference"],
    // Image 01's prompt, which is also the server's `search.hint`.
    searchPlaceholder: "customers.moveIns.list.searchHint",
    // `BR-CUS-1046` — newest first by default.
    defaultSort: { sort: "created", dir: "desc" },
    columns: [
      {
        key: "reference",
        label: t("customers.moveIns.col.reference", { defaultValue: "Reference" }),
        identity: true,
        cell: cells.reference,
      },
      {
        key: "customer",
        label: t("customers.moveIns.col.customer", { defaultValue: "Customer" }),
        cell: (row) =>
          row.reopened ? (
            // CR-181-BRC10 F3 — a returning customer's own account, reopened.
            <span className="flex flex-col gap-1">
              <MoveCustomerCell name={row.customer} number={null} absence={row.customer_absence ?? null} />
              <span className="text-sm text-neutral-700" data-move-in-reopened={row.reopened.account_no}>
                {t("customers.moveIn.reopen.reopened", { account: row.reopened.account_no })}
              </span>
            </span>
          ) : (
            <MoveCustomerCell name={row.customer} number={null} absence={row.customer_absence ?? null} />
          ),
      },
      {
        key: "unit",
        label: t("customers.moveIns.col.unit", { defaultValue: "Unit" }),
        cell: (row) => <span>{row.unit ?? "—"}</span>,
      },
      {
        key: "services",
        label: t("customers.moveIns.col.services", { defaultValue: "Services" }),
        cell: (row) =>
          row.services === null || row.services === undefined || row.services.length === 0 ? (
            <span>—</span>
          ) : (
            <ServiceSquares services={row.services} />
          ),
      },
      {
        key: "move_in_date",
        sortable: true,
        label: t("customers.moveIns.col.moveInDate", { defaultValue: "Move-in date" }),
        cell: cells.moveInDate,
      },
      {
        key: "step",
        label: t("customers.moveIns.col.step", { defaultValue: "Step" }),
        cell: (row) => <MoveInStepCell step={row.step} />,
      },
      {
        key: "opening_read",
        label: t("customers.moveIns.col.openingRead", { defaultValue: "Opening read" }),
        cell: (row) => <MoveInOpeningReadCell read={row.opening_read} />,
      },
      {
        key: "deposit",
        numeric: true,
        label: t("customers.moveIns.col.deposit", { defaultValue: "Deposit" }),
        cell: (row) => <MoveInDepositCell deposit={row.deposit} />,
      },
      {
        key: "state",
        label: t("customers.moveIns.col.state", { defaultValue: "State" }),
        cell: (row) => (
          <span className="whitespace-nowrap" data-move-in-status={row.status ?? ""}>
            <StatusPill tone={moveInStatusTone(row.status ?? "")}>
              {moveInStatusLabel(row, t)}
            </StatusPill>
          </span>
        ),
      },
      {
        // The column holds a control; a heading over it would label a verb
        // the icon's own name already says.
        key: "action",
        label: "",
        cell: cells.action,
      },
    ],
    filters: moveInFilterGroups([], t),
  };
}

export function moveInsQueryKey(state: TableRequestState): readonly unknown[] {
  // Filters, sort and direction are IN THE KEY, or react-query answers a
  // changed request from the page already in cache and the list never moves.
  return [
    "move-ins",
    state.q,
    state.page,
    state.per,
    state.filters,
    state.sort,
    state.dir,
  ];
}

/**
 * Image 01's FIVE tiles, each the SERVER's count over the whole list — never
 * the page, never the search (§9.LIST). To approve is drawn in the accent
 * colour because it is the one that waits on a clerk.
 *
 * ⚠ **A TILE THE SERVER DID NOT SEND DRAWS `—`, NEVER `0`** — `0` is a claim
 * that there are none, and a browser holding an older server's answer would
 * make it about a figure nobody counted.
 */
export function moveInsKpis(
  payload: MoveInList | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
): KpiTile[] {
  const kpis = payload?.kpis;
  const figure = (value: number | null | undefined): ReactNode =>
    typeof value === "number" ? value : "—";
  const toApprove = kpis?.to_approve;
  return [
    {
      id: "to-approve",
      label: t("customers.moveIns.kpi.toApprove", { defaultValue: "To approve" }),
      value:
        typeof toApprove === "number" && toApprove > 0 ? (
          <span className="text-accent">{toApprove}</span>
        ) : (
          figure(toApprove)
        ),
    },
    {
      id: "not-started",
      label: t("customers.moveIns.kpi.notStarted", { defaultValue: "Not started" }),
      value: figure(kpis?.not_started),
    },
    {
      id: "drafts",
      label: t("customers.moveIns.kpi.drafts", { defaultValue: "Drafts" }),
      value: figure(kpis?.drafts),
    },
    {
      id: "starting-this-week",
      label: t("customers.moveIns.kpi.startingThisWeek", { defaultValue: "Starting this week" }),
      value: figure(kpis?.starting_this_week),
    },
    {
      id: "waiting-on-a-read",
      label: t("customers.moveIns.kpi.waitingOnARead", { defaultValue: "Waiting on a read" }),
      value: figure(kpis?.waiting_on_a_read),
    },
  ];
}

export interface MoveInsTabProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function MoveInsTab(props: MoveInsTabProps) {
  const { t } = useTranslation();
  const translate = (key: string, params?: Record<string, unknown>): string => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props);

  const config = useMemo(
    () =>
      moveInsTableConfig(translate, {
        reference: (row) => {
          const to = moveInDetailsPath(row);
          return to === null ? (
            <MoveAbsenceValue absence={row.move_no_unavailable} marker="reference" />
          ) : (
            <Link
              to={tenantPath(to)}
              className="whitespace-nowrap tabular-nums text-accent underline underline-offset-2"
              data-move-in-reference={row.reference ?? ""}
            >
              {row.reference}
            </Link>
          );
        },
        moveInDate: (row) =>
          row.move_in_date === null ? (
            <MoveAbsenceValue absence={row.move_in_date_absence ?? null} marker="move-in-date" />
          ) : (
            <DateCell value={row.move_in_date} timeZone={timeZone} dateFormat={dateFormat} />
          ),
        action: (row) => <MoveInRowAction row={row} />,
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, timeZone, dateFormat],
  );

  // DEF-664 — the table state is THIS COMPONENT'S; the query string belongs to
  // the Accounts page this tab sits inside.
  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  const listQuery = useQuery({
    queryKey: moveInsQueryKey(state),
    queryFn: () =>
      listMoveIns(
        {
          q: state.q,
          page: state.page,
          per: state.per,
          filters: state.filters,
          sort: state.sort,
          dir: state.dir,
        },
        client,
      ),
  });

  // The Service dimension's vocabulary is the TENANT's enabled set (BR-MET-003),
  // never the services on the page in hand, which would differ per page.
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const serviceOptions = enabledServiceRows(servicesQuery.data).map((row) => ({
    value: row.service,
    label: row.name,
  }));

  return (
    <div data-embedded="" data-screen={MOVE_INS_TABLE_SCREEN}>
      <KPIStrip
        kpis={moveInsKpis(listQuery.data, translate)}
        loading={listQuery.isPending}
        tiles="count"
      />
      <DataTable<MoveInRow>
        config={config}
        filterBarSlot={
          <FilterBar
            filters={offerableFilters(moveInFilterGroups(serviceOptions, translate))}
            state={state}
            onStateChange={setState}
          />
        }
        state={state}
        onStateChange={setState}
        rows={rowsOf<MoveInRow>(listQuery.data)}
        totalRows={totalOf(listQuery.data)}
        loading={listQuery.isPending}
        error={
          listQuery.isError
            ? {
                reason: t("customers.moveIns.list.loadFailed", {
                  defaultValue: "The move-ins could not be loaded.",
                }),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        empty={{
          title: t("customers.moveIns.list.emptyTitle", { defaultValue: "No move-ins" }),
          helper: t("customers.moveIns.list.emptyHelperNow", { defaultValue: "Move-ins appear here." }),
          ctaLabel: t("customers.moveIns.action.new", { defaultValue: "+ New move-in" }),
          onCta: () => navigate(tenantPath(MOVE_IN_WIZARD_ROUTE)),
        }}
      />
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W5 (the Move-ins tab, frontend half) · B18 §5.5.1 · §5.5.2 ·
//         §5.5.7 · §5.7.3 · `apps/customers/move_reads.py` · `GET /move-ins` ·
//         BR-CUS-018 · BR-CUS-022 · BR-CUS-023 · BR-CUS-024 · BR-CUS-080 ·
//         DEF-664 (the embedded rule) · DEF-332 (ids are attributes) ·
//         hard-won law 8 (no story owns this tab)
// generated: 2026-08-25 by lane MOVES (the last two Accounts tabs)
// amended: 2026-08-26 by lane SCREENVOICE — **DEF-731**. The server's absence
//         `detail` was rendered to the DOM, as the paragraph under the table and
//         as every cell tooltip, so a clerk read `service_requests`, `accounts`,
//         `B18 §5.5.2` and `opened_at`. `ABSENCE_COPY` + `absenceCopy()` now
//         author the sentence off the absence's `code`; `detail` reaches nothing
//         a person can read. The reasoning is in `ABSENCE_COPY`'s docstring and
//         stays in `move_reads.py` as the diagnostic it is.
// amended: 2026-08-26 by lane MOVEENTRY — **PO ruling** *"-Enable Move in
//         /move out"*. The empty state's `+ New move-in` is LIVE, onto
//         `/move-ins/new`. ⚠ Its `ctaReason` is DELETED rather than reworded:
//         *"A move-in starts from the unit the occupant is taking, so it begins
//         on the unit's own page"* named a control that has NEVER existed — no
//         unit page in this product carries a move-in action — so a clerk who
//         believed it went hunting for a button that was not there (hard-won law
//         1). The first clause is now the DESIGN of the standalone wizard's step
//         1. The key was a code-only `defaultValue`, so no catalogue row exists
//         to remove; that is recorded in `scratchpad/newkeys-MOVEENTRY.json` so
//         the sentence is not re-introduced.
// checklist: A=n/a(the backend half is `move_reads.py` in this same lane) B✔
//         C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: **[CR-045 wave G 2026-08-27 · `DEF-1702`]** E2 **the segment strip
//         is DELETED and the toolbar carries a REAL `+ Filter ▾`.** The strip
//         drew five states, three servable, and was handed
//         `onSelect={() => undefined}` — it sat in the slot B14 rule 12 reserves
//         for the filter and narrowed nothing, which is how this tab was counted
//         as *having* a filter twice while having none. `f.state` is wired now
//         over the three codes `MOVE_IN_STATES` marks `supported`, applied by the
//         server before paging · E3 **`in_progress` and `done` are NOT OFFERED
//         rather than offered disabled** — a disabled SEGMENT could carry its
//         reason on a tooltip and a filter OPTION cannot, and an option that
//         returns an empty list forever reads as *"there are none"*, which is
//         false rather than missing. Both absences are still served and still
//         rendered by the cells that state them · E3 **this tab has NO SEARCH BOX
//         and `move_ins_list` has taken `q` since it shipped** — filed as
//         `DEF-1784`, not fixed here · E3 **the DEPOSIT cell never prints `waived` and never prints
//         `—`** — the disposition has no column, so a zero renders the REASON
//         and the amount renders only when the server says one is recorded ·
//         E3 the STEP bar draws `of` EMPTY segments and no numerator; there is
//         no wizard store · E3 READS renders the absence — customers publishes
//         no metering read seam, so `taken` / `due` appear nowhere on the tab ·
//         E3 `DEPOSITS TO CARRY OVER` renders its REASON in the value slot
//         rather than `0`, and `OLDEST` renders `—` rather than `0 days` · E3
//         two of five state segments are OFF (`In progress`, `Done`) carrying
//         the server's sentence; `due` is a MINTED code and is marked as one ·
//         E3 no row action and no `Completed — opens at the review step` hover:
//         both reopen a wizard at a step this product cannot restore (law 2) ·
//         E3 no `+ New move-in` primary — the empty-state CTA is disabled with
//         its reason · E3 no sortable column: the server takes no `sort` · E3
//         the STATE tone mapping is the SCREEN's; B18 draws no tone · E3 the
//         table `screenId` is namespaced off S19 because A1 allocates this
//         worklist no id and no story owns it (law 8) — OWED
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
