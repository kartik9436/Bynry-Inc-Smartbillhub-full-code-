// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-004 (EP-WRK-01) — the Work shell's Orders tab reads
//           `GET /work-orders`. US-WRK-001 — a row whose `connection` is null
//           is an order raised on a premises, an account or an asset alone.
// Rules:    BR-WRK-001 (Work owns the list) · BR-WRK-006 (four anchors; the
//           premise comes from whichever one the order has) · BR-SHL-011
//           (q/page/per fall back or clamp, never error)
// Tests:    src/features/work/OrdersPage.test.tsx
// Impacts:  06-backend/apps/work/api.py (serves this) ·
//           06-backend/apps/work/selectors.py (shapes the row)
// ───────────────────────────────────────────────────────
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
// DEF-WRK-4119 — the list envelope is DECLARED ONCE, in `@/api/paginated`, and
// `readListPage` is the one reader of it. This file used to write the four keys
// out by hand ELEVEN times; four of those copies described the SELECTOR's dict
// instead of the wire and three shipped screens rendered empty.
import { readListPage, readListPageWith } from "@/api/paginated";
import type { Paginated, PagedRows } from "@/api/paginated";
// CR-070 wave O — the two hosts own their own routes; this file composes
// them rather than re-spelling them (hard-won law 5: one source, derive).
import { accountDetailPath } from "@/features/customers/customersShared";
import { premisesDetailPath } from "@/features/metering/meteringShared";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1). */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** `work_orders.state` — the five tokens metering declares; three of them are OPEN. */
export type WorkOrderState = "planned" | "in_progress" | "blocked" | "completed" | "cancelled";

/** `work_orders.outcome` — five tokens, or null while the field has sent nothing. */
export type WorkOrderOutcome =
  | "passed"
  | "failed"
  | "partially_done"
  | "cancelled"
  | "waiting_on_someone_else"
  /** FB-013 (PO 2026-10-28) — the step stopped on a fresh cleared balance. */
  | "not_done_payment_received";

/**
 * Where a build is REACHED — `apps/work/seams/metering_seam.home_of_connection`.
 *
 * ⚠ **THIS EXISTS BECAUSE `/connections/<uuid>` IS NO LONGER A DESTINATION**
 * (`CR-070 §W.11`, PO 2026-09-04: *"you cannot have two different screens — this
 * is an integration problem"*). A build's progress, its units, its work orders
 * and its charges are reached from the ACCOUNT that owns it and from the
 * PREMISES it stands on, so every cell that used to link to that screen links
 * here instead.
 *
 * `kind` is the host and `id` is a LINK target — never the visible value of a
 * field, which B14 rule 31 forbids. The visible text stays the build's own
 * number (`CON-26-0117`), which is what a clerk quotes down a phone.
 */
export interface BuildHome {
  kind: "premises" | "account";
  id: string;
}

/** The CONNECTION cell of any work-order list: the number a person reads, and
 *  the place the link goes. */
export interface WorkOrderConnectionCell {
  id: string;
  connection_no: string | null;
  /** null only for a build with neither an owner account nor a premises, which
   *  `connections.premises_id` being NOT NULL makes impossible today. The cell
   *  then draws the number as TEXT rather than as a link to nowhere — a link
   *  that silently goes nowhere passes every test in this repo (law 6). */
  home: BuildHome | null;
}

export interface WorkOrderPremise {
  id: string;
  premise_no: string | null;
  address: string;
}

/** One row of `GET /work-orders` — `apps/work/selectors._row`, verbatim. */
export interface WorkOrderRow {
  id: string;
  order_no: string | null;
  type: string;
  premise: WorkOrderPremise | null;
  /** `DEF-WRK-9671` — the asset's own location note, ONLY when the job stands
   *  on no premises (a meter in the warehouse); `null` otherwise. */
  stored_at?: string | null;
  service: string | null;
  state: WorkOrderState;
  outcome: WorkOrderOutcome | null;
  mode: string;
  is_gate: boolean;
  /** null when the order stands on a premises, an account or an asset alone (BR-WRK-006). */
  connection: WorkOrderConnectionCell | null;
  account: { id: string; account_no: string } | null;
  raised_at: string | null;
}

/**
 * `GET /work-orders`'s row — **wave A's seven PLUS the dispatcher's** (CR-070
 * wave G, `apps/work/dispatch._dispatch_row`).
 *
 * ⚠ **A SEPARATE TYPE, AND THE REASON IS A ROUTE THAT WOULD OTHERWISE LIE.**
 * These fields grow ONE list — the Orders tab and the dispatcher are the same
 * route with two readers, and the `Columns ▾` chooser decides which columns a
 * given dispatcher sees. Putting the whole dispatch set on the BASE row would
 * declare, in the type system, that every route serving a `WorkOrderRow` sends
 * an assignee and an area — and `GET /work-orders/awaiting-approval` does not,
 * so every cell reading one would be `undefined` with `tsc` perfectly happy.
 *
 * ⚠ **THIS PARAGRAPH USED TO NAME `GET /premises/{id}/work-orders` AND
 * `GET /accounts/{id}/work-orders` AS SERVING *NONE* OF THEM, AND THAT WAS
 * OVERTAKEN TWICE** (hard-won law 1). Wave `C6` put `technician`, `due_at` and
 * the appointment window on `ScopedWorkOrderRow`; 2026-09-13 added `priority`
 * and `source`, which the account blueprint draws as columns. Both scoped
 * routes serve them today — see `ScopedWorkOrderRow` below.
 *
 * ⚠ THEY DO NOT REPLACE THE SEVEN. A first draft on the server returned only
 * this half and `test_us_wrk_004` went red on a missing `connection`; nothing
 * on this side would have caught it, because a narrower object typechecks and
 * an empty CONNECTION cell looks exactly like a job that has no build.
 */
export interface WorkOrderDispatchRow extends WorkOrderRow {
  // ⚠ THESE GROW THE ROW, THEY DO NOT REPLACE IT. There is ONE `GET
  // /work-orders` with two readers — the Orders tab drew the seven above at
  // wave A, the dispatcher draws these — so the row is the UNION and the
  // `Columns ▾` chooser decides which a given dispatcher sees. A first draft on
  // the server returned only this half and `test_us_wrk_004` went red on a
  // missing `connection`; nothing on THIS side would have caught it, because a
  // narrower object typechecks and an empty CONNECTION cell looks exactly like
  // a job that has no build.
  /** null until the utility seeds priorities; the cell then draws a dash. */
  priority: WorkOrderPriority | null;
  /** null = nobody is going. Drawn as a RED pill, never as a blank cell. */
  technician: WorkOrderHolder | null;
  due_at: string | null;
  window_start: string | null;
  window_end: string | null;
  /** BR-WRK-023's third axis — where the technician is, beside `state`. */
  dispatch_state: WorkOrderDispatchState;
  /** BR-WRK-024 — RAISED BY. Null on a job raised before any door stamped a
   *  reason, which the screen draws as a dash rather than guessing one. */
  source: WorkOrderSource | null;
  source_ref: string | null;
  area: { id: string; code: string; name: string } | null;
  /** CR-168 P4.1 — did the person given the job take it? `null` when nobody
   *  holds it; `pending` until the phone answers. Optional because only the
   *  list and the order serve it (§7.3), never the scoped routes. */
  technician_acceptance?: TechnicianAcceptance | null;
}

/** P0.2 / P4.1 — the TECHNICIAN's acceptance, which is not `accepted` (the
 *  supervisor's approval of finished work, `BR-MET-110`). */
export interface TechnicianAcceptance {
  state: "pending" | "accepted" | "declined";
  at: string | null;
  reason: string | null;
}

/** BR-WRK-023 — the seven dispatch states, a THIRD axis beside state/outcome. */
export type WorkOrderDispatchState =
  | "queued"
  | "scheduled"
  | "en_route"
  | "on_site"
  | "complete"
  | "on_hold"
  | "cancelled";

/**
 * BR-WRK-024's seventeen reasons a job exists — `metering/0049` closed the
 * vocabulary, `0052`/`0056`/`0075` widened it, and `ck_work_orders_source`
 * refuses anything else.
 *
 * ⚠ **TYPED OUT RATHER THAN `string`, BECAUSE THE SCREEN TRANSLATES EACH ONE.**
 * A `string` would let a fifteenth reason land on the server with the screen
 * rendering its raw token — `DEF-322`'s shape, a dotted key on a clerk's
 * screen. The runtime list below is the other half of the same guarantee and is
 * what the test counts.
 */
export type WorkOrderSource =
  | "dunning_auto"
  | "asset_age_rule"
  | "high_usage_alert"
  | "payment_received"
  | "billing_exception"
  | "compliance_calendar"
  | "dispatcher"
  | "move_out"
  | "assets"
  | "new_connect"
  | "service_request"
  | "move_in"
  | "transfer"
  | "reconnect"
  | "failed_outcome"
  | "meter_read"
  | "disconnect"
  | "route_finding";

export const WORK_ORDER_SOURCES: readonly WorkOrderSource[] = [
  "dunning_auto",
  "asset_age_rule",
  "high_usage_alert",
  "payment_received",
  "billing_exception",
  "compliance_calendar",
  "dispatcher",
  "move_out",
  "assets",
  "new_connect",
  "service_request",
  "move_in",
  "transfer",
  "reconnect",
  // `metering/0052`, `0056` and `0075` (`DEF-CUS-9631`, 2026-10-05) — the
  // server has held seventeen since round 8; the screen's list now matches.
  "failed_outcome",
  "meter_read",
  "disconnect",
  // `work/0048` (`BR-WRK-067`, 2026-10-22) — a job raised from a route finding.
  "route_finding",
] as const;

export const WORK_ORDER_DISPATCH_STATES: readonly WorkOrderDispatchState[] = [
  "queued",
  "scheduled",
  "en_route",
  "on_site",
  "complete",
  "on_hold",
  "cancelled",
] as const;

/** A priority as the utility published it. `colour` is one of the four tokens
 *  `PRIORITY_COLOURS` allows, which are a subset of the kit's six pill tones —
 *  so the pill takes the TENANT's colour and this screen invents none. */
export interface WorkOrderPriority {
  id: string;
  code: string;
  name: string;
  colour: "danger" | "warning" | "info" | "neutral";
  rank: number;
}

/** Who has the job — a person, a crew or a contractor, ONE shape for all three
 *  because BR-WRK-029 says one test decides for all three. */
export interface WorkOrderHolder {
  kind: string;
  name: string;
  slug: string;
  /** CR-168 P1.25 (`DEF-WRK-9530`) — the holder's own id, served on the edit
   *  form so the picker opens on the job's holder. Optional: the list rows do
   *  not carry it. */
  id?: string;
}

/** The ONE list envelope every list in this product answers (A11) — and it is
 *  now literally the one declaration, `@/api/paginated`. */
export type WorkOrderList = Paginated<WorkOrderDispatchRow>;

export interface WorkOrderListQuery {
  q?: string;
  page?: number;
  per?: number;
  /** BR-WRK-026's other five, and there is no sixth beyond `q`. */
  type?: string;
  status?: string;
  priority?: string;
  technician?: string;
  area?: string;
}

/** `BR-WRK-026` — the six, named once so the screen and its test count the same
 *  set. A seventh sent as a BARE parameter is a `400` from the server. */
export const WORK_ORDER_FILTERS = [
  "q",
  "type",
  "status",
  "priority",
  "technician",
  "area",
] as const;

/**
 * `GET /work-orders` — every open order across every anchor.
 *
 * No `sort`/`dir` and no `f.<name>`: the server fixes the order until the
 * dispatcher's columns exist (wave G) and declares no filter yet, so a
 * control for either would offer something the request cannot ask for.
 */
/** One row of `GET /work-orders/awaiting-approval` — `apps/work/selectors.
 *  _approval_row`, verbatim. `Work-009`'s seven columns plus the id the eye
 *  icon opens the drawer with. */
export interface AwaitingApprovalRow {
  id: string;
  order_no: string | null;
  type: string;
  premise: WorkOrderPremise | null;
  /** `DEF-WRK-9671` — see `WorkOrderRow.stored_at`. */
  stored_at?: string | null;
  service: string | null;
  outcome: WorkOrderOutcome | null;
  completed_at: string | null;
  /** Whole days since the field finished, FLOORED — six days and twenty-three
   *  hours is *6 days*, never seven. Null only if `completed_at` is, which this
   *  queue's own condition makes impossible. */
  waiting_days: number | null;
  /** Null when the order stands on a premises, an account or an asset alone —
   *  the screen draws a dash (`BR-WRK-006`, `US-WRK-003` TC-7). */
  connection: WorkOrderConnectionCell | null;
  /** `DEF-WRK-9679` — who closed it in the field (image 22's *closed by D.
   *  Ortiz*); null where no close was recorded. Optional because a fixture
   *  recorded before round 7 does not carry it. */
  closed_by?: { name: string } | null;
}

/**
 * The queue's envelope: the house list shape plus ONE extra figure.
 *
 * `oldest_waiting` is the second half of `Work-009`'s footer — *"3 orders ·
 * oldest waiting 6 days"* — and it is a fact about the WHOLE queue, not about
 * the page in hand, which is why it cannot be computed from `results`. `null`
 * on an empty queue rather than `0`, because *"waiting 0 days"* is a sentence
 * about something that does not exist.
 */
export interface AwaitingApprovalList extends Paginated<AwaitingApprovalRow> {
  oldest_waiting: number | null;
}

/**
 * `GET /work-orders/awaiting-approval` — `BR-WRK-007`.
 *
 * Every order the field has finished and nobody has accepted, across every
 * connection and every anchor, oldest first. **No search and no sort:**
 * `Work-009` draws neither, the server fixes the order, and a control the
 * drawing does not carry is not added on the way past.
 */
export async function listAwaitingApproval(
  query: { page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<AwaitingApprovalList> {
  return requireData(
    await client.get<AwaitingApprovalList>("/work-orders/awaiting-approval", {
      query: { page: query.page, per: query.per },
    }),
  );
}

export async function listWorkOrders(
  query: WorkOrderListQuery = {},
  client: ApiClient = api,
): Promise<WorkOrderList> {
  return requireData(
    await client.get<WorkOrderList>("/work-orders", {
      query: {
        q: blank(query.q),
        page: query.page,
        per: query.per,
        // ⚠ **BARE NAMES, NOT `f.<name>`, AND THE SERVER CARES WHICH.** The
        // shared table framework serialises a declared filter as `f.type`; this
        // route reads the six as BARE parameters (`07-endpoints.md` row 61's
        // own spelling) and refuses a seventh bare name with a `400`. The
        // mapping happens HERE, once, so the screen keeps using the ordinary
        // `state.filters` record and no component has to know.
        type: blank(query.type),
        status: blank(query.status),
        priority: blank(query.priority),
        technician: blank(query.technician),
        area: blank(query.area),
      },
    }),
  );
}

/** `""` and `undefined` both mean *no filter*, and neither may reach the wire:
 *  an empty `type=` would be a filter that matches nothing. */
function blank(value: string | undefined): string | undefined {
  return value === undefined || value === "" ? undefined : value;
}


// ══════════════════════════════════════════════════════════════════════════
// CR-070 WAVE O · ONE DESTINATION — the build on the premises and the account
// ══════════════════════════════════════════════════════════════════════════
//
// PO, 2026-09-04, scoping their own ruling: *"One screen too many. The
// objection is the duplicate destination — a person should reach the build's
// progress, its units, its work orders and its charges from the account, not
// from a parallel screen. Whatever the tables are called underneath, there is
// one place to look."*
//
// ⚠ **FIVE READS AND NOT ONE NEW FILTER.** `BR-WRK-026` gives the dispatcher
// exactly six filters and a `400` on a seventh. These are PATHS, so that signed
// rule does not move and no screen is built on top of one that does.

/** Which anchor a job stands on, in the ONE word the server sends. The screen
 *  turns it into a sentence from its own catalogue — never prints the token. */
export type WorkOrderAnchorKind = "account" | "asset" | "unit" | "build" | "premises";

/**
 * One row of `GET /premises/{id}/work-orders` or `GET /accounts/{id}/work-orders`.
 *
 * The list row every work-order list in this product answers, plus the one word
 * that says which anchor this job is standing on, plus **what the drawer opens
 * with**. Those last six are here and not on `WorkOrderRow` deliberately: the
 * dispatcher's queue pages fifty orders and draws none of them, and carrying a
 * JSON document per row on a list that never reads it is a cost for nothing. A
 * premises or an account holds a handful of jobs and the person on it opens
 * them.
 */
export interface ScopedWorkOrderRow extends WorkOrderRow {
  stands_on: WorkOrderAnchorKind;
  scope: string;
  unit_label: string | null;
  external_ref: string | null;
  completed_at: string | null;
  /** ⚠ **NULL ON A COMPLETED ORDER IS THE REVIEW QUEUE.** It is the only thing
   *  in the product that says the field sent data and no person has accepted it
   *  (`BR-MET-110`), so it is served exactly as stored and never defaulted to
   *  the completion date. */
  accepted_at: string | null;
  accepted_by: string | null;
  /** What a crew sent back. A JSON document and not a column set, because what
   *  a utility collects differs per service and per template (`BR-MET-109`). */
  field_data: Record<string, unknown> | null;
  // ── CR-089 wave C `C6` (`PUJ-16`) · WHEN IS SOMEBODY COMING ──────────────
  //
  // The premises and account tabs drew seven columns and **not one was a date
  // or a name**. These three answer the question the tab exists for, and they
  // are served on the SCOPED row only — the dispatcher's own list has carried
  // them since wave G under `WorkOrderDispatchRow`.
  //
  // ⚠ **THE WINDOW AND THE DEADLINE ARE DIFFERENT PROMISES TO DIFFERENT
  // PEOPLE AND ARE NEVER COALESCED.** `window_start` is what a customer was
  // told — *Thursday, 08:00–12:00*; `due_at` is `BR-WRK-018`'s internal SLA
  // deadline, stamped at the raise. A screen printing the second as *when
  // somebody is coming* would tell a customer a time the utility never said.
  /** null = nobody is going. Drawn as a sentence, never as a blank cell. */
  technician: WorkOrderHolder | null;
  window_start: string | null;
  window_end: string | null;
  due_at: string | null;
  // ── B14 rule 41 · `ACC-T08` draws PRIORITY and RAISED BY ─────────────────
  //
  // ⚠ **THE NOTE ABOVE `WorkOrderDispatchRow` SAID THESE TWO ROUTES SERVE
  // NEITHER, AND THAT STOPPED BEING TRUE ON 2026-09-13** (hard-won law 1 — a
  // comment claiming a guarantee outliving the guarantee). `work_orders` has
  // carried `priority_id` since wave G and `source` since wave P; the account
  // blueprint draws both as columns, and `apps/work/selectors._scoped_row`
  // serves them now, through `dispatch._priority_of` so there is one shape.
  //
  // ⚠ **OPTIONAL, AND THAT IS THE HONEST DECLARATION RATHER THAN A HEDGE.**
  // A deployment whose server predates that change answers without them, and a
  // required field would make every such row a lie `tsc` cannot see. The cell
  // reads `undefined` and `null` the same way: an absence it STATES.
  priority?: WorkOrderPriority | null;
  /** `BR-WRK-024` — RAISED BY, the flow that caused this job to exist. Null on
   *  a job raised before any door stamped one. */
  source?: WorkOrderSource | null;
}

export type ScopedWorkOrderList = Paginated<ScopedWorkOrderRow>;

/** CLAUDE.md hard rule 2 — the FOUR decimals that are stored beside the TWO the
 *  SERVER rounded. A client that re-rounded `stored` would be the second
 *  rounding path `DEF-088` removed. */
export interface BuildMoney {
  stored: string | null;
  display: string | null;
}

/** One line of one of the build's bills (`CR-163-BRC10` item 18). `each` and
 *  `line_total` are the SERVER's display pairs — nothing here multiplies or
 *  rounds (hard rule 2). `quantity` is the stored string, e.g. `2.000000`. */
export interface BuildChargeLine {
  charge_code?: string | null;
  description?: string | null;
  quantity?: string | number | null;
  unit_price?: string | null;
  amount?: string | null;
  each?: BuildMoney;
  line_total?: BuildMoney;
  invoice_no?: string | null;
  invoice_id?: string | null;
  currency?: string | null;
}

/** One bill the build raised — the quote (`added: false`) or a fee added after
 *  submission (`CR-163-BRC10` item 2). */
export interface BuildBill {
  invoice_no: string | null;
  invoice_id: string;
  total: BuildMoney;
  added: boolean;
}

/** One payment behind the build's bills — `payments.selectors.payments_for_bills`
 *  (`CR-163-BRC10` item 20). `payment_no` is the receipt number AND the record's
 *  address; `applied` false means it has met no bill yet (e.g. a cheque still
 *  processing), so `amount` is the payment's own. */
export interface BuildPaymentRow {
  id: string;
  payment_no: string | null;
  posted_at: string | null;
  method_code: string | null;
  method_name: string | null;
  confirmation: string | null;
  type: string;
  purpose: string;
  status: string;
  amount: BuildMoney;
  applied: boolean;
  currency: string | null;
}

/** One thing a person wrote down as still outstanding on a build
 *  (`BR-MET-114` — human-authored, never derived, and never a blocker). */
export interface BuildTodo {
  id: string;
  title: string;
  closed_at?: string | null;
  [key: string]: unknown;
}

/**
 * A build's own facts — `GET /premises/{id}/build` and `GET /accounts/{id}/build`.
 *
 * Every figure is metering's own derivation, read through Work's seam and
 * recomputed nowhere: `state` is `connection_state()` (the derivation, never
 * the cached column), `mode` is `connection_mode()` and is **null when the
 * orders disagree**, which §8.3 calls *"the normal case, not the edge"*.
 */
export interface BuildFacts {
  id: string;
  connection_no: string | null;
  state: string;
  mode: string | null;
  target_activation: string | null;
  quote_total: BuildMoney;
  waiting_on: string | null;
  units: number;
  orders: { done: number; total: number };
  outstanding: BuildTodo[];
  home: BuildHome | null;
  premises_id: string | null;
}

/**
 * `GET /premises/{id}/build` — the build at this address, or nothing.
 *
 * ⚠ **`null` IS THE ORDINARY ANSWER.** Most premises in a utility's book were
 * connected long before this product existed. The host does not draw an empty
 * Build tab on them — it draws no Build tab at all, because a tab pointing at
 * nothing is dead UI (law 2, `G13`).
 */
export async function getPremisesBuild(
  premisesId: string,
  client: ApiClient = api,
): Promise<BuildFacts | null> {
  return requireData(
    await client.get<{ build: BuildFacts | null }>(`/premises/${premisesId}/build`),
  ).build;
}

/**
 * `GET /accounts/{id}/build` — the build this account owns, or the one at its
 * address, or nothing.
 *
 * ⚠ **THE ADDRESS IS THE PREMISES', REACHED BY WALKING** (`BR-MET-1161`): an
 * account declares no address column, so the server walks account → unit →
 * premises → build. The premises is the other host because the OWNER-ACCOUNT
 * reading is optional — a build whose owner was never named has no
 * `owner_account_id` to match — and not because nothing fills that column.
 * ⚠ **This line said *"Nothing here waits on `OQ-373`"* until 2026-09-12
 * (`DEF-MET-5081`); `OQ-373` closed 2026-08-25 → `BR-MET-116` and
 * `create_owner_account()` has written the column since.**
 */
export async function getAccountBuild(
  accountId: string,
  client: ApiClient = api,
): Promise<BuildFacts | null> {
  return requireData(
    await client.get<{ build: BuildFacts | null }>(`/accounts/${accountId}/build`),
  ).build;
}

// ══════════════════════════════════════════════════════════════════════════
// THE BUILD RECORD — `GET /connections/{id}/record`, CR-126-BRC07
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS IS THE READ THE DRAWN RECORD WAS BUILT AGAINST, AND UNTIL THIS
// DECLARATION EXISTED THE RECORD WAS DEAD UI.** The backend landed
// `connection_record.build_record` and the front end landed eight panels
// against `buildRecordSource.ts`, and nothing joined them: every panel drew a
// stated absence because nothing passed it a value. CLAUDE.md hard-won law 2 —
// *"a component with an optional prop that nothing passes is dead UI: it
// renders nothing, every test passes, and the feature does not exist."*
//
// ⛔ **IT DOES NOT ADD A SCREEN.** `OQ-MET-12520` closed on the PO's option C
// and was CONFIRMED when the collision was put to them again: the property's
// **Build tab IS the build record**. `/connections/:connectionId` stays a
// redirect (`BuildRedirect`), there is no `SCREEN_ROUTES` row and no `NCT-02`
// badge. Blueprint p098–p101 remain the CONTENT contract; only their address
// and tab strip are superseded.

/**
 * A counted pair the blueprint draws as `3 of 7`.
 *
 * ⚠ **STRUCTURALLY IDENTICAL TO `buildRecord/buildRecordSource.BuildCount` ON
 * PURPOSE, AND DECLARED HERE RATHER THAN IMPORTED FROM IT.** That file already
 * imports `BuildMoney` from this one, so importing back would close a module
 * cycle for the sake of two fields. TypeScript is structural, so
 * `record.tiles.activated` assigns straight into a `BuildCount` prop with **no
 * mapping step** — which is the point: the server was aligned to the front
 * end's published declaration precisely so the join would have nothing to
 * adapt, and an adapter is one of the places a wired screen goes wrong.
 */
export interface BuildRecordCount {
  done: number;
  total: number;
}

/**
 * One list inside the record, server-sliced.
 *
 * ⚠ **FOUR KEYS, AND DELIBERATELY NEITHER OF THIS PRODUCT'S TWO LIST
 * CONVENTIONS** — the read model says so in its own docstring. A list ENDPOINT
 * answers `{count, next, previous, results}` or `{rows, page, per, total,
 * pages}`; a SECTION is part of one document and has no URL of its own, so
 * there is no `next` to give. It avoids `rows` so that `G114`, which treats a
 * `rows` + `per` pair in a front-end declaration as the signature of the defect
 * it was written for, is not tripped by a shape that is not that defect.
 */
export interface BuildRecordSection<Row> {
  count: number;
  page: number;
  per: number;
  results: Row[];
}

/**
 * Why a drawn figure is null, as a CODE.
 *
 * ⚠ **NOTHING RENDERS THESE AND NOTHING SHOULD.** B14 rule 32 keeps a rule id
 * or an internal code off clerk-facing copy, and `this_build_has_raised_no_bill`
 * is an internal code. The panels already draw the drawing's own short absence
 * for a null value; this list is for a person reading the payload.
 */
export interface BuildRecordAbsence {
  field: string;
  code: string;
  tracks: string;
}

/**
 * One of the build's own work orders, as the record serves it.
 *
 * Only the fields the Build tab reads are declared — the row carries eleven
 * more (`type`, `service`, `scope`, `unit_label`, `mode`, `outcome`,
 * `completed_at`, `accepted_at`, `accepted_by`, `external_ref`, `field_data`),
 * and the Work orders tab reads those from its own endpoint rather than from
 * here.
 */
export interface BuildRecordOrderRow {
  id: string;
  /** `WO-26-0309` — a BUSINESS number, which is why it may be shown (rule 31). */
  order_no: string | null;
  state: WorkOrderState;
  /** Written, stored and printed — and it refuses nothing. See the banner. */
  is_gate: boolean;
}

/**
 * One unit this BUILD services, as the record's `units` section serves it.
 *
 * ⚠ **THE ROWS ARE THE BUILD'S, NOT THE PREMISES'.** `_unit_rows` walks the
 * build's own `connection_services`, so a second connection at an existing
 * block reports the units IT touches and not the whole block. That is what
 * makes this list the right one to offer *Add service* a unit from
 * (`DEF-MET-6118`).
 *
 * Only the two fields a caller outside the units table reads are declared; the
 * row carries `unit_type`, `services`, `meters`, `plan`, `occupancy`,
 * `account_no` and `characteristics` beside them, and the table that draws
 * those reads them from the same payload.
 */
export interface BuildRecordUnitRow {
  /** ⚠ A row id, so `B14` rule 31 keeps it off the screen — it is the VALUE a
   *  control sends, never the text it shows, which is `label`. */
  id: string;
  label: string;
  [key: string]: unknown;
}

/**
 * Everything blueprint p098–p101 draw, in ONE call.
 *
 * ⚠ **ONE CALL BECAUSE THE POINT OF THE RULING IS THAT THE CLERK STOPS HOPPING
 * BETWEEN THREE PLACES.** Three round trips to fill one tab would be that
 * problem wearing a different hat, so the header, the five tiles, all six
 * Overview blocks and the FIRST PAGE of every list come back together.
 * `?section=<name>&page=<n>` pages one list deeper without disturbing the
 * others; an unknown name is ignored and never a 4xx (`BR-SHL-011`).
 *
 * ⚠ **A `null` MONEY PAIR MEANS *NOBODY PRICED IT* AND IS NEVER `$0.00`.** On
 * the OUTSTANDING tile a zero says *settled* about a debt that was never
 * worked out, which is `DEF-127`'s whole lesson.
 *
 * ⚠ **`plan`, `money.lines` AND FOUR OF THE SIX SECTIONS ARE SERVED AND NOT
 * DRAWN ON THIS TAB TODAY**, and that is said here rather than left to be
 * discovered. `Units & services`, `Plan & charges`, `Communication` and
 * `Audit` are drawn as their own tabs on p099–p102 and the Build tab does not
 * host them yet; the premises' own Units, Assets and Audit-log tabs and the
 * account's Bills tab hold most of those facts already. They are declared so
 * the next lane can see what is already on the wire.
 *
 * ⚠ **`plan.services[]` CARRIES A KEY NAMED `units_energised`.** It is a
 * SERVER KEY and not screen copy — the PO ruled *"we ahe to say activate"* —
 * so nothing may render it raw, here or anywhere.
 */
export interface BuildRecord {
  id: string;
  /** `CX-26-0007`. The uuid never leaves the wire (B14 rule 31). */
  connection_no: string | null;
  header: {
    /** The record's drawn TITLE — the owner, not the property. */
    owner_name: string | null;
    /** Who APPLIED, which is a different question from who PAYS. */
    applicant: string | null;
    request_no: string | null;
    state: string;
    waiting_on: string | null;
    target_activation: string | null;
    /** Service CODES, derived from the build's rows — never a typed list. */
    services: string[];
  };
  tiles: {
    units: number;
    activated: BuildRecordCount;
    service_points: BuildRecordCount;
    work_orders: BuildRecordCount;
    quoted: BuildMoney;
    outstanding: BuildMoney;
  };
  live_state: {
    state: string;
    waiting_on: string | null;
    units_activated: BuildRecordCount;
    service_points_live: BuildRecordCount;
    target_activation: string | null;
    activated_at: string | null;
  };
  owner_and_scope: {
    /** `builder_developer` — a CODE. Labelled before it reaches a screen. */
    owner_type: string | null;
    units_prefix: string | null;
    /** `new_premise` — a CODE, and free text on the server by design. */
    scope: string | null;
    owner_or_developer: string | null;
    external_system_reference: string | null;
    /** What the ORDERS say — null when they disagree, which is the normal case. */
    mode: string | null;
    /** The build's own stamp, beside the derived reading rather than under it. */
    mode_recorded: string | null;
    /** ⊕ `CR-164-BRC10` wave 4 — a single-family owner's account: holds the
     *  home, or billing only. `null` for a master account or none. */
    owner_account_role?: "lives_there" | "billing_only" | null;
  };
  /** Nine rows, every one WALKED to `premises` — hard rule 8. */
  premise: {
    premise_type: string | null;
    premise_type_code: string | null;
    address_line: string | null;
    /** Drawn, and drawn EMPTY: a build spans a property and has many units. */
    unit_label: string | null;
    city: string | null;
    /** The administrative state (`TX`), NOT the build's state. */
    state: string | null;
    postal_code: string | null;
    parcel_or_gis_ref: string | null;
    external_ref: string | null;
    /** A LIST: route membership is per unit and a building can span several. */
    routes: { code: string | null; name: string | null; area: string | null }[];
    premise_no: string | null;
  };
  where_it_came_from: {
    request_no: string | null;
    approved: { by: string | null; at: string | null };
    created_at: string | null;
    started_at: string | null;
    /** The APPLICATION FEE, which is not the build's own outstanding. */
    fee_outstanding: BuildMoney;
  };
  plan: {
    services: Record<string, unknown>[];
    assets: Record<string, unknown>[];
    sub_meter_links: Record<string, unknown>[];
  };
  money: {
    invoice_no: string | null;
    /** The first bill's id — for its ADDRESS only, never shown (B14 rule 31). */
    invoice_id?: string | null;
    billed_to: string | null;
    /** The payer account's id — for its ADDRESS only (`CR-163-BRC10` item 21). */
    billed_to_id?: string | null;
    quoted: BuildMoney;
    /** The figure the COMMIT wrote down, beside the bill rather than instead. */
    quote_total_recorded: BuildMoney;
    taken: BuildMoney;
    outstanding: BuildMoney;
    clearing_date: string | null;
    tender: string | null;
    reference: string | null;
    lines: BuildChargeLine[];
    /** Every bill the build raised: the quote, then each added fee. */
    bills?: BuildBill[];
    /** Each payment behind the bills; `null` = payments could not be asked. */
    payments?: BuildPaymentRow[] | null;
    unavailable: BuildRecordAbsence[];
  };
  sections: {
    units: BuildRecordSection<BuildRecordUnitRow>;
    charges: BuildRecordSection<Record<string, unknown>>;
    work_orders: BuildRecordSection<BuildRecordOrderRow>;
    communication: BuildRecordSection<Record<string, unknown>>;
    audit: BuildRecordSection<Record<string, unknown>>;
    outstanding: BuildRecordSection<BuildTodo>;
  };
  /** `CR-163-BRC10` item 26 — who a clerk may send a letter to: the owner,
   *  and the request's co-applicant on the channels they gave an address for. */
  message_recipients?: { code: string; name: string | null; channels: string[] }[];
  unavailable: BuildRecordAbsence[];
}

/**
 * `GET /connections/{id}/record` — the whole build record, in one call.
 *
 * ⚠ **KEYED BY THE BUILD AND NOT BY THE HOST**, because the build is the
 * subject: a property can carry more than one, and the Build tab already holds
 * the build's id from the read beside it. A cross-tenant or unknown id is a
 * 404 and never a 403, which is hard rule 1's posture — anything else is an
 * existence oracle across the tenant boundary.
 */
export async function getBuildRecord(
  connectionId: string,
  query: { section?: string; page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<BuildRecord> {
  return requireData(
    await client.get<BuildRecord>(`/connections/${connectionId}/record`, {
      query: { section: query.section, page: query.page, per: query.per },
    }),
  );
}

/** `POST /connections/{id}/messages/{code}/send` — one letter, one channel. */
export async function sendBuildMessage(
  connectionId: string,
  code: string,
  body: { channel: string; recipient: string },
  client: ApiClient = api,
): Promise<{ state: string; copy_no: number; channel: string }> {
  return requireData(
    await client.post(
      `/connections/${connectionId}/messages/${encodeURIComponent(code)}/send`,
      body,
    ),
  );
}

export interface BuildMessagePreview {
  available: boolean;
  reason: string | null;
  subject?: string | null;
  body?: string | null;
  channel?: string | null;
}

/** `GET /connections/{id}/messages/{code}/preview` — nothing is written. */
export async function previewBuildMessage(
  connectionId: string,
  code: string,
  client: ApiClient = api,
): Promise<BuildMessagePreview> {
  return requireData(
    await client.get<BuildMessagePreview>(
      `/connections/${connectionId}/messages/${encodeURIComponent(code)}/preview`,
    ),
  );
}

/** `POST /connections/{id}/fees` — a fee added after submission (`CR-163-BRC10`
 *  item 2). The server raises and issues a NEW bill; the quote is never edited. */
export async function addConnectionFee(
  connectionId: string,
  body: Record<string, unknown>,
  client: ApiClient = api,
): Promise<{ invoice_no: string | null; invoice_id: string; total: string; charge_code: string }> {
  return requireData(await client.post(`/connections/${connectionId}/fees`, body));
}

/** `GET /premises/{id}/work-orders` — every job at this address, newest first,
 *  every anchor and every state. */
export async function listPremisesWorkOrders(
  premisesId: string,
  query: { page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<ScopedWorkOrderList> {
  return requireData(
    await client.get<ScopedWorkOrderList>(`/premises/${premisesId}/work-orders`, {
      query: { page: query.page, per: query.per },
    }),
  );
}

/** `GET /accounts/{id}/work-orders` — the jobs on this account AND at its
 *  address, each row saying which (`US-WRK-004`). */
export async function listAccountWorkOrders(
  accountId: string,
  query: { page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<ScopedWorkOrderList> {
  return requireData(
    await client.get<ScopedWorkOrderList>(`/accounts/${accountId}/work-orders`, {
      query: { page: query.page, per: query.per },
    }),
  );
}

/**
 * `GET /work/builds/{id}/home` — where an old `/connections/<uuid>` link lands.
 *
 * ⚠ **A BOOKMARK IS A WORKING LINK AND STAYS ONE.** The New Connect wizard's
 * completion, the *New connects* tab and every bookmark point at that path
 * today. A 404 would break a working link in order to punish a screen, so the
 * route redirects: to the owner account where there is one, to the premises
 * otherwise. An unknown or cross-tenant id 404s here, identically — anything
 * else would be an existence oracle across the tenant boundary.
 */
export async function getBuildHome(
  connectionId: string,
  client: ApiClient = api,
): Promise<BuildHome> {
  return requireData(await client.get<{ home: BuildHome }>(`/work/builds/${connectionId}/home`))
    .home;
}

/**
 * The path a person goes to, to see a build. **ONE function**, so the approval
 * queue, the dispatcher, the New Connect wizard's completion, the *New
 * connects* tab and the bookmark redirect cannot disagree about where a build
 * lives — which is the whole of what the PO asked for: *"there is one place to
 * look."*
 *
 * It composes the two hosts' OWN path helpers rather than spelling the routes
 * out, so the day either detail route moves this follows it (law 5: one source,
 * derive the rest).
 *
 * The `?tab=` lands the reader on the panel they came for: the account's Work
 * tab, the premises' Build tab. Both are URL state already (`BR-SHL-011` —
 * every tab is linkable), so this adds no mechanism.
 */
export function buildHomePath(home: BuildHome): string {
  return home.kind === "account"
    ? `${accountDetailPath(home.id)}?tab=work`
    : `${premisesDetailPath(home.id)}?tab=build`;
}

/**
 * The path to ONE job, opened in the drawer over its host's work-orders tab.
 *
 * The tab differs by host and the drawer does not: the account calls its tab
 * **Work** and the premises calls its **Work orders**, because on a premises
 * *"Work"* alone would sit beside Units and Assets and read as a category of
 * the place. `?order=` is the same convention S29 uses over the reads list —
 * one acceptance, one drawer, whichever screen a supervisor reached it from.
 */
export function buildOrderPath(home: BuildHome, orderId: string): string {
  const host =
    home.kind === "account"
      ? `${accountDetailPath(home.id)}?tab=work`
      : `${premisesDetailPath(home.id)}?tab=work-orders`;
  return `${host}&order=${encodeURIComponent(orderId)}`;
}


// ── Work-025 · the parts register (wave C) ──────────────────────────────────

/** One row of `GET /work/parts` — `apps/work/selectors._part_row`, verbatim.
 *
 * ⚠ **THERE IS NO `on_hand`, NO `reorder_at` AND NO `location`, AND THIS TYPE
 * IS ONE OF THE THREE PLACES THAT IS ASSERTED.** The wireframe draws all three;
 * the card that specifies the same screen says *"No stock levels, no reorder
 * points"* and wins (`DEF-WRK-3550`); whether a stock table may exist at all is
 * `OQ-WRK-1490`, OPEN. The server publishes no such key, `POST /work/parts`
 * refuses one as an unknown field, and the tests assert their absence by name.
 * Adding one HERE would be the quiet way in, which is why the absence is
 * written down where a lane would type it.
 */
export interface PartRow {
  id: string;
  part_no: string;
  name: string;
  /** null when nobody has filed it — the register draws a dash, never a blank. */
  category: { id: string; name: string } | null;
  /** hard rule 3 — a quantity carries its unit, so the register stores one. */
  unit_of_measure: string;
  /** A decimal STRING at four decimals (`"92.4000"`). MoneyCell shows `$92.40`;
   *  nothing on this side ever parses it into a number (hard rule 2). */
  unit_cost: string;
  active: boolean;
}

/** The ONE list envelope every list in this product answers (A11), plus the
 *  register's own units — the Unit filter's choices (`CR-168`, `DEF-WRK-9580`;
 *  spread beside the page by `apps/work/api.parts`). */
export type PartList = Paginated<PartRow> & { units?: string[] };

export interface PartListQuery {
  q?: string;
  page?: number;
  per?: number;
  /** `CR-168` P3.10 — `category` (a CODE, or `none`), `unit`, `status`
   *  (`active` | `inactive`). Sent as `f.<name>` (BR-SHL-011), applied in SQL
   *  before the page is cut (NFR-3). */
  filters?: Record<string, string>;
}

/** `GET /work/parts` — Work-025's register. */
export async function listParts(
  query: PartListQuery = {},
  client: ApiClient = api,
): Promise<PartList> {
  return requireData(
    await client.get<PartList>("/work/parts", {
      query: {
        q: query.q === undefined || query.q === "" ? undefined : query.q,
        page: query.page,
        per: query.per,
        ...Object.fromEntries(
          Object.entries(query.filters ?? {})
            .filter(([, value]) => value !== "")
            .map(([name, value]) => [`f.${name}`, value]),
        ),
      },
    }),
  );
}

/** What `POST /work/parts` accepts — the five fields of `BR-WRK-019` and
 *  nothing else. The server refuses an unknown field rather than ignoring it. */
export interface NewPart {
  part_no: string;
  name: string;
  unit_of_measure: string;
  /** A decimal STRING, typed by a person. Never a `number` (hard rule 2). */
  unit_cost: string;
  /** The category's NAME, as the picker shows it (B14 rule 31). */
  category?: string;
}

/** `POST /work/parts` — add one row to the register (`US-WRK-010` TC-1). */
export async function createPart(part: NewPart, client: ApiClient = api): Promise<PartRow> {
  return requireData(await client.post<PartRow>("/work/parts", part));
}

/** `PATCH /work/parts/{id}` — edit a part, or switch it off and on (`CR-168`
 *  P3.8, P3.9). Only the fields sent change; `active` is a true boolean. */
export async function updatePart(
  partId: string,
  patch: Partial<NewPart> & { active?: boolean },
  client: ApiClient = api,
): Promise<PartRow> {
  return requireData(
    await client.patch<PartRow>(`/work/parts/${encodeURIComponent(partId)}`, patch),
  );
}


// ══════════════════════════════════════════════════════════════════════════
// CR-070 WAVE D · THE TEMPLATE BUNDLE — Work-013 and Work-022
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **`id` IS A LINK TARGET AND `template_no` IS THE VISIBLE VALUE.** B14 rule
// 31 — no database id is ever the visible value of a field. `ST-0002` is what
// a supervisor reads and quotes; the uuid is what the row action opens.

/** `Work-013`'s STATUS column, derived by the server from `active` + `version`
 *  and never stored — three states out of two columns, so there is no fourth
 *  place for the same fact to be wrong. */
export type TemplateStatus = "published" | "draft" | "inactive";

/** `Work-013`'s CONTENTS cell — *2 tasks · 0 parts · 1 reading*. Zero is a
 *  NUMBER here, never a blank: a blank cell reads as a bug. */
export interface TemplateContents {
  tasks: number;
  parts: number;
  readings: number;
  safety: number;
  help: number;
}

export interface NamedRef {
  id: string;
  name: string;
}

/** One row of `GET /work/templates` — `apps/work/selectors._template_list_row`. */
export interface TemplateRow {
  id: string;
  /** NULL until the template is published: a number is allocated on publish
   *  and never reused (`BR-TEN-035`), so a draft honestly has none. */
  template_no: string | null;
  name: string;
  service: { id: string; code: string; name: string } | null;
  scope: string;
  sequence: number;
  job_type: NamedRef | null;
  skill: NamedRef | null;
  safety_kit: NamedRef | null;
  crew_size: number;
  /** Minutes, as an integer, because `Work-013`'s EST. column reads *45 min*.
   *  Null where the utility has not estimated it. */
  est_duration_minutes: number | null;
  is_gate: boolean;
  no_gate_reason: string | null;
  is_sample: boolean;
  active: boolean;
  /** 0 is a DRAFT and is not a version (`BR-WRK-011`). */
  version: number;
  contents: TemplateContents;
  status: TemplateStatus;
}

/** The house list envelope plus ONE extra figure — the footer's three counts,
 *  computed over the WHOLE list rather than the page in hand, because a footer
 *  that described the page would change as a person paged through it. */
export interface TemplateList extends Paginated<TemplateRow> {
  counts: { published: number; draft: number; inactive: number };
}

export interface TemplateBundle {
  details: {
    /** `Work-014`'s four ticks — what the technician SEES on the job. */
    show_account_summary: boolean;
    show_asset_card: boolean;
    show_access_notes: boolean;
    show_appointment: boolean;
    /** FB-023 F4 — absent from a server older than `work/0061` (read as shown). */
    show_balance_payments?: boolean;
    /** FB-028 — the Reconnect limit, 4 places; null = none set. */
    reconnect_limit?: string | null;
    /**
     * The builder's step 7 — what the technician has to BRING BACK
     * (CR-070 wave E, `work/0005`).
     *
     * ⚠ **THIS IS THE TEMPLATE'S ASK, NEVER THE JOB'S ANSWER.** What a
     * technician actually captured is `work_order_signatures`, which is
     * `US-WRK-036`'s table and phase 2's. These three are named after that
     * table's own columns so the two read in one vocabulary.
     */
    signature_required: boolean;
    refusal_reason_required: boolean;
    door_hanger_on_no_answer: boolean;
    /** `DEF-WRK-10652` (PO 2026-10-29) — the customer's preparation text
     *  (null: the utility's default applies) and the visit-message switch. */
    prep_instructions?: string | null;
    send_customer_visit_messages?: boolean;
  } | null;
  safety: { seq: number; text: string; is_mandatory: boolean }[];
  tasks: {
    seq: number;
    title: string;
    est_minutes: number;
    photo_required: boolean;
    is_mandatory: boolean;
    /** PO answer 3 (2026-10-04) — what the technician is told about this task,
     *  shown as a second line under it. Null where none was written. */
    instruction?: string | null;
    /** FB-013 — the step's payment check: how fresh the money must be
     *  (minutes; null = no check) and a fee's charge code (R111). */
    money_fresh_minutes?: number | null;
    money_charge_code?: string | null;
  }[];
  materials: {
    part_id: string;
    part_no: string;
    name: string;
    /** A decimal STRING at four decimals — never parsed into a number on this
     *  side (hard rule 2). */
    planned_qty: string;
    /** hard rule 3 — the unit travels with the quantity, in its own column. */
    unit_of_measure: string;
  }[];
  readings: {
    seq: number;
    prompt: string;
    unit_of_measure: string;
    min: string | null;
    max: string | null;
    required: boolean;
    photo_required: boolean;
    posts_as_meter_read: boolean;
  }[];
  /**
   * `kind` is `document | phone | link` (ruling 6; a stored `note` still reads).
   * A `link` row carries its https address in `link` (P3.25, stored in `ref`);
   * a held document carries the stored file's key in `ref`, a same-origin
   * `url` to its content and `file` (P3.14). `url` is null where `ref` is not
   * a file this template holds — a typed place from before the upload.
   */
  help: {
    seq: number;
    kind: string;
    label: string;
    ref: string | null;
    url?: string | null;
    link?: string | null;
    file?: { id: string; name: string; content_type: string; bytes: number } | null;
  }[];
  asset_types: { asset_type_id: string }[];
}

export interface TemplateDetail extends TemplateRow {
  bundle: TemplateBundle;
  orders_raised: number;
}

export interface TemplateVersionRow {
  version: number;
  published_at: string;
  published_by: string | null;
  change_note: string | null;
  /** Counted from `work_orders` at read time and cached nowhere. It IS the
   *  demonstration of `BR-WRK-008`: v2 is current and the v1 orders still read
   *  v1, because nothing was rewritten. */
  orders_raised: number;
  status: "current" | "superseded";
}

export interface TemplateVersions {
  template_no: string | null;
  name: string;
  versions: TemplateVersionRow[];
  orders_raised: number;
}

export interface TemplateUsage {
  orders_raised: number;
  by_version: { version: number; orders_raised: number }[];
}

export interface TemplateListQuery {
  q?: string;
  service?: string;
  page?: number;
  per?: number;
}

/** `GET /work/templates` — `Work-013`'s list, its filter and its footer. */
export async function listTemplates(
  query: TemplateListQuery = {},
  client: ApiClient = api,
): Promise<TemplateList> {
  return requireData(
    await client.get<TemplateList>("/work/templates", {
      query: {
        q: query.q === undefined || query.q === "" ? undefined : query.q,
        "f.service": query.service || undefined,
        page: query.page,
        per: query.per,
      },
    }),
  );
}

/** `GET /work/templates/{id}` — `Work-022`'s Overview: header plus bundle. */
export async function getTemplate(
  templateId: string,
  client: ApiClient = api,
): Promise<TemplateDetail> {
  return requireData(await client.get<TemplateDetail>(`/work/templates/${templateId}`));
}

/** `GET /work/templates/{id}/versions` — `Work-022`'s Versions tab. */
export async function getTemplateVersions(
  templateId: string,
  client: ApiClient = api,
): Promise<TemplateVersions> {
  return requireData(
    await client.get<TemplateVersions>(`/work/templates/${templateId}/versions`),
  );
}

/** `GET /work/templates/{id}/usage` — the total and the per-version breakdown
 *  that sums to it. */
export async function getTemplateUsage(
  templateId: string,
  client: ApiClient = api,
): Promise<TemplateUsage> {
  return requireData(await client.get<TemplateUsage>(`/work/templates/${templateId}/usage`));
}

/** One line of a template's change history — `GET /work/templates/{id}/audit`
 *  (P3.28, lane SRV-3). `act` names what happened; `collection` names the list
 *  a `replaced` changed. `summary` carries no ids (B14 rule 31). */
export interface TemplateAuditRow {
  at: string;
  by: { name: string } | null;
  act:
    | "created"
    | "updated"
    | "published"
    | "deactivated"
    | "reactivated"
    | "duplicated"
    | "replaced"
    | "help_document_stored"
    | "deleted"
    | string;
  collection: string | null;
  version: number | null;
  summary: Record<string, unknown> | null;
}

export interface TemplateAudit extends Paginated<TemplateAuditRow> {
  template_no: string | null;
  name: string;
}

/** `GET /work/templates/{id}/audit` — the trail `audit_log` already held for
 *  every builder write, paged on the server. */
export async function getTemplateAudit(
  templateId: string,
  query: { page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<TemplateAudit> {
  return requireData(
    await client.get<TemplateAudit>(`/work/templates/${templateId}/audit`, {
      query: { page: query.page, per: query.per },
    }),
  );
}

/** `POST /work/templates/{id}/help/upload-url` — where to send a help document
 *  (P3.14). Our own address, the field name, the ceiling and the types. */
export interface HelpUploadTicket {
  upload_url: string;
  method: string;
  field: string;
  max_bytes: number;
  content_types: string[];
}

/** What storing a help document answers — `ref` is what the help row keeps. */
export interface HelpDocumentStored {
  id: string;
  ref: string;
  name: string;
  content_type: string;
  bytes: number;
  url: string;
}

/** The two calls of a help upload: ask where, then send the file there. The
 *  help row itself is written by the next `PUT …/help` with the answer's `ref`. */
export async function uploadHelpDocument(
  templateId: string,
  file: File,
  client: ApiClient = api,
): Promise<HelpDocumentStored> {
  const ticket = requireData(
    await client.post<HelpUploadTicket>(`/work/templates/${templateId}/help/upload-url`, {
      filename: file.name,
      content_type: file.type,
    }),
  );
  const body = new FormData();
  body.append(ticket.field || "file", file);
  return requireData(await client.post<HelpDocumentStored>(ticket.upload_url, body));
}

/** `POST /work/templates/{id}/duplicate` — a new DRAFT carrying every child
 *  row, the name suffixed *(copy)*, no number and no version. */
export async function duplicateTemplate(
  templateId: string,
  client: ApiClient = api,
): Promise<TemplateRow> {
  return requireData(await client.post<TemplateRow>(`/work/templates/${templateId}/duplicate`, {}));
}

/**
 * `POST /work/templates/{id}/deactivate` and `/reactivate` — `BR-WRK-012`.
 *
 * ⚠ **TWO NAMED ROUTES AND NOT A `PATCH` ON `active`** (`DEF-WRK-3579`). The
 * one control a supervisor presses must not be able to arrive as an
 * untraceable field edit, so the server refuses `active` as an unknown field
 * on `PATCH` and each of these writes its own audit action.
 */
export async function setTemplateActive(
  templateId: string,
  active: boolean,
  client: ApiClient = api,
): Promise<TemplateRow> {
  const route = active ? "reactivate" : "deactivate";
  return requireData(await client.post<TemplateRow>(`/work/templates/${templateId}/${route}`, {}));
}

/**
 * `DELETE /work/templates/{id}` — refused while ANY version is referenced.
 *
 * The screen disables the button with the same reason and the server refuses
 * independently: `BR-SHL-025` asks for both halves, and a screen that only
 * greyed the control would ship a template a scripted call could still delete.
 */
export async function deleteTemplate(
  templateId: string,
  client: ApiClient = api,
): Promise<{ id: string; deleted: boolean }> {
  return requireData(
    await client.del<{ id: string; deleted: boolean }>(`/work/templates/${templateId}`),
  );
}


// ══════════════════════════════════════════════════════════════════════════
// CR-070 WAVE E · THE BUILDER'S WRITES, THE PACKS, AND WHAT STEP 6 PROPOSES
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THERE ARE THREE CALLS AND EXACTLY ONE OF THEM REACHES A WORK ORDER.**
// `BR-WRK-011`: seven steps of editing persist as a DRAFT; *Publish* is the one
// write. `createTemplateDraft` and `replaceTemplateCollection` write rows a
// browser tab can lose without loss; `publishTemplate` is what allocates the
// `ST-` number, sets the version and makes the template something New Connect
// step 6 will propose.

/** What `POST /work/templates` and `PATCH /work/templates/{id}` accept — the
 *  header field set metering declares, and NOTHING else: an unknown field is
 *  REFUSED rather than dropped, so a typo here is a 400 and not a silently
 *  missing crew size.
 *
 *  ⚠ `active` IS ABSENT ON PURPOSE (`DEF-WRK-3579`). Deactivate and Reactivate
 *  are their own routes with their own audit action, so the one control a
 *  supervisor presses can never arrive as an untraceable field edit. */
export interface TemplateHeaderPayload {
  name: string;
  /** The service CODE (`electric`), never its uuid — B14 rule 31, and it is
   *  what the picker shows. */
  service: string;
  scope?: string;
  /** `>= 1` puts this template in the connection sequence, which is what makes
   *  New Connect step 6 propose it (`BR-WRK-016`). An authored exchange or
   *  leak-investigation template leaves it at 0 and is not proposed. */
  sequence?: number;
  type_id?: string | null;
  skill_id?: string | null;
  safety_kit_id?: string | null;
  crew_size?: number;
  /** MINUTES, and Work's own service turns them into the interval the column
   *  stores. The read side has published `est_duration_minutes` since wave D;
   *  a browser converting to an ISO duration would be a second vocabulary for
   *  one fact. */
  est_duration_minutes?: number | null;
  is_gate?: boolean;
  no_gate_reason?: string | null;
}

/** `POST /work/templates` — a DRAFT. Version 0, no `ST-` number, nothing an
 *  order can be raised from (`BR-WRK-011`). */
export async function createTemplateDraft(
  payload: TemplateHeaderPayload,
  client: ApiClient = api,
): Promise<TemplateRow> {
  return requireData(await client.post<TemplateRow>("/work/templates", payload));
}

/** `PATCH /work/templates/{id}` — the header, on a draft or a published
 *  template's editable face. */
export async function updateTemplateHeader(
  templateId: string,
  payload: Partial<TemplateHeaderPayload>,
  client: ApiClient = api,
): Promise<TemplateRow> {
  return requireData(
    await client.patch<TemplateRow>(`/work/templates/${templateId}`, payload),
  );
}

/** Every name `PUT /work/templates/{id}/{collection}` answers to — the six
 *  list-shaped collections and the one-row `details`. ONE route, seven
 *  collections; see `apps/work/templates_svc.replace_collection` for why. */
export type TemplateCollection =
  | "details"
  | "safety"
  | "tasks"
  | "materials"
  | "readings"
  | "help"
  | "asset-types";

/**
 * `PUT /work/templates/{id}/{collection}` — replace one collection WHOLE.
 *
 * ⚠ **REPLACE-IN-FULL IS WHAT MAKES REORDERING WORK.** Six reordered tasks are
 * ONE call carrying the new order, not six PATCHes with a moment in between
 * where two rows both claim `seq = 3` and the unique key refuses. The list's
 * ORDER is the payload's order; `seq` is assigned from it server-side, so a
 * caller never sends one.
 */
export async function replaceTemplateCollection(
  templateId: string,
  collection: TemplateCollection,
  rows: unknown,
  client: ApiClient = api,
): Promise<{ collection: string; count: number }> {
  return requireData(
    await client.put<{ collection: string; count: number }>(
      `/work/templates/${templateId}/${collection}`,
      // `details` is an OBJECT and the six others are a LIST; the server takes
      // `{rows: […]}` or a bare list, and this sends whichever the caller has.
      Array.isArray(rows) ? { rows } : (rows as Record<string, unknown>),
    ),
  );
}

/** What `publish` answers with — the header, plus which version now stands and
 *  whether this call is what made it. */
export interface TemplatePublished extends TemplateRow {
  published_at: string;
  /**
   * ⚠ **`false` MEANS *NOTHING HAD CHANGED*, NOT *IT FAILED*.** Pressed twice
   * within a second, publish answers the version that already exists and
   * writes nothing — because a v2 identical to v1 is a number a supervisor has
   * to explain on `Work-022`. The screen says *already published* rather than
   * claiming a version it did not make.
   */
  created: boolean;
}

/** `POST /work/templates/{id}/publish` — **THE ONE WRITE** (`BR-WRK-011`). */
export async function publishTemplate(
  templateId: string,
  changeNote: string | null,
  client: ApiClient = api,
): Promise<TemplatePublished> {
  return requireData(
    await client.post<TemplatePublished>(`/work/templates/${templateId}/publish`, {
      change_note: changeNote,
    }),
  );
}

/** One row of a pack's prefill — the shape `PUT …/{collection}` takes back
 *  unchanged, so nothing is translated between the offer and the write. */
export interface TemplatePackBundle {
  details: Record<string, boolean>;
  safety: { text: string; is_mandatory: boolean }[];
  tasks: {
    title: string;
    est_minutes: number;
    photo_required: boolean;
    is_mandatory: boolean;
    /** PO answer 3 — a pack may carry one; absent reads as none. */
    instruction?: string | null;
    money_fresh_minutes?: number | null;
    money_charge_code?: string | null;
  }[];
  materials: {
    part_id: string;
    part_no: string;
    name: string;
    planned_qty: string;
    unit_of_measure: string;
  }[];
  readings: {
    prompt: string;
    unit_of_measure: string;
    min: string | null;
    max: string | null;
    required: boolean;
    photo_required: boolean;
    posts_as_meter_read: boolean;
  }[];
  help: { kind: string; label: string; ref: string | null }[];
}

/** `Work-014`'s tile — *Meter exchange · 7 tasks · 3 parts · 3 readings* — and
 *  the rows behind it. */
export interface TemplatePack {
  code: string;
  name: string;
  tasks: number;
  parts: number;
  readings: number;
  safety: number;
  help: number;
  est_duration_minutes: number;
  bundle: TemplatePackBundle;
  /**
   * Part numbers this pack names that this tenant's register does NOT hold, so
   * step 4 can say what is missing instead of quietly offering one row fewer.
   * An absence nobody can see is what `DEF-CUS-3653` cost.
   */
  unresolved_parts: string[];
}

/** `GET /work/template-packs` — the three PLATFORM packs, resolved against this
 *  tenant's parts register. A pack is prefill and is never stored as a link:
 *  nothing on a template records which pack it came from. */
export async function getTemplatePacks(client: ApiClient = api): Promise<TemplatePack[]> {
  return requireData(await client.get<{ packs: TemplatePack[] }>("/work/template-packs")).packs;
}

/** One line of `Work-004`'s step 6 — a job the build needs, from the utility's
 *  OWN published templates. */
export interface ProposedWorkOrder {
  /** A LINK/stamp target, never the visible value of a field (B14 rule 31). */
  template_id: string;
  template_no: string | null;
  name: string;
  service: { id: string; code: string; name: string } | null;
  scope: string;
  sequence: number;
  job_type: NamedRef | null;
  /** The job that COMPLETES the connection — gas's is the light-up and never
   *  the meter set (`BR-WRK-013`). */
  is_gate: boolean;
  /** What step 9 stamps beside the template, so *copy, never link* has a number
   *  (`BR-WRK-008`). */
  version: number;
  est_duration_minutes: number | null;
  /** `CR-168-BRC10` P3.42 — the Work rule on *a new connection is built* that
   *  proposes this job; step 9 then applies the rule's priority and holder. */
  preselected_by?: { id: string; name: string } | null;
}

export interface ProposedWorkOrders {
  services: string[];
  proposed: ProposedWorkOrder[];
  count: number;
}

/**
 * `GET /connections/proposed-work-orders?services=electric,water` — what the
 * New Connect wizard's step 6 offers (`US-WRK-017`, `BR-WRK-016`).
 *
 * ⚠ **A READ, AND THE STEP WRITES NOTHING** (`BR-MET-112`). Removing a proposed
 * row is wizard state in this browser; what survives travels into step 9's own
 * commit.
 *
 * ⚠ **`customers` CALLS THIS OVER HTTP AND NEVER TOUCHES `work_order_templates`
 * WITH A QUERY.** That is the module boundary in the direction `G78` cannot
 * see, and it is why the wizard imports this function rather than a selector.
 */
export async function getProposedWorkOrders(
  services: readonly string[],
  client: ApiClient = api,
  /** `CR-171-BRC10` P1.19 — a flow with a *Field visit* table (`move_in`,
   *  `move_out`, `transfer`) asks for ITS offer: the jobs done to a live
   *  service. Absent is New Connect step 6's read, unchanged. */
  flow?: string,
): Promise<ProposedWorkOrders> {
  return requireData(
    await client.get<ProposedWorkOrders>("/connections/proposed-work-orders", {
      query: { services: services.join(","), ...(flow === undefined ? {} : { flow }) },
    }),
  );
}


// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-004@67caa1a9 · US-WRK-001@67caa1a9 · US-WRK-003@ab786097 (EP-WRK-01) · apps/work/api.py
// generated: 2026-09-03 by the CR-070 wave A build lane
// amended: 2026-09-04 by the CR-070 wave B build lane — `listAwaitingApproval` (Work-009, BR-WRK-007)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · vitest src/features/work
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ══════════════════════════════════════════════════════════════════════════
// CR-070 WAVE F · THE WORKFORCE (Work-023, Work-024) — 07-endpoints.md §4
// ══════════════════════════════════════════════════════════════════════════

/** A row of `Work-023`'s one table: a person, a crew or a contractor.
 *
 * ⚠ **ONE ROW TYPE FOR ALL THREE, WHICH IS `BR-WRK-028` IN THE TYPE SYSTEM.**
 * *"Whoever the work is offered to, the skill match is the same test."* Two
 * interfaces here would be two shapes for the table to branch on, and a branch
 * is where the two drift. `kind` says which it is, for the cells that differ. */
export interface CrewRow {
  id: string;
  kind: "person" | "crew" | "contractor";
  /** The visible value — B14 rule 31 forbids the id being it. A crew carries
   *  its headcount in the name the way `WS-23` writes it: *Crew B (3)*. */
  name: string;
  /** What a link is built from — `r-patel`, never the uuid. */
  slug: string;
  role_label: string | null;
  skills: HeldSkill[];
  certifications: HeldCertification[];
  /** *07:00–16:00*, or null for a contractor who works by arrangement. */
  shift: string | null;
  status: TechnicianStatus | "crew" | "contractor";
  /** FB-033 — when the status took its value, in the utility's zone. */
  status_since?: string | null;
  unavailable_reason: string | null;
}

export interface HeldSkill {
  skill_id: string;
  code: string;
  name: string;
  /** `not_held` is RENDERED and never stored — it is the absence of a row. */
  proficiency: "trained" | "certified" | "not_held";
  /** Only on the detail screen: which templates this makes them eligible for. */
  eligible_for?: string[];
}

export interface HeldCertification {
  certification_type_id: string;
  /** Null when the type has been removed from Settings — the cell renders a
   *  dash rather than a raw uuid (B14 rule 31). */
  name: string | null;
  expires_on: string | null;
  /** Image 33's PROOF — the certificate's own scan, or null (a dash). Served
   *  on ONE technician's page only (lane SRV-4, `tenancy/0060`); the lists do
   *  not draw it, so it is absent there. `url` is same-origin. */
  proof?: CertificateProof | null;
}

/** `POST /work/technicians/{slug}/certifications/{type_id}/proof` answers this. */
export interface CertificateProof {
  id: string;
  name: string;
  content_type: string;
  bytes: number;
  url: string;
}

export interface CrewList extends Paginated<CrewRow> {
  /** `Work-023`'s footer, over the WHOLE list and not the page. */
  counts: { rows: number; people: number; crews: number; contractors: number };
}

/** `GET /work/crews` — `Work-023`. */
export async function listCrews(
  query: { q?: string; page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<CrewList> {
  return requireData(
    await client.get<CrewList>("/work/crews", {
      query: {
        q: query.q === undefined || query.q === "" ? undefined : query.q,
        page: query.page,
        per: query.per,
      },
    }),
  );
}

/** `Work-024` — one technician. */
export interface TechnicianDetail {
  id: string;
  slug: string;
  name: string;
  role_label: string | null;
  shift: string | null;
  /** FB-033 — `on_break` / `off_duty` are what the technician said on the
   *  phone; `off_today` is End shift's. */
  status: TechnicianStatus;
  /** FB-033 — when the status took its value, in the utility's zone; null = not known. */
  status_since?: string | null;
  /** FB-033 (D4 = B) — off today because End shift still holds it. */
  shift_ended?: boolean;
  unavailable_reason: string | null;
  van: string | null;
  /** CR-168-BRC10 §30 (`work/0038`) — jobs a day this person is expected to
   *  carry; default 6, edited on this page. Advice, never a cap. Optional so
   *  a recording made before 2.519.0 still reads (absent = not said). */
  daily_job_limit?: number;
  /** ⚠ A RECORD, NOT A NAME (`DEF-WRK-9611`). SRV-3 (`2.502.0`) serves
   *  `crew {id, name}` as CR-168 §7.3 says; this read `string` until
   *  `2.502.1`. Draw `crew.name`, never `crew` — printing the object is
   *  `DEF-WRK-9600`'s crash. */
  crew: { id: string; name: string } | null;
  /** Every skill in the tenant's catalogue, held or not — the *Not held* rows
   *  are the point of the panel, not an omission from it. */
  skills: HeldSkill[];
  certifications: HeldCertification[];
  /** P3.46 (SRV-3, `2.502.0`) — read by image 31's meta line and *This
   *  month* (lane CREWS). `on` is the utility's own date, and is what the
   *  Certifications tab measures *expires in N days* against. */
  today?: { jobs: number; on: string };
  this_month?: {
    month: string;
    closed: number;
    on_time: number;
    on_time_of: number;
    first_visit_pct: string | null;
    vs_estimate_pct: string | null;
    vs_estimate_minutes: number | null;
  };
}

/**
 * One person on the crew list, as a NAME and an EMAIL — `BR-AST-533`.
 *
 * PO ruling 2026-09-12, verbatim: ***"a) Let a clerk read the crew list (name
 * + email only)"***. The `id` is the picker's chosen VALUE and is never its
 * label: *"the id still travels on the wire as the chosen value; what the rule
 * forbids is a person reading or typing it"* (B14 rule 31).
 */
export interface CrewMember {
  id: string;
  name: string;
  email: string;
}

/**
 * `GET /work/crew-directory` — **the read a Billing Clerk is allowed to make**
 * (`BR-AST-533`, `DEF-MET-4977`).
 *
 * ⚠ **IT IS NOT `GET /users`, WHICH STAYS `SystemAdminOnly`.** Measured with
 * a real Billing Clerk session on `pine-hill`, 2026-09-12: `GET /users` →
 * **403 `BR-IDN-009`**, this route → **200 with 7 rows**. That pair is the
 * whole shape of the ruling — a NEW narrow read beside the admin one, never a
 * relaxed admin one — and a backend test holds both halves.
 *
 * ⚠ **AND IT IS NOT `GET /work/technicians`, WHICH A CLERK COULD ALREADY
 * READ.** That route answers the supervisor's *add a technician* picker and
 * carries `role_code`, `status` and `has_profile` beside the name — the three
 * things the ruling names as not-served. Displaying only the name would not
 * have been enough: the role would still have crossed the wire into the
 * clerk's browser, and *role-safe* is a statement about what LEAVES the server.
 */
export async function listCrewDirectory(
  client: ApiClient = api,
): Promise<{ results: CrewMember[] }> {
  return requireData(await client.get<{ results: CrewMember[] }>("/work/crew-directory"));
}

/** `GET /work/technicians/{slug}` — `Work-024`. */
export async function getTechnician(
  slug: string,
  client: ApiClient = api,
): Promise<TechnicianDetail> {
  return requireData(await client.get<TechnicianDetail>(`/work/technicians/${slug}`));
}

/** `PUT /work/technicians/{slug}/skills` — the skills wizard's confirm.
 *
 *  A REPLACE: step 2 shows the whole set, so a supervisor who unticks a skill
 *  means it. `not_held` is never sent — it is an absence, and the server
 *  refuses it by name rather than storing a third proficiency. */
export async function setTechnicianSkills(
  slug: string,
  skills: { skill_id: string; proficiency: "trained" | "certified" }[],
  client: ApiClient = api,
): Promise<TechnicianDetail> {
  return requireData(
    await client.put<TechnicianDetail>(`/work/technicians/${slug}/skills`, { skills }),
  );
}

/** `technicians.status` — the office sets the first three; `on_break` and
 *  `off_duty` come from the technician's phone (FB-033). */
export type TechnicianStatus = "on_shift" | "off_today" | "unavailable" | "on_break" | "off_duty";

/** `POST /work/technicians/{slug}/unavailable` — and the way back. */
export async function setTechnicianAvailability(
  slug: string,
  body: { status: "on_shift" | "off_today" | "unavailable"; reason?: string },
  client: ApiClient = api,
): Promise<TechnicianDetail> {
  return requireData(
    await client.post<TechnicianDetail>(`/work/technicians/${slug}/unavailable`, body),
  );
}

/** `PATCH /work/technicians/{slug} {daily_job_limit}` — CR-168-BRC10 §30. */
export async function setTechnicianDailyLimit(
  slug: string,
  dailyJobLimit: number,
  client: ApiClient = api,
): Promise<TechnicianDetail> {
  return requireData(
    await client.patch<TechnicianDetail>(`/work/technicians/${slug}`, { daily_job_limit: dailyJobLimit }),
  );
}

/** One line of `Work-023`'s certification watch. */
export interface WatchEntry {
  technician: string;
  technician_slug: string;
  certification: string | null;
  expires_on: string;
  expired: boolean;
  /** How many published template types NAME this certification. Served always;
   *  RENDERED only where the tenant has switched blocking on. */
  blocked_template_types: number;
}

/** `GET /work/certification-watch`.
 *
 * ⚠ **`policy` AND `blocks` TRAVEL WITH THE ROWS BECAUSE OF `OQ-WRK-1493`,
 * RULED 2026-09-04 — option (c), a per-tenant setting defaulting to *warn*.**
 * The screen may not decide this for itself: a browser that assumed would
 * render *She is blocked from 4 template types* over a utility that has
 * blocking switched off, which is a screen claiming a guarantee the setting
 * has cancelled (hard-won law 1). */
export interface CertificationWatch {
  today: string;
  policy: "warn" | "block";
  blocks: boolean;
  windows: { days: number; entries: WatchEntry[] }[];
}

/** `GET /work/certification-watch` — `Work-023`'s box. */
export async function getCertificationWatch(
  client: ApiClient = api,
): Promise<CertificationWatch> {
  return requireData(await client.get<CertificationWatch>("/work/certification-watch"));
}

// ══════════════════════════════════════════════════════════════════════════
// CR-070 WAVE G · the dispatcher's other reads and its one bulk write
// ══════════════════════════════════════════════════════════════════════════

/**
 * `GET /work/kpis` — the five tiles, plus the footer's denominator.
 *
 * ⚠ **`open_total` IS HERE AND NOT IN THE LIST ENVELOPE.** A11 gives this
 * product ONE list shape (`count`/`next`/`previous`/`results`), and
 * `Work-007`'s footer needs *Showing 8 of 10 open orders* — the 10 is an
 * aggregate over the utility, so it is served beside the other aggregates
 * rather than smuggled into the envelope. `test_us_wrk_004` asserts that
 * envelope's exact key set and caught the first attempt.
 *
 * ⚠ **THE SUB-LINES ARE FIGURES, NOT SENTENCES.** *2 of them urgent* and
 * *WO-4823 · 2 days* come back as `urgent` and `worst`; the screen composes the
 * words from its own catalogue, in the reader's own language (B14 rule 35). A
 * sentence assembled on the server would ship English to every tenant.
 */
export interface WorkKpis {
  open_total: number;
  unassigned: { count: number };
  due_today: { count: number; urgent: number };
  in_field: { count: number };
  awaiting_approval: { count: number };
  overdue: { count: number; worst: { order_no: string | null; days: number } | null };
}

export async function getWorkKpis(client: ApiClient = api): Promise<WorkKpis> {
  return requireData(await client.get<WorkKpis>("/work/kpis"));
}

/** `GET /work/areas` — `US-WRK-011`: the Area chip's options, which ARE
 *  `tenancy.Area` and never a Work-side copy (`BR-WRK-022`). */
export interface WorkArea {
  id: string;
  code: string;
  name: string;
}

export async function listWorkAreas(client: ApiClient = api): Promise<WorkArea[]> {
  const data = await requireData(await client.get<{ results: WorkArea[] }>("/work/areas"));
  return data.results;
}

/**
 * CR-168 §7.3 — one candidate with the ADVICE beside it (ruling 2, PO
 * 2026-09-23; answer 2, 2026-10-04: *the match advises and never blocks; a
 * lapsed certificate only warns*). Nothing here is `eligible: false` any more:
 * every name is choosable and the advice says why it fits or does not.
 */
export interface CandidateAdvice {
  skill: { name: string } | null;
  has_skill: boolean;
  area_match: boolean;
  off_that_day: boolean;
  /** `null` when the server did not say — never drawn as zero. */
  jobs_that_day: number | null;
  /** CR-168-BRC10 §30 — the person's daily job limit (null for a crew) and
   *  whether `jobs_that_day` exceeds it. Advice only. OPTIONAL because the
   *  recordings made before 2.519.0 do not carry them (absent = not said);
   *  `candidateOf` always fills both. */
  daily_job_limit?: number | null;
  over_daily_limit?: boolean;
  certifications_lapsed: { name: string | null; expired_on: string }[];
  /** FB-033 (D1/D2) — the technician's own Off duty / On break from the
   *  phone and since when, whatever day is asked about; null otherwise.
   *  Advice only. Optional: recordings made before it do not carry it. */
  availability?: { status: "off_duty" | "on_break"; since: string | null } | null;
}

export interface Candidate {
  kind: string;
  id: string;
  name: string;
  advice: CandidateAdvice;
  best_fit: boolean;
  /** A crew's or a contractor's head-count (image 12's *2 people*); absent
   *  on a person. Counted by the server, never typed. */
  members?: number;
}

export interface CandidatePage {
  results: Candidate[];
  count: number;
  next: string | null;
  previous: string | null;
}

/** One page of §7.3's row, defensively read: a missing field is "not said". */
function candidateOf(raw: Record<string, unknown>): Candidate {
  const advice = (raw.advice ?? {}) as Partial<CandidateAdvice>;
  return {
    kind: String(raw.kind ?? "person"),
    id: String(raw.id ?? ""),
    name: String(raw.name ?? ""),
    best_fit: raw.best_fit === true,
    ...(typeof raw.members === "number" ? { members: raw.members } : {}),
    advice: {
      skill: advice.skill ?? null,
      has_skill: advice.has_skill !== false,
      area_match: advice.area_match === true,
      off_that_day: advice.off_that_day === true,
      jobs_that_day: typeof advice.jobs_that_day === "number" ? advice.jobs_that_day : null,
      daily_job_limit: typeof advice.daily_job_limit === "number" ? advice.daily_job_limit : null,
      over_daily_limit: advice.over_daily_limit === true,
      certifications_lapsed: Array.isArray(advice.certifications_lapsed) ? advice.certifications_lapsed : [],
    },
  };
}

/**
 * §7.3's paged envelope, read into the shape the screen draws.
 *
 * ⚠ **ONE SHAPE ONLY (lane ASSIGN, 2026-10-04, after SRV-2's `2.500.0`).** Until
 * then this also read the old `{skill, policy, candidates[]}` with `eligible`
 * and `lapsed`; the server now serves the envelope (recorded in
 * `__fixtures__/work-order-candidates.recorded.json`) and keeps the old keys
 * one round only, so nothing here reads them — SRV-3 may remove them.
 */
export function normaliseCandidates(raw: unknown): CandidatePage {
  const body = (raw ?? {}) as Record<string, unknown>;
  const results = (Array.isArray(body.results) ? (body.results as Record<string, unknown>[]) : []).map(candidateOf);
  return {
    results,
    count: typeof body.count === "number" ? body.count : results.length,
    next: typeof body.next === "string" ? body.next : null,
    previous: typeof body.previous === "string" ? body.previous : null,
  };
}

/** `GET /work-orders/{id}/candidates?q=&page=&per=` — paged and uncapped
 *  (NFR-3, NFR-5): a picker that needs everybody pages and searches. */
export async function listCandidatesPage(
  orderId: string,
  params: { q?: string; page?: number; per?: number },
  client: ApiClient = api,
): Promise<CandidatePage> {
  const raw = await requireData(
    await client.get<unknown>(`/work-orders/${orderId}/candidates`, {
      query: { q: params.q ? params.q : undefined, page: params.page, per: params.per },
    }),
  );
  return normaliseCandidates(raw);
}

/** One entry of `POST /work-orders/bulk`'s answer — **per order, never a
 *  boolean** (`07-endpoints.md` row 67). `reason` is a catalogue KEY, so the
 *  screen says why in the reader's own language. */
export interface BulkResult {
  id: string;
  ok: boolean;
  reason?: string;
  order_no?: string | null;
}

export interface BulkOutcome {
  act: BulkAct;
  results: BulkResult[];
  done: number;
  failed: number;
}

/** `BR-WRK-027` — Assign, Reschedule, Change priority. Three, and no fourth. */
export type BulkAct = "assign" | "reschedule" | "priority";

export interface BulkRequest {
  act: BulkAct;
  ids: string[];
  technician_id?: string;
  crew_id?: string;
  scheduled_for?: string;
  window_start?: string;
  window_end?: string;
  priority_id?: string;
  /** P4.4 — why the ticked orders that already have somebody move off them;
   *  carried onto each order's two history rows (SRV-2). */
  reason?: string;
}

export async function bulkWorkOrders(
  body: BulkRequest,
  client: ApiClient = api,
): Promise<BulkOutcome> {
  return requireData(await client.post<BulkOutcome>("/work-orders/bulk", body));
}


// ══════════════════════════════════════════════════════════════════════════
// CR-070 WAVE H · THE ORDER'S OWN COPIES — `07-endpoints.md` §6 #71–#73
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **EVERY TYPE BELOW DESCRIBES THE ORDER'S COPY, NEVER THE TEMPLATE'S ROWS**
// (`BR-WRK-008`). There is deliberately no `template_task_id` anywhere in this
// file, because there is no such column: the only reference the order keeps is
// `template_id` + `template_version`, which say where its checklist came from
// without letting it move when the template does.

/** One safety line the technician has to tick before the task list opens. */
export interface OrderSafetyRow {
  id: string;
  seq: number;
  text: string;
  is_mandatory: boolean;
  ticked_at: string | null;
  ticked_by: string | null;
}

/** One step of the job, as it read on the day the order was raised. */
export interface OrderTaskRow {
  id: string;
  seq: number;
  title: string;
  est_minutes: number;
  photo_required: boolean;
  is_mandatory: boolean;
  ticked_at: string | null;
  ticked_by: string | null;
  /** The FILE. `photo_required` above is the RULE — two fields, because *asked
   *  for and not taken* must be tellable from *never asked for*. */
  photo_attachment_id: string | null;
}

export interface OrderReadingRow {
  id: string;
  seq: number;
  prompt: string;
  /** Hard rule 3 — a reading never travels without its unit. */
  unit_of_measure: string;
  min_value: string | null;
  max_value: string | null;
  required: boolean;
  photo_required: boolean;
  posts_as_meter_read: boolean;
  value: string | null;
  captured_at: string | null;
  /** The `Thumbnail` cell arrives in wave K — a dash until then. */
  photo_attachment_id: string | null;
  in_range: boolean | null;
}

export interface OrderMaterialRow {
  id: string;
  part_id: string;
  /** B14 rule 31 — `MTR-W58` is what a person reads; `part_id` is for calls. */
  part_no: string;
  part_name: string;
  planned_qty: string;
  used_qty: string | null;
  unit_of_measure: string;
  unplanned: boolean;
}

export interface OrderHelpRow {
  id: string;
  seq: number;
  /** `link` since `2.504.0` (ruling 6): its https address is `ref`. */
  kind: "document" | "phone" | "link" | "note";
  label: string;
  ref: string | null;
}

export interface OrderDetailsRow {
  access_notes: string | null;
  hazards: string | null;
  gate_code: string | null;
  show_account_summary: boolean;
  show_asset_card: boolean;
  show_access_notes: boolean;
  show_appointment: boolean;
  /** FB-023 F4 — Balance & payments. */
  show_balance_payments?: boolean;
  /** FB-028 — the Reconnect limit, 4 places; null = none set. */
  reconnect_limit?: string | null;
}

/**
 * ⚠ **THE LOCK IS EVALUATED ONCE, ON THE SERVER, AND SERVED.** `BR-WRK-037`
 * binds the staff screen and the phone alike, so neither computes it: two
 * surfaces with their own copy of the condition are two surfaces that will
 * eventually disagree about whether a job may proceed.
 *
 * `remaining > 0` is the whole rule — *two of three ticked is locked, not
 * two-thirds unlocked* — and there is no threshold in it anywhere.
 */
export interface OrderSafetyLock {
  locked: boolean;
  remaining: number;
  /** The row a screen names beside the refusal. */
  first_outstanding: string | null;
  ticked: number;
  total: number;
  mandatory_total: number;
}

export interface OrderChecklist {
  order_id: string;
  order_no: string | null;
  template_id: string | null;
  template_version: number | null;
  safety: OrderSafetyRow[];
  safety_lock: OrderSafetyLock;
  tasks: OrderTaskRow[];
  /** ⚠ **COUNTED SERVER-SIDE, AND SERVED AS TWO NUMBERS.** *3 of 7* assembled
   *  in JavaScript is a plural nobody can translate — the eleven catalogues
   *  would each need a rule the data never reaches. The screen interpolates
   *  two numbers into ONE catalogue string. */
  tasks_total: number;
  tasks_ticked: number;
  tasks_est_minutes: number;
  readings: OrderReadingRow[];
  materials: OrderMaterialRow[];
  help: OrderHelpRow[];
  details: OrderDetailsRow | null;
}

/** `GET /work-orders/{id}` — the dispatch row, plus the two axes the LIST
 *  does not draw. Wave G built the route (`dispatch.order_row`) deliberately
 *  ahead of this screen, because a route with no screen and a screen with no
 *  route are the two halves of hard-won law 2. */
/**
 * `GET /work/raise-options` (`DEF-CUS-6363`) — the utility's ACTIVE job types
 * and priorities, for a flow's *+ Add work order* row. A Work read readable by
 * every role that reads a work order; the Settings lookups over the same rows
 * answer a Billing Clerk 403 (see `from_flows.raise_options`).
 */
export interface RaiseOptionType {
  id: string;
  code: string;
  name: string;
  parent_name: string | null;
  default_priority_id: string | null;
}

export interface RaiseOptionPriority {
  id: string;
  code: string;
  name: string;
  sla_hours: number;
}

export interface RaiseOptions {
  types: RaiseOptionType[];
  priorities: RaiseOptionPriority[];
  /** `DEF-WRK-9626` — the job type each flow's new row opens on, by flow kind. */
  flow_types?: Record<string, string>;
  /**
   * `CR-168-BRC10` P3.42 — the rows an ENABLED Work rule on a screen moment
   * puts in that moment's *Field visit* table before the clerk touches it, by
   * flow kind (`move_in` · `move_out` · `transfer`). `holder` is
   * `technician:<id>`, `crew:<id>` or `""`. Nothing is raised until the save.
   */
  preselected?: Record<string, RaiseOptionPreselected[]>;
}

export interface RaiseOptionPreselected {
  rule: { id: string; name: string };
  type_id: string;
  priority_id: string;
  holder: string;
}

export async function getRaiseOptions(client: ApiClient = api): Promise<RaiseOptions> {
  return requireData(await client.get<RaiseOptions>("/work/raise-options"));
}

export async function getWorkOrder(
  orderId: string,
  client: ApiClient = api,
): Promise<
  WorkOrderDispatchRow & {
    state: WorkOrderState;
    est_duration_minutes: number | null;
    /** CR-161-BRC10 W4 — the utility's own answers (`WORK_DETAIL`). */
    custom_data?: Record<string, unknown>;
  }
> {
  return requireData(
    await client.get<WorkOrderDispatchRow & { state: WorkOrderState; est_duration_minutes: number | null }>(
      `/work-orders/${orderId}`,
    ),
  );
}

/**
 * `GET /work-orders/by-number/{order_no}` — **the same row, found by the
 * reference a person can read**, and the whole of `DEF-WRK-4518`'s new surface.
 *
 * ⚠ **NOTHING COULD ANSWER THIS QUESTION UNTIL 2026-09-07, AND THE ROUTE
 * PARAMETER HAD BEEN NAMED AFTER IT SINCE WAVE H.** `Work-008` opens at
 * `/work/orders/:orderNo`, every producer of that address passes a UUID, and
 * every one of the screen's fourteen calls is routed `<uuid:order_id>`. So an
 * address carrying the number a clerk was actually looking at — the Orders
 * table's first column — 404'd fourteen times and the screen drew a dash for
 * each, with `tsc` green because an order number IS a string.
 *
 * ⚠ **THE SCREEN CALLS THIS AT MOST ONCE, AND ONLY WHEN THE SEGMENT IS NOT A
 * UUID.** Resolving on every one of the fourteen calls would be fourteen
 * lookups for one page; `OrderDetailPage` resolves once and uses `row.id` for
 * the other thirteen.
 */
export async function getWorkOrderByNumber(
  orderNo: string,
  client: ApiClient = api,
): Promise<
  WorkOrderDispatchRow & {
    state: WorkOrderState;
    est_duration_minutes: number | null;
    /** CR-161-BRC10 W4 — the utility's own answers (`WORK_DETAIL`). */
    custom_data?: Record<string, unknown>;
  }
> {
  return requireData(
    await client.get<WorkOrderDispatchRow & { state: WorkOrderState; est_duration_minutes: number | null }>(
      `/work-orders/by-number/${encodeURIComponent(orderNo)}`,
    ),
  );
}

/** `POST /work-orders` — **the ONE raise every door uses** (`07-endpoints.md`
 *  §1 row 14). The three-step wizard is a THIRD door onto it, not a second
 *  write: `BR-WRK-008`'s copy runs inside metering's `create_work_order`, so
 *  the wizard gets the order's checklist for free and cannot forget to.
 *
 *  `source` is stamped `dispatcher` — `BR-WRK-024`, and it is what `Work-007`
 *  draws as RAISED BY. */
export async function raiseWorkOrderFromDispatcher(
  body: {
    premises_id?: string | null;
    account_id?: string | null;
    asset_id?: string | null;
    type: string;
    /**
     * The job type's CATALOGUE ROW, when the caller has it.
     *
     * ⚠ **THIS IS WHAT MAKES THE PROMISE EXIST, AND IT WAS UNDECLARED UNTIL
     * `CR-094-BRC01` WAVE G.** `metering.connections._resolve_order_type` takes
     * `type_id` exactly, or matches the typed `type` against a code or a name
     * *"case-insensitively and in full"*, and returns `None` otherwise — and
     * with no type resolved `_resolve_priority` has no default to read, so
     * `BR-WRK-018` stamps **no `due_at` at all**. A door that knows the id and
     * can only send words is one rename away from raising jobs with no
     * response time, silently. The server has accepted this field since wave
     * G of `CR-070`; only this signature did not offer it.
     */
    type_id?: string | null;
    template_id?: string | null;
    priority_id?: string | null;
    due_at?: string | null;
    area_id?: string | null;
    /** CR-161-BRC10 W4 — the utility's own answers, sent ONLY by the New work
     *  order screen and always (`{}` included): the server reads the key as
     *  "typed on New work order", so a required field binds there alone. */
    custom_data?: Record<string, unknown>;
  },
  client: ApiClient = api,
): Promise<{ id: string; order_no: string | null; dispatch_state: string }> {
  return requireData(
    await client.post<{ id: string; order_no: string | null; dispatch_state: string }>(
      "/work-orders",
      { ...body, source: "dispatcher" },
    ),
  );
}

/** `GET /work-orders/{id}/checklist` (#71) — the six copy collections. */
export async function getOrderChecklist(
  orderId: string,
  client: ApiClient = api,
): Promise<OrderChecklist> {
  return requireData(await client.get<OrderChecklist>(`/work-orders/${orderId}/checklist`));
}

export interface SafetyTickResult {
  id: string;
  ticked_at: string;
  safety_lock: OrderSafetyLock;
}

/** `POST /work-orders/{id}/safety/{sid}/tick` (#72) — the act that LIFTS the
 *  lock, so it is never refused by it. */
export async function tickOrderSafety(
  orderId: string,
  safetyId: string,
  client: ApiClient = api,
): Promise<SafetyTickResult> {
  return requireData(
    await client.post<SafetyTickResult>(`/work-orders/${orderId}/safety/${safetyId}/tick`, {}),
  );
}

export interface TaskTickResult {
  id: string;
  ticked_at: string;
  tasks_ticked: number;
  tasks_total: number;
}

/** `POST /work-orders/{id}/tasks/{tid}/tick` (#73) — **the server refuses this
 *  while the safety lock holds**, whatever the screen has drawn. */
export async function tickOrderTask(
  orderId: string,
  taskId: string,
  client: ApiClient = api,
): Promise<TaskTickResult> {
  return requireData(
    await client.post<TaskTickResult>(`/work-orders/${orderId}/tasks/${taskId}/tick`, {}),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// CR-070 WAVE L · `Work-008`'s FOUR ACTIONS, WIRED
//
// ⚠ **THESE FOUR WERE DRAWN AND DEAD FROM WAVE H UNTIL 2026-09-05, AND WAVE H
// SAID SO IN ITS OWN STAMP.** Four live-looking buttons over a routed, tested
// screen is `DEF-CWP-3925` exactly — hard-won law 2's MIRROR, the half `G13`
// cannot see, because `G13` asks whether a prop is passed and nothing asks
// whether a REFUSAL is still true.
//
// **All four endpoints already existed when the buttons were drawn.**
// `field-result` since CR-038, `hold` and `cancel` since wave G, `assignments`
// since wave G. What was missing was four client functions and four handlers —
// which is why `ORDER_DETAIL_HELD_CONTROLS` names the ENDPOINT that releases
// each rather than a wave, and why `OrderDetailPage.test.tsx` asserts each
// button reaches its own path with its own method and body.
// ══════════════════════════════════════════════════════════════════════════

export interface FieldResultAccepted {
  id: string;
  state: string;
  awaiting_review: boolean;
  br_ref: string;
}

/** `POST /work-orders/{id}/field-result` — *Mark complete* (`BR-MET-110`).
 *
 *  ⚠ **THIS SENDS THE JOB FOR APPROVAL AND ACTIVATES NOTHING.** `accepted_by`
 *  stays NULL — and that NULL is the review queue. The supply is switched on by
 *  a person pressing Accept on `Work-009`, never by this call, and the
 *  `ConsequenceBox` above the button says so in a clerk's words.
 *
 *  The SERVER refuses this while the safety lock holds (`BR-WRK-037`), whatever
 *  the screen has drawn — the disabled state here is a courtesy.
 */
export async function markOrderComplete(
  orderId: string,
  body: { outcome?: string; external_ref?: string } = {},
  client: ApiClient = api,
): Promise<FieldResultAccepted> {
  return requireData(
    await client.post<FieldResultAccepted>(`/work-orders/${orderId}/field-result`, body),
  );
}

export interface DispatchStateResult {
  id: string;
  dispatch_state: string;
}

/** `POST /work-orders/{id}/hold` — off the run, **nothing deleted**. */
export async function holdWorkOrder(
  orderId: string,
  client: ApiClient = api,
): Promise<DispatchStateResult> {
  return requireData(await client.post<DispatchStateResult>(`/work-orders/${orderId}/hold`, {}));
}

/** `POST /work-orders/{id}/cancel` — danger tier, and **nothing deleted**: a
 *  cancelled order keeps its number, its history and its audit trail. */
export async function cancelWorkOrder(
  orderId: string,
  client: ApiClient = api,
): Promise<DispatchStateResult> {
  return requireData(await client.post<DispatchStateResult>(`/work-orders/${orderId}/cancel`, {}));
}

// ⚠ **THERE IS NO `reassignWorkOrder` HERE, AND ITS ABSENCE IS DELIBERATE.**
// A first draft of this block exported one *"for the day a one-click reassign is
// drawn"* — which is hard-won law 1 exactly: **a comment claiming a plan is not
// a plan**, and an exported client function nothing calls is dead code that
// reads as a wired feature. *Reassign…* on `Work-008` opens `Work-021`, the
// screen that already owns the picker, the candidate list and `BR-WRK-026`'s
// eligibility rules, and posts `POST /work-orders/{id}/assignments` from there.
// One caller, one place for the rules.

// ══════════════════════════════════════════════════════════════════════════
// CR-070 WAVE I · CHANGING COURSE — the edit form, the Save, the map
// ══════════════════════════════════════════════════════════════════════════

/** What `Work-021` opens with — the RAW value of every field it edits.
 *
 *  ⚠ **NOT the dispatch row.** The list needs an area's NAME to draw a cell;
 *  the form needs its ID to select an option. Serving the display row into a
 *  form makes a select that cannot post back what it shows, and it fails
 *  SILENTLY with every check green (`DEF-CUS-3653`'s shape).
 */
/** A promised visit in the utility's own zone — what the server reads back. */
export interface OrderAppointment {
  date: string;
  start: string | null;
  end: string | null;
  time_zone: string;
}

export interface OrderEditForm {
  id: string;
  order_no: string | null;
  type: string | null;
  dispatch_state: string;
  state: string;
  priority_id: string | null;
  due_at: string | null;
  window_start: string | null;
  window_end: string | null;
  area_id: string | null;
  technician_notes: string | null;
  /** CR-161-BRC10 W4 — the utility's own answers the form opens with. */
  custom_data?: Record<string, unknown>;
  technician: WorkOrderHolder | null;
  /** `DEF-WRK-9688` — the booked day and clock times in the UTILITY's zone,
   *  `{date, start, end, time_zone}` (`edit._appointment`). The form opens on
   *  THESE, never on `window_start` read in the browser's zone, so a Central
   *  08:00–12:00 opens as *Morning* on a laptop in any zone. */
  appointment?: OrderAppointment | null;
  /** The id the `<select>` posts back — the candidate list is keyed by it,
   *  while `technician` above carries the display shape a CELL needs. Two
   *  shapes of one fact, because a select whose value matches no option opens
   *  showing *Unassigned* over an order that has somebody on it.
   *
   *  ⚠ OPTIONAL BECAUSE THE SERVER NEVER SENDS IT (`DEF-WRK-9605`). The real
   *  `GET /work-orders/{id}/edit` serves `technician {id, kind, name, slug}`,
   *  as CR-168 §7.3 says, and `holderIdOf` falls back to `technician.id`. It
   *  read REQUIRED until 2.502.1, so every edit-page fixture typed it and the
   *  fallback — the only path production takes — had no test.
   *  `recordedServerShapes.typecheck.ts` holds the server's own answer to it. */
  technician_id?: string | null;
  premise: { id: string; premise_no: string | null; address: string | null } | null;
  template_id: string | null;
  /** `BR-WRK-018` — a Complete order refuses a priority change. Served so the
   *  screen can DISABLE the control rather than answer a 400 into a dialog
   *  (`BR-SHL-025`: disabled WITH its reason). */
  priority_locked: boolean;
}

/** Only the fields that MOVED are sent. A browser posts the whole form, and
 *  auditing what was POSTED would write a row per field for a dispatcher who
 *  changed one — and, far worse, would tell a customer their visit moved to the
 *  time it already was (`US-WRK-031` TC-6). */
export interface OrderEditPatch {
  dispatch_state?: string;
  priority_id?: string | null;
  due_at?: string | null;
  window_start?: string | null;
  window_end?: string | null;
  area_id?: string | null;
  technician_notes?: string | null;
  technician_id?: string | null;
  crew_id?: string | null;
  /** CR-168 P4.4 (image 13's *Why it moves*) — sent only when the job moves
   *  OFF somebody to somebody else: the reason both history rows carry, in the
   *  dispatcher's own words. The server refuses a reassign without it
   *  (`work.dispatch.reason_required`). */
  reason?: string;
  /** CR-161-BRC10 W4 — only the answers that changed; a cleared one is
   *  `null`. Merged into the stored answers by the server (`WORK_EDIT`). */
  custom_data?: Record<string, unknown>;
}

/** What Save actually did — the three things the Change effects box promised.
 *
 *  `reschedule_notice` is `null` when the date and the window did not move, and
 *  carries `queued: false` with a reason when there was nobody to tell. It
 *  NEVER reports a message it did not queue (hard-won law 1): a tick over a
 *  missing row is worse than a visible failure, because the dispatcher stops
 *  watching for it. */
export interface OrderEditResult {
  order_no: string | null;
  changed: string[];
  audit_rows: number;
  reschedule_notice:
    | { queued: true; source_type: string; window_now: string | null }
    | { queued: false; reason: string; source_type: string }
    | null;
}

export async function getOrderEditForm(
  orderId: string,
  client: ApiClient = api,
): Promise<OrderEditForm> {
  return requireData(await client.get<OrderEditForm>(`/work-orders/${orderId}/edit`));
}

export async function saveOrderEdit(
  orderId: string,
  patch: OrderEditPatch,
  client: ApiClient = api,
): Promise<OrderEditResult> {
  return requireData(await client.patch<OrderEditResult>(`/work-orders/${orderId}`, patch));
}

/** One pin — `US-WRK-029`, `WM-23`.
 *
 *  `hollow` is a fact about the ASSIGNMENT and not about either the state or
 *  the priority, which is why it is its own field: *nobody is going* is the one
 *  a dispatcher scans for. */
export interface MapPin {
  id: string;
  order_no: string | null;
  type: string | null;
  priority: WorkOrderPriority | null;
  technician: WorkOrderHolder | null;
  dispatch_state: string;
  due_at: string | null;
  lat: number;
  lng: number;
  address: string | null;
  hollow: boolean;
}

/** An order that has NO coordinate — listed, never silently dropped
 *  (`US-WRK-029` TC-3). `reason` distinguishes the two cases that differ: a
 *  premises nobody geocoded, which a dispatcher can fix, and a network job with
 *  no premises at all, which nobody can. */
export interface UnplacedOrder {
  id: string;
  order_no: string | null;
  type: string | null;
  priority: WorkOrderPriority | null;
  technician: WorkOrderHolder | null;
  dispatch_state: string;
  due_at: string | null;
  address: string | null;
  reason: "premises_not_geocoded" | "no_premises";
}

export interface WorkOrderMap {
  pins: MapPin[];
  unplaced: UnplacedOrder[];
  total: number;
}

export async function getWorkOrderMap(
  params: Record<string, string> = {},
  client: ApiClient = api,
): Promise<WorkOrderMap> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  const suffix = query.toString();
  return requireData(
    await client.get<WorkOrderMap>(`/work-orders/map${suffix ? `?${suffix}` : ""}`),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// CR-070 wave N · what a job cost — `US-WRK-050`, `051`, `054`
//
// ⚠ EVERY MONEY FIELD BELOW IS A DECIMAL **STRING**, NEVER A NUMBER. Hard rule
// 2 stores to four places and displays two, and the moment a `"48.5000"`
// becomes a JavaScript number it is a float — the exact thing the rule forbids.
// `MoneyCell` is the one display boundary that trims it.
// ══════════════════════════════════════════════════════════════════════════

/** One row of `Work-030` — a rate for a ROLE, never for a person (`WM-45`). */
export interface LabourRateRow {
  id: string;
  /** `field_technician`, `contractor:<crew_id>` — a code, never rendered raw
   *  (B14 rule 31: no database id is the visible value of a field). */
  role: string;
  /** The words a supervisor typed — *Field technician*, *Apex Utility Svc*. */
  role_label: string;
  /** Four decimals. `Work-030` is the ONE screen that SHOWS four, because the
   *  stored value is what is being edited; the report shows `48.50`. */
  hourly: string;
  /** ⚠ **NULL IS A DASH, NOT A ZERO.** A contractor carries one rate and a
   *  dash — *"an agency invoices its own overtime"* (`BR-WRK-020`). Rendering
   *  a `0.0000` here would state that their overtime is free. */
  overtime_hourly: string | null;
  overtime_after_hours: string | null;
  effective_from: string;
  superseded_on: string | null;
  current: boolean;
}

/**
 * ⚠ **THIS TYPE SAID `{rows, page, per, total, last_page}` AND
 * `Settings → Labour rates` DREW AN EMPTY TABLE OVER FOUR SERVED RATES FOR AS
 * LONG AS THE SCREEN HAS EXISTED** (`DEF-WRK-4119`). Those five keys are
 * exactly what `selectors.labour_rates_page` returns — the right file, one
 * layer too low. `api.labour_rates` wraps it in `_envelope()` first, so the
 * wire carries `{count, next, previous, results}` and `query.data?.rows` was
 * `undefined` on every render.
 *
 * ⚠ **IT IS THE SAME DEFECT `DEF-WRK-4098` FIXED ON THE RULES SCREEN, FOUND
 * SEPARATELY, ON THE SAME DAY, BY A DIFFERENT LANE — WHICH IS THE ARGUMENT FOR
 * NOT FIXING IT ONE SCREEN AT A TIME.** That fix corrected the rules type to
 * the envelope; correct, and the ELEVENTH hand-written copy of the same four
 * keys in this file, leaving the twelfth free to be wrong again. There is one
 * declaration now (`@/api/paginated`) and no screen describes a paged reply.
 */
export async function listLabourRates(
  query: { page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<PagedRows<LabourRateRow>> {
  return readListPage<LabourRateRow>(
    "/work/labour-rates",
    { page: query.page, per: query.per },
    client,
  );
}

/** One movement of stores — `Work-025`'s Issue log.
 *
 *  ⚠ **THERE IS NO `on_hand`, NO `reorder_at`, NO `location` AND NO RUNNING
 *  BALANCE ON THIS TYPE, AND THAT IS ASSERTED BY NAME.** `OQ-WRK-1490` closed
 *  on 2026-09-04 to option (a): the register and the log, and no stock at all.
 *  A running balance IS an on-hand figure with extra steps. */
export interface PartIssueRow {
  id: string;
  part_id: string;
  part_no: string;
  part_name: string;
  /** Signed and four decimals: `"-1.0000"` taken, `"4.0000"` returned. */
  qty: string;
  unit_of_measure: string;
  issued_to: string;
  purpose: string;
  /** Plain text by design — *"this register does not know what a work order
   *  is"* (`WM-22`). Reconciled with the order by the number a human reads. */
  order_ref: string;
  at: string;
  /** Derived from the SIGN, which IS the fact — a second column could disagree
   *  with it. */
  direction: "issue" | "return";
}

/**
 * ⚠ **THE SAME WRONG SHAPE AGAIN, AND IT HAD NO SCREEN YET — WHICH IS THE ONLY
 * REASON NOBODY SAW IT** (`DEF-WRK-4119`). `Work-025`'s Movements tab would
 * have opened blank on its first day. Fixed here rather than left for that lane
 * to trip over: a wrapper nothing calls is exactly where a wrong shape waits.
 */
export async function listPartIssues(
  query: { q?: string; part_id?: string; page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<PagedRows<PartIssueRow>> {
  return readListPage<PartIssueRow>(
    "/work/parts/issues",
    {
      q: query.q === undefined || query.q === "" ? undefined : query.q,
      part_id: query.part_id,
      page: query.page,
      per: query.per,
    },
    client,
  );
}

/** `Work-027` — did the field keep its promises, and what did it cost.
 *
 *  ⚠ **THERE IS NO LINK, ROUTE OR ACCOUNT CODE ON THIS TYPE.** r10 says the
 *  total *"feeds the O&M / labour line in Finance → Cost & Margin"*; that
 *  arrow is **not built** (`BR-WRK-004`; `OQ-WRK-1491` closed 2026-09-04 to
 *  option (a)). Payroll already posts the hour, and posting field labour
 *  beside it would count the same hour twice. `G111` fails the build if one
 *  appears. */
export interface PerformanceRow {
  job_type: string;
  volume: number;
  /** CR-168 P5.1 — the jobs this row measured against a promise, and the ones
   *  that kept it. The headline tile is these columns' sum (`DEF-WRK-9586`). */
  sla_measured: number;
  sla_met: number;
  /** One decimal, as `Work-027` draws it (`94.2`). A string, so the server
   *  decides the precision and the screen never re-rounds it. */
  sla_met_pct: string;
  first_time_fix_pct: string;
  cost_per_job: string;
  total_cost: string;
}

/** `GET /work/performance` — the house list envelope (paged in SQL, CR-168
 *  P5.6) plus the tiles and the total, which are aggregates over the WHOLE
 *  period and never over the page in hand. */
export interface PerformancePayload extends Paginated<PerformanceRow> {
  period: string;
  tiles: {
    sla_met_pct: string;
    sla_measured: number;
    sla_met: number;
    first_time_fix_pct: string;
    cost_per_job: string;
    volume: number;
  };
  total: { volume: number; total_cost: string };
}

/** A column key → the server's sort word (`selectors.PERFORMANCE_SORTS`). A
 *  column not named here is not sortable on the server and is not offered. */
export const PERFORMANCE_SORT_PARAM: Readonly<Record<string, string>> = {
  job_type: "job_type",
  volume: "volume",
  sla_met_pct: "sla_met",
  first_time_fix_pct: "first_time_fix",
  total_cost: "total_cost",
};

export async function fetchPerformance(
  query: { period?: string; page?: number; per?: number; sort?: string | null; dir?: string | null } = {},
  client: ApiClient = api,
): Promise<PerformancePayload> {
  const sort = query.sort ? PERFORMANCE_SORT_PARAM[query.sort] : undefined;
  return requireData(
    await client.get<PerformancePayload>("/work/performance", {
      query: {
        period: query.period,
        page: query.page,
        per: query.per,
        sort,
        dir: sort === undefined ? undefined : (query.dir ?? undefined),
      },
    }),
  );
}

/* ── CR-070 wave M · rules, and the Assets door ─────────────────────────────
 *
 * `Work-026` (the rule list + the five-step builder) and `Work-028` (the
 * Assets door). Routes #82–#87 plus the two asset-shaped reads Work serves.
 */

/** One rule as `Work-026` draws it.
 *
 *  ⚠ **`id` IS AN ADDRESS, NOT A VISIBLE VALUE** (B14 rule 31). Every column
 *  the table RENDERS — rule, source module, trigger, template raised, priority,
 *  this month, enabled — is a name, a word or a count. */
export interface WorkRuleRow {
  id: string;
  name: string;
  source_module: string;
  trigger_kind: string;
  params: Record<string, unknown>;
  template: { id: string; name: string | null };
  priority: { id: string; name: string } | null;
  assignment: Record<string, unknown>;
  /** §7.3's Notify rows, served as a LIST since `2.512.0` (lane SRV-4); a
   *  wave M rule's stored object reads as `[]`. Recorded: `work.rules.json`. */
  notifications: { event_key: string; when: string | null; who: string | null }[];
  escalation: Record<string, unknown>;
  enabled: boolean;
  /** Orders this rule raised since the 1st. Counted from the sweep's own
   *  memory, so a utility that purged last week's closed jobs still sees a
   *  truthful figure. */
  this_month: number;
}

/**
 * `GET /work/rules` — **`Work-026` RENDERED ZERO RULES FOR EVERY TENANT**
 * (`DEF-WRK-4098`, and `DEF-WRK-4119` for the two screens it did not reach).
 *
 * The type here said `{rows, page, per, total, pages}` — the shape of
 * `rules.rules_page()` INSIDE the backend — but `apps/work/api._envelope` wraps
 * that service result before it leaves the process and serves
 * `{count, next, previous, results}`, exactly as it does for orders, templates
 * and parts. **A generic on `client.get<T>()` is an ASSERTION, not a check:**
 * nothing at runtime compares the JSON to this type, so `data.rows` was
 * `undefined`, the page passed `[]` to `DataTable`, `totalRows` fell to
 * `null` → `0`, and the screen drew its zero-results state over seven perfectly
 * good rules. `tsc` cannot see it and neither can any test that does not make a
 * real request.
 *
 * ⚠ **THAT DIAGNOSIS IS `DEF-WRK-4098`'s, KEPT VERBATIM BECAUSE IT IS RIGHT.
 * WHAT CHANGED IS THE SCOPE OF THE CURE.** The first fix corrected this one
 * interface to the envelope — correct, and the ELEVENTH hand-written copy of
 * those four keys in this file. Two other screens had the identical bug at the
 * same moment (`Settings → Labour rates`, and the asset detail's Maintenance
 * history), a fourth wrapper was carrying it with no screen yet, and the twelfth
 * copy would have been free to be wrong again. So the envelope is declared ONCE
 * now (`@/api/paginated`), `readListPage` is its only reader, and a screen
 * receives `{rows, total}` and never sees the wire shape at all.
 *
 * The helper also ASSERTS the envelope at runtime, which is the half a type
 * cannot do: if this reply ever changes again, the console names the path and
 * the keys that arrived instead of drawing an empty grid.
 */
export async function listWorkRules(
  query: { page?: number; per?: number } = {},
  client: ApiClient = api,
): Promise<PagedRows<WorkRuleRow>> {
  return readListPage<WorkRuleRow>(
    "/work/rules",
    { page: query.page, per: query.per },
    client,
  );
}

export interface NewWorkRule {
  name: string;
  source_module: string;
  trigger_kind: string;
  template_id: string;
  priority_id?: string | null;
  params?: Record<string, unknown>;
  assignment?: Record<string, unknown>;
  notifications?: Record<string, unknown>;
  escalation?: Record<string, unknown>;
  enabled?: boolean;
}

/** The builder's step 5, *Review & activate*. */
export async function createWorkRule(
  body: NewWorkRule,
  client: ApiClient = api,
): Promise<WorkRuleRow> {
  return requireData(await client.post<WorkRuleRow>("/work/rules", body));
}

/** The ENABLED switch on `Work-026`. `BR-WRK-033`: a rule that is off raises
 *  nothing — and keeps its memory, so switching it back on does not re-raise
 *  every subject it has ever seen. */
export async function setWorkRuleEnabled(
  ruleId: string,
  enabled: boolean,
  client: ApiClient = api,
): Promise<WorkRuleRow> {
  const verb = enabled ? "enable" : "disable";
  return requireData(await client.post<WorkRuleRow>(`/work/rules/${ruleId}/${verb}`, {}));
}

/** One row of `Work-028`'s template list — filtered by *applies to asset
 *  types*. `restricted: false` means the template names NO asset types, which
 *  is *nobody has restricted it* rather than *it applies to nothing*. */
export interface AssetTemplateRow {
  id: string;
  name: string;
  scope: string;
  restricted: boolean;
}

/** The house envelope (`results`) plus the asset. SRV-2's one-round `rows`
 *  twin was retired by lane SRV-3 once RAISE read only `results` (2.501.0). */
export interface AssetTemplatesPayload {
  asset: { id: string; asset_no: string; asset_type_id: string | null } | null;
  count: number;
  next: string | null;
  previous: string | null;
  results: AssetTemplateRow[];
}

export async function listTemplatesForAsset(
  assetId: string,
  client: ApiClient = api,
): Promise<AssetTemplatesPayload> {
  return requireData(
    await client.get<AssetTemplatesPayload>(`/assets/${assetId}/work-order-templates`),
  );
}

/** The jobs raised against one asset, and the Maintenance history's index.
 *
 *  ⚠ **`maintenance_index` IS KEYED BY DATE AND THAT IS A JUDGMENT, NOT A
 *  STORED LINK.** `BR-WRK-056` forbids a column on `asset_maintenance`, so the
 *  history's Work-order column pairs a repair with the job raised on the same
 *  day; a row with no job on its date keeps the dash — which is r10's own third
 *  row. The reasoning is in `apps/work/asset_door.py` and the decision log.
 *
 *  ⚠ THIS PARAGRAPH DESCRIBES `AssetWorkOrders`, the ENVELOPE, and sat above
 *  the ROW type because the row type used to be the only thing here. It now
 *  reads with the alias below rather than against it. */

/**
 * One job raised against an asset — **`_scoped_row`'s shape, by alias**
 * (`DEF-MET-4967`, 2026-09-12).
 *
 * ⚠ **THIS DECLARED FOUR KEYS WHERE THE WIRE CARRIES TWENTY-FOUR**, and the
 * cost was not a type complaint: the asset's Maintenance tab fetched the list
 * on every open and read only `maintenance_index`, so `rows` and `total` were
 * paid for and thrown away. A four-key type is what made that invisible —
 * there was nothing on the row worth drawing, so nobody noticed nothing was
 * drawn.
 *
 * ⚠ **IT IS AN ALIAS AND NOT A COPY, BECAUSE THE SERVER SAYS SO.**
 * `apps/work/asset_door.orders_for_asset` returns `selectors._scoped_page`,
 * whose own docstring is *"one row shape for every list of work orders in this
 * product, so the account tab, the premises tab, the dispatcher's queue and
 * this one cannot describe the same order four ways."* A second interface here
 * would be exactly that fourth description.
 *
 * ⚠ **`priority` IS NOT ON IT, AND THAT IS DELIBERATE RATHER THAN AN
 * OVERSIGHT.** It is built by `dispatch._priority_of` and reaches
 * `_dispatch_row` only; `_scoped_row` has never served it. Adding it there
 * would widen the premises tab and the account tab in the same commit — see
 * `WorkOrderDispatchRow` above, whose own comment is this same reasoning from
 * the other side. `due_at` and `technician` ARE served, and are what the
 * asset's Open work panel draws.
 */
export type AssetWorkOrderRow = ScopedWorkOrderRow;

/**
 * ⚠ **BROKEN AT BOTH ENDS, AND THE SERVER HALF LOST A WHOLE FIELD**
 * (`DEF-AST-4120`).
 *
 * The client half is `DEF-WRK-4098`'s shape again — five selector keys where
 * the wire carries four envelope ones. The SERVER half is worse and is fixed in
 * `apps/work/api.py`: `asset_work_orders` set `result["maintenance_index"]` and
 * then handed `result` to `_envelope()`, **which builds a fresh dict of four
 * keys and copies nothing else**. Two other call sites in that same file write
 * `{**_envelope(request, result), "counts": …}` precisely because they hit this
 * and noticed; this one did not, so the index never left the server and the
 * asset detail's Maintenance history drew a dash in every WORK ORDER cell —
 * the exact cell wave M's own render check exists to prove.
 *
 * `maintenance_index` stays at the TOP LEVEL of what this returns, beside the
 * rows, because that is where `AssetDetailPage` reads it and because a caller
 * that had to reach into a nested `body` for it is a caller one edit away from
 * describing a second shape.
 */
export interface AssetWorkOrders extends PagedRows<AssetWorkOrderRow> {
  /** `WO-4908` keyed by maintenance-entry id — the Work-order column of
   *  `BR-WRK-056`'s history. An empty object when nothing has been raised,
   *  never absent: an absent index and an empty one render identically, which
   *  is how this stayed invisible. */
  maintenance_index: Record<string, string>;
}

export async function listAssetWorkOrders(
  assetId: string,
  client: ApiClient = api,
): Promise<AssetWorkOrders> {
  const path = `/assets/${encodeURIComponent(assetId)}/work-orders`;
  const page = await readListPageWith<
    AssetWorkOrderRow,
    { maintenance_index?: Record<string, string> }
  >(path, {}, client);
  return {
    rows: page.rows,
    total: page.total,
    maintenance_index: page.body.maintenance_index ?? {},
  };
}

/** `POST /work-orders` with `asset_id` — **the Assets door** (`BR-WRK-056`).
 *
 *  The SAME write as the dispatcher's, with a different `source`: `assets`
 *  rather than `dispatcher`, so a report grouping by RAISED BY can tell a job a
 *  clerk raised standing on a meter from one raised from the queue. That is why
 *  this is its own function and not a `source` parameter on the dispatcher's —
 *  a door whose provenance is a caller-supplied string gets the wrong stamp the
 *  first time somebody copies the call.
 *
 *  No connection is created and none is named: `Work-007`'s CONNECTION column
 *  reads a dash for these, which is the `ConsequenceBox`'s own first sentence. */
export async function raiseWorkOrderForAsset(
  body: {
    asset_id: string;
    type: string;
    template_id?: string | null;
    priority_id?: string | null;
    due_at?: string | null;
  },
  client: ApiClient = api,
): Promise<{ id: string; order_no: string | null; dispatch_state: string }> {
  return requireData(
    await client.post<{ id: string; order_no: string | null; dispatch_state: string }>(
      "/work-orders",
      { ...body, source: "assets" },
    ),
  );
}

// ── CR-070 wave K · what the OFFICE reads back (`Work-033`) ────────────────
//
// ⚠ **THE SAME THREE ROUTES THE PHONE CALLS, AND THAT IS DELIBERATE.**
// `apps/work/api.py` says so where it registers them: *"`Work-033` READS THESE
// TOO … there is one route per fact rather than a staff copy and a phone copy
// of each. Two copies is how the two surfaces come to disagree about whether a
// job may close."* So the supervisor's screen asks the server the same
// questions the handset asks, and neither recomputes the other's answer.

/**
 * `GET /work-orders/{id}/close-readiness` — may this job close, and what is a
 * flag rather than a blocker.
 *
 * ⚠ **TWO LISTS, AND A CALLER THAT CONCATENATES THEM HAS UNDONE THE RULE.**
 * `blocking` holds missing REQUIRED photographs, which stop the close;
 * `flagged` holds out-of-range values, which never do (`BR-WRK-039` /
 * `BR-WRK-040`). The counts come down as INTEGERS because *3 of 4* assembled in
 * JavaScript is a plural nobody can translate.
 */
export interface CloseReadiness {
  can_close: boolean;
  blocking: { kind: string; scope: string; id: string; prompt: string }[];
  flagged: {
    kind: string;
    scope: string;
    id: string;
    prompt: string;
    value: string | null;
    unit: string;
  }[];
  readings_captured: number;
  readings_total: number;
  required_photos_taken: number;
  required_photos_total: number;
}

export async function getCloseReadiness(
  orderId: string,
  client: ApiClient = api,
): Promise<CloseReadiness> {
  return requireData(
    await client.get<CloseReadiness>(`/work-orders/${orderId}/close-readiness`),
  );
}

/** One photograph on the job — what `Thumbnail` opens to. */
export interface OrderAttachment {
  id: string;
  kind: string;
  taken_at: string | null;
  /** Which handset — sent by no client yet, so usually `null`. */
  device: string | null;
  /** WHO took it. The fact a supervisor questioning a reading needs first. */
  added_by_name: string | null;
  reading_id: string | null;
  task_id: string | null;
}

export async function getOrderAttachments(
  orderId: string,
  client: ApiClient = api,
): Promise<OrderAttachment[]> {
  return requireData(
    await client.get<OrderAttachment[]>(`/work-orders/${orderId}/attachments`),
  );
}

/**
 * `GET /work-orders/{id}/signature` — what the Customer tab shows.
 *
 * ⚠ **`null` IS *NOBODY HAS ASKED YET*, WHICH IS NOT A REFUSAL** and must not
 * render as one. B14 rule 32 makes a stated absence CLOSED by default, so the
 * screen shows nothing at all rather than a line explaining that nothing has
 * happened.
 */
export interface OrderSignature {
  id: string;
  refused: boolean;
  printed_name: string | null;
  decline_reason: string | null;
  signed_at: string | null;
  /** `DEF-WRK-10635` — the refusal's door-hanger photo (`DEF-WRK-10625`). */
  door_hanger_attachment_id?: string | null;
  door_hanger_uploading?: boolean;
}

export async function getOrderSignature(
  orderId: string,
  client: ApiClient = api,
): Promise<OrderSignature | null> {
  const response = await client.get<OrderSignature | null>(
    `/work-orders/${orderId}/signature`,
  );
  return (response.data ?? null) as OrderSignature | null;
}
