// ── Trace ──────────────────────────────────────────────
// Change:   **BR-CUS-1083 + the reconnection doors (PO 2026-09-20)** — *"The
//           other half of the job. Today a utility can cut supply and cannot
//           restore it from the product."* and *"The register reflects reality.
//           Today a failed visit is invisible and the case looks untouched."*
//           Three writes join this file: `mark_reconnecting`, `restore_service`
//           (both mounted since 2026-08-25 and called by NOTHING until today)
//           and `record_visit` (new). ⚠ **NEITHER IS DRAWN ANYWHERE** — see
//           `reconnectPath` below.
// Change:   CR-125-BRC07 — THE DISCONNECT CASE RECORD, blueprint
//           `02 Accounts Menu Blueprint.pdf` p143, with its two dialogs on
//           p144 (hold) and p145 (mark as cut). The page's own red banner
//           reads *"TODAY: no disconnect case page exists"* — no route, no
//           component, no endpoint — so this is a screen that has never
//           existed rather than one being changed.
// Rules:    B14 rule 31 (the record is addressed by CASE NUMBER, never a uuid)
//           · rule 43 (a piece of UI is a COMPONENT — the test is
//           ADDRESSABILITY, which is why the wire shape, the three actions and
//           the four panels are separate modules rather than one page file) ·
//           CLAUDE.md rule 2 (money travels as a STRING and displays at 2)
// ───────────────────────────────────────────────────────
/**
 * What `GET /disconnects/{ref}` owes this screen, and the two writes it reaches.
 *
 * ⚠ **THE TYPES ARE DECLARED HERE AND NOT IN THE PAGE**, so a panel can be
 * imported and tested without importing the page — B14 rule 43's test is
 * addressability, and a type that lives in a 900-line screen file drags the
 * screen into every test that names it.
 *
 * ⚠ **THE TWO WRITES ARE ENDPOINTS THAT ALREADY EXIST AND ARE CALLED BY
 * NOTHING.** `POST /accounts/{id}/protections` and
 * `POST /accounts/{id}/disconnect-case/cut` were both built, role-gated and
 * tested on 2026-08-25 and have had no door since. This screen is their first
 * caller — which is hard-won law 2 read from the engine end.
 */
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

/** A1's screen id — p143 is the record behind S90's register. */
export const DISCONNECT_RECORD_SCREEN = "S90.disconnectRecord";

/**
 * The record's address — **`/disconnects/{ref}`, beside `/disconnects/new`
 * and never under `/accounts/`**.
 *
 * The blueprint's own URL is `/brazosbend/disconnects/dsc-26-0003`. The
 * placement follows the transfer record's, and for the reason that one states:
 * a disconnection is a record of an act the utility is taking against an
 * account, not a sub-page OF the account — and the wizard it belongs beside is
 * already top-level because it FINDS its account as step 1.
 *
 * ⚠ **`:ref` IS THE CASE NUMBER AND NEVER A UUID** (B14 rule 31). `DSC-26-0003`
 * is what a clerk reads back to a customer holding a disconnection notice.
 * `OQ-427` closed on 2026-08-27 — PO verbatim, *"it needs its own series"* —
 * so `core/numbering.py` carries the `disconnect_case` series and a case opened
 * on a provisioned tenant has one.
 */
export function disconnectRecordPath(reference: string): string {
  return `/disconnects/${encodeURIComponent(reference)}`;
}

export const DISCONNECT_RECORD_ROUTE = "/disconnects/:ref";

// ══════════════════════════════════════════════════════════════════════════
// THE WIRE SHAPE
// ══════════════════════════════════════════════════════════════════════════
/**
 * Why a fact is missing.
 *
 * `code` and `detail` are the two fields every absence in this product
 * carries; `br_ref` rides on most and is optional here rather than required,
 * because a type demanding one would force this screen to fabricate a rule id
 * for a real server payload (`TransferRecordPage`'s own reasoning for the same
 * choice).
 */
export interface DisconnectAbsence {
  code: string;
  detail: string;
  br_ref?: string;
  tracks?: string | null;
}

/**
 * One label→value cell: a value, OR the reason there is none.
 *
 * ⚠ **NEVER BOTH AND NEVER NEITHER.** The type cannot express that, so the
 * server enforces it (`disconnect_record._fact`) and
 * `test_disconnect_record_page.py` asserts it recursively over the whole
 * payload. What this file guarantees is that BOTH arms are drawn.
 */
export interface DisconnectFact<T = string> {
  value: T | null;
  unavailable: DisconnectAbsence | null;
}

/**
 * A money cell.
 *
 * ⚠ **`stored` IS 4 DECIMALS AND `display` IS 2** (CLAUDE.md rule 2), both as
 * STRINGS. Nothing here parses either into a number: a float is how a ledger
 * and a screen come to disagree about a cent.
 */
export interface DisconnectMoney {
  stored: string | null;
  display: string | null;
  currency: string | null;
  unavailable: DisconnectAbsence | null;
}

/** One row of p143's `NOTICES SENT` — §3 of the server module: TWO columns. */
export interface DisconnectNoticeRow {
  /** A stored tier CODE, translated on screen (B14 rule 31). */
  tier: string;
  issued_on: string;
  /** The PROOF-of-service channel, null until a person attests. Never a send. */
  channel: string | null;
  proved: boolean;
}

/** One row of p143's `PROTECTIONS CHECKED`. */
export interface DisconnectProtectionRow {
  check: string;
  /** ⚠ **THREE-VALUED, AND `unavailable` IS NOT `pass`.** The drawn *disputed
   *  bill* row answers `unavailable` because nothing stores a disputed AMOUNT,
   *  and a green clearance there would be fabricated on the screen that
   *  authorises a cut. */
  outcome: "pass" | "fail" | "unavailable";
  reason: string;
}

/** One row of p144's `WHAT HOLDING WILL DO`. */
export interface DisconnectHoldEffect {
  when: "now" | "not_now";
  code: string;
}

export interface DisconnectCutBlocker {
  code: string;
  br_ref: string;
  detail: string;
}

/**
 * One reason a reconnection step cannot be taken, **in the server's own words**.
 *
 * ⚠ **THE SENTENCE IS NEVER RESTATED ON THIS SIDE.**
 * `disconnects.reconnect_blockers` holds the three refusals and
 * `mark_reconnecting` RAISES them, so the sentence beside a greyed button and
 * the sentence a refused call carries are the same string. A paraphrase here
 * would be a second answer to a question the writer already answers.
 */
export interface DisconnectReconnectBlocker {
  code: string;
  br_ref: string;
  detail: string;
}

/** `GET /disconnects/{ref}` → `actions.reconnect` — the way back. */
export interface DisconnectReconnectPanel {
  /** `mark_reconnecting` · `restore_service` · `null` when there is no case. */
  step: "mark_reconnecting" | "restore_service" | null;
  ready: boolean;
  refusal: DisconnectReconnectBlocker | null;
  blockers: DisconnectReconnectBlocker[];
  /** ⚠ **TRUE, AND NOT A REASON THE BUTTON IS GREY** — `BR-CUS-1097`, PO
   *  2026-09-25. `not_settled` was a blocker until that day and is
   *  `money_still_owed` here now. `ready` does not read this array; a screen
   *  that greyed a control on it would be the refusal restored under another
   *  name. Optional so an older server renders unchanged. */
  warnings?: DisconnectReconnectBlocker[];
  /**
   * What the GATE reads — **not** the quote.
   *
   * ⚠ **TWO NUMBERS, AND THEY ANSWER DIFFERENT QUESTIONS.** `to_clear` is
   * what the customer was QUOTED (arrears + fee, `BR-CUS-104`); this is the
   * live balance `mark_reconnecting` compares against zero. A clerk reading a
   * refusal needs to know which one refused them.
   */
  balance: DisconnectMoney | null;
  /** A stored status CODE, translated on screen (B14 rule 31). History only
   *  since 2026-10-29 — a restoration writes Active (`DEF-CUS-10668`). */
  status_before_cut: string | null;
  /** The status `restore_service` writes — `active` (`DEF-CUS-10668`). */
  status_restored_to?: string;
  /** Set only when the tenant has no live `active` status to write. */
  status_absence: DisconnectAbsence | null;
  to_clear: DisconnectMoney & { arrears?: unknown; fee?: unknown; total?: unknown };
  fee: { stored: string; display: string } | null;
  fee_absence: DisconnectAbsence | null;
  deposit: {
    on_file: { stored: string; display: string } | null;
    election: string | null;
    new_deposit_required: boolean | null;
    detail: string;
  } | null;
  cut_on: string | null;
  reconnected_on: string | null;
  visit: DisconnectAbsence;
}

/** One of `BR-CUS-1083`'s four outcomes, with WHERE it sends the case. */
export interface DisconnectVisitOption {
  code: string;
  move: "clears_the_cut_date" | "stops_the_ladder";
}

/** One attendance already recorded on this case. */
export interface DisconnectVisitRow {
  visit_id: string;
  visited_on: string;
  outcome: string;
  note: string | null;
  clears_the_cut_date: boolean;
}

/** `GET /disconnects/{ref}` → `actions.visit`. */
export interface DisconnectVisitPanel {
  outcomes: DisconnectVisitOption[];
  /** ⛔ **A VISIT IS RECORDED ON A SCHEDULED CASE AND NOWHERE ELSE.** */
  can_record: boolean;
  refusal: DisconnectAbsence | null;
  recorded: DisconnectVisitRow[];
  follow_up: DisconnectAbsence;
  money: DisconnectAbsence;
}

/** `GET /disconnects/{ref}` → `work_orders` — the cut visits this case raised
 *  (`DEF-CUS-9696`), counted and numbered by Work. */
export interface DisconnectCaseVisits {
  raised: number;
  done: number;
  accepted: number;
  orders: readonly { order_no: string; state: string; done: boolean; accepted: boolean }[];
}

/** One read meter on a service the case cuts (`closing_read_meters`). The
 *  NUMBER, never an id (B14 rule 31); the unit travels with it (hard rule 3). */
export interface ClosingReadMeter {
  asset_no: string;
  service: string | null;
  kind: string | null;
  unit: string | null;
  last_read: { value: string | null; read_at: string | null } | null;
}

export interface DisconnectRecordDetail {
  case_no: DisconnectFact;
  customer_name: DisconnectFact;
  address: DisconnectFact;
  customer_class: DisconnectFact;
  /** A stored state CODE, translated on screen. */
  state: DisconnectFact;
  /** A stored tier CODE, translated on screen. */
  tier: DisconnectFact;
  cut_date: DisconnectFact;
  the_case: {
    account_no: DisconnectFact;
    owed: DisconnectMoney;
    /** ⛔ **NO SOURCE ANYWHERE** — see the server module's §2. */
    oldest_debt: DisconnectFact;
    tier: DisconnectFact;
    cut_date: DisconnectFact;
    opened_on: DisconnectFact;
    /** ⛔ **THE NAME HALF HAS NO SOURCE** — `disconnect_cases` has no actor
     *  column. The DATE half is `opened_on`, above. */
    raised_by: DisconnectFact;
  };
  notices: {
    rows: DisconnectNoticeRow[];
    state_column_unavailable: DisconnectAbsence;
    channel_column_empty: DisconnectAbsence | null;
    delivery: DisconnectAbsence;
  };
  protections: {
    as_of: string;
    checks: DisconnectProtectionRow[];
    all_clear: boolean;
  };
  /** `DEF-CUS-9696` — optional only so an older server still renders. */
  work_orders?: DisconnectFact<DisconnectCaseVisits>;
  /** `DEF-CUS-10657` — the reconnect REQUEST's jobs (PO C1 2026-10-29), served
   *  once the case is `reconnecting` or `restored`; `null`/absent before. */
  reconnect_work_orders?: DisconnectFact<DisconnectCaseVisits> | null;
  what_a_cut_would_do: {
    services_affected: DisconnectFact<string[]>;
    reconnection_fee: DisconnectMoney & { charge_code_configured: boolean };
    account_status_becomes: DisconnectAbsence;
    to_clear_before_reconnection: DisconnectMoney;
    base_charges: DisconnectAbsence;
    not_a_close_out: DisconnectAbsence;
    /**
     * ⚠ **THE CUT HAPPENED AND THE STATUS WAS HELD** — `DEF-CUS-6063` /
     * `DEF-CUS-6064`. Non-null ONLY on a case that is `cut` and whose account
     * never took `Disconnected`, which by construction means billing refused
     * the final bill for the days before the cut. The panel two rows above
     * promises *"Status becomes Disconnected"*; this is the server saying it
     * did not.
     *
     * ⛔ **IT CARRIES NO ENGINE SENTENCE AND THAT IS DELIBERATE.** The original
     * refusal survives only on an `audit_log` row and `audit_log` is pruned on
     * a retention schedule. The reason is produced FRESH when the clerk
     * presses `Finish disconnection`.
     */
    cut_unfinished: DisconnectAbsence | null;
    /**
     * ⚠ **THE DAYS NOBODY HAS BILLED — PO ruling 2026-09-21.** A cut may now
     * be COMPLETED with no final bill, and a `disconnected` account leaves the
     * bill run, so these days would otherwise stop being anywhere the moment
     * the status is written. Non-null while any day up to the cut date is
     * unbilled, on a FINISHED cut as well as a held one — the finished one is
     * the case this exists for.
     *
     * ⚠ **IT IS DERIVED SERVER-SIDE ON EVERY READ AND CLOSES ITSELF.** The day
     * billing's single-bill workflow raises the bill, `first_unbilled_day`
     * moves past the cut and this goes null with nobody clearing a flag.
     */
    days_not_billed?: (DisconnectAbsence & {
      from?: string;
      to?: string;
      days?: number;
    }) | null;
  };
  actions: {
    available: string[];
    /** NOT a visible value — the address the two writes post to (rule 31). */
    account_id: string;
    hold: {
      kinds: string[];
      review_date: Record<string, "required" | "refused">;
      dispute_unrecordable: DisconnectAbsence;
      effects: DisconnectHoldEffect[];
      promises_not_kept: DisconnectAbsence;
    };
    mark_as_cut: {
      ready: boolean;
      refusal: DisconnectCutBlocker | null;
      blockers: DisconnectCutBlocker[];
      /** ⚠ **TRUE, AND NOT A REASON THE BUTTON IS GREY** — `BR-CUS-1099`, PO
       *  2026-09-25. `cut_on_unrecorded_service` was a blocker until that day.
       *  `ready` does not read this array. Optional: an older server renders
       *  unchanged. */
      warnings?: DisconnectCutBlocker[];
    };
    /** `DEF-CUS-10166` — the meters the cut takes a closing reading for.
     *  Optional: an older server sends none and the dialog shows no rows. */
    closing_reads?: { meters: ClosingReadMeter[] };
    /**
     * ⚠ **OPTIONAL ON THE TYPE AND PRESENT ON EVERY LIVE PAYLOAD.** A server
     * that predates 2026-09-20 sends neither, and a required field here would
     * make the page crash on a stale deployment instead of simply not offering
     * the action — which is the failure this product least wants on a screen
     * that takes supply away.
     */
    reconnect?: DisconnectReconnectPanel;
    visit?: DisconnectVisitPanel;
  };
}

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/**
 * ⚠ **THE LEADING SLASH IS LOAD-BEARING** — `DEF-CUS-4010`. Without it
 * `apiPath` joins the tenant and the path with nothing between them and every
 * request goes to `/api/brazosbenddisconnects/…`: a 404 on every case,
 * invisible because a 404 and a stated absence look identical on screen.
 */
export async function readDisconnectRecord(
  reference: string,
  client: ApiClient = api,
): Promise<DisconnectRecordDetail> {
  return requireData(
    await client.get<DisconnectRecordDetail>(
      `/disconnects/${encodeURIComponent(reference)}`,
    ),
  );
}

/** The query key, exported so a test seeds the same one the page reads. */
export function disconnectRecordKey(reference: string): [string, string] {
  return ["disconnect-record", reference];
}

// ══════════════════════════════════════════════════════════════════════════
// THE TWO WRITES — both already mounted, both called by nothing until now
// ══════════════════════════════════════════════════════════════════════════
/**
 * p144's commit — `POST /accounts/{id}/protections`.
 *
 * ⚠ **`expires_on` IS REQUIRED FOR TWO KINDS AND REFUSED FOR THE THIRD**, and
 * those are the SERVER's rules rather than this screen's: a medical
 * certificate must carry the date it expires (*"a hold with no end date is a
 * permanent exemption nobody signed"*), a weather moratorium is a date WINDOW
 * and carries both ends, and a payment-plan protection takes none because
 * `BR-CUS-043` holds it while the plan is active and current. The payload's
 * `review_date` map is what the dialog reads, so the rule has one home.
 */
export async function holdDisconnectCase(
  accountId: string,
  body: { kind: string; effective_from: string; expires_on?: string | null; note?: string },
  client: ApiClient = api,
): Promise<unknown> {
  return client.post(`/accounts/${encodeURIComponent(accountId)}/protections`, body);
}

/**
 * p145's commit — `POST /accounts/{id}/disconnect-case/cut`.
 *
 * ⛔ **`final_reads` IS THE ONLY OPTIONAL FIELD AND `Who did it` IS NOT A
 * FIELD AT ALL.** p145 draws a `Who did it · Field crew · WO-26-0402` select
 * and `commit_cut` takes no such argument — there is no column on
 * `disconnect_cases` for it and no vocabulary for a crew outcome
 * (`disconnects.CREW_OUTCOME_UNRECORDABLE`, `OQ-383`). A select that cannot be
 * recorded is a dead control (hard-won law 2), so the dialog states the
 * absence instead of offering one.
 */
export async function markDisconnectCaseCut(
  accountId: string,
  body: { cut_on: string; final_reads?: unknown },
  client: ApiClient = api,
): Promise<unknown> {
  return client.post(
    `/accounts/${encodeURIComponent(accountId)}/disconnect-case/cut`,
    body,
  );
}

/** What `POST /accounts/{id}/disconnect-case/finish` answers. */
export interface DisconnectFinishResult {
  finished: boolean;
  account_status_written: string | null;
  /**
   * ⚠ **NULL WHEN THE REQUEST WAS COMPLETED WITHOUT A BILL** (PO ruling
   * 2026-09-21). No bill was asked for, so there is no engine answer to carry
   * — not an empty one.
   */
  cut_bill: {
    outcome: string;
    billed: boolean;
    invoice_no: string | null;
    total: string | null;
    currency: string | null;
    period_start: string | null;
    period_end: string | null;
    reason: string | null;
    /** The ENGINE's own sentence — what to fix, in the words billing wrote. */
    detail: string | null;
  } | null;
  account_status_held?: DisconnectAbsence;
  /** PO ruling 2026-09-21 — the days this completion left unbilled, or null. */
  days_not_billed?: (DisconnectAbsence & {
    from?: string;
    to?: string;
    days?: number;
  }) | null;
  completed?: DisconnectAbsence;
  settlement?: {
    outstanding: { stored: string | null; display: string | null } | null;
    currency: string | null;
  };
}

/**
 * The third commit — `POST /accounts/{id}/disconnect-case/finish`.
 *
 * **`DEF-CUS-6063`.** It raises the final bill a cut could not raise and writes
 * BR-CUS-107's status.
 *
 * ⚠ **`withoutBill` JOINED 2026-09-21 AND IT IS THE ONLY ARGUMENT THERE WILL
 * BE.** PO ruling: *"we will need to allow clark to complete the cut request
 * later without bill."* Completing the cut request and raising its final bill
 * are two acts, and only the clerk knows which one they are performing. Every
 * DATE and every FIGURE is still the server's: the window comes from the case's
 * own recorded cut date, the money comes from the engine, and a parameter for
 * either would be a clerk deciding how many days a customer pays for.
 *
 * ⚠ **A STILL-REFUSED BILL COMES BACK 200 WITH `finished: false`**, carrying
 * the engine's sentence. That is not an error — it is a configuration problem a
 * human fixes, and the sentence is the useful half of the answer.
 */
export async function finishDisconnectCut(
  accountId: string,
  client: ApiClient = api,
  withoutBill = false,
): Promise<DisconnectFinishResult> {
  return requireData(
    await client.post<DisconnectFinishResult>(
      `/accounts/${encodeURIComponent(accountId)}/disconnect-case/finish`,
      withoutBill ? { without_bill: true } : {},
    ),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE OTHER HALF OF THE JOB — three writes, two of them mounted since August
// ══════════════════════════════════════════════════════════════════════════
/**
 * §5.8.4's first step back — `POST /accounts/{id}/disconnect-case/reconnecting`.
 *
 * ⚠ **BUILT 2026-08-25, ROUTED 2026-08-28, CALLED BY NOTHING UNTIL TODAY.**
 * PO, 2026-09-20: *"Today a utility can cut supply and cannot restore it from
 * the product."* This function is the first caller — hard-won law 2 read from
 * the engine end, exactly as `markDisconnectCaseCut` above was.
 *
 * ⛔ **IT IS NOT AUTOMATIC ON PAYMENT, AND THAT IS `BR-PAY-036`.** A payment is
 * always accepted and acceptance never changes an account's status by itself;
 * the ladder stops itself when money posts, and the METER does not turn itself
 * back on. This is the explicit, audited staff act that says a visit is due.
 *
 * `field_visit` carries the reconnect job the clerk ticked (`CR-070` wave P).
 * **An absent key means nobody was sent**, which is the answer this door gave
 * for its whole life, so it is omitted rather than sent empty.
 */
export async function markDisconnectCaseReconnecting(
  accountId: string,
  body: { on_date: string },
  client: ApiClient = api,
): Promise<unknown> {
  return client.post(
    `/accounts/${encodeURIComponent(accountId)}/disconnect-case/reconnecting`,
    body,
  );
}

/**
 * §5.8.4's last rung — `POST /accounts/{id}/disconnect-case/restore`.
 *
 * ⛔ **ONLY FROM `reconnecting`.** A cut account cannot jump straight to
 * restored: the middle state is *"paid, awaiting a visit"*, and skipping it
 * would record a restoration on an account that never settled.
 *
 * ⚠ **IT PUTS THE ACCOUNT STATUS BACK, OR SAYS IT COULD NOT.** The status is
 * read from what the cut recorded; where the cut recorded none, the account
 * keeps the status it has and the response names the absence rather than
 * choosing `active` for a customer who was on holiday hold.
 */
export async function restoreDisconnectCaseService(
  accountId: string,
  body: { on_date: string },
  client: ApiClient = api,
): Promise<unknown> {
  return client.post(
    `/accounts/${encodeURIComponent(accountId)}/disconnect-case/restore`,
    body,
  );
}

/**
 * `BR-CUS-1083` — `POST /accounts/{id}/disconnect-case/visit`.
 *
 * The crew attended and did not cut. PO, 2026-09-20: *"The register reflects
 * reality. Today a failed visit is invisible and the case looks untouched."*
 *
 * ⚠ **`note` IS OPTIONAL AND IS OMITTED RATHER THAN SENT EMPTY** — the server
 * stores an empty string as NULL, and two spellings of *nobody wrote a note*
 * is how a screen renders a blank line where it meant an absence.
 */
export async function recordDisconnectCaseVisit(
  accountId: string,
  body: { on_date: string; outcome: string; note?: string },
  client: ApiClient = api,
): Promise<unknown> {
  return client.post(
    `/accounts/${encodeURIComponent(accountId)}/disconnect-case/visit`,
    body,
  );
}
