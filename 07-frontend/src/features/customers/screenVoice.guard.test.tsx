// ── Trace ──────────────────────────────────────────────
// Change:  DEF-731 — engineering rationale was rendered as user-facing copy on
//          the Move-ins tab, the Move-outs tab and the transfer wizard. The PO
//          reported it twice walking the deployed build: *"this text is note
//          required on screen"* / *"this content on page not required"*.
// Rules:   B14 rule 21 (Tailwind utilities) · BR-SHL-025 (a thing this
//          deployment cannot honour renders WITH its reason, never blank) ·
//          DEF-332 (our ids are attributes, never copy) · CLAUDE.md hard-won
//          law 6 (no gate looks at rendered output — this one does)
// Tests:   this file IS the gate.
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS, AND WHY EVERY EXISTING CHECK WAS BLIND
// ══════════════════════════════════════════════════════════════════════════
// DEF-731's escape column says it plainly: *"nothing catches it because no gate
// reads rendered output, and prose in a component is indistinguishable from
// copy to every check that exists."*
//
//   · `tsc` type-checks a string. It cannot read one.
//   · `eslint` has no opinion about register.
//   · The tabs' own suites asserted the offending sentences were PRESENT —
//     `expect(html).toContain("scheduled_move_out_on")` was a passing test over
//     a column name on a billing clerk's screen.
//   · G38 checks a stated absence carries a tracking id. It never reads the
//     sentence.
//
// So this file reads the RENDERED OUTPUT of the three screens and asserts two
// things that together are the fix:
//
//   1. **NOTHING A PERSON READS CARRIES AN ENGINEER'S VOCABULARY** — no
//      backticked identifier, no `§`, no snake_case field, no ALL_CAPS
//      constant, no source-file name, no dotted module path, no internal id,
//      and not the word *endpoint*. Visible text AND `title` tooltips, because
//      a clerk reads both.
//   2. **THE ABSENCE IS STILL STATED.** Deleting the sentences would trade a
//      badly-worded truth for a lie of omission, which this repo has recorded
//      as the more expensive failure (hard-won law 2 · G38 · DEF-445).
//
// ⚠ **THE MOVE-TAB FIXTURES CARRY THE SERVER'S REAL ENGINEERING PROSE,
// VERBATIM.** That is deliberate and it is the only design that tests the right
// thing. The offending sentences on those two tabs are authored in
// `06-backend/apps/customers/move_reads.py` and travel over the wire; a fixture
// with clean strings in it would prove nothing about the screen. Feeding the
// tab the real payload asserts the property that actually fixes the defect:
// **the screen states the absence in the reader's language whatever the server
// sends**, and it never pipes a diagnostic to the DOM.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import type { AccountDetail } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import { defaultRequestState } from "@/components/tableTypes";

import {
  ABSENCE_COPY,
  MoveInsTab,
  listMoveIns,
  moveInsQueryKey,
  moveInsTableConfig,
} from "./MoveInsTab";
import type { MoveInList } from "./MoveInsTab";
import { MoveOutsTab, listMoveOuts, moveOutsQueryKey, moveOutsTableConfig } from "./MoveOutsTab";
import type { MoveOutList } from "./MoveOutsTab";
import { LeavingStep, TransferWizard, emptyTransferDraft } from "./TransferWizard";
import { TRANSFER_WIZARD_ROUTE } from "./transferDisconnectShared";
import { DisconnectsTab, disconnectsQueryKey, disconnectsTableConfig } from "./DisconnectsTab";
import { listDisconnects } from "./worklistEndpoints";
import type { DisconnectList } from "./worklistEndpoints";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params) as string;

// ══════════════════════════════════════════════════════════════════════════
// WHAT A PERSON ACTUALLY READS
// ══════════════════════════════════════════════════════════════════════════
/**
 * Visible text PLUS every `title` tooltip, with HTML entities decoded.
 *
 * ⚠ Three mistakes are designed out of this helper, and two of them were made
 * in this repo already (see `MoveInsTab.test.tsx`'s `visibleText`):
 *
 *   1. A raw `html.includes(...)` reads ATTRIBUTES, so it finds `data-tracks`
 *      ids that DEF-332 deliberately puts there — machine data, not copy.
 *   2. Stripping tags alone DROPS the `title` tooltip, which is copy: hovering
 *      a cell is how a clerk reads the long form of an absence.
 *   3. `Save &amp; exit` is not what anybody reads. Entities are decoded so the
 *      patterns below match the sentence, not the markup.
 */
function readable(html: string): string {
  const titles = Array.from(html.matchAll(/\stitle="([^"]*)"/g))
    .map((m) => m[1])
    .join("  ");
  const text = html.replace(/<[^>]*>/g, " ");
  return `${text}  ${titles}`
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

/** The vocabulary of an engineer, each pattern named so a failure says WHAT it
 *  found and not merely that something matched. */
const FORBIDDEN: ReadonlyArray<{ readonly what: string; readonly re: RegExp }> = [
  { what: "a backtick-quoted code identifier", re: /`/ },
  { what: "a design-section number (§)", re: /§/ },
  { what: "the word `endpoint`", re: /\bendpoints?\b/i },
  { what: "a snake_case field or function name", re: /\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/ },
  { what: "an ALL_CAPS constant name", re: /\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/ },
  { what: "a source-file name", re: /\b[\w/.]+\.(?:py|tsx?|jsx?|css|json|md)\b/ },
  { what: "a dotted module path", re: /\b[a-z_]+\.[a-z_]+\.[a-z_]+\b/ },
  {
    what: "one of our internal ids",
    re: /\b(?:BR|DEF|OQ|US|GT|EP|TC|IS|ADR)-[A-Z]{0,3}-?\d{2,3}\b/,
  },
  { what: "a design-document id (B1, B18, B19…)", re: /\bB\d{1,2}\b/ },
  // ⚠ **THREE PHRASES, NOT TOKENS, AND THEY ARE HERE BECAUSE THE TOKEN LIST
  // MISSED THEM.** A sweep after the first fix found step 3 still saying *"is
  // not served to this screen: 'reserved' has no column anywhere in the
  // product"* — engineer's voice, and every pattern above passed it clean. A
  // gate that only catches punctuation catches the easy half.
  { what: "the phrase `served to this screen`", re: /\bserved to this screen\b/i },
  { what: "the phrase `this screen can read`", re: /\bthis screen can read\b/i },
  { what: "the phrase `no column`", re: /\bno column\b/i },
];

/**
 * The BACKEND's own absence catalogues, as text.
 *
 * ⚠ Read through Vite's `?raw` and NOT through `node:fs`: this app's tsconfig
 * carries no `@types/node`, so a bare `node:fs` import passes vitest and FAILS
 * `tsc --noEmit`. The house precedent is `ConfirmDialogTier.dom.test.tsx`,
 * which documents the same trap — and this file walked straight into it.
 */
const ABSENCE_SOURCES = import.meta.glob(
  "../../../../06-backend/apps/customers/{move_reads,move_out_settlement,seams}.py",
  { query: "?raw", eager: true, import: "default" },
) as Record<string, string>;

/**
 * The absence codes these two tabs can render, taken from what the two list
 * responses actually carry. Declared rather than derived, because "every code
 * in the backend" would drag in absences belonging to screens this lane never
 * touched and turn a real check into a chore.
 */
const RENDERED_ON_THE_MOVE_TABS = new Set<string>([
  "move_step_has_no_store",
  "unit_reads_not_readable_from_customers",
  "deposit_disposition_has_no_column",
  "deposit_carry_election_has_no_column",
  "waiting_on_has_no_vocabulary",
  "completed_move_in_has_no_retention_window",
  "parked_draft_has_no_account_row",
  "request_leg_matches_only_linked_refs",
  "account_has_no_customer_link",
  "service_start_date_not_set",
  "move_out_before_close_has_no_store",
  "move_out_window_has_no_closing_edge",
  "move_out_has_no_request_link",
  "final_bill_not_stated",
  "deposit_interest_not_accrued",
  "settlement_terms_not_read_on_a_list",
  "ledger_publishes_no_per_account_ar_position",
  // ⚠ THE THREE BELOW JOINED 2026-08-26 (CR-038 W9 · DEF-786). They were served
  // by `move_reads.py` and absent from this set, so the guard did not ask
  // whether the tabs had words for them — DEF-786's own escape reason,
  // verbatim: *"the ABSENCE_COPY guard's declared set was untouched so no
  // frontend test broke"*. A declared set that is not maintained is a guard
  // that reports PASS over the thing it was written to find.
  //
  // RED-FIRST PROOF, verbatim, with these three declared and `ABSENCE_COPY`
  // still as it was:
  //   AssertionError: absence code(s) with no sentence a person can read:
  //   final_read_state_not_recorded, reads_state_needs_a_service_start_date,
  //   unit_has_no_meters: expected [ …(3) ] to deeply equal []
  "unit_has_no_meters",
  "reads_state_needs_a_service_start_date",
  "final_read_state_not_recorded",
  // ⚠ THE THREE BELOW JOINED 2026-08-27 (CR-039 wave D 17–19) — the three ways
  // the new leading `Reference` cell can be empty. Declared HERE, in the same
  // commit that made them renderable, precisely because DEF-786's escape
  // reason (quoted above) is that a declared set which is not maintained is a
  // guard reporting PASS over the thing it was written to find.
  "move_predates_the_record",
  "move_in_not_completed",
  "numbering_series_missing",
]);

/** Assert, naming the offender. A gate whose output cannot tell you WHAT it
 *  found is the failure DEF-182 records. */
function expectNoEngineerVoice(html: string, screen: string): void {
  const prose = readable(html);
  for (const rule of FORBIDDEN) {
    const hit = rule.re.exec(prose);
    expect(
      hit === null,
      `${screen}: ${rule.what} is on a clerk's screen — "${
        hit === null ? "" : prose.slice(Math.max(0, hit.index - 90), hit.index + 110).trim()
      }"`,
    ).toBe(true);
  }
}

// ══════════════════════════════════════════════════════════════════════════
// THE MOVE-INS TAB — the payload with the SERVER's real sentences in it
// ══════════════════════════════════════════════════════════════════════════
/** `move_reads.STEP_HAS_NO_STORE`, character for character. */
const STEP_ABSENT = {
  code: "move_step_has_no_store",
  br_ref: "BR-CUS-018 · BR-SHL-046",
  detail:
    "B18 draws a STEP cell over a segmented bar, and a move-in or move-out in progress is " +
    "not a row anywhere in this product: there is no `move_ins` table, no `move_outs` " +
    "table and no wizard store, and `waiting_on` / `park_note` / `parked_at` are columns " +
    "on `service_requests` alone.",
};

/** `move_reads.READS_NOT_READABLE`. */
const READS_ABSENT = {
  code: "unit_reads_not_readable_from_customers",
  br_ref: "B1 · BR-MET-036",
  detail:
    "B18 draws READS as `taken` / `due`. `apps/customers/seams.py` — the one published door " +
    "from customers into metering — carries NO reader for whether a read has been taken at " +
    "a unit.",
};

/** `move_reads.DEPOSIT_SENTENCE_HAS_NO_STORE`. */
const DEPOSIT_ABSENT = {
  code: "deposit_disposition_has_no_column",
  br_ref: "BR-CUS-023 · BR-CUS-024 · US-CUS-007",
  detail:
    "B18 §5.5.2 draws DEPOSIT as a SENTENCE and not a number alone. Which of those applies " +
    "is a DISPOSITION and no column records one: `accounts.deposit_on_file` holds an " +
    "amount, and it is a REFUSED field on both doors that edit an account.",
};

/** `move_reads.MOVE_IN_DRAFT_HAS_NO_ACCOUNT` — one of the two the PO read. */
const DRAFT_ABSENT = {
  code: "parked_draft_has_no_account_row",
  br_ref: "BR-CUS-018 · BR-CUS-080",
  detail:
    "B18 §5.5.2 draws `— draft` in italic where the wizard has not created an account yet. " +
    "A draft with no account is a `service_requests` row and cannot appear on a list built " +
    "over `accounts`.",
};

/** `move_reads.MOVE_IN_DONE_HAS_NO_WINDOW`. */
const DONE_ABSENT = {
  code: "completed_move_in_has_no_retention_window",
  br_ref: "BR-CUS-018",
  detail:
    "B18 §5.5.7 draws two `Done` move-ins. Showing recent ones back would need a retention " +
    "window that no rule states, and `opened_at` alone cannot tell a move-in completed last " +
    "week from an account opened in 2019.",
};

/** `move_reads.MOVE_IN_IS_STILL_A_DRAFT` — CR-039 wave D 17–19, and the third
 *  of the three ways the new `Reference` cell can be empty. Character for
 *  character, because this guard's whole job is to render the SERVER's real
 *  sentences and see whether a clerk could read them. */
const REFERENCE_ABSENT_DRAFT = {
  code: "move_in_not_completed",
  // ⚠ **NARROWED 2026-09-22 (`BR-CUS-1090`), AND THE FIXTURE MOVED IN THE SAME
  // COMMIT AS THE SERVER.** It read *"This move-in has not completed, so there
  // is no job to reference yet. The record and its number are written when the
  // account opens…"* — 31 words, and the sentence the PO found inside a column
  // headed `Reference`. A fixture left at the old string would go on testing a
  // sentence the product no longer sends, which is this repository's most
  // repeated failure wearing a test's clothes.
  br_ref: "BR-CUS-018 · BR-CUS-150 · BR-CUS-1090",
  detail:
    "No number has been issued for this move-in. One is issued when a service request is " +
    "approved, or when somebody opens the move-in wizard, and neither has happened here — " +
    "so the reference appears with whichever comes first.",
};

function moveInPayload(): MoveInList {
  return {
    rows: [
      {
        // CR-039 wave D 17–19 — every row of this list is a draft, so the
        // reference is the stated absence rather than a number.
        move_no: null,
        move_no_unavailable: REFERENCE_ABSENT_DRAFT,
        // `BR-CUS-1077` — this tab serves two kinds of row now; this one is the
        // kind it has always served, a draft ACCOUNT.
        row_kind: "account",
        job_id: null,
        account_absence: null,
        documents_outstanding: null,
        account_id: "acc-12048",
        account_no: "A-12048",
        customer: null,
        customer_no: null,
        customer_source: null,
        customer_absence: {
          code: "account_has_no_customer_link",
          br_ref: "BR-CUS-054",
          detail:
            "no `customer_accounts` link and no primary contact on this account. A real " +
            "answer, not a gap.",
        },
        unit_id: "u-1",
        unit: "88 Pine Vista · 1",
        move_in_date: null,
        move_in_date_absence: {
          code: "service_start_date_not_set",
          br_ref: "BR-CUS-022",
          detail:
            "no service start date, so this account cannot be activated at all — " +
            "`_make_occupying` refuses an occupying account without one.",
        },
        step: { reached: null, of: 5, unavailable: STEP_ABSENT },
        // The UNREADABLE shape on purpose — this file is about the VOICE of an
        // absence, so its fixtures keep serving one (CR-038 W9 · DEF-786 gave
        // the cell four more keys and they are typed here, not smoothed away).
        reads: {
          state: null,
          measured_against: null,
          meters_total: null,
          meters_read: null,
          missing: [],
          unavailable: READS_ABSENT,
        },
        deposit: {
          currency: "USD",
          amount: { stored: null, display: null },
          recorded: false,
          sentence: null,
          unavailable: [DEPOSIT_ABSENT],
        },
        state: "waiting",
        starting_this_week: false,
        booked_in_on: "2026-08-23",
        age_days: 2,
        request: null,
        request_absence: null,
      },
    ],
    // `CR-171-BRC10` P2.01 — the redesigned list reads image 01's five tiles
    // and none of the seven-step screen's keys.
    kpis: {
      to_approve: 0,
      not_started: 0,
      drafts: 0,
      starting_this_week: 1,
      waiting_on_a_read: 0,
    },
    page: 1,
    per: 50,
    total: 3,
    pages: 1,
    columns: ["account", "customer", "unit", "move_in_date", "step", "reads", "deposit", "state"],
    states: [
      { code: "scheduled", label: "Scheduled", drawn: true, supported: true, unavailable: null },
      { code: "due", label: "Due", drawn: false, supported: true, unavailable: null },
      { code: "waiting", label: "Waiting", drawn: true, supported: true, unavailable: null },
      {
        code: "in_progress",
        label: "In progress",
        drawn: true,
        supported: false,
        unavailable: STEP_ABSENT,
      },
      { code: "done", label: "Done", drawn: true, supported: false, unavailable: DONE_ABSENT },
    ],
    search: {
      hint: "Customer, unit, address, account #, or request #…",
      min_chars: 2,
      legs: ["customer", "unit", "address", "account_no", "request_no"],
      unavailable: [
        {
          code: "request_leg_matches_only_linked_refs",
          br_ref: "BR-CUS-080",
          detail: "`outcome_ref` is TEXT and is not constrained to an account number.",
        },
      ],
    },
    exclusion: {
      callout:
        "A transfer appears only here. Its two halves are deliberately kept out of Move-ins " +
        "and Move-outs — the same job listed three times would be counted three times.",
      contract: ["transfer_half_account_ids"],
      half_account_ids: ["acc-9001"],
    },
    unavailable: [DRAFT_ABSENT, DONE_ABSENT],
    as_of: "2026-08-25",
  };
}

async function renderMoveIns(): Promise<string> {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify(moveInPayload()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = defaultRequestState(
    moveInsTableConfig(t, {
      // Stubs — the real cells are routed and a config case needs no router.
      reference: () => <span />,
      moveInDate: () => <span />,
      action: () => <span />,
    }),
  );
  await queryClient.prefetchQuery({
    queryKey: moveInsQueryKey(state),
    queryFn: () => listMoveIns({ q: state.q, page: state.page, per: state.per }, client),
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=move-ins`]}>
        <MoveInsTab client={client} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE MOVE-OUTS TAB — the sentence the PO quoted is in this fixture
// ══════════════════════════════════════════════════════════════════════════
/** `move_reads.MOVE_OUT_NOT_YET_CLOSED_HAS_NO_STORE` — DEF-731's own quotation. */
const NO_STORE_BEFORE_CLOSE = {
  code: "move_out_before_close_has_no_store",
  br_ref: "BR-CUS-030",
  detail:
    "A move-out that has not committed yet is not recorded anywhere. `services.move_out` " +
    "writes `closed_at`, the terminal status and the agreement end dates in ONE " +
    "transaction, and `accounts` carries no `scheduled_move_out_on`, no move-out state and " +
    "no step — `MOVE_OUT_FIELDS` will not even accept a date to park. `sample_data.py`'s W5 " +
    "block measured the same thing from the seeding side and wrote `account_notes` rows " +
    "instead.",
};

const WINDOW_ABSENT = {
  code: "move_out_window_has_no_closing_edge",
  br_ref: "BR-CUS-031 · US-BIL-011",
  detail:
    "Billing publishes no per-account final-bill total, so nothing takes a row off this " +
    "list and a closed account stays on it forever.",
};

const FINAL_BILL_ABSENT = {
  code: "final_bill_not_stated",
  br_ref: "BR-CUS-031 · US-BIL-011",
  detail:
    "billing publishes no per-account final-bill total, so the left-hand column of B19 " +
    "§15.9.0 cannot be read from here and the caller must state it.",
};

const DEPOSIT_INTEREST_ABSENT = {
  code: "deposit_interest_not_accrued",
  br_ref: "BR-CUS-057 · US-CUS-023 §7 · GT-61",
  detail:
    "the accrual engine is customers' own and is NOT BUILT — " +
    "`apps.customers.selectors.deposit_interest_accrued` is published by nothing.",
};

const SETTLEMENT_TERMS_ABSENT = {
  code: "settlement_terms_not_read_on_a_list",
  br_ref: "B19 §15.9 · BR-CUS-096 · BR-CUS-054",
  detail:
    "A full settlement also weighs unapplied credit, the customer's OTHER accounts and any " +
    "open dispute. The whole settlement is `GET /accounts/{id}/close-impact` on the " +
    "account's own page.",
};

const AR_ABSENT = {
  code: "ledger_publishes_no_per_account_ar_position",
  br_ref: "BR-CUS-015 · BR-REP-002 · DEF-127",
  detail:
    "the ledger module publishes no `apps.ledger.seams.ar_positions`, so what this customer " +
    "owes cannot be read from the books. `accounts.balance` is a cache nothing writes.",
};

/** `moves.MOVE_NUMBER_UNAVAILABLE["move_out"]` — CR-039 wave D 17–19. The
 *  SETTINGS-gap absence, chosen for this fixture rather than the numbered case
 *  precisely because this guard reads absence SENTENCES: a row that carried a
 *  number would render no sentence and prove nothing about this column. */
const REFERENCE_ABSENT_NO_SERIES = {
  code: "numbering_series_missing",
  detail:
    "This move-out has no reference number yet. A number series for move-outs has not been " +
    "set up, so nothing has been issued — the move-out itself completed and only its " +
    "reference is missing.",
};

function moveOutPayload(): MoveOutList {
  return {
    rows: [
      {
        move_no: null,
        move_no_unavailable: REFERENCE_ABSENT_NO_SERIES,
        // PO ruling 2026-09-19 — the list holds two kinds of row; this guard is
        // about the SENTENCES a finished one renders, so it stays `account`.
        row_kind: "account",
        park_id: null,
        waiting_on: null,
        park_note: null,
        remind_on: null,
        parked_at: null,
        age_days: null,
        account_id: "acc-11340",
        account_no: "A-11340",
        account_absence: null,
        customer: null,
        customer_no: null,
        customer_source: null,
        customer_absence: {
          code: "account_has_no_customer_link",
          br_ref: "BR-CUS-054",
          detail:
            "no `customer_accounts` link and no primary contact on this account — a real " +
            "answer, not a gap.",
        },
        unit_id: "u-9",
        unit: "77 Industrial Way",
        move_out_date: "2026-09-12",
        move_out_date_absence: null,
        step: { reached: null, of: 6, unavailable: STEP_ABSENT },
        final_read: {
          state: null,
          measured_against: null,
          meters_total: null,
          meters_read: null,
          missing: [],
          unavailable: READS_ABSENT,
        },
        settlement: {
          currency: "USD",
          landing: null,
          landings: ["settled", "refund_due", "short", "refused_other_debt", "refused_excess"],
          complete: false,
          sentence: null,
          deposit_held: { stored: "150.0000", display: "150.00" },
          deposit_interest: null,
          outstanding: { stored: null, display: null },
          outstanding_source: null,
          unavailable: [
            FINAL_BILL_ABSENT,
            DEPOSIT_INTEREST_ABSENT,
            SETTLEMENT_TERMS_ABSENT,
            AR_ABSENT,
          ],
        },
        state: "closed",
        leaving_this_week: false,
      },
    ],
    kpis: {
      open: 5,
      open_means: "closed_and_not_yet_finally_billed",
      open_unavailable: NO_STORE_BEFORE_CLOSE,
      leaving_this_week: 1,
      final_reads_due: null,
      final_reads_due_unavailable: READS_ABSENT,
      shortfalls_to_decide: null,
      shortfalls_to_decide_unavailable: FINAL_BILL_ABSENT,
      refunds_to_pay: null,
      refunds_to_pay_unavailable: FINAL_BILL_ABSENT,
      period_basis: "tenant_today",
      as_of: "2026-08-25",
    },
    page: 1,
    per: 50,
    total: 5,
    pages: 1,
    columns: [
      "account",
      "customer",
      "unit",
      "move_out_date",
      "step",
      "final_read",
      "settlement",
      "state",
    ],
    states: [
      { code: "closed", label: "Closed", drawn: false, supported: true, unavailable: null },
      {
        code: "scheduled",
        label: "Scheduled",
        drawn: true,
        supported: false,
        unavailable: NO_STORE_BEFORE_CLOSE,
      },
      {
        code: "in_progress",
        label: "In progress",
        drawn: true,
        supported: false,
        unavailable: NO_STORE_BEFORE_CLOSE,
      },
      {
        code: "waiting",
        label: "Waiting",
        drawn: true,
        supported: false,
        unavailable: NO_STORE_BEFORE_CLOSE,
      },
    ],
    search: {
      hint: "Customer, account #, unit, or address…",
      min_chars: 2,
      legs: ["customer", "account_no", "unit", "address"],
      unavailable: [
        {
          code: "move_out_has_no_request_link",
          br_ref: "BR-CUS-080",
          detail: "a move-out creates no child, so `link_child` has no reference to write.",
        },
      ],
    },
    exclusion: {
      callout:
        "A transfer appears only here. Its two halves are deliberately kept out of Move-ins " +
        "and Move-outs — the same job listed three times would be counted three times.",
      contract: ["transfer_half_account_ids"],
      half_account_ids: ["acc-9001"],
    },
    unavailable: [NO_STORE_BEFORE_CLOSE, WINDOW_ABSENT],
    as_of: "2026-08-25",
  };
}

async function renderMoveOuts(): Promise<string> {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify(moveOutPayload()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = defaultRequestState(
    // p117's three routed cells (2026-09-19). They take no part in this suite's
    // question — it reads the tab's VOICE — but the config's shape is the
    // config's shape, and a stub that lies about it is how a type error hides.
    moveOutsTableConfig(t, {
      // `DEF-CUS-5994` — the parked draft's state cell, stubbed like the rest.
      draftState: () => <span />,
      moveOutDate: () => <span />,
      settlement: () => <span />,
      reference: () => <span />,
      accountLink: () => <span />,
      openRecord: () => <span />,
    }),
  );
  await queryClient.prefetchQuery({
    queryKey: moveOutsQueryKey(state),
    queryFn: () => listMoveOuts({ q: state.q, page: state.page, per: state.per }, client),
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=move-outs`]}>
        <MoveOutsTab client={client} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE TRANSFER WIZARD — three RED panels on step 1, before the clerk has done
// anything wrong
// ══════════════════════════════════════════════════════════════════════════
function drawnAccount(): AccountDetail {
  return {
    id: "acc-10650",
    account_no: "A-10650",
    customer_no: "C-0091",
    name: "Iversen, Britt",
    unit_id: "unit-1",
    unit_label: "18 Marten Row",
    premise: "18 Marten Row",
    services: ["electric", "water"],
    balance: "0.0000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    // BR-CUS-510 / DEF-628 — the DEFAULT is `false`: this fixture's zero,
    // wherever it has one, is a real answer about money owed.
    balance_not_yet_billable: false,
    balance_cached: "0.0000",
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    kind: "regular",
    account_type: "residential",
    account_subtype: null,
    autopay: false,
    opened_at: "2022-06-01",
    closed_at: null,
    last_bill_at: "2026-08-01",
    aging: null,
    deposit_on_file: "150.0000",
    deposit_received_on: "2022-06-01",
    credit_tier: null,
    tax_exempt: false,
    tax_exempt_ref: null,
    tax_exempt_expires: null,
    bad_address: false,
    nsf_count: 0,
    preferred_language: null,
    custom_data: {},
    contacts: [],
    addresses: [],
    service_agreements: [],
    meters: [],
    plan: null,
    plan_snapshot_unavailable: "no plan snapshot",
    // DEF-2419 — the plan the UNIT stands on. Null here: these fixtures are
    // about a flow, not about the plan cell, and null is a real state
    // (a unit with no plan) rather than a placeholder.
    unit_plan: null,
    customer: {
      id: "cus-1",
      kind: "person",
      display_name: "Iversen, Britt",
      external_ref: null,
      accounts: [{ id: "acc-10650", account_no: "A-10650" }],
    },
  };
}

function renderLeavingStep(): string {
  return renderToStaticMarkup(
    <LeavingStep
      draft={{ ...emptyTransferDraft(), fromAccountId: "acc-10650" }}
      account={drawnAccount()}
      failed={false}
      onPatch={() => undefined}
      t={t}
    />,
  );
}

function renderWizardStep(step: number, opts: { park?: boolean } = {}): string {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify({ count: 0, results: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter
          initialEntries={[
            `/${TEST_TENANT}${TRANSFER_WIZARD_ROUTE}?step=${step}${
              opts.park === true ? "&park=1" : ""
            }`,
          ]}
        >
          <Routes>
            <Route
              path={`/:tenant${TRANSFER_WIZARD_ROUTE}`}
              element={<TransferWizard client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════
// THE DISCONNECTS TAB — DEF-742, AND THE REASON THIS FILE'S EXISTING COVERAGE
// WAS THE EXPENSIVE KIND
// ══════════════════════════════════════════════════════════════════════════
//
// **DEF-731 WAS FILED FROM WHAT THE PO HAPPENED TO CLICK, AND WAS FIXED ON
// EXACTLY THOSE SCREENS.** The mechanism it found is module-wide — a backend
// absence dict whose `detail`, written for an engineer, is piped straight to
// the DOM as visible text and as every cell tooltip — and this guard was
// pointed at the two Move tabs and the transfer wizard because those were the
// three the report named. The Disconnects tab shares the same pattern, in eight
// places, and sat OUTSIDE the list.
//
// That is the most expensive shape of coverage gap, because **the guard's
// presence reads as protection.** A reader seeing `screenVoice.guard.test.tsx`
// green concludes the module is covered. So the tab joins the list here, in the
// same commit as its fix.
//
// ⚠ **THE FIXTURE CARRIES THE SERVER'S REAL DIAGNOSTICS, VERBATIM**, exactly as
// the Move-tab fixtures do and for the same reason: a fixture with clean
// strings would prove nothing about the screen. What is asserted is that the
// screen states the absence in the READER's language whatever the server sends.
const DISC_PRECEDENCE_UNRULED = {
  code: "segment_precedence_unruled",
  tracks: "OQ-374",
  br_ref: "B18 §5.8.2",
  detail:
    "the six segments are NOT mutually exclusive: an account can be `on_hold` and have an " +
    "open case at once, and which segment wins is drawn nowhere.",
};

const DISC_DELIVERY_UNAVAILABLE = {
  code: "delivery_adapter_absent",
  br_ref: "BR-NOT-005",
  detail:
    "`LAST NOTICE` records HOW a notice was delivered — emailed, posted, certified sent, " +
    "certified signed. There is no email, SMS or print adapter in this release.",
};

const DISC_NO_TIER = {
  code: "no_tier_reached",
  br_ref: "B18 §5.8.2",
  detail:
    "no notice has been issued on this account, so it sits on no rung and B18 §5.8.2's chip " +
    "vocabulary has nothing to draw.",
};

const DISC_LEDGER_UNREADABLE = {
  code: "ledger_publishes_no_per_account_ar_position",
  br_ref: "BR-CUS-015 · DEF-127",
  detail:
    "the ledger module publishes no `apps.ledger.selectors.ar_positions`, so what this " +
    "customer owes cannot be read from the books.",
};

const DISC_CUT_CAPTION = {
  code: "cut_accrual_caption_superseded",
  br_ref: "BR-CUS-103 (PO 2026-08-25, OQ-380) · B18 §5.8.1",
  detail:
    "SUPERSEDED (BR-CUS-103 → base charges STOP at the cut). B18 §5.8.1 drew this tile a " +
    "caption saying a cut account keeps accruing its base charge.",
};

function disconnectPayload(): DisconnectList {
  const segment = (code: string, label: string, supported: boolean) => ({
    code,
    label,
    supported,
    unavailable: supported ? null : DISC_PRECEDENCE_UNRULED,
  });
  return {
    rows: [
      {
        account_id: "acc-11812",
        case_no: null,
        case_no_unavailable: {
          code: "no_case_opened",
          br_ref: "B18 §5.8.6",
          detail:
            "This account is on the list because a protection is in force. No disconnection " +
            "case row exists to carry a number.",
        },
        account_no: "A-11812",
        customer: "Bramble Bakery",
        address: "12 Foundry Row",
        unit_id: "u-11812",
        // the ledger could not be asked — the one cell where saying the wrong
        // thing about money costs most (DEF-127)
        owed: {
          stored: null,
          display: null,
          currency: null,
          source: null,
          unavailable: [DISC_LEDGER_UNREADABLE],
        },
        tier: { chips: [], ambiguous: false, unavailable: [DISC_NO_TIER] },
        cut_date: null,
        cut_date_is_this_week: false,
        last_notice: {
          issued_on: null,
          tier: null,
          delivery_state: null,
          unavailable: DISC_DELIVERY_UNAVAILABLE,
        },
        state: {
          stored: "notice_sent",
          held_by: ["medical_certificate"],
          one_cell_is_unresolved: true,
          unavailable: DISC_PRECEDENCE_UNRULED,
        },
        ladder: {
          runs: true,
          halt_code: null,
          detail: "the ladder runs",
          sequence: "service",
          scheduler: null,
        },
        protections: [],
        case: null,
        subject: null,
        chase_subject_unresolved: null,
      },
    ],
    kpis: {
      at_notice: 4,
      due_to_cut_this_week: 2,
      on_hold_protected: 3,
      cut_awaiting_payment: 1,
      cut_awaiting_payment_unavailable: DISC_CUT_CAPTION,
      reconnections_due: 1,
      as_of: "2026-08-26",
    },
    page: 1,
    per: 50,
    total: 1,
    pages: 1,
    columns: ["account", "customer", "address", "owed", "tier", "last_notice", "state"],
    segment: "all",
    segments: [
      segment("all", "All", true),
      segment("at_notice", "At notice", false),
      segment("on_hold", "On hold", false),
      segment("cut", "Cut", false),
    ],
    chips: [],
    search: { hint: "Customer, account #, address, or meter #…", legs: ["customer"] },
    delivery: DISC_DELIVERY_UNAVAILABLE,
    scheduler: null,
    as_of: "2026-08-26",
  } as unknown as DisconnectList;
}

async function renderDisconnects(): Promise<string> {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify(disconnectPayload()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const noCell = () => <span />;
  const state = defaultRequestState(
    disconnectsTableConfig(t, {
      owed: noCell,
      tier: noCell,
      cutDate: noCell,
      lastNotice: noCell,
      state: noCell,
      // `CR-125-BRC07` — the Disconnects list grew an ACTIONS column when the
      // disconnect case record landed. One line, in the commit that requires it.
      actions: noCell,
    }),
  );
  await queryClient.prefetchQuery({
    queryKey: disconnectsQueryKey(state),
    queryFn: () => listDisconnects({ q: state.q, page: state.page, per: state.per }, client),
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=disconnects`]}>
        <DisconnectsTab client={client} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DEF-731 · a screen speaks the reader's language, never the codebase's", () => {
  it("the Move-ins tab renders NO engineering vocabulary, whatever the server sends", async () => {
    expectNoEngineerVoice(await renderMoveIns(), "Move-ins tab");
  });

  it("the Move-outs tab renders NO engineering vocabulary, whatever the server sends", async () => {
    expectNoEngineerVoice(await renderMoveOuts(), "Move-outs tab");
  });

  it("⛔ DEF-742 — the Disconnects tab renders NO engineering vocabulary either", async () => {
    expectNoEngineerVoice(await renderDisconnects(), "Disconnects tab");
  });

  it("DEF-742 — the tab's eight absences each state their own fact, in the reader's words", async () => {
    const html = await renderDisconnects();
    const text = readable(html);
    // Every one of the server's diagnostics that this payload carries is GONE…
    for (const diagnostic of [
      "NOT mutually exclusive",
      "no email, SMS or print adapter",
      "B18 §5.8.2's chip vocabulary",
      "apps.ledger.selectors.ar_positions",
      "SUPERSEDED (BR-CUS-103",
    ]) {
      expect(html).not.toContain(diagnostic);
    }
    // …and the reader's sentence about the SAME fact is present in its place.
    // Not "an absence is stated somewhere" — the specific one, per cell, so a
    // single shared "cannot be shown" cannot pass this (DEF-127's shape).
    expect(text).toContain("has not been decided, so it appears under both");
    // ⚠ `DEF-CUS-9107` — the notice sentence is NOT on the default render any
    // more, because its column is not: `Last notice` came OFF the default set
    // on 2026-09-25 (`4448a4551`, DEF-CUS-6745 — ten columns were clipping the
    // only row action) and stays in the column chooser. The sentence itself is
    // unchanged and is asserted on the cell that draws it,
    // `DisconnectsTab.test.tsx`'s LastNoticeCell case.
    expect(text).not.toContain("no email, SMS or print adapter");
    expect(text).toContain("has not reached a step on the reminder ladder");
    expect(text).toContain("cannot be read from the books");
    expect(text).toContain("A blank is not the same as nothing owed");
  });

  it("the transfer wizard renders NO engineering vocabulary on any of its five steps", () => {
    expectNoEngineerVoice(renderLeavingStep(), "TransferWizard step 1");
    for (const step of [1, 2, 3, 4, 5]) {
      expectNoEngineerVoice(renderWizardStep(step), `TransferWizard step ${step}`);
    }
    // The Park panel is opened by `?park=1`, so a walk of the five steps never
    // renders it — and DEF-731 names the paragraph under Park explicitly.
    expectNoEngineerVoice(renderWizardStep(1, { park: true }), "TransferWizard · Park");
  });

  /**
   * ⚠ **A CATALOGUE ENTRY BEATS A `defaultValue`, AND THAT IS HOW A FIX SHIPS
   * DEAD.** This case was written for DEF-731, when the park control could not
   * act: it asserted the panel read the NEW *"Parking is not available here
   * yet"* rather than the engineering sentence all eleven catalogues still hold
   * under `customers.move.park.noStore`.
   *
   * ⚠ **CR-035 REMOVED THE SENTENCE ALTOGETHER, SO THE CASE IS RE-POINTED
   * RATHER THAN DELETED — AND IT IS RE-POINTED AT TWO MORE STALE CATALOGUE
   * ENTRIES, WHICH IS THE SAME TRAP ONE TURN LATER.** The panel now renders
   * `wizard.park.draftStep`, because the eleven catalogues' `wizard.park.parkedAt`
   * ends *"…and everything already entered stays on the record"* — and under
   * BR-SHL-048 **there is no record**: the unit stays Vacant and no account
   * exists. Rewriting that default under the old key would have left every clerk
   * being told a move-in had begun, with a green suite and a convincing diff.
   * `wizard.park.age` is the same shape (*"the unit is still held"*, now false)
   * and is asserted in `wizardPark.dom.test.tsx`, where the age renders.
   *
   * All three old keys are REPORTED for retirement; nothing here edits a
   * catalogue.
   */
  it("the Park panel reads the NEW sentences — three stale catalogue entries cannot win", () => {
    const prose = readable(renderWizardStep(1, { park: true }));
    // The store exists, so the blocked sentence is gone from the screen — both
    // the DEF-731 wording and the engineering one it replaced.
    expect(prose).not.toContain("Parking is not available here yet");
    expect(prose).not.toContain("it is already a saved row");
    expect(prose).not.toContain("becomes a record only when it commits");
    // ⛔ `wizard.park.parkedAt` — the sentence BR-SHL-048 made false.
    expect(prose).not.toContain("stays on the record");
    // ✅ `wizard.park.draftStep` — what a clerk reads instead, and it says the
    // ruling in a clerk's words rather than citing it.
    expect(prose).toContain("Nothing is created or changed until you finish the wizard");
    expect(prose).toContain("brings you back to this step with everything you have typed");
  });

  /**
   * ⚠ **AN ABSENCE IS NOT AN ERROR, AND THIS IS THE SECOND FAULT DEF-731
   * NAMES.** The three statements on step 1 rendered in `RefusalStrip`, which is
   * the RED strip `BR-SHL-020` reserves for a server REFUSAL. So a clerk opening
   * the wizard met three red blocks before doing anything at all. The neutral
   * treatment is the work-orders placeholder's, which the PO praised.
   */
  it("step 1 states its absences NEUTRALLY — no red refusal strip on a clean first render", () => {
    const html = renderLeavingStep();
    expect(html).not.toContain("data-refusal");
    expect(html).not.toContain("bg-danger-100");
  });

  /**
   * The honest-absence posture must SURVIVE the rewrite. Deleting the
   * sentences would trade a badly-worded truth for a lie of omission, which
   * hard-won law 2 and G38 both price higher than the bad wording.
   */
  it("every absence is still STATED, in the reader's language", async () => {
    const moveIns = readable(await renderMoveIns());
    // ⚠ **`CR-171-BRC10` (S3) REVERSED THE FACT THIS LINE ASSERTED.** It
    // demanded *"…so it is on the Requests tab"*, which was true until the
    // redesign put requests on this list as rows; the sentence is now FALSE
    // and must not come back. The absences that are still true are still
    // stated, below.
    expect(moveIns).not.toContain("Requests tab");
    // Each cell's absence, in the reader's words, on its tooltip (rule 32).
    expect(moveIns).toContain("No number has been issued for this move-in yet.");
    expect(moveIns).toContain("No service start date.");
    expect(moveIns).toMatch(/nothing was recorded/i);

    // ⚠ **THE MOVE-OUTS HALF IS TURNED AROUND, NOT DELETED (2026-09-19,
    // `DEF-CUS-5898`), AND THE REVERSAL IS A LATER RULE RATHER THAN A CHANGE OF
    // MIND.** These two lines asserted the tab PRINTED its two list-level
    // absences — *"has not gone through yet"* (45 words) and *"stays on this
    // list"*. This suite's own reasoning for demanding them is sound and is
    // quoted above: *"Deleting the sentences would trade a badly-worded truth
    // for a lie of omission"* — correct on 2026-08-26, when the only two
    // options were badly-worded and absent.
    //
    // **B14 rule 33 was ratified 2026-08-30, four days later, and it adds the
    // third option that lane did not have:** RATIONALE — why the product works
    // this way, why a row cannot leave a list — is ZERO WORDS ON SCREEN, and it
    // belongs in the code and the register. The PO applied it to this exact
    // screen on 2026-09-19: *"you ahve to follow our UI rules - this is correct
    // screen - too much text"*.
    //
    // ⛔ **SO THE GUARD STILL GUARDS, IN BOTH DIRECTIONS.** The prose must not
    // come back, AND the facts must still be carried — `data-list-absences` on
    // the tab's root holds both codes, so this is a screen that stopped
    // printing a fact rather than a product that stopped knowing it. A bare
    // deletion of these two lines would have left nothing watching either half.
    //
    // ⚠ **THE ASSERTION IS OVER THE BODY, NOT OVER `readable()`, AND THE
    // DIFFERENCE IS DELIBERATE.** `readable()` appends every `title=` because
    // DEF-731's whole point is that hover text is read by a person. The 45-word
    // sentence is STILL the OPEN tile's hover text, attached to the figure it
    // explains — untouched by this change, and not what the PO ruled off. What
    // came off is the BLOCK OF PROSE under the table, which is what rule 33
    // calls rationale on screen. Asserting over `readable()` would have failed
    // for the tooltip and told the next lane to strip that too.
    const moveOutsHtml = await renderMoveOuts();
    const moveOutsBody = moveOutsHtml.replace(/\stitle="[^"]*"/g, "").replace(/<[^>]*>/g, " ");
    expect(moveOutsBody).not.toMatch(/has not gone through yet/i);
    expect(moveOutsBody).not.toMatch(/stays on this list/i);
    // ✅ AND BOTH ARE STILL CARRIED, so the product has not stopped knowing it.
    expect(moveOutsHtml).toContain("move_out_before_close_has_no_store");
    expect(moveOutsHtml).toContain("move_out_window_has_no_closing_edge");

    // ⚠ **TURNED AROUND, NOT DELETED (`DEF-CUS-9107`) — THE SAME RULE AS THE
    // MOVE-OUTS HALF ABOVE.** The PO walked the transfer wizard on 2026-09-20
    // and ruled its explanations off the screen (`bd42316c3`, decision log of
    // that date): step 1 lost *"the premise panel, the paragraph telling a
    // clerk to go and check for a payment plan themselves"*. Those were
    // RATIONALE, which B14 rule 33 puts at zero words on screen. So the guard
    // asserts they STAY gone — and the step still names the account it is
    // about, which is the fact a clerk needs.
    const step1 = readable(renderLeavingStep());
    expect(step1).not.toMatch(/sub-meter/i);
    expect(step1).not.toMatch(/owns or manages/i);
    expect(step1).toMatch(/account being sold/i);
  });

  /**
   * ⚠ **THE FALLBACK IS A SAFETY NET, NOT A HIDING PLACE.** `absenceCopy` falls
   * back to a generic sentence for a code it has not learned, which keeps a NEW
   * server absence honest instead of silent — but a screen quietly generic
   * about six different things is the next defect. So this case reads the
   * BACKEND's own absence catalogues and asserts every code they can serve to
   * these two tabs has its own words here.
   *
   * It reaches across the repo on purpose. Nothing else connects the module
   * that AUTHORS an absence to the screen that has to SAY it, which is exactly
   * the seam DEF-731 fell through: the server added a sentence, the screen
   * printed it, and no check knew the two were different jobs.
   */
  it("every absence the server can serve these two tabs has its OWN words", () => {
    // ⚠ **A MISSING SOURCE IS A FAILURE, NOT A SKIP.** A guard that silently
    // stops checking is DEF-524's shape — G14's hardcoded path outlived the
    // file it named and reported PASS through six UI defects. Three files in,
    // and the count assertions below go red if any of them stops resolving.
    expect(Object.keys(ABSENCE_SOURCES)).toHaveLength(3);
    const codes = new Set<string>();
    for (const text of Object.values(ABSENCE_SOURCES)) {
      for (const m of text.matchAll(/"code":\s*"([a-z0-9_]+)"/g)) {
        codes.add(m[1]);
      }
      for (const m of text.matchAll(/^GAP_[A-Z_]+ = "([a-z0-9_]+)"/gm)) {
        codes.add(m[1]);
      }
    }
    expect(codes.size).toBeGreaterThan(10);
    // Only the codes these two tabs can actually render are required here; the
    // rest belong to screens this lane did not touch and are REPORTED, not
    // silently adopted.
    const reachable = [...codes].filter((code) => RENDERED_ON_THE_MOVE_TABS.has(code));
    expect(reachable.length).toBeGreaterThan(10);
    const missing = reachable.filter((code) => ABSENCE_COPY[code] === undefined);
    expect(missing, `absence code(s) with no sentence a person can read: ${missing.join(", ")}`)
      .toEqual([]);
  });

  /**
   * G38's mechanism is untouched: the tracking id stays a `data-` attribute and
   * never enters the sentence (DEF-332, PO 2026-08-19). This asserts BOTH
   * halves — the id is present for us, and absent from what a person reads.
   */
  it("G38 · the tracking id is still carried, and still not in the copy", async () => {
    const html = await renderMoveOuts();
    expect(html).toContain('data-tracks="BR-CUS-030"');
    expect(readable(html)).not.toContain("BR-CUS-030");
  });

  // ══════════════════════════════════════════════════════════════════════
  // `DEF-CUS-6177` — A TABLE CELL IS A VALUE, AND THIS SUITE NEVER ASKED
  // ══════════════════════════════════════════════════════════════════════
  //
  // ⛔ **THE ESCAPE REASON, AND IT IS THIS FILE'S OWN.** Every check above
  // reads the rendered output of this exact tab and asks two questions:
  // *is the absence STATED* and *does it carry an engineer's vocabulary*.
  // **Neither one asks how LONG it is.** So on 2026-09-22 the PO opened
  // Move-ins and found three sentences of rationale inside a column headed
  // `Reference`, and the generic *"SMARTBillHub cannot show this yet…"*
  // inside one headed `Customer`, with this suite, `tsc` and every gate green.
  //
  // **B14 rule 33 caps ON-SCREEN TEXT BY WHAT IT IS FOR** — a FACT at six
  // words, RATIONALE at zero words on screen — and **no gate in this
  // repository measures either.** `G33` comes closest and walks the message
  // keys the BACKEND raises, which is a fraction of the catalogue and none of
  // a sentence a React component renders from a map of its own.
  //
  // ⚠ **IT MEASURES THE VISIBLE BODY AND NOT `readable()`, DELIBERATELY.**
  // `readable()` appends every `title=` because hover text is read by a
  // person — and the tooltip is exactly where rule 32 says a stated absence
  // belongs, CLOSED by default. Measuring it here would tell the next lane to
  // strip the tooltip too, which is the lie-of-omission trade this file has
  // already refused once (see the Move-outs note above).
  //
  // ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY**, asked before trusting the green
  // (hard-won law 7, habit 2):
  //   · **A selector that matches no cell.** Then the loop runs zero times and
  //     reports success over a screen full of paragraphs — the shape that made
  //     a chart-copy walkthrough print a green tick over 224 notes. So the
  //     COUNT of cells measured is asserted first, and asserted as a minimum
  //     rather than merely logged.
  //   · **Counting words in the markup.** `data-` attributes and class names
  //     are not words a person reads. The body is stripped of tags and of
  //     `title=` before anything is counted.
  //   · **A cap loose enough to pass the defect.** The paragraph the PO read
  //     is 31 words. The cap here is 6 — rule 33's own number for a FACT — so
  //     the defect cannot squeeze under it.
  it("DEF-CUS-6177 · a stated absence in a cell is a FACT, never a paragraph", async () => {
    const html = await renderMoveIns();

    // ⚠ **WHAT THIS MEASURES, AND IT IS NARROWER THAN *EVERY CELL* ON PURPOSE.**
    // The first draft measured every `<td>` and went red on two things rule 33
    // does not govern — found by running it against the RUNNING APP rather than
    // this fixture (hard-won law 6, and law 7's habit 2 answered by a browser):
    //
    //   · **`3450 Oak Ridge Dr · Unit 1`** — seven "words", and an ADDRESS is a
    //     VALUE. Rule 33 caps a LABEL, a FACT, an INSTRUCTION, a CONSEQUENCE and
    //     RATIONALE — all of them text WE author. A tenant's own address is none
    //     of those, and a check that trimmed it would be corrupting data to
    //     satisfy a copy rule.
    //   · **a 27-word `Parked … Photo ID and the signed agreement still to come
    //     — chased 21 Aug.`** — most of that is the CLERK's own note. The chart
    //     of accounts settled this one on 2026-09-22: a reviewer's free text cut
    //     to six words discards the half that says what to do.
    //
    // So the subject is **a stated ABSENCE**, which is exactly what
    // `DEF-CUS-6177` is: the words this product writes when it has no value to
    // show. They carry `data-move-absent`, which is the marker `MoveAbsenceNote`
    // has always set.
    // ⚠ **INSIDE A `<td>`, AND NOTHING ELSE — TWO STAGES, BECAUSE ONE REGEX
    // OVER THE WHOLE PAGE IS NOT THE SAME QUESTION.** The first version
    // matched every `data-move-absent` in the document and went red on the two
    // LIST-LEVEL absences, which are rendered UNDER the table and are 21 and 28
    // words. **Those are correct and must stay**: B14 rule 32 gives a screen
    // one sentence per SECTION, and this file already records the ruling that
    // put them there rather than in a panel. The defect is a paragraph inside a
    // CELL, where a person is reading a column of values.
    const cells = Array.from(html.matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/g)).map((m) => m[1]);
    const cellCount = cells.length;
    const notes = cells
      .flatMap((cell) =>
        Array.from(
          cell.matchAll(/<span\b[^>]*\sdata-move-absent="[^"]*"[^>]*>([\s\S]*?)<\/span>/g),
        ),
      )
      .map((m) =>
        m[1]
        // The tooltip is where the whole sentence lives, and it is CLOSED by
        // default — rule 32's own posture. It is not what a person reads at
        // rest, so it is not what is measured.
          .replace(/\stitle="[^"]*"/g, "")
          .replace(/<[^>]*>/g, " ")
          .replace(/&amp;/g, "&")
          .replace(/&#x27;/g, "'")
          .replace(/&#39;/g, "'")
          .replace(/\s+/g, " ")
          .trim(),
      );

    // ⚠ **A CHECK THAT MEASURED NOTHING WOULD PASS IN SILENCE**, which is the
    // shape that printed a green tick over 224 notes on the chart of accounts.
    // Both numbers are asserted, and the one NOT covered is printed beside the
    // one that is — a declared blind spot with no number attached is
    // indistinguishable from an empty one (hard-won law 7).
    expect(
      notes.length,
      `no stated absence was measured — the marker is wrong (${cellCount} cells on screen)`,
    ).toBeGreaterThan(0);

    const tooLong = notes
      .map((text) => ({ text, words: text.split(" ").filter(Boolean).length }))
      .filter((note) => note.words > 6);

    expect(
      tooLong.map((c) => `${c.words} words: "${c.text}"`),
      `B14 rule 33 caps a FACT at six words. ${notes.length} stated absence(s) measured ` +
        `out of ${cellCount} cells — the rest hold VALUES and a clerk's own words, ` +
        `which rule 33 does not govern (see DEF-CUS-6192 for the one that is ours).`,
    ).toEqual([]);
  });
});
