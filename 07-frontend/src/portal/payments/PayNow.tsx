// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-045 (EP-CWP-09) — pay now, and where the payment will land,
//           BEFORE it commits. Screen: CWP-038 (blueprint 35 `Pay now`, p64)
// Change:   CR-085 step 2 lane 6 — **this screen is now the FIRST OF THREE.**
//           PO 2026-09-11, verbatim: *"it should be 3 screens - confirmed"* and
//           *"ii). Your ruling was about the shape, not the addresses."* The
//           commit and the receipt left this file for `CWP-076` at
//           `/pay-now/check` and `CWP-077` at `/pay-now/done`; no guest address
//           moved.
// Rules:    BR-CWP-058 (the *where it will go* panel, before the commit) ·
//           BR-CWP-056 / CR-068 R3 (a control that may not be used is VISIBLE,
//           DISABLED and carries its reason — never hidden, never live-but-
//           inert) · BR-CWP-057 (a brand and four digits, never a card number)
//           · BR-CWP-047 (nothing here is cached) · R-10 (bad news carries its
//           way out) · R-22 (loading, empty and failed are three SENTENCES) ·
//           B14 rule 2 (one page head, every screen) · rule 20 (ONE table
//           type) · rule 21 (Tailwind utilities, no stylesheet class) · rule 31
//           (no database id is a visible value) · rule 32 (a description budget)
//           · rule 33 (a refusal is five or six words) · rule 35 (each catalogue
//           in its own language) · rule 36 (compose the kit) · CLAUDE.md hard
//           rule 2 (2 dp displayed) · hard rule 4 (a payment cannot be edited)
// Defects:  DEF-CWP-4866 (a refusal on `title=` only) · DEF-CWP-4867 (*what
//           this will do* promising a payment over a dead button) ·
//           DEF-CWP-4869 (a live commit over a priced panel for another amount)
// Tests:    src/portal/payments/PayNow.dom.test.tsx
// Impacts:  src/portal/api/payNowClient.ts · src/portal/payments/PayNowPage.tsx
//           · src/portal/payments/PayNowCheck.tsx (the screen it hands on to)
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import {
  Card,
  ConsequenceBox,
  ErrandLink,
  FormField,
  MiniTable,
  RadioList,
  SectionTitle,
  Stepper,
  TextInput,
  TotalRow,
  TwoCol,
  usePortalPath,
  WizardFooter,
} from "../components/primitives";
import { PortalScreen, PortalState } from "../components/states";
import { Button } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { formatMoney } from "../signin/Enrol";
import {
  getPayNow,
  previewPayment,
  type PortalInstrument,
  type PortalLanding,
  type PortalPayNow,
  type PortalPayPreview,
} from "../api/payNowClient";
import { HeldCommit } from "../components/heldCommit";
import { isAboveZero, type PayNowHandoff } from "./payNowFlow";
import { Announced } from "../components/a11y";

/** The three amounts `CWP-038` offers. `another` is the one that makes the
 *  panel matter — a partial payment is the case a customer can be surprised by. */
type Choice = "whole" | "bill" | "another";

/**
 * The wireframe's THIRD payment radio — *A different card or bank account*
 * (`DEF-CWP-3972`, wireframe `P24`, delta row 38.4).
 *
 * ⚠ **IT IS A SENTINEL AND NOT AN INSTRUMENT ID, AND THAT IS THE WHOLE FIX.**
 * Until 2026-09-05 this screen listed SAVED instruments and nothing else, so a
 * customer who had never saved one met `portal.payNow.noMethods` — *"Cards and
 * bank accounts you save will show here."* — over a Pay button held with
 * *"Add a card or bank account."*, **and no control on the screen added one.**
 * Both halves were individually correct (B14 rule 17 asks an empty state to
 * name what fills it; `BR-CWP-056` asks a hold to carry its reason), which is
 * exactly why it survived every check: nothing asks whether the action a
 * refusal INSTRUCTS is reachable from where the person is standing.
 *
 * ⚠ **CHOOSING IT DRAWS A DOOR, BY ADDRESS, TO `CWP-039`** — which is routed,
 * live and is the screen that adds one. A refusal that names an action is a
 * promise the action is reachable; this is that promise kept.
 *
 * The leading `_` cannot collide with a server id: instrument ids are UUIDs.
 */
const A_DIFFERENT_ONE = "_different";

/** How long a typed amount settles before it is priced. A keystroke is not a
 *  question for the server; a pause is. */
const PRICE_AFTER_MS = 250;

/**
 * `CWP-038` — **how much, and from where.** Blueprint 35.
 *
 * ⚠ **THE COMMIT IS NOT ON THIS SCREEN ANY MORE AND ITS ABSENCE IS THE
 * RULING** (PO 2026-09-11: *"it should be 3 screens - confirmed"*). This screen
 * chooses; `CWP-076` is *"the last screen at which anything can be changed"*
 * and is where money moves; `CWP-077` is the receipt. The drawing's own
 * argument for the split is that *"the pay screen is a form; this is a
 * confirmation… the total, the fee and the date are read once, deliberately,
 * rather than glanced at while choosing a card"*, and the PO's is plainer still
 * — a payment is the one journey where somebody wants a page they can stop on,
 * go back to and screenshot.
 *
 * ⚠ **SO THE BUTTON HERE DOES NOT SAY *Pay*.** The drawing puts `Pay $191.00`
 * on screen 35 and again on screen 36, and once 36 exists the first of those is
 * a button that says it takes money and does not (hard-won law 1, in a piece of
 * copy a customer acts on). The drawing's own rule — *"one button, and it names
 * the figure… never a bare Continue"* — is kept: the figure stays on the
 * control and the VERB is what the control actually does. The word *Pay* is
 * reserved for the one control in this product that takes money.
 *
 * ⚠ **THE *WHERE IT WILL GO* PANEL IS NOT DECORATION** (`BR-CWP-058`, and the
 * story says so in capitals). Payments are allocated by a rule the utility
 * configures, so a customer paying part of what they owe needs to see which bill
 * it lands on **before** they press anything — because afterwards the payment
 * row cannot be edited, only reversed (hard rule 4).
 *
 * ⚠ **NOT ONE FIGURE ON THIS SCREEN IS COMPUTED HERE.** `$142.18` less `$40.00`
 * is `$102.18` and the SERVER says so, out of the same
 * `allocation.allocate_payment` that will apply the money a second later. A
 * subtraction written in this file would be a second answer to *where did my
 * payment go*, and the customer would be reading the one the receipt does not
 * say. ⚠ **The one exception was the BUTTON LABEL and it cost `DEF-CWP-4869`** —
 * see the effect below.
 *
 * ⚠ **THE HELD CONTROL IS THE SERVER'S VERDICT, NOT THIS FILE'S GUESS**
 * (`BR-CWP-056`). Whether the utility has connected a processor, whether the
 * account is cash-only and whether this login may pay are facts the browser does
 * not hold. `held_reason` arrives as a CODE and the eleven catalogues write the
 * sentence in their own language (rule 35), each of them five or six words
 * (rule 33) — and **it is now READ ALOUD on the screen** rather than hidden on a
 * `title` attribute no phone can show (`DEF-CWP-4866`, `HeldCommit`).
 */
export function PayNowView(props: { accountId?: string | null }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const path = usePortalPath();
  const accountId = props.accountId ?? null;
  const [screen, setScreen] = useState<PortalPayNow | null>(null);
  const [failed, setFailed] = useState(false);
  // R-10's way out of the failed card, and it is a REAL one: bumping this
  // re-runs the read below. A `Try again` wired to nothing is `EmptyList`'s own
  // `onCta: () => undefined` defect (`DEF-MET-4764`) — a control that looks
  // pressable, is pressable, and does nothing.
  const [attempt, setAttempt] = useState(0);
  // ⚠ **A REFUSED PREVIEW DOES NOT DESTROY THE SCREEN, WHICH IS WHY IT IS NOT
  // `failed`.** `failed` swaps the whole page for *"We could not read this"*;
  // a refused preview leaves the amount, the method and the radios exactly
  // where the customer left them and says so beside the control — the posture
  // `AskForPlan` already takes for the same shape of refusal.
  const [choice, setChoice] = useState<Choice>("whole");
  const [typed, setTyped] = useState("");
  const [method, setMethod] = useState<string | null>(null);
  const [panel, setPanel] = useState<PortalPayPreview | null>(null);
  // ⚠ **THE KEY LIVES ACROSS THE WHOLE JOURNEY AND IS NEVER RE-MINTED HERE**
  // (TC-7). It is the preview's, kept in state, handed to `CWP-076` and
  // re-presented on every attempt there — including the attempt after a
  // timeout, which is the only one it exists for.
  const [key, setKey] = useState<string | null>(null);
  const [seeFailed, setSeeFailed] = useState(false);

  useEffect(() => {
    if (accountId === null) return;
    let live = true;
    getPayNow(accountId)
      .then((answer) => {
        if (!live) return;
        setScreen(answer);
        // ⚠ **A CUSTOMER WITH NOTHING SAVED LANDS ON THE THIRD RADIO, NOT ON
        // NOTHING** (`DEF-CWP-3972`). It is the only option they have, so
        // pre-selecting it is what puts the door to `CWP-039` on screen the
        // moment the page opens rather than after a click they had no reason
        // to make.
        const first = answer.instruments.find((one) => one.selectable);
        setMethod(first ? first.id : A_DIFFERENT_ONE);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [accountId, attempt]);

  // ⚠ **HOISTED ABOVE THE EARLY RETURNS BECAUSE A HOOK CANNOT SIT BEHIND
  // ONE.** `amountFor` needs the screen, so it answers `null` until the read
  // lands — which is also exactly what the standing preview below wants:
  // nothing to price yet.
  const amount = screen === null ? null : amountFor(choice, typed, screen);
  // ⚠ **`amount !== null` WAS THE WHOLE TEST UNTIL `DEF-CWP-<pay-now-zero>`
  // (2026-09-05), AND `"0.0000"` IS NOT NULL.** A customer who owes nothing
  // opens this screen — they are exactly the person who opens it to check —
  // and *Everything you owe · $0.00* is ALREADY selected. The server correctly
  // refuses `422 VAL-003`, so the refusal is made LOCALLY and nothing is asked.
  const priceable = amount !== null && isAboveZero(amount);

  /**
   * ⚠ **THE PANEL IS STANDING, NOT EARNED** (`DEF-CWP-3970`, delta row 38.1).
   *
   * The wireframe (`P24`) draws `WHERE IT WILL GO` as a **standing right-rail
   * panel, visible from the moment the screen opens**, and its own design note
   * says why: payments are allocated by a rule the utility configures, so
   * somebody paying part of a balance has to see which bill it lands on
   * *before* they commit. We had once taken the thing that INFORMS the decision
   * and made it a gate the decision must pass through.
   *
   * ⚠ **THE PREVIEW WRITES NOTHING, WHICH IS WHAT MAKES THIS SAFE TO FIRE ON
   * ITS OWN.** `pay_now_seam.preview` states it in its own docstring and the
   * response carries `writes: []` so a caller can prove it.
   *
   * ⚠ **THE PANEL IS CLEARED THE INSTANT THE AMOUNT MOVES, AND THAT ONE LINE
   * IS `DEF-CWP-4869`.** Typing into *Another amount* changed the button label
   * immediately — it is computed locally from `amount` — while `panel` kept the
   * PREVIOUS preview for at least `PRICE_AFTER_MS` plus a round trip. Measured
   * on screen simultaneously on 2026-09-11: button `Pay $40.00 ✓`, *"Takes
   * $191.00 … Clears bill BL-2608-0141 in full"*, rail `PAYING $191.00 / LEFT
   * OWING $0.00`. **And the commit stayed live across that window**, carrying
   * the previous amount's `idempotency_key` — the one string hard rule 6 makes
   * load-bearing. A panel describing a payment nobody is about to make is worse
   * than no panel, so the stale one goes before the new one is asked for.
   *
   * ⚠ **THE KEY IS RE-SENT, NEVER RE-MINTED** (TC-7). The seam answers
   * `key or mint()`, so every re-price after the first carries the string the
   * first one returned.
   */
  useEffect(() => {
    // Whatever was priced was priced for a DIFFERENT amount. It stops being
    // drawn now, not when its replacement arrives.
    setPanel(null);
    if (accountId === null || !priceable || amount === null) {
      setSeeFailed(false);
      return;
    }
    let live = true;
    // A typed amount changes on every keystroke; pricing each one would ask
    // the server to allocate `4`, `40`, `40.` and `40.5` on the way to `40.50`.
    const timer = setTimeout(() => {
      previewPayment(accountId, {
        amount,
        ...(key === null ? {} : { idempotency_key: key }),
      })
        .then((answer) => {
          if (!live) return;
          setPanel(answer);
          setKey(answer.idempotency_key);
          setSeeFailed(false);
        })
        // ⚠ **A REFUSED PREVIEW IS DRAWN, NEVER SWALLOWED.** An unhandled
        // rejection fails no assertion in `vitest` and changes nothing in a
        // screenshot, so only a browser listening for `pageerror` ever saw it.
        .catch(() => {
          if (!live) return;
          setPanel(null);
          setSeeFailed(true);
        });
    }, PRICE_AFTER_MS);
    return () => {
      live = false;
      clearTimeout(timer);
    };
    // `key` is deliberately not a dependency: it is re-read from the closure of
    // whichever render last ran this effect, and adding it would re-price the
    // moment the first preview answered.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, amount, priceable]);

  // ⚠ **THE HEAD IS BUILT ONCE, ABOVE THE BRANCHES, AND RENDERS ON EVERY ONE
  // OF THEM** (`DEF-CWP-4926`, and B14 rule 2). This screen had NO head at all
  // — no kicker, no `<h1>` — while blueprint 35 draws `‹ Payments` over *Pay
  // your bill*. A slow or failed read must not also throw away the title, the
  // screen id every rendered check selects on, and the only door out.
  const head = (
    <PageHeader
      kicker={t("portal.money.kicker")}
      title={t("portal.payNow.title")}
      backTo={{ label: t("portal.money.title"), to: path("/payments"), testId: "pay-now-back" }}
    />
  );

  // ⚠ **THREE SENTENCES FOR THREE STATES, NOT THREE PICTURES** — R-22 as the PO
  // ruled it (*"differntiate it using text message"*). The failed card also
  // carries its way out, which is R-10: *"the thing they can do about it must
  // be on that same screen, next to the message"*.
  if (failed) {
    return (
      <PortalScreen screen="CWP-038" head={head}>
        <PortalState
          kind="failed"
          testId="pay-now-failed"
          sentence={t("portal.payNow.couldNotRead")}
          waysOut={[
            {
              label: t("portal.payNow.tryAgain"),
              testKey: "retry",
              onClick: () => {
                setFailed(false);
                setAttempt((n) => n + 1);
              },
            },
            { label: t("portal.money.title"), testKey: "payments", to: path("/payments") },
          ]}
        />
      </PortalScreen>
    );
  }
  if (screen === null || accountId === null) {
    return (
      <PortalScreen screen="CWP-038" head={head}>
        <PortalState kind="loading" testId="pay-now-reading" sentence={t("portal.payNow.reading")} />
      </PortalScreen>
    );
  }

  // ⚠ **A CHOSEN INSTRUMENT, NOT MERELY A CHOSEN RADIO.** `A_DIFFERENT_ONE`
  // is a destination and not a way to pay, so it must not satisfy *ready* —
  // otherwise the third radio would be a live button over nothing at all,
  // which is `DEF-CWP-3925` wearing the opposite face.
  const chosen = method === null || method === A_DIFFERENT_ONE ? null : method;
  const ready = priceable && screen.can_pay && chosen !== null && panel !== null && key !== null;

  function onwards() {
    if (amount === null || chosen === null || key === null) return;
    const handoff: PayNowHandoff = { amount, instrumentId: chosen, idempotencyKey: key };
    // ⚠ **ROUTER STATE, NEVER THE ADDRESS.** An amount and an instrument id in
    // a URL end up in access logs, in history and in a `Referer` header, and
    // an instrument id in an address bar is a database id on screen (rule 31).
    navigate(path("/pay-now/check"), { state: handoff });
  }

  return (
    <PortalScreen screen="CWP-038" head={head}>
      <Stepper
        steps={[
          t("portal.payNow.step.choose"),
          t("portal.payNow.step.check"),
          t("portal.payNow.step.done"),
        ]}
        current={1}
      />
      <TwoCol
        main={
          <Card testId="pay-now">
            <SectionTitle>{t("portal.payNow.amountTitle")}</SectionTitle>
            <RadioList
              name={t("portal.payNow.amountTitle")}
              value={choice}
              options={[
                {
                  value: "whole",
                  label: t("portal.payNow.wholeBalance", {
                    amount: formatMoney(screen.balance, screen.currency),
                  }),
                },
                ...(screen.bills.length > 0
                  ? [
                      {
                        value: "bill",
                        label: t("portal.payNow.justThisBill", {
                          number: screen.bills[0].number,
                          amount: formatMoney(
                            screen.bills[0].open_balance ?? "0",
                            screen.currency,
                          ),
                        }),
                      },
                    ]
                  : []),
                { value: "another", label: t("portal.payNow.anotherAmount") },
              ]}
              onChange={(value) => setChoice(value as Choice)}
            />
            {choice === "another" ? (
              // ⚠ `FormField` AND NOT A BARE INPUT: the kit's field is what
              // supplies the `<label for>` (B14 rule 36), and a money box with
              // no label is a box a screen reader announces as nothing.
              <FormField id="pay-amount" label={t("portal.payNow.anotherAmount")} required>
                <TextInput id="pay-amount" value={typed} onChange={setTyped} />
              </FormField>
            ) : null}

            <SectionTitle>{t("portal.payNow.methodTitle")}</SectionTitle>
            <Methods
              rows={screen.instruments}
              current={method}
              onChoose={setMethod}
              wantsAnother={method === A_DIFFERENT_ONE}
            />

            {/* ⚠ **`WHAT THIS WILL DO` NO LONGER PROMISES A PAYMENT OVER A DEAD
                BUTTON — `DEF-CWP-4867`.** It was drawn on `panel !== null`
                alone and never asked whether the payment could happen, so an
                account with no provider connected read *"Takes $191.00 from
                Bank account ····4417. Clears bill BL-2608-0141 in full. Emails
                you a receipt."* over a control that could not be pressed and,
                until `DEF-CWP-4866`, gave no reason. A confident promise, a
                dead button and no explanation is the worst of the three
                possible screens. The consequence now stands or falls with the
                commit it describes. */}
            {panel !== null && screen.can_pay ? (
              <ConsequenceBox
                heading={t("portal.payNow.consequenceHeading")}
                bullets={consequences(t, screen, panel, chosen)}
              />
            ) : null}

            {seeFailed ? (
              <Announced tone="error" className="text-body font-semibold text-danger-700" data-see-refused="">
                {t("portal.payNow.couldNotRead")}
              </Announced>
            ) : null}

            {/* ⚠ **THE BUTTON ROW IS AT THE BOTTOM LEFT OF THE CARD** (delta
                row 38.5). It floated outside the card, top right, with no
                `Back` at all — so the one commit on this screen sat away from
                everything it was about, and a customer who had changed their
                mind had nowhere to press.

                ⚠ **`HeldCommit` AND NOT `CommitButton` — `DEF-CWP-4866`.** The
                kit renders a refusal on `title=` and nowhere else; on a phone
                that sentence does not exist. `data-pay-control` is kept exactly
                where it was so every existing test and walkthrough still finds
                this control by the same hook. */}
            {/* `DEF-CWP-9164` — Back on the LEFT, the commit on the RIGHT. */}
            <WizardFooter
              back={
                // ⚠ **NOT THE DANGER TIER AND NOT A PRIMARY** (r10 rule 6, B14
                // rule 2's one-primary law): leaving a screen is neither
                // destructive nor the thing to press.
                <Button
                  variant="secondary"
                  size="sm"
                  data-back=""
                  onClick={() => navigate(-1)}
                >
                  {t("portal.payNow.back")}
                </Button>
              }
              forward={
                <HeldCommit
                  label={t("portal.payNow.checkFirst", {
                    amount: formatMoney(amount ?? "0", screen.currency),
                  })}
                  working={false}
                  ready={ready}
                  reason={heldSentence(t, screen, panel, amount, method)}
                  onClick={onwards}
                />
              }
            />
          </Card>
        }
        rail={
          <>
            {/* ⚠ **THE PANEL `BR-CWP-058` IS ABOUT, AND IT STANDS.** It is
                drawn as soon as the server has priced an amount — which is on
                open, because *Everything you owe* is already selected. A table
                of dashes would be a promise about money nobody has worked out
                yet, so an unpriceable amount draws nothing rather than a
                skeleton. */}
            {panel !== null ? <WhereItWillGo panel={panel} order={screen.order} /> : null}
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
    </PortalScreen>
  );
}

/**
 * The rail table — **bill, owing, paying**, and what each bill owes afterwards.
 *
 * ⚠ **`owing_after` IS THE COLUMN THE WHOLE SCREEN IS FOR.** The wireframe draws
 * three columns; the fourth is `US-CWP-045` TC-4's own acceptance sentence
 * (*"afterwards that bill reads owing $102.18"*), and a customer who can only
 * see it afterwards has been told at the one moment they cannot act on it.
 */
export function WhereItWillGo(props: { panel: PortalPayPreview; order: string }) {
  const { t } = useTranslation();
  const { panel } = props;
  return (
    <Panel as="aside" title={t("portal.payNow.panelTitle")}>
      {panel.lands_on.length === 0 ? (
        <p className="text-body text-neutral-600" data-lands-none="">
          {t("portal.payNow.landsNowhere")}
        </p>
      ) : (
        <MiniTable
          caption={t("portal.payNow.panelCaption")}
          columns={[
            { key: "bill", label: t("portal.payNow.colBill") },
            { key: "owing", label: t("portal.payNow.colOwing"), align: "right" as const },
            { key: "paying", label: t("portal.payNow.colPaying"), align: "right" as const },
            { key: "after", label: t("portal.payNow.colAfter"), align: "right" as const },
          ]}
          rows={panel.lands_on.map((row: PortalLanding, index: number) => ({
            // B14 rule 31 — the BL- number printed on the bill, never a row id.
            key: row.number,
            cells: {
              bill: <span data-bill={index}>{row.number}</span>,
              owing: (
                <span className="tabular-nums">{formatMoney(row.owing, panel.currency)}</span>
              ),
              paying: (
                <span className="tabular-nums" data-paying={index}>
                  {formatMoney(row.paying, panel.currency)}
                </span>
              ),
              after: (
                <span className="tabular-nums" data-after={index}>
                  {formatMoney(row.owing_after, panel.currency)}
                </span>
              ),
            },
          }))}
        />
      )}
      <TotalRow
        label={t("portal.payNow.totalPaying")}
        value={formatMoney(panel.amount, panel.currency)}
        testKey="paying"
      />
      {/* ⚠ **THE FOOTER STATES THE TENANT'S RULE, READ FROM THE SERVER.** A
          sentence typed here would go on saying *oldest first* on the day a
          utility configured something else. */}
      <p className="mt-2 text-base text-neutral-600" data-order={props.order}>
        {t(`portal.payNow.order.${props.order}`)}
      </p>
    </Panel>
  );
}

/**
 * The saved methods — **a brand and four digits** (`BR-CWP-057`).
 *
 * ⚠ **AN EXPIRED CARD IS LISTED AND CANNOT BE CHOSEN, WITH ITS REASON ON IT.**
 * `US-CWP-046` TC-6. Removing it from the list would leave a customer wondering
 * where their card went; a live-looking radio that fails on submit is worse.
 */
function Methods(props: {
  rows: PortalInstrument[];
  current: string | null;
  onChoose: (id: string) => void;
  wantsAnother: boolean;
}) {
  const { t } = useTranslation();
  const saved = props.rows.filter((one) => one.selectable);
  return (
    <div data-methods="">
      {props.rows.length === 0 ? (
        // B14 rule 17 — a sentence naming what will fill it, never a row of
        // dashes. ⚠ **IT IS NOW A LEAD-IN AND NOT THE WHOLE SECTION.** On its
        // own it was a dead end: it named what would fill the list and the
        // screen offered no way to fill it (`DEF-CWP-3972`).
        <p className="text-body text-neutral-600" data-methods-empty="">
          {t("portal.payNow.noMethods")}
        </p>
      ) : null}
      <RadioList
        name={t("portal.payNow.methodTitle")}
        value={props.current}
        options={[
          ...saved.map((one) => ({
            // ⚠ THE LABEL IS WHAT A PERSON RECOGNISES. The id is the VALUE and
            // is never rendered (B14 rule 31).
            value: one.id,
            label: one.label,
            // ⚠ THE STATUS WORD IS THE INLINE HINT `RadioList` DRAWS AFTER
            // `·` — *VERIFIED* on a bank mandate the utility has proved, which
            // is the one the wireframe puts a success chip beside.
            hint: one.status === "verified" ? t("portal.payNow.verified") : undefined,
          })),
          // ⚠ **THE WIREFRAME'S THIRD RADIO** (`P24`, delta row 38.4). It is
          // drawn whether or not anything is saved, because it is the option a
          // customer with nothing saved has — and the only one.
          { value: A_DIFFERENT_ONE, label: t("portal.payNow.aDifferentOne") },
        ]}
        onChange={props.onChoose}
      />
      {props.rows
        .filter((one) => !one.selectable)
        .map((one) => (
          <p key={one.id} className="py-1.5 text-body text-neutral-600" data-method-held={one.id}>
            {one.label} · {t(`portal.payNow.held.${one.held_reason}`)}
          </p>
        ))}
      {/* ⚠ **THE DOOR THAT MAKES THE REFUSAL TRUE** (`DEF-CWP-3972`). The
          control is held with *"Add a card or bank account."*; this is where a
          person does that. `CWP-039` is routed and live, so it is a LINK and
          never a `HeldButton` — a held control over a live screen is the
          `DEF-CWP-3925` shape, and this product has already paid for eight of
          those. The address is asserted in the DOM test. */}
      {props.wantsAnother ? (
        <div className="mt-2" data-add-a-method="">
          <ErrandLink label={t("portal.payNow.addAMethod")} to="/payment-methods" />
        </div>
      ) : null}
    </div>
  );
}

/**
 * What the customer is about to do, in their own words.
 *
 * ⚠ **EVERY FIGURE IS THE SERVER'S.** The story's box reads *takes `$142.18`
 * from Chase `••••4021` · clears the August bill in full · emails you a
 * receipt*, and each of those three is a fact off the preview rather than a
 * sentence assembled from a subtraction here.
 */
export function consequences(
  t: (key: string, options?: Record<string, unknown>) => string,
  screen: PortalPayNow,
  panel: PortalPayPreview,
  method: string | null,
): string[] {
  const instrument = screen.instruments.find((one) => one.id === method);
  const cleared = panel.lands_on.filter((one) => one.owing_after === "0.0000");
  return [
    // ⚠ **NO METHOD, NO BULLET** (`DEF-CWP-3971`). `portal.payNow.consequence.
    // takes` is *"Takes {{amount}} from {{method}}."* and it was written
    // whether or not anything had been chosen, so `{{method}}` interpolated to
    // nothing and the sentence on the panel that tells a customer what is about
    // to happen to their money read **"Takes $155.45 from ."** — ending on a
    // bare full stop, in all eleven languages.
    //
    // ⚠ **EVERY CHECK PASSED OVER IT.** The key exists, the parity gate is
    // green, `tsc` is green, and a `toContain("Takes")` assertion passes on the
    // broken string. Only a person reading the whole sentence can see that it
    // names nothing — which is why the test added with this fix asserts the
    // WHOLE sentence and, for the empty case, asserts the bullet's ABSENCE.
    ...(instrument
      ? [
          t("portal.payNow.consequence.takes", {
            amount: formatMoney(panel.amount, panel.currency),
            method: instrument.label,
          }),
        ]
      : []),
    cleared.length > 0
      ? t("portal.payNow.consequence.clears", { number: cleared[0].number })
      : t("portal.payNow.consequence.partly", {
          number: panel.lands_on.length > 0 ? panel.lands_on[0].number : "",
          amount: formatMoney(
            panel.lands_on.length > 0 ? panel.lands_on[0].owing_after : "0",
            panel.currency,
          ),
        }),
    t("portal.payNow.consequence.receipt"),
    // ⚠ **HARD RULE 4, SAID OUT LOUD BEFORE THE COMMIT.** A payment cannot be
    // edited afterwards, only reversed — which is exactly why the panel above
    // exists, and it is cheaper to say here than to explain on the telephone.
    t("portal.payNow.consequence.cannotEdit"),
  ];
}

/**
 * The words on a held control — the SERVER's reason, or the local one.
 *
 * ⚠ **THE ZERO CASE AND THE NOTHING-TYPED CASE ARE DIFFERENT SENTENCES.**
 * *"Choose an amount first."* is a lie to someone whose only choice is
 * *Everything you owe · $0.00* and who has already chosen it. `BR-CWP-056`
 * asks for the reason, not for a reason.
 *
 * ⚠ **AND *"Add a card or bank account."* IS A TRUE SENTENCE** — the screen
 * carries the door (`DEF-CWP-3972`). Six words, B14 rule 33.
 */
export function heldSentence(
  t: (key: string, options?: Record<string, unknown>) => string,
  screen: PortalPayNow,
  panel: PortalPayPreview | null,
  amount: string | null,
  method: string | null,
): string {
  if (screen.held_reason !== null) return t(`portal.payNow.held.${screen.held_reason}`);
  if (amount === null) return t("portal.payNow.heldNoAmount");
  if (!isAboveZero(amount)) return t("portal.payNow.amountMustBePositive");
  if (method === null || method === A_DIFFERENT_ONE) {
    return t("portal.payNow.held.no_saved_payment_method");
  }
  if (panel === null) return t("portal.payNow.pricing");
  return "";
}

/**
 * The figure to pay, as a STRING — never a number.
 *
 * ⚠ **NO ARITHMETIC AND NO `parseFloat`** (CLAUDE.md hard rule 2). Money travels
 * as a string beside its currency and the browser must not turn it into a
 * binary float on the way back: `$292.87` becoming `292.87000000000003` is a
 * payment nobody can reproduce. The only validation here is *did they type
 * digits*; the server decides everything else.
 */
function amountFor(choice: Choice, typed: string, screen: PortalPayNow): string | null {
  if (choice === "whole") return screen.balance;
  if (choice === "bill") {
    return screen.bills.length > 0 ? screen.bills[0].open_balance : null;
  }
  const cleaned = typed.trim();
  if (cleaned === "" || !/^\d+(\.\d{1,4})?$/.test(cleaned)) return null;
  return cleaned;
}
