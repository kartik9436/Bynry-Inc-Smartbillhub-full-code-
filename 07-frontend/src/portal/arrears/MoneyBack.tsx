// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-056 (EP-CWP-10) — credits and refunds in flight, and they
//           are different things · US-CWP-049 (EP-CWP-09) — the refund returns
//           to the method the money came in on. Screen: CWP-045 (blueprint
//           `P31`)
// Rules:    BR-CWP-047 (the credit figure is re-read on every load, never
//           cached) · BR-CWP-060 (the refund names the method it is going back
//           to) · BR-CWP-093 (nothing empty ever appears) · B14 rule 21 ·
//           rule 31 (no database id on screen) · rule 32 · rule 35 · rule 36 ·
//           CLAUDE.md hard rule 2 (2 dp displayed)
// Tests:    src/portal/arrears/MoneyBack.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getMoneyBack`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

import {
  ChecklistTimeline,
  MiniTable,
  SectionTitle,
  StatusChip,
  usePortalPath,
} from "../components/primitives";
import { PortalScreen, PortalState, type PortalWayOut } from "../components/states";
import { Panel } from "@/components/Panel";
import { usePortalDate } from "../components/regional";
import { formatMoney } from "../signin/Enrol";
import {
  getMoneyBack,
  type PortalCredit,
  type PortalRefund,
} from "../api/portalClient";

/**
 * `CWP-045` — *is it coming back, or is it coming off?*
 *
 * ⚠ **CREDIT AND REFUND ARE DIFFERENT THINGS AND CUSTOMERS USE THE WORDS
 * INTERCHANGEABLY**, so the screen separates them and one line does the work:
 * *a credit comes off your next bill. A refund is money sent back.* **A screen
 * that calls both *money back* is the defect** this story names.
 *
 * ⚠ **NOTHING IS CACHED AND NOTHING MAY BE** (`BR-CWP-047`): a credit that was
 * real on Tuesday can be spent by Thursday. The read runs on every mount and
 * the server answers `no-store`.
 *
 * ⚠ **A VOIDED REFUND IS LISTED AS VOIDED, NOT REMOVED.** A customer told money
 * was coming and then shown nothing has no way to ask what happened to it.
 *
 * ⚠ **THE SIGN THE SERVER SENT IS THE SIGN RENDERED.** A credit note is stored
 * at or below zero by a database CHECK and shows negative; a refund is stored
 * positive and shows positive. **Nothing here takes an absolute value** — a
 * panel that once read `272.30` where a customer owed `222.30` is what two
 * writers disagreeing about a sign costs.
 */
export function MoneyBackView(props: { accountId: string }) {
  const { t } = useTranslation();
  //: ⚠ **THE CREDITS COLUMN WAS THE ONE DATE LEFT RAW** — `DEF-CWP-4178`.
  //: The refund's own dates were moved onto the tenant's format with
  //: `DEF-CWP-4131`, and `showDate` lives inside `OneRefund`; this table is
  //: in a different component and kept printing `2026-07-12` in the WHEN
  //: column while the panel above it read `07/12/2026`. Two date formats on
  //: one screen is worse than one wrong one, because it reads as two
  //: different KINDS of date.
  const showDate = usePortalDate();
  const [body, setBody] = useState<{
    any: boolean;
    refunds: PortalRefund[];
    credits: PortalCredit[];
  } | null>(null);
  const [failed, setFailed] = useState(false);
  //: R-10's *Try again* needs something to try — see `Overdue.tsx`.
  const [attempt, setAttempt] = useState(0);
  const path = usePortalPath();

  useEffect(() => {
    let live = true;
    setFailed(false);
    getMoneyBack(props.accountId)
      .then((answer) => {
        if (live) setBody(answer);
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
  const head = (
    <PageHeader
      kicker={t("portal.kicker.payments")}
      title={t("portal.moneyBack.title")}
    />
  );

  // ⚠ **R-10 — *we could not read this* ABOUT MONEY OWED TO THE CUSTOMER**
  // (PO 2026-09-11). A failed read on this screen is the one that reads as
  // *your money has gone*, and it offered nothing at all. The door is the
  // payments list, because that is the only other place in this portal where
  // a credit or a refund appears.
  const failedWaysOut: PortalWayOut[] = [
    {
      label: t("portal.payNow.tryAgain"),
      onClick: () => setAttempt((n) => n + 1),
      tone: "primary",
      testKey: "try-again",
    },
    { label: t("portal.money.title"), to: path("/payments"), testKey: "payments" },
  ];

  if (failed) {
    return (
      <PortalScreen screen="CWP-045" head={head}>
        <PortalState
          kind="failed"
          testId="money-back"
          sentence={t("portal.moneyBack.couldNotRead")}
          waysOut={failedWaysOut}
        />
      </PortalScreen>
    );
  }
  if (body === null) {
    return (
      <PortalScreen screen="CWP-045" head={head}>
        <PortalState kind="loading" testId="money-back" sentence={t("portal.moneyBack.reading")} />
      </PortalScreen>
    );
  }
  if (!body.any) {
    // ⚠ `BR-CWP-093` — one sentence, never two empty tables.
    return (
      <PortalScreen screen="CWP-045" head={head}>
        <PortalState kind="empty" testId="money-back" sentence={t("portal.moneyBack.none")}>
          {/* ⚠ **THE DRAWING'S *no credit* STATE SAYS WHAT WOULD CREATE ONE**
              (wireframe screen 49), and this branch stopped at the absence. A
              customer who believes they overpaid last month and is told only
              *there is no money coming back* has been answered without being
              told how to tell whether that is right. No figure is invented
              here: the sentence names the two things that produce a credit in
              this product and quotes nothing. */}
          <p className="m-0 text-body text-neutral-700" data-money-back-what-next="">
            {t("portal.moneyBack.whatWouldCreateOne")}
          </p>
        </PortalState>
      </PortalScreen>
    );
  }

  // ⚠ **ONE COLUMN, AND `DEF-CWP-4146` IS WRONG ABOUT THIS SCREEN — CHECKED,
  // NOT ASSUMED.** The row says *"one column where the plan and the drawing say
  // two"*. `08-screen-layouts.md` marks `CWP-045` **T4**: *`Panel` A REFUND ON
  // ITS WAY … `Panel` CREDITS ON THE ACCOUNT [ … footer sentence]* — two
  // FULL-WIDTH panels and no rail. `MoneyBack.dom.test.tsx`'s D9 case was
  // written by an earlier lane for exactly this moment: *"recorded as a case
  // rather than a note so the next lane reading D9 does not 'fix' it by adding
  // a column the drawing does not have."*
  //
  // **This lane composed a `TwoCol` here and that test went red.** It is the
  // guard working, and it is the reason the change was reverted rather than
  // the test widened. What the drawing DOES have and this screen does not is
  // the `YOUR CREDIT $84.20` headline and its *"enough to cover about half of
  // a typical bill"* — and neither figure is on the wire: `credits[]` is a
  // list of negative amounts with no total, and nothing anywhere carries a
  // typical monthly bill. Reported, not invented.
  return (
    <div data-screen="CWP-045" className="flex flex-col gap-4">
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
      {body.refunds.map((refund, index) => (
        <OneRefund key={`${refund.requested_at ?? ""}-${index}`} refund={refund} />
      ))}
      {body.credits.length > 0 ? (
        <Panel as="section" title={t("portal.moneyBack.creditsHeading")}>
          <MiniTable
            caption={t("portal.moneyBack.creditsCaption")}
            columns={[
              { key: "what", label: t("portal.moneyBack.colWhat") },
              { key: "when", label: t("portal.moneyBack.colWhen") },
              { key: "amount", label: t("portal.moneyBack.colAmount"), align: "right" as const },
              { key: "used", label: t("portal.moneyBack.colUsed") },
            ]}
            rows={body.credits.map((credit, index) => ({
              key: credit.credit_note_no ?? String(index),
              cells: {
                what: credit.reason ?? t("portal.moneyBack.noReasonRecorded"),
                when: credit.issued_on
                  ? showDate(credit.issued_on)
                  : t("portal.moneyBack.noDateRecorded"),
                amount: (
                  // ⚠ **NEGATIVE, BECAUSE THAT IS WHAT THE SERVER SENT.**
                  <span className="tabular-nums" data-credit={index}>
                    {formatMoney(credit.amount, credit.currency)}
                  </span>
                ),
                used:
                  credit.used_on_bill ??
                  // ⚠ An ABSENCE in words, never a blank cell: a blank reads as
                  // *there is nothing here* about a credit that exists.
                  t("portal.moneyBack.notYetUsed"),
              },
            }))}
          />
        </Panel>
      ) : null}
      {/* ⚠ **THE ONE LINE THAT DOES THE WORK** — `US-CWP-056` TC-5. It is on
          the screen rather than in help, because the confusion happens here,
          and it is the plan's own *footer sentence* for the credits panel. */}
      <p className="m-0 text-body text-neutral-600" data-separating-sentence="">
        {t("portal.moneyBack.creditIsNotARefund")}
      </p>
    </div>
  );
}

/** One refund, as four dated steps — **derived from the timestamps the server
 *  sent, never from a second status this screen keeps.** */
function OneRefund(props: { refund: PortalRefund }) {
  const { t } = useTranslation();
  //: ⚠ **THE TENANT'S OWN FORMAT, IN THE TENANT'S OWN ZONE** (`DEF-CWP-4131`).
  //: Every date on this screen was the server's raw string: the four timeline
  //: steps read `2026-09-03` and the void chip read the whole instant —
  //: `Cancelled on 2026-08-28T02:08:26.806734+00:00`, microseconds and a UTC
  //: offset, on a customer's screen. `usePortalDate` has existed since the
  //: regional lane and `bills/Bills.tsx` already uses it; this screen simply
  //: never asked. Hard-won law 2 read from the CONSUMING side.
  const showDate = usePortalDate();
  const { refund } = props;
  const voided = refund.voided_at !== null;
  //: ⚠ **A CANCELLED REFUND IS NOT ON ITS WAY** (`DEF-CWP-4132`). The heading
  //: was fixed for every panel, so the voided one announced money that is not
  //: coming as money that is — one line above a chip saying the opposite.
  //: `US-CWP-056` TC-4 keeps a voided refund on screen so the customer can ask
  //: what happened to it; a title that contradicts the chip defeats that.
  return (
    <Panel
      as="section"
      title={t(voided ? "portal.moneyBack.refundCancelledHeading" : "portal.moneyBack.refundHeading")}
    >
      <div className="flex flex-wrap items-baseline gap-2">
        <SectionTitle>
          <span className="tabular-nums" data-refund-amount="">
            {formatMoney(refund.amount, refund.currency)}
          </span>
        </SectionTitle>
        {voided ? (
          // ⚠ Shown as voided, with its date — never removed. The REASON is the
          // utility's own note and is not on the wire for this screen to show.
          <StatusChip tone="danger" testKey="refund-void">
            {t("portal.moneyBack.voidedOn", { date: showDate(refund.voided_at) })}
          </StatusChip>
        ) : null}
      </div>
      {refund.method !== null ? (
        // `BR-CWP-060` — the refund names the method it is going back to.
        <p className="m-0 text-body text-neutral-600" data-refund-method={refund.method}>
          {t(`portal.moneyBack.method.${refund.method}`, {
            reference: refund.reference ?? "",
          })}
        </p>
      ) : null}
      <WhereItWentBack refund={refund} />
      <ChecklistTimeline
        steps={refund.steps.map((step) => ({
          label: t(`portal.moneyBack.step.${step.step}`),
          detail: step.on === null ? t("portal.moneyBack.notYet") : showDate(step.on),
          state: step.on === null ? ("future" as const) : ("done" as const),
        }))}
      />
      {refund.steps[3]?.on === null && !voided ? (
        <p className="m-0 text-base text-neutral-600" data-clearing-note="">
          {t("portal.moneyBack.clearingNote")}
        </p>
      ) : null}
    </Panel>
  );
}


/**
 * `US-CWP-049` — **where the money came in, where it is going, and why those
 * are not always the same place.**
 *
 * ⚠ **THE STORY DRAWS *"Sent · 21 Sep · to the card ending 8812"* AND THIS
 * SCREEN MAY NOT PRINT IT TODAY.** `BR-PAY-014` puts card refunds behind the
 * payment rails (W7) and the database refuses `card` as a refund method, so
 * money that came in on a card goes back out **by cheque**. Printing the drawn
 * sentence over a cheque in the post is a promise on screen with nothing behind
 * it — hard-won law 1 pointed at a customer.
 *
 * **So the same fact is told truthfully**, which is the shape `TC-3` already
 * asks for in the expired-card case (*"falls back to a cheque and the timeline
 * says so — never silently to a dead card"*): name the card the money came in
 * on, name the cheque it is going back on, and say WHY. `payments` decides
 * which of the four reasons applies; this renders the sentence the catalogue
 * writes for it.
 *
 * ⚠ **A REASON WITH NO SENTENCE RENDERS NOTHING** rather than its code —
 * `DEF-CWP-3926`'s rule, and `problems[]` is not the only channel it applies
 * to: a code is an internal name and a customer never reads one.
 *
 * ⚠ **AND `destination` IS OPTIONAL ON THE TYPE**, so a body served before this
 * landed renders exactly what it did before rather than throwing.
 */
function WhereItWentBack(props: { refund: PortalRefund }) {
  const { t } = useTranslation();
  const where = props.refund.destination;
  if (where === undefined) {
    return null;
  }
  const cameInBy =
    where.came_in_by === null
      ? ""
      : t(`portal.moneyBack.cameInBy.${where.came_in_by}`, {
          defaultValue: "",
          brand: where.brand ?? "",
          lastFour: where.last_four ?? "",
        });
  const fallback =
    where.fallback_reason === null
      ? ""
      : t(`portal.moneyBack.instead.${where.fallback_reason}`, { defaultValue: "" });
  return (
    // ⚠ **THE FACTS ARE ON THE WRAPPER AND THE SENTENCES ARE INSIDE IT, AND
    // THAT SPLIT IS DELIBERATE.** A sentence that has not been written yet
    // renders NOTHING (`DEF-CWP-3926`), so a test asserting the sentence would
    // be asserting one of eleven catalogues and would go green or red on a
    // translation rather than on this screen's behaviour. The server's answer —
    // where it came in, why it is not going back there, and where the cheque
    // was posted — is carried as data, which is what the walkthrough and the
    // suite can both check in any language.
    <div
      className="flex flex-col gap-1"
      data-destination={where.kind}
      data-came-in-by={where.came_in_by ?? undefined}
      data-fallback-reason={where.fallback_reason ?? undefined}
      data-posted-to={where.posted_to ?? undefined}
    >
      {cameInBy === "" ? null : (
        <p className="m-0 text-base text-neutral-600">{cameInBy}</p>
      )}
      {/* ⚠ **THE REASON IS THE POINT** — `US-CWP-049` TC-4 bans a bare *sent*. */}
      {fallback === "" ? null : (
        <p className="m-0 text-base text-neutral-600">{fallback}</p>
      )}
      {/* TC-2 — a cheque names the address it went to. */}
      {where.posted_to ? (
        <p className="m-0 text-base text-neutral-600">
          {t("portal.moneyBack.postedTo", { address: where.posted_to })}
        </p>
      ) : null}
    </div>
  );
}
