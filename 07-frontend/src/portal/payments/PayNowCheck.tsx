// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-045 (EP-CWP-09). Screen: CWP-076 — blueprint 36 *Check
//           before you pay* (p66), at `/{tenant}/portal/pay-now/check`
// Change:   CR-085 step 2 lane 6. PO 2026-09-11: *"it should be 3 screens -
//           confirmed"*, then *"ii). Your ruling was about the shape, not the
//           addresses."* — so this screen is NEW and it is at `/pay-now/check`,
//           NOT at `/pay/check`, which is the GUEST flow and does not move.
//           ⚠ The blueprint draws screens 35–37 at `/pay`, `/pay/check` and
//           `/pay/done`; the product has had the two journeys at each other's
//           addresses since CR-068 and the divergence is RULED. Do not
//           "correct" the router from the drawing.
// Rules:    R-10 (PO 2026-09-11, verbatim: *"when a screen tells a customer
//           something bad, the thing they can do about it must be on that same
//           screen, next to the message. Not a page away. Not in a menu. Right
//           there."*) · R-22 (three states, three SENTENCES) · BR-CWP-056 (a
//           held control is visible, disabled and carries its reason) ·
//           BR-CWP-058 (where the payment lands, before it commits) ·
//           BR-CWP-047 (nothing here is cached) · B14 rule 2 (one page head) ·
//           rule 21 · rule 31 (no database id on screen) · rule 32 · rule 33 ·
//           rule 35 · rule 36 (compose the kit) · CLAUDE.md hard rule 2 (money
//           to 2 dp) · hard rule 4 (a payment is never edited) · hard rule 6
//           (one idempotency key, re-sent and never re-minted)
// Defects:  DEF-CWP-4866 (a refusal a phone cannot read) · DEF-CWP-4868 (a
//           declined payment with ZERO controls on the screen)
// Tests:    src/portal/payments/PayNowCheck.dom.test.tsx
// Impacts:  src/portal/payments/PayNow.tsx (hands the choice on) ·
//           src/portal/payments/PayNowDone.tsx (the receipt it hands on)
// ───────────────────────────────────────────────────────
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { Button, ButtonLink } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { PortalRefusal } from "../components/a11y";

import {
  Card,
  ConsequenceBox,
  KVList,
  SectionTitle,
  Stepper,
  TotalRow,
  TwoCol,
  usePortalPath,
  WizardFooter,
} from "../components/primitives";
import { PortalScreen, PortalState } from "../components/states";
import { formatMoney } from "../signin/Enrol";
import {
  getPayNow,
  payNow,
  previewPayment,
  type PortalPayNow,
  type PortalPayPreview,
  type PortalPayResult,
} from "../api/payNowClient";
import { WhereItWillGo, consequences, heldSentence } from "./PayNow";
import { HeldCommit } from "../components/heldCommit";
import { PayNowShell, payNowHandoffFrom } from "./payNowFlow";

/**
 * `CWP-076` — **the last screen at which anything can be changed.**
 *
 * ⚠ **WHY IT IS ITS OWN SCREEN, IN THE DRAWING'S OWN WORDS:** *"The pay screen
 * is a form; this is a confirmation. Separating them means the total, the fee
 * and the date are read once, deliberately, rather than glanced at while
 * choosing a card."* The PO's reason is plainer and is the one that decided it:
 * a payment is the journey where somebody wants a page they can stop on, go
 * back to and screenshot.
 *
 * ⚠ **THE FIGURES ARE RE-READ HERE, NEVER CARRIED.** What `CWP-038` hands on is
 * the CHOICE — an amount, an instrument and the idempotency key — and this
 * screen asks the server again. That is the same discipline the guest flow
 * already states (`QuickPayCheck`: *"what step 1 hands on is the PAIR, not the
 * answer"*), and it is what makes the drawing's `AMOUNT CHANGED` state real: a
 * payment that landed while the customer was choosing changes the total they
 * are about to agree to, and they read the new one.
 *
 * ⚠ **THE KEY IS RE-PRESENTED AND NEVER RE-MINTED** (`US-CWP-045` TC-7, hard
 * rule 6). The preview seam answers `key or mint()`, so presenting the key from
 * step one means the re-price, the commit and every retry of it carry one
 * string — and a debit that already happened cannot be taken twice.
 *
 * ⚠ **A DECLINED PAYMENT IS NOT A DEAD END ANY MORE — `DEF-CWP-4868`, and it is
 * R-10 exactly.** The old single screen answered `declined` and `refused` with
 * *"No money was taken. Try another card or bank account."* and **zero
 * controls**: no back, no retry, no door to `/payment-methods`, and the form the
 * customer had filled in was gone. Measured in a browser at 390 and at 1280 on
 * 2026-09-11 — `controls: []` both times. Here the outcome is drawn **on this
 * screen, with the amount and the method still chosen** (which is also
 * blueprint 35's own DECLINED state: *"the amount and method stay selected"*),
 * and the ways out sit next to the sentence.
 *
 * ⚠ **ONLY `paid` LEAVES FOR `CWP-077`.** A screen called *Payment made* must
 * never be reachable on a tenant with no gateway, so the receipt screen is
 * entered only with a result the server answered `paid` — and its own parser
 * refuses anything else (`paidResultFrom`).
 */
export function PayNowCheckView(props: { accountId?: string | null; client?: ApiClient }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const path = usePortalPath();
  const location = useLocation();
  const handoff = payNowHandoffFrom(location.state);
  const accountId = props.accountId ?? null;

  const [screen, setScreen] = useState<PortalPayNow | null>(null);
  const [panel, setPanel] = useState<PortalPayPreview | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [working, setWorking] = useState(false);
  /** The outcome that is NOT `paid`. `paid` never lands here — it navigates. */
  const [outcome, setOutcome] = useState<PortalPayResult | null>(null);

  const amount = handoff?.amount ?? null;
  const instrumentId = handoff?.instrumentId ?? null;
  const key = handoff?.idempotencyKey ?? null;

  const reread = useCallback(async () => {
    if (accountId === null || amount === null || key === null) return;
    setFailed(false);
    try {
      // ⚠ **BOTH READS, AND THE FIRST ONE IS NOT OPTIONAL.** The preview gives
      // the figures; `getPayNow` gives the SERVER'S VERDICT on whether this
      // account may pay at all and which instrument is still selectable. A
      // screen that carried `can_pay` from the previous page would be showing a
      // live Pay button over a permission that had changed — `BR-CWP-056` says
      // the hold is the server's answer, re-asked, not a fact the browser keeps.
      const [now, priced] = await Promise.all([
        getPayNow(accountId, props.client),
        previewPayment(accountId, { amount, idempotency_key: key }, props.client),
      ]);
      setScreen(now);
      setPanel(priced);
    } catch {
      setFailed(true);
    }
  }, [accountId, amount, key, props.client]);

  useEffect(() => {
    void reread();
  }, [reread, attempt]);

  const head = (
    <PageHeader
      kicker={t("portal.money.kicker")}
      title={t("portal.payNowCheck.title")}
      backTo={{ label: t("portal.payNow.title"), to: path("/pay-now"), testId: "check-back" }}
    />
  );

  const steps = (
    <Stepper
      steps={[
        t("portal.payNow.step.choose"),
        t("portal.payNow.step.check"),
        t("portal.payNow.step.done"),
      ]}
      current={2}
    />
  );

  // ⚠ **ARRIVING HERE WITH NOTHING IS A WRONG TURN, NOT AN ERROR** — a reload, a
  // bookmark, a link somebody kept. The address deliberately carries nothing, so
  // there is nothing to re-read. One sentence, and the door back is LIVE and by
  // address (`DEF-CWP-3925`: the mirror of dead UI is a live screen behind a
  // dead control).
  if (handoff === null) {
    return (
      <PortalScreen screen="CWP-076" head={head}>
        {steps}
        <PortalState
          kind="empty"
          testId="pay-now-check-no-handoff"
          sentence={t("portal.payNowCheck.startAgainBody")}
          waysOut={[
            {
              label: t("portal.payNowCheck.startAgain"),
              to: path("/pay-now"),
              tone: "primary",
              testKey: "start-again",
            },
          ]}
        />
      </PortalScreen>
    );
  }

  if (failed) {
    return (
      <PortalScreen screen="CWP-076" head={head}>
        {steps}
        <PortalState
          kind="failed"
          testId="pay-now-check-failed"
          sentence={t("portal.payNowCheck.couldNotRead")}
          waysOut={[
            {
              label: t("portal.payNow.tryAgain"),
              testKey: "retry",
              onClick: () => setAttempt((n) => n + 1),
            },
            { label: t("portal.payNowCheck.change"), testKey: "change", to: path("/pay-now") },
          ]}
        />
      </PortalScreen>
    );
  }

  if (screen === null || panel === null || accountId === null) {
    return (
      <PortalScreen screen="CWP-076" head={head}>
        {steps}
        <PortalState
          kind="loading"
          testId="pay-now-check-reading"
          sentence={t("portal.payNowCheck.reading")}
        />
      </PortalScreen>
    );
  }

  const instrument = screen.instruments.find((one) => one.id === instrumentId) ?? null;
  const chosen = instrument !== null && instrument.selectable ? instrument.id : null;
  const ready = screen.can_pay && chosen !== null && outcome === null;
  // ⚠ **BLUEPRINT 36's `METHOD EXPIRED` STATE, AND ITS OWN WORDS ARE THE
  // REASON THIS BRANCH EXISTS: *"Caught here, not at the processor: the row is
  // flagged and Pay is disabled."*** The generic *Add a card or bank account.*
  // is true and useless to somebody whose saved card expired between choosing
  // it and confirming it — `BR-CWP-056` asks for THE reason, not for a reason.
  const refusal =
    instrument !== null && !instrument.selectable && instrument.held_reason !== null
      ? t(`portal.payNow.held.${instrument.held_reason}`)
      : heldSentence(t, screen, panel, amount, chosen);

  async function commit() {
    if (accountId === null || amount === null || key === null) return;
    setWorking(true);
    try {
      // ⚠ THE SAME KEY, EVERY TIME. A retry that minted a fresh one would have
      // idempotency that reads correctly and protects nothing.
      const answer = await payNow(
        accountId,
        { amount, instrument_id: instrumentId, idempotency_key: key },
        props.client,
      );
      if (answer.outcome === "paid") {
        // ⚠ **THE RECEIPT IS A SCREEN, AND THE BALANCE IT SHOWS IS THE SERVER'S
        // OWN.** `remaining_balance` is what the preview worked out for after
        // this exact payment, and this payment has now happened — so the
        // receipt states a figure it did not compute (R-23's shape, and the
        // reason `CWP-077` can answer *where do I stand* at all).
        navigate(path("/pay-now/done"), {
          state: { result: answer, balanceAfter: panel?.remaining_balance ?? null },
          replace: true,
        });
        return;
      }
      setOutcome(answer);
    } catch {
      setFailed(true);
    } finally {
      setWorking(false);
    }
  }

  return (
    <div data-screen="CWP-076">
      {/* ⚠ **THE SCREEN ID IS A LITERAL HERE AND MUST STAY ONE.**
          `PortalScreen` renders an identical DOM from its `screen` PROP, and two
          source scanners find a portal screen by the exact string
          `data-screen="CWP-…"` — `pageHeadCensus.test.ts`'s `screenFiles()`
          (`/data-screen="(CWP-\d+)"/g`) and `g100_every_screen_has_a_door.py`'s
          `SCREEN_MARK`. Neither reads a prop. This screen was BORN on
          `PortalScreen` for every branch, so it was invisible to both from its
          first commit and the census reported green over a scope that silently
          excluded it — hard-won law 7's *reporting zero over a scope it
          excludes*. `bills/BillDetail.tsx` and `payments/Fees.tsx` keep the
          literal on their populated branch for exactly this reason; `CR-085`
          step 2 lane 7 restored it on ten more. Do not tidy it back. */}
      {head}
      {steps}
      <TwoCol
        main={
          <Card testId="pay-now-check">
            <SectionTitle>{t("portal.payNowCheck.whatYouArePaying")}</SectionTitle>
            <KVList
              rows={[
                {
                  key: "from",
                  label: t("portal.payNowCheck.from"),
                  // B14 rule 31 — the label a person recognises, never the id.
                  value: (
                    <span data-check-method="">
                      {instrument?.label ?? t("portal.payNowCheck.noMethodChosen")}
                    </span>
                  ),
                },
                {
                  key: "settles",
                  label: t("portal.payNowCheck.settles"),
                  value: (
                    <span data-check-settles="">
                      {panel.lands_on.length > 0
                        ? panel.lands_on.map((row) => row.number).join(" · ")
                        : t("portal.payNow.landsNowhere")}
                    </span>
                  ),
                },
                {
                  key: "after",
                  label: t("portal.payNowCheck.balanceAfter"),
                  value: (
                    <span className="tabular-nums" data-check-after="">
                      {formatMoney(panel.remaining_balance, panel.currency)}
                    </span>
                  ),
                },
              ]}
            />
            {/* Hard rule 2 — the total is the SERVER's priced figure, rendered
                at two decimals, and nothing on this screen adds anything up. */}
            <TotalRow
              label={t("portal.payNowCheck.total")}
              value={
                <span data-check-total={panel.amount}>
                  {formatMoney(panel.amount, panel.currency)}
                </span>
              }
              testKey="check-total"
            />

            {/* ⚠ **THE CONSEQUENCE STANDS OR FALLS WITH THE COMMIT IT
                DESCRIBES** (`DEF-CWP-4867`). On the old single screen it was
                drawn on `panel !== null` alone, so it promised the payment over
                a dead button. */}
            {screen.can_pay ? (
              <ConsequenceBox
                heading={t("portal.payNow.consequenceHeading")}
                bullets={consequences(t, screen, panel, chosen)}
              />
            ) : null}

            {/* ⚠ **THE OUTCOME IS ON THIS SCREEN, WITH ITS WAYS OUT BESIDE IT**
                — R-10 as the PO ruled it, and `DEF-CWP-4868`'s fix. */}
            {outcome !== null ? (
              <Outcome
                result={outcome}
                onTryAgain={() => {
                  setOutcome(null);
                  setAttempt((n) => n + 1);
                }}
                changeTo={path("/pay-now")}
                methodsTo={path("/payment-methods")}
              />
            ) : null}

            {/* `DEF-CWP-9164` — the way back on the LEFT, Pay on the RIGHT. */}
            <WizardFooter
              back={
                // The drawing's own second control: *Go back and change
                // something*. Not a primary and not the danger tier — going back
                // is neither destructive nor the thing to press.
                <ButtonLink to={path("/pay-now")} variant="secondary" data-change="">
                  {t("portal.payNowCheck.change")}
                </ButtonLink>
              }
              forward={
                // ⚠ **THE ONE CONTROL IN THIS PRODUCT THAT TAKES MONEY**, and
                // the blueprint's own note about it: *"the button is the last
                // thing read before money moves"*. `HeldCommit` renders its
                // refusal as TEXT as well as `title` — on a phone a tooltip does
                // not exist (`DEF-CWP-4866`).
                <HeldCommit
                  label={t("portal.payNow.pay", {
                    amount: formatMoney(panel.amount, panel.currency),
                  })}
                  working={working}
                  ready={ready}
                  reason={refusal}
                  onClick={() => void commit()}
                  testKey="commit"
                />
              }
            />
          </Card>
        }
        rail={
          <>
            <WhereItWillGo panel={panel} order={screen.order} />
            {screen.environment === "sandbox" ? (
              <Panel as="aside" tone="warning" title={t("portal.payNow.testingTitle")}>
                <p className="text-body text-neutral-700" data-sandbox="">
                  {t("portal.payNow.testing")}
                </p>
              </Panel>
            ) : null}
          </>
        }
      />
    </div>
  );
}

/**
 * What happened, when it was not `paid` — **and what the customer can do about
 * it, right here** (R-10).
 *
 * ⚠ **THREE OUTCOMES, THREE DIFFERENT SENTENCES, AND THE MIDDLE ONE IS THE
 * POINT.** *Declined* says no money moved. *No answer* says nobody knows —
 * and its retry re-sends the key the first attempt used, so a debit that
 * already happened is never taken twice. *Refused* says the utility will not
 * take it, in the server's own reason. A screen that said *failed* to all three
 * would tell a customer their card was refused when it may have been charged.
 *
 * ⚠ **THE WAYS OUT DIFFER BY OUTCOME AND THAT IS NOT DECORATION.** Trying again
 * is offered only where trying again is safe and could work. Changing the card
 * is offered on a decline, because that is what the sentence tells them to do —
 * and `DEF-CWP-3972`'s lesson is that a refusal naming an action is a promise
 * the action is reachable from where the person is standing.
 */
function Outcome(props: {
  result: PortalPayResult;
  onTryAgain: () => void;
  changeTo: string;
  methodsTo: string;
}) {
  const { t } = useTranslation();
  const { result } = props;
  const said =
    result.outcome === "refused" && result.held_reason !== null
      ? t(`portal.payNow.held.${result.held_reason}`)
      : t(`portal.payNow.done.${result.outcome}`);
  return (
    <section
      // It is news about their money: the strip below is announced
      // assertively and takes focus (`PortalRefusal`, F-02 / F-04), so this
      // section is no longer a second alert that would read it twice.
      data-pay-outcome={result.outcome}
      className="flex flex-col gap-2"
    >
      <p className="text-body font-semibold text-neutral-900" data-outcome-title="">
        {t(`portal.payNow.done.${result.outcome}Title`)}
      </p>
      {/* ⚠ **THE KIT'S OWN REFUSAL STRIP, NOT A BOX BUILT HERE** (B14 rule 36,
          and 71 call sites already draw it). The first draft of this block
          wrote `border-danger-200 border-l-danger-600` — **two utilities this
          theme has no token for**, so they would have compiled to NOTHING while
          `tsc`, every test and every `toContain` assertion passed on the class
          list (B14 rule 21's per-file clause, `DEF-974`). The theme declares
          `danger-100`, `-500` and `-700` and no other step. */}
      <PortalRefusal data-outcome-said="">{said}</PortalRefusal>
      <div className="flex flex-wrap items-center gap-2" data-ways-out="">
        {result.outcome === "no_answer" ? (
          <Button variant="primary" data-way-out="try-again" onClick={props.onTryAgain}>
            {t("portal.payNow.tryAgain")}
          </Button>
        ) : null}
        {result.outcome === "declined" ? (
          <ButtonLink to={props.methodsTo} variant="primary" data-way-out="methods">
            {t("portal.payNowCheck.useAnother")}
          </ButtonLink>
        ) : null}
        <ButtonLink to={props.changeTo} variant="secondary" data-way-out="change">
          {t("portal.payNowCheck.change")}
        </ButtonLink>
      </div>
    </section>
  );
}

/**
 * `CWP-076` inside the signed-in shell.
 *
 * ⚠ **NO ACCOUNT ID IN THE ADDRESS** (B14 rule 31) and nothing else in it
 * either: the amount, the instrument and the idempotency key travel in ROUTER
 * STATE, so this address can be bookmarked and reloaded without leaking a
 * customer's payment into a log, a history entry or a `Referer` header. What a
 * reload gets is the wrong-turn card above, with a live door back.
 */
export function PayNowCheckPage(props: { client?: ApiClient }) {
  return (
    <PayNowShell client={props.client}>
      {(accountId) => <PayNowCheckView accountId={accountId} client={props.client} />}
    </PayNowShell>
  );
}
