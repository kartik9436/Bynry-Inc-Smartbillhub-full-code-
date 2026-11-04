// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · CS-6 · CS-7 · task 18 — **P3, the whole refunds page**.
//           The CR's own words: *"P3 · Refunds (S58, `/finance/refunds`, no
//           screen at all today) … The whole screen: tabs for awaiting
//           approval · issued · all; Raise, Issue and Mark-cleared actions."*
// Story:    US-PAY-011 (refunds) · J15 steps 1–4
//           Screens: S58 (Record refund + the approval queue)
// Rules:    BR-PAY-014 (CONFIRMED — *"Refunds only from a real credit balance;
//           Admin approval; check/ACH v1; DR customer-credit / CR cash;
//           immutable row + receipt"*, amended 2026-08-12: the clerk chooses
//           refund or credit, and a refund may be raised against the CREDIT
//           BALANCE) · BR-PAY-037 (one user MAY initiate and approve in v1, as
//           long as both acts are recorded separately) · BR-PAY-1071 (NEW
//           2026-09-01 — `issue_refund` and `clear_refund` carry a SERVICE role
//           gate) · BR-SHL-020 (plain-language failure) · BR-SHL-023 (one money
//           path) · BR-SHL-025 (a control this role may not use renders
//           DISABLED WITH ITS REASON, never hidden) · BR-SHL-044 (one header) ·
//           B14 rule 15 (row actions are ICONS) · B14 rule 31 (no database id
//           is the visible value of a field) · CLAUDE.md hard rule 4 (a void is
//           a status move plus a reversing posting, never a removal)
// Ruling:   OQ-135 (2026-08-12, CLOSED — offset first) · OQ-132 (2026-08-11,
//           CLOSED — a credit may go below zero and is a real debt) · CR-059 §6
//           Q6 (2026-09-01 — a refund belongs to the ACCOUNT)
// Impacts:  App.tsx route · paymentsShared.REFUNDS_ROUTE ·
//           ledger/RefundsQueuePanel (the door, inside Revenue & AR)
// Amended:  2026-09-03 — ⚠ **THIS WAS AN EIGHTH FINANCE TAB AND IT IS NOT ONE
//           NOW.** PO ruling 2026-09-03, asked directly, verbatim: *"C25 says
//           six tabs. - this is correct."* `CR-060` `C25` names its six and
//           Refunds is not among them, so `financeShared.FINANCE_TABS` is back
//           to six. **The page is RE-HOMED, not withdrawn:** `/finance/refunds`
//           stays routed for the links already in circulation and this file is
//           unchanged below the header except for the tab it highlights. The
//           DOOR is `RefundsQueuePanel` inside Revenue & AR — `C25`'s own
//           principle, the one that folded Write-offs there *"where the
//           receivable it gives up already lives"*, because a refund gives back
//           money the account holds as CREDIT and the credit position lives in
//           that tab. Full reasoning: `02-decision-log.md` 2026-09-03 and
//           `CR-060` §0d.2.
// ───────────────────────────────────────────────────────
//
// S58 — REFUNDS, END TO END. The screen the whole outbound half of this module
// had been waiting for.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT WAS BEHIND THIS SCREEN, AND HOW LONG IT HAD BEEN FINISHED
// ══════════════════════════════════════════════════════════════════════════
// `apps/payments/refunds.py` could request, approve, issue, clear and void a
// refund — the credit tested twice, the DR 2400 / CR 1000 posting, the cheque
// clearing the bank, the reversing posting on a void — and **no person could
// reach any of it.** The approval queue `GET /refunds` has been mounted since
// 2026-08-28 and **could never have held a row**, because nothing in the
// product could RAISE a refund: only the demo seeder called `request_refund`.
// The three missing routes landed on 2026-09-01 (CS-6, task 17); this is their
// screen, and task 17's own row says the closure bar is a person doing it here.
//
// ══════════════════════════════════════════════════════════════════════════
// FIVE ACTS, FIVE GATES, AND EVERY ONE OF THEM IS THE SERVER'S
// ══════════════════════════════════════════════════════════════════════════
//   Raise          Admin or Clerk   — a clerk may ask; only an Admin may pay.
//   Approve        Admin            — BR-PAY-014's approval. Moves no money.
//   Issue          Admin            — THE MONEY LEAVES HERE.
//   Mark cleared   Admin or Exec    — *"a bank fact, not an approval"*.
//   Void           Admin            — a status move plus a reversing posting.
//
// Every one of those is enforced by `@require_role` on the SERVICE (BR-PAY-014,
// BR-PAY-1071) and mirrored on the route. What this screen does with the role
// is decide whether a control is OFFERED or **drawn disabled with its reason**
// (BR-SHL-025) — never hidden, so a clerk learns the rule instead of hunting
// for a control somebody removed.
//
// ══════════════════════════════════════════════════════════════════════════
// THE CREDIT FIGURE IS NEVER CACHED, AND THAT IS CS-6'S OWN *WATCH FOR*
// ══════════════════════════════════════════════════════════════════════════
// *"A credit real on Tuesday can be gone by Thursday, and the money moves on
// Thursday."* Every step answers with `credit_position_after`, computed by the
// service inside that step's own transaction, and this screen renders the
// figure it was just handed and keeps none between one act and the next. The
// credit is tested at request AND AGAIN at issue by the service; an approval
// given on Tuesday does not pay out a credit a Wednesday bounce pulled back.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS SCREEN CANNOT SAY, AND WHY IT SAYS SO INSTEAD OF GUESSING
// ══════════════════════════════════════════════════════════════════════════
// CR-059 §10 asks for *"the refundable position shown BEFORE the amount, with
// what the customer owes elsewhere already deducted"* and for *"Built from
// 40.00 (June) + 17.13 (July)"*. **Neither can be served today and neither is
// invented here** — `DEF-3119`:
//
//   · **No route publishes an account's credit position.** `credit.py` computes
//     it and `selectors.account_credit_position` is its reader, and the only
//     way it reaches the wire is `credit_position_after` on a step that has
//     ALREADY happened. So the position appears after each act and not before
//     the amount.
//   · **`selectors.refund_row` carries `payment_id` and no account.** So the
//     queue cannot name whose refund a row is, and it may not print the id —
//     a database id is never the visible value of a field (B14 rule 31).
//   · **"Built from 40.00 + 17.13" is CS-7 and unbuilt.** `refunds.payment_id`
//     is still NOT NULL with no `account_id` beside it, so one refund still
//     names exactly one payment. That is why the raise form collects the
//     payment behind the credit — task 17's row says so in terms — and that
//     field disappears when CS-7 lands.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THE SCREEN REFUSES TO DRAW
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **THIS FILE FIRST CITED `DEF-2392` AND THE ROW LANDED AS `DEF-3119`
// (`DEF-1787`).** The id was allocated correctly, twice, against a register that
// moved underneath it: an allocated id is a BLOB like any other, and the only
// safe moment to fix one is push time. The REGISTER is the authority and the
// code follows it — never the other way round.
//
//   · **A cross-account offset control.** *Offset first* is signed law (OQ-135,
//     closed 2026-08-12) and `cross_account_check` is ALWAYS true in the
//     service — never a client choice, or a screen could switch a ruling off.
//     A credit here against an arrear on a sibling account is REFUSED, and
//     the refusal is rendered. Actually MOVING the credit is CS-8 and unbuilt.
//   · **A `card` method.** BR-PAY-014 is *"check/ACH v1"* and `card` is absent
//     from the column rather than present-and-refused.
//   · **A self-approval block.** BR-PAY-037 permits it in v1 *"as long as both
//     acts are recorded separately"*; the queue names the raiser on every row
//     so the person approving can see whether it is themselves, which is the
//     WriteOffQueuePage precedent and the whole content of that rule.
//   · **An un-void.** A refund row is append-only: the correction is a new
//     refund, and the credit comes back by exactly what left.
import { useState } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  REFUND_METHODS,
  approveRefund,
  clearRefund,
  getMe,
  getPayments,
  // ⚠ `getRefunds` WAS IMPORTED HERE AND CALLED BY NOTHING — a dead import that
  // has failed `npm run lint` since `fb3526105` (`CR-138-BRC07` P4.26), where
  // `RefundsTable` was replaced by `RefundsAndCreditsList` and its reader went
  // with it. It is removed rather than left: a red nobody caused is how a true
  // red acquires the protective colouring of a known one (CLAUDE.md law 7).
  getRefundsAndCredits,
  issueRefund,
  requestRefund,
  voidRefund,
} from "@/api/endpoints";
import { REFUND_KINDS } from "@/api/endpoints";
import type { PaymentRow, RefundMethod, RefundRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
// B14 rule 11 (a consequence before a commit that writes money) and rule 43 (a
// piece of UI is a COMPONENT) — `DEF-PAY-6332`. The kit's box, never a shape
// this screen invents: two answers to one question is how a figure drifts.
import { ConsequenceBox } from "@/components/ConsequenceBox";
import type { RegionalDateFormat } from "@/components/DateCell";
import {
  DatePickerField,
  FormModal,
  SelectField,
  TextField,
} from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { CommitIcon, PencilIcon, PowerIcon, RetireIcon, SwapIcon } from "@/components/icons";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { queryKeys } from "@/api/queryClient";
import { RowAction, RowActions } from "@/components/RowActions";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import type { StatusTone } from "@/components/StatusPill";
import { Panel } from "@/components/Panel";
import { useToast } from "@/components/Toast";
import { PageHeader } from "@/components/PageHeader";
import { Note } from "@/components/TextBits";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableRequestState } from "@/components/tableTypes";
import {
  CELL_FULL,
  GuardedButton,
  ROLE_EXECUTIVE,
  ROLE_SYSTEM_ADMIN,
  isDenied,
  useRegional,
  useAccessCell,
  useTenantRole,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  AccountPickerFields,
  PAYMENTS_PERMISSION,
  PAYMENTS_TABS,
  PAYMENTS_TAB_REFUNDS,
  REFUNDS_ROUTE,
  listRouteAbsent,
  paymentsTabPath,
  useAccountSearch,
} from "./paymentsShared";
import { CounterHeadSlot } from "./CounterDoors";
import { IssueCreditDoor } from "./IssueCreditDoor";
// CR-141-BRC07 — the refund's check number, correctable (OQ-PAY-12614).
import { RefundCorrectCheckModal, refundCorrectBlockedReason } from "./RefundCorrectCheckModal";
import { RefundsAndCreditsList } from "./RefundsAndCreditsList";
import { refundsAndCreditsConfig } from "./RefundsAndCreditsList";

import "./payments.css";

export const refundsQueryKey = (status: string) => ["payments", "refunds", status] as const;

/** 6·1's list key. It carries the PAGE, the SIZE and the KIND, because those
 *  three are the whole of the request — a key that dropped any of them would
 *  serve page one's rows under page two's footer. */
export const refundsAndCreditsQueryKey = (page: number, per: number, kind: string) =>
  ["payments", "refunds-and-credits", page, per, kind] as const;

/**
 * What an act on this page refreshes — EVERY key the page reads from.
 *
 * ⚠ **THE SECOND ENTRY WAS MISSING (`DEF-PAY-6398`).** Since `P4.26` the list
 * is `refundsAndCreditsQueryKey`, and TanStack Query matches a key PREFIX
 * ELEMENT BY ELEMENT — `"refunds"` is a prefix of the STRING
 * `"refunds-and-credits"` and not of the ARRAY — so the old single key matched
 * nothing the page draws and every act closed its form over a stale row. A
 * named list rather than two lines in `refresh()`, so a test can assert that
 * each key the page reads is covered by one of these.
 */
export const REFUNDS_REFRESH_KEYS = [
  ["payments", "refunds"],
  ["payments", "refunds-and-credits"],
] as const;

/**
 * The old address, kept alive.
 *
 * ⚠ **`/finance/refunds` IS NOT DELETED — IT REDIRECTS** (`CR-138-BRC07`
 * `P4.10`). The URL is in saved links, in tickets and in this repo's own
 * journeys; `CR-060`'s ruling kept `/finance/gl` and `/finance/write-offs`
 * routed for exactly that reason when their tabs went. `P4.21` states the bar:
 * *"The old refunds address 404s or redirects **deliberately**. No silent dead
 * link."*
 *
 * `replace` so the old address does not sit in the clerk's Back history and
 * bounce them forward again.
 */
export function RefundsLegacyRedirect() {
  const tenantPath = useTenantPath();
  return <Navigate to={tenantPath(REFUNDS_ROUTE)} replace />;
}

// ⚠ **`REFUND_FILTERS` STOOD HERE AND IS DELETED (`P1.5` · `DEF-PAY-6557`).**
// It listed CR-059 §10's three views as literals, and no screen had rendered it
// since `P4.26` moved 6·1's list onto `GET /refunds-and-credits` on 2026-09-23
// — a dead export with a live test asserting its three values, which is a check
// passing over an absence.
//
// **It was kept deliberately, and the reason it was kept is what changed.** Its
// own test argued *"deleting the constant would take the queue's vocabulary
// with it"*, which was true: `GET /refunds` took `f.status` and nothing served
// the five words. It serves them now — `statuses` and `methods` ride on the
// queue's envelope off `models.REFUND_STATUSES` and `models.REFUND_METHODS` —
// so the vocabulary has a home that is not a literal in a screen, and a sixth
// status added server-side appears with no front-end change.

/** The four acts a row can carry. `raise` is the header action, not a row one. */
export type RefundAct = "approve" | "issue" | "clear" | "void";

// ── Pure pieces (provable without a browser or a network) ──────────────────

/**
 * A2/A12's four tones over `models.REFUND_STATUSES`.
 *
 * `void` is `danger` and `cleared` is `success`, and `issued` is deliberately
 * NEITHER: the money has left the building and the bank has not confirmed it,
 * which is a waiting state and not good news.
 */
export function refundStatusTone(status: string): StatusTone {
  if (status === "cleared") {
    return "success";
  }
  if (status === "void") {
    return "danger";
  }
  if (status === "requested") {
    return "warning";
  }
  return "neutral";
}

/**
 * Why this act cannot run on this row, or `null` — BR-SHL-025's whole content.
 *
 * PURE, so every branch is provable without a browser, and **every branch
 * mirrors a refusal the SERVICE already makes** rather than inventing one:
 *
 *   · the ROLE, from `BR-PAY-014` and `BR-PAY-1071`. A null role (the
 *     permissions read has not answered) offers the control — the server's own
 *     `@require_role` is the boundary either way.
 *   · the STATUS. `approve_refund` accepts only `requested`, `issue_refund`
 *     only `approved`, `clear_refund` only `issued`, and `void_refund` only
 *     `issued` or `cleared` — *"a REQUESTED or APPROVED one has moved no money
 *     and posted nothing, so there is nothing to reverse."*
 *
 * The role check runs FIRST, because a role that may never do this act should
 * read that reason on every row rather than a status sentence that changes as
 * the queue moves.
 */
export function refundActBlockedReason(
  act: RefundAct,
  row: RefundRow,
  role: string | null,
  t: Translator,
): string | null {
  const isAdmin = role === null || role === ROLE_SYSTEM_ADMIN;
  if (act === "clear") {
    if (!(isAdmin || role === ROLE_EXECUTIVE)) {
      return t("payments.refunds.adminOrExecutiveOnly");
    }
  } else if (!isAdmin) {
    return t("payments.refunds.adminOnly");
  }
  if (act === "approve" && row.status !== "requested") {
    return t("payments.refunds.approveUnavailable");
  }
  if (act === "issue" && row.status !== "approved") {
    return t("payments.refunds.issueUnavailable");
  }
  if (act === "clear" && row.status !== "issued") {
    return t("payments.refunds.clearUnavailable");
  }
  if (act === "void" && row.status !== "issued" && row.status !== "cleared") {
    return t("payments.refunds.voidUnavailable");
  }
  return null;
}

/** Which date each act stamps, and the copy that names it. One table, so a new
 *  act cannot be added with the wrong field name and a right-looking label. */
export const REFUND_ACT_COPY: Record<
  RefundAct,
  { title: string; date: string; submit: string; done: string }
> = {
  approve: {
    title: "payments.refunds.approveTitle",
    date: "payments.refunds.approveDate",
    submit: "payments.refunds.action.approve",
    done: "payments.refunds.approvedToast",
  },
  issue: {
    title: "payments.refunds.issueTitle",
    date: "payments.refunds.issueDate",
    submit: "payments.refunds.action.issue",
    done: "payments.refunds.issuedToast",
  },
  clear: {
    title: "payments.refunds.clearTitle",
    date: "payments.refunds.clearDate",
    submit: "payments.refunds.action.clear",
    done: "payments.refunds.clearedToast",
  },
  void: {
    title: "payments.refunds.voidTitle",
    date: "payments.refunds.voidDate",
    submit: "payments.refunds.action.void",
    done: "payments.refunds.voidedToast",
  },
};

const AMOUNT_PATTERN = /^\d+(\.\d{1,6})?$/;
const ALL_ZEROS_PATTERN = /^0*(\.0*)?$/;

/**
 * Client validation is UX only — the SERVER is authoritative and refuses every
 * one of these again with its own rule id.
 *
 * The amount is checked as a STRING pattern and never parsed: a `Number()` here
 * would be the float CLAUDE.md rule 2 exists to keep out of money, in the one
 * place it is most tempting.
 */
export function raiseRefundSchema(t: Translator) {
  return z.object({
    account_id: z.string().min(1, t("payments.refunds.accountRequired")),
    payment_id: z.string().min(1, t("payments.refunds.paymentRequired")),
    amount: z
      .string()
      .regex(AMOUNT_PATTERN, t("payments.form.amountInvalid"))
      .refine((value) => !ALL_ZEROS_PATTERN.test(value), {
        message: t("payments.form.amountPositive"),
      }),
    requested_at: z.string().min(1, t("payments.refunds.dateRequired")),
  });
}

/** The act modal's schema: a date always, a reason when it is a void, and a
 *  cheque number when a CHEQUE is being issued.
 *
 *  ⚠ **`needsCheque` IS THE METHOD, NOT THE ACT** (`DEF-PAY-6331`). US-PAY-011
 *  §5 reads *"required for check"*, so an ACH refund is issued with nothing in
 *  this field and a cheque refund cannot be. The service refuses the same case
 *  in the sentence that rule owns — this is the half that stops the clerk
 *  reaching the server to find out. */
export function refundActSchema(act: RefundAct, t: Translator, needsCheque = false) {
  return z.object({
    acted_at: z.string().min(1, t("payments.refunds.dateRequired")),
    void_reason: z
      .string()
      .refine((value) => act !== "void" || value.trim() !== "", {
        message: t("payments.refunds.voidReasonRequired"),
      }),
    reference: z
      .string()
      .refine((value) => !needsCheque || value.trim() !== "", {
        message: t("payments.refunds.chequeNumberRequired"),
      }),
  });
}

/**
 * One payment, as the raise picker names it.
 *
 * ⚠ **NEVER THE ID.** The option's VALUE is the payment id, because that is
 * what the body carries; what a clerk READS is the `PMT-` number and the date,
 * and a row whose number is absent says so rather than falling back to the id
 * (B14 rule 31). The amount is deliberately not in the label: money renders
 * through `MoneyCell` and nowhere else (BR-SHL-023), and a label is a string.
 */
export function paymentPickerLabel(payment: PaymentRow, t: Translator): string {
  const number = payment.payment_no ?? t("payments.row.noNumber");
  return `${number} · ${payment.posted_at.slice(0, 10)}`;
}

// ── The row's four acts ───────────────────────────────────────

/**
 * ⚠ **`RefundsTable` STOOD HERE UNTIL 2026-09-23 AND IS REPLACED, NOT DELETED
 * IN SPIRIT (`CR-138-BRC07` `P4.26`).** It was a bespoke `PlainTable` with
 * seven columns and no toolbar, no filter, no column chooser and no pagination
 * footer — four B14 rules (12, 14, 16 and this task's Kind column) that the
 * blueprint's own Table-controls row names as *"the change"*. 6·1's list is
 * `RefundsAndCreditsList` on the kit's `DataTable` now, so the product has one
 * table type rather than two (B14 rule 20, and rule 43's *"a piece of UI is a
 * COMPONENT"*).
 *
 * **WHAT SURVIVED IT IS THIS, AND IT IS THE HALF THAT WAS LOAD-BEARING:** the
 * four acts, as ICONS with an accessible name (B14 rule 15), rendered on every
 * refund row, each saying WHY when it cannot run (`BR-SHL-025`). It is a
 * component rather than a cell written inline in the list, because a clerk who
 * may not issue money must learn the rule and not lose the button — and that
 * behaviour is worth being able to mount and assert on its own.
 *
 * ⚠ **IT RENDERS FOUR BARE ICONS AND B14 RULE 15 CAPS A ROW AT TWO PLUS AN
 * OVERFLOW — CARRIED FORWARD UNCHANGED AND FILED AS `DEF-PAY-6282`.** p073
 * draws two glyphs and a `…`. `RowActions` does not enforce the cap (it is a
 * flex row that renders what it is given; the caller composes `RowActionsMore`),
 * and rule 15 is RATIFIED and UNENFORCED like most of B14, because no gate here
 * reads rendered output. **Changing a shipped control set inside a task whose
 * subject is the Kind column is the silent fix `CLAUDE.md` forbids**, so the
 * behaviour is byte-for-byte what shipped on 2026-09-01 and the breach is in the
 * register instead.
 *
 * ⚠ **IT IS DRAWN ON A REFUND ROW AND ON NOTHING ELSE.** A credit note has no
 * lifecycle to act on — it is issued and it freezes — which is why p073 draws
 * ✂ on the RFD rows only. `RefundsAndCreditsList` gates the whole cell on the
 * kind; this component never has to ask.
 *
 * ⚠ **A FIFTH ICON FROM 2026-09-23 — ✎ *Correct check number* (`CR-141-BRC07`,
 * PO ruling `OQ-PAY-12614`, option b).** The pencil, because it is the payment
 * row's glyph for the same act (*"✎ Edit"*, p030 ⑥), and one act wears one
 * glyph. It is NOT a status act — it moves no status and opens its own form —
 * so it is a separate REQUIRED prop rather than a fifth `RefundAct`: an
 * optional handler nothing passed would be dead UI (hard-won law 2). **It
 * takes the row from four bare icons to five, which WIDENS `DEF-PAY-6282`**
 * (rule 15 caps a row at two plus `…`); that defect's fix — two visible and
 * `RowActionsMore` — now has five to arrange, not four, and it stays with the
 * 6·1/6·3 redraw rather than being taken inside a lane whose subject is the
 * ruling.
 */
export function RefundRowActions(props: {
  refund: RefundRow;
  role: string | null;
  t: Translator;
  onAct: (act: RefundAct, row: RefundRow) => void;
  onCorrect: (row: RefundRow) => void;
}) {
  const { refund, role, t } = props;
  return (
    <RowActions>
      <RowAction
        label={t("payments.refunds.action.approve")}
        icon={<CommitIcon />}
        reason={refundActBlockedReason("approve", refund, role, t)}
        onClick={() => props.onAct("approve", refund)}
      />
      <RowAction
        label={t("payments.refunds.action.issue")}
        icon={<PowerIcon />}
        reason={refundActBlockedReason("issue", refund, role, t)}
        onClick={() => props.onAct("issue", refund)}
      />
      <RowAction
        label={t("payments.refunds.action.clear")}
        icon={<SwapIcon />}
        reason={refundActBlockedReason("clear", refund, role, t)}
        onClick={() => props.onAct("clear", refund)}
      />
      <RowAction
        label={t("payments.refunds.action.correct")}
        icon={<PencilIcon />}
        reason={refundCorrectBlockedReason(refund, role, t)}
        onClick={() => props.onCorrect(refund)}
      />
      <RowAction
        label={t("payments.refunds.action.void")}
        icon={<RetireIcon />}
        danger
        reason={refundActBlockedReason("void", refund, role, t)}
        onClick={() => props.onAct("void", refund)}
      />
    </RowActions>
  );
}

// ── Raise (J15 step 1) ────────────────────────────────────────────────────

/** What an account's held-credit row hands the raise form (`DEF-PAY-10707`). */
export interface RaiseRefundPreset {
  accountId: string;
  /** What the clerk reads — the account NUMBER, never the id (B14 rule 31). */
  accountNo: string;
  currency: string;
  paymentId: string;
  /** The part of that payment no bill took, as the server served it. */
  amount: string;
}

export function RaiseRefundModal(props: {
  client: ApiClient;
  dateFormat: RegionalDateFormat;
  /** Only the consequence box reads it, and only to say a figure the clerk's
   *  own way (`DEF-PAY-6332`). Optional, so every existing mount is unchanged. */
  locale?: string;
  /** `DEF-PAY-10707` — opened from an account's held-credit row: the account
   *  is fixed (no picker), the payment and its held amount are filled in. The
   *  clerk can still change the amount; the server is still the authority. */
  preset?: RaiseRefundPreset;
  onClose: () => void;
  onRaised: (creditAfter: string, currency: string, created: boolean) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const preset = props.preset;
  const [accountQuery, setAccountQuery] = useState("");
  const [accountId, setAccountId] = useState(preset?.accountId ?? "");
  const [paymentId, setPaymentId] = useState(preset?.paymentId ?? "");
  const [amount, setAmount] = useState(preset?.amount ?? "");
  const [method, setMethod] = useState<RefundMethod>("check");
  // ⚠ **`reference` — THE CHEQUE NUMBER — WAS COLLECTED HERE AND IS GONE
  // (`DEF-PAY-6331`, 2026-09-23).** It asked a clerk for the number of a cheque
  // that Finance has not approved and nobody has written. 6·3a draws Amount,
  // Reason, How and Note and no cheque number at all; 6·3b draws it and calls
  // it *"the only record of which cheque this was"*. It is collected on
  // `RefundActModal`'s issue branch below, and the raise DOOR refuses one by
  // name rather than dropping it in silence.
  const [requestedAt, setRequestedAt] = useState("");
  const [reason, setReason] = useState("");
  const [memo, setMemo] = useState("");
  // One token per opened form. The door REFUSES a body without it, and a key
  // the server invented would differ on the second submit and dedupe nothing.
  const [submitToken] = useState(() => crypto.randomUUID());

  // IS-3: the account search is SERVER-side, from two characters, so an empty
  // box does not pull the tenant's whole account list into a select.
  //
  // ⚠ **DEF-3506 WAS HERE TOO, AND THAT IS WHY THE FIX IS A SHARED HOOK.** The
  // Product Owner reported it on S33's Record modal — *"On this payment record
  // form unable to search account"* — and this modal carried a byte-for-byte
  // copy of the same two lines: the two-character gate read `.trim()` and the
  // request sent the untyped term, and no state was drawn for searching, for
  // no-match or for failed. Fixing one and leaving the other is how a defect
  // gets filed twice.
  const accountSearch = useAccountSearch(accountQuery, props.client, "refund-account-picker");

  // ⚠ **THE PAYMENT PICKER IS SCOPED BY `f.account_id`, AND THE SCOPE IS THE
  // POINT.** `POST /accounts/{id}/refunds` refuses BY NAME a `payment_id` on
  // another account — without it the account in the URL would be a label, and a
  // clerk on account A's screen could raise a refund funded by account B's
  // overpayment while every downstream figure was B's. Offering only this
  // account's payments is the same rule, one layer earlier, where a clerk can
  // see it.
  const paymentsQuery = useQuery({
    queryKey: ["payments", "refund-payment-picker", accountId],
    queryFn: () => getPayments({ filters: { account_id: accountId }, per: 50 }, props.client),
    enabled: accountId !== "",
    retry: false,
  });
  const payments: PaymentRow[] = paymentsQuery.data?.results ?? [];

  // The chosen account's OWN currency code, for the consequence box and for
  // nothing else (`DEF-PAY-6332`). `null` until an account is chosen — and a
  // null is a real answer here rather than a reason to guess: BR-SHL-023 is
  // one money path and a sentence that named a currency this screen picked
  // would be the second one. The box simply does not draw.
  const chosenCurrency: string | null =
    preset?.currency ??
    accountSearch.matches.find((row) => row.id === accountId)?.currency ??
    null;

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const step = await requestRefund(
        accountId,
        {
          payment_id: paymentId,
          amount,
          method,
          requested_at: requestedAt,
          reason: reason === "" ? null : reason,
          memo: memo === "" ? null : memo,
          idempotency_key: submitToken,
        },
        props.client,
      );
      props.onRaised(step.credit_position_after, step.currency, step.created);
      return { ok: true };
    } catch (error) {
      // Every BR-PAY-014 refusal lands here and is SHOWN — the zero-credit
      // case, the over-refund, and the cross-account offset that names the
      // amount withheld. Server-side enforcement is THE enforcement.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("payments.refunds.raiseTitle")}
      schema={raiseRefundSchema(translate)}
      values={{ account_id: accountId, payment_id: paymentId, amount, requested_at: requestedAt }}
      submitLabel={t("payments.refunds.raiseSubmit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {preset !== undefined ? (
        <Note data-refund-account="">
          {t("payments.refunds.account")}: {preset.accountNo}
        </Note>
      ) : (
      <AccountPickerFields
        searchLabel={t("payments.refunds.accountSearch")}
        accountLabel={t("payments.refunds.account")}
        term={accountQuery}
        onTermChange={setAccountQuery}
        search={accountSearch}
        value={accountId}
        onChange={(next) => {
          setAccountId(next);
          // The payment belongs to the account, so changing the account must
          // not leave a payment from the previous one selected — the server
          // would refuse it by name, and the form would look correct.
          setPaymentId("");
        }}
        t={translate}
      />
      )}
      {/* ⚠ THIS FIELD DISAPPEARS WHEN CS-7 LANDS. The PO ruled 2026-09-01 that a
          refund belongs to the ACCOUNT; `refunds.payment_id` is still NOT NULL
          with no `account_id` beside it, so one refund still names one payment
          and the screen must collect it. */}
      <SelectField
        id="payment_id"
        label={t("payments.refunds.payment")}
        value={paymentId}
        onChange={setPaymentId}
        options={payments.map((payment) => ({
          value: payment.id,
          label: paymentPickerLabel(payment, translate),
        }))}
        placeholder={t("payments.refunds.paymentPlaceholder")}
        required
        help={t("payments.refunds.paymentHelp")}
      />
      <TextField
        id="amount"
        label={t("payments.form.amount")}
        value={amount}
        onChange={setAmount}
        numeric
        required
        help={t("payments.refunds.amountHelp")}
      />
      <SelectField
        id="method"
        label={t("payments.refunds.method")}
        value={method}
        onChange={(next) => setMethod(next as RefundMethod)}
        // BR-PAY-014 is *"check/ACH v1"*. `card` is ABSENT from the column
        // rather than present-and-refused, so it is absent here too.
        options={REFUND_METHODS.map((code) => ({
          value: code,
          label: t(`payments.refunds.method.${code}`),
        }))}
        required
      />
      {/* The clerk's business moment, never a clock (BR-TEN-043, gate G6). Not
          pre-filled: the day a refund was asked for decides nothing here, and a
          pre-filled today is a date nobody read. */}
      <DatePickerField
        id="requested_at"
        label={t("payments.refunds.requestedAt")}
        value={requestedAt}
        onChange={setRequestedAt}
        dateFormat={props.dateFormat}
        required
      />
      <TextField
        id="reason"
        label={t("payments.refunds.reason")}
        value={reason}
        onChange={setReason}
      />
      <TextField
        id="memo"
        label={t("payments.refunds.memo")}
        value={memo}
        onChange={setMemo}
      />
      {/* Signed law, stated where it bites (OQ-135, closed 2026-08-12). It is
          not a choice on this form and never will be: a screen that could send
          `false` would switch a ruling off. */}
      <p className="pay-form-note">{t("payments.refunds.offsetNote")}</p>
      {/* B14 rule 11, and 6·3a's whole remaining work — the blueprint's own
          TODAY row reads *"Built. Missing only the consequence box."*
          (`DEF-PAY-6332`). Annotation ③ draws it as a CHECK box with two
          lines: what leaves, and that approval stands between.

          ⚠ **IT DRAWS ONLY WHEN THERE IS A FIGURE TO STATE.** A consequence
          box over an empty form would say *"leaves the utility"* about
          nothing, which is the description budget rule 32 caps spent on no
          information. Same rule as 2·3a's, and its test asserts the empty
          case.

          ⚠ **THE CURRENCY IS THE ACCOUNT'S, NEVER INVENTED** (BR-TEN-042 is
          one currency per tenant, and BR-SHL-023 is one money path). An
          account not yet chosen has none, so the box waits for both. */}
      {amount !== "" && chosenCurrency !== null && (
        <ConsequenceBox
          tone="check"
          tag={t("payments.consequence.tag")}
          data-consequence="raise"
          title={t("payments.refunds.raise.consequence.title", {
            amount: formatMoney(amount, chosenCurrency, props.locale),
          })}
          body={t("payments.refunds.raise.consequence.body")}
        />
      )}
    </FormModal>
  );
}

// ── Approve · Issue · Clear · Void (J15 steps 3–4, and TC-3/TC-4) ─────────

export function RefundActModal(props: {
  client: ApiClient;
  act: RefundAct;
  refund: RefundRow;
  dateFormat: RegionalDateFormat;
  locale?: string;
  onClose: () => void;
  onDone: (creditAfter: string | null, currency: string) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const { act, refund } = props;
  const [actedAt, setActedAt] = useState("");
  const [voidReason, setVoidReason] = useState("");
  const [memo, setMemo] = useState("");
  // ⚠ **THE CHEQUE NUMBER, COLLECTED AT THE ACT THAT WRITES THE CHEQUE
  // (`DEF-PAY-6331`, 2026-09-23).** 6·3b draws it as annotation ② and says what
  // it is for in four words: *"the only record of which cheque this was"*. It
  // was collected on the RAISE form until today, which asked a clerk for the
  // number of a cheque nobody had written — and because `refunds.reference` was
  // frozen from row creation, the guess they typed was the only number the
  // product would ever hold.
  //
  // It is pre-filled from the row when the row already has one, so the one
  // lawful case — a refund recorded with its number already known — opens
  // showing what it will keep rather than an empty box that looks like a
  // demand. The server writes it ONCE (`payments/0041`).
  const [reference, setReference] = useState(refund.reference ?? "");
  const copy = REFUND_ACT_COPY[act];
  // Only a CHEQUE has a cheque number. `BR-PAY-014` is *"check/ACH v1"*, and a
  // required field shown over a bank transfer would be a wall with nothing
  // behind it — the service refuses one and asks for the other.
  const needsCheque = act === "issue" && refund.method === "check";

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      if (act === "approve") {
        await approveRefund(
          refund.id,
          { approved_at: actedAt, memo: memo === "" ? null : memo },
          props.client,
        );
        // Approval moves no money and answers with the ROW, which carries no
        // credit position — so none is claimed. `null` is *"not stated"*, and
        // the panel says so rather than printing a figure from a earlier step.
        props.onDone(null, refund.currency);
        return { ok: true };
      }
      if (act === "issue") {
        const step = await issueRefund(
          refund.id,
          // `null` rather than `""` — an empty string is a value the row would
          // then be asked to hold, and "no cheque number" is an absence.
          { issued_at: actedAt, reference: reference.trim() === "" ? null : reference.trim() },
          props.client,
        );
        props.onDone(step.credit_position_after, step.currency);
        return { ok: true };
      }
      if (act === "clear") {
        const step = await clearRefund(refund.id, { cleared_at: actedAt }, props.client);
        props.onDone(step.credit_position_after, step.currency);
        return { ok: true };
      }
      await voidRefund(
        refund.id,
        { voided_at: actedAt, void_reason: voidReason },
        props.client,
      );
      props.onDone(null, refund.currency);
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t(copy.title)}
      schema={refundActSchema(act, translate, needsCheque)}
      values={{ acted_at: actedAt, void_reason: voidReason, reference }}
      submitLabel={t(copy.submit)}
      /* ⚠ **B14 rule 6 — DANGER TIER ON THE ONE ACT THAT MOVES MONEY OUT
         (`DEF-PAY-6332`).** 6·3b's TODAY row names it as the defect: *"Built.
         The commit renders in the standard tier, like Save — same defect as
         the reversal on 2·3e"*, and annotation ③ marks *"Money out · danger
         tier — it is irreversible in the way that matters"* as CHANGED.
         Irreversible *in the way that matters* is the precise claim: a refund
         CAN be voided, but only by a reversing posting after the cheque has
         gone out — the money has left the building either way.
         **APPROVE, CLEAR AND VOID KEEP THE STANDARD TIER.** Approving moves no
         money, clearing posts nothing, and a void RESTORES a credit. A tier
         spent on every act is a tier that warns about nothing. */
      submitVariant={act === "issue" ? "danger" : undefined}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <p className="pay-resolve-facts">
        <MoneyCell amount={refund.amount} currency={refund.currency} locale={props.locale} />
      </p>
      {/* ⚠ **`payments.refunds.issueWarning` — *"The money leaves now."* —
          STOOD HERE AND IS RETIRED (`DEF-PAY-6332`).** The consequence box at
          the foot of this form says the same thing four lines lower AND names
          the figure, so keeping both spends the description budget B14 rule 32
          caps on a sentence a clerk then learns to read past. Same call as
          `ReversePaymentModal`'s, and for the same reason its own comment
          gives: the second copy is the one that stops being read.

          ⚠ **ABOVE THE DATE, BELOW THE APPROVAL — 6·3b's OWN ORDER.** The
          drawing runs: who approved it (①), the cheque number (②), Issued on,
          then the consequence box (③) and the footer. That order is CONTENT
          and it is the drawing's call (B14 rule 38); what the field is BUILT
          from is ours, so it is the kit's `TextField` like every other.

          ⚠ **ONLY OVER A CHEQUE.** `BR-PAY-014` is *"check/ACH v1"* and a
          bank transfer has no cheque number, so the field is absent rather
          than present-and-optional — an optional box labelled *Cheque number*
          over an ACH refund is a question with no right answer. */}
      {needsCheque && (
        <TextField
          id="reference"
          label={t("payments.refunds.col.reference")}
          value={reference}
          onChange={setReference}
          required
          help={t("payments.refunds.chequeNumberHelp")}
        />
      )}
      {/* Clearing posts NOTHING — the money left at issue, and posting again
          would take it out twice. Said on the form, because a clerk pressing a
          button on a money screen is entitled to know it moves none. */}
      {act === "clear" && <p className="pay-form-note">{t("payments.refunds.clearNote")}</p>}
      <DatePickerField
        id="acted_at"
        label={t(copy.date)}
        value={actedAt}
        onChange={setActedAt}
        dateFormat={props.dateFormat}
        required
      />
      {act === "void" && (
        // REQUIRED and never defaulted: *"a cheque that left the building and
        // came back is a fact somebody has to be able to reconstruct in a
        // year"* (hard rule 7). The service refuses a blank.
        <TextField
          id="void_reason"
          label={t("payments.refunds.voidReason")}
          value={voidReason}
          onChange={setVoidReason}
          required
        />
      )}
      {act === "approve" && (
        <TextField
          id="memo"
          label={t("payments.refunds.memo")}
          value={memo}
          onChange={setMemo}
        />
      )}
      {/* B14 rule 11, and the other half of 6·3b's work (`DEF-PAY-6332`).
          Annotation ③, drawn as a CHECK box: what leaves, and what the clerk
          does next when the bank shows it.

          ⚠ **UNCONDITIONAL, UNLIKE THE RAISE BOX ABOVE.** The figure is the
          REFUND'S OWN, served with the row, so there is no state in which this
          form is open and the amount is unknown. A box that waited for
          something would be waiting for nothing.

          ⚠ **THE DRAWN SECOND LINE IS EIGHT WORDS AND OURS IS TWO SENTENCES,
          ON PURPOSE.** The drawing reads *"Mark it cleared when the bank shows
          it."*; B14 rule 33 caps a consequence at six words per sentence and
          prescribes the remedy itself — *two sentences of six beat one
          sentence of twelve* — and forbids cutting below clarity, so the
          meaning is kept whole and split rather than trimmed. Rule 38's line:
          what the box SAYS is the drawing's, how the copy is BUILT is ours. */}
      {act === "issue" && (
        <ConsequenceBox
          tone="check"
          tag={t("payments.consequence.tag")}
          data-consequence="issue"
          title={t("payments.refunds.issue.consequence.title", {
            amount: formatMoney(refund.amount, refund.currency, props.locale),
          })}
          body={t("payments.refunds.issue.consequence.body")}
        />
      )}
    </FormModal>
  );
}

// ── The credit position, as the LAST step reported it ─────────────────────

/**
 * CS-6's *watch for*, rendered.
 *
 * It appears only AFTER an act and it is the figure that act's own transaction
 * computed — never a cached one, and never one this screen worked out. It may
 * be BELOW zero and is not floored (`OQ-132`, 2026-08-11: *"Yes, it's a real
 * debt"*).
 */
export function CreditPositionPanel(props: {
  amount: string;
  currency: string;
  locale?: string;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="pay-result" role="status">
      <div className="pay-result-head">
        <h3>{t("payments.refunds.creditAfter")}</h3>
        <Button variant="ghost" onClick={props.onDismiss}>
          {t("payments.result.dismiss")}
        </Button>
      </div>
      <p className="pay-today-amount">
        <MoneyCell amount={props.amount} currency={props.currency} locale={props.locale} />
      </p>
    </div>
  );
}

// ── The screen ────────────────────────────────────────────────────────────

export interface RefundsPageProps extends RegionalProps {
  client?: ApiClient; // test seam
  locale?: string;
}

export function RefundsPage(props: RefundsPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const toast = useToast();
  // ⚠ `timeZone` left with the table's date columns on 2026-09-23 (`P4.26`).
  // The act modals take `dateFormat` alone; `RefundsAndCreditsList` formats no
  // date at all, because the read's `occurred_at` is not a drawn column.
  const { dateFormat } = useRegional(props);
  // A4's "Payments (record)" row and NOT the finance/reconcile one: a Billing
  // Clerk RAISES refunds (CS-6, *"raise — Admin or Clerk"*), and gating the
  // screen on the reconcile cell would shut out the very person the raise route
  // is for. Each ACT still carries its own role reason below.
  const cell = useAccessCell(PAYMENTS_PERMISSION, client);
  const role = useTenantRole(client);
  // ⚠ **THE FINANCE PERIOD LEFT WITH THE FRAME ON 2026-09-23 (`P4.10`).** It
  // read `const { period } = useFinancePeriod(client)` and was passed to
  // `FinanceHeader` *"for continuity with its sibling tabs"* — the sibling
  // tabs are no longer this screen's. A refunds list is NOT period-scoped
  // either way: a request waits until somebody works it, so nothing here was
  // ever gated on one.

  const [raising, setRaising] = useState(false);
  const [crediting, setCrediting] = useState(false);
  const [acting, setActing] = useState<{ act: RefundAct; row: RefundRow } | null>(null);
  // CR-141-BRC07 — the refund whose check number is being corrected, or none.
  const [correcting, setCorrecting] = useState<RefundRow | null>(null);
  const [credit, setCredit] = useState<{ amount: string; currency: string } | null>(null);

  // ⚠ **THE LIST IS `GET /refunds-and-credits`, NOT `GET /refunds` — `P4.26`.**
  // The two reads answer different questions and only one of them is pageable;
  // `RefundsAndCreditsList`'s own header sets out why the three status tabs
  // could not survive the move and where the approval queue still lives.
  // **`NFR-3`:** the page is taken in SQL on both sides of the module boundary,
  // so this screen never asks for a row it will not draw.
  const [searchParams, setSearchParams] = useSearchParams();
  // ⚠ **THIS SECOND CONFIG IS FOR THE URL ONLY, AND IT IS SAFE FOR A REASON
  // WORTH WRITING DOWN RATHER THAN A COINCIDENCE.** `parseTableParams` and
  // `serializeTableParams` walk `filters[].name` through `filterParamNames` and
  // never read `options`, so a config built before the first response — with
  // the STATIC `REFUND_KINDS` and no `lifecycles` — round-trips `f.kind`
  // identically to the one the list builds from the envelope. The LIST's config
  // is the one that renders; this one only names the params.
  //
  // Sharing one object would mean the page could not serialize a URL until the
  // response landed, which is the wrong way round: the URL is what ASKS for the
  // response. If a filter is ever added, add it in `refundsAndCreditsConfig` —
  // both callers get it, because both call that function.
  const listConfig = refundsAndCreditsConfig(translate, REFUND_KINDS, refundStatusTone, undefined);
  const listState = parseTableParams(searchParams, listConfig);
  function setListState(next: TableRequestState): void {
    setSearchParams(serializeTableParams(next, listConfig), { replace: true });
  }

  const queueQuery = useQuery({
    queryKey: refundsAndCreditsQueryKey(listState.page, listState.per, listState.filters.kind ?? ""),
    queryFn: () =>
      getRefundsAndCredits(
        { page: listState.page, per: listState.per, kind: listState.filters.kind },
        client,
      ),
    retry: false,
  });

  // WHO IS LOOKING. Read from the SESSION and never taken as a prop: the whole
  // point of naming the raiser is that the person about to approve can see
  // whether it is themselves (BR-PAY-037), and a prop nothing passed would
  // silently disable the warning — the unwired-prop shape G13 exists to catch.
  const meQuery = useQuery({ queryKey: queryKeys.me, queryFn: () => getMe(client), retry: false });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("payments.refunds.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }
  if (queueQuery.isError && isPermissionDenied(queueQuery.error)) {
    return (
      <PermissionDenied
        helper={t("payments.refunds.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }

  const rows = queueQuery.data?.rows;
  const failed = queueQuery.isError && rows === undefined;
  const routeAbsent = failed && listRouteAbsent(queueQuery.error);
  // ⚠ **THE KIND LIST AND THE LIFECYCLES COME OFF THE ENVELOPE**, so this
  // screen holds no second copy of a vocabulary the server owns. `REFUND_KINDS`
  // is the fallback used only before the first response lands — a filter with
  // no options at all reads as a broken control.
  const kinds = queueQuery.data?.kinds ?? REFUND_KINDS;
  const lifecycles = queueQuery.data?.lifecycles;
  const currentUserId = meQuery.data?.id ?? null;
  // BR-SHL-025: "Full" writes. An Executive holds View on this surface and may
  // still MARK CLEARED, which is a row action with its own gate — so the header
  // action alone carries the raise reason.
  const raiseBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("payments.refunds.raiseBlocked");

  function refresh(): void {
    // `DEF-PAY-6398` — see `REFUNDS_REFRESH_KEYS`: the list's own key was
    // missing, so every act left the row it acted on looking unchanged.
    for (const queryKey of REFUNDS_REFRESH_KEYS) {
      void queryClient.invalidateQueries({ queryKey });
    }
  }

  return (
    <div className="fin-page">
      {/* ⚠ **THIS WAS `FinanceHeader` UNTIL 2026-09-23 (`CR-138-BRC07` `P4.10`).**
          It highlighted `FINANCE_TAB_REVENUE`, because between 2026-09-03 and
          today this screen lived in the Finance area and the tab that OWNED it
          was Revenue & AR. The blueprint moves it: `REFUNDS_ROUTE` is
          `/payments/refunds` now and the strip is the payments seven, with
          **Refunds** selected. The supersedes chain is on that constant.

          It is `PageHeader` with `PAYMENTS_TABS`, which is exactly what
          `CollectionsPage` does one screen over — a payments screen on its own
          static route drawing the strip itself. Not a second strip (B14 rule
          43), and not a second header (rule 2). */}
      <PageHeader
        kicker={t("payments.refunds.kicker")}
        title={t("payments.refunds.title")}
        tabs={PAYMENTS_TABS.map((tab) => ({ id: tab.id, label: t(tab.labelKey) }))}
        activeTabId={PAYMENTS_TAB_REFUNDS}
        tabsLabel={t("payments.tabsLabel")}
        onTabSelect={(tab) => navigate(tenantPath(paymentsTabPath(tab.id)))}
        // ⚠ **TWO SLOTS, NOT ONE `actions` ARRAY.** `PageHeader` splits the
        // secondaries from the primary precisely so *"exactly one primary"*
        // stays checkable (TC-6), and the split is also the drawn order:
        // `Issue credit` sits to the LEFT of `Raise refund` on p073.
        secondaryActions={
          <>
            {/* ⚠ **`P2.7`/`P2.16`: `Start counter →` IS ON EVERY PAYMENTS SCREEN,
                AND THIS SCREEN BECAME ONE TODAY.** `counterDoors.dom.test.tsx`
                excluded Refunds with its reason stated and a case asserting the
                exclusion was still true — *"If it is ever re-homed into this
                strip — the blueprint's 6·1–6·3c work — this goes RED and this
                file has to say what it now means by every."* It went red on
                this commit, which is that case working exactly as written.

                A clerk working refunds is standing on a payments screen, and
                without this they would have to navigate away to find the till
                door — which is what *every payments screen* exists to prevent
                (`DEF-PAY-6237`, the same miss one screen over). It is
                `CounterHeadSlot`, the component `P2.7` built, not a second copy
                of it (B14 rule 43). */}
            <CounterHeadSlot client={client} />
            {/* ⚠ **`Issue credit` BESIDE `Raise refund` IS THE WHOLE OF `P4.10`'s
                second half**, and the drawing states the reason in its
                Primary-action row: *"so the cheaper option is visible at the
                moment the choice is made."* A credit costs the utility a
                journal entry; a refund costs it a cheque, the postage and a
                bank reconciliation, and until today the cheaper of the two was
                invisible from payments — *"a credit issued today appears
                nowhere in payments at all"* (p073).

                **It is a DOOR and not a second credit path** (PO 2026-09-22,
                *"we can not have two path for 1 capabilities"*): it opens a
                picker and navigates to billing's own address. See
                `IssueCreditDoor`.

                B14 rule 4 — SECONDARY tier. There is exactly one primary on a
                screen and `Raise refund` is it, which is also the order the
                drawing puts them in. */}
            <GuardedButton
              label={t("payments.refunds.credit.open")}
              reason={raiseBlockedReason}
              variant="secondary"
              onClick={() => setCrediting(true)}
            />
          </>
        }
        primaryAction={
          <GuardedButton
            label={t("payments.refunds.raise")}
            reason={raiseBlockedReason}
            variant="primary"
            onClick={() => setRaising(true)}
          />
        }
      />

      {routeAbsent ? (
        <ArrivesWith
          title={t("payments.refunds.awaitsTitle")}
          message={t("payments.refunds.awaits")}
          tracks="DEF-2032"
        />
      ) : failed ? (
        <Panel role="alert">
          <h3>{t("payments.refunds.errorTitle")}</h3>
          <p className="pay-absent">{apiErrorText(queueQuery.error, translate)}</p>
        </Panel>
      ) : rows === undefined ? (
        <LoadingSkeleton variant="table" />
      ) : (
        <>
          {/* ⚠ **THE THREE-VIEW SEGMENTED CONTROL WAS HERE AND IS GONE
              (`P4.26`).** It read *awaiting approval · issued · all* over
              `GET /refunds`, and the drawing replaces it in terms: *"Three tabs
              today — approval, issued, all. **The toolbar, the Kind filter and
              paging are the change.**"* `RefundsAndCreditsList`'s header sets
              out why a status filter could not come with it — the union read
              accepts `f.kind` alone, so a status control here could only filter
              the page already fetched, which tells the truth on page one and
              lies on page two. **The approval queue is not lost**: it is
              `RefundsQueuePanel` in Finance → Revenue & AR, where the PO's
              ruling of 2026-09-03 put it. */}
          {/* ⚠ **`DEF-3119`'s PANEL WAS HERE AND HAS MOVED INTO THE LIST
              (`P4.26`).** It stated the same absence — no account column,
              because `refund_row` carries a uuid and B14 rule 31 forbids
              printing one — and `RefundsAndCreditsList` now says it in a
              disclosure CLOSED by default, beside the columns it is about.
              **Saying it in both places would break rule 32's own budget**
              (*one sentence per section*), which the PO ratified after
              *"too much content - desctiption is too much for clark to read"*
              four times in twenty minutes. The defect is unchanged and still
              open; only where the sentence lives has moved. */}
          {credit !== null && (
            <CreditPositionPanel
              amount={credit.amount}
              currency={credit.currency}
              locale={props.locale}
              onDismiss={() => setCredit(null)}
            />
          )}
          <RefundsAndCreditsList
            rows={rows}
            totalRows={queueQuery.data?.count ?? null}
            state={listState}
            onStateChange={setListState}
            loading={queueQuery.isPending}
            kinds={kinds}
            lifecycles={lifecycles}
            statusTone={refundStatusTone}
            currentUserId={currentUserId}
            emptyCtaLabel={t("payments.refunds.raise")}
            emptyCtaReason={raiseBlockedReason}
            onEmptyCta={() => setRaising(true)}
            // ⚠ **THE FOUR ACTS SURVIVED THE MOVE, AND ONLY ON A REFUND ROW.**
            // `RefundsAndCreditsList` draws this cell for `kind === "refund"`
            // and for nothing else — *"✂ appears only on a refund row; a credit
            // has nothing to void"* (p073, annotation ⑥). The gating is
            // `refundActBlockedReason`, unchanged and still the SERVICE's own
            // refusal mirrored (BR-SHL-025), reading the refund through the
            // union row's `source`, which IS `selectors.refund_row`.
            rowActions={(row) => (
              <RefundRowActions
                refund={row.source as unknown as RefundRow}
                role={role}
                t={translate}
                onAct={(act, refund) => setActing({ act, row: refund })}
                onCorrect={(refund) => setCorrecting(refund)}
              />
            )}
          />
        </>
      )}

      {crediting && (
        <IssueCreditDoor
          client={client}
          onGo={(path) => {
            setCrediting(false);
            navigate(tenantPath(path));
          }}
          onClose={() => setCrediting(false)}
        />
      )}
      {raising && (
        <RaiseRefundModal
          client={client}
          dateFormat={dateFormat}
          locale={props.locale}
          onClose={() => setRaising(false)}
          onRaised={(creditAfter, currency, created) => {
            setRaising(false);
            setCredit({ amount: creditAfter, currency });
            // A REPLAY is not a second refund: the door answers 200 with the
            // FIRST one, which is the right answer to a double click and the
            // wrong thing to congratulate somebody for.
            toast(created ? t("payments.refunds.raisedToast") : t("payments.refunds.replayToast"));
            refresh();
          }}
        />
      )}
      {correcting !== null && (
        <RefundCorrectCheckModal
          client={client}
          refund={correcting}
          onClose={() => setCorrecting(null)}
          onCorrected={(result) => {
            setCorrecting(null);
            // The numbers come off the SERVER's answer — what was stored and
            // what it replaced — never off what this screen sent. No sentence
            // about how long the old one is kept: B14 rule 33 (see the modal).
            toast(
              t("payments.refunds.correct.toast", {
                was: result.previous.reference ?? "",
                now: result.corrected.reference,
              }),
            );
            refresh();
          }}
        />
      )}
      {acting !== null && (
        <RefundActModal
          client={client}
          act={acting.act}
          refund={acting.row}
          dateFormat={dateFormat}
          locale={props.locale}
          onClose={() => setActing(null)}
          onDone={(creditAfter, currency) => {
            const act = acting.act;
            setActing(null);
            setCredit(creditAfter === null ? null : { amount: creditAfter, currency });
            toast(t(REFUND_ACT_COPY[act].done));
            refresh();
          }}
        />
      )}
    </div>
  );
}

export default RefundsPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-059 §8 CS-6 · §8 CS-7 · §10 P3 · §11 tasks 17 and 18 ·
//         apps/payments/refunds_api.py · apps/payments/refunds.py ·
//         apps/payments/selectors.refund_row · BR-PAY-014 · BR-PAY-037 ·
//         BR-PAY-1071 · OQ-132 (CLOSED) · OQ-135 (CLOSED)
// generated: 2026-09-01 by the CR-059 W3 screens lane (task 18)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions:
//   E1 **The refundable position is NOT shown before the amount**, which CR-059
//      §10 P3 asks for. No route publishes an account's credit position — it is
//      computed in `apps/payments/credit.py` and reaches the wire ONLY as
//      `credit_position_after` on a step that has already happened. The screen
//      shows that figure after each act and states the gap rather than
//      inventing a number. `DEF-3119`. REPORTED.
//   E2 **The queue cannot name the account**, for the same row: `refund_row`
//      serves `payment_id` and no account, and B14 rule 31 forbids printing the
//      id. The cheque number stands in. Same defect row.
//   E3 **"Built from 40.00 (June) + 17.13 (July)" is NOT drawn.** That is CS-7
//      (task 60, contracts): `refunds.payment_id` is still NOT NULL and one
//      refund still names one payment, so the raise form collects the payment
//      behind the credit — which task 17's row asks for in terms.
//   E4 **The raiser is named as *a person*, not by name.** `refund_row` serves
//      `requested_by` as an id and no display name, and printing the id is a
//      rule-31 breach. The one case BR-PAY-037 actually leans on — that it was
//      YOU — is compared against the session and marked.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
