// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-062 (EP-CWP-11) — *"stop or restart service, and the screen
//           names the cheaper option."* Screen: CWP-052 (blueprint `P38`)
// Rules:    BR-CWP-080 (a disconnect leaves the account OPEN and standing
//           charges keep running) · BR-CWP-081 (where stopping is more
//           expensive than closing, the screen says so, WITH BOTH FIGURES) ·
//           BR-CWP-056 (a control that may not be used is disabled WITH its
//           reason) · B14 rule 6 (the danger tier is for a destructive commit)
//           · rule 11 (the consequence box) · rule 21 · rule 31 · rule 32 ·
//           rule 33 · rule 35 · rule 36 (compose the kit) · CLAUDE.md hard
//           rule 2 (money displays at 2 dp)
//           · CR-085 task (c), the signed-off wireframes s20–s23: stop is a
//           JOURNEY, not one form. PO ruling: *"please show all 4 screens -
//           address, when , about you, check; and show seperate screens for
//           stop - when you develope you can use same code internally"*
// Defects:  DEF-CWP-4874 — the missing fourth step (*where the final bill
//           goes*) and the four-date timeline were recorded in this file's own
//           docstring and NOWHERE else. The gap is unchanged and correct; the
//           RECORD is now `OQ-CWP-1767` + `10-execution-plan.md` §12, and the
//           docstring cites them. See `StopCheck`'s note below.
// Tests:    src/portal/requests/StopOrRestart.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getStopOrRestart` ·
//           `askToStopOrRestart`
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

import { Button } from "@/components/Button";
import { Panel } from "@/components/Panel";
import {
  ButtonRow,
  Card,
  CommitButton,
  ConsequenceBox,
  FormField,
  KVList,
  RadioList,
  SectionTitle,
  Stepper,
  TextInput,
  TotalRow,
  TwoCol,
  WizardFooter,
} from "../components/primitives";
import { useCurrentAccount } from "../shell/currentAccount";
import type { PortalAccount } from "../api/portalClient";
// ⚠ **DATES GO THROUGH THE TENANT'S OWN FORMAT, NEVER STRAIGHT TO THE
// SCREEN** (`DEF-CWP-4204`). Pine Hill asks for `MM/DD/YYYY`; this screen
// printed the wire's `2026-09-06`. `usePortalDate` returns the server's
// string unchanged when a tenant has stated no format — declining to say
// is honest, inventing one for a utility in Berlin is what shipped a
// five-hour error. Wave M took this fix (`DEF-CWP-4138`) and wave L took
// it (`DEF-CWP-4178`); wave I's five screens were never moved.
import { usePortalDate } from "../components/regional";
import { formatMoney } from "../signin/Enrol";
import {
  askToStopOrRestart,
  getMyDetails,
  getStopOrRestart,
  type PortalStopOrRestart,
} from "../api/portalClient";
import { Announced } from "../components/a11y";
import { ButtonReason } from "../components/primitives";

/**
 * `CWP-052` — stop the supply for a while, and be told if leaving is cheaper.
 *
 * ⚠ **THE COMPARISON IS THE SCREEN AND EVERY FIGURE IN IT IS THE SERVER'S.**
 * `US-CWP-062` §7: *"the recommendation must be computed, not hardcoded — a
 * screen that always says stopping is cheaper is wrong for a long absence."*
 * Nothing here multiplies, adds or compares: `cheaper` arrives already decided,
 * and where it could not be decided `no_verdict` names why. That is what makes
 * *for this property, stopping is cheaper* a true sentence rather than a
 * slogan.
 *
 * ⚠ **AND THE MOST IMPORTANT LINE ON THE SCREEN IS NOT A NUMBER**
 * (`BR-CWP-080`, TC-4). *The account stays open* prevents the most expensive
 * misunderstanding in the product — assuming a stopped supply stops the bill —
 * and it is served as a fact rather than composed here, so no future edit can
 * quietly drop it.
 *
 * ⚠ **`$0.00` IS NEVER SHOWN AS A SAVING** (TC-8). A utility whose plan states
 * no standing charge gets a sentence saying we cannot work the comparison out,
 * not a zero that would make stopping look free forever.
 *
 * ⚠ **THE COMMIT IS THE DANGER TIER AND IT IS EARNED** (B14 rule 6,
 * `08-screen-layouts.md`: *"Second danger-tier commit"*). Asking to have the
 * supply turned off is a destructive commit from the customer's side, even
 * though the row it writes is an ordinary service request.
 */
/** The three steps of the stop journey, in the order the wireframe draws them. */
type StopStep = "what" | "when" | "check";

export function StopOrRestartView(props: { accountId: string; accounts?: PortalAccount[] }) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  const [, setCurrentAccount] = useCurrentAccount();
  const [step, setStep] = useState<StopStep>("what");
  /**
   * ⚠ **THE PAUSE AND THE STOP ARE ONE FIELD, AND THE WIREFRAME ASKS THE
   * QUESTION BEHIND IT.** s20 opens on *"Stop everything, or just part?"* with
   * *Pause for a season* beside it, because a large share of stop requests are
   * seasonal absences and a customer should not have to price the difference
   * themselves. What this product actually holds is one optional date —
   * `start_again` — so the choice below is that field's two states and nothing
   * more: a date, or no date yet. `POST stop-or-restart/ask` accepts no per
   * service scope, so *stop trash only* is not a thing that can be asked for
   * here, and drawing it would be a control that posts nowhere (hard-won law 2).
   */
  const [comingBack, setComingBack] = useState<"yes" | "later">("yes");
  const [stopFrom, setStopFrom] = useState("");
  const [startAgain, setStartAgain] = useState("");
  const [reason, setReason] = useState("");
  /**
   * ⚠ **THE PHONE IS WHY EVERY REQUEST FROM THIS SCREEN WAS REFUSED, AND ONLY
   * PRESSING THE BUTTON COULD HAVE FOUND IT (`CR-085` task (c)).**
   * `create_from_portal` requires `applicant_phone` — *"the form's own promise
   * is `we ring you only if we need to`, and a promise to ring needs a way to
   * ring"* — and this screen sent a stop date, a restart date and a reason and
   * nothing else. Every press answered **422 VAL-001 `applicant_phone`**. Nine
   * backend cases, eight screen tests, `tsc` and every gate were green over it,
   * because the refusal came from the running product agreeing with itself.
   * It went unnoticed because `/stop-or-restart` had no door anywhere in the
   * portal until 2026-09-08, so nobody had ever reached the button.
   *
   * ⚠ **PREFILLED FROM `GET /portal/my-details`, NOT ASKED COLD.** A signed-in
   * customer typing a phone number we already hold is a form asking a question
   * it knows the answer to. Where the login's accounts disagree the server
   * sends `null` rather than a majority (`phone_varies`), and then the box is
   * empty and the commit says what it is waiting for.
   */
  const [contact, setContact] = useState({ name: "", email: "", phone: "" });
  const contactSeeded = useRef(false);
  const [answer, setAnswer] = useState<PortalStopOrRestart | null>(null);
  const [failed, setFailed] = useState(false);
  const [working, setWorking] = useState(false);
  const [sent, setSent] = useState<string | null>(null);

  const accounts = props.accounts ?? [];
  /**
   * ⚠ **s20 IS SKIPPED FOR THE CUSTOMER WITH ONE PROPERTY, AND THAT IS THE
   * WIREFRAME'S OWN STATE RATHER THAN A SHORTCUT:** *"One account with no
   * optional services means nothing to choose, so this step does not render …
   * A chooser with one option is furniture, exactly as everywhere else."* The
   * chooser writes to the SHARED account context the switcher in the bar uses,
   * so the two can never disagree about which property is being stopped.
   */
  const many = accounts.length > 1;
  const chosen = accounts.find((row) => row.id === props.accountId) ?? null;

  // ⚠ **THE COMPARISON IS RE-ASKED OF THE SERVER WHEN EITHER DATE MOVES**, and
  // never recomputed in the browser from a monthly figure it already holds.
  // Multiplying here would be a second arithmetic over money — the thing
  // `12-reuse-map.md` calls *"a clerk and a customer arguing on the phone"*.
  useEffect(() => {
    if (!stopFrom) {
      setAnswer(null);
      return;
    }
    let live = true;
    setFailed(false);
    getStopOrRestart(props.accountId, {
      stop_from: stopFrom,
      start_again: startAgain || null,
    })
      .then((result) => {
        if (live) setAnswer(result);
      })
      .catch(() => {
        if (live) {
          setAnswer(null);
          setFailed(true);
        }
      });
    return () => {
      live = false;
    };
  }, [props.accountId, stopFrom, startAgain]);

  // The contact this login already has on file, read once and written into the
  // boxes below unless the customer has already typed over them.
  useEffect(() => {
    let live = true;
    getMyDetails()
      .then((details) => {
        if (!live || contactSeeded.current) return;
        contactSeeded.current = true;
        setContact({
          name: details.legal_name ?? "",
          email: details.email ?? "",
          phone: details.phone ?? "",
        });
      })
      // ⚠ A contact we could not read is an EMPTY box, never a blocked screen:
      // the customer can type one, and the commit says what it is waiting for.
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  const restartBeforeStop = Boolean(stopFrom && startAgain && startAgain <= stopFrom);
  const hasPhone = contact.phone.trim().length > 0;

  // ⚠ `DEF-CWP-4000` — the shared `components/PageHeader.tsx`, never a second
  // one. This screen is NOT one of the four the drawing gives a step bar
  // instead of a head ({CWP-038, CWP-042, CWP-047, CWP-055}): it is a form on a
  // page of its own, and the audit records it as missing its title.
  const head = <PageHeader kicker={t("portal.kicker.requests")} title={t("portal.stopRestart.title")} />;

  if (sent !== null) {
    return (
      <div data-screen="CWP-052">
        {head}
        <Card testId="stop-restart-sent">
          {/* F-02 / F-04: the confirmation takes focus; the reference is heard. */}
          <Announced
            tone="status"
            as="div"
            say={`${t("portal.stopRestart.sentReference", { reference: sent })} ${t("portal.stopRestart.sentStaysOpen")}`}
          >
            <SectionTitle>{t("portal.stopRestart.sentTitle")}</SectionTitle>
          </Announced>
          <p className="text-body text-neutral-700" data-stop-reference="">
            {t("portal.stopRestart.sentReference", { reference: sent })}
          </p>
          {/* ⚠ THE CONFIRMATION REPEATS IT. Nothing has been turned off and the
              bill has not stopped; a screen that went quiet here would let the
              customer walk away believing both. */}
          <p className="text-body text-neutral-700" data-stop-still-open="">
            {t("portal.stopRestart.sentStaysOpen")}
          </p>
        </Card>
      </div>
    );
  }

  /**
   * ⚠ **THREE STEPS RATHER THAN THE DRAWING'S FOUR, AND THE MISSING ONE IS
   * NAMED.** s22 — *where the final bill goes* — is the step this product
   * cannot serve at all (see the long note above `StopCheck`'s read-back
   * below); the other three are drawn.
   *
   * ⚠ **AND STEP ONE IS NOT SKIPPED FOR A ONE-PROPERTY CUSTOMER, WHICH IS
   * WHERE THIS PARTS COMPANY WITH s20 ON PURPOSE.** The drawing skips it
   * because for most people it holds only a chooser with one option, which is
   * furniture. Here it also asks *are you coming back* — a question every
   * customer must answer and the one that decides whether stopping or leaving
   * is cheaper — so the step earns its place with one property as well as
   * four. Only the chooser itself disappears.
   */
  const steps = [
    t("portal.stopRestart.step1"),
    t("portal.stopRestart.step2"),
    t("portal.stopRestart.step3"),
  ];
  const stepNumber = { what: 1, when: 2, check: 3 }[step];

  const consequences = (
    <ConsequenceBox
      heading={t("portal.stopRestart.consequenceHeading")}
      bullets={[
        <span key="off" data-consequence-code="supply_off">
          {stopFrom
            ? t("portal.stopRestart.consequence.supplyOff", { date: asDate(stopFrom) })
            : t("portal.stopRestart.consequence.supplyOffUndated")}
        </span>,
        // ⚠ **THE LINE THE WHOLE SCREEN EXISTS FOR** (BR-CWP-080).
        <span key="open" data-consequence-code="stays_open">
          {t("portal.stopRestart.consequence.staysOpen")}
        </span>,
        <span key="charges" data-consequence-code="charges_run">
          {answer?.standing_charge_monthly
            ? t("portal.stopRestart.consequence.chargesRun", {
                amount: formatMoney(answer.standing_charge_monthly, answer.currency),
              })
            : t("portal.stopRestart.consequence.chargesRunUnknown")}
        </span>,
      ]}
    />
  );

  const frame = (main: ReactNode, rail: ReactNode) => (
    <div data-screen="CWP-052" data-step={step}>
      {head}
      {/* ⚠ **A JOURNEY, NOT A FORM — `CR-085` task (c).** This screen asked for
          two dates, a reason and a destructive commit on one card, with no
          read-back before the press and no step bar to say how far along
          anybody was. The wireframes draw four steps and the PO ruled that stop
          gets *"seperate screens"* of its own even though it shares this code
          with start service underneath. */}
      <Stepper current={stepNumber} steps={steps} />
      <TwoCol main={main} rail={rail} />
    </div>
  );

  /* ══ STEP 1 · WHICH PROPERTY, AND WHAT YOU NEED (wireframe s20) ══════════ */
  if (step === "what") {
    return frame(
      <Card testId="stop-what">
        {many ? (
          <>
            <SectionTitle>{t("portal.stopRestart.whichProperty")}</SectionTitle>
            <RadioList
              name={t("portal.stopRestart.whichProperty")}
              value={props.accountId}
              options={accounts.map((row) => ({
                value: row.id,
                // B14 rule 31 — `account_no` is the number printed on a bill,
                // not a database id, and the address is what a person knows
                // the property by.
                label: row.label,
                hint: row.account_no,
              }))}
              onChange={setCurrentAccount}
            />
          </>
        ) : null}
        <SectionTitle>{t("portal.stopRestart.whatDoYouNeed")}</SectionTitle>
        {/* B14 rule 32 — one sentence for the section. */}
        <p className="text-body text-neutral-700" data-stop-lead="">
          {t("portal.stopRestart.lead")}
        </p>
        <RadioList
          name={t("portal.stopRestart.comingBack")}
          value={comingBack}
          options={[
            {
              value: "yes",
              label: t("portal.stopRestart.comingBackYes"),
              hint: t("portal.stopRestart.comingBackYesHint"),
            },
            {
              value: "later",
              label: t("portal.stopRestart.comingBackLater"),
              hint: t("portal.stopRestart.comingBackLaterHint"),
            },
          ]}
          onChange={(value) => {
            setComingBack(value as "yes" | "later");
            // ⚠ A date already typed is CLEARED when the answer changes to
            // *no date yet*, because leaving it behind would send a restart the
            // customer has just said they do not have.
            if (value === "later") setStartAgain("");
          }}
        />
        <ButtonRow>
          <Button variant="primary" size="default" data-action="continue" onClick={() => setStep("when")}>
            {t("portal.stopRestart.continue")}
          </Button>
        </ButtonRow>
      </Card>,
      <Panel as="aside" title={t("portal.stopRestart.notSure")}>
        {t("portal.stopRestart.notSureBody")}
      </Panel>,
    );
  }

  /* ══ STEP 2 · WHEN (wireframe s21) ══════════════════════════════════════ */
  if (step === "when") {
    return frame(
      <Card testId="stop-restart">
        <SectionTitle>{t("portal.stopRestart.whenHeading")}</SectionTitle>
        <FormField
          id="stop_from"
          label={t("portal.stopRestart.stopFrom")}
          required
          helper={t("portal.stopRestart.stopFromHelp")}
        >
          <TextInput id="stop_from" type="date" value={stopFrom} onChange={setStopFrom} />
        </FormField>
        {comingBack === "yes" ? (
          // ⚠ The old helper — *"leave this blank if you do not know yet"* —
          // is gone rather than reworded: step 1 has just asked that exact
          // question, and this box only draws when the answer was *yes, and I
          // know the date*. A helper repeating a question already answered is
          // the screen not listening.
          <FormField
            id="start_again"
            label={t("portal.stopRestart.startAgain")}
            required
            error={restartBeforeStop ? t("portal.stopRestart.restartBeforeStop") : null}
          >
            <TextInput id="start_again" type="date" value={startAgain} onChange={setStartAgain} />
          </FormField>
        ) : null}
        <FormField id="reason" label={t("portal.stopRestart.why")}>
          <TextInput id="reason" multiline value={reason} onChange={setReason} />
        </FormField>
        {/* ⚠ **THE CONSEQUENCE BOX IS ON THIS STEP *AND* ON THE READ-BACK, AND
            THAT REPETITION IS THE POINT.** `BR-CWP-080`'s sentence — *the
            account stays open* — is what prevents the most expensive
            misunderstanding in the product, and a customer choosing a date is
            exactly who needs to read it. Showing it only on the last step
            would put it after the decision it exists to inform. */}
        {consequences}
        {/* `DEF-CWP-9164` — Back on the LEFT, Continue on the RIGHT. */}
        <WizardFooter
          back={
            <Button variant="secondary" size="default" data-action="back" onClick={() => setStep("what")}>
              {t("portal.stopRestart.back")}
            </Button>
          }
          forward={
            <Button
              variant="primary"
              size="default"
              data-action="continue"
              disabled={!stopFrom || restartBeforeStop}
              title={!stopFrom ? t("portal.stopRestart.commitHeld") : undefined}
              // F-22 (`DEF-CWP-10551`): the reason is drawn as text below too.
              aria-describedby={!stopFrom ? "stop-continue-reason" : undefined}
              onClick={() => setStep("check")}
            >
              {t("portal.stopRestart.continue")}
            </Button>
          }
        />
        <ButtonReason id="stop-continue-reason" reason={!stopFrom ? t("portal.stopRestart.commitHeld") : null} />
        {failed ? (
          <Announced tone="error" className="text-base font-semibold text-danger-700" data-stop-failed="">
            {t("portal.stopRestart.couldNotRead")}
          </Announced>
        ) : null}
      </Card>,
      <Comparison answer={answer} />,
    );
  }

  /* ══ STEP 3 · CHECK (wireframe s23) ═════════════════════════════════════
   *
   * ⚠ **THE READ-BACK THE SCREEN DID NOT HAVE.** *Request this ✓* used to sit
   * under the date boxes: a destructive commit with nothing between the typing
   * and the press. The drawing puts a whole step there — *"nothing is stopped
   * until you press the button"* — and each block names the step it came from.
   *
   * ⚠ **THE WIREFRAME'S THIRD STEP — *where the final bill goes* — IS ABSENT,
   * AND ITS ABSENCE IS THE HONEST ANSWER RATHER THAN AN OVERSIGHT.** s22 asks
   * for a forwarding address and a deposit-refund destination, and shows the
   * deposit held. `POST accounts/{id}/stop-or-restart/ask` accepts a stop date,
   * a restart date, a reason and a contact — and no address, no refund
   * destination and no deposit at all; `GET stop-or-restart` serves no deposit
   * figure either. A step of forwarding-address boxes that posted nowhere would
   * be a screen collecting the one thing a leaving customer most needs us to
   * have and quietly dropping it (hard-won law 2). It is reported as a gap
   * rather than drawn as a promise.
   *
   * ⚠ **AND UNTIL 2026-09-11 THESE THREE PARAGRAPHS WERE THE *ONLY* RECORD OF
   * IT ANYWHERE — `DEF-CWP-4874`.** No question, no plan row, no rule. A
   * deferral written as a code comment is tracked by nothing, which is
   * `DEF-CWP-4203`'s own escape reason and hard-won law 1 in its plainest
   * form: **the comment is now a CITATION and not the record.** The question
   * is `OQ-CWP-1767` (OPEN, three costed options, and the note that a
   * forwarding address already has a lawful home in `customers.addresses`
   * `kind='mailing'` — CLAUDE.md hard rule 8's first exception); the plan row
   * is `04-docs/05-modules/15-portal/10-execution-plan.md` §12, which also
   * names the other end of the same gap — `CWP-032`'s drawn *WHERE WE SENT IT*
   * block cannot exist while this step does not.
   *
   * ⚠ **AND THE FOUR DATES ARE NOT DRAWN EITHER, WHICH IS DECIDED RATHER THAN
   * OPEN.** s23 ends with *meter read Sep 30 · final bill around Oct 5 · due
   * around Oct 20 · deposit back by Nov 4*. Nothing on this wire carries them,
   * and the blueprint's **R-23** — *no sentence states a fact it does not
   * derive* — forbids printing them; a timeline of invented dates on the screen
   * that closes a supply is the most expensive kind of guess. **They stay
   * absent**, recorded in the decision log of 2026-09-11 rather than left for
   * the next lane to re-decide. What IS served — the supply date, that the
   * account stays open, and the standing charge — is what the box below says.
   */
  return frame(
    <Card testId="stop-check">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <SectionTitle>{t("portal.stopRestart.checkTitle")}</SectionTitle>
        <Button
          variant="secondary"
          size="sm"
          data-change="when"
          onClick={() => setStep("when")}
        >
          {t("portal.stopRestart.change")}
        </Button>
      </div>
      {/* B14 rule 32 — one sentence for the section. */}
      <p className="text-body text-neutral-700" data-check-lead="">
        {t("portal.stopRestart.checkLead")}
      </p>
      <KVList
        rows={[
          ...(chosen
            ? [
                {
                  key: "property",
                  label: t("portal.stopRestart.property"),
                  value: `${chosen.label} · ${chosen.account_no}`,
                },
              ]
            : []),
          {
            key: "last_day",
            label: t("portal.stopRestart.lastDay"),
            value: asDate(stopFrom) || "—",
          },
          {
            key: "back_on",
            label: t("portal.stopRestart.backOn"),
            value: startAgain ? asDate(startAgain) : t("portal.stopRestart.backOnNoDate"),
          },
          {
            key: "services",
            label: t("portal.stopRestart.services"),
            value:
              (answer?.services ?? []).map((row) => row.name).join(" · ") ||
              t("portal.stopRestart.servicesUnknown"),
          },
          {
            key: "why",
            label: t("portal.stopRestart.why"),
            value: reason.trim() || t("portal.stopRestart.notSaid"),
          },
        ]}
      />
      <SectionTitle>{t("portal.stopRestart.howWeReachYou")}</SectionTitle>
      {/* B14 rule 32 — one sentence for the section. */}
      <p className="text-body text-neutral-700" data-contact-lead="">
        {t("portal.stopRestart.howWeReachYouWhy")}
      </p>
      <FormField id="stop_name" label={t("portal.report.yourName")}>
        <TextInput
          id="stop_name"
          value={contact.name}
          onChange={(value) => setContact((was) => ({ ...was, name: value }))}
        />
      </FormField>
      <FormField id="stop_phone" label={t("portal.report.phone")} required>
        <TextInput
          id="stop_phone"
          value={contact.phone}
          onChange={(value) => setContact((was) => ({ ...was, phone: value }))}
        />
      </FormField>
      <FormField id="stop_email" label={t("portal.stopRestart.yourEmail")}>
        <TextInput
          id="stop_email"
          type="email"
          value={contact.email}
          onChange={(value) => setContact((was) => ({ ...was, email: value }))}
        />
      </FormField>
      {consequences}
      {/* `DEF-CWP-9164` — Back on the LEFT, the commit on the RIGHT. */}
      <WizardFooter
        back={
          <Button variant="secondary" size="default" data-action="back" onClick={() => setStep("when")}>
            {t("portal.stopRestart.back")}
          </Button>
        }
        forward={
          <>
            {/* ⚠ **THE DANGER TIER, AT LAST** — `08-screen-layouts.md` CWP-052:
                *"`Button(danger)` Request this ✓ … Second danger-tier commit"*, and
                this file's own docstring has claimed it since it was written while
                the DOM measured `data-variant="primary"`. B14 rule 6 reserves the
                tier for a destructive commit, and asking a utility to turn a
                household's water off is one. */}
            <CommitButton
              label={t("portal.stopRestart.commit")}
              working={working}
              ready={Boolean(stopFrom) && !restartBeforeStop && hasPhone}
              reason={
                hasPhone ? t("portal.stopRestart.commitHeld") : t("portal.stopRestart.phoneHeld")
              }
              tier="danger"
              onClick={() => {
                setWorking(true);
                askToStopOrRestart(props.accountId, {
                  stop_from: stopFrom,
                  start_again: startAgain || null,
                  reason,
                  name: contact.name.trim() || undefined,
                  email: contact.email.trim() || undefined,
                  phone: contact.phone.trim(),
                })
                  .then((result) => {
                    setWorking(false);
                    setSent(result.reference);
                  })
                  .catch(() => {
                    setWorking(false);
                    setFailed(true);
                  });
              }}
            />
          </>
        }
      />
      {failed ? (
        <Announced tone="error" className="text-base font-semibold text-danger-700" data-stop-failed="">
          {t("portal.stopRestart.couldNotRead")}
        </Announced>
      ) : null}
    </Card>,
    <Comparison answer={answer} />,
  );
}

/**
 * *Would moving out be cheaper?* — the panel that names the option.
 *
 * ⚠ **IT IS ABSENT UNTIL THERE ARE DATES TO COMPARE, RATHER THAN PRESENT AND
 * EMPTY** (`BR-CWP-093`). A panel of dashes over a heading that promises a
 * verdict is worse than no panel: it looks like an answer.
 */
function Comparison(props: { answer: PortalStopOrRestart | null }) {
  const { t } = useTranslation();
  const answer = props.answer;
  if (answer === null) {
    return (
      <Card testId="stop-compare-waiting">
        <SectionTitle>{t("portal.stopRestart.compareTitle")}</SectionTitle>
        <p className="text-body text-neutral-600" data-compare-waiting="">
          {t("portal.stopRestart.compareWaiting")}
        </p>
      </Card>
    );
  }

  const currency = answer.currency;
  return (
    <Card testId="stop-compare">
      <SectionTitle>{t("portal.stopRestart.compareTitle")}</SectionTitle>
      {answer.cost_of_stopping === null || answer.cost_of_closing === null ? (
        // TC-8 — the comparison SAYS SO rather than showing `$0.00` as a
        // saving. One sentence covers every reason the server can give: the
        // customer's question is *can you tell me?* and the answer is no.
        <p className="text-body text-neutral-600" data-compare-unavailable="">
          {t("portal.stopRestart.compareUnavailable")}
        </p>
      ) : (
        <>
          <KVList
            rows={[
              {
                key: "stopping",
                label: t("portal.stopRestart.costOfStopping", {
                  count: answer.months ?? 0,
                }),
                value: formatMoney(answer.cost_of_stopping, currency),
              },
              {
                key: "connection",
                label: t("portal.stopRestart.connectionFee"),
                value:
                  answer.connection_fee === null
                    ? t("portal.stopRestart.notPriced")
                    : formatMoney(answer.connection_fee, currency),
              },
              {
                key: "deposit",
                label: t("portal.stopRestart.newDeposit"),
                value:
                  answer.new_deposit === null
                    ? t("portal.stopRestart.notPriced")
                    : formatMoney(answer.new_deposit, currency),
              },
            ]}
          />
          <TotalRow
            testKey="closing"
            label={t("portal.stopRestart.costOfClosing")}
            value={formatMoney(answer.cost_of_closing, currency)}
          />
          {/* ⚠ THE VERDICT IS THE SERVER'S WORD, RENDERED. The screen picks a
              sentence from a code; it never compares the two figures itself. */}
          <p className="text-body font-bold text-neutral-900" data-verdict={answer.cheaper ?? ""}>
            {answer.cheaper === "closing"
              ? t("portal.stopRestart.closingIsCheaper")
              : t("portal.stopRestart.stoppingIsCheaper")}
          </p>
        </>
      )}
    </Card>
  );
}
