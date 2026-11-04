// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W5 — **the MOVE-OUTS tab, FRONTEND half**, and the last of
//           the Accounts screen's eight. Until now it rendered
//           `<ArrivesWith … tracks="OQ-346" />`; OQ-346 CLOSED on 2026-08-24
//           (→ BR-CUS-082), so the panel was tracking a question that no longer
//           existed while the tab stayed empty — hard-won law 2 with a stale
//           citation on top.
// Rules:    BR-CUS-015 / DEF-127 (`accounts.balance` is a CACHE — the figure
//           here is the LEDGER's or an absence) · BR-CUS-030 (move-out closes
//           the account) · BR-CUS-031 (the final bill, which billing does not
//           publish) · BR-CUS-057 (deposit interest — CONFIRMED, NOT BUILT) ·
//           BR-CUS-081 / BR-CUS-082 (the two settlement landings the PO ruled
//           on 2026-08-24) · BR-MET-036 (the unit derives back to vacant) ·
//           BR-SHL-046 (both bars are driven by ONE declared step list — its
//           NUMBER moved to FOUR on 2026-09-24 and its MECHANISM did not;
//           `moveShared.MOVE_OUT_STEPS` is that list) · BR-SHL-010 ·
//           BR-SHL-011 (this list owns NO query string — DEF-664) ·
//           BR-SHL-025 · CLAUDE.md hard rule 2 · B14 rules 5, 12, 16, 17, 19,
//           20, 21
// Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.6.1 (the five
//           tiles) · §5.6.2 (the eight columns) · §5.6.4 (the shortfall
//           decision) · §5.6.7 (the six drawn rows)
// Tests:    07-frontend/src/features/customers/MoveOutsTab.test.tsx
// Impacts:  AccountsListPage.tsx (the mount + `ACCOUNTS_BUILT_TABS`) ·
//           06-backend `GET /move-outs` (REPORTED — `api.py` is another lane's)
//
// ⚠ AMENDED 2026-09-19 — **THE LIST REBUILT TO THE ACCOUNTS BLUEPRINT p117**,
//           PO-ruled the same day. Four filed rows close here:
//           `DEF-CUS-5897` (five KPI tiles where the drawing has three) ·
//           `DEF-CUS-5898` (~78 words of rationale under the table) ·
//           `DEF-CUS-5899` (the Settlement cell stacked three lines where the
//           drawing has one direction) · `DEF-CUS-5900` (every row a dead end
//           — no reference link, no account link, no `↗ Open`). Two are NOT
//           closed here and are named where they bite: `DEF-CUS-5896`'s
//           SERVER half (no reference search leg) and `DEF-CUS-5901` (this
//           list says `Closed`, the record says `completed`).
// Rules+:   B14 rule 12 (the toolbar's grammar) · rule 32 (one sentence per
//           section, no internal code in clerk copy) · rule 33 (five caps, and
//           RATIONALE is zero words on screen) · rule 41 (the product matches
//           the blueprint) · rule 42 (built from the drawing AS AN IMAGE —
//           p117 rendered at scale 2 and read, never from the text layer)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · THIS TAB SHOWS MOVE-OUTS THAT HAVE HAPPENED, AND B18 DRAWS FOUR THAT
//     HAVE NOT. THE DIFFERENCE IS THE FIRST THING THE SCREEN SAYS.
// ══════════════════════════════════════════════════════════════════════════
// `services.move_out` writes `closed_at`, the terminal status and the agreement
// end dates in ONE commit, and `accounts` carries nothing about leaving before
// that: no `scheduled_move_out_on`, no move-out state, no step. So a move-out
// in flight is not a row anywhere in this product.
//
// §5.6.7 draws six rows and FOUR of them are in exactly that state — `Ridge
// Coffee Co.` on Sep 05, `Delgado, Pilar` on Sep 09, `Northwind Mfg.` on Sep 12
// — accounts that are still LIVE and still billing. This tab cannot show them,
// so three of B18's four state segments render DISABLED carrying the server's
// own sentence, which names the columns it would take (BR-SHL-025).
//
// ⚠ **AND THE WINDOW HAS NO CLOSING EDGE EITHER.** Billing publishes no
// per-account final bill, so nothing ever takes a row off this list.
//
// ⚠ **BOTH FACTS WERE STATED UNDER THE TABLE UNTIL 2026-09-19 AND ARE NOW
// STATED HERE (`DEF-CUS-5898`).** That paragraph read *"Stated under the table
// rather than left for a clerk to discover after the first hundred closures"* —
// and B14 rule 33, ratified 2026-08-30, puts RATIONALE at ZERO words on screen.
// The PO ruled the ~78 words off on 2026-09-19: *"you ahve to follow our UI
// rules - this is correct screen - too much text"*. The server still SENDS both
// codes, `absenceCopy` still spells both, and the tab carries them on its root
// as `data-list-absences` — so nothing was deleted from the wire and the facts
// live where rule 33 says they belong: in the code and the register.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · THE SETTLEMENT CELL SHOWS NO VERDICT, AND THAT IS THE ENGINE'S RULE
// ══════════════════════════════════════════════════════════════════════════
// §5.6.2 draws SETTLEMENT as `refunded $88.40` · `refund $11.20` · `settles
// exactly` · **`SHORT $175.20`** in the accent · `—`, and every one of those is
// a LANDING. `MoveOutSettlement.landing`, verbatim:
//
//   *"any gap → **no landing**. Not a sixth outcome: a missing deposit interest
//   understates `applied`, biasing the answer toward `short`; a missing final
//   bill understates `outstanding`, biasing it toward `refund_due`. **One of
//   those two directions posts a cheque.**"*
//
// Both gaps are open on every row of this tab — billing publishes no final bill
// and BR-CUS-057's interest accrual is confirmed and unbuilt. So `landing` is
// `null` on every row and this screen renders the two TERMS the server actually
// read, each labelled, plus the reason no verdict is stated.
//
// ⛔ **`SHORT` IS THE WORD THIS CELL MUST NOT GUESS AT.** §5.6.2's footnote is
// *"a shortfall is shown in the accent because it needs a decision — nothing
// settles itself"*, and §5.6.4 forces a four-way decision off the back of it.
// Deriving `short` here from deposit-minus-outstanding would skip the final
// bill, the unapplied credit, the export credit, the sibling accounts and any
// open dispute — and would put a customer into BR-CUS-082's collections ladder
// on a figure nobody computed. The whole settlement, with every term, is
// `GET /accounts/{id}/close-impact` on the account's own page.
//
// ⚠ **AND THE OUTSTANDING FIGURE IS THE LEDGER'S OR IT IS AN ABSENCE**
// (DEF-127). `accounts.balance` is a cache nothing writes; serving it once told
// a customer owing $108.88 that they owed nothing. `display: null` means the
// books could not be asked, and on THIS column `$0.00` would read as *this
// customer is square and owed nothing back*.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

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
import { StatusPill } from "@/components/StatusPill";
import { defaultRequestState } from "@/components/tableTypes";
import type {
  TableConfig,
  TableFilterConfig,
  TableRequestState,
} from "@/components/tableTypes";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

// `DEF-CUS-5994` — `resumePath` is the ONE builder for `?parked=<id>` and was
// already imported here; the three controls join it now that the panel that
// used to carry them is gone.
import {
  ParkedBadge,
  ParkedDiscardDialog,
  ParkedDraftActions,
  ParkedWhyCell,
  // ⚠ `resumePath` is gone from this import as of 2026-09-25
  // (`DEF-CUS-6759`): this tab no longer builds the resume address itself.
  // `ParkedDraftActions` draws the Resume icon and goes through the same one
  // builder, so the two surfaces still cannot disagree about the handle —
  // there is simply one caller now instead of two.
} from "./parkedDrafts";
import type { ParkedDiscardTarget } from "./parkedDrafts";
import {
  MoveAbsenceNote,
  MoveCustomerCell,
  MoveReadsCellView,
  MoveStepBar,
  MOVE_OUT_LIST_FILTERS,
  absenceCopy,
  requireMoveData,
} from "./MoveInsTab";
import type {
  MoveCustomerAbsence,
  MoveListQuery,
  MoveReadsCell,
  MoveStateSegment,
  MoveStepCell,
} from "./MoveInsTab";
import { RecordNumberCell } from "./transferDisconnectShared";
import { accountDetailPath } from "./customersShared";
import { moveRecordPath } from "./MoveRecordPage";
import { MOVE_OUT_WIZARD_ROUTE } from "./moveShared";
import { rowsOf, totalOf, worklistFilterParams } from "./worklistEndpoints";
import type { WorklistAbsence, WorklistMoney } from "./worklistEndpoints";

/** The screen id `TableConfig` keys its column preference on. A1 allocates S20
 *  to the move-out WIZARD and nothing to this worklist, and **no story owns
 *  it** — hard-won law 8, filed by `move_reads.py` for the backend half.
 *  Namespaced so two tables cannot share one saved column set (DEF-647). */
export const MOVE_OUTS_TABLE_SCREEN = "S20.moveOuts";

/**
 * ⚠⚠ **THE ROW ACTION IS AN ICON SINCE 2026-09-25, AND IT WAS A BORDERED
 * `↗ Open` BUTTON UNTIL THEN (`DEF-CUS-6759`).**
 *
 * **PO, verbatim, looking at `v2.351.98`:** *"few bugs on Move out - list
 * screen action it should be icons not buttons"*. That **supersedes the PO's
 * own ruling of 2026-09-19** (*"this si all good - please update it"*), which
 * accepted p117's drawn text button on this list and on the Move-ins list. The
 * supersession is stated here rather than assumed, and the old ruling is NOT
 * re-put to them — asking again is hard-won law 13's bug.
 *
 * ⚠ **AND IT IS ALSO WHAT B14 RULE 15 ALWAYS SAID** — *"row actions are ICONS
 * with tooltips, never text links"* — so this list now agrees with the
 * Disconnects list, which reached the same answer from the drawing's other
 * side: p142 draws a bordered `↗ Open` there too and that lane built an icon,
 * because **where a drawing and our UI standard disagree about how a control is
 * BUILT, the standard wins** (B14 rule 44, rule 38's scope removed). WHAT the
 * cell contains is still the drawing's: one action, open this move-out.
 *
 * ⚠ **NOTHING NEW IS WRITTEN — `components/RowActions.tsx` IS MOUNTED** (B14
 * rule 43). That component exists precisely to end five hand-rolled action
 * cells, and it is the one place an `aria-label` on an icon is a REQUIRED prop,
 * so a glyph cannot ship without an accessible name. The hoisted
 * `buttonClasses("secondary", "sm")` it replaces is gone with it — the kit's
 * `row` tier (`w-8 h-8`) is what an icon belongs in, and the only reason this
 * file used `sm` was that it held a WORD.
 *
 * ⚠ **THE SIBLING MOVE-INS TAB STILL DRAWS THE TEXT BUTTON, AND IT IS REPORTED
 * RATHER THAN EDITED FROM HERE** — `DEF-CUS-6771`. The PO reported the
 * Move-outs list; that file is another lane's and a second lane rewriting its
 * button is how two fixes become one revert (law 11).
 */

/**
 * §5.6.2's SETTLEMENT cell.
 *
 * ⛔ **`landing` IS `null` ON EVERY ROW AND MUST NEVER BE RENDERED AS A
 * VERDICT** — §2. `landings` is the engine's own closed vocabulary, served so a
 * screen cannot invent a sixth; nothing here reads it except to prove it is not
 * being drawn from.
 */
export interface MoveOutSettlementCell {
  currency: string;
  landing: string | null;
  landings: string[];
  complete: boolean;
  sentence: string | null;
  deposit_held: WorklistMoney;
  /** ⛔ ALWAYS `null` — BR-CUS-057's accrual is CONFIRMED and NOT BUILT. */
  deposit_interest: WorklistMoney | null;
  /** ⚠ `display: null` MEANS THE BOOKS COULD NOT BE ASKED, NOT ZERO. */
  outstanding: WorklistMoney;
  outstanding_source: string | null;
  /**
   * ⚠ **THE FIGURE p117's ONE-LINE CELL DRAWS, AND `GET /move-outs` DOES NOT
   * SERVE IT YET (2026-09-19).** The drawing renders `Short by $186.40` /
   * `Refund $42.15` — a direction AND an amount — and `move_out_settlement`
   * computes exactly that as `net`. `move_out_settlement_cell` hard-codes
   * `landing: None`, `complete: False` and serves no `net`, so this is
   * `undefined` on every row today and the cell falls through to the absence.
   *
   * ⛔ **IT IS NOT DERIVABLE HERE AND MUST NEVER BE DERIVED HERE.**
   * `outstanding − deposit_held` skips the final bill, the deposit interest,
   * the unapplied credit, the sibling accounts and any open dispute — §2 of
   * this file's header — and one of those two directions posts a cheque.
   *
   * ⚠ OPTIONAL on the type, because a browser holding a cached bundle can meet
   * a server that predates the key; every read of it is guarded.
   */
  net?: WorklistMoney | null;
  unavailable: WorklistAbsence[];
}

/**
 * ⚠ **`account` IS A MOVE-OUT THAT HAPPENED · `parked_move_out` IS ONE STILL IN
 * A CLERK'S HANDS** (PO ruling 2026-09-19, verbatim **`yes`**, asked whether
 * this list should show move-outs that have not finished yet).
 *
 * Read the KIND, never infer it from an absent field: an inference is a second
 * implementation of a rule, and this one is the difference between *finished*
 * and *not started yet*.
 */
export const MOVE_OUT_ROW_KIND_ACCOUNT = "account";
export const MOVE_OUT_ROW_KIND_PARKED = "parked_move_out";

export interface MoveOutRow {
  /** CR-039 wave D 17–19 — the record `services.move_out` now leaves for the
   *  job (PO 2026-08-27: *"you cna keep them as records for audit perpuses"*).
   *  The SAME pair `transfers` and `disconnects` serve, so `RecordNumberCell`
   *  reads all four flows without learning a fourth shape.
   *
   *  ⛔ **NULL ON EVERY UNFINISHED ROW, AND THAT IS A DECISION.** Only a
   *  move-IN draft is numbered while it is in hand (`CR-122-BRC06`), so an
   *  unfinished move-out carries `parked_move_out_has_no_reference` here. */
  move_no: string | null;
  move_no_unavailable: WorklistAbsence | null;
  /** Which kind of row this is — `MOVE_OUT_ROW_KIND_*`. */
  row_kind: string;
  /** The draft's own handle, for the resume. `null` on a finished row.
   *  ⛔ It is NEVER rendered: B14 rule 31 keeps a database id off the screen,
   *  and this only ever reaches an `href`. */
  park_id: string | null;
  /** ⚠ NULLABLE NOW. The move-out wizard can be opened and parked before an
   *  account is chosen, and a draft joins to nothing (BR-SHL-048 (a)), so the
   *  account it named can also have gone. `account_absence` says which. */
  account_id: string | null;
  account_no: string | null;
  account_absence: WorklistAbsence | null;
  customer: string | null;
  customer_no: string | null;
  customer_source: string | null;
  customer_absence: MoveCustomerAbsence | null;
  unit_id: string | null;
  unit: string | null;
  move_out_date: string | null;
  /** Why there is no date — the step that asks for one has not been reached. */
  move_out_date_absence: WorklistAbsence | null;
  /** `of` is the SERVER's `MOVE_OUT_STEP_COUNT`, whatever it says — never a
   *  literal here. ⚠ **IT WAS SIX UNTIL 2026-09-24 AND IS NOW FOUR** (PO:
   *  *"i okay with these steps"*), old 3+4 and 5+6 merged. B18 §5.6.2's `of 4`
   *  is still SUPERSEDED and is NOT this four: that one was a drawn count that
   *  never matched the wizard, which is the defect BR-SHL-046 closed.
   *  ⚠ `reached` is a REAL number on an unfinished row and `null` on a closed
   *  one — see `MoveStepBar`, and the header of this file for why the closed
   *  one must never be derived. */
  step: MoveStepCell;
  final_read: MoveReadsCell;
  settlement: MoveOutSettlementCell;
  state: string;
  leaving_this_week: boolean;
  /** What an unfinished move-out is waiting for, in the clerk's own words.
   *  Empty means a draft rather than a park; the STATE is what carries that. */
  waiting_on: string | null;
  park_note: string | null;
  remind_on: string | null;
  parked_at: string | null;
  age_days: number | null;
  /** ⚠ **ADDED WITH THE PANEL'S REMOVAL (`DEF-CUS-5994`), AND IT IS THE ONE
   *  FIELD THAT WOULD HAVE GONE MISSING.** Every other line the panel drew was
   *  already on the row beside it; `Parked by` was not, and it is what `CR-035`
   *  amendment 1 put in place of the mine/everyone's toggle it dissolved — so
   *  dropping it would have quietly re-opened a closed question. */
  parked_by_name?: string | null;
}

export interface MoveOutKpis {
  /** ⚠ NOT *"customers leaving"*. `open_means` names the narrower thing this
   *  product can count — see §1. */
  open: number;
  open_means: string;
  open_unavailable: WorklistAbsence;
  leaving_this_week: number;
  /**
   * ⚠ **`final_reads_due` IS DERIVED NOW (2026-08-26, CR-038 W9 · DEF-786).**
   * It sat in the "three that are `null` and must NEVER render as `0`" block
   * below with a NON-nullable absence beside it, which is how the tile could
   * only ever draw its reason. The read seam answers, so this is a REAL COUNT
   * — closed move-outs with a meter unread since the close — and the absence
   * is served only where the seam does not resolve.
   *
   * ⛔ **THE `0` RULE IS UNCHANGED AND STILL LOAD-BEARING.** `FINAL READS DUE ·
   * 0` says every meter has been read, which is good news to the one person
   * paid to act on the bad kind; a `0` may be drawn ONLY when the server
   * derived it, never as a fallback for a `null`.
   */
  final_reads_due: number | null;
  final_reads_due_unavailable: WorklistAbsence | null;
  /** What the figure counts, in the server's own words — the `open_means`
   *  precedent, so the tile cannot be captioned into meaning something else. */
  final_reads_due_means?: string;
  /** Closed move-outs EXCLUDED from the count because their unit has no meter
   *  at all. Served beside the figure so the exclusion is visible. */
  final_reads_due_meterless?: number;
  /**
   * ⚠ **STILL SERVED, NO LONGER DRAWN (PO 2026-09-19, *"Drop it"*, twice).**
   * These four keys have NO reader on this screen since p117's three-tile strip
   * landed. They are kept on the type because `GET /move-outs` still sends
   * them and a reader that drops a served key starts lying about the contract —
   * and because deleting a served field is the `DEF-CUS-3653` shape in reverse:
   * an absence is invisible to every check this repo has, so the field being
   * here, with this note, is what makes the drop findable.
   *
   * ⛔ The `0` rule that governed them is unchanged and still true of them:
   * `SHORTFALLS TO DECIDE · 0` says every closing account is square and
   * `REFUNDS TO PAY · 0` says nobody is owed their deposit back. Neither is
   * derivable — both need a LANDING (§2) — so if either tile is ever wanted
   * back it comes back as an absence, never as a zero.
   */
  shortfalls_to_decide: number | null;
  shortfalls_to_decide_unavailable: WorklistAbsence;
  refunds_to_pay: number | null;
  refunds_to_pay_unavailable: WorklistAbsence;
  period_basis: string;
  as_of: string;
}

export interface MoveOutList {
  rows: MoveOutRow[];
  kpis: MoveOutKpis;
  page: number;
  per: number;
  total: number;
  pages: number;
  columns: string[];
  states: MoveStateSegment[];
  /** CR-045 wave D · D.10 — the `f.<name>` names this list accepts. */
  filters?: string[];
  /** The windows `f.closed` accepts — `MOVE_OUT_CLOSED_WINDOWS`, served so the
   *  screen cannot offer a bucket the queryset does not know. `days` is the
   *  number the option's own label is built from. */
  closed_windows?: { code: string; days: number }[];
  search: { hint: string; min_chars: number; legs: string[]; unavailable: WorklistAbsence[] };
  exclusion: { callout: string; contract: string[]; half_account_ids: string[] };
  unavailable: WorklistAbsence[];
  as_of: string;
}

/**
 * `GET /move-outs`.
 *
 * ⛔ **NO `state` PARAMETER, AND THAT IS A SCHEMA FINDING RATHER THAN A GAP.**
 * `MOVE_OUT_STATES` marks exactly ONE code `supported` — `closed` — because
 * `services.move_out` writes `closed_at`, the terminal status and the agreement
 * end dates in ONE commit, and this product holds no move-out before it
 * closes. A state filter here would offer a single option that changes nothing.
 *
 * ✅ **`f.closed` IS WHAT THIS LIST CAN HONESTLY BE ASKED (CR-045 wave G,
 * `DEF-1702`).** `accounts.closed_at` is the one stored, filterable fact on the
 * row, applied in the queryset before paging. Buckets and not a date PAIR
 * because `TableRequestState.filters` is `Record<string, string>` — one value
 * per dimension, signed in BR-SHL-011 — so a range is not expressible without
 * an API change; **`OQ-306` already carries that limit and is not re-opened.**
 *
 * No `sort` either: §5.6.2 fixes the order.
 */
export async function listMoveOuts(
  query: MoveListQuery = {},
  client: ApiClient = api,
): Promise<MoveOutList> {
  return requireMoveData(
    await client.get<MoveOutList>("/move-outs", {
      query: {
        q: query.q === undefined || query.q === "" ? undefined : query.q,
        page: query.page,
        per: query.per,
        // `BR-CUS-1046` — the chosen ordering, so it reaches the `ORDER BY` and
        // survives a refresh in the URL rather than living only in component
        // state (the rule's own second clause).
        sort: query.sort,
        dir: query.dir,
        ...worklistFilterParams(query.filters, MOVE_OUT_LIST_FILTERS),
      },
    }),
  );
}

/**
 * p117's SETTLEMENT column — **ONE LINE**, and §2 of this file's header is the
 * reason it is usually the absence.
 *
 * ⚠ **IT WAS THREE STACKED LINES UNTIL 2026-09-19** — `Deposit held $150.00` /
 * `Outstanding $108.88` / the reason no verdict is stated — and the PO ruled
 * the blueprint's single line over them, in the words *"you ahve to follow our
 * UI rules - this is correct screen - too much text"*. The drawing's own
 * argument is why it is one line rather than two shorter ones:
 *
 *   > *"Settlement is a direction, not a status. One of these owes the utility
 *   > $186.40 and one is owed $42.15 back, and they are the same kind of row."*
 *
 * Three stacked terms are the opposite of a direction: they hand a clerk the
 * inputs and leave the subtraction to them.
 *
 * ⛔ **AND COLLAPSING THE DISPLAY DOES NOT LICENCE THE CELL TO ASSERT A
 * DIRECTION.** `landing` is `null` on every row this server serves — the
 * engine's rule is *any gap → no landing*, and both gaps are open on every row
 * (billing publishes no per-account final bill, BR-CUS-057's interest accrual
 * is confirmed and unbuilt). So the one line is the ABSENCE, and the direction
 * branch below renders only when the server has both computed a landing and
 * sent the figure for it. **Deriving either here is what §2 forbids**, and
 * BR-CUS-082's collections ladder is what it would start.
 *
 * ⚠ **THE TWO TERMS ARE STILL CARRIED, AS DATA RATHER THAN AS COPY.** DEF-127
 * is about the OUTSTANDING figure never being fabricated, not about it being
 * printed in this cell, and the whole settlement with every term is one click
 * away on the account's own page (`GET /accounts/{id}/close-impact`). The
 * `data-` attributes keep the figures findable — the `open_means` precedent
 * this file already uses in three other places.
 */
/**
 * The engine's five landings, in a clerk's words — `MONEY_LANDINGS` is a CLOSED
 * set and this map exists so the screen cannot invent a sixth.
 *
 * ⚠ **`defaultValue`s, NOT COPY** — the same posture as `MOVE_OUT_STATE_LABELS`
 * further down. p117 draws two of the five (`Short by $186.40`, `Refund
 * $42.15`); the other three are named here because a landing the server can
 * send and the screen cannot spell would render as an amount with no direction.
 */
const MOVE_OUT_LANDING_LABELS: Record<string, string> = {
  short: "Short by",
  refund_due: "Refund",
  settled: "Settles exactly",
  refused_other_debt: "Held — other debt",
  refused_excess: "Held — excess",
};

export function MoveOutSettlementCellView(props: {
  settlement: MoveOutSettlementCell;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const { settlement, t } = props;
  const landing = settlement.landing;
  const net = settlement.net?.display ?? null;
  // ⛔ DEF-731 — the hover text is the READER's sentences joined, never the
  // server's. `detail` on this cell carried the settlement engine's own
  // diagnostics, so hovering a money cell printed a module path at a clerk.
  const why = settlement.unavailable
    .map((row) => absenceCopy(row, t))
    .filter((line): line is string => line !== null)
    .join(" ");
  return (
    <span
      className="inline-flex flex-col gap-0.5"
      title={why}
      data-settlement-landing={landing ?? ""}
      // The two terms the server really read, kept as data — see the header.
      data-deposit-held-display={settlement.deposit_held.display ?? undefined}
      data-outstanding-display={settlement.outstanding.display ?? undefined}
    >
      {/* ⛔ BOTH HALVES, OR NEITHER. A landing with no figure would print a
          bare `Short by`, and a figure with no landing an amount with no
          direction; each is a sentence this list cannot stand behind. */}
      {settlement.complete && landing !== null && net !== null ? (
        // p117's line: a direction and its figure. The WORD comes from the
        // engine's own closed vocabulary through a label map, never from a
        // comparison made here, and hard rule 2 means `display` is already the
        // server's 2-dp string — this formats and does not re-round.
        <span data-settlement-net={net}>
          <span className="text-neutral-700">
            {t(`customers.moveOuts.settlement.landing.${landing}`, {
              defaultValue: MOVE_OUT_LANDING_LABELS[landing] ?? "",
            })}{" "}
          </span>
          <MoneyCell amount={net} currency={settlement.currency} />
        </span>
      ) : (
        /* ⛔ **THE VERDICT, WITHHELD — AND SINCE 2026-09-25 IT IS AN EM DASH
           AND NOT A SENTENCE (`DEF-CUS-6760`).** This cell printed *"No
           settlement yet — the final bill is not readable"* on every row, and
           **the second half of that is RATIONALE**, which B14 rule 33 puts at
           ZERO words on screen — removed, never shortened. **The blueprint
           says the same thing from the other side:** p119 draws this column as
           `Short by $186.40` · **`—`** · `Refund $42.15`, so the drawn absence
           was a dash all along and the product had grown an explanation in its
           place.

           ⚠ **NOTHING IS LOST FROM THE WIRE OR FROM THE SCREEN'S REACH.** The
           engine's own reason still rides on this cell's `title` (the joined
           reader sentences, `DEF-731`'s shape), `MoveAbsenceNote` still stamps
           `data-move-absent` and `data-tracks`, and the two terms the server
           actually read are still `data-deposit-held-display` and
           `data-outstanding-display` on the wrapper. The whole settlement with
           every term is one click away on the account's own page.

           ⚠ **BOTH BRANCHES COLLAPSE, NOT ONE.** *"Not settled until it
           closes"* was the parked row's sentence and is the same kind of thing
           — a *why* in a column that states a figure — and p119 draws the
           in-flight row's cell as a dash too. Its key is retired from all
           eleven catalogues through `10-scripts/i18n_fanin.py`; rule 33's
           *removed rather than shortened* is what makes leaving one of the two
           the wrong answer. The STATE column on that same row already says the
           move-out has not finished. */
        <MoveAbsenceNote absence={settlement.unavailable[0]} marker="settlement">
          {"\u2014"}
        </MoveAbsenceNote>
      )}
    </span>
  );
}

/**
 * The state words this column may print. ⚠ `defaultValue`s, NOT COPY — the
 * eleven catalogues carry `customers.moveOuts.state.*` and are what a reader
 * actually sees.
 *
 * ⚠⚠ **`closed` PRINTS `Completed`, AND IT PRINTED `Closed` UNTIL 2026-09-19
 * (`DEF-CUS-5901`).** The Accounts blueprint p117 draws `Completed` and
 * `move_record_reads.STATE_COMPLETED` already served that word, so **the record
 * page spoke the blueprint's vocabulary and only the LIST did not** — one
 * move-out was `Closed` in the table and `completed` on its own page, two
 * words for one state, on two screens a clerk moves between with one click.
 * The list is the surface that moved.
 *
 * ⛔ **IT IS A DISPLAY WORD AND NOTHING ELSE.** The stored value is still
 * `closed`, there is no migration and no state value changed — the key is
 * still `closed` right here, which is the whole shape of the fix.
 *
 * ⚠ **`in_progress` AND `waiting` ARE LIVE NOW** (PO ruling the same day,
 * `yes`). They are not B18 leftovers waiting for a column: each is a
 * `wizard_parks` draft for `flow='move_out'`, and the one column that tells
 * them apart is whether the clerk recorded what they are waiting for.
 *
 * ⚠ **`scheduled` STAYS IN THE MAP AND CANNOT ARRIVE.** The server marks it
 * unsupported with its reason; the word is spelled here because a state the
 * server can name and the screen cannot spell would render as a raw code, and
 * B14 rule 31 keeps an internal code off the screen.
 */
const MOVE_OUT_STATE_LABELS: Record<string, string> = {
  closed: "Completed",
  scheduled: "Scheduled",
  in_progress: "In progress",
  waiting: "Waiting",
};

export function moveOutsTableConfig(
  t: (key: string, params?: Record<string, unknown>) => string,
  cells: {
    /** ⚠ **`DEF-CUS-5994` — the DRAFT's state cell, passed in like the routed
     *  ones beside it.** It needs the tenant's date format, the api client and
     *  the translator, none of which this function takes — and a config that
     *  reached for them could not be tested without mounting a page, which is
     *  the same reason `reference`, `accountLink` and `openRecord` arrive this
     *  way. */
    draftState: (row: MoveOutRow) => JSX.Element;
    moveOutDate: (row: MoveOutRow) => JSX.Element;
    settlement: (row: MoveOutRow) => JSX.Element;
    /** p117 — the MVO reference, as a door onto `/moves/{ref}`. Routed, so it
     *  is passed in rather than built here: this function takes no router and a
     *  config that reached for one could not be tested without a page. */
    reference: (row: MoveOutRow) => JSX.Element;
    /** p117 — the account number, as a door onto the account. Routed. */
    accountLink: (row: MoveOutRow) => JSX.Element;
    /** p117's per-row `↗ Open`. Routed. */
    openRecord: (row: MoveOutRow) => JSX.Element;
  },
): TableConfig<MoveOutRow> {
  return {
    screenId: MOVE_OUTS_TABLE_SCREEN,
    // ⚠ **NOT `account_id` ANY MORE (PO ruling 2026-09-19).** An unfinished
    // move-out has no account id of its own until a clerk picks one, and two
    // drafts can name the SAME account — so keying on it would collapse two
    // rows into one and lose whichever React drew second. The draft's own
    // handle is the identity of that row; nothing renders either value.
    getRowId: (row) => row.park_id ?? row.account_id ?? "",
    // FOUR legs, not §5.6.2's five: `request #` is not offered, because a
    // move-out creates no child and `outcome_ref` is null on every move-out
    // request. A box that offered it would silently find nothing.
    //
    // ⚠ **`reference` IS A FIFTH LEG AND THE SERVER DOES NOT SERVE IT YET
    // (2026-09-19, `DEF-CUS-5896`).** p117 draws the prompt as *"Search by
    // reference, account, customer or unit"*, the PO ruled it, and REFERENCE is
    // the first column of this table — a clerk holding `MVO-26-0088` cannot
    // find its row. `move_outs_queryset` matches `account_no`, the customer's
    // display name and number, the contact name and the unit ids, and has NO
    // `move_no` leg; `MOVE_OUT_SEARCH_HINT` still reads the old four.
    //
    // ⛔ **SO THIS DECLARATION AND THE PROMPT BESIDE IT ARE AHEAD OF THE
    // SERVER, AND THE ROW IS FILED RATHER THAN LEFT IN A COMMENT.** B14 rule 19
    // says a prompt names what the box MATCHES and `DEF-950` is the last time a
    // list promised a leg it did not have. `DEF-CUS-5896` names BOTH halves —
    // `move_outs_queryset` plus *"MoveOutsTab.tsx searchFields and the eleven
    // searchPlaceholder catalogue strings"* — and only the front half is in
    // this commit. The backend half is one `Q` on `move_no__icontains` plus
    // `MOVE_OUT_SEARCH_HINT`; until it lands, a clerk typing a reference gets
    // no rows, and the row is what makes that countable rather than a sentence
    // in a file nobody greps (CLAUDE.md hard rule 4's closing lesson).
    searchFields: ["reference", "customer", "account_no", "unit", "address"],
    // ✅ **B14 rule 19's prompt is WIRED (CR-041 task 2)**, new in all eleven
    // catalogues. Its English is the server's own `MOVE_OUT_SEARCH_HINT`,
    // verbatim — FOUR legs, not five. The move-in sentence beside it names a
    // `request #` and this one must not: `outcome_ref` is null on every
    // move-out request, so a prompt offering it would send a clerk hunting for
    // a match that cannot exist. The two hints differ because the two
    // predicates differ, and copying one onto the other is the whole failure
    // this CR is about.
    searchPlaceholder: "customers.moveOuts.list.searchPlaceholder",
    // ⚠ NO SORT — the server orders by move-out date and takes no param.
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
    // ⚠ **THIS TAB OPENED ON `move_out_date` ASCENDING** — §5.6.2's *"soonest
    // first"*. Sortable now, so that ordering is one click.
    defaultSort: { sort: "created", dir: "desc" },
    columns: [
      {
        // ⚠ **§5.6.2 DRAWS EIGHT COLUMNS AND THIS IS A NINTH** — CR-039 wave D
        // tasks 17–19, the same divergence S89 and S90 carry and stamped here
        // for the same reason. The design's eight follow it unchanged. The CR's
        // finding 5 named move-in and move-out as the two flows with *"NO
        // RECORD AT ALL"*; this is the cell that makes one quotable.
        //
        // ⛔ Three absences can land here and the cell renders the SERVER's
        // sentence for whichever it is, never a dash: a job that predates the
        // record, a tenant with no series row, and (on the Move-ins tab) a
        // move-in that has not completed. See `move_reads.move_reference_cell`.
        key: "reference",
        label: t("customers.moveOuts.col.reference", { defaultValue: "Reference" }),
        // ⚠ **THE REFERENCE IS A DOOR NOW — p117, PO-ruled 2026-09-19**
        // (*"you ahve to imporve th itneraction design - allow to open the move
        // out request"*). It rendered as plain text because there was nowhere
        // for it to go; `/moves/{ref}` is a real address.
        //
        // ⛔ **THE ABSENCE BRANCH IS UNTOUCHED AND HAS TO STAY.** A link wrapped
        // round a null is a control that opens nothing — hard-won law 2's
        // mirror, which this repo paid for on the portal's front page. Three
        // absences can land here and `cells.reference` falls through to the
        // server's own sentence for whichever it is.
        cell: (row) => cells.reference(row),
      },
      {
        key: "account",
        // `BR-CUS-1046` — SORTABLE, and the key IS the server's sort name.
        sortable: true,
        label: t("customers.moveOuts.col.account", { defaultValue: "Account" }),
        identity: true,
        // p117's second door. This one needed nothing built: the account page
        // has existed since S21, which is why the conformance table said
        // *"link — the account page exists today"*.
        //
        // ⛔ **AND IT IS A DOOR ONLY WHERE THERE IS AN ACCOUNT.** An unfinished
        // move-out can have none — parked before one was picked, or the account
        // it named has gone — and a link wrapped round a null is a control that
        // opens nothing (hard-won law 2's mirror, which this repo paid for on
        // the portal's front page). `cells.accountLink` falls through to the
        // server's sentence for whichever it is.
        cell: (row) => cells.accountLink(row),
      },
      {
        key: "customer",
        label: t("customers.moveOuts.col.customer", { defaultValue: "Customer" }),
        cell: (row) => (
          <MoveCustomerCell
            name={row.customer}
            number={row.customer_no}
            absence={row.customer_absence}
          />
        ),
      },
      {
        key: "unit",
        label: t("customers.moveOuts.col.unit", { defaultValue: "Unit" }),
        // BR-MET-036 — this unit derived back to Vacant when the account
        // closed, because the terminal class does not occupy.
        cell: (row) => <span>{row.unit ?? "—"}</span>,
      },
      {
        key: "move_out_date",
        // `BR-CUS-1046` — SORTABLE, and the key IS the server's sort name.
        sortable: true,
        label: t("customers.moveOuts.col.moveOutDate", { defaultValue: "Move-out date" }),
        cell: cells.moveOutDate,
      },
      {
        key: "step",
        label: t("customers.moveOuts.col.step", { defaultValue: "Step" }),
        // ⚠ The bar draws the SERVER's `of`, whatever number that is — never
        // a literal typed here, which is the whole of BR-SHL-046's durable
        // half. It served six until 2026-09-24 and serves four now; a number
        // written into this file is B18's superseded count coming back
        // through the screen, whichever number it happens to match today.
        //
        // ⚠ **AND `reached` IS THE SERVER'S TOO.** p117's in-flight row draws
        // `2 of 6` — a DRAWN figure, and an illustration (B14 rule 37) now
        // that the flow is four — and an unfinished move-out carries its own
        // draft. `label` is what prints when there is NO step, which is every
        // closed row — see this file's header for why a closed row must never
        // be given one.
        cell: (row) => (
          <MoveStepBar
            step={row.step}
            label={t("customers.moveOuts.step.noStore", { defaultValue: "Step not recorded" })}
          />
        ),
      },
      {
        key: "final_read",
        label: t("customers.moveOuts.col.finalRead", { defaultValue: "Final read" }),
        // ⚠ **ALL THREE WORDS ARE PRINTABLE NOW (2026-08-26, CR-038 W9 ·
        // DEF-786).** This comment read "⛔ `taken` / `due` / `estimated` are
        // all words this screen may not print: customers publishes no metering
        // read seam, and `estimated` additionally has no home on a settlement
        // (TC-MVO-7)". Both halves closed on the same day: the seam derives
        // `taken`/`due` against this row's `closed_at`, and `estimated` has a
        // home — `accounts.final_read_state`, stored at close, which is the
        // ONLY thing allowed to say it. `final: true` is what admits the third
        // word to this cell and keeps it out of the move-ins one.
        cell: (row) => (
          <MoveReadsCellView
            reads={row.final_read}
            marker="final-read"
            final
            notReadableLabel={t("customers.moveOuts.finalRead.notReadable", {
              defaultValue: "Not readable here",
            })}
          />
        ),
      },
      {
        key: "settlement",
        label: t("customers.moveOuts.col.settlement", { defaultValue: "Settlement" }),
        cell: cells.settlement,
      },
      {
        key: "state",
        label: t("customers.moveOuts.col.state", { defaultValue: "State" }),
        cell: (row) => (
          // ⚠ **THREE STATES SINCE 2026-09-19, NOT ONE.** This comment read
          // *"Every row is `closed` — the only state this schema holds"*; the
          // PO ruled the unfinished ones onto the list that day and they carry
          // `in_progress` or `waiting`. Neutral on all three, because B18 draws
          // no tone and neither a finished move-out nor one a clerk is still
          // working on is an alarm.
          //
          // ⚠ **THE STORED CODE IS THE KEY AND THE WORD IS THE CATALOGUE'S.**
          // `closed` prints `Completed` (p117, `DEF-CUS-5901`) and nothing
          // stored moved — which is the whole shape of that fix.
          <span data-move-out-state={row.state}>
            {/* ⚠ **REQUIREMENT 1 OF `CR-035` AMENDMENT 1, MET ON THE ROW
                INSTEAD OF ABOVE THE TABLE (`DEF-CUS-5994`).** *"A clerk cannot
                mistake a draft for a job that happened"* was the pinned
                panel's dashed border and its own block. The panel is gone and
                the requirement is not, so the badge comes onto the row wearing
                the SAME warning tone — which is also the one place this tab's
                deliberate neutrality has to yield, because neutral on a draft
                is exactly the confusion the requirement forbids. */}
            {row.row_kind === MOVE_OUT_ROW_KIND_PARKED ? (
              cells.draftState(row)
            ) : (
              <StatusPill tone="neutral">
                {t(`customers.moveOuts.state.${row.state}`, {
                  defaultValue: MOVE_OUT_STATE_LABELS[row.state] ?? row.state,
                })}
              </StatusPill>
            )}
          </span>
        ),
      },
      {
        // ⚠ **p117's PER-ROW `↗ Open`, WHICH HAD NO DESTINATION UNTIL THIS
        // WEEK.** The drawing puts one on every row — on the completed
        // `MVO-26-0088`, on the in-flight `MVO-26-0087` and on `MVO-26-0084` —
        // and this tab carried no row action at all, which its own lifecycle
        // trailer recorded as an exception. `/moves/{ref}` is a real address
        // now, so the control is a door rather than a stub.
        //
        // ⛔ **IT IS DRAWN ONLY WHERE IT OPENS SOMETHING.** A row with no
        // `move_no` gets nothing rather than a greyed button carrying a reason
        // — B14 rule 33 puts rationale at zero words on screen, and the
        // REFERENCE cell on that same row already states why there is no
        // record. Two statements of one absence on one row is what rule 32's
        // description budget exists to stop.
        //
        // ⚠ **TWO DESTINATIONS SINCE 2026-09-19, AND THE ROW DECIDES WHICH.**
        // A FINISHED move-out opens its record at `/moves/{ref}` — the page
        // that says what happened. An UNFINISHED one has no record and no
        // reference to build that address from; what a clerk wants from it is
        // to CARRY ON, so it opens the wizard at the step it was left on
        // (`/move-outs/new?parked=<id>`) through `resumePath` — the SAME
        // builder the parked-drafts panel uses, so two surfaces cannot disagree
        // about the handle. Same word on the button, because the verb a clerk
        // reads is *open this move-out* either way.
        key: "open",
        // The column exists to hold a control; a heading over it would be a
        // label for a verb the button already says (rule 32).
        label: "",
        cell: (row) => cells.openRecord(row),
      },
    ],
    // ── CR-045 wave G · `DEF-1702` — CLOSED, a window, and NOT a state ────
    // The dimension is declared here so `?f.closed=last30` round-trips
    // (BR-SHL-011); the buckets are the server's and arrive on the response.
    // See `moveOutFilterGroups` for why this tab is the one that cannot have a
    // state filter.
    filters: moveOutFilterGroups(undefined, t),
  };
}

/**
 * The one dimension the MOVE-OUTS tab declares — a WINDOW on `closed_at`, and
 * not a state (CR-045 wave G, `DEF-1702`).
 *
 * ⚠ **THIS TAB IS THE ONE THAT CANNOT HAVE A STATE FILTER, AND THE REASON IS
 * THE SCHEMA.** `MOVE_OUT_STATES` draws four and marks exactly ONE `supported`.
 * The other three — `scheduled`, `in_progress`, `waiting` — each carry
 * `MOVE_OUT_NOT_YET_CLOSED_HAS_NO_STORE`: `services.move_out` writes
 * `closed_at`, the terminal status and the agreement end dates in a SINGLE
 * commit, so a move-out before it closes is a state this product cannot
 * represent at all. Four of B18 §5.6.7's six drawn rows are accounts still live
 * and still billing. **A State group here would offer one option that changes
 * nothing** — B14 rule 9's own objection.
 *
 * ⚠ **SO THE DIMENSION IS `closed`, AND IT IS BUCKETS RATHER THAN A DATE
 * PAIR.** `TableRequestState.filters` is `Record<string, string>` — one value
 * per dimension, signed in BR-SHL-011 — so a range is not expressible without
 * an API change. `OQ-306` already carries that limit; this does not re-open it.
 *
 * ⚠ **THE BUCKETS ARE THE SERVER'S** (BR-SHL-010). `MOVE_OUT_CLOSED_WINDOWS`
 * maps each code to its day count and `move_outs_queryset` applies it; the
 * label is built from the served `days`, so a fourth window added on the server
 * appears here with the right words and no edit.
 */
export function moveOutFilterGroups(
  windows: { code: string; days: number }[] | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
): TableFilterConfig[] {
  return [
    {
      name: "closed",
      label: t("customers.moveOuts.filter.closed", { defaultValue: "Closed" }),
      options: (windows ?? []).map((window) => ({
        value: window.code,
        label: t(`customers.moveOuts.closed.${window.code}`, {
          defaultValue: `Last ${window.days} days`,
        }),
      })),
    },
  ];
}

export function moveOutsQueryKey(state: TableRequestState): readonly unknown[] {
  // `state.filters` is IN THE KEY, or react-query answers the filtered request
  // from the unfiltered page in cache and the list never moves.
  // `state.sort`/`state.dir` in the key — see `moveInsQueryKey`.
  return [
    "move-outs",
    state.q,
    state.page,
    state.per,
    state.filters,
    state.sort,
    state.dir,
  ];
}

/**
 * The Accounts blueprint p117's **THREE** tiles. ⚠ **IT WAS B18 §5.6.1's FIVE
 * UNTIL 2026-09-19**, when the PO dropped two of them by name — *"Drop it"*,
 * said twice, of `SHORTFALLS TO DECIDE` and `REFUNDS TO PAY`.
 *
 * ⚠ **THE TWO THAT WENT ARE THE TWO THAT COULD NEVER CARRY A FIGURE.** Both
 * need a LANDING (§2), `landing` is `null` on every row this server serves, and
 * so each rendered a SENTENCE where a number belongs. Three tiles that each
 * carry a figure is a better strip than five where two are apologies — and the
 * DEF-127 rule they were protecting is unchanged and still load-bearing on the
 * one tile that remains nullable:
 *
 *   · `FINAL READS DUE · 0` says every meter has been read, which is good news
 *     to the one person paid to act on the bad kind. A `0` may be drawn ONLY
 *     where the server derived it, never as a fallback for a `null`.
 *
 * ⚠ **NOTHING WAS DROPPED FROM THE PAYLOAD.** `shortfalls_to_decide*` and
 * `refunds_to_pay*` are still served and still on `MoveOutKpis`: a reader that
 * drops a served key starts lying about the contract, and the day either tile
 * is wanted back it is a tile rather than a migration.
 *
 * ⚠ **`OPEN` CARRIES `open_means` IN ITS DETAIL**, because p117 captions it
 * *"not yet closed"* and what it counts is move-outs that have CLOSED —
 * otherwise five here reads as five people still packing. The drawn caption is
 * therefore NOT the copy; ours is `closed, not yet finally billed`, which is
 * five words and true, and the drawn words are unbuildable rather than merely
 * longer.
 *
 * ⚠ **`FINAL READS DUE` LOST ITS SUB-LINE ENTIRELY** — *"nothing settles
 * without one"* is RATIONALE, and B14 rule 33 puts rationale at ZERO words on
 * screen. It is removed rather than shortened: cutting a *why* sentence to six
 * words keeps the breach and makes it terser. What the figure counts still
 * rides as data (`final_reads_due_means`, the `open_means` precedent).
 */
export function moveOutsKpis(
  payload: MoveOutList | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
): KpiTile[] {
  const kpis = payload?.kpis;
  const undecidable = (
    id: string,
    label: string,
    absence: WorklistAbsence | undefined,
    detail: string,
  ): KpiTile => ({
    id,
    label,
    // ⛔ THE REASON, NOT A ZERO.
    value: (
      <MoveAbsenceNote absence={absence} marker={id}>
        {t("customers.moveOuts.kpi.notReadable", { defaultValue: "Not readable" })}
      </MoveAbsenceNote>
    ),
    detail,
  });
  return [
    {
      id: "open",
      // ⚠⚠ **THIS TILE SAID `Open` OVER ROWS THAT ALL READ `Completed`, AND
      // BOTH WERE TRUE — 2026-09-25, `DEF-CUS-6762`.** The PO saw `OPEN 5` above
      // five rows each stating `Completed` and nothing on the screen told them
      // apart. **Neither figure is wrong and no logic moved here.** What this
      // counts is what it has always counted — `move_out_kpis` says so in its
      // own words, *"move-outs that have closed and are not yet finally
      // billed"* — and the rows are right that the move-out itself completed.
      //
      // **THE WORD WAS THE FAULT, AND IT CAME FROM THE DRAWING MEANING THE
      // OPPOSITE.** p119 heads this tile `OPEN` under the caption *"not yet
      // closed"*, i.e. move-outs still in flight. This product cannot count
      // those — a move-out before it closes is not a row anywhere — so the
      // tile was given the drawn WORD over an undrawn MEANING, and a caption
      // was added underneath to stop it being read backwards. **A label that
      // needs a caption to stop it being read backwards is the wrong label.**
      //
      // ⚠ **SO THE LABEL NOW STATES WHAT IS COUNTED AND THE CAPTION COMES OFF**
      // — three words, B14 rule 33's cap for a label, and rule 32's one
      // statement per section rather than the same fact twice. `FINAL READS
      // DUE` directly below already renders exactly this shape: the server's
      // `means` carried as DATA and no words under the number.
      label: t("customers.moveOuts.kpi.awaitingFinalBill", {
        defaultValue: "Awaiting final bill",
      }),
      value: kpis?.open ?? 0,
      detail: (
        <span
          // The server's own sentence for WHAT was counted, carried so a
          // caption cannot quietly redefine the figure (the `open_means`
          // precedent this tab already uses in three other places). It renders
          // no words.
          data-tracks={kpis?.open_unavailable.br_ref}
          data-open-means={kpis?.open_means}
        />
      ),
    },
    {
      id: "leaving-this-week",
      label: t("customers.moveOuts.kpi.leavingThisWeek", { defaultValue: "Leaving this week" }),
      value: kpis?.leaving_this_week ?? 0,
      detail: t("customers.moveOuts.kpi.leavingThisWeekDetail", {
        defaultValue: "within 7 days of today",
      }),
    },
    // ⚠ **THE FIGURE, WHEN THE SERVER DERIVED ONE (2026-08-26, DEF-786).** This
    // tile was `undecidable(...)` unconditionally and drew its reason where the
    // number goes. It now draws the number the seam derived — and falls back to
    // the SAME reason, unchanged, on a deployment where the seam does not
    // resolve. `?? 0` is deliberately absent: a `null` here is "not worked out"
    // and printing 0 for it is the exact bug the block above is about.
    // ⛔ **NO SUB-LINE ON EITHER BRANCH — B14 rule 33.** `undecidable` takes
    // one, so the empty string is passed deliberately rather than the tile
    // being rebuilt: the reason the figure is missing already renders WHERE THE
    // NUMBER GOES, and a caption under it would state the same absence twice.
    kpis?.final_reads_due_unavailable != null || kpis?.final_reads_due == null
      ? undecidable(
          "final-reads-due",
          t("customers.moveOuts.kpi.finalReadsDue", { defaultValue: "Final reads due" }),
          kpis?.final_reads_due_unavailable ?? undefined,
          "",
        )
      : {
          id: "final-reads-due",
          label: t("customers.moveOuts.kpi.finalReadsDue", { defaultValue: "Final reads due" }),
          value: kpis.final_reads_due,
          detail: (
            <span
              // The server's own sentence for WHAT was counted, and the
              // meterless rows it left out — carried so a caption cannot
              // quietly redefine the figure (the `open_means` precedent). It
              // was ALSO the sub-line's only defensible content once *"nothing
              // settles without one"* came off as rationale, so it stays here
              // as data and renders no words.
              data-final-reads-due-means={kpis.final_reads_due_means}
              data-final-reads-due-meterless={kpis.final_reads_due_meterless}
            />
          ),
        },
    // ⛔ **`Shortfalls to decide` AND `Refunds to pay` ARE GONE FROM THE SCREEN
    // — PO 2026-09-19, *"Drop it"* twice.** Both are still SERVED; see this
    // function's header for why nothing was removed from the payload or the
    // type, and `MoveOutKpis` for the two fields that now have no reader here.
  ];
}

export interface MoveOutsTabProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function MoveOutsTab(props: MoveOutsTabProps) {
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
      moveOutsTableConfig(translate, {
        // ⚠ **THE DASH BECAME A SENTENCE WHERE THERE IS A REASON (2026-09-19).**
        // On a finished row `move_out_date` cannot be null — the window is
        // `closed_at IS NOT NULL` — so the dash was unreachable and harmless.
        // An UNFINISHED row can genuinely have no date: the step that asks for
        // one has not been reached. A dash there says *nothing to show*, and a
        // blank cell and an absent fact are indistinguishable once drawn
        // (`DEF-127`). The dash stays for the case with no served reason.
        moveOutDate: (row) =>
          row.move_out_date === null ? (
            row.move_out_date_absence === null ? (
              <span aria-hidden="true">—</span>
            ) : (
              <MoveAbsenceNote absence={row.move_out_date_absence} marker="move-out-date" />
            )
          ) : (
            <DateCell value={row.move_out_date} timeZone={timeZone} dateFormat={dateFormat} />
          ),
        settlement: (row) => (
          <MoveOutSettlementCellView settlement={row.settlement} t={translate} />
        ),
        // ── p117's TWO DOORS AND ITS ROW ACTION ───────────────────────────
        //
        // ⚠ **ALL THREE ARE BUILT THROUGH `tenantPath`, AND THAT IS NOT A
        // STYLE CHOICE.** A bare `/moves/MVO-26-0088` rendered outside a tenant
        // is a PROTOCOL-RELATIVE URL to another host — `//moves/…` — which
        // reads as a perfectly good href to a person, to `toContain` and to
        // `tsc`, and opens nothing. That is the fixture trap hard-won law 2
        // records, and it is why this tab's own cases now mount under the real
        // `/:tenant/accounts` pattern and read the href out of the marked tag.
        //
        // ⚠ **AND EACH IS DRAWN ONLY WHERE IT OPENS SOMETHING.** A link round a
        // null reference, or an `Open` on a row with no record, is the
        // live-screen-behind-a-dead-control shape: it looks finished and does
        // nothing.
        reference: (row) =>
          row.move_no === null ? (
            row.row_kind === MOVE_OUT_ROW_KIND_PARKED ? (
              // ⚠ **FIVE WORDS, NOT TWENTY-FIVE — B14 rule 33 (2026-09-19).**
              // `RecordNumberCell` renders the server's whole sentence, which is
              // right for the absences it was built for: a move that predates the
              // record is a one-off a clerk meets rarely and needs explaining.
              // This one is on EVERY unfinished row, and measured in a browser at
              // 1440 it wrapped to **twelve lines** inside the REFERENCE column and
              // pushed the row taller than the three beside it. A FACT caps at six
              // words; the full sentence rides on the cell's `title`, which is the
              // posture the SETTLEMENT column two cells over already takes.
              <MoveAbsenceNote absence={row.move_no_unavailable} marker="reference">
                {translate("customers.moveOuts.reference.notYet", {
                  defaultValue: "No number until it completes",
                })}
              </MoveAbsenceNote>
            ) : (
              <RecordNumberCell
                number={row.move_no}
                unavailable={row.move_no_unavailable}
                kind="move_out"
              />
            )
          ) : (
            <Link
              to={tenantPath(moveRecordPath(row.move_no))}
              className="font-medium tabular-nums underline underline-offset-2"
              data-move-out-record={row.move_no}
            >
              {row.move_no}
            </Link>
          ),
        accountLink: (row) =>
          row.account_id === null || row.account_no === null ? (
            // ⛔ NO LINK ROUND A NULL — the server's sentence instead, which
            // says whether nobody has picked an account yet or the one this
            // draft named has gone. Two different facts, two different
            // sentences, neither of them a dash.
            <MoveAbsenceNote absence={row.account_absence} marker="account" />
          ) : (
            <Link
              to={tenantPath(accountDetailPath(row.account_id))}
              className="tabular-nums underline underline-offset-2"
              data-move-out-account={row.account_no}
            >
              {row.account_no}
            </Link>
          ),
        // `DEF-CUS-5994` — the badge and the parked facts, one implementation
        // shared with the other four tabs (`parkedDrafts.tsx`).
        draftState: (row) => (
          <span className="flex flex-col items-start gap-1">
            {/* ⚠ **p117's OWN WORD, IN A WARNING TONE (`DEF-CUS-5994`).** The
                drawing gives this column exactly two words — `Completed` and
                `In progress` — and `DEF-CUS-5901` moved `closed` to print the
                first for that reason. The first draft of this change printed
                `Parked` here instead and three cases caught it. **The tone is
                what the removed panel actually contributed; the word was never
                ours to change.** */}
            <ParkedBadge
              parked={(row.waiting_on ?? "") !== ""}
              t={translate}
              label={translate(`customers.moveOuts.state.${row.state}`, {
                defaultValue: MOVE_OUT_STATE_LABELS[row.state] ?? row.state,
              })}
            />
            <ParkedWhyCell row={row} timeZone={timeZone} dateFormat={dateFormat} />
          </span>
        ),
        openRecord: (row) =>
          row.row_kind === MOVE_OUT_ROW_KIND_PARKED ? (
            // ⚠ **AN UNFINISHED MOVE-OUT OPENS THE WIZARD, NOT A RECORD.**
            // There is no record and no reference to address one with, and what
            // a clerk wants from this row is to carry on from where they
            // stopped. `resumePath` is the ONE builder for `?parked=<id>` — the
            // parked-drafts panel's own resume goes through it too, so the two
            // surfaces cannot drift apart on the handle.
            row.park_id === null ? (
              <></>
            ) : (
              // ⚠⚠ **AN ICON PAIR SINCE 2026-09-25 (`DEF-CUS-6759`), AND IT
              // WAS A TEXT `↗ Open` BESIDE THEM UNTIL THEN.** The PO ruled row
              // actions are icons on this list; `ParkedDraftActions` has drawn
              // exactly the right pair since `DEF-CUS-5994` — **Resume** and
              // **Discard**, both `RowActionLink`/`RowAction` — and this tab
              // was suppressing its Resume through `resumeAlreadyDrawn` ONLY
              // because it drew a worded button itself. That prop is dropped
              // here, so the shared component draws both halves and this file
              // writes no control of its own (B14 rule 43).
              //
              // **Discard is still the half that would have gone missing.** A
              // clerk could throw a draft away ONLY from the panel above this
              // table, so deleting that panel without re-homing its second
              // control would have removed a live capability with **nothing to
              // notice** (`DEF-CUS-3653`).
              //
              // ⚠ **THE MARKER IS ON A WRAPPER, NOT ON THE LINK.**
              // `RowActionLink` takes a fixed shape and spreads nothing, so a
              // `data-*` handed to it typechecks, renders nowhere, and is
              // asserted on by a test that cannot find it — which is the note
              // `ParkedDraftActions` already carries. Its two consumers read
              // the `<a>` INSIDE this span.
              <span data-move-out-resume={row.park_id}>
                <ParkedDraftActions
                  flow="move_out"
                  onDiscard={setDiscarding}
                  parkId={row.park_id}
                  subjectLabel={row.customer ?? row.account_no ?? ""}
                />
              </span>
            )
          ) : row.move_no === null ? (
            // Nothing at all — see the column's own note. The reference cell on
            // this same row already states why there is no record, and saying
            // it twice on one row is what rule 32's budget exists to stop.
            <></>
          ) : (
            // ⚠ **ONE ICON, WITH AN ACCESSIBLE NAME — THE DISCONNECTS LIST'S
            // OWN SHAPE.** `RowActionLink` makes the label a REQUIRED prop, so
            // the glyph cannot ship nameless; the word a clerk hovers is the
            // verb the button used to spell. A LINK and not a button, because
            // middle-click and *open in a new tab* are a real loss on a
            // worklist a clerk wants to open beside the one they are reading.
            <span data-move-out-open={row.move_no}>
              <RowActions>
                <RowActionLink
                  label={translate("customers.moveOuts.action.open", {
                    defaultValue: "Open the move-out",
                  })}
                  icon={<EyeIcon />}
                  to={tenantPath(moveRecordPath(row.move_no))}
                />
              </RowActions>
            </span>
          ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, timeZone, dateFormat],
  );

  // DEF-664 — the table state is THIS COMPONENT'S; the query string belongs to
  // the Accounts page this tab sits inside.
  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  const listQuery = useQuery({
    queryKey: moveOutsQueryKey(state),
    queryFn: () =>
      listMoveOuts(
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

  // ⚠ **CARRIED, NOT PRINTED (2026-09-19).** These two codes rendered as ~78
  // words under the table until the PO ruled them off; see the note where they
  // used to be. `DEF-332` / `G38`'s posture is what this is: the tracking id is
  // still carried and still not in the copy, so the day either absence is
  // resolved — or a THIRD one arrives that a clerk really does need — it is
  // findable in the DOM rather than silently gone.
  const listAbsenceCodes = (listQuery.data?.unavailable ?? [])
    .map((absence) => absence.code)
    .join(" ");

  return (
    <div
      data-embedded=""
      data-screen={MOVE_OUTS_TABLE_SCREEN}
      data-list-absences={listAbsenceCodes}
    >
      {/* `DEF-CUS-5994` — the parked draft's DISCARD confirmation, mounted ONCE
          and ABOVE the table. It is here rather than in the row because a
          `DataTable` cell is unmounted and remounted on every render
          (`DEF-CUS-6011`), so state set by a click inside one does not survive
          the render that click causes. It draws nothing until a clerk asks. */}
      <ParkedDiscardDialog
        flow="move_out"
        target={discarding}
        onClose={() => setDiscarding(null)}
        client={client}
      />
      <KPIStrip kpis={moveOutsKpis(listQuery.data, translate)} loading={listQuery.isPending} />

      {/* ⛔ **NO `downloadSlot`, AND THIS IS THE STATED ABSENCE CR-041 TASK 4
          ASKS FOR — NOT A FORGOTTEN PROP (DEF-1005).**

          `POST /exports` resolves only the resources a module REGISTERS, and an
          unregistered one is a plain 404, never a guessed queryset. Nothing
          registers `move-outs`, so BR-SHL-010 keeps the capability unrendered:
          an undeclared capability is not drawn. Not drawn DISABLED either —
          BR-SHL-025 is for a control this ROLE cannot use, not one the PRODUCT
          does not have.

          The move-out list is where a settlement figure is read, so it is one of the
          more plausible of the eight to deserve an export — which is a reason to
          rule on it, not a reason to draw a button first.

          ⚠ A DOWNLOAD BUTTON HERE WOULD BE A CONTROL WIRED TO A 404 — hard-won
          law 2, which this repo has four instances of from a single day. The
          capability is OWED and unruled, and **DEF-1005 carries it** so this
          sentence expires when the row does rather than outliving its reason
          (DEF-445). */}
      <DataTable<MoveOutRow>
        config={config}
        // ── CR-045 wave G · `DEF-1702` — THE `+ Filter ▾` PANEL, WHERE THE
        //    INERT SEGMENT STRIP USED TO BE ────────────────────────────────
        //
        // The strip drew four segments, THREE permanently off and the fourth
        // permanently active, with `onSelect={() => undefined}`. It occupied
        // the slot B14 rule 12 reserves for the filter and narrowed nothing —
        // which is how this screen was counted as *having* a filter twice while
        // having none (`DEF-1702`). Its removal is argued once, where the
        // component stood, in `NewConnectsTab`.
        //
        // ⚠ **AND THIS TAB IS THE PROOF THAT A SEGMENT AND A FILTER ARE NOT
        //    THE SAME DIMENSION.** The strip's four codes are STATES; the panel
        //    below offers a WINDOW on `closed_at`, because a state filter here
        //    would have exactly one option (see `moveOutFilterGroups`). Moving
        //    the strip into the panel was never available as an option.
        filterBarSlot={
          <FilterBar
            filters={offerableFilters(
              moveOutFilterGroups(listQuery.data?.closed_windows, translate),
            )}
            state={state}
            onStateChange={setState}
          />
        }
        state={state}
        onStateChange={setState}
        rows={rowsOf<MoveOutRow>(listQuery.data)}
        totalRows={totalOf(listQuery.data)}
        loading={listQuery.isPending}
        error={
          listQuery.isError
            ? {
                reason: t("customers.moveOuts.list.loadFailed", {
                  defaultValue: "The move-outs could not be loaded.",
                }),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        empty={{
          title: t("customers.moveOuts.list.emptyTitle", { defaultValue: "No move-outs yet" }),
          // ✅ **UI-RULES 17 — THE EMPTY STATE EXISTS, AND ITS HELPER CAME DOWN
          // TO FIVE WORDS ON 2026-09-19.** It read *"A move-out closes an
          // account and settles what is owed. Closed accounts are listed
          // here."* — 16 words, and the first sentence is RATIONALE (what a
          // move-out IS), which B14 rule 33 puts at zero words on screen. What
          // is left is the FACT a clerk needs to read an empty table correctly,
          // inside rule 33's six, with the action beside it.
          helper: t("customers.moveOuts.list.emptyHelper", {
            defaultValue: "Closed accounts are listed here.",
          }),
          ctaLabel: t("customers.moveOuts.action.new", { defaultValue: "+ New move-out" }),
          // ✅ LIVE — PO ruling 2026-08-26 (*"-Enable Move in /move out"*).
          // The reason this carried — *"A move-out closes one named account, so
          // it starts from that account's own page"* — was true about the
          // ENDPOINT and wrong about the screen: naming the account is step 1 of
          // the flow, not a prerequisite for reaching it. `/move-outs/new` opens
          // on the shared `AccountFinder`, the same first step `/transfers/new`
          // and `/disconnects/new` already had.
          onCta: () => navigate(tenantPath(MOVE_OUT_WIZARD_ROUTE)),
        }}
      />

      {/* ⛔ **~78 WORDS OF PROSE STOOD HERE UNTIL 2026-09-19 AND ALL OF IT IS
          GONE — PO ruling, verbatim: *"you ahve to follow our UI rules - this
          is correct screen - too much text"*.** Three things, and each fails a
          different clause of the same two rules:

            · `customers.moveOuts.list.sortFootnote` — *"Opens newest first.
              Click Move-out date for soonest."* An INSTRUCTION for a control
              that explains itself: the column header carries the sort glyph and
              clicking it is what it is for. **Its key is deleted from all
              eleven catalogues in the same commit**, because a key nothing
              renders is a string that comes back.

            · `move_out_before_close_has_no_store` — 45 words on why a move-out
              in flight is not listed. **RATIONALE, which B14 rule 33 puts at
              ZERO words on screen.**

            · `move_out_window_has_no_closing_edge` — *"A closed account stays
              on this list. Nothing takes it off, because the final bill that
              would finish it cannot be seen from here."* Rationale again, and
              it names an internal limitation at a clerk (rule 32's last
              clause).

          ⚠ **BOTH SENTENCES ARE STILL SERVED AND STILL DEFINED** —
          `move_reads` sends both codes on every response and `absenceCopy` in
          `MoveInsTab.tsx` still spells both, because the Move-ins tab and the
          backend contract both read them. Nothing was deleted from the wire;
          this screen stopped PRINTING them. `listQuery.data.unavailable` is
          what carries them, and §1 of this file's header is where the two facts
          are written down for the next lane — which is exactly where rule 33
          says rationale belongs.

          ⚠ **THIS REVERSES A DELIBERATE `DEF-731` POSTURE, AND THE REVERSAL IS
          A LATER RULE RATHER THAN A CHANGE OF MIND.** That lane's guard reads
          *"Deleting the sentences would trade a badly-worded truth for a lie of
          omission"* — correct on 2026-08-26, when the only alternatives were
          badly-worded and absent. B14 rule 33 was ratified 2026-08-30, four
          days later, and it adds the third option the guard did not have: the
          fact lives in the code and the register, not on the screen. The guard
          in `screenVoice.guard.test.tsx` is TURNED AROUND rather than deleted,
          so it still fires if the prose comes back. */}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W5 (the Move-outs tab, frontend half) · B18 §5.6.1 · §5.6.2 ·
//         §5.6.4 · §5.6.7 · §5.7.3 · `apps/customers/move_reads.py` ·
//         `apps/customers/move_out_settlement.py` · `GET /move-outs` ·
//         BR-CUS-030 · BR-CUS-031 · BR-CUS-057 · BR-CUS-081 · BR-CUS-082 ·
//         BR-SHL-046 · DEF-127 · DEF-664 · hard-won law 8
// generated: 2026-08-25 by lane MOVES (the last two Accounts tabs)
// amended: 2026-08-26 by lane SCREENVOICE — **DEF-731**, the tab the PO quoted.
//         The paragraph under the table read `services.move_out` writes
//         `closed_at` … `MOVE_OUT_FIELDS` will not even accept a date to park.
//         Every absence on this tab now renders through `absenceCopy()` in
//         `MoveInsTab.tsx`; the settlement cell's hover text is the reader's
//         sentences joined, never the settlement engine's diagnostics.
// amended: 2026-08-26 by lane MOVEENTRY — **PO ruling** *"-Enable Move in
//         /move out"*. The empty state's `+ New move-out` is LIVE, onto
//         `/move-outs/new`. Its `ctaReason` — *"A move-out closes one named
//         account, so it starts from that account's own page"* — is deleted: it
//         was true about the ENDPOINT and wrong about the screen, because naming
//         the account is step 1 of the flow rather than a prerequisite for
//         reaching it. Code-only `defaultValue`; no catalogue row to remove.
// amended: 2026-09-19 by lane MOVEOUTLIST — **THE PO's p117 CHANGE LIST**, run
//         as MAINTENANCE (`12-governance/22-product-maintenance-process.md`):
//         the screen is live, so it is reproduce → locate → blast radius →
//         minimal fix, not a build. Read as an IMAGE (B14 rule 42), scale 2.
//         Closes `DEF-CUS-5897` · `DEF-CUS-5898` · `DEF-CUS-5899` ·
//         `DEF-CUS-5900`. Six changes: the strip is THREE tiles (`Shortfalls
//         to decide` and `Refunds to pay` dropped — *"Drop it"*, twice — and
//         both still SERVED, see `MoveOutKpis`); `FINAL READS DUE` loses its
//         rationale sub-line; the SETTLEMENT cell is ONE line; REFERENCE and
//         ACCOUNT are doors and every row grows `↗ Open`; ~78 words of prose
//         under the table are gone; the empty state's helper drops from 16
//         words to five. The search prompt gains `reference` in all eleven
//         catalogues and `customers.moveOuts.list.sortFootnote` is deleted
//         from them.
// checklist: A=n/a(the backend half is `move_reads.py` in this same lane) B✔
//         C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E3 **NO SETTLEMENT LANDING IS RENDERED ON ANY ROW** — not
//         `SHORT`, not `settles exactly`, not `refund`; both of the engine's
//         gaps are open on every row and a guessed landing feeds §5.6.4's
//         four-way decision and BR-CUS-082's ladder · E3 the OUTSTANDING figure
//         is the LEDGER's or an ABSENCE, never `accounts.balance` and never
//         `$0.00` (DEF-127) · E3 **THREE OF FIVE KPI TILES RENDER THEIR REASON
//         WHERE A NUMBER IS DRAWN** rather than `0` · E3 `OPEN` counts CLOSED
//         move-outs and carries `open_means`, because a move-out in flight has
//         no store · E2 **the exception that stood here is SUPERSEDED BY
//         CR-045 WAVE G (2026-08-27, `DEF-1702`) and is kept rather than deleted
//         (hard-won law 1).** It read: *"three of four state segments are OFF
//         carrying the columns they would need; `closed` is a MINTED code and
//         not B18's `Done`"*. Both facts still hold about the DATA; the STRIP is
//         deleted, because the fourth segment was the one already active and
//         `onSelect={() => undefined}` had nothing to write · E3 **the filter
//         dimension is `f.closed` — a WINDOW on `closed_at` (last 7 / 30 / 90
//         days) — and NOT a state**, and this tab is the clearest proof a segment
//         and a filter are different questions: exactly one state is servable, so
//         a State group would offer one option that changes nothing (B14 rule 9).
//         The three unservable states are still SERVED and still stated · E3 the STEP bar draws the SERVER's `of` — never a literal (BR-SHL-046's durable half; the number moved to four on 2026-09-24),
//         never B18 §5.6.2's superseded four · E3 FINAL READ renders the
//         absence: no read seam, and `estimated` has no home on a settlement ·
//         E3 no `request #` search leg — a move-out creates no child, so
//         `outcome_ref` is null on every move-out request · E2 **the exception
//         that read *"no row action, no `+ New move-out` primary … no sortable
//         column"* IS SUPERSEDED (2026-09-19, `DEF-CUS-5900`) and is kept
//         rather than deleted (hard-won law 1).** Every row now carries p117's
//         `↗ Open` onto `/moves/{ref}`, the reference and the account are
//         links, and two columns have been sortable since `BR-CUS-1046` · E3
//         no story owns this tab (law 8) — OWED, and A1 allocates the worklist
//         no screen id
// exceptions: **[p117 · PO 2026-09-19]** E3 **THE HEAD IS NOT IN THIS FILE AND
//         IS NOT IN THIS COMMIT.** p117 draws an `ACCOUNTS` kicker, the title
//         **The register**, the sub-line `10 tabs · Move-outs · N still open`,
//         a breadcrumb reaching `Accounts / Move-outs`, and an `Accounts` tab
//         with NO count. All five live in `AccountsListPage.tsx`'s ONE
//         `PageHeader`, which serves all ten tabs — retitling it from a
//         Move-outs lane would rename the page under nine siblings. REPORTED,
//         with the exact strings, to whoever owns that file · E3 **`[▦
//         Columns]` STILL RENDERS AS A GLYPH ALONE** where p117 draws `Columns
//         ▾`. The control is `components/ColumnChooser.tsx`, shared by every
//         `DataTable` in the product, and adding the word from here would
//         change every list at once on one screen's authority — B14 rule 38's
//         own reasoning, one layer up. REPORTED · E3 **`[⇩ Export]` IS NOT
//         RENDERED, AND THE DRAWING SHOWS IT.** `apps/customers/` has no
//         `exports.py` and registers no `move-outs` resource, so BR-SHL-010
//         keeps an undeclared capability unrendered and `DEF-1005` carries it.
//         The change list's *"verify it sits on the first row"* could not be
//         verified because there is no button; drawing one would wire a control
//         to a 404 · E3 **THE DRAWING'S FOUR SEGMENT CHIPS ARE DELIBERATELY
//         ABSENT** — `Open` · `Leaving this week` · `Closed` · `All`. B14 rule
//         12 fixes this toolbar's grammar and `FilterBar`'s own docstring
//         records why the strip was removed: the applied state was visible only
//         INSIDE a select, so a user could not remove one filter without first
//         finding the right one. This is the one place p117 loses, and it loses
//         on rule 38's reasoning — how a control is BUILT is our rules' to
//         decide · E3 **THE SETTLEMENT CELL STILL RENDERS NO DIRECTION ON ANY
//         ROW.** p117 draws `Short by $186.40`; `move_out_settlement_cell`
//         hard-codes `landing: None`, `complete: False` and serves no `net`, so
//         the direction branch is built and unreachable until the server
//         answers. Deriving it here is what §2 forbids · E3 **`State` SAYS
//         `Closed` WHERE p117 SAYS `Completed`** — `DEF-CUS-5901`, whose other
//         half is `move_record_reads.STATE_COMPLETED`. Left for the backend
//         lane on purpose: papering one vocabulary over the other in the front
//         end is how the two screens stop being comparable · E3 `Step not
//         recorded` and `Not readable here` are UNCHANGED. Both are honest
//         absences carrying a server reason, not copy faults, and whether the
//         data exists is the backend lane's finding
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
