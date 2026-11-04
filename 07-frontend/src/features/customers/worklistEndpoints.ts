// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W6 task 6.12 (S86 `NCT-01`) · W7 task 7.4 (S89) · W7 task
//           7.11 (S90) — the FRONTEND half of three worklists whose backends
//           shipped 2026-08-25 with `E=deferred(no-frontend-half)` in their own
//           trailers. The PO reported the hole from a live build: *"nothing on
//           new connect + on all of these screens"*.
// Rules:    CLAUDE.md hard rule 2 (money stored 4 dp, DISPLAYED 2 — the server
//           rounds once and this client never re-rounds) · BR-SHL-011 (list URL
//           grammar; these three lists are EMBEDDED and own no query string —
//           DEF-664) · BR-SHL-010 (an undeclared capability is not rendered) ·
//           B14 rule 21 (the screens that consume this add no stylesheet class)
// Design:   04-docs/02-decisions/18-cr030-onboarding-design.md — §5.4.1/§5.4.2
//           and §5.4.9 `NCT-01` (new connects) · §5.7.1/§5.7.2 (transfers) ·
//           §5.8.1/§5.8.2 (disconnects)
// Tests:    NewConnectsTab.test.tsx · TransfersTab.test.tsx ·
//           DisconnectsTab.test.tsx
// Impacts:  06-backend/apps/metering/api.py `GET /connections` ·
//           06-backend/apps/customers/api.py `GET /transfers` · `GET /disconnects`
// ───────────────────────────────────────────────────────
//
// THE TYPED WRAPPERS FOR THE THREE WORKLIST ROUTES THE ACCOUNTS TABS CALL.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS ITS OWN FILE
// ══════════════════════════════════════════════════════════════════════════
// `serviceRequestEndpoints.ts`'s reason, unchanged: `api/endpoints.ts` is the
// file every lane appends to, and on any afternoon it holds two or three lanes'
// half-finished work. One family, one file, one lane's diff. Nothing here
// re-exports or shadows anything `endpoints.ts` publishes.
//
// ══════════════════════════════════════════════════════════════════════════
// THE THREE ENVELOPES ARE NOT THE SAME SHAPE, AND THAT IS THE SERVER'S FACT,
// NOT A TYPO HERE
// ══════════════════════════════════════════════════════════════════════════
// `GET /connections` answers the DRF envelope — `count` / `next` / `previous` /
// `results` — because `_connections_envelope` builds it by hand for exactly
// that reason (*"ONE SHAPE. Every list in this product answers the DRF envelope
// unconditionally"*). `GET /transfers` and `GET /disconnects` answer their
// selectors' own `{rows, page, per, total, pages}` verbatim: `transfers_list`
// and `disconnects_list` return `list_transfers(...)` / `list_disconnects(...)`
// with nothing wrapped around them. **Measured on the tree, 2026-08-25.**
//
// Three of one and two of the other is a real divergence and it is REPORTED
// rather than smoothed over here: normalising it in this file would put a
// second opinion about the contract in the client, and the next lane reading
// `apps/customers/api.py` would find a shape no server sends. What the screens
// get instead is `rowsOf`/`totalOf` below — two functions that read whichever
// envelope arrived, so a screen never learns which of its lists is which.
//
// ══════════════════════════════════════════════════════════════════════════
// AN `unavailable` BLOCK IS A STATED ABSENCE. IT IS NEVER A ZERO.
// ══════════════════════════════════════════════════════════════════════════
// All three payloads carry them, and each is `{code, br_ref?, tracks?, detail}`
// where `detail` is the sentence a utility user reads and the ids are machine
// fields (G28/CR-016, DEF-332). Four of them are load-bearing on these screens
// and each is rendered rather than defaulted:
//
//   · **the segment refusals** (OQ-371 on connections, OQ-374 on disconnects) —
//     the screen DISABLES the tabs it cannot fill and shows the reason on them,
//     so it never calls the route to discover that it fails;
//   · **`delivery_state: null`** on every disconnect notice — there is no
//     email, SMS or print adapter in this release, so `emailed`, `posted`,
//     `certified sent` and `certified signed` must not be rendered by anything;
//   · **a transfer MONEY line whose `amount` is `{stored: null, display: null}`**
//     — the account HOLDS a deposit whose carried figure cannot be read, and
//     `$0.00` there would serve `$150.00` where `$153.50` is held (❄️ WE-7 /
//     GT-23's frozen pair), keeping $3.50 of the customer's money;
//   · **`owed` with `display: null`** — DEF-127: a fabricated `$0.00` *"looks
//     exactly like a settled account"*, and on the disconnects tab it looks
//     like an account nobody should be chasing.
//
// So every money field below is `string | null` and NOT `string`, and the null
// is what makes the screen branch instead of defaulting.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import type { BuildHome } from "@/features/work/workEndpoints";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated rather than imported from `endpoints.ts` so this file adds no
 *  coupling to a file three lanes are editing — `bankRecEndpoints`' rule. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

// ══════════════════════════════════════════════════════════════════════════
// SHARED SHAPES
// ══════════════════════════════════════════════════════════════════════════

/**
 * One stated absence, as all three selectors build them.
 *
 * `detail` is the only field that reaches a user. `code`, `br_ref` and `tracks`
 * are machine fields — `tracks` names the register row whose closure kills the
 * sentence, so an absence expires by itself instead of outliving its question
 * (G38's discipline, pointed at a server payload).
 */
export interface WorklistAbsence {
  code: string;
  br_ref?: string;
  tracks?: string;
  detail: string;
  /** Only on the connections segment refusal: the four tabs it cannot fill. */
  segments?: string[];
}

/**
 * The two shapes CLAUDE.md hard rule 2 requires, exactly as the servers build
 * them: `stored` is the 4-dp string, `display` the 2-dp one the SERVER already
 * rounded.
 *
 * ⚠ **BOTH ARE NULLABLE AND A SCREEN RENDERS `display` OR THE REASON — NEVER
 * A RE-ROUNDING OF `stored`.** Rounding for a human happens once, server-side
 * (rule 2, and B4's "round only at finalization/display"). A client that
 * quantized `stored` itself would be the second rounding path this product
 * spent DEF-088 removing.
 */
export interface WorklistMoney {
  stored: string | null;
  display: string | null;
}

// ══════════════════════════════════════════════════════════════════════════
// CR-045 wave G · `DEF-1702`'s FRONTEND HALF — THE `f.<name>` SERIALIZER THE
// FOUR WORKLIST WRAPPERS SHARE
// ══════════════════════════════════════════════════════════════════════════

/**
 * `state.filters` → the `f.<name>` query BR-SHL-011 signs, ALLOW-LIST FIRST.
 *
 * ⚠ **THE FILTER IS SENT TO THE SERVER AND THAT IS THE WHOLE POINT (`DEF-1702`).**
 * Every list behind these wrappers is PAGED — the server answers one window and
 * a total. A dimension narrowed in the browser would narrow THE PAGE IN HAND,
 * so `state=waiting` over page 1 of 9 would report the waiting rows of the
 * first fifty and call it the answer. It is a subset of a subset, it is
 * silently wrong, and it is worse than no control at all because the count
 * beside it looks authoritative. Every leg below applies its `WHERE` in the
 * queryset BEFORE paging (`transfer_reads.list_queryset`,
 * `move_reads.move_ins_queryset`, `disconnect_reads._rows_for`,
 * `connection_reads.list_connections`), so the total moves with the filter.
 *
 * ⚠ **ALLOW-LIST, NOT PASS-THROUGH**, and it is `getImportRuns`' shape one
 * screen along: an undeclared name is DROPPED here rather than sent. The
 * server's `parse_list_params(allowed_filters=…)` drops it a second time, so
 * this is a convenience and never the guard — but it keeps a screen from
 * shipping a param nobody serves and reading the silence as "no matches".
 *
 * An empty value is an ABSENT dimension, never `f.state=` — that is what
 * `FilterBar.setFilter` writes when a chip's ✕ is clicked, and an empty
 * `f.<name>` is a value the server would try to match.
 */
export function worklistFilterParams(
  filters: Record<string, string> | undefined,
  allowed: readonly string[],
): Record<string, string> {
  const query: Record<string, string> = {};
  for (const name of allowed) {
    const value = filters?.[name];
    if (value !== undefined && value !== "") {
      query[`f.${name}`] = value;
    }
  }
  return query;
}

/** One served filter dimension, as every worklist payload publishes it.
 *  The screen reads its vocabulary from here and NEVER hardcodes one
 *  (BR-SHL-010) — a code the server stops serving stops being offered. */
export interface WorklistFilterState {
  code: string;
  /** The server's own word for this value, when it serves one.
   *
   * ⚠ **OPTIONAL BECAUSE IT IS OPTIONAL ON THE WIRE, NOT AS A HEDGE.** The
   * disconnects list serves `label` on the two DRAFT states and on every
   * `dues` value, and omits it on the stored case states — where the screen's
   * own catalogue owns the word. A screen falls back to its catalogue and
   * never to the CODE, which is `DEF-CUS-6053`: three filter options reached a
   * clerk reading `closed_out`, `in_progress_draft` and `parked`. */
  label?: string;
  /** Whether the blueprint draws this value as a quick view. Served so a
   *  screen cannot decide it locally. */
  drawn?: boolean;
}

// ══════════════════════════════════════════════════════════════════════════
// S86 · `GET /connections` — B18 §5.4, the NEW CONNECT worklist
// ══════════════════════════════════════════════════════════════════════════

/** The only segment the server serves. Every other value raises
 *  `NotImplementedError("OQ-371")` — see `CONNECTION_SEGMENT_UNAVAILABLE`. */
export const CONNECTION_SEGMENT_ALL = "all";

/** The refusal's `code`, so the screen can find its own absence in the list by
 *  name rather than by position. */
export const CONNECTION_SEGMENTS_NOT_DECIDED = "segments_not_decided";

/**
 * One `NCT-01` row: `CONNECTION · PREMISE · UNITS · SERVICES · ORDERS · TARGET
 * · WAITING ON · STATE`.
 *
 * ⚠ **`state` IS THE DERIVATION, NOT THE CACHED COLUMN**, and the KPI tiles are
 * the other way round. `connection_reads` §1 states the asymmetry and its tests
 * force the two apart on purpose; nothing on this side may re-derive either.
 *
 * ⚠ **THE PRODUCT WORD IS `activated` / `partly_activated`** — CR-032, PO
 * 2026-08-25, verbatim: *"instead of energise can we use activated"*. B18 still
 * DRAWS *"Partly energised"* and is stamped as such; the old tokens are gone
 * from `connections.py`, not aliased. Read the constants for the product and
 * the drawing for the layout.
 *
 * `request_no` and `applicant` are NOT drawn columns. They are served because
 * the search matches on them — a clerk who searches an applicant's name and
 * gets four rows that mention neither cannot tell why they matched — so the
 * screen declares them as columns that are OFF by default and reachable from
 * the column chooser.
 */
export interface ConnectionRow {
  id: string;
  connection_no: string;
  /**
   * ⚠ **`null` WHILE A DRAFT HAS NO ADDRESS YET — `DEF-CUS-6109`.** Approving
   * an application whose address had not resolved raises the build as a DRAFT
   * (PO ruling 2026-09-21) and `BR-MET-112` writes the property at the
   * wizard's last button, so this row legitimately names none in between. The
   * whole block goes rather than four nulls inside it: *there is no address
   * yet* is ONE fact, and a cell reading `premise_no` off an all-null object
   * cannot tell it from a property nobody numbered.
   */
  premises: {
    id: string;
    premise_no: string;
    name: string | null;
    address: string | null;
  } | null;
  /**
   * Where a person GOES to see this build — CR-070 wave O (`§W.11`).
   *
   * `/connections/<uuid>` stopped being a destination on 2026-09-04, so the
   * eye on this row goes to the build's home: the account that owns it, the
   * premises otherwise. Served by `connections.connection_home()`, the ONE
   * implementation every list in the product reads, so the *New connects* tab,
   * the approval queue and the dispatcher cannot disagree about where a build
   * lives. `null` for a build with neither — ⚠ **which became REACHABLE on
   * 2026-09-21 (`DEF-CUS-6109`) and this sentence said it was not.** It read
   * *"which `connections.premises_id` being NOT NULL makes impossible today"*,
   * true when written and false the moment the column became nullable
   * (hard-won law 1). A draft raised from an application whose address had not
   * resolved has no owner account and no premises, so it has no home until it
   * commits, and the eye on its row is drawn with nowhere to go.
   */
  home: BuildHome | null;
  units: number;
  /** Service CODES, sorted. The two-character badge set and its `+N` overflow
   *  chip are the screen's, because only the screen knows how many badges fit. */
  services: string[];
  /** B18 §5.4.2: *"not a percentage, not a bar alone. The fraction is readable;
   *  a bar is not"* — so both halves are served and no ratio is computed. */
  orders: { done: number; total: number };
  target_activation: string | null;
  waiting_on: string | null;
  state: string;
  request_no: string | null;
  applicant: string | null;
  /**
   * ── `CR-150-BRC09` · `CUSTOMER`, the drawn column — `connection_reads._row`
   *
   * ⚠ **THE WHOLE BLOCK OR `null`, LIKE `premises` ABOVE, AND NEVER `""`.** A
   * build with no owner account has no customer, and *there is no owner yet*
   * is ONE fact. Two nulls inside a block would let a cell read `account_no`
   * off an object meaning *nobody has been assigned* and draw it as *a
   * customer with no number*. The server's own note says the words are the
   * screen's to choose; the drawing writes **no account yet**.
   *
   * ⚠ **`account_no` IS NOT A DATABASE ID AND B14 RULE 31 DOES NOT REACH IT.**
   * Rule 31 is *no database id is ever the visible value of a field*; this is
   * `accounts.account_no`, the human number a clerk reads down the phone
   * (`AC-2026-00011` on the drawing), which is the same class as
   * `connection_no` and `premise_no` already on this row. The primary key is
   * served nowhere on this block at all — there is no `id` field here to
   * render by mistake, which is how that rule is kept rather than remembered.
   */
  customer?: { name: string | null; account_no: string | null } | null;
  /**
   * ── `CR-150-BRC09` · the money behind the column chooser (`Charged`)
   *
   * ⚠ **`display` IS PRINTED AND `stored` IS NEVER RE-ROUNDED** — hard rule 2,
   * and `WorklistMoney`'s own header above. `{stored: null, display: null}` is
   * a build nobody priced, and it renders a stated absence: a `$0.00` there
   * reads as *this build costs nothing*, which is `DEF-127` exactly.
   */
  quote_total?: WorklistMoney;
  /** `connections.connection_mode()` over the page's batched read of the work
   *  orders. `null` where a build has raised none yet — which is *nobody has
   *  said how this is being built*, not a mode called "none". */
  mode?: string | null;
  /** `CR-126-BRC07`'s step-1 answer. ⚠ **`null` MEANS NOBODY WAS ASKED** — the
   *  column was deliberately not back-filled, so every build raised before that
   *  migration has none and the cell states an absence rather than a default
   *  somebody never chose. */
  scope?: string | null;
  /** Who raised the build, resolved to a NAME by the page's one batched actor
   *  read. `null` where the actor cannot be named. */
  raised_by?: string | null;
  /** The build's own newest STAMP — `connection_reads._last_stamped_event`.
   *
   * ⚠ **IT IS NOT THE AUDIT TRAIL AND THE NAME SAYS SO.** `what` is a TOKEN
   *  (`created` · `submitted` · `held` · `activated` · `cancelled`) and never a
   *  sentence, because a token can be translated and an English sentence
   *  composed on the server cannot. */
  last_stamped_event?: { at: string; what: string } | null;
  /** ⚠ **`DEF-CUS-5994` (PO 2026-09-20) — THE DRAFT'S OWN FIELDS.** A parked
   *  wizard is a ROW of this list now; it was drawn on a pinned panel above the
   *  table until that day. `park_id` is `null` on a record row, and it is both
   *  the key `getRowId` uses and the handle `resumePath` builds `?parked=<id>`
   *  from — B14 rule 31 keeps it off the screen. The rest are the parked facts
   *  the panel carried, and **none of them is anywhere else**: `parked_by_name`
   *  in particular is what `CR-035` amendment 1 put in place of the
   *  mine/everyone's toggle it dissolved. */
  park_id?: string | null;
  row_kind?: string;
  park_note?: string | null;
  remind_on?: string | null;
  parked_at?: string | null;
  parked_by_name?: string | null;
  /** ⚠ **THE ONE CELL A NEW-CONNECT DRAFT CAN FILL.** A new connect has no
   *  premises, unit or account id until it commits — `NewConnectWizard` parks
   *  `subject_ref: {}` and says so — so the row shows the address the clerk
   *  TYPED, copied at the moment they put it down. `null` on a build row. */
  address_typed?: string | null;
  /**
   * ── `CR-150-BRC09` · `AGING`, the drawn column
   *
   * ⚠ **`age_days` STOOD IN THE PARKED-DRAFT BLOCK ABOVE AND IS NOT A DRAFT
   * FIELD ANY MORE.** `connection_reads._row` serves it on a BUILD row too,
   * from `submitted_at` falling back to `created_at`, counted in the utility's
   * own calendar day (`BR-TEN-043`) rather than in elapsed 24-hour periods —
   * which is `DEF-CUS-7620`, the defect that had the `oldest` tile and this
   * column reading two different clocks under one word.
   *
   * ⚠ **`age_is_accented` IS THE SERVER'S ANSWER AND NOTHING HERE MAY
   * RE-DERIVE IT** (`BR-CUS-106`, ruled at seven days inclusive; `AgeCell`'s
   * own rule: *"two thresholds is how the list and a later KPI drift
   * apart"*). **`null` IS *NOBODY COULD BE ASKED* AND IS NOT `false`** — the
   * seam returns it when customers publishes no threshold at all, and a
   * missing implementer answering *"not old"* is `DEF-075`'s substitution on
   * the column a clerk chases work from. `AgeCell` draws the three apart.
   *
   * ⚠ **THE FIGURE WAS RULED ON `REQ-01` AND THIS SCREEN WAS NEVER SHOWN —
   * `OQ-CUS-12771`, OPEN.** Reusing the ruled number is what stops a second
   * threshold being minted here; whether a BUILD, which runs for weeks rather
   * than days, wants its own is that row's question. Nothing is blocked on it.
   */
  age_days?: number | null;
  age_is_accented?: boolean | null;
}

export interface ConnectionKpis {
  open: number;
  waiting_on_inspection: number;
  partly_activated: number;
  units_awaiting_activation: number;
  /** Null when the tenant has no open build. ⚠ NOT `0` — "0 days" is a
   *  different claim from "there is none". */
  oldest: { days: number; connection_no: string; waiting_on: string | null } | null;
  /**
   * ── `CR-150-BRC09` · the drawn *Waiting on someone* tile
   *
   * Every open build with ANY value in `waiting_on`, trimmed and compared in
   * SQL. ⚠ **IT IS A DIFFERENT QUESTION FROM `waiting_on_inspection`, WHICH IS
   * ONE LITERAL AND HAS NOT LEFT** — a build waiting on *"site inspection"* is
   * invisible to the literal tile and counted by this one. Both are served
   * because removing a live figure to swap a caption takes a working tile off
   * the page before its replacement is wired (hard-won law 2).
   *
   * ⛔ **IT IS A FACT AND NOT A CONTROL.** `f.state` has no *waiting* value —
   * *waiting* is derived from a separate COLUMN and `OQ-371` is the open
   * question about ranking it against a state — so a tile wired to
   * `f.state=on_hold` would be a plausible-looking lie.
   */
  waiting_on_anyone?: number;
  /**
   * ⛔ **DRAWN AS `$4,210` AND SERVED AS `null` — `DEF-CUS-7619`, OPEN.**
   *
   * Exactly one of this and `owed_on_open_builds_unavailable` is ever set, and
   * today it is always the reason. Billing publishes `invoice_detail` for ONE
   * id and no batched position, so a tenant-wide total would be one call per
   * open build; B1 puts that read in billing's own selector and this module
   * may not author it.
   *
   * ⚠ **THE SCREEN RENDERS THE ABSENCE AND NEVER `$0.00`, AND IT NEVER ADDS
   * THE ROWS UP ITSELF.** A zero on this tile reads as *every build is paid
   * for* (`DEF-127`), and a browser-side total would be a second rounding path
   * on a receivable (hard rule 2). The DUE column is off for the same reason
   * and no row carries a `due` key at all.
   */
  owed_on_open_builds?: WorklistMoney | null;
  owed_on_open_builds_unavailable?: WorklistAbsence;
}

export interface ConnectionList {
  count: number;
  next: string | null;
  previous: string | null;
  results: ConnectionRow[];
  kpis: ConnectionKpis;
  segment: string;
  /** What this list CANNOT do, served on every response so the screen disables
   *  the four tabs it cannot fill and says why. */
  unavailable: WorklistAbsence[];
  /** CR-045 wave D · D.11 — the `f.<name>` names this list accepts. */
  filters?: string[];
  /** The states `f.state` accepts — `OPEN_STATES`, the worklist's own window.
   *  `activated` and `cancelled` are NOT here: they are outside the list, so
   *  offering either would be a control that always answers "none". */
  states?: WorklistFilterState[];
}

export const CONNECTION_LIST_FILTERS = ["state"] as const;

export interface ConnectionListQuery {
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
 * `GET /connections` — S86's only endpoint.
 *
 * ⛔ **NO `segment` PARAMETER IS ACCEPTED BY THIS WRAPPER, AND THAT IS THE
 * POINT.** The server serves `all` and refuses everything else by name
 * (OQ-371, OPEN). A wrapper that took a segment would let a screen discover the
 * refusal by CALLING it; the refusal is already in `unavailable` on every
 * response, in words the screen can render on the disabled tabs. When OQ-371
 * closes, the parameter arrives here with the segments it is allowed to send.
 *
 * ⚠ **`f.state` IS NOT `?segment=`, AND THAT IS WHY IT COULD BE BUILT WHILE
 * `OQ-371` STAYS OPEN (CR-045 wave G, `DEF-1702`).** A SEGMENT is an exclusive
 * partition — every row belongs to exactly one tab — so `CON-26-0126`, which
 * is `partly_activated` AND waiting, forces a precedence nobody has ruled. A
 * FILTER is a predicate: *does this row's stored `state` equal X*. It claims
 * nothing about the rows it excludes, needs no ranking, and hides nothing —
 * so it is answerable today. `?segment=` still refuses everything but `all`.
 *
 * `sort`/`dir` are likewise absent: B18 §5.4.2 fixes the order — *"Sorted by
 * target date, soonest first"* — and the server accepts no sort param, so a
 * sort control would offer an ordering the request cannot ask for.
 */
export async function listConnections(
  query: ConnectionListQuery = {},
  client: ApiClient = api,
): Promise<ConnectionList> {
  return requireData(
    await client.get<ConnectionList>("/connections", {
      query: {
        q: query.q === undefined || query.q === "" ? undefined : query.q,
        page: query.page,
        per: query.per,
        // `BR-CUS-1046` — the chosen ordering, so it reaches the `ORDER BY` and
        // survives a refresh in the URL rather than living only in component
        // state (the rule's own second clause).
        sort: query.sort,
        dir: query.dir,
        ...worklistFilterParams(query.filters, CONNECTION_LIST_FILTERS),
      },
    }),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// S89 · `GET /transfers` — B18 §5.7, one job and not two
// ══════════════════════════════════════════════════════════════════════════

export const TRANSFER_LINE_DEPOSIT = "deposit_carried";
export const TRANSFER_LINE_ARREAR = "arrear_follows";

/**
 * One line of B18 §5.7.2's stacked `MONEY` cell.
 *
 * ⚠ **A LINE MAY CARRY NO FIGURE, AND THAT IS WHY `lines` EXISTS BESIDE
 * `sentences`.** `MoneyStatement.sentences` emits a sentence only when its
 * figure is readable, so an account holding $150.00 whose BR-CUS-057 interest
 * cannot be read produces NO deposit sentence — indistinguishable, once
 * rendered, from an account with no deposit at all. The LINE is emitted either
 * way with `text: null`, `amount: {stored: null, display: null}` and the
 * absence attached. **The screen renders the absence; it never renders
 * `$0.00`, and it never shows the principal in place of an unreadable
 * interest figure.**
 *
 * `tone` is DATA, not a caption: §5.7.2 draws the arrear sentence in **amber**,
 * so B14's colour decision is made once, in the design, rather than re-derived
 * by every renderer.
 */
export interface TransferMoneyLine {
  kind: string;
  tone: string;
  text: string | null;
  amount: WorklistMoney;
  unavailable: WorklistAbsence | null;
}

/**
 * B18 §5.7.2's `MONEY` cell.
 *
 * ⚠ **NO MONEY MOVES IN A TRANSFER AND THE CELL MUST NOT SUGGEST OTHERWISE.**
 * `unavailable` names up to five reasons on one row — the transfer money rule
 * does not exist, the deposit has no carry path, the arrear has no posting
 * path, the balance is the cached AR figure, and the deposit interest cannot be
 * read. They are the writer lane's own sentences, carried verbatim.
 */
export interface TransferMoneyCell {
  currency: string;
  lines: TransferMoneyLine[];
  /** §5.7.2's own rendering for a screen that wants the strings only. SHORTER
   *  than `lines` whenever a figure could not be read — which is exactly why
   *  `lines` is the thing this screen renders. */
  sentences: string[];
  gaps: string[];
  unavailable: WorklistAbsence[];
}

/**
 * One S89 row: `FROM ACCOUNT · CUSTOMER · FROM → TO · OUT DATE · IN DATE ·
 * STEP (of 5) · MONEY · STATE`.
 *
 * ⚠ **`from_cell` IS THE SERVER'S TWO LINES, DASH INCLUDED.** TC-TRF-2: *"a
 * transfer at step 1 → `→ —` in the FROM ACCOUNT cell, not a blank"*, and
 * `transfers._serialize` writes that literal because *"a blank second line and
 * an absent one are indistinguishable once rendered"*. The screen prints the
 * two strings and produces no dash of its own.
 */
/** The stated absence a number cell renders instead of a blank or a dash.
 *
 * ⚠ **`detail` IS THE SERVER'S SENTENCE AND THE SCREEN NEVER WRITES ITS OWN.**
 * The reason a record has no reference is a fact about the tenant's numbering
 * setup, and only the writer knows it. `open_question` travels as a `data-`
 * attribute, never inside the sentence (DEF-332 — our internal ids mean
 * nothing to a billing clerk). */
export interface NumberUnavailable {
  code: string;
  series: string;
  open_question: string;
  detail: string;
}

export interface TransferRow {
  id: string;
  /** CR-039 wave D task 15 — the reference a clerk quotes down a phone.
   *  **`null` on every row until `OQ-426` closes**, because no `transfer`
   *  number series exists: B18 §5.7 draws no number, so nothing may invent
   *  its format. `transfer_no_unavailable` carries the reason. */
  transfer_no: string | null;
  transfer_no_unavailable: NumberUnavailable | null;
  state: string;
  step: number;
  step_of: number;
  step_label: string | null;
  /** `"3 of 5"`, built from the writer's own `STEP_COUNT`. */
  step_cell: string;
  customer_id: string;
  /** The SELLER, for good since 2026-09-20 (migration 0060). Never the buyer. */
  customer: string;
  customer_no: string;
  /** `DEF-CUS-6462` — who BOUGHT it, and its customer number. `null` until the
   *  sale commits. Optional because a parked-draft row carries neither. */
  buyer?: string | null;
  buyer_no?: string | null;
  from_account_id: string;
  from_account_no: string;
  to_account_id: string | null;
  to_account_no: string | null;
  /** Exactly two strings: `A-10650` and `→ A-11940`, or `→ —` before the new
   *  account exists. */
  from_cell: string[];
  to_unit_id: string | null;
  from_to: {
    from: string | null;
    to: string | null;
    to_absence: { reason: string } | null;
  };
  out_date: string | null;
  in_date: string | null;
  same_day: boolean | null;
  deposit_carry_elected: boolean;
  arrears_follow_elected: boolean;
  committed_at: string | null;
  cancelled_at: string | null;
  money: TransferMoneyCell;
  moving_this_week: boolean;
  /** ⚠ **`DEF-CUS-5994` (PO 2026-09-20) — THE DRAFT'S OWN FIELDS.** A parked
   *  wizard is a ROW of this list now; it was drawn on a pinned panel above the
   *  table until that day. `park_id` is `null` on a record row, and it is both
   *  the key `getRowId` uses and the handle `resumePath` builds `?parked=<id>`
   *  from — B14 rule 31 keeps it off the screen. The rest are the parked facts
   *  the panel carried, and **none of them is anywhere else**: `parked_by_name`
   *  in particular is what `CR-035` amendment 1 put in place of the
   *  mine/everyone's toggle it dissolved. */
  park_id?: string | null;
  row_kind?: string;
  park_note?: string | null;
  remind_on?: string | null;
  parked_at?: string | null;
  age_days?: number | null;
  parked_by_name?: string | null;
  /** What the clerk said they are waiting for — free text, and EMPTY means a
   *  draft they simply left rather than a park with no reason
   *  (`WizardPark.waiting_on`'s own rule). `null` on a record row. */
  waiting_on?: string | null;
}

export interface TransferKpis {
  open: number;
  moving_this_week: number;
  deposits_carrying: number;
  arrears_following: number;
  completed_this_month: number;
  /** Named rather than assumed: no rule states which clock a KPI window reads. */
  period_basis: string;
  as_of: string;
}

export interface TransferList {
  rows: TransferRow[];
  kpis: TransferKpis;
  page: number;
  per: number;
  total: number;
  pages: number;
  columns: string[];
  steps: { step: number; label: string }[];
  search: {
    hint: string;
    min_chars: number;
    legs: string[];
    /** ⛔ `request #` is one of four drawn search legs and the `transfers`
     *  table carries no service-request column (measured 2026-08-25). */
    unavailable: WorklistAbsence[];
  };
  /** §5.7.3's counting contract, published rather than restated. */
  exclusion: {
    callout: string;
    contract: string[];
    half_account_ids: string[];
  };
  /** CR-045 wave D · D.12 — the `f.<name>` names this list accepts. */
  filters?: string[];
  /** `Transfer.STATES` minus `cancelled`, which `list_queryset` excludes from
   *  the list itself — an option that can never return a row is a control
   *  reporting "none" for a reason the user cannot see. */
  states?: WorklistFilterState[];
  as_of: string;
}

export const TRANSFER_LIST_FILTERS = ["state"] as const;

export interface TransferListQuery {
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

/** `GET /transfers` — S89's list. `AdminOrClerk`, narrower than A4's Executive
 *  VIEW, because the MONEY cell is the statement `transfers.money_statement`
 *  itself gates to System Admin and Billing Clerk. */
export async function listTransfers(
  query: TransferListQuery = {},
  client: ApiClient = api,
): Promise<TransferList> {
  return requireData(
    await client.get<TransferList>("/transfers", {
      query: {
        q: query.q === undefined || query.q === "" ? undefined : query.q,
        page: query.page,
        per: query.per,
        // `BR-CUS-1046` — the chosen ordering, so it reaches the `ORDER BY` and
        // survives a refresh in the URL rather than living only in component
        // state (the rule's own second clause).
        sort: query.sort,
        dir: query.dir,
        ...worklistFilterParams(query.filters, TRANSFER_LIST_FILTERS),
      },
    }),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// S90 · `GET /disconnects` — B18 §5.8, the ladder and its protections
// ══════════════════════════════════════════════════════════════════════════

/** The only segment served. The other five refuse — OQ-374, OPEN. */
export const DISCONNECT_SEGMENT_ALL = "all";

export interface DisconnectChip {
  code: string;
  label: string;
  /** `ink` · `accent` (TIER 3) · `grey` (the three HELD chips). Tone is DATA so
   *  B14's colour decision is made once, in the design. */
  tone: string;
}

/**
 * B18 §5.8.2's `TIER` cell.
 *
 * ⚠ **`chips` IS A LIST AND THAT IS NOT DECORATION.** B18 draws ONE chip per
 * row; the product can produce two — §5.8.3's ladder draws `T1 · T2 · T3 -.->
 * HOLD`, so a customer at TIER 2 who files a medical certificate has both a
 * tier reached and a protection in force. Which one wins in a single cell is
 * stated by no rule (OQ-374), so every applicable chip is served in the drawn
 * order, `ambiguous` is flagged, and NOTHING is dropped: dropping one would
 * hide a protection from a screen that authorises a cut.
 *
 * An EMPTY `chips` with an `unavailable` entry is B18's `—`, and it has two
 * causes a screen must be able to tell apart: `no_tier_reached` (nothing has
 * been sent) and `unmapped_rung` (payments' `second_5_day`, which B18 draws no
 * chip for).
 */
export interface DisconnectTierCell {
  chips: DisconnectChip[];
  ambiguous: boolean;
  unavailable: WorklistAbsence[];
}

/**
 * B18 §5.8.2's `LAST NOTICE`.
 *
 * ⛔ **`delivery_state` IS NULL ON EVERY ROW AND MUST NEVER BE RENDERED AS A
 * DELIVERY CLAIM.** B18's own warning: *"There is no email, SMS or print
 * adapter in this release … This column is drawn against a capability that
 * does not exist, and a lane must render the absence rather than fabricate a
 * delivery state."* The two FACTS — which tier, and the date it was issued —
 * are served and are the only things this cell may say. TC-DSC-6.
 */
export interface DisconnectLastNotice {
  issued_on: string | null;
  tier: string | null;
  delivery_state: string | null;
  unavailable: WorklistAbsence;
}

/**
 * B18 §5.8.2's `OWED` — the ledger's figure, or its stated absence.
 *
 * ⚠ **`display: null` MEANS THE READING FAILED, NOT ZERO** (DEF-127): a
 * fabricated `$0.00` *"looks exactly like a settled account"*, and on this tab
 * it looks like an account nobody should be chasing.
 */
export interface DisconnectOwed {
  stored: string | null;
  display: string | null;
  currency: string | null;
  source: string | null;
  unavailable: WorklistAbsence[] | null;
}

/**
 * B18 §5.8.2's `STATE` — BOTH axes, and never a silent winner.
 *
 * `On hold` is COMPUTED from the account's protections; `notice_sent`,
 * `scheduled`, `cut` and `reconnecting` are the STORED case state. A row can be
 * both, and `one_cell_is_unresolved` marks it (OQ-374). §5.8.6's nine drawn
 * rows all have exactly one of the two, so the drawn screen renders unchanged.
 */
export interface DisconnectStateCell {
  stored: string | null;
  held_by: string[];
  one_cell_is_unresolved: boolean;
  unavailable: WorklistAbsence | null;
}

/**
 * WHEN a booked cut is due, and whether it has already happened.
 *
 * `status` is one of `overdue` · `due_today` · `ahead` · `no_date` · `done`.
 * **`done` means the supply is already off or a reconnection visit is owed**,
 * and the date on that row is the record of WHEN rather than a plan — reading
 * it as late is `DEF-CUS-6055`, which is the defect this whole block answers.
 *
 * `days_overdue` is CALENDAR days and is `null` unless `status` is `overdue`.
 */
export interface DisconnectCutDue {
  status: string;
  days_overdue: number | null;
  /** The business day it was decided against, so a cached page cannot claim a
   *  freshness it does not have. */
  as_of: string;
  /** Present only on a parked draft, which has no case and therefore no date. */
  unavailable?: WorklistAbsence;
}

export interface DisconnectRow {
  account_id: string;
  /** CR-039 wave D task 16 — the reference a clerk reads back to a customer
   *  holding a disconnection notice. **`null` on every row today**, for one of
   *  TWO reasons the cell must not merge: `OQ-427` (no series exists, so the
   *  case is unnumbered) or `no_case_opened` (a protection row — no case was
   *  ever opened, so there is nothing to number). `case_no_unavailable` says
   *  which, and it is the server's sentence in both cases.
   *
   *  ⚠ Lifted OUT of `case` deliberately: that field is documented below as an
   *  opaque record no screen reads a field from, and this is the one field a
   *  screen must. */
  case_no: string | null;
  case_no_unavailable: NumberUnavailable | { code: string; detail: string } | null;
  account_no: string;
  customer: string | null;
  address: string | null;
  unit_id: string;
  owed: DisconnectOwed;
  tier: DisconnectTierCell;
  cut_date: string | null;
  /** §5.8.2: *"`CUT DATE` renders in the **accent** when it is this week"* —
   *  the accent is a FACT about the date, served as data.
   *
   *  ⚠ **FORWARD-LOOKING ONLY**, by `_within_the_week`'s own docstring: a cut
   *  whose date has PASSED is not in it. `cut_due` below is the other half. */
  cut_date_is_this_week: boolean;
  /**
   * ⚠ **PO 2026-09-20 — *"A case due last week stops looking identical to one
   * due next month."*** The second fact about the same date, and it is not a
   * second calendar: both are computed by the server, from
   * `apps/customers/disconnect_due.py`, which is also what `f.due` filters on
   * and what the nightly cut-date watch reads. One predicate, three readers —
   * `DEF-CUS-6055`'s own remedy, which is that a tile and the list it opens
   * must be counted the same way.
   *
   * OPTIONAL, so a deployment whose server predates the field renders the
   * plain date it renders today rather than `undefined`.
   */
  cut_due?: DisconnectCutDue;
  last_notice: DisconnectLastNotice;
  state: DisconnectStateCell;
  ladder: {
    runs: boolean;
    halt_code: string | null;
    detail: string;
    sequence: string;
    scheduler: WorklistAbsence & { advances_on_a_schedule: boolean };
  };
  protections: {
    kind: string;
    lifetime: string;
    in_force: boolean;
    effective_from: string | null;
    expires_on: string | null;
    reason: string | null;
  }[];
  /**
   * `disconnects.case_payload(case)`, or null for a row that is on this tab
   * because of a PROTECTION and never entered the ladder (§5.8.6's three HELD
   * rows).
   *
   * ⚠ **TYPED AS AN OPAQUE RECORD ON PURPOSE.** Nothing on S90 renders a field
   * from it — the case DETAIL screen does not exist in this application — and
   * typing its twenty fields here would be twenty claims about a shape no
   * screen reads and no test could keep honest. It is declared because the
   * server sends it, so a fixture that mirrors the payload compiles.
   */
  case: Record<string, unknown> | null;
  /**
   * ⚠ **`DEF-CUS-6749` (2026-09-25) — THE CREW'S LAST ATTENDANCE, AND THE LIST
   * READ NO VISIT AT ALL BEFORE THIS.** `apps/customers/disconnect_visits.py`
   * has held four outcomes since `BR-CUS-1083` and `disconnect_reads.py`
   * contained **zero references to it**. Three of the four CLEAR the cut date
   * and return the case to `notice_sent` — a real, correct state — so a case a
   * crew drove to and could not cut rendered IDENTICALLY to one nobody has
   * ever visited: same word, same empty cut date, nothing for a check to see.
   *
   * `null` means **no attendance is recorded**, which is not the same claim as
   * *nobody went*. The screen states the first and never the second.
   *
   * ⚠ **OPTIONAL, so a deployment whose server predates the field compiles and
   * renders exactly what it rendered before** — the posture `dues` took on the
   * same payload (`DEF-782`).
   */
  visit?: {
    /** One of `BR-CUS-1083`'s four: `locked_gate` · `access_refused` ·
     *  `paid_at_door` · `disputed`. The set is CHECK-constrained server-side. */
    outcome: string;
    /** The day the crew attended — the clerk's own date, never defaulted to
     *  today by the writer, because a failed visit is often recorded the
     *  following morning. */
    visited_on: string;
    /** True for the three outcomes that send the case back to `notice_sent`.
     *  Served rather than derived here: one rule, one place. */
    clears_the_cut_date: boolean;
  } | null;
  /** ⛔ OQ-366 — NO row names a chased party. `subject` is null on every row and
   *  a collections-sequence row says so out loud rather than by omission. */
  subject: null;
  chase_subject_unresolved: WorklistAbsence | null;
  /** ⚠ **`DEF-CUS-5994` (PO 2026-09-20) — THE DRAFT'S OWN FIELDS.** A parked
   *  wizard is a ROW of this list now; it was drawn on a pinned panel above the
   *  table until that day. `park_id` is `null` on a record row, and it is both
   *  the key `getRowId` uses and the handle `resumePath` builds `?parked=<id>`
   *  from — B14 rule 31 keeps it off the screen. The rest are the parked facts
   *  the panel carried, and **none of them is anywhere else**: `parked_by_name`
   *  in particular is what `CR-035` amendment 1 put in place of the
   *  mine/everyone's toggle it dissolved. */
  park_id?: string | null;
  row_kind?: string;
  park_note?: string | null;
  remind_on?: string | null;
  parked_at?: string | null;
  age_days?: number | null;
  parked_by_name?: string | null;
  /** What the clerk said they are waiting for — free text, and EMPTY means a
   *  draft they simply left rather than a park with no reason
   *  (`WizardPark.waiting_on`'s own rule). `null` on a record row. */
  waiting_on?: string | null;
}

export interface DisconnectKpis {
  at_notice: number;
  due_to_cut_this_week: number;
  on_hold_protected: number;
  cut_awaiting_payment: number;
  /** §5.8.1 draws this tile's caption as *"still accruing base charges"*.
   *  **SUPERSEDED (BR-CUS-103, PO 2026-08-25 → base charges STOP at the cut).**
   *
   *  ⚠ This comment read *"a BILLING claim this packet does not rule"* until
   *  2026-08-25 and that was true when written (DEF-716): the caption is now
   *  withheld because it is FALSE, not because it is unverified. The absence
   *  the server sends carries the code `cut_accrual_caption_superseded`. */
  cut_awaiting_payment_unavailable: WorklistAbsence;
  reconnections_due: number;
  as_of: string;
}

export interface DisconnectSegment {
  code: string;
  label: string;
  supported: boolean;
  unavailable: WorklistAbsence | null;
}

export interface DisconnectList {
  rows: DisconnectRow[];
  kpis: DisconnectKpis;
  page: number;
  per: number;
  total: number;
  pages: number;
  columns: string[];
  segment: string;
  /** All six, each carrying `supported` and — for the five that are not — the
   *  reason, so the screen disables them by name and never calls the route to
   *  discover the refusal. */
  segments: DisconnectSegment[];
  /** CR-045 wave D · D.8 — the `f.<name>` names this list accepts. */
  filters?: string[];
  /** The STORED `disconnect_cases.state` codes `f.state` accepts —
   *  `CASE_STATES` minus the ones `open_cases` excludes, because a state that
   *  takes the row OFF this list can never be a useful option here.
   *  ⚠ **NOT the six drawn SEGMENTS.** `on_hold` is COMPUTED from the
   *  account's protections and is not a stored state at all; the segments are
   *  the unruled question (OQ-374), these are the column. */
  states?: WorklistFilterState[];
  /** ⚠ **PO 2026-09-20 — the `f.due` vocabulary, SERVED AND NEVER TYPED
   *  (`BR-SHL-010`).** A second DIMENSION beside `states`, not a second
   *  spelling of it: `state` asks what has been decided about a case, `due`
   *  asks whether its date has arrived. The two compose. */
  dues?: WorklistFilterState[];
  /** The applied `f.due`, echoed so a chip can light from the response. */
  due?: string;
  chips: DisconnectChip[];
  /**
   * ⚠ **`CR-125-BRC07` — THE HEAD'S THIRD FRAGMENT, SERVED 2026-09-20.**
   * p142 draws the sub-line `10 tabs · Disconnects · 3 open cases`; until this
   * arrived nothing could supply the number and the fragment was OMITTED
   * rather than zeroed (`DEF-CUS-5953`).
   *
   * ⚠ **IT IS NOT `total`.** `total` counts this list's ROWS, and those rows
   * are a UNION of open cases and accounts carrying a protection — an account
   * on a medical hold with no case raised is a row and is not an open case.
   * Serving `total` under the words *open cases* would overstate, on the tab
   * that authorises cutting people off.
   *
   * OPTIONAL, so a deployment whose server predates the field renders the
   * two-fragment line it renders today rather than `undefined open cases`.
   */
  open_case_count?: number;
  search: { hint: string; legs: string[] };
  delivery: WorklistAbsence;
  scheduler: WorklistAbsence & { advances_on_a_schedule: boolean };
  as_of: string;
}

/**
 * The `f.<name>` dimensions this list sends. ⚠ **`worklistFilterParams` DROPS
 * anything not named here**, so a dimension the server accepts and this tuple
 * omits is a control that looks live and narrows nothing — `tsc` passes and
 * every test passes, because the request is well formed and simply carries no
 * filter. `due` joined it on 2026-09-20 with the server's own
 * `DISCONNECT_FILTERS`; a test asserts the pair.
 */
export const DISCONNECT_LIST_FILTERS = ["state", "due"] as const;

export interface DisconnectListQuery {
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
 * `GET /disconnects` — S90's list.
 *
 * ⛔ **NO `segment` PARAMETER, for `listConnections`' reason.** The five
 * unserved segments come back on every response with `supported: false` and the
 * sentence to draw on them; asking for one would return a catalogue refusal
 * (`customers.disconnects.segment.unavailable`) and leave the tab empty, which
 * is the "call the route to find out" the payload exists to prevent.
 *
 * ⚠ **`f.state` IS SERVED AND `?segment=` IS NOT, AND THE DIFFERENCE IS EXACTLY
 * WHY (CR-045 wave G, `DEF-1702`).** The six drawn segments are not mutually
 * exclusive — `On hold` is computed from the account's protections while the
 * rest are the stored case state — and *no rule ranks them* (OQ-374). A filter
 * asks *does this row's stored `state` equal X*, which needs no ranking, no
 * exclusivity and no precedence, and hides nothing.
 */
export async function listDisconnects(
  query: DisconnectListQuery = {},
  client: ApiClient = api,
): Promise<DisconnectList> {
  return requireData(
    await client.get<DisconnectList>("/disconnects", {
      query: {
        q: query.q === undefined || query.q === "" ? undefined : query.q,
        page: query.page,
        per: query.per,
        // `BR-CUS-1046` — the chosen ordering, so it reaches the `ORDER BY` and
        // survives a refresh in the URL rather than living only in component
        // state (the rule's own second clause).
        sort: query.sort,
        dir: query.dir,
        ...worklistFilterParams(query.filters, DISCONNECT_LIST_FILTERS),
      },
    }),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE TWO ENVELOPE READERS — see this file's header for why they exist
// ══════════════════════════════════════════════════════════════════════════

/** The page's rows, whichever envelope the server sent. */
export function rowsOf<Row>(payload: { results: Row[] } | { rows: Row[] } | undefined): Row[] {
  if (payload === undefined) {
    return [];
  }
  return "results" in payload ? payload.results : payload.rows;
}

/** The server's total, or `null` until the first response — which is what
 *  `DataTable` wants for its pager, and the reason this is not `?? 0`: a zero
 *  total renders "0 of 0" over a list that has not answered yet. */
export function totalOf(payload: { count: number } | { total: number } | undefined): number | null {
  if (payload === undefined) {
    return null;
  }
  return "count" in payload ? payload.count : payload.total;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W6 task 6.12 · W7 tasks 7.4 / 7.11 — B18 §5.4 · §5.7 · §5.8 ·
//         `apps/metering/connection_reads.py` · `apps/customers/transfer_reads.py`
//         · `apps/customers/disconnect_reads.py` · OQ-371 · OQ-374 · OQ-366 ·
//         CR-032 (`activated`, not `energised`)
// generated: 2026-08-25 by lane F-TABS (the frontend half of the three worklists)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E3 no `segment` parameter on either wrapper that has unserved
//         segments — the refusals ride on the payload and the screen disables
//         the tabs by name (OQ-371 / OQ-374 are OPEN, and calling the route to
//         learn that is the thing `unavailable` exists to prevent) · E3 the two
//         envelope shapes are carried as they are and read through
//         `rowsOf`/`totalOf`; normalising them here would put a second opinion
//         about the contract in the client · E3 no story owns S86, S89 or S90
//         (hard-won law 8) — three backend files filed the same finding and it
//         is REPORTED again here, not invented
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
