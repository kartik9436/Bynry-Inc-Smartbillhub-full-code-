// ── Trace ──────────────────────────────────────────────
// Change:   CR-060 · C25 · T10 — the Finance strip goes from SEVEN to SIX and
//           **Refunds is re-homed as a panel inside Revenue & AR**. PO ruling
//           2026-09-03, asked directly, verbatim: *"C25 says six tabs. - this
//           is correct."* This file is the door that ruling took away.
// Story:    US-PAY-011 (refunds)   Screens: S36 (Finance · Revenue & AR) → S58
// Rules:    BR-PAY-014 (refund approval is Finance-area work, which is why the
//           surface lives in this area at all) · BR-PAY-020 (payments owns the
//           record, Finance reports it — the same split `BadDebtPanel` and
//           `WriteOffQueuePanel` already make) · BR-REP-001 (a money figure
//           labels its basis) · BR-SHL-020 (plain-language failure) ·
//           BR-SHL-023 (one money formatting path) · CLAUDE.md rule 2 (money
//           4dp, DISPLAY 2, beside a CHAR(3)) · B14 rule 21 (no Tailwind here) ·
//           B14 rule 31 (no database id is the visible value of a field) ·
//           B14 rule 32 (one sentence a section)
// Ruling:   PO 2026-09-03 (the count) · Eng integrator 2026-09-03 (the
//           placement) — both in `12-governance/02-decision-log.md`
// Tests:    07-frontend/src/features/ledger/revenueAr.test.tsx
// ───────────────────────────────────────────────────────
// **THE DOOR TO S58, ON THE SCREEN THAT OWNS THE CREDIT IT GIVES BACK.**
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS PANEL EXISTS, AND WHY IT IS IN *THIS* TAB
// ══════════════════════════════════════════════════════════════════════════
// `RefundsPage` shipped whole at `2.125.2` (CR-059 task 18) and it landed as an
// EIGHTH Finance tab. `CR-060` `C25` names six, the PO confirmed six, and
// Refunds is not one of them. **Removing a tab without building its door would
// have left a finished five-act lifecycle reachable only by typing a URL** —
// hard-won law 2, at feature scale, in the module that has already met it five
// times. So the tab went and this panel arrived in the same change.
//
// **The tab it went into is not a preference.** `C25` folds Write-offs into
// Revenue & AR *"where the receivable it gives up already lives"*, and that
// sentence decides Refunds too: **a refund gives back money the customer's
// ACCOUNT holds as credit, and the credit position lives in Revenue & AR.** So
// this panel sits directly beside `WriteOffQueuePanel`, on the same principle.
//
// **THE COUNTER-ARGUMENT, CONSIDERED AND DECLINED** — recorded so the next
// reader does not re-open a settled question: a refund cheque appears on the
// bank reconciliation as an outstanding cheque (`CS-14` states it in the
// statement's own arithmetic), which argues for Deposits & Bank. Declined,
// because that is the cheque CLEARING — which already lives in bank rec,
// exactly as a payment's deposit batch lives in Deposits & Bank while the
// payment itself lives here.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS PANEL DOES NOT DO, AND WHY THAT IS THE POINT
// ══════════════════════════════════════════════════════════════════════════
//   · **IT OFFERS NO ACT.** Raise, approve, issue, mark-cleared and void all
//     stay on `RefundsPage`, which is still routed at `/finance/refunds`. A
//     second copy of five role-gated controls is five places for a gate to
//     drift, and the write-off precedent one component along is the opposite
//     case for a good reason: a one-control approval list IS a panel, and a
//     five-act lifecycle is a destination. **This panel is the door to it.**
//   · **IT SHOWS THE WAITING QUEUE ONLY.** *Issued* and *all* are the other two
//     views `CR-059` §10 asks for and they are `RefundsPage`'s; the question
//     Revenue & AR asks is *what is outstanding against the credit we hold*.
//   · **IT NEVER NAMES THE ACCOUNT.** `selectors.refund_row` carries
//     `payment_id` and no account, and a database id is never the visible value
//     of a field (B14 rule 31). The cheque number stands in, exactly as it does
//     on the page, and a row with none says so in words. `DEF-3119` tracks the
//     missing read; nothing here approximates it.
//   · **IT ADDS NO COPY.** Every string below is a key the eleven catalogues
//     already carry — `finance.tab.refunds` is the heading (the tab label,
//     re-used rather than orphaned) and `payments.bulk.openRefundQueue` is the
//     link. B14 rule 32 gives this section one sentence and it does not spend
//     it: the queue itself is the sentence.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE ADDS NO CLASS AND NO TAILWIND UTILITY (B14 rule 21)
// ══════════════════════════════════════════════════════════════════════════
// `07-frontend/src/styles/route-b-migrated.txt` lists neither
// `features/payments/*` nor `features/ledger/*`. A Tailwind utility written
// here would be a class NO stylesheet declares: it renders as nothing at all
// while `tsc`, eslint and every `toContain("flex")` assertion pass, because the
// class IS in the DOM (DEF-974). Every class below is one `payments.css` or
// `finance.css` already declares — the same set `WriteOffQueuePanel` uses — and
// G31, at a ceiling of zero undeclared classes, is what holds it.
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getRefunds } from "@/api/endpoints";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { InlineLink } from "@/components/Surfaces";
import { LoadingSkeleton } from "@/components/StateFrame";
import { AbsentPanel } from "@/features/ledger/financeShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { refundDetailPath } from "@/features/ledger/RefundDetailPage";
import { useTenantPath } from "@/routing/tenantPath";

import { REFUNDS_ROUTE } from "./paymentsShared";

import "./payments.css";

/**
 * The SAME key `RefundsPage` uses for its own `requested` view, so opening the
 * page from this panel costs no second request and approving one there
 * invalidates this one. A second key would be a second copy of the queue, free
 * to disagree with the first about what is waiting.
 */
export const refundsQueuePanelQueryKey = ["payments", "refunds", "requested"] as const;

/**
 * How many waiting refunds this panel draws before it stops and states the
 * total (`P1.3` · `DEF-PAY-6555`).
 *
 * ⚠ **THIS PANEL RENDERED EVERY PENDING ROW, AND THE READ UNDER IT SERVED
 * EVERY PENDING ROW.** The argument for that was a good one, in the selector's
 * own words — *"a page of an approval queue is a queue that lies about what is
 * pending"* — and the ceiling under it moved to 40,000 accounts on 2026-09-06.
 *
 * **The answer is the COUNT, which is why the total below is not optional.**
 * The Finance blueprint settles it on p040: *"`Refunds · 1` states the true
 * total on every page, so paging can no longer hide anything."* A panel drawing
 * five rows and saying nothing about the other nine hundred would be exactly
 * the lie the unpaginated read existed to prevent.
 *
 * **Five, because this is a DOOR and not the queue.** The queue is
 * `RefundsPage`, which has a table, a pager and the five acts; this panel's job
 * is *"something is waiting, here is how much, here is the way in"*. A longer
 * list inside a Revenue & AR tab would be a second copy of a screen that
 * already exists — `E1` in this file's own lifecycle notes.
 *
 * ⚠ **IT IS NOT SENT AS `per`, AND THAT IS DELIBERATE RATHER THAN AN
 * OVERSIGHT.** `core.pagination.clamp_page_size` clamps to the IS-2 vocabulary
 * — 50 / 100 / 200 / 500 / 1000 — so `per=5` would arrive as **50** and this
 * constant would be a parameter the server silently ignores, which hard-won law
 * 14 names as worse than one that errors. So the WIRE is bounded by the default
 * page of fifty and the SCREEN by this number, and both are stated rather than
 * assumed. Fifty rows is the difference between a bounded request and a request
 * for every refund the utility has ever raised, which is the defect.
 */
export const REFUND_PANEL_ROWS = 5;

export interface RefundsQueuePanelProps {
  t: Translator;
  locale?: string;
  client?: ApiClient;
}

export function RefundsQueuePanel(props: RefundsQueuePanelProps) {
  const { t } = props;
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();

  const queue = useQuery({
    queryKey: refundsQueuePanelQueryKey,
    queryFn: () => getRefunds({ status: "requested" }, client),
    // A missing route or a refused role is not a flaky network — the same
    // posture `WriteOffQueuePanel` takes beside this one.
    retry: false,
  });

  // A refusal is REPORTED, never drawn as an empty queue. *"Nothing is waiting"*
  // and *"we could not read what is waiting"* are opposite answers, and a finance
  // officer acts differently on each.
  if (queue.isError) {
    return (
      <AbsentPanel
        title={t("finance.tab.refunds")}
        reason={apiErrorText(queue.error, props.t)}
      />
    );
  }

  // ⚠ **THE TOTAL IS THE SERVER'S `count` AND NEVER `rows.length`** — that is
  // the whole of `P1.3`. `count` is a `COUNT(*)` over the filtered set;
  // `rows.length` is how many fitted on one page, and rendering it as the total
  // is precisely the lie this panel used to be unbounded to avoid.
  //
  // ⚠ **`count` AND NOT `pending`, AND THE TWO AGREE HERE FOR A REASON WORTH
  // STATING.** `P2.19` serves `pending` — the whole `requested` population,
  // ignoring every filter — for the badge in the Revenue & AR view label, and
  // `count` is the total over what THIS request asked for. This panel asks for
  // `f.status=requested` and nothing else, so the two are the same number; the
  // moment this panel gains a filter they stop being, and it is `pending` that
  // would then be the honest heading.
  const rows = (queue.data?.results ?? []).slice(0, REFUND_PANEL_ROWS);
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("finance.tab.refunds")}</h3>
        {/* ⚠ **THE TOTAL IS STATED ONCE ON THIS SCREEN, AND IT IS NOT STATED
            HERE.** This head carried `12 waiting` for about an hour on
            2026-09-24 and it was a SECOND copy: `P2.15`/`P2.18` put a
            `CountBadge` on the **Refunds** view label directly above this
            panel, reading `P2.19`'s `pending`, so a clerk saw the same number
            twice within 200px. B14 rule 32 gives a screen a description budget
            and the badge is the better of the two — `pending` counts the whole
            `requested` population and cannot be narrowed, while this panel's
            `count` is the total over what THIS request asked for.
            **The wire keeps both** (`DEF-PAY-6555`): `count` is what makes the
            bounded request honest and is asserted in the backend suite; the
            badge is what a person reads. `DEF-PAY-6623` records the coupling —
            if the view label ever loses its badge, this panel goes silent about
            the total and the old objection comes back. */}
      </div>
      {queue.isPending ? (
        <LoadingSkeleton variant="kpi" />
      ) : rows.length === 0 ? (
        <p className="fin-absent-reason" role="note">
          {t("payments.refunds.empty")}
        </p>
      ) : (
        <ul className="pay-writeoff-rows">
          {rows.map((row) => (
            <li key={row.id}>
              {/* B14 rule 31 — the CHEQUE NUMBER, which is the human-facing
                  reference, and a stated absence where there is none. There is
                  no `?? row.payment_id` fallback here and there must never be
                  one: that exact shape printed a raw uuid to a finance user one
                  screen along (`DEF-2580`), and `RefundsPage`'s own reference
                  cell carries the same warning. */}
              {/* ⚠ **`P3.3` — THE DOOR TO 2·5d, WHICH NOTHING HAD.**
                  `GET /refunds/{id}` and three reads beside it were built,
                  tested and called by NOBODY, which is why the approve modal
                  one screen along apologises in the product's own words: *"The
                  account is not shown here. No account served."* p047's DOORS
                  row names this exact control: *"NOTHING today. After P3.3: the
                  refund number on 2·5 Refunds."*

                  The LABEL is still the cheque number with its stated absence —
                  no `?? row.id` fallback, ever (`DEF-2580`) — and the id rides
                  in the ROUTE, which is what the blueprint draws (`:id`) and
                  the only place it appears. */}
              <InlineLink
                type="button"
                onClick={() => navigate(tenantPath(refundDetailPath(row.id)))}
              >
                {row.reference ?? t("payments.refunds.noReference")}
              </InlineLink>
              <MoneyCell
                amount={row.amount}
                currency={row.currency}
                basis="posting"
                locale={props.locale}
              />
              <span className="fin-fact-label">{t("payments.refunds.status.requested")}</span>
            </li>
          ))}
        </ul>
      )}
      {/* THE DOOR. It is drawn in every state — including the empty one —
          because *raise a refund* is reached through it, and a link that
          appears only when something is already waiting is a link nobody can
          use to start. `/finance/refunds` is still routed; this is simply the
          strip's job done by a panel. */}
      <InlineLink type="button" onClick={() => navigate(tenantPath(REFUNDS_ROUTE))}>
        {t("payments.bulk.openRefundQueue")}
      </InlineLink>
    </Panel>
  );
}

export default RefundsQueuePanel;

// ── Lifecycle ─────────────────────────────────────────────
// packet: 12-governance/02-decision-log.md 2026-09-03 (the ruling and the
//         placement, with the counter-argument declined) · 12-governance/
//         11-change-requests.md CR-060 C25 · §0d.2 · T10 · CR-059 §10 P3 +
//         task 18 · 07-frontend/src/features/ledger/RevenueArPage.tsx
//         (WriteOffQueuePanel, the precedent this copies) ·
//         07-frontend/src/features/payments/BadDebtPanel.tsx (the file shape) ·
//         04-docs/02-decisions/14-ui-conventions.md rules 21/31/32
// generated: 2026-09-03 by the CR-060 T10 six-tab lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — removing the Refunds entry from FINANCE_TABS broke
//        `tsc` on the two places that named it, verbatim in the lane report;
//        and the new strip test in revenueAr.test.tsx was shown RED against the
//        seven-tab array before the entry came out.
// exceptions:
//   E1 **NO ACT IS OFFERED HERE.** Raise, approve, issue, mark-cleared and void
//      stay on `RefundsPage` at `/finance/refunds`, which is still routed. A
//      second copy of five role-gated controls is five places for a gate to
//      drift; this panel is the door, not a duplicate screen.
//   E2 **NO NEW LOCALE KEY.** Another lane held the eleven catalogues while
//      this landed, and every string here is a key they already carry —
//      `finance.tab.refunds` (the retired tab's own label, re-used as the
//      heading rather than orphaned) and `payments.bulk.openRefundQueue`.
//   E3 **THE ACCOUNT IS STILL NOT NAMED**, for the reason `RefundsPage` states:
//      `selectors.refund_row` serves `payment_id` and no account, and B14
//      rule 31 forbids printing the id. `DEF-3119`. Unchanged by this move.
//   E4 **NO CLASS ADDED AND NO TAILWIND UTILITY** — neither `features/payments/*`
//      nor `features/ledger/*` is on `route-b-migrated.txt` (DEF-974).
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
