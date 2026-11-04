// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-037 (EP-CWP-07) — *"your final bill, where the deposit comes
//           back."* Screen: CWP-032 (blueprint `P18`)
// Defects:  DEF-CWP-3962 (this screen's *Query this reading* was held over
//           CWP-055, which is live — the fourth rotted hold in a week) ·
//           DEF-CWP-4006 (T4 is `TwoEqual`; this composed `TwoCol`, which is
//           62/35 and puts a peer panel in a rail slot)
// Rules:    BR-CWP-048 (a negative final balance is a REFUND, never a carried
//           credit) · BR-CWP-049 (the deposit and its accrued interest are
//           settled here) · BR-CWP-056 (held WITH its reason) · B14 rule 21 ·
//           rule 31 (no database id on screen) · rule 32 (one sentence per
//           section) · rule 33 · rule 35 · rule 36 (compose the kit) ·
//           CLAUDE.md hard rule 2 (money displays at 2 dp) · CR-085 task (c),
//           wireframe s24: the money is the HEADLINE (*"that is what they came
//           for"*) and the printed bill has a door
// Tests:    src/portal/bills/FinalBill.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getFinalBill`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

import {
  Card,
  ConsequenceBox,
  ErrandLink,
  HeldButton,
  KVList,
  KpiTile,
  SectionTitle,
  TotalRow,
  TwoEqual,
} from "../components/primitives";
import { usePortalDate } from "../components/regional";
import { formatMoney } from "../signin/Enrol";
import { getFinalBill, type PortalFinalBillView } from "../api/portalClient";

/**
 * `CWP-032` — settling up on the way out.
 *
 * ⚠ **THE SIGN IS THE SERVER'S AND THERE IS NO `Math.abs` ON THIS SCREEN.**
 * `$63.40 − $150.00 − $3.20 = −$89.80`, and a negative remainder is drawn as
 * *we owe you `$89.80`* by choosing a SENTENCE, never by stripping a minus.
 * The two directions are two different screens: one offers a Pay control, the
 * other explains where the money is going and when.
 *
 * ⚠ **IT IS A REFUND AND NOT A CREDIT** (`BR-CWP-048`). There is no next bill
 * to carry a credit to, and the word matters to a customer deciding whether to
 * chase us. The server names the path; this screen renders the word for it.
 *
 * ⚠ **AN ACCOUNT WITH NO DEPOSIT HAS NO DEPOSIT LINES AT ALL** (TC-6) — not
 * `$0.00`, which reads as *we took nothing from you* rather than *there is
 * nothing here*. `CWP-065`'s own panel draws the same distinction, and the two
 * screens quote the same figures because both read one implementation of them.
 *
 * ⚠ **AND THE LAST CHANCE TO QUERY THE CLOSING READING IS HERE, WITH ITS
 * CLOSING TIME SAID OUT LOUD.** Once the account settles a correction is a much
 * slower business; the control does not simply vanish, it is replaced by the
 * sentence that explains why (`BR-CWP-056`'s posture on a control that may no
 * longer be used).
 */
export function FinalBillView(props: { accountId: string }) {
  const { t } = useTranslation();
  // ⚠ **FOUR MACHINE DATES REACHED A CUSTOMER HERE** (`DEF-CWP-4193`) — the
  // period sentence, *Service to*, *Deposit held since* and the closing
  // reading's *Taken on*. They came straight off the wire as `2026-09-17`, on
  // the last screen a leaving customer ever opens. `usePortalDate` renders the
  // TENANT's own format and is what every other portal screen composes; two of
  // the four sit inside interpolated sentences, which is why a fix aimed at
  // date COLUMNS would not have reached them (`DEF-CWP-4172`'s distinction).
  const showDate = usePortalDate();
  // ⚠ `undefined` IS *STILL READING* AND IS NOT A THIRD STATE FOR *NO BILL*.
  // A final bill's absence is `view.bill === null`, which the server states;
  // conflating the two would draw the loading sentence over an account that
  // simply is not leaving.
  const [view, setView] = useState<PortalFinalBillView | undefined>(undefined);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    getFinalBill(props.accountId)
      .then((answer) => {
        if (live) setView(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [props.accountId]);

  // ⚠ **THE HEAD IS BUILT ONCE AND RENDERS ON EVERY BRANCH, LOADING INCLUDED**
  // (`DEF-CWP-4000`; audit D1, delta X4/X5) — the shared
  // `components/PageHeader.tsx`, never a second one. The drawing's kicker here
  // is MOVING OUT rather than BILLS: this screen is the closing bill, and the
  // word a customer is looking for is the situation, not the document.
  const head = (
    <PageHeader kicker={t("portal.kicker.movingOut")} title={t("portal.finalBill.title")} />
  );

  if (failed) {
    return (
      <div data-screen="CWP-032">
        {head}
        <Card testId="final-bill">
          <p className="text-body text-neutral-600">{t("portal.finalBill.couldNotRead")}</p>
        </Card>
      </div>
    );
  }
  if (view === undefined) {
    return (
      <div data-screen="CWP-032">
        {head}
        <Card testId="final-bill">
          <p className="text-body text-neutral-600">{t("portal.finalBill.reading")}</p>
        </Card>
      </div>
    );
  }

  const bill = view.bill;
  if (bill === null) {
    // BR-CWP-093 — a settlement panel over an account that has not moved out
    // would be a page telling a customer their service is ending.
    return (
      <div data-screen="CWP-032">
        {head}
        <Card testId="final-bill">
          <p className="text-body text-neutral-600" data-final-none="">
            {t("portal.finalBill.none")}
          </p>
        </Card>
      </div>
    );
  }

  const currency = bill.currency;
  const remainder = Number(bill.remainder ?? "0");
  const weOwe = remainder < 0;

  return (
    <div data-screen="CWP-032">
      {/* ⚠ **THIS WAS MISSING AND IT IS THE ONLY BRANCH A CUSTOMER WITH A
          FINAL BILL EVER REACHES** (`DEF-CWP-4193`'s sibling `DEF-CWP-4190`,
          found by opening the screen in a browser). `{head}` was rendered in
          the three returns ABOVE — could-not-read, still-reading, and no final
          bill — so the heading appeared on every state where there is nothing
          to read and vanished the moment there was something. The docstring at
          the top of this file has claimed *"renders on every branch"* since the
          `DEF-CWP-4000` page-head sweep; it was true of three branches out of
          four, and the fourth is the screen.
          **The general shape, worth more than the fix:** when a sweep adds one
          element to a component with early returns, the branch that matters is
          the LAST one, and it is the only branch a fixture reaches by accident
          — every empty state draws without any data at all. */}
      {head}
      <TwoEqual
        left={
          <Card testId="final-bill">
            <SectionTitle>{t("portal.finalBill.settlingUp")}</SectionTitle>
            {/* B14 rule 32 — one sentence for the section. */}
            <p className="text-body text-neutral-700" data-final-period="">
              {bill.period_start && bill.period_end
                ? t("portal.finalBill.period", {
                    from: showDate(bill.period_start),
                    to: showDate(bill.period_end),
                  })
                : t("portal.finalBill.periodUnknown")}
            </p>

            {bill.settlement_unavailable ? (
              // ⚠ THE ENGINE REFUSES RATHER THAN PAYING PRINCIPAL ALONE, and
              // the screen says so instead of showing a settlement it does not
              // have. One sentence covers every reason the server can give.
              <p className="text-body text-neutral-600" data-final-unavailable="">
                {t("portal.finalBill.settlementUnavailable")}
              </p>
            ) : (
              <>
                {/* ⚠ **THE MONEY IS THE HEADLINE, BECAUSE IT IS WHAT THEY CAME
                    FOR** (`CR-085` task (c), wireframe s24: *"The refund is the
                    headline, not the bill … It answers 'is that everything' and
                    'where is my deposit' without a call."*). It used to be the
                    last row of a list, under three lines of arithmetic, on the
                    last screen a leaving customer ever opens.

                    ⚠ **AND IT IS THE SAME STRING AS THE TOTAL BELOW, NOT A
                    SECOND READING OF THE SIGN.** `formatMoney(bill.remainder)`
                    is rendered twice out of one figure, so the headline and the
                    arithmetic cannot disagree — there is still no `Math.abs` on
                    this screen, and the DIRECTION is a sentence, exactly as the
                    docstring at the top of this file requires. */}
                <KpiTile
                  testKey="settlement-headline"
                  lead
                  label={
                    weOwe ? t("portal.finalBill.comingBackToYou") : t("portal.finalBill.stillToPay")
                  }
                  value={formatMoney(bill.remainder ?? "0", currency)}
                  sub={
                    !weOwe && bill.due_on
                      ? t("portal.finalBill.dueOn", { date: showDate(bill.due_on) })
                      : null
                  }
                />
                <KVList
                  rows={[
                    {
                      key: "service",
                      label: t("portal.finalBill.serviceTo", {
                        to: showDate(bill.period_end) || "",
                      }),
                      value: formatMoney(bill.service_charges, currency),
                    },
                    ...(bill.deposit
                      ? [
                          {
                            key: "held",
                            label: bill.deposit.taken_on
                              ? t("portal.finalBill.depositHeldSince", {
                                  since: showDate(bill.deposit.taken_on),
                                })
                              : t("portal.finalBill.depositHeld"),
                            // The credit is money coming OFF, so it is drawn
                            // negative — and the minus is composed here from a
                            // figure the server sent as a positive holding,
                            // which is a presentation of a credit rather than a
                            // re-reading of a sign.
                            value: formatMoney(`-${bill.deposit.held}`, currency),
                          },
                          {
                            key: "interest",
                            label: t("portal.finalBill.depositInterest"),
                            value: formatMoney(`-${bill.deposit.interest}`, currency),
                          },
                        ]
                      : []),
                  ]}
                />
                <TotalRow
                  testKey="settlement"
                  label={
                    weOwe ? t("portal.finalBill.weOweYou") : t("portal.finalBill.youOweUs")
                  }
                  // ⚠ THE SERVER'S FIGURE, NOT AN ABSOLUTE VALUE. `-89.8000`
                  // renders as `-$89.80` under *we owe you*, which is the
                  // arithmetic the customer can check against the lines above.
                  value={formatMoney(bill.remainder ?? "0", currency)}
                  signed={weOwe ? "down" : "up"}
                />
                {/* ⚠ **THE DOCUMENT ITSELF, WHICH THIS SCREEN NEVER OFFERED**
                    (wireframe s24: *"↓ Download the final bill"*). A final bill
                    carries a NUMBER like any other bill — `PortalFinalBill.number`
                    — and `/bills/{number}/document` is the route `CWP-028` and
                    `CWP-029` already open; the same words are used, out of the
                    same catalogue key, so a customer meets one name for one
                    thing. A bill with no number opens nothing, so the link is
                    absent rather than dead (hard-won law 2). */}
                {bill.number ? (
                  <ErrandLink
                    label={t("portal.billDetail.openDocument")}
                    to={`/bills/${encodeURIComponent(bill.number)}/document`}
                  />
                ) : null}
                <ConsequenceBox
                  heading={t("portal.finalBill.whatHappensNext")}
                  bullets={[
                    <span key="path" data-consequence-code={bill.path ?? "pending"}>
                      {bill.path === "refund"
                        ? t("portal.finalBill.next.refund")
                        : bill.path === "write_off"
                          ? t("portal.finalBill.next.writtenOff")
                          : weOwe
                            ? t("portal.finalBill.next.beingDecided")
                            : t("portal.finalBill.next.pay")}
                    </span>,
                    <span key="notCredit" data-consequence-code="not_a_credit">
                      {t("portal.finalBill.next.notACredit")}
                    </span>,
                  ]}
                />
              </>
            )}
          </Card>
        }
        right={
          <Card testId="closing-reading">
            <SectionTitle>{t("portal.finalBill.closingReading")}</SectionTitle>
            {view.closing_reading === null ? (
              <p className="text-body text-neutral-600" data-closing-none="">
                {t("portal.finalBill.noClosingReading")}
              </p>
            ) : (
              <>
                <KVList
                  rows={[
                    {
                      key: "reading",
                      label: t("portal.finalBill.reading_"),
                      value: view.closing_reading.reading_display ?? "—",
                    },
                    {
                      key: "taken",
                      label: t("portal.finalBill.takenOn"),
                      value: showDate(view.closing_reading.taken_on) || "—",
                    },
                    {
                      key: "used",
                      label: t("portal.finalBill.usedSince"),
                      value: view.closing_reading.used_since_display ?? "—",
                    },
                  ]}
                />
                {/* ⚠ The METHOD travels as a code and the catalogue writes the
                    words (B14 rule 35) — `CWP-034` uses the same vocabulary. */}
                {view.closing_reading.how ? (
                  <p className="text-base text-neutral-600" data-closing-how="">
                    {t(`portal.readings.how.${view.closing_reading.how}`, {
                      defaultValue: t("portal.finalBill.howUnknown"),
                    })}
                  </p>
                ) : null}
              </>
            )}
            {view.query_reading_open ? (
              <div data-query-reading="open">
                {/* ⚠ **THIS WAS HELD OVER A SCREEN THAT HAD ALREADY LANDED**
                    (`DEF-CWP-3962`, the fourth rotted hold in a week). It read
                    *Ring us to query this* while `CWP-055` — *Dispute a bill or
                    a reading* — was live, routed and tested.

                    **The three facts that had to be established before opening
                    it**, because a released hold on a money path is worse than
                    a held one if any of them is false:
                      · `CWP-055` takes a BILL NUMBER in its path and a final
                        bill carries one (`PortalFinalBill.number`);
                      · `POST bills/{number}/dispute` resolves through
                        `bill_in_set`, the SAME lookup every bill screen uses —
                        there is no *not a final bill* guard anywhere in it, so
                        a final bill's number is a bill number like any other;
                      · this branch only draws while the account is NOT settled
                        (`query_reading_open = not settled`), which is exactly
                        the window in which a query is still the ordinary route.
                        Once it settles the control is GONE and the sentence
                        below says a correction takes longer — that refusal is
                        about the account's state, answered by the data every
                        time it draws, and cannot rot.

                    ⚠ **A BILL WITH NO NUMBER STAYS HELD, and that reason cannot
                    rot either**: `/bills//dispute` opens nothing, and *ring us*
                    is then the true answer rather than a placeholder for a
                    screen somebody has not built. */}
                {bill.number ? (
                  <ErrandLink
                    label={t("portal.finalBill.queryReading")}
                    to={`/bills/${encodeURIComponent(bill.number)}/dispute`}
                  />
                ) : (
                  <HeldButton
                    label={t("portal.finalBill.queryReading")}
                    reason={t("portal.finalBill.queryHeld")}
                  />
                )}
              </div>
            ) : (
              // TC-9 — the route is gone AND the screen says a correction is
              // slower now. A control that merely vanished would leave a
              // customer looking for what they read yesterday.
              <p className="text-body text-neutral-600" data-query-reading="closed">
                {t("portal.finalBill.queryClosed")}
              </p>
            )}
          </Card>
        }
      />
    </div>
  );
}
