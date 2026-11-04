// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W7 task 7.4 — **S89, the TRANSFERS tab, FRONTEND half.** The
//           read model and `GET /transfers` landed 2026-08-25 carrying
//           `B=deferred(no-frontend-half — S89's rendering is task 7.4's
//           frontend lane)`; the PO reported the hole from a live build:
//           *"nothing on new connect + on all of these screens"*. This is that
//           half.
// Rules:    BR-CUS-015 (`accounts.balance` is a CACHE — the arrear shown is
//           that cache and is named as such by the server) · BR-CUS-024 (the
//           deposit carry mechanics are PROPOSED) · BR-CUS-057 (deposit
//           interest — CONFIRMED, NOT BUILT) · BR-CUS-099 (2026-08-25, closing
//           DEF-688: the `request #` search leg is RULED AWAY, so the box does
//           not offer it) · BR-SHL-010 · BR-SHL-011 (this list owns NO query
//           string — DEF-664) · BR-SHL-025 · CLAUDE.md hard rule 2 (money
//           DISPLAYS at 2 dp — the SERVER rounds, this file never does) ·
//           B14 rules 5, 12, 16, 17, 19, 20, 21
// Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.7.1 (the five
//           tiles) · §5.7.2 (the two-line FROM cell, the stacked MONEY
//           sentences) · §5.7.3 (the ONE JOB callout) · §5.7.6 (the five seeded
//           rows)
// Tests:    07-frontend/src/features/customers/TransfersTab.test.tsx
// Impacts:  AccountsListPage.tsx (the mount + `ACCOUNTS_BUILT_TABS`) ·
//           06-backend `GET /transfers` (live)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 0 · WHAT THIS TAB DESCRIBED UNTIL 2026-09-20, AND WHY IT WAS ALL WRONG
// ══════════════════════════════════════════════════════════════════════════
// `BR-CUS-1030` (PO 2026-09-01) made a transfer a **REASSIGNMENT** — *"dont
// create new account - we reassing that account - bascailly I have sold my
// property"*. The commit that landed it (`d1066469e`) rewrote `transfers.py` by
// **916 lines** and touched this file by **38**, all of which were one added
// sentence and a link. **So the list went on drawing the deleted job for
// nineteen days**, and six of its statements were false rather than merely
// stale (`DEF-CUS-5092`, and the PO's own words looking at it live: *"too much
// text"*):
//
//   · `Open — same customer, new address`   — a sale is a DIFFERENT customer at
//     the SAME address, which is the exact inverse
//   · `Moving this week`                    — nobody moves; it is a sale date
//   · `Deposits carrying`                   — counted an election `OQ-1252`
//     removed the same day
//   · `Arrears following — a debt moving to a new account` — **there is no new
//     account**
//   · the empty state, *"moves the same customer to a new address as one job"* —
//     the case the wizard's own red warning says is NOT a transfer
//   · the `ONE JOB` callout's *"its two halves are deliberately kept out of
//     Move-ins and Move-outs"* — **there are no halves**, and it published an
//     internal counting decision, which B14 rule 33 puts at ZERO words on screen
//
// Rebuilt here to `05-prototype/02 Accounts Menu Blueprint.pdf` **p131, read as
// an IMAGE** (B14 rule 42), against
// `04-docs/05-modules/03-customers/conformance/transfer-against-its-blueprint.md`
// §6. **PO approval, 2026-09-20, verbatim: *"this is correct - please fix it"***.
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · `TAKEN ON` IS ONE FIGURE — THE BALANCE THE BUYER TAKES ON
// ══════════════════════════════════════════════════════════════════════════
// p131 draws a single `TAKEN ON` money column and says, under the table,
// *"Taken on is the balance at the moment of sale, and the buyer owes it."*
// B18 §5.7.2's two STACKED sentences — `deposit carried $153.50` above
// `arrear follows $542.10` — are the old job: **both describe positions that do
// not move**, and the deposit is the one thing a sale deliberately leaves
// exactly where it is. So the cell renders the ARREAR line and nothing else.
//
// ⛔ **THE SERVED PAYLOAD IS UNTOUCHED AND THAT IS DELIBERATE (`DEF-CUS-3653`).**
// `money.lines` still carries the `deposit_carried` line, `money.sentences`,
// `money.gaps` and `money.unavailable` are all still sent, and `TransferMoneyCell`
// still declares them. Retiring a served value without grepping its consumers is
// how an account header silently lost `Austin, TX 78704` on every account with
// `tsc` and every test green. **This screen stopped RENDERING one line; nothing
// stopped SERVING it.**
//
// ⛔ **AND A LINE MAY CARRY NO FIGURE AT ALL**, which is why `lines` is read and
// `sentences` is not: `money.lines` emits its line with `text: null` and
// `amount: {stored: null, display: null}` whenever the figure cannot be read,
// while `sentences` simply omits it — and an omitted sentence is
// indistinguishable from *"nothing is owed"* once rendered.
//
// So the cell obeys three rules and each is asserted:
//
//   1. **It renders the SERVER's sentence figure** — already rounded to 2 dp
//      (hard rule 2: rounding for a human happens once, server-side). Nothing
//      here re-rounds `stored`.
//   2. **When the figure is absent, the ABSENCE is rendered** — the server's
//      reason, as a `role="note"` carrying the rule it tracks in a `data-`
//      attribute, never in the sentence (DEF-332).
//   3. **`$0.00` is never written.** DEF-127: a fabricated zero *"looks exactly
//      like a settled account"*, which on this column would tell a clerk the
//      buyer takes on nothing.
//
// A row with no arrear at all renders `—`, and that dash means NONE.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · `SOLD TO` IS EMPTY UNTIL THE SALE COMMITS, AND IT SAYS SO
// ══════════════════════════════════════════════════════════════════════════
// ⛔ **AMENDED 2026-09-24 (`DEF-CUS-6462`) — THIS SAID `row.customer` BECOMES
// THE BUYER AT COMMIT, AND IT HAS BEEN FALSE SINCE 2026-09-20.** Migration 0060
// (`927f82bb4`) stopped the commit overwriting `transfer.customer`: it is the
// SELLER for good, and the buyer is `buyer_customer_id`, served on the row as
// `buyer` / `buyer_no`. The cell read `row.customer`, so every completed sale
// named its SELLER under `Sold to`. `set_new_customer` — step 2, where the buyer
// is named — **stores nothing at all**, deliberately: a government identifier
// has no encrypted column on a workflow table. So the cell prints `row.buyer`
// once the sale has committed, and states the absence before that.
//
// ⛔ **`SOLD BY` IS DRAWN ON p131 AND IS NOT BUILT, BY RULING.** ⚠ The reason
// below stopped being true on 2026-09-20 — `row.customer` IS the seller now —
// and the ruling still holds the column; `DEF-CUS-5976` owns it. As written: the
// seller was overwritten at commit and survived only in the commit response's
// `reassignment` block and in `audit_log`, **which is pruned on a retention
// schedule** (hard rule 4's own warning). A `Sold by` column would therefore be
// empty on exactly the rows a clerk needs it — the completed ones — or would be
// faked from a log that gets deleted. PO, 2026-09-20: *"Two held deliberately:
// Sold by and ↗ Open. Both would need faking — one from a pruned audit log, one
// pointing at a page that doesn't exist. That's the defect we spent yesterday
// removing."* It needs a `sold_by` served from a column of its own; that is
// `DEF-CUS-5976` and it is a backend leg.
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · WHAT p131 DRAWS THAT THIS DOES NOT, EACH WITH ITS REASON
// ══════════════════════════════════════════════════════════════════════════
//   * **The `SOLD BY` column** — §2 above. `DEF-CUS-5976`.
//   * ✅ **The `↗ Open` row action — BUILT 2026-09-24, AND THE TWO HOLDS THAT
//     DELAYED IT ARE WORTH READING BEFORE ANYBODY WRITES A THIRD
//     (`DEF-CUS-6532`).** PO, looking at a `Done` row on a live tenant: *"also
//     this done request - we are unabel to open - view should be available -
//     all the time"*. The column is live on EVERY row in EVERY state; the
//     whole argument sits on the column itself, below.
//     **Hold 1** read *"there is no transfer record page at any address"* —
//     true when written, and the expiry test hard-won law 2's mirror asks for
//     was landed with it. A sibling mounted `TRANSFER_RECORD_ROUTE` the same
//     day and the test went RED naming this column, *"expected true to be
//     false"*, exactly as designed.
//     **Hold 2 is the one that rotted, and it rotted BECAUSE it was
//     re-pointed.** It became *"`GET /transfers/{ref}` is not mounted"* — a
//     BACKEND fact — while every assertion the test kept is a FRONTEND one.
//     `transfer_record_api.py` landed 2026-09-20 in `86a28f23d`; the condition
//     expired that day and the case went on passing green for four days.
//     **A vitest case cannot watch a Django urlpattern. Re-pointing a hold
//     across a tier boundary leaves you with something that LOOKS like an
//     expiry test and is not one.** `DEF-CUS-5982` closes here.
//   * **`Open · Selling this week · Completed · All` segments.** B14 rule 12
//     replaced the fixed strip with removable chips over `+ Filter ▾`; the
//     Move-outs file records the same refusal for the same reason.
//   * **`⇩ Export`.** Nothing registers a `transfers` export resource, so
//     `POST /exports` answers a plain 404 — `BR-SHL-010` / `DEF-1005`, and a
//     button wired to a 404 is law 2 again.
//   * **A sort on `Sale date`.** `transfer_reads.SORTS["out_date"]` orders by
//     `from_account__closed_at`, which was right while a transfer CLOSED the
//     outgoing account and has been NULL on every live row since
//     `BR-CUS-1030` removed the closure. A date header that reorders rows by
//     nothing is a control telling a clerk something untrue, so the column is
//     not declared sortable until the server's term names `transfers.out_date`.
//     `DEF-CUS-5975`.
//   * **The search prompt.** p131 draws *"Search by reference, account, address
//     or name"*; the box says *"Customer, account #, or either address…"*, which
//     is `transfer_reads.SEARCH_HINT` verbatim and a **backend** constant. The
//     two must move together or the screen starts lying about what it matches
//     (DEF-950). `DEF-CUS-5978`.
//
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FilterBar, offerableFilters } from "@/components/FilterBar";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { EyeIcon } from "@/components/icons";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { defaultRequestState } from "@/components/tableTypes";
import type {
  TableConfig,
  TableFilterConfig,
  TableRequestState,
} from "@/components/tableTypes";
import { useTenantPath } from "@/routing/tenantPath";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";

// ⚠ **THE ROUTE CONSTANT, NEVER A TYPED PATH.** `CR-058` task 16 sends a
// clerk from here to the OTHER door, and a hand-written string is how the
// two drift — the route already moved once (`/requests`, not
// `/service-requests`).
// `DEF-CUS-5994` — the three controls the five worklists share, now that a
// parked draft is a ROW rather than a panel above the table.
import {
  ParkedBadge,
  ParkedDiscardDialog,
  ParkedDraftActions,
  ParkedWhyCell,
} from "./parkedDrafts";
import type { ParkedDiscardTarget } from "./parkedDrafts";
import { SERVICE_REQUEST_NEW_ROUTE } from "./serviceRequestShared";
// ⚠ **THE RECORD LANE'S OWN HELPER, NEVER A RETYPED `/transfers/${ref}`.**
// `DisconnectsTab` took the same decision for the same reason: two spellings
// of one address is how a door starts pointing at nothing, and it is the
// defect that let this tab's own hold pass over a live screen
// (`DEF-CUS-6042`, and `DEF-CUS-6532` one level up).
import { transferRecordPath } from "./TransferRecordPage";
import { RecordNumberCell, TRANSFER_WIZARD_ROUTE } from "./transferDisconnectShared";
import { listTransfers, rowsOf, totalOf } from "./worklistEndpoints";
// ⛔ `TransferMoneyLine` is NOT imported any more, and that is the ONE place
// this rebuild's "nothing served was retired" claim could quietly become false.
// The TYPE still exists and `TransferMoneyCell.lines` is still declared with
// it; what went is this file's own use of it, when the two stacked sentences
// became one `Taken on` figure. The server still sends both lines.
import type {
  TransferList,
  TransferMoneyCell,
  TransferRow,
  WorklistFilterState,
} from "./worklistEndpoints";

/** The screen id `TableConfig` keys its column preference on. **No story owns
 *  S89** — `transfer_reads.py` filed the finding for the read half and
 *  `transfers.py` for the write half (hard-won law 8). REPORTED again, not
 *  invented. */
export const TRANSFERS_TABLE_SCREEN = "S89";

/** §5.7.2 draws the arrear sentence in **amber**, and `lines[].tone` carries
 *  that decision as DATA so it is made once, in the design.
 *
 *  ⚠ A tone this map does not know renders as ordinary ink rather than as
 *  nothing: an unrecognised tone must not make a money sentence disappear. */
const LINE_TONE_CLASS: Record<string, string> = {
  ink: "text-text",
  amber: "text-warning-700",
};

export function transferLineToneClass(tone: string): string {
  return LINE_TONE_CLASS[tone] ?? LINE_TONE_CLASS.ink;
}

/**
 * English fallbacks for the STATE vocabulary — `defaultValue`s, not copy.
 *
 * Every string reaches the screen through `t(key, {defaultValue})`, so the
 * catalogues own the words the moment the locale lane adds the keys. This lane
 * may not edit `src/i18n/locales/*.json`, and a raw
 * `customers.transfers.state.in_progress` on the tab would be a second defect
 * on top of the empty one being fixed. Keys and sentences are REPORTED.
 *
 * §5.7.6 spells them `Done` · `In progress` · `Scheduled`.
 */
const STATE_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  in_progress: "In progress",
  done: "Done",
  cancelled: "Cancelled",
};

/**
 * B18 §5.7.6's STATE column.
 *
 * ⚠ **B18 DRAWS NO TONE HERE**, so this mapping is the SCREEN's and is stated
 * as such: a committed job reads success, one in flight reads warning, and a
 * scheduled one is neutral. Cancelled transfers are not listed at all
 * (`list_queryset` excludes them), which is stated in the backend and is worth
 * knowing here: a clerk cannot currently find one.
 */
export function transferStateTone(state: string): StatusTone {
  if (state === "done") {
    return "success";
  }
  if (state === "in_progress") {
    return "warning";
  }
  return "neutral";
}

/** `transfer_reads.LINE_ARREAR` — the kind of the one line this column draws. */
const ARREAR_LINE = "arrear_follows";

/**
 * p131's `TAKEN ON` — §1 of this file's header, rendered.
 *
 * The three shapes, and all three occur in §5.7.6's own five rows:
 *   · a readable arrear   → `$542.10`, in the tone the SERVER decided;
 *   · an arrear with no readable figure → the server's REASON, never `$0.00`;
 *   · no arrear at all    → `—`, which means NONE and is the only dash here.
 *
 * ⚠ **THE CELL-LEVEL `unavailable` RIDES IN THE TITLE, NOT AS PARAGRAPHS PER
 * ROW.** On a row carrying both a deposit and an arrear the server names four
 * to five reasons why nothing moves. Printing them on every row would be the
 * page-level *"what this cannot do yet"* panel the PO deleted on 2026-08-24,
 * merely repeated per row — and B14 rule 33 puts rationale at zero words on
 * screen. They stay reachable on the cell they are about (BR-SHL-025's
 * placement), while the absence a reader MUST see — a figure that could not be
 * read — is rendered as visible text.
 */
export function TakenOnCell(props: { money: TransferMoneyCell }) {
  const { money } = props;
  const why = money.unavailable.map((row) => row.detail).join(" ");
  const arrear = money.lines.find((line) => line.kind === ARREAR_LINE) ?? null;

  if (arrear === null) {
    // §5.7.6's `A-11109 · Osei, Grace` — nothing owed. This dash means NONE.
    return (
      <span className="text-neutral-700" title={why} data-taken-on-none="">
        —
      </span>
    );
  }
  if (arrear.amount.display === null) {
    // ⛔ NO FIGURE. The balance exists and cannot be read, so the REASON is what
    // renders. The tracking id is a `data-` attribute and never part of the
    // sentence (DEF-332 — our internal ids mean nothing to a billing clerk).
    return (
      <span
        role="note"
        className="block text-sm text-neutral-700"
        title={why}
        data-taken-on-absent=""
        data-tracks={arrear.unavailable?.br_ref ?? arrear.unavailable?.code}
      >
        {arrear.unavailable?.detail ?? ""}
      </span>
    );
  }
  // ⚠ ONE FIGURE, the server's, already rounded to 2 dp (hard rule 2 — rounding
  // for a human happens once, server-side).
  //
  // ⚠ **THE AMBER IS KEPT, AND IT IS A JUDGEMENT RATHER THAN AN OVERSIGHT.**
  // p131 draws `TAKEN ON $64.20` in plain ink; `line.tone` arrives as `amber`,
  // because B18 §5.7.2 decided that for the arrear SENTENCE and the server
  // carries the decision as DATA so it is made once. Two reasons to keep it and
  // both are written down rather than assumed: B14 rule 37 says a figure drawn
  // in a wireframe is an ILLUSTRATION, and reading "black" off line art is
  // weaker evidence than a decision somebody made on purpose; and dropping it
  // here would make this file a SECOND place deciding the tone, which is the
  // shape §5.7.2 put it in the payload to avoid. Verified in a browser at 1440
  // and 1280 on 2026-09-20 — it reads as money the buyer takes on, which is the
  // column's whole point. **Stamped as a divergence from the drawing** (B14
  // requires every divergence stamped) and reported; a ruling either way is
  // cheap to apply, because it is this one expression.
  return (
    <span
      className={`tabular-nums ${transferLineToneClass(arrear.tone)}`}
      title={why}
      data-taken-on={arrear.amount.display}
    >
      {`$${arrear.amount.display}`}
    </span>
  );
}

/**
 * The one dimension `TRF-01` declares, built FROM THE PAYLOAD (CR-045 wave G,
 * `DEF-1702`).
 *
 * ⚠ **THE VOCABULARY IS THE SERVER'S AND IS NEVER TYPED HERE (BR-SHL-010).**
 * `transfer_reads.TRANSFER_FILTER_STATES` is `Transfer.STATES` minus
 * `cancelled`, computed by SUBTRACTION from the list's own exclusion — so the
 * day a state is added, or `cancelled` is re-admitted (`DEF-1004`), this panel
 * follows without an edit. Hardcoding the four here is how an option that can
 * never return a row gets offered, and `STATE_LABELS` above is a `defaultValue`
 * map rather than a vocabulary for exactly that reason.
 *
 * Before the first response there is nothing to offer, so the group is empty
 * and `offerableFilters` drops it — the panel shows no legend over nothing
 * (`DEF-782`).
 */
export function transferFilterGroups(
  states: WorklistFilterState[] | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
): TableFilterConfig[] {
  return [
    {
      name: "state",
      label: t("customers.transfers.col.state", { defaultValue: "State" }),
      options: (states ?? []).map((state) => ({
        value: state.code,
        label: t(`customers.transfers.state.${state.code}`, {
          defaultValue: STATE_LABELS[state.code] ?? state.code,
        }),
      })),
    },
  ];
}

export function transfersTableConfig(
  t: (key: string, params?: Record<string, unknown>) => string,
  cells: {
    // ⚠ **ONE DATE CELL, NOT TWO.** `out_date` and `in_date` are written to the
    // SAME day by `transfers.set_sale_date` — *"One date, not two"* — so two
    // columns were equal by construction and p131 draws one `SALE DATE`.
    saleDate: (row: TransferRow) => JSX.Element;
    state: (row: TransferRow) => JSX.Element;
  },
  // ⚠ **THE DOOR IS A REQUIRED ARGUMENT, NOT A CELL THE CALLER MAY OMIT, AND
  // THAT IS THIS DEFECT'S SHAPE ANSWERED IN THE TYPE (`DEF-CUS-6532`).**
  // `DisconnectsTab` builds its `↗ Open` at the call site as `cells.actions`,
  // which works and leaves the door OPTIONAL — a caller can hand in a cell
  // that renders nothing and every check stays green, which is hard-won law
  // 2's mirror with a shorter fuse. Taking the path builder instead means the
  // column, its address and its refusal are all the config's own: there is no
  // way to construct this table without the door in it.
  tenantPath: (segment: string) => string,
): TableConfig<TransferRow> {
  return {
    screenId: TRANSFERS_TABLE_SCREEN,
    getRowId: (row) => row.id,
    // ⚠ **THESE ARE THE SERVER'S LEGS AND THEY ARE LEFT EXACTLY AS SERVED.**
    // `transfer_reads.list_queryset` still matches `to_unit_id`, so declaring
    // three here would make this screen's claim about the box NARROWER than
    // what the box can answer — and a search prompt that under-promises is the
    // mirror of DEF-950's over-promise. `to_address` is dead in PRACTICE (no
    // live path sets `to_unit_id` any more) and that is the backend's finding
    // to make, filed rather than assumed here.
    searchFields: ["customer", "account_no", "from_address", "to_address"],
    // ✅ **B14 rule 19's prompt is WIRED (CR-041 task 2).** The key existed in
    // all eleven catalogues and no screen pointed at it — hard-won law 2, the
    // copy translated and unreachable while the box said "Search this list".
    // The sentence is the server's own AMENDED `SEARCH_HINT` (BR-CUS-099,
    // 2026-08-25 — the PO ruled the `request #` leg away rather than adding the
    // link, so the old four-leg wording must NOT come back), and the catalogue
    // string was checked against `transfer_reads.SEARCH_HINT` before wiring:
    // three legs on both sides.
    searchPlaceholder: "customers.transfers.list.searchPlaceholder",
    // ── CR-045 wave G · `DEF-1702` — STATE, and state only ────────────────
    // ⚠ **THE DIMENSION IS DECLARED HERE; THE OPTIONS ARE NOT, AND THE SPLIT IS
    // DELIBERATE.** `parseTableParams`/`serializeTableParams` read only
    // `filter.name` — that is what makes `?f.state=done` survive a reload
    // (BR-SHL-011) — and the name is a static capability of this screen. The
    // VALUES are the server's and arrive on the response, so this call passes
    // no states and yields the zero-option shape. The panel is handed
    // `transferFilterGroups(listQuery.data?.states, …)` at render, which is the
    // same builder with the served vocabulary in it.
    filters: transferFilterGroups(undefined, t),
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
    // ⚠ **THIS TAB'S ORDERING DID NOT CHANGE — ONLY THE CONTROL IS NEW.** It
    // already opened newest-first, which is why `BR-CUS-1046` asked nothing of it;
    // what it had no answer to was the rule's second clause, because there was no
    // sort to choose. The key is renamed `created_at` → `created` to match the
    // server's vocabulary, which is now a real parameter rather than a label.
    defaultSort: { sort: "created", dir: "desc" },
    columns: [
      {
        // ⚠ **CR-039 WAVE D TASK 15 — AND p131 NOW DRAWS IT FIRST TOO.** It was
        // a NINTH column over B18's eight when it landed, stamped as a
        // divergence; the 2026-09-12 redesign adopted it and leads with it, so
        // the divergence is closed rather than carried.
        key: "reference",
        // `BR-CUS-1046` — SORTABLE, and the key IS the server's sort name.
        sortable: true,
        label: t("customers.transfers.col.reference", { defaultValue: "Reference" }),
        cell: (row) => (
          <RecordNumberCell
            number={row.transfer_no}
            unavailable={row.transfer_no_unavailable}
            kind="transfer"
          />
        ),
      },
      {
        // p131's `ADDRESS` — **the property being sold**, and the reason the
        // column earns its place: under `BR-CUS-1030` the address is the one
        // thing that does NOT change, so it is what a clerk recognises a row
        // by. Served already as `from_to.from`, through metering's own
        // `_premise_cell` (hard rule 8 — every address is walked to `premises`
        // and this screen composes none of its own).
        key: "address",
        label: t("customers.transfers.col.address", { defaultValue: "Address" }),
        cell: (row) => (
          <span data-address-cell="">{row.from_to.from ?? "—"}</span>
        ),
      },
      {
        // ⚠ **ONE ACCOUNT, ONE LINE.** This was a two-line cell — `A-10650`
        // over `→ A-11940` — and **the arrow was the second account the ruling
        // deleted**. `reassign_account` sets `to_account_id` to the SAME
        // account it started from, on purpose (*"a reader asking what this
        // transfer did is told it moved one account rather than made a
        // second"*), so the second line rendered `A-11455 → A-11455` on every
        // completed sale.
        //
        // ⛔ `from_cell` — the server's two strings, dash included — is STILL
        // SERVED and still typed (`DEF-CUS-3653`); this column reads the plain
        // `from_account_no` instead. TC-TRF-2 (*"`→ —`, not a blank"*) described
        // the two-line cell and therefore describes a cell that no longer
        // exists; it is retired with the job it belonged to, not failed.
        key: "from_account",
        label: t("customers.transfers.col.account", { defaultValue: "Account" }),
        identity: true,
        cell: (row) => (
          <span className="tabular-nums" data-account-cell="">
            {row.from_account_no}
          </span>
        ),
      },
      {
        // p131's `SOLD TO` — §2 of this file's header. The buyer, and ONLY once
        // the sale has committed.
        // ⛔ **`row.buyer`, NEVER `row.customer` — `DEF-CUS-6462`.** This cell
        // drew `row.customer` on the premise that the commit overwrote it with
        // the buyer. Since 2026-09-20 (migration 0060) `customer` is the SELLER
        // for good, so every completed sale named its seller under `Sold to`.
        key: "customer",
        label: t("customers.transfers.col.soldTo", { defaultValue: "Sold to" }),
        cell: (row) =>
          row.committed_at !== null && row.buyer ? (
            <span className="inline-flex flex-col" data-sold-to="">
              <span>{row.buyer}</span>
              <span className="tabular-nums text-neutral-700">{row.buyer_no}</span>
            </span>
          ) : (
            // A STAGE of the job, said in words rather than left as a blank —
            // the posture the `to_absence` note used, kept where it is still
            // true. `set_new_customer` names the buyer and stores nothing.
            <span role="note" className="text-sm text-neutral-700" data-sold-to-absent="">
              {t("customers.transfers.soldToAbsent", {
                defaultValue: "Recorded when the sale completes.",
              })}
            </span>
          ),
      },
      {
        // p131's `SALE DATE`. ⚠ **THE KEY STAYS `out_date` BECAUSE IT IS THE
        // SERVER'S NAME**, not a label: renaming it here would point the column
        // preference and the sort parameter at a word the server does not know.
        //
        // ⛔ **NOT SORTABLE, AND THAT IS A REFUSAL RATHER THAN AN OMISSION.**
        // `SORTS["out_date"]` orders by `from_account__closed_at` — correct
        // while a transfer CLOSED the outgoing account, NULL on every live row
        // since `BR-CUS-1030` removed the closure. A header that reorders rows
        // by nothing is hard-won law 2's mirror. `DEF-CUS-5975`; the column
        // gains `sortable` back the day the term names `transfers.out_date`.
        key: "out_date",
        label: t("customers.transfers.col.saleDate", { defaultValue: "Sale date" }),
        cell: cells.saleDate,
      },
      {
        key: "step",
        label: t("customers.transfers.col.step", { defaultValue: "Step" }),
        // `3 of 5`, built server-side from the writer's own STEP_COUNT so a
        // sixth step could never be silently restated here. The step's NAME is
        // the tooltip — the column is one cell wide and the label is a sentence.
        cell: (row) => (
          <span className="tabular-nums" title={row.step_label ?? undefined} data-step-cell="">
            {row.step_cell}
          </span>
        ),
      },
      {
        // p131's `TAKEN ON` — ONE figure, §1 of this file's header.
        key: "money",
        label: t("customers.transfers.col.takenOn", { defaultValue: "Taken on" }),
        cell: (row) => <TakenOnCell money={row.money} />,
      },
      {
        key: "state",
        // `BR-CUS-1046` — SORTABLE, and the key IS the server's sort name.
        sortable: true,
        label: t("customers.transfers.col.state", { defaultValue: "State" }),
        cell: cells.state,
      },
      {
        // ══════════════════════════════════════════════════════════════════
        // `↗ Open` — THE HOLD THAT ROTTED, AND THE DOOR IS NEVER STATE-GATED
        // ══════════════════════════════════════════════════════════════════
        // PO ruling 2026-09-24, verbatim, looking at a `Done` row on Ottumwa
        // Water Works: *"also this done request - we are unabel to open - view
        // should be available - all the time"*.
        //
        // **THE RULING IS GENERAL AND THE TWO HALVES ARE BOTH LOAD-BEARING.**
        // A record opens in EVERY state — done, in progress, scheduled,
        // parked, cancelled — and what a clerk cannot DO with it is disabled
        // ON THE RECORD PAGE carrying its own reason. Removing the door is
        // never how a product says "there is nothing left to decide here".
        // `TransferRecordPage` already says exactly that about itself: it has
        // two doors out and no verbs, by the blueprint's own ruling. So there
        // was never anything to gate.
        //
        // **WHY IT WAS MISSING FOR FOUR DAYS, BECAUSE IT IS THE USEFUL PART.**
        // This column was held twice, and the second hold is the one that
        // rotted. The first said *"no transfer record page exists at any
        // address"* — true when written, and `TransfersTab.test.tsx` carried
        // the expiry test hard-won law 2's mirror prescribes. A sibling
        // mounted `TRANSFER_RECORD_ROUTE` hours later and that test went RED
        // by name, exactly as designed. It was then RE-POINTED at a narrower
        // hold — *"`GET /transfers/{ref}` is not mounted"* — and **every
        // assertion it kept is a FRONTEND fact**: the route matches, `new` is
        // not swallowed, no `/transfers/` href is rendered. None of them can
        // see a Django urlpattern. `transfer_record_api.py` landed on
        // 2026-09-20 in `86a28f23d`, the hold's stated condition expired that
        // day, and the case went on passing GREEN for four days.
        //
        // ⚠ **THE LESSON IS NOT "WRITE AN EXPIRY TEST" — THIS FILE HAD ONE.**
        // It is that **a hold re-pointed at a condition in another tier has no
        // expiry test at all**, only one that looks like it. A vitest case
        // cannot watch a backend route. Either assert the new condition where
        // it lives, or release the hold and file the remainder as its own row.
        //
        // ⚠ **B14 RULE 44 (ratified today) AND RULE 15 DECIDE HOW, NOT
        // WHETHER.** p133 draws `↗ Open` as a bordered, labelled button on the
        // right of EVERY row — on the `Completed` row and the `In progress`
        // row alike, which is the PO's ruling drawn a fortnight before they
        // said it. The drawing says WHAT is on the screen; our UI standard
        // says HOW it is built, and it wins every time. Rule 15 makes a row
        // action an UNLABELLED ICON with a tooltip, so a labelled button here
        // would change every table in the product on one screen's authority.
        // `DisconnectsTab` stamped the identical divergence against p142.
        //
        // ⚠ **NO DATABASE ID REACHES THE SCREEN OR THE ADDRESS (rule 31).**
        // The link is built by `transferRecordPath` from the transfer NUMBER —
        // what a clerk quotes down a phone. The reader accepts a uuid as a way
        // IN for a tenant whose numbering series predates the catalogue row,
        // and that is never a way to WRITE one: a row with no reference is
        // disabled with its reason (BR-SHL-025), never opened by id.
        //
        // ⚠ **AND NOTHING IS EXPLAINED BESIDE THE CONTROL (rule 33).** The
        // tooltip names the act in three words; why a record has no verbs is
        // rationale, and rationale is zero words on screen.
        key: "actions",
        label: t("customers.transfers.col.actions", { defaultValue: "Actions" }),
        cell: (row) => (
          <RowActions>
            <RowActionLink
              label={t("customers.transfers.action.open", {
                defaultValue: "Open the transfer",
              })}
              icon={<EyeIcon />}
              // BR-SHL-025 — the record is addressed by its REFERENCE, so a
              // row that has none cannot be addressed and says so rather than
              // losing its control. This is NOT a state gate: it is the same
              // absence `RecordNumberCell` already draws in the first column,
              // and it is the tenant's numbering series, never the sale's
              // progress.
              reason={
                (row.transfer_no ?? "") === ""
                  ? t("customers.transfers.action.openBlocked", {
                      defaultValue: "This row has no reference.",
                    })
                  : null
              }
              to={tenantPath(transferRecordPath(String(row.transfer_no)).slice(1))}
            />
          </RowActions>
        ),
      },
    ],
  };
}

export function transfersQueryKey(state: TableRequestState): readonly unknown[] {
  // `state.filters` is IN THE KEY, and leaving it out is the bug that makes a
  // filter look broken: react-query would serve the unfiltered page from cache
  // for the filtered request and the list would not move (CR-045 wave G).
  // `state.sort`/`state.dir` in the key — see `moveInsQueryKey`.
  return [
    "transfers",
    state.q,
    state.page,
    state.per,
    state.filters,
    state.sort,
    state.dir,
  ];
}

/**
 * p131's THREE tiles — `OPEN` · `SELLING THIS WEEK` · `OWED ON ACCOUNTS BEING
 * SOLD`. B18 §5.7.1 drew FIVE and three of them counted the deleted job.
 *
 * ⛔ **THE THREE THAT CAME OFF, AND WHY EACH IS WRONG RATHER THAN MERELY
 * UNDRAWN:**
 *   · `Deposits carrying — not refunded and re-collected` counts
 *     `deposit_carry_elected`, an ELECTION `OQ-1252` removed on 2026-09-01. A
 *     sale leaves the deposit exactly where it is; nobody chooses it any more,
 *     so the tile counts a decision that is never made.
 *   · `Arrears following — a debt moving to a new account` says **there is a new
 *     account**. There is not. The debt stays on the one account, which is the
 *     whole of `BR-CUS-1030`.
 *   · `Completed this month — one job, not two` is not drawn, and its caption is
 *     the counting contract again.
 *
 * ⛔ **AND ALL FIVE COUNTS ARE STILL SERVED (`DEF-CUS-3653`).** `kpi_strip`
 * returns `deposits_carrying`, `arrears_following` and `completed_this_month`
 * untouched, `TransferKpis` still declares them, and two backend suites still
 * assert them. **This screen stopped DRAWING three tiles; nothing stopped
 * SERVING their fields** — retiring a value without grepping its consumers is
 * how an account header silently lost its locality line on every account.
 *
 * ⚠ **`OWED ON ACCOUNTS BEING SOLD` IS A SUM AND NO SUM IS SERVED.** `kpi_strip`
 * returns five COUNTS and no money (`transfer_reads.py:538`). The tile is drawn
 * because p131 draws it and a clerk needs it — it is the one figure on this
 * screen that is money — and it **states the absence rather than inventing a
 * zero**: `$0.00` on a money tile is a claim that nothing is owed, which is
 * DEF-127's *"looks exactly like a settled account"* at strip scale. It becomes
 * a `money` tile the day the server sums it — `DEF-CUS-5979`.
 */
export function transfersKpis(
  payload: TransferList | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
): KpiTile[] {
  const kpis = payload?.kpis;
  return [
    {
      id: "open",
      label: t("customers.transfers.kpi.open", { defaultValue: "Open" }),
      value: kpis?.open ?? 0,
      detail: t("customers.transfers.kpi.openDetail", {
        defaultValue: "a sale part-way through",
      }),
    },
    {
      id: "selling-this-week",
      // ⚠ **THE WORD MOVED, THE ARITHMETIC DID NOT.** `_within_the_week` reads
      // `out_date`, which `set_sale_date` writes as the day of SALE — so the
      // count was always right and only the label said "moving".
      label: t("customers.transfers.kpi.sellingThisWeek", {
        defaultValue: "Selling this week",
      }),
      value: kpis?.moving_this_week ?? 0,
      detail: t("customers.transfers.kpi.sellingThisWeekDetail", {
        defaultValue: "sale date within 7 days",
      }),
    },
    {
      id: "owed-on-accounts-being-sold",
      label: t("customers.transfers.kpi.owed", {
        defaultValue: "Owed on accounts being sold",
      }),
      // ⛔ A STATED ABSENCE, NEVER A ZERO — see this function's docstring. It is
      // `value` and not `money`, because `KpiMoney` requires an `amount` and
      // there is no amount to give it: the type would have to be lied to.
      value: (
        <span role="note" className="text-neutral-700" data-kpi-absent="owed">
          {t("customers.transfers.kpi.owedAbsent", { defaultValue: "Not available" })}
        </span>
      ),
    },
  ];
}

export interface TransfersTabProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function TransfersTab(props: TransfersTabProps) {
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
      transfersTableConfig(translate, {
        // ⚠ **`out_date` IS THE SALE DAY.** `set_sale_date` writes ONE keyed
        // date to BOTH `out_date` and `in_date`, so `same_day` is true by
        // construction and the second column was the first one again.
        saleDate: (row) =>
          row.out_date === null ? (
            <span aria-hidden="true">—</span>
          ) : (
            <DateCell value={row.out_date} timeZone={timeZone} dateFormat={dateFormat} />
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
            <span className="flex flex-col items-start gap-1" data-transfer-draft={row.park_id}>
              <ParkedBadge parked={(row.waiting_on ?? "") !== ""} t={translate} />
              <ParkedWhyCell row={row} timeZone={timeZone} dateFormat={dateFormat} />
              <ParkedDraftActions
                flow="transfer"
                onDiscard={setDiscarding}
                parkId={String(row.park_id)}
                subjectLabel={row.customer ?? row.from_account_no ?? ""}
              />
            </span>
          ) : (
            <StatusPill tone={transferStateTone(row.state)}>
              {translate(`customers.transfers.state.${row.state}`, {
                defaultValue: STATE_LABELS[row.state] ?? row.state,
              })}
            </StatusPill>
          ),
      }, tenantPath),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, timeZone, dateFormat],
  );

  // DEF-664 — the table state is THIS COMPONENT'S. The query string belongs to
  // the Accounts page this tab sits inside, and is neither read nor written
  // here. See `NewConnectsTab` §1 for the whole rule and its stated price.
  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  const listQuery = useQuery({
    queryKey: transfersQueryKey(state),
    queryFn: () =>
      listTransfers(
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

  // ⛔ **THE SERVER'S `exclusion.callout` IS NO LONGER RENDERED, AND THE READ
  // IS KEPT SO THE REASON DOES NOT VANISH WITH IT.**
  //
  // It said, verbatim: *"A transfer appears only here. Its two halves are
  // deliberately kept out of Move-ins and Move-outs — the same job listed three
  // times would be counted three times."* **There are no halves.** Nothing is
  // closed and nothing is opened, so a sale has exactly one account and the
  // sentence describes the deleted job. And even corrected it would not belong
  // on a screen: it explains an INTERNAL COUNTING DECISION between three tabs,
  // which is rationale, which B14 rule 33 puts at **zero words on screen**.
  //
  // ⚠ **THE CONTRACT ITSELF IS REAL AND IS NOT BEING DISPUTED HERE.**
  // `exclusion.contract` and `exclusion.half_account_ids` are still served,
  // still asserted server-side, and `transfer_half_account_ids()` still governs
  // what the Move-ins and Move-outs lists subtract — a contract that is now
  // deleting genuine move-outs from another screen (`DEF-CUS-5913`). It is a
  // rule between MODULES; a clerk is not a party to it.
  //
  // ⚠ **THE OPTIONAL CHAIN IS KEPT DOUBLE (DEF-781).** It read
  // `listQuery.data?.exclusion.callout`, which guards a missing RESPONSE and
  // not a missing `exclusion` BLOCK, so any envelope without one took the whole
  // Accounts screen down with `TypeError: Cannot read properties of undefined`.
  // `tsc` was satisfied because the type declares `exclusion` non-optional, and
  // no test could build the failing payload for exactly that reason.
  const calloutServed = listQuery.data?.exclusion?.callout ?? null;

  return (
    <div data-embedded="" data-screen={TRANSFERS_TABLE_SCREEN} data-callout-served={calloutServed !== null ? "" : undefined}>
      {/* `DEF-CUS-5994` — the parked draft's DISCARD confirmation, mounted ONCE
          and ABOVE the table. It is here rather than in the row because a
          `DataTable` cell is unmounted and remounted on every render
          (`DEF-CUS-6011`), so state set by a click inside one does not survive
          the render that click causes. It draws nothing until a clerk asks. */}
      <ParkedDiscardDialog
        flow="transfer"
        target={discarding}
        onClose={() => setDiscarding(null)}
        client={client}
      />
      <KPIStrip kpis={transfersKpis(listQuery.data, translate)} loading={listQuery.isPending} />

      {/* p131's red note, and ONLY its first clause. The drawing reads *"One
          account, not two — and that is the whole point of this flow. A sale
          reassigns the account that is already at the address: the number, the
          unit, the meters and the ledger all stay, and the customer changes."*
          The four words before the dash are the FACT; the thirty after it are
          RATIONALE, which rule 33 puts at zero words on screen and which the PO
          named on this very tab — *"too much text"*. */}
      <p
        className="mb-3 border-l-2 border-danger-500 pl-3 text-sm font-semibold text-danger-700"
        data-one-account-callout=""
      >
        {t("customers.transfers.list.oneAccount", { defaultValue: "One account, not two." })}
      </p>

      {/* ⛔ **CR-058 TASK 16 · BR-CUS-1031 — SAID WHERE A CLERK WOULD OTHERWISE
          REACH FOR TRANSFER.**

          PO ruling 2026-09-01, verbatim: *"dont create new account - we
          reassing that account - bascailly I have sold my property - so account
          get transfer to new person or business; **if I move to new location
          then it is new Service request and we follow the process**"*.

          **Two different jobs used to be one door, and the door that existed
          did the WRONG one of them.** A clerk arriving here with a customer who
          is moving house has to be told, HERE, or they will use the wrong door
          and split an address's history in two.

          ⚠ **SHORTENED 2026-09-20, NOT DELETED.** It was one 27-word paragraph;
          rule 33 caps an INSTRUCTION at six words PER SENTENCE and says two
          sentences of six beat one of twelve. Both halves survive — what a
          transfer IS, and what to do instead — because rule 33's hardest clause
          is *shorten by deleting RATIONALE, never INSTRUCTION*. */}
      <p className="mb-3 text-sm text-neutral-700" data-moving-is-a-service-request="">
        {t("customers.transfers.list.movingIsARequest", {
          defaultValue: "A transfer is a sale. Moving house needs a service request.",
        })}{" "}
        <Link className="text-accent underline" to={tenantPath(SERVICE_REQUEST_NEW_ROUTE)}>
          {t("customers.transfers.list.movingIsARequestLink", {
            defaultValue: "Start a service request",
          })}
        </Link>
      </p>

      {/* ⚠ **THIS SLOT WAS EMPTY UNTIL CR-045 WAVE G, AND THE SENTENCE THAT
          EXPLAINED WHY IS NOW FALSE — IT IS KEPT AND CORRECTED RATHER THAN
          DELETED (hard-won law 1, `DEF-1702`).**

          It read, verbatim: *"There is also nothing a `+ Filter ▾` panel could
          offer: `config.filters` is undeclared, and `transfer_reads.list_queryset`
          reads `q` and nothing else — no `filters` argument reaches it."* That
          was true when written and stopped being true on 2026-08-27, when
          `TRANSFER_FILTERS = ("state",)` landed and `list_queryset` grew its
          `filters` argument. **The comment outlived the fact by a day, and the
          screen stayed bare because nothing re-read it** — which is the exact
          shape of the escape `DEF-1702` records.

          ⚠ **THE OTHER HALF OF THAT SENTENCE STILL HOLDS AND IS NOT A FILTER.**
          EP-CUS-08 rules out a SEGMENT STRIP for `TRF-01` in its own words —
          *"NONE drawn and none built"* — and §5.7.2 draws none. A segment is an
          exclusive partition of the list; `f.state` is a predicate over a column
          this tab already draws. Adding the second is not building the first.

          ⚠ **`cancelled` IS STILL UNREACHABLE, AND IT IS FILED — `DEF-1004`.**
          `list_queryset` excludes cancelled jobs, so `TRANSFER_FILTER_STATES`
          computes the option list by SUBTRACTING it: the panel cannot offer a
          value that would return nothing. When `DEF-1004` lands, the server's
          own tuple grows and this panel follows with no edit here. */}
      {/* ⛔ **NO `downloadSlot`** — the stated absence below is unchanged. */}
      {/* ⛔ **NO `downloadSlot`, AND THIS IS THE STATED ABSENCE CR-041 TASK 4
          ASKS FOR — NOT A FORGOTTEN PROP (DEF-1005).**

          `POST /exports` resolves only the resources a module REGISTERS, and an
          unregistered one is a plain 404, never a guessed queryset. Nothing
          registers `transfers`, so BR-SHL-010 keeps the capability unrendered:
          an undeclared capability is not drawn. Not drawn DISABLED either —
          BR-SHL-025 is for a control this ROLE cannot use, not one the PRODUCT
          does not have.

          This tab's §3 already lists what p131 draws and this does not, and the
          export is on that list.

          ⚠ A DOWNLOAD BUTTON HERE WOULD BE A CONTROL WIRED TO A 404 — hard-won
          law 2, which this repo has four instances of from a single day. The
          capability is OWED and unruled, and **DEF-1005 carries it** so this
          sentence expires when the row does rather than outliving its reason
          (DEF-445). */}
      <DataTable<TransferRow>
        config={config}
        // CR-045 wave G · `DEF-1702` — the `+ Filter ▾` panel, in the ONE
        // toolbar row B14 rule 12 fixes. The groups are built from the
        // response, so the options are the server's vocabulary and never a
        // copy of it (BR-SHL-010); `offerableFilters` drops the group entirely
        // before the first response rather than drawing a legend over nothing.
        filterBarSlot={
          <FilterBar
            filters={offerableFilters(transferFilterGroups(listQuery.data?.states, translate))}
            state={state}
            onStateChange={setState}
          />
        }
        state={state}
        onStateChange={setState}
        rows={rowsOf<TransferRow>(listQuery.data)}
        totalRows={totalOf(listQuery.data)}
        loading={listQuery.isPending}
        error={
          listQuery.isError
            ? {
                reason: t("customers.transfers.list.loadFailed", {
                  defaultValue: "The transfers could not be loaded.",
                }),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        empty={{
          title: t("customers.transfers.list.emptyTitle", { defaultValue: "No transfers yet" }),
          // ⚠ **THIS SENTENCE DESCRIBED THE DELETED JOB TWICE OVER.** It read
          // *"A transfer moves the same customer to a new address as one job,
          // rather than a move-out followed by a move-in"* — which is (a) the
          // exact case the wizard's own red warning says **is not a transfer**,
          // and (b) the counting contract again. An empty state is where a
          // clerk LEARNS a flow, so this one taught it backwards.
          helper: t("customers.transfers.list.emptyHelper", {
            defaultValue: "A transfer sells a property. The account stays; the owner changes.",
          }),
          ctaLabel: t("customers.transfers.action.new", { defaultValue: "+ New transfer" }),
          // ⚠ **WAS DISABLED, AND IS LIVE FROM 2026-08-25 (lane W7WIZ).** This
          // CTA carried `ctaReason: "The transfer wizard is not built yet"` —
          // BR-SHL-025 / law 2, correctly, while `TRF-02` had no route. The
          // wizard is mounted now, so the reason is gone and the button goes to
          // it. Anything a clerk still cannot do from there is disabled ON that
          // screen carrying its own reason, which is where it belongs.
          onCta: () => navigate(tenantPath(TRANSFER_WIZARD_ROUTE)),
        }}
      />

      {/* p131 draws two sentences under the table and only this one is a FACT:
          *"Taken on is the balance at the moment of sale, and the buyer owes
          it."* The second, *"One date, because there is only one. This used to
          be a flow with an out date and an in date…"*, is the product
          explaining its own history — rule 33's rationale, at zero words. With
          one `Sale date` column drawn there is nothing left for it to correct. */}
      <p className="mt-2 text-sm text-neutral-700" data-taken-on-note="">
        {t("customers.transfers.list.takenOnNote", {
          defaultValue: "Taken on: the buyer owes this.",
        })}
      </p>

      <p className="mt-1 text-sm text-neutral-700">
        {t("customers.transfers.list.sortFootnote")}
      </p>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: `DEF-CUS-5092` (the tab still describes the job the PO deleted) ·
//         `BR-CUS-1030` (PO 2026-09-01 — a transfer is a REASSIGNMENT) ·
//         `05-prototype/02 Accounts Menu Blueprint.pdf` p131, read as an IMAGE
//         (B14 rule 42) · `04-docs/05-modules/03-customers/conformance/
//         transfer-against-its-blueprint.md` §6 · B14 rules 12, 21, 32, 33, 41,
//         42 · hard-won laws 1, 2 (and its mirror), 6 · `DEF-CUS-3653` (grep a
//         value's consumers before letting it go quiet) · PO approval
//         2026-09-20: *"this is correct - please fix it"*
// generated: 2026-08-25 by lane F-TABS · REBUILT 2026-09-20 to p131
// checklist: A=n/a(no backend half in this lane) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions:
//   E3 **`SOLD BY` IS DRAWN AND NOT BUILT, BY RULING.** `reassign_account`
//      overwrites `transfer.customer_id` with the buyer, so the seller survives
//      only in the commit response and in `audit_log`, **which is pruned**. PO
//      2026-09-20: *"Both would need faking — one from a pruned audit log, one
//      pointing at a page that doesn't exist."* `DEF-CUS-5976`, backend first.
//   ✅ **`↗ Open` IS BUILT (2026-09-24, `DEF-CUS-6532`) — THIS EXCEPTION READ
//      *"No transfer record page exists at any address"* AND HAD BEEN FALSE
//      SINCE 2026-09-20.** `DEF-CUS-5977` and `DEF-CUS-5982` both close here.
//      The door opens in every state, by PO ruling, and is disabled only on a
//      row with no reference to address (BR-SHL-025) — which is the tenant's
//      numbering series and never the sale's progress. The expiry test that
//      was supposed to fire is replaced by one that presses the door: it
//      asserts the ADDRESS and the screen id, once per state the list draws,
//      and `10-scripts/def_cus_6529_transfer_door_walkthrough.mjs` clicks it.
//   E3 **`SALE DATE` IS NOT SORTABLE.** `SORTS["out_date"]` orders by
//      `from_account__closed_at`, NULL on every live row since `BR-CUS-1030`
//      removed the closure. `DEF-CUS-5975`; the column gains it back when the
//      server's term names `transfers.out_date`.
//   E3 **`OWED ON ACCOUNTS BEING SOLD` STATES ITS ABSENCE.** `kpi_strip` serves
//      five counts and no money. A `$0.00` would be DEF-127's *"looks exactly
//      like a settled account"* at strip scale. `DEF-CUS-5979`.
//   E3 the SEARCH PROMPT still reads `transfer_reads.SEARCH_HINT` verbatim
//      rather than p131's wording — the two are one string in two languages and
//      must move together (DEF-950). `DEF-CUS-5978`.
//   E3 **`One date, because there is only one.`** is drawn on p131 and NOT
//      built: it is the product narrating its own history, which rule 33 puts
//      at zero words on screen, and with one date column drawn there is nothing
//      for it to correct. Stamped here as a deliberate divergence from the
//      drawing (B14 requires every divergence stamped) rather than an omission.
//   E3 no segment strip and no `⇩ Export` — B14 rule 12 and `DEF-1005`,
//      unchanged from the previous build.
//   E3 TC-TRF-2 (*"`→ —`, not a blank"*) described the two-line FROM ACCOUNT
//      cell, which the ruling deleted. RETIRED WITH ITS JOB, not failed.
//   E3 no story owns S89 (law 8) — OWED, unchanged
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
