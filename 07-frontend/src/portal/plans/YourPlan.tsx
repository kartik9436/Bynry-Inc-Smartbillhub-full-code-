// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-052 (EP-CWP-10) — your payment plan, WHOLE, not a monthly
//           summary of it. Screen: CWP-043 (blueprint `P29`)
// Rules:    BR-CWP-063 (a plan holds the arrears; new bills still arrive and
//           still have to be paid) · BR-CWP-064 (late-fee and disconnection
//           suspension are a PER-PLAN election) · BR-CWP-056 (a held control
//           carries its reason) · B14 rule 20 · rule 21 · rule 31 (no database
//           id on screen) · rule 32 · rule 33 · rule 35 · rule 36 ·
//           CLAUDE.md hard rule 2 (2 dp displayed)
// Open:     OQ-CWP-1720 — the blueprint's *"missing two instalments ends the
//           plan"* against the PO's 2026-08-11 ruling that nobody is dropped.
//           **This panel does not say a plan ends.**
// Tests:    src/portal/plans/YourPlan.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getCurrentPlans`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

import {
  Card,
  ErrandLink,
  HeldButton,
  KVList,
  MiniTable,
  StatusChip,
  TotalRow,
  TwoCol,
  usePortalPath,
} from "../components/primitives";
import { PortalScreen, PortalState, type PortalWayOut } from "../components/states";
import { Panel } from "@/components/Panel";
import { usePortalDate } from "../components/regional";
import { formatMoney } from "../signin/Enrol";
import { ButtonAnchor } from "@/components/Button";
import { useParams } from "react-router-dom";
import {
  getCurrentPlans,
  planAgreementHref,
  type PortalPlan,
  type PortalPlanInstalmentRow,
} from "../api/portalClient";

const TONE: Record<string, "success" | "warning" | "danger" | "neutral" | "info"> = {
  paid_on_time: "success",
  // ⚠ **PAID LATE IS ITS OWN WORD AND ITS OWN TONE.** It is neither *paid on
  // time* nor *missed*: the money arrived and it arrived late, and a customer
  // reconciling a statement is exactly the person who wants to know which.
  paid_late: "warning",
  due_next: "info",
  to_come: "neutral",
  missed: "danger",
};

/**
 * `CWP-043` — the WHOLE plan record.
 *
 * ⚠ **FOUR THINGS THE BACK OFFICE HAS HELD ALL ALONG REACH A SCREEN HERE FOR
 * THE FIRST TIME** (`US-CWP-052` §1): the down payment after step one, the
 * cadence, whether the plan takes payment automatically, and **which payment
 * paid which instalment** — without that last one a customer cannot reconcile a
 * plan against a bank statement at all, which is the reason this screen exists.
 *
 * ⚠ **THE RIGHT-HAND PANEL IS THE PART CUSTOMERS GET WRONG.** A plan holds the
 * ARREARS; it does not pause the current month's bill, and the product enforces
 * exactly that distinction (`BR-CWP-063`). Saying it plainly here is cheaper
 * than the call that comes when the next bill arrives on top of the plan.
 *
 * ⚠ **THE HOLD PANEL IS READ FROM THIS PLAN'S OWN ELECTIONS** (`BR-CWP-064`).
 * On a plan where the clerk left late-fee suspension off it says **fees still
 * apply** — the blueprint singles that case out as *worse than a blank space*.
 *
 * ⚠ **A CLOSED PLAN IS STILL HERE, MARKED CLOSED.** It disappears from the
 * portal today and it must not: a finished plan is a thing a customer reconciles
 * against.
 *
 * ⚠ **AND THE PANEL DOES NOT SAY A PLAN ENDS ON A MISSED INSTALMENT.** The
 * blueprint promises it does; the Product Owner ruled on 2026-08-11 that nobody
 * is dropped — *"nodrop we chase for payments until write off"* — and that
 * ruling is what the code implements. The collision is `OQ-CWP-1720`; until it
 * is answered this screen states what happens, which is that we get in touch.
 */
export function YourPlanView(props: { accountId: string }) {
  // The tenant comes from the address bar and from nowhere else
  // (`BR-TEN-003`), the source every portal screen that leaves the SPA reads.
  const tenant = useParams().tenant ?? "";
  const { t } = useTranslation();
  const path = usePortalPath();
  const [plans, setPlans] = useState<PortalPlan[] | null>(null);
  const [failed, setFailed] = useState(false);
  //: R-10's *Try again* needs something to try — see `Overdue.tsx`.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setFailed(false);
    getCurrentPlans(props.accountId)
      .then((answer) => {
        if (live) setPlans(answer.plans);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [props.accountId, attempt]);

  // ⚠ **THE HEAD IS BUILT ONCE AND RENDERS ON EVERY BRANCH, LOADING INCLUDED**
  // (`DEF-CWP-4000`; audit D1, delta X4/X5). It composes the shared
  // `components/PageHeader.tsx` — the ONE page head B14 rule 2 names, which
  // fifteen portal files already used and twenty-eight signed-in screens did
  // not. A head that lived only in the happy-path return would leave the page
  // with no `<h1>` for as long as the request takes.
  //: The one instalment the server marked `due_next`, on a LIVE plan — the
  //: figure `08-screen-layouts.md` heads this screen with. A closed plan has
  //: nothing due next, and a plan fully paid has no such row at all.
  const nextDue =
    plans
      ?.filter((plan) => plan.live)
      .flatMap((plan) => plan.instalments)
      .find((row) => row.state === "due_next") ?? null;

  const head = (
    <PageHeader
      kicker={t("portal.kicker.payments")}
      title={t("portal.yourPlan.title")}
      // ⚠ **THE ACTION ROW, WHICH THE HEAD SWEEP DID NOT BRING WITH IT**
      // (`DEF-CWP-4000`, audit D1). `08-screen-layouts.md` heads `CWP-043`
      // *· actions ↓ Agreement · Pay the next one*; the agreement control was
      // drawn in a `mt-3` row at the FOOT of the instalments card. Moved, not
      // re-drawn — same `HeldButton`, same six-word reason (B14 rule 33).
      // ⚠ **THIS BLOCK ONCE SAID ONLY ONE OF THE DRAWING'S TWO ACTIONS WAS
      // HERE — *"this lane will not invent a destination for money"* — AND
      // THAT SENTENCE IS SUPERSEDED BY THE `DEF-CWP-4181` NOTE BELOW.** It is
      // struck rather than left standing, because two comments making opposite
      // claims about one head is `DEF-CWP-4918` in this file (`Payments.tsx`
      // still argues `/level-pay` is *"deliberately not here"* seventeen lines
      // under the entry that puts it there), and the stale one is always the
      // one that gives a reason.
      // ⚠ Absent while the read is in flight — a head action over a page that
      // may turn out to have no plan is a control pointing at nothing
      // (`BR-CWP-093`).
      // ⚠ **AND THE AGREEMENT IS A DOWNLOAD NOW (`CR-085` `CPB-14`).** It read
      // *"Downloads arrive later this year"*, and its row in `holds.ts` was
      // `unwatched` — the kind `G103` says in as many words it cannot see. It
      // is the SAME hold `CPB-03` released on `CWP-063` a wave earlier, on the
      // same document class out of the same store; releasing one and leaving
      // the other is hard-won law 12's shape for pointers.
      // ⚠ **HELD AGAIN WHERE NO COPY WAS FILED**, and that refusal cannot rot:
      // the server answers it from the store on every draw.
      //
      // ⚠ **AND THE SECOND DRAWN ACTION IS HERE NOW — `DEF-CWP-4181`.** The
      // note above used to read *"this lane will not invent a destination for
      // money"*, and that was right on the day it was written. It stopped
      // being right when `CWP-038` shipped: `/pay-now` is routed, live, and is
      // the door `CWP-057` already sends *Pay $247.30* to. So the destination
      // is not an invention, it is the one this product already uses — and a
      // plan screen that names an instalment due in eighteen days and offers
      // no way to pay it is R-10 breached on the exact screen R-10 is for.
      // ⚠ **THE AMOUNT IS THE NEXT INSTALMENT AND IT IS THE SERVER'S, NOT A
      // SUM.** `due_next` is a state the server sets on exactly one row; this
      // reads that row's `amount`. Nothing is added up here — the drawing's
      // second control, *Pay the whole $164.86*, would be `total` minus
      // `paid_to_date` computed in TypeScript, and it is reported rather than
      // built for that reason.
      // ⚠ **`null` DRAWS NO BUTTON** (`BR-CWP-093`): a plan whose instalments
      // are all paid, or one that is closed, has nothing to pay next.
      primaryAction={
        nextDue === null ? null : (
          <ErrandLink
            variant="primary"
            label={t("portal.home.pay", {
              amount: formatMoney(nextDue.amount, nextDue.currency),
            })}
            to="/pay-now"
          />
        )
      }
      secondaryActions={
        plans && plans.length > 0 ? (
          plans.some((plan) => plan.live && plan.agreement_available) ? (
            <ButtonAnchor
              variant="secondary"
              href={planAgreementHref(tenant, props.accountId)}
              data-download="plan-agreement"
            >
              {t("portal.yourPlan.agreement")}
            </ButtonAnchor>
          ) : (
            <HeldButton
              label={t("portal.yourPlan.agreement")}
              reason={t("portal.documents.cannotOpen")}
            />
          )
        ) : null
      }
    />
  );

  // ⚠ **R-10** (PO 2026-09-11). Both of these branches ended in a full stop
  // for a customer who is, by definition, asking a question about money.
  // `Ask for a payment plan` is the one door that is true in both — the empty
  // branch already carried it, and a failed read did not.
  const askForAPlan: PortalWayOut = {
    label: t("portal.overdue.askForAPlan"),
    to: path("/ask-for-a-plan"),
    testKey: "ask-for-a-plan",
  };
  const tryAgain: PortalWayOut = {
    label: t("portal.payNow.tryAgain"),
    onClick: () => setAttempt((n) => n + 1),
    tone: "primary",
    testKey: "try-again",
  };

  if (failed) {
    return (
      <PortalScreen screen="CWP-043" head={head}>
        <PortalState
          kind="failed"
          testId="your-plan"
          sentence={t("portal.yourPlan.couldNotRead")}
          waysOut={[tryAgain, askForAPlan]}
        />
      </PortalScreen>
    );
  }
  if (!plans) {
    return (
      <PortalScreen screen="CWP-043" head={head}>
        <PortalState kind="loading" testId="your-plan" sentence={t("portal.yourPlan.reading")} />
      </PortalScreen>
    );
  }
  if (plans.length === 0) {
    // ⚠ **A FULL STOP WAS THE WHOLE SCREEN** (`CR-085` task (c)).
    // *You are not on a payment plan.* — and nothing else, on a screen a
    // customer opens precisely because they are wondering whether they could
    // be. The door is the same one, now rendered by the shared state card so
    // it sits beside the sentence rather than under it.
    return (
      <PortalScreen screen="CWP-043" head={head}>
        <PortalState
          kind="empty"
          testId="your-plan"
          sentence={t("portal.yourPlan.none")}
          waysOut={[askForAPlan]}
        />
      </PortalScreen>
    );
  }

  return (
    <div data-screen="CWP-043">
      {/* ⚠ **THE SCREEN ID IS A LITERAL HERE AND MUST STAY ONE — `CR-085` lane 8.**
          `PortalScreen` renders an identical DOM from its `screen` prop, but THREE
          source scanners find a portal screen by the exact string
          `data-screen="CWP-…"` and not one of them reads a prop: this census,
          `g100_every_screen_has_a_door.py` and `g103_holds_cannot_rot.py`. Wrapping
          this branch too made the whole file invisible to all three — hard-won law
          7’s *reporting zero over a scope it silently excluded*.
          `bills/BillDetail.tsx` keeps the literal on its populated branch for
          exactly this reason. */}
      {head}
      {plans.map((plan) => (
        <OnePlan key={plan.started_on ?? plan.status} plan={plan} />
      ))}
    </div>
  );
}

function OnePlan(props: { plan: PortalPlan }) {
  const { t } = useTranslation();
  //: `DEF-CWP-4138` — the tenant's own date format, through the ONE formatter
  //: (`DEF-CWP-3994`'s wire). An unset Regional setting publishes nothing and
  //: this hands back the server's string unchanged, so it cannot invent a
  //: format for a tenant that has not chosen one.
  const showDate = usePortalDate();
  const { plan } = props;
  const paid = plan.instalments.filter(
    (row) => row.state === "paid_on_time" || row.state === "paid_late",
  ).length;

  return (
    <div className="mb-4" data-plan={plan.live ? "live" : "closed"}>
      <TwoCol
        main={
          <Card testId="your-plan">
            {/* ⚠ **THE TITLE WAS PRINTED TWICE, ONE LINE APART** —
                `Your payment plan` as the page `<h1>` and `YOUR PAYMENT PLAN`
                as this section title (`DEF-CWP-4183`). B14 rule 32's
                description budget spent saying the screen's own name again.
                The card opens on the progress line, which is what a customer
                came for. */}
            <p className="text-body text-neutral-600" data-progress="">
              {t("portal.yourPlan.progress", { paid, count: plan.term_months })}
            </p>
            {plan.closed_on !== null ? (
              // ⚠ Still reachable, marked closed with its date — never vanished.
              <p className="text-body text-neutral-600" data-closed-on={plan.closed_on}>
                {t("portal.yourPlan.closedOn", { date: showDate(plan.closed_on) })}
              </p>
            ) : null}
            <KVList
              rows={[
                {
                  key: "up-front",
                  label: t("portal.yourPlan.upFront"),
                  // ⚠ TC-3 — shown, and not only at creation, or the
                  // instalments look as though they came from nowhere.
                  value: (
                    <span data-up-front="">{formatMoney(plan.down_payment, plan.currency)}</span>
                  ),
                },
                {
                  key: "cadence",
                  // ⚠ **`cadenceLabel`, NOT `cadence` — G18 CAUGHT THIS.** The
                  // first draft called `portal.yourPlan.cadence`, which is the
                  // PREFIX of the four value keys and a key no catalogue
                  // defines, so the label would have rendered the raw key on
                  // every plan screen in every language. `tsc` and every DOM
                  // assertion passed on it: hard-won law 2, one layer down.
                  label: t("portal.yourPlan.cadenceLabel"),
                  // ⚠ TC-4 — READ from the record. A plan may be weekly.
                  value: <span data-cadence="">{t(`portal.yourPlan.cadence.${plan.cadence}`)}</span>,
                },
                {
                  key: "autopay",
                  label: t("portal.yourPlan.autopay"),
                  value: (
                    <span data-autopay={plan.autopay_enabled ? "on" : "off"}>
                      {plan.autopay_enabled
                        ? t("portal.yourPlan.autopayOn")
                        : t("portal.yourPlan.autopayOff")}
                    </span>
                  ),
                },
              ]}
            />
            <div className="mt-3">
              <MiniTable
                caption={t("portal.yourPlan.caption")}
                columns={[
                  { key: "seq", label: t("portal.yourPlan.colInstalment") },
                  { key: "due", label: t("portal.yourPlan.colDue") },
                  { key: "amount", label: t("portal.yourPlan.colAmount"), align: "right" as const },
                  { key: "status", label: t("portal.yourPlan.colStatus") },
                ]}
                rows={plan.instalments.map((row) => ({
                  key: String(row.seq),
                  cells: {
                    seq: t("portal.yourPlan.ofCount", { seq: row.seq, count: plan.term_months }),
                    due: showDate(row.due_on),
                    amount: (
                      <span className="tabular-nums" data-instalment={row.seq}>
                        {formatMoney(row.amount, row.currency)}
                      </span>
                    ),
                    status: <StatusCell row={row} />,
                  },
                }))}
              />
              <TotalRow
                label={t("portal.yourPlan.total")}
                value={formatMoney(plan.instalments_total, plan.currency)}
                testKey="instalments-total"
              />
            </div>
          </Card>
        }
        rail={
          <>
            <Panel as="aside" tone="info" title={t("portal.yourPlan.holdHeading")}>
              <ul className="m-0 list-disc pl-5 text-body leading-relaxed text-neutral-800">
                <li data-hold="late-fees">
                  {/* `BR-CWP-064` — the per-plan election, both ways. */}
                  {plan.suspend_late_fees
                    ? t("portal.yourPlan.hold.noLateFees")
                    : t("portal.yourPlan.hold.lateFeesApply")}
                </li>
                <li data-hold="disconnect">
                  {plan.suspend_disconnect
                    ? t("portal.yourPlan.hold.noDisconnection")
                    : t("portal.yourPlan.hold.disconnectionApplies")}
                </li>
                {/* `BR-CWP-063` — the sentence customers get wrong. */}
                <li data-hold="new-bills">
                  <strong>{t("portal.yourPlan.hold.newBills")}</strong>
                </li>
              </ul>
            </Panel>
            {/* ⚠ **WHAT A MISSED PAYMENT ACTUALLY DOES.** Not *the plan ends*:
                see the component docstring and `OQ-CWP-1720`. */}
            <Panel as="aside" tone="warning" title={t("portal.yourPlan.missedHeading")}>
              <p className="m-0 text-body text-neutral-800" data-missed-note="">
                {t("portal.yourPlan.missedNote")}
              </p>
            </Panel>
          </>
        }
      />
    </div>
  );
}

/** Where this instalment stands, and — when it is paid — **which payment
 *  cleared it** (`US-CWP-052` TC-2), by its `PAY-` number and never by an id. */
function StatusCell(props: { row: PortalPlanInstalmentRow }) {
  const { t } = useTranslation();
  const { row } = props;
  return (
    <span className="flex flex-col">
      <StatusChip tone={TONE[row.state] ?? "neutral"} testKey={`state-${row.seq}`}>
        {row.state === "due_next" && row.days_until !== null
          ? t("portal.yourPlan.dueInDays", { count: row.days_until })
          : t(`portal.yourPlan.state.${row.state}`)}
      </StatusChip>
      {row.paid_reference ? (
        <span className="text-base text-neutral-600" data-paid-by={row.seq}>
          {t("portal.yourPlan.paidBy", { reference: row.paid_reference })}
        </span>
      ) : null}
    </span>
  );
}
