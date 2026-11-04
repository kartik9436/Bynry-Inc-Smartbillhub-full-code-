// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-004 (S33 Record payments — the vocabularies, tones and tab
//           strip) · US-PAY-001 (the S22/S35 Record modal's allocation choice) ·
//           US-PAY-013 (the S34 ageing bands, collection tiers and plan states) ·
//           US-PAY-005 (the S32 money cells) · US-PAY-012 (the four write-off
//           reasons) · US-PAY-014 (why the ladder skipped an account)
//           Screens: S33 · S22 · S35 · S32 · S34
// Rules:    BR-PAY-001 (default rules / specific / carry credit / split) ·
//           BR-PAY-002 (a payment is append-only — this module offers no edit
//           affordance and no write wrapper exists for one) · BR-PAY-012
//           (purpose) · BR-PAY-021 (both dates) · BR-PAY-024 (the receipt that
//           is not queued) · BR-PAY-025 (the deposit batch that does not
//           exist) · BR-PAY-026 (the method list is the tenant's, live) ·
//           BR-PAY-017 (the ladder's rungs) · BR-PAY-020 (the four write-off
//           reasons, and only those four) · BR-PAY-029 (A2 §S34's ageing
//           bands) · BR-TEN-042 (one currency per tenant — which is what lets
//           the display code be read off the payments list) ·
//           BR-SHL-001 (the sidebar's own paths) · BR-SHL-020 (plain language
//           when something is absent) · BR-SHL-023 (ONE money formatting path:
//           `Money` composes `MoneyCell` and adds no second formatter) ·
//           BR-SHL-025 (a control this deployment cannot honour renders
//           disabled WITH its reason)
// ───────────────────────────────────────────────────────
// The pieces S33 and the Record modal are built from. They live beside the
// screens so the honesty rules below are components rather than conventions the
// next payments screen could forget.
//
// FOUR THINGS THIS MODULE REFUSES TO DO:
//
//   1. **It never prints a receipt number or a deposit batch.** Both are IS-5
//      "available columns" and both are served NULL by a server that cannot
//      answer them: BR-PAY-024's receipt queue is US-PAY-025's and unbuilt, and
//      `deposit_batches` is EP-PAY-06's table and does not exist. The cells say
//      so, because an empty cell reads as a value that failed to load.
//
//   2. **It never turns a blank clearing date into a blank cell.** A payment
//      with no `cleared_at` is PROCESSING — the money has not arrived
//      (BR-PAY-021) — which is a state, not a missing value, and the two look
//      identical if you render "—" for both.
//
//   3. **It never enables an allocation choice the server would refuse.**
//      BR-PAY-001 confirms four staff choices and `allocation.py` executes all
//      four; two of them need a picker of the account's OPEN bills.
//      ⚠ **THIS RULE SAID *"no endpoint serves that position (OQ-154), so they
//      render DISABLED with the reason"* UNTIL 2026-09-02 AND IT HAD STOPPED
//      BEING TRUE (hard-won law 1).** `GET /accounts/{id}/open-bills` serves it
//      (CR-059 CS-4, 2026-09-01) and `OQ-154` is CLOSED. The rule still HOLDS —
//      nothing here offers a choice the server would refuse — it is just that
//      all four are now offerable, and `OpenBillPicker` below is what makes the
//      other two safe: a clerk aims at what a bill STILL OWES, never at what it
//      was issued for.
//
//   4. **It never claims the payments API is missing.** Both routes are served
//      now, and the list screen still DERIVES a route-absent message from a 404
//      rather than hardcoding either state — a constant reading
//      `PAYMENTS_API = true` would be a comment claiming a fact about another
//      file (hard-won law 1) and would be wrong the day someone removed the
//      include.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import type { ReactNode } from "react";

import { isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getAccountOpenBills,
  getAccounts,
  getPaymentReasonCodes,
  getPaymentPlans,
} from "@/api/endpoints";
import type {
  AccountRow,
  AgeingBucket,
  OpenBillPosition,
  PaymentMethodOption,
  PaymentPlanInstallmentView,
  PaymentPlanRow,
  PaymentReasonOption,
  PaymentRow,
  PaymentStatus,
  PaymentType,
  PaymentsProblem,
  PaymentsPageResponse,
} from "@/api/endpoints";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";
import type { StatusTone } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import type { Translator } from "@/features/tenancy/settingsShared";

import "./payments.css";

// ── Permission (A4 / BR-IDN-009) ───────────────────────────────────────────
// A4 has ONE row for this surface — "Payments (record)": System Admin Full ·
// Billing Clerk Full · Executive View. Declared once so the list and the modal
// cannot gate on two copies of the code.
export const PAYMENTS_PERMISSION = "payments_record";

// ── Routes (the AppShell sidebar's own paths — SHELL_NAV `payments`) ───────
// TENANT-RELATIVE, like every route constant since path tenancy landed (PO
// 2026-08-10): the screen that navigates puts it through `tenantPath()`.
export const PAYMENTS_ROUTE = "/payments";
export const PAYMENTS_RECORD_ROUTE = "/payments/record";
// ══════════════════════════════════════════════════════════════════════
// `DEF-PAY-6317` — 2·3a's OWN ADDRESS, AND IT IS A SIBLING OF THE LIST'S
// ══════════════════════════════════════════════════════════════════════
// The blueprint writes it in the frame header itself (p037): *"today: a modal ·
// agreed: `/:tenant/payments/record/new` — a page, not a modal"*, over
// *"DESKTOP · 1440 · A PAGE, FULL WIDTH"*.
//
// ⚠ **`PAYMENTS_RECORD_ROUTE` ABOVE IS THE LIST AND IS NOT REDIRECTED HERE.**
// p030 draws frame 2·1 as `/:tenant/payments/record → PaymentsPage →
// PaymentsTable` — the `record` segment is the Payments TAB's id
// (`PAYMENTS_TAB_RECORD`), not the form's. Sending it to this page would
// delete the tab that lists every payment, on an address `AppShell`'s sidebar
// and `sidebarDestinations` both name. The two are siblings; the tab's page
// head is what carries the door.
//
// THREE SEGMENTS, so it can collide with neither `:tab` nor the counter — the
// `DEF-520` lesson that puts `counter/:counterCode`, `debtors/:accountNo` and
// `imports/new` where they are.
export const PAYMENTS_RECORD_NEW_ROUTE = "/payments/record/new";
// ══════════════════════════════════════════════════════════════════════
// S58 MOVES TO PAYMENTS — `CR-138-BRC07` `P4.10`, 2026-09-23
// ══════════════════════════════════════════════════════════════════════
// ⚠ **THIS LINE READ `"/finance/refunds"` UNTIL 2026-09-23, AND CHANGING IT
// REVERSES A SIGNED STATEMENT.** The change process (step 2) requires the
// statement being reversed to be QUOTED with its supersedes chain before a line
// is written, *"because that is what stops the next lane putting it back"* —
// so the whole chain is here rather than in a commit message nobody re-reads.
//
//   **THE SIGNED STATEMENT, verbatim** — `CR-059` §10, task 18
//   (`12-governance/11-change-requests.md`):
//
//       *"**P3 · Refunds** (S58, `/finance/refunds`, **no screen at all
//       today**) — **CS-6 · CS-7.** The whole screen: tabs for awaiting
//       approval · issued · all; Raise, Issue and Mark-cleared actions …"*
//
//   **ITS CHAIN, in order:**
//   1. `CR-059` §10 / task 18 (2026-09-01, shipped `2.125.2`) — the address
//      `/finance/refunds`, chosen on `BR-PAY-020`'s reasoning for write-offs:
//      **money LEAVING the utility is approved and reported in Finance, while
//      the record belongs to payments.** It landed as an EIGHTH Finance tab.
//   2. `CR-060` `T10` (2026-09-02) — the Finance strip goes to SEVEN and
//      Refunds does NOT fold. Recorded in `02-decision-log.md` that day.
//   3. **PO ruling 2026-09-03, asked directly, verbatim: *"C25 says six tabs. -
//      this is correct."*** `C25` names its six and Refunds is not among them,
//      so (2)'s conclusion is superseded: Refunds stops being a Finance TAB and
//      becomes `RefundsQueuePanel` inside Revenue & AR. **`/finance/refunds`
//      stays routed** — *"the page is RE-HOMED, not withdrawn"*.
//   4. `CR-135` `P0.8` (2026-09-22) — the payments strip gains a **Refunds**
//      tab whose path is still this constant, *"a door to the screen that
//      already exists rather than a second copy of it"*, and says in terms that
//      re-homing the page *"is the blueprint's 6·1–6·3c work"*.
//   5. **THIS CHANGE.** The payments blueprint p074 supersedes (1)'s PLACEMENT
//      and says exactly how far it reaches, verbatim: ***"Role separation does
//      not need a separate page: issuing and clearing already carry their own
//      role checks server-side, which work wherever the button sits. This
//      supersedes `CR-059` §10's placement, **not the rule behind it** —
//      Finance keeps reporting money out, which is a read."***
//
// ⚠ **SO THE RULE IN (1) IS NOT REVERSED AND MUST NOT BE READ AS REVERSED.**
// Money leaving the utility is still approved and reported in Finance; what
// moved is one URL. The role checks that made the Finance address meaningful
// are `BR-PAY-1071`'s and live in `refunds.py`'s service, where they work from
// any address at all.
export const REFUNDS_ROUTE = "/payments/refunds";

/** Where S58 lived from 2026-09-01 to 2026-09-23.
 *
 *  ⚠ **IT STAYS MOUNTED AND REDIRECTS — IT IS NOT DELETED.** This URL is in
 *  saved links, in tickets and in this repo's own journeys, and `CR-060`'s own
 *  ruling kept `/finance/gl` and `/finance/write-offs` routed for exactly that
 *  reason. `P4.21` states the requirement for this lane's successor in terms:
 *  *"The old refunds address 404s or redirects **deliberately**. No silent dead
 *  link."* A redirect is the half of that choice which costs a clerk nothing. */
export const REFUNDS_LEGACY_ROUTE = "/finance/refunds";

/** The collections ladder (blueprint 7·3a). A STATIC route that outranks
 *  `/payments/:tab`, so it leaves `PaymentsPage` entirely.
 *
 *  ⚠ **DECLARED HERE RATHER THAN IN `CollectionsPage`, WHERE IT USED TO BE THE
 *  ONLY COPY.** `P0.8` takes the ladder's tab off the strip as the drawing
 *  does, so the Debtors tab now has to name this address to keep the screen
 *  reachable — and a second literal `/payments/collections` in a second file is
 *  how two answers to one question start drifting. `CollectionsPage` re-exports
 *  it under its own long-standing name, so App.tsx and its tests are unchanged. */
export const COLLECTIONS_LADDER_ROUTE = "/payments/collections";

// ── The tab strip ──────────────────────────────────────────────────────────
// ⚠ **THIS SECTION DESCRIBED THE PROTOTYPE'S THREE TABS UNTIL 2026-09-22 AND
// THE STRIP IS NOW THE PAYMENTS BLUEPRINT'S SEVEN (`P0.8`).** `CLAUDE.md`'s own
// ruling of 2026-09-14 is why: for any module that has a blueprint PDF, r10
// drops to VISUAL STYLE ALONE and the blueprint owns layout, copy, FLOWS and
// states. A tab strip is a flow. The paragraphs below are kept, not deleted,
// because each records a judgment that is still live — where the page OPENS,
// why the strip carries no count, and why the ladder got a destination of its
// own — and losing the reasoning is how the next lane re-litigates it.
//
// The three original ids and the sidebar's three paths (BR-SHL-001) are
// unchanged: `/payments` = Summary · `/payments/record` · `/payments/outstandings`.
// What moved is the LABELS and the four tabs beside them, and the drawing owns
// both — see the seven-tab block below.
//
// TWO DELIBERATE DIVERGENCES FROM THE PROTOTYPE, both reported rather than
// silently taken:
//
//   · The prototype OPENS on "Record payments" (`payTab: 'record'`, line 6204).
//     This screen opens on Summary, because the ratified sidebar maps the
//     parent path `/payments` to Summary and a sidebar item that lands
//     somewhere other than its label says is a worse defect than a landing tab.
//   · The prototype's third tab reads "Outstandings (184)". The count is a live
//     aggregate over the S34 read-model, which EXISTS now (US-PAY-013 shipped
//     2026-08-15 and the tab calls it) — but the TAB STRIP does not fetch it,
//     and it must not: the count depends on a business day nobody has chosen
//     until the tab opens and asks for one (BR-TEN-043). So the label still
//     carries no number, and the real figure is the first line of the tab.
export const PAYMENTS_TAB_SUMMARY = "summary";
export const PAYMENTS_TAB_RECORD = "record";
export const PAYMENTS_TAB_OUTSTANDINGS = "outstandings";
// ⚠ A FOURTH TAB THE PROTOTYPE DOES NOT DRAW, added 2026-08-16 by the payments
// SURFACE lane and REPORTED rather than taken quietly.
//
// `apps/payments/ladder.py` could only ever be DRIVEN: `POST /collections/run`
// SENDS the notice, advances the tier and writes a `notice_history` row on
// every path, skips included. There was no way for a clerk to LOOK first —
// which tier each account had already had, what would go next, and which of
// BR-PAY-017's five stop conditions would silently pass an account over. Every
// one of those skips is a customer nobody contacted.
//
// The board belongs beside the outstandings a clerk works from, and the sidebar
// renders no submenus (PO 2026-08-10), so a page's tab strip IS how a
// sub-destination is reached. The precedent for reporting a strip that is wider
// than the prototype's is the Finance page, which has carried five tabs against
// four ratified sidebar children since it shipped.
//
// ⚠ **AND IT LEFT THE STRIP ON 2026-09-22 (`P0.8`) WITHOUT LOSING ITS SCREEN.**
// The blueprint folds the ladder under **Debtors** as screen 7·3a, so this id
// is no longer a tab — it is the id the strip shows as *Debtors* while the
// ladder is open, and the ladder's door is a control on the Debtors tab. The
// reasoning above is why the board exists at all and has not changed.
export const PAYMENTS_TAB_COLLECTIONS = "collections";

// ══════════════════════════════════════════════════════════════════════════
// THE SEVEN-TAB STRIP — payments blueprint `P0.8`/`P0.9`
// ══════════════════════════════════════════════════════════════════════════
// **PO ruling 2026-09-22, verbatim:** *"go as per phase 0 ; we are going to
// implement all phases one by one so fcus on current one."* — answering what a
// clerk sees when they click a tab with nothing behind it. Three options were
// put: add each tab when its screen lands · all seven with the three saying
// plainly that they are not built · all seven with three greyed out. **All
// seven render and all seven are reachable**, and the three without screens say
// so plainly.
//
// **THE LABELS AND THE ORDER ARE READ OFF THE DRAWING, NOT OFF THE TASK LIST**
// (B14 rule 42 — a screen is built from the drawing AS AN IMAGE). Every §03
// screen draws the same strip:
//
//     Summary · Payments · Counter · Imports · Settlements · Refunds · Debtors
//
// so `record` is labelled **Payments** rather than *Record payments*, and
// `outstandings` is labelled **Debtors** rather than *Outstandings*. Neither id
// moves: an id is in a URL a clerk may have bookmarked, and renaming one would
// 404 a saved link to gain nothing.
//
// ⚠ **`collections` LEAVES THE STRIP AND KEEPS ITS SCREEN, AND THAT NEEDED A
// DOOR RATHER THAN A DELETION.** The drawing folds the ladder under Debtors as
// screen 7·3a, and the blueprint's own page for it records that its ONLY door
// today is its tab — *"the door is built from the tab id"*. Dropping the tab
// with nothing in its place would have made a live, routed, tested screen
// unreachable, which is the exact defect `P0.9`'s outcome names (*"Three
// screens in this audit were built and unreachable; this is how that is avoided
// by design"*) and hard-won law 2's mirror. So the ladder is reached from the
// Debtors tab's own head until 7·1 is redrawn in phase 2, and
// `paymentsTabFrom` still answers `collections` so that screen's strip can show
// **Debtors** selected — which is what the drawing shows it showing.
export const PAYMENTS_TAB_COUNTER = "counter";
export const PAYMENTS_TAB_IMPORTS = "imports";
export const PAYMENTS_TAB_SETTLEMENTS = "settlements";
export const PAYMENTS_TAB_REFUNDS = "refunds";

export interface PaymentsTab {
  readonly id: string;
  readonly labelKey: string;
  /** TENANT-RELATIVE, like every route constant in this file. The strip puts it
   *  through `tenantPath()`. It is declared HERE rather than derived from the id
   *  because two of the seven do not live under `/payments` at all. */
  readonly path: string;
}

export const PAYMENTS_TABS = [
  { id: PAYMENTS_TAB_SUMMARY, labelKey: "payments.tab.summary", path: PAYMENTS_ROUTE },
  { id: PAYMENTS_TAB_RECORD, labelKey: "payments.tab.record", path: PAYMENTS_RECORD_ROUTE },
  { id: PAYMENTS_TAB_COUNTER, labelKey: "payments.tab.counter", path: "/payments/counter" },
  { id: PAYMENTS_TAB_IMPORTS, labelKey: "payments.tab.imports", path: "/payments/imports" },
  {
    id: PAYMENTS_TAB_SETTLEMENTS,
    labelKey: "payments.tab.settlements",
    path: "/payments/settlements",
  },
  // ⚠ **THIS COMMENT SAID *"NOT `/payments/refunds`"* UNTIL 2026-09-23 AND IT
  // IS NOW EXACTLY THAT** (`CR-138-BRC07` `P4.10`). It read: *"S58 is
  // payments-owned and lives in the FINANCE area by ruling … so this tab is a
  // door to the screen that already exists rather than a second copy of it.
  // Re-homing that page into this strip is the blueprint's 6·1–6·3c work and
  // is phase 2's."* **That work is this change.** The tab is no longer a door
  // out of payments into Finance; it is the payments address itself, and the
  // supersedes chain for the move is on `REFUNDS_ROUTE` above.
  { id: PAYMENTS_TAB_REFUNDS, labelKey: "payments.tab.refunds", path: REFUNDS_ROUTE },
  {
    id: PAYMENTS_TAB_OUTSTANDINGS,
    labelKey: "payments.tab.outstandings",
    path: "/payments/outstandings",
  },
] as const;

/**
 * The three tabs `P0.8` lands with no screen behind them, and the id that
 * closes each one.
 *
 * ⚠ **THIS IS A REGISTER, NOT A CONVENIENCE LIST**, in `NotBuiltYet`'s own
 * discipline: `sevenTabs.dom.test.tsx` reads it and fails BOTH WAYS — a tab
 * here that has started rendering a real screen is stale, and a tab with no
 * screen and no entry is an unexplained blank. That is the test hard-won law 2
 * asks for *in the same commit as the hold*: on 2026-09-05 the customer portal
 * shipped **two working doors out of eight** because landing a screen and
 * releasing the control that pointed at it are two acts, and only the first one
 * feels like the work.
 */
export const PAYMENTS_TABS_AWAITING_A_SCREEN: Readonly<Record<string, string>> = {
  // ⛔ **`counter` LEFT THIS REGISTER ON 2026-09-23 (`CR-136-BRC07` `P2.6`).**
  // It read `[PAYMENTS_TAB_COUNTER]: "P2-counter"` — the task that releases it
  // — and the day that task landed, `sevenTabs.dom.test.tsx` went RED on the
  // hold-expiry case and named the tab, which is exactly what hard-won law 2's
  // mirror asks a hold to do. The tab now renders `CountersTab` (3·1) and its
  // four acts; the holding panel is gone and this line with it, in the SAME
  // commit, because landing a screen and releasing the thing that pointed at
  // it are two acts and only the first one feels like the work.
  // ⛔ **`imports` LEFT THIS REGISTER ON 2026-09-22 (`CR-135` `P1.5`).** It read
  // `[PAYMENTS_TAB_IMPORTS]: "P1.5"` — the task that releases it — and the day
  // that task landed, `sevenTabs.dom.test.tsx` went RED on the hold-expiry case
  // and named the tab, which is exactly what hard-won law 2's mirror asks a
  // hold to do. The tab now renders `PaymentsImportsTab`; the holding panel is
  // gone and this line with it, in the SAME commit, because landing a screen
  // and releasing the thing that pointed at it are two acts and only the first
  // one feels like the work.
  // ⛔ **`settlements` LEFT THIS REGISTER ON 2026-09-23 (`CR-139-BRC07`
  // `P5.7`).** It read `[PAYMENTS_TAB_SETTLEMENTS]: "P2-settlements"` over the
  // sentence *"No table, no endpoint"* — and both halves had stopped being
  // true: `payments/0038` and `0039` landed `settlements` and
  // `settlement_members` earlier the same day, and the read that was missing
  // (`GET /settlements`, which the drawing's own *To build* row names and no
  // task row owned — `DEF-PAY-6286`) landed with the screen. The tab renders
  // `SettlementsTab` (5·1) and its one door onto 5·2; the holding panel is gone
  // and this line with it, in the SAME commit, because landing a screen and
  // releasing the thing that pointed at it are two acts and only the first one
  // feels like the work.
  //
  // ⚠ **THE REGISTER IS NOW EMPTY, AND THAT IS A STATE IT HAS TO HOLD.** `P0.8`
  // landed three holds and all three are released. It stays DECLARED rather
  // than deleted: `sevenTabs.dom.test.tsx` reads it in both directions, so the
  // next tab that ships without a screen has a place to say so, and every tab
  // in the strip is asserted against it today.
};

export type PaymentsTabId = string;

/** An unknown `:tab` falls back to the sidebar's own landing tab, never 404s.
 *
 *  ⚠ `collections` is NOT in `PAYMENTS_TABS` and IS answered here: the ladder
 *  keeps its own static route and renders this strip with **Debtors** selected,
 *  exactly as the blueprint draws it. Returning `summary` for it would leave
 *  that screen's whole strip looking unselected. */
export function paymentsTabFrom(tab: string | undefined): PaymentsTabId {
  const found = PAYMENTS_TABS.find((candidate) => candidate.id === tab);
  if (found !== undefined) {
    return found.id;
  }
  return tab === PAYMENTS_TAB_COLLECTIONS ? PAYMENTS_TAB_COLLECTIONS : PAYMENTS_TAB_SUMMARY;
}

/** The TENANT-RELATIVE address a tab id opens.
 *
 *  ⚠ **THE STRIP CALLS THIS RATHER THAN BUILDING `/payments/${id}`.** Two of the
 *  seven do not live under `/payments` — Refunds is at `/finance/refunds` by
 *  ruling, and Summary is the bare parent — so a derived address sent Refunds to
 *  an address nothing mounts, which renders the catch-all and looks like a
 *  broken deployment. `PageHeader` hands `onTabSelect` its OWN tab shape, which
 *  carries an id and no path, so the lookup has to happen here. */
export function paymentsTabPath(id: string): string {
  return PAYMENTS_TABS.find((tab) => tab.id === id)?.path ?? PAYMENTS_ROUTE;
}

/** Which tab the strip shows as selected for a screen that is not a `:tab`.
 *
 *  The ladder is the only one today: it is a static route, so it leaves
 *  `PaymentsPage` entirely, and the tab it belongs to is Debtors. */
export function paymentsStripSelection(tab: PaymentsTabId): string {
  return tab === PAYMENTS_TAB_COLLECTIONS ? PAYMENTS_TAB_OUTSTANDINGS : tab;
}

// ── Status + type vocabularies (A5 §Payment) ───────────────────────────────

/**
 * A5 §Payment / `apps.payments.models.PAYMENT_STATUSES` — the six, and only
 * the six. A tenant cannot invent a seventh: the immutability trigger, the
 * ledger contract and the S33 action sets are all written against these.
 */
/**
 * The Status filter's offer, in LIFECYCLE order (`CR-186-BRC10`, PO
 * 2026-10-21): every payment is `posted` when taken and `cleared` when its
 * deposit batch is reconciled with the bank; `cancelled` only from `posted`;
 * `reversed` is the negative row a bounce writes. `processing` and `failed`
 * are no longer written by new payments and stay offered because old rows
 * hold them. Every one of the six, and only the six — the parity test
 * asserts it against `PAYMENT_STATUSES`.
 */
export const PAYMENT_STATUS_FILTER_ORDER: readonly PaymentStatus[] = [
  "posted",
  "cleared",
  "cancelled",
  "reversed",
  "processing",
  "failed",
];

export function paymentStatusLabel(status: PaymentStatus, t: Translator): string {
  return t(`payments.status.${status}`);
}

export function paymentStatusTone(status: PaymentStatus): StatusTone {
  if (status === "cleared" || status === "posted") {
    return "success";
  }
  if (status === "processing") {
    return "warning";
  }
  // `failed`, `reversed` and `cancelled` are all money that did NOT stay — the
  // tone says so rather than leaving one of them looking like an ordinary
  // payment.
  //
  // ⚠ **`cancelled` REACHES THIS LINE BY A FALL-THROUGH, AND THAT IS NOW A
  // DECISION RATHER THAN AN ACCIDENT (`CR-137-BRC07` `P3.11`, 2026-09-23).**
  // The sixth status arrived with `payments/0036` while `PAYMENT_STATUSES` in
  // `api/endpoints.ts` still listed five, so this function could not have been
  // given it — `PaymentStatus` did not contain the word. The tone it lands on
  // is the right one (a cancel is money that never stayed, exactly like a
  // reversal), and it is written down here so the next reader does not have to
  // re-derive whether anybody actually looked.
  return "danger";
}

export function paymentTypeLabel(type: PaymentType, t: Translator): string {
  return t(`payments.type.${type}`);
}

// ── The allocation choice (BR-PAY-001) ─────────────────────────────────────
//
// ⚠ **TWO OF THESE FOUR SHIPPED DISABLED FROM 2026-08-11 TO 2026-09-02, AND
// THEY ARE LIVE NOW (CR-059 CS-4, task 12).** `disabled?: boolean` and
// `allocationChoiceReason()` used to live here; the reason was
// `payments.applyTo.pickerUnavailable`, rendered under the allocation field on
// BOTH modals from one function — *"no endpoint serves that position"*. The
// endpoint is `GET /accounts/{id}/open-bills`, served since 2026-09-01, and
// `OQ-154` is CLOSED. The flags, the function and the eleven catalogue entries
// are DELETED rather than left standing beside a control that works: CS-4's own
// Proof says *"the two disabled options become enabled and the on-screen reason
// text is deleted with them"*.

export interface AllocationChoice {
  value: string;
  labelKey: string;
  /** True when the choice needs the open-bill picker below. NOT a disable —
   *  the picker exists; this is what tells the form to draw it. */
  needsTargets?: boolean;
}

/**
 * BR-PAY-001's four staff options, in the prototype's own order (line 5636:
 * "Oldest open bill · Specific bill · Carry as credit · Split").
 *
 * `newest_first` is deliberately NOT here. BR-PAY-010 makes the ORDER a tenant
 * SETTING, not a per-payment staff choice, and the S22 form is the staff
 * instruction — offering it on the form would let one clerk silently override a
 * setting the tenant configured once.
 */
export const ALLOCATION_CHOICES: readonly AllocationChoice[] = [
  { value: "oldest_first", labelKey: "payments.applyTo.oldest_first" },
  { value: "specific", labelKey: "payments.applyTo.specific", needsTargets: true },
  { value: "carry_credit", labelKey: "payments.applyTo.carry_credit" },
  { value: "split", labelKey: "payments.applyTo.split", needsTargets: true },
];

/** Does this choice aim at named bills? `specific` and `split` do; the other
 *  two are instructions the allocator carries out on its own. */
export function choiceNeedsTargets(value: string): boolean {
  return ALLOCATION_CHOICES.some((choice) => choice.value === value && choice.needsTargets === true);
}

// ── Method options (BR-PAY-026 — the tenant's list, never a constant) ──────

/**
 * The served list, as the form's picker. NOT a hardcoded set: BR-PAY-026 seeds
 * six and OQ-031 closed the enum into a tenant-extensible LOOKUP, so a tenant
 * that adds "Bill-pay portal" can use it the same day (US-PAY-001 TC-3). An
 * empty list is rendered as an empty picker, never as the six seeds: it means
 * the tenant deactivated every method, and inventing the seeds back would offer
 * codes the server refuses.
 */
export function methodOptions(methods: readonly PaymentMethodOption[]) {
  return methods.map((method) => ({ value: method.code, label: method.name }));
}

// ── Failure sentences (BR-SHL-020) ─────────────────────────────────────────

/**
 * A COLLECTION route that answers 404 does not exist — `GET /payments` returns
 * 200-with-zero-results when nothing matches. DERIVED from the response rather
 * than declared, so nothing here has to be edited if the route ever moves.
 */
export function listRouteAbsent(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

// ═══════════════════════════════════════════════════════════════════════════
// The visible half — S32 Summary · S34 Outstandings · write-offs · the
// collections run (US-PAY-005 · US-PAY-013 · US-PAY-012 · US-PAY-014).
// ═══════════════════════════════════════════════════════════════════════════

// ── The one CHAR(3) code these two read-models do not carry ────────────────

/**
 * ⚠ **`GET /outstandings` AND `GET /payments/summary` SERVE MONEY WITH NO
 * CURRENCY CODE.** Every amount on both bodies — the balances, the ageing
 * tiles, the day's takings, the method mix, write-offs YTD — is a bare 4dp
 * decimal string. CLAUDE.md rule 2 is that the amount and its CHAR(3) travel
 * together, and `MoneyCell` cannot render one without the other.
 *
 * Three answers were available and two are wrong. Assuming `USD` prints a
 * wrong symbol on a Canadian tenant's books (the exact reasoning `endpoints.ts`
 * already records for `RevenueArResponse.currency`). Formatting the figure here
 * without a symbol makes this file a SECOND money formatter, which is the
 * defect a lane fixed at the single formatter today.
 *
 * So the code is READ FROM A SERVED VALUE: `GET /payments` — which this page
 * already calls, for the same tenant, under BR-TEN-042's one-currency lock —
 * carries `totals.currency` and a `currency` on every row. Null when the tenant
 * has taken no payment at all, and null then renders as a stated absence rather
 * than as a guess. **REPORTED**: the honest fix is a `currency` member on both
 * read-model bodies, which is a backend shape change this lane may not make.
 */
export function paymentsDisplayCurrency(list: PaymentsPageResponse | undefined): string | null {
  return list?.totals?.currency ?? list?.results?.[0]?.currency ?? null;
}

/**
 * Money on these two screens: `MoneyCell` when the tenant's code could be read,
 * and the A18 absence sentence when it could not.
 *
 * The absence branch is not defensive padding — it is the state a brand-new
 * tenant with issued bills and no payments is genuinely in, and printing
 * "8,240.00" with no currency beside it on a collections screen is a figure a
 * clerk would act on.
 */
export function Money(props: { amount: string; currency: string | null }) {
  const { t } = useTranslation();
  if (props.currency === null) {
    return <span className="cus-awaits">{t("payments.money.currencyUnavailable")}</span>;
  }
  return <MoneyCell amount={props.amount} currency={props.currency} />;
}

// ── Exact decimal addition (CLAUDE.md rule 2 — never a float) ──────────────

const DECIMAL_RE = /^-?\d+(\.\d+)?$/;
const SCALE = 6; // NUMERIC(18,6) — the storage grid, and the wire's own

/**
 * Σ of decimal strings, EXACTLY, or null when any of them is not one.
 *
 * Two screens need a total no endpoint answers: the S34 bulk toolbar's
 * *"4 selected · $11,642.90 owed"* (US-PAY-013 TC-4's own copy) and the S32
 * method-mix tie-out (US-PAY-005 TC-2's *"Σ = 100%"*).
 *
 * **It is computed on the exact NUMERIC(18,6) grid with BigInt, never with a
 * float.** `Number("8240.0000") + Number("1842.1000")` is the shape of every
 * money defect this repo has logged; scaling each string to six decimal places
 * of integer and adding those is exact for any figure the database can hold.
 * Nothing here rounds and nothing here FORMATS — the result is a decimal
 * string that goes to `MoneyCell` like every other amount (BR-SHL-023), so
 * this is not a second money formatter.
 *
 * A value that is not a plain decimal string returns **null** rather than being
 * skipped: a total that silently dropped one selected account would be a
 * smaller number wearing the right label.
 */
export function sumDecimalStrings(values: readonly string[]): string | null {
  let total = 0n;
  for (const value of values) {
    if (!DECIMAL_RE.test(value)) {
      return null;
    }
    const negative = value.startsWith("-");
    const [whole, fraction = ""] = (negative ? value.slice(1) : value).split(".");
    const scaled = BigInt(whole + fraction.padEnd(SCALE, "0").slice(0, SCALE));
    total += negative ? -scaled : scaled;
  }
  const negative = total < 0n;
  const digits = (negative ? -total : total).toString().padStart(SCALE + 1, "0");
  const body = `${digits.slice(0, digits.length - SCALE)}.${digits.slice(digits.length - SCALE)}`;
  return negative ? `-${body}` : body;
}

// ═══════════════════════════════════════════════════════════════════════════
// THE OPEN-BILL PICKER AND ITS RUNNING REMAINDER — CR-059 CS-4 · P1, task 12
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  IT AIMS AT WHAT A BILL STILL OWES, NEVER AT WHAT IT WAS ISSUED FOR.     ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// The repo's own worked figure is why this exists: `BL-2608-018410` was issued
// at 247.87, a 200.00 payment left 47.87 open, and a picker built on the bill
// list would have offered a clerk **247.87** as the figure to aim at. That is a
// wrong allocation nobody looking at the screen can see is wrong.
//
// ONE IMPLEMENTATION, TWO SCREENS. S33's Record modal and S21's Record modal
// both draw this, for the reason `ALLOCATION_CHOICES` is shared: two copies of
// a money control drift, and this one decides where a customer's payment lands.
//
// WHAT IT DOES NOT DO:
//   · **It computes no bill balance.** Every figure below is served — the seam
//     did the subtraction (`amount_due − Σ allocations`), and this file adds
//     nothing to it. The ONE arithmetic here is the remainder, which is a fact
//     about the FORM (what the clerk is holding, less what they have aimed) and
//     not about the account. It is exact BigInt, never a float.
//   · **It never lists a settled bill.** The server drops one, so a control
//     that could only produce a refusal is never drawn.
//   · **It never renders `invoice_id`.** B14 rule 31 — the `targets[]` the form
//     posts name a bill by its NUMBER, which is also what the API takes.
// ═══════════════════════════════════════════════════════════════════════════

/** The form's aim: one entry per bill the clerk has named, keyed by NUMBER. */
export type BillTargets = Readonly<Record<string, string>>;

export const openBillsKey = (accountId: string) =>
  ["payments", "open-bills", accountId] as const;

/**
 * The account's open position, read ONLY when a choice needs it.
 *
 * `enabled` is the whole point: a clerk taking money oldest-first or as credit
 * never names a bill, so the read is not made. It is one hook rather than two
 * copies for the same reason `ALLOCATION_CHOICES` is one list — the S33 modal
 * and the S21 modal must ask the same question of the same route.
 */
export function useOpenBills(accountId: string, client: ApiClient, enabled: boolean) {
  return useQuery({
    queryKey: openBillsKey(accountId),
    queryFn: () => getAccountOpenBills(accountId, client),
    enabled: enabled && accountId !== "",
    retry: false,
  });
}

// ── The REASON a credit or an adjustment carries (BR-TEN-036) ──────────────
//
// ⚠ **DEF-PAY-5128 — THE HALF OF CR-059 CS-35 THAT NEVER SHIPPED.** CS-35
// taught `record_payment` the TYPE and the REASON and built the type select;
// nothing ever offered the reason. `services._reason_code` REFUSES a credit or
// an adjustment carrying no reason BY NAME, so two of the three options on a
// live control could only ever fail — and the suite stayed green, because every
// test of that form drives the default `payment`, for which a reason is
// REFUSED. A select whose non-default options are untested is a control nobody
// has ever submitted.
//
// It is ONE hook rather than two copies for the same reason `ALLOCATION_CHOICES`
// is one list: the S33 form and the account's Adjust modal must offer the same
// reasons the recorder validates against, or a clerk meets a server refusal on
// a value the screen has just handed them.

export const paymentReasonsKey = () => ["payments", "reason-codes"] as const;

/**
 * This utility's live credit/adjustment reasons, read ONLY when one is needed.
 *
 * `enabled` is the point: a clerk recording an ordinary PAYMENT may not carry a
 * reason at all — the server refuses one — so the read is not made.
 */
export function useReasonCodes(client: ApiClient, enabled: boolean) {
  return useQuery({
    queryKey: paymentReasonsKey(),
    queryFn: () => getPaymentReasonCodes(client),
    enabled,
    retry: false,
  });
}

/**
 * The picker's options: the tenant's own rows, NAME shown and CODE sent.
 *
 * B14 rule 31 — the code is a tenant reference value the server takes, never
 * the label. An empty list stays empty: offering a seeded five back would offer
 * codes this tenant has deactivated and the recorder refuses, which is the same
 * posture `methodOptions` takes directly above.
 */
export function reasonOptions(reasons: readonly PaymentReasonOption[]) {
  return reasons.map((reason) => ({ value: reason.code, label: reason.name }));
}

/** `targets[]` as the record body takes it. An empty amount is the `specific`
 *  instruction — *"this bill, up to what it owes"* — and the server reads a
 *  missing `amount` as exactly that, so it is omitted rather than sent blank. */
export function targetsBody(targets: BillTargets): { invoice_number: string; amount?: string }[] {
  return Object.entries(targets).map(([invoiceNumber, amount]) =>
    amount.trim() === ""
      ? { invoice_number: invoiceNumber }
      : { invoice_number: invoiceNumber, amount: amount.trim() },
  );
}

/** `-x` for `x`, exactly, on decimal STRINGS — never `-Number(x)` (rule 2). */
function negated(value: string): string {
  return value.startsWith("-") ? value.slice(1) : `-${value}`;
}

/**
 * What is left of the payment after everything the clerk has aimed — or `null`
 * when any figure is not a plain decimal string.
 *
 * **`null` is rendered as a stated absence and never as zero.** A remainder
 * that silently dropped one unparseable box would be a smaller number wearing
 * the right label, which is `sumDecimalStrings`' own reasoning one control up.
 */
export function remainingToAllocate(amount: string, targets: BillTargets): string | null {
  const aimed = Object.values(targets).filter((value) => value.trim() !== "");
  return sumDecimalStrings([amount.trim(), ...aimed.map((value) => negated(value.trim()))]);
}

export interface OpenBillPickerProps {
  /** The served position. `undefined` while it is being read or after it
   *  failed — the two are told apart by `pending`, never by an empty list. */
  position: OpenBillPosition | undefined;
  pending: boolean;
  failed: boolean;
  /** `specific` picks ONE bill; `split` states an amount per bill. */
  mode: "specific" | "split";
  /** What the clerk is holding, as typed. The remainder is measured off it. */
  amount: string;
  targets: BillTargets;
  onTargets: (next: BillTargets) => void;
  t: Translator;
}

export function OpenBillPicker(props: OpenBillPickerProps) {
  const { t, position } = props;

  if (props.pending) {
    return <p className="pay-form-note">{t("payments.openBills.loading")}</p>;
  }
  if (props.failed || position === undefined) {
    return <p className="pay-form-note">{t("payments.openBills.failed")}</p>;
  }
  // A measured zero, not an absence: this read LOOKED and nothing is owed, and
  // the money the clerk is holding will carry as account credit. Saying so is
  // what stops a clerk hunting for a bill that is not there.
  if (position.bills.length === 0) {
    return <p className="pay-form-note">{t("payments.openBills.none")}</p>;
  }

  const remainder = remainingToAllocate(props.amount, props.targets);

  // `specific` is ONE bill by definition (BR-PAY-001) — re-picking REPLACES
  // rather than adds, so the form can never post two bills under a choice that
  // means one.
  const pickOne = (invoiceNumber: string): void => props.onTargets({ [invoiceNumber]: "" });

  const setSplit = (invoiceNumber: string, value: string): void => {
    const next: Record<string, string> = { ...props.targets };
    if (value.trim() === "") {
      delete next[invoiceNumber];
    } else {
      next[invoiceNumber] = value;
    }
    props.onTargets(next);
  };

  return (
    <div className="pay-pair-list">
      <p className="pay-form-note">
        {/* CR-059 P1's own header, summed by the SERVER over exactly the rows
            below it, so the sentence and the list cannot disagree. */}
        {position.total_open !== null && position.currency !== null
          ? t("payments.openBills.owes", {
              // BR-SHL-023 — ONE money formatting path. `formatMoney` is the
              // function `MoneyCell` itself composes, so this is that path used
              // inside a sentence, not a second formatter: 2 dp on screen over
              // the served 4 dp, with the tenant's own CHAR(3).
              amount: formatMoney(position.total_open, position.currency),
              count: position.bill_count,
            })
          : t("payments.openBills.owesUnpriced", { count: position.bill_count })}
      </p>
      <div className="pay-table-scroll">
        <PlainTable>
          <thead>
            <tr>
              <th scope="col">{t("payments.openBills.col.pick")}</th>
              <th scope="col">{t("payments.openBills.col.bill")}</th>
              <th scope="col">{t("payments.openBills.col.issued")}</th>
              <th scope="col" className="pay-num">
                {t("payments.openBills.col.issuedFor")}
              </th>
              <th scope="col" className="pay-num">
                {t("payments.openBills.col.owes")}
              </th>
            </tr>
          </thead>
          <tbody>
            {position.bills.map((bill) => (
              <tr key={bill.number}>
                <td>
                  {props.mode === "specific" ? (
                    <label className="pay-inline-field">
                      <input
                        type="radio"
                        name="open-bill"
                        value={bill.number}
                        checked={props.targets[bill.number] !== undefined}
                        onChange={() => pickOne(bill.number)}
                      />
                      <span className="pay-sub">{t("payments.openBills.pickThis")}</span>
                    </label>
                  ) : (
                    <label className="pay-inline-field">
                      <input
                        type="text"
                        inputMode="decimal"
                        aria-label={t("payments.openBills.amountFor", { number: bill.number })}
                        value={props.targets[bill.number] ?? ""}
                        onChange={(event) => setSplit(bill.number, event.target.value)}
                      />
                    </label>
                  )}
                </td>
                <td>{bill.number}</td>
                <td>
                  {bill.issued_on ?? (
                    <span className="pay-sub">{t("payments.openBills.noIssueDate")}</span>
                  )}
                </td>
                <td className="pay-num">
                  {/* BR-BIL-004 — what the bill CHARGED. Beside, never instead
                      of, what it still owes: "issued 247.87 · owes 47.87" is
                      the sentence CS-4 exists to make sayable. */}
                  {bill.total !== null && bill.currency !== null ? (
                    <MoneyCell amount={bill.total} currency={bill.currency} />
                  ) : (
                    <span className="pay-sub">{t("payments.openBills.noFigure")}</span>
                  )}
                </td>
                <td className="pay-num">
                  {bill.open_balance !== null && bill.currency !== null ? (
                    <MoneyCell amount={bill.open_balance} currency={bill.currency} />
                  ) : (
                    <span className="pay-sub">{t("payments.openBills.noFigure")}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </div>
      <p className="pay-form-note">
        {remainder !== null && position.currency !== null
          ? t("payments.openBills.remainder", {
              amount: formatMoney(remainder, position.currency),
            })
          : t("payments.openBills.remainderUnknown")}
      </p>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// A RELEASE, SHOWN AS A RELEASE — CR-059 CS-36 · task 20
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE FIGURES WERE ALREADY RIGHT. WHAT WAS MISSING WAS THE WORD.          ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// `allocation_release` landed on 2026-09-01: when a paid bill is corrected, the
// payment's application to it is taken off by an APPEND-ONLY negative mirror row
// hung off that same payment (BR-PAY-1072 — the original row is never edited,
// because `allocations` refuses UPDATE and DELETE in every state).
//
// **On screen that read as the bill listed TWICE against one payment** — the
// amount, and the same amount back off it — with nothing saying why. A clerk
// looking at Ajinkya's 100.00 saw `2608-0141` and `2608-0141`, and the money
// looked as though it had gone somewhere twice.
//
// TWO THINGS FIX IT AND NEITHER TOUCHES A FIGURE:
//   1. **Net the rows per bill**, so one bill is one line. (It also removes a
//      duplicate React key, which is what listing a bill twice was.)
//   2. **Say why the money came back off**, in the bill's own line.
//
// ⚠ **THERE ARE EXACTLY TWO WAYS A NEGATIVE ALLOCATION EXISTS, AND THEY ARE
// TOLD APART BY WHOSE PAYMENT HOLDS THEM — not by a flag, because `allocations`
// carries no reason column and CS-36's own spec says "Data: None".**
//
//   * **A CORRECTION released it.** `allocation_release` hangs the negative
//     mirror off the SAME payment that made the application, so a payment whose
//     own amount is POSITIVE and which holds a negative row was released. That
//     path has one caller in the whole product — `corrections.
//     execute_restatement` — so "the bill it met was corrected" is a fact, not
//     an inference dressed up.
//   * **A BOUNCE reversed it.** `reversal.reverse_payment` hangs its negatives
//     off the NEW reversing payment, whose own `amount` is NEGATIVE and whose
//     status is `reversed`. The original payment's rows are untouched.
//
// So the sign of the payment decides which sentence is true, and neither
// sentence is ever guessed from an absence.
// ═══════════════════════════════════════════════════════════════════════════

/** One bill a payment met, netted across every row it wrote against it. */
export interface AppliedBill {
  invoiceId: string;
  invoiceNumber: string | null;
  /** Σ of every row against this bill — positive less negative. Never rounded;
   *  `null` when a row's amount is not a decimal string, which is stated on
   *  screen rather than silently dropped. */
  net: string | null;
  /** Σ of the NEGATIVE rows as a positive magnitude, or `null` when there are
   *  none. Its presence is what makes a line say "released". */
  releasedBack: string | null;
}

/** Did a CORRECTION take money back off this payment's bills?
 *
 *  True only on a payment that is itself positive and holds a negative row —
 *  see this section's header for why that is the whole test. A reversing
 *  payment (negative amount) answers false: its negatives are the bounce. */
export function releasedByCorrection(row: PaymentRow): boolean {
  return !row.amount.startsWith("-") && row.applied_to.some((e) => e.amount.startsWith("-"));
}

/** `applied_to`, one entry per BILL, in first-seen order. */
export function appliedBills(row: PaymentRow): AppliedBill[] {
  const order: string[] = [];
  const rows = new Map<string, { number: string | null; amounts: string[] }>();
  for (const entry of row.applied_to) {
    const found = rows.get(entry.invoice_id);
    if (found === undefined) {
      order.push(entry.invoice_id);
      rows.set(entry.invoice_id, { number: entry.invoice_number, amounts: [entry.amount] });
    } else {
      found.amounts.push(entry.amount);
      // Billing resolves the number once; a later row may carry it where an
      // earlier one could not, and the number is never un-learned.
      found.number = found.number ?? entry.invoice_number;
    }
  }
  return order.map((invoiceId) => {
    const bill = rows.get(invoiceId)!;
    const negatives = bill.amounts.filter((amount) => amount.startsWith("-"));
    return {
      invoiceId,
      invoiceNumber: bill.number,
      net: sumDecimalStrings(bill.amounts),
      releasedBack:
        negatives.length === 0
          ? null
          : sumDecimalStrings(negatives.map((amount) => amount.slice(1))),
    };
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// THE PAYMENT-PLAN STRIP — CR-059 CS-23 · task 6 (S22 · S35)
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  A CUSTOMER PAYING PERFECTLY ON TIME WAS BEING CHASED UP THE LADDER.     ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// `plans.record_installment_payment` — the one function that stamps an
// instalment as paid — had NO CALLER on the running product until 2026-09-01.
// The record path linked a payment to the PLAN and never touched the instalment
// row, so every instalment stayed unmarked: the plan read as behind from the
// day after the first one fell due, BR-CUS-043's dunning pause never applied,
// missed-instalment notices went to customers who had missed nothing, and the
// plan could never close. The link is built. This is the half that lets the
// clerk SEE which obligation their money is about to meet.
//
// **WHICH INSTALMENT IS NOT DECIDED HERE.** `plans.earliest_unmet_installment`
// is the rule — the earliest by the customer's OWN `seq`, which is what the
// agreement they signed is numbered by, and NOT by due date (two rows can share
// one). This mirrors that exact predicate against the served schedule so the
// screen cannot promise a different row from the one the service will link, and
// the CHOICE the clerk makes travels as `installment_seq` so the server decides
// even when they override.
// ═══════════════════════════════════════════════════════════════════════════

export const accountPlanKey = (accountId: string) =>
  ["payments", "account-plan", accountId] as const;

/**
 * The account's payment-plan context, for the Record form's strip.
 *
 * ONE hook, both Record modals — the same reason `ALLOCATION_CHOICES` and
 * `OpenBillPicker` are shared: the strip promises which instalment the money
 * will meet, and two implementations of that promise would eventually disagree
 * with each other and with the service.
 */
export function useAccountPlan(accountId: string, client: ApiClient) {
  return useQuery({
    queryKey: accountPlanKey(accountId),
    queryFn: () => getPaymentPlans(accountId, client),
    enabled: accountId !== "",
    retry: false,
  });
}

/** The instalment a payment meets by default — earliest by `seq`, unpaid.
 *
 *  Mirrors `plans.earliest_unmet_installment`: ordered by the customer's own
 *  numbering, never by due date, and reading no clock. `null` when every
 *  instalment is met, which is a plan about to close and not an error. */
export function nextUnmetInstallment(
  plan: PaymentPlanRow,
): PaymentPlanInstallmentView | null {
  const unmet = plan.installments
    .filter((row) => row.paid_posted_on === null || row.paid_posted_on === undefined)
    .sort((a, b) => a.seq - b.seq);
  return unmet[0] ?? null;
}

export function PlanInstallmentStrip(props: {
  /** The account's LIVE plan, or null when it has none. */
  plan: PaymentPlanRow | null;
  /** True while the plan read is in flight — told apart from "no plan". */
  pending: boolean;
  /** The server's own reason the plans could not be read, or null. */
  unavailable: string | null;
  /** The instalment the clerk NAMED, or null for the ruled default. */
  chosenSeq: number | null;
  onChoose: (seq: number | null) => void;
  t: Translator;
}) {
  const { t, plan } = props;
  if (props.pending) {
    return <p className="pay-form-note">{t("payments.plan.loading")}</p>;
  }
  // ⚠ `null` PLANS AND AN EMPTY LIST ARE DIFFERENT FACTS (DEF-127). Payments
  // publishes the read; an unwired deployment answers null WITH a reason, which
  // is NOT the "this account has no plan" an ordinary account answers.
  if (props.unavailable !== null) {
    return <p className="pay-form-note">{t("payments.plan.unreadable")}</p>;
  }
  // No plan is not an absence worth a sentence on a payment form — B14 rule 32
  // ("a screen has a description budget") and rule 12's own posture: a control
  // for a thing that does not exist teaches nothing.
  if (plan === null) {
    return null;
  }
  const defaultRow = nextUnmetInstallment(plan);
  if (defaultRow === null) {
    return <p className="pay-form-note">{t("payments.plan.allMet")}</p>;
  }
  const chosen =
    plan.installments.find((row) => row.seq === props.chosenSeq) ?? defaultRow;
  const unpaid = plan.installments
    .filter((row) => row.paid_posted_on === null || row.paid_posted_on === undefined)
    .sort((a, b) => a.seq - b.seq);
  return (
    <div className="pay-pair-list">
      <p className="pay-form-note">
        {/* CR-059 P1's own sentence: "Instalment 2 of 6 · 36.22 · due 01 Oct". */}
        {t("payments.plan.meeting", {
          seq: chosen.seq,
          count: plan.installment_count,
          amount: formatMoney(chosen.amount, chosen.currency ?? plan.currency),
          due: chosen.due_date,
        })}
      </p>
      {/* CS-23: *"with the option to change it"*. Only UNPAID rows are
          offered — an instalment already met is refused by the service by name
          (`plan_installment_already_paid`), and offering it would be a control
          that can only produce a refusal. */}
      <label className="pay-inline-field">
        <span className="pay-sub">{t("payments.plan.changeLabel")}</span>
        <select
          value={props.chosenSeq === null ? "" : String(props.chosenSeq)}
          onChange={(event) =>
            props.onChoose(event.target.value === "" ? null : Number(event.target.value))
          }
        >
          <option value="">{t("payments.plan.useDefault", { seq: defaultRow.seq })}</option>
          {unpaid.map((row) => (
            <option key={row.seq} value={String(row.seq)}>
              {t("payments.plan.option", {
                seq: row.seq,
                due: row.due_date,
                amount: formatMoney(row.amount, row.currency ?? plan.currency),
              })}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

// ── The vocabularies these screens render (server constants, one copy) ─────

/**
 * A2 §S34's four ageing bands + `current`, keyed to catalogue-safe slugs.
 *
 * The SERVER's own values are `1-30` / `90+` and they stay the values on the
 * wire; only the catalogue leaf is slugged, because a `+` in an i18n key is a
 * character the parity gates read as punctuation rather than as a name.
 */
export const AGEING_BUCKET_SLUGS: Record<string, string> = {
  current: "current",
  "1-30": "d1_30",
  "31-60": "d31_60",
  "61-90": "d61_90",
  "90+": "d90_plus",
};

export function bucketLabel(bucket: AgeingBucket | string, t: Translator): string {
  const slug = AGEING_BUCKET_SLUGS[bucket];
  // An unrecognised band renders its own raw value rather than a label for a
  // band it is not: the server owns this vocabulary and a fifth value would be
  // a real change nobody here may paper over.
  return slug === undefined ? bucket : t(`payments.bucket.${slug}`);
}

/** BR-PAY-017's rungs (`ladder.LADDER_RUNGS`) — the tier a row has reached. */
export function collectionTierLabel(tier: string, t: Translator): string {
  return t(`payments.tier.${tier}`);
}

/** `collections_models` plan statuses — proposed · agreement_sent · active · closed. */
export function planStatusLabel(status: string, t: Translator): string {
  return t(`payments.planStatus.${status}`);
}

/** Why the ladder did NOT step an account (`ladder.SKIP_*` and
 *  `notices.SKIP_*` — TWO modules reach this one renderer). Every skip is a
 *  decision, never an absence — J4 step 2 requires each one to be visible.
 *
 *  ⚠ **THE FALLBACK IS THE POINT, AND IT WAS A CLAIM BEFORE IT WAS CODE
 *  (`DEF-PAY-6284`).** i18next returns THE KEY ITSELF when it cannot resolve
 *  one, so this was `t(key)` and an uncatalogued code put
 *  `payments.skip.tier_already_sent` in front of a clerk — B14 rule 31 — at
 *  the moment the Send-notice wizard had just posted real letters.
 *  `SendNoticeWizard`'s own `SkipCell` already PROMISED the behaviour written
 *  here (*"an unknown code renders the fact of the skip without pretending to
 *  know why"*); hard-won law 1 says a comment claiming a guarantee is not the
 *  guarantee, so the promise is now kept in code.
 *
 *  It is a second line of defence, never the first: every code either module
 *  can emit MUST carry real words, and
 *  `06-backend/tests/test_def_pay_6284_skip_codes_have_words.py` fails by name
 *  when one does not. `G15` cannot see that — it checks PARITY across the
 *  eleven catalogues, and a key absent from all eleven is parity-perfect,
 *  which is how this escaped twice in one day. */
export function ladderSkipLabel(reason: string, t: Translator): string {
  const key = `payments.skip.${reason}`;
  const words = t(key);
  return words === key ? t("payments.skip.unlisted") : words;
}

// ── Write-offs (US-PAY-012 / BR-PAY-020) ───────────────────────────────────

/**
 * The four reasons `collections_models.WRITE_OFF_REASONS` will accept.
 *
 * The prototype's write-off modal offers FIVE and two extra checkboxes; three
 * of those are not offered here and each is refused by name rather than
 * silently dropped:
 *
 *   · *"Sent to collections agency"* — field-map P-4, no ratified rule, and the
 *     `reason` column carries a CHECK constraint that would refuse the value.
 *   · *"Flag these accounts so future service requires a deposit"* — P-5, same.
 *   · *"GL account"* (6100 Bad Debt / 6110 Allowance) — the posting picks the
 *     designated bad-debt account through the ledger seam (BR-PAY-020), and a
 *     picker here would let a clerk post bad debt to an account finance did not
 *     designate.
 */
export const WRITE_OFF_REASON_CODES = [
  "uncollectible_120_days",
  "customer_bankruptcy",
  "deceased_no_estate",
  "below_write_off_threshold",
] as const;

export function writeOffReasonLabel(reason: string, t: Translator): string {
  return t(`payments.writeOff.reason.${reason}`);
}

// ── B14 rule 32 · the copy a screen keeps but does not lead with ───────────

/**
 * ⚠ **THE SECOND, THIRD AND FOURTH SENTENCES OF A PAYMENTS SCREEN GO IN HERE,
 * CLOSED (B14 rule 32).** Walking all four Payments tabs on 2026-09-03 the
 * Product Owner said *"on this screen too much content"*, *"too much text on
 * the form"* and *"why we are shoiwng this"* — the same complaint that ratified
 * the rule on 2026-08-31 in the words *"desctiption is too much for clark to
 * read"*.
 *
 * **NOTHING IS DELETED BY MOVING IT HERE, AND THAT IS THE POINT.** Every
 * sentence a lane wrote to stop the next reader filing a gap as a bug is still
 * in the DOM, still found by `Ctrl-F`, still counted by `G38`. It is simply not
 * the first thing a clerk meets. A `<details>` is the right primitive because
 * **being closed is what it IS** — the copy cannot leak back onto the screen
 * through a prop nobody passes, which is how it got there in the first place.
 *
 * ⚠ **THIS IS `features/rating/ratingShared.tsx`'s `MoreAbout` WRITTEN OUT
 * AGAIN, NOT IMPORTED, AND THE DIFFERENCE IS ONE LINE OF CLASSES.** That one
 * carries `mt-3` and a `text-[color-mix(…)]` bracket on its summary, which
 * compile because `ratingShared.tsx` is listed in
 * `src/styles/route-b-migrated.txt`. **No payments file is on that list**
 * (DEF-974), so a utility written here is a class no stylesheet declares: it
 * renders as NOTHING while `tsc`, eslint and every `toContain` assertion pass,
 * because the class IS in the DOM. `.field-help` is the declared class this
 * product already styles a small muted line with, and it is reused rather than
 * a new one being added — `G31` reports the stylesheets are AT rule 21's
 * ceiling of 470 classes, so there is no room for a `.pay-disclosure` and no
 * need for one.
 */
export function MoreAboutPayments(props: { summary: string; children: ReactNode }) {
  return (
    <details>
      <summary className="field-help">{props.summary}</summary>
      <div className="pay-form-note">{props.children}</div>
    </details>
  );
}

// ── `problems[]` — the absences the server refuses to guess at ─────────────

/**
 * Every named absence, rendered — **inside a `<details>` CLOSED by default**.
 *
 * The README's fourth rule, verbatim: *"Render `problems[]`. Both bodies carry
 * them and each names something the product genuinely cannot answer yet … A
 * screen that drops them is the comment that claims a guarantee."* The CODE is
 * rendered through the catalogue and the server's English `detail` is never
 * printed (B8 — the server sends codes, the UI renders language).
 *
 * ⚠ **IT WAS OPEN UNTIL 2026-09-03 AND THE PRODUCT OWNER READ IT ON TWO TABS
 * AT ONCE.** Verbatim, of the Summary and of Outstandings: *"why we are shoiwng
 * this - What is missing * Finance owns this formula... * Medical protections
 * cannot be shown here..."*. Both are true and neither is something a clerk
 * taking a cheque can act on. B14 rule 32 says a stated absence is a `<details>`
 * CLOSED by default; `SummaryTab.tsx`'s own 2026-09-01 trailer already recorded
 * this as *"REPORTED, NOT DONE"* because the component is shared with S34 —
 * which is exactly why closing it here fixes both screens in one edit.
 *
 * **Closed is not deleted.** The list is in the DOM, the codes still route
 * through the catalogue, and a clerk who wants to know why a figure is absent
 * is one click away.
 */
/** The one place the family's key is spelled. */
export const PROBLEM_KEY_PREFIX = "payments.problem.";

/**
 * Codes whose SENTENCE was deleted on purpose, by name and with its reason.
 *
 * ⚠ **THIS LIST IS THE PROVENANCE, AND KEEPING IT IS THE POINT.** B14 rule 33
 * puts RATIONALE at ZERO WORDS ON SCREEN and says where it goes instead: *"it
 * belongs in the code and the register"*. This is the code half. Rule 31 says
 * the same thing about an internal reference — *"The provenance is not deleted,
 * it MOVES to the code comment beside the string"* — so a later lane meeting a
 * code with no words finds out here why, rather than assuming somebody forgot.
 *
 * Product Owner, 2026-09-23, having been shown the panel and offered (a) delete
 * all 40, (b) keep the facts / shorten to six words / delete the reasons, or
 * (c) leave as is, verbatim: ***"(b) Keep the facts, shorten to six words,
 * delete the reasons"*** (`DEF-PAY-6327`).
 *
 *   * `dso_not_computed_here` — *"Finance owns this formula. It is not worked
 *     out here."* The PO's own example of what they could not act on. Pure
 *     rationale: it explains why a figure is absent, and the absence is already
 *     visible on the tile. **Still emitted** by `outstandings.py`, so it is
 *     listed here rather than merely un-keyed.
 *   * `no_receipt_queued` — deleted for a SECOND reason as well (`DEF-PAY-6330`):
 *     the sentence was FALSE. It said sending receipts "is not built" for five
 *     weeks after `receipts.queue_receipt_for_recorded_payment` started running
 *     on every payment, and the code left `RECORD_UNAVAILABLE` on 2026-08-18.
 *   * `grouped_bank_credits_not_matchable` — the same fault (`DEF-PAY-6330`):
 *     it told a clerk *"Those deposits will stay unmatched"* on the same page as
 *     the control that matches them, from the day `CR-059` task 45 landed
 *     `match_set` on 2026-09-01.
 *
 * ⚠ **`medical_hold_not_readable` IS NOT ON THIS LIST AND IS NOT AN OVERSIGHT —
 * IT WAS RULED KEPT, NOT DELETED (`OQ-PAY-12612`, 2026-09-24).** PO, verbatim:
 * *"p6 b) Keep a short version: "Medical protections apply. Not shown here.""*.
 * It was the PO's other quoted bullet and it classifies as rationale on the same
 * reading as the first entry — but it is the only one of the four where a
 * SAFETY argument exists, because a clerk who does not know a debtor is
 * medically protected might chase them, and the PO took that half of it.
 *
 * ⛔ **SUPERSEDED — the hold this paragraph used to carry.** It read *"It is
 * HELD, unchanged, pending a PO ruling put to them on 2026-09-23"*, over the
 * English *"Medical protections cannot be shown here. Notices still apply
 * them."*. The hold expired the day the ruling landed, and the two assertions
 * that were written to feel it (`SummaryTab.test.tsx`, `OutstandingsTab.
 * test.tsx`) now name the new sentence LITERALLY rather than through `t()` —
 * hard-won law 2's second half: write the test that fires when the hold
 * expires, and then make sure somebody actually released it.
 *
 * The kept sentence is a FACT at three words and three (rule 33's six-word
 * cap); what went is the clause explaining WHY the screen cannot show the hold,
 * which is rationale and is zero words on screen. Do not sweep it up as a
 * straggler.
 */
export const PROBLEM_CODES_DELETED_ON_PURPOSE: readonly string[] = [
  // `DEF-PAY-10736` (L2-05, PO 2026-10-30 *"Rest we will fix"*) — *"The account
  // balance is not refreshed."* rode record, reapply, refund, transfer and
  // reversal. It names a CACHE column a clerk never sees and cannot refresh;
  // the account screen computes its balance from the ledger. The SERVER keeps
  // returning the code (a caller may still reason about it); screens say
  // nothing. Its catalogue key was RETIRED from all eleven on 2026-10-30
  // (lane NSF-2, `i18n_fanin.retire`), so this list is the provenance.
  "account_balance_cache_not_updated",
  "dso_not_computed_here",
  "grouped_bank_credits_not_matchable",
  "no_receipt_queued",
];

/**
 * `DEF-PAY-10733` (L3-01) — the ONLY outcomes the Record-payment result panel
 * shows a clerk. Everything else on a recorded payment's `problems[]` is the
 * receipt queue's bookkeeping (`template_pin_resolved_at_queue_write`,
 * `print_floor_channel_added`, `channel_has_no_rule_toggle`, …), up to a dozen
 * codes per payment, and the tester read them as raw keys. An ALLOW-list rather
 * than a deny-list because the queue mints new codes and each one would
 * otherwise reach the panel the day it is added. Each kept code is a fact the
 * clerk acts on, worded in ≤ 2 short sentences (B14 rule 33).
 */
export const RECORD_RESULT_CLERK_CODES: readonly string[] = [
  "billing_publishes_no_invoice_read",
  "duplicate_submit_ignored",
  "awaiting_finance_approval",
  "recipient_absent_on_record",
];

/**
 * `DEF-PAY-10783` (PO 2026-10-31 P11 = A) — when a payment carries more than one
 * of the codes above, the panel says ONE: the one that changes what the clerk
 * does next. Money first (not applied; not in the books yet), then the replay,
 * then the receipt with nobody to send it to.
 */
export const RECORD_RESULT_PRIORITY: readonly string[] = [
  "billing_publishes_no_invoice_read",
  "awaiting_finance_approval",
  "duplicate_submit_ignored",
  "recipient_absent_on_record",
];

/** The ONE clerk-facing warning for a recorded payment, or null. */
export function firstRecordOutcome(
  t: Translator,
  problems: readonly { code: string }[],
): { code: string; words: string } | null {
  const lines = recordOutcomeLines(t, problems);
  const rank = (code: string) => {
    const at = RECORD_RESULT_PRIORITY.indexOf(code);
    return at === -1 ? RECORD_RESULT_PRIORITY.length : at;
  };
  return [...lines].sort((a, b) => rank(a.code) - rank(b.code))[0] ?? null;
}

/** The clerk-facing lines for a recorded payment — allow-listed, worded, and
 *  each said once (the queue repeats a code per channel). */
export function recordOutcomeLines(
  t: Translator,
  problems: readonly { code: string }[],
): { code: string; words: string }[] {
  const seen = new Set<string>();
  const lines: { code: string; words: string }[] = [];
  for (const problem of problems) {
    if (!RECORD_RESULT_CLERK_CODES.includes(problem.code) || seen.has(problem.code)) {
      continue;
    }
    seen.add(problem.code);
    const words = problemWords(t, problem.code);
    if (words !== null) {
      lines.push({ code: problem.code, words });
    }
  }
  return lines;
}

/**
 * One code → the words a clerk reads, or NOTHING.
 *
 * ⚠ **THREE OF THE FIVE RENDER SITES OF THIS FAMILY PRINTED A RAW DOTTED KEY AT
 * A CLERK (`DEF-PAY-6328`), AND ONE OF THEM WAS THIS COMPONENT.** `i18n` is
 * configured `keySeparator: false`, so `t()` on a missing key returns the KEY:
 * the literal text `payments.problem.receipt_queued` on screen. That code rides
 * `problems` on every recorded payment behind an election that is default ON,
 * and 60 codes emitted from `apps/payments` have no key in this family at all.
 * `depositsShared.tsx` and `PaymentsPage.tsx:1981` each grew their own private
 * fallback; `ProblemList`, `BadDebtCaveats` and `PaymentsPage.tsx:1361` had
 * none. That is B14 rule 43's shape — the same piece of UI written out five
 * times, so a fix to one is not a fix to the others — and this function is the
 * one answer the sites that can share it now share.
 *
 * **AN UNLISTED CODE RENDERS AS NOTHING, AND THAT IS A DECISION RATHER THAN A
 * DEFAULT.** The two fallbacks that already existed disagreed: one printed
 * *"This deployment reports a limit. It has no wording yet."* and the other
 * printed an empty string. Nothing is right, for two reasons that both come
 * from rule 33. A missing key is OUR omission and the sentence describing it is
 * RATIONALE — why the product behaves this way — which the rule puts at zero
 * words. And the sentence names *"this deployment"*, which is internal
 * vocabulary a utility clerk has no use for (rule 32). A clerk can act on
 * neither the confession nor the code; the honest build is silence.
 *
 * ⚠ **AND A CODE WITH NO WORDS IS NOT AUTOMATICALLY A CODE THAT WANTS WORDS —
 * THE OBVIOUS FIX FOR `DEF-PAY-6328` IS WRONG FOR AT LEAST TWO OF THE SIXTY.**
 * Reading them before writing for them is the whole of B14 rule 33's test, and
 * two of the ones this component renders fail it:
 *
 *   * `nothing_posted_to_the_ledger` (a reapply, `reapply.py`) — the server's
 *     own detail says *"a reapply posts NO journal entry, and that is the rule
 *     rather than an omission … nothing an entry could make more true"*. The
 *     cash total has not moved; only which bill the money met, which is what
 *     the screen already shows. That is rationale, and rationale is zero words.
 *   * `account_balance_cache_not_recomputed` (a transfer, `transfer.py`) — the
 *     detail is explicit that it is named *"only because this module cannot
 *     state what that cache holds, never because it is known to be wrong"*.
 *     **It is NOT the sibling `account_balance_cache_not_updated`**, which IS
 *     worded, because there the balance really is stale after a payment and a
 *     clerk must not trust it. Here nothing should have changed it, so
 *     *"the account balance is not refreshed"* would be worded AND false.
 *
 * So `DEF-PAY-6328` is closed by giving each of the sixty a READING, not by
 * giving each of them a sentence. These two are already rendered as nothing and
 * that is the finished state for them, not a gap.
 *
 * ⚠ **SILENCE IS ONLY SAFE BECAUSE SOMETHING COUNTS IT** — hard-won law 7's
 * fifth shape is a check reporting zero over a scope it silently excludes, and
 * a code that vanishes with no trace is exactly that. `problemWords.rule33.
 * test.ts` asserts what this function RENDERS rather than what the catalogue
 * holds, so a dotted key reaching a clerk goes red there. The 60 unkeyed codes
 * are counted in `DEF-PAY-6328` rather than left as an absence with no number
 * beside it.
 */
export function problemWords(t: Translator, code: string): string | null {
  if (PROBLEM_CODES_DELETED_ON_PURPOSE.includes(code)) {
    return null;
  }
  const words = t(`${PROBLEM_KEY_PREFIX}${code}`, { defaultValue: "" });
  return words.trim() === "" ? null : words;
}

export function ProblemList(props: { problems: readonly PaymentsProblem[]; title: string }) {
  const { t } = useTranslation();
  // Resolved BEFORE the panel is drawn, because a list whose every code is
  // wordless must not leave an empty `<details>` inviting a clerk to open
  // nothing — that is hard-won law 2's dead UI, one click further in.
  const lines = props.problems
    .map((problem) => ({ code: problem.code, words: problemWords(t, problem.code) }))
    .filter((line): line is { code: string; words: string } => line.words !== null);
  if (lines.length === 0) {
    return null;
  }
  return (
    <details className="pay-problems">
      <summary>{props.title}</summary>
      <ul>
        {lines.map((line) => (
          <li key={line.code}>{line.words}</li>
        ))}
      </ul>
    </details>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE ACCOUNT PICKER — DEF-3506
// ══════════════════════════════════════════════════════════════════════════
// Product Owner, walking the deployed build on 2026-09-03, verbatim: *"On this
// payment record form unable to search account"*. They typed `AC-2026-00050`
// into "Find the account" and the Account dropdown below still read "Choose an
// account".
//
// **THE WIRE PATH WAS NEVER BROKEN**, and saying so plainly matters because the
// obvious fix would have been to the request. The query fired, the rows came
// back and the options landed in the select — `accountSearch.dom.test.tsx`
// keeps the case that proves it. What was wrong was everything around it:
//
//   1. **The two-character gate trimmed the term and the request did not.**
//      `enabled: accountQuery.trim().length >= 2` sat beside
//      `getAccounts({ q: accountQuery })`. A number pasted out of a spreadsheet
//      cell or an email carries whitespace, and `account_no ILIKE
//      '%AC-2026-00050 %'` matches nothing at all. Payments was the odd one out
//      of the product's three account searches, TWICE — `customers/
//      accountFinder.tsx` and `metering/OwnerAccount.tsx` both send the trimmed
//      term, and both this modal and S36's refund modal did not.
//   2. **Searching, no-match and failed were all drawn as nothing.** The select
//      renders its placeholder in every one of those states AND in the success
//      state, so a clerk cannot tell "still looking" from "no such account"
//      from "the search could not run" from "your match is in here, open me".
//      That is the PO's sentence exactly.
//
// The shape below is `customers/accountFinder.tsx`'s, which is the ratified
// pattern for this in the product — read, not imported: it belongs to another
// feature and another lane, and its `AccountFinder` takes an `idPrefix` and
// draws a wizard step, where these two are modal fields whose ids the zod
// schemas key on (`account_id`).

/** IS-3, and the same two the server holds (`selectors.MIN_SEARCH_CHARS`). */
export const ACCOUNT_SEARCH_MIN_CHARS = 2;

/**
 * What the picker knows, as ONE value rather than three booleans a caller
 * assembles. `searched` is what separates *no such account* from *not asked
 * yet* — the distinction the two screens above were rendering identically.
 */
export interface AccountSearchState {
  matches: readonly AccountRow[];
  /** Below the minimum length, or nothing typed at all. */
  idle: boolean;
  /** The request is in flight. */
  searching: boolean;
  /** The search RAN, so an empty `matches` means "no such account". */
  searched: boolean;
  /** The search itself could not be run — a PLATFORM fact, never a term fact. */
  failed: boolean;
}

const ACCOUNT_SEARCH_IDLE: AccountSearchState = {
  matches: [],
  idle: true,
  searching: false,
  searched: false,
  failed: false,
};

/**
 * The account search behind both payment pickers.
 *
 * ⚠ **`q` IS THE TRIMMED TERM AND THE GATE READS THE SAME STRING.** That is
 * DEF-3506's mechanical half: one `trimmed` local, used by both, so the two can
 * never disagree again. `queryKey` carries it too, so re-typing a term that was
 * already searched is answered from cache with no second request.
 *
 * `keyPrefix` keeps the S22/S35 modal's cache separate from S36's, because the
 * two ask the same question on different screens and a shared key would make
 * one screen's in-flight state visible on the other.
 */
export function useAccountSearch(
  term: string,
  client: ApiClient,
  keyPrefix: string,
): AccountSearchState {
  const trimmed = term.trim();
  const enabled = trimmed.length >= ACCOUNT_SEARCH_MIN_CHARS;
  const query = useQuery({
    queryKey: ["payments", keyPrefix, trimmed],
    queryFn: () => getAccounts({ q: trimmed, per: 50 }, client),
    enabled,
    retry: false,
  });
  if (!enabled) {
    return ACCOUNT_SEARCH_IDLE;
  }
  return {
    matches: query.data?.results ?? [],
    idle: false,
    searching: query.isPending,
    searched: query.isSuccess,
    failed: query.isError,
  };
}

/**
 * One account, as the picker names it. Both halves are nullable — an account
 * number can be absent and BR-CUS-054's `customers` entity is unbuilt, so
 * `name` is the primary CONTACT's — and an option with an empty label is one a
 * clerk can select without knowing whose money they are taking.
 *
 * ⚠ **THE DATABASE ID IS THE LAST RESORT AND IT IS NOT A LABEL (B14 rule 31).**
 * A row with neither number nor name gets the catalogue's own words for that
 * state; printing `acc-0050` would put a key on screen, which the PO ruled out
 * on 2026-08-31 in the words *"no Databse ID on screen - that is a rule"*.
 */
export function accountPickerLabel(account: AccountRow, t: Translator): string {
  if (account.account_no !== null && account.name !== null) {
    return `${account.account_no} — ${account.name}`;
  }
  return account.account_no ?? account.name ?? t("payments.form.accountUnnamed");
}

/**
 * ONE control: the clerk types the account into it and chooses from the panel
 * that opens under it.
 *
 * ⚠ **THIS WAS TWO FIELDS UNTIL 2026-09-23 (`DEF-PAY-6319`).** Product Owner,
 * on the Raise-a-refund form, verbatim: *"why to button - why cannot we have
 * dropdown search drectly for this - user has to do two clicks"*, and then,
 * having been told why it was built that way: *"fix it"*. A "Find account" box
 * and an "Account" select that appeared beneath it once something matched —
 * two gestures to choose one account.
 *
 * ⚠ **THE REASON FOR THE SPLIT WAS REAL AND IT SURVIVES INTACT.** The note that
 * stood here said: *"THE PICKER IS DRAWN ONLY WHEN SOMETHING MATCHED. A select
 * holding one placeholder is what made all four states look alike; an absent
 * select plus a sentence is what tells a clerk which of them they are in."*
 * That is `DEF-3506`, and it is still true — a clerk must be able to tell
 * **typed too little** from **searching** from **the search itself failed**
 * from **nothing matched that term** from **here are your matches**, and the
 * last two look identical in a naive dropdown while meaning opposite things.
 * **What was load-bearing was the five states, not the second control.**
 * `RemoteSearchSelectField` draws all five INSIDE the one panel, in the same
 * two visual registers — `Note` for the three ordinary ones, `RefusalStrip`
 * for the platform failure (BR-SHL-020) — and in the same words: not one
 * catalogue key moved.
 *
 * ⚠ **IT IS A KIT COMPONENT AND NOT A LOCAL ONE (B14 rules 43 and 36).** The
 * two-field pattern was copied into `customers/accountFinder.tsx` and
 * `metering/OwnerAccount.tsx` because the kit had nothing to reach for — its
 * one combobox, `SearchSelectField`, filters a list already in hand and cannot
 * say *"the search could not run"*. The next screen that must find a record on
 * the server gets this for free.
 *
 * ⚠ **THE EXPORTED NAME AND THE PROPS ARE UNCHANGED ON PURPOSE.** Four screens
 * compose this — S22/S33/S35's Record payment, S36's Raise a refund, Issue
 * credit and Move/reapply — and a lane was building a fifth host while this was
 * written. Only the internals moved, so no call site needed an edit.
 */
export function AccountPickerFields(props: {
  searchLabel: string;
  accountLabel: string;
  term: string;
  onTermChange: (term: string) => void;
  search: AccountSearchState;
  /** The chosen account id — `""` until one is picked. This is what posts. */
  value: string;
  onChange: (accountId: string) => void;
  t: Translator;
  /** `DEF-PAY-10706` — the panel starts put away when a door has already
   *  chosen the account (*Pay units*), exactly as the kit's own prop says. */
  startClosed?: boolean;
}) {
  const { search, t } = props;
  return (
    <RemoteSearchSelectField
      // ⚠ **THE ID STAYS `account_id`, AND IT IS THE FORM'S KEY.** Every one of
      // the four hosts validates `account_id` through its zod schema and the
      // server names the same field in a refusal, so this is the id an error
      // has to find. The old `account_query` box was a second id for the same
      // question and is gone with the second control.
      id="account_id"
      // The field's NAME (B14 rule 33: a label is ≤ 3 words and no sentence).
      label={props.accountLabel}
      // …and the search is what the box invites, so it is the placeholder. Both
      // strings the four hosts already pass are still on screen; neither moved
      // catalogue.
      placeholder={props.searchLabel}
      term={props.term}
      onTermChange={props.onTermChange}
      status={search}
      // B14 rule 31: the id is the VALUE — what posts — and `accountPickerLabel`
      // is the only thing a clerk reads. Its fallbacks are untouched: number and
      // name when both are there, whichever exists when one is, and the
      // catalogue's own words for an account with neither.
      options={search.matches.map((account) => ({
        value: account.id,
        label: accountPickerLabel(account, t),
      }))}
      value={props.value}
      // Typing clears the choice inside the control, so every host's own
      // dependent-field clearing — the refund's payment, the credit's bill —
      // still fires exactly when it did.
      onChange={props.onChange}
      startClosed={props.startClosed}
      words={{
        tooShort: t("payments.form.accountTooShort"),
        searching: t("payments.form.accountSearching"),
        // BR-SHL-020. THE PLATFORM failed — the only one of the four that
        // support can act on, and the only one drawn as a refusal.
        failed: t("payments.form.accountSearchFailed"),
        // ⛔ NOT A REFUSAL. The search ran and the answer was "no account of
        // yours looks like that" — a fact about the TERM, which is the one the
        // clerk can act on.
        noMatch: t("payments.form.accountNoMatch"),
      }}
      help={t("payments.form.accountSearchHelp")}
      required
    />
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-004@0f1a7c3 (story+rules snapshot — EP-PAY-01 US-PAY-004 lead; co-packet US-PAY-001, same epic; 08-payments/02-business-rules.md; 11b §1 + §2.9)
// generated: 2026-08-11 by story-coder (W4 payments FRONTEND lane — the S33 ledger and the Record modal the payments API landed without)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔ (G13 unwired-props, G14 prototype-conformance, G15 i18n-parity, G18 i18n call sites and G19 hostnames included)
// amended:   2026-08-15 by story-coder (payments FRONTEND visible-half lane) — the S32/S34 vocabularies (ageing bands, ladder rungs, plan states, skip reasons, write-off reasons), the exact `sumDecimalStrings` (BigInt on the NUMERIC(18,6) grid, never a float), `Money` (MoneyCell where the tenant's CHAR(3) could be read, a stated absence where it could not) and `ProblemList`. TWO CLAIMS IN THIS FILE WERE FALSIFIED AND REWRITTEN rather than left to rot (hard-won law 1): that the S34 read-model "is not built", and the Rules block's silence about the money path this file now composes.
// exceptions: (1) the payments page LANDS on Summary, where the prototype opens on Record payments — the ratified sidebar (BR-SHL-001) maps `/payments` to Summary and a nav item must land where its label says · (2) the third tab drops the prototype's "(184)" count: it is US-PAY-013's live aggregate and a hardcoded number would be a claim about a tenant's debtors · (3) `specific` and `split` render DISABLED with their reason (OQ-154 — no endpoint serves an account's OPEN bill position) · (4) `newest_first` is NOT offered on the form: BR-PAY-010 makes the order a tenant SETTING, not a per-payment staff choice · (5) [2026-08-15] `GET /outstandings` and `GET /payments/summary` serve every amount with NO CHAR(3) currency code; `paymentsDisplayCurrency` reads the tenant's own off `GET /payments` under BR-TEN-042's currency lock and `Money` states the absence when it cannot — REPORTED as the one backend shape change these two screens want, never guessed as USD
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
