// ── Trace ──────────────────────────────────────────────
// Change:   The TRANSFER RECORD screen — blueprint `02 Accounts Menu
//           Blueprint.pdf` p132, *"The transfer, opened · TRF-26-0021 ·
//           /brazosbend/transfers/trf-26-0021 · Proposed · the deposit and the
//           balance that followed the customer"*. Approved by the PO:
//           *"buildit - use drawing images. screens hosuld match exactly to
//           drawing"*. **Drawn and never built** — the conformance file's own
//           §7 reads *"NOT BUILT, AT ANY ADDRESS … no route, no component, no
//           endpoint"*, and it is the sharpest gap on this surface: a clerk can
//           make a sale and has no way to read it back.
// Rules:    B14 rule 42 (the drawing is read AS AN IMAGE — this screen was
//           built from a 2x page render and 3x crops of p132, never from
//           extracted text) · rule 41 (the product matches the blueprint) ·
//           rule 40 (page-head title 32px, which `PageHeader` carries) ·
//           rule 2 (ONE page header) · rule 31 (no database id is ever a
//           field's visible value — the kicker is the transfer NUMBER) ·
//           rules 32/33 (the copy budget — every cut is recorded in §3) ·
//           rule 21 + its per-file clause (Tailwind utilities; this file is on
//           `styles/route-b-migrated.txt`) · rule 36 (the shared kit is how you
//           comply) · hard-won law 2 and its mirror (no dead control, and no
//           live control refusing over something already shipped) ·
//           `BR-CUS-1030` (a transfer REASSIGNS the account) · `BR-CUS-085`
//           (nothing is refunded and re-collected) · CLAUDE.md hard rule 2
//           (money displays to 2 decimals, and is never computed here)
// Screens:  the TRANSFER RECORD, `/transfers/{ref}` — a NEW route beside
//           `/transfers/new`, and the static segment is declared FIRST in
//           `App.tsx` so `new` can never be read as a reference
// Tests:    src/features/customers/TransferRecordPage.test.tsx
// Walk:     10-scripts/po20260920_transfer_record_walkthrough.mjs — transfer
//           was the ONLY one of these flows with no walkthrough script, which
//           is why the PO found a live step-4 break the suites could not
//           (`DEF-CUS-5934`, 2026-09-20)
// Impacts:  App.tsx (the route) · styles/route-b-migrated.txt · the eleven
//           locale catalogues (`customers.transferRecord.*`)
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS RECORD HAS NO ACTIONS, AND THAT IS THE ANSWER RATHER THAN A GAP.**
// The blueprint says so on p132, under the drawing, in its own words:
//
//     *"This record has no actions, and that is the answer rather than a gap.
//     A move-in and a transfer are records of acts that have already happened
//     — there is nothing left to decide on them, so the only controls are
//     doors to the accounts they produced. Drawing a button here would invent
//     a decision the product does not offer."*
//
// It is unusual enough that somebody will try to "improve" it, which is why it
// is written here before it is built rather than left to be inferred from the
// absence of a verb. **TWO DOORS AND NOTHING ELSE** — `Open the customer`
// (primary, as p132 draws it) and `Open the account` (secondary). The test
// file counts them rather than sampling them, because a subset assertion goes
// on passing while somebody adds a third.
//
// ⚠ **`MoveRecordPage.tsx` REACHED THE SAME CONCLUSION INDEPENDENTLY AND THIS
// FILE FOLLOWS ITS SHAPE RATHER THAN INVENTING A SECOND ONE.** Same fact rows,
// same stated-absence machinery, same two-column grid, same head. The one
// deliberate difference is the ORDER of the doors: p074 draws the account
// first and p132 draws the customer first, and each screen follows its own
// drawing.
//
// ⛔ **AND IT DOES *NOT* TAKE THE MOVE RECORD'S `Resume` DOOR.** That door was
// a PO ruling of 2026-09-19 about an unfinished MOVE (*"We will need this
// action on details page - 4 · Close or complete it"*). No such ruling exists
// for a transfer, and the brief for this screen is explicit that there are two
// doors and no other control — so an unfinished transfer renders its facts as
// stated absences and offers nothing. Adding one here would be this lane
// deciding a control the PO has not been asked about.
//
// ══════════════════════════════════════════════════════════════════════════
// §1 · WHAT THIS SCREEN IS ABOUT, IN ONE SENTENCE
// ══════════════════════════════════════════════════════════════════════════
// `BR-CUS-1030` (PO ruling 2026-09-01) made a transfer a REASSIGNMENT: one
// account changes hands and nothing else moves. p132's red banner is that rule
// stated to a clerk, and the two `$0.00` rows in the money box are the same
// rule stated as arithmetic — see §4.
//
// ══════════════════════════════════════════════════════════════════════════
// §2 · WHAT THE SERVER OWES THIS SCREEN, AND WHAT IT CANNOT SERVE YET
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **`GET /transfers/{ref}` DOES NOT EXIST AT THE COMMIT THAT LANDS THIS
// FILE.** A sibling lane is building it. Until it answers, this address
// renders the NOT-FOUND branch — one sentence, no figures, no invented shape —
// and that is the honest state rather than a screen dressed up with defaults.
//
// ⚠ **A SIBLING MEASURED THE SAME QUESTION THE SAME DAY AND THE TWO AGREE —
// READ `04-docs/05-modules/03-customers/conformance/
// transfer-record-what-is-durable.md` BEFORE CHANGING ANY OF THIS.** It was
// written independently of this screen and lands on all six of the decisions
// below: the reference IS servable, the two `$0.00` rows are *"CONSTANTS of the
// rule"*, `Sold by` and the two money snapshots and `Buyer matched or created`
// have **no durable home**, the page may **never** read today's
// `accounts.balance` and label it as the sale's figure (*"wrong by exactly the
// amount the account has moved since"*), and the doors should follow the move
// record's `doors` shape. Two lanes reaching one answer separately is the only
// evidence either is right.
//
// **So every figure and every fact on this page arrives from the server or is
// stated as an ABSENCE. Nothing is derived here and nothing is defaulted.**
// The wire shape below is `move_record_reads.record_detail`'s convention —
// `{value, unavailable}`, never both and never neither — because the sibling
// endpoint will be written beside that one and two conventions on one surface
// is how a screen learns to render `null` as a figure.
//
// Three things the endpoint may legitimately be unable to serve, each for a
// reason that is written down, and each rendered as a stated absence:
//
//   · **`Sold by`.** `transfers.reassign_account` deletes the seller's
//     `customer_accounts` link and overwrites `accounts.customer_id`, so after
//     a sale the seller survives ONLY in `audit_log`, **which is pruned on a
//     retention schedule**. The drawn TITLE — `Tan, Wei → Ferraro, L.` — needs
//     it, so when it is absent this page renders the BUYER alone rather than
//     an arrow pointing at a dash. ⚠ **The PO ruled on 2026-09-20 that this
//     must stop** — *"we cannot override customer id - seller and buyer cstmer
//     id are unique those does not change"* — and the SHAPE that follows (a
//     link that ENDS rather than a row that is deleted) is proposed and NOT
//     built. The day it is, this row fills itself and nothing here changes.
//   · **the reference.** ⚠ **p132's dashed panel — *"No transfer numbering
//     series exists…"* — IS STALE, and this is worth reading before anybody
//     "restores" it.** `OQ-426` reads **CLOSED** in the register's status
//     column, ruled 2026-08-27, PO verbatim: *"Transfer TRF-26-0001 … follow
//     same logic that we are following for other numbers we have did in
//     settings."* `core/numbering.py` carries the series, `transfers.py`
//     allocates inside `start_transfer`'s transaction, and `_serialize`
//     already emits `transfer_no` **and** `TRANSFER_NUMBER_UNAVAILABLE` for a
//     row that predates the series. So the drawing describes the world of
//     2026-08-26. **Both arms are rendered** — the number when there is one,
//     the server's own absence when there is not — which is what the dashed
//     panel asked for, in four words instead of forty-five.
//   · **deposit interest.** Not computed. The PO ruled on 2026-09-19 that it
//     is computed AT SETTLEMENT, so on the day of a sale there is nothing to
//     show and p132 draws `— not recorded` for exactly that reason.
//
// ⚠ **A `$0.00` WHERE A FIGURE COULD NOT BE COMPUTED IS A MONEY CLAIM, NOT A
// BLANK.** A sibling shipped `Short by $0.00` under its own sentence saying the
// subtraction had not run and it was filed as a defect the same day. Every
// money row here is either the server's figure or a stated absence — with the
// two exceptions §4 names, which are a PROHIBITION rather than a measurement.
//
// ══════════════════════════════════════════════════════════════════════════
// §3 · WHAT p132 DRAWS THAT THIS SCREEN DOES NOT SAY, AND WHERE EACH WENT
// ══════════════════════════════════════════════════════════════════════════
// **The copy is not the drawing's, on the PO's own instruction** (2026-09-19,
// verbatim): *"even if drawing sshow too much content ons creen - dont apply
// that we have to use our rules to show content on screen"*. So the SHAPE is
// p132's and the WORDS are B14 rules 32 and 33's. `MoveRecordPage` cut both of
// p074's red boxes on the same reasoning (its exception E3). Recorded rather
// than silently dropped, because a reader comparing this screen with the
// drawing will otherwise think something is missing:
//
//   · the banner's second sentence — *"A-11455 is the same account it was
//     before the sale, at the same address, with the same meters and the same
//     unbroken ledger"* (24 words) — is CUT. It is not lost: every clause of it
//     is a ROW of *Nothing changed* directly below, which is where a clerk
//     reads it as fact rather than as prose. The banner keeps the FACT, in
//     four words.
//   · *"Nothing moved, and that is why this is cheap. The account carries its
//     own ledger and the account did not go anywhere, so the balance never
//     moved either."* — RATIONALE, which rule 33 puts at ZERO words on screen.
//     It is here, and in the decision log.
//   · *"A bill is a record of what was sent. Every invoice, payment and
//     journal entry issued before the sale still names the seller and always
//     will."* — RATIONALE. The FACT survives as the `Bills issued` row's value.
//   · the red *"The contact details stayed with the account, and somebody has
//     to fix that…"* box (48 words) — RATIONALE for a row that is already on
//     the screen: *Contact details · Still the seller's*, under **Not said
//     here**. The instruction inside it (a clerk changes them on the account
//     screen) is one click away through `Open the account`, which is drawn.
//   · the dashed *THE REFERENCE ABOVE* panel (45 words) — see §2. It is a
//     stated absence, and it is rendered as one.
//   · `Account · A-11455 · active, and it stayed active` loses its second
//     clause: `Status` is a row of its own six rows below, and saying it twice
//     is rule 32's description budget spent on a repetition.
//
// ⚠ **ONE DRAWN ROW IS KEPT UNDER PROTEST AND IT IS NAMED HERE SO THE PO CAN
// SETTLE IT IN ONE WORD.** *Buyer told · Not decided* is the disclosure
// question `OQ-1253`, which is OPEN. On **2026-09-20** the PO struck the
// wizard's own *Who gets told this figure* panel — *"why we are showing this"*
// — because it shows a clerk an undecided internal question. That ruling is
// about STEP 4, a surface where a clerk is deciding; this row sits in a
// section whose whole job is to name what the record cannot tell you, and the
// brief for this screen lists it. **It is kept, in two words, and reported.**
// The day `OQ-1253` closes, this row states the answer instead.
//
// ══════════════════════════════════════════════════════════════════════════
// §4 · THE TWO `$0.00` ROWS ARE THE POINT OF THE SCREEN
// ══════════════════════════════════════════════════════════════════════════
// `BR-CUS-085`, verbatim from `TRF-02.1`'s badge: *"This customer is not
// leaving. Their deposit, their discounts and their history move with them —
// nothing is refunded and re-collected."* The register states what the rule
// BINDS: *"on the outgoing account `deposit_on_file` is **not touched**, so no
// refund is raised and no `payments.refunds` row is created"*, and
// `transfers.py` commits with `"refund_raised": False` with a test asserting
// it.
//
// **So `Refunded to seller` and `Re-collected from buyer` are a PROHIBITION,
// not a measurement**, and they are the one place on this page where a figure
// is drawn without the server sending one. Rendering them as an absence would
// say *"we did not check"* about the single fact this screen exists to prove.
// They take the server's figure when it sends one — a non-zero there would
// mean the rule had been broken and the screen must show it — and otherwise
// they read `0.00`, from the rule.
//
// `Fees charged · None` is the same kind of statement one step weaker: nothing
// in `apps/customers/transfers.py` raises a fee — the word does not appear in
// the file — so a sale charges none. It is rendered as the rule's `None` and
// yields to a served fact the moment one exists.
//
// ⛔ **THE TOTAL IS NOT COMPUTED HERE.** `Taken on` is the server's figure or
// an absence. Adding the balance to the deposit on a screen would be this file
// doing arithmetic on money, which CLAUDE.md hard rule 2 and B4 put on the
// other side of the wire.
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { buttonClasses } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { useCrumbLeaf } from "@/components/crumbLeaf";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { accountDetailPath } from "./customersShared";
import { CUSTOMERS_ROUTE } from "./CustomersListPage";

/**
 * The two doors' class sets, resolved ONCE at module scope.
 *
 * ⚠ **HOISTED DELIBERATELY — `MoveRecordPage` and `routesCyclesShared` do the
 * same.** `styles/routeBUtilities.test.ts` reads string literals that appear
 * inside a `className` attribute, so calling the kit INLINE there makes it see
 * a class named after the variant and report an orphan — a true reading of
 * what it can see, over a call that is perfectly correct. Naming the result
 * keeps the literal out of the attribute and keeps the check honest.
 *
 * ⚠ **`secondary` AND `ghost`, NOT `primary` AND `secondary` — AND THE REASON
 * IS THE DRAWING.** p132 draws `Open the customer` as an OUTLINED button and
 * `Open the account` as quiet text beside it: **no filled button appears on
 * this screen at all**, which is the same sentence as *"this record has no
 * actions"* said in ink. This kit's `primary` is `bg-accent` — filled, the
 * colour a commit wears — so reaching for it here would draw a control that
 * looks like a decision on the one page whose point is that there is none.
 * The kit's two nearest members to what is drawn are the OUTLINED `secondary`
 * and the borderless `ghost`, and picking from the kit rather than inventing a
 * grey of our own is B14 rule 36. The EMPHASIS the brief asks for survives —
 * the customer door is the emphasised one — and only the variant names differ
 * from the words used to describe them.
 */
const DOOR_EMPHASIS = buttonClasses("secondary");
const DOOR_QUIET = buttonClasses("ghost");

/** A1's screen id for this page — p132 is the record behind S89's wizard. */
export const TRANSFER_RECORD_SCREEN = "S89.transferRecord";

/**
 * The TRANSFER RECORD's address — **`/transfers/{ref}`, beside
 * `/transfers/new` and never under `/accounts/`**.
 *
 * The blueprint's own URL is `/brazosbend/transfers/trf-26-0021`, and the
 * placement is the point rather than a preference: a sale is a record OF an
 * act that spans two customers, and `BR-CUS-1030` leaves it belonging to one
 * account. Hanging it off `/accounts/:id` would say the ACCOUNT owns the sale,
 * which is the reading `BR-CUS-1030` spent 916 lines correcting.
 *
 * ⚠ **`:ref` IS THE TRANSFER NUMBER AND NEVER A UUID** (B14 rule 31).
 * `TRF-26-0001` is what a clerk quotes down a phone, ruled by the PO on
 * 2026-08-27 when `OQ-426` closed.
 */
export function transferRecordPath(reference: string): string {
  return `/transfers/${encodeURIComponent(reference)}`;
}

export const TRANSFER_RECORD_ROUTE = "/transfers/:ref";

// ══════════════════════════════════════════════════════════════════════════
// THE WIRE SHAPE — what `GET /transfers/{ref}` owes this screen
// ══════════════════════════════════════════════════════════════════════════
/**
 * One label→value cell: a value, OR the reason there is none.
 *
 * ⚠ **NEVER BOTH AND NEVER NEITHER.** This type cannot express the rule, so
 * the server is where it is enforced; what this file guarantees is that BOTH
 * arms are drawn — an absence is rendered as its own short sentence, never
 * swallowed into a dash and never into a zero.
 */
export interface TransferFact<T = string> {
  value: T | null;
  unavailable: TransferAbsence | null;
}

/**
 * Why a fact is missing.
 *
 * ⚠ **`br_ref` IS OPTIONAL HERE AND IT IS REQUIRED ON `MoveAbsence`, WHICH IS
 * WHY THIS TYPE EXISTS AT ALL RATHER THAN BEING IMPORTED.** The transfer
 * module already publishes an absence of its own shape —
 * `transfers.TRANSFER_NUMBER_UNAVAILABLE` carries `code`, `series`,
 * `open_question` and `detail` and NO `br_ref` — so a type demanding one would
 * force this screen to fabricate a rule id for a real server payload. The two
 * fields every absence has are `code` and `detail`, and those are the two this
 * screen reads.
 */
export interface TransferAbsence {
  code: string;
  detail: string;
  br_ref?: string;
  series?: string;
  open_question?: string;
}

export interface TransferRecordDetail {
  /** `completed` · `in_flight` · `cancelled` — the head's first chip. */
  state: "completed" | "in_flight" | "cancelled";
  /** `TRF-26-0001`, or the server's own reason there is no number (§2). */
  reference: TransferFact;
  /** The buyer's display name — the right-hand half of p132's drawn title. */
  buyer_name: TransferFact;
  /** The seller's display name — the LEFT half, and the one that may be gone
   *  for ever (§2). When it is absent the title is the buyer alone. */
  seller_name: TransferFact;
  what_happened: {
    /** The account NUMBER, never its id (B14 rule 31). */
    account: TransferFact;
    unit: TransferFact;
    service_address: TransferFact;
    sold_on: TransferFact;
    sold_by: TransferFact;
    sold_to: TransferFact;
    /** `person` · `company` — a stored CODE, translated on this screen. */
    buyer_kind: TransferFact;
    /** `ssn` · `driving_licence` — a stored CODE, translated on this screen.
     *  ⚠ **THE KIND, NEVER THE NUMBER.** `BR-CUS-092` keeps the value itself
     *  app-layer encrypted, and a licence number on a record page would be a
     *  government id rendered to anyone who can open a sale. */
    identifier_given: TransferFact;
    /** `matched` · `created` — a stored CODE, translated on this screen. */
    buyer_matched: TransferFact;
    changeover_read: TransferFact<{
      raised: number;
      completed: number;
      on: string | null;
    }>;
    committed_by: TransferFact<{ name: string | null; at: string | null }>;
  };
  unchanged: {
    account_no: TransferFact;
    /** A stored status CODE, translated on this screen (B14 rule 31). */
    status: TransferFact;
    /** How long the account's ledger runs, unbroken. ⚠ **NOTHING COUNTS THIS
     *  TODAY** — the conformance file's §7 says so of p132's drawn
     *  `38 months`, and it is the same gap step 1's `Ledger` row has. It
     *  arrives as an absence until something counts it. */
    ledger_months: TransferFact<number>;
  };
  money: {
    /** ISO 4217, served with the figures. */
    currency: string | null;
    /** `reassign_account` captures `balance_at_sale` at the moment of sale. */
    balance: TransferFact;
    /** …and `deposit_at_sale` beside it. */
    deposit: TransferFact;
    /** Not computed anywhere — the PO ruled it is computed at SETTLEMENT
     *  (2026-09-19), so on the day of a sale there is nothing to show. */
    deposit_interest: TransferFact;
    /** `BR-CUS-085` — see §4. Optional on the wire BECAUSE the rule, not the
     *  server, is what guarantees it. */
    refunded?: TransferFact;
    /** `BR-CUS-085` — see §4. */
    recollected?: TransferFact;
    /** No fee is raised anywhere in the transfer path — see §4. */
    fees?: TransferFact;
    /** The total the buyer took on. **SERVED, never added up here** (§4). */
    taken_on: TransferFact;
  };
  doors: {
    account: TransferFact<{ account_id: string; account_no: string }>;
    customer: TransferFact<{ customer_id: string; name: string | null }>;
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
 * `apiPath` joins tenant and path with nothing between them and every request
 * goes to `/api/brazosbendtransfers/…`, a 404 on every sale, invisible because
 * a 404 and a stated absence look identical on screen.
 */
export async function readTransferRecord(
  reference: string,
  client: ApiClient = api,
): Promise<TransferRecordDetail> {
  return requireData(
    await client.get<TransferRecordDetail>(`/transfers/${encodeURIComponent(reference)}`),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE PIECES
// ══════════════════════════════════════════════════════════════════════════
/**
 * One drawn fact — label left, value RIGHT, a hairline between rows.
 *
 * ⚠ **THE HAIRLINE IS `border-b` ON THE ROW AND `last:border-0`, NOT A GAP** —
 * `MoveRecordPage.Fact`'s markup, character for character, so the two record
 * screens cannot drift into two shapes. A `divide-y` on the parent would be
 * equivalent until one row is conditionally absent, which is what an
 * unfinished transfer does to every list on this page.
 */
export function TransferFactRow(props: { label: string; children: ReactNode }) {
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
 * `detail` explains WHY a fact is missing, which is RATIONALE and is zero
 * words on screen. What a clerk reads is the short form; the full sentence is
 * reachable on hover and, more importantly, is in the payload for anyone
 * debugging. A dash with nothing behind it is what this exists to prevent
 * (`DEF-075` / `DEF-127`).
 */
export function Absent(props: { absence: TransferAbsence; label: string }) {
  return (
    <span className="text-neutral-600 font-normal" title={props.absence.detail}>
      {props.label}
    </span>
  );
}

/** A fact row that draws whichever arm the server filled. */
function Fact(props: {
  label: string;
  fact: TransferFact<unknown> | undefined;
  absentLabel: string;
  render: (value: never) => ReactNode;
}) {
  const fact = props.fact;
  // ⚠ **AN ABSENT FIELD IS NOT AN ABSENT FACT, AND THE DIFFERENCE IS THE WHOLE
  // POINT OF §2.** A payload that carries no `sold_by` at all — because the
  // endpoint has not landed, or because a version of it predates the field —
  // must still say something a clerk can read, and the only honest thing is
  // the same short label the server's own absence would carry.
  if (fact === undefined || (fact.value === null && fact.unavailable === null)) {
    return (
      <TransferFactRow label={props.label}>
        <span className="text-neutral-600 font-normal">{props.absentLabel}</span>
      </TransferFactRow>
    );
  }
  return (
    <TransferFactRow label={props.label}>
      {fact.unavailable ? (
        <Absent absence={fact.unavailable} label={props.absentLabel} />
      ) : (
        props.render(fact.value as never)
      )}
    </TransferFactRow>
  );
}

/**
 * One line of the money box.
 *
 * ⚠ **A FIGURE OR A SENTENCE, AND NEVER A ZERO STANDING IN FOR EITHER.**
 */
function MoneyRow(props: {
  label: string;
  fact: TransferFact | undefined;
  currency: string;
  absentLabel: string;
  /** The figure this row carries when the RULE guarantees it and the server
   *  sends nothing — `BR-CUS-085`'s two rows and the fee row, and nothing
   *  else. See §4. */
  ruled?: string;
  ruledWords?: string;
}) {
  const fact = props.fact;
  const served = fact !== undefined && fact.unavailable === null && fact.value !== null;
  return (
    <TransferFactRow label={props.label}>
      {served ? (
        <MoneyCell amount={fact!.value!} currency={props.currency} />
      ) : props.ruled !== undefined ? (
        <MoneyCell amount={props.ruled} currency={props.currency} />
      ) : props.ruledWords !== undefined ? (
        props.ruledWords
      ) : fact?.unavailable ? (
        <Absent absence={fact.unavailable} label={props.absentLabel} />
      ) : (
        <span className="text-neutral-600 font-normal">{props.absentLabel}</span>
      )}
    </TransferFactRow>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE SCREEN
// ══════════════════════════════════════════════════════════════════════════
export function TransferRecordPage(props: RegionalProps & { client?: ApiClient } = {}) {
  const { t } = useTranslation();
  const { ref = "" } = useParams<{ ref: string }>();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  // IS-8 — a date renders in the TENANT's zone AND format, and `DateCell`
  // requires both. One regional path, the same every other dated screen uses.
  const { timeZone, dateFormat } = useRegional(props);

  // ⚠ **ONE HOOK, DECLARED ABOVE EVERY EARLY RETURN, AND THAT IS NOT A STYLE
  // CHOICE (`DEF-CUS-5911`).** React counts hooks per render: a second
  // `useQuery` placed below a loading guard runs zero times on the first paint
  // and once on the next, and React throws *"Rendered more hooks than during
  // the previous render"* — which turned the whole move record into
  // `Unexpected Application Error!` for both its flows. Every unit test passed
  // over it, because `renderToStaticMarkup` renders ONCE. If this screen ever
  // needs a second read, it is declared HERE with `enabled`, never below.
  const query = useQuery({
    queryKey: ["transfer-record", ref],
    queryFn: () => readTransferRecord(ref, client),
    enabled: ref !== "",
  });

  // ── p132's BREADCRUMB LEAF — `Accounts / Transfers / TRF-26-0001` ────────
  //
  // ⚠ **DECLARED HERE, ABOVE EVERY EARLY RETURN, FOR THE SAME REASON THE QUERY
  // IS** (`DEF-CUS-5911`): `useCrumbLeaf` is a hook, and a hook that runs on
  // some renders and not others changes the hook COUNT and crashes the screen.
  // It reads `query.data` defensively because `record` is not in scope yet.
  //
  // ⚠ **THE LEAF IS THE REFERENCE AND NEVER THE ID** (B14 rule 31), and it is
  // `null` until the server has sent one — *"an empty crumb is not the same
  // claim as no crumb"*, in `crumbLeaf`'s own words. A record with no number
  // publishes nothing rather than a blank.
  //
  // ⚠ **THIS MECHANISM LANDED HOURS BEFORE THIS SCREEN DID, AND FINDING IT IS
  // WHY THIS LINE EXISTS RATHER THAN A SECOND DEFECT ROW.** `DEF-374` had been
  // open since 2026-08-21 — *"no wizard or detail screen can supply its own
  // breadcrumb leaf"* — and its own fix note asked for ONE shell-level
  // mechanism rather than nine per-screen ones. `components/crumbLeaf.ts` is
  // that mechanism. The ancestors `Accounts / Transfers` still do not resolve,
  // because `breadcrumbFor` reads `SHELL_NAV` and `/transfers/:ref` hangs
  // outside it; that half is `DEF-SHL-5983` and is the shell's to settle.
  useCrumbLeaf(query.data?.reference?.value ?? null);

  if (query.isLoading) return <LoadingSkeleton variant="card" />;
  if (query.isError || !query.data) {
    // ⚠ **THIS IS THE STATE THE PRODUCT IS IN UNTIL `GET /transfers/{ref}`
    // LANDS**, and it says so in a sentence rather than by drawing an empty
    // version of the record. A screen that renders its own furniture over no
    // data is worse than a 404, because it looks like a page.
    return (
      <div className="p-6">
        <PageHeader
          title={t("customers.transferRecord.notFound.title")}
          backTo={{
            to: tenantPath("/accounts?tab=transfers"),
            label: t("customers.transferRecord.back"),
          }}
        />
        <p className="mt-4 text-sm text-neutral-600">
          {t("customers.transferRecord.notFound.body")}
        </p>
      </div>
    );
  }

  const record = query.data;
  const day = (iso: string | null | undefined) =>
    iso ? <DateCell value={iso} timeZone={timeZone} dateFormat={dateFormat} /> : null;
  // ⚠ **THE COMMIT CARRIES ITS TIME, BECAUSE p132 DRAWS ONE** —
  // `S. Ortiz · 05/07/2026 14:06`. It is the one timestamp on this page rather
  // than a calendar date, and `DateCell`'s own `withTime` renders it through
  // the SAME formatting path in the tenant's zone. A second path for one row
  // is what `BR-SHL-023` forbids and how a screen ends up showing one clerk
  // `2026-05-07` and another `05/07/2026`.
  const moment = (iso: string | null | undefined) =>
    iso ? (
      <DateCell value={iso} timeZone={timeZone} dateFormat={dateFormat} withTime />
    ) : null;
  // `money.currency ?? "USD"` is the sibling's fallback and it is only ever
  // reached by a payload that sent figures and no currency — which the server
  // contract forbids. It exists so a malformed payload renders a wrong symbol
  // rather than crashing a money component mid-screen.
  const currency = record.money?.currency ?? "USD";

  // ── the head's chips: p132 draws three ───────────────────────────────────
  const chips: { key: string; label: ReactNode; tone: StatusTone }[] = [];
  chips.push({
    key: "state",
    label: t(`customers.transferRecord.state.${record.state}`),
    tone: record.state === "completed" ? "success" : record.state === "cancelled" ? "muted" : "info",
  });
  // ⚠ **`Account reassigned` IS DRAWN ON A COMPLETED SALE AND ON NO OTHER.**
  // It is `BR-CUS-1030` having HAPPENED, not a description of the flow — an
  // unfinished transfer has reassigned nothing, and a cancelled one never
  // will. Showing it on either would be the screen stating an act nobody
  // performed.
  if (record.state === "completed") {
    chips.push({
      key: "reassigned",
      label: t("customers.transferRecord.chip.reassigned"),
      tone: "neutral",
    });
  }
  if (record.what_happened?.sold_on?.value) {
    chips.push({
      key: "sold",
      label: (
        <>
          {t("customers.transferRecord.chip.sold")} {day(record.what_happened.sold_on.value)}
        </>
      ),
      tone: "neutral",
    });
  }

  // ── the drawn title: `Tan, Wei → Ferraro, L.` ───────────────────────────
  // ⚠ **WHEN THE SELLER IS GONE, THE TITLE IS THE BUYER ALONE.** An arrow with
  // a dash on its left would read as *"somebody sold this"* — which is true
  // and useless — and an invented word in the seller's place would be this
  // screen naming a person nobody recorded. The absence is stated once, as the
  // `Sold by` row, where a clerk can hover it for the reason.
  const seller = record.seller_name?.value ?? null;
  const buyer = record.buyer_name?.value ?? null;
  const title =
    seller !== null && buyer !== null
      ? `${seller} → ${buyer}`
      : (buyer ?? seller ?? record.reference?.value ?? "");

  const accountDoor = record.doors?.account;
  const customerDoor = record.doors?.customer;

  return (
    <div className="p-6">
      <PageHeader
        // p132: `← The register`. The Transfers tab is where a clerk came from
        // and the only place this page links backwards to.
        backTo={{
          to: tenantPath("/accounts?tab=transfers"),
          label: t("customers.transferRecord.back"),
        }}
        // The kicker is the REFERENCE — `TRANSFER TRF-26-0001` — which is the
        // number a clerk quotes. B14 rule 31: the transfer's NUMBER, never its
        // uuid. When there is no number, the kicker says so in three words and
        // carries the server's own sentence for anyone who needs it (§2).
        kicker={
          <span className="uppercase tracking-wide">
            {t("customers.transferRecord.kicker")}{" "}
            {record.reference?.unavailable ? (
              <Absent
                absence={record.reference.unavailable}
                label={t("customers.transferRecord.absent.noReference")}
              />
            ) : (
              (record.reference?.value ?? "")
            )}
          </span>
        }
        // ⚠ **THE TITLE IS THE TWO PARTIES** (p132), at 32px — `PageHeader`
        // carries rule 40's size on both heading branches, so this screen does
        // not set it and cannot drift from the other ~137.
        title={title}
        status={
          <span className="flex flex-wrap items-center gap-2">
            {chips.map((chip) => (
              <StatusPill key={chip.key} tone={chip.tone}>
                {chip.label}
              </StatusPill>
            ))}
          </span>
        }
        // ── THE TWO DOORS, AND NOTHING ELSE ────────────────────────────────
        // p132 draws `Open the customer` boxed and `Open the account` beside
        // it. Neither decides anything — both are doors.
        //
        // ⚠ **THE DRAWING PUTS THE CUSTOMER DOOR ON THE LEFT AND THIS HEADER
        // PUTS IT ON THE RIGHT, AND THE HEADER WINS.** `PageHeader` renders
        // `secondaryActions` before `primaryAction` on every one of ~137
        // screens, so the emphasised control is the rightmost one. B14 rule 38
        // settles it — *"where a drawing and our UI rules disagree about how a
        // FORM IS BUILT, the UI rules win"*, and a header's button ORDER is
        // construction rather than layout: following the drawing here would
        // make this the one screen in the product whose action bar reads the
        // other way round. What the bar CONTAINS is still the drawing's, and
        // it contains exactly these two.
        primaryAction={
          customerDoor?.unavailable || !customerDoor?.value ? (
            <span
              className="text-sm text-neutral-600"
              title={customerDoor?.unavailable?.detail}
              data-testid="transfer-record-no-customer"
            >
              {t("customers.transferRecord.door.noCustomer")}
            </span>
          ) : (
            <Link
              className={DOOR_EMPHASIS}
              // ⚠ **THERE IS NO CUSTOMER DETAIL SCREEN IN THIS PRODUCT** —
              // `/customers` is a LIST and its row action opens the person's
              // first ACCOUNT. `MoveRecordPage` measured this on 2026-09-19 and
              // landed its own customer door on the register filtered to that
              // person; this one lands in the same place, for the same reason
              // and through the same route constant. It is the nearest TRUE
              // destination rather than a button that opens nothing (hard-won
              // law 2's mirror), and the day a customer screen lands, both
              // doors move together.
              to={tenantPath(
                `${CUSTOMERS_ROUTE}?q=${encodeURIComponent(customerDoor.value.name ?? "")}`,
              )}
              data-testid="transfer-record-open-customer"
            >
              {t("customers.transferRecord.door.customer")}
            </Link>
          )
        }
        secondaryActions={
          accountDoor?.unavailable || !accountDoor?.value ? (
            <span
              className="text-sm text-neutral-600"
              title={accountDoor?.unavailable?.detail}
              data-testid="transfer-record-no-account"
            >
              {t("customers.transferRecord.door.noAccount")}
            </span>
          ) : (
            <Link
              className={DOOR_QUIET}
              to={tenantPath(accountDetailPath(accountDoor.value.account_id))}
              data-testid="transfer-record-open-account"
            >
              {t("customers.transferRecord.door.account")}
            </Link>
          )
        }
      />

      {/* p132's red banner — `BR-CUS-1030` stated to a clerk, in four words.
          The 24-word second sentence is CUT and every clause of it is a row of
          *Nothing changed* below (§3). `role="note"` because it is a standing
          fact about this record, not an alert that has just fired — the same
          reading `WarningBox` records for `role="status"`: this is not a fire.

          ⚠ **EVERY ONE OF THESE FOUR NAMES IS A DECLARED TOKEN, AND THAT IS
          NOT A DETAIL (`DEF-SHL-5088`, `DEF-INT-4236`, `DEF-SHL-4281`).** This
          theme declares `--color-danger-100/500/700` and NO `-50`, `-300`,
          `-800` and no bare `--color-danger`; a utility naming one of those
          compiles to nothing, stays in the DOM, and passes `toContain`, `tsc`
          and eslint while the box draws with no colour at all. Three defects
          in this repository are that exact sentence. */}
      <p
        role="note"
        className="mt-4 border border-danger-500 bg-danger-100 px-4 py-3 text-sm font-semibold text-danger-700"
        data-testid="transfer-record-banner"
      >
        {t("customers.transferRecord.banner")}
      </p>

      {/* p132 is TWO COLUMNS at desktop and one at phone width. */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          <Panel title={t("customers.transferRecord.section.whatHappened")}>
            <dl className="mt-1">
              <Fact
                label={t("customers.transferRecord.fact.account")}
                fact={record.what_happened?.account}
                absentLabel={t("customers.transferRecord.absent.notRecorded")}
                render={(value: string) => value}
              />
              <Fact
                label={t("customers.transferRecord.fact.unit")}
                fact={record.what_happened?.unit}
                absentLabel={t("customers.transferRecord.absent.notRecorded")}
                render={(value: string) => value}
              />
              {/* CLAUDE.md hard rule 8: the address is WALKED from the premises
                  by the server. No entity on this page declares one. */}
              <Fact
                label={t("customers.transferRecord.fact.serviceAddress")}
                fact={record.what_happened?.service_address}
                absentLabel={t("customers.transferRecord.absent.notRecorded")}
                render={(value: string) => value}
              />
              <Fact
                label={t("customers.transferRecord.fact.soldOn")}
                fact={record.what_happened?.sold_on}
                absentLabel={t("customers.transferRecord.absent.notChosenYet")}
                render={(value: string) => day(value)}
              />
              {/* ⚠ **THE ROW THE PRODUCT CANNOT YET FILL** (§2). Its absence
                  label says *the seller is not recorded* and never *none*: a
                  sale always had one, and the difference between *nobody* and
                  *not kept* is the whole of the PO's 2026-09-20 ruling. */}
              <Fact
                label={t("customers.transferRecord.fact.soldBy")}
                fact={record.what_happened?.sold_by}
                absentLabel={t("customers.transferRecord.absent.sellerNotKept")}
                render={(value: string) => value}
              />
              <Fact
                label={t("customers.transferRecord.fact.soldTo")}
                fact={record.what_happened?.sold_to}
                absentLabel={t("customers.transferRecord.absent.notRecorded")}
                render={(value: string) => value}
              />
              {/* A stored CODE is never a visible value (B14 rule 31) — what a
                  clerk reads is the catalogue's own word in their language.

                  ⚠ **`customers.customer.kind.*` IS BORROWED, NOT COPIED.** A
                  buyer is a customer and the product already has ONE pair of
                  words for what kind of one they are, in all eleven
                  catalogues. Minting `transferRecord.buyerKind.person` would
                  be eleven new strings free to drift from eleven that exist —
                  the reasoning B14 rule 34 settles for `Recorded`, and the
                  reasoning `MoveRecordPage` records for sharing the `Resume`
                  key. A re-wording upstream re-words this row, which is the
                  point rather than the risk. */}
              <Fact
                label={t("customers.transferRecord.fact.buyerKind")}
                fact={record.what_happened?.buyer_kind}
                absentLabel={t("customers.transferRecord.absent.notRecorded")}
                render={(value: string) =>
                  t(`customers.customer.kind.${value}`, { defaultValue: "" })
                }
              />
              <Fact
                label={t("customers.transferRecord.fact.identifier")}
                fact={record.what_happened?.identifier_given}
                absentLabel={t("customers.transferRecord.absent.notRecorded")}
                render={(value: string) =>
                  t(`customers.transferRecord.identifier.${value}`, { defaultValue: "" })
                }
              />
              <Fact
                label={t("customers.transferRecord.fact.matched")}
                fact={record.what_happened?.buyer_matched}
                absentLabel={t("customers.transferRecord.absent.notRecorded")}
                render={(value: string) =>
                  t(`customers.transferRecord.matched.${value}`, { defaultValue: "" })
                }
              />
              {/* p132: `2 jobs raised · both completed 05/07`. The COUNTS are
                  the server's; the words are this screen's, within rule 33. */}
              <Fact
                label={t("customers.transferRecord.fact.changeover")}
                fact={record.what_happened?.changeover_read}
                absentLabel={t("customers.transferRecord.absent.noneRaised")}
                render={(value: { raised: number; completed: number; on: string | null }) => (
                  <span>
                    {t("customers.transferRecord.changeover.jobs", {
                      raised: value.raised,
                      completed: value.completed,
                    })}
                    {value.on ? <span className="text-neutral-600"> · {day(value.on)}</span> : null}
                  </span>
                )}
              />
              {/* ⛔ `DEF-CUS-6429` — the label follows the record's STATE. A
                  completed sale had a committer this table does not keep, so
                  it reads *Not recorded*; only an unfinished one is *Not
                  committed yet*. One label for both drew a done sale as a
                  draft. */}
              <Fact
                label={t("customers.transferRecord.fact.committedBy")}
                fact={record.what_happened?.committed_by}
                absentLabel={t(
                  record.state === "completed"
                    ? "customers.transferRecord.absent.notRecorded"
                    : "customers.transferRecord.absent.notCommittedYet",
                )}
                render={(value: { name: string | null; at: string | null }) => (
                  <span>
                    {value.name}
                    {value.at ? (
                      <span className="text-neutral-600"> · {moment(value.at)}</span>
                    ) : null}
                  </span>
                )}
              />
            </dl>
          </Panel>

          <Panel title={t("customers.transferRecord.section.nothingChanged")}>
            <dl className="mt-1">
              <Fact
                label={t("customers.transferRecord.unchanged.accountNo")}
                fact={record.unchanged?.account_no}
                absentLabel={t("customers.transferRecord.absent.notRecorded")}
                render={(value: string) => value}
              />
              {/* ⚠ **THESE THREE ARE THE RULE, NOT A READING** — and they are
                  the only rows on this page whose VALUE is a constant. A
                  transfer writes `customer_id`, the link rows and the
                  transfer's own columns; `BR-CUS-1030` forbids it touching the
                  unit, the meters, the plan or the agreements, and step 1 of
                  the wizard already tells a clerk so in the panel the PO kept
                  on 2026-09-20 (*"What this sale will not touch"*). A server
                  read would be this screen asking whether a thing the code
                  cannot do had happened. */}
              <TransferFactRow label={t("customers.transferRecord.unchanged.unitMeters")}>
                {t("customers.transferRecord.unchanged.value")}
              </TransferFactRow>
              <TransferFactRow label={t("customers.transferRecord.unchanged.plan")}>
                {t("customers.transferRecord.unchanged.value")}
              </TransferFactRow>
              <TransferFactRow label={t("customers.transferRecord.unchanged.agreements")}>
                {t("customers.transferRecord.unchanged.value")}
              </TransferFactRow>
              {/* ⛔ **STATUS IS A READING AND NOT A RULE.** p132 draws `Active
                  throughout`, which is TRUE of the sale — it closes nothing —
                  and is NOT a statement this screen can make about an account
                  it has not read. So the server sends the status it captured
                  and this screen translates the code. */}
              <Fact
                label={t("customers.transferRecord.unchanged.status")}
                fact={record.unchanged?.status}
                absentLabel={t("customers.transferRecord.absent.notRecorded")}
                // ⚠ **THE REGISTER'S OWN FIVE WORDS** —
                // `customers.accounts.status.*` is what the Accounts list
                // prints for the same five codes, so a status cannot read one
                // way on the register and another way here. Borrowed for the
                // reason the `buyer_kind` row above records.
                render={(value: string) =>
                  t(`customers.accounts.status.${value}`, { defaultValue: "" })
                }
              />
              {/* ⚠ **`38 months` IS AN ILLUSTRATION (B14 rule 37) AND NOTHING
                  COUNTS IT.** The conformance file says so of this exact row —
                  *"nothing counts unbroken months (same gap as step 1's
                  `Ledger` row)"*. So it is a stated absence naming what would
                  close it, never a number this screen worked out. */}
              <Fact
                label={t("customers.transferRecord.unchanged.ledger")}
                fact={record.unchanged?.ledger_months}
                absentLabel={t("customers.transferRecord.absent.notCounted")}
                render={(value: number) =>
                  t("customers.transferRecord.unchanged.ledgerMonths", { count: value })
                }
              />
              {/* CLAUDE.md hard rule 4 is what guarantees this one: an issued
                  invoice, payment or journal entry is never updated, so every
                  document the seller was sent still says what it said. */}
              <TransferFactRow label={t("customers.transferRecord.unchanged.bills")}>
                {t("customers.transferRecord.unchanged.billsValue")}
              </TransferFactRow>
            </dl>
          </Panel>
        </div>

        <div className="flex flex-col gap-6">
          <Panel title={t("customers.transferRecord.section.money")}>
            {/* p132 draws this as a BORDERED BOX inside the section, with the
                total separated by a heavier rule — the same component the move
                record's deposit box uses, at the other end of a tenancy. */}
            <div
              className="mt-2 border border-neutral-300 p-4"
              data-testid="transfer-record-money"
            >
              <p className="text-sm font-semibold text-neutral-900">
                {t("customers.transferRecord.money.box")}
              </p>
              <dl className="mt-2">
                <MoneyRow
                  label={t("customers.transferRecord.money.balance")}
                  fact={record.money?.balance}
                  currency={currency}
                  absentLabel={t("customers.transferRecord.absent.notRecorded")}
                />
                <MoneyRow
                  label={t("customers.transferRecord.money.deposit")}
                  fact={record.money?.deposit}
                  currency={currency}
                  absentLabel={t("customers.transferRecord.absent.notRecorded")}
                />
                {/* ⛔ **NEVER `$0.00` HERE.** Nothing computes deposit interest,
                    and the PO ruled on 2026-09-19 that it is computed at
                    SETTLEMENT. A zero would say the interest was worked out and
                    came to nothing, which on a $150.00 deposit held fourteen
                    months at 2% is wrong by $3.50 AGAINST THE CUSTOMER. */}
                <MoneyRow
                  label={t("customers.transferRecord.money.depositInterest")}
                  fact={record.money?.deposit_interest}
                  currency={currency}
                  absentLabel={t("customers.transferRecord.absent.atSettlement")}
                />
                {/* §4 — `BR-CUS-085`, the two rows this screen exists to prove.
                    `0.0000` is stored precision; `MoneyCell` displays two
                    (CLAUDE.md hard rule 2). */}
                <MoneyRow
                  label={t("customers.transferRecord.money.refunded")}
                  fact={record.money?.refunded}
                  currency={currency}
                  absentLabel={t("customers.transferRecord.absent.notRecorded")}
                  ruled="0.0000"
                />
                <MoneyRow
                  label={t("customers.transferRecord.money.recollected")}
                  fact={record.money?.recollected}
                  currency={currency}
                  absentLabel={t("customers.transferRecord.absent.notRecorded")}
                  ruled="0.0000"
                />
                {/* p132 draws `— there are none`, and no fee exists to draw:
                    the word does not appear in `apps/customers/transfers.py`.
                    A WORD rather than a zero, because "no fee was charged" and
                    "a fee of nothing was charged" are different sentences. */}
                <MoneyRow
                  label={t("customers.transferRecord.money.fees")}
                  fact={record.money?.fees}
                  currency={currency}
                  absentLabel={t("customers.transferRecord.absent.notRecorded")}
                  ruledWords={t("customers.transferRecord.money.noFees")}
                />
              </dl>
              <div className="mt-2 flex items-baseline justify-between gap-4 border-t-2 border-neutral-900 pt-3">
                <span className="text-sm font-semibold text-neutral-900">
                  {t("customers.transferRecord.money.takenOn")}
                </span>
                <span className="text-sm font-semibold text-neutral-900">
                  {record.money?.taken_on?.unavailable ? (
                    <Absent
                      absence={record.money.taken_on.unavailable}
                      label={t("customers.transferRecord.absent.notRecorded")}
                    />
                  ) : record.money?.taken_on?.value ? (
                    <MoneyCell amount={record.money.taken_on.value} currency={currency} />
                  ) : (
                    <span className="text-neutral-600 font-normal">
                      {t("customers.transferRecord.absent.notRecorded")}
                    </span>
                  )}
                </span>
              </div>
            </div>
          </Panel>

          {/* p132's **WHAT THIS RECORD DOES NOT SAY** — one row now (two retired
              2026-09-23, below), a
              standing fact about what a sale does NOT move. None is served and
              none could be: each is a statement about a table this flow never
              writes. */}
          <Panel title={t("customers.transferRecord.section.notSaid")}>
            <dl className="mt-1">
              {/* `OQ-1253` is OPEN — see §3's note. Two words, and the day it
                  closes this row states the answer instead. */}
              <TransferFactRow label={t("customers.transferRecord.notSaid.buyerTold")}>
                {t("customers.transferRecord.notSaid.buyerToldValue")}
              </TransferFactRow>
              {/* ⛔ **TWO ROWS OF p132 ARE REMOVED, NOT REWORDED — THEY BECAME
                  FALSE (`DEF-CUS-6393`, `DEF-CUS-6394`, PO 2026-09-23).** They
                  read *Owner record · Still names the seller* and *Contact
                  details · Still the seller's*. A sale now removes the seller's
                  email, phone and autopay from the account (T3), and moves the
                  premises owner when the account sold is the premises' master
                  account (T2) — so neither is a standing fact any more, and
                  what did change is on the commit's own answer. */}
            </dl>
          </Panel>
        </div>
      </div>
    </div>
  );
}

export default TransferRecordPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: blueprint p132 (rendered at 2x whole-page and 3x/3.5x in three crops,
//         and READ AS AN IMAGE, B14 rule 42) + p133's trace block + the PO's
//         approval (*"buildit - use drawing images. screens hosuld match
//         exactly to drawing"*) + `04-docs/05-modules/03-customers/conformance/
//         transfer-against-its-blueprint.md` §7 + the three PO rulings of
//         2026-09-20 (the wizard walk, the buyer's mailing address, and the
//         seller's customer id)
// generated: 2026-09-20, the transfer-record lane
// exceptions: E1 the banner's second sentence, both grey explanatory
//             paragraphs, the red contact-details box and the dashed reference
//             panel are CUT as rationale (B14 rule 33) — §3 records every one
//             and where its FACT survives · E2 `Open the customer` lands on the
//             customers register filtered to that person, because this product
//             has no customer detail screen — `MoveRecordPage`'s E2, measured
//             again here · E3 p132's dashed panel is STALE: `OQ-426` closed
//             2026-08-27 and transfers ARE numbered, so the reference is
//             rendered from the payload with the server's own absence as its
//             other arm (§2) · E4 the drawn breadcrumb leaf
//             `Accounts / Transfers / TRF-26-0021` is NOT rendered — the shell
//             derives crumbs from its nav config and has no mechanism for a
//             record's leaf, which is the same on `/moves/:ref`; filed rather
//             than fixed, because it is a shell change and this file may not
//             make one
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
