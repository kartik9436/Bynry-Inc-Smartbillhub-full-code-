// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-065 (EP-CWP-11) — dispute a bill or a reading: **a marker,
//           never an edit**. Screen: CWP-055 (blueprint `P41`)
// Rules:    CLAUDE.md hard rule 4 (an issued bill takes no UPDATE) ·
//           BR-CWP-042 (a correction is a NEW bill; the original stays) ·
//           B14 rule 31 (the bill is named by its number) · rule 21 · rule 32
//           (one sentence per section) · rule 33 (a refusal is five or six
//           words) · rule 36 (compose the kit)
// Open:     OQ-CWP-1682 — the blueprint's consequence box promises a hold on
//           `$142.18` and nothing records a disputed AMOUNT (`OQ-420`).
//           **Until that is answered this screen does not promise a hold.**
//           OQ-CWP-1681 — a clerk raises metering's dispute marker, not this.
// Tests:    src/portal/requests/DisputeBill.dom.test.tsx
// Design:   CR-085 (c) — redrawn against the signed-off wireframe for s34:
//           a title and a way back to the bill, and the five real reasons as
//           a list rather than an empty box. The photo upload and the
//           collection-hold promise the drawing also carries are REPORTED —
//           there is no upload endpoint, and the hold is `OQ-CWP-1682`.
// Impacts:  src/portal/api/portalClient.ts `disputeBill`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";

import {
  ButtonRow,
  Card,
  CommitButton,
  ConsequenceBox,
  ErrandLink,
  FormField,
  KVList,
  SectionTitle,
  SelectInput,
  Stepper,
  TextInput,
  TwoCol,
  usePortalPath,
  WizardFooter,
} from "../components/primitives";
import { usePortalDate } from "../components/regional";
import { formatMoney } from "../signin/Enrol";
import { disputeBill, getBillDetail, type PortalBillDetail } from "../api/portalClient";
import { Announced } from "../components/a11y";

/**
 * **THE FIVE REASONS, IN THE CUSTOMER'S OWN WORDS** — the drawing's list, and
 * its reasoning verbatim: *"The reasons are the five real ones, in the
 * customer's words, chosen from a list. An open text box alone makes them
 * compose an argument; a list lets them recognise their situation."*
 *
 * ⚠ **THE VALUE THAT TRAVELS IS THE SENTENCE THE CUSTOMER PICKED, NOT A CODE.**
 * `POST bills/{number}/dispute` takes `what` as free text and writes it into
 * the sentence a clerk reads on their worklist — so a key like `meter_reading`
 * would put an internal code in front of a person (B14 rule 32) and would need
 * a second lookup table on the staff side to mean anything. The customer's own
 * words go through unchanged, which is also what `CWP-046` shows the customer
 * back.
 *
 * ⚠ **`other` IS LAST AND IS NOT A DEAD END** — *Why* is a required box on the
 * same step, so *Something else* still arrives with a sentence attached.
 */
const REASONS = ["higher", "reading", "service", "payment", "other"] as const;

/**
 * What sending the query does, and **there is no hold bullet.**
 *
 * ⚠ **`OQ-CWP-1682` IS OPEN AND THE BLUEPRINT'S FIFTH BULLET CANNOT BE
 * PRINTED.** The drawing promises *"We hold collection on `$142.18`. No late
 * fee while we look."*; nothing in this product records a disputed AMOUNT
 * (`OQ-420`, and `late_fee.ageable_portion` raises rather than choose between
 * two fallbacks `$137.20` apart), so the sentence would be hard-won law 1 on a
 * customer's money. A test asserts no catalogue promises one.
 */
const CONSEQUENCES = [
  "billStands",
  "correctionIsNewBill",
  "restStillDue",
  "weReply",
] as const;

/**
 * `CWP-055` — question a bill, and **the bill does not change.**
 *
 * ⚠ **THAT IS CLAUDE.md HARD RULE 4 WEARING A SCREEN.** An issued invoice takes
 * no UPDATE: what this form sends is a service request BESIDE the bill, and if
 * the utility agrees the outcome is a CORRECTED bill — a new document — with
 * the disputed original still in the customer's list (`BR-CWP-042`). The panel
 * says so in the customer's own words, because a screen that appeared to edit a
 * bill would be describing a database this product does not have.
 *
 * ⚠ **AND THE CONSEQUENCE BOX DOES NOT PROMISE A HOLD, WHICH IS A DELIBERATE
 * DEPARTURE FROM THE BLUEPRINT.** `US-CWP-065` §1 draws *"we hold collection on
 * `$142.18` · no late fee while we look"*. The rule behind it — `BR-MET-133`
 * clause 4 — is built and needs the DISPUTED AMOUNT, and **nothing in this
 * product records one**: `OQ-420` has been OPEN since 2026-08-26 and
 * `late_fee.ageable_portion` raises rather than choosing between two fallbacks
 * that are `$137.20` apart on the rule's own bill. Printing the promise anyway
 * would be hard-won law 1 on a customer's money. `OQ-CWP-1682` carries the
 * collision to the Product Owner; meanwhile the box says what the code does —
 * the same treatment `OQ-CWP-1720` already put on the payment-plan box.
 */
export function DisputeBillView(props: { number: string }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const asDate = usePortalDate();
  // ⚠ **THE BILL IS READ, AND IT IS THE SAME READ `CWP-028` MAKES**
  // (`CR-085` `CPB-13`, `DEF-CWP-4202` row 55.1). This screen knew a bill
  // NUMBER and nothing else, so **the one screen in the product where a
  // customer disputes money never stated the money** — read live on
  // 2026-09-08: not one figure anywhere on the page. `getBillDetail` is
  // `GET portal/bills/{number}`, which every bill screen already goes
  // through, so the amount a customer is querying and the amount their bill
  // shows are one answer and not two (`12-reuse-map.md`).
  //
  // ⚠ **AND IT IS NOT REQUIRED FOR THE FORM TO WORK.** A failed read leaves
  // `bill` null and the screen says the amount could not be read rather than
  // refusing a customer their query over a figure — the send path never
  // touches it, and the server re-reads the bill for itself.
  //: ⚠ **ONE PIECE OF STATE AND NOT TWO.** A first draft kept a `billFailed`
  //: flag beside this and never read it — eslint said so, correctly. `null`
  //: already means *no figure to show*, and the screen says the same true
  //: thing whether the read is still in flight or has failed; a second flag
  //: would only let the two drift into two sentences about one absence.
  const [bill, setBill] = useState<PortalBillDetail | null>(null);
  const [what, setWhat] = useState("");
  const [reason, setReason] = useState("");
  const [ownReading, setOwnReading] = useState("");
  const [step, setStep] = useState<1 | 2>(1);
  const [reference, setReference] = useState<string | null>(null);
  const [refused, setRefused] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  const ready = what.trim() !== "" && reason.trim() !== "";

  useEffect(() => {
    let live = true;
    getBillDetail(props.number)
      .then((answer) => {
        if (live) setBill(answer);
      })
      .catch(() => {
        // The figure is a courtesy and the query is the point — see `amount`.
      });
    return () => {
      live = false;
    };
  }, [props.number]);

  //: The figure, rounded ONCE by the server (`total_display`) and never here —
  //: CLAUDE.md hard rule 2, and the reason this screen does no arithmetic at
  //: all. `null` until the read lands, and `null` for good if it fails.
  const amount =
    bill === null ? null : formatMoney(bill.total_display, bill.currency);

  // ⚠ **THE CONSEQUENCE BOX SITS ABOVE THE COMMIT AND IN THE SAME COLUMN AS
  // IT** (`DEF-CWP-4202` row 55.2, r10 rule 11, and `08-screen-layouts.md`'s
  // own `CWP-055` line: *main Card [KVList · ConsequenceBox · ButtonRow]*).
  // It was in the RIGHT RAIL, so *before the commit button* was true in DOM
  // ORDER — which is what the walkthrough was checking — and false on the
  // screen, where the box and the button were in two different columns and a
  // phone put the box below the send. A person reads what is above the button
  // they are about to press.
  //
  // ⚠ **DRAWN ON BOTH STEPS, AND THE DRAWING ONLY DRAWS IT ON THE SECOND.**
  // There are two commits here — *Check it* and *Send the query ✓* — and rule
  // 11 is about the button a person is about to press, not about which step of
  // the form they are on. Putting it only on step 2 took *the bill itself does
  // not change* off the first screen a customer sees, which is the screen where
  // they are deciding whether to complain at all.
  const consequences = (
    <ConsequenceBox
      heading={t("portal.dispute.consequenceHeading")}
      bullets={CONSEQUENCES.map((key) => t(`portal.dispute.consequence.${key}`))}
    />
  );

  async function send() {
    setWorking(true);
    setRefused(null);
    try {
      const answer = await disputeBill(props.number, {
        what: what.trim(),
        reason: reason.trim(),
        own_reading: ownReading.trim(),
      });
      setReference(answer.reference);
    } catch {
      // B14 rule 33 — five or six words, and ONE sentence for every refusal the
      // server can give (already queried, unknown bill, not yours).
      setRefused(t("portal.dispute.couldNotSend"));
    } finally {
      setWorking(false);
    }
  }

  // ⚠ **A TITLE AND A WAY BACK, WHICH THIS SCREEN HAD NEITHER OF.** It opened
  // straight onto the stepper: no `<h1>` for a screen reader to land on, and no
  // route back to the bill a person had just come from — so the only way out of
  // a half-filled query was the browser's own back button or the nav. Every
  // other screen in this journey carries the same `PageHeader` with the same
  // back link, and this one is reached from exactly one place.
  //
  // ⚠ **IT RENDERS ON EVERY BRANCH, THE SENT ONE INCLUDED** (`DEF-CWP-4000`'s
  // reading): a head that lived only in the form branch would take the title
  // away at the moment the customer most wants to know where they are.
  const head = (
    <span data-back="bill">
      <PageHeader
        kicker={t("portal.kicker.bills")}
        title={t("portal.dispute.title")}
        backTo={{
          to: path(`/bills/${encodeURIComponent(props.number)}`),
          label: t("portal.dispute.backToBill", { number: props.number }),
        }}
      />
    </span>
  );

  if (reference !== null) {
    return (
      <div data-screen="CWP-055">
        {head}
        <Card testId="dispute-sent">
          {/* F-02 / F-04: the confirmation takes focus; the reference is heard. */}
          <Announced tone="status" as="div" say={t("portal.dispute.sent", { reference })}>
            <SectionTitle>{t("portal.dispute.sentTitle")}</SectionTitle>
          </Announced>
          <p className="text-body text-neutral-800" data-reference={reference}>
            {t("portal.dispute.sent", { reference })}
          </p>
          <p className="text-body text-neutral-600">{t("portal.dispute.sentNote")}</p>
          <ButtonRow>
            {/* ⚠ THE REFERENCE IS A DOOR AND NOT A DECORATION (hard-won law 2):
                it opens `CWP-051`, which is what makes the two screens one
                journey rather than a number nobody can look up. */}
            <ErrandLink
              label={t("portal.dispute.track")}
              to={`/requests/${encodeURIComponent(reference)}`}
            />
          </ButtonRow>
        </Card>
      </div>
    );
  }

  return (
    <div data-screen="CWP-055">
      {head}
      <Stepper
        steps={[t("portal.dispute.step1"), t("portal.dispute.step2")]}
        current={step}
      />
      <TwoCol
        main={
          <Card testId="dispute">
            {/* ⚠ The card's own heading was the PAGE title word for word, and
                the page has one now — so it is drawn once (B14 rule 32). */}
            {/* B14 rule 32 — one sentence, and B14 rule 31: the bill is its
                number, which is what is printed on the paper. */}
            <p
              className="text-body text-neutral-600"
              data-bill-number={props.number}
              data-bill-amount={amount ?? ""}
            >
              {amount === null
                ? t("portal.dispute.lead", { number: props.number })
                : t("portal.dispute.leadWithAmount", { number: props.number, amount })}
            </p>
            {step === 1 ? (
              <>
                {/* ⚠ **A LIST OF FIVE, NOT AN EMPTY BOX** — the drawing's
                    `Select`, and the reason it gives is the one that matters:
                    an open text box asks a customer to compose an argument
                    before they have said what is wrong, and most of them will
                    close the page instead. It also arrived at the clerk as
                    five hundred different sentences meaning four things.
                    ⚠ **THE OPTIONS ARE THE FIVE REAL ONES** and *Something
                    else* is one of them, so nothing is refused — *Why* below
                    is required either way. */}
                <FormField id="dispute-what" label={t("portal.dispute.whatLabel")} required>
                  <SelectInput
                    id="dispute-what"
                    value={what}
                    placeholder={t("portal.dispute.whatPlaceholder")}
                    options={REASONS.map((key) => ({
                      value: t(`portal.dispute.reason.${key}`),
                      label: t(`portal.dispute.reason.${key}`),
                    }))}
                    onChange={setWhat}
                  />
                </FormField>
                <FormField
                  id="dispute-reason"
                  label={t("portal.dispute.reasonLabel")}
                  helper={t("portal.dispute.reasonHelper")}
                  required
                >
                  <TextInput id="dispute-reason" multiline value={reason} onChange={setReason} />
                </FormField>
                <FormField
                  id="dispute-reading"
                  label={t("portal.dispute.ownReadingLabel")}
                  helper={t("portal.dispute.ownReadingHelper")}
                >
                  <TextInput id="dispute-reading" value={ownReading} onChange={setOwnReading} />
                </FormField>
                {consequences}
                <ButtonRow>
                  <CommitButton
                    label={t("portal.dispute.check")}
                    working={false}
                    ready={ready}
                    reason={t("portal.dispute.checkHeld")}
                    onClick={() => setStep(2)}
                  />
                </ButtonRow>
              </>
            ) : (
              <>
                <KVList
                  rows={[
                    {
                      key: "bill",
                      label: t("portal.dispute.rowBill"),
                      // ⚠ **THE NUMBER AND THE AMOUNT, WHICH IS THE DRAWING'S
                      // OWN FIRST ROW** — `Bill  BL-2608-0141 · $142.18`. A
                      // check-and-send step that names the bill and not the
                      // figure asks a customer to confirm a claim about money
                      // without showing them the money.
                      value: (
                        <span data-check="bill">
                          {props.number}
                          {amount === null ? "" : ` · ${amount}`}
                        </span>
                      ),
                    },
                    ...(bill !== null && bill.period_start !== null && bill.period_end !== null
                      ? [
                          {
                            key: "period",
                            label: t("portal.dispute.rowPeriod"),
                            value: (
                              <span data-check="period">
                                {t("portal.dispute.periodRange", {
                                  from: asDate(bill.period_start),
                                  to: asDate(bill.period_end),
                                })}
                              </span>
                            ),
                          },
                        ]
                      : []),
                    {
                      key: "what",
                      label: t("portal.dispute.rowWhat"),
                      value: <span data-check="what">{what}</span>,
                    },
                    {
                      key: "reason",
                      label: t("portal.dispute.rowReason"),
                      value: <span data-check="reason">{reason}</span>,
                    },
                    ...(ownReading.trim() !== ""
                      ? [
                          {
                            key: "own_reading",
                            label: t("portal.dispute.rowOwnReading"),
                            value: <span data-check="own_reading">{ownReading}</span>,
                          },
                        ]
                      : []),
                  ]}
                />
                {consequences}
                {/* `DEF-CWP-9164` — the way back on the LEFT, Send on the RIGHT. */}
                <WizardFooter
                  back={
                    // ⚠ **A WAY BACK TO STEP 1** (`DEF-CWP-4202` row 55.4, and
                    // the same missing control `DEF-CWP-4182` found on
                    // `CWP-042`). The customer had no route back to what they
                    // had typed once they moved on: the browser's own back
                    // button leaves this screen entirely.
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={working}
                      data-action="back-to-step-1"
                      onClick={() => setStep(1)}
                    >
                      {t("portal.dispute.back")}
                    </Button>
                  }
                  forward={
                    // ⚠ NOT the danger tier (r10 rule 6): questioning a bill
                    // destroys nothing — it is the opposite of destructive.
                    <CommitButton
                      label={t("portal.dispute.send")}
                      working={working}
                      ready={ready}
                      reason={t("portal.dispute.sendHeld")}
                      onClick={() => void send()}
                    />
                  }
                />
              </>
            )}
            {refused !== null ? (
              <Announced tone="error" className="text-body font-semibold text-danger-700" data-refused="">
                {refused}
              </Announced>
            ) : null}
          </Card>
        }
        rail={
          <>
            <Card testId="dispute-while-queried">
              <SectionTitle>{t("portal.dispute.whileQueriedTitle")}</SectionTitle>
              <p className="text-body text-neutral-600">{t("portal.dispute.whileQueried")}</p>
            </Card>
          </>
        }
      />
    </div>
  );
}
