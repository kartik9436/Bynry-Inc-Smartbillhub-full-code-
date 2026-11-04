// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.6` — the six Counter screens of
//           `05-prototype/06 Payments Page Blueprint.pdf` §03 frames 3·1, 3·2
//           and 3·3a–d, read AS IMAGES at scale 2.0 (p051–p059).
//           ⚠ **THE PDF IS NOT ON THIS BRANCH.** It is on
//           `origin/claude/confirm-understanding-3ktufc`, which is the same
//           anomaly `CLAUDE.md` records for the Billing blueprint — check the
//           refs, not just yours.
// Screens:  3·1 Counters (`PAY-04`) · 3·2 My counter (`PAY-07`) ·
//           3·3a Start · 3·3b Close · 3·3c Force close · 3·3d Declare
// Rules:    CLAUDE.md hard rule 2 (money is a DECIMAL STRING on the wire and
//           never a JSON number) · hard rule 1 (the tenant is the URL's first
//           segment; this file sends none) · BR-SHL-011 (the list URL grammar)
//           · BR-SHL-025 (a role check is the SERVER's; see `forceCloseCounter`)
//           · `CR-136-BRC07` §3.1 · §3.2 · §3.3
// ───────────────────────────────────────────────────────
// The typed wrappers for the six counter routes the blueprint proposes.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ SERVED SINCE 2026-09-23 — AND THE TWO LANES' CONTRACTS MET
// ══════════════════════════════════════════════════════════════════════════
// This file was written against the DRAWING while `P2.1`–`P2.3` were being
// built in parallel, and it said so. `apps/payments/counters_api.py` landed
// the same day and chose these field names deliberately — its own comment
// reads *"`rows`, NOT DRF's `results`, AND THE SCREEN LANE'S NAME WINS"* —
// so the six routes below are LIVE and the types are read off the server's
// own payload builders rather than off the drawing:
//
//   `POST /counters`                  3·3a p054, verbatim: *"opens the session
//                                     AND its batch, in one act"*
//   `GET  /counters`                  3·1 p052 *To build*
//   `GET  /counters/{ref}`            3·2 p053 *To build*, with its running
//                                     split by method
//   `POST /counters/{ref}/close`      3·3b p055
//   `POST /counters/{ref}/force-close`3·3c p057, *"supervisor only"*
//   `POST /counters/{ref}/declare`    3·3d p058
//
// **Nothing here invents a seventh route or a different verb.** Where the
// drawing did not say what a field is called, the field is named after the
// COLUMN that already exists in `apps/payments/counter_session_models.py`,
// which is the only other authority there is.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE ADDRESS SEGMENT IS THE COUNTER'S **CODE**, AND THE DRAWING SAYS `{id}`
// ══════════════════════════════════════════════════════════════════════════
// 3·2's own address is drawn as `/:tenant/payments/counter/CTR-260921-DW` —
// the CODE — while every write is drawn as `POST /counters/{id}`. Both cannot
// be literally true of one value, and **B14 rule 31 decides it**: no database
// id is ever the visible value of a field, and an address bar is the most
// visible field there is. So this client speaks in a `CounterRef`: whatever
// the list served as the row's `code`, which is what the address carries and
// what a clerk reads out loud.
//
// **The server must therefore resolve a counter by its code.** That is a
// contract this lane needs and cannot write; it is stated in `P2.6`'s row on
// `12-governance/change-requests/CR-136-BRC07-payments-phase-2-the-counter.md`
// so LANE P2-API reads it rather than being told in a chat that does not
// survive (hard-won law 10).
import type { ApiClient, ApiResponse } from "./client";

/** A 2xx with no body where the contract promises one is a server bug (B12
 *  r1). Throwing beats handing a screen a silent `null` it renders as blank.
 *  Restated here rather than imported from `endpoints.ts`, which three lanes
 *  are editing on any given afternoon. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/**
 * What the address bar carries and what this client sends — the counter's
 * human-facing CODE, never its primary key. See the header.
 */
export type CounterRef = string;

/**
 * `apps.payments.models.COUNTER_CLOSE_KINDS`, and it stays at THREE.
 *
 * ⚠ **`declared` IS NOT A FOURTH VALUE AND WILL NOT BECOME ONE** —
 * `CR-136-BRC07` §3.2, PO ruling 2026-09-23, verbatim: *"(a) Keep it as a
 * forced close and add the late count beside it"*. A late count fills
 * `declared_at`, `declared_by`, `counted_totals`, `difference` and `note`; it
 * does not rewrite how the till was sealed, because that would erase who
 * counted what.
 */
export const COUNTER_CLOSE_KINDS = ["counted", "forced", "system"] as const;
export type CounterCloseKind = (typeof COUNTER_CLOSE_KINDS)[number];

/** One countable or uncountable method's running figure on an open till, and
 *  its counted figure on a closed one. Money is a decimal STRING (hard rule
 *  2): a JSON number is a double in every serialiser in this stack, and this
 *  is a figure whose whole job is to be compared with a drawer. */
export interface CounterMethodTotal {
  /** The tenant's own method id. **Never rendered** — B14 rule 31. */
  method_id: string;
  /** What the clerk calls it: *Cash*, *Cheques*, *Tap and pay*. */
  method_name: string;
  /** `cash` · `check` · `money_order` · `card` · `ach` · `wire` · `lockbox`. */
  method_code: string;
  /** What the system says this till took through this method. */
  system_total: string;
  /**
   * ⚠ **`false` IS THE WHOLE OF p056's ③, AND IT IS DRAWN DELIBERATELY.**
   * Verbatim: *"you cannot count a card total in a drawer, so the screen does
   * not pretend"*. Only cash and cheques are countable; an uncountable method
   * renders the words *Not counted* in the YOU COUNTED column and a dash in
   * DIFFERENCE, and contributes to neither total.
   */
  countable: boolean;
  /** How many payments made up `system_total`. */
  payment_count: number;
  /**
   * The figure somebody actually counted, on a till that has been counted.
   * `null` on an open till, and `null` for ever on an uncountable method.
   */
  counted_total?: string | null;
}

/** One row of 3·1's list. */
export interface CounterRow {
  /** The row's human-facing code — `CTR-260921-DW`. The address segment. */
  code: CounterRef;
  /** The person accountable for the drawer. `null` on the system till, which
   *  is nobody's by constraint (`ck_counter_sessions_system_is_nobodys`). */
  owner_name: string | null;
  /** The walk-in counter the till is at. `null` on the system till. */
  service_centre_name: string | null;
  opened_at: string;
  closed_at: string | null;
  close_kind: CounterCloseKind | null;
  /** ⚠ `CR-136-BRC07` §3.2's two new columns. Set together or not at all. */
  declared_at: string | null;
  declared_by_name: string | null;
  payment_count: number;
  /** What the system says the till took, across every method. */
  taken_total: string;
  /** What somebody counted, across the COUNTABLE methods. `null` until they
   *  did — which is 3·1 annotation ④: *"empty is the finding"*. */
  counted_total: string | null;
  /** Counted minus expected at the moment of the count. Positive is over. */
  difference: string | null;
  currency: string;
}

/** 3·1's four tiles, folded server-side over the same rows the table shows —
 *  never computed in the browser off one page of a paginated list. */
export interface CounterListTotals {
  open_now: number;
  /** The names behind `open_now`, for the tile's detail line. Bounded to ten
   *  by the server — a display bound on one subtitle, never a cap on the list
   *  (`NFR-5`). */
  open_owner_names: readonly string[];
  /**
   * ⚠ **THE TWO DAY-SHAPED TILES ANSWER `null` WITHOUT AN `as_of`, AND THE
   * NULL IS NOT A ZERO.** Nothing under `apps/payments/` may read a wall clock
   * (`BR-TEN-043`), because a server clock decides a business day in the
   * SERVER's timezone. So a caller that does not say which day it means gets a
   * stated absence, and `?? "0"` here would turn *"we cannot answer"* into
   * *"$0.00 was taken today"* — a different and far more alarming statement.
   * That is `DEF-127`'s shape and it reached a real screen: the Counter tab
   * printed `$0.00 · payments` in a browser before this type was narrowed.
   */
  taken_today: string | null;
  taken_today_payment_count: number | null;
  difference_this_week: string | null;
  /** `"as_of_missing"` when the two above are null, so a screen can say WHICH
   *  absence it is rather than guessing. */
  totals_unavailable?: string | null;
  /** ⚠ THE DERIVED EXPRESSION, COUNTED ON THE SERVER. See `isNotCounted`. */
  not_counted: number;
  /** The opened date of the oldest uncounted till, for the tile's detail. */
  not_counted_oldest: string | null;
  currency: string;
}

export interface CountersResponse {
  rows: CounterRow[];
  count: number;
  totals: CounterListTotals;
}

/** 3·2's detail — the running split by method, which p053 ③ calls *"what a
 *  till reconciliation actually needs"*. */
export interface CounterDetail extends CounterRow {
  opening_float: string;
  methods: CounterMethodTotal[];
  /** Force close and declare both require one; a counted close requires one
   *  only when the difference is not zero (p056). */
  note: string | null;
  /** Who sealed it, which on a forced close is not the owner. */
  closed_by_name: string | null;
}

export interface StartCounterBody {
  /**
   * The EXISTING reference-data list — 3·3a ①, marked `REUSED`, and served by
   * `GET /settings/reference-data/service-centres`.
   *
   * ⚠ **THE KEY IS `service_centre_id`; THE VALUE IS THE CENTRE'S `slug`.**
   * Those two sentences look like they disagree and they do not.
   * `counters._service_centre()` resolves the reference **by slug first** and
   * falls back to a uuid primary key, precisely so a caller need not look an
   * id up — that list is keyed by slug everywhere it is already read
   * (`getServiceCentre(slug)`), and B14 rule 31 keeps a database id out of
   * anything a person can see, which a form value that lands in an error
   * message is. The server's PARAMETER is still spelled `_id`, and the wire
   * key is the server's to name.
   *
   * ⚠ **THIS FIELD READ `service_centre` UNTIL `DEF-PAY-6314` (2026-09-23),
   * AND THE VALUE WAS NEVER WRONG — ONLY THE KEY.** `payload.get(
   * "service_centre_id")` came back `None`, so every *Start counter* on the
   * deployed build was refused with `BR-PAY-1160`, *"a counter is a till AT a
   * place, and this request names none"*, over a form in which the clerk had
   * just picked one.
   */
  service_centre_id: string;
  /** A decimal string. Hard rule 2, and `opening_float` is `NUMERIC(18,4)`. */
  opening_float: string;
  /**
   * ⚠ **REQUIRED, AND THE CLIENT IS WHERE IT COMES FROM** — `BR-TEN-043` and
   * gate G6: nothing under `apps/payments/` may read a wall clock, so
   * `_counters_open` refuses a body without it rather than stamping the
   * server's day on a till opened at 08:55 in Houston. The type never
   * mentioned it until `DEF-PAY-6314`, which is why no caller ever sent one.
   *
   * ⚠ **A TENANT WALL CLOCK — `YYYY-MM-DDTHH:mm` — AND NOT AN INSTANT.** PO
   * ruling 2026-09-23, verbatim: *"show date and time pciker and deult should
   * be as per date time format set by utility and timezone - show the detault
   * time"*. So 3·3a draws a THIRD field: a date-and-time picker prefilled with
   * the current moment in the utility's own zone, which the clerk may change.
   *
   * It is sent NAIVE and that is deliberate. `apps/payments/api._moment`
   * anchors a value carrying no offset in the tenant's own timezone —
   * `BR-TEN-081` / `OQ-153`, *"a time of day with no zone … came from a human
   * in that utility"* — so the wall clock the clerk read off the screen is the
   * instant that gets stored. Computing an offset in the browser would derive
   * the tenant's UTC offset, DST included, a second time in a second place.
   *
   * ⚠ **THE OTHER THREE WRITES BELOW STILL SEND `toISOString()`**, because
   * they are not drawn with a picker and the ruling was given about *Start
   * counter*. See their own notes.
   */
  opened_at: string;
}

/** One counted figure per COUNTABLE method, keyed by the tenant's method id —
 *  the shape `counter_sessions.counted_totals` already declares. */
export type CountedTotals = Record<string, string>;

/**
 * ⚠ **THE MOMENT ON THESE THREE WRITES IS MACHINE-STAMPED, AND THAT IS A
 * REPORTED OPEN SHAPE RATHER THAN A DECISION (`DEF-PAY-6315`).**
 *
 * All three endpoints require one — `counter_close` and `counter_force_close`
 * read `closed_at`, `counter_declare` reads `declared_at`, each through
 * `_required_moment` — and none of the three bodies declared it, so all three
 * refused every submit exactly as *Start counter* did.
 *
 * The PO's 2026-09-23 ruling asked for a prefilled date-and-time picker and it
 * was given about **3·3a Start counter**. It is not obvious that it carries to
 * these: a close is *"I am sealing the drawer now"*, and a DECLARE is the one
 * that most likely does want a typed moment, because a late count is by
 * definition made at a time other than the press (3·3d, *"the count, late"*).
 * Choosing for them would be this file widening a ruling nobody gave, so the
 * contract is made correct here with `new Date().toISOString()` — offset-
 * bearing, the shape `confirmed_at` and `issued_at` already use — and the
 * question is put back to the PO rather than answered.
 */
export interface CloseCounterBody {
  counted_totals: CountedTotals;
  /** Required by the service only when the difference is not zero (p056). */
  note?: string;
  /** ⚠ **REQUIRED** — `counter_close` reads it through `_required_moment`. */
  closed_at: string;
}

export interface ForceCloseCounterBody {
  /** ⚠ **REQUIRED** — 3·3c ②, verbatim: *"a force close with no reason is
   *  indistinguishable from a mistake"*. */
  note: string;
  /** ⚠ **REQUIRED** — `counter_force_close` reads it through
   *  `_required_moment`. See the note above `CloseCounterBody`. */
  closed_at: string;
}

export interface DeclareCountBody {
  counted_totals: CountedTotals;
  /** ⚠ **REQUIRED, ALWAYS** — `CR-136-BRC07` §3.2. A declared difference is
   *  the only number nobody watched happen (3·3d ②). */
  note: string;
  /** ⚠ **REQUIRED** — `counter_declare` reads it through `_required_moment`.
   *  The likeliest of the three to want a typed moment; see the note above
   *  `CloseCounterBody`. */
  declared_at: string;
}

export function getCounters(
  client: ApiClient,
  query: Record<string, string | number | undefined>,
): Promise<CountersResponse> {
  return client
    .get<CountersResponse>("/counters", { query })
    .then((response) => requireData(response));
}

export function getCounter(client: ApiClient, ref: CounterRef): Promise<CounterDetail> {
  return client
    .get<CounterDetail>(`/counters/${encodeURIComponent(ref)}`)
    .then((response) => requireData(response));
}

/**
 * 3·3a — **one act, not two.** The blueprint's ② is a ruling of 2026-09-21:
 * *"the batch is created by this button — there is no separate 'start
 * batch'"*, so every payment carries its batch id from the first one and
 * closing only seals it.
 */
export function startCounter(client: ApiClient, body: StartCounterBody): Promise<CounterDetail> {
  return client.post<CounterDetail>("/counters", body).then((response) => requireData(response));
}

export function closeCounter(
  client: ApiClient,
  ref: CounterRef,
  body: CloseCounterBody,
): Promise<CounterDetail> {
  return client
    .post<CounterDetail>(`/counters/${encodeURIComponent(ref)}/close`, body)
    .then((response) => requireData(response));
}

/**
 * 3·3c — **supervisor only, and the check is the SERVER's** (`BR-SHL-025`).
 * A button hidden from a Billing Clerk is not a guarantee; the screen reflects
 * the role, it does not enforce it.
 */
export function forceCloseCounter(
  client: ApiClient,
  ref: CounterRef,
  body: ForceCloseCounterBody,
): Promise<CounterDetail> {
  return client
    .post<CounterDetail>(`/counters/${encodeURIComponent(ref)}/force-close`, body)
    .then((response) => requireData(response));
}

/**
 * 3·3d — the late count, **beside** the forced close and never over it
 * (`CR-136-BRC07` §3.2).
 */
export function declareCount(
  client: ApiClient,
  ref: CounterRef,
  body: DeclareCountBody,
): Promise<CounterDetail> {
  return client
    .post<CounterDetail>(`/counters/${encodeURIComponent(ref)}/declare`, body)
    .then((response) => requireData(response));
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §2 · §3.1–§3.4 · §4 row `P2.6` · blueprint p051–p059 read as images at 2.0
// generated: 2026-09-23 by LANE P2-SCREENS
// checklist: A✔ B=n/a(this lane serves no endpoint — `P2.1`/`P2.2`/`P2.3` are LANE P2-API's) C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit · apiPathLiteral.guard.test.ts
// exceptions: E3 the six routes are NOT SERVED at this commit — stated in the header rather than guessed at, and every screen renders the server's refusal as a sentence · E3 the address segment is the counter CODE where the drawing writes `{id}`, decided by B14 rule 31 and recorded in the CR
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

/**
 * `GET /counters/service-centres` — the places a till can be opened at, read
 * as a Billing Clerk may (DEF-PAY-10768, L1-11). The Settings reference-data
 * read is closed to that role by A4, so *Start counter* reads this instead.
 */
export interface CounterCentre {
  slug: string;
  name: string;
}

export async function getCounterCentres(client: ApiClient): Promise<{ centres: CounterCentre[] }> {
  return requireData(await client.get<{ centres: CounterCentre[] }>("/counters/service-centres"));
}
