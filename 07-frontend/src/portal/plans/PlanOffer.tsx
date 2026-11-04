// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-053 (EP-CWP-10) — *"A plan the utility has offered you, and
//           your signature on it"*. Screen: CWP-063 (blueprint `P49`)
// Rules:    BR-CWP-065 (a plan activates on the CUSTOMER's signature ALONE) ·
//           BR-CWP-063 (new bills still arrive and still have to be paid) ·
//           BR-CWP-001 (the portal writes rows of exactly six kinds — a
//           signature is none of them; G81) · BR-CWP-056 (a control that may
//           not be used is DISABLED WITH ITS REASON, never hidden) ·
//           BR-CUS-043 (late-fee suspension is a PER-PLAN election) ·
//           B14 rule 20 · rule 21 · rule 31 · rule 32 · rule 33 · rule 35 ·
//           rule 36 (compose the kit; `TotalRow` was ADDED to it) ·
//           CLAUDE.md hard rule 2 (2 dp displayed)
// Open:     OQ-CWP-1566 (no column holds the offer's expiry) ·
//           OQ-CWP-1567 (the clerk's name lives only on a pruned audit row) ·
//           OQ-CWP-1568 (may the portal accept, decline or counter?)
// Defect:   DEF-CWP-4139 — these three read 1563/1564/1565 until 2026-09-06.
//           1565 and 1564 were NEVER ISSUED (no register row, no reservation)
//           and 1563 is a real but unrelated CLOSED question, so the three
//           holds on this screen pointed at nothing anybody could answer. The
//           server had all three right the whole time; only the front end was
//           wrong, which is why nothing disagreed.
// Tests:    src/portal/plans/PlanOffer.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getPlanOffer`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { apiHref } from "@/api/apiHref";
import { PageHeader } from "@/components/PageHeader";

import {
  ButtonRow,
  Card,
  ConsequenceBox,
  HeldButton,
  KVList,
  MiniTable,
  SectionTitle,
  TotalRow,
  TwoCol,
  usePortalPath,
} from "../components/primitives";
import { PortalScreen, PortalState, type PortalWayOut } from "../components/states";
import { Button, ButtonAnchor } from "@/components/Button";
import { usePortalDate } from "../components/regional";
import { formatMoney } from "../signin/Enrol";
import { getPlanOffer, type PortalPlanOffer } from "../api/portalClient";

/**
 * `CWP-063` — the plan a clerk built, waiting on the customer.
 *
 * ⚠ **`agreement_sent` IS THE ONLY STATE THIS SCREEN EXISTS FOR.** A plan moves
 * `proposed → agreement_sent → active → closed` and `BR-CWP-065` says it
 * activates on the customer's signature ALONE — so `agreement_sent` means
 * *offered, waiting on you*, and it is the one state where the customer has
 * something to do. Three of the four states were drawn and this one was not,
 * which is why a utility could raise a plan and the person it was for would
 * hear about it only if somebody rang them.
 *
 * ⚠ **ALL THREE CONTROLS ARE HELD, AND THAT IS A SIGNED BOUNDARY RATHER THAN
 * AN UNFINISHED SCREEN.** `BR-CWP-001` lists the six kinds of row the portal
 * may write — a payment, a service request, a meter reading, a preference, a
 * contact detail, an account link. A plan signature is none of them, `G81`
 * fails the build on a seventh, and `write_points.py` says in its own words
 * that adding one *"is a ruling and not an edit"*. `08-screen-layouts.md`
 * already draws *Accept this plan ✓* **held**. The ruling is `OQ-CWP-1568`.
 *
 * ⚠ **TWO SENTENCES THIS SCREEN CANNOT SAY, AND IT SAYS SO INSTEAD OF
 * GUESSING.** *"The offer stands until 16 September"* — no column holds an
 * expiry (`OQ-CWP-1566`). *"Sarah at the office set this up"* — the clerk
 * exists only on an audit row that is pruned (`OQ-CWP-1567`). Printing a
 * computed date would state a deadline this product cannot enforce; printing
 * a user id would breach B14 rule 31.
 *
 * ⚠ **THE CONSEQUENCES ARE READ FROM THIS PLAN, NOT WRITTEN HERE.** Late-fee
 * suspension is a per-plan election (`BR-CUS-043`), so a plan with it off says
 * *late fees still apply* rather than promising they stop — J41 step 4's case,
 * and the reason these are four codes from the server rather than four bullets
 * in this file.
 */
export function PlanOfferView(props: { accountId: string }) {
  const { t } = useTranslation();
  //: `CR-085` `CPB-03` — the tenant segment of the API address. Read the same
  //: way `usePortalPath` reads it, from the route, never from a config.
  const { tenant } = useParams();
  //: `DEF-CWP-4138` — the tenant's own date format, through the ONE formatter
  //: (`DEF-CWP-3994`'s wire). An unset Regional setting publishes nothing and
  //: this hands back the server's string unchanged, so it cannot invent a
  //: format for a tenant that has not chosen one.
  const showDate = usePortalDate();
  const path = usePortalPath();
  const [offer, setOffer] = useState<PortalPlanOffer | null | undefined>(undefined);
  const [failed, setFailed] = useState(false);
  //: R-10's *Try again* needs something to try — see `Overdue.tsx`.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setFailed(false);
    getPlanOffer(props.accountId)
      .then((answer) => {
        if (live) setOffer(answer.offer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [props.accountId, attempt]);

  //: `CR-085` `CPB-03` — the API address that answers the kept bytes. Composed
  //: once, beside the head that uses it, so the string exists in one place.
  //: ⚠ **THE TENANT IS IN IT.** Every portal API address is
  //: `/api/{tenant}/portal/…`; a bare `/api/portal/…` would reach nothing and
  //: `toContain` would accept it (`DEF-CWP-3925`'s fixture lesson).
  const agreementHref = apiHref(
    `/${tenant ?? ""}/portal/accounts/${props.accountId}/plans/offer/agreement`,
  );

  // ⚠ **THE HEAD IS BUILT ONCE AND RENDERS ON EVERY BRANCH, LOADING INCLUDED**
  // (`DEF-CWP-4000`; audit D1, delta X4/X5). It composes the shared
  // `components/PageHeader.tsx` — the ONE page head B14 rule 2 names, which
  // fifteen portal files already used and twenty-eight signed-in screens did
  // not. A head that lived only in the happy-path return would leave the page
  // with no `<h1>` for as long as the request takes.
  const head = (
    <PageHeader
      kicker={t("portal.kicker.payments")}
      title={t("portal.planOffer.title")}
      // ⚠ **THE DRAWING'S HEAD ACTION (`DEF-CWP-4000`, audit D1).**
      // `08-screen-layouts.md` heads `CWP-063` *· action ↓ Agreement* and the
      // control sat at the FOOT of the offer card. Moved, not re-drawn.
      // ⚠ **THE REASON STILL COMES FROM THE OFFER, WHICH IS WHY THIS IS A
      // CONDITIONAL AND NOT A CONSTANT.** `BR-CWP-045`: the agreement is
      // SERVED and never re-rendered, so an offer that kept no document
      // refuses with the store's own reason, not "not built yet". Collapsing
      // the two into one sentence would tell a customer their agreement is
      // coming when it was never kept.
      //
      // ⚠ **AND WHERE A COPY *WAS* KEPT IT IS NOW A DOWNLOAD, NOT A HOLD**
      // (`CR-085` `CPB-03`). *Downloads are not ready yet* sat over a document
      // this product had already frozen and could already serve — the bill
      // route has streamed the same kind of bytes, out of the same store,
      // behind the same `download` permission, since `US-CWP-034`. The hold
      // was a hold on nothing, which is hard-won law 2's mirror: a live
      // capability behind a dead control.
      //
      // ⚠ **A PLAIN `<a>` AND NOT A ROUTER LINK.** The destination is an API
      // address that answers bytes, not a screen; `ErrandLink` would push it
      // through the router and land on *not built yet*.
      secondaryActions={
        offer ? (
          offer.agreement.available ? (
            // ⚠ **THE KIT'S `ButtonAnchor`, NOT FIVE HAND-ROLLED UTILITIES**
            // (`DEF-CWP-4720`, B14 rule 36). It was written out here as an
            // `<a>` with its own border, padding and hover — and the hover was
            // `hover:bg-neutral-50`, **a class `tokens.css` does not declare**:
            // the lightest neutral in this product is `neutral-100`, so the
            // hover state of the only download on the screen did nothing at
            // all. `tsc`, eslint and every `toContain` assertion passed on it
            // because the class IS in the DOM (`DEF-974`). `CWP-043` already
            // serves the same document through `ButtonAnchor`, so this is one
            // shape for one job rather than two.
            <ButtonAnchor
              variant="secondary"
              href={agreementHref}
              data-plan-agreement-download=""
            >
              {t("portal.planOffer.agreement")}
            </ButtonAnchor>
          ) : (
            <HeldButton
              label={t("portal.planOffer.agreement")}
              reason={t("portal.planOffer.agreementNotKept")}
            />
          )
        ) : null
      }
    />
  );

  // ⚠ **R-10** (PO 2026-09-11). *There is no plan waiting for you* and *we
  // could not open your offer* are both read by somebody who wants a plan, so
  // both carry the way to ask for one — the empty branch already did, and the
  // failed branch did not.
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
      <PortalScreen screen="CWP-063" head={head}>
        <PortalState
          kind="failed"
          testId="plan-offer"
          sentence={t("portal.planOffer.couldNotRead")}
          waysOut={[tryAgain, askForAPlan]}
        />
      </PortalScreen>
    );
  }
  if (offer === undefined) {
    return (
      <PortalScreen screen="CWP-063" head={head}>
        <PortalState kind="loading" testId="plan-offer" sentence={t("portal.planOffer.reading")} />
      </PortalScreen>
    );
  }
  if (offer === null) {
    // B14 rule 17 — a sentence naming what would fill it. An account with no
    // offer is the ordinary case, not a fault.
    // ⚠ **THE SENTENCE OFFERED A TELEPHONE AND THE PRODUCT HAS A SCREEN**
    // (`CR-085` task (c)): the way to ask for a plan is one route along, and
    // it now sits beside the sentence rather than in a row under it.
    return (
      <PortalScreen screen="CWP-063" head={head}>
        <PortalState
          kind="empty"
          testId="plan-offer"
          sentence={t("portal.planOffer.none")}
          waysOut={[askForAPlan]}
        />
      </PortalScreen>
    );
  }

  const spread = formatMoney(offer.spread, offer.currency);
  return (
    <div data-screen="CWP-063">
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
      <TwoCol
        main={
          <Card testId="plan-offer">
            {/* ⚠ **THE TITLE WAS PRINTED TWICE, ONE LINE APART** — *The plan we
                can offer* as the page `<h1>` and again here as a section title
                (`DEF-CWP-4183`). The card opens on the lead, which names the
                person who set the plan up. */}
            {/* ⚠ **B14 rule 32 — ONE sentence for the section, AND IT NOW
                CARRIES THE PERSON** (`CR-085` `CPB-21`, closing `OQ-CWP-1567`
                option (a) on 2026-09-08). It used to name the utility and the
                date and no person, because the clerk's identity lived only on
                an audit row the retention schedule deletes; `payment_plans`
                keeps it now, so *the office* becomes a name when there is one.

                ⚠ **IT REPLACES THE SENTENCE RATHER THAN ADDING ONE.** A fourth
                grey line under the lead would have spent the whole section's
                description budget saying who, and *"Sarah Kesler set this up"*
                is the reassurance the sentence already existed for.

                ⚠ **AND WHERE NOBODY WAS RECORDED THE OLD SENTENCE STANDS**,
                with the stated absence in the rail card below — never an
                invented office. */}
            <p className="mt-2 text-body text-neutral-700" data-plan-offer-lead="">
              {offer.offered_by === null
                ? t("portal.planOffer.lead", { date: showDate(offer.offered_on) || "—" })
                : t("portal.planOffer.leadBy", {
                    name: offer.offered_by,
                    date: showDate(offer.offered_on) || "—",
                  })}
            </p>
            <div className="mt-3">
              <KVList
                rows={[
                  {
                    key: "covers",
                    label: t("portal.planOffer.covers"),
                    value: formatMoney(offer.covers, offer.currency),
                  },
                  {
                    key: "upfront",
                    label: t("portal.planOffer.paidUpFront"),
                    value: formatMoney(offer.paid_up_front, offer.currency),
                  },
                  {
                    key: "spread",
                    label: t("portal.planOffer.spreadOver", {
                      count: offer.instalment_count,
                    }),
                    value: spread,
                  },
                  {
                    key: "first",
                    label: t("portal.planOffer.firstPayment"),
                    value: showDate(offer.first_payment_on) || "—",
                  },
                ]}
              />
            </div>
            <p className="mt-2 text-base text-neutral-600" data-plan-offer-rounding="">
              {t("portal.planOffer.roundingNote")}
            </p>
            <div className="mt-4">
              <ConsequenceBox
                heading={t("portal.planOffer.consequenceHeading")}
                bullets={offer.consequences.map((code) => (
                  <span key={code} data-consequence-code={code}>
                    {t(`portal.planOffer.consequence.${code}`)}
                  </span>
                ))}
              />
            </div>
            {/* The three controls, IN THIS ORDER (`US-CWP-053` §1), all held.
                B14 rule 33 — the reason is five words.

                ⚠ **ONE REASON UNDER THE GROUP, NOT ONE UNDER EACH BUTTON —
                `DEF-CWP-4920`.** `HeldButton` prints its reason as a line
                under itself, which is exactly right for a lone control and
                wrong three times over in a row: the screen read *Ring us to
                answer this offer · Ring us to answer this offer · Ring us to
                answer this offer*, stacked, which reads as a stutter and buries
                the sentence it is trying to make. The three share ONE cause, so
                they share one sentence — and it is `HeldButton`'s own reason
                line, same key, same type, same colour, so the kit still owns
                what *held* looks like (B14 rule 36).

                ⚠ **THE KIT HAS NO *GROUP OF HELD CONTROLS* AND SHOULD**, and
                this lane is not the one to add it: `primitives.tsx` belongs to
                the frame lane this session. Reported rather than forked.

                ⚠ **STILL HELD, WITH `OQ-CWP-1568` NOW CLOSED.** The ruling of
                2026-09-11 says a signed-in customer MAY accept, ask for
                different terms and decline. **It gave permission, not a write
                path.** `apps/portal` serves this offer as a READ; the six
                kinds `BR-CWP-001` allows do not include a plan signature,
                `write_points.py` says adding one *"is a ruling and not an
                edit"*, and `G81` fails the build until a row is recorded. So
                the refusal is still TRUE — ringing really is the only way to
                answer this offer today — and `holds.ts` now carries the closed
                ruling and the three things still to decide. */}
            <ButtonRow>
              <span data-plan-action="accept">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled
                  title={t("portal.planOffer.actionsHeld")}
                  aria-describedby="plan-actions-held"
                >
                  {t("portal.planOffer.accept")}
                </Button>
              </span>
              <span data-plan-action="different-terms">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled
                  title={t("portal.planOffer.actionsHeld")}
                  aria-describedby="plan-actions-held"
                >
                  {t("portal.planOffer.differentTerms")}
                </Button>
              </span>
              <span data-plan-action="decline">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled
                  title={t("portal.planOffer.actionsHeld")}
                  aria-describedby="plan-actions-held"
                >
                  {t("portal.planOffer.decline")}
                </Button>
              </span>
            </ButtonRow>
            <p id="plan-actions-held" className="mt-1 text-base text-neutral-600" data-plan-actions-held="">
              {t("portal.planOffer.actionsHeld")}
            </p>
          </Card>
        }
        rail={
          <>
            <Card testId="plan-instalments">
              <SectionTitle>{t("portal.planOffer.instalmentsTitle")}</SectionTitle>
              <div className="mt-3">
                <MiniTable
                  caption={t("portal.planOffer.instalmentsCaption")}
                  columns={[
                    { key: "number", label: t("portal.planOffer.colNumber") },
                    { key: "due", label: t("portal.planOffer.colDue") },
                    {
                      key: "amount",
                      label: t("portal.planOffer.colAmount"),
                      align: "right" as const,
                    },
                  ]}
                  rows={offer.instalments.map((row) => ({
                    key: String(row.number),
                    cells: {
                      number: row.number,
                      due: showDate(row.due_on),
                      amount: (
                        <span className="tabular-nums" data-instalment={row.number}>
                          {formatMoney(row.amount, row.currency)}
                        </span>
                      ),
                    },
                  }))}
                />
              </div>
              {/* The instalments add to what is SPREAD, not to what the plan
                  COVERS: the down payment is already received. Showing the
                  covered figure here would look like the customer still owes
                  it twice. */}
              <div className="mt-2">
                <TotalRow
                  testKey="instalments"
                  label={t("portal.planOffer.instalmentsTotal")}
                  value={spread}
                />
              </div>
            </Card>
            <Card testId="plan-nothing-happens">
              <SectionTitle>{t("portal.planOffer.waitingTitle")}</SectionTitle>
              <p className="mt-2 text-body text-neutral-700" data-plan-waiting="">
                {t("portal.planOffer.nothingHappens")}
              </p>
              {/* ⚠ TWO STATED ABSENCES, EACH WITH ITS OWN SENTENCE. Neither is
                  computed and neither is hidden — a screen that quietly
                  dropped the expiry line would leave a customer believing the
                  offer stands for ever. */}
              {offer.expires_on === null ? (
                <p className="mt-2 text-base text-neutral-600" data-plan-no-expiry="">
                  {t("portal.planOffer.noExpiry")}
                </p>
              ) : (
                // ⚠ **THE TENANT'S OWN FORMAT — `DEF-CWP-4911`.** This one
                // line printed the WIRE date, `2026-08-27`, beside four dates
                // on the same screen already going through `usePortalDate` and
                // reading `08/27/2026`. Every other date on `CWP-063` was
                // fixed by `DEF-CWP-4138`'s sweep and this one was missed
                // because it is inside a conditional the seeded estate never
                // reaches: `expires_on` is `null` on every account today, so
                // the branch that is wrong is the branch nobody can open.
                <p className="mt-2 text-base text-neutral-600" data-plan-expiry={offer.expires_on}>
                  {t("portal.planOffer.expiresOn", { date: showDate(offer.expires_on) })}
                </p>
              )}
              {offer.offered_by === null ? (
                <p className="mt-2 text-base text-neutral-600" data-plan-no-clerk="">
                  {t("portal.planOffer.noClerkName")}
                </p>
              ) : null}
            </Card>
          </>
        }
      />
    </div>
  );
}
