// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-005 (EP-CWP-02) — paid: a reference to keep, and the offer
//           of a login. Screens: CWP-004 · wireframes/CWP-004.png
// Rules:    08-screen-layouts.md CWP-004 (T2, two cards ≈ 55/45: Stepper
//           ✓·✓·3 → left Card [kicker PAID · title *$142.18 received, thank
//           you* · KVList Reference / Paid / Against / Method · ButtonRow
//           ↓ Receipt · ✉ Email it to me] · right Card with a brand left rule
//           [title *Want this to be easier next time?* · two grey lines ·
//           KVList We already know / You would add · Set up a login →]) ·
//           BR-CWP-028 (every guest flow ends on a reference and offers to
//           send it) · BR-CWP-029 (enrolment attaches a password to a person
//           already on file) · BR-CWP-021 (never a person) · B14 rule 21
//           (`src/portal/` is on route-b-migrated.txt) · rule 31 (the
//           reference is the HUMAN one, never a row id) · rule 32 (one
//           sentence per section) · rule 33 (a refusal is five or six words) ·
//           rule 35 (the catalogue writes the words) · rule 36 (compose the
//           kit)
// Tests:    src/portal/guest/QuickPayDone.dom.test.tsx
// Impacts:  QuickPayCheck.tsx (the receipt it is handed) ·
//           06-backend/apps/portal/selectors.guest_payment_receipt ·
//           TrackAnything.tsx (the reload card's first door goes to CWP-012,
//           live since 2026-09-05 — US-CWP-005 TC-3)
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";

import type { GuestPaymentReceipt } from "../api/guestClient";
import { usePortalDate } from "../components/regional";
import { GuestPage } from "./GuestPage";
import {
  ButtonRow,
  Card,
  ErrandLink,
  HeldButton,
  KVList,
  Stepper,
  TwoEqual,
} from "../components/primitives";

/** The three steps `08-screen-layouts.md` draws across CWP-002 · 003 · 004. */
const STEP_KEYS = ["find", "check", "done"] as const;

/** The four brands `tokeniseCard` can name. ⚠ **A WORD IS NEVER THE SERVER'S**
 *  (B14 rule 35, and `DEF-CWP-3926` — two screens once printed a server's
 *  engineering prose onto a customer's home page): an unknown brand falls back
 *  to the generic word *card*, never to the raw code. */
const KNOWN_BRANDS: readonly string[] = ["visa", "mastercard", "amex", "card"];

function receiptFrom(state: unknown): GuestPaymentReceipt | null {
  if (typeof state !== "object" || state === null) {
    return null;
  }
  const candidate = (state as { receipt?: unknown }).receipt;
  if (typeof candidate !== "object" || candidate === null) {
    return null;
  }
  const receipt = candidate as Partial<GuestPaymentReceipt>;
  return typeof receipt.reference === "string" ? (receipt as GuestPaymentReceipt) : null;
}

/**
 * `CWP-004` — what a person keeps, and the one offer that costs nothing.
 *
 * ⚠ **THE OFFER OF A LOGIN IS MADE AND THE LOGIN IS NOT CREATED** (`US-CWP-005`
 * §1). This is *"the single best moment in the product to offer an account"* —
 * the visitor has just succeeded and the account is already identified — and
 * §1 is equally clear about what it must not do: it does not create the
 * credential silently, and it does **not withhold the receipt** until they take
 * it. So *Set up a login →* is an ordinary link to `/enrol`, which asks for the
 * one-time code like it asks everybody; TC-4 requires exactly that, *"does not
 * skip the one-time code because a payment just succeeded"*.
 *
 * ⚠ **THE OFFER IS UNCONDITIONAL AND THAT IS A DISCLOSURE DECISION.** A server
 * flag saying *this account has no login yet* would answer a question a
 * neighbour holding the bill has no business asking (`BR-CWP-021`), so nothing
 * on the receipt says whether one exists and `/enrol` protects itself.
 *
 * ⚠ **TWO CONTROLS ARE HELD AND EACH CARRIES `data-held-for`, WHICH IS THE
 * EXPIRY TEST HARD-WON LAW 2 ASKS FOR (`DEF-CWP-3925`).** The receipt DOCUMENT
 * is `US-CWP-005` TC-6's *"document class that already exists"* and no guest
 * route serves one yet; *email it to me* has no guest send. Both attributes are
 * asserted by name in the DOM test, so the day somebody builds either and takes
 * the attribute off, the suite goes red and names the control — a hold with no
 * such test is a promise nobody is keeping.
 *
 * ⚠ **AND WHEN AN ADDRESS WAS GIVEN AT STEP 2 THE SECOND CONTROL IS NOT DRAWN
 * AT ALL** — it is replaced by the FACT that the receipt went. A held button
 * over a thing that already happened is worse than no button.
 */
export function QuickPayDone() {
  const { t } = useTranslation();
  const location = useLocation();
  const receipt = receiptFrom(location.state);
  //: ⚠ **AND IT IS DRAWN `withTime`, IN THE TENANT'S ZONE** (`DEF-CWP-4197`).
  //: This screen printed `2026-09-06T03:59:13.769308+00:00` — a UTC instant
  //: with microseconds — on the one document a person keeps. `usePortalDate`'s
  //: own docstring names this failure: *the half of `IS-8` that made a payment
  //: taken at 7pm local show as the next day.* A receipt dated tomorrow is the
  //: thing that gets quoted back in a dispute.
  const asDate = usePortalDate();

  // ⚠ **A RELOAD IS A WRONG TURN, NOT AN ERROR** — `/pay/done` carries nothing
  // in its address on purpose, so a refreshed tab has no receipt to draw. The
  // screen says so in one sentence and offers two live doors back, by address.
  //
  // ⚠ **THE FIRST OF THEM WAS A STATED GAP UNTIL 2026-09-05 AND IS NOT ONE
  // ANY MORE.** This comment read *"until the `PAY-` series is trackable that
  // door is find the bill again, which is honest, and the gap is recorded
  // rather than papered over"* — and `selectors.TRACKABLE_SERIES` now names
  // the payment, so `US-CWP-005` TC-3 (*"the receipt is still reachable by
  // reference"*) has a real destination: `/track`.
  //
  // ⚠ **WHAT IS ON THE OTHER SIDE OF IT IS NARROWER THAN THIS RECEIPT AND
  // THAT IS DELIBERATE.** `US-CWP-010` TC-7 is explicit — a tracked payment
  // answers its status and its dates and *"⚠ **Not the amount** — the amount
  // is account data"*. The figure belongs on THIS screen, where the person
  // agreed to it ten seconds ago; it does not belong on a page anybody holding
  // a scrap of paper can reach a fortnight later.
  if (receipt === null) {
    return (
      <div data-screen="CWP-004">
        <Stepper steps={STEP_KEYS.map((key) => t(`portal.quickPay.step.${key}`))} current={3} />
        <Card testId="quick-pay-no-receipt">
          <PageHeader
            kicker={t("portal.quickPay.doneKicker")}
            title={t("portal.quickPay.noReceiptTitle")}
          />
          <p className="text-body leading-relaxed text-neutral-600" data-no-receipt="">
            {t("portal.quickPay.noReceiptBody")}
          </p>
          <div className="mt-3">
            <ButtonRow>
              {/* ⚠ **THE FIRST DOOR IS NEW AND THE HOLD ABOVE IT EXPIRED ON
                  2026-09-05.** This card offered one way on — *find the bill
                  again* — and said why: `US-CWP-005` TC-3 wants the receipt
                  reachable by reference and the `PAY-` series was not
                  trackable. It is now (`selectors.TRACKABLE_SERIES`), so the
                  reference somebody wrote down is the shortest way back and it
                  goes first. Asserted BY ADDRESS in the DOM test, which is what
                  makes this a door rather than a decoration. */}
              <ErrandLink label={t("portal.track.lookItUp")} to="/track" size="default" />
              {/* And the old one stays, because the two answer different
                  people: somebody who KEPT the reference tracks it, and
                  somebody who lost it with the tab has only the paper. */}
              <ErrandLink label={t("portal.quickPay.startAgain")} to="/pay" size="default" />
            </ButtonRow>
          </div>
        </Card>
      </div>
    );
  }

  const brand = receipt.method.brand ?? "card";
  const brandWord = t(
    `portal.quickPay.brand.${KNOWN_BRANDS.includes(brand) ? brand : "card"}`,
  );

  return (
    <div data-screen="CWP-004">
      <Stepper steps={STEP_KEYS.map((key) => t(`portal.quickPay.step.${key}`))} current={3} />
      <TwoEqual
        left={
          <Card testId="quick-pay-receipt">
            {/* ⚠ **THE FIGURE IS ON THE WRAPPER AS WELL AS IN THE SENTENCE.**
                *$142.18 received, thank you* is the catalogue's sentence (B14
                rule 35), so a test asserting the figure through the title would
                be asserting a TRANSLATION rather than a screen — and would go
                quiet in ten languages the day one of them was reworded. */}
            <div data-receipt-amount={receipt.amount.display ?? ""}>
              <PageHeader
                kicker={t("portal.quickPay.doneKicker")}
                title={t("portal.quickPay.doneTitle", { amount: receipt.amount.display })}
              />
            </div>
            <KVList
              rows={[
                {
                  key: "reference",
                  label: t("portal.quickPay.reference"),
                  // B14 rule 31 — `PAY-26-08841`, the human reference somebody
                  // reads down a telephone. Never a row id.
                  value: <span data-reference="">{receipt.reference}</span>,
                },
                {
                  key: "paid",
                  label: t("portal.quickPay.paidAt"),
                  value: <span data-paid-at={receipt.paid_at}>{asDate(receipt.paid_at, true)}</span>,
                },
                {
                  key: "against",
                  label: t("portal.quickPay.against"),
                  value: <span data-against="">{receipt.against}</span>,
                },
                {
                  key: "method",
                  label: t("portal.quickPay.method"),
                  value: (
                    // ⚠ The two FACTS sit on the element and the SENTENCE that
                    // joins them is the catalogue's (B14 rule 35) — *Visa
                    // ending 8812* reads differently in eleven languages and a
                    // test must not be asserting one of them.
                    <span
                      data-method={receipt.method.brand ?? "card"}
                      data-last-four={receipt.method.last_four ?? ""}
                    >
                      {t("portal.quickPay.methodLine", {
                        brand: brandWord,
                        lastFour: receipt.method.last_four ?? "",
                      })}
                    </span>
                  ),
                },
              ]}
            />
            <ButtonRow>
              <span data-held-for="US-CWP-005-receipt-document">
                <HeldButton
                  label={t("portal.quickPay.downloadReceipt")}
                  reason={t("portal.quickPay.receiptHeld")}
                />
              </span>
              {receipt.receipt_sent ? (
                <span className="text-body text-neutral-600" data-receipt-sent="">
                  {t("portal.quickPay.receiptSent")}
                </span>
              ) : (
                <span data-held-for="US-CWP-005-receipt-email">
                  <HeldButton
                    label={t("portal.quickPay.emailReceipt")}
                    reason={t("portal.quickPay.emailHeld")}
                  />
                </span>
              )}
            </ButtonRow>
          </Card>
        }
        right={
          // The wireframe's brand left rule, as a Tailwind utility — `portal/`
          // is on `route-b-migrated.txt`, so no stylesheet class is added
          // (B14 rule 21).
          <div className="border-l-4 border-l-accent" data-enrol-offer="">
            <Card testId="quick-pay-enrol-offer">
              <PageHeader
                title={t("portal.quickPay.enrolTitle")}
                rollup={t("portal.quickPay.enrolLead")}
              />
              <KVList
                rows={[
                  {
                    key: "we-know",
                    label: t("portal.quickPay.weAlreadyKnow"),
                    value: <span>{t("portal.quickPay.weAlreadyKnowValue")}</span>,
                  },
                  {
                    key: "you-add",
                    label: t("portal.quickPay.youWouldAdd"),
                    value: <span>{t("portal.quickPay.youWouldAddValue")}</span>,
                  },
                ]}
              />
              <div className="mt-3">
                {/* LIVE, and it goes to `/{tenant}/portal/enrol` — `CWP-016`,
                    where the one-time code is asked for like it is asked of
                    everybody (`US-CWP-005` TC-4). */}
                <ErrandLink
                  label={t("portal.quickPay.setUpLogin")}
                  to="/enrol"
                  size="default"
                />
              </div>
            </Card>
          </div>
        }
      />
    </div>
  );
}

/** `CWP-004` at `/{tenant}/portal/pay/done`. Composes `GuestPage` for the
 *  reason `QuickPayPage.tsx` gives: `CR-068` R8 puts the holding-page check
 *  there, so every guest route inherits it. */
export function QuickPayDonePage(props: { client?: ApiClient }) {
  return (
    <GuestPage client={props.client}>
      <QuickPayDone />
    </GuestPage>
  );
}
