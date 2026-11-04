// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-004 (EP-CWP-02) — check and pay, and the masked name that
//           makes it safe. Screens: CWP-003 · wireframes/CWP-003.png
// Rules:    08-screen-layouts.md CWP-003 (T2: Stepper ✓·2·3 → main Card
//           [KVList Bill / Billed to `M. A••••••` / Due · TotalRow Owing ·
//           section title HOW YOU ARE PAYING · FormField card number · TwoUp
//           Expires* | Security code* · FormField Email (optional) ·
//           ConsequenceBox 3 bullets · ButtonRow Pay $142.18 ✓] · rail [Panel
//           WHY SO LITTLE IS SHOWN · Panel.Warning]) · BR-CWP-019/020 (the
//           amount owing and a MASKED name, masked SERVER-SIDE) · BR-CWP-021
//           (a guest sees an amount and a status, never a person) ·
//           BR-CWP-023 (five wrong tries — and step 2 is the SAME door) ·
//           BR-CWP-057 (a token, a brand, a last four) · BR-CWP-058 (the
//           screen shows where the payment lands BEFORE it commits) ·
//           B14 rule 21 (`src/portal/` is on route-b-migrated.txt) · rule 31
//           (no database id is a visible value) · rule 32 (one sentence per
//           section) · rule 33 (a refusal is five or six words) · rule 35 (the
//           catalogue writes the words) · rule 36 (compose the kit)
// Tests:    src/portal/guest/QuickPayCheck.dom.test.tsx
// Impacts:  06-backend/apps/portal/guest_api.bill_pay · guestClient.ts ·
//           QuickPayDone.tsx (the receipt it hands on)
// ───────────────────────────────────────────────────────
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { PortalRefusal } from "../components/a11y";

import { lookUpBill, payBill, tokeniseCard } from "../api/guestClient";
import type { BillLookupView, GuestPaymentReceipt } from "../api/guestClient";
import { usePortalDate } from "../components/regional";
import { newDraftToken } from "../draftToken";
import { GuestPage } from "./GuestPage";
import {
  Card,
  ConsequenceBox,
  ErrandLink,
  FormField,
  KVList,
  SectionTitle,
  Stepper,
  TextInput,
  TotalRow,
  TwoCol,
  TwoUp,
  usePortalPath,
} from "../components/primitives";
import { HeldCommit } from "../components/heldCommit";

/** The three steps `08-screen-layouts.md` draws across CWP-002 · 003 · 004. */
const STEP_KEYS = ["find", "check", "done"] as const;

/** What step 1 hands on. ⚠ **THE POSTCODE TRAVELS IN ROUTER STATE AND NOT IN
 *  THE ADDRESS** — the reasoning `QuickPayPage.tsx` records for step 1 holds
 *  here unchanged: a bill number and the postcode of somebody's home in a URL
 *  end up in access logs, in browser history and in a `Referer` header. */
export interface QuickPayHandoff {
  billNumber: string;
  postcode: string;
}

function handoffFrom(state: unknown): QuickPayHandoff | null {
  if (typeof state !== "object" || state === null) {
    return null;
  }
  const candidate = state as Partial<QuickPayHandoff>;
  if (typeof candidate.billNumber !== "string" || typeof candidate.postcode !== "string") {
    return null;
  }
  return { billNumber: candidate.billNumber, postcode: candidate.postcode };
}

/**
 * `CWP-003` — confirm it is the right bill, then pay it.
 *
 * ⚠ **THE MASKED NAME IS RENDERED EXACTLY AS IT ARRIVED, AND THAT IS THE WHOLE
 * SECURITY PROPERTY OF THIS SCREEN** (`US-CWP-004` §5, verbatim: *"Masked
 * server-side. Never send the full name and mask in the browser"*). Masking
 * again here would be a second implementation of `BR-CWP-020` and the two would
 * drift; masking *instead of* here would mean the browser had already been told
 * the name, whatever it drew. `M. A••••••` lets whoever holds the bill confirm
 * they have the right one without the page disclosing who lives there — a bill
 * goes astray, gets photographed, gets left in a hallway.
 *
 * ⚠ **THE SERVICE ADDRESS IS NOT DRAWN, AND ITS ABSENCE IS DELIBERATE.** The
 * wireframe puts *Service address* in the `KVList`. `BR-CWP-021` — *a guest
 * sees an amount and a status, never a person* — and `guest_fields.py`'s
 * `NEVER_ON_A_GUEST_RESPONSE` (which names `address` and `postal_code`) between
 * them mean the server does not serve one, so this screen cannot draw one: the
 * six keys `bill_lookup` answers were reserved as data before the code existed
 * *"so the wave that builds it cannot quietly widen it"*. The holder already
 * typed the postcode; the street would tell them something they had not.
 *
 * ⚠ **THE FIGURE IS RE-READ ON EVERY LOAD, NEVER CARRIED** (`US-CWP-003` §5,
 * and `US-CWP-004` §7: *"the amount owing at the moment of commit"*). What step
 * 1 hands on is the PAIR, not the answer, so this screen asks again — which is
 * also what puts step 2 behind the SAME five-tries lockout rather than beside
 * it (`BR-CWP-023`).
 *
 * ⚠ **AND THERE IS NO FEE LINE.** `OQ-1394` is CLOSED (2026-09-04): absorbed or
 * surcharged, behind a per-tenant switch, and beta ships ABSORBED. A surcharge
 * would have to be computed, disclosed here BEFORE the button, and checked
 * against the customer's state; the edge refuses rather than guessing, so what
 * the consequence box promises is what the person pays.
 */
export function QuickPayCheck(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const location = useLocation();
  const navigate = useNavigate();
  const path = usePortalPath();
  const handoff = handoffFrom(location.state);

  const [bill, setBill] = useState<BillLookupView | null>(null);
  const [loading, setLoading] = useState(handoff !== null);
  const [refused, setRefused] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  const [cardNumber, setCardNumber] = useState("");
  const [expires, setExpires] = useState("");
  const [securityCode, setSecurityCode] = useState("");

  // Hard rule 6 — ONE token per visit, minted once. A double press, a retried
  // request and a refreshed fetch all carry it, so the rails collapse them into
  // one payment rather than taking the money twice.
  const attemptToken = useRef(newDraftToken());

  const billNumber = handoff?.billNumber ?? "";
  const postcode = handoff?.postcode ?? "";

  const reread = useCallback(async () => {
    if (handoff === null) {
      return;
    }
    setLoading(true);
    setRefused(null);
    try {
      setBill(await lookUpBill(billNumber, postcode, client));
    } catch (error) {
      setBill(null);
      setRefused(refusalText(t, error));
    } finally {
      setLoading(false);
    }
    // `handoff` is rebuilt from `location.state` on every render, so the two
    // primitives are the dependency — an object identity here would re-fetch
    // forever.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [billNumber, postcode, client, t]);

  useEffect(() => {
    void reread();
  }, [reread]);

  async function pay() {
    if (bill === null) {
      return;
    }
    // ⚠ TOKENISED BEFORE ANYTHING IS POSTED. The number is reduced to a brand
    // and a last four inside `tokeniseCard` and is not in the body, in state,
    // or in any type on the wire (`US-CWP-004` §5).
    const instrument = tokeniseCard(cardNumber);
    if (instrument === null) {
      setRefused(t("portal.quickPay.cardLooksWrong"));
      return;
    }
    setWorking(true);
    setRefused(null);
    try {
      const receipt: GuestPaymentReceipt = await payBill(
        bill.number,
        {
          postcode,
          amount: bill.amount.amount ?? "",
          instrument,
          // ⚠ **`null`, AND THE FIELD IT USED TO CARRY IS NO LONGER ASKED
          // FOR** (`DEF-CWP-3951`). The form collected an address, validated
          // it, sent it, and NOTHING sent anything to it: `record_payment`
          // queues a receipt to the ACCOUNT's own contacts under the tenant's
          // election — a different address — and `BR-NOT-013` means nothing
          // dispatches in this release at all. The helper under the box read
          // *"Optional. We use it only for this receipt."*, which is a
          // guarantee the product does not provide, in a customer's own words
          // (hard-won law 1, in a piece of copy).
          receipt_email: null,
          attempt_token: attemptToken.current,
        },
        client,
      );
      navigate(path("/pay/done"), { state: { receipt } });
    } catch (error) {
      setRefused(refusalText(t, error));
    } finally {
      setWorking(false);
    }
  }

  //: ⚠ **THE PUBLISHED FORMATTER, NOT A FOURTH ONE** (`DEF-CWP-4197`). A guest
  //: screen is inside `PortalRegionalProvider` from birth — `GuestFrame` is one
  //: of its two callers by design — so the tenant's own format and zone are
  //: available here and this screen was simply never wired to them. Writing a
  //: date helper in this file is the thing `DEF-CWP-3994` exists to stop.
  //:
  //: ⚠ **AND IT IS CALLED HERE, ABOVE THE `handoff === null` RETURN, BECAUSE A
  //: HOOK AFTER AN EARLY RETURN IS NOT A STYLE POINT** (`DEF-CWP-4390`). It sat
  //: below that return from 2026-09-06, so on the render where a handoff
  //: ARRIVES React sees one more hook than it saw last time and throws
  //: "Rendered more hooks than during the previous render" — the guest loses
  //: the card they had just typed. `tsc` and vitest are both green over it and
  //: eslint's `react-hooks/rules-of-hooks` is the only thing in this repository
  //: that can see it, which is `DEF-CUS-3935`'s whole argument for G98.
  const asDate = usePortalDate();

  // ⚠ **ARRIVING HERE WITH NOTHING IS NOT AN ERROR STATE, IT IS A WRONG TURN**
  // — a reload, a bookmark, a link somebody kept. The screen says so in one
  // sentence and offers the door back, LIVE, by address (`DEF-CWP-3925`: the
  // mirror of dead UI is a live screen behind a dead control).
  if (handoff === null) {
    return (
      <div data-screen="CWP-003">
        <Stepper steps={STEP_KEYS.map((key) => t(`portal.quickPay.step.${key}`))} current={2} />
        <Card testId="quick-pay-no-bill">
          <PageHeader
            kicker={t("portal.quickPay.checkKicker")}
            title={t("portal.quickPay.startAgainTitle")}
          />
          <p className="text-body leading-relaxed text-neutral-600" data-no-handoff="">
            {t("portal.quickPay.startAgainBody")}
          </p>
          <div className="mt-3">
            <ErrandLink label={t("portal.quickPay.startAgain")} to="/pay" size="default" />
          </div>
        </Card>
      </div>
    );
  }

  const payable = bill !== null && bill.status === "payable";
  const ready = cardNumber.trim() !== "" && expires.trim() !== "" && securityCode.trim() !== "";


  return (
    <div data-screen="CWP-003">
      <Stepper steps={STEP_KEYS.map((key) => t(`portal.quickPay.step.${key}`))} current={2} />
      <TwoCol
        main={
          <Card testId="quick-pay-check">
            <PageHeader
              kicker={t("portal.quickPay.checkKicker")}
              title={t("portal.quickPay.checkTitle")}
              rollup={t("portal.quickPay.checkLead")}
            />
            <hr className="border-neutral-200" />

            {loading ? (
              <p className="mt-4 text-body text-neutral-600" data-loading="">
                {t("portal.quickPay.rereading")}
              </p>
            ) : null}

            {bill !== null ? (
              <div className="mt-4" data-bill-found="">
                <KVList
                  rows={[
                    {
                      key: "number",
                      label: t("portal.quickPay.billNumber"),
                      // B14 rule 31 — the number off the paper, never a uuid.
                      value: <span data-bill-number="">{bill.number}</span>,
                    },
                    {
                      key: "billed-to",
                      label: t("portal.quickPay.billedTo"),
                      // ⚠ SERVER-MASKED, RENDERED VERBATIM (`BR-CWP-020`).
                      value: <span data-masked-name="">{bill.masked_name}</span>,
                    },
                    {
                      key: "due",
                      label: t("portal.quickPay.due"),
                      //: The ATTRIBUTE keeps the server's own string — it is
                      //: what a test and a walkthrough read — and the VISIBLE
                      //: value is the tenant's format. The two must not be the
                      //: same string, which is what made the fault invisible.
                      value: <span data-due-on={bill.due_on ?? ""}>{asDate(bill.due_on) || "—"}</span>,
                    },
                  ]}
                />
                <TotalRow
                  label={t("portal.quickPay.owing")}
                  // Hard rule 2 — the screen renders `display` and never formats
                  // money itself.
                  value={<span data-money={bill.amount.amount ?? ""}>{bill.amount.display}</span>}
                  testKey="owing"
                />
                {bill.replaced_by !== null ? (
                  <p
                    className="mt-2 text-body text-neutral-600"
                    data-replaced-by={bill.replaced_by}
                  >
                    {t("portal.quickPay.replacedBy", { number: bill.replaced_by })}
                  </p>
                ) : null}
              </div>
            ) : null}

            {payable && bill !== null ? (
              <div className="mt-4">
                <SectionTitle>{t("portal.quickPay.howPaying")}</SectionTitle>
                <div className="mt-3 flex flex-col gap-3">
                  <FormField id="quickpay-card" label={t("portal.quickPay.cardNumber")} required>
                    <TextInput
                      id="quickpay-card"
                      value={cardNumber}
                      onChange={setCardNumber}
                      placeholder={t("portal.quickPay.cardNumberExample")}
                    />
                  </FormField>
                  <TwoUp>
                    <FormField id="quickpay-expires" label={t("portal.quickPay.expires")} required>
                      <TextInput
                        id="quickpay-expires"
                        value={expires}
                        onChange={setExpires}
                        placeholder={t("portal.quickPay.expiresExample")}
                      />
                    </FormField>
                    <FormField
                      id="quickpay-security"
                      label={t("portal.quickPay.securityCode")}
                      required
                    >
                      <TextInput
                        id="quickpay-security"
                        value={securityCode}
                        onChange={setSecurityCode}
                      />
                    </FormField>
                  </TwoUp>
                  {/* ⚠ **THE RECEIPT-EMAIL BOX IS GONE, AND THAT IS THE FIX
                      RATHER THAN A REDUCTION IN SCOPE** (`DEF-CWP-3951`). It
                      was accepted, validated and dropped: nothing sent to it,
                      nothing checked that anything did, and every test passed
                      because every test asked whether the input was ACCEPTED
                      and none asked what became of it.

                      ⚠ **THE ALTERNATIVE NEEDS A RULING AND THIS DOES NOT.**
                      Writing an unverified address supplied by an anonymous
                      caller into a notification row against somebody else's
                      account is a DISCLOSURE decision and a spam-relay
                      surface — `US-CWP-004` §4 is explicit that a guest may be
                      a NEIGHBOUR — so it is not a plumbing job a lane takes.
                      Until it is ruled, the honest thing is not to ask.

                      ⚠ **AND THE SENTENCE HERE IS A HOLD WITH A TEST THAT
                      FIRES WHEN IT EXPIRES** (hard-won law 2's mirror,
                      `DEF-CWP-3925`): `QuickPayCheck.dom.test.tsx` asserts
                      that this note and the server's `receipt_sent` agree, so
                      the day the product can send a receipt the suite goes red
                      and names this block. A hold with no such test is a
                      promise nobody is keeping. */}
                  <p className="text-base text-neutral-600" data-receipt-email-held="">
                    {t("portal.quickPay.receiptEmailHeld")}
                  </p>

                  {/* `BR-CWP-058` — where the money lands, BEFORE the button,
                      because afterwards the row can only be reversed.

                      ⚠ **THE TWO FACTS ARE ALSO ON THE WRAPPER**, and that is
                      not decoration: the sentence itself is the catalogue's (B14
                      rule 35), so a test asserting *"this box names the figure
                      and the bill"* would otherwise be asserting a TRANSLATION
                      rather than a screen — and would go quiet in ten languages
                      the day one of them was reworded. */}
                  <div
                    data-pay-amount={bill.amount.display ?? ""}
                    data-pay-against={bill.number}
                  >
                    <ConsequenceBox
                      heading={t("portal.quickPay.consequenceHeading")}
                      bullets={[
                        t("portal.quickPay.consequencePays", {
                          amount: bill.amount.display,
                          number: bill.number,
                        }),
                        t("portal.quickPay.consequenceNoAccount"),
                        t("portal.quickPay.consequenceReference"),
                      ]}
                    />
                  </div>

                  {refused !== null ? (
                    <PortalRefusal data-quick-pay-refused="">{refused}</PortalRefusal>
                  ) : null}

                  {/* ⚠ **`HeldCommit` AND NOT `CommitButton` — `DEF-CWP-4866`.**
                      The kit puts a refusal on `title=` and NOWHERE else:
                      measured in a browser on 2026-09-11, this control carried
                      `title="Fill in the card boxes first."`, `aria-label` null, `aria-describedby` null,
                      and the sentence appeared nowhere in the page text. A
                      tooltip needs a mouse and a second of hover, so on a phone
                      — where most people pay a bill — the reason a button will
                      not work did not exist. `HeldButton`, in the same kit
                      file, has rendered exactly this kind of sentence visibly
                      all along. The wrapper composes the two and is deleted the
                      day `CommitButton` says its own reason. */}
                  <HeldCommit
                    label={t("portal.quickPay.pay", { amount: bill.amount.display })}
                    working={working}
                    ready={ready}
                    reason={t("portal.quickPay.needCard")}
                    onClick={() => void pay()}
                  />

                  {/* ⚠ **THE WAY BACK, BESIDE THE BUTTON** (`CR-085`, and the
                      drawing's own *Go back and change something*). This screen
                      describes itself as *the last screen at which anything can
                      be changed*, and until now nothing on it could change
                      anything: the `Stepper` is a list of `<li>`s rather than
                      links, and the only door to `/pay` lived inside the
                      *arrived with nothing* branch above. A visitor who typed
                      one digit of the bill number wrong read a masked name that
                      was not theirs and had nowhere to go but the browser's own
                      back button.

                      ⚠ **QUIET, AND SECOND.** The wireframe is explicit that
                      the button naming the figure is the last thing read before
                      money moves, so the way back is an ordinary link under it
                      rather than a second button competing with it.

                      ⚠ **AND IT MINTS NO KEY.** `portal.quickPay.startAgain` —
                      *Find my bill →* — is already written natively in all
                      eleven catalogues and is exactly this sentence (B14 rule
                      35). */}
                  <div data-pay-again="">
                    <ErrandLink label={t("portal.quickPay.startAgain")} to="/pay" />
                  </div>
                </div>
              </div>
            ) : null}

            {bill !== null && !payable ? (
              <p className="mt-4 text-body text-neutral-600" data-nothing-to-pay="">
                {t("portal.quickPay.nothingToPay")}
              </p>
            ) : null}

            {bill === null && !loading && refused !== null ? (
              <PortalRefusal data-quick-pay-refused="">{refused}</PortalRefusal>
            ) : null}
          </Card>
        }
        rail={
          <>
            <Panel as="aside" title={t("portal.quickPay.whySoLittle")}>
              <p className="text-body leading-relaxed text-neutral-600" data-why-so-little="">
                {t("portal.quickPay.whySoLittleBody")}
              </p>
            </Panel>
            <Panel as="aside" tone="warning" title={t("portal.quickPay.triesTitle")}>
              <p className="text-body leading-relaxed text-neutral-600" data-five-tries="">
                {t("portal.quickPay.triesBody")}
              </p>
            </Panel>
          </>
        }
      />
    </div>
  );
}

/** `CWP-003` at `/{tenant}/portal/pay/check`. Composes `GuestPage` for the
 *  reason `QuickPayPage.tsx` gives: `CR-068` R8 puts the holding-page check
 *  there, so every guest route inherits it. */
export function QuickPayCheckPage(props: { client?: ApiClient }) {
  return (
    <GuestPage client={props.client}>
      <QuickPayCheck client={props.client} />
    </GuestPage>
  );
}
