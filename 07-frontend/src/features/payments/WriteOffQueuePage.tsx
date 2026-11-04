// ── Trace ──────────────────────────────────────────────
// ⚠ `DEF-GOV-10106`: THE PAGE COMPONENT (`WriteOffQueuePage`) IS DELETED.
//           Its route went in `4c96baa75` (one queue, not two — CR-135 P1.10);
//           the queue lives as `WriteOffQueuePanel` in Revenue & AR. This file
//           keeps the table, its config and the decision helpers that panel
//           and its tests import.
// Story:    US-PAY-012 (write-offs: INITIATED in Payments, APPROVED + reported
//           in Finance — the approval half that had an endpoint and no screen)
//           Screens: S36 area (Finance) · S34/S35 (where the request is made)
// Rules:    BR-PAY-020 (write-offs are initiated in Payments and approved in
//           Finance by Owner/Admin, to the bad-debt GL; payments owns the
//           record, ledger posts, finance reports) · BR-PAY-037 (the SAME user
//           holding the approver role MAY initiate AND approve in v1 — both
//           acts recorded distinctly; enforced separation of duties is v2;
//           CONFIRMED-AS-RE-AFFIRMED 2026-09-23, `OQ-226` closed) ·
//           BR-PAY-002 (a write-off row is append-only) · BR-SHL-020 ·
//           BR-SHL-023 · BR-SHL-025 · BR-SHL-044
// ───────────────────────────────────────────────────────
// ⛔ **THIS PAGE IS NO LONGER ROUTED (`CR-135` P1.10, 2026-09-22), AND IT IS
// KEPT ON PURPOSE. READ THIS BEFORE DELETING IT.**
//
// The Payments blueprint's §05 audit says *"delete the route and the
// component"*, and the ROUTE went — `/finance/write-offs` was a second
// write-off queue beside `WriteOffQueuePanel` in Revenue & AR, reachable only
// by typing the address. **The COMPONENT did not go, because the two are not
// the same queue, which the audit did not measure and this lane did:**
//
//   · `WriteOffQueuePanel` (`features/ledger/RevenueArPage.tsx`) offers
//     **Approve** and nothing else.
//   · `WriteOffQueueTable` below offers **Approve · Reject · Reverse** —
//     `CR-059` CS-25 task 63, `BR-PAY-1120`'s four-state set, landed
//     2026-09-01 and served by `POST /write-offs/{id}/reject` and
//     `/reverse`.
//
// So deleting this file would take the ONLY Reject and Reverse doors in the
// product with it, silently, on a money path — and an absence is invisible to
// every check this repository has. The panel must GAIN both acts first; until
// it does, this component is the record of what the queue owes. That is filed
// as `DEF-PAY-6199`, not left in a comment.
//
// The write-off approval queue — where the money actually moves.
//
// ══════════════════════════════════════════════════════════════════════════
// THE TWO-PERSON SPLIT WAS NOMINAL, AND THIS IS THE HALF THAT WAS MISSING
// ══════════════════════════════════════════════════════════════════════════
// `writeoffs.py` records it in its own words: *"the only write-off id a browser
// could hold was the one the requester's own screen had just minted, so the
// Approve control had nowhere to live except beside the request."* `GET
// /write-offs` was added to fix that — and then nothing called it. A queue
// endpoint with no queue screen is the same defect one layer up.
//
// So: a clerk REQUESTS a write-off from the outstandings screen (S34/S35, which
// already exists and moves no money), and Finance works it here.
//
// ══════════════════════════════════════════════════════════════════════════
// THE APPROVER AND THE REQUESTER — WHAT THIS SCREEN MAY AND MAY NOT DO
// ══════════════════════════════════════════════════════════════════════════
// **BR-PAY-037 is CONFIRMED and it permits self-approval in v1**, verbatim:
// *"the SAME user holding the approver role MAY initiate AND approve in v1 —
// both acts recorded distinctly; enforced separation-of-duties = v2"*. A screen
// that BLOCKED it would be this lane overturning a signed rule, which the prime
// directive forbids outright.
//
// ⚠ **RE-AFFIRMED BY THE PRODUCT OWNER ON 2026-09-23, AND THAT MAKES THE
// WARNING BELOW THE RATIFIED SHAPE RATHER THAN A STOPGAP (`OQ-226` CLOSED,
// option (a)).** PO, verbatim: *"allow it - we are dealing with smaller
// utilites they dont have too many people"*. **The reasoning is the ICP
// argument and it is recorded here because it decides the next case of this
// shape too:** a utility run by 10–20 staff may not HAVE a second approver, so
// a control that demands one does not protect the work — it stops it, and a
// write-off nobody can approve is a receivable that never clears. Enforced
// separation of duties stays v2 and **no person-level check is ever added for
// v1**; the ROLE control in the service is the whole of it.
//
// ⚠ **WHAT THE RULING SUPERSEDES IS THE DRAWING, AND A PDF CANNOT CARRY ITS
// OWN CORRECTION — WHICH IS WHY IT IS WRITTEN HERE.** Payments blueprint
// **p086** (`05-prototype/06 Payments Page Blueprint.pdf`), screen 7·3b, draws
// *"A second person decides."* with *"You cannot approve one you asked for."*
// under it, and a third row whose action cell reads *"Yours — someone else
// decides"* in place of Approve and Refuse. **All three are superseded. They
// are not built and they may not be built.**
//
// ⚠ **AND NONE OF THIS REASONING REACHES A CLERK (B14 rule 33 — RATIONALE IS
// ZERO WORDS ON SCREEN).** The queue says who asked and warns the viewer when
// that was them. It does not say that a second approver is not required
// because the utility is small; that sentence belongs in this file and in
// `OQ-226`, never on the screen.
//
// What the screen does instead is make it impossible to do by ACCIDENT: every
// row names its requester, and a row the current user requested carries a
// standing warning beside the Approve control. A person who means it still can,
// and now knows that they are — which is the whole content of *"both acts
// recorded distinctly"* rendered where a human can see it.
//
// **The build brief for this lane asked for hard separation of duties.** That
// contradicts BR-PAY-037 as signed, so it was NOT taken: it was raised as
// **OQ-226** in `12-governance/01-open-questions.md` for the Product Owner, and
// this file implements the rule as it stands. Changing a signed rule needs a
// ruling, not a lane's opinion — **and on 2026-09-23 the ruling arrived and
// went the other way: `OQ-226` is CLOSED, the brief's ask is declined for v1,
// and `BR-PAY-037` is `CONFIRMED-AS-RE-AFFIRMED`.**
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THE SCREEN REFUSES TO DRAW
// ══════════════════════════════════════════════════════════════════════════
//   · **A GL-account picker.** The posting picks the designated bad-debt
//     account through the ledger seam (BR-PAY-020); a picker here would let a
//     clerk post bad debt to an account finance did not designate. The
//     prototype's write-off modal offers one — it is not ported (P-4/P-5).
//   · **An "un-approve" control.** A write-off row is append-only (BR-PAY-002)
//     and an approved one has already reduced receivables. The correction is a
//     new entry, and it is the ledger's.
//   · **A bulk approve.** Each approval posts to the books and closes any live
//     payment plan on the account (PO 2026-08-12, OQ-171). One decision, one
//     act, one audit row.
import { useState } from "react";

import type { WriteOffApprovalRow } from "@/api/bankRecEndpoints";
import { CommitIcon, RetireIcon, RollBackIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { MoneyCell } from "@/components/MoneyCell";
import { StatusPill } from "@/components/StatusPill";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { clientPage } from "@/components/clientTable";
import type { ClientTableSpec } from "@/components/clientTable";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { InlineLinkTo } from "@/components/Surfaces";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { WRITE_OFF_REASON_CODES, writeOffReasonLabel } from "./paymentsShared";
import { debtorDetailPath } from "./debtorsTable";

import "./payments.css";

export const writeOffQueueQueryKey = (status: string) =>
  ["payments", "write-offs", status] as const;

/** `collections_models.WRITE_OFF_STATUSES` — the FOUR this product has.
 *
 *  ⚠ **THIS COMMENT SAID "the two this product has" UNTIL 2026-09-02, AND IT
 *  WAS RIGHT WHEN IT WAS WRITTEN.** CR-059 CS-25 (task 62) widened the status
 *  set to four and widened the check constraint with it (`payments/0011`), so
 *  the server has been serving `rejected` and `reversed` rows into a screen
 *  that offered no way to see them — and the queue's own filter would answer
 *  the server with a status it refuses. The sentence changes with the fact
 *  (hard-won law 1). */
export const WRITE_OFF_FILTERS = [
  { value: "requested", labelKey: "payments.writeOffQueue.filter.requested" },
  { value: "approved", labelKey: "payments.writeOffQueue.filter.approved" },
  { value: "rejected", labelKey: "payments.writeOffQueue.filter.rejected" },
  { value: "reversed", labelKey: "payments.writeOffQueue.filter.reversed" },
  { value: "", labelKey: "payments.writeOffQueue.filter.all" },
] as const;

/** Which decision a clerk is being asked to confirm. Held as a PAIR with the
 *  row rather than as two booleans: a modal that could be open for a rejection
 *  and a reversal at once is a state this screen must not be able to express,
 *  because the two acts have opposite consequences. */
export type WriteOffDecisionKind = "approve" | "reject" | "reverse";

/**
 * Why a decision cannot be taken on this row, or null when it can.
 *
 * DERIVED FROM THE ROW's own status and never from a role: BR-PAY-1120 puts
 * `@require_role(SYSTEM_ADMIN)` on the SERVICE, so the server is the
 * authorisation and this screen never second-guesses it (BR-SHL-025). What it
 * DOES know is which act the row is in a state for — CS-25's whole point is
 * that the two are different shapes:
 *
 *   `requested`  nothing posted, so it can be approved or REJECTED
 *   `approved`   receivables already reduced, so it can only be REVERSED
 *   anything else  a decision already recorded; the correction is another row
 */
export function decisionBlockedReason(
  row: WriteOffApprovalRow,
  kind: WriteOffDecisionKind,
  t: Translator,
): string | undefined {
  const wanted = kind === "reverse" ? "approved" : "requested";
  if (row.status === wanted) {
    return undefined;
  }
  return t(`payments.writeOffQueue.blocked.${kind}`, {
    defaultValue: t("payments.writeOffQueue.blocked.wrongState"),
  });
}

/** Today, as an ISO date, from the BROWSER — the caller states the business day
 *  and the server reads no clock (BR-TEN-043, gate G6). */
export function todayIso(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10);
}

// ── The queue ─────────────────────────────────────────────────────────────

/**
 * **THE APPROVAL QUEUE — 7·3b, AND IT IS THE KIT'S TABLE SINCE 2026-09-23.**
 *
 * `CR-138-BRC07` `P4.9`: *"the write-off panel gains a toolbar and paging."*
 * The blueprint's own Today row for 7·3b is *"The panel is built and
 * reachable. What it lacks is a toolbar and paging — rule 16, the weakest of
 * the eighteen, because an approval queue is short by nature"*, and the
 * drawing on p086 puts a search box, an `All` chip, `+ Filter ▾`, `▦ Columns`,
 * ⇅ on four headers and a `Showing 1–3 of 3` footer on it.
 *
 * ⚠ **`state` AND `onStateChange` ARE OPTIONAL AND THAT IS DELIBERATE.** A
 * caller that hands them over owns the request state; one that does not gets
 * an internally-held set, so `writeOffDecisions.test.tsx` — which mounts this
 * with four props and asserts the three decisions — is byte-for-byte
 * unaffected. Two writers on one state is a race, not a feature.
 *
 * ⚠ **THE DRAWING'S TWO SEPARATION-OF-DUTIES SENTENCES ARE SUPERSEDED, RULED
 * 2026-09-23 (`OQ-226`, option (a)).** p086 draws *"A second person decides."*,
 * *"You cannot approve one you asked for."* and a third row reading *"Yours —
 * someone else decides"* instead of the two buttons. **PO, verbatim:** *"allow
 * it - we are dealing with smaller utilites they dont have too many people"* —
 * a utility of 10–20 staff may not HAVE a second approver. So `BR-PAY-037`
 * stands re-affirmed, the *your request* warning below is the ratified shape,
 * and **none of the three drawn elements is built.** The PDF cannot be edited;
 * this is where the correction lives.
 *
 * ⚠ **ALL THREE DECISIONS STAY, AND THE DRAWING DRAWS TWO.** `Approve` and
 * `Refuse` are drawn; `Reverse` is not, and it is LIVE — an approved write-off
 * corrected by a new row (`CR-059` CS-25). Dropping a working control to match
 * a drawing would be a regression wearing rule 41's clothes, so the third
 * stays and the divergence is reported.
 */
export function WriteOffQueueTable(props: {
  rows: readonly WriteOffApprovalRow[];
  currentUserId: string | null;
  t: Translator;
  locale?: string;
  onDecide: (row: WriteOffApprovalRow, kind: WriteOffDecisionKind) => void;
  /** Handed over by a caller that owns the state; absent = held here. */
  state?: TableRequestState;
  onStateChange?: (next: TableRequestState) => void;
}) {
  const { rows, t } = props;
  const tenantPath = useTenantPath();
  const [ownState, setOwnState] = useState<TableRequestState>(() => ({
    q: "",
    sort: "requested_on",
    dir: "desc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  }));
  const state = props.state ?? ownState;
  const setState = props.onStateChange ?? setOwnState;
  // ⚠ **`GET /write-offs` IS UNPAGINATED AND SO IS THIS SEAM.** It is `NFR-3`'s
  // FOURTH unbounded read and `CLAUDE.md` names only three — its own docstring
  // says *"unpaginated, deliberately … a utility under 3,000 connections has a
  // queue a person reads in one screen"*, which is the ceiling that moved to
  // 40,000 on 2026-09-06. An approval queue is genuinely short, which is why
  // this is the least urgent of the four and not why it is absent.
  const page = clientPage(rows, state, WRITE_OFF_QUEUE_SPEC);
  const config = writeOffQueueConfig(
    t,
    props.currentUserId,
    props.locale,
    props.onDecide,
    tenantPath,
  );

  return (
    <DataTable
      config={config}
      state={state}
      onStateChange={setState}
      // The drawing's `+ Filter ▾`. Declared filters render through the
      // composed slot and through nothing else — see `OutstandingsTab`.
      filterBarSlot={
        <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
      }
      rows={page.page}
      totalRows={page.total}
      loading={false}
      empty={{
        title: t("payments.writeOffQueue.empty"),
        helper: t("payments.writeOffQueue.emptyHelper"),
      }}
    />
  );
}

/** How the browser narrows and orders the queue. */
const WRITE_OFF_QUEUE_SPEC: ClientTableSpec<WriteOffApprovalRow> = {
  // The drawing's prompt: *"Search account or requester…"* — and those are
  // exactly the two fields it matches (B14 rule 19).
  search: (row) => [row.account_no ?? "", row.requested_by_name ?? ""],
  filter: (row, name, value) => (name === "reason" ? row.reason === value : true),
  sortValue: (row, key) => {
    switch (key) {
      case "requested_on":
        return row.requested_on;
      case "account_no":
        return row.account_no;
      // Decides an ORDER only; the figure itself stays `MoneyCell`'s.
      case "amount":
        return Number(row.amount);
      case "requested_by_name":
        return row.requested_by_name;
      case "reason":
        return row.reason;
      default:
        return null;
    }
  },
};

function writeOffQueueConfig(
  t: Translator,
  currentUserId: string | null,
  locale: string | undefined,
  onDecide: (row: WriteOffApprovalRow, kind: WriteOffDecisionKind) => void,
  tenantPath: (path: string) => string,
): TableConfig<WriteOffApprovalRow> {
  return {
    screenId: "S36.writeoffs",
    columns: [
      { key: "requested_on", label: t("payments.writeOffQueue.col.requested"),
        sortable: true, cell: (row) => row.requested_on ?? "" },
      {
        key: "account_no",
        label: t("payments.col.account"),
        sortable: true,
        identity: true,
        // B14 rule 31 — never the id. This cell read `account_no ?? account_id`
        // and printed a raw uuid to a finance user on any account whose number
        // had not been minted, which is `DEF-2580` one screen along.
        //
        // Record links (PO 2026-10-19): the number opens the DEBTOR page, the
        // same door the Outstandings list's account cell opens.
        cell: (row) => {
          const href = debtorDetailPath(row.account_no);
          return href === null ? (
            <span className="pay-absent">{t("payments.writeOffQueue.noAccountNo")}</span>
          ) : (
            <InlineLinkTo to={tenantPath(href)}>{row.account_no}</InlineLinkTo>
          );
        },
      },
      {
        key: "amount",
        label: t("payments.col.amount"),
        sortable: true,
        numeric: true,
        // CLAUDE.md rule 2 — the row's OWN currency, not a tenant default. This
        // is the utility's record of money it has stopped chasing, and a bare
        // number is half a fact.
        cell: (row) => <MoneyCell amount={row.amount} currency={row.currency} locale={locale} />,
      },
      { key: "reason", label: t("payments.writeOffQueue.col.reason"),
        sortable: true, cell: (row) => writeOffReasonLabel(row.reason, t) },
      {
        key: "requested_by_name",
        label: t("payments.writeOffQueue.col.requestedBy"),
        sortable: true,
        cell: (row) => {
          // ⚠ **BR-PAY-037 — THIS IS A WARNING, NEVER A BLOCK.** The rule is
          // CONFIRMED and says the SAME user holding the approver role MAY
          // initiate AND approve in v1, both acts recorded distinctly;
          // enforced separation-of-duties is v2. The screen's job is to make
          // it DELIBERATE, and the drawing's own *"You cannot approve one you
          // asked for"* states a rule this product does not have — reported
          // under B14 rule 41 rather than built. ⚠ **THE PO RULED ON THAT
          // REPORT ON 2026-09-23 AND KEPT v1** (`OQ-226`, option (a);
          // *"allow it - we are dealing with smaller utilites they dont have
          // too many people"*), so this warning is the RATIFIED shape and the
          // drawn sentence is superseded. A person-level block is not a future
          // tidy-up here: it is v2 and it needs a new ruling.
          const isOwnRequest = currentUserId !== null && row.requested_by === currentUserId;
          return (
            <>
              {row.requested_by_name ?? t("payments.writeOffQueue.unknownRequester")}
              {isOwnRequest && (
                <span className="pay-sub">{t("payments.writeOffQueue.yourRequest")}</span>
              )}
            </>
          );
        },
      },
      {
        key: "status",
        label: t("payments.col.status"),
        // `posted_to_ledger` is derived from the JOURNAL ENTRY, not from the
        // status: the status says what a human decided, the entry id says what
        // the books carry, and US-PAY-012 TC-1's whole control is that those
        // are different facts.
        cell: (row) => (
          <StatusPill tone={row.posted_to_ledger ? "success" : "warning"}>
            {row.posted_to_ledger
              ? t("payments.writeOffQueue.posted")
              : t("payments.writeOffQueue.awaiting")}
          </StatusPill>
        ),
      },
      {
        key: "actions",
        label: t("payments.writeOffQueue.col.action"),
        locked: true,
        // ── CR-059 CS-25 — THE THREE DECISIONS. B14 rule 15: icons with an
        //    accessible name, never text links, and each blocked one renders
        //    VISIBLE AND DISABLED with its reason (BR-SHL-025) rather than
        //    disappearing — a control that vanishes teaches that the product
        //    cannot do the thing at all.
        cell: (row) => (
          <RowActions>
            <RowAction
              label={t("payments.writeOffQueue.approve")}
              icon={<CommitIcon />}
              reason={decisionBlockedReason(row, "approve", t)}
              onClick={() => onDecide(row, "approve")}
            />
            <RowAction
              label={t("payments.writeOffQueue.reject")}
              // ✕ and NOT the trash: *"rejection moves no money and is not a
              // deletion"* (CS-25, in as many words).
              icon={<RetireIcon />}
              reason={decisionBlockedReason(row, "reject", t)}
              danger
              onClick={() => onDecide(row, "reject")}
            />
            <RowAction
              label={t("payments.writeOffQueue.reverse")}
              // The same glyph a payment reversal uses, because it is the same
              // verb: an approved write-off is corrected by a NEW ROW.
              icon={<RollBackIcon />}
              reason={decisionBlockedReason(row, "reverse", t)}
              danger
              onClick={() => onDecide(row, "reverse")}
            />
            {/* ⚠ **WHO DECIDED, AND WHY — RESTORED 2026-09-23.** The first
                draft of the `DataTable` conversion dropped these four lines
                and `writeOffDecisions.test.tsx` went red on *"expected … to
                contain 'Priya Shah'"* and *"'Approved against the wrong
                account.'"*, which is the case doing exactly its job.

                They sit UNDER the actions rather than replacing them: the
                decision is a fact about the ROW and the controls are a fact
                about its STATE, and the cell this replaced conflated the two.
                **The REASON a request was refused is the only thing the
                requester is ever shown**, and a queue whose refusals say
                nothing sends the same request back tomorrow (`CR-059` CS-25). */}
            {row.status === "approved" && (
              <span className="pay-absent">
                {t("payments.writeOffQueue.approvedBy", {
                  who: row.approved_by_name ?? t("payments.writeOffQueue.unknownRequester"),
                  date: row.approved_on ?? "",
                })}
              </span>
            )}
            {row.status === "rejected" && (
              <span className="pay-absent">
                {t("payments.writeOffQueue.rejectedBy", {
                  who: row.rejected_by_name ?? t("payments.writeOffQueue.unknownRequester"),
                  date: row.rejected_on ?? "",
                })}
              </span>
            )}
            {row.rejection_reason !== undefined &&
              row.rejection_reason !== null &&
              row.rejection_reason !== "" && (
                <span className="pay-sub">{row.rejection_reason}</span>
              )}
            {row.reversal_reason !== undefined &&
              row.reversal_reason !== null &&
              row.reversal_reason !== "" && (
                <span className="pay-sub">{row.reversal_reason}</span>
              )}
          </RowActions>
        ),
      },
    ],
    getRowId: (row) => row.id,
    searchFields: ["account_no", "requested_by_name"],
    searchPlaceholder: "payments.writeOffQueue.searchPlaceholder",
    filters: [
      {
        name: "reason",
        label: t("payments.writeOffQueue.col.reason"),
        options: WRITE_OFF_REASON_CODES.map((code) => ({
          value: code,
          label: writeOffReasonLabel(code, t),
        })),
      },
    ],
    defaultSort: { sort: "requested_on", dir: "desc" },
  };
}

// ── The screen ────────────────────────────────────────────────────────────

/** The approval carries no typed fields — the decision IS the submit. A schema
 *  is still required by `FormModal`, and an empty one keeps the confirm flow,
 *  the server-error rendering and the single-submit guard identical to every
 *  other money action in this product. */
export function approveSchema() {
  return { safeParse: () => ({ success: true as const, data: {} }) } as never;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-012@3c9f5a1 (sources: 04-docs/05-modules/08-payments/06-epics/EP-PAY-03-exceptions.md US-PAY-012 §1/§3/§5 · 08-payments/02-business-rules.md BR-PAY-002/020/037 · 08-payments/03-field-map.md §3 + P-4/P-5 · 08-qa/01-e2e/journeys/J4-collections.md step 3)
// generated: 2026-08-16 by story-coder (payments SURFACE lane — the approval screen `GET /write-offs` was added for and never got)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the write-off queue test failed to resolve this module before it existed; verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: (1) SELF-APPROVAL IS WARNED, NOT BLOCKED. BR-PAY-037 is CONFIRMED and permits the same user to initiate and approve in v1 (*"both acts recorded distinctly; enforced separation-of-duties = v2"*), so blocking it would be this lane overturning a signed rule. THE BUILD BRIEF FOR THIS LANE ASKED FOR HARD SEPARATION — that was raised as OQ-226 for the PO and is not taken here. ⚠ **RULED 2026-09-23: OQ-226 CLOSED, option (a) — the PO kept v1** (*"allow it - we are dealing with smaller utilites they dont have too many people"*), so this exception is no longer an exception awaiting an answer: it is the ratified behaviour, BR-PAY-037 is CONFIRMED-AS-RE-AFFIRMED, and p086's *"You cannot approve one you asked for"* / *"Yours — someone else decides"* are SUPERSEDED · (2) no GL-account picker: the posting picks the designated bad-debt account through the ledger seam (BR-PAY-020), and a picker would let a clerk post bad debt to an account finance did not designate · (3) no un-approve and no bulk approve — a write-off row is append-only (BR-PAY-002) and each approval closes any live plan on the account (OQ-171), so it is one decision, one act, one audit row · (4) the current user is read from the SESSION (`getMe`) rather than taken as a prop: a prop nothing passed would silently disable the self-approval warning, which is the unwired-prop shape G13 exists to catch
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
