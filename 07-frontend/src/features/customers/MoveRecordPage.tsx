// ── Trace ──────────────────────────────────────────────
// Change:   The MOVE RECORD screen — blueprint `02 Accounts Menu Blueprint.pdf`
//           p074, *"The move-in, opened · MVI-26-0114 ·
//           /brazosbend/moves/mvi-26-0114 · Proposed"*. Approved by the PO on
//           2026-09-19: *"we have to buid … we have it in drawing that is our
//           next work"*. Drawn and never built — no route, no component, no
//           endpoint until this commit.
// Rules:    B14 rule 42 (the drawing is read AS AN IMAGE; this screen was built
//           from a 2.6x and a 5x render of p074, never from extracted text —
//           the labels are not IN the text layer) · rule 41 (the product
//           matches the blueprint) · rule 40 (page-head title 32px, which
//           `PageHeader` now carries on both branches) · rule 2 (ONE page
//           header) · rule 31 (no database id is ever a field's visible value)
//           · rules 32/33 (the copy budget — see §3) · rule 21 + its per-file
//           clause (Tailwind utilities; this file is on
//           `styles/route-b-migrated.txt`) · rule 36 (the shared kit is how you
//           comply) · hard-won law 2 and its mirror (no dead control, and no
//           live control that refuses over something already shipped)
// Screens:  the MOVE RECORD, `/moves/{ref}` — a NEW TOP-LEVEL route
// Tests:    src/features/customers/MoveRecordPage.test.tsx
// Impacts:  06-backend/apps/customers/move_record_reads.py (the one read) ·
//           App.tsx (the route) · MoveInsTab.tsx (the reference and `↗ Open`
//           gain this destination) · styles/route-b-migrated.txt
//
// Change 2: **THE RESUME DOOR** — PO ruling 2026-09-19, *"We will need this
//           action on details page - 4 · Close or complete it"*, the fourth of
//           four capabilities. An `in_flight` record gains ONE action that
//           carries the clerk back into the wizard at the parked step; a
//           COMPLETED record is untouched. The work does not move — the door
//           does: `resumePath()` in parkedDrafts.tsx is the one builder for
//           `?parked=<id>` and this page uses it rather than rebuilding six
//           steps on a second surface.
// Impacts2: move_record_reads.py `_in_flight` (serves `park_id`, the handle a
//           reference cannot give) · parkedDrafts.tsx (`resumePath` widened to
//           the two fields it reads) · MoveRecordPage.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠⚠ **THE SENTENCE BELOW IS NOW TRUE OF A *COMPLETED* RECORD ONLY — AMENDED
// 2026-09-19, THE SAME DAY IT WAS WRITTEN (PO ruling: *"We will need this
// action on details page - 4 · Close or complete it"*).** It read as a flat
// statement about this screen, and it governed both states; an UNFINISHED move
// now carries exactly one action, `Resume`, which carries the clerk back into
// the wizard at the step the draft was parked at. **A completed record is
// unchanged and the paragraph below still rules it** — no action was added
// there, and the count assertion in the test file holds it to two doors.
//
// ⚠ **THE DISTINCTION THE ORIGINAL MISSED IS THE ONE THE BLUEPRINT ITSELF
// MAKES**, and it is worth naming because the amendment is otherwise easy to
// read as a reversal. The paragraph's own reasoning is *"records of acts that
// have ALREADY HAPPENED — there is nothing left to decide on them"*. An
// in-flight move is the one case where that premise is false: the act has not
// happened, there IS something left to decide, and p077 draws such a row on the
// list with an `↗ Open` of its own. So the ruling did not overturn the
// blueprint; it answered the state the blueprint's sentence never described.
//
// ⚠ **THIS RECORD HAS NO ACTIONS, AND THAT IS THE ANSWER RATHER THAN A GAP.**
// The blueprint says so on p074 in its own words:
//
//     *"A move-in and a sale are records of acts that have already happened —
//     there is nothing left to decide on them, so the only controls are doors
//     to the account and the customer. The two things this record says are
//     still wrong are deliberately not buttons here: the property's owner
//     record and the account's contact details are both fixed on their own
//     screens, by somebody who can see the whole picture."*
//
// It is unusual enough that somebody will try to "improve" it, which is why it
// is written here before it is built rather than left to be inferred from the
// absence of a verb. **The PO ruled the control set on 2026-09-19 and on a
// COMPLETED record it is TWO DOORS AND NOTHING ELSE** — `Open the account` and
// `Open the customer`.
// `Raise a visit` was removed (*"not required"*) and `Record the reading` was
// removed (*"if provdied in move in"*): the readings come from the wizard's
// step 3, which already accepts them and commits them through metering's event
// door, so a button here would be a second door onto one act. **This page
// DISPLAYS the opening reads it was given and never offers to create one.**
//
// ⚠ **THE PAGE RENDERS FOR A MOVE THAT HAS NOT HAPPENED YET, AND THAT IS HALF
// ITS JOB.** p073 draws `MVI-26-0113 · 3 of 6 · In progress` two rows from a
// completed one and gives BOTH an `↗ Open`. An in-flight move has no account,
// no committed-by and no opening reads, and every one of those renders as a
// STATED ABSENCE — never a dash, a blank or a zero, which would read as
// *nobody recorded one* instead of *this has not happened yet*.
//
// ⚠ **THE COPY IS NOT THE DRAWING'S, ON THE PO'S OWN INSTRUCTION**, verbatim:
// *"even if drawing sshow too much content ons creen - dont apply that we have
// to use our rules to show content on screen"*. So the SHAPE is p074's and the
// WORDS are B14 rules 32 and 33's. What was cut, and where each cut string went
// instead, is §3 — recorded rather than silently dropped, because a reader
// comparing this screen with the drawing will otherwise think something is
// missing.
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { MoneyCell } from "@/components/MoneyCell";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { UnitCell, formatQuantity } from "@/components/UnitCell";
import type { StatusTone } from "@/components/StatusPill";
import { DateCell } from "@/components/DateCell";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { MoveInDetail } from "./moveDetail/MoveInDetail";
import type { MoveInDetail as MoveInDetailRecord } from "./moveDetail/moveDetailEndpoints";
import { isMoveInStatus, moveRecordActions } from "./moveRecordActions";
import type { ShortfallPath } from "./moveRecordActions";
import { BalanceToOwnerState } from "./BalanceToOwnerState";
import type { BalanceToOwnerStateValue } from "./BalanceToOwnerState";
import { useMoveRecordActionBar } from "./moveRecordActionBar";
import { resumePath } from "./parkedDrafts";
import { parkedHomePath } from "./wizardPark";
import { isWizardParkFlow } from "./wizardParkEndpoints";
import type { WizardParkFlow } from "./wizardParkEndpoints";

/** The two flows one address serves. ⚠ **THE VALUES ARE THE SERVER'S**
 *  (`moves.KIND_MOVE_IN` / `KIND_MOVE_OUT`) — a list typed out by hand here is
 *  how an eleventh service failed to appear on the sign-up screen, silently. */
/**
 * p118's `Unit now` has no field, on either endpoint — stated here once so the
 * screen carries a REASON rather than a blank, and so the day something serves
 * it there is one place to delete.
 */
const UNIT_NOW_NOT_SERVED = {
  code: "unit_state_after_move_out_not_served",
  br_ref: "BR-MET-105a · CR-056 W6",
  detail:
    "The move record does not carry the unit's state after the tenant left, and " +
    "`close-impact` counts units occupied without saying what THIS unit now is. " +
    "A unit standing empty and a unit whose standby charge was switched off are " +
    "two different facts; deriving either from occupancy would state a " +
    "measurement nobody took.",
} as const;

export const MOVE_KIND_IN = "move_in";
export const MOVE_KIND_OUT = "move_out";

/** The reference prefix each series allocates — `moves.py:137`. */
const MOVE_OUT_REF_PREFIX = "MVO-";

/**
 * WHERE THE `←` GOES — the Move-ins tab for an arrival, Move-outs for a
 * departure.
 *
 * ⚠ **`DEF-CUS-5996`, REPORTED FROM THE LIVE PRODUCT.** PO, verbatim: *"Same
 * problem with MOve out also - it takes you to move in list page"*. This page
 * serves BOTH flows and hardcoded `/accounts?tab=move-ins` in its two header
 * sites while already holding `record.kind` — decision log 2026-09-20 §8: *"The
 * destination simply ignored a fact it already held."* **B14 rule 1 decides it:
 * a page header's `←` NAMES WHERE IT EXITS TO**, and a control that names its
 * destination cannot send a clerk to the wrong tab.
 *
 * ⚠ **THE TAB IS NOT CHOSEN HERE — `parkedHomePath` ALREADY OWNS IT.** That map
 * is what a park, a discard and a resume all read, and the decision log is
 * explicit about why a second one is not written: *"that map is the single
 * source; a second one is how two screens come to disagree."* It is also why
 * the slugs are `AccountsListPage`'s HYPHENATED tab ids (`move-outs`) and NOT
 * the backend's `QUEUE_MOVE_OUTS = "move_outs"`, which names a job queue.
 *
 * ⚠ **`kind` IS ABSENT IN THE NOT-FOUND STATE**, which is reached exactly when
 * the server could not answer — so there is no record to read it off. The
 * REFERENCE is the one fact a 404 still holds: `MVO-` is the move-out series
 * and `MVI-` the move-in one, and the lookup is `move_no__iexact`, so the
 * comparison is case-insensitive like the query it mirrors. A reference
 * carrying neither prefix keeps the Move-ins destination this page has always
 * had — the old behaviour as a stated default, not a silent guess.
 */
function moveFlow(kind: string | null, ref: string): WizardParkFlow {
  return kind !== null && isWizardParkFlow(kind)
    ? kind
    : ref.trim().toUpperCase().startsWith(MOVE_OUT_REF_PREFIX)
      ? MOVE_KIND_OUT
      : MOVE_KIND_IN;
}

export function moveRegisterPath(kind: string | null, ref: string): string {
  return parkedHomePath(moveFlow(kind, ref));
}

/**
 * The `←` LABEL, from the SAME flow as the destination above, so the word and
 * the tab cannot disagree (`DEF-CUS-5997`, `DEF-CUS-6422`). It read
 * *"The register"* for both kinds — our internal name for a list, which the
 * PO ruled out of every clerk-facing string on 2026-09-23 — and B14 rule 1
 * wants the header's `←` to name where it exits to: *Move-ins* or
 * *Move-outs*, in the tab strip's own words.
 */
export function moveRegisterLabel(
  kind: string | null,
  ref: string,
  t: (key: string) => string,
): string {
  return moveFlow(kind, ref) === MOVE_KIND_OUT
    ? t("customers.accounts.tab.moveOuts")
    : t("customers.accounts.tab.moveIns");
}

/** A1's screen id for this page. */
export const MOVE_RECORD_SCREEN = "S19.moveRecord";

/**
 * The MOVE RECORD's address — **TOP-LEVEL, not under `/accounts/`**.
 *
 * The blueprint's own URL is `/brazosbend/moves/mvi-26-0114`, and the placement
 * is the point rather than a preference: *"A move-in is a record OF an act, and
 * the thing it produced is an account"* (p073). Hanging it off `/accounts/:id`
 * would say the opposite — that the move belongs to the account — and would
 * make the address unreachable for an in-flight move, which has no account at
 * all.
 */
export function moveRecordPath(reference: string): string {
  return `/moves/${encodeURIComponent(reference)}`;
}

export const MOVE_RECORD_ROUTE = "/moves/:ref";

// ══════════════════════════════════════════════════════════════════════════
// THE WIRE SHAPE — `move_record_reads.record_detail`'s, restated
// ══════════════════════════════════════════════════════════════════════════
/**
 * One label→value cell: a value, OR the reason there is none.
 *
 * ⚠ **NEVER BOTH AND NEVER NEITHER**, which the server asserts as an invariant
 * over its whole payload. This type cannot express the rule, so the server is
 * where it is enforced; what this file guarantees is that BOTH arms are drawn —
 * an absence is rendered as its sentence, never swallowed into a dash.
 */
export interface MoveFact<T = string> {
  value: T | null;
  unavailable: MoveAbsence | null;
}

export interface MoveAbsence {
  code: string;
  br_ref: string;
  detail: string;
  wanted_reads?: readonly string[];
  wanted_columns?: readonly string[];
}

export interface MoveReadRow {
  register: string;
  reading: string | null;
  unit?: string | null;
  read_at: string | null;
  how: "read" | "not_estimated";
  /** `DEF-CUS-9765` — the event the reading was entered for
   *  (`meter_reads.event_context`: `move_in` …), `null` for an ordinary read. */
  event?: string | null;
}

export interface MoveRecordDetail {
  /**
   * ⚠ **THREE, NOT TWO, SINCE `BR-CUS-1090` (PO 2026-09-22).** `approved` is an
   * approved move-in nobody has started — a `move_in_jobs` row carrying its own
   * `MVI-`. It is NOT `in_flight`: a parked draft is work somebody has BEGUN
   * and put down, and telling a clerk covering somebody's desk that a job is
   * half-done when nothing has been typed is a different claim, so it keeps a
   * different word.
   */
  state: "completed" | "in_flight" | "approved";
  kind: string;
  move_no: string | null;
  title: string | null;
  address_line: string | null;
  effective_on: string | null;
  step?: number;
  /**
   * The parked draft's own id — **served for an `in_flight` record ONLY**, and
   * the one thing the resume door needs that the reference cannot give it.
   *
   * ⚠ **ABSENT ON A COMPLETED RECORD, AND THE ABSENCE IS LOAD-BEARING.** A
   * finished move has no draft to go back into, so this field is how the page
   * knows not to offer one — the blueprint's *"this record has no actions"*
   * ruling still governs p077 and p118, and this wave must not touch them.
   */
  park_id?: string | null;
  is_draft?: boolean;
  waiting_on?: string | null;
  park_note?: string | null;
  remind_on?: string | null;
  /**
   * **THE APPLICATION THIS JOB CAME FROM** — served on an `approved` record and
   * on nothing else (`BR-CUS-1090`).
   *
   * ⚠ **IT IS WHAT MAKES `openRequest` STOP BEING A HELD CONTROL.**
   * `moveRecordActions` has emitted `Open the request →` on a non-null
   * `requestRef` since it was written, and both call sites hardcoded `null`
   * with a note saying *"the day E3 goes green, `requestRef` starts arriving
   * and this needs no change at all"*. That day is today for the move-in half.
   * **A control correctly absent on 100% of records is indistinguishable from
   * one nobody built** — that is the note's own sentence, and it is why this
   * field is wired in the same commit that starts serving it.
   *
   * B14 rule 31 — the id rides in the href, the NUMBER is what a clerk reads.
   */
  request?: { id: string; request_no: string | null; state?: string } | null;
  /** What the application asked for, READ through the link and stored nowhere
   *  (`move_in_jobs` §2). `[]` is a real answer: an application can be taken
   *  before anybody decides what to connect. */
  services?: { code: string | null; name: string | null; available: boolean | null }[];
  documents_outstanding?: { key?: string; state?: string } | null;
  what_happened: {
    account_opened: MoveFact;
    from_account: MoveFact;
    unit: MoveFact;
    moved_in_on: MoveFact;
    earliest_legal_start: MoveFact;
    /**
     * **WHY THIS TENANCY ENDED** (PO ruling 2026-09-20, option A). One of the
     * server's `CLOSE_REASONS` CODES — never a sentence, so this screen
     * translates it (B14 rule 31: no stored code is a field's visible value).
     * Carries an absence on a move-in and on a close made before the column
     * existed; the server decides which sentence, this screen only renders it.
     */
    close_reason: MoveFact;
    committed_by: MoveFact<{ name: string | null; at: string | null }>;
  };
  opening_reads: { rows: readonly MoveReadRow[]; unavailable: MoveAbsence | null };
  money_taken: {
    required: MoveFact;
    taken: MoveFact;
    taken_on?: string | null;
    /** `DEF-CUS-9755` — deposit money recorded and not yet cleared (a check in
     * the drawer). Not counted as still to collect; not counted as taken. */
    awaiting_clearance?: MoveFact;
    still_to_collect: MoveFact;
    tender: MoveFact;
    currency?: string | null;
  };
  still_owed: {
    demand_register: MoveFact<{ count: number; registers: readonly string[] }>;
    /** `DEF-CUS-9628` — the jobs this move raised, read from Work by its number. */
    visit: MoveFact<MoveVisit>;
    carry_forward: MoveFact;
  };
  /** `CR-185-BRC10` — a move-out's tie-back to the owner; null when none. */
  balance_to_owner?: BalanceToOwnerStateValue | null;
  doors: {
    account: MoveFact<{ account_id: string; account_no: string }>;
    customer: MoveFact<{ customer_id: string; name: string | null }>;
  };
  chips: { unread_registers: number; reads_committed: number };
}

/**
 * The MONEY half of `GET /accounts/{id}/close-impact`, for p118's SETTLEMENT box.
 *
 * ⚠ **A SECOND PROJECTION OF ONE ENDPOINT, AND IT IS DELIBERATE RATHER THAN A
 * DUPLICATE READER.** `moveShared.closeImpactPort()` already reads this URL and
 * its own docstring records why it cannot serve this screen: the two sides
 * disagree about what a `CloseImpact` IS, and the payload is *"a SUPERSET on
 * the money side and a SUBSET on the impact side"* (`DEF-669`). That port maps
 * the IMPACT half — units occupied after, the owner on record, the vacant base
 * charges — and drops every money field, because the wizard panel it feeds
 * prints none of them. This screen prints ONLY money.
 *
 * So rather than widen a port four other callers depend on, this maps the
 * fields p118 draws and names the ones it ignores. **It MAPS and never CASTS,
 * for the reason `DEF-669` records: an unmapped field arrives `undefined`, and
 * `undefined` renders as a figure nobody measured.**
 *
 * ⚠ **THE LEADING SLASH IS LOAD-BEARING** — `DEF-CUS-4010`. Without it
 * `apiPath` joins tenant and path with nothing between them and every request
 * goes to `/api/brazosbendaccounts/…`, a 404 on every move-out, invisible
 * because a 404 and a stated absence look identical on screen.
 */
export interface MoveOutSettlement {
  currency: string | null;
  /** `settled` · `refund_due` · `short` · `refused_other_debt` · `refused_excess`,
   *  or `null` while the settlement is not complete. */
  landing: string | null;
  /** ⚠ **`false` IS A REAL ANSWER AND IT IS THE ONE THE SEEDED TENANT GIVES.**
   *  A settlement whose final bill has not been stated cannot total, so every
   *  figure below is null and `gaps` names why. Printing `$0.00` over that
   *  would be a screen inventing a settlement nobody ran. */
  complete: boolean;
  gaps: readonly string[];
  /** p118 `Closing balance`. */
  closing_balance: string | null;
  /** p118 `Deposit applied`. */
  deposit_applied: string | null;
  /** p118 `Short by`, in the accent. */
  shortfall: string | null;
  /** p118's `WHERE IT COULD GO`, SERVED — each path with whether it is open and
   *  the server's own reason when it is not. Never a list typed out here. */
  shortfall_paths: readonly {
    path: string;
    enabled: boolean;
    reason: string | null;
  }[];
  /** CR-056 W6 — the account a shortfall would be tied back to, and the FAULT
   *  when there is none. p118 draws `A-10001 · Elm Street Holdings LLC`. */
  unit_falls_to: {
    available: boolean;
    account_no: string | null;
    reason: string | null;
  } | null;
}

/** The field visit a move raised (`DEF-CUS-9628`): counts and the orders. */
export interface MoveVisit {
  raised: number;
  done: number;
  accepted: number;
  orders: readonly { order_no: string; done: boolean; accepted: boolean }[];
}

/**
 * `1 raised · 1 done · 1 accepted`, and each order's number as a link to it —
 * the PO's question (*"when work orders are completed is clerk able to see the
 * status update"*) answered on the record the clerk opens. Numbers only
 * (B14 rule 31).
 */
function VisitValue(props: { visit: MoveVisit; path: (to: string) => string }) {
  const { t } = useTranslation();
  const { visit } = props;
  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-2" data-move-visit="">
      <span>
        {t("customers.moveRecord.owed.visitCounts", {
          raised: visit.raised,
          done: visit.done,
          accepted: visit.accepted,
        })}
      </span>
      {visit.orders.map((order) => (
        <InlineLinkTo key={order.order_no} to={props.path(`/work/orders/${order.order_no}`)} data-visit-order={order.order_no}>
          {order.order_no}
        </InlineLinkTo>
      ))}
    </span>
  );
}

function money(cell: unknown): string | null {
  // The server sends `{stored, display}` and `display` is its own 2-dp string
  // (CLAUDE.md hard rule 2). This reads it and never re-rounds.
  if (cell === null || typeof cell !== "object") return null;
  const display = (cell as { display?: unknown }).display;
  return typeof display === "string" ? display : null;
}

export async function readMoveOutSettlement(
  accountId: string,
  client: ApiClient = api,
): Promise<MoveOutSettlement> {
  const answer = await client.get<Record<string, unknown>>(
    `/accounts/${accountId}/close-impact`,
  );
  const served = answer.data ?? {};
  const outstanding = (served.everything_outstanding ?? {}) as Record<string, unknown>;
  const applied = (served.what_is_applied ?? {}) as Record<string, unknown>;
  const verdict = (served.verdict ?? {}) as Record<string, unknown>;
  const paths = Array.isArray(served.shortfall_paths) ? served.shortfall_paths : [];
  const falls = (served.unit_falls_to ?? null) as Record<string, unknown> | null;
  return {
    currency: typeof served.currency === "string" ? served.currency : null,
    landing: typeof served.landing === "string" ? served.landing : null,
    complete: served.complete === true,
    gaps: (Array.isArray(served.gaps) ? served.gaps : []).map(String),
    closing_balance: money(outstanding.total),
    deposit_applied: money(applied.total),
    shortfall: money(verdict.shortfall),
    shortfall_paths: paths.map((row) => {
      const r = (row ?? {}) as Record<string, unknown>;
      return {
        path: String(r.path ?? ""),
        enabled: r.enabled === true,
        reason: typeof r.reason === "string" ? r.reason : null,
      };
    }),
    unit_falls_to:
      falls === null
        ? null
        : {
            available: falls.available === true,
            account_no: typeof falls.account_no === "string" ? falls.account_no : null,
            reason: typeof falls.reason === "string" ? falls.reason : null,
          },
  };
}

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export async function readMoveRecord(
  reference: string,
  client: ApiClient = api,
): Promise<MoveRecordDetail> {
  return requireData(
    await client.get<MoveRecordDetail>(`/moves/${encodeURIComponent(reference)}`),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE PIECES
// ══════════════════════════════════════════════════════════════════════════
/**
 * One drawn fact — label left, value RIGHT, a hairline between rows.
 *
 * ⚠ **THE HAIRLINE IS `border-b` ON THE ROW AND `last:border-0`, NOT A GAP.**
 * p074 draws a continuous rule between the six facts and none under the last
 * one; a `divide-y` on the parent would be equivalent here but breaks the
 * moment one row is conditionally absent, which is exactly what an in-flight
 * move does to this list.
 */
export function Fact(props: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-neutral-200 py-3 last:border-0">
      <dt className="text-sm text-neutral-600">{props.label}</dt>
      <dd className="text-sm font-medium text-right text-neutral-900">{props.children}</dd>
    </div>
  );
}

/**
 * A stated absence, drawn as the quiet half of a row.
 *
 * ⚠ **THE SENTENCE IS THE `title`, NOT THE BODY — B14 rule 33.** The server's
 * `detail` explains WHY a fact is missing, which is RATIONALE and is zero words
 * on screen. What a clerk reads is the short form; the full sentence is
 * reachable on hover and, more importantly, is in the payload for anyone
 * debugging. A dash with nothing behind it is what this exists to prevent
 * (DEF-075 / DEF-127).
 */
export function Absent(props: { absence: MoveAbsence; label: string }) {
  return (
    <span className="text-neutral-600 font-normal" title={props.absence.detail}>
      {props.label}
    </span>
  );
}

/** A fact row that draws whichever arm the server filled. */
function FactRow(props: {
  label: string;
  fact: MoveFact<unknown>;
  absentLabel: string;
  render: (value: never) => ReactNode;
}) {
  const { fact } = props;
  return (
    <Fact label={props.label}>
      {fact.unavailable ? (
        <Absent absence={fact.unavailable} label={props.absentLabel} />
      ) : (
        props.render(fact.value as never)
      )}
    </Fact>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE SCREEN
// ══════════════════════════════════════════════════════════════════════════
export function MoveRecordPage(props: RegionalProps & { client?: ApiClient } = {}) {
  const { t } = useTranslation();
  const { ref = "" } = useParams<{ ref: string }>();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  // IS-8 — a date renders in the TENANT's zone AND format, and `DateCell`
  // requires both. One regional path, the same every other dated screen uses.
  const { timeZone, dateFormat } = useRegional(props);

  const query = useQuery({
    queryKey: ["move-record", ref],
    queryFn: () => readMoveRecord(ref, client),
    enabled: ref !== "",
  });

  // ── p118's SETTLEMENT, FETCHED ABOVE EVERY EARLY RETURN ────────────────
  //
  // ⚠⚠ **THIS HOOK WAS BELOW THE `if (query.isLoading) return …` GUARDS AND IT
  // CRASHED THE WHOLE SCREEN — BOTH FLOWS (`DEF-CUS-5911`).** React counts
  // hooks per render: the first paint returns early from the loading guard and
  // runs ONE `useQuery`, the next runs TWO, and React throws *"Rendered more
  // hooks than during the previous render"* (minified #310). The page became
  // `Unexpected Application Error!` for a move-IN as well as a move-out.
  //
  // ⚠ **EVERY UNIT TEST PASSED OVER IT, AND THAT IS THE POINT.**
  // `renderToStaticMarkup` renders ONCE from seeded query data, so the second
  // render that changes the hook count never happens; `tsc` cannot see a rule
  // about call order and no gate reads rendered output. **It was found by
  // clicking the page in a browser** — hard-won law 6, which is the only check
  // in this repository that could have caught it.
  //
  // So it is declared here, unconditionally, and reads the account id
  // DEFENSIVELY off `query.data` because `record` is not in scope yet. `enabled`
  // does the narrowing that the old placement was doing by position: the
  // request is made only for a move-out that HAS an account, which is the only
  // case `close-impact` can answer.
  const settlementAccountId =
    query.data?.kind === MOVE_KIND_OUT
      ? (query.data.doors?.account?.value?.account_id ?? null)
      : null;
  const settlementQuery = useQuery({
    queryKey: ["move-record-settlement", settlementAccountId ?? ""],
    enabled: settlementAccountId !== null,
    queryFn: () => readMoveOutSettlement(settlementAccountId!, client),
  });

  // ══════════════════════════════════════════════════════════════════════════
  // THE ACTION BAR'S HOOK — DECLARED ABOVE EVERY EARLY RETURN
  // ══════════════════════════════════════════════════════════════════════════
  //
  // ⚠⚠ **THE FIRST DRAFT PUT THIS BELOW THE `if (query.isLoading) return …`
  // GUARDS AND IT WOULD HAVE CRASHED THE WHOLE SCREEN — `DEF-CUS-5911`, ON THE
  // SAME FILE, TWO WAVES EARLIER.** React counts hooks per render: the first
  // paint returns early from the loading guard and runs the hooks above it,
  // the next runs those plus every hook inside `useMoveRecordActionBar`, and
  // React throws *"Rendered more hooks than during the previous render"*.
  //
  // ⚠ **AND THE MOUNTED SUITE PASSED OVER IT, WHICH IS THE POINT.** Its
  // fixture seeds the record query, so the LOADING render never happens and
  // the hook count never changes. `tsc` cannot see a rule about call order and
  // no gate reads rendered output. **`eslint`'s `react-hooks/rules-of-hooks`
  // is what caught it** — the one check in this repository that can, and the
  // reason the file's own `DEF-CUS-5911` note was not enough on its own.
  //
  // So the context is read DEFENSIVELY off `query.data`, exactly as
  // `settlementAccountId` above it is, and the pure grid — which is not a hook
  // — is still computed after the guards where `record` is in scope.
  const pendingAccountId = query.data?.doors?.account?.value?.account_id ?? null;
  const pendingParkId =
    typeof query.data?.park_id === "string" && query.data.park_id !== ""
      ? query.data.park_id
      : null;
  const pendingResumeFlow =
    query.data?.state === "in_flight" && isWizardParkFlow(query.data.kind) ? query.data.kind : null;
  const pendingResumeTo =
    pendingResumeFlow !== null && pendingParkId !== null
      ? tenantPath(resumePath({ id: pendingParkId, flow: pendingResumeFlow }))
      : null;
  const actionBar = useMoveRecordActionBar({
    accountId: pendingAccountId,
    customerName: query.data?.doors?.customer?.value?.name ?? null,
    // ⚠ **IT ARRIVES NOW, ON AN `approved` MOVE-IN (`BR-CUS-1090`), AND THE
    // NOTE THAT USED TO STAND HERE SAID THIS WOULD HAPPEN.** It read *"NULL ON
    // EVERY RECORD TODAY … the day E3 closes, this starts arriving and nothing
    // here has to change"* — correct when written, and it would have rotted
    // silently the moment the server started serving a request, because a
    // control held on a hardcoded `null` is a live screen behind a dead door
    // (hard-won law 2's mirror, eight of them on the portal front page in one
    // day). **`move_records.request_id` is STILL never written by either
    // wizard** (`DEF-CUS-6001`, scenario `E3`), so a COMPLETED record still
    // offers nothing — that absence is unchanged and still ratified.
    requestRef: query.data?.request?.request_no ?? null,
    requestId: query.data?.request?.id ?? null,
    parkId: pendingParkId,
    resumeTo: pendingResumeTo,
    shortfallDisplay: settlementQuery.data?.shortfall ?? null,
    currency: settlementQuery.data?.currency ?? null,
    tieBackAccountNo: settlementQuery.data?.unit_falls_to?.account_no ?? null,
    // 🔒 `DEF-CUS-5927` — the READ's stated terms must be the WRITE's. This
    // screen reads `close-impact` with NEITHER stated (it shows a settlement
    // that has already happened, not one being composed), so it states neither
    // on the write and the server re-derives the same settlement it served.
    terms: {},
    client,
    afterDiscardTo: tenantPath(moveRegisterPath(query.data?.kind ?? null, query.data?.move_no ?? ref)),
  });

  if (query.isLoading) return <LoadingSkeleton variant="card" />;
  if (query.isError || !query.data) {
    return (
      <div className="p-6">
        <PageHeader
          title={t("customers.moveRecord.notFound.title")}
          backTo={{
            // No record, so no `kind` — the REFERENCE names the flow.
            to: tenantPath(moveRegisterPath(null, ref)),
            label: moveRegisterLabel(null, ref, t),
          }}
        />
        <p className="mt-4 text-sm text-neutral-600">
          {t("customers.moveRecord.notFound.body")}
        </p>
      </div>
    );
  }

  // ── CR-171-BRC10 P2.04 — A MOVE-IN IS THE REDESIGNED DETAILS VIEW ──────────
  //
  // Every move-in status the server serves (images 03–29: a request, a job, a
  // draft, a committed and a cancelled move-in) renders `MoveInDetail`, which
  // reads `status` — the list's ONE function — so the pill on the list, the
  // chip here and the buttons can never disagree. A move-OUT is untouched and
  // keeps the page below (p117–p119). The hooks above still run for both,
  // unconditionally, so the hook count never changes between renders
  // (`DEF-CUS-5911`).
  if (query.data.kind === MOVE_KIND_IN && isMoveInStatus((query.data as { status?: unknown }).status)) {
    return (
      <MoveInDetail
        record={query.data as unknown as MoveInDetailRecord}
        refKey={ref}
        regional={{ timeZone, dateFormat }}
        client={client}
      />
    );
  }

  const record = query.data;
  const day = (iso: string | null | undefined) =>
    iso ? <DateCell value={iso} timeZone={timeZone} dateFormat={dateFormat} /> : null;

  // ── the head's chips ─────────────────────────────────────────────────────
  // p074 draws three: the state, an amber register count, and the date.
  //
  // ⚠ **THE SECOND CHIP READS `1 register unread`, NOT THE DRAWING'S
  // `1 register estimated`** — a deliberate divergence, recorded in the
  // conformance file. The drawing contradicts itself on this one word: the same
  // register's `How` cell reads `Not estimated` and the page's own note says
  // *"One register opened with no figure at all"*. `estimated` and *"no figure
  // at all"* are opposite facts, and a chip that says a reading was estimated
  // when none was taken sends a clerk looking for an estimate that does not
  // exist. B14 rule 37 settles the shape — a figure in a wireframe is an
  // illustration — and rule 33 requires the FACT to be true in six words.
  const chips: { key: string; label: ReactNode; tone: StatusTone }[] = [];
  if (record.state === "completed") {
    chips.push({
      key: "state",
      label: t("customers.moveRecord.state.completed"),
      tone: "success",
    });
  } else if (record.state === "approved") {
    // ⚠ **ITS OWN WORD, NOT `In progress`** (`BR-CUS-1090`). Nobody has started
    // this job; borrowing the draft's word would tell a clerk that somebody is
    // holding it. `move_reads.MOVE_IN_STATE_PENDING` keeps the same two facts
    // apart on the list, for the same reason.
    chips.push({
      key: "state",
      label: t("customers.moveRecord.state.approved", { defaultValue: "Approved" }),
      tone: "info",
    });
  } else {
    chips.push({
      key: "state",
      label: t("customers.moveRecord.state.inProgress"),
      tone: "info",
    });
    if (record.step) {
      chips.push({
        key: "step",
        label: t("customers.moveRecord.state.step", { step: record.step }),
        tone: "neutral",
      });
    }
  }
  if (record.chips.unread_registers > 0) {
    chips.push({
      key: "unread",
      label: t("customers.moveRecord.chip.unread", { count: record.chips.unread_registers }),
      tone: "warning",
    });
  }
  if (record.effective_on) {
    chips.push({
      key: "movedIn",
      label: (
        <>
          {/* p118 draws `Moved out 01/28/2026` where p077 draws `Moved in`. One
              chip, two words, chosen by the flow — never two chips with one
              hidden, which is how a screen comes to render both. */}
          {t(
            record.kind === MOVE_KIND_OUT
              ? "customers.moveRecord.chip.movedOut"
              : "customers.moveRecord.chip.movedIn",
          )}{" "}
          {day(record.effective_on)}
        </>
      ),
      tone: "neutral",
    });
  }

  const accountDoor = record.doors.account;
  const customerDoor = record.doors.customer;

  // ── THE DOOR THAT FINISHES AN UNFINISHED MOVE ────────────────────────────
  //
  // PO ruling 2026-09-19, verbatim: *"We will need this action on details page
  // - 4 · Close or complete it"* — the fourth of the four capabilities they
  // named that hour. Before it, a clerk who opened an `In progress` row from
  // the list arrived at a dead end and had to go back to the parked-drafts
  // panel to carry on.
  //
  // ⚠ **THE WORK DOES NOT MOVE — THE DOOR DOES.** The six wizard steps are NOT
  // rebuilt here. `resumePath()` is the ONE builder for `?parked=<id>`, the
  // same one the parked-drafts panel uses, so the two surfaces cannot drift
  // into two spellings of one handle. Duplicating the steps on a second surface
  // is what `DEF-CUS-5901` — one state called two things on two screens — cost
  // this product already.
  //
  // ⚠ **THE LABEL IS `Resume`, AND IT IS A THIRD ANSWER TO THE RULING's OWN
  // QUESTION.** The ruling left the word to the builder and offered `Continue`
  // or `Complete`. Neither is used, and the reasoning is in the decision log:
  // `Complete` is TRUE ONLY AT STEP 6 — it over-promises at step 2 of 6, and on
  // a move-out it promises something the product cannot presently do at all
  // (no final bill is produced in the flow, so the settlement has nothing to
  // total). `Continue` is true everywhere but mints a SECOND word for an act
  // this product already names: `customers.waitingOn.action.resume` is
  // `Resume`, in all eleven catalogues, on the very panel this door replaces.
  // One act, one word — which is what B14 rule 34 settles for `Recorded` and
  // what rule 33 means by a label of three words or fewer.
  //
  // ⚠ **THE CATALOGUE KEY IS REUSED RATHER THAN COPIED, DELIBERATELY.** A new
  // `moveRecord.action.resume` key would be eleven new strings free to drift
  // from the eleven that already exist. Sharing the key makes drift
  // impossible, and a test asserts both surfaces read the same word so that
  // anyone re-wording one is told they are re-wording both.
  // ⚠ **BOTH HALVES ARE REQUIRED AND THE `park_id` HALF IS THE REAL ONE.** This
  // record is addressed by REFERENCE (`MVI-26-0114`, B14 rule 31) and the
  // wizard is resumed by ID, so a payload without `park_id` can NAME the draft
  // and cannot open it. When the server does not send one there is no door —
  // never a door built from the reference, which would resolve to nothing and
  // is hard-won law 2's mirror wearing a correct-looking URL.
  //
  // ⚠ **THE COMPUTATION MOVED ABOVE THE EARLY RETURNS AS `pendingResumeTo`**,
  // because the hook that consumes it must be declared unconditionally
  // (`DEF-CUS-5911`'s shape — see the block beside `settlementAccountId`). The
  // reasoning above it is unchanged and is left here, where a reader looking
  // for the resume door will look.

  // ── THE ONE BRANCH THIS SCREEN MAKES ──────────────────────────────────────
  //
  // ⚠ **`kind` IS SERVED AND ALWAYS WAS — MEASURED, NOT ASSUMED (2026-09-19).**
  // `GET /moves/MVO-26-0001` answers 200 with `kind: "move_out"` and
  // `state: "completed"`, so this page branches with no backend change. What it
  // does NOT do is change its SHAPE: until this commit every section was built
  // move-in shaped over a closed account, so a real move-out rendered
  // *"Account opened"* and *"Moved in on"* about somebody who had left
  // (`DEF-CUS-5889`). That is worse than a 404, because it looks like a page.
  //
  // ⛔ **THE App.tsx COMMENT CLAIMED THIS ALREADY WORKED** — *"a move-OUT record
  // answers here too … so one address serves both flows"*. Half true, and the
  // half that was false is the half that matters: the ADDRESS served both, the
  // PAGE did not. Hard-won law 1 — a comment claiming a guarantee is not the
  // guarantee — and it is corrected there rather than left.
  const isMoveOut = record.kind === MOVE_KIND_OUT;
  // ⚠ **HOISTED ABOVE THE ACTION GRID, WHICH IS THE ONLY PLACE IT CAN GO.**
  // The grid's second axis IS the settlement's landing, so the grid cannot be
  // computed before this is read. It moved up rather than the grid moving down
  // because the grid feeds the page HEADER, which renders first.
  const settlement = settlementQuery.data ?? null;

  // ══════════════════════════════════════════════════════════════════════════
  // THE RATIFIED ACTION GRID — decision log 2026-09-20 §7
  // ══════════════════════════════════════════════════════════════════════════
  //
  // ⚠ **THE SECOND AXIS IS `undecided` FOR AS LONG AS MONEY IS SHORT, AND THAT
  // IS THE SERVER'S ANSWER RATHER THAN A DEFAULT.** `settlement.landing ===
  // "short"` is what `close-impact` says; `actionBar.decided` is what this
  // clerk did a moment ago. Nothing else can distinguish the two, because
  // `shortfall_decision` answers `persisted: false` — there is no
  // `final_settlements` table — so a reload reads `short` again. The screen
  // says so in six words rather than pretending in either direction
  // (`OQ-CUS-12516`).
  const settlementShort = isMoveOut && settlement?.landing === "short";
  const gridActions = moveRecordActions({
    // ⚠ **`approved` IS ITS OWN ARM AND IS NOT FOLDED INTO `in_flight`
    // (`BR-CUS-1090`).** The first draft of this change did fold it, and the
    // BROWSER caught what no unit test could: the in-flight arm returns before
    // `openRequest` is ever considered, so the walk back to the application
    // was served by the server, typed on this page, and **drawn nowhere** —
    // built and not wired, hard-won law 2, found by walking the running app.
    // Folding it would also have offered `Resume →` and `Discard draft` on a
    // row with no draft behind either.
    state:
      record.state === "completed"
        ? "completed"
        : record.state === "approved"
          ? "approved"
          : "in_flight",
    shortfall: !settlementShort
      ? "none"
      : actionBar.decided !== null
        ? "decided"
        : "undecided",
    hasAccount: !accountDoor.unavailable,
    hasCustomer: !customerDoor.unavailable,
    // `BR-CUS-1090` — the same field the action bar above now reads. Two call
    // sites for one fact, and they must not disagree about whether the door
    // exists: the GRID decides it is drawn, the BAR decides where it goes.
    requestRef: record.request?.request_no ?? null,
    parkId: typeof record.park_id === "string" && record.park_id !== "" ? record.park_id : null,
  });
  // B14 rule 2 / `PageHeader` TC-6: exactly one primary, and it goes to the
  // slot the head draws last.
  const gridPrimary = gridActions.find((a) => a.tier === "primary") ?? null;
  const gridRest = gridActions.filter((a) => a !== gridPrimary);

  // p118 draws `Completed · Short by $186.40 · Moved out 01/28/2026`, so the
  // money chip sits BETWEEN the state and the date rather than being appended.
  //
  // ⛔ **ONLY WHEN THE SETTLEMENT LANDED SHORT, AND NEVER AS A ZERO.** On the
  // seeded tenant this settlement is `complete: false` with `final_bill_not_stated`,
  // so a `Short by $0.00` chip would state a settlement nobody has run. The
  // drawing shows the figure because the drawing shows a finished one.
  if (settlement?.landing === "short" && settlement.shortfall !== null) {
    chips.splice(1, 0, {
      key: "shortBy",
      label: (
        <>
          {t("customers.moveRecord.chip.shortBy")}{" "}
          <MoneyCell amount={settlement.shortfall} currency={settlement.currency ?? "USD"} />
        </>
      ),
      tone: "warning",
    });
  }

  return (
    <div className="p-6">
      <PageHeader
        // p074 draws `← The register`. ⚠ **THE WORD IS STILL THE DRAWING'S AND
        // THE DESTINATION NO LONGER IS (`DEF-CUS-5996`).** p074 is a move-IN
        // page, so the one list it can mean is Move-ins; this page serves BOTH
        // flows, and sending a departure to the arrivals tab is what the PO
        // reported. `moveRegisterPath` reads the record's own `kind`.
        //
        // ✅ **AND THE LABEL NOW NAMES IT (`DEF-CUS-5997`, `DEF-CUS-6422`,
        // 2026-09-24).** B14 rule 1 wants `← Move-outs` on a move-out, which
        // the PO ratified on 2026-09-20 (§6), and on 2026-09-23 the PO ruled
        // "register" out of every clerk-facing string. `moveRegisterLabel`
        // reads the same flow as the destination; `customers.moveRecord.back`
        // is retired.
        backTo={{
          to: tenantPath(moveRegisterPath(record.kind, record.move_no ?? ref)),
          label: moveRegisterLabel(record.kind, record.move_no ?? ref, t),
        }}
        // The kicker is the REFERENCE — `MOVE-IN MVI-26-0114` — which is the
        // number a clerk quotes. B14 rule 31: this is the move's NUMBER and
        // never its uuid.
        kicker={
          <span className="uppercase tracking-wide">
            {t(`customers.moveRecord.kind.${record.kind}`)} {record.move_no}
          </span>
        }
        // ⚠ **THE TITLE IS THE CUSTOMER'S NAME** (p074), at 32px — `PageHeader`
        // carries rule 40's size on both heading branches, so this screen does
        // not set it and cannot drift from the other ~137.
        title={record.title ?? record.move_no ?? ""}
        status={
          <span className="flex flex-wrap items-center gap-2">
            {chips.map((chip) => (
              <StatusPill key={chip.key} tone={chip.tone}>
                {chip.label}
              </StatusPill>
            ))}
          </span>
        }
        // ── THE RATIFIED ACTION GRID ───────────────────────────────────────
        //
        // ⚠ **THIS WAS `THE TWO DOORS, AND NOTHING ELSE` UNTIL 2026-09-20, AND
        // THAT SENTENCE WAS TRUE OF ITS OWN DAY.** It reasoned from p077's
        // *"records of acts that have already happened — there is nothing left
        // to decide on them"*, which is right about a move-IN and **wrong about
        // a move-OUT that is short**. p117's own caption says the opposite in
        // the blueprint's words: *"the one decision a closed move-out can still
        // be waiting on"*. The PO ratified the grid that settles it (decision
        // log §7, *"this si correct"*).
        //
        // ⚠ **WHICH CONTROLS EXIST IS `moveRecordActions()`'s AND NOT THIS
        // FILE'S**, so the table-driven proof can read the grid without
        // mounting a page — and so a future lane changing the rule changes it
        // in the place the test is pointed at. The header has two slots and
        // TC-6 asserts exactly one primary, so the grid's primary goes to
        // `primaryAction` and the rest to `secondaryActions`; the order inside
        // the grid is the ratified order.
        primaryAction={gridPrimary === null ? undefined : actionBar.control(gridPrimary)}
        secondaryActions={
          <>
            {gridRest.map((action) => actionBar.control(action))}
            {/* ⚠ **A STATED ABSENCE, NOT A DISABLED BUTTON AND NOT A LINKING
                FLOW.** The PO: *"Open the customer - if requried otherwise we
                will ahev to link to exisitng one"*. Linking a move to an
                existing customer is its own piece of work, and the grid simply
                does not emit the door when there is nobody to open — so the
                sentence lives here, beside the controls, rather than inside a
                grid that only decides membership. */}
            {customerDoor.unavailable ? (
              <span
                className="text-sm text-neutral-600"
                title={customerDoor.unavailable.detail}
                data-testid="move-record-no-customer"
              >
                {t("customers.moveRecord.door.noCustomer")}
              </span>
            ) : null}
          </>
        }
      />

      {/* B14 rule 11's consequence box lives here rather than inside the head:
          it is a MODAL, so where it is declared does not decide where it
          appears, and a dialog declared inside an action slot would unmount
          the moment its own commit re-rendered the header. */}
      {actionBar.dialog}
      {actionBar.failed ? (
        <p className="mt-2 text-sm text-accent-700" role="alert" data-testid="move-record-shortfall-failed">
          {t("customers.moveRecord.shortfall.failed")}
        </p>
      ) : null}

      {/* p074's address line, with its home mark. Hard rule 8: this is WALKED
          from the premises by the server — the account declares no address. */}
      {record.address_line ? (
        <p className="mt-2 flex items-center gap-2 text-sm text-neutral-600">
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path d="M3 21V9l9-6 9 6v12M9 21v-8h6v8" />
          </svg>
          {record.address_line}
        </p>
      ) : null}

      {/* p074 is TWO COLUMNS at desktop and one at phone width. */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          <Panel title={t("customers.moveRecord.section.whatHappened")}>
            <dl className="mt-1">
              {/* ⚠ **THE SAME FIELD, TWO LABELS — p077 vs p118.** `account_opened`
                  carries the account either way; on a move-out that account was
                  CLOSED, and printing *"Account opened"* over a departure is the
                  defect this branch exists to end. Relabelled rather than
                  re-served: the server's field name is a contract with four other
                  readers, and what a clerk reads is this screen's job. */}
              <FactRow
                label={t(
                  isMoveOut
                    ? "customers.moveRecord.fact.accountClosed"
                    : "customers.moveRecord.fact.accountOpened",
                )}
                fact={record.what_happened.account_opened}
                absentLabel={t("customers.moveRecord.absent.noAccountYet")}
                render={(value: string) => value}
              />
              {/* ⛔ **`From account` AND `Earliest legal start` ARE MOVE-IN FACTS
                  AND p118 DRAWS NEITHER.** A chained move-in has a predecessor and
                  a legal earliest date; a move-out has neither, and the server
                  sends both carrying honest move-in absences
                  (`move_did_not_follow_another_account`,
                  `no_prior_tenancy_on_this_unit`). Rendering those on a departure
                  states two absences about questions nobody asked — rule 32's
                  description budget, and the skill's own §2.5: an absence in the
                  drawing is a decision, not an oversight to fill in. */}
              {isMoveOut ? null : (
              <FactRow
                label={t("customers.moveRecord.fact.fromAccount")}
                fact={record.what_happened.from_account}
                absentLabel={t("customers.moveRecord.absent.notChained")}
                render={(value: string) => value}
              />
              )}
              <FactRow
                label={t("customers.moveRecord.fact.unit")}
                fact={record.what_happened.unit}
                absentLabel={t("customers.moveRecord.absent.notRecorded")}
                render={(value: string) => value}
              />
              <FactRow
                label={t(
                  isMoveOut
                    ? "customers.moveRecord.fact.movedOutOn"
                    : "customers.moveRecord.fact.movedInOn",
                )}
                fact={record.what_happened.moved_in_on}
                absentLabel={t("customers.moveRecord.absent.notChosenYet")}
                render={(value: string) => day(value)}
              />
              {/* ⚠ **WHAT THE APPLICATION ASKED FOR — `BR-CUS-1090`, and ON
                  THE APPROVED STATE ONLY.** The PO's words were *"add all
                  details from servcies request to it"*, and this is the one
                  detail no surface was showing. It is READ through the link at
                  the moment the page is drawn and stored nowhere
                  (`move_in_jobs` §2), so a clerk who adds a service to the
                  application sees it here without anything being kept in step.

                  ⛔ **NOT DRAWN ON A COMPLETED RECORD OR A PARKED DRAFT, AND
                  THAT IS THE DRAWING'S RULE RATHER THAN A CONDITION.** p074's
                  `What happened` table has six rows and this is not one of
                  them; a finished move-in's services are its ACCOUNT's service
                  agreements, which is a different fact with a different owner.
                  This row exists for a state the drawing never drew.

                  B14 rule 33 — a VALUE list, never a sentence. The tenant's own
                  names, joined the way every other service list on this product
                  is joined. */}
              {record.state === "approved" && (record.services?.length ?? 0) > 0 && (
                <FactRow
                  label={t("customers.moveRecord.fact.servicesAsked", {
                    defaultValue: "Services asked for",
                  })}
                  fact={{
                    value: (record.services ?? [])
                      .map((svc) => svc.name ?? svc.code ?? "")
                      .filter(Boolean)
                      .join(" · "),
                    unavailable: null,
                  }}
                  absentLabel={t("customers.moveRecord.absent.notRecorded")}
                  render={(value: string) => value}
                />
              )}
              {isMoveOut ? null : (
              <FactRow
                label={t("customers.moveRecord.fact.earliestStart")}
                fact={record.what_happened.earliest_legal_start}
                absentLabel={t("customers.moveRecord.absent.noPriorTenancy")}
                render={(value: string) => day(value)}
              />
              )}
              {/* ⛔ **p118 DRAWS `Unit now · Vacant · standby off` AND NOTHING
                  SERVES IT.** Not on the move record, not on `close-impact`.
                  It is the one drawn fact of this section with no field behind
                  it, so it is stated as an absence naming what would close it
                  rather than derived from occupancy — a unit standing empty and
                  a unit whose standby was switched off are two facts, and
                  guessing either from the other is how a screen states a
                  measurement nobody took. */}
              {isMoveOut ? (
                <FactRow
                  label={t("customers.moveRecord.fact.unitNow")}
                  fact={{ value: null, unavailable: UNIT_NOW_NOT_SERVED }}
                  absentLabel={t("customers.moveRecord.absent.unitStateNotServed")}
                  render={(value: string) => value}
                />
              ) : null}
              {/* ✅ **WHY THIS TENANCY ENDED — THE OTHER HALF OF THE RULING**
                  (PO 2026-09-20, option A). Storing the reason and never
                  showing it again would be the same defect one move along:
                  *"a value a clerk types that no screen returns"*. p118's
                  drawn list does not have this row, and it predates the
                  ruling by eight days — an absence in a drawing is a decision
                  only about what the drawing was asked to decide (§2.5).

                  ⚠ **MOVE-OUT ONLY, like `unitNow` above it.** A move-in ends
                  no tenancy, so the row would state an absence about a
                  question nobody asked — B14 rule 32's description budget,
                  and the reasoning the `from_account` branch already records.

                  ⚠ **THE CODE IS TRANSLATED, NEVER PRINTED** (B14 rule 31).
                  `lease_ended` is a stored value; what a clerk reads is the
                  catalogue's own sentence in their own language. */}
              {isMoveOut ? (
                <FactRow
                  label={t("customers.moveRecord.fact.closeReason")}
                  fact={record.what_happened.close_reason}
                  absentLabel={
                    // ⚠ **TWO SILENCES, TWO LABELS, AND THE SERVER DECIDES
                    // WHICH.** *Nobody was asked* (the close predates the
                    // column) and *they did not say* (asked, skipped) are
                    // different facts about the utility's own record, and one
                    // label covering both would be wrong half the time. Each
                    // is ≤ 3 words — B14 rule 33's cap for a label.
                    record.what_happened.close_reason.unavailable?.code === "close_reason_not_given"
                      ? t("customers.moveRecord.absent.closeReasonNotGiven")
                      : t("customers.moveRecord.absent.closeReasonNotAsked")
                  }
                  render={(value: string) => t(`customers.moveOut.reason.${value}`)}
                />
              ) : null}
              <FactRow
                label={t("customers.moveRecord.fact.committedBy")}
                fact={record.what_happened.committed_by}
                absentLabel={t("customers.moveRecord.absent.notCommittedYet")}
                render={(value: { name: string | null; at: string | null }) => (
                  <span>
                    {value.name}
                    {value.at ? <span className="text-neutral-600"> · {day(value.at)}</span> : null}
                  </span>
                )}
              />
            </dl>
          </Panel>

          {/* p077 calls these the OPENING reads and p118 calls them the FINAL
              read — same table, opposite ends of a tenancy. */}
          <Panel
            title={t(
              isMoveOut
                ? "customers.moveRecord.section.finalReads"
                : "customers.moveRecord.section.openingReads",
            )}
          >
            {record.opening_reads.unavailable ? (
              <p
                className="mt-2 text-sm text-neutral-600"
                title={record.opening_reads.unavailable.detail}
                data-testid="move-record-reads-absent"
              >
                {t(`customers.moveRecord.readsAbsent.${record.opening_reads.unavailable.code}`, {
                  defaultValue: t("customers.moveRecord.absent.notRecorded"),
                })}
              </p>
            ) : (
              <table className="mt-2 w-full text-sm">
                <thead>
                  <tr className="border-b border-neutral-200 text-left text-xs uppercase tracking-wide text-neutral-600">
                    <th className="py-2 font-medium">{t("customers.moveRecord.reads.register")}</th>
                    <th className="py-2 font-medium">{t("customers.moveRecord.reads.reading")}</th>
                    <th className="py-2 font-medium">{t("customers.moveRecord.reads.readDate")}</th>
                    <th className="py-2 font-medium">{t("customers.moveRecord.reads.how")}</th>
                  </tr>
                </thead>
                <tbody>
                  {record.opening_reads.rows.map((row) => (
                    <tr key={row.register} className="border-b border-neutral-100 last:border-0">
                      <td className="py-2">{row.register}</td>
                      <td className="py-2">
                        {/* `DEF-CUS-9650` — the shared quantity formatter, never
                            the stored NUMERIC(18,6): it read 16082.000000 kWh. */}
                        {row.reading === null ? (
                          <span className="text-neutral-400">—</span>
                        ) : row.unit ? (
                          <UnitCell quantity={row.reading} unit={row.unit} />
                        ) : (
                          <span className="tabular-nums">{formatQuantity(row.reading)}</span>
                        )}
                      </td>
                      <td className="py-2">{day(row.read_at)}</td>
                      <td className="py-2">
                        {/* The drawing's two words, and no third is possible. */}
                        {row.how === "read"
                          ? t("customers.moveRecord.reads.wasRead")
                          : t("customers.moveRecord.reads.notEstimated")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </div>

        <div className="flex flex-col gap-6">
          {isMoveOut ? (
            <MoveOutMoney
              settlement={settlement}
              loading={settlementQuery.isPending}
              decided={actionBar.decided}
              tieBackAccountNo={settlement?.unit_falls_to?.account_no ?? null}
            />
          ) : null}
          {/* `DEF-CUS-9628` — a move-out raises its final read too, and the
              record had no line for it at all. The visit row alone: the
              move-in's demand-register and carry-forward rows are not facts
              about a departure. */}
          {isMoveOut ? (
            <Panel title={t("customers.moveRecord.section.stillOwed")}>
              <dl className="mt-1">
                <FactRow
                  label={t("customers.moveRecord.owed.visit")}
                  fact={record.still_owed.visit}
                  absentLabel={t("customers.moveRecord.owed.notRaised")}
                  render={(value: MoveVisit) => <VisitValue visit={value} path={tenantPath} />}
                />
                {/* `CR-185-BRC10` — the tie-back to the owner: pending until
                    the final bill is sent, then posted. Absent when nobody
                    tied the balance back. */}
                {record.balance_to_owner ? (
                  <Fact label={t("customers.moveOut.done.balanceToOwner")}>
                    <BalanceToOwnerState
                      state={record.balance_to_owner}
                      currency={record.money_taken.currency ?? "USD"}
                      t={t}
                      testId="move-record-balance-to-owner"
                    />
                  </Fact>
                ) : null}
              </dl>
            </Panel>
          ) : null}
          {isMoveOut ? null : (
          <Panel title={t("customers.moveRecord.section.moneyTaken")}>
            {/* p074 draws this as a BORDERED BOX inside the section, with the
                total separated by a heavier rule. */}
            <div className="mt-2 rounded-md border border-neutral-300 p-4">
              <p className="text-sm font-semibold text-neutral-900">
                {t("customers.moveRecord.money.deposit")}
              </p>
              <dl className="mt-2">
                <FactRow
                  label={t("customers.moveRecord.money.required")}
                  fact={record.money_taken.required}
                  absentLabel={t("customers.moveRecord.absent.noPlanStandard")}
                  render={(value: string) => (
                    <MoneyCell amount={value} currency={record.money_taken.currency ?? "USD"} />
                  )}
                />
                {/* ⚠ **THE DRAWING'S `Taken · cheque 4471` LOSES ITS CHEQUE
                    NUMBER, AND THE REASON RIDES HERE RATHER THAN VANISHING.**
                    The tender and its confirmation are columns on the PAYMENT
                    row; B1 forbids the join and payments publishes no read for
                    them. So the AMOUNT and the DATE are drawn — both from the
                    register customers owns — and the missing half is reachable
                    on the value a clerk would look at for it, as a `title`.
                    Zero words on screen (rule 33), and not silently dropped,
                    which is the absence nobody can see that CLAUDE.md names. */}
                <FactRow
                  label={t("customers.moveRecord.money.taken")}
                  fact={record.money_taken.taken}
                  absentLabel={t("customers.moveRecord.absent.notRecorded")}
                  render={(value: string) => (
                    <span title={record.money_taken.tender.unavailable?.detail}>
                      {/* `DEF-CUS-9632` — the stored 4-dp string printed raw
                          read `0.0000`; MoneyCell is the one 2-dp path. */}
                      <MoneyCell amount={value} currency={record.money_taken.currency ?? "USD"} />
                      {record.money_taken.taken_on ? (
                        <span className="text-neutral-600">
                          {" · "}
                          {day(record.money_taken.taken_on)}
                        </span>
                      ) : null}
                    </span>
                  )}
                />
              </dl>
              <div className="mt-2 flex items-baseline justify-between gap-4 border-t-2 border-neutral-900 pt-3">
                <span className="text-sm font-semibold text-neutral-900">
                  {t("customers.moveRecord.money.stillToCollect")}
                </span>
                <span className="text-sm font-semibold text-neutral-900">
                  {record.money_taken.still_to_collect.unavailable ? (
                    <Absent
                      absence={record.money_taken.still_to_collect.unavailable}
                      label={t("customers.moveRecord.absent.noPlanStandard")}
                    />
                  ) : (
                    <MoneyCell
                      amount={record.money_taken.still_to_collect.value as string}
                      currency={record.money_taken.currency ?? "USD"}
                    />
                  )}
                </span>
              </div>
            </div>
          </Panel>
          )}

          {isMoveOut ? null : (
          <Panel title={t("customers.moveRecord.section.stillOwed")}>
            <dl className="mt-1">
              <FactRow
                label={t("customers.moveRecord.owed.demandRegister")}
                fact={record.still_owed.demand_register}
                absentLabel={t("customers.moveRecord.absent.notRecorded")}
                render={(value: { count: number; registers: readonly string[] }) =>
                  value.count === 0
                    ? t("customers.moveRecord.owed.allRead")
                    : t("customers.moveRecord.owed.unread", { count: value.count })
                }
              />
              <FactRow
                label={t("customers.moveRecord.owed.visit")}
                fact={record.still_owed.visit}
                absentLabel={t("customers.moveRecord.owed.notRaised")}
                render={(value: MoveVisit) => <VisitValue visit={value} path={tenantPath} />}
              />
              <FactRow
                label={t("customers.moveRecord.owed.carryForward")}
                fact={record.still_owed.carry_forward}
                absentLabel={t("customers.moveRecord.owed.notChecked")}
                render={(value: string) => value}
              />
            </dl>
          </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * p118's **HOW THE MONEY LANDED** and **WHERE IT COULD GO**, together, because
 * the second is only meaningful beside the first.
 *
 * ⚠ **EVERY FIGURE AND EVERY OPTION IS SERVED — NOTHING HERE IS DERIVED.**
 * `GET /accounts/{id}/close-impact` has been mounted since 2026-08-25 and it
 * carries the settlement, the four shortfall PATHS, whether each is open, the
 * server's reason when one is not, and the account a shortfall would tie back
 * to. An earlier reading of this lane's own said the fields did not exist; they
 * do, and writing "not served" over them would have been the expired-absence
 * defect this repo names three times.
 *
 * ⚠ **`complete: false` IS A REAL LANDING AND IT IS THE ONE THE SEEDED TENANT
 * GIVES.** `AC-2026-00042` answers `complete: false`, `gaps:
 * ["final_bill_not_stated"]`, every total `null`. The drawing shows a FINISHED
 * settlement, so the drawn figures cannot be rendered for it — and `$0.00`
 * would state a settlement nobody ran (rule 37: a figure in a wireframe is an
 * illustration, never a fact to build to). The gap the SERVER named is shown
 * instead.
 */
function MoveOutMoney(props: {
  settlement: MoveOutSettlement | null;
  loading: boolean;
  /** The disposition this clerk just committed — the ratified *"short,
   *  decided"* arm. `null` on every first paint. */
  decided: ShortfallPath | null;
  tieBackAccountNo: string | null;
}) {
  const { t } = useTranslation();
  const { settlement } = props;
  return (
    <>
      <Panel title={t("customers.moveRecord.section.moneyLanded")}>
        {props.loading ? (
          <LoadingSkeleton variant="card" />
        ) : settlement === null ? (
          <p className="mt-2 text-sm text-neutral-600" data-testid="move-record-settlement-absent">
            {t("customers.moveRecord.money.settlementNotRead")}
          </p>
        ) : settlement.complete ? (
          // p118: a BORDERED box, the total separated by a heavier rule — the
          // same shape the move-in deposit box uses, because they are the same
          // drawn component at opposite ends of a tenancy.
          <div
            className="mt-2 rounded-md border border-neutral-300 p-4"
            data-testid="move-record-settlement"
          >
            <p className="text-sm font-semibold text-neutral-900">
              {t("customers.moveRecord.money.settlement")}
            </p>
            <dl className="mt-2">
              <SettlementRow
                label={t("customers.moveRecord.money.closingBalance")}
                amount={settlement.closing_balance}
                currency={settlement.currency}
              />
              <SettlementRow
                label={t("customers.moveRecord.money.depositApplied")}
                amount={settlement.deposit_applied}
                currency={settlement.currency}
              />
            </dl>
            <div className="mt-2 flex items-baseline justify-between border-t-2 border-neutral-900 pt-2">
              <span className="text-sm font-semibold text-neutral-900">
                {t("customers.moveRecord.money.shortBy")}
              </span>
              <span className="font-semibold text-warning-700" data-testid="move-record-short-by">
                {settlement.shortfall === null ? (
                  t("customers.moveRecord.absent.notRecorded")
                ) : (
                  <MoneyCell amount={settlement.shortfall} currency={settlement.currency ?? "USD"} />
                )}
              </span>
            </div>
          </div>
        ) : (
          // ⛔ NOT a zero, and not a blank. The server names the gap; the screen
          // says which one, in the clerk's words, and nothing else.
          <p className="mt-2 text-sm text-neutral-700" data-testid="move-record-settlement-gap">
            {t(`customers.moveRecord.gap.${settlement.gaps[0] ?? "unknown"}`, {
              defaultValue: t("customers.moveRecord.money.settlementNotComplete"),
            })}
          </p>
        )}
      </Panel>

      {/* ⚠ **READ-ONLY THIS WAVE, AND THAT IS A SCOPE DECISION RATHER THAN A
          MISSING FEATURE.** p118 draws an Option / What-it-means table with
          NOTHING PRESELECTED, and the reason it gives — *"A default here would
          be the product deciding whose debt this is"* — is RATIONALE and is
          ZERO WORDS ON SCREEN (rule 33). The table states what each path means;
          choosing one is `POST /accounts/{id}/settle-shortfall`, which EXISTS
          and is wired in the next wave with its consent dialog. It moves money
          between accounts, so it is a 🔒 sensitive path: immutability, balanced
          pairs through the ledger posting service only, hard rule 7's audit_log
          write, and a human-review row. That is why it is its own wave.

          ⚠ **THE PATHS ARE THE SERVER'S, NEVER A LIST TYPED OUT HERE** — the
          eleventh-service lesson. The server sends three (`collect`,
          `payment_plan`, `transfer`) and p118 draws three. It sent a fourth,
          `write_off`, until 2026-10-12, when the PO ruled *"we will not write
          off at the time of move out"* — the balance stays outstanding and is
          chased (BR-CUS-082); a write-off is a later act in Payments. */}
      {/* ⚠ **ONCE A CLERK HAS DECIDED, THE FOUR OPTIONS BECOME A SENTENCE.**
          PO 2026-09-20 §7: *"The four options are not permanent furniture —
          they belong to one situation, money short and nobody has said whose
          it is, and once decided they become a sentence."* The controls
          themselves live in the header (the ratified grid); this panel is the
          glossary that explains them, so it turns into the outcome at the same
          moment they leave.

          ⚠⚠ **AND IT SAYS, IN FIVE WORDS, THAT IT WILL NOT SURVIVE A RELOAD.**
          `shortfall_decision` answers `persisted: false` — there is no
          `final_settlements` table — and `settlement_for` recomputes the
          landing from the BALANCE. Since 2026-10-14 a TRANSFER moves that
          balance (`OQ-1250` → a, `CR-185-BRC10`); collect and a payment plan
          do not, so for those this record reads `short` again on the next load.
          Saying nothing would be the product claiming a settlement it cannot
          produce; hiding the options for good would strand a clerk who was
          interrupted. `OQ-CUS-12516` carries the durable fix. */}
      {props.decided !== null ? (
        <Panel title={t("customers.moveRecord.section.whereItWent")}>
          <p className="mt-2 text-sm text-neutral-900" data-testid="move-record-decided">
            {t(`customers.moveRecord.decided.${props.decided}`, {
              account: props.tieBackAccountNo ?? "",
            })}
          </p>
          <p className="mt-1 text-sm text-neutral-600" data-testid="move-record-decided-not-kept">
            {t("customers.moveRecord.decided.notKept")}
          </p>
        </Panel>
      ) : settlement !== null && settlement.shortfall_paths.length > 0 ? (
        <Panel title={t("customers.moveRecord.section.whereItCouldGo")}>
          <table className="mt-2 w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-300 text-left text-neutral-600">
                <th scope="col" className="pb-1 font-medium">
                  {t("customers.moveRecord.option.option")}
                </th>
                <th scope="col" className="pb-1 font-medium">
                  {t("customers.moveRecord.option.meaning")}
                </th>
              </tr>
            </thead>
            <tbody>
              {settlement.shortfall_paths.map((row) => (
                <tr
                  key={row.path}
                  className="border-b border-neutral-200 align-top last:border-0"
                  data-shortfall-path={row.path}
                  data-shortfall-enabled={row.enabled ? "yes" : "no"}
                >
                  <td className="py-2 pr-3 font-medium text-neutral-900">
                    {t(`customers.moveRecord.path.${row.path}`, { defaultValue: row.path })}
                  </td>
                  <td className="py-2 text-neutral-700">
                    {t(`customers.moveRecord.pathMeans.${row.path}`, { defaultValue: "" })}
                    {/* The server's reason rides as the TITLE and never as copy
                        — it is engineering prose addressed to us (DEF-731), and
                        rule 33 keeps rationale off the screen. */}
                    {row.enabled ? null : (
                      <span
                        className="block text-neutral-600"
                        title={row.reason ?? undefined}
                        data-testid={`move-record-path-closed-${row.path}`}
                      >
                        {t("customers.moveRecord.option.notOpen")}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      ) : null}
    </>
  );
}

/** One line of p118's settlement box. */
function SettlementRow(props: { label: string; amount: string | null; currency: string | null }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-baseline justify-between border-b border-neutral-200 py-1.5">
      <dt className="text-neutral-700">{props.label}</dt>
      <dd className="font-medium text-neutral-900">
        {props.amount === null ? (
          <span className="text-neutral-600">{t("customers.moveRecord.absent.notRecorded")}</span>
        ) : (
          <MoneyCell amount={props.amount} currency={props.currency ?? "USD"} />
        )}
      </dd>
    </div>
  );
}

export default MoveRecordPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: blueprint p074 (rendered at 2.6x and 5x and READ AS AN IMAGE, rule
//         42) + the PO's approval and action-bar ruling of 2026-09-19 + the
//         conformance file's "The Move-ins LIST and the MOVE RECORD —
//         blueprint pages 073–074"
// generated: 2026-09-19, the move-record lane
// exceptions: E1 the amber chip says `unread` where the drawing says
//             `estimated` — the drawing contradicts itself on that word and
//             `estimated` is the false half (see the chip block) · E2
//             `Open the customer` lands on the customers register filtered to
//             that person, because this product has NO customer detail screen ·
//             E3 both of p074's red explanatory boxes are CUT — they are
//             rationale, which rule 33 puts at zero words on screen; their text
//             lives in this file's header and in the conformance file
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
